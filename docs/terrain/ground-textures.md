# Ground textures: Fallout 4's ground look on the native Commonwealth terrain

Author: Claude, 2026-10-11. Branch `claude/terrain-ground-textures`, stacked on `claude/terrain-overlay-records`
(PR #64). Starfield 1.16.244. Everything here is offline work; the staged experiments (exp2t0, exp2ta, exp2tb, exp2tc,
exp2t) have **not** run in game.
Labels: **verified** (checked on files, command and number given), **supported** (supported hypothesis), **unresolved**,
**refuted**.

Revision (fix pass after the QA review of PR #70, same day): ground spots are now chosen by one Starfield target each
and checked over the ground the screenshot shows; the experiment is split into five variants that change one thing at
a time; every variant registers the overlay at a site where earlier runs arrived in daylight; claims about the vanilla
LTEX tables, the lighting and the "Mars dirt" look are corrected. Details in sections 2.2, 5 and the research log.

## Short answer
- The exp2b2 terrain (verified in game: FO4 heights at 13 of 14 probes within 0.08 m) was painted with one texture,
  `LDirtFootprints01`, copied from a vanilla template. Its albedo averages `#8F6C58` (reddish brown). Whether that
  albedo alone is the "Mars dirt" look in the screenshots is **unresolved**: every Commonwealth overlay run so far
  arrived at night and the ground shows only in the helmet lamp's circle (section 5.1), so the shots cannot separate
  albedo, lamp colour and a possible planet tint. The control variant exp2t0 shows the same terrain in daylight.
- A BTD's texture sections can carry Fallout 4's ground textures as **vanilla Starfield land textures (option a)**:
  per 50 m quadrant up to 6 LTEX (5 layers with 3-bit alphas + a base) from the BTD's LTEX table, no plugin record.
  What vanilla does is narrower than "any LTEX": all 659 vanilla BTDs with a table carry the six `LDefault*`
  placeholders, the largest table has 18 entries (gameplay worlds: 11) and 20 of the 24 textures our full mapping
  uses appear in no vanilla table (verified, section 2.2). Whether the engine accepts a table without placeholders,
  with more entries or with LTEX no BTD uses is **unresolved**; the five staged variants test one of these at a time.
- Every FO4 land texture (105 LTEX + the default texture) maps to one of 24 vanilla LTEX by category and nearest
  average colour (`src/fo4sf/ground_map.py`; three near-empty ones folded away); the FO4 LAND layers become per-sample
  weights and BTD texture sections (`src/fo4sf/landtex.py`). Heights stay byte-identical to exp2b2.
- **Option b** (new LTEX + materials made from FO4 textures) is designed but not built (section 3.2).
- Staged: `C:\Modding\staging\terrain_exp2t0`, `..._exp2ta`, `..._exp2tb`, `..._exp2tc`, `..._exp2t`; each drops at
  the 14 usual probes and at four ground-type spots (road bed, paved lot, dried grass, eroded dirt) and screenshots
  each. FO4 reference renders of the same spots are in each folder's `reference\`. Run order: exp2t0, exp2ta, exp2t;
  exp2tc and exp2tb only if exp2t differs from exp2ta (section 5.3).

## 1. Fallout 4 terrain texturing (verified on Fallout4.esm)
Read with `fo4land.Plugin.read_world(..., land_textures=True)` and `landtex.parse_land_textures` for the exp2 BTD
footprint (FO4 cells x -24..25, y -24..25, 2,500 LAND).

| Field | Layout | Count in the footprint |
|---|---|---|
| `BTXT` | u32 LTEX, u8 quadrant, u8 unused, i16 layer: base texture of one quadrant | 8,299 (1,701 of 10,000 quadrants have none: default texture) |
| `ATXT` | u32 LTEX, u8 quadrant, u8 unused, u16 layer: header of one alpha layer | 40,199 |
| `VTXT` | n x (u16 position, u16 unused, f32 opacity), position = row x 17 + column in the quadrant, row 0 = south | 40,199 |
| `VCLR` | 33 x 33 x RGB u8, row 0 = south | 1,490 cells: mean 0.996 of white, p5 0.992; the 175 cells of the region of interest (around Red Rocket): mean 0.998, p5 0.996. No visible tint |

- Quadrants 0 = SW, 1 = SE, 2 = NW, 3 = NE, 17 x 17 vertices each, vertex row/column 16 shared (as fo76utils
  `landdata.cpp` reads them). Layers per quadrant: 1: 114, 2: 625, 3: 2,588, 4: 3,406, 5: 2,332, 6: 729, 7: 166,
  8: 28, 9: 3 (quadrants with at least one ATXT).
- Blending (**supported**, fo76utils `renderPixelTES4`): base, then layers in ascending layer number, each drawn over
  what is below with its opacity. `landtex.quadrant_weights` turns that into weights that sum to 1 per vertex.
- LTEX -> `TNAM` texture set (TXST `TX00` diffuse) or the TXST's BGSM (`MNAM`). 105 LTEX records.
- Default texture (**verified**): the Commonwealth WRLD has no default-texture field and no DOBJ entry names one, but
  `Fallout4.exe` (depot 377162) holds the setting defaults side by side: `Ground\CommonwealthDefault01_d.dds` at byte
  46,682,039 right before `sDefaultLandDiffuseTexture:Landscape` (46,682,072), and the same pattern for `_n`
  (`sDefaultLandNormalTexture`) and `_s` (`sDefaultLandSpecularTexture`). The file is
  `textures\Landscape\Ground\CommonwealthDefault01_d.dds` (the path `ground_textures.py` uses; fo76utils' FO4 examples
  pass `-deftxt 0x000AB07E`, `LCWDefault01Grass02`, the LTEX of the same texture set). It is the most common ground in
  the region of interest (22.7 %).
- Grass placement (`LTEX.GNAM`) and FO4's vertex colours are not carried over (Starfield BTDs have no colour
  section, architecture.md 1.4; grass is out of scope).

