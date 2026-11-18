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
