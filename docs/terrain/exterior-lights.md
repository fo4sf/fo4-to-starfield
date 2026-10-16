# Exterior lights: FO4 LIGH -> native Starfield LIGH (core64 builds)

Author: Claude, 2026-10-16. Status: **offline only**. Nothing deployed or queued, and the game was not launched.
Labels as in the other terrain docs: **verified** means read from files, **supported** means a hypothesis with
evidence, **unresolved** means open. The owner's playtest found the nights dark: core64c placed none of FO4's
6,275 exterior Light references (`exterior.TYPE_REASONS`).

## Path

```
python scripts/terrain/make_cluster.py lights --work <core64c work> --fo4 <Fallout4.esm> --out lights.json [--lumens-per-m2 333]
python scripts/terrain/make_core64c.py stage ... --cluster <cluster with "lights" (and "containers")>
python scripts/terrain/make_core64c.py check ...
python scripts/terrain/light_census.py --sf-esm <Starfield.esm> --fo4-esm <Fallout4.esm>   # the evidence below
```

1. **`make_cluster.py lights`** reads every exported reference of type `Light` from the band exports. The exports
   carry no light data, so it reads the rest from `Fallout4.esm` with the raw record walker (`src/fo4sf/fo4light.py`
   over `fo4land`; no Mutagen):
   - the LIGH bases;
   - each reference's own light fields (`XRDS`, `XLIG`, `XEMI`), found in the Commonwealth worldspace.

   It maps both to Starfield fields (tables below) and writes `{"light_bases": {FO4 base: fields}, "lights": [...]}`,
   ordered by FO4 source key.
2. **`make_core64c.py stage --cluster`** (`cluster_lights`, `stage_lights`) works in three steps:
   - It converts positions to metres and cells, and drops lights outside the overlay's cells as `outside_terrain`.
   - It names one LIGH per FO4 base, `FO4Core_ligh_<6 hex>_<plugin>`, formed the same way as the container names.
   - It refuses a light whose source is a placed or promoted reference, a light listed twice, an unknown base, or an
     XLIG fade outside the vanilla range.

   `objects.json` gets `lights` and `light_bases`. The promoted lights leave `skipped.json`, so placed + promoted +
   lights + skipped still add up to the export.
3. **`TerrainOverlays`** writes the records: `ReferenceIdentityPlan.Lights` validates the input before anything is
   written, then the writer adds the light block after the NAVM block. Each LIGH is a copy of the vanilla
   `LGT_Interior_Omni_NS_Warm_004_2k` (12A74B:Starfield.esm) with the mapped fields. That light is the most-placed
   omnidirectional light in vanilla exterior cells (328 placements), so every Starfield-only field (contact shadow
   component, barndoors, roundness, gobo data, area light, layer, adaptive lighting, volumetric scale) is a vanilla
   value. Its CK object-window filter component is dropped. Each light gets one temporary REFR in its cell.
   `formids.json` gets `"lights": {src: {"base", "ref"}}`, but only when there are lights.
4. **`check`** verifies the result:
   - the light identities (`check_light_identities`), and that every light record comes after the rest
     (`lights_after`);
   - LIGH count = light bases;
   - the REFR total includes the lights;
   - each LIGH's raw `DAT2` (radius, colour, flags, lumens, type, flicker effect) and each light REFR's base,
     position, flags, `XRDS` and `XLIG` (`light_record_problems`);
   - lights per cell, and each light in the cell of its position.

   The NAVM-order check ignores the light REFRs, which come after the NAVMs.

## Reference identities: which FormIDs the lights get, and why

The lights get **new** FormIDs, placed after every other record of the build: first the light REFRs in `lights` order,
then the LIGH bases in first-use order. On core64g's inputs (containers + navmesh) the first light REFR is **0A5AA3**,
right after core64g's last NAVM (0A5AA2).

- **No slot to keep.** `ReferenceIdentityPlan.Order` keeps a promoted source's original REFR slot because that
  source *had* a REFR in the earlier builds (containers are placed statics first). core64c never placed a light, so a
  light has no earlier id. `ReferenceIdentityPlan.Lights` refuses a light that claims a `reference_index`, or whose
  source is one of the reserved ones.
