"""fo4_world_survey: a synthetic plugin (one world, one cell, LAND with a texture layer, one tree reference)."""
import importlib.util
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "src"))
from fo4sf import fo4land as fl  # noqa: E402

spec = importlib.util.spec_from_file_location("fo4_world_survey", os.path.join(REPO, "scripts", "terrain", "fo4_world_survey.py"))
survey = importlib.util.module_from_spec(spec)
spec.loader.exec_module(survey)


def sub(s, d):
    return s + struct.pack("<H", len(d)) + d


def rec(t, fid, body):
    return t + struct.pack("<III", len(body), 0, fid) + b"\0" * 8 + body


def grp(label, gt, body):
    return b"GRUP" + struct.pack("<I", 24 + len(body)) + label + struct.pack("<i", gt) + b"\0" * 8 + body


def z(s):
    return s.encode() + b"\0"


SCRIPT = os.path.join(REPO, "scripts", "terrain", "fo4_world_survey.py")


def plugin(masters=(), persistent=False):
    hdr = sub(b"HEDR", b"\0" * 12) + b"".join(sub(b"MAST", z(m)) + sub(b"DATA", b"\0" * 8) for m in masters)
    stat = grp(b"STAT", 0, rec(b"STAT", 0x100, sub(b"EDID", z("TreeMaple01"))
                                + sub(b"MODL", z("Landscape\\Trees\\TreeMaple01.nif"))))
    gras = grp(b"GRAS", 0, rec(b"GRAS", 0x200, sub(b"EDID", z("GrassA")) + sub(b"MODL", z("Landscape\\Grass\\a.nif"))))
    ltex = grp(b"LTEX", 0, rec(b"LTEX", 0x300, sub(b"EDID", z("LDirt")) + sub(b"TNAM", struct.pack("<I", 0x400))
                                + sub(b"GNAM", struct.pack("<I", 0x200))))
    land = rec(b"LAND", 0x501, sub(b"VHGT", fl.encode_vhgt(10.0, np.zeros((33, 33), int)))
               + sub(b"BTXT", struct.pack("<IBBH", 0x300, 0, 0, 0)))
    refr = rec(b"REFR", 0x502, sub(b"NAME", struct.pack("<I", 0x100)) + sub(b"DATA", b"\0" * 24))
    cell = rec(b"CELL", 0x500, sub(b"XCLC", struct.pack("<iiI", 3, -2, 0)))
    cc = grp(struct.pack("<I", 0x500), 6, grp(struct.pack("<I", 0x500), 9, land + refr))
    pers = b""
    if persistent:   # the world's persistent cell sits directly in the world children group, XCLC (0, 0)
        pref = rec(b"REFR", 0x702, sub(b"NAME", struct.pack("<I", 0x100)) + sub(b"DATA", b"\0" * 24))
        pers = (rec(b"CELL", 0x700, sub(b"XCLC", struct.pack("<iiI", 0, 0, 0)))
                + grp(struct.pack("<I", 0x700), 6, grp(struct.pack("<I", 0x700), 8, pref)))
    wc = grp(struct.pack("<I", 0x600), 1, pers + grp(b"\0" * 4, 4, grp(b"\0" * 4, 5, cell + cc)))
    wrld = grp(b"WRLD", 0, rec(b"WRLD", 0x600, sub(b"EDID", z("TestWorld"))) + wc)
    return rec(b"TES4", 0, hdr) + stat + gras + ltex + wrld


