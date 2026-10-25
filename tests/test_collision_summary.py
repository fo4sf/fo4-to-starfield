"""Synthetic tests for the collision-summary CLI (offline NIF diagnostics)."""
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fo4sf import nif  # noqa: E402
from fo4sf.__main__ import main  # noqa: E402


def minimal_nif(with_collision: bool = False) -> bytes:
    f = nif.NifFile(bs_version=130)
    f.add_block("NiNode", b"\x00" * 16)
    if with_collision:
        f.add_block("bhkPhysicsSystem", b"\x00" * 32)
    return nif.serialize(f)


class TestCollisionSummary(unittest.TestCase):
    def test_valid_with_collision(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "test.nif"
            p.write_bytes(minimal_nif(True))
            buf = io.StringIO()
            err = io.StringIO()
            with redirect_stdout(buf), redirect_stderr(err):
                rc = main(["collision-summary", str(p)])
            self.assertEqual(rc, 0)
            out = buf.getvalue()
            self.assertIn("bhkPhysicsSystem: 1", out)
            self.assertIn("BS version: 130", out)

    def test_valid_without_collision(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "plain.nif"
            p.write_bytes(minimal_nif(False))
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = main(["collision-summary", str(p)])
            self.assertEqual(rc, 0)
            self.assertIn("collision-related blocks: none detected", buf.getvalue())

    def test_missing_file(self):
        buf = io.StringIO()
        err = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(err):
            rc = main(["collision-summary", "/nonexistent/missing.nif"])
        self.assertEqual(rc, 1)
        self.assertIn("file not found", err.getvalue())


if __name__ == "__main__":
    unittest.main()
