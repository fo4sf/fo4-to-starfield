"""Read-only: list command-line style switches named inside a Creation Kit executable.

    python scripts/research/ck_switches.py "<Starfield>\\CreationKit.exe" [--pattern Generate --pattern Compile]

Scans the file's bytes for ASCII and UTF-16LE strings that contain one of the patterns (default: Generate, Compile,
Lip, AnimInfo, -Convert, -Build) and prints each distinct string once. Nothing is written or changed.
"""
import argparse
import re
import sys

DEFAULT = ("Generate", "Compile", "Lip", "AnimInfo", "-Convert", "-Build")


def strings(data, minlen=6):
    """Distinct ASCII and UTF-16LE strings of at least minlen printable characters."""
    out = set()
    for m in re.finditer(rb"[\x20-\x7e]{%d,}" % minlen, data):
        out.add(m.group().decode("ascii"))
    for m in re.finditer(rb"(?:[\x20-\x7e]\x00){%d,}" % minlen, data):
        out.add(m.group().decode("utf-16le"))
    return out


def matches(found, patterns):
    pats = [p.lower() for p in patterns]
    return sorted(s for s in found if any(p in s.lower() for p in pats) and len(s) <= 200)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("exe")
    ap.add_argument("--pattern", action="append")
    a = ap.parse_args(argv)
    with open(a.exe, "rb") as fh:
        data = fh.read()
    hits = matches(strings(data), a.pattern or DEFAULT)
    for s in hits:
        print(s)
    print(f"{len(hits)} strings from {a.exe} ({len(data)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
