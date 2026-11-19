# Lead Ordered Game-Session Run Sheet (`G1` / `R11`)

> **NEW GAME needed (`A16` / `R15`):** Sessions 1 and 2 (`FO4SFNewGame.esm` mastering `FO4SFCoreValues.esm`) require a **NEW GAME** (old saves are not carried). Sessions 3 and 4 are `TEST-STATION` / `OWNER TEST` swap probes run from a clean test save via Console `coc`.

Truth labels used throughout: **`REACHABLE`**, **`TEST-STATION`**, **`RECORDS ONLY`**, **`TOOLING`**, **`NOT BUILT`**, **`NOT WIRED`**.

## Pre-Session Clean-Slate Preflight (Run Once Before Session 1, Game Closed)

> **PLAIN-WORDS WARNING (`H5`):** Running this preflight **removes the owner's currently installed build** from `<starfield-dir>/Data` and `Plugins.txt`: it releases any `plugin_toggle.py` hold (`FO4SF.toggle.json`), **uninstalls the standalone Pip-Boy probe kit** (`FO4SFPipboyProbe.install.json` + `FO4SFPipboyProbe.esm` + `FO4SFPipboyProbe - Main.ba2`), uninstalls `FO4SFMapMarkers.esm` before the core swap, and **uninstalls the installed experiment set** (`FO4SFExp.install.json`, e.g. the 7-plugin Vault 111 exit build and its `Main.ba2`). (`FO4Port.esm` and `FO4SFBridge.esm` stay on disk unless explicitly uninstalled; `IB2`'s `plugins_restore_pending = true` on completed manifests is benign.)

```bash
python scripts/game/plugin_toggle.py status --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/ui/pipboy_probe_install.py status --starfield <starfield-dir>
python scripts/ui/pipboy_probe_install.py uninstall --starfield <starfield-dir>
python scripts/game/map_markers_install.py status --starfield <starfield-dir>
python scripts/game/map_markers_install.py uninstall --starfield <starfield-dir>
python scripts/game/exp_install.py status --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
```

### Putting the Owner's Installed Build Back Afterwards (`H5`)
Each `uninstall` above archives a content-addressed `.json.gz` receipt into `<localappdata>/FO4SF/experiment-receipts/` (recording the staged `exp_dir` / `dir` and `plugins`). When those prior staged folders (`<prior-exp-dir>`, `<prior-mapmarkers-stage>`, `<prior-probe-stage>`) remain intact on disk, the CLI sequence from the preserved receipts is:

```bash
python scripts/game/exp_install.py install --exp-dir <prior-exp-dir> --starfield <starfield-dir> --plugins <prior-exp-plugins> --pack
python scripts/game/exp_install.py order --starfield <starfield-dir>
python scripts/game/map_markers_install.py install --dir <prior-mapmarkers-stage> --starfield <starfield-dir>
python scripts/ui/pipboy_probe_install.py install --dir <prior-probe-stage> --starfield <starfield-dir>
python scripts/game/plugin_toggle.py off --plugins FO4SFBridge.esm --starfield <starfield-dir> --why <prior-hold-reason>
```

**Important limitation (`H5`):** `make_core_bundle.py sidecar-undo` restores backed-up `Data/SFSE/Plugins/*` files overwritten by `sidecar-install`, whereas private `--extra-movie` / `--page-movie` / `--component-movie` probe options (recorded in `FO4SFPipboyProbe.install.json` only as `source_inputs` paths rather than CLI arguments) or exact pre-session `Plugins.txt` line positions cannot be reconstructed byte-identically by `exp_install.py` / `pipboy_probe_install.py` alone. **Use Lead's pre-session rollback set (`<prestate-backup>`) for a byte-identical restore of the owner's exit build.**

> **Bridge Hold Note (`H4`):** The owner's standing launcher setting holds `FO4SFBridge.esm` **OFF** (`Data/FO4SF.toggle.json`). Because `exp_install.py` and `home_world_install.py` refuse any `install` or `uninstall` while `FO4SF.toggle.json` is active, preflight and each swap temporarily run `plugin_toggle.py on` — which leaves `*FO4SFBridge.esm` **ACTIVE** in `Plugins.txt` until toggled back off! Each session below therefore states explicitly whether `FO4SFBridge.esm` must be **OFF** or **ON** in game and ends with `plugin_toggle.py off --plugins FO4SFBridge.esm --starfield <starfield-dir> --why owner-standing-bridge-off` so the owner's standing launcher setting is always put back.

---

## Session 1 — Candidate 2b Cards B and C (`1a`/`1c`/`1d` F7 `STAT` Crash-Proof Isolation & `1g` Scanner/Map Block)

