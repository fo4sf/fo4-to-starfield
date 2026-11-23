"""Round 11 A2.7 / R11 / P3 / A3 / candidate-2g-fix card validator."""

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
CARD_R11_REL = "docs/testing/round11-a1-a3-card.md"
CARD_2G_PATH = ROOT / CARD_2G_REL
CARD_R11_PATH = ROOT / CARD_R11_REL


def _extract_blocks(md_text: str, lang: str) -> list[str]:
    want = lang.strip().lower()
    return [body for blk_lang, body in r11.FENCED_BLOCK_RE.findall(md_text) if blk_lang.strip().lower() == want]


def _check_mnv_scope(md_text: str) -> list[str]:
    """Enforce P3 M/N/V strictly on typed ```console lines and batch filenames (NOT ```bat contents)."""
    errs: list[str] = []
    for body in _extract_blocks(md_text, "console"):
        for raw in body.splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if re.search(r"[mnv]", line, re.I):
                errs.append(f"typed console line contains M/N/V: {line!r}")
            m_bat = re.match(r"^bat\s+([A-Za-z0-9_.-]+)$", line, re.I)
            if m_bat and re.search(r"[mnv]", m_bat.group(1), re.I):
                errs.append(f"bat invocation filename contains M/N/V: {m_bat.group(1)!r}")
    for bat_name in re.findall(r"<starfield-dir>/([A-Za-z0-9_-]+)\.txt", md_text):
        if re.search(r"[mnv]", bat_name, re.I):
            errs.append(f"batch filename contains M/N/V: {bat_name!r}")
    return errs


