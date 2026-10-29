"""src/fo4sf/planet/records.py: our planet's master (FO4SFPlanet.esm), in Sol (route B) and in a star system of our
own (route A), and the registration override, cloned from tests/planet_fixture.py's synthetic Starfield.esm (no game
data), then read back with the raw reader."""
import math
import os
import struct
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "src"))
import planet_fixture as pf  # noqa: E402
from fo4sf.planet import esm, records  # noqa: E402


class MasterTests(unittest.TestCase):
    """Route A: our own star system (system "own")."""
    SYSTEM = "own"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.sf = os.path.join(self.tmp.name, "Starfield.esm")
        pf.write_starfield(self.sf, houdini=70000)            # a PCCC above 65,535 bytes: written with XXXX

    def build(self, opts=None, other=(), planets=(), locations=(), overlays=()):
        with esm.Plugin(self.sf) as sf:
            w, rep = records.build_master(sf, dict({"system": self.SYSTEM}, **(opts or {})), other, planets, locations,
                                          overlays)
        out = os.path.join(self.tmp.name, records.MASTER)
        w.write(out)
        return out, rep

    def recs(self, path):
        with esm.Plugin(path) as p:
            out = {}
            for g in p.groups:
                for r in p.records(g):
                    out[r.formid] = r
            return p.masters, p.flags, out

    def test_master_passes_its_check_and_holds_its_records(self):
        out, rep = self.build()
        problems, summary = records.check_master(out)
        self.assertEqual(problems, [])
        masters, flags, recs = self.recs(out)
        self.assertEqual((masters, flags & esm.ESM, flags & esm.LOCALIZED), (["Starfield.esm"], 1, 0))
        self.assertEqual(sorted(recs), [0x01000800 + i for i in range(6)])
        self.assertEqual(rep["system_id"], hex(records.DEFAULT_SYSTEM_ID))
        self.assertEqual([loc["edid"] for loc in rep["locations"]],
                         ["SFO4SFProbeStar", "SFO4SFProbeStar_PFO4SFProbe", "SFO4SFProbeStar_PFO4SFProbe_Orbit",
                          "SFO4SFProbeStar_PFO4SFProbe_Surface"])

    def test_star_is_sol_with_our_ids_name_and_position(self):
        out, rep = self.build()
        _, _, recs = self.recs(out)
        star = recs[0x01000800]
        self.assertEqual(records.star_system_id(star), records.DEFAULT_SYSTEM_ID)
        self.assertEqual(records.star_name(star), records.DEFAULT_STAR_NAME)
        pos = records.star_position(star)
        for got, want in zip(pos, (12.0, -3.0, 3.0)):                  # Sol (10, -5, 2) + (2, 2, 1)
            self.assertAlmostEqual(got, want, places=5)
        self.assertFalse(star.flags & records.STARTS_HIDDEN)
        self.assertEqual(star.get(b"WED0"), bytes(20))                  # every other field kept
        self.assertEqual(records.full_names(star.subs), [("TESFullName_Component", esm.zbytes(records.DEFAULT_STAR_NAME))])
        self.assertAlmostEqual(rep["star"]["nearest_star_pc"], math.dist(pos, (12.5, -3.0, 2.5)), places=4)

    def test_locations_chain_to_universe_with_vanilla_data(self):
        out, rep = self.build()
        _, _, recs = self.recs(out)
        k = records.KEYWORDS
        want = {0x01000801: (records.UNIVERSE, [k["LocTypeStarSystem"]], 0, b"\0\0\0\0\xff\x01\x00\x0a"),
                0x01000802: (0x01000801, [k["LocTypePlanet"], k["LocTypeMajorOrbital"]], 1, b"\0\0\0\0\xff\x02\x00\x0b"),
                0x01000803: (0x01000802, [k["LocTypeOrbit"]], 1, b"\0\0\0\0\xff\x03\x00\x0c"),
                0x01000804: (0x01000802, [k["LocTypeSurface"]], 1, b"\0\0\0\0\xff\x04\x00\x0d")}
        for fid, (parent, kws, ynam, data) in want.items():
            r = recs[fid]
            self.assertEqual(struct.unpack("<I", r.get(b"PNAM"))[0], parent, r.edid)
            self.assertEqual(records.keywords_of(r), kws, r.edid)
            self.assertEqual(records.location_ids(r), (records.DEFAULT_SYSTEM_ID, ynam), r.edid)
            self.assertEqual(r.get(b"DATA"), data, r.edid)              # the template location's DATA
            self.assertEqual(esm.zstring(r.get(b"FULL")), records.DEFAULT_STAR_NAME if fid == 0x01000801
                             else records.DEFAULT_PLANET_NAME)

    def test_planet_is_jemison_without_worlds_space_cell_or_life(self):
        out, rep = self.build()
        _, _, recs = self.recs(out)
        p = recs[0x01000805]
        self.assertEqual(records.galaxy(p), (records.DEFAULT_SYSTEM_ID, 0, 1))
        self.assertEqual(records.master_worldspaces(p), [])
        self.assertEqual(records.planet_name(p), records.DEFAULT_PLANET_NAME)
        self.assertEqual(records.body_get(p.subs, b"DNAM"), b"\0\0\0\0\0")
        self.assertEqual(p.get(b"EOVR"), b"")
        bs = records.biomes(p)
        self.assertEqual([b["biome"] for b in bs], [0x0007F88A, 0x000FD00D])
        self.assertTrue(all(not b["fauna"] and not b["flora"] for b in bs))
        self.assertEqual(bs[0]["keywords"], [0x00169593])                # the rest of the biome kept
        self.assertEqual(records.orbital(p)["surface_gravity"], records.orbital(pf.planet())["surface_gravity"])
        self.assertTrue(p.flags & esm.COMPRESSED)
        self.assertIn("CNAM: 2 master worldspaces removed", rep["planet"]["changes"])
        self.assertIn("DNAM: unique space cell cleared", rep["planet"]["changes"])
        self.assertEqual(len([c for c in rep["planet"]["changes"] if "fauna removed" in c]), 1)

    def test_keeping_life_on_request(self):
        out, rep = self.build({"no_fauna": False, "no_flora": False})
        _, _, recs = self.recs(out)
        bs = records.biomes(recs[0x01000805])
        self.assertEqual(len(bs[0]["fauna"]), 2)
        self.assertEqual(len(bs[0]["flora"]), 1)

    def test_taken_system_id_and_close_star_are_refused(self):
        with self.assertRaises(records.PlanetError):
            self.build({"system_id": pf.JEMISON_SYSTEM})
        with self.assertRaises(records.PlanetError):
            self.build(other=[("SFBGS00X.esm Star", records.DEFAULT_SYSTEM_ID, (50.0, 50.0, 5.0))])
        with self.assertRaises(records.PlanetError):
            self.build(other=[("SFBGS00X.esm Star", 0x1F0F0, (12.1, -3.0, 3.0))])
        with self.assertRaises(records.PlanetError):
            self.build({"planet": "Nowhere"})

    def test_check_master_finds_a_wrong_record(self):
        out, _ = self.build()
        masters, flags, recs = self.recs(out)
        w = esm.PluginWriter(masters, flags)
        for fid, r in recs.items():
            if fid == 0x01000804:
                r.subs = [(s, struct.pack("<I", 0x01000801) if s == b"PNAM" else d) for s, d in r.subs]
            w.add(r)
        w.write(out)
        problems, _ = records.check_master(out)
        self.assertEqual(len(problems), 1)
        self.assertIn("parent 01000801", problems[0])


    def test_every_full_of_a_clone_is_our_name(self):
        with esm.Plugin(self.sf) as sf:
            sol = records.find_star(sf, "Sol")
        sol.subs = sol.subs[:1] + [(b"FULL", struct.pack("<I", 0x0001A682))] + sol.subs[1:]   # a stray string id
        star = records.clone_star(sol, 0x01000800, "S", "Our Star", 0xF04F1, (1.0, 2.0, 3.0))
        self.assertEqual([d for _, d in records.full_names(star.subs)], [b"Our Star\0", b"Our Star\0"])

    def test_check_master_wants_our_names_in_every_full(self):
        out, _ = self.build()
        self.assertEqual(records.check_master(out, star_name="Another Star")[0],
                         [f"SFO4SFProbeStar: FULL is {esm.zbytes(records.DEFAULT_STAR_NAME).hex()}, not 'Another Star'",
                          f"star: FULL in TESFullName_Component is {esm.zbytes(records.DEFAULT_STAR_NAME).hex()}, "
                          "not 'Another Star'"])
        masters, flags, recs = self.recs(out)
        w = esm.PluginWriter(masters, flags)
        for fid, r in recs.items():
            if fid == 0x01000800:                                # a string id left in the star: ends in a zero byte
                r.subs = r.subs[:1] + [(b"FULL", bytes.fromhex("82a60100"))] + r.subs[1:]
            w.add(r)
        w.write(out)
        problems, _ = records.check_master(out)
        self.assertEqual(problems, [f"star: FULL is 82a60100, not {records.DEFAULT_STAR_NAME!r}"])


