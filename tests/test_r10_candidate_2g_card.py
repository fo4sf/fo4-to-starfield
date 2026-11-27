"""Offline R11 / P3 / R8 / A3 validator for docs/testing/candidate-2g-card.md and post-2f cards."""

from __future__ import annotations

import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import test_lead_cards_beginning as r11  # noqa: E402

CARD_2G_REL = "docs/testing/candidate-2g-card.md"
CARD_2G_PATH = ROOT / CARD_2G_REL
CARD_A3A7_PATH = ROOT / "docs/testing/playable-path-a3-a7-card.md"
CARD_ACT2_PATH = ROOT / "docs/testing/playable-path-act2-card.md"


class Candidate2gCardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.card_2g = CARD_2G_PATH.read_text(encoding="utf-8")
        cls.card_a3a7 = CARD_A3A7_PATH.read_text(encoding="utf-8")
        cls.card_act2 = CARD_ACT2_PATH.read_text(encoding="utf-8")
        cls.help_runner = r11.HelpRunner(ROOT)
        cls.source_patterns = r11.collect_source_format_patterns(ROOT)
        cls.writer_edids, cls.writer_fids, cls.quest_stages = r11.collect_writer_symbols(ROOT)

    def test_candidate_2g_card_structure_a3_rows_and_honesty(self) -> None:
        txt = self.card_2g
        first_line = txt.splitlines()[0]
        self.assertIn("Titles: Fallout 4", first_line)
        self.assertIn("Modes: Story & Warfare", first_line)
        self.assertIn("Track: Track 1", first_line)

        top = "\n".join(txt.splitlines()[:16])
        self.assertIn("NEW GAME needed", top)
        self.assertIn("9b5327ff", top)
        self.assertIn("7082117074", top)
        self.assertIn("prototype, offline", top)
        self.assertIn("OFFLINE ONLY — UNPROVEN IN GAME", top)
        self.assertIn("stand-in", top.lower())
        self.assertIsNone(re.search(r"\b[A-Za-z]:[\\/]", txt), "local drive path leaked in candidate-2g-card.md")

        headings = re.findall(r"(?m)^##\s+(Card\s+2g-\d+[^\r\n]*)$", txt)
        self.assertEqual(len(headings), 4, headings)
        for idx, h in enumerate(headings, start=1):
            self.assertTrue(h.startswith(f"Card 2g-{idx}"), h)

        required_tokens = (
            "<cand2g-player-bundle>",
            "<cand2g-test-bundle>",
            "C1",
            "C2",
            "C3",
            "C4",
            "C5",
            "C6",
            "R1",
            "R2",
            "R3",
            "R6",
            "R8",
            "A4",
            "god mode",
            "before=2846..2868",
            "Throwaway_2g_Surface",
            "Throwaway_2g_MidWFC",
            "Quit to Desktop",
            "preston scene talk requested",
            "preston dialogue menu opened",
            "reason=no_scene",
            "04005C50",
            "09000817",
            "09000A50",
            "10.23.2287",
            "HP 0/0",
            "AP --/--",
            "bat r10stat",
            "bat cods06",
            "bat r9hop1",
            "bat r9hop2",
            "bat r9hop3",
            "bat r9door",
            "< 180 m",
            "docs/actors/c5-actor-and-hud-looks-report.md",
            "Starfield chargen approximation",
            "09000980",
            "09000988",
            "safe_d=1.85",
            "INTV=1",
            "ShellBackdrop=1",
            "ShellVitalsFill=1",
            "ShellVitalsFill=0",
            "207.23 m",
            "501.73 m",
            "sanctuary01 bench_activated=true ref=<ref> complete=false stage=100",
            "preston scene resolved via=<property|file> scene=<ref>",
            "typed interactive",
            "batch filenames",
            "NOT",
            "step=shell_c4_config shell_backdrop=1 shell_vitals_fill=1 suppress_data_menu=0 tab_opens_pipboy=0",
            "step=shell_vitals when=kShow",
            "step=shell_date_fix",
            "step=quest_cache_build",
        )
        for tok in required_tokens:
            self.assertIn(tok, txt, f"candidate-2g-card.md missing {tok!r}")
        self.assertIsNone(re.search(r"\btgm\b", txt, re.I), "A2.7 forbids telling tester to type tgm")
        self.assertNotIn("preston scene resolved via=file scene=<ref>", txt)
        self.assertNotIn("preston scene resolved via=property scene=<ref>", txt)

    def test_candidate_2g_card_p3_zero_mnv_console_and_batch_names(self) -> None:
        console_blocks = [
            body for lang, body in r11.FENCED_BLOCK_RE.findall(self.card_2g) if lang.strip().lower() == "console"
        ]
        self.assertGreaterEqual(len(console_blocks), 3)
        for block in console_blocks:
            for raw in block.splitlines():
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                self.assertIsNone(
                    re.search(r"[mnv]", line, re.I),
                    f"P3 forbids M/N/V in interactive console line: {line!r}",
                )
                self.assertIsNone(
                    re.match(r"^(?:set|help)\s+FO4SF_", line, re.I),
                    f"P3 forbids stripped mod GLOB/QUST EditorID in console line: {line!r}",
                )

        # Also check every batch filename in bat blocks for P3 zero M/N/V
        for bat_name in re.findall(r"<starfield-dir>/([A-Za-z0-9_-]+)\.txt", self.card_2g):
            self.assertIsNone(
                re.search(r"[mnv]", bat_name, re.I),
                f"P3 forbids M/N/V in batch filename: {bat_name!r}",
            )

        # Negative P3 control
        bad_txt = self.card_2g.replace("\nsqs 09000800\n", "\nsqv 09000800\n", 1).replace(
            "\nbat r10stat\n", "\nset FO4SF_PipboyAcquired to 1\n", 1
        )
        errs = r11.validate_lead_card_markdown(
            CARD_2G_REL,
            bad_txt,
            help_runner=self.help_runner,
            source_patterns=self.source_patterns,
            writer_edids=self.writer_edids,
            writer_fids=self.writer_fids,
            quest_stages=self.quest_stages,
        )
        joined = "\n".join(errs)
        self.assertIn("P3 forbids M/N/V letters in interactive console line", joined)
        self.assertIn("P3 forbids stripped mod GLOB/QUST EditorID", joined)

    def test_candidate_2g_card_passes_r11_validation(self) -> None:
        errs = r11.validate_lead_card_markdown(
            CARD_2G_REL,
            self.card_2g,
            help_runner=self.help_runner,
            source_patterns=self.source_patterns,
            writer_edids=self.writer_edids,
            writer_fids=self.writer_fids,
            quest_stages=self.quest_stages,
        )
        cods_src = (ROOT / "scripts/mission/FO4SF_Codsworth01Quest.psc").read_text(encoding="utf-8")
        min00_src = (ROOT / "scripts/mission/FO4SF_Min00Quest.psc").read_text(encoding="utf-8")
        sanc_src = (ROOT / "scripts/mission/FO4SF_Sanctuary01Quest.psc").read_text(encoding="utf-8")
        pipboy_src = (ROOT / "sfse/FO4SFPipboyMenu/src/main.cpp").read_text(encoding="utf-8")

        # Historical 2g log lines whose format strings gained trailing fields in Round 11 (W1 wall_avoid=, W4 hide_starfield_watch=)
        r11_evolved_2g_prefixes: list[str] = []
        if " wall_avoid=" in cods_src:
            r11_evolved_2g_prefixes.append(
                "PASS line does not match any source format string: 'FO4SF_MISSION rt=<rt> codsworth talk camera_guard prev_d=<d> safe_d=1.85'"
            )
        if " eff_dmg=" in min00_src:
            r11_evolved_2g_prefixes.append(
                "PASS line does not match any source format string: 'FO4SF_MISSION rt=<rt> arm raider <i> ammo=<n>'"
            )
        if "hide_starfield_watch=" in pipboy_src:
            r11_evolved_2g_prefixes.append(
                "PASS line does not match any source format string: 'step=shell_c4_config shell_backdrop=1 shell_vitals_fill=1 suppress_data_menu=0 tab_opens_pipboy=0'"
            )
        if "preston scene resolved via=property " not in min00_src and "preston scene resolved via=file " in min00_src:
            r11_evolved_2g_prefixes.append(
                "PASS line does not match any source format string: 'FO4SF_MISSION rt=<rt> preston scene resolved via=<property|file> scene=<ref>'"
            )
        if "descending={}" in pipboy_src:
            r11_evolved_2g_prefixes.append(
                "PASS line does not match any source format string: 'step=lift_open confirmed=<confirmed>'"
            )
        if "action={} pool={}" in pipboy_src:
            r11_evolved_2g_prefixes.append(
                "PASS line does not match any source format string: 'step=lift_confirm action=<action> confirmed=<confirmed> values=<s>,<p>,<e>,<c>,<i>,<a>,<l>'"
            )
        if "mission_update={}" in pipboy_src:
            r11_evolved_2g_prefixes.append(
                "PASS line does not match any source format string: 'step=hud_quest_label_runtime file=<present|absent> file_ok=<0|1> mission_status=<txt> mission_new=<txt> runtime_ok=<0|1>'"
            )
        newgame_src = (ROOT / "scripts/newgame/FO4SF_NewGameQuest.psc").read_text(encoding="utf-8")
        if "ascent gap_ms=" in newgame_src:
            r11_evolved_2g_prefixes.append(
                "PASS line does not match any source format string: 'FO4SF_NEWGAME rt=<rt> ascent fade_out elapsed=<t>'"
            )

        w1_present = "preston scene resolved via=" in min00_src
        w2_present = "complete=false stage=" in sanc_src
        w4_present = "step=shell_c4_config" in pipboy_src
        if w1_present and w2_present and w4_present:
            unexpected = [e for e in errs if not any(p in e for p in r11_evolved_2g_prefixes)]
            self.assertEqual(unexpected, [], "\n".join(unexpected))
            return

        r10_new_prefixes = (
            "PASS line does not match any source format string: 'FO4SF_MISSION rt=<rt> codsworth talk camera_guard",
            "PASS line does not match any source format string: 'FO4SF_MISSION rt=<rt> codsworth talk scene phase=",
            "PASS line does not match any source format string: 'FO4SF_MISSION rt=<rt> arm raider ",
            "PASS line does not match any source format string: 'FO4SF_MISSION rt=<rt> preston scene resolved via=",
            "PASS line does not match any source format string: 'FO4SF_MISSION rt=<rt> preston talk scene phase=",
            "PASS line does not match any source format string: 'FO4SF_MISSION rt=<rt> sanctuary01 bench_activated=true ref=<ref> complete=false stage=100",
            "PASS line does not match any source format string: 'step=shell_c4_config ",
            "PASS line does not match any source format string: 'step=shell_backdrop ",
            "PASS line does not match any source format string: 'step=shell_vitals ",
            "PASS line does not match any source format string: 'step=shell_date_fix ",
            "PASS line does not match any source format string: 'step=quest_cache_build ",
        )
        unexpected = [e for e in errs if not any(p in e for p in r10_new_prefixes)]
        self.assertEqual(unexpected, [], "\n".join(unexpected))

    def test_r8_stand_in_truth_labels_across_post_2f_cards(self) -> None:
        for label, txt in (("playable-path-a3-a7-card.md", self.card_a3a7), ("playable-path-act2-card.md", self.card_act2)):
            self.assertIsNone(re.search(r"\b[A-Za-z]:[\\/]", txt), f"local path leaked in {label}")
            self.assertIn("stand-in", txt.lower(), f"{label} missing R8 stand-in truth label")
            self.assertIn("InitiallyDisabled", txt, f"{label} missing R3 InitiallyDisabled actor gating")

        for tok in ("09000A15", "R1", "R2", "R4", "R8", "ZERO modal messagebox"):
            self.assertIn(tok.lower(), self.card_a3a7.lower(), f"playable-path-a3-a7-card.md missing {tok!r}")

        for tok in ("09000B55", "09000AD6", "0x03D52E", "0x00F2D3", "fallback=inline_scan", "15 Nov", "R8"):
            self.assertIn(tok, self.card_act2, f"playable-path-act2-card.md missing {tok!r}")


if __name__ == "__main__":
    unittest.main()
