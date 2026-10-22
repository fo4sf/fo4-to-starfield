#!/usr/bin/env python3
"""Print a short JSON summary of a BA2 archive for conversion planning.

Usage: python scripts/ba2_summary.py path/to/archive.ba2
Offline only; no game files required beyond the archive itself.
"""
import json
import sys
from pathlib import Path

# Allow running from repo root without install
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fo4sf.ba2 import Ba2, Ba2Error  # noqa: E402


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: ba2_summary.py <archive.ba2>", file=sys.stderr)
        return 2
    path = sys.argv[1]
    try:
        ba2 = Ba2(path)
        print(json.dumps(ba2.summary(), indent=2))
        return 0
    except Ba2Error as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
