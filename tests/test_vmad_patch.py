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


def core_folder(d, doors, plugin="FO4TerrainCore.esm", target_cell=(-12, -27)):
    """A core build with doors: objects.json "doors" entries, formids.json "doors" ids, overlays_params.json with the
    overlay's planet_target_cell (the merge offset in cells) and a second overlay of another world."""
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "objects.json"), "w", encoding="utf-8") as f:
        json.dump({"world": "FO4Core_Commonwealth", "doors": [dict(e, ids=None) for e in doors]}, f)
    with open(os.path.join(d, "formids.json"), "w", encoding="utf-8") as f:
        json.dump({"plugin": plugin, "world": "FO4Core_Commonwealth", "doors": {e["src"]: e["ids"] for e in doors}}, f)
    with open(os.path.join(d, "overlays_params.json"), "w", encoding="utf-8") as f:
        json.dump({"plugin": plugin, "overlays": [{"world": "Other", "planet_target_cell": [3, 4]},
                                                  {"world": "FO4Core_Commonwealth", "planet_target_cell": list(target_cell)}]}, f)


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

    def test_destination_position_properties(self):
        """DestinationX / Y / Z: three edited float properties after the two of #272, each `uint16 length + name |
        04 (float) | 01 (edited) | f32`, then UseDestinationPosition (`uint16 length + name | 05 (bool) | 01 (edited) |
        01`): six properties; load_door_target reads the position back, the two-property door reads None."""
        vm = vp.load_door_vmad("FO4Port.esm", 0x2339, (5.449, 17.291, -3.654))
        tail = b"".join(struct.pack("<H", 12) + n.encode() + b"\x04\x01" + struct.pack("<f", v)
                        for n, v in (("DestinationX", 5.449), ("DestinationY", 17.291), ("DestinationZ", -3.654)))
        tail += struct.pack("<H", 22) + b"UseDestinationPosition" + b"\x05\x01\x01"
        head = bytearray(REFERENCE)
        head[6 + 2 + 14 + 1:6 + 2 + 14 + 3] = struct.pack("<H", 6)              # header, name, status: the count 2 -> 6
        self.assertEqual(vm, bytes(head) + tail)
        self.assertEqual(len(vm), 80 + 3 * (2 + 12 + 2 + 4) + (2 + 22 + 2 + 1))
        plugin, local_id, pos = vp.load_door_target(vm)
        self.assertEqual((plugin, local_id), ("FO4Port.esm", 0x2339))
        self.assertEqual(pos, tuple(struct.unpack("<3f", struct.pack("<3f", 5.449, 17.291, -3.654))))   # float32
        self.assertEqual(vp.load_door_destination(vm), ("FO4Port.esm", 0x2339))
        self.assertEqual(vp.load_door_target(REFERENCE), ("FO4Port.esm", 0x2339, None))
        d = vp.decode(vm)                                                         # the generic decoder
        self.assertEqual([(p["name"], p["type"], p["status"], p["value"] if p["type"] == 5 else None)
                          for p in d["scripts"][0]["properties"]][2:],
                         [("DestinationX", 4, 1, None), ("DestinationY", 4, 1, None), ("DestinationZ", 4, 1, None),
                          ("UseDestinationPosition", 5, 1, True)])
        self.assertEqual(len(d["scripts"][0]["properties"]), 6)
        self.assertEqual(vp.encode(d["scripts"]), vm)                             # decode -> encode round trip
        self.assertTrue(vp.same_position(pos, [5.449, 17.291, -3.654]))
        self.assertFalse(vp.same_position(pos, [5.449, 17.291, -3.644]))
        self.assertFalse(vp.same_position(None, [5.449, 17.291, -3.654]))
        for bad in ([1, 2], [1, 2, float("nan")], [1, 2, float("inf")], [1, 2, 1e39], 3.0, "abc"):
            with self.assertRaisesRegex(ValueError, "destination position"):
                vp.load_door_vmad("FO4Port.esm", 1, bad)

        def shape(props):
            return vp.encode([{"name": "FO4SF_LoadDoor", "status": 0, "properties": props}])
        good = vp.load_door_scripts("FO4Port.esm", 1, (1, 2, 3))[0]["properties"]
        self.assertEqual([p["name"] for p in good], ["DestinationPlugin", "DestinationId", "DestinationX", "DestinationY",
                                                     "DestinationZ", "UseDestinationPosition"])
        self.assertEqual(vp.load_door_target(shape(good)), ("FO4Port.esm", 1, (1.0, 2.0, 3.0)))
        for props in (good[:4] + [good[5]],                                       # Z missing
                      good[:2] + [good[3], good[2], good[4], good[5]],            # Y before X
                      good[:4] + [dict(good[4], type=3, value=3), good[5]],       # Z an int
                      good[:4] + [dict(good[4], status=0), good[5]],              # Z not edited
                      good[:5] + [dict(good[5], type=3, value=1)],                # the bool an int
                      good[:5] + [dict(good[5], status=0)],                       # the bool not edited
                      good[:5] + [dict(good[5], name="UseDestination")],          # another name
                      good + [dict(good[4], name="DestinationW")],                # one more
                      good[:2] + [good[5]],                                       # the bool alone
                      good[:2] + [good[5]] + good[2:5] + [good[5]]):              # the bool twice
            with self.assertRaisesRegex(ValueError, "properties"):
                vp.load_door_target(shape(props))
        with self.assertRaisesRegex(ValueError, "not finite"):
            vp.load_door_target(shape(good[:4] + [dict(good[4], value=float("nan")), good[5]]))

    def test_the_position_needs_its_opt_in(self):
        """The script ignores DestinationX / Y / Z unless UseDestinationPosition is true: a VMAD with the floats and no
        bool (the writer of 2026-10-17 before this change) or a false bool is refused, not read as a position; the
        two-property door stays readable; the script's own declaration order (the bool first) is read too."""
        def shape(props):
            return vp.encode([{"name": "FO4SF_LoadDoor", "status": 0, "properties": props}])
        good = vp.load_door_scripts("FO4Port.esm", 0x2339, (5.449, 17.291, -3.654))[0]["properties"]
        want = ("FO4Port.esm", 0x2339, tuple(struct.unpack("<3f", struct.pack("<3f", 5.449, 17.291, -3.654))))
        self.assertEqual(vp.load_door_target(shape(good)), want)
        self.assertEqual(vp.load_door_target(shape(good[:2] + [good[5]] + good[2:5])), want)      # bool, then X Y Z
        self.assertEqual(vp.load_door_target(REFERENCE), ("FO4Port.esm", 0x2339, None))             # two properties
        with self.assertRaisesRegex(ValueError, "without UseDestinationPosition"):                   # five: no bool
            vp.load_door_target(shape(good[:5]))
        with self.assertRaisesRegex(ValueError, "UseDestinationPosition is false"):
            vp.load_door_target(shape(good[:5] + [dict(good[5], value=False)]))
        with self.assertRaisesRegex(ValueError, "UseDestinationPosition is false"):
            vp.load_door_target(shape(good[:2] + [dict(good[5], value=False)] + good[2:5]))
        for pos in ((0.0, 0.0, 0.0), (1.0, 0.0, -0.0)):                       # zero is a coordinate: the bool decides
            self.assertEqual(vp.load_door_target(vp.load_door_vmad("FO4Port.esm", 1, pos))[2], pos)
        no_bool = shape(good[:5])
        self.assertEqual(vp.decode(no_bool)["scripts"][0]["properties"][4]["name"], "DestinationZ")   # still decodes
        self.assertEqual(vp.load_door_vmad("FO4Port.esm", 0x2339, (5.449, 17.291, -3.654)), shape(good))

    def test_property_names_and_types_are_the_scripts_declarations(self):
        """The VMAD names and types are those FO4SF_LoadDoor.psc declares (Papyrus binds a VMAD property by name and
        type). The psc of PR #291 declares the bool before the three floats; this writer puts it sixth, after
        DestinationZ, which the reader accepts as it does the declared order. A psc that predates #291 (no
        UseDestinationPosition / DestinationX..Z yet) skips the check of those four."""
        import re
        with open(os.path.join(ROOT, "scripts", "door_bridge", "FO4SF_LoadDoor.psc"), encoding="utf-8") as f:
            source = re.sub(r";[^\r\n]*", "", f.read())
        declared = {m[1]: m[0].lower() for m in re.findall(r"(?m)^\s*(string|int|float|bool)\s+Property\s+(\w+)", source)}
        types = {2: "string", 3: "int", 4: "float", 5: "bool"}
        written = {p["name"]: types[p["type"]]
                   for p in vp.load_door_scripts("FO4Port.esm", 1, (1, 2, 3))[0]["properties"]}
        self.assertEqual(list(written), [vp.PROP_PLUGIN, vp.PROP_ID, *vp.PROP_POSITION, vp.PROP_USE_POSITION])
        for name, kind in written.items():
            if name in declared:
                self.assertEqual(declared[name], kind, name)
        self.assertEqual({n: declared[n] for n in (vp.PROP_PLUGIN, vp.PROP_ID)},
                         {"DestinationPlugin": "string", "DestinationId": "int"})
        missing = [n for n in written if n not in declared]
        if missing:
            self.skipTest(f"scripts/door_bridge/FO4SF_LoadDoor.psc here does not declare {missing} yet (PR #291)")

    def test_merge_offset_from_overlays_params(self):
        with tempfile.TemporaryDirectory() as d:
            core_folder(d, [door_entry()])
            self.assertEqual(vp.merge_offset(d), (-1200.0, -2700.0, 0.0))        # planet_target_cell [-12, -27] x 100 m
            self.assertEqual(vp.merged([-469.444, 636.074, 42.356], (-1200.0, -2700.0, 0.0)),
                             [-469.444 - 1200.0, 636.074 - 2700.0, 42.356])
            core_folder(d, [door_entry()], target_cell=(-11, -27))              # an offset nobody measured
            with self.assertRaisesRegex(ValueError, "not the measured"):
                vp.merge_offset(d)
            with open(os.path.join(d, "overlays_params.json"), "w", encoding="utf-8") as f:
                json.dump({"overlays": [{"world": "FO4Core_Commonwealth"}]}, f)
            with self.assertRaisesRegex(ValueError, "no planet_target_cell"):
                vp.merge_offset(d)
            with open(os.path.join(d, "overlays_params.json"), "w", encoding="utf-8") as f:
                json.dump({"overlays": [{"world": "Elsewhere", "planet_target_cell": [-12, -27]}]}, f)
            with self.assertRaisesRegex(ValueError, "0 overlay"):
                vp.merge_offset(d)


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
        back = [-469.444 - 1200.0, 636.074 - 2700.0, 42.356]                   # the exterior marker, merged
        self.assertEqual(dict(door.fields())[b"VMAD"], vp.load_door_vmad("FO4TerrainCore.esm", 0xA5E20, back))
        plugin, local_id, pos = vp.load_door_target(dict(door.fields())[b"VMAD"])
        self.assertEqual((plugin, local_id), ("FO4TerrainCore.esm", 0xA5E20))
        self.assertTrue(vp.same_position(pos, back, 1e-4))
        self.assertEqual(new.hedr()[1:], (5, 0x805))
        with open(os.path.join(self.out, "doors.json"), encoding="utf-8") as f:
            rep = json.load(f)
        d = rep["doors"][0]
        self.assertEqual((d["interior_door"], d["marker"], d["cell_edid"]), ("000802", "000804", "FO4Port_Test"))
        self.assertEqual(rep["merge_offset"], [-1200.0, -2700.0, 0.0])
        self.assertEqual(d["return_destination"], {"plugin": "FO4TerrainCore.esm", "id": "0A5E20",
                                                   "local": [-469.444, 636.074, 42.356], "merged": back})
        # a second run refuses to touch the folder
        with self.assertRaises(SystemExit):
            vp.main(["port", "--port", self.port, "--core", self.core, "--out", self.out])

    def test_check_fails_when_another_record_changed_or_the_marker_is_wrong(self):
        self.assertEqual(vp.main(["port", "--port", self.port, "--core", self.core, "--out", self.out]), 0)
        before = vp.Plugin.read(os.path.join(self.port, "FO4Port.esm"))
        after = vp.Plugin.read(os.path.join(self.out, "FO4Port.esm"))
        _plugin, doors = vp.core_doors(self.core)
        merge = vp.MERGE_MEASURED
        self.assertTrue(all(ok for _w, ok in vp.check_port(before, after, doors, "FO4TerrainCore.esm", merge)))
        wrong = vp.check_port(before, after, doors, "Other.esm", merge)              # the VMAD names another plugin
        self.assertFalse(all(ok for _w, ok in wrong))
        unmerged = vp.check_port(before, after, doors, "FO4TerrainCore.esm", (0.0, 0.0, 0.0))   # the local position
        self.assertEqual([w.split(":")[0] for w, ok in unmerged if not ok], ["0EE661"])
        touched = vp.Plugin.read(os.path.join(self.out, "FO4Port.esm"))
        touched.set_vmad(OWN | 0x803, b"\x06\x00\x02\x00\x00\x00")                    # another REFR changed
        self.assertFalse(vp.check_port(before, touched, doors, "FO4TerrainCore.esm", merge)[1][1])
        old_shape = vp.Plugin.read(os.path.join(self.out, "FO4Port.esm"))             # the door VMAD of #272: no position
        old_shape.set_vmad(OWN | 0x802, vp.load_door_vmad("FO4TerrainCore.esm", 0xA5E20))
        for m in (merge, None):
            res = vp.check_port(before, old_shape, doors, "FO4TerrainCore.esm", m)
            self.assertEqual([ok for w, ok in res if "VMAD FO4SF_LoadDoor" in w], [False])
        back = vp.merged([-469.444, 636.074, 42.356], merge)
        props = vp.load_door_scripts("FO4TerrainCore.esm", 0xA5E20, back)[0]["properties"]
        for what, kept in (("floats without the bool (the writer before UseDestinationPosition)", props[:5]),
                           ("a false bool", props[:5] + [dict(props[5], value=False)])):
            five = vp.Plugin.read(os.path.join(self.out, "FO4Port.esm"))
            five.set_vmad(OWN | 0x802, vp.encode([{"name": vp.SCRIPT, "status": vp.STATUS_LOCAL, "properties": kept}]))
            for m in (merge, None):
                res = vp.check_port(before, five, doors, "FO4TerrainCore.esm", m)
                self.assertEqual([ok for w, ok in res if "VMAD FO4SF_LoadDoor" in w], [False], what)
                self.assertTrue(all(ok for w, ok in res if "VMAD FO4SF_LoadDoor" not in w), what)
        self.assertIn("UseDestinationPosition true", [w for w, ok in vp.check_port(before, after, doors, "FO4TerrainCore.esm", merge)
                                                      if "VMAD FO4SF_LoadDoor" in w][0])
        moved = vp.Plugin.read(os.path.join(self.out, "FO4Port.esm"))
        items, i, r = moved.find(OWN | 0x804)
        items[i] = r.with_fields([(b"NAME", struct.pack("<I", vp.XMARKER)), (b"DATA", struct.pack("<6f", 0, 0, 0, 0, 0, 0))])
        res = vp.check_port(before, moved, doors, "FO4TerrainCore.esm", merge)
        self.assertFalse(all(ok for w, ok in res if "marker" in w))

    def test_keep_markers_reapplies_the_doors_to_a_grown_port(self):
        # the first doors build (marker 0x804), then a later port that grew (a REFR at 0x806, next 0x807) and kept every
        # earlier id; --keep-markers puts the marker back at 0x804, below the grown plugin's next id
        self.assertEqual(vp.main(["port", "--port", self.port, "--core", self.core, "--out", self.out]), 0)
        grown = os.path.join(self.tmp.name, "grown")
        os.makedirs(grown)
        extra = rec(b"REFR", OWN | 0x806, [(b"NAME", struct.pack("<I", OWN | 0x800)), (b"DATA", struct.pack("<6f", 9, 9, 9, 0, 0, 0))])
        with open(os.path.join(grown, "FO4Port.esm"), "wb") as f:
            f.write(tiny_plugin(next_id=0x807, extra=[extra]))
        with open(os.path.join(self.out, "formids.json"), encoding="utf-8") as f:
            ids = json.load(f)
        ids["REFR:FO4Port_Test:000099:Fallout4.esm"] = 0x806
        with open(os.path.join(grown, "formids.json"), "w", encoding="utf-8") as f:
            json.dump(ids, f)
        kept = os.path.join(self.out, "doors.json")
        out2 = os.path.join(self.tmp.name, "grown_doors")
        with self.assertRaisesRegex(SystemExit, "promised marker id"):        # without --keep-markers: next + k = 0x807
            vp.main(["port", "--port", grown, "--core", self.core, "--out", out2])
        self.assertEqual(vp.main(["port", "--port", grown, "--core", self.core, "--out", out2, "--keep-markers", kept]), 0)
        self.assertEqual(vp.main(["check", "--port", grown, "--out", out2]), 0)
        new = vp.Plugin.read(os.path.join(out2, "FO4Port.esm"))
        self.assertEqual(new.hedr()[1:], (6, 0x807))
        self.assertEqual(new.find(OWN | 0x804)[2].sig, b"REFR")
        with open(os.path.join(out2, "formids.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f)["MARK:FO4Port_Test:0EE661:Fallout4.esm"], 0x804)
        # a kept id a record of the grown plugin already uses is refused
        clash = os.path.join(self.tmp.name, "clash")
        os.makedirs(clash)
        taken = rec(b"REFR", OWN | 0x804, [(b"NAME", struct.pack("<I", OWN | 0x800)), (b"DATA", struct.pack("<6f", 0, 0, 0, 0, 0, 0))])
        with open(os.path.join(clash, "FO4Port.esm"), "wb") as f:
            f.write(tiny_plugin(extra=[taken]))
        with open(os.path.join(clash, "formids.json"), "w", encoding="utf-8") as f:
            json.dump(ids, f)
        with self.assertRaisesRegex(SystemExit, "already used"):
            vp.main(["port", "--port", clash, "--core", self.core, "--out", os.path.join(self.tmp.name, "c2"), "--keep-markers", kept])
        # the core promising another id than the kept build is refused
        core_folder(self.core, [door_entry(dest_id=0x805)])
        with self.assertRaisesRegex(SystemExit, "kept doors build has 000804"):
            vp.main(["port", "--port", grown, "--core", self.core, "--out", os.path.join(self.tmp.name, "c3"), "--keep-markers", kept])

    def test_decode_prints_the_destination(self):
        self.assertEqual(vp.main(["port", "--port", self.port, "--core", self.core, "--out", self.out]), 0)
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(vp.main(["decode", os.path.join(self.out, "FO4Port.esm"), "000802"]), 0)
        text = buf.getvalue()
        self.assertIn("FO4SF_LoadDoor: DestinationPlugin FO4TerrainCore.esm, DestinationId 679456 (0x0A5E20), DestinationX "
                      f"{struct.unpack('<f', struct.pack('<f', -469.444 - 1200.0))[0]!r}", text)
        self.assertIn('"name": "DestinationZ"', text)
        self.assertIn('"name": "UseDestinationPosition"', text)
        self.assertRegex(text, r"DestinationZ 42\.35\d+, UseDestinationPosition True")

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
        # a core build whose overlay merges elsewhere than the measured offset
        core_folder(self.core, [door_entry()], target_cell=(-12, -26))
        with self.assertRaisesRegex(SystemExit, "not the measured"):
            vp.main(["port", "--port", self.port, "--core", self.core, "--out", self.out])
        self.assertFalse(os.path.exists(self.out))


if __name__ == "__main__":
    unittest.main()
