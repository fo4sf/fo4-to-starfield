"""src/fo4sf/planet/records.py: our star system's master (FO4SFPlanet.esm) and the registration override, cloned from
tests/planet_fixture.py's synthetic Starfield.esm (no game data), then read back with the raw reader."""
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
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.sf = os.path.join(self.tmp.name, "Starfield.esm")
        pf.write_starfield(self.sf, houdini=70000)            # a PCCC above 65,535 bytes: written with XXXX

    def build(self, opts=None, other=()):
        with esm.Plugin(self.sf) as sf:
            w, rep = records.build_master(sf, opts, other)
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

    def test_master_passes_its_check_and_holds_six_records(self):
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
