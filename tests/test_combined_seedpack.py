"""Marker reading (seed.py second pass) and the draft-to-pack generator (seedpack.py) on synthetic plugins.

Every plugin here is built in bytes in a temp dir. Editor ids, positions and form ids are INVENTED for the test;
the only names taken from a real report are the LocEnc keyword names the generator's rules key on, and the
Commonwealth-scale draft below mirrors only the COUNTS of the first real seed-pack run (owner's PC, 2026-10-21) with
invented ids and random positions on a plane. Nothing here is game data.
"""
import contextlib
import copy
import io
import json
import os
import random
import shutil
import struct
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # sibling test module below

from fo4sf.combined import __main__ as cli  # noqa: E402
from fo4sf.combined import balance, pack, seed, seedpack, sim  # noqa: E402
from fo4sf.combined.model import ROLES, STRENGTH_CAP, WorldState  # noqa: E402
from test_combined_seed import edid, grup, keywords, plugin, rec, special_ref, sub, u32  # noqa: E402


def pos(x, y, z=0.0, size=24):
    """A REFR DATA subrecord: position then rotation floats (xEdit layout), cut to `size` bytes when malformed."""
    return sub(b"DATA", struct.pack("<6f", x, y, z, 0.0, 0.0, 0.0)[:size])


def refr(fid, data, compress=False):
    return rec(b"REFR", fid, [data], compress=compress)


def world_tree(wrld_fid, cell_fid, refrs):
    """WRLD record, then its World Children group (type 1, label = WRLD form id) holding a CELL whose Cell Children
    (type 6) hold a Persistent Children group (type 8) of REFRs: the nesting the reader walks, labels as form ids."""
    return grup(b"WRLD", [
        rec(b"WRLD", wrld_fid, [edid(f"TestWorld{wrld_fid:X}")]),
        grup(u32(wrld_fid), [
            rec(b"CELL", cell_fid, [edid(f"TestCell{cell_fid:X}")]),
            grup(u32(cell_fid), [grup(u32(cell_fid), refrs, gtype=8)], gtype=6),
        ], gtype=1),
    ])


def write_base(path):
    plugin(path, [], [
        grup(b"KYWD", [rec(b"KYWD", 0x10, [edid("TestKwWorkshop")]),
                       rec(b"KYWD", 0x11, [edid("LocEncRaiders")]),
                       rec(b"KYWD", 0x12, [edid("LocEncGhouls")]),
                       rec(b"KYWD", 0x13, [edid("LocEncTestMoles")])]),      # an unmapped encounter keyword
        grup(b"LCRT", [rec(b"LCRT", 0x20, [edid("TestWorkshopRefType")])]),
        grup(b"FACT", [
            rec(b"FACT", 0x30, [edid("TestRaiderGang"), sub(b"XNAM", struct.pack("<IiI", 0x31, 0, 3))]),  # friend
            rec(b"FACT", 0x31, [edid("TestGhoulPack")]),
            rec(b"FACT", 0x32, [edid("TestNobody")]),
        ]),
        world_tree(0x80, 0x81, [
            refr(0x90, pos(0, 0)),
            refr(0x91, pos(10000, 0)),
            refr(0x92, pos(0, 10000)),
            refr(0x93, pos(50000, 50000), compress=True),                  # marker in a compressed record
            refr(0x94, pos(100000, 0)),
            refr(0x95, pos(1, 1, size=10)),                                 # malformed DATA: too short
            refr(0x96, pos(5000, 5000)),
            refr(0x9A, pos(7, 7)),                                          # no LCTN names it: never decoded
        ]),
        world_tree(0x82, 0x83, [refr(0x97, pos(0, 0))]),                    # a second worldspace, one marker
        grup(b"LCTN", [
            rec(b"LCTN", 0x40, [edid("TestRegion")]),
            rec(b"LCTN", 0x41, [edid("TestFarmA"), sub(b"LCSR", special_ref(0x20)), sub(b"PNAM", u32(0x40)),
                                sub(b"MNAM", u32(0x90))]),
            rec(b"LCTN", 0x42, [edid("TestFarmB"), keywords(0x10), sub(b"PNAM", u32(0x40)), sub(b"MNAM", u32(0x91))]),
            rec(b"LCTN", 0x43, [edid("TestRaiderCamp"), keywords(0x11), sub(b"PNAM", u32(0x40)),
                                sub(b"MNAM", u32(0x92))]),
            rec(b"LCTN", 0x44, [edid("TestGhoulDen"), keywords(0x12), sub(b"PNAM", u32(0x40)),
                                sub(b"MNAM", u32(0x93))]),
            rec(b"LCTN", 0x45, [edid("TestRuin"), sub(b"PNAM", u32(0x40)), sub(b"MNAM", u32(0x94))]),
            rec(b"LCTN", 0x46, [edid("TestBadMarker"), sub(b"PNAM", u32(0x40)), sub(b"MNAM", u32(0x95))]),
            rec(b"LCTN", 0x47, [edid("TestMissing"), sub(b"PNAM", u32(0x40)), sub(b"MNAM", u32(0x99))]),
            rec(b"LCTN", 0x48, [edid("TestMoleHole"), keywords(0x13), sub(b"PNAM", u32(0x40)),
                                sub(b"MNAM", u32(0x96))]),
            rec(b"LCTN", 0x49, [edid("TestQuestSpot"), sub(b"PNAM", u32(0x41))]),
            rec(b"LCTN", 0x4A, [edid("TestFarmAnnex"), sub(b"LCSR", special_ref(0x20)), sub(b"PNAM", u32(0x41))]),
            rec(b"LCTN", 0x4B, [edid("TestOrphanFarm"), sub(b"LCSR", special_ref(0x20)), sub(b"PNAM", u32(0x40))]),
            rec(b"LCTN", 0x4C, [edid("TestIsland"), keywords(0x11), sub(b"PNAM", u32(0x40)), sub(b"MNAM", u32(0x97))]),
        ]),
    ])


