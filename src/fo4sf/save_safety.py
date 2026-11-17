"""Binary save-compatibility inspector across Starfield/FO4SF plugin & script builds.

Checks the three contract surfaces that Starfield bakes into `.sfs` savegames:
  1. Plugin presence and relative load-order indices (`TES4` / `Plugins.txt` / `bundle_plan.json`).
  2. Papyrus property bindings in record/quest/alias `VMAD` subrecords and compiled `.pex` (`0xFA57C0DE`) scripts
     (loose `Data/Scripts/*.pex` and packed `<plugin> - Main.ba2` archives).
  3. Quest (`QUST`) records, stage `INDX` values, and `ALST`/`ALLS` alias counts & IDs.
"""

from __future__ import annotations

import base64
import json
import mmap
import os
import re
import struct
import zlib
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .ba2 import Ba2, Ba2Error
from .planet import esm

PEX_MAGIC_LE = 0xFA57C0DE
PEX_MAGIC_BE = 0xDEC057FA

VMAD_PROP_TYPES = {
    1: "Object",
    2: "String",
    3: "Int",
    4: "Float",
    5: "Bool",
    7: "Struct",
    11: "Object[]",
    12: "String[]",
    13: "Int[]",
    14: "Float[]",
    15: "Bool[]",
    17: "Struct[]",
}

IMPLICIT_MASTERS = frozenset(
    {
        "starfield.esm",
        "blueprintships-starfield.esm",
        "constellation.esm",
        "oldmars.esm",
        "shatteredspace.esm",
    }
)

# Records that never carry QUST or VMAD subrecords; skipping decompression keeps 200 MB terrain plugins sub-second.
_NO_VMAD_SIGS = frozenset({b"LAND", b"NAVM", b"LTEX", b"MATO", b"TXST", b"STAT", b"MSTT", b"LIGH"})

_README_PLUGINS_RE = re.compile(r"\bexp_install\.py\s+install\b.*?--plugins\s+([A-Za-z0-9_.,-]+)", re.IGNORECASE)

# Papyrus bytecode operand counts (fixed_var_args, has_trailing_vararg_count) for non-auto property handlers.
_PEX_OP_ARGS: Dict[int, Tuple[int, bool]] = {
    0x00: (0, False),
    0x01: (3, False),
    0x02: (3, False),
    0x03: (3, False),
    0x04: (3, False),
    0x05: (3, False),
    0x06: (3, False),
    0x07: (3, False),
    0x08: (3, False),
    0x09: (3, False),
    0x0A: (2, False),
    0x0B: (2, False),
    0x0C: (2, False),
    0x0D: (2, False),
    0x0E: (2, False),
    0x0F: (3, False),
    0x10: (3, False),
    0x11: (3, False),
    0x12: (3, False),
    0x13: (3, False),
    0x14: (1, False),
    0x15: (2, False),
    0x16: (2, False),
    0x17: (3, True),   # CallMethod
    0x18: (2, True),   # CallParent
    0x19: (3, True),   # CallStatic
    0x1A: (1, False),
    0x1B: (3, False),
    0x1C: (3, False),
    0x1D: (3, False),
    0x1E: (2, False),
    0x1F: (2, False),
    0x20: (3, False),
    0x21: (3, False),
    0x22: (4, False),
    0x23: (4, False),
    0x24: (3, False),
    0x25: (1, False),
    0x26: (3, False),
    0x27: (3, False),
    0x28: (5, False),
    0x29: (5, False),
    0x2A: (3, False),
    0x2B: (2, False),
    0x2C: (3, False),
    0x2D: (3, False),
    0x2E: (3, False),
    0x2F: (5, False),  # ArrayGetAllMatchingStructs
    0x30: (0, True),   # LockGuards
    0x31: (0, True),   # UnlockGuards
    0x32: (1, True),   # TryLockGuards
}


class SaveSafetyError(ValueError):
    """Raised when a plugin, VMAD subrecord, or PEX binary cannot be inspected."""


def _is_implicit_master(name: str) -> bool:
    low = name.casefold()
    return low in IMPLICIT_MASTERS or low.startswith("sfbgs")


def _stable_master_order(plugins: Sequence[str], masters_by_casefold: Dict[str, Sequence[str]]) -> List[str]:
    """Stable topological order matching scripts/game/load_order.py: already-valid orders stay identical."""
    nodes = [(idx, p.casefold(), p) for idx, p in enumerate(plugins)]
    at = {cf: idx for idx, cf, _p in nodes}
    needs = {
        idx: {at[m.casefold()] for m in masters_by_casefold.get(cf, ()) if m.casefold() in at and at[m.casefold()] != idx}
        for idx, cf, _p in nodes
    }
    placed = set()
    ordered: List[str] = []
    while len(ordered) < len(nodes):
        ready = [idx for idx, _cf, _p in nodes if idx not in placed and needs[idx] <= placed]
        if not ready:
            left = ", ".join(nodes[idx][2] for idx, _cf, _p in nodes if idx not in placed)
            raise SaveSafetyError(f"cyclic plugin master dependency among: {left}")
        pick = min(ready)
        placed.add(pick)
        ordered.append(nodes[pick][2])
    return ordered


def _read_plugin_masters_fast(path: str) -> List[str]:
    try:
        with open(path, "rb") as f:
            head = f.read(24)
            if len(head) < 24 or head[:4] != b"TES4":
                raise SaveSafetyError(f"{os.path.basename(path)}: not a TES4 plugin")
            size = struct.unpack_from("<I", head, 4)[0]
            flags = struct.unpack_from("<I", head, 8)[0]
            raw = f.read(size)
            if len(raw) != size:
                raise SaveSafetyError(f"{os.path.basename(path)}: truncated TES4 header")
        if flags & esm.COMPRESSED:
            if size < 4:
                raise SaveSafetyError(f"{os.path.basename(path)}: compressed TES4 header missing size")
            raw = zlib.decompress(raw[4:])
        subs = esm.parse_subrecords(raw)
    except (OSError, zlib.error, esm.EsmError) as exc:
        raise SaveSafetyError(f"{os.path.basename(path)}: {exc}") from exc
    return [esm.zstring(d) for s, d in subs if s == b"MAST"]


