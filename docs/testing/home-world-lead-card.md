# Lane B Lead Verification Cards — Home Planet Arrival & Outer-Ring Lever Walk (`gemini/world-own-space`)

Truth labels used throughout: **`REACHABLE`**, **`TEST-STATION`**, **`RECORDS ONLY`**, **`TOOLING`**, **`NOT BUILT`**.

---

## Card 1 — `W1`–`W4` Home Planet Swap Session & Merge-Offset Measurement (`TEST-STATION`)

- **Scope & Label:** `FO4SFHome.esm` (`7` records: our own star `STDT`, `4` location chain records `system -> planet -> orbit -> surface`, `1.0 g` `24 h` `15 C` breathable `PNDT` with HUD `FULL = "Earth"` and non-colliding internal body `ANAM = "fo4sf_home_earth"`, and our own `"no-life, Starfield-patterned"` `FO4SFHomeBiome` `BIOM`, written field-by-field from `home_planet_spec.py` with zero whole-record copies; Starfield climate, sky, terrain pattern, surface tree, and ground texture remain Starfield references until `WB1`–`WB3` land) + `FO4TerrainCore_Home.esm` (`3` records: home `PNDT` `CNAM` registration, `WRLD 0x803` override, `LCTN 0x802` override) + dual `.biom` maps (`Data/PlanetData/BiomeMaps/fo4sf_home_earth.biom` and `Data/PlanetData/BiomeMaps/fo4sfhome.esm/fo4sf_home_earth.biom`, both labelled `TEST-STATION` under `C9` so vanilla `earth.biom` can never collide), installed reversibly via `scripts/planet/home_world_install.py`.
- **Stage Placeholder:** `<home-stage>` (outside Git worktrees and game folders).
- **Disk Space Need:** `~2 MiB` in `<game-dir>/Data` (`FO4SFHome - Main.ba2` `~1.3 MiB` + `FO4SFHome.esm` + `FO4TerrainCore_Home.esm` + `FO4SFHomeWorld.install.json` + `FO4SFHomeWorld.swap.json`).
- **Active `Plugins.txt` Load List:** `*FO4Port.esm`, `*FO4TerrainCore.esm`, `*FO4SFMapMarkers.esm` (when kept active and pinned via `--map-markers`), `*FO4SFHome.esm`, `*FO4TerrainCore_Home.esm` (`FO4TerrainCore_Mars.esm` unticked automatically by `home_world_install.py`; any other plugin overriding `FO4TerrainCore.esm:000803` `WRLD`, such as `FO4SFMission.esm`, must be unticked during this raw host-swap probe).

### Offline Stage & Load-Order Precheck (`W3` / `C3` Single-Override Rule)
Stage against `<game-dir>/Data` (passing `--map-markers <game-dir>/Data/FO4SFMapMarkers.esm` when `FO4SFMapMarkers.esm` stays active so `FO4TerrainCore_Home.esm` adds `FO4SFMapMarkers.esm` as a master, merges all `312` `LCSR` rows into `FO4Core_CommonwealthLocation`, and pins `map_markers_sha256` in `plan.json`):

```powershell
python scripts/planet/make_home_planet.py stage --data <game-dir>/Data --out <home-stage> --map-markers <game-dir>/Data/FO4SFMapMarkers.esm
python scripts/planet/make_home_planet.py check --stage <home-stage> --data <game-dir>/Data
```

### Exact Install Command (Game Closed)
`home_world_install.py` refuses `install` and `undo` / `uninstall` while `Starfield.exe` is running, checks `PNDT`, `LCTN`, and `WRLD` overrides across all active FO4SF plugins in `Plugins.txt`, unticks `FO4TerrainCore_Mars.esm`, places `FO4SFHome.esm` and `FO4TerrainCore_Home.esm` after `FO4SFMapMarkers.esm`, and refuses any load list holding both `_Mars` and `_Home`:

```powershell
python scripts/planet/home_world_install.py install --dir <home-stage> --starfield <game-dir>
python scripts/planet/home_world_install.py order --starfield <game-dir>
```

### In-Game Probe Steps (2 Fresh Launches)
1. **Launch 1:** Load a clean test save, open the developer console, arrive at Red Rocket, wait for the exterior cell to settle, and read the player coordinates to compute `merge_offset = pos_read - spawn_local`:

```console
coc FO4Core_RedRocketSpawn
player.getpos x
player.getpos y
player.getpos z
```

