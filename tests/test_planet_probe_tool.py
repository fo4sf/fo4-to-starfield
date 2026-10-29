"""dotnet/PlanetProbe on the synthetic master (dotnet/TerrainIdentityFixture with its overlay ids: the three template
identities LC172World 02DF8C, OverlayBlockLC172World 102382 and LC172WorldLocation 3807BE under synthetic EditorIDs),
never a game: build, the tool's own Mutagen check, then the raw check of src/fo4sf/planet/probe.py on the same file."""
from pathlib import Path
import json
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "src"))
from test_map_markers_plugin import build  # noqa: E402
from fo4sf.planet import probe, records  # noqa: E402

TEMPLATES = {"world": ("Starfield.esm", 0x02DF8C, "SyntheticTemplateWorld"),
             "block": ("Starfield.esm", 0x102382, "SyntheticTemplateBlock"),
             "location": ("Starfield.esm", 0x3807BE, "SyntheticTemplateLocation")}


class PlanetProbeToolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dotnet = shutil.which("dotnet")
        if not cls.dotnet:
            raise unittest.SkipTest(".NET SDK needed for the actual tool test")
        fixture = build(cls.dotnet, "TerrainIdentityFixture")
        cls.tool = build(cls.dotnet, "PlanetProbe")
        temporary = tempfile.TemporaryDirectory(prefix="fo4sf-planetprobe-")
        cls.addClassCleanup(temporary.cleanup)
        cls.root = Path(temporary.name)
        cls.master = cls.root / "master/Starfield.esm"
        subprocess.run([cls.dotnet, str(fixture), str(cls.master), "overlay-ids"], capture_output=True, check=True)
        cls.plain = cls.root / "plain/Starfield.esm"
        subprocess.run([cls.dotnet, str(fixture), str(cls.plain)], capture_output=True, check=True)

    def run_tool(self, *argv):
        return subprocess.run([self.dotnet, str(self.tool), *map(str, argv)], capture_output=True, text=True)

    def params(self, name, **kw):
        prm = probe.params(records.DEFAULT_SYSTEM_ID, records.DEFAULT_PLANET_ID, list(range(100, 109)),
                           templates=TEMPLATES, **kw)
        path = self.root / name
        path.write_text(json.dumps(prm), encoding="utf-8")
        return prm, path

    def test_build_passes_both_checks(self):
        prm, prm_path = self.params("params.json", world_biome=("Starfield.esm", 0x0007F88A))
        out = self.root / "probe"
        r = self.run_tool("build", self.master, prm_path, out)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        plugin = out / probe.PLUGIN
        r = self.run_tool("check", plugin, self.master, prm_path)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("all checks pass", r.stdout)
        problems, summary = probe.check_plugin(str(plugin), prm)
        self.assertEqual(problems, [])
        self.assertEqual(summary["masters"], ["Starfield.esm", records.MASTER])
        self.assertEqual(len(summary["location"]["lcpr"]), 3)

    def test_a_template_with_another_editor_id_is_refused(self):
        prm, prm_path = self.params("wrong.json")
        prm["templates"]["block"]["edid"] = "OverlayBlockLC172World"
        prm_path.write_text(json.dumps(prm), encoding="utf-8")
        r = self.run_tool("build", self.master, prm_path, self.root / "wrong")
        self.assertEqual(r.returncode, 1)
        self.assertIn("refused", r.stderr)
        self.assertFalse((self.root / "wrong" / probe.PLUGIN).exists())

    def test_a_template_world_without_overlay_ids_is_refused(self):
        _, prm_path = self.params("plain.json")
        r = self.run_tool("build", self.plain, prm_path, self.root / "plainout")
        self.assertEqual(r.returncode, 1)
        self.assertIn("SNAM / PNAM", r.stderr)

    def test_check_finds_a_plugin_built_from_other_params(self):
        _, prm_path = self.params("a.json")
        out = self.root / "a"
        self.assertEqual(self.run_tool("build", self.master, prm_path, out).returncode, 0)
        prm, other = self.params("b.json")
        prm["system_id"] = 0x000F04F2
        other.write_text(json.dumps(prm), encoding="utf-8")
        r = self.run_tool("check", out / probe.PLUGIN, self.master, other)
        self.assertEqual(r.returncode, 1)
        self.assertIn("overlay SNAM / PNAM are not our system and planet", r.stdout)


if __name__ == "__main__":
    unittest.main()
