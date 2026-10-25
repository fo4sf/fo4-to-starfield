"""Synthetic tests for fo4sf dds-summary CLI."""
import io
import struct
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

from fo4sf.__main__ import main


def _make_minimal_dds(width=4, height=4, fourcc=b"DXT1"):
    # Minimal valid DDS header that read_dds_header accepts
    header = bytearray(128)
    header[0:4] = b"DDS "
    struct.pack_into("<I", header, 12, height)
    struct.pack_into("<I", header, 16, width)
    struct.pack_into("<I", header, 28, 1)  # mips
    header[84:88] = fourcc
    return bytes(header)


class DdsSummaryTests(unittest.TestCase):
    def test_summary_text(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "test.dds"
            p.write_bytes(_make_minimal_dds(8, 8, b"BC5U"))
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = main(["dds-summary", str(p)])
            self.assertEqual(rc, 0)
            out = buf.getvalue()
            self.assertIn("8x8", out)
            self.assertIn("BC5U", out)

    def test_missing_file(self):
        buf_err = io.StringIO()
        with redirect_stderr(buf_err):
            rc = main(["dds-summary", "no-such-file.dds"])
        self.assertEqual(rc, 1)
        self.assertIn("missing:", buf_err.getvalue())


if __name__ == "__main__":
    unittest.main()