# ------------------------------------------------------------------------------------------------ VMAD decoder
def _rstr_cp1252(data: bytes, pos: int) -> Tuple[str, int]:
    if pos + 2 > len(data):
        raise SaveSafetyError("truncated VMAD string length")
    n, = struct.unpack_from("<H", data, pos)
    end = pos + 2 + n
    if end > len(data):
        raise SaveSafetyError("truncated VMAD string payload")
    return data[pos + 2 : end].decode("cp1252", "replace"), end


def _skip_vmad_value(data: bytes, pos: int, ptype: int, obj_format: int, version: int) -> int:
    if ptype == 1:  # Object
        need = 8
        if pos + need > len(data):
            raise SaveSafetyError("truncated VMAD Object value")
        return pos + need
    if ptype == 2:  # String
        _s, pos = _rstr_cp1252(data, pos)
        return pos
    if ptype in (3, 4):  # Int, Float
        if pos + 4 > len(data):
            raise SaveSafetyError("truncated VMAD numeric value")
        return pos + 4
    if ptype == 5:  # Bool
        if pos + 1 > len(data):
            raise SaveSafetyError("truncated VMAD Bool value")
        return pos + 1
    if ptype == 7:  # Struct
        if pos + 4 > len(data):
            raise SaveSafetyError("truncated VMAD Struct member count")
        count, = struct.unpack_from("<I", data, pos)
        pos += 4
        for _ in range(count):
            _mname, pos = _rstr_cp1252(data, pos)
            if pos + 1 > len(data):
                raise SaveSafetyError("truncated VMAD Struct member header")
            mtype = data[pos]
            pos += 1
            if version >= 4:
                if pos + 1 > len(data):
                    raise SaveSafetyError("truncated VMAD Struct member status")
                pos += 1
            pos = _skip_vmad_value(data, pos, mtype, obj_format, version)
        return pos
    if ptype in (11, 12, 13, 14, 15, 17):  # Arrays
        if pos + 4 > len(data):
            raise SaveSafetyError("truncated VMAD array length")
        count, = struct.unpack_from("<I", data, pos)
        pos += 4
        elem_type = ptype - 10
        for _ in range(count):
            pos = _skip_vmad_value(data, pos, elem_type, obj_format, version)
        return pos
    raise SaveSafetyError(f"unsupported VMAD property type {ptype}")


def _decode_script_entry(
    data: bytes,
    pos: int,
    version: int,
    obj_format: int,
    owner: str,
    *,
    pre_read_name: Optional[str] = None,
) -> Tuple[dict, int]:
    if pre_read_name is None:
        sname, pos = _rstr_cp1252(data, pos)
    else:
        sname = pre_read_name
    status = 0
    if version >= 4:
        if pos + 1 > len(data):
            raise SaveSafetyError("truncated VMAD script status")
        status = data[pos]
        pos += 1
    if pos + 2 > len(data):
        raise SaveSafetyError("truncated VMAD property count")
    nprops, = struct.unpack_from("<H", data, pos)
    pos += 2
    props: Dict[str, dict] = {}
    for _ in range(nprops):
        pname, pos = _rstr_cp1252(data, pos)
        if pos + 1 > len(data):
            raise SaveSafetyError("truncated VMAD property type")
        ptype = data[pos]
        pos += 1
        pstatus = 1
        if version >= 4:
            if pos + 1 > len(data):
                raise SaveSafetyError("truncated VMAD property status")
            pstatus = data[pos]
            pos += 1
        if pstatus != 3:  # status 3 == removed (carries no value bytes)
            pos = _skip_vmad_value(data, pos, ptype, obj_format, version)
        props[pname.casefold()] = {
            "name": pname,
            "type": ptype,
            "type_name": VMAD_PROP_TYPES.get(ptype, f"Type{ptype}"),
            "status": pstatus,
        }
    return {
        "name": sname,
        "owner": owner,
        "status": status,
        "properties": props,
    }, pos


def decode_vmad_scripts(data: bytes, record_sig: bytes = b"REFR") -> List[dict]:
    """Decode all bound scripts & properties from a record or QUST VMAD (including QUST fragment & alias scripts)."""
    data = bytes(data)
    if len(data) < 6:
        raise SaveSafetyError("VMAD shorter than 6-byte header")
    version, obj_format, script_count = struct.unpack_from("<hHH", data, 0)
    if version not in (4, 5, 6) or obj_format not in (1, 2):
        raise SaveSafetyError(f"unsupported VMAD version={version} format={obj_format}")
    pos = 6
    scripts: List[dict] = []
    for _ in range(script_count):
        entry, pos = _decode_script_entry(data, pos, version, obj_format, owner="record")
        scripts.append(entry)

    if record_sig == b"QUST" and pos < len(data):
        extra_ver = data[pos]
        pos += 1
        if pos + 2 > len(data):
            raise SaveSafetyError("truncated QUST VMAD fragment count")
        frag_count, = struct.unpack_from("<H", data, pos)
        pos += 2
        frag_script_name, pos = _rstr_cp1252(data, pos)
        if extra_ver >= 3 and frag_script_name:
            frag_entry, pos = _decode_script_entry(
                data,
                pos,
                version,
                obj_format,
                owner="fragment",
                pre_read_name=frag_script_name,
            )
            scripts.append(frag_entry)

        for _ in range(frag_count):
            # Starfield / FO4 QUST fragment: u16 stage, u16 unk, i32 log_index, u8 unk2, wstr script, wstr func
            if pos + 9 > len(data):
                raise SaveSafetyError("truncated QUST VMAD stage fragment")
            pos += 9
            _fs, pos = _rstr_cp1252(data, pos)
            _ff, pos = _rstr_cp1252(data, pos)

        if pos + 2 <= len(data):
            alias_count, = struct.unpack_from("<H", data, pos)
            pos += 2
            for _ in range(alias_count):
                if pos + 8 > len(data):
                    raise SaveSafetyError("truncated QUST VMAD alias object handle")
                if obj_format == 2:
                    _unused, alias_id, _qform = struct.unpack_from("<HhI", data, pos)
                else:
                    _qform, alias_id, _unused = struct.unpack_from("<Ihh", data, pos)
                pos += 8
                if pos + 6 > len(data):
                    raise SaveSafetyError("truncated QUST VMAD alias adapter header")
                al_ver, al_fmt, al_sc_count = struct.unpack_from("<hHH", data, pos)
                pos += 6
                for _ in range(al_sc_count):
                    al_entry, pos = _decode_script_entry(data, pos, al_ver, al_fmt, owner=f"alias:{alias_id}")
                    scripts.append(al_entry)

    return scripts


