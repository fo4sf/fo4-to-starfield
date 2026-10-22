"""Synthetic tests for scripts/game/value_scan.py: a 4-byte value found in plugin fields and in raw files.
No game data: the plugin is built byte by byte (TES4 header, one group, a plain and a compressed record)."""
import contextlib
import importlib.util
import io
import json
import os
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("value_scan", ROOT / "scripts" / "game" / "value_scan.py")
vs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vs)

V = struct.pack("<f", 0.02)


def field(sig, data):
    return sig + struct.pack("<H", len(data)) + data


def record(typ, fid, fields, compress=False):
    body = b"".join(fields)
    flags = 0
    if compress:
        body, flags = struct.pack("<I", len(body)) + zlib.compress(body), 0x40000
    return typ + struct.pack("<III", len(body), flags, fid) + b"\0" * 8 + body


def plugin():
    stat = record(b"STAT", 0x01000800, [field(b"EDID", b"FO4Core_Box\0"), field(b"DNAM", struct.pack("<ff", 1.0, 0.02))])
    other = record(b"STAT", 0x01000801, [field(b"EDID", b"FO4Core_Plain\0"), field(b"DNAM", struct.pack("<f", 1.0))])
    packed = record(b"REFR", 0x01000802, [field(b"EDID", b"FO4Core_Ref\0"), field(b"XSCL", V)], compress=True)
    group_body = stat + other + packed
    group = b"GRUP" + struct.pack("<I4si", 24 + len(group_body), b"STAT", 0) + b"\0" * 8 + group_body
    return record(b"TES4", 0, [field(b"HEDR", b"\0" * 12)]) + group


class ValueScan(unittest.TestCase):
    def test_plugin_hits_name_the_record_and_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "FO4TerrainCore.esm")
            with open(path, "wb") as f:
                f.write(plugin())
            hits = vs.plugin_hits(path, V)
        self.assertEqual([(h["type"], h["form_id"], h["edid"], h["field"], h["at"]) for h in hits],
                         [("STAT", "01000800", "FO4Core_Box", "DNAM", 4), ("REFR", "01000802", "FO4Core_Ref", "XSCL", 0)])

    def test_main_scans_folders_by_extension_and_writes_json_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "a.esm"), "wb") as f:
                f.write(plugin())
            os.makedirs(os.path.join(tmp, "geometries", "ab"))
            with open(os.path.join(tmp, "geometries", "ab", "x.mesh"), "wb") as f:
                f.write(b"\1\2" + V + b"\0" * 6 + V)
            with open(os.path.join(tmp, "notes.txt"), "wb") as f:
                f.write(V)
            out = os.path.join(tmp, "out.json")
            with contextlib.redirect_stdout(io.StringIO()) as text:
                self.assertEqual(vs.main([tmp, "--ext", "esm,.mesh", "--json", out]), 0)
            self.assertIn("x.mesh: 2 hit(s) at 2, 12", text.getvalue())
            self.assertIn("2 files scanned, 2 hold 0x3ca3d70a, 0 unreadable", text.getvalue())
            with open(out) as f:
                self.assertEqual(json.load(f)["value"], "0x3ca3d70a")
            with self.assertRaises(FileExistsError), contextlib.redirect_stdout(io.StringIO()):
                vs.main([tmp, "--json", out])

    def test_hex_pattern_and_an_unreadable_plugin(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = os.path.join(tmp, "bad.esm")
            with open(bad, "wb") as f:
                f.write(b"TES4" + b"\xff" * 30)
            with contextlib.redirect_stdout(io.StringIO()) as text:
                self.assertEqual(vs.main([bad, "--hex", "3ca3d70a"]), 1)
            self.assertIn("1 unreadable", text.getvalue())

    def test_a_record_cut_short_and_a_missing_folder_are_errors_not_empty_scans(self):
        # Codex on #459: a plugin cut inside a record, and a misspelled folder, used to scan "clean"
        with tempfile.TemporaryDirectory() as tmp:
            cut = os.path.join(tmp, "cut.esm")
            with open(cut, "wb") as f:
                f.write(plugin()[:-10])
            with self.assertRaises(ValueError):
                vs.plugin_hits(cut, V)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(vs.main([cut]), 1)
            with self.assertRaises(SystemExit) as stop, contextlib.redirect_stdout(io.StringIO()):
                vs.main([os.path.join(tmp, "no_such_folder")])
            self.assertIn("no such file or folder", str(stop.exception.code))


if __name__ == "__main__":
    unittest.main()
