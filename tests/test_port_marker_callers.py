"""Actual producer/patcher callers with the checked reservation store; no game I/O."""
import copy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests"), str(ROOT / "scripts/terrain")]
import make_cluster as mc
import port_marker_ids as ids
import port_marker_store as store
import test_port_marker_ids as fixture
import vmad_patch as vp


class PairedCallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.case = fixture.PortMarkerIdentityTests()
        self.case.setUp()
        self.port = self.root / "port"
        self.port.mkdir()
        (self.port / "FO4Port.esm").write_bytes(self.case.base)
        self.map_raw = fixture.encoded(self.case.mapping)
        (self.port / "formids.json").write_bytes(self.map_raw)
        self.refs, inner = [], []
        for door in self.case.doors:
            source, target = door["src"], door["destination"]["door"]
            self.refs.append({"formkey": source, "type": "Door", "base_formkey": "000100:Synthetic.esm",
                              "pos": [1, 2, 3], "rot": [0, 0, 0],
                              "teleport_destination": {"door": target, "pos": [70, 140, 210], "rot": [0, 0, 0]}})
            inner.append({"formkey": target, "model": "door.nif", "teleport_destination": {
                "door": source, "pos": [280, 350, 420], "rot": [0, 0, 0]}})
        (self.port / "Test.json").write_text(json.dumps({"refs": inner}), encoding="utf-8")
        self.directory = self.root / "reservations"
        self.initial = store.initialize(self.directory, self.case.base, self.map_raw, self.case.patched,
                                        fixture.encoded(self.case.patched_map), self.case.doors,
                                        plugin="FO4Port.esm", core_plugin="Core.esm")

    def produce(self, writer, sources):
        port = mc.port_index(str(self.port), marker_writer=writer)
        cluster, report = mc.doors(self.refs, sources, port)
        return port, cluster, report

    def consumer_entries(self, cluster):
        out = []
        for e in cluster["doors"]:
            item = copy.deepcopy(next(d for d in self.case.doors if d["src"] == e["src"]))
            d = e["destination"]
            item["destination"].update(id=int(d["id"], 16), ref=d["port_ref"], cell=d["port_cell"],
                                       arrival=d["arrival"])
            item["arrival"] = e["return"]["arrival"]
            out.append(item)
        return out

    def patch(self, plan, entries, **changes):
        args = dict(marker_plan=plan, expected_sha256=plan.sha256, base_raw=self.case.base,
                    base_map_raw=self.map_raw, base_map_sha256=hashlib.sha256(self.map_raw).hexdigest())
        args.update(changes)
        edits = vp.port_edits("Core.esm", entries, "FO4Port.esm", 0x804, (-1200, -2700, 0), **args)
        plugin = vp.Plugin(self.case.base)
        vp.patch_port(plugin, edits, 1)
        raw = plugin.serialize()
        checks = vp.check_port(vp.Plugin(self.case.base), vp.Plugin(raw), entries, "Core.esm", (-1200, -2700, 0),
                               marker_plan=plan, expected_sha256=plan.sha256, base_map_raw=self.map_raw,
                               base_map_sha256=hashlib.sha256(self.map_raw).hexdigest())
        self.assertTrue(all(ok for _, ok in checks), checks)
        return raw

    def test_removal_and_reorder_use_retained_ids_and_real_gap_hedr(self):
        with store.session(self.directory, self.initial.sha256) as writer:
            port, cluster, _ = self.produce(writer, [self.case.sources[1]])
            plan = port["_marker_plan"]
            self.assertEqual(cluster["doors"][0]["destination"]["id"], "000805")
            self.assertEqual(cluster["doors_port"]["marker_state_sha256"], plan.sha256)
            self.assertEqual(cluster["doors_port"]["base_sha256"], hashlib.sha256(self.case.base).hexdigest())
            raw = self.patch(plan, self.consumer_entries(cluster))
            self.assertEqual(vp.Plugin(raw).hedr()[2], 0x806)
            self.assertNotIn(0x01000804, vp.Plugin(raw).records())
            _, both, _ = self.produce(writer, list(reversed(self.case.sources)))
            self.assertEqual([e["destination"]["id"] for e in both["doors"]], ["000805", "000804"])
            self.patch(port["_marker_plan"], self.consumer_entries(cluster))
            self.assertEqual(ids.validate_state(writer.raw, plan.sha256)["reservations"], self.initial.assignments)

    def test_removed_highest_marker_stays_reserved_without_inflating_emitted_hedr(self):
        with store.session(self.directory, self.initial.sha256) as writer:
            port, cluster, _ = self.produce(writer, [self.case.sources[0]])
            raw = self.patch(port["_marker_plan"], self.consumer_entries(cluster))
            self.assertEqual(vp.Plugin(raw).hedr()[2], 0x805)
            self.assertEqual(json.loads(writer.raw)["next_id"], 0x806)
            self.assertEqual(writer.reserve(self.case.base, self.map_raw, ["000003:Synthetic.esm"],
                                            plugin="FO4Port.esm").assignments["000003:synthetic.esm"], 0x806)

    def test_new_producer_source_cannot_recycle_a_removed_source_marker(self):
        new_source = "000003:Synthetic.esm"
        added = copy.deepcopy(self.refs[0])
        added["formkey"] = new_source
        self.refs.append(added)
        path = self.port / "Test.json"
        exports = json.loads(path.read_text(encoding="utf-8"))
        exports["refs"][0]["teleport_destination"]["door"] = new_source
        path.write_text(json.dumps(exports), encoding="utf-8")
        new_door = copy.deepcopy(self.case.doors[0])
        new_door["src"] = new_source
        self.case.doors.append(new_door)
        with store.session(self.directory, self.initial.sha256) as writer:
            port, cluster, _ = self.produce(writer, [self.case.sources[1], new_source])
            self.assertEqual([e["destination"]["id"] for e in cluster["doors"]], ["000805", "000806"])
            self.assertEqual(json.loads(writer.raw)["reservations"][self.case.sources[0].lower()], 0x804)
            raw = self.patch(port["_marker_plan"], self.consumer_entries(cluster))
            self.assertEqual(vp.Plugin(raw).hedr()[2], 0x807)

    def test_empty_selection_preserves_all_reservations(self):
        with store.session(self.directory, self.initial.sha256) as writer:
            port, cluster, _ = self.produce(writer, [])
            self.assertEqual(cluster["doors"], [])
            self.assertEqual(writer.raw, self.initial.state)
            self.patch(port["_marker_plan"], [])

    def test_legacy_default_remains_sequential_and_refuses_gaps(self):
        port = mc.port_index(str(self.port))
        cluster, _ = mc.doors(self.refs, list(reversed(self.case.sources)), port)
        self.assertEqual([e["destination"]["id"] for e in cluster["doors"]], ["000804", "000805"])
        self.assertNotIn("marker_state_sha256", cluster["doors_port"])
        with self.assertRaisesRegex(ValueError, "allocates"):
            vp.port_edits("Core.esm", [self.case.doors[1]], "FO4Port.esm", 0x804, (0, 0, 0))

    def test_tampered_assignment_state_pin_owner_and_base_refuse_before_patch(self):
        with store.session(self.directory, self.initial.sha256) as writer:
            port, cluster, _ = self.produce(writer, self.case.sources)
            plan, entries = port["_marker_plan"], self.consumer_entries(cluster)
            cases = [dict(expected_sha256="0" * 64), dict(base_raw=self.case.base + b"x"),
                     dict(base_map_raw=fixture.encoded({**self.case.mapping, "STAT:extra": 0x900})),
                     dict(expected_sha256=None), dict(base_map_raw=self.map_raw + b" "),
                     dict(base_map_sha256=None), dict(base_map_sha256="0" * 64)]
            for change in cases:
                with self.subTest(change=list(change)), self.assertRaises((ValueError, KeyError)):
                    self.patch(plan, entries, **change)
            bad_plan = replace(plan, assignments={**plan.assignments, self.case.sources[0].lower(): 0x900})
            with self.assertRaisesRegex(ValueError, "differs"):
                self.patch(bad_plan, entries)
            wrong = copy.deepcopy(entries)
            wrong[0]["destination"]["plugin"] = "Other.esm"
            with self.assertRaisesRegex(ValueError, "destination plugin"):
                self.patch(plan, wrong)
            wrong = copy.deepcopy(entries)
            wrong[0]["destination"]["id"] += 10
            with self.assertRaisesRegex(ValueError, "promised"):
                self.patch(plan, wrong)
            self.assertEqual((self.port / "FO4Port.esm").read_bytes(), self.case.base)

    def test_duplicate_full_source_alias_and_destination_refuse(self):
        with store.session(self.directory, self.initial.sha256) as writer:
            port, cluster, _ = self.produce(writer, self.case.sources)
            entries = self.consumer_entries(cluster)
            entries[1]["src"] = entries[0]["src"].upper()
            with self.assertRaisesRegex(ValueError, "duplicate requested"):
                self.patch(port["_marker_plan"], entries)
            entries = self.consumer_entries(cluster)
            entries[1]["destination"]["ref"] = entries[0]["destination"]["ref"]
            with self.assertRaisesRegex(ValueError, "pinned base map|listed twice"):
                self.patch(port["_marker_plan"], entries)

    def test_wrong_interior_cell_or_source_owner_refuses_despite_correct_marker(self):
        with store.session(self.directory, self.initial.sha256) as writer:
            port, cluster, _ = self.produce(writer, self.case.sources)
            for field, value in (("cell", "000999"), ("ref", "000803"),
                                 ("door", "00A001:Other.esm")):
                entries = self.consumer_entries(cluster)
                entries[0]["destination"][field] = value
                with self.subTest(field=field), self.assertRaisesRegex(ValueError, "pinned base map"):
                    self.patch(port["_marker_plan"], entries)

    def test_checker_rejects_tampered_plan_instead_of_trusting_gap_alone(self):
        with store.session(self.directory, self.initial.sha256) as writer:
            port, cluster, _ = self.produce(writer, [self.case.sources[1]])
            plan, entries = port["_marker_plan"], self.consumer_entries(cluster)
            raw = self.patch(plan, entries)
            checks = vp.check_port(vp.Plugin(self.case.base), vp.Plugin(raw), entries, "Core.esm", (0, 0, 0),
                                   marker_plan=plan, expected_sha256="0" * 64, base_map_raw=self.map_raw,
                                   base_map_sha256=hashlib.sha256(self.map_raw).hexdigest())
            self.assertFalse(all(ok for _, ok in checks))
            self.assertIn("hash mismatch", checks[0][0])
            checks = vp.check_port(vp.Plugin(self.case.base), vp.Plugin(raw), entries, "Core.esm", (0, 0, 0),
                                   expected_sha256=plan.sha256)
            self.assertFalse(checks[0][1])

    def test_input_drift_and_closed_writer_refuse(self):
        with store.session(self.directory, self.initial.sha256) as writer:
            port = mc.port_index(str(self.port), marker_writer=writer)
            (self.port / "formids.json").write_bytes(self.map_raw + b" ")
            with self.assertRaisesRegex(ValueError, "changed after indexing"):
                mc.doors(self.refs, self.case.sources, port)
            (self.port / "formids.json").write_bytes(self.map_raw)
        with self.assertRaisesRegex(OSError, "closed"):
            mc.doors(self.refs, self.case.sources, port)

    def test_failed_output_retains_reservations_and_lease_until_both_checks(self):
        # Functional API boundary only: this is not the unwired stage CLI's
        # recovery protocol. The first output here is cluster JSON, not a core ESM.
        with store.session(self.directory, self.initial.sha256) as writer:
            writer.reserve(self.case.base, self.map_raw, [*self.case.sources, "000003:Synthetic.esm"],
                           plugin="FO4Port.esm")
            port, cluster, _ = self.produce(writer, self.case.sources)
            plan = port["_marker_plan"]
            first = self.root / "cluster.json"
            first.write_text(json.dumps(cluster), encoding="utf-8")
            probe = "import sys;sys.path.insert(0,sys.argv[1]);import port_marker_store as s;" \
                    "\nwith s.session(sys.argv[2],sys.argv[3]): pass"
            held = subprocess.run([sys.executable, "-I", "-B", "-c", probe, str(ROOT / "scripts/terrain"),
                                   str(self.directory), plan.sha256], capture_output=True, text=True)
            self.assertNotEqual(held.returncode, 0)
            original = first.read_bytes()
            try:
                raise OSError("synthetic failure before second publication")
            except OSError:
                pass
            self.assertEqual(first.read_bytes(), original)
            self.assertEqual((self.directory / "state.json").read_bytes(), plan.state)
            raw = self.patch(plan, self.consumer_entries(cluster))
            (self.root / "FO4Port.esm").write_bytes(raw)
        with store.session(self.directory, plan.sha256) as writer:
            port, cluster, _ = self.produce(writer, self.case.sources)
            self.assertEqual(port["_marker_plan"].sha256, plan.sha256)
            self.assertEqual(json.loads(writer.raw)["reservations"]["000003:synthetic.esm"], 0x806)
            self.patch(port["_marker_plan"], self.consumer_entries(cluster))


if __name__ == "__main__":
    unittest.main()