class SurveyTest(unittest.TestCase):
    def test_world_heights_textures_grass_and_trees(self):
        with tempfile.TemporaryDirectory() as d:
            esm, out = os.path.join(d, "Test.esm"), os.path.join(d, "out.json")
            open(esm, "wb").write(plugin())
            survey.main([out, esm])
            res = json.load(open(out))
        (w,) = res["worlds"]
        self.assertEqual((w["edid"], w["cells"], w["land"], w["xr"], w["yr"]), ("TestWorld", 1, 1, [3, 3], [-2, -2]))
        self.assertAlmostEqual(w["zmin_m"], 80.0 / 70.0, places=2)      # offset 10 x 8 units
        self.assertEqual(w["refs_by_category"], {"tree": 1})
        self.assertEqual(w["ltex_named"], {"Test.esm:000300": ["LDirt", 1]})
        self.assertEqual(res["ltex"]["Test.esm:000300"]["grass"], ["Test.esm:000200"])
        self.assertEqual(res["grass"]["Test.esm:000200"]["model"], "Landscape\\Grass\\a.nif")

    def test_master_index_resolves_to_the_master(self):
        with tempfile.TemporaryDirectory() as d:
            esm, out = os.path.join(d, "DLC.esm"), os.path.join(d, "out.json")
            open(esm, "wb").write(plugin(masters=("Fallout4.esm",)))
            res = survey.main([out, esm])
        # ids with index byte 00 belong to the first master, not to the plugin itself
        self.assertIn("Fallout4.esm:000300", res["ltex"])
        self.assertEqual(res["worlds"][0]["fid"], "Fallout4.esm:000600")

    def test_persistent_cell_is_not_a_tile(self):
        with tempfile.TemporaryDirectory() as d:
            esm, out = os.path.join(d, "Test.esm"), os.path.join(d, "out.json")
            open(esm, "wb").write(plugin(persistent=True))
            (w,) = survey.main([out, esm])["worlds"]
            with fl.Plugin(esm) as p:
                world = p.read_world("TestWorld")
        self.assertEqual(sorted(world["cells"]), [(3, -2)])            # the reader this repo already trusts
        self.assertEqual((w["cells"], w["xr"], w["yr"]), (1, [3, 3], [-2, -2]))
        self.assertTrue(w["persistent_cell"])
        self.assertEqual(w["refs"], 2)                                 # its persistent reference still counts


class CliAliasTest(unittest.TestCase):
    """The survey only reads: an output that names an input is refused before anything is written."""

    def run_cli(self, cwd, *args):
        return subprocess.run([sys.executable, SCRIPT, *args], cwd=cwd, capture_output=True, text=True)

    def check_refused(self, d, esm, out_arg, extra=()):
        before = open(esm, "rb").read()
        r = self.run_cli(d, out_arg, esm, *extra)
        self.assertNotEqual(r.returncode, 0, r.stdout)
        self.assertIn("refused", r.stderr)
        self.assertEqual(open(esm, "rb").read(), before)
        self.assertFalse(os.path.exists(os.path.join(d, out_arg) + ".tmp"))

    def test_distinct_output_leaves_the_input_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            esm = os.path.join(d, "Test.esm")
            open(esm, "wb").write(plugin())
            before = open(esm, "rb").read()
            r = self.run_cli(d, os.path.join(d, "out.json"), esm)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(open(esm, "rb").read(), before)
            self.assertEqual(json.load(open(os.path.join(d, "out.json")))["worlds"][0]["edid"], "TestWorld")

    def test_same_path_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            esm = os.path.join(d, "Test.esm")
            open(esm, "wb").write(plugin())
            self.check_refused(d, esm, esm)

    def test_relative_alias_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            os.mkdir(os.path.join(d, "sub"))
            esm = os.path.join(d, "Test.esm")
            open(esm, "wb").write(plugin())
            self.check_refused(d, esm, os.path.join("sub", "..", "Test.esm"))

    def test_hard_link_is_refused_and_existing_output_kept(self):
        with tempfile.TemporaryDirectory() as d:
            esm, link = os.path.join(d, "Test.esm"), os.path.join(d, "out.json")
            open(esm, "wb").write(plugin())
            os.link(esm, link)
            self.check_refused(d, esm, link)
            self.assertEqual(open(link, "rb").read(), open(esm, "rb").read())

    def test_second_input_alias_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            esm, dlc = os.path.join(d, "Test.esm"), os.path.join(d, "DLC.esm")
            open(esm, "wb").write(plugin())
            shutil.copy(esm, dlc)
            before = open(dlc, "rb").read()
            r = self.run_cli(d, dlc, esm, dlc)
            self.assertNotEqual(r.returncode, 0)
            self.assertEqual(open(dlc, "rb").read(), before)


if __name__ == "__main__":
    unittest.main()
