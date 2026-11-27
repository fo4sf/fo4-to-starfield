"""Offline P3 / R11 / R15 validator for docs/testing/round11-probes-p1-p4-card.md."""

from __future__ import annotations

import json
import os
import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import test_lead_cards_beginning as r11  # noqa: E402

CARD_REL = "docs/testing/round11-probes-p1-p4-card.md"
CARD_PATH = ROOT / CARD_REL

P1_EXPECTED_FILES = {
    "port/FO4Port.esm": (4612735, "8163ca9a7187bd07fdd09f20ad7c16d511577f91d91c858ed28ec0fc434fef39"),
    "port/FO4Port - Main.ba2": (117755711, "064c762499a1cc975df81da2c12ea3a20aec5f84cae0c89f4d9cdac12d094c7e"),
    "port/FO4Port - Textures.ba2": (2289478621, "f4664dd0a4fb49a3adb17440596bbb936b0ffa47516024be9fff07c7b1a69a48"),
    "exp/FO4SF_R11P1Museum.esm": (5037, "63e0862f22c43838f4738a790710a2754d3f28ca74d38b8e62e17c90fffdcd11"),
    "exp/FO4SF_R11P1Museum - Main.ba2": (32883, "1d4580c17e7b7d619c44ac6531db7ac28a478dea055d762cdea08e34a3899c02"),
}

P4_EXPECTED_FILES = {
    "core/FO4SFCoreValues.esm": (11555, "b6fca94fd98f42654d9cc83a7a4c7ab166f5ff37b2ec8087558aa3ec31ee6ac7"),
    "core/FO4SFNewGame.esm": (12688, "7fcbb12ff901daa2b392dba54948ea076f21db22d9eb20a6e2429a6baa45301e"),
    "exp/FO4SF_R11P4Pistol.esm": (1348, "e6e50ab185670c4b518e7cab047e7a97ce1ec65a36a8a36467d6b05ef17d2f6b"),
    "exp/FO4SF_R11P4Pistol - Main.ba2": (296251, "d112735e2bc2c966c29ed6c9a80a10ed610a160bd0e75f5b0acfc3bc4c24d0bb"),
    "exp/FO4SF_R11P4Pistol - Textures.ba2": (5909367, "9421ae40bc9a36259f53405f2c3cb7d7dff2c26f9ed4fe19bd8433be55e92e1a"),
    "assets/meshes/fo4sf/weapons/10mm/fo4_10mmpistol.nif": (
        10796,
        "2033561ea31ce4213063d5b8e29ee6af36322b719ce6f8608d1c8ad2ce7559a2",
    ),
    "assets/meshes/fo4core/ammo/10mm/10mmammo.nif": (
        7135,
        "a08ee05fc4746300669d52c503c8b5836657457be65f7f9fe4b80472efd58f09",
    ),
}

P1_BAT_STEMS = ("p1h1", "p1c", "p1r", "p1f", "p1b", "p1k", "p1p", "p1q")
P4_BAT_STEMS = ("p4d", "p4o", "p4g", "p4t", "p4h1", "p4e", "p4s")


def _extract_blocks(md_text: str, lang: str) -> list[str]:
    want = lang.strip().lower()
    return [body for blk_lang, body in r11.FENCED_BLOCK_RE.findall(md_text) if blk_lang.strip().lower() == want]


