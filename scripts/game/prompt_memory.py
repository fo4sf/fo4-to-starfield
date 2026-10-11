"""Per-cell memory of the camera pitch that showed the activation prompt (used by route_run.ps1).

route_run.ps1 levels the first-person camera before every route (mouse fully up, which clamps, then down LEVEL
counts) and, on a door route, tilts down STEP counts per screenshot+OCR round until the prompt is on screen (up to
9 rounds of about 2.1 s each). In the 2026-10-09 runs no door route saw the prompt in round 1, and the same door
needed the same number of rounds in different runs (Vault 114 ``05C7DC``: 3 rounds in three runs), so the pitch is
worth remembering: the next door route in that cell levels straight to it, and only a miss falls back to the old sweep.

File (JSON): {"cells": {<cell>: {"pitch": P, "models": {<model basename>: P}, "refs": {<ref>: P},
                                 "misses": {"<P>": n}, "updated": "<iso time>"}}}
P is in mouse counts below the top clamp: LEVEL (700) is the levelled camera, the sweep tries 700, 850, ..., 1900.

usage:
  prompt_memory.py get <file> <cell> [<model> [<ref>]]                       prints the pitch to start at, or "none"
  prompt_memory.py hit <file> <cell> <model> <ref> <pitch> [--missed <P>]    the prompt was found at <pitch>;
                                                                             --missed <P>: the remembered P showed none
<model> or <ref> given as "-" means unknown (route_run.ps1 passes that for an empty field: Windows PowerShell 5.1 drops
an empty-string argument to a native command, which would shift the positional arguments).
Lookup order: ref, then model, then the cell's last pitch. A pitch is not offered when it equals LEVEL (the sweep's
first round is there anyway) or when it missed MAX_MISSES times in this cell. No file or no entry prints "none", and
the runner then searches exactly as before.
"""
import argparse
import json
import os
import sys
from datetime import datetime

LEVEL = 700        # route_run.ps1: counts down from the top clamp that level the camera (calibrated in game)
STEP = 150         # route_run.ps1: counts per sweep round
MAX_MISSES = 2     # a remembered pitch that showed no prompt this often is not offered again in that cell
NONE_ARG = "-"     # route_run.ps1 passes this for an empty model or ref (PowerShell 5.1 drops empty-string arguments)


def model_key(model):
    """Basename of a model path, lower case: both slashes, so FO4 and manifest spellings match."""
    return str(model or "").replace("\\", "/").rsplit("/", 1)[-1].lower()


def load(path):
    """The memory file as a dict; a missing or unreadable file is an empty memory (the runner must never stop on it)."""
    try:
        with open(path, encoding="utf-8-sig") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {"cells": {}}
    if not isinstance(data, dict) or not isinstance(data.get("cells"), dict):
        return {"cells": {}}
    return data


def save(path, data):
    """Write the whole file through a temp file, so a crash mid-write cannot leave half a JSON behind."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, sort_keys=True)
    os.replace(tmp, path)


def _usable(pitch, misses, level=LEVEL, max_misses=MAX_MISSES):
    if isinstance(pitch, bool) or not isinstance(pitch, int) or pitch <= 0:
        return False
    if pitch == level:
        return False
    return misses.get(str(pitch), 0) < max_misses


def lookup(data, cell, model=None, ref=None, level=LEVEL, max_misses=MAX_MISSES):
    """The pitch to start the prompt search at, or None (ref, then model, then the cell's last pitch)."""
    entry = data.get("cells", {}).get(cell) if isinstance(data, dict) else None
    if not isinstance(entry, dict):
        return None
    misses = entry.get("misses") if isinstance(entry.get("misses"), dict) else {}
    candidates = []
    if ref:
        candidates.append((entry.get("refs") or {}).get(str(ref)))
    if model:
        candidates.append((entry.get("models") or {}).get(model_key(model)))
    candidates.append(entry.get("pitch"))
    for pitch in candidates:
        if _usable(pitch, misses, level, max_misses):
            return pitch
    return None


def record_hit(data, cell, model, ref, pitch, missed=None, when=None):
    """The prompt was seen at `pitch` on a route of `cell`; `missed` is a remembered pitch that showed none first."""
    pitch = int(pitch)
    entry = data.setdefault("cells", {}).setdefault(cell, {})
    entry["pitch"] = pitch
    if model:
        entry.setdefault("models", {})[model_key(model)] = pitch
    if ref:
        entry.setdefault("refs", {})[str(ref)] = pitch
    if missed is not None:
        misses = entry.setdefault("misses", {})
        key = str(int(missed))
        misses[key] = misses.get(key, 0) + 1
    entry["updated"] = when or datetime.now().isoformat(timespec="seconds")
    return data


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    get = sub.add_parser("get")
    get.add_argument("file")
    get.add_argument("cell")
    get.add_argument("model", nargs="?", default="")
    get.add_argument("ref", nargs="?", default="")
    hit = sub.add_parser("hit")
    hit.add_argument("file")
    hit.add_argument("cell")
    hit.add_argument("model")
    hit.add_argument("ref")
    hit.add_argument("pitch", type=int)
    hit.add_argument("--missed", type=int, default=None)
    a = ap.parse_args(argv)
    model = "" if a.model == NONE_ARG else a.model
    ref = "" if a.ref == NONE_ARG else a.ref
    if a.cmd == "get":
        pitch = lookup(load(a.file), a.cell, model, ref)
        print("none" if pitch is None else pitch)
        return 0
    data = record_hit(load(a.file), a.cell, model, ref, a.pitch, a.missed)
    save(a.file, data)
    print(f"{a.cell}: {a.pitch}" + (f" (missed {a.missed})" if a.missed is not None else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
