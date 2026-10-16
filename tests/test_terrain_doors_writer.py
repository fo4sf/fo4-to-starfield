"""Scripted load doors through the actual terrain writer (dotnet/TerrainOverlays) on the synthetic master of
test_terrain_reference_identity (dotnet/TerrainIdentityFixture), never a game: the door REFR keeps its slot, every
earlier FormID stays, the ACTI bases and then the arrival markers take new ids after every other record, the REFR's
VMAD is byte-for-byte the layout Starfield.esm's own REFR scripts carry (scripts/terrain/vmad_patch.encode), and the
core64c check accepts the written records (docs/terrain/scripted-doors.md)."""
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

spec = importlib.util.spec_from_file_location("make_core64c", ROOT / "scripts" / "terrain" / "make_core64c.py")
mk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mk)
import overlay_records  # noqa: E402
import vmad_patch  # noqa: E402

DOOR_EDID = "FO4Core_door_018c8b_fallout4"
OBND = [[-0.8, -0.2286, 0.0], [0.8, 0.1143, 2.5143]]


def subrecords(payload):
    out, pos = [], 0
    while pos < len(payload):
        sig, size = payload[pos:pos + 4], struct.unpack_from("<H", payload, pos + 4)[0]
        out.append((sig, payload[pos + 6:pos + 6 + size]))
        pos += 6 + size
    return out


def field(payload, sig):
    return next((d for s, d in subrecords(payload) if s == sig), None)