## 2. Starfield BTD texturing (verified on vanilla files unless marked)
### 2.1 Layout
Per 64 x 64-sample quadrant (50 m) the BTD stores 8 bytes; value v names `table[n - v]`, 0 = empty
(`btd.py`, fo76utils `getCellTextureSet`). Survey of lc172world, newatlantis, akilacity, cydoniacity, lc001world:

- Bytes 0..4 are layer slots; slot k's alpha is bits 3k..3k+2 of the sample's u16 (0..7). Bit 15 is never set; a group
  is never non-zero where its byte is 0.
- Byte 6 is the base (no alpha); bytes 5 and 7 are always 0. "6 layers" = 5 alpha slots + base.
- A quadrant's textures sit in **ascending table index**, filled from slot 0 without gaps; the highest index is the
  bottom (all 1,644 quadrants of the five files).
- With up to 5 textures there is no byte 6: the last slot is the bottom and its alpha is **7 at (nearly) every
  sample**: lc172world (9 such quadrants), lc001world (6) and cydoniacity (22) 100 %, newatlantis (486) 99.97 %;
  akilacity 100 % in its 2 four-texture quadrants and 69 % in its 3 five-texture ones. (exp2b2's template BTD has one
  slot with alpha 0 everywhere and rendered `LDirtFootprints01` in game, so a lone slot is drawn whatever its alpha.)
- So slot 0 is the top layer: an opaque bottom slot only makes sense under the others. Reading model
  (**supported, strong**): from the bottom up, each slot drawn over what is below with alpha / 7 (fo76utils
  `renderPixelFO76*` walks the same order top-down and uses the alpha as a height-blend threshold).
- Round trip (`landtex.decode` -> `landtex.encode`) of those five vanilla BTDs: effective weights identical (mean
  difference 0.0000), quadrant bytes identical in 78-100 % of quadrants (the rest: vanilla lists textures that have
  no visible weight there), and every alpha that differs from vanilla is hidden below an opaque layer (31,290 to
  631,452 per file, 0 visible). Under this reading our writer produces what the Creation Kit wrote.

### 2.2 What vanilla BTDs reference (`ground_textures.py survey`)
- Archives: `Starfield - Terrain01..04.ba2`, `Starfield - TerrainPatch.ba2` and the add-on `SFBGS00D - Main.ba2`
  (Shattered Space): 2,112 BTD files, every entry stored uncompressed. 659 have an LTEX table (Terrain01 546,
  TerrainPatch 5, SFBGS00D 108; Terrain02..04 hold 1,114 files without a table). Top-level `terrain/*.btd` in the
  Starfield archives: 758, of which 551 have a table and 402 also `LDirtFootprints01`.
- **Every one of the 659 tables holds all six placeholders** `LDefault001Solid`, `LDefault002Talus`,
  `LDefault003FlatIn`, `LDefault004FlatOut`, `LDefault005Flow`, `LDefault006Base`. Their positions vary (11 index
  patterns; indices 0..5 in 615 tables; akilacity interleaves them with concrete LTEX), so this is not a fixed-index
  artefact.
