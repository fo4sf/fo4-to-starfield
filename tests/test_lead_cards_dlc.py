"""Rule R11 lead-card verification test for `gemini/dlc-and-interiors` (#834).

Reads ONLY the card file listed in `CARD_FILES` (`docs/testing/dlc-and-interiors-lead-card.md`) and verifies:
1. Every runnable `python ...` / `dotnet ...` command sits in a fenced code block, and every `--flag` it uses (plus
   forwarded `--convert-arg` / `--promote-arg` flags and `interior_batch.py build`'s required flags) is accepted by
   `<tool> [subcommand] --help` in a real subprocess.
2. Every in-game console `coc <EditorID>` line matches `interior_dlc` + `PluginSpike`'s exact cell naming constants
   (`FO4DLC_<Cell>`), verified against both source constants and `PluginSpike.dll` output.
3. Every line in the fenced PASS blocks matches real format strings / JSON keys in `scripts/deploy_starfield.py` or
   `scripts/terrain/interior_batch.py`.
4. Every card section declares its stage placeholder, `Plugins.txt` load list, `40` GB disk floor, install command, and
   undo command, and Card 1's `uninstall` carries `--plugin-name FO4DLC.esm` with the prose warning about `FO4Port.esm`.
"""
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "src", ROOT / "scripts", ROOT / "scripts" / "terrain", ROOT / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from fo4sf import pipeline  # noqa: E402
import interior_dlc  # noqa: E402
from pluginspike_fixture import ensure_pluginspike_dll  # noqa: E402

CARD_FILES = ("docs/testing/dlc-and-interiors-lead-card.md",)
FLAG_RX = re.compile(r"(--[A-Za-z0-9][A-Za-z0-9_-]*)")
PLACEHOLDER_RX = re.compile(r"<[^>]+>")


def parse_fenced_blocks(markdown_text: str):
    """Yield (heading, info_string, lines) for every fenced code block in `markdown_text`."""
    heading = ""
    in_fence = False
    fence_marker = ""
    info = ""
    buf = []
    blocks = []
    for raw_line in markdown_text.splitlines():
        stripped = raw_line.strip()
        if not in_fence:
            if stripped.startswith("#"):
                heading = stripped.lstrip("#").strip()
            m = re.match(r"^(`{3,}|~{3,})(.*)$", stripped)
            if m:
                in_fence = True
                fence_marker = m.group(1)
                info = m.group(2).strip().lower()
                buf = []
        else:
            if stripped.startswith(fence_marker) and stripped.strip(fence_marker[0]) == "":
                blocks.append((heading, info, list(buf)))
                in_fence = False
                fence_marker = ""
                info = ""
                buf = []
            else:
                buf.append(raw_line)
    if in_fence:
        raise AssertionError(f"Unclosed fenced code block under heading {heading!r}")
    return blocks


def extract_outside_fence_lines(markdown_text: str):
    in_fence = False
    fence_marker = ""
    out = []
    for idx, raw_line in enumerate(markdown_text.splitlines(), 1):
        stripped = raw_line.strip()
        if not in_fence:
            m = re.match(r"^(`{3,}|~{3,})", stripped)
            if m:
                in_fence = True
                fence_marker = m.group(1)
            else:
                out.append((idx, stripped))
        else:
            if stripped.startswith(fence_marker) and stripped.strip(fence_marker[0]) == "":
                in_fence = False
                fence_marker = ""
    return out


class HelpCache:
    """Cache `<tool> [subcommand] --help` subprocess outputs so each distinct CLI help runs once."""

    def __init__(self):
        self._flags = {}
        self._raw = {}

    def help_flags(self, cmd_prefix: tuple[str, ...]) -> set[str]:
        if cmd_prefix not in self._flags:
            proc = subprocess.run(
                [*cmd_prefix, "--help"],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                check=True,
            )
            combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
            self._raw[cmd_prefix] = combined
            self._flags[cmd_prefix] = set(FLAG_RX.findall(combined))
        return self._flags[cmd_prefix]


