"""Terrain experiment 2c: the real Fallout 4 objects around Red Rocket on the exp2b terrain (docs/terrain/experiment2c.md).

    dotnet run --project dotnet/Fo4Land -c Release -- <Fallout4.esm> export-exterior Commonwealth -20 16 -15 21 <work>/export.json
    python scripts/terrain/make_exp2c.py select --export <work>/export.json --work <work>
    python scripts/convert_batch.py --cell-json <work>/convert_input.json --staging <work>/convert --prefix fo4cw
           --types <printed by select> --limit 100000 --resume ... (the usual converter arguments, --starfield-data included)
    python scripts/terrain/make_exp2c.py stage --work <work> --exp2b <terrain_exp2b> --out <terrain_exp2c> --texconv <exe>
    dotnet run --project dotnet/TerrainExp2 -c Release -- <Starfield.esm> <terrain_exp2c>
    python scripts/terrain/make_exp2c.py check --work <work> --exp2b <terrain_exp2b> --out <terrain_exp2c> --sf-data <dir>

select   classifies every exported reference: convert, or skip with a reason (never silently). Writes convert_input.json
         (the references to convert, schema v2) and selection.json.
stage    joins the selection with the converter manifest (exterior.place), copies exp2b (terrain, mask, Mars plugin,
         params), adds the object list for TerrainExp2 (objects.json), copies the converted meshes / geometries /
         materials / textures under Data\\, and writes plan.json: the 14 exp2 terrain points (each re-judged against
         the placed collision) plus points on top of the Red Rocket building floor and other large flat objects.
check    decodes the BTD under every placed object's origin (object z - terrain z), the converted collision under every
         plan point, and raw-walks the plugins (masters, cells, REFR counts, base records, exp2b records unchanged).
Everything this writes stays outside the repo (derived game data).
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "src"))
from fo4sf import exterior  # noqa: E402


def load(path):
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def save(path, value, indent=1):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(value, f, indent=indent)
    os.replace(tmp, path)


# ------------------------------------------------------------------------------------------------------------- select
def cmd_select(a):
    export = load(a.export)
    sub, skipped = exterior.select(export)
    save(os.path.join(a.work, "convert_input.json"), sub)
    models = sorted({exterior.source_key(r["model"]) for r in sub["refs"]})
    rep = {"export": os.path.abspath(a.export), "refs": len(export["refs"]), "deferred": len(export.get("deferred_refs", [])),
           "to_convert": len(sub["refs"]), "models": len(models), "skipped": len(skipped),
           "skip_reasons": exterior.reason_counts(skipped), "convert_types": list(exterior.CONVERT_TYPES),
           "skipped_refs": skipped}
    save(os.path.join(a.work, "selection.json"), rep)
    print(f"{rep['refs']} references + {rep['deferred']} deferred: convert {rep['to_convert']} ({rep['models']} models), "
          f"skip {rep['skipped']}: {rep['skip_reasons']}")
    print("convert_batch --types " + ",".join(exterior.CONVERT_TYPES))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("select")
    s.add_argument("--export", required=True)
    s.add_argument("--work", required=True)
    a = ap.parse_args()
    return {"select": cmd_select}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
