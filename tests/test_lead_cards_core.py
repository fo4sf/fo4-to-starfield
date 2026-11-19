"""Rule R11 lead-card validator for `gemini/core-integration` (`docs/testing/task0-task1-lead-cards.md` only).

Verifies that every runnable CLI command's `--flags` exist in `<tool> [subcommand] --help` (via subprocess),
every in-game console command's EditorIDs, FormIDs, and quest stages exist in the writers' constants /
`core_values.json`, every PASS log line's fixed words match a real format string in the C++/Papyrus/Python
sources, and every card states its install command, `Plugins.txt` list, `<placeholder>` stage path, disk need,
and undo command.
"""
from __future__ import annotations

import os
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

# R11: read ONLY the card file owned by gemini/core-integration (#831)
CARD_PATHS: Tuple[str, ...] = ("docs/testing/task0-task1-lead-cards.md",)

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
    "sqv",
    "startquest",
    "stopquest",
})

FENCED_BLOCK_RE = re.compile(r"```([A-Za-z0-9_-]*)\r?\n(.*?)```", re.S)


def _join_cpp_adjacent_strings(cpp_text: str) -> str:
    return re.sub(r'"\s*\r?\n\s*"', "", cpp_text)


def collect_source_format_patterns(repo_root: Path) -> List[Tuple[str, str, Pattern[str]]]:
    """Extract real log format templates from C++, Papyrus, and Python sources and compile matching regexes."""
    templates: List[Tuple[str, str]] = []

    # 1. C++ sources (REX::INFO, REX::ERROR, std::format("step=..."), emplace_back("step=..."))
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

    # 2. Papyrus sources (Trace, Debug.TraceUser, and file-local LogLine(kind, kv) helpers)
    scripts_dir = repo_root / "scripts"
    for fp in sorted(scripts_dir.rglob("*.psc")):
        rel = fp.relative_to(repo_root).as_posix()
        txt = fp.read_text(encoding="utf-8", errors="replace")

        # Detect `LogLine(string kind, string kv)` prefix/suffix wrapper such as FO4SF_ListDialogueQuest.psc
        logline_prefix: Optional[str] = None
        logline_suffix: str = ""
        m_ll = re.search(
            r'Function\s+LogLine\([^)]*\).*?Debug\.TraceUser\(\s*"[^"]+"\s*,\s*"([^"]+)"\s*\+[^\n]*\+\s*kv(?:\s*\+\s*"([^"]*)")?\s*\)',
            txt,
            re.S | re.I,
        )
        if m_ll:
            # e.g. prefix="FO4SFLIST rt=", suffix=" end=true"
            logline_prefix = m_ll.group(1)
            logline_suffix = m_ll.group(2) or ""

        for raw_line in txt.splitlines():
            code = raw_line.split(";", 1)[0].strip()
            if not code:
                continue
            # Direct Trace("...") or Debug.TraceUser("...", "...")
            for tm in re.finditer(r'\b(?:Trace|TraceUser)\((?:"[^"]+"\s*,\s*)?"([^"\r\n]+)"\s*\)', code):
                templates.append((rel, tm.group(1)))

            if logline_prefix is not None:
                lm = re.search(r'\bLogLine\(\s*"([^"]+)"\s*,\s*(.+)\)\s*$', code)
                if lm:
                    kind = lm.group(1)
                    kv_expr = lm.group(2).strip()
                    # Replace `" + <expr> + "` and trailing `+ <expr>` in kv_expr with `{}`
                    kv_tpl = re.sub(r'"\s*\+\s*[^"]+\s*\+\s*"', "{}", kv_expr)
                    kv_tpl = re.sub(r'"\s*\+\s*[^"]+$', "{}", kv_tpl)
                    if kv_tpl.startswith('"'):
                        kv_tpl = kv_tpl[1:]
                    if kv_tpl.endswith('"'):
                        kv_tpl = kv_tpl[:-1]
                    full_tpl = f"{logline_prefix}{{}} {kind} {kv_tpl}{logline_suffix}"
                    templates.append((rel, full_tpl))

    compiled: List[Tuple[str, str, Pattern[str]]] = []
    for rel, tpl in templates:
        # Collapse adjacent `{}{}` (e.g. `args={}{}` where optional trailing detail may be empty) before wildcarding
        norm_tpl = re.sub(r"(\{[^{}]*\})+", "{}", tpl)
        parts = norm_tpl.split("{}")
        regex_str = "^" + r"[^\r\n]+".join(re.escape(p) for p in parts) + "$"
        compiled.append((rel, tpl, re.compile(regex_str)))
    return compiled


