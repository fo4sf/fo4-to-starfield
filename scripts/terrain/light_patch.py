"""light_patch.py: scale every LIGH base's lumens in a built plugin as a raw record patch (docs/terrain/exterior-lights.md,
"Calibration (17 Oct)"). A full exterior rebuild with --lumens-per-m2 takes hours; the only bytes that depend on it are the
u32 lumens of each LIGH base's DAT2, so they are rewritten in a copy and nothing else moves.

  python scripts/terrain/light_patch.py scale --in <plugin> --out <NEW plugin> --factor 0.375
                                              [--objects <objects.json> --objects-out <NEW objects.json>]
  python scripts/terrain/light_patch.py check --a <plugin> --b <patched plugin> --factor 0.375

DAT2 layout (make_core64c.light_record_problems; Starfield.esm's own DAT2): lumens = u32 at offset 52. New value =
max(1, round(old * factor)) (Python's round: halves go to the even number, the same function in `scale` and `check`).
`scale` copies the file byte for byte except those four bytes per LIGH; it refuses a compressed LIGH (the Mutagen writer
does not compress them), an existing --out, and --out equal to --in. `check` proves the two files have the same records
(count, signature, FormID, flags, size, and every group) and differ only in LIGH DAT2 bytes 52..56, each equal to the rule.
Nothing is installed; output files belong in a staging folder, never in the repo.
"""
import argparse
import json
import os
import statistics
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "src"))
from fo4sf import fo4land  # noqa: E402

LUMENS_OFFSET = 52          # u32 inside DAT2 (make_core64c.light_record_problems)
DAT2_MIN = 58               # the writer's DAT2 (radius .. flicker effect); anything shorter is not ours
COMPRESSED = 0x40000


def scaled(lumens, factor):
    """The rule: max(1, round(lumens * factor))."""
    return max(1, round(lumens * factor))


def walk(buf):
    """Every record in file order: (sig, off, size, flags, fid). Groups are recursed into and returned as ('GRUP', off,
    group size, gtype, label as int) so that a group header change shows up in the structure comparison."""
    hsize = struct.unpack_from("<I", buf, 4)[0]
    out = [("TES4", 0, hsize, struct.unpack_from("<I", buf, 8)[0], 0)]

    def go(start, end):
        for item in fo4land.iter_items(buf, start, end):
            if item[0] == "GRUP":
                _g, off, end_off, label, gtype = item
                out.append(("GRUP", off, end_off - off, gtype, struct.unpack_from("<I", label)[0]))
                go(off + 24, end_off)
            else:
                typ, off, flags, fid = item
                out.append((typ.decode("ascii", "replace"), off, struct.unpack_from("<I", buf, off + 4)[0], flags, fid))
    go(24 + hsize, len(buf))
    return out


def lumens_windows(buf, items):
    """[(absolute offset of the lumens u32, fid)] for every LIGH. ValueError for a compressed LIGH or one without a
    usable DAT2."""
    wins = []
    for sig, off, size, flags, fid in items:
        if sig != "LIGH":
            continue
        if flags & COMPRESSED:
            raise ValueError(f"LIGH {fid:08X} is compressed: this patch only rewrites uncompressed records")
        p, end, found = off + 24, off + 24 + size, None
        while p + 6 <= end:
            s = bytes(buf[p:p + 4])
            n = struct.unpack_from("<H", buf, p + 4)[0]
            if s == b"XXXX":
                raise ValueError(f"LIGH {fid:08X} has an XXXX field: not written by our builds")
            if s == b"DAT2":
                found = (p + 6, n)
                break
            p += 6 + n
        if found is None or found[1] < DAT2_MIN:
            raise ValueError(f"LIGH {fid:08X}: DAT2 {'missing' if found is None else str(found[1]) + ' bytes'}")
        wins.append((found[0] + LUMENS_OFFSET, fid))
    return wins


def read(path):
    with open(path, "rb") as f:
        buf = f.read()
    if buf[:4] != b"TES4":
        raise ValueError(f"{path}: not a plugin")
    return buf


def stats(values):
    return {"min": min(values), "median": statistics.median(values), "max": max(values)}