class SolTests(MasterTests):
    """Route B, the default: our planet in Sol, under Sol's own system location."""
    SYSTEM = "sol"

    def check(self, out, planet_id=pf.SOL_FREE_ID, system_location=pf.SOL_LOCATION, **kw):
        return records.check_master(out, pf.SOL_SYSTEM, planet_id, system_location=system_location, **kw)

    def test_master_passes_its_check_and_holds_its_records(self):
        out, rep = self.build()
        self.assertEqual(self.check(out)[0], [])
        _, _, recs = self.recs(out)
        self.assertEqual(sorted(recs), [0x01000802, 0x01000803, 0x01000804, 0x01000805])    # no star, no system
        self.assertEqual((rep["system"], rep["system_id"], rep["planet_id"]), ("sol", "0x0", pf.SOL_FREE_ID))
        self.assertEqual(rep["system_location"], {"formid": f"{pf.SOL_LOCATION:08X}", "edid": "SSol",
                                                  "parent": f"{records.UNIVERSE:08X}", "ours": False})
        self.assertEqual((rep["star"]["edid"], rep["star"]["ours"]), ("Sol", False))
        self.assertEqual([loc["edid"] for loc in rep["locations"]],
                         ["SSol_PFO4SFProbe", "SSol_PFO4SFProbe_Orbit", "SSol_PFO4SFProbe_Surface"])
        self.assertIn("location SSol_PBelt_Orbit has YNAM 7", rep["sol"]["planet_id_why"])
        self.assertEqual([b[1] for b in rep["sol"]["bodies"]], ["EarthPlanetData", "LunaPlanetData"])
        self.assertEqual(rep["sol"]["location_ynams"], [0, 3, 6, 7])
        # the default is route B
        with esm.Plugin(self.sf) as sf:
            self.assertEqual(records.build_master(sf)[1]["system"], "sol")

    def test_locations_chain_to_sols_system_location(self):
        out, rep = self.build()
        _, _, recs = self.recs(out)
        k = records.KEYWORDS
        want = {0x01000802: (pf.SOL_LOCATION, [k["LocTypePlanet"], k["LocTypeMajorOrbital"]],
                             b"\0\0\0\0\xff\x02\x00\x0b"),
                0x01000803: (0x01000802, [k["LocTypeOrbit"]], b"\0\0\0\0\xff\x03\x00\x0c"),
                0x01000804: (0x01000802, [k["LocTypeSurface"]], b"\0\0\0\0\xff\x04\x00\x0d")}
        for fid, (parent, kws, data) in want.items():
            r = recs[fid]
            self.assertEqual(struct.unpack("<I", r.get(b"PNAM"))[0], parent, r.edid)
            self.assertEqual(records.keywords_of(r), kws, r.edid)
            self.assertEqual(records.location_ids(r), (pf.SOL_SYSTEM, pf.SOL_FREE_ID), r.edid)
            self.assertEqual(r.get(b"DATA"), data, r.edid)              # Jemison's locations' DATA
            self.assertEqual(esm.zstring(r.get(b"FULL")), records.DEFAULT_PLANET_NAME)
        self.assertEqual(records.galaxy(recs[0x01000805]), (pf.SOL_SYSTEM, 0, pf.SOL_FREE_ID))

    def test_locations_chain_to_universe_with_vanilla_data(self):
        self.skipTest("route A only: route B has no system location of its own")

    def test_star_is_sol_with_our_ids_name_and_position(self):
        self.skipTest("route A only: route B adds no star")

    def test_planet_is_jemison_without_worlds_space_cell_or_life(self):
        out, rep = self.build()
        _, _, recs = self.recs(out)
        p = recs[0x01000805]
        self.assertEqual(records.master_worldspaces(p), [])
        self.assertEqual(records.body_get(p.subs, b"DNAM"), b"\0\0\0\0\0")
        self.assertTrue(all(not b["fauna"] and not b["flora"] for b in records.biomes(p)))
        self.assertEqual(records.orbital(p), records.orbital(pf.planet()))       # Jemison's orbit and body kept

    def test_keeping_life_on_request(self):
        out, _ = self.build({"no_fauna": False})
        _, _, recs = self.recs(out)
        self.assertEqual(len(records.biomes(recs[0x01000805])[0]["fauna"]), 2)

    def test_taken_system_id_and_close_star_are_refused(self):
        self.skipTest("route A only")

    def test_the_other_plugins_bodies_and_locations_count(self):
        _, rep = self.build(planets=[("SomeMod.esp", "ModMoon", "Mod Moon", [0, 3, 12], True),
                                     ("Far.esp", "FarBody", "Far", [pf.JEMISON_SYSTEM, 0, 40], True)])
        self.assertEqual(rep["planet_id"], 13)
        self.assertIn("SomeMod.esp ModMoon has planet id 12", rep["sol"]["planet_id_why"])
        _, rep = self.build(locations=[("SomeMod.esp", "ModLoc", 0, 20, [], 0x01000800, True),
                                       ("Far.esp", "FarLoc", pf.JEMISON_SYSTEM, 50, [], 0x01000801, True),
                                       ("Junk.esp", "NoY", 0, None, [], 0x01000802, True)])
        self.assertEqual(rep["planet_id"], 21)

    def test_a_planet_id_asked_for_must_be_free(self):
        out, rep = self.build({"planet_id": 9})
        self.assertEqual((rep["planet_id"], rep["sol"]["planet_id_why"]), (9, "asked for"))
        self.assertEqual(self.check(out, planet_id=9)[0], [])
        for taken in (3, 6, 7, 0, records.ID_UNSET):            # Earth, Luna, a location's YNAM, no id, negative
            with self.assertRaises(records.PlanetError):
                self.build({"planet_id": taken})

    def test_check_master_finds_a_wrong_record(self):
        out, _ = self.build()
        self.assertEqual(self.check(out, system_location=0x00018001)[0],
                         ["SSol_PFO4SFProbe: parent 00018000, expected 00018001"])
        self.assertEqual(self.check(out, system_location=0x01000801)[0],
                         ["system location 01000801 is not a Starfield.esm record"])
        self.assertEqual(records.check_master(out, pf.SOL_SYSTEM, pf.SOL_FREE_ID)[0],     # read as route A
                         ["STDT 01000800 missing", "LCTN 01000801 missing"])
        self.assertIn("planet GNAM (0, 0, 8)", self.check(out, planet_id=9)[0])
        own, _ = self.build({"system": "own"})                    # route A's master read as route B
        self.assertIn("unexpected records ['01000800', '01000801']", self.check(own)[0])

    def test_check_master_wants_our_names_in_every_full(self):
        out, _ = self.build()
        self.assertEqual(self.check(out, planet_name="Another")[0][0],
                         f"SSol_PFO4SFProbe: FULL is {esm.zbytes(records.DEFAULT_PLANET_NAME).hex()}, not 'Another'")

    def test_sols_system_location_must_be_one_record(self):
        with esm.Plugin(self.sf) as sf:
            kw, _ = records.check_keywords(records.keyword_edids(sf))
            self.assertEqual(records.star_system_location(sf, pf.SOL_SYSTEM, kw).edid, "SSol")
            with self.assertRaises(records.PlanetError):
                records.star_system_location(sf, 0x7777, kw)
        k = records.KEYWORDS
        stray = pf.location(0x00018020, "SSolDev", [k["LocTypeStarSystem"]], 0x00018001, pf.SOL_SYSTEM, 0)
        twin = pf.location(0x00018021, "SSolTwin", [k["LocTypeStarSystem"]], records.UNIVERSE, pf.SOL_SYSTEM, 0)
        for extra, ok in (([stray], True), ([stray, twin], False)):
            w = esm.PluginWriter([], esm.ESM | esm.LOCALIZED)
            for r in pf.keyword_records() + pf.locations() + extra:
                w.add(r)
            path = os.path.join(self.tmp.name, "two.esm")
            w.write(path)
            with esm.Plugin(path) as p:
                if ok:                                        # the one under Universe is taken
                    self.assertEqual(records.star_system_location(p, pf.SOL_SYSTEM, kw).edid, "SSol")
                else:
                    with self.assertRaises(records.PlanetError):
                        records.star_system_location(p, pf.SOL_SYSTEM, kw)

    def test_an_unknown_system_is_refused(self):
        with self.assertRaises(records.PlanetError):
            self.build({"system": "mars"})

    def test_overlay_worlds_count_and_ids_that_read_negative_do_not(self):
        world = ("Starfield.esm", "SomeWorld", pf.SOL_SYSTEM, 15)
        _, rep = self.build(overlays=[world, ("Far.esp", "FarWorld", pf.JEMISON_SYSTEM, 40),
                                      ("Mod.esp", "NoPlanet", pf.SOL_SYSTEM, 0)])
        self.assertEqual(rep["planet_id"], 16)
        self.assertIn("Starfield.esm overlay world SomeWorld names planet id 15", rep["sol"]["planet_id_why"])
        self.assertEqual(rep["sol"]["overlay_worlds"], [["Starfield.esm", "SomeWorld", 15]])
        with self.assertRaises(records.PlanetError):                 # an overlay world's planet id is taken
            self.build({"planet_id": 15}, overlays=[world])
        _, rep = self.build(planets=[("Odd.esp", "OddBody", "Odd", [0, 0, 0xFFFFFFFF], True)])
        self.assertEqual(rep["planet_id"], pf.SOL_FREE_ID)
        self.assertEqual(rep["sol"]["unset"], [["Odd.esp", "OddBody", 0xFFFFFFFF]])
        self.assertEqual(rep["sol"]["no_gnam"], [])

    def test_free_planet_id(self):
        self.assertEqual(records.free_planet_id([], []), (1, "no body or location id in use"))
        bodies = [("A.esm", "P", "P", (0, 0, 4)), ("B.esm", "", "Moon", (0, 4, 9))]
        self.assertEqual(records.free_planet_id(bodies, [("A.esm", "L", 2)]), (10, "B.esm Moon has planet id 9"))
        self.assertEqual(records.free_planet_id(bodies, [("A.esm", "L", 11)])[0], 12)
        self.assertEqual(records.free_planet_id(bodies, [], [("C.esm", "W", 20)]),
                         (21, "C.esm overlay world W names planet id 20"))
        odd = bodies + [("D.esm", "Odd", "Odd", (0, 0, records.ID_UNSET)), ("D.esm", "Max", "Max", (0, 0, 0xFFFFFFFF))]
        self.assertEqual(records.free_planet_id(odd, [("D.esm", "L", 0xFFFFFFFE)])[0], 10)       # not counted
        with self.assertRaises(records.PlanetError):                 # one above the largest would read negative
            records.free_planet_id([("E.esm", "Last", "Last", (0, 0, records.ID_UNSET - 1))], [])


class RegistrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        sf = os.path.join(self.tmp.name, "Starfield.esm")
        pf.write_starfield(sf)
        with esm.Plugin(sf) as p:
            w, _ = records.build_master(p)
        self.master = os.path.join(self.tmp.name, records.MASTER)
        w.write(self.master)

    def test_registration_is_the_planet_plus_one_master_worldspace(self):
        w = records.build_registration(self.master, "FO4SFPlanetProbe.esm", 0x809)
        out = os.path.join(self.tmp.name, records.REGISTRATION)
        w.write(out)
        problems, summary = records.check_registration(out, "FO4SFPlanetProbe.esm", 0x809, self.master)
        self.assertEqual(problems, [])
        self.assertEqual(summary["worldspaces"], [(0.0, 0.0, "02000809")])
        with esm.Plugin(out) as p:
            self.assertEqual(p.masters, ["Starfield.esm", records.MASTER, "FO4SFPlanetProbe.esm"])

    def test_registration_check_catches_another_world(self):
        w = records.build_registration(self.master, "FO4SFPlanetProbe.esm", 0x80A)
        out = os.path.join(self.tmp.name, records.REGISTRATION)
        w.write(out)
        problems, _ = records.check_registration(out, "FO4SFPlanetProbe.esm", 0x809, self.master)
        self.assertEqual(len(problems), 1)

    def test_bad_latitude_is_refused(self):
        with self.assertRaises(records.PlanetError):
            records.build_registration(self.master, "FO4SFPlanetProbe.esm", 0x809, latitude=2.0)


