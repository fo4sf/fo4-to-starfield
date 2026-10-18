#!/usr/bin/env python3
"""CLI helper for BA2 size estimates and largest entries (conversion planning).

Usage:
  python scripts/ba2_sizes.py path/to/archive.ba2 [--top N]
"""
import argparse
import sys
from pathlib import Path

# Allow running from repo root without install
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fo4sf.ba2 import Ba2, Ba2Error


def main():
    p = argparse.ArgumentParser(description="BA2 size estimates and largest entries")
    p.add_argument("path", help="Path to a .ba2 archive")
    p.add_argument("--top", type=int, default=10, help="Number of largest entries to show (default 10)")
    args = p.parse_args()

    try:
        a = Ba2(args.path)
    except (Ba2Error, OSError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    print(f"Archive: {a.path}")
    print(f"Version {a.version}, kind {a.kind}, entries {len(a.entries)}")
    est = a.size_estimates()
    print(f"Total unpacked estimate: {est['total_unpacked']:,} bytes")
    print(f"Total packed:            {est['total_packed']:,} bytes")
    print(f"General unpacked:        {est['general_unpacked']:,} bytes")
    print(f"Texture unpacked:        {est['texture_unpacked']:,} bytes")
    print(f"Average unpacked:        {est['average_unpacked']:,} bytes")
    print()
    print(f"Top {args.top} largest entries:")
    for item in a.largest_entries(args.top):
        print(f"  {item['unpacked']:12,} unpacked  {item['packed']:12,} packed  {item['kind']:4}  {item['name']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
