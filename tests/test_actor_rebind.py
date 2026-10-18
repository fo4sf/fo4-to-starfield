"""Template rebind: a synthetic FO4 skinned shape onto a synthetic Starfield skinned template."""
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from fo4sf import actor_rebind, fo4skin, nif, sfmesh, sfnif  # noqa: E402
from test_fo4skin import skinned_nif  # noqa: E402

IDENT = struct.pack("<3f9ff", 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 1.0)


def sf_node(f, name, children, trans=(0, 0, 0)):
    return (struct.pack("<iIiI", f.string_index(name), 0, -1, 0xE) + struct.pack("<3f9ff", *trans, 1, 0, 0, 0, 1, 0, 0, 0, 1, 1.0)
            + struct.pack("<iI", -1, len(children)) + struct.pack(f"<{len(children)}i", *children))


def bone_entry(trans):
    return struct.pack("<4f", 0, 0, 0, 0.1) + struct.pack("<9f", 1, 0, 0, 0, 1, 0, 0, 0, 1) + struct.pack("<3f", *trans) + struct.pack("<f", 1.0)


def template(decal_under_bone=False):
    """0 root(children 1, 8), 1 skinned body, 2 instance, 3 bone data, 4 shader, 5 MaterialID, 6 C_Chassis, 7 C_Arm1,
    8 decal geometry (unskinned)."""
    f = nif.NifFile(endian=1, user_version=12, bs_version=173, author=b"\x00", export_script=b"\x00", sf_data=b"\x7a\x00")
    f.add_block("NiNode", sf_node(f, b"Root", [1, 6] if decal_under_bone else [1, 8, 6]))
    body = sfnif.BSGeometry(name_idx=f.string_index(b"MiniBot:0"), extra_refs=[5], skin=2, shader=4,
                            meshes=[sfnif.MeshRef(3, 3, 0x40, b"aa\\bb"), sfnif.MeshRef(3, 3, 0x40, b"aa\\cc"), None, None])
    f.add_block("BSGeometry", sfnif.build_bsgeometry(body))
    f.add_block("BSSkin::Instance", struct.pack("<iiI2i", 0, 3, 2, 6, 7) + struct.pack("<I", 0))
    f.add_block("BSSkin::BoneData", struct.pack("<I", 2) + bone_entry((0, 0, -0.1)) + bone_entry((0, 0, -0.3)))
    f.add_block("BSLightingShaderProperty", struct.pack("<iIi", f.string_index(b"materials\\minibot.mat"), 0, -1))
    f.add_block("NiIntegerExtraData", struct.pack("<iI", f.string_index(b"MaterialID"), 1234))
    f.add_block("NiNode", sf_node(f, b"C_Chassis", [7, 8] if decal_under_bone else [7], trans=(0, 0, 0.1)))
    f.add_block("NiNode", sf_node(f, b"C_Arm1", [], trans=(0, 0, 0.2)))
    f.add_block("BSGeometry", sfnif.build_bsgeometry(sfnif.BSGeometry(name_idx=f.string_index(b"Decal:0"), shader=4,
                meshes=[sfnif.MeshRef(3, 3, 0x40, b"aa\\dd"), None, None, None])))
    f.footer = struct.pack("<II", 1, 0)
    return nif.serialize(f)


BONES = {"BoneA": "C_Chassis", "BoneB": "C_Arm1"}


