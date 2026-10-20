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
  python scripts/door_bridge/load_door_anim.py sounds --manifest <manifest.json> --doorsounds <doorsounds.tsv> --out <new>
      writes a NEW manifest where rigged load doors (and with --ordinary-doors every rigged door) carry the open / close
      sounds of a vanilla door (SfInspect doorsounds over Starfield.esm): same skeleton first, else the commonest pair on
      the same graph; plus <out>.sounds.json (one row per door and where its sounds came from).
  python scripts/door_bridge/load_door_anim.py flags --manifest <manifest.json> --cells <cell.json>... --out <new>
      writes a NEW manifest where each door entry carries the FNAM flags (Automatic, Hidden, Minimal Use, Sliding, Do Not
      Open In Combat Search, No To Text) of the FO4 DOOR bases placed with its model in those Fo4Export cell exports, bit
      for bit; models whose bases disagree are left as they are. Plus <out>.flags.json (one row per door).

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
    so = sub.add_parser("sounds")
    so.add_argument("--manifest", required=True)
    so.add_argument("--doorsounds", required=True, help="SfInspect <Starfield.esm> doorsounds output (TSV)")
    so.add_argument("--out", required=True)
    so.add_argument("--ordinary-doors", action="store_true", help="also give rigged non-load doors their vanilla sounds")
    fl = sub.add_parser("flags")
    fl.add_argument("--manifest", required=True)
    fl.add_argument("--cells", nargs="+", required=True, help="Fo4Export cell exports with door_bases (2026-10-18 or later)")
    fl.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "flags":
        if os.path.abspath(a.out) == os.path.abspath(a.manifest):
            raise SystemExit("refusing to overwrite the input manifest: give a new --out")
        side = a.out + ".flags.json"
        if os.path.exists(side):
            raise SystemExit(f"refusing to overwrite {side}: give a new file")
        new, rows = load_door_anim.flag_plan(read(a.manifest), [read(c) for c in a.cells])
        written = sum(1 for r in rows if r["flags"] is not None)
        reasons = {}
        for r in rows:
            if r["reason"]:
                key = r["reason"].split(":")[0]
                reasons[key] = reasons.get(key, 0) + 1
        write_new(a.out, new)
        write_new(side, {"doors": len(rows), "written": written, "reasons": reasons, "rows": rows})
        print(f"{len(rows)} doors: flags written on {written}" + "".join(f"; {v} {k}" for k, v in sorted(reasons.items()))
              + f"; wrote {a.out}")
        return 0
    if a.cmd == "sounds":
        if os.path.abspath(a.out) == os.path.abspath(a.manifest):
            raise SystemExit("refusing to overwrite the input manifest: give a new --out")
        with open(a.doorsounds, encoding="utf-8-sig", errors="replace") as f:
            rows = load_door_anim.read_door_sounds(f)
        new, plan_rows = load_door_anim.sound_plan(read(a.manifest), rows, ordinary=a.ordinary_doors)
        side = a.out + ".sounds.json"
        if os.path.exists(side):
            raise SystemExit(f"refusing to overwrite {side}: give a new file")
        write_new(a.out, new)
        counts = {}
        for r in plan_rows:
            counts[r["match"] or "none"] = counts.get(r["match"] or "none", 0) + 1
        write_new(side, {"vanilla_doors_with_sounds": len(rows), "counts": counts, "rows": plan_rows})
        print(f"{len(plan_rows)} rigged doors: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items()))
              + f" (vanilla doors with sounds: {len(rows)}); wrote {a.out}")
        return 0
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
