"""Tests for scripts/probes/stage_ra2_handy.py (robot-anim E: the RA2 Handy probe bundle).

    PYTHONPATH=src python -m unittest tests.test_stage_ra2_handy
"""
import json
import math
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT / "src"), str(ROOT / "scripts" / "probes"), str(ROOT / "scripts" / "actors")):
    if p not in sys.path:
        sys.path.insert(0, p)

import stage_ra2_handy as ra2  # noqa: E402
from fo4sf import actor_anim as aa  # noqa: E402
from fo4sf import handy_race as hr  # noqa: E402
from fo4sf.planet import esm  # noqa: E402

E_OUT = ra2.OUT                      # the pre-fix bundle (robot-anim E)
E2_OUT = ra2.OUT.parent / "E2"       # the fixed bundle (rebased COM, safe names, DirectAt, Codsworth's parts)


def _bones():
    """A small rig whose bind is mirror-symmetric in world space (as the Handy's): Root, COM turned -90 deg about Y
    (as the Handy's, so its local -Z is world +X), a centre arm |0 and side arms |1 (world +X) / |2 (world -X) whose
    frames are reflections of each other (the child of |2 points along local -X)."""
    s = math.sqrt(0.5)
    com_q = (0, -s, 0, s)
    q1 = aa.q_norm((0.1, 0.2, 0.5, 0.8))
    w1 = aa.q_mul(com_q, q1)
    q2 = aa.q_norm(aa.q_mul(aa.q_conj(com_q), ra2._mquat(w1)))
    spec = [("Root", -1, (0, 0, 0), (0, 0, 0, 1)), ("COM", 0, (0, 0, 1.0), com_q),
            ("Arm1|0", 1, (0, 0.2, 0), (0, 0, 0, 1)), ("Arm1|1", 1, (0, -0.1, -0.17), q1),
            ("Arm1|2", 1, (0, -0.1, 0.17), q2), ("Arm2|1", 3, (0.3, 0, 0), (0, 0, 0, 1)),
            ("Arm2|2", 4, (-0.3, 0, 0), (0, 0, 0, 1))]
    return aa.validate_bones([{"name": n, "parent": p, "translation": t, "rotation": q} for n, p, t, q in spec])


def _frames(bones, n=5):
    out = []
    for f in range(n):
        fr = [(b["translation"], b["rotation"]) for b in bones]
        a = 0.1 * f
        fr[3] = (fr[3][0], aa.q_norm(aa.q_mul(fr[3][1], aa.q_from_axis_angle((0, 1, 0), a))))
        fr[5] = ((0.3 + 0.01 * f, 0.02 * f, 0.0), aa.q_from_axis_angle((1, 0, 0), 2 * a))
        fr[1] = ((0.01 * f, 0.0, 1.0 + 0.02 * f), fr[1][1])
        out.append(fr)
    return out


def _close(test, a, b, tol=1e-9):
    for fa, fb in zip(a, b):
        for (ta, qa), (tb, qb) in zip(fa, fb):
            test.assertLess(max(abs(x - y) for x, y in zip(ta, tb)), tol)
            test.assertLess(aa.q_angle(qa, qb), 1e-6)


class TestMirror(unittest.TestCase):
    def test_pair_names(self):
        self.assertEqual(ra2.pair_name("Arm3|1"), "Arm3|2")
        self.assertEqual(ra2.pair_name("EyeArm1|2"), "EyeArm1|1")
        self.assertEqual(ra2.pair_name("Arm1|0"), "Arm1|0")
        self.assertEqual(ra2.pair_name("LClavicle"), "RClavicle")
        self.assertEqual(ra2.pair_name("C-HandLeft"), "C-HandRight")
        self.assertEqual(ra2.pair_name("Ring"), "Ring")

    def test_pairs_need_matching_parents(self):
        b = _bones()
        names, parents = [x["name"] for x in b], [x["parent"] for x in b]
        self.assertEqual(ra2.pair_indices(names, parents), [0, 1, 2, 4, 3, 6, 5])
        bad = list(parents)
        bad[6] = 3      # Arm2|2 under the right arm
        with self.assertRaises(ra2.Ra2Error):
            ra2.pair_indices(names, bad)

    def test_bind_is_fixed_and_mirror_is_an_involution(self):
        b = _bones()
        parents = [x["parent"] for x in b]
        pairs = ra2.pair_indices([x["name"] for x in b], parents)
        bind = [(x["translation"], x["rotation"]) for x in b]
        _close(self, ra2.mirror_frames([bind], bind, parents, pairs), [bind])
        fr = _frames(b)
        twice = ra2.mirror_frames(ra2.mirror_frames(fr, bind, parents, pairs), bind, parents, pairs)
        _close(self, twice, fr)

    def test_mirror_reflects_world_positions(self):
        b = _bones()
        parents = [x["parent"] for x in b]
        pairs = ra2.pair_indices([x["name"] for x in b], parents)
        bind = [(x["translation"], x["rotation"]) for x in b]
        fr = _frames(b)
        mir = ra2.mirror_frames(fr, bind, parents, pairs)
        for f in range(len(fr)):
            w, wm = ra2.world_of(parents, fr[f]), ra2.world_of(parents, mir[f])
            for j, i in enumerate(pairs):
                x, y, z = w[i][0]
                self.assertLess(math.dist((-x, y, z), wm[j][0]), 1e-9)


