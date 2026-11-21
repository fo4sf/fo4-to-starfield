# Pip-Boy Stack Integration Candidate (`CF-3` & `CF-4`)

## Overview

Branch `gemini/pipboy-stack` rebases the complete four-PR Pip-Boy stack linearly onto `main` (`713ed97a35440c9c5058d3383a55a3da8427e215`) while leaving all four original PR branches untouched:

| Layer | Source PR & Tip | Rebased Tip(s) on `gemini/pipboy-stack` | Scope |
| :--- | :--- | :--- | :--- |
| **1. Map Heading & World Read** | `#762` (`b2f33d34`) | `5440aaf7` .. `adc146ce` (`3` commits) | `HeadingAt=88`, `+0x110` worldspace read, `GridUnits=100`, `pipboy_map_bytes.py` |
| **2. Fallout 4 Shell Rebuild** | `#764` (`a115045e`) | `529fe5a5` .. `07b67f33` (`27` commits) | `Movie=`, `CodeObj=`, `CodeObjHide=`, `CodeObjSound=`, `CodeObjAt=Menu_mc`, `CodeObjPages=1`, `ShellKeys=`, `Arm=`, `CodeObjLateCalls=`, `CodeObjSpecial=`, `swf_names.py`, `--extra-movie` / `--page-movie` / `--component-movie` |
| **3. `S1-c4` Safety Fixes** | `#804` (`0469b8d4`) | `1d551034` (`1` commit) | `RootOf` vtable slot `0x2E` `InImage` guard, `ShellKeys` `SpecialReady` pre-hook, and partial `SPECIALList` fill rollback |
| **4. Pip-Boy `MAP` Slices 1–4** | `#801` (`80520c20`) | `2a87ff7d` .. `b8e722db` (`4` commits) | Dedicated `src/pipboy_map.cpp`/`.h` controller, complete Starfield Star-Map lockout (`starmap_blocked`), `M`-key routing/swallow, `2048x2048` BC1 -> SWF world map, `309`-row Commonwealth marker store, live `ExtraMapMarker` `0x20` discovery sync, and `FO4SF_PipboyTravel.Go` fast-travel / cross-world bridge |

---

## Conflict Resolutions Against `main` (`713ed97a`)

1. **`scripts/ui/pipboy_probe_install.py` & `tests/test_pipboy_probe_install.py`:**
   - `main` (`40407e12`, `df68c2e4`) added `--prepacked <archive>` and two prepacked-archive unit tests (`test_prepacked_path_never_calls_archive_builder`, `test_wrong_prepacked_archive_refuses_without_game_changes`).
   - `#764` (`c26b5e67`, `92244e49`, `3412d74a`, `06a05a6d`) added `--extra-movie`, `--page-movie`, `--component-movie`, SWF container checks, and Starfield `Interface` archive shadow refusal.
   - **Resolution:** Preserved both feature sets intact (`--prepacked` forwards cleanly to `exp_install.py` alongside `stage_problems` and `shadow_problems` checks, and all prepacked + movie/component unit tests run together).
2. **Clean Forwarder Isolation (`sfse/FO4SFPipboyMenu/`):**
   - `src/main.cpp` retains `#804`'s `RootOf` slot `0x2E` `InImage` check, `ShellKeys` `SpecialReady` pre-hook, and partial `SPECIALList` rollback, while delegating all `MAP` Slices 1–4 hooks through 10 single-line `PipboyMap::*` forwarders into `src/pipboy_map.cpp` / `src/pipboy_map.h`.
   - `sfse/FO4SFPipboyMenu/build.ps1` `$sources`, `tests/test_sfse_sidecar_scripts.py` (normalized to `LF` line endings so only the single `$sources` line differs from `main`), `sfse/native_components.json`, and `tests/test_native_components.py` remain 100% synchronized.
3. **Complete Vanilla Star-Map Block (`Map=1`, `MapBlockStarMap=1`):**
   - `InstallStarMapBlock` replaces `GalaxyStarMapMenu`'s creator in `RE::UI::menuMap` with `BlockedStarMapCreate` (`step=starmap_blocked n=... route=create`), blocking vanilla Star Map instantiation from `M`, scanner `G`, `DataMenu`, `MonocleMenu`, console, or script, while `MapKey` (`0x4D`) opens `FO4SF_PipboyMenu` directly on `MAP` (`page=3`) and swallows `M` while open so closing never bounces.
4. **`INV` Drop & `DATA` `WorkshopsList` Placeholder (`InvDataAnswers=1`):**
   - `WorkshopsList` on the `DATA` page is an explicit static **placeholder** (`Sanctuary Hills (Placeholder)`), not live settlement telemetry.
   - `TESObjectREFR::RemoveItem` virtual slot `0x8B` and `RawRemoveItemRequest` (`0x40` bytes) are documented in [pipboy-inv-drop-note.md](../ui/pipboy-inv-drop-note.md).

---

## Offline Build, Stage & Verify Commands

```powershell
$env:TMP = $env:TEMP = "<SCRATCH_TMP>"
$py = "<PYTHON_EXE>"

# 1. Build FO4SFPipboyMenu.dll with portable MSVC + xmake + pinned CommonLibSF
powershell -NoProfile -ExecutionPolicy Bypass `
  -File sfse/FO4SFPipboyMenu/build.ps1 `
  -Out "<BUILD_DIR>" `
  -Env "<MSVC_ENV_PS1>"

# 2. Stage base FO4SFPipboyProbe.esm + fallback kit SWF
& $py scripts/ui/make_pipboy_probe.py stage "<PROBE_STAGE>" --kit
& $py scripts/ui/make_pipboy_probe.py check "<PROBE_STAGE>\FO4SFPipboyProbe.esm"

