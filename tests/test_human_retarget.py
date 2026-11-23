"""Tests for fo4sf.human_retarget and scripts/probes/stage_ra4_human.py (human-animation lane).

    PYTHONPATH=src python -m unittest tests.test_human_retarget

Synthetic skeletons only, except the last class, which checks a staged RA4 bundle when one exists on this machine.
"""
import math
import random
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT / "src"), str(ROOT / "scripts" / "probes")):
    if p not in sys.path:
        sys.path.insert(0, p)

from fo4sf import actor_anim as aa  # noqa: E402
from fo4sf import human_retarget as hrt  # noqa: E402
from fo4sf.planet import esm  # noqa: E402

S2 = math.sqrt(0.5)


def _qx(deg):
    return aa.q_from_axis_angle((1, 0, 0), math.radians(deg))


def _qy(deg):
    return aa.q_from_axis_angle((0, 1, 0), math.radians(deg))


def _qz(deg):
    return aa.q_from_axis_angle((0, 0, 1), math.radians(deg))


def _world_rest(names, parents, world):
    """Parent-local rest from model-space (t, q) per bone."""
    local = []
    for i, (t, q) in enumerate(world):
        p = parents[i]
        if p < 0:
            local.append((t, q))
        else:
            pt, pq = world[p]
            inv = aa.q_conj(pq)
            local.append((aa.q_rotate(inv, tuple(a - b for a, b in zip(t, pt))), aa.q_norm(aa.q_mul(inv, q))))
    return hrt.Skel(list(names), list(parents), local)


def _leg_dir(down_deg_forward):
    """A bone frame whose local +X points down (tilted forward by the angle), local +Y forward."""
    return aa.q_norm(aa.q_mul(_qx(down_deg_forward), aa.q_mul(_qy(90), _qx(0))))


def _toy(kind, scale=1.0, twist=0.0):
    """A torso + two legs skeleton with Fallout 4 ('fo4') or Starfield ('sf') bone names. Bones point along their
    local +X to the next joint; `twist` turns every bone about its own X (a different axis convention); the Starfield
    one has an extra spine and neck joint like the real rig."""
    tw = _qx(twist)
    down = aa.q_norm(aa.q_mul(_qy(90), tw))      # local +X -> world -Z
    up = aa.q_norm(aa.q_mul(_qy(-90), tw))       # local +X -> world +Z
    fwd = aa.q_norm(aa.q_mul(_qz(90), tw))       # local +X -> world +Y
    h = 1.0 * scale
    if kind == "fo4":
        spec = [("Root", -1, (0, 0, 0), (0, 0, 0, 1)), ("COM", 0, (0, 0, h), _qy(-90)),
                ("Pelvis", 1, (0, 0, h), up),
                ("LLeg_Thigh", 2, (-0.1 * scale, 0, h), down), ("LLeg_Calf", 3, (-0.1 * scale, 0.01, 0.55 * scale), down),
                ("LLeg_Foot", 4, (-0.1 * scale, 0, 0.1 * scale), fwd), ("LLeg_Toe1", 5, (-0.1 * scale, 0.12 * scale, 0.02), fwd),
                ("RLeg_Thigh", 2, (0.1 * scale, 0, h), down), ("RLeg_Calf", 7, (0.1 * scale, 0.01, 0.55 * scale), down),
                ("RLeg_Foot", 8, (0.1 * scale, 0, 0.1 * scale), fwd), ("RLeg_Toe1", 9, (0.1 * scale, 0.12 * scale, 0.02), fwd),
                ("Spine1", 1, (0, 0, h + 0.05 * scale), up), ("Spine2", 11, (0, 0, h + 0.2 * scale), up),
                ("Chest", 12, (0, 0, h + 0.35 * scale), up), ("Neck", 13, (0, 0.02, h + 0.6 * scale), up),
                ("Head", 14, (0, 0.02, h + 0.72 * scale), up)]
    else:
        spec = [("Root", -1, (0, 0, 0), (0, 0, 0, 1)), ("COM", 0, (0, 0, h + 0.1 * scale), (0, 0, 0, 1)),
                ("C_Hips", 1, (0, 0, h + 0.1 * scale), aa.q_mul(_qz(180), up)),
                ("L_Thigh", 2, (-0.1 * scale, 0, h), down), ("L_Calf", 3, (-0.1 * scale, 0.01, 0.55 * scale), down),
                ("L_Foot", 4, (-0.1 * scale, 0, 0.1 * scale), fwd), ("L_Toe", 5, (-0.1 * scale, 0.12 * scale, 0.02), fwd),
                ("R_Thigh", 2, (0.1 * scale, 0, h), down), ("R_Calf", 7, (0.1 * scale, 0.01, 0.55 * scale), down),
                ("R_Foot", 8, (0.1 * scale, 0, 0.1 * scale), fwd), ("R_Toe", 9, (0.1 * scale, 0.12 * scale, 0.02), fwd),
                ("C_Spine", 1, (0, 0, h + 0.1 * scale), up), ("C_Spine1", 11, (0, 0, h + 0.15 * scale), up),
                ("C_Spine2", 12, (0, 0, h + 0.25 * scale), up), ("C_Chest", 13, (0, 0, h + 0.35 * scale), up),
                ("C_Neck", 14, (0, 0.02, h + 0.6 * scale), up), ("C_Neck1", 15, (0, 0.02, h + 0.66 * scale), up),
                ("C_Head", 16, (0, 0.02, h + 0.72 * scale), up)]
    names = [s[0] for s in spec]
    parents = [s[1] for s in spec]
    world = [(tuple(float(v) for v in s[2]), aa.q_norm(s[3])) for s in spec]
    return _world_rest(names, parents, world)