# ------------------------------------------------------------------------------------------------ PEX decoder
def _read_pex_var_data(data: bytes, pos: int, endian: str) -> Tuple[object, int]:
    if pos >= len(data):
        raise SaveSafetyError("truncated PEX variable data")
    vt = data[pos]
    pos += 1
    if vt == 0:
        return None, pos
    if vt in (1, 2):
        if pos + 2 > len(data):
            raise SaveSafetyError("truncated PEX string/identifier var data")
        v, = struct.unpack_from(endian + "H", data, pos)
        return v, pos + 2
    if vt == 3:
        if pos + 4 > len(data):
            raise SaveSafetyError("truncated PEX int var data")
        v, = struct.unpack_from(endian + "i", data, pos)
        return v, pos + 4
    if vt == 4:
        if pos + 4 > len(data):
            raise SaveSafetyError("truncated PEX float var data")
        v, = struct.unpack_from(endian + "f", data, pos)
        return v, pos + 4
    if vt == 5:
        if pos + 1 > len(data):
            raise SaveSafetyError("truncated PEX bool var data")
        return bool(data[pos]), pos + 1
    raise SaveSafetyError(f"unknown PEX variable data tag {vt}")


def _skip_pex_function(data: bytes, pos: int, endian: str) -> int:
    if pos + 11 > len(data):
        raise SaveSafetyError("truncated PEX function header")
    pos += 9  # returnType(u16), doc(u16), userFlags(u32), flags(u8)
    n_params, = struct.unpack_from(endian + "H", data, pos)
    pos += 2 + 4 * n_params
    if pos + 2 > len(data):
        raise SaveSafetyError("truncated PEX function locals")
    n_locals, = struct.unpack_from(endian + "H", data, pos)
    pos += 2 + 4 * n_locals
    if pos + 2 > len(data):
        raise SaveSafetyError("truncated PEX instruction count")
    n_insns, = struct.unpack_from(endian + "H", data, pos)
    pos += 2
    for _ in range(n_insns):
        if pos >= len(data):
            raise SaveSafetyError("truncated PEX instruction stream")
        op = data[pos]
        pos += 1
        spec = _PEX_OP_ARGS.get(op)
        if spec is None:
            raise SaveSafetyError(f"unknown PEX opcode 0x{op:02X}")
        fixed, has_var = spec
        for _ in range(fixed):
            _, pos = _read_pex_var_data(data, pos, endian)
        if has_var:
            extra, pos = _read_pex_var_data(data, pos, endian)
            for _ in range(int(extra or 0)):
                _, pos = _read_pex_var_data(data, pos, endian)
    return pos


def parse_pex_properties(data: bytes, source: str = "") -> Dict[str, dict]:
    """Parse compiled Papyrus `.pex` (`0xFA57C0DE`) objects and their `Property` tables."""
    data = bytes(data)
    if len(data) < 16:
        raise SaveSafetyError(f"{source or 'pex'}: file shorter than 16-byte PEX header")
    magic_le, = struct.unpack_from("<I", data, 0)
    if magic_le == PEX_MAGIC_LE:
        endian = "<"
    elif magic_le == PEX_MAGIC_BE:
        endian = ">"
    else:
        raise SaveSafetyError(f"{source or 'pex'}: invalid PEX magic 0x{magic_le:08X}")

    _magic, major, minor, _game_id, _ctime = struct.unpack_from(endian + "IBBHQ", data, 0)
    pos = 16

    def rstr() -> str:
        nonlocal pos
        if pos + 2 > len(data):
            raise SaveSafetyError(f"{source or 'pex'}: truncated string length")
        n, = struct.unpack_from(endian + "H", data, pos)
        pos += 2
        if pos + n > len(data):
            raise SaveSafetyError(f"{source or 'pex'}: truncated string data")
        s = data[pos : pos + n].decode("utf-8", "replace")
        pos += n
        return s

    rstr()  # source file name
    rstr()  # user name
    rstr()  # machine name
    if pos + 2 > len(data):
        raise SaveSafetyError(f"{source or 'pex'}: truncated string table count")
    n_strs, = struct.unpack_from(endian + "H", data, pos)
    pos += 2
    strings = [rstr() for _ in range(n_strs)]

    def s_at(idx: int) -> str:
        if 0 <= idx < len(strings):
            return strings[idx]
        raise SaveSafetyError(f"{source or 'pex'}: string index {idx} out of range ({len(strings)})")

    if pos >= len(data):
        raise SaveSafetyError(f"{source or 'pex'}: truncated debug flag")
    has_debug = data[pos]
    pos += 1
    if has_debug:
        if pos + 10 > len(data):
            raise SaveSafetyError(f"{source or 'pex'}: truncated debug header")
        _mtime, n_df = struct.unpack_from(endian + "QH", data, pos)
        pos += 10
        for _ in range(n_df):
            if pos + 9 > len(data):
                raise SaveSafetyError(f"{source or 'pex'}: truncated debug function")
            n_ln, = struct.unpack_from(endian + "H", data, pos + 7)
            pos += 9 + 2 * n_ln
        if (major, minor) >= (3, 9):
            n_pg, = struct.unpack_from(endian + "H", data, pos)
            pos += 2
            for _ in range(n_pg):
                n_nm, = struct.unpack_from(endian + "H", data, pos + 10)
                pos += 12 + 2 * n_nm
            n_so, = struct.unpack_from(endian + "H", data, pos)
            pos += 2
            for _ in range(n_so):
                n_sz, = struct.unpack_from(endian + "H", data, pos + 4)
                pos += 6 + 2 * n_sz

    n_uf, = struct.unpack_from(endian + "H", data, pos)
    pos += 2 + 3 * n_uf
    n_obj, = struct.unpack_from(endian + "H", data, pos)
    pos += 2

    objects: Dict[str, dict] = {}
    for _ in range(n_obj):
        if pos + 6 > len(data):
            raise SaveSafetyError(f"{source or 'pex'}: truncated object header")
        name_idx, obj_size = struct.unpack_from(endian + "HI", data, pos)
        pos += 2
        obj_end = pos + obj_size
        if obj_end > len(data):
            raise SaveSafetyError(f"{source or 'pex'}: object runs past EOF")
        pos += 4
        # parent(u16), doc(u16), const(u8 if >=3.9), userFlags(u32), autoState(u16)
        if (major, minor) >= (3, 9):
            pos += 11
        else:
            pos += 10

        if (major, minor) >= (3, 9):
            n_structs, = struct.unpack_from(endian + "H", data, pos)
            pos += 2
            for _ in range(n_structs):
                pos += 2
                n_members, = struct.unpack_from(endian + "H", data, pos)
                pos += 2
                for _ in range(n_members):
                    pos += 8
                    _, pos = _read_pex_var_data(data, pos, endian)
                    pos += 3

        n_vars, = struct.unpack_from(endian + "H", data, pos)
        pos += 2
        for _ in range(n_vars):
            pos += 8
            _, pos = _read_pex_var_data(data, pos, endian)
            if (major, minor) >= (3, 9):
                pos += 1

        if (major, minor) >= (3, 10):
            n_guards, = struct.unpack_from(endian + "H", data, pos)
            pos += 2 + 2 * n_guards

        n_props, = struct.unpack_from(endian + "H", data, pos)
        pos += 2
        props: Dict[str, dict] = {}
        for _ in range(n_props):
            pname_idx, ptype_idx, _pdoc_idx, puf, pflags = struct.unpack_from(endian + "HHHIB", data, pos)
            pos += 11
            if pflags & 4:
                pos += 2
            else:
                if pflags & 1:
                    pos = _skip_pex_function(data, pos, endian)
                if pflags & 2:
                    pos = _skip_pex_function(data, pos, endian)
            pname = s_at(pname_idx)
            ptype = s_at(ptype_idx)
            props[pname.casefold()] = {
                "name": pname,
                "type": ptype,
                "type_norm": ptype.casefold(),
                "flags": pflags,
                "user_flags": puf,
            }

        obj_name = s_at(name_idx)
        objects[obj_name.casefold()] = {
            "name": obj_name,
            "source": source,
            "properties": props,
        }
        pos = obj_end

    return objects