def _check_p3_probe_rules(md_text: str) -> list[str]:
    errs: list[str] = []
    for body in _extract_blocks(md_text, "console"):
        for raw in body.splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if re.search(r"[mnv]", line, re.I):
                errs.append(f"typed console line contains M/N/V: {line!r}")
            if re.match(r"^coc\b", line, re.I):
                errs.append(f"coc must live inside a .txt batch file, not typed console: {line!r}")
            if re.match(r"^(?:set|setstage|help|startquest|stopquest)\s+FO4SF_", line, re.I):
                errs.append(f"stripped mod FO4SF_* EditorID in console: {line!r}")
            m_bat = re.match(r"^bat\s+([A-Za-z0-9_.-]+)$", line, re.I)
            if m_bat and re.search(r"[mnv]", m_bat.group(1), re.I):
                errs.append(f"bat filename contains M/N/V: {m_bat.group(1)!r}")

    for body in _extract_blocks(md_text, "bat"):
        for raw in body.splitlines():
            line = raw.strip()
            if not line or line.startswith(";"):
                continue
            if re.match(r"^(?:set|setstage|help|startquest|stopquest)\s+FO4SF_", line, re.I):
                errs.append(f"stripped mod FO4SF_* EditorID in bat: {line!r}")

    for bat_name in re.findall(r"<starfield-dir>/([A-Za-z0-9_-]+)\.txt", md_text):
        if re.search(r"[mnv]", bat_name, re.I):
            errs.append(f"batch filename contains M/N/V: {bat_name!r}")
    return errs


def _collect_probe_log_templates(repo_root: pathlib.Path) -> list[tuple[str, str, re.Pattern[str]]]:
    """Collect real Log(...) and Trace(...) templates from probe & newgame Papyrus scripts."""
    compiled = list(r11.collect_source_format_patterns(repo_root))
    for rel in (
        "scripts/doors/FO4SF_ConfirmedLoadDoor.psc",
        "scripts/doors/FO4SF_LoadDoorQuest.psc",
        "scripts/probes/FO4SF_R11P1Quest.psc",
        "scripts/probes/FO4SF_R11P4Quest.psc",
    ):
        fp = repo_root / rel
        if not fp.is_file():
            continue
        for raw_line in fp.read_text(encoding="utf-8", errors="replace").splitlines():
            code = r11._strip_psc_comment(raw_line)
            if not code or code.startswith("Function "):
                continue
            ml = re.search(r"\bLog\((.+)\)\s*$", code)
            if ml:
                tpl = r11._psc_concat_expr_to_template(ml.group(1))
                if tpl:
                    norm = re.sub(r"(\{[^{}]*\})+", "{}", tpl)
                    parts = norm.split("{}")
                    compiled.append((rel, tpl, re.compile("^" + r"[^\r\n]+".join(re.escape(p) for p in parts) + "$")))
    return compiled


