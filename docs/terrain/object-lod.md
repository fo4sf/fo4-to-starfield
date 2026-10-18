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
bytes** (2 are 22, 1 is 16). Twenty bytes is an **observed common size**, not a validity gate. Examples:
`lc172world` / `landingoverlay01` `FE FF FF FF FE FF FF FF 08 00…`; `newatlantis`
`DD FF FF FF C5 FF FF FF 88 00…` — cell min/size, **supported**. A CK-produced file of 16, 20, or 22 bytes
that names the overlay and is referenced by generated `_lod_*` meshes is a candidate; inspect that fixture,
do not reject on size. FO4 object LOD is `.bto` (FORMAT-GAP); not this format.

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

CK is the hypothesized generator of `lodsettings` + object LOD meshes. The `-MockWorldSpaceLOD` flag is
**community-supported** (not CK-proven on this overlay) from
[r/starfieldmods 1ntdwu9](https://www.reddit.com/r/starfieldmods/comments/1ntdwu9/) (primary firsthand
procedure). Pin the **saved** plugin name and extension from the CK Save dialog; do not assume `.esp`.

```
CreationKit.exe -MockWorldSpaceLOD:<SavedPluginName> <WorldspaceEDID>[,<Worldspace2>,...]
```

Example shape only: `CreationKit.exe -MockWorldSpaceLOD:MyMod.esm FO4Core_Commonwealth` if Save wrote `MyMod.esm`.

**Input preparation (required before generate):** assign the intended references to a **layer enabled for LOD**,
then **save the plugin**. Missing output without that eligibility pin is **inconclusive**, not evidence that
this worldspace cannot generate LOD.

Outputs land in `Data\LODSettings\<edid>.lod` and `Data\Meshes\Terrain\<Worldspace>\` (or
`meshes/lod/generated/` for the runtime pair used by overlays; confirm on the spike). This repo has no
object-LOD writer. Per-mesh `sfmesh` LOD index arrays are not world object LOD.

## .lod format (**supported hypothesis**, 20-byte files only)

From [ConvertFromLOD.cs](https://github.com/UnknownExplorer13/Bethesda-LOD-File-Generator/blob/01380dce14898a3a2ebea41ef151b094d4d83e11/Bethesda%20LOD%20File%20Generator/ConvertFromLOD.cs)
at `01380dce14898a3a2ebea41ef151b094d4d83e11`. The extractor selects **16-byte legacy** and **20-byte newer**
layouts and rejects other lengths. The five-int32 struct below is the **20-byte hypothesis only**. Do not
force 16-byte or 22-byte CK output into it. Inspect and retain unsupported lengths; they do not fail the
CK spike.

```c
struct lodsetting {              /* 20-byte files only */
    int32_t objBoundMinX;        /* 0x00 */
    int32_t objBoundMinY;        /* 0x04 */
    int32_t size;                /* 0x08 derived from max-min; do not hard-code */
    int32_t unk1;                /* 0x0C usually 0 */
    int32_t unk2;                /* 0x10 usually 0 */
};
```

NewAtlantis example (`DD FF FF FF C5 FF FF FF 88 00 00 00 00 00 00 00 00 00 00 00`): minX=-35, minY=-59,
size=136, unks=0. Matches the plan's 20-byte `newatlantis` hex. Creation/size derivation remains
**unresolved**. CK-generated fixture from the spike is the acceptance gate; do not hand-author.

## Pins and recovery (before any install)

Claude records, on the private evidence volume, a trial pin set: source git SHA, CK build/version, Starfield
exe version, overlay plugin hash, BA2 hashes, `Plugins.txt` / load order, INI cell-buffer and fade values,
and `FO4Port.deploy.json` if using `scripts/deploy_starfield.py`. Install and uninstall go through that
deployer ([S2-S4-S9](../spikes/S2-S4-S9-plugin-units-loading.md)); do not imply that generating files in a
scratch folder isolates the live install. Failed and passing captures stay on the second local volume
([progress-storage.md](../testing/progress-storage.md)). Owner set is unchanged: Claude owns CK/stage/game;
Grok hands docs/patches; Codex reviews.

## Trial (Claude window; Grok hands docs/patches only)

1. **Tiny overlay spike (go/no-go).** Duplicate a vanilla unique overlay (LC172-class), place a handful of
   large vanilla STAT, **assign those refs to a LOD-enabled layer, save the plugin**, then run
   `CreationKit.exe -MockWorldSpaceLOD:<SavedPluginName> <WorldspaceEDID>` using the name CK just wrote.
   Pin the saved filename/extension. Pass = CK writes `lodsettings/<edid>.lod` plus
   `meshes/lod/generated/…_lod_0..3.nif` (or the Terrain path) that name those STAT. Inspect the actual
   `.lod`: 20-byte files may match the five-int32 struct; 16-byte and 22-byte files are retained and
   **not** forced into that schema. Missing output **without** the layer+save pin is inconclusive, not a
   fail of the worldspace. Fail of the spike = eligible refs + saved plugin + command produced nothing
   usable. **Do not write lodsettings or `_lod_*` by hand**.
2. **Only then** the same generate for `FO4Core_Commonwealth` on a scratch overlay that already has the
   #296 marker (LCSR tail `0xFFFFFFFF`). Start with large STAT (Red Rocket, sanctuary houses), not every
   clutter ref. Output is **verified CK generator output**, not a hand stub.
3. **Row-24 A/B at Red Rocket (world view).** Two fresh sessions, **identical** camera/world/player
   coordinates, INI, load order, and plugin except the generated LOD pair present vs absent. Pin the look
   target (Diamond City / sanctuary houses) and its player distance. The LOD-absent control must show that
   target **unloaded / not full-detail** at those coordinates (screenshot or cell-log); do not convert
   `uExterior Cell Buffer=36` into a 6-cell streaming radius as acceptance evidence. Retain both captures.
   Pass = the **same** far STAT visible with LOD files and missing without them, after that unload is
   observed. A distant silhouette in a single session is not that proof. Surface-map 3D view is a
   **separate** check, not a substitute for this world-view pair.
4. **Writer later, if the spike passes.** A separately reverse-engineered `lodsettings` / `_lod_*` writer,
   scoped on #32, with its own gate: it must match a CK-generated fixture from step 1 or 2, not a guessed
   20-byte stub. Claude owns that edit and the stage.

## Not this trial

- Porting FO4 `.bto`.
- Raising `uExterior Cell Buffer` as the product fix.
- Unparenting the overlay from Mars.
- Garage-button wiring (#303) or NIF rig.
- Native acceptance from offline file counts.
- Hand-authored lodsettings as a stand-in for CK generate.

## Acceptance

Claude: complete the pinned A/B in step 3. Pass = far STAT present only when the generated LOD pair is
installed, at recorded coordinates, with both captures retained. Offline `check` cannot see the LOD camera.
