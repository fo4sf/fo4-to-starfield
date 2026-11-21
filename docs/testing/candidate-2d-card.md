# Candidate 2d — First Game-Session Card (`Round 6` / `P2` / `P3` / `R11`)

> **NEW GAME needed (`A16` / `R15`) & Unproven Round-6 Notice:** Candidate 2d (`player`: `21` plugins **without** `FO4SFRouteLoot.esm`; `test`: `23` plugins; plus `22`-plugin `T1` isolation split bundles `<cand2d-t1-bases-only>` and `<cand2d-t1-ext-overrides-only>`) requires a **NEW GAME**. **Nothing from Round 6 (`T1` route-loot split, `T2` `MapBlockStarMap=0` default + non-null `IMenu` fallback, `T3` post-`LoadingMenu` box settle, `T4` single appearance prompt with `"Quick start"` button `0` + `Timer 1` continuation + fallback Vault 111 pistol, `T5` Warfare post-streaming fade-in, `T6` `0x1814` `DialogueMenu` choice list, `T7` `$ConsoleFont` boot SWF + 1st-person wrist visibility study, `T8` `SetCharGenHUDMode(2)` + `0`-XP secret-area `GMST`) has run in the game yet** — every Round-6 change below is **`TEST-STATION` / `OWNER TEST` (unproven in game)** until this session runs.

Truth labels used throughout: **`REACHABLE`**, **`TEST-STATION`**, **`OWNER TEST`**, **`RECORDS ONLY`**, **`TOOLING`**, **`NOT BUILT`**, **`NOT WIRED`**, **`NOT OURS`**.

## Console Batch & Runtime FormID Rules (`P2` / `P3` — Zero `M`, `N`, or `V` Typed)

1. **Never type `M`, `N`, or `V` in Console, and never pass mod `GLOB` or `QUST` EditorIDs:** Starfield strips EditorID strings from mod `GLOB` and `QUST` records (`set FO4SF_...` and `help FO4SF_...` fail with `Unknown variable` / `VIEWER STRINGS NOT AVAILABLE` even inside batch files). Every interactive ```` ```console ```` line on this card contains **zero `M`, `N`, or `V` letters**; commands needing `getglobalvalue`, `sqv`, or `M`/`N`/`V` characters live in `<starfield-dir>/<bat-id>.txt` (next to `Starfield.exe`) and are run via `bat <bat-id>` (whose filename also omits `m`, `n`, and `v`).
2. **How to confirm `FO4SFCoreValues.esm`'s runtime load-order byte (`0x07` in Lead's sessions):**
   - **Without opening Console:** Read `FO4SFPipboyMenu.log` after launch: `step=core_value_resolve name=FO4SF_PipboyAcquired source=FO4SFCoreValues.esm:000865 found=1 form=0x07000865` — the high byte (`07`) is `FO4SFCoreValues.esm`'s runtime index.
   - **In Console (zero `M`, `N`, or `V`):** Type `help "Health Cap" 4` -> Starfield prints `AVIF: (07000801) 'Radiation Health Cap'`. If the high byte differs from `07`, substitute `<XX>` for `07` in the batch files below.
   - **Load-Index Shift Without `FO4SFRouteLoot.esm` (`Card A` Note):** Because `FO4SFRouteLoot.esm` sits after `FO4SFWorkshop.esm`, omitting or holding off `FO4SFRouteLoot.esm` shifts plugins after `FO4SFWorkshop.esm` down by `1` slot (`FO4SFListDialogue.esm` becomes `0x11` -> `11000810` when `FO4SFCoreValues.esm` is `0x07`, vs `12000810` when `FO4SFRouteLoot.esm` is active). Always confirm `<quest-hex>` via `help "List Dialogue" 4 QUST`.
3. **`FO4SFCoreValues.esm` Runtime FormIDs at Load Index `0x07` (`set 0700089x to 1` — literal `to` required):**
   - **`H00` Suspect Switches (default `0`):** `07000890` (`FO4SF_H00_SkipLoadingHook`), `07000891` (`FO4SF_H00_ClearChargenBeforeSurface`), `07000892` (`FO4SF_H00_SkipArrivalDiscovery`), `07000893` (`FO4SF_H00_SkipMapSetup`), `07000894` (`FO4SF_H00_SkipRouteLoot`), `07000895` (`FO4SF_H00_SkipMissionActors`), `07000896` (`FO4SF_H00_SkipLandingQuests`), `07000897` (`FO4SF_H00_SkipSurfaceSetPos`).
   - **Start-Record & Gate Globals:** `07000865` (`FO4SF_PipboyAcquired`), `07000866` (`FO4SF_StartCardOpen`), `07000870` (`FO4SF_GameMode`), `07000871` (`FO4SF_SurvivalStart`), `07000872` (`FO4SF_SurvivalLocked`), `07000873` (`FO4SF_StartDifficulty`), `07000874` (`FO4SF_WarfareFaction`), `07000875` (`FO4SF_WarfareStartIndex`), `07000876` (`FO4SF_StartChoiceDone`), `07000877` (`FO4SF_StartNeutralSpot`), `07000878` (`FO4SF_StoryLine`), `07000879` (`FO4SF_StartPlaceRow`).

---

## Card 2d-1 — (1) Swap from Installed Candidate 2c to Candidate 2d (`21` Plugins Without `FO4SFRouteLoot.esm`, `sidecar-install`) and Exact Undo (`TOOLING` / `TEST-STATION`)

- **Starting Game State:** Candidate `2c` `--profile player` is installed with `sidecar-install` (`Data/FO4SFSidecar.install.json` present), and `FO4SFBridge.esm` + `FO4SFRouteLoot.esm` are held off by `plugin_toggle.py`. Run `sidecar-undo` and `plugin_toggle.py on` **first** before uninstalling `2c`.
- **Verifier Head Note (`H2`):** Run `make_core_bundle.py verify` at the `#833` head recorded in `<cand2d-player-bundle>/bundle_plan.json` (`verify` refuses cross-head runs with `this bundle was built at <build-head>; this tool is at <head>`).
- **Stage Placeholders:** `<cand2d-player-bundle>`, `<cand2c-player-bundle>`, `<mapmarkers-stage-dir>`, `<starfield-dir>`
- **Disk Need:** `~4.2 GB` free under `<starfield-dir>/Data` plus `~5 MB` under `<starfield-dir>/Data/SFSE/Plugins` (`sidecar-install` backs up pre-existing `Data/SFSE/Plugins/*` files byte-for-byte with SHA-256 into `Data/SFSE/.fo4sf_sidecar_backup`; `sfse_sidecar/reputation/*` is reference-only and **not installed**; shipped `FO4SFPipboyMenu.ini` now sets `MapBlockStarMap=0` by default per `T2`).
- **Player Plugin List (`Plugins.txt`, `21` plugins WITHOUT `FO4SFRouteLoot.esm` per `T1` + `*FO4SFMapMarkers.esm`, `FO4SFBridge.esm` held OFF):**
  `FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm`