def cmd_scale(a):
    if not a.factor > 0:
        sys.exit("--factor must be positive")
    src, dst = os.path.abspath(a.in_), os.path.abspath(a.out)
    if os.path.normcase(src) == os.path.normcase(dst):
        sys.exit("refusing: --out is --in")
    if os.path.exists(dst):
        sys.exit(f"refusing: {dst} exists (write to a NEW file)")
    if bool(a.objects) != bool(a.objects_out):
        sys.exit("--objects and --objects-out go together")
    if a.objects_out and os.path.exists(a.objects_out):
        sys.exit(f"refusing: {a.objects_out} exists (write to a NEW file)")
    if a.objects_out and os.path.normcase(os.path.abspath(a.objects)) == os.path.normcase(os.path.abspath(a.objects_out)):
        sys.exit("refusing: --objects-out is --objects")
    buf = bytearray(read(src))
    try:
        wins = lumens_windows(buf, walk(buf))
    except ValueError as e:
        sys.exit(f"refusing: {e}")
    if not wins:
        sys.exit("refusing: no LIGH record in the plugin")
    old, new = [], []
    for off, _fid in wins:
        v, = struct.unpack_from("<I", buf, off)
        w = scaled(v, a.factor)
        struct.pack_into("<I", buf, off, w)
        old.append(v)
        new.append(w)
    with open(dst, "xb") as f:
        f.write(buf)
    print(f"{len(wins)} LIGH: lumens old {stats(old)} -> new {stats(new)} (factor {a.factor}); wrote {dst}")
    if a.objects:
        with open(a.objects, encoding="utf-8-sig") as f:
            obj = json.load(f)
        bases = obj.get("light_bases")
        if not isinstance(bases, list) or len(bases) != len(wins):
            sys.exit(f"refusing (the plugin is written, the objects copy is not): light_bases has "
                     f"{len(bases) if isinstance(bases, list) else 'none'} entries, the plugin {len(wins)} LIGH")
        for b in bases:
            b["lumens"] = scaled(b["lumens"], a.factor)
        obj["lumens_scale"] = a.factor
        with open(a.objects_out, "x", encoding="utf-8") as f:
            json.dump(obj, f)
        print(f"{len(bases)} light_bases scaled in {a.objects_out}, lumens_scale {a.factor}")
    return 0


def cmd_check(a):
    A, B = read(a.a), read(a.b)
    problems = []
    if len(A) != len(B):
        print(f"FAIL: sizes differ ({len(A)} vs {len(B)} bytes)")
        return 1
    ia, ib = walk(A), walk(B)
    if ia != ib:
        n = next((i for i, (x, y) in enumerate(zip(ia, ib)) if x != y), min(len(ia), len(ib)))
        print(f"FAIL: record sets differ ({len(ia)} vs {len(ib)} items; first difference at item {n}: "
              f"{ia[n] if n < len(ia) else None} vs {ib[n] if n < len(ib) else None})")
        return 1
    try:
        wins = lumens_windows(A, ia)
    except ValueError as e:
        print(f"FAIL: {e}")
        return 1
    allowed = {}
    for off, fid in wins:
        for k in range(4):
            allowed[off + k] = fid
    stray = 0
    step = 1 << 20
    for s in range(0, len(A), step):
        ca, cb = A[s:s + step], B[s:s + step]
        if ca == cb:
            continue
        for i in range(len(ca)):
            if ca[i] != cb[i] and s + i not in allowed:
                stray += 1
                if stray <= 5:
                    problems.append(f"byte 0x{s + i:X} differs outside any LIGH DAT2 lumens ({ca[i]:02X} -> {cb[i]:02X})")
    if stray > 5:
        problems.append(f"... {stray} bytes in all outside LIGH lumens")
    old, new, wrong = [], [], 0
    for off, fid in wins:
        v, = struct.unpack_from("<I", A, off)
        w, = struct.unpack_from("<I", B, off)
        old.append(v)
        new.append(w)
        if w != scaled(v, a.factor):
            wrong += 1
            if wrong <= 5:
                problems.append(f"LIGH {fid:08X}: lumens {v} -> {w}, rule gives {scaled(v, a.factor)}")
    if wrong > 5:
        problems.append(f"... {wrong} LIGH off the rule in all")
    if not wins:
        problems.append("no LIGH record")
    counts = {}
    for it in ia:
        counts[it[0]] = counts.get(it[0], 0) + 1
    print(f"records: {sum(v for k, v in counts.items() if k not in ('GRUP',))} in {counts.get('GRUP', 0)} groups, "
          f"identical count / signatures / FormIDs / flags / sizes; {len(A)} bytes both")
    print(f"LIGH {len(wins)}: lumens old {stats(old) if old else None}")
    print(f"LIGH {len(wins)}: lumens new {stats(new) if new else None} (rule max(1, round(old * {a.factor})))")
    for p in problems:
        print("  FAIL " + p)
    print("CHECK", "PASS" if not problems else "FAIL")
    return 0 if not problems else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("scale")
    p.add_argument("--in", dest="in_", required=True)
    p.add_argument("--out", required=True, help="a new file")
    p.add_argument("--factor", type=float, required=True)
    p.add_argument("--objects", default="", help="the build's objects.json")
    p.add_argument("--objects-out", default="", help="a new file: light_bases[*].lumens scaled, lumens_scale added")
    p = sub.add_parser("check")
    p.add_argument("--a", required=True, help="the original plugin")
    p.add_argument("--b", required=True, help="the patched plugin")
    p.add_argument("--factor", type=float, required=True)
    a = ap.parse_args(argv)
    return {"scale": cmd_scale, "check": cmd_check}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
