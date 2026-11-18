"""Output-path safety guard for terrain and DLC staging tools (`R4`).

Refuses writing converted or staged files inside any Git repository/worktree, inside any game
installation or Steam depot folder, or over an input path.
"""
from __future__ import annotations

import os
from typing import Iterable, List

GAME_INSTALL_MARKERS = frozenset(
    {
        "starfield.exe",
        "fallout4.exe",
        "fallout4launcher.exe",
        "starfield.ccc",
        "fallout4.ccc",
        "creationkit.exe",
    }
)
GAME_DATA_ESMS = frozenset({"starfield.esm", "fallout4.esm"})


class OutputPathRefusedError(ValueError):
    """Raised when an output path targets a Git worktree, a game folder, or an input path."""


def _ancestor_dirs(path: str) -> List[str]:
    cur = os.path.abspath(path)
    if not os.path.isdir(cur):
        cur = os.path.dirname(cur)
    out: List[str] = []
    while True:
        out.append(cur)
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return out


def refuse_unsafe_output_path(out_path: str, input_paths: Iterable[str] = ()) -> str:
    """Validate `out_path` and return its normalized absolute path, or raise `OutputPathRefusedError`."""
    if not out_path or not str(out_path).strip():
        raise OutputPathRefusedError("refused: empty output path")

    abs_out = os.path.abspath(out_path)
    real_out = os.path.realpath(abs_out)
    candidates = [abs_out, real_out]

    for src in input_paths:
        if not src:
            continue
        src_abs = os.path.abspath(src)
        src_real = os.path.realpath(src_abs)
        for target in candidates:
            if os.path.normcase(target) in (os.path.normcase(src_abs), os.path.normcase(src_real)):
                raise OutputPathRefusedError(f"refused: output path {out_path!r} aliases input {src!r}")

    for target in candidates:
        norm_slash = target.replace("\\", "/").lower()
        if "/steamapps/common/" in norm_slash or "/steamapps/content/" in norm_slash:
            raise OutputPathRefusedError(
                f"refused: output path {out_path!r} lies inside a Steam game/depot folder"
            )
        for anc in _ancestor_dirs(target):
            git_marker = os.path.join(anc, ".git")
            if os.path.exists(git_marker):
                raise OutputPathRefusedError(
                    f"refused: output path {out_path!r} lies inside Git worktree/repository {anc!r}"
                )
            try:
                entries = {e.lower() for e in os.listdir(anc)}
            except OSError:
                continue
            if entries & GAME_INSTALL_MARKERS:
                raise OutputPathRefusedError(
                    f"refused: output path {out_path!r} lies inside game installation directory {anc!r}"
                )
            if os.path.basename(anc).lower() == "data" and (entries & GAME_DATA_ESMS):
                raise OutputPathRefusedError(
                    f"refused: output path {out_path!r} lies inside game Data directory {anc!r}"
                )

    return abs_out
