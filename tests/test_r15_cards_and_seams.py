"""Round 15 Wave A Items 6, 7, 8 & Workshop Seam unit and card tests."""

from __future__ import annotations

import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "tests"), str(ROOT / "scripts" / "newgame")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import test_lead_cards_beginning as r11  # noqa: E402
import test_r11_cards_m_n_v_rule as mnv  # noqa: E402

SETTLEMENT_RULES_PATH = ROOT / "src" / "fo4sf" / "workshop" / "settlement_rules.json"
WORKSHOP_CS_PATH = ROOT / "dotnet" / "WorkshopCore" / "Program.cs"
WORKSHOP_PSC_PATH = ROOT / "scripts" / "workshop" / "FO4SF_WorkshopCoreQuest.psc"
NEWGAME_CS_PATH = ROOT / "dotnet" / "NewGame" / "Program.cs"
NEWGAME_PSC_PATH = ROOT / "scripts" / "newgame" / "FO4SF_NewGameQuest.psc"
CARD_2G_PATH = ROOT / "docs" / "testing" / "candidate-2g-card.md"
CARD_R11_PATH = ROOT / "docs" / "testing" / "round11-a1-a3-card.md"

DOTNET_ENABLED = os.environ.get("FO4SF_DOTNET_TESTS", "") == "1" and shutil.which("dotnet") is not None


class R15WorkshopSeamTests(unittest.TestCase):
    def test_settlement_rules_json_schema_and_sanctuary_seam(self) -> None:
        self.assertTrue(SETTLEMENT_RULES_PATH.is_file(), "missing src/fo4sf/workshop/settlement_rules.json")
        data = json.loads(SETTLEMENT_RULES_PATH.read_text(encoding="utf-8"))
        self.assertEqual(data.get("schema_version"), 1)

        settlements = data.get("settlements", [])
        self.assertGreaterEqual(len(settlements), 1)
        by_id = {s["id"]: s for s in settlements}
        self.assertIn("sanctuary_hills", by_id)
        sanc = by_id["sanctuary_hills"]
        self.assertEqual(int(sanc["workbench_ref_id"], 16), 0x005C50)
        self.assertEqual(int(sanc["clean_swap_bench_id"], 16), 0x000849)
        self.assertNotIn("clean_swap_bench_runtime_hex", sanc)
        self.assertEqual(int(sanc["swap_global_id"], 16), 0x00084A)
        self.assertEqual(float(sanc["build_radius_m"]), 250.0)

        attack_rules = data.get("attack_rules", [])
        self.assertGreaterEqual(len(attack_rules), 1)
        atk_ids = {r["id"] for r in attack_rules}
        self.assertIn(sanc["attack_rule_id"], atk_ids)
        for r in attack_rules:
            self.assertGreaterEqual(r["min_population"], 0)
            self.assertGreater(r["cooldown_game_hours"], 0.0)
            self.assertTrue(0.0 <= r["base_chance_pct"] <= 100.0)

        pop_rules = data.get("population_upgrade_rules", [])
        self.assertGreaterEqual(len(pop_rules), 3)
        tiers = [t["tier"] for t in pop_rules]
        min_pops = [t["min_population"] for t in pop_rules]
        self.assertEqual(tiers, sorted(tiers))
        self.assertEqual(len(set(tiers)), len(tiers))
        self.assertEqual(min_pops, sorted(min_pops))
        self.assertEqual(len(set(min_pops)), len(min_pops))

    def test_workshop_core_seam_wired_and_papyrus_has_no_hardcoded_settlement_table(self) -> None:
        cs = WORKSHOP_CS_PATH.read_text(encoding="utf-8")
        psc = WORKSHOP_PSC_PATH.read_text(encoding="utf-8")
        self.assertIn("--settlement-rules", cs)
        self.assertIn("--self-test", cs)
        self.assertIn("LoadSettlementRules", cs)
        self.assertIn("SettlementRulesTable", cs)
        self.assertIsNone(re.search(r"\b[A-Za-z]:[\\/]", cs), "drive path leaked in WorkshopCore/Program.cs")

        # FO4SF_WorkshopCoreQuest.psc tracks dynamic arrays only (no hardcoded settlement/attack/population tables)
        self.assertNotIn("sanctuary_hills", psc.lower())
        self.assertNotIn("attack_rules", psc.lower())
        self.assertNotIn("population_upgrade", psc.lower())

    @unittest.skipUnless(DOTNET_ENABLED, "requires FO4SF_DOTNET_TESTS=1 and dotnet")
    def test_dotnet_workshop_core_settlement_rules_self_test(self) -> None:
        with tempfile.TemporaryDirectory(prefix="r15-wscore-") as td:
            env = dict(os.environ)
            env.setdefault("DOTNET_ROLL_FORWARD", "Major")
            proc = subprocess.run(
                [
                    "dotnet", "run", "-c", "Release",
                    "--project", str(ROOT / "dotnet" / "WorkshopCore"),
                    "--", "--self-test", td,
                ],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + "\n" + proc.stderr)
            self.assertIn("selftest: ok", proc.stdout)
            synth = pathlib.Path(td) / "settlement_rules_synth.json"
            self.assertTrue(synth.is_file())
            synth_data = json.loads(synth.read_text(encoding="utf-8"))
            self.assertEqual(len(synth_data["settlements"]), 2)
            self.assertEqual(synth_data["settlements"][1]["id"], "red_rocket_truck_stop")


