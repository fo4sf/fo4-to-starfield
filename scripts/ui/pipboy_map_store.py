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
import os
import struct
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
if os.path.join(REPO, "src") not in sys.path:
    sys.path.insert(0, os.path.join(REPO, "src"))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from fo4sf.planet.esm import ESM, PluginWriter, Record, zbytes  # noqa: E402
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


def patch_map_page_swf(swf_bytes, worldmap_url=WORLDMAP_URL_PATCHED, msgbox_url=MSGBOX_URL_PATCHED):
    """Rewrite `img://WorldMap` and `PipboyMessageBox.swf` in `Pipboy_MapPage.swf` DoABC constant pool."""
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
            for k, v in c.items():
                total_counts[k] += v
            payload = payload[:nul + 1] + abc_patched
        elif code == DO_ABC1:
            payload, c = _patch_abc_strings(payload, replacements)
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


# ------------------------------------------------------------------------------------------------ travel ESM & store TSV
def _glob_record(formid, edid, value=0.0):
    return Record(b"GLOB", formid, [(b"EDID", zbytes(edid)), (b"FLTV", struct.pack("<f", float(value)))])


def travel_plugin_bytes(survival=False, initial_disc_bits=()):
    """Build `FO4SFPipboyTravel.esm` holding travel target/coord globals and 14 x 24-bit discovery globals."""
    w = PluginWriter(["Starfield.esm"], flags=ESM, author="FO4SF", description="Pip-Boy MAP travel and discovery bridge")
    fixed = (
        (GLOB_TRAVEL_TARGET, "FO4SF_PipboyTravelTarget", 0.0),
        (GLOB_TRAVEL_PLUGIN, "FO4SF_PipboyTravelPlugin", 0.0),
        (GLOB_SURVIVAL_MODE, "FO4SF_SurvivalMode", 1.0 if survival else 0.0),
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

    p_tr = sub.add_parser("stage-travel-esm", help="Write FO4SFPipboyTravel.esm with travel and discovery GLOBs")
    p_tr.add_argument("--out", required=True, help="Output FO4SFPipboyTravel.esm path")
    p_tr.add_argument("--survival", action="store_true", help="Initialize FO4SF_SurvivalMode to 1")

    sub.add_parser("self-test", help="Run synthetic offline self-checks")

    args = ap.parse_args(argv)
    if args.cmd == "self-test":
        return run_self_test()
    if args.cmd == "stage-worldmap":
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
        n = write_travel_plugin(args.out, survival=args.survival)
        print(f"wrote {TRAVEL_PLUGIN} ({n} bytes)")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