### Swap 2c -> 2d Install Command (Game Closed)
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/map_markers_install.py uninstall --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
python scripts/core/make_core_bundle.py verify --bundle-dir <cand2d-player-bundle>
python scripts/testing/check_beginning_pilot.py check-bundle --bundle-dir <cand2d-player-bundle>
python scripts/game/exp_install.py install --exp-dir <cand2d-player-bundle> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/game/map_markers_install.py install --dir <mapmarkers-stage-dir> --starfield <starfield-dir>
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2d-player-bundle> --starfield <starfield-dir>
python scripts/game/plugin_toggle.py off --plugins FO4SFBridge.esm --starfield <starfield-dir> --why cand2d-session-bridge-off
```

### Exact Undo 2d -> 2c Command (Game Closed — Restores Pre-Session 2c State with `FO4SFBridge.esm` & `FO4SFRouteLoot.esm` Held Off)
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/map_markers_install.py uninstall --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
python scripts/game/exp_install.py install --exp-dir <cand2c-player-bundle> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFRouteLoot.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/game/map_markers_install.py install --dir <mapmarkers-stage-dir> --starfield <starfield-dir>
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2c-player-bundle> --starfield <starfield-dir>
python scripts/game/plugin_toggle.py off --plugins FO4SFBridge.esm,FO4SFRouteLoot.esm --starfield <starfield-dir> --why owner-standing-bridge-off
```

### Required Startup PASS Log Lines (`FO4SFPipboyMenu.log`)
```log
step=core_value_resolve name=FO4SF_PipboyAcquired source=FO4SFCoreValues.esm:000865 found=1 form=<hex>
step=menu_guard registered=<menus> count=<n>/38
step=map_config map_key=<vk> map_page=3 menus=<menus> block_starmap=0 store=<store> markers=<cnt> travel=<script>.<fn> survival=<0|1> heading_at=<sign>+<off>
```

