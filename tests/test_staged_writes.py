"""pipeline.write_staged replaces a staging file instead of writing through it. Staged cores hard-link their Data tree to
the conversion work folder, so an in-place write changed the rollback builds too (2026-10-21, red-rocket-crash-bisect.md)."""
import os
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from fo4sf import nif, pipeline, textures  # noqa: E402
from test_fo4skin import node_block, shape_block  # noqa: E402
from test_texture_cap import bc_dds  # noqa: E402


class WriteStaged(unittest.TestCase):
    def test_a_hard_linked_staged_copy_keeps_the_old_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = os.path.join(tmp, "work", "meshes", "door.nif")
            staged = os.path.join(tmp, "staged", "door.nif")
            pipeline.write_staged(work, b"v6e")
            os.makedirs(os.path.dirname(staged))
            try:
                os.link(work, staged)
            except OSError:
                self.skipTest("no hard links on this filesystem")
            pipeline.write_staged(work, b"v6h")
            with open(work, "rb") as f:
                self.assertEqual(f.read(), b"v6h")
            with open(staged, "rb") as f:
                self.assertEqual(f.read(), b"v6e")
            self.assertEqual(sorted(os.listdir(os.path.dirname(work))), ["door.nif"])   # no temporary left behind


class WriteStagedCallSites(unittest.TestCase):
    """Rebuild through actual callers, keeping links to every previous output.

    Texconv and vanilla material-template construction are stand-ins; NIF conversion,
    DDS/plane writers, material serialization and every staging publication remain real.
    These checks cover the seven write_staged call sites changed by #455. They do not
    establish that every possible conversion branch or installed build is safe.
    """

    def _assert_rebuild_keeps_links(self, writer):
        with tempfile.TemporaryDirectory() as tmp:
            work, prior = Path(tmp) / "work", Path(tmp) / "prior"
            writer(work)
            expected = {p.relative_to(work): p.read_bytes() for p in work.rglob("*") if p.is_file()}
            self.assertTrue(expected, "writer returned without publishing anything")
            old = {}
            for rel in expected:
                old[rel] = b"previous-build:" + rel.as_posix().encode()
                target, saved = work / rel, prior / rel
                target.write_bytes(old[rel])
                saved.parent.mkdir(parents=True, exist_ok=True)
                try:
                    os.link(target, saved)
                except OSError:
                    self.skipTest("no hard links on this filesystem")
                self.assertTrue(os.path.samefile(target, saved))
            writer(work)  # fresh Converter: exercise the publication, not a cache hit
            actual = {p.relative_to(work): p.read_bytes() for p in work.rglob("*") if p.is_file()}
            self.assertEqual(actual, expected)  # includes meshes, geometry, DDS planes and .mat files; no temp files
            for rel, data in old.items():
                with self.subTest(output=str(rel)):
                    self.assertEqual((prior / rel).read_bytes(), data)
                    self.assertFalse(os.path.samefile(work / rel, prior / rel))

    def converter(self, staging):
        c = pipeline.Converter.__new__(pipeline.Converter)
        c.staging, c.prefix, c.texconv = str(staging), "synthetic", "unused-texconv"
        c.no_collision, c.rig_doors, c.door_physics_donor = None, False, None
        c.collision_template = c.sf_mesh_template = c.dynamic_template = None
        c.neutral, c.template_mat = "materials\\synthetic\\neutral.mat", {}
        c.texture_caps, c.texture_log, c._materials, c.material_errors = {}, {}, {}, {}
        c.stats = {"assets": 0, "failed": 0, "materials_ok": 0, "materials_fallback": 0}
        c._glass_template = c._decal_template = c._two_sided_template = {}
        c._shape_material = lambda *_: c.neutral
        c.spec_mask_roughness = False
        return c

    def test_mesh_and_geometry_publish_through_real_convert_nif(self):
        source = nif.NifFile(bs_version=130)
        source.string_index(b"Root")
        source.string_index(b"Triangle")
        source.add_block("NiNode", node_block(0, [1]))
        source.add_block("BSTriShape", shape_block(1, [(0, 0, 0), (1, 0, 0), (0, 1, 0)]))
        source.footer = struct.pack("<II", 1, 0)
        raw = nif.serialize(source)

        def rebuild(staging):
            c = self.converter(staging)
            c.src = SimpleNamespace(mesh=lambda _: raw)
            result = c.convert_nif("meshes/synthetic/triangle.nif")
            self.assertTrue(result["ok"], result)
            self.assertTrue(any(staging.rglob("*.nif")))
            self.assertTrue(any(staging.rglob("*.mesh")))
        self._assert_rebuild_keeps_links(rebuild)

    def test_uncapped_texture_publication(self):
        self._texture_publication(capped=False)

    def test_capped_texture_publication(self):
        self._texture_publication(capped=True)

    def _texture_publication(self, capped):
        def rebuild(staging):
            c = self.converter(staging)
            c.texture_caps = {"color": 4} if capped else {}
            staging.mkdir(parents=True, exist_ok=True)
            src = staging.parent / "source.dds"
            src.write_bytes(bc_dds(8, 8))
            target = staging / "textures" / "synthetic.dds"
            c._publish_texture(str(src), str(target), "color")
            self.assertEqual(textures.read_dds_header(target.read_bytes())["width"], 4 if capped else 8)
        self._assert_rebuild_keeps_links(rebuild)

    def _material_rebuild(self, staging, kind):
        c = self.converter(staging)
        # Synthetic RGBA DDS; texconv is a no-op, not a real executable or archive read.
        source = staging.parent / "color.dds"
        source.parent.mkdir(parents=True, exist_ok=True)
        textures.write_dds_dx10(str(source), 4, 4, textures.DXGI_R8G8B8A8_UNORM, bytes([20, 40, 60, 128]) * 16, 4)
        c.src = SimpleNamespace(texture=lambda _: source.read_bytes())
        with patch.object(pipeline.textures, "texconv"), \
                patch.object(pipeline.cm, "build_mat", return_value={"synthetic": "opaque"}), \
                patch.object(pipeline.cm, "build_from_template", return_value={"synthetic": "transparent"}):
            if kind == "neutral":
                result = c._make_neutral_material()
            elif kind == "texture_set":
                result = c.texture_set_material("textures/color.dds", "textures/normal.dds", "")
            elif kind == "glass":
                result = c.glass_material("textures/color.dds", "")
            else:
                result = c.effect_decal_material("textures/color.dds", "")
        self.assertIsNotNone(result, c.material_errors)
        self.assertTrue(any(staging.rglob("*.mat")))
        self.assertTrue(any(staging.rglob("*.dds")))

    def test_neutral_texture_planes_and_material_publication(self):
        self._assert_rebuild_keeps_links(lambda p: self._material_rebuild(p, "neutral"))

    def test_texture_set_planes_and_material_publication(self):
        self._assert_rebuild_keeps_links(lambda p: self._material_rebuild(p, "texture_set"))

    def test_glass_planes_and_material_publication(self):
        self._assert_rebuild_keeps_links(lambda p: self._material_rebuild(p, "glass"))

    def test_effect_decal_planes_and_material_publication(self):
        self._assert_rebuild_keeps_links(lambda p: self._material_rebuild(p, "effect_decal"))


if __name__ == "__main__":
    unittest.main()
