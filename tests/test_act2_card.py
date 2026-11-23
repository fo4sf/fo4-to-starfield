"""Offline R11 / P3 / structural validator for docs/testing/playable-path-act2-card.md (Push 6 Act II)."""

from __future__ import annotations

import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))

import test_lead_cards_beginning as r11  # noqa: E402

CARD_REL = "docs/testing/playable-path-act2-card.md"
CARD_PATH = ROOT / CARD_REL

ACT2_COC_TARGETS = frozenset(
    {
        "FO4Port_FortHagen01",
        "FO4Port_FortHagen02",
        "FO4Port_GoodneighborTheMemoryDen",
        "FO4Port_MQ203KelloggsBrain",
        "FO4Port_VirgilsLab01",
        "FO4Port_GreenetechGenetics01",
        "FO4Port_RailroadHQ01",
        "FO4Port_InstituteConcourse",
    }
)


class Act2CardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.card_text = CARD_PATH.read_text(encoding="utf-8")
        cls.help_runner = r11.HelpRunner(ROOT)
        cls.source_patterns = r11.collect_source_format_patterns(ROOT)
        cls.writer_edids, cls.writer_fids, cls.quest_stages = r11.collect_writer_symbols(ROOT)
        cls.a7cd_present = (ROOT / "dotnet/Mission/NextStoryMissionsA7cd.cs").is_file()
        cls.a7d_present = (ROOT / "scripts/terrain/a7d_glowing_sea_places.py").is_file()

    def test_act2_card_structure_headers_prefixes_formids_and_save_reload(self) -> None:
        txt = self.card_text
        first_line = txt.splitlines()[0]
        self.assertIn("Titles: Fallout 4", first_line)
        self.assertIn("Modes: Story & Warfare", first_line)
        self.assertIn("Track: Track 1", first_line)

        top_header = "\n".join(txt.splitlines()[:15])
        self.assertIn("NEW GAME needed", top_header)
        self.assertIn("prototype, offline", top_header)
        self.assertIn("OFFLINE ONLY — UNPROVEN IN GAME", top_header)
        self.assertIsNone(re.search(r"\b[A-Za-z]:[\\/]", txt), "local drive path leaked in Act II card")

        headings = re.findall(r"(?m)^##\s+(Card\s+Act2-\d+[^\r\n]*)$", txt)
        self.assertEqual(len(headings), 4, headings)
        for idx, h in enumerate(headings, start=1):
            self.assertTrue(h.startswith(f"Card Act2-{idx}"), h)

        required_tokens = (
            # 13-plugin vs 22-plugin prefixes & border rule
            "--profile player",
            "--profile test",
            "< 200 m",
            "0D0547B0",
            "150547B0",
            "0x800..0xBFF",
            # Persistent 0x400 arrival refs (13-plugin & 22-plugin)
            "1000090A",
            "1900090A",
            "10000990",
            "19000990",
            "10000A00",
            "19000A00",
            "100009C9",
            "190009C9",
            "100009D9",
            "190009D9",
            "1000099A",
            "1900099A",
            "10000980",
            "19000980",
            "1000099B",
            "1900099B",
            # Quest, actor, proxy & GLOB FormIDs
            "09000AD0",
            "09000AD2",
            "09000AD5",
            "09000AD6",
            "09000AF0",
            "09000AF2",
            "09000AF3",
            "09000AF5",
            "09000B10",
            "09000B12",
            "09000B14",
            "09000B16",
            "09000B17",
            "09000B18",
            "09000B30",
            "09000B32",
            "09000B3C",
            "09000B3D",
            "09000B40..09000B47",
            "0203D252",
            "0x00F2D3",
            "0x00F23D",
            "0x03D52E",
            "dest=0x00F2D3",
            "dest=0x03D52E",
            # Save/reload throwaway checkpoints & Open-Mode fallbacks
            "Throwaway_Act2_FortHagen",
            "Throwaway_Act2_MemoryDen",
            "Throwaway_Act2_GlowingSea",
            "Throwaway_Act2_Molecular",
            "FO4SF_MQ106_TerminalProxyActi",
            "FO4SF_MQ203_LoungerProxyActi",
            "FO4SF_MQ204_LabTerminalProxyActi",
            "FO4SF_MQ206_ScannerProxyActi",
            "FO4SF_MQ206_ConsoleProxyActi",
            # Required completion & Pip-Boy PASS log lines
            "mq106 complete stage=500 mq203_armed=1",
            "mq203 complete stage=300 memories=1 mq204_armed=1",
            "mq204 complete stage=200 mq206_armed=1",
            "mq206 complete stage=1200 faction=<n> mq207_armed=1 institute_cell=0x03D252",
            "step=quest_catalog file=FO4SFPipboyQuestObjectives.tsv",
            "step=map_quest_markers",
        )
        for tok in required_tokens:
            self.assertIn(tok, txt, f"Act II card missing required token: {tok!r}")

    def test_act2_card_p3_zero_mnv_console_and_batch_names(self) -> None:
        console_blocks = [
            body for lang, body in r11.FENCED_BLOCK_RE.findall(self.card_text) if lang.strip().lower() == "console"
        ]
        self.assertEqual(len(console_blocks), 4, "expected 1 console block per Act II card")
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

        # Negative P3 control via validate_lead_card_markdown
        bad_txt = self.card_text.replace("\nsqs 09000AD0\n", "\nsqv 09000AD0\n", 1).replace(
            "\nbat a2r1\n", "\nset FO4SF_MQ206Armed to 1\n", 1
        )
        errs = r11.validate_lead_card_markdown(
            CARD_REL,
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

    def test_act2_card_passes_full_r11_when_act2_sources_present(self) -> None:
        orig_coc = r11.CROSS_BRANCH_COC_TARGETS
        try:
            r11.CROSS_BRANCH_COC_TARGETS = orig_coc | ACT2_COC_TARGETS
            errs = r11.validate_lead_card_markdown(
                CARD_REL,
                self.card_text,
                help_runner=self.help_runner,
                source_patterns=self.source_patterns,
                writer_edids=self.writer_edids,
                writer_fids=self.writer_fids,
                quest_stages=self.quest_stages,
            )
        finally:
            r11.CROSS_BRANCH_COC_TARGETS = orig_coc

        if not (self.a7cd_present and self.a7d_present):
            # Standalone branch before Push 6 merges A7cd + A7d: verify all non-Act2-source R11 invariants
            # (existing CLI --help flags, zero M/N/V, install/undo/PASS blocks, disk need, placeholders).
            unexpected = [
                e
                for e in errs
                if not any(
                    marker in e
                    for marker in (
                        "unknown FO4SF_* identifier",
                        "not in writer constants",
                        "PASS line does not match any source format string: 'FO4SF_MISSION rt=<rt> mq",
                        "a7d_glowing_sea_places.py",
                    )
                )
            ]
            self.assertEqual(unexpected, [], "\n".join(unexpected))
            return

        self.assertEqual(errs, [], "\n".join(errs))


if __name__ == "__main__":
    unittest.main()
