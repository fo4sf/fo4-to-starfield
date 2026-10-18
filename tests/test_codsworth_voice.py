"""Codsworth voice helpers: .fuz split, RIFF fmt probe and line choice on synthetic data."""
import importlib.util
from pathlib import Path
import struct
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("codsworth_voice", ROOT / "scripts/actors/codsworth_voice.py")
cv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cv)


def riff(form, tag, ch, rate):
    fmt = struct.pack("<HHIIHH", tag, ch, rate, rate * 2, 2, 16)
    body = form + b"fmt " + struct.pack("<I", len(fmt)) + fmt + b"data" + struct.pack("<I", 0)
    return b"RIFF" + struct.pack("<I", len(body)) + body


class VoiceTest(unittest.TestCase):
    def test_split_fuz(self):
        audio = riff(b"XWMA", 0x161, 1, 44100)
        lip, got = cv.split_fuz(b"FUZE" + struct.pack("<II", 1, 3) + b"lip" + audio)
        self.assertEqual((lip, got), (b"lip", audio))
        with self.assertRaises(ValueError):
            cv.split_fuz(b"RIFF....")

    def test_riff_fmt(self):
        f = cv.riff_fmt(riff(b"WAVE", 0xFFFF, 1, 48000))
        self.assertEqual((f["form"], f["codec_tag"], f["channels"], f["rate"]), ("WAVE", "0xffff", 1, 48000))
        self.assertIn("error", cv.riff_fmt(b"OggS"))

    def test_pick(self):
        rows = [{"info": "0001", "subtype": "IDAT", "text": "Longer line here"}, {"info": "0002", "subtype": "HELO", "text": "Sir!"},
                {"info": "0003", "subtype": "SCEN", "text": "Scene"}, {"info": "0004", "subtype": "HELO", "text": ""}]
        self.assertEqual([r["info"] for r in cv.pick(rows, 5, None)], ["0002", "0001"])
        self.assertEqual([r["info"] for r in cv.pick(rows, 5, ["0003"])], ["0003"])


if __name__ == "__main__":
    unittest.main()
