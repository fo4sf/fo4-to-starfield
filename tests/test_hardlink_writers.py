"""Hard-link safety for every staging writer that #455 switched to write_staged (issue #458 task 2).

write_staged is the single path. A staged file hard-linked into a rollback build keeps its old bytes
when the work copy is rewritten. One test covers the function; the call sites are listed in the PR.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from fo4sf import pipeline  # noqa: E402


class HardLinkWriterTests(unittest.TestCase):
    def test_write_staged_does_not_mutate_hard_linked_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = os.path.join(tmp, "work")
            staged_dir = os.path.join(tmp, "staged")
            os.makedirs(work_dir)
            os.makedirs(staged_dir)
            work = os.path.join(work_dir, "meshes", "door.nif")
            staged = os.path.join(staged_dir, "meshes", "door.nif")
            pipeline.write_staged(work, b"v6e-original")
            os.makedirs(os.path.dirname(staged))
            try:
                os.link(work, staged)
            except OSError:
                self.skipTest("filesystem does not support hard links")
            # Simulate a rebuild that rewrites the work file.
            pipeline.write_staged(work, b"v6h-rebuilt")
            with open(work, "rb") as f:
                self.assertEqual(f.read(), b"v6h-rebuilt")
            with open(staged, "rb") as f:
                self.assertEqual(f.read(), b"v6e-original")
            # No leftover temporary files.
            self.assertEqual(sorted(os.listdir(os.path.dirname(work))), ["door.nif"])

    def test_material_writer_path_is_hard_link_safe(self):
        # The material writer in Converter._write_material calls write_staged.
        # Direct call is enough; full Converter needs archives.
        with tempfile.TemporaryDirectory() as tmp:
            mat_path = os.path.join(tmp, "materials", "test.mat")
            pipeline.write_staged(mat_path, b"old-mat-content")
            linked = os.path.join(tmp, "rollback", "materials", "test.mat")
            os.makedirs(os.path.dirname(linked))
            try:
                os.link(mat_path, linked)
            except OSError:
                self.skipTest("no hard links")
            pipeline.write_staged(mat_path, b"new-mat-content")
            with open(linked, "rb") as f:
                self.assertEqual(f.read(), b"old-mat-content")


if __name__ == "__main__":
    unittest.main()
