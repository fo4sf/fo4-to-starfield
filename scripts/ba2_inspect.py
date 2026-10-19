#!/usr/bin/env python3
"""Inspect a BA2 archive: print a summary and optionally the largest entries.

Useful for conversion planning: see how much general vs texture data an archive holds,
and which files dominate the size.

Usage:
    python -I scripts/ba2_inspect.py path/to/archive.ba2
    python -I scripts/ba2_inspect.py path/to/archive.ba2 --largest 20
    python -I scripts/ba2_inspect.py path/to/archive.ba2 --json
"""
import argparse
import json
import sys

from fo4sf.ba2 import Ba2, Ba2Error


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("ba2", help="path to a .ba2 archive")
    p.add_argument("--largest", type=int, default=0, metavar="N",
                   help="also print the N largest entries by unpacked size (0 = summary only)")
    p.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = p.parse_args(argv)

    try:
        a = Ba2(args.ba2)
    except Ba2Error as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    summary = a.summary()
    largest = a.largest_entries(args.largest) if args.largest > 0 else []

    if args.json:
        out = {"summary": summary, "largest": largest}
        json.dump(out, sys.stdout, indent=2)
        print()
    else:
        print(f"Archive: {summary.get('path', args.ba2)}")
        print(f"  version {summary.get('version')}  kind {summary.get('kind')}")
        print(f"  entries: {summary.get('total_entries', summary.get('entries', '?'))}")
        gnrl = summary.get("gnrl_count", summary.get("general", 0))
        dx10 = summary.get("dx10_count", summary.get("textures", 0))
        print(f"  general (GNRL): {gnrl}")
        print(f"  textures (DX10): {dx10}")
        if "gnrl_unpacked" in summary:
            def mb(n):
                return f"{n / 1_048_576:.1f} MiB" if n >= 1_048_576 else f"{n:,} B"
            print(f"  unpacked: GNRL {mb(summary['gnrl_unpacked'])}  DX10 {mb(summary['dx10_unpacked'])}  total {mb(summary['total_unpacked'])}")
            print(f"  packed:   total {mb(summary['total_packed'])}")
        if largest:
            print(f"\nTop {len(largest)} by unpacked size:")
            for i, e in enumerate(largest, 1):
                print(f"  {i:2d}. {e['unpacked']:12,} B  {e['kind']:4s}  {e['name']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
