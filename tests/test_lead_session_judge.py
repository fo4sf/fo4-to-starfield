"""Synthetic unit tests for the Sessions 1, 3, and 4 read-only log judge (`K1` / `R11`).

Uses purely hand-written log fixtures with made-up text inside temporary directories.
Verifies:
  1. Single-table R11 parity between `SESSION_PASS_SPECS` and `docs/testing/lead-run-order.md`.
  2. All-PASS synthetic log fixtures for Sessions 1, 3, and 4 (with first matching line reported).
  3. Missing PASS line detection per card.
  4. Every named stop-point condition across Sessions 1, 3, and 4 triggering `FAIL`.
  5. Card C `MapBlockStarMap=0` hide-only fallback opt-in (`--allow-map-suppress-fallback`).
  6. Strict read-only behaviour: zero files created or modified inside `--log-dir` (or anywhere
     else when `--out-dir` is omitted), and `--out-dir` writes only inside the named folder.
"""
from __future__ import annotations

import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS_TESTING = ROOT / "scripts" / "testing"
for p in (str(SRC), str(SCRIPTS_TESTING)):
    if p not in sys.path:
        sys.path.insert(0, p)

from fo4sf.testing.lead_session_specs import (  # noqa: E402
    SESSION_PASS_SPECS,
    SESSION_STOP_SPECS,
    SUPPORTED_SESSIONS,
    evaluate_session_logs,
    expected_sheet_pass_lines,
    extract_session_pass_lines,
)
import check_lead_sessions  # noqa: E402


# Purely made-up synthetic log fixtures (zero real game paths or private evidence).
SYNTHETIC_SESSION_1_LOGS = {
    "FO4SFPipboyMenu.log": "\n".join(
        [
            "[00:00:01] [info] synthetic boot header",
            "[00:00:02] [info] step=code_obj_holder type=object raw_type=8 is_closure=0 source=menu_mc members=49 of=49",
            "[00:00:03] [info] step=code_obj_destruction movie=0x00001234 called=1",
            "[00:00:04] [info] step=map_unregister ok=1",
            "[00:00:05] [info] step=destroy menu=0x00005678 flags=0x0004",
            "[00:00:06] [info] step=menu_guard registered=Console,PauseMenu count=38/38",
            "[00:00:07] [info] step=process_user_event name=Cancel handled=0 down=1",
            "[00:00:08] [info] step=toggle n=1 ignored=menu_open menu=Console",
            "[00:00:09] [info] step=request_open by=map_key page=3 ignored=menu_open menu=Console",
            "[00:00:10] [info] step=starmap_block_install menu=GalaxyStarMapMenu found=1 slot=0 orig_rva=0x01AB20",
            "[00:00:11] [info] step=starmap_blocked n=1 blocked menu=GalaxyStarMapMenu route=create",
            "[00:00:12] [info] step=starmap_blocked n=2 blocked menu=GalaxyStarMapMenu route=create",
        ]
    )
    + "\n",
    "FO4SFCombat.log": "\n".join(
        [
            "[00:00:08] [info] step=dispatch n=1 fn=FO4SF_CombatInput.OnVatsKey ignored=menu_open menu=Console",
            "[00:00:09] [info] step=dispatch n=2 fn=FO4SF_CombatInput.OnAmmoKey ignored=menu_open menu=Console",
        ]
    )
    + "\n",
    "fo4sf_newgame.0.log": "[00:00:10] FO4SF_NEWGAME rt=14.25 blocked input=handscanner\n",
}

SYNTHETIC_SESSION_3_LOGS = {
    "session3_cli.txt": "\n".join(
        [
            "check: ok",
            "installed 3 files, plugins ['FO4SFHome.esm', 'FO4TerrainCore_Home.esm']",
            "uninstalled",
            "nothing installed",
        ]
    )
    + "\n",
}

