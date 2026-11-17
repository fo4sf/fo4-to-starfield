"""Synthetic cross-platform unit tests for the 60-minute soak log reader and phone report."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fo4sf.testing.soak_report import (  # noqa: E402
    PHONE_MAX_LINES,
    PHONE_MAX_WIDTH,
    analyze_session,
    format_phone_report,
)


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class SoakReportTests(unittest.TestCase):
    def _populate_clean_60min_session(self, base: Path) -> None:
        # Papyrus.0.log spanning 60m 05s with benign vanilla startup noise only
        papyrus_lines = [
            "[12:00:00] Papyrus log opened (PC-64)",
            "[12:00:00] Update budget: 1.200000ms (Extra tasklet budget: 1.200000ms, Load screen budget: 500.000000ms)",
            '[12:00:02] Cannot open store for class "TestVanillaMissingScript", missing file?',
            "[12:00:02] error: Unable to bind script TestVanillaMissingScript to  (001E9B90) because their base types do not match",
            "[13:00:05] Log closed",
        ]
        _write(base / "Logs" / "Script" / "Papyrus.0.log", "\n".join(papyrus_lines) + "\n")

        # FO4SF_NewGame.0.log: clean hold-off + stage progression 10 -> 20 -> 30 -> 40 -> 200 with steady 6s status ticks
        ng_lines = [
            "[12:00:10] FO4SF_NewGame log opened (PC-64)",
            "[12:00:10] FO4SF_NEWGAME rt=10.0 init holdoff=165 vault=fo4port.esm:4920",
            "[12:00:12] FO4SF_NEWGAME rt=12.0 hold-off pass 1 stopped=0 of 165",
            "[12:00:15] FO4SF_NEWGAME rt=15.0 held off [mq00questscript <MQ00 (00005790)>] running_after=false pass=2",
            "[12:00:16] FO4SF_NEWGAME rt=16.0 hold-off pass 2 stopped=162 of 165",
            "[12:00:16] FO4SF_NEWGAME rt=16.5 stage 10",
            "[12:00:22] FO4SF_NEWGAME rt=22.5 status stage=10 pos=0 0 0 cell=Vault world=None",
            "[12:00:28] FO4SF_NEWGAME rt=28.5 stage 20",
            "[12:00:28] FO4SF_NEWGAME rt=28.6 status stage=20 pos=0 0 0 cell=Vault world=None",
            "[12:00:34] FO4SF_NEWGAME rt=34.6 status stage=20 pos=1 1 0 cell=Vault world=None",
            "[12:00:40] FO4SF_NEWGAME rt=40.6 stage 30",
            "[12:00:40] FO4SF_NEWGAME rt=40.7 status stage=30 pos=2 2 0 cell=Vault world=None",
            "[12:00:46] FO4SF_NEWGAME rt=46.7 stage 40",
            "[12:00:50] FO4SF_NEWGAME rt=50.0 stage 200",
        ]
        _write(base / "Logs" / "Script" / "User" / "FO4SF_NewGame.0.log", "\n".join(ng_lines) + "\n")

        # fo4sf_mission.0.log: reaches stage 200 cleanly
        min_lines = [
            "[12:15:00] fo4sf_mission log opened (PC-64)",
            "[12:15:00] FO4SF_MISSION rt=900.0 stage 10",
            "[12:15:06] FO4SF_MISSION rt=906.0 status stage=10 dead=0/5",
            "[12:15:12] FO4SF_MISSION rt=912.0 status stage=10 dead=0/5",
            "[12:16:00] FO4SF_MISSION rt=960.0 stage 20",
            "[12:16:30] FO4SF_MISSION rt=990.0 stage 30",
            "[12:16:45] FO4SF_MISSION rt=1005.0 stage 40",
            "[12:16:46] FO4SF_MISSION rt=1006.0 stage 200",
        ]
        _write(base / "Logs" / "Script" / "User" / "fo4sf_mission.0.log", "\n".join(min_lines) + "\n")

        # FO4SF_ALife.0.log: steady 2s samples across 60m mark + PASS summary
        alife_lines = [
            "[12:30:00] FO4SF_ALife log opened (PC-64)",
            "[12:30:00] FO4SF_ALIFE rt=1800.0 step=rung1a_start from=0 to=3 waypoints=4",
            "[12:30:02] FO4SF_ALIFE rt=1802.0 step=rung1a_progress t=2.0 wp=0/4",
            "[12:30:04] FO4SF_ALIFE rt=1804.0 step=rung1a_progress t=4.0 wp=1/4",
            "[12:30:06] FO4SF_ALIFE rt=1806.0 step=rung1a_progress t=6.0 wp=3/4",
            "[12:30:08] FO4SF_ALIFE rt=1808.0 step=summary rung=1a result=PASS why=arrived t=8.0",
            "[13:00:05] FO4SF_ALIFE rt=3615.0 step=status rung1a=2 rung1a_passed=true wp=3/4",
        ]
        _write(base / "Logs" / "Script" / "User" / "FO4SF_ALife.0.log", "\n".join(alife_lines) + "\n")

        # SFSE logs: 2 plugins loaded, 0 refusals, 2 starmap blocks
        _write(
            base / "SFSE" / "Logs" / "sfse.txt",
            "SFSE runtime: initialize\n"
            "plugin FO4SFPipboyMenu.dll (00000001 FO4SFPipboyMenu 00010000) loaded correctly (handle 1)\n"
            "plugin FO4SFCombat.dll (00000001 FO4SFCombat 00010000) loaded correctly (handle 2)\n",
        )
        _write(
            base / "SFSE" / "Logs" / "FO4SFPipboyMenu.log",
            "[12:00:01.100] [100] [I] FO4SFPipboyMenu v0.1.0.0\n"
            "[12:00:01.105] [100] [I] step=load runtime=1.16.244.0 stage=5\n"
            "[12:25:10.000] [100] [I] step=starmap_blocked\n",
        )
        _write(
            base / "SFSE" / "Logs" / "FO4SFCombat.log",
            "[12:00:01.200] [100] [I] FO4SFCombat v0.1.0.0\n"
            "[12:00:01.205] [100] [I] step=load runtime=1.16.244.0\n",
        )
        _write(
            base / "SFSE" / "Logs" / "sfse_loader.txt",
            "SFSE loader: initialize\nWinVerifyTrust: 00000000 00000000 sfse_loader.exe\nhook thread complete\n",
        )

        # Clean exit in crashwatch.log
        _write(base / "crashes" / "crashwatch.log", "2026-11-17T13:00:06 exited: 0x00000000 normal exit\n")

    def test_clean_60min_soak_passes_and_fits_phone_bounds(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self._populate_clean_60min_session(base)
            report = analyze_session(str(base), crash_dir=str(base / "crashes"))

            self.assertEqual(report["verdict"], "PASS")
            self.assertGreaterEqual(report["duration_seconds"], 3600.0)
            self.assertEqual(report["crashes"]["dump_count"], 0)
            self.assertEqual(report["crashes"]["clean_exits"], 1)
            self.assertEqual(report["crashes"]["unexpected_exits"], 0)
            self.assertEqual(report["papyrus"]["vm_errors_ours"], 0)
            self.assertEqual(report["papyrus"]["vm_errors_total"], 1)
            self.assertEqual(report["sfse"]["plugins_loaded_count"], 2)
            self.assertEqual(report["sfse"]["refusals"], [])
            self.assertEqual(report["sfse"]["starmap_blocked"], 1)
            self.assertEqual(report["quests"]["running_after_hold"], [])
            self.assertEqual(report["quests"]["stuck_quests"], [])
            self.assertEqual(report["perf"]["timer_dips"], [])

            card = format_phone_report(report)
            lines = card.splitlines()
            self.assertIn("VERDICT: PASS", lines)
            self.assertIn("1. Crashes & Exits", lines)
            self.assertIn("2. Script & SFSE Errors", lines)
            self.assertIn("3. Quests (Held / Stuck)", lines)
            self.assertIn("4. Perf & Timer Dips", lines)
            self.assertLessEqual(len(lines), PHONE_MAX_LINES)
            for ln in lines:
                self.assertLessEqual(len(ln), PHONE_MAX_WIDTH, f"line too wide ({len(ln)}): {ln!r}")

    def test_crash_dump_and_unexpected_driver_exit_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self._populate_clean_60min_session(base)
            (base / "crashes" / "Starfield_261117_123000.dmp").write_bytes(b"synthetic dump payload")
            _write(base / "driver.log", "2026-11-17T12:30:01Z monitor check alive=False pid=4242\n")

            report = analyze_session(str(base), crash_dir=str(base / "crashes"))
            self.assertEqual(report["verdict"], "FAIL")
            self.assertEqual(report["crashes"]["dump_count"], 1)
            self.assertEqual(report["crashes"]["unexpected_exits"], 1)
            self.assertIn("crash_dumps=1", report["fail_reasons"])
            self.assertIn("unexpected_exits=1", report["fail_reasons"])

            card = format_phone_report(report)
            self.assertIn("VERDICT: FAIL", card)
            for ln in card.splitlines():
                self.assertLessEqual(len(ln), 60)

    def test_papyrus_stack_error_and_sfse_refuse_step_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _write(
                base / "Logs" / "Script" / "Papyrus.0.log",
                "[14:00:00] Papyrus log opened (PC-64)\n"
                '[14:00:05] Cannot open store for class "FO4SF_MissingQuest", missing file?\n'
                "[14:00:10] error: Cannot call Enable() on a None object, aborting function call\n"
                "stack:\n"
                '\t[FO4SF_Min00 (03000800)].FO4SF_Min00Quest.PlaceCodsworth() - "FO4SF_Min00Quest.psc" Line 470\n'
                '[14:00:12] warning: Assigning None to a non-object variable named "::temp4"\n'
                "stack:\n"
                '\t[FO4SF_Min00 (03000800)].FO4SF_Min00Quest.OnTimer() - "FO4SF_Min00Quest.psc" Line 250\n',
            )
            _write(
                base / "SFSE" / "Logs" / "FO4SFPipboyMenu.log",
                "[14:00:01.000] [200] [I] FO4SFPipboyMenu v0.1.0.0\n"
                "[14:00:01.010] [200] [E] refuse step=slots vtable=IMenu slot=0x6\n"
                "[14:00:02.000] [200] [W] step=fault read=pause_byte\n",
            )

            report = analyze_session(str(base))
            self.assertEqual(report["verdict"], "FAIL")
            self.assertEqual(report["papyrus"]["vm_errors_ours"], 1)
            self.assertEqual(report["papyrus"]["stack_errors_ours"], 1)
            self.assertEqual(report["papyrus"]["cannot_open_store_ours"], 1)
            self.assertEqual(report["papyrus"]["assign_none_ours"], 1)
            self.assertEqual(report["sfse"]["refusals"], ["FO4SFPipboyMenu:slots"])
            self.assertEqual(report["sfse"]["faults"], 1)

            card = format_phone_report(report)
            self.assertIn("VERDICT: FAIL", card)
            self.assertIn("FO4SFPipboyMenu:slots", card)
            for ln in card.splitlines():
                self.assertLessEqual(len(ln), PHONE_MAX_WIDTH)

    def test_stuck_quest_stage_warns_and_running_after_true_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            # Case A: Stuck on intermediate stage 20 for 360s (> 300s), hold-off clean -> WARN
            _write(
                base / "User" / "FO4SF_NewGame.0.log",
                "[15:00:00] FO4SF_NewGame log opened (PC-64)\n"
                "[15:00:05] FO4SF_NEWGAME rt=10.0 hold-off pass 2 stopped=165 of 165\n"
                "[15:00:10] FO4SF_NEWGAME rt=20.0 stage 20\n"
                "[15:06:10] FO4SF_NEWGAME rt=380.0 status stage=20 pos=0 0 0 cell=Vault world=None\n",
            )
            warn_rep = analyze_session(str(base))
            self.assertEqual(warn_rep["verdict"], "WARN")
            self.assertEqual(len(warn_rep["quests"]["stuck_quests"]), 1)
            self.assertEqual(warn_rep["quests"]["stuck_quests"][0]["quest"], "FO4SF_NewGame")
            self.assertEqual(warn_rep["quests"]["stuck_quests"][0]["stage"], 20)

            # Case B: Add running_after=true -> FAIL
            _write(
                base / "User" / "FO4SF_NewGame.0.log",
                "[15:00:00] FO4SF_NewGame log opened (PC-64)\n"
                "[15:00:04] FO4SF_NEWGAME rt=9.0 held off [defaulttutorialquestscript <MQ101 (00003448)>] running_after=true pass=2\n"
                "[15:00:05] FO4SF_NEWGAME rt=10.0 hold-off pass 2 stopped=164 of 165\n"
                "[15:00:10] FO4SF_NEWGAME rt=20.0 stage 20\n"
                "[15:06:10] FO4SF_NEWGAME rt=380.0 status stage=20 pos=0 0 0 cell=Vault world=None\n",
            )
            fail_rep = analyze_session(str(base))
            self.assertEqual(fail_rep["verdict"], "FAIL")
            self.assertEqual(fail_rep["quests"]["running_after_hold"], ["MQ101"])
            self.assertIn("running_after_hold=1", fail_rep["fail_reasons"])

    def test_timer_dip_detection_ignores_vm_freeze_and_flags_real_spike(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            # Papyrus freezes from 16:00:18 to 16:00:48 (menu pause), then a real unpaused 26s hitch occurs at 16:01:20
            _write(
                base / "Script" / "Papyrus.0.log",
                "[16:00:00] Papyrus log opened (PC-64)\n"
                "[16:00:18] VM is freezing...\n"
                "[16:00:48] VM is thawing...\n"
                "[16:01:25] warning: Papyrus VM budget exceeded during heavy cell load (stack count high)\n",
            )
            _write(
                base / "Script" / "User" / "FO4SF_NewGame.0.log",
                "[16:00:00] FO4SF_NewGame log opened (PC-64)\n"
                "[16:00:06] FO4SF_NEWGAME rt=6.0 status stage=20 pos=0 0 0\n"
                "[16:00:12] FO4SF_NEWGAME rt=12.0 status stage=20 pos=0 0 0\n"
                "[16:00:18] FO4SF_NEWGAME rt=18.0 status stage=20 pos=0 0 0\n"
                "[16:00:49] FO4SF_NEWGAME rt=49.0 status stage=20 pos=0 0 0\n"
                "[16:00:55] FO4SF_NEWGAME rt=55.0 status stage=20 pos=0 0 0\n"
                "[16:01:21] FO4SF_NEWGAME rt=81.0 status stage=20 pos=0 0 0\n"
                "[16:01:22] FO4SF_NEWGAME rt=82.0 stage 200\n",
            )

            report = analyze_session(str(base))
            self.assertEqual(report["verdict"], "WARN")
            # The 31s gap during VM freeze (18 -> 49) is excused; the unpaused 26s gap (55 -> 81) is caught!
            self.assertEqual(len(report["perf"]["timer_dips"]), 1)
            dip = report["perf"]["timer_dips"][0]
            self.assertAlmostEqual(dip["gap_s"], 26.0, places=1)
            self.assertEqual(dip["excess_ms"], 20000)
            self.assertEqual(report["perf"]["vm_budget_warnings"], 1)

    def test_rotated_log_fallback_missing_dirs_and_cli_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            # Only .1.log exists (rotated fallback), and crash_dir / sfse_log_dir do not exist
            _write(
                base / "Papyrus.1.log",
                "[10:00:00] Papyrus log opened (PC-64)\n[10:05:00] Log closed\n",
            )
            missing_sfse = base / "no_such_sfse"
            missing_crash = base / "no_such_crash"
            report = analyze_session(
                str(base),
                sfse_log_dir=str(missing_sfse),
                crash_dir=str(missing_crash),
            )
            self.assertEqual(report["verdict"], "PASS")
            self.assertEqual(report["rotated_fallbacks"], 1)
            self.assertIn("sfse_log_dir", report["missing_dirs"])
            self.assertIn("crash_dir", report["missing_dirs"])

            # Verify CLI --json and --out roundtrip
            out_json = base / "out" / "report.json"
            cli = ROOT / "scripts" / "testing" / "soak_log_reader.py"
            proc = subprocess.run(
                [sys.executable, "-I", str(cli), str(base), "--json", "--out", str(out_json)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            parsed = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(parsed["verdict"], "PASS")
            self.assertEqual(json.loads(proc.stdout)["verdict"], "PASS")

    def test_stale_leftover_logs_from_prior_days_are_filtered_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self._populate_clean_60min_session(base)
            stale_sfse = base / "SFSE" / "Logs" / "FOCCPing.log"
            _write(stale_sfse, "[10:00:00.000] [99] [E] refuse step=slots\n")
            now_m = (base / "Logs" / "Script" / "Papyrus.0.log").stat().st_mtime
            os.utime(stale_sfse, (now_m - 7 * 86400, now_m - 7 * 86400))

            fresh_only = analyze_session(str(base), crash_dir=str(base / "crashes"))
            self.assertEqual(fresh_only["verdict"], "PASS")
            self.assertEqual(fresh_only["stale_logs_skipped"], 1)

            all_ages = analyze_session(str(base), crash_dir=str(base / "crashes"), session_window_hours=None)
            self.assertEqual(all_ages["verdict"], "FAIL")
            self.assertIn("FOCCPing:slots", all_ages["sfse"]["refusals"])


if __name__ == "__main__":
    unittest.main()