# 3. Build 309-marker Commonwealth store & FO4SFPipboyTravel.esm
& $py scripts/ui/pipboy_map_store.py build-store `
  --core "<CORE_DIR>\FO4TerrainCore.esm" `
  --markers-esm "<MARKERS_DIR>\FO4SFMapMarkers.esm" `
  --out "<STAGE_DIR>\SFSE\Plugins\FO4SFPipboyMapMarkers.tsv"

& $py scripts/ui/pipboy_map_store.py stage-travel-esm `
  --store "<STAGE_DIR>\SFSE\Plugins\FO4SFPipboyMapMarkers.tsv" `
  --out "<STAGE_DIR>\FO4SFPipboyTravel.esm"

# 4. Stage WorldMap_d.dds -> Components/FO4SF_WorldMap.swf & patch Pipboy_MapPage.swf
& $py scripts/ui/pipboy_map_store.py stage-worldmap `
  --dds "<FO4_EXTRACT>\WorldMap_d.dds" `
  --out "<STAGE_DIR>\Data\Interface\Components\FO4SF_WorldMap.swf"

& $py scripts/ui/pipboy_map_store.py patch-mappage `
  --src "<FO4_EXTRACT>\Pipboy_MapPage.swf" `
  --out "<STAGE_DIR>\Data\Interface\Pipboy_MapPage.swf"

# 5. Compile FO4SF_PipboyTravel.psc -> Data/Scripts/FO4SF_PipboyTravel.pex
& "<SF_DIR>\Tools\Papyrus Compiler\PapyrusCompiler.exe" FO4SF_PipboyTravel.psc `
  -f=Starfield_Papyrus_Flags.flg `
  -i="scripts\mapmarkers;<EXTRACTED_SF_SOURCES>" `
  -o="<STAGE_DIR>\Data\Scripts"

# 6. Run repository guard and targeted unit suites
$env:FO4SF_DOTNET_TESTS = "1"
& $py scripts/guard.py
& $py -m unittest `
  tests.test_native_components `
  tests.test_sfse_sidecar_scripts `
  tests.test_pipboy_probe_install `
  tests.test_pipboy_fo4_rebuild_plan `
  tests.test_pipboy_map `
  tests.test_pipboy_kit `
  tests.test_pipboy_map_bytes `
  tests.test_pipboy_map_plan `
  tests.test_pipboy_quest_bytes `
  tests.test_pipboy_look_plan `
  tests.test_pipboy_menu_channel `
  tests.test_pipboy_stat_page `
  tests.test_swf_names
```

---

## Integrated PC Verification Card (`S1-c4` + `MAP` Slices 1–4)

> [!IMPORTANT]
> Requires explicit owner game-launch release. Game closed during file copy and BA2 install. Follow the gated slice order in [pipboy-map-s1-s4.md](../ui/pipboy-map-s1-s4.md): verify shell + `STAT` (`S1-c3`/`S1-c4`) and `MAP` Slices 1–2 before claiming Slices 3–4 in-game marker/travel behavior.

1. **Install Staged Artifacts (Game Closed):**
   - Copy staged `SFSE/Plugins/FO4SFPipboyMenu.dll`, `SFSE/Plugins/FO4SFPipboyMenu.ini` (`Stage=2`, `Movie=FO4SF_Fo4Shell`, `CodeObj=1`, `CodeObjAt=Menu_mc`, `CodeObjPages=1`, `CodeObjSpecial=fill`, `Map=1`, `MapKey=0x4D`, `MapPage=3`, `MapBlockStarMap=1`), and `SFSE/Plugins/FO4SFPipboyMapMarkers.tsv` beside `versionlib-1-16-244-0.bin` in `<SF_DIR>/Data/SFSE/Plugins/`.
   - Install `FO4SFPipboyProbe.esm`, `FO4SFPipboyTravel.esm`, and packed `Data/` (`Interface/` shell + 5 pages + 18 `ConditionClips` + `FO4SF_WorldMap` + `PipboyMessageBox`, plus `Scripts/FO4SF_PipboyTravel.pex`) via `exp_install.py` (or folded core bundle).
2. **Verify Shell, `STAT`, & Complete Star-Map Lockout:**
   - Load an exterior Commonwealth test save (do not overwrite permanent saves).
   - Press `F7` (`0x76`): verify Fallout 4 Pip-Boy shell opens paused on `STAT` with `code_obj_special ... mode=fill ... pushed=7 length=#7`, `ConditionClips` loaded cleanly, and `E`/`Q` cycling `STAT` -> `INV` -> `DATA` -> `MAP` -> `RADIO` without crash; press `F7` to close.
   - Press `M` (`0x4D`): verify `FO4SF_PipboyMenu` opens directly on `MAP` (`page=3`), `2048x2048` Commonwealth world map renders inside `WorldMapHolder_mc`, and pressing `M` again closes cleanly with zero reopen bounce.
   - Open scanner (`F`) and press `G`: verify vanilla `GalaxyStarMapMenu` never opens and `FO4SFPipboyMenu.log` records `step=starmap_blocked ... route=create`.
3. **Verify Live Discovery & Fast Travel (Slices 3–4):**
   - Reveal a nearby Commonwealth marker (`SetMarkerDiscovered`), reopen `M`, and confirm `step=map_disc_sync ... written=1`, `step=map_markers ... corners_set=3/3 read_back=match`, and compass rotation on `PlayerLocMarker`.
   - Click the discovered marker on `MAP` and confirm in `PipboyMessageBox`: verify `step=map_fast_travel ... call=FO4SF_PipboyTravel.Go queued=1`, arrival at the marker's merged coordinates, clock advance, and follower teleportation without ever opening Starfield's Star Map.
