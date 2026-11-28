# Earth Lore Placement Plan, Host Routes, and `WRLD` EDID Reconciliation

- **Scope:** Round 14 Task 3 (`#858`, `gemini/r13-w2-whome`) — design & migration plan **only**.
- **Invariant preserved this round:** **Do NOT move the Commonwealth** (`[0.3, -1.2]` rad, measured merge offset `[-1200.0, -2700.0]` m). Track 1 runs (`2g-fix4`/`fix5`/`fix6`, Vault 111 -> Sanctuary -> Concord -> Mission -> Workshop) rely on the measured `(-1200.0, -2700.0)` offset.

---

## 1. Real-World Placement Coordinates (Earth, `R = 6371.0 km`)

All `PNDT CNAM` entries store `[latitude_rad, longitude_rad]` (`lat = deg * pi / 180`, `lon = deg * pi / 180`).
Great-circle surface distance on Earth (`R = 6,371,000 m`, `1 Starfield cell = 100 m`, playable landing half-width `= 45 cells = 4,500 m`):

| Region (`world_registry.json` key) | Real City Anchor | Target Latitude / Longitude (deg) | Target `PNDT CNAM` `[lat, lon]` (rad) | Status in Round 14 | Distance from Current CW `[0.3, -1.2]` | Distance from Lore Boston `[0.739323216, -1.240211768]` |
|---|---|---|---|---|---|---|
| **Commonwealth** | Boston, MA (`42.3601°N, 71.0589°W`) | `+42.3601, -71.0589` | `[0.739323216, -1.240211768]` | **PROPOSED (held until Track 1 sign-off)** | `28,074.6` cells (`~2,807 km`) | `0` cells |
| **CapitalWasteland** | Washington, DC (`38.9000°N, 77.0400°W`) | `+38.9000, -77.0400` | `[0.678933079, -1.344601656]` | **TEST-ONLY** (`world_registry.json` filled) | `25,444.8` cells (`~2,544 km`) | `6,343.9` cells (`~634 km`) |
| **MojaveWasteland** | Las Vegas, NV (`36.1700°N, 115.1400°W`) | `+36.1700, -115.1400` | `[0.631285591, -2.009572091]` | **TEST-ONLY** (`world_registry.json` filled) | `50,101.3` cells (`~5,010 km`) | `38,132.2` cells (`~3,813 km`) |

- **Separation check:** Every pair among `{current CW [0.3, -1.2], lore Boston, DC, Las Vegas}` is separated by at least `6,343.9` cells (`> 140x` the `45`-cell landing half-width), and DC <-> Las Vegas is `33,488.1` cells (`~3,349 km`). Thus no overlay landing rectangle overlaps.
- **Note on Commonwealth `[0.3, -1.2]` today:** `(0.3 rad, -1.2 rad)` equals `(17.19°N, 68.75°W)` in the Caribbean Sea (inherited from `exp2b` on Mars). Moving Commonwealth to real Boston is strictly deferred until owner sign-off after Track 1.

---

## 2. Host Routes for New Worlds (`FO3`/`FNV` Pilots) & `WRLD` EDID Reconciliation

### 2.1 Supported Host Routes on `#858` (Both Kept Stable)

Claude's Round 14 `CapitalWasteland` and `MojaveWasteland` pilots (`FO4CapitalWasteland.esm`, `FO4Mojave.esm`) were built with `overlays_params.json` `host = None` (`masters = ["Starfield.esm"]`). Both host routes on `main` / `#858` remain stable and supported:

1. **`#858` Registry Registration Route (`make_home_planet.py stage` -> `FO4SFHome.esm` + `FO4TerrainCore_Home.esm`):**
   - **Recommended for multi-world testing on one Earth.** `FO4CapitalWasteland.esm` and `FO4Mojave.esm` stay **untouched** (`masters = ["Starfield.esm"]` only; `host = None`).
   - `build_home_registration` reads `CapitalWasteland` / `MojaveWasteland` from `src/fo4sf/core/world_registry.json`, adds each plugin to `FO4TerrainCore_Home.esm`'s masters, appends its `[lat, lon, WRLD]` `CNAM` entry into the shared single `FO4SF_EarthPlanetData` (`PNDT 0x000805:FO4SFHome.esm`) override, and emits `WRLD`, `LCTN` (`PNAM` -> `FO4SFHome.esm:000804` `SFO4SFHome_PEarth_Surface`), and `SFBK` remaps into `FO4TerrainCore_Home.esm` (with `Starfield.esm` FormIDs left unchanged).
   - Command: `python scripts/planet/make_home_planet.py stage --data <Data> --out <dir> --worlds Commonwealth,CapitalWasteland,MojaveWasteland --world-plugin-dir <pilot-dir>`.
