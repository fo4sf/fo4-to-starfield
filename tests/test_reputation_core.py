"""Unit tests for Global Karma (-1000..+1000 in FO4SFCoreValues.esm) and 16-state Faction Reputation (FO4SFReputation.esm)."""
import os
import re
import stat
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "ui"))
sys.path.insert(0, str(REPO / "scripts" / "reputation"))

import make_pipboy_kit  # noqa: E402
import make_reputation_core  # noqa: E402
from fo4sf.combined import reputation as combined_rep  # noqa: E402
from fo4sf.reputation import (  # noqa: E402
    CORE_FACTIONS,
    FNV_REPU_RECORDS,
    FO76_TIER_TO_FAME_INFAMY,
    KARMA_TIERS,
    NV_16_STATE_MATRIX,
    PLUGIN_MASTERS,
    PLUGIN_NAME,
    RECORD_IDS,
    SHARED_CORE_FORM_IDS,
    STATE_BY_CODE,
    TITLE_REPUTATION_TABLES,
    build_shell_manifest,
    companion_moral_global,
    companion_reaction_for_alignment,
    evaluate_faction_reputation,
    evaluate_karma,
    fo76_tier_to_state,
    format_as3_data_reputation_rows,
    format_as3_stat_karma_entry,
    format_shell_tsv,
    inject_pipboy_kit_pages,
    parse_single_log,
    reputation_state_index,
    resolve_log_chain,
    slot_factions,
    stitch_and_evaluate_logs,
)

DOTNET_ENABLED = os.environ.get("FO4SF_DOTNET_TESTS") == "1"


