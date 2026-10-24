"""Read-only: for each FO4-only function name in the core scripts, is it native, does any Starfield script declare it,
and how often FO4's own scripts call it.

    python scripts/research/native_census.py --sf-zip "<Starfield>\\Tools\\ContentResources.zip"
        --fo4-zip "<Fallout 4>\\Data\\Scripts\\Source\\Base\\Base.zip" --out D:\\Modding\\research\\native_census.json

Reads .psc text from both zips in memory (nothing extracted). The FO4-only list is engine_probe's native gap. Prints
one line per name: native or wrapper, Starfield scripts that declare the same name (any script, not only the same
class), FO4 call sites in total and the five FO4 scripts that call it most. Only names and counts go to the output.
"""
import argparse
import json
import os
import re
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine_probe as ep  # noqa: E402


def all_decls(path):
    """{lower name: [script, ...]} for every function or event declared in any .psc of a zip, and the texts."""
    decls, texts = {}, {}
    with zipfile.ZipFile(path) as z:
        for info in z.infolist():
            if not info.filename.lower().endswith(".psc"):
                continue
            script = os.path.splitext(os.path.basename(info.filename.replace("\\", "/")))[0]
            text = z.read(info).decode("utf-8", "replace")
            texts[script] = text
            for d in ep.declarations(text):
                decls.setdefault(d["name"].lower(), []).append(script)
    return decls, texts


def census(fo4_zip, sf_zip):
    fo4 = ep.scan_zip(fo4_zip)
    sf = ep.scan_zip(sf_zip)
    gap = ep.native_gap(fo4, sf) or {}
    sf_decls, _ = all_decls(sf_zip)
    _, fo4_texts = all_decls(fo4_zip)
    rows = []
    for cls, g in sorted(gap.items()):
        natives = {d["name"].lower(): d["native"] for d in fo4["core"][cls]["decls"]}
        for name in g["fo4_only"]:
            call = re.compile(r"\b%s\s*\(" % re.escape(name), re.I)
            per = {s: len(call.findall(t)) for s, t in fo4_texts.items() if s.lower() != cls}
            per = {s: n for s, n in per.items() if n}
            rows.append({"class": cls, "name": name, "native": natives.get(name.lower(), False),
                         "sf_declared_in": sorted(set(sf_decls.get(name.lower(), [])))[:10],
                         "fo4_calls": sum(per.values()), "fo4_scripts": len(per),
                         "top": sorted(per.items(), key=lambda kv: -kv[1])[:5]})
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sf-zip", required=True)
    ap.add_argument("--fo4-zip", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    if any(ep.inside(a.out, os.path.dirname(p)) for p in (a.sf_zip, a.fo4_zip)):
        print("refused: --out is inside an input folder", file=sys.stderr)
        return 2
    rows = census(a.fo4_zip, a.sf_zip)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=1)
    for r in rows:
        top = ", ".join(f"{s} {n}" for s, n in r["top"])
        print(f"{r['class']}.{r['name']}: {'native' if r['native'] else 'wrapper'}; "
              f"SF declares in [{', '.join(r['sf_declared_in'])}]; FO4 calls {r['fo4_calls']} in {r['fo4_scripts']} "
              f"scripts" + (f": {top}" if top else ""))
    print(f"{len(rows)} names; wrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
