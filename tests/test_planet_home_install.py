"""Mock-only unit tests for `scripts/planet/home_world_install.py` (`W3`).
Tests ONLY against temporary directories and a temporary `LOCALAPPDATA` (`Plugins.txt`),
with `exp_install.build_ba2` stubbed via `ba2_fixture` — never touches any real game installation.
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
for sub in (HERE, ROOT / "scripts" / "planet", ROOT / "scripts" / "game", ROOT / "src"):
    p = str(sub)
    if p not in sys.path:
        sys.path.insert(0, p)

from ba2_fixture import archive_from_tree  # noqa: E402
from fo4sf.planet import biom, esm  # noqa: E402
import exp_install  # noqa: E402
import home_world_install as hwi  # noqa: E402
import make_home_planet  # noqa: E402

PLUGINS = ["FO4SFHome.esm", "FO4TerrainCore_Home.esm"]
MASTERS = {
    "FO4SFHome.esm": ["Starfield.esm"],
    "FO4TerrainCore_Home.esm": ["Starfield.esm", "FO4SFHome.esm", "FO4TerrainCore.esm"],
}
EXP_RECEIPT_BYTES = b'{\n "exp_dir": "X:/synthetic/core",\n "files": {},\n "complete": true\n}'
INITIAL_PLUGINS_BYTES = (
    b"\xef\xbb\xbf# Synthetic Plugins.txt\r\n"
    b"*FO4Port.esm\r\n"
    b"*FO4TerrainCore.esm\r\n"
    b"*FO4TerrainCore_Mars.esm\r\n"
)


def _write_bytes(path: str | Path, raw: bytes) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(raw)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _make_mock_stage(stage_dir: Path) -> Path:
    biom_raw = biom.build_uniform_biome_map(0x01000806)
    files = {
        name: esm.PluginWriter(MASTERS[name], esm.ESM, author=name).to_bytes(compress=False)
        for name in PLUGINS
    }
    files["Data/PlanetData/BiomeMaps/earth.biom"] = biom_raw
    files["Data/PlanetData/BiomeMaps/fo4sfhome.esm/earth.biom"] = biom_raw
    for rel, raw in files.items():
        _write_bytes(stage_dir / Path(*rel.split("/")), raw)
    plan = {
        "kind": "home-world",
        "version": 1,
        "plugins": PLUGINS,
        "swaps_out": ["FO4TerrainCore_Mars.esm"],
        "archive": "FO4SFHome - Main.ba2",
        "worlds": ["Commonwealth"],
        "lever_keywords": [],
        "planet_name": "Earth",
        "outputs": {k: _sha(v) for k, v in files.items()},
        "inputs": {"Starfield.esm": {"sha256": "0" * 64}, "world_plugins": {}},
    }
    (stage_dir / "plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
    return stage_dir


class HomeWorldInstallTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="fo4sf-home-install-")
        root = Path(self.tmp.name)
        self.game = root / "mock_game"
        self.data = self.game / "Data"
        self.data.mkdir(parents=True)
        _write_bytes(self.data / exp_install.RECORD, EXP_RECEIPT_BYTES)

        self.staged = _make_mock_stage(root / "home_stage")
        self.local = root / "mock_localappdata"
        self.plugins_txt = self.local / "Starfield" / "Plugins.txt"
        _write_bytes(self.plugins_txt, INITIAL_PLUGINS_BYTES)

        self.old_local = os.environ.get("LOCALAPPDATA")
        os.environ["LOCALAPPDATA"] = str(self.local)
        self.saved = (exp_install.build_ba2, make_home_planet.verify_stage)

        def stub_build(a, root_dir, out, textures=None):
            _write_bytes(out, archive_from_tree(Path(root_dir)))
            return out

        exp_install.build_ba2 = stub_build
        make_home_planet.verify_stage = lambda d, plan, data=None: []

    def tearDown(self) -> None:
        exp_install.build_ba2, make_home_planet.verify_stage = self.saved
        if self.old_local is None:
            os.environ.pop("LOCALAPPDATA", None)
        else:
            os.environ["LOCALAPPDATA"] = self.old_local
        self.tmp.cleanup()

    def run_cli(self, *argv: str) -> tuple[int | str, str]:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                rc = hwi.main(list(argv) + ["--starfield", str(self.game)]) or 0
            except SystemExit as exc:
                rc = exc.code if exc.code is not None else 0
        return rc, buf.getvalue()

    def plugin_lines(self) -> list[str]:
        return self.plugins_txt.read_text(encoding="utf-8-sig").splitlines()

    def test_install_unticks_mars_ticks_home_keeps_exp_receipt_and_undo_restores_byte_for_byte(self) -> None:
        rc, out = self.run_cli("install", "--dir", str(self.staged))
        self.assertEqual(rc, 0, out)
        self.assertEqual(exp_install.RECORD, "FO4SFExp.install.json")

        # Verify files added and exp_install's own receipt untouched byte-for-byte
        for fname in PLUGINS + ["FO4SFHome - Main.ba2", hwi.RECORD, hwi.SWAP_RECORD]:
            self.assertTrue((self.data / fname).is_file(), fname)
        self.assertEqual((self.data / exp_install.RECORD).read_bytes(), EXP_RECEIPT_BYTES)

        # Verify _Mars unticked and FO4SFHome + FO4TerrainCore_Home ticked
        self.assertEqual(
            self.plugin_lines(),
            [
                "# Synthetic Plugins.txt",
                "*FO4Port.esm",
                "*FO4TerrainCore.esm",
                "FO4TerrainCore_Mars.esm",
                "*FO4SFHome.esm",
                "*FO4TerrainCore_Home.esm",
            ],
        )
        self.assertEqual(self.run_cli("active")[0], 0)
        self.assertEqual(self.run_cli("order")[0], 0)
        self.assertEqual(self.run_cli("status")[0], 0)

        # Undo restores Plugins.txt and Data byte-for-byte
        rc_undo, out_undo = self.run_cli("undo")
        self.assertEqual(rc_undo, 0, out_undo)
        for fname in PLUGINS + ["FO4SFHome - Main.ba2", hwi.RECORD, hwi.SWAP_RECORD]:
            self.assertFalse((self.data / fname).exists(), fname)
        self.assertEqual(self.plugins_txt.read_bytes(), INITIAL_PLUGINS_BYTES)
        self.assertEqual((self.data / exp_install.RECORD).read_bytes(), EXP_RECEIPT_BYTES)

    def test_refuses_load_list_holding_both_mars_and_home_active(self) -> None:
        bad_bytes = (
            b"# Synthetic Plugins.txt\r\n"
            b"*FO4TerrainCore.esm\r\n"
            b"*FO4TerrainCore_Mars.esm\r\n"
            b"*FO4TerrainCore_Home.esm\r\n"
        )
        _write_bytes(self.plugins_txt, bad_bytes)
        rc, _out = self.run_cli("install", "--dir", str(self.staged))
        self.assertNotEqual(rc, 0)
        self.assertIn("both FO4TerrainCore_Mars.esm and FO4TerrainCore_Home.esm", str(rc))
        self.assertFalse((self.data / hwi.RECORD).exists())
        self.assertEqual(self.plugins_txt.read_bytes(), bad_bytes)

        # Also check `active` and `order` refuse dual active hosts
        self.assertEqual(self.run_cli("active")[0], 8)
        self.assertEqual(self.run_cli("order")[0], 6)

    def test_uninstall_alias_also_restores_byte_for_byte(self) -> None:
        self.assertEqual(self.run_cli("install", "--dir", str(self.staged))[0], 0)
        self.assertEqual(self.run_cli("uninstall")[0], 0)
        self.assertEqual(self.plugins_txt.read_bytes(), INITIAL_PLUGINS_BYTES)
        self.assertEqual((self.data / exp_install.RECORD).read_bytes(), EXP_RECEIPT_BYTES)


if __name__ == "__main__":
    unittest.main()