class RebindTest(unittest.TestCase):
    def run_rebind(self, materials=None):
        return actor_rebind.rebind(template(), nif.serialize(skinned_nif()), lambda b: BONES.get(b, "C_Chassis"),
                                   materials=materials)

    def test_one_group_replaces_the_template_geometry(self):
        res = self.run_rebind()
        n = nif.parse(res.nif)
        self.assertEqual(len(n.blocks), 9)
        self.assertEqual(actor_rebind._raw_children(n, 0), [1, 6])              # decal detached, body kept first
        g = sfnif.parse_bsgeometry(n.blocks[1])
        self.assertIsNone(g.meshes[1])                                           # template LODs dropped
        (d, f), mesh_bytes = next(iter(res.meshes.items()))
        self.assertEqual(g.meshes[0].path, f"{d}\\{f}".encode())
        m = sfmesh.parse(mesh_bytes)
        self.assertEqual(m.weights_per_vertex, 1)
        # vertex 0 heaviest BoneA, vertex 1 BoneB, vertex 2 a tie -> first slot (BoneA)
        self.assertEqual(m.weights, [(0, 65535), (1, 65535), (0, 65535)])
        self.assertEqual(g.meshes[0].num_verts, 3)
        self.assertEqual(res.report["bound"], {"BoneA->C_Chassis": 2, "BoneB->C_Arm1": 1})
        self.assertEqual(res.report["detached"], ["Decal:0"])
        # positions are the FO4 node pose in metres (fixture bones sit at their bind pose)
        pts = [sfmesh.decode_position(p, m.scale) for p in m.positions]
        self.assertAlmostEqual(pts[1][2], 25.0 / 70.0, places=3)
        # the bone-space sphere of C_Arm1 now holds vertex 1
        _, xfs = fo4skin.read_bone_data(n.blocks[3])
        sphere = struct.unpack_from("<4f", n.blocks[3], 4 + 68)
        self.assertAlmostEqual(sphere[2], 25.0 / 70.0 - 0.3, places=3)

    def test_material_groups_copy_the_skin_blocks(self):
        res = self.run_rebind(materials={"Body": "materials\\fo4port\\actors\\codsworth\\body.mat"})
        n = nif.parse(res.nif)
        shader_name = n.strings[struct.unpack_from("<i", n.blocks[4], 0)[0]]
        self.assertEqual(shader_name, b"materials\\fo4port\\actors\\codsworth\\body.mat")
        self.assertEqual(struct.unpack_from("<I", n.blocks[5], 4)[0],
                         sfnif.material_id("materials\\fo4port\\actors\\codsworth\\body.mat"))

    def test_two_groups(self):
        src = skinned_nif()
        arms = bytearray(src.blocks[3])
        struct.pack_into("<i", arms, 0, src.string_index(b"Arms"))
        k = src.add_block("BSTriShape", bytes(arms))
        actor_rebind._set_children(src, 0, actor_rebind._raw_children(src, 0) + [k])
        res = actor_rebind.rebind(template(), nif.serialize(src), lambda b: BONES.get(b, "C_Chassis"),
                                  materials={"Body": "materials\\a.mat", "Arms": "materials\\b.mat"})
        n = nif.parse(res.nif)
        self.assertEqual(len(n.blocks), 9 + 5)                                   # geometry, shader, instance, bone data, MaterialID
        self.assertEqual(actor_rebind._raw_children(n, 0), [1, 6, 9])
        g = sfnif.parse_bsgeometry(n.blocks[9])
        self.assertEqual((g.shader, g.skin, g.extra_refs), (10, 11, [13]))
        self.assertEqual(actor_rebind.read_instance(n.blocks[11])[1], 12)        # copy points at its own bone data
        self.assertEqual(actor_rebind.read_instance(n.blocks[2])[1], 3)
        self.assertEqual(struct.unpack_from("<I", n.blocks[13], 4)[0], sfnif.material_id("materials\\b.mat"))
        self.assertEqual(n.strings[struct.unpack_from("<i", n.blocks[10], 0)[0]], b"materials\\b.mat")
        self.assertEqual(len(res.meshes), 1)                                     # identical geometry, same hashed file
        self.assertEqual(sorted(res.report["groups"]), ["materials\\a.mat", "materials\\b.mat"])

    def test_template_geometry_under_a_bone_is_detached(self):
        res = actor_rebind.rebind(template(decal_under_bone=True), nif.serialize(skinned_nif()),
                                  lambda b: BONES.get(b, "C_Chassis"))
        n = nif.parse(res.nif)
        self.assertEqual(res.report["detached"], ["Decal:0"])
        reachable, todo = set(), [0]
        while todo:
            i = todo.pop()
            reachable.add(i)
            if n.type_of(i).endswith("Node"):
                todo += actor_rebind._raw_children(n, i)
        emitted = {f"{d}\\{f}".encode() for d, f in res.meshes}
        for i in reachable:
            if n.type_of(i) == "BSGeometry":
                self.assertTrue({m.path for m in sfnif.parse_bsgeometry(n.blocks[i]).meshes if m} <= emitted)
        self.assertNotIn(8, reachable)

    def test_unknown_bone_is_refused(self):
        with self.assertRaises(nif.NifError):
            actor_rebind.rebind(template(), nif.serialize(skinned_nif()), lambda b: "C_Nope")


