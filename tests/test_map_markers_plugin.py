"""dotnet/MapMarkers on a synthetic core (the actual terrain writer, dotnet/TerrainOverlays, on the synthetic master of
test_terrain_reference_identity with the map-marker template), never a game: the quest's Markers are the core's own
MapMarker REFRs in FormID order and LocalX / LocalY / LocalZ their written positions (docs/terrain/map-markers.md
"Markers in the merged world"); the plugin's overrides of those REFRs (the marker's own name shown, the arrival lifted,
docs/terrain/map-markers.md "Overrides"); plus the Papyrus script's contract (it cannot be compiled here)."""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
import test_terrain_reference_identity as tri  # noqa: E402
import test_terrain_lights_writer as tlw  # noqa: E402

SCRIPT = ROOT / "scripts/mapmarkers/FO4SF_MapMarkers.psc"
PROGRAM = ROOT / "dotnet/MapMarkers/Program.cs"
Z_LIFT = 2.5                     # dotnet/MapMarkers DefaultZLift, metres above the core's sampled terrain height
Z_LIFT_STEP = 0.1                # dotnet/MapMarkers ZLiftStep: the build takes a lift on this grid only
USE_LOCATION_NAME, VISIBLE = 0x8, 0x1   # map-marker FNAM bits (docs/terrain/map-markers.md)


def build(dotnet, project):
    proc = subprocess.run([dotnet, "build", str(ROOT / "dotnet" / project), "-c", "Release", "--nologo"],
                          capture_output=True, text=True)
    if proc.returncode:
        raise AssertionError(proc.stdout + proc.stderr)
    return ROOT / f"dotnet/{project}/bin/Release/net9.0/{project}.dll"


