"""sf_ground_cover: a synthetic Starfield-shaped plugin (WRLD -> BIOM -> LTEX + GCVR -> GRAS)."""
import importlib.util
import os
import struct
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location("sf_ground_cover", os.path.join(REPO, "scripts", "terrain", "sf_ground_cover.py"))
gc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gc)


def sub(s, d):
    return s + struct.pack("<H", len(d)) + d


def rec(t, fid, body):
    return t + struct.pack("<III", len(body), 0, fid) + b"\0" * 8 + body


def grp(label, body, gtype=0):
    return b"GRUP" + struct.pack("<I", 24 + len(body)) + label + struct.pack("<i", gtype) + b"\0" * 8 + body


def z(s):
    return s.encode() + b"\0"


def u32(v):
    return struct.pack("<I", v)


def write(path, data):
    with open(path, "wb") as f:
        f.write(data)


def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def addon(master, gcvr_flags=0):
    """An add-on over `master`: overrides GrassA's model and the ground cover (optionally flagged deleted)."""
    tes4 = rec(b"TES4", 0, sub(b"HEDR", b"\0" * 12) + sub(b"MAST", z(master)) + sub(b"DATA", b"\0" * 8))
    body = sub(b"EDID", z("GCMeadow")) + sub(b"GNAM", u32(0x50)) + sub(b"DNAM", struct.pack("<h", -1))
    gcvr = b"GCVR" + struct.pack("<III", len(body), gcvr_flags, 0x40) + b"\0" * 8 + body
    gras = rec(b"GRAS", 0x50, sub(b"EDID", z("GrassA")) + sub(b"MODL", z("grass/a2.nif")))
    return tes4 + grp(b"GCVR", gcvr) + grp(b"GRAS", gras)


def plugin():
    children = grp(u32(0x10), grp(b"\0" * 4, rec(b"CELL", 0x11, sub(b"EDID", z(""))), 4), 1)   # as Starfield.esm: cells
    wrld = grp(b"WRLD", rec(b"WRLD", 0x10, sub(b"EDID", z("TestCity")) + sub(b"BNAM", u32(0x60))   # component SFBK first
                            + sub(b"DATA", b"\x01") + sub(b"BNAM", u32(0x20)))
               + children)
    biom = grp(b"BIOM", rec(b"BIOM", 0x20, sub(b"EDID", z("TestBiome"))
                            + sub(b"LNAM", u32(7) + u32(0x30) + u32(0x40))
                            + sub(b"ANAM", u32(7) + u32(0x31) + u32(0))))
    ltex = grp(b"LTEX", rec(b"LTEX", 0x30, sub(b"EDID", z("LGrass")) + sub(b"BNAM", z("terrain/grass.mat")))
               + rec(b"LTEX", 0x31, sub(b"EDID", z("LRock")) + sub(b"BNAM", z("terrain/rock.mat"))))
    gcvr = grp(b"GCVR", rec(b"GCVR", 0x40, sub(b"EDID", z("GCMeadow")) + sub(b"GNAM", u32(0x50))
                            + sub(b"DNAM", struct.pack("<h", -1)) + sub(b"GNAM", u32(0x51)) + sub(b"DNAM", struct.pack("<h", 40))
                            + sub(b"LNAM", u32(0x30)) + sub(b"YNAM", struct.pack("<f", 28.0))))
    gras = grp(b"GRAS", rec(b"GRAS", 0x50, sub(b"EDID", z("GrassA")) + sub(b"MODL", z("grass/a.nif")) + sub(b"DNAM", b"\x01\x02"))
               + rec(b"GRAS", 0x51, sub(b"EDID", z("GrassB")) + sub(b"MODL", z("grass/b.nif"))))
    return rec(b"TES4", 0, sub(b"HEDR", b"\0" * 12)) + wrld + biom + ltex + gcvr + gras


