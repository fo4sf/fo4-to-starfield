"""scripts/terrain/vmad_patch.py: the Starfield REFR VMAD layout (encode / decode round trip against the bytes the design
pass dumped from Starfield.esm and from Mutagen), the record-level patch of a synthetic plugin (sizes of the record and
of every enclosing GRUP, nothing else moved) and its check."""
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "terrain"))
sys.path.insert(0, str(ROOT / "src"))
import vmad_patch as vp  # noqa: E402

# Mutagen 0.55.0-alpha.67's VMAD for the scripted door (design pass, C:\Modding\scratch\doorspec: 80 bytes)
MUTAGEN = (bytes.fromhex("060002000100") + bytes.fromhex("0e00") + b"FO4SF_LoadDoor" + bytes.fromhex("000200")
           + bytes.fromhex("1100") + b"DestinationPlugin" + bytes.fromhex("0201") + bytes.fromhex("0b00") + b"FO4Port.esm"
           + bytes.fromhex("0d00") + b"DestinationId" + bytes.fromhex("0301") + bytes.fromhex("39230000"))
# Starfield.esm temporary REFR 001FDD1E MQ105SetStage50Trigger001 (101 bytes): Inherited script, int + object + int
VANILLA = bytes.fromhex("060002000100180044656661756c745265664f6e54726967676572456e7465720103000a005374616765546f536574"
                        "03013200000011005175657374546f5365744f72436865636b01010000ffff9b1c2c000b005072657265715374616765"
                        "030128000000")


def rec(sig, fid, fields, flags=0):
    data = b"".join(s + struct.pack("<H", len(d)) + d for s, d in fields)
    return sig + struct.pack("<IIIHHHH", len(data), flags, fid, 0, 0, 0x240, 0) + data


def grp(label, gtype, body):
    return b"GRUP" + struct.pack("<I", 24 + len(body)) + label + struct.pack("<iHHHH", gtype, 0, 0, 0, 0) + body


def plugin(door_fields=None):
    """TES4 + a CELL top group holding one interior block / subblock / cell with a temporary children group of three
    REFRs (the middle one is the door), as FO4Port.esm nests them."""
    tes4 = rec(b"TES4", 0, [(b"HEDR", struct.pack("<fII", 0.96, 7, 0x804)), (b"MAST", b"Starfield.esm\0")])
    refr = lambda fid, extra=(): rec(b"REFR", fid, list(extra) + [(b"NAME", struct.pack("<I", 0x01000801)),
                                                                     (b"DATA", struct.pack("<6f", 1, 2, 3, 0, 0, 1.5))])
    temp = grp(struct.pack("<I", 0x01000802), 9, refr(0x01000803) + refr(0x01000804, door_fields or ()) + refr(0x01000805))
    cell = rec(b"CELL", 0x01000802, [(b"EDID", b"Cell\0"), (b"DATA", b"\1\0")])
    children = grp(struct.pack("<I", 0x01000802), 6, temp)
    sub = grp(struct.pack("<I", 0), 3, cell + children)
    block = grp(struct.pack("<I", 0), 2, sub)
    top = grp(b"CELL", 0, block)
    acti = grp(b"ACTI", 0, rec(b"ACTI", 0x01000801, [(b"EDID", b"Base\0")]))
    return tes4 + acti + top


class CodecTests(unittest.TestCase):
    def test_encoder_writes_the_mutagen_bytes(self):
        self.assertEqual(vp.load_door_vmad("FO4SF_LoadDoor", "DestinationPlugin", "FO4Port.esm", "DestinationId", 0x2339), MUTAGEN)
        self.assertEqual(vp.decode(MUTAGEN), {"version": 6, "object_format": 2, "scripts": [
            {"name": "FO4SF_LoadDoor", "status": 0, "properties": [
                {"name": "DestinationPlugin", "type": 2, "status": 1, "value": "FO4Port.esm"},
                {"name": "DestinationId", "type": 3, "status": 1, "value": 0x2339}]}]})
        self.assertEqual(vp.door_properties(MUTAGEN, "FO4SF_LoadDoor", "DestinationPlugin", "DestinationId"),
                         (("FO4Port.esm", 0x2339), ""))

    def test_vanilla_round_trip(self):
        v = vp.decode(VANILLA)
        self.assertEqual(v["scripts"][0]["name"], "DefaultRefOnTriggerEnter")
        self.assertEqual(v["scripts"][0]["status"], 1)
        self.assertEqual([p["type"] for p in v["scripts"][0]["properties"]], [3, 1, 3])
        self.assertEqual(v["scripts"][0]["properties"][1]["value"], {"unused": 0, "alias": -1, "formid": 0x2C1C9B})
        scripts = [{"name": s["name"], "status": s["status"], "properties": [
            dict(p, value=p["value"]["formid"] if p["type"] == 1 else p["value"]) for p in s["properties"]]}
            for s in v["scripts"]]
        self.assertEqual(vp.encode(scripts), VANILLA)
        self.assertIsNone(vp.door_properties(VANILLA, "FO4SF_LoadDoor", "DestinationPlugin", "DestinationId")[0])

    def test_other_property_types_and_refusals(self):
        scripts = [{"name": "S", "properties": [{"name": "f", "type": "float", "value": 1.5},
                                                {"name": "b", "type": "bool", "value": True},
                                                {"name": "ints", "type": 13, "value": [1, 2]},
                                                {"name": "strs", "type": 12, "value": ["a", "bc"]}]}]
        back = vp.decode(vp.encode(scripts))["scripts"][0]["properties"]
        self.assertEqual([p["value"] for p in back], [1.5, True, [1, 2], ["a", "bc"]])
        with self.assertRaises(ValueError):
            vp.decode(MUTAGEN + b"\0")                                     # trailing bytes
        with self.assertRaises(ValueError):
            vp.decode(struct.pack("<hHH", 6, 1, 0))                        # object format 1
        for bad in (0, 0x1000000, "7D0B"):
            with self.assertRaises((ValueError, TypeError)):
                vp.load_door_vmad("FO4SF_LoadDoor", "DestinationPlugin", "FO4Port.esm", "DestinationId", bad)
        with self.assertRaises(ValueError):
            vp.load_door_vmad("FO4SF_LoadDoor", "DestinationPlugin", "FO4Port", "DestinationId", 5)
        wrong = vp.load_door_vmad("Other", "DestinationPlugin", "FO4Port.esm", "DestinationId", 5)
        self.assertIn("expected one Local", vp.door_properties(wrong, "FO4SF_LoadDoor", "DestinationPlugin", "DestinationId")[1])