### Negative / FAIL Conditions
- CLI: `this bundle was built at `, `sidecar install refused:`, `sidecar undo refused:`, `plugins held off by plugin_toggle.py`, `FO4SFRouteLoot.esm` active in `2d` player `Plugins.txt`, or `block_starmap=1` in default startup `FO4SFPipboyMenu.log`.

---

## Card 2d-2 — (2) Story Start Without Double Box (`T3` / `T4` / `T8`), Vault Exit, Concord Walk & Outdoor `M`-Key Map (`T2` `MapBlockStarMap=0`) (`TEST-STATION`)

- **Stage Placeholders:** `<cand2d-player-bundle>`, `<mapmarkers-stage-dir>`, `<starfield-dir>`
- **Disk Need:** `~4.2 GB` free under `<starfield-dir>/Data` (`0 B` extra on installed Candidate 2d).
- **Plugin List (`Plugins.txt`):** Same `21` plugins WITHOUT `FO4SFRouteLoot.esm` + `*FO4SFMapMarkers.esm` (`FO4SFBridge.esm` OFF) as Card 2d-1.

### Install Command (Already Installed from Card 2d-1)
```bash
python scripts/core/make_core_bundle.py verify --bundle-dir <cand2d-player-bundle>
python scripts/game/exp_install.py install --exp-dir <cand2d-player-bundle> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2d-player-bundle> --starfield <starfield-dir>
```

### Keys & Exact Visual Sequence (`T3`, `T4`, `T8`, `T2`, and Card 5)
1. **Main Menu -> New Game (`T3` + `T8` in `FO4SF_StartRoomCell` `0x00081C`):** Wait for `LoadingMenu` to close + `0.75 s` post-load settle **without touching `~` Console**. **You should SEE:** an empty neutral backdrop with **no health bar**, **no crosshairs** (`SetCharGenHUDMode(2)`), **no first-person hands** (`ShowFirstPersonGeometry(false)`), and **Box 1 (`FO4SF_NewGameModeMsg` `0x000806`) drawn automatically on screen** without needing Console to flush the message queue.
2. **Start Room Choices (`T4` Button Order & Title):**
   - **Box 1 (`0x000806`):** Pick **`Story`** (button `0`).
   - **Box 2 (`FO4SF_NewGameStoryLineMsg` `0x00081E`):** Pick **`Fallout 4: Commonwealth`** (button `0`).
   - **Box 3 (`FO4SF_NewGameSurvivalMsg` `0x000807`):** Pick **`No`** (button `0`).
   - **Box 4 (`FO4SF_NewGameStart` `0x000802`):** Confirm title is **`Character Appearance`** (not `"Vault 111"`) and **`Quick start` is button `0` (first)**, **`Create character` is button `1` (second, `NOT OURS`)** -> pick **`Quick start`** (button `0`).
3. **Vault 111 Arrival (`T4` Single Prompt + `Timer 1` Active + `T8` Zero XP Toast):**
   - Player enters `FO4Port_Vault111Cryo` (`stage 10 by=Trigger` -> immediate `stage 20` from pre-world choice) with **zero second appearance box at the cryo pod** and **zero `"40 XP"` secret-area toast** (`iXPRewardDiscoverSecretArea = 0`).
   - Pick up the fallback `FO4SFNewGame.esm` Vault pistol (`0x000820` -> `0x24561C`) + `48` rounds (`0x000821` -> `0x2B5598`) (`pistol picked`), pick up Pip-Boy (`0x00080F`, `pipboy pickup equipped flag=1` — run **Card 2d-5** here!), activate the gear-door console (`0x000819`, `cog door console activated` -> `stage 30`), step onto the lift (`0x000801`: confirm pressing `Continue` first shows `FO4SF_NewGameExitNeedSpecialMsg` `0x00081F`, no `"Character"` button), confirm `40`-point S.P.E.C.I.A.L. (`source=Lift`), and press **`Continue`**.
4. **Surface Landing (`21` Plugins Without `FO4SFRouteLoot.esm`) & Outdoor `T2` `M`-Key Check (`MapBlockStarMap=0`):**
   - Confirm clean hilltop landing (`stage 40 by=Trigger`, `landed z=<z> confirmed=True fallback=false`, `stage 200 by=Trigger`) with zero `Starfield.exe+0x41efd6` crash.
   - Press **`F`** (`blocked input=handscanner`), then press **`M`** outdoors (after first-open boot movie): confirm **zero `Starfield.exe+0x2540dc6` crash**, `GalaxyStarMapMenu` is hidden via `step=map_suppress n=<k> name=GalaxyStarMapMenu sent=hide`, our Commonwealth MAP page opens (`step=map_markers ... read_back=match`), **`Tab`** closes it (`step=map_unregister ok=1`), and pressing **`M`** a second time re-opens it cleanly.
