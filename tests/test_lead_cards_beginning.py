"""Rule R11 lead-card validator for `gemini/beginning-real` (#833).

Reads ONLY the three lead-card files owned by `gemini/beginning-real`:
  - `docs/testing/candidate-2-cards.md`
  - `docs/testing/fo4-beginning-pilot.md`
  - `docs/testing/sanctuary-workbench-card.md`

Verifies that:
  1. Every card file states `NEW GAME needed` near the top and contains zero leaked local drive paths (`R4`).
  2. Every `## Card ...` section includes fenced runnable CLI commands, exact install command with `--plugins`,
     `<placeholder>` stage/game paths, disk space need, exact undo command, and a fenced ```log PASS block.
  3. Every `python ` or `dotnet ` command's `--flags` exist in `<tool> [subcommand] --help` (via subprocess).
  4. Every in-game console command's EditorIDs, FormIDs, and quest stages exist in the writers' constants /
     `core_values.json`.
  5. Every PASS log line's fixed words match a real format string in the C++ / Papyrus sources.
"""
from __future__ import annotations

import re
import shlex
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Dict, List, Optional, Pattern, Sequence, Set, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from fo4sf.core.cross_plugin_check import build_writer_catalog  # noqa: E402

# R11: read ONLY the three card files owned by gemini/beginning-real (#833)
CARD_PATHS: Tuple[str, ...] = (
    "docs/testing/candidate-2-cards.md",
    "docs/testing/fo4-beginning-pilot.md",
    "docs/testing/sanctuary-workbench-card.md",
)

CONSOLE_VERBS = frozenset({
    "coc",
    "prid",
    "player.moveto",
    "moveto",
    "setstage",
    "setgs",
    "set",
    "help",
    "player.additem",
    "additem",
    "setpqv",
    "startquest",
    "stopquest",
    "cgf",
})

FENCED_BLOCK_RE = re.compile(r"```([A-Za-z0-9_-]*)\r?\n(.*?)```", re.S)


def _join_cpp_adjacent_strings(cpp_text: str) -> str:
    return re.sub(r'"\s*\r?\n\s*"', "", cpp_text)


def _psc_concat_expr_to_template(expr: str) -> Optional[str]:
    """Convert a Papyrus string concatenation expression (`"a=" + x + " b=" + y`) into `a={} b={}`."""
    s = expr.strip()
    if '"' not in s:
        return None
    # Replace `" + <non-quote-expr> + "` with `{}`
    tpl = re.sub(r'"\s*\+\s*[^"]+\s*\+\s*"', "{}", s)
    # Leading `<expr> + "`
    tpl = re.sub(r'^[^"]+\+\s*"', "{}", tpl)
    # Trailing `" + <expr>`
    tpl = re.sub(r'"\s*\+\s*[^"]+$', "{}", tpl)
    if tpl.startswith('"'):
        tpl = tpl[1:]
    if tpl.endswith('"'):
        tpl = tpl[:-1]
    return tpl


