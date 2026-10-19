"""dotnet/MergeProbe on the synthetic master (dotnet/TerrainIdentityFixture with the map-marker template: its
LC172World stand-in 02DF8C has a persistent cell holding REFR 3E5E12), never a game: one persistent XMarker in an
override of the vanilla world's persistent cell, nothing else (docs/terrain/map-markers.md "Markers in the merged
world")."""
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


class MergeProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dotnet = shutil.which("dotnet")
        if not cls.dotnet:
            raise unittest.SkipTest(".NET SDK needed for the actual tool test")
        fixture = build(cls.dotnet, "TerrainIdentityFixture")
        cls.tool = build(cls.dotnet, "MergeProbe")
        temporary = tempfile.TemporaryDirectory(prefix="fo4sf-mergeprobe-")
        cls.addClassCleanup(temporary.cleanup)
        cls.root = Path(temporary.name)
        cls.master = cls.root / "master/Starfield.esm"
        subprocess.run([cls.dotnet, str(fixture), str(cls.master), "map-marker"], capture_output=True, check=True)
        cls.plain = cls.root / "plain/Starfield.esm"
        subprocess.run([cls.dotnet, str(fixture), str(cls.plain)], capture_output=True, check=True)

    def run_tool(self, *argv):
        return subprocess.run([self.dotnet, str(self.tool), *map(str, argv)], capture_output=True, text=True)

    def test_one_persistent_probe_in_the_vanilla_persistent_cell(self):
        out = self.root / "probe"
        proc = self.run_tool("build", self.master, out, "--ref", "3E5E12")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("(40.4, 57.2, 7.6)", proc.stdout)                   # 3E5E12 (37.4, 57.2, 7.6) + 3 m east
        plugin = out / "FO4SFMergeProbe.esm"
        check = self.run_tool("check", plugin, self.master, "--ref", "3E5E12")
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        recs = tri.records(plugin)
        self.assertEqual(sorted(sig for sig, *_ in recs.values()), [b"CELL", b"REFR", b"WRLD"])
        sig, payload, owner, flags = recs[0x800]
        self.assertEqual(sig, b"REFR")
        self.assertEqual(flags & 0xC00, 0x400)
        self.assertEqual(struct.unpack("<I", tlw.field(payload, b"NAME"))[0], 0x3B)  # XMarker of master index 0
        self.assertEqual(recs[0x02DF8C][0], b"WRLD")                       # the override keeps the vanilla FormKey
        self.assertEqual(recs[0x3807C7][0], b"CELL")                       # the vanilla persistent cell, overridden

    def test_check_refuses_another_offset(self):
        out = self.root / "probe-offset"
        self.assertEqual(self.run_tool("build", self.master, out, "--ref", "3E5E12", "--offset", "5").returncode, 0)
        check = self.run_tool("check", out / "FO4SFMergeProbe.esm", self.master, "--ref", "3E5E12")
        self.assertEqual(check.returncode, 1, check.stdout)
        self.assertIn("FAIL  the probe is at (42.4, 57.2, 7.6)", check.stdout)

    def test_non_finite_offsets_are_refused_and_keep_the_output(self):
        out = self.root / "probe-finite"
        self.assertEqual(self.run_tool("build", self.master, out, "--ref", "3E5E12").returncode, 0)
        plugin = out / "FO4SFMergeProbe.esm"
        before = plugin.read_bytes()
        for bad in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(bad=bad):
                proc = self.run_tool("build", self.master, out, "--ref", "3E5E12", "--offset", bad)
                self.assertNotEqual(proc.returncode, 0, proc.stdout)
                self.assertIn("not a finite number", proc.stderr)
                self.assertEqual(plugin.read_bytes(), before)
                check = self.run_tool("check", plugin, self.master, "--ref", "3E5E12", "--offset", bad)
                self.assertNotEqual(check.returncode, 0, check.stdout)
        self.assertEqual(sorted(p.name for p in out.iterdir()), ["FO4SFMergeProbe.esm"])

    def test_check_refuses_a_non_finite_probe_position(self):
        out = self.root / "probe-nan"
        self.assertEqual(self.run_tool("build", self.master, out, "--ref", "3E5E12").returncode, 0)
        plugin = out / "FO4SFMergeProbe.esm"
        data = bytearray(plugin.read_bytes())
        at = data.index(struct.pack("<3f", 40.4, 57.2, 7.6))     # the probe's DATA position
        struct.pack_into("<f", data, at, float("nan"))
        plugin.write_bytes(bytes(data))
        check = self.run_tool("check", plugin, self.master, "--ref", "3E5E12")
        self.assertEqual(check.returncode, 1, check.stdout)
        self.assertIn("is not finite", check.stdout)

    def test_build_refuses_a_master_without_the_reference(self):
        proc = self.run_tool("build", self.plain, self.root / "none", "--ref", "3E5E12")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("has no persistent cell", proc.stderr + proc.stdout)


if __name__ == "__main__":
    unittest.main()
