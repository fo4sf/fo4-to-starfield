# Object LOD trial (playtest row 24)

Author: Grok, 2026-10-17. Status: **plan only, no build**. Split out of #303 so the garage-button wire
can merge without carrying this trial. Claude owns CK/staging/game; Grok does not generate LOD, install,
or send input.

The owner, on foot at Red Rocket: “extremely long distances you can just see nothingness”. Terrain LOD is
already in the overlay BTD (LOD0–4). **Object LOD is a separate file pair.** Converted STAT/ACTI have no
Starfield distant stand-ins, so past the loaded cell window the world is empty terrain.

Labels: **verified** = counted or read from files; **supported** = hypothesis with evidence;
**unresolved** = open.

## Vanilla files (**verified**, Starfield 1.16.244)

`Starfield - LODMeshes.ba2`: 20,400 files = 19,535 `meshes/lod/generated/…_lod_{0-3}.nif` (cities included),
**864** `lodsettings/<world>.lod`, 1 `distantlod/lodruntimedb.bgsdb`. **861 of 864** `.lod` files are **20
bytes** (2 are 22, 1 is 16). Examples: `lc172world` / `landingoverlay01`
`FE FF FF FF FE FF FF FF 08 00…`; `newatlantis` `DD FF FF FF C5 FF FF FF 88 00…` — cell min/size,
**supported**. FO4 object LOD is `.bto` (FORMAT-GAP); not this format.

Pinned core64k `Data\` has **zero** `.lod` / `meshes/lod/generated`. Overlay objects are full STAT/ACTI only.
Past the loaded window Starfield draws BTD terrain and nothing else. Matches the walk (row 24) and the
surface-map gap in [surface-map.md](surface-map.md).

World object LOD is **not** the converted FO4 `*_lod.nif` files (315 under `meshes/fo4core/lod/` on core64k).
Those are ordinary meshes. Shipping them as `meshes/lod/generated/` is **not go**.

## INI (not the product path)

`Starfield.ini` `uExterior Cell Buffer=36`; High/Ultra do not override it. Raising it keeps more
**full-detail** converted meshes in memory (648k refs) and still has no distant stand-ins once cells drop.
The owner’s `setini "fLODFadeOutMultObjects:LOD" 15` is a fade-multiplier experiment, not object LOD. Do
not put an INI change in the converter or the overlay plugin.

## Tooling

CK is the **hypothesized** generator of `lodsettings` + `meshes/lod/generated` (this trial’s first spike).
This repo has no object-LOD writer. Per-mesh `sfmesh` LOD index arrays are not world object LOD.

## Trial (Claude window; Grok hands docs/patches only)

1. **Tiny overlay spike (go/no-go).** Duplicate a vanilla unique overlay (LC172-class), place a handful of
   large vanilla STAT, run CK object-LOD generate (`-MockWorldSpaceLOD` or the CK Object LOD UI — which
   command is **unresolved** until this spike). Pass = a 20-byte `lodsettings/<edid>.lod` plus
   `meshes/lod/generated/…_lod_0..3.nif`, and those structures visible past the cell buffer and on the 3D
   surface map. Fail = stop; do not stub files by hand.
2. **Only then** the same generate for `FO4Core_Commonwealth` on a scratch overlay that already has the
   #296 marker (LCSR tail `0xFFFFFFFF`). Start with large STAT (Red Rocket, sanctuary houses), not every
   clutter ref.
3. **In-world check at Red Rocket.** Walk or look toward Diamond City from the station ground. Pass =
   building silhouettes past the loaded window (row 24). Surface-map screenshot is extra evidence, not a
   substitute.
4. **Writer later, if the spike passes.** A `lodsettings` stub named for `FO4Core_Commonwealth` plus
   generated `_lod_0..3` for large STAT. File scope agreed on #32 before any exterior-writer edit. Claude
   owns that edit and the stage.

## Not this trial

- Porting FO4 `.bto`.
- Raising `uExterior Cell Buffer` as the product fix.
- Unparenting the overlay from Mars.
- Garage-button wiring (#303) or NIF rig.
- Native acceptance from offline file counts.

## Acceptance

Claude: from a scratch overlay that completed step 1 (or 2), stand at Red Rocket on the ground. Pass =
structures visible beyond the loaded cells. Offline `check` cannot see the LOD camera.
