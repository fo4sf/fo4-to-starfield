"""actor_skin: Havok skeleton reader, multi-weight actor mesh NIF, skeleton NIFs, Mr. Handy bone names.
Synthetic data; the last class reads the real game files and is skipped when they are absent."""
import math
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from fo4sf import actor_skin, fo4skin, hkpackfile, nif as nifmod, sfmesh, sfnif  # noqa: E402

FO4_DATA = r"D:\SteamLibrary\steamapps\common\Fallout 4\Data"
IDENT = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)
S = math.sqrt(0.5)


def make_packfile(bones, pad=16):
    """A minimal hk_2014 64-bit packfile holding one hkaSkeleton. bones: [(name, parent, t, quat xyzw)]."""
    n = len(bones)
    data = bytearray(136)                                  # hkaSkeleton object at 0
    local = []

    def put(blob, align=16):
        while len(data) % align:
            data.append(0)
        at = len(data)
        data.extend(blob)
        return at

    name_at = put(b"Root\0")
    local.append((16, name_at))
    par_at = put(struct.pack(f"<{n}h", *[b[1] for b in bones]))
    local.append((24, par_at))
    bones_at = put(bytes(16 * n))
    local.append((40, bones_at))
    pose_at = put(b"".join(struct.pack("<4f4f4f", *b[2], 0.0, *b[3], 1.0, 1.0, 1.0, 1.0) for b in bones))
    local.append((56, pose_at))
    for off, cnt in ((24, n), (40, n), (56, n)):
        struct.pack_into("<iI", data, off + 8, cnt, 0x80000000 | cnt)
    for i, b in enumerate(bones):
        local.append((bones_at + 16 * i, put(b[0].encode() + b"\0", 1)))
    while len(data) % 16:
        data.append(0)
    classnames = bytearray(struct.pack("<IB", 0x12345678, 9) + b"hkaSkeleton\0")
    while len(classnames) % 16:
        classnames.append(0xFF)
    sections = []
    header = bytearray(b"\x57\xe0\xe0\x57\x10\xc0\xc0\x10" + struct.pack("<ii", 0, 11) + bytes([8, 1, 0, 1])
                       + struct.pack("<iiiii", 3, 2, 0, 0, 0) + b"hk_2014.1.0-r1\0\xff" + struct.pack("<ihh", 0, 21, pad))
    assert len(header) == 64
    header += b"\xff" * pad
    start = len(header) + 3 * 64
    body = bytearray()
    # __classnames__: names only
    sections.append(("__classnames__", start, len(classnames), len(classnames), len(classnames), len(classnames),
                     len(classnames), len(classnames)))
    body += classnames
    sections.append(("__types__", start + len(body), 0, 0, 0, 0, 0, 0))
    dstart = start + len(body)
    loc = len(data)
    fix = b"".join(struct.pack("<ii", a, b) for a, b in local)
    glo = loc + len(fix)
    vfix = struct.pack("<iii", 0, 0, 5)                    # object at 0, class name at classnames offset 5
    vir = glo
    exp = vir + len(vfix)
    sections.append(("__data__", dstart, loc, glo, vir, exp, exp, exp))
    body += data + fix + vfix
    for tag, st, lo, gl, vi, ex, im, en in sections:
        header += tag.encode().ljust(20, b"\0") + struct.pack("<7i", st, lo, gl, vi, ex, im, en) + b"\xff" * 16
    return bytes(header + body)


BONES = [("Root", -1, (0, 0, 0), (0, 0, 0, 1)),
         ("COM", 0, (0, 0, 70.0), (0, -S, 0, S)),           # -90 degrees about Y, like the Handy COM
         ("ArmA|0", 1, (35.0, 0, 0), (0, 0, 0, 1)),
         ("ArmB|0", 2, (21.0, 0, 0), (0, 0, S, S)),          # +90 degrees about Z
         ("ArmC|0", 3, (10.0, 0, 0), (0, 0, 0, 1)),
         ("Anim", 0, (0, 0, 0), (0, 0, 0, 1))]