def collect_source_format_patterns(repo_root: Path) -> List[Tuple[str, str, Pattern[str]]]:
    """Extract real log format templates from C++ and Papyrus sources and compile matching regexes."""
    templates: List[Tuple[str, str]] = []

    # 1. C++ sources (REX::INFO, REX::ERROR, REX::WARN, std::format, emplace_back)
    sfse_dir = repo_root / "sfse"
    for ext in ("*.cpp", "*.h"):
        for fp in sorted(sfse_dir.rglob(ext)):
            rel = fp.relative_to(repo_root).as_posix()
            joined = _join_cpp_adjacent_strings(fp.read_text(encoding="utf-8", errors="replace"))
            for m in re.finditer(
                r'(?:REX::(?:INFO|ERROR|WARN)|std::format|emplace_back)\(\s*"((?:[^"\\\r\n]|\\.)+)"',
                joined,
            ):
                raw_tpl = m.group(1).replace(r'\"', '"').replace(r"\\", "\\")
                templates.append((rel, raw_tpl))

    # 2. Papyrus sources (Trace, LogNewGameLine, Debug.TraceUser, and LogLine helpers)
    scripts_dir = repo_root / "scripts"
    for fp in sorted(scripts_dir.rglob("*.psc")):
        rel = fp.relative_to(repo_root).as_posix()
        txt = fp.read_text(encoding="utf-8", errors="replace")

        # Detect `Function Trace(string msg)` user-log prefix (e.g. "FO4SF_NEWGAME rt=" or "FO4SF_MISSION rt=")
        trace_prefix: Optional[str] = None
        m_tr = re.search(
            r'Function\s+Trace\([^)]*\).*?Debug\.TraceUser\(\s*(?:[A-Za-z_]\w*|"[^"]+")\s*,\s*"(FO4SF_[A-Z0-9_]+\s+rt=)"',
            txt,
            re.S | re.I,
        )
        if m_tr:
            trace_prefix = m_tr.group(1).rstrip()

        # Detect `Function LogLine(string kind, string kv)` wrapper (e.g. FO4SF_HardcoreQuest.psc / FO4SF_ProgressionQuest.psc)
        logline_prefix: Optional[str] = None
        logline_sep: str = " "
        logline_suffix: str = ""
        m_ll = re.search(
            r'Function\s+LogLine\([^)]*\).*?Debug\.TraceUser\(\s*"[^"]+"\s*,\s*"([^"]+)"\s*\+[^\n]*\+\s*kv(?:\s*\+\s*"([^"]*)")?\s*\)',
            txt,
            re.S | re.I,
        )
        if m_ll:
            logline_prefix = m_ll.group(1)
            logline_suffix = m_ll.group(2) or ""
        else:
            m_ll_prog = re.search(
                r'Function\s+LogLine\(\s*string\s+\w+\s*,\s*string\s+\w+\s*\).*?Debug\.TraceUser\(\s*"[^"]+"\s*,\s*"(\[FO4SF_Progression\]\s+step=)"',
                txt,
                re.S | re.I,
            )
            if m_ll_prog:
                logline_prefix = m_ll_prog.group(1)
                logline_sep = " "

        has_log_ng = bool(re.search(r"Function\s+LogNewGameLine\(", txt, re.I))

        for raw_line in txt.splitlines():
            code = raw_line.split(";", 1)[0].strip()
            if not code or code.startswith("Function "):
                continue

            # Trace(<expr>)
            mt = re.search(r"\bTrace\((.+)\)\s*$", code)
            if mt:
                msg_tpl = _psc_concat_expr_to_template(mt.group(1))
                if msg_tpl:
                    templates.append((rel, msg_tpl))
                    if trace_prefix:
                        templates.append((rel, f"{trace_prefix}{{}} {msg_tpl}"))

            # LogNewGameLine(<expr>) -> writes into fo4sf_newgame with `FO4SF_NEWGAME rt=<rt> <msg>`
            if has_log_ng:
                mng = re.search(r"\bLogNewGameLine\((.+)\)\s*$", code)
                if mng:
                    ng_tpl = _psc_concat_expr_to_template(mng.group(1))
                    if ng_tpl:
                        templates.append((rel, ng_tpl))
                        templates.append((rel, f"FO4SF_NEWGAME rt={{}} {ng_tpl}"))

            # LogLine("<kind>", <kv_expr>)
            if logline_prefix is not None:
                lm = re.search(r'\bLogLine\(\s*"([^"]+)"\s*,\s*(.+)\)\s*$', code)
                if lm:
                    kind = lm.group(1)
                    kv_tpl = _psc_concat_expr_to_template(lm.group(2))
                    if kv_tpl is not None:
                        if logline_prefix.endswith("step="):
                            full_tpl = f"{logline_prefix}{kind}{logline_sep}{kv_tpl}{logline_suffix}"
                        else:
                            full_tpl = f"{logline_prefix}{{}} {kind} {kv_tpl}{logline_suffix}"
                        templates.append((rel, full_tpl))

    compiled: List[Tuple[str, str, Pattern[str]]] = []
    for rel, tpl in templates:
        norm_tpl = re.sub(r"(\{[^{}]*\})+", "{}", tpl)
        parts = norm_tpl.split("{}")
        regex_str = "^" + r"[^\r\n]+".join(re.escape(p) for p in parts) + "$"
        compiled.append((rel, tpl, re.compile(regex_str)))
    return compiled


