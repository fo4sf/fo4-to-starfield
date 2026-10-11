# The whole Commonwealth as native Starfield terrain: size limits, options, generator, experiment 3

Author: Claude, 2026-10-11. Branch `claude/commonwealth-terrain-scale`, stacked on PR #64
(`claude/terrain-overlay-records`, which contains #60, #57 and #56). Starfield 1.16.244. Nothing here ran in game or
in the Creation Kit. Labels: **verified** (checked offline on files, command or number given), **supported**
(supported hypothesis), **unresolved**.

Already verified in game before this work (runner, 2026-10-11, `C:\Modding\research\terrain\binding\findings.md`):
a worldspace's own BTD applies only when it is an overlay activated on a planet (PNDT `CNAM` entry); activation merges
its cells into the planet worldspace at a whole-cell XY offset plus a Z offset; the outer cell ring of an overlay is
blended with procedural ground (LC172World border cells 4 to 6 m off, inner cell within 0.02 m).

## Short answer

1. **The full LAND grid cannot be one landing in any option.** The Commonwealth LAND grid is 192 FO4 cells =
   11,234.7 m = 114 Starfield cells per side. Starfield's default game terrain width is **100 cells** with a
   **5-cell** playable buffer (decoded from Starfield.exe, **verified** values, meaning **supported**), and the
   largest overlay any planet registers is **14 x 14 cells** (**verified**). The 108 BTDs of 100 x 100 cells are
   editor and test worlds, not overlays or surface blocks (**verified**).
2. **The playable Commonwealth fits.** Cells with at least 20 placed references span FO4 cells x -34..31, y -39..31:
   3.86 x 4.15 km, **39 x 42 Starfield cells** (**verified**). With 1.2 to 2.5 km of visible surroundings that is
   64 to 90 cells, inside one landing.
3. **Recommendation: (a) one overlay** for the playable Commonwealth plus its surroundings (64 to 90 cells, Absolute
   alignment), placed in the middle of the landing by a measured lat/long. **Fallback: (b) a grid of 14-cell
   overlays**, edge-matched by construction, if a large overlay fails. (c) a custom planet surface stays research; (d)
   static mesh tiles only for terrain the BTD cannot hold (the far ring, cliffs). Exactness argument: (a) has no seams;
   (b) has a 1-cell merge ring at every seam whose behaviour is unknown (experiment 3 measures it).
4. **Generator built**: `scripts/terrain/make_cw_overlays.py` + `src/fo4sf/overlay_grid.py` + `dotnet/TerrainOverlays`
   write the BTDs, masks, SFBK / LCTN / WRLD / cells / anchors and the Mars registration for any FO4 cell rectangle,
   as one overlay (`--tile` at least the region) or a grid. 22 synthetic tests.
5. **Experiment 3 staged** (`C:\Modding\staging\terrain_exp3`): 2 x 2 overlays of 14 x 14 cells around Sanctuary,
   Vault 111 and Red Rocket, one shared height range, masks 0 on the seams, an anchor and a COC cell per tile, placed by
   hypothesis H_ll so they should lie edge to edge. 8 plan entries, 68 points, pairs on both sides of all 4 seam
   segments. Offline check: 277 of 277 items pass, worst point 5.03 mm (step 5.17 mm).

## 1. Size limits

### 1.1 Vanilla overlays and blocks (verified)
Raw walk of Starfield.esm (scratch `scan_planets.py`, output `C:\Modding\research\terrain\scale\planets.json`):

| What | Sizes (cells per side: count) |
|---|---|
| SFBK of the 430 overlay worldspaces (`WRLD` overlay `BNAM`) | 3: 207, 4: 121, 5: 77, 6: 3, 7: 3, 8: 7, 9: 1, 10: 5, 11: 3, 12: 1, **14: 2** (NewAtlantis, SettleWaggonerFarm) |
| Overlays registered on a planet (PNDT `CNAM`, 72) | 3 to 14; the 14 largest are cities and settlements |
| Overlay source blocks (`NAM1 OverlaySource\...`) | 3, 4, 5: 135 each |
| Procedural surface blocks (`NAM1` = theme) | **14** ("1K" themes): 616, **26** ("2K"): 217 |
| SFBK with `DNAM` 100 x 100 | 1: `OverlayBlockTestPCMBaseSurvey01Overlay`, no WRLD in the shipped esm |

The 108 BTDs of 100 x 100 cells (architecture.md 1.4): all top-level `terrain/*.btd`, all with the default range
-500 / 1000 m (= `fTerrainMinHeight` / `fTerrainMaxHeight` below), 92 of them 4,210,995 or 4,211,023 bytes (the same
flat default terrain). 100 have neither an SFBK nor a WRLD in Starfield.esm, 5 have a test overlay block
(`TestPCM*`, `lc136worldDUPLICATE000`, `xxTestLightingGIWorld02`), 3 have a WRLD (`DefaultWorld` with 0 cells,
`TempJemisonWorld` without an overlay component, `OutpostOverlayTemplate`). None is registered on a planet. They are
the editor's default terrain for new worlds (`uDefaultEditorTerrainWidthInCells` = 100), not proof that a 100-cell
overlay works in game. Scratch `btd100.py`.

### 1.2 Engine and CK defaults (verified values; meaning supported)
Method: each INI setting is a static object built by a 4-instruction initialiser (`mov r8d, value` or
`vmovss xmm2, [constant]`, `lea rdx, name`, `lea rcx, object`, `call`). Scratch `inidefaults.py` finds the code that
references each name string in Starfield.exe and decodes the value; `xref_lea.py` / `xref_addr.py` follow the CK's
"maximum recommended cut dimensions are %1x%1" message to the setting it formats.

| Setting | Default | Reading (supported unless marked) |
|---|---|---|
| `uDefaultGameTerrainWidthInCells:Terrain` | 100 | width of a worldspace's terrain in game: a landing (planet worldspace) is 100 x 100 cells |
| `uDefaultEditorTerrainWidthInCells:Terrain` | 100 | same in the editor; matches the 108 test BTDs |
| `uPlayableSpaceOverlayCellBuffer:Planet` | 5 | buffer cells at the edge of the playable space (CK string: `GetHalfPlanetPlayableWidthInCells() > aCellBuffer`) |
| `uOverlayMergeZoneSize:Overlays` | 1 | the 1-cell ring an overlay blends with planet ground (matches the LC172World measurement) |
| `uBlockSize:Stitching` / `uBlockMergeZoneSize:Stitching` | 10 / 2 | surface blocks: 10-cell core, 2-cell merge zones; 14 = 12 + 2 and 26 = 2 x 12 + 2 fit a 12-cell pitch with 2-cell overlaps |
| `uHeightMergeStyle:Stitching`, `uMaterialMergeStyle` | 1, 1 | blend style in merge zones (meaning unresolved) |
| `uPlanetBiomMapFaceDim:Planet` | 256 | = SFTR `DNAM` edge 256 (all 1,505 trees), 2 faces (`CNAM` 2) |
| `uAlignment:Overlay` | 4 | default alignment mode; 4 = Median in the SFBK `JNAM` enum (xEdit) |
| `bUsePlacedOverlayParentOffset:Overlay` | 0 | |
| `uMinCellsFromBorder:Landing`, `uLandingKeepBufferSize:Landing` | 17, 3 | landing site constraints |
| `fCellWidthToNewOverlayMultiplier:Landing` | 3.0 | |
| `iPlanetContentBlockOverlaySafeZoneBufferSize:PlanetContent` | 10 | cells kept free of procedural content around overlays |
| `fTerrainMinHeight` / `fTerrainMaxHeight`, `fDefaultTerrainZMin/ZMax` | -500 / 1000 | default BTD range (verified: matches all 108 test BTDs) |
| `uMaximumPlayableAreaWorldCoord:General`, `fPlayableAreaX/Y/Z` | 4096, 100 / 100 / 50 | unresolved (probably space) |
| `bDisableWorldShift`, `bDisableTerrainShift` | 0, 0 | world and terrain shifting are on |
| CK `iBlockCutRecommendedMaxDimensionExclusive:General` | 6 | **the CK recommends overlays under 6 x 6 cells** (the value the "%1x%1" message prints) |

### 1.3 The Commonwealth (verified, Fallout4.esm)

| Extent | FO4 cells | Metres | Starfield cells | Heights |
|---|---|---|---|---|
| LAND grid | -96..95 (192) | 11,234.7 | 114 | -118.86..641.03 m |
| Placed references, cells with at least 20 | x -34..31, y -39..31 | 3,862 x 4,155 | 39 x 42 | -118.86..302.74 m |
| Pip-Boy map (WRLD `MNAM` NW (-33, 25), SE (28, -36)) | 62 x 62 | 3,628 | 37 | -118.86..295.66 m |
| 64-cell window on the playable core | | 6,400 | 64 | -118.86..521.37 m |
| 90-cell window on the playable core | | 9,000 | 90 | -118.86..641.03 m |

55 % of the LAND cells have a mean height below 0 (sea and rivers; water is not handled by this track).
BTD size: 30.6 to 34.2 KB per cell in experiment 3 (32.8 in experiment 2); one 64 x 64-cell overlay of the
playable core measured 103.2 MB (25.2 KB per cell, generator trial in section 5), so 90 x 90 is about 200 to 270 MB
and the full 114 x 114 about 330 to 430 MB, in one plugin BA2. The BTD stores every cell and LOD level as
its own zlib block, so streaming per cell is possible (**supported**; whether the overlay merge loads a whole BTD at
once is **unresolved**).

### 1.4 What follows
- One landing holds at most about 90 x 90 usable cells (100 minus the buffer) (**supported**). The full 114-cell
  LAND grid does not fit in any option; the outermost ~1 km ring (FO4's own unplayable, LOD-only terrain) can only be
  cropped, drawn as planet LOD (option c) or as static LOD meshes (option d).
- A single overlay of 64 to 90 cells is 4.6 to 6.4 times wider than any vanilla overlay. Experiment 2b (29 cells,
  queued) is the first in-game data point above 14.

## 2. Where an activated overlay lands (lat/long -> planet cell)

- **PNDT `CNAM` order (verified):** each entry is f64 latitude, f64 longitude (radians), u32 WRLD. Evidence: the 11
  Earth overlays sit at their real cities with the first value as latitude: LC146World (34.91, 135.73 deg) Kyoto,
  LC152World (22.15, 114.33) Hong Kong, LC154World (30.38, 30.97) Cairo, LC144World (38.58, -91.20) St. Louis,
  lc017world (28.46, -81.42) Orlando; CydoniaCity on Mars at (41.03, -9.80) = the real Cydonia region. Mutagen 0.55
  names the first value `Longitude` and the second `Latitude`; our builders write the latitude into Mutagen's
  `Longitude` (TerrainOverlays) and the check reads the raw bytes. In these terms experiment 1's World01 is at
  latitude 0.2, longitude 1.2 rad and experiment 2b at latitude 0.3, longitude -1.2.
- **Measured (runner):** World01 (0.2, 1.2) -> local origin at planet cell **(+30, -35)** (both registered runs);
  LC172World (-0.043119, -0.087881) -> **(-5, -23)** (anchor 0010238E, run `terrain_A2_lc172`: offset -500, -2300,
  Z -3.62).
- **No absolute rule found (unresolved):** 7 projections (equirectangular, sinusoidal, orthographic, azimuthal
  equidistant / Lambert per hemisphere, Mercator, swapped axes) x 13 scales (Mars radius; 49,152 = 256 x 16 x 12 cells
  per face over pi, pi/2, 2 pi; 14- and 10-cell pitches) x 4 sign choices x 20 origin grids (1 to 256 cells, floor or
  round) reproduce both measurements in 0 cases (scratch `latlon_fit.py`). Two points cannot separate projection,
  scale and the landing's origin snapping.
- **Local scale (supported):** hypothesis H_ll: near a registration the offset moves at true planet scale, x east =
  R cos(lat) dlon / 100 m, y north = R dlat / 100 m (Mars R = 3,390 km from its PNDT body data: 33,900 cells per
  radian). Vanilla clusters agree within a factor of about 2 (scratch `clusters.py`): the 8 Cydonia overlays never
  overlap for scale factors 0.5 to 4 but do at 0.25, and span 51 x 79 cells at 1 (fits in one 90-cell landing),
  91 x 148 at 2 (does not); Akila (2 overlays) and Ixyll II (3) show the same picture. So 0.5 <= s <= about 1.1 if the
  Cydonia overlays are meant to share one landing.
- **Consequence:** edge-to-edge overlays need the local rule measured once (experiment 3 does that with an anchor per
  tile). A single overlay only needs a lat/long that puts it in the middle of the landing; experiment 2b's anchor
  measures its offset at (0.3, -1.2) for that.

## 3. Options

| | (a) One big overlay | (b) Grid of adjacent overlays | (c) Custom planet surface with our blocks | (d) Static mesh tiles |
|---|---|---|---|---|
| What | One WRLD + SFBK + BTD (64 to 90 cells), Absolute, one PNDT entry | N x N overlays of <= 14 cells, one PNDT entry each, lat/longs edge to edge | A planet (new, or an override of an unused one) whose surface tree (SFTR: 2 faces x 256 x 256 pattern slots) points at our patterns (SFPT: 16 x 16 block slots) of our 14-cell blocks (SFBK + BTD) | FO4 LAND triangles as `.mesh` tiles with collision, placed as statics over a flat or lowered ground |
| Geography | exact (1 sample = 0.78 m, quantisation 6 to 12 mm; FO4 cliffs lose up to 1.4 m, experiment 2) | exact inside tiles; at seams unknown | exact only if block alignment and merge blending keep absolute heights (unknown) | exact (FO4's own triangles) |
| Seams | none inside; outer 1-cell ring blends into planet ground (fine: outside the playable area) | every seam has two 1-cell merge rings (`uOverlayMergeZoneSize` 1). With mask 0 on seams they may stay exact (unknown); if blended, a 200 m strip per seam is wrong by metres (LC172: 4 to 6 m) | blocks overlap by 2 cells; equal heights in both blocks blend to the same values (supported) | tile edges share vertices (we control them); none with the ground if it is hidden |
| Placement | lat/long so the overlay sits in the middle of the 100-cell landing: one measurement (exp2b gives one) | the local lat/long rule to the cell (exp3); rounding to whole cells must not shift a tile | which face cell a lat/long falls in (projection unresolved), or fill every slot | none (worldspace coordinates) |
| LOD / far terrain | BTD LOD0-4 inside; beyond the overlay the planet's procedural ground | same | the planet's own LOD shows our blocks (far terrain is the Commonwealth) | own LOD meshes needed |
| Overlay mask | 255 on the outer ring (vanilla style) | 255 on outer edges, 0 on seams (exp3) | none (blocks have no mask) | n/a |
| Precedent | none above 14 cells (vanilla max), CK recommends < 6 | each tile vanilla-sized | the way every vanilla planet is built (procedural blocks) | statics are routine |
| Effort | done (generator, `--tile` >= region) | done (generator) | large: SFTR (512 KB arrays), SFPT, SFBK sets, rotation byte meaning, face mapping, a planet | large: terrain mesh + collision + materials + LOD pipelines |
| Main unknowns | does a 64-90-cell overlay activate, stream and stay exact; Z offset of Absolute | seam blending; the lat/long rule; overlap refusals ("Overlapping existing overlay") | block height alignment (`JNAM`, Relative), merge style, rotation identity (`GNAM` 0x08?), SFTR overrides ("CK does not copy this on overrides"), procedural content on it | performance at 4,700 to 37,000 tiles; terrain materials |
| Cheapest in-game test | exp2b (29 cells, queued); then a 64-cell core overlay (`--tile 64`) | **exp3 (staged)** | override MarsSurfaceTree so every slot holds one test pattern of one 14-cell marker block; coc LC172Ext01, probe the 12-cell pitch, rotation and heights | one FO4 cell as a mesh tile with collision in exp2b's world, 1 m above the BTD |

Evidence for (c) (**verified** record layout, behaviour **unresolved**): SFTR `CNAM` 2, `DNAM` 256, then per face
`FNAM` 65,536 SFPT FormIDs and `GNAM` 65,536 bytes (almost all 0x08); SFPT `FNAM` 256 SFBK FormIDs, `GNAM` 256 bytes:
(k << 5) | 0x08 for 1 x 1 blocks (eight orientations, equally common) and 0x10 / 0x40 / 0x50 for the other three slots
of a 26-cell block, `DAT2` per-slot height adjustment (0 in most patterns), optional `DNAM` worldspaces: 34 unique
patterns (`PatternCydoniaCity`, `PatternNewAtlantisWorld`, ...) list the overlays placed on them over a full grid of
procedural blocks; 5 surface trees carry a `SurfaceTreePatternSwapInfo_Component` (Mars swaps in 0012268E). CK strings
show unique pattern placement per planet ("current block pattern is already set as unique on a planet", "Original block
pattern for surface tree on ... Point: [ ... Hemisphere:"). So a pattern can place specific blocks at specific slots;
the planet's base terrain can be ours, but none of its height or blending rules is known.

## 4. Recommendation and decision gates

**(a) one Commonwealth overlay** of the playable core plus surroundings, Absolute alignment (`INAM` 1, `HNAM` 0),
its own Location, mask ring 255, registered on a host planet at a lat/long measured to put it in the middle of the
landing. Start at 64 x 64 cells (6.4 km: the 3.9 x 4.2 km playable area plus 1.2 km), grow toward 90 if it works.
Static LOD meshes (d) for the ring beyond only if the far view matters.

Gates, in order (each a queued runner job; nothing else depends on guessing):
1. **exp1d / exp2b (queued):** record fixes; a 29-cell real-terrain overlay, Absolute, Z offset, its merge offset.
2. **exp3 (staged here):** tile heights, seam behaviour with mask 0, the local lat/long rule (anchors per tile).
3. **exp4 (next, generator ready):** if exp2b passes, `--fo4-cells -34 31 -39 31 --tile 64 --pad origin
   --grid-points 4` (the playable core in one overlay, its frame = the CW frame) at a lat/long chosen from exp2b's and
   exp3's offsets; if exp2b fails on size, 14-cell tiles with the exp3 calibration.

Why not (b) first: it is only as exact as its seams, needs the placement rule to the cell, and multiplies records
(the 64-cell core = 25 tiles of 14). Why not (c): every vanilla planet uses it, but the exactness depends on four
unknown rules and it needs a planet. Why not (d): new pipelines (terrain collision, materials, LOD) for what the BTD
already does.

## 5. Generator

    python scripts/terrain/make_cw_overlays.py build --fo4 <Fallout4.esm> --sf-data <Starfield\Data> --out <dir>
        [--fo4-cells X0 X1 Y0 Y1] [--tile 14] [--pad centre|sw|origin] [--grid-points 0] [--prefix FO4CW3]
        [--plugin FO4TerrainExp3.esm]
        [--mars-plugin FO4TerrainExp3_Mars.esm | --no-mars] [--alignment absolute|relative] [--hnam 0]
        [--ref-lat 0.2 --ref-lon 1.2 --ref-offset 30 -35] [--centre-cell 0 0] [--radius-km 3390]
    dotnet run --project dotnet/TerrainOverlays -c Release -- <Starfield.esm> <dir>
    python scripts/terrain/make_cw_overlays.py check --sf-data <Starfield\Data> --out <dir> [--no-plugins] [--verbose]

- `src/fo4sf/overlay_grid.py`: FO4 cell rectangle -> Starfield cells (CW frame = FO4 units / 70), split into n x n
  tiles (padding split between both sides), tile frames (local = CW - origin; the BTD grid rule of terrain_grid.py),
  sample lattices that continue across seams, outer edges, seam segments, the shared height range, H_ll placement
  (`latlon_for_offset`, `predicted_offset`, `group_targets`). `overlay.mask_array(n, edges=...)` writes rings only on
  outer edges.
- `make_cw_overlays.py`: reads FO4 LAND once (`fo4land`, or a cached `.npz`), resamples every tile at its CW sample
  positions (separable bilinear), quantises all tiles with one range, writes BTDs (LTEX of TempJemisonWorld, as
  experiment 2), masks (texconv BC4, or the built-in lossless writer), `overlays_params.json`, `plan.json`,
  `expected.json`, `README.txt`, `preview.png`. Check points are FO4 vertices whose decoded height equals the FO4
  height within one quantisation step under bilinear and both triangle splits, on slopes up to 25 deg.
- `dotnet/TerrainOverlays`: per tile an SFBK (copy of OverlayBlockLC172World: `ANAM`, `DNAM`, `ENAM` = shared range,
  `FNAM` = SW-corner rule, `INAM`/`HNAM`), its own LCTN (keyword LocTypeOverlay, parent SSol_PMars_Surface; the CK
  warns when overlays share one), a WRLD (copy of LC172World) with all n x n cells, a COC cell with a marker 2 m
  above the anchor, and a persistent XMarker anchor; anchors take FormIDs 0x800 + tile index so plan.json can name
  them. The Mars plugin appends one `CNAM` entry per tile.
- One overlay = `--tile` at least the region's size (option a); `--pad origin` puts tile origins on multiples of the
  tile size, so a single overlay over the FO4 origin has its own frame equal to the CW frame (FO4 position / 70 is the
  local position, as in experiment 2); `--grid-points K` adds a K x K spread of check points. The whole LAND grid
  with 14-cell tiles is 9 x 9 tiles (126 cells). Tiles are resampled in row strips and check points decode 2 x 2
  samples, so memory stays per strip (strips equal one resample bit for bit: test).
- Option (a) trial (scratch folder, not staged): the playable core, FO4 cells x -34..31, y -39..31, `--tile 64 --pad
  origin --grid-points 4` -> one overlay of Starfield cells -32..31 on both axes, origin = CW origin, BTD 103,172,485
  B, range -120..503 m (step 9.506 mm), plugin 183,096 B with 4,096 cells, 21 points, check 74 of 74, worst point
  8.5 mm; about 17 s to build.
- Tests (`tests/test_overlay_grid.py`, 22, synthetic heights from a formula): region and padding arithmetic, frames,
  lattice continuity, seams and edges, masks per edge, H_ll round trip and scale, edge-to-edge targets; a full build
  of 2 x 2 tiles of 5 cells whose four BTDs side by side are **exactly** the raw samples of one 10 x 10-cell BTD of the
  same region, plan points are FO4 vertices, seam pairs on both sides at the same along-seam coordinate, the offline
  check passes and catches a wrong expectation and a step at a seam; a single-overlay build (option a: one tile,
  ring on all four edges, no seam entries, origin padding, grid points); row strips equal one resample bit for bit;
  the 2 x 2-sample decode equals point_interp over the whole decoded grid.

## 6. Experiment 3 (staged, not deployed)

`C:\Modding\staging\terrain_exp3` (outside the repo): `FO4TerrainExp3.esm` 39,822 B, `FO4TerrainExp3_Mars.esm`
6,573 B, four BTDs 6,000,752 to 6,701,057 B, four masks 980,128 B, `overlays_params.json`, `plan.json`,
`expected.json`, `offline_check.json`, `README.txt`, `preview.png`. FO4 cells x -35..10, y -6..40 -> Starfield cells
x -21..6, y -4..23 (28 x 28) -> 2 x 2 tiles of 14. Shared range -40..299 m, step 5.173 mm. Built twice, from
Fallout4.esm through `fo4land` and from the earlier cached grid: the four BTDs are byte-identical (SHA-256).

| Tile | CW cells x / y | Own origin (CW m) | Mask ring | Anchor (local) | lat, lon (rad) | Predicted planet cell |
|---|---|---|---|---|---|---|
| FO4CW3_T00 (SW) | -21..-8 / -4..9 | (-1400, 300) | w, s | 02000800 (52.34, 58.40, 88.57) | 0.200825959, 1.198886263 | (-7, -7) |
| FO4CW3_T10 (SE) | -7..6 / -4..9 | (0, 300) | e, s | 02000801 (45.71, 47.43, 9.83) | 0.200825959, 1.199307677 | (7, -7) |
| FO4CW3_T01 (NW) | -21..-8 / 10..23 | (-1400, 1700) | w, n | 02000802 (410.74, -553.49, 105.14) = Red Rocket | 0.201238938, 1.198886216 | (-7, 7) |
| FO4CW3_T11 (NE) | -7..6 / 10..23 | (0, 1700) | e, n | 02000803 (100.57, 49.94, 56.23) | 0.201238938, 1.199307648 | (7, 7) |

- Seams: x = -700 m (T00 | T10, T01 | T11), y = 1000 m (T00 / T01, T10 / T11). Red Rocket (CW -989, 1147), Sanctuary
  (-1154, 1260) and Vault 111 (-1275, 1305) all lie in T01, at least one cell from its seams.
- Placement by H_ll from World01's measured offset, group centre at planet cell (0, 0): adjacent tiles differ by
  14 cells = 4.130e-4 rad in latitude and 4.214e-4 rad in longitude.
- `plan.json`, 8 entries, 68 points, runner format (points and `expect` in the entry's frame, `expect` = FO4 height / 70):
  - 4 tile entries (coc the tile, its own anchor and `spawn_local`): its landmarks or centre, a slope point, and its
    side of every seam it touches at three distances: near (1.5 to 2.2 m), ring (40 to 52 m, inside the 1-cell merge
    ring), inner (140 to 149 m).
  - 1 group entry (coc T00, anchor T00): both sides of all 4 seam segments (24 points) in T00's frame. It passes only
    if the tiles lie edge to edge and the seams are exact.
  - 3 position entries (coc T00, anchor of T10 / T01 / T11, no spawn fallback): each tile's planet cell and heights
    read from T00's landing.
- Offline check (`make_cw_overlays.py check`, raw record walk independent of Mutagen): **277 of 277 pass**. Every point
  decodes within one step under all three interpolation rules (worst 5.029 mm); all seams continue the lattice (largest
  raw step across a seam not above twice the steps beside it; T10 / T11 crosses a 2.7 m-per-sample slope); each WRLD ->
  own LCTN (2CA99D, parent 01B736) -> SFBK (`ANAM`, `DNAM` 14 x 14, `ENAM` -40 / 299, `FNAM` 196 values = rule,
  `INAM` 1, `HNAM` 0); anchors `01000800..803` persistent XMarkers at the plan positions; 4 COC cells; Mars plugin
  overrides 0003F59A with 10 + 4 entries, latitude first; masks decode exactly.

**Reading the result**

| Observation | Meaning |
|---|---|
| Tile entries pass | each tile's heights are exact (H holds for all four; Absolute gives Z offset ~0) |
| Tile entries pass except the `ring` points of seams | the merge ring blends even with mask 0: option (b) cannot be exact at seams; go (a) |
| Group entry passes | tiles edge to edge and seams exact: (b) works and H_ll holds at scale 1 |
| Position entries put T10, T01, T11 at (14, 0), (0, 14), (14, 14) cells from T00 | H_ll holds; other values give the local scale and axes directly |
| A position entry fails `prid` | that tile was not activated in T00's landing (outside the window, or refused as overlapping: scale < 1) |
| Tile entries `NOTERRAIN` | 14-cell overlays do not load where exp2b's does: compare records |
| An anchor reads exactly its local position (offset 0, as in exp1d below) | its persistent refs were not merged (or `prid` read unloaded data); the probes went to the wrong place: take the offset from `spawn_read` - `spawn_local` in `obs.json` and rerun with that |

Runner caveat, **verified** from exp1d's `obs.json` (finished 16:24, while this was written; its analysis belongs to
the overlay-records track): in both attempts the anchor `02000800` read back (50.00, 50.00, 10.00), exactly its local
position, while the COC spawn arrived at (3050, -3450, -500) in attempt 1 and (75.32, 99.74, -19.84) in attempt 2. In
the vanilla control the anchor did move with the merge (LC172World: -500, -2300). Both anchors sit in the world's
persistent top cell (raw walk: group type 8 under the top cell, flag 0x400), so the record layout is not the difference
(**unresolved**). Experiment 3's anchors are built the same way; exp2b (running now) will show whether they move.

## 7. Risks
- A 64 to 90-cell overlay may not activate, may load slowly, or may be cut at the landing's edge; nothing in vanilla
  is that large. Mitigation: grow in steps (29 -> 64 -> 90), fall back to (b).
- The lat/long rule may have per-landing origin snapping that moves a large overlay off-centre; the anchor shows it
  and the lat/long can be corrected.
- Merge rings at seams (b) may be impossible to make exact.
- Water (55 % of LAND cells average below 0 m), FO4 land textures, grass and terrain holes are not handled yet.
- Host planet: Mars is a test host; the final host (a hidden or new planet) changes the Location parent and the
  lat/long reference.
- FO4 cliffs: a 0.78 m grid loses up to 1.4 m at 75 deg cliffs (experiment 2); (d) patches if needed.

## 8. Unknowns
1. Whether the 100-cell game terrain width bounds a landing as read here (supported only by the setting's name and
   value and the measured offsets, all within 35 cells).
2. The absolute lat/long -> planet cell rule and the landing's origin snapping.
3. Overlay size limits in game above 14 cells (exp2b: 29).
4. Seam behaviour between adjacent overlays and the role of the mask in blending (exp3).
5. Option (c) rules: block pitch, height alignment, merge style, rotation identity, face projection.

## Reproduce

    python scripts/terrain/make_cw_overlays.py build --fo4 <Fallout4.esm> --sf-data <Starfield\Data> --out C:\Modding\staging\terrain_exp3
    dotnet run --project dotnet/TerrainOverlays -c Release -- <Starfield.esm> C:\Modding\staging\terrain_exp3
    python scripts/terrain/make_cw_overlays.py check --sf-data <Starfield\Data> --out C:\Modding\staging\terrain_exp3
    python -m unittest tests.test_overlay_grid tests.test_overlay

Install for the runner: `scripts/game/exp_install.py install --exp-dir C:\Modding\staging\terrain_exp3 --plugins
FO4TerrainExp3.esm,FO4TerrainExp3_Mars.esm --pack` (branch `claude/test-queue`), then `testqueue.py plan-terrain
--exp-dir C:\Modding\staging\terrain_exp3 ...`. Never with experiment 1 or 2 installed (all three Mars plugins override
MarsPlanetData).

Scratch scripts (not in the repo; outputs are game-derived) in `C:\Modding\research\terrain\scale\`:
`scan_planets.py` (PNDT / SFBK / SFPT / SFTR / WRLD raw scan), `btd100.py`, `sfpt_worlds.py`, `inidefaults.py`,
`xref_lea.py`, `xref_addr.py`, `latlon_fit.py`, `clusters.py`, `fo4_extent.py`, `fo4_landmarks.py`, `fo4_refpos.py`.