def collect_writer_symbols(repo_root: Path) -> Tuple[Set[str], Set[int], Dict[str, Set[int]]]:
    """Return `(all_edids_exact, all_local_formids, {quest_edid_lower: set_of_stages})` across all writers."""
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
        for prog in sorted(dotnet_dir.glob("*/Program.cs")):
            cs = prog.read_text(encoding="utf-8", errors="replace")
            for m in re.finditer(r'\bconst\s+string\s+\w*Edid\s*=\s*"([^"]+)"', cs):
                edids.add(m.group(1))
            for m in re.finditer(r"\bconst\s+uint\s+\w+\s*=\s*(0x[0-9A-Fa-f]+|\d+)", cs):
                form_ids.add(int(m.group(1), 0))
            qm = re.search(r'\bQuestEdid\s*=\s*"([^"]+)"', cs)
            sm = re.search(r"Stages\s*=\s*\{([^}]+)\}", cs)
            if qm and sm:
                q_edid = qm.group(1).lower()
                stages = {int(tok.strip(), 0) for tok in sm.group(1).split(",") if tok.strip().isdigit()}
                quest_stages[q_edid] = stages

    return edids, form_ids, quest_stages


def _sample_from_card_line(card_line: str) -> str:
    """Replace `<placeholder>` tokens in a card PASS line with representative values for regex matching."""
    def _repl(m: re.Match[str]) -> str:
        inner = m.group(1)
        if "|" in inner:
            return inner.split("|", 1)[0]
        if inner in ("0", "1"):
            return inner
        if "hex" in inner.lower():
            return "0x1234AB"
        return "1"

    return re.sub(r"<([^>\r\n]+)>", _repl, card_line)


def _extract_fixed_tokens(card_line: str) -> List[str]:
    """Extract fixed literal tokens (`step=...`, `key=literal`, standalone words) outside `<...>` placeholders."""
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
    sections = re.split(r"(?m)^##\s+(Card\s+[^\r\n]+)$", md_text)
    if len(sections) < 3:
        return [f"{card_rel}: no '## Card ...' sections found"]

    for idx in range(1, len(sections), 2):
        card_title = sections[idx].strip()
        body = sections[idx + 1]
        # Trim trailing non-card footer sections (`## Explicitly ...`)
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
                        if pat.search(sample) and all(
                            (ft in src_tpl) or (ft.split("=", 1)[0] + "=" in src_tpl) for ft in fixed_toks
                        ):
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
                        if re.fullmatch(r"<[A-Za-z0-9_-]+>", q_edid):
                            if stg_raw.isdigit():
                                stg = int(stg_raw, 10)
                                if not any(stg in stgs for stgs in quest_stages.values()):
                                    errors.append(
                                        f"{card_rel} [{card_title}]: console 'setstage {q_edid} {stg}' stage not in any writer Stages"
                                    )
                        elif q_edid not in writer_edids:
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
                        rest_help = cline.split(None, 1)[1].lstrip()
                        if not rest_help.startswith('"'):
                            target_edid = parts[1].strip('"')
                            if target_edid not in writer_edids:
                                errors.append(
                                    f"{card_rel} [{card_title}]: console 'help {target_edid}' EditorID not in writer constants"
                                )

                    # Also verify any FO4SF_* EditorID or concrete 0x... FormID anywhere on the console line
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


class LeadCardsCoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.help_runner = HelpRunner(ROOT)
        cls.source_patterns = collect_source_format_patterns(ROOT)
        cls.writer_edids, cls.writer_fids, cls.quest_stages = collect_writer_symbols(ROOT)

    def test_task0_task1_lead_cards_pass_r11(self) -> None:
        self.assertGreater(len(self.source_patterns), 50)
        for rel in CARD_PATHS:
            card_path = ROOT / rel
            self.assertTrue(card_path.is_file(), f"missing lead card: {rel}")
            txt = card_path.read_text(encoding="utf-8")
            # Public hygiene check (R4): zero local drive paths
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

    def test_r11_validator_rejects_bad_flags_wrong_edids_and_stale_pass_lines(self) -> None:
        bad_card = """
## Card X — Negative Control
Disk need: 10 MB on <stage-dir>.

```bash
python scripts/ui/make_pipboy_stage_ini.py --stage <stage-dir> --bogus-flag 1
python scripts/game/exp_install.py install --exp-dir <stage-dir> --starfield <game-dir> --plugins FO4SFCoreValues.esm --pack
python scripts/game/exp_install.py uninstall --starfield <game-dir>
```

```console
coc FO4SFListDialogueCell
setstage FO4SF_ListDialogueQuest 999
```

```log
FO4SFLIST rt=<rt> Init speaker_present=true arrival_present=true end=true
step=code_obj_late_call n=1 name=Menu_mc.InvalidateData found=1 called=1
step=menu_guard registered=<menus> count=37
step=stat_stub fn=ShowPerksMenu
```
"""
        errors = validate_lead_card_markdown(
            "docs/testing/task0-task1-lead-cards.md",
            bad_card,
            help_runner=self.help_runner,
            source_patterns=self.source_patterns,
            writer_edids=self.writer_edids,
            writer_fids=self.writer_fids,
            quest_stages=self.quest_stages,
        )
        joined = "\n".join(errors)
        self.assertIn("--bogus-flag", joined)
        self.assertIn("coc FO4SFListDialogueCell", joined)
        self.assertIn("setstage FO4SF_ListDialogueQuest 999", joined)
        self.assertIn("Init speaker_present=true", joined)
        self.assertIn("code_obj_late_call", joined)
        self.assertIn("count=37", joined)
        self.assertIn("fn=ShowPerksMenu", joined)


if __name__ == "__main__":
    unittest.main()