class TestClipOps(unittest.TestCase):
    def _clip(self, n=20, step_deg=10.0):
        b = _bones()
        bind = [(x["translation"], x["rotation"]) for x in b]
        root = [(0.0, 0.0, 0.0, math.radians(step_deg * f)) for f in range(n)]
        return ra2.Clip([list(bind) for _ in range(n)], root, [(0.1, "HitFrame"), (0.5, "weaponSwing")], "x").finish(), b

    def test_crop_turn_ends_exactly(self):
        clip, _b = self._clip(step_deg=7.0)
        c = ra2.crop_turn(clip, 90.0)
        self.assertEqual(c.n, 14)            # 13 x 7 = 91 deg is the first frame past 90
        self.assertAlmostEqual(math.degrees(c.root[-1][3]), 90.0, places=9)
        self.assertEqual([t for t, _ in c.annotations], [0.1, ])
        q = c.frames[-1][0][1]
        self.assertAlmostEqual(math.degrees(2 * math.atan2(q[2], q[3])), 90.0, places=6)
        with self.assertRaises(ra2.Ra2Error):
            ra2.crop_turn(clip, 400.0)

    def test_mirror_clip_negates_root(self):
        clip, b = self._clip()
        pairs = ra2.pair_indices([x["name"] for x in b], [x["parent"] for x in b])
        clip.root = [(0.1 * f, 0.2 * f, 0.0, r[3]) for f, r in enumerate(clip.root)]
        m = ra2.mirror_clip(clip.finish(), b, pairs)
        self.assertEqual(m.root[3][:2], (-0.30000000000000004, 0.6000000000000001))
        self.assertAlmostEqual(m.root[3][3], -clip.root[3][3])

    def test_root_velocity_and_events(self):
        clip, _b = self._clip(n=31)
        c = ra2.with_root_velocity(clip, (0.0, 1.09, 0.0), "test")
        self.assertAlmostEqual(c.root[-1][1], 1.09)
        self.assertEqual(c.root[-1][3], 0.0)
        cm = hr.ClipMap("MeleeAttack01", "MeleeAttack01", "Claw\\Attack_1.hkx", add_events=(("end", "SetOrientEnd"),))
        self.assertEqual(ra2.clip_events(cm, c), [(3, "HitFrame", ""), (15, "weaponSwing", ""), (30, "SetOrientEnd", "")])


