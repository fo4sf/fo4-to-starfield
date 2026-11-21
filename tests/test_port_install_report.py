"""Unit tests for `IB2` read-only port install-record report tool (`scripts/terrain/port_install_report.py`).

Uses 100% hand-written fixture records and synthetic byte files — zero local paths, zero real report output."""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for _p in (
    str(ROOT / "src"),
    str(ROOT / "scripts"),
    str(ROOT / "scripts" / "terrain"),
    str(ROOT / "tests"),
):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import port_install_report as pir  # noqa: E402


def _b64_lines(lines: list[str], crlf: bool = True) -> str:
    nl = "\r\n" if crlf else "\n"
    raw = (nl.join(lines) + (nl if lines else "")).encode("utf-8")
    return base64.b64encode(raw).decode("ascii")


def _ident(payload: bytes) -> dict:
    return {"size": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}


class PortInstallReportTests(unittest.TestCase):
    def test_clean_matching_install_record_reports_zero_differences_and_is_strictly_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sf = root / "Starfield"
            data = sf / "Data"
            data.mkdir(parents=True)
            pt = root / "AppData" / "Starfield" / "Plugins.txt"
            pt.parent.mkdir(parents=True)

            files_payload = {
                "FO4Port.esm": b"TES4" + b"\x00" * 38,
                "FO4Port - Main.ba2": b"BTDX" + b"main" * 10,
                "FO4Port - Textures.ba2": b"BTDX" + b"tex1" * 10,
            }
            for fname, body in files_payload.items():
                (data / fname).write_bytes(body)

            orig_lines = ["*BlueprintShips-Starfield.esm", "*SFBGS003.esm"]
            act_lines = [*orig_lines, "*FO4Port.esm"]
            pt.write_bytes(("\r\n".join(act_lines) + "\r\n").encode("utf-8"))

            rec_path = data / "FO4Port.deploy.json"
            rec_doc = {
                "files": list(files_payload),
                "published_files": list(files_payload),
                "plugins_txt": str(pt),
                "plugins_added": ["*FO4Port.esm"],
                "plugins_replaced": [],
                "plugins_original": _b64_lines(orig_lines),
                "plugins_activated": _b64_lines(act_lines),
                "plugins_restore_pending": False,
                "complete": True,
                "artifacts": {k: _ident(v) for k, v in files_payload.items()},
            }
            rec_path.write_text(json.dumps(rec_doc, indent=1), encoding="utf-8")

            # Pin fixed mtimes to verify 100% read-only execution
            fixed_ts = 1761650000.0
            for p in (rec_path, pt, *(data / k for k in files_payload)):
                os.utime(p, (fixed_ts, fixed_ts))
            before_snapshots = {
                str(p): (p.read_bytes(), os.stat(p).st_mtime)
                for p in (rec_path, pt, *(data / k for k in files_payload))
            }

            report = pir.inspect_port_install(str(sf), plugins_txt_override=str(pt))
            self.assertTrue(report["read_only"])
            self.assertEqual(report["plugin_name"], "FO4Port.esm")
            self.assertTrue(report["record"]["old_format_without_plugin_name"])
            self.assertEqual(report["differences"], [])
            self.assertEqual(report["counts"]["total_differences"], 0)
            self.assertEqual(report["counts"]["recorded_files"], 3)
            self.assertEqual(report["counts"]["data_files_matching"], 3)
            self.assertEqual(report["counts"]["data_files_missing"], 0)
            self.assertEqual(report["counts"]["data_files_changed"], 0)
            self.assertEqual(report["counts"]["owned_plugins_active_in_live"], 1)
            self.assertEqual(report["counts"]["pending_restore_flag"], 0)

            after_snapshots = {
                str(p): (p.read_bytes(), os.stat(p).st_mtime)
                for p in (rec_path, pt, *(data / k for k in files_payload))
            }
            self.assertEqual(before_snapshots, after_snapshots)

    def test_pending_restore_flag_and_drifted_oct28_load_list_reported_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sf = root / "Starfield"
            data = sf / "Data"
            data.mkdir(parents=True)
            pt = root / "Plugins.txt"

            esm_bytes = b"TES4" + b"port" * 12
            ba2_bytes = b"BTDX" + b"arch" * 12
            (data / "FO4Port.esm").write_bytes(esm_bytes)
            (data / "FO4Port - Main.ba2").write_bytes(ba2_bytes)

            # Hand-written Oct-28-style snapshot vs evolved live Plugins.txt
            oct28_orig = [
                "*BlueprintShips-Starfield.esm",
                "*OldTestMod.esm",
                "*TogglePlugin.esm",
            ]
            oct28_activated = [
                "*BlueprintShips-Starfield.esm",
                "*OldTestMod.esm",
                "*TogglePlugin.esm",
                "*FO4Port.esm",
            ]
            # Live Plugins.txt: OldTestMod removed, TogglePlugin deactivated, order swapped between FO4Port & BlueprintShips,
            # and 2 new plugins added after Oct 28.
            live_lines = [
                "# Starfield load list",
                "*FO4Port.esm",
                "*BlueprintShips-Starfield.esm",
                "TogglePlugin.esm",
                "*FO4TerrainCore.esm",
                "*FO4SFStart.esm",
            ]
            pt.write_text("\r\n".join(live_lines) + "\r\n", encoding="utf-8")

            rec_doc = {
                "files": ["FO4Port.esm", "FO4Port - Main.ba2"],
                "published_files": ["FO4Port.esm", "FO4Port - Main.ba2"],
                "plugins_txt": str(pt),
                "plugins_added": ["*FO4Port.esm"],
                "plugins_replaced": [],
                "plugins_original": _b64_lines(oct28_orig),
                "plugins_activated": _b64_lines(oct28_activated),
                "plugins_restore_pending": True,
                "complete": True,
                "artifacts": {
                    "FO4Port.esm": _ident(esm_bytes),
                    "FO4Port - Main.ba2": _ident(ba2_bytes),
                },
            }
            (data / "FO4Port.deploy.json").write_text(json.dumps(rec_doc), encoding="utf-8")

            report = pir.inspect_port_install(str(sf), plugins_txt_override=str(pt))
            counts = report["counts"]
            self.assertEqual(counts["record_exists"], 1)
            self.assertEqual(counts["record_complete"], 1)
            self.assertEqual(counts["record_has_plugin_name_key"], 0)
            self.assertEqual(counts["pending_restore_flag"], 1)
            self.assertEqual(counts["data_files_matching"], 2)
            self.assertEqual(counts["snapshot_original_lines"], 3)
            self.assertEqual(counts["snapshot_activated_lines"], 4)
            self.assertEqual(counts["live_plugins_txt_lines"], 5)
            self.assertEqual(counts["plugins_txt_added_since_snapshot"], 2)
            self.assertEqual(counts["plugins_txt_removed_since_snapshot"], 1)
            self.assertEqual(counts["plugins_txt_activation_toggles"], 1)
            self.assertEqual(counts["plugins_txt_order_changed"], 1)
            self.assertEqual(counts["owned_plugins_active_in_live"], 1)

            codes = {d["code"] for d in report["differences"]}
            self.assertEqual(codes, {"pending_restore_flag_set", "plugins_txt_drifted_from_snapshot"})
            self.assertEqual(report["plugins_txt_comparison"]["live_only_plugins"], ["FO4TerrainCore.esm", "FO4SFStart.esm"])
            self.assertEqual(report["plugins_txt_comparison"]["snapshot_only_plugins"], ["OldTestMod.esm"])

    def test_missing_and_changed_data_files_unrecorded_companions_and_backups(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sf = root / "Starfield"
            data = sf / "Data"
            data.mkdir(parents=True)
            pt_dir = root / "LocalAppData"
            pt_dir.mkdir()
            pt = pt_dir / "Plugins.txt"

            esm_orig = b"TES4" + b"orig" * 10
            main_orig = b"BTDX" + b"main_orig" * 8
            tex_orig = b"BTDX" + b"tex_orig" * 8

            # FO4Port.esm matches; Main.ba2 modified on disk; Textures.ba2 missing on disk!
            (data / "FO4Port.esm").write_bytes(esm_orig)
            (data / "FO4Port - Main.ba2").write_bytes(b"BTDX" + b"TAMPERED" * 8)
            # Extra unrecorded companion + temp/backup files + side-by-side FO4DLC.deploy.json
            (data / "FO4PortTextures2.esm").write_bytes(b"TES4" + b"\x00" * 38)
            (data / ".fo4port-install-stale").write_bytes(b"temp")
            (data / "FO4Port.esm.bak").write_bytes(esm_orig)
            (data / "FO4DLC.deploy.json").write_text("{}", encoding="utf-8")

            # Live Plugins.txt has FO4Port.esm disabled (missing '*') plus a backup file next to it
            pt.write_text("FO4Port.esm\r\n", encoding="utf-8")
            (pt_dir / "Plugins.txt.bak").write_text("*FO4Port.esm\r\n", encoding="utf-8")

            rec_doc = {
                "plugin_name": "FO4Port.esm",
                "files": ["FO4Port.esm", "FO4Port - Main.ba2", "FO4Port - Textures.ba2"],
                "published_files": ["FO4Port.esm", "FO4Port - Main.ba2"],
                "plugins_txt": str(pt),
                "plugins_added": ["*FO4Port.esm"],
                "plugins_replaced": [],
                "plugins_original": None,
                "plugins_activated": _b64_lines(["*FO4Port.esm"]),
                "plugins_restore_pending": True,
                "cleanup_pending": True,
                "complete": False,
                "artifacts": {
                    "FO4Port.esm": _ident(esm_orig),
                    "FO4Port - Main.ba2": _ident(main_orig),
                    "FO4Port - Textures.ba2": _ident(tex_orig),
                },
            }
            (data / "FO4Port.deploy.json").write_text(json.dumps(rec_doc), encoding="utf-8")

            report = pir.inspect_port_install(str(sf), plugins_txt_override=str(pt))
            counts = report["counts"]
            self.assertEqual(counts["record_complete"], 0)
            self.assertEqual(counts["record_has_plugin_name_key"], 1)
            self.assertEqual(counts["pending_restore_flag"], 1)
            self.assertEqual(counts["cleanup_pending_flag"], 1)
            self.assertEqual(counts["data_files_matching"], 1)
            self.assertEqual(counts["data_files_changed"], 1)
            self.assertEqual(counts["data_files_missing"], 1)
            self.assertEqual(counts["unrecorded_bundle_files_in_data"], 1)
            self.assertEqual(counts["other_deploy_records_in_data"], 1)
            self.assertEqual(counts["temp_or_backup_files_in_data"], 2)
            self.assertEqual(counts["owned_plugins_inactive_or_missing"], 1)
            self.assertEqual(counts["plugins_txt_backup_or_temp_files"], 1)

            codes = {d["code"] for d in report["differences"]}
            for expected_code in (
                "incomplete_install_record",
                "cleanup_pending_flag_set",
                "pending_restore_flag_set",
                "unpublished_recorded_files",
                "changed_recorded_file",
                "missing_recorded_file",
                "unrecorded_bundle_file",
                "temp_or_backup_file_in_data",
                "owned_plugin_not_active",
                "plugins_txt_drifted_from_snapshot",
                "plugins_txt_backup_or_temp_file",
            ):
                self.assertIn(expected_code, codes)

    def test_out_path_guard_allows_only_fo4sf_owner_tests_outside_git_and_game(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sf = root / "Starfield"
            data = sf / "Data"
            data.mkdir(parents=True)
            (sf / "Starfield.exe").write_bytes(b"MZ")
            pt = root / "Plugins.txt"
            pt.write_bytes(b"*FO4Port.esm\r\n")

            esm = b"TES4" + b"\x00" * 38
            (data / "FO4Port.esm").write_bytes(esm)
            (data / "FO4Port.deploy.json").write_text(
                json.dumps({
                    "files": ["FO4Port.esm"],
                    "published_files": ["FO4Port.esm"],
                    "plugins_txt": str(pt),
                    "plugins_added": ["*FO4Port.esm"],
                    "plugins_replaced": [],
                    "plugins_original": None,
                    "plugins_activated": _b64_lines(["*FO4Port.esm"]),
                    "plugins_restore_pending": False,
                    "complete": True,
                    "artifacts": {"FO4Port.esm": _ident(esm)},
                }),
                encoding="utf-8",
            )

            # 1. Refused inside a Git worktree (even if subpath contains FO4SF-Owner-Tests!)
            git_wt = root / "fake_git_repo"
            (git_wt / ".git").mkdir(parents=True)
            self.assertEqual(
                pir.main([
                    "--starfield", str(sf), "--plugins-txt", str(pt),
                    "--out", str(git_wt / "FO4SF-Owner-Tests" / "r.json"),
                ]),
                1,
            )

            # 2. Refused inside --starfield / game directory
            self.assertEqual(
                pir.main([
                    "--starfield", str(sf), "--plugins-txt", str(pt),
                    "--out", str(sf / "FO4SF-Owner-Tests" / "r.json"),
                ]),
                1,
            )

            # 3. Refused outside FO4SF-Owner-Tests
            self.assertEqual(
                pir.main([
                    "--starfield", str(sf), "--plugins-txt", str(pt),
                    "--out", str(root / "other_folder" / "r.json"),
                ]),
                1,
            )

            # 4. Succeeds inside <tmp>/FO4SF-Owner-Tests/sub/r.json, and --counts-only prints only counts
            good_out = root / "FO4SF-Owner-Tests" / "run1" / "report.json"
            buf = io.StringIO()
            with patch("sys.stdout", buf):
                rc = pir.main([
                    "--starfield", str(sf), "--plugins-txt", str(pt),
                    "--out", str(good_out), "--counts-only",
                ])
            self.assertEqual(rc, 0)
            self.assertTrue(good_out.is_file())
            stdout_doc = json.loads(buf.getvalue())
            self.assertEqual(list(stdout_doc.keys()), ["counts"])
            saved_doc = json.loads(good_out.read_text(encoding="utf-8"))
            self.assertEqual(saved_doc["counts"]["total_differences"], 0)


if __name__ == "__main__":
    unittest.main()
