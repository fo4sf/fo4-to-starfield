"""Read converted .mesh vertex bounds (#359), without changing the input.

Usage: python -I scripts/oracles/mesh_aabb_helper.py <converted.mesh>
Reports mesh-local metres. Does not read a NIF's node transforms, collision,
placed references or world offsets; these bounds are not a collision verdict.
"""
import argparse
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from fo4sf import sfmesh  # noqa: E402


def mesh_bounds(data: bytes) -> dict:
    mesh = sfmesh.parse(data)
    if not math.isfinite(mesh.scale) or mesh.scale <= 0:
        raise ValueError("mesh scale must be finite positive")
    if not mesh.positions:
        raise ValueError("mesh has no vertices")
    low = [math.inf] * 3
    high = [-math.inf] * 3
    for raw in mesh.positions:
        for axis, value in enumerate(sfmesh.decode_position(raw, mesh.scale)):
            low[axis] = min(low[axis], value)
            high[axis] = max(high[axis], value)
    return {"frame": "mesh-local", "units": "metres", "vertices": len(mesh.positions),
            "min": low, "max": high}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mesh", type=Path)
    args = parser.parse_args(argv)
    try:
        report = mesh_bounds(args.mesh.read_bytes())
    except (OSError, ValueError) as exc:
        print(f"mesh bounds: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