class Round11ProbesP1P4CardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw_bytes = CARD_PATH.read_bytes()
        cls.txt = cls.raw_bytes.decode("utf-8")
        cls.log_patterns = _collect_probe_log_templates(ROOT)

    def test_hygiene_headers_honesty_and_no_local_paths(self) -> None:
        self.assertFalse(self.raw_bytes.startswith(b"\xef\xbb\xbf"), "card must not have UTF-8 BOM")
        first_line = self.txt.splitlines()[0]
        self.assertIn("Titles: Fallout 4", first_line)
        self.assertIn("Modes: Story & Warfare", first_line)
        self.assertIn("Track: Track 1", first_line)

        top = "\n".join(self.txt.splitlines()[:16])
        self.assertIn("NEW GAME needed", top)
        self.assertIn("prototype, offline", top)
        self.assertIn("OFFLINE ONLY — UNPROVEN IN GAME", top)
        self.assertIn("stand-in", top.lower())
        self.assertIsNone(re.search(r"\b[A-Za-z]:[\\/]", self.txt), "local drive path leaked in probes card")
        self.assertIsNone(re.search(r"\btgm\b", self.txt, re.I), "card must not instruct typing tgm")
        self.assertNotIn("[P4_MANIFEST_SYNC]", self.txt, "all P4 manifest sync placeholders must be filled")

        headings = re.findall(r"(?m)^##\s+(Card\s+P\d+[^\r\n]*)$", self.txt)
        self.assertEqual(len(headings), 2, headings)
        self.assertTrue(headings[0].startswith("Card P1"))
        self.assertTrue(headings[1].startswith("Card P4"))

    def test_p3_zero_mnv_zero_stripped_edids_and_under_200m_hops(self) -> None:
        self.assertEqual(_check_p3_probe_rules(self.txt), [])
        for stem in P1_BAT_STEMS + P4_BAT_STEMS:
            self.assertIn(f"bat {stem}", self.txt)
            self.assertIn(f"<starfield-dir>/{stem}.txt", self.txt)

        # Negative P3 controls
        self.assertTrue(_check_p3_probe_rules("```console\nbat p1move\n```\n"))
        self.assertTrue(_check_p3_probe_rules("```console\ncoc FO4Port_ConcordMuseum01\n```\n"))
        self.assertTrue(_check_p3_probe_rules("```bat\nSetStage FO4SF_R11P1Quest 10\n```\n"))

        # Verify every exterior hop row in BOTH hop tables (5 P1 + 2 P4 = 7) is strictly < 200 m per axis
        hop_rows = re.findall(
            r"(?m)^\|\s*`[^`]+`\s*\|[^|]+\|\s*`(\d+(?:\.\d+)?)`\s*\|\s*`(\d+(?:\.\d+)?)`\s*\|\s*`(\d+(?:\.\d+)?)`\s*\|\s*\*\*`(\d+(?:\.\d+)?)`\*\*\s*\|\s*PASS\s*\|$",
            self.txt,
        )
        self.assertGreaterEqual(len(hop_rows), 7, "expected >= 7 verified < 200 m/axis exterior hop rows (5 P1 + 2 P4)")
        for dx_s, dy_s, dz_s, max_s in hop_rows:
            dx, dy, dz, mx = float(dx_s), float(dy_s), float(dz_s), float(max_s)
            self.assertAlmostEqual(mx, max(dx, dy, dz), places=2)
            self.assertLess(mx, 200.0, f"exterior hop exceeds 200 m/axis limit: {mx}")

    def test_p1_and_p4_required_sections_hashes_and_r15_disclosures(self) -> None:
        for rel, (size_b, sha) in {**P1_EXPECTED_FILES, **P4_EXPECTED_FILES}.items():
            self.assertIn(rel, self.txt, f"missing probe file {rel}")
            self.assertIn(f"`{size_b:,}`", self.txt, f"missing exact byte size for {rel}")
            self.assertIn(sha, self.txt, f"missing exact SHA-256 for {rel}")

        required_tokens = (
            # P1 v2 CLI + Row 1 exterior-loads gate + 6 mandatory checks + optional XTEL extra
            "r11-p1-museum-v2",
            "Row 1 — Exterior-Loads Gate",
            "z ≈ 88.3 m",
            "z ≈ 12.6 m",
            "0x0006BCF8",
            "0x0400080F",
            "0x00000009",
            "StartTimer",
            "FO4SF_LoadDoorQuest.psc",
            "(-1990.58, -1724.19, 97.56)",
            "0x0A775B",
            "0x00000FF1",
            "stage_r11_p1_museum.py verify --stage-dir <p1-stage-dir>",
            "stage_r11_p1_museum.py install --stage-dir <p1-stage-dir> --starfield <starfield-dir>",
            "stage_r11_p1_museum.py uninstall --starfield <starfield-dir>",
            "5x",
            "3x",
            "Quit to Desktop",
            "0x0100EDF0",
            "[Unlock Security Gate]",
            "InitiallyDisabled",
            "FO4SF_P1_RaiderNavTriggerRef",
            "0x0100EFA8",
            "FO4Port_PrewarVault111",
            "0x0100EDFB",
            "P1v2 F4",
            "0x0100E35E",
            "0x0100EFA9",
            "0x0100EFAA",
            "FO4PortTextures2.esm",
            # P4 CLI + 10mm alone + 7 checks + mandatory R15 rigid/XM2311 disclosures + post-P4 code fixes
            "ArmoryCageDoorLocalId",
            "RemoveAllItems",
            "stage_r11_p4_10mm.py verify --stage-dir <p4-stage-dir>",
            "stage_r11_p4_10mm.py install --stage-dir <p4-stage-dir> --starfield <starfield-dir>",
            "stage_r11_p4_10mm.py uninstall --starfield <starfield-dir>",
            "0x000898",
            "0x000899",
            "FO4_10mmPistol",
            "FO4_Ammo10mm",
            "0A000820",
            "0A000821",
            "FO4SF_P4_TargetTriggerRef",
            "FO4SF_P4_TargetDummyRef",
            "0x01001539",
            "(-48.80, 30.00, 0.15)",
            "player.setpos x -53.20",
            "1st-person",
            "3rd-person",
            "ADS",
            "12` rounds",
            "Reload",
            "Hit & Kill",
            '"10mm Pistol"',
            '"10mm Round"',
            "xm2311_leak=0",
            "cal45_leak=0",
            "slide/bolt, hammer, trigger, mag release, detachable magazine",
            "rigid and do NOT move",
            "XM2311",
            "0x24561C",
            "stand-ins",
        )
        for tok in required_tokens:
            self.assertIn(tok, self.txt, f"probes card missing required token {tok!r}")

    def test_all_pass_log_lines_match_real_papyrus_sources(self) -> None:
        log_blocks = _extract_blocks(self.txt, "log")
        self.assertGreaterEqual(len(log_blocks), 2, "expected log blocks in Card P1 and Card P4")
        p4_psc_present = (ROOT / "scripts/probes/FO4SF_R11P4Quest.psc").is_file()
        unmatched: list[str] = []
        for blk in log_blocks:
            for raw in blk.splitlines():
                pline = raw.strip()
                if not pline or pline.startswith("#"):
                    continue
                if not p4_psc_present and pline.startswith("FO4SF_R11P4 "):
                    continue
                sample = r11._sample_from_card_line(pline)
                fixed_toks = r11._extract_fixed_tokens(pline)
                ok = any(
                    pat.search(sample) and all(r11._token_matches_template(ft, tpl) for ft in fixed_toks)
                    for _src, tpl, pat in self.log_patterns
                )
                if not ok:
                    unmatched.append(pline)
        self.assertEqual(unmatched, [], f"PASS log lines do not match source templates: {unmatched}")

    @unittest.skipUnless(
        os.environ.get("FO4SF_R11_P1_STAGE")
        and pathlib.Path(os.environ["FO4SF_R11_P1_STAGE"], "manifest.json").is_file(),
        "Set FO4SF_R11_P1_STAGE to live staged r11-p1-museum directory to cross-check manifest.json",
    )
    def test_live_p1_manifest_matches_card_hashes(self) -> None:
        manifest_path = pathlib.Path(os.environ["FO4SF_R11_P1_STAGE"]) / "manifest.json"
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        files = data["files"]
        for rel, (size_b, sha) in P1_EXPECTED_FILES.items():
            self.assertIn(rel, files, f"manifest missing {rel}")
            self.assertEqual(files[rel]["size_bytes"], size_b)
            self.assertEqual(files[rel]["sha256"], sha)
            self.assertIn(sha, self.txt)

    @unittest.skipUnless(
        os.environ.get("FO4SF_R11_P4_STAGE")
        and pathlib.Path(os.environ["FO4SF_R11_P4_STAGE"], "manifest.json").is_file(),
        "Set FO4SF_R11_P4_STAGE to live staged r11-p4-10mm directory to cross-check manifest.json",
    )
    def test_live_p4_manifest_matches_card_hashes(self) -> None:
        manifest_path = pathlib.Path(os.environ["FO4SF_R11_P4_STAGE"]) / "manifest.json"
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        files = data["files"]
        for rel, (size_b, sha) in P4_EXPECTED_FILES.items():
            self.assertIn(rel, files, f"manifest missing {rel}")
            self.assertEqual(files[rel]["size_bytes"], size_b)
            self.assertEqual(files[rel]["sha256"], sha)
            self.assertIn(sha, self.txt)


if __name__ == "__main__":
    unittest.main()