5. **Card 5 Sanctuary -> Concord Walk (`T6` `0x1814` Live NPC Check):** Walk down to Sanctuary Codsworth (`0x000811`) -> press **`E`** (`DialogueMenu` with `0x1814` choices -> Choice 4 points to Concord, `min00 stage 10`) -> clear Concord street raiders + `Quit to Desktop` reload (`stage 20` -> `stage 30`) -> talk to Preston (`0x000802`, `3` exchanges -> `stage 40` -> `stage 200`) -> activate Sanctuary workbench (`0x005C50`, `min01 bench activated -> stage 100`).
6. *(Optional Console / `H00` batch check if needed — zero `M`, `N`, or `V` letters):*
```console
help "Health Cap" 4
bat h00a
bat h00b
```

```bat
; <starfield-dir>/h00a.txt (optional H00 Group A switches 0890..0893)
set 07000890 to 1
set 07000891 to 1
set 07000892 to 1
set 07000893 to 1
getglobalvalue 07000890

; <starfield-dir>/h00b.txt (optional H00 Group B switches 0894..0897)
set 07000894 to 1
set 07000895 to 1
set 07000896 to 1
set 07000897 to 1
getglobalvalue 07000894
```

### Undo Command (Game Closed)
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/map_markers_install.py uninstall --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
```

### Required PASS Log Lines (`fo4sf_newgame.0.log`, `FO4SFPipboyMenu.log`, `fo4sf_mission.0.log`)
```log
FO4SF_NEWGAME rt=<rt> start room ready by=<by> loaded=true cell=<cell> backdrop=empty_cell
FO4SF_NEWGAME rt=<rt> start ui ready released_by=<how> waited_s=<sec>
FO4SF_NEWGAME rt=<rt> start choice button=0
FO4SF_NEWGAME rt=<rt> start record mode=story story=fo4_commonwealth faction=-1 place=fo4_vault111 survival=0 difficulty=1 backdrop=empty_cell
FO4SF_NEWGAME rt=<rt> stage 10 by=Trigger
FO4SF_NEWGAME rt=<rt> looks done: <how>
FO4SF_NEWGAME rt=<rt> stage 20 by=Trigger
FO4SF_NEWGAME rt=<rt> pod settle ok=true pos=<x> <y> <z> dx=<dx> dy=<dy> drop=<drop> target=<tx> <ty> <tz> heading=<h> loaded=true cell=<cell> world=<world> sample_start=<t0> sample_end=<t1>
FO4SF_NEWGAME rt=<rt> status stage=20 pos=<x> <y> <z> cell=<cell> world=<world>
FO4SF_NEWGAME rt=<rt> pistol picked item=<item> count=<cnt>
FO4SF_NEWGAME rt=<rt> cog door console activated ref=<ref> before=<b0> after=<b1>
FO4SF_NEWGAME rt=<rt> elevator continue refused: special unconfirmed
FO4SF_NEWGAME rt=<rt> special set S=<s> P=<p> E=<e> C=<c> I=<i> A=<a> L=<l> sum=40 source=Lift
FO4SF_NEWGAME rt=<rt> stage 40 by=Trigger
FO4SF_NEWGAME rt=<rt> landed z=<z> confirmed=True fallback=false world=<world>
FO4SF_NEWGAME rt=<rt> stage 200 by=Trigger
step=map_key n=<k> vk=0x4d was_open=0 page=3 sent=request_open
step=map_suppress n=<k> name=GalaxyStarMapMenu sent=hide
step=map_markers n=<k> discovered=<d_cnt> undiscovered=<u_cnt> player_idx=<idx> corners_set=3/3 read_back=match
step=map_unregister ok=1
FO4SF_MISSION rt=<rt> mission gate mode=1 started=true
```

### Negative / FAIL Conditions
- First box sitting invisible until `~` Console opens/closes (`mode box waiting s=60` without box on screen), second appearance prompt shown at the cryo pod (`start choice button=` logged twice), `FO4SF_NewGameQuest` going silent after `stage 20`, missing Vault 111 pistol while `FO4SFRouteLoot.esm` is off, access violation at `Starfield.exe+0x2540dc6` on outdoor `M`, or `"No Dialogue Action on Player in First Phase"` on Codsworth/Preston.

---

## Card 2d-3 — (3) Warfare Post-Streaming Fade-In (`T5` / Card 4) & Card A `0x1814` Choice List (`T6` Test Bundle) (`TEST-STATION`)

- **Stage Placeholders:** `<cand2d-player-bundle>`, `<cand2d-test-bundle>`, `<starfield-dir>`, `<quest-hex>`
- **Disk Need:** `~4.2 GB` free under `<starfield-dir>/Data` plus `~5 MB` under `<starfield-dir>/Data/SFSE/Plugins`.
- **Plugin Lists (`Plugins.txt`):**
  - **Part 3A (`T5` / `Card 4` Warfare, `<cand2d-player-bundle>`, `21` plugins):** Same as Card 2d-1 (`FO4SFRouteLoot.esm` omitted, `FO4SFBridge.esm` OFF).
  - **Part 3B (`T6` / `Card A`, `<cand2d-test-bundle>`, `23` plugins installed, `FO4SFBridge.esm` & `FO4SFRouteLoot.esm` held OFF via `plugin_toggle.py`):**
    `FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFRouteLoot.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFCoreCandidate.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm`

### Part 3A (`T5` Warfare Post-Streaming Fade-In) — Console-Free Steps on Installed `<cand2d-player-bundle>`
1. Start a **New Game** -> in `FO4SF_StartRoomCell` (`0x00081C`), pick **`Warfare`** -> **`Easy`** (`0`) -> **`Minutemen`** (`0`) -> **`Sanctuary Hills`** (`0`) -> **`Survival: No`** (`0`).
2. Confirm `40`-point S.P.E.C.I.A.L. (`source=warfare`) draws in `FO4SF_StartRoomCell`, then in **`Character Appearance`** (`0x000802`) pick **`Quick start`** (button `0`, first option).
3. **`T5` Exterior Fade-In Check:** After `warfare move ok=true marker=FO4Core_CommonwealthMapMarkerSanctuary` and exterior `LoadingMenu` streaming finish, confirm `RunWarfareBranch`'s post-`Is3DLoaded()` settle + Timer `4` re-assertions **automatically lift the black fade and loading spinner within ~2–4 s** into visible Sanctuary Hills (`stage 210 by=Trigger`, `mission gate mode=2 started=false`) with zero console fade command needed.

### Part 3B (`T6` Card A `0x1814` Choice List) — Swap `<cand2d-player-bundle>` -> `<cand2d-test-bundle>` (Game Closed)
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/map_markers_install.py uninstall --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
python scripts/core/make_core_bundle.py verify --bundle-dir <cand2d-test-bundle>
python scripts/game/exp_install.py install --exp-dir <cand2d-test-bundle> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFRouteLoot.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFCoreCandidate.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2d-test-bundle> --starfield <starfield-dir>
python scripts/game/plugin_toggle.py off --plugins FO4SFBridge.esm,FO4SFRouteLoot.esm --starfield <starfield-dir> --why cand2d-test-bridge-and-routeloot-off
```

