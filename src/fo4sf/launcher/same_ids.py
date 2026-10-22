"""Same ids on every PC: do two builds of the same inputs give the same FormIDs?

Level 1, bytes: every plugin of build A against the same-named plugin of build B (SHA-256). Identical bytes settle
it.
Level 2, records: for plugins that differ, a raw walk of both (TES4 header, GRUPs, records; compressed records
inflated) compares, record by record:
    the FormID set, and for every FormID its record type and editor id (EDID)   -> the ids
    the record header's version-control fields (timestamp, VC info, form version) -> metadata
    the record body                                                            -> content
and the TES4 header on its own. Two builds have the same ids when the FormID sets match, every FormID keeps its
type and editor id, and the ordered MAST entries are unchanged. A raw FormID's master index cannot be compared
across changed master tables. A difference in other metadata or content alone is an explained diff, listed with examples.
Level 3, formids.json: when both build folders carry the converter's formids.json, make_core64c.py's formids_diff
(the compare-ids tool) runs on them too, so the converter's own allocation map is checked, not just the plugin.

Verdicts: IDENTICAL (bytes), SAME_IDS (ids equal, an explained diff remains), IDS_DIFFER, INCOMPLETE (a plugin is in
only one build, or one could not be read). Only IDENTICAL and SAME_IDS exit 0.

The walker reads the header layout Fallout 4 and Starfield share: 24-byte record and GRUP headers, the compressed
flag 0x00040000 with a u32 inflated size before the zlib stream, and XXXX for subrecords over 65,535 bytes. It
needs no Mutagen and no load order (plain Python, so CI and the PC run the same code).
"""
import hashlib
import os
import struct
import zlib

from . import files

COMPRESSED = 0x00040000
VERDICT_OK = ("IDENTICAL", "SAME_IDS")


class PluginError(ValueError):
    pass


def subrecords(data):
    """[(type, bytes)] of a record body."""
    out, pos, big = [], 0, None
    while pos < len(data):
        if pos + 6 > len(data):
            raise PluginError("truncated subrecord header")
        typ = data[pos:pos + 4].decode("latin-1")
        n = struct.unpack_from("<H", data, pos + 4)[0]
        if typ == "XXXX":
            big = struct.unpack_from("<I", data, pos + 6)[0]
            pos += 6 + n
            continue
        if big is not None:
            n, big = big, None
        if pos + 6 + n > len(data):
            raise PluginError(f"truncated {typ} subrecord")
        out.append((typ, data[pos + 6:pos + 6 + n]))
        pos += 6 + n
    return out


def read_plugin(path):
    """Parsed records; tes4.subrecords.MAST retains every master's raw bytes as an ordered hex list."""
    with open(path, "rb") as f:
        raw = f.read()
    if raw[:4] != b"TES4" or len(raw) < 24:
        raise PluginError(f"{path}: not a TES4 plugin")
    records, dups, pos, tes4 = {}, [], 0, None
    while pos < len(raw):
        if pos + 24 > len(raw):
            raise PluginError(f"{path}: truncated header at {pos}")
        typ = raw[pos:pos + 4].decode("latin-1")
        size = struct.unpack_from("<I", raw, pos + 4)[0]
        if typ == "GRUP":
            if size < 24:
                raise PluginError(f"{path}: GRUP of {size} bytes at {pos}")
            pos += 24                                 # walk into the group: its contents follow sequentially
            continue
        flags, formid, vc1, version, vc2 = struct.unpack_from("<IIIHH", raw, pos + 8)
        body = raw[pos + 24:pos + 24 + size]
        if len(body) != size:
            raise PluginError(f"{path}: truncated {typ} {formid:08X}")
        pos += 24 + size
        if flags & COMPRESSED:
            if size < 4:
                raise PluginError(f"{path}: compressed {typ} {formid:08X} too short")
            try:
                body = zlib.decompress(body[4:])
            except zlib.error as e:
                raise PluginError(f"{path}: {typ} {formid:08X} does not inflate: {e}") from None
        subs = subrecords(body)
        edid = next((v.split(b"\0", 1)[0].decode("utf-8", "replace") for t, v in subs if t == "EDID"), None)
        entry = {"type": typ, "edid": edid, "flags": flags & ~COMPRESSED,
                 "meta": [vc1, version, vc2], "body_sha256": hashlib.sha256(body).hexdigest()}
        if typ == "TES4":
            header = {t: v.hex() for t, v in subs if t in ("HEDR", "CNAM", "SNAM")}
            header["MAST"] = [v.hex() for t, v in subs if t == "MAST"]
            tes4 = dict(entry, subrecords=header)
            continue
        if formid in records:
            dups.append(f"{formid:08X}")
        records[formid] = entry
    return {"tes4": tes4, "records": records, "duplicates": dups}


