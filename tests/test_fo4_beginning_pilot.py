"""Unit tests for `fo4sf.beginning_pilot`, `scripts/testing/check_beginning_pilot.py`, and `docs/testing/fo4-beginning-pilot.md` (`V1`).

Per Rule R4, all log fixtures are hand-written FO4SF state lines only (zero copied game logs or PC paths).
"""
from __future__ import annotations

import json
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fo4sf.beginning_pilot import (  # noqa: E402
    BEGINNING_STEPS,
    CODSWORTH_NIF_REL,
    CODSWORTH_VOICE_DIR_REL,
    MIN_CODSWORTH_WEMS,
    NOT_BUILT_MUSEUM_CONTENT,
    evaluate_beginning_logs,
    verify_bundle_beginning_readiness,
)


def _dummy_tes4() -> bytes:
    return b"TES4" + struct.pack("<IIII", 0, 1, 0, 0) + b"\x00\x00\x00\x00"


def _handwritten_newgame_lines() -> list[str]:
    return [
        "FO4SF_NEWGAME rt=10.0 mode choice mode=story survival=0",
        "FO4SF_NEWGAME rt=12.0 hold-off pass 1 stopped=60 of 199",
        "FO4SF_NEWGAME rt=14.0 hold-off pass 2 stopped=136 of 199",
        "FO4SF_NEWGAME rt=14.5 stage 10",
        "FO4SF_NEWGAME rt=15.0 pod settle ok=true drop=0.12",
        "FO4SF_NEWGAME rt=20.0 stage 20",
        "FO4SF_NEWGAME rt=30.0 pistol picked count=1",
        "FO4SF_NEWGAME rt=35.0 pipboy pickup equipped flag=1",
        "FO4SF_NEWGAME rt=42.0 cog door console activated ref=0x000808 before=3 after=2",
        "FO4SF_NEWGAME rt=42.5 stage 30",
        "FO4SF_NEWGAME rt=70.0 elevator prompt button=1",
        "FO4SF_NEWGAME rt=75.0 special set S=6 P=6 E=6 C=5 I=6 A=6 L=5",
        "FO4SF_NEWGAME rt=78.0 elevator prompt button=0",
        "FO4SF_NEWGAME rt=79.0 ascent play accepted=true rise=21.6 seconds=9.87",
        "FO4SF_NEWGAME rt=83.0 map setup done markers=309 elapsed=2.1",
        "FO4SF_NEWGAME rt=89.0 ascent carried confirmed elapsed=9.9 z=19.81",
        "FO4SF_NEWGAME rt=94.0 surface setposition ok=true core_cell=true",
        "FO4SF_NEWGAME rt=94.1 stage 40",
        "FO4SF_NEWGAME rt=98.0 landed z=127.45 confirmed=True fallback=false",
        "FO4SF_NEWGAME rt=98.2 stage 200",
    ]


def _handwritten_mission_lines() -> list[str]:
    return [
        "FO4SF_MISSION rt=100.0 mission gate mode=1 started=true",
        "FO4SF_MISSION rt=100.1 init raiders=5",
        "FO4SF_MISSION rt=120.0 hold codsworth by=keeper off=0.2 ok=true",
        "FO4SF_MISSION rt=135.0 min00 given by=codsworth",
        "FO4SF_MISSION rt=135.1 stage 10",
        "FO4SF_MISSION rt=135.2 codsworth talk end -> min00 stage 10",
        "FO4SF_MISSION rt=135.3 codsworth01 complete choices=4 concord_pointed=true",
        "FO4SF_MISSION rt=210.0 startcombat raider 0 d=48.0",
        "FO4SF_MISSION rt=210.1 stage 20",
        "FO4SF_MISSION rt=225.0 reload mission stage=20 relocate_fails=0",
        "FO4SF_MISSION rt=290.0 wfc01 raider cleared absent id=2055 raider=4 elapsed=61.0",
        "FO4SF_MISSION rt=291.0 stage 30",
        "FO4SF_MISSION rt=305.0 preston activated at stage 30",
        "FO4SF_MISSION rt=318.0 preston talk end info=0x092A -> stage 40",
        "FO4SF_MISSION rt=318.1 stage 40",
        "FO4SF_MISSION rt=318.2 reward credits=100",
        "FO4SF_MISSION rt=319.0 stage 200",
        "FO4SF_MISSION rt=319.5 min01 stage 10 objective bench",
        "FO4SF_MISSION rt=380.0 min01 bench activated -> stage 100",
    ]


