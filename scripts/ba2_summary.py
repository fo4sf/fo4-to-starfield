#!/usr/bin/env python3
"""Print a summary of a BA2 archive, including counts by file extension.

Useful for conversion planning: see how many meshes, textures, animations,
etc. are in an archive before deciding what to convert first.

Usage:
    python scripts/ba2_summary.py path/to/archive.ba2
"""
import argparse
import sys
from pathlib import Path

# Allow running from repo root or scripts/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from fo4sf.ba2 import Ba2, Ba2Error


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("archive", help="Path to a .ba2 file")
    p.add_argument("--extensions", action="store_true",
                   help="Also print counts by file extension")
    args = p.parse_args()

    try:
        ba2 = Ba2(args.archive)
    except (Ba2Error, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    s = ba2.summary()
    print(f"path:      {s['path']}")
    print(f"version:   {s['version']}")
    print(f"kind:      {s['kind']}")
    print(f"entries:   {s['entries']}")
    print(f"general:   {s['general']}")
    print(f"textures:  {s['textures']}")

    if args.extensions or True:  # always show for now; flag reserved
        counts = ba2.extension_counts()
        if counts:
            print("\nby extension:")
            for ext, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
                label = f".{ext}" if ext else "(no extension)"
                print(f"  {label:20} {n}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
