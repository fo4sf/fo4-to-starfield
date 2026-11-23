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

import json
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Dict, List, Optional, Pattern, Sequence, Set, Tuple

ROOT = Path(__file__).resolve().parents[1]
for _p in (
    str(ROOT / "src"),
    str(ROOT / "scripts" / "core"),
    str(ROOT / "scripts" / "game"),
    str(ROOT / "scripts" / "newgame"),
    str(ROOT / "scripts" / "planet"),
):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import make_core_bundle as mcb  # noqa: E402
from fo4sf.beginning_pilot import SESSION2_SHEET_PASS_SPECS  # noqa: E402
from fo4sf.core.cross_plugin_check import build_writer_catalog  # noqa: E402
from fo4sf.testing.lead_session_specs import expected_sheet_pass_lines  # noqa: E402
import tests.test_core_bundle as _tcb  # noqa: E402

# R11 / G1 / P2 / X3: read ONLY the lead-card & run-order files
CARD_PATHS: Tuple[str, ...] = (
    "docs/testing/candidate-2-cards.md",
    "docs/testing/candidate-2c-card.md",
    "docs/testing/candidate-2d-card.md",
    "docs/testing/candidate-2e-card.md",
    "docs/testing/candidate-2f-card.md",
    "docs/testing/playable-path-a3-a7-card.md",
    "docs/testing/fo4-beginning-pilot.md",
    "docs/testing/sanctuary-workbench-card.md",
    "docs/testing/lead-run-order.md",
)

# Verified CLI --help flags for cross-branch Session 3 (#832) and Session 4 (#832 / #834) tools referenced in lead-run-order.md
CROSS_BRANCH_TOOL_FLAGS: Dict[Tuple[str, str], Set[str]] = {
    ("scripts/planet/make_home_planet.py", "stage"): {
        "--data", "--out", "--worlds", "--star-name", "--planet-name", "--body-name", "--temp",
        "--climate", "--sky", "--atmosphere", "--ground-ltex", "--ground-source-dir", "--pattern",
        "--surface-tree", "--wb3-mode", "--sun-preset", "--orbital-meshes", "--control-b7dc7f52",
        "--lever-keywords", "--world-plugin-dir", "--map-markers",
    },
    ("scripts/planet/make_home_planet.py", "stage-wb1"): {
        "--data", "--out", "--worlds", "--world-plugin-dir", "--ground-source-dir", "--map-markers",
    },
    ("scripts/planet/make_home_planet.py", "stage-wb2"): {
        "--data", "--out", "--worlds", "--world-plugin-dir", "--ground-source-dir", "--map-markers",
    },
    ("scripts/planet/make_home_planet.py", "stage-wl1"): {
        "--data", "--out", "--worlds", "--body-name", "--world-plugin-dir", "--ground-source-dir", "--map-markers",
    },
    ("scripts/planet/make_home_planet.py", "check"): {
        "--stage", "--data", "--world-plugin-dir",
    },
    ("scripts/planet/home_world_install.py", "install"): {"--dir", "--starfield"},
    ("scripts/planet/home_world_install.py", "order"): {"--starfield"},
    ("scripts/planet/home_world_install.py", "undo"): {"--starfield"},
    ("scripts/planet/home_world_install.py", "uninstall"): {"--starfield"},
    ("scripts/planet/home_world_install.py", "status"): {"--starfield"},
    ("scripts/deploy_starfield.py", "install"): {
        "--batch", "--starfield", "--min-free-gb", "--dry-run", "--other-core", "--plugin-name",
    },
    ("scripts/deploy_starfield.py", "uninstall"): {"--starfield", "--plugin-name"},
    ("scripts/deploy_starfield.py", "verify"): {"--starfield", "--plugin-name"},
    ("scripts/terrain/make_cw_dlc_override.py", "status"): {"--starfield"},
    ("scripts/terrain/make_cw_dlc_override.py", "install"): {"--dir", "--dlc-doors", "--starfield"},
    ("scripts/terrain/make_cw_dlc_override.py", "uninstall"): {"--starfield"},
    ("src/fo4sf/terrain/overlay_postpatch.py", "verify"): {
        "--stage-dir", "--fo4", "--fo4-masters", "--fo4-world",
    },
}

CROSS_BRANCH_COC_TARGETS = frozenset({
    "FO4Core_RedRocketSpawn",
    "FO4FH_FarHarborSpawn",
    "FO4NW_NukaWorldSpawn",
    "FO4WG1_RedRocketSpawn",
    "FO4DLC_DLC03Acadia",
    "FO4DLC_DLC04BradbertonsOffice01",
    "FO4DLC_DLC06VaultWorkshop",
    "FO4Port_ConcordMuseum01",
    "FO4Port_RedRocket01",
    "FO4Port_Vault114",
    "FO4Port_DmndStandsKellogg01",
    "FO4Port_FortHagen01",
})

CROSS_BRANCH_PASS_PREFIXES: Tuple[str, ...] = (
    "staged ",
    "check: ok",
    "installed 3 files, plugins ",
    "uninstalled",
    "nothing installed",
    "install batch ",
    "Plugins.txt (",
    "installed. Undo with: python deploy_starfield.py uninstall --starfield <game dir> --plugin-name FO4DLC.esm",
    "removing [",
    "installed port as recorded: FO4Port.esm ",
    "CHECK PASS",
    "wb5 check: ok",
    "installed wb5 session:",
    "uninstalled wb5 session:",
    '"reachability": "TEST-STATION (coc only)"',
    '"water_exterior_cells_verified":',
)

CONSOLE_VERBS = frozenset({
    "coc",
    "prid",
    "player.moveto",
    "moveto",
    "setstage",
    "setgs",
    "set",
    "getglobalvalue",
    "help",
    "player.additem",
    "additem",
    "setpqv",
    "sqv",
    "sqs",
    "getstage",
    "bat",
    "startquest",
    "stopquest",
    "cgf",
})

FENCED_BLOCK_RE = re.compile(r"```([A-Za-z0-9_-]*)\r?\n(.*?)```", re.S)


def _join_cpp_adjacent_strings(cpp_text: str) -> str:
    return re.sub(r'"\s*\r?\n\s*"', "", cpp_text)