# ------------------------------------------------------------------------------------------------ plugin & build inspection
def _record_key(formid: int, masters: Sequence[str]) -> str:
    idx = (formid >> 24) & 0xFF
    local = formid & 0x00FFFFFF
    if idx < len(masters):
        return f"ovr:{masters[idx].casefold()}:{local:06X}"
    return f"own:{local:06X}"


def inspect_plugin(path: str) -> dict:
    """Inspect one `.esm` plugin's masters, `QUST` stages/aliases, and all `VMAD` script property bindings."""
    if not os.path.isfile(path):
        raise SaveSafetyError(f"missing plugin file: {os.path.basename(path)}")
    quests: Dict[str, dict] = {}
    vmad_records: Dict[str, dict] = {}
    record_count = 0

    try:
        with esm.Plugin(path) as plug:
            masters = list(plug.masters)
            for label, spans in plug.groups.items():
                for start, end in spans:
                    for item in plug.walk(start, end):
                        if item[0] != "REC":
                            continue
                        record_count += 1
                        off = item[1]
                        sig = item[2]
                        if sig in _NO_VMAD_SIGS:
                            continue
                        size = struct.unpack_from("<I", plug.buf, off + 4)[0]
                        flags = struct.unpack_from("<I", plug.buf, off + 8)[0]
                        fid = struct.unpack_from("<I", plug.buf, off + 12)[0]
                        if sig != b"QUST" and not (flags & esm.COMPRESSED):
                            if plug.buf.find(b"VMAD", off + 24, off + 24 + size) < 0:
                                continue

                        rec = plug.record_at(off)
                        rkey = _record_key(fid, masters)
                        edid = rec.edid
                        vmad_raw = rec.get(b"VMAD")
                        if vmad_raw is not None:
                            scripts = decode_vmad_scripts(vmad_raw, sig)
                            vmad_records[rkey] = {
                                "sig": sig.decode("latin1"),
                                "edid": edid,
                                "local_id": f"{fid & 0xFFFFFF:06X}",
                                "scripts": scripts,
                            }

                        if sig == b"QUST":
                            stages = sorted({struct.unpack_from("<H", d, 0)[0] for d in rec.all(b"INDX") if len(d) >= 2})
                            aliases: List[dict] = []
                            cur_alias: Optional[dict] = None
                            for s_sig, s_data in rec.subs:
                                if s_sig in (b"ALST", b"ALLS") and len(s_data) >= 4:
                                    if cur_alias is not None:
                                        aliases.append(cur_alias)
                                    cur_alias = {
                                        "id": struct.unpack_from("<I", s_data, 0)[0],
                                        "kind": s_sig.decode("ascii"),
                                        "name": "",
                                    }
                                elif s_sig == b"ALID" and cur_alias is not None and not cur_alias["name"]:
                                    cur_alias["name"] = esm.zstring(s_data)
                                elif s_sig == b"ALED" and cur_alias is not None:
                                    aliases.append(cur_alias)
                                    cur_alias = None
                            if cur_alias is not None:
                                aliases.append(cur_alias)

                            dnam = rec.get(b"DNAM")
                            qflags = struct.unpack_from("<H", dnam, 0)[0] if dnam and len(dnam) >= 2 else 0
                            quests[rkey] = {
                                "edid": edid or f"0x{fid & 0xFFFFFF:06X}",
                                "local_id": f"{fid & 0xFFFFFF:06X}",
                                "stages": stages,
                                "aliases": aliases,
                                "start_game_enabled": bool(qflags & 0x0001),
                            }
    except (OSError, esm.EsmError) as exc:
        raise SaveSafetyError(f"{os.path.basename(path)}: {exc}") from exc

    return {
        "name": os.path.basename(path),
        "masters": masters,
        "record_count": record_count,
        "quests": quests,
        "vmad_records": vmad_records,
    }