class GroundCoverTest(unittest.TestCase):
    def test_world_biome_ground_cover_chain(self):
        with tempfile.TemporaryDirectory() as d:
            esm = os.path.join(d, "Test.esm")
            write(esm, plugin())
            out = gc.main([os.path.join(d, "out.json"), esm, "--worlds", "testcity,Nowhere"])
        w = out["worlds"]["testcity"]
        self.assertEqual((w["biome"], w["data_flags"]), ("Test.esm:000020", 1))
        self.assertEqual(w["bnam_all"], ["Test.esm:000060", "Test.esm:000020"])
        self.assertIsNone(out["worlds"]["Nowhere"])
        t = out["biomes"]["Test.esm:000020"]["terrain"]
        self.assertEqual([(x["kind"], x["mask"], x["land_texture_edid"], x["ground_cover_edid"]) for x in t],
                         [("main", 7, "LGrass", "GCMeadow"), ("alternate", 7, "LRock", None)])
        g = out["ground_covers"]["Test.esm:000040"]
        self.assertEqual([(x["grass_edid"], x["density"]) for x in g["grasses"]], [("GrassA", -1), ("GrassB", 40)])
        self.assertEqual((g["land_textures"], g["painted_threshold"]), (["Test.esm:000030"], 28.0))
        self.assertEqual(out["grasses"]["Test.esm:000050"], {"edid": "GrassA", "model": "grass/a.nif", "dnam_hex": "0102"})
        self.assertEqual(out["land_textures"]["Test.esm:000031"]["material"], "terrain/rock.mat")

    def test_output_alias_of_input_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            esm = os.path.join(d, "Test.esm")
            write(esm, plugin())
            before = read_bytes(esm)
            with self.assertRaises(SystemExit):
                gc.main([esm, esm, "--worlds", "TestCity"])
            self.assertEqual(read_bytes(esm), before)

    def test_plugin_names_match_without_case(self):
        for master_spelling, file_spelling in (("test.esm", "Test.esm"), ("Test.esm", "test.esm")):
            with tempfile.TemporaryDirectory() as d:
                esm, add = os.path.join(d, file_spelling), os.path.join(d, "Addon.esm")
                write(esm, plugin())
                write(add, addon(master_spelling))
                out = gc.main([os.path.join(d, "out.json"), esm, add, "--worlds", "TestCity"])
            key = file_spelling + ":000050"
            self.assertEqual(out["worlds"]["TestCity"]["biome"], file_spelling + ":000020")
            self.assertEqual(out["grasses"][key]["model"], "grass/a2.nif")        # the add-on's override wins
            self.assertEqual(out["totals"]["GRAS"], 2)

    def test_same_plugin_twice_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = os.path.join(d, "Test.esm"), os.path.join(d, "sub", "test.esm")
            os.mkdir(os.path.join(d, "sub"))
            write(a, plugin())
            write(b, plugin())
            with self.assertRaises(SystemExit):
                gc.main([os.path.join(d, "out.json"), a, b, "--worlds", "TestCity"])

    def test_winning_deleted_record_shadows_and_is_not_followed(self):
        with tempfile.TemporaryDirectory() as d:
            esm, add = os.path.join(d, "Test.esm"), os.path.join(d, "Addon.esm")
            write(esm, plugin())
            write(add, addon("Test.esm", gcvr_flags=0x20))
            out = gc.main([os.path.join(d, "out.json"), esm, add, "--worlds", "TestCity"])
        main = out["biomes"]["Test.esm:000020"]["terrain"][0]
        self.assertEqual((main["ground_cover"], main["ground_cover_status"]), ("Test.esm:000040", "deleted"))
        g = out["ground_covers"]["Test.esm:000040"]
        self.assertTrue(g["deleted"])
        self.assertEqual(g["grasses"], [])                                     # not traversed, base not resurrected
        self.assertNotIn("Test.esm:000051", out["grasses"])
        self.assertEqual((out["totals"]["GCVR"], out["deleted"]["GCVR"]), (0, 1))


if __name__ == "__main__":
    unittest.main()
