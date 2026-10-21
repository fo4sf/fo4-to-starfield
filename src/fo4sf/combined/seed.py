"""Draft a combined-core pack from the player's own Fallout 4 plugins (G7 seed tables).

Reads LCTN (locations), FACT (factions), KYWD and LCRT (names for keywords and location ref types) from
Fallout4.esm and its DLC, then the REFR map markers the locations name, and writes a pack draft plus a report of
keyword and ref-type counts. Read-only, stdlib only, runs on the PC that owns the game; nothing it reads or writes
is shipped (scripts/guard.py). seedpack.py turns the draft into a pack that runs.

Field layouts, from xEdit dev-4.1.6 wbDefinitionsFO4.pas: LCTN has EDID; LCSR/ACSR arrays of 16-byte structs
(LCRT formid, ref formid, world/cell formid, grid y s16, grid x s16); ACPR/LCPR are 12-byte structs without the
LCRT formid (ref, world/cell, grid y s16, grid x s16; not read); KSIZ/KWDA keywords; PNAM parent location; MNAM
world location marker ref (the form id of a REFR). REFR DATA is Position x, y, z float32 then Rotation x, y, z
float32 (24 bytes). From wbDefinitionsCommon.pas: FACT XNAM is (faction formid,
modifier s32, group combat reaction u32: 0 neutral, 1 enemy, 2 ally, 3 friend). Container layout (xEdit
wbImplementation.pas, UESP "Mod File Format"): 24-byte record header (sig, data size u32, flags u32, formid u32,
8 bytes version control); 24-byte GRUP header (sig, group size u32 incl. header, label, type s32, 8 bytes); a
group of type 1 is a worldspace's World Children, labelled with the WRLD form id, and that is where a marker's
worldspace comes from; a compressed record's data is a u32 decompressed size followed by a zlib stream; an XXXX
subrecord carries the u32 size of the next subrecord. A formid's top byte indexes the plugin's MAST list; beyond
it, the plugin itself.

Markers are read in a second pass that enters only the WRLD tree and decodes only the REFR records some LCTN's
MNAM names (the rest cost one header read each), so a several-hundred-MB master stays cheap.

Which keywords or ref types mark a settlement or a faction's place is NOT assumed: CLASSIFY holds regex
guesses that the first real run's report (which lists every keyword and ref type used by locations, with counts)
supports; see the note at CLASSIFY. A supported hypothesis, not proof.

The draft keeps evidence next to each entry (form, parent, keywords, ref types, hints, marker position); to_pack()
strips it to the pack shape so that, once a human fills holders and faction homes, pack.validate_pack accepts it;
seedpack.generate() fills them by rules instead.
"""
from __future__ import annotations

import json
import math
import mmap
import os
import re
import struct
import zlib
from collections import Counter

COMPRESSED = 0x00040000
DELETED = 0x00000020
WANTED = (b"KYWD", b"LCRT", b"FACT", b"LCTN")
MARKER_TYPES = (b"REFR",)      # second pass: map marker references named by LCTN MNAM
MARKER_GROUPS = (b"WRLD",)     # entered at the top level in that pass; everything else is skipped whole
REACTIONS = ("neutral", "enemy", "ally", "friend")
_REC = struct.Struct("<4sIII")
_GRP = struct.Struct("<4sI4si")
_U32 = struct.Struct("<I")
_XNAM = struct.Struct("<IiI")
_POS = struct.Struct("<fff")
_HDR = 24

# Regex guesses on editor ids. The first real run (owner's PC, 2026-10-21, Fallout4.esm + DLCRobot.esm +
# DLCworkshop01.esm; the other four DLC were not installed) supports them: 397 locations, 38 settlement candidates,
# 84 base candidates, 710 factions; location keyword counts included LocTypeWorkshop 30, LocTypeWorkshopSettlement
# 30, LocTypeSettlement 24, LocEncRaiders 39, LocEncSuperMutants 24, LocEncGhouls 27; ref type WorkshopRefType 31.
# A supported hypothesis, not proof: which of those 38 are the places a player would call settlements is unchecked.
CLASSIFY = {
    "settlement_ref_type": r"workshop",
    "settlement_keyword": r"settlement|workshop",
    "faction_keyword": r"raider|gunner|supermutant|minutemen|brotherhood|institute|railroad|triggerm|atom",
}
# Placeholder mapping from a FACT reaction to the model's -100..100 relation, for to_pack(); to tune.
REACTION_RELATION = {"enemy": -80, "neutral": 0, "friend": 40, "ally": 80}


