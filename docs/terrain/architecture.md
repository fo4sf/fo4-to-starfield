# Starfield terrain architecture for the Commonwealth (S5 / WP-12)

Author: Claude, 2026-10-11. Branch `claude/terrain-architecture`. Status: **offline research done, in-game test pending**.

Labels used below: **verified** = measured here, command and number given; **supported** = supported hypothesis
(evidence points one way, not proven in game); **unresolved** = not known yet. Community claims from the web are
marked **unverified** unless we measured the same thing. Nothing about terrain has been tested in game yet; a terrain
research handoff the owner mentioned could not be found, so this document assumes nothing works until shown.

Goal (owner): a faithful conversion with the Commonwealth as the main authored location, exact geography (no
procedural replacement, no Earth overhaul as the final design). An engine-required planet registration is fine if it
stays behind the scenes. Prefer native terrain; static-mesh terrain only if the evidence forces it.

## Short answer

- Starfield has **no `LAND` records** (verified). Terrain heights live in **`.btd` files**, one per worldspace, plus
  procedural "surface blocks" for planets.
- A worldspace is bound to its BTD by a **record chain**, not only by name (verified for 433/433 worldspaces):
  `PNDT.MasterWorldspaces[]` (planet, latitude/longitude) -> `WRLD` -> `WorldSpaceOverlayComponent.SurfaceBlock` ->
  `SFBK.ANAM = "Data\TERRAIN\<name>.btd"`. Every vanilla WRLD also has `terrain/<EditorID>.btd`.
- The BTD format is fully decodable (verified on real files, byte-exact): 128 height samples per 100 m cell, 16-bit
  heights mapped linearly between a per-file min and max **in metres**, 5 LOD levels, a land-texture (LTEX) table.
  Vanilla ships BTDs up to **100 x 100 cells (10 km x 10 km)** and with custom height ranges.
- So a **dedicated Commonwealth worldspace with its own BTD (option A)** can carry the exact FO4 heights with ~1 cm
  quantisation. It is the recommended path, *if* the engine loads a new worldspace + new BTD from a plugin. That is the
  one thing only the game can answer (experiment 1 below).

## 1. Evidence: how Starfield stores terrain

### 1.1 No LAND records (verified)
Raw walk of the record tree (24-byte headers, every GRUP descended), script `esm_count.py` (scratch, not in the repo):

| | `LAND` | `WRLD` | `CELL` | `LTEX` | other terrain types |
|---|---|---|---|---|---|
| Starfield.esm | **0** | 433 | 30,717 | 416 | `SFBK` 1,753, `SFTR` 1,505, `SFPT` 258, `PNDT` 1,765, `BIOM` 431 |
| Fallout4.esm | 37,020 | 5 | 40,164 | 105 | - |

Same totals as docs/measurements (3,829,247 / 1,549,051 records incl. header). Mutagen's Starfield `Cell` type has
no `Landscape` property at all (`SfInspect landcount`: 18,732 exterior cells, 0 with landscape).

### 1.2 Worldspace records (verified)
`dotnet run --project dotnet/SfInspect -c Release -- <Starfield.esm> wrld` (new read-only command; full dump kept
outside the repo in `C:\Modding\research\terrain\sf_wrld_dump.txt`). 433 WRLD. Fields that matter for terrain:

| Field | What we saw |
|---|---|
| `Components` -> `WorldSpaceOverlayComponent` | 430 of 433. `SurfaceBlock` = the SFBK that names the BTD; `SNAM`, `PNAM` 4-byte values (unresolved meaning; SNAM is not a FormID: resolving it gives unrelated refs/cells) |
| `PlanetContentManagerContentPropertiesComponent` | 351 worldspaces: procedurally placed content (POIs, landing overlays, caves) |
| `Parent` (`WorldspaceParent.Worldspace`, flags) | only 7: six `OverlayTrait*` -> `DefaultWorld` (00003C), and `lc070world01` -> itself |
| `Flags` | `SmallWorld` 428; `0` (NewAtlantis, TempJemisonWorld); `NoLandscape` only on NeonCity (which still has a BTD) |
| `LandDefaults` | `DefaultLandHeight` -2048 for 428; `DefaultWaterHeight` -200 (261), 0 (88), -800 (27) ... |
| `Location` | 432; e.g. NewAtlantis -> `CityNewAtlantisLocation` (parent location 01AB2B) |
| `Biome`, `Climate`, water (`Water`, `CellWaterHeightLocations`, `WaterHeights`, `NAM7` water material) | per worldspace |
| `MapData` | all zero (no usable-dimensions map data like FO4) |
| `LandscapeTextures` | only `TempJemisonWorld` |

