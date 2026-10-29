"""The planet's biome map, copied out of the user's own "Starfield - PlanetData.ba2" at stage time.

Vanilla biome maps live in "Starfield - PlanetData.ba2" as planetdata/biomemaps/<body name, lower case>.biom, one per
planet (1,438 files on 1.16.244; "agamon a.biom", "jemison.biom": verified). A file starts with u16 0x0105, a u32
count and that many biome form ids; jemison.biom lists five (verified), the biomes of Jemison's PPBD records
(supported: the planet record was not read in the cloud). A clone keeps the template's biomes, so a renamed copy of
the template's map fits it. Which path the game reads for a plugin's planet is not known (supported hypothesis: the
body name; a plugin subfolder is the other candidate), so the copy goes to both:
  Data/PlanetData/BiomeMaps/<name>.biom  and  Data/PlanetData/BiomeMaps/<plugin>/<name>.biom
The copy never enters the repo and never ships: it is made on the user's PC from the user's own archive.
"""
import hashlib
import os
import struct

from .. import ba2

ARCHIVE = "Starfield - PlanetData.ba2"
MAGIC = 0x0105


class BiomError(ValueError):
    pass


def archive_path(name):
    return f"planetdata/biomemaps/{name.lower()}.biom"


def biome_ids(data):
    """The biome form ids a .biom file lists (its header)."""
    if len(data) < 6:
        raise BiomError("biome map shorter than its header")
    magic, n = struct.unpack_from("<HI", data)
    if magic != MAGIC:
        raise BiomError(f"biome map magic {magic:#06x}, expected {MAGIC:#06x}")
    if n > 64 or len(data) < 6 + 4 * n:
        raise BiomError(f"biome map lists {n} biomes in {len(data)} bytes")
    return list(struct.unpack_from(f"<{n}I", data, 6))


def stage_paths(name, plugin):
    """The staged files (relative to the stage folder) the copy goes to."""
    base = name.lower() + ".biom"
    return [f"Data/PlanetData/BiomeMaps/{base}", f"Data/PlanetData/BiomeMaps/{plugin.lower()}/{base}"]


def copy_biome_map(data_dir, template, name, plugin, out, expect_biomes=None, strict=True):
    """Copy <template>'s biome map from <data_dir>/Starfield - PlanetData.ba2 into <out> under our planet's name (both
    paths). expect_biomes: the biome form ids of the planet record (PPBD), which the map should list (same set): a
    difference raises BiomError when strict, else the report says so ("biomes_match": False; the template planet
    itself then lives with that difference in the game, and our clone has the same biomes). Returns a report dict."""
    src = os.path.join(data_dir, ARCHIVE)
    if not os.path.isfile(src):
        raise BiomError(f"{src} not found")
    arch = ba2.Ba2(src)
    want = archive_path(template)
    if arch.find(want) is None:
        raise BiomError(f"{ARCHIVE} has no {want}")
    data = arch.read(want)
    ids = biome_ids(data)
    match = None if expect_biomes is None else sorted(ids) == sorted(expect_biomes)
    if match is False and strict:
        raise BiomError(f"{want} lists biomes {[f'{i:08X}' for i in ids]}, the planet record "
                        f"{[f'{i:08X}' for i in expect_biomes]}")
    written = []
    for rel in stage_paths(name, plugin):
        dst = os.path.join(out, *rel.split("/"))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "wb") as f:
            f.write(data)
        written.append(rel)
    return {"source": f"{ARCHIVE}:{want}", "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "biomes": [f"{i:08X}" for i in ids], "files": written, "biomes_match": match,
            "planet_biomes": None if expect_biomes is None else [f"{i:08X}" for i in expect_biomes]}
