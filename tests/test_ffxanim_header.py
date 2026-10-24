"""ffxanim_header: hex dump of entries from a synthetic General BA2."""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from ba2_fixture import general_archive  # noqa: E402

spec = importlib.util.spec_from_file_location("ffxanim_header", ROOT / "scripts/research/ffxanim_header.py")
fh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fh)


class FfxanimHeaderTest(unittest.TestCase):
    def test_dump(self):
        self.assertEqual(fh.hexdump(b"FACEz", 64), ["00000000  46 41 43 45 7a" + " " * 33 + "  FACEz"])
        with tempfile.TemporaryDirectory() as t:
            arc = os.path.join(t, "a.ba2")
            open(arc, "wb").write(general_archive({"sound/voice/x/a.ffxanim": b"FACE" + bytes(30), "b.txt": b"x"}))
            local = os.path.join(t, "run1.ffxanim")
            open(local, "wb").write(b"FACE")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                self.assertEqual(fh.main([arc, "--compare", local]), 0)
            out = buf.getvalue()
            self.assertIn("a.ffxanim: 34 bytes", out)
            self.assertIn("run1.ffxanim: 4 bytes", out)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                self.assertEqual(fh.main([arc, "--ext", ".txt"]), 0)
            self.assertIn("b.txt: 1 bytes", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
