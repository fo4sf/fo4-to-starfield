"""Skinned FO4 shapes are converted in the NIF's node pose (convert_static.pose_skinned_shapes). Synthetic NIFs only."""
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from test_fo4skin import skinned_nif, ROT_Z90, IDENT  # noqa: E402
from fo4sf import convert_static, nif, sfmesh  # noqa: E402


def mesh_points(files):
    data = next(v for k, v in files.items() if k.endswith(".mesh"))
    m = sfmesh.parse(data)
    return [tuple(round(c * 70.0, 3) for c in sfmesh.decode_position(p, m.scale)) for p in m.positions]


class SkinnedPoseTests(unittest.TestCase):
    def test_bone_turned_in_the_node_pose_moves_its_vertices(self):
        # BoneB is turned 90 degrees about z in the NIF's node pose (the bind pose is unturned): v1 follows BoneB
        n = skinned_nif(bone_b_rot=ROT_Z90)
        report = {}
        files = convert_static.convert_static(nif.serialize(n), "fo4port/test/posed", include_skinned=True, report=report)
        pts = mesh_points(files)
        self.assertEqual(pts[0], (1.0, 0.0, 5.0))                        # follows BoneA: unchanged
        self.assertEqual(pts[1], (0.0, 1.0, 25.0))                       # (1, 0, 5) in BoneB space, turned, + (0, 0, 20)
        self.assertEqual(report["skinned_posed"], 1)
        self.assertNotIn("skinned_kept_stored", report)

    def test_node_pose_equal_to_bind_pose_keeps_positions(self):
        n = skinned_nif()
        files = convert_static.convert_static(nif.serialize(n), "fo4port/test/same", include_skinned=True)
        self.assertEqual(mesh_points(files), [(1.0, 0.0, 5.0), (1.0, 0.0, 25.0), (0.0, 1.0, 15.0)])

    def test_animated_nif_is_posed_and_flagged(self):
        n = skinned_nif(bone_b_rot=ROT_Z90)
        f = nif.NifFile(bs_version=130, author=b"t\x00", process_script=b"\x00", export_script=b"\x00", max_filepath=b"\x00")
        f.strings = list(n.strings)
        for i in range(len(n.blocks)):
            f.add_block(n.type_of(i), n.blocks[i])
        f.add_block("NiControllerSequence", bytes(64))                   # an animated model: node pose is its rest pose
        f.footer = struct.pack("<II", 1, 0)
        report = {}
        files = convert_static.convert_static(nif.serialize(f), "fo4port/test/anim", include_skinned=True, report=report)
        self.assertEqual(mesh_points(files)[1], (0.0, 1.0, 25.0))
        self.assertEqual(report["skinned_posed"], 1)
        self.assertEqual(report["skinned_posed_animated"], 1)
        self.assertNotIn("skinned_kept_stored", report)

    def test_unreadable_skin_keeps_stored_positions(self):
        n = skinned_nif(bone_b_rot=ROT_Z90, instance=struct.pack("<iiI", 0, 5, 9) + bytes(36))   # 9 bones declared, 2 exist
        report = {}
        files = convert_static.convert_static(nif.serialize(n), "fo4port/test/bad", include_skinned=True, report=report)
        self.assertEqual(mesh_points(files)[1], (1.0, 0.0, 25.0))
        self.assertEqual(report["skinned_kept_stored"], 1)
        self.assertNotIn("skinned_posed", report)

    def test_unskinned_shapes_are_untouched(self):
        n = skinned_nif()
        shapes = nif.fo4_trishapes(n)
        plain = [s for s in shapes]
        for s in plain:
            s_static = convert_static.replace(s, skinned=False)
            out = convert_static.pose_skinned_shapes(n, [s_static], {})
            self.assertIs(out[0], s_static)


if __name__ == "__main__":
    unittest.main()
