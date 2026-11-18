# Lane B Lead Verification Cards — Home Planet Arrival & Outer-Ring Lever Walk (`gemini/world-own-space`)

Truth labels used throughout: **`REACHABLE`**, **`TEST-STATION`**, **`RECORDS ONLY`**, **`TOOLING`**, **`NOT BUILT`**.

---

## Card 1 — `W1`–`W4` Home Planet Swap Session & Merge-Offset Measurement (`TEST-STATION`)

**Scope & Label:** `FO4SFHome.esm` (`7` records: our own star `STDT`, `4` location chain records `system -> planet -> orbit -> surface`, `1.0 g` `24 h` `15 C` breathable `PNDT` `"Earth"`, and our own no-life `FO4SFHomeBiome` `BIOM`, written field-by-field from `home_planet_spec.py` with zero whole-record copies) + `FO4TerrainCore_Home.esm` (`3` records: home `PNDT` `CNAM` registration, `WRLD 0x803` override, `LCTN 0x802` override) + dual `.biom` maps (`Data/PlanetData/BiomeMaps/earth.biom` and `Data/PlanetData/BiomeMaps/fo4sfhome.esm/earth.biom`), installed reversibly via `scripts/planet/home_world_install.py`.

### Load-Order Precheck (`W3` Single-Override Rule)
- `check_no_duplicate_overrides` enforces that no second active plugin overrides our home `PNDT` or `FO4Core_CommonwealthLocation` (`FO4TerrainCore.esm:000802`).
- **Important note on current set:** Today's `FO4SFMapMarkers.esm` also overrides `FO4TerrainCore.esm:000802` (with `PNAM = SSol_PMars_Surface`), and both `FO4SFMapMarkers.esm` and `FO4SFMission.esm` carry `WRLD 0x803` group headers (`SNAM=0, PNAM=4`). For the swap probe, `home_world_install.py` places `FO4TerrainCore_Home.esm` **after** `FO4SFMapMarkers.esm` and `FO4SFMission.esm` (or unticks `FO4SFMapMarkers.esm` during the raw host-offset check); post-rebase (`W5`/`W7`), `LCSR` moves into the single host registration plugin.
- `home_world_install.py` unticks `FO4TerrainCore_Mars.esm`, refuses any load list holding both `_Mars` and `_Home`, writes its own `FO4SFHomeWorld.install.json` + `FO4SFHomeWorld.swap.json` without touching `FO4SFExp.install.json`, and restores `Data` + `Plugins.txt` byte-for-byte on `undo`.

