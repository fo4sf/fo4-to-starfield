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


if __name__ == "__main__":
    unittest.main()
