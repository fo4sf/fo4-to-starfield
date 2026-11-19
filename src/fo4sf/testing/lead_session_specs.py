"""Single declarative PASS and stop-point table for Lead Sessions 1, 3, and 4 (`K1` / `R11`).

Both `docs/testing/lead-run-order.md`'s fenced PASS blocks for Sessions 1, 3, and 4
and the read-only `scripts/testing/check_lead_sessions.py` log judge derive their
exact lines and match patterns from this one module (checked by the R11 test in
`tests/test_lead_cards_beginning.py` and `tests/test_lead_session_judge.py`).

Read-only contract:
  - `evaluate_session_logs(log_dir, ...)` reads ONLY regular `.log`, `.txt`, and `.out`
    files located strictly inside `log_dir` (never following symlinks outside `log_dir`,
    never touching any game or Documents folder unless explicitly passed as `log_dir`).
  - It writes nothing to disk.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


SUPPORTED_SESSIONS: Tuple[int, ...] = (1, 3, 4)
SUPPORTED_LOG_EXTENSIONS: frozenset[str] = frozenset({".log", ".txt", ".out"})
MAP_SUPPRESS_FALLBACK_LINE = "step=map_suppress n=<k> name=<menu> sent=hide"
CARD_C_STARMAP_BLOCKED_LINE = "step=starmap_blocked n=<k> blocked menu=<menu> route=create"


@dataclass(frozen=True)
class SessionPassSpec:
    """One required PASS line belonging to a card in Session 1, 3, or 4."""

    session: int
    card: str
    line: str
    block_kind: str  # "log" (SFSE/Papyrus trace) or "text" (CLI output capture)
    source_hint: str


@dataclass(frozen=True)
class SessionStopSpec:
    """One named stop-point / FAIL condition from `docs/testing/lead-run-order.md`."""

    session: int
    card: str
    stop_id: str
    description: str
    pattern: str
    flags: int = 0


SESSION_TITLES: Dict[int, str] = {
    1: "Session 1 — Candidate 2b Cards B and C (F7 STAT Isolation & Scanner/Map Block)",
    3: "Session 3 — Home Planet Pair and Variants (FO4SFHome + WB1/WB2/WL1)",
    4: "Session 4 — DLC Worlds (FO4DLC, WB5/WB5b Two-Way Doors, Far Harbor & Nuka-World)",
}


# Single canonical PASS table for Sessions 1, 3, and 4 (`R11`).
# Order inside each session MUST match the fenced PASS block of `docs/testing/lead-run-order.md`.
SESSION_PASS_SPECS: Dict[int, Tuple[SessionPassSpec, ...]] = {
    1: (
        SessionPassSpec(
            1,
            "Card B",
            "step=code_obj_holder type=object raw_type=8 is_closure=0 source=menu_mc members=49 of=49",
            "log",
            "FO4SFPipboyMenu.log",
        ),
        SessionPassSpec(
            1,
            "Card B",
            "step=code_obj_destruction movie=<hex> called=1",
            "log",
            "FO4SFPipboyMenu.log",
        ),
        SessionPassSpec(
            1,
            "Card B",
            "step=map_unregister ok=1",
            "log",
            "FO4SFPipboyMenu.log",
        ),
        SessionPassSpec(
            1,
            "Card B",
            "step=destroy menu=<hex> flags=<flags>",
            "log",
            "FO4SFPipboyMenu.log",
        ),
        SessionPassSpec(
            1,
            "Card B",
            "step=menu_guard registered=<menus> count=<n>/38",
            "log",
            "FO4SFPipboyMenu.log",
        ),
        SessionPassSpec(
            1,
            "Card B",
            "step=process_user_event name=Cancel handled=<0|1> down=1",
            "log",
            "FO4SFPipboyMenu.log",
        ),
        SessionPassSpec(
            1,
            "Card B",
            "step=toggle n=<k> ignored=menu_open menu=Console",
            "log",
            "FO4SFPipboyMenu.log",
        ),
        SessionPassSpec(
            1,
            "Card B",
            "step=request_open by=map_key page=3 ignored=menu_open menu=Console",
            "log",
            "FO4SFPipboyMenu.log",
        ),
        SessionPassSpec(
            1,
            "Card B",
            "step=dispatch n=<k> fn=FO4SF_CombatInput.OnVatsKey ignored=menu_open menu=Console",
            "log",
            "FO4SFCombat.log",
        ),
        SessionPassSpec(
            1,
            "Card B",
            "step=dispatch n=<k> fn=FO4SF_CombatInput.OnAmmoKey ignored=menu_open menu=Console",
            "log",
            "FO4SFCombat.log",
        ),
        SessionPassSpec(
            1,
            "Card C",
            "FO4SF_NEWGAME rt=<rt> blocked input=handscanner",
            "log",
            "fo4sf_newgame.0.log",
        ),
        SessionPassSpec(
            1,
            "Card C",
            "step=starmap_block_install menu=<menu> found=1 slot=<slot> orig_rva=<rva>",
            "log",
            "FO4SFPipboyMenu.log",
        ),
        SessionPassSpec(
            1,
            "Card C",
            CARD_C_STARMAP_BLOCKED_LINE,
            "log",
            "FO4SFPipboyMenu.log",
        ),
    ),
    3: (
        SessionPassSpec(
            3,
            "Card 1",
            "check: ok",
            "text",
            "make_home_planet.py check",
        ),
        SessionPassSpec(
            3,
            "Card 1",
            "installed 3 files, plugins ['FO4SFHome.esm', 'FO4TerrainCore_Home.esm']",
            "text",
            "home_world_install.py install",
        ),
        SessionPassSpec(
            3,
            "Card 1 / Card 2",
            "uninstalled",
            "text",
            "home_world_install.py undo",
        ),
        SessionPassSpec(
            3,
            "Card 1 / Card 2",
            "nothing installed",
            "text",
            "home_world_install.py status",
        ),
    ),
    4: (
        SessionPassSpec(
            4,
            "Sub-session 4A",
            "install batch <fo4dlc-stage>: ['FO4DLC.esm', 'FO4DLC - Main.ba2', 'FO4DLC - Textures.ba2', "
            "'FO4DLCTextures2.esm', 'FO4DLCTextures2 - Textures.ba2', 'FO4DLCTextures3.esm', "
            "'FO4DLCTextures3 - Textures.ba2'] -> <starfield-dir>\\Data (<gb> GB)",
            "text",
            "deploy_starfield.py install",
        ),
        SessionPassSpec(
            4,
            "Sub-session 4A",
            "installed. Undo with: python deploy_starfield.py uninstall --starfield <game dir> --plugin-name FO4DLC.esm",
            "text",
            "deploy_starfield.py install",
        ),
        SessionPassSpec(
            4,
            "Sub-session 4A",
            "installed port as recorded: FO4Port.esm <sha8>",
            "text",
            "deploy_starfield.py verify",
        ),
        SessionPassSpec(
            4,
            "Sub-session 4B",
            "installed wb5 session: added=8, plugins=['FO4DLC.esm', 'FO4DLCTextures2.esm', "
            "'FO4DLCTextures3.esm', 'FO4TerrainCore_DLC.esm']",
            "text",
            "make_cw_dlc_override.py install",
        ),
        SessionPassSpec(
            4,
            "Sub-session 4B",
            "uninstalled wb5 session: removed=8, restored_fo4dlc=False",
            "text",
            "make_cw_dlc_override.py uninstall",
        ),
        SessionPassSpec(
            4,
            "Sub-session 4C",
            "installed 3 files, plugins ['FO4WorldFarHarbor.esm', 'FO4WorldFarHarbor_Mars.esm']",
            "text",
            "exp_install.py install (Far Harbor)",
        ),
        SessionPassSpec(
            4,
            "Sub-session 4C",
            "installed 3 files, plugins ['FO4WorldNukaWorld.esm', 'FO4WorldNukaWorld_Mars.esm']",
            "text",
            "exp_install.py install (Nuka-World)",
        ),
        SessionPassSpec(
            4,
            "Sub-session 4C",
            "uninstalled",
            "text",
            "exp_install.py uninstall",
        ),
    ),
}


# Named stop-point / FAIL lines per session (`docs/testing/lead-run-order.md` Stop Point sections).
SESSION_STOP_SPECS: Dict[int, Tuple[SessionStopSpec, ...]] = {
    1: (
        SessionStopSpec(
            1,
            "Card B",
            "s1_card_b_is_closure",
            "code_obj_holder reported is_closure != 0",
            r"\bstep=code_obj_holder\b[^\r\n]*\bis_closure=(?!0\b)",
        ),
        SessionStopSpec(
            1,
            "Card B",
            "s1_card_b_members",
            "code_obj_holder reported members != 49",
            r"\bstep=code_obj_holder\b[^\r\n]*\bmembers=(?!49\b)",
        ),
        SessionStopSpec(
            1,
            "Card B",
            "s1_card_b_refuse",
            "plugin logged refuse step= failure",
            r"\brefuse\s+step=",
        ),
        SessionStopSpec(
            1,
            "Card B",
            "s1_card_b_console_leak",
            "hotkey acted over Console without ignored=menu_open",
            r"\bstep=(?:toggle|request_open|dispatch)\b(?![^\r\n]*\bignored=menu_open\b)[^\r\n]*\bmenu=Console\b",
        ),
        SessionStopSpec(
            1,
            "Card C",
            "s1_card_c_outside_image",
            "starmap_block_install refused with outside_image",
            r"\bstep=starmap_block_install\b[^\r\n]*\boutside_image\b",
        ),
        SessionStopSpec(
            1,
            "Card C",
            "s1_card_c_refuse_starmap",
            "refuse step=starmap_block logged",
            r"\brefuse\s+step=starmap_block\b",
        ),
    ),
    3: (
        SessionStopSpec(
            3,
            "Card 1",
            "s3_not_ordered",
            "home_world_install.py reported 'not ordered:'",
            r"\bnot ordered:",
            re.IGNORECASE,
        ),
        SessionStopSpec(
            3,
            "Card 1",
            "s3_duplicate_override",
            "home_world_install.py refused duplicate override",
            r"\bduplicate override\b",
            re.IGNORECASE,
        ),
        SessionStopSpec(
            3,
            "Card 1",
            "s3_already_installed",
            "home_world_install.py refused (already installed)",
            r"\balready installed\b",
            re.IGNORECASE,
        ),
        SessionStopSpec(
            3,
            "Card 1",
            "s3_refused",
            "home_world_install.py or make_home_planet.py refused",
            r"\brefused\b",
            re.IGNORECASE,
        ),
        SessionStopSpec(
            3,
            "Card 1",
            "s3_check_failed",
            "make_home_planet.py check failed",
            r"\bcheck:\s*(?:fail(?:ed)?|error|\d+\s+problem)",
            re.IGNORECASE,
        ),
    ),
    4: (
        SessionStopSpec(
            4,
            "Sub-session 4A",
            "s4a_verify_mismatch",
            "deploy_starfield.py verify mismatch (differs / missing)",
            r"(?:\b(?:FO4Port\.esm|FO4DLC(?:\.esm|Textures\d+\.esm)?)\b[^\r\n]*\b(?:differs|missing)\b"
            r"|\bverify\b[^\r\n]*\b(?:differs|missing|fail(?:ed)?)\b)",
            re.IGNORECASE,
        ),
        SessionStopSpec(
            4,
            "Sub-session 4A",
            "s4a_deploy_refused",
            "deploy_starfield.py refused install/uninstall",
            r"\bdeploy_starfield(?:\.py)?\b[^\r\n]*\brefused\b|\brefused\b[^\r\n]*\b(?:FO4DLC|deploy_starfield|min-free)\b",
            re.IGNORECASE,
        ),
        SessionStopSpec(
            4,
            "Sub-session 4B",
            "s4b_bridge_inactive",
            "FO4SFBridge.esm inactive or held off by plugin_toggle.py",
            r"\bFO4SFBridge\.esm\b[^\r\n]*\binactive\b|\bplugins held off by plugin_toggle\.py\b",
            re.IGNORECASE,
        ),
        SessionStopSpec(
            4,
            "Sub-session 4B",
            "s4b_load_door_failed",
            "FO4SF_LoadDoor failed arrival or refusal",
            r"\bload door arrival failed\b|\bFO4SF_LoadDoor\s+(?:refused:|retry gave up\b)",
            re.IGNORECASE,
        ),
        SessionStopSpec(
            4,
            "Sub-session 4B",
            "s4b_wb5_mismatch",
            "WB5/WB5b install refusal or reference mismatch",
            r"\b(?:make_cw_dlc_override(?:\.py)?|wb5)\b[^\r\n]*\b(?:refused|mismatch|fail(?:ed)?)\b",
            re.IGNORECASE,
        ),
        SessionStopSpec(
            4,
            "Sub-session 4C",
            "s4c_not_ordered",
            "exp_install.py order reported 'not ordered:'",
            r"\bnot ordered:",
            re.IGNORECASE,
        ),
        SessionStopSpec(
            4,
            "Sub-session 4C",
            "s4c_install_or_uninstall_failed",
            "exp_install.py install failed or uninstall incomplete",
            r"\b(?:install failed|uninstall incomplete)\b",
            re.IGNORECASE,
        ),
    ),
}


_PLACEHOLDER_RE = re.compile(r"<([^>\r\n]+)>")
_FENCED_BLOCK_RE = re.compile(r"```([A-Za-z0-9_-]*)\r?\n(.*?)```", re.S)


def expected_sheet_pass_lines(session_num: int) -> List[str]:
    """Return the exact list of PASS lines expected in `docs/testing/lead-run-order.md` for `session_num`."""
    if session_num not in SESSION_PASS_SPECS:
        raise ValueError(f"unsupported session {session_num!r}; expected one of {SUPPORTED_SESSIONS}")
    return [spec.line for spec in SESSION_PASS_SPECS[session_num]]


def extract_session_pass_lines(md_text: str, session_num: int) -> List[str]:
    """Extract the fenced `log` or `text` PASS block lines for `session_num` from `lead-run-order.md`."""
    parts = re.split(r"(?m)^##\s+(Session\s+(\d+)\s+—\s+[^\r\n]+)$", md_text)
    for idx in range(1, len(parts), 3):
        if int(parts[idx + 1]) == session_num:
            body = re.split(r"(?m)^##\s+(?!Session\b)", parts[idx + 2], maxsplit=1)[0]
            lines: List[str] = []
            for lang, block_body in _FENCED_BLOCK_RE.findall(body):
                if lang.strip().lower() in ("log", "text"):
                    lines.extend(
                        ln.strip()
                        for ln in block_body.splitlines()
                        if ln.strip() and not ln.strip().startswith("#")
                    )
            return lines
    raise ValueError(f"Session {session_num} section not found in run sheet")


def compile_spec_pattern(sheet_line: str, block_kind: str = "log") -> re.Pattern[str]:
    """Compile a deterministic regex from a sheet PASS template line.

    - `<a|b>` placeholders match any listed literal alternative (`(?:a|b)`).
    - Other `<name>` placeholders match a non-empty inline value (`[^\\r\\n]+?`).
    - Path separators `\\Data` accept either `\\Data` or `/Data`.
    - `log` lines allow any standard SFSE/Papyrus prefix before the line (`(?:^|\\s)`).
    - `text` CLI capture lines anchor at start-of-line (with optional `[timestamp]` prefixes)
      so short lines like `uninstalled` cannot falsely match `not uninstalled` or
      `uninstalled wb5 session: ...`.
    """
    pieces: List[str] = []
    cursor = 0
    for match in _PLACEHOLDER_RE.finditer(sheet_line):
        literal = sheet_line[cursor : match.start()]
        if literal:
            escaped = re.escape(literal).replace(r"\\Data", r"[\\/]Data")
            pieces.append(escaped)
        token = match.group(1)
        if "|" in token:
            alts = "|".join(re.escape(alt) for alt in token.split("|"))
            pieces.append(f"(?:{alts})")
        else:
            pieces.append(r"[^\r\n]+?")
        cursor = match.end()
    tail = sheet_line[cursor:]
    if tail:
        escaped_tail = re.escape(tail).replace(r"\\Data", r"[\\/]Data")
        pieces.append(escaped_tail)

    body = "".join(pieces)
    if block_kind == "text":
        prefix = r"^(?:\[[^\]]*\]\s*)*"
    else:
        prefix = r"(?:^|\s)"
    return re.compile(prefix + body + r"\s*$")


def _iter_log_lines(log_dir: Path) -> List[Tuple[str, int, str]]:
    """Read `(relative_posix_path, 1_based_line_no, text)` strictly inside `log_dir`."""
    root = log_dir.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"log directory does not exist: {log_dir}")

    collected_files: List[Tuple[str, Path]] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            # Never follow symlinks that could point outside the named copied-log folder.
            continue
        if not path.is_file():
            continue
        if path.suffix.lower() not in SUPPORTED_LOG_EXTENSIONS:
            continue
        resolved = path.resolve()
        try:
            rel = resolved.relative_to(root).as_posix()
        except ValueError:
            continue
        collected_files.append((rel, resolved))

    collected_files.sort(key=lambda item: item[0].lower())
    lines: List[Tuple[str, int, str]] = []
    for rel, full in collected_files:
        with full.open("r", encoding="utf-8", errors="replace") as fp:
            for lineno, raw in enumerate(fp, 1):
                lines.append((rel, lineno, raw.rstrip("\r\n")))
    return lines


def _format_hit(rel: str, lineno: int, text: str) -> str:
    return f"{rel}:{lineno}: {text}"


def evaluate_session_logs(
    log_dir: Path | str,
    sessions: Sequence[int] = SUPPORTED_SESSIONS,
    *,
    allow_map_suppress_fallback: bool = False,
) -> Dict[str, object]:
    """Evaluate copied logs in `log_dir` against Sessions 1, 3, and/or 4 (strictly read-only)."""
    selected = tuple(int(s) for s in sessions)
    for s in selected:
        if s not in SESSION_PASS_SPECS:
            raise ValueError(f"unsupported session {s!r}; expected subset of {SUPPORTED_SESSIONS}")

    root = Path(log_dir)
    all_lines = _iter_log_lines(root)
    files_scanned = sorted({rel for rel, _ln, _txt in all_lines})
    fallback_pat = compile_spec_pattern(MAP_SUPPRESS_FALLBACK_LINE, "log")

    session_reports: Dict[int, Dict[str, object]] = {}
    any_stop_hit = False
    any_missing = False

    for snum in selected:
        cards_order: List[str] = []
        cards: Dict[str, Dict[str, object]] = {}

        def _ensure_card(card_name: str) -> Dict[str, object]:
            if card_name not in cards:
                cards_order.append(card_name)
                cards[card_name] = {
                    "card": card_name,
                    "verdict": "PASS",
                    "pass_lines": [],
                    "stop_points": [],
                }
            return cards[card_name]

        # 1. Evaluate every PASS line from the single declarative table.
        found_count = 0
        missing_count = 0
        for spec in SESSION_PASS_SPECS[snum]:
            card_entry = _ensure_card(spec.card)
            pat = compile_spec_pattern(spec.line, spec.block_kind)
            first_hit: Optional[Tuple[str, int, str]] = None
            for rel, lineno, text in all_lines:
                if pat.search(text):
                    first_hit = (rel, lineno, text)
                    break

            status = "FOUND" if first_hit is not None else "MISSING"
            hit_str = _format_hit(*first_hit) if first_hit is not None else None
            note = ""

            if (
                first_hit is None
                and allow_map_suppress_fallback
                and snum == 1
                and spec.line == CARD_C_STARMAP_BLOCKED_LINE
            ):
                for rel, lineno, text in all_lines:
                    if fallback_pat.search(text):
                        status = "FOUND"
                        hit_str = _format_hit(rel, lineno, text)
                        note = "matched MapBlockStarMap=0 hide fallback"
                        break

            if status == "FOUND":
                found_count += 1
            else:
                missing_count += 1
                any_missing = True

            card_entry["pass_lines"].append(
                {
                    "expected": spec.line,
                    "source_hint": spec.source_hint,
                    "status": status,
                    "match": hit_str,
                    "note": note,
                }
            )

        # 2. Evaluate every named stop-point condition.
        stop_fail_count = 0
        for stop in SESSION_STOP_SPECS[snum]:
            card_entry = _ensure_card(stop.card)
            stop_re = re.compile(stop.pattern, stop.flags)
            first_hit = None
            for rel, lineno, text in all_lines:
                if stop_re.search(text):
                    first_hit = (rel, lineno, text)
                    break

            if first_hit is not None:
                stop_fail_count += 1
                any_stop_hit = True
                card_entry["stop_points"].append(
                    {
                        "stop_id": stop.stop_id,
                        "description": stop.description,
                        "status": "FAIL",
                        "match": _format_hit(*first_hit),
                    }
                )
            else:
                card_entry["stop_points"].append(
                    {
                        "stop_id": stop.stop_id,
                        "description": stop.description,
                        "status": "CLEAR",
                        "match": None,
                    }
                )

        # 3. Compute per-card and per-session verdicts.
        for card_name in cards_order:
            c = cards[card_name]
            c_stop_fail = any(sp["status"] == "FAIL" for sp in c["stop_points"])
            c_missing = any(pl["status"] == "MISSING" for pl in c["pass_lines"])
            c["verdict"] = "FAIL" if (c_stop_fail or c_missing) else "PASS"

        session_verdict = "FAIL" if (stop_fail_count > 0 or missing_count > 0) else "PASS"
        session_reports[snum] = {
            "session": snum,
            "title": SESSION_TITLES[snum],
            "verdict": session_verdict,
            "found": found_count,
            "total": len(SESSION_PASS_SPECS[snum]),
            "missing": missing_count,
            "stop_failures": stop_fail_count,
            "cards": [cards[name] for name in cards_order],
        }

    return {
        "schema": 1,
        "read_only": True,
        "log_dir": str(root),
        "files_scanned": files_scanned,
        "lines_scanned": len(all_lines),
        "selected_sessions": list(selected),
        "allow_map_suppress_fallback": allow_map_suppress_fallback,
        "all_pass": not any_stop_hit and not any_missing,
        "any_stop_failure": any_stop_hit,
        "any_missing": any_missing,
        "sessions": {str(k): v for k, v in session_reports.items()},
    }


def format_report_text(report: Dict[str, object]) -> str:
    """Format an `evaluate_session_logs` result as concise human-readable text per session and card."""
    lines: List[str] = [
        f"lead sessions judge (read-only): {len(report['files_scanned'])} file(s), "
        f"{report['lines_scanned']} line(s) scanned",
    ]
    sessions_map = report["sessions"]
    for snum in report["selected_sessions"]:
        s = sessions_map[str(snum)]
        lines.append(
            f"\n[{s['verdict']}] {s['title']} "
            f"(PASS lines: {s['found']}/{s['total']}, stop failures: {s['stop_failures']})"
        )
        for card in s["cards"]:
            lines.append(f"  Card: {card['card']} -> {card['verdict']}")
            for pl in card["pass_lines"]:
                suffix = f"  [{pl['note']}]" if pl["note"] else ""
                lines.append(f"    {pl['status']:7s}  {pl['expected']}{suffix}")
                if pl["match"]:
                    lines.append(f"             hit: {pl['match']}")
            for sp in card["stop_points"]:
                if sp["status"] == "FAIL":
                    lines.append(f"    FAIL     stop={sp['stop_id']} ({sp['description']})")
                    lines.append(f"             hit: {sp['match']}")
                else:
                    lines.append(f"    CLEAR    stop={sp['stop_id']} ({sp['description']})")
    overall = "PASS" if report["all_pass"] else "FAIL"
    lines.append(f"\noverall: {overall}")
    return "\n".join(lines)
