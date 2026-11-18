"""R11 lead-card contract tests for `#832` (`gemini/world-own-space`).

Reads ONLY `docs/testing/home-world-lead-card.md` as its card input (`R11`) and verifies:
  1. Every runnable `python ` / `dotnet ` command is inside a fenced block, and every `--flag` it passes is accepted
     by `<tool> [subcommand] --help` executed in a clean-`PYTHONPATH` subprocess.
  2. Every in-game console `coc <EditorID>` target on the cards exists in the repo's writer constants.
  3. Every fenced PASS output line matches actual format strings / report keys in the repo's source files.
  4. Every card (`Card 1`..`Card 5`) states its stage `<placeholder>`, `Plugins.txt` load list, disk space need,
     exact install command, and exact undo command, plus `C5`/`C6`/`C7`/`C9`/`C11` invariants.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
CARD_FILES: tuple[str, ...] = ("docs/testing/home-world-lead-card.md",)
CARD_FILE = ROOT / CARD_FILES[0]

SOURCE_FORMAT_FILES: tuple[Path, ...] = (
    ROOT / "scripts" / "planet" / "make_home_planet.py",
    ROOT / "scripts" / "planet" / "home_world_install.py",
    ROOT / "scripts" / "game" / "exp_install.py",
    ROOT / "src" / "fo4sf" / "terrain" / "overlay_postpatch.py",
    ROOT / "scripts" / "terrain" / "make_core64c.py",
    ROOT / "scripts" / "terrain" / "vmad_patch.py",
    ROOT / "scripts" / "bridge" / "door_rounds.py",
    ROOT / "scripts" / "terrain" / "make_wg1_redrocket.py",
)

WRITER_CONSTANT_FILES: tuple[Path, ...] = (
    ROOT / "src" / "fo4sf" / "core" / "world_registry.json",
    ROOT / "src" / "fo4sf" / "planet" / "home_planet_spec.py",
    ROOT / "src" / "fo4sf" / "planet" / "wb_records.py",
    ROOT / "src" / "fo4sf" / "planet" / "records.py",
    ROOT / "scripts" / "terrain" / "make_wg1_redrocket.py",
    ROOT / "scripts" / "bridge" / "border_walk.py",
    ROOT / "scripts" / "bridge" / "door_rounds.py",
    ROOT / "scripts" / "terrain" / "walk_route.py",
    ROOT / "dotnet" / "TerrainOverlays" / "Program.cs",
)

_FENCE_RE = re.compile(r"^```([A-Za-z0-9_-]*)\r?\n(.*?)^```", re.MULTILINE | re.DOTALL)
_FLAG_RE = re.compile(r"--[A-Za-z0-9][A-Za-z0-9_-]*")


def _extract_fenced_blocks(markdown_text: str) -> list[tuple[str, str]]:
    return [(m.group(1).strip().lower(), m.group(2)) for m in _FENCE_RE.finditer(markdown_text)]


def _strip_fenced_blocks(markdown_text: str) -> str:
    return _FENCE_RE.sub("", markdown_text)


def _split_cards(markdown_text: str) -> dict[int, str]:
    parts = re.split(r"(?=^## Card \d+\b)", markdown_text, flags=re.MULTILINE)
    out: dict[int, str] = {}
    for chunk in parts:
        m = re.match(r"^## Card (\d+)\b", chunk)
        if m:
            out[int(m.group(1))] = chunk
    return out


class LeadCardsWorldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not CARD_FILE.is_file():
            raise AssertionError(f"Missing lead card file: {CARD_FILE}")
        cls.card_text = CARD_FILE.read_text(encoding="utf-8")
        cls.fenced_blocks = _extract_fenced_blocks(cls.card_text)
        cls.cards = _split_cards(cls.card_text)
        cls._help_cache: dict[tuple[str, str], str] = {}

        cls.combined_sources = "\n".join(p.read_text(encoding="utf-8") for p in SOURCE_FORMAT_FILES)
        cls.combined_constants = "\n".join(p.read_text(encoding="utf-8") for p in WRITER_CONSTANT_FILES)
        cls.registry_doc = json.loads((ROOT / "src" / "fo4sf" / "core" / "world_registry.json").read_text(encoding="utf-8"))

    @classmethod
    def _clean_env(cls) -> dict[str, str]:
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        return env

    @classmethod
    def _run_help(cls, script_rel: str, subcommand: str = "") -> str:
        key = (script_rel, subcommand)
        if key in cls._help_cache:
            return cls._help_cache[key]
        script_path = ROOT / script_rel
        if not script_path.is_file():
            raise AssertionError(f"Card references non-existent tool script: {script_rel}")
        argv = [sys.executable, "-B", str(script_path)]
        if subcommand:
            argv.append(subcommand)
        argv.append("--help")
        proc = subprocess.run(
            argv,
            cwd=str(ROOT),
            env=cls._clean_env(),
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise AssertionError(
                f"`{' '.join(argv)}` failed (rc={proc.returncode}):\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
            )
        cls._help_cache[key] = proc.stdout
        return proc.stdout

    @classmethod
    def _accepted_flags_for_python_line(cls, line: str) -> tuple[str, str, set[str], list[str]]:
        # Replace <placeholder> tokens containing spaces safely before shlex splitting
        sanitized = re.sub(r"<[^>]+>", "<placeholder>", line.strip())
        tokens = shlex.split(sanitized, posix=True)
        assert tokens and tokens[0] == "python", f"Expected python command, got {line!r}"
        idx = 1
        while idx < len(tokens) and tokens[idx].startswith("-"):
            idx += 1
        if idx >= len(tokens):
            raise AssertionError(f"Malformed python command on card: {line!r}")
        script_rel = tokens[idx]
        rest = tokens[idx + 1 :]
        used_flags = [tok.split("=", 1)[0] for tok in rest if tok.startswith("--")]

        top_help = cls._run_help(script_rel)
        accepted = set(_FLAG_RE.findall(top_help))

        subcmd = ""
        if rest and not rest[0].startswith("-") and not rest[0].startswith("<"):
            candidate = rest[0]
            # Check if top-level --help exposes subcommands `{a,b,c}` and whether `<script> <subcmd> --help` accepts `--help`
            sub_choices: set[str] = set()
            for brace_match in re.finditer(r"\{([A-Za-z0-9_,-]+)\}", top_help):
                sub_choices.update(x.strip() for x in brace_match.group(1).split(",") if x.strip())
            if candidate in sub_choices:
                # Tools using add_subparsers accept `<subcmd> --help`; positional `choices=` tools keep all flags at top-level.
                probe = subprocess.run(
                    [sys.executable, "-B", str(ROOT / script_rel), candidate, "--help"],
                    cwd=str(ROOT),
                    env=cls._clean_env(),
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if probe.returncode == 0 and "usage:" in probe.stdout.lower():
                    subcmd = candidate
                    cls._help_cache[(script_rel, subcmd)] = probe.stdout
                    accepted |= set(_FLAG_RE.findall(probe.stdout))

        return script_rel, subcmd, accepted, used_flags

    def test_no_runnable_commands_outside_fenced_blocks(self) -> None:
        outside = _strip_fenced_blocks(self.card_text)
        for lineno, raw_line in enumerate(outside.splitlines(), 1):
            stripped = raw_line.strip()
            self.assertFalse(
                stripped.startswith(("python ", "dotnet ")),
                f"Runnable command found outside fenced code block on line {lineno}: {raw_line!r}",
            )

    def test_every_fenced_python_and_dotnet_command_and_flag_is_accepted_by_help(self) -> None:
        cmd_lines: list[str] = []
        for lang, body in self.fenced_blocks:
            if lang in ("text", "console"):
                continue
            for raw_line in body.splitlines():
                stripped = raw_line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if stripped.startswith(("python ", "dotnet ")):
                    cmd_lines.append(stripped)

        self.assertGreaterEqual(len(cmd_lines), 18, "Expected runnable commands across Cards 1-5")

        for line in cmd_lines:
            if line.startswith("python "):
                script_rel, subcmd, accepted_flags, used_flags = self._accepted_flags_for_python_line(line)
                for flg in used_flags:
                    self.assertIn(
                        flg,
                        accepted_flags,
                        f"Flag {flg!r} in card command `{line}` is not accepted by `{script_rel} {subcmd} --help` "
                        f"(accepted: {sorted(accepted_flags)})",
                    )
            elif line.startswith("dotnet "):
                raise AssertionError(f"Unexpected dotnet line without handler: {line}")

        # Negative self-check: ensure validator catches Card 1's former bogus `--stage` flag on home_world_install.py
        _, _, hwi_flags, _ = self._accepted_flags_for_python_line(
            "python scripts/planet/home_world_install.py install --dir <home-stage> --starfield <game-dir>"
        )
        self.assertNotIn("--stage", hwi_flags)

    def test_every_console_coc_editor_id_exists_in_writer_constants(self) -> None:
        console_blocks = [body for lang, body in self.fenced_blocks if lang == "console"]
        self.assertGreaterEqual(len(console_blocks), 4, "Expected fenced ```console blocks on Cards 1, 2, 3, and 5")

        coc_targets: set[str] = set()
        for body in console_blocks:
            for raw in body.splitlines():
                stripped = raw.strip()
                if stripped.lower().startswith("coc "):
                    target = stripped.split()[1]
                    coc_targets.add(target)

        # Also catch any inline `coc FO4...` mentions anywhere in prose
        for m in re.finditer(r"\bcoc\s+(FO4[A-Za-z0-9_]+)\b", self.card_text):
            coc_targets.add(m.group(1))

        self.assertEqual(
            coc_targets,
            {
                "FO4Core_RedRocketSpawn",
                "FO4FH_FarHarborSpawn",
                "FO4NW_NukaWorldSpawn",
                "FO4WG1_RedRocketSpawn",
            },
        )
        for edid in sorted(coc_targets):
            self.assertTrue(
                f'"{edid}"' in self.combined_constants,
                f"Console coc EditorID {edid!r} not found as a string constant in writer sources",
            )

        # Verify all hex FormIDs named on the cards (e.g. 0x0003F59A, 0x000F04F2, 0x803) exist in writer constants
        haystack = self.combined_constants + "\n" + self.combined_sources
        for hex_m in re.finditer(r"\b0x[0-9A-Fa-f]{3,8}\b", self.card_text):
            fid_tok = hex_m.group(0)
            short_hex = fid_tok[2:].lstrip("0").upper() or "0"
            self.assertTrue(
                bool(re.search(rf"0x0*{re.escape(short_hex)}\b", haystack, re.IGNORECASE)),
                f"FormID {fid_tok} on card does not match any hex constant in writer sources",
            )

    def test_every_fenced_pass_line_matches_source_format_strings(self) -> None:
        pass_blocks = [body for lang, body in self.fenced_blocks if lang == "text"]
        self.assertEqual(len(pass_blocks), 5, "Each of Cards 1-5 must have a fenced ```text PASS block")
        haystack = self.combined_sources + "\n" + self.combined_constants

        for block_idx, body in enumerate(pass_blocks, 1):
            lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
            self.assertGreaterEqual(len(lines), 3, f"Card {block_idx} PASS block too short")
            for ln in lines:
                if ln.startswith('"') and ":" in ln:
                    json_key = ln.split(":", 1)[0].strip().strip('"')
                    self.assertTrue(
                        f'"{json_key}"' in self.combined_sources,
                        f"Card {block_idx} PASS JSON key {json_key!r} missing from writer/verifier sources",
                    )
                else:
                    # Check key= prefixes from f-strings (e.g. plugins=, system_id=, planet_id=, body_name=, biome=, levers=)
                    for key_eq in re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*=", ln):
                        self.assertTrue(
                            key_eq in self.combined_sources,
                            f"Format prefix {key_eq!r} in Card {block_idx} PASS line {ln!r} missing from writer sources",
                        )
                    # Strip <placeholder>, quoted plugin lists, and numeric literals; verify every identifier word exists
                    cleaned = re.sub(r"<[^>]+>", " ", ln)
                    cleaned = re.sub(r"\[[^\]]*\]", " ", cleaned)
                    cleaned = re.sub(r"0x[0-9A-Fa-f]+|\b\d+\b", " ", cleaned)
                    fixed_words = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", cleaned)
                    self.assertTrue(fixed_words, f"No fixed words extracted from PASS line {ln!r}")
                    for word in fixed_words:
                        if word in ("json",):
                            continue
                        self.assertTrue(
                            word in haystack,
                            f"Fixed word {word!r} in Card {block_idx} PASS line {ln!r} not found in repo sources",
                        )

    def test_cards_1_to_5_structure_and_c5_c6_c7_c9_c11_invariants(self) -> None:
        self.assertEqual(sorted(self.cards.keys()), [1, 2, 3, 4, 5])

        for card_num, text in self.cards.items():
            self.assertIn("**Stage Placeholder", text, f"Card {card_num} missing Stage Placeholder")
            self.assertIn("**Disk Space Need:**", text, f"Card {card_num} missing Disk Space Need")
            self.assertRegex(text, r"\b(MiB|GiB)\b", f"Card {card_num} missing MiB/GiB disk figure")
            self.assertIn("`Plugins.txt`", text, f"Card {card_num} missing Plugins.txt load list")
            self.assertRegex(text, r"\*FO4[A-Za-z0-9_]+\.esm", f"Card {card_num} missing *-prefixed plugin list")
            blocks = _extract_fenced_blocks(text)
            ps_cmds = "\n".join(b for lang, b in blocks if lang == "powershell")
            self.assertIn(" install ", ps_cmds, f"Card {card_num} missing fenced install command")
            self.assertTrue(
                (" undo " in ps_cmds) or (" uninstall " in ps_cmds),
                f"Card {card_num} missing fenced undo/uninstall command",
            )
            self.assertTrue(any(lang == "text" for lang, _ in blocks), f"Card {card_num} missing fenced ```text PASS block")

        # C9: Card 1 uses non-colliding fo4sf_home_earth.biom (never Data/PlanetData/BiomeMaps/earth.biom)
        self.assertIn("Data/PlanetData/BiomeMaps/fo4sf_home_earth.biom", self.cards[1])
        self.assertIn("Data/PlanetData/BiomeMaps/fo4sfhome.esm/fo4sf_home_earth.biom", self.cards[1])
        self.assertNotIn("Data/PlanetData/BiomeMaps/earth.biom", self.cards[1])

        # C5 & C7: Cards 3, 4, and 5 explicitly warn that *_Mars.esm overrides MarsPlanetData and REPLACES Commonwealth
        for card_num in (3, 4, 5):
            self.assertIn("MarsPlanetData", self.cards[card_num], f"Card {card_num} missing MarsPlanetData warning")
            self.assertIn("REPLACES the", self.cards[card_num], f"Card {card_num} missing REPLACES warning")

        # C11: Card 3 states TEST-STATION console-only + both Mars and Home Earth-radius cell distances matching registry
        fh_psw = next(w["planned_starfield_world"] for w in self.registry_doc["worlds"] if w["key"] == "FarHarbor")
        nw_psw = next(w["planned_starfield_world"] for w in self.registry_doc["worlds"] if w["key"] == "NukaWorld")
        self.assertEqual(fh_psw["reachability"], "TEST-STATION (coc only)")
        self.assertEqual(nw_psw["reachability"], "TEST-STATION (coc only)")
        for num_str in (
            f"{fh_psw['mars_separation_from_cw_cells']:,}",
            f"{fh_psw['home_separation_from_cw_cells']:,}",
            f"{nw_psw['mars_separation_from_cw_cells']:,}",
            f"{nw_psw['home_separation_from_cw_cells']:,}",
        ):
            self.assertIn(num_str, self.cards[3], f"Card 3 missing distance {num_str}")

        # C6: Card 4 explicitly holds live port install for WB4 and warns against installing Round-1 I3 port
        self.assertIn("HELD FOR WB4", self.cards[4])
        self.assertIn("DO NOT INSTALL", self.cards[4])
        self.assertIn("FO4SF_AnimatedLoadDoor", self.cards[4])


if __name__ == "__main__":
    unittest.main()