class Problems:
    """Counts of odd input (truncated subrecords, bad zlib, ...) that the report carries instead of crashing."""

    def __init__(self):
        self.counts = Counter()

    def note(self, what: str) -> None:
        self.counts[what] += 1


def _subrecords(data, problems: Problems):
    p, big = 0, None
    while p + 6 <= len(data):
        sig = data[p:p + 4]
        size = struct.unpack_from("<H", data, p + 4)[0]
        p += 6
        if big is not None:
            size, big = big, None
        if sig == b"XXXX":
            if size == 4 and p + 4 <= len(data):
                big = _U32.unpack_from(data, p)[0]
            else:
                problems.note("bad XXXX subrecord")
            p += size
            continue
        if p + size > len(data):
            problems.note("truncated subrecord")
        yield sig, data[p:p + size]
        p += size
    if p != len(data):
        problems.note("trailing bytes after subrecords")


def _record_data(buf, off: int, size: int, flags: int, problems: Problems):
    raw = buf[off + _HDR:off + _HDR + size]
    if not flags & COMPRESSED:
        return raw
    if len(raw) < 4:
        problems.note("compressed record too short")
        return b""
    want = _U32.unpack_from(raw)[0]
    try:
        data = zlib.decompress(raw[4:])
    except zlib.error:
        problems.note("bad zlib stream")
        return b""
    if len(data) != want:
        problems.note("decompressed size mismatch")
    return data


def _records(buf, start: int, end: int, wanted, problems: Problems, top: bool, enter=None, select=None,
             world: int | None = None):
    """Yield (type, formid, flags, data, world) for wanted records between start and end, walking nested groups.

    At the top level, groups whose label is not in `enter` (default: the wanted types; type-0 groups are labelled
    with their record type) are skipped whole, so CELL and WRLD trees in a several-hundred-MB master cost one
    header read each. `select(formid)`, when given, decides which wanted records are decoded at all; the others
    cost one header read. `world` is the WRLD form id of the enclosing World Children group (type 1), else None.
    """
    enter = wanted if enter is None else enter
    off = start
    while off + _HDR <= end:
        typ = buf[off:off + 4]
        if typ == b"GRUP":
            _t, gsize, label, gtype = _GRP.unpack_from(buf, off)
            if gsize < _HDR:
                problems.note("bad group size")
                return
            if not (top and gtype == 0 and label not in enter):
                inner = _U32.unpack_from(label)[0] if gtype == 1 else world
                yield from _records(buf, off + _HDR, min(off + gsize, end), wanted, problems, False, enter, select,
                                    inner)
            off += gsize
            continue
        _t, size, flags, fid = _REC.unpack_from(buf, off)
        if off + _HDR + size > end:
            problems.note("truncated record")
            size = max(0, end - off - _HDR)
        if typ in wanted and (select is None or select(fid)):
            # a deleted record is yielded with empty data so read() can drop an earlier plugin's record
            data = b"" if flags & DELETED else _record_data(buf, off, size, flags, problems)
            yield typ, fid, flags, data, world
        off += _HDR + size


def _zstring(b) -> str:
    return bytes(b).split(b"\0", 1)[0].decode("cp1252", "replace")


