"""Option B (recommended default) Loading-Screen Override Builder & Verifier (`FO4SFLoadScreens.esm`).

Per owner-decision tracking rule (pending owner choice between Option A vs Option B and
blank tip text vs converted Fallout4.esm tip text in docs/world/loading-screens-options.md):
- Option B (condition all 304 Starfield.esm LSCR records off + ship FO4SF_LSCR_* records) and
- Blank DESC tip text (b"\\x00") with clean black background DDS
are implemented as RECOMMENDED DEFAULTS only and remain reversible without touching Starfield.esm.
"""

from __future__ import annotations

import os
import struct
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from fo4sf.planet.esm import COMPRESSED, ESM, LOCALIZED, Plugin, PluginWriter, Record, zbytes, zstring

SUPPRESS_GLOBAL_LOCAL_ID = 0x000800
SUPPRESS_GLOBAL_EDID = "FO4SF_SuppressVanillaLoadScreens"
DEFAULT_LSCR_STRATEGY = "Option B (recommended default pending owner confirmation)"
DEFAULT_TIP_TEXT_MODE = "blank (recommended default pending owner confirmation)"
DEFAULT_BLANK_ICON_PATH = r"Data\textures\interface\loadscreens\fo4sf_load_blank_color.dds"

# CTDA function 74 (0x004A) = GetGlobalValue, Subject/Player-independent global comparison.
CTDA_FUNC_GET_GLOBAL_VALUE = 74
CTDA_STRUCT = struct.Struct("<B3xfHHIIIII")  # 32 bytes: op_flags, pad3, value, func, pad2, param1, param2, runOn, ref, swap

DEFAULT_FALLOUT_SCREENS: Tuple[Tuple[int, str, str], ...] = (
    (0x000801, "FO4SF_LSCR_Vault111", DEFAULT_BLANK_ICON_PATH),
    (0x000802, "FO4SF_LSCR_Commonwealth", DEFAULT_BLANK_ICON_PATH),
    (0x000803, "FO4SF_LSCR_Sanctuary", DEFAULT_BLANK_ICON_PATH),
    (0x000804, "FO4SF_LSCR_FarHarbor", DEFAULT_BLANK_ICON_PATH),
)


def pack_get_global_ctda(glob_formid: int, target_value: float, *, or_flag: bool = False) -> bytes:
    """Pack a 32-byte Creation Engine CTDA checking `GetGlobalValue(glob) == target_value`.

    Operator byte:
      - bits 5..7 = compare op (`0` = Equal `==`)
      - bit 0 (0x01) = OR (`0` = AND)
    """
    op_flags = 0x01 if or_flag else 0x00
    return CTDA_STRUCT.pack(
        op_flags,
        float(target_value),
        CTDA_FUNC_GET_GLOBAL_VALUE,
        0,
        int(glob_formid) & 0xFFFFFFFF,
        0,
        0,
        0,
        0xFFFFFFFF,
    )


def unpack_ctda_header(data: bytes) -> Dict[str, Any]:
    """Decode key fields of a 32-byte CTDA subrecord for tests and offline verification."""
    if len(data) != CTDA_STRUCT.size:
        raise ValueError(f"expected {CTDA_STRUCT.size}-byte CTDA, got {len(data)}")
    op_flags, value, func, _pad2, param1, param2, run_on, ref, swap = CTDA_STRUCT.unpack(data)
    return {
        "op_flags": op_flags,
        "is_or": bool(op_flags & 0x01),
        "compare_op": (op_flags >> 5) & 0x07,
        "value": value,
        "func": func,
        "param1": param1,
        "param2": param2,
        "run_on": run_on,
        "ref": ref,
        "swap": swap,
    }


def generate_black_dds_bytes(width: int = 8, height: int = 8) -> bytes:
    """Generate a minimal valid uncompressed 32-bit RGBA `.dds` (all-black alpha=255)."""
    header_size = 124
    flags = 0x1 | 0x2 | 0x4 | 0x1000  # CAPS | HEIGHT | WIDTH | PIXELFORMAT
    pitch = width * 4
    pf = struct.pack(
        "<IIIIIIII",
        32,       # dwSize
        0x41,     # DDPF_RGB | DDPF_ALPHAPIXELS
        0,        # dwFourCC
        32,       # dwRGBBitCount
        0x00FF0000,
        0x0000FF00,
        0x000000FF,
        0xFF000000,
    )
    caps = struct.pack("<IIIIII", 0x1000, 0, 0, 0, 0, 0)  # DDSCAPS_TEXTURE + reserved
    hdr = b"DDS " + struct.pack("<IIIIIII", header_size, flags, height, width, pitch, 0, 0) + (b"\x00" * 44) + pf + caps
    pixels = b"\x00\x00\x00\xff" * (width * height)
    return hdr + pixels


