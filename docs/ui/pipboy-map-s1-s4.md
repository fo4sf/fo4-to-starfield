# Pip-Boy `MAP` Replacement — Slices 1–4 Architecture & PC Cards

## Scope and Stacking Base

This document covers **Slices 1–4** of the Pip-Boy `MAP` ladder, stacked on the Fallout 4 shell rebuild branch (`#764`):

1. **Slice 1 (`MapKey` Open & Complete Starfield Star-Map Block):** Pressing `MapKey` (`0x4D` = `M`) opens `FO4SF_PipboyMenu` directly on `MAP` (`DataObj.CurrentPage = 3`, `CurrentTab = 0`). Starfield's star map (`GalaxyStarMapMenu` / `MapMenus`) is **blocked completely** (`MapBlockStarMap=1`): its creator in `UI::menuMap` is replaced with `BlockedStarMapCreate` so nothing (`M`, `G`, `DataMenu`, `MonocleMenu`, console, or scripts) can instantiate it; while `FO4SF_PipboyMenu` is open, `BSInputEventUser` (`MenuShouldHandleEvent` / `MenuOnButtonEvent`) swallows `MapKey` and map user events (`kStop`), and fallback suppression (`SuppressVanillaMapMenus`) sends `kHide` without ever reopening `FO4SF_PipboyMenu` (preventing any close-then-reopen bounce loop).
2. **Slice 2 (Commonwealth World Map Texture):** Stage-time tool `scripts/ui/pipboy_map_store.py` decodes the player's local BC1 `WorldMap_d.dds` (`2048 x 2048`) into a 1-frame SWF v12 component (`Components/FO4SF_WorldMap.swf`), rewrites `"img://WorldMap"` in the staged `Pipboy_MapPage.swf` constant pool, and completes the `RegisterMap` -> `onMapTexturesLoaded()` handshake.
3. **Slice 3 (Marker Store CLI, Live Engine Discovery Sync, & Configurable Offsets — *unverified in game until Slices 1–2 pass*):** `pipboy_map_store.py build-store` builds `FO4SFPipboyMapMarkers.tsv` directly from `FO4TerrainCore.esm` (`plugin_code=1`) and optional `FO4SFMapMarkers.esm` (`plugin_code=0`), clamping location icons to `0..80` (`< 85`). At runtime, `CheckCreateObjectSlot` in `pipboy_map.cpp` checks **only** that vtable slot `0x2E` points inside the `Starfield.exe` module image (`InImage`) — it does **not** verify that slot `0x2E` is `ASMovieRootBase::CreateObject`. When enabled, it mutates `DataObj`'s getter-only `WorldMapNW/NE/SWCorner` `Point`s and `WorldMapMarkers` `Array` in-place, reads live engine `ExtraMapMarker` `kDiscovered` (`0x20`, set by `ObjectReference.SetMarkerDiscovered()`) via `ExtraDataList::GetExtraMapMarker` (`REL::ID 44761`) and syncs newly discovered bits into `FO4SF_MapDisc00..13` (`TESGlobal` value offset verified by `ChooseGlobalSlot`), and projects live player coordinates and configurable compass yaw (`MapHeadingAt` / `[Kit] HeadingAt`) onto `PlayerLocMarker` (`type = 86`).
4. **Slice 4 (Fast Travel & Multi-World Travel Bridge — *gated on Slice 3 in-game verification*):** Answers direct unguarded `BGSCodeObj` methods `CheckHardcoreModeFastTravel` (returning `Boolean`) and `RefreshMapMarkers`, stages `Components/PipboyMessageBox.swf` for confirmation prompts, writes target FormID, `pluginCode`, store index, and arrival coordinates to `FO4SFPipboyTravel.esm` `TESGlobal`s with read-back verification, and dispatches `FO4SF_PipboyTravel.Go` (`0` arguments, slot `0x2F`), where native C++ and Papyrus gate travel on the exact same `FO4SF_MapDisc00..13` discovery bitset.

> [!IMPORTANT]
> **Verification Status & Claim Scoping (`NOT_RUN` in Game):**
> - **Prerequisite Gate (`S1-c3`):** All four PC cards below use the Fallout 4 `PipboyMenu.swf` shell route (`Stage=2`, `Movie=`, `CodeObj=1`, `CodeObjAt=Menu_mc`). Run **Card S1-c3** first. With `Map=0` (shipped default in `FO4SFPipboyMenu.ini`), all `PipboyMap` code is inert.
> - **Slices 1–2 (`MapKey` + Star-Map Block + World Texture) are testable first.**
> - **Do NOT claim Slices 3–4 are verified** until real in-game marker discovery (`ExtraMapMarker` `+0x18` bit `0x20` -> `FO4SF_MapDisc00..13`) and the rendered `WorldMapMarkers` list (`CreateObject` slot `0x2E`) are observed and verified on the PC.

