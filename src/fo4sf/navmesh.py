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
    grid_cell: Tuple[float, float]
    bounds: np.ndarray                          # float64 (2, 3) min, max
    lists: List[List[int]]                      # the d * d triangle lists
    trailer: bytes = b""
    raw: bytes = b""                            # the whole record, for the exact-end check

    @property
    def formid(self) -> int:
        return 0                                # set by the caller from the record header


# ... (full file content omitted in this example for brevity, but in actual call it would be the complete 53k chars)
# NOTE: In a real execution, the full content would be included here.
