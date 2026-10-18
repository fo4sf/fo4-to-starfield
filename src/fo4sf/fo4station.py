"""Raw reads for the station classes (docs/terrain/stations.md): which Fallout 4 containers are settlement workshops
(CONT with the `workshopscript` VMAD script), which furniture is a crafting station (FURN with a WBDT bench type), and
the Starfield records the build copies from or binds to (ACTI OutpostPlayerHouseActivator's keywords and PRPS, the
vanilla benches' WBDT and keywords). Everything is read with fo4land's raw walker; no Mutagen, no game file is written.

The band exports carry a reference's base type and editor id but not the base's script, keywords or bench type, so
make_cluster.py workshops / benches read them here, and make_core64c.py check binds the written records to them.
"""
import struct

from . import fo4land

# VMAD property data sizes by type (Fallout 4 / Starfield version 6, object format 1 or 2: an object is 8 bytes either
# way); strings and arrays are length-prefixed and handled in _skip_property
_FIXED = {1: 8, 3: 4, 4: 4, 5: 1}
_ARRAYS = {11: 8, 13: 4, 14: 4, 15: 1}


def _wstring(data, pos):
    n, = struct.unpack_from("<H", data, pos)
    s = bytes(data[pos + 2:pos + 2 + n])
    if len(s) != n:
        raise ValueError("VMAD string runs past the end")
    return s.decode("cp1252", "replace"), pos + 2 + n


def _skip_property(data, pos, ptype):
    if ptype in _FIXED:
        return pos + _FIXED[ptype]
    if ptype == 2:
        return _wstring(data, pos)[1]
    if ptype in _ARRAYS:
        n, = struct.unpack_from("<I", data, pos)
        return pos + 4 + n * _ARRAYS[ptype]
    if ptype == 12:
        n, = struct.unpack_from("<I", data, pos)
        pos += 4
        for _ in range(n):
            pos = _wstring(data, pos)[1]
        return pos
    if ptype == 7:                                   # struct: member count, then members as properties
        return _skip_members(data, pos)
    if ptype == 17:                                  # array of structs
        n, = struct.unpack_from("<I", data, pos)
        pos += 4
        for _ in range(n):
            pos = _skip_members(data, pos)
        return pos
    raise ValueError(f"VMAD property type {ptype} not handled")


def _skip_members(data, pos):
    n, = struct.unpack_from("<I", data, pos)
    pos += 4
    for _ in range(n):
        _name, pos = _wstring(data, pos)
        ptype, _status = struct.unpack_from("<BB", data, pos)
        pos = _skip_property(data, pos + 2, ptype)
    return pos


def vmad_scripts(data):
    """The script names of a base record's VMAD (version, object format, script count, then per script its name,
    status and properties, which are skipped by type). [] for no VMAD. ValueError for a blob this does not parse,
    so that a workshop is never missed silently."""
    if data is None:
        return []
    data = bytes(data)
    if len(data) < 6:
        raise ValueError("VMAD shorter than its header")
    version, obj_format, count = struct.unpack_from("<HHH", data, 0)
    if version not in (5, 6) or obj_format not in (1, 2):
        raise ValueError(f"VMAD version {version} object format {obj_format} not handled")
    pos, names = 6, []
    for _ in range(count):
        name, pos = _wstring(data, pos)
        _status, nprops = struct.unpack_from("<BH", data, pos)
        pos += 3
        for _ in range(nprops):
            _pname, pos = _wstring(data, pos)
            ptype, _pstatus = struct.unpack_from("<BB", data, pos)
            pos = _skip_property(data, pos + 2, ptype)
        names.append(name)
    return names


def parse_base(typ, fields):
    """The station-relevant fields of one base record: edid, scripts (VMAD script names, or the parse error as
    "scripts_error"), keywords (KWDA form ids, file-local), wbdt (the FURN bench type byte, None without WBDT), model,
    full (the FULL string id or text), prps ([(actor value, value, curve table)], Starfield object properties)."""
    out = {"type": typ, "edid": "", "scripts": [], "keywords": [], "wbdt": None, "model": None, "full": None, "prps": []}
    for sig, d in fields:
        if sig == b"EDID":
            out["edid"] = fo4land.zstring(d)
        elif sig == b"VMAD":
            try:
                out["scripts"] = vmad_scripts(d)
            except ValueError as e:
                out["scripts_error"] = str(e)
        elif sig == b"KWDA":
            out["keywords"] = list(struct.unpack_from(f"<{len(d) // 4}I", d))
        elif sig == b"WBDT" and len(d) >= 1:
            out["wbdt"] = d[0]
        elif sig == b"MODL":
            out["model"] = fo4land.zstring(d)
        elif sig == b"FULL":
            out["full"] = struct.unpack_from("<I", d)[0] if len(d) == 4 else fo4land.zstring(d)
        elif sig == b"PRPS":
            out["prps"] = [struct.unpack_from("<IfI", d, i) for i in range(0, len(d) - 11, 12)]
    return out


def read_bases(plugin_path, ids, groups=("CONT", "FURN")):
    """{form id: parse_base(...)} for the wanted record ids inside the given top-level groups of a plugin (a master's
    own records: the ids are file-local). Compressed records are inflated by fo4land.record_data."""
    wanted = {int(i) for i in ids}
    labels = {g.encode("ascii") if isinstance(g, str) else g for g in groups}
    out = {}
    with fo4land.Plugin(plugin_path) as p:
        for item in fo4land.iter_items(p.buf, p.body, len(p.buf)):
            if item[0] != "GRUP" or item[3] not in labels:
                continue
            for typ, off, _flags, fid in fo4land.iter_items(p.buf, item[1] + 24, item[2]):
                if typ == "GRUP" or fid not in wanted:
                    continue
                out[fid] = parse_base(typ.decode("ascii"), list(fo4land.iter_subrecords(fo4land.record_data(p.buf, off))))
    return out


def has_script(base, name):
    """True when a parse_base result's VMAD names the script (case-blind)."""
    return any(s.casefold() == name.casefold() for s in base.get("scripts") or [])