class TestRecords(unittest.TestCase):
    def _npc(self, template_flags=0x4902):
        acbs = struct.pack("<IhhHHhH", 0x40010142, 0, 6, 0, 0, 35, template_flags)
        return esm.Record(b"NPC_", 0x4297C, [
            (b"EDID", esm.zbytes("OutpostRobotMiniBotA_Garden")), (b"VMAD", b"\x06\x00"), (b"ACBS", acbs),
            (b"SNAM", b"\x30\x6c\x10\x00\x00"), (b"SNAM", b"\x31\x6c\x10\x00\x00"), (b"RNAM", struct.pack("<I", 0x227705)),
            (b"WNAM", struct.pack("<I", 0x3FFD3A)), (b"AIDT", bytes.fromhex("00043203000200")),
            (b"OBND", b"\0" * 24), (b"FULL", b"\x7b\x1b\x03\x00")], flags=esm.COMPRESSED, version=581)

    def test_copy_npc(self):
        rec, rep = ra2.copy_npc(self._npc(), 0x01000804, "FO4SF_RA2HandyTest", "Mr. Handy (test)", 0x01000800,
                                0x01000803, ra2.HANDY_OBND)
        self.assertEqual(rec.edid, "FO4SF_RA2HandyTest")
        self.assertEqual(esm.zstring(rec.get(b"FULL")), "Mr. Handy (test)")
        self.assertEqual(rec.all(b"SNAM"), [])
        self.assertIsNone(rec.get(b"VMAD"))
        self.assertEqual(struct.unpack("<I", rec.get(b"RNAM"))[0], 0x01000800)
        self.assertEqual(struct.unpack("<I", rec.get(b"WNAM"))[0], 0x01000803)
        self.assertEqual(struct.unpack_from("<I", rec.get(b"ACBS"))[0], 0x40010140)
        self.assertEqual(rec.get(b"AIDT")[:2], bytes([2, 4]))
        self.assertEqual(struct.unpack("<6f", rec.get(b"OBND"))[5], struct.unpack("<f", struct.pack("<f", 1.8))[0])
        self.assertFalse(rec.flags & esm.COMPRESSED)
        self.assertEqual(rep["dropped"], ["VMAD", "SNAM", "SNAM"])
        with self.assertRaises(ra2.Ra2Error):
            ra2.copy_npc(self._npc(template_flags=0x1), 1, "x", "x", 1, 1)

    def test_copy_race_paths_and_strings(self):
        race = esm.Record(b"RACE", 0x227705, [
            (b"EDID", esm.zbytes("MiniBotARace")), (b"FULL", b"\xd1\x1e\0\0"), (b"DESC", b"\xcf\x1e\0\0"),
            (b"NAM5", esm.zbytes("actors\\minibota\\characterassets\\skeleton.rig")),
            (b"DNAM", esm.zbytes("Actors\\MiniBotA\\Animations")), (b"SAPT", esm.zbytes("Actors\\MiniBotA\\Animations\\Furniture")),
            (b"WED0", b"\x01" * 40)], version=581)
        ren = ra2.copy_race(race, 0x01000805, "X", "Mini Bot")
        self.assertEqual([s for s, d in ren.subs if dict(race.subs).get(s) != d], [b"EDID", b"FULL", b"DESC"])
        own = ra2.copy_race(race, 0x01000809, "Y", "Mini Bot", rig=ra2.OWN_RIG, clips=ra2.OWN_CLIPS)
        self.assertEqual(esm.zstring(own.get(b"NAM5")), ra2.OWN_RIG)
        self.assertEqual(esm.zstring(own.get(b"SAPT")), ra2.OWN_CLIPS + "\\Furniture")
        self.assertEqual(own.get(b"WED0"), b"\x01" * 40)

    def test_plugin_group_order_and_round_trip(self):
        recs = [esm.Record(b"NPC_", 0x01000804, [(b"EDID", esm.zbytes("A"))]),
                esm.Record(b"RACE", 0x01000800, [(b"EDID", esm.zbytes("B"))]),
                esm.Record(b"ARMA", 0x01000802, [(b"EDID", esm.zbytes("C"))])]
        raw = ra2.plugin_bytes(recs, ["Starfield.esm"], ["RACE", "ARMO", "NPC_", "ARMA"])
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "t.esm"
            p.write_bytes(raw)
            with esm.Plugin(str(p)) as pl:
                self.assertEqual(pl.masters, ["Starfield.esm"])
                self.assertEqual(list(pl.groups), ["RACE", "NPC_", "ARMA"])
                hedr = struct.unpack("<fII", pl.header.get(b"HEDR"))
                self.assertEqual(hedr[1:], (6, 0x805))


class TestManifests(unittest.TestCase):
    def test_own_folder_rekey(self):
        g = hr.STRAFING_GRAPH
        old = hr.manifest_key(g, [ra2.VAN_CLIPS])
        race = esm.Record(b"RACE", 1, [(b"NAM6", esm.zbytes(hr.ROOT_GRAPH)), (b"SGNM", esm.zbytes(g)),
                                       (b"SAPT", esm.zbytes(ra2.VAN_CLIPS))])
        clip = ra2.VAN_CLIPS + "\\Idle.af"
        offs = hr.animation_offsets(g, [("Fire", ra2.VAN_CLIPS + "\\Fire")],
                                    [hr.OffsetClip(ra2.VAN_CLIPS + "\\Fire", 1.0, [(0.3, "WeaponFire")])])
        vanilla = {f"animationfiledata/{old}.txt": hr.animation_file_data(old, [clip]),
                   f"animationoffsets/{old}.txt": offs, f"animationstancedata/{old}.txt": b"stance",
                   f"dynamicidledata/{old}.txt": b"Version 1\n"}
        files, rep = ra2.own_folder_manifests(vanilla, race, hr.GSD_HEADER.encode(), "OwnRace")
        new = hr.manifest_key(g, [ra2.OWN_CLIPS])
        self.assertEqual(rep["keys"][str(old)]["new_key"], str(new))
        afd = files[f"Meshes\\AnimTextData\\AnimationFileData\\{new}.txt"].decode()
        self.assertEqual(afd, f"3\n1\n{new}\n1\n{ra2.OWN_CLIPS}\\Idle.af\n")
        _g, tags, recs = hr.parse_animation_offsets(files[f"Meshes\\AnimTextData\\AnimationOffsets\\{new}.txt"])
        self.assertEqual(tags, [("Fire", ra2.OWN_CLIPS + "\\Fire")])
        self.assertEqual(recs[0].events, [(struct.unpack("<f", struct.pack("<f", 0.3))[0], "WeaponFire")])
        self.assertEqual(files[f"Meshes\\AnimTextData\\AnimationStanceData\\{new}.txt"], b"stance")
        self.assertIn("Meshes\\AnimTextData\\GeneratedSubgraphData\\ownrace.txt", files)


