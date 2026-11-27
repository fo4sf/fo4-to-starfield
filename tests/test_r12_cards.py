"""Unit tests for Round 12 card template and validator (VIDEO column + 5-row Claude's Additions)."""
from __future__ import annotations

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
TESTING_DIR = ROOT / "scripts" / "testing"
if str(TESTING_DIR) not in sys.path:
    sys.path.insert(0, str(TESTING_DIR))

import r12_card_validator as validator  # noqa: E402

TEMPLATE_PATH = ROOT / "docs" / "testing" / "round12-card-template.md"


class R12CardValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.template_text = TEMPLATE_PATH.read_text(encoding="utf-8")

    def test_template_passes_all_checks(self) -> None:
        errors = validator.validate_r12_card_markdown("docs/testing/round12-card-template.md", self.template_text)
        self.assertEqual(errors, [], f"Unexpected errors: {errors}")

    def test_missing_video_column_is_rejected(self) -> None:
        broken = self.template_text.replace("| VIDEO |", "| CLIP |")
        errors = validator.validate_r12_card_markdown("card.md", broken)
        self.assertTrue(any("VIDEO" in e for e in errors), errors)

    def test_wrong_claude_row_count_is_rejected(self) -> None:
        lines = self.template_text.splitlines()
        filtered = [ln for ln in lines if not ln.startswith("| **Gun sounds**")]
        errors = validator.validate_r12_card_markdown("card.md", "\n".join(filtered))
        self.assertTrue(any("4 rows, expected 5" in e for e in errors), errors)
        self.assertTrue(any("gun sounds" in e for e in errors), errors)

    def test_missing_claude_section_is_rejected(self) -> None:
        broken = self.template_text.replace("## Claude's Additions (5 Rows — 23 Nov In-Game Baseline)", "## Extra Notes")
        errors = validator.validate_r12_card_markdown("card.md", broken)
        self.assertTrue(any("Claude's Additions" in e for e in errors), errors)

    def test_p3_mnv_in_console_and_batch_name_is_rejected(self) -> None:
        broken = self.template_text.replace("bat p6a", "bat p6mv")
        errors = validator.validate_r12_card_markdown("card.md", broken)
        self.assertTrue(any("M/N/V" in e for e in errors), errors)

    def test_bundle_install_and_drive_paths_are_rejected(self) -> None:
        broken = self.template_text.replace(
            "python <stager-script.py> verify --stage-dir <stage-dir>",
            "python scripts/game/bundle_install.py --bundle D:\\FO4SF-Owner-Tests\\bad",
        )
        errors = validator.validate_r12_card_markdown("card.md", broken)
        self.assertTrue(any("bundle_install.py" in e for e in errors), errors)
        self.assertTrue(any("drive path" in e for e in errors), errors)

    def test_cli_main_returns_zero_on_template(self) -> None:
        rc = validator.main([str(TEMPLATE_PATH)])
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