- Table sizes over the 2,112 files: 0: 1,453, 6: 256, 7: 341, 8: 37, 9: 20, 11: 1, 12: 1, 17: 1, 18: 2. The largest
  are test worlds (`testmuckworld01`, `testvideo` 18, `testice` 17, `testmahelyworld` 12, which also holds five null
  FormIDs and one that is no LTEX); the largest gameplay table is `akilacity` with 11 (6 placeholders,
  `LDirtFootprints01`, 4 concrete LTEX).
- Concrete LTEX in vanilla tables (always next to the placeholders): akilacity (`LDirtMudPacked01_DarkBrown`,
  `LDirtMudPacked02_DarkBrown`, `LDirtPacked04_Brown`, `LRiverRocks01_NoGroundCover`), `sb016templeworld`
  (`LGrassAridSparse01_Dead`), `sb013templeworld` (`LLooseRocksForest01`), `overlaytraitprimordialnetworksm01`
  (`LDirtForestPacked01`), overlay-trait worlds (`LMossForest01_Yellow`, `LSandPacked03_Sulfur`, `LIceCracked01`,
  ...), `rl003world` (`LScrapPile01`), 50 distinct in all. Shattered Space's 108 tables hold only the six placeholders
  and use one quadrant pattern `(6,5,4,3,2,0,1,0)`.
- BIOM terrain data names land textures in `LNAM` (2,943) and `ANAM` (2,059) fields: 5,002 entries, 335 distinct
  LTEX. xEdit's mask-role enum: 0 Base, 1 Solid, 2 FlatOuter, 3 FlatInner, 4 Talus, 5 Flow, 6 Path. No BIOM references
  the six `LDefault*` records, and `LDirtFootprints01` is the Path texture in 211 BIOM entries. So the placeholders
  stand for "this biome's Solid / Talus / ... texture" and an overlay painted with them takes the planet's look
  (**supported**: names and usage, not tested).
- The textures our full mapping uses (24 after folding, section 3.1; 27 before): 20 appear in no vanilla BTD table
  (22 of the earlier 27), 5 in no BIOM, and 2 in neither: `LGravelRoad01` and `LDebrisPile01`.
- Consequence: "a BTD table may name any `Starfield.esm` LTEX" was **overstated** in the first version of this doc.
  What vanilla shows is concrete LTEX next to the six placeholders in tables of at most 18 (gameplay 11) entries.
  A table without placeholders, a larger table and LTEX no vanilla table uses are three separate departures, each
  **unresolved**; section 5 stages one variant per departure.
