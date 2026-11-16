# Pip-Boy `MAP` Replacement — Slices 1–4 Architecture & PC Cards

## Scope and Stacking Base

This document covers **Slices 1–4** of the Pip-Boy `MAP` ladder, stacked on the Pip-Boy heading/grid branch (`#762`) and Fallout 4 shell rebuild branch (`#764`):

1. **Slice 1 (`MapKey` Open & Vanilla Map Suppression):** Pressing `MapKey` (`0x4D` = `M`) opens `FO4SF_PipboyMenu` directly on `MAP` (`DataObj.CurrentPage = 3`, `CurrentTab = 0`) and closes any open menu in `MapMenus` (`GalaxyStarMapMenu`) via `UI::IsMenuOpen` + `UIMessageQueue::AddMessage(..., kHide)`.
2. **Slice 2 (Commonwealth World Map Texture):** Stage-time tool `scripts/ui/pipboy_map_store.py` decodes the player's local BC1 `WorldMap_d.dds` (`2048 x 2048`) into a 1-frame SWF v12 component (`Components/FO4SF_WorldMap.swf`), rewrites `"img://WorldMap"` in the staged `Pipboy_MapPage.swf` constant pool, and completes the `RegisterMap` -> `onMapTexturesLoaded()` handshake.
3. **Slice 3 (Marker Store, Live Player Arrow, & 24-Bit Discovery State):** `pipboy_map.cpp` checks `ASMovieRootBase::CreateObject` (vtable slot `0x2E`) inside `Starfield.exe`, mutates `DataObj`'s getter-only `WorldMapNW/NE/SWCorner` `Point`s and `WorldMapMarkers` `Array` in-place (`SetMember("length", 0)` + `Invoke("push", ...)` + `RemoveAllMapMarkers = true`), projects live player coordinates `(x_sf + 1200) * 70`, `(y_sf + 2700) * 70` and compass yaw `+0x88` onto `PlayerLocMarker` (`type = 86`), supports custom waypoints (`type = 85`), and reads 24-bit discovery bitsets from `FO4SF_MapDisc00..13`.
4. **Slice 4 (Fast Travel to a Discovered Marker):** Answers direct unguarded `BGSCodeObj` methods `CheckHardcoreModeFastTravel` (returning `Boolean`) and `RefreshMapMarkers`, stages `Components/PipboyMessageBox.swf` for confirmation prompts, writes target FormID and arrival coordinates to `FO4SFPipboyTravel.esm` `TESGlobal`s at `+0x48` with read-back verification, and dispatches `FO4SF_PipboyTravel.Go` (`0` arguments, slot `0x2F`).

> [!IMPORTANT]
> **Prerequisite Gate (`S1-c3`):** All four PC cards below use the Fallout 4 `PipboyMenu.swf` shell route (`Stage=2`, `Movie=`, `CodeObj=1`, `CodeObjAt=Menu_mc`). Run **Card S1-c3** (verifying `Menu_mc.InvalidateData` draws a page body without faulting once required component movies are staged) before executing Slices 1–4 in game. With `Map=0` (shipped default in `FO4SFPipboyMenu.ini`), all `PipboyMap` code is inert.

---

## Key Safety & Engine Contracts

- **Zero New Unchecked `REL::ID` Lookups on `GFx::Value`:** `WorldMapMarkers` is cleared and populated exclusively through `SetMember("length", 0)` and `Invoke("push", ...)` — using only the five `GFx::Value::ObjectInterface` functions already verified against SFSE 0.2.21 RVAs.
- **`RemoveAllMapMarkers = true` on Marker Array Rebuild:** `Pipboy_MapPage` never assigns `markerId` onto instantiated `MovieClip` children, so `RemovedMapMarkerIds` alone leaks old sprites; setting `RemoveAllMapMarkers = true` during full rebuild clears `MarkerHolder_mc` cleanly.
- **24-Bit Cap per `TESGlobal`:** Because `TESGlobal` stores `float32` at `+0x48`, each `FO4SF_MapDisc00..13` global holds **24** marker bits (`14 * 24 = 336 >= 315` Commonwealth markers) with zero IEEE-754 mantissa rounding loss.
- **Reversible Staging Without Installer Conflicts:** Rewriting `"img://WorldMap"` -> `"Components/FO4SF_WorldMap.swf"` and `"PipboyMessageBox.swf"` -> `"Components/PipboyMessageBox.swf"` lets both files pack through `pipboy_probe_install.py --component-movie` with zero changes to `pipboy_probe_install.py` and zero shadowing of root `Interface/*.swf` files.