class HavokSkeleton(unittest.TestCase):
    def test_padded_header_and_skeleton_fields(self):
        for pad in (0, 16):
            blob = make_packfile(BONES, pad)
            pf = actor_skin._PaddedPackfile(blob)
            self.assertEqual([c for _, c in pf.objects()], ["hkaSkeleton"])
            sk = actor_skin.read_hka_skeleton(blob)
            self.assertEqual(sk.names, [b[0] for b in BONES])
            self.assertEqual(sk.parents, [-1, 0, 1, 2, 3, 0])
            self.assertEqual(sk.name, "Root")
            w = sk.world()
            # COM turns -90 about Y: its local +X points up (world +Z), as FO4 Handy Ring stands above COM
            for a, b in zip(w[2][0], (0.0, 0.0, 105.0)):
                self.assertAlmostEqual(a, b, places=4)

    def test_load_packfile_picks_a_reader_that_sees_the_skeleton(self):
        pf = actor_skin.load_packfile(make_packfile(BONES, 16))
        self.assertEqual(pf.objects("hkaSkeleton")[0][0], 0)

    def test_quaternion_matrix_round_trip(self):
        r = actor_skin.quat_to_matrix((0, 0, S, S))
        for a, b in zip(r, (0, -1, 0, 1, 0, 0, 0, 0, 1)):
            self.assertAlmostEqual(a, b, places=6)
        for q in ((0, 0, 0, 1), (0, -S, 0, S), (0.5, 0.5, 0.5, 0.5), (0.9, 0.1, -0.3, 0.2)):
            n = math.sqrt(sum(c * c for c in q))
            q = tuple(c / n for c in q)
            back = actor_skin.matrix_to_quat(actor_skin.quat_to_matrix(q))
            sign = 1 if q[3] >= 0 else -1
            for a, b in zip(back, q):
                self.assertAlmostEqual(a, sign * b, places=6)


class Weights(unittest.TestCase):
    def test_quantize(self):
        q = actor_skin.quantize_weights([(2, 0.25), (1, 0.5), (2, 0.25), (3, 0.0)])
        self.assertEqual(sorted(s for s, _ in q), [1, 2])
        self.assertTrue(all(abs(w - 32767.5) <= 1 for _, w in q))
        self.assertEqual(sum(w for _, w in q), 65535)
        q = actor_skin.quantize_weights([(0, 0.1), (1, 0.2), (2, 0.3), (3, 0.15), (4, 0.25)])
        self.assertEqual([s for s, _ in q], [2, 4, 1, 3])
        self.assertEqual(sum(w for _, w in q), 65535)
        self.assertTrue(all(a[1] >= b[1] for a, b in zip(q, q[1:])))
        self.assertEqual(actor_skin.quantize_weights([], fallback=5), [(5, 65535)])
        q = actor_skin.quantize_weights([(0, 1.0), (1, 1e-7)])
        self.assertEqual(q, [(0, 65535)])


class HandyNames(unittest.TestCase):
    def test_mapping(self):
        m = actor_skin.handy_mesh_bone_to_hkx
        self.assertEqual(m("MArm_1"), "Arm1|0")
        self.assertEqual(m("RArm_7"), "Arm7|1")
        self.assertEqual(m("LArm_Hub2"), "ArmHub2|2")
        self.assertEqual(m("LArm_Palm"), "ArmPalm|2")
        self.assertEqual(m("MArm_Palm_Bone3"), "ArmPalmBone3|0")
        self.assertEqual(m("REyeArm_Flap"), "EyeArm_Flap|1")
        self.assertEqual(m("LEyeArmPalm_Lens"), "EyeArmPalm_Lens|2")
        self.assertEqual(m("MEyeArm2"), "EyeArm2|0")
        self.assertEqual(m("HEAD"), "Neck")
        self.assertEqual(m("Pelvis"), "Pelvis")
        self.assertIsNone(m("Bip01 Spine"))


def synthetic_skeleton():
    return actor_skin.read_hka_skeleton(make_packfile(BONES)).scaled(1 / 70)


def synthetic_part(skel):
    w = skel.world()
    pa = w[skel.index("ArmA|0")][0]
    pb = w[skel.index("ArmB|0")][0]
    pts = [tuple(c * 70 for c in p) for p in (pa, pb, (pb[0] + 0.1, pb[1], pb[2]), (pa[0], pa[1] + 0.1, pa[2]))]
    shape = nifmod.Fo4Shape(b"Part", (0, 0, 0), IDENT, 1.0, -1, -1, -1, pts, [(0, 0), (1, 0), (1, 1), (0, 1)],
                            [(0, 0, 1)] * 4, [(1, 0, 0)] * 4, [], [(0, 1, 2), (0, 2, 3)], False)
    inf = [[("ArmA|0", 1.0)], [("ArmA|0", 0.5), ("ArmB|0", 0.5)], [("ArmB|0", 0.7), ("ArmA|0", 0.2), ("ArmC|0", 0.1)],
           [("ArmA|0", 0.0), ("ArmB|0", 1.0)]]
    return actor_skin.SkinPart("Part", shape, inf, "materials\\test\\a.mat"), [tuple(c / 70 for c in p) for p in pts], inf


