"""Scripted load doors through the actual terrain writer (dotnet/TerrainOverlays) on the synthetic master of
test_terrain_reference_identity (dotnet/TerrainIdentityFixture), never a game: the door REFR keeps its slot and carries
the FO4SF_LoadDoor VMAD byte for byte as scripts/terrain/vmad_patch.py encodes it, the arrival markers take new ids
after every other record (the lights included), one ACTI per door base follows, and make_core64c's own checks pass on
the written plugin (docs/terrain/scripted-doors.md)."""
import copy
import importlib.util
import json
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "terrain"))
import test_terrain_reference_identity as tri  # noqa: E402  (module import: its TestCase is not collected twice)
import test_terrain_lights_writer as tlw  # noqa: E402
import vmad_patch  # noqa: E402

spec = importlib.util.spec_from_file_location("make_core64c", ROOT / "scripts" / "terrain" / "make_core64c.py")
mk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mk)

subrecords, field = tlw.subrecords, tlw.field


class TerrainDoorsWriterTests(unittest.TestCase):
    setUpClass = classmethod(tri.TerrainReferenceIdentityTests.setUpClass.__func__)
    run_writer = tri.TerrainReferenceIdentityTests.run_writer
    promote = tri.TerrainReferenceIdentityTests.promote

    @staticmethod
    def door(r, index, dest_id, edid="FO4Core_door_018c8b_synthetic", name="Door", arrival=(150.0, 160.0, 2.0), model="synthetic.nif"):
        return dict(r, reference_index=index, edid=edid, model=model, name=name,
                    destination={"plugin": "FO4Port.esm", "id": dest_id, "ref": "007D0B", "cell": "006C46",
                                 "door": "0EE5D6:Fallout4.esm", "arrival": {"pos": [5.449, 17.291, -3.654], "rot": [0, 0, 4.7124]}},
                    arrival={"pos": list(arrival), "rot": [0, 0, 2.5812], "cell": [int(arrival[0] // 100), int(arrival[1] // 100)]})

    def with_doors(self, objects, change=None):
        """Refs 1 and 2 become two doors of one base (one ACTI); the marker of the first lands in cell (1, 1), of the
        second in (0, 1); the lights of test_terrain_lights_writer come along (the markers must follow them)."""
        obj = copy.deepcopy(objects)
        r = obj["refs"]                                            # the two left after the container (original slots 1, 2)
        obj["doors"] = [self.door(r[0], 1, 0xDEFF), self.door(r[1], 2, 0xDF00, arrival=(30.0, 140.0, 4.0))]
        obj["refs"] = []
        if change:
            change(obj)
        return obj

    def build_pair(self, name):
        base = tlw.TerrainLightsWriterTests.with_lights(self, self.promote([0]))   # a container, three lights
        before, old_stage = self.run_writer(base, f"{name}-before")
        after, new_stage = self.run_writer(self.with_doors(base), f"{name}-after")
        self.assertEqual(before.returncode, 0, before.stderr)
        self.assertEqual(after.returncode, 0, after.stderr)
        return base, old_stage, new_stage

    def test_doors_keep_their_slots_and_append_markers_then_the_acti(self):
        base, old_stage, new_stage = self.build_pair("doors")
        old = json.loads((old_stage / "formids.json").read_text())
        new = json.loads((new_stage / "formids.json").read_text())
        self.assertNotIn("doors", old)                             # a build without doors keeps its formids.json shape
        for k in ("bases", "containers", "lights"):
            self.assertEqual(new[k], old[k])                       # nothing before the doors moved, the lights included
        doors = new["doors"]
        self.assertEqual(set(doors), {"000002:Synthetic.esm", "000003:Synthetic.esm"})
        combined = dict(new["refs"], **{src: v["ref"] for src, v in doors.items()})
        self.assertEqual(combined, old["refs"])                    # every door REFR keeps its id
        old_records, new_records = tri.records(old_stage / "Synthetic.esm"), tri.records(new_stage / "Synthetic.esm")
        top = max(old_records)
        m1, m2 = int(doors["000002:Synthetic.esm"]["arrival"], 16), int(doors["000003:Synthetic.esm"]["arrival"], 16)
        acti = {int(v["base"], 16) for v in doors.values()}
        self.assertEqual(len(acti), 1)                             # one ACTI per FO4 door base
        acti = acti.pop()
        self.assertEqual([m1, m2, acti], [top + 1, top + 2, top + 3])   # markers in "doors" order, then the ACTI, after the LIGHs
        for key, rec in old_records.items():
            if key in {int(v["ref"], 16) for v in doors.values()}:
                self.assertEqual(tri.without_base(new_records[key])[0][1:], tri.without_base(rec)[0])   # + VMAD in front
                continue
            self.assertEqual(new_records[key], rec)                # every other record: same id, same bytes, same cell
        # the door REFR: VMAD first, then NAME (the ACTI), the rest as before; the VMAD is vmad_patch's byte for byte
        for src, dest in (("000002:Synthetic.esm", 0xDEFF), ("000003:Synthetic.esm", 0xDF00)):
            r = new_records[int(doors[src]["ref"], 16)]
            self.assertEqual(r[0], b"REFR")
            sigs = [s for s, _d in subrecords(r[1])]
            self.assertEqual(sigs[:2], [b"VMAD", b"NAME"])
            self.assertEqual(field(r[1], b"VMAD"), vmad_patch.load_door_vmad("FO4Port.esm", dest))
            self.assertEqual(vmad_patch.load_door_destination(field(r[1], b"VMAD")), ("FO4Port.esm", dest))
            self.assertEqual(struct.unpack("<I", field(r[1], b"NAME"))[0], 0x01000000 | acti)
            self.assertEqual(r[3] & 0x400, 0)                      # temporary
        # the markers: XMarker of the master, at the arrival point, temporary, in the arrival's own cell
        cells = {k: v[1] for k, v in new_records.items() if v[0] == b"CELL"}
        for m, pos, cell in ((m1, (150.0, 160.0, 2.0), (1, 1)), (m2, (30.0, 140.0, 4.0), (0, 1))):
            r = new_records[m]
            self.assertEqual(r[0], b"REFR")
            self.assertEqual(struct.unpack("<I", field(r[1], b"NAME"))[0], 0x0000003B)
            self.assertEqual(struct.unpack("<6f", field(r[1], b"DATA"))[:3], pos)
            self.assertAlmostEqual(struct.unpack("<6f", field(r[1], b"DATA"))[5], 2.5812, places=5)
            self.assertEqual(r[3], 0)
            self.assertIsNone(field(r[1], b"XSCL"))
            grid = struct.unpack("<2i", field(cells[r[2]], b"XCLC")[:8])
            self.assertEqual(grid, cell)
        # the ACTI: the door mesh, FULL, the vanilla majority PNAM / FNAM / JNAM, no VMAD
        a = dict(subrecords(new_records[acti][1]))
        self.assertEqual(new_records[acti][0], b"ACTI")
        self.assertEqual((a[b"EDID"], a[b"MODL"], a[b"FULL"]), (b"FO4Core_door_018c8b_synthetic\0", b"synthetic.nif\0", b"Door\0"))
        self.assertEqual((a.get(b"PNAM"), a.get(b"FNAM"), a.get(b"JNAM")), (bytes.fromhex("cc4c3300"), b"\0\0", struct.pack("<H", 360)))
        self.assertNotIn(b"VMAD", a)
        (new_stage / "record-layout.json").write_text(json.dumps(
            {"ACTI_door": [[s.decode(), d.hex()] for s, d in subrecords(new_records[acti][1])],
             "REFR_door": [[s.decode(), d.hex()] for s, d in subrecords(new_records[int(doors["000002:Synthetic.esm"]["ref"], 16)][1])],
             "REFR_marker": [[s.decode(), d.hex()] for s, d in subrecords(new_records[m1][1])]}, indent=1))
        # make_core64c's checks on the written plugin
        objects = self.with_doors(base)
        mk.check_reference_slots(objects, new)
        mk.check_light_identities(objects, new)
        mk.check_door_identities(objects, new)
        walked = mk.overlay_records.walk_plugin(str(new_stage / "Synthetic.esm"))
        own = len(walked["masters"]) << 24
        first_light, last_other = mk.lights_after(walked["records"], 1, new)
        self.assertGreater(first_light, last_other)
        first_door, last_other = mk.doors_after(walked["records"], 1, new)
        self.assertGreater(first_door, last_other)
        self.assertEqual(mk.door_record_problems(walked["records"], own, objects, new), [])
        res = mk.promotion_checks(walked["records"], own, objects, new, {"objects": {"exported": 6, "skipped": {}}})
        self.assertTrue(all(ok for _w, ok in res), res)
        self.assertIn("+ 2 door arrival markers", res[0][0])
        self.assertIn("1 ACTI = 1 distinct doors edids", [w.split(" (")[0] for w, _ok in res])
        wrong = self.with_doors(base, lambda o: o["doors"][0]["destination"].update(id=0xDF01))
        self.assertFalse(mk.promotion_checks(walked["records"], own, wrong, new, {"objects": {"exported": 6, "skipped": {}}})[-1][1])
        wrong = self.with_doors(base, lambda o: o["doors"][1]["arrival"].update(pos=[30.0, 140.0, 5.0]))
        self.assertTrue(mk.door_record_problems(walked["records"], own, wrong, new))

    def test_a_navmesh_door_triangle_may_name_a_scripted_door(self):
        """The core's manhole door 042908 is a navmesh door triangle (core64i's navmesh.json): a promoted door keeps
        its REFR id, so the NAVM links to the same record; an unknown source is still refused."""
        base = tlw.TerrainLightsWriterTests.with_lights(self, self.promote([0]))
        objects = self.with_doors(base)
        navmesh = {"navmeshes": [{"cell": [0, 1], "grid": {"size": [100.0, 100.0], "min": [0.0, 100.0, 0.0], "max": [100.0, 200.0, 10.0],
                                                           "divisor": 1, "raw": [1, 0]},
                                  "vertices": [[1.0, 101.0, 0.0, 0], [9.0, 101.0, 0.0, 0], [5.0, 109.0, 0.0, 0]],
                                  "triangles": [[0, 1, 2, -1, -1, -1, 0.5, 0, 0, 0]], "links": [],
                                  "doors": [[0, 1, "000003:Synthetic.esm"]], "waypoints": [],
                                  "nvmi": {"location": [5.0, 104.0, 0.0], "border": 0}}]}
        saved = dict(self.params)
        try:
            self.params = dict(saved, navmesh="navmesh.json")
            stage = self.root / "doors-navmesh"
            stage.mkdir(exist_ok=True)
            (stage / "navmesh.json").write_text(json.dumps(navmesh), encoding="utf-8")
            proc, stage = self.run_writer(objects, "doors-navmesh")
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            ids = json.loads((stage / "formids.json").read_text())
            written = tri.records(stage / "Synthetic.esm")
            navm = written[int(ids["navmeshes"][0], 16)]
            self.assertEqual(navm[0], b"NAVM")
            door_ref = int(ids["doors"]["000003:Synthetic.esm"]["ref"], 16)
            self.assertIn(struct.pack("<I", 0x01000000 | door_ref), navm[1])             # the door triangle's link
            navmesh["navmeshes"][0]["doors"] = [[0, 1, "00FFFF:Synthetic.esm"]]
            (stage / "navmesh.json").write_text(json.dumps(navmesh), encoding="utf-8")
            proc, _ = self.run_writer(objects, "doors-navmesh")
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("not a placed reference", proc.stdout + proc.stderr)
        finally:
            self.params = saved

    def test_bad_door_inputs_leave_the_plugin_and_map(self):
        base = tlw.TerrainLightsWriterTests.with_lights(self, self.promote([0]))
        good = self.with_doors(base)
        proc, stage = self.run_writer(good, "doors-refusals")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        pinned = {n: (stage / n).read_bytes() for n in ("Synthetic.esm", "formids.json")}
        invalid = [
            self.with_doors(base, lambda o: o["doors"][0]["destination"].update(id=0)),
            self.with_doors(base, lambda o: o["doors"][0]["destination"].update(id=0x1000000)),
            self.with_doors(base, lambda o: o["doors"][0]["destination"].update(plugin="")),
            self.with_doors(base, lambda o: o["doors"][0]["destination"].update(plugin="sub\\FO4Port.esm")),
            self.with_doors(base, lambda o: o["doors"][1]["destination"].update(id=0xDEFF)),        # two doors, one destination
            self.with_doors(base, lambda o: o["doors"][1].update(name="Gate")),                       # one ACTI edid, two names
            self.with_doors(base, lambda o: o["doors"][1].update(model="other.nif")),                 # one ACTI edid, two models
            self.with_doors(base, lambda o: o["doors"][1]["arrival"].update(cell=[5, 5])),            # outside the overlay
            self.with_doors(base, lambda o: o["doors"][1].update(reference_index=0)),                 # the container's slot
            self.with_doors(base, lambda o: o["doors"][0].update(name="two\nlines")),
        ]
        for objects in invalid:
            proc, _ = self.run_writer(objects, "doors-refusals")
            self.assertNotEqual(proc.returncode, 0)
            self.assertEqual({n: (stage / n).read_bytes() for n in pinned}, pinned)


if __name__ == "__main__":
    unittest.main()
