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
import json
import re
import struct

from . import door_motion

# the Akila template door's clips (sfnif.DOOR_TEMPLATE): 31 frames at 30 fps (docs/spikes/WP-doors-research.md)
TEMPLATE_OPEN_SECONDS = 31 / 30
# the vanilla load variant of that same rig: AK_Ext_Bld_WallA_DoorA_Load_01 (1C42C2) and _Load_03/04/05 carry the Akila
# skeleton and clips with this graph (PC read A1, SfInspect doortsv 2026-10-19: 32 vanilla rigs pair SimpleOpenClose01
# with one *_Load graph on the same skeleton and clips, so a load graph is a graph swap). For an XTEL door (step B).
TEMPLATE_XTEL_GRAPH = "AnimTextData\\Tables\\Graphs\\SimpleOpenClose02_Load.agx"
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
        if anim.get("rig") != "native":          # the template rig: Starfield's clip length, and its vanilla load graph
            anim["open_seconds"] = TEMPLATE_OPEN_SECONDS
            anim["xtel_anim_graph"] = TEMPLATE_XTEL_GRAPH
        else:
            anim.setdefault("open_seconds", None)
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


_NO_GUID = "00000000-0000-0000-0000-000000000000"


def read_door_sounds(lines):
    """Rows of SfInspect `doorsounds` (TSV, header first; build warnings before it are skipped) as dicts with
    "open" / "close" = {"start", "stop", "condition", "mapping"} or None when the door has no such sound."""
    rows, header = [], None
    for line in lines:
        cols = line.rstrip("\r\n").split("\t")
        if header is None:
            if cols and cols[0].lstrip("﻿") == "editor_id":
                header = [c.lstrip("﻿") for c in cols]
            continue
        if len(cols) < len(header) - 1:
            continue
        r = dict(zip(header, cols + [""] * (len(header) - len(cols))))

        def snd(kind):
            start = r.get(kind + "_start", "")
            if not start or start == _NO_GUID:
                return None
            return {"start": start, "stop": r.get(kind + "_stop") or _NO_GUID,
                    "condition": r.get(kind + "_condition") or None, "mapping": r.get(kind + "_mapping") or None}
        rows.append({"editor_id": r["editor_id"], "formkey": r["formkey"], "anam": r.get("anam", ""),
                     "bnam": r.get("bnam", ""), "open": snd("open"), "close": snd("close")})
    return rows


def _key(path):
    return (path or "").replace("/", "\\").lower()


def sound_plan(manifest, sound_rows, ordinary=False):
    """(new manifest, rows). Gives each rigged load door (load_door.anim) the open and close sounds of a vanilla Starfield
    door; with ordinary=True also every rigged ordinary door ("door"). The input is not changed. Choice, nearest first:
    "skeleton": a vanilla door on the same skeleton (BNAM), for a load door one with a *_Load graph first (the Akila
    template rig -> AK_Ext_Bld_WallA_DoorA_Load_01's sounds), for an ordinary door one without; "graph": the most common sound pair among vanilla doors playing the same graph
    (own rigs have no vanilla skeleton; supported hypothesis that it fits). Rows: {"editor_id", "kind", "match", "from"}
    (match None: no vanilla door to copy from, the door stays silent as today)."""
    out = copy.deepcopy(manifest)
    voiced = [r for r in sound_rows if r["open"] or r["close"]]
    by_bnam, by_anam = {}, {}
    for r in voiced:
        by_bnam.setdefault(_key(r["bnam"]), []).append(r)
        by_anam.setdefault(_key(r["anam"].rpartition("\\")[2]), []).append(r)

    def pick(rig, load):
        same = by_bnam.get(_key(rig.get("skeleton")))
        if same:       # a load door takes a vanilla load variant's sounds first, an ordinary door a non-load door's
            same = sorted(same, key=lambda r: (r["anam"].lower().endswith("_load.agx") != load, r["formkey"]))
            return "skeleton", same[0]
        pool = by_anam.get(_key((rig.get("anim_graph") or "").replace("/", "\\").rpartition("\\")[2]))
        if not pool:
            return None, None
        counts = {}
        for r in pool:
            sig = json.dumps([r["open"], r["close"]], sort_keys=True)
            counts.setdefault(sig, []).append(r)
        best = min(counts.values(), key=lambda g: (-len(g), min(x["formkey"] for x in g)))
        return "graph", min(best, key=lambda r: r["formkey"])

    rows = []
    for it in out.get("items", []):
        targets = []
        ld = it.get("load_door")
        if isinstance(ld, dict) and isinstance(ld.get("anim"), dict):
            targets.append(("load_door", ld["anim"]))
        if ordinary and isinstance(it.get("door"), dict):
            targets.append(("door", it["door"]))
        for kind, rig in targets:
            match, src = pick(rig, kind == "load_door")
            rows.append({"editor_id": it.get("editor_id"), "kind": kind, "match": match,
                         "from": f"{src['editor_id']} {src['formkey']}" if src else None})
            if src:
                if src["open"]:
                    rig["open_sound"] = dict(src["open"])
                if src["close"]:
                    rig["close_sound"] = dict(src["close"])
                rig["sounds_from"] = src["formkey"]
    return out, rows