### Part 3B (`T6` Card A) — In-Game Console & Batch Lines (Zero `M`, `N`, or `V` Letters; Confirm `<quest-hex>` via `help "List Dialogue" 4 QUST`)
1. Type `help "List Dialogue" 4 QUST` -> Starfield prints `QUST: (<quest-hex>) 'FO4SF Silent-Player List Dialogue'` (`11000810` when `FO4SFCoreValues.esm` is `07` and `FO4SFRouteLoot.esm` is held off, or `12000810` if `FO4SFRouteLoot.esm` is active; update `<XX>000810` in `carda0.txt`..`carda3.txt` if needed).
2. Run `bat carda0` (`coc FO4SF_ListTalkCell`), then `bat carda1` (`setstage ... 10`) and press **`E`** on `Relay Operator` (`0x000808`): confirm `SCEN.Flags = 0x1814` (`SCPI = null`, single NPC `SceneActor ID = 0`) plays the Phase 0 NPC greeting and **shows the full Phase 1 player choice list** (zero `"No Dialogue Action on Player in First Phase"`), pick failing checks `21` and `31`, then run `bat carda2` (`setstage ... 15`), press **`E`**, pick passing checks `20`, `22`, `30`, `40`, `50` and Goodbye `60`, and finish with `bat carda3` (`setstage ... 70`):
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
; <starfield-dir>/carda0.txt (11000810 when FO4SFCoreValues=07 and RouteLoot is held off; confirm via help "List Dialogue" 4 QUST)
sqv 11000810
startquest 11000810
coc FO4SF_ListTalkCell