class TestAfx(unittest.TestCase):
    TEMPLATE = (b"<root>\r\n\t<is_state>0</is_state>\r\n\t<tag>TurnInPlace_Left90</tag>\r\n\t<filename>TurnInPlace_Left90.af"
                b"</filename>\r\n\t<flags>\r\n\t\t<flag>Turn Animation</flag>\r\n\t</flags>\r\n\t<events>\r\n\t\t<event><frame>28"
                b"</frame><name>SetOrientEnd</name><payload></payload></event>\r\n\t</events>\r\n\t<audios>\r\n\t\t<audio><frame>1"
                b"</frame><foley>NPC_X</foley></audio>\r\n\t</audios>\r\n</root>")

    def test_template_round_trip_and_replacement(self):
        p = aa.parse_afx(self.TEMPLATE)
        self.assertEqual(ra2.afx_vanilla(p["tag"], p["filename"], p["is_state"], p["events"], p["audio"], self.TEMPLATE),
                         self.TEMPLATE)
        new = ra2.afx_vanilla("TurnInPlace_Left90", "TurnInPlace_Left90.af", 0, [(17, "SetOrientEnd", "")], (), self.TEMPLATE)
        self.assertIn(b"<flag>Turn Animation</flag>", new)
        self.assertNotIn(b"audios", new)
        self.assertIn(b"<frame>17</frame>", new)
        self.assertEqual([n for n, _ in ra2.afx_elements(new)[0]], ["is_state", "tag", "filename", "flags", "events"])
        var = (b"<root>\r\n\t<is_state>0</is_state>\r\n\t<tag>T</tag>\r\n\t<filename>T.af</filename>\r\n\t<variables>\r\n"
               b"\t\t<variable><name>A</name><start>3</start><end>35</end></variable>\r\n"
               b"\t\t<variable><name>B</name><start>64</start><end>74</end></variable>\r\n\t</variables>\r\n</root>")
        self.assertEqual(ra2.afx_vanilla("T", "T.af", 0, template=var), var)
        clamped = ra2.afx_vanilla("T", "T.af", 0, template=var, frame_count=31)
        self.assertIn(b"<name>A</name><start>3</start><end>30</end>", clamped)
        self.assertNotIn(b"<name>B</name>", clamped)
        self.assertNotIn(b"variables", ra2.afx_vanilla("T", "T.af", 0, template=var, frame_count=2))
        plain = ra2.afx_vanilla("Idle", "Idle.af", 1)
        self.assertEqual(plain, b"<root>\r\n\t<is_state>1</is_state>\r\n\t<tag>Idle</tag>\r\n\t<filename>Idle.af</filename>\r\n</root>")
        with self.assertRaises(ra2.Ra2Error):
            ra2.afx_elements(b"<root><tag>x</tag></root>")

    @unittest.skipUnless((ra2.STARFIELD_DIR / "Data" / "Starfield - Animations.ba2").is_file(), "Starfield absent")
    def test_reproduces_every_vanilla_minibot_afx(self):
        from fo4sf.ba2 import Ba2
        a = Ba2(str(ra2.STARFIELD_DIR / "Data" / "Starfield - Animations.ba2"))
        names = [n for n in a.names if n.startswith(ra2.VAN_PREFIX) and n.endswith(".afx")]
        self.assertEqual(len(names), 55)
        for n in names:
            raw = a.read(a.find(n))
            p = aa.parse_afx(raw)
            self.assertEqual(ra2.afx_vanilla(p["tag"], p["filename"], p["is_state"], p["events"], p["audio"], raw), raw, n)


