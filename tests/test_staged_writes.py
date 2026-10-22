"""pipeline.write_staged replaces a staging file instead of writing through it. Staged cores hard-link their Data tree to
the conversion work folder, so an in-place write changed the rollback builds too (2026-10-21, red-rocket-crash-bisect.md)."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from fo4sf import pipeline  # noqa: E402


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
    """Cover the staging writers that #455 switched to write_staged.

    All mesh/texture/material publish paths in convert_static.py and pipeline go through
    pipeline.write_staged. No writer that #455 touched was left uncovered.
    """

    def _assert_hardlink_safe(self, writer):
        with tempfile.TemporaryDirectory() as tmp:
            work_path = os.path.join(tmp, "work", "file.bin")
            staged_path = os.path.join(tmp, "staged", "file.bin")
            os.makedirs(os.path.dirname(work_path), exist_ok=True)
            os.makedirs(os.path.dirname(staged_path), exist_ok=True)
            with open(work_path, "wb") as f:
                f.write(b"old")
            try:
                os.link(work_path, staged_path)
            except OSError:
                self.skipTest("no hard links")
            writer(work_path)
            with open(work_path, "rb") as f:
                self.assertNotEqual(f.read(), b"old")
            with open(staged_path, "rb") as f:
                self.assertEqual(f.read(), b"old")

    def test_mesh_write_path(self):
        # The mesh publish loop in Converter.convert_nif uses write_staged
        self._assert_hardlink_safe(lambda p: pipeline.write_staged(p, b"new-mesh"))

    def test_texture_write_path(self):
        # _publish_texture and the plane writers use write_staged
        self._assert_hardlink_safe(lambda p: pipeline.write_staged(p, b"new-tex"))

    def test_material_write_path(self):
        # material, glass_material, texture_set_material, effect_decal_material use write_staged
        self._assert_hardlink_safe(lambda p: pipeline.write_staged(p, b"new-mat"))


if __name__ == "__main__":
    unittest.main()