2. **`TerrainOverlays` Direct `host` Object Route (`dotnet/TerrainOverlays/Program.cs` / `tests/test_terrain_overlays_host.py`):**
   - Kept backward-compatible unchanged. Useful when building a single standalone world against an existing `FO4SFHome.esm` (`host.planet_plugin = "FO4SFHome.esm"`, `planet_edid = "FO4SF_EarthPlanetData"`, `surface_location = "000804:FO4SFHome.esm"`, `biome = "000806:FO4SFHome.esm"`, `registration_plugin = "<World>_Home.esm"`; legacy `--control-b7dc7f52` / synthetic fixtures use `"EarthPlanetData"`).
   - **Constraint:** Never load two separate `*_Home.esm` registration plugins that both override `FO4SFHome.esm:000805` (`FO4SF_EarthPlanetData`); for simultaneous multi-world Earth runs, always combine worlds in Route 1 (`FO4TerrainCore_Home.esm`).

### 2.2 `WRLD` EditorID Reconciliation (`world_edid` vs Pilot EditorIDs)

- `src/fo4sf/core/world_registry.json` historically reserved `FO4CW_CapitalWasteland` (`CapitalWasteland`) and `FO4NV_MojaveWasteland` (`MojaveWasteland`), whereas Claude's offline pilots use `FO3Core_CapitalWasteland` and `FNVCore_Mojave`.
- **Reconciliation implemented in `#858`:** `src/fo4sf/planet/home_planet_spec.py` defines `WORLD_EDID_ALIASES`:
  - `CapitalWasteland`: accepts both `"FO4CW_CapitalWasteland"` and `"FO3Core_CapitalWasteland"`.
  - `MojaveWasteland`: accepts both `"FO4NV_MojaveWasteland"` and `"FNVCore_Mojave"`.
- Pilot plugins **do not need to be rebuilt or renamed** before next-round testing; whichever single matching `WRLD` EditorID exists in `FO4CapitalWasteland.esm` / `FO4Mojave.esm` is resolved cleanly. Long-term naming alignment can happen if/when both masters are rebuilt for multi-region integration.

---

## 3. Exhaustive Inventory of Files Pinning Commonwealth Coordinates `(0.3, -1.2)` / Merge Offset `(-1200.0, -2700.0)`

Every source file in this repository that hardcodes the Commonwealth Mars registration `(0.3, -1.2)` rad or its measured runtime merge offset `(-1200.0, -2700.0)` m (`planet_target_cell = [-12, -27]`):

### 3.1 Registry, Overlay Builders & Core Terrain
- `src/fo4sf/core/world_registry.json` (`Commonwealth.planned_starfield_world`: `planet_position = [0.3, -1.2]`, `measured_merge_offset = [-1200.0, -2700.0]`)
- `src/fo4sf/overlay_grid.py` (`WORLD01_LATLON`, `exp2b` `(-12, -27)` reference comments)
- `scripts/terrain/make_cw_overlays.py` (`EXP2B_LATLON = (0.3, -1.2)`)
- `scripts/terrain/make_core64c.py` (`CORE64_OFFSET = (-1200.0, -2700.0)`)
- `scripts/terrain/vmad_patch.py` (`MERGE_MEASURED = (-1200.0, -2700.0, 0.0)`)
- `scripts/terrain/a3_path_places.py` (`MERGE_OFFSET = (-1200.0, -2700.0, 0.0)`)
- `scripts/slice/make_redrocket_door.py` (`LAST_OFFSET = (-1200.0, -2699.8, 0.01)`)

### 3.2 Native C# Writers (`.NET 9`)
- `dotnet/NewGame/Program.cs` (`MergeX = -1200f, MergeY = -2700f`)
- `dotnet/Mission/Program.cs` (`MergeOffsetX = -1200.0f, MergeOffsetY = -2700.0f`)
- `dotnet/Mission/NextStoryMissionsA4.cs` (`MergeOffsetX`, `MergeOffsetY`, Sanctuary merged coords)
- `dotnet/Mission/NextStoryMissionsA7.cs` (merged Commonwealth comments & coords for Park St, Vault 114, Diamond City)
- `dotnet/FortHagen/Program.cs` (`MergeOffsetX = -1200f, MergeOffsetY = -2700f`)
- `dotnet/InteractiveFidelity/OverlayBuilder.cs` (overlay documentation & verification comments)

