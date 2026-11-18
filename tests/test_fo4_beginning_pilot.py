"""Unit tests for `fo4sf.beginning_pilot` and `docs/testing/fo4-beginning-pilot.md`."""
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
    evaluate_beginning_logs,
    verify_bundle_beginning_readiness,
)


def _dummy_tes4() -> bytes:
    return b"TES4" + struct.pack("<IIII", 0, 1, 0, 0) + b"\x00\x00\x00\x00"


class BeginningPilotTests(unittest.TestCase):
    def _build_synthetic_bundle(self, root: Path) -> Path:
        bundle = root / "candidate"
        (bundle / "Data" / "Scripts").mkdir(parents=True, exist_ok=True)
        req_plugins = {
            "FO4ActorRaider.esm",
            "FO4TerrainCore.esm",
            "FO4SFMission.esm",
            "FO4SFVaultGearDoor.esm",
            "FO4SFExitLift.esm",
            "FO4SFNewGame.esm",
        }
        for p in sorted(req_plugins):
            (bundle / p).write_bytes(_dummy_tes4())

        for sc in (
            "FO4SF_NewGameQuest.pex",
            "FO4SF_NewGameLooks.pex",
            "FO4SF_Min00Quest.pex",
            "FO4SF_COMPreston.pex",
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
            self.assertEqual(len(ok_res["steps"]), 7)

            first_wem = sorted((bundle / "Data" / Path(CODSWORTH_VOICE_DIR_REL)).glob("*.wem"))[0]
            first_wem.unlink()
            bad_res = verify_bundle_beginning_readiness(str(bundle))
            self.assertFalse(bad_res["ok"])
            self.assertEqual(bad_res["steps"]["B5_codsworth_sanctuary"]["status"], "FAIL")

    def test_real_vault_session_excerpt_catches_surface_exit_fail_and_ignores_init_keeper_load(self) -> None:
        """Sanitized real log lines (16 Nov 5-quest build + surface_cell_not_core exit failure)."""
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            ng_log = tdir / "fo4sf_newgame.0.log"
            ms_log = tdir / "fo4sf_mission.0.log"

            ng_log.write_text(
                "[20:58:48] FO4SF_NewGame log opened (PC-64)\n"
                "[20:58:48] FO4SF_NEWGAME rt=43.715004 init holdoff=5 vault=fo4port.esm:4920 anchor_temporary=false core=fo4terraincore.esm:685915\n"
                "[20:58:52] FO4SF_NEWGAME rt=47.419003 enter vault ok=true pos=9.142858 -6.614286 -0.851672 target=9.142858 -6.614286 -0.728571 cell=[Cell <FO4Port_Vault111Cryo (020011F3)>]\n"
                "[20:58:52] FO4SF_NEWGAME rt=47.446003 hold-off pass 1 stopped=0 of 5\n"
                "[20:58:54] FO4SF_NEWGAME rt=49.963001 hold-off pass 2 stopped=2 of 5\n"
                "[20:58:54] FO4SF_NEWGAME rt=50.095001 stage 10\n"
                "[20:58:56] FO4SF_NEWGAME rt=51.496002 pod settle ok=true pos=9.142858 -6.614286 -0.851672 dx=0.000000 dy=0.000000 drop=0.123100\n"
                "[20:59:28] FO4SF_NEWGAME rt=83.315002 stage 20\n"
                "[21:10:57] FO4SF_NEWGAME rt=772.392029 cog door open_state before=2 after=2\n"
                "[21:10:57] FO4SF_NEWGAME rt=772.428040 stage 30\n"
                "[21:11:58] FO4SF_NEWGAME rt=833.964050 elevator prompt button=0\n"
                "[21:12:01] FO4SF_NEWGAME rt=836.391052 surface moveto pos=-1275.313965 1305.275757 119.384842 world=[WorldSpace <MarsPlanetWorld137917136288 (FF0096A4)>] moves=1\n"
                "[21:12:03] FO4SF_NEWGAME rt=838.903015 exit failed reason=surface_cell_not_core stage=30\n",
                encoding="utf-8",
            )
            ms_log.write_text(
                "[20:58:52] fo4sf_mission log opened (PC-64)\n"
                "[20:58:52] FO4SF_MISSION rt=47.913002 keeper init codsworth=[Actor <FO4SF_CodsworthREF (06000811)>]\n"
                "[20:58:52] FO4SF_MISSION rt=47.913002 init raiders=5\n"
                "[20:58:52] FO4SF_MISSION rt=47.913002 stage 10\n"
                "[20:58:52] FO4SF_MISSION rt=47.913002 keeper load Preston d=340282346638528859811704183484516925440.000000 off=2954.653564 state=None moves=0 held=false holds=0 at -811.142883 1002.457153 89.085716 disabled=false dead=false fails=0 player=9.142858 -6.614286 -0.851672 interior=true\n"
                "[20:58:52] FO4SF_MISSION rt=47.913002 keeper load Codsworth d=340282346638528859811704183484516925440.000000 off=2954.656738 state=None moves=0 held=false holds=0 at -1146.709106 1293.836548 111.734100 disabled=false dead=false fails=0 player=9.142858 -6.614286 -0.851672 interior=true\n"
                "[21:00:31] FO4SF_MISSION rt=146.311005 keeper status Codsworth d=340282346638528859811704183484516925440.000000 off=2954.656738 state=off, player inside moves=0 held=false holds=0 at -1146.709106 1293.836548 111.734100 disabled=false dead=false fails=0 player=10.048894 -9.465561 -0.867304 interior=true\n",
                encoding="utf-8",
            )

            res = evaluate_beginning_logs(str(ng_log), str(ms_log))
            self.assertFalse(res["ok"])
            self.assertFalse(res["all_pass"])
            # B1 dynamically accepts 2/5 (3 non-running MQ101 quests) instead of hardcoded 162
            self.assertEqual(res["steps"]["B1_pod"]["status"], "PASS")
            self.assertEqual(res["steps"]["B2_gear_door"]["status"], "PASS")
            # No 'ascent carried confirmed' -> UNTESTED
            self.assertEqual(res["steps"]["B3_exit_lift"]["status"], "UNTESTED")
            # Real 'exit failed reason=surface_cell_not_core' -> FAIL
            self.assertEqual(res["steps"]["B4_surface_landing"]["status"], "FAIL")
            self.assertIn("surface_cell_not_core", res["steps"]["B4_surface_landing"]["detail"])
            # Init 'keeper load Codsworth' must NOT falsely pass B5!
            self.assertEqual(res["steps"]["B5_codsworth_sanctuary"]["status"], "UNTESTED")
            self.assertEqual(res["steps"]["B6_concord_raiders"]["status"], "UNTESTED")
            self.assertEqual(res["steps"]["B7_preston_turnin"]["status"], "UNTESTED")

    def test_real_17nov_pod_and_codsworth_excerpts_plus_dynamic_hold_thresholds(self) -> None:
        """Sanitized real 17 Nov log lines (162/165 and 34/37 hold-off + proximity Codsworth relocation)."""
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            ng_log = tdir / "fo4sf_newgame.0.log"
            ms_log = tdir / "fo4sf_mission.0.log"

            ng_log.write_text(
                "[13:27:02] FO4SF_NEWGAME rt=58.415001 hold-off pass 1 stopped=0 of 165\n"
                "[13:27:15] FO4SF_NEWGAME rt=71.081001 hold-off pass 2 stopped=162 of 165\n"
                "[13:27:15] FO4SF_NEWGAME rt=71.214005 stage 10\n"
                "[13:27:17] FO4SF_NEWGAME rt=72.547005 pod settle ok=true pos=9.142858 -6.614286 -0.851672 dx=0.000000 dy=0.000000 drop=0.123100\n"
                "[13:27:36] FO4SF_NEWGAME rt=92.191002 stage 20\n",
                encoding="utf-8",
            )
            ms_log.write_text(
                "[20:26:41] FO4SF_MISSION rt=64.596001 stage 10\n"
                "[20:26:41] FO4SF_MISSION rt=64.596001 keeper load Codsworth d=340282346638528859811704183484516925440.000000 off=2954.656738 state=None moves=0 held=false holds=0 at -1146.709106 1293.836548 111.734100 disabled=false dead=false fails=0 player=9.193993 -3.120838 -0.384664 interior=true\n"
                "[20:30:04] FO4SF_MISSION rt=225.839005 moved Codsworth to -2346.708984 -1406.162964 111.776276 target -2346.708984 -1406.162964 111.734001 before=340282346638528859811704183484516925440.000000 off=2954.656738 d=215.724350 failed=false by=keeper\n"
                "[20:30:04] FO4SF_MISSION rt=225.970016 hold Codsworth by=keeper off=0.042274 ok=true\n",
                encoding="utf-8",
            )
            res = evaluate_beginning_logs(str(ng_log), str(ms_log))
            self.assertTrue(res["ok"])
            self.assertEqual(res["steps"]["B1_pod"]["status"], "PASS")
            self.assertEqual(res["steps"]["B5_codsworth_sanctuary"]["status"], "PASS")

            # Under-stopped 199-quest list (e.g. 180 of 199) must FAIL B1
            ng_log.write_text(
                "FO4SF_NEWGAME rt=10.0 hold-off pass 2 stopped=180 of 199\n"
                "FO4SF_NEWGAME rt=11.0 stage 10\n"
                "FO4SF_NEWGAME rt=12.0 pod settle ok=true pos=9.14 -6.61 -0.85\n",
                encoding="utf-8",
            )
            bad_hold = evaluate_beginning_logs(str(ng_log), None)
            self.assertFalse(bad_hold["ok"])
            self.assertEqual(bad_hold["steps"]["B1_pod"]["status"], "FAIL")

    def test_b3_lift_and_b4_fallback_negative_cases(self) -> None:
        """Stage 40 alone does NOT pass B3; lift_ failures fail B3; fell z= fallback fails B4."""
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            ng_log = tdir / "fo4sf_newgame.0.log"

            # Stage 40 + Stage 200 WITHOUT 'ascent carried confirmed' -> B3 UNTESTED, B4 PASS
            ng_log.write_text(
                "FO4SF_NEWGAME rt=10.0 hold-off pass 2 stopped=195 of 199\n"
                "FO4SF_NEWGAME rt=11.0 stage 10\n"
                "FO4SF_NEWGAME rt=12.0 pod settle ok=true pos=9.14 -6.61 -0.85\n"
                "FO4SF_NEWGAME rt=20.0 stage 30\n"
                "FO4SF_NEWGAME rt=30.0 stage 40\n"
                "FO4SF_NEWGAME rt=34.0 landed z=128.11 confirmed=True fallback=False world= Commonwealth\n"
                "FO4SF_NEWGAME rt=34.1 stage 200\n",
                encoding="utf-8",
            )
            no_lift = evaluate_beginning_logs(str(ng_log), None)
            self.assertEqual(no_lift["steps"]["B3_exit_lift"]["status"], "UNTESTED")
            self.assertEqual(no_lift["steps"]["B4_surface_landing"]["status"], "PASS")

            # 'ascent carried confirmed' followed by 'exit failed reason=lift_rider_left_before_arrival' -> B3 FAIL
            ng_log.write_text(
                "FO4SF_NEWGAME rt=10.0 hold-off pass 2 stopped=195 of 199\n"
                "FO4SF_NEWGAME rt=11.0 stage 10\n"
                "FO4SF_NEWGAME rt=12.0 pod settle ok=true pos=9.14 -6.61 -0.85\n"
                "FO4SF_NEWGAME rt=20.0 stage 30\n"
                "FO4SF_NEWGAME rt=30.0 ascent carried confirmed elapsed=9.85 z=19.85\n"
                "FO4SF_NEWGAME rt=30.1 exit failed reason=lift_rider_left_before_arrival stage=30\n",
                encoding="utf-8",
            )
            lift_fail = evaluate_beginning_logs(str(ng_log), None)
            self.assertFalse(lift_fail["ok"])
            self.assertEqual(lift_fail["steps"]["B3_exit_lift"]["status"], "FAIL")
            self.assertIn("lift_rider_left_before_arrival", lift_fail["steps"]["B3_exit_lift"]["detail"])

            # Fallback landing ('fell z=...: fallback pos=...') reaching stage 200 MUST still FAIL B4!
            ng_log.write_text(
                "FO4SF_NEWGAME rt=10.0 hold-off pass 2 stopped=195 of 199\n"
                "FO4SF_NEWGAME rt=11.0 stage 10\n"
                "FO4SF_NEWGAME rt=12.0 pod settle ok=true pos=9.14 -6.61 -0.85\n"
                "FO4SF_NEWGAME rt=20.0 stage 30\n"
                "FO4SF_NEWGAME rt=30.0 ascent carried confirmed elapsed=9.85 z=19.85\n"
                "FO4SF_NEWGAME rt=33.0 stage 40\n"
                "FO4SF_NEWGAME rt=36.5 fell z=118.20: fallback pos=-2475.31 -1394.72 120.38\n"
                "FO4SF_NEWGAME rt=39.5 landed z=120.38 confirmed=True fallback=True world=Commonwealth\n"
                "FO4SF_NEWGAME rt=39.6 stage 200\n",
                encoding="utf-8",
            )
            fb_fail = evaluate_beginning_logs(str(ng_log), None)
            self.assertFalse(fb_fail["ok"])
            self.assertEqual(fb_fail["steps"]["B3_exit_lift"]["status"], "PASS")
            self.assertEqual(fb_fail["steps"]["B4_surface_landing"]["status"], "FAIL")
            self.assertIn("fell z=", fb_fail["steps"]["B4_surface_landing"]["detail"])

    def test_in_progress_vs_relocation_failure_and_full_pass_cli(self) -> None:
        """Mid-fight stage 20 / stage 30 are IN_PROGRESS (not FAIL); real failed=true / keeper gave up FAIL."""
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            ng_log = tdir / "fo4sf_newgame.0.log"
            ms_log = tdir / "fo4sf_mission.0.log"

            ng_log.write_text(
                "FO4SF_NEWGAME rt=10.0 hold-off pass 2 stopped=195 of 199\n"
                "FO4SF_NEWGAME rt=11.0 stage 10\n"
                "FO4SF_NEWGAME rt=12.0 pod settle ok=true pos=9.14 -6.61 -0.85\n"
                "FO4SF_NEWGAME rt=20.0 stage 30\n"
                "FO4SF_NEWGAME rt=30.0 ascent carried confirmed elapsed=9.85 z=19.85\n"
                "FO4SF_NEWGAME rt=33.0 stage 40\n"
                "FO4SF_NEWGAME rt=36.5 landed z=128.11 confirmed=True fallback=False world=Commonwealth\n"
                "FO4SF_NEWGAME rt=36.6 stage 200\n",
                encoding="utf-8",
            )

            # Mid-fight stage 20 -> IN_PROGRESS, ok=True, all_pass=False
            ms_log.write_text(
                "[14:00:00] FO4SF_MISSION rt=10.0 init raiders=5\n"
                "[14:00:00] FO4SF_MISSION rt=10.0 stage 10\n"
                "[14:01:00] FO4SF_MISSION rt=70.0 hold Codsworth by=keeper off=0.4 ok=true\n"
                "[14:03:00] FO4SF_MISSION rt=190.0 stage 20\n",
                encoding="utf-8",
            )
            mid_b6 = evaluate_beginning_logs(str(ng_log), str(ms_log))
            self.assertTrue(mid_b6["ok"])
            self.assertFalse(mid_b6["all_pass"])
            self.assertEqual(mid_b6["steps"]["B6_concord_raiders"]["status"], "IN_PROGRESS")

            # Post-fight stage 30 awaiting turn-in -> B6 PASS, B7 IN_PROGRESS; CLI --require-all-pass exits 2
            ms_log.write_text(
                ms_log.read_text(encoding="utf-8")
                + "[14:04:00] FO4SF_MISSION rt=250.0 stage 30\n",
                encoding="utf-8",
            )
            mid_b7 = evaluate_beginning_logs(str(ng_log), str(ms_log))
            self.assertTrue(mid_b7["ok"])
            self.assertFalse(mid_b7["all_pass"])
            self.assertEqual(mid_b7["steps"]["B6_concord_raiders"]["status"], "PASS")
            self.assertEqual(mid_b7["steps"]["B7_preston_turnin"]["status"], "IN_PROGRESS")

            cli_script = ROOT / "scripts" / "testing" / "check_beginning_pilot.py"
            r_no_req = subprocess.run(
                [sys.executable, str(cli_script), "check-logs", "--newgame-log", str(ng_log), "--mission-log", str(ms_log)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_no_req.returncode, 0, r_no_req.stdout + r_no_req.stderr)

            r_req = subprocess.run(
                [
                    sys.executable,
                    str(cli_script),
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
            self.assertEqual(r_req.returncode, 2)

            # Real FO4SF_Min00Quest relocation budget exhaustion (10 'moved raider ... failed=true') -> B6 FAIL
            fail_lines = "".join(
                f"[14:03:{10 + i:02d}] FO4SF_MISSION rt={200 + i}.0 moved raider 0 to 0 0 0 target -2029 -1698 88 before=2954 d=2954 failed=true\n"
                for i in range(10)
            )
            ms_log.write_text(
                "[14:00:00] FO4SF_MISSION rt=10.0 stage 10\n"
                "[14:03:00] FO4SF_MISSION rt=190.0 stage 20\n"
                + fail_lines,
                encoding="utf-8",
            )
            reloc_fail = evaluate_beginning_logs(str(ng_log), str(ms_log))
            self.assertFalse(reloc_fail["ok"])
            self.assertEqual(reloc_fail["steps"]["B6_concord_raiders"]["status"], "FAIL")

            # Full B1..B7 completion -> all 7 PASS; door hold after follow -> B7 FAIL
            ms_log.write_text(
                "[14:00:00] FO4SF_MISSION rt=10.0 init raiders=5\n"
                "[14:00:00] FO4SF_MISSION rt=10.0 stage 10\n"
                "[14:01:00] FO4SF_MISSION rt=70.0 hold Codsworth by=keeper off=0.4 ok=true\n"
                "[14:03:00] FO4SF_MISSION rt=190.0 stage 20\n"
                "[14:04:00] FO4SF_MISSION rt=250.0 stage 30\n"
                "[14:04:10] FO4SF_MISSION rt=260.0 stage 40\n"
                "[14:04:10] FO4SF_MISSION rt=260.0 reward credits=100\n"
                "[14:04:11] FO4SF_MISSION rt=261.0 stage 200\n",
                encoding="utf-8",
            )
            full = evaluate_beginning_logs(str(ng_log), str(ms_log))
            self.assertTrue(full["ok"])
            self.assertTrue(full["all_pass"])
            for spec in BEGINNING_STEPS:
                self.assertEqual(full["steps"][spec.step_id]["status"], "PASS")

            ms_log.write_text(
                ms_log.read_text(encoding="utf-8")
                + "[14:05:00] FO4SF_MISSION rt=310.0 follow preston test-only alias=Preston filled=1 linked=player released=True quest=2069\n"
                + "[14:05:05] FO4SF_MISSION rt=315.0 hold preston by=keeper off=0.5 ok=True\n",
                encoding="utf-8",
            )
            reg = evaluate_beginning_logs(str(ng_log), str(ms_log))
            self.assertFalse(reg["ok"])
            self.assertEqual(reg["steps"]["B7_preston_turnin"]["status"], "FAIL")

    def test_docs_cover_labels_placeholders_and_pr803_attribution(self) -> None:
        pilot_doc = (ROOT / "docs" / "testing" / "fo4-beginning-pilot.md").read_text(encoding="utf-8")
        card_doc = (ROOT / "docs" / "testing" / "core-candidate-pc-card.md").read_text(encoding="utf-8")
        for spec in BEGINNING_STEPS:
            self.assertIn(spec.step_id, pilot_doc)
        for label in ("REACHABLE", "TEST-STATION", "RECORDS ONLY", "TOOLING", "NOT BUILT"):
            self.assertIn(label, pilot_doc)
            self.assertIn(label, card_doc)
        self.assertIn("ascent carried confirmed", pilot_doc)
        self.assertIn("FinishSurface", pilot_doc)
        self.assertIn("#803", pilot_doc)
        self.assertIn("placeholder", pilot_doc.lower())
        self.assertIn("placeholder", card_doc.lower())
        for step_num in ("Step 13", "Step 14", "Step 15"):
            self.assertIn(step_num, card_doc)


if __name__ == "__main__":
    unittest.main()