def _resolve_build_paths_and_plugins(target_dir: str, explicit_plugins: Optional[Sequence[str]] = None) -> Tuple[str, str, List[str]]:
    """Return (plugin_root, data_root, ordered_plugin_names) for a staged bundle or an installed Starfield folder."""
    if not os.path.isdir(target_dir):
        raise SaveSafetyError(f"build directory does not exist: {os.path.basename(target_dir) or target_dir}")

    # Installed game root (`<game>/Data/FO4SFExp.install.json`) vs direct `Data/` vs staged bundle dir.
    rec_in_data = os.path.join(target_dir, "Data", "FO4SFExp.install.json")
    rec_direct = os.path.join(target_dir, "FO4SFExp.install.json")
    bundle_plan_p = os.path.join(target_dir, "bundle_plan.json")
    readme_p = os.path.join(target_dir, "README.txt")

    if os.path.isfile(rec_in_data) and not any(fn.lower().endswith(".esm") for fn in os.listdir(target_dir)):
        plugin_root = os.path.join(target_dir, "Data")
        data_root = plugin_root
        rec_path = rec_in_data
    else:
        plugin_root = target_dir
        data_sub = os.path.join(target_dir, "Data")
        data_root = data_sub if os.path.isdir(data_sub) else target_dir
        rec_path = rec_direct if os.path.isfile(rec_direct) else None

    raw_plugins: Optional[List[str]] = None
    preserve_exact_order = False

    if explicit_plugins:
        raw_plugins = [p.strip() for p in explicit_plugins if p and p.strip()]
    elif rec_path is not None:
        with open(rec_path, encoding="utf-8") as f:
            rec = json.load(f)
        cand = rec.get("plugins")
        if cand is None:
            cand = [x.lstrip("*").strip() for x in rec.get("plugins_added", [])]
            cand += [x["active"].lstrip("*").strip() for x in rec.get("plugins_replaced", [])]
        raw_plugins = list(cand)
        act_b64 = rec.get("plugins_activated")
        if act_b64:
            try:
                act_text = base64.b64decode(act_b64).decode("utf-8-sig", "replace")
                act_order = [
                    ln.strip()[1:].strip().casefold()
                    for ln in act_text.splitlines()
                    if ln.strip().startswith("*")
                ]
                pos_map = {name: i for i, name in enumerate(act_order)}
                if all(p.casefold() in pos_map for p in raw_plugins):
                    raw_plugins.sort(key=lambda p: pos_map[p.casefold()])
                    preserve_exact_order = True
            except (ValueError, KeyError):
                pass
    elif os.path.isfile(bundle_plan_p):
        with open(bundle_plan_p, encoding="utf-8") as f:
            bplan = json.load(f)
        if isinstance(bplan.get("plugins"), list) and bplan["plugins"]:
            raw_plugins = [str(x) for x in bplan["plugins"]]
            preserve_exact_order = True
    elif os.path.isfile(readme_p):
        with open(readme_p, encoding="utf-8", errors="replace") as f:
            rtxt = f.read()
        m = _README_PLUGINS_RE.search(rtxt)
        if m:
            cand = [p.strip() for p in m.group(1).split(",") if p.strip()]
            if cand and all(os.path.isfile(os.path.join(plugin_root, p)) for p in cand):
                raw_plugins = cand

    if raw_plugins is None:
        raw_plugins = sorted(
            fn for fn in os.listdir(plugin_root) if fn.lower().endswith((".esm", ".esp", ".esl"))
        )

    # Resolve case-insensitive filenames on disk for cross-platform safety.
    disk_map = {fn.casefold(): fn for fn in os.listdir(plugin_root) if os.path.isfile(os.path.join(plugin_root, fn))}
    resolved_plugins: List[str] = []
    masters_map: Dict[str, List[str]] = {}
    for p in raw_plugins:
        actual = disk_map.get(p.casefold())
        if actual is None:
            raise SaveSafetyError(f"plugin {p} not found in build directory")
        resolved_plugins.append(actual)
        masters_map[actual.casefold()] = _read_plugin_masters_fast(os.path.join(plugin_root, actual))

    ordered = resolved_plugins if preserve_exact_order else _stable_master_order(resolved_plugins, masters_map)
    return plugin_root, data_root, ordered


def collect_build_pex(plugin_root: str, data_root: str, plugins: Sequence[str]) -> Dict[str, dict]:
    """Collect compiled `.pex` script definitions from packed BA2 archives and loose `Data/Scripts` files."""
    scripts: Dict[str, dict] = {}

    # 1. Read GNRL BA2 archives (`<plugin> - Main.ba2` or other general archives associated with the build).
    ba2_dirs = []
    for d in (plugin_root, data_root):
        if os.path.isdir(d) and d not in ba2_dirs:
            ba2_dirs.append(d)

    plugin_stems = {os.path.splitext(p)[0].casefold() for p in plugins}
    for folder in ba2_dirs:
        for fn in sorted(os.listdir(folder)):
            if not fn.lower().endswith(".ba2"):
                continue
            # When scanning a shared game Data/ folder, restrict to archives belonging to the selected plugins.
            stem_prefix = fn.split(" - ", 1)[0].casefold()
            if plugin_stems and folder != plugin_root and stem_prefix not in plugin_stems:
                continue
            bpath = os.path.join(folder, fn)
            if not os.path.isfile(bpath):
                continue
            try:
                archive = Ba2(bpath)
            except Ba2Error:
                continue
            if archive.kind != "GNRL":
                continue
            for idx, entry in enumerate(archive.entries):
                norm_name = entry.name.replace("/", "\\")
                if norm_name.lower().endswith(".pex"):
                    raw = archive.read(idx)
                    parsed = parse_pex_properties(raw, source=f"{fn}:{os.path.basename(norm_name)}")
                    scripts.update(parsed)

    # 2. Loose `Scripts/*.pex` files (override BA2 entries of the same script name if both exist).
    scripts_dir = os.path.join(data_root, "Scripts")
    if not os.path.isdir(scripts_dir):
        # Case-insensitive fallback on POSIX filesystems
        for fn in os.listdir(data_root) if os.path.isdir(data_root) else ():
            if fn.casefold() == "scripts" and os.path.isdir(os.path.join(data_root, fn)):
                scripts_dir = os.path.join(data_root, fn)
                break

    if os.path.isdir(scripts_dir):
        for root, dirs, files in os.walk(scripts_dir):
            dirs.sort()
            for fn in sorted(files):
                if not fn.lower().endswith(".pex"):
                    continue
                fpath = os.path.join(root, fn)
                with open(fpath, "rb") as handle:
                    raw = handle.read()
                parsed = parse_pex_properties(raw, source=fn)
                scripts.update(parsed)

    return scripts


