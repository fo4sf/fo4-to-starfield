"""src/fo4sf/planet/census.py on tests/planet_fixture.py's synthetic Starfield.esm with its worlds, and a synthetic
built-in Creation (no game data): the records the probe copies, LC172World's references and links, Sol's ids and
their precedent, the arrivals."""
import os
import shutil
import struct
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "src"))
import planet_fixture as pf  # noqa: E402
from fo4sf.planet import census, esm  # noqa: E402


class CensusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="fo4sf-census-")
        cls.data = os.path.join(cls.tmp, "Data")
        os.makedirs(cls.data)
        cls.sf = os.path.join(cls.data, "Starfield.esm")
        pf.write_starfield(cls.sf, census=True)
        # a Creation adding a station to Jemison's system (and a body in Sol whose id reads negative) and overriding
        # Jemison's system location (as SFBGS00D.esm does Algorab's); a DLC master; a mod with a star of its own, a
        # moon in Sol, a body without a GNAM, an overlay world naming Sol's planet 13 (as one on another plugin's
        # planet would) and an override of Earth's location; and our own master, registration and probe plugin from
        # an earlier install (skipped: their records are the ones rebuilt)
        pf.write_creation(os.path.join(cls.data, "SFBGS00X.esm"),
                          bodies=[("CreationStationPlanetData", "Creation Station", (pf.JEMISON_SYSTEM, 0, 3)),
                                  ("UnsetPlanetData", "Unset", (pf.SOL_SYSTEM, 0, 0xFFFFFFFF))],
                          overrides=[0x00018001])
        pf.write_creation(os.path.join(cls.data, "ShatteredSpace.esm"), system_id=0x1F0F1, position=(41.0, 40.0, 4.0))
        pf.write_creation(os.path.join(cls.data, "SomeMod.esp"), system_id=0x1F0F2, position=(42.0, 40.0, 4.0),
                          bodies=[("ModMoonPlanetData", "Mod Moon", (pf.SOL_SYSTEM, 3, 11)),
                                  ("ModNoGnamPlanetData", "No GNAM", None)],
                          own_index=0xFD, overrides=[0x00018010], overlay=("ModOverlayWorld", pf.SOL_SYSTEM, 13))
        pf.write_creation(os.path.join(cls.data, "FO4SFPlanet.esm"), system_id=0xF04F1, position=(2.0, 2.0, 1.0),
                          bodies=[("OldProbePlanetData", "Old Probe", (pf.SOL_SYSTEM, 0, 30))])
        pf.write_creation(os.path.join(cls.data, "FO4SFPlanetProbe_Reg.esm"), system_id=0xF04F2,
                          position=(3.0, 2.0, 1.0),
                          bodies=[("OldProbePlanetData", "Old Probe", (pf.SOL_SYSTEM, 0, 31))])
        pf.write_creation(os.path.join(cls.data, "FO4SFPlanetProbe.esm"), system_id=0xF04F3, position=(4.0, 2.0, 1.0),
                          overlay=("FO4SF_PlanetProbeWorld", pf.SOL_SYSTEM, 32))
        for name in ("NotAPlugin.esm", "SFBGS00Y.esm"):
            with open(os.path.join(cls.data, name), "wb") as f:
                f.write(b"junk")
        with open(os.path.join(cls.data, "readme.txt"), "w", encoding="utf-8") as f:
            f.write("not a plugin")
        os.makedirs(os.path.join(cls.data, "Strings"))
        cls.rep = census.run(cls.sf, cls.data)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def test_templates_and_bases_by_editor_id(self):
        t = self.rep["templates"]
        self.assertEqual((t["world"]["edid"], t["block"]["edid"], t["location"]["edid"]),
                         ("LC172World", "OverlayBlockLC172World", "LC172WorldLocation"))
        self.assertEqual(t["world"]["overlay"], (0, 4, 0x102382))
        self.assertEqual(t["block"]["dnam"], [3, 3])
        self.assertEqual(t["location"]["lcpr_rows"], 1)
        self.assertEqual(t["bases"], {"XMarker": "0000003B", "COCMarkerHeading": "00000032",
                                      "EncCitizen01Template": "002B211C"})

    def test_lc172_references_links_and_coc_marker(self):
        lc = self.rep["lc172"]
        self.assertEqual(lc["references"], {"REFR persistent flag - - -": 1, "REFR persistent flag XLCN - LCPR": 1,
                                            "REFR temporary noflag - - -": 1, "ACHR temporary noflag XLCN - -": 1})
        self.assertEqual(lc["coc_marker"]["group"], "persistent")
        self.assertFalse(lc["coc_marker"]["in_lcpr"])
        for got, want in zip(lc["coc_marker"]["pos"], pf.LC172_COC_POS):
            self.assertAlmostEqual(got, want, places=4)
        self.assertEqual(lc["coc_cells"], [("LC172Ext01", "003807C1", [0, 0], "003807C2")])
        self.assertNotIn("warning", lc)

    def test_mars_new_atlantis_temp_jemison_and_plugin_stars(self):
        r = self.rep
        self.assertEqual(r["mars"]["master_worldspaces"], [(-0.0431, -0.0879, "0002DF8C")])
        self.assertTrue(r["new_atlantis"]["biome_in_planet_biomes"])
        self.assertEqual(r["overlay_worlds"]["count"], 2)
        self.assertEqual([o[1] for o in r["overlay_worlds"]["on_template_planet"]], ["NewAtlantis"])
        self.assertEqual(r["temp_jemison"]["world"]["overlay"], None)
        self.assertEqual(r["planet_biomes"], ["0007F88A", "000FD00D"])
        st = r["plugin_stars"]
        self.assertEqual(st["plugins"], ["SFBGS00X.esm", "ShatteredSpace.esm", "SomeMod.esp"])
        self.assertEqual([u.split(":")[0] for u in st["unreadable"]], ["NotAPlugin.esm", "SFBGS00Y.esm"])
        self.assertEqual(st["stars"], [("SFBGS00X.esm CreationStar", 0x1F0F0, [40.0, 40.0, 4.0]),
                                       ("ShatteredSpace.esm CreationStar", 0x1F0F1, [41.0, 40.0, 4.0]),
                                       ("SomeMod.esp CreationStar", 0x1F0F2, [42.0, 40.0, 4.0])])

    def test_sol_ids_and_their_precedent(self):
        sol = self.rep["sol"]
        self.assertEqual(sol["star"], {"formid": f"{pf.SOL_STAR:08X}", "edid": "Sol", "name": "Sol", "system_id": 0})
        self.assertEqual((sol["system_location"]["edid"], sol["system_location"]["parent"]), ("SSol", "0001A53A"))
        self.assertEqual([b[1] for b in sol["bodies"]], ["EarthPlanetData", "LunaPlanetData", "MarsPlanetData",
                                                         "UnsetPlanetData", "ModMoonPlanetData"])
        self.assertEqual(sol["overlay_worlds"], [["Starfield.esm", "LC172World", 0, pf.MARS_PLANET_ID],
                                                 ["SomeMod.esp", "ModOverlayWorld", 0, 13]])
        self.assertEqual((sol["free_planet_id"], sol["why"]),
                         (14, "SomeMod.esp overlay world ModOverlayWorld names planet id 13"))
        self.assertEqual(sol["location_ynams"], [0, 3, 6, 7])
        self.assertEqual(sol["not_counted"], {"ids_unset": [["SFBGS00X.esm", "UnsetPlanetData", 0xFFFFFFFF]],
                                              "bodies_without_gnam": [["SomeMod.esp", "ModNoGnamPlanetData"]]})
        added = sol["precedent"]["bodies_added_by_plugins"]
        self.assertEqual(added, [("SFBGS00X.esm", "CreationStationPlanetData", "Creation Station",
                                  [pf.JEMISON_SYSTEM, 0, 3], 2),
                                 ("SFBGS00X.esm", "UnsetPlanetData", "Unset", [0, 0, 0xFFFFFFFF], 6),
                                 ("SomeMod.esp", "ModMoonPlanetData", "Mod Moon", [0, 3, 11], 6)])
        # only the override of a star system location: Earth's planet location is overridden too, and left out
        self.assertEqual(sol["precedent"]["system_location_overrides"],
                         [{"plugin": "SFBGS00X.esm", "formid": "00018001", "edid": "SAlphaCentauri",
                           "changed": [("KSIZ", "01000000", "02000000"), ("KWDA", "9f140000", "9f14000090190600")]}])
        bodies = self.rep["plugin_bodies"]
        self.assertEqual(sorted({b[0] for b in bodies["planets"]}), ["SFBGS00X.esm", "SomeMod.esp"])
        self.assertEqual(bodies["locations"], [("SFBGS00X.esm", "SAlphaCentauri", pf.JEMISON_SYSTEM, 0,
                                                ["0000149F", "00061990"], "00018001", False),
                                               ("SomeMod.esp", "SSol_PEarth", 0, 3,
                                                ["000014A0", "00070A54", "00061990"], "00018010", False)])

    def test_plugin_bodies_skips_our_own_plugins_and_keeps_overrides_apart(self):
        b = census.plugin_bodies(self.data)
        self.assertEqual(b["read"], ["SFBGS00X.esm", "ShatteredSpace.esm", "SomeMod.esp"])
        self.assertEqual(b["overlays"], [("SomeMod.esp", "ModOverlayWorld", 0, 13)])     # not FO4SFPlanetProbe.esm's
        self.assertEqual(b["planets_without_gnam"], [("SomeMod.esp", "ModNoGnamPlanetData")])
        self.assertEqual([(src, f"{f:06X}", rec.edid, idx) for src, f, rec, idx in b["location_overrides"]],
                         [("SFBGS00X.esm", "018001", "SAlphaCentauri", 0), ("SomeMod.esp", "018010", "SSol_PEarth", 0)])
        with esm.Plugin(self.sf) as sf:
            self.assertEqual(census.overlay_worlds(sf, "Starfield.esm"),
                             [("Starfield.esm", "LC172World", 0, pf.MARS_PLANET_ID),
                              ("Starfield.esm", "NewAtlantis", pf.JEMISON_SYSTEM, pf.JEMISON_PLANET)])

    def test_sol_without_a_system_location_is_a_finding_not_a_crash(self):
        d = os.path.join(self.tmp, "nosol")
        os.makedirs(d)
        path = os.path.join(d, "Starfield.esm")
        with open(self.sf, "rb") as f:
            raw = f.read()
        k = struct.pack("<I", 0x0000149F)                 # SSol's keyword turned into another one: no Sol location
        at = raw.index(b"SSol\0")
        at = raw.index(k, at)
        with open(path, "wb") as f:
            f.write(raw[:at] + struct.pack("<I", 0x00016504) + raw[at + 4:])
        rep = census.run(path)
        self.assertIn("0 star system locations with XNAM 0", rep["sol"]["error"])
        self.assertNotIn("plugin_bodies", rep)

    def test_arrivals(self):
        self.assertEqual([(a["label"], a["coc"]) for a in census.arrivals(self.rep)],
                         [("lc172", "LC172Ext01"), ("temp_jemison", "TempJemisonExt"),
                          ("new_atlantis", "NewAtlanticExt01")])
        self.assertEqual([a["label"] for a in census.arrivals({"lc172": {}})], ["lc172"])

    def test_a_renamed_template_stops_the_census(self):
        d = os.path.join(self.tmp, "renamed")
        os.makedirs(d)
        path = os.path.join(d, "Starfield.esm")
        with open(self.sf, "rb") as f:
            raw = f.read()
        with open(path, "wb") as f:
            f.write(raw.replace(b"OverlayBlockLC172World\0", b"OverlayBlockLC999World\0"))
        with self.assertRaises(census.CensusError):
            census.run(path)

    def test_find_records_reads_only_the_wanted_ids(self):
        with esm.Plugin(self.sf) as p:
            got = census.find_records(p, "STAT", [0x3B, 0x99])
        self.assertEqual(list(got), [0x3B])


if __name__ == "__main__":
    unittest.main()
