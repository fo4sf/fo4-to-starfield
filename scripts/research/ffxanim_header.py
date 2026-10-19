"""Read-only: print the first bytes of a few vanilla .ffxanim lip files from a Starfield archive, for format checks.

    python scripts/research/ffxanim_header.py "<Starfield>\\Data\\Starfield - FaceAnimation01.ba2" [--count 3] [--bytes 64]
        [--compare C:\\Modding\\scratch\\lipgen_test\\run1.ffxanim]

Reads the named entries in memory and prints their size and a hex dump of the first bytes; nothing is extracted to
disk. With --compare, also prints the same for a local file.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))
from fo4sf.ba2 import Ba2  # noqa: E402


def hexdump(data, n):
    lines = []
    for i in range(0, min(n, len(data)), 16):
        chunk = data[i:i + 16]
        text = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"{i:08x}  {' '.join(f'{b:02x}' for b in chunk):<47}  {text}")
    return lines


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("archive")
    ap.add_argument("--count", type=int, default=3)
    ap.add_argument("--bytes", type=int, default=64)
    ap.add_argument("--compare", action="append", default=[])
    a = ap.parse_args(argv)
    ba2 = Ba2(a.archive)
    names = [n for n in ba2.names if n.lower().endswith(".ffxanim")][:a.count]
    for n in names:
        data = ba2.read(n)
        print(f"{n}: {len(data)} bytes")
        print("\n".join(hexdump(data, a.bytes)))
    for p in a.compare:
        data = open(p, "rb").read()
        print(f"{p}: {len(data)} bytes")
        print("\n".join(hexdump(data, a.bytes)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