class MatrixAndKarmaTests(unittest.TestCase):
    def test_all_16_matrix_cells_canonical_index_and_measured_gmst(self) -> None:
        expected = [
            # (fame, infamy, fame_t, inf_t, code, title, disposition, buy_mult, sell_mult, allow_trade)
            (0, 0, 0, 0, 0, "Neutral", "Neutral", 1.00, 1.00, True),
            (0, 20, 0, 1, 1, "Shunned", "Neutral", 1.25, 0.80, False),
            (0, 50, 0, 2, 2, "Hated", "Enemy", 1.50, 0.50, False),
            (0, 85, 0, 3, 3, "Vilified", "Enemy", 1.50, 0.00, False),
            (20, 0, 1, 0, 4, "Accepted", "Friend", 0.95, 1.05, True),
            (20, 20, 1, 1, 5, "mixed_fame1_infamy1", "Neutral", 1.00, 1.00, True),
            (20, 50, 1, 2, 6, "mixed_fame1_infamy2", "Neutral", 1.25, 0.80, False),
            (20, 85, 1, 3, 7, "mixed_fame1_infamy3", "Enemy", 1.40, 0.00, False),
            (50, 0, 2, 0, 8, "Liked", "Friend", 0.85, 1.15, True),
            (50, 20, 2, 1, 9, "mixed_fame2_infamy1", "Friend", 0.90, 1.10, True),
            (50, 50, 2, 2, 10, "mixed_fame2_infamy2", "Neutral", 1.05, 0.95, True),
            (50, 85, 2, 3, 11, "mixed_fame2_infamy3", "Neutral", 1.15, 0.85, True),
            (85, 0, 3, 0, 12, "Idolized", "Ally", 0.75, 1.25, True),
            (85, 20, 3, 1, 13, "mixed_fame3_infamy1", "Ally", 0.85, 1.15, True),
            (85, 50, 3, 2, 14, "mixed_fame3_infamy2", "Friend", 0.95, 1.05, True),
            (85, 85, 3, 3, 15, "mixed_fame3_infamy3", "Neutral", 1.00, 1.00, True),
        ]
        self.assertEqual(len(NV_16_STATE_MATRIX), 16)
        self.assertEqual(len(STATE_BY_CODE), 16)
        # Single shared 16-state matrix across reputation and combined modules
        self.assertIs(combined_rep.NV_16_STATE_MATRIX, NV_16_STATE_MATRIX)
        self.assertIs(combined_rep.FNV_REPU_RECORDS, FNV_REPU_RECORDS)

        for fame, infamy, ft, it, code, title, disp, buy_m, sell_m, trade in expected:
            self.assertEqual(reputation_state_index(ft, it), code)
            spec = evaluate_faction_reputation(fame, infamy)
            self.assertEqual(spec.code, code)
            self.assertEqual(spec.state_id, f"state_{code:02d}")
            self.assertEqual((spec.fame_tier, spec.infamy_tier), (ft, it))
            self.assertEqual(spec.title, title)
            self.assertEqual(spec.disposition, disp)
            self.assertAlmostEqual(spec.buy_mult, buy_m)
            self.assertAlmostEqual(spec.sell_mult, sell_m)
            self.assertEqual(spec.allow_trade, trade)
            if (ft, it) == (2, 3):
                self.assertEqual(spec.gmst_form_id, 0x0016951C)
                self.assertEqual(spec.gmst_edid, "sRepTitlePosTwoNegThreeDesc")
                self.assertEqual(spec.esm_status, "verified_gmst_edid")
            else:
                self.assertIsNone(spec.gmst_form_id)
                self.assertIsNone(spec.gmst_edid)
                self.assertEqual(spec.esm_status, "unverified")

        custom = evaluate_faction_reputation(30.0, 5.0, thresholds=(10.0, 25.0, 60.0))
        self.assertEqual(custom.title, "Liked")
        self.assertEqual(custom.code, 8)
        with self.assertRaises(ValueError):
            evaluate_faction_reputation(10.0, 10.0, thresholds=(50.0, 20.0, 80.0))

    def test_measured_fnv_13_repu_records_and_slot_builder(self) -> None:
        want_fnv = [
            (0, 0x0F2406, "RepNVPrimm", 30.0),
            (1, 0x0F43DD, "RepNVCaesarsLegion", 100.0),
            (2, 0x0F43DE, "RepNVNCR", 80.0),
            (3, 0x0FFAE8, "RepNVBoomer", 50.0),
            (4, 0x104C22, "RepNVGoodsprings", 15.0),
            (5, 0x116F16, "RepNVWhiteGloveSociety", 10.0),
            (6, 0x118F61, "RepNVTheStrip", 40.0),
            (7, 0x11989B, "RepNVGreatKhans", 30.0),
            (8, 0x11E662, "RepNVBrotherhood", 20.0),
            (9, 0x124AD1, "RepNVFollowers", 50.0),
            (10, 0x129A79, "RepNVNovac", 20.0),
            (11, 0x129A7A, "RepNVFreeside", 70.0),
            (12, 0x1558E6, "RepNVPowderGanger", 30.0),
        ]
        got_fnv = [(r["fnv_slot"], r["form_id"], r["edid"], r["pool_max"]) for r in FNV_REPU_RECORDS]
        self.assertEqual(got_fnv, want_fnv)
        self.assertEqual(len(slot_factions(8)), 8)
        fnv_slots = slot_factions(13)
        self.assertEqual(len(fnv_slots), 13)
        self.assertEqual([s["key"] for s in fnv_slots], [r[2] for r in want_fnv])
        self.assertEqual(fnv_slots[12]["fact_id"], 0x81C)
        with self.assertRaises(ValueError):
            slot_factions(0)
        with self.assertRaises(ValueError):
            slot_factions(16)

    def test_karma_thresholds_companions_and_endings(self) -> None:
        cases = [
            (-1500, -1000.0, -2, "Very Evil", 0x808, 0, -2),
            (-750, -750.0, -2, "Very Evil", 0x808, 0, -2),
            (-749, -749.0, -1, "Evil", 0x809, 1, -2),
            (-500, -500.0, -1, "Evil", 0x809, 1, -2),
            (-499, -499.0, -1, "Evil", 0x809, 1, -1),
            (-250, -250.0, -1, "Evil", 0x809, 1, -1),
            (-249, -249.0, 0, "Neutral", 0x80A, 2, 0),
            (0, 0.0, 0, "Neutral", 0x80A, 2, 0),
            (249, 249.0, 0, "Neutral", 0x80A, 2, 0),
            (250, 250.0, 1, "Good", 0x80B, 3, 0),
            (499, 499.0, 1, "Good", 0x80B, 3, 0),
            (500, 500.0, 1, "Good", 0x80B, 3, 1),
            (749, 749.0, 1, "Good", 0x80B, 3, 1),
            (750, 750.0, 2, "Very Good", 0x80C, 4, 1),
            (1400, 1000.0, 2, "Very Good", 0x80C, 4, 1),
        ]
        self.assertEqual(len(KARMA_TIERS), 5)
        for raw, clamped, tier, title, perk_id, slide, comp_code in cases:
            res = evaluate_karma(raw)
            self.assertEqual(res["karma"], clamped)
            self.assertEqual(res["tier"], tier)
            self.assertEqual(res["title"], title)
            self.assertEqual(res["perk_id"], perk_id)
            self.assertEqual(res["ending_slide"], slide)
            self.assertEqual(res["companion_global"], comp_code)
            self.assertEqual(companion_moral_global(raw), comp_code)

        self.assertEqual(companion_reaction_for_alignment(-600, "Good"), "leave")
        self.assertEqual(companion_reaction_for_alignment(-300, "Good"), "warn")
        self.assertEqual(companion_reaction_for_alignment(100, "Good"), "steady")
        self.assertEqual(companion_reaction_for_alignment(600, "Evil"), "warn")
        self.assertEqual(companion_reaction_for_alignment(-900, "Evil"), "steady")
        for k_val in (-950, 0, 950):
            self.assertEqual(companion_reaction_for_alignment(k_val, "Neutral"), "ignore")

    def test_very_evil_karma_stays_idolized_ally_with_discount(self) -> None:
        # Owner invariant: "a bad person can still be liked by certain groups"
        karma = evaluate_karma(-900.0)
        standing = evaluate_faction_reputation(fame=90.0, infamy=0.0)

        self.assertEqual(karma["title"], "Very Evil")
        self.assertEqual(karma["tier"], -2)
        self.assertEqual(karma["ending_slide"], 0)
        self.assertEqual(karma["good_companion"], "leave")

        self.assertEqual(standing.code, 12)
        self.assertEqual(standing.state_id, "state_12")
        self.assertEqual(standing.title, "Idolized")
        self.assertEqual(standing.disposition, "Ally")
        self.assertAlmostEqual(standing.buy_mult, 0.75)
        self.assertAlmostEqual(standing.sell_mult, 1.25)
        self.assertTrue(standing.allow_trade)
        self.assertIn("[Idolized]", standing.dialogue_tags)

    def test_all_seven_fallout_title_tables_and_fo76_curve(self) -> None:
        self.assertEqual(
            set(TITLE_REPUTATION_TABLES.keys()),
            {"FO1", "FO2", "Tactics", "FO3", "FNV", "FO4", "FO76"},
        )
        fnv = TITLE_REPUTATION_TABLES["FNV"]
        self.assertEqual(fnv["native_fact_count"], 682)
        self.assertEqual(fnv["native_repu_count"], 13)
        fnv_factions = list(fnv["factions"])
        self.assertEqual(len(fnv_factions), 13)
        self.assertEqual(len({entry["form_id"] for entry in fnv_factions}), 13)
        self.assertEqual([entry["fnv_slot"] for entry in fnv_factions], list(range(13)))
        self.assertTrue(all(float(entry["pool_max"]) >= 10.0 for entry in fnv_factions))

        self.assertEqual(TITLE_REPUTATION_TABLES["FO3"]["native_fact_count"], 326)
        self.assertEqual(TITLE_REPUTATION_TABLES["FO4"]["native_fact_count"], 699)
        self.assertEqual(TITLE_REPUTATION_TABLES["FO4"]["native_repu_count"], 0)
        self.assertEqual(TITLE_REPUTATION_TABLES["FO76"]["native_fact_count"], 954)

        for title_key, table in TITLE_REPUTATION_TABLES.items():
            factions = list(table["factions"])
            self.assertGreaterEqual(len(factions), 1, title_key)
            if title_key != "FNV":
                for fac in factions:
                    slot = int(fac["core_slot"])
                    self.assertGreaterEqual(slot, 0)
                    self.assertLess(slot, len(CORE_FACTIONS))

        self.assertEqual(len(FO76_TIER_TO_FAME_INFAMY), 7)
        self.assertEqual(fo76_tier_to_state("Hostile").disposition, "Enemy")
        self.assertEqual(fo76_tier_to_state("Caution").disposition, "Enemy")
        self.assertEqual(fo76_tier_to_state("Neutral").title, "Neutral")
        self.assertEqual(fo76_tier_to_state("Cooperative").title, "Accepted")
        self.assertEqual(fo76_tier_to_state("Friendly").title, "Liked")
        self.assertEqual(fo76_tier_to_state("Neighborly").title, "Liked")
        self.assertEqual(fo76_tier_to_state("Ally").title, "Idolized")