def _override_vanilla_lscr(rec: Record, glob_formid: int, *, blank_desc: bytes = b"\x00") -> Record:
    """Clone a Starfield.esm LSCR as an unlocalized override gated off by `glob == 0.0`."""
    new_subs: List[Tuple[bytes, bytes]] = []
    inserted_ctda = False
    prepend_ctda = (b"CTDA", pack_get_global_ctda(glob_formid, 0.0, or_flag=False))
    for sig, data in rec.subs:
        if sig == b"DESC":
            # Overriding into an unlocalized plugin must emit a plain NUL-terminated string, never a 4-byte lstring ID.
            new_subs.append((b"DESC", blank_desc))
        elif sig == b"CTDA":
            if not inserted_ctda:
                new_subs.append(prepend_ctda)
                inserted_ctda = True
            new_subs.append((sig, data))
        else:
            new_subs.append((sig, data))
    if not inserted_ctda:
        new_subs.append(prepend_ctda)
    return Record(
        b"LSCR",
        rec.formid,
        new_subs,
        flags=rec.flags & ~(COMPRESSED | LOCALIZED),
        vc=0,
        version=rec.version,
        unknown=0,
    )


def build_load_screens_bytes(
    starfield_esm: Path | str,
    *,
    fallout_screens: Optional[Sequence[Tuple[int, str, str]]] = DEFAULT_FALLOUT_SCREENS,
    initial_suppress: float = 1.0,
) -> Tuple[bytes, Dict[str, Any]]:
    """Build `FO4SFLoadScreens.esm` (Option B default) in memory from `starfield_esm`."""
    w = PluginWriter(
        ["Starfield.esm"],
        flags=ESM,  # Unlocalized master (LOCALIZED 0x80 OFF) so DESC is plain zstring
        author="FO4SF",
        description="Suppresses Starfield LSCRs via FO4SF_SuppressVanillaLoadScreens and adds FO4SF LSCR pool (Option B default)",
    )
    glob_fid = w.own(SUPPRESS_GLOBAL_LOCAL_ID)
    w.add(
        Record(
            b"GLOB",
            glob_fid,
            [(b"EDID", zbytes(SUPPRESS_GLOBAL_EDID)), (b"FLTV", struct.pack("<f", float(initial_suppress)))],
        )
    )

    override_count = 0
    or_chain_preserved = 0
    with Plugin(str(starfield_esm)) as sf:
        for rec in sf.records("LSCR"):
            existing_ctdas = [d for s, d in rec.subs if s == b"CTDA"]
            if any((d[0] & 0x01) for d in existing_ctdas):
                or_chain_preserved += 1
            w.add(_override_vanilla_lscr(rec, glob_fid))
            override_count += 1

    screens = list(DEFAULT_FALLOUT_SCREENS if fallout_screens is None else fallout_screens)
    custom_ctda = pack_get_global_ctda(glob_fid, 1.0, or_flag=False)
    for local_id, edid, icon in screens:
        w.add(
            Record(
                b"LSCR",
                w.own(local_id),
                [
                    (b"EDID", zbytes(edid)),
                    (b"DESC", b"\x00"),  # Blank tip text (recommended default pending owner decision)
                    (b"ICON", zbytes(icon)),
                    (b"CTDA", custom_ctda),
                ],
                flags=0,
                vc=0,
                version=581,
                unknown=0,
            )
        )

    summary = {
        "strategy": DEFAULT_LSCR_STRATEGY,
        "tip_text_mode": DEFAULT_TIP_TEXT_MODE,
        "suppress_global_edid": SUPPRESS_GLOBAL_EDID,
        "suppress_global_formid": f"0x{glob_fid:08X}",
        "initial_suppress": float(initial_suppress),
        "vanilla_override_count": override_count,
        "or_chain_overrides": or_chain_preserved,
        "custom_fallout_lscr_count": len(screens),
        "custom_edids": [edid for _, edid, _ in screens],
    }
    return w.to_bytes(compress=False), summary


