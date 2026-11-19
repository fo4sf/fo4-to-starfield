# Candidate 2b — Player-Profile Swap Test Cards (Cards 1–5)

> **NEW GAME needed (`A16` / `R15`):** Candidate 2b requires a **NEW GAME**. Old saves are **not** carried (`FO4SFNewGame.esm` adds `FO4SFCoreValues.esm` as a master and moves shared values — including `FO4SF_PipboyAcquired` `0x000865`, S.P.E.C.I.A.L., skills, karma, rads, and survival meters — into `FO4SFCoreValues.esm`).

## Recommended Lead Execution Order (`Candidate 2b`)
1. **`Card A`** (`docs/testing/task0-task1-lead-cards.md`, `--profile test`, `FO4SF_TestModeEnabled == 1.0`): prove the `DialogueMenu` speaker/scene route first.
2. **Switch to Candidate 2b `--profile player` (`FO4SF_TestModeEnabled == 0.0`) and start ONE New Game (`Story`, `Survival: No`):**
   - Begin **`Card 2`** (black-fade mode choice -> Vault 111 cryo pod -> pistol & Pip-Boy pickup).
   - **Run `Card 1` immediately after the Vault 111 Pip-Boy pickup** (`pipboy pickup equipped flag=1`), so `A1` (`pipboybootsequence.swf` loose under `Data/Interface/`), `A6` (`FO4SF_PipboyAcquired` `0x000865` in `FO4SFCoreValues.esm`), and `A7` (Fallout-only Stimpak count with zero Starfield Med Pack fallback) are all exercised in game.
   - Finish **`Card 2`** (`FO4SF_GearDoorConsoleRef` `0x000819` / `ACTI` `0x000818` -> `stage 30 by=vault_console` -> `<= 7`-button `40`-point lift S.P.E.C.I.A.L. -> ascent & hilltop `stage 200 by=Trigger`), then continue directly into **`Card 5`** (Sanctuary Codsworth -> Concord raiders with **`Quit to Desktop`** reload -> Preston `stage 35 by=info` -> `stage 40 by=info` -> Sanctuary workbench `0x005C50`).
3. **`Card 3`** (New Game -> `Story` + `Survival: Yes` -> save, quit, reload).
4. **`Card 4`** (New Game -> `Warfare` -> `Minutemen` -> `Sanctuary Hills`).

## Truth Labels & Explicit `NOT BUILT` / `NOT WIRED` Scope
- **`REACHABLE` / `TEST-STATION` / `RECORDS ONLY` / `TOOLING` / `NOT BUILT` / `NOT WIRED`:** No card upgrades to **`REACHABLE`** until its console-free game run writes the PASS log lines below with zero FAIL conditions.
- **Explicitly `NOT BUILT` this round:**
  - **Museum of Freedom interior quest chain:** `laser musket`, `balcony talk`, `power armor + fusion core` on the museum roof (`NOT REACHABLE` in `--profile player`; no frame is placed outside the `--profile test` cell), `minigun`, `second wave` raiders, and `deathclaw` emergence.
  - **Post-Concord group movement (`B11`):** **`Preston's group moving to Sanctuary`** (`NOT BUILT` — `FO4SF_CodsworthKeeper` holds Preston at the Concord museum door after `stage 200`).
  - **Vault 111 lift extras (`X3`):** Tag skills, background selection, and trait selection from the Story lift prompt.
- **Explicitly `NOT WIRED` this round (`R14`):**
  - **Native `FO4SF_SpecialMenu` (`A3` / `A12`):** **`NOT WIRED`** to the Vault 111 lift or Warfare start this round (the lift uses `<= 7`-button `Message` pages `0x0870` / `0x0878`).
  - **List Dialogue (`G4`):** Test cell `FO4SF_ListTalkCell` (`0x000807`) only; **`NOT WIRED`** to Preston or Codsworth.

---

## Card 1 — Pip-Boy Boot Movie, Crash Proof & Map Page (`1a`, `1c`–`1g`, `A1`, `A2`, `A6`, `A7`)

