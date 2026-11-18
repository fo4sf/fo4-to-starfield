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
DEFAULT_FACE_SIZE = 256
DEFAULT_FACES = 2


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


def build_uniform_biome_map(biome_formid, resource_byte=0, width=DEFAULT_FACE_SIZE, height=DEFAULT_FACE_SIZE,
                            faces=DEFAULT_FACES):
    """Build a synthetic `.biom` binary file (magic 0x0105, 1 biome, `faces` polar grids of `width x height` pixels)
    naming `biome_formid` at every pixel with zero Bethesda archive bytes copied."""
    if not (0 < biome_formid <= 0xFFFFFFFF):
        raise BiomError(f"biome form id {biome_formid:#x} out of u32 range")
    if not (0 <= resource_byte <= 0xFF):
        raise BiomError(f"resource_byte {resource_byte} out of u8 range")
    if width <= 0 or height <= 0 or faces <= 0:
        raise BiomError(f"invalid biome map dimensions {width}x{height}x{faces}")
    npix = width * height
    parts = [struct.pack("<HIII", MAGIC, 1, biome_formid, faces)]
    face_header = struct.pack("<3I", width, height, npix)
    face_pixels = struct.pack("<I", biome_formid) * npix
    face_res = struct.pack("<I", npix) + (bytes([resource_byte]) * npix)
    for _ in range(faces):
        parts.append(face_header)
        parts.append(face_pixels)
        parts.append(face_res)
    return b"".join(parts)


def parse_biome_map(data):
    """Validate and summarize a `.biom` binary buffer (header biomes, faces, dimensions, distinct pixel biomes, and
    distinct resource bytes)."""
    ids = biome_ids(data)
    p = 6 + 4 * len(ids)
    if p + 4 > len(data):
        raise BiomError("biome map truncated before face count")
    nfaces, = struct.unpack_from("<I", data, p)
    p += 4
    if nfaces <= 0 or nfaces > 16:
        raise BiomError(f"biome map has invalid face count {nfaces}")
    face_summaries = []
    header_set = set(ids)
    for idx in range(nfaces):
        if p + 12 > len(data):
            raise BiomError(f"biome map face {idx} truncated before header")
        w, h, npix = struct.unpack_from("<3I", data, p)
        p += 12
        if w <= 0 or h <= 0 or npix != w * h:
            raise BiomError(f"biome map face {idx} invalid dimensions {w}x{h} ({npix} pixels)")
        pix_end = p + 4 * npix
        if pix_end + 4 > len(data):
            raise BiomError(f"biome map face {idx} truncated inside pixel table")
        pixels = struct.unpack_from(f"<{npix}I", data, p)
        pix_set = set(pixels)
        if not pix_set.issubset(header_set):
            raise BiomError(f"biome map face {idx} pixel biomes {sorted(hex(x) for x in pix_set - header_set)} not in header")
        p = pix_end
        nres, = struct.unpack_from("<I", data, p)
        p += 4
        if nres != npix or p + nres > len(data):
            raise BiomError(f"biome map face {idx} invalid resource table ({nres} vs {npix})")
        res_vals = sorted(set(data[p:p + nres]))
        p += nres
        face_summaries.append({"width": w, "height": h, "pixels": npix,
                               "pixel_biomes": [f"{x:08X}" for x in sorted(pix_set)],
                               "resource_values": res_vals})
    if p != len(data):
        raise BiomError(f"biome map has {len(data) - p} trailing bytes")
    return {"biomes": [f"{i:08X}" for i in ids], "faces": face_summaries, "bytes": len(data)}


def stage_uniform_biome_map(biome_formid, name, plugin, out, resource_byte=0):
    """Write a synthetic `.biom` map for `biome_formid` to both candidate paths under `out`:
      Data/PlanetData/BiomeMaps/<name_lower>.biom
      Data/PlanetData/BiomeMaps/<plugin_lower>/<name_lower>.biom
    Returns a report dict with `label='TEST-STATION'` for the plugin-subfolder candidate."""
    data = build_uniform_biome_map(biome_formid, resource_byte=resource_byte)
    parsed = parse_biome_map(data)
    written = []
    for rel in stage_paths(name, plugin):
        dst = os.path.join(out, *rel.split("/"))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "wb") as f:
            f.write(data)
        written.append(rel)
    return {
        "source": "synthetic:uniform_biome_map",
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "biomes": parsed["biomes"],
        "faces": len(parsed["faces"]),
        "resource_values": parsed["faces"][0]["resource_values"],
        "files": written,
        "path_status": {
            written[0]: "VERIFIED_ENGINE_ANAM_PATH",
            written[1]: "TEST-STATION",
        },
    }