class MapMarkersPluginTests(unittest.TestCase):
    run_writer = tri.TerrainReferenceIdentityTests.run_writer

    @classmethod
    def setUpClass(cls):
        cls.dotnet = shutil.which("dotnet")
        if not cls.dotnet:
            raise unittest.SkipTest(".NET SDK needed for the actual writer test")
        fixture = build(cls.dotnet, "TerrainIdentityFixture")
        cls.writer = Path(os.environ.get("FO4SF_TERRAIN_WRITER", build(cls.dotnet, "TerrainOverlays")))
        cls.tool = build(cls.dotnet, "MapMarkers")
        temporary = tempfile.TemporaryDirectory(prefix="fo4sf-mapmarkers-")
        cls.addClassCleanup(temporary.cleanup)
        cls.root = Path(temporary.name)
        cls.master = cls.root / "master/Starfield.esm"
        subprocess.run([cls.dotnet, str(fixture), str(cls.master), "map-marker"], capture_output=True, check=True)
        cls.params = {                                   # test_terrain_map_marker_writer's synthetic overlay
            "plugin": "Synthetic.esm", "hmin": 0, "hmax": 1, "alignment": "absolute", "hnam": 0,
            "objects": "objects.json", "overlays": [{"world": "SyntheticWorld", "block": "SyntheticBlock",
            "location": "SyntheticLocation", "tag": "Synthetic", "n": 2, "cell_min": 0, "cell_max": 1,
            "btd_path": "Terrain/Synthetic.btd", "fnam": [0] * 4, "bounds_min_m": 0, "bounds_max_m": 200,
            "spawn": [1, 1, 2], "spawn_cell": [1, 0], "coc": "SyntheticSpawn",
            "anchor": {"form_id": 0x800, "edid": "SyntheticAnchor", "local": [1, 1, 2]}}]}
        cls.objects = {"world": "SyntheticWorld", "bases": [{"edid": "SyntheticBase", "model": "synthetic.nif"}],
                       "refs": [{"src": "000001:Synthetic.esm", "base": 0, "cell": [0, 0], "pos": [1, 2, 3],
                                 "rot": [0, 0, 0], "scale": 1, "disabled": False}]}
        ov = cls.params["overlays"][0]
        cls.markers = [{"tag": "RedRocket", "name": "Red Rocket Truck Stop", "pos": ov["spawn"], "cell": [0, 0]},
                       {"tag": "Sanctuary", "name": "Sanctuary Hills", "pos": [150.0, 50.0, 1.0], "cell": [1, 0]},
                       {"tag": "Concord", "name": "Concord", "pos": [50.0, 150.0, 1.5], "cell": [0, 1]}]
        ov["map_markers"] = cls.markers
        proc, cls.stage = cls.run_writer(cls, cls.objects, "core")
        if proc.returncode:
            raise AssertionError(proc.stdout + proc.stderr)
        cls.core = cls.stage / "Synthetic.esm"
        cls.ids = json.loads((cls.stage / "formids.json").read_text())["map_marker_refs"]["SyntheticWorld"]

    def tool_run(self, *argv):
        return subprocess.run([self.dotnet, str(self.tool), *map(str, argv)], capture_output=True, text=True)

    def test_build_lists_every_core_marker_with_its_written_position(self):
        out = self.root / "plugin"
        proc = self.tool_run("build", "--core", self.core, "--out", out)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        plugin = out / "FO4SFMapMarkers.esm"
        check = self.tool_run("check", plugin, self.core)
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        self.assertIn("all checks pass", check.stdout)
        recs = tri.records(plugin)
        # the quest, plus an override of each core marker under the core's worldspace and persistent cell: nothing else
        self.assertEqual(sorted(k for k, r in recs.items() if r[0] == b"REFR"), sorted(int(v, 16) for v in self.ids.values()))
        self.assertEqual(sorted(r[0] for r in recs.values()), [b"CELL", b"QUST"] + [b"REFR"] * 3 + [b"WRLD"])
        for m in self.markers:
            sig, payload, _, flags = recs[int(self.ids[m["tag"]], 16)]
            self.assertEqual(flags & 0xC00, 0x400, m["tag"])                       # persistent, enabled
            fnam = struct.unpack("<I", tlw.field(payload, b"FNAM"))[0]
            self.assertEqual(fnam & (USE_LOCATION_NAME | VISIBLE), VISIBLE, m["tag"])  # its own name, visible
            self.assertEqual(tlw.field(payload, b"FULL"), m["name"].encode() + b"\0")
            x, y, z = struct.unpack_from("<fff", tlw.field(payload, b"DATA"))
            self.assertEqual([x, y], [float(v) for v in m["pos"][:2]])
            self.assertAlmostEqual(z, m["pos"][2] + Z_LIFT, places=4)
        self.assertEqual(check.stdout.count("  override "), 3)
        self.assertIn(f"overridden (own name shown, lifted {Z_LIFT} m)", proc.stdout)
        sig, payload, _, flags = recs[0x800]
        self.assertEqual(sig, b"QUST")
        vmad = tlw.field(payload, b"VMAD")
        self.assertIsNotNone(vmad)
        self.assertEqual(struct.unpack_from("<hH", vmad), (6, 2))
        self.assertIn(b"FO4SF_MapMarkers", vmad)
        # the three markers in FormID order, each a core reference (master index 1, after Starfield.esm)
        want = sorted(int(v, 16) for v in self.ids.values())
        self.assertEqual(len(want), 3)
        got = [f & 0xFFFFFF for f in self.object_list(vmad)]
        self.assertEqual(got, want)
        # masters: Starfield.esm (the overrides' base STAT) then the core; the quest's references are the core's
        self.assertTrue(all(f >> 24 == 1 for f in self.object_list(vmad)))
        # LocalX in FormID order equals the positions the writer was given; LocalZ the lifted height the override holds
        by_id = {int(self.ids[m["tag"]], 16): m["pos"] for m in self.markers}
        self.assertIn(f"LocalX: {', '.join(self.num(by_id[i][0]) for i in want)}", check.stdout)
        self.assertIn(f"LocalZ: {', '.join(self.num(by_id[i][2] + Z_LIFT) for i in want)}", check.stdout)

    def test_z_lift_is_an_option_and_the_check_follows_it(self):
        out = self.root / "plugin-flat"
        proc = self.tool_run("build", "--core", self.core, "--out", out, "--z-lift", "0")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        plugin = out / "FO4SFMapMarkers.esm"
        recs = tri.records(plugin)
        for m in self.markers:
            z = struct.unpack_from("<fff", tlw.field(recs[int(self.ids[m["tag"]], 16)][1], b"DATA"))[2]
            self.assertAlmostEqual(z, m["pos"][2], places=4)
        self.assertEqual(self.tool_run("check", plugin, self.core, "--z-lift", "0").returncode, 0)
        other = self.tool_run("check", plugin, self.core)               # the default lift is not what was built
        self.assertEqual(other.returncode, 1, other.stdout)
        self.assertIn(f"not the core's {self.num(self.markers[0]['pos'][2])} lifted {Z_LIFT} m", other.stdout)
        bad = self.tool_run("build", "--core", self.core, "--out", self.root / "plugin-bad-lift", "--z-lift", "-1")
        self.assertEqual(bad.returncode, 2)
        # lifts come in steps of Z_LIFT_STEP: a change between builds smaller than the script's ZTolerance would
        # never reach a saved game (Codex on #483), so the build refuses a lift off that grid
        fine = self.tool_run("build", "--core", self.core, "--out", self.root / "plugin-fine-lift", "--z-lift", "0.55")
        self.assertEqual(fine.returncode, 2, fine.stdout + fine.stderr)
        self.assertIn("multiple of 0.1 m", fine.stderr)
        self.assertIn("ZTolerance (0.05 m)", fine.stderr)
        stepped = self.root / "plugin-step-lift"
        step = self.tool_run("build", "--core", self.core, "--out", stepped, "--z-lift", "0.5")
        self.assertEqual(step.returncode, 0, step.stdout + step.stderr)
        self.assertEqual(self.tool_run("check", stepped / "FO4SFMapMarkers.esm", self.core, "--z-lift", "0.5").returncode, 0)

    def test_check_rejects_an_override_that_still_uses_the_location_name(self):
        out = self.root / "plugin-locname"
        self.assertEqual(self.tool_run("build", "--core", self.core, "--out", out).returncode, 0)
        plugin = out / "FO4SFMapMarkers.esm"
        data = bytearray(plugin.read_bytes())
        at = data.index(b"FNAM\x04\x00") + 6                       # the first override's map-marker flags
        struct.pack_into("<I", data, at, struct.unpack_from("<I", data, at)[0] | USE_LOCATION_NAME)
        plugin.write_bytes(bytes(data))
        check = self.tool_run("check", plugin, self.core)
        self.assertEqual(check.returncode, 1, check.stdout)
        self.assertIn("override still uses the location's name", check.stdout)

    def test_check_rejects_a_world_copy_that_no_longer_matches_the_core(self):
        # the plugin carries the core's WRLD and persistent CELL as the overrides' containers; it loads after the
        # core, so a copy taken before a core rebuild (a changed world flag) would undo the rebuild: check compares
        # both records with the core's, so a stale stage fails before it is installed
        out = self.root / "plugin-stale-world"
        proc = self.tool_run("build", "--core", self.core, "--out", out)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        plugin = out / "FO4SFMapMarkers.esm"
        fresh = self.tool_run("check", plugin, self.core)
        self.assertEqual(fresh.returncode, 0, fresh.stdout)
        # the writer gives the synthetic world the real one's SmallWorld flag and HNAM 0 (#495)
        self.assertIn("  worldspace 000803:Synthetic.esm SyntheticWorld: flags SmallWorld, HNAM [0], as the core's", fresh.stdout)
        data = bytearray(plugin.read_bytes())
        rec = data.index(b"WRLD", data.index(b"WRLD") + 4)            # the record, after the group label
        at = data.index(b"EDID", rec) + 6                             # a stale copy: its EditorID changes case
        data[at] ^= 0x20
        plugin.write_bytes(bytes(data))
        stale = self.tool_run("check", plugin, self.core)
        self.assertEqual(stale.returncode, 1, stale.stdout)
        self.assertIn("worldspace record differs from the core's (a core rebuilt since the stage: stage again)", stale.stdout)
        self.assertIn("NOT the core's", stale.stdout)

    def test_world_takes_the_border_probe_variant_and_the_check_expects_it(self):
        # --world nosmall / city: the WRLD copy as dotnet/BorderProbe's variant (SmallWorld cleared; city HNAM 5),
        # the marker overrides untouched; check wants the same --world, and fails the copy under any other
        control = self.root / "plugin-world-control"
        self.assertEqual(self.tool_run("build", "--core", self.core, "--out", control).returncode, 0)
        for world, flags, hnam in [("nosmall", "0", "0"), ("city", "0", "5")]:     # the core's: SmallWorld, HNAM [0]
            out = self.root / f"plugin-world-{world}"
            proc = self.tool_run("build", "--core", self.core, "--out", out, "--world", world)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn(f"world copy --world {world} (SmallWorld cleared, HNAM {'5' if world == 'city' else 'as the core'}", proc.stdout)
            plugin = out / "FO4SFMapMarkers.esm"
            check = self.tool_run("check", plugin, self.core, "--world", world)
            self.assertEqual(check.returncode, 0, check.stdout)
            self.assertIn(f"  worldspace 000803:Synthetic.esm SyntheticWorld: flags {flags}, HNAM [{hnam}], as the core's with --world {world}",
                          check.stdout)
            self.assertEqual(check.stdout.count("  override "), 3)       # the marker overrides, as under control
            # the bytes: the WRLD record's DATA flags (0: SmallWorld 0x1 gone) and HNAM
            data = plugin.read_bytes()
            rec = data.index(b"WRLD", data.index(b"WRLD") + 4)
            body = data[rec + 24: rec + 24 + int.from_bytes(data[rec + 4: rec + 8], "little")]
            at = body.index(b"DATA")
            flag_bytes = body[at + 6: at + 6 + int.from_bytes(body[at + 4: at + 6], "little")]
            self.assertTrue(flag_bytes and not any(flag_bytes), flag_bytes)
            at = body.index(b"HNAM")                                      # city sets 5; nosmall keeps the core's 0
            self.assertEqual(body[at + 6: at + 6 + int.from_bytes(body[at + 4: at + 6], "little")], b"\5" if world == "city" else b"\0")
            plain = self.tool_run("check", plugin, self.core)             # another --world: not this stage's
            self.assertEqual(plain.returncode, 1, plain.stdout)
            self.assertIn("NOT the core's", plain.stdout)
            self.assertIn("worldspace record differs from the core's (a core rebuilt since the stage: stage again)", plain.stdout)
            crossed = self.tool_run("check", control / "FO4SFMapMarkers.esm", self.core, "--world", world)
            self.assertEqual(crossed.returncode, 1, crossed.stdout)
            self.assertIn(f"NOT the core's with --world {world}", crossed.stdout)
            self.assertIn(f"worldspace record differs from the core's with --world {world} (a stage with another --world, or a core rebuilt since it: stage again)",
                          crossed.stdout)
        other = self.tool_run("build", "--core", self.core, "--out", self.root / "plugin-world-other", "--world", "hnam5")
        self.assertEqual(other.returncode, 2)
        self.assertIn("--world hnam5: want control", other.stderr)

    def test_many_markers_split_into_quests_of_100(self):
        params = copy.deepcopy(self.params)
        params["overlays"][0]["map_markers"] = [
            {"tag": f"M{k:03d}", "name": f"Marker {k}", "pos": [10.0 + k * 0.5, 20.0 + k * 0.25, 1.0], "cell": [0, 0]}
            for k in range(205)]
        saved, type(self).params = type(self).params, params
        try:
            proc, many = self.run_writer(self.objects, "core-many")
        finally:
            type(self).params = saved
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        out = self.root / "plugin-many"
        built = self.tool_run("build", "--core", many / "Synthetic.esm", "--out", out)
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        self.assertIn("3 quest(s) FO4SF_MapMarkersQuest 000800", built.stdout)
        check = self.tool_run("check", out / "FO4SFMapMarkers.esm", many / "Synthetic.esm")
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        recs = tri.records(out / "FO4SFMapMarkers.esm")
        self.assertEqual(sorted(k for k, r in recs.items() if r[0] == b"QUST"), [0x800, 0x801, 0x802])
        self.assertEqual(sum(1 for r in recs.values() if r[0] == b"REFR"), 205)    # one override per marker
        lists = [self.object_list(tlw.field(recs[q][1], b"VMAD")) for q in (0x800, 0x801, 0x802)]
        self.assertEqual([len(x) for x in lists], [100, 100, 5])
        ids = [f & 0xFFFFFF for x in lists for f in x]
        self.assertEqual(ids, sorted(ids))                                     # FormID order across the quests
        self.assertEqual(len(set(ids)), 205)
        for q, cap in ((0x800, 200), (0x801, 200)):
            vmad = tlw.field(recs[q][1], b"VMAD")
            name = b"\x08\x00MaxMoves"
            at = vmad.index(name) + len(name)
            self.assertEqual(struct.unpack_from("<BBi", vmad, at), (3, 1, cap))  # int property, edited, the cap
        self.assertNotIn(b"MaxMoves", tlw.field(recs[0x802][1], b"VMAD"))       # 5 markers: the script's 40
        # a plugin missing its last quest no longer matches the core
        short = self.root / "plugin-many-short"
        three = self.tool_run("build", "--core", self.core, "--out", short)
        self.assertEqual(three.returncode, 0)
        bad = self.tool_run("check", short / "FO4SFMapMarkers.esm", many / "Synthetic.esm")
        self.assertEqual(bad.returncode, 1, bad.stdout)
        self.assertIn("1 quest(s) for 205 marker(s): 3 wanted", bad.stdout)

    # sha256 of the synthetic core above and of the plugin main's dotnet/MapMarkers (5ffe8ff0, before --extra) built
    # from it with no options: a build without --extra must stay those bytes (Grok on #519)
    SYNTHETIC_CORE_SHA256 = "642628d4b3fad1397558f6a48728a7e3f3e90f09ffa58ce31a99d873b6f1dd40"
    PLAIN_PLUGIN_SHA256 = "750a80440b07bd8b042d51c1bd6d365f8d41cc440492183ed9ce4bb93811065d"

    def test_without_extra_the_plugin_is_byte_for_byte_the_one_before_extra(self):
        core = hashlib.sha256(self.core.read_bytes()).hexdigest()
        self.assertEqual(core, self.SYNTHETIC_CORE_SHA256, "the synthetic core changed (TerrainOverlays or its fixture): "
                         "rebuild the plain plugin with the last MapMarkers before the change and record both hashes")
        out = self.root / "plain"
        proc = self.tool_run("build", "--core", self.core, "--out", out)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(hashlib.sha256((out / "FO4SFMapMarkers.esm").read_bytes()).hexdigest(), self.PLAIN_PLUGIN_SHA256)

    EXTRA = [{"tag": "M01F2A9", "name": "Abernathy Farm", "src": "01F2A9:Fallout4.esm", "pos": [120.0, 30.0, 4.0], "cell": [1, 0]},
             {"tag": "M01F2AA", "name": "Starlight Drive In", "src": "01F2AA:Fallout4.esm", "pos": [40.0, 160.0, 6.5], "cell": [0, 1]}]

    def extra_file(self, name, markers):
        path = self.root / f"{name}.json"
        path.write_text(json.dumps({"markers": markers}))
        return path

    def test_extra_markers_are_the_plugins_own_with_lcsr_rows(self):
        # --extra (make_map_markers.py stage --fo4-map-markers): FO4's other markers as REFRs of this plugin, copies of
        # the core's first marker in the core world's persistent cell, one MapMarkerRefType LCSR row each in an
        # override of the core's Location, and listed after the core's markers in the quest
        extra = self.extra_file("extra", self.EXTRA)
        out = self.root / "plugin-extra"
        proc = self.tool_run("build", "--core", self.core, "--out", out, "--extra", extra)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("3 marker(s) overridden (own name shown, lifted 2.5 m), 2 of its own (--extra)", proc.stdout)
        plugin = out / "FO4SFMapMarkers.esm"
        check = self.tool_run("check", plugin, self.core, "--extra", extra)
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        self.assertIn("2 marker(s) of this plugin, 2 in --extra", check.stdout)
        recs = tri.records(plugin)
        core_ids = sorted(int(v, 16) for v in self.ids.values())
        self.assertEqual(sorted(k for k, r in recs.items() if r[0] == b"REFR"), core_ids + [0x900, 0x901])
        self.assertEqual(sorted(r[0] for r in recs.values()), [b"CELL", b"LCTN", b"QUST"] + [b"REFR"] * 5 + [b"WRLD"])
        core_recs = tri.records(self.core)
        cell = next(k for k, r in recs.items() if r[0] == b"CELL")
        template = core_recs[core_ids[0]][1]
        for k, m in zip((0x900, 0x901), self.EXTRA):
            sig, payload, owner, flags = recs[k]
            self.assertEqual(owner, cell, m["tag"])                                    # in the persistent cell copy
            self.assertEqual(flags & 0xC00, 0x400, m["tag"])                          # persistent, enabled
            self.assertEqual(tlw.field(payload, b"NAME"), struct.pack("<I", 0x10))    # Starfield.esm's MapMarker
            self.assertEqual(tlw.field(payload, b"EDID"), f"SyntheticWorldMapMarker{m['tag']}".encode() + b"\0")
            fnam = struct.unpack("<I", tlw.field(payload, b"FNAM"))[0]
            self.assertEqual(fnam & (USE_LOCATION_NAME | VISIBLE), VISIBLE, m["tag"])
            self.assertEqual(tlw.field(payload, b"TNAM"), tlw.field(template, b"TNAM"))  # the core's icon type
            self.assertEqual(tlw.field(payload, b"FULL"), m["name"].encode() + b"\0")
            x, y, z = struct.unpack_from("<fff", tlw.field(payload, b"DATA"))
            self.assertEqual([x, y], m["pos"][:2])
            self.assertAlmostEqual(z, m["pos"][2] + Z_LIFT, places=4)
        # the Location: the core's rows unchanged, then one row per own marker (own index 2, after Starfield.esm and
        # the core), the cell's grid packed as the core writes it (the core's Sanctuary row has cell [1, 0])
        sys.path.insert(0, str(ROOT / "src"))
        from fo4sf import map_markers
        loc = next(k for k, r in recs.items() if r[0] == b"LCTN")
        rows = map_markers.parse_lcsr(tlw.field(recs[loc][1], b"LCSR"))
        core_rows = map_markers.parse_lcsr(tlw.field(core_recs[loc][1], b"LCSR"))
        self.assertEqual(len(core_rows), 3)
        self.assertEqual([r["refr"] & 0xFFFFFF for r in rows[:3]], [r["refr"] & 0xFFFFFF for r in core_rows])
        self.assertEqual([r["refr"] for r in rows[3:]], [0x02000900, 0x02000901])
        self.assertEqual({r["lcrt"] for r in rows}, {map_markers.MAPMARKER_REF_TYPE})
        self.assertEqual({r["wrld"] for r in rows}, {rows[0]["wrld"]})
        self.assertEqual({r["tail"] for r in rows}, {map_markers.LCSR_TAIL})
        sanctuary = int(self.ids["Sanctuary"], 16)
        self.assertEqual(rows[3]["pad"], next(r["pad"] for r in core_rows if r["refr"] & 0xFFFFFF == sanctuary))
        self.assertNotEqual(rows[3]["pad"], rows[4]["pad"])
        # the quest: the core's markers in FormID order (index 1), then the plugin's own (index 2)
        got = self.object_list(tlw.field(recs[0x800][1], b"VMAD"))
        self.assertEqual(got, [0x01000000 | i for i in core_ids] + [0x02000900, 0x02000901])
        by_id = {int(self.ids[m["tag"]], 16): m["pos"] for m in self.markers}
        xs = [by_id[i][0] for i in core_ids] + [m["pos"][0] for m in self.EXTRA]
        zs = [by_id[i][2] + Z_LIFT for i in core_ids] + [m["pos"][2] + Z_LIFT for m in self.EXTRA]
        self.assertIn(f"LocalX: {', '.join(self.num(v) for v in xs)}", check.stdout)
        self.assertIn(f"LocalZ: {', '.join(self.num(v) for v in zs)}", check.stdout)

    def test_check_wants_the_same_extra_markers(self):
        extra = self.extra_file("extra-same", self.EXTRA)
        out = self.root / "plugin-extra-same"
        self.assertEqual(self.tool_run("build", "--core", self.core, "--out", out, "--extra", extra).returncode, 0)
        plugin = out / "FO4SFMapMarkers.esm"
        bare = self.tool_run("check", plugin, self.core)                    # without --extra: they are not expected
        self.assertEqual(bare.returncode, 1, bare.stdout)
        self.assertIn("is a REFR of this plugin that --extra and --landing do not list", bare.stdout)
        self.assertIn("1 Location record(s) without --extra or --landing", bare.stdout)
        moved = copy.deepcopy(self.EXTRA)
        moved[1]["pos"][0] += 1.0
        far = self.tool_run("check", plugin, self.core, "--extra", self.extra_file("extra-moved", moved))
        self.assertEqual(far.returncode, 1, far.stdout)
        self.assertIn("not --extra's (41, 160, 6.5) lifted 2.5 m", far.stdout)
        renamed = copy.deepcopy(self.EXTRA)
        renamed[0]["cell"] = [0, 0]                                          # another grid: the LCSR row differs
        grid = self.tool_run("check", plugin, self.core, "--extra", self.extra_file("extra-grid", renamed))
        self.assertEqual(grid.returncode, 1, grid.stdout)
        self.assertIn("LCSR rows are not the core's followed by one MapMarkerRefType row per own marker", grid.stdout)
        plain = self.root / "plugin-extra-none"                              # a plugin without them, checked with them
        self.assertEqual(self.tool_run("build", "--core", self.core, "--out", plain).returncode, 0)
        missing = self.tool_run("check", plain / "FO4SFMapMarkers.esm", self.core, "--extra", extra)
        self.assertEqual(missing.returncode, 1, missing.stdout)
        self.assertIn("(M01F2A9 \"Abernathy Farm\", --extra) is missing", missing.stdout)
        self.assertIn("Location records []: want one override of", missing.stdout)

    def test_check_rejects_a_location_copy_that_no_longer_matches_the_core(self):
        extra = self.extra_file("extra-loc", self.EXTRA)
        out = self.root / "plugin-extra-loc"
        self.assertEqual(self.tool_run("build", "--core", self.core, "--out", out, "--extra", extra).returncode, 0)
        plugin = out / "FO4SFMapMarkers.esm"
        data = bytearray(plugin.read_bytes())
        rec = data.index(b"LCTN", data.index(b"LCTN") + 4)                   # the record, after the group label
        at = data.index(b"EDID", rec) + 6                                     # a stale copy: its EditorID changes case
        data[at] ^= 0x20
        plugin.write_bytes(bytes(data))
        stale = self.tool_run("check", plugin, self.core, "--extra", extra)
        self.assertEqual(stale.returncode, 1, stale.stdout)
        self.assertIn("Location override differs from the core's beyond its LCSR rows (a core rebuilt since the stage: stage again)",
                      stale.stdout)

    def test_build_refuses_a_bad_extra_file(self):
        for name, markers, want in [
                ("extra-repeat", [self.EXTRA[0], dict(self.EXTRA[1], tag="m01f2a9")], "tag M01F2A9 repeats"),
                ("extra-noname", [dict(self.EXTRA[0], name="")], "M01F2A9: no name"),
                ("extra-badtag", [dict(self.EXTRA[0], tag="M 1")], 'tag "M 1": want letters, digits or _'),
                ("extra-short", [dict(self.EXTRA[0], pos=[1.0, 2.0])], "M01F2A9: pos needs 3 finite numbers")]:
            proc = self.tool_run("build", "--core", self.core, "--out", self.root / f"plugin-{name}", "--extra",
                                 self.extra_file(name, markers))
            self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
            self.assertIn(want, proc.stderr)
        # a marker the core already has (a core built with --fo4-map-markers) is not added twice
        dup = self.tool_run("build", "--core", self.core, "--out", self.root / "plugin-extra-dup", "--extra",
                            self.extra_file("extra-dup", [dict(self.EXTRA[0], tag="Sanctuary")]))
        self.assertEqual(dup.returncode, 1, dup.stdout + dup.stderr)
        self.assertIn("the core already has a record SyntheticWorldMapMarkerSanctuary", dup.stderr)

    def test_extra_markers_fill_the_quests_after_the_core_markers(self):
        # 3 core markers and 205 of the plugin's own: quests of 100, 100 and 8, each with its own move budget
        many = [{"tag": f"M{k:06X}", "name": f"Marker {k}", "pos": [10.0 + k * 0.5, 20.0 + k * 0.25, 1.0], "cell": [0, 0]}
                for k in range(205)]
        extra = self.extra_file("extra-many", many)
        out = self.root / "plugin-extra-many"
        built = self.tool_run("build", "--core", self.core, "--out", out, "--extra", extra)
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        self.assertIn("3 quest(s) FO4SF_MapMarkersQuest 000800", built.stdout)
        check = self.tool_run("check", out / "FO4SFMapMarkers.esm", self.core, "--extra", extra)
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        # the third quest is 0x802 of this plugin, the core's Location override 0x802 of the core: read by full FormID
        recs = self.records_by_form(out / "FO4SFMapMarkers.esm")
        lists = [self.object_list(tlw.field(recs[0x02000000 | q][1], b"VMAD")) for q in (0x800, 0x801, 0x802)]
        self.assertEqual([len(x) for x in lists], [100, 100, 8])
        flat = [f for x in lists for f in x]
        self.assertEqual([f >> 24 for f in flat], [1] * 3 + [2] * 205)       # the core's first, then the plugin's
        self.assertEqual([f & 0xFFFFFF for f in flat[3:]], list(range(0x900, 0x900 + 205)))
        nxt = struct.unpack_from("<I", (out / "FO4SFMapMarkers.esm").read_bytes(), 24 + 4 + 2 + 8)[0]   # HEDR next id
        self.assertEqual(nxt, 0x900 + 205)

    @staticmethod
    def landing(**kw):
        """fo4sf.map_markers.landing_spot on the synthetic overlay (0..200 m): the pad at (100, 100), flat ground at 1 m."""
        sys.path.insert(0, str(ROOT / "src"))
        from fo4sf import map_markers
        return map_markers.landing_spot(100.0, 100.0, (0, 200), lambda x, y: 1.0, Z_LIFT, **kw)

    def landing_file(self, name, spot):
        path = self.root / f"{name}.json"
        path.write_text(json.dumps({"landing": spot}))
        return path

    def test_landing_spot_is_landingoverlay01s_four_references_and_rows(self):
        # --landing (make_map_markers.py stage --landing): the pad, its landing-zone trigger, the "Landing Area" marker
        # and its heading, persistent in the world copy, linked as LandingOverlay01's, with its three LCSR rows after
        # --extra's, and listed after the plugin's markers in the quest
        sys.path.insert(0, str(ROOT / "src"))
        from fo4sf import map_markers
        spot = self.landing()
        landing, extra = self.landing_file("landing", spot), self.extra_file("extra-landing", self.EXTRA)
        out = self.root / "plugin-landing"
        proc = self.tool_run("build", "--core", self.core, "--out", out, "--extra", extra, "--landing", landing)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("2 of its own (--extra), a landing spot (--landing RedRocketNorth)", proc.stdout)
        plugin = out / "FO4SFMapMarkers.esm"
        check = self.tool_run("check", plugin, self.core, "--extra", extra, "--landing", landing)
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        self.assertEqual(check.stdout.count("  landing 0008F"), 4)
        recs = tri.records(plugin)
        core_ids = sorted(int(v, 16) for v in self.ids.values())
        self.assertEqual(sorted(k for k, r in recs.items() if r[0] == b"REFR"),
                         core_ids + [0x8F0, 0x8F1, 0x8F2, 0x8F3, 0x900, 0x901])
        cell = next(k for k, r in recs.items() if r[0] == b"CELL")
        bases = {0x8F0: 0x7145, 0x8F1: 0x267F4C, 0x8F2: 0x10, 0x8F3: 0x34}   # pad, trigger, MapMarker, XMarkerHeading
        parts = dict(zip((0x8F0, 0x8F1, 0x8F2, 0x8F3), ("pad", "trigger", "marker", "heading")))
        for k, part in parts.items():
            sig, payload, owner, flags = recs[k]
            self.assertEqual(owner, cell, part)                                     # all four persistent in the copy
            self.assertEqual(flags & 0xC00, 0x400, part)
            self.assertEqual(tlw.field(payload, b"NAME"), struct.pack("<I", bases[k]), part)   # Starfield.esm's bases
            got = struct.unpack_from("<6f", tlw.field(payload, b"DATA"))
            for g, w in zip(got, spot[part]["pos"] + spot[part]["rot"]):
                self.assertAlmostEqual(g, w, places=3, msg=part)
        links = lambda k: [struct.unpack("<II", d) for s, d in tlw.subrecords(recs[k][1]) if s == b"XLKR"]  # noqa: E731
        self.assertEqual(links(0x8F0), [(0x267F4D, 0x020008F1), (0x3A866F, 0x020008F2)])   # trigger, marker
        self.assertEqual(links(0x8F2), [(0, 0x020008F3)])                                   # the heading, no keyword
        self.assertEqual(links(0x8F1) + links(0x8F3), [])
        self.assertIsNotNone(tlw.field(recs[0x8F1][1], b"XPRM"))                            # the trigger's box
        marker = recs[0x8F2][1]
        self.assertEqual(struct.unpack("<I", tlw.field(marker, b"FNAM"))[0], 0x33)           # LandingOverlay01's
        self.assertEqual(tlw.field(marker, b"FULL"), b"Landing Area\0")
        # the Location: the core's rows, --extra's, then the marker's MapMarkerRefType row and the pad's two
        loc = next(k for k, r in recs.items() if r[0] == b"LCTN")
        rows = map_markers.parse_lcsr(tlw.field(recs[loc][1], b"LCSR"))
        self.assertEqual([r["refr"] for r in rows[3:]], [0x02000900, 0x02000901, 0x020008F2, 0x020008F0, 0x020008F0])
        self.assertEqual([r["lcrt"] for r in rows[5:]], [map_markers.MAPMARKER_REF_TYPE, map_markers.SHIP_LANDING_MARKER_REF_TYPE,
                                                         map_markers.SHIP_LANDING_MARKER_REF_TYPE_LARGE])
        self.assertNotEqual(rows[5]["pad"], rows[6]["pad"])          # the marker sits in the cell south of the pad's
        # the quest moves them with the markers, at their written spots (no lift: landing_spot lifted the heading)
        got = self.object_list(tlw.field(recs[0x800][1], b"VMAD"))
        self.assertEqual(got[3:], [0x02000900, 0x02000901, 0x020008F0, 0x020008F1, 0x020008F2, 0x020008F3])
        zs = [self.markers_z(i) for i in core_ids] + [m["pos"][2] + Z_LIFT for m in self.EXTRA] + \
             [spot[p]["pos"][2] for p in ("pad", "trigger", "marker", "heading")]
        self.assertIn(f"LocalZ: {', '.join(self.num(v) for v in zs)}", check.stdout)
        nxt = struct.unpack_from("<I", plugin.read_bytes(), 24 + 4 + 2 + 8)[0]          # HEDR next id: after --extra's
        self.assertEqual(nxt, 0x902)

    def markers_z(self, form):
        return next(m["pos"][2] for m in self.markers if int(self.ids[m["tag"]], 16) == form) + Z_LIFT

    def test_check_wants_the_same_landing_spot(self):
        landing = self.landing_file("landing-same", self.landing())
        out = self.root / "plugin-landing-same"
        built = self.tool_run("build", "--core", self.core, "--out", out, "--landing", landing)
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        plugin = out / "FO4SFMapMarkers.esm"
        self.assertEqual(struct.unpack_from("<I", plugin.read_bytes(), 24 + 4 + 2 + 8)[0], 0x8F4)   # no --extra
        self.assertEqual(self.tool_run("check", plugin, self.core, "--landing", landing).returncode, 0)
        bare = self.tool_run("check", plugin, self.core)
        self.assertEqual(bare.returncode, 1, bare.stdout)
        self.assertIn("is a REFR of this plugin that --extra and --landing do not list", bare.stdout)
        self.assertIn("1 Location record(s) without --extra or --landing", bare.stdout)
        renamed = self.tool_run("check", plugin, self.core, "--landing", self.landing_file("landing-renamed", self.landing(name="Pad")))
        self.assertEqual(renamed.returncode, 1, renamed.stdout)
        self.assertIn("SyntheticWorldLandingMapMarkerRedRocketNorth is not the record --landing builds", renamed.stdout)
        moved = self.landing()
        moved["pad"]["cell"] = [0, 0]                                           # the pad's rows name another grid
        grid = self.tool_run("check", plugin, self.core, "--landing", self.landing_file("landing-grid", moved))
        self.assertEqual(grid.returncode, 1, grid.stdout)
        self.assertIn("and the landing spot's three", grid.stdout)
        plain = self.root / "plugin-landing-none"
        self.assertEqual(self.tool_run("build", "--core", self.core, "--out", plain).returncode, 0)
        missing = self.tool_run("check", plain / "FO4SFMapMarkers.esm", self.core, "--landing", landing)
        self.assertEqual(missing.returncode, 1, missing.stdout)
        self.assertIn("SyntheticWorldLandingPadRedRocketNorth (--landing) is missing", missing.stdout)

    def test_the_landing_spot_stays_in_one_quest(self):
        # the script finds the landing marker two places after the pad (FO4SF_MapMarkers.psc ShowLanding): 3 core
        # markers, 195 of the plugin's own and the landing's 4 would leave 2 pieces alone in a third quest, so that
        # quest takes the other two from the one before it (100, 98, 4), and the check wants the same split
        many = [{"tag": f"M{k:06X}", "name": f"Marker {k}", "pos": [10.0 + k * 0.5, 20.0 + k * 0.25, 1.0], "cell": [0, 0]}
                for k in range(195)]
        extra, landing = self.extra_file("extra-split", many), self.landing_file("landing-split", self.landing())
        out = self.root / "plugin-landing-split"
        built = self.tool_run("build", "--core", self.core, "--out", out, "--extra", extra, "--landing", landing)
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        self.assertIn("3 quest(s) FO4SF_MapMarkersQuest 000800", built.stdout)
        check = self.tool_run("check", out / "FO4SFMapMarkers.esm", self.core, "--extra", extra, "--landing", landing)
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        recs = self.records_by_form(out / "FO4SFMapMarkers.esm")
        vmads = [tlw.field(recs[0x02000000 | q][1], b"VMAD") for q in (0x800, 0x801, 0x802)]
        lists = [self.object_list(v) for v in vmads]
        self.assertEqual([len(x) for x in lists], [100, 98, 4])
        self.assertEqual(lists[2], [0x020008F0, 0x020008F1, 0x020008F2, 0x020008F3])     # pad, trigger, marker, heading
        flat = [f for x in lists for f in x]
        self.assertEqual([f & 0xFFFFFF for f in flat[3:-4]], list(range(0x900, 0x900 + 195)))   # the order kept
        name = b"\x08\x00MaxMoves"
        at = vmads[1].index(name) + len(name)
        self.assertEqual(struct.unpack_from("<BBi", vmads[1], at), (3, 1, 196))      # its own count's budget
        self.assertNotIn(b"MaxMoves", vmads[2])                                       # 4: the script's 40

    def test_build_refuses_a_bad_landing_file(self):
        spot = self.landing()
        for name, bad, want in [
                ("landing-badtag", dict(spot, tag="Red Rocket"), 'tag "Red Rocket": want letters, digits or _'),
                ("landing-noname", dict(spot, name=""), "RedRocketNorth: no name"),
                ("landing-nopart", {k: v for k, v in spot.items() if k != "heading"}, "RedRocketNorth: no heading"),
                ("landing-short", dict(spot, pad=dict(spot["pad"], rot=[0.0, 0.0])), "pad: rot needs 3 finite numbers")]:
            proc = self.tool_run("build", "--core", self.core, "--out", self.root / f"plugin-{name}", "--landing",
                                 self.landing_file(name, bad))
            self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
            self.assertIn(want, proc.stderr)

    def test_check_rejects_an_alias_encoded_marker(self):
        out = self.root / "plugin-alias"
        self.assertEqual(self.tool_run("build", "--core", self.core, "--out", out).returncode, 0)
        plugin = out / "FO4SFMapMarkers.esm"
        data = bytearray(plugin.read_bytes())
        name = b"\x07\x00Markers"
        entry = data.index(name) + len(name) + 6                # type, status, u32 count
        self.assertEqual(struct.unpack_from("<Hh", data, entry), (0, -1))
        struct.pack_into("<h", data, entry + 2, 0)              # alias -1 -> 0, the form id untouched
        plugin.write_bytes(bytes(data))
        check = self.tool_run("check", plugin, self.core)
        self.assertEqual(check.returncode, 1, check.stdout)
        self.assertIn("FAIL  Markers[0] is not a direct reference (alias 0, unused 0)", check.stdout)

    def test_check_rejects_a_plugin_built_from_another_core(self):
        params = copy.deepcopy(self.params)
        params["overlays"][0]["map_markers"] = self.markers[:2]
        saved, type(self).params = type(self).params, params
        try:
            proc, other = self.run_writer(self.objects, "core-two")
        finally:
            type(self).params = saved
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        out = self.root / "plugin-two"
        self.assertEqual(self.tool_run("build", "--core", other / "Synthetic.esm", "--out", out).returncode, 0)
        check = self.tool_run("check", out / "FO4SFMapMarkers.esm", self.core)
        self.assertEqual(check.returncode, 1, check.stdout)
        self.assertIn("FAIL  Markers", check.stdout)

    def test_build_refuses_a_core_without_markers(self):
        # the plain synthetic master has no LC172 template, so the writer writes no MapMarker REFR
        fixture = ROOT / "dotnet/TerrainIdentityFixture/bin/Release/net9.0/TerrainIdentityFixture.dll"
        plain = self.root / "master-plain/Starfield.esm"
        plain.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([self.dotnet, str(fixture), str(plain)], capture_output=True, check=True)
        saved, type(self).master = type(self).master, plain
        try:
            proc, stage = self.run_writer(self.objects, "core-plain")
        finally:
            type(self).master = saved
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        proc = self.tool_run("build", "--core", stage / "Synthetic.esm", "--out", self.root / "none")
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("no MapMarker REFR", proc.stderr)

    @staticmethod
    def records_by_form(path):
        """{full FormID: (sig, payload)} of a plugin (tri.records keys by the low 24 bits, so an override and a record of
        the plugin's own with the same low bits collide there)."""
        data, out = path.read_bytes(), {}

        def walk(pos, end):
            while pos < end:
                sig, size = data[pos:pos + 4], struct.unpack_from("<I", data, pos + 4)[0]
                if sig == b"GRUP":
                    walk(pos + 24, pos + size)
                    pos += size
                    continue
                flags, form = struct.unpack_from("<II", data, pos + 8)
                payload = data[pos + 24:pos + 24 + size]
                out[form] = (sig, zlib.decompress(payload[4:]) if flags & 0x40000 else payload)
                pos += 24 + size
        walk(0, len(data))
        return out

    @staticmethod
    def num(v):
        return f"{v:.3f}".rstrip("0").rstrip(".")

    @staticmethod
    def object_list(vmad):
        """Form ids of the Markers array property (type 11) in a quest VMAD."""
        name = b"\x07\x00Markers"                     # the property's u16-length-prefixed name
        pos = vmad.index(name) + len(name)
        kind, _status, count = struct.unpack_from("<BBI", vmad, pos)
        assert kind == 11, kind
        pos += 6
        out = []
        for _ in range(count):
            _zero, _alias, form = struct.unpack_from("<HhI", vmad, pos)
            out.append(form)
            pos += 8
        return out