Categories (cross-referenced with the planets, `SfInspect planetworlds`):

| Kind | Count | Example | BTD size (cells per side) |
|---|---|---|---|
| **Master worldspace** registered by a planet (`PNDT.MasterWorldspaces`: worldspace + latitude/longitude) | 72 | Jemison -> NewAtlantis (lat 2.2810, lon 0.7111); Mars -> CydoniaCity; Akila -> akilacity; Volii Alpha -> NeonCity; Earth -> 11 `LC14x/15x` worlds | 3 to 14 |
| Planet-content (PCM) overlays, placed procedurally | 351 | `LandingOverlay01`, `OE*World`, `OverlayPOI*` | mostly 3 |
| Overlay without PCM | 7 | `PCMShipLanding01..04` | 3-4 |
| **No overlay component** | 3 | `DefaultWorld` (0 cells), `TempJemisonWorld` (171 cells, Flags 0), `OutpostOverlayTemplate` | 100 |

45 of 1,765 planets register at least one master worldspace; 1,504 planets have a `SurfaceTree` (procedural terrain).

### 1.3 How a worldspace finds its BTD (verified, two independent ways)
1. **Record chain.** `SfInspect form 034763` -> `SurfaceBlock OverlayBlockNewAtlantis`, `ANAM = Data\TERRAIN\NewAtlantis.btd`,
   `NAM1 = OverlayBlock`, `WHGT = -500`. All 1,753 SFBK have an `ANAM` BTD path (`SfInspect sfbk`).
   The same SFBK `ENAM` holds two floats that equal the BTD header height range (akilacity: `0xC3FA0000` = -500,
   `0x447A0000` = 1000; header -500 / 1000), and `DNAM` = cells per side (akilacity 9 = 1152 / 128).
2. **Name.** Every one of the 433 WRLD EditorIDs has `terrain/<editorid>.btd` in the archives (433/433). 374 more
   top-level BTDs have no WRLD in the shipped esm (test worlds removed from the data).

Which one the engine uses is **unresolved** (record path vs name). fo76utils (Fallout 76) uses the name:
`Terrain/<WRLD EDID>.btd` (`src/landdata.cpp` lines 732-762). Experiment 1 sets both so either works, and has a
variant that tests the record path alone.

**Planet registration (verified data, behaviour unresolved):** `JemisonPlanetData.MasterWorldspaces =
[{Worldspace 01251B NewAtlantis, Longitude 0.7111, Latitude 2.2810}]`. This is what places a city on a planet. Whether a
worldspace *must* be registered there to load or render terrain is the main unknown.

### 1.4 BTD format (verified on real files)
Source of the layout: fo76utils `src/btdfile.cpp` (MIT licence, (c) 2021-2025 fo76utils; cloned read-only to
`C:\Modding\research\ext\fo76utils-sf`, commit c52da18). Our Python decoder (scratch `btd.py`) follows it and checks
itself: for `landingoverlay01.btd` (331,069 B) and `akilacity.btd` (3,788,482 B) the last compressed block ends exactly
at the file size, LOD4 equals every 16th LOD0 sample exactly (max difference 0), and the per-cell min/max table equals
the decoded LOD0 per cell with 0.0000 m error.

| Offset | Content (Starfield variant) |
|---|---|
| 0x00 | `BTDB`, u32 version (vanilla: 5 x1,332, 6 x779, 4 x1) |
| 0x08 | f32 height min, f32 height max (metres; see 1.5) |
| 0x10 | u32 samples X, u32 samples Y (= cells x 128; all 2,112 files multiples of 128, 3 non-square) |
| 0x18 | 4 x i32 cell rectangle, **always 0 in Starfield** (2,112/2,112); cells are implied by the size |
| 0x28 | u32 n LTEX, n x u32 LTEX FormIDs |
| ... | per cell: f32 min, f32 max (cells x 8 B) |
| ... | per cell quadrant: 8 bytes of LTEX table indices (cells x 32 B) |
| ... | LOD4 heights, 8 x 8 u16 per cell (uncompressed); LOD4 land-texture weights, same size |
| ... | zlib block tables (offset, size) for LOD3 (8x8-cell groups), LOD2 (4x4), LOD1 (2x2), LOD0 (1 cell) |
| ... | zlib blocks: each 65,536 B = 128 x 128 u16 heights + 128 x 128 u16 land-texture weights (3-bit alphas, 5 layers) |

