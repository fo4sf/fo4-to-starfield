"""Keep/animation compatibility with a real reservation lease and port commands.

The command fixture uses synthetic core metadata, not a private core stage.
test_paired_stage separately exercises the actual synthetic core ESM writer.
No new keep/animation options are exposed by paired_stage's pinned request CLI.
"""
import copy
from contextlib import redirect_stdout
from dataclasses import replace
import hashlib
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tests"), str(ROOT / "scripts/terrain"), str(ROOT / "src")]
import paired_stage as paired
import port_marker_store as store
import test_port_marker_callers as callers
import test_vmad_patch as fixture
import vmad_patch as vp


class PortMarkerModeTests(unittest.TestCase):
    def setUp(self):
        self.fixture = callers.PairedCallerTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        f = self.fixture
        # Same synthetic promotion used by main's standalone animation tests.
        f.case.base = f.case.base.replace(b"STAT", b"DOOR")
        f.case.patched = f.case.patched.replace(b"STAT", b"DOOR")
        for mapping in (f.case.mapping, f.case.patched_map):
            mapping["DOOR:FO4Port_door02"] = mapping.pop("STAT:FO4Port_door02")
        f.map_raw = json.dumps(f.case.mapping).encode()
        (f.port / "FO4Port.esm").write_bytes(f.case.base)
        (f.port / "formids.json").write_bytes(f.map_raw)
        f.directory = f.root / "animated-reservations"
        f.initial = store.initialize(f.directory, f.case.base, f.map_raw, f.case.patched,
                                     json.dumps(f.case.patched_map).encode(), f.case.doors,
                                     plugin="FO4Port.esm", core_plugin="Core.esm")
        self.source = f.case.sources[1]
        self.merge = (-1200, -2700, 0)
        self.keep = {self.source: 0x805}
        self.animated = {self.source: 1.25}

    def selected(self, writer):
        port, cluster, _ = self.fixture.produce(writer, [self.source])
        return port["_marker_plan"], cluster, self.fixture.consumer_entries(cluster)

    def pins(self, plan):
        f = self.fixture
        return dict(marker_plan=plan, expected_sha256=plan.sha256,
                    base_map_raw=f.map_raw, base_map_sha256=hashlib.sha256(f.map_raw).hexdigest())

    def patched(self, plan, entries):
        edits = vp.port_edits("Core.esm", entries, "FO4Port.esm", 0x804, self.merge,
                              self.keep, self.animated, base_raw=self.fixture.case.base, **self.pins(plan))
        plugin = vp.Plugin(self.fixture.case.base)
        vp.patch_port(plugin, edits, 1)
        return plugin

    def test_retained_gap_kept_and_animated_checks_share_the_pinned_plan(self):
        f = self.fixture
        with store.session(f.directory, f.initial.sha256) as writer:
            plan, _, entries = self.selected(writer)
            plugin = self.patched(plan, entries)
            self.assertEqual(plugin.hedr()[2], 0x806)
            self.assertNotIn(0x01000804, plugin.records())
            vmad = dict(plugin.find(0x01000803)[2].fields())[b"VMAD"]
            name, marker, pos, seconds = vp.animated_load_door_target(vmad)
            self.assertEqual((name, marker, seconds), ("Core.esm", int(entries[0]["ids"]["arrival"], 16), 1.25))
            self.assertTrue(vp.same_position(pos, vp.merged(entries[0]["arrival"]["pos"], self.merge)))
            for kept in (False, True):
                checks = vp.check_port(vp.Plugin(f.case.base), plugin, entries, "Core.esm", self.merge,
                                       kept=kept, animated=self.animated, **self.pins(plan))
                self.assertTrue(all(ok for _, ok in checks), checks)
            self.assertEqual(writer.raw, f.initial.state)

    def test_kept_ids_cannot_override_reservations_even_if_the_cluster_agrees(self):
        f = self.fixture
        with store.session(f.directory, f.initial.sha256) as writer:
            plan, _, entries = self.selected(writer)
            wrong = copy.deepcopy(entries)
            wrong[0]["destination"]["id"] = 0x806
            with self.assertRaisesRegex(ValueError, "kept marker differs from pinned reservation"):
                vp.port_edits("Core.esm", wrong, "FO4Port.esm", 0x804, self.merge,
                              {self.source: 0x806}, self.animated, base_raw=f.case.base, **self.pins(plan))
            with self.assertRaisesRegex(ValueError, "not in the kept doors build"):
                vp.port_edits("Core.esm", entries, "FO4Port.esm", 0x804, self.merge,
                              {}, self.animated, base_raw=f.case.base, **self.pins(plan))
            self.assertEqual(writer.raw, f.initial.state)

    def test_kept_mode_still_rejects_stale_pins_and_wrong_animation(self):
        f = self.fixture
        with store.session(f.directory, f.initial.sha256) as writer:
            plan, _, entries = self.selected(writer)
            plugin = self.patched(plan, entries)
            for change in ({"expected_sha256": "0" * 64}, {"animated": {self.source: 2.5}},
                           {"animated": None}):
                options = dict(self.pins(plan), kept=True, animated=self.animated)
                options.update(change)
                checks = vp.check_port(vp.Plugin(f.case.base), plugin, entries, "Core.esm", self.merge, **options)
                self.assertFalse(all(ok for _, ok in checks), change)
            plain = vp.Plugin(plugin.serialize())
            plain.set_vmad(0x01000803, vp.load_door_vmad("Core.esm", int(entries[0]["ids"]["arrival"], 16),
                                                      vp.merged(entries[0]["arrival"]["pos"], self.merge)))
            checks = vp.check_port(vp.Plugin(f.case.base), plain, entries, "Core.esm", self.merge,
                                   kept=True, animated=self.animated, **self.pins(plan))
            self.assertFalse(all(ok for _, ok in checks))

    def command_args(self, writer):
        f = self.fixture
        plan, cluster, entries = self.selected(writer)
        core = f.root / "core"
        fixture.core_folder(str(core), entries, plugin="Core.esm")
        pair = paired.Pair(writer, plan, cluster, f.case.base, f.map_raw, "FO4Port.esm", core)
        keep = f.root / "keep.json"
        keep.write_text(json.dumps({"doors": [{"src": self.source, "marker": "000805"}]}), encoding="utf-8")
        manifest = f.root / "manifest.json"
        manifest.write_text(json.dumps({"items": [{"editor_id": "FO4Port_door02",
                             "load_door": {"anim": {"open_seconds": 1.25}}}]}), encoding="utf-8")
        return SimpleNamespace(core=str(core), port=str(f.port), out=str(f.root / "output"), paired=pair,
                               keep_markers=str(keep), animated_doors=str(manifest))

    def test_actual_port_commands_forward_kept_animation_and_live_pair(self):
        f = self.fixture
        before = paired.inventory(f.port)
        with store.session(f.directory, f.initial.sha256) as writer, redirect_stdout(io.StringIO()):
            args = self.command_args(writer)
            self.assertEqual(vp.cmd_port(args), 0)
            self.assertEqual(vp.cmd_check(args), 0)
            report = json.loads((Path(args.out) / "doors.json").read_bytes())
            self.assertEqual(report["doors"][0]["marker"], "000805")
            self.assertEqual(report["doors"][0]["script"], vp.ANIMATED_SCRIPT)
            self.assertEqual(report["doors"][0]["open_seconds"], 1.25)
            self.assertEqual(report["merge_offset"], list(self.merge))
            self.assertEqual(writer.raw, f.initial.state)
        self.assertEqual(before, paired.inventory(f.port))
        with self.assertRaises(OSError):
            vp.cmd_check(args)  # output metadata cannot recreate the closed lease

    def test_actual_port_refuses_kept_conflict_before_output(self):
        f = self.fixture
        before = paired.inventory(f.port)
        with store.session(f.directory, f.initial.sha256) as writer:
            args = self.command_args(writer)
            Path(args.keep_markers).write_text(json.dumps({"doors": [{"src": self.source, "marker": "000806"}]}),
                                               encoding="utf-8")
            with self.assertRaisesRegex(SystemExit, "kept marker differs from pinned reservation"):
                vp.cmd_port(args)
            self.assertFalse(Path(args.out).exists())
            self.assertEqual(writer.raw, f.initial.state)
        self.assertEqual(before, paired.inventory(f.port))

    def test_actual_port_refuses_stale_pair_pin_before_output(self):
        f = self.fixture
        with store.session(f.directory, f.initial.sha256) as writer:
            args = self.command_args(writer)
            args.paired.plan = replace(args.paired.plan, sha256="0" * 64)
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                vp.cmd_port(args)
            self.assertFalse(Path(args.out).exists())
            self.assertEqual(writer.raw, f.initial.state)


if __name__ == "__main__":
    unittest.main()
