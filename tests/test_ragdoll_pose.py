"""FO4 `XRGD` ragdoll pose -> bone world transforms (ragdoll_pose.py). Synthetic NIFs only, no game data.

The conventions under test come from docs/ai/research-log.md 2026-10-11 "XRGD ragdoll pose decoded": one 28-byte entry
per physics body in body-index order; an entry replaces its bone node's local transform (parent-node frame, game units);
rotation = Rx(-x) Ry(-y) Rz(-z) (Gamebryo Euler XYZ, the NIF's own row-major convention)."""
import math
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from fo4sf import nif, ragdoll_pose as rp  # noqa: E402

IDENTITY = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)


# ---- independent reference maths -------------------------------------------------------------------------------------
def rx(a):
    c, s = math.cos(a), math.sin(a)
    return (1, 0, 0, 0, c, -s, 0, s, c)


def ry(a):
    c, s = math.cos(a), math.sin(a)
    return (c, 0, s, 0, 1, 0, -s, 0, c)


def rz(a):
    c, s = math.cos(a), math.sin(a)
    return (c, -s, 0, s, c, 0, 0, 0, 1)


def mm(a, b):
    return tuple(sum(a[3 * r + k] * b[3 * k + c] for k in range(3)) for r in range(3) for c in range(3))


def mv(m, v):
    return tuple(sum(m[3 * r + k] * v[k] for k in range(3)) for r in range(3))