def compare_plugins(a_path, b_path, examples=5):
    """Record-level comparison of two plugin files: {"ids_equal", "ids", "metadata", "content", "tes4", ...}."""
    a, b = read_plugin(a_path), read_plugin(b_path)
    ra, rb = a["records"], b["records"]
    only_a, only_b = sorted(set(ra) - set(rb)), sorted(set(rb) - set(ra))
    both = sorted(set(ra) & set(rb))
    retyped = [f for f in both if ra[f]["type"] != rb[f]["type"]]
    renamed = [f for f in both if ra[f]["edid"] != rb[f]["edid"]]
    meta = [f for f in both if ra[f]["meta"] != rb[f]["meta"] or ra[f]["flags"] != rb[f]["flags"]]
    content = [f for f in both if ra[f]["body_sha256"] != rb[f]["body_sha256"]]
    # the same editor id under another FormID is the failure mode determinism is about: name it directly
    by_edid_a = {v["edid"]: k for k, v in ra.items() if v["edid"]}
    by_edid_b = {v["edid"]: k for k, v in rb.items() if v["edid"]}
    moved = sorted(e for e in set(by_edid_a) & set(by_edid_b) if by_edid_a[e] != by_edid_b[e])
    tes4 = {}
    for k in sorted(set(a["tes4"]["subrecords"]) | set(b["tes4"]["subrecords"])):
        if a["tes4"]["subrecords"].get(k) != b["tes4"]["subrecords"].get(k):
            tes4[k] = {"a": a["tes4"]["subrecords"].get(k), "b": b["tes4"]["subrecords"].get(k)}
    masters_changed = a["tes4"]["subrecords"]["MAST"] != b["tes4"]["subrecords"]["MAST"]
    # the header flags (master, light, medium) decide how the game maps the plugin's FormIDs
    flags_changed = a["tes4"]["flags"] != b["tes4"]["flags"]
    if flags_changed:
        tes4["flags"] = {"a": f"{a['tes4']['flags']:08X}", "b": f"{b['tes4']['flags']:08X}"}

    def ex(ids, f=lambda i: f"{i:08X}"):
        return [f(i) for i in ids[:examples]]
    ids_equal = not (only_a or only_b or retyped or renamed or moved or masters_changed or flags_changed
                     or a["duplicates"] or b["duplicates"])
    return {
        "ids_equal": ids_equal, "records": [len(ra), len(rb)],
        "ids": {"only_a": len(only_a), "only_b": len(only_b), "retyped": len(retyped), "renamed": len(renamed),
                "edid_moved": len(moved), "masters_changed": masters_changed, "tes4_flags_changed": flags_changed,
                "duplicates": [a["duplicates"][:examples], b["duplicates"][:examples]],
                "examples": {"only_a": ex(only_a), "only_b": ex(only_b), "retyped": ex(retyped),
                             "renamed": ex(renamed, lambda i: f"{i:08X} {ra[i]['edid']} -> {rb[i]['edid']}"),
                             "edid_moved": [f"{e}: {by_edid_a[e]:08X} -> {by_edid_b[e]:08X}" for e in moved[:examples]]}},
        "metadata": {"count": len(meta), "examples": ex(meta)},
        "content": {"count": len(content),
                    "examples": [f"{i:08X} {ra[i]['type']} {ra[i]['edid'] or ''}".strip() for i in content[:examples]]},
        "tes4": tes4,
    }