---

## PC Session Cards (One Launch Each After `S1-c3` PASS)

### PC Card — Slice 1: Map Key Opens Pip-Boy `MAP` & Suppresses `GalaxyStarMapMenu`

- **Prerequisite:** `S1-c3` PASS, explicit owner game-launch release.
- **Stage (game closed):**
  1. Build `FO4SFPipboyMenu.dll` via `sfse/FO4SFPipboyMenu/build.ps1 -Out <build_dir> -Env <msvc_env_ps1>` and copy `FO4SFPipboyMenu.dll` + `FO4SFPipboyMenu.ini` beside `versionlib-1-16-244-0.bin` in `<game_dir>/Data/SFSE/Plugins/`.
  2. Stage the shell (`FO4SF_Fo4Shell.swf`) and `Pipboy_MapPage.swf` with `make_pipboy_probe.py stage <stage_dir>` and `pipboy_probe_install.py install --dir <stage_dir> --extra-movie FO4SF_Fo4Shell --page-movie Pipboy_MapPage --starfield <game_dir>` (plus any component clips required by `S1-c3`).
  3. In `FO4SFPipboyMenu.ini`, set:
     - `Stage=2`, `Movie=FO4SF_Fo4Shell`, `Key=0x76`, `Pause=1`, `Flags=0x19`
     - `CodeObj=1`, `CodeObjHide=1`, `CodeObjAt=Menu_mc`, `CodeObjPages=1`
     - `CodeObjCalls=Menu_mc.onCodeObjCreate`, `CodeObjLateCalls=Menu_mc.InvalidateData`
     - `CodeObjNames=PlaySound,HideMenu,onNewPage,onNewTab,RegisterMap,UnregisterMap,CenterMarkerRequest,CheckHardcoreModeFastTravel,RefreshMapMarkers,FastTravel,SetPlayerMarker,ClearPlayerMarker,onModalOpen,onSwitchBetweenWorldLocalMap,PlaySmallTransition`
     - `Map=1`, `MapKey=0x4D`, `MapPage=3`, `MapMenus=GalaxyStarMapMenu`
- **In-Game Steps:**
  1. Load an exterior save and press `M` (`0x4D`) once; wait 3 seconds.
  2. Record whether `FO4SF_PipboyMenu` opened on the `MAP` tab and whether Starfield's `GalaxyStarMapMenu` closed immediately.
  3. Press `M` again to close `FO4SF_PipboyMenu`, then quit cleanly.
- **PASS Criteria:**
  - `FO4SFPipboyMenu.log` shows `step=map_config map_key=0x4d map_page=3 menus=GalaxyStarMapMenu`, `step=map_key n=1 vk=0x4d ... page=3 sent=show`, `step=code_answer ... page=3 ... page_now=#3`, `step=map_register ok=1`, and (if `GalaxyStarMapMenu` opened) `step=map_suppress ... name=GalaxyStarMapMenu sent=hide`.
  - No crash or hang; second `M` press logs `sent=hide`.

---

### PC Card — Slice 2: Commonwealth World Texture Renders in `WorldMapHolder_mc`

- **Prerequisite:** Slice 1 PASS, explicit owner game-launch release.
- **Stage (game closed):**
  1. Extract the player's own `Textures/Interface/Pip-Boy/WorldMap_d.dds` and `Interface/Pipboy_MapPage.swf` into a private scratch folder outside the repository.
  2. Generate the texture wrapper SWF and patch the staged map page:
     - `python scripts/ui/pipboy_map_store.py stage-worldmap --dds <scratch>/WorldMap_d.dds --out <stage_dir>/Data/Interface/Components/FO4SF_WorldMap.swf`
     - `python scripts/ui/pipboy_map_store.py patch-mappage --src <scratch>/Pipboy_MapPage.swf --out <stage_dir>/Data/Interface/Pipboy_MapPage.swf --msgbox-url ""`
  3. Re-install the probe archive with `--component-movie Components/FO4SF_WorldMap`.
