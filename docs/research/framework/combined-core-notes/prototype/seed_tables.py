"""G7: draft Commonwealth seed tables for the combined core, read from the player's own plugins.

Reads LCTN (locations), FACT (factions), KYWD and LCRT (to name keywords and location ref
types) from Fallout4.esm and its DLC, and writes a draft pack for worldstate.load_pack plus a
report of keyword and ref-type counts. Read-only; stdlib only; nothing of the game's is shipped
(the output stays on the PC that ran it).

Field layouts from xEdit dev-4.1.6 wbDefinitionsFO4.pas (LCTN: EDID, LCSR/ACSR special
references [LCRT, ref, world/cell, y, x], KSIZ/KWDA keywords, PNAM parent location, MNAM world
marker) and wbDefinitionsCommon.pas (FACT XNAM: faction, modifier s32, group combat reaction
u32 0 neutral 1 enemy 2 ally 3 friend).

Which keywords or ref types mark a settlement or a faction's place is NOT assumed: CLASSIFY
holds regex guesses to confirm against the first real run's report, which lists every
keyword and ref type used by locations with counts.

Usage: python3 seed_tables.py OUT_DIR Fallout4.esm [DLCRobot.esm ...]
"""
from __future__ import annotations

import json
import os
import re
import struct
import sys
import zlib
from collections import Counter

COMPRESSED = 0x00040000
_REC = struct.Struct("<4sIII")
_GRP = struct.Struct("<4sI4si")

# Regex guesses on editor ids, to be confirmed or replaced from the report (unverified).
CLASSIFY = {
    "settlement_ref_type": r"workshop",
    "settlement_keyword": r"settlement|workshop",
    "faction_keyword": r"raider|gunner|supermutant|minutemen|brotherhood|institute|railroad|triggerm|atom",
}


def _subrecords(data):
    p, big = 0, None
    while p + 6 <= len(data):
        sig = data[p:p + 4]
        size = struct.unpack_from("<H", data, p + 4)[0]
        p += 6
        if big is not None:
            size, big = big, None
        if sig == b"XXXX":
            big = struct.unpack_from("<I", data, p)[0]
            p += size
            continue
        yield sig, data[p:p + size]
        p += size


def _records(buf, start, end, wanted):
    """Yield (type, form id, fields) for records of the wanted types, walking nested groups."""
    off = start
    while off + 24 <= end:
        typ = buf[off:off + 4]
        if typ == b"GRUP":
            _t, gsize, label, _gtype = _GRP.unpack_from(buf, off)
            yield from _records(buf, off + 24, off + gsize, wanted)
            off += gsize
            continue
        _t, size, flags, fid = _REC.unpack_from(buf, off)
        if typ in wanted:
            raw = buf[off + 24:off + 24 + size]
            data = zlib.decompress(raw[4:]) if flags & COMPRESSED else raw
            yield typ.decode("ascii"), fid, list(_subrecords(data))
        off += 24 + size


def _zstring(b):
    return b.split(b"\0", 1)[0].decode("cp1252", "replace")


class Source:
    """One plugin: its name, masters and records. Form ids become (plugin, low 24 bits)."""

    def __init__(self, path):
        self.name = os.path.basename(path)
        with open(path, "rb") as f:
            self.buf = f.read()
        typ, size, _flags, _fid = _REC.unpack_from(self.buf, 0)
        if typ != b"TES4":
            raise ValueError(f"{path}: not a plugin")
        self.masters = [_zstring(d) for s, d in _subrecords(self.buf[24:24 + size]) if s == b"MAST"]
        self.body = 24 + size

    def key(self, fid):
        idx = fid >> 24
        owner = self.masters[idx] if idx < len(self.masters) else self.name
        return f"{owner}:{fid & 0xFFFFFF:06X}"

    def records(self, *types):
        return _records(self.buf, self.body, len(self.buf), {t.encode() for t in types})


