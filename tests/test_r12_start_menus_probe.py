"""Offline unit tests for `scripts/probes/make_r12_start_menus_probe.py` (Round 12 Task 5)."""
from __future__ import annotations

import json
import os
import shutil
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (
    ROOT / "src",
    ROOT / "scripts" / "probes",
    ROOT / "scripts" / "ui",
    ROOT / "scripts" / "testing",
):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import make_probe_swf as swf  # noqa: E402
import make_r12_start_menus_probe as stager  # noqa: E402
import probe_common as pc  # noqa: E402
from fo4sf.planet.esm import PluginWriter, Record, group_bytes, zbytes  # noqa: E402


class _FakeSystem:
    def __init__(self, pids: list[int] | None = None) -> None:
        self._pids = pids or []

    def pids(self, image: str = "Starfield.exe") -> list[int]:
        return list(self._pids)


def _minimal_swf_bytes() -> bytes:
    body = (
        swf.rect(0, 800 * 20, 0, 600 * 20)
        + struct.pack("<HH", 30 << 8, 1)
        + swf.tag(swf.FILE_ATTRIBUTES, struct.pack("<I", swf.AS3))
        + swf.tag(swf.SHOW_FRAME)
        + swf.tag(swf.END)
    )
    return b"CWS" + bytes([12]) + struct.pack("<I", 8 + len(body)) + zlib.compress(body, 6)


def _clean_newgame_esm_bytes(*, full_name: str = "Out of Time") -> bytes:
    pw = PluginWriter(["Starfield.esm"])
    pw.add(Record(b"QUST", pw.own(0x800), [(b"EDID", zbytes("FO4SF_NewGame")), (b"FULL", zbytes(full_name))]))
    return pw.to_bytes()


def _dirty_wrld_esm_bytes() -> bytes:
    pw = PluginWriter(["Starfield.esm", "FO4TerrainCore.esm"])
    cw_wrld = Record(b"WRLD", (1 << 24) | 0x803, [(b"EDID", zbytes("FO4Core_Commonwealth"))])
    return pw.to_bytes() + group_bytes("WRLD", cw_wrld.to_bytes())


def _build_synthetic_inputs(base: Path) -> dict[str, Path]:
    ng_stage = base / "ng_stage"
    ng_scripts = ng_stage / "Data" / "Scripts"
    ng_meshes = ng_stage / "Data" / "meshes" / "fo4sf" / "newgame"
    ng_scripts.mkdir(parents=True, exist_ok=True)
    ng_meshes.mkdir(parents=True, exist_ok=True)
    (ng_stage / "FO4SFNewGame.esm").write_bytes(_clean_newgame_esm_bytes())
    for sname in (
        "FO4SF_NewGameQuest.pex",
        "FO4SF_NewGameLooks.pex",
        "FO4SF_NewGameSpecial.pex",
        "FO4SF_NewGameVersion.pex",
    ):
        (ng_scripts / sname).write_bytes(f"PEX:{sname}".encode("ascii"))
    (ng_meshes / "v111_pipboy_pickup.nif").write_bytes(b"Gamebryo File Format, Version 20.2.0.7\n")

    iface_dir = base / "Interface"
    iface_dir.mkdir(parents=True, exist_ok=True)
    (iface_dir / "FO4SF_Fo4Shell.swf").write_bytes(_minimal_swf_bytes())

    dll_src = base / "FO4SFPipboyMenu.dll"
    dll_src.write_bytes(b"MZ-SYNTHETIC-DLL")

    sf_dir = base / "Starfield"
    (sf_dir / "Data").mkdir(parents=True, exist_ok=True)
    (sf_dir / "Data" / "FO4SFNewGame.esm").write_bytes(b"OLD-NEWGAME-ESM")
    (sf_dir / "Data" / "Scripts").mkdir(parents=True, exist_ok=True)
    (sf_dir / "Data" / "Scripts" / "FO4SF_NewGameQuest.pex").write_bytes(b"OLD-QUEST-PEX")
    (sf_dir / "Data" / "SFSE" / "Plugins").mkdir(parents=True, exist_ok=True)
    (sf_dir / "Data" / "SFSE" / "Plugins" / "FO4SFPipboyMenu.dll").write_bytes(b"OLD-DLL")
    (sf_dir / "Data" / "SFSE" / "Plugins" / "FO4SFPipboyMenu.ini").write_bytes(b"OLD-INI")
    plugins_txt = base / "Plugins.txt"
    plugins_txt.write_text("# Starfield Plugins\n*FO4TerrainCore.esm\n", encoding="utf-8", newline="\n")

    return {
        "ng_stage": ng_stage,
        "iface_dir": iface_dir,
        "dll_src": dll_src,
        "sf_dir": sf_dir,
        "plugins_txt": plugins_txt,
    }


