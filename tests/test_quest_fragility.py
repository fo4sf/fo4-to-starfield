"""Unit tests for Tier 1 offline quest fragility checker, W7 Open Mode, and W6 docs (R11 / P3)."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve()


def _resolve_repo_or_sibling(repo_rel: str, sibling_name: str) -> Path:
    repo_root = HERE.parents[1]
    candidate = repo_root / repo_rel
    if candidate.is_file():
        return candidate
    return HERE.parent / sibling_name


CHECKER_PATH = _resolve_repo_or_sibling("scripts/testing/check_quest_fragility.py", "check_quest_fragility.py")
CATALOG_PATH = _resolve_repo_or_sibling("src/fo4sf/testing/quest_test_catalog.json", "quest_test_catalog.json")
PLAN_PATH = _resolve_repo_or_sibling("docs/testing/quest-test-plan.md", "quest-test-plan.md")
REACH_PATH = _resolve_repo_or_sibling("docs/testing/reachability-fixes.md", "reachability-fixes.md")

_spec = importlib.util.spec_from_file_location("check_quest_fragility", CHECKER_PATH)
assert _spec is not None and _spec.loader is not None
cqf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cqf)

DRIVE_PATH_RX = re.compile(r"\b[A-Za-z]:[\\/]")
FORBIDDEN_MOD_PATTERNS = [
    re.compile(r"\b" + ("UF" + "O4P") + r"\b", re.I),
    re.compile(r"\b" + ("Unofficial" + r"\s+" + "Fallout") + r"\b", re.I),
    re.compile(r"\b" + ("Yuki" + "chigai" + "|" + "Y" + "UP") + r"\b", re.I),
    re.compile(r"\b" + ("GAM" + "MA") + r"\b", re.I),
    re.compile(r"\b" + ("Buff" + "out") + r"\b", re.I),
    re.compile(r"\b" + ("Role" + "players" + r"'?\s+" + "Alternate") + r"\b", re.I),
]
FENCED_BLOCK_RE = re.compile(r"```([A-Za-z0-9_-]*)\r?\n(.*?)```", re.S)


class QuestFragilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = cqf.load_catalog(CATALOG_PATH)

    def test_catalog_schema_and_unique_ids(self) -> None:
        quests = self.catalog["quests"]
        self.assertEqual(len(quests), 60)
        ids = [q["id"] for q in quests]
        self.assertEqual(len(ids), len(set(ids)), "duplicate quest IDs in catalog")

        by_game = {"FO4": 0, "FO3": 0, "FNV": 0}
        for q in quests:
            by_game[q["game"]] += 1
            self.assertIn(q["start_stage"], q["stages"], q["id"])
            self.assertTrue(q["completion_stages"], q["id"])
            for cs in q["completion_stages"]:
                self.assertIn(cs, q["stages"], q["id"])
            for npc in q["essential_npcs"]:
                self.assertTrue(npc["id"].strip(), q["id"])
                self.assertGreater(len(npc["open_mode_fallback"].strip()), 15, f"{q['id']}:{npc['id']}")
        self.assertEqual(by_game, {"FO4": 19, "FO3": 20, "FNV": 21})

    def test_clean_pass_normal_and_open_mode_with_exact_tier_counts(self) -> None:
        normal = cqf.evaluate_catalog(self.catalog, open_mode=False)
        open_rep = cqf.evaluate_catalog(self.catalog, open_mode=True)

        self.assertEqual(normal["quests_checked"], 60)
        self.assertEqual(normal["dead_end_count"], 0, normal["dead_ends"])
        self.assertEqual(open_rep["dead_end_count"], 0, open_rep["dead_ends"])
        self.assertEqual(open_rep["open_mode_failure_count"], 0, open_rep["open_mode_failures"])

        # Deterministic FRAGILE list matches across Normal and Open Mode
        self.assertEqual(normal["fragile_count"], 18)
        self.assertEqual(open_rep["fragile_count"], 18)
        self.assertEqual(
            [q["id"] for q in normal["fragile_list"]],
            [q["id"] for q in open_rep["fragile_list"]],
        )
        self.assertEqual(open_rep["fragile_by_game"], {"FO4": 5, "FO3": 6, "FNV": 7, "total": 18})

        # Exact per-tier counts
        self.assertEqual(open_rep["tier_counts"]["tier_1"], {"FO4": 19, "FO3": 20, "FNV": 21, "total": 60})
        self.assertEqual(open_rep["tier_counts"]["tier_2"], {"FO4": 19, "FO3": 0, "FNV": 0, "total": 19})
        self.assertEqual(open_rep["tier_counts"]["tier_3"], {"FO4": 7, "FO3": 20, "FNV": 21, "total": 48})
        self.assertEqual(open_rep["tier_counts"]["tier_4"], {"FO4": 19, "FO3": 13, "FNV": 14, "total": 46})

        # Every Tier 4 quest must be main_spine, fragile, or feel_item (W6 Tier 4 rule)
        for q in open_rep["quests"]:
            if 4 in q["tiers"]:
                self.assertTrue(
                    q["main_spine"] or q["fragile"] or q["feel_item"],
                    f"Tier 4 quest {q['id']} is not main_spine, fragile, or feel_item",
                )

    def test_mutation_detects_normal_dead_end(self) -> None:
        mutated = copy.deepcopy(self.catalog)
        min00 = next(q for q in mutated["quests"] if q["id"] == "FO4SF_Min00")
        # Break stage 20 -> 30 transition so stage 20 becomes a dead end
        min00["transitions"] = [t for t in min00["transitions"] if not (t["from"] == 20 and t["to"] == 30)]

        rep = cqf.evaluate_catalog(mutated, open_mode=False)
        self.assertGreater(rep["dead_end_count"], 0)
        self.assertTrue(
            any(de["quest_id"] == "FO4SF_Min00" and de["stage"] == 20 for de in rep["dead_ends"]),
            rep["dead_ends"],
        )

    def test_mutation_detects_out_of_order_entry_dead_end(self) -> None:
        mutated = copy.deepcopy(self.catalog)
        mq02 = next(q for q in mutated["quests"] if q["id"] == "MQ02")
        # Disconnect stage 10 (out_of_order_mid_entry) from stage 20
        mq02["transitions"] = [t for t in mq02["transitions"] if t["from"] != 10]

        rep = cqf.evaluate_catalog(mutated, open_mode=False)
        self.assertTrue(
            any(de["quest_id"] == "MQ02" and de["state"] == "out_of_order_mid_entry" for de in rep["dead_ends"]),
            rep["dead_ends"],
        )

    def test_mutation_detects_open_mode_essential_npc_dead_end(self) -> None:
        mutated = copy.deepcopy(self.catalog)
        min00 = next(q for q in mutated["quests"] if q["id"] == "FO4SF_Min00")
        # Remove Open Mode fallback transitions while keeping Normal play intact
        min00["transitions"] = [t for t in min00["transitions"] if not t.get("open_mode_only", False)]

        normal_rep = cqf.evaluate_catalog(mutated, open_mode=False)
        self.assertEqual(normal_rep["dead_end_count"], 0, "Normal mode should still pass")

        open_rep = cqf.evaluate_catalog(mutated, open_mode=True)
        self.assertGreater(open_rep["open_mode_failure_count"], 0)
        self.assertTrue(
            any(
                f["quest_id"] == "FO4SF_Min00" and "FO4_PrestonGarvey" in f.get("dead_npcs", [])
                for f in open_rep["open_mode_failures"]
            ),
            open_rep["open_mode_failures"],
        )

    def test_mutation_detects_new_single_edge_fragility_and_single_route_reward(self) -> None:
        # Baseline: FO4SF_Sanctuary01 is NOT fragile, and VMS38 Pimp-Boy 3 Billion has 3 routes (0 fragile rewards)
        base = cqf.evaluate_catalog(self.catalog, open_mode=True)
        sanc_base = next(q for q in base["quests"] if q["id"] == "FO4SF_Sanctuary01")
        self.assertFalse(sanc_base["fragile"])
        vms38_base = next(q for q in base["quests"] if q["id"] == "VMS38")
        self.assertEqual(vms38_base["fragile_rewards"], [])

        # Mutate FO4SF_Sanctuary01 to leave only a single 10->100 edge
        mutated = copy.deepcopy(self.catalog)
        sanc = next(q for q in mutated["quests"] if q["id"] == "FO4SF_Sanctuary01")
        sanc["transitions"] = [
            t for t in sanc["transitions"] if t["kind"] in ("bootstrap_init", "primary")
        ]
        # Mutate VMS38 reward back to vanilla single route
        vms38 = next(q for q in mutated["quests"] if q["id"] == "VMS38")
        vms38["rewards"][0]["routes"] = ["vanilla_unmarked_mick_troike_chain"]
        vms38["rewards"][0]["single_sequence_only"] = True

        rep = cqf.evaluate_catalog(mutated, open_mode=True)
        sanc_mut = next(q for q in rep["quests"] if q["id"] == "FO4SF_Sanctuary01")
        self.assertTrue(sanc_mut["fragile"])
        self.assertTrue(any(ce["from"] == 10 and ce["to"] == 100 for ce in sanc_mut["fragile_cut_edges"]))

        vms38_mut = next(q for q in rep["quests"] if q["id"] == "VMS38")
        self.assertEqual(len(vms38_mut["fragile_rewards"]), 1)
        self.assertEqual(vms38_mut["fragile_rewards"][0]["reward_id"], "pimp_boy_3_billion")

    def test_cli_subprocess_exit_codes_and_json(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(CHECKER_PATH), "--catalog", str(CATALOG_PATH), "--open-mode", "--json"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["quests_checked"], 60)
        self.assertEqual(payload["dead_end_count"], 0)
        self.assertEqual(payload["fragile_count"], 18)

        # Text output decodes cleanly as UTF-8 on Windows cp1252 and POSIX pipes
        proc_txt = subprocess.run(
            [sys.executable, str(CHECKER_PATH), "--catalog", str(CATALOG_PATH), "--open-mode"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(proc_txt.returncode, 0, proc_txt.stderr)
        self.assertIn("FRAGILE LIST (18 quests):", proc_txt.stdout)
        self.assertNotIn("\u2014", proc_txt.stdout)

        # --fail-on-fragile returns exit code 2 when FRAGILE quests exist
        proc_frag = subprocess.run(
            [sys.executable, str(CHECKER_PATH), "--catalog", str(CATALOG_PATH), "--fail-on-fragile"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(proc_frag.returncode, 2)

        # Mutated catalog with dead end returns exit code 1
        mutated = copy.deepcopy(self.catalog)
        mutated["quests"][0]["transitions"] = []
        with tempfile.TemporaryDirectory() as tmp:
            bad_path = Path(tmp) / "bad_catalog.json"
            bad_path.write_text(json.dumps(mutated), encoding="utf-8")
            proc_bad = subprocess.run(
                [sys.executable, str(CHECKER_PATH), "--catalog", str(bad_path)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(proc_bad.returncode, 1)

    def test_docs_redaction_p3_and_tier_count_sync(self) -> None:
        all_files = [CHECKER_PATH, CATALOG_PATH, PLAN_PATH, REACH_PATH, HERE]
        for path in all_files:
            self.assertTrue(path.is_file(), f"missing deliverable {path}")
            txt = path.read_text(encoding="utf-8")
            self.assertIsNone(DRIVE_PATH_RX.search(txt), f"local drive path leaked in {path.name}")
            if path != HERE:
                for rx in FORBIDDEN_MOD_PATTERNS:
                    self.assertIsNone(rx.search(txt), f"forbidden mod pattern {rx.pattern} in {path.name}")

        plan_txt = PLAN_PATH.read_text(encoding="utf-8")
        # Verify exact tier counts appear in quest-test-plan.md
        for expected_token in ("**`60`**", "**`19`**", "**`48`**", "**`46`**", "**`18`**"):
            self.assertIn(expected_token, plan_txt)

        # P3 check on quest-test-plan.md: zero M/N/V in interactive console blocks,
        # and zero uppercase or standalone M/N/V hotkey tokens in bat remark lines
        console_blocks = 0
        bat_blocks = 0
        for lang, body in FENCED_BLOCK_RE.findall(plan_txt):
            lang_l = lang.strip().lower()
            if lang_l == "console":
                console_blocks += 1
                for line in body.splitlines():
                    s = line.strip()
                    if not s:
                        continue
                    self.assertIsNone(
                        re.search(r"[mnvMNV]", s),
                        f"P3 violation (M/N/V in console line): {s!r}",
                    )
            elif lang_l == "bat":
                bat_blocks += 1
                for line in body.splitlines():
                    s = line.strip()
                    if s.startswith(";"):
                        self.assertIsNone(
                            re.search(r"[MNV]|\b[mnv]\b", s),
                            f"P3 violation (hotkey M/N/V in bat remark): {s!r}",
                        )
        self.assertGreaterEqual(console_blocks, 25, "expected interactive console blocks for all 24 staged cases + template")
        self.assertGreaterEqual(bat_blocks, 25, "expected bat recipe blocks for all 24 staged cases + template")

        # Verify reachability-fixes.md documents RF-FNV-001 (Pimp-Boy 3 Billion) with 3 routes
        reach_txt = REACH_PATH.read_text(encoding="utf-8")
        self.assertIn("RF-FNV-001", reach_txt)
        self.assertIn("Pimp-Boy 3 Billion", reach_txt)
        for route_hdr in ("Route 1", "Route 2", "Route 3"):
            self.assertIn(route_hdr, reach_txt)


if __name__ == "__main__":
    unittest.main()