; <starfield-dir>/carda1.txt
setstage 11000810 10

; <starfield-dir>/carda2.txt
setstage 11000810 15

; <starfield-dir>/carda3.txt
setstage 11000810 70
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
FO4SF_NEWGAME rt=<rt> warfare move ok=True marker=FO4Core_CommonwealthMapMarkerSanctuary dist=<d> z=<z>
FO4SF_NEWGAME rt=<rt> stage 210 by=Trigger
FO4SF_NEWGAME rt=<rt> warfare fade reassert tick=2
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
- **Part 3A (`T5` Warfare):** Black screen / loading spinner remaining on screen `> 10 s` after `stage 210 by=Trigger`, `"Vault 111"` title on the appearance box, or `warfare move ok=False`.
- **Part 3B (`T6` Card A):** `"No Dialogue Action on Player in First Phase"` on `Relay Operator`, missing choice list at stage `10` or `15`, or missing `summary ok=true`.

---

## Card 2d-4 — (4) One-Session `T1` Route-Loot Crash Split (`<cand2d-t1-bases-only>` vs `<cand2d-t1-ext-overrides-only>`) (`TEST-STATION`)

- **Purpose (`T1`):** Full `FO4SFRouteLoot.esm` crashed `2/2` runs at `Starfield.exe+0x41efd6` (null-member read at `+0x1f0`) ~`5 s` after `warfare gear n=4`, and passed `2/2` runs when held off. Run these two `22`-plugin split builds back-to-back in **one session** via fast Warfare Quick-Start (~`60 s` each, no Vault ride required) to isolate whether `+0x41efd6` comes from the synthesized `0x000820+` `CONT` bases or from overriding exterior `FO4TerrainCore.esm` `WRLD`/`CELL`/`REFR` container records:
  1. **`<cand2d-t1-bases-only>` (`--split bases-only`):** Owns `FO4SFRouteLoot.esm` `0x000820+` `CONT` bases + Vault 111 armory records ONLY (`0` exterior `REFR` overrides, `0` `WRLD` overrides; does not master `FO4TerrainCore.esm`).
  2. **`<cand2d-t1-ext-overrides-only>` (`--split ext-overrides-only`):** Owns `<= 600 m` Sanctuary->Concord exterior `WRLD`/`CELL`/`REFR` container overrides ONLY, keeping each reference's `FO4TerrainCore.esm` `CONT` base (`0` new `0x000820+` `CONT` bases, `0` Vault 111 edits; masters `Starfield.esm` + `FO4TerrainCore.esm` only).
- **Stage Placeholders:** `<cand2d-t1-bases-only>`, `<cand2d-t1-ext-overrides-only>`, `<cand2d-player-bundle>`, `<mapmarkers-stage-dir>`, `<starfield-dir>`
- **Disk Need:** `~4.2 GB` free under `<starfield-dir>/Data` plus `~5 MB` under `<starfield-dir>/Data/SFSE/Plugins`.
- **Split Plugin List (`Plugins.txt`, `22` plugins WITH split `FO4SFRouteLoot.esm` active, `FO4SFBridge.esm` OFF):**
  `FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFRouteLoot.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm`

