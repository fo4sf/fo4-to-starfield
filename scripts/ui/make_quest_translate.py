#!/usr/bin/env python3
"""Stage-time generator for `Data/Interface/Translate_en.txt` replacing Starfield's HUD "MISSION" labels.

Reads the full vanilla `interface/translate_en.txt` directly from `<starfield-data>/Starfield - Interface.ba2`,
preserves its exact BOM, encoding (UTF-16LE with BOM), line endings, and 100% of all other translation lines, and
under `--mode quest` rewrites only the 6 `$Mission*` HUD toast/status keys to use `--label` (default `QUEST`).
Under `--mode mission`, all lines are preserved untouched.

Never writes inside any Git worktree or game installation directory (Rule R4).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, Optional, Sequence, Tuple

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
for _p in (str(HERE), str(REPO / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fo4sf import ba2  # noqa: E402
import pipboy_map_store  # noqa: E402

INTERFACE_BA2_NAME = "Starfield - Interface.ba2"
TRANSLATE_ENTRY_NAME = "interface/translate_en.txt"
TARGET_REL_PATH = Path("Data") / "Interface" / "Translate_en.txt"

TARGET_KEY_TEMPLATES: Dict[str, str] = {
    "$MISSION FAILED": "{label} FAILED",
    "$MISSION STATUS": "{label} STATUS",
    "$MISSION UPDATED": "{label} UPDATED",
    "$MissionFailed": "{label} FAILED",
    "$MissionNew": "NEW {label}",
    "$MissionUpdate": "{label} UPDATED",
}


class QuestTranslateError(ValueError):
    pass


def refuse_unsafe_output_path(path: os.PathLike | str) -> Path:
    """Refuse writing staged files inside any Git worktree or game folder (Rule R4)."""
    try:
        resolved = pipboy_map_store.refuse_unsafe_output_path(path)
    except pipboy_map_store.MapStoreError as exc:
        raise QuestTranslateError(str(exc)) from exc
    return Path(resolved)


def validate_label(label: str) -> str:
    cleaned = label.strip()
    if not cleaned or any(ch in cleaned for ch in ("\t", "\r", "\n")):
        raise QuestTranslateError(f"invalid --label {label!r}: must be non-empty single-line text without tabs")
    return cleaned


def detect_encoding_and_bom(raw: bytes) -> Tuple[bytes, str]:
    if raw.startswith(b"\xff\xfe"):
        return b"\xff\xfe", "utf-16-le"
    if raw.startswith(b"\xfe\xff"):
        return b"\xfe\xff", "utf-16-be"
    if raw.startswith(b"\xef\xbb\xbf"):
        return b"\xef\xbb\xbf", "utf-8"
    return b"", "utf-8"


def _split_eol(raw_line: str) -> Tuple[str, str]:
    if raw_line.endswith("\r\n"):
        return raw_line[:-2], "\r\n"
    if raw_line.endswith("\n"):
        return raw_line[:-1], "\n"
    if raw_line.endswith("\r"):
        return raw_line[:-1], "\r"
    return raw_line, ""


def rewrite_translate_bytes(
    raw: bytes,
    *,
    mode: str = "quest",
    label: str = "QUEST",
) -> Tuple[bytes, int, int]:
    """Rewrite only the 6 `$Mission*` HUD keys when `mode == 'quest'`, preserving BOM, encoding, and line endings.

    Returns `(output_bytes, total_lines, changed_lines)`.
    """
    if mode not in ("quest", "mission"):
        raise QuestTranslateError(f"unsupported mode {mode!r} (expected 'quest' or 'mission')")
    lbl = validate_label(label)
    bom, encoding = detect_encoding_and_bom(raw)
    body = raw[len(bom):].decode(encoding)
    lines = body.splitlines(keepends=True)

    if mode == "mission":
        return raw, len(lines), 0

    replacements = {k: tmpl.format(label=lbl) for k, tmpl in TARGET_KEY_TEMPLATES.items()}
    seen_keys = set()
    changed = 0
    out_lines = []
    for raw_line in lines:
        line, eol = _split_eol(raw_line)
        if "\t" in line:
            key, val = line.split("\t", 1)
            if key in replacements:
                seen_keys.add(key)
                new_val = replacements[key]
                if val != new_val:
                    changed += 1
                out_lines.append(f"{key}\t{new_val}{eol}")
                continue
        out_lines.append(raw_line)

    missing = sorted(set(TARGET_KEY_TEMPLATES) - seen_keys)
    if missing:
        raise QuestTranslateError(f"missing expected translation keys in {TRANSLATE_ENTRY_NAME}: {', '.join(missing)}")

    out_bytes = bom + "".join(out_lines).encode(encoding)
    return out_bytes, len(lines), changed


def find_interface_ba2(starfield_data: os.PathLike | str) -> Path:
    data_dir = Path(starfield_data)
    if data_dir.is_file() and data_dir.name.lower() == INTERFACE_BA2_NAME.lower():
        return data_dir
    if not data_dir.is_dir():
        raise QuestTranslateError(f"Starfield Data directory not found: {data_dir}")
    direct = data_dir / INTERFACE_BA2_NAME
    if direct.is_file():
        return direct
    for child in data_dir.iterdir():
        if child.is_file() and child.name.lower() == INTERFACE_BA2_NAME.lower():
            return child
    raise QuestTranslateError(f"{INTERFACE_BA2_NAME} not found under {data_dir}")


def generate_quest_translate(
    starfield_data: os.PathLike | str,
    out_stage: os.PathLike | str,
    *,
    mode: str = "quest",
    label: str = "QUEST",
) -> Dict[str, object]:
    """Extract `interface/translate_en.txt` from Starfield's BA2 and write staged `<out>/Data/Interface/Translate_en.txt`."""
    stage_root = refuse_unsafe_output_path(out_stage)
    target_path = refuse_unsafe_output_path(stage_root / TARGET_REL_PATH)
    ba2_path = find_interface_ba2(starfield_data)

    try:
        archive = ba2.Ba2(str(ba2_path))
        raw = archive.read(TRANSLATE_ENTRY_NAME)
    except (ba2.Ba2Error, KeyError, OSError) as exc:
        raise QuestTranslateError(f"failed reading {TRANSLATE_ENTRY_NAME} from {ba2_path}: {exc}") from exc

    out_bytes, total_lines, changed = rewrite_translate_bytes(raw, mode=mode, label=label)
    bom, encoding = detect_encoding_and_bom(raw)

    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(out_bytes)

    return {
        "ba2_path": str(ba2_path),
        "out_path": str(target_path),
        "mode": mode,
        "label": validate_label(label),
        "encoding": encoding,
        "bom": bom.hex(),
        "total_lines": total_lines,
        "changed_lines": changed,
    }


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Stage Data/Interface/Translate_en.txt replacing Starfield's MISSION HUD labels with QUEST."
    )
    ap.add_argument("--starfield-data", required=True, help="Path to Starfield Data folder (or Starfield - Interface.ba2)")
    ap.add_argument("--out", required=True, help="Staging root directory (writes <out>/Data/Interface/Translate_en.txt)")
    ap.add_argument("--mode", choices=("quest", "mission"), default="quest", help="Label mode: quest (default) or mission (native)")
    ap.add_argument("--label", default="QUEST", help="Replacement HUD label when --mode quest (default QUEST)")
    return ap


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        res = generate_quest_translate(
            args.starfield_data,
            args.out,
            mode=args.mode,
            label=args.label,
        )
    except QuestTranslateError as exc:
        sys.stderr.write(f"make_quest_translate error: {exc}\n")
        return 1
    note = " (native labels kept)" if res["mode"] == "mission" else ""
    print(
        f"step=quest_translate mode={res['mode']} label={res['label']} "
        f"lines={res['total_lines']} changed={res['changed_lines']} out={res['out_path']}{note}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