TOY_PAIRS = tuple(p for p in hrt.BODY_MAP if p.sf in {
    "COM", "C_Hips", "C_Spine", "C_Spine1", "C_Spine2", "C_Chest", "C_Neck", "C_Neck1", "C_Head",
    "L_Thigh", "L_Calf", "L_Foot", "L_Toe", "R_Thigh", "R_Calf", "R_Foot", "R_Toe"})
TOY_JOINTS = tuple(j for j in hrt.JOINTS if j[2] in ("spine", "head", "L_leg", "R_leg"))
TOY_SEGMENTS = tuple(s for s in hrt.SEGMENTS if s[4] in ("L_leg", "R_leg"))


def _random_pose(skel, rng, amount=25.0):
    fr = []
    for i, (t, q) in enumerate(skel.rest):
        if i == 0:
            fr.append(((0.0, 0.0, 0.0), hrt.IDENTITY))
            continue
        axis = tuple(rng.uniform(-1, 1) for _ in range(3))
        fr.append((t, aa.q_norm(aa.q_mul(q, aa.q_from_axis_angle(axis, math.radians(rng.uniform(-amount, amount)))))))
    return fr


def _clip(skel, n, rng, root_speed=0.0):
    frames = [_random_pose(skel, rng) for _ in range(n)]
    root = [(0.0, root_speed * f / 30.0, 0.0, 0.0) for f in range(n)]
    return hrt.Fo4Clip(frames, root, [], 30.0, "NORMAL")