SYNTHETIC_SESSION_4_LOGS = {
    "session4_cli.txt": "\n".join(
        [
            "install batch synthetic-fo4dlc-stage: ['FO4DLC.esm', 'FO4DLC - Main.ba2', 'FO4DLC - Textures.ba2', "
            "'FO4DLCTextures2.esm', 'FO4DLCTextures2 - Textures.ba2', 'FO4DLCTextures3.esm', "
            "'FO4DLCTextures3 - Textures.ba2'] -> /synth-game-dir/Data (7.10 GB)",
            "installed. Undo with: python deploy_starfield.py uninstall --starfield /synth-game-dir --plugin-name FO4DLC.esm",
            "installed port as recorded: FO4Port.esm deadbeef",
            "installed wb5 session: added=8, plugins=['FO4DLC.esm', 'FO4DLCTextures2.esm', "
            "'FO4DLCTextures3.esm', 'FO4TerrainCore_DLC.esm']",
            "uninstalled wb5 session: removed=8, restored_fo4dlc=False",
            "installed 3 files, plugins ['FO4WorldFarHarbor.esm', 'FO4WorldFarHarbor_Mars.esm']",
            "installed 3 files, plugins ['FO4WorldNukaWorld.esm', 'FO4WorldNukaWorld_Mars.esm']",
            "uninstalled",
        ]
    )
    + "\n",
}


