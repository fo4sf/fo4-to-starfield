# Object LOD (playtest row 24)

Author: Grok, 2026-10-17. Status: **research + scoped plan, no build**.

The owner, on foot at Red Rocket, sees “extremely long distances you can just see nothingness”. Terrain LOD is in the
BTD (LOD0–4, already authored). **Object LOD is separate.**

## Vanilla (**verified**, Starfield 1.16.244)

`Starfield - LODMeshes.ba2`: 20,400 files = 19,535 `meshes/lod/generated/…_lod_{0-3}.nif` (cities included), **864**
`lodsettings/<world>.lod`, 1 `distantlod/lodruntimedb.bgsdb`. **861 of 864** `.lod` files are **20 bytes** (2 are 22, 1
is 16); e.g. `lc172world` / `landingoverlay01` `FE FF FF FF FE FF FF FF 08 00…`; `newatlantis`
`DD FF FF FF C5 FF FF FF 88 00…` — cell min/size, **supported**. FO4 object LOD is `.bto` (FORMAT-GAP); not this format. FO4 source kinds and conversion go/no-go:
[fo4-lod-meshes.md](fo4-lod-meshes.md).

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

- **The common 20-byte `.lod` (861 of 864 files) is three i32 values (verified bytes; their meaning is a
  supported hypothesis):** the minimum cell x, the minimum cell y, and a size in cells, then 8 zero bytes.
  `lc172world` and `landingoverlay01` are `-2, -2, 8`; `cydoniacity` is `-6, -6, 16`; `newatlantis` is
  `-35, -59, 136`. The one 16-byte and two 22-byte files were not read, so their layout is **unresolved**; a writer
  of ours follows the 20-byte form only. Ours would name the Commonwealth overlay's own cell range.
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

## The Creation Kit can do it from the command line (Claude-cloud, 2026-10-22, read-only)

Strings in the owner's `CreationKit.exe` (239,885,664 bytes) show these command-line operations (**verified** as
strings; their behaviour is **unresolved** until a run):

- `-MockWorldSpaceLOD:<ESMFilename> <WorldSpaceName0> [WorldSpaceName1] [...]`. "Mock" may mean placeholder LOD;
  the run shows what it writes.
- `-GenerateMeshLODAssociations:<ESMFilename> [AdditionalPlugin]`, plus `-GenerateMeshLODStats` and
  `-GenerateMeshLODFailureReport` (both `<ESMFilename> <DestinationFileName> [AdditionalPlugin]`).
- The output paths named in the program are `Data\LODSettings\%s.LOD`, `Meshes\LOD\Generated\%s.nif`,
  `LOD\Generated\Composite\`, `Materials\LOD\Generated`, `Data\Textures\LOD\Generated\Merged\...`, and an
  `LODRuntimeDB` (`.bgsdb`).
- The window also has a "Generate LOD" command.

So the spike needs no clicking if these work. Its plan:
1. A vanilla oracle first: `CreationKit.exe -MockWorldSpaceLOD:Starfield.esm LC172World`, then compare its output
   with the shipped `lodsettings/lc172world.lod` and the LC172 meshes. The CK writes loose files into the game's
   `Data`, and a name listing cannot tell a new file from one it overwrote (a file left by an interrupted run, or
   another loose-file mod's), so before the run copy every loose file under the output paths above
   (`LODSettings`, `Meshes\LOD\Generated`, `Materials\LOD\Generated`, `Textures\LOD\Generated`, `distantlod`)
   to the staging folder and record a sha256 listing of all of `Data`'s loose files; after the run, move every
   new file to staging, restore every changed file from the copy, and check the listing matches again. Only then
   is `Data` as it was. This install reads no loose files, so nothing reaches the game meanwhile.
2. The tiny custom-world gate from the plan above, with the same backup: the same command on a plugin of ours
   with one new worldspace of a few cells and a handful of large converted STATs (an experiment core cut to a few
   cells, as the `make_exp2*` plugins are). A vanilla world proves nothing about a new plugin's world, and a
   failure on the full core would not tell custom-world support from scale.
3. Only on a pass there, the same command on our core (`FO4TerrainCore.esm`, world `FO4Core_Commonwealth`). It
   has 648k references, so it is timed, run at Idle, and needs disk room.
4. If it works, the generated files go into a ba2 beside the core, with their own installer, as for the map
   markers.
