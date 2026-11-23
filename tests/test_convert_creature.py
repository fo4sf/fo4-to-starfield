"""scripts/actors/convert_creature.py: rig names, COM insertion, rebase choice, the finished rig (synthetic)."""
import math
import os
import sys
import unittest

HERE = os.path.dirname(__file__)
for p in (os.path.join(HERE, "..", "src"), os.path.join(HERE, "..", "scripts", "actors")):
    if p not in sys.path:
        sys.path.insert(0, p)

from fo4sf import actor_skin  # noqa: E402
import convert_creature as cc  # noqa: E402

I = actor_skin.IDENT_R


def rot_z(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return (c, -s, 0.0, s, c, 0.0, 0.0, 0.0, 1.0)


def rot_y(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return (c, 0.0, s, 0.0, 1.0, 0.0, -s, 0.0, c)


def roach(unit=70.0):
    """Root -> Pelivis (turned, 24 units up) -> Spine1 / 1LLeg1 / 1RLeg1 / Head (FO4 units); no COM."""
    names = ["Root", "Pelivis", "Spine1", "1LLeg1", "1RLeg1", "Head"]
    parents = [-1, 0, 1, 1, 1, 2]
    local = [((0.0, 0.0, 0.0), I, 1.0), ((0.2, 0.0, 24.0), rot_y(20.0), 1.0), ((0.0, 0.0, 7.0), rot_z(80.0), 1.0),
             ((-1.7, 4.8, -2.8), rot_y(130.0), 1.0), ((1.7, 4.8, -2.8), rot_y(-130.0), 1.0),
             ((0.0, 5.0, 1.0), rot_z(30.0), 1.0)]
    return actor_skin.Skeleton(names, parents, local, [False] * len(names), "Root")


def positions(skel):
    return [w[0] for w in skel.world()]


class TestNames(unittest.TestCase):
    def test_rig_name_map(self):
        names = ["Dogmeat_Root", "Dogmeat_COM", "Dogmeat_Ear_L1", "Dogmeat_Front_LLeg|1", "Other"]
        parents = [-1, 0, 1, 1, 1]
        m = cc.rig_name_map(names, parents, "Dogmeat_")
        self.assertEqual(m, {"Dogmeat_Root": "Root", "Dogmeat_COM": "COM", "Dogmeat_Ear_L1": "Ear_L1",
                             "Dogmeat_Front_LLeg|1": "Front_LLeg_1", "Other": "Other"})
        self.assertEqual(cc.rig_name_map(["Base", "com"], [-1, 0])["com"], "COM")
        with self.assertRaises(ValueError):
            cc.rig_name_map(["Root", "A|1", "A-1"], [-1, 0, 0])

    def test_force_root_identity(self):
        s = roach()
        s.local[0] = ((1.0, 2.0, 3.0), rot_z(10.0), 1.0)
        out, off = cc.force_root_identity(s)
        self.assertGreater(off, 1.0)
        self.assertEqual(out.local[0], ((0.0, 0.0, 0.0), I, 1.0))
        self.assertEqual(out.local[1:], s.local[1:])


class TestComInsert(unittest.TestCase):
    def test_insert_keeps_world_pose(self):
        s = roach()
        out, ins = cc.insert_com(s)
        self.assertEqual(out.names[:3], ["Root", "COM", "Pelivis"])
        self.assertEqual(out.parents[:3], [-1, 0, 1])
        self.assertEqual(ins.new_index, [0, 2, 3, 4, 5, 6])
        self.assertEqual(ins.reparented, [1])
        self.assertEqual(out.local[1][1], I)
        a, b = positions(s), positions(out)
        for i in range(len(s.names)):
            self.assertLess(math.dist(a[i], b[ins.new_index[i]]), 1e-9)
        self.assertLess(math.dist(b[1], a[1]), 1e-9)           # COM stands on the body bone
        for i in range(len(s.names)):                           # rotations unchanged too
            ra, rb = s.world()[i][1], out.world()[ins.new_index[i]][1]
            self.assertLess(max(abs(x - y) for x, y in zip(ra, rb)), 1e-9)

    def test_existing_com_kept(self):
        s = roach()
        s.names[1] = "Dogmeat_COM"
        out, ins = cc.insert_com(s, strip_prefix="Dogmeat_")
        self.assertIsNone(ins)
        self.assertIs(out, s)
        _out, ins2 = cc.insert_com(s)                       # without the prefix rule it would add one
        self.assertIsNotNone(ins2)

    def test_frames_round_trip(self):
        sys.path.insert(0, os.path.join(HERE, "..", "scripts", "probes"))
        import stage_ra5_creatures as ra5
        s = roach()
        _out, ins = cc.insert_com(s)
        fr = [[((0.1, 0.2, 0.0), (0.0, 0.0, 0.0, 1.0)), ((0.3, 0.0, 24.0), (0.1, 0.0, 0.0, math.sqrt(0.99))),
               ((0.0, 0.0, 7.0), (0.0, 0.0, 0.2, math.sqrt(0.96))), ((-1.7, 4.8, -2.8), (0, 0, 0, 1)),
               ((1.7, 4.8, -2.8), (0, 0, 0, 1)), ((0.0, 5.0, 1.0), (0, 0, 0, 1))]]
        s1 = cc.insert_com_frames(fr, ins)
        self.assertEqual(len(s1[0]), 7)
        self.assertEqual(s1[0][1][0], ins.com_local[0])
        back = ra5.remove_com_frames(s1, ins)
        for (t0, q0), (t1, q1) in zip(fr[0], back[0]):
            self.assertLess(math.dist(t0, t1), 1e-9)
            self.assertLess(max(abs(a - b) for a, b in zip(q0, q1)), 1e-6)
        self.assertEqual(cc.insert_com_frames(fr, None), fr)


class TestRig(unittest.TestCase):
    def test_build_rig(self):
        s = roach()
        rig = cc.build_rig(s, rebase=["COM", "Pelivis", "Head"])
        names = rig.skel.names
        self.assertEqual(names[:2], ["Root", "COM"])
        self.assertEqual(names[-1], "DirectAt")
        self.assertEqual(rig.skel.parents[-1], names.index("COM"))
        for n in ("Pelivis", "Head"):
            self.assertLess(actor_skin.rotation_angle_deg(rig.skel.local[names.index(n)][1], I), 1e-6)
        src = positions(rig.source)
        out = positions(rig.skel)
        for i in range(len(rig.source.names)):
            self.assertLess(math.dist(src[i], out[rig.com.new_index[i]]), 1e-9)
        self.assertAlmostEqual(out[1][2], 24.0 / 70.0, places=9)      # metres
        self.assertTrue(rig.report["names_safe"])
        self.assertTrue(rig.report["com_inserted"])
        self.assertEqual(rig.report["reparented_under_com"], ["Pelivis"])

    def test_bones_to_rebase(self):
        s = roach().scaled(1 / 70.0)
        bind = [(t, (0.0, 0.0, 0.0, 1.0)) for t, _r, _s in s.local]
        still = [list(bind)] * 3
        moved = [list(bind) for _ in range(3)]
        moved[2][1] = ((bind[1][0][0], bind[1][0][1], bind[1][0][2] + 0.01), bind[1][1])
        moved[1][5] = ((bind[5][0][0] + 5e-5, bind[5][0][1], bind[5][0][2]), bind[5][1])    # below the threshold
        moved[0][0] = ((1.0, 0.0, 0.0), bind[0][1])                                        # root: never rebased
        self.assertEqual(cc.bones_to_rebase(s.names, {"a": still, "b": moved}, bind, None), ["Pelivis"])
        _o, ins = cc.insert_com(roach())
        self.assertEqual(cc.bones_to_rebase(s.names, {"a": still}, bind, ins), ["COM"])


if __name__ == "__main__":
    unittest.main()