2. Verify persistent references in the Commonwealth (`FO4Core_CommonwealthMapMarkerVault111`, Vault 111 exterior pad anchors, Red Rocket references) loaded on `FO4SFHome.esm`.
3. Walk past the `64`-cell core edge into the procedural ring and inspect the ground (`FO4SFHomeBiome` `"no-life, Starfield-patterned"` `LDirtFootprints01` via `PlanetData\BiomeMaps\fo4sf_home_earth.biom` vs probe run 1's `FrozenLife07` icy fallback).
4. Quit completely, launch fresh (**Launch 2**), repeat step 1, and confirm the same whole-cell `merge_offset` across both launches.

### Exact Undo Command (Game Closed)
Close `Starfield.exe` and restore `Data` + `Plugins.txt` (`*FO4TerrainCore_Mars.esm` re-ticked) byte-for-byte:

```powershell
python scripts/planet/home_world_install.py undo --starfield <game-dir>
python scripts/planet/home_world_install.py status --starfield <game-dir>
```

### Expected PASS Output & Owner Judgments

```text
staged <home-stage>: plugins=['FO4SFHome.esm', 'FO4TerrainCore_Home.esm'], system_id=0x000F04F2, planet_id=1, body_name=fo4sf_home_earth, biome=01000806, levers=[]
check: ok
installed 3 files, plugins ['FO4SFHome.esm', 'FO4TerrainCore_Home.esm']
uninstalled
nothing installed
```

- **Technical PASS:** Both fresh launches produce the same whole-cell `merge_offset`; core persistent references load in the Commonwealth on `FO4SFHome.esm`; HUD planet name reads `Earth` (`1.0 g`, `15 C`, breathable `O2`, zero Sol planets or locations in system).
- **OWNER TEST (Visual, `R8`):** Sky look under default `ATMO_Jemison` vs optional `--sky ATMO_Earth`, and plain neutral dirt (`LDirtFootprints01`, zero Starfield flora/fauna/rocks/ice) past the `64`-cell edge.

---

## Card 2 — `WL1` Outer-Ring Starfield Content Lever Walk (`TEST-STATION`)

- **Scope & Label:** Seven staged `FO4TerrainCore_Home.esm` variants (`00-baseline`, `01-PCM_OverlayExclusionZone`, `02-PCM_OverlayExclusionZone_HumanLocations`, `03-LocTypeNoPCMScanTreeContent`, `04-LocTypeNoPCMCreatureContent`, `05-LocTypeSENotAllowed`, `06-all5`), each verified offline by `sf_location_census.py` and `make_home_planet.py check`.
- **Stage Placeholder:** `<wl1-stage>` (with per-variant subfolders `<wl1-stage>/00-baseline` .. `<wl1-stage>/06-all5`).
- **Disk Space Need:** `~10 MiB` on staging disk (`7` variants x `~1.3 MiB`); `~2 MiB` in `<game-dir>/Data` for whichever single variant is installed at a time.
- **Active `Plugins.txt` Load List (per variant swap):** `*FO4Port.esm`, `*FO4TerrainCore.esm`, `*FO4SFMapMarkers.esm` (when pinned via `--map-markers`), `*FO4SFHome.esm`, `*FO4TerrainCore_Home.esm` (`FO4TerrainCore_Mars.esm` unticked).

### Offline Stage & Check Commands

```powershell
python scripts/planet/make_home_planet.py stage-wl1 --data <game-dir>/Data --out <wl1-stage> --map-markers <game-dir>/Data/FO4SFMapMarkers.esm
python scripts/planet/make_home_planet.py check --stage <wl1-stage>/00-baseline --data <game-dir>/Data
```

### Exact Install Command (Per Variant, Game Closed)

```powershell
python scripts/planet/home_world_install.py install --dir <wl1-stage>/00-baseline --starfield <game-dir>
python scripts/planet/home_world_install.py order --starfield <game-dir>
```

### In-Game Probe Steps
1. Arrive via console on `00-baseline` and hop outward in `<= 180 m` steps from the NW (`Sanctuary`) and S (`Concord`) core edges into the ring between cell `32` and the `100`-cell landing boundary, recording any procedural Starfield POI, creature, scan tree, or ship encounter:

```console
coc FO4Core_RedRocketSpawn
```

2. Close `Starfield.exe`, run `undo`, and repeat `install --dir <wl1-stage>/<variant>` across `01-PCM_OverlayExclusionZone` through `06-all5` to isolate which keyword suppresses any observed bleed-through.

### Exact Undo Command (Game Closed)

```powershell
python scripts/planet/home_world_install.py undo --starfield <game-dir>
python scripts/planet/home_world_install.py status --starfield <game-dir>
```

### Expected PASS Output

```text
staged 7 WL1 variants under <wl1-stage>
check: ok
installed 3 files, plugins ['FO4SFHome.esm', 'FO4TerrainCore_Home.esm']
uninstalled
nothing installed
```

---

## Card 3 — `WD2` & `WD3` Staged Far Harbor and Nuka-World Terrain & Sea Probes (`TEST-STATION`, Console Only)

- **Scope & Label (`C11` — `TEST-STATION`, Console Only):** Terrain-only overlay worlds built from parameterized `make_cw_overlays.py` + `dotnet/Fo4Land --master` + `src/fo4sf/terrain/overlay_postpatch.py`. Each plugin currently holds `3` persistent `REFR`s (`XMarker` anchor, `COCMarkerHeading`, `1` `MapMarker`), `0` placed exterior objects, `0` ship landing markers, `0` load doors, and unwired Pip-Boy travel codes (`pipboy_plugin_code = 5` and `6` are reserved in `world_registry.json`; `FO4SF_PipboyTravel.psc` handles `1..4` only today). Both worlds are reachable **strictly via developer console** (`coc FO4FH_FarHarborSpawn` and `coc FO4NW_NukaWorldSpawn`), and coastal sea-water rendering (`WRLD.DNAM`, `SFBK.WHGT`, `CELL.XCLW`) is unproven in game until this probe:
  - **Far Harbor (`FO4WorldFarHarbor.esm`):** `34 x 34` cells (`1,156` exterior cells), heights `-22.49..117.34 m`, sea water `6.43 m`, `8` FO4 `LAND` probes `<= 0.037 m` error. Separation from Commonwealth (`(0.3, -1.2)` rad): **`3,563.1` cells (`356.31 km`, `79.18` `±45`-cell / `±4.5 km` landing-area half-widths)** on Mars radius (`3,390.0 km` `FNAM`; `3,562.6` cells at `3,389.5 km`) and **`6,696.4` cells (`669.64 km`, `148.81` `±45`-cell landing-area half-widths)** on the Home planet's Earth radius (`6,371.0 km`).
  - **Nuka-World (`FO4WorldNukaWorld.esm`):** `40 x 40` cells (`1,600` exterior cells covering all `4,225` FO4 `LAND` cells), heights `-0.40..212.62 m`, water `4.64 m`, `8` FO4 `LAND` probes `<= 0.088 m` error. Separation from Commonwealth: **`4,583.1` cells (`458.31 km`, `101.85` `±45`-cell landing-area half-widths)** on Mars radius (`3,390.0 km` `FNAM`; `4,582.4` cells at `3,389.5 km`) and **`8,613.3` cells (`861.33 km`, `191.41` `±45`-cell landing-area half-widths)** on the Home planet's Earth radius (`6,371.0 km`).
- **Mars Planet-Record Replacement Warning (`C5` & `C7`):** Every `*_Mars.esm` plugin (`FO4WorldFarHarbor_Mars.esm`, `FO4WorldNukaWorld_Mars.esm`, `FO4TerrainCore_Mars.esm`) overrides the **entire** `MarsPlanetData` (`PNDT 0x0003F59A`) record (`CNAM` master worldspaces), and `Data/FO4SFExp.install.json` owns one active `exp_install.py` experiment at a time. Installing a Mars test world therefore **REPLACES the Commonwealth experiment set (`FO4TerrainCore.esm` + `FO4TerrainCore_Mars.esm`) for that swap session** (`FO4Port.esm` stays untouched). To keep Commonwealth active beside Far Harbor and Nuka-World instead, register all three worlds together through the single `FO4TerrainCore_Home.esm` registration plugin (`make_home_planet.py stage --worlds Commonwealth,FarHarbor,NukaWorld --world-plugin-dir <dlc-world-esms>`).
- **Stage Placeholders:** `<fh-stage>` (`FO4WorldFarHarbor.esm` + `FO4WorldFarHarbor_Mars.esm` + `Data/`), `<nw-stage>` (`FO4WorldNukaWorld.esm` + `FO4WorldNukaWorld_Mars.esm` + `Data/`), and `<cw-exp-dir>` / `<cw-plugins>` recorded from `exp_install.py status` before the swap.
- **Disk Space Need:** `~26 MiB` in `<game-dir>/Data` for Far Harbor (`FO4WorldFarHarbor - Main.ba2` `24.9 MiB` + `2` `.esm`s); `~54 MiB` in `<game-dir>/Data` for Nuka-World (`FO4WorldNukaWorld - Main.ba2` `52.9 MiB` + `2` `.esm`s).
- **Active `Plugins.txt` Load List:**
  - Far Harbor Mars swap session: `*FO4Port.esm`, `*FO4WorldFarHarbor.esm`, `*FO4WorldFarHarbor_Mars.esm` (Commonwealth experiment uninstalled for the swap session).
  - Nuka-World Mars swap session: `*FO4Port.esm`, `*FO4WorldNukaWorld.esm`, `*FO4WorldNukaWorld_Mars.esm` (Commonwealth experiment uninstalled for the swap session).

### Offline Verification Commands

```powershell
python src/fo4sf/terrain/overlay_postpatch.py verify --stage-dir <fh-stage> --fo4 <fo4-data>/DLCCoast.esm --fo4-masters <fo4-data>/Fallout4.esm --fo4-world DLC03FarHarbor
python src/fo4sf/terrain/overlay_postpatch.py verify --stage-dir <nw-stage> --fo4 <fo4-data>/DLCNukaWorld.esm --fo4-masters <fo4-data>/Fallout4.esm --fo4-world NukaWorld
```

### Exact Install Commands (Mars Swap Session — Game Closed)
Record `<cw-exp-dir>` and `<cw-plugins>` from the active Commonwealth experiment receipt, uninstall the Commonwealth experiment cleanly, and install Far Harbor (then repeat for Nuka-World):

```powershell
python scripts/game/exp_install.py status --starfield <game-dir>
python scripts/game/exp_install.py uninstall --starfield <game-dir>
python scripts/game/exp_install.py install --exp-dir <fh-stage> --starfield <game-dir> --pack --plugins FO4WorldFarHarbor.esm,FO4WorldFarHarbor_Mars.esm
python scripts/game/exp_install.py order --starfield <game-dir>
```

Swap from Far Harbor to Nuka-World (game closed):

```powershell
python scripts/game/exp_install.py uninstall --starfield <game-dir>
python scripts/game/exp_install.py install --exp-dir <nw-stage> --starfield <game-dir> --pack --plugins FO4WorldNukaWorld.esm,FO4WorldNukaWorld_Mars.esm
python scripts/game/exp_install.py order --starfield <game-dir>
```

### In-Game Probe Steps (Console Only)
1. In the Far Harbor session, arrive via console, read `player.getpos` to compute `merge_offset = pos_read - spawn_local`, hop `<= 180 m` across the `plan.json` height probe points (`<= 0.5 m` tolerance), and inspect coastal sea-water rendering at `6.43 m`:

```console
coc FO4FH_FarHarborSpawn
player.getpos x
player.getpos y
player.getpos z
```

2. In the Nuka-World session, arrive via console, compute `merge_offset`, verify `plan.json` terrain heights (`<= 0.5 m`), and inspect water rendering at `4.64 m`:

```console
coc FO4NW_NukaWorldSpawn
player.getpos x
player.getpos y
player.getpos z
```

### Exact Undo Commands Restoring Commonwealth (Game Closed)

```powershell
python scripts/game/exp_install.py uninstall --starfield <game-dir>
python scripts/game/exp_install.py install --exp-dir <cw-exp-dir> --starfield <game-dir> --pack --plugins <cw-plugins>
python scripts/game/exp_install.py order --starfield <game-dir>
```

### Expected PASS Output

```text
"reachability": "TEST-STATION (coc only)"
"water_exterior_cells_verified": 1156
"water_exterior_cells_verified": 1600
installed 3 files, plugins ['FO4WorldFarHarbor.esm', 'FO4WorldFarHarbor_Mars.esm']
installed 3 files, plugins ['FO4WorldNukaWorld.esm', 'FO4WorldNukaWorld_Mars.esm']
uninstalled
```

---

## Card 4 — `I3` Start-Path 13 Exterior Doors Walk (`HELD FOR WB4` — Do NOT Install Round-1 `I3` Port)

- **Scope & Hold Gate (`C6` — `HELD FOR WB4`):** Core door delta (`<i3-stage>/core`) promotes `13` existing placed exterior door references in place (`ConcordMuseum01`: `01D22F`, `01AC07`, `029AD8`; `ConcordCivicAccess01`: `04C3E0`, `04C3DE`, `02C9A5`; `ConcordFactory`: `0E3DAD`, `0E3DAB`, `0E3DA1`; `ConcordSpeakeasy`: `07895F`, `07895D`, `07895C`; `SanctuaryBasementJahani`: `0A36EB`) alongside the `15` kept doors (`28` total), keeping every existing `FO4TerrainCore.esm` FormID unchanged. **DO NOT INSTALL `<i3-stage>/port` from Round 1:** it was built on un-animated `interiors_b10` (`28` plain `FO4SF_LoadDoor`, `0` `FO4SF_AnimatedLoadDoor`; `interiors_b11` did not exist yet) and installing it would overwrite the owner's installed animated doors (`FO4SF_AnimatedLoadDoor`). Live swap-install is **HELD FOR `WB4`**, which rebuilds the `28`-door port on top of Lead's Interior Batch 11 `plugin` folder with `--keep-markers <i3-stage>/port/doors.json`, `--allow-new-doors`, and `--animated-doors <batch11-anim-manifest>`.
- **Mars Planet-Record & Core Replacement Note (`C5` & `C7`):** When `WB4` runs, `<wb4-core-stage>` (`13`-door `FO4TerrainCore.esm` + `FO4TerrainCore_Mars.esm`, which overrides the whole `MarsPlanetData` `PNDT 0x0003F59A` record) **REPLACES the installed Commonwealth core experiment set for that swap session**, and `<wb4-port-stage>` replaces `FO4Port.esm` for that swap session.
- **Stage Placeholders:** `<i3-stage>/core` and `<i3-stage>/port` (offline checks today); `<wb4-core-stage>`, `<wb4-port-stage>`, `<batch11-plugin-dir>`, `<batch11-anim-manifest>`, and `<cw-exp-dir>` / `<cw-plugins>` (once Interior Batch 11 and `WB4` are staged).
- **Disk Space Need:** `0 B` installed in `<game-dir>/Data` today (`HELD FOR WB4`); `~3.8 GiB` during the future `WB4` swap session (`FO4TerrainCore - Main.ba2` + `FO4TerrainCore.esm` + `FO4TerrainCore_Mars.esm` + `WB4` `FO4Port.esm`).
- **Active `Plugins.txt` Load List (Future `WB4` Session Only):** `*FO4Port.esm`, `*FO4TerrainCore.esm`, `*FO4TerrainCore_Mars.esm` (replacing the `15`-door Commonwealth core and base `FO4Port.esm` for that session).

### Runnable Offline Verification Commands (Valid Today on `<i3-stage>` and on `WB4`)

```powershell
python scripts/terrain/make_core64c.py compare-ids --out <i3-stage>/core --against <base-core-stage>
python scripts/terrain/vmad_patch.py check --port <base-port-plugin-dir> --out <i3-stage>/port --core <i3-stage>/core
```

### `WB4` Rebuild, Install, Judge, and Undo Commands (Run Only After Interior Batch 11 Lands)
Rebuild the `28`-door port on Batch 11's un-patched `plugin` folder preserving marker FormIDs `074CD3..074CDF` and animated door scripts:

```powershell
python scripts/terrain/vmad_patch.py port --port <batch11-plugin-dir> --core <i3-stage>/core --out <wb4-port-stage> --keep-markers <i3-stage>/port/doors.json --allow-new-doors --animated-doors <batch11-anim-manifest>
python scripts/terrain/vmad_patch.py check --port <batch11-plugin-dir> --out <wb4-port-stage> --core <i3-stage>/core
```

Future `WB4` swap-install (game closed, after recording `<cw-exp-dir>` / `<cw-plugins>` and `<prev-port-batch>`):

```powershell
python scripts/game/exp_install.py status --starfield <game-dir>
python scripts/game/exp_install.py uninstall --starfield <game-dir>
python scripts/game/exp_install.py install --exp-dir <i3-stage>/core --starfield <game-dir> --pack --plugins FO4TerrainCore.esm,FO4TerrainCore_Mars.esm
python scripts/deploy_starfield.py install --batch <wb4-batch-stage> --other-core --starfield <game-dir>
python scripts/game/exp_install.py order --starfield <game-dir>
python scripts/bridge/door_rounds.py judge --queue <door-queue>
```

### Exact Undo Commands for Future `WB4` Session (Game Closed)

```powershell
python scripts/deploy_starfield.py install --batch <prev-port-batch> --other-core --starfield <game-dir>
python scripts/game/exp_install.py uninstall --starfield <game-dir>
python scripts/game/exp_install.py install --exp-dir <cw-exp-dir> --starfield <game-dir> --pack --plugins <cw-plugins>
python scripts/game/exp_install.py order --starfield <game-dir>
```

### Expected PASS Output

```text
  bases        identical
  containers   identical
  lights       identical
CHECK PASS
PASS 56, FAIL 0, INCONCLUSIVE 0, NOT_RUN 0; <door-queue>/door_rounds_judge.json
```

---

## Card 5 — `WG1` 29 x 29 Red Rocket Ground-Texture Window (`TEST-STATION` / `OWNER TEST`)

- **Scope & Label:** Staged test world (`FO4WG1RedRocket.esm` + `FO4WG1RedRocket_Mars.esm` + `Data/Terrain/FO4WG1_Commonwealth.btd` + `40` `Terrain1Layer.mat` materials + `120` converted BC7/BC5/BC4 `_color`/`_normal`/`_rough` `.dds` maps) mapping Fallout 4's `40` most-used `LTEX` land textures across the `29 x 29`-cell Red Rocket window (`41` `LTEX` entries in `.btd`, matching Fallout 4's dominant land texture across `3,134 / 3,364 = 93.16% >= 90%` of quadrants).
- **Mars Planet-Record Replacement Warning (`C5` & `C7`):** `FO4WG1RedRocket_Mars.esm` overrides the **entire** `MarsPlanetData` (`PNDT 0x0003F59A`) record (`CNAM` registered at `(0.3, -1.2)` rad, the Commonwealth's spot), and `Data/FO4SFExp.install.json` owns one active `exp_install.py` experiment at a time. Installing `FO4WG1RedRocket.esm` + `FO4WG1RedRocket_Mars.esm` therefore **REPLACES the Commonwealth experiment set (`FO4TerrainCore.esm` + `FO4TerrainCore_Mars.esm`) for that swap session** (`FO4Port.esm` stays untouched).
- **Stage Placeholder:** `<wg1-stage>` (`FO4WG1RedRocket.esm`, `FO4WG1RedRocket_Mars.esm`, `wg1_ltex_manifest.json`, `Data/`), plus `<cw-exp-dir>` / `<cw-plugins>` recorded from `exp_install.py status` before the swap.
- **Disk Space Need:** `~118 MiB` in `<game-dir>/Data` (`FO4WG1RedRocket - Main.ba2` `115.5 MiB` + `FO4WG1RedRocket.esm` `45 KB` + `FO4WG1RedRocket_Mars.esm` `7 KB`).
- **Active `Plugins.txt` Load List:** `*FO4Port.esm`, `*FO4WG1RedRocket.esm`, `*FO4WG1RedRocket_Mars.esm` (Commonwealth experiment uninstalled for the swap session).

### Offline Check Command

```powershell
python scripts/terrain/make_wg1_redrocket.py check --out <wg1-stage>
```

### Exact Install Commands (Mars Swap Session — Game Closed)

```powershell
python scripts/game/exp_install.py status --starfield <game-dir>
python scripts/game/exp_install.py uninstall --starfield <game-dir>
python scripts/game/exp_install.py install --exp-dir <wg1-stage> --starfield <game-dir> --pack --plugins FO4WG1RedRocket.esm,FO4WG1RedRocket_Mars.esm
python scripts/game/exp_install.py order --starfield <game-dir>
```

### In-Game Probe & Owner Test (`R8`)
With owner release (`R8`), launch `Starfield.exe`, arrive at the Red Rocket `29 x 29` window via console, and capture screenshots of road asphalt, dirt shoulder, grass transitions, and specular/roughness response for owner visual judgement before expanding `LTEX` mapping across the `64 x 64` Commonwealth (`NEXT`):

```console
coc FO4WG1_RedRocketSpawn
player.getpos x
player.getpos y
player.getpos z
```

### Exact Undo Commands Restoring Commonwealth (Game Closed)

```powershell
python scripts/game/exp_install.py uninstall --starfield <game-dir>
python scripts/game/exp_install.py install --exp-dir <cw-exp-dir> --starfield <game-dir> --pack --plugins <cw-plugins>
python scripts/game/exp_install.py order --starfield <game-dir>
```

### Expected PASS Output

```text
"step": "WG1"
"plugin_ltex_records": 40
"btd_ltex_table_size": 41
"pass": true
installed 3 files, plugins ['FO4WG1RedRocket.esm', 'FO4WG1RedRocket_Mars.esm']
uninstalled
```