No vertex colour and no ground-cover sections in Starfield BTDs (FO76 has them). Header survey of all 2,112 BTDs
(`btd_survey.py`, reads 44 bytes per member): height ranges per file vary: -500/1000 (762 files), -1000/3000 (78),
NewAtlantis 0/260.502, many small custom ranges. **Largest: 100 x 100 cells** (12,800 x 12,800 samples), 108 files, e.g.
`testplayeranimworld.btd` 134 MB, `defaultworld.btd` 4.2 MB (flat compresses well). Compressed size of real terrain:
~45 KB per cell (akilacity 46.8, NewAtlantis 43.4).

### 1.5 Coordinates and height scale
- **Starfield exterior cell = 100 m** (verified: `SfInspect wcells LandingOverlay01`: cell (1,0) refs x 100.0..199.9,
  cell (0,1) y 100.0..199.2). Positions are metres (S4: 1 FO4 unit = 1/70 m, confirmed in game earlier).
- **128 samples per cell -> 0.78125 m spacing** (verified from the format; spacing in metres is supported, see below).
- **Heights are metres, linear:** z = min + raw / 65535 x (max - min) (verified against the per-cell table; the x8 scale
  in fo76utils' Starfield path, marked FIXME there, is **refuted**: median error 754 m against placed objects).
- **World z = BTD height** (supported): `lc001world` (Vectera, Kreet research base) BTD centre is a flat pad at
  111.4 m (80 x 80 samples, p5-p95 109.8-111.9); the base's placed objects cluster at z 112.0-113.5 m (foundations on
  the pad).
- **Grid alignment** (supported): BTD cell i = world cell i - n//2 (n = cells per side; the BTD's SW corner is at
  -(n//2) x 100 m), rows south to north. With bilinear sampling, the share of all placed refs within 0.25 m of the surface
  is 12.3% (akilacity, 50,785 refs) and 7.5% (lc001world, 7,412 refs) for this mapping, against 3.6% / 2.5% with Y
  flipped and lower for 100/127 spacing (`align4.py`). Cities are mostly floors and walls, so a low absolute share is
  expected; the in-game test confirms it.

### 1.6 Cities and landing zones use BTD terrain (verified as data)
NewAtlantis (14 x 14 cells, 0..260.5 m), akilacity (9 x 9), NeonCity (11 x 11, has `NoLandscape` flag), CydoniaCity
(10 x 10) each have their own SFBK + BTD and are registered on their planet. Landing sites (`LandingOverlay01..05`,
`PCMShipLanding01..04`) and POIs are 3 x 3-cell overlay BTDs stamped into procedural planet terrain. NewAtlantis also
has source blocks `NewAtlantisSource` -> `Data\TERRAIN\NewAtlantis\NewAtlantis01.btd` and `NANorthLake01`, so even the
largest city starts from blocks. The 1,300 BTDs in sub-folders (`terrain/hillsrockylarge1k/...`) are the procedural
surface blocks (SFBK with category `NAM1` = the folder theme) used by planet surface trees (`SFTR`); the matching
density maps sit in `textures/terrain/<same folder>` (DensityMaps archive).

## 2. Fallout 4 Commonwealth numbers (verified)
`fo4_land.py` (scratch) reads every `LAND.VHGT` (33 x 33 vertices per cell, heights = (offset + cumulative byte
deltas) x 8 units) from `Fallout4.esm`; grid saved outside the repo (`C:\Modding\research\terrain\fo4\commonwealth_vhgt.npz`).

| Worldspace | LAND | cell range | heights |
|---|---|---|---|
| Commonwealth | 36,864 | x -96..95, y -96..95 (192 x 192) | -8,320..44,872 units = **-118.86..641.03 m** |
| SanctuaryHillsWorld | 118 | x -25..2, y -9..25 | 0..149.83 m |
| DiamondCity | 4 | -1..0 | -30.06..-29.26 m |

Conversion math (verified arithmetic): FO4 cell 4,096 units = 58.514 m; FO4 vertex spacing 128 units = 1.829 m;
Starfield sample spacing 0.781 m (2.34 samples per FO4 vertex). The grids do not line up, so heights are resampled
(bilinear on the FO4 33 x 33 grid) at exact world positions; absolute positions and heights are kept, cell indices
are not (FO4 cell (x, y) covers 0.585 x 0.585 Starfield cells). The full FO4 LAND grid is 11.23 km per side = 113
Starfield cells, a bit over the 100-cell maximum seen in vanilla; the playable core is much smaller (unresolved exact
bounds). Quantisation with min/max = -120/645 m: 1.2 cm per step (FO4's own VHGT step is 8 units = 11.4 cm).

## 3. Community knowledge
(in progress)

## 4. Options
(in progress)

## 5. Experiment 1
(in progress)