class R15WaveACardsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.card_2g = CARD_2G_PATH.read_text(encoding="utf-8")
        cls.card_r11 = CARD_R11_PATH.read_text(encoding="utf-8")

    def test_item6_10mm_coords_persistent_explanation_and_falling_drop(self) -> None:
        ng_cs = NEWGAME_CS_PATH.read_text(encoding="utf-8")
        ng_psc = NEWGAME_PSC_PATH.read_text(encoding="utf-8")
        self.assertIn("VaultPistolRefId = 0x820", ng_cs)
        self.assertIn("Vault10mmWeapId = 0x822", ng_cs)
        self.assertIn("Vault10mmAmmoCapacity = 12u", ng_cs)
        self.assertIn("Vault10mmAttackDamage = 18.0f", ng_cs)
        self.assertIn("-57.0338f, 30.006f, 1.29f", ng_cs)
        self.assertIn("pistolRef.MajorRecordFlagsRaw |= 0x400", ng_cs)
        self.assertIn("cellOver.Persistent.Add(pistolRef)", ng_cs)
        self.assertIn("cellOver.Persistent.Add(ammoRef)", ng_cs)
        self.assertIn("pistol picked", ng_psc)

        for tok in (
            "(-57.0338, 30.006, 1.29)",
            "0A000820",
            "0A000822",
            "0A000821",
            "18 dmg",
            "12-round",
            "02001607",
            "02001609",
            "0200160A",
            "02001539",
            "0x400",
            "bat r15p10",
            "bat r15drp",
            "1.00 g",
        ):
            self.assertIn(tok, self.card_2g, f"Card 2g-fix7 missing Item 6 token {tok!r}")

    def test_item7_obsolete_half_health_line_replaced_with_live_combat_expectation(self) -> None:
        stale_patterns = (
            r"half health at 30 s",
            r"half-health at 30 s",
            r">=\s*50%\s*HP\b[^\r\n]*30 s",
            r">=\s*100/200",
            r"dropping < 50% HP at 30 s",
            r"HP < 50%[^\r\n]*30 s",
        )
        for rel, txt in (("candidate-2g-card.md", self.card_2g), ("round11-a1-a3-card.md", self.card_r11)):
            for pat in stale_patterns:
                self.assertIsNone(
                    re.search(pat, txt, re.I),
                    f"{rel} still contains obsolete Concord expectation matching {pat!r}",
                )
            for tok in (">= 20", "10 s", "stage 30", "god mode OFF", "10mm Pistol"):
                self.assertIn(tok, txt, f"{rel} missing updated Item 7 combat expectation {tok!r}")
        self.assertIn("within `60` rounds", self.card_2g)
        self.assertIn("alive at `10 s`", self.card_2g)

    def test_item8_card_2g_fix7_covers_all_wave_a_items_logs_and_later_plugins(self) -> None:
        m = re.search(r"(?ms)^##\s+Card 2g-fix7 — Wave A Playable-0\.1 Blockers\b.*$", self.card_2g)
        self.assertIsNotNone(m, "docs/testing/candidate-2g-card.md missing '## Card 2g-fix7 — Wave A Playable-0.1 Blockers'")
        sec = m.group(0)

        self.assertEqual(mnv._check_mnv_scope(sec), [], "Card 2g-fix7 failed P3 M/N/V scope check")
        self.assertNotIn("<cand2g-fix7-test>", sec, "G2 forbids un-staged <cand2g-fix7-test> placeholder")

        required_tokens = (
            "REACHABLE",
            "TEST-STATION",
            "VIDEO",
            "--port <starfield-dir>\\Data\\FO4Port.esm --require-map-markers",
            "check_beginning_pilot.py check-bundle --bundle-dir <cand2g-fix7b-player>",
            "--textures-archive",
            "0. Preflight — Papyrus INI & 10 s Log Gate",
            "1. Wrist Pip-Boy",
            "2. Toasts & `QUEST` Label",
            "3. Silent Arrival, Silent Strip, Single-Pass Fade & Red Rocket Fix",
            "4. Lift Flow, Unspent S.P.E.C.I.A.L. Lock & Rising Arrival",
            "4b. Direct-Override Surface Lift Cog Bidirectional Up/Down",
            "5. Pod Safe Exit + Stage-15 Hook",
            "6. 10mm Pistol",
            "Starfield stand-in (XM-2311 / .45) until H4",
            "pushed, not run",
            "5 m+",
            "30+ fps",
            "7. Updated Concord Fight",
            "8. Structured Papyrus & SFSE Logs",
            "G13. Invisible Talk Proxy, Navmesh Snap, Weather & Jump Fallback",
            "bat g13p",
            "bEnableLogging=1",
            "bEnableTrace=1",
            "bLoadDebugInformation=1",
            "`10 s` of clicking New Game",
            "pipboy wrist equipped",
            "pipboy wrist reequip on_load",
            "codsworth01 objective10_toast skipped=true reason=already_displayed",
            "lift_pair reload recovered",
            "step=hud_quest_label",
            "arrival discovery silent=<bool>",
            "inventory starter_strip silent=<bool>",
            "story_fade single_pass=true",
            "ascent gap_closed=true",
            "lift_pair surface_cog ready",
            "lift_pair ride start",
            "lift_pair ride arrived",
            "pod_exit mode=<safe_spawn\\|cryopod_anim_hook> hook_stage=15",
            "pistol picked",
            "Later plug-in:",
            "not wired yet until H6",
            "settlement_rules.json",
        )
        for tok in required_tokens:
            self.assertIn(tok, sec, f"Card 2g-fix7 missing {tok!r}")

        # G3: every line citing bEnableLogging=1 in Card 2g-fix7 must also carry bEnableTrace=1 & bLoadDebugInformation=1
        def check_papyrus_keys(text: str) -> list[str]:
            bad: list[str] = []
            for ln in text.splitlines():
                if "bEnableLogging" in ln and ("bEnableTrace=1" not in ln or "bLoadDebugInformation=1" not in ln):
                    bad.append(ln.strip())
            return bad

        self.assertEqual(check_papyrus_keys(sec), [], "G3: bEnableLogging without bEnableTrace+bLoadDebugInformation")
        self.assertTrue(check_papyrus_keys("Enable [Papyrus] bEnableLogging=1 only"))

        # G3: every backticked pattern in Item 8 markdown log table must regex-match a source format string
        src_pats = r11.collect_source_format_patterns(ROOT)
        tbl_m = re.search(
            r"(?ms)^### Item 8 — Code-Verified Papyrus & SFSE Log Lines.*?\n(\|.*?)(?=\n### )",
            sec,
        )
        self.assertIsNotNone(tbl_m, "Missing Item 8 Code-Verified Log Lines Table")
        tbl_lines = [ln for ln in tbl_m.group(1).splitlines() if ln.startswith("| **")]
        self.assertGreaterEqual(len(tbl_lines), 20)

        def match_log_pattern(pline: str) -> bool:
            sample = r11._sample_from_card_line(pline)
            fixed = r11._extract_fixed_tokens(pline)
            return any(
                pat.search(sample) and all(r11._token_matches_template(ft, src_tpl) for ft in fixed)
                for _rel, src_tpl, pat in src_pats
            )

        # I6(a) / J3 replaced older log signatures on `#853`; `candidate-2g-card.md` retains the 2g-fix7 historical lines.
        superseded_2g_fix7 = {
            "FO4SF_MISSION rt=<rt> codsworth talk proxy model=none visible=false",
            "step=hud_quest_label_runtime file=<present|absent> file_ok=<0|1> mission_status=<txt> mission_new=<txt> runtime_ok=<0|1>",
        }
        unmatched = []
        for ln in tbl_lines:
            cells = [c.strip() for c in re.split(r"(?<!\\)\|", ln.strip().strip("|"))]
            pat_cell = cells[2].strip("`").replace(r"\|", "|")
            if pat_cell not in superseded_2g_fix7 and not match_log_pattern(pat_cell):
                unmatched.append(pat_cell)
        self.assertEqual(unmatched, [], f"G3 unmatched Item 8 table log patterns: {unmatched}")
        self.assertFalse(match_log_pattern("step=invented_fake_log foo=<bar>"))

        # Candidate 2h-4 card check: P3 zero M/N/V in console/bat names AND all Required PASS Log Lines match source
        card_2h = (ROOT / "docs" / "testing" / "candidate-2h-card.md").read_text(encoding="utf-8")
        from tests import test_r11_cards_m_n_v_rule as r11_mnv
        self.assertEqual(r11_mnv._check_mnv_scope(card_2h), [], "candidate-2h-card.md failed P3 M/N/V rule")
        log_blk_m = re.search(r"(?ms)^### Required PASS Log Lines.*?\n```log\n(.*?)\n```", card_2h)
        self.assertIsNotNone(log_blk_m, "Missing Required PASS Log Lines block in candidate-2h-card.md")
        unmatched_2h = [
            ln.strip() for ln in log_blk_m.group(1).splitlines()
            if ln.strip() and not match_log_pattern(ln.strip())
        ]
        self.assertEqual(unmatched_2h, [], f"candidate-2h-card.md unmatched Required PASS Log Lines: {unmatched_2h}")

        # G11: Vault 111 armory walk leg L10 in walk_headings.py & console-free-walk-list.md
        import walk_headings as wh
        cont = wh.check_route_continuity(wh.VAULT_ARMORY_WALK_SEGMENTS)
        self.assertTrue(cont["pass"], cont["issues"])
        self.assertEqual(cont["segment_count"], 6)
        self.assertIn("L10", cont["leg_totals_m"])
        walk_doc = (ROOT / "docs" / "testing" / "console-free-walk-list.md").read_text(encoding="utf-8")
        self.assertIn("pushed, not run", walk_doc)
        for ln in wh.format_markdown_table(wh.compute_route_rows(wh.VAULT_ARMORY_WALK_SEGMENTS)).splitlines():
            self.assertIn(ln, walk_doc, f"Missing L10 armory row in console-free-walk-list.md: {ln}")

        # Cross-check Card 2g-fix7 passes live R11 validation cleanly
        errs = r11.validate_lead_card_markdown(
            "docs/testing/candidate-2g-card.md",
            self.card_2g,
            help_runner=r11.HelpRunner(ROOT),
            source_patterns=src_pats,
            writer_edids=r11.collect_writer_symbols(ROOT)[0],
            writer_fids=r11.collect_writer_symbols(ROOT)[1],
            quest_stages=r11.collect_writer_symbols(ROOT)[2],
        )
        fix7_errs = [e for e in errs if "Card 2g-fix7" in e]
        self.assertEqual(fix7_errs, [], f"Card 2g-fix7 failed R11 validation: {fix7_errs}")


if __name__ == "__main__":
    unittest.main()