### Sub-Run 4A — Install & Run `<cand2d-t1-bases-only>` (`~60 s` Warfare Sanctuary Quick-Start)
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
python scripts/core/make_core_bundle.py verify --bundle-dir <cand2d-t1-bases-only>
python scripts/game/exp_install.py install --exp-dir <cand2d-t1-bases-only> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFRouteLoot.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2d-t1-bases-only> --starfield <starfield-dir>
python scripts/game/plugin_toggle.py off --plugins FO4SFBridge.esm --starfield <starfield-dir> --why cand2d-t1-bases-bridge-off
```
- **In Game (`4A`):** Launch -> **New Game** -> **`Warfare`** -> **`Easy`** -> **`Minutemen`** -> **`Sanctuary Hills`** -> **`Survival: No`** -> confirm `40`-pt S.P.E.C.I.A.L. -> **`Quick start`** -> record **`LANDS`** (`stage 210 by=Trigger` + walk `15 s` in Sanctuary) vs **`CRASHES`** (`Starfield.exe+0x41efd6` after `warfare gear n=4`), then `Quit to Desktop`.

### Sub-Run 4B — Swap to `<cand2d-t1-ext-overrides-only>` & Run Identical `~60 s` Check
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
python scripts/core/make_core_bundle.py verify --bundle-dir <cand2d-t1-ext-overrides-only>
python scripts/game/exp_install.py install --exp-dir <cand2d-t1-ext-overrides-only> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFRouteLoot.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2d-t1-ext-overrides-only> --starfield <starfield-dir>
python scripts/game/plugin_toggle.py off --plugins FO4SFBridge.esm --starfield <starfield-dir> --why cand2d-t1-ext-bridge-off
```
- **In Game (`4B`):** Run the exact same **New Game -> Warfare -> Sanctuary Hills -> Quick start** sequence and record **`LANDS`** vs **`CRASHES`**:
  - **`4A` LANDS + `4B` CRASHES:** Exterior `FO4TerrainCore.esm` `WRLD`/`CELL`/`REFR` override records alone trigger `+0x41efd6` at exterior cell attach.
  - **`4A` CRASHES + `4B` LANDS:** Synthesized `0x000820+` `CONT` base / `CNTO` records trigger `+0x41efd6`.
  - **Both LAND:** Crash requires pairing an exterior `REFR` override with a swapped `0x000820+` `CONT` base `NAME` at cell attach.