class CrossLayerParityAndPipboyTests(unittest.TestCase):
    def test_csharp_papyrus_python_formid_and_identifier_parity(self) -> None:
        cs_text = (REPO / "dotnet" / "ReputationCore" / "Program.cs").read_text(encoding="utf-8")
        psc_text = (REPO / "scripts" / "reputation" / "FO4SF_ReputationQuest.psc").read_text(encoding="utf-8")

        self.assertEqual(PLUGIN_MASTERS, ("Starfield.esm", "FO4SFCoreValues.esm"))
        self.assertEqual(SHARED_CORE_FORM_IDS, {
            "KarmaAvId": 0x000830,
            "KarmaValueGlobId": 0x000831,
            "KarmaTierGlobId": 0x000832,
            "TestModeGlobId": 0x000860,
        })
        for removed_key in ("RepKarmaAvId", "KarmaValueGlobId", "KarmaTierGlobId"):
            self.assertNotIn(removed_key, RECORD_IDS)

        for const_name, val in RECORD_IDS.items():
            hex_pat = rf"\b{re.escape(const_name)}\s*=\s*0x0*{val:X}\b"
            self.assertRegex(cs_text, re.compile(hex_pat, re.IGNORECASE), f"C# FormID drift for {const_name}")

        psc_expected = {
            "CoreKarmaAvId": 0x830,
            "CoreKarmaValueGlobId": 0x831,
            "CoreKarmaTierGlobId": 0x832,
            "EndingSlideGlobId": 0x804,
            "VendorBuyMultAvId": 0x805,
            "RepVendorPerkId": 0x806,
            "CompanionMoralGlobId": 0x807,
            "KarmaPerkFirstId": 0x808,
            "FactFirstId": 0x810,
            "FameAvFirstId": 0x820,
            "InfamyAvFirstId": 0x830,
            "StateAvFirstId": 0x840,
            "FameGlobFirstId": 0x850,
            "InfamyGlobFirstId": 0x860,
            "StateGlobFirstId": 0x870,
            "CharityTokenId": 0x880,
            "TheftTokenId": 0x881,
            "FactionAidTokenId": 0x882,
            "FactionCrimeTokenId": 0x883,
            "RepTokenListId": 0x88F,
        }
        for name, val in psc_expected.items():
            self.assertRegex(psc_text, re.compile(rf"\b{name}\s*=\s*0x0*{val:X}\b", re.IGNORECASE))

        self.assertNotIn("FO4SFProgression.esm", psc_text)
        self.assertIn("AddInventoryEventFilter(CachedTokenList)", psc_text)
        self.assertIn("TestModeGlobal == None || TestModeGlobal.GetValue() == 0.0", psc_text)

        # Verify OnItemAdded does ZERO per-item GetFormFromFile lookups
        m_item = re.search(r"Event\s+ObjectReference\.OnItemAdded\b.*?\nEndEvent", psc_text, re.S)
        self.assertIsNotNone(m_item)
        self.assertNotIn("GetFormFromFile", m_item.group(0))

        for hook in (
            "Function OnQuestStageEvent(",
            "Function OnFactionKill(",
            "Function OnTheftObserved(",
            "Event Actor.OnPlayerLoadGame(",
            "FO4SFCoreValues.esm",
        ):
            self.assertIn(hook, psc_text)

        # Ensure zero Papyrus reserved class names are used as variable or parameter names
        reserved = {"race", "cell", "form", "actor", "quest", "faction", "perk", "formlist"}
        decl_re = re.compile(r"^\s*(?:int|float|bool|string|Form|Actor|Faction|Perk|ActorValue|GlobalVariable)\s+([A-Za-z0-9_]+)", re.M)
        for ident in decl_re.findall(psc_text):
            if ident == "Property":
                continue
            self.assertNotIn(ident.lower(), reserved, f"reserved Papyrus identifier used: {ident}")

    def test_pipboy_kit_ini_and_as3_shell_formatters(self) -> None:
        shipped_ini = (REPO / "sfse" / "FO4SFPipboyMenu" / "FO4SFPipboyMenu.ini").read_text(encoding="utf-8")
        injected_once = inject_pipboy_kit_pages(shipped_ini, load_index=0x0C, core_load_index=0x02)
        injected_twice = inject_pipboy_kit_pages(injected_once, load_index=0x0C, core_load_index=0x02)
        self.assertEqual(injected_once, injected_twice)

        kit = make_pipboy_kit.parse_kit(injected_once)
        page_keys = [(p["tab"], p["sub"]) for p in kit["pages"]]
        self.assertIn(("STAT", "KARMA"), page_keys)
        self.assertIn(("DATA", "REPUTATION"), page_keys)

        stat_karma = next(p for p in kit["pages"] if (p["tab"], p["sub"]) == ("STAT", "KARMA"))
        self.assertEqual(stat_karma["rows"][0], ("GLOBAL KARMA", "av:02000830"))
        self.assertEqual(stat_karma["rows"][1], ("VENDOR BUY MULT", "av:0C000805"))

        data_rep = next(p for p in kit["pages"] if (p["tab"], p["sub"]) == ("DATA", "REPUTATION"))
        self.assertEqual(len(data_rep["rows"]), 24)
        self.assertEqual(data_rep["rows"][0], ("MINUTEMEN FAME", "av:0C000820"))

        # 13-slot FNV Pip-Boy kit validation
        fnv_ini = inject_pipboy_kit_pages(shipped_ini, load_index=0x0C, core_load_index=0x02, slot_count=13)
        fnv_kit = make_pipboy_kit.parse_kit(fnv_ini)
        fnv_rep = next(p for p in fnv_kit["pages"] if (p["tab"], p["sub"]) == ("DATA", "REPUTATION"))
        self.assertEqual(len(fnv_rep["rows"]), 39)

        tsv = format_shell_tsv()
        self.assertEqual(len(tsv.strip().splitlines()), 10)  # header + GlobalKarma + 8 factions
        manifest = build_shell_manifest()
        self.assertEqual(manifest["plugin"], PLUGIN_NAME)
        self.assertEqual(manifest["core_values_plugin"], "FO4SFCoreValues.esm")
        self.assertEqual(len(manifest["data_stats_reputation"]["states"]), 16)

        stat_obj = format_as3_stat_karma_entry(-800.0)
        self.assertEqual(stat_obj["text"], "Karma: Very Evil (-800)")
        self.assertEqual(stat_obj["rank"], 1)
        self.assertEqual(stat_obj["maxRank"], 5)

        data_rows = format_as3_data_reputation_rows(-800.0, {"Minutemen": (85.0, 0.0), "Legion": (0.0, 50.0)})
        self.assertEqual(data_rows[0]["value"], "-800")
        self.assertIn("Minutemen: Idolized", [r["text"] for r in data_rows])
        self.assertIn("Legion: Hated", [r["text"] for r in data_rows])


