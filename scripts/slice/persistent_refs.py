"""Where a worldspace keeps its persistent references, read raw from a Starfield plugin (read-only; the merge question
of docs/slice/door-frames.md, section 3).

    python scripts/slice/persistent_refs.py <plugin.esm> --worlds LC172World,OEJP006CaveWorld [--refs 10238E,24F9CE]
           [--masters n] [--out report.json]

For each named worldspace (EditorID): the WRLD record's subrecord types, its persistent cell (the CELL directly in the
world's children group, before the exterior blocks) with its subrecords and XCLC, and every reference in it: group
(the world's persistent cell, or an exterior cell's persistent / temporary children), record flags, base, position,
subrecord types. --refs also reports where the given reference form ids (file-local, 6 hex digits; or 8 with the load
index) are, whatever world they are in. The walk follows the GRUP tree (types 1 world children, 4 / 5 exterior blocks,
6 cell children, 8 persistent children, 9 temporary children) and decompresses only the records it reports.
Pure stdlib; game data stays outside the repo.
"""
import argparse
import json
import mmap
import struct
import zlib

GROUP_NAMES = {0: "top", 1: "world children", 2: "interior block", 3: "interior subblock", 4: "exterior block",
               5: "exterior subblock", 6: "cell children", 7: "topic children", 8: "persistent children",
               9: "temporary children"}


def subrecords(data):
    """[(type, payload)] of a record's data (XXXX extended sizes handled)."""
    out, pos, big = [], 0, None
    while pos + 6 <= len(data):
        typ = data[pos:pos + 4].decode("ascii", "replace")
        n = struct.unpack_from("<H", data, pos + 4)[0]
        if typ == "XXXX":
            big = struct.unpack_from("<I", data, pos + 6)[0]
            pos += 6 + n
            continue
        if big is not None:
            n, big = big, None
        out.append((typ, bytes(data[pos + 6:pos + 6 + n])))
        pos += 6 + n
    return out


def record_data(buf, pos):
    size, flags = struct.unpack_from("<II", buf, pos + 4)
    data = buf[pos + 24:pos + 24 + size]
    if flags & 0x40000:
        data = zlib.decompress(bytes(data[4:]))
    return data


def edid(subs):
    for t, p in subs:
        if t == "EDID":
            return p.rstrip(b"\0").decode("utf-8", "replace")
    return None


def summarize_ref(buf, pos, fid, stack, cell_of):
    flags = struct.unpack_from("<I", buf, pos + 8)[0]
    subs = subrecords(record_data(buf, pos))
    d = {t: p for t, p in subs}
    out = {"formid": f"{fid:08X}", "edid": edid(subs), "record_flags": f"0x{flags:X}",
           "persistent": bool(flags & 0x400), "subrecords": [t for t, _ in subs],
           "group": GROUP_NAMES.get(stack[-1][0], str(stack[-1][0])) if stack else "",
           "cell": f"{stack[-1][1]:08X}" if stack and stack[-1][0] in (8, 9) else None}
    if out["cell"]:
        out["cell_kind"] = cell_of.get(stack[-1][1], {}).get("kind")
        out["cell_grid"] = cell_of.get(stack[-1][1], {}).get("grid")
    if "NAME" in d:
        out["base"] = f"{struct.unpack_from('<I', d['NAME'])[0]:08X}"
    if "DATA" in d and len(d["DATA"]) >= 24:
        v = struct.unpack_from("<6f", d["DATA"])
        out["pos"], out["rot"] = [round(x, 4) for x in v[:3]], [round(x, 6) for x in v[3:]]
    for t in ("XLRL", "XLRT", "XLCN", "XEMI", "XLKR", "XTEL", "XNDP", "XLOC", "XWPG", "XRGD", "XBSD"):
        if t in d:
            out.setdefault("fields", {})[t] = d[t].hex()
    return out