def collect_writer_symbols(repo_root: Path) -> Tuple[Set[str], Set[int], Dict[str, Set[int]]]:
    """Return `(all_edids_exact, all_local_formids, {quest_edid_lower: set_of_stages})` across writers."""
    catalog, _ = build_writer_catalog(str(repo_root))
    edids: Set[str] = set()
    form_ids: Set[int] = set()
    quest_stages: Dict[str, Set[int]] = {}

    for _plg, recs in catalog.items():
        for fid, (_rtype, edid) in recs.items():
            form_ids.add(fid)
            if edid:
                edids.add(edid)

    dotnet_dir = repo_root / "dotnet"
    if dotnet_dir.is_dir():
        for prog in sorted(dotnet_dir.rglob("*.cs")):
            cs = prog.read_text(encoding="utf-8", errors="replace")
            for m in re.finditer(r'"(FO4(?:SF)?_[A-Za-z0-9_]+)"', cs):
                edids.add(m.group(1))
            for m in re.finditer(r"\b0x[0-9A-Fa-f]+u?\b", cs):
                form_ids.add(int(m.group(0).rstrip("uU"), 16))
            qm = re.search(r'\bQuestEdid\s*=\s*"([^"]+)"', cs)
            sm = re.search(r"Stages\s*=\s*\{([^}]+)\}", cs)
            if qm and sm:
                q_edid = qm.group(1).lower()
                stages = {int(tok.strip(), 0) for tok in sm.group(1).split(",") if tok.strip().isdigit()}
                quest_stages[q_edid] = stages

    for psc in sorted((repo_root / "scripts").rglob("*.psc")):
        txt = psc.read_text(encoding="utf-8", errors="replace")
        sm = re.search(r"(?im)^Scriptname\s+(FO4SF_[A-Za-z0-9_]+)\b", txt)
        if sm:
            edids.add(sm.group(1))
    for ext in ("*.cpp", "*.h"):
        for cpp in sorted((repo_root / "sfse").rglob(ext)):
            txt = cpp.read_text(encoding="utf-8", errors="replace")
            for mm in re.finditer(r'"(FO4SF_[A-Za-z0-9_]+)"', txt):
                edids.add(mm.group(1))

    return edids, form_ids, quest_stages


def _sample_from_card_line(card_line: str) -> str:
    def _repl(m: re.Match[str]) -> str:
        inner = m.group(1)
        if "|" in inner:
            return inner.split("|", 1)[0]
        if inner in ("0", "1"):
            return inner
        if "hex" in inner.lower():
            return "001234AB"
        return "1"

    return re.sub(r"<([^>\r\n]+)>", _repl, card_line)


def _extract_fixed_tokens(card_line: str) -> List[str]:
    stripped = re.sub(r"<[^>\r\n]+>", "<PH>", card_line)
    fixed: List[str] = []
    for raw_tok in stripped.split():
        tok = raw_tok.strip(",;()\"'")
        if not tok or "<PH>" in tok:
            continue
        fixed.append(tok)
    return fixed