class LogStitchingAndStageCliTests(unittest.TestCase):
    def test_log_stitching_across_save_quit_reload_and_failures(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            log1 = root / "FO4SFReputation.1.log"
            log0 = root / "FO4SFReputation.0.log"
            pap = root / "Papyrus.0.log"

            log1.write_text(
                "\n".join(
                    [
                        "FO4SF_REPUTATION rt=10.1 init version=1 quest=167774208 installed=true core_installed=true states=0,0,0,0,0,0,0,0 end=true",
                        "FO4SF_REPUTATION rt=12.4 orthogonality_proof karma=-800 tier=-2 fac=0 state=12 disp=Ally reaction=2 buy_mult=0.75 ok=true end=true",
                        "FO4SF_REPUTATION rt=14.0 quest_hook src=stage20 fac=1 state=8 reaction=3 buy_mult=0.85 karma=-500 tier=-1 states=12,8,0,0,0,0,0,0 end=true",
                        "FO4SF_REPUTATION rt=15.5 kill_hook fac=6 innocent=false state=2 karma=-500 tier=-1 states=12,8,0,0,0,0,2,0 end=true",
                        "FO4SF_REPUTATION rt=17.0 theft_hook fac=4 val=100 witnessed=true state=1 karma=-515 tier=-1 states=12,8,0,0,1,0,2,0 end=true",
                        "FO4SF_REPUTATION rt=18.2 status_dump karma=-515 tier=-1 slide=1 comp=-2 active_fac=1 buy_mult=0.85 fac0_react=2 states=12,8,0,0,1,0,2,0 end=true",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            time.sleep(0.02)
            log0.write_text(
                "FO4SF_REPUTATION rt=4.3 reload_audit karma=-515 tier=-1 slide=1 comp=-2 active_fac=1 buy_mult=0.85 fac0_react=2 states=12,8,0,0,1,0,2,0 ok=true end=true\n",
                encoding="utf-8",
            )
            pap.write_text("[00:00:01] Papyrus log opened cleanly.\n", encoding="utf-8")

            chain = resolve_log_chain(str(log0))
            self.assertEqual(chain, [str(log1), str(log0)])
            rc = make_reputation_core.main(["log", "--file", str(log0), "--papyrus-log", str(pap), "--require-hooks"])
            self.assertEqual(rc, 0)

            # Negative 1: State drift after reload -> FAIL
            log0_drift = root / "drift.0.log"
            log0_drift.write_text(
                "FO4SF_REPUTATION rt=4.3 reload_audit karma=-515 tier=-1 states=0,0,0,0,0,0,0,0 buy_mult=1.0 ok=true end=true\n",
                encoding="utf-8",
            )
            rep_drift = stitch_and_evaluate_logs([str(log1), str(log0_drift)])
            self.assertEqual(rep_drift["verdict"], "FAIL")

            # Negative 2: Truncated line lacking end=true -> FAIL
            recs, trunc = parse_single_log("FO4SF_REPUTATION rt=9.1 status_dump karma=-515 states=12,8,0,0,1,0,2,0")
            self.assertEqual(len(recs), 0)
            self.assertEqual(trunc, 1)

            # Negative 3: Non-innocent kill_hook mutating Karma -> FAIL
            bad_kill = root / "bad_kill.0.log"
            bad_kill.write_text(
                "\n".join(
                    [
                        "FO4SF_REPUTATION rt=1.0 orthogonality_proof karma=-800 tier=-2 fac=0 state=12 disp=Ally reaction=2 buy_mult=0.75 ok=true end=true",
                        "FO4SF_REPUTATION rt=2.0 kill_hook fac=6 innocent=false state=2 karma=-900 tier=-2 states=12,0,0,0,0,0,2,0 end=true",
                        "FO4SF_REPUTATION rt=3.0 reload_audit karma=-900 tier=-2 states=12,0,0,0,0,0,2,0 buy_mult=0.75 ok=true end=true",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            self.assertEqual(stitch_and_evaluate_logs([str(bad_kill)])["verdict"], "FAIL")

    @unittest.skipUnless(DOTNET_ENABLED, "set FO4SF_DOTNET_TESTS=1 to run ReputationCore C# selftest & stage tests")
    def test_dotnet_selftest_and_stage_verify_tamper_guards(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            # 1. C# ReputationCore selftest (byte-identical 8-slot, 13-slot FNV, --no-test-cell, + 3 negative tamper checks)
            out_txt = make_reputation_core.run_dotnet_reputation("selftest", str(root / "selftest"))
            self.assertIn("selftest pass", out_txt)

            # 2. Synthetic Starfield.esm + fake Papyrus compiler -> stage + verify + tamper refusal
            fix_dir = root / "fixture"
            make_reputation_core.run_dotnet_reputation("fixture", str(fix_dir))
            sf_esm = fix_dir / "Starfield.esm"

            res_zip = root / "ContentResources.zip"
            with zipfile.ZipFile(res_zip, "w") as zf:
                zf.writestr("Scripts/Source/Starfield_Papyrus_Flags.flg", "Flags {}\n")
                zf.writestr("Scripts/Source/Quest.psc", "Scriptname Quest\n")

            helper_py = root / "fake_compiler_impl.py"
            helper_py.write_text(
                "import pathlib, sys\n"
                "args = sys.argv[1:]\n"
                "out = None\n"
                "for idx, tok in enumerate(args):\n"
                "    if tok.startswith('-o=') and len(tok) > 3:\n"
                "        out = tok[3:]\n"
                "    elif tok == '-o' and idx + 1 < len(args):\n"
                "        out = args[idx + 1]\n"
                "(pathlib.Path(out) / 'FO4SF_ReputationQuest.pex').write_bytes(b'PEXDATA')\n"
                "print('Compilation succeeded.')\n",
                encoding="utf-8",
            )
            fake_comp = root / ("fake_compiler.cmd" if os.name == "nt" else "fake_compiler.sh")
            if os.name == "nt":
                fake_comp.write_text(
                    f'@echo off\r\n"{sys.executable}" "{helper_py}" %*\r\n',
                    encoding="utf-8",
                )
            else:
                fake_comp.write_text(
                    f'#!/bin/sh\nexec "{sys.executable}" "{helper_py}" "$@"\n',
                    encoding="utf-8",
                )
                fake_comp.chmod(fake_comp.stat().st_mode | stat.S_IEXEC)

            stage_dir = root / "stage"
            rc_stage = make_reputation_core.main(
                [
                    "stage",
                    "--out",
                    str(stage_dir),
                    "--starfield",
                    str(sf_esm),
                    "--compiler",
                    str(fake_comp),
                    "--content-resources",
                    str(res_zip),
                ]
            )
            self.assertEqual(rc_stage, 0)

            rc_ver = make_reputation_core.main(
                ["verify", "--stage", str(stage_dir), "--starfield", str(sf_esm), "--run-dotnet-check"]
            )
            self.assertEqual(rc_ver, 0)

            # 13-slot FNV + --no-test-cell stage & verify
            stage_fnv = root / "stage_fnv_player"
            self.assertEqual(
                make_reputation_core.main(
                    [
                        "stage",
                        "--out",
                        str(stage_fnv),
                        "--starfield",
                        str(sf_esm),
                        "--compiler",
                        str(fake_comp),
                        "--content-resources",
                        str(res_zip),
                        "--slot-count",
                        "13",
                        "--no-test-cell",
                    ]
                ),
                0,
            )
            self.assertEqual(
                make_reputation_core.main(
                    [
                        "verify",
                        "--stage",
                        str(stage_fnv),
                        "--starfield",
                        str(sf_esm),
                        "--run-dotnet-check",
                        "--slot-count",
                        "13",
                        "--no-test-cell",
                    ]
                ),
                0,
            )

            # Refusal on existing output directory
            self.assertEqual(
                make_reputation_core.main(
                    [
                        "stage",
                        "--out",
                        str(stage_dir),
                        "--starfield",
                        str(sf_esm),
                        "--compiler",
                        str(fake_comp),
                        "--content-resources",
                        str(res_zip),
                    ]
                ),
                1,
            )

            # Refusal on unexpected extra file
            extra = stage_dir / "stray.txt"
            extra.write_text("stray", encoding="utf-8")
            self.assertEqual(make_reputation_core.main(["verify", "--stage", str(stage_dir)]), 1)
            extra.unlink()
            self.assertEqual(make_reputation_core.main(["verify", "--stage", str(stage_dir)]), 0)

            # Refusal on byte tamper of FO4SFReputation.esm
            esm_file = stage_dir / PLUGIN_NAME
            esm_file.write_bytes(esm_file.read_bytes() + b"\x00")
            self.assertEqual(make_reputation_core.main(["verify", "--stage", str(stage_dir)]), 1)

    def test_public_surface_cleanliness(self) -> None:
        owned_files = [
            *sorted((REPO / "src" / "fo4sf" / "reputation").glob("*.py")),
            *sorted((REPO / "dotnet" / "ReputationCore").glob("*.*")),
            *sorted((REPO / "scripts" / "reputation").glob("*.*")),
            *sorted((REPO / "docs" / "reputation").glob("*.md")),
            Path(__file__).resolve(),
        ]
        self.assertGreaterEqual(len(owned_files), 10)
        banned_patterns = [
            re.compile(r"\b[A-Za-z]:" + r"[\\/]"),
            re.compile(r"/(?:users|home)/", re.I),
            re.compile(r"steam" + r"library", re.I),
            re.compile(r"fo4sf" + r"-", re.I),
            re.compile(r"\bfal" + r"-", re.I),
            re.compile(r"paper" + r"clip", re.I),
            re.compile(r"ts\." + r"net", re.I),
            re.compile(r"\bmod" + r"ding\b", re.I),
            re.compile(r"\bgr" + r"eat\b", re.I),
            re.compile(r"\baa" + r"ron\b", re.I),
            re.compile(r"\bufo" + r"4p\b", re.I),
            re.compile(r"\by" + r"up\b", re.I),
            re.compile(r"fallout\s+" + r"london", re.I),
            re.compile(r"tale\s+of\s+two\s+" + r"wastelands", re.I),
        ]
        for fp in owned_files:
            txt = fp.read_text(encoding="utf-8")
            for pat in banned_patterns:
                m = pat.search(txt)
                self.assertIsNone(m, f"forbidden pattern {pat.pattern!r} matched in {fp.name}: {m}")


if __name__ == "__main__":
    unittest.main()
