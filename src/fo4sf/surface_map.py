"""Starfield 3D surface-map file contract (docs/terrain/surface-map.md). Synthetic only.

The May 2024 surface map draws the current loading zone in 3D. It is not a separate mesh we author.
World object LOD is lodsettings/<edid>.lod plus meshes/lod/generated/…_lod_0..3.nif. Converted FO4
*_lod.nif files under meshes/fo4core/lod/ are ordinary meshes, not that contract.
"""

import struct

MARS_SURFACE = 0x0001B736  # LCTN SSol_PMars_Surface; parent of FO4Core_CommonwealthLocation
MARS_PNDT = 0x0003F59A  # PNDT MarsPlanetData
OVERLAY_SNAM_SOL = 0  # WRLD overlay component, LC172 / core64k
OVERLAY_PNAM_MARS = 4
WORLD_EDID = "FO4Core_Commonwealth"
WORLD_OBJECT_LOD_PREFIX = "meshes/lod/generated/"
CONVERTED_FO4_LOD_PREFIX = "meshes/fo4core/lod/"
LODSETTINGS_DIR = "lodsettings"


def _slash(relpath):
    return relpath.replace("\\", "/").lower().lstrip("/")


def lodsettings_rel(world_edid):
    """Vanilla path: lodsettings/<world editor id, lower case>.lod (20-byte file)."""
    if not world_edid or world_edid != world_edid.strip() or "/" in world_edid or "\\" in world_edid:
        raise ValueError("world editor id required")
    return f"{LODSETTINGS_DIR}/{world_edid.lower()}.lod"


def is_starfield_world_lod_mesh(relpath):
    """True only for CK/world object LOD meshes, not converted FO4 *_lod.nif files."""
    p = _slash(relpath)
    return p.startswith(WORLD_OBJECT_LOD_PREFIX) and any(
        p.endswith(f"_lod_{i}.nif") for i in range(4)
    )


def is_converted_fo4_lod_mesh(relpath):
    return _slash(relpath).startswith(CONVERTED_FO4_LOD_PREFIX)


def make_lodsettings_stub(min_x: int = -2, min_y: int = -2, cell_size: int = 8) -> bytes:
    """Generate a 20-byte lodsettings stub matching vanilla format examples.

    Vanilla examples (object-lod.md): cell min_x/min_y as signed int32, followed by size-related
    fields. This produces a minimal valid-length file for the go/no-go trial.
    """
    if not (-32768 <= min_x <= 32767 and -32768 <= min_y <= 32767):
        raise ValueError("cell mins out of int16-compatible range")
    if not (0 <= cell_size <= 65535):
        raise ValueError("cell_size out of range")
    data = struct.pack("<ii", min_x, min_y)
    data += struct.pack("<H", cell_size)
    data += b"\x00" * (20 - len(data))
    assert len(data) == 20
    return data
