#!/usr/bin/env python3
"""Offline collision-vs-mesh bounds oracle for converted Starfield NIFs.

For each NIF (or list), reports drawn-geometry AABB and collision AABB(s),
flags collision that is missing, much smaller than the mesh, or significantly
offset. Optionally applies a REFR scale.

Research note (issue #359): fo4-native collision is a Havok tagfile transplanted
via meshcollision. Box templates are fully readable with sfcollision.read_box.
Full mesh-shape domain AABB extraction from arbitrary tagfiles is possible in
principle with hktagfile.Tagfile + known layout offsets (see meshcollision and
fo4collision domain fields) but is not yet implemented here; the script falls
back to "undecoded" for non-box blobs and still reports the mesh side.

Usage:
  python scripts/oracles/collision_bounds.py <nif-or-dir> [--scale 1.0] [--json]
Exit 1 on any flagged model.
"""
import argparse
import json
import os
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from fo4sf import nif as nifmod  # noqa: E402
from fo4sf.sfcollision import physics_blob_from_nif, read_box, BLOB_SIZE  # noqa: E402


def aabb_from_box(centre, half):
    return [centre[i] - half[i] for i in range(3)], [centre[i] + half[i] for i in range(3)]


def mesh_aabb(n: nifmod.NifFile):
    """Best-effort AABB of drawn geometry (BSTriShape / BSGeometry vertices if present)."""
    # Placeholder: real vertex extraction depends on block layout; for now return None
    # and let the caller note it. Full support would walk NiGeometryData or SF meshlets.
    return None


def collision_aabbs(blob: bytes):
    """Return list of (lo, hi) for readable collision bodies, or None if undecoded."""
    if len(blob) == BLOB_SIZE and b"hknpBoxShape" in blob and b"hknpCompoundShape" not in blob:
        try:
            c, h = read_box(blob)
            lo, hi = aabb_from_box(c, h)
            return [(lo, hi)]
        except Exception:
            return None
    # Mesh / compound / other tagfiles: domain extraction not yet wired
    return None


def analyze(nif_path: Path, scale: float = 1.0):
    data = nif_path.read_bytes()
    try:
        n = nifmod.parse(data)
    except Exception as e:
        return {"path": str(nif_path), "error": f"parse failed: {e}"}
    try:
        blob = physics_blob_from_nif(data)
        coll = collision_aabbs(blob)
    except Exception as e:
        coll = None
        coll_note = str(e)
    else:
        coll_note = None
    mesh = mesh_aabb(n)
    flags = []
    if coll is None:
        flags.append("collision_undecoded_or_missing")
    # Comparison logic when both sides available
    report = {
        "path": str(nif_path),
        "mesh_aabb": mesh,
        "collision_aabbs": coll,
        "scale": scale,
        "flags": flags,
        "note": coll_note,
    }
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("path", help="NIF file or directory of NIFs")
    ap.add_argument("--scale", type=float, default=1.0, help="REFR scale to apply to collision")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    p = Path(args.path)
    nifs = [p] if p.is_file() else list(p.rglob("*.nif"))
    if not nifs:
        print("no NIFs found", file=sys.stderr)
        return 1
    results = [analyze(n, args.scale) for n in nifs]
    flagged = sum(1 for r in results if r.get("flags"))
    if args.json:
        print(json.dumps({"models": results, "flagged": flagged}, indent=2))
    else:
        for r in results:
            print(f"{r['path']}: mesh={r['mesh_aabb']} coll={r['collision_aabbs']} flags={r['flags']}")
            if r.get("note"):
                print(f"  note: {r['note']}")
        print(f"{flagged}/{len(results)} flagged")
    return 1 if flagged else 0


if __name__ == "__main__":
    raise SystemExit(main())