---

## Complete Starfield Star-Map Block & Multi-World Travel

Per the owner's decision (16 Nov), **the player never sees Starfield's surface, planet, or star map (`GalaxyStarMapMenu`), and all intra-world and inter-world travel goes through the Pip-Boy `MAP`**:

1. **Three-Layer Star-Map Lockout (`Map=1`, `MapBlockStarMap=1`):**
   - **Creator Replacement (`UI::menuMap`):** On `PipboyMap::Start` (main thread after `PostDataLoad`), every menu in `MapMenus` (`GalaxyStarMapMenu`) has its `UIMenuEntry::initFunc` verified inside `Starfield.exe` and replaced with `BlockedStarMapCreate`, which constructs an empty `Scaleform::Ptr<IMenu>` (`step=starmap_blocked route=create`). Opening the star map from `M`, scanner `G` (`MonocleMenu`), `DataMenu`, console, or quest script cannot instantiate the menu or load `GalaxyStarMapMenu.swf`.
   - **Open-Menu Input Swallow (`BSInputEventUser`):** When `FO4SF_PipboyMenu` is open, `MenuShouldHandleEvent` / `MenuOnButtonEvent` claims `MapKey` (`0x4D`) and user events `Map`, `SurfaceMap`, `PlanetMap`, `GalaxyMap`, and `StarMap`, marking them `InputEvent::Status::kStop` (`step=map_input ... swallowed=1`), debouncing until key release (`value == 0`), and closing `FO4SF_PipboyMenu` cleanly (or switching from another Pip-Boy tab to `MAP`).
   - **One-Way Fallback Hide (`SuppressVanillaMapMenus`):** `OnMovieCreated` and `Tick` send `kHide` if any `MapMenus` entry ever reports open, and **never** send `kShow` to `FO4SF_PipboyMenu`, while `Tick` polls `GetAsyncKeyState(MapKey)` only when `!g_menuOpen` outside a 350 ms transition cooldown — eliminating any `M`-key close-then-reopen loop.
2. **Travel to Other Worlds Without the Star Map:**
   - Each ported game's world (Commonwealth `plugin_code = 0/1`, Capital Wasteland `2`, Mojave `3`, Appalachia `4`) is a standalone worldspace/planet master with persistent arrival `XMarkerHeading` / `MapMarker` references.
   - Selecting a cross-world transit marker (train station, vertibird pad, border gate, or future world-selector tab) on the Pip-Boy `MAP` writes its `pluginCode` (`>= 2`), `localId`, and arrival coordinates into `FO4SFPipboyTravel.esm` and dispatches `FO4SF_PipboyTravel.Go`.
   - `FO4SF_PipboyTravel.Go` fades out (`FadeOutGame`), advances `GameHour` / `GameDaysPassed`, calls `player.MoveTo(dest)` + `WaitFor3DLoad()` across worldspaces (creating a normal Fallout loading transition with zero star-map UI), teleports active `SQ_Followers` companions alongside the player, marks arrival discovered in both engine `ExtraMapMarker` and `FO4SF_MapDisc00..13`, and fades in.

---

## Key Safety, Discovery, & Configurable Engine Contracts