- **When to Run:** Inside the Candidate 2b `--profile player` New Game **right after picking up the Vault 111 Pip-Boy** (`FO4SF_PipboyAcquired` `0x000865 == 1`), and again outdoors on the Vault 111 hilltop for `MAP` fast-travel / marker verification.
- **Stage Placeholders:** `<player-bundle-dir>`, `<mapmarkers-stage-dir>`, `<starfield-dir>`
- **Disk Need:** `~4.2 GB` free under `<starfield-dir>/Data` plus `~5 MB` under `<starfield-dir>/Data/SFSE/Plugins` and `<starfield-dir>/Data/Interface/pipboybootsequence.swf`.
- **Plugin List (`Plugins.txt`, `22` bundle plugins + `FO4SFMapMarkers.esm`):**
  `FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFRouteLoot.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm` (plus `*FO4SFMapMarkers.esm` appended by `map_markers_install.py`).

### Install Command (Game Closed)
```bash
python scripts/core/make_core_bundle.py verify --bundle-dir <player-bundle-dir>
python scripts/game/exp_install.py install --exp-dir <player-bundle-dir> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFRouteLoot.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/game/map_markers_install.py install --dir <mapmarkers-stage-dir> --starfield <starfield-dir>
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <player-bundle-dir> --starfield <starfield-dir>
```

