"""BSMeshLODTriShape keeps every triangle group (synthetic fixture, no game data).

Owner playtest (Vault 111, NpcTableVaultSit02 = SetDressing\\Vault\\Vault_Table_02.nif): the table frames rendered but
not the tops. The FO4 shape is one BSMeshLODTriShape whose LOD sizes are (684, 0, 1018); the top is in the 684-triangle
LOD0 group and the converter kept only the largest group (1018 triangles of frame). The groups are disjoint parts of one
object, so a converted mesh needs all of them.
"""
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from fo4sf import convert_static, nif, sfmesh, sfnif  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_review_fixes import av_fields, trishape_block  # noqa: E402

IDENTITY = (1, 0, 0, 0, 1, 0, 0, 0, 1)


def table_parts():
    """A table in FO4 units: one top quad at z = 56 (LOD0 group) and two thin leg quads (LOD2 group)."""
    pts = [(-80, -70, 56), (80, -70, 56), (80, 70, 56), (-80, 70, 56)]               # top
    top = [(0, 1, 2), (0, 2, 3)]
    legs = []
    for x in (-75, 70):                                                               # two vertical leg panels
        b = len(pts)
        pts += [(x, -65, 0), (x + 5, -65, 0), (x + 5, -65, 53), (x, -65, 53)]
        legs += [(b, b + 1, b + 2), (b, b + 2, b + 3)]
    return pts, top, legs


def lod_table_nif():
    """root NiNode -> BSMeshLODTriShape whose triangles are [top..., legs...] with LOD sizes (2, 0, 4)."""
    pts, top, legs = table_parts()
    tris = top + legs
    f = nif.NifFile(bs_version=130, author=b"t\x00", process_script=b"\x00", export_script=b"\x00", max_filepath=b"\x00")
    f.string_index(b"Table:1 - L2_Table:1")
    f.add_block("NiNode", av_fields(0, (0, 0, 0), IDENTITY, 1.0) + struct.pack("<Ii", 1, 1))
    f.add_block("BSMeshLODTriShape", trishape_block(pts, tris) + struct.pack("<3I", len(top), 0, len(legs)))
    f.footer = struct.pack("<II", 1, 0)
    return nif.serialize(f), pts, top, legs


class LodTriShapeTests(unittest.TestCase):
    def test_reader_keeps_every_lod_group(self):
        raw, pts, top, legs = lod_table_nif()
        shapes = nif.fo4_trishapes(nif.parse(raw))
        self.assertEqual(len(shapes), 1)
        self.assertEqual(shapes[0].triangles, top + legs)        # was legs only: the largest group
        used = {v for t in shapes[0].triangles for v in t}
        self.assertEqual(used, set(range(len(pts))))            # no vertex left without a triangle

    def test_three_nonempty_groups_are_all_kept(self):
        pts, top, legs = table_parts()
        tris = top + legs
        f = nif.NifFile(bs_version=130, author=b"t\x00", process_script=b"\x00", export_script=b"\x00", max_filepath=b"\x00")
        f.string_index(b"Shape")
        f.add_block("BSMeshLODTriShape", trishape_block(pts, tris) + struct.pack("<3I", 2, 1, 3))
        f.footer = struct.pack("<II", 1, 0)
        self.assertEqual(nif.fo4_trishapes(nif.parse(nif.serialize(f)))[0].triangles, tris)

    def test_converted_mesh_has_the_table_top(self):
        raw, pts, top, legs = lod_table_nif()
        files = convert_static.convert_static(raw, "fo4port/test/table")
        meshes = [v for k, v in files.items() if k.endswith(".mesh")]
        self.assertEqual(len(meshes), 1)
        m = sfmesh.parse(meshes[0])
        self.assertEqual(len(m.triangles), len(top) + len(legs))
        z_top = 56 * convert_static.UNIT_SCALE
        decoded = [sfmesh.decode_position(p, m.scale) for p in m.positions]
        top_tris = [t for t in m.triangles if all(abs(decoded[v][2] - z_top) < 1e-3 for v in t)]
        self.assertEqual(len(top_tris), 2)
        geo = sfnif.parse_bsgeometry(nif.parse(files["meshes/fo4port/test/table.nif"]).blocks[2])
        self.assertEqual(geo.meshes[0].indices_size, 3 * (len(top) + len(legs)))


if __name__ == "__main__":
    unittest.main()
