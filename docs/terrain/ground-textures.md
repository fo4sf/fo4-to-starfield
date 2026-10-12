# Ground textures: Fallout 4's ground look on the native Commonwealth terrain

Author: Claude, 2026-10-11. Branch `claude/terrain-ground-textures`, stacked on `claude/terrain-overlay-records`
(PR #64). Starfield 1.16.244. Everything here is offline work; the staged experiment (exp2t) has **not** run in game.
Labels: **verified** (checked on files, command and number given), **supported** (supported hypothesis), **unresolved**,
**refuted**.

## Short answer
- The exp2b2 terrain (verified in game: FO4 heights at 13 of 14 probes within 0.08 m) was painted with one texture,
  `LDirtFootprints01`, copied from a vanilla template. Its albedo averages `#8F6C58` (reddish brown), which is the
  "Mars dirt" look in the in-game screenshots (supported: a planet tint on top is not ruled out).
- A BTD can carry Fallout 4's ground textures with **vanilla Starfield land textures (option a)**: per 50 m quadrant up
  to 6 LTEX (5 layers with 3-bit alphas + a base) from the BTD's LTEX table. The table may name any `Starfield.esm`
  LTEX; vanilla BTDs do this (akilacity, overlay-trait worlds), so no plugin record is needed.
- Every FO4 land texture (105 LTEX + the default texture) is mapped to one of 27 vanilla LTEX by category and nearest
  average colour (`src/fo4sf/ground_map.py`), the FO4 LAND layers are converted into per-sample weights and written
  as BTD texture sections (`src/fo4sf/landtex.py`). The heights stay byte-identical to exp2b2.
- **Option b** (new LTEX + materials made from FO4 textures) is designed but not built: no official plugin adds an
  LTEX, a BTD's LTEX table has no master list (a plugin LTEX would need its run-time load-order byte), and whether
  terrain materials load from a plugin archive is **unresolved**. Section 3.2 gives the safest test.
- Staged: `C:\Modding\staging\terrain_exp2t` (exp2b2 + textured BTD) with a plan that drops at the 14 usual probes
  and at four ground-type spots (road, dried grass, dirt, paved lot) and screenshots each; FO4 reference renders of
  the same spots are in its `reference\` folder.

## 1. Fallout 4 terrain texturing (verified on Fallout4.esm)
Read with `fo4land.Plugin.read_world(..., land_textures=True)` and `landtex.parse_land_textures` for the exp2 BTD
footprint (FO4 cells x -24..25, y -24..25, 2,500 LAND).

| Field | Layout | Count in the footprint |
|---|---|---|
| `BTXT` | u32 LTEX, u8 quadrant, u8 unused, i16 layer: base texture of one quadrant | 8,299 (1,701 of 10,000 quadrants have none: default texture) |
| `ATXT` | u32 LTEX, u8 quadrant, u8 unused, u16 layer: header of one alpha layer | 40,199 |
| `VTXT` | n x (u16 position, u16 unused, f32 opacity), position = row x 17 + column in the quadrant, row 0 = south | 40,199 |
| `VCLR` | 33 x 33 x RGB u8, row 0 = south | 1,490 cells; mean 0.998 of white, p5 0.996: no visible tint here |

- Quadrants 0 = SW, 1 = SE, 2 = NW, 3 = NE, 17 x 17 vertices each, vertex row/column 16 shared (as fo76utils
  `landdata.cpp` reads them). Layers per quadrant: 1: 114, 2: 625, 3: 2,588, 4: 3,406, 5: 2,332, 6: 729, 7: 166,
  8: 28, 9: 3 (quadrants with at least one ATXT).
- Blending (**supported**, fo76utils `renderPixelTES4`): base, then layers in ascending layer number, each drawn over
  what is below with its opacity. `landtex.quadrant_weights` turns that into weights that sum to 1 per vertex.
- LTEX -> `TNAM` texture set (TXST `TX00` diffuse) or the TXST's BGSM (`MNAM`). 105 LTEX records.
- Default texture: the Commonwealth WRLD has no default-texture field and no DOBJ entry names one. Treated as
  `CommonwealthDefault01` (LTEX `LCWDefault01Grass01/02`), **supported**: fo76utils' FO4 render examples pass
  `-deftxt 0x000AB07E` (`LCWDefault01Grass02`). It is the most common ground in the region of interest (22.7 %).
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
  akilacity 100 % in its 2 four-texture quadrants and 69 % in its 3 five-texture ones.
- So slot 0 is the top layer: an opaque bottom slot only makes sense under the others. Reading model
  (**supported, strong**): from the bottom up, each slot drawn over what is below with alpha / 7 (fo76utils
  `renderPixelFO76*` walks the same order top-down and uses the alpha as a height-blend threshold).
- Round trip (`landtex.decode` -> `landtex.encode`) of those five vanilla BTDs: effective weights identical (mean
  difference 0.0000), quadrant bytes identical in 78-100 % of quadrants (the rest: vanilla lists textures that have
  no visible weight there), and every alpha that differs from vanilla is hidden below an opaque layer (31,290 to
  631,452 per file, 0 visible). Under this reading our writer produces what the Creation Kit wrote.

### 2.2 What vanilla BTDs reference
- 546 of 753 surveyed top-level BTDs have an LTEX table; all 546 hold the six placeholders `LDefault001Solid`,
  `LDefault002Talus`, `LDefault003FlatIn`, `LDefault004FlatOut`, `LDefault005Flow`, `LDefault006Base`; 397 add
  `LDirtFootprints01`. Shattered Space: 108 BTD entries (54 under `terrain/`, 54 under `meshes/terrain/`), all with
  only the six placeholders and one quadrant pattern `(6,5,4,3,2,0,1,0)`.
- BIOM terrain data (5,002 entries, 335 distinct LTEX) names textures by mask role; xEdit's enum: 0 Base, 1 Solid,
  2 FlatOuter, 3 FlatInner, 4 Talus, 5 Flow, 6 Path. No BIOM references the six `LDefault*` records, and
  `LDirtFootprints01` is the Path texture in 211 BIOM entries. So the placeholders stand for "this biome's Solid / Talus /
  ... texture" and an overlay painted with them takes the planet's look (**supported**: names and usage, not tested).
- Concrete LTEX in vanilla BTDs (not placeholders): akilacity (`LDirtMudPacked01_DarkBrown`, `LDirtPacked04_Brown`,
  `LRiverRocks01_NoGroundCover`, ...), overlay-trait worlds (`LMossForest01_Yellow`, `LSandPacked03_Sulfur`,
  `LIceCracked01`, ...), `rl003world` (`LScrapPile01`). They render as themselves (**supported**: designers would not
  mix them with placeholders otherwise; exp2b's `LDirtFootprints01` showed its own footprint pattern in game).
- LTEX record: `BNAM` material file (`Materials\Terrain\<name>.mat`), `MNAM` material type, `HNAM` friction /
  restitution, `QNAM`. 416 records. The CK sources (`Tools\ContentResources.zip`) hold 394
  `Materials/Terrain/*.mat`: shader model `Terrain1Layer`, a `TerrainSettingsComponent` (`TilingDistance`,
  `BlendSoftness`, displacement) and color / normal / rough / ao / height textures. The materials of all 27 LTEX in
  the exp2t table occur by name in the run-time `materials/materialsbeta.cdb` (5 to 268 hits each); 2 of them
  (`LGravelRoad01`, `LDebrisPile01`) are used by no BIOM and no surveyed vanilla BTD, so their in-game look is the
  least certain.

## 3. Mapping decision
### 3.1 Option a: vanilla Starfield LTEX (chosen, built)
`src/fo4sf/ground_map.py`:
1. Each FO4 LTEX gets a category by hand: grass, lawn, paved, gravel, dirt, forest, mud, sand, debris.
2. Each category lists Earth-like vanilla LTEX (no `_Red` / `_Mars` / `_Volcanic` / `_Purple` / glow variants).
3. Average albedo of every FO4 diffuse and every Starfield albedo (low mips only, averaged in linear light;
   `ground_textures.py palette`), CIE76 colour difference; the nearest candidate of the category wins
   (`ground_textures.py suggest`, which also checks every FormID against `Starfield.esm`: 0 mismatches).
4. Reviewed by eye on previews; 4 changes, each with its reason in `REVIEWED`: `LDirtGravel01` and
   `LDirtGravel01Grass` keep the same-named `LDirtGravel01` (the Red Rocket lot's gravel), `LMuddyLeaves01Wet` takes
   the brown leaf litter instead of tropical leaves, `LQuaryMarble01` a neutral grey instead of a pink-cast rock.
   Wet coast sand is categorised as mud (dark), not sand.

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
| LAsphalt01 | 0.5 % | paved | LGravelDecorative01 | 7.0 | |
| LCrackedMud01 | 0.5 % | dirt | LDirtPacked10 | 3.0 | |
| 15 others | 1.8 % | | | | |

FO4 paints its roads' beds `LRubbleRock01` (the grey bands in the reference render) and puts asphalt road meshes on
top; `LAsphalt01` is painted on paved lots (the Red Rocket forecourt, parking areas). exp2t has no statics, so the
terrain under them is what shows.

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
2. LTEX table order: rarest first, most common last (vanilla puts the base texture last).
3. Bilinear resampling onto the BTD samples, one 64-row band at a time; per quadrant the 6 textures with the largest
   summed weight, the rest renormalised onto them.
4. Alphas from the top: slot j's exact alpha is w_j / (what is left); of the 2^5 round-down/round-up choices the one
   with the smallest summed weight error per sample is kept. Before this search (plain rounding) the mean error was
   0.0302 and the dominant texture survived at 99.05 % of samples; with it 0.0286 / 99.27 % (same input).
5. `btd.write` with exp2b2's heights; `btd.height_digest` compares header, cell min/max, LOD4 heights and every
   block's height half (SHA-256): identical.

exp2t BTD (29 x 29 cells, 13,778,944 samples): 38,427,525 bytes (exp2b2 27,612,888; 45.7 KB per cell, vanilla
akilacity 46.8, NewAtlantis 43.4). LTEX table 27 entries. Mean weight error (total variation) 0.0289, dominant
texture kept at 99.25 % of samples, weight dropped by the 6-texture limit 0.11 %. Quadrants by texture count:
2: 10, 3: 330, 4: 962, 5: 959, 6: 1,103.

## 5. Staged: terrain_exp2t (not deployed)
`python scripts/terrain/ground_textures.py build --from C:\Modding\staging\terrain_exp2b2 --out
C:\Modding\staging\terrain_exp2t --palette C:\Modding\research\terrain\ground\palette.json`

| File | Content |
|---|---|
| `FO4TerrainExp2.esm`, `FO4TerrainExp2_Mars.esm`, `exp2_params.json`, `Data\textures\terrain\overlaymasks\fo4cw_commonwealth.dds` | exp2b2's, unchanged |
| `Data\Terrain\FO4CW_Commonwealth.btd`, `Data\meshes\terrain\FO4CW_Commonwealth.btd` | the textured BTD (both places, as exp2b2) |
| `plan.json` | exp2b2's test (coc `FO4CW_RedRocketSpawn`, spawn_local, z_ref `flat_1`, drop_z 150) + 4 ground spots, `"fresh": true` |
| `expected.json` | exp2b2's + LTEX table, encode statistics, height digest, mapping, spots with FO4 / decoded Starfield textures |
| `reference\compare_spots.png` | per spot 40 x 40 m top-down, FO4 layers (left) vs decoded Starfield layers (right), textures tiled |
| `reference\compare_overview.png` | region of interest, 1 m/px, average colours, hill-shaded; also `fo4_overview*.png`, `sf_overview.png` |
| `README.txt` | install, queue command, spot list |
| `offline_check_textures.json` | written by `check`: PASS and the source BTD's height digest |

Packing (verified offline): Archive2 `-format=General -compression=None` (what `exp_install.py --pack` runs) stores
all three Data files uncompressed and byte-identical (81,060,443-byte archive, built in a scratch folder).

Ground spots (worldspace frame; FO4 vertices, expect = FO4 height / 70, decoded BTD within 0.04 m under every
interpolation rule, slope <= 10 degrees, 8 m from the other probes):

| Probe | Screenshot | x, y (m) | expect (m) | FO4 ground | Starfield LTEX | from Red Rocket |
|---|---|---|---|---|---|---|
| ground_road | pt14 | -1034.9714, 1088.0 | 109.4857 | LRubbleRock01 (road bed) | LGravelRoad01 | 75 m |
| ground_lot | pt15 | -894.1714, 1034.9714 | 88.2286 | LAsphalt01 (paved lot) | LGravelDecorative01 | 147 m |
| ground_grass | pt16 | -863.0857, 978.2857 | 85.8286 | LDriedGrass01NoGrass | LGrassDeadWet01 | 211 m |
| ground_dirt | pt17 | -1144.6857, 1034.9714 | 105.6 | LDirtPath01 | LDirtPacked10 | 192 m |

The runner's terrain step screenshots every probe looking north, pitched down (`pt<k>.png`), plus the arrival
(`spawn.png`, Red Rocket).

Queue (from the integration worktree, as the other terrain queues; one test with a relaunch first):

    python scripts/game/testqueue.py plan-terrain --staging C:\Modding\staging\integ_1011 --exp-dir C:\Modding\staging\terrain_exp2t --out C:\Modding\testqueue\terrain_exp2t --plugins FO4TerrainExp2.esm,FO4TerrainExp2_Mars.esm --fresh

A dry run of that command into a scratch folder accepted the plan: test `0000_terrain_FO4CW_RedRocketSpawn`,
`fresh` true, 18 points, `z_ref` `flat_1`, drop_z 150, `exp_install.py ... --pack` as pre-launch step.

Never install together with another FO4TerrainExp2 experiment (exp2c uses the same plugin names; the installer
refuses while one is installed).

### Reading the result
| Observation | Meaning |
|---|---|
| Heights as exp2b2 (14 probes, the 4 new ones within 0.5 m) | expected: only texture sections changed |
| Spots show grass / gravel / dirt / grey gravel instead of footprint dirt, matching `compare_spots.png` | concrete vanilla LTEX in a plugin BTD render as themselves: option a works |
| Same textures but tinted red | the planet tints terrain materials; look for a biome or material colour setting |
| Everything still footprint dirt | the texture sections are ignored or the LTEX table is replaced (e.g. by the biome); compare with a vanilla overlay |
| Black, checkered or missing ground | a material failed to load (most likely one of the 7 never-used ones, e.g. `LGravelRoad01` at the road spot) |
| Hard edges every 50 m | the 6-texture-per-quadrant limit or slot order is read differently in game |

## 6. Unknowns
1. Whether concrete LTEX render as themselves in a plugin's BTD on Mars, and whether the planet tints them (exp2t).
2. The engine's exact blend (over-compositing vs height-blend thresholds); our reading reproduces vanilla data
   exactly but is not observed in game.
3. Option b: plugin-added terrain materials and plugin LTEX FormIDs in a BTD table.
4. FO4 texture scale: the renders tile FO4 textures 16 times per FO4 cell at 1,024 px (fo76utils' "16384 / 2^mip
   texels per cell" hint) and Starfield textures every `TilingDistance` metres (assumed to be metres); illustrative.
5. Grass, vertex colours (white here) and the FO4 default texture's identity (supported, not verified).

## Reproduce

    python scripts/terrain/ground_textures.py palette --out C:\Modding\research\terrain\ground\palette.json
    python scripts/terrain/ground_textures.py suggest --palette C:\Modding\research\terrain\ground\palette.json
    python scripts/terrain/ground_textures.py build --from C:\Modding\staging\terrain_exp2b2 --out C:\Modding\staging\terrain_exp2t --palette C:\Modding\research\terrain\ground\palette.json
    python scripts/terrain/ground_textures.py check --from C:\Modding\staging\terrain_exp2b2 --out C:\Modding\staging\terrain_exp2t
    python -m unittest tests.test_landtex

Defaults: `--fo4-data` the FO4 depot `Data`, `--sf-data` Starfield `Data`, `--content-resources` the Creation Kit's
`Tools\ContentResources.zip` (read-only). The vanilla surveys (layout statistics, round trip, BIOM references,
material database names, Shattered Space tables) were scratch scripts; their outputs are summarised above.