- **Appending moves nothing.** Every id after an inserted record would shift by the number of lights: 6,249 REFRs
  plus 144 bases, landing on CONT bases and NAVMs that a save or the NAVI may already name. Appended at the end,
  every record of the build without lights keeps its id and its bytes:
  - the synthetic writer test compares this byte for byte;
  - the full-scale dry run below compares every `formids.json` entry.
- **REFRs before bases**, as with containers: the ids a save can hold come first.
- **Limit (as for CONT bases, docs/testing/container-reference-identities.md).** A later build that adds records in
  front of the light block moves the whole block. #235's MISC bases sit before the NAVMs, so they would shift the
  NAVMs and the lights alike, but never onto another record's id. A persistent allocator (#227) would make the
  light ids stable as well.

## Field mapping: LIGH base

The FO4 side was read raw from `Fallout4.esm` (`DATA` offsets in `fo4light.parse_ligh`). On all 146 Commonwealth
exterior bases it agrees field by field with Mutagen.Bethesda.Fallout4 0.55 (**verified**: 146/146 bases and
6,275/6,275 references, cross-checked in C:\Modding\scratch\exterior-lights\crosscheck.py).

The Starfield `DAT2` offsets come from the raw records of six vanilla exterior lights: 07AA05, 0D3DC7, 12A74B, 15AE5B,
1690FC, 363BEF. They agree with Mutagen.Bethesda.Starfield 0.55's typed values (**verified**). `light_census.py`
recomputes every count in the tables from raw records, and its numbers equal the Mutagen-based scratch dumps.

"Shared" in the evidence column means the **21 LIGH records that Starfield.esm holds under the same FormID and
EditorID as Fallout4.esm**: MuzFlashLightMachineGun, defaultLight01-04, ExplosionLight*, FXFireLight01 and others.
They show how Bethesda carried FO4 lights over.