def _write_files(root: Path, files: dict[str, str]) -> None:
    for rel, content in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def _snapshot_tree(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


class LeadSessionJudgeTests(unittest.TestCase):
    def test_single_table_matches_lead_run_order_sheet_r11(self) -> None:
        sheet = ROOT / "docs" / "testing" / "lead-run-order.md"
        self.assertTrue(sheet.is_file(), "docs/testing/lead-run-order.md must exist")
        md_text = sheet.read_text(encoding="utf-8")
        for snum in SUPPORTED_SESSIONS:
            self.assertEqual(
                extract_session_pass_lines(md_text, snum),
                expected_sheet_pass_lines(snum),
                f"Session {snum} PASS block in lead-run-order.md diverged from SESSION_PASS_SPECS",
            )

    def test_all_sessions_pass_and_record_first_matching_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp) / "copied_logs"
            log_dir.mkdir()
            _write_files(log_dir, {**SYNTHETIC_SESSION_1_LOGS, **SYNTHETIC_SESSION_3_LOGS, **SYNTHETIC_SESSION_4_LOGS})
            before = _snapshot_tree(log_dir)

            report = evaluate_session_logs(log_dir)
            self.assertTrue(report["all_pass"])
            self.assertFalse(report["any_stop_failure"])
            self.assertFalse(report["any_missing"])
            for snum in SUPPORTED_SESSIONS:
                s = report["sessions"][str(snum)]
                self.assertEqual(s["verdict"], "PASS")
                self.assertEqual(s["found"], len(SESSION_PASS_SPECS[snum]))
                self.assertEqual(s["missing"], 0)
                self.assertEqual(s["stop_failures"], 0)

            # Confirm first matching hit is reported (n=1, not n=2) with file:line prefix.
            s1_cards = {c["card"]: c for c in report["sessions"]["1"]["cards"]}
            blocked_row = [
                r for r in s1_cards["Card C"]["pass_lines"] if "starmap_blocked" in r["expected"]
            ][0]
            self.assertEqual(blocked_row["status"], "FOUND")
            self.assertIn("FO4SFPipboyMenu.log:11:", blocked_row["match"])
            self.assertIn("n=1", blocked_row["match"])

            # Strictly read-only: copied log directory bytes untouched.
            self.assertEqual(_snapshot_tree(log_dir), before)

    def test_missing_pass_lines_are_flagged_per_card(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp) / "logs"
            log_dir.mkdir()
            # Drop the handscanner line from Session 1 and `nothing installed` from Session 3.
            _write_files(
                log_dir,
                {
                    "FO4SFPipboyMenu.log": SYNTHETIC_SESSION_1_LOGS["FO4SFPipboyMenu.log"],
                    "FO4SFCombat.log": SYNTHETIC_SESSION_1_LOGS["FO4SFCombat.log"],
                    "session3_cli.txt": "check: ok\ninstalled 3 files, plugins ['FO4SFHome.esm', 'FO4TerrainCore_Home.esm']\nuninstalled\n",
                },
            )
            report = evaluate_session_logs(log_dir, sessions=(1, 3))
            self.assertFalse(report["all_pass"])
            self.assertTrue(report["any_missing"])
            self.assertFalse(report["any_stop_failure"])

            s1_cards = {c["card"]: c for c in report["sessions"]["1"]["cards"]}
            self.assertEqual(s1_cards["Card B"]["verdict"], "PASS")
            self.assertEqual(s1_cards["Card C"]["verdict"], "FAIL")
            missing_s1 = [r["expected"] for r in s1_cards["Card C"]["pass_lines"] if r["status"] == "MISSING"]
            self.assertEqual(missing_s1, ["FO4SF_NEWGAME rt=<rt> blocked input=handscanner"])

            s3 = report["sessions"]["3"]
            self.assertEqual(s3["verdict"], "FAIL")
            self.assertEqual(s3["missing"], 1)

    def test_card_c_map_suppress_fallback_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp) / "logs"
            log_dir.mkdir()
            pipboy_no_create = "\n".join(
                ln for ln in SYNTHETIC_SESSION_1_LOGS["FO4SFPipboyMenu.log"].splitlines() if "starmap_blocked" not in ln
            ) + "\n[00:00:15] [info] step=map_suppress n=1 name=GalaxyStarMapMenu sent=hide\n"
            _write_files(
                log_dir,
                {
                    "FO4SFPipboyMenu.log": pipboy_no_create,
                    "FO4SFCombat.log": SYNTHETIC_SESSION_1_LOGS["FO4SFCombat.log"],
                    "fo4sf_newgame.0.log": SYNTHETIC_SESSION_1_LOGS["fo4sf_newgame.0.log"],
                },
            )
            strict = evaluate_session_logs(log_dir, sessions=(1,), allow_map_suppress_fallback=False)
            self.assertEqual(strict["sessions"]["1"]["verdict"], "FAIL")

            with_fb = evaluate_session_logs(log_dir, sessions=(1,), allow_map_suppress_fallback=True)
            self.assertEqual(with_fb["sessions"]["1"]["verdict"], "PASS")

    def test_all_session_1_3_4_stop_points_trigger_fail(self) -> None:
        stop_samples = [
            # Session 1 stop points
            (1, "s1_card_b_is_closure", "[00:01] step=code_obj_holder type=object raw_type=8 is_closure=1 source=menu_mc members=49 of=49"),
            (1, "s1_card_b_members", "[00:01] step=code_obj_holder type=object raw_type=8 is_closure=0 source=menu_mc members=48 of=49"),
            (1, "s1_card_b_refuse", "[00:01] refuse step=code_obj_install reason=missing_symbol"),
            (1, "s1_card_b_console_leak", "[00:01] step=toggle n=3 menu=Console action=opened"),
            (1, "s1_card_c_outside_image", "[00:01] step=starmap_block_install menu=GalaxyStarMapMenu reason=outside_image"),
            (1, "s1_card_c_refuse_starmap", "[00:01] refuse step=starmap_block reason=bad_slot"),
            # Session 3 stop points
            (3, "s3_not_ordered", "not ordered: FO4TerrainCore_Home.esm appears before FO4SFHome.esm"),
            (3, "s3_duplicate_override", "error: duplicate override for MarsPlanetData"),
            (3, "s3_already_installed", "error: home world already installed"),
            (3, "s3_refused", "home_world_install: refused install"),
            (3, "s3_check_failed", "check: 2 problems found"),
            # Session 4 stop points
            (4, "s4a_verify_mismatch", "FO4Port.esm differs from recorded sha256"),
            (4, "s4a_deploy_refused", "deploy_starfield.py: refused (insufficient free-gb)"),
            (4, "s4b_bridge_inactive", "FO4SFBridge.esm is inactive in Plugins.txt"),
            (4, "s4b_load_door_failed", "[00:12] FO4SF_LoadDoor load door arrival failed n=3 door=184875"),
            (4, "s4b_wb5_mismatch", "make_cw_dlc_override.py: wb5 reference mismatch"),
            (4, "s4c_not_ordered", "not ordered: FO4WorldFarHarbor_Mars.esm missing"),
            (4, "s4c_install_or_uninstall_failed", "exp_install: uninstall incomplete for synthetic pack"),
        ]

        # Ensure every single declared stop_id across Sessions 1, 3, and 4 is exercised.
        declared_ids = {
            sp.stop_id for snum in SUPPORTED_SESSIONS for sp in SESSION_STOP_SPECS[snum]
        }
        tested_ids = {stop_id for _s, stop_id, _line in stop_samples}
        self.assertEqual(tested_ids, declared_ids)

        base_by_session = {
            1: SYNTHETIC_SESSION_1_LOGS,
            3: SYNTHETIC_SESSION_3_LOGS,
            4: SYNTHETIC_SESSION_4_LOGS,
        }
        for snum, stop_id, bad_line in stop_samples:
            with self.subTest(session=snum, stop_id=stop_id):
                with tempfile.TemporaryDirectory() as tmp:
                    log_dir = Path(tmp) / "logs"
                    log_dir.mkdir()
                    files = dict(base_by_session[snum])
                    files["stop_inject.log"] = bad_line + "\n"
                    _write_files(log_dir, files)

                    report = evaluate_session_logs(log_dir, sessions=(snum,))
                    self.assertTrue(report["any_stop_failure"])
                    self.assertFalse(report["all_pass"])
                    s = report["sessions"][str(snum)]
                    self.assertEqual(s["verdict"], "FAIL")
                    hits = [
                        sp
                        for card in s["cards"]
                        for sp in card["stop_points"]
                        if sp["stop_id"] == stop_id
                    ]
                    self.assertEqual(len(hits), 1)
                    self.assertEqual(hits[0]["status"], "FAIL")
                    self.assertIn("stop_inject.log:1:", hits[0]["match"])

    def test_cli_is_read_only_by_default_and_writes_only_inside_out_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log_dir = root / "logs"
            out_dir = root / "report_out"
            log_dir.mkdir()
            _write_files(log_dir, {**SYNTHETIC_SESSION_1_LOGS, **SYNTHETIC_SESSION_3_LOGS, **SYNTHETIC_SESSION_4_LOGS})
            before_root = _snapshot_tree(root)

            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = check_lead_sessions.main(["--log-dir", str(log_dir), "--require-all-pass"])
            self.assertEqual(rc, 0)
            self.assertIn("overall: PASS", buf.getvalue())
            # Zero files written anywhere when --out-dir is omitted.
            self.assertEqual(_snapshot_tree(root), before_root)

            # With --out-dir, writes ONLY <out-dir>/lead_sessions_report.json; --log-dir untouched.
            buf_json = io.StringIO()
            with redirect_stdout(buf_json):
                rc2 = check_lead_sessions.main(
                    ["--log-dir", str(log_dir), "--session", "1,4", "--json", "--out-dir", str(out_dir)]
                )
            self.assertEqual(rc2, 0)
            parsed = json.loads(buf_json.getvalue())
            self.assertEqual(parsed["selected_sessions"], [1, 4])
            report_file = out_dir / "lead_sessions_report.json"
            self.assertTrue(report_file.is_file())
            self.assertEqual(list(out_dir.iterdir()), [report_file])
            self.assertEqual(_snapshot_tree(log_dir), {
                k.split("/", 1)[1]: v for k, v in before_root.items() if k.startswith("logs/")
            })


if __name__ == "__main__":
    unittest.main()
