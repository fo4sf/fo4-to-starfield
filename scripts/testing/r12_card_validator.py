#!/usr/bin/env python3
"""Validator and template helper for Round 12 test / probe markdown cards.

Enforces Round 12 card requirements:
  1. At least one verification markdown table includes a `VIDEO` column.
  2. A `Claude's Additions` section exists containing a 5-row markdown table
     covering `#854` (robot/Codsworth), `#855` (creatures), `#856` (humans),
     gun moving parts proof, and gun sounds (on hold).
  3. Standard card safety: `NEW GAME needed` notice (when required), placeholders
     instead of local Windows drive letters (`[A-Za-z]:\\` or `/`), and `P3`
     rules (zero `m`/`n`/`v` in ```` ```console ```` lines and `bat <name>`
     commands, and zero stripped `FO4SF_*` `GLOB`/`QUST` EDIDs in `set`/`help`).
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys
from typing import Dict, List, Optional, Sequence, Tuple

FENCED_BLOCK_RE = re.compile(r"```([A-Za-z0-9_-]*)[ \t]*\r?\n(.*?)```", re.DOTALL)
DRIVE_PATH_RE = re.compile(r"\b[A-Za-z]:[\\/]")

CLAUDE_ADDITION_MATCHERS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("#854 robot/Codsworth", ("854", "codsworth", "robot")),
    ("#855 creatures", ("855", "creature", "radroach", "deathclaw")),
    ("#856 humans", ("856", "human")),
    ("gun moving parts", ("moving parts", "gunpart", "gun_*.af", "misca", "xm2311")),
    ("gun sounds", ("sound", "sndr", "on hold")),
)

REQUIRED_CLAUDE_ROW_COUNT = 5


def _parse_md_row(line: str) -> List[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def _is_separator_row(cells: Sequence[str]) -> bool:
    return bool(cells) and all(bool(re.fullmatch(r":?-{3,}:?", c.replace(" ", ""))) for c in cells)


def extract_markdown_tables(md_text: str) -> List[Tuple[int, List[str], List[List[str]]]]:
    """Return list of (header_line_no, headers, data_rows) outside fenced code blocks."""
    tables: List[Tuple[int, List[str], List[List[str]]]] = []
    lines = md_text.splitlines()
    in_fence = False
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("```"):
            in_fence = not in_fence
            i += 1
            continue
        if in_fence:
            i += 1
            continue
        if "|" in line and i + 1 < len(lines) and "|" in lines[i + 1]:
            headers = _parse_md_row(line)
            sep = _parse_md_row(lines[i + 1])
            if len(headers) >= 2 and len(sep) == len(headers) and _is_separator_row(sep):
                header_line = i + 1
                rows: List[List[str]] = []
                j = i + 2
                while j < len(lines):
                    row_line = lines[j].strip()
                    if not row_line or "|" not in row_line or row_line.startswith("```"):
                        break
                    cells = _parse_md_row(row_line)
                    rows.append(cells)
                    j += 1
                tables.append((header_line, headers, rows))
                i = j
                continue
        i += 1
    return tables


def _find_claude_additions_section(md_text: str) -> Optional[str]:
    lines = md_text.splitlines()
    start_idx: Optional[int] = None
    start_level = 0
    heading_re = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
    for idx, line in enumerate(lines):
        m = heading_re.match(line)
        if not m:
            continue
        title = m.group(2).lower()
        if "claude" in title and "addition" in title:
            start_idx = idx + 1
            start_level = len(m.group(1))
            break
    if start_idx is None:
        return None
    end_idx = len(lines)
    for idx in range(start_idx, len(lines)):
        m = heading_re.match(lines[idx])
        if m and len(m.group(1)) <= start_level:
            end_idx = idx
            break
    return "\n".join(lines[start_idx:end_idx])


def validate_r12_card_markdown(
    card_rel: str,
    md_text: str,
    *,
    require_new_game_banner: bool = True,
    require_no_drive_paths: bool = True,
    require_p3: bool = True,
) -> List[str]:
    """Validate an R12 test/probe card for VIDEO column, 5-row Claude's Additions, and P3 cleanliness."""
    errors: List[str] = []
    if not md_text.strip():
        return [f"{card_rel}: card is empty"]

    if require_new_game_banner:
        top = "\n".join(md_text.splitlines()[:18])
        if "NEW GAME needed" not in top:
            errors.append(f"{card_rel}: missing 'NEW GAME needed' banner in top 18 lines")

    if require_no_drive_paths:
        for idx, line in enumerate(md_text.splitlines(), start=1):
            if DRIVE_PATH_RE.search(line):
                errors.append(f"{card_rel}:{idx}: literal Windows drive path found ({line.strip()!r}); use placeholders")

    # 1. VIDEO column check
    all_tables = extract_markdown_tables(md_text)
    video_tables = [
        (ln, hdrs, rows)
        for ln, hdrs, rows in all_tables
        if any(h.strip().upper() == "VIDEO" for h in hdrs)
    ]
    if not video_tables:
        errors.append(f"{card_rel}: missing verification table with a 'VIDEO' column")
    else:
        has_row = False
        for ln, hdrs, rows in video_tables:
            for r_off, row in enumerate(rows, start=1):
                has_row = True
                if len(row) != len(hdrs):
                    errors.append(
                        f"{card_rel}:{ln + 1 + r_off}: table row has {len(row)} columns, expected {len(hdrs)} (VIDEO table)"
                    )
        if not has_row:
            errors.append(f"{card_rel}: 'VIDEO' table has header only and 0 rows")

    # 2. Claude's Additions 5-row section check
    sec = _find_claude_additions_section(md_text)
    if sec is None:
        errors.append(f"{card_rel}: missing 'Claude's Additions' heading/section")
    else:
        sec_tables = extract_markdown_tables(sec)
        if not sec_tables:
            errors.append(f"{card_rel}: 'Claude's Additions' section must contain a 5-row markdown table")
        else:
            _ln, hdrs, rows = sec_tables[0]
            if len(rows) != REQUIRED_CLAUDE_ROW_COUNT:
                errors.append(
                    f"{card_rel}: 'Claude's Additions' table has {len(rows)} rows, expected {REQUIRED_CLAUDE_ROW_COUNT}"
                )
            for r_off, row in enumerate(rows, start=1):
                if len(row) != len(hdrs):
                    errors.append(
                        f"{card_rel}: 'Claude's Additions' row {r_off} has {len(row)} columns, expected {len(hdrs)}"
                    )
            row_texts = [" ".join(row).lower() for row in rows]
            for label, tokens in CLAUDE_ADDITION_MATCHERS:
                if not any(any(tok in rt for tok in tokens) for rt in row_texts):
                    errors.append(
                        f"{card_rel}: 'Claude's Additions' table missing expected row for {label}"
                    )

    # 3. P3 console / batch check + ban on bundle_install.py
    for lang, body in FENCED_BLOCK_RE.findall(md_text):
        lang_low = lang.strip().lower()
        for raw_line in body.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or (lang_low == "bat" and line.startswith(";")):
                continue
            if "bundle_install.py" in line:
                errors.append(f"{card_rel}: bundle_install.py is forbidden in Round 12 cards: {line!r}")
            if not require_p3:
                continue
            if lang_low == "console":
                if re.search(r"[mnv]", line, re.I):
                    errors.append(f"{card_rel}: P3 forbids M/N/V in console line: {line!r}")
                if re.match(r"^(?:set|help|setstage)\s+FO4SF_", line, re.I):
                    errors.append(f"{card_rel}: P3 forbids stripped mod GLOB/QUST EditorID in console: {line!r}")
            elif lang_low == "bat":
                if re.match(r"^(?:set|help|setstage)\s+FO4SF_", line, re.I):
                    errors.append(f"{card_rel}: P3 forbids stripped mod GLOB/QUST EditorID in bat: {line!r}")
            m_bat = re.match(r"^bat\s+([^\s;#]+)", line, re.I)
            if m_bat and re.search(r"[mnv]", m_bat.group(1), re.I):
                errors.append(f"{card_rel}: P3 forbids M/N/V in batch activation name: {m_bat.group(1)!r}")

    return errors


def validate_r12_card_file(path: pathlib.Path, **kwargs) -> List[str]:
    text = path.read_text(encoding="utf-8")
    return validate_r12_card_markdown(path.as_posix(), text, **kwargs)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cards", nargs="+", type=pathlib.Path, help="One or more Round 12 card markdown paths")
    ap.add_argument("--no-new-game-banner", action="store_true", help="Do not require NEW GAME needed banner")
    ap.add_argument("--allow-drive-paths", action="store_true", help="Allow drive-letter paths (not recommended)")
    ap.add_argument("--skip-p3", action="store_true", help="Skip P3 console/bat checks")
    args = ap.parse_args(argv)

    all_errors: List[str] = []
    for p in args.cards:
        all_errors.extend(
            validate_r12_card_file(
                p,
                require_new_game_banner=not args.no_new_game_banner,
                require_no_drive_paths=not args.allow_drive_paths,
                require_p3=not args.skip_p3,
            )
        )
    if all_errors:
        for err in all_errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1
    print(f"R12 CARDS OK: validated {len(args.cards)} file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