- **Branch, Bundle & Verifier Head (`H1` / `H2`):** Install **`<cand2b-player-bundle>`** (**`Candidate 2b` `--profile player`**, `22` plugins) and run `make_core_bundle.py verify` from **`gemini/beginning-real` (`#833`, at `8bdafe6f`+)**, where `<cand2b-player-bundle>` passes (`verify: ok`). `gemini/beginning-real` (`#833`) merges `gemini/core-integration` (`#831` at `a21ea083`) with **`0` `sfse/` diff**, so `<cand2b-player-bundle>` carries the exact `#831` `FO4SFPipboyMenu.dll` and `FO4SFCombat.dll` code under test. **Do NOT use the Round 1 `Candidate 2` bundle (`72f903b9`)**: `#831` `b03a534d`'s `make_core_bundle.py verify` refuses it (`verify: 69 problem(s); do not install`, starting with missing `Data/Interface/pipboybootsequence.swf` from `A1`), and `#831`'s `verify` now refuses cross-head bundles in one line (`this bundle was built at <head>; this tool is at <head>`, `H2`).
- **`FO4SFBridge.esm` State (`H4`):** **MUST BE OFF** in game (`plugin_toggle.py off --plugins FO4SFBridge.esm` run immediately after `exp_install.py install`), matching the owner's standing launcher setting (Cards B and C test `FO4SFPipboyMenu`, `FO4SFCombat`, and scanner/map suppression without port load doors). At Session 1 end, release via `plugin_toggle.py on` for `exp_install.py uninstall`, then re-apply `plugin_toggle.py off --plugins FO4SFBridge.esm --starfield <starfield-dir> --why owner-standing-bridge-off` so the owner's bridge-off setting is put back.
- **New-Game Note:** **NEW GAME needed** — start one fresh `--profile player` New Game (`RequirePickup=0` and `--arm 0` in Card B's isolation INI let `F7` open immediately across `10` rapid cycles without carrying old saves).
- **Disk Need & Sidecar (`H3`):** `~4.2 GB` free under `<starfield-dir>/Data` plus `~5 MB` under `<starfield-dir>/Data/SFSE/Plugins` (installed and backed up via `make_core_bundle.py sidecar-install` -> `Data/FO4SFSidecar.install.json`, keeping format-5 `versionlib-1-16-244-0.bin` untouched beside `FO4SFPipboyMenu.dll`; `<cand2b-player-bundle>/sfse_sidecar/reputation/*` is reference-only and **not installed**).
- **Plugin List (`Plugins.txt`, `22` plugins in `<cand2b-player-bundle>`):**
  `FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFRouteLoot.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm`
- **Cards to Run in Order (`docs/testing/task0-task1-lead-cards.md`):**
  1. **`Card B` (`1a` / `1c` / `1d` F7 `STAT` Crash-Proof Isolation):** Part 1 negative `--arm 0 --omit StopPerkSound --allow-omit StopPerkSound` check, then Part 2 full `49`-name `--arm 0` plain-`Object` `BGSCodeObj` (`raw_type=8`, `is_closure=0`) check across `10` `F7` open/close cycles (`E` on `STAT` does not switch pages; `m`, `v`, `n` ignored while `Console` is open).
  2. **`Card C` (`1g` Starfield Scanner & Map Menus Block):** Outdoors in the same session (`MapBlockStarMap=1`), press Star Map, Surface Map, Planet Map, and `F` (`handscanner`); verify null-menu block (`route=create`) and zero `"FO4SF"` HUD developer banner (`1h`). (`MapBlockStarMap=0` hide-only fallback `sent=hide` is available in `FO4SFPipboyMenu.ini` if needed.)

### Exact Install, Sidecar & INI Commands (Run from `gemini/beginning-real` Worktree, Game Closed)
```bash
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/core/make_core_bundle.py verify --bundle-dir <cand2b-player-bundle>
python scripts/game/exp_install.py install --exp-dir <cand2b-player-bundle> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFRouteLoot.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2b-player-bundle> --starfield <starfield-dir>
python scripts/game/plugin_toggle.py off --plugins FO4SFBridge.esm --starfield <starfield-dir> --why session1-bridge-off
python scripts/ui/make_pipboy_stage_ini.py --stage <pipboy-stage-dir> --out <stage-ini-path> --arm 0 --omit StopPerkSound --allow-omit StopPerkSound
python scripts/ui/make_pipboy_stage_ini.py --stage <pipboy-stage-dir> --out <stage-ini-path> --arm 0
python scripts/testing/check_lead_sessions.py --log-dir <log-dir> --session 1 --require-all-pass
```

### PASS Lines to Read in Logs (`FO4SFPipboyMenu.log`, `FO4SFCombat.log`, `fo4sf_newgame.0.log`)
```log
step=code_obj_holder type=object raw_type=8 is_closure=0 source=menu_mc members=49 of=49
step=code_obj_destruction movie=<hex> called=1
step=map_unregister ok=1
step=destroy menu=<hex> flags=<flags>
step=menu_guard registered=<menus> count=<n>/38
step=process_user_event name=Cancel handled=<0|1> down=1
step=toggle n=<k> ignored=menu_open menu=Console
step=request_open by=map_key page=3 ignored=menu_open menu=Console
step=dispatch n=<k> fn=FO4SF_CombatInput.OnVatsKey ignored=menu_open menu=Console
step=dispatch n=<k> fn=FO4SF_CombatInput.OnAmmoKey ignored=menu_open menu=Console
FO4SF_NEWGAME rt=<rt> blocked input=handscanner
step=starmap_block_install menu=<menu> found=1 slot=<slot> orig_rva=<rva>
step=starmap_blocked n=<k> blocked menu=<menu> route=create
```

### Exact Undo Command (Game Closed — Restore Sidecar Backups, Uninstall & Restore Standing Bridge-Off)
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
python scripts/game/plugin_toggle.py off --plugins FO4SFBridge.esm --starfield <starfield-dir> --why owner-standing-bridge-off
```

### Stop Point if a Card Fails
- **If `Card B` fails** (any crash on `F7` open/close, `is_closure!=0`, `members!=49`, or hotkeys firing over `Console`): **STOP Session 1 immediately**, run the undo command, keep `Card D` (`1b`/`1i`/`1j`/`1k`) switched off, and skip `F7` in Session 2 (`Card 1`) until the crash log/minidump is diagnosed.
- **If `Card C` fails** under `MapBlockStarMap=1`: test `MapBlockStarMap=0` hide-only fallback (`step=map_suppress n=<k> name=<menu> sent=hide`) once in the same install; if either map or scanner suppression still crashes or opens Starfield's star map, run undo and record before Session 2 `Card 1` outdoor map checks.

---

## Session 2 — Candidate 2b Card A, then Cards 2, 1, 2/5, 3, 4

- **Branch & Head:** `gemini/beginning-real` (`#833`, Candidate 2b built over `350bc4bb` + Round 3/4 head on `gemini/beginning-real`, `0` `sfse/` diff from `#831` `a21ea083`).
- **`FO4SFBridge.esm` State (`H4`):** **MUST BE OFF** in game during both Sub-session 2A (`Card A`) and Sub-session 2B (`Cards 2, 1, 2/5, 3, 4`), matching the owner's standing launcher setting (Candidate 2b tests `FO4SF_ListTalkCell` and Vault 111 -> Sanctuary -> Concord without port load doors). Release `plugin_toggle.py on` before each `exp_install.py install`/`uninstall`, run `plugin_toggle.py off --plugins FO4SFBridge.esm` right after each install, and end Session 2 with `plugin_toggle.py off --plugins FO4SFBridge.esm --starfield <starfield-dir> --why owner-standing-bridge-off`.
- **New-Game Note:** **NEW GAME needed (`A16` / `R15`)** — start a fresh New Game for `Card A`, for the continuous `Card 2 -> Card 1 -> Card 2/5` Story walk, for `Card 3`, and for `Card 4`. At `Card 5` Concord `stage 20`, choose **`Quit to Desktop`** (never `Quit to Main Menu`) so `.0.log` rotates to `.1.log` (`B7`).
- **Disk Need & Sidecar (`H3`):** `~4.2 GB` free under `<starfield-dir>/Data` plus `~5 MB` under `<starfield-dir>/Data/SFSE/Plugins` and `<starfield-dir>/Data/Interface/pipboybootsequence.swf` (installed and backed up via `make_core_bundle.py sidecar-install` -> `Data/FO4SFSidecar.install.json`; `<cand2b-player-bundle>/sfse_sidecar/reputation/*` is reference-only and **not installed**).
- **Plugin Lists (`Plugins.txt`):**
  - **Sub-session 2A (`Card A`, `<cand2b-test-bundle>`, `--profile test`, `23` plugins, `FO4SF_TestModeEnabled == 1.0`):**
    `FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFRouteLoot.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFCoreCandidate.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm`
  - **Sub-session 2B (`Cards 2, 1, 2/5, 3, 4`, `<cand2b-player-bundle>`, `--profile player`, `22` plugins + `*FO4SFMapMarkers.esm`, `FO4SF_TestModeEnabled == 0.0`):**
    `FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFRouteLoot.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm` + `*FO4SFMapMarkers.esm`.
- **Cards to Run in Order (`docs/testing/task0-task1-lead-cards.md` & `docs/testing/candidate-2-cards.md`):**
  1. **`Card A` (`--profile test` `<cand2b-test-bundle>`):** Prove `DialogueMenu` silent-player list choices on `FO4SF_ListSpeakerNpc` (`0x000808`) inside `FO4SF_ListTalkCell` (`0x000807`), then uninstall `<cand2b-test-bundle>`.
  2. **Install `<cand2b-player-bundle>` + `<mapmarkers-stage-dir>`, start New Game #1 (`Story`, `Fallout 4: Commonwealth`, `Survival: No`):**
     - **`Card 2` (Pre-world set-up in `FO4SF_StartRoomCell` `0x00081C` -> Vault 111 Pip-Boy pickup):** Visible fade-free set-up prompts in `FO4SF_StartRoomCell` (`start room ready`, `start record mode=story story=fo4_commonwealth faction=-1 place=fo4_vault111 survival=0 difficulty=1 backdrop=empty_cell`, pre-world character choice) -> move to cryo pod (`stage 10 by=Trigger` -> `stage 20 by=scene`) -> Vault pistol (`0x24561C`) -> gear door blocked & `FO4SF_GearDoorConsoleRef` (`0x000819`) refused before Pip-Boy -> Pip-Boy pickup (`0x00080F`, `flag=1`).
     - **`Card 1` (immediately after Pip-Boy pickup):** Press **`F7`** to verify `pipboybootsequence.swf` first-open playback (`loose=<0|1>`), reopen onto `STAT`, Fallout-only Stimpak count (`0x000851`), and Console hotkey guard.
     - **`Card 2` -> `Card 5` (`2/5` continuous console-free walk):** Activate `FO4SF_GearDoorConsoleRef` (`0x000819`) -> `stage 30 by=vault_console` -> lift box (`Continue`, `S.P.E.C.I.A.L.`, `Stay`; choosing `Continue` first shows `FO4SF_NewGameExitNeedSpecialMsg` `0x00081F`) -> `<= 7`-button `40`-point S.P.E.C.I.A.L. (`FO4SF_ProgSpecialPage1Msg` `0x000870` / `FO4SF_ProgSpecialPage2Msg` `0x000878`, `source=Lift`) -> `+21.6 m` ascent -> hilltop `stage 200 by=Trigger` -> outdoor `Card 1` `MAP` (`discovered=1`, `FO4SFCoreValues.esm:000841`) -> Sanctuary Codsworth (`stage 10 by=info`) -> Concord raiders (`stage 20 by=Trigger`) -> manual save + **`Quit to Desktop`** + relaunch + reload (`reload mission stage=20 relocate_fails=0`) -> clear raiders (`stage 30 by=Trigger`) -> Preston 3 exchanges (`stage 35 by=info` -> `stage 40 by=info` -> `stage 200 by=Trigger`) -> Sanctuary workbench `0x005C50` (`sanctuary01 stage 100 by=bench`), then run `check_beginning_pilot.py check-logs --log-dir <log-dir> --require-all-pass`.
  3. **`Card 3` (same `--profile player` install, New Game #2):** `Story` + `Survival: Yes` (`gpof=0`, `start=1`, `enabled=1`, `why=start_choice`) -> save at cryo pod -> **`Quit to Desktop`** -> relaunch & reload (`why=Reload`, `hardcore=1`).
  4. **`Card 4` (same `--profile player` install, New Game #3):** Pre-world `FO4SF_StartRoomCell` (`Warfare` -> difficulty -> `Minutemen` -> `Sanctuary Hills` -> `Survival` -> `<= 7`-button `40`-point S.P.E.C.I.A.L. `source=warfare` *before* `ChargenMenu` -> character choice) -> direct exterior Sanctuary spawn without ever entering Vault 111 (`stage 210 by=Trigger`, `mission gate mode=2 started=false`).
  5. **`H00` One-Session Surface-Arrival Bisect (Console in Vault 111 Before the Lift Ride Only, Default `0` Keeps Today's Behaviour):**
     Quicksave at the Vault 111 lift before pressing `Continue`, then toggle one store global (`FO4SFCoreValues.esm` `0x000890`–`0x000897`) per run (`set FO4SF_H00_SkipMissionActors to 1`, `set FO4SF_H00_SkipRouteLoot to 1`, `set FO4SF_H00_SkipSurfaceSetPos to 1`, `set FO4SF_H00_SkipMapSetup to 1`, `set FO4SF_H00_SkipArrivalDiscovery to 1`, `set FO4SF_H00_ClearChargenBeforeSurface to 1`, `set FO4SF_H00_SkipLoadingHook to 1`, `set FO4SF_H00_SkipLandingQuests to 1`); each is read and logged once (`h00 suspect <EDID>=<0|1>`) before `surface moveto`.

### Exact Install, Sidecar, Console (`Card A` Only), & Log-Judge Commands (Game Closed for CLI)
Sub-session 2A (`Card A`, `--profile test`):
```bash
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/core/make_core_bundle.py verify --bundle-dir <cand2b-test-bundle>
python scripts/game/exp_install.py install --exp-dir <cand2b-test-bundle> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFRouteLoot.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFCoreCandidate.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2b-test-bundle> --starfield <starfield-dir>
python scripts/game/plugin_toggle.py off --plugins FO4SFBridge.esm --starfield <starfield-dir> --why session2a-bridge-off
```

```console
help "Silent-Player List Dialogue" 0
help FO4SF_ListDialogueQuest 4 QUST
sqv <quest-hex>
startquest <quest-hex>
coc FO4SF_ListTalkCell
setstage <quest-hex> 10
setstage <quest-hex> 15
setstage <quest-hex> 70
```

Swap from Sub-session 2A to Sub-session 2B (`Cards 2, 1, 2/5, 3, 4`, `--profile player`, console-free):
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
python scripts/core/make_core_bundle.py verify --bundle-dir <cand2b-player-bundle>
python scripts/testing/check_beginning_pilot.py check-bundle --bundle-dir <cand2b-player-bundle>
python scripts/game/exp_install.py install --exp-dir <cand2b-player-bundle> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFRouteLoot.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/game/map_markers_install.py install --dir <mapmarkers-stage-dir> --starfield <starfield-dir>
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2b-player-bundle> --starfield <starfield-dir>
python scripts/game/plugin_toggle.py off --plugins FO4SFBridge.esm --starfield <starfield-dir> --why session2b-bridge-off
python scripts/testing/check_beginning_pilot.py check-logs --log-dir <log-dir> --require-all-pass
```

### PASS Lines to Read in Logs (`FO4SFListDialogue.0.log`, `FO4SFPipboyMenu.log`, `fo4sf_newgame.*.log`, `fo4sf_mission.*.log`, `FO4SFHardcore.*.log`)
```log
FO4SFLIST rt=<rt> init speaker_present=True arrival_present=True end=true
FO4SFLIST rt=<rt> summary ok=true host_menu=DialogueMenu replaced_swf=false end=true
step=core_value_resolve name=FO4SF_PipboyAcquired source=FO4SFCoreValues.esm:000865 found=1 form=<hex>
step=boot_sequence movie=pipboybootsequence first_open=1 page=<page> loose=<0|1>
step=boot_sequence finished=1 reopen_page=<page>
step=map_markers n=<k> discovered=1 undiscovered=<u_cnt> player_idx=<idx> corners_set=3/3 read_back=match
step=map_check_hardcore idx=<idx> source=FO4SFCoreValues.esm:000841 allow=1
FO4SF_NEWGAME rt=<rt> start room ready by=<by> loaded=true cell=<cell> backdrop=empty_cell
FO4SF_NEWGAME rt=<rt> mode choice mode=story survival=0
FO4SF_NEWGAME rt=<rt> start record mode=story story=fo4_commonwealth faction=-1 place=fo4_vault111 survival=0 difficulty=1 backdrop=empty_cell
FO4SF_NEWGAME rt=<rt> stage 10 by=Trigger
FO4SF_NEWGAME rt=<rt> stage 20 by=scene
FO4SF_NEWGAME rt=<rt> pistol picked item=<form> count=<n>
FO4SF_NEWGAME rt=<rt> pipboy pickup equipped flag=1 worn=true
FO4SF_NEWGAME rt=<rt> cog door console activated ref=<ref> before=<s0> after=<s1>
FO4SF_NEWGAME rt=<rt> stage 30 by=vault_console
FO4SF_NEWGAME rt=<rt> special box shown box=FO4SF_ProgSpecialPage1Msg buttons=7 unspent=<u0> step=1
FO4SF_NEWGAME rt=<rt> special set S=<s> P=<p> E=<e> C=<c> I=<i> A=<a> L=<l> sum=40 source=Lift
FO4SF_NEWGAME rt=<rt> ascent carried confirmed elapsed=<sec> z=<z1>
FO4SF_NEWGAME rt=<rt> surface pre_setposition target=<tx> <ty> <tz> cell=<cell> world=<world>
FO4SF_NEWGAME rt=<rt> stage 40 by=Trigger
FO4SF_NEWGAME rt=<rt> landed z=<z> confirmed=True fallback=false world=<world>
FO4SF_NEWGAME rt=<rt> stage 200 by=Trigger
FO4SF_MISSION rt=<rt> mission gate mode=1 started=true
FO4SF_MISSION rt=<rt> min00 given by=codsworth
FO4SF_MISSION rt=<rt> stage 10 by=info
FO4SF_MISSION rt=<rt> stage 20 by=Trigger
FO4SF_MISSION rt=<rt> reload mission stage=20 relocate_fails=0
FO4SF_MISSION rt=<rt> stage 30 by=Trigger
FO4SF_MISSION rt=<rt> stage 35 by=info
FO4SF_MISSION rt=<rt> preston talk end info=0x092A -> stage 40
FO4SF_MISSION rt=<rt> stage 40 by=info
FO4SF_MISSION rt=<rt> stage 200 by=Trigger
FO4SF_MISSION rt=<rt> sanctuary01 stage 100 by=bench
FO4SF_MISSION rt=<rt> min01 bench activated -> stage 100
FO4SFHC rt=<rt> hardcore source gpof=0 start=1 enabled=1 why=start_choice end=true
FO4SFHC rt=<rt> hardcore source gpof=0 start=1 enabled=1 why=Reload end=true
FO4SF_NEWGAME rt=<rt> warfare pick faction=0 start=minutemen_sanctuary difficulty=<diff>
FO4SF_NEWGAME rt=<rt> start record mode=warfare story=none faction=0 place=minutemen_sanctuary survival=<0|1> difficulty=<diff> backdrop=empty_cell
FO4SF_NEWGAME rt=<rt> stage 210 by=Trigger
FO4SF_MISSION rt=<rt> mission gate mode=2 started=false
```

### Exact Undo Command (Game Closed — Restore Sidecar Backups, Uninstall & Restore Standing Bridge-Off)
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/map_markers_install.py uninstall --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
python scripts/game/plugin_toggle.py off --plugins FO4SFBridge.esm --starfield <starfield-dir> --why owner-standing-bridge-off
```

### Stop Point if a Card Fails
- **If `Card A` fails** (`speaker_present=False` or `DialogueMenu` never opens): save `FO4SFListDialogue.0.log`, uninstall `<cand2b-test-bundle>`, and still proceed to `<cand2b-player-bundle>` (`Card A` is not wired to Preston or Codsworth).
- **If `Card 2` fails inside Vault 111** (`cog door open failed state=`, lift strand, or stage `by=fallback`/`by=other`): **STOP the `2 -> 1 -> 2/5` Story walk immediately** (do not attempt `Card 5` via console), archive the rotated `.log` files, and still run `Card 3` (needs only `stage 10` cryo pod) and `Card 4` (Warfare exterior start) before running the undo commands to restore the clean exit build prior to Session 3.

---

## Session 3 — The Home Planet Pair and Its Variants (`FO4SFHome.esm` + `FO4TerrainCore_Home.esm`, `WB1`, `WB2`, `WL1`)

- **Branch & Head:** `gemini/world-own-space` (`#832`) at `44855053`.
- **`FO4SFBridge.esm` State (`H4`):** **MUST BE OFF** in game (`plugin_toggle.py off --plugins FO4SFBridge.esm` run after `home_world_install.py order`), matching the owner's standing launcher setting (Session 3 tests exterior sky, weather, ground, and outer-ring exclusion via `coc FO4Core_RedRocketSpawn`, never interior load doors; release `plugin_toggle.py on` only across `home_world_install.py install` and `undo`, which delegate to `exp_install.py`, and end Session 3 with `plugin_toggle.py off --plugins FO4SFBridge.esm --starfield <starfield-dir> --why owner-standing-bridge-off`).
- **New-Game Note:** **No New Game required** (`TEST-STATION` / `OWNER TEST` host swap: restore the baseline installed `FO4TerrainCore.esm` + `FO4Port.esm` set after Session 2's undo, load a clean test save, and arrive via Console `coc FO4Core_RedRocketSpawn`). **Do NOT install `Card 4`'s Round-1 `<i3-stage>/port` (`HELD FOR WB4`).**
- **Disk Need:** `~5 MiB` in `<starfield-dir>/Data` per active swap (`FO4SFHome - Main.ba2` + `FO4SFHome.esm` + `FO4TerrainCore_Home.esm`); `~42 MiB` on staging disk across `<home-stage>`, `<wb1-stage>`, `<wb2-stage>`, and `<wl1-stage>`.
- **Plugin List (`Plugins.txt`):**
  `*FO4Port.esm`, `*FO4PortTextures2.esm` (as installed), `FO4SFBridge.esm` (unticked / held off via `plugin_toggle.py off`), `*FO4TerrainCore.esm` (installed `15`-door core), `*FO4SFMapMarkers.esm` (merged & pinned via `--map-markers`), `*FO4SFHome.esm`, `*FO4TerrainCore_Home.esm` (`FO4TerrainCore_Mars.esm` unticked automatically by `home_world_install.py`; `FO4SFMission.esm` not installed).
- **Cards to Run in Order (`docs/testing/home-world-lead-card.md`):**
  1. **`Card 1` (Default `<home-stage>`, 2 fresh launches):** Launch 1 & Launch 2 `coc FO4Core_RedRocketSpawn` to confirm reproducible `merge_offset`, persistent refs, `WB3` overrides (Commonwealth HUD name, silent `_NONE` music, dry `-200 m` LOD water, cleared `LCTN` level cap), and outer-ring FO4 ground (`FO4SFHomeGroundDirt01` + `38.11 m` `PatternStyleFieldsHillsFieldsFlat`), then `undo`.
  2. **`Card 1` (`WB1` Weather & Sky Variants, game closed between swaps):** Swap `<wb1-stage>/01-ours-clear-temperate` vs `<wb1-stage>/02-starfield-control` for Owner screenshots (`R8`), running `undo` after each.
  3. **`Card 1` (`WB2` Ground, Pattern & Surface-Tree Variants, game closed between swaps):** Swap `<wb2-stage>/01-fo4-ground-flat-nosftr`, `<wb2-stage>/02-fo4-ground-flat-emptysftr`, `<wb2-stage>/03-fo4-ground-hills-control`, and `<wb2-stage>/04-no-orbital-meshes-ours-sunp`, running `undo` after each.
  4. **`Card 2` (`WL1` Outer-Ring Exclusion Levers):** Swap `<wl1-stage>/00-baseline` .. `06-all5` if any procedural POI, creature, scan tree, or ship encounter appears past cell `32`, running `undo` after each.

### Exact Stage, Check & Install Commands (Run from `gemini/world-own-space` Worktree, Game Closed)
```powershell
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/planet/make_home_planet.py check --stage <home-stage> --data <starfield-dir>/Data
python scripts/planet/home_world_install.py install --dir <home-stage> --starfield <starfield-dir>
python scripts/planet/home_world_install.py order --starfield <starfield-dir>
python scripts/game/plugin_toggle.py off --plugins FO4SFBridge.esm --starfield <starfield-dir> --why session3-bridge-off
```

```console
coc FO4Core_RedRocketSpawn
player.getpos x
player.getpos y
player.getpos z
```

### PASS Lines to Read in CLI / Probe Output
```text
check: ok
installed 3 files, plugins ['FO4SFHome.esm', 'FO4TerrainCore_Home.esm']
uninstalled
nothing installed
```

### Exact Undo Command (Game Closed — Restore Host & Standing Bridge-Off)
```powershell
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/planet/home_world_install.py undo --starfield <starfield-dir>
python scripts/planet/home_world_install.py status --starfield <starfield-dir>
python scripts/game/plugin_toggle.py off --plugins FO4SFBridge.esm --starfield <starfield-dir> --why owner-standing-bridge-off
python scripts/testing/check_lead_sessions.py --log-dir <log-dir> --session 3 --require-all-pass
```

### Stop Point if a Card Fails
- **If `Card 1` default `<home-stage>` fails** (`home_world_install.py install`/`order` refuses duplicate overrides, `coc FO4Core_RedRocketSpawn` crashes, or `merge_offset` shifts non-deterministically between Launch 1 and Launch 2): **STOP Session 3 immediately**, run `home_world_install.py undo --starfield <starfield-dir>` + `status` (`nothing installed`) to re-tick `*FO4TerrainCore_Mars.esm`, and skip `WB1`/`WB2`/`WL1` variant swaps until the host record is corrected.

---

## Session 4 — The DLC Worlds (`FO4DLC.esm`, Commonwealth DLC Override & Two-Way Doors, Far Harbor & Nuka-World)

- **Branch & Head:** `gemini/dlc-and-interiors` (`#834`) at `3b1c4110` (`Card 1` `FO4DLC.esm`) and `gemini/world-own-space` (`#832`) at `44855053` (`Card 6` `FO4TerrainCore_DLC.esm` `WB5`/`WB5b` and `Card 3` `FO4WorldFarHarbor.esm` / `FO4WorldNukaWorld.esm`).
- **`FO4SFBridge.esm` State (`H4`):**
  - **Sub-session 4A (`FO4DLC.esm` `Card 1`):** **OFF** (keep the owner's standing `plugin_toggle.py off --plugins FO4SFBridge.esm` hold; `deploy_starfield.py` tests `coc FO4DLC_*` interiors directly without port load doors).
  - **Sub-session 4B (`WB5` & `WB5b` `Card 6`):** **MUST BE ON (`ACTIVE`)** (`plugin_toggle.py on --starfield <starfield-dir>`), because `WB5b`'s two-way Nuka-World Transit & Vault 88 doors execute `FO4SF_LoadDoor.pex` from `FO4SFBridge - Main.ba2` and `make_cw_dlc_override.py install` refuses whenever `FO4SFBridge.esm` is inactive or held off in `Data/FO4SF.toggle.json`.
  - **Sub-session 4C (`Far Harbor` & `Nuka-World` `Card 3`) & Session 4 End State:** Keep `plugin_toggle.py` released while `exp_install.py` swaps `<fh-stage>` / `<nw-stage>` and restores `<cw-exp-dir>`, with `FO4SFBridge.esm` **OFF** in game (`plugin_toggle.py off --plugins FO4SFBridge.esm` after each `order`), and finish Session 4 with **`python scripts/game/plugin_toggle.py off --plugins FO4SFBridge.esm --starfield <starfield-dir> --why owner-standing-bridge-off`** so the owner's standing launcher bridge-off setting is restored.
- **New-Game Note:** **No New Game required** (`TEST-STATION`, Console `coc` only on a clean test save). **Mars Planet-Record Replacement Warning (`C5`/`C7`):** `FO4WorldFarHarbor_Mars.esm` and `FO4WorldNukaWorld_Mars.esm` override the whole `MarsPlanetData` record and replace the Commonwealth `exp_install.py` set for that sub-session; record `<cw-exp-dir>` and `<cw-plugins>` via `exp_install.py status` first and restore Commonwealth at the end of Session 4.
- **Disk Need:** `--min-free-gb 40` free-space floor on `<starfield-dir>`'s drive (`~7.1 GB` for `FO4DLC.esm` + `4` `.ba2`s, `~9.5 MiB` extra when `FO4TerrainCore_DLC.esm` swaps onto `FO4DLC`, `~26 MiB` for Far Harbor, `~54 MiB` for Nuka-World).
- **Plugin Lists (`Plugins.txt` per sub-session):**
  - **Sub-session 4A (`#834` `Card 1` — `FO4DLC.esm` 49 DLC Interiors):** `*FO4Port.esm`, `*FO4PortTextures2.esm`, `*FO4DLC.esm`, `*FO4DLCTextures2.esm`, `*FO4DLCTextures3.esm` (side-by-side with Commonwealth).
  - **Sub-session 4B (`#832` `Card 6` — `WB5` & `WB5b` Commonwealth DLC Override & Two-Way Doors):** `*FO4Port.esm`, `*FO4PortTextures2.esm`, `*FO4SFBridge.esm` (supplying `FO4SF_LoadDoor.pex`), `*FO4TerrainCore.esm`, `*FO4DLC.esm`, `*FO4DLCTextures2.esm`, `*FO4DLCTextures3.esm`, `*FO4TerrainCore_DLC.esm`, `*FO4TerrainCore_Mars.esm`.
  - **Sub-session 4C (`#832` `Card 3` — Far Harbor & Nuka-World Terrain & Sea Water on Mars):** `*FO4Port.esm`, `*FO4WorldFarHarbor.esm`, `*FO4WorldFarHarbor_Mars.esm` (then `*FO4Port.esm`, `*FO4WorldNukaWorld.esm`, `*FO4WorldNukaWorld_Mars.esm`).
- **Cards to Run in Order:**
  1. **`#834` `Card 1` (`docs/testing/dlc-and-interiors-lead-card.md`):** Dry-run then install `<fo4dlc-stage>`, `coc FO4DLC_DLC03Acadia`, `coc FO4DLC_DLC04BradbertonsOffice01`, `coc FO4DLC_DLC06VaultWorkshop` (floor collision + companion texture rendering), then uninstall with **`--plugin-name FO4DLC.esm`** (required so `FO4Port.esm` is never touched) and `deploy_starfield.py verify`.
  2. **`#832` `Card 6` (`docs/testing/home-world-lead-card.md`):** Ensure `FO4SFBridge.esm` is active (`plugin_toggle.py on`), install `<cw-dlc-stage>` + `<fo4dlc-doors-stage>`, `coc FO4Core_RedRocketSpawn`, test outbound entry and return exit (`R10`: no one-way door) at Nuka-World Transit Centre and both Vault 88 entrances, then `make_cw_dlc_override.py uninstall`.
  3. **`#832` `Card 3` (`docs/testing/home-world-lead-card.md`):** Record `<cw-exp-dir>` / `<cw-plugins>`, swap to `FO4WorldFarHarbor.esm,FO4WorldFarHarbor_Mars.esm` (`coc FO4FH_FarHarborSpawn`, `8` height probes + `6.43 m` sea water), swap to `FO4WorldNukaWorld.esm,FO4WorldNukaWorld_Mars.esm` (`coc FO4NW_NukaWorldSpawn`, `8` height probes + `4.64 m` water), then uninstall and restore `<cw-exp-dir>` / `<cw-plugins>`.

### Exact Install Commands (Run from Respective `#834` / `#832` Worktrees, Game Closed)
Sub-session 4A (`#834` `Card 1`):
```sh
python scripts/deploy_starfield.py install --batch <fo4dlc-stage> --starfield <starfield-dir> --min-free-gb 40 --dry-run
python scripts/deploy_starfield.py install --batch <fo4dlc-stage> --starfield <starfield-dir> --min-free-gb 40
```

```console
coc FO4DLC_DLC03Acadia
coc FO4DLC_DLC04BradbertonsOffice01
coc FO4DLC_DLC06VaultWorkshop
```

Sub-session 4B (`#832` `Card 6`):
```powershell
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/terrain/make_cw_dlc_override.py status --starfield <starfield-dir>
python scripts/terrain/make_cw_dlc_override.py install --dir <cw-dlc-stage> --dlc-doors <fo4dlc-doors-stage> --starfield <starfield-dir>
```

Sub-session 4C (`#832` `Card 3`):
```powershell
python scripts/game/exp_install.py status --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
python scripts/game/exp_install.py install --exp-dir <fh-stage> --starfield <starfield-dir> --pack --plugins FO4WorldFarHarbor.esm,FO4WorldFarHarbor_Mars.esm
python scripts/game/exp_install.py order --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
python scripts/game/exp_install.py install --exp-dir <nw-stage> --starfield <starfield-dir> --pack --plugins FO4WorldNukaWorld.esm,FO4WorldNukaWorld_Mars.esm
python scripts/game/exp_install.py order --starfield <starfield-dir>
```

```console
coc FO4FH_FarHarborSpawn
coc FO4NW_NukaWorldSpawn
```

### PASS Lines to Read in CLI / Probe Output
```text
install batch <fo4dlc-stage>: ['FO4DLC.esm', 'FO4DLC - Main.ba2', 'FO4DLC - Textures.ba2', 'FO4DLCTextures2.esm', 'FO4DLCTextures2 - Textures.ba2', 'FO4DLCTextures3.esm', 'FO4DLCTextures3 - Textures.ba2'] -> <starfield-dir>\Data (<gb> GB)
installed. Undo with: python deploy_starfield.py uninstall --starfield <game dir> --plugin-name FO4DLC.esm
installed port as recorded: FO4Port.esm <sha8>
installed wb5 session: added=8, plugins=['FO4DLC.esm', 'FO4DLCTextures2.esm', 'FO4DLCTextures3.esm', 'FO4TerrainCore_DLC.esm']
uninstalled wb5 session: removed=8, restored_fo4dlc=False
installed 3 files, plugins ['FO4WorldFarHarbor.esm', 'FO4WorldFarHarbor_Mars.esm']
installed 3 files, plugins ['FO4WorldNukaWorld.esm', 'FO4WorldNukaWorld_Mars.esm']
uninstalled
```

### Exact Undo Commands (Game Closed — Always Pass `--plugin-name FO4DLC.esm` on 4A & Restore Standing Bridge-Off)
```powershell
python scripts/deploy_starfield.py uninstall --starfield <starfield-dir> --plugin-name FO4DLC.esm
python scripts/deploy_starfield.py verify --starfield <starfield-dir>
python scripts/terrain/make_cw_dlc_override.py uninstall --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
python scripts/game/exp_install.py install --exp-dir <cw-exp-dir> --starfield <starfield-dir> --pack --plugins <cw-plugins>
python scripts/game/exp_install.py order --starfield <starfield-dir>
python scripts/game/plugin_toggle.py off --plugins FO4SFBridge.esm --starfield <starfield-dir> --why owner-standing-bridge-off
python scripts/testing/check_lead_sessions.py --log-dir <log-dir> --session 4 --require-all-pass
```

### Stop Point if a Card Fails
- **If Sub-session 4A (`FO4DLC.esm`) fails** (crash or missing-texture magenta in `FO4DLC_*`): **STOP before Sub-session 4B (`Card 6`)**, since `FO4TerrainCore_DLC.esm` masters `FO4DLC.esm`; run `deploy_starfield.py uninstall --starfield <starfield-dir> --plugin-name FO4DLC.esm` + `verify`, then skip directly to Sub-session 4C (`Card 3` Far Harbor & Nuka-World terrain have zero `FO4DLC.esm` dependency).
- **If Sub-session 4B (`WB5`/`WB5b`) fails** (reference mismatch or door return failure): run `make_cw_dlc_override.py uninstall --starfield <starfield-dir>` before starting Sub-session 4C.
- **If Sub-session 4C (`Card 3`) fails** on Far Harbor or Nuka-World: run `exp_install.py uninstall --starfield <starfield-dir>` and immediately restore `<cw-exp-dir>` / `<cw-plugins>` so the owner's exit build is left intact.