def dist(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def entry_bytes(entries):
    return b"".join(struct.pack("<B3s3f3f", 0, b"\0\0\0", *pos, *rot) for pos, rot in entries)


# ---- synthetic ragdoll NIF ---------------------------------------------------------------------------------------------
def node_block(name_idx, trans, rot, scale, children=(), collision=-1):
    return (struct.pack("<iIiI", name_idx, 0, -1, 0xE) + struct.pack("<3f", *trans) + struct.pack("<9f", *rot)
            + struct.pack("<f", scale) + struct.pack("<i", collision)
            + struct.pack(f"<I{len(children)}i", len(children), *children))


def colobj_block(target, system, body):
    return struct.pack("<iHiI", target, 0x80, system, body)


def ragdoll_nif(bind, thigh_scale=1.0, reversed_colobjs=False):
    """root (identity, no body) -> hip (body 0) -> thigh (body 1) -> shin (body 2); a 'tag' NiNode without a body hangs
    under the thigh at local (1, 0, 0). `bind` = {name: (translation, row-major rotation)} for hip, thigh, shin.
    Blocks: 0 root, 1 hip, 2 thigh, 3 shin, 4-6 collision objects, 7 tag, 8 bhkPhysicsSystem (unreadable packfile, so the
    body count comes from the collision objects)."""
    f = nif.NifFile(bs_version=130, author=b"t\x00", process_script=b"\x00", export_script=b"\x00", max_filepath=b"\x00")
    names = {k: f.string_index(k.encode()) for k in ("root", "hip", "thigh", "shin", "tag")}
    f.add_block("NiNode", node_block(names["root"], (0, 0, 0), IDENTITY, 1.0, children=(1,)))
    f.add_block("NiNode", node_block(names["hip"], *bind["hip"], 1.0, children=(2,), collision=4))
    f.add_block("NiNode", node_block(names["thigh"], *bind["thigh"], thigh_scale, children=(3, 7), collision=5))
    f.add_block("NiNode", node_block(names["shin"], *bind["shin"], 1.0, collision=6))
    bodies = [(1, 0), (2, 1), (3, 2)]
    if reversed_colobjs:
        bodies.reverse()
    for target, body in bodies:
        f.add_block("bhkNPCollisionObject", colobj_block(target, 8, body))
    f.add_block("NiNode", node_block(names["tag"], (1, 0, 0), IDENTITY, 1.0))
    f.add_block("bhkPhysicsSystem", struct.pack("<I", 0))
    f.footer = struct.pack("<II", 1, 0)
    return nif.serialize(f)


BIND = {"hip": ((0.0, 0.0, 84.0), IDENTITY),
        "thigh": ((-7.0, 1.9, -13.4), rp.euler_matrix((0.3, -1.1, 2.0))),
        "shin": ((-0.5, 1.6, 32.9), rp.euler_matrix((-0.1, 0.0, 0.05)))}
HIP, THIGH, SHIN, TAG = 1, 2, 3, 7


class XrgdParsingTests(unittest.TestCase):
    def test_entries_are_28_bytes_in_order(self):
        raw = struct.pack("<B3s3f3f", 7, b"\x29\x7f\x21", 1.0, 2.0, 3.0, 0.1, 0.2, 0.3) + entry_bytes([((0, 0, 5), (0, 0, 0))])
        e = rp.parse_xrgd(raw)
        self.assertEqual(len(e), 2)
        self.assertEqual((e[0].bone_id, e[0].unused), (7, b"\x29\x7f\x21"))
        self.assertEqual(e[0].position, (1.0, 2.0, 3.0))
        self.assertEqual(tuple(round(v, 6) for v in e[0].rotation), (0.1, 0.2, 0.3))
        self.assertEqual(e[1].position, (0.0, 0.0, 5.0))
        with self.assertRaisesRegex(rp.RagdollPoseError, "multiple of 28"):
            rp.parse_xrgd(raw[:-1])

    def test_export_dicts_are_read_in_index_order(self):
        items = [{"index": 1, "bone_id": 0, "unused": "000000", "pos": [0, 0, 5], "rot": [0, 0, 0]},
                 {"index": 0, "bone_id": 0, "unused": "297f21", "pos": [1, 2, 3], "rot": [0.1, 0.2, 0.3]}]
        e = rp.entries_from_export(items)
        self.assertEqual([x.position for x in e], [(1.0, 2.0, 3.0), (0.0, 0.0, 5.0)])
        with self.assertRaisesRegex(rp.RagdollPoseError, "indices"):
            rp.entries_from_export(items[:1])


class EulerConventionTests(unittest.TestCase):
    def test_rotation_is_clockwise_x_then_y_then_z(self):
        # z = +90 deg turns +x onto -y (clockwise seen from +z): the NIF / Gamebryo convention
        self.assertEqual(tuple(round(v, 9) for v in rp.euler_matrix((0.0, 0.0, math.pi / 2))), (0, 1, 0, -1, 0, 0, 0, 0, 1))
        a, b, c = 0.3, -1.1, 2.0
        want = mm(rx(-a), mm(ry(-b), rz(-c)))
        for got, w in zip(rp.euler_matrix((a, b, c)), want):
            self.assertAlmostEqual(got, w, places=9)
        wrong = mm(rz(-c), mm(ry(-b), rx(-a)))                      # the other multiplication order differs
        self.assertGreater(max(abs(g - w) for g, w in zip(rp.euler_matrix((a, b, c)), wrong)), 0.1)


class PoseBonesTests(unittest.TestCase):
    def test_bind_pose_entries_reproduce_the_nif_world_transforms(self):
        raw = ragdoll_nif(BIND)
        entries = [((0.0, 0.0, 84.0), (0.0, 0.0, 0.0)), ((-7.0, 1.9, -13.4), (0.3, -1.1, 2.0)), ((-0.5, 1.6, 32.9), (-0.1, 0.0, 0.05))]
        posed = rp.pose_bones(raw, entry_bytes(entries))
        world = nif.world_transforms(nif.parse(raw))
        self.assertEqual(sorted(posed), [HIP, THIGH, SHIN])
        for node in (HIP, THIGH, SHIN):
            t, r, s = world(node)
            for got, w in zip(posed[node].translation, t):
                self.assertAlmostEqual(got, w, places=4)
            for got, w in zip(sum(posed[node].rotation, ()), r):
                self.assertAlmostEqual(got, w, places=5)
            self.assertEqual(posed[node].scale, 1.0)

    def test_entries_replace_local_transforms_and_compose_down_the_chain(self):
        raw = ragdoll_nif(BIND)
        entries = [((0.0, 0.0, 0.0), (0.0, 0.0, math.pi / 2)),      # hip: on the reference, turned 90 deg about z
                   ((0.0, 0.0, 20.0), (math.pi / 2, 0.0, 0.0)),     # thigh: 20 units up the hip's z, turned about x
                   ((0.0, 0.0, 5.0), (0.0, 0.0, 0.0))]              # shin: 5 units along the thigh's z
        posed = rp.pose_bones(raw, entry_bytes(entries), all_nodes=True)
        hip, thigh, shin, tag = (posed[i] for i in (HIP, THIGH, SHIN, TAG))
        self.assertEqual(tuple(round(v, 6) for v in hip.translation), (0, 0, 0))
        self.assertEqual(tuple(round(v, 6) for v in thigh.translation), (0, 0, 20))
        # Rx(-90) takes (0,0,5) to (0,5,0) (y' = z), then Rz(-90) takes that to (5,0,0) (x' = y)
        self.assertEqual(tuple(round(v, 6) for v in shin.translation), (5, 0, 20))
        # bone lengths are the entry offsets, whatever the parents' rotations
        self.assertAlmostEqual(dist(thigh.translation, hip.translation), 20.0, places=6)
        self.assertAlmostEqual(dist(shin.translation, thigh.translation), 5.0, places=6)
        # rotations compose parent * local (entries are float32 in the record: pi/2 rounds to ~4e-8)
        for got, w in zip(sum(thigh.rotation, ()), mm(rz(-math.pi / 2), rx(-math.pi / 2))):
            self.assertAlmostEqual(got, w, places=6)
        # a node without a body keeps its NIF transform under its posed parent: (1,0,0) in the thigh frame
        self.assertEqual(tuple(round(v, 6) for v in tag.translation), (0, -1, 20))
        self.assertEqual(posed[0].translation, (0.0, 0.0, 0.0))

    def test_entries_follow_the_body_index_not_the_collision_block_order(self):
        entries = [((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)), ((0.0, 0.0, 20.0), (0.0, 0.0, 0.0)), ((0.0, 0.0, 5.0), (0.0, 0.0, 0.0))]
        plain = rp.pose_bones(ragdoll_nif(BIND), entry_bytes(entries))
        shuffled = rp.pose_bones(ragdoll_nif(BIND, reversed_colobjs=True), entry_bytes(entries))
        self.assertEqual(plain, shuffled)
        self.assertEqual(tuple(round(v, 6) for v in shuffled[SHIN].translation), (0, 0, 25))

    def test_export_dicts_and_raw_bytes_pose_alike(self):
        entries = [((0.0, 0.0, 84.0), (0.0, 0.0, 0.3)), ((-7.0, 1.9, -13.4), (0.3, -1.1, 2.0)), ((-0.5, 1.6, 32.9), (-0.1, 0.0, 0.05))]
        items = [{"index": k, "bone_id": 0, "unused": "", "pos": list(p), "rot": list(r)} for k, (p, r) in enumerate(entries)]
        a = rp.pose_bones(ragdoll_nif(BIND), entry_bytes(entries))
        b = rp.pose_bones(ragdoll_nif(BIND), list(reversed(items)))
        for node in a:
            for got, w in zip(a[node].translation, b[node].translation):
                self.assertAlmostEqual(got, w, places=4)

    def test_entry_count_must_match_the_body_count(self):
        stale = entry_bytes([((0, 0, 0), (0, 0, 0)), ((0, 0, 20), (0, 0, 0))])
        with self.assertRaisesRegex(rp.RagdollPoseError, "2 ragdoll entries for 3 bodies"):
            rp.pose_bones(ragdoll_nif(BIND), stale)

    def test_non_finite_entry_is_rejected(self):
        bad = entry_bytes([((0, 0, 0), (0, 0, 0)), ((0, 0, float("nan")), (0, 0, 0)), ((0, 0, 5), (0, 0, 0))])
        with self.assertRaisesRegex(rp.RagdollPoseError, "entry 1 is not finite"):
            rp.pose_bones(ragdoll_nif(BIND), bad)

    def test_scaled_bone_node_is_rejected(self):
        entries = entry_bytes([((0, 0, 0), (0, 0, 0)), ((0, 0, 20), (0, 0, 0)), ((0, 0, 5), (0, 0, 0))])
        with self.assertRaisesRegex(rp.RagdollPoseError, "scale"):
            rp.pose_bones(ragdoll_nif(BIND, thigh_scale=2.0), entries)


if __name__ == "__main__":
    unittest.main()