class PatchTests(unittest.TestCase):
    def test_patch_grows_record_and_enclosing_groups_only(self):
        old = plugin()
        new, info = vp.patch(old, 0x000804, MUTAGEN)
        self.assertEqual(info["delta"], 6 + len(MUTAGEN))
        self.assertEqual(len(new), len(old) + info["delta"])
        self.assertEqual(len(info["groups"]), 5)                                # CELL top, block, subblock, children, temporary
        self.assertEqual(vp.check(old, new, [0x804]), [])
        self.assertEqual(vp.refr_vmad(new, 0x804), MUTAGEN)
        self.assertIsNone(vp.refr_vmad(new, 0x803))
        recs, _groups = vp.records_by_id(new)
        self.assertEqual([s for s, _ in recs[0x01000804][3]], [b"VMAD", b"NAME", b"DATA"])   # VMAD first, as vanilla
        self.assertEqual(recs[0x01000803], vp.records_by_id(old)[0][0x01000803])
        # every untouched byte region is the same, shifted by the insert after the record
        off = info["offset"]
        self.assertEqual(new[off + 24 + info["new_size"]:], old[off + 24 + info["old_size"]:])
        # replacing an existing VMAD keeps one, and an EDID stays in front of it
        old2 = plugin(door_fields=[(b"EDID", b"Door\0"), (b"VMAD", b"\6\0\2\0\0\0")])
        new2, _ = vp.patch(old2, 0x804, MUTAGEN)
        self.assertEqual([s for s, _ in vp.records_by_id(new2)[0][0x01000804][3]], [b"EDID", b"VMAD", b"NAME", b"DATA"])
        self.assertEqual(vp.check(old2, new2, [0x804]), [])

    def test_check_sees_any_other_change(self):
        old = plugin()
        new, _ = vp.patch(old, 0x804, MUTAGEN)
        other, _ = vp.patch(old, 0x803, MUTAGEN)
        self.assertTrue(any("00803" in p for p in vp.check(old, other, [0x804])))
        tampered = bytearray(new)
        tampered[-1] ^= 1                                                       # the last REFR's DATA
        self.assertTrue(vp.check(old, bytes(tampered), [0x804]))
        self.assertTrue(vp.check(old, old, [0x804]))                            # no VMAD at all
        with self.assertRaises(KeyError):
            vp.patch(old, 0x999, MUTAGEN)
        with self.assertRaises(ValueError):
            vp.patch(old, 0x801, MUTAGEN)                                       # an ACTI, not a REFR

    def test_cli_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            src, out = os.path.join(d, "in.esm"), os.path.join(d, "out.esm")
            with open(src, "wb") as f:
                f.write(plugin())
            self.assertEqual(vp.main(["apply", "--plugin", src, "--out", out, "--ref", "000804", "--script", "FO4SF_LoadDoor",
                                      "--string", "DestinationPlugin=FO4Port.esm", "--int", "DestinationId=0x2339"]), 0)
            self.assertEqual(vp.refr_vmad(open(out, "rb").read(), 0x804), MUTAGEN)
            self.assertEqual(vp.main(["check", "--old", src, "--new", out, "--ref", "000804"]), 0)
            self.assertEqual(vp.main(["dump", "--plugin", out, "--ref", "000804"]), 0)
            with self.assertRaises(SystemExit):
                vp.main(["apply", "--plugin", src, "--out", out, "--ref", "000804", "--script", "S"])   # out exists


if __name__ == "__main__":
    unittest.main()