- Concrete LTEX render as themselves (**supported**: designers would not mix them with placeholders otherwise;
  exp2b's `LDirtFootprints01` showed its own footprint pattern in game, under the helmet lamp at night).
- LTEX record: `BNAM` material file (`Materials\Terrain\<name>.mat`), `MNAM` material type, `HNAM` friction /
  restitution, `QNAM`. 416 records. The CK sources (`Tools\ContentResources.zip`) hold 394
  `Materials/Terrain/*.mat`: shader model `Terrain1Layer`, a `TerrainSettingsComponent` (`TilingDistance` in 220 of
  the 416 LTEX's materials, `BlendSoftness`, displacement) and color / normal / rough / ao / height textures. The
  materials of all 27 LTEX of the first exp2t table and of the 4 that only ta uses occur by name in the run-time
  `materials/materialsbeta.cdb` (`Starfield - Materials.ba2`; 5 to 268 hits each).

## 3. Mapping decision
### 3.1 Option a: vanilla Starfield LTEX (chosen, built)
`src/fo4sf/ground_map.py`:
1. Each FO4 LTEX gets a category by hand: grass, lawn, paved, gravel, dirt, forest, mud, sand, debris.
2. Each category lists Earth-like vanilla LTEX (no `_Red` / `_Mars` / `_Volcanic` / `_Purple` / glow variants).
3. Average albedo of every FO4 diffuse and every Starfield albedo (low mips only, averaged in linear light;
   `ground_textures.py palette`), CIE76 colour difference; the nearest candidate of the category wins
   (`ground_textures.py suggest`, which also checks every FormID, mapped and placeholder, against `Starfield.esm`:
   0 mismatches).
4. Reviewed by eye on previews; 4 changes, each with its reason in `REVIEWED`: `LDirtGravel01` and
   `LDirtGravel01Grass` keep the same-named `LDirtGravel01` (the Red Rocket lot's gravel), `LMuddyLeaves01Wet` takes
   the brown leaf litter instead of tropical leaves, `LQuaryMarble01` a neutral grey instead of a pink-cast rock.
   Wet coast sand is categorised as mud (dark), not sand. `NOTES` records one nearest-colour choice that is not the
   obvious name: `LAsphalt01` -> `LGravelDecorative01` (dE 7.0) although the paved list holds vanilla
   `LGravelAsphaltRoad01` (`001235C0`), the semantic match, because that albedo averages (47, 46, 45) against FO4
   Asphalt01's (115, 111, 100): FO4's lots are sun-bleached light grey.
5. At build time an LTEX with less than 0.05 % of the BTD's weight is folded into the kept LTEX nearest in colour
   (`fold_rare`): `LDirtForestPacked01` -> `LDirtForestRoots02`, `LDirtPacked08_GrayRocks` -> `LLooseRocksSharp01`,
   `LMossForest01` -> `LMossDebris02`. The full mapping's table has 24 entries (27 before).

Around Red Rocket (the 14 x 14 FO4 cells x -24..-11, y 12..25 that cover exp2's region of interest, x -1353..-636 m,
y 753..1470 m; 35 FO4 land textures), share of FO4 texture weight:

| FO4 land texture | share | category | Starfield LTEX | dE | nearest if different (dE) |
|---|---|---|---|---|---|
| (FO4 default) | 22.7 % | dirt | LDirtPacked09_Brown | 5.7 | |
| LDriedGrass01 | 13.2 % | grass | LGrassDeadWet01 | 5.3 | |
| LRubbleRock01 | 13.1 % | gravel | LGravelRoad01 | 2.3 | |
| LForestFloor01 | 11.0 % | forest | LDirtForestPacked01_Dark | 4.6 | |
| LDirtGravel01 | 8.4 % | gravel | LDirtGravel01 | 7.8 | LLooseRocksForest01_DarkGray (3.6) |
| LRootsEroded01 | 7.1 % | dirt | LDirtPacked04 | 4.2 | |
| LFallenLeaves01 | 4.3 % | forest | LDirtForestRoots02 | 1.6 | |
| LDriedGrass01NoGrass | 3.6 % | grass | LGrassDeadWet01 | 5.3 | |
| LRiverbedSilt01 / Wet | 5.7 % | mud | LDirtMudPacked01_Brown | 3.0 / 2.5 | |
| LRubbleRock01Grass | 1.8 % | gravel | LGravelRoad01 | 2.3 | |
| LDriedGrass02Weeds | 1.4 % | grass | LGrassDeadWet01 | 5.3 | |
| LRiverbedRocks02Wet (+Grass) | 1.6 % | gravel | LGravelRoad01 | 4.5 | |
| LBlastedForestGrass01_NoGrass | 1.1 % | grass | LGrassDeadWet02 | 15.3 | |
| LRootsEroded01Grass01 | 0.8 % | dirt | LDirtPacked04 | 4.2 | |
| LQuaryMarble01 | 0.8 % | paved | LDirtPacked05_Gray | 8.1 | LRockCracked01 (7.0) |
| LMuddyLeaves01Wet | 0.6 % | forest | LDirtForestRoots02 | 7.6 | LLeavesTropical01 (2.9) |
| LAsphalt01 | 0.5 % | paved | LGravelDecorative01 | 7.0 | (LGravelAsphaltRoad01 by name, see 4. above) |
| LCrackedMud01 | 0.5 % | dirt | LDirtPacked10 | 3.0 | |
| 15 others | 1.8 % | | | | |

FO4 paints its roads' beds `LRubbleRock01` (the grey bands in the reference render) and puts asphalt road meshes on
top; `LAsphalt01` is painted on paved lots (the Red Rocket forecourt, parking areas). exp2t has no statics, so the
terrain under them is what shows.

Folded variants (section 5): `FOLD["ta"]` maps every category onto four LTEX that vanilla gameplay tables carry
(grass, lawn -> `LGrassAridSparse01_Dead`; gravel, paved, debris -> `LLooseRocksForest01`; dirt, mud, sand ->
`LDirtPacked04_Brown`; forest -> `LDirtForestPacked01`); `FOLD["tb"]` onto four of the full mapping that no vanilla
table carries but BIOMs name (`LGrassDeadWet01`, `LGravelDecorative01`, `LDirtPacked04`, `LDirtForestPacked01_Dark`).

### 3.2 Option b: new terrain materials from FO4 textures (not built)
- Possible pieces: an LTEX record (`EDID`, `BNAM`, `MNAM`, `HNAM`, `QNAM`), a `.mat` cloned from a vanilla
  `Terrain1Layer` material (as `convert_material.py` clones mesh materials), FO4 `_d/_n/_s` converted to
  color/normal/rough (`textures.py`), ao and height from replacement values.
- Against it: none of the 8 official add-on plugins (Shattered Space included) has an LTEX record (verified: no LTEX
  group), so there is no precedent for plugin-added terrain materials; a BTD's LTEX table stores raw FormIDs with no
  master list, so a plugin LTEX would have to be written with its run-time load-order byte (02 in the 2026-10-11
  runs) or be remapped by the engine (**unresolved**); terrain blending uses the material's height texture, which FO4
  does not have.
- For it: loose `.mat` files in a plugin's `- Main.ba2` work for meshes (S3, verified in game).
- Safest test: override one of the 56 vanilla LTEX that no BIOM, WRLD or surveyed BTD references (for example
  `LDirtSandDunesA` 0000128C, which has no material at all) to point at an FO4 material, and use that FormID in one
  patch of the BTD. If it renders FO4's texture, option b is open for the textures where no vanilla match is close.

## 4. Writer (src/fo4sf/landtex.py, scripts/terrain/ground_textures.py)
1. FO4 weights per vertex (over-compositing per quadrant, shared quadrant and cell borders averaged), mapped to
   Starfield keys while they are added (`WeightGrid`).
2. LTEX table: for variants with the template, exp2b2's 7 entries first (placeholders at indices 0..5, as in 615 of
   659 vanilla tables, then `LDirtFootprints01`), never referenced by a quadrant; then the textures rarest first, most
   common last (vanilla puts the base texture last).
3. Bilinear resampling onto the BTD samples, one 64-row band at a time; per quadrant the 6 textures with the largest
   summed weight, the rest renormalised onto them.
4. Alphas from the top: slot j's exact alpha is w_j / (what is left); of the 2^5 round-down/round-up choices the one
   with the smallest summed weight error per sample is kept. Same input (full mapping, variant t),
   `--alpha-rounding plain` against the default search: mean weight error 0.0306 -> 0.0289, dominant texture kept at
   99.04 % -> 99.25 % of samples. (The first version quoted 0.0302 / 99.05 % -> 0.0286 / 99.27 % from an input before
   the wet-sand remap; those cannot be reproduced from this code.)
5. `btd.write` with exp2b2's heights; `btd.height_digest` compares header, cell min/max, LOD4 heights and every
   block's height half (SHA-256): identical in every variant.

| Variant | Table | BTD bytes | Mean weight error | Dominant texture kept | Dropped by the 6-texture limit | Quadrants by texture count (1..6) |
|---|---|---|---|---|---|---|
| t | 24 | 38,427,280 | 0.0289 | 99.25 % | 0.11 % | 0, 10, 330, 962, 960, 1,102 |
| tc | 31 (7 + 24) | 38,427,308 | 0.0289 | 99.25 % | 0.11 % | as t |
| ta, tb | 11 (7 + 4) | 34,910,506 | 0.0217 | 99.63 % | 0 | 17, 830, 1,498, 1,019, 0, 0 |
| t0 | 7 (exp2b2's) | 27,612,888 | (exp2b2's BTD byte for byte) | | | |

29 x 29 cells, 13,778,944 samples; vanilla for comparison: akilacity 46.8 KB per cell, NewAtlantis 43.4 (t: 45.7).

## 5. Staged: five variants (not deployed)
`python scripts/terrain/ground_textures.py build --from C:\Modding\staging\terrain_exp2b2 --out
C:\Modding\staging\terrain_exp2t --palette C:\Modding\research\terrain\ground\palette.json` builds all five into
`terrain_exp2t` + suffix; `check` with the same arguments re-reads them (all PASS).

| Variant (folder) | LTEX table | Against | It changes |
|---|---|---|---|
| t0 (`terrain_exp2t0`) | exp2b2's: 6 placeholders + `LDirtFootprints01`, used everywhere | exp2b2 | only the site (daylight); control |
| ta (`terrain_exp2ta`) | exp2b2's 7 + 4 LTEX that vanilla gameplay tables carry (11, akilacity's size) | t0 | FO4 layers painted with concrete LTEX in a vanilla-shaped table |
| tb (`terrain_exp2tb`) | exp2b2's 7 + 4 LTEX that no vanilla table carries, all named by BIOMs (11) | ta | LTEX never used in a BTD |
| tc (`terrain_exp2tc`) | exp2b2's 7 + the full mapping (31) | tb | table size beyond any vanilla table, the full set of mapped LTEX |
| t (`terrain_exp2t`) | the full mapping only (24) | tc | no placeholders |

Each folder:

| File | Content |
|---|---|
| `FO4TerrainExp2.esm`, `exp2_params.json`, `Data\textures\terrain\overlaymasks\fo4cw_commonwealth.dds` | exp2b2's, unchanged |
| `FO4TerrainExp2_Mars.esm` | exp2b2's with the worldspace's PNDT `CNAM` entry moved to the daylight site (5.1); in the record's field data only those 16 bytes differ (the record is zlib-compressed and is recompressed), checked by `check` |
| `Data\Terrain\FO4CW_Commonwealth.btd`, `Data\meshes\terrain\FO4CW_Commonwealth.btd` | the variant's BTD (both places, as exp2b2) |
| `plan.json` | exp2b2's test (coc `FO4CW_RedRocketSpawn`, spawn_local, z_ref `flat_1`, drop_z 150) + 4 ground spots, `"fresh": true` |
| `expected.json` | exp2b2's + variant, site, LTEX table, encode statistics, height digest, mapping, spots with FO4 and decoded shares |
| `reference\compare_spots.png` | per spot 40 x 40 m top-down, FO4 layers (left) vs the decoded BTD (right), textures tiled at their material's `TilingDistance` (else 2.5 m; palette rebuilt so the tiling is read) (not for t0) |
| `reference\compare_overview.png` | region of interest, 1 m/px, average colours, hill-shaded; also `fo4_overview*.png`, `sf_overview.png` |
| `README.txt` | what the variant changes, install, queue command, spot list with shares |
| `offline_check_textures.json` | written by `check`: PASS and the source BTD's height digest |

Packing (verified offline on the first exp2t): Archive2 `-format=General -compression=None` (what
`exp_install.py --pack` runs) stores all three Data files uncompressed and byte-identical.

### 5.1 Lighting and the site
- Every Commonwealth overlay arrival so far was at night (`ground_textures.py lighting`, mean of the top 200 rows of
  `spawn.png`, 0..255): exp2b 19.2 / 10.1, exp2b2 19.9 / 8.0, exp2b3 6.4 / 17.2, exp2c 11.2, 10.0, 9.9, 11.2. The
  probe shots show the ground only in the helmet lamp's circle. The runner relaunches from the same save
  (`fo4sf_test_2470f876`) and has no time-of-day control (verified: no game-hour or set-time command in
  `testqueue.py` or `qstep.ps1`, and the plan format cannot carry one).
- From the same save, runs registered at another longitude arrived in daylight: exp1_mars 105.8 / 130.7, exp1d
  131.0 (its other attempt fell into a pit below the overlay: sky 7.3, probes in daylight), exp3 103.0. The raw PNDT
  `CNAM` pairs (latitude, longitude in radians; commonwealth-scale.md): exp2b..exp2c (0.3, -1.2), exp1 (0.2, 1.2),
  exp3 (0.2008..0.2012, 1.1989..1.1993). exp1d's daylight arrival (16:15) and exp2b's night arrival (16:27) were 12
  minutes apart. **Supported**: the local time follows the registration longitude (2.4 rad apart = about 9 h of a
  24.6 h Mars day); nothing else differs that would explain day against night.
- So every variant registers the overlay at exp1's site, raw (0.2, 1.2), instead of exp2b2's (0.3, -1.2). The
  worldspace then merges at another offset; the runner measures it from the arrival (spawn_local), as before. Under
  Absolute alignment exp3 at that longitude read a Z offset of 0. Risks: the site has another biome and procedural
  surroundings (only the overlay's edge blend shows them); a new runner save (another `FO4Port.esm` build) would
  start at another time.
- After a run, `python scripts/terrain/ground_textures.py lighting --run C:\Modding\testqueue\terrain_exp2t0 ...`
  classifies each attempt from the spawn sky and the probe shots' top corners (away from the lamp): night at
  longitude -1.2 read sky 6.4..19.9 and corners 6.7..37.0, daylight read sky 103..131 and corners 51.1..154.4
  (thresholds 30 / 60 and 40 / 45; a heuristic). Colour and tint are judged only on daylight attempts.
- Alternative not built: a game-hour step in the runner (e.g. `set gamehour to 12` before the probes); whether that
  moves the sun on a planet is **unresolved**.

### 5.2 Ground spots
Chosen from the full mapping (variant t) and the same in every variant. Each spot has one Starfield target; the FO4
textures that map to it cover the vertex's neighbourhood (pre-filter), and on the decoded BTD the target holds at least
90 % of the ground the probe screenshot looks at and of a 6 m disk around the spot. The runner's terrain step
screenshots each probe looking north, pitched 15 degrees down, the eye about 1.7 m up: the middle of the picture is
the ground 2..7 m north (view window: 6 m wide, 2..7 m north). Also: slope <= 10 degrees, decoded height = FO4 height
/ 70 within 0.05 m under every interpolation rule, 8 m from the other probes, nearest to Red Rocket.

| Probe | Screenshot | x, y (m) | expect (m) | FO4 over the view window | t: decoded view / disk | ta | tb |
|---|---|---|---|---|---|---|---|
| ground_road | pt14 | -1034.9714, 1086.1714 | 109.7143 | RubbleRock01 94.5 %, default 5.5 % | `LGravelRoad01` 94 % / 100 % | `LLooseRocksForest01` 94 % | `LGravelDecorative01` 94 % |
| ground_lot | pt15 | -826.5143, 1049.6 | 88.2286 | Asphalt01 89.2 %, default 7.8 %, debris 3 % | `LGravelDecorative01` 91 % / 95 % | `LLooseRocksForest01` 94 % | `LGravelDecorative01` 94 % |
| ground_grass | pt16 | -863.0857, 978.2857 | 85.8286 | DriedGrass01NoGrass 51.6 %, DriedGrass01 44.5 %, DirtGravel01 3.2 % | `LGrassDeadWet01` 96 % / 99 % | `LGrassAridSparse01_Dead` 96 % | `LGrassDeadWet01` 96 % |
| ground_dirt | pt17 | -797.2571, 981.9429 | 86.8571 | RootsEroded01 87.4 %, default 12.6 % | `LDirtPacked04` 93 % / 98 % | `LDirtPacked04_Brown` 100 % | `LDirtPacked04` 100 % |

In t0 every spot is `LDirtFootprints01`. Correction: the first exp2t chose spots by the purity of a *union* of FO4
textures and checked one sample. Its `ground_dirt` (-1144.6857, 1034.9714) was a single `LDirtPath01` vertex in
mostly `LRootsEroded01`, which map to two different LTEX (`LDirtPacked10`, `LDirtPacked04`); the decoded BTD there was
51 / 48 % within 3 m and 24 / 68 % in the window the screenshot shows, so its label `LDirtPath01 -> LDirtPacked10` was
wrong for the picture. Its `ground_lot` had `LGravelDecorative01` at 69 % within 6 m and 49 % in that window. Both
spots moved; `ground_dirt` is now eroded dirt (`LDirtPacked04`), and `check` tests the view window and the disk
instead of the nearest sample.

### 5.3 Run order and reading the result
Queue (from the integration worktree, one test each with a relaunch first; the chain uninstalls between queues):

    python scripts/game/testqueue.py plan-terrain --staging C:\Modding\staging\integ_1011 --exp-dir C:\Modding\staging\terrain_exp2t0 --out C:\Modding\testqueue\terrain_exp2t0 --plugins FO4TerrainExp2.esm,FO4TerrainExp2_Mars.esm --fresh
    python scripts/game/testqueue.py plan-terrain --staging C:\Modding\staging\integ_1011 --exp-dir C:\Modding\staging\terrain_exp2ta --out C:\Modding\testqueue\terrain_exp2ta --plugins FO4TerrainExp2.esm,FO4TerrainExp2_Mars.esm --fresh
    python scripts/game/testqueue.py plan-terrain --staging C:\Modding\staging\integ_1011 --exp-dir C:\Modding\staging\terrain_exp2t --out C:\Modding\testqueue\terrain_exp2t --plugins FO4TerrainExp2.esm,FO4TerrainExp2_Mars.esm --fresh
    python scripts/game/testqueue.py plan-terrain --staging C:\Modding\staging\integ_1011 --exp-dir C:\Modding\staging\terrain_exp2tc --out C:\Modding\testqueue\terrain_exp2tc --plugins FO4TerrainExp2.esm,FO4TerrainExp2_Mars.esm --fresh
    python scripts/game/testqueue.py plan-terrain --staging C:\Modding\staging\integ_1011 --exp-dir C:\Modding\staging\terrain_exp2tb --out C:\Modding\testqueue\terrain_exp2tb --plugins FO4TerrainExp2.esm,FO4TerrainExp2_Mars.esm --fresh

A dry run of each into a scratch folder accepted the plan: test `0000_terrain_FO4CW_RedRocketSpawn`, `fresh` true,
18 points, `z_ref` `flat_1`, drop_z 150, save `fo4sf_test_2470f876`, `exp_install.py ... --pack` as pre-launch step.
Never install two FO4TerrainExp2 experiments together (exp2c uses the same plugin names; the installer refuses).

First `lighting --run` on each finished queue: only daylight attempts answer colour questions. Then:

| Observation | Meaning |
|---|---|
| t0: heights as exp2b2 (14 probes; the 4 spots within 0.5 m) | the new site merges and aligns as the old one |
| t0: no arrival / flat heights | the site change broke the merge: judge nothing else; rerun the variants with `--site source` (night) |
| t0 in daylight: footprint dirt with the colour of `LDirtFootprints01`'s albedo | the "Mars dirt" look is the texture itself (no tint) |
| t0 in daylight: clearly redder or bluer than that albedo, like the procedural ground around | the planet tints or relights terrain materials; compare the same spots in ta |
| ta: spots show rocks / dry grass / brown dirt / forest dirt, matching `reference\compare_spots.png` | concrete LTEX painted from FO4 layers work in a vanilla-shaped table |
| ta: still footprint dirt everywhere | the texture sections are ignored or replaced; compare with a vanilla overlay |
| t as ta (its own textures) | none of the three departures matters: the full mapping works; tc and tb are not needed |
| t black, checkered, biome-coloured or unchanged while ta works | run tc: tc as ta -> the missing placeholders broke t; tc as t -> run tb: tb as ta -> table size or the full LTEX set (tc); tb as t -> LTEX never used in a BTD |
| one spot black or checkered in t / tc only | a material failed to load there: most likely `LGravelRoad01` (ground_road) or `LDebrisPile01`, the two that no BIOM and no vanilla BTD names |
| Hard edges every 50 m | the 6-texture-per-quadrant limit or slot order is read differently in game |

Notes: the runner's automatic verdict covers heights only. In exp2b3 the `resampled_sw` probe was classed MOVED (it
ended 141.9 m away), so the automatic verdict is likely INCONCLUSIVE whatever the textures do; the texture result is
judged by a person on pt14-pt17 and `spawn.png`. The runner's `beyond` point defaults to the first point's x + 500 m
(-489.26, 1146.51), which lies inside the 29-cell BTD (-1400..1500 m) and is teleported to without the merge offset
(inherited from exp2b2, not specific to this experiment).

## 6. Unknowns
1. Whether concrete LTEX render as themselves in a plugin's BTD on Mars (ta), whether the planet tints them (t0 / ta
   in daylight), and which of the three table departures the engine minds (t, tc, tb).
