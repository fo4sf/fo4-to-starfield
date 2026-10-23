"""Combined core seed reader on synthetic plugins built in bytes; editor ids are invented, never game data."""
import json
import os
import shutil
import struct
import sys
import tempfile
import unittest
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from fo4sf.combined import pack, seed  # noqa: E402


def sub(sig, data):
    return sig + struct.pack("<H", len(data)) + data


def rec(typ, fid, fields, compress=False, flags=0):
    data = b"".join(fields)
    if compress:
        data = struct.pack("<I", len(data)) + zlib.compress(data)
        flags |= seed.COMPRESSED
    return typ + struct.pack("<III", len(data), flags, fid) + b"\0" * 8 + data


def grup(label, records, gtype=0):
    body = b"".join(records)
    return b"GRUP" + struct.pack("<I", 24 + len(body)) + label + struct.pack("<i", gtype) + b"\0" * 8 + body


def edid(s):
    return sub(b"EDID", s.encode() + b"\0")


def u32(*v):
    return struct.pack(f"<{len(v)}I", *v)


def keywords(*fids):
    return sub(b"KSIZ", u32(len(fids))) + sub(b"KWDA", u32(*fids))


def special_ref(lcrt, ref=0x99, cell=0x98, y=1, x=2):
    return struct.pack("<IIIhh", lcrt, ref, cell, y, x)


def plugin(path, masters, groups):
    hdr = b"".join(sub(b"MAST", m.encode() + b"\0") + sub(b"DATA", b"\0" * 8) for m in masters)
    with open(path, "wb") as f:
        f.write(rec(b"TES4", 0, [hdr]) + b"".join(groups))


class SeedTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.base = os.path.join(self.dir, "Base.esm")
        plugin(self.base, [], [
            grup(b"KYWD", [rec(b"KYWD", 0x10, [edid("TestKwSettlement")]),
                           rec(b"KYWD", 0x11, [edid("TestKwRaider")])]),
            grup(b"LCRT", [rec(b"LCRT", 0x20, [edid("TestWorkshopRefType")])]),
            # a group the reader must skip whole, with a nested child group inside it
            grup(b"CELL", [grup(b"\0\0\0\0", [rec(b"REFR", 0x70, [edid("TestRefr")])], gtype=6)]),
            grup(b"FACT", [
                rec(b"FACT", 0x30, [edid("TestSettlers"), sub(b"XNAM", struct.pack("<IiI", 0x31, 0, 1)),
                                    sub(b"XNAM", struct.pack("<IiI", 0x32, 5, 3))]),
                rec(b"FACT", 0x31, [edid("TestRaiders"), sub(b"XNAM", struct.pack("<IiI", 0x30, 0, 1))]),
                rec(b"FACT", 0x32, [edid("TestOrder")]),
            ]),
            grup(b"LCTN", [
                rec(b"LCTN", 0x40, [edid("TestRegion")]),
                rec(b"LCTN", 0x41, [edid("TestFarm"), sub(b"LCSR", special_ref(0x20)),
                                    sub(b"PNAM", u32(0x40)), sub(b"MNAM", u32(0x97))], compress=True),
                rec(b"LCTN", 0x42, [edid("TestCamp"), keywords(0x11), sub(b"PNAM", u32(0x40))]),
                rec(b"LCTN", 0x43, [edid("TestRuin"), sub(b"PNAM", u32(0x42))]),
                rec(b"LCTN", 0x44, [edid("TestGone")], flags=seed.DELETED),
            ]),
        ])
        self.dlc = os.path.join(self.dir, "Dlc.esm")
        plugin(self.dlc, ["Base.esm"], [grup(b"LCTN", [
            rec(b"LCTN", 0x01000050, [edid("TestDlcTown"), keywords(0x10), sub(b"PNAM", u32(0x40))]),
            # override of Base's TestCamp: a later plugin's record wins
            rec(b"LCTN", 0x00000042, [edid("TestCampRenamed"), sub(b"PNAM", u32(0x40))]),
        ])])

    def draft(self, *paths):
        return seed.build(seed.read(paths or [self.base, self.dlc]))

    def test_places_regions_and_kinds(self):
        draft, report = self.draft()
        by = {p["id"]: p for p in draft["places"]}
        self.assertEqual(by["TestFarm"]["kind"], "settlement")           # by ref type, compressed record
        self.assertEqual(by["TestDlcTown"]["kind"], "settlement")        # by keyword, across plugins
        self.assertEqual(by["TestRuin"]["kind"], "landmark")
        self.assertEqual(by["TestRuin"]["parent"], "TestCampRenamed")
        self.assertEqual(by["TestDlcTown"]["region"], "TestRegion")
        self.assertEqual(by["TestRuin"]["region"], "TestRegion")          # two levels up
        self.assertEqual(by["TestFarm"]["form"], "base.esm:000041")
        self.assertEqual(by["TestDlcTown"]["form"], "dlc.esm:000050")
        self.assertTrue(by["TestFarm"]["has_marker"])
        self.assertFalse(by["TestRuin"]["has_marker"])
        self.assertNotIn("TestGone", by)                                  # deleted record skipped
        self.assertNotIn("TestRefr", json.dumps(draft))                   # CELL tree skipped
        self.assertEqual(report["settlement_candidates"], 2)
        self.assertEqual(report["location_ref_types"], {"TestWorkshopRefType": 1})
        self.assertEqual(report["location_keywords"], {"TestKwSettlement": 1})
        self.assertEqual(report["overrides"], 1)
        self.assertEqual(report["compressed_records"], 1)
        self.assertEqual(report["record_counts"], {"KYWD": 2, "LCRT": 1, "FACT": 3, "LCTN": 6})
        self.assertEqual(report["problems"], {})

    def test_override_replaces_the_whole_record(self):
        draft, _ = self.draft()
        by = {p["id"]: p for p in draft["places"]}
        self.assertNotIn("TestCamp", by)
        self.assertEqual(by["TestCampRenamed"]["keywords"], [])          # the override dropped the keyword
        self.assertEqual(by["TestCampRenamed"]["kind"], "landmark")

    def test_later_plugin_deletion_removes_an_earlier_record(self):
        gone = os.path.join(self.dir, "Gone.esm")
        plugin(gone, ["Base.esm"], [
            grup(b"LCTN", [rec(b"LCTN", 0x00000041, [], flags=seed.DELETED)]),   # deletes Base's TestFarm
            grup(b"FACT", [rec(b"FACT", 0x00000030, [], flags=seed.DELETED)]),   # deletes Base's TestSettlers
        ])
        data = seed.read([self.base, self.dlc, gone])
        self.assertNotIn("base.esm:000041", data["locations"])
        self.assertNotIn("base.esm:000030", data["factions"])
        self.assertNotIn("base.esm:000041", data["names"])
        self.assertEqual(data["overrides"], 3)                           # TestCamp rename + two deletions
        self.assertEqual(data["deleted"], 3)                             # Base's own TestGone plus these two
        draft, report = seed.build(data)
        self.assertNotIn("TestFarm", {p["id"] for p in draft["places"]})
        self.assertNotIn("TestSettlers", {f["id"] for f in draft["factions"]})
        self.assertEqual(report["deleted_records"], 3)
        self.assertEqual(report["problems"], {})

    def test_faction_hint_makes_a_base_candidate(self):
        draft, report = self.draft(self.base)
        by = {p["id"]: p for p in draft["places"]}
        self.assertEqual(by["TestCamp"]["faction_hints"], ["TestKwRaider"])
        self.assertEqual(by["TestCamp"]["kind"], "base")
        self.assertEqual(report["base_candidates"], 1)

    def test_factions_and_relations(self):
        draft, _ = self.draft()
        by = {f["id"]: f for f in draft["factions"]}
        self.assertEqual(by["TestSettlers"]["relations"]["TestRaiders"], {"modifier": 0, "reaction": "enemy"})
        self.assertEqual(by["TestSettlers"]["relations"]["TestOrder"], {"modifier": 5, "reaction": "friend"})
        self.assertEqual(by["TestOrder"]["relations"], {})
        self.assertEqual(by["TestRaiders"]["form"], "base.esm:000031")

    def test_to_pack_fails_only_on_unfilled_homes(self):
        draft, _ = self.draft()
        p = seed.to_pack(draft)
        problems = pack.validate_pack(p)
        self.assertEqual(len(problems), 3)                                # one per faction, nothing else
        self.assertTrue(all("home" in x for x in problems), problems)
        self.assertEqual(pack.validate_pack({"places": p["places"]}), [])
        self.assertEqual(p["factions"][0]["relations"], {"TestOrder": 40, "TestRaiders": -80})
        for f in p["factions"]:
            f["home"], f["strength"] = "TestFarm" if f["id"] == "TestSettlers" else "TestCampRenamed", 5
        for place in p["places"]:
            place["holder"] = {"TestFarm": "TestSettlers", "TestCampRenamed": "TestRaiders"}.get(place["id"])
        self.assertEqual([x for x in pack.validate_pack(p) if "TestOrder" not in x], [])

    def test_duplicate_editor_ids_get_unique_ids(self):
        extra = os.path.join(self.dir, "Extra.esm")
        plugin(extra, [], [grup(b"LCTN", [rec(b"LCTN", 0x60, [edid("TestFarm")])])])
        draft, _ = self.draft(self.base, extra)
        ids = sorted(p["id"] for p in draft["places"] if p["id"].startswith("TestFarm"))
        self.assertEqual(ids, ["TestFarm@base.esm:000041", "TestFarm@extra.esm:000060"])

    def test_truncated_and_odd_input_is_reported_not_fatal(self):
        odd = os.path.join(self.dir, "Odd.esm")
        plugin(odd, [], [grup(b"LCTN", [
            rec(b"LCTN", 0x61, [edid("TestShort"), sub(b"KSIZ", u32(2)), sub(b"KWDA", u32(0x10) + b"\x01\x02"),
                                sub(b"LCSR", special_ref(0x20)[:10])]),
            rec(b"LCTN", 0x62, [edid("TestBadZip")], compress=True)[:-3] + b"\0\0\0",
        ])])
        data = seed.read([odd])
        self.assertEqual(data["locations"]["odd.esm:000061"]["keywords"], ["odd.esm:000010"])
        self.assertEqual(data["locations"]["odd.esm:000061"]["ref_types"], [])
        self.assertEqual(data["problems"].get("odd.esm: truncated KWDA"), 1)
        self.assertEqual(data["problems"].get("odd.esm: truncated LCSR"), 1)
        self.assertEqual(data["problems"].get("odd.esm: KSIZ does not match KWDA"), 1)
        self.assertEqual(data["problems"].get("odd.esm: bad zlib stream"), 1)
        self.assertEqual(data["locations"]["odd.esm:000062"]["edid"], "")
        draft, report = seed.build(data)
        self.assertIn("odd.esm:000010", report["unresolved_references"])  # keyword never defined

    def test_xxxx_large_subrecord(self):
        big = os.path.join(self.dir, "Big.esm")
        body = u32(0x10) * 20000                                          # 80000 bytes > u16 size field
        kwda = b"KWDA" + struct.pack("<H", 0) + body
        plugin(big, [], [grup(b"KYWD", [rec(b"KYWD", 0x10, [edid("TestKw")])]),
                         grup(b"LCTN", [rec(b"LCTN", 0x63, [edid("TestBig"), sub(b"XXXX", u32(len(body))), kwda])])])
        data = seed.read([big])
        self.assertEqual(len(data["locations"]["big.esm:000063"]["keywords"]), 20000)
        self.assertEqual(data["problems"], {})

    def test_not_a_plugin(self):
        bad = os.path.join(self.dir, "bad.bin")
        with open(bad, "wb") as f:
            f.write(b"not a plugin at all, long enough for a header....")
        with self.assertRaises(ValueError):
            seed.read([bad])
        with open(bad, "wb"):
            pass
        with self.assertRaises(ValueError):
            seed.read([bad])

    def test_seed_writes_files(self):
        out = os.path.join(self.dir, "out")
        report = seed.seed(out, [self.base, self.dlc])
        self.assertEqual(report["locations"], 5)
        with open(os.path.join(out, "commonwealth_seed.draft.json"), encoding="utf-8") as f:
            draft = json.load(f)
        self.assertEqual(len(draft["places"]), 5)
        self.assertEqual(draft["source_plugins"], ["base.esm", "dlc.esm"])  # names only, no paths
        self.assertNotIn(self.dir, json.dumps(draft))
        with open(os.path.join(out, "seed_report.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f)["classify_rules"], seed.CLASSIFY)


if __name__ == "__main__":
    unittest.main()
