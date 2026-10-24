"""Read-only: list FaceFX actor files (.facefx) and count lip animations (.ffxanim) in Starfield's archives.

    python scripts/research/facefx_list.py "<Starfield>\\Data" [--examples 5]

Reads only the name tables of the General BA2s in the folder (texture archives are skipped) and loose .facefx files
under Data. Prints every .facefx path, the .ffxanim count per archive and a few example .ffxanim paths. Nothing is
extracted or changed. LipGenerator needs an actor .facefx and an actor analysis .facefx per face rig.
"""
import argparse
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))
from fo4sf.ba2 import Ba2, Ba2Error  # noqa: E402


def scan(data, examples=5):
    out = {"facefx": [], "ffxanim": {}, "examples": [], "skipped": []}
    for f in sorted(os.listdir(data)):
        if not f.lower().endswith(".ba2"):
            continue
        try:
            a = Ba2(os.path.join(data, f))
        except (Ba2Error, OSError, ValueError, struct.error) as exc:
            out["skipped"].append(f"{f}: {exc}")
            continue
        if a.kind != "GNRL":
            continue
        n = 0
        for name in a.names:
            low = name.lower()
            if low.endswith(".facefx"):
                out["facefx"].append(f"{f}: {name}")
            elif low.endswith(".ffxanim"):
                n += 1
                if len(out["examples"]) < examples:
                    out["examples"].append(f"{f}: {name}")
        if n:
            out["ffxanim"][f] = n
    for root, _dirs, files in os.walk(data):
        for f in files:
            if f.lower().endswith(".facefx"):
                out["facefx"].append("loose: " + os.path.relpath(os.path.join(root, f), data))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("data")
    ap.add_argument("--examples", type=int, default=5)
    a = ap.parse_args(argv)
    r = scan(a.data, a.examples)
    for s in r["facefx"]:
        print("facefx", s)
    for f, n in r["ffxanim"].items():
        print(f"ffxanim {n} in {f}")
    for s in r["examples"]:
        print("example", s)
    for s in r["skipped"]:
        print("skipped", s)
    print(f"{len(r['facefx'])} .facefx, {sum(r['ffxanim'].values())} .ffxanim")
    return 0


if __name__ == "__main__":
    sys.exit(main())
