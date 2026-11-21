# Candidate 2c — First Game-Session Card (`P2` / `P3` / `R11`)

> **NEW GAME needed (`A16` / `R15`) & Unproven Round-4 Notice:** Candidate 2c (`player`: `22` plugins; `test`: `23` plugins; built and verified at `gemini/beginning-real` `#833` head `2e24d36e`) requires a **NEW GAME**. **Nothing from Round 4 has run in the game yet** — every Round-4 item below (`H00`, `H0` / `N2` start room, `Card 4` pre-creator Warfare S.P.E.C.I.A.L., `Card A` alias/lighting, `N1` `Arm=1` raise, `H0b` / `H0c`, `H3` `sidecar-install` / `sidecar-undo`) is **`TEST-STATION` / `OWNER TEST` (unproven in game)** until this session runs.

Truth labels used throughout: **`REACHABLE`**, **`TEST-STATION`**, **`OWNER TEST`**, **`RECORDS ONLY`**, **`TOOLING`**, **`NOT BUILT`**, **`NOT WIRED`**, **`NOT OURS`**.

## Console Batch & Runtime FormID Rules (`P2` / `P3` — Zero `M`, `N`, or `V` Typed)

1. **Never type `M`, `N`, or `V` in Console, and never pass mod `GLOB` or `QUST` EditorIDs:** Starfield strips EditorID strings from mod `GLOB` and `QUST` records (`set FO4SF_...` and `help FO4SF_...` fail with `Unknown variable` / `VIEWER STRINGS NOT AVAILABLE` even inside batch files). Every interactive ```` ```console ```` line on this card contains **zero `M`, `N`, or `V` letters**; commands needing `getglobalvalue`, `sqv`, or `M`/`N`/`V` characters live in `<starfield-dir>/<bat-id>.txt` (next to `Starfield.exe`) and are run via `bat <bat-id>` (whose filename also omits `m`, `n`, and `v`).
2. **How to confirm `FO4SFCoreValues.esm`'s runtime load-order byte (`0x07` in Lead's 22-plugin sessions):**
   - **Without opening Console:** Read `FO4SFPipboyMenu.log` after launch: `step=core_value_resolve name=FO4SF_PipboyAcquired source=FO4SFCoreValues.esm:000865 found=1 form=0x07000865` — the high byte (`07`) is `FO4SFCoreValues.esm`'s runtime index.
   - **In Console (zero `M`, `N`, or `V`):** Type `help "Health Cap" 4` -> Starfield prints `AVIF: (07000801) 'Radiation Health Cap'`. If the high byte differs from `07`, substitute `<XX>` for `07` in the batch files below.
3. **`FO4SFCoreValues.esm` Runtime FormIDs at Load Index `0x07` (`set 0700089x to 1` — literal `to` required):**
   - **`H00` Suspect Switches (default `0`):**
     - `07000890` — `FO4SF_H00_SkipLoadingHook`
     - `07000891` — `FO4SF_H00_ClearChargenBeforeSurface`
     - `07000892` — `FO4SF_H00_SkipArrivalDiscovery`
     - `07000893` — `FO4SF_H00_SkipMapSetup`
     - `07000894` — `FO4SF_H00_SkipRouteLoot`
     - `07000895` — `FO4SF_H00_SkipMissionActors`
     - `07000896` — `FO4SF_H00_SkipLandingQuests`
     - `07000897` — `FO4SF_H00_SkipSurfaceSetPos`
   - **Start-Record & Gate Globals:** `07000865` (`FO4SF_PipboyAcquired`), `07000866` (`FO4SF_StartCardOpen`), `07000870` (`FO4SF_GameMode`), `07000871` (`FO4SF_SurvivalStart`), `07000872` (`FO4SF_SurvivalLocked`), `07000873` (`FO4SF_StartDifficulty`), `07000874` (`FO4SF_WarfareFaction`), `07000875` (`FO4SF_WarfareStartIndex`), `07000876` (`FO4SF_StartChoiceDone`), `07000877` (`FO4SF_StartNeutralSpot`), `07000878` (`FO4SF_StoryLine`), `07000879` (`FO4SF_StartPlaceRow`).

---

## Card 2c-1 — (1) Swap from Installed Candidate 2b to Candidate 2c (`sidecar-install`) and Exact Undo Back to 2b (`TOOLING` / `TEST-STATION`)

- **Starting Game State:** Candidate `2b` `--profile player` is installed via `exp_install.py`, its sidecar was copied by hand into `<starfield-dir>/Data/SFSE/Plugins/*` (so no `Data/FO4SFSidecar.install.json` exists yet), and `FO4SFBridge.esm` is currently active in `Plugins.txt`.
- **Verifier Head Note (`H2`):** Candidate `2c` (`<cand2c-player-bundle>` and `<cand2c-test-bundle>`) was built and verified at `#833` head `2e24d36e` (`verify` checks `build_head` and refuses at a different git commit with `this bundle was built at 2e24d36e; this tool is at <head>`, whereas `exp_install.py` and `sidecar-install` / `sidecar-undo` run from any `#833` head).
- **Stage Placeholders:** `<cand2c-player-bundle>`, `<cand2b-player-bundle>`, `<mapmarkers-stage-dir>`, `<starfield-dir>`
- **Disk Need:** `~4.2 GB` free under `<starfield-dir>/Data` plus `~5 MB` under `<starfield-dir>/Data/SFSE/Plugins` (`sidecar-install` backs up every pre-existing `2b` file in `Data/SFSE/Plugins/*` byte-for-byte with SHA-256 into `Data/SFSE/.fo4sf_sidecar_backup`; `<cand2c-player-bundle>/sfse_sidecar/reputation/*` is reference-only and **not installed**).
- **Plugin List (`Plugins.txt`, `22` plugins + optional `*FO4SFMapMarkers.esm`, `FO4SFBridge.esm` held OFF):**
  `FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFRouteLoot.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm`

### Swap 2b -> 2c Install Command (Game Closed; Run `verify` at Build Head `2e24d36e` per `H2`; If `FO4SFMapMarkers.esm` Is Installed on 2b, Uninstall It Before `exp_install.py uninstall`)
```bash
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/map_markers_install.py status --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
python scripts/core/make_core_bundle.py verify --bundle-dir <cand2c-player-bundle>
python scripts/testing/check_beginning_pilot.py check-bundle --bundle-dir <cand2c-player-bundle>
python scripts/game/exp_install.py install --exp-dir <cand2c-player-bundle> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFRouteLoot.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/game/map_markers_install.py install --dir <mapmarkers-stage-dir> --starfield <starfield-dir>
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2c-player-bundle> --starfield <starfield-dir>
python scripts/game/plugin_toggle.py off --plugins FO4SFBridge.esm --starfield <starfield-dir> --why cand2c-session-bridge-off
```

### Exact Undo 2c -> 2b Command (Game Closed — Restores Backed-Up 2b `Data/SFSE/Plugins/*` Bytes & Reinstalls 2b)
*(Omit the final `plugin_toggle.py off` line only if you want `FO4SFBridge.esm` left active as in the pre-session state; keep it to restore the owner's standing launcher bridge-off setting.)*
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/map_markers_install.py uninstall --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
python scripts/game/exp_install.py install --exp-dir <cand2b-player-bundle> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFRouteLoot.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/game/plugin_toggle.py off --plugins FO4SFBridge.esm --starfield <starfield-dir> --why owner-standing-bridge-off
```

### Required Startup PASS Log Lines (`FO4SFPipboyMenu.log`)
```log
step=core_value_resolve name=FO4SF_PipboyAcquired source=FO4SFCoreValues.esm:000865 found=1 form=<hex>
step=menu_guard registered=<menus> count=<n>/38
step=starmap_block_install menu=<menu> found=1 slot=<slot> orig_rva=<rva>
```

### Negative / FAIL Conditions
- CLI: `this bundle was built at `, `sidecar install refused:`, `sidecar undo refused:`, `plugins held off by plugin_toggle.py`, or `found=0` on `FO4SF_PipboyAcquired` (`000865`).

---

## Card 2c-2 — (2) The New Pre-World Start Flow (`N2` / `H0` in `FO4SF_StartRoomCell`, Unproven in Game)

- **Stage Placeholders:** `<cand2c-player-bundle>`, `<mapmarkers-stage-dir>`, `<starfield-dir>`
- **Disk Need:** `~4.2 GB` free under `<starfield-dir>/Data` (`0 B` extra on installed Candidate 2c).
- **Plugin List (`Plugins.txt`):** Same `22` plugins + `*FO4SFMapMarkers.esm` (`FO4SFBridge.esm` OFF) as Card 2c-1.

### Install Command (Already Installed from Card 2c-1)
```bash
python scripts/core/make_core_bundle.py verify --bundle-dir <cand2c-player-bundle>
python scripts/game/exp_install.py install --exp-dir <cand2c-player-bundle> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFRouteLoot.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2c-player-bundle> --starfield <starfield-dir>
```

### Keys & Exact Visual Sequence (What You Should SEE at Every Step)
1. **Main Menu -> New Game:** During the initial load, `FO4SF_NewGameQuest` moves the player to owned empty cell `FO4SF_StartRoomCell` (`0x00081C` / `FO4SF_StartRoomMarkerRef` `0x00081D`), hides first-person geometry + Starfield HUD (`SetCharGenHUDMode(3)`), and immediately lifts `FaderMenu` (`FadeOutGame(False, True, 0.0, 0.1, False)`). **You should SEE:** `LoadingMenu` close within seconds into a lit, empty neutral backdrop with **no black screen**, **no Vault 111 cryo pod**, **no player hands/body**, and **no Starfield HUD**.
2. **Box 1 (`FO4SF_NewGameModeMsg` `0x000806`):** Drawn immediately on screen -> choose **`Story`** (button `0`; `Enter` / click).
3. **Box 2 (`FO4SF_NewGameStoryLineMsg` `0x00081E`):** Lists loadable story rows -> choose **`Fallout 4: Commonwealth`** (button `0`).
4. **Box 3 (`FO4SF_NewGameSurvivalMsg` `0x000807`):** Choose **`No`** (button `0`).
5. **Box 4 (`FO4SF_NewGameStart` `0x000802`):** Choose **`Quick start`** (button `0`, skips `ShowRaceMenu`) or **`Create character`** (button `1`, opens `ShowRaceMenu(None, 2)` — **`NOT OURS`**).
6. **Arrival at Vault 111 Cryo Pod:** Only AFTER Box 4 finishes does the quest write the start-record store globals (`07000870`..`07000879`), log `start record`, move the player into `FO4Port_Vault111Cryo` (`stage 10 by=Trigger`), restore first-person geometry + HUD, and fade in standing in front of the cryo pod (`pod settle ok=true`).
7. *(Optional store-index check in Console, zero `M`, `N`, `V`):*
```console
help "Health Cap" 4
```

### Undo Command (Game Closed)
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
```

### Required PASS Log Lines (`fo4sf_newgame.0.log`)
```log
FO4SF_NEWGAME rt=<rt> start room ready by=<by> loaded=true cell=<cell> backdrop=empty_cell
FO4SF_NEWGAME rt=<rt> mode choice mode=story survival=0
FO4SF_NEWGAME rt=<rt> start record mode=story story=fo4_commonwealth faction=-1 place=fo4_vault111 survival=0 difficulty=1 backdrop=empty_cell
FO4SF_NEWGAME rt=<rt> stage 5 by=Trigger
FO4SF_NEWGAME rt=<rt> stage 10 by=Trigger
FO4SF_NEWGAME rt=<rt> pod settle ok=true pos=<x> <y> <z> dx=<dx> dy=<dy> drop=<drop> target=<tx> <ty> <tz> heading=<h> loaded=true cell=<cell> world=<world> sample_start=<t0> sample_end=<t1>
```

### Negative / FAIL Conditions
- `mode fade lifted by=timeout s=15` (`15 s` hard `R10` fallback fired because `LoadingMenu` did not report closed — player is not stranded, but `H0` immediate-lift hypothesis failed), `mode box waiting s=60`, `enter start room ok=False`, or Vault 111 visible before `start record`.

---

## Card 2c-3 — (3) `H00` Surface-Arrival Crash Isolation (**At Most `4` Bisect Rides** after Baseline)

- **Stage Placeholders:** `<cand2c-player-bundle>`, `<starfield-dir>`
- **Disk Need:** `~4.2 GB` free under `<starfield-dir>/Data` (`0 B` extra on installed Candidate 2c).
- **Plugin List (`Plugins.txt`):** Same `22` plugins + `*FO4SFMapMarkers.esm` (`FO4SFBridge.esm` OFF) as Card 2c-1.

### Install Command (Already Installed from Card 2c-1)
```bash
python scripts/core/make_core_bundle.py verify --bundle-dir <cand2c-player-bundle>
python scripts/game/exp_install.py install --exp-dir <cand2c-player-bundle> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFRouteLoot.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2c-player-bundle> --starfield <starfield-dir>
```

### Pre-Ride Save & Binary-Bisect Order (**At Most `4` Bisect Rides** to Isolate Any of the `8` Suspects)
1. **Walk to the Lift & Save Once Before `Continue`:** Pick up Vault pistol (`0x24561C`) -> Pip-Boy (`0x00080F`; run **Card 2c-5 `N1`** right here before opening the gear door!) -> open gear door via console `0x000819` (`stage 30 by=vault_console`) -> step onto lift (`0x000801`: `Continue`, `S.P.E.C.I.A.L.`, `Stay` — confirm pressing `Continue` first shows modal `FO4SF_NewGameExitNeedSpecialMsg` `0x00081F`, no `"Character"` button) -> confirm `40`-point S.P.E.C.I.A.L. (`source=Lift`) -> choose **`Stay`** and **Quicksave (`F5`)** in front of the lift (`h00SuspectsRead` is still `false` until `Continue` is pressed!).
2. **Ride 0 (Clean `2c` Baseline, all `8` globals `0`):** Press **`Continue`** on the lift (`UnregisterStartLoadingHook()` and `N2` are active by default).
   - **If Ride 0 LANDS:** `H00` did not recur on `2c`; go straight to **"When a Ride Lands"** below!
3. **If Ride 0 Crashes (`Starfield.exe+0x41efd6`), Drop Batch Files into `<starfield-dir>/<id>.txt` and Reload the Pre-Lift Save (`<= 4` Bisect Rides Total):**
   - **Bisect Ride 1 (`bat h00a` — Group A, the `4` arrival/hook/map suspects `07000890..07000893`):**
     - **If Ride 1 LANDS** (culprit is in `0890..0893`): reload pre-lift save and run **Bisect Ride 2 (`bat h00a1` — `07000890, 07000891`)**:
       - Ride 2 LANDS -> reload and run **Bisect Ride 3 (`bat h00s0` — `07000890` only)**: LANDS = `07000890` (`SkipLoadingHook`); CRASHES = `07000891` (`ClearChargenBeforeSurface`). (**`3` bisect rides**)
       - Ride 2 CRASHES -> reload and run **Bisect Ride 3 (`bat h00s2` — `07000892` only)**: LANDS = `07000892` (`SkipArrivalDiscovery`); CRASHES = `07000893` (`SkipMapSetup`). (**`3` bisect rides**)
     - **If Ride 1 CRASHES** (culprit is not in `0890..0893`): reload pre-lift save and run **Bisect Ride 2 (`bat h00b` — Group B, the `4` loot/actor/quest/setpos suspects `07000894..07000897`)**:
       - **Ride 2 CRASHES** -> **STOP (`2` bisect rides!)**: none of the `8` scripted suspects stopped the crash (points to a static plugin record in the `22`-plugin load list, e.g. toggling `FO4SFRouteLoot.esm` or `FO4SFMission.esm` off via `plugin_toggle.py off`).
       - **Ride 2 LANDS** (culprit is in `0894..0897`) -> reload and run **Bisect Ride 3 (`bat h00b1` — `07000894, 07000895`)**:
         - Ride 3 LANDS -> reload and run **Bisect Ride 4 (`bat h00s4` — `07000894` only)**: LANDS = `07000894` (`SkipRouteLoot`); CRASHES = `07000895` (`SkipMissionActors`). (**`4` bisect rides**)
         - Ride 3 CRASHES -> reload and run **Bisect Ride 4 (`bat h00s6` — `07000896` only)**: LANDS = `07000896` (`SkipLandingQuests`); CRASHES = `07000897` (`SkipSurfaceSetPos`). (**`4` bisect rides max**)

### Interactive Console Lines to Trigger Any Bisect Batch (Zero `M`, `N`, or `V` Letters)
```console
bat h00a
bat h00a1
bat h00s0
bat h00s2
bat h00b
bat h00b1
bat h00s4
bat h00s6
```

### Batch File Contents to Place in `<starfield-dir>/` (Hex FormIDs Only, Paired with `getglobalvalue`)
```bat
; <starfield-dir>/h00a.txt (Group A: 0890..0893)
set 07000890 to 1
set 07000891 to 1
set 07000892 to 1
set 07000893 to 1
getglobalvalue 07000890
getglobalvalue 07000891
getglobalvalue 07000892
getglobalvalue 07000893

; <starfield-dir>/h00a1.txt (0890, 0891)
set 07000890 to 1
set 07000891 to 1
getglobalvalue 07000890
getglobalvalue 07000891

; <starfield-dir>/h00s0.txt (0890 only)
set 07000890 to 1
getglobalvalue 07000890

; <starfield-dir>/h00s2.txt (0892 only)
set 07000892 to 1
getglobalvalue 07000892

; <starfield-dir>/h00b.txt (Group B: 0894..0897)
set 07000894 to 1
set 07000895 to 1
set 07000896 to 1
set 07000897 to 1
getglobalvalue 07000894
getglobalvalue 07000895
getglobalvalue 07000896
getglobalvalue 07000897

; <starfield-dir>/h00b1.txt (0894, 0895)
set 07000894 to 1
set 07000895 to 1
getglobalvalue 07000894
getglobalvalue 07000895

; <starfield-dir>/h00s4.txt (0894 only)
set 07000894 to 1
getglobalvalue 07000894

; <starfield-dir>/h00s6.txt (0896 only)
set 07000896 to 1
getglobalvalue 07000896
```

### What to Do When a Ride LANDS
1. Confirm `stage 40 by=Trigger`, `landed z=<z> confirmed=True fallback=false`, and `stage 200 by=Trigger` in `fo4sf_newgame.0.log`.
2. **Run Card C Outdoor Checks on the Hilltop:** Press **`F`** (`blocked input=handscanner`) and press **`M`** (`step=map_suppress n=<k> name=<menu> sent=hide`, `step=map_markers ... discovered=1`, `step=map_check_hardcore ... source=FO4SFCoreValues.esm:000841`).
3. **If Mission Actors & Quests Are Enabled (`07000895 == 0` and `07000896 == 0`):** Walk down into **Card 5** (Sanctuary Codsworth `0x000811` -> Concord raiders + `Quit to Desktop` reload -> Preston `0x000802` 3 exchanges -> Sanctuary workbench `0x005C50`).

### Undo Command (Game Closed)
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
```

### Required PASS Log Lines (`fo4sf_newgame.0.log` & `FO4SFPipboyMenu.log`)
```log
FO4SF_NEWGAME rt=<rt> elevator continue refused: special unconfirmed
FO4SF_NEWGAME rt=<rt> special set S=<s> P=<p> E=<e> C=<c> I=<i> A=<a> L=<l> sum=40 source=Lift
FO4SF_NEWGAME rt=<rt> h00 suspect FO4SF_H00_SkipLoadingHook=<0|1>
FO4SF_NEWGAME rt=<rt> h00 suspect FO4SF_H00_ClearChargenBeforeSurface=<0|1>
FO4SF_NEWGAME rt=<rt> h00 suspect FO4SF_H00_SkipArrivalDiscovery=<0|1>
FO4SF_NEWGAME rt=<rt> h00 suspect FO4SF_H00_SkipMapSetup=<0|1>
FO4SF_NEWGAME rt=<rt> h00 suspect FO4SF_H00_SkipRouteLoot=<0|1>
FO4SF_NEWGAME rt=<rt> h00 suspect FO4SF_H00_SkipMissionActors=<0|1>
FO4SF_NEWGAME rt=<rt> h00 suspect FO4SF_H00_SkipLandingQuests=<0|1>
FO4SF_NEWGAME rt=<rt> h00 suspect FO4SF_H00_SkipSurfaceSetPos=<0|1>
FO4SF_NEWGAME rt=<rt> ascent carried confirmed elapsed=<sec> z=<z1>
FO4SF_NEWGAME rt=<rt> surface pre_setposition target=<tx> <ty> <tz> cell=<cell> world=<world>
FO4SF_NEWGAME rt=<rt> stage 40 by=Trigger
FO4SF_NEWGAME rt=<rt> landed z=<z> confirmed=True fallback=false world=<world>
FO4SF_NEWGAME rt=<rt> stage 200 by=Trigger
step=map_suppress n=<k> name=<menu> sent=hide
step=map_markers n=<k> discovered=1 undiscovered=<u_cnt> player_idx=<idx> corners_set=3/3 read_back=match
```

### Negative / FAIL Conditions
- Access violation at `Starfield.exe+0x41efd6` after `surface moveto`, `mode loading menu closed` firing at surface arrival (proves `UnregisterStartLoadingHook` missed an edge), `exit fallback by=move`, or `fallback=True`.

---

## Card 2c-4 — (4) Rebuilt Card 4 (Warfare Start) & Rebuilt Card A (`FO4SFListDialogue` Test Bundle)

- **Stage Placeholders:** `<cand2c-player-bundle>`, `<cand2c-test-bundle>`, `<starfield-dir>`, `<quest-hex>`
- **Disk Need:** `~4.2 GB` free under `<starfield-dir>/Data` plus `~5 MB` under `<starfield-dir>/Data/SFSE/Plugins`.
- **Plugin Lists (`Plugins.txt`):**
  - **Part 4A (`Card 4`, `<cand2c-player-bundle>`, `22` plugins):** Same as Card 2c-1 (`FO4SFBridge.esm` OFF).
  - **Part 4B (`Card A`, `<cand2c-test-bundle>`, `23` plugins, `FO4SF_TestModeEnabled` `07000860 == 1.0`):**
    `FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFRouteLoot.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFCoreCandidate.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm`

### Part 4A (`Card 4` Warfare) — Console-Free Steps on Installed `<cand2c-player-bundle>`
1. Start a **New Game** -> in `FO4SF_StartRoomCell` (`0x00081C`), pick **`Warfare`** -> **`Easy`** (`0`) -> **`Minutemen`** (`0`) -> **`Sanctuary Hills`** (`0`) -> **`Survival: No`** (`0`).
2. **Pre-creator `<= 7`-button S.P.E.C.I.A.L. (`source=warfare`):** Confirm `FO4SF_ProgSpecialPage1Msg` (`0x000870`) draws **visibly** inside `FO4SF_StartRoomCell` **before** `ChargenMenu` (while `SetInChargen` is `false`), allocate `40` points -> **`Confirm`**, then pick **`Quick start`** (or **`Create character`** -> finish `ChargenMenu`, `NOT OURS`).
3. **Direct Exterior Arrival:** Confirm fade-in directly at Sanctuary Hills (`stage 210 by=Trigger`, `mission gate mode=2 started=false`) without ever loading Vault 111.

### Part 4B (`Card A` List Dialogue) — Swap `<cand2c-player-bundle>` -> `<cand2c-test-bundle>` (Game Closed)
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/map_markers_install.py uninstall --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
python scripts/core/make_core_bundle.py verify --bundle-dir <cand2c-test-bundle>
python scripts/game/exp_install.py install --exp-dir <cand2c-test-bundle> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFRouteLoot.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFCoreCandidate.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2c-test-bundle> --starfield <starfield-dir>
python scripts/game/plugin_toggle.py off --plugins FO4SFBridge.esm --starfield <starfield-dir> --why cand2c-test-bridge-off
```

### Part 4B (`Card A`) — In-Game Console & Batch Lines (Zero `M`, `N`, or `V` Letters; `<quest-hex>` Is `12000810` When `FO4SFCoreValues.esm` Is `07`)
1. Type `help "List Dialogue" 4 QUST` -> Starfield prints `QUST: (<quest-hex>) 'FO4SF Silent-Player List Dialogue'` (`12000810` at load index `0x12`; substitute `<XX>000810` in the batch files if the high byte differs).
2. Run `bat carda0` (or `sqs <quest-hex>`, `startquest <quest-hex>`, `coc FO4SF_ListTalkCell`), confirm the `4`-light room illuminates `Relay Operator` (`0x000808`) clearly, then run `bat carda1` (`setstage 12000810 10` -> press `E`, pick failing checks `21`, `31`), `bat carda2` (`setstage 12000810 15` -> press `E`, pick passing checks `20`, `22`, `30`, `40`, `50` and `60`), and `bat carda3` (`setstage 12000810 70`):
```console
help "List Dialogue" 4 QUST
sqs <quest-hex>
bat carda0
bat carda1
bat carda2
bat carda3
startquest <quest-hex>
coc FO4SF_ListTalkCell
setstage <quest-hex> 10
setstage <quest-hex> 15
setstage <quest-hex> 70
```

```bat
; <starfield-dir>/carda0.txt (confirm <XX> == 12 via help "List Dialogue" 4 QUST)
sqv 12000810
startquest 12000810
coc FO4SF_ListTalkCell

; <starfield-dir>/carda1.txt
setstage 12000810 10

; <starfield-dir>/carda2.txt
setstage 12000810 15

; <starfield-dir>/carda3.txt
setstage 12000810 70
```

### Undo Command (Game Closed)
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
```

### Required PASS Log Lines (`fo4sf_newgame.0.log`, `fo4sf_mission.0.log`, `FO4SFListDialogue.0.log`)
```log
FO4SF_NEWGAME rt=<rt> warfare pick faction=0 start=minutemen_sanctuary difficulty=<diff>
FO4SF_NEWGAME rt=<rt> start record mode=warfare story=none faction=0 place=minutemen_sanctuary survival=<0|1> difficulty=<diff> backdrop=empty_cell
FO4SF_NEWGAME rt=<rt> special set S=<s> P=<p> E=<e> C=<c> I=<i> A=<a> L=<l> sum=40 source=warfare
FO4SF_NEWGAME rt=<rt> stage 210 by=Trigger
FO4SF_MISSION rt=<rt> mission gate mode=2 started=false
FO4SFLIST rt=<rt> init speaker_present=True arrival_present=True end=true
FO4SFLIST rt=<rt> eval phase=baseline_low speech=<sp> speech50=fail science=<sc> science40=fail strength=<st> strength7=fail bg_vaultdweller=locked trait_goodnatured=locked end=true
FO4SFLIST rt=<rt> choice_stage stage=21 tag=Speech_50 outcome=fail end=true
FO4SFLIST rt=<rt> eval phase=qualified_high speech=<sp> speech50=pass science=<sc> science40=pass strength=<st> strength7=pass bg_vaultdweller=pass trait_goodnatured=pass end=true
FO4SFLIST rt=<rt> choice_stage stage=20 tag=Speech_50 outcome=pass end=true
FO4SFLIST rt=<rt> choice_stage stage=60 tag=Plain_Goodbye outcome=exit end=true
FO4SFLIST rt=<rt> summary ok=true host_menu=DialogueMenu replaced_swf=false end=true
```

### Negative / FAIL Conditions
- **Card 4:** `special box shown` with no visible box on screen, player stranded in Vault 111 on Warfare, `special default` without player cancelling `3` times, or `warfare move ok=false`.
- **Card A:** Missing `FO4SFLIST ... init` in `--profile test`, `speaker_present=False`, dark/unlit silhouette speaker, or pressing `E` on `Relay Operator` failing to open `DialogueMenu`.

---

## Card 2c-5 — (5) `N1` First-Person Pip-Boy Arm (`Arm=1`, `idleexaminewatch`) & `OWNER TEST` (`TEST-STATION` / `OWNER TEST`)

- **Shipped INI in `<cand2c-player-bundle>/sfse_sidecar/SFSE/Plugins/FO4SFPipboyMenu.ini`:** `Stage=2`, `Movie=FO4SF_Fo4Shell`, `BootMovie=pipboybootsequence`, `BootOnFirstOpen=1`, `Key=0x76` (`F7`), `Pause=1`, `Arm=1`, `ArmRaiseIdle=idleexaminewatch`, `ArmRaiseMs=2000`, `ArmLowerIdle=`, `ArmLowerEvent=`, `ArmLowerMs=3500`, `ArmRetryMs=2000` (zero `[Kit]` / `[Page ...]` sections).
- **Stage Placeholders:** `<cand2c-player-bundle>`, `<starfield-dir>`
- **Disk Need:** `~4.2 GB` free under `<starfield-dir>/Data` (`0 B` extra on installed Candidate 2c).
- **Plugin List (`Plugins.txt`):** Same `22` plugins as Card 2c-1 (`FO4SFBridge.esm` OFF).

### Install Command (Already Installed from Card 2c-1)
```bash
python scripts/core/make_core_bundle.py verify --bundle-dir <cand2c-player-bundle>
python scripts/game/exp_install.py install --exp-dir <cand2c-player-bundle> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFRouteLoot.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2c-player-bundle> --starfield <starfield-dir>
```

### Exact In-Game Keys & Sequence (Run in Vault 111 Immediately After Pip-Boy Pickup `0x00080F`)
1. **First Open (`BootMovie` + `Arm=1`):** Stand in first person with weapon holstered after equipping the Pip-Boy (`0x00080F`) and press **`F7`**: `idleexaminewatch` raises the left wrist (`ArmRaiseMs=2000`), `pipboybootsequence` plays (`loose=0` from BA2), and `step=boot_reopen` transitions directly into `FO4SF_Fo4Shell` (`STAT`) without triggering a `3500 ms` lower lockout. Press **`Tab`** or **`F7`** to close and let the wrist lower over `ArmLowerMs=3500`.
2. **Second Open (`Arm=1` Steady-State):** After `3.5 s`, press **`F7`** again -> confirm `2.0 s` wrist raise into paused `FO4SF_Fo4Shell` (`STAT`) -> press **`Tab`** to lower.
3. **Failed-Raise `R10` Fallback Check:** Switch to third person (or draw the Vault pistol) so `1stPerson` `idleexaminewatch` reports `accepted=0` (or `gave_up`), press **`F7`**, and confirm `FO4SF_Fo4Shell` still opens cleanly without hanging and closes with `lock_ms=0`.

### OWNER TEST Section (Recorded by Lead for Owner Visual Judgement)
1. **Raise Angle & `ArmRaiseMs=2000` Timing:** In first person with holstered hands, does `idleexaminewatch` bring the left forearm/wrist to a convincing Pip-Boy viewing angle right as `Pause=1` freezes the world at `2000 ms`, or should `ArmRaiseMs` shift earlier/later?
2. **Close & `ArmLowerMs=3500` Feel:** When closing with `Tab` / `F7`, does unpausing let the remainder of `idleexaminewatch` lower smoothly without a camera snap, and is the `3500 ms` re-open guard comfortable?
3. **Overlay Framing:** How `FO4SF_Fo4Shell` (`STAT`) reads over the paused wrist backdrop compared to the flat `Arm=0` overlay.

### Undo Command (Game Closed)
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
```

### Required PASS Log Lines (`FO4SFPipboyMenu.log`)
```log
step=boot_sequence movie=pipboybootsequence first_open=1 page=<page> loose=<0|1>
step=boot_sequence finished=1 reopen_page=<page>
step=boot_reopen page=<page> sent=show
step=arm_raise n=<k> result=1 try=1 accepted=1 t_ms=<ms>
step=arm_raise_done n=<k> result=1 accepted=1 tries=<t> waited_ms=<w> show_in_ms=2000 t_ms=<ms>
step=arm_show n=<k> sent=show raise=1 arm_ready=1 t_ms=<ms>
step=arm_shown n=<k> accepted=1 t_ms=<ms>
step=arm_lower n=<k> send=none (the raise's clip carries on) accepted=1 lock_ms=3500 t_ms=<ms>
step=arm_raise_done n=<k> result=<gave_up|refused> accepted=0 tries=<t> waited_ms=<w> show_in_ms=0 t_ms=<ms>
step=arm_show n=<k> sent=show raise=<gave_up|refused> arm_ready=<0|1> t_ms=<ms>
step=arm_lower n=<k> send=none (the raise's clip carries on) accepted=0 lock_ms=0 t_ms=<ms>
```

### Negative / FAIL Conditions
- `step=boot_skip reason=missing` (means `pipboybootsequence.swf` failed both BA2 and loose lookup), `boot_done` locking `F7` behind `ArmLowerMs=3500` instead of reopening `FO4SF_Fo4Shell`, any crash across `LoadingMenu` transitions (`A4`), or a refused/missing animation blocking `FO4SF_Fo4Shell` from opening (`R10`).