def commonwealth_scale_draft(seed=0, size=400000.0):
    """A synthetic seed draft at the scale of the first real run (its seed-pack report: 233 kept of 397; settlement 38,
    base 89, landmark 106; raiders 29, ghouls 22, supermutants 19, gunners 12 places; unmapped LocEnc keywords BoS 2,
    Bugs 4, CoA 2, Deathclaw 1, Mirelurks 6, Molerats 1, Robots 8, Synths 5, Wildlife 5; 6 isolated settlement
    candidates). Ids are invented except PrydwenLocation and Goodneighbor, two ids that run reported and the story
    lock rule names; positions are uniform random on a `size` x `size` plane from `seed` (deterministic), which says
    nothing about any map. Places without a marker mirror the run's drops."""
    rng = random.Random(seed)
    world = "test.esm:000080"
    places = []

    def add(pid, kind, keywords=(), marker=True, parent="TestCommonwealth"):
        m = {"x": rng.uniform(0, size), "y": rng.uniform(0, size), "world": world} if marker else None
        places.append({"id": pid, "region": "TestCommonwealth", "kind": kind, "form": f"test:{len(places):06X}",
                       "parent": parent, "keywords": sorted(keywords), "ref_types": [], "faction_hints": [],
                       "has_marker": marker, "marker": m})

    for i in range(32):
        add(f"TestSettlement{i:02d}", "settlement", ["LocTypeWorkshop"])
    for i in range(6):                                              # settlement candidates without a marker
        add(f"TestIsolated{i:02d}", "settlement", ["LocTypeWorkshop"], marker=False, parent="TestNowhere")
    add("PrydwenLocation", "settlement", ["LocTypeWorkshop"])        # a story place the settlement regex caught
    for kw, n in (("Raiders", 29), ("Ghouls", 22), ("SuperMutants", 19), ("Gunners", 12)):
        for i in range(n):
            add(f"Test{kw}Camp{i:02d}", "base", [f"LocEnc{kw}"])
    for i in range(7):
        add(f"TestOtherBase{i:02d}", "base", ["LocEncBoS" if i < 2 else "LocEncCoA" if i < 4 else "LocEncSynths"])
    n_land = 106
    for kw, n in (("Bugs", 4), ("Deathclaw", 1), ("Mirelurks", 6), ("Molerats", 1), ("Wildlife", 5), ("Robots", 8),
                  ("Synths", 2)):
        for i in range(n):
            add(f"Test{kw}Spot{i:02d}", "landmark", [f"LocEnc{kw}"])
            n_land -= 1
    add("Goodneighbor", "landmark")
    n_land -= 1
    for i in range(n_land):
        add(f"TestLandmark{i:03d}", "landmark")
    for i in range(164):                                            # dropped: no marker
        add(f"TestInterior{i:03d}", "landmark", marker=False, parent=f"TestLandmark{i % 50:03d}" if i % 3 else None)
    return {"draft": True, "source_plugins": ["Test.esm"], "places": places, "factions": []}


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(argv)
    return code, out.getvalue(), err.getvalue()


class MarkerReadingTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.base = os.path.join(self.dir, "Base.esm")
        write_base(self.base)

    def test_positions_and_worlds_are_read_for_named_markers_only(self):
        data = seed.read([self.base])
        m = data["markers"]
        self.assertEqual(m["base.esm:000090"], {"x": 0.0, "y": 0.0, "world": "base.esm:000080"})
        self.assertEqual(m["base.esm:000093"], {"x": 50000.0, "y": 50000.0, "world": "base.esm:000080"})  # compressed
        self.assertEqual(m["base.esm:000097"]["world"], "base.esm:000082")                               # 2nd world
        self.assertNotIn("base.esm:00009A", m)                                 # no MNAM names it
        self.assertNotIn("base.esm:000095", m)                                 # malformed DATA
        self.assertNotIn("base.esm:000099", m)                                 # no such REFR
        self.assertEqual(data["problems"], {"base.esm: truncated REFR DATA": 1})
        self.assertEqual(data["record_counts"].get("REFR"), None)             # pass one counts only its types

    def test_draft_carries_marker_and_counts(self):
        draft, report = seed.build(seed.read([self.base]))
        by = {p["id"]: p for p in draft["places"]}
        self.assertEqual(by["TestFarmB"]["marker"], {"x": 10000.0, "y": 0.0, "world": "base.esm:000080"})
        self.assertTrue(by["TestBadMarker"]["has_marker"])
        self.assertIsNone(by["TestBadMarker"]["marker"])
        self.assertIsNone(by["TestMissing"]["marker"])
        self.assertIsNone(by["TestFarmAnnex"]["marker"])
        self.assertFalse(by["TestFarmAnnex"]["has_marker"])
        self.assertEqual(report["markers_found"], 7)
        self.assertEqual(report["markers_missing"], 2)                        # bad DATA, no REFR

    def test_later_plugin_moves_or_deletes_a_marker(self):
        dlc = os.path.join(self.dir, "Dlc.esm")
        plugin(dlc, ["Base.esm"], [
            world_tree(0x00000080, 0x00000081, [refr(0x00000094, pos(20000, 0)),            # moved
                                                rec(b"REFR", 0x00000091, [], flags=seed.DELETED)]),  # gone
            grup(b"LCTN", [rec(b"LCTN", 0x01000050, [edid("TestDlcSpot"), sub(b"MNAM", u32(0x00000092))])]),
        ])
        data = seed.read([self.base, dlc])
        self.assertEqual(data["markers"]["base.esm:000094"]["x"], 20000.0)
        self.assertNotIn("base.esm:000091", data["markers"])
        self.assertEqual(data["locations"]["dlc.esm:000050"]["marker"], "base.esm:000092")  # cross-plugin MNAM
        draft, _ = seed.build(data)
        by = {p["id"]: p for p in draft["places"]}
        self.assertEqual(by["TestDlcSpot"]["marker"]["y"], 10000.0)
        self.assertIsNone(by["TestFarmB"]["marker"])

    def test_no_markers_wanted_skips_the_second_pass(self):
        tiny = os.path.join(self.dir, "Tiny.esm")
        plugin(tiny, [], [grup(b"LCTN", [rec(b"LCTN", 0x40, [edid("TestSpot")])]),
                          world_tree(0x80, 0x81, [refr(0x90, pos(1, 2))])])
        data = seed.read([tiny])
        self.assertEqual(data["markers"], {})
        self.assertEqual(data["problems"], {})

    def test_non_finite_and_missing_data_are_problems(self):
        odd = os.path.join(self.dir, "Odd.esm")
        plugin(odd, [], [
            world_tree(0x80, 0x81, [refr(0x90, pos(float("nan"), 0)), rec(b"REFR", 0x91, [edid("TestNoData")])]),
            grup(b"LCTN", [rec(b"LCTN", 0x40, [edid("TestA"), sub(b"MNAM", u32(0x90))]),
                           rec(b"LCTN", 0x41, [edid("TestB"), sub(b"MNAM", u32(0x91))])]),
        ])
        data = seed.read([odd])
        self.assertEqual(data["markers"], {})
        self.assertEqual(data["problems"], {"odd.esm: non-finite REFR position": 1, "odd.esm: REFR without DATA": 1})


class GeneratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        cls.base = os.path.join(cls.dir, "Base.esm")
        write_base(cls.base)
        cls.draft, _ = seed.build(seed.read([cls.base]))
        cls.pack, cls.report = seedpack.generate(cls.draft)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, ignore_errors=True)

    def places(self):
        return {p["id"]: p for p in self.pack["places"]}

    def test_keep_and_drop_rules(self):
        ids = set(self.places())
        self.assertEqual(ids, {"TestFarmA", "TestFarmB", "TestRaiderCamp", "TestGhoulDen", "TestRuin", "TestMoleHole",
                               "TestFarmAnnex", "TestOrphanFarm", "TestIsland"})
        self.assertEqual(self.report["dropped"], {"no marker position": 2,            # TestRegion, TestQuestSpot
                                                  "marker position not found": 2})    # TestBadMarker, TestMissing
        self.assertEqual((self.report["draft_places"], self.report["kept"]), (13, 9))

    def test_holders_kinds_and_defence(self):
        by = self.places()
        for sid in ("TestFarmA", "TestFarmB", "TestFarmAnnex", "TestOrphanFarm"):
            self.assertEqual((by[sid]["holder"], by[sid]["kind"], by[sid]["defence"]), ("settlers", "settlement", 2))
        self.assertEqual((by["TestRaiderCamp"]["holder"], by["TestRaiderCamp"]["kind"]), ("raiders", "base"))
        self.assertEqual((by["TestIsland"]["holder"], by["TestIsland"]["kind"]), ("raiders", "base"))
        self.assertEqual((by["TestGhoulDen"]["holder"], by["TestGhoulDen"]["kind"], by["TestGhoulDen"]["defence"]),
                         ("ghouls", "base", 4))
        self.assertEqual((by["TestRuin"]["holder"], by["TestRuin"]["kind"]), (None, "landmark"))
        self.assertEqual((by["TestMoleHole"]["holder"], by["TestMoleHole"]["kind"]), (None, "landmark"))
        self.assertEqual(self.report["unmapped_enc_keywords"], {"LocEncTestMoles": 1})
        self.assertEqual(self.report["holders"], {"ghouls": 1, "raiders": 2, "settlers": 4})
        self.assertEqual(self.report["unheld"], 2)

    def test_factions_are_the_packs_own_set(self):
        f = {x["id"]: x for x in self.pack["factions"]}
        self.assertEqual(sorted(f), ["ghouls", "raiders", "settlers"])            # the others hold nothing
        self.assertEqual(self.report["factions_dropped_no_place"], ["creatures", "gunners", "robots", "supermutants"])
        self.assertNotIn("TestRaiderGang", json.dumps(self.pack))                 # FACT ids never enter the pack
        self.assertEqual(f["settlers"]["strength"], 8 + 2 * 4)
        self.assertEqual(f["raiders"]["strength"], 8 + 2 * 2)
        self.assertEqual(f["ghouls"]["strength"], 8 + 2 * 1)
        self.assertEqual((f["settlers"]["aggression"], f["raiders"]["aggression"]), (20, 70))

    def test_homes_most_same_holder_neighbours_then_id(self):
        f = {x["id"]: x for x in self.pack["factions"]}
        self.assertEqual(f["settlers"]["home"], "TestFarmA")     # two settler neighbours (FarmB, Annex)
        self.assertEqual(f["raiders"]["home"], "TestIsland")     # 0 and 0: tie, smaller id wins
        self.assertEqual(f["ghouls"]["home"], "TestGhoulDen")
        self.assertEqual(self.report["homes"], {"ghouls": "TestGhoulDen", "raiders": "TestIsland",
                                                "settlers": "TestFarmA"})

    def test_relations_carried_from_fact_or_placeholder(self):
        f = {x["id"]: x for x in self.pack["factions"]}
        self.assertEqual(f["raiders"]["relations"], {"ghouls": 40, "settlers": -80})   # friend XNAM carried
        self.assertEqual(f["ghouls"]["relations"], {"settlers": -80})                  # no FACT data: placeholder
        self.assertEqual(f["settlers"]["relations"], {"ghouls": -80, "raiders": -80})
        self.assertEqual(self.report["fact_ids_matched"], {"ghouls": ["TestGhoulPack"], "raiders": ["TestRaiderGang"]})
        self.assertEqual(self.report["fact_relations_carried"], {"raiders": {"ghouls": 40}})

    def test_routes_k_nearest_per_world_undirected_and_data_relative(self):
        routes = self.pack["routes"]
        edges = {frozenset((r["a"], r["b"])): r["hours"] for r in routes}
        self.assertEqual(len(edges), len(routes))                                # deduplicated
        self.assertTrue(all(r["a"] < r["b"] for r in routes))                    # undirected, canonical order
        self.assertEqual(len(routes), 13)                                        # 12 k-nearest + 1 parent link
        nbrs = seedpack._neighbours(routes)
        for pid in ("TestFarmA", "TestFarmB", "TestRaiderCamp", "TestGhoulDen", "TestRuin", "TestMoleHole"):
            self.assertGreaterEqual(len(nbrs[pid]), 3, pid)
        # The 12 distances are 7071, 10000 x5, 63640 x2, 70711 x2, 90000, 95131: the median is the mean of the 6th and 7th
        # (38891), which maps to 3 hours, so units_per_hour is 12964 and the two clusters land at 1 and 5..7 hours.
        scale = self.report["route_scale"]["base.esm:000080"]
        self.assertEqual((scale["places"], scale["routes"]), (6, 12))
        self.assertAlmostEqual(scale["distance"]["median"], 38890.87, places=1)
        self.assertAlmostEqual(scale["units_per_hour"], 38890.87 / 3, places=1)
        self.assertAlmostEqual(scale["distance"]["min"], 7071.07, places=1)
        self.assertEqual(scale["route_hours"], {1: 6, 5: 4, 7: 2})
        self.assertEqual(edges[frozenset(("TestFarmA", "TestMoleHole"))], 1)      # 7071: 0.55 h rounds to 1
        self.assertEqual(edges[frozenset(("TestFarmA", "TestFarmB"))], 1)         # 10000: 0.77 h
        self.assertEqual(edges[frozenset(("TestGhoulDen", "TestMoleHole"))], 5)   # 63640: 4.9 h
        self.assertEqual(edges[frozenset(("TestGhoulDen", "TestRuin"))], 5)      # 70711: 5.45 h
        self.assertNotIn(frozenset(("TestFarmA", "TestRuin")), edges)            # 4th nearest, k is 3
        self.assertEqual(edges[frozenset(("TestFarmB", "TestRuin"))], 7)          # 90000: 6.9 h
        self.assertNotIn(frozenset(("TestIsland", "TestFarmA")), edges)           # never across worlds
        self.assertEqual(edges[frozenset(("TestFarmAnnex", "TestFarmA"))], 1)     # no marker: parent link, minimum
        self.assertEqual(self.report["route_scale"]["base.esm:000082"]["units_per_hour"], None)   # one place
        self.assertEqual(self.report["isolated"], ["TestIsland", "TestOrphanFarm"])
        self.assertEqual(self.report["unlinked"], {"no marker and parent not kept": 1})
        self.assertEqual(self.report["worlds"], {"base.esm:000080": 6, "base.esm:000082": 1})
        self.assertEqual(self.report["route_hours"], {1: 7, 5: 4, 7: 2})
        self.assertEqual(self.report["story_locked"], {})                         # no id matches the placeholders

    def test_route_hours_follow_the_median_not_the_unit(self):
        """Scaling every marker by 1000 changes no hour: the rule needs no fact about what a unit measures."""
        big = copy.deepcopy(self.draft)
        for p in big["places"]:
            if p["marker"]:
                p["marker"]["x"] *= 1000
                p["marker"]["y"] *= 1000
        p2, r2 = seedpack.generate(big)
        self.assertEqual(p2["routes"], self.pack["routes"])
        self.assertAlmostEqual(r2["route_scale"]["base.esm:000080"]["units_per_hour"],
                               1000 * self.report["route_scale"]["base.esm:000080"]["units_per_hour"], places=3)
        rules = copy.deepcopy(seedpack.DEFAULT_RULES)
        rules["median_route_hours"], rules["min_route_hours"] = 6, 2
        p3, r3 = seedpack.generate(self.draft, rules)
        self.assertEqual(r3["route_hours"], {2: 7, 10: 3, 11: 1, 14: 1, 15: 1})   # double the hours, floor 2
        self.assertEqual(min(x["hours"] for x in p3["routes"]), 2)

    def test_story_lock_rule_unholds_and_pins_a_place(self):
        rules = copy.deepcopy(seedpack.DEFAULT_RULES)
        rules["story_lock"] = {"story_test_b": r"^TestFarmB$", "story_test_a": r"Ruin"}
        p, r = seedpack.generate(self.draft, rules)
        by = {x["id"]: x for x in p["places"]}
        self.assertEqual((by["TestFarmB"]["holder"], by["TestFarmB"]["kind"], by["TestFarmB"]["story_lock"]),
                         (None, "landmark", "story_test_b"))                      # a settlement candidate: no stats
        self.assertNotIn("TestFarmB", {x["place"] for x in p["settlements"]})
        self.assertEqual(by["TestRuin"]["story_lock"], "story_test_a")
        self.assertNotIn("story_lock", by["TestFarmA"])                            # unlocked places carry no key
        self.assertEqual(r["story_locked"], {"TestFarmB": "story_test_b", "TestRuin": "story_test_a"})
        self.assertEqual(r["holders"]["settlers"], 3)
        self.assertEqual(pack.validate_pack(p), [])
        ws = WorldState(seed=4)
        pack.load_pack(ws, copy.deepcopy(p))
        for f in ws.factions.values():
            f.aggression = 100
        sim.run(ws, 60 * 24)
        self.assertIsNone(ws.places["TestFarmB"].holder)                           # never taken
        self.assertIsNone(ws.places["TestRuin"].holder)
        self.assertEqual(balance.metrics(ws)["story_lock_violations"], 0)

    def test_wild_factions_are_hostile_to_everyone_and_priority_picks_the_holder(self):
        rules = copy.deepcopy(seedpack.DEFAULT_RULES)
        rules["enc_factions"]["TestMoles"] = "creatures"
        p, r = seedpack.generate(self.draft, rules)
        by = {x["id"]: x for x in p["places"]}
        self.assertEqual((by["TestMoleHole"]["holder"], by["TestMoleHole"]["kind"]), ("creatures", "base"))
        f = {x["id"]: x for x in p["factions"]}
        self.assertEqual(f["creatures"]["relations"], {"ghouls": -80, "raiders": -80, "settlers": -80})
        self.assertEqual(f["raiders"]["relations"], {"creatures": -80, "ghouls": 40, "settlers": -80})
        self.assertEqual(f["creatures"]["aggression"], 50)
        self.assertEqual(r["unmapped_enc_keywords"], {})
        # a place with keywords for two mapped factions goes to the one earlier in enc_priority, whatever the order
        draft = copy.deepcopy(self.draft)
        hole = [x for x in draft["places"] if x["id"] == "TestMoleHole"][0]
        hole["keywords"] = ["LocEncTestMoles", "LocEncGhouls"]
        p2, _ = seedpack.generate(draft, rules)
        self.assertEqual({x["id"]: x for x in p2["places"]}["TestMoleHole"]["holder"], "ghouls")
        rules["enc_priority"] = ["creatures"]
        p3, _ = seedpack.generate(draft, rules)
        self.assertEqual({x["id"]: x for x in p3["places"]}["TestMoleHole"]["holder"], "creatures")

    def test_settlements_get_the_fixture_defaults(self):
        s = {x["place"]: x for x in self.pack["settlements"]}
        self.assertEqual(sorted(s), ["TestFarmA", "TestFarmAnnex", "TestFarmB", "TestOrphanFarm"])
        for x in s.values():
            self.assertEqual(x["population"], 5)
            self.assertEqual(x["roles"], {"farmer": 3, "guard": 1, "trader": 1, "crafter": 0, "scavenger": 0,
                                          "doctor": 0})
            self.assertEqual(x["stock"], {"food": 20, "water": 20, "scrap": 0, "ammo": 10, "medicine": 0})
            self.assertEqual((x["morale"], x["stage"], x["beds"]), (50, 0, 20))

    def test_pack_validates_and_loads(self):
        self.assertEqual(pack.validate_pack(self.pack), [])
        self.assertEqual(self.report["validation_problems"], [])
        ws = WorldState(seed=1)
        pack.load_pack(ws, copy.deepcopy(self.pack))
        self.assertEqual(len(ws.places), 9)
        self.assertEqual(len(ws.settlements), 4)

    def test_deterministic_bytes_whatever_the_draft_order(self):
        a = seedpack.dumps(self.pack) + seedpack.dumps(self.report)
        shuffled = copy.deepcopy(self.draft)
        shuffled["places"].reverse()
        shuffled["factions"].reverse()
        for p in shuffled["places"]:
            p["keywords"].reverse()
        p2, r2 = seedpack.generate(shuffled)
        self.assertEqual(seedpack.dumps(p2) + seedpack.dumps(r2), a)
        self.assertEqual(seedpack.generate(self.draft), (self.pack, self.report))
        self.assertEqual(seedpack.DEFAULT_RULES["k_nearest"], 3)                 # generate copies, never mutates

    def test_rules_can_be_changed(self):
        rules = copy.deepcopy(seedpack.DEFAULT_RULES)
        rules["k_nearest"], rules["median_route_hours"], rules["strength_base"] = 1, 30, 100
        p, r = seedpack.generate(self.draft, rules)
        self.assertLess(r["routes"], self.report["routes"])
        self.assertEqual(min(x["hours"] for x in p["routes"]), 1)               # the parent link
        self.assertGreater(max(x["hours"] for x in p["routes"]), 10)
        self.assertTrue(all(f["strength"] == STRENGTH_CAP for f in p["factions"]))  # capped by the model
        self.assertEqual(pack.validate_pack(p), [])

    def test_empty_draft_gives_an_empty_valid_pack(self):
        p, r = seedpack.generate({"draft": True, "places": [], "factions": []})
        self.assertEqual(p, {"places": [], "settlements": [], "factions": [], "routes": []})
        self.assertEqual(pack.validate_pack(p), [])
        self.assertEqual(r["factions_dropped_no_place"], ["creatures", "ghouls", "gunners", "raiders", "robots",
                                                           "settlers", "supermutants"])

    def test_thirty_day_sim_keeps_the_invariants(self):
        for s in (1, 2, 3):
            ws = WorldState(seed=s)
            pack.load_pack(ws, copy.deepcopy(self.pack))
            start = copy.deepcopy(ws)
            for _ in range(30 * 24 // sim.TICK_HOURS):
                sim.tick(ws)
                for pid, pl in ws.places.items():
                    if pl.story_lock:
                        self.assertEqual(pl.holder, start.places[pid].holder, pid)
                for fid, f in ws.factions.items():
                    self.assertEqual(ws.places[f.home].holder, fid, f"{fid} lost its home")
                    self.assertTrue(0 <= f.strength <= STRENGTH_CAP, (fid, f.strength))
                for sid, st in ws.settlements.items():
                    self.assertTrue(0 <= st.population <= st.beds, (sid, st.population))
                    self.assertTrue(0 <= st.morale <= 100, (sid, st.morale))
                    self.assertEqual(set(st.roles), set(ROLES))
                    self.assertEqual(sum(st.roles.values()), st.population, (sid, st.roles))
                    self.assertTrue(all(v >= 0 for v in st.stock.values()), (sid, st.stock))
                for q in ws.squads.values():
                    self.assertIn(q.at, ws.places)
                    self.assertIn(q.goal, ws.places)
            self.assertEqual(ws.hour, 30 * 24)
            m = balance.metrics(ws)
            self.assertEqual((m["story_lock_violations"], m["home_violations"]), (0, 0))
            self.assertTrue(any(e["kind"] == "attack_launched" for e in ws.events))   # alive, not frozen


class CommonwealthScaleTests(unittest.TestCase):
    """The generator on a draft at the first real run's scale (counts only; invented ids and positions)."""

    @classmethod
    def setUpClass(cls):
        cls.draft = commonwealth_scale_draft()
        cls.pack, cls.report = seedpack.generate(cls.draft)

    def test_counts_mirror_the_first_run(self):
        r = self.report
        self.assertEqual((r["draft_places"], r["kept"]), (398, 234))
        self.assertEqual(r["kinds"], {"base": 114, "landmark": 82, "settlement": 38})
        self.assertEqual(r["holders"], {"creatures": 17, "ghouls": 22, "gunners": 12, "raiders": 29, "robots": 8,
                                        "settlers": 38, "supermutants": 19})
        self.assertEqual(r["unmapped_enc_keywords"], {"LocEncBoS": 2, "LocEncCoA": 2, "LocEncSynths": 5})
        self.assertEqual(r["unheld"], 89)
        self.assertEqual(len(r["isolated"]), 6)
        self.assertEqual(r["factions"], ["creatures", "ghouls", "gunners", "raiders", "robots", "settlers",
                                         "supermutants"])
        self.assertEqual(r["validation_problems"], [])

    def test_story_places_are_locked_and_unheld(self):
        self.assertEqual(self.report["story_locked"], {"Goodneighbor": "story_goodneighbor",
                                                       "PrydwenLocation": "story_prydwen"})
        by = {p["id"]: p for p in self.pack["places"]}
        self.assertEqual((by["PrydwenLocation"]["holder"], by["PrydwenLocation"]["kind"]), (None, "landmark"))
        self.assertNotIn("PrydwenLocation", {s["place"] for s in self.pack["settlements"]})
        self.assertEqual(len(self.pack["settlements"]), 38)

    def test_route_hours_spread_around_the_median(self):
        hours = self.report["route_hours"]
        self.assertEqual(sum(hours.values()), self.report["routes"])
        self.assertGreater(hours[1] / self.report["routes"], 0.05)              # not everything at the floor
        self.assertLess(hours[1] / self.report["routes"], 0.3)
        self.assertEqual(max(hours, key=hours.get), 3)                           # the median maps to 3 hours
        scale = self.report["route_scale"]["test.esm:000080"]
        self.assertEqual(scale["places"], 228)
        self.assertAlmostEqual(scale["distance"]["median"] / scale["units_per_hour"], 3.0)

    def test_scale_pack_runs_with_the_invariants(self):
        ws = WorldState(seed=1)
        pack.load_pack(ws, copy.deepcopy(self.pack))
        sim.run(ws, 30 * 24)
        m = balance.metrics(ws)
        self.assertEqual((m["story_lock_violations"], m["home_violations"]), (0, 0))
        self.assertIsNone(ws.places["PrydwenLocation"].holder)
        self.assertGreater(m["settlement_captures"], 0)
        self.assertLess(m["settlements_at_cap_share"], 0.5)                       # the growth brakes at scale
        self.assertTrue(all(f["id"] in m["places_taken_by"] for f in self.pack["factions"]))


class CliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        base = os.path.join(self.dir, "Base.esm")
        write_base(base)
        self.seed_out = os.path.join(self.dir, "seed")
        seed.seed(self.seed_out, [base])
        self.draft = os.path.join(self.seed_out, "commonwealth_seed.draft.json")

    def test_seed_pack_writes_pack_and_report(self):
        out = os.path.join(self.dir, "pack")
        code, text, err = run_cli(["seed-pack", self.draft, out])
        self.assertEqual(code, 0, err)
        self.assertEqual(text.count("\n"), 1)
        self.assertTrue(text.startswith("seed-pack: 9 of 13 places kept, 3 factions, 13 routes, 2 isolated"), text)
        self.assertEqual(sorted(os.listdir(out)), ["commonwealth.pack.json", "seedpack_report.json"])
        with open(os.path.join(out, "commonwealth.pack.json"), encoding="utf-8") as f:
            p = json.load(f)
        self.assertEqual(pack.validate_pack(p), [])
        # the generated pack runs through the existing simulate command
        code, text, err = run_cli(["simulate", "--pack", os.path.join(out, "commonwealth.pack.json"),
                                   "--seed", "2", "--days", "5"])
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(text)["hour"], 120)
        with open(os.path.join(out, "seedpack_report.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f)["rules"], seedpack.DEFAULT_RULES)

    def test_seed_pack_refuses_a_file_that_is_not_a_draft(self):
        notdraft = os.path.join(self.dir, "pack.json")
        with open(notdraft, "w", encoding="utf-8") as f:
            json.dump({"places": []}, f)
        code, _, err = run_cli(["seed-pack", notdraft, os.path.join(self.dir, "x")])
        self.assertEqual(code, 1)
        self.assertIn("not a seed draft", err)
        self.assertFalse(os.path.exists(os.path.join(self.dir, "x")))


if __name__ == "__main__":
    unittest.main()