### 3.3 Papyrus Quests & Runtime Helpers
- `scripts/newgame/FO4SF_NewGameQuest.psc` (`MergeOffsetX = -1200.0, MergeOffsetY = -2700.0`)
- `scripts/newgame/walk_headings.py` (`MERGE_OFFSET_X = -1200.0, MERGE_OFFSET_Y = -2700.0`)
- `scripts/mapmarkers/FO4SF_MapMarkers.psc` (`MergeOffsetX = -1200.0, MergeOffsetY = -2700.0`)
- `scripts/mapmarkers/FO4SF_MarkerProbeQuest.psc` (`MergeX = -1200.0, MergeY = -2700.0`)
- `scripts/mission/FO4SF_Min00Quest.psc` (`MergeOffsetX`, `MergeOffsetY`)
- `scripts/mission/FO4SF_Codsworth01Quest.psc` (`MergeOffsetX`, `MergeOffsetY`)
- `scripts/mission/FO4SF_Sanctuary01Quest.psc` (`MergeOffsetX`, `MergeOffsetY`)
- `scripts/mission/FO4SF_MinRecruit00Quest.psc` (`MergeOffsetX`, `MergeOffsetY`)
- `scripts/mission/FO4SF_MQ103Quest.psc` through `FO4SF_MQ206Quest.psc` (`FO4SF_MQ103Quest.psc`, `FO4SF_MQ104Quest.psc`, `FO4SF_MQ105Quest.psc`, `FO4SF_MQ106Quest.psc`, `FO4SF_MQ203Quest.psc`, `FO4SF_MQ204Quest.psc`, `FO4SF_MQ206Quest.psc` — each pins `MergeOffsetX/Y = -1200.0 / -2700.0`)
- `scripts/alife/FO4SF_ALifeControllerQuest.psc`, `scripts/alife/make_alife.py`, `scripts/alife/nw_subgraph.json`
- `scripts/bridge/door_probe.py`, `scripts/bridge/FO4SF_Probe.psc`, `scripts/game/bridge_log.py`
- `scripts/ui/pipboy_map_store.py` (`MERGE_OFFSET_X = -1200.0, MERGE_OFFSET_Y = -2700.0`)

---

## 4. Risk to Track 1 & Phased Migration Order

### 4.1 Why Moving Commonwealth Right Now Would Break Track 1
1. **Unmeasured landing merge offset at `[0.739323216, -1.240211768]`:** The `(-1200.0, -2700.0)` m constant was empirically measured in-game at `[0.3, -1.2]` on Mars. Moving Commonwealth to Boston coordinates on Earth changes the planet-grid cell where Starfield mounts the `64x64` overlay. Until a height-probe / arrival check measures the Boston cell offset in game, hardcoded `-1200 / -2700` across `20+` C#/Papyrus/JSON modules would misplace:
   - Vault 111 surface exit & Sanctuary/Concord mission NPCs (`NewGame`, `Mission`, `Min00`, `Codsworth01`, `Sanctuary01`, `MQ103+`),
   - All `15` exterior <-> interior return `FO4SF_LoadDoor` VMAD coordinates (`vmad_patch.MERGE_MEASURED`),
   - All `FO4SFMapMarkers` / landing spot triggers and `Border` extent bounds (`MinX/MaxX/MinY/MaxY`),
   - A-Life patrol nodes (`nw_subgraph.json`) and Pip-Boy map coordinate transforms.
2. **Double-offset save persistence risk:** Existing in-game throwaway saves hold moved persistent markers at old merged positions. Re-basing offsets requires a clean new game once Track 1 signs off.

### 4.2 Recommended Execution Order (After Owner Approves Lore Pass)
1. **Stage & measure at Boston `[0.739323216, -1.240211768]` on Earth first:** Run a height/arrival probe on `#858` (keeping `-1200, -2700` unchanged on Track 1 bundles) to record the exact empirical `measured_merge_offset` for Boston on `FO4SFHomePlanet`.
2. **Centralize offset reads where feasible:** Derive `MergeOffsetX/Y` and `MapMarkers` `MinX/MaxX/MinY/MaxY` from `world_registry.json` (`planned_starfield_world.measured_merge_offset`) in Python/C# generators (`make_cw_overlays.py`, `vmad_patch.py`, `NewGame`, `Mission`, `FortHagen`, `MapMarkers`, `ALife`, `pipboy_map_store.py`) and quest properties so `(-1200, -2700)` stops being hand-duplicated across `20+` files.
3. **Update `world_registry.json` & re-patch `FO4Port.esm`:** Update Commonwealth `planet_position` & `measured_merge_offset`, regenerate `FO4Port.esm` door return VMADs (`vmad_patch.py`), rebuild mission/newgame/mapmarker plugins in lockstep, and verify offline before one clean New Game smoke run.

---

## 5. Multi-World Border Switch (`FO4SF_MapMarkers.psc`, Design Behind Opt-In Toggle)

- `scripts/mapmarkers/FO4SF_MapMarkers.psc` adds `bool Property BorderRegisteredEarthWorlds = False Auto` (default `False` to preserve existing Mars/`FO4TerrainCore.esm`-only runs and `test_sfse_border.py` / `test_map_markers_plugin.py` contracts byte-for-byte).
- When `BorderRegisteredEarthWorlds = True`, `IsRegisteredEarthWorldCell(Cell c)` resolves the cell's owning plugin index (`c.GetFormID() / 16777216`) against loaded registered Earth-world plugins from `world_registry.json` (`FO4TerrainCore.esm`, `FO4WorldFarHarbor.esm`, `FO4WorldNukaWorld.esm`, `FO4CapitalWasteland.esm`, `FO4Mojave.esm`) using `Game.GetFormFromFile` / `GetModByName`-free FormID prefix lookup on a known `0x000803`/`0x000802`/`0x000801` worldspace/location anchor, treating any active registered FO4SF Earth world identically to `core` inside `Border(Actor player)` without emitting extra `"border="` log lines.
