# Object LOD (playtest row 24)

Author: Grok, 2026-10-17. Status: **research + scoped plan, no build**.

The owner, on foot at Red Rocket, sees “extremely long distances you can just see nothingness”. Terrain LOD is in the
BTD (LOD0–4, already authored). **Object LOD is separate.**

## Vanilla (**verified**, Starfield 1.16.244)

`Starfield - LODMeshes.ba2`: 20,400 files = 19,535 `meshes/lod/generated/…_lod_{0-3}.nif` (cities included), **864**
`lodsettings/<world>.lod`, 1 `distantlod/lodruntimedb.bgsdb`. **861 of 864** `.lod` files are **20 bytes** (2 are 22, 1
is 16); e.g. `lc172world` / `landingoverlay01` `FE FF FF FF FE FF FF FF 08 00…`; `newatlantis`
`DD FF FF FF C5 FF FF FF 88 00…` — cell min/size, **supported**. FO4 object LOD is `.bto` (FORMAT-GAP); not this format.

Pinned core64k `Data\` has **zero** `.lod` / `meshes/lod`. Overlay objects are full STAT/ACTI only, so past the loaded
window Starfield draws BTD terrain and nothing else. Matches the walk.

## INI

`Starfield.ini` `uExterior Cell Buffer=36`; High/Ultra do not override it. Raising it keeps more **full-detail**
converted meshes in memory (648k refs) and still has no distant stand-ins once cells drop. Not the product fix. The
owner’s `setini "fLODFadeOutMultObjects:LOD" 15` is a fade-multiplier experiment, not object LOD.

## Tooling

CK is the **hypothesized** generator of object LOD (plan step 1 is the spike). This repo has no writer. Per-mesh
`sfmesh` LOD index arrays are not world object LOD.

## Plan (no build now)

1. Tiny overlay + CK object-LOD generate as a go/no-go (Claude window).
2. Only then a `lodsettings` stub named for `FO4Core_Commonwealth` plus generated `_lod_0..3` for large STAT.
3. Do not port FO4 `.bto` until that spike. No INI change in the product path.

## Format read from the vanilla archive (Claude-cloud, 2026-10-22, read-only)

Read with `src/fo4sf/ba2.py` from the owner's `Starfield - LODMeshesPatch.ba2` (20,405 entries; `LODMeshes.ba2`
has 20,400). Owner's ask: buildings on the 3D surface map, which needs this object LOD.

- **`.lod` is three i32 values (verified bytes; their meaning is a supported hypothesis):** the minimum cell x, the
  minimum cell y, and a size in cells, then 8 zero bytes. `lc172world` and `landingoverlay01` are `-2, -2, 8`;
  `cydoniacity` is `-6, -6, 16`; `newatlantis` is `-35, -59, 136`. Ours would name the Commonwealth overlay's
  own cell range.
- **Two kinds of LOD mesh.** 12,627 are per object (`meshes/lod/generated/<mesh path>_lod_<0-3>.nif`, keyed by the
  full mesh's name, so they serve any world that places that mesh). 6,913 are per world, under
  `meshes/lod/generated/composite/<world>/` for 242 worlds (for example `packin` 844, `newatlantis` 662,
  `cydoniacity` 530), named `<name>_lod_<x>_<y>_lod_<level>_cell<k>.nif`.
- **The NIFs are small wrappers.** A composite NIF is 769 bytes: `NiNode`, `BSGeometry` and
  `BSLightingShaderProperty` naming a generated material
  (`Materials\LOD\Generated\Composite\CydoniaCity\...mat`) and a geometry hash. The vertices live in a separate
  `.mesh` file, as for the full meshes our converter already writes. A per-object NIF keeps the source mesh's own
  materials.
- **`distantlod/lodruntimedb.bgsdb`** is 559,956 bytes and opens with the counts 8 and 4,387 (0x1123), then records
  that carry hashes and the text `nif`. Whether it is one global database that our LOD must be merged into, or
  whether a world can do without an entry, is **unresolved**.

So a generator, whether the Creation Kit or ours, writes three things: a `.lod` for the overlay, per-object and
composite LOD NIFs with their `.mesh` and `.mat`, and possibly entries in `lodruntimedb.bgsdb`. The Creation Kit
spike above stays the first step: it shows what the CK writes for a world of ours, and that output is the
reference for our own generator.