### Swap-Session Steps (2 Fresh Launches, Game Closed for Install / Undo)
1. Run `python scripts/planet/home_world_install.py install --stage <home-stage> --starfield <game-dir>`.
2. **Launch 1:** Load a clean test save, run `coc FO4Core_RedRocketSpawn` (or `coc FO4Core_Vault111Ext`), wait for the exterior cell to settle, read `player.getpos`, and compute `merge_offset = pos_read - spawn_local`.
3. Verify persistent references in the Commonwealth (`FO4Core_CommonwealthMapMarkerVault111`, Vault 111 exterior pad anchors, Red Rocket references) loaded on the home planet.
4. Walk past the 64-cell core edge into the procedural ring and inspect the ground (`FO4SFHomeBiome` `LDirtFootprints01` via `PlanetData\BiomeMaps\earth.biom` vs probe run 1's `FrozenLife07` icy fallback).
5. Quit completely, launch fresh (**Launch 2**), repeat step 2, and confirm the same whole-cell `merge_offset` across both launches.
6. Close the game and run `python scripts/planet/home_world_install.py undo --starfield <game-dir>`, verifying receipt restoration.

### Pass Criteria & Owner Test Judgments
- **Technical PASS:**
  - Both fresh launches produce the same whole-cell `merge_offset` (to be recorded for post-rebase `W5`).
  - Core persistent references load in the Commonwealth on `FO4SFHome.esm` (resolving probe run 2's `T1`–`T7` question).
  - HUD planet name reads `Earth` (`1.0 g`, `15 C`, breathable `O2`, no Sol planets or locations in system).
- **OWNER TEST (Visual):**
  - Sky look under default `ATMO_Jemison` (`0x0000C010`) vs optional `ATMO_Earth` (`0x0000C9D1`) screenshot comparison.
  - Ground past the 64-cell edge is plain neutral dirt (`LDirtFootprints01`, zero Starfield flora/fauna/rocks/ice).

---

## Card 2 — `WL1` Outer-Ring Starfield Content Lever Walk (`TEST-STATION`)

**Scope & Label:** Seven staged `FO4TerrainCore_Home.esm` variants (`00-baseline`, `01-PCM_OverlayExclusionZone`, `02-PCM_OverlayExclusionZone_HumanLocations`, `03-LocTypeNoPCMScanTreeContent`, `04-LocTypeNoPCMCreatureContent`, `05-LocTypeSENotAllowed`, `06-all5`), each verified offline by `sf_location_census.py`.

### Steps
1. On `00-baseline`, hop outward in `<= 180 m` steps from the NW (`Sanctuary`) and S (`Concord`) core edges into the ring between cell `32` and the `100`-cell landing boundary, recording any procedural Starfield POI, creature, or ship encounter.
2. Swap in single-keyword variants `01`–`05` (and `06-all5`) to isolate which keyword suppresses any observed bleed-through.

---

## Card 3 — `WD2` & `WD3` Staged Far Harbor and Nuka-World Terrain & Sea Probes (`TEST-STATION`)

**Scope & Label:** Terrain-only overlay worlds built from parameterized `make_cw_overlays.py` + `dotnet/Fo4Land --master`, registered both on Mars (`FO4WorldFarHarbor_Mars.esm`, `FO4WorldNukaWorld_Mars.esm`) and together in the single 3-world `W3` registration plugin (`FO4TerrainCore_Home.esm` listing `Commonwealth`, `FarHarbor`, and `NukaWorld` `>= 2,000` planet cells apart, with `FO4TerrainCore.esm` SHA-256 unchanged):
- **Far Harbor (`FO4WorldFarHarbor.esm`):** `34 x 34` cells (`1,156` exterior cells), heights `-22.49..117.34 m`, sea water `6.43 m` (`HasWater` + `XCLW` inherit), `8` FO4 `LAND` probes `<= 0.037 m` error, nearest other world `3,563.1` planet cells (`>= 2,000`).
- **Nuka-World (`FO4WorldNukaWorld.esm`):** `40 x 40` cells (`1,600` exterior cells covering all `4,225` FO4 `LAND` cells), heights `-0.40..212.62 m`, water `4.64 m`, `8` FO4 `LAND` probes `<= 0.088 m` error, nearest other world `4,583.1` planet cells (`>= 2,000`).

### Swap-Session Steps
1. Swap-install `FO4WorldFarHarbor.esm` (and then `FO4WorldNukaWorld.esm`) alongside its registration plugin with pre/post install receipts.
2. Arrive via `coc FO4FH_FarHarborSpawn` / `coc FO4NW_NukaWorldSpawn`, read `player.getpos`, and compute each world's own `merge_offset = pos_read - spawn_local`.
3. Hop `<= 180 m` across the `plan.json` height probe points and verify terrain heights within `<= 0.5 m` and coastal water surface visibility at the sea/lake edge.
4. Roll back and verify receipts.

---

## Card 4 — `I3` Start-Path 13 Exterior Doors Walk (`TEST-STATION` -> `REACHABLE` After Swap Walk)

**Scope & Label:** Core door delta promoting `13` existing placed exterior door references in place (`ConcordMuseum01`: `01D22F`, `01AC07`, `029AD8`; `ConcordCivicAccess01`: `04C3E0`, `04C3DE`, `02C9A5`; `ConcordFactory`: `0E3DAD`, `0E3DAB`, `0E3DA1`; `ConcordSpeakeasy`: `07895F`, `07895D`, `07895C`; `SanctuaryBasementJahani`: `0A36EB`) alongside the `15` kept doors (`28` total).
- **Offline Proof:** `make_core64c.py compare-ids` confirms `0` existing FormIDs changed (`683,857 / 683,857` non-door records byte-identical; only `13` arrival markers + `3` door `ACTI` bases appended after lights); `vmad_patch.py check` passes `88/88` checks across all `28` doors.

### Console-Free Steps
1. Swap-install the `I3` core + animated-door batch (`interiors_b11` / patched `28`-door port) with receipts.
2. Walk from Sanctuary to the Sanctuary root cellar (`SanctuaryBasementJahani`), press `E` to enter, open `3` containers, and exit through the same door.
3. Walk to Concord, press `E` on the Museum of Freedom front door (`ConcordMuseum01`), walk the ground floor, open `3` containers, and walk back out the front door.
4. Run `python scripts/bridge/door_rounds.py judge` on the `FO4SF_LoadDoor` log (`0` `retry gave up` lines).

---

## Card 5 — `WG1` 29 x 29 Red Rocket Ground-Texture Window (`TEST-STATION` / `OWNER TEST`)

**Scope & Label:** Staged test world (`FO4WG1RedRocket.esm` + `.btd` + `40` `Terrain1Layer.mat` materials + converted `_color`/`_normal`/`_rough` `.dds` maps) mapping Fallout 4's `40` most-used `LTEX` land textures across the `29 x 29`-cell Red Rocket window.
- **Offline Proof:** Decoded `.btd` carries `41` `LTEX` entries (`> 1`) and matches Fallout 4's dominant land texture across **`3,134 / 3,364` quadrants (`93.16% >= 90%`)**.
- **OWNER TEST:** With owner release (`R8`), swap-install the Red Rocket ground window so the owner can inspect the ground-texture blending and roughness look directly before expanding across the full Commonwealth (`NEXT`).
