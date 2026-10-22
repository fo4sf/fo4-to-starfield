"""dotnet/BorderProbe on its own synthetic plugins (BorderProbe fixture: a Starfield.esm stand-in, a core whose world is
SmallWorld with HNAM 0 and a persistent cell, and a Mission plugin overriding that world), never a game: each variant
overrides only the world's WRLD record, copied from the last override, with only its DATA flags and HNAM changed,
and masters every given plugin (docs/terrain/border.md)."""
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
import test_terrain_reference_identity as tri  # noqa: E402
import test_terrain_lights_writer as tlw  # noqa: E402
from test_map_markers_plugin import build  # noqa: E402

SMALL_WORLD = 0x01


def masters(path):
    data = path.read_bytes()
    assert data[:4] == b"TES4"
    size = struct.unpack_from("<I", data, 4)[0]
    return [d.rstrip(b"\0").decode() for s, d in tri.subrecords(data[24:24 + size]) if s == b"MAST"]


class BorderProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dotnet = shutil.which("dotnet")
        if not cls.dotnet:
            raise unittest.SkipTest(".NET SDK needed for the actual tool test")
        cls.tool = build(cls.dotnet, "BorderProbe")
        temporary = tempfile.TemporaryDirectory(prefix="fo4sf-borderprobe-")
        cls.addClassCleanup(temporary.cleanup)
        cls.root = Path(temporary.name)
        cls.fx = cls.root / "fixture"
        proc = cls.run_tool("fixture", cls.fx)
        if proc.returncode:
            raise AssertionError(proc.stdout + proc.stderr)
        cls.plugins = [cls.fx / "FO4TerrainCore.esm", cls.fx / "FO4SFMission.esm"]

    @classmethod
    def run_tool(cls, *argv):
        return subprocess.run([cls.dotnet, str(cls.tool), *map(str, argv)], capture_output=True, text=True)

    def probe(self, variant):
        out = self.root / variant
        proc = self.run_tool("build", self.fx / "Starfield.esm", out, "--variant", variant, *self.plugins)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return out / f"FO4SFBorderProbe_{variant}.esm"

    def test_show_lists_the_world_in_every_plugin(self):
        proc = self.run_tool("show", self.fx / "Starfield.esm", *self.plugins)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        lines = proc.stdout.splitlines()
        self.assertEqual([ln.split(":")[0] for ln in lines], ["FO4TerrainCore.esm", "FO4SFMission.esm"])
        self.assertTrue(all("Flags SmallWorld" in ln and "HNAM [0]" in ln for ln in lines), lines)

    def test_each_variant_changes_only_its_fields_of_the_last_override(self):
        want = {"nosmall": (0, b"\x00"), "hnam5": (SMALL_WORLD, b"\x05"), "city": (0, b"\x05")}
        for variant, (flags, hnam) in want.items():
            with self.subTest(variant=variant):
                plugin = self.probe(variant)
                self.assertEqual(masters(plugin), ["Starfield.esm", "FO4TerrainCore.esm", "FO4SFMission.esm"])
                recs = tri.records(plugin)
                self.assertEqual(sorted(recs), [0x803])                  # the WRLD alone: no cell, no reference
                sig, payload, _owner, _flags = recs[0x803]
                self.assertEqual(sig, b"WRLD")
                self.assertEqual(tlw.field(payload, b"DATA")[0], flags)
                self.assertEqual(tlw.field(payload, b"HNAM"), hnam)
                self.assertIn(b"Mission", tlw.field(payload, b"FULL"))      # copied from the last override

    def test_an_unknown_variant_is_refused(self):
        proc = self.run_tool("build", self.fx / "Starfield.esm", self.root / "bad", "--variant", "huge", *self.plugins)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("want nosmall, hnam5 or city", proc.stderr)
        self.assertFalse((self.root / "bad").exists())


if __name__ == "__main__":
    unittest.main()