def plugin_names(root):
    return sorted(n for n in os.listdir(root) if os.path.isfile(os.path.join(root, n))
                  and n.lower().endswith(files.PLUGIN_EXT))


def formids_json_diff(a_dir, b_dir):
    """make_core64c.py's formids_diff over both folders' formids.json, or None when either has none."""
    pa, pb = os.path.join(a_dir, "formids.json"), os.path.join(b_dir, "formids.json")
    if not (os.path.isfile(pa) and os.path.isfile(pb)):
        return None
    import importlib.util
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.dirname(os.path.dirname(os.path.dirname(here)))
    spec = importlib.util.spec_from_file_location(
        "make_core64c", os.path.join(repo, "scripts", "terrain", "make_core64c.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.formids_diff(files.load_json(pa), files.load_json(pb))


def check(a_dir, b_dir, plugins=None, examples=5):
    """The full report for two build folders (plugins at their top level, as staged builds keep them)."""
    names_a, names_b = plugin_names(a_dir), plugin_names(b_dir)
    names = plugins or sorted(set(names_a) | set(names_b))
    report = {"a": os.path.abspath(a_dir), "b": os.path.abspath(b_dir), "plugins": {}}
    verdicts = []
    for n in names:
        pa, pb = os.path.join(a_dir, n), os.path.join(b_dir, n)
        if not (os.path.isfile(pa) and os.path.isfile(pb)):
            report["plugins"][n] = {"verdict": "INCOMPLETE", "why": f"only in {'a' if os.path.isfile(pa) else 'b'}"}
            verdicts.append("INCOMPLETE")
            continue
        ha, hb = files.sha256(pa), files.sha256(pb)
        entry = {"sha256": [ha, hb]}
        if ha == hb:
            entry["verdict"] = "IDENTICAL"
        else:
            try:
                cmp = compare_plugins(pa, pb, examples)
            except PluginError as e:
                entry.update(verdict="INCOMPLETE", why=str(e))
            else:
                entry.update(cmp, verdict="SAME_IDS" if cmp["ids_equal"] else "IDS_DIFFER")
        report["plugins"][n] = entry
        verdicts.append(entry["verdict"])
    fj = formids_json_diff(a_dir, b_dir)
    if fj is not None:
        report["formids_json"] = fj
        if any(v["status"] != "identical" for v in fj.values()):
            verdicts.append("IDS_DIFFER")
    if not verdicts:
        verdicts.append("INCOMPLETE")
    order = ("IDENTICAL", "SAME_IDS", "INCOMPLETE", "IDS_DIFFER")
    report["verdict"] = max(verdicts, key=order.index)
    return report


def summary_lines(report):
    out = [f"same-ids: {report['verdict']}  ({report['a']}  vs  {report['b']})"]
    for n, e in report["plugins"].items():
        line = f"  {n:<32} {e['verdict']}"
        if e["verdict"] in ("SAME_IDS", "IDS_DIFFER"):
            i = e["ids"]
            line += (f": {e['records'][0]:,} / {e['records'][1]:,} records; ids only-a {i['only_a']}, only-b "
                     f"{i['only_b']}, retyped {i['retyped']}, renamed {i['renamed']}, edid moved {i['edid_moved']}; "
                     f"metadata {e['metadata']['count']}, content {e['content']['count']}"
                     + (f"; TES4 {sorted(e['tes4'])}" if e["tes4"] else ""))
        elif e.get("why"):
            line += f": {e['why']}"
        out.append(line)
    for k, d in (report.get("formids_json") or {}).items():
        out.append(f"  formids.json {k:<14} {d['status']}")
    return out
