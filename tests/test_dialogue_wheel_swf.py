"""scripts/ui/make_dialogue_wheel_swf.py (FAL-865): four named slots, no code, no game movie. Temp files only."""
import os
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "ui"))
import make_dialogue_wheel_swf as wheel  # noqa: E402
import make_probe_swf as swf  # noqa: E402

SCRIPT = os.path.join(ROOT, "scripts", "ui", "make_dialogue_wheel_swf.py")
NO_CODE = {72, 82, 76, 12, 59}  # DoABC, DoABC2, SymbolClass, DoAction, DoInitAction


def texts(movie):
    out = []
    for t in movie["tags"]:
        if t.get("text"):
            out.append(t["text"])
        for inner in t.get("tags") or []:
            if inner.get("text"):
                out.append(inner["text"])
    return out


class WheelMovieTest(unittest.TestCase):
    def test_compressed_header_version_12(self):
        data = wheel.movie_bytes()
        self.assertEqual(data[:3], b"CWS")
        self.assertEqual(data[3], 12)
        body = zlib.decompress(data[8:])
        self.assertEqual(struct.unpack_from("<I", data, 4)[0], 8 + len(body))

    def test_deterministic(self):
        self.assertEqual(wheel.movie_bytes(), wheel.movie_bytes())

    def test_four_named_slots(self):
        movie = swf.read_movie(wheel.movie_bytes())
        self.assertEqual(wheel.named_places(movie), list(wheel.SLOT_NAMES))
        self.assertEqual(list(wheel.SLOT_NAMES), ["fo4sfOptN", "fo4sfOptE", "fo4sfOptS", "fo4sfOptW"])

    def test_placeholders_not_fallout_lines(self):
        movie = swf.read_movie(wheel.movie_bytes())
        self.assertEqual(texts(movie), list(wheel.PLACEHOLDERS))

    def test_no_background_and_no_code(self):
        movie = swf.read_movie(wheel.movie_bytes())
        codes = {t["code"] for t in movie["tags"]}
        self.assertNotIn(9, codes)
        self.assertFalse(codes & NO_CODE)

    def test_as3_flag_without_code(self):
        movie = swf.read_movie(wheel.movie_bytes())
        attrs = next(t for t in movie["tags"] if t["code"] == 69)
        self.assertTrue(attrs["actionscript3"])

    def test_write_then_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "DialogueMenu.swf")
            wheel.write_movie(path)
            movie = swf.read_movie(path)
            self.assertEqual(wheel.named_places(movie), list(wheel.SLOT_NAMES))

    def test_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "w.swf")
            r = subprocess.run([sys.executable, SCRIPT, "--out", path], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(os.path.isfile(path))


if __name__ == "__main__":
    unittest.main()
