"""Raw bootstrap and allocation component for #280; no producer integration."""
import copy
import hashlib
import json
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tests"), str(ROOT / "scripts/terrain"), str(ROOT / "src")]
import test_vmad_patch as fixture
import port_marker_ids as ids
import vmad_patch as vp


def encoded(value):
    return json.dumps(value).encode()


class PortMarkerIdentityTests(unittest.TestCase):
    def setUp(self):
        self.base = fixture.tiny_plugin()
        self.mapping = {"STAT:FO4Port_door02": 0x800, "CELL:FO4Port_Test": 0x801,
                        "REFR:FO4Port_Test:00A001:Synthetic.esm": 0x802,
                        "REFR:FO4Port_Test:00A002:Synthetic.esm": 0x803}
        self.doors = []
        self.patched_map = dict(self.mapping)
        for i in (1, 2):
            door = fixture.door_entry(src=f"{i:06X}:Synthetic.esm", ref=f"{0x801+i:06X}",
                                      dest_id=0x803+i, arrival=0x920+i)
            door["destination"]["door"] = f"{0xA000+i:06X}:Synthetic.esm"
            door["destination"]["arrival"]["pos"] = [i * 10.0, 2.0, 3.0]
            self.doors.append(door)
            self.patched_map[f"MARK:FO4Port_Test:{door['src']}"] = 0x803+i
        plugin = vp.Plugin(self.base)
        vp.patch_port(plugin, vp.port_edits("Core.esm", self.doors, "FO4Port.esm", 0x804), 1)
        self.patched = plugin.serialize()
        self.sources = [d["src"] for d in self.doors]

    def bootstrap(self, **overrides):
        values = dict(base_raw=self.base, base_map_raw=encoded(self.mapping), patched_raw=self.patched,
                      patched_map_raw=encoded(self.patched_map), doors=self.doors,
                      plugin="FO4Port.esm", core_plugin="Core.esm")
        values.update(overrides)
        return ids.bootstrap(**values)

    def reserve(self, plan, sources, **overrides):
        values = dict(state_raw=plan.state, expected_sha256=plan.sha256, base_raw=self.base,
                      base_map_raw=encoded(self.mapping), sources=sources, plugin="FO4Port.esm")
        values.update(overrides)
        return ids.reserve(**values)

    def test_raw_bootstrap_uses_actual_ids_even_when_entries_are_reordered(self):
        plan = self.bootstrap()
        reverse = self.bootstrap(doors=list(reversed(self.doors)))
        self.assertEqual(plan.state, reverse.state)
        self.assertEqual(plan.assignments, {"000001:synthetic.esm": 0x804, "000002:synthetic.esm": 0x805})
        self.assertEqual(plan.sha256, hashlib.sha256(plan.state).hexdigest())

    def test_reorder_insert_remove_reintroduce_preserves_ids_and_tombstones(self):
        original = self.bootstrap()
        self.assertEqual(self.reserve(original, list(reversed(self.sources))).state, original.state)
        added = self.reserve(original, ["000003:Synthetic.esm", *self.sources])
        for source, local in original.assignments.items():
            self.assertEqual(added.assignments[source], local)
        self.assertEqual(added.assignments["000003:synthetic.esm"], 0x806)
        removed = self.reserve(added, [self.sources[1]])
        self.assertEqual(removed.state, added.state)
        self.assertEqual(self.reserve(removed, [*self.sources, "000003:Synthetic.esm"]).state, added.state)
        next_plan = self.reserve(removed, ["000004:Synthetic.esm"])
        self.assertEqual(next_plan.assignments["000004:synthetic.esm"], 0x807)
        self.assertEqual(len(json.loads(next_plan.state)["reservations"]), 4)

    def test_full_source_ownership_case_and_duplicate_aliases(self):
        plan = self.bootstrap()
        result = self.reserve(plan, ["000001:SYNTHETIC.ESM", "000001:Another.esm"])
        self.assertEqual(result.assignments["000001:synthetic.esm"], 0x804)
        self.assertEqual(result.assignments["000001:another.esm"], 0x806)
        with self.assertRaisesRegex(ValueError, "duplicate requested"):
            self.reserve(plan, [self.sources[0], self.sources[0].upper()])
        for bad in ("1:Synthetic.esm", "000000:Synthetic.esm", "01000001:Synthetic.esm", "000001:../X.esm"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.reserve(plan, [bad])

    def test_uncommitted_output_retry_retains_previously_planned_reservations(self):
        # The consumer must persist this state before publishing output. Reopen
        # the returned state as if later plugin publication failed.
        initial = self.bootstrap()
        planned = self.reserve(initial, [*self.sources, "000003:Synthetic.esm"])
        self.assertEqual(self.reserve(planned, ["000003:Synthetic.esm"]).state, planned.state)

    def grown_base(self, local):
        extra = fixture.rec(b"REFR", fixture.OWN | local,
                            [(b"NAME", struct.pack("<I", fixture.OWN | 0x800)),
                             (b"DATA", struct.pack("<6f", 9, 8, 7, 0, 0, 0))])
        mapping = dict(self.mapping, **{"REFR:FO4Port_Test:00A003:Synthetic.esm": local})
        return fixture.tiny_plugin(extra=(extra,)), encoded(mapping)

    def test_append_only_base_growth_is_allowed_without_marker_collisions(self):
        plan = self.bootstrap()
        base, mapping = self.grown_base(0x810)
        changed = self.reserve(plan, [*self.sources, "000003:Synthetic.esm"], base_raw=base, base_map_raw=mapping)
        self.assertEqual(changed.assignments["000001:synthetic.esm"], 0x804)
        self.assertEqual(changed.assignments["000003:synthetic.esm"], 0x811)
        self.assertEqual(self.reserve(changed, self.sources, base_raw=base, base_map_raw=mapping).state, changed.state)

    def test_base_growth_cannot_take_even_a_removed_marker_reservation(self):
        removed = self.reserve(self.bootstrap(), [self.sources[1]])
        base, mapping = self.grown_base(0x804)
        with self.assertRaisesRegex(ValueError, "occupied a reserved"):
            self.reserve(removed, self.sources, base_raw=base, base_map_raw=mapping)
        # An un-emitted base reservation is just as unavailable as a record.
        mapping = dict(self.mapping, **{"STAT:SkippedNewSource": 0x804})
        with self.assertRaisesRegex(ValueError, "occupied a reserved"):
            self.reserve(removed, self.sources, base_map_raw=encoded(mapping))

    def test_unemitted_base_map_ids_remain_reserved(self):
        before = dict(self.mapping, **{"STAT:RetiredSource": 0x806})
        after = dict(self.patched_map, **{"STAT:RetiredSource": 0x806})
        plan = self.bootstrap(base_map_raw=encoded(before), patched_map_raw=encoded(after))
        added = self.reserve(plan, ["000003:Synthetic.esm"], base_map_raw=encoded(before))
        self.assertEqual(added.assignments["000003:synthetic.esm"], 0x807)
        self.assertEqual(json.loads(added.state)["base"]["source_ids"]["stat:retiredsource"], 0x806)
        before["STAT:RetiredSource"], after["STAT:RetiredSource"] = 0x804, 0x804
        with self.assertRaisesRegex(ValueError, "collides with base"):
            self.bootstrap(base_map_raw=encoded(before), patched_map_raw=encoded(after))

    def test_unemitted_cells_and_references_cannot_be_bootstrap_endpoints(self):
        for field, map_key in (("cell", "CELL:FO4Port_Missing"),
                               ("ref", "REFR:FO4Port_Test:00A003:Synthetic.esm")):
            before = dict(self.mapping, **{map_key: 0x810})
            after = dict(self.patched_map, **{map_key: 0x810})
            doors = copy.deepcopy(self.doors)
            doors[0]["destination"][field] = "000810"
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "not emitted"):
                self.bootstrap(base_map_raw=encoded(before), patched_map_raw=encoded(after), doors=doors)

    def test_base_relocation_or_source_reassignment_requires_reviewed_migration(self):
        plan = self.bootstrap()
        mapping = dict(self.mapping)
        a, b = [k for k in mapping if k.startswith("REFR:")]
        mapping[a], mapping[b] = mapping[b], mapping[a]
        with self.assertRaisesRegex(ValueError, "source identities changed"):
            self.reserve(plan, self.sources, base_map_raw=encoded(mapping))
        base = vp.Plugin(self.base)
        group, index, record = base.find(fixture.OWN | 0x802)
        group[index] = record.with_fields([(s, struct.pack("<6f", 1, 2, 3, 0, 0, 0) if s == b"DATA" else d)
                                           for s, d in record.fields()])
        with self.assertRaisesRegex(ValueError, "base records changed"):
            self.reserve(plan, self.sources, base_raw=base.serialize())
        with self.assertRaisesRegex(ValueError, "lineage changed"):
            self.reserve(plan, self.sources, plugin="Different.esm")

    def test_marker_maps_cannot_substitute_for_raw_proof(self):
        wrong = dict(self.patched_map)
        markers = [k for k in wrong if k.startswith("MARK:")]
        wrong[markers[0]], wrong[markers[1]] = wrong[markers[1]], wrong[markers[0]]
        with self.assertRaisesRegex(ValueError, "marker map differs"):
            self.bootstrap(patched_map_raw=encoded(wrong))
        with self.assertRaisesRegex(ValueError, "raw generation check failed"):
            self.bootstrap(patched_raw=self.base)
        broken = vp.Plugin(self.patched)
        record = broken.find(fixture.OWN | 0x804)[2]
        record.header = record.header[:8] + struct.pack("<I", record.flags & ~vp.PERSISTENT) + record.header[12:]
        with self.assertRaisesRegex(ValueError, "raw generation check failed"):
            self.bootstrap(patched_raw=broken.serialize())
        with self.assertRaisesRegex(ValueError, "raw generation check failed"):
            self.bootstrap(core_plugin="WrongCore.esm")

    def test_bootstrap_rejects_duplicate_alias_owner_and_malformed_transform(self):
        bad = copy.deepcopy(self.doors)
        bad.append(copy.deepcopy(bad[0]))
        bad[-1]["src"] = bad[-1]["src"].upper()
        with self.assertRaisesRegex(ValueError, "duplicate source"):
            self.bootstrap(doors=bad)
        bad = copy.deepcopy(self.doors)
        bad[0]["destination"]["plugin"] = "Other.esm"
        with self.assertRaisesRegex(ValueError, "wrong destination owner"):
            self.bootstrap(doors=bad)
        for value in ([], [1, 2], [1, 2, float("nan")], [1, 2, True]):
            bad = copy.deepcopy(self.doors)
            bad[0]["destination"]["arrival"]["pos"] = value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "transform"):
                self.bootstrap(doors=bad)

    def test_pins_duplicate_json_corrupt_ids_and_missing_state_refuse(self):
        plan = self.bootstrap()
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            self.reserve(plan, self.sources, state_raw=plan.state + b" ")
        with self.assertRaises(ValueError):
            self.reserve(plan, self.sources, state_raw=b"", expected_sha256=hashlib.sha256(b"").hexdigest())
        duplicate = b'{"format":1,' + plan.state[1:]
        with self.assertRaisesRegex(ValueError, "duplicate JSON"):
            self.reserve(plan, self.sources, state_raw=duplicate, expected_sha256=hashlib.sha256(duplicate).hexdigest())
        for value in (True, 0x7FF, 0x1000000, 0x805):
            state = json.loads(plan.state)
            state["reservations"]["000001:synthetic.esm"] = value
            raw = encoded(state)
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.reserve(plan, self.sources, state_raw=raw, expected_sha256=hashlib.sha256(raw).hexdigest())

    def test_id_exhaustion_refuses_without_recycling(self):
        plan = self.bootstrap()
        state = json.loads(plan.state)
        state["reservations"]["000002:synthetic.esm"] = ids.MAX_ID
        state["next_id"] = ids.MAX_ID + 1
        raw = encoded(state)
        with self.assertRaisesRegex(ValueError, "exhausted"):
            self.reserve(plan, ["000003:Synthetic.esm"], state_raw=raw, expected_sha256=hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    unittest.main()