class MathTests(unittest.TestCase):
    def test_quat_from_basis(self):
        rng = random.Random(1)
        for _ in range(20):
            a = tuple(rng.uniform(-1, 1) for _ in range(3))
            b = tuple(rng.uniform(-1, 1) for _ in range(3))
            q = hrt.quat_from_basis(a, b)
            x = aa.q_rotate(q, (1, 0, 0))
            y = aa.q_rotate(q, (0, 1, 0))
            ua = hrt._unit(a)
            self.assertLess(math.dist(x, ua), 1e-9)
            self.assertLess(abs(hrt._dot(y, ua)), 1e-9)
            self.assertGreater(hrt._dot(y, b), 0)

    def test_quat_between(self):
        for a, b in (((1, 0, 0), (0, 1, 0)), ((0, 0, 1), (0, 0, -1)), ((1, 2, 3), (-2, 0.5, 1)), ((1, 0, 0), (1, 0, 0))):
            q = hrt.quat_between(a, b)
            self.assertLess(math.dist(aa.q_rotate(q, hrt._unit(a)), hrt._unit(b)), 1e-9)

    def test_two_bone_ik(self):
        hip, knee, ankle = (0, 0, 1.0), (0, 0.05, 0.55), (0, 0, 0.1)
        new_knee, reached, miss = hrt.two_bone_ik(hip, knee, ankle, (0.05, 0.1, 0.2))
        self.assertAlmostEqual(math.dist(hip, new_knee), math.dist(hip, knee), places=9)
        self.assertAlmostEqual(math.dist(new_knee, reached), math.dist(knee, ankle), places=9)
        self.assertLess(math.dist(reached, (0.05, 0.1, 0.2)), 1e-9)
        self.assertEqual(miss, 0.0)
        self.assertGreater(new_knee[1], 0.0)                    # bend plane kept: the knee still points forward
        _k, _r, miss = hrt.two_bone_ik(hip, knee, ankle, (0, 0, -2.0))
        self.assertGreater(miss, 1.0)


class RetargetTests(unittest.TestCase):
    def _rt(self, scale=1.0, twist=90.0, ik=False):
        rt = hrt.Retargeter(_toy("fo4"), _toy("sf", scale=scale, twist=twist), pairs=TOY_PAIRS)
        rt.leg_ik = ik
        return rt.prepare()

    def test_rest_maps_to_bind(self):
        rt = self._rt()
        pose = rt.pose([((0, 0, 0), hrt.IDENTITY)] + list(rt.fo4.rest[1:]))
        for (t, q), (bt, bq) in zip(pose[1:], rt.sf.rest[1:]):
            self.assertLess(aa.q_angle(q, bq), 1e-7)
            self.assertLess(math.dist(t, bt), 1e-9)

    def test_motion_transfers_across_axis_conventions(self):
        """Different local axes (twist 90 deg) and rest heights: leg segment directions and every single-bone
        anatomical frame match exactly; with equal proportions (the toy rigs differ only in torso joints) leg joints
        sit at k * the Fallout 4 ones."""
        rt = self._rt()
        clip = _clip(rt.fo4, 6, random.Random(3))
        frames = hrt.retarget_clip(rt, clip)
        rep = hrt.compare(rt, clip, frames, joints=TOY_JOINTS, segments=TOY_SEGMENTS)
        for chain in ("L_leg", "R_leg"):
            self.assertLess(rep[chain]["direction_deg"]["max"], 1e-5)
            self.assertLess(rep[chain]["frame_deg"]["max"], 1e-5)
        self.assertLess(rep["spine"]["frame_deg"]["max"], 1e-5)
        self.assertAlmostEqual(rt.k, 1.0, places=9)

    def test_hips_follow_scaled(self):
        rt = self._rt(scale=1.2)
        self.assertAlmostEqual(rt.k, 1.2, places=9)
        clip = _clip(rt.fo4, 4, random.Random(5), root_speed=1.5)
        frames = hrt.retarget_clip(rt, clip)
        rep = hrt.compare(rt, clip, frames, joints=(("HIPS", "HIPS", "spine"),), segments=())
        self.assertLess(rep["spine"]["position_m"]["max"], 1e-9)
        last = frames[-1][0][0]
        self.assertAlmostEqual(last[1], 1.2 * clip.root[-1][1], places=9)     # root motion scaled by k

    def test_leg_ik_plants_feet(self):
        """A planted Fallout 4 foot (ankle at rest height) stays planted on the Starfield rig with leg IK, while a
        rig with other proportions slides without it."""
        fo4 = _toy("fo4")
        sf = _toy("sf", scale=1.1)
        ix = sf.index()
        # make the Starfield shins shorter than a uniform scale would (other leg proportions than Fallout 4)
        for name in ("L_Foot", "R_Foot"):
            t, q = sf.rest[ix[name]]
            sf.rest[ix[name]] = (tuple(v * 0.9 for v in t), q)
        fix = fo4.index()
        rest_w = fo4.rest_world()
        frames = []
        for f in range(8):            # the pelvis bobs and sways, the feet stay where they are (an idle)
            fr = [((0.0, 0.0, 0.0), hrt.IDENTITY)] + list(fo4.rest[1:])
            t, q = fr[1]
            fr[1] = ((t[0] + 0.02 * math.sin(f), t[1], t[2] - 0.03 * (1 - math.cos(f))), q)
            # plant the Fallout 4 feet on their rest ankles (two-bone IK on its own legs)
            w = hrt.world_of(fo4.parents, fr)
            rots = {}
            for th, ca, fo in (("LLeg_Thigh", "LLeg_Calf", "LLeg_Foot"), ("RLeg_Thigh", "RLeg_Calf", "RLeg_Foot")):
                hip, knee, ankle = w[fix[th]][0], w[fix[ca]][0], w[fix[fo]][0]
                nk, reached, _m = hrt.two_bone_ik(hip, knee, ankle, rest_w[fix[fo]][0])
                r1 = hrt.quat_between(hrt._sub(knee, hip), hrt._sub(nk, hip))
                wc = aa.q_mul(r1, w[fix[ca]][1])
                a1 = hrt._add(nk, aa.q_rotate(wc, fo4.rest[fix[fo]][0]))
                r2 = hrt.quat_between(hrt._sub(a1, nk), hrt._sub(reached, nk))
                rots[th], rots[ca], rots[fo] = aa.q_mul(r1, w[fix[th]][1]), aa.q_mul(r2, wc), rest_w[fix[fo]][1]
            frames.append(hrt.set_world_rotations(fo4, fr, rots))
        clip = hrt.Fo4Clip(frames, [(0, 0, 0, 0)] * len(frames), [], 30.0, "NORMAL")
        for ik in (False, True):
            rt = hrt.Retargeter(fo4, sf, pairs=TOY_PAIRS)
            rt.leg_ik = ik
            rt.prepare()
            out = hrt.retarget_clip(rt, clip)
            rep = hrt.compare(rt, clip, out, joints=TOY_JOINTS, segments=TOY_SEGMENTS)
            slide = max(rep[c].get("stance_slide_m", {"max": 0.0})["max"] for c in ("L_leg", "R_leg"))
            if ik:
                self.assertLess(slide, 1e-6)
            else:
                self.assertGreater(slide, 1e-3)