class ScriptContractTests(unittest.TestCase):
    text = SCRIPT.read_text(encoding="utf-8")

    def test_properties_the_writer_fills(self):
        for decl in ("ObjectReference[] Property Markers", "float[] Property LocalX", "float[] Property LocalY",
                     "float[] Property LocalZ"):
            self.assertIn(decl, self.text)

    def test_offset_and_extent_match_the_repo(self):
        sys.path.insert(0, str(ROOT / "scripts" / "terrain"))
        import vmad_patch
        dx, dy, _ = vmad_patch.MERGE_MEASURED
        self.assertIn(f"MergeOffsetX = {dx}", self.text)
        self.assertIn(f"MergeOffsetY = {dy}", self.text)
        half = 64 // 2 * 100.0                             # core64: local -3200..3200 m
        for name, v in (("MinX", -half + dx), ("MaxX", half + dx), ("MinY", -half + dy), ("MaxY", half + dy)):
            self.assertIn(f"{name} = {v}", self.text)

    def test_a_marker_at_the_old_height_is_moved_again(self):
        # a save from before a lifted build holds the markers at the old z (Codex on #483): the reposition test
        # reads the height too, so the first pass moves them once more. The tolerance is half the lift step the
        # build enforces, so every supported change between builds (0.1 m up) is seen, while a landed move is not
        place = self.text[self.text.index("Function Place"):self.text.index("Function Trace")]
        self.assertIn("ez * ez > ZTolerance * ZTolerance", place)
        tol = float(re.search(r"float Property ZTolerance = ([0-9.]+) Auto Const", self.text).group(1))
        self.assertEqual(tol, Z_LIFT_STEP / 2)
        self.assertGreater(tol, 0.01)                                     # a landed move is within 0.01 m (22 Oct log)
        placed = lambda ez: not (ez * ez > tol * tol)                     # the script's test, in Python
        self.assertTrue(placed(0.01) and placed(-0.01))                   # landed: left alone
        self.assertFalse(placed(Z_LIFT_STEP) or placed(-Z_LIFT_STEP))     # the smallest change between builds: moved
        self.assertFalse(placed(Z_LIFT))                                  # a save from before the default lift: moved

    def test_the_move_budget_starts_over_for_a_new_build(self):
        # moves is saved state, so a save that spent its budget on the first placement and one lift would ignore
        # the next lift (Codex on #483): the budget is keyed to the build (marker count, LocalZ[0]) and starts over
        self.assertIn("int budgetN = -1", self.text)
        self.assertIn("float budgetZ = 0.0", self.text)
        reset = self.text[self.text.index("Function ResetBudget"):self.text.index("Function Place")]
        self.assertIn("budgetN != Markers.Length || budgetZ != LocalZ[0]", reset)
        for line in ("budgetN = Markers.Length", "budgetZ = LocalZ[0]", "moves = 0"):
            self.assertIn(line, reset)
        place = self.text[self.text.index("Function Place"):self.text.index("Function Trace")]
        self.assertLess(place.index("ResetBudget()"), place.index("IsInInterior"))   # before any early return
        # the script's loop, modelled: n markers, the build's MaxMoves (2n above 40, as dotnet/MapMarkers sets it),
        # a pass per Interval; initial placement, then lift A, then lift B, on one save
        tol = float(re.search(r"float Property ZTolerance = ([0-9.]+) Auto Const", self.text).group(1))
        n = 100
        max_moves = max(2 * n, 40)
        saved_z = [None] * n                                              # None: not yet in the player's world
        state = {"moves": 0, "budget_n": -1, "budget_z": 0.0}

        def passes(local_z, count=3):
            moved = 0
            for _ in range(count):                                        # the script runs until nothing is off
                if state["budget_n"] != n or state["budget_z"] != local_z[0]:
                    state["budget_n"], state["budget_z"], state["moves"] = n, local_z[0], 0
                for i in range(n):
                    if state["moves"] >= max_moves:
                        break
                    off = saved_z[i] is None or (saved_z[i] - local_z[i]) ** 2 > tol * tol
                    if off:
                        saved_z[i] = local_z[i] + 0.004                   # a move lands within 0.01 m
                        state["moves"] += 1
                        moved += 1
            return moved

        base = [100.0 + i for i in range(n)]
        self.assertEqual(passes(base), n)                                 # placed once each
        self.assertEqual(passes([z + 0.5 for z in base]), n)              # lift A: every marker moved once more
        self.assertEqual(passes([z + 1.0 for z in base]), n)              # lift B: the budget started over
        self.assertEqual(passes([z + 1.0 for z in base]), 0)              # the same build again: nothing moves

    def test_moves_only_outdoors_capped_and_logged(self):
        place = self.text[self.text.index("Function Place"):self.text.index("Function Trace")]
        self.assertLess(place.index("IsInInterior"), place.index("MoveTo"))
        # the budget is part of the loop condition, so it holds before every Enable / MoveTo (Codex 4311385104)
        loop = place.index("while i < Markers.Length && moves < MaxMoves")
        self.assertLess(loop, place.index("m.Enable"))
        self.assertEqual(place.count("moves += 1"), 1)
        self.assertEqual(place.count("MoveTo("), 1)
        # no match-rotation: a moved pad keeps its record's facing, not the player's
        self.assertRegex(place, r"m\.MoveTo\(player, x - px, y - py, z - pz, False, False\)")
        self.assertIn('Trace("moved "', place)
        self.assertNotIn("Math.", self.text)               # only the base scripts the bridge already imports

    def test_a_pass_reads_the_player_before_every_move(self):
        # a load door can take the player away while a pass runs: a pass that read them once put about 300 markers
        # into Vault 95 at the target plus the trip and spent every budget (PC, 2026-10-24 10:24, fo4sf_map.0.log).
        # Inside the move branch, just before MoveTo, the player is read again and the pass stops once they are
        # indoors or in another world; a marker already in place costs no player reads (fresh review on #570)
        place = self.text[self.text.index("Function Place"):self.text.index("Function Trace")]
        loop = place.index("while i < Markers.Length && moves < MaxMoves")
        self.assertLess(place.index("WorldSpace w = player.GetWorldSpace()"), loop)
        branch = place.index("if before > SameWorld", loop)
        stop = place.index("if player.IsInInterior() || player.GetWorldSpace() != w", loop)
        read = place.index("px = player.GetPositionX()", loop)
        self.assertLess(branch, stop)
        self.assertLess(stop, read)
        self.assertLess(read, place.index("m.Enable", loop))
        self.assertLess(place.index("m.Enable"), place.index("m.MoveTo("))
        self.assertIn('Trace("pass stopped at "', place)
        self.assertEqual(place.count("player.GetPositionX()"), 2)     # once for the extent, once before the move
        self.assertEqual(place[loop:branch].count("player.Get"), 1)   # only the distance before a move is needed

    def test_a_reference_the_game_will_not_move_is_left_alone_for_the_session(self):
        # the landing pad: "cannot be moved" on every pass, and its quest spent its whole budget retrying it
        # (Papyrus.0.log, 2026-10-24); a refused reference is skipped until the next game session
        place = self.text[self.text.index("Function Place"):self.text.index("Function Trace")]
        self.assertIn("if m != None && !refused[i]", place)
        self.assertLess(place.index("!refused[i]"), place.index("m.Enable"))
        self.assertLess(place.index("m.MoveTo("), place.index("refused[i] = True"))
        self.assertIn("if d > SameWorld && sx * sx + sy * sy < 0.0001", place)    # still in its own world, unmoved
        self.assertLess(place.index("NewSession()"), place.index("IsInInterior"))
        session = self.text[self.text.index("Function NewSession"):self.text.index("Function ShowLanding")]
        size = int(re.search(r"refused = new bool\[(\d+)\]", session).group(1))
        per_quest = int(re.search(r"const int PerQuest = (\d+)", PROGRAM.read_text(encoding="utf-8")).group(1))
        self.assertGreaterEqual(size, per_quest)                          # every index a quest can hold
        self.assertLessEqual(size, 128)                                   # a script-made array's limit
        # every game session: the budget starts over, so markers a session left wrong are put right in the next
        for line in ("moves = 0", "landingShown = False"):
            self.assertIn(line, session)
        # a save from before these variables brings them in unset: 0.0 counts as a new session too, so the list is made
        self.assertIn("bool fresh = placeRealTime <= 0.0 || rt < placeRealTime", session)
        self.assertIn("return fresh", session)
        self.assertIn("float placeRealTime = -1.0", self.text)
        # a new build can list other references at the same places, so the list starts over with its budget
        reset = self.text[self.text.index("Function ResetBudget"):self.text.index("Function NewSession")]
        self.assertIn(f"refused = new bool[{size}]", reset)

    def test_every_save_load_is_a_new_session(self):
        # Codex on #570: the clock alone misses a launch whose first pass reads a later real time than the save's last
        # one (saved 20 s, first pass at 90 s), keeping that session's spent budget. The player's load event clears
        # both clocks. Replayed here from the script's own predicates and the values the event writes
        on_init = self.text[self.text.index("Event OnInit"):self.text.index("EndEvent")]
        self.assertIn('RegisterForRemoteEvent(Game.GetPlayer(), "OnPlayerLoadGame")', on_init)
        load = self.text[self.text.index("Event Actor.OnPlayerLoadGame(Actor akSender)"):]
        load = load[:load.index("EndEvent")]
        written = dict(re.findall(r"^\s+(placeRealTime|lastRealTime) = ([0-9.]+)", load, re.M))
        self.assertEqual(set(written), {"placeRealTime", "lastRealTime"})
        session = self.text[self.text.index("bool Function NewSession"):self.text.index("Function SessionLine")]
        self.assertIn('RegisterForRemoteEvent(Game.GetPlayer(), "OnPlayerLoadGame")', session)   # older saves
        place_new = re.search(r"bool fresh = (.+)$", session, re.M).group(1)
        border = self.text[self.text.index("Function Border"):self.text.index("Function Trace")]
        border_new = re.search(r"if (rt < lastRealTime)\s", border).group(1)

        def py(expr):
            return expr.replace("||", " or ").replace("&&", " and ")

        def replay(name, expr, initial, events):
            """The variable as saved, then each event: ("load",) or ("tick", rt); the ticks that start a session."""
            var, out = initial, []
            for e in events:
                if e[0] == "load":
                    var = float(written[name])
                else:
                    out.append(eval(py(expr), {}, {name: var, "rt": e[1]}))   # noqa: S307 - the script's own text
                    var = e[1]
            return out

        for name, expr, initial in (("placeRealTime", place_new, -1.0), ("lastRealTime", border_new, -1.0)):
            same = [("tick", 2.0), ("tick", 4.0), ("tick", 6.0)]
            self.assertEqual(replay(name, expr, initial, same)[1:], [False, False], name)             # one session
            later = [("tick", 18.0), ("tick", 20.0), ("load",), ("tick", 90.0), ("tick", 92.0)]
            self.assertEqual(replay(name, expr, initial, later)[2:], [True, False], name)            # a later clock
            earlier = [("tick", 600.0), ("load",), ("tick", 40.0), ("tick", 42.0)]
            self.assertEqual(replay(name, expr, initial, earlier)[1:], [True, False], name)          # an earlier one
            reload = [("tick", 300.0), ("load",), ("tick", 310.0)]
            self.assertEqual(replay(name, expr, initial, reload)[1:], [True], name)                  # same launch
            unset = [("tick", 90.0)]                                   # a save from before NewSession: 0.0
            if name == "placeRealTime":
                self.assertEqual(replay(name, expr, 0.0, unset), [True])

    def test_each_quest_says_once_per_session_what_the_border_guards_read(self):
        # a coc session from the main menu at Red Rocket wrote no border line in 240 s while "moved 9" lines kept
        # coming (Review, 2026-10-28): every line names its quest, and each quest's first pass of a session logs
        # what Border's guards read, so the log tells whether 0x800 ticked or its Markers[0] was None
        place = self.text[self.text.index("Function Place"):self.text.index("Function Trace")]
        self.assertLess(place.index("if NewSession()"), place.index("SessionLine(player)"))
        self.assertLess(place.index("SessionLine(player)"), place.index("Border(player)"))
        line = self.text[self.text.index("Function SessionLine"):self.text.index("Function ShowLanding")]
        for field in ('"session id=" + GetFormID()', '" signal=" + SignalQuest()', '" enabled=" + BorderSignal',
                      '" markers=" + Markers.Length', '" first=" + first', '" interior=" + player.IsInInterior()'):
            self.assertIn(field, line)
        self.assertIn("if Markers.Length > 0", line)                     # no index into an empty list
        self.assertNotIn("border=", line)                                # FO4SFBorder takes the newest border= token
        trace = self.text[self.text.index("Function Trace"):]
        self.assertIn('" q=" + QuestLow() + " " + msg', trace)

    def test_the_landing_marker_is_found_after_its_pad_and_shown_once_per_session(self):
        # Mars's map had no Commonwealth location (owner, 2026-10-28): the landing marker is marked discovered and
        # shown on the star map. dotnet/MapMarkers lists the landing spot pad, trigger, marker, heading, in one quest
        program = PROGRAM.read_text(encoding="utf-8")
        pad = int(re.search(r"LandingPad = 0x([0-9A-F]+)", program).group(1), 16)
        self.assertEqual(int(re.search(r"int Property LandingPadID = 0x([0-9A-Fa-f]+) Auto Const", self.text).group(1), 16), pad)
        self.assertIn("new List<PlacedObject> { pad, trigger, marker, heading }", program)
        self.assertIn("static List<T[]> QuestChunks<T>(", program)
        self.assertEqual(program.count("QuestChunks("), 2)                # build and check split the same way
        self.assertIn("var chunks = all.Chunk(PerQuest).ToList();", program)    # the landing is the list's last four
        show = self.text[self.text.index("Function ShowLanding"):self.text.index("Event OnTimer")]
        self.assertIn("int i = Markers.Length - 4", show)                      # the pad, fourth from the end
        self.assertIn("ObjectReference marker = Markers[i + 2]", show)
        self.assertIn("pad.GetBaseObject() == Game.GetForm(LandingPadID)", show)
        self.assertIn("marker.SetMarkerDiscovered()", show)
        self.assertIn("marker.SetMarkerVisibleOnStarMap(True)", show)
        self.assertNotIn("while", show)                                       # one read per quest
        self.assertLess(show.index("landingShown = True"), show.index("Game.GetForm"))   # once, found or not
        place = self.text[self.text.index("Function Place"):self.text.index("Function Trace")]
        self.assertLess(place.index("Border(player)"), place.index("ShowLanding()"))   # the border signal first
        self.assertLess(place.index("ShowLanding()"), place.index("IsInInterior"))     # wherever the player is



