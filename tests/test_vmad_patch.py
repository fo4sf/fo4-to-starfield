"""scripts/terrain/vmad_patch.py: the scripted load door's REFR VMAD (codec against the layout the design pass read
from Starfield.esm and from Mutagen's own write), and the interior post-pass on a synthetic plugin: the door REFR
gains the VMAD, the persistent arrival marker is added, every other record stays byte-identical."""
import json
import os
import struct
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "terrain"))
sys.path.insert(0, os.path.join(ROOT, "src"))
import vmad_patch as vp  # noqa: E402

# The 80 bytes Mutagen 0.55.0-alpha.67 wrote for FO4SF_LoadDoor -> FO4Port.esm:0x2339 (the design pass of 2026-10-16,
# C:\Modding\scratch\doorspec: read back raw, the layout of vanilla REFR VMADs)
REFERENCE = bytes.fromhex("0600" "0200" "0100" "0e00" + "FO4SF_LoadDoor".encode().hex() + "00" "0200"
                          "1100" + "DestinationPlugin".encode().hex() + "02" "01" "0b00" + "FO4Port.esm".encode().hex()
                          + "0d00" + "DestinationId".encode().hex() + "03" "01" "39230000")
OWN = 0x01000000


def rec(sig, fid, fields, flags=0):
    return vp.record_bytes(sig, fid, flags, fields)


def tiny_plugin(door_id=0x802, cell_id=0x801, next_id=None, extra=()):
    """A synthetic plugin: TES4 (master Starfield.esm), a STAT, an interior CELL whose temporary children group holds
    the door REFR (NAME the STAT, DATA) and a second REFR, plus `extra` records in the temporary group. Returns bytes."""
    stat = rec(b"STAT", OWN | 0x800, [(b"EDID", b"FO4Port_door02\0"), (b"MODL", b"door02.nif\0")])
    cell = rec(b"CELL", OWN | cell_id, [(b"EDID", b"FO4Port_Test\0"), (b"DATA", struct.pack("<I", 1))])
    door = rec(b"REFR", OWN | door_id, [(b"NAME", struct.pack("<I", OWN | 0x800)), (b"DATA", struct.pack("<6f", 6.4, 17.3714, -3.6571, 0, 0, 4.712389))])
    other = rec(b"REFR", OWN | 0x803, [(b"EDID", b"FO4Port_other\0"), (b"NAME", struct.pack("<I", OWN | 0x800)),
                                       (b"DATA", struct.pack("<6f", 1, 2, 3, 0, 0, 0))])
    temp = vp.Group(struct.pack("<I", OWN | cell_id), vp.GROUP_TEMPORARY, bytes(8), [door, other] + list(extra))
    children = vp.Group(struct.pack("<I", OWN | cell_id), vp.GROUP_CELL_CHILDREN, bytes(8), [temp])
    sub = vp.Group(struct.pack("<I", 0), 3, bytes(8), [cell, children])
    block = vp.Group(struct.pack("<I", 0), 2, bytes(8), [sub])
    top = vp.Group(b"CELL", 0, bytes(8), [block])
    stats = vp.Group(b"STAT", 0, bytes(8), [stat])
    ids = [0x800, cell_id, door_id, 0x803] + [r.fid & 0xFFFFFF for r in extra]
    hedr = struct.pack("<fII", 0.96, len(ids), next_id if next_id is not None else max(ids) + 1)
    tes4 = vp.record_bytes(b"TES4", 0, 0x1, [(b"HEDR", hedr), (b"MAST", b"Starfield.esm\0"), (b"DATA", bytes(8))])
    return tes4.serialize() + stats.serialize() + top.serialize()


def core_folder(d, doors, plugin="FO4TerrainCore.esm"):
    """A core build with doors: objects.json "doors" entries and formids.json "doors" ids."""
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "objects.json"), "w", encoding="utf-8") as f:
        json.dump({"doors": [dict(e, ids=None) for e in doors]}, f)
    with open(os.path.join(d, "formids.json"), "w", encoding="utf-8") as f:
        json.dump({"plugin": plugin, "doors": {e["src"]: e["ids"] for e in doors}}, f)


def door_entry(src="0EE661:Fallout4.esm", dest_id=0x804, ref="000802", cell="000801", arrival=0xA5E20):
    return {"src": src, "edid": "FO4Core_door_018c8b_fallout4", "model": "fo4core\\d.nif", "name": "Door",
            "destination": {"plugin": "FO4Port.esm", "id": dest_id, "ref": ref, "cell": cell, "door": "0EE5D6:Fallout4.esm",
                            "arrival": {"pos": [5.449, 17.291, -3.654], "rot": [0, 0, 4.7124]}},
            "arrival": {"pos": [-469.444, 636.074, 42.356], "rot": [0, 0, 2.5812], "cell": [-5, 6]},
            "ids": {"base": "0A7712", "ref": "02D22C", "arrival": f"{arrival:06X}"}}