- **Zero New Unchecked `REL::ID` Lookups on `GFx::Value`; Honest `CheckCreateObjectSlot` Scope:** `WorldMapMarkers` is cleared and populated exclusively through `SetMember("length", 0)` and `Invoke("push", ...)`. Before calling `ASMovieRootBase::CreateObject` (vtable slot `0x2E`), `CheckCreateObjectSlot` checks **only** that the vtable and slot `0x2E` lie inside the `Starfield.exe` module image (`InImage`) — it does **not** prove that slot `0x2E` is `CreateObject` (which remains an in-game Slice 3 check).
- **Live Engine Discovery Agreement (C++ <-> Papyrus):** In `Starfield.exe` `1.16.244`, `ObjectReference.SetMarkerDiscovered()` (`REL::ID 118457`, RVA `0x2080440`) calls `ExtraDataList::GetExtraMapMarker` (`REL::ID 44761`, RVA `0x50A840`) on `[refr + 0xC8]` and sets bit `0x20` at `[ExtraMapMarker + 0x18]` (whereas `FNAM` bits `0x01`/`0x02` are already `1` on undiscovered markers in `FO4SFMapMarkers.esm`). `CollectMainThreadState` reads `[ExtraMapMarker + 0x18] & 0x20` (with `TESObjectREFR@@` and `ExtraMapMarker@@` RTTI checks) and writes newly discovered bits into `FO4SF_MapDisc00..13` before rendering or dispatching `FO4SF_PipboyTravel.Go`, which checks `IsBitDiscovered(storeIdx)` — keeping native and Papyrus in 100% agreement.
- **Verified / INI-Configurable Offsets:** `FO4SFPipboyMenu.ini` exposes `MapHeadingAt` (defaulting to `[Kit] HeadingAt=88`, supporting `-` sign inversion), `MapGlobalValueAt` (`0` = self-verified via `GameHour`/`GameDaysPassed` slot check, default `+0x48`), `MapGameHourId` (`0x38`), `MapGameDaysPassedId` (`0x39`), `MapFileCollectionAt` (`0x1580` with `TESFile@@` RTTI verification), `MapExtraListAt` (`0xC8`), `MapMarkerFlagsAt` (`0x18`), and `MapMarkerDiscoveredMask` (`0x20`).

---

## PC Session Cards (One Launch Each After `S1-c3` PASS)

### PC Card — Slice 1: Map Key Opens Pip-Boy `MAP`, Swallows `M` on Close, & Blocks `GalaxyStarMapMenu`

- **Prerequisite:** `S1-c3` PASS, explicit owner game-launch release.
- **Stage (game closed):**
  1. Build `FO4SFPipboyMenu.dll` via `sfse/FO4SFPipboyMenu/build.ps1 -Out <build_dir> -Env <msvc_env_ps1>` and copy `FO4SFPipboyMenu.dll` + `FO4SFPipboyMenu.ini` beside `versionlib-1-16-244-0.bin` in `<game_dir>/Data/SFSE/Plugins/`.
  2. Stage the shell (`FO4SF_Fo4Shell.swf`) and `Pipboy_MapPage.swf` with `make_pipboy_probe.py stage <stage_dir>` and `pipboy_probe_install.py install --dir <stage_dir> --extra-movie FO4SF_Fo4Shell --page-movie Pipboy_MapPage --starfield <game_dir>` (plus any component clips required by `S1-c3`).
  3. In `FO4SFPipboyMenu.ini`, set:
     - `Stage=2`, `Movie=FO4SF_Fo4Shell`, `Key=0x76`, `Pause=1`, `Flags=0x19`
     - `CodeObj=1`, `CodeObjHide=1`, `CodeObjAt=Menu_mc`, `CodeObjPages=1`
     - `CodeObjCalls=Menu_mc.onCodeObjCreate`, `CodeObjLateCalls=Menu_mc.InvalidateData`
     - `CodeObjNames=PlaySound,HideMenu,onNewPage,onNewTab,RegisterMap,UnregisterMap,CenterMarkerRequest,CheckHardcoreModeFastTravel,RefreshMapMarkers,FastTravel,SetPlayerMarker,ClearPlayerMarker,onModalOpen,onSwitchBetweenWorldLocalMap,PlaySmallTransition`
     - `Map=1`, `MapKey=0x4D`, `MapPage=3`, `MapMenus=GalaxyStarMapMenu`, `MapBlockStarMap=1`
- **In-Game Steps:**
  1. Load an exterior save and press `M` (`0x4D`) once; wait 3 seconds and verify `FO4SF_PipboyMenu` opens on `MAP` while `GalaxyStarMapMenu` never appears.
  2. Press `M` a second time; wait 3 seconds and verify `FO4SF_PipboyMenu` closes cleanly and **stays closed** (no reopen bounce).
  3. Open scanner (`F`) and press `G` (surface/star map shortcut); verify Starfield's star map stays blocked, then quit cleanly.
- **PASS Criteria:**
  - `FO4SFPipboyMenu.log` shows `step=starmap_block_install menu=GalaxyStarMapMenu orig_rva=0x...`, `step=map_key n=1 vk=0x4d was_open=0 page=3 sent=show`, `step=map_input id=0x4d ... press=1 ... swallowed=1`, `step=map_key n=2 vk=0x4d was_open=1 on_map=1 sent=hide` (with no subsequent unrequested `sent=show`), and `step=starmap_blocked ... route=create`.

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