def inspect_build(target_dir: str, *, plugins: Optional[Sequence[str]] = None) -> dict:
    """Inspect all selected plugins and compiled `.pex` scripts in a staged or installed build."""
    plugin_root, data_root, ordered_plugins = _resolve_build_paths_and_plugins(target_dir, plugins)
    plugin_infos: Dict[str, dict] = {}
    for p in ordered_plugins:
        plugin_infos[p.casefold()] = inspect_plugin(os.path.join(plugin_root, p))
    pex_scripts = collect_build_pex(plugin_root, data_root, ordered_plugins)

    total_quests = sum(len(info["quests"]) for info in plugin_infos.values())
    total_aliases = sum(
        len(q["aliases"]) for info in plugin_infos.values() for q in info["quests"].values()
    )
    total_vmad_props = sum(
        len(sc["properties"])
        for info in plugin_infos.values()
        for rec in info["vmad_records"].values()
        for sc in rec["scripts"]
    )
    total_pex_props = sum(len(sc["properties"]) for sc in pex_scripts.values())

    return {
        "ordered_plugins": ordered_plugins,
        "plugins": plugin_infos,
        "pex_scripts": pex_scripts,
        "summary": {
            "plugin_count": len(ordered_plugins),
            "record_count": sum(info["record_count"] for info in plugin_infos.values()),
            "quest_count": total_quests,
            "alias_count": total_aliases,
            "vmad_record_count": sum(len(info["vmad_records"]) for info in plugin_infos.values()),
            "vmad_property_count": total_vmad_props,
            "pex_script_count": len(pex_scripts),
            "pex_property_count": total_pex_props,
        },
    }


# ------------------------------------------------------------------------------------------------ build comparison
def _compare_vmad_script_lists(
    plugin_name: str,
    rec_label: str,
    before_scripts: Sequence[dict],
    after_scripts: Sequence[dict],
    breaking: List[dict],
    advisories: List[dict],
) -> None:
    b_map = {(s["owner"], s["name"].casefold()): s for s in before_scripts if s.get("status") != 3}
    a_map = {(s["owner"], s["name"].casefold()): s for s in after_scripts if s.get("status") != 3}

    for key, b_sc in sorted(b_map.items()):
        owner, _scf = key
        if key not in a_map:
            breaking.append(
                {
                    "category": "changed_script_property",
                    "kind": "removed_vmad_script",
                    "plugin": plugin_name,
                    "target": f"{rec_label}:{owner}:{b_sc['name']}",
                    "detail": f"bound VMAD script {b_sc['name']} removed from {rec_label} ({owner})",
                }
            )
            continue
        a_sc = a_map[key]
        b_props = {k: v for k, v in b_sc["properties"].items() if v["status"] != 3}
        a_props = {k: v for k, v in a_sc["properties"].items() if v["status"] != 3}
        for pk, bp in sorted(b_props.items()):
            if pk not in a_props:
                breaking.append(
                    {
                        "category": "changed_script_property",
                        "kind": "removed_vmad_property",
                        "plugin": plugin_name,
                        "target": f"{rec_label}:{b_sc['name']}.{bp['name']}",
                        "detail": f"VMAD property {b_sc['name']}.{bp['name']} ({bp['type_name']}) removed on {rec_label}",
                    }
                )
            elif a_props[pk]["type"] != bp["type"]:
                ap = a_props[pk]
                breaking.append(
                    {
                        "category": "changed_script_property",
                        "kind": "retyped_vmad_property",
                        "plugin": plugin_name,
                        "target": f"{rec_label}:{b_sc['name']}.{bp['name']}",
                        "detail": (
                            f"VMAD property {b_sc['name']}.{bp['name']} changed type "
                            f"{bp['type_name']} -> {ap['type_name']} on {rec_label}"
                        ),
                    }
                )
        for pk, ap in sorted(a_props.items()):
            if pk not in b_props:
                advisories.append(
                    {
                        "category": "added_script_property",
                        "plugin": plugin_name,
                        "target": f"{rec_label}:{a_sc['name']}.{ap['name']}",
                        "detail": f"added VMAD property {a_sc['name']}.{ap['name']} ({ap['type_name']}) on {rec_label}",
                    }
                )