class OffsetRuleTests(unittest.TestCase):
    BONES = [{"name": "Root", "parent": -1, "translation": (0, 0, 0), "rotation": (0, 0, 0, 1)},
             {"name": "Weapon", "parent": 0, "translation": (0.1, 0.2, 0.3), "rotation": aa.q_norm((0.5, -0.4, -0.5, -0.4))}]

    def test_translation_offset_not_rotated(self):
        frames = [[((0, 0, 0), (0, 0, 0, 1)), ((0.15, 0.2, 0.25), aa.q_norm((0.4, -0.5, -0.5, -0.4)))]]
        off = hrt.offsets_from_local(self.BONES, frames)
        t_o, q_o = off["Weapon"][0]
        self.assertLess(math.dist(t_o, (0.05, 0.0, -0.05)), 1e-12)           # t - t_bind, in the parent's axes
        blocks = aa.build_blocks(self.BONES, off, 1, keys_are="offset")
        back = hrt.local_from_offsets(self.BONES, blocks, 1)
        self.assertLess(math.dist(back[0][1][0], frames[0][1][0]), 1e-12)
        self.assertLess(aa.q_angle(back[0][1][1], frames[0][1][1]), 1e-7)

    def test_clip_bones(self):
        bones = [{"name": f"B{i}", "key": None} for i in range(5)] + [{"name": f"T{i}", "key": 142 + i} for i in range(3)]
        self.assertEqual(len(hrt.clip_bones(bones)), 5)
        bad = bones[:2] + [{"name": "T", "key": 150}] + bones[2:]
        with self.assertRaises(hrt.RetargetError):
            hrt.clip_bones(bad)
        self.assertEqual(len(hrt.clip_bones(bones[:5])), 5)