### PC Card — Slice 3: Project Marker Store, Live Engine Discovery, & Player Heading Arrow

- **Prerequisite:** Slice 2 PASS, explicit owner game-launch release.
- **Stage (game closed):**
  1. Generate `FO4SFPipboyMapMarkers.tsv` from the project's installed plugins:
     - `python scripts/ui/pipboy_map_store.py build-store --core <game_dir>/Data/FO4TerrainCore.esm --markers-esm <game_dir>/Data/FO4SFMapMarkers.esm --out <game_dir>/Data/SFSE/Plugins/FO4SFPipboyMapMarkers.tsv`
  2. Build `FO4SFPipboyTravel.esm` via `python scripts/ui/pipboy_map_store.py stage-travel-esm --store <game_dir>/Data/SFSE/Plugins/FO4SFPipboyMapMarkers.tsv --out <stage_travel>/FO4SFPipboyTravel.esm` and activate `FO4SFPipboyTravel.esm` in the test load order.
- **In-Game Steps:**
  1. Load the exterior Commonwealth save, press `M`, and verify markers start undiscovered (`discovered=0` on a fresh save before reveal).
  2. Close `M`, reveal one marker via engine `SetMarkerDiscovered` (e.g. Vault 111 exit lift arrival discovery or console `<markerRef>.cf "ObjectReference.SetMarkerDiscovered"`), press `M` again (without reloading), and verify that marker immediately flips to Discovered (`step=map_disc_sync`) while rotating ~90 deg East updates the `PlayerLocMarker` arrow.
- **PASS Criteria:**
  - `FO4SFPipboyMenu.log` shows `step=map_store file=FO4SFPipboyMapMarkers.tsv status=loaded markers=309` (`309` Commonwealth location rows; landing marker `0x8F2` is excluded unless `--include-landing` is passed), `step=map_globals value_at=0x48 source=verified ...`, `step=map_heading heading_at=+088 ...`, `step=map_disc_sync ... written=1`, and `step=map_markers ... discovered=1 ... corners_set=3/3 read_back=match`.

---

### PC Card — Slice 4: Fast Travel to a Discovered Marker (`PipboyMessageBox` -> `FO4SF_PipboyTravel.Go`)

- **Prerequisite:** Slice 3 PASS, explicit owner game-launch release.
- **Stage (game closed):**
  1. Copy the player's `PipboyMessageBox.swf` to `<stage_dir>/Data/Interface/Components/PipboyMessageBox.swf`, re-run `patch-mappage` with default `--msgbox-url Components/PipboyMessageBox.swf`, and pack `--component-movie Components/FO4SF_WorldMap --component-movie Components/PipboyMessageBox`.
  2. Compile `scripts/mapmarkers/FO4SF_PipboyTravel.psc` to `<stage_travel>/Data/Scripts/FO4SF_PipboyTravel.pex` and pack with `FO4SFPipboyTravel.esm`.
  3. Verify `MapSurvival=0` in `FO4SFPipboyMenu.ini`.
- **In-Game Steps:**
  1. Stand outdoors in the Commonwealth away from the discovered marker, press `M`, click an undiscovered marker first (verify fast travel is refused and custom waypoint is offered), then click the discovered marker and confirm in `PipboyMessageBox`.
  2. Wait for the loading fade to complete, observe player arrival and `GameHour` advance, then test `MapSurvival=1` (or `FO4SF_HardcoreFastTravelBlocked = 1` at `FO4SFCoreValues.esm:0x000841`) to confirm Hardcore/Survival mode blocks fast travel cleanly (`step=map_check_hardcore idx=... source=FO4SFCoreValues.esm:000841 allow=0`).
- **PASS Criteria:**
  - `FO4SFPipboyMenu.log` shows `step=map_check_hardcore ... source=FO4SFCoreValues.esm:000841 allow=1` (when Hardcore is OFF), `step=map_modal open=1`, `step=map_fast_travel_req idx=...`, and `step=map_fast_travel idx=... global_set=1 read_back=match call=FO4SF_PipboyTravel.Go queued=1`.
  - `FO4SF_PipboyTravel.0.log` shows `step=go idx=... fallback=...` with arrival coordinates matching the marker's merged arrival point and companions warped alongside the player.
  - Rollback: run `pipboy_probe_install.py uninstall --starfield <game_dir>` and restore `Map=0` / `Stage=0` in `FO4SFPipboyMenu.ini`.