def compare_inspected_builds(before: dict, after: dict) -> dict:
    """Compare two `inspect_build` snapshots and classify save compatibility."""
    breaking: List[dict] = []
    advisories: List[dict] = []

    b_order = before["ordered_plugins"]
    a_order = after["ordered_plugins"]
    b_cf = [p.casefold() for p in b_order]
    a_cf = [p.casefold() for p in a_order]
    b_names = {p.casefold(): p for p in b_order}
    a_names = {p.casefold(): p for p in a_order}

    a_set = set(a_cf)
    b_set = set(b_cf)

    # 1. Plugin Load-Order & Presence Rules
    removed_plugins = [b_names[p] for p in b_cf if p not in a_set]
    for p in removed_plugins:
        breaking.append(
            {
                "category": "removed_plugin",
                "kind": "removed_plugin",
                "plugin": p,
                "target": p,
                "detail": f"removed plugin {p} orphans baked save FormIDs",
            }
        )

    kept_b = [p for p in b_cf if p in a_set]
    kept_a = [p for p in a_cf if p in b_set]
    reordered_plugins: List[str] = []
    if kept_b != kept_a:
        for idx_old, p in enumerate(kept_b):
            idx_new = kept_a.index(p)
            if idx_old != idx_new:
                reordered_plugins.append(a_names[p])
                breaking.append(
                    {
                        "category": "reordered_plugin",
                        "kind": "reordered_plugin",
                        "plugin": a_names[p],
                        "target": a_names[p],
                        "detail": (
                            f"plugin {a_names[p]} moved relative slot {idx_old} -> {idx_new}, "
                            "shifting load-order FormID indices"
                        ),
                    }
                )

    added_cf = [p for p in a_cf if p not in b_set]
    inserted_plugins: List[str] = []
    appended_plugins: List[str] = []
    last_surviving_idx = max((a_cf.index(p) for p in kept_a), default=-1)
    for p in added_cf:
        pos = a_cf.index(p)
        pname = a_names[p]
        if pos < last_surviving_idx:
            inserted_plugins.append(pname)
            shifted_after = a_names[next(k for k in kept_a if a_cf.index(k) > pos)]
            breaking.append(
                {
                    "category": "inserted_plugin_shifts_indices",
                    "kind": "inserted_plugin_shifts_indices",
                    "plugin": pname,
                    "target": pname,
                    "detail": (
                        f"added plugin {pname} at index {pos} before {shifted_after} "
                        "shifts surviving plugin FormID indices"
                    ),
                }
            )
        else:
            appended_plugins.append(pname)
            p_info = after["plugins"][p]
            sge = [q["edid"] for q in p_info["quests"].values() if q["start_game_enabled"]]
            advisories.append(
                {
                    "category": "appended_plugin",
                    "plugin": pname,
                    "target": pname,
                    "detail": (
                        f"appended plugin {pname} at index {pos}"
                        + (
                            f" ({len(sge)} StartGameEnabled quest(s) may need OnPlayerLoadGame or New Game)"
                            if sge
                            else ""
                        )
                    ),
                }
            )

    # 2. Shared Plugin QUST Stage/Alias Rules & VMAD Property Rules
    for p_cf in kept_b:
        b_plug = before["plugins"][p_cf]
        a_plug = after["plugins"][p_cf]
        pname = a_plug["name"]

        # QUST checks
        for qkey, b_q in sorted(b_plug["quests"].items()):
            qlabel = f"QUST {b_q['edid']} ({b_q['local_id']})"
            if qkey not in a_plug["quests"]:
                breaking.append(
                    {
                        "category": "changed_quest_or_alias",
                        "kind": "removed_quest",
                        "plugin": pname,
                        "target": qlabel,
                        "detail": f"removed {qlabel} from {pname}",
                    }
                )
                continue
            a_q = a_plug["quests"][qkey]
            missing_stages = sorted(set(b_q["stages"]) - set(a_q["stages"]))
            if missing_stages:
                breaking.append(
                    {
                        "category": "changed_quest_or_alias",
                        "kind": "removed_quest_stage",
                        "plugin": pname,
                        "target": qlabel,
                        "detail": f"{qlabel} removed INDX stage(s) {missing_stages}",
                    }
                )
            b_aliases = b_q["aliases"]
            a_aliases = a_q["aliases"]
            if len(a_aliases) < len(b_aliases):
                breaking.append(
                    {
                        "category": "changed_quest_or_alias",
                        "kind": "reduced_alias_count",
                        "plugin": pname,
                        "target": qlabel,
                        "detail": f"{qlabel} reduced alias count {len(b_aliases)} -> {len(a_aliases)}",
                    }
                )
            b_amap = {al["id"]: al for al in b_aliases}
            a_amap = {al["id"]: al for al in a_aliases}
            for al_id, b_al in sorted(b_amap.items()):
                if al_id not in a_amap:
                    breaking.append(
                        {
                            "category": "changed_quest_or_alias",
                            "kind": "changed_alias_id",
                            "plugin": pname,
                            "target": f"{qlabel}:alias[{al_id}]",
                            "detail": f"{qlabel} removed or renumbered {b_al['kind']} alias ID {al_id} ({b_al['name']})",
                        }
                    )
                elif a_amap[al_id]["kind"] != b_al["kind"]:
                    breaking.append(
                        {
                            "category": "changed_quest_or_alias",
                            "kind": "changed_alias_kind",
                            "plugin": pname,
                            "target": f"{qlabel}:alias[{al_id}]",
                            "detail": (
                                f"{qlabel} alias ID {al_id} changed kind "
                                f"{b_al['kind']} -> {a_amap[al_id]['kind']}"
                            ),
                        }
                    )

        # VMAD checks on all scripted records
        for rkey, b_rec in sorted(b_plug["vmad_records"].items()):
            rlabel = f"{b_rec['sig']} {b_rec['edid'] or b_rec['local_id']}"
            if rkey not in a_plug["vmad_records"]:
                # If a QUST record itself was deleted, removed_quest already recorded it; otherwise VMAD was stripped or record deleted.
                if b_rec["sig"] == "QUST" and rkey not in a_plug["quests"]:
                    continue
                breaking.append(
                    {
                        "category": "changed_script_property",
                        "kind": "removed_vmad",
                        "plugin": pname,
                        "target": rlabel,
                        "detail": f"VMAD bindings removed from {rlabel} in {pname}",
                    }
                )
                continue
            a_rec = a_plug["vmad_records"][rkey]
            _compare_vmad_script_lists(pname, rlabel, b_rec["scripts"], a_rec["scripts"], breaking, advisories)

    # 3. Compiled .pex Script Property Rules
    b_pex = before["pex_scripts"]
    a_pex = after["pex_scripts"]
    for sc_cf, b_sc in sorted(b_pex.items()):
        if sc_cf not in a_pex:
            breaking.append(
                {
                    "category": "changed_script_property",
                    "kind": "removed_pex_script",
                    "plugin": "Scripts",
                    "target": f"{b_sc['name']}.pex",
                    "detail": f"compiled script {b_sc['name']}.pex removed",
                }
            )
            continue
        a_sc = a_pex[sc_cf]
        for pk, bp in sorted(b_sc["properties"].items()):
            if pk not in a_sc["properties"]:
                breaking.append(
                    {
                        "category": "changed_script_property",
                        "kind": "removed_pex_property",
                        "plugin": "Scripts",
                        "target": f"{b_sc['name']}.{bp['name']}",
                        "detail": f"compiled PEX property {b_sc['name']}.{bp['name']} ({bp['type']}) removed",
                    }
                )
            elif a_sc["properties"][pk]["type_norm"] != bp["type_norm"]:
                ap = a_sc["properties"][pk]
                breaking.append(
                    {
                        "category": "changed_script_property",
                        "kind": "retyped_pex_property",
                        "plugin": "Scripts",
                        "target": f"{b_sc['name']}.{bp['name']}",
                        "detail": (
                            f"compiled PEX property {b_sc['name']}.{bp['name']} changed type "
                            f"{bp['type']} -> {ap['type']}"
                        ),
                    }
                )
        for pk, ap in sorted(a_sc["properties"].items()):
            if pk not in b_sc["properties"]:
                advisories.append(
                    {
                        "category": "added_script_property",
                        "plugin": "Scripts",
                        "target": f"{a_sc['name']}.{ap['name']}",
                        "detail": f"compiled PEX property {a_sc['name']}.{ap['name']} ({ap['type']}) added",
                    }
                )

    counts = {
        "removed_plugin": sum(1 for x in breaking if x["category"] == "removed_plugin"),
        "reordered_plugin": sum(1 for x in breaking if x["category"] == "reordered_plugin"),
        "inserted_plugin_shifts_indices": sum(
            1 for x in breaking if x["category"] == "inserted_plugin_shifts_indices"
        ),
        "changed_script_property": sum(1 for x in breaking if x["category"] == "changed_script_property"),
        "changed_quest_or_alias": sum(1 for x in breaking if x["category"] == "changed_quest_or_alias"),
        "appended_plugin": len(appended_plugins),
    }

    if breaking:
        verdict = "BREAKING"
    elif appended_plugins:
        verdict = "SAFE_APPEND"
    else:
        verdict = "SAFE"

    report = {
        "verdict": verdict,
        "save_compatible": verdict != "BREAKING",
        "before": {
            "plugins": b_order,
            "summary": before["summary"],
        },
        "after": {
            "plugins": a_order,
            "summary": after["summary"],
        },
        "plugin_diff": {
            "removed": removed_plugins,
            "reordered": reordered_plugins,
            "inserted": inserted_plugins,
            "appended": appended_plugins,
        },
        "counts": counts,
        "breaking": breaking,
        "advisories": advisories,
    }
    report["swap_warning"] = one_line_swap_warning(report)
    return report