class TerrainDoorsWriterTests(unittest.TestCase):
    setUpClass = classmethod(tri.TerrainReferenceIdentityTests.setUpClass.__func__)
    run_writer = tri.TerrainReferenceIdentityTests.run_writer
    promote = tri.TerrainReferenceIdentityTests.promote

    def with_doors(self, objects, indices=(2,)):
        """The refs at `indices` become scripted doors (one shared ACTI), each with its own destination and arrival."""
        obj = copy.deepcopy(objects)
        obj["doors"] = []
        for n, i in enumerate(indices):
            r = next(x for x in objects["refs"] if x["src"] == self.objects["refs"][i]["src"])
            obj["doors"].append({"src": r["src"], "edid": DOOR_EDID, "reference_index": i, "model": "synthetic.nif",
                                 "name": "Door", "obnd": OBND, "cell": r["cell"], "pos": r["pos"], "rot": r["rot"],
                                 "scale": r["scale"], "rigged": False,
                                 "script": {"name": "FO4SF_LoadDoor",
                                            "properties": {"DestinationPlugin": "FO4Port.esm", "DestinationId": 0x7D0B + n}},
                                 "destination": {"plugin": "FO4Port.esm", "id": 0x7D0B + n, "door": "0EE5D6:Fallout4.esm",
                                                 "cell": "SuperDuperMart01"},
                                 "arrival": {"pos": [r["pos"][0] + 0.5, r["pos"][1] - 0.5, r["pos"][2]], "rot": [0, 0, 2.5812],
                                             "cell": r["cell"]}})
        obj["refs"] = [x for x in obj["refs"] if x["src"] not in {d["src"] for d in obj["doors"]}]
        return obj

    def build_pair(self, name, indices=(2,), items=()):
        base = self.promote([1], items)                            # one container: its CONT base must keep its id too
        before, old_stage = self.run_writer(base, f"{name}-before")
        after, new_stage = self.run_writer(self.with_doors(base, indices), f"{name}-after")
        self.assertEqual(before.returncode, 0, before.stderr)
        self.assertEqual(after.returncode, 0, after.stderr)
        return old_stage, new_stage

    def test_door_keeps_its_slot_and_new_records_follow_everything(self):
        old_stage, new_stage = self.build_pair("doors", indices=(2, 0))
        old = json.loads((old_stage / "formids.json").read_text())
        new = json.loads((new_stage / "formids.json").read_text())
        self.assertNotIn("doors", old)
        self.assertEqual(new["bases"], old["bases"])
        self.assertEqual(new["containers"], old["containers"])
        objects = self.with_doors(self.promote([1]), (2, 0))
        srcs = [d["src"] for d in objects["doors"]]
        self.assertEqual(dict(new["refs"], **{s: new["doors"][s]["ref"] for s in srcs}), old["refs"])   # slots kept
        old_records, new_records = tri.records(old_stage / "Synthetic.esm"), tri.records(new_stage / "Synthetic.esm")
        for key, rec in old_records.items():
            if key in {int(old["refs"][s], 16) for s in srcs}:
                self.assertEqual(tri.without_base(new_records[key])[1:], tri.without_base(rec)[1:])   # cell, flags
            else:
                self.assertEqual(new_records[key], rec)                                        # same id, same bytes
        first = max(old_records) + 1
        self.assertEqual({new["doors"][s]["base"] for s in srcs}, {f"{first:06X}"})            # one ACTI, first new id
        self.assertEqual([int(new["doors"][s]["arrival"], 16) for s in srcs], [first + 1, first + 2])
        self.assertEqual(max(new_records), first + 2)
        mk.check_reference_slots(objects, new)
        mk.check_door_identities(objects, new)
        plugin = overlay_records.walk_plugin(str(new_stage / "Synthetic.esm"))
        self.assertEqual(mk.door_record_check(plugin["records"], 1 << 24, objects, new), [])
        self.assertEqual(mk.promoted_record_check(plugin["records"], 1 << 24, objects, new), [])
        cells = {k: struct.unpack_from("<ii", field(v[1], b"XCLC")) for k, v in new_records.items()
                 if v[0] == b"CELL" and field(v[1], b"XCLC") is not None}
        for e in objects["doors"]:
            sig, payload, owner, flags = new_records[int(new["doors"][e["src"]]["ref"], 16)]
            self.assertEqual(sig, b"REFR")
            self.assertEqual(tuple(e["cell"]), cells[owner])
            self.assertEqual(flags & 0x400, 0)                                                   # temporary
            self.assertEqual(struct.unpack("<I", field(payload, b"NAME"))[0], 0x01000000 | first)
            self.assertEqual([s for s, _ in subrecords(payload)][:2], [b"VMAD", b"NAME"])           # vanilla order
            vmad = field(payload, b"VMAD")
            want = vmad_patch.load_door_vmad("FO4SF_LoadDoor", "DestinationPlugin", "FO4Port.esm", "DestinationId",
                                             e["script"]["properties"]["DestinationId"])
            self.assertEqual(vmad, want)                                                         # Mutagen == raw encoder
            self.assertEqual(vmad_patch.door_properties(vmad, "FO4SF_LoadDoor", "DestinationPlugin", "DestinationId")[0],
                             ("FO4Port.esm", e["script"]["properties"]["DestinationId"]))
            sig, payload, owner, flags = new_records[int(new["doors"][e["src"]]["arrival"], 16)]
            self.assertEqual((sig, flags & 0x400), (b"REFR", 0))
            self.assertEqual(tuple(e["arrival"]["cell"]), cells[owner])
            self.assertEqual(struct.unpack("<I", field(payload, b"NAME"))[0], 0x3B)              # XMarker, master 0
            self.assertIsNone(field(payload, b"VMAD"))
            data = struct.unpack("<6f", field(payload, b"DATA"))
            for u, v in zip(data, e["arrival"]["pos"] + e["arrival"]["rot"]):
                self.assertAlmostEqual(u, v, places=4)
        sig, payload, _owner, _flags = new_records[first]
        self.assertEqual(sig, b"ACTI")
        fields = dict(subrecords(payload))
        self.assertEqual(fields[b"EDID"], DOOR_EDID.encode() + b"\0")
        self.assertEqual(fields[b"FULL"], b"Door\0")
        self.assertEqual(fields[b"MODL"], b"synthetic.nif\0")
        self.assertEqual(fields[b"PNAM"], bytes.fromhex("cc4c3300"))
        self.assertEqual(fields[b"FNAM"], b"\0\0")
        self.assertEqual(struct.unpack("<H", fields[b"JNAM"])[0], 360)
        self.assertNotIn(b"VMAD", fields)
        for u, v in zip(struct.unpack("<6f", fields[b"OBND"]), OBND[0] + OBND[1]):
            self.assertAlmostEqual(u, v, places=4)

    def test_doors_come_after_items_and_an_empty_list_changes_nothing(self):
        old_stage, new_stage = self.build_pair("doors-items", indices=(0,), items=(2,))
        old = json.loads((old_stage / "formids.json").read_text())
        new = json.loads((new_stage / "formids.json").read_text())
        for k in ("bases", "containers", "items"):
            self.assertEqual(new[k], old[k])
        old_records, new_records = tri.records(old_stage / "Synthetic.esm"), tri.records(new_stage / "Synthetic.esm")
        misc = [k for k, v in new_records.items() if v[0] == b"MISC"]
        acti = [k for k, v in new_records.items() if v[0] == b"ACTI"]
        self.assertEqual((len(misc), len(acti)), (1, 1))
        self.assertGreater(acti[0], max(old_records))
        base = self.promote([1], (2,))
        a, sa = self.run_writer(base, "doors-empty-a")
        b, sb = self.run_writer(dict(copy.deepcopy(base), doors=[]), "doors-empty-b")
        self.assertEqual((a.returncode, b.returncode), (0, 0), a.stderr + b.stderr)
        self.assertEqual((sa / "Synthetic.esm").read_bytes(), (sb / "Synthetic.esm").read_bytes())

    def test_bad_door_inputs_do_not_replace_the_plugin_or_map(self):
        good = self.with_doors(self.promote([1]), (2, 0))
        proc, stage = self.run_writer(good, "door-refusals")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        pinned = {n: (stage / n).read_bytes() for n in ("Synthetic.esm", "formids.json")}
        invalid = []
        no_slot = copy.deepcopy(good)
        del no_slot["doors"][0]["reference_index"]                 # a door keeps its original slot
        invalid.append(no_slot)
        alias = copy.deepcopy(good)
        alias["doors"][0]["src"] = good["containers"][0]["src"].lower()   # the same source as a promoted REFR
        invalid.append(alias)
        twice = copy.deepcopy(good)
        twice["doors"][1]["reference_index"] = good["doors"][0]["reference_index"]
        invalid.append(twice)
        disagree = copy.deepcopy(good)
        disagree["doors"][1]["name"] = "Hatch"                     # one ACTI edid, two names
        invalid.append(disagree)
        for bad_id in (0, 0x1000000, -1):                         # (a string id is make_core64c's refusal)
            bad = copy.deepcopy(good)
            bad["doors"][0]["script"]["properties"]["DestinationId"] = bad_id
            invalid.append(bad)
        empty_plugin = copy.deepcopy(good)
        empty_plugin["doors"][0]["script"]["properties"]["DestinationPlugin"] = ""
        invalid.append(empty_plugin)
        no_props = copy.deepcopy(good)
        no_props["doors"][0]["script"]["properties"] = {}
        invalid.append(no_props)
        outside = copy.deepcopy(good)
        outside["doors"][0]["arrival"]["cell"] = [5, 5]
        invalid.append(outside)
        bad_obnd = copy.deepcopy(good)
        bad_obnd["doors"][0]["obnd"] = [[1, 0, 0], [0, 0, 0]]
        invalid.append(bad_obnd)
        blank = copy.deepcopy(good)
        blank["doors"][0]["name"] = " "
        invalid.append(blank)
        for objects in invalid:
            proc, _ = self.run_writer(objects, "door-refusals")
            self.assertNotEqual(proc.returncode, 0)
            self.assertEqual({n: (stage / n).read_bytes() for n in pinned}, pinned)


if __name__ == "__main__":
    unittest.main()