class CodecTests(unittest.TestCase):
    def test_load_door_vmad_is_the_layout_mutagen_and_vanilla_use(self):
        self.assertEqual(vp.load_door_vmad("FO4Port.esm", 0x2339), REFERENCE)
        self.assertEqual(len(REFERENCE), 80)
        self.assertEqual(vp.load_door_destination(REFERENCE), ("FO4Port.esm", 0x2339))
        d = vp.decode(REFERENCE)
        self.assertEqual((d["version"], d["format"], len(d["scripts"])), (6, 2, 1))
        s = d["scripts"][0]
        self.assertEqual((s["name"], s["status"]), ("FO4SF_LoadDoor", vp.STATUS_LOCAL))
        self.assertEqual([(p["name"], p["type"], p["status"], p["value"]) for p in s["properties"]],
                         [("DestinationPlugin", 2, 1, "FO4Port.esm"), ("DestinationId", 3, 1, 0x2339)])
        self.assertEqual(vp.encode(d["scripts"]), REFERENCE)                     # decode -> encode round trip

    def test_every_written_type_round_trips(self):
        scripts = [{"name": "A", "status": 1, "properties": [
            {"name": "obj", "type": 1, "status": 1, "value": {"form": 0x01000802, "alias": -1}},
            {"name": "s", "type": 2, "status": 1, "value": "text"},
            {"name": "i", "type": 3, "status": 1, "value": -7},
            {"name": "f", "type": 4, "status": 1, "value": 1.5},
            {"name": "b", "type": 5, "status": 3, "value": True}]},
            {"name": "B", "status": 0, "properties": []}]
        back = vp.decode(vp.encode(scripts))
        self.assertEqual([s["name"] for s in back["scripts"]], ["A", "B"])
        got = [(p["name"], p["type"], p["status"], p["value"]) for p in back["scripts"][0]["properties"]]
        self.assertEqual(got[0], ("obj", 1, 1, {"unused": 0, "alias": -1, "form": 0x01000802}))
        self.assertEqual(got[1:], [("s", 2, 1, "text"), ("i", 3, 1, -7), ("f", 4, 1, 1.5), ("b", 5, 3, True)])
        # the vanilla example of the design pass: an int, an object (format 2) and another int, 101 bytes
        vanilla = bytes.fromhex("060002000100" "1800" + "DefaultRefOnTriggerEnter".encode().hex() + "01" "0300"
                                "0a00" + "StageToSet".encode().hex() + "0301" "32000000"
                                "1100" + "QuestToSetOrCheck".encode().hex() + "0101" "0000" "ffff" "9b1c2c00"
                                "0b00" + "PrereqStage".encode().hex() + "0301" "28000000")
        self.assertEqual(len(vanilla), 101)
        v = vp.decode(vanilla)
        self.assertEqual(v["scripts"][0]["status"], vp.STATUS_INHERITED)
        self.assertEqual([p["value"] for p in v["scripts"][0]["properties"]], [50, {"unused": 0, "alias": -1, "form": 0x002C1C9B}, 40])
        self.assertEqual(vp.encode(v["scripts"]), vanilla)
        with self.assertRaisesRegex(ValueError, "after the last property"):
            vp.decode(REFERENCE + b"\0")
        with self.assertRaisesRegex(ValueError, "not a plain file name"):
            vp.load_door_vmad("sub\\FO4Port.esm", 1)
        for bad in (0, -1, 0x01000000, "7"):
            with self.assertRaisesRegex(ValueError, "plugin-local id"):
                vp.load_door_vmad("FO4Port.esm", bad)
        with self.assertRaisesRegex(ValueError, "properties"):                  # another shape is not a load door
            vp.load_door_destination(vp.encode([{"name": "FO4SF_LoadDoor", "status": 0, "properties": [
                {"name": "DestinationId", "type": 3, "status": 1, "value": 5}]}]))
        with self.assertRaisesRegex(ValueError, "script"):
            vp.load_door_destination(vp.encode([{"name": "Other", "status": 0, "properties": []}]))