class HelpRunner:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self._cache: Dict[Tuple[str, ...], Tuple[int, str]] = {}

    def get_help_flags(self, cmd_tokens: Sequence[str]) -> Tuple[Set[str], str]:
        if not cmd_tokens:
            return set(), ""
        head = cmd_tokens[0]
        if head == "python":
            if len(cmd_tokens) < 2:
                return set(), "missing script path after python"
            script_rel = cmd_tokens[1]
            script_abs = self.repo_root / script_rel
            if not script_abs.is_file():
                return set(), f"script does not exist: {script_rel}"
            subcmd: Optional[str] = None
            if len(cmd_tokens) >= 3 and not cmd_tokens[2].startswith("-"):
                subcmd = cmd_tokens[2]
            key = ("python", script_rel, subcmd or "")
            if key not in self._cache:
                argv = [sys.executable, str(script_abs)]
                if subcmd:
                    argv.append(subcmd)
                argv.append("--help")
                proc = subprocess.run(argv, cwd=str(self.repo_root), capture_output=True, text=True)
                if proc.returncode != 0 and subcmd:
                    proc = subprocess.run(
                        [sys.executable, str(script_abs), "--help"],
                        cwd=str(self.repo_root),
                        capture_output=True,
                        text=True,
                    )
                self._cache[key] = (proc.returncode, (proc.stdout or "") + "\n" + (proc.stderr or ""))
            rc, out = self._cache[key]
            if rc != 0:
                return set(), f"--help failed ({rc}) for {script_rel}: {out.strip()}"
            return set(re.findall(r"--[A-Za-z0-9][A-Za-z0-9_-]*", out)), ""

        if head == "dotnet":
            if not shutil.which("dotnet"):
                return set(), "SKIP_NO_DOTNET"
            proj_idx = cmd_tokens.index("--project") + 1 if "--project" in cmd_tokens else -1
            if proj_idx <= 0 or proj_idx >= len(cmd_tokens):
                return set(), f"unsupported dotnet invocation: {' '.join(cmd_tokens)}"
            proj_rel = cmd_tokens[proj_idx]
            key = ("dotnet", proj_rel)
            if key not in self._cache:
                proc = subprocess.run(
                    ["dotnet", "run", "--project", str(self.repo_root / proj_rel), "--", "--help"],
                    cwd=str(self.repo_root),
                    capture_output=True,
                    text=True,
                )
                self._cache[key] = (proc.returncode, (proc.stdout or "") + "\n" + (proc.stderr or ""))
            _, out = self._cache[key]
            return set(re.findall(r"--[A-Za-z0-9][A-Za-z0-9_-]*", out)), ""

        return set(), ""


def _token_matches_template(fixed_tok: str, src_tpl: str) -> bool:
    if fixed_tok in src_tpl:
        return True
    if "=" in fixed_tok:
        key_prefix = fixed_tok.split("=", 1)[0] + "="
        if key_prefix in src_tpl:
            return True
    # Allow integer/float literal token instantiated into `{}` placeholder (e.g. `stage 35` matching `stage {}`)
    if re.fullmatch(r"-?\d+(?:\.\d+)?", fixed_tok) and "{}" in src_tpl:
        return True
    return False