class ManifestTests(unittest.TestCase):
    def test_override_in_place(self):
        vanilla = ["AnimTextData\\Tables\\Graphs\\NPC_Melee.agx", "actors\\human\\animations\\common\\a.af",
                   "Actors\\Human\\Animations\\Melee\\Unarmed\\Relaxed_Idle.af", "actors\\x\\b.af"]
        ours = ["Actors\\FO4SF\\Human\\Animations\\Melee\\Unarmed\\relaxed_idle.af", "Actors\\FO4SF\\new.af"]
        out = hrt.override_file_list(vanilla, ours)
        self.assertEqual(out, [vanilla[0], vanilla[1], ours[0], vanilla[3], ours[1]])
        with self.assertRaises(hrt.RetargetError):
            hrt.override_file_list(vanilla, ours + ["other\\Relaxed_Idle.af"])

    def test_angry_rule(self):
        """Vanilla's AnimArchetypeAngry row lists the default row's clips with its five same-named files swapped in."""
        default = ["g.agx", "actors\\human\\animations\\melee\\unarmed\\relaxed_walkforward.af",
                   "actors\\human\\animations\\melee\\unarmed\\relaxed_idle.af"]
        angry = ["actors\\human\\animations\\melee\\unarmed\\angry\\relaxed_walkforward.af"]
        self.assertEqual(set(hrt.override_file_list(default, angry)), {default[0], default[2], angry[0]})

    def test_file_data_round_trip(self):
        raw = hrt.animation_file_data_in_order(42, ["b.af", "a.af"])
        self.assertEqual(raw, b"3\n1\n42\n2\nb.af\na.af\n")
        self.assertEqual(hrt.parse_animation_file_data(raw), (42, ["b.af", "a.af"]))
        with self.assertRaises(hrt.RetargetError):
            hrt.parse_animation_file_data(b"3\n1\n42\n3\nb.af\n")


class EventTests(unittest.TestCase):
    def test_passes_under_hips(self):
        """A foot swinging forward then sliding back under the hips (in place) crosses once."""
        sk = hrt.Skel(["Root", "Hips", "L_Thigh", "R_Thigh", "L_Foot"], [-1, 0, 1, 1, 0],
                      [((0, 0, 0), hrt.IDENTITY), ((0, 0, 1), hrt.IDENTITY), ((-0.1, 0, 0), hrt.IDENTITY),
                       ((0.1, 0, 0), hrt.IDENTITY), ((0, 0, 0.1), hrt.IDENTITY)])
        ys = [0.0, 0.2, 0.3, 0.15, 0.04, -0.06, -0.2, -0.1, 0.0]
        frames = [[sk.rest[0], sk.rest[1], sk.rest[2], sk.rest[3], ((0, y, 0.1), hrt.IDENTITY)] for y in ys]
        self.assertEqual(hrt.passes_under_hips(sk, frames, "L_Foot", ("L_Thigh", "R_Thigh")), [4])