| Starfield (`DAT2` offset / Mutagen name) | From FO4 | Rule | Evidence | Label |
|---|---|---|---|---|
| EDID | base formkey | `FO4Core_ligh_<6 hex>_<plugin>` | same scheme as containers | - |
| OBND (6 f32) | OBND (6 i16, units) | / 70 | Starfield OBND are metres (12A74B: +-0.14 to 0.27) | supported |
| +0 Time | DATA time | copied (-1) | 146/146 FO4 bases and the vanilla lights are -1 | verified |
| +4 Radius (f32, m) | DATA radius (u32, units) | / 70, the project's unit (positions are / 70 too) | shared: 400->4, 340->5, 1600->25, 256->4, 128->2 (about / 64, rounded); native radii are 1-8 m | supported |
| +8 Color (RGBA) | DATA colour | RGB copied, A = 0 | 20 of 21 shared copy it; vanilla A = 0 | verified |
| +12 flag 0x1 | FO4 0x1 (dynamic) | carried | 1,560 of 1,575 vanilla set it; every shared FO4 record with 0x1 has it, every other FO4 bit is cleared | supported |
| +12 0x20 OffByDefault | FO4 0x20 | carried (35 refs: workshop bulbs) | Mutagen's name in both schemas; 18 vanilla | supported |
| +12 0x40 DisableSpecular | FO4 0x8000 non specular | carried (1,034 refs) | Mutagen's name only; 66 vanilla | hypothesis |
| +12 0x2 CanBeCarried | FO4 0x2 | carried (none in the Commonwealth) | Mutagen's name | - |
| +16 FalloffExponent | DATA | copied | shared copy it | verified |
| +20 FOV | DATA | copied (degrees) | shared copy it | verified |
| +24 NearClip | DATA (units) | / 70 | shared copy the unit value verbatim (7.2174); native lights use 0.15-0.25 m | unresolved |
| +28 FlickerPeriod, +32 FlickerIntensityAmplitude | DATA | copied | shared copy them; native `LGT_Exterior_Spot_SS_Warm_003_Flicker_4k` uses 1 / 1 | supported |
| +36 FlickerMovementAmplitude | DATA (units) | / 70 (a distance) | shared copy it verbatim but never flicker; 32 units is 32 m if left unconverted | supported |
| +52 PbrLuminousPowerLm | FNAM fade, radius | `333 x fade x scale x radius_m^2`, rounded, at least 1 | `LGT_*_2k / _8k / _75k` hold 2000 / 8000 / 75000; omni lumens / radius^2 over 4,712 vanilla exterior placements: median 333 (p25 78, p75 1,667); scale: next table | supported, needs a night screenshot |
| +56 Type | FO4 0x400 / 0x4000 | 0x400 -> 1 shadow spot (26 refs), 0x4000 -> 2 non-shadow spot (281), else 0 omni (5,942) | Mutagen enum; vanilla LIGH: 459 omni, 649 shadow spot, 467 non-shadow spot | supported |
| +57 FlickerEffect | FO4 0x8 flicker / 0x80 pulse | 1 flicker / 2 pulse (3,069 / 3 refs) | native flicker lights use 1; the shared records dropped flicker altogether (0) | supported |
| record flag 0x10000 | FO4 record 0x10000 | carried (Random Anim Start, 348 refs) | Mutagen's name in both schemas | supported |
| +40 ShadowOffset, +44 InnerFOV, +48 (Mutagen: PbrLightTemperatureK, 0x41200000), adaptive fields, +72 radius falloff exponent, FLCS/FLBD/FLRD/FLGD/LLLD/FLAD/FVLD | - | the template's | 924 vanilla carry the same +48 word without flag 0x200 | supported |
| MODL | FO4 model (424 refs) | **not carried** | 1 of 1,575 vanilla LIGH has a model; the fixtures are separate statics | verified (census) |
| NAM0 gobo (549), LNAM lens (149), WGDR god rays (7), SNAM sound | - | not carried | FO4 gobo textures are not converted; FO4 forms do not exist in Starfield | - |
| FO4 DATA constant / scalar / exponent / god rays near clip / value / weight | - | dropped | no Starfield field | verified |
| FO4 flags no rim (1,087), 0x2000 (1,050), shadow omni (6) / hemisphere (4), attenuation only, ignore roughness | - | dropped | no known Starfield bit | - |
| FO4 flag 0x100000 ambient only | - | **light skipped** (26 refs) | no Starfield equivalent; as a point light it would add white light | - |

## Field mapping: light REFR