### Console-Free Steps
1. After activating the Vault 111 Pip-Boy pickup (`0x00080F`), press **`F7`**: confirm `pipboybootsequence.swf` plays on first open (`A1`, `A6`) and reopens directly onto **`STAT`**, staying up `>= 10 s` with zero crash.
2. Verify `STAT` shows Fallout `FO4SF_Stimpak` (`0x000851`) count only (`0` when carrying none; Starfield Med Pack never counted, `A7`), and pressing **`E`** on `STAT` does **not** switch pages.
3. Close with **`Tab`** or **`Esc`**; open Console (`` ` ``) briefly only to type `m`, `v`, `n` and confirm hotkeys are ignored while a blocking menu is open, then close Console without running any command.
4. Once outdoors on the Commonwealth hilltop (after Card 2 `stage 200`), press **`M`** to open **`MAP`**, confirm only Vault 111 is discovered (`discovered=1`), check fast-travel hardcore gate (`source=FO4SFCoreValues.esm:000841`), and press Starfield's scanner (**`F`**) and Star/Surface Map keys to verify they stay blocked cleanly.

### Undo Command (Game Closed)
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/map_markers_install.py uninstall --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
python scripts/game/plugin_toggle.py off --plugins FO4SFBridge.esm --starfield <starfield-dir> --why owner-standing-bridge-off
```

### Required PASS Log Lines (`FO4SFPipboyMenu.log` & `fo4sf_newgame.0.log`)
```log
step=core_value_resolve name=FO4SF_PipboyAcquired source=FO4SFCoreValues.esm:000865 found=1 form=<hex>
step=boot_sequence movie=pipboybootsequence first_open=1 page=<page> loose=<0|1>
step=boot_sequence finished=1 reopen_page=<page>
step=code_obj_holder type=object raw_type=8 is_closure=0 source=menu_mc members=49 of=49
step=code_obj_destruction movie=<hex> called=1
step=map_unregister ok=1
step=destroy menu=<hex> flags=<flags>
step=toggle n=<k> ignored=menu_open menu=Console
step=map_markers n=<k> discovered=1 undiscovered=<u_cnt> player_idx=<idx> corners_set=3/3 read_back=match
step=map_check_hardcore idx=<idx> source=FO4SFCoreValues.esm:000841 allow=1
FO4SF_NEWGAME rt=<rt> blocked input=handscanner
step=starmap_blocked n=<k> blocked menu=<menu> route=create
```

### OWNER TEST Items
- Boot movie visual playback, `STAT` Vault-Boy / condition layout, font legibility, `Pause=1` feel, and Commonwealth map alignment under pins.

---

## Card 2 — Story Start and Console-Free Vault 111 Exit (`S4`, `X1`–`X5`, `B1`–`B5`, `B8`)

- **Stage Placeholders:** `<player-bundle-dir>`, `<mapmarkers-stage-dir>`, `<starfield-dir>`
- **Disk Need:** `~4.2 GB` free under `<starfield-dir>/Data` (`0 B` extra when already installed for Card 1).
- **Plugin List (`Plugins.txt`, `22` bundle plugins + `FO4SFMapMarkers.esm`):**
  Same 22-plugin `--profile player` list + `*FO4SFMapMarkers.esm` as Card 1.

### Install Command (Game Closed)
```bash
python scripts/core/make_core_bundle.py verify --bundle-dir <player-bundle-dir>
python scripts/game/exp_install.py install --exp-dir <player-bundle-dir> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFRouteLoot.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/game/map_markers_install.py install --dir <mapmarkers-stage-dir> --starfield <starfield-dir>
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <player-bundle-dir> --starfield <starfield-dir>
```

### Console-Free Steps (Plus Optional First-Session Neutral-Spot Probe `B8`)
1. **Pre-world set-up (`N2`, `H0`, `B8`):** Start a **New Game** (`~` closed). `FO4SF_NewGameQuest` stages the player in owned empty interior `FO4SF_StartRoomCell` (`0x00081C` / `FO4SF_StartRoomMarkerRef` `0x00081D`), immediately lifts `FaderMenu` so `LoadingMenu` finishes cleanly (with `StartLoadTimeout = 15 s` hard fallback `mode fade lifted by=timeout s=15`, `R10`), hides first-person body & HUD, and presents `FO4SF_NewGameModeMsg` (`0x000806`), `FO4SF_NewGameStoryLineMsg` (`0x00081E`), `FO4SF_NewGameSurvivalMsg` (`0x000807`), and `FO4SF_NewGameStart` (`0x000802`, `NOT OURS` `ShowRaceMenu` if `Create character` is picked) BEFORE moving to Vault 111 (`stage 5 by=Trigger` -> `start record mode=story story=fo4_commonwealth faction=-1 place=fo4_vault111 survival=0 difficulty=1 backdrop=empty_cell` -> `stage 10 by=Trigger`). *(If `FO4SF_NewGameModeMsg` is left unanswered `>= 60 s`, `mode box waiting s=60` logs once per minute while continuing to wait.)*
2. **Cryo pod, vault pistol & Pip-Boy (`B4`, `B5`, `X1`, `X2`):** Step out of the pod (`pod settle ok=true`), finish looks (`stage 20 by=scene`), pick up the Vault 111 pistol (`0x24561C` from `route_loot_ids.json` `vault111.pistol_id`, filtered via `AddInventoryEventFilter` -> `pistol picked`), verify pressing `E` on the gear door directly stays shut and pressing `E` on `FO4SF_GearDoorConsoleRef` (`0x000819`, `ACTI` `FO4SF_GearDoorConsole` `0x000818`) before the Pip-Boy refuses (`0x000817` `FO4SF_NoPipboyConsoleMsg`), then equip the Pip-Boy (`0x00080F`) and activate `FO4SF_GearDoorConsoleRef` (`0x000819`) to open the gear door (`stage 30 by=vault_console`).
3. **Lift `<= 7`-button `40`-point S.P.E.C.I.A.L. & ascent (`B1`–`B3`, `X3`, `X4`, `H00`):** Step onto the Vault 111 platform (`FO4SF_NewGameElevator` `0x000801`: `Continue`, `S.P.E.C.I.A.L.`, `Stay` — Starfield's Enhance character screen is removed from the lift), confirm `Continue` shows `FO4SF_NewGameExitNeedSpecialMsg` (`0x00081F`) until `S.P.E.C.I.A.L.` is confirmed, allocate all `40` points across `FO4SF_ProgSpecialPage1Msg` (`0x000870`, `7` buttons) and `FO4SF_ProgSpecialPage2Msg` (`0x000878`, `7` buttons) and press `Confirm` (**do not** cancel 3 times into `special default`), then press `Continue` to ride `+21.6 m` (`ascent carried confirmed`) while `RunSharedMapSetup()` prepares Commonwealth markers, landing at `stage 40 by=Trigger` -> `stage 200 by=Trigger`.
4. *(Optional standalone `B8` neutral-spot fallback check in a separate throwaway session only, never during the `REACHABLE` walk):* Inspect `FO4SF_StartNeutralSpot` (`0x000877` in `FO4SFCoreValues.esm`) via Console if testing neutral-spot staging:
```console
help FO4SF_StartNeutralSpot 4 GLOB
```

### Undo Command (Game Closed)
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/map_markers_install.py uninstall --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
python scripts/game/plugin_toggle.py off --plugins FO4SFBridge.esm --starfield <starfield-dir> --why owner-standing-bridge-off
```

### Required PASS Log Lines (`fo4sf_newgame.0.log`)
```log
FO4SF_NEWGAME rt=<rt> start room ready by=<by> loaded=true cell=<cell> backdrop=empty_cell
FO4SF_NEWGAME rt=<rt> mode choice mode=story survival=0
FO4SF_NEWGAME rt=<rt> start record mode=story story=fo4_commonwealth faction=-1 place=fo4_vault111 survival=0 difficulty=1 backdrop=empty_cell
FO4SF_NEWGAME rt=<rt> stage 5 by=Trigger
FO4SF_NEWGAME rt=<rt> stage 10 by=Trigger
FO4SF_NEWGAME rt=<rt> hold-off pass 2 stopped=<stopped> of <total>
FO4SF_NEWGAME rt=<rt> pod settle ok=true pos=<x> <y> <z> dx=<dx> dy=<dy> drop=<drop> target=<tx> <ty> <tz> heading=<h> loaded=true cell=<cell> world=<world> sample_start=<t0> sample_end=<t1>
FO4SF_NEWGAME rt=<rt> stage 20 by=scene
FO4SF_NEWGAME rt=<rt> pistol filter added base=<form> id=<id>
FO4SF_NEWGAME rt=<rt> console activator registered ref=<ref> id=<id> pos=<x> <y> <z>
FO4SF_NEWGAME rt=<rt> pistol picked item=<form> count=<n>
FO4SF_NEWGAME rt=<rt> cog door activate blocked by=player open_state=<state>
FO4SF_NEWGAME rt=<rt> console refused: no pipboy
FO4SF_NEWGAME rt=<rt> pipboy pickup equipped flag=1 worn=true
FO4SF_NEWGAME rt=<rt> cog door console activated ref=<ref> before=<s0> after=<s1>
FO4SF_NEWGAME rt=<rt> stage 30 by=vault_console
FO4SF_NEWGAME rt=<rt> lift platform waiting cage_door=open
FO4SF_NEWGAME rt=<rt> special box shown box=FO4SF_ProgSpecialPage1Msg buttons=7 unspent=<u0> step=1
FO4SF_NEWGAME rt=<rt> special set S=<s> P=<p> E=<e> C=<c> I=<i> A=<a> L=<l> sum=40 source=Lift
FO4SF_NEWGAME rt=<rt> lift cage_door=closing
FO4SF_NEWGAME rt=<rt> ascent play accepted=true ref=<lift> from=<z0> rise=21.6 seconds=<sec>
FO4SF_NEWGAME rt=<rt> map setup done markers=<n> elapsed=<sec>
FO4SF_NEWGAME rt=<rt> ascent carried confirmed elapsed=<sec> z=<z1>
FO4SF_NEWGAME rt=<rt> surface pre_setposition target=<tx> <ty> <tz> cell=<cell> world=<world>
FO4SF_NEWGAME rt=<rt> stage 40 by=Trigger
FO4SF_NEWGAME rt=<rt> landed z=<z> confirmed=True fallback=false world=<world>
FO4SF_NEWGAME rt=<rt> stage 200 by=Trigger
```

### Negative / FAIL Conditions
- Any stage with `by=other` or `by=fallback`, `cog door open failed state=`, `special default`, `special skipped`, `exit retry`, `exit fallback by=move`, `fallback=True`, or mission objectives appearing before `stage 200`.

### OWNER TEST Items
- Black-fade hold coverage after `LoadingMenu` closes, Vault 111 lighting/atmosphere, gear-door opening animation, `<= 7`-button S.P.E.C.I.A.L. box readability, lift ride feel, and hilltop arrival look.

---

## Card 3 — Story with Survival Across Save and Reload (`S2`, `B14`)

- **Version Note (`S2`):** Picking `Survival: Yes` at New Game start locks Survival ON for that playthrough (`FO4SF_SurvivalStart == 1`, `FO4SF_SurvivalLocked == 1`); picking `Survival: No` leaves Survival unlocked for Gameplay Options toggling.
- **Stage Placeholders:** `<player-bundle-dir>`, `<mapmarkers-stage-dir>`, `<starfield-dir>`
- **Disk Need:** `~4.2 GB` free under `<starfield-dir>/Data` (`0 B` extra on existing Candidate 2b install).
- **Plugin List (`Plugins.txt`, `22` bundle plugins + `FO4SFMapMarkers.esm`):**
  Same 22-plugin `--profile player` list + `*FO4SFMapMarkers.esm` as Card 1.

### Install Command (Game Closed)
```bash
python scripts/core/make_core_bundle.py verify --bundle-dir <player-bundle-dir>
python scripts/game/exp_install.py install --exp-dir <player-bundle-dir> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFRouteLoot.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/game/map_markers_install.py install --dir <mapmarkers-stage-dir> --starfield <starfield-dir>
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <player-bundle-dir> --starfield <starfield-dir>
```

### Console-Free Steps
1. Start a **New Game**, pick **`Story`** and **`Survival: Yes`** (leave Starfield's Gameplay Options Hardcore toggle at `0`).
2. After fade-in at the Vault 111 cryo pod (`stage 10 by=Trigger`), create a manual save, choose **`Quit to Desktop`**, relaunch Starfield, reload that save, and wait `5 s`.

### Undo Command (Game Closed)
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/map_markers_install.py uninstall --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
python scripts/game/plugin_toggle.py off --plugins FO4SFBridge.esm --starfield <starfield-dir> --why owner-standing-bridge-off
```

### Required PASS Log Lines (`fo4sf_newgame.1.log`, `FO4SFHardcore.1.log`, `FO4SFHardcore.0.log`)
```log
FO4SF_NEWGAME rt=<rt> mode choice mode=story survival=1
FO4SFHC rt=<rt> hardcore source gpof=0 start=1 enabled=1 why=start_choice end=true
FO4SFHC rt=<rt> sync reason=start_choice hardcore=1 h=<h> hs=<hs> t=<t> ts=<ts> s=<s> ss=<ss> ammo_burden=<ab> carry_mod=<cm> end_mod=<em> str_mod=<sm> agi_mod=<am> int_mod=<im> ft_blocked=1 sq_env_running=false end=true
FO4SFHC rt=<rt> hardcore source gpof=0 start=1 enabled=1 why=Reload end=true
FO4SFHC rt=<rt> sync reason=Reload hardcore=1 h=<h> hs=<hs> t=<t> ts=<ts> s=<s> ss=<ss> ammo_burden=<ab> carry_mod=<cm> end_mod=<em> str_mod=<sm> agi_mod=<am> int_mod=<im> ft_blocked=1 sq_env_running=false end=true
```

---

## Card 4 — Warfare Start (`S3`, `S5`, `B3`, `B6`)

- **Stage Placeholders:** `<player-bundle-dir>`, `<mapmarkers-stage-dir>`, `<starfield-dir>`
- **Disk Need:** `~4.2 GB` free under `<starfield-dir>/Data` (`0 B` extra on existing Candidate 2b install).
- **Plugin List (`Plugins.txt`, `22` bundle plugins + `FO4SFMapMarkers.esm`):**
  Same 22-plugin `--profile player` list + `*FO4SFMapMarkers.esm` as Card 1.

### Install Command (Game Closed)
```bash
python scripts/core/make_core_bundle.py verify --bundle-dir <player-bundle-dir>
python scripts/game/exp_install.py install --exp-dir <player-bundle-dir> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFRouteLoot.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/game/map_markers_install.py install --dir <mapmarkers-stage-dir> --starfield <starfield-dir>
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <player-bundle-dir> --starfield <starfield-dir>
```

### Console-Free Steps
1. Start a **New Game** in `FO4SF_StartRoomCell` (`0x00081C`), choose **`Warfare`**, difficulty, **`Minutemen`**, **`Sanctuary Hills`** (`minutemen_sanctuary`), and **`Survival: No`** (or `Yes`).
2. Allocate all `40` points across the `<= 7`-button S.P.E.C.I.A.L. boxes (`source=warfare`, **before** `ShowRaceMenu` while `SetInChargen` is `false`; **never** cancelling 3 times into `special default`), then complete pre-world character appearance (`ChargenMenu`, `NOT OURS` this round).
3. Confirm direct exterior fade-in at Sanctuary Hills (`stage 210 by=Trigger`) without ever loading Vault 111, with starter gear, wrist Pip-Boy, `discovered=1` on `MAP`, and zero Story mission objectives.

### Undo Command (Game Closed)
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/map_markers_install.py uninstall --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
python scripts/game/plugin_toggle.py off --plugins FO4SFBridge.esm --starfield <starfield-dir> --why owner-standing-bridge-off
```

### Required PASS Log Lines (`fo4sf_newgame.0.log`, `fo4sf_mission.0.log`, `FO4SFPipboyMenu.log`)
```log
FO4SF_NEWGAME rt=<rt> mode choice mode=warfare survival=<0|1>
FO4SF_NEWGAME rt=<rt> warfare pick faction=0 start=minutemen_sanctuary difficulty=<diff>
FO4SF_NEWGAME rt=<rt> start record mode=warfare story=none faction=0 place=minutemen_sanctuary survival=<0|1> difficulty=<diff> backdrop=empty_cell
FO4SF_NEWGAME rt=<rt> special set S=<s> P=<p> E=<e> C=<c> I=<i> A=<a> L=<l> sum=40 source=warfare
FO4SF_NEWGAME rt=<rt> warfare creator open mode=2
FO4SF_NEWGAME rt=<rt> warfare creator closed
FO4SF_NEWGAME rt=<rt> warfare gear n=4
FO4SF_NEWGAME rt=<rt> warfare move ok=true marker=<marker> dist=<dist> z=<z>
FO4SF_NEWGAME rt=<rt> map setup done markers=<n> elapsed=<sec>
FO4SF_NEWGAME rt=<rt> warfare standing slot=0 fame=<fame> infamy=<inf> karma=<karma> squad_cap=4
FO4SF_NEWGAME rt=<rt> stage 210 by=Trigger
FO4SF_NEWGAME rt=<rt> mission gate mode=2 started=false
FO4SF_MISSION rt=<rt> mission gate mode=2 started=false
step=map_markers n=<k> discovered=1 undiscovered=<u_cnt> player_idx=<idx> corners_set=3/3 read_back=match
```

---

## Card 5 — Console-Free Mission Walk, Desktop-Quit Reload & Beginning Verifier (`M1`–`M6`, `B6`–`B12`, `V1`)

- **Exact Quit Mode Required (`B7`):** At Step 4 (`stage 20` in Concord), save the game, choose **`Quit to Desktop`** (do **not** use `Quit to Main Menu`), and relaunch Starfield. Relaunching rotates `.0.log` -> `.1.log` (`fo4sf_newgame.1.log` + `fo4sf_newgame.0.log`, `fo4sf_mission.1.log` + `fo4sf_mission.0.log`), and `check_beginning_pilot.py` reads all rotated files per channel in chronological order (`*.3.log` -> `*.2.log` -> `*.1.log` -> `*.0.log`).
- **Stage Placeholders:** `<player-bundle-dir>`, `<mapmarkers-stage-dir>`, `<starfield-dir>`, `<log-dir>`, `<newgame-log-1>`, `<newgame-log-0>`, `<mission-log-1>`, `<mission-log-0>`
- **Disk Need:** `~4.2 GB` free under `<starfield-dir>/Data` (`0 B` extra when continuing directly from Card 2).
- **Plugin List (`Plugins.txt`, `22` bundle plugins + `FO4SFMapMarkers.esm`):**
  Same 22-plugin `--profile player` list + `*FO4SFMapMarkers.esm` as Card 1.

### Install & Post-Run Multi-Log Verifier Commands (Game Closed)
```bash
python scripts/core/make_core_bundle.py verify --bundle-dir <player-bundle-dir>
python scripts/game/exp_install.py install --exp-dir <player-bundle-dir> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFRouteLoot.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/game/map_markers_install.py install --dir <mapmarkers-stage-dir> --starfield <starfield-dir>
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <player-bundle-dir> --starfield <starfield-dir>
python scripts/testing/check_beginning_pilot.py check-logs --log-dir <log-dir> --require-all-pass
python scripts/testing/check_beginning_pilot.py check-logs --newgame-log <newgame-log-1> <newgame-log-0> --mission-log <mission-log-1> <mission-log-0> --require-all-pass
```

### Console-Free Steps (Continuing Directly from Card 2 `stage 200 by=Trigger`)
1. **Silent start & route-only loot (`M1`, `M2`, `B10`, `B12`):** Confirm no Concord objective shows at hilltop landing while `FO4SF_Codsworth01` (`0x000816`) displays its Sanctuary objective (`B12`: cleared automatically via `codsworth01 objective 10 cleared by=concord` if the player bypasses Sanctuary to Concord). Along the `<= 600 m` Sanctuary -> Red Rocket -> Concord corridor, open at least `3` containers (`460` corridor `REFR` overrides pointing to `83` dedicated `FO4SFRouteLoot.esm` `CONT` bases, `439` non-credit; `0` `FO4TerrainCore.esm` `CONT` overrides so off-route containers stay unchanged).
2. **Codsworth Sanctuary talk (`M6`, `B6`):** Press **`E`** on brushed-steel Codsworth (`0x000811`) in Sanctuary and complete Choice 4 (`codsworth01 stage 100 by=info` -> `min00 given by=codsworth` -> `stage 10 by=info`).
3. **Concord raider fight + `Quit to Desktop` reload (`M3`, `B7`, `B9`):** Engage the Concord raiders (`stage 20 by=Trigger`), create a manual save mid-fight, select **`Quit to Desktop`**, relaunch Starfield, reload that save (`reload mission stage=20 relocate_fails=0`), and clear the raiders (`stage 30 by=Trigger`; any unreachable `> 60 s` or rescued-but-stuck `< 2 m` undamaged `60 s` raider stops combat, disables, and logs `wfc01 raider cleared <absent|stuck> ... disabled=true`).
4. **Preston `DialogueMenu` final exchange (`M4`, `B6`, `B11`):** Press **`E`** on Preston (`0x000802`) and complete **all 3** `DialogueMenu` exchanges so exchange 3 (`0x092A`) sets **`stage 35 by=info`**, prints `preston talk end info=0x092A -> stage 40`, and advances to **`stage 40 by=info`** -> `100` placeholder credits -> **`stage 200 by=Trigger`**. *(Preston remains held at the museum door after `stage 200`; `"Preston's group moving to Sanctuary"` is **`NOT BUILT`**.)*
5. **Sanctuary workbench hand-over (`M5`, `B6`):** Follow `FO4SF_Sanctuary01` (`0x000817`) back to Sanctuary workbench `0x005C50` (`0250FE`) and press **`E`** (`sanctuary01 stage 100 by=bench`, `min01 bench activated -> stage 100`), then quit and run `check_beginning_pilot.py check-logs --log-dir <log-dir> --require-all-pass`.

### Undo Command (Game Closed)
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/map_markers_install.py uninstall --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
python scripts/game/plugin_toggle.py off --plugins FO4SFBridge.esm --starfield <starfield-dir> --why owner-standing-bridge-off
```

### Required PASS Log Lines (`fo4sf_mission.1.log` + `fo4sf_mission.0.log`)
```log
FO4SF_MISSION rt=<rt> mission gate mode=1 started=true
FO4SF_MISSION rt=<rt> codsworth01 stage 10 by=Trigger
FO4SF_MISSION rt=<rt> codsworth01 stage 100 by=info
FO4SF_MISSION rt=<rt> min00 given by=codsworth
FO4SF_MISSION rt=<rt> stage 10 by=info
FO4SF_MISSION rt=<rt> codsworth talk end -> min00 stage 10
FO4SF_MISSION rt=<rt> codsworth01 complete choices=<n> concord_pointed=true
FO4SF_MISSION rt=<rt> stage 20 by=Trigger
FO4SF_MISSION rt=<rt> reload mission stage=20 relocate_fails=0
FO4SF_MISSION rt=<rt> stage 30 by=Trigger
FO4SF_MISSION rt=<rt> preston talk scene triggered stage=30
FO4SF_MISSION rt=<rt> stage 35 by=info
FO4SF_MISSION rt=<rt> preston talk end info=0x092A -> stage 40
FO4SF_MISSION rt=<rt> stage 40 by=info
FO4SF_MISSION rt=<rt> reward credits=100
FO4SF_MISSION rt=<rt> stage 200 by=Trigger
FO4SF_MISSION rt=<rt> sanctuary01 stage 10 by=Trigger
FO4SF_MISSION rt=<rt> sanctuary01 init stage=10 bench_ref=0x005C50
FO4SF_MISSION rt=<rt> sanctuary01 stage 100 by=bench
FO4SF_MISSION rt=<rt> min01 bench activated -> stage 100
FO4SF_MISSION rt=<rt> sanctuary01 bench_activated=true ref=<ref> complete=true
```

### Negative / FAIL Conditions
- Any required stage missing `by=` or carrying `by=other` or `by=fallback`, Preston scene ending before exchange 3 (`preston talk scene ended stage=30 end_info=False`), `exit fallback by=move`, `special default`, mission starting before NewGame `stage 200`, or `check-logs --require-all-pass` exiting non-zero.