class HelperTests(unittest.TestCase):
    def test_biome_round_trip_and_bad_sizes(self):
        b = records.parse_biome(pf.biome(0x1234, fauna=(1, 2), flora=(3,)))
        self.assertEqual((b["biome"], b["fauna"], len(b["flora"])), (0x1234, [1, 2], 1))
        self.assertEqual(records.pack_biome(b), pf.biome(0x1234, fauna=(1, 2), flora=(3,)))
        with self.assertRaises(records.PlanetError):
            records.parse_biome(pf.biome(0x1234) + b"\0")
        with self.assertRaises(records.PlanetError):
            records.parse_biome(b"\0" * 7)

    def test_tag_and_full_name_insertion(self):
        self.assertEqual(records.tag("FO4SF Probe-1!"), "FO4SFProbe1")
        with self.assertRaises(records.PlanetError):
            records.tag("  ")
        subs = records.set_full_name([(b"EDID", b"A\0"), (b"DATA", b"")], "Name")
        self.assertEqual([s for s, _ in subs], [b"EDID", b"BFCB", b"FULL", b"BFCE", b"DATA"])

    def test_check_keywords_uses_names(self):
        names = {fid: name for name, fid in records.KEYWORDS.items()}
        moved = dict(names)
        del moved[records.KEYWORDS["LocTypeOrbit"]]
        moved[0x00ABCDEF] = "LocTypeOrbit"
        kw, notes = records.check_keywords(moved)
        self.assertEqual(kw["LocTypeOrbit"], 0x00ABCDEF)
        self.assertEqual(len(notes), 1)
        del moved[0x00ABCDEF]
        with self.assertRaises(records.PlanetError):
            records.check_keywords(moved)


if __name__ == "__main__":
    unittest.main()