| Starfield REFR | From the FO4 REFR | Rule | Evidence | Label |
|---|---|---|---|---|
| NAME | base | the LIGH of its FO4 base | - | - |
| DATA, XSCL | DATA, XSCL | position / 70, rotation copied, scale if != 1 | same rule as the statics | verified (check) |
| record flags | - / 0x800 | **0x100 always**, 0x800 = initially disabled (20 refs) | 28,572 of 28,719 vanilla exterior light REFRs carry 0x100 (meaning unknown); 3 vanilla have 0x800 | supported |
| XRDS (f32) | XRDS (units) | **a radius delta**, / 70 (5,816 refs) | FO4: no XRDS equals its base radius, and the smallest is -0.981 x the base, never at or below -1. Starfield: 10,596 of 24,841 vanilla XRDS are negative (FXFireLight01's refs: -0.836 on a 4 m base) | supported |
| XLIG FOV +/- | XLIG FOV delta | copied (degrees) | 19,281 vanilla non-zero, e.g. -52.6 on a 120 degree base | supported |
| XLIG fade | base fade + XLIG fade delta | `ref_intensity / scale`, clamped to [0.01, 1.6] (826 of 6,249 clamp) | every vanilla XLIG fade lies in [0.01, 1.6] (median 0.45), never <= 0: a multiplier, not FO4's +/- delta | hypothesis |
| XLIG end distance cap, shadow depth bias, volumetric | - | 0 | FO4: 0 on every Commonwealth light except the bias (1-50); vanilla uses 0 | supported |
| XLIG near clip | XLIG near clip delta (units) | / 70 | - | supported |
| XLIG trailing 8 bytes | - | `ab ab ab ab 00 ab ab ab` | 27,305 of 28,070 vanilla XLIG (all 32 bytes) | verified |
| XEMI (368 refs), enable parent (190) | - | not carried | same as the statics' enable parents | - |

**Intensity scale.** FO4 sets a light's intensity per reference: base fade plus the XLIG fade delta. Relative to the
base this ratio runs from 0.08 to 15 (p1 to p99) across the Commonwealth. One LIGH per FO4 base cannot hold that range
in the vanilla XLIG band, so each base takes the **median** ratio of its references (`fo4light.base_scale`) into its
lumens, and each reference keeps `ratio / median` as its XLIG fade. Three cases follow:

- **Clamping.** 826 references clamp. If each base kept its own fade, 1,612 would.
- **References without XLIG.** They get one (fade `1 / median`) when the scale is not 1.
- **Lumens across the references.** p10 1,224, median 4,356, p90 17,655. The most-placed base, defaultLightFire01NSFlicker
  (746 refs, scale 3.96), gets 17,655 lm at 3.66 m.

## Evidence files

Scratch files, outside the repo, in C:\Modding\scratch\exterior-lights (derived from game files, so not committed):

- `census.json`: the output of `light_census.py` on both masters.
- `sfbases.txt`, `sf_raw.txt`: the six vanilla lights, typed and raw.
- `fo4bases.txt`, `fo4_table.txt`: the 146 FO4 bases.
- `fo4_light_ref_overrides.json`: Mutagen's reading of the 6,275 references.
- `crosscheck.py`: the raw reader against Mutagen.
- `commonwealth_lights.json`: `make_cluster.py lights` on core64c's work.
- `core64g_lights\`: the full-scale stage and check, described below.

## Full-scale dry run (offline)

core64g's inputs were staged into scratch (`core64g_lights\`) and checked on 2026-10-16:

- `--core terrain_core64`;
- `--cluster` = `commonwealth_containers.json` + `commonwealth_lights.json`;
- `--navmesh` = core64g's `navmesh.json`.

**Verified:**

- **Lights.** `make_cluster.py lights` takes 6 s and writes 6,249 lights over 144 LIGH bases. The 26 ambient-only
  references are skipped, and none falls outside the cells.
- **Stage.** 158 s. FO4TerrainCore.esm grows from 192,662,677 to 193,414,549 bytes, and next FormID is 0x0A739C.
- **Check.** 254 of 254 checks pass in 184 s (core64g: 250; the 4 new checks are the light identities, the LIGH
  count, the order and the raw records). REFR total 654,609 = 643,173 + COC marker + anchor + 5,185 containers +
  6,249 lights.
- **Every earlier id kept.** Against core64g's `formids.json`, the plugin, world, bases, refs, containers, navmeshes
  and navi entries are identical. Against core64g's plugin, all **676,516 records are byte-identical** (signature,
  header flags, decompressed fields, parent group). The build adds exactly 6,249 REFR + 144 LIGH at
  **0A5AA3..0A730B** (light REFRs) and **0A730C..0A739B** (LIGH).
- **Unchanged files.** `objects.json` without the two light keys, `plan.json`, `overlays_params.json` and the Mars
  plugin equal core64g's.
- **Mutagen read-back.** A typed read with Starfield.esm as master finds 144 LIGH and 6,249 light REFRs in the
  exterior cells. 5,816 carry XRDS, 5,998 XLIG, 20 are initially disabled, all 6,249 have flag 0x100. By type:
  5,942 omni, 281 non-shadow spot, 26 shadow spot.

## Not done / open

- **Not tested in game.** The acceptance is a night screenshot at Red Rocket and in Sanctuary (the runner sets the
  time of day) next to the same view without lights. Brightness then tunes `--lumens-per-m2`.
- **XLIG fade semantics are a hypothesis.** If Starfield adds the fade to 1.0 instead of multiplying by it,
  references come out up to twice as bright. If it ignores the fade, each base shows its median.
- **Not carried:** light models (bulbs, klaxons, 424 refs), gobos, lens flares, emittance, and FO4 shadow omni and
  hemisphere lights (they become omni lights without shadows).
- **Unknown cost:** the frame-time cost of 6,249 lights, 5,942 of them omni without shadows, in dense cells
  (Diamond City) has not been measured.
