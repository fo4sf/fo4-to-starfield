"""File-local OFST/CLSZ experiment: synthetic bytes only, no game files or input."""
import os
from pathlib import Path
import struct
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "slice"))
import make_cave_core64c as mk


def sub(tag, data):
    return tag + struct.pack("<H", len(data)) + data


class EmptyWorldDataTests(unittest.TestCase):
    def setUp(self):
        self.fields = [sub(b"EDID", b"SyntheticWorld\0"), sub(b"NAM0", struct.pack("<2f", -100, -200)),
                       sub(b"NAM9", struct.pack("<2f", 100, 100)), sub(b"DATA", b"\x01")]
        self.master = ("WRLD", 0, b"".join(self.fields))
        self.empty = sub(b"OFST", bytes(48)) + sub(b"CLSZ", bytes(48))  # 3x4 entries

    def check(self, arrays=None, fields=None, flags=0):
        return mk.compare_empty_world_data(self.master, ("WRLD", flags,
            b"".join(self.fields if fields is None else fields) + (self.empty if arrays is None else arrays)))

    def test_rectangular_negative_bounds_and_persistent_cell_outside_table(self):
        self.assertEqual(self.check(), (True, "only OFST/CLSZ differ: 3x4 absent local cells, 48 zero bytes each"))

    def test_rejects_stale_pointer_and_size_independently(self):
        for tag in (b"OFST", b"CLSZ"):
            with self.subTest(tag=tag):
                broken = self.empty.replace(sub(tag, bytes(48)), sub(tag, struct.pack("<I", 256026) + bytes(44)))
                self.assertFalse(self.check(broken)[0])

    def test_requires_both_exact_lengths_and_unique_fields(self):
        for data in (b"", sub(b"OFST", bytes(48)), sub(b"OFST", bytes(44)) + sub(b"CLSZ", bytes(48)),
                     self.empty + sub(b"OFST", bytes(48)), self.empty + sub(b"CLSZ", bytes(48))):
            with self.subTest(data=data):
                self.assertFalse(self.check(data)[0])

    def test_rejects_unrelated_change_and_record_flags(self):
        self.assertFalse(self.check(fields=self.fields[:-1] + [sub(b"DATA", b"\x02")])[0])
        self.assertFalse(self.check(flags=0x400)[0])

    def test_rejects_invalid_bounds_even_when_master_matches(self):
        for low, high in (((100, 0), (-100, 100)), ((float("nan"), 0), (100, 100)),
                          ((0, 0), (float("inf"), 100)), ((0, 0), (150, 100)),
                          ((-100000000, -100000000), (100000000, 100000000))):
            with self.subTest(low=low, high=high):
                fields = [sub(b"NAM0", struct.pack("<2f", *low)), sub(b"NAM9", struct.pack("<2f", *high))]
                master = ("WRLD", 0, b"".join(fields))
                self.assertFalse(mk.compare_empty_world_data(master, ("WRLD", 0, master[2] + self.empty))[0])

    def test_extended_sizes_validate_payload_and_headers(self):
        ext = sub(b"XXXX", struct.pack("<I", 48)) + b"OFST\0\0" + bytes(48) + sub(b"CLSZ", bytes(48))
        self.assertTrue(self.check(ext)[0])
        for broken in (ext[:-1], self.empty + b"ED", sub(b"XXXX", struct.pack("<I", 48)),
                       sub(b"XXXX", b"\x00"), sub(b"XXXX", struct.pack("<I", 48)) * 2 + ext):
            with self.subTest(data=broken):
                self.assertFalse(self.check(broken)[0])

    def test_cli_refuses_probes_before_reading_or_creating_stage(self):
        with patch.object(mk.os, "makedirs", side_effect=AssertionError("must refuse before writes")):
            with self.assertRaisesRegex(ValueError, "requires --no-probes"):
                mk.main(["stage", "--sf-esm", "synthetic", "--port", "synthetic", "--core", "synthetic",
                         "--out", "synthetic", "--fo4", "synthetic", "--empty-world-cell-data"])

    def test_cli_preserves_existing_candidate_directory(self):
        with patch.object(mk.os.path, "lexists", return_value=True), patch.object(mk.os, "makedirs",
                side_effect=AssertionError("must refuse before writes")):
            with self.assertRaisesRegex(ValueError, "new output directory"):
                mk.main(["stage", "--sf-esm", "synthetic", "--port", "synthetic", "--core", "synthetic",
                         "--out", "synthetic", "--fo4", "synthetic", "--empty-world-cell-data", "--no-probes"])


@unittest.skipUnless(os.environ.get("FO4SF_SLICEDOOR_DOTNET"), "opt in to synthetic SliceDoor .NET integration")
class WorldDataDotnetTests(unittest.TestCase):
    def test_build_check_and_corruption_controls(self):
        result = subprocess.run(["dotnet", "run", "--project", str(ROOT / "dotnet" / "SliceDoor.Tests"),
                                 "--configuration", "Release", "--verbosity", "quiet"],
                                capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("synthetic world-cell-data controls pass", result.stdout)


if __name__ == "__main__":
    unittest.main()
