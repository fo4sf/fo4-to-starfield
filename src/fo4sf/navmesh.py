"""Navmesh geometry (NAVM / NVNM) and navmesh info (NAVI / NVMI) of Fallout 4 and Starfield: read both NVNM layouts,
convert Fallout 4 exterior navmeshes into Starfield's 100 m cells, write Starfield's NVNM and NVMI, validate.

NVNM layouts (docs/actors/navmesh-conversion.md; PR #61 parsed every record of both ESMs exactly):

    u32 version (FO4 15, Starfield 17), u32 magic 0xA5E9A03C, u32 parent worldspace FormID, then
        worldspace != 0: i16 grid y, i16 grid x        worldspace == 0: u32 parent cell FormID
    u32 n, vertices        FO4 12 B (x, y, z f32, game units)     Starfield 16 B (x, y, z f32 metres, i32 extra)
    u32 n, triangles       21 B: i16 v0, v1, v2; i16 edge 0-1, 1-2, 2-0; f32 height; u8 extra; u16 flags; u16 cover
    u32 n, edge links      11 B: u32 type, u32 navmesh FormID, i16 triangle, u8 edge of that triangle
    u32 n, door triangles  10 B: i16 triangle, u32 extra, u32 door REFR FormID
    u32 n, cover           FO4 8 B, Starfield 12 B (kept as raw bytes)
    u32 n, cover map       4 B: u16 cover, u16 triangle
    u32 n, waypoints       18 B: x, y, z f32, i16 triangle, u32 extra
    u32 grid divisor d, f32 grid cell size x, y, f32 min x, y, z, f32 max x, y, z, then d * d lists (u32 n, i16 ...),
        y-major (list r * d + c covers column c, row r)
    Starfield only: 4 trailing bytes

A triangle edge value is a triangle index of the same navmesh, -1 for none, or (flag bit 1 << edge set) an index into
the edge links; a link names the other navmesh, its triangle and THAT triangle's edge, and links come in symmetric
pairs. FormIDs are stored as in the file (load-order byte = master index). Field order and these semantics were
checked on Fallout4.esm and Starfield.esm (the numbers are in the doc).

NVMI (one per navmesh in the NAVI record; Starfield.esm: all 56,631 entries parse exactly):

    u32 navmesh, u32 flags (0x20: outline present), f32 x, y, z (mean of the navmesh's vertices), f32 (0 in 99 %),
    u32 n + n u32 merged-to (= the navmeshes its edge links reach), u32 n + n u32 preferred merges,
    u32 n + n (u32 door-triangle extra, u32 door REFR) linked doors, u32 n + n * 60 B traversals,
    u8 outline flag [6 f32 bbox, u32 n + n * 3 i16 triangles, u32 n + n * 3 f32 vertices],
    u32 0xA5E9A03C, u32 worldspace, (i16 grid y, i16 grid x | u32 cell), u8 cell-border bits (S 1, E 2, N 4, W 8),
    4 zero bytes.
"""
import math
import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

MAGIC = 0xA5E9A03C
FO4_VERSION = 15
SF_VERSION = 17
UNITS_PER_METRE = 70.0
SF_CELL_M = 100.0
SF_TRAILER = b"\x0c\x00\x08\x00"          # 55,994 of 56,570 vanilla records (PR #61)
FLT_MAX = float(np.finfo(np.float32).max)
NO_CEILING = 1e30                           # heights above this are FLT_MAX: no ceiling over the triangle
DOOR_EXTRA = 0xE48A5FF3                     # the u32 of every door triangle in both games' Red Rocket / Cydonia data
MAX_INDEX = 32767                           # vertex and triangle indices are i16

# triangle flags (Mutagen Starfield NavmeshTriangle.Flag; the same low bits in Fallout 4)
EDGE_LINK_BITS = (0x0001, 0x0002, 0x0004)   # edge 0-1, 1-2, 2-0 is an edge-link index
F_DELETED = 0x0008
F_NO_LARGE_CREATURES = 0x0010
F_OVERLAPPING = 0x0020
F_PREFERRED = 0x0040
F_WATER = 0x0200
F_DOOR = 0x0400
F_FOUND = 0x0800
LINK_MASK = 0x0007

# NVMI
NVMI_OUTLINE = 0x20
BORDER_S, BORDER_E, BORDER_N, BORDER_W = 1, 2, 4, 8

TRI_DTYPE = np.dtype([("v", "<i2", 3), ("e", "<i2", 3), ("height", "<f4"), ("extra", "u1"), ("flags", "<u2"),
                      ("cover", "<u2")])
LINK_DTYPE = np.dtype([("type", "<u4"), ("navmesh", "<u4"), ("tri", "<i2"), ("edge", "u1")])
DOOR_DTYPE = np.dtype([("tri", "<i2"), ("extra", "<u4"), ("door", "<u4")])
COVERMAP_DTYPE = np.dtype([("cover", "<u2"), ("tri", "<u2")])
WAYPOINT_DTYPE = np.dtype([("pos", "<f4", 3), ("tri", "<i2"), ("extra", "<u4")])
assert TRI_DTYPE.itemsize == 21 and LINK_DTYPE.itemsize == 11 and DOOR_DTYPE.itemsize == 10
assert WAYPOINT_DTYPE.itemsize == 18


class NavmeshError(ValueError):
    pass


@dataclass
class Nvnm:
    version: int
    magic: int
    world: int                                  # parent worldspace FormID (0 for an interior navmesh)
    grid: Optional[Tuple[int, int]]             # (x, y) cell grid when world != 0
    cell: Optional[int]                         # parent cell FormID when world == 0
    vertices: np.ndarray                        # float64 (n, 3), file units (FO4 game units, Starfield metres)
    vertex_extra: Optional[np.ndarray]          # int32 (n,) Starfield only
    triangles: np.ndarray                       # TRI_DTYPE
    links: np.ndarray                           # LINK_DTYPE
    doors: np.ndarray                           # DOOR_DTYPE
    cover: List[bytes]
    cover_map: np.ndarray                       # COVERMAP_DTYPE
    waypoints: np.ndarray                       # WAYPOINT_DTYPE
    grid_divisor: int
    grid_size: Tuple[float, float]
    grid_min: Tuple[float, float, float]
    grid_max: Tuple[float, float, float]
    grid_lists: List[List[int]] = field(default_factory=list)
    trailer: bytes = b""

    @property
    def starfield(self):
        return self.version >= SF_VERSION


# ------------------------------------------------------------------------------------------------------------ NVNM
def _arr(b, p, dtype):
    n = struct.unpack_from("<I", b, p)[0]
    p += 4
    end = p + n * dtype.itemsize
    if end > len(b):
        raise NavmeshError(f"{n} x {dtype.itemsize} B array at {p - 4} runs past the end ({len(b)} B)")
    return np.frombuffer(b, dtype, n, p).copy(), end


