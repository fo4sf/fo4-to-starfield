"""Find which NIFs, and which blocks in them, hold a given 32-bit value (docs/spikes/red-rocket-crash-research.md).

    python scripts/game/nif_float_scan.py <folder | .ba2 | .nif> [...] [--value 0x3ca3d70a] [--filter text]
        [--names @list.txt] [--objects <core build>/objects.json --near redrocket=-1005,1136,200 ...] [--json <out.json>]

The Red Rocket crash reads a 4-byte object reference from a stream and gets 0x3ca3d70a, the float 0.02, where a block
index (or -1) belongs. If a converted NIF is that stream, the value sits in it at a place a reference is read. This scan
lists, per NIF, every block holding the value (block index, block type, byte offset in the block, 4-byte aligned or
not) and, for bhkPhysicsSystem box blobs (sfcollision.BLOB_SIZE), whether it is one of the box's half-extents
(sfcollision.box_blob clamps a door leaf's half-extent to 0.02 in convert_static). It cannot say which hit the game read;
it narrows the list of models to test. --names keeps only NIFs whose file name, without extension, is on the list (one
per line, or joined with |). --objects with one or more --near LABEL=X,Y,R (core-local metres, as objects.json) tags each
hit with the areas that place its model (matched on the converted model path, as near_changes.py does) and keeps only
NIFs placed in at least one area. Read-only, except --json, which writes a new file.
"""
import argparse
import collections
import json
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))
from fo4sf import meshcheck, nif as nifmod, sfcollision  # noqa: E402

sys.path.insert(0, os.path.join(ROOT, "scripts", "terrain"))
import near_changes  # noqa: E402

HALF_OFFSETS = {540: "hx", 556: "hy", 572: "hz"}         # sfcollision.LINEAR's half-extent words


def scan(data: bytes, value: int):
    """[(block index, block type, offset in the block, where)] for every place the 4 bytes of value occur."""
    needle = struct.pack("<I", value)
    f = nifmod.parse(data)
    out = []
    for i, blk in enumerate(f.blocks):
        t = f.type_of(i)
        at = blk.find(needle)
        while at >= 0:
            where = "aligned" if at % 4 == 0 else "unaligned"
            if t == "bhkPhysicsSystem" and len(blk) == 4 + sfcollision.BLOB_SIZE and at - 4 in HALF_OFFSETS:
                where = "box half-extent " + HALF_OFFSETS[at - 4]
            out.append((i, t, at, where))
            at = blk.find(needle, at + 1)
    return out


def _names(arg):
    if not arg:
        return None
    text = open(arg[1:], encoding="utf-8").read() if arg.startswith("@") else arg
    return {n.strip().lower() for n in text.replace("|", "\n").splitlines() if n.strip()}


def area_models(objects, areas):
    """{model_key: [area labels]} for every model placed within an area (label, (x, y), radius)."""
    out = {}
    for p in near_changes.placements(objects).values():
        model = near_changes.model_key(p.get("model"))
        if not model:
            continue
        for label, center, radius in areas:
            if near_changes.near(p.get("pos"), center, radius) and label not in out.get(model, []):
                out.setdefault(model, []).append(label)
    return out


def areas_of(name, placed):
    """The areas placing a scanned NIF: its full path (input folder or archive included) ends with a placed model's
    whole path, so a short name never stands for every model that ends the same way (Codex on #453)."""
    key = near_changes.model_key(name)
    hits = []
    for model, labels in placed.items():
        if key == model or key.endswith("/" + model):
            hits += [x for x in labels if x not in hits]
    return hits


def _area(text):
    label, _, nums = text.partition("=")
    x, y, r = (float(v) for v in nums.split(","))
    return label, (x, y), r


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("paths", nargs="+", help="NIF files, folders of NIFs or BA2 archives")
    ap.add_argument("--value", default="0x3ca3d70a", help="the 32-bit value, hex or decimal (default: the float 0.02)")
    ap.add_argument("--filter", default="", help="only NIFs whose path contains this text")
    ap.add_argument("--names", default="", help="only these model names (no extension): a|b|c or @file")
    ap.add_argument("--objects", default="", help="a core build's objects.json, for --near")
    ap.add_argument("--near", action="append", default=[], help="LABEL=X,Y,R: an area to tag hits with (repeat)")
    ap.add_argument("--json", default="")
    a = ap.parse_args(argv)
    value = int(a.value, 0)
    names = _names(a.names)
    placed = None
    if a.near:
        if not a.objects:
            ap.error("--near needs --objects")
        placed = area_models(near_changes.load(a.objects), [_area(t) for t in a.near])
    found, types, n_nif, errors = {}, collections.Counter(), 0, 0
    lines = []                                           # printed sorted, so the report does not follow os.walk's order
    for path in a.paths:
        for rel, data in meshcheck.iter_nifs(path, a.filter or None):
            # the input path stays in the name: two inputs with the same relative file do not share a JSON key
            name = os.path.join(path, rel) if os.path.isdir(path) else (path if rel == os.path.basename(path)
                                                                          else f"{path}::{rel}")
            stem = os.path.splitext(name.replace("\\", "/").rsplit("/", 1)[-1])[0].lower()
            if names is not None and stem not in names:
                continue
            where = areas_of(name, placed) if placed is not None else None
            if placed is not None and not where:
                continue
            n_nif += 1
            try:
                hits = scan(data, value)
            except Exception as e:                         # noqa: BLE001  (a reader failure is reported, not fatal)
                errors += 1
                lines.append(f"ERROR {name}: {type(e).__name__}: {e}")
                continue
            if hits:
                found[name] = [{"block": i, "type": t, "offset": o, "where": w} for i, t, o, w in hits]
                if where is not None:
                    found[name] = {"areas": where, "hits": found[name]}
                for _i, t, _o, w in hits:
                    types[f"{t} ({w})" if w.startswith("box") else t] += 1
                lines.append(f"{name}{' [' + ', '.join(where) + ']' if where else ''}: "
                             + "; ".join(f"block {i} {t} +{o} {w}" for i, t, o, w in hits[:6])
                             + (f"; +{len(hits) - 6} more" if len(hits) > 6 else ""))
    for line in sorted(lines):
        print(line)
    by_type = dict(sorted(types.items(), key=lambda kv: (-kv[1], kv[0])))
    print(f"{n_nif} NIFs scanned, {len(found)} hold 0x{value:08x}" + (f", {errors} read errors" if errors else "")
          + f"; by block type: {by_type}")
    if a.json:
        with open(a.json, "x", encoding="utf-8") as f:
            json.dump({"value": f"0x{value:08x}", "nifs": n_nif, "found": dict(sorted(found.items()))}, f, indent=1)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