def validate_command_line(line: str, help_cache: HelpCache) -> list[str]:
    """Validate all `--flags` on a `python ...` or `dotnet ...` command line against subprocess `--help`.
    Returns the parsed tokens."""
    tokens = shlex.split(line, posix=True)
    if not tokens:
        raise ValueError("empty command line")
    prog = tokens[0]
    if prog == "python":
        if len(tokens) < 2:
            raise ValueError(f"missing script path in {line!r}")
        script_rel = tokens[1].replace("\\", "/")
        script_path = ROOT / script_rel
        if not script_path.is_file():
            raise AssertionError(f"Card references missing Python script: {script_rel}")
        # Determine whether tokens[2] is a subcommand/action positional.
        sub = tokens[2] if len(tokens) >= 3 and not tokens[2].startswith("-") and not tokens[2].startswith("<") else None
        help_cmd = (sys.executable, str(script_path), sub) if sub else (sys.executable, str(script_path))
        accepted = help_cache.help_flags(help_cmd)
        used_flags = []
        forwarded_convert = []
        forwarded_promote = []
        i = 2 + (1 if sub else 0)
        while i < len(tokens):
            tok = tokens[i]
            if tok.startswith("--"):
                flag_name, eq, eq_val = tok.partition("=")
                used_flags.append(flag_name)
                if flag_name == "--convert-arg":
                    val = eq_val if eq else (tokens[i + 1] if i + 1 < len(tokens) else "")
                    if val.startswith("--"):
                        forwarded_convert.append(val.partition("=")[0])
                    if not eq and i + 1 < len(tokens):
                        i += 1
                elif flag_name == "--promote-arg":
                    val = eq_val if eq else (tokens[i + 1] if i + 1 < len(tokens) else "")
                    if val.startswith("--"):
                        forwarded_promote.append(val.partition("=")[0])
                    if not eq and i + 1 < len(tokens):
                        i += 1
            i += 1
        unknown = sorted(set(used_flags) - accepted)
        if unknown:
            raise AssertionError(f"Unknown flag(s) {unknown} for {' '.join(help_cmd)} in card command: {line}")

        if script_rel == "scripts/terrain/interior_batch.py" and sub == "build":
            required_build_flags = {
                "--plan", "--batch", "--base", "--base-exports", "--core", "--work", "--out",
                "--fo4-data", "--starfield", "--content-resources", "--texconv",
                "--collision-template", "--fo4export", "--pluginspike",
            }
            missing_req = sorted(required_build_flags - set(used_flags))
            if missing_req:
                raise AssertionError(f"interior_batch.py build card command omits required flag(s) {missing_req}: {line}")

        if forwarded_convert:
            cb_accepted = help_cache.help_flags((sys.executable, str(ROOT / "scripts" / "convert_batch.py")))
            bad_cb = sorted(set(forwarded_convert) - cb_accepted)
            if bad_cb:
                raise AssertionError(f"Unknown --convert-arg flag(s) {bad_cb} for convert_batch.py in: {line}")
        if forwarded_promote:
            pp_accepted = help_cache.help_flags((sys.executable, str(ROOT / "scripts" / "terrain" / "port_promote.py")))
            bad_pp = sorted(set(forwarded_promote) - pp_accepted)
            if bad_pp:
                raise AssertionError(f"Unknown --promote-arg flag(s) {bad_pp} for port_promote.py in: {line}")
        return tokens

    if prog == "dotnet":
        raise AssertionError(f"Unexpected direct dotnet command without registered validator: {line}")
    raise ValueError(f"Not a python/dotnet command: {line!r}")


def pass_line_matches_sources(line: str, sources_text: str) -> bool:
    """Check that every fixed phrase or JSON key on a card PASS line appears in the tool sources."""
    stripped = line.strip()
    if not stripped:
        return True
    # JSON-style PASS lines: extract every quoted JSON key ("key":) and verify each key appears in source code.
    json_keys = re.findall(r'"([A-Za-z0-9_]+)"\s*:', stripped)
    if json_keys:
        return all(f'"{k}"' in sources_text or f"'{k}'" in sources_text for k in json_keys)

    # Plaintext stdout PASS lines: replace <placeholder> spans and bracketed file/plugin lists with wildcards,
    # then verify every remaining fixed literal segment (length >= 3) occurs in sources_text.
    cleaned = PLACEHOLDER_RX.sub("\n", stripped)
    cleaned = re.sub(r"\[[^\]]*\]", "\n", cleaned)
    cleaned = re.sub(r"\([^)]*\)", "\n", cleaned)
    cleaned = re.sub(r"\*[A-Za-z0-9_.-]+\.esm", "\n", cleaned)
    cleaned = re.sub(r"\bFO4(?:Port|DLC)[A-Za-z0-9_.-]*", "\n", cleaned)
    segments = [seg.strip(" :\\/") for seg in cleaned.splitlines()]
    fixed_segments = [seg for seg in segments if len(seg) >= 3]
    if not fixed_segments:
        return False
    return all(seg in sources_text for seg in fixed_segments)


class LeadCardsDlcTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.help_cache = HelpCache()
        cls.cards = {}
        for rel in CARD_FILES:
            p = ROOT / rel
            if not p.is_file():
                raise AssertionError(f"Missing lead card file: {rel}")
            cls.cards[rel] = p.read_text(encoding="utf-8")
        cls.sources_text = "\n".join(
            (ROOT / s).read_text(encoding="utf-8")
            for s in ("scripts/deploy_starfield.py", "scripts/terrain/interior_batch.py")
        )

    def test_only_dlc_branch_card_is_read_and_no_naked_commands_outside_fences(self):
        self.assertEqual(CARD_FILES, ("docs/testing/dlc-and-interiors-lead-card.md",))
        for rel, text in self.cards.items():
            for line_no, stripped in extract_outside_fence_lines(text):
                self.assertFalse(
                    stripped.startswith(("python ", "dotnet ")),
                    f"{rel}:{line_no} has runnable command outside a fenced code block: {stripped!r}",
                )

    def test_every_fenced_command_flag_is_accepted_by_subprocess_help(self):
        cmd_count = 0
        for rel, text in self.cards.items():
            for heading, _info, lines in parse_fenced_blocks(text):
                for raw in lines:
                    s = raw.strip()
                    if s.startswith(("python ", "dotnet ")):
                        validate_command_line(s, self.help_cache)
                        cmd_count += 1
                    elif "pass" not in heading.lower() and s and not s.startswith(("#", "coc ")):
                        self.fail(f"{rel} ({heading}): unexpected non-command line inside non-PASS fence: {s!r}")
        self.assertGreaterEqual(cmd_count, 8)

    def test_card_structure_d4_uninstall_safety_and_dropped_checks(self):
        text = self.cards["docs/testing/dlc-and-interiors-lead-card.md"]
        sections = re.split(r"(?m)^##\s+", text)
        card_sections = [s for s in sections[1:] if s.startswith("Card ")]
        self.assertEqual(len(card_sections), 2, "Expected Card 1 (FO4DLC swap) and Card 2 (Batch 11 offline build)")

        for card in card_sections:
            title = card.splitlines()[0]
            self.assertRegex(card, r"<[a-z0-9-]+-stage>", f"{title}: missing <...-stage> placeholder")
            self.assertIn("Plugins.txt", card, f"{title}: missing Plugins.txt load list")
            self.assertIn("--min-free-gb 40", card, f"{title}: missing 40 GB free-space need")
            self.assertIn("deploy_starfield.py install --batch", card, f"{title}: missing install command")
            self.assertIn("deploy_starfield.py uninstall", card, f"{title}: missing undo command")

        card1, card2 = card_sections
        # Card 1 uninstall MUST carry --plugin-name FO4DLC.esm, and prose must warn about FO4Port.esm without it.
        c1_blocks = parse_fenced_blocks("## " + card1)
        c1_uninstalls = [
            ln.strip()
            for _h, _i, lines in c1_blocks
            for ln in lines
            if ln.strip().startswith("python scripts/deploy_starfield.py uninstall")
        ]
        self.assertTrue(c1_uninstalls, "Card 1 must have a fenced deploy_starfield.py uninstall command")
        for u_line in c1_uninstalls:
            self.assertIn("--plugin-name FO4DLC.esm", u_line)
        self.assertIn("Without `--plugin-name FO4DLC.esm`", card1)
        self.assertIn("FO4Port.esm", card1)

        # Card 1 must NOT ask to swap-test the 269-cell base port or visually inspect the 58 SCOL meshes in FO4DLC.esm.
        self.assertNotIn("coc FO4Port_ConcordMuseum01", text)
        self.assertNotIn("coc FO4Port_DLC01Lair01", text)

        # Card 2 must include D6 Automatron extra args and note D3 seed-check behavior.
        self.assertIn("--dlc-data", card2)
        self.assertIn("--dlc-plugins DLCRobot.esm", card2)
        self.assertIn("--work <new-work-dir>", card2)
        self.assertIn("seed_check", card2)
        self.assertIn("in no built plugin yet", text)

    def test_console_editor_ids_match_writer_constants_and_pluginspike(self):
        text = self.cards["docs/testing/dlc-and-interiors-lead-card.md"]
        console_edids = []
        for _heading, info, lines in parse_fenced_blocks(text):
            if info == "console":
                for ln in lines:
                    s = ln.strip()
                    if s.startswith("coc "):
                        console_edids.append(s.split()[1])
        self.assertEqual(
            console_edids,
            ["FO4DLC_DLC03Acadia", "FO4DLC_DLC04BradbertonsOffice01", "FO4DLC_DLC06VaultWorkshop"],
        )

        # Check against interior_dlc + pipeline + PluginSpike/Program.cs writer pattern.
        expected_prefix = pipeline.editor_id_prefix(interior_dlc.DEFAULT_PREFIX)
        self.assertEqual(expected_prefix, "FO4DLC")
        program_cs = (ROOT / "dotnet" / "PluginSpike" / "Program.cs").read_text(encoding="utf-8")
        self.assertIn('var cellName = $"{edidPrefix}_{src4}";', program_cs)

        census_cells = {
            r["editor_id"]
            for r in [
                {"editor_id": "DLC03Acadia", "owner": "DLCCoast"},
                {"editor_id": "DLC04BradbertonsOffice01", "owner": "DLCNukaWorld"},
                {"editor_id": "DLC06VaultWorkshop", "owner": "DLCworkshop03"},
            ]
        }
        for edid in console_edids:
            self.assertTrue(edid.startswith(expected_prefix + "_"))
            raw_cell = edid[len(expected_prefix) + 1 :]
            self.assertIn(raw_cell, census_cells)
            self.assertIn(raw_cell[:5], ("DLC03", "DLC04", "DLC06"))
            for stem in interior_dlc.DLC_LOAD_ORDER:
                self.assertTrue(isinstance(stem, str) and stem)

        # Also verify PluginSpike.dll emits these exact CELL keys when dotnet is present.
        dll = ensure_pluginspike_dll(ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            sf_data = Path(tmp) / "sf_data"
            sf_data.mkdir()
            man = Path(tmp) / "manifest.json"
            man.write_text(
                json.dumps({"items": [{"editor_id": "FO4DLC_Wall", "model": "fo4dlc\\w.nif", "source": "DLC\\W.nif"}], "failures": []}),
                encoding="utf-8",
            )
            cell_files = []
            for raw_cell in sorted(census_cells):
                cp = Path(tmp) / f"{raw_cell}.json"
                cp.write_text(json.dumps({"schema_version": 3, "cell": raw_cell, "refs": []}), encoding="utf-8")
                cell_files.append(str(cp))
            out_dir = Path(tmp) / "out"
            subprocess.run(
                ["dotnet", dll, str(out_dir), str(man), "--plugin-name", interior_dlc.DEFAULT_PLUGIN, "--edid-prefix", expected_prefix, *cell_files],
                check=True,
                env=dict(os.environ, STARFIELD_DATA=str(sf_data)),
                capture_output=True,
            )
            fids = json.loads((out_dir / "formids.json").read_text(encoding="utf-8"))
            for edid in console_edids:
                self.assertIn(f"CELL:{edid}", fids)

    def test_pass_blocks_match_source_format_strings_and_keys(self):
        pass_lines = []
        for _rel, text in self.cards.items():
            for heading, _info, lines in parse_fenced_blocks(text):
                if "pass" in heading.lower():
                    for ln in lines:
                        if ln.strip():
                            pass_lines.append((heading, ln))
        self.assertGreaterEqual(len(pass_lines), 10)
        for heading, ln in pass_lines:
            self.assertTrue(
                pass_line_matches_sources(ln, self.sources_text),
                f"PASS line under {heading!r} does not match tool sources: {ln!r}",
            )

    def test_validator_rejects_bogus_flags_and_bogus_pass_lines(self):
        with self.assertRaises(AssertionError):
            validate_command_line(
                "python scripts/deploy_starfield.py uninstall --starfield <starfield-dir> --bogus-flag",
                self.help_cache,
            )
        with self.assertRaises(AssertionError):
            validate_command_line(
                "python scripts/terrain/interior_batch.py build --plan <p> --batch 10",
                self.help_cache,
            )
        self.assertFalse(pass_line_matches_sources("completely_invented_pass_phrase_xyz", self.sources_text))
        self.assertFalse(pass_line_matches_sources('"nonexistent_json_key_xyz": true', self.sources_text))


if __name__ == "__main__":
    unittest.main()