def parse(b: bytes, layout: Optional[str] = None) -> Nvnm:
    """Parse an NVNM subrecord. layout 'fo4' / 'sf' or None (from the version). The parser must end exactly at the
    end of the data (the check every vanilla record passes, PR #61)."""
    b = bytes(b)
    version, magic, world = struct.unpack_from("<III", b, 0)
    layout = layout or ("sf" if version >= SF_VERSION else "fo4")
    sf = layout == "sf"
    p = 12
    grid = cell = None
    if world:
        gy, gx = struct.unpack_from("<hh", b, p)
        grid = (gx, gy)
    else:
        cell = struct.unpack_from("<I", b, p)[0]
    p += 4
    vsize = 16 if sf else 12
    n = struct.unpack_from("<I", b, p)[0]
    p += 4
    if p + n * vsize > len(b):
        raise NavmeshError("vertices run past the end")
    if sf:
        raw = np.frombuffer(b, np.dtype([("p", "<f4", 3), ("x", "<i4")]), n, p)
        verts, vextra = raw["p"].astype(np.float64), raw["x"].astype(np.int32)
    else:
        verts, vextra = np.frombuffer(b, "<f4", 3 * n, p).reshape(n, 3).astype(np.float64), None
    p += n * vsize
    tris, p = _arr(b, p, TRI_DTYPE)
    if len(tris) and (tris["v"].min() < 0 or tris["v"].max() >= len(verts)):
        raise NavmeshError("triangle vertex index out of range")
    links, p = _arr(b, p, LINK_DTYPE)
    doors, p = _arr(b, p, DOOR_DTYPE)
    csize = 12 if sf else 8
    n = struct.unpack_from("<I", b, p)[0]
    p += 4
    cover = [b[p + i * csize:p + (i + 1) * csize] for i in range(n)]
    p += n * csize
    cmap, p = _arr(b, p, COVERMAP_DTYPE)
    wps, p = _arr(b, p, WAYPOINT_DTYPE)
    div, sx, sy, x0, y0, z0, x1, y1, z1 = struct.unpack_from("<I8f", b, p)
    p += 36
    lists = []
    for _ in range(div * div):
        n = struct.unpack_from("<I", b, p)[0]
        p += 4
        lists.append(list(struct.unpack_from(f"<{n}h", b, p)))
        p += 2 * n
    trailer = b""
    if sf:
        trailer = b[p:p + 4]
        p += 4
    if p != len(b):
        raise NavmeshError(f"parser ended at {p}, data is {len(b)} B")
    return Nvnm(version, magic, world, grid, cell, verts, vextra, tris, links, doors, cover, cmap, wps, div, (sx, sy),
                (x0, y0, z0), (x1, y1, z1), lists, trailer)


def write_sf(m: Nvnm) -> bytes:
    """Starfield (v17) NVNM bytes. vertex_extra defaults to 0, the trailer to SF_TRAILER; cover entries must be 12 B."""
    out = [struct.pack("<III", SF_VERSION, m.magic or MAGIC, m.world)]
    if m.world:
        out.append(struct.pack("<hh", m.grid[1], m.grid[0]))
    else:
        out.append(struct.pack("<I", m.cell or 0))
    v = np.zeros(len(m.vertices), np.dtype([("p", "<f4", 3), ("x", "<i4")]))
    v["p"] = m.vertices
    if m.vertex_extra is not None:
        v["x"] = m.vertex_extra
    out += [struct.pack("<I", len(v)), v.tobytes()]
    for arr, dt in ((m.triangles, TRI_DTYPE), (m.links, LINK_DTYPE), (m.doors, DOOR_DTYPE)):
        out += [struct.pack("<I", len(arr)), np.asarray(arr, dt).tobytes()]
    if any(len(c) != 12 for c in m.cover):
        raise NavmeshError("Starfield cover entries are 12 B")
    out += [struct.pack("<I", len(m.cover))] + list(m.cover)
    for arr, dt in ((m.cover_map, COVERMAP_DTYPE), (m.waypoints, WAYPOINT_DTYPE)):
        out += [struct.pack("<I", len(arr)), np.asarray(arr, dt).tobytes()]
    out.append(struct.pack("<I8f", m.grid_divisor, *m.grid_size, *m.grid_min, *m.grid_max))
    if len(m.grid_lists) != m.grid_divisor * m.grid_divisor:
        raise NavmeshError("grid needs divisor^2 lists")
    for lst in m.grid_lists:
        out.append(struct.pack(f"<I{len(lst)}h", len(lst), *lst))
    out.append(m.trailer if m.starfield and len(m.trailer) == 4 else SF_TRAILER)
    return b"".join(out)