def walk(path, worlds=(), refs=()):
    """The report (module doc)."""
    want_worlds = {w.lower() for w in worlds}
    want_refs = {int(r, 16) & 0xFFFFFF if len(r) <= 6 else int(r, 16) for r in refs}
    rep = {"plugin": path, "worlds": {}, "refs": []}
    with open(path, "rb") as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as buf:
        hsize = struct.unpack_from("<I", buf, 4)[0]
        masters = [p.rstrip(b"\0").decode() for t, p in subrecords(buf[24:24 + hsize]) if t == "MAST"]
        rep["masters"] = masters
        local_index = len(masters)
        world_of = {}                   # WRLD form id -> EditorID (wanted ones)
        cell_of = {}                    # CELL form id -> {"kind": persistent | exterior | interior, "grid"}
        stack = []                      # (group type, label, end)
        pos = 24 + hsize
        end = len(buf)
        cur_world = None
        while pos < end:
            while stack and pos >= stack[-1][2]:
                stack.pop()
            typ = buf[pos:pos + 4]
            size = struct.unpack_from("<I", buf, pos + 4)[0]
            if typ == b"GRUP":
                label, gtype = struct.unpack_from("<II", buf, pos + 8)
                stack.append((gtype, label, pos + size))
                pos += 24
                continue
            fid = struct.unpack_from("<I", buf, pos + 12)[0]
            in_world = next((s for s in reversed(stack) if s[0] == 1), None)
            if typ == b"WRLD":
                subs = subrecords(record_data(buf, pos))
                e = edid(subs) or ""
                if e.lower() in want_worlds:
                    world_of[fid] = e
                    rep["worlds"][e] = {"formid": f"{fid:08X}", "subrecords": [t for t, _ in subs],
                                        "persistent_cell": None, "persistent_refs": [], "exterior_persistent_refs": [],
                                        "temporary_refs": 0}
            elif typ == b"CELL" and in_world is not None:
                subs = subrecords(record_data(buf, pos)) if in_world[1] in world_of else []
                d = {t: p for t, p in subs}
                exterior_block = any(s[0] in (4, 5) for s in stack)
                grid = list(struct.unpack_from("<ii", d["XCLC"])) if "XCLC" in d else None
                cell_of[fid] = {"kind": "exterior" if exterior_block else "persistent", "grid": grid}
                if in_world[1] in world_of and not exterior_block:
                    w = rep["worlds"][world_of[in_world[1]]]
                    w["persistent_cell"] = {"formid": f"{fid:08X}", "record_flags": f"0x{struct.unpack_from('<I', buf, pos + 8)[0]:X}",
                                            "subrecords": [t for t, _ in subs], "xclc": d["XCLC"].hex() if "XCLC" in d else None,
                                            "grid": grid, "raw": {t: p.hex() for t, p in subs if len(p) <= 32}}
            elif typ in (b"REFR", b"ACHR"):
                w = world_of.get(in_world[1]) if in_world else None
                local = fid & 0xFFFFFF
                hit = fid in want_refs or (local in want_refs and (fid >> 24) == local_index)
                if w is not None or hit:
                    cell_group = next((s for s in reversed(stack) if s[0] in (8, 9)), None)
                    gtype = cell_group[0] if (w is not None and cell_group is not None) else None
                    if gtype == 9:                  # the storage count: the same whether or not --refs asks for the ref
                        rep["worlds"][w]["temporary_refs"] += 1    # (Codex's review of PR #107: it dropped the hits)
                    if hit or gtype == 8:
                        r = summarize_ref(buf, pos, fid, [s for s in stack if s[0] in (1, 4, 5, 6, 8, 9)], cell_of)
                        r["world"] = w
                        if hit:
                            rep["refs"].append(r)
                        if gtype == 8:
                            key = ("persistent_refs" if cell_of.get(cell_group[1], {}).get("kind") == "persistent"
                                   else "exterior_persistent_refs")
                            rep["worlds"][w][key].append(r)
            pos += 24 + size
    return rep


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plugin")
    ap.add_argument("--worlds", default="")
    ap.add_argument("--refs", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--limit", type=int, default=12, help="persistent refs printed per world")
    a = ap.parse_args(argv)
    rep = walk(a.plugin, [w for w in a.worlds.split(",") if w], [r for r in a.refs.split(",") if r])
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(rep, f, indent=1)
    for name, w in rep["worlds"].items():
        print(f"WRLD {name} {w['formid']}: {' '.join(w['subrecords'])}")
        print(f"  persistent cell: {w['persistent_cell']}")
        print(f"  {len(w['persistent_refs'])} refs in the persistent cell, {len(w['exterior_persistent_refs'])} "
              f"persistent refs in exterior cells, {w['temporary_refs']} temporary refs")
        for r in (w["persistent_refs"] + w["exterior_persistent_refs"])[:a.limit]:
            print(f"    {r['formid']} {r.get('edid')} base {r.get('base')} {r['record_flags']} {r['group']} "
                  f"{r.get('cell_kind')} {r.get('cell_grid')} pos {r.get('pos')} {' '.join(r['subrecords'])}")
    for r in rep["refs"]:
        print(f"REF {r['formid']} {r.get('edid')} world {r.get('world')} base {r.get('base')} {r['record_flags']} "
              f"{r['group']} cell {r.get('cell')} {r.get('cell_kind')} {r.get('cell_grid')} pos {r.get('pos')} "
              f"{' '.join(r['subrecords'])} {r.get('fields', '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