class Round11CardsAndMNVRuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.card_2g = CARD_2G_PATH.read_text(encoding="utf-8")
        cls.card_r11 = CARD_R11_PATH.read_text(encoding="utf-8")
        cls.help_runner = r11.HelpRunner(ROOT)
        cls.source_patterns = r11.collect_source_format_patterns(ROOT)
        cls.writer_edids, cls.writer_fids, cls.quest_stages = r11.collect_writer_symbols(ROOT)

    def test_a2_7_mnv_rule_scope_typed_console_and_batch_names_only(self) -> None:
        for rel, txt in ((CARD_2G_REL, self.card_2g), (CARD_R11_REL, self.card_r11)):
            self.assertEqual(_check_mnv_scope(txt), [], f"{rel} failed P3 typed-console/batch-name M/N/V check")
            self.assertIn("typed interactive", txt, f"{rel} must state P3 applies to typed interactive console lines")
            self.assertIn("batch filenames", txt, f"{rel} must state P3 applies to batch filenames")
            self.assertIn("NOT", txt, f"{rel} must state P3 does NOT apply to batch file contents")

            # Batch file contents intentionally contain M/N/V commands (getglobalvalue, sqv, moveto)
            bat_blocks = _extract_blocks(txt, "bat")
            self.assertGreaterEqual(len(bat_blocks), 1, f"{rel} expected at least one bat block")
            bat_joined = "\n".join(bat_blocks)
            self.assertRegex(
                bat_joined,
                r"\b(?:getglobalvalue|sqv|player\.moveto)\b",
                f"{rel} bat contents should hold M/N/V commands allowed by A2.7",
            )

        # Negative controls: M/N/V in typed console OR batch filename MUST be caught
        bad_console = "```console\nplayer.moveto 09000811\n```\n"
        self.assertTrue(_check_mnv_scope(bad_console))
        bad_bat_name = "; <starfield-dir>/move1.txt\n"
        self.assertTrue(_check_mnv_scope(bad_bat_name))
        # Positive control: M/N/V inside ```bat contents is explicitly allowed
        ok_bat_contents = (
            "```bat\n; <starfield-dir>/r11stat.txt\n"
            "getglobalvalue 06000865\nsqv 09000800\nplayer.moveto 09000811\n```\n"
        )
        self.assertEqual(_check_mnv_scope(ok_bat_contents), [])

    def test_a2_7_no_tgm_instruction_in_cards(self) -> None:
        for rel, txt in ((CARD_2G_REL, self.card_2g), (CARD_R11_REL, self.card_r11)):
            self.assertIsNone(
                re.search(r"\btgm\b", txt, re.I),
                f"{rel} must not instruct the tester to type 'tgm'",
            )
            self.assertIn("god mode OFF", txt, f"{rel} must keep explicit god mode OFF instruction")

    def test_a2_7_c1_preston_scene_resolved_never_requires_both_via_lines(self) -> None:
        for rel, txt in ((CARD_2G_REL, self.card_2g), (CARD_R11_REL, self.card_r11)):
            self.assertIn(
                "FO4SF_MISSION rt=<rt> preston scene resolved via=<property|file> scene=<ref>",
                txt,
                f"{rel} must use single via=<property|file> C1 log line",
            )
            for log_blk in _extract_blocks(txt, "log"):
                has_prop = "preston scene resolved via=property " in log_blk
                has_file = "preston scene resolved via=file " in log_blk
                self.assertFalse(
                    has_prop and has_file,
                    f"{rel} must not list both via=property and via=file as required in the same log block",
                )

    def test_round11_a1_a3_card_structure_sections_and_honesty(self) -> None:
        raw_bytes = CARD_R11_PATH.read_bytes()
        self.assertFalse(raw_bytes.startswith(b"\xef\xbb\xbf"), "round11-a1-a3-card.md must not have UTF-8 BOM")
        txt = self.card_r11
        first_line = txt.splitlines()[0]
        self.assertIn("Titles: Fallout 4", first_line)
        self.assertIn("Modes: Story & Warfare", first_line)
        self.assertIn("Track: Track 1", first_line)

        top = "\n".join(txt.splitlines()[:14])
        self.assertIn("NEW GAME needed", top)
        self.assertIn("candidate-2g-fix", top)
        self.assertIn("73ea9a4b", top)
        self.assertIn("7085816241", top)
        self.assertIn("prototype, offline", top)
        self.assertIn("OFFLINE ONLY — UNPROVEN IN GAME", top)
        self.assertIn("stand-in", top.lower())
        self.assertIsNone(re.search(r"\b[A-Za-z]:[\\/]", txt), "local drive path leaked in round11-a1-a3-card.md")

        headings = re.findall(r"(?m)^##\s+(Card\s+R11-\d+[^\r\n]*)$", txt)
        self.assertEqual(len(headings), 3, headings)
        for idx, h in enumerate(headings, start=1):
            self.assertTrue(h.startswith(f"Card R11-{idx}"), h)

        # W5 #472/#476 binary truth: ACTI 0x0100E0E6 has no FULL display name -> never tell player to press E on lift
        self.assertNotIn("press E on the elevator", txt.lower())
        self.assertNotIn("press `e` on the elevator", txt.lower())
        # InvDataAnswers=0 in --profile player: never instruct equipping via F7 -> INV
        self.assertNotIn("equip it (`f7` -> `inv`)", txt.lower())
        # Old placeholder replaced by <cand2g-fix-player-bundle>
        self.assertNotIn("<cand-r11-player-bundle>", txt)

        required_tokens = (
            "<cand2g-fix-player-bundle>",
            "D1",
            "D2",
            "D3",
            "D4",
            "D5",
            "D6",
            "D7",
            "A2.1",
            "A2.2",
            "A2.3",
            "A2.4",
            "A2.5",
            "A2.6",
            "A2.7",
            "A3",
            "HAND-PLAY",
            # Review items #1-#10 coverage
            "late_dialogue_open",
            "post-`200`",
            "--codsworth-race-framing 0",
            "variants/codsworth-race-framing-on/FO4SFMission.esm",
            "0B00084A",
            "EnableCleanBenchSwap = False",
            "bat r11swp1",
            "bat r11swp0",
            "set 0B00084A to 1",
            "3.5 s",
            "sanctuary01 clean_bench_swap self_heal reason=no_workshop_menu",
            "sanctuary01 clean_bench_swap active=false ref=<ref>",
            "sanctuary01 clean_bench_swap active=true ref=<ref>",
            "openMenuCount",
            "09000A23",
            "09000AD1",
            "09000B31",
            "0x3D094D",
            "ClimateUniqueCydonia",
            "ClimateUniqueCydoniaFrozen",
            "ATMO_Mars",
            "Known Side Effect (`#4`)",
            "Mars-wide",
            "--commonwealth-weather 0",
            "try=<n>",
            "step=hud_watch_hide when=<when> try=<n> movie=<hex> ok=1 target=BottomLeftGroup_mc children_hidden=<n>",
            "step=hud_watch_hide_init ok=0 reason=channel_ids_unavailable",
            "HandleLiftControlActivate",
            # Core A1-A3 checks
            "thrusters",
            "codsworth talk dialogue_camera stopped phase=2",
            "wall_avoid=<true|false>",
            "tricorn hat",
            "MO2F = 0x01",
            "BO64 = 0x68",
            "09000986",
            "Console-Free Close-Up Concord Raider Body Inspection",
            "30, 70, 30, 30, 20",
            "arm raider <i> ammo=60",
            "sidearm=eon sidearm_ammo=36",
            "Industrial Workbench",
            "Spacesuit Workbench",
            "Research Lab",
            "WORKSHOP, MARS, SOL",
            "0B000849",
            "CheckSturgesTalkFallback",
            "RADAWAY (0)",
            "ButtonHintBar_mc.y",
            "step=shell_hintbar_layout when=kShow old_y=575.0 new_y=672.0 ok=1",
            "A, X, Y, LT, RT",
            "step=shell_platform when=kShow platform=0 called=1 triggers_hidden=2",
            "INV",
            "DATA",
            "RADIO",
            "ShellVitalsFill=0",
            "ShellBackdrop=0",
            "HideStarfieldWatch=1",
            "HideStarfieldWatch=0",
            "hide_starfield_watch=1",
            "4.8 m/s",
            "6.97 s",
            "97",
            "overshoot margin",
            "Sanctuary Hills houses",
            "Museum of Freedom interior",
            "1.815 m",
            "0x08C94A",
            "Stay",
            "0A000820",
            "0A000821",
            "02001607",
            "02001609",
            "0200160A",
            "02001539",
            "(-57.03, 30.01, 1.29)",
            "hold `E` on the pistol to take-and-equip, or press `I` / `Tab` -> `Inventory` -> `Weapons`",
            "FO4SF_NEWGAME rt=<rt> pistol picked item=<item> count=<cnt>",
            "AlreadySaid_Unselected",
            "move the cursor/highlight off the asked row",
            "abPreventRemoval=True",
            "removes `Coachman` + `AmmoShotshell`",
            "Only Starfield In Game Can Prove",
            "docs/plans/round11-first-mission-plan.md",
            "< 180 m",
        )
        for tok in required_tokens:
            self.assertIn(tok, txt, f"round11-a1-a3-card.md missing {tok!r}")

    def test_round11_card_passes_live_r11_validation(self) -> None:
        errs = r11.validate_lead_card_markdown(
            CARD_R11_REL,
            self.card_r11,
            help_runner=self.help_runner,
            source_patterns=self.source_patterns,
            writer_edids=self.writer_edids,
            writer_fids=self.writer_fids,
            quest_stages=self.quest_stages,
        )
        workshop_src = (ROOT / "dotnet/WorkshopCore/Program.cs").read_text(encoding="utf-8")
        pipboy_src = (ROOT / "sfse/FO4SFPipboyMenu/src/main.cpp").read_text(encoding="utf-8")

        w2_fix_present = "0x00084A" in workshop_src or "0x0000084A" in workshop_src or "0x84A" in workshop_src
        w4_fix_present = "step=hud_watch_hide" in pipboy_src and "try=" in pipboy_src

        if w2_fix_present and w4_fix_present:
            self.assertEqual(errs, [], f"{CARD_R11_REL} failed live R11 validation:\n" + "\n".join(errs))
            return

        r11_fix_pending_prefixes = (
            "console 'set 0B00084A' local FormID 0x00084A not in writer constants",
            "PASS line does not match any source format string: 'step=hud_watch_hide ",
        )
        unexpected = [e for e in errs if not any(p in e for p in r11_fix_pending_prefixes)]
        self.assertEqual(unexpected, [], "\n".join(unexpected))


if __name__ == "__main__":
    unittest.main()