# ------------------------------------------------------------------------------------------------------------ search grid
def grid_divisor(n_triangles: int) -> int:
    """Starfield's grid divisor from the triangle count: 1 up to 16 triangles, then n // 50 + 2, at most 12 (all 1,004
    navmeshes of akilacity, all 2,708 of CydoniaCity; Fallout 4's Red Rocket navmeshes follow it too)."""
    return 1 if n_triangles <= 16 else min(12, n_triangles // 50 + 2)


def _tri_rect(p, x0, y0, x1, y1, eps):
    """Separating-axis test of a 2D triangle (3, 2) against an axis-aligned rectangle, with tolerance eps."""
    if p[:, 0].max() < x0 - eps or p[:, 0].min() > x1 + eps or p[:, 1].max() < y0 - eps or p[:, 1].min() > y1 + eps:
        return False
    corners = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
    area2 = (p[1, 0] - p[0, 0]) * (p[2, 1] - p[0, 1]) - (p[1, 1] - p[0, 1]) * (p[2, 0] - p[0, 0])
    sgn = 1.0 if area2 >= 0 else -1.0
    for i in range(3):
        ax, ay = p[i]
        bx, by = p[(i + 1) % 3]
        nx, ny = (ay - by) * sgn, (bx - ax) * sgn          # inward normal of edge i
        ln = math.hypot(nx, ny)
        if ln == 0:
            continue
        if all((cx - ax) * nx + (cy - ay) * ny < -eps * ln for cx, cy in corners):
            return False
    return True


def build_grid(vertices, triangles, eps=1e-3):
    """(divisor, (size x, y), min xyz, max xyz, lists) as Starfield stores them: min = the vertices' bounding box,
    max x/y = the bounding box, max z = the highest vertex z + triangle height (float32, so FLT_MAX stays FLT_MAX);
    list r * d + c = the triangles whose xy shape touches grid cell (c, r) (eps: 1 mm, a superset at the cell edges)."""
    v = np.asarray(vertices, np.float64)
    t = triangles
    d = grid_divisor(len(t))
    lo, hi = v.min(0), v.max(0)
    zt = np.float32(hi[2])
    if len(t):
        top = (v[t["v"]][:, :, 2].max(1).astype(np.float32) + t["height"].astype(np.float32))
        zt = np.float32(max(float(top.max()), float(hi[2])))
    gmin = tuple(float(np.float32(x)) for x in lo)
    gmax = (float(np.float32(hi[0])), float(np.float32(hi[1])), float(zt))
    sx = float(np.float32((gmax[0] - gmin[0]) / d))
    sy = float(np.float32((gmax[1] - gmin[1]) / d))
    lists = [[] for _ in range(d * d)]
    p2 = v[t["v"]][:, :, :2] if len(t) else np.zeros((0, 3, 2))
    tlo, thi = p2.min(1) if len(t) else None, p2.max(1) if len(t) else None
    for r in range(d):
        for c in range(d):
            x0, y0 = gmin[0] + c * sx, gmin[1] + r * sy
            x1, y1 = x0 + sx, y0 + sy
            if not len(t):
                continue
            cand = np.nonzero((tlo[:, 0] <= x1 + eps) & (thi[:, 0] >= x0 - eps) &
                              (tlo[:, 1] <= y1 + eps) & (thi[:, 1] >= y0 - eps))[0]
            lists[r * d + c] = [int(i) for i in cand if _tri_rect(p2[i], x0, y0, x1, y1, eps)]
    return d, (sx, sy), gmin, gmax, lists


# ------------------------------------------------------------------------------------------------------------ NVMI
@dataclass
class Nvmi:
    navmesh: int
    flags: int
    location: Tuple[float, float, float]
    unknown_f: float
    merged: List[int]
    preferred: List[int]
    doors: List[Tuple[int, int]]
    traversals: List[bytes]
    outline: Optional[tuple]                    # (bbox 6 floats, triangles (n, 3) i16, vertices (n, 3) f32) or None
    world: int
    grid: Optional[Tuple[int, int]]
    cell: Optional[int]
    border: int
    tail: bytes = b"\0\0\0\0"


def parse_nvmi(d: bytes) -> Nvmi:
    d = bytes(d)
    fid, flags, x, y, z, f = struct.unpack_from("<II4f", d, 0)
    p = 24
    lists = []
    for _ in range(2):
        n = struct.unpack_from("<I", d, p)[0]
        p += 4
        lists.append(list(struct.unpack_from(f"<{n}I", d, p)))
        p += 4 * n
    n = struct.unpack_from("<I", d, p)[0]
    p += 4
    doors = [struct.unpack_from("<II", d, p + 8 * i) for i in range(n)]
    p += 8 * n
    n = struct.unpack_from("<I", d, p)[0]
    p += 4
    trav = [d[p + 60 * i:p + 60 * (i + 1)] for i in range(n)]
    p += 60 * n
    outline = None
    if d[p]:
        p += 1
        bbox = struct.unpack_from("<6f", d, p)
        p += 24
        nt = struct.unpack_from("<I", d, p)[0]
        p += 4
        it = np.frombuffer(d, "<i2", 3 * nt, p).reshape(nt, 3).copy()
        p += 6 * nt
        nv = struct.unpack_from("<I", d, p)[0]
        p += 4
        iv = np.frombuffer(d, "<f4", 3 * nv, p).reshape(nv, 3).copy()
        p += 12 * nv
        outline = (bbox, it, iv)
    else:
        p += 1
    crc, world = struct.unpack_from("<II", d, p)
    p += 8
    if crc != MAGIC:
        raise NavmeshError(f"NVMI {fid:08X}: CRC field {crc:08X}")
    grid = cell = None
    if world:
        gy, gx = struct.unpack_from("<hh", d, p)
        grid = (gx, gy)
    else:
        cell = struct.unpack_from("<I", d, p)[0]
    p += 4
    border = d[p]
    tail = d[p + 1:p + 5]
    if p + 5 != len(d):
        raise NavmeshError(f"NVMI {fid:08X}: parser ended at {p + 5}, data is {len(d)} B")
    return Nvmi(fid, flags, (x, y, z), f, lists[0], lists[1], doors, trav, outline, world, grid, cell, border, tail)


def nvmi_data(location, flags=0, unknown_f=0.0) -> bytes:
    """Mutagen's NavigationMapInfo.Data: u32 flags, f32 x, y, z, f32 (20 B)."""
    return struct.pack("<I4f", flags, *location, unknown_f)


def nvmi_unknown(world: int, grid: Tuple[int, int], border: int) -> bytes:
    """Mutagen's NavigationMapInfo.Unknown for an entry without traversals and without outline: u32 0 traversals,
    u8 0, CRC, worldspace (file-local FormID), i16 grid y, i16 grid x, border bits, 4 zero bytes (22 B)."""
    return struct.pack("<IBIIhhB4x", 0, 0, MAGIC, world, grid[1], grid[0], border)


def write_nvmi(e: Nvmi) -> bytes:
    """Whole NVMI bytes (used by tests and the offline check; the plugin writer assembles the same from Mutagen)."""
    out = [struct.pack("<II4f", e.navmesh, e.flags, *e.location, e.unknown_f)]
    for lst in (e.merged, e.preferred):
        out.append(struct.pack(f"<I{len(lst)}I", len(lst), *lst))
    out.append(struct.pack("<I", len(e.doors)) + b"".join(struct.pack("<II", *dd) for dd in e.doors))
    out.append(struct.pack("<I", len(e.traversals)) + b"".join(e.traversals))
    if e.outline is not None:
        bbox, it, iv = e.outline
        out.append(b"\x01" + struct.pack("<6f", *bbox) + struct.pack("<I", len(it)) + np.asarray(it, "<i2").tobytes() +
                   struct.pack("<I", len(iv)) + np.asarray(iv, "<f4").tobytes())
    else:
        out.append(b"\x00")
    out.append(struct.pack("<II", MAGIC, e.world))
    out.append(struct.pack("<hh", e.grid[1], e.grid[0]) if e.world else struct.pack("<I", e.cell or 0))
    out.append(bytes([e.border]) + (e.tail if len(e.tail) == 4 else b"\0\0\0\0"))
    return b"".join(out)


def border_bits(vmin, vmax, cell, cell_m=SF_CELL_M, eps=0.01):
    """NVMI border byte: which edges of its exterior cell the navmesh reaches (S 1, E 2, N 4, W 8; vanilla: the bits
    match the vertex bounding box against the 100 m cell edges in about 16,000 exterior entries)."""
    x0, y0 = cell[0] * cell_m, cell[1] * cell_m
    bits = 0
    if vmin[1] <= y0 + eps:
        bits |= BORDER_S
    if vmax[0] >= x0 + cell_m - eps:
        bits |= BORDER_E
    if vmax[1] >= y0 + cell_m - eps:
        bits |= BORDER_N
    if vmin[0] <= x0 + eps:
        bits |= BORDER_W
    return bits


# ------------------------------------------------------------------------------------------------------------ conversion
@dataclass
class _Pt:
    key: tuple
    pos: tuple                                   # (x, y, z) metres
    edges: frozenset                             # original edges (navmesh, a, b) a < b the point lies on
    lines: frozenset                             # cell lines (axis, value) it lies on


@dataclass
class Piece:
    """One Starfield navmesh: the part of one Fallout 4 navmesh inside one Starfield cell."""
    src: int                                     # Fallout 4 navmesh FormID
    cell: Tuple[int, int]
    keys: List[tuple] = field(default_factory=list)
    pos: List[tuple] = field(default_factory=list)
    tris: List[Tuple[int, int, int]] = field(default_factory=list)
    tri_src: List[int] = field(default_factory=list)    # Fallout 4 triangle index
    neighbours: List[List[int]] = field(default_factory=list)   # per triangle 3 x (tri index, -1, or ('L', link))
    links: List[Tuple[int, int, int, int]] = field(default_factory=list)  # (type, target piece, tri, edge)
    flags: List[int] = field(default_factory=list)
    heights: List[float] = field(default_factory=list)
    doors: List[Tuple[int, int, str]] = field(default_factory=list)   # (tri, extra, door src "XXXXXX:Fallout4.esm")
    waypoints: List[Tuple[tuple, int, int]] = field(default_factory=list)
    index: Dict[tuple, int] = field(default_factory=dict)

    def vertex(self, p: _Pt) -> int:
        i = self.index.get(p.key)
        if i is None:
            i = self.index[p.key] = len(self.keys)
            self.keys.append(p.key)
            self.pos.append(p.pos)
        return i


def _grid_lines(x, y, cell_m, eps):
    out = set()
    for axis, v in ((0, x), (1, y)):
        k = round(v / cell_m)
        if abs(v - k * cell_m) <= eps:
            out.add((axis, k * cell_m))
    return out


def _area2(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _area3(a, b, c):
    u = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    w = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    cx, cy, cz = u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]
    return 0.5 * math.sqrt(cx * cx + cy * cy + cz * cz)


class _Clipper:
    """Clips triangles of one navmesh against cell lines. Every point gets a canonical key, so the same point
    computed for two triangles (a shared edge) or for two cells (a clipped edge on a cell line) is bit-identical."""

    def __init__(self, nav_id, verts_m, cell_m, eps):
        self.n, self.v, self.cell_m, self.eps = nav_id, verts_m, cell_m, eps
        self.cache: Dict[tuple, _Pt] = {}

    def vertex(self, i, tri):
        a, b, c = (int(x) for x in tri)
        others = [x for x in (a, b, c) if x != i]
        key = ("v", self.n, i)
        p = self.v[i]
        edges = frozenset((self.n, min(i, o), max(i, o)) for o in others)
        lines = frozenset(_grid_lines(p[0], p[1], self.cell_m, self.eps))
        return _Pt(key, (float(p[0]), float(p[1]), float(p[2])), edges, lines)

    def cut(self, p, q, axis, value, tri):
        common = p.edges & q.edges
        if common:
            (n, a, b), = sorted(common)[:1]
            key = ("e", n, a, b, axis, value)
            got = self.cache.get(key)
            if got is not None:
                return got
            pa, pb = self.v[a], self.v[b]
            t = (value - pa[axis]) / (pb[axis] - pa[axis])
            pos = [pa[k] + t * (pb[k] - pa[k]) for k in range(3)]
            pos[axis] = value
            lines = {(axis, value)} | {ln for ln in _grid_lines(pos[0], pos[1], self.cell_m, self.eps) if ln[0] != axis}
            got = self.cache[key] = _Pt(key, tuple(float(x) for x in pos), frozenset({(n, a, b)}), frozenset(lines))
            return got
        on = [ln for ln in (p.lines & q.lines) if ln[0] != axis]
        if not on:
            raise NavmeshError(f"clip: no common support between {p.key} and {q.key}")
        axis2, value2 = on[0]
        xy = [0.0, 0.0]
        xy[axis], xy[axis2] = value, value2
        key = ("c", self.n, xy[0], xy[1])
        got = self.cache.get(key)
        if got is not None:
            return got
        z = _plane_z(self.v[list(tri)], xy[0], xy[1])
        got = self.cache[key] = _Pt(key, (xy[0], xy[1], z), frozenset(), frozenset({(axis, value), (axis2, value2)}))
        return got

    def clip(self, poly, axis, value, keep_ge, tri):
        eps = self.eps
        out = []
        m = len(poly)
        for i in range(m):
            p, q = poly[i], poly[(i + 1) % m]
            sp = (p.pos[axis] - value) if keep_ge else (value - p.pos[axis])
            sq = (q.pos[axis] - value) if keep_ge else (value - q.pos[axis])
            if sp >= -eps:
                out.append(p)
            if (sp > eps and sq < -eps) or (sp < -eps and sq > eps):
                out.append(self.cut(p, q, axis, value, tri))
        return out


def _plane_z(p3, x, y):
    (x1, y1, z1), (x2, y2, z2), (x3, y3, z3) = p3
    d = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
    if abs(d) < 1e-15:
        return float((z1 + z2 + z3) / 3)
    l1 = ((y2 - y3) * (x - x3) + (x3 - x2) * (y - y3)) / d
    l2 = ((y3 - y1) * (x - x3) + (x1 - x3) * (y - y3)) / d
    return float(l1 * z1 + l2 * z2 + (1 - l1 - l2) * z3)


def _fan(poly, min_area):
    """Triangulate a convex polygon (list of _Pt) keeping every vertex: the apex that maximises the smallest
    triangle; triangles below min_area (m2) are left out (reported by the caller)."""
    m = len(poly)
    if m == 3:
        return [(0, 1, 2)] if _area3(*(p.pos for p in poly)) >= min_area else []
    best = None
    for apex in range(m):
        tris = [(apex, (apex + i) % m, (apex + i + 1) % m) for i in range(1, m - 1)]
        small = min(_area3(poly[a].pos, poly[b].pos, poly[c].pos) for a, b, c in tris)
        if best is None or small > best[0]:
            best = (small, tris)
    return [t for t in best[1] if _area3(poly[t[0]].pos, poly[t[1]].pos, poly[t[2]].pos) >= min_area]


def convert(fo4: List[Tuple[int, "Nvnm"]], door_refs=None, units_per_metre=UNITS_PER_METRE, cell_m=SF_CELL_M,
            eps=1e-6, min_area=1e-6, portal_overlap=0.01):
    """Fallout 4 exterior navmeshes [(FormID, Nvnm)] -> (pieces, report). Each Fallout 4 navmesh is cut at the
    Starfield cell lines (cell_m) into one piece per cell it touches; positions are metres (/ units_per_metre) at the
    same absolute place. Links: a clipped edge on a cell line links the two pieces of the same navmesh (exactly the
    same points on both sides); a Fallout 4 portal (type-0 edge link) between two converted navmeshes becomes a link
    between their pieces in every cell where both sub-edges exist and overlap; everything else is dropped and counted.
    door_refs: {Fallout 4 door REFR FormID: "XXXXXX:Fallout4.esm"} of the doors that were converted (others dropped)."""
    door_refs = door_refs or {}
    rep = {"fo4_navmeshes": len(fo4), "fo4_triangles": 0, "fo4_vertices": 0, "pieces": 0, "triangles": 0,
           "clipped_triangles": 0, "sliver_triangles_dropped": 0, "nonmanifold_edges": 0,
           "links": {"cell_line": 0, "fo4_portal": 0},
           "dropped": {"fo4_links_outside": 0, "fo4_links_ledge_type1_2": 0, "fo4_portal_no_overlap": 0,
                       "fo4_portal_subedge_missing": 0, "cover_entries": 0, "cover_flag_triangles": 0,
                       "water_flag_triangles": 0, "doors_not_converted": 0, "waypoints_not_found": 0,
                       "deleted_triangles": 0},
           "kept": {"doors": 0, "waypoints": 0}}
    fids = {fid for fid, _ in fo4}
    pieces: Dict[Tuple[int, Tuple[int, int]], Piece] = {}
    # (navmesh, a, b) -> {cell: (piece key, tri, k)}: piece edges lying on an original edge (for the portals)
    on_edge: Dict[tuple, Dict[tuple, list]] = {}
    for fid, m in fo4:
        v = m.vertices / units_per_metre
        tris = m.triangles
        rep["fo4_triangles"] += len(tris)
        rep["fo4_vertices"] += len(v)
        rep["dropped"]["cover_entries"] += len(m.cover)
        clipper = _Clipper(fid, v, cell_m, eps)
        for ti in range(len(tris)):
            tri = tris[ti]
            fl = int(tri["flags"])
            if fl & F_DELETED:
                rep["dropped"]["deleted_triangles"] += 1
                continue
            if int(tri["cover"]):
                rep["dropped"]["cover_flag_triangles"] += 1
            if fl & F_WATER:
                rep["dropped"]["water_flag_triangles"] += 1
            idx = [int(x) for x in tri["v"]]
            p3 = v[idx]
            lo, hi = p3.min(0), p3.max(0)
            cx0, cx1 = int(math.floor((lo[0] - eps) / cell_m)), int(math.floor((hi[0] + eps) / cell_m))
            cy0, cy1 = int(math.floor((lo[1] - eps) / cell_m)), int(math.floor((hi[1] + eps) / cell_m))
            base = [clipper.vertex(i, idx) for i in idx]
            h = float(tri["height"])
            h = FLT_MAX if not math.isfinite(h) or abs(h) > NO_CEILING else h / units_per_metre
            new_flags = fl & ~(LINK_MASK | F_DOOR | F_WATER)
            cut = (cx0, cy0) != (cx1, cy1)
            if cut:
                rep["clipped_triangles"] += 1
            for cx in range(cx0, cx1 + 1):
                for cy in range(cy0, cy1 + 1):
                    poly = base
                    if cut:
                        X0, Y0 = cx * cell_m, cy * cell_m
                        for axis, value, ge in ((0, X0, True), (0, X0 + cell_m, False), (1, Y0, True),
                                                (1, Y0 + cell_m, False)):
                            poly = clipper.clip(poly, axis, value, ge, idx)
                            if len(poly) < 3:
                                break
                        dedup = []
                        for p in poly:
                            if not dedup or dedup[-1].key != p.key:
                                dedup.append(p)
                        while len(dedup) > 1 and dedup[0].key == dedup[-1].key:
                            dedup.pop()
                        poly = dedup
                    if len(poly) < 3:
                        continue
                    fan = _fan(poly, min_area)
                    if len(fan) < len(poly) - 2:
                        rep["sliver_triangles_dropped"] += len(poly) - 2 - len(fan)
                    if not fan:
                        continue
                    pk = (fid, (cx, cy))
                    pc = pieces.get(pk)
                    if pc is None:
                        pc = pieces[pk] = Piece(fid, (cx, cy))
                    for a, b, c in fan:
                        ids = (pc.vertex(poly[a]), pc.vertex(poly[b]), pc.vertex(poly[c]))
                        pc.tris.append(ids)
                        pc.tri_src.append(ti)
                        pc.flags.append(new_flags)
                        pc.heights.append(h)
    # adjacency inside each piece, open edges for the cross-piece links
    open_edges: Dict[tuple, list] = {}
    for pk, pc in pieces.items():
        pc.neighbours = [[-1, -1, -1] for _ in pc.tris]
        em: Dict[tuple, list] = {}
        for ti, t in enumerate(pc.tris):
            for k in range(3):
                a, b = t[k], t[(k + 1) % 3]
                em.setdefault((min(a, b), max(a, b)), []).append((ti, k))
        for (a, b), lst in em.items():
            if len(lst) == 2:
                (t1, k1), (t2, k2) = lst
                pc.neighbours[t1][k1] = t2
                pc.neighbours[t2][k2] = t1
            elif len(lst) > 2:
                rep["nonmanifold_edges"] += 1
            else:
                ti, k = lst[0]
                ka, kb = pc.keys[a], pc.keys[b]
                gk = (ka, kb) if ka <= kb else (kb, ka)
                open_edges.setdefault(gk, []).append((pk, ti, k))
    for pk, pc in pieces.items():
        rep["triangles"] += len(pc.tris)
        if len(pc.tris) > MAX_INDEX or len(pc.keys) > MAX_INDEX:
            raise NavmeshError(f"piece {pk}: {len(pc.tris)} triangles / {len(pc.keys)} vertices exceed i16 indices")

    def link(a, b, kind):
        (pa, ta, ka), (pb, tb, kb) = a, b
        A, B = pieces[pa], pieces[pb]
        A.neighbours[ta][ka] = ("L", len(A.links))
        A.links.append((0, pb, tb, kb))
        B.neighbours[tb][kb] = ("L", len(B.links))
        B.links.append((0, pa, ta, ka))
        rep["links"][kind] += 1

    # 1. cell lines: the two pieces of one navmesh share the clipped edge's exact keys
    for gk, lst in open_edges.items():
        if len(lst) == 2 and lst[0][0] != lst[1][0]:
            link(lst[0], lst[1], "cell_line")
    # 2. Fallout 4 portals between converted navmeshes
    for gk, lst in open_edges.items():
        for pk, ti, k in lst:
            pc = pieces[pk]
            if pc.neighbours[ti][k] != -1:
                continue
            ea, eb = pc.keys[pc.tris[ti][k]], pc.keys[pc.tris[ti][(k + 1) % 3]]
            common = _edge_support(ea, eb)
            for oe in common:
                on_edge.setdefault(oe, {}).setdefault(pk[1], []).append((pk, ti, k))
    done = set()
    for fid, m in fo4:
        tris = m.triangles
        for ti in range(len(tris)):
            fl = int(tris["flags"][ti])
            for k in range(3):
                if not fl & EDGE_LINK_BITS[k]:
                    continue
                L = m.links[int(tris["e"][ti][k])]
                tgt = int(L["navmesh"])
                if int(L["type"]) != 0:
                    rep["dropped"]["fo4_links_ledge_type1_2"] += 1
                    continue
                if tgt not in fids:
                    rep["dropped"]["fo4_links_outside"] += 1
                    continue
                pair = tuple(sorted(((fid, ti, k), (tgt, int(L["tri"]), int(L["edge"])))))
                if pair in done:
                    continue
                done.add(pair)
                (n1, t1, k1), (n2, t2, k2) = pair
                m1 = m if n1 == fid else _by_fid(fo4, n1)
                m2 = m if n2 == fid else _by_fid(fo4, n2)
                e1 = _orig_edge(n1, m1, t1, k1)
                e2 = _orig_edge(n2, m2, t2, k2)
                c1, c2 = on_edge.get(e1, {}), on_edge.get(e2, {})
                cells = set(c1) | set(c2)
                for cell in sorted(cells):
                    s1 = [x for x in c1.get(cell, []) if pieces[x[0]].neighbours[x[1]][x[2]] == -1]
                    s2 = [x for x in c2.get(cell, []) if pieces[x[0]].neighbours[x[1]][x[2]] == -1]
                    if not s1 or not s2:
                        rep["dropped"]["fo4_portal_subedge_missing"] += 1
                        continue
                    a, b = s1[0], s2[0]
                    if _overlap(pieces, a, b) < portal_overlap:
                        rep["dropped"]["fo4_portal_no_overlap"] += 1
                        continue
                    link(a, b, "fo4_portal")
    # doors and waypoints
    by_src: Dict[Tuple[int, int], List[Tuple[tuple, int]]] = {}
    for pk, pc in pieces.items():
        for ti, s in enumerate(pc.tri_src):
            by_src.setdefault((pk[0], s), []).append((pk, ti))
    for fid, m in fo4:
        for d in m.doors:
            src = door_refs.get(int(d["door"]))
            subs = by_src.get((fid, int(d["tri"])), [])
            if src is None or not subs:
                rep["dropped"]["doors_not_converted"] += 1
                continue
            pk, ti = max(subs, key=lambda s: _tri_area(pieces[s[0]], s[1]))
            pc = pieces[pk]
            pc.doors.append((ti, int(d["extra"]), src))
            pc.flags[ti] |= F_DOOR
            rep["kept"]["doors"] += 1
        for w in m.waypoints:
            pos = tuple(float(x) / units_per_metre for x in w["pos"])
            cell = (int(math.floor(pos[0] / cell_m)), int(math.floor(pos[1] / cell_m)))
            pc = pieces.get((fid, cell))
            hit = _locate(pc, pos) if pc else None
            if hit is None:
                rep["dropped"]["waypoints_not_found"] += 1
                continue
            pc.waypoints.append((pos, hit, int(w["extra"])))
            rep["kept"]["waypoints"] += 1
    rep["pieces"] = len(pieces)
    order = sorted(pieces, key=lambda k: (k[1][1], k[1][0], k[0]))       # by cell (south to north, west to east)
    index = {k: i for i, k in enumerate(order)}
    out = []
    for k in order:
        pc = pieces[k]
        pc.links = [(typ, index[tgt], tri, edge) for typ, tgt, tri, edge in pc.links]
        out.append(pc)
    return out, rep


def _edge_support(ka, kb):
    """The original edges (navmesh, a, b) a piece edge between point keys ka and kb lies on. Both points of a piece
    triangle come from one original triangle: two vertex keys span that triangle's edge between them; a cut point
    ("e") lies on its original edge; a cell corner ("c") lies on none."""
    if ka[0] == "v" and kb[0] == "v":
        return {(ka[1], min(ka[2], kb[2]), max(ka[2], kb[2]))} if ka[2] != kb[2] else set()
    ea = {(ka[1], ka[2], ka[3])} if ka[0] == "e" else None
    eb = {(kb[1], kb[2], kb[3])} if kb[0] == "e" else None
    if ea is None and eb is None:
        return set()
    if ea is None:
        return {e for e in eb if ka[0] == "v" and ka[2] in (e[1], e[2])}
    if eb is None:
        return {e for e in ea if kb[0] == "v" and kb[2] in (e[1], e[2])}
    return ea & eb


def _by_fid(fo4, fid):
    for f, m in fo4:
        if f == fid:
            return m
    raise KeyError(fid)


def _orig_edge(n, m, ti, k):
    a, b = int(m.triangles["v"][ti][k]), int(m.triangles["v"][ti][(k + 1) % 3])
    return (n, min(a, b), max(a, b))


def _seg(pc, ti, k):
    t = pc.tris[ti]
    return np.array(pc.pos[t[k]]), np.array(pc.pos[t[(k + 1) % 3]])


def _overlap(pieces, a, b):
    """Length (m) over which edge a and edge b overlap, projected on a's direction in xy."""
    (p0, p1), (q0, q1) = _seg(pieces[a[0]], a[1], a[2]), _seg(pieces[b[0]], b[1], b[2])
    d = p1[:2] - p0[:2]
    ln = float(np.hypot(*d))
    if ln == 0:
        return 0.0
    u = d / ln
    s = sorted((float(np.dot(q0[:2] - p0[:2], u)), float(np.dot(q1[:2] - p0[:2], u))))
    return max(0.0, min(ln, s[1]) - max(0.0, s[0]))


def _tri_area(pc, ti):
    a, b, c = (pc.pos[i] for i in pc.tris[ti])
    return _area3(a, b, c)


def _locate(pc, pos, ztol=2.0):
    """Index of the piece triangle under pos (xy inside, z within ztol), the closest in z; None if none."""
    best = None
    for ti, t in enumerate(pc.tris):
        a, b, c = (pc.pos[i] for i in t)
        d = _area2(a, b, c)
        if abs(d) < 1e-12:
            continue
        l1 = _area2(pos, b, c) / d
        l2 = _area2(a, pos, c) / d
        l3 = 1 - l1 - l2
        if min(l1, l2, l3) < -1e-9:
            continue
        z = l1 * a[2] + l2 * b[2] + l3 * c[2]
        dz = abs(z - pos[2])
        if dz <= ztol and (best is None or dz < best[0]):
            best = (dz, ti)
    return None if best is None else best[1]


# ------------------------------------------------------------------------------------------------------------ records
def piece_arrays(pc: Piece):
    """(vertices (n, 3) float64, vertex_extra (n,) int32, triangles TRI_DTYPE) of a converted piece. Edge values: the
    neighbour triangle, -1, or the link index with the edge's flag bit. Vertex extra 1 = on an open edge (no neighbour,
    no link): akilacity's 136,976 open-boundary vertices are 1 in 136,176 cases, its 34,057 interior ones always 0."""
    v = np.array(pc.pos, np.float64).reshape(-1, 3)
    t = np.zeros(len(pc.tris), TRI_DTYPE)
    extra = np.zeros(len(v), np.int32)
    for ti, tri in enumerate(pc.tris):
        t["v"][ti] = tri
        fl = pc.flags[ti] & ~LINK_MASK
        for k in range(3):
            nb = pc.neighbours[ti][k]
            if isinstance(nb, tuple):
                t["e"][ti][k] = nb[1]
                fl |= EDGE_LINK_BITS[k]
            else:
                t["e"][ti][k] = nb
                if nb == -1:
                    extra[tri[k]] = 1
                    extra[tri[(k + 1) % 3]] = 1
        t["flags"][ti] = fl
        t["height"][ti] = pc.heights[ti]
    return v, extra, t


def piece_nvnm(pc: Piece, world: int, fid_of: List[int], door_fid=None) -> Nvnm:
    """The Starfield NVNM of a piece; fid_of[i] = the file-local FormID of piece i (link targets), door_fid maps a door
    source key to its file-local REFR FormID."""
    v, extra, t = piece_arrays(pc)
    links = np.zeros(len(pc.links), LINK_DTYPE)
    for i, (typ, tgt, tri, edge) in enumerate(pc.links):
        links[i] = (typ, fid_of[tgt], tri, edge)
    doors = np.zeros(len(pc.doors), DOOR_DTYPE)
    for i, (tri, ex, src) in enumerate(pc.doors):
        doors[i] = (tri, ex, (door_fid or {}).get(src, 0))
    wps = np.zeros(len(pc.waypoints), WAYPOINT_DTYPE)
    for i, (pos, tri, ex) in enumerate(pc.waypoints):
        wps[i] = (pos, tri, ex)
    d, size, gmin, gmax, lists = build_grid(v, t)
    return Nvnm(SF_VERSION, MAGIC, world, pc.cell, None, v, extra, t, links, doors, [], np.zeros(0, COVERMAP_DTYPE),
                wps, d, size, gmin, gmax, lists, SF_TRAILER)


def piece_nvmi(pc: Piece, nav_fid: int, world: int, fid_of: List[int], door_fid=None) -> Nvmi:
    """The NVMI entry of a piece: no outline, no traversals (the vanilla form of 2,021 Starfield.esm entries, mostly
    large navmeshes), merged-to = link targets in link order, location = float32 vertex mean, border bits."""
    v = np.array(pc.pos, np.float32).reshape(-1, 3)
    loc = tuple(float(x) for x in v.mean(0, dtype=np.float32))
    merged = []
    for _typ, tgt, _tri, _edge in pc.links:
        if fid_of[tgt] not in merged:
            merged.append(fid_of[tgt])
    doors = [(ex, (door_fid or {}).get(src, 0)) for _tri, ex, src in pc.doors]
    return Nvmi(nav_fid, 0, loc, 0.0, merged, [], doors, [], None, world, pc.cell, None,
                border_bits(v.min(0), v.max(0), pc.cell))


def export(pieces: List[Piece]) -> dict:
    """navmesh.json for dotnet/TerrainExp2: one entry per piece, links name pieces by index (the writer allocates the
    FormIDs), doors name the converted door by its source key. Vertices are float32 values (as written)."""
    out = []
    for pc in pieces:
        v, extra, t = piece_arrays(pc)
        vf = v.astype(np.float32)
        d, size, gmin, gmax, lists = build_grid(vf.astype(np.float64), t)
        out.append({
            "src": f"{pc.src & 0xFFFFFF:06X}:Fallout4.esm", "cell": list(pc.cell),
            "vertices": [[float(a), float(b), float(c), int(x)] for (a, b, c), x in zip(vf, extra)],
            "triangles": [[int(a) for a in r["v"]] + [int(a) for a in r["e"]] +
                          [float(r["height"]), int(r["extra"]), int(r["flags"]), int(r["cover"])] for r in t],
            "links": [list(x) for x in pc.links],
            "doors": [[tri, ex, src] for tri, ex, src in pc.doors],
            "waypoints": [[float(p[0]), float(p[1]), float(p[2]), tri, ex] for p, tri, ex in pc.waypoints],
            "grid": {"divisor": d, "size": list(size), "min": list(gmin), "max": list(gmax), "lists": lists},
            "nvmi": {"location": [float(x) for x in vf.mean(0, dtype=np.float32)],
                     "border": border_bits(vf.min(0), vf.max(0), pc.cell)},
        })
    return {"version": 1, "navmeshes": out}


# ------------------------------------------------------------------------------------------------------------ validation
def validate(navs: Dict[int, Nvnm], nvmis: Optional[Dict[int, Nvmi]] = None, world: Optional[int] = None,
             cell_m=SF_CELL_M, cell_eps=1e-3, portal_tol=0.5):
    """Structural checks of a set of Starfield navmeshes {FormID: Nvnm}. Returns counts and "errors" (list).
    Every triangle vertex index and edge value in range; internal edges symmetric and sharing the two vertices;
    every link used by exactly one triangle edge, its target navmesh present, the target edge flagged and linking back
    (symmetry), the two linked segments within portal_tol of each other (Fallout 4's own portals leave up to
    0.34 m around Red Rocket); vertices inside the navmesh's own
    exterior cell; the grid listing every triangle; with nvmis: one entry per navmesh, merged-to = the link targets in
    link order, location = the vertex mean, border bits, parent, linked doors = door triangles."""
    errs = []
    st = {"navmeshes": len(navs), "triangles": 0, "vertices": 0, "links": 0, "links_symmetric": 0,
          "internal_edges": 0, "open_edges": 0, "link_gap_max_m": 0.0, "link_gaps_over_5cm": 0, "doors": 0,
          "waypoints": 0}

    def err(msg):
        if len(errs) < 200:
            errs.append(msg)
        st["error_count"] = st.get("error_count", 0) + 1

    for fid, m in navs.items():
        t, nv, nt, nl = m.triangles, len(m.vertices), len(m.triangles), len(m.links)
        st["triangles"] += nt
        st["vertices"] += nv
        st["links"] += nl
        st["doors"] += len(m.doors)
        st["waypoints"] += len(m.waypoints)
        if world is not None and m.world != world:
            err(f"{fid:08X}: parent worldspace {m.world:08X}, want {world:08X}")
        if m.grid is not None and nv:
            x0, y0 = m.grid[0] * cell_m, m.grid[1] * cell_m
            lo, hi = m.vertices.min(0), m.vertices.max(0)
            if lo[0] < x0 - cell_eps or lo[1] < y0 - cell_eps or hi[0] > x0 + cell_m + cell_eps or \
                    hi[1] > y0 + cell_m + cell_eps:
                err(f"{fid:08X}: vertices leave cell {m.grid}: x {lo[0]:.3f}..{hi[0]:.3f} y {lo[1]:.3f}..{hi[1]:.3f}")
        used = [0] * nl
        for ti in range(nt):
            vv = [int(x) for x in t["v"][ti]]
            if min(vv) < 0 or max(vv) >= nv or len(set(vv)) < 3:
                err(f"{fid:08X} tri {ti}: bad vertices {vv}")
                continue
            fl = int(t["flags"][ti])
            for k in range(3):
                e = int(t["e"][ti][k])
                if fl & EDGE_LINK_BITS[k]:
                    if not 0 <= e < nl:
                        err(f"{fid:08X} tri {ti} edge {k}: link {e} of {nl}")
                        continue
                    used[e] += 1
                    L = m.links[e]
                    other = navs.get(int(L["navmesh"]))
                    if other is None:
                        err(f"{fid:08X} tri {ti} edge {k}: link to missing navmesh {int(L['navmesh']):08X}")
                        continue
                    t2, k2 = int(L["tri"]), int(L["edge"])
                    if not (0 <= t2 < len(other.triangles) and 0 <= k2 < 3):
                        err(f"{fid:08X} tri {ti} edge {k}: link to bad triangle {t2} edge {k2}")
                        continue
                    f2 = int(other.triangles["flags"][t2])
                    back = None
                    if f2 & EDGE_LINK_BITS[k2]:
                        e2 = int(other.triangles["e"][t2][k2])
                        if 0 <= e2 < len(other.links):
                            B = other.links[e2]
                            back = (int(B["navmesh"]), int(B["tri"]), int(B["edge"]))
                    if back != (fid, ti, k):
                        err(f"{fid:08X} tri {ti} edge {k}: link to {int(L['navmesh']):08X}/{t2}/{k2} does not link "
                            f"back ({back})")
                        continue
                    st["links_symmetric"] += 1
                    a = m.vertices[vv[k]], m.vertices[vv[(k + 1) % 3]]
                    v2 = other.triangles["v"][t2]
                    b = other.vertices[int(v2[k2])], other.vertices[int(v2[(k2 + 1) % 3])]
                    gap = segment_gap(a, b)
                    st["link_gap_max_m"] = max(st["link_gap_max_m"], gap)
                    st["link_gaps_over_5cm"] += gap > 0.05
                    if gap > portal_tol:
                        err(f"{fid:08X} tri {ti} edge {k}: linked segments {gap:.3f} m apart")
                elif e == -1:
                    st["open_edges"] += 1
                elif 0 <= e < nt:
                    st["internal_edges"] += 1
                    w = [int(x) for x in t["v"][e]]
                    if not {vv[k], vv[(k + 1) % 3]} <= set(w):
                        err(f"{fid:08X} tri {ti} edge {k}: neighbour {e} does not share the edge's vertices")
                    back = [kk for kk in range(3)
                            if int(t["e"][e][kk]) == ti and not int(t["flags"][e]) & EDGE_LINK_BITS[kk]]
                    if not back:
                        err(f"{fid:08X} tri {ti} edge {k}: neighbour {e} does not point back")
                else:
                    err(f"{fid:08X} tri {ti} edge {k}: neighbour {e} of {nt}")
        for i, u in enumerate(used):
            if u != 1:
                err(f"{fid:08X}: link {i} used by {u} triangle edges (dangling or shared)")
        listed = set(i for lst in m.grid_lists for i in lst)
        if listed != set(range(nt)):
            err(f"{fid:08X}: grid lists {len(listed)} of {nt} triangles")
        if len(m.grid_lists) != m.grid_divisor ** 2 or m.grid_divisor != grid_divisor(nt):
            err(f"{fid:08X}: grid divisor {m.grid_divisor} for {nt} triangles")
        for d in m.doors:
            if not 0 <= int(d["tri"]) < nt or not int(t["flags"][int(d["tri"])]) & F_DOOR:
                err(f"{fid:08X}: door triangle {int(d['tri'])} missing or not flagged")
        for w in m.waypoints:
            if not 0 <= int(w["tri"]) < nt:
                err(f"{fid:08X}: waypoint triangle {int(w['tri'])}")
    if nvmis is not None:
        st["nvmi"] = len(nvmis)
        for fid, m in navs.items():
            e = nvmis.get(fid)
            if e is None:
                err(f"{fid:08X}: no NVMI entry")
                continue
            want = []
            for L in m.links:
                if int(L["navmesh"]) not in want:
                    want.append(int(L["navmesh"]))
            if e.merged != want:
                err(f"{fid:08X}: NVMI merged-to {[hex(x) for x in e.merged]}, links reach {[hex(x) for x in want]}")
            if len(m.vertices):
                mean = m.vertices.astype(np.float32).mean(0, dtype=np.float32)
                if np.abs(np.array(e.location) - mean).max() > 1e-3:
                    err(f"{fid:08X}: NVMI location {e.location} vs vertex mean {mean.tolist()}")
                if m.grid is not None and e.border != border_bits(m.vertices.min(0), m.vertices.max(0), m.grid, cell_m):
                    err(f"{fid:08X}: NVMI border bits {e.border}")
            if (e.world, e.grid) != (m.world, m.grid):
                err(f"{fid:08X}: NVMI parent {e.world:08X} {e.grid} vs navmesh {m.world:08X} {m.grid}")
            if sorted(x[1] for x in e.doors) != sorted(int(d["door"]) for d in m.doors):
                err(f"{fid:08X}: NVMI linked doors differ from the door triangles")
        for fid in nvmis:
            if fid not in navs:
                err(f"NVMI entry {fid:08X} has no navmesh")
    st["errors"] = errs
    return st


def segment_gap(a, b):
    """How far the shorter of two segments lies from the longer one (largest endpoint distance, 3D): 0 for identical
    edges, small for a Fallout 4 portal whose two edges overlap only in part."""
    a0, a1 = np.asarray(a[0], np.float64), np.asarray(a[1], np.float64)
    b0, b1 = np.asarray(b[0], np.float64), np.asarray(b[1], np.float64)

    def dist(p, s0, s1):
        d = s1 - s0
        ln = float(np.dot(d, d))
        t = 0.0 if ln == 0 else min(1.0, max(0.0, float(np.dot(p - s0, d)) / ln))
        return float(np.linalg.norm(p - (s0 + t * d)))
    if np.linalg.norm(a1 - a0) >= np.linalg.norm(b1 - b0):
        return max(dist(b0, a0, a1), dist(b1, a0, a1))
    return max(dist(a0, b0, b1), dist(a1, b0, b1))


def triangle_path(navs: Dict[int, Nvnm], start: Tuple[int, int], goal: Tuple[int, int]):
    """Breadth-first walk over triangle edges and edge links from (navmesh, tri) to (navmesh, tri): the list of
    (navmesh, tri) on the way, or None. An offline connectivity check, not the game's pathfinder."""
    from collections import deque
    prev = {start: None}
    q = deque([start])
    while q:
        cur = q.popleft()
        if cur == goal:
            out = []
            while cur is not None:
                out.append(cur)
                cur = prev[cur]
            return out[::-1]
        fid, ti = cur
        m = navs[fid]
        fl = int(m.triangles["flags"][ti])
        for k in range(3):
            e = int(m.triangles["e"][ti][k])
            if fl & EDGE_LINK_BITS[k]:
                L = m.links[e]
                nxt = (int(L["navmesh"]), int(L["tri"]))
            elif e >= 0:
                nxt = (fid, e)
            else:
                continue
            if nxt not in prev and nxt[0] in navs:
                prev[nxt] = cur
                q.append(nxt)
    return None


def locate(navs: Dict[int, Nvnm], x, y, z=None, ztol=2.0):
    """[(key, navmesh, tri, z)] of the triangles under (x, y): nearest in z first (z None: highest first)."""
    out = []
    for fid, m in navs.items():
        v = m.vertices
        if not len(v) or not len(m.triangles):
            continue
        lo, hi = v.min(0), v.max(0)
        if not (lo[0] - 1e-6 <= x <= hi[0] + 1e-6 and lo[1] - 1e-6 <= y <= hi[1] + 1e-6):
            continue
        P = v[m.triangles["v"]]
        a, b, c = P[:, 0], P[:, 1], P[:, 2]
        d = (b[:, 1] - c[:, 1]) * (a[:, 0] - c[:, 0]) + (c[:, 0] - b[:, 0]) * (a[:, 1] - c[:, 1])
        ok = np.abs(d) > 1e-12
        d = np.where(ok, d, 1.0)
        l1 = ((b[:, 1] - c[:, 1]) * (x - c[:, 0]) + (c[:, 0] - b[:, 0]) * (y - c[:, 1])) / d
        l2 = ((c[:, 1] - a[:, 1]) * (x - c[:, 0]) + (a[:, 0] - c[:, 0]) * (y - c[:, 1])) / d
        l3 = 1 - l1 - l2
        hit = np.nonzero(ok & (l1 >= -1e-9) & (l2 >= -1e-9) & (l3 >= -1e-9))[0]
        for i in hit:
            zz = float(l1[i] * a[i, 2] + l2[i] * b[i, 2] + l3[i] * c[i, 2])
            if z is None or abs(zz - z) <= ztol:
                out.append((abs(zz - z) if z is not None else -zz, fid, int(i), zz))
    return sorted(out)


# ------------------------------------------------------------------------------------------------------------ plugins
def world_navmeshes(plugin, world_edid, cells=None):
    """[(cell (x, y), FormID, record flags, NVNM bytes)] of the NAVM records in one worldspace's exterior cells
    (cells: a set of (x, y) or None for all). plugin: an open fo4sf.fo4land.Plugin (Fallout 4 or Starfield)."""
    from .fo4land import iter_items, iter_subrecords, record_data
    _wfid, start, end, _ = plugin.find_world(world_edid)
    out = []
    cur = [None]

    def walk(s, e):
        for it in iter_items(plugin.buf, s, e):
            if it[0] == "GRUP":
                walk(it[1] + 24, it[2])
                continue
            typ, off, flags, fid = it
            if typ == b"CELL":
                cur[0] = None
                for sig, d in iter_subrecords(record_data(plugin.buf, off)):
                    if sig == b"XCLC" and len(d) >= 8:
                        cur[0] = struct.unpack_from("<ii", d)
            elif typ == b"NAVM" and (cells is None or cur[0] in cells):
                for sig, d in iter_subrecords(record_data(plugin.buf, off)):
                    if sig == b"NVNM":
                        out.append((cur[0], fid, flags, bytes(d)))
    walk(start, end)
    return out


def navi_entries(plugin):
    """[bytes] of every NVMI in the plugin's NAVI records."""
    from .fo4land import iter_items, iter_subrecords, record_data
    out = []
    for it in iter_items(plugin.buf, plugin.body, len(plugin.buf)):
        if it[0] == "GRUP" and it[3] == b"NAVI":
            for sub in iter_items(plugin.buf, it[1] + 24, it[2]):
                if sub[0] == "GRUP":
                    continue
                for sig, d in iter_subrecords(record_data(plugin.buf, sub[1])):
                    if sig == b"NVMI":
                        out.append(bytes(d))
    return out
