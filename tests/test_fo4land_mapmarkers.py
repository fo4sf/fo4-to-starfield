"""dotnet/Fo4Land export-mapmarkers on a synthetic Fallout 4 plugin written here byte by byte: one worldspace with a
persistent cell (two map markers and a plain reference) and one exterior cell (a temporary map marker), plus a second
worldspace whose marker must not be listed. No game file is read."""
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def sub(sig, data):
    return sig + struct.pack("<H", len(data)) + data


def record(sig, fid, subs, flags=0):
    payload = b"".join(sub(s, d) for s, d in subs)
    return struct.pack("<4sIIIIHH", sig, len(payload), flags, fid, 0, 131, 0) + payload


def group(label, records, gtype=0):
    body = b"".join(records)
    return struct.pack("<4sI4siHHHH", b"GRUP", 24 + len(body), label, gtype, 0, 0, 0, 0) + body


def fid_label(fid):
    return struct.pack("<I", fid)


def z(text):
    return text.encode("cp1252") + b"\0"


def marker(fid, name, pos, flags=0x400, edid=None):
    subs = ([(b"EDID", z(edid))] if edid else []) + [
        (b"NAME", struct.pack("<I", 0x10)), (b"XMRK", b""), (b"FNAM", b"\x03"), (b"FULL", z(name)),
        (b"TNAM", b"\x05\x00"), (b"DATA", struct.pack("<6f", *pos, 0, 0, 0))]
    return record(b"REFR", fid, subs, flags)


def world(fid, edid, persistent_cell, persistent, exterior):
    """WRLD + its children: the persistent cell's persistent group, then one block / sub-block / exterior cell."""
    cell_fid, ext_fid = persistent_cell, persistent_cell + 1
    ext_cell = record(b"CELL", ext_fid, [(b"XCLC", struct.pack("<iiI", -20, 21, 0))])
    children = (record(b"CELL", cell_fid, [], flags=0x400)
                + group(fid_label(cell_fid), [group(fid_label(cell_fid), persistent, 8)], 6)
                + group(struct.pack("<hh", 21, -20), [group(struct.pack("<hh", 21, -20), [
                    ext_cell, group(fid_label(ext_fid), [group(fid_label(ext_fid), exterior, 9)], 6)], 5)], 4))
    return [record(b"WRLD", fid, [(b"EDID", z(edid))]), group(fid_label(fid), [children], 1)]


def synthetic_plugin(path):
    tes4 = record(b"TES4", 0, [(b"HEDR", struct.pack("<fiI", 1.0, 9, 0x900)), (b"CNAM", z("fo4sf test"))], flags=0x1)
    plain = record(b"REFR", 0x812, [(b"NAME", struct.pack("<I", 0x10)), (b"DATA", struct.pack("<6f", 1, 2, 3, 0, 0, 0))],
                   flags=0x400)
    cw = world(0x800, "Commonwealth", 0x801, [
        marker(0x811, "Sanctuary Hills", (-80768.19, 88174.80, 2800.0), edid="SynthSanctuaryMarker"),
        marker(0x810, "Concord", (-60286.01, 72977.79, 1500.0)), plain],
        [marker(0x813, "Abernathy Farm", (-81000.0, 86000.0, 1200.0), flags=0)])
    other = world(0x820, "DiamondCityWorld", 0x821, [marker(0x830, "Diamond City", (0, 0, 0))], [])
    Path(path).write_bytes(tes4 + group(b"WRLD", cw + other))


class Fo4LandMapMarkersTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dotnet = shutil.which("dotnet")
        if not cls.dotnet:
            raise unittest.SkipTest(".NET SDK needed for the Fo4Land test")
        build = subprocess.run([cls.dotnet, "build", str(ROOT / "dotnet/Fo4Land"), "-c", "Release", "--nologo"],
                               capture_output=True, text=True)
        if build.returncode:
            raise AssertionError(build.stdout + build.stderr)
        cls.tool = ROOT / "dotnet/Fo4Land/bin/Release/net9.0/Fo4Land.dll"

    def run_tool(self, *args):
        return subprocess.run([self.dotnet, str(self.tool), *args], capture_output=True, text=True)

    def test_every_marker_of_the_world_in_formid_order(self):
        with tempfile.TemporaryDirectory() as d:
            plugin, out = os.path.join(d, "Synthetic.esm"), os.path.join(d, "markers.json")
            synthetic_plugin(plugin)
            proc = self.run_tool(plugin, "export-mapmarkers", out)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("3 map markers in Commonwealth, 3 with a name", proc.stdout)
            doc = json.loads(Path(out).read_text(encoding="utf-8"))
            self.assertEqual((doc["plugin"], doc["world"]), ("Synthetic.esm", "Commonwealth"))
            rows = doc["markers"]
            self.assertEqual([r["fid"] for r in rows], ["00000810", "00000811", "00000813"])
            self.assertEqual([r["name"] for r in rows], ["Concord", "Sanctuary Hills", "Abernathy Farm"])
            self.assertEqual([r["persistent"] for r in rows], [True, True, False])
            self.assertEqual(rows[1]["editor_id"], "SynthSanctuaryMarker")
            self.assertEqual(rows[1]["base"], "00000010")
            self.assertAlmostEqual(rows[1]["pos"][0], -80768.19, places=1)
            self.assertAlmostEqual(rows[1]["pos"][1], 88174.80, places=1)

    def test_another_world_and_a_missing_world(self):
        with tempfile.TemporaryDirectory() as d:
            plugin, out = os.path.join(d, "Synthetic.esm"), os.path.join(d, "markers.json")
            synthetic_plugin(plugin)
            proc = self.run_tool(plugin, "export-mapmarkers", out, "DiamondCityWorld")
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertEqual([r["name"] for r in json.loads(Path(out).read_text())["markers"]], ["Diamond City"])
            missing = self.run_tool(plugin, "export-mapmarkers", out, "FarHarbor")
            self.assertEqual(missing.returncode, 1)
            self.assertIn("FarHarbor not found", missing.stderr)
            self.assertEqual(self.run_tool(plugin, "export-mapmarkers").returncode, 2)


if __name__ == "__main__":
    unittest.main()