class StageTests(unittest.TestCase):
    def setUp(self):
        import stage_ra4_human as ra4
        self.ra4 = ra4

    def _template_race(self):
        subs = [(b"EDID", esm.zbytes("SFBGS003_HumanRace")), (b"FULL", struct.pack("<I", 0x8A4)),
                (b"DESC", struct.pack("<I", 0)), (b"KWDA", struct.pack("<I", 0x25E194)),
                (b"SADD", struct.pack("<I", 0x347D)), (b"SAKD", struct.pack("<I", 0x251535)),
                (b"STKD", struct.pack("<I", 0xFD00F650)), (b"SGNM", esm.zbytes("g.agx")), (b"SAPT", esm.zbytes("a")),
                (b"SRAF", bytes(4)), (b"PTOP", struct.pack("<f", 15.0))]
        return esm.Record(b"RACE", 0xFD00009D, subs)

    def test_addon_race_rows(self):
        row = self.ra4.row_subrecords([0x01000800], [], "AnimTextData\\Tables\\Graphs\\NPC_MT_Wrapping.agx",
                                      ["ours", "v1"], bytes(4))
        self.assertEqual([s for s, _ in row], [b"SAKD", b"SGNM", b"SAPT", b"SAPT", b"SRAF"])
        r = self.ra4.addon_race(self._template_race(), 0x01000801, "FO4SF_X", "X", [row])
        sigs = [s for s, _ in r.subs]
        self.assertEqual(sigs, [b"EDID", b"FULL", b"DESC", b"KWDA", b"SADD", b"SAKD", b"SGNM", b"SAPT", b"SAPT",
                                b"SRAF", b"PTOP"])
        self.assertEqual(r.get(b"FULL"), esm.zbytes("X"))
        self.assertNotIn(struct.pack("<I", 0xFD00F650), [d for _s, d in r.subs])
        bad = self._template_race()
        bad.subs.insert(2, (b"GNAM", struct.pack("<I", 0xFD000123)))
        with self.assertRaises(self.ra4.Ra4Error):
            self.ra4.addon_race(bad, 0x01000801, "FO4SF_X", "X", [row])

    def test_test_npc(self):
        subs = [(b"EDID", esm.zbytes("Tpl")), (b"ACBS", bytes(16)), (b"SNAM", bytes(5)), (b"RNAM", struct.pack("<I", 0x347D)),
                (b"AIDT", bytes([2, 3, 0, 0, 0, 0, 0])), (b"PKID", struct.pack("<I", 1)), (b"PKID", struct.pack("<I", 2)),
                (b"FULL", struct.pack("<I", 7)), (b"SHRT", struct.pack("<I", 8))]
        r, rep = self.ra4.test_npc(esm.Record(b"NPC_", 0x14A813, subs), 0x01000802, "E", "FO4 Clip Test", [0x01000800], 0x21E76)
        sigs = [s for s, _ in r.subs]
        self.assertEqual(sigs, [b"EDID", b"ACBS", b"RNAM", b"AIDT", b"PKID", b"KSIZ", b"KWDA", b"FULL"])
        self.assertEqual(r.get(b"KWDA"), struct.pack("<I", 0x01000800))
        self.assertEqual(r.get(b"PKID"), struct.pack("<I", 0x21E76))
        self.assertEqual(r.get(b"AIDT")[0], 0)
        female = list(subs)
        female[1] = (b"ACBS", struct.pack("<I", 1) + bytes(12))
        with self.assertRaises(self.ra4.Ra4Error):
            self.ra4.test_npc(esm.Record(b"NPC_", 1, female), 2, "E", "N", [], 3)

    def test_bats(self):
        bats = self.ra4.build_bats()
        for name, text in bats.items():
            self.assertIsNone(self.ra4.P3_FORBIDDEN_RE.search(name))
            self.assertIn("player.placeatme XX", text)
            self.assertNotIn("FO4SF_", text)
        self.assertIn("player.placeatme 0A000802 1", self.ra4.build_bats(0x0A)["ra4a.txt"])
        for name in self.ra4.NPC_NAMES.values():
            self.assertIsNone(self.ra4.P3_FORBIDDEN_RE.search(name))

    def test_gsd_row(self):
        raw = self.ra4.gsd_row("KW", "g.agx", ["a", "b"])
        self.assertEqual(raw.decode().splitlines()[1], "MT\t3rd\tKW\t\tg.agx\ta, b")


@unittest.skipUnless((Path(r"D:\FO4SF-Owner-Tests\robot-anim\RA4") / "manifest.json").is_file(), "no staged RA4 bundle here")
class StagedBundleTests(unittest.TestCase):
    def test_verify(self):
        import stage_ra4_human as ra4
        rep = ra4.verify(ra4.OUT)
        self.assertEqual(len(rep["our_clips_listed"]), 4)
        self.assertEqual(rep["records"]["01000801"], "FO4SF_RA4HumanAddRace")


if __name__ == "__main__":
    unittest.main()