class Source:
    """One plugin, mapped read-only. Form ids become "owner.esm:XXXXXX" keys (owner lower-cased: Windows names)."""

    def __init__(self, path: str):
        self.path = path
        self.name = os.path.basename(path).lower()
        self.problems = Problems()
        self._f = open(path, "rb")
        try:
            self.buf = mmap.mmap(self._f.fileno(), 0, access=mmap.ACCESS_READ)
        except ValueError:
            self._f.close()
            raise ValueError(f"{path}: empty file, not a plugin")
        if len(self.buf) < _HDR or self.buf[:4] != b"TES4":
            self.close()
            raise ValueError(f"{path}: not a plugin (no TES4 header)")
        _t, size, _flags, _fid = _REC.unpack_from(self.buf, 0)
        hdr = self.buf[_HDR:_HDR + size]
        self.masters = [_zstring(d).lower() for s, d in _subrecords(hdr, self.problems) if s == b"MAST"]
        self.body = _HDR + size

    def close(self) -> None:
        self.buf.close()
        self._f.close()

    def key(self, fid: int) -> str:
        idx = fid >> 24
        owner = self.masters[idx] if idx < len(self.masters) else self.name
        return f"{owner}:{fid & 0xFFFFFF:06X}"

    def fid(self, key: str) -> int | None:
        """The raw form id this plugin would use for a key, or None when the key's owner is not in its load list."""
        owner, _, low = key.rpartition(":")
        owners = self.masters + [self.name]
        if owner not in owners:
            return None
        return (owners.index(owner) << 24) | int(low, 16)

    def records(self, wanted=WANTED, enter=None, select=None):
        return _records(self.buf, self.body, len(self.buf), wanted, self.problems, True, enter, select)


def _u32s(d, problems: Problems, what: str) -> list[int]:
    if len(d) % 4:
        problems.note(f"truncated {what}")
    n = len(d) // 4
    return list(struct.unpack_from(f"<{n}I", d)) if n else []


def _location(src: Source, fields, edid: str) -> dict:
    loc = {"edid": edid, "parent": None, "keywords": [], "ref_types": [], "marker": None}
    ksiz = None
    for s, d in fields:
        if s == b"PNAM" and len(d) >= 4:
            loc["parent"] = src.key(_U32.unpack_from(d)[0])
        elif s == b"KSIZ" and len(d) >= 4:
            ksiz = _U32.unpack_from(d)[0]
        elif s == b"KWDA":
            loc["keywords"] = [src.key(v) for v in _u32s(d, src.problems, "KWDA")]
        elif s in (b"LCSR", b"ACSR"):
            if len(d) % 16:
                src.problems.note(f"truncated {s.decode('ascii')}")
            for i in range(0, len(d) - len(d) % 16, 16):   # LCRT, ref, world/cell, y s16, x s16
                loc["ref_types"].append(src.key(_U32.unpack_from(d, i)[0]))
        elif s == b"MNAM" and len(d) >= 4:
            loc["marker"] = src.key(_U32.unpack_from(d)[0])
    if ksiz is not None and ksiz != len(loc["keywords"]):
        src.problems.note("KSIZ does not match KWDA")
    return loc


def _faction(src: Source, fields, edid: str) -> dict:
    rel = []
    for s, d in fields:
        if s != b"XNAM":
            continue
        if len(d) < _XNAM.size:
            src.problems.note("truncated XNAM")
            continue
        other, mod, react = _XNAM.unpack_from(d)
        rel.append({"faction": src.key(other), "modifier": mod, "reaction": react})
    return {"edid": edid, "relations": rel}


def _marker(src: Source, fields, world: int | None) -> dict | None:
    """{x, y, world} from a REFR's DATA (position floats), or None (and a problem) when it is unusable."""
    data = next((d for s, d in fields if s == b"DATA"), None)
    if data is None:
        src.problems.note("REFR without DATA")
        return None
    if len(data) < _POS.size:
        src.problems.note("truncated REFR DATA")
        return None
    x, y, _z = _POS.unpack_from(data)
    if not (math.isfinite(x) and math.isfinite(y)):
        src.problems.note("non-finite REFR position")
        return None
    return {"x": x, "y": y, "world": src.key(world) if world is not None else None}


