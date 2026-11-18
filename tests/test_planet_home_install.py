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
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
for sub in (HERE, ROOT / "scripts" / "planet", ROOT / "scripts" / "game", ROOT / "src"):
    p = str(sub)
    if p not in sys.path:
        sys.path.insert(0, p)

from ba2_fixture import archive_from_tree  # noqa: E402
from fo4sf.planet import biom, esm, records  # noqa: E402
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
        self.saved = (exp_install.build_ba2, make_home_planet.verify_stage, hwi._active_game_pids)

        def stub_build(a, root_dir, out, textures=None):
            _write_bytes(out, archive_from_tree(Path(root_dir)))
            return out

        exp_install.build_ba2 = stub_build
        make_home_planet.verify_stage = lambda d, plan, data=None: []
        hwi._active_game_pids = lambda system=None: []

    def tearDown(self) -> None:
        exp_install.build_ba2, make_home_planet.verify_stage, hwi._active_game_pids = self.saved
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

    def test_c1_refuses_install_and_uninstall_when_starfield_exe_is_running_or_check_fails(self) -> None:
        # 1. Running Starfield.exe refuses install before touching Data or Plugins.txt
        with patch.object(hwi, "_active_game_pids", return_value=[4242]):
            rc, _out = self.run_cli("install", "--dir", str(self.staged))
        self.assertIn("Starfield.exe is running (pid 4242)", str(rc))
        self.assertFalse((self.data / hwi.RECORD).exists())
        self.assertEqual(self.plugins_txt.read_bytes(), INITIAL_PLUGINS_BYTES)

        # 2. Failed process query also refuses install
        with patch.object(hwi, "_active_game_pids", side_effect=ValueError("tasklist unavailable")):
            rc_err, _out = self.run_cli("install", "--dir", str(self.staged))
        self.assertIn("cannot confirm Starfield.exe is closed", str(rc_err))
        self.assertFalse((self.data / hwi.RECORD).exists())

        # 3. Install cleanly when game is closed, then verify running Starfield.exe refuses undo & uninstall
        self.assertEqual(self.run_cli("install", "--dir", str(self.staged))[0], 0)
        installed_plugins_bytes = self.plugins_txt.read_bytes()
        for cmd in ("undo", "uninstall"):
            with patch.object(hwi, "_active_game_pids", return_value=[9001]):
                rc_u, _ = self.run_cli(cmd)
            self.assertIn("Starfield.exe is running (pid 9001)", str(rc_u))
            self.assertTrue((self.data / hwi.RECORD).is_file())
            self.assertEqual(self.plugins_txt.read_bytes(), installed_plugins_bytes)

        # 4. Once closed, undo restores cleanly
        self.assertEqual(self.run_cli("undo")[0], 0)
        self.assertEqual(self.plugins_txt.read_bytes(), INITIAL_PLUGINS_BYTES)

    def _build_map_markers_and_home_stage(
        self,
        stage_dir: Path,
        *,
        include_mm_rows_in_home: bool = True,
        pin_sha_override: str | None = None,
    ) -> tuple[Path, str]:
        """Write synthetic `FO4TerrainCore.esm` + `FO4SFMapMarkers.esm` in `self.data` and a matching home stage."""
        cw = esm.PluginWriter(["Starfield.esm"], esm.ESM)
        core_row = struct.pack("<5I", 0x0002271F, cw.own(0x80A), cw.own(0x803), 0, 0xFFFFFFFF)
        cw.add(
            esm.Record(
                b"LCTN",
                cw.own(0x802),
                [(b"EDID", esm.zbytes("FO4Core_CommonwealthLocation")), (b"LCSR", core_row)],
            )
        )
        cw.add(esm.Record(b"WRLD", cw.own(0x803), [(b"EDID", esm.zbytes("FO4Core_Commonwealth"))]))
        cw.write(str(self.data / "FO4TerrainCore.esm"), compress=False)

        mm = esm.PluginWriter(["Starfield.esm", "FO4TerrainCore.esm"], esm.ESM)
        mm_core_row = struct.pack("<5I", 0x0002271F, 0x0100080A, 0x01000803, 0, 0xFFFFFFFF)
        mm_extra_row = struct.pack("<5I", 0x0002271F, 0x02000800, 0x01000803, 12, 0xFFFFFFFF)
        mm.add(
            esm.Record(
                b"LCTN",
                0x01000802,
                [(b"EDID", esm.zbytes("FO4Core_CommonwealthLocation")), (b"LCSR", mm_core_row + mm_extra_row)],
            )
        )
        mm.add(esm.Record(b"WRLD", 0x01000803, [(b"EDID", esm.zbytes("FO4Core_Commonwealth"))]))
        mm_path = self.data / "FO4SFMapMarkers.esm"
        mm.write(str(mm_path), compress=False)
        mm_sha = _sha(mm_path.read_bytes())

        hm = esm.PluginWriter(["Starfield.esm"], esm.ESM)
        hm.add(
            esm.Record(
                b"PNDT",
                0x01000805,
                [(b"EDID", esm.zbytes("EarthPlanetData")), (b"BDST", b""), (b"ANAM", esm.zbytes("Earth")), (b"BDED", b"")],
            )
        )

        reg_masters = ["Starfield.esm", "FO4SFHome.esm", "FO4TerrainCore.esm"]
        if include_mm_rows_in_home:
            reg_masters.append("FO4SFMapMarkers.esm")
        reg = esm.PluginWriter(reg_masters, esm.ESM)
        reg.add(
            esm.Record(
                b"PNDT",
                0x01000805,
                [(b"EDID", esm.zbytes("EarthPlanetData")), (b"BDST", b""), (b"ANAM", esm.zbytes("Earth")), (b"BDED", b"")],
            )
        )
        reg_core_row = struct.pack("<5I", 0x0002271F, 0x0200080A, 0x02000803, 0, 0xFFFFFFFF)
        reg_extra_row = struct.pack("<5I", 0x0002271F, 0x03000800, 0x02000803, 12, 0xFFFFFFFF)
        reg_lcsr = (reg_core_row + reg_extra_row) if include_mm_rows_in_home else reg_core_row
        reg.add(
            esm.Record(
                b"LCTN",
                0x02000802,
                [(b"EDID", esm.zbytes("FO4Core_CommonwealthLocation")), (b"LCSR", reg_lcsr)],
            )
        )
        reg.add(esm.Record(b"WRLD", 0x02000803, [(b"EDID", esm.zbytes("FO4Core_Commonwealth"))]))

        biom_raw = biom.build_uniform_biome_map(0x01000806)
        files = {
            "FO4SFHome.esm": hm.to_bytes(compress=False),
            "FO4TerrainCore_Home.esm": reg.to_bytes(compress=False),
            "Data/PlanetData/BiomeMaps/earth.biom": biom_raw,
            "Data/PlanetData/BiomeMaps/fo4sfhome.esm/earth.biom": biom_raw,
        }
        for rel, raw in files.items():
            _write_bytes(stage_dir / Path(*rel.split("/")), raw)
        pinned = pin_sha_override if pin_sha_override is not None else mm_sha
        plan = {
            "kind": "home-world",
            "version": 1,
            "plugins": PLUGINS,
            "swaps_out": ["FO4TerrainCore_Mars.esm"],
            "archive": "FO4SFHome - Main.ba2",
            "worlds": ["Commonwealth"],
            "lever_keywords": [],
            "planet_name": "Earth",
            "map_markers_plugin": "FO4SFMapMarkers.esm",
            "map_markers_sha256": pinned,
            "outputs": {k: _sha(v) for k, v in files.items()},
            "inputs": {"Starfield.esm": {"sha256": "0" * 64}, "world_plugins": {}},
        }
        (stage_dir / "plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
        return stage_dir, mm_sha

    def test_c3_allows_map_markers_before_home_when_lcsr_and_hash_match(self) -> None:
        stage_dir, _mm_sha = self._build_map_markers_and_home_stage(Path(self.tmp.name) / "stage_mm_ok")
        _write_bytes(
            self.plugins_txt,
            b"*FO4Port.esm\r\n*FO4TerrainCore.esm\r\n*FO4TerrainCore_Mars.esm\r\n*FO4SFMapMarkers.esm\r\n",
        )
        rc, out = self.run_cli("install", "--dir", str(stage_dir))
        self.assertEqual(rc, 0, out)
        self.assertEqual(
            self.plugin_lines(),
            [
                "*FO4Port.esm",
                "*FO4TerrainCore.esm",
                "FO4TerrainCore_Mars.esm",
                "*FO4SFMapMarkers.esm",
                "*FO4SFHome.esm",
                "*FO4TerrainCore_Home.esm",
            ],
        )
        rc_ord, out_ord = self.run_cli("order")
        self.assertEqual(rc_ord, 0, out_ord)

    def test_c3_refuses_when_map_markers_loads_after_home_in_install_and_order(self) -> None:
        stage_dir, _mm_sha = self._build_map_markers_and_home_stage(Path(self.tmp.name) / "stage_mm_order")
        # 1. Pre-existing unticked FO4TerrainCore_Home.esm before *FO4SFMapMarkers.esm -> install refuses
        bad_pre = (
            b"*FO4TerrainCore.esm\r\n"
            b"FO4SFHome.esm\r\n"
            b"FO4TerrainCore_Home.esm\r\n"
            b"*FO4SFMapMarkers.esm\r\n"
        )
        _write_bytes(self.plugins_txt, bad_pre)
        rc, _ = self.run_cli("install", "--dir", str(stage_dir))
        self.assertNotEqual(rc, 0)
        self.assertIn("FO4SFMapMarkers.esm", str(rc))
        self.assertIn("FO4TerrainCore_Home.esm", str(rc))
        self.assertFalse((self.data / hwi.RECORD).exists())

        # 2. Install cleanly first, then reorder Plugins.txt so *FO4SFMapMarkers.esm loads after *FO4TerrainCore_Home.esm -> order refuses
        _write_bytes(self.plugins_txt, b"*FO4TerrainCore.esm\r\n*FO4SFMapMarkers.esm\r\n")
        self.assertEqual(self.run_cli("install", "--dir", str(stage_dir))[0], 0)
        _write_bytes(
            self.plugins_txt,
            b"*FO4TerrainCore.esm\r\n*FO4SFHome.esm\r\n*FO4TerrainCore_Home.esm\r\n*FO4SFMapMarkers.esm\r\n",
        )
        rc_ord, out_ord = self.run_cli("order")
        self.assertEqual(rc_ord, 6)
        self.assertIn("FO4SFMapMarkers.esm", out_ord)
        self.assertIn("FO4TerrainCore_Home.esm", out_ord)

    def test_c3_refuses_when_map_markers_hash_differs_or_lcsr_rows_missing(self) -> None:
        # 1. Hash mismatch refuses install
        stage_bad_sha, _ = self._build_map_markers_and_home_stage(
            Path(self.tmp.name) / "stage_bad_sha",
            pin_sha_override="f" * 64,
        )
        _write_bytes(self.plugins_txt, b"*FO4TerrainCore.esm\r\n*FO4SFMapMarkers.esm\r\n")
        rc_sha, _ = self.run_cli("install", "--dir", str(stage_bad_sha))
        self.assertNotEqual(rc_sha, 0)
        self.assertIn("sha256 mismatch", str(rc_sha))
        self.assertFalse((self.data / hwi.RECORD).exists())

        # 2. Missing LCSR rows refuses install even when hash matches
        stage_missing_lcsr, _ = self._build_map_markers_and_home_stage(
            Path(self.tmp.name) / "stage_no_lcsr",
            include_mm_rows_in_home=False,
        )
        rc_lcsr, _ = self.run_cli("install", "--dir", str(stage_missing_lcsr))
        self.assertNotEqual(rc_lcsr, 0)
        self.assertIn("missing 1 LCSR row(s)", str(rc_lcsr))
        self.assertFalse((self.data / hwi.RECORD).exists())

        # 3. Hash tamper after clean install refuses order
        stage_ok, _ = self._build_map_markers_and_home_stage(Path(self.tmp.name) / "stage_ok_then_tamper")
        self.assertEqual(self.run_cli("install", "--dir", str(stage_ok))[0], 0)
        tampered = esm.PluginWriter(["Starfield.esm", "FO4TerrainCore.esm"], esm.ESM, author="tampered")
        tampered.write(str(self.data / "FO4SFMapMarkers.esm"), compress=False)
        rc_ord, out_ord = self.run_cli("order")
        self.assertEqual(rc_ord, 6)
        self.assertIn("sha256 mismatch", out_ord)

    def test_c3_refuses_any_other_pndt_lctn_or_wrld_duplicate_naming_both_plugins(self) -> None:
        stage_dir, _ = self._build_map_markers_and_home_stage(Path(self.tmp.name) / "stage_other_dups")

        # 1. Another active FO4SF plugin overriding WRLD fo4terraincore.esm:000803 -> refused naming both plugins & FormKey
        wrld_dup = esm.PluginWriter(["Starfield.esm", "FO4TerrainCore.esm"], esm.ESM)
        wrld_dup.add(esm.Record(b"WRLD", 0x01000803, [(b"EDID", esm.zbytes("FO4Core_Commonwealth"))]))
        wrld_dup.write(str(self.data / "FO4SFOtherWorldOv.esm"), compress=False)
        _write_bytes(
            self.plugins_txt,
            b"*FO4TerrainCore.esm\r\n*FO4SFMapMarkers.esm\r\n*FO4SFOtherWorldOv.esm\r\n",
        )
        rc_w, _ = self.run_cli("install", "--dir", str(stage_dir))
        self.assertNotEqual(rc_w, 0)
        self.assertIn("duplicate WRLD override of fo4terraincore.esm:000803", str(rc_w))
        self.assertIn("FO4SFOtherWorldOv.esm", str(rc_w))
        self.assertIn("FO4TerrainCore_Home.esm", str(rc_w))

        # 2. Another active FO4SF plugin overriding LCTN fo4terraincore.esm:000802 -> refused naming both plugins & FormKey
        lctn_dup = esm.PluginWriter(["Starfield.esm", "FO4TerrainCore.esm"], esm.ESM)
        lctn_dup.add(records.new_location(0x01000802, "FO4Core_CommonwealthLocation", "CW", [0x2CA99D], 0x01B736, 0, 4))
        lctn_dup.write(str(self.data / "FO4SFOtherLocOv.esm"), compress=False)
        _write_bytes(self.plugins_txt, b"*FO4TerrainCore.esm\r\n*FO4SFOtherLocOv.esm\r\n")
        rc_l, _ = self.run_cli("install", "--dir", str(stage_dir))
        self.assertNotEqual(rc_l, 0)
        self.assertIn("duplicate LCTN override of fo4terraincore.esm:000802", str(rc_l))
        self.assertIn("FO4SFOtherLocOv.esm", str(rc_l))
        self.assertIn("FO4TerrainCore_Home.esm", str(rc_l))

        # 3. Another active FO4SF plugin overriding PNDT fo4sfhome.esm:000805 -> refused naming both plugins & FormKey
        pndt_dup = esm.PluginWriter(["Starfield.esm", "FO4SFHome.esm"], esm.ESM)
        pndt_dup.add(
            esm.Record(
                b"PNDT",
                0x01000805,
                [(b"EDID", esm.zbytes("EarthPlanetData")), (b"BDST", b""), (b"ANAM", esm.zbytes("Earth")), (b"BDED", b"")],
            )
        )
        pndt_dup.write(str(self.data / "FO4SFOtherPlanetOv.esm"), compress=False)
        _write_bytes(self.plugins_txt, b"*FO4TerrainCore.esm\r\n*FO4SFOtherPlanetOv.esm\r\n")
        rc_p, _ = self.run_cli("install", "--dir", str(stage_dir))
        self.assertNotEqual(rc_p, 0)
        self.assertIn("duplicate PNDT override of fo4sfhome.esm:000805", str(rc_p))
        self.assertIn("FO4SFOtherPlanetOv.esm", str(rc_p))
        self.assertIn("FO4TerrainCore_Home.esm", str(rc_p))


if __name__ == "__main__":
    unittest.main()
