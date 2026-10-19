"""Load doors that open before the trip (phase 2 of the roadmap: doors with enter and exit animations).

Today every FO4 load door becomes a graph-less DOOR (interior XTEL pairs) or a scripted door (FO4SF_LoadDoor, exterior
<-> interior): the player presses E and is moved at once, the door never moves. Starfield's own visible load doors carry
an animation graph (506 of its 964 XTEL references; docs/ai/research-log.md 2026-10-10), so the door swings or slides
open, then the load screen comes. This module plans the same for the port, offline and behind switches that are off by
default (docs/spikes/load-door-animations.md):

- open_timing: the length and text-key events (FO4's door sounds) of an FO4 NIF's Open sequence.
- twin_names / plan: a load door whose own NIF does not animate (FO4 often ships a static "...Load" copy of an animated
  door) borrows the rig of its non-load twin in the same manifest, when both models have the same bounds.

Nothing here reads game data: the inputs are a parsed NIF (nif.parse) and a converter manifest.
"""
import copy
import re
import struct

from . import door_motion

# the Akila template door's clips (sfnif.DOOR_TEMPLATE): 31 frames at 30 fps (docs/spikes/WP-doors-research.md)
TEMPLATE_OPEN_SECONDS = 31 / 30
# a twin's bounds must match the load model's within this (metres, each corner coordinate): the rigged model replaces
# the load model, so a different shape or origin would show
TWIN_TOLERANCE_M = 0.05
_LOAD = re.compile(r"_?load", re.I)


def open_timing(source):
    """{"seconds", "events": [{"time", "text"}]} of the FO4 NIF's "Open" sequence (seconds = (stop - start) /
    frequency), or None when it has none. events are FO4's text keys (door sounds such as "Sound: DRSWoodOpen")."""
    for i, block in enumerate(source.blocks):
        if source.type_of(i) != "NiControllerSequence":
            continue
        name, count = struct.unpack_from("<iI", block)
        if not 0 <= name < len(source.strings) or source.strings[name] != b"Open":
            continue
        t = door_motion.sequence_timing(source, block, count)
        freq = t["frequency"] or 1.0
        return {"seconds": round(max(0.0, (t["stop"] - t["start"]) / freq), 4), "events": t["text_events"]}
    return None


def twin_names(source):
    """Candidate non-load twins of a load-door model path, nearest first: the file name with one "load" removed
    ("UtilMetalDbDoorLoad01.nif" -> "UtilMetalDbDoor01.nif", "Door_Load01" -> "Door01"); [] when the name holds none."""
    head, _, name = source.replace("/", "\\").rpartition("\\")
    out = []
    for m in _LOAD.finditer(name):
        cand = name[:m.start()] + name[m.end():]
        if cand and not cand.startswith("."):
            full = f"{head}\\{cand}" if head else cand
            if full not in out:
                out.append(full)
    return out


def _fo4_bounds(door):
    """A rigged door's bounds in its FO4 model's space: door.bounds is the rebuilt NIF's, and the FO4 point is the rebuilt
    one plus origin_offset (convert_static.convert_door: offset = pivot - hinge)."""
    off = door.get("origin_offset") or [0.0, 0.0, 0.0]
    lo, hi = door["bounds"]
    return [[lo[a] + off[a] for a in range(3)], [hi[a] + off[a] for a in range(3)]]


def _close(a, b, tol):
    return all(abs(a[k][j] - b[k][j]) <= tol for k in range(2) for j in range(3))


def plan(manifest, tolerance=TWIN_TOLERANCE_M):
    """(new manifest, rows). Every load-door item keeps its entry; the new manifest is a deep copy (the input is not
    changed). Per load door one row: {"editor_id", "source", "anim": "own" | "twin" | None, "twin", "reason"}.
    "own": the converter rigged it (--rig-load-doors). "twin": a non-load item of the same manifest (twin_names) is a
    rigged door whose FO4-space bounds equal the load model's within tolerance; its model and rig become this load
    door's load_door.anim (with "model" and "twin" set, so the writer uses the twin's rigged NIF). None: the reason says
    why (no twin, twin not rigged, bounds differ, no bounds) and the door stays the graph-less door it is today."""
    out = copy.deepcopy(manifest)
    items = out.get("items", [])
    by_source = {it.get("source", "").replace("/", "\\").lower(): it for it in items}
    rows = []
    for it in items:
        ld = it.get("load_door")
        if ld is None:
            continue
        row = {"editor_id": it.get("editor_id"), "source": it.get("source"), "anim": None, "twin": None, "reason": None}
        rows.append(row)
        if isinstance(ld, dict) and ld.get("anim"):
            row["anim"] = "own"
            continue
        if not isinstance(ld, dict) or "bounds" not in ld:
            row["reason"] = "load door entry has no bounds (manifest older than 2026-10-10)"
            continue
        names = twin_names(it.get("source", ""))
        twins = [by_source[n.lower()] for n in names if n.lower() in by_source]
        if not twins:
            row["reason"] = "no non-load twin in this manifest" if names else "model name holds no 'load'"
            continue
        twin = twins[0]
        row["twin"] = twin.get("source")
        door = twin.get("door")
        if not door or "bounds" not in door or "load_door" in twin:
            row["reason"] = "twin is not a rigged door" + (f" ({twin['door_error']})" if twin.get("door_error") else "")
            continue
        if not _close(_fo4_bounds(door), ld["bounds"], tolerance):
            row["reason"] = f"twin bounds differ by more than {tolerance} m"
            continue
        anim = copy.deepcopy(door)
        anim["model"] = twin["model"]
        anim["twin"] = twin.get("source")
        anim.setdefault("open_seconds", TEMPLATE_OPEN_SECONDS if anim.get("rig") != "native" else None)
        ld["anim"] = anim
        row["anim"] = "twin"
    return out, rows


def summary(rows):
    """{"load_doors", "own", "twin", "static", "reasons": {reason: count}}."""
    s = {"load_doors": len(rows), "own": 0, "twin": 0, "static": 0, "reasons": {}}
    for r in rows:
        if r["anim"]:
            s[r["anim"]] += 1
        else:
            s["static"] += 1
            key = re.sub(r" \(.*\)$", "", r["reason"] or "")
            s["reasons"][key] = s["reasons"].get(key, 0) + 1
    return s


def survey(models, mesh):
    """Read-only, for the PC: per FO4 load-door model (convert_batch.teleport_models over cell exports) whether its own
    NIF animates and, if not, whether a non-load twin does. mesh(name) -> NIF bytes or None (pipeline.Fo4Archives.mesh).
    Rows: {"model", "found", "open_seconds", "events", "hinged", "twins": [{"model", "found", "open_seconds"}],
    "error"}; open_seconds None = no Open sequence. Holds no game data beyond names, times and FO4's sound key names."""
    from . import nif as nifmod

    def look(name):
        raw = mesh(name)
        if raw is None:
            return {"model": name, "found": False, "open_seconds": None}
        try:
            src = nifmod.parse(raw)
            t = open_timing(src)
            hinge = bool(t) and bool(nifmod.door_hinge(src))
        except Exception as e:                     # noqa: BLE001  (one row per model, the survey goes on)
            return {"model": name, "found": True, "open_seconds": None, "error": f"{type(e).__name__}: {e}"}
        return {"model": name, "found": True, "open_seconds": t["seconds"] if t else None,
                "events": [e["text"] for e in t["events"]] if t else [], "hinged": hinge}

    rows = []
    for m in models:
        row = look(m)
        row["twins"] = [] if row.get("open_seconds") else [look(n) for n in twin_names(m)]
        rows.append(row)
    return rows