def _read_markers(paths, wanted_refs: set, problems: Counter) -> dict:
    """Second pass over the plugins: positions of the REFR records whose keys are in wanted_refs, in load order
    (a later plugin's record wins, a deleted one removes), entering only the WRLD trees."""
    markers = {}
    for path in paths:
        src = Source(path)
        try:
            raw = {f for f in (src.fid(k) for k in wanted_refs) if f is not None}
            if raw:
                for typ, fid, flags, data, world in src.records(MARKER_TYPES, MARKER_GROUPS, raw.__contains__):
                    k = src.key(fid)
                    if flags & DELETED:
                        markers.pop(k, None)
                        continue
                    pos = _marker(src, list(_subrecords(data, src.problems)), world)
                    if pos is None:
                        markers.pop(k, None)
                    else:
                        markers[k] = pos
        finally:
            src.close()
        problems.update({f"{src.name}: {w}": n for w, n in src.problems.counts.items()})
    return markers


def read(paths) -> dict:
    """Read the plugins in load order. A later plugin's record of the same form id overrides the earlier one;
    a record flagged DELETED removes it (and counts as an override when an earlier plugin defined it).
    "markers" maps the REFR keys the locations' MNAMs name to {x, y, world} where the REFR was found."""
    names, locs, facts = {}, {}, {}
    counts, overrides, deleted, compressed, problems, plugins = Counter(), 0, 0, 0, Counter(), []
    for path in paths:
        src = Source(path)
        try:
            for typ, fid, flags, data, _world in src.records():
                k = src.key(fid)
                if flags & DELETED:
                    deleted += 1
                    overrides += k in names
                    names.pop(k, None)
                    locs.pop(k, None)
                    facts.pop(k, None)
                    continue
                fields = list(_subrecords(data, src.problems))
                edid = next((_zstring(d) for s, d in fields if s == b"EDID"), "")
                counts[typ.decode("ascii")] += 1
                compressed += bool(flags & COMPRESSED)
                if k in names:
                    overrides += 1
                names[k] = edid
                if typ == b"LCTN":
                    locs[k] = _location(src, fields, edid)
                elif typ == b"FACT":
                    facts[k] = _faction(src, fields, edid)
        finally:
            src.close()
        plugins.append({"name": src.name, "masters": src.masters})
        problems.update({f"{src.name}: {w}": n for w, n in src.problems.counts.items()})
    wanted_refs = {loc["marker"] for loc in locs.values() if loc["marker"]}
    markers = _read_markers(paths, wanted_refs, problems) if wanted_refs else {}
    return {"names": names, "locations": locs, "factions": facts, "plugins": plugins, "markers": markers,
            "record_counts": dict(counts), "overrides": overrides, "deleted": deleted,
            "compressed": compressed, "problems": dict(problems)}


def _root(locs: dict, k: str) -> str:
    seen = set()
    while True:
        p = locs.get(k, {}).get("parent")
        if not p or p not in locs or p in seen:    # cycles happen only in broken data; stop there
            return k
        seen.add(k)
        k = p


def _unique_ids(keys, label) -> dict:
    """Editor ids as ids, with the form key appended where two records share one (packs need unique ids)."""
    by_name = Counter(label(k) for k in keys)
    return {k: label(k) if by_name[label(k)] == 1 else f"{label(k)}@{k}" for k in keys}