class BeginningPilotTests(unittest.TestCase):
    def _build_synthetic_bundle(self, root: Path) -> Path:
        bundle = root / "candidate"
        (bundle / "Data" / "Scripts").mkdir(parents=True, exist_ok=True)
        req_plugins = {
            "FO4SFCoreValues.esm",
            "FO4ActorRaider.esm",
            "FO4TerrainCore.esm",
            "FO4SFMission.esm",
            "FO4SFVaultGearDoor.esm",
            "FO4SFExitLift.esm",
            "FO4SFNewGame.esm",
            "FO4SFProgression.esm",
        }
        for p in sorted(req_plugins):
            (bundle / p).write_bytes(_dummy_tes4())

        for sc in (
            "FO4SF_NewGameQuest.pex",
            "FO4SF_NewGameLooks.pex",
            "FO4SF_ProgressionQuest.pex",
            "FO4SF_Min00Quest.pex",
            "FO4SF_COMPreston.pex",
            "FO4SF_Codsworth01Quest.pex",
            "FO4SF_Sanctuary01Quest.pex",
        ):
            (bundle / "Data" / "Scripts" / sc).write_bytes(b"PEX_SYNTHETIC_BINARY_PAYLOAD")

        nif = bundle / "Data" / Path(CODSWORTH_NIF_REL)
        nif.parent.mkdir(parents=True, exist_ok=True)
        nif.write_bytes(b"NIF_CODSWORTH")

        vdir = bundle / "Data" / Path(CODSWORTH_VOICE_DIR_REL)
        vdir.mkdir(parents=True, exist_ok=True)
        for idx in range(MIN_CODSWORTH_WEMS):
            (vdir / f"00f4c{idx:03x}.wem").write_bytes(b"RIFF_WEM")

        (bundle / "bundle_plan.json").write_text(
            json.dumps(
                {
                    "plugins": sorted(req_plugins),
                    "components": {
                        "cog_door": {"outputs": {"FO4SFVaultGearDoor.esm": "aa", "Data/meshes/door.nif": "bb"}},
                        "exit_lift": {"outputs": {"FO4SFExitLift.esm": "cc", "Data/meshes/lift.nif": "dd"}},
                    },
                }
            ),
            encoding="utf-8",
        )
        return bundle

    def test_verify_bundle_beginning_readiness_passes_and_catches_gaps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bundle = self._build_synthetic_bundle(Path(tmp))
            ok_res = verify_bundle_beginning_readiness(str(bundle))
            self.assertTrue(ok_res["ok"], ok_res["problems"])
            self.assertEqual(len(ok_res["steps"]), 8)

            first_wem = sorted((bundle / "Data" / Path(CODSWORTH_VOICE_DIR_REL)).glob("*.wem"))[0]
            first_wem.unlink()
            bad_res = verify_bundle_beginning_readiness(str(bundle))
            self.assertFalse(bad_res["ok"])
            self.assertEqual(bad_res["steps"]["B5_codsworth_sanctuary"]["status"], "FAIL")

    def test_full_handwritten_story_walk_passes_all_eight_steps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            ng_log = tdir / "fo4sf_newgame.0.log"
            ms_log = tdir / "fo4sf_mission.0.log"
            ng_log.write_text("\n".join(_handwritten_newgame_lines()) + "\n", encoding="utf-8")
            ms_log.write_text("\n".join(_handwritten_mission_lines()) + "\n", encoding="utf-8")

            res = evaluate_beginning_logs(str(ng_log), str(ms_log))
            self.assertTrue(res["ok"], res)
            self.assertTrue(res["all_pass"], res)
            for spec in BEGINNING_STEPS:
                self.assertEqual(res["steps"][spec.step_id]["status"], "PASS", spec.step_id)

    def test_negative_special_skipped_and_wrong_sum_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            ng_log = tdir / "fo4sf_newgame.0.log"
            ms_log = tdir / "fo4sf_mission.0.log"
            ms_log.write_text("\n".join(_handwritten_mission_lines()) + "\n", encoding="utf-8")

            # 1. 'special skipped' must FAIL B3_exit_lift
            skipped_lines = [
                "FO4SF_NEWGAME rt=76.0 special skipped: left the vault with SPECIAL unset"
                if "special set" in ln
                else ln
                for ln in _handwritten_newgame_lines()
            ]
            ng_log.write_text("\n".join(skipped_lines) + "\n", encoding="utf-8")
            r_skip = evaluate_beginning_logs(str(ng_log), str(ms_log))
            self.assertFalse(r_skip["ok"])
            self.assertEqual(r_skip["steps"]["B3_exit_lift"]["status"], "FAIL")

            # 2. 28-point S.P.E.C.I.A.L. sum (instead of 40) must FAIL B3_exit_lift
            sum28_lines = [
                "FO4SF_NEWGAME rt=75.0 special set S=4 P=4 E=4 C=4 I=4 A=4 L=4"
                if "special set" in ln
                else ln
                for ln in _handwritten_newgame_lines()
            ]
            ng_log.write_text("\n".join(sum28_lines) + "\n", encoding="utf-8")
            r_sum = evaluate_beginning_logs(str(ng_log), str(ms_log))
            self.assertFalse(r_sum["ok"])
            self.assertEqual(r_sum["steps"]["B3_exit_lift"]["status"], "FAIL")

            # 3. Missing 'map setup done' must FAIL B3_exit_lift
            no_map = [ln for ln in _handwritten_newgame_lines() if "map setup done" not in ln]
            ng_log.write_text("\n".join(no_map) + "\n", encoding="utf-8")
            r_map = evaluate_beginning_logs(str(ng_log), str(ms_log))
            self.assertFalse(r_map["ok"])
            self.assertEqual(r_map["steps"]["B3_exit_lift"]["status"], "FAIL")

    def test_negative_missing_console_activation_pipboy_order_and_pistol_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            ng_log = tdir / "fo4sf_newgame.0.log"
            ms_log = tdir / "fo4sf_mission.0.log"
            ms_log.write_text("\n".join(_handwritten_mission_lines()) + "\n", encoding="utf-8")

            # 1. Missing 'cog door console activated' when reaching stage 30 must FAIL B2_gear_door
            no_console = [
                "FO4SF_NEWGAME rt=42.0 cog door open_state before=3 after=2"
                if "cog door console activated" in ln
                else ln
                for ln in _handwritten_newgame_lines()
            ]
            ng_log.write_text("\n".join(no_console) + "\n", encoding="utf-8")
            r_no_con = evaluate_beginning_logs(str(ng_log), str(ms_log))
            self.assertFalse(r_no_con["ok"])
            self.assertEqual(r_no_con["steps"]["B2_gear_door"]["status"], "FAIL")

            # 2. Direct door open ('cog door opened directly') must FAIL B2_gear_door
            direct = _handwritten_newgame_lines() + ["FO4SF_NEWGAME rt=41.0 cog door opened directly"]
            ng_log.write_text("\n".join(direct) + "\n", encoding="utf-8")
            r_dir = evaluate_beginning_logs(str(ng_log), str(ms_log))
            self.assertFalse(r_dir["ok"])
            self.assertEqual(r_dir["steps"]["B2_gear_door"]["status"], "FAIL")

            # 3. Console activated before 'pipboy pickup equipped flag=1' must FAIL B2_gear_door
            swapped = []
            for ln in _handwritten_newgame_lines():
                if "pipboy pickup equipped flag=1" in ln:
                    continue
                swapped.append(ln)
                if "cog door console activated" in ln:
                    swapped.append("FO4SF_NEWGAME rt=42.1 pipboy pickup equipped flag=1")
            ng_log.write_text("\n".join(swapped) + "\n", encoding="utf-8")
            r_ord = evaluate_beginning_logs(str(ng_log), str(ms_log))
            self.assertFalse(r_ord["ok"])
            self.assertEqual(r_ord["steps"]["B2_gear_door"]["status"], "FAIL")

            # 4. Missing 'pistol picked' before stage 30 must FAIL B2_gear_door
            no_pistol = [ln for ln in _handwritten_newgame_lines() if "pistol picked" not in ln]
            ng_log.write_text("\n".join(no_pistol) + "\n", encoding="utf-8")
            r_pis = evaluate_beginning_logs(str(ng_log), str(ms_log))
            self.assertFalse(r_pis["ok"])
            self.assertEqual(r_pis["steps"]["B2_gear_door"]["status"], "FAIL")

    def test_negative_stage40_fallback_warfare_gate_and_early_vault_mission_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            ng_log = tdir / "fo4sf_newgame.0.log"
            ms_log = tdir / "fo4sf_mission.0.log"
            ng_log.write_text("\n".join(_handwritten_newgame_lines()) + "\n", encoding="utf-8")

            # 1. 'stage 40 by=fallback' counts as FAIL for REACHABLE on B7_preston_turnin
            fb_lines = [
                "FO4SF_MISSION rt=318.0 stage 40 by=fallback"
                if "preston talk end" in ln
                else ln
                for ln in _handwritten_mission_lines()
            ]
            ms_log.write_text("\n".join(fb_lines) + "\n", encoding="utf-8")
            r_fb = evaluate_beginning_logs(str(ng_log), str(ms_log))
            self.assertFalse(r_fb["ok"])
            self.assertEqual(r_fb["steps"]["B7_preston_turnin"]["status"], "FAIL")

            # 2. Warfare gate ('mission gate mode=2 started=false') fails Story B5_codsworth_sanctuary
            wf_lines = ["FO4SF_MISSION rt=100.0 mission gate mode=2 started=false"]
            ms_log.write_text("\n".join(wf_lines) + "\n", encoding="utf-8")
            r_wf = evaluate_beginning_logs(str(ng_log), str(ms_log))
            self.assertFalse(r_wf["ok"])
            self.assertEqual(r_wf["steps"]["B5_codsworth_sanctuary"]["status"], "FAIL")

            # 3. Mission starting in Vault 111 before NewGame stage 200 (rt=40.0 < rt=98.2) fails B5
            early_lines = [ln.replace("rt=100.0", "rt=40.0", 1) for ln in _handwritten_mission_lines()]
            ms_log.write_text("\n".join(early_lines) + "\n", encoding="utf-8")
            r_early = evaluate_beginning_logs(str(ng_log), str(ms_log))
            self.assertFalse(r_early["ok"])
            self.assertEqual(r_early["steps"]["B5_codsworth_sanctuary"]["status"], "FAIL")

    def test_cli_check_bundle_and_check_logs_exit_codes(self) -> None:
        cli = ROOT / "scripts" / "testing" / "check_beginning_pilot.py"
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            bundle = self._build_synthetic_bundle(tdir)
            r_bun = subprocess.run(
                [sys.executable, str(cli), "check-bundle", "--bundle-dir", str(bundle)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_bun.returncode, 0, r_bun.stdout + r_bun.stderr)

            ng_log = tdir / "ng.log"
            ms_log = tdir / "ms.log"
            ng_log.write_text("\n".join(_handwritten_newgame_lines()) + "\n", encoding="utf-8")
            ms_log.write_text("\n".join(_handwritten_mission_lines()[:-1]) + "\n", encoding="utf-8")

            # Without --require-all-pass, IN_PROGRESS on B8 exits 0; with --require-all-pass, exits 2
            r_prog = subprocess.run(
                [sys.executable, str(cli), "check-logs", "--newgame-log", str(ng_log), "--mission-log", str(ms_log)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_prog.returncode, 0, r_prog.stdout)
            r_req = subprocess.run(
                [
                    sys.executable,
                    str(cli),
                    "check-logs",
                    "--newgame-log",
                    str(ng_log),
                    "--mission-log",
                    str(ms_log),
                    "--require-all-pass",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_req.returncode, 2, r_req.stdout)

            ms_log.write_text("\n".join(_handwritten_mission_lines()) + "\n", encoding="utf-8")
            r_ok = subprocess.run(
                [
                    sys.executable,
                    str(cli),
                    "check-logs",
                    "--newgame-log",
                    str(ng_log),
                    "--mission-log",
                    str(ms_log),
                    "--require-all-pass",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_ok.returncode, 0, r_ok.stdout)

    def test_docs_cover_labels_and_not_built_museum_content(self) -> None:
        pilot_doc = (ROOT / "docs" / "testing" / "fo4-beginning-pilot.md").read_text(encoding="utf-8")
        for spec in BEGINNING_STEPS:
            self.assertIn(spec.step_id, pilot_doc)
        for label in ("REACHABLE", "TEST-STATION", "RECORDS ONLY", "TOOLING", "NOT BUILT"):
            self.assertIn(label, pilot_doc)
        for cut_item in NOT_BUILT_MUSEUM_CONTENT:
            self.assertIn(cut_item, pilot_doc.lower())
        self.assertIn("placeholder", pilot_doc.lower())


if __name__ == "__main__":
    unittest.main()
