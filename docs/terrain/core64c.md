# core64c: every Fallout 4 exterior object of the 64-cell core on the core64 terrain

Author: Claude, 2026-10-12. Branch `claude/terrain-core64-objects`, stacked on PR #72 (`claude/terrain-core64`,
the 64 x 64-cell overlay) and PR #66 (`claude/terrain-exterior-statics`, the exp2c object pipeline). Starfield 1.16.244.
Status: **built and checked offline (167 of 167 checks), staged in `C:\Modding\staging\terrain_core64c`, not deployed,
not queued.**
Labels: **verified** = checked here on files, number given; **supported** = supported hypothesis; **unresolved**.
Offline checks are not in-game acceptance.

## What it is
core64 (PR #72) is one overlay worldspace `FO4Core_Commonwealth` of 64 x 64 Starfield cells (6.4 km, local frame = FO4
position / 70) with the real FO4 heights, registered on Mars. In game (2026-10-11, PR #74 section 6b) every probe up
to about 380 m from the Red Rocket arrival (Sanctuary, Vault 111, Concord, 500 m diagonally) read FO4 height / 70
within 0.01 m; a single teleport more than about 4 cells from where the player stood raised "Boundary Reached" and
hung, while core64b's north-west ray travelled in 300 m hops (7 s each) and read every probe to 2 km
(**verified**, runner reports). exp2c (PR #66) put the 8,069 converted FO4 objects around Red Rocket on exp2b's
terrain; in game they stood on it with collision within 0.02 m and their textures loaded from the General archive.

core64c puts **every Fallout 4 exterior object of the core that converts** on core64: **648,358 references of 11,769
models**, in the same plugin after core64's records, so core64's records, FormIDs, BTD, mask and Mars plugin are
unchanged. The core covers the whole playable Commonwealth (FO4 references reach FO4 cells x -53..33, y -49..41, all
inside the 64-cell BTD), so this is the whole Commonwealth's exterior object set, not a sample.

## Measured first (verified)

| Quantity | Value | How |
|---|---|---|
| FO4 references in the covered cells | **706,579** = 701,754 placed objects + 4,825 deferred placements (actors 3,685, hazards 858, traps 281, a missile) in 12,100 FO4 cells (x -55..54, y -55..54) | `Fo4Land export-exterior`, 11 bands of 10 rows, 76 s; an independent raw count (`fo4land.py`) found 705,439 REFR + ACHR inside the BTD and 3 outside it |
| Selected to convert | **649,596** references of **11,887** models | `make_core64c.py select` (`exterior.classify`), 17 s |
| Converted | **11,769 models**, 118 failed: 102 only effect-shader shapes, 13 without BSTriShape geometry, 3 not in the mesh archives (the converter reports them as `AttributeError`) | the dry run in `measure` predicted exactly these 11,769 / 118 |
| Placed | **648,358 references** (1,238 belong to the 118 failed models) | `make_core64c.py stage` |
| Materials, textures | 2,632 materials (+ 22 that fall back to the neutral material: BGSM or textures missing from the archives), 8,593 textures | conversion log |
| Textures at full resolution | **7.26 GiB** (7,797,955,660 B: color 2.29, normal 3.04, rough 1.20, opacity 0.73 GiB); `measure` estimated 7.30 GiB before converting | `texture_log.json`: the size of every converted texture before the cap |
| Textures written (capped) | **2.42 GiB** (2,593,516,620 B: color 1.44, normal 0.77, opacity 0.11, rough 0.10 GiB); 5,557 of 8,593 capped | color 1024, normal 512, rough 256, opacity 512 px (below) |
| Meshes + geometries | 0.98 GiB (NIFs 606,167,545 B, `.mesh` 449,886,306 B); estimate 0.96 GiB | |
| Conversion time | **2,499 s** (41.6 min), one process, nothing reused | `convert_batch.py --prefix fo4core --max-texture ...` |
| Plugin | `FO4TerrainCore.esm` **46,114,630 B**: core64's 4,102 records + 11,699 STAT + 70 rigged DOOR + 648,358 REFR, next FormID 0xA2AA5 (a full master allows 0xFFFFFF); written in 17.6 s | `dotnet/TerrainOverlays` objects mode |
| Archive (stored) | **3,899,305,077 B (3.63 GiB)**, 51,821 entries, none packed: textures 2.43 GiB (incl. the mask), meshes 0.66 (incl. the BTD copy), geometries 0.42, terrain 0.10, materials 0.02 | Archive2 dry run with the installer's arguments, 19 s |

References per Starfield cell (plugin): 1,708 cells hold references, the densest (downtown Boston, cell (0, -4))
6,049. By 16 x 16-cell region (1.6 km) the four central regions hold 136 to 183 thousand references each, every other
region at most 12 thousand.

### Skipped, never silently (`skipped.json`, 58,221, verified counts)

| Reason | References | What |
|---|---|---|
| `type_not_translated` | 31,979 | decals (TextureSet) 13,118, **lights 6,275**, idle markers 5,828, bendable splines (power lines) 4,982, sound markers 878, acoustic spaces 749, books 104, holotapes 22, keys 12, talking activators 11 |
| `editor_marker` | 13,542 | models named `*marker*`: XMarker statics 8,560, invisible furniture markers 2,844, comment / helper / dummy-loot markers |
| `deferred` | 4,825 | **actors** (PlacedNpc) 3,685, hazards 858, traps 281, a missile: NPCs are another track |
| `no_model` | 3,829 | trigger volumes (Activator) 2,414, collision planes and primitives 1,155, 252 armour / 7 doors / 1 weapon without a world model in the record Mutagen reads |
| `effect` | 2,087 | `effects\` meshes (fog, mist, debris, light beams) |
| `conversion_failed` | 1,238 | references of the 118 **models that do not convert** |
| `water` | 721 | **water planes** `Water\*.nif` (as a static they would be an opaque sheet) |

Also not translated, counted in `expected.json`: 6,732 references have an FO4 enable parent (they show by default),
3,706 are persistent in FO4 (all are temporary here), 219 stay initially disabled.

## Why one archive with capped textures, not a region split (decision)
- **4 GiB.** Every large vanilla archive stops just below 2^32 bytes: `Starfield - Textures02 / 05 / 06 / 07 / 09 / 10`,
  `Meshes01`, `Voices01`, `FaceAnimation01..03`, `WwiseSounds01..03`, `LODTextures01` are 4,294,061,043 to
  4,294,946,755 bytes, never more (directory listing, **verified**). Whether the engine reads an archive beyond 4 GiB
  is **unresolved**, so one archive stays below it (budget 3.8 GiB).
- **One archive per install today.** `exp_install.py --pack` (the runner's installer on `claude/integration-1011`)
  packs the whole staged Data tree into the first plugin's `<plugin> - Main.ba2`. Starfield also loads
  `<plugin> - Textures.ba2` (vanilla SFBGS003 / 00D, FO4Port), and its executable holds the patterns
  `.* - Main[0-9]*\.ba2` and `%s%s%02u.ba2` (read-only string scan), so numbered per-plugin archives may load too
  (**unresolved**: no installed plugin uses them).
- **Full resolution needs about 8.3 GiB** (textures 7.26 + meshes 0.98 + terrain 0.21): at least three archives.
- **A region split does not help.** The 11,769 models share 2,632 materials across the whole map, so every region
  archive needs most of them. Split into the 15 occupied 16 x 16-cell regions at full resolution: **28.8 GiB** in all
  (3.5 times one archive), and each of the four central regions would still need 5.6 to 6.2 GiB, above 4 GiB on its
  own (`measure.json` `region_split_full_resolution`, **supported**: estimate from the archives' texture records).
  Smaller regions duplicate more.
- **Disk.** C: had 12 to 43 GB free while this ran (other jobs come and go), and the installer builds the archive in
  `%TEMP%` on C: before copying it to the game. A full-resolution build plus its archive would need about 17 GB at once.
- **Chosen:** convert with per-kind caps that drop top mip levels (no re-encoding: the remaining levels are the
  texconv output's own smaller levels): color 1024, normal 512, rough 256, opacity 512 pixels on the longest side
  (`convert_batch.py --max-texture`, new, off by default, part of the checkpoint signature when set). Result above:
  2.42 GiB of textures, 3.63 GiB in all.
- **Full resolution later** = one plugin's `Main` + `Textures` archives plus a second carrier plugin (three archives),
  which needs the installer to pack per plugin and an in-game check of the second archive. Not done here.
- Alternatives: cap 512 for every kind (1.66 GiB, blurrier color), cap 1024 for every kind (5.73 GiB, two archives),
  region split (above). Recorded in docs/ai/decisions.md.

## Pipeline

| Step | Tool | Result |
|---|---|---|
| 1 export | `dotnet/Fo4Land export-exterior Commonwealth -55 <y0> 54 <y0+9>` x 11 | 630 MB JSON, 76 s |
| 2 select | `make_core64c.py select --work <work> --core terrain_core64` | `selected.json` (slim references), `convert_input.json` (one entry per model), `selection.json`, 17 s |
| 3 measure | `make_core64c.py measure --fo4-data <FO4 Data> --calibrate <exp2c convert>` | `measure.json`: dry run of the converter's material logic, sizes at full resolution, per-kind caps, region split; 63 s |
| 4 convert | `convert_batch.py --cell-json convert_input.json --prefix fo4core --max-texture color=1024,normal=512,rough=256,opacity=512 --starfield-data ... --resume` | 11,769 models, 3.4 GiB, 2,499 s |
| 5 stage | `make_core64c.py stage --sf-esm <Starfield.esm>` | placing, hard links (no second copy), plugin, plan; 92 s |
| 6 check | `make_core64c.py check --fo4 --fo4-data --sf-data --archive2 --scratch` | 167 of 167 PASS, 95 s (Archive2 dry run 19 s) |

- Placing is exp2c's (`exterior.place`): FO4 position / 70 (core64's origin is CW (0, 0)), rotation and scale copied,
  rigged doors shifted by their hinge offset, Starfield cell of the written position, initially disabled stays
  disabled, every reference temporary in its exterior cell, enable parents not translated. EditorIDs `FO4Core_<stem>`
  (checked not to clash with core64's six EditorIDs), assets under `meshes\fo4core`, `materials\fo4core`,
  `textures\fo4core`, `geometries\`. Collision of the placed references: FO4's own bodies 486,064, none in FO4
  153,553, guessed boxes 7,786, rigged door boxes 759, passable doors 123, none 73.
- `dotnet/TerrainOverlays` gained exp2c's objects mode (`"objects": "objects.json"` in `overlays_params.json`): STAT
  (or rigged DOOR) per model and REFR per reference, allocated after every core64 record. Rebuilt without objects it
  writes core64's two plugins byte for byte; with objects, a second stage run rebuilt `FO4TerrainCore.esm` byte for
  byte (SHA-256 924e182b...) and the same plan (**verified**).
- `stage` hard-links the converted files into `Data\` (same volume: no second copy) and copies core64's three Data
  files; it refuses a Data tree that would not fit one archive below 4 GiB.

## Offline results (verified, `offline_check.json`, 167 of 167 checks)
- **core64 unchanged**: `overlays_params.json` = core64's + `"objects"`; BTD, its `meshes\terrain` copy, mask and
  `FO4TerrainCore_Mars.esm` byte-identical; all 4,102 core64 records unchanged (signature, flags, fields); every new
  FormID after core64's last (0x001805); core64's own record checks (WRLD, SFBK FNAM 4,096 of 4,096, ENAM, INAM 1 /
  HNAM 0, Location, anchor, COC marker, unique PNDT entry) pass again.
- **Records** (raw walk, independent of Mutagen): 11,769 STAT/DOOR = bases, every base model on disk; every REFR's
  base, position (worst 1.2e-4 m, float32), rotation (2.4e-7 rad), scale and disabled flag as `objects.json`; 648,360
  REFR = objects + COC marker + anchor; REFRs per cell as `objects.json` in 1,708 cells; every reference in the cell of
  its written position. Files: 30,856 geometries, 2,633 materials, 8,596 own textures and 1 vanilla texture named by
  the models and materials: 0 missing.
- **Object z vs terrain under every one of the 648,358 origins**:
  - BTD minus FO4's own LAND (the alignment error the terrain conversion adds under each object): **median 2.78 mm,
    p95 34.1 mm, p99 86.7 mm, max 3.19 m**; 80.3 % within 1 cm, 97.3 % within 5 cm; 4,868 above 0.10 m, 673 (0.10 %)
    above 0.25 m, 15 above 1 m. At those 673 the FO4 terrain quad under the origin spans a median 3.54 m (0.46 m over
    all origins): quarry walls, cliffs and terrain dipped under building floors (worst: a Hightech floor edge over FO4
    terrain that rises 13 m within about 5 m), which the 0.78 m BTD grid rounds off; FO4's triangle-versus-bilinear rule
    explains only 22 of them (**supported**: resampling of steep relief, not placement). For comparison, exp2c on
    exp2b's BTD: median 1.43 mm, p99 56.6 mm, max 482 mm over 8,069 origins.
  - Object z minus the terrain itself (FO4's own placement, kept): against the BTD median +0.22 m, p1 -4.88 m, p99
    +61.7 m, min -100.5 m, max +372.6 m; against FO4's LAND median +0.219 m, p99 +61.69 m.
  - The Red Rocket station: z minus BTD 3.48 mm (one quantisation step: 9.51 mm), z minus FO4 LAND 0.00 mm.
- **Plan points** re-derived from the converted collision in a local world (62,131 references of 3,446 models, 7.7
  million collision triangles within 620 m of the arrival): every object point lands on its owner within 0.04 mm.
  The three judged tops and the seven informational object points equal FO4's own collision (the source NIFs from
  the FO4 archives, `routes.collision_bodies`, or Codex's `fo4_compounds.decode_body` for the museum's compound
  bodies) within 0.045 mm, all on layer 1, except the informational Sanctuary road probe `nw_200m`, 10.0 mm above
  FO4's compound collision (convex radius is the likely cause, **unresolved**).
- **Archive**: Archive2 with the installer's arguments built 3,899,305,077 bytes (equal to the estimate), 51,821
  entries, none packed, then deleted. 61 paths keep FO4's spaces (`loose planks 01.nif`); exp2c shipped 33 such paths
  the same way and loaded.

## plan.json (runner format, three entries, one fresh coc each)
Every entry: `coc FO4Core_RedRocketSpawn`; `spawn_local` (-989.2571, 1146.5143, **105.2609**) = the pump island the
player falls onto from the COC marker (as in exp2c); **`z_ref zref_ground`** (-985.2571, 1138.5143 -> 105.0253: open
level terrain 8.9 m from the arrival, nothing above it within 1.5 m), which is also the **first point** (the runner
does not hop the first jump); **`hop_m` 300, `hop_wait_ms` 7000** (core64b's verified hops: no single teleport longer
than 300 m); points ordered around the arrival (spoke zig-zag + 2-opt on the longest jump). The integration runner
(`claude/integration-1011` dcf8ad6) plans 3 terrain tests from it with `spawn_local`, `z_ref`, `hop_m`, `hop_wait_ms`,
`settle_ms` and `fresh` (planned into a scratch folder, **verified**).

| Entry | Drop / settle / hops | Points (expect, m) | Verdict tells |
|---|---|---|---|
| 1 terrain (judged) | 170 m / 10 s / 6 | `zref_ground`, core64's probes that stay clear of objects within 1 m: `vault111`, `nw_500m`, `w_200m`, `s_200m`, `s_500m`, `se_500m`, `e_200m`, `ne_500m` | without objects: PASS (they do not matter); flat ground: FAIL (54.5 m) |
| 2 object tops (judged) | 160 m / 8 s / 0 | `zref_ground`; `sanctuary_house_roof` 117.8513 (the player's house roof, 5.78 m above the terrain, a low-pitched part: disc spread 0.085 m); `redrocket_roof` 109.7408 (shop roof, 4.72 m); `concord_museum_roof` 101.6544 (Museum of Freedom, 14.20 m) | without objects: FAIL (14.1 m) |
| 3 informational | 190 m / 9.5 s / 3 | `zref_ground`; core64 probes now on objects: `arrival` (canopy 110.4923), `concord` (curb 88.2915), `se_200m` (88.2120), `sanctuary_bridge` (North bridge 109.6907), `nw_200m` (road 111.7757), `sanctuary` (grass mound 110.2780), `w_500m` (cliff 146.9985), or near one: `e_500m` (a maple 0.3 m away), `ne_200m` (a rock cliff 0.8 m away); **screenshot spots** `view_redrocket` (45.8 m south of the station), `view_sanctuary_house` (37.2 m south of the house), `view_concord_museum` (73.0 m south of the museum) | read one by one; each point has its `ptN.png` |

Screenshots: before every drop the runner turns the player to heading 0 (north) and pitch 15 and saves `ptN.png`
after the read, so every point is a screenshot spot. The three view spots are open, level terrain south of each
landmark whose line of sight from eye height (1.7 m) to the landmark's middle crosses no collision triangle and stays
above the terrain (offline check). Every arrival so far was at night on Mars; the runner on `claude/integration-1011`
does not set the time (PR #73 adds that).

## Running it
Prerequisites: no other terrain experiment installed (core64, core64b and core64e use the same plugin names and
archive name; `exp_install.py uninstall --starfield <game>` first, the installer refuses otherwise). The installer
builds the 3.63 GiB archive in `%TEMP%` (C:) and copies it into the game's Data folder (D:).

    python scripts\game\testqueue.py plan-terrain --staging C:\Modding\staging\integ_1011 --exp-dir C:\Modding\staging\terrain_core64c ^
        --out C:\Modding\testqueue\terrain_core64c --plugins FO4TerrainCore.esm,FO4TerrainCore_Mars.esm --fresh
    python scripts\game\testqueue.py run --queue C:\Modding\testqueue\terrain_core64c

By hand: `C:\Modding\staging\terrain_core64c\README.txt`. The runner's `beyond` step (after the points; recorded, not
judged) teleports to the first point + 500 m without the merge offset, so it may raise "Boundary Reached"; `--fresh`
relaunches before the next test.

## Reading the result

| Observation | Meaning |
|---|---|
| Entry 1 PASS | core64's terrain still reads exactly with 648,358 objects in the worldspace |
| Entry 1 FAIL, probes hanging at the drop height | cells did not load in time with this many references: compare the hop and settle times with core64b |
| Entry 2 PASS | FO4 objects at FO4 position / 70 stand on core64 at three familiar places 220 to 250 m apart (exp2c's check, now over the whole map's object set) |
| Entry 2 FAIL with the tops at terrain height (house about 112.1, shop 105.0, museum 87.5) | the objects did not load there (archive, cell attach, memory) |
| Entry 2 FAIL by one constant | objects merged with another offset than the terrain |
| Load or frame-time trouble, a crash | too many references or textures in the loaded cells: next steps are fewer references per cell (precombines) or a smaller region |
| Screenshots dark | night on Mars (see above) |

## Unknowns
1. Everything in game: whether 1,708 cells with up to 6,049 references each load and stream; frame time, memory and
   load time with a 46 MB plugin and a 3.6 GiB archive.
2. Whether the objects keep the terrain's merge offset everywhere (exp2c: yes, for 16 cells near Red Rocket).
3. STAT records have no object bounds (as in FO4Port and exp2c, which load); culling and LOD at this size: no LOD for
   the objects, far objects simply are not loaded (**unresolved** how that looks).
4. Texture quality at the caps; full resolution needs three archives and a per-plugin installer.
5. Everything skipped above (actors, lights, decals, power lines, markers, effects, water) and FO4 enable parents.
6. The capsule (0.6 m landing disc, 1 m clear radius, 0.4 m x 1.8 m teleport cylinder: assumptions as in exp2c);
   intermediate teleport positions overlap objects 3 / 0 / 5 times in entries 1 / 2 / 3 (`expected.json`).

## Reproduce
    dotnet run --project dotnet/Fo4Land -c Release -- <Fallout4.esm> export-exterior Commonwealth -55 <y0> 54 <y0+9> <work>\export\band_<y0>_<y0+9>.json   (y0 = -55, -45, ..., 45)
    python scripts/terrain/make_core64c.py select  --work <work> --core C:\Modding\staging\terrain_core64
    python scripts/terrain/make_core64c.py measure --work <work> --fo4-data <FO4 Data> --calibrate <exp2c work>\convert
    python scripts/convert_batch.py --fo4-data <FO4 Data> --staging <work>\convert --content-resources <ContentResources.zip> ^
        --texconv <Texconvx64.exe> --collision-template <template.nif> --starfield-data <Starfield Data> ^
        --cell-json <work>\convert_input.json --types Static,StaticCollection,MovableStatic,Furniture,Door,Activator,Container,MiscItem,Terminal,Flora,Ingestible,Weapon,Ammunition,Armor ^
        --prefix fo4core --max-texture color=1024,normal=512,rough=256,opacity=512 --limit 1000000 --resume
    python scripts/terrain/make_core64c.py stage --work <work> --core C:\Modding\staging\terrain_core64 --out C:\Modding\staging\terrain_core64c --sf-esm <Starfield.esm>
    python scripts/terrain/make_core64c.py check --work <work> --core C:\Modding\staging\terrain_core64 --out C:\Modding\staging\terrain_core64c ^
        --sf-data <Starfield Data> --fo4 <Fallout4.esm> --fo4-data <FO4 Data> --archive2 <Starfield>\Tools\Archive2\Archive2.exe --scratch <scratch folder>
    python -m unittest tests.test_make_core64c tests.test_texture_cap

`<work>` was `C:\Modding\staging\terrain_core64c_work` (export 630 MB, converted files 3.4 GiB; the staged Data tree
hard-links them).