### Undo / Restore `<cand2d-player-bundle>` (`21` Plugins Without `FO4SFRouteLoot.esm`, Game Closed)
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
python scripts/core/make_core_bundle.py verify --bundle-dir <cand2d-player-bundle>
python scripts/game/exp_install.py install --exp-dir <cand2d-player-bundle> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/game/map_markers_install.py install --dir <mapmarkers-stage-dir> --starfield <starfield-dir>
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2d-player-bundle> --starfield <starfield-dir>
python scripts/game/plugin_toggle.py off --plugins FO4SFBridge.esm --starfield <starfield-dir> --why cand2d-session-bridge-off
```

### Required PASS Log Lines (For Whichever Split Half Lands Cleanly in `fo4sf_newgame.0.log`)
```log
FO4SF_NEWGAME rt=<rt> warfare gear n=<n>
FO4SF_NEWGAME rt=<rt> warfare move ok=True marker=FO4Core_CommonwealthMapMarkerSanctuary dist=<d> z=<z>
FO4SF_NEWGAME rt=<rt> stage 210 by=Trigger
FO4SF_NEWGAME rt=<rt> warfare fade reassert tick=2
```

### Negative / FAIL Conditions (Crash Signature Being Isolated)
- Access violation at `Starfield.exe+0x41efd6` (read `+0x1f0`) ~`5 s` after `warfare gear n=4` before `warfare move ok=True`. Leave `<cand2d-player-bundle>` (`21` plugins without `FO4SFRouteLoot.esm`) installed afterward regardless of outcome.

---

## Card 2d-5 — (5) `T7` / `N1` First-Person Pip-Boy Arm, `$ConsoleFont` Boot Movie & `OWNER TEST` (`TEST-STATION` / `OWNER TEST`)

- **Shipped INI in `<cand2d-player-bundle>/sfse_sidecar/SFSE/Plugins/FO4SFPipboyMenu.ini`:** `Stage=2`, `Movie=FO4SF_Fo4Shell`, `BootMovie=pipboybootsequence`, `BootOnFirstOpen=1`, `MapBlockStarMap=0`, `Key=0x76` (`F7`), `Pause=1`, `Arm=1`, `ArmRaiseIdle=idleexaminewatch`, `ArmRaiseMs=2000`, `ArmLowerIdle=`, `ArmLowerEvent=`, `ArmLowerMs=3500`, `ArmRetryMs=2000` (zero `[Kit]` / `[Page ...]` sections).
- **Offline `T7` Finding (`docs/ui/pipboy-arm-visibility-study.md`):** `IDLE 0x0C154F` (`idleexaminewatch`) plays `DynamicIdle` on the 1st-person graph, while `FO4SF_PipboyWrist` (`0x00080D` in `FO4SFPipboyProbe.esm`) uses Biped slot `Chronomark` — which Starfield's 1st-person rig hides/occludes whenever equipped body/suit armor occupies Biped slots `3` (`BODY`), `8` (`SleevesVisOnly`), or `35` (`Spacesuit`) (vanilla watch-inspect scripts unequip slots `3`/`8`/`35` + call `ForceFirstPerson` + `SheatheWeapon` during the idle), and `FO4SF_Fo4Shell` currently renders as a 2D Scaleform `IMenu` overlay rather than onto a 3D mesh render target.
- **Stage Placeholders:** `<cand2d-player-bundle>`, `<starfield-dir>`
- **Disk Need:** `~4.2 GB` free under `<starfield-dir>/Data` (`0 B` extra on installed Candidate 2d).
- **Plugin List (`Plugins.txt`):** Same `21` plugins WITHOUT `FO4SFRouteLoot.esm` as Card 2d-1 (`FO4SFBridge.esm` OFF).

### Install Command (Already Installed from Card 2d-1)
```bash
python scripts/core/make_core_bundle.py verify --bundle-dir <cand2d-player-bundle>
python scripts/game/exp_install.py install --exp-dir <cand2d-player-bundle> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2d-player-bundle> --starfield <starfield-dir>
```

### Exact In-Game Keys & Sequence
1. **First Open (`$ConsoleFont` Boot Movie Fix + `Arm=1`):** After acquiring `FO4SF_PipboyWrist` (`0x00080F` in Vault 111 or `FO4SF_PipboyAcquired == 1` in Warfare), stand in first person with weapon holstered and press **`F7`** (or **`M`**): confirm `pipboybootsequence` renders **legible `$ConsoleFont` (`Consolas`) boot text inside its frame** (no garbled fallback text strips across the top of the screen), then `step=boot_reopen` opens `FO4SF_Fo4Shell` (`STAT` or `MAP`) without a `3500 ms` lockout. Press **`Tab`** to close.
2. **Unarmored Bare-Forearm `T7` Visibility Check:** Open Inventory, temporarily unequip body/suit clothing occupying Biped slots `3`/`8`/`35` while keeping `FO4SF_PipboyWrist` (`0x00080D`) equipped, holster weapon in first person, and press **`F7`**: observe whether the bare left forearm + `Chronomark` wrist mesh come into view during the `2000 ms` `idleexaminewatch` raise before `FO4SF_Fo4Shell` pauses the frame. Re-equip outfit afterward.
3. **Failed-Raise `R10` Fallback Check:** Switch to third person (or draw the pistol) so `idleexaminewatch` logs `accepted=0`, press **`F7`**, and confirm `FO4SF_Fo4Shell` still opens immediately (`show_in_ms=0`) and closes with `lock_ms=0`.

### OWNER TEST Section (Live Motion & Visual Judgement Required — Stills Cannot Sign Off `N1`)
1. **Live First-Person Arm Motion (Suit On vs Slots `3`/`8`/`35` Unequipped):** Watching live in-game motion (not 3 still captures), does `idleexaminewatch` bring the left forearm and `FO4SF_PipboyWrist` into view when sleeve/body slots `3`/`8`/`35` are unequipped, confirming sleeve-slot occlusion as the sole reason nothing appeared in `2c`'s screenshots?
2. **Boot-Movie Typography & Transition:** Does the patched `$ConsoleFont` `pipboybootsequence` text read cleanly on first open before `FO4SF_Fo4Shell` takes over?
3. **2D Overlay vs 3D Wrist Device Direction:** Confirm that `N1` ("get the Pip-Boy animation working") remains **NOT MET** until the owner sees acceptable live 1st-person arm/device motion in game, and record whether automatic temporary sleeve strip/re-equip on `F7` is desired.

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
step=arm_play_idle form=<hex> process=<proc> played=1 accepted=1 t_ms=<ms>
step=arm_raise n=<k> result=1 try=1 accepted=1 t_ms=<ms>
step=arm_raise_done n=<k> result=1 accepted=1 tries=<t> waited_ms=<w> show_in_ms=2000 t_ms=<ms>
step=arm_show n=<k> sent=show raise=1 arm_ready=1 t_ms=<ms>
step=arm_shown n=<k> accepted=1 t_ms=<ms>
step=arm_lower n=<k> send=none (the raise's clip carries on) accepted=1 lock_ms=3500 t_ms=<ms>
step=arm_raise_done n=<k> result=<gave_up|refused> accepted=0 tries=<t> waited_ms=<w> show_in_ms=0 t_ms=<ms>
step=arm_lower n=<k> send=none (the raise's clip carries on) accepted=0 lock_ms=0 t_ms=<ms>
```

### Negative / FAIL Conditions
- Garbled `$Terminal_Font` fallback strips across the top of the screen during `pipboybootsequence`, `step=boot_skip reason=missing`, `boot_done` locking `F7` behind `ArmLowerMs=3500`, or a refused raise blocking `FO4SF_Fo4Shell` (`R10`).