class StageTests(unittest.TestCase):
    def test_stage_builds_compiles_and_checks_against_the_core(self):
        sys.path.insert(0, str(ROOT / "scripts" / "mapmarkers"))
        import make_map_markers as mm
        calls = []

        def fake_run(cmd, cwd=None):
            calls.append((cmd, cwd))
            if cmd[0].endswith("PapyrusCompiler.exe"):
                open(os.path.join(cmd[-1][3:], "FO4SF_MapMarkers.pex"), "wb").close()
                return "Compilation succeeded."
            return "ok\n"

        with tempfile.TemporaryDirectory() as d, mock.patch.object(mm.make_bridge, "run", fake_run), \
                mock.patch.object(mm.make_bridge, "extract_sources", lambda z, w: w):
            out, core = os.path.join(d, "stage"), os.path.join(d, "FO4TerrainCore.esm")
            with open(core, "wb") as f:
                f.write(b"core bytes")
            mm.main(["stage", "--core", core, "--out", out, "--compiler", "PapyrusCompiler.exe"])
            with open(os.path.join(out, "core.json"), encoding="utf-8") as f:   # the installer's pin on this core
                self.assertEqual(json.load(f), {"masters": {"FO4TerrainCore.esm": hashlib.sha256(b"core bytes").hexdigest()}})
            self.assertTrue(os.path.exists(os.path.join(out, "README.txt")))
            self.assertTrue(os.path.exists(os.path.join(out, "Data", "Scripts", "FO4SF_MapMarkers.pex")))
            with self.assertRaises(SystemExit):                # never into a used folder
                mm.main(["stage", "--core", core, "--out", out])
            with self.assertRaises(SystemExit):                # one plugin name, the one the installer knows
                mm.main(["stage", "--core", core, "--out", os.path.join(d, "s2"), "--plugin", "Custom.esm"])
            city = os.path.join(d, "city")                      # a world variant goes to build and check alike
            mm.main(["stage", "--core", core, "--out", city, "--compiler", "PapyrusCompiler.exe", "--world", "city"])
            with open(os.path.join(city, "README.txt"), encoding="utf-8") as f:
                self.assertIn("--world city (dotnet/BorderProbe's: SmallWorld cleared, HNAM 5)", f.read())
            with self.assertRaises(SystemExit):                # the probe's variants only
                mm.main(["stage", "--core", core, "--out", os.path.join(d, "s3"), "--world", "hnam5"])
        build, comp, check, build2, comp2, check2 = calls
        self.assertEqual(build[0][-7:], ["build", "--core", core, "--out", out, "--plugin", "FO4SFMapMarkers.esm"])
        self.assertEqual(comp[0][1], "FO4SF_MapMarkers.psc")
        self.assertEqual(check[0][-3:], ["check", os.path.join(out, "FO4SFMapMarkers.esm"), core])
        self.assertEqual(build2[0][-9:], ["build", "--core", core, "--out", city, "--plugin", "FO4SFMapMarkers.esm", "--world", "city"])
        self.assertEqual(check2[0][-5:], ["check", os.path.join(city, "FO4SFMapMarkers.esm"), core, "--world", "city"])

    def test_stage_adds_fo4_markers_from_the_core_stage(self):
        # --fo4-map-markers with --core-stage: the core's own stage folder gives the bounds, the fixed markers and the
        # BTD (its copy of the core must be --core), the export the markers; both dotnet runs get --extra
        sys.path.insert(0, str(ROOT / "scripts" / "mapmarkers"))
        sys.path.insert(0, str(ROOT / "scripts" / "terrain"))
        sys.path.insert(0, str(ROOT / "src"))
        import make_map_markers as mm
        import make_core64c
        calls, btds = [], []

        def fake_run(cmd, cwd=None):
            calls.append(cmd)
            if cmd[0].endswith("PapyrusCompiler.exe"):
                open(os.path.join(cmd[-1][3:], "FO4SF_MapMarkers.pex"), "wb").close()
                return "Compilation succeeded."
            return "ok\n"

        class FlatTerrain:
            def __init__(self, path):
                btds.append(path)

            def bilinear(self, xs, ys):
                return [3.0 for _ in xs]

        fixed = [{"tag": "RedRocket", "name": "Red Rocket Truck Stop", "src": "0211C0:Fallout4.esm",
                  "pos": [-989.2571, 1146.5143, 107.1429], "cell": [-10, 11]}]
        export = {"plugin": "Fallout4.esm", "world": "Commonwealth", "markers": [
            {"fid": "0001F2A9", "name": "Abernathy Farm", "pos": [-81000.0, 86000.0, 0]},
            {"fid": "0001F2AA", "name": None, "pos": [0, 0, 0]},
            {"fid": "0001F2AB", "name": "Far Away", "pos": [-300000.0, 0.0, 0]},
            {"fid": "00024FBE", "name": "Red Rocket Truck Stop", "pos": [-69230.0, 80240.0, 0]}]}   # on the fixed one

        with tempfile.TemporaryDirectory() as d, mock.patch.object(mm.make_bridge, "run", fake_run), \
                mock.patch.object(mm.make_bridge, "extract_sources", lambda z, w: w), \
                mock.patch.object(make_core64c, "Terrain", FlatTerrain):
            cs, core = os.path.join(d, "core_stage"), os.path.join(d, "FO4TerrainCore.esm")
            os.makedirs(cs)
            for path in (core, os.path.join(cs, "FO4TerrainCore.esm")):
                with open(path, "wb") as f:
                    f.write(b"core bytes")

            def params(markers):
                with open(os.path.join(cs, "overlays_params.json"), "w", encoding="utf-8-sig") as f:   # the PC's BOM
                    json.dump({"overlays": [{"btd_file": "Data/Terrain/W.btd", "bounds_min_m": -3200.0,
                                             "bounds_max_m": 3200.0, "map_markers": markers}]}, f)
            params(fixed)
            exp = os.path.join(d, "cw_markers.json")
            with open(exp, "w", encoding="utf-8") as f:
                json.dump(export, f)
            out = os.path.join(d, "stage")
            mm.main(["stage", "--core", core, "--out", out, "--compiler", "PapyrusCompiler.exe",
                     "--fo4-map-markers", exp, "--core-stage", cs])
            self.assertEqual(btds, [os.path.join(cs, "Data", "Terrain", "W.btd")])
            with open(os.path.join(out, "extra_markers.json"), encoding="utf-8") as f:
                doc = json.load(f)
            self.assertEqual([(m["tag"], m["name"], m["cell"]) for m in doc["markers"]],
                             [("M01F2A9", "Abernathy Farm", [-12, 12])])
            pos = doc["markers"][0]["pos"]
            self.assertAlmostEqual(pos[0], -81000.0 / 70, places=3)
            self.assertAlmostEqual(pos[1], 86000.0 / 70, places=3)
            self.assertEqual(pos[2], 3.0)                                     # the BTD ground, before the lift
            with open(os.path.join(out, "map_markers_left_out.json"), encoding="utf-8") as f:
                reasons = sorted(e["reason"] for e in json.load(f)["left_out"])
            self.assertEqual(len(reasons), 3)
            self.assertIn("no name", reasons)
            self.assertTrue(any(r.startswith("outside the overlay") for r in reasons), reasons)
            self.assertIn("Red Rocket Truck Stop: within 100 m of the fixed marker RedRocket", reasons)
            path = os.path.join(out, "extra_markers.json")
            build, _comp, check = calls
            self.assertEqual(build[-2:], ["--extra", path])
            self.assertEqual(check[-5:], ["check", os.path.join(out, "FO4SFMapMarkers.esm"), core, "--extra", path])
            with open(os.path.join(out, "README.txt"), encoding="utf-8") as f:
                self.assertIn("Plus 1 markers of its own (extra_markers.json", f.read())
            # refusals: half the pair; a core stage holding another core build; a core already built with the markers
            with self.assertRaises(SystemExit) as e:
                mm.main(["stage", "--core", core, "--out", os.path.join(d, "s1"), "--fo4-map-markers", exp])
            self.assertIn("--core-stage goes with --fo4-map-markers or --landing", str(e.exception))
            with open(os.path.join(cs, "FO4TerrainCore.esm"), "wb") as f:
                f.write(b"another build")
            with self.assertRaises(SystemExit) as e:
                mm.main(["stage", "--core", core, "--out", os.path.join(d, "s2"), "--compiler", "PapyrusCompiler.exe",
                         "--fo4-map-markers", exp, "--core-stage", cs])
            self.assertIn("is not --core (another build)", str(e.exception))
            with open(os.path.join(cs, "FO4TerrainCore.esm"), "wb") as f:
                f.write(b"core bytes")
            params(fixed + [dict(doc["markers"][0])])
            with self.assertRaises(SystemExit) as e:
                mm.main(["stage", "--core", core, "--out", os.path.join(d, "s3"), "--compiler", "PapyrusCompiler.exe",
                         "--fo4-map-markers", exp, "--core-stage", cs])
            self.assertIn("it was built with --fo4-map-markers", str(e.exception))
        self.assertEqual(len(calls), 3)                                       # no dotnet run after a refusal

    def test_stage_adds_a_landing_spot_at_a_getpos_spot(self):
        # --landing x y (the merged frame, as getpos and the owner's snapshots give it) with --core-stage: the pad at
        # x, y less the merge offset, heights from the core stage's BTD; both dotnet runs get --landing
        sys.path.insert(0, str(ROOT / "scripts" / "mapmarkers"))
        sys.path.insert(0, str(ROOT / "scripts" / "terrain"))
        sys.path.insert(0, str(ROOT / "src"))
        import make_map_markers as mm
        import make_core64c
        calls = []

        def fake_run(cmd, cwd=None):
            calls.append(cmd)
            if cmd[0].endswith("PapyrusCompiler.exe"):
                open(os.path.join(cmd[-1][3:], "FO4SF_MapMarkers.pex"), "wb").close()
                return "Compilation succeeded."
            return "ok\n"

        class FlatTerrain:
            def __init__(self, path):
                pass

            def bilinear(self, xs, ys):
                return [3.0 for _ in xs]

        with tempfile.TemporaryDirectory() as d, mock.patch.object(mm.make_bridge, "run", fake_run), \
                mock.patch.object(mm.make_bridge, "extract_sources", lambda z, w: w), \
                mock.patch.object(make_core64c, "Terrain", FlatTerrain):
            cs, core = os.path.join(d, "core_stage"), os.path.join(d, "FO4TerrainCore.esm")
            os.makedirs(cs)
            for path in (core, os.path.join(cs, "FO4TerrainCore.esm")):
                with open(path, "wb") as f:
                    f.write(b"core bytes")
            with open(os.path.join(cs, "overlays_params.json"), "w", encoding="utf-8-sig") as f:
                json.dump({"overlays": [{"btd_file": "Data/Terrain/W.btd", "bounds_min_m": -3200.0,
                                         "bounds_max_m": 3200.0, "map_markers": []}]}, f)
            out = os.path.join(d, "stage")
            mm.main(["stage", "--core", core, "--out", out, "--compiler", "PapyrusCompiler.exe",
                     "--landing", "-1959", "-493", "--core-stage", cs])
            path = os.path.join(out, "landing.json")
            with open(path, encoding="utf-8") as f:
                doc = json.load(f)
            self.assertEqual((doc["getpos"], doc["merge_offset"]), ([-1959.0, -493.0], [-1200.0, -2700.0]))
            spot = doc["landing"]
            self.assertEqual(spot["pad"]["pos"], [-759.0, 2207.0, 3.0])          # local = getpos less the offset
            self.assertEqual(spot["heading"]["pos"][2], 5.5)                     # its ground plus the tool's 2.5 m
            self.assertEqual(spot["name"], "Commonwealth Landing Area")
            build, _comp, check = calls
            self.assertEqual(build[-2:], ["--landing", path])
            self.assertEqual(check[-5:], ["check", os.path.join(out, "FO4SFMapMarkers.esm"), core, "--landing", path])
            with open(os.path.join(out, "README.txt"), encoding="utf-8") as f:
                self.assertIn('Plus a ship landing spot "Commonwealth Landing Area" (landing.json): a pad at getpos -1959.0 -493.0', f.read())
            mm.main(["stage", "--core", core, "--out", os.path.join(d, "lift"), "--compiler", "PapyrusCompiler.exe",
                     "--landing", "-1959", "-493", "--core-stage", cs, "--z-lift", "1.0"])
            with open(os.path.join(d, "lift", "landing.json"), encoding="utf-8") as f:
                self.assertEqual(json.load(f)["landing"]["heading"]["pos"][2], 4.0)   # --z-lift lifts the heading too
            # refusals: no core stage; a pad less than a cell inside the overlay
            with self.assertRaises(SystemExit) as e:
                mm.main(["stage", "--core", core, "--out", os.path.join(d, "s1"), "--landing", "-1959", "-493"])
            self.assertIn("--core-stage goes with --fo4-map-markers or --landing", str(e.exception))
            with self.assertRaises(SystemExit) as e:
                mm.main(["stage", "--core", core, "--out", os.path.join(d, "s2"), "--compiler", "PapyrusCompiler.exe",
                         "--landing", "1950", "-493", "--core-stage", cs])
            self.assertIn("less than 100 m inside the overlay", str(e.exception))
        self.assertEqual(len(calls), 6)                                       # two stages, none after a refusal


if __name__ == "__main__":
    unittest.main()
