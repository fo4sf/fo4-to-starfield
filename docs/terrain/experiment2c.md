# Terrain experiment 2c: the real Fallout 4 objects around Red Rocket on the native terrain

Author: Claude, 2026-10-11. Branch `claude/terrain-exterior-statics`, stacked on PR #64
(`claude/terrain-overlay-records`, which contains #60, #57 and #56). Starfield 1.16.244.
Status: **built and checked offline, staged, not deployed, not run in game.**
Labels: **verified** = checked here on files, number given; **supported** = supported hypothesis; **unresolved**.
Offline checks are not in-game acceptance.

## What it tests
The owner's step-2 check, "alignment with a familiar placed structure", now in Starfield: experiment 2b
([overlay-records.md](overlay-records.md): the 29 x 29-cell BTD of the real heights, Location, mask, Absolute
alignment, Mars registration, persistent anchor) plus **every Fallout 4 reference of FO4 cells x -20..-15,
y 16..21 that converts**, placed at FO4 position / 70 in the same worldspace `FO4CW_Commonwealth`. That is
8,069 references of 1,385 converted models around Red Rocket (351 m x 351 m).

1. Do references in the overlay worldspace's own exterior cells load, and merge with the same offset as its terrain
   (the runner measures everything relative to the anchor `02000800`)?
2. Does an object placed at FO4 position / 70 sit on the BTD as it sits on FO4's terrain? The Red Rocket building
   `RedRExt_Workshop01` (`000211C0`, FO4 z 7360 = 105.1429 m) stands exactly on FO4's terrain (PR #56).
3. Do the tops of large flat objects and the Red Rocket shop floor read at their converted collision height?

## Pipeline

| Step | Tool | Result |
|---|---|---|
| 1 export | `dotnet/Fo4Land export-exterior` (new mode, Claude's) | 36 FO4 cells, 8,960 references + 48 actors (deferred), 12 s |
| 2 select | `scripts/terrain/make_exp2c.py select` (`src/fo4sf/exterior.py`) | 8,099 to convert (1,400 models), 909 skipped with a reason |
| 3 convert | `scripts/convert_batch.py --cell-json ... --prefix fo4cw` | 1,386 models converted, 15 failed, 278 s, 2.3 GB |
| 4 stage | `make_exp2c.py stage` (+ `dotnet/TerrainExp2` with `objects.json`) | `C:\Modding\staging\terrain_exp2c`, plugin 829,032 B |
| 5 check | `make_exp2c.py check` | 109 checks, **PASS** |

### 1. Exterior export (verified)
- `dotnet/Fo4Export` (Codex's, unchanged) exports interior cells only. The new Claude-owned mode
  `Fo4Land <Fallout4.esm> export-exterior <World> <xmin> <ymin> <xmax> <ymax> <out.json>` compiles Fo4Export's
  `ReferenceExport.cs`, `KeywordExport.cs` and `TeleportDependencies.cs` in from their source files
  (`dotnet/Fo4Land/Fo4Land.csproj`). Every reference therefore has exactly the schema v2 fields of an interior
  export ([CELL-EXPORT.md](../CELL-EXPORT.md)), plus `exterior_cell` (FO4 grid) and `source_cell` (the CELL that stores it).
- Persistent references of exterior cells live in the worldspace's persistent cell in Fallout4.esm
  (`00018AA2` for Commonwealth); they are taken from there when floor(position / 4096) is in the range.
  Top level: `cell` is a name for the range, `formkey` the worldspace (there is no single cell), `worldspace`,
  `exterior` (range and per-cell counts).
- Cross-check against the independent Python reader `src/fo4sf/fo4land.py` (raw group walk): the same
  9,008 FormIDs, the same cells, positions within 0.004 units (JSON float formatting), persistent flags agree
  (496 persistent, 488 objects + 8 actors).

### 2. Selection: nothing is dropped silently (verified counts)
`exterior.classify` puts every reference in one of two lists. Skipped (`skipped.json`, 939 in total):

| Reason | Refs | What |
|---|---|---|
| `type_not_translated` | 453 | decals (TextureSet) 125, lights 119, bendable splines (power lines) 110, idle markers 67, sound markers 21, acoustic spaces 11 |
| `editor_marker` | 233 | models named `*marker*` (XMarkerHeading 99, invisible generic 37, ...), the filter convert_batch applies to cell exports |
| `effect` | 107 | `effects\` meshes: wind debris, mist, paper bits, leaves (particles / fog volumes) |
| `no_model` | 66 | trigger volumes (Activator 35), PlaneMarker / CollisionMarker / LightBox statics (27), 4 armour (its world model is not in the ARMO record Mutagen reads) |
| `deferred` | 48 | actors (`PlacedNpc`): NPC translation is another track |
| `conversion_failed` | 30 | 15 models: rubble FloorChunk01/03/04/05 and the gnat swarm ("no static BSTriShape geometry"); distant clouds `Sky\CloudDistant*` and workshop borders ("only effect-shader shapes") |
| `water` | 2 | `Water\Water1024.nif` water planes: FO4 renders them with a water type; as a static they would be an opaque grey sheet |

- **Trees did not fail**: the 1,382 tree references here (`landscape\trees`) are STAT records with ordinary
  BSTriShape geometry and converted like any static. Landscape statics (grass clumps 408, grass mounds 316, rocks 340,
  roads 147, sidewalks 196, cliffs 93, guard rails 48) converted too.
- Placed by family: setdressing 2,481, trees 1,382, plants 1,197, architecture 617, grass 408, rocks 340, grass mounds
  316, precombines (`scol`) 299, sidewalks 196, props 159, roads 147, interiors (the Red Rocket models) 142, others.

### 3. Conversion
- The existing converter with `--starfield-data` (FO4's own collision bodies, rigged doors), a type list that adds
  Flora, Ingestible, Weapon, Ammunition and Armor (loose items become plain statics), and the new
  **`convert_batch.py --prefix`** (default `fo4port`, unchanged behaviour): the files go to `meshes\fo4cw`,
  `materials\fo4cw`, `textures\fo4cw`, so FO4Port's own archive (loaded later, same converter) can never override an
  experiment file at the same path. The checkpoint signature names a non-default prefix only, so existing
  checkpoints stay valid.
- Collision of the placed references: FO4's own bodies 5,446, none in FO4 (paper, plants, rubble) 2,550, rigged door
  boxes 15, passable door 1, **guessed boxes 57** (13 precombined meshes: 11 whose debris bodies use the undecoded
  primitive encoding, one with a scaled collision node, one whose native bodies came out empty). No measuring point
  uses an object with guessed collision.

### 4. Placement and plugin layout (decision)
- Position = FO4 position / 70 in the worldspace's own frame, Starfield cell = floor(x / 100 m), floor(y / 100 m)
  (16 cells, x -12..-9, y 9..12), rotation copied (radians), scale copied, rigged doors shifted by their hinge offset
  as PluginSpike does, initially disabled stays disabled (1).
- All references are **temporary** in their exterior cell, the 105 that are persistent in FO4 too: nothing here
  (no scripts, aliases or linked references) needs them persistent, and 105 statics would otherwise stay loaded.
  FO4 enable parents are not translated (11 references show by default).
- **One plugin**: `FO4TerrainExp2.esm` = exp2b's records + 1,376 STAT + 9 DOOR + 8,069 REFR, EditorIDs `FO4CW_<stem>`.
  Why:
  - the meshes must ship in `<plugin> - Main.ba2` (loose files are disabled), and `exp_install.py --pack` builds
    one archive named after the first plugin;
  - the new records are allocated **after** every terrain record, so exp2b's FormIDs do not move: the anchor stays
    `02000800`, `FO4TerrainExp2_Mars.esm` is byte-identical to exp2b's, and the runner's plan format is unchanged;
  - nothing depends on FO4Port.esm or its archive (own EditorIDs, own asset prefix).
  - Alternatives: a separate statics plugin mastered on `FO4TerrainExp2.esm` would need its own archive, CELL
    overrides of 16 exterior cells and a third plugin in the install, for no gain; FO4Port.esm would tie the
    experiment to the main build, and PluginSpike writes interior cells only.
- STAT records have no object bounds, as in FO4Port.esm (which loads in game); whether exteriors need them for
  culling is **unresolved**.

### 5. Reading back the converted collision (verified)
`src/fo4sf/sfbodies.py` (new) decodes the collision of our converted Starfield NIFs: every bhkNPCollisionObject's
tagfile (compressed mesh, convex hull with its radius, sphere, the box template), placed by its node's world
transform. On `RedRExt_Workshop01` it gives back FO4's own collision exactly: 3,557 vertices, 5,898 triangles,
0 differ from `fo4collision` on the source NIF. All 1,385 models decode (736,906 world triangles).

## Red Rocket, as the converted collision shows it (verified offline)
- `RedRExt_Workshop01` (`000211C0`) holds the rocket tower (19 m), the canopy and the shop **ceiling** at 3.2 m.
  It has **no floor**.
- `RedRExt_Workshop02` (`001B5F12`, same origin and rotation 225 degrees) holds the **shop floor**, 0.0286 m
  (2 FO4 units) above the origin, at 105.1714 m everywhere (512 samples, min = max), and the shop roof at 4.6 m.
- The building origin (the COC marker and the anchor stand there) is under the canopy, on the pump island
  `SWIsland9x1Str01` (`00035B80`), 0.117 m above the terrain. After `coc` the player lands on it at 105.2609 m.
- Yaw convention: 33 references at floor height (cabinets, counters, the tool chest, the shop door) lie inside the
  shop footprint with the clockwise heading PluginSpike and `routes.py` use; with the opposite sign, 0. So the
  convention used for the offline geometry is right for this building (**verified**; the game itself reads the
  copied angles).

## Offline results (verified, `offline_check.json`)
- **Object z - terrain z.** Red Rocket building: -0.56 mm against the decoded BTD (all three interpolation rules),
  0.00 mm against FO4's own LAND (FO4 says 0). For all 8,069 origins, the BTD under the object differs from FO4's
  terrain under it by median 1.43 mm, p95 24.8 mm, p99 56.6 mm, max 482 mm; 6,743 within 1 cm, 7,954 within 5 cm.
  The worst five are around (-877, 1047), a sharp FO4 terrain edge the 0.78 m BTD grid cannot hold (experiment 2's
  cliff note). So objects keep their FO4 height above the terrain to millimetres almost everywhere.
- **Raw walk** of `FO4TerrainExp2.esm` (independent of Mutagen): masters [Starfield.esm]; CELL 842, WRLD 1, SFBK 1,
  LCTN 1, STAT 1,376, DOOR 9, REFR 8,071 (8,069 + COC marker + anchor); 16 exterior cells with references, as
  `objects.json` says (most: 1,164 in cell (-9, 10)); every REFR's base, position (within 6.1e-5 m, float32),
  rotation, scale and disabled flag as written; **all 847 exp2b records unchanged**; BTD, mask and Mars plugin
  byte-identical to exp2b; the exp2b check (FNAM, XLCN, INAM/HNAM, anchor, Mars entry, mask) passes again.
- **Files**: every base model is in `Data\meshes`; the 1,385 NIFs name 3,366 geometries, 704 materials; the
  materials name 2,328 of our textures and one vanilla texture (in the Starfield texture archives): 0 missing.

## plan.json (runner format, three entries)
All entries: `coc FO4CW_RedRocketSpawn`, anchor `02000800` at exp2b's local (-989.0286, 1147.2, 105.1434),
`spawn_local` (-989.0286, 1147.2, **105.2609**) = the pump island the player lands on (exp2b: 105.1434, the terrain),
`settle_ms` 8000. Expectations are in the worldspace's own frame; the runner adds the measured offset.
Measuring points are level over a 0.6 m disc (about the player's capsule; **supported**) and on one object.

| Entry | drop_z | Label | x | y | expect | What |
|---|---|---|---|---|---|---|
| 1 | 150 | flat_2 | -976.4571 | 1144.6857 | 105.0286 | terrain (exp2b) |
| 1 | 150 | slope_2_cell_-17_18 | -983.7714 | 1106.2857 | 100.5714 | terrain |
| 1 | 150 | seam_fo4_east | -991.0857 | 1100.8000 | 99.5429 | terrain |
| 1 | 150 | seam_sf_west | -1000.2286 | 1089.8286 | 100.4571 | terrain |
| 1 | 150 | seam_sf_east | -998.4000 | 1089.8286 | 100.0000 | terrain |
| 1 | 150 | resampled_sw | -1258.0571 | 857.6000 | 94.8571 | terrain |
| 1 | 150 | resampled_ne | -735.0857 | 1367.7714 | 121.7143 | terrain |
| 1 | 150 | redrocket_roof | -993.3143 | 1140.4142 | 109.7408 | roof of RedRExt_Workshop02, 4.71 m above the terrain |
| 1 | 150 | flat_sancroadcrvcustom02 | -1167.6982 | 1245.5133 | 110.0482 | road piece `000788B5`, 0.10 m above the terrain |
| 1 | 150 | flat_northbridge | -1085.5932 | 1161.1108 | 106.8362 | the North bridge `0001F970`, 0.31 m above the terrain |
| 1 | 150 | roof_bld04angle45brickacom01 | -900.2594 | 1022.3516 | 103.8768 | brick building roof `0001CC78`, 16.0 m above the terrain |
| 2 | 105.92 | redrocket_floor_1 | -996.9562 | 1135.2723 | 105.1714 | shop floor, dropped 0.75 m, 3.17 m free above it |
| 2 | 105.92 | redrocket_floor_2 | -996.4562 | 1141.7723 | 105.1714 | shop floor |
| 3 | 150 | redrocket_1 | -989.2571 | 1146.5143 | 110.4923 | exp2b point, now under the canopy roof (Workshop02) |
| 3 | 150 | redrocket_2 | -989.2571 | 1148.3429 | 110.6579 | same |
| 3 | 150 | flat_1 | -987.4286 | 1128.2286 | 105.0286 | terrain, a truck 1.08 m high 0.45 m away |
| 3 | 150 | slope_1_cell_-18_18 | -1009.3714 | 1075.2000 | 108.8821 | now on rock `RockCliff04` (3.97 m above the terrain) |
| 3 | 150 | slope_3_cell_-18_19 | -1044.1143 | 1153.8286 | 110.3400 | on a rock edge (`RockCliff02`), disc spread 1.36 m |
| 3 | 150 | slope_4_cell_-17_19 | -947.2000 | 1141.0286 | 98.8571 | terrain, a grass mound 0.20 m high 0.6 m away |
| 3 | 150 | seam_fo4_west | -998.4000 | 1106.2857 | 100.3429 | terrain, a tyre pile 0.24 m high 0.15 m away |

- Entry 1 measures terrain and object tops together (one verdict). Entry 2 is dropped from 0.75 m above the floor
  so the player starts inside the shop, under its ceiling. Entry 3 holds the seven exp2b terrain points the objects
  now cover or crowd; its verdict is **informational** (rock edges, tyres), compare its readings one by one.
- The runner moves the player with `setpos x`, then `y`, then `z`; a scratch capsule test (0.4 m radius, 1.8 m) found
  no collision at any intermediate position of entry 2 (spawn -> floor 1 -> floor 2).
- REFR FormIDs of every measured object (load-order byte 02 assumed, as the anchor) are in `expected.json`
  (`owner.refr`), e.g. Workshop02 `02002DC3`, so `prid` can find them.

## Staged files (`C:\Modding\staging\terrain_exp2c`, outside the repo)

| File | Bytes | Content |
|---|---|---|
| `FO4TerrainExp2.esm` | 829,032 | exp2b's WRLD / SFBK / LCTN / 841 cells / COC marker / anchor + 1,376 STAT, 9 DOOR, 8,069 REFR |
| `FO4TerrainExp2_Mars.esm` | 6,512 | byte-identical to exp2b's |
| `Data\Terrain\FO4CW_Commonwealth.btd`, `Data\textures\terrain\overlaymasks\fo4cw_commonwealth.dds` | | byte-identical to exp2b's |
| `Data\meshes\fo4cw`, `Data\geometries`, `Data\materials\fo4cw`, `Data\textures\fo4cw` | 2.3 GB, 7,733 files | converted models |
| `plan.json`, `expected.json`, `objects.json`, `formids.json`, `skipped.json`, `exp2_params.json`, `offline_check.json`, `README.txt` | | runner input, every point with owner and landing, what TerrainExp2 placed, FormIDs, skipped references, builder params, offline check, manual steps |

**Textures**: `exp_install.py --pack` puts all of `Data\` into `FO4TerrainExp2 - Main.ba2` (General). Starfield
normally streams textures from a separate DX10 archive, so the converted DDS files may need their own
`FO4TerrainExp2 - Textures.ba2` (another track adds that to the installer). Without it the objects may show
untextured; positions and collision do not depend on it (README.txt says so).

## Running it
Never with experiment 1 or 2b installed (same plugin names, same `MarsPlanetData` override).

    python scripts/game/testqueue.py plan-terrain --staging <FO4Port build dir> --exp-dir C:\Modding\staging\terrain_exp2c ^
        --out <queue dir> --plugins FO4TerrainExp2.esm,FO4TerrainExp2_Mars.esm
    python scripts/game/testqueue.py run --queue <queue dir>

Three tests (one per entry). By hand: `README.txt`.

## Reading the result

| Observation | Meaning |
|---|---|
| Entry 1 PASS, entry 2 PASS | objects and terrain share one frame: FO4 position / 70 on the BTD reproduces FO4's placement (step-2 check passed) |
| Terrain points right, object tops off by one constant | the overlay merge moves references differently from the terrain (or not at all): compare with the anchor offset |
| Terrain right, object points read the terrain | the objects did not load (archive, cell attach, or references in an overlay worldspace are not merged) |
| Object tops right, floor points read ~4.6 m or ~3.2 m higher | the teleport put the player above the roof / ceiling (drop_z + offset wrong) |
| Floor points read about 105.14 instead of 105.17 | the player stood on terrain: the shop floor collision did not load |
| Everything off by the same Z as exp2b | the offset question of exp2b (HNAM / Absolute), not the objects |
| Objects visible but white / untextured | the textures need their own DX10 archive (see Textures) |

## Unknowns
1. Everything in game (the run is queued after exp1d / exp2b).
2. Whether references in an activated overlay worldspace merge with the same offset as its terrain.
3. Texture archive format; STAT object bounds in exteriors; 8,069 references in 16 cells (performance, LOD: none).
4. The player capsule radius (0.6 m disc assumed for level / clear checks) and how `getpos z` reads on a slope.
5. FO4 enable parents, persistence, actors, lights, decals, power lines and water: not translated (counted above).

## Reproduce
    dotnet run --project dotnet/Fo4Land -c Release -- <Fallout4.esm> export-exterior Commonwealth -20 16 -15 21 <work>\export.json
    python scripts/terrain/make_exp2c.py select --export <work>\export.json --work <work>
    python scripts/convert_batch.py --fo4-data <FO4 Data> --staging <work>\convert --content-resources <ContentResources.zip> ^
        --texconv <Texconvx64.exe> --collision-template <template.nif> --starfield-data <Starfield Data> ^
        --cell-json <work>\convert_input.json --types Static,StaticCollection,MovableStatic,Furniture,Door,Activator,Container,MiscItem,Terminal,Flora,Ingestible,Weapon,Ammunition,Armor ^
        --prefix fo4cw --limit 100000 --resume
    python scripts/terrain/make_exp2c.py stage --work <work> --exp2b C:\Modding\staging\terrain_exp2b --out C:\Modding\staging\terrain_exp2c --sf-esm <Starfield.esm>
    python scripts/terrain/make_exp2c.py check --work <work> --exp2b C:\Modding\staging\terrain_exp2b --out C:\Modding\staging\terrain_exp2c --sf-data <Starfield Data> --fo4 <Fallout4.esm>
    python -m unittest tests.test_exterior tests.test_sfbodies tests.test_make_exp2c tests.test_batch_prefix

`<work>` was `C:\Modding\staging\terrain_exp2c_work`. Times: export 12 s, conversion 278 s, stage 17 s (plus about
15 s to copy 2.3 GB the first time), check 9 s (with `--fo4`).
