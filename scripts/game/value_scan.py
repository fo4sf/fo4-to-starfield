"""Find a 4-byte value (by default the float 0.02, bits 0x3ca3d70a: the index every Red Rocket crash reads) in any file.

    python scripts/game/value_scan.py <file or folder> [...] [--float 0.02 | --hex 3ca3d70a] [--ext .mesh,.esm]
        [--top 20] [--json <out.json>]

Plugins (a TES4 header: .esm, .esp, .esl) are walked record by record, compressed records included, and each hit is
named by record type, form id, editor id and field (subrecord) with its offset in the field. Every other file is
scanned as raw bytes (.mesh geometry, .nif, materials, animations, ...); hits are counted with their first offsets.
Archives (.ba2) are not opened: scan the loose staging folder instead. A hit is the value's bytes, at any alignment;
whether the game reads them as that value is for the reader to judge. Read-only, except --json, which writes a new
file. docs/spikes/red-rocket-crash-bisect.md.
"""
import argparse
import json
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))
from fo4sf import fo4land  # noqa: E402


def offsets(data, needle):
    out, i = [], data.find(needle)
    while i != -1:
        out.append(i)
        i = data.find(needle, i + 1)
    return out


def items(buf, start, end):
    """Yield ('GRUP', off, group end) or (type, off, form id) in [start, end), refusing anything that overruns it."""
    off = start
    while off < end:
        if off + 24 > end:
            raise ValueError(f"truncated item header at {off}")
        typ, size, _flags, fid = struct.unpack_from("<4sIII", buf, off)
        if typ == b"GRUP":
            if size < 24 or off + size > end:
                raise ValueError(f"group at {off} runs past its container ({off + size} > {end})")
            yield "GRUP", off, off + size
            off += size
        else:
            if off + 24 + size > end:
                raise ValueError(f"{typ.decode('ascii', 'replace')} {fid:08X} at {off} runs past its container")
            yield typ, off, fid
            off += 24 + size


def plugin_hits(path, needle):
    """[{type, form_id, edid, field, at}] for every field of every record holding needle."""
    hits = []
    with fo4land.Plugin(path) as p:
        if p.body > len(p.buf):
            raise ValueError("truncated plugin: the TES4 header runs past the end of the file")
        stack = [(p.body, len(p.buf))]
        while stack:
            start, end = stack.pop()
            for item in items(p.buf, start, end):
                if item[0] == "GRUP":
                    stack.append((item[1] + 24, item[2]))
                    continue
                typ, off, fid = item
                data = fo4land.record_data(p.buf, off)
                if needle not in data:
                    continue
                fields = list(fo4land.iter_subrecords(data))
                edid = next((fo4land.zstring(d) for sig, d in fields if sig == b"EDID"), "")
                for sig, d in fields:
                    for at in offsets(d, needle):
                        hits.append({"type": typ.decode("ascii", "replace"), "form_id": f"{fid:08X}", "edid": edid,
                                     "field": sig.decode("ascii", "replace"), "at": at, "field_size": len(d)})
    return hits


def is_plugin(path):
    with open(path, "rb") as f:
        return f.read(4) == b"TES4"


def scan_file(path, needle):
    if path.lower().endswith(".ba2"):
        return {"file": path, "skipped": "archive: scan the loose staging folder"}
    if is_plugin(path):
        hits = plugin_hits(path, needle)
        return {"file": path, "plugin": True, "count": len(hits), "hits": hits}
    with open(path, "rb") as f:
        data = f.read()
    found = offsets(data, needle)
    return {"file": path, "count": len(found), "offsets": found[:16]}


def _raise(error):
    raise error


def walk(paths, exts):
    """Every file under the given paths. A missing path or an unreadable folder raises: an empty scan of the wrong place
    must not read as "the value is absent"."""
    for p in paths:
        if os.path.isfile(p):
            yield p
            continue
        if not os.path.isdir(p):
            raise FileNotFoundError(f"no such file or folder: {p}")
        for root, _dirs, names in os.walk(p, onerror=_raise):
            for n in sorted(names):
                if not exts or os.path.splitext(n)[1].lower() in exts:
                    yield os.path.join(root, n)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("paths", nargs="+")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--float", type=float, default=0.02, help="a float32 value (default 0.02)")
    g.add_argument("--hex", default="", help="the value's 32-bit pattern as hex, for example 3ca3d70a")
    ap.add_argument("--ext", default="", help="comma-separated extensions to scan in folders (default: all files)")
    ap.add_argument("--top", type=int, default=20, help="hits to print per plugin")
    ap.add_argument("--json", default="")
    a = ap.parse_args(argv)
    needle = struct.pack("<I", int(a.hex, 16)) if a.hex else struct.pack("<f", a.float)
    exts = {e.strip().lower() if e.strip().startswith(".") else "." + e.strip().lower()
            for e in a.ext.split(",") if e.strip()}
    results, scanned, errors = [], 0, 0
    try:
        files = list(walk(a.paths, exts))
    except OSError as e:
        sys.exit(f"value_scan: {e}")
    for path in files:
        try:
            r = scan_file(path, needle)
        except Exception as e:  # noqa: BLE001  (a damaged file or record must not stop the scan)
            r = {"file": path, "error": f"{type(e).__name__}: {e}"}
        scanned += 1
        if "error" in r:
            errors += 1
            print(f"{path}: {r['error']}")
            results.append(r)
        elif r.get("skipped"):
            print(f"{path}: skipped ({r['skipped']})")
        elif r["count"]:
            results.append(r)
            if r.get("plugin"):
                print(f"{path}: {r['count']} field hit(s)")
                for h in r["hits"][:a.top]:
                    print(f"  {h['type']} {h['form_id']} {h['edid'] or '-'} {h['field']}+{h['at']} (field {h['field_size']} bytes)")
            else:
                print(f"{path}: {r['count']} hit(s) at {', '.join(str(o) for o in r['offsets'])}")
    hit_files = sum(1 for r in results if r.get("count"))
    print(f"{scanned} files scanned, {hit_files} hold 0x{struct.unpack('<I', needle)[0]:08x}, {errors} unreadable")
    if a.json:
        with open(a.json, "x", encoding="utf-8") as f:
            json.dump({"value": f"0x{struct.unpack('<I', needle)[0]:08x}", "scanned": scanned, "results": results}, f,
                      indent=1)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