class TestBatsAndInstall(unittest.TestCase):
    def test_bats(self):
        b = ra2.build_bats()
        self.assertEqual(sorted(b), ["ra2a.txt", "ra2b.txt", "ra2c.txt"])
        self.assertIn("player.placeatme XX000804 1", b["ra2a.txt"])
        self.assertIn("player.placeatme 1A000808 1", ra2.build_bats(0x1A)["ra2b.txt"])
        with self.assertRaises(ra2.Ra2Error):
            ra2.validate_bats({"ra2m.txt": "x"})
        with self.assertRaises(ra2.Ra2Error):
            ra2.validate_bats({"ra2a.txt": "; FO4SF_RA2HandyTest"})

    def _tes4(self, path, flags=0x1):
        path.write_bytes(struct.pack("<4sIIIIHH", b"TES4", 0, flags, 0, 0, 0, 0))

    def test_install_uninstall_restores_plugins_txt(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            stage, game = d / "stage", d / "game"
            (game / "Data").mkdir(parents=True)
            stage.mkdir()
            (stage / ra2.PLUGIN).write_bytes(b"esm")
            (stage / ra2.MAIN_BA2).write_bytes(b"ba2")
            self._tes4(game / "Data" / "Starfield.esm")
            self._tes4(game / "Data" / "A.esm")
            self._tes4(game / "Data" / "Light.esm", 0x201)
            ptxt = d / "Plugins.txt"
            original = "\ufeff# comment\r\n*A.esm\r\n*Light.esm\r\n".encode("utf-8")
            ptxt.write_bytes(original)
            with mock.patch.object(ra2, "verify", return_value={}):
                rc = ra2.install(stage, game, ptxt, min_free_gb=0.0, check_running=False)
                self.assertEqual(rc["slot_hex"], "02")            # Starfield.esm 00, A.esm 01, light skipped
                self.assertIn("player.placeatme 02000804 1", (game / "ra2a.txt").read_text())
                self.assertTrue(ptxt.read_text(encoding="utf-8-sig").rstrip().endswith("*" + ra2.PLUGIN))
                self.assertIsNotNone(rc["warning"])
                with self.assertRaises(ra2.Ra2Error):
                    ra2.install(stage, game, ptxt, min_free_gb=0.0, check_running=False)
                res = ra2.uninstall(game, ptxt, check_running=False)
            self.assertEqual(res["plugins_txt"], "restored byte for byte")
            self.assertEqual(ptxt.read_bytes(), original)
            self.assertEqual(sorted(p.name for p in game.iterdir()), ["Data"])
            self.assertEqual(sorted(p.name for p in (game / "Data").iterdir()), ["A.esm", "Light.esm", "Starfield.esm"])
            self.assertFalse((stage / "backup_pre_ra2").exists())

    def test_uninstall_keeps_later_plugins_txt_edits(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            stage, game = d / "stage", d / "game"
            (game / "Data").mkdir(parents=True)
            stage.mkdir()
            (stage / ra2.PLUGIN).write_bytes(b"esm")
            (stage / ra2.MAIN_BA2).write_bytes(b"ba2")
            ptxt = d / "Plugins.txt"
            ptxt.write_text("*A.esm\n", encoding="utf-8")
            with mock.patch.object(ra2, "verify", return_value={}):
                ra2.install(stage, game, ptxt, min_free_gb=0.0, check_running=False)
                ptxt.write_text(ptxt.read_text(encoding="utf-8") + "*B.esm\n", encoding="utf-8")
                res = ra2.uninstall(game, ptxt, check_running=False)
            self.assertIn("only the appended line", res["plugins_txt"])
            self.assertEqual(ptxt.read_text(encoding="utf-8"), "*A.esm\n*B.esm\n")

    def test_refuses_repo_and_game_library(self):
        with self.assertRaises(ra2.Ra2Error):
            ra2.check_out_dir(ROOT / "out")
        with self.assertRaises(ra2.Ra2Error):
            ra2.check_out_dir(Path(r"D:\SteamLibrary\x"))


@unittest.skipUnless((ra2.FO4_DATA / "Fallout4 - Meshes.ba2").is_file()
                     and (ra2.STARFIELD_DIR / "Data" / "Starfield - Meshes01.ba2").is_file(), "game data absent")
class TestBindOverride(unittest.TestCase):
    def test_pelvis_on_com_in_mesh_and_rig(self):
        import convert_handy
        from fo4sf.ba2 import Ba2
        fo4a = Ba2(str(ra2.FO4_DATA / "Fallout4 - Animations.ba2"))
        fo4m = Ba2(str(ra2.FO4_DATA / "Fallout4 - Meshes.ba2"))
        sf = lambda rel: ra2._read_archive(ra2.STARFIELD_DIR / "Data", "Starfield - Meshes*.ba2", rel)  # noqa: E731
        args = (fo4m.read(fo4m.find(convert_handy.SRC_MESH)), fo4a.read(fo4a.find(convert_handy.SRC_SKELETON)),
                sf(convert_handy.SF_MESH_TEMPLATE), sf(convert_handy.SF_SKELETON_TEMPLATES["minibota"]),
                dict(convert_handy.HANDY_MATERIALS))
        _f, rep, skel, _m = convert_handy.convert(*args, bind_overrides=ra2.BIND_OVERRIDES_FO4)
        self.assertTrue(rep["verify_mesh"]["ok"] and rep["verify_skeleton"]["ok"] and rep["verify_skeleton_ref"]["ok"])
        world = skel.world()
        self.assertLess(math.dist(world[skel.index("Pelvis")][0], world[skel.index("COM")][0]), 1e-9)
        self.assertEqual(rep["bind_overrides_fo4_units"]["Pelvis"], [0.0, 0.0, 0.0])
        bones = ra2.rig_bones_from_skeleton(skel)
        self.assertEqual(len(bones), 112)
        self.assertEqual((bones[0]["name"], bones[0]["key"], bones[1]["name"], bones[1]["key"]), ("Root", 0, "COM", 9))
        _f0, rep0, skel0, _m0 = convert_handy.convert(*args)
        w0 = skel0.world()
        self.assertAlmostEqual(math.dist(w0[skel0.index("Pelvis")][0], w0[skel0.index("COM")][0]), 5.8136 / 70, places=4)


def _skeleton_of(bones):
    from fo4sf import actor_skin
    return actor_skin.Skeleton([b["name"] for b in bones], [b["parent"] for b in bones],
                               [(b["translation"], actor_skin.quat_to_matrix(b["rotation"]), 1.0) for b in bones])


class TestRebase(unittest.TestCase):
    """The clip side of the COM rebase (convert_handy.finish_skeleton does the rig / mesh side)."""

    def _setup(self, zero=("COM",)):
        from fo4sf import actor_skin
        b = _bones()
        parents = [x["parent"] for x in b]
        corr = ra2.corrections_as_quats(actor_skin.rest_rotation_corrections(_skeleton_of(b), zero))
        return b, parents, corr

    def test_rebased_bind_has_identity_com(self):
        b, parents, corr = self._setup()
        bind = [(x["translation"], x["rotation"]) for x in b]
        rb = ra2.rebase_frames([bind], parents, corr)[0]
        self.assertLess(aa.q_angle(rb[1][1], aa.IDENTITY), 1e-9)
        self.assertGreater(math.degrees(aa.q_angle(bind[1][1], aa.IDENTITY)), 89.9)

    def test_world_positions_kept_and_round_trip(self):
        b, parents, corr = self._setup(("COM", "Arm1|1"))
        fr = _frames(b)
        new = ra2.rebase_frames(fr, parents, corr)
        d, _f, _j = ra2.world_position_difference(parents, fr, parents, new, len(b))
        self.assertLess(d, 1e-12)
        _close(self, ra2.unrebase_frames(new, parents, corr), fr, tol=1e-12)
        extra = [((0.0, 0.0, 0.0), aa.IDENTITY)]
        rig = ra2.to_rig_frames(fr, parents, corr, extra)
        self.assertEqual(len(rig[0]), len(b) + 1)
        _close(self, ra2.unrebase_frames(rig, parents, corr), fr, tol=1e-12)   # the extra bone is dropped

    def test_translation_rule_exposure(self):
        b, parents, corr = self._setup()
        fr = _frames(b)                      # COM (turned rest) moves 0.08 m in x and z over the clip
        before, bone = ra2.translation_rule_exposure(b, fr)
        self.assertEqual(bone, "COM")
        self.assertGreater(before, 0.05)
        bind = ra2.rebase_frames([[(x["translation"], x["rotation"]) for x in b]], parents, corr)[0]
        rebased = [dict(x, translation=t, rotation=q) for x, (t, q) in zip(b, bind)]
        after, _bone = ra2.translation_rule_exposure(rebased, ra2.rebase_frames(fr, parents, corr))
        self.assertLess(after, 1e-12)        # Arm2|1 also moves, but its rest is not turned


class TestStretch(unittest.TestCase):
    def _shape(self):
        import numpy as np
        bd = np.zeros((2, 3, 4))
        bd[:, :, :3] = np.eye(3)
        bd[1, :, 3] = (-1.0, 0.0, 0.0)               # bone B stands at x = 1 (BoneData = inverse bind)
        pts = np.array([(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 0.5, 0.0)])
        return {"name": "S", "bones": ["A", "B"], "bone_data": bd, "pts": pts,
                "w": np.array([[1.0], [1.0], [1.0]]), "slots": np.array([[0], [1], [1]]),
                "edges": np.array([(0, 1), (1, 2), (0, 2)]), "l0": np.array([1.0, 0.5, math.hypot(1, 0.5)]),
                "heavy": np.array([0, 1, 1]), "verts": 3, "tris": 1}

    def test_edge_stretch_and_summary(self):
        names, parents = ["A", "B"], [-1, 0]
        frames = [[((0, 0, 0), aa.IDENTITY), ((1.0, 0, 0), aa.IDENTITY)],
                  [((0, 0, 0), aa.IDENTITY), ((3.0, 0, 0), aa.IDENTITY)]]       # B pulled 2 m away
        w = ra2.edge_stretch([self._shape()], parents, names, frames)["S"]
        self.assertAlmostEqual(w["ratio"], 3.0, places=6)
        self.assertEqual((w["frame"], w["bones"]), (1, ["A", "B"]))
        s = ra2.summarize_stretch({"clipa": {"S": w}, "clipb": {"S": dict(w, ratio=1.2)}}, [self._shape()])
        self.assertEqual(s["over_limit"], ["clipa"])
        self.assertEqual(s["worst"]["clip"], "clipa")


class TestBodyParts(unittest.TestCase):
    def test_renamed_bptd_bones(self):
        from fo4sf import actor_skin
        names = actor_skin.starfield_bone_names(["Root", "COM", "Pelvis", "Chest", "Spine2", "Arm1|0", "Arm1|1", "Arm1|2",
                                                 "EyeArm3|0", "EyeArm3|1", "EyeArm3|2"])
        bone_map, extra = ra2.renamed_body_parts(names)
        self.assertEqual(bone_map["C_Arm1"], "Arm1_0")
        self.assertEqual([b for _t, b in extra], ["Arm1_1", "Arm1_2", "EyeArm3_0", "EyeArm3_1", "EyeArm3_2"])
        for v in list(bone_map.values()) + [b for _t, b in extra]:
            self.assertTrue(actor_skin.SAFE_BONE_NAME.match(v), v)
        race = esm.Record(b"BPTD", 0x227704, [
            (b"EDID", esm.zbytes("MiniBotABodyPartData")), (b"MODL", esm.zbytes("x.nif")),
            (b"BPTN", b"\1\0\0\0"), (b"BPNN", esm.zbytes("C_Arm1")), (b"BPNT", esm.zbytes("C_Arm1")),
            (b"BPTN", b"\2\0\0\0"), (b"BPNN", esm.zbytes("C_Chassis")), (b"BPNT", esm.zbytes("C_Chassis"))])
        rec = hr.build_bptd(race, 0x01000801, hr.HandyPaths(), bone_map=bone_map, extra_parts=extra)
        texts = [esm.zstring(d) for s, d in rec.subs if s in (b"BPTN", b"BPNN", b"BPNT")]
        self.assertIn("Arm1_0", texts)
        self.assertFalse(any("|" in t or "-" in t for t in texts), texts)


class TestInstanceBones(unittest.TestCase):
    def test_instance_bone(self):
        import convert_handy
        self.assertEqual(convert_handy.instance_bone("Arm1|0", 2), "Arm1|2")
        self.assertEqual(convert_handy.instance_bone("EyeArmPalm_IrisSC|0", 1), "EyeArmPalm_IrisSC|1")
        self.assertEqual(convert_handy.instance_bone("Chest", None), "Chest")
        with self.assertRaises(ValueError):
            convert_handy.instance_bone("Chest", 1)


@unittest.skipUnless((ra2.FO4_DATA / "Fallout4 - Meshes.ba2").is_file()
                     and (ra2.STARFIELD_DIR / "Data" / "Starfield - Meshes01.ba2").is_file(), "game data absent")
class TestCodsworthParts(unittest.TestCase):
    """convert_handy.convert_parts on the real Fallout 4 parts Codsworth's object template attaches."""

    @classmethod
    def setUpClass(cls):
        import convert_handy
        from fo4sf.ba2 import Ba2
        fo4a = Ba2(str(ra2.FO4_DATA / "Fallout4 - Animations.ba2"))
        fo4m = Ba2(str(ra2.FO4_DATA / "Fallout4 - Meshes.ba2"))
        sf = lambda rel: ra2._read_archive(ra2.STARFIELD_DIR / "Data", "Starfield - Meshes*.ba2", rel)  # noqa: E731
        cls.ch = convert_handy
        cls.files, cls.rep, cls.skel, cls.names = convert_handy.convert_parts(
            convert_handy.read_codsworth_parts(fo4m), fo4a.read(fo4a.find(convert_handy.SRC_SKELETON)),
            sf(convert_handy.SF_MESH_TEMPLATE), sf(convert_handy.SF_SKELETON_TEMPLATES["minibota"]),
            dict(convert_handy.HANDY_MATERIALS), bind_overrides=ra2.BIND_OVERRIDES_FO4)

    def test_verified_shapes_and_materials(self):
        rep = self.rep
        self.assertTrue(rep["verify_mesh"]["ok"] and rep["verify_skeleton"]["ok"] and rep["verify_skeleton_ref"]["ok"],
                        rep["verify_mesh"]["errors"])
        self.assertEqual(sorted(rep["verify_mesh"]["shapes"]), sorted(self.ch.HANDY_MATERIALS))
        self.assertEqual(len(rep["placed"]), 21)               # 18 placements; the three eyes have two lit shapes each
        self.assertEqual([s["shape"] for s in rep["skipped"]], ["ModTorsoHandyEye:2"] * 3)
        self.assertLess(rep["bind_spread_max_fo4_units"], 0.05)
        for s in rep["verify_mesh"]["shapes"].values():
            self.assertLess(s["bind_pose_max_error_mm"], 0.1)

    def test_rig_skeleton(self):
        from fo4sf import actor_skin
        skel = self.skel
        self.assertEqual(len(skel.names), 113)
        self.assertTrue(all(actor_skin.SAFE_BONE_NAME.match(n) for n in skel.names))
        self.assertEqual(self.rep["skeleton"]["renamed"], 80)
        for n in ("COM", "Pelvis", "C_ModSlotB_0", "C_ModSlotB_1", "C_ModSlotB_2"):
            self.assertLess(actor_skin.rotation_angle_deg(skel.local[skel.index(n)][1], actor_skin.IDENT_R), 1e-4)
        w = skel.world()
        self.assertLess(math.dist(w[skel.index("Pelvis")][0], w[skel.index("COM")][0]), 1e-9)
        self.assertEqual(skel.names[-1], "DirectAt")
        self.assertEqual(skel.parents[-1], skel.index("COM"))
        self.assertLess(math.dist(w[-1][0], w[skel.index("COM")][0]), 1e-12)
        self.assertEqual(self.rep["skeleton"]["not_in_mesh_nif"], ["DirectAt"])
        self.assertEqual(self.rep["skeleton"]["bones_in_mesh_nif"], 110)   # COM_Twin + the 109 bones below COM
        bones = ra2.rig_bones_from_skeleton(skel)
        self.assertEqual({b["name"]: b["key"] for b in bones if b["key"] is not None}, ra2.RIG_KEYS)


@unittest.skipUnless((E_OUT / "manifest.json").is_file(), "the pre-fix RA2 bundle (E) is not present")
class TestOldBundleRejected(unittest.TestCase):
    def test_verify_refuses_the_pre_fix_rig(self):
        with self.assertRaises(ra2.Ra2Error):
            ra2.verify(E_OUT)


@unittest.skipUnless((E2_OUT / "manifest.json").is_file() and (E2_OUT / "report.json").is_file(),
                     "fixed RA2 bundle (E2) not built")
class TestStagedBundle(unittest.TestCase):
    def test_verify_and_report(self):
        res = ra2.verify(E2_OUT)
        self.assertEqual(len(res["records"]), 13)
        self.assertEqual(res["rig_bones"], 113)
        self.assertEqual(res["rig_keys"], ra2.RIG_KEYS)
        self.assertTrue(res["names_safe"])
        rep = json.loads((E2_OUT / "report.json").read_text(encoding="utf-8"))
        tags = {c["tag"] for c in rep["clips"]}
        for t in ra2.REQUIRED_TAGS:
            self.assertIn(t, tags)
        for c in rep["clips"]:
            self.assertEqual(c["readback_frames"], c["frames"])
            self.assertEqual(c["header"]["bones"], 113)
            self.assertLess(c["err_vs_written_poses"]["t_m"], 5e-4)
            self.assertLess(c["err_vs_written_poses"]["r_deg"], 0.5)
            self.assertLess(c["rebase_world_max_m"], 1e-9)
        self.assertLess(rep["clip_summary"]["translation_rule_difference_max_m"], 1e-3)
        d = rep["deformation"]
        self.assertEqual(d["clips"], len(rep["clips"]))
        self.assertLess(d["rigid_edges_worst_dev"], 1e-3)          # rigid pieces never stretch
        nat = d.get("fo4_native_all_clips")
        if nat:      # every remaining stretch is Fallout 4's own skinning of the same poses
            self.assertLess(nat["max_rel_diff"], 0.01)
            self.assertEqual(nat["clips_native_over_limit"], d["over_limit"])
        if "compare_with_before" in rep:
            self.assertLess(rep["compare_with_before"]["max_position_mm"], 0.5)


if __name__ == "__main__":
    unittest.main()