class MeshNif(unittest.TestCase):
    def test_build_and_verify(self):
        skel = synthetic_skeleton()
        part, expected, inf = synthetic_part(skel)
        res = actor_skin.build_actor_mesh_nif(skel, [part], unit_scale=1 / 70)
        rep = actor_skin.verify_actor_mesh_nif(res.nif, res.meshes, skel, {"Part": expected}, {"Part": inf})
        self.assertTrue(rep["ok"], rep["errors"])
        s = rep["shapes"]["Part"]
        self.assertEqual(s["weights_per_vertex"], 3)
        self.assertEqual(s["bone_names"], ["ArmA|0", "ArmB|0", "ArmC|0"])
        self.assertLess(s["bind_pose_max_error_mm"], 0.05)
        self.assertEqual(rep["bone_nodes"], 3)                 # ArmA|0, ArmB|0, ArmC|0 below COM
        n = nifmod.parse(res.nif)
        types = [n.type_of(i) for i in range(len(n.blocks))]
        for t in ("BSXFlags", "SkinAttach", "BSSkin::Instance", "BSSkin::BoneData", "BSLightingShaderProperty"):
            self.assertIn(t, types)
        g = sfnif.parse_bsgeometry(n.blocks[types.index("BSGeometry")])
        m = sfmesh.parse(next(iter(res.meshes.values())))
        self.assertEqual(m.colors, [])
        self.assertEqual(g.meshes[0].num_verts, 4)
        # ParentBoneName points the twin at COM
        twin = next(i for i in range(len(n.blocks)) if fo4skin._block_name(n, i) == b"COM_Twin")
        self.assertEqual(n.type_of(twin), "NiNode")

    def test_verify_catches_a_shifted_mesh(self):
        skel = synthetic_skeleton()
        part, expected, inf = synthetic_part(skel)
        res = actor_skin.build_actor_mesh_nif(skel, [part], unit_scale=1 / 70)
        moved = [(x + 0.002, y, z) for x, y, z in expected]
        rep = actor_skin.verify_actor_mesh_nif(res.nif, res.meshes, skel, {"Part": moved})
        self.assertFalse(rep["ok"])
        self.assertTrue(any("bind pose" in e for e in rep["errors"]))

    def test_bone_outside_com_is_refused(self):
        skel = synthetic_skeleton()
        part, _, _ = synthetic_part(skel)
        part.influences[0] = [("Anim", 1.0)]
        with self.assertRaises(ValueError):
            actor_skin.build_actor_mesh_nif(skel, [part])


def template_skeleton_nif() -> bytes:
    f = nifmod.NifFile(endian=1, user_version=12, bs_version=173, author=b"\x00", unknown_int=3,
                       export_script=b"\x00", sf_data=b"\x7a\x00")

    def node(name, kids, coll=-1, t=(0, 0, 0)):
        return actor_skin._node_bytes(f.string_index(name), [], (t, IDENT, 1.0), kids, collision=coll)
    f.add_block("NiNode", node(b"T_mrRigRoot", [1, 4]))
    f.add_block("NiNode", node(b"Root", [2]))
    f.add_block("NiNode", node(b"COM", [], 6, (0, 0, 0.5)))
    f.add_block("BSXFlags", struct.pack("<iI", f.string_index(b"BSX"), 0x4A))
    f.add_block("NiNode", node(b"CharacterController", [], 8))
    f.add_block("NiNode", node(b"Unused", []))
    f.add_block("bhkNPCollisionObject", struct.pack("<iHiI", 2, 0x80, 7, 0))
    f.add_block("bhkPhysicsSystem", struct.pack("<I", 4) + b"COMB")
    f.add_block("bhkNPCollisionObject", struct.pack("<iHiI", 4, 0x80, 9, 0))
    f.add_block("bhkPhysicsSystem", struct.pack("<I", 4) + b"CTRL")
    f.footer = struct.pack("<II", 1, 0)
    return nifmod.serialize(f)


