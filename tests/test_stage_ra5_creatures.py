"""scripts/probes/stage_ra5_creatures.py: ids, output folder rule, batch files, rig mapping, root motion resampling,
install / uninstall (synthetic; the live build is checked by the stager's own report)."""
import json
import math
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
for p in (str(ROOT / "src"), str(ROOT / "scripts" / "actors"), str(ROOT / "scripts" / "probes"), str(HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)

import convert_creature as cc  # noqa: E402
import stage_ra2_handy as ra2  # noqa: E402
import stage_ra5_creatures as ra5  # noqa: E402
from fo4sf import creature_race as cr  # noqa: E402

from test_convert_creature import roach  # noqa: E402


class TestIdsAndFolders(unittest.TestCase):
    def test_form_ids(self):
        seen = set()
        for k in ra5.ORDER:
            ids = ra5.form_ids(k)
            self.assertEqual(sorted(ids.values()), list(range(ids["RACE"], ids["RACE"] + 5)))
            self.assertFalse(seen & set(ids.values()))
            seen |= set(ids.values())
            self.assertIn(k, cr.CREATURES)
            self.assertTrue(all(e.startswith("FO4SF_") for e in ra5.edids(cr.CREATURES[k]).values()))
        self.assertEqual(ra5.form_ids("radroach")["NPC_"], 0x804)

    def test_out_dir_rule(self):
        self.assertEqual(ra5.check_out_dir(ra5.OUT), ra5.OUT.resolve())
        self.assertEqual(ra5.check_out_dir(ra5.OUT / "trial"), (ra5.OUT / "trial").resolve())
        for bad in (ra5.OWNER_TESTS / "robot-anim" / "E2", ra5.OWNER_TESTS, ra5.OWNER_TESTS / "RA5"):
            with self.assertRaises(ra5.Ra5Error):
                ra5.check_out_dir(bad)
        with self.assertRaises(ra2.Ra2Error):
            ra5.check_out_dir(ROOT / "out")
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(ra5.check_out_dir(Path(d)), Path(d).resolve())

    def test_bats(self):
        b = ra5.build_bats(list(ra5.ORDER))
        self.assertEqual(sorted(b), sorted(cr.CREATURES[k].bat for k in ra5.ORDER))
        self.assertIn("player.placeatme XX000804 1", b["ra5roach.txt"])
        self.assertIn("player.placeatme 1C000818 1", ra5.build_bats(["deathclaw"], 0x1C)["ra5claw.txt"])
        for f, text in b.items():
            self.assertNotRegex(f, "[mnvMNV]")
            self.assertNotIn("FO4SF_", text)


class TestRigMap(unittest.TestCase):
    def test_round_trip_and_world(self):
        s = roach()
        rig = cc.build_rig(s, rebase=["COM", "Pelivis", "Head"])
        bones = ra2.rig_bones_from_skeleton(rig.skel, keys=ra5.RIG_KEYS)
        src_bones = ra2.rig_bones_from_skeleton(rig.source, keys={})
        rm = ra5.RigMap(rig, bones)
        bind = [(b["translation"], b["rotation"]) for b in src_bones]
        mapped = rm.to_rig([bind])[0]
        for (t, q), b in zip(mapped, bones):
            self.assertLess(math.dist(t, b["translation"]), 1e-9)
            self.assertLess(ra5.aa.q_angle(q, b["rotation"]), 1e-6)
        pose = [list(bind)]
        pose[0][1] = ((bind[1][0][0], bind[1][0][1] + 0.05, bind[1][0][2]), ra5.aa.q_from_axis_angle((0, 0, 1), 0.3))
        pose[0][0] = ((0.4, 0.1, 0.0), ra5.aa.q_from_axis_angle((0, 0, 1), 0.2))
        rig_frames = rm.to_rig(pose)
        parents_src = [b["parent"] for b in src_bones]
        parents = [b["parent"] for b in bones]
        self.assertLess(ra5.world_difference(parents_src, pose, parents, rig_frames, rm.source_index), 1e-12)
        back = rm.to_source(rig_frames)
        for (t0, q0), (t1, q1) in zip(pose[0], back[0]):
            self.assertLess(math.dist(t0, t1), 1e-9)
            self.assertLess(ra5.aa.q_angle(q0, q1), 1e-6)
        rule, _bone = ra2.translation_rule_exposure(bones, rig_frames)
        self.assertLess(rule, 1e-9)          # Pelivis (the only bone moved) has an identity rest now

    def test_resample_root(self):
        r = ra5.resample_root([(0, 0, 0, 0), (70.0, 140.0, 0, math.pi / 2)], 5)
        self.assertEqual(len(r), 5)
        self.assertEqual(r[0], (0.0, 0.0, 0.0, 0.0))
        self.assertAlmostEqual(r[-1][0], 1.0)
        self.assertAlmostEqual(r[-1][1], 2.0)
        self.assertAlmostEqual(r[2][3], math.pi / 4)
        r3 = ra5.resample_root([(0, 0, 0, 0), (70, 0, 0, 0), (70, 70, 0, 0)], 5)
        self.assertAlmostEqual(r3[2][0], 1.0)
        self.assertAlmostEqual(r3[3][1], 0.5)
        with self.assertRaises(ra5.Ra5Error):
            ra5.resample_root([(0, 0, 0, 0)], 3)


class TestInstall(unittest.TestCase):
    def _tes4(self, path, flags=0x1):
        path.write_bytes(struct.pack("<4sIIIIHH", b"TES4", 0, flags, 0, 0, 0, 0))

    def _stage(self, d):
        stage, game = d / "stage", d / "game"
        (game / "Data").mkdir(parents=True)
        stage.mkdir()
        (stage / ra5.PLUGIN).write_bytes(b"esm")
        (stage / ra5.MAIN_BA2).write_bytes(b"ba2")
        (stage / "manifest.json").write_text(json.dumps({"creatures": ["radroach", "dog"]}), encoding="utf-8")
        self._tes4(game / "Data" / "Starfield.esm")
        self._tes4(game / "Data" / "A.esm")
        self._tes4(game / "Data" / "Light.esm", 0x201)
        return stage, game

    def test_install_uninstall_restores_plugins_txt(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            stage, game = self._stage(d)
            ptxt = d / "Plugins.txt"
            original = "﻿# comment\r\n*A.esm\r\n*Light.esm\r\n".encode("utf-8")
            ptxt.write_bytes(original)
            with mock.patch.object(ra5, "verify", return_value={}):
                rc = ra5.install(stage, game, ptxt, min_free_gb=0.0, check_running=False)
                self.assertEqual(rc["slot_hex"], "02")
                self.assertEqual(rc["form_ids"]["FO4SF_RA5RadroachTest"], "02000804")
                self.assertEqual(rc["form_ids"]["FO4SF_RA5DogTest"], "02000813")
                self.assertIn("player.placeatme 02000804 1", (game / "ra5roach.txt").read_text())
                self.assertIn("player.placeatme 02000813 1", (game / "ra5dog.txt").read_text())
                self.assertTrue(ptxt.read_text(encoding="utf-8-sig").rstrip().endswith("*" + ra5.PLUGIN))
                with self.assertRaises(ra5.Ra5Error):
                    ra5.install(stage, game, ptxt, min_free_gb=0.0, check_running=False)
                res = ra5.uninstall(game, ptxt, check_running=False)
            self.assertEqual(res["plugins_txt"], "restored byte for byte")
            self.assertEqual(ptxt.read_bytes(), original)
            self.assertEqual(sorted(p.name for p in game.iterdir()), ["Data"])
            self.assertEqual(sorted(p.name for p in (game / "Data").iterdir()), ["A.esm", "Light.esm", "Starfield.esm"])
            self.assertFalse((stage / ra5.BACKUP).exists())

    def test_refuses_to_overwrite_and_keeps_later_edits(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            stage, game = self._stage(d)
            ptxt = d / "Plugins.txt"
            ptxt.write_text("*A.esm\n", encoding="utf-8")
            (game / "ra5dog.txt").write_text("mine", encoding="utf-8")
            with mock.patch.object(ra5, "verify", return_value={}):
                with self.assertRaises(ra5.Ra5Error):
                    ra5.install(stage, game, ptxt, min_free_gb=0.0, check_running=False)
                self.assertEqual(ptxt.read_text(encoding="utf-8"), "*A.esm\n")     # rolled back
                self.assertFalse((game / "Data" / ra5.PLUGIN).exists())
                self.assertEqual((game / "ra5dog.txt").read_text(encoding="utf-8"), "mine")
                (game / "ra5dog.txt").unlink()
                ra5.install(stage, game, ptxt, min_free_gb=0.0, check_running=False)
                ptxt.write_text(ptxt.read_text(encoding="utf-8") + "*B.esm\n", encoding="utf-8")
                res = ra5.uninstall(game, ptxt, check_running=False)
            self.assertIn("only the appended line", res["plugins_txt"])
            self.assertEqual(ptxt.read_text(encoding="utf-8"), "*A.esm\n*B.esm\n")
            self.assertEqual(ra5.status(game), {"installed": False, "receipt": None})


if __name__ == "__main__":
    unittest.main()