2. Whether the registration longitude sets the local time as the earlier runs suggest (5.1); `lighting` checks it.
3. The engine's exact blend (over-compositing vs height-blend thresholds); our reading reproduces vanilla data
   exactly but is not observed in game.
4. Option b: plugin-added terrain materials and plugin LTEX FormIDs in a BTD table.
5. FO4 texture scale: the renders tile FO4 textures 16 times per FO4 cell at 1,024 px (fo76utils' "16384 / 2^mip
   texels per cell" hint) and Starfield textures every `TilingDistance` metres (assumed to be metres); illustrative.
6. Grass and vertex colours (white here) are not carried over.

## Reproduce

    python scripts/terrain/ground_textures.py palette --out C:\Modding\research\terrain\ground\palette.json
    python scripts/terrain/ground_textures.py suggest --palette C:\Modding\research\terrain\ground\palette.json
    python scripts/terrain/ground_textures.py survey --out C:\Modding\research\terrain\ground\btd_survey.json
    python scripts/terrain/ground_textures.py build --from C:\Modding\staging\terrain_exp2b2 --out C:\Modding\staging\terrain_exp2t --palette C:\Modding\research\terrain\ground\palette.json --replace
    python scripts/terrain/ground_textures.py check --from C:\Modding\staging\terrain_exp2b2 --out C:\Modding\staging\terrain_exp2t
    python scripts/terrain/ground_textures.py build --from C:\Modding\staging\terrain_exp2b2 --out <scratch> --variants t --site source --alpha-rounding plain
    python scripts/terrain/ground_textures.py lighting --run C:\Modding\testqueue\terrain_exp2b2 C:\Modding\testqueue\terrain_exp3
    python -m unittest tests.test_landtex

Defaults: `--fo4-data` the FO4 depot `Data`, `--sf-data` Starfield `Data`, `--content-resources` the Creation Kit's
`Tools\ContentResources.zip` (read-only). The quadrant-layout statistics, the vanilla round trip and the material
database name search were scratch scripts; their outputs are summarised above. The VCLR figures and the
`Fallout4.exe` strings were read with short scratch scripts (numbers above).