class SkeletonNif(unittest.TestCase):
    def test_skeleton_and_ref(self):
        skel = synthetic_skeleton()
        tmpl = template_skeleton_nif()
        bound = ((0, 0, 0.5), (0.3, 0.3, 0.5))
        for full in (False, True):
            data = actor_skin.build_skeleton_nif(skel, tmpl, b"X_mrRigRoot", bound, full_tree=full)
            rep = actor_skin.verify_skeleton_nif(data, skel, full)
            self.assertTrue(rep["ok"], rep["errors"])
            self.assertEqual(rep["collision_objects"], 2)
            n = nifmod.parse(data)
            names = {fo4skin._block_name(n, i).decode() for i in range(len(n.blocks)) if n.type_of(i) == "NiNode"}
            self.assertIn("CharacterController", names)
            self.assertEqual("ArmB|0" in names, full)
            phys = [n.blocks[i] for i in range(len(n.blocks)) if n.type_of(i) == "bhkPhysicsSystem"]
            self.assertEqual(sorted(p[4:] for p in phys), [b"COMB", b"CTRL"])
            for i in range(len(n.blocks)):
                if n.type_of(i) == "bhkNPCollisionObject":
                    target, _, ref, _ = struct.unpack_from("<iHiI", n.blocks[i], 0)
                    self.assertEqual(n.type_of(target), "NiNode")
                    self.assertEqual(n.type_of(ref), "bhkPhysicsSystem")


def _posed(skel, angle=0.4):
    """The skeleton with every bone turned `angle` about a tilted axis and COM moved: a non-rest pose."""
    q = actor_skin.quat_to_matrix((0.3 * math.sin(angle), 0.2 * math.sin(angle), 0.4 * math.sin(angle), math.cos(angle)))
    local = [(tuple(c + (0.05 if i == 1 else 0.0) for c in t), actor_skin._mat_mul(r, q), s)
             for i, (t, r, s) in enumerate(skel.local)]
    return actor_skin.Skeleton(list(skel.names), list(skel.parents), local, list(skel.lock_translation), skel.name)