def build(data: dict) -> tuple[dict, dict]:
    """Turn read() output into (draft, report). Deterministic: everything is walked in sorted key order."""
    names, locs, facts = data["names"], data["locations"], data["factions"]
    markers = data.get("markers", {})
    rx = {k: re.compile(v, re.I) for k, v in CLASSIFY.items()}
    kw_counts, rt_counts, regions, unresolved = Counter(), Counter(), Counter(), Counter()

    def name(k):
        if k in names and names[k]:
            return names[k]
        unresolved[k] += 1
        return k

    loc_ids = _unique_ids(sorted(locs), lambda k: locs[k]["edid"] or k)
    fac_ids = _unique_ids(sorted(facts), lambda k: facts[k]["edid"] or k)
    places = []
    for k in sorted(locs):
        loc = locs[k]
        kws = sorted({name(x) for x in loc["keywords"]})
        rts = sorted({name(x) for x in loc["ref_types"]})
        kw_counts.update(kws)
        rt_counts.update(rts)
        hints = [w for w in kws if rx["faction_keyword"].search(w)]
        settlement = any(rx["settlement_ref_type"].search(r) for r in rts) or any(
            rx["settlement_keyword"].search(w) for w in kws)
        # UNVERIFIED: a non-settlement place with a faction keyword is drafted as that faction's base.
        kind = "settlement" if settlement else "base" if hints else "landmark"
        region = name(_root(locs, k))
        regions[region] += 1
        places.append({
            "id": loc_ids[k], "region": region, "kind": kind, "form": k,
            "parent": loc_ids.get(loc["parent"], loc["parent"]) if loc["parent"] else None,
            "keywords": kws, "ref_types": rts, "faction_hints": hints, "has_marker": loc["marker"] is not None,
            "marker": markers.get(loc["marker"]) if loc["marker"] else None,
        })
    factions = []
    for k in sorted(facts):
        rel = {}
        for r in facts[k]["relations"]:
            other = fac_ids.get(r["faction"]) or name(r["faction"])
            rel[other] = {"modifier": r["modifier"],
                          "reaction": REACTIONS[r["reaction"]] if r["reaction"] < len(REACTIONS) else r["reaction"]}
        factions.append({"id": fac_ids[k], "form": k, "relations": rel})
    draft = {"draft": True, "source_plugins": [p["name"] for p in data["plugins"]],
             "places": places, "factions": factions}
    report = {
        "plugins": data["plugins"], "record_counts": data["record_counts"], "overrides": data["overrides"],
        "deleted_records": data["deleted"], "compressed_records": data["compressed"], "problems": data["problems"],
        "locations": len(places), "settlement_candidates": sum(p["kind"] == "settlement" for p in places),
        "base_candidates": sum(p["kind"] == "base" for p in places), "factions": len(factions),
        "markers_found": sum(p["marker"] is not None for p in places),
        "markers_missing": sum(p["has_marker"] and p["marker"] is None for p in places),
        "regions": dict(regions.most_common()), "unresolved_references": dict(unresolved.most_common()),
        "classify_rules": CLASSIFY,
        "location_keywords": dict(kw_counts.most_common()), "location_ref_types": dict(rt_counts.most_common()),
    }
    return draft, report


def to_pack(draft: dict) -> dict:
    """The pack-shaped part of a draft: holders and faction homes are left for a human to fill (seedpack.generate
    fills them by rules instead).

    Places pass pack.validate_pack as they are; each faction fails only on its empty home until filled.
    Relations keep only factions in the draft and map reactions through REACTION_RELATION (placeholder).
    """
    known = {f["id"] for f in draft["factions"]}
    places = [{"id": p["id"], "region": p["region"], "kind": p["kind"], "holder": None} for p in draft["places"]]
    factions = []
    for f in draft["factions"]:
        rel = {o: REACTION_RELATION.get(r["reaction"], 0) for o, r in f["relations"].items() if o in known}
        factions.append({"id": f["id"], "strength": 0, "home": "", "relations": rel})
    return {"places": places, "factions": factions}


def write(out_dir: str, draft: dict, report: dict) -> dict:
    """Write the draft and report into out_dir; return the two paths."""
    os.makedirs(out_dir, exist_ok=True)
    paths = {"draft": os.path.join(out_dir, "commonwealth_seed.draft.json"),
             "report": os.path.join(out_dir, "seed_report.json")}
    with open(paths["draft"], "w", encoding="utf-8") as f:
        json.dump(draft, f, indent=1, sort_keys=True)
    with open(paths["report"], "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1)
    return paths


def seed(out_dir: str, paths) -> dict:
    """Read the plugins, write draft and report, return the report."""
    draft, report = build(read(paths))
    write(out_dir, draft, report)
    return report