class PluginTreeTests(unittest.TestCase):
    def test_round_trip_and_lookups(self):
        raw = tiny_plugin()
        p = vp.Plugin(raw)
        self.assertEqual(p.serialize(), raw)
        self.assertEqual(p.masters(), ["Starfield.esm"])
        self.assertEqual(p.hedr()[1:], (4, 0x804))
        self.assertEqual(p.own_max(1), 0x803)
        recs = p.records()
        self.assertEqual(recs[OWN | 0x802][3], ((0, 0x4C4C4543), (2, 0), (3, 0), (6, OWN | 0x801), (9, OWN | 0x801)))
        self.assertEqual(recs[OWN | 0x800][0], b"STAT")
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "FO4Port.esm")
            with open(path, "wb") as f:
                f.write(raw)
            self.assertEqual(vp.next_local_id(path), 0x804)
            with open(path, "wb") as f:
                f.write(tiny_plugin(next_id=0x900))                            # HEDR disagrees with the records
            with self.assertRaisesRegex(ValueError, "HEDR next"):
                vp.next_local_id(path)
            self.assertEqual(vp.plugin_in(d), "FO4Port.esm")

    def test_set_vmad_and_add_persistent_ref(self):
        p = vp.Plugin(tiny_plugin())
        before = p.records()
        vm = vp.load_door_vmad("FO4TerrainCore.esm", 0xA5E20)
        r = p.set_vmad(OWN | 0x802, vm)
        self.assertEqual([s for s, _d in r.fields()], [b"VMAD", b"NAME", b"DATA"])   # vanilla: VMAD before NAME
        r2 = p.set_vmad(OWN | 0x803, vm)                                              # after EDID when there is one
        self.assertEqual([s for s, _d in r2.fields()], [b"EDID", b"VMAD", b"NAME", b"DATA"])
        p.set_vmad(OWN | 0x803, vm)                                                   # replacing, not doubling
        self.assertEqual(sum(1 for s, _d in p.find(OWN | 0x803)[2].fields() if s == b"VMAD"), 1)
        with self.assertRaisesRegex(ValueError, "not a REFR"):
            p.set_vmad(OWN | 0x800, vm)
        with self.assertRaisesRegex(ValueError, "persistent flag"):
            p.add_persistent_ref(OWN | 0x801, rec(b"REFR", OWN | 0x804, []))
        marker = vp.xmarker_ref(OWN | 0x804, [5.449, 17.291, -3.654], [0, 0, 4.7124])
        g = p.add_persistent_ref(OWN | 0x801, marker)
        self.assertEqual(g.gtype, vp.GROUP_PERSISTENT)
        children = p.cell_children(OWN | 0x801)
        self.assertEqual([c.gtype for c in children.children], [8, 9])             # persistent before temporary
        back = vp.Plugin(p.serialize())                                            # the sizes are right: it parses
        after = back.records()
        self.assertEqual(after[OWN | 0x804][3][-2:], ((6, OWN | 0x801), (8, OWN | 0x801)))
        self.assertEqual(after[OWN | 0x804][1] & vp.PERSISTENT, vp.PERSISTENT)
        self.assertEqual(after[OWN | 0x800], before[OWN | 0x800])
        self.assertEqual(after[OWN | 0x801], before[OWN | 0x801])
        self.assertEqual(vp.load_door_destination(dict(vp.Record(b"REFR" + bytes(20), after[OWN | 0x802][2]).fields())[b"VMAD"]),
                         ("FO4TerrainCore.esm", 0xA5E20))
        p.add_persistent_ref(OWN | 0x801, vp.xmarker_ref(OWN | 0x805, [0, 0, 0], [0, 0, 0]))   # the group is reused
        self.assertEqual(len(p.cell_children(OWN | 0x801).children), 2)
        with self.assertRaises(KeyError):
            p.cell_children(OWN | 0x777)


class PortPassTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.port = os.path.join(self.tmp.name, "integ")
        os.makedirs(os.path.join(self.port, "meshes"))
        with open(os.path.join(self.port, "FO4Port.esm"), "wb") as f:
            f.write(tiny_plugin())
        with open(os.path.join(self.port, "meshes", "a.nif"), "wb") as f:
            f.write(b"nif")
        with open(os.path.join(self.port, "formids.json"), "w", encoding="utf-8") as f:
            json.dump({"STAT:FO4Port_door02": 0x800, "CELL:FO4Port_Test": 0x801,
                       "REFR:FO4Port_Test:0EE5D6:Fallout4.esm": 0x802, "REFR:FO4Port_Test:000001:Fallout4.esm": 0x803}, f)
        self.core = os.path.join(self.tmp.name, "core")
        core_folder(self.core, [door_entry()])
        self.out = os.path.join(self.tmp.name, "integ_doors")

    def tearDown(self):
        self.tmp.cleanup()

    def test_port_patches_the_door_and_adds_the_marker_and_check_passes(self):
        self.assertEqual(vp.main(["port", "--port", self.port, "--core", self.core, "--out", self.out]), 0)
        self.assertEqual(vp.main(["check", "--port", self.port, "--out", self.out]), 0)
        with open(os.path.join(self.out, "doors_check.json"), encoding="utf-8") as f:
            rep = json.load(f)
        self.assertTrue(rep["pass"], rep["checks"])
        self.assertEqual(rep["records_after"], rep["records_before"] + 1)
        with open(os.path.join(self.out, "formids.json"), encoding="utf-8") as f:
            ids = json.load(f)
        self.assertEqual(ids["MARK:FO4Port_Test:0EE661:Fallout4.esm"], 0x804)
        self.assertEqual(ids["REFR:FO4Port_Test:0EE5D6:Fallout4.esm"], 0x802)   # the pinned keys stay
        self.assertTrue(os.path.isfile(os.path.join(self.out, "meshes", "a.nif")))  # the tree came along
        with open(os.path.join(self.port, "FO4Port.esm"), "rb") as f:
            self.assertEqual(f.read(), tiny_plugin())                          # the pinned plugin is untouched
        new = vp.Plugin.read(os.path.join(self.out, "FO4Port.esm"))
        door = new.find(OWN | 0x802)[2]
        self.assertEqual(dict(door.fields())[b"VMAD"], vp.load_door_vmad("FO4TerrainCore.esm", 0xA5E20))
        self.assertEqual(new.hedr()[1:], (5, 0x805))
        with open(os.path.join(self.out, "doors.json"), encoding="utf-8") as f:
            d = json.load(f)["doors"][0]
        self.assertEqual((d["interior_door"], d["marker"], d["cell_edid"]), ("000802", "000804", "FO4Port_Test"))
        # a second run refuses to touch the folder
        with self.assertRaises(SystemExit):
            vp.main(["port", "--port", self.port, "--core", self.core, "--out", self.out])

    def test_check_fails_when_another_record_changed_or_the_marker_is_wrong(self):
        self.assertEqual(vp.main(["port", "--port", self.port, "--core", self.core, "--out", self.out]), 0)
        before = vp.Plugin.read(os.path.join(self.port, "FO4Port.esm"))
        after = vp.Plugin.read(os.path.join(self.out, "FO4Port.esm"))
        _plugin, doors = vp.core_doors(self.core)
        self.assertTrue(all(ok for _w, ok in vp.check_port(before, after, doors, "FO4TerrainCore.esm")))
        wrong = vp.check_port(before, after, doors, "Other.esm")                     # the VMAD names another plugin
        self.assertFalse(all(ok for _w, ok in wrong))
        touched = vp.Plugin.read(os.path.join(self.out, "FO4Port.esm"))
        touched.set_vmad(OWN | 0x803, b"\x06\x00\x02\x00\x00\x00")                    # another REFR changed
        self.assertFalse(vp.check_port(before, touched, doors, "FO4TerrainCore.esm")[1][1])
        moved = vp.Plugin.read(os.path.join(self.out, "FO4Port.esm"))
        items, i, r = moved.find(OWN | 0x804)
        items[i] = r.with_fields([(b"NAME", struct.pack("<I", vp.XMARKER)), (b"DATA", struct.pack("<6f", 0, 0, 0, 0, 0, 0))])
        res = vp.check_port(before, moved, doors, "FO4TerrainCore.esm")
        self.assertFalse(all(ok for w, ok in res if "marker" in w))

    def test_refusals(self):
        # the cluster promised another marker id than the port allocates
        core_folder(self.core, [door_entry(dest_id=0x805)])
        with self.assertRaisesRegex(SystemExit, "promised marker id"):
            vp.main(["port", "--port", self.port, "--core", self.core, "--out", self.out])
        # the destination plugin is not this one
        e = door_entry()
        e["destination"]["plugin"] = "Other.esm"
        core_folder(self.core, [e])
        with self.assertRaisesRegex(SystemExit, "not FO4Port.esm"):
            vp.main(["port", "--port", self.port, "--core", self.core, "--out", self.out])
        # two doors on one interior door
        core_folder(self.core, [door_entry(), door_entry(src="0EED8A:Fallout4.esm", dest_id=0x805)])
        with self.assertRaisesRegex(SystemExit, "twice"):
            vp.main(["port", "--port", self.port, "--core", self.core, "--out", self.out])
        # ids without an arrival (a core build without the markers)
        e = door_entry()
        del e["ids"]["arrival"]
        core_folder(self.core, [e])
        with self.assertRaisesRegex(ValueError, "arrival"):
            vp.core_doors(self.core)
        self.assertFalse(os.path.exists(self.out))


if __name__ == "__main__":
    unittest.main()