class RigEdits(unittest.TestCase):
    def test_starfield_bone_names(self):
        m = actor_skin.starfield_bone_names(["Arm1|0", "C-Head", "EyeArmPalm_IrisSC|2", "Root"])
        self.assertEqual(m, {"Arm1|0": "Arm1_0", "C-Head": "C_Head", "EyeArmPalm_IrisSC|2": "EyeArmPalm_IrisSC_2",
                             "Root": "Root"})
        self.assertTrue(all(actor_skin.SAFE_BONE_NAME.match(v) for v in m.values()))
        with self.assertRaises(ValueError):
            actor_skin.starfield_bone_names(["A|0", "A-0"])
        with self.assertRaises(ValueError):
            actor_skin.starfield_bone_names(["a_b", "A|b"])          # collides ignoring case

    def test_rebase_gives_identity_rest_and_keeps_world_positions(self):
        skel = synthetic_skeleton()
        corr = actor_skin.rest_rotation_corrections(skel, ["COM"])
        new = actor_skin.rebase_skeleton(skel, corr)
        self.assertLess(max(abs(a - b) for a, b in zip(new.local[1][1], IDENT)), 1e-12)
        self.assertGreater(actor_skin.rotation_angle_deg(skel.local[1][1], IDENT), 89.9)
        for pose in (skel, _posed(skel), _posed(skel, -1.1)):
            w0, w1 = pose.world(), actor_skin.rebase_skeleton(pose, corr).world()
            for i in range(len(skel.names)):
                self.assertLess(math.dist(w0[i][0], w1[i][0]), 1e-12)
                # world rotation becomes W_j C_j
                want = actor_skin._mat_mul(w0[i][1], corr[i])
                self.assertLess(max(abs(a - b) for a, b in zip(want, w1[i][1])), 1e-12)

    def test_rebase_chain(self):
        skel = synthetic_skeleton()
        corr = actor_skin.rest_rotation_corrections(skel, ["COM", "ArmB|0"])
        new = actor_skin.rebase_skeleton(skel, corr)
        for n in ("COM", "ArmB|0"):
            self.assertLess(max(abs(a - b) for a, b in zip(new.local[new.index(n)][1], IDENT)), 1e-12)
        self.assertEqual(corr[skel.index("Anim")], IDENT)
        w0, w1 = _posed(skel).world(), actor_skin.rebase_skeleton(_posed(skel), corr).world()
        self.assertLess(max(math.dist(a[0], b[0]) for a, b in zip(w0, w1)), 1e-12)

    def test_add_and_rename(self):
        skel = synthetic_skeleton()
        s2 = actor_skin.add_bone(skel, "DirectAt", "COM", ((0, 0, 0), IDENT, 1.0))
        self.assertEqual(s2.names[-1], "DirectAt")
        self.assertEqual(s2.parents[-1], 1)
        self.assertEqual(s2.names[:-1], skel.names)
        with self.assertRaises(ValueError):
            actor_skin.add_bone(s2, "directat", "COM", ((0, 0, 0), IDENT, 1.0))
        s3 = actor_skin.rename_skeleton(s2, actor_skin.starfield_bone_names(s2.names))
        self.assertEqual(s3.names, ["Root", "COM", "ArmA_0", "ArmB_0", "ArmC_0", "Anim", "DirectAt"])
        with self.assertRaises(ValueError):
            actor_skin.rename_skeleton(s2, {"ArmA|0": "ArmB|0"})

    def test_mesh_exclude(self):
        skel = actor_skin.add_bone(synthetic_skeleton(), "DirectAt", "COM", ((0, 0, 0), IDENT, 1.0))
        part, expected, inf = synthetic_part(skel)
        res = actor_skin.build_actor_mesh_nif(skel, [part], unit_scale=1 / 70, exclude=["DirectAt"])
        n = nifmod.parse(res.nif)
        names = {fo4skin._block_name(n, i).decode() for i in range(len(n.blocks)) if n.type_of(i) == "NiNode"}
        self.assertNotIn("DirectAt", names)
        rep = actor_skin.verify_actor_mesh_nif(res.nif, res.meshes, skel, {"Part": expected}, {"Part": inf},
                                               exclude=["DirectAt"])
        self.assertTrue(rep["ok"], rep["errors"])
        self.assertFalse(actor_skin.verify_actor_mesh_nif(res.nif, res.meshes, skel, {"Part": expected})["ok"])
        part.influences[0] = [("DirectAt", 1.0)]
        with self.assertRaises(ValueError):
            actor_skin.build_actor_mesh_nif(skel, [part], unit_scale=1 / 70, exclude=["DirectAt"])
        with self.assertRaises(ValueError):                    # an excluded bone must be a leaf
            actor_skin.build_actor_mesh_nif(skel, [synthetic_part(skel)[0]], unit_scale=1 / 70, exclude=["ArmB|0"])


@unittest.skipUnless(os.path.exists(os.path.join(FO4_DATA, "Fallout4 - Animations.ba2")), "Fallout 4 data not present")
class RealHandy(unittest.TestCase):
    def test_handy_skeleton_and_every_mesh_bone_maps(self):
        from fo4sf import ba2
        anim = ba2.Ba2(os.path.join(FO4_DATA, "Fallout4 - Animations.ba2"))
        sk = actor_skin.read_hka_skeleton(anim.read(anim.find(r"Meshes\Actors\Robot\CharacterAssets\skeleton.hkx")))
        self.assertEqual(len(sk.names), 112)
        self.assertEqual(sk.names[:2], ["Root", "COM"])
        self.assertAlmostEqual(sk.world()[1][0][2], 68.9113, places=3)
        meshes = ba2.Ba2(os.path.join(FO4_DATA, "Fallout4 - Meshes.ba2"))
        n = nifmod.parse(meshes.read(meshes.find(r"Meshes\Actors\Robot\CharacterAssets\MrHandy.nif")))
        bones = set()
        for s in nifmod.fo4_trishapes(n):
            bones |= {b.decode() for b in fo4skin.read_skin(n, s.block).bone_names}
        self.assertEqual(len(bones), 55)
        mapped = {b: actor_skin.handy_mesh_bone_to_hkx(b) for b in bones}
        self.assertEqual([b for b, h in mapped.items() if h not in sk.names], [])
        self.assertEqual(len(set(mapped.values())), 55)        # no two mesh bones share a skeleton bone


if __name__ == "__main__":
    unittest.main()
