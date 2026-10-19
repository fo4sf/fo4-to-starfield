"""Plan which FO4 load doors open before the trip (docs/spikes/load-door-animations.md). Offline, read-only on its input.

  python scripts/door_bridge/load_door_anim.py plan --manifest <staging>\\manifest.json --out <new>\\manifest.json
      writes a NEW manifest where load doors that can animate carry load_door.anim (their own rig from
      convert_batch.py --rig-load-doors, or the rig of a non-load twin with the same bounds), plus <out>.load_doors.json
      (one row per load door and the counts). The input manifest is never written.
  python scripts/door_bridge/load_door_anim.py report --manifest <manifest.json>
      the same rows and counts for an existing manifest, nothing written.
  python scripts/door_bridge/load_door_anim.py survey --fo4-data <FO4 Data> --cells <cell.json>... --out <new.json>
      read-only on the game: for every model FO4 places as a teleporting Door in those cell exports, whether its NIF has an
      Open sequence (length, sound keys, hinged) and, if not, whether its non-load twin has one.

The plugin writer (dotnet/PluginSpike) gives a load door an animation graph only when its manifest entry has "anim", so a
manifest this tool did not touch builds exactly as before.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "src"))
from fo4sf import load_door_anim  # noqa: E402


def read(path):
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def write_new(path, value):
    if os.path.exists(path):
        raise SystemExit(f"refusing to overwrite {path}: give a new file")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(value, f, indent=1)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--manifest", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--tolerance", type=float, default=load_door_anim.TWIN_TOLERANCE_M)
    r = sub.add_parser("report")
    r.add_argument("--manifest", required=True)
    r.add_argument("--tolerance", type=float, default=load_door_anim.TWIN_TOLERANCE_M)
    v = sub.add_parser("survey")
    v.add_argument("--fo4-data", required=True)
    v.add_argument("--cells", nargs="+", required=True)
    v.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "survey":
        from fo4sf import pipeline
        models = set()
        for c in a.cells:
            cell = read(c)
            if not isinstance(cell, dict):            # a staging folder also holds other JSON (lists, maps)
                continue
            models |= {"meshes\\" + r["model"].lstrip("\\") for r in cell.get("refs", []) if r.get("model")
                       and r.get("type") == "Door" and r.get("teleport_destination")}
        rows = load_door_anim.survey(sorted(models, key=str.lower), pipeline.Fo4Archives(a.fo4_data).mesh)
        counts = {"models": len(rows), "found": sum(r["found"] for r in rows),
                  "own_open": sum(1 for r in rows if r.get("open_seconds")),
                  "twin_open": sum(1 for r in rows if any(t.get("open_seconds") for t in r["twins"]))}
        write_new(a.out, {"cells": [os.path.abspath(c) for c in a.cells], "counts": counts, "rows": rows})
        print(json.dumps(counts, indent=1))
        return 0
    if a.cmd == "plan" and os.path.abspath(a.out) == os.path.abspath(a.manifest):
        raise SystemExit("--out must be a new file, not the input manifest")
    new, rows = load_door_anim.plan(read(a.manifest), a.tolerance)
    counts = load_door_anim.summary(rows)
    if a.cmd == "plan":
        write_new(a.out, new)
        write_new(a.out + ".load_doors.json", {"manifest": os.path.abspath(a.manifest), "counts": counts, "rows": rows})
    print(json.dumps(counts, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