def validate_lead_card_markdown(
    card_rel: str,
    md_text: str,
    *,
    help_runner: HelpRunner,
    source_patterns: Sequence[Tuple[str, str, Pattern[str]]],
    writer_edids: Set[str],
    writer_fids: Set[int],
    quest_stages: Dict[str, Set[int]],
) -> List[str]:
    errors: List[str] = []
    top_header = "\n".join(md_text.splitlines()[:12])
    if "NEW GAME needed" not in top_header:
        errors.append(f"{card_rel}: missing 'NEW GAME needed' banner at top of card")

    for sym in sorted(set(re.findall(r"\bFO4SF_[A-Za-z0-9_]+\b", md_text))):
        if sym not in writer_edids and sym not in ("FO4SF_NEWGAME", "FO4SF_MISSION"):
            errors.append(f"{card_rel}: unknown FO4SF_* identifier {sym!r} (not in writer/script/C++ constants)")

    sections = re.split(r"(?m)^##\s+(Card\s+[^\r\n]+)$", md_text)
    if len(sections) < 3:
        errors.append(f"{card_rel}: no '## Card ...' sections found")
        return errors

    for idx in range(1, len(sections), 2):
        card_title = sections[idx].strip()
        body = sections[idx + 1]
        body = re.split(r"(?m)^##\s+(?!Card\b)", body, maxsplit=1)[0]

        blocks = FENCED_BLOCK_RE.findall(body)
        if not blocks:
            errors.append(f"{card_rel} [{card_title}]: contains zero fenced blocks")
            continue

        has_install = False
        has_undo = False
        has_plugins_flag = False
        has_pass_block = False

        if not re.search(r"<[A-Za-z0-9_-]+>", body):
            errors.append(f"{card_rel} [{card_title}]: missing <placeholder> stage/game path")
        if not re.search(r"\b\d+(?:\.\d+)?\s*(?:B|KB|MB|GB|GiB|MiB)\b", body):
            errors.append(f"{card_rel} [{card_title}]: missing disk need statement")

        for lang, block_body in blocks:
            lang_low = lang.strip().lower()
            lines = [ln.strip() for ln in block_body.splitlines() if ln.strip() and not ln.strip().startswith("#")]
            if lang_low == "log":
                has_pass_block = True
                for pline in lines:
                    sample = _sample_from_card_line(pline)
                    fixed_toks = _extract_fixed_tokens(pline)
                    matched = False
                    for _src_rel, src_tpl, pat in source_patterns:
                        if pat.search(sample) and all(_token_matches_template(ft, src_tpl) for ft in fixed_toks):
                            matched = True
                            break
                    if not matched:
                        errors.append(
                            f"{card_rel} [{card_title}]: PASS line does not match any source format string: {pline!r}"
                        )
                continue

            for cline in lines:
                if "exp_install.py install" in cline:
                    has_install = True
                    if "--plugins " in cline:
                        has_plugins_flag = True
                if "exp_install.py uninstall" in cline:
                    has_undo = True

                if cline.startswith(("python ", "dotnet ")):
                    sanitized = re.sub(r"<[^>\s]+>", "PLACEHOLDER", cline)
                    tokens = shlex.split(sanitized, posix=True)
                    used_flags = [t.split("=", 1)[0] for t in tokens if t.startswith("--") and t != "--"]
                    allowed_flags, err = help_runner.get_help_flags(tokens)
                    if err == "SKIP_NO_DOTNET":
                        continue
                    if err:
                        errors.append(f"{card_rel} [{card_title}]: {err}")
                        continue
                    for fl in used_flags:
                        if fl not in allowed_flags:
                            errors.append(
                                f"{card_rel} [{card_title}]: flag {fl!r} not in --help for command: {cline}"
                            )
                    continue

                first_word = cline.split()[0].lower()
                if lang_low == "console" or first_word in CONSOLE_VERBS:
                    parts = cline.split()
                    verb = parts[0].lower()
                    if verb == "coc" and len(parts) >= 2:
                        cell_edid = parts[1]
                        if cell_edid not in writer_edids:
                            errors.append(
                                f"{card_rel} [{card_title}]: console 'coc {cell_edid}' EditorID not in writer constants"
                            )
                    elif verb == "setstage" and len(parts) >= 3:
                        q_edid, stg_raw = parts[1], parts[2]
                        if q_edid not in writer_edids:
                            errors.append(
                                f"{card_rel} [{card_title}]: console 'setstage {q_edid}' Quest EditorID not in writer constants"
                            )
                        elif q_edid.lower() in quest_stages and stg_raw.isdigit():
                            stg = int(stg_raw, 10)
                            if stg not in quest_stages[q_edid.lower()]:
                                errors.append(
                                    f"{card_rel} [{card_title}]: console 'setstage {q_edid} {stg}' stage not in writer Stages"
                                )
                    elif verb == "help" and len(parts) >= 2:
                        target_edid = parts[1].strip('"')
                        if target_edid not in writer_edids:
                            errors.append(
                                f"{card_rel} [{card_title}]: console 'help {target_edid}' EditorID not in writer constants"
                            )

                    for ed_tok in re.findall(r"\bFO4SF_[A-Za-z0-9_]+\b", cline):
                        if ed_tok not in writer_edids:
                            errors.append(
                                f"{card_rel} [{card_title}]: console EditorID {ed_tok!r} not in writer constants"
                            )
                    for hex_tok in re.findall(r"\b0x[0-9A-Fa-f]+\b", cline):
                        fid_val = int(hex_tok, 16)
                        if (fid_val & 0xFFFFFF) not in writer_fids and fid_val not in writer_fids:
                            errors.append(
                                f"{card_rel} [{card_title}]: console FormID {hex_tok} not in writer constants"
                            )

        if not has_install:
            errors.append(f"{card_rel} [{card_title}]: missing fenced install command")
        if not has_plugins_flag:
            errors.append(f"{card_rel} [{card_title}]: install command missing --plugins list")
        if not has_undo:
            errors.append(f"{card_rel} [{card_title}]: missing fenced undo command")
        if not has_pass_block:
            errors.append(f"{card_rel} [{card_title}]: missing fenced ```log PASS block")

    return errors


class LeadCardsBeginningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.help_runner = HelpRunner(ROOT)
        cls.source_patterns = collect_source_format_patterns(ROOT)
        cls.writer_edids, cls.writer_fids, cls.quest_stages = collect_writer_symbols(ROOT)

    def test_beginning_lead_cards_pass_r11(self) -> None:
        self.assertEqual(
            CARD_PATHS,
            (
                "docs/testing/candidate-2-cards.md",
                "docs/testing/fo4-beginning-pilot.md",
                "docs/testing/sanctuary-workbench-card.md",
            ),
        )
        self.assertGreater(len(self.source_patterns), 80)
        for rel in CARD_PATHS:
            card_path = ROOT / rel
            self.assertTrue(card_path.is_file(), f"missing lead card: {rel}")
            txt = card_path.read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"\b[A-Za-z]:[\\/]", txt), f"local path leaked in {rel}")
            errors = validate_lead_card_markdown(
                rel,
                txt,
                help_runner=self.help_runner,
                source_patterns=self.source_patterns,
                writer_edids=self.writer_edids,
                writer_fids=self.writer_fids,
                quest_stages=self.quest_stages,
            )
            self.assertEqual(errors, [], "\n".join(errors))

    def test_r11_validator_rejects_bad_flags_wrong_edids_missing_new_game_and_stale_pass_lines(self) -> None:
        bad_card = """# Stale Card

## Card Z — Negative Control
Disk need: 10 MB on <stage-dir>.

```bash
python scripts/testing/check_beginning_pilot.py check-logs --nonexistent-flag <stage-dir>
python scripts/game/exp_install.py install --exp-dir <stage-dir> --starfield <game-dir> --plugins FO4SFCoreValues.esm --pack
python scripts/game/exp_install.py uninstall --starfield <game-dir>
```

```console
help FO4SF_NonexistentGlobal 4 GLOB
setstage FO4SF_Min00 999
```

```log
FO4SF_NEWGAME rt=<rt> special box shown buttons=10
FO4SF_NEWGAME rt=<rt> lift cage_door=closing_for_ride
FO4SF_MISSION rt=<rt> min01 stage 10 objective bench
```
"""
        errors = validate_lead_card_markdown(
            "docs/testing/candidate-2-cards.md",
            bad_card,
            help_runner=self.help_runner,
            source_patterns=self.source_patterns,
            writer_edids=self.writer_edids,
            writer_fids=self.writer_fids,
            quest_stages=self.quest_stages,
        )
        joined = "\n".join(errors)
        self.assertIn("NEW GAME needed", joined)
        self.assertIn("--nonexistent-flag", joined)
        self.assertIn("FO4SF_NonexistentGlobal", joined)
        self.assertIn("setstage FO4SF_Min00 999", joined)
        self.assertIn("special box shown buttons=10", joined)
        self.assertIn("closing_for_ride", joined)
        self.assertIn("min01 stage 10 objective bench", joined)


if __name__ == "__main__":
    unittest.main()