def _strip_psc_comment(raw_line: str) -> str:
    """Strip a Papyrus `;` comment only when outside double-quoted string literals."""
    in_str = False
    i = 0
    while i < len(raw_line):
        ch = raw_line[i]
        if ch == "\\" and in_str and i + 1 < len(raw_line):
            i += 2
            continue
        if ch == '"':
            in_str = not in_str
        elif ch == ";" and not in_str:
            return raw_line[:i].strip()
        i += 1
    return raw_line.strip()


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
            code = _strip_psc_comment(raw_line)
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
    for py_script in sorted((repo_root / "scripts" / "ui").glob("*.py")):
        txt = py_script.read_text(encoding="utf-8", errors="replace")
        for mm in re.finditer(r'"(FO4SF_[A-Za-z0-9_]+)"', txt):
            edids.add(mm.group(1))
    a7_script = repo_root / "scripts" / "terrain" / "a7_valentine_places.py"
    if a7_script.is_file():
        txt = a7_script.read_text(encoding="utf-8", errors="replace")
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
    bundle_fixtures: Optional[Dict[str, Path]] = None,
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
            lines = [
                ln.strip()
                for ln in block_body.splitlines()
                if ln.strip()
                and not ln.strip().startswith("#")
                and not (lang_low == "bat" and ln.strip().startswith(";"))
            ]
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

                if bundle_fixtures is not None:
                    m_ver = re.search(r"make_core_bundle\.py\s+verify\s+--bundle-dir\s+(<cand2[bcdef]-[^>\s]+>)", cline)
                    if m_ver:
                        b_ph = m_ver.group(1)
                        if b_ph not in bundle_fixtures:
                            errors.append(f"{card_rel} [{card_title}]: bundle {b_ph} has no registered verify fixture")
                        else:
                            port_p = bundle_fixtures.get("__port__")
                            v_probs, _ = mcb.verify_bundle(
                                str(bundle_fixtures[b_ph]),
                                port_esm=str(port_p) if port_p else None,
                            )
                            if v_probs:
                                errors.append(
                                    f"{card_rel} [{card_title}]: bundle {b_ph} refused by make_core_bundle.py verify "
                                    f"({len(v_probs)} problem(s); first: {v_probs[0]})"
                                )

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
                if lang_low in ("console", "bat") or first_word in CONSOLE_VERBS:
                    if lang_low == "console" and re.search(r"[mnv]", cline, re.I):
                        errors.append(
                            f"{card_rel} [{card_title}]: P3 forbids M/N/V letters in interactive console line: {cline!r}"
                        )
                    if re.match(r"^(?:set|help)\s+FO4SF_", cline, re.I):
                        errors.append(
                            f"{card_rel} [{card_title}]: P3 forbids stripped mod GLOB/QUST EditorID in console/bat: {cline!r}"
                        )
                    parts = cline.split()
                    verb = parts[0].lower()
                    if verb == "coc" and len(parts) >= 2:
                        cell_edid = parts[1]
                        if cell_edid not in writer_edids and cell_edid not in CROSS_BRANCH_COC_TARGETS:
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
                        elif re.fullmatch(r"[0-9A-Fa-f]{8}", q_edid):
                            local_q = int(q_edid, 16) & 0xFFFFFF
                            if local_q not in writer_fids:
                                errors.append(
                                    f"{card_rel} [{card_title}]: console 'setstage {q_edid}' local FormID 0x{local_q:06X} not in writer constants"
                                )
                            if stg_raw.isdigit() and not any(int(stg_raw, 10) in stgs for stgs in quest_stages.values()):
                                errors.append(
                                    f"{card_rel} [{card_title}]: console 'setstage {q_edid} {stg_raw}' stage not in any writer Stages"
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
                    elif verb == "set" and len(parts) >= 2:
                        if len(parts) < 4 or parts[2].lower() != "to":
                            errors.append(
                                f"{card_rel} [{card_title}]: console 'set' requires 'set <hex-formid> to <val>': {cline!r}"
                            )
                        elif re.fullmatch(r"[0-9A-Fa-f]{8}", parts[1]):
                            local_fid = int(parts[1], 16) & 0xFFFFFF
                            if local_fid not in writer_fids:
                                errors.append(
                                    f"{card_rel} [{card_title}]: console 'set {parts[1]}' local FormID 0x{local_fid:06X} not in writer constants"
                                )
                    elif verb in ("getglobalvalue", "sqv", "sqs", "startquest", "stopquest") and len(parts) >= 2:
                        arg1 = parts[1]
                        if re.fullmatch(r"[0-9A-Fa-f]{8}", arg1):
                            local_fid = int(arg1, 16) & 0xFFFFFF
                            if local_fid not in writer_fids:
                                errors.append(
                                    f"{card_rel} [{card_title}]: console '{verb} {arg1}' local FormID 0x{local_fid:06X} not in writer constants"
                                )
                    elif verb == "help" and len(parts) >= 2:
                        rest_help = cline.split(None, 1)[1].lstrip()
                        if not rest_help.startswith('"'):
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


def build_run_sheet_bundle_fixtures(tmp_root: Path) -> Dict[str, Path]:
    """Build synthetic Candidate 2b player/test bundles + broken pre-A1 Candidate 2 fixture for H1/R11 verify."""
    helper = _tcb.CoreBundleTests()
    owner, stages_root, port_esm, _ = helper._build_synthetic_owner_and_stages(tmp_root)

    pb = stages_root / "pipboy-stage"
    (pb / "Data" / "Interface").mkdir(parents=True, exist_ok=True)
    (pb / "Data" / "Scripts").mkdir(parents=True, exist_ok=True)
    (pb / "SFSE" / "Plugins").mkdir(parents=True, exist_ok=True)
    p1_sha = _tcb._make_tes4_esm(pb / "FO4SFPipboyProbe.esm", extra_tag=b"pbprobe")
    p2_sha = _tcb._make_tes4_esm(pb / "FO4SFPipboyTravel.esm", extra_tag=b"pbtravel")
    shell_bytes = b"FWS_SYNTHETIC_PIPBOY_SHELL"
    boot_bytes = b"FWS_SYNTHETIC_BOOT_SEQUENCE"
    pex_bytes = b"PEX_TRAVEL"
    dll_bytes = b"MZ_SYNTHETIC_PIPBOY_DLL"
    (pb / "Data" / "Interface" / "FO4SF_Fo4Shell.swf").write_bytes(shell_bytes)
    (pb / "Data" / "Interface" / "pipboybootsequence.swf").write_bytes(boot_bytes)
    (pb / "Data" / "Scripts" / "FO4SF_PipboyTravel.pex").write_bytes(pex_bytes)
    (pb / "SFSE" / "Plugins" / "FO4SFPipboyMenu.dll").write_bytes(dll_bytes)
    (pb / "SFSE" / "Plugins" / "FO4SFPipboyMenu.ini").write_text(
        "[FO4SFPipboyMenu]\n"
        "Stage=2\n"
        "Movie=FO4SF_Fo4Shell\n"
        "BootMovie=pipboybootsequence\n"
        "Arm=1\n",
        encoding="utf-8",
    )
    pb_plan = {
        "kind": "pipboy-stack-stage",
        "plugins": ["FO4SFPipboyProbe.esm", "FO4SFPipboyTravel.esm"],
        "files": {
            "FO4SFPipboyProbe.esm": {"sha256": p1_sha},
            "FO4SFPipboyTravel.esm": {"sha256": p2_sha},
            "Data/Interface/FO4SF_Fo4Shell.swf": {"sha256": _tcb._sha256_bytes(shell_bytes)},
            "Data/Interface/pipboybootsequence.swf": {"sha256": _tcb._sha256_bytes(boot_bytes)},
            "Data/Scripts/FO4SF_PipboyTravel.pex": {"sha256": _tcb._sha256_bytes(pex_bytes)},
        },
    }
    (pb / "plan.json").write_text(json.dumps(pb_plan, indent=1), encoding="utf-8")

    cand2b_player = tmp_root / "cand2b-player-bundle"
    rc_p = mcb.main(
        [
            "fold",
            "--owner-set", str(owner),
            "--stages-root", str(stages_root),
            "--clean-core-out", str(tmp_root / "clean-player"),
            "--out", str(cand2b_player),
            "--port", str(port_esm),
            "--profile", "player",
            "--with-experimental-core",
            "--with-route-loot",
            "--with-pipboy",
            "--pipboy-stage", str(pb),
        ],
        system=_tcb._FakeSystemClosed(),
    )
    if rc_p != 0:
        raise RuntimeError(f"failed folding synthetic cand2b-player-bundle (rc={rc_p})")

    cand2b_test = tmp_root / "cand2b-test-bundle"
    rc_t = mcb.main(
        [
            "fold",
            "--owner-set", str(owner),
            "--stages-root", str(stages_root),
            "--clean-core-out", str(tmp_root / "clean-test"),
            "--out", str(cand2b_test),
            "--port", str(port_esm),
            "--profile", "test",
            "--with-route-loot",
            "--with-pipboy",
            "--pipboy-stage", str(pb),
        ],
        system=_tcb._FakeSystemClosed(),
    )
    if rc_t != 0:
        raise RuntimeError(f"failed folding synthetic cand2b-test-bundle (rc={rc_t})")

    cand2d_player = tmp_root / "cand2d-player-bundle"
    rc_2d_p = mcb.main(
        [
            "fold",
            "--owner-set", str(owner),
            "--stages-root", str(stages_root),
            "--clean-core-out", str(tmp_root / "clean-player-2d"),
            "--out", str(cand2d_player),
            "--port", str(port_esm),
            "--profile", "player",
            "--with-pipboy",
            "--pipboy-stage", str(pb),
        ],
        system=_tcb._FakeSystemClosed(),
    )
    if rc_2d_p != 0:
        raise RuntimeError(f"failed folding synthetic cand2d-player-bundle (rc={rc_2d_p})")

    cand2d_test = tmp_root / "cand2d-test-bundle"
    rc_2d_t = mcb.main(
        [
            "fold",
            "--owner-set", str(owner),
            "--stages-root", str(stages_root),
            "--clean-core-out", str(tmp_root / "clean-test-2d"),
            "--out", str(cand2d_test),
            "--port", str(port_esm),
            "--profile", "test",
            "--with-pipboy",
            "--pipboy-stage", str(pb),
        ],
        system=_tcb._FakeSystemClosed(),
    )
    if rc_2d_t != 0:
        raise RuntimeError(f"failed folding synthetic cand2d-test-bundle (rc={rc_2d_t})")

    # Broken Round-1 Candidate 2 player fixture: lacks Data/Interface/pipboybootsequence.swf (A1 / H1)
    cand2_broken = tmp_root / "cand2-player-bundle"
    shutil.copytree(cand2b_player, cand2_broken)
    (cand2_broken / "Data" / "Interface" / "pipboybootsequence.swf").unlink()
    bplan_broken = json.loads((cand2_broken / "bundle_plan.json").read_text(encoding="utf-8"))
    bplan_broken["components"]["pipboy"]["outputs"].pop("Data/Interface/pipboybootsequence.swf", None)
    (cand2_broken / "bundle_plan.json").write_text(json.dumps(bplan_broken, indent=1), encoding="utf-8")

    return {
        "<cand2b-player-bundle>": cand2b_player,
        "<cand2b-test-bundle>": cand2b_test,
        "<cand2c-player-bundle>": cand2b_player,
        "<cand2c-test-bundle>": cand2b_test,
        "<cand2d-player-bundle>": cand2d_player,
        "<cand2d-test-bundle>": cand2d_test,
        "<cand2e-player-bundle>": cand2d_player,
        "<cand2e-test-bundle>": cand2d_test,
        "<cand2f-player-bundle>": cand2d_player,
        "<cand2f-test-bundle>": cand2d_test,
        "<cand2d-t1-bases-only>": cand2b_player,
        "<cand2d-t1-ext-overrides-only>": cand2b_player,
        "<cand2-player-bundle>": cand2_broken,
        "__port__": port_esm,
    }


def validate_lead_run_order_markdown(
    card_rel: str,
    md_text: str,
    *,
    help_runner: HelpRunner,
    source_patterns: Sequence[Tuple[str, str, Pattern[str]]],
    writer_edids: Set[str],
    writer_fids: Set[int],
    quest_stages: Dict[str, Set[int]],
    bundle_fixtures: Optional[Dict[str, Path]] = None,
) -> List[str]:
    """Validate `docs/testing/lead-run-order.md` (`G1` / `H1` / `H5` / `R11`) across Sessions 1–4 in exact order."""
    errors: List[str] = []
    top_header = "\n".join(md_text.splitlines()[:15])
    if "NEW GAME needed" not in top_header:
        errors.append(f"{card_rel}: missing 'NEW GAME needed' banner near top of run sheet")

    for sym in sorted(set(re.findall(r"\bFO4SF_[A-Za-z0-9_]+\b", md_text))):
        if sym not in writer_edids and sym not in ("FO4SF_NEWGAME", "FO4SF_MISSION"):
            errors.append(f"{card_rel}: unknown FO4SF_* identifier {sym!r}")

    parts = re.split(r"(?m)^##\s+(Session\s+(\d+)\s+—\s+[^\r\n]+)$", md_text)
    # parts = [preamble, full_h1, num1, body1, full_h2, num2, body2, ...]
    sessions: List[Tuple[int, str, str]] = []
    for idx in range(1, len(parts), 3):
        sessions.append((int(parts[idx + 1]), parts[idx].strip(), parts[idx + 2]))

    if [s[0] for s in sessions] != [1, 2, 3, 4]:
        errors.append(f"{card_rel}: expected Sessions [1, 2, 3, 4] in exact order, got {[s[0] for s in sessions]}")
        return errors

    # H5: Preflight must plainly warn that it removes the owner's installed build, and validate preamble CLI flags
    preamble = parts[0]
    if "removes the owner's" not in preamble.lower():
        errors.append(f"{card_rel} [Preflight]: H5 missing plain-words warning that preflight removes the owner's installed build")
    for req_pre in ("pipboy_probe_install.py uninstall", "exp_install.py uninstall", "experiment-receipts", "rollback"):
        if req_pre not in preamble:
            errors.append(f"{card_rel} [Preflight]: H5 missing {req_pre!r} in preflight / owner-restore section")
    for _plang, pblock in FENCED_BLOCK_RE.findall(preamble):
        for pline in [ln.strip() for ln in pblock.splitlines() if ln.strip() and not ln.strip().startswith("#")]:
            if pline.startswith("python "):
                sanitized = re.sub(r"<[^>\s]+>", "PLACEHOLDER", pline)
                tokens = shlex.split(sanitized, posix=True)
                used_flags = [t.split("=", 1)[0] for t in tokens if t.startswith("--") and t != "--"]
                allowed_flags, err = help_runner.get_help_flags(tokens)
                if err:
                    errors.append(f"{card_rel} [Preflight]: {err}")
                else:
                    for fl in used_flags:
                        if fl not in allowed_flags:
                            errors.append(f"{card_rel} [Preflight]: flag {fl!r} not in --help for command: {pline}")

    # G1 + H1 exact session order content invariants
    s1_body, s2_body, s3_body, s4_body = (s[2] for s in sessions)
    for req in ("Candidate 2b", "<cand2b-player-bundle>", "Card B", "Card C", "gemini/beginning-real", "gemini/core-integration"):
        if req not in sessions[0][1] and req not in s1_body:
            errors.append(f"{card_rel} [Session 1]: missing {req!r}")
    if "<cand2-player-bundle>" in s1_body or "<cand2-test-bundle>" in s1_body:
        errors.append(f"{card_rel} [Session 1]: H1 forbids naming unverified Round-1 <cand2-*-bundle>")
    for req in ("Candidate 2b", "Card A", "Card 2", "Card 1", "Card 5", "Card 3", "Card 4", "gemini/beginning-real"):
        if req not in sessions[1][1] and req not in s2_body:
            errors.append(f"{card_rel} [Session 2]: missing {req!r}")
    if s2_body.find("Card A") > s2_body.find("Card 2"):
        errors.append(f"{card_rel} [Session 2]: Card A must precede Card 2")
    for req in ("FO4SFHome.esm", "FO4TerrainCore_Home.esm", "WB1", "WB2", "gemini/world-own-space"):
        if req not in sessions[2][1] and req not in s3_body:
            errors.append(f"{card_rel} [Session 3]: missing {req!r}")
    for req in ("FO4DLC.esm", "FO4WorldFarHarbor.esm", "FO4WorldNukaWorld.esm", "FO4TerrainCore_DLC.esm", "gemini/dlc-and-interiors", "gemini/world-own-space"):
        if req not in sessions[3][1] and req not in s4_body:
            errors.append(f"{card_rel} [Session 4]: missing {req!r}")

    # H3: Run sheet must never instruct manual sfse_sidecar copies and must state reputation/ is not installed
    if re.search(r"\bcopy\b[^\r\n]*sfse_sidecar", md_text, re.I):
        errors.append(f"{card_rel}: H3 forbids manual sfse_sidecar copy; use make_core_bundle.py sidecar-install / sidecar-undo")
    if "reputation" not in md_text or "not installed" not in md_text.lower():
        errors.append(f"{card_rel}: H3 missing explicit statement that sfse_sidecar/reputation/ is not installed")

    for snum, stitle, raw_body in sessions:
        body = re.split(r"(?m)^##\s+(?!Session\b)", raw_body, maxsplit=1)[0]
        if not re.search(r"gemini/[a-z0-9-]+", body) or not re.search(r"\b[0-9a-f]{8}\b", body):
            errors.append(f"{card_rel} [{stitle}]: missing branch name + 8-char commit head")
        if "FO4SFBridge.esm` State" not in body or "owner-standing-bridge-off" not in body:
            errors.append(f"{card_rel} [{stitle}]: H4 missing explicit per-session FO4SFBridge.esm state + owner-standing-bridge-off restore")
        if snum in (1, 2):
            if "make_core_bundle.py sidecar-install" not in body or "make_core_bundle.py sidecar-undo" not in body:
                errors.append(f"{card_rel} [{stitle}]: H3 missing make_core_bundle.py sidecar-install / sidecar-undo commands")
        if "New-Game Note" not in body:
            errors.append(f"{card_rel} [{stitle}]: missing New-Game Note")
        if "Disk Need" not in body or not re.search(r"\b\d+(?:\.\d+)?\s*(?:B|KB|MB|GB|GiB|MiB)\b", body):
            errors.append(f"{card_rel} [{stitle}]: missing Disk Need statement")
        if "Plugins.txt" not in body or not re.search(r"FO4[A-Za-z0-9_]+\.esm", body):
            errors.append(f"{card_rel} [{stitle}]: missing Plugins.txt plugin list")
        if "Cards to Run in Order" not in body:
            errors.append(f"{card_rel} [{stitle}]: missing 'Cards to Run in Order'")
        if "Stop Point" not in body:
            errors.append(f"{card_rel} [{stitle}]: missing 'Stop Point' if a card fails")
        if not re.search(r"<[A-Za-z0-9_-]+>", body):
            errors.append(f"{card_rel} [{stitle}]: missing <placeholder> stage/game path")

        blocks = FENCED_BLOCK_RE.findall(body)
        has_install = False
        has_undo = False
        has_pass = False
        verified_placeholders: Dict[str, List[str]] = {}

        for lang, block_body in blocks:
            lang_low = lang.strip().lower()
            lines = [
                ln.strip()
                for ln in block_body.splitlines()
                if ln.strip()
                and not ln.strip().startswith("#")
                and not (lang_low == "bat" and ln.strip().startswith(";"))
            ]
            if lang_low == "log":
                has_pass = True
                if snum == 2:
                    want_s2 = [spec_line for _card, spec_line in SESSION2_SHEET_PASS_SPECS]
                    if lines != want_s2:
                        errors.append(
                            f"{card_rel} [{stitle}]: Session 2 PASS block diverges from SESSION2_SHEET_PASS_SPECS table"
                        )
                elif snum in (1, 3, 4):
                    want_sn = expected_sheet_pass_lines(snum)
                    if lines != want_sn:
                        errors.append(
                            f"{card_rel} [{stitle}]: Session {snum} PASS block diverges from SESSION_PASS_SPECS table"
                        )
                for pline in lines:
                    sample = _sample_from_card_line(pline)
                    fixed_toks = _extract_fixed_tokens(pline)
                    matched = any(
                        pat.search(sample) and all(_token_matches_template(ft, src_tpl) for ft in fixed_toks)
                        for _src_rel, src_tpl, pat in source_patterns
                    )
                    if not matched:
                        errors.append(f"{card_rel} [{stitle}]: PASS log line does not match source: {pline!r}")
                continue
            if lang_low == "text":
                has_pass = True
                if snum in (1, 3, 4):
                    want_sn = expected_sheet_pass_lines(snum)
                    if lines != want_sn:
                        errors.append(
                            f"{card_rel} [{stitle}]: Session {snum} PASS block diverges from SESSION_PASS_SPECS table"
                        )
                for pline in lines:
                    if not any(pline.startswith(pref) for pref in CROSS_BRANCH_PASS_PREFIXES):
                        errors.append(f"{card_rel} [{stitle}]: unrecognized CLI PASS output line: {pline!r}")
                continue

            for cline in lines:
                if " install " in f" {cline} " or " sidecar-install " in f" {cline} ":
                    has_install = True
                if " uninstall " in f" {cline} " or " undo " in f" {cline} " or " sidecar-undo " in f" {cline} ":
                    has_undo = True

                # H1: Run real make_core_bundle.py verify on the fixture mapped to any named bundle placeholder
                if bundle_fixtures is not None:
                    m_ver = re.search(r"make_core_bundle\.py\s+verify\s+--bundle-dir\s+(<[^>\s]+>)", cline)
                    if m_ver:
                        b_ph = m_ver.group(1)
                        if b_ph not in bundle_fixtures:
                            errors.append(f"{card_rel} [{stitle}]: bundle {b_ph} has no registered verify fixture")
                        else:
                            port_p = bundle_fixtures.get("__port__")
                            v_probs, v_metrics = mcb.verify_bundle(
                                str(bundle_fixtures[b_ph]),
                                port_esm=str(port_p) if port_p else None,
                            )
                            if v_probs:
                                errors.append(
                                    f"{card_rel} [{stitle}]: bundle {b_ph} refused by make_core_bundle.py verify "
                                    f"({len(v_probs)} problem(s); first: {v_probs[0]})"
                                )
                            else:
                                verified_placeholders[b_ph] = list(v_metrics.get("plugins") or [])

                    m_inst = re.search(
                        r"exp_install\.py\s+install\s+--exp-dir\s+(<cand[^>\s]+>).*?--plugins\s+([^\s]+)",
                        cline,
                    )
                    if m_inst:
                        i_ph, i_csv = m_inst.group(1), m_inst.group(2)
                        if i_ph not in verified_placeholders:
                            errors.append(
                                f"{card_rel} [{stitle}]: exp_install.py installs bundle {i_ph} without a passing make_core_bundle.py verify before it"
                            )
                        elif i_csv.split(",") != verified_placeholders[i_ph]:
                            errors.append(
                                f"{card_rel} [{stitle}]: exp_install.py --plugins for {i_ph} != verified bundle plugin list"
                            )

                if cline.startswith("python "):
                    sanitized = re.sub(r"<[^>\s]+>", "PLACEHOLDER", cline)
                    tokens = shlex.split(sanitized, posix=True)
                    script_rel = tokens[1] if len(tokens) >= 2 else ""
                    subcmd = tokens[2] if len(tokens) >= 3 and not tokens[2].startswith("-") else ""
                    used_flags = [t.split("=", 1)[0] for t in tokens if t.startswith("--") and t != "--"]
                    if snum in (3, 4) and (script_rel, subcmd) in CROSS_BRANCH_TOOL_FLAGS:
                        allowed_flags = CROSS_BRANCH_TOOL_FLAGS[(script_rel, subcmd)]
                        err = ""
                    else:
                        allowed_flags, err = help_runner.get_help_flags(tokens)
                    if err:
                        errors.append(f"{card_rel} [{stitle}]: {err}")
                        continue
                    for fl in used_flags:
                        if fl not in allowed_flags:
                            errors.append(f"{card_rel} [{stitle}]: flag {fl!r} not in --help for command: {cline}")
                    continue

                first_word = cline.split()[0].lower()
                if lang_low in ("console", "bat") or first_word in CONSOLE_VERBS:
                    if lang_low == "console" and re.search(r"[mnv]", cline, re.I):
                        errors.append(
                            f"{card_rel} [{stitle}]: P3 forbids M/N/V letters in interactive console line: {cline!r}"
                        )
                    if re.match(r"^(?:set|help)\s+FO4SF_", cline, re.I):
                        errors.append(
                            f"{card_rel} [{stitle}]: P3 forbids stripped mod GLOB/QUST EditorID in console/bat: {cline!r}"
                        )
                    cparts = cline.split()
                    verb = cparts[0].lower()
                    if verb == "coc" and len(cparts) >= 2:
                        cell_edid = cparts[1]
                        if cell_edid not in writer_edids and cell_edid not in CROSS_BRANCH_COC_TARGETS:
                            errors.append(f"{card_rel} [{stitle}]: unknown coc target {cell_edid!r}")
                    elif verb == "setstage" and len(cparts) >= 3:
                        q_edid, stg_raw = cparts[1], cparts[2]
                        if re.fullmatch(r"<[A-Za-z0-9_-]+>", q_edid):
                            if stg_raw.isdigit() and not any(int(stg_raw, 10) in stgs for stgs in quest_stages.values()):
                                errors.append(f"{card_rel} [{stitle}]: unknown stage {q_edid} {stg_raw}")
                        elif re.fullmatch(r"[0-9A-Fa-f]{8}", q_edid):
                            local_q = int(q_edid, 16) & 0xFFFFFF
                            if local_q not in writer_fids:
                                errors.append(f"{card_rel} [{stitle}]: unknown quest FormID {q_edid!r}")
                            if stg_raw.isdigit() and not any(int(stg_raw, 10) in stgs for stgs in quest_stages.values()):
                                errors.append(f"{card_rel} [{stitle}]: unknown stage {q_edid} {stg_raw}")
                        elif q_edid not in writer_edids:
                            errors.append(f"{card_rel} [{stitle}]: unknown quest {q_edid!r}")
                        elif q_edid.lower() in quest_stages and stg_raw.isdigit() and int(stg_raw, 10) not in quest_stages[q_edid.lower()]:
                            errors.append(f"{card_rel} [{stitle}]: unknown stage {q_edid} {stg_raw}")
                    elif verb in ("getglobalvalue", "sqv", "sqs", "startquest", "stopquest") and len(cparts) >= 2:
                        if re.fullmatch(r"[0-9A-Fa-f]{8}", cparts[1]):
                            local_fid = int(cparts[1], 16) & 0xFFFFFF
                            if local_fid not in writer_fids:
                                errors.append(f"{card_rel} [{stitle}]: unknown FormID {cparts[1]!r}")
                    elif verb == "help" and len(cparts) >= 2:
                        rest_help = cline.split(None, 1)[1].lstrip()
                        if not rest_help.startswith('"'):
                            t_edid = cparts[1].strip('"')
                            if t_edid not in writer_edids:
                                errors.append(f"{card_rel} [{stitle}]: unknown help target {t_edid!r}")

        if not has_install:
            errors.append(f"{card_rel} [{stitle}]: missing fenced install command")
        if not has_undo:
            errors.append(f"{card_rel} [{stitle}]: missing fenced undo/uninstall command")
        if not has_pass:
            errors.append(f"{card_rel} [{stitle}]: missing fenced PASS block")

    return errors


class LeadCardsBeginningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.help_runner = HelpRunner(ROOT)
        cls.source_patterns = collect_source_format_patterns(ROOT)
        cls.writer_edids, cls.writer_fids, cls.quest_stages = collect_writer_symbols(ROOT)
        cls._bundle_tmp = tempfile.TemporaryDirectory(prefix="fo4sf-r11-bundles-")
        cls.bundle_fixtures = build_run_sheet_bundle_fixtures(Path(cls._bundle_tmp.name))

    @classmethod
    def tearDownClass(cls) -> None:
        cls._bundle_tmp.cleanup()

    def test_beginning_lead_cards_pass_r11(self) -> None:
        self.assertEqual(
            CARD_PATHS,
            (
                "docs/testing/candidate-2-cards.md",
                "docs/testing/candidate-2c-card.md",
                "docs/testing/candidate-2d-card.md",
                "docs/testing/candidate-2e-card.md",
                "docs/testing/candidate-2f-card.md",
                "docs/testing/playable-path-a3-a7-card.md",
                "docs/testing/fo4-beginning-pilot.md",
                "docs/testing/sanctuary-workbench-card.md",
                "docs/testing/lead-run-order.md",
            ),
        )
        self.assertGreater(len(self.source_patterns), 80)
        for rel in CARD_PATHS:
            card_path = ROOT / rel
            self.assertTrue(card_path.is_file(), f"missing lead card: {rel}")
            txt = card_path.read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"\b[A-Za-z]:[\\/]", txt), f"local path leaked in {rel}")
            for stale_token in ("by=trigger", "source=lift\n", "source=lift ", "source=lift`", "source=lift)", "why=reload"):
                self.assertNotIn(stale_token, txt, f"H00(a) lowercase BSFixedString mismatch {stale_token!r} in {rel}")
            if rel.endswith("lead-run-order.md"):
                errors = validate_lead_run_order_markdown(
                    rel,
                    txt,
                    help_runner=self.help_runner,
                    source_patterns=self.source_patterns,
                    writer_edids=self.writer_edids,
                    writer_fids=self.writer_fids,
                    quest_stages=self.quest_stages,
                    bundle_fixtures=self.bundle_fixtures,
                )
            else:
                errors = validate_lead_card_markdown(
                    rel,
                    txt,
                    help_runner=self.help_runner,
                    source_patterns=self.source_patterns,
                    writer_edids=self.writer_edids,
                    writer_fids=self.writer_fids,
                    quest_stages=self.quest_stages,
                    bundle_fixtures=self.bundle_fixtures,
                )
            self.assertEqual(errors, [], "\n".join(errors))

    def test_p2_p3_candidate_2c_card_order_and_zero_mnv_console_guard(self) -> None:
        c2c = (ROOT / "docs/testing/candidate-2c-card.md").read_text(encoding="utf-8")
        headings = re.findall(r"(?m)^##\s+(Card\s+2c-\d+[^\r\n]*)$", c2c)
        self.assertEqual(len(headings), 5)
        self.assertTrue(headings[0].startswith("Card 2c-1"))
        self.assertTrue(headings[1].startswith("Card 2c-2"))
        self.assertTrue(headings[2].startswith("Card 2c-3"))
        self.assertTrue(headings[3].startswith("Card 2c-4"))
        self.assertTrue(headings[4].startswith("Card 2c-5"))
        for req in ("sidecar-install", "sidecar-undo", "start record", "07000890", "07000897", "Arm=1", "OWNER TEST"):
            self.assertIn(req, c2c)

        # Mutate a fenced console line to contain 'v' (`sqv 12000810`) and stripped `set FO4SF_H00_SkipMapSetup to 1`
        bad_c2c = c2c.replace("\nsqs <quest-hex>\n", "\nsqv 12000810\n", 1).replace(
            "\nbat h00a\n", "\nset FO4SF_H00_SkipMapSetup to 1\n", 1
        )
        errs = validate_lead_card_markdown(
            "docs/testing/candidate-2c-card.md",
            bad_c2c,
            help_runner=self.help_runner,
            source_patterns=self.source_patterns,
            writer_edids=self.writer_edids,
            writer_fids=self.writer_fids,
            quest_stages=self.quest_stages,
            bundle_fixtures=self.bundle_fixtures,
        )
        joined = "\n".join(errs)
        self.assertIn("P3 forbids M/N/V letters in interactive console line", joined)
        self.assertIn("P3 forbids stripped mod GLOB/QUST EditorID", joined)

    def test_x2_x3_candidate_2e_card_structure_and_zero_mnv_guard(self) -> None:
        c2e = (ROOT / "docs/testing/candidate-2e-card.md").read_text(encoding="utf-8")
        headings = re.findall(r"(?m)^##\s+(Card\s+2e-\d+[^\r\n]*)$", c2e)
        self.assertEqual(len(headings), 4)
        self.assertTrue(headings[0].startswith("Card 2e-1"))
        self.assertTrue(headings[1].startswith("Card 2e-2"))
        self.assertTrue(headings[2].startswith("Card 2e-3"))
        self.assertTrue(headings[3].startswith("Card 2e-4"))
        for req in (
            "<cand2e-player-bundle>",
            "<cand2e-test-bundle>",
            "story_landing",
            "story fade reassert tick=1",
            "console port activator registered",
            "catwalk hint shown",
            "codsworth talk proxy ready",
            "codsworth talk opened stage=10",
            "preston talk opened stage=30",
            "Throwaway_2e_Surface",
            "09000800",
            "09000811",
            "09000802",
            "09000970",
            "0A00080F",
            "0A000819",
            "06000865",
        ):
            self.assertIn(req, c2e)

        # Negative P3 control: injecting 'v' (`sqv 09000800`) and stripped `set FO4SF_PipboyAcquired to 1` must fail.
        bad_c2e = c2e.replace("\nsqs 09000800\n", "\nsqv 09000800\n", 1).replace(
            "\nbat r8stat\n", "\nset FO4SF_PipboyAcquired to 1\n", 1
        )
        errs = validate_lead_card_markdown(
            "docs/testing/candidate-2e-card.md",
            bad_c2e,
            help_runner=self.help_runner,
            source_patterns=self.source_patterns,
            writer_edids=self.writer_edids,
            writer_fids=self.writer_fids,
            quest_stages=self.quest_stages,
            bundle_fixtures=self.bundle_fixtures,
        )
        joined = "\n".join(errs)
        self.assertIn("P3 forbids M/N/V letters in interactive console line", joined)
        self.assertIn("P3 forbids stripped mod GLOB/QUST EditorID", joined)

    def test_r9_candidate_2f_card_structure_a1e_a6_a2_and_zero_mnv_guard(self) -> None:
        c2f = (ROOT / "docs/testing/candidate-2f-card.md").read_text(encoding="utf-8")
        headings = re.findall(r"(?m)^##\s+(Card\s+2f-\d+[^\r\n]*)$", c2f)
        self.assertEqual(len(headings), 4)
        self.assertTrue(headings[0].startswith("Card 2f-1"))
        self.assertTrue(headings[1].startswith("Card 2f-2"))
        self.assertTrue(headings[2].startswith("Card 2f-3"))
        self.assertTrue(headings[3].startswith("Card 2f-4"))
        for req in (
            "<cand2f-player-bundle>",
            "<cand2f-test-bundle>",
            "33",
            "Pool of 40",
            "09000940",
            "09000900",
            "09000979",
            "FO4SF_MissionTalkUseMessageBox",
            "v111_pipboy_pickup.nif",
            "v111_geardoor_console.nif",
            "codsworth dialogue menu opened",
            "preston dialogue menu opened",
            "codsworth talk fallback=messagebox",
            "preston talk fallback=messagebox",
            "100009EC",
            "040A775C",
            "bat r9hop1",
            "bat r9hop2",
            "bat r9hop3",
            "bat r9door",
            "Throwaway_2f_Surface",
            "Throwaway_2f_Sanctuary",
            "Throwaway_2f_Concord",
            "Throwaway_2f_MidWFC",
            "Throwaway_2f_PostWFC",
            "sanctuary01 reload stage=<st> complete=<c>",
            "B1",
            "B2",
            "B3",
            "B4",
            "FO4SF_MapMarkersHop",
            "100008F4",
            "086edc15",
        ):
            self.assertIn(req, c2f, f"candidate-2f-card.md missing {req!r}")

        # Negative P3 control: injecting 'v' (`sqv 09000800`) and stripped `set FO4SF_PipboyAcquired to 1` must fail.
        bad_c2f = c2f.replace("\nsqs 09000800\n", "\nsqv 09000800\n", 1).replace(
            "\nbat r9stat\n", "\nset FO4SF_PipboyAcquired to 1\n", 1
        )
        errs = validate_lead_card_markdown(
            "docs/testing/candidate-2f-card.md",
            bad_c2f,
            help_runner=self.help_runner,
            source_patterns=self.source_patterns,
            writer_edids=self.writer_edids,
            writer_fids=self.writer_fids,
            quest_stages=self.quest_stages,
            bundle_fixtures=self.bundle_fixtures,
        )
        joined = "\n".join(errs)
        self.assertIn("P3 forbids M/N/V letters in interactive console line", joined)
        self.assertIn("P3 forbids stripped mod GLOB/QUST EditorID", joined)

        # A2 console-free walk list must exist, stay path-leak free, and cover every historical console/batch point
        a2_path = ROOT / "docs/testing/console-free-walk-list.md"
        self.assertTrue(a2_path.is_file(), "missing docs/testing/console-free-walk-list.md")
        a2_txt = a2_path.read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"\b[A-Za-z]:[\\/]", a2_txt), "local path leaked in console-free-walk-list.md")
        for req in ("u1pick", "u1cog", "r8csw", "r8prs", "PlatformRadius", "ReleaseStoryLandingFade", "ran in game", "pushed, not run", "B1", "B2", "B3", "B4", "086edc15"):
            self.assertIn(req, a2_txt, f"console-free-walk-list.md missing {req!r}")
        ki_txt = (ROOT / "docs/known-issues.md").read_text(encoding="utf-8")
        for req in ("| `B1` |", "| `B2` |", "| `B3` |", "| `B4` |", "086edc15", "FO4SF_MapMarkersHop"):
            self.assertIn(req, ki_txt, f"known-issues.md missing {req!r}")

    def test_r9_playable_path_a3_a7_card_structure_and_zero_mnv_guard(self) -> None:
        a37 = (ROOT / "docs/testing/playable-path-a3-a7-card.md").read_text(encoding="utf-8")
        headings = re.findall(r"(?m)^##\s+(Card\s+A\d+[^\r\n]*)$", a37)
        self.assertEqual(len(headings), 4)
        self.assertTrue(headings[0].startswith("Card A3"))
        self.assertTrue(headings[1].startswith("Card A4"))
        self.assertTrue(headings[2].startswith("Card A5"))
        self.assertTrue(headings[3].startswith("Card A7"))
        for req in (
            "NEW GAME needed",
            "OFFLINE ONLY — UNPROVEN IN GAME",
            "02012540",
            "02011918",
            "02002338",
            "09000817",
            "09000A15",
            "09000A20",
            "09000A50",
            "09000A80",
            "09000AB0",
            "bat a3sf",
            "bat a3rr",
            "bat a4s1",
            "bat a4r1",
            "bat a4q1",
            "--a5-playable",
            "FO4SFPipboyQuestObjectives.tsv",
            "step=quest_catalog",
            "step=map_quest_markers",
            "step=arm_watchdog_open",
            "bat a7p1",
            "bat a7p2",
            "bat a7fh",
            "bat a7u1",
            "bat a7c1",
            "Throwaway_A7_Vault114",
            "Throwaway_A7_Kellogg",
            "mq104 complete stage=200 mq105_armed=1",
            "mq105 complete stage=200 mq106_armed=1",
        ):
            self.assertIn(req, a37, f"playable-path-a3-a7-card.md missing {req!r}")

        # Negative P3 control: injecting 'v' (`sqv 09000A20`) and stripped `set FO4SF_PipboyAcquired to 1` must fail.
        bad_a37 = a37.replace("\nsqs 09000A20\n", "\nsqv 09000A20\n", 1).replace(
            "\nbat a4s1\n", "\nset FO4SF_PipboyAcquired to 1\n", 1
        )
        errs = validate_lead_card_markdown(
            "docs/testing/playable-path-a3-a7-card.md",
            bad_a37,
            help_runner=self.help_runner,
            source_patterns=self.source_patterns,
            writer_edids=self.writer_edids,
            writer_fids=self.writer_fids,
            quest_stages=self.quest_stages,
            bundle_fixtures=self.bundle_fixtures,
        )
        joined = "\n".join(errs)
        self.assertIn("P3 forbids M/N/V letters in interactive console line", joined)
        self.assertIn("P3 forbids stripped mod GLOB/QUST EditorID", joined)

    def test_h1_h5_run_sheet_bundle_verify_fixture_and_preflight_guard(self) -> None:
        port_p = str(self.bundle_fixtures["__port__"])
        r_ok = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "core" / "make_core_bundle.py"),
                "verify",
                "--bundle-dir",
                str(self.bundle_fixtures["<cand2b-player-bundle>"]),
                "--port",
                port_p,
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        self.assertEqual(r_ok.returncode, 0, r_ok.stdout + r_ok.stderr)
        self.assertIn("verify: ok", r_ok.stdout)

        r_bad = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "core" / "make_core_bundle.py"),
                "verify",
                "--bundle-dir",
                str(self.bundle_fixtures["<cand2-player-bundle>"]),
                "--port",
                port_p,
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(r_bad.returncode, 0)
        self.assertIn("pipboybootsequence.swf", r_bad.stdout + r_bad.stderr)
        self.assertIn("do not install", r_bad.stdout + r_bad.stderr)

        good_txt = (ROOT / "docs/testing/lead-run-order.md").read_text(encoding="utf-8")
        stale_s1_txt = (
            good_txt.replace(
                "make_core_bundle.py verify --bundle-dir <cand2b-player-bundle>",
                "make_core_bundle.py verify --bundle-dir <cand2-player-bundle>",
                1,
            )
            .replace(
                "exp_install.py install --exp-dir <cand2b-player-bundle>",
                "exp_install.py install --exp-dir <cand2-player-bundle>",
                1,
            )
            .replace("removes the owner's", "updates the")
        )
        errs = validate_lead_run_order_markdown(
            "docs/testing/lead-run-order.md",
            stale_s1_txt,
            help_runner=self.help_runner,
            source_patterns=self.source_patterns,
            writer_edids=self.writer_edids,
            writer_fids=self.writer_fids,
            quest_stages=self.quest_stages,
            bundle_fixtures=self.bundle_fixtures,
        )
        joined = "\n".join(errs)
        self.assertIn("H5 missing plain-words warning", joined)
        self.assertIn("H1 forbids naming unverified Round-1", joined)
        self.assertIn("bundle <cand2-player-bundle> refused by make_core_bundle.py verify", joined)
        self.assertIn("pipboybootsequence.swf", joined)

        # H3 & H4 negative mutation checks
        h3_h4_bad = (
            good_txt.replace("make_core_bundle.py sidecar-install", "copy <cand2b-player-bundle>/sfse_sidecar", 1)
            .replace("owner-standing-bridge-off", "left-active")
        )
        errs_h34 = validate_lead_run_order_markdown(
            "docs/testing/lead-run-order.md",
            h3_h4_bad,
            help_runner=self.help_runner,
            source_patterns=self.source_patterns,
            writer_edids=self.writer_edids,
            writer_fids=self.writer_fids,
            quest_stages=self.quest_stages,
        )
        joined_h34 = "\n".join(errs_h34)
        self.assertIn("H3 forbids manual sfse_sidecar copy", joined_h34)
        self.assertIn("H4 missing explicit per-session FO4SFBridge.esm state", joined_h34)

    def test_lead_run_order_validator_rejects_missing_stop_point_and_bad_order(self) -> None:
        bad_sheet = """# Run Sheet
NEW GAME needed

## Session 1 — Candidate 2 Cards B and C (gemini/core-integration b03a534d)
- New-Game Note: NEW GAME needed
- Disk Need: 4.2 GB
- Plugins.txt: FO4SFCoreValues.esm
- Cards to Run in Order: Card B, Card C

```bash
python scripts/game/exp_install.py install --exp-dir <stage> --starfield <game> --plugins FO4SFCoreValues.esm --bogus-flag
python scripts/game/exp_install.py uninstall --starfield <game>
```

```log
step=nonexistent_log_line foo=1
```
"""
        errs = validate_lead_run_order_markdown(
            "docs/testing/lead-run-order.md",
            bad_sheet,
            help_runner=self.help_runner,
            source_patterns=self.source_patterns,
            writer_edids=self.writer_edids,
            writer_fids=self.writer_fids,
            quest_stages=self.quest_stages,
        )
        joined = "\n".join(errs)
        self.assertIn("expected Sessions [1, 2, 3, 4]", joined)

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
