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
