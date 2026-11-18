# Lane B Lead Verification Cards — Home Planet Arrival & Outer-Ring Lever Walk (`gemini/world-own-space`)

Truth labels used throughout: **`REACHABLE`**, **`TEST-STATION`**, **`RECORDS ONLY`**, **`TOOLING`**, **`NOT BUILT`**.

---

## Card 1 — `W1`–`W4` & `WB1`–`WB3` Home Planet Arrival, Weather/Sky, Outer-Ring FO4 Ground, & Override Walk (`TEST-STATION` / `OWNER TEST`)

- **Scope & Label:**
  - `FO4SFHome.esm` (`12` records in `Starfield.esm`'s canonical `GRUP` order under defaults: `FO4SFHomeGroundDirt01` `LTEX 0x80A` across all `7` biome `LNAM` slots, `FO4SFHomeClearWeather` `WTHR 0x807`, `FO4SFHomeClimate` `CLMT 0x808`, `FO4SFHomeDryWater` `WATR 0x80C`, `4` location chain records `LCTN 0x801..0x804`, `FO4SFHomeBiome` `BIOM 0x806` using smallest-relief `PatternStyleFieldsHillsFieldsFlat`, `FO4SFHomeAtmosphere` `ATMO 0x809`, `1.0 g` `24 h` `15 C` breathable `PNDT 0x805` omitting `SFTR` `FNAM` by default with HUD `FULL = "Earth"` and non-colliding `ANAM = "fo4sf_home_earth"`, and our own star `STDT 0x800`; zero whole-record copies and zero reference to `FO4WG1RedRocket.esm`).
  - `FO4TerrainCore_Home.esm` (`3` records: home `PNDT` `CNAM` registration, `WRLD 0x803` override, `LCTN 0x802` override; all `WB3` inherited-field overrides — `CNAM` climate, `ZNAM` `_NONE` silence music, `NAM3` `FO4SFHomeDryWater`, `NAM4 = -200.0`, `DNAM = (-120.0, -200.0)`, `MNAM` `64 x 64`-cell bounds, `ONAM`, `FULL = "Commonwealth"`, and zeroed `LCTN.DATA` clearing `max_level = 16` — are labelled **`untested`** until Lead's probe, while `FO4TerrainCore.esm` stays untouched).
  - Dual `.biom` maps (`Data/PlanetData/BiomeMaps/fo4sf_home_earth.biom` and `Data/PlanetData/BiomeMaps/fo4sfhome.esm/fo4sf_home_earth.biom`, both labelled `TEST-STATION` under `C9`) + converted Fallout 4 ground `.mat` and `_color`/`_normal`/`_rough` `.dds` maps in `<home-stage>/Data/` (never in Git), installed reversibly via `scripts/planet/home_world_install.py`.
- **Paired Core (`WB3`):** Staged against the **installed `15`-door `FO4TerrainCore.esm`** in `<game-dir>/Data` (plus `--map-markers <game-dir>/Data/FO4SFMapMarkers.esm`). Do not install Card 4's `13`-door `<home-13door-stage>` onto the `15`-door core (`home_world_install.py` verifies the pinned `FO4TerrainCore.esm` SHA-256 and refuses core mismatches).
- **Stage Placeholders:** `<home-stage>` (default installed-core stage), `<wb1-stage>` (`01-ours-clear-temperate`, `02-starfield-control`), `<wb2-stage>` (`01-fo4-ground-flat-nosftr`, `02-fo4-ground-flat-emptysftr`, `03-fo4-ground-hills-control`, `04-no-orbital-meshes-ours-sunp`), and `<fo4-ground-src>` (converted Fallout 4 ground `.dds` folder, outside Git).
- **Disk Space Need:** `~5 MiB` in `<game-dir>/Data` per active swap (`FO4SFHome - Main.ba2` `~4.4 MiB` + `FO4SFHome.esm` + `FO4TerrainCore_Home.esm` + `FO4SFHomeWorld.install.json` + `FO4SFHomeWorld.swap.json`); `~32 MiB` on staging disk across `<home-stage>`, `<wb1-stage>`, and `<wb2-stage>`.
- **Active `Plugins.txt` Load List:** `*FO4Port.esm`, `*FO4TerrainCore.esm` (installed `15`-door core), `*FO4SFMapMarkers.esm` (when kept active and pinned via `--map-markers`), `*FO4SFHome.esm`, `*FO4TerrainCore_Home.esm` (`FO4TerrainCore_Mars.esm` unticked automatically by `home_world_install.py`; any other plugin overriding `FO4TerrainCore.esm:000803` `WRLD`, such as `FO4SFMission.esm`, must be unticked during this raw host-swap probe).

### Offline Stage & Load-Order Precheck (`W3` / `C3` / `WB1`–`WB3`)
Stage the default installed-core pair plus the `WB1` weather/sky and `WB2` ground/shape comparison variants (`make_home_planet.py check` prints every form `BIOM` and `PNDT` point at and confirms zero Starfield climate, weather, or atmosphere under defaults):

```powershell
python scripts/planet/make_home_planet.py stage --data <game-dir>/Data --out <home-stage> --map-markers <game-dir>/Data/FO4SFMapMarkers.esm --ground-source-dir <fo4-ground-src>
python scripts/planet/make_home_planet.py stage-wb1 --data <game-dir>/Data --out <wb1-stage> --map-markers <game-dir>/Data/FO4SFMapMarkers.esm --ground-source-dir <fo4-ground-src>
python scripts/planet/make_home_planet.py stage-wb2 --data <game-dir>/Data --out <wb2-stage> --map-markers <game-dir>/Data/FO4SFMapMarkers.esm --ground-source-dir <fo4-ground-src>
python scripts/planet/make_home_planet.py check --stage <home-stage> --data <game-dir>/Data
```

### Exact Install Command (Game Closed)
`home_world_install.py` refuses `install` and `undo` / `uninstall` while `Starfield.exe` is running, checks `PNDT`, `LCTN`, and `WRLD` overrides across all active FO4SF plugins in `Plugins.txt`, unticks `FO4TerrainCore_Mars.esm`, places `FO4SFHome.esm` and `FO4TerrainCore_Home.esm` after `FO4SFMapMarkers.esm`, and refuses any load list holding both `_Mars` and `_Home`:

```powershell
python scripts/planet/home_world_install.py install --dir <home-stage> --starfield <game-dir>
python scripts/planet/home_world_install.py order --starfield <game-dir>
```

### In-Game Probe Steps (2 Fresh Launches + `WB1`/`WB2` Variant Swaps)
1. **Launch 1:** Load a clean test save, open the developer console, arrive at Red Rocket, wait for the exterior cell to settle, and read the player coordinates to compute `merge_offset = pos_read - spawn_local`:

```console
coc FO4Core_RedRocketSpawn
player.getpos x
player.getpos y
player.getpos z
```

2. Verify persistent references in the Commonwealth (`FO4Core_CommonwealthMapMarkerVault111`, Vault 111 exterior pad anchors, Red Rocket references) loaded on `FO4SFHome.esm`, and verify `WB3`'s `untested` overrides (Commonwealth HUD location name, silent `_NONE` music, dry `-200 m` LOD water, cleared `LCTN` level cap).
3. Walk past the `64`-cell core edge into the procedural ring and inspect our Fallout 4 ground texture (`FO4SFHomeGroundDirt01` via `PlanetData\BiomeMaps\fo4sf_home_earth.biom`) and gentle `38.11 m` `PatternStyleFieldsHillsFieldsFlat` relief.
4. Quit completely, launch fresh (**Launch 2**), repeat step 1, and confirm the same whole-cell `merge_offset` across both launches.
5. **`WB1` & `WB2` Variant Swap Sessions (Game Closed Between Swaps):** Run `undo`, then `install --dir <wb1-stage>/01-ours-clear-temperate` vs `<wb1-stage>/02-starfield-control`, and `<wb2-stage>/01-fo4-ground-flat-nosftr` vs `<wb2-stage>/02-fo4-ground-flat-emptysftr` vs `<wb2-stage>/03-fo4-ground-hills-control`, capturing comparison screenshots at identical time-of-day and coordinates.

### Exact Undo Command (Game Closed)
Close `Starfield.exe` and restore `Data` + `Plugins.txt` (`*FO4TerrainCore_Mars.esm` re-ticked) byte-for-byte:

```powershell
python scripts/planet/home_world_install.py undo --starfield <game-dir>
python scripts/planet/home_world_install.py status --starfield <game-dir>
```

### Expected PASS Output

```text
staged <home-stage>: plugins=['FO4SFHome.esm', 'FO4TerrainCore_Home.esm'], system_id=0x000F04F2, planet_id=1, body_name=fo4sf_home_earth, biome=01000806, levers=[]
staged 2 WB1 variants under <wb1-stage>
staged 4 WB2 variants under <wb2-stage>
check: ok
installed 3 files, plugins ['FO4SFHome.esm', 'FO4TerrainCore_Home.esm']
uninstalled
nothing installed
```

### `OWNER TEST` — `WB1` Weather & Sky Variants (`R8` — Owner Picks from Screenshots; No Variant Is Final)
- **Variant 1 (`<wb1-stage>/01-ours-clear-temperate`, default):** Our own `FO4SFHomeClearWeather` (`WTHR 0x807`) + `FO4SFHomeClimate` (`CLMT 0x808`) + `FO4SFHomeAtmosphere` (`ATMO 0x809`, clear blue O2/N2 Rayleigh/Mie scattering, zero Starfield weather/sky forms).
- **Control (`<wb1-stage>/02-starfield-control`):** Starfield `ClimateUniqueNewAtlantis` + `ATMO_Jemison`.

### `OWNER TEST` — `WB2` Outer-Ring Fallout 4 Ground, Terrain Pattern, & Surface Tree Variants (`R8` — No Variant Is Final)
- **Variant 1 (`<wb2-stage>/01-fo4-ground-flat-nosftr`, default):** Converted Fallout 4 dirt `FO4SFHomeGroundDirt01` (`LTEX 0x80A` in all `7` `LNAM` slots), smallest-relief `PatternStyleFieldsHillsFieldsFlat` (`38.11 m` max span), `PNDT` `SFTR` omitted (`--surface-tree none`).
- **Variant 2 (`<wb2-stage>/02-fo4-ground-flat-emptysftr`):** Same Fallout 4 ground + `38.11 m` pattern, with our empty `FO4SFHomeSurfaceTree` (`SFTR 0x80B`, `--surface-tree ours_empty`).
- **Control (`<wb2-stage>/03-fo4-ground-hills-control`):** Same Fallout 4 ground with Round-1 `PatternStyleHillsRockyFieldsRocky` (`372.61 m` max span) + `EarthSurfaceTree`.
- **Minimalist Variant (`<wb2-stage>/04-no-orbital-meshes-ours-sunp`):** Omits orbital `MODL` unit spheres (`--orbital-meshes none`) and uses standalone `FO4SFHomeSunPreset` (`SUNP 0x80D`, `--sun-preset ours`).

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
- **Mars Planet-Record & Core Replacement Note (`C5`, `C7`, & `WB3`):** When `WB4` runs, `<wb4-core-stage>` (`13`-door `FO4TerrainCore.esm` + `FO4TerrainCore_Mars.esm`, which overrides the whole `MarsPlanetData` `PNDT 0x0003F59A` record) **REPLACES the installed `15`-door Commonwealth core experiment set for that swap session**, and `<wb4-port-stage>` replaces `FO4Port.esm` for that swap session. If testing the `13`-door core on `FO4SFHome.esm` instead of Mars (`WB3`), stage and use the dedicated **`13`-door-core home pair** `<home-13door-stage>` (`--world-plugin-dir <i3-stage>/core`, NOT Card 1's `15`-door `<home-stage>`).
- **Stage Placeholders:** `<i3-stage>/core`, `<i3-stage>/port`, and `<home-13door-stage>` (paired `WB3` home stage against the `13`-door `FO4TerrainCore.esm`, runnable offline today); `<wb4-core-stage>`, `<wb4-port-stage>`, `<batch11-plugin-dir>`, `<batch11-anim-manifest>`, and `<cw-exp-dir>` / `<cw-plugins>` (once Interior Batch 11 and `WB4` are staged).
- **Disk Space Need:** `0 B` installed in `<game-dir>/Data` today (`HELD FOR WB4`); `~5 MiB` on staging disk for `<home-13door-stage>`; `~3.8 GiB` during the future `WB4` swap session (`FO4TerrainCore - Main.ba2` + `FO4TerrainCore.esm` + `FO4TerrainCore_Mars.esm` or `<home-13door-stage>` + `WB4` `FO4Port.esm`).
- **Active `Plugins.txt` Load List (Future `WB4` Session Only):** `*FO4Port.esm`, `*FO4TerrainCore.esm` (`13`-door core), `*FO4TerrainCore_Mars.esm` (or `*FO4SFHome.esm`, `*FO4TerrainCore_Home.esm` from `<home-13door-stage>`), replacing the `15`-door Commonwealth core and base `FO4Port.esm` for that session.

### Runnable Offline Verification Commands (Valid Today on `<i3-stage>` + `<home-13door-stage>` and on `WB4`)

```powershell
python scripts/terrain/make_core64c.py compare-ids --out <i3-stage>/core --against <base-core-stage>
python scripts/terrain/vmad_patch.py check --port <base-port-plugin-dir> --out <i3-stage>/port --core <i3-stage>/core
python scripts/planet/make_home_planet.py stage --data <game-dir>/Data --out <home-13door-stage> --world-plugin-dir <i3-stage>/core --ground-source-dir <fo4-ground-src>
python scripts/planet/make_home_planet.py check --stage <home-13door-stage> --data <game-dir>/Data --world-plugin-dir <i3-stage>/core
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

---

## Card 6 — `WB5` & `WB5b` Staged Commonwealth DLC Reference Override & Two-Way DLC Doors (`TEST-STATION`)

- **Scope & Label (`TEST-STATION`):**
  - `FO4TerrainCore_DLC.esm` (`masters = ['Starfield.esm', 'FO4TerrainCore.esm', 'FO4DLC.esm']`, `TEST-STATION`) staged on top of the **unchanged** `FO4TerrainCore.esm` (`core_unchanged=True`):
    - Places references only: `647` `FO4TerrainCore.esm` `REFR` overrides (`511` DLC core deletions overridden at their exact core FormIDs with `InitiallyDisabled` `0x00000800` and **never** `Deleted` `0x00000020`, plus `136` moved/modified core `REFR`s; `80` identical overrides resolved as no-ops; `18` changed/deleted base-game references absent from `FO4TerrainCore.esm` listed by name in `not_in_core`).
    - Places `6,295` added DLC Commonwealth `REFR`s (`5,659` reusing `FO4TerrainCore.esm` bases, `636` reusing `FO4DLC.esm` bases via its pinned `formids.json` without writing a duplicate base for any model `FO4DLC.esm` holds, `0` override-authored bases on the current manifests, and `909` unconverted/non-model references listed by name in `missing_bases`).
    - Pins `FO4DLC`'s `formids.json` SHA-256 and refuses any `FO4DLC` stage whose `formids.json` hash differs.
  - **`WB5b` Two-Way Commonwealth <-> `FO4DLC.esm` Doors (`R10` — No One-Way Door):**
    - Wires all `3` placed Commonwealth exterior entrances into the `2` `FO4DLC.esm` interiors Fallout 4 enters from the Commonwealth (`DLC06VaultWorkshop` via `003CC5:DLCworkshop03.esm <-> 003CBF:DLCworkshop03.esm` and `003CC6:DLCworkshop03.esm <-> 003CC0:DLCworkshop03.esm`, and `DLC04TransitCenter01` via `00AD1B:DLCNukaWorld.esm <-> 00ADB3:DLCNukaWorld.esm`), plus persistent exterior arrival `XMarker`s (`0x00000400`) in `FO4TerrainCore_DLC.esm` and a **patched copy** of the `FO4DLC.esm` stage (`<fo4dlc-doors-stage>`) via `scripts/terrain/vmad_patch.py` (`120,052 / 120,052` non-door records in `FO4DLC.esm` byte-identical, every other `FO4DLC.esm` FormID unchanged).
- **Required `FO4DLC` Archives (`WB5`):** **This `TEST-STATION` session requires `FO4DLC.esm` and its archives (`FO4DLC - Main.ba2`, `FO4DLC - Textures.ba2`, `FO4DLCTextures2.esm`, `FO4DLCTextures2 - Textures.ba2`, `FO4DLCTextures3.esm`, `FO4DLCTextures3 - Textures.ba2`) installed.** `make_cw_dlc_override.py install` installs them together from `<fo4dlc-doors-stage>` (or swaps `FO4DLC.esm` against a backup if the `FO4DLC` archive set is already in `<game-dir>/Data`) and refuses any install missing the `FO4DLC` archives.
- **Stage Placeholders:** `<cw-dlc-stage>` (`FO4TerrainCore_DLC.esm`, `objects.json`, `formids.json`, `overlays_params.json`, `wb5_report.json`), `<fo4dlc-doors-stage>` (patched `FO4DLC.esm` + hard-linked `FO4DLC` `.ba2` / companion `.esm` files), `<core-stage>` (`folded-v111-exit` core build), `<fo4dlc-stage>` (pinned `fo4dlc-stage/port`), and `<dlc-edits-json>` (`dlc_edits.json`).
- **Disk Space Need:** `~6.65 GiB` in `<game-dir>/Data` when installing `FO4DLC.esm` and its `4` `.ba2` archives fresh from `<fo4dlc-doors-stage>` (hard-linked with zero extra disk allocation when `<fo4dlc-doors-stage>` and `<game-dir>/Data` share an NTFS volume), or `~9.5 MiB` (`FO4TerrainCore_DLC.esm` `0.46 MiB` + `FO4DLC.esm` backup `9.01 MiB`) when the `FO4DLC` archives are already installed.
- **Active `Plugins.txt` Load List:** `*FO4Port.esm`, `*FO4PortTextures2.esm`, `*FO4TerrainCore.esm`, `*FO4DLC.esm`, `*FO4DLCTextures2.esm`, `*FO4DLCTextures3.esm`, `*FO4TerrainCore_DLC.esm`, `*FO4TerrainCore_Mars.esm` (placed after `FO4TerrainCore.esm` and before the world registration plugin; run on the Mars `TEST-STATION` load list with Card 1 undone so `FO4TerrainCore_DLC.esm`'s structural `WRLD` group header does not collide with Card 1's strict single-override `home_world_install.py` check).

### Offline Build & Two-Way Door Check Commands

```powershell
python scripts/terrain/make_cw_dlc_override.py build --edits <dlc-edits-json> --core <core-stage> --dlc <fo4dlc-stage> --fo4-data <fo4-data-dir> --out <cw-dlc-stage> --dlc-doors-out <fo4dlc-doors-stage>
python scripts/terrain/make_cw_dlc_override.py check --out <cw-dlc-stage> --core <core-stage> --dlc <fo4dlc-stage> --dlc-doors-out <fo4dlc-doors-stage>
python scripts/terrain/vmad_patch.py check --port <fo4dlc-stage> --out <fo4dlc-doors-stage> --core <cw-dlc-stage>
```

### Exact Install Command (`TEST-STATION` Session — Game Closed)

```powershell
python scripts/terrain/make_cw_dlc_override.py status --starfield <game-dir>
python scripts/terrain/make_cw_dlc_override.py install --dir <cw-dlc-stage> --dlc-doors <fo4dlc-doors-stage> --starfield <game-dir>
```

### In-Game Two-Way Door Probe (`R8` & `R10`)
With owner release (`R8`), launch `Starfield.exe`, arrive in the Commonwealth via console, and verify both outbound entry and return exit (`R10`: no one-way door) at the Nuka-World Transit Centre (`[-2798.8, -2442.0, 96.4]` merged) and the two Vault 88 entrances (`[-916.0, -3545.1, 16.2]` and `[-1335.7, -3541.3, 17.1]` merged):

```console
coc FO4Core_RedRocketSpawn
player.getpos x
player.getpos y
player.getpos z
```

### Exact Undo Command (Game Closed)

```powershell
python scripts/terrain/make_cw_dlc_override.py uninstall --starfield <game-dir>
```

### Expected PASS Output

```text
CHECK PASS
wb5 check: ok (core_resolved=727, not_in_core=18, added_placed=6295, missing_refs=909, wb5b_doors=3)
installed wb5 session: added=8, plugins=['FO4DLC.esm', 'FO4DLCTextures2.esm', 'FO4DLCTextures3.esm', 'FO4TerrainCore_DLC.esm']
uninstalled wb5 session: removed=8, restored_fo4dlc=False
```