def compare_builds(
    before_dir: str,
    after_dir: str,
    *,
    before_plugins: Optional[Sequence[str]] = None,
    after_plugins: Optional[Sequence[str]] = None,
) -> dict:
    """Inspect and compare two builds/bundles (`before_dir` -> `after_dir`) for savegame compatibility."""
    before = inspect_build(before_dir, plugins=before_plugins)
    after = inspect_build(after_dir, plugins=after_plugins)
    return compare_inspected_builds(before, after)


def one_line_swap_warning(report: dict) -> Optional[str]:
    """Return None when save-compatible, or a single-line warning string when a swap breaks saves."""
    if not report or report.get("verdict") != "BREAKING":
        return None
    counts = report.get("counts") or {}
    ordered_keys = (
        "removed_plugin",
        "reordered_plugin",
        "inserted_plugin_shifts_indices",
        "changed_script_property",
        "changed_quest_or_alias",
    )
    parts = [f"{k}={counts[k]}" for k in ordered_keys if counts.get(k, 0) > 0]
    if not parts:
        parts = [f"issues={len(report.get('breaking') or ())}"]
    return (
        f"WARNING: swapping builds will invalidate existing saves ({', '.join(parts)}); "
        "start a New Game or back up saves first."
    )


def format_text_report(report: dict) -> str:
    """Format a human-readable save-compatibility summary without any machine-specific paths."""
    b_sum = report["before"]["summary"]
    a_sum = report["after"]["summary"]
    lines = [
        f"SAVE SAFETY VERDICT: {report['verdict']}",
        (
            f"Before: {b_sum['plugin_count']} plugins, {b_sum['quest_count']} QUST ({b_sum['alias_count']} aliases), "
            f"{b_sum['vmad_property_count']} VMAD props, {b_sum['pex_script_count']} PEX ({b_sum['pex_property_count']} props)"
        ),
        (
            f"After:  {a_sum['plugin_count']} plugins, {a_sum['quest_count']} QUST ({a_sum['alias_count']} aliases), "
            f"{a_sum['vmad_property_count']} VMAD props, {a_sum['pex_script_count']} PEX ({a_sum['pex_property_count']} props)"
        ),
    ]
    pdiff = report["plugin_diff"]
    if any(pdiff.values()):
        lines.append(
            f"Plugins: removed={len(pdiff['removed'])}, reordered={len(pdiff['reordered'])}, "
            f"inserted={len(pdiff['inserted'])}, appended={len(pdiff['appended'])}"
        )
    warn = report.get("swap_warning") or one_line_swap_warning(report)
    if warn:
        lines.append(warn)
    for item in report["breaking"][:20]:
        lines.append(f"  [BREAKING:{item['category']}] {item['detail']}")
    if len(report["breaking"]) > 20:
        lines.append(f"  ... and {len(report['breaking']) - 20} more breaking finding(s)")
    for adv in report["advisories"][:10]:
        lines.append(f"  [ADVISORY:{adv['category']}] {adv['detail']}")
    if len(report["advisories"]) > 10:
        lines.append(f"  ... and {len(report['advisories']) - 10} more advisory note(s)")
    return "\n".join(lines) + "\n"
