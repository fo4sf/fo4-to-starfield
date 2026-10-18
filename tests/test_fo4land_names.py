"""dotnet/Fo4Land export-names (the FO4 display names make_cluster.py --names reads) on a synthetic Fallout 4 plugin
written here byte by byte: four records, no game file is read."""
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


def group(label, records):
    body = b"".join(records)
    return struct.pack("<4sI4siHHHH", b"GRUP", 24 + len(body), label, 0, 0, 0, 0, 0) + body


def z(text):
    return text.encode("cp1252") + b"\0"


def synthetic_plugin(path):
    """TES4 (not localized: FULL is an inline string) + ACTI x2 (one without FULL), TERM, STAT (not a listed type)."""
    tes4 = record(b"TES4", 0, [(b"HEDR", struct.pack("<fiI", 1.0, 4, 0x804)), (b"CNAM", z("fo4sf test"))], flags=0x1)
    data = (tes4
            + group(b"STAT", [record(b"STAT", 0x803, [(b"EDID", z("SynthStatic"))])])
            + group(b"ACTI", [record(b"ACTI", 0x800, [(b"EDID", z("SynthBell")), (b"FULL", z("Bell"))]),
                              record(b"ACTI", 0x801, [(b"EDID", z("SynthTrigger"))])])
            + group(b"TERM", [record(b"TERM", 0x802, [(b"EDID", z("SynthTerminal")), (b"FULL", z("Zeke's Terminal"))])]))
    Path(path).write_bytes(data)


class Fo4LandNamesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dotnet = shutil.which("dotnet")
        if not cls.dotnet:
            raise unittest.SkipTest(".NET 9 SDK needed for the Fo4Land test")
        sdks = subprocess.run([cls.dotnet, "--list-sdks"], capture_output=True, text=True, check=True)
        if not any(line.startswith("9.") for line in sdks.stdout.splitlines()):
            raise unittest.SkipTest(".NET 9 SDK needed for the Fo4Land test")
        build = subprocess.run([cls.dotnet, "build", str(ROOT / "dotnet/Fo4Land"), "-c", "Release", "--nologo"],
                               capture_output=True, text=True)
        if build.returncode:
            raise AssertionError(build.stdout + build.stderr)
        cls.tool = ROOT / "dotnet/Fo4Land/bin/Release/net9.0/Fo4Land.dll"

    def test_names_of_the_listed_types_with_null_for_no_full(self):
        with tempfile.TemporaryDirectory() as d:
            plugin, out = os.path.join(d, "Synthetic.esm"), os.path.join(d, "names.json")
            synthetic_plugin(plugin)
            proc = subprocess.run([self.dotnet, str(self.tool), plugin, "export-names", out], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("3 base records", proc.stdout)
            with open(out, encoding="utf-8") as f:
                doc = json.load(f)
            self.assertEqual(doc["plugin"], "Synthetic.esm")
            self.assertEqual(doc["types"], ["Activator", "Terminal", "Container", "MiscItem", "Ingestible"])
            self.assertEqual(doc["names"], {
                "000800:Synthetic.esm": {"type": "Activator", "editor_id": "SynthBell", "name": "Bell"},
                "000801:Synthetic.esm": {"type": "Activator", "editor_id": "SynthTrigger", "name": None},
                "000802:Synthetic.esm": {"type": "Terminal", "editor_id": "SynthTerminal", "name": "Zeke's Terminal"}})
            self.assertEqual(list(doc["names"]), sorted(doc["names"]))                   # stable bytes per plugin
            bad = subprocess.run([self.dotnet, str(self.tool), plugin, "export-names"], capture_output=True, text=True)
            self.assertEqual(bad.returncode, 2)


if __name__ == "__main__":
    unittest.main()
