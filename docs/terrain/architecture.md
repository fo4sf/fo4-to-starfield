# Starfield terrain architecture for the Commonwealth (S5 / WP-12)

Author: Claude, 2026-10-11. Branch `claude/terrain-architecture`. Status: **offline research done; the first in-game
runs (2026-10-11) refute or qualify several claims below, see [In-game results](#in-game-results-2026-10-11)**.

Labels used below: **verified** = measured here, command and number given; **supported** = supported hypothesis
(evidence points one way, not proven in game); **unresolved** = not known yet; **refuted** = contradicted by a
measurement. Community claims from the web are marked **unverified** unless we measured the same thing. The offline
sections were written before any terrain test in game; where the in-game runs contradict them, the text now says so
in place. A terrain research handoff the owner mentioned could not be found.

Goal (owner): a faithful conversion with the Commonwealth as the main authored location, exact geography (no
procedural replacement, no Earth overhaul as the final design). An engine-required planet registration is fine if it
stays behind the scenes. Prefer native terrain; static-mesh terrain only if the evidence forces it.

## In-game results (2026-10-11)
Unattended runner (PR #59) on Starfield 1.16.244. Evidence per run: `C:\Modding\testqueue\<queue>\tests\...\obs.json`
plus screenshots (outside the repo). Experiment 1 itself is described in section 5.

| Finding | Status | Evidence (queue) |
|---|---|---|
| Loose files are disabled on this install: `Starfield.ini` has `sResourceDataDirsFinal=STRINGS\` and there is no `StarfieldCustom.ini`. Every loose-BTD run had no readable BTD. Terrain must ship in `<plugin> - Main.ba2`. | verified | `terrain_exp1` |
| A worldspace's own BTD only applies to an overlay **activated** on a planet (PNDT `CNAM`). Unregistered plugin worldspaces load and show procedural planet ground: World01 and World02 read identical heights, 4.18 / 11.86 / 15.98 m at ground / pad A / pad B (BTDs: 10 / 35 / 22.5 m for World01, 10 / 45 / 27.5 m for World02), loose and packed. | verified | `terrain_exp1`, `terrain_exp1b` |
| Activation merges the overlay's cells into the planet worldspace at a whole-cell XY offset plus a Z offset: World01 on Mars +3000 / -3500 m; exp2b -1200 / -2700 m; vanilla LC172World -500 / -2300 m, Z -3.62 m (read from its persistent COC marker `0010238E`). | verified | `terrain_exp1_mars`, `terrain_exp2b`, `terrain_A2_lc172` |
| "BTD height = world z" (section 1.5) holds only relative to the overlay's Z offset. Anchor-relative probes on vanilla LC172World matched its BTD within 0.02 m in the cell the vanilla overlay mask marks authored, 0.3-0.36 m next to it, and were 4-6 m off in mask-255 border cells. So the mask (or the outer cell ring; LC172World cannot separate the two) also blends heights with the planet. | absolute form refuted; relative form verified (Relative alignment, `INAM` 0); Absolute alignment unresolved | `terrain_A2_lc172` |
| Every registered run with the BTD in our plugin BA2 was flat at exactly the BTD's raw-0 height: exp2b -116.00 m at all 14 probes (= `ENAM` minimum), exp1d -500.00 m at the arrival. | verified (observation) | `terrain_exp2b`, `terrain_exp2b2`, `terrain_exp1d` |
| Cause of the flat result: the BTD was zlib-compressed inside our BA2 (Archive2 default), while all 2,112 vanilla BTDs are stored uncompressed. `exp_install.py` now packs with `-compression=None` (branch `claude/test-queue`). Rerun pending. | supported hypothesis | offline comparison; journal on `claude/test-queue` |
| A worldspace without the overlay component (World03) hangs on the loading screen (black screen and spinner for more than 150 s), with a loose BTD and with the BTD in an archive. | verified (twice) | `terrain_exp1`, `terrain_C_w03` |
| Our persistent `XMarker` anchors read back their **unmerged** local position (exp1d 50 50 10; exp2b -989.03 1147.20 105.14), unlike vanilla's COC marker in LC172World; the runner falls back to the arrival point to measure the offset. | verified | `terrain_exp1d`, `terrain_exp2b` |
| Console: `coc <exterior cell EditorID>` works (`LC172Ext01`, `LC001Outpost`); `cow`, `coc <worldspace>` and `player.moveto <non-persistent ref>` do not. | verified | `terrain_ctrl*`, `terrain_A_ctrl`, `terrain_A2_lc172` |

Size, from the QA review of this PR (raw walk of Starfield.esm, offline): no 100 x 100-cell BTD is behind any WRLD
overlay component. The largest overlay BTDs are **14 x 14** cells (NewAtlantis, SettleWaggonerFarm, both registered);
unregistered PCM overlays are at most 5 x 5. Activated overlays larger than 14 x 14 are untested (exp2b is 29 x 29).

## Short answer

- Starfield has **no `LAND` records** (verified). Terrain heights live in **`.btd` files**, one per worldspace, plus
  procedural "surface blocks" for planets.
- The data binds a worldspace to its BTD by a **record chain** (verified: 430 of 433 WRLD have
  `WorldSpaceOverlayComponent.SurfaceBlock` -> `SFBK.ANAM = "Data\TERRAIN\<EditorID>.btd"`, the other 3 have no overlay
  component) and planets place worldspaces by `PNDT.MasterWorldspaces[]` (latitude/longitude). Every vanilla WRLD
  also has `terrain/<EditorID>.btd` (433/433). In game the BTD is used only for an overlay **activated on a planet**
  (PNDT `CNAM`): an unregistered worldspace shows procedural planet ground, and one without the overlay component hangs
  on load (both **verified**). Record path vs name for an activated overlay is still **unresolved**.
- The BTD format is fully decodable (verified on real files, byte-exact per section and per decompressed block):
  128 height samples per 100 m cell, 16-bit heights mapped linearly between a per-file min and max **in metres**, 5 LOD
  levels, a land-texture (LTEX) table. Vanilla ships BTDs up to **100 x 100 cells (10 km x 10 km)** and with custom
  height ranges, but none of the 100-cell BTDs backs an overlay: the largest overlay BTD is **14 x 14 cells**.
- So a **Commonwealth worldspace with its own BTD (option A)** can carry the exact FO4 heights with ~1 cm
  quantisation, but in game it must be activated on a host planet, as in option B. Still **unresolved**: whether the
  engine uses a plugin's own BTD at all (every registered run so far was flat at the BTD's raw-0 height; supported
  hypothesis: our BA2 stored the BTD compressed, rerun pending) and whether overlays larger than 14 x 14 cells work.

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
| **Master worldspace** registered by a planet (`PNDT.MasterWorldspaces`: worldspace + latitude/longitude) | 72 | Jemison -> NewAtlantis (0.7111, 2.2810); Mars -> CydoniaCity; Akila -> akilacity; Volii Alpha -> NeonCity; Earth -> 11 `LC14x/15x` worlds | 3 to 14 |
| Planet-content (PCM) overlays, placed procedurally | 351 | `LandingOverlay01`, `OE*World`, `OverlayPOI*` | mostly 3 |
| Overlay without PCM | 7 | `PCMShipLanding01..04` | 3-4 |
| **No overlay component** | 3 | `DefaultWorld` (0 cells), `TempJemisonWorld` (171 cells, Flags 0), `OutpostOverlayTemplate` | 100 |

45 of 1,765 planets register at least one master worldspace; 1,504 planets have a `SurfaceTree` (procedural terrain).

### 1.3 How a worldspace finds its BTD (verified, two independent ways)
1. **Record chain.** `SfInspect form 034763` -> `SurfaceBlock OverlayBlockNewAtlantis`, `ANAM = Data\TERRAIN\NewAtlantis.btd`,
   `NAM1 = OverlayBlock`, `WHGT = -500`. All 1,753 SFBK have an `ANAM` BTD path (`SfInspect sfbk`); for all 430 WRLD
   with a surface block, `ANAM` is exactly `Data\TERRAIN\<EditorID>.btd` (cross-check of the two dumps).
   The same SFBK `ENAM` holds two floats that equal the BTD header height range (akilacity: `0xC3FA0000` = -500,
   `0x447A0000` = 1000; header -500 / 1000), and `DNAM` = cells per side (akilacity 9 = 1152 / 128).
2. **Name.** Every one of the 433 WRLD EditorIDs has `terrain/<editorid>.btd` in the archives (433/433). 374 more
   top-level BTDs have no WRLD in the shipped esm (test worlds removed from the data).

Which one the engine uses is **unresolved** (record path vs name). fo76utils (Fallout 76) uses the name:
`Terrain/<WRLD EDID>.btd` (`src/landdata.cpp` lines 732-762). `TempJemisonWorld` (171 cells, 100 x 100-cell BTD) has
no overlay component and no SFBK, so if it loads terrain at all, the name path must exist. Experiment 1 tests record
path + name, record path only, and name only in one session.
**In game (2026-10-11) experiment 1 could not separate them:** unregistered World01 (record + name) and World02
(record only) read identical procedural heights, so neither used its BTD; World03 (name only, no overlay component)
hung on the loading screen, loose and packed (**verified**, section [In-game results](#in-game-results-2026-10-11)).
A plugin worldspace without the overlay component does not load; for an activated overlay, record path vs name is
still **unresolved**.

Field names from xEdit's Starfield definitions (`Core/wbDefinitionsSF1.pas`, TES5Edit `dev-4.1.6` at 9fb0168, MPL-2.0;
one file read, not run; community reverse engineering, so names are **supported**, not verified):
- WRLD overlay component (`BGSWorldSpaceOverlay_Component`): `SNAM` *Star System ID*, `PNAM` *Planet ID*, `BNAM`
  *Surface Block*. Consistent with our data: the Mars worlds CydoniaCity and LC172World have SNAM 0 (Sol), PNAM 4.
- WRLD `DATA` flags: Small World, Can't Fast Travel From Here, No LOD Water, **No Landscape**, No Sky, **Fixed
  Dimensions**, No Grass. WRLD `FNAM` flags: ..., **Allow ProcGen**, Allow Cell Content. Parent worldspace flags: Use
  Land / LOD / Map / Water / Climate Data, Use Sky Cell.
- SFBK: `ANAM` data file, `DNAM` size X/Y (cells), `ENAM` height min/max, `FNAM` "Connections" (our earlier reading,
  8 x i16 border heights for stitching, is **refuted**: all 1,730 vanilla SFBK with an `FNAM` store `DNAM.x` x
  `DNAM.y` u16 values, one per BTD cell, 0 exceptions; in most records each value is the raw BTD height at that cell's
  SW corner, see `docs/terrain/overlay-records.md` on PR #64), `GNAM` rarity, `HNAM`/`INAM` manual alignment value / mode (**Relative / Absolute**), `JNAM` grid
  alignment override (Min / Max / Average / Median / Percent), `KNAM` grid sampling override, `WHGT` water height,
  `NAM2`/`NAM3` cell min/max, `NAM4` height range, `NAM5` source block. NewAtlantis: INAM 1 (Absolute), HNAM -239.
- PNDT: `CNAM` *Master Worldspaces* (latitude, longitude as f64, then the WRLD) and `EOVR` *Edited Worldspaces*
  (same + Added/Removed): a plugin can add a worldspace to a planet without replacing the list (**supported**).
  Note: Mutagen 0.55 names the two doubles the other way round (its "Longitude" is xEdit's first value, range
  -1.32..1.16 = latitude; its "Latitude" ranges -2.93..3.04 = longitude). Tables here print them as (first, second).

**Planet registration (verified data; behaviour verified in game 2026-10-11):** `JemisonPlanetData.MasterWorldspaces =
[(0.7111, 2.2810) -> 01251B NewAtlantis]`. This is what places a city on a planet. A worldspace's own BTD only
applies when the worldspace is activated this way: an unregistered plugin worldspace loads but shows the planet's
procedural ground (**verified**, exp1/exp1b). Activation merges the overlay's cells into the planet worldspace at a
whole-cell XY offset plus a Z offset (**verified**: World01 on Mars +3000 / -3500 m, exp2b -1200 / -2700 m, vanilla
LC172World -500 / -2300 m with Z -3.62 m).

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

LOD1-3 blocks are the full grid sampled every 2nd / 4th / 8th sample from the group's SW corner, partial groups padded
with 0 (verified: max difference 0 for heights and texture weights in akilacity and landingoverlay01). Vanilla blocks
are stored contiguously in table order (LOD3 first), zlib header `78 DA`.
Writer check (`src/fo4sf/btd.py`, re-encoding three vanilla files): all decompressed blocks identical, header, LTEX,
quadrant map and LOD4 byte-identical; only the per-cell min/max floats differ in the last bits (vanilla stores slightly
wider, rounded bounds; ours are the exact bounds of the data). Synthetic round trip: `tests/test_btd.py` (5 tests).
No vertex colour and no ground-cover sections in Starfield BTDs (FO76 has them). Header survey of all 2,112 BTDs
(`btd_survey.py`, reads 44 bytes per member): height ranges per file vary: -500/1000 (762 files), -1000/3000 (78),
NewAtlantis 0/260.502, many small custom ranges. **Largest: 100 x 100 cells** (12,800 x 12,800 samples), 108 files,
none of them behind a WRLD overlay component (the largest overlay BTD is 14 x 14, QA raw walk), e.g.
`testplayeranimworld.btd` 134 MB, `defaultworld.btd` 4.2 MB (flat compresses well). Compressed size of real terrain:
~45 KB per cell (akilacity 46.8, NewAtlantis 43.4).

### 1.5 Coordinates and height scale
- **Starfield exterior cell = 100 m** (verified: `SfInspect wcells LandingOverlay01`: cell (1,0) refs x 100.0..199.9,
  cell (0,1) y 100.0..199.2). Positions are metres (S4: 1 FO4 unit = 1/70 m, confirmed in game earlier).
- **128 samples per cell -> 0.78125 m spacing** (verified from the format; spacing in metres is supported, see below).
- **Heights are metres, linear:** z = min + raw / 65535 x (max - min) (verified against the per-cell table; the x8 scale
  in fo76utils' Starfield path, marked FIXME there, is **refuted**: median error 754 m against placed objects).
- **World z = BTD height: refuted in this absolute form** (in game, 2026-10-11). An activated overlay is merged into
  the planet worldspace with a Z offset (LC172World: -3.62 m under Relative alignment, `INAM` 0), so the BTD height
  equals world z only relative to that offset. The relative form is **verified** on vanilla LC172World: probes
  measured from the overlay's anchor matched its BTD within 0.02 m in the cell the vanilla overlay mask marks
  authored, 0.3-0.36 m next to it, and 4-6 m off in mask-255 border cells (heights blend with the planet there).
  Under Absolute alignment (`INAM` 1): **unresolved** (exp2b, the test for it, came out flat; see the results table).
  The offline evidence was measured in the overlay's own frame and fits the relative form: `lc001world` (Vectera,
  Kreet research base) BTD centre is a flat pad at 111.4 m (80 x 80 samples, p5-p95 109.8-111.9); the base's placed
  objects cluster at z 112.0-113.5 m (foundations on the pad).
- **Grid alignment** (supported, in the overlay's own frame only; in the planet frame the cells move by the
  whole-cell activation offset): BTD cell i = world cell i - n//2 (n = cells per side; the BTD's SW corner is at
  -(n//2) x 100 m), rows south to north. With bilinear sampling, the share of all placed refs within 0.25 m of the surface
  is 12.3% (akilacity, 50,785 refs) and 7.5% (lc001world, 7,412 refs) for this mapping, against 3.6% / 2.5% with Y
  flipped and lower for 100/127 spacing (`align4.py`). Cities are mostly floors and walls, so a low absolute share is
  expected. Second check: NewAtlantis (14 x 14-cell BTD -> cells -7..6): **130 of the 133** cells that hold placed
  objects lie inside that footprint (`SfInspect wcells NewAtlantis`). Not measured in game yet: at LC172World's
  authored probe `lc172_7` the corner rule, a half-sample shift, a one-sample shift and a Y flip differ by at most
  0.035 m, too little to tell apart; exp2b's slope points are the deciding test.

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
Starfield cells, a bit over the 100-cell maximum seen in vanilla BTDs and about 8x the largest vanilla overlay
(14 cells) per side; the playable core is much smaller (unresolved exact bounds). Quantisation with min/max = -120/645 m: 1.2 cm per step (FO4's own VHGT step is 8 units = 11.4 cm).

## 3. Community knowledge (web, unverified unless stated)
Web access was poor today (Steam guides returned HTTP 429, Nexus 403), so this section is thin.
- Starfield CK concept: *"Worldspaces can be imposed on a planet as an 'Overlay' in the Galaxy View menu, replacing a
  grid section of the terrain in game at particular planetary coordinates"*; a worldspace "includes a textured polygon
  terrain mesh, which can be edited with the Terrain Edit feature"
  ([Starfield Wiki, CK: Cell](https://starfieldwiki.net/wiki/Starfield_Mod:Starfield_Creation_Kit:Cell)). Matches what
  we measured (overlay component + SFBK + BTD, planet registration by coordinates).
- Bethesda's CK release notes (quoted by Nexus, [news 14993](https://www.nexusmods.com/news/14993), page itself
  returned 403): worldspace overlays let modders "create mini-worldspaces which are then stitched into the procedural
  terrain on the surface of one or more planets, instead of creating terrain for an entire planet". **Unverified**
  quote via search snippet.
- The repo's earlier note (docs/RISKS.md, from the
  [CK Info & Help guide](https://steamcommunity.com/sharedfiles/filedetails/?l=english&id=3404834557)) says the CK's
  "New worldspace" is greyed out because a worldspace needs terrain; guides describe a Terrain menu that selects
  "blocks of various types of terrain" for new worldspaces
  ([intro guide for outposts and POIs](https://steamcommunity.com/sharedfiles/filedetails/?id=3385012985), search
  snippet). This fits the SFBK "source block" chain (an overlay starts from a procedural block such as
  `OverlayFieldsFlatSmall04`). **Unverified**: we could not open either guide today.
- No public tool that *writes* Starfield BTDs was found (GitHub code search for `BTDB` and repo search "starfield
  terrain": nothing relevant). fo76utils reads them (render/landscape tools; its Starfield height scale is marked
  FIXME and is wrong by 8x, see 1.5). Our `src/fo4sf/btd.py` writer is new.
- No mod shipping its own large heightmap was found in the searches. **Unresolved**, worth asking the community.

## 4. Options compared
FO4 geometry to keep: absolute positions (FO4 units / 70 = metres, verified S4), absolute heights (-118.9..641.0 m),
the 4,096-unit cell grid (58.5 m). Starfield's grid is 100 m, so cell indices change in every option; positions and
heights do not have to.

**Update 2026-10-11 (in game):** the engine uses a worldspace's BTD only when the worldspace is activated on a planet
(**verified**), so A cannot stand alone: it needs B's registration, and with it B's merge offset, Z offset and border
blending. The rows below are corrected where the in-game runs contradict them.

| | **A. Dedicated worldspace, own BTD** | **B. Overlay on a host planet** | **C. Static mesh terrain tiles** |
|---|---|---|---|
| What it is | WRLD + SFBK + one large BTD with the FO4 heights; entered by load door / fast travel; activated on a host planet (PNDT `CNAM`), which the engine requires (**verified**), so A uses B's mechanism | Same records, but stamped into a planet's procedural terrain like New Atlantis / landing sites, procedural terrain around it | FO4 LAND baked into `.mesh` tiles with Havok collision, placed as STAT refs in a worldspace with a flat BTD (a worldspace without the overlay component hangs on load, **verified**) |
| Records / files | WRLD (overlay component), SFBK (`ANAM`), BTD (writer done) shipped in `<plugin> - Main.ba2` (loose files are not read on this install), LTEX list, Location, Biome/Climate, water heights; PNDT `CNAM`/`EOVR` entry (required) | A + PNDT entry (lat/long), SFBK placement fields (alignment mode, per-cell `FNAM`), planet biome/atmosphere | WRLD with overlay component + SFBK + BTD (`NoLandscape` flag exists, NeonCity uses it), ~37k mesh tiles (or fewer, merged), collision per tile, a terrain material |
| Exact geography | Heights quantised to 1.2 cm (range -120..645 m); resampling a 1.83 m grid onto 0.78 m keeps FO4's surface if we sample FO4's triangles. In game heights are relative to the overlay's Z offset (**verified**), so absolute z needs the same alignment as B | Only with `INAM` Absolute alignment (supported by field name; NewAtlantis uses it; untested in game, exp2b came out flat). Relative alignment shifts heights (LC172World: Z -3.62 m, **verified**) | Yes, FO4's own triangles exactly |
| Size | Vanilla BTDs reach 100 x 100 cells = 10 km (verified), but none backs an overlay: the largest activated overlay is 14 x 14 cells (NewAtlantis, SettleWaggonerFarm). FO4 LAND grid is 11.2 km (113 cells), 8x that per side: **unresolved** | Vanilla overlays are at most 14 x 14 cells (1.4 km, NewAtlantis); the 100-cell BTDs belong to worlds without an overlay component or without a WRLD (test worlds) | No hard limit; memory and draw calls grow with tiles |
| Seams | None inside one heightfield. At the edge, the overlay mask (or the outer cell ring) blends heights with the planet: LC172World's mask-255 border cells were 4-6 m off its BTD (**verified**), so the BTD must reach at least one cell past the authored area | Border blends into procedural terrain (overlay mask / outer ring, as for A) | Tile edges must share vertices exactly (we control that); seams at LOD changes |
| LOD | Built into the BTD (LOD0-4, verified format); object LOD separate | Same | Must build our own (mesh LODs or none) |
| Collision | Expected from BTD heights (no terrain collision files exist in vanilla: Terrain BA2s hold only `.btd`, **supported**) | Same | Havok per tile (S6 work, not done for terrain) |
| Texturing | LTEX table, up to 6 layers per quadrant, 3-bit alphas (coarser than FO4's float alphas); FO4 textures need SF LTEX/material records | Same | One material per tile, layer blending must be baked into textures |
| Navmesh | FO4 NAVM stays valid if heights are kept (FORMAT-GAP: NAVM subrecords match 1.0) | Same | Same, navmesh is independent of how the ground renders |
| Behind-the-scenes registration | Required (**verified**): one PNDT entry on a host planet; how much of that planet (sky, gravity, edges) shows when the BTD covers the playable area is **unresolved** | Required and visible (you are on that planet: sky, gravity, procedural edges) | Same as A (the worldspace still needs an overlay) |
| Main unknowns | Answered: registration is required; loose BTDs are not read on this install. Open: does the engine use a plugin's own BTD at all (registered runs were flat at raw 0; supported hypothesis: compressed BA2 entry)? Overlays above 14 x 14 cells? Absolute alignment? | All of A + how alignment/blending treats a 10 km overlay; ship landing and scanner behaviour | Performance at Commonwealth scale; terrain materials; collision baking |

## Recommendation
**Option A, amended after the first in-game runs (2026-10-11):** one Commonwealth worldspace with its own native
BTD, generated from FO4 `LAND` at exact heights, entered by a transition. The engine only uses that BTD when the
worldspace is activated on a planet (PNDT `CNAM`, **verified**), so A now uses B's registration mechanism: a single
entry on a host planet kept as far behind the scenes as the planet allows, with the BTD covering the playable area
plus at least one extra cell ring for the border blend. C stays for local patches (for example under structures) or
as the fallback if a plugin cannot bring its own BTD.
Not shown yet, and the next gates: that the engine uses a plugin's own BTD at all (every registered run so far was
flat at the BTD's raw-0 height; supported hypothesis: the BTD was stored compressed in our BA2, rerun with stored
BTDs pending); Absolute alignment for exact absolute z; overlays larger than 14 x 14 cells (exp2b is 29 x 29, the
Commonwealth would be ~113).
Why (offline): every piece A needs is either verified offline (format, writer, coordinates, height scale, custom
height ranges; vanilla BTD sizes up to 10 km, but overlays only up to 1.4 km) or answered by short in-game tests; C
needs large new pipelines (terrain collision, LOD, materials) and loses the engine's terrain LOD and texture blending.

Not decided here: LTEX/texture mapping, water (FO4 per-cell water heights vs Starfield's `CellWaterHeightLocations`,
8 entries in NewAtlantis), terrain holes (the BTD layout has no hole mask; whether the Commonwealth needs any is
unresolved), grass. They do not change the choice.

## 5. Experiment 1 (prepared offline; run in game 2026-10-11)
**Question:** does a plugin-defined worldspace load its own BTD, at the heights and positions we compute, and does
it need a planet registration or a record path vs a name?

**Result (unattended runner, `C:\Modding\testqueue\<queue>`):** our BTD was never seen in game yet.

| Queue | Setup | Result |
|---|---|---|
| `terrain_exp1` | loose BTDs, no registration | World01 and World02: identical procedural heights, 4.18 / 11.86 / 15.98 / 10.68 m at ground / pad A / pad B / pit C. World03: hung on the loading screen |
| `terrain_exp1_mars` | loose, World01 registered on Mars | arrival moved to (3050, -3450, -72.8) on a Mars mountainside (merge offset +3000 / -3500 m); the probes, at unshifted x/y, missed the overlay |
| `terrain_exp1b` | BTDs in `FO4TerrainExp1 - Main.ba2` (zlib-compressed), no registration | World01 and World02: the same procedural heights as `terrain_exp1` |
| `terrain_B_w01`, `terrain_exp1c_mars` | packed (compressed), World01 registered | flat: -13.94 m at every probe |
| `terrain_C_w03` | packed, World03 | hung on the loading screen again |
| `terrain_exp1d` | PR #64 record fixes, packed (compressed), registered | arrival at -500.00 m, the BTD's raw-0 height (`ENAM` minimum). The anchor read its unmerged local position (50, 50, 10), so the probes missed the overlay |

Reading: loose BTDs are not read on this install (**verified**); unregistered worlds get procedural planet ground
(**verified**); a world without the overlay component hangs (**verified**); registered worlds with our packed BTD are
flat at its raw-0 height (**verified**), probably because the archive stored the BTD compressed (**supported
hypothesis**; reruns with stored BTDs are queued). The steps and the reading table below are the original plan; the
notes in them say where the game behaved differently.

Built by `dotnet/TerrainExp1` (plugin) and `scripts/terrain/make_exp1_btd.py` (BTDs) into
`C:\Modding\staging\terrain_exp1`:

| File | Bytes | Content |
|---|---|---|
| `FO4TerrainExp1.esm` | 5,961 | master Starfield.esm; WRLD `FO4TX_World01..03` (copies of Mars landing world `LC172World` 02DF8C without its cells/location), SFBK `FO4TX_Block01/02`, 25 empty cells -2..2 each, cell (0,0) EditorID `FO4TX_W0nSpawn` with a COC marker at (50, 50, 12) and a vanilla 8 x 8 m platform (050776) at (90, 50, 10) whose top should be flush with the ground |
| `FO4TerrainExp1_Mars.esm` | 6,516 | optional: overrides `MarsPlanetData` to add `FO4TX_World01` as a master worldspace at (0.2, 1.2) |
| `Data\Terrain\FO4TX_World01.btd` | 298,371 | World01: SFBK `ANAM` points here **and** the name matches |
| `Data\Terrain\FO4TX_Shared02.btd` | 298,379 | World02: reachable **only** through SFBK `ANAM` |
| `Data\Terrain\FO4TX_World03.btd` | 298,382 | World03: no overlay component, reachable **only** by name |
| `expected.json` | 484 | expected heights |

Raw check of the plugin (scratch `espdump.py`): WRLD overlay `BNAM` -> SFBK 0x800 / 0x801, SFBK `ANAM`/`DNAM 5 x 5`/
`ENAM -500..1000`, cells at XCLC -2..2, two REFRs in (0,0); Mars override `CNAM` 220 bytes = 11 entries, last
(0.2, 1.2) -> `FO4TX_World01`.

Heights in every BTD (world metres): ground **10.0**; pad A x 20..40, y 20..40 at **10 + D**; pad B x 60..80,
y 20..40 at **10 + D/2**; pit C x 20..40, y 60..80 at **5.0**; D = 25 / 35 / 45 for World01 / 02 / 03, so the pad
height says which file the engine loaded.

**Steps for the lead** (original plan; game closed to install; nothing here touches saves except what you do in game):
1. Copy `FO4TerrainExp1.esm` to `Starfield\Data`, and the three `.btd` to `Starfield\Data\Terrain\` (create the folder).
   Add `*FO4TerrainExp1.esm` to `Plugins.txt`. Loose files must be enabled as for the converted meshes.
   **Superseded:** loose files are not read on this install (`sResourceDataDirsFinal=STRINGS\`); the BTDs go into
   `FO4TerrainExp1 - Main.ba2` next to the plugin, stored uncompressed (`exp_install.py --pack`, `claude/test-queue`).
2. Start the game, load a test save, open the console: `tgm`.
3. `coc FO4TX_W01Spawn`. Look: is there ground? `player.getpos z` -> expect **10.0** (+-0.1). Screenshot.
4. Pad A: `player.setpos x 30`, `player.setpos y 30`, `player.setpos z 80`, wait to land, `player.getpos z` ->
   **35.0**. Pad B: x 70, y 30 -> **22.5**. Pit C: x 30, y 70 -> **5.0**. Edges: x 39, y 30 -> 35.0 and x 41, y 30 ->
   10.0 (tests XY alignment to +-1 m). Note whether the platform top at x 86..94, y ~50 is flush with the ground.
5. Look past x/y = +-250 m (edge of the BTD): void, flat ground, water, or procedural Mars terrain?
6. `coc FO4TX_W02Spawn` -> pad A **45.0** (record path works). `coc FO4TX_W03Spawn` -> pad A **55.0** (name path works).
   In game `coc FO4TX_W03Spawn` never finished loading (World03 has no overlay component).
7. Only if 3 shows no terrain: add `*FO4TerrainExp1_Mars.esm` after it in `Plugins.txt`, restart, repeat 3-5.
   In game there is always ground; the BTD needs the registration, and the registered world is merged at
   +3000 / -3500 m, so the x/y in steps 3-5 must be shifted by that offset.
8. Uninstall: remove the lines from `Plugins.txt`, delete the plugin files and `FO4TerrainExp1 - Main.ba2`.

**Reading the result**

| Observation | Meaning |
|---|---|
| Ground at 10.0, pads at 35 / 22.5 / 5 | A works without registration; height scale and grid alignment verified (**refuted** premise: without registration the BTD is never used) |
| Pads at the right height but shifted by a constant | alignment origin differs (fix ORIGIN in the generator); in game, expect the whole-cell merge offset and a Z offset |
| Pads at heights scaled by a factor | height mapping differs (fo76utils' x8 or similar) |
| No ground in World01, ground after step 7 | planet registration is required: keep it behind the scenes. In game there was always ground: unregistered = procedural planet terrain (**verified**) |
| World02 has terrain, World03 not (or the reverse) | the engine binds by record (or by name). In game neither used its BTD unregistered, and World03 hung on load |
| No ground anywhere, even with Mars | loose BTD not loaded, or a field we copied matters; next: pack into a BA2, then try overriding a vanilla BTD. In game: registered with a packed BTD, flat at the raw-0 height instead |

## 6. Unknowns (in order)
1. **In game:** does the engine use a plugin's own BTD at all, once the worldspace is activated on a planet? Every
   registered run so far was flat at the BTD's raw-0 height (supported hypothesis: compressed BA2 entry; rerun with
   stored BTDs pending). Everything else waits on this. (Answered 2026-10-11: without a planet entry the BTD is never
   used, **verified**; loose `.btd` files are not read on this install, they must be in a BA2, **verified**.)
2. Record path vs name binding for an activated overlay; Absolute alignment (`INAM` 1) for exact absolute z; where
   exactly the overlay mask or the outer cell ring blends heights with the planet.
3. Activated overlays larger than the largest vanilla one (14 x 14 cells): exp2b is 29 x 29, the full FO4 grid needs
   113 (also above the 100 x 100 maximum of any vanilla BTD).
4. LTEX/material mapping for FO4 land textures; water heights; terrain holes; grass.
5. Meaning of `SNAM`/`PNAM` beyond xEdit's names; the per-cell `FNAM` values and the alignment fields (`FNAM` is not
   "8 connections", see 1.3).

## Reproduce
- `dotnet run --project dotnet/SfInspect -c Release -- <Starfield.esm> wrld | sfbk | planetworlds | wcells <WRLD> [out.tsv] | form <hex>... | form type:Planet <name>` (read-only).
- `python scripts/terrain/make_exp1_btd.py <Starfield Data> C:\Modding\staging\terrain_exp1` and
  `dotnet run --project dotnet/TerrainExp1 -c Release -- <Starfield.esm> C:\Modding\staging\terrain_exp1`.
- `python -m unittest tests.test_btd`.
- Scratch analysis scripts (BTD survey, alignment fits, FO4 LAND reader) are not in the repo; their outputs are in
  `C:\Modding\research\terrain\` (game-derived data, never committed).
