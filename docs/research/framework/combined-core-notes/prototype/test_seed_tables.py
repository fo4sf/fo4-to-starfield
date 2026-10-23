"""Synthetic-plugin tests for seed_tables.py. Editor ids below are invented fixtures."""
import json
import os
import struct
import tempfile
import unittest
import zlib

import seed_tables


def sub(sig, data):
    return sig + struct.pack("<H", len(data)) + data


def rec(typ, fid, fields, compress=False):
    data = b"".join(fields)
    flags = 0
    if compress:
        data = struct.pack("<I", len(data)) + zlib.compress(data)
        flags = seed_tables.COMPRESSED
    return typ + struct.pack("<III", len(data), flags, fid) + b"\0" * 8 + data


def grup(label, records):
    body = b"".join(records)
    return b"GRUP" + struct.pack("<I", 24 + len(body)) + label + struct.pack("<i", 0) + b"\0" * 8 + body


def edid(s):
    return sub(b"EDID", s.encode() + b"\0")


def plugin(path, masters, groups):
    hdr = b"".join(sub(b"MAST", m.encode() + b"\0") + sub(b"DATA", b"\0" * 8) for m in masters)
    with open(path, "wb") as f:
        f.write(rec(b"TES4", 0, [hdr]) + b"".join(groups))


class SeedTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.base = os.path.join(self.dir, "Base.esm")
        plugin(self.base, [], [
            grup(b"KYWD", [rec(b"KYWD", 0x10, [edid("TestKwSettlement")]),
                           rec(b"KYWD", 0x11, [edid("TestKwRaider")])]),
            grup(b"LCRT", [rec(b"LCRT", 0x20, [edid("TestWorkshopRefType")])]),
            grup(b"FACT", [
                rec(b"FACT", 0x30, [edid("TestSettlers"), sub(b"XNAM", struct.pack("<IiI", 0x31, 0, 1))]),
                rec(b"FACT", 0x31, [edid("TestRaiders"), sub(b"XNAM", struct.pack("<IiI", 0x30, 0, 1))]),
            ]),
            grup(b"LCTN", [
                rec(b"LCTN", 0x40, [edid("TestRegion")]),
                rec(b"LCTN", 0x41, [edid("TestFarm"),
                                    sub(b"LCSR", struct.pack("<IIIhh", 0x20, 0x99, 0x98, 1, 2)),
                                    sub(b"PNAM", struct.pack("<I", 0x40)),
                                    sub(b"MNAM", struct.pack("<I", 0x97))], compress=True),
                rec(b"LCTN", 0x42, [edid("TestCamp"), sub(b"KSIZ", struct.pack("<I", 1)),
                                    sub(b"KWDA", struct.pack("<I", 0x11)),
                                    sub(b"PNAM", struct.pack("<I", 0x40))]),
            ]),
        ])
        self.dlc = os.path.join(self.dir, "Dlc.esm")
        plugin(self.dlc, ["Base.esm"], [grup(b"LCTN", [
            rec(b"LCTN", 0x01000050, [edid("TestDlcTown"), sub(b"KSIZ", struct.pack("<I", 1)),
                                      sub(b"KWDA", struct.pack("<I", 0x00000010)),
                                      sub(b"PNAM", struct.pack("<I", 0x00000040))]),
        ])])

    def pack(self):
        return seed_tables.build(*seed_tables.read([self.base, self.dlc]))

    def test_places_regions_and_kinds(self):
        pack, report = self.pack()
        by = {p["id"]: p for p in pack["places"]}
        self.assertEqual(by["TestFarm"]["kind"], "settlement")           # by ref type
        self.assertEqual(by["TestDlcTown"]["kind"], "settlement")        # by keyword, across plugins
        self.assertEqual(by["TestCamp"]["kind"], "landmark")
        self.assertEqual(by["TestCamp"]["faction_hints"], ["TestKwRaider"])
        self.assertEqual(by["TestDlcTown"]["region"], "TestRegion")
        self.assertTrue(by["TestFarm"]["has_marker"])
        self.assertEqual(report["settlement_candidates"], 2)
        self.assertEqual(report["location_ref_types"], {"TestWorkshopRefType": 1})

    def test_factions_and_relations(self):
        pack, _ = self.pack()
        by = {f["id"]: f for f in pack["factions"]}
        self.assertEqual(by["TestSettlers"]["relations"]["TestRaiders"]["reaction"], "enemy")

    def test_main_writes_files(self):
        out = os.path.join(self.dir, "out")
        self.assertEqual(seed_tables.main(["x", out, self.base, self.dlc]), 0)
        with open(os.path.join(out, "commonwealth_seed.draft.json")) as f:
            self.assertEqual(len(json.load(f)["places"]), 4)


if __name__ == "__main__":
    unittest.main()