- **In-Game Steps:**
  1. Load the exterior Commonwealth save and press `M`.
  2. Pan and zoom the map with the mouse wheel / drag for 5 seconds, then close with `M` and quit.
- **PASS Criteria:**
  - `FO4SFPipboyMenu.log` shows `step=map_textures_loaded called=1` followed by `step=map_texture loaded=1 children=1`.
  - Owner recorder shows the 2048x2048 Commonwealth world map framed inside `WorldMapMask_mc` with smooth pan/zoom and no crash.

---

### PC Card — Slice 3: Map Markers, Discovered State, & Live Player Heading Arrow

- **Prerequisite:** Slice 2 PASS, explicit owner game-launch release.
- **Stage (game closed):**
  1. Build `FO4SFPipboyTravel.esm` via `python scripts/ui/pipboy_map_store.py stage-travel-esm --out <stage_travel>/FO4SFPipboyTravel.esm` and copy `FO4SFPipboyMapMarkers.tsv` beside `FO4SFPipboyMenu.dll` (`MapStore=FO4SFPipboyMapMarkers.tsv`).
  2. Activate `FO4SFPipboyTravel.esm` in the test load order.
- **In-Game Steps:**
  1. Load the exterior Commonwealth save near Vault 111 / Sanctuary, face North (`0` deg), press `M`, and hover over a discovered marker and an undiscovered marker.
  2. Close with `M`, turn ~90 deg East, press `M` again, and verify the `PlayerLocMarker` arrow rotated to ~90 deg and centered on the player.
- **PASS Criteria:**
  - `FO4SFPipboyMenu.log` shows `step=map_store file=FO4SFPipboyMapMarkers.tsv status=loaded markers=...`, `step=map_root ... create_object=0x...`, `step=map_markers n=... discovered=... undiscovered=... corners_set=3/3 read_back=match`, and `step=map_center idx=... called=1`.
  - Owner recorder shows icons at canonical Commonwealth landmarks (Vault 111, Sanctuary, Concord) with distinct Discovered vs Undiscovered frames and accurate live player arrow heading.

---

### PC Card — Slice 4: Fast Travel to a Discovered Marker (`PipboyMessageBox` -> `FO4SF_PipboyTravel.Go`)

- **Prerequisite:** Slice 3 PASS, explicit owner game-launch release.
- **Stage (game closed):**
  1. Copy the player's `PipboyMessageBox.swf` to `<stage_dir>/Data/Interface/Components/PipboyMessageBox.swf`, re-run `patch-mappage` with default `--msgbox-url Components/PipboyMessageBox.swf`, and pack `--component-movie Components/FO4SF_WorldMap --component-movie Components/PipboyMessageBox`.
  2. Compile `scripts/mapmarkers/FO4SF_PipboyTravel.psc` to `<stage_travel>/Data/Scripts/FO4SF_PipboyTravel.pex` and pack with `FO4SFPipboyTravel.esm`.
  3. Verify `MapSurvival=0` in `FO4SFPipboyMenu.ini`.
- **In-Game Steps:**
  1. Stand outdoors in the Commonwealth away from Sanctuary / Red Rocket, press `M`, click an undiscovered marker first (verify fast travel is refused and custom waypoint is offered), then click a discovered marker and confirm in `PipboyMessageBox`.
  2. Wait for the loading fade to complete, observe player arrival and `GameHour` advance, then test `MapSurvival=1` (or `FO4SF_SurvivalMode = 1`) to confirm Survival mode blocks fast travel cleanly.
- **PASS Criteria:**
  - `FO4SFPipboyMenu.log` shows `step=map_check_hardcore ... allow=1`, `step=map_modal open=1`, `step=map_fast_travel_req idx=...`, and `step=map_fast_travel idx=... global_set=1 read_back=match call=FO4SF_PipboyTravel.Go queued=1`.
  - `FO4SF_PipboyTravel.0.log` shows `step=go idx=... result=...` with arrival coordinates matching the marker's merged arrival point and companions warped alongside the player.
  - Rollback: run `pipboy_probe_install.py uninstall --starfield <game_dir>` and restore `Map=0` / `Stage=0` in `FO4SFPipboyMenu.ini`.