def read(paths):
    names, locs, facts = {}, {}, {}
    for path in paths:
        src = Source(path)
        for typ, fid, fields in src.records("KYWD", "LCRT", "LCTN", "FACT"):
            k = src.key(fid)
            edid = next((_zstring(d) for s, d in fields if s == b"EDID"), "")
            names[k] = edid
            if typ == "LCTN":
                loc = {"edid": edid, "parent": None, "keywords": [], "ref_types": [], "marker": None}
                for s, d in fields:
                    if s == b"PNAM" and len(d) >= 4:
                        loc["parent"] = src.key(struct.unpack_from("<I", d)[0])
                    elif s == b"KWDA":
                        loc["keywords"] = [src.key(v) for v in struct.unpack_from(f"<{len(d) // 4}I", d)]
                    elif s in (b"LCSR", b"ACSR"):
                        for i in range(0, len(d) - len(d) % 16, 16):   # LCRT, ref, cell, y s16, x s16
                            loc["ref_types"].append(src.key(struct.unpack_from("<I", d, i)[0]))
                    elif s == b"MNAM" and len(d) >= 4:
                        loc["marker"] = src.key(struct.unpack_from("<I", d)[0])
                locs[k] = loc   # a later plugin's override wins
            elif typ == "FACT":
                rel = []
                for s, d in fields:
                    if s == b"XNAM" and len(d) >= 12:
                        other, mod, react = struct.unpack_from("<IiI", d)
                        rel.append({"faction": src.key(other), "modifier": mod, "reaction": react})
                facts[k] = {"edid": edid, "relations": rel}
    return names, locs, facts


def _root(locs, k, depth=0):
    p = locs.get(k, {}).get("parent")
    return k if not p or p not in locs or depth > 32 else _root(locs, p, depth + 1)


def build(names, locs, facts):
    rx = {k: re.compile(v, re.I) for k, v in CLASSIFY.items()}
    kw_counts, rt_counts = Counter(), Counter()
    places = []
    for k in sorted(locs):
        loc = locs[k]
        kws = sorted({names.get(x, x) for x in loc["keywords"]})
        rts = sorted({names.get(x, x) for x in loc["ref_types"]})
        kw_counts.update(kws)
        rt_counts.update(rts)
        settlement = any(rx["settlement_ref_type"].search(r) for r in rts) or any(
            rx["settlement_keyword"].search(w) for w in kws)
        places.append({
            "id": loc["edid"] or k, "form": k, "region": names.get(_root(locs, k), "unknown"),
            "kind": "settlement" if settlement else "landmark",
            "parent": names.get(loc["parent"]) if loc["parent"] else None,
            "faction_hints": [w for w in kws if rx["faction_keyword"].search(w)],
            "keywords": kws, "ref_types": rts, "has_marker": loc["marker"] is not None,
        })
    factions = []
    for k in sorted(facts):
        f = facts[k]
        factions.append({"id": f["edid"] or k, "form": k, "relations": {
            names.get(r["faction"], r["faction"]): {"modifier": r["modifier"],
                                                    "reaction": ("neutral", "enemy", "ally", "friend")[r["reaction"]]
                                                    if r["reaction"] < 4 else r["reaction"]}
            for r in f["relations"]}})
    report = {
        "locations": len(places), "settlement_candidates": sum(p["kind"] == "settlement" for p in places),
        "factions": len(factions), "classify_rules": CLASSIFY,
        "location_keywords": dict(kw_counts.most_common()), "location_ref_types": dict(rt_counts.most_common()),
    }
    return {"places": places, "factions": factions}, report


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    out, paths = argv[1], argv[2:]
    os.makedirs(out, exist_ok=True)
    pack, report = build(*read(paths))
    with open(os.path.join(out, "commonwealth_seed.draft.json"), "w", encoding="utf-8") as f:
        json.dump(pack, f, indent=1, sort_keys=True)
    with open(os.path.join(out, "seed_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1)
    print(json.dumps({k: report[k] for k in ("locations", "settlement_candidates", "factions")}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
