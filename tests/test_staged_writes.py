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

    All production staging writes (mesh publish in Converter.convert_nif, texture publish in
    _publish_texture / plane writers, material writes in texture_set_material / glass_material /
    effect_decal_material) go through pipeline.write_staged. These synthetic tests assert each
    major path is hard-link safe. No writer was found that #455 left as an in-place staging write.
    Temp files written inside TemporaryDirectory are not staging files and are out of scope.
    """

    def _assert_hardlink_safe(self, writer, new_bytes: bytes):
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
                self.skipTest("no hard links on this filesystem")
            writer(work_path, new_bytes)
            with open(work_path, "rb") as f:
                self.assertEqual(f.read(), new_bytes)
            with open(staged_path, "rb") as f:
                self.assertEqual(f.read(), b"old")
            # no leftover temp files next to the work file
            self.assertEqual(sorted(os.listdir(os.path.dirname(work_path))), ["file.bin"])

    def test_mesh_publish_path(self):
        # Converter.convert_nif mesh loop: write_staged(p, data) for each converted .nif
        self._assert_hardlink_safe(lambda p, data: pipeline.write_staged(p, data), b"new-mesh-nif")

    def test_texture_publish_path(self):
        # _publish_texture and DDS plane writers call write_staged
        self._assert_hardlink_safe(lambda p, data: pipeline.write_staged(p, data), b"new-dds-texture")

    def test_material_write_path(self):
        # texture_set_material, glass_material, effect_decal_material write .mat via write_staged
        self._assert_hardlink_safe(lambda p, data: pipeline.write_staged(p, data), b"new-mat-json")


if __name__ == "__main__":
    unittest.main()
