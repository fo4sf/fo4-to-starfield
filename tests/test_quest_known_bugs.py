"""Schema, cross-link, approval-queue, and clean-room/redaction tests for docs/quests/known-bugs/*.md."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
BUGS_DIR = ROOT / "docs" / "quests" / "known-bugs"

EXPECTED_LEDGERS = {
    "opening-sequence.md": "OPEN",
    "concord-when-freedom-calls.md": "WFC",
    "preston-follow.md": "COMP",
}

ALLOWED_OCCURS = ("`Yes`", "`Mitigated`", "`Not applicable yet`")
ALLOWED_RESOLUTIONS = (
    "`Fix directly (ours)`",
    "`Study community patch's documented change (owner approval needed if external read/download required)`",
    "`Left / N-A in current cut-down stage`",
)

# Constructed without literal third-party names in source text so repo-wide scans stay zero-hit
FORBIDDEN_MOD_PATTERNS = [
    re.compile(r"\b" + ("UF" + "O4P") + r"\b", re.I),
    re.compile(r"\b" + ("Unofficial" + r"\s+" + "Fallout") + r"\b", re.I),
    re.compile(r"\b" + ("Yuki" + "chigai" + "|" + "Y" + "UP") + r"\b", re.I),
    re.compile(r"\b" + ("GAM" + "MA") + r"\b", re.I),
    re.compile(r"\b" + ("Buff" + "out") + r"\b", re.I),
    re.compile(r"\b" + ("Role" + "players" + r"'?\s+" + "Alternate") + r"\b", re.I),
]
DRIVE_PATH_RX = re.compile(r"\b[A-Za-z]:[\\/]")


class QuestKnownBugsTests(unittest.TestCase):
    def test_readme_index_schema_and_owner_approval_queue(self):
        readme_path = BUGS_DIR / "README.md"
        self.assertTrue(readme_path.is_file(), "missing docs/quests/known-bugs/README.md")
        txt = readme_path.read_text(encoding="utf-8")

        for filename in EXPECTED_LEDGERS:
            self.assertIn(f"({filename})", txt, f"README.md does not link {filename}")

        for heading in (
            "## 1. Quest Ledgers",
            "## 2. Ledger Schema",
            "## 3. Clean-Room & Public-Surface Policy",
            "## 4. Owner Download / Read Approval Request Queue",
        ):
            self.assertIn(heading, txt)

        reqs = re.findall(r"^\|\s*`(REQ-KB-\d{2})`\s*\|([^|]+)\|([^|]+)\|([^|]+)\|\s*\*\*Awaiting Owner Approval\*\*\s*\|", txt, re.M)
        self.assertGreaterEqual(len(reqs), 3, "expected at least 3 queued owner approval requests in README.md")
        for req_id, target_doc, quest_slice, question in reqs:
            self.assertTrue(target_doc.strip(), req_id)
            self.assertTrue(quest_slice.strip(), req_id)
            self.assertGreater(len(question.strip()), 20, req_id)

    def test_every_quest_ledger_has_valid_matrix_and_complete_bug_entries(self):
        for filename, prefix in EXPECTED_LEDGERS.items():
            path = BUGS_DIR / filename
            self.assertTrue(path.is_file(), f"missing {filename}")
            txt = path.read_text(encoding="utf-8")

            self.assertIn("## Summary Matrix", txt, filename)
            self.assertIn("## Detailed Bug Entries", txt, filename)
            self.assertRegex(
                txt,
                r"\|\s*Bug ID\s*\|\s*Short Functional Name\s*\|\s*Occurs in Our Conversion\?\s*\|\s*Resolution Category\s*\|",
            )

            matrix_rows = re.findall(
                rf"^\|\s*`({prefix}-\d{{2}})`\s*\|\s*([^|]+?)\s*\|\s*(`[^`]+`)\s*\|\s*(`[^`]+`)\s*\|",
                txt,
                re.M,
            )
            self.assertGreaterEqual(len(matrix_rows), 5, f"{filename} should document at least 5 bugs")
            matrix_ids = [r[0] for r in matrix_rows]
            for bug_id, short_name, occurs_col, res_col in matrix_rows:
                self.assertTrue(short_name.strip(), bug_id)
                self.assertIn(occurs_col, ALLOWED_OCCURS, f"{filename}:{bug_id} invalid matrix occurs {occurs_col}")
                self.assertIn(res_col, ALLOWED_RESOLUTIONS, f"{filename}:{bug_id} invalid matrix resolution {res_col}")

            sections = list(re.finditer(rf"^### `({prefix}-\d{{2}})` — (.+)$", txt, re.M))
            detail_ids = [m.group(1) for m in sections]
            self.assertEqual(detail_ids, matrix_ids, f"{filename} matrix IDs do not match detailed section IDs")

            for idx, m in enumerate(sections):
                bug_id = m.group(1)
                start = m.end()
                end = sections[idx + 1].start() if idx + 1 < len(sections) else len(txt)
                block = txt[start:end]

                for field in (
                    "- **Plain Functional Description:**",
                    "- **Occurs in Our Conversion?:**",
                    "- **Proposed Resolution:**",
                    "- **PC Card Reproduction & Check:**",
                ):
                    self.assertIn(field, block, f"{filename}:{bug_id} missing {field}")

                occurs_m = re.search(r"- \*\*Occurs in Our Conversion\?:\*\*\s*(`[^`]+`)\s*(.+)", block)
                self.assertIsNotNone(occurs_m, f"{filename}:{bug_id} malformed Occurs line")
                self.assertIn(occurs_m.group(1), ALLOWED_OCCURS, f"{filename}:{bug_id}")
                # Must cite concrete repo artifact (.psc, .cs, .esm, or .md)
                self.assertRegex(
                    occurs_m.group(2),
                    r"(\.psc|\.cs|\.esm|\.md|0x[0-9A-Fa-f]+|stage\s+`?\d+)",
                    f"{filename}:{bug_id} must cite concrete conversion code/stage",
                )

                res_m = re.search(r"- \*\*Proposed Resolution:\*\*\s*(`[^`]+`)\s*—\s*(.+)", block)
                self.assertIsNotNone(res_m, f"{filename}:{bug_id} malformed Proposed Resolution line")
                self.assertIn(res_m.group(1), ALLOWED_RESOLUTIONS, f"{filename}:{bug_id}")
                self.assertGreater(len(res_m.group(2).strip()), 15, f"{filename}:{bug_id}")

                pc_m = re.search(r"- \*\*PC Card Reproduction & Check:\*\*\s*(.+)", block)
                self.assertIsNotNone(pc_m, f"{filename}:{bug_id} empty PC check")
                self.assertGreater(len(pc_m.group(1).strip()), 20, f"{filename}:{bug_id}")

    def test_zero_third_party_mod_names_or_pc_paths(self):
        files = sorted(BUGS_DIR.glob("*.md")) + [Path(__file__)]
        self.assertEqual(len(files), 5)
        for p in files:
            txt = p.read_text(encoding="utf-8")
            self.assertIsNone(DRIVE_PATH_RX.search(txt), f"PC drive path found in {p.name}")
            for rx in FORBIDDEN_MOD_PATTERNS:
                self.assertIsNone(rx.search(txt), f"forbidden third-party mod name matched {rx.pattern} in {p.name}")


if __name__ == "__main__":
    unittest.main()