def write_load_screens_plugin(
    starfield_esm: Path | str,
    out_path: Path | str,
    *,
    fallout_screens: Optional[Sequence[Tuple[int, str, str]]] = DEFAULT_FALLOUT_SCREENS,
    initial_suppress: float = 1.0,
    write_blank_icon_under_data: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """Write `FO4SFLoadScreens.esm` and optionally the generated black placeholder `.dds`."""
    data, summary = build_load_screens_bytes(
        starfield_esm,
        fallout_screens=fallout_screens,
        initial_suppress=initial_suppress,
    )
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    if write_blank_icon_under_data is not None:
        dds_path = Path(write_blank_icon_under_data) / DEFAULT_BLANK_ICON_PATH.replace("Data\\", "").replace("\\", "/")
        dds_path.parent.mkdir(parents=True, exist_ok=True)
        dds_path.write_bytes(generate_black_dds_bytes())
        summary["blank_dds_path"] = str(dds_path)
    summary["out_path"] = str(out)
    summary["size_bytes"] = len(data)
    return summary


def verify_load_screens_plugin(plugin_path: Path | str, starfield_esm: Path | str) -> Dict[str, Any]:
    """Roundtrip-check generated `FO4SFLoadScreens.esm` against `starfield_esm`."""
    with Plugin(str(starfield_esm)) as sf:
        vanilla_fids = [rec.formid for rec in sf.records("LSCR")]

    with Plugin(str(plugin_path)) as plug:
        if plug.localized:
            raise AssertionError("FO4SFLoadScreens.esm must NOT set LOCALIZED (0x80)")
        if plug.masters != ["Starfield.esm"]:
            raise AssertionError(f"expected masters ['Starfield.esm'], got {plug.masters}")

        globs = list(plug.records("GLOB"))
        suppr = [g for g in globs if g.edid == SUPPRESS_GLOBAL_EDID]
        if len(suppr) != 1:
            raise AssertionError(f"expected 1 {SUPPRESS_GLOBAL_EDID} GLOB, found {len(suppr)}")
        fltv = suppr[0].get(b"FLTV")
        if fltv is None or abs(struct.unpack("<f", fltv)[0] - 1.0) > 1e-6:
            raise AssertionError("FO4SF_SuppressVanillaLoadScreens default FLTV must be 1.0")
        glob_fid = suppr[0].formid

        overrides: Dict[int, Record] = {}
        customs: List[Record] = []
        for rec in plug.records("LSCR"):
            master_idx = (rec.formid >> 24) & 0xFF
            if master_idx == 0:
                overrides[rec.formid] = rec
            elif master_idx == plug.self_index:
                customs.append(rec)
            else:
                raise AssertionError(f"unexpected master index in LSCR {rec.formid:08X}")

        if set(overrides.keys()) != set(vanilla_fids):
            missing = len(set(vanilla_fids) - set(overrides.keys()))
            extra = len(set(overrides.keys()) - set(vanilla_fids))
            raise AssertionError(f"vanilla LSCR override mismatch (missing={missing}, extra={extra})")

        for fid, rec in overrides.items():
            desc = rec.get(b"DESC")
            if desc != b"\x00":
                raise AssertionError(f"override 0x{fid:08X} must carry blank zstring DESC b'\\x00', got {desc!r}")
            ctdas = rec.all(b"CTDA")
            if not ctdas:
                raise AssertionError(f"override 0x{fid:08X} has zero CTDAs")
            first = unpack_ctda_header(ctdas[0])
            if first["func"] != CTDA_FUNC_GET_GLOBAL_VALUE or first["param1"] != glob_fid or first["value"] != 0.0 or first["is_or"]:
                raise AssertionError(f"override 0x{fid:08X} first CTDA invalid: {first}")

        if not customs:
            raise AssertionError("expected >= 1 custom FO4SF_LSCR_* record for Option B default")
        for rec in customs:
            if rec.get(b"DESC") != b"\x00":
                raise AssertionError(f"custom {rec.edid} DESC must be blank zstring default b'\\x00'")
            ctdas = rec.all(b"CTDA")
            if not ctdas:
                raise AssertionError(f"custom {rec.edid} missing suppression == 1.0 CTDA")
            first = unpack_ctda_header(ctdas[0])
            if first["func"] != CTDA_FUNC_GET_GLOBAL_VALUE or first["param1"] != glob_fid or first["value"] != 1.0 or first["is_or"]:
                raise AssertionError(f"custom {rec.edid} CTDA invalid: {first}")

    return {
        "ok": True,
        "vanilla_override_count": len(overrides),
        "custom_count": len(customs),
        "suppress_global_formid": f"0x{glob_fid:08X}",
    }