class CodsworthBoneMapTest(unittest.TestCase):
    def test_map(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("convert_codsworth", ROOT / "scripts/actors/convert_codsworth.py")
        cc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cc)
        still, arms = cc.bone_map(False), cc.bone_map(True)
        self.assertEqual([still(b) for b in ("Pelvis", "Chest", "LArm_3", None)], ["C_Base", "C_Chassis", "C_Chassis", "C_Chassis"])
        self.assertEqual([arms(b) for b in ("LArm_3", "MArm_Palm_Bone1", "RArm_1", "HEAD")],
                         ["C_Arm1", "C_Arm2", "C_Arm3", "C_Chassis"])


class CodsworthPublishTest(unittest.TestCase):
    """convert_codsworth.main publishes a complete stage or nothing (synthetic sources, stubbed converter)."""
    def setUp(self):
        import importlib.util
        import tempfile
        spec = importlib.util.spec_from_file_location("convert_codsworth", ROOT / "scripts/actors/convert_codsworth.py")
        self.cc = cc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cc)
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        fo4 = nif.serialize(skinned_nif())

        class Src:
            def __init__(self, _d):
                pass

            def mesh(self, _n):
                return fo4

        class Conv:
            neutral = "materials\\fo4port\\_neutral.mat"

            def __init__(self, _src, staging, *_a):
                self.staging = staging

            def _shape_material(self, _n, _s):
                p = Path(self.staging, "materials", "body.mat")
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text("new")
                return "materials\\body.mat"

        from unittest import mock
        for target, name, value in ((cc.pipeline, "Fo4Archives", Src), (cc.pipeline, "Converter", Conv),
                                    (cc, "read_starfield", lambda _d, _n: template())):
            patcher = mock.patch.object(target, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.args = ["--fo4-data", "x", "--sf-data", "x", "--content-resources", "x", "--texconv", "x"]

    def tearDown(self):
        self.tmp.cleanup()

    def test_success_publishes_and_removes_partial(self):
        stage = self.root / "stage"
        self.assertEqual(self.cc.main(self.args + ["--staging", str(stage)]), 0)
        self.assertTrue((stage / "meshes/fo4port/actors/codsworth/codsworth.nif").exists())
        self.assertEqual((stage / "materials/body.mat").read_text(), "new")
        self.assertTrue((stage / "codsworth_report.json").exists())
        self.assertFalse(Path(str(stage) + ".partial").exists())

    def test_existing_stage_is_refused_untouched(self):
        stage = self.root / "stage"
        (stage / "materials").mkdir(parents=True)
        (stage / "materials/body.mat").write_text("old")
        with self.assertRaises(SystemExit):
            self.cc.main(self.args + ["--staging", str(stage)])
        self.assertEqual((stage / "materials/body.mat").read_text(), "old")

    def test_failure_publishes_nothing(self):
        stage = self.root / "stage"
        from unittest import mock
        with mock.patch.object(self.cc.actor_rebind, "rebind", side_effect=nif.NifError("injected")):
            with self.assertRaises(nif.NifError):
                self.cc.main(self.args + ["--staging", str(stage)])
        self.assertFalse(stage.exists())


if __name__ == "__main__":
    unittest.main()
