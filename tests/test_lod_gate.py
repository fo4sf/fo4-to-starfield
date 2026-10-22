"""dotnet/LodGate on its own synthetic plugins (LodGate fixture: a Starfield.esm stand-in with LC172World and four
statics of known bounds, and a core with FO4Core_Commonwealth), never a game: the three tiny custom-world gate plugins
for the Creation Kit's -MockWorldSpaceLOD (docs/terrain/object-lod.md "What the runs showed")."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from test_border_probe import masters  # noqa: E402
from test_map_markers_plugin import build  # noqa: E402

CELLS = "[(-1,-1), (-1,0), (-1,1), (0,-1), (1,-1), (0,0), (0,1), (1,0), (1,1)]"


class LodGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dotnet = shutil.which("dotnet")
        if not cls.dotnet:
            raise unittest.SkipTest(".NET SDK needed for the actual tool test")
        cls.tool = build(cls.dotnet, "LodGate")
        temporary = tempfile.TemporaryDirectory(prefix="fo4sf-lodgate-")
        cls.addClassCleanup(temporary.cleanup)
        cls.root = Path(temporary.name)
        cls.fx = cls.root / "fixture"
        proc = cls.run_tool("fixture", cls.fx)
        if proc.returncode:
            raise AssertionError(proc.stdout + proc.stderr)
        cls.sf, cls.core = cls.fx / "Starfield.esm", cls.fx / "FO4TerrainCore.esm"
        cls.out = cls.root / "out"
        proc = cls.run_tool("build", cls.sf, cls.core, cls.out)
        if proc.returncode:
            raise AssertionError(proc.stdout + proc.stderr)
        cls.built = proc.stdout

    @classmethod
    def run_tool(cls, *argv):
        return subprocess.run([cls.dotnet, str(cls.tool), *map(str, argv)], capture_output=True, text=True)

    def show(self, name):
        proc = self.run_tool("show", self.out / name, self.sf, self.core)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return proc.stdout

    def test_build_picks_the_largest_vanilla_statics(self):
        # by object-bounds extent: StatBig1 (200), StatBig2 (160), StatBig3 (120); never StatSmall
        self.assertIn("statics (3 largest by object bounds): 001001:Starfield.esm StatBig1 (200), "
                      "001002:Starfield.esm StatBig2 (160), 001003:Starfield.esm StatBig3 (120)", self.built)

    def test_gate_1_copies_the_vanilla_template_world_into_a_master(self):
        shown = self.show("FO4SFLodGate1.esm")
        self.assertIn("FO4SFLodGate1.esm: header flags Master, masters [Starfield.esm]", shown)
        self.assertIn("  FO4SF_LodGate1 000800:FO4SFLodGate1.esm: Flags SmallWorld, HNAM [0], location 3807BE:Starfield.esm, "
                      f"components [], persistent cell 000801:FO4SFLodGate1.esm, 9 cell(s) at {CELLS}", shown)
        for i, base in enumerate(["001001", "001002", "001003"], 1):
            self.assertIn(f"FO4SF_LodGate1Stat{i} base {base}:Starfield.esm at ({i}, 1, 0)", shown)
        self.assertEqual(masters(self.out / "FO4SFLodGate1.esm"), ["Starfield.esm"])
        self.assertEqual((self.out / "FO4SFLodGate1.esm").read_bytes()[8:12], (1).to_bytes(4, "little"))   # Master

    def test_gate_2_is_the_same_world_without_the_master_flag(self):
        shown = self.show("FO4SFLodGate2.esm")                      # the .esm name kept: the flag is the only difference
        self.assertIn("FO4SFLodGate2.esm: header flags 0, masters [Starfield.esm]", shown)
        self.assertIn(f"FO4SF_LodGate2 000800:FO4SFLodGate2.esm: Flags SmallWorld, HNAM [0], location 3807BE:Starfield.esm, components [], "
                      f"persistent cell 000801:FO4SFLodGate2.esm, 9 cell(s) at {CELLS}", shown)
        self.assertEqual(shown.count("    ref "), 3)
        self.assertEqual((self.out / "FO4SFLodGate2.esm").read_bytes()[8:12], (0).to_bytes(4, "little"))
        self.assertFalse((self.out / "FO4SFLodGate2.esp").exists())

    def test_gate_3_copies_our_core_world_and_masters_the_core(self):
        shown = self.show("FO4SFLodGate3.esm")
        self.assertIn("FO4SFLodGate3.esm: header flags Master, masters [Starfield.esm, FO4TerrainCore.esm]", shown)
        self.assertIn("FO4SF_LodGate3 000800:FO4SFLodGate3.esm: Flags SmallWorld, HNAM [0], location 000801:FO4TerrainCore.esm, "
                      f"components [], persistent cell 000801:FO4SFLodGate3.esm, 9 cell(s) at {CELLS}", shown)
        self.assertEqual(shown.count("    ref "), 3)
        self.assertNotIn("SyntheticCore", shown)                    # the core's own cell tree and references stay behind
        self.assertNotIn(b"SyntheticCore", (self.out / "FO4SFLodGate3.esm").read_bytes())
        self.assertEqual(masters(self.out / "FO4SFLodGate3.esm"), ["Starfield.esm", "FO4TerrainCore.esm"])

    def test_build_refuses_inputs_without_the_worlds(self):
        proc = self.run_tool("build", self.core, self.core, self.root / "bad")      # the core has no LC172World
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("no worldspace LC172World", proc.stderr)
        proc = self.run_tool("build", self.sf, self.sf, self.root / "bad2")         # Starfield.esm has no world of ours
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("no worldspace FO4Core_Commonwealth of its own", proc.stderr)
        self.assertEqual(self.run_tool("build", self.sf, self.core, self.root / "bad3", "--statics", "0").returncode, 2)


if __name__ == "__main__":
    unittest.main()
