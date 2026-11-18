"""Stage-time assets and marker store for the Fallout 4 Pip-Boy MAP slices 1-4 (docs/ui/pipboy-map-s1-s4.md).

Nothing copyrighted or machine-specific enters Git: all outputs are generated privately on the player's machine at stage
time from their own Fallout 4 and ported Starfield files.

Capabilities:
  1. Pure-Python BC1 (DXT1) DDS decoder -> 1-frame SWF v12 wrapper (`Components/FO4SF_WorldMap.swf`, 2048x2048 twip-exact
     `DefineBitsLossless2` + `DefineShape3` smoothed bitmap fill), avoiding D3D12 `img://WorldMap` reverse engineering.
  2. Surgical `DoABC` / `DoABC1` constant-pool UTF-8 string patcher for `Pipboy_MapPage.swf`, rewriting `"img://WorldMap"`
     -> `"Components/FO4SF_WorldMap.swf"` and `"PipboyMessageBox.swf"` -> `"Components/PipboyMessageBox.swf"` so both
     ride cleanly through `pipboy_probe_install.py --component-movie` without shadowing vanilla `Interface/*.swf` files.
  3. Pure-Python `FO4SFPipboyTravel.esm` writer (`Starfield.esm` master, `ESM` flag) emitting `GLOB` records `0x800..0x807`
     (travel target local FormID, plugin code, survival flag, store index, merged arrival X/Y/Z/heading) and
     `0x810..0x81D` (`FO4SF_MapDisc00..13`, 24 integer bits per `float32` `TESGlobal`, exact up to 2^24).
  4. Forward/inverse Commonwealth <-> merged planet coordinate transforms and `FO4SFPipboyMapMarkers.tsv` serializer.
"""
import argparse
import json
import math
import os
import re
import struct
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
if os.path.join(REPO, "src") not in sys.path:
    sys.path.insert(0, os.path.join(REPO, "src"))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from fo4sf.map_markers import MAP_MARKER_TYPES_JSON, MAPMARKER_STAT  # noqa: E402
from fo4sf.planet.esm import ESM, Plugin, PluginWriter, Record, zbytes, zstring  # noqa: E402
import make_probe_swf as swf  # noqa: E402
import pipboy_probe_install as pbi  # noqa: E402

DEFINE_BITS_LOSSLESS2 = 36
DO_ABC1, DO_ABC = 72, 82

# Canonical Fallout 4 Commonwealth world-map parameters (WRLD 0x0000003C MNAM outer cell edges)
COMMONWEALTH_NW = (-135168.0, 106496.0)
COMMONWEALTH_NE = (118784.0, 106496.0)
COMMONWEALTH_SW = (-135168.0, -147456.0)
DIAMOND_CITY_WRLD = 0x00000F94
DIAMOND_CITY_ONAM = (1.0, -16384.0, -27852.80078125, 3072.0)

FO4_UNITS_PER_M = 70.0
MERGE_OFFSET_X = -1200.0
MERGE_OFFSET_Y = -2700.0

WORLDMAP_URL_ORIG = "img://WorldMap"
WORLDMAP_URL_PATCHED = "Components/FO4SF_WorldMap.swf"
MSGBOX_URL_ORIG = "PipboyMessageBox.swf"
MSGBOX_URL_PATCHED = "Components/PipboyMessageBox.swf"

FO4_STAT_COMPONENT_PREFIXES = (
    "Interface/Components/ConditionClips/",
    "Interface/Components/VaultBoys/SPECIAL/",
    "Interface/Components/VaultBoys/Perks/",
)

TRAVEL_PLUGIN = "FO4SFPipboyTravel.esm"
GLOB_TRAVEL_TARGET = 0x800
GLOB_TRAVEL_PLUGIN = 0x801
GLOB_SURVIVAL_MODE = 0x802
GLOB_TRAVEL_INDEX = 0x803
GLOB_TRAVEL_X = 0x804
GLOB_TRAVEL_Y = 0x805
GLOB_TRAVEL_Z = 0x806
GLOB_TRAVEL_H = 0x807
GLOB_DISC_FIRST = 0x810
DISC_GLOBAL_COUNT = 14
BITS_PER_GLOBAL = 24

TSV_HEADER = (
    "index\tplugin_code\tlocal_id_hex\ttype\tinit_disc\t"
    "x_fo4\ty_fo4\tarr_x_sf\tarr_y_sf\tarr_z_sf\tarr_h_deg\tlabel"
)


class MapStoreError(ValueError):
    pass


def refuse_unsafe_output_path(path):
    """Refuse writing converted/staged game files inside any Git worktree or game install directory (Rule R4)."""
    target = os.path.abspath(os.fspath(path))
    cur = target if os.path.isdir(target) else os.path.dirname(target)
    visited = set()
    while cur and cur not in visited:
        visited.add(cur)
        if os.path.exists(os.path.join(cur, ".git")):
            raise MapStoreError(f"refused output path inside Git worktree: {target}")
        if os.path.isfile(os.path.join(cur, "Starfield.exe")) or os.path.isfile(os.path.join(cur, "Fallout4.exe")):
            raise MapStoreError(f"refused output path inside game directory: {target}")
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return target


# ------------------------------------------------------------------------------------------------ coordinates & bitsets
def project_child_world(x_fo4, y_fo4, world_formid=0x0000003C):
    """Project child worldspace coordinates onto canonical Commonwealth world-map coordinates."""
    if world_formid == DIAMOND_CITY_WRLD:
        scale, dx, dy, _ = DIAMOND_CITY_ONAM
        return x_fo4 * scale + dx, y_fo4 * scale + dy
    return float(x_fo4), float(y_fo4)


def fo4_to_sf_merged(x_fo4, y_fo4, world_formid=0x0000003C):
    """Convert Fallout 4 world coordinates into merged Starfield planet runtime coordinates (metres)."""
    cx, cy = project_child_world(x_fo4, y_fo4, world_formid)
    return cx / FO4_UNITS_PER_M + MERGE_OFFSET_X, cy / FO4_UNITS_PER_M + MERGE_OFFSET_Y


def sf_merged_to_fo4(x_sf, y_sf):
    """Convert merged Starfield planet runtime coordinates (metres) into canonical Fallout 4 Commonwealth units."""
    return (float(x_sf) - MERGE_OFFSET_X) * FO4_UNITS_PER_M, (float(y_sf) - MERGE_OFFSET_Y) * FO4_UNITS_PER_M


def world_to_map_pixel(x_fo4, y_fo4, tex_size=2048):
    """Project canonical Commonwealth FO4 coordinates onto usable pixel coordinates on WorldMap_d.dds."""
    left_gutter = 55.0 / 2048.0 * tex_size
    right_gutter = 58.0 / 2048.0 * tex_size
    usable = tex_size - left_gutter - right_gutter
    u = (x_fo4 - COMMONWEALTH_NW[0]) / (COMMONWEALTH_NE[0] - COMMONWEALTH_NW[0])
    v = (COMMONWEALTH_NW[1] - y_fo4) / (COMMONWEALTH_NW[1] - COMMONWEALTH_SW[1])
    return left_gutter + u * usable, left_gutter + v * usable


