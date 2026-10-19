#!/usr/bin/env python3
"""Print a short summary of a BA2 archive for conversion planning.

Usage:
  python scripts/ba2_summary.py path/to/archive.ba2
  python scripts/ba2_summary.py path/to/archive.ba2 --largest 5
"""
import argparse
import sys

from fo4sf.ba2 import Ba2, Ba2Error


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("archive", help="Path to a .ba2 file")
    p.add_argument("--largest", type=int, default=0, metavar="N",
                   help="Also list the N largest entries by unpacked size")
    args = p.parse_args()

    try:
        a = Ba2(args.archive)
    except (OSError, Ba2Error) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    s = a.summary()
    print(f"{s['path']}")
    print(f"  version={s['version']} kind={s['kind']}")
    print(f"  entries: {s['total_entries']}  (general={s['general_count']}  textures={s['texture_count']})")
    print(f"  unpacked: {s['total_unpacked']:,} bytes  (general={s['general_unpacked']:,}  textures={s['texture_unpacked']:,})")
    print(f"  packed:   {s['total_packed']:,} bytes")

    if args.largest:
        top = a.largest_entries(args.largest)
        if top:
            print("  largest by unpacked size:")
            for e in top:
                print(f"    {e['unpacked']:>12,}  {e['kind']}  {e['name']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