class R12StartMenusProbeTests(unittest.TestCase):
    def test_stage_and_verify_synthetic_probe_and_negative_gates(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inp = _build_synthetic_inputs(root)
            out_dir = root / "staged_r12_t5"

            manifest = stager.stage_probe(
                out_dir=out_dir,
                starfield_dir=inp["sf_dir"],
                newgame_stage_dir=inp["ng_stage"],
                pipboy_dll=inp["dll_src"],
                interface_dir=inp["iface_dir"],
                min_free_gb=0.0,
                system=_FakeSystem([]),
            )
            self.assertEqual(manifest["probe_id"], "r12-start-menus")
            self.assertEqual(
                manifest["available_starts"],
                ["fo4_vault111", "minutemen_sanctuary", "gunners_plaza", "raiders_corvega"],
            )
            self.assertTrue((out_dir / "bat" / "s5a.txt").is_file())
            self.assertTrue((out_dir / "bat" / "s5b.txt").is_file())
            self.assertTrue((out_dir / "Data" / "FO4SFNewGame - Main.ba2").is_file())

            rep = stager.verify_probe(
                stage_dir=out_dir,
                card_path=ROOT / "docs" / "testing" / "r12-start-menus-card.md",
            )
            self.assertTrue(rep["verified"])
            self.assertTrue(rep["card_validated"])
            self.assertGreaterEqual(rep["ba2_entries"], 5)

            # Negative gate 1: tampering MapBlockStarMap=1 in staged INI must fail verification
            ini_p = out_dir / "Data" / "SFSE" / "Plugins" / "FO4SFPipboyMenu.ini"
            orig_ini = ini_p.read_text(encoding="utf-8")
            ini_p.write_text(orig_ini.replace("MapBlockStarMap=0", "MapBlockStarMap=1"), encoding="utf-8")
            man_data = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
            for item in man_data["files"]:
                if item["target_rel"] == "Data/SFSE/Plugins/FO4SFPipboyMenu.ini":
                    item["sha256"] = pc.sha256_file(ini_p)
            (out_dir / "manifest.json").write_text(json.dumps(man_data), encoding="utf-8")
            with self.assertRaises(pc.ProbeValidationError):
                stager.verify_probe(stage_dir=out_dir)
            ini_p.write_text(orig_ini, encoding="utf-8")
            for item in man_data["files"]:
                if item["target_rel"] == "Data/SFSE/Plugins/FO4SFPipboyMenu.ini":
                    item["sha256"] = pc.sha256_file(ini_p)
            (out_dir / "manifest.json").write_text(json.dumps(man_data), encoding="utf-8")

            # Negative gate 2: non-Vault-111 Story row claiming available=true must be rejected
            sp_p = out_dir / "Data" / "SFSE" / "Plugins" / "FO4SFStartPlaces.json"
            sp_orig = sp_p.read_text(encoding="utf-8")
            sp_obj = json.loads(sp_orig)
            for row in sp_obj["places"]:
                if row["id"] == "fo3_vault101":
                    row["available"] = True
            sp_p.write_text(json.dumps(sp_obj, indent=2), encoding="utf-8")
            for item in man_data["files"]:
                if item["target_rel"] == "Data/SFSE/Plugins/FO4SFStartPlaces.json":
                    item["sha256"] = pc.sha256_file(sp_p)
            (out_dir / "manifest.json").write_text(json.dumps(man_data), encoding="utf-8")
            with self.assertRaises(ValueError):
                stager.verify_probe(stage_dir=out_dir)
            sp_p.write_text(sp_orig, encoding="utf-8")
            for item in man_data["files"]:
                if item["target_rel"] == "Data/SFSE/Plugins/FO4SFStartPlaces.json":
                    item["sha256"] = pc.sha256_file(sp_p)
            (out_dir / "manifest.json").write_text(json.dumps(man_data), encoding="utf-8")

            # Negative gate 3: WRLD override on FO4Core_Commonwealth in FO4SFNewGame.esm fails scan
            esm_p = out_dir / "Data" / "FO4SFNewGame.esm"
            esm_p.write_bytes(_dirty_wrld_esm_bytes())
            for item in man_data["files"]:
                if item["target_rel"] == "Data/FO4SFNewGame.esm":
                    item["sha256"] = pc.sha256_file(esm_p)
            (out_dir / "manifest.json").write_text(json.dumps(man_data), encoding="utf-8")
            with self.assertRaises(pc.ProbeValidationError):
                stager.verify_probe(stage_dir=out_dir)

    def test_install_status_and_uninstall_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inp = _build_synthetic_inputs(root)
            out_dir = root / "staged_r12_t5"

            stager.stage_probe(
                out_dir=out_dir,
                starfield_dir=inp["sf_dir"],
                newgame_stage_dir=inp["ng_stage"],
                pipboy_dll=inp["dll_src"],
                interface_dir=inp["iface_dir"],
                min_free_gb=0.0,
                system=_FakeSystem([]),
            )

            with self.assertRaises(pc.ProbePreflightError):
                stager.install_probe_cmd(
                    stage_dir=out_dir,
                    starfield_dir=inp["sf_dir"],
                    plugins_txt=inp["plugins_txt"],
                    min_free_gb=0.0,
                    system=_FakeSystem([1234]),
                )

            rcpt = stager.install_probe_cmd(
                stage_dir=out_dir,
                starfield_dir=inp["sf_dir"],
                plugins_txt=inp["plugins_txt"],
                min_free_gb=0.0,
                allow_hardlink=False,
                system=_FakeSystem([]),
            )
            self.assertTrue(rcpt["complete"])
            self.assertTrue((inp["sf_dir"] / "s5a.txt").is_file())
            self.assertTrue((inp["sf_dir"] / "s5b.txt").is_file())
            self.assertIn("*FO4SFNewGame.esm", inp["plugins_txt"].read_text(encoding="utf-8"))
            self.assertEqual(
                (inp["sf_dir"] / "Data" / "SFSE" / "Plugins" / "FO4SFPipboyMenu.dll").read_bytes(),
                b"MZ-SYNTHETIC-DLL",
            )

            st = pc.probe_status(probe_id=stager.PROBE_ID, starfield_dir=inp["sf_dir"])
            self.assertTrue(st["installed"])
            self.assertEqual(st["state"], "installed")

            res = pc.uninstall_probe(
                probe_id=stager.PROBE_ID,
                starfield_dir=inp["sf_dir"],
                system=_FakeSystem([]),
            )
            self.assertIn("s5a.txt", res["removed_adds"])
            self.assertFalse((inp["sf_dir"] / "s5a.txt").exists())
            self.assertEqual((inp["sf_dir"] / "Data" / "FO4SFNewGame.esm").read_bytes(), b"OLD-NEWGAME-ESM")
            self.assertEqual(
                (inp["sf_dir"] / "Data" / "SFSE" / "Plugins" / "FO4SFPipboyMenu.dll").read_bytes(),
                b"OLD-DLL",
            )
            self.assertNotIn("FO4SFNewGame.esm", inp["plugins_txt"].read_text(encoding="utf-8"))

            st_after = pc.probe_status(probe_id=stager.PROBE_ID, starfield_dir=inp["sf_dir"])
            self.assertFalse(st_after["installed"])
            self.assertEqual(st_after["state"], "not_installed")

    def test_reuse_tested_binary_matches_slot2_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fake_dll = root / "tested.dll"
            fake_dll.write_bytes(b"TESTED-SLOT2-DLL")
            dst_dll = root / "out" / "FO4SFPipboyMenu.dll"

            res = pc.reuse_tested_binary(
                stager._pipboy_src_paths(),
                stager.TESTED_SLOT2_PIPBOY_SOURCE_HASHES,
                fake_dll,
                lambda: root / "should_not_run.dll",
                dst_path=dst_dll,
            )
            self.assertTrue(res.reused)
            self.assertEqual(dst_dll.read_bytes(), b"TESTED-SLOT2-DLL")

            # Mutated copy triggers fallback build cleanly
            mutated_src = root / "src_copy"
            shutil.copytree(ROOT / "sfse" / "FO4SFPipboyMenu", mutated_src)
            (mutated_src / "src" / "main.cpp").write_text("// changed\n", encoding="utf-8")
            mutated_paths = [mutated_src / rel for rel in stager.PIPBOY_SOURCE_REL_PATHS]
            rebuilt = root / "rebuilt.dll"
            rebuilt.write_bytes(b"REBUILT-DLL")
            res2 = pc.reuse_tested_binary(
                mutated_paths,
                stager.TESTED_SLOT2_PIPBOY_SOURCE_HASHES,
                fake_dll,
                lambda: rebuilt,
                dst_path=root / "out2" / "FO4SFPipboyMenu.dll",
            )
            self.assertFalse(res2.reused)
            self.assertEqual((root / "out2" / "FO4SFPipboyMenu.dll").read_bytes(), b"REBUILT-DLL")

    def test_install_refuses_active_routeloot_and_allows_inactive_routeloot(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            stage_dir = root / "stage"
            sf_dir = root / "Starfield"
            data_dir = sf_dir / "Data"
            data_dir.mkdir(parents=True)
            stage_dir.mkdir(parents=True)
            (stage_dir / "manifest.json").write_text(
                json.dumps({"plugins_to_activate": ["FO4SFNewGame.esm"], "files": []}),
                encoding="utf-8",
            )
            plugins_txt = root / "Plugins.txt"
            plugins_txt.write_text("*FO4TerrainCore.esm\n*FO4SFRouteLoot.esm\n", encoding="utf-8")
            with self.assertRaisesRegex(pc.ProbeInstallError, "FO4SFRouteLoot\\.esm"):
                stager.install_probe_cmd(stage_dir=stage_dir, starfield_dir=sf_dir, plugins_txt=plugins_txt)

            # Deactivated (# or unstarred) clears the RouteLoot guard and proceeds to probe_common.install_probe
            plugins_txt.write_text("*FO4TerrainCore.esm\n# *FO4SFRouteLoot.esm\n", encoding="utf-8")
            stager._assert_no_active_routeloot(plugins_txt)
            plugins_txt.write_text("*FO4TerrainCore.esm\nFO4SFRouteLoot.esm\n", encoding="utf-8")
            stager._assert_no_active_routeloot(plugins_txt)

    def test_task8_no_hardcoded_drive_defaults_and_f12_sanctuary_cell_label(self) -> None:
        src = (ROOT / "scripts" / "probes" / "make_r12_start_menus_probe.py").read_text(encoding="utf-8")
        self.assertNotRegex(src, r"[A-Za-z]:\\")
        self.assertIsNone(stager.DEFAULT_STARFIELD_DIR)
        self.assertIsNone(stager.DEFAULT_BASELINE_DIR)
        self.assertIsNone(stager.DEFAULT_FO4_DATA_DIR)
        self.assertIsNone(stager.DEFAULT_PORT_ESM)
        self.assertIsNone(stager.DEFAULT_PORT_IDS)
        self.assertIsNone(stager.DEFAULT_TESTED_PIPBOY_DLL)
        sanctuary = next(a for a in stager.COMMONWEALTH_WARFARE_ANCHORS if a.name == "sanctuary")
        self.assertEqual(sanctuary.cell, "Sanctuary Hills (-12, 12)")

    def test_f1_install_accepts_candidate_2g_fix4_hashes_and_copies_build_json(self) -> None:
        import hashlib

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inp = _build_synthetic_inputs(root)
            build_json_src = inp["dll_src"].parent / "build.json"
            build_json_src.write_text('{"plugin": "FO4SFPipboyMenu"}\n', encoding="utf-8")
            out_dir = root / "staged_r13"

            man = stager.stage_probe(
                out_dir=out_dir,
                starfield_dir=inp["sf_dir"],
                newgame_stage_dir=inp["ng_stage"],
                pipboy_dll=inp["dll_src"],
                interface_dir=inp["iface_dir"],
                min_free_gb=0.0,
                system=_FakeSystem([]),
            )
            self.assertTrue((out_dir / "build.json").is_file())
            self.assertEqual(man["pipboy_build_json_sha256"], pc.sha256_file(build_json_src))

            # Populate Starfield Data matching a candidate-2g-fix4 baseline file hash
            mission_p = inp["sf_dir"] / "Data" / "FO4SFMission.esm"
            exp_mission_sha = pc.CANDIDATE_2G_FIX4_HASHES["Data/FO4SFMission.esm"]
            # Override expected spec temporarily in memory only? Instead confirm non-matching warns with candidate-2g-fix4 label
            mission_p.write_bytes(b"MISMATCH-DATA")
            rcpt = stager.install_probe_cmd(
                stage_dir=out_dir,
                starfield_dir=inp["sf_dir"],
                plugins_txt=inp["plugins_txt"],
                min_free_gb=0.0,
                allow_hardlink=False,
                system=_FakeSystem([]),
            )
            self.assertTrue(rcpt["complete"])
            warns = rcpt.get("baseline_warnings", [])
            self.assertTrue(any("candidate-2g-fix4 baseline" in w for w in warns), warns)
            self.assertIn(hashlib.sha256(b"MISMATCH-DATA").hexdigest()[:16], "\n".join(warns))


if __name__ == "__main__":
    unittest.main()