def pack_discovery_bits(discovered_flags, num_globals=DISC_GLOBAL_COUNT, bits_per_global=BITS_PER_GLOBAL):
    """Pack boolean discovery flags into `num_globals` integers of at most `bits_per_global` (24) bits each."""
    if bits_per_global > 24:
        raise MapStoreError("TESGlobal float32 requires <= 24 bits per global for exact integer round-trip")
    capacity = num_globals * bits_per_global
    if len(discovered_flags) > capacity:
        raise MapStoreError(f"{len(discovered_flags)} markers exceed bitset capacity {capacity}")
    out = [0] * num_globals
    for idx, flag in enumerate(discovered_flags):
        if flag:
            out[idx // bits_per_global] |= 1 << (idx % bits_per_global)
    return out


def unpack_discovery_bits(global_values, count, bits_per_global=BITS_PER_GLOBAL):
    """Unpack `count` boolean discovery flags from 24-bit TESGlobal float/int values."""
    flags = []
    for idx in range(count):
        grp = idx // bits_per_global
        bit = idx % bits_per_global
        raw = int(round(float(global_values[grp]))) if grp < len(global_values) else 0
        flags.append(bool((raw >> bit) & 1))
    return flags


# ------------------------------------------------------------------------------------------------ BC1 DDS -> SWF v12
def _rgb565(c):
    r = ((c >> 11) & 0x1F) * 255 // 31
    g = ((c >> 5) & 0x3F) * 255 // 63
    b = (c & 0x1F) * 255 // 31
    return r, g, b


def decode_bc1(block_bytes, width, height):
    """Decode BC1 / DXT1 compressed blocks into `width * height * 4` premultiplied ARGB bytes (`[A, R, G, B]`)."""
    if width <= 0 or height <= 0 or width % 4 or height % 4:
        raise MapStoreError(f"BC1 dimensions must be positive multiples of 4, got {width}x{height}")
    bx, by = width // 4, height // 4
    need = bx * by * 8
    if len(block_bytes) < need:
        raise MapStoreError(f"BC1 buffer has {len(block_bytes)} bytes, need {need} for {width}x{height}")
    out = bytearray(width * height * 4)
    mv = memoryview(block_bytes)
    pos = 0
    for ty in range(by):
        base_y = ty * 4
        for tx in range(bx):
            c0, c1, idx_bits = struct.unpack_from("<HHI", mv, pos)
            pos += 8
            r0, g0, b0 = _rgb565(c0)
            r1, g1, b1 = _rgb565(c1)
            if c0 > c1:
                pal = (
                    bytes((255, r0, g0, b0)),
                    bytes((255, r1, g1, b1)),
                    bytes((255, (2 * r0 + r1 + 1) // 3, (2 * g0 + g1 + 1) // 3, (2 * b0 + b1 + 1) // 3)),
                    bytes((255, (r0 + 2 * r1 + 1) // 3, (g0 + 2 * g1 + 1) // 3, (b0 + 2 * b1 + 1) // 3)),
                )
            else:
                pal = (
                    bytes((255, r0, g0, b0)),
                    bytes((255, r1, g1, b1)),
                    bytes((255, (r0 + r1) // 2, (g0 + g1) // 2, (b0 + b1) // 2)),
                    bytes((0, 0, 0, 0)),
                )
            base_x = tx * 4
            for py in range(4):
                row_off = ((base_y + py) * width + base_x) * 4
                row_codes = (idx_bits >> (py * 8)) & 0xFF
                out[row_off:row_off + 4] = pal[row_codes & 0x03]
                out[row_off + 4:row_off + 8] = pal[(row_codes >> 2) & 0x03]
                out[row_off + 8:row_off + 12] = pal[(row_codes >> 4) & 0x03]
                out[row_off + 12:row_off + 16] = pal[(row_codes >> 6) & 0x03]
    return bytes(out)


def parse_dds_bc1(dds_bytes):
    """Parse a `DDS ` BC1/DXT1 file (legacy FourCC `DXT1` or DX10 `BC1_UNORM` 71/72) and decode mip 0 to ARGB."""
    if len(dds_bytes) < 128 or dds_bytes[:4] != b"DDS ":
        raise MapStoreError("not a DDS texture")
    hdr_size, _flags, height, width = struct.unpack_from("<IIII", dds_bytes, 4)
    if hdr_size != 124:
        raise MapStoreError(f"unexpected DDS header size {hdr_size}")
    fourcc = dds_bytes[84:88]
    data_off = 128
    if fourcc == b"DX10":
        if len(dds_bytes) < 148:
            raise MapStoreError("truncated DX10 DDS header")
        dxgi_fmt = struct.unpack_from("<I", dds_bytes, 128)[0]
        if dxgi_fmt not in (70, 71, 72):
            raise MapStoreError(f"unsupported DXGI format {dxgi_fmt} (expected BC1 70/71/72)")
        data_off = 148
    elif fourcc not in (b"DXT1", b"BC1 "):
        raise MapStoreError(f"unsupported DDS FourCC {fourcc!r} (expected DXT1 or DX10 BC1)")
    mip0_bytes = (width // 4) * (height // 4) * 8
    if len(dds_bytes) < data_off + mip0_bytes:
        raise MapStoreError("DDS mip0 payload truncated")
    return width, height, decode_bc1(dds_bytes[data_off:data_off + mip0_bytes], width, height)


def _bitmap_scale_matrix_20x():
    """SWF MATRIX mapping 1 bitmap pixel to 20 twips (`ScaleX = ScaleY = 20.0` in 16.16 fixed point)."""
    fixed = 20 << 16
    nbits = swf.sb_bits(fixed, fixed)
    b = swf.Bits()
    b.ub(1, 1)          # HasScale = 1
    b.ub(nbits, 5)
    b.sb(fixed, nbits)  # ScaleX
    b.sb(fixed, nbits)  # ScaleY
    b.ub(0, 1)          # HasRotate = 0
    b.ub(0, 5)          # NTranslateBits = 0
    return b.align()


def worldmap_swf_bytes(argb_bytes, width=2048, height=2048):
    """Build a deterministic 1-frame compressed SWF v12 (`CWS`) displaying an ARGB bitmap at `width x height` pixels."""
    if width <= 0 or height <= 0 or len(argb_bytes) != width * height * 4:
        raise MapStoreError(f"ARGB byte length {len(argb_bytes)} does not match {width}x{height}*4")
    w_twips, h_twips = width * swf.TWIPS, height * swf.TWIPS
    bmp_body = struct.pack("<HBHH", 1, 5, width, height) + zlib.compress(argb_bytes, 6)
    bounds = swf.rect(0, w_twips, 0, h_twips)
    fill_style = bytes([1, 0x41]) + struct.pack("<H", 1) + _bitmap_scale_matrix_20x() + bytes([0])
    shape_body = struct.pack("<H", 2) + bounds + fill_style + swf.square_records([(0, 0, w_twips, h_twips)], "worldmap")
    tags = b"".join((
        swf.tag(swf.FILE_ATTRIBUTES, struct.pack("<I", swf.AS3)),
        swf.tag(DEFINE_BITS_LOSSLESS2, bmp_body),
        swf.tag(swf.DEFINE_SHAPE3, shape_body),
        swf.place_object2(2, 1),
        swf.tag(swf.SHOW_FRAME),
        swf.tag(swf.END),
    ))
    body = bounds + struct.pack("<HH", swf.FRAME_RATE << 8, 1) + tags
    return b"CWS" + bytes([swf.VERSION]) + struct.pack("<I", 8 + len(body)) + zlib.compress(body, 6)


# ------------------------------------------------------------------------------------------------ DoABC string patcher
def _read_u30(buf, pos):
    val = shift = 0
    while True:
        if pos >= len(buf):
            raise MapStoreError("ABC u30 read past end")
        b = buf[pos]
        pos += 1
        val |= (b & 0x7F) << shift
        shift += 7
        if not (b & 0x80) or shift >= 35:
            return val, pos


def _pack_u30(val):
    if val < 0:
        raise MapStoreError(f"negative u30 {val}")
    out = bytearray()
    while True:
        byte = val & 0x7F
        val >>= 7
        if val:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def _patch_abc_strings(abc_bytes, replacements):
    """Rewrite exact UTF-8 strings in an AVM2 ABC constant pool, preserving indices and all trailing tables/bodies."""
    pos = 4  # minor (u16), major (u16)
    if len(abc_bytes) < 8:
        raise MapStoreError("ABC block too short")
    for _ in ("ints", "uints"):
        cnt, pos = _read_u30(abc_bytes, pos)
        for _i in range(max(cnt - 1, 0)):
            _, pos = _read_u30(abc_bytes, pos)
    dbl_cnt, pos = _read_u30(abc_bytes, pos)
    pos += 8 * max(dbl_cnt - 1, 0)
    if pos > len(abc_bytes):
        raise MapStoreError("ABC doubles run past end")

    str_start = pos
    str_cnt, pos = _read_u30(abc_bytes, pos)
    rebuilt = bytearray(_pack_u30(str_cnt))
    counts = {k: 0 for k in replacements}
    for _ in range(max(str_cnt - 1, 0)):
        slen, pos = _read_u30(abc_bytes, pos)
        if pos + slen > len(abc_bytes):
            raise MapStoreError("ABC string runs past end")
        raw_s = bytes(abc_bytes[pos:pos + slen])
        pos += slen
        try:
            decoded = raw_s.decode("utf-8")
        except UnicodeDecodeError:
            decoded = None
        if decoded in replacements:
            counts[decoded] += 1
            raw_s = replacements[decoded].encode("utf-8")
        rebuilt += _pack_u30(len(raw_s)) + raw_s
    patched = bytes(abc_bytes[:str_start]) + bytes(rebuilt) + bytes(abc_bytes[pos:])
    return patched, counts


def _skip_abc_traits(buf, pos, count):
    for _ in range(count):
        _, pos = _read_u30(buf, pos)  # name
        if pos >= len(buf):
            raise MapStoreError("ABC trait kind past end")
        kind_byte = buf[pos]
        pos += 1
        tag, attrs = kind_byte & 0x0F, kind_byte >> 4
        if tag in (0, 6):
            _, pos = _read_u30(buf, pos)  # slot_id
            _, pos = _read_u30(buf, pos)  # type_name
            vindex, pos = _read_u30(buf, pos)
            if vindex != 0:
                pos += 1  # vkind
        elif tag in (1, 2, 3, 4, 5):
            _, pos = _read_u30(buf, pos)  # disp_id / slot_id
            _, pos = _read_u30(buf, pos)  # method / classi / function
        else:
            raise MapStoreError(f"unsupported ABC trait kind {tag}")
        if attrs & 0x04:
            mcnt, pos = _read_u30(buf, pos)
            for _m in range(mcnt):
                _, pos = _read_u30(buf, pos)
    return pos


def _parse_abc_multinames_and_bodies(abc_bytes):
    """Return `(multiname_names, body_ranges)` for an AVM2 ABC block without modifying bytes."""
    pos = 4
    if len(abc_bytes) < 8:
        raise MapStoreError("ABC block too short")
    for _ in ("ints", "uints"):
        cnt, pos = _read_u30(abc_bytes, pos)
        for _i in range(max(cnt - 1, 0)):
            _, pos = _read_u30(abc_bytes, pos)
    dbl_cnt, pos = _read_u30(abc_bytes, pos)
    pos += 8 * max(dbl_cnt - 1, 0)

    str_cnt, pos = _read_u30(abc_bytes, pos)
    strings = [""]
    for _ in range(max(str_cnt - 1, 0)):
        slen, pos = _read_u30(abc_bytes, pos)
        raw_s = bytes(abc_bytes[pos:pos + slen])
        pos += slen
        strings.append(raw_s.decode("utf-8", errors="replace"))

    ns_cnt, pos = _read_u30(abc_bytes, pos)
    for _ in range(max(ns_cnt - 1, 0)):
        pos += 1  # kind
        _, pos = _read_u30(abc_bytes, pos)

    nss_cnt, pos = _read_u30(abc_bytes, pos)
    for _ in range(max(nss_cnt - 1, 0)):
        c, pos = _read_u30(abc_bytes, pos)
        for _j in range(c):
            _, pos = _read_u30(abc_bytes, pos)

    mn_cnt, pos = _read_u30(abc_bytes, pos)
    mn_names = [""]
    for _ in range(max(mn_cnt - 1, 0)):
        if pos >= len(abc_bytes):
            raise MapStoreError("ABC multiname kind past end")
        kind = abc_bytes[pos]
        pos += 1
        name_idx = 0
        if kind in (0x07, 0x0D):  # QName, QNameA
            _, pos = _read_u30(abc_bytes, pos)
            name_idx, pos = _read_u30(abc_bytes, pos)
        elif kind in (0x0F, 0x10):  # RTQName, RTQNameA
            name_idx, pos = _read_u30(abc_bytes, pos)
        elif kind in (0x11, 0x12):  # RTQNameL, RTQNameLA
            pass
        elif kind in (0x09, 0x0E):  # Multiname, MultinameA
            name_idx, pos = _read_u30(abc_bytes, pos)
            _, pos = _read_u30(abc_bytes, pos)
        elif kind in (0x1B, 0x1C):  # MultinameL, MultinameLA
            _, pos = _read_u30(abc_bytes, pos)
        elif kind == 0x1D:  # TypeName (Vector.<T>)
            _, pos = _read_u30(abc_bytes, pos)
            pcnt, pos = _read_u30(abc_bytes, pos)
            for _p in range(pcnt):
                _, pos = _read_u30(abc_bytes, pos)
        else:
            raise MapStoreError(f"unsupported ABC multiname kind {kind:#x}")
        mn_names.append(strings[name_idx] if 0 <= name_idx < len(strings) else "")

    if pos >= len(abc_bytes):
        return mn_names, []

    meth_cnt, pos = _read_u30(abc_bytes, pos)
    for _ in range(meth_cnt):
        pcnt, pos = _read_u30(abc_bytes, pos)
        _, pos = _read_u30(abc_bytes, pos)  # return_type
        for _p in range(pcnt):
            _, pos = _read_u30(abc_bytes, pos)
        _, pos = _read_u30(abc_bytes, pos)  # name
        flags = abc_bytes[pos]
        pos += 1
        if flags & 0x08:
            ocnt, pos = _read_u30(abc_bytes, pos)
            for _o in range(ocnt):
                _, pos = _read_u30(abc_bytes, pos)
                pos += 1
        if flags & 0x80:
            for _p in range(pcnt):
                _, pos = _read_u30(abc_bytes, pos)

    meta_cnt, pos = _read_u30(abc_bytes, pos)
    for _ in range(meta_cnt):
        _, pos = _read_u30(abc_bytes, pos)
        icnt, pos = _read_u30(abc_bytes, pos)
        for _i in range(icnt):
            _, pos = _read_u30(abc_bytes, pos)
            _, pos = _read_u30(abc_bytes, pos)

    cls_cnt, pos = _read_u30(abc_bytes, pos)
    for _ in range(cls_cnt):
        _, pos = _read_u30(abc_bytes, pos)  # name
        _, pos = _read_u30(abc_bytes, pos)  # super_name
        cflags = abc_bytes[pos]
        pos += 1
        if cflags & 0x08:
            _, pos = _read_u30(abc_bytes, pos)
        icnt, pos = _read_u30(abc_bytes, pos)
        for _i in range(icnt):
            _, pos = _read_u30(abc_bytes, pos)
        _, pos = _read_u30(abc_bytes, pos)  # iinit
        tcnt, pos = _read_u30(abc_bytes, pos)
        pos = _skip_abc_traits(abc_bytes, pos, tcnt)
    for _ in range(cls_cnt):
        _, pos = _read_u30(abc_bytes, pos)  # cinit
        tcnt, pos = _read_u30(abc_bytes, pos)
        pos = _skip_abc_traits(abc_bytes, pos, tcnt)

    scr_cnt, pos = _read_u30(abc_bytes, pos)
    for _ in range(scr_cnt):
        _, pos = _read_u30(abc_bytes, pos)  # init
        tcnt, pos = _read_u30(abc_bytes, pos)
        pos = _skip_abc_traits(abc_bytes, pos, tcnt)

    body_cnt, pos = _read_u30(abc_bytes, pos)
    bodies = []
    for _ in range(body_cnt):
        for _hdr in range(5):  # method, max_stack, local_count, init_scope_depth, max_scope_depth
            _, pos = _read_u30(abc_bytes, pos)
        code_len, pos = _read_u30(abc_bytes, pos)
        code_start = pos
        code_end = pos + code_len
        if code_end > len(abc_bytes):
            raise MapStoreError("ABC method body code runs past end")
        bodies.append((code_start, code_end))
        pos = code_end
        exc_cnt, pos = _read_u30(abc_bytes, pos)
        for _e in range(exc_cnt):
            for _ef in range(5):
                _, pos = _read_u30(abc_bytes, pos)
        tcnt, pos = _read_u30(abc_bytes, pos)
        pos = _skip_abc_traits(abc_bytes, pos, tcnt)
    return mn_names, bodies


def _patch_abc_map_loader_unload(abc_bytes):
    """Neutralize `MapImageLoader.unloadAndStop(...)` inside `TextureMapHolder.onMapLoadComplete` method bodies while
    leaving `MessageLoader.unloadAndStop(...)` and `loader.unload()` in `Pipboy_MapPage.CloseMessage` untouched.

    Replaces `callpropvoid <unloadAndStop>, 0` (immediately preceded by `getproperty/getlex <MapImageLoader>`) with
    equal-length `pop (0x29) + nop (0x02)...` so stack balance, `code_length`, and all jump/exception offsets stay exact.
    """
    mn_names, bodies = _parse_abc_multinames_and_bodies(abc_bytes)
    if not bodies:
        return abc_bytes, 0
    loader_mns = [i for i, n in enumerate(mn_names) if n == "MapImageLoader"]
    unload_mns = [i for i, n in enumerate(mn_names) if n == "unloadAndStop"]
    if not loader_mns or not unload_mns:
        return abc_bytes, 0

    prefixes = [bytes([op]) + _pack_u30(mn) for mn in loader_mns for op in (0x66, 0x60)]  # getproperty, getlex
    calls_0 = [b"\x4f" + _pack_u30(mn) + b"\x00" for mn in unload_mns]  # callpropvoid <unloadAndStop>, 0
    calls_1_bool = [bytes([bop]) + b"\x4f" + _pack_u30(mn) + b"\x01" for mn in unload_mns for bop in (0x26, 0x27)]

    out = bytearray(abc_bytes)
    patched_count = 0
    for start, end in bodies:
        for pref in prefixes:
            for call_seq in calls_0 + calls_1_bool:
                pattern = pref + call_seq
                search_at = start
                while True:
                    idx = out.find(pattern, search_at, end)
                    if idx < 0:
                        break
                    call_off = idx + len(pref)
                    call_len = len(call_seq)
                    # Pop the MapImageLoader reference pushed by getproperty/getlex, pad remaining bytes with nop (0x02)
                    out[call_off:call_off + call_len] = b"\x29" + (b"\x02" * (call_len - 1))
                    patched_count += 1
                    search_at = call_off + call_len
    return bytes(out), patched_count


def inspect_mappage_unload_calls(swf_bytes):
    """Count active `MapImageLoader.unloadAndStop`, `MessageLoader.unloadAndStop`, and `.unload()` calls in SWF DoABC."""
    if len(swf_bytes) < 8 or swf_bytes[:3] not in (b"CWS", b"FWS"):
        raise MapStoreError("input is not a CWS or FWS SWF")
    body = zlib.decompress(swf_bytes[8:]) if swf_bytes[:3] == b"CWS" else swf_bytes[8:]
    nbits = body[0] >> 3
    pos = (5 + 4 * nbits + 7) // 8 + 4
    summary = {"MapImageLoader.unloadAndStop": 0, "MessageLoader.unloadAndStop": 0, "unload": 0}
    while pos + 2 <= len(body):
        head = struct.unpack_from("<H", body, pos)[0]
        code, size = head >> 6, head & 0x3F
        pos += 2
        if size == 0x3F:
            size = struct.unpack_from("<I", body, pos)[0]
            pos += 4
        payload = bytes(body[pos:pos + size])
        pos += size
        abc = None
        if code == DO_ABC:
            nul = payload.find(b"\x00", 4)
            if nul >= 0:
                abc = payload[nul + 1:]
        elif code == DO_ABC1:
            abc = payload
        if abc is not None:
            mn_names, bodies = _parse_abc_multinames_and_bodies(abc)
            map_mns = [i for i, n in enumerate(mn_names) if n == "MapImageLoader"]
            msg_mns = [i for i, n in enumerate(mn_names) if n == "MessageLoader"]
            ustop_mns = [i for i, n in enumerate(mn_names) if n == "unloadAndStop"]
            unload_mns = [i for i, n in enumerate(mn_names) if n == "unload"]
            for bstart, bend in bodies:
                chunk = abc[bstart:bend]
                for lmn in map_mns:
                    for umn in ustop_mns:
                        for op in (0x66, 0x60):
                            summary["MapImageLoader.unloadAndStop"] += chunk.count(
                                bytes([op]) + _pack_u30(lmn) + b"\x4f" + _pack_u30(umn)
                            )
                for mmn in msg_mns:
                    for umn in ustop_mns:
                        for op in (0x66, 0x60):
                            summary["MessageLoader.unloadAndStop"] += chunk.count(
                                bytes([op]) + _pack_u30(mmn) + b"\x4f" + _pack_u30(umn)
                            )
                for umn in unload_mns:
                    summary["unload"] += chunk.count(b"\x4f" + _pack_u30(umn))
        if code == swf.END:
            break
    return summary


def patch_map_page_swf(swf_bytes, worldmap_url=WORLDMAP_URL_PATCHED, msgbox_url=MSGBOX_URL_PATCHED):
    """Rewrite `img://WorldMap` and `PipboyMessageBox.swf` in `Pipboy_MapPage.swf` DoABC constant pool and neutralize
    `TextureMapHolder.onMapLoadComplete`'s `MapImageLoader.unloadAndStop()` so `FO4SF_WorldMap.swf` stays rendered."""
    if len(swf_bytes) < 8 or swf_bytes[:3] not in (b"CWS", b"FWS"):
        raise MapStoreError("input is not a CWS or FWS SWF")
    version = swf_bytes[3]
    body = zlib.decompress(swf_bytes[8:]) if swf_bytes[:3] == b"CWS" else swf_bytes[8:]
    if not body:
        raise MapStoreError("empty SWF body")
    nbits = body[0] >> 3
    header_end = (5 + 4 * nbits + 7) // 8 + 4
    if header_end > len(body):
        raise MapStoreError("truncated SWF frame header")

    replacements = {}
    if worldmap_url:
        replacements[WORLDMAP_URL_ORIG] = worldmap_url
    if msgbox_url:
        replacements[MSGBOX_URL_ORIG] = msgbox_url

    total_counts = {k: 0 for k in replacements}
    out_tags = bytearray()
    pos = header_end
    saw_end = False
    while pos + 2 <= len(body):
        head = struct.unpack_from("<H", body, pos)[0]
        code, size = head >> 6, head & 0x3F
        pos += 2
        if size == 0x3F:
            if pos + 4 > len(body):
                raise MapStoreError("truncated long tag header")
            size = struct.unpack_from("<I", body, pos)[0]
            pos += 4
        if pos + size > len(body):
            raise MapStoreError(f"tag {code} runs past SWF body")
        payload = bytes(body[pos:pos + size])
        pos += size
        if code == DO_ABC:
            nul = payload.find(b"\x00", 4)
            if nul < 0:
                raise MapStoreError("DoABC tag missing name terminator")
            abc_patched, c = _patch_abc_strings(payload[nul + 1:], replacements)
            abc_patched, _ = _patch_abc_map_loader_unload(abc_patched)
            for k, v in c.items():
                total_counts[k] += v
            payload = payload[:nul + 1] + abc_patched
        elif code == DO_ABC1:
            payload, c = _patch_abc_strings(payload, replacements)
            payload, _ = _patch_abc_map_loader_unload(payload)
            for k, v in c.items():
                total_counts[k] += v
        out_tags += swf.tag(code, payload)
        if code == swf.END:
            saw_end = True
            break
    if not saw_end:
        raise MapStoreError("SWF missing End tag")

    new_body = bytes(body[:header_end]) + bytes(out_tags)
    out_swf = b"CWS" + bytes([version]) + struct.pack("<I", 8 + len(new_body)) + zlib.compress(new_body, 6)
    return out_swf, total_counts


patch_mappage_swf = patch_map_page_swf


def stage_fo4_stat_components(fo4_interface_ba2, out_interface_dir, include_perks=True):
    """Extract Fallout 4 Pip-Boy STAT component SWFs (`ConditionClips`, `VaultBoys/SPECIAL`, and optionally
    `VaultBoys/Perks`) from a local `Fallout4 - Interface.ba2` into `<out_interface_dir>/Components/...` so switching
    between STATUS, SPECIAL, and PERKS tabs never hits a missing-SWF `IOErrorEvent`.

    Returns the sorted list of component specifiers suitable for `pipboy_probe_install.py --component-movie`.
    """
    refuse_unsafe_output_path(out_interface_dir)
    from fo4sf.ba2 import Ba2
    prefixes = FO4_STAT_COMPONENT_PREFIXES if include_perks else FO4_STAT_COMPONENT_PREFIXES[:2]
    lower_prefixes = tuple(p.lower() for p in prefixes)
    archive = Ba2(fo4_interface_ba2)
    staged = []
    for idx, entry in enumerate(archive.entries):
        norm = entry.name.replace("\\", "/")
        low = norm.lower()
        if not low.endswith(".swf") or not low.startswith(lower_prefixes):
            continue
        # Canonicalize leading "Interface/Components/" prefix for pipboy_probe_install.py
        rel_after_iface = "Components/" + norm[len("Interface/Components/"):]
        comp_spec = rel_after_iface[:-4]  # strip .swf
        dst = os.path.join(out_interface_dir, *rel_after_iface.split("/"))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        raw = archive.read(entry.name)
        with open(dst, "wb") as f:
            f.write(raw)
        why = pbi.swf_problem(dst)
        if why:
            raise MapStoreError(f"extracted component {rel_after_iface} failed SWF check: {why}")
        staged.append(comp_spec)
    staged.sort(key=str.lower)
    return staged


def stage_fo4_boot_movie(fo4_interface_ba2, out_interface_dir, dst_name="pipboybootsequence"):
    """Extract `Interface/PipboyBootSequence.swf` from a local `Fallout4 - Interface.ba2` into `<out_interface_dir>/<dst_name>.swf`."""
    refuse_unsafe_output_path(out_interface_dir)
    if not dst_name or not re.fullmatch(r"[A-Za-z0-9_]{1,64}", dst_name):
        raise MapStoreError(f"invalid boot movie name: {dst_name!r}")
    from fo4sf.ba2 import Ba2
    archive = Ba2(fo4_interface_ba2)
    matched_entry = None
    for entry in archive.entries:
        if entry.name.replace("\\", "/").lower() == "interface/pipboybootsequence.swf":
            matched_entry = entry
            break
    if matched_entry is None:
        raise MapStoreError("Interface/PipboyBootSequence.swf not found in archive")
    os.makedirs(out_interface_dir, exist_ok=True)
    dst = os.path.join(out_interface_dir, f"{dst_name}.swf")
    raw = archive.read(matched_entry.name)
    with open(dst, "wb") as f:
        f.write(raw)
    why = pbi.swf_problem(dst)
    if why:
        raise MapStoreError(f"extracted boot movie {dst_name}.swf failed SWF check: {why}")
    return dst_name


def stage_fo4_special_movie(fo4_interface_ba2, out_interface_dir, dst_name="fo4sf_specialmenu"):
    """Extract `Interface/SPECIALMenu.swf` from a local `Fallout4 - Interface.ba2` into `<out_interface_dir>/<dst_name>.swf`."""
    refuse_unsafe_output_path(out_interface_dir)
    if not dst_name or not re.fullmatch(r"[A-Za-z0-9_]{1,64}", dst_name):
        raise MapStoreError(f"invalid special menu movie name: {dst_name!r}")
    from fo4sf.ba2 import Ba2
    archive = Ba2(fo4_interface_ba2)
    matched_entry = None
    for entry in archive.entries:
        if entry.name.replace("\\", "/").lower() == "interface/specialmenu.swf":
            matched_entry = entry
            break
    if matched_entry is None:
        raise MapStoreError("Interface/SPECIALMenu.swf not found in archive")
    os.makedirs(out_interface_dir, exist_ok=True)
    dst = os.path.join(out_interface_dir, f"{dst_name}.swf")
    raw = archive.read(matched_entry.name)
    with open(dst, "wb") as f:
        f.write(raw)
    why = pbi.swf_problem(dst)
    if why:
        raise MapStoreError(f"extracted special menu movie {dst_name}.swf failed SWF check: {why}")
    return dst_name


# ------------------------------------------------------------------------------------------------ travel ESM & store TSV
def _glob_record(formid, edid, value=0.0):
    return Record(b"GLOB", formid, [(b"EDID", zbytes(edid)), (b"FLTV", struct.pack("<f", float(value)))])


def travel_plugin_bytes(survival=False, initial_disc_bits=()):
    """Build `FO4SFPipboyTravel.esm` holding travel target/coord globals and 14 x 24-bit discovery globals.

    Hardcore fast-travel blocking lives exclusively in `FO4SFCoreValues.esm:0x000841` (`FO4SF_HardcoreFastTravelBlocked`),
    so `FO4SFPipboyTravel.esm` carries no static `0x802` survival authority (`survival` arg kept unused for CLI compatibility).
    """
    _ = survival
    w = PluginWriter(["Starfield.esm"], flags=ESM, author="FO4SF", description="Pip-Boy MAP travel and discovery bridge")
    fixed = (
        (GLOB_TRAVEL_TARGET, "FO4SF_PipboyTravelTarget", 0.0),
        (GLOB_TRAVEL_PLUGIN, "FO4SF_PipboyTravelPlugin", 0.0),
        (GLOB_TRAVEL_INDEX, "FO4SF_PipboyTravelIndex", -1.0),
        (GLOB_TRAVEL_X, "FO4SF_PipboyTravelX", 0.0),
        (GLOB_TRAVEL_Y, "FO4SF_PipboyTravelY", 0.0),
        (GLOB_TRAVEL_Z, "FO4SF_PipboyTravelZ", 0.0),
        (GLOB_TRAVEL_H, "FO4SF_PipboyTravelH", 0.0),
    )
    for local_id, edid, val in fixed:
        w.add(_glob_record(w.own(local_id), edid, val))
    for i in range(DISC_GLOBAL_COUNT):
        bits = int(initial_disc_bits[i]) if i < len(initial_disc_bits) else 0
        if bits < 0 or bits >= (1 << BITS_PER_GLOBAL):
            raise MapStoreError(f"discovery bitset {i} out of 24-bit range: {bits}")
        w.add(_glob_record(w.own(GLOB_DISC_FIRST + i), f"FO4SF_MapDisc{i:02d}", float(bits)))
    return w.to_bytes(compress=False)


def write_travel_plugin(path, survival=False, initial_disc_bits=()):
    data = travel_plugin_bytes(survival=survival, initial_disc_bits=initial_disc_bits)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    return len(data)


def format_store_tsv(rows):
    """Serialize marker store dictionaries into `FO4SFPipboyMapMarkers.tsv` text."""
    lines = [TSV_HEADER]
    for idx, r in enumerate(rows):
        label = str(r.get("label", f"LOC_{idx:03d}")).replace("\t", " ").replace("\r", "").replace("\n", "").strip()
        lines.append(
            f"{int(r.get('index', idx))}\t"
            f"{int(r.get('plugin_code', 0))}\t"
            f"{int(r['local_id']) & 0xFFFFFF:06X}\t"
            f"{int(r.get('type', 0))}\t"
            f"{1 if r.get('init_disc', False) else 0}\t"
            f"{float(r['x_fo4']):.2f}\t"
            f"{float(r['y_fo4']):.2f}\t"
            f"{float(r['arr_x_sf']):.3f}\t"
            f"{float(r['arr_y_sf']):.3f}\t"
            f"{float(r['arr_z_sf']):.3f}\t"
            f"{float(r.get('arr_h_deg', 0.0)):.2f}\t"
            f"{label}"
        )
    return "\n".join(lines) + "\n"


def parse_store_tsv(text):
    """Parse `FO4SFPipboyMapMarkers.tsv` back into structured dictionaries."""
    rows = []
    for line_no, raw in enumerate(text.splitlines(), 1):
        line = raw.strip("\r")
        if not line or line.startswith("#") or (line_no == 1 and line.startswith("index\t")):
            continue
        cols = line.split("\t")
        if len(cols) < 11:
            raise MapStoreError(f"line {line_no}: expected >= 11 columns, got {len(cols)}")
        rows.append({
            "index": int(cols[0]),
            "plugin_code": int(cols[1]),
            "local_id": int(cols[2], 16) & 0xFFFFFF,
            "type": int(cols[3]),
            "init_disc": int(cols[4]) != 0,
            "x_fo4": float(cols[5]),
            "y_fo4": float(cols[6]),
            "arr_x_sf": float(cols[7]),
            "arr_y_sf": float(cols[8]),
            "arr_z_sf": float(cols[9]),
            "arr_h_deg": float(cols[10]),
            "label": cols[11] if len(cols) >= 12 else f"LOC_{int(cols[0]):03d}",
        })
    return rows


# Pipboy_MapPage MarkerTypesA reserves 85 = PlayerSetMarker and 86 = PlayerLocMarker; location icons lie in 0..80.
MAX_FO4_LOCATION_ICON = 80
DEFAULT_FO4_ICON = 5  # Landmark
CORE_FIXED_FO4_ICONS = {
    "FO4Core_CommonwealthMapMarker": 27,          # Filling Station (Red Rocket)
    "FO4Core_CommonwealthMapMarkerSanctuary": 12, # Sanctuary
    "FO4Core_CommonwealthMapMarkerVault111": 15,  # Vault
    "FO4Core_CommonwealthMapMarkerConcord": 49,   # Town
}
LANDING_MARKER_LOCAL_ID = 0x0008F2
DEFAULT_CORE_Z_LIFT = 2.5


def _sf_to_fo4_icon_map(types_json_path=MAP_MARKER_TYPES_JSON):
    with open(types_json_path, encoding="utf-8") as f:
        doc = json.load(f)
    inv = {}
    for row in doc.get("types", []):
        fo4_id = int(row["fo4_id"])
        sf_type = int(row["sf_type"])
        if 0 <= fo4_id <= MAX_FO4_LOCATION_ICON and sf_type not in inv:
            inv[sf_type] = fo4_id
    return inv


def _iter_xmrk_refrs(plugin):
    """Yield placed `REFR` records carrying an `XMRK` map-marker subrecord inside `WRLD` or `CELL` groups."""
    for grp_name in ("WRLD", "CELL"):
        for start, end in plugin.groups.get(grp_name, []):
            for item in plugin.walk(start, end):
                if item[0] != "REC" or item[2] != b"REFR":
                    continue
                rec = Record.parse(plugin.buf, item[1])
                if rec.index(b"XMRK") < 0:
                    continue
                name_sub = rec.get(b"NAME")
                if name_sub is not None and len(name_sub) == 4:
                    base_id = struct.unpack_from("<I", name_sub, 0)[0]
                    if (base_id & 0xFFFFFF) != MAPMARKER_STAT:
                        continue
                yield rec


def _parse_xmrk_record(rec):
    data_sub = rec.get(b"DATA")
    if data_sub is None or len(data_sub) < 12:
        raise MapStoreError(f"REFR {rec.formid:08X} ({rec.edid}) missing 12+ byte DATA position")
    vals = struct.unpack_from("<6f" if len(data_sub) >= 24 else "<3f", data_sub, 0)
    x_m, y_m, z_m = vals[0], vals[1], vals[2]
    rz = vals[5] if len(vals) >= 6 else 0.0
    full_sub = rec.get(b"FULL")
    label = zstring(full_sub).strip() if full_sub else ""
    tnam_sub = rec.get(b"TNAM")
    sf_tnam = struct.unpack_from("<H", tnam_sub, 0)[0] if tnam_sub and len(tnam_sub) >= 2 else None
    fnam_sub = rec.get(b"FNAM")
    fnam = struct.unpack_from("<I", fnam_sub, 0)[0] if fnam_sub and len(fnam_sub) >= 4 else (
        fnam_sub[0] if fnam_sub else 0
    )
    return {
        "formid": rec.formid,
        "local_id": rec.formid & 0xFFFFFF,
        "edid": rec.edid,
        "label": label or rec.edid or f"LOC_{rec.formid & 0xFFFFFF:06X}",
        "x_m": x_m,
        "y_m": y_m,
        "z_m": z_m,
        "h_deg": (math.degrees(rz) % 360.0),
        "sf_tnam": sf_tnam,
        "fnam": fnam,
    }


def _fo4_export_types(fo4_export_path):
    """Map source FO4 hex FormID (`int`) -> FO4 `type_id` (`0..80`) from a `Fo4Land` `export-mapmarkers` JSON."""
    if not fo4_export_path:
        return {}
    with open(fo4_export_path, encoding="utf-8-sig") as f:
        doc = json.load(f)
    out = {}
    for r in doc.get("markers") or []:
        tid = r.get("type_id")
        if tid is not None and "fid" in r:
            iv = int(tid)
            if 0 <= iv <= MAX_FO4_LOCATION_ICON:
                out[int(r["fid"], 16) & 0xFFFFFF] = iv
    return out


def build_store_rows(
    core_esm,
    markers_esm="",
    fo4_export="",
    z_lift=DEFAULT_CORE_Z_LIFT,
    discover=(),
    include_landing=False,
):
    """Build ordered Pip-Boy MAP store rows from the project's `FO4TerrainCore.esm` and optional `FO4SFMapMarkers.esm`.

    - Core-owned markers (`FO4TerrainCore.esm`) carry `plugin_code = 1`; `FO4SFMapMarkers.esm`-owned extra markers
      carry `plugin_code = 0` (`0x000900..`). When `markers_esm` is provided, its overrides of the core's markers
      supply their lifted `DATA` height and `FULL` label while keeping `plugin_code = 1`.
    - `init_disc` defaults to `False` unless the marker's `FNAM` already carries engine `kDiscovered` (`0x20`) or its
      EditorID / label is listed in `discover`: in game, live discovery comes from the engine's `ExtraMapMarker` state
      (`SetMarkerDiscovered` bit `0x20`) synced into `FO4SF_MapDisc00..13`.
    """
    sf_to_fo4 = _sf_to_fo4_icon_map()
    export_types = _fo4_export_types(fo4_export)
    disc_set = {s.strip().casefold() for s in discover if s and s.strip()}

    with Plugin(core_esm) as pc:
        core_self = pc.self_index
        core_by_local = {}
        for rec in _iter_xmrk_refrs(pc):
            if (rec.formid >> 24) == core_self:
                info = _parse_xmrk_record(rec)
                core_by_local[info["local_id"]] = info

    if not core_by_local:
        raise MapStoreError(f"{os.path.basename(core_esm)} has no own XMRK MapMarker REFRs")

    core_ordered = [core_by_local[k] for k in sorted(core_by_local)]
    extra_ordered = []
    has_markers_plugin = bool(markers_esm)

    if has_markers_plugin:
        with Plugin(markers_esm) as pm:
            pm_self = pm.self_index
            for rec in _iter_xmrk_refrs(pm):
                info = _parse_xmrk_record(rec)
                top = rec.formid >> 24
                if top < pm_self and info["local_id"] in core_by_local:
                    # Override of a core marker (carries lifted Z and cleared UseLocationName)
                    merged = dict(core_by_local[info["local_id"]])
                    merged.update({k: v for k, v in info.items() if v not in ("", None)})
                    core_by_local[info["local_id"]] = merged
                elif top == pm_self:
                    if info["local_id"] == LANDING_MARKER_LOCAL_ID and not include_landing:
                        continue
                    extra_ordered.append(info)
        core_ordered = [core_by_local[k] for k in sorted(core_by_local)]
        extra_ordered.sort(key=lambda r: r["local_id"])

    capacity = DISC_GLOBAL_COUNT * BITS_PER_GLOBAL
    combined = [(1, r) for r in core_ordered] + [(0, r) for r in extra_ordered]
    if len(combined) > capacity:
        raise MapStoreError(f"{len(combined)} markers exceed 24-bit discovery store capacity ({capacity})")

    rows = []
    for idx, (plugin_code, info) in enumerate(combined):
        edid = info["edid"]
        fo4_icon = CORE_FIXED_FO4_ICONS.get(edid)
        if fo4_icon is None:
            m = re.search(r"M([0-9A-Fa-f]{6})$", edid)
            if m:
                fo4_icon = export_types.get(int(m.group(1), 16))
        if fo4_icon is None and info["sf_tnam"] is not None:
            fo4_icon = sf_to_fo4.get(info["sf_tnam"])
        if fo4_icon is None or not (0 <= fo4_icon <= MAX_FO4_LOCATION_ICON):
            fo4_icon = DEFAULT_FO4_ICON

        arr_z = info["z_m"] if has_markers_plugin else (info["z_m"] + float(z_lift))
        init_disc = bool(info["fnam"] & 0x20) or (
            edid.casefold() in disc_set or info["label"].casefold() in disc_set
        )
        rows.append({
            "index": idx,
            "plugin_code": plugin_code,
            "local_id": info["local_id"],
            "type": fo4_icon,
            "init_disc": init_disc,
            "x_fo4": info["x_m"] * FO4_UNITS_PER_M,
            "y_fo4": info["y_m"] * FO4_UNITS_PER_M,
            "arr_x_sf": info["x_m"] + MERGE_OFFSET_X,
            "arr_y_sf": info["y_m"] + MERGE_OFFSET_Y,
            "arr_z_sf": arr_z,
            "arr_h_deg": info["h_deg"],
            "label": info["label"],
        })
    return rows


def write_store_tsv(path, rows):
    text = format_store_tsv(rows)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return len(rows)


def run_self_test():
    """Offline synthetic verification of BC1->SWF, DoABC string patching, 24-bit globals, and coord transforms."""
    # 1. Synthetic 8x8 BC1 DDS -> SWF container validation
    blk = struct.pack("<HHI", 0xF800, 0x07E0, 0x55AA55AA) * 4
    dds = b"DDS " + struct.pack("<IIII", 124, 0x1007, 8, 8) + bytes(64) + b"DXT1" + bytes(40) + blk
    w, h, argb = parse_dds_bc1(dds)
    assert (w, h, len(argb)) == (8, 8, 256)
    wm_swf = worldmap_swf_bytes(argb, w, h)
    assert pbi.swf_problem_bytes(wm_swf) is None if hasattr(pbi, "swf_problem_bytes") else len(wm_swf) > 32

    # 2. Synthetic DoABC constant pool rewrite
    pool = [WORLDMAP_URL_ORIG.encode(), b"KeepMe", MSGBOX_URL_ORIG.encode()]
    abc = struct.pack("<HH", 16, 46) + b"\x00\x00\x00" + _pack_u30(len(pool) + 1)
    abc += b"".join(_pack_u30(len(s)) + s for s in pool)
    doabc = struct.pack("<I", 1) + b"frame1\x00" + abc
    raw_body = swf.rect(0, 17520, 0, 14000) + struct.pack("<HH", 30 << 8, 1) + swf.tag(DO_ABC, doabc) + swf.tag(swf.END)
    src_swf = b"CWS" + bytes([12]) + struct.pack("<I", 8 + len(raw_body)) + zlib.compress(raw_body)
    patched, counts = patch_map_page_swf(src_swf)
    assert counts == {WORLDMAP_URL_ORIG: 1, MSGBOX_URL_ORIG: 1}
    assert WORLDMAP_URL_PATCHED.encode() in zlib.decompress(patched[8:])

    # 3. Vault 111 coordinate round-trip
    sf_x, sf_y = fo4_to_sf_merged(-89271.7, 91369.6)
    rx, ry = sf_merged_to_fo4(sf_x, sf_y)
    assert abs(rx - (-89271.7)) < 1e-4 and abs(ry - 91369.6) < 1e-4
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Stage private Pip-Boy MAP assets and travel/discovery store")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_wm = sub.add_parser("stage-worldmap", help="Convert local WorldMap_d.dds into Components/FO4SF_WorldMap.swf")
    p_wm.add_argument("--dds", required=True, help="Path to local WorldMap_d.dds")
    p_wm.add_argument("--out", required=True, help="Destination SWF path (e.g. <stage>/Data/Interface/Components/FO4SF_WorldMap.swf)")

    p_mp = sub.add_parser("patch-mappage", help="Patch img://WorldMap and PipboyMessageBox.swf in staged Pipboy_MapPage.swf")
    p_mp.add_argument("--src", required=True, help="Source Pipboy_MapPage.swf")
    p_mp.add_argument("--out", required=True, help="Destination staged Pipboy_MapPage.swf")
    p_mp.add_argument("--worldmap-url", default=WORLDMAP_URL_PATCHED)
    p_mp.add_argument("--msgbox-url", default=MSGBOX_URL_PATCHED)

    p_bs = sub.add_parser("build-store", help="Build FO4SFPipboyMapMarkers.tsv from FO4TerrainCore.esm / FO4SFMapMarkers.esm")
    p_bs.add_argument("--core", required=True, help="Path to FO4TerrainCore.esm")
    p_bs.add_argument("--markers-esm", default="", help="Optional path to FO4SFMapMarkers.esm (overrides + extra markers)")
    p_bs.add_argument("--fo4-map-markers", default="", help="Optional Fo4Land export-mapmarkers JSON for exact FO4 icon types")
    p_bs.add_argument("--z-lift", type=float, default=DEFAULT_CORE_Z_LIFT, help="Arrival Z lift in m when --markers-esm is omitted")
    p_bs.add_argument("--discover", action="append", default=[], help="Marker label or EditorID initially discovered (repeatable)")
    p_bs.add_argument("--include-landing", action="store_true", help="Include the 0x8F2 ship landing marker if present")
    p_bs.add_argument("--out", required=True, help="Output FO4SFPipboyMapMarkers.tsv path")

    p_tr = sub.add_parser("stage-travel-esm", help="Write FO4SFPipboyTravel.esm with travel and discovery GLOBs")
    p_tr.add_argument("--out", required=True, help="Output FO4SFPipboyTravel.esm path")
    p_tr.add_argument("--store", default="", help="Optional FO4SFPipboyMapMarkers.tsv to seed initial FO4SF_MapDisc00..13 bits")
    p_tr.add_argument("--survival", action="store_true", help="Initialize FO4SF_SurvivalMode to 1")

    p_fc = sub.add_parser(
        "stage-fo4-components",
        help="Extract ConditionClips and VaultBoys/SPECIAL (+ Perks) SWFs from Fallout4 - Interface.ba2 into Data/Interface",
    )
    p_fc.add_argument("--ba2", required=True, help="Path to local Fallout4 - Interface.ba2")
    p_fc.add_argument("--interface-dir", required=True, help="Destination <stage>/Data/Interface directory")
    p_fc.add_argument("--no-perks", action="store_true", help="Skip VaultBoys/Perks/*.swf")

    p_sm = sub.add_parser(
        "stage-special-menu",
        help="Extract SPECIALMenu.swf from Fallout4 - Interface.ba2 into Data/Interface/<dst_name>.swf",
    )
    p_sm.add_argument("--ba2", required=True, help="Path to local Fallout4 - Interface.ba2")
    p_sm.add_argument("--interface-dir", required=True, help="Destination <stage>/Data/Interface directory")
    p_sm.add_argument("--dst-name", default="fo4sf_specialmenu", help="Destination base SWF name")

    sub.add_parser("self-test", help="Run synthetic offline self-checks")

    args = ap.parse_args(argv)
    if args.cmd == "self-test":
        return run_self_test()
    if args.cmd == "build-store":
        rows = build_store_rows(
            args.core,
            markers_esm=args.markers_esm,
            fo4_export=args.fo4_map_markers,
            z_lift=args.z_lift,
            discover=args.discover,
            include_landing=args.include_landing,
        )
        n = write_store_tsv(args.out, rows)
        print(f"wrote {n} marker row(s) to {os.path.basename(args.out)}")
        return 0
    if args.cmd == "stage-worldmap":
        refuse_unsafe_output_path(args.out)
        with open(args.dds, "rb") as f:
            w, h, argb = parse_dds_bc1(f.read())
        data = worldmap_swf_bytes(argb, w, h)
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "wb") as f:
            f.write(data)
        why = pbi.swf_problem(args.out)
        if why:
            raise SystemExit(f"generated SWF failed container check: {why}")
        print(f"wrote {w}x{h} world map SWF ({len(data)} bytes)")
        return 0
    if args.cmd == "patch-mappage":
        refuse_unsafe_output_path(args.out)
        with open(args.src, "rb") as f:
            patched, counts = patch_map_page_swf(f.read(), args.worldmap_url, args.msgbox_url)
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "wb") as f:
            f.write(patched)
        why = pbi.swf_problem(args.out)
        if why:
            raise SystemExit(f"patched SWF failed container check: {why}")
        print(f"patched Pipboy_MapPage.swf replacements={counts}")
        return 0
    if args.cmd == "stage-travel-esm":
        init_bits = ()
        if args.store:
            with open(args.store, encoding="utf-8") as f:
                parsed = parse_store_tsv(f.read())
            init_bits = pack_discovery_bits([r["init_disc"] for r in parsed])
        n = write_travel_plugin(args.out, survival=args.survival, initial_disc_bits=init_bits)
        print(f"wrote {TRAVEL_PLUGIN} ({n} bytes)")
        return 0
    if args.cmd == "stage-fo4-components":
        staged = stage_fo4_stat_components(args.ba2, args.interface_dir, include_perks=not args.no_perks)
        print(f"staged {len(staged)} component SWF(s) into {args.interface_dir}")
        return 0
    if args.cmd == "stage-special-menu":
        name = stage_fo4_special_movie(args.ba2, args.interface_dir, dst_name=args.dst_name)
        print(f"staged {name}.swf into {args.interface_dir}")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
