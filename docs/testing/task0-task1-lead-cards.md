# Task 0 & Task 1 Lead Verification Cards (`gemini/core-integration`)

Truth labels used throughout: **`REACHABLE`**, **`TEST-STATION`**, **`RECORDS ONLY`**, **`TOOLING`**, **`NOT BUILT`**, **`NOT WIRED`**.

> **Save & Master Break Notice:** The rebuilt `FO4SFNewGame.esm` masters `FO4SFCoreValues.esm` and requires a **NEW GAME** (old saves lose S.P.E.C.I.A.L., skills, karma, rads, and survival meters).

---

## Card A — `G4` List-Dialogue Scene & Speaker Route Proof (`TEST-STATION`)

- **Purpose:** Verify in game that pressing `E` on `FO4SF_ListSpeakerNpc` (`0x000806` in `FO4SFListDialogue.esm`, placed as persistent ref `0x000808` `FO4SF_ListSpeakerRef` inside lit `FO4SF_ListTalkCell` `0x000807`, bound to `Optional` alias `0` `Speaker` via `ForcedReference -> 0x000808`, allied with the player via `FO4SF_ListSpeakerFaction` `0x000805`, and reusing a human template whose own `VoiceType` carries `AllowDefaultDialog`) opens Starfield's `DialogueMenu`, renders silent-player list choices, and sets quest `FO4SF_ListDialogueQuest` (`0x000810`) outcome stages on selection.
- **Why Session 2 Saw No `init` Log and Silent `TALK` (Fixed Here):**
  1. In `--profile player` (`--no-test-cell`), `FO4SF_ListDialogueQuest` had `0` aliases so `StartGameEnabled` started it immediately and logged `init`. In `--profile test`, alias `0` (`Speaker`) previously used `UniqueActor` without `QuestReferenceAlias.Flag.Optional` on an NPC inside an unloaded interior cell; when `UniqueActor` resolution failed at startup, Starfield aborted starting the quest (`IsRunning() == false`), so neither `OnQuestInit()` nor `FO4SF_ListTopScene` (`0x2814` top-level activate scene) could run. Alias `0` now uses `ForcedReference -> 0x000808` + `QuestReferenceAlias.Flag.Optional`, and `FO4SF_ListDialogueQuest.psc` logs `init` unconditionally on `OnQuestStarted` / `OnQuestInit` / `OnStageSet` and runs `PollStages()` directly inside `OnStageSet`.
  2. `FO4SF_ListTalkCell` (`0x000807`) now carries explicit `CellLighting` (`XCLL`) plus `4` `OmniLight` placements (front key `(0, 1.4, 2.2)` between player and speaker, left/right fills, and back rim) so the speaker is evenly lit rather than silhouetted.
- **Wiring Status:** List dialogue stays a **`TEST-STATION`** cell this round; it is **`NOT WIRED`** to Preston or Codsworth.
- **Stage Placeholders:** `<test-bundle-dir>`, `<starfield-dir>`, `<quest-hex>`
- **Disk Need:** `~4.2 GB` free under `<starfield-dir>/Data` (`FO4ActorRaider - Main.ba2` plus `22` `.esm` plugins; `FO4SFCoreValues.esm` is built with `--test-mode 1` so `FO4SF_TestModeEnabled` `0x000860` defaults to `1.0`).
- **Plugin List (`Plugins.txt`, `--profile test`, `22` plugins):**
  `FO4ActorRaider.esm,FO4TerrainCore.esm,FO4SFMission.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFCoreCandidate.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm`

### Install Command (Game Closed)
```bash
python scripts/core/make_core_bundle.py verify --bundle-dir <test-bundle-dir>
python scripts/game/exp_install.py install --exp-dir <test-bundle-dir> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4SFMission.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFCoreCandidate.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
```

### In-Game Steps & Console Commands (`P3` Runtime FormID Read + Zero `M`/`N`/`V` Console Lines)
1. Start a new session on the `--profile test` bundle (`FO4SF_TestModeEnabled` `0x000860` defaults to `1.0`).
2. **Read `<quest-hex>` in game (zero `M`, `N`, or `V` typed; Starfield strips mod `QUST` EditorIDs):** Open Console and run **`help "List Dialogue" 4 QUST`**. Starfield prints `QUST: (<quest-hex>) 'FO4SF Silent-Player List Dialogue'` — its low `6` hex digits are always `000810` (`12000810` when `FO4SFListDialogue.esm` is at `0x12`, or `11000810` on `22`-plugin builds). Run `sqs <quest-hex>` (or `bat carda0` to run `sqv 12000810` from `<starfield-dir>/carda0.txt` without typing `v`) to confirm `Enabled? Yes`, `State: Running`, and `REF 'Speaker'->'(...000808)'`.
3. Move to `FO4SF_ListTalkCell` (`0x000807`), set baseline low sheet (`setstage <quest-hex> 10` / `bat carda1`), press `E` on `Relay Operator` (`0x000808`) to exercise failing checks (`21`, `31`), set qualified high sheet (`setstage <quest-hex> 15` / `bat carda2`), press `E` again to exercise passing checks (`20`, `22`, `30`, `40`, `50`) and goodbye (`60`), then restore the player sheet (`setstage <quest-hex> 70` / `bat carda3`):
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
; <starfield-dir>/carda0.txt (substitute high byte from help "List Dialogue" 4 QUST if != 12)
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

### Undo Command (Game Closed — Release Any `plugin_toggle.py` Hold First)
```bash
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
```

### Required PASS Log Lines (`FO4SFListDialogue.0.log`)
```log
FO4SFLIST rt=<rt> init speaker_present=True arrival_present=True end=true
FO4SFLIST rt=<rt> eval phase=baseline_low speech=<sp> speech50=fail science=<sc> science40=fail strength=<st> strength7=fail bg_vaultdweller=locked trait_goodnatured=locked end=true
FO4SFLIST rt=<rt> choice_stage stage=21 tag=Speech_50 outcome=fail end=true
FO4SFLIST rt=<rt> choice_stage stage=31 tag=Strength_7 outcome=fail end=true
FO4SFLIST rt=<rt> eval phase=qualified_high speech=<sp> speech50=pass science=<sc> science40=pass strength=<st> strength7=pass bg_vaultdweller=pass trait_goodnatured=pass end=true
FO4SFLIST rt=<rt> choice_stage stage=20 tag=Speech_50 outcome=pass end=true
FO4SFLIST rt=<rt> choice_stage stage=22 tag=Science_40 outcome=pass end=true
FO4SFLIST rt=<rt> choice_stage stage=30 tag=Strength_7 outcome=pass end=true
FO4SFLIST rt=<rt> choice_stage stage=40 tag=Vault_Dweller outcome=pass end=true
FO4SFLIST rt=<rt> choice_stage stage=50 tag=Good_Natured outcome=pass end=true
FO4SFLIST rt=<rt> choice_stage stage=60 tag=Plain_Goodbye outcome=exit end=true
FO4SFLIST rt=<rt> eval phase=reset speech=<sp> speech50=<s50> science=<sc> science40=<sc40> strength=<st> strength7=<st7> bg_vaultdweller=<bg> trait_goodnatured=<tr_state> end=true
FO4SFLIST rt=<rt> summary ok=true host_menu=DialogueMenu replaced_swf=false end=true
```

### Owner / Visual Check
- Pressing `E` on `FO4SF_ListSpeakerNpc` (`0x000808`) opens `DialogueMenu` immediately with readable choice rows and releases camera/controls cleanly on exit.

---

## Card B — `1a` / `1c` / `1d` F7 `STAT` Crash-Proof Isolation (`REACHABLE` Key / `TEST-STATION` Isolation)

- **Purpose:** Prove in isolation (`PopulateInCall=0`, `LateInvalidate=0`, `StatActions=0`, `InvDataAnswers=0`, `RequirePickup=0`) that the plain `Object` `BGSCodeObj` holder (`CreateObject`, never `CreateFunction`) eliminates the `PerksTab` `StopPerkSound` crash and survives `10` open/close cycles cleanly.
- **Stage Placeholders:** `<player-bundle-dir>`, `<pipboy-stage-dir>`, `<stage-ini-path>`, `<starfield-dir>`
- **Disk Need:** `~4.2 GB` free under `<starfield-dir>/Data` plus `~3 MB` under `<starfield-dir>/Data/SFSE/Plugins` (installed and backed up via `make_core_bundle.py sidecar-install` -> `Data/FO4SFSidecar.install.json`, keeping format-5 `versionlib-1-16-244-0.bin` untouched beside `FO4SFPipboyMenu.dll`; `<player-bundle-dir>/sfse_sidecar/reputation/*` is reference-only and **not installed**).
- **Plugin List (`Plugins.txt`, `--profile player`, `21` plugins):**
  `FO4ActorRaider.esm,FO4TerrainCore.esm,FO4SFMission.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm`

### Install, Sidecar & INI Generation Commands (Game Closed)
```bash
python scripts/core/make_core_bundle.py verify --bundle-dir <player-bundle-dir>
python scripts/game/exp_install.py install --exp-dir <player-bundle-dir> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4SFMission.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <player-bundle-dir> --starfield <starfield-dir>
python scripts/ui/make_pipboy_stage_ini.py --stage <pipboy-stage-dir> --out <stage-ini-path> --arm 0 --omit StopPerkSound --allow-omit StopPerkSound
python scripts/ui/make_pipboy_stage_ini.py --stage <pipboy-stage-dir> --out <stage-ini-path> --arm 0
```

### In-Game Steps
1. **Part 1 (Negative `StopPerkSound` omission):** With the `--arm 0 --omit StopPerkSound --allow-omit StopPerkSound` INI written over `<starfield-dir>/Data/SFSE/Plugins/FO4SFPipboyMenu.ini` (`sidecar-install` already backed up any pre-existing owner `FO4SFPipboyMenu.ini` bytes), press `F7`, cycle `STAT` subtabs (`Status`, `SPECIAL`, `Perks`), hold `10 s`, and close with `Tab` or `Esc`.
2. **Part 2 (Full `49`-name INI, `10` cycles):** Write the full `49`-name `--arm 0` isolation INI over `<starfield-dir>/Data/SFSE/Plugins/FO4SFPipboyMenu.ini`, press `F7`, verify `E` on `STAT` does **not** switch top-level pages, close with `Tab`/`Esc`, and repeat `10` times.
3. Open Console (`` ` ``) and press `m`, `v`, and `n`; confirm neither Pip-Boy nor combat hotkeys fire while `Console` is open.

### Undo Command (Game Closed — Restore Sidecar Backups & Release Any `plugin_toggle.py` Hold)
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
```

### Required PASS Log Lines (`FO4SFPipboyMenu.log` & `FO4SFCombat.log`)
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
```

---

## Card C — `1g` Starfield Scanner & Map Menus Block (`TEST-STATION`)

- **Purpose:** Verify that `GalaxyStarMapMenu`, `SurfaceMap`, and `MapMenu` each log `step=starmap_block_install menu=<name> found=<0|1>` at startup and are blocked via per-slot null-menu creation (`MapBlockStarMap=1` default, `kMaxMapMenus = 16`) without crashing when each map shortcut key is pressed, and that `FO4SF_NewGameQuest` logs its hand-scanner input-layer block.
- **Same-Session Hide-Only Fallback (`MapBlockStarMap=0`):** If returning an empty `Ptr<IMenu>` from `route=create` ever misbehaves in game, edit `<starfield-dir>/Data/SFSE/Plugins/FO4SFPipboyMenu.ini` (game closed), set `MapBlockStarMap=0`, and rerun in the same install: `SuppressVanillaMapMenus()` hides any opened map menu on the main thread via `kHide` without replacing its creator (`step=map_suppress n=<k> name=<menu> sent=hide`).
- **Stage Placeholders:** `<player-bundle-dir>`, `<starfield-dir>`
- **Disk Need:** `~4.2 GB` free under `<starfield-dir>/Data` (`0 B` extra when run in the same session as Card B).
- **Plugin List (`Plugins.txt`, `--profile player`, `21` plugins):**
  `FO4ActorRaider.esm,FO4TerrainCore.esm,FO4SFMission.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm`

### Install & Sidecar Command (Game Closed)
```bash
python scripts/core/make_core_bundle.py verify --bundle-dir <player-bundle-dir>
python scripts/game/exp_install.py install --exp-dir <player-bundle-dir> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4SFMission.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <player-bundle-dir> --starfield <starfield-dir>
```

### In-Game Steps
1. Outdoors in a new `--profile player` session (`MapBlockStarMap=1`), press the Star Map, Surface Map, and Planet Map keys once each, and press `F` (hand scanner).
2. Confirm no Starfield map menu opens, no crash occurs, and zero `"FO4SF"` developer banner text (`1h`) appears on screen.
3. *(Fallback only if `MapBlockStarMap=1` needs bypass)* Set `MapBlockStarMap=0` in `FO4SFPipboyMenu.ini`, relaunch, press the map keys once, and verify `step=map_suppress n=<k> name=<menu> sent=hide`.

### Undo Command (Game Closed — Restore Sidecar Backups & Release Any `plugin_toggle.py` Hold)
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
```

### Required PASS Log Lines (`FO4SF_NewGame.0.log` & `FO4SFPipboyMenu.log`)
```log
blocked input=handscanner
step=starmap_block_install menu=<menu> found=1 slot=<slot> orig_rva=<rva>
step=starmap_block_install menu=<menu> found=0
step=starmap_blocked n=<k> blocked menu=<menu> route=create
```

### Fallback PASS Log Line (`MapBlockStarMap=0` Hide-Only Mode, `FO4SFPipboyMenu.log`)
```log
step=map_suppress n=<k> name=<menu> sent=hide
```

---

## Card D — `N1`, `1b`, `1i`, `1j`, `1k` Player-Build Pip-Boy Arm (`Arm=1`), In-Call Vitals, `STAT` Aid Actions, `INV`/`DATA` Answers & Standalone `SpecialMenu` (`REACHABLE` Arm / `TEST-STATION` Opt-In Switches)

- **Default Safety & Scope Notes:**
  - **Card B passed in game (`Session 1`, `10/10` cycles):** `make_pipboy_stage_ini.py` now ships **`Arm=1`** by default in the player build (`Stage=2`, `Movie=FO4SF_Fo4Shell`, `Key=0x76` `F7`, `Pause=1` — zero `[Kit]` or `[Page ...]` entries), while keeping `PopulateInCall=0`, `StatActions=0`, `InvDataAnswers=0`, and `SpecialMenu=0` opt-in for Card D.
  - Native `FO4SF_SpecialMenu` is **`NOT WIRED`** to the Vault 111 lift or start flow this round (`R14`; testable standalone only via `SpecialMenu=1` and `SpecialKey`). It refuses increments when `pointsRemaining <= 0` and writes chosen values to `FO4SFCoreValues.esm` (`0x000880..0x000887`) for `FO4SF_ProgressionQuest` to apply (`source=fo4_menu`).
  - `WorkshopsList` on `DATA` is an explicit static **placeholder** (`Sanctuary Hills (Placeholder)`) this round.
  - `DropItem` (`inv_drop`, documented in `docs/ui/pipboy-inv-drop-note.md`) is withheld from Card D until tried separately on a throwaway item.
  - Power armor is **`NOT REACHABLE`** in `--profile player` (no frame is placed in the world outside the `--profile test` cell).
- **Stage Placeholders:** `<test-bundle-dir>`, `<pipboy-stage-dir>`, `<stage-ini-path>`, `<starfield-dir>`
- **Disk Need:** `~4.2 GB` free under `<starfield-dir>/Data` plus `~5 MB` under `<starfield-dir>/Data/SFSE/Plugins`.
- **Plugin List (`Plugins.txt`, `--profile test`, `22` plugins):**
  `FO4ActorRaider.esm,FO4TerrainCore.esm,FO4SFMission.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFCoreCandidate.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm`

### N1 — Player-Build First-Person Pip-Boy Arm (`Arm=1`, `idleexaminewatch`, `Stage=2` `FO4SF_Fo4Shell` Only)
- **Shipped INI Lines (Generated by Default in `make_pipboy_stage_ini.py`, Never `[Kit]` / `[Page ...]`):**
```ini
Stage=2
Movie=FO4SF_Fo4Shell
Key=0x76
Pause=1
Arm=1
ArmRaiseIdle=idleexaminewatch
ArmRaiseMs=2000
ArmLowerIdle=
ArmLowerEvent=
ArmLowerMs=3500
ArmRetryMs=2000
```
- **Why These Timings:** `idleexaminewatch` (`0x000C154F`) brings the left wrist face-on at `~1.9 s–4.3 s`, so `ArmRaiseMs=2000` opens `FO4SF_Fo4Shell` as the wrist settles in view and `Pause=1` holds that frame while browsing. Leaving `ArmLowerIdle=` and `ArmLowerEvent=` empty lets closing (`Tab`/`Esc`/`F7`) unpause the clip to carry on and lower naturally over the remaining `~3.5 s` (`ArmLowerMs=3500` guards re-entry until lowered; `ArmRetryMs=2000` retries a transient `result=0` every `100 ms` up to `2.0 s` before opening immediately).
- **Proved Offline vs. Only In Game:**
  - **Proved offline:** `FO4SFPipboyMenu.dll` compiles cleanly against `1.16.244` RVAs (`Actor::PlayIdle` `102136`, context `35720`, graph sink `123821`/`123822`, `0x000C154F` `idleexaminewatch` fallback), `A4` load-screen sink generation tracking (`ArmPollLoadingTransitionMainThread` + `g_armGraphLoadGen`) resets watched graph pointers and cancels in-flight raises across loads without calling `UnregisterSink` on freed graphs, `g_bootReopenPage` suppresses `ArmMessage(false)` across `pipboybootsequence` -> `FO4SF_Fo4Shell` reopen so `BootOnFirstOpen=1` never triggers a `3500 ms` lower lockout, `ArmKey` checks `Console` and `RequirePickup` on the main thread before raising, and `ArmShow` unconditionally opens `FO4SF_Fo4Shell` even when `g_armState != 1` or `accepted=0` (`R10`: a missing or refused animation never blocks the Pip-Boy).
  - **Only the game can show:** Live `1stPerson` animation graph acceptance (`accepted=1`) on `F7` after pickup, visual alignment of `ArmRaiseMs=2000` when `Pause=1` freezes the wrist, natural lower when unpaused on close, and third-person / weapon-drawn `accepted=0` immediate open.
- **N1 Required PASS Log Lines (Raise, Page Showing, Lower & Failed-Raise `R10` Fallback in `FO4SFPipboyMenu.log`):**
```log
step=arm_raise n=<k> result=1 try=1 accepted=1 t_ms=<ms>
step=arm_raise_done n=<k> result=1 accepted=1 tries=<t> waited_ms=<w> show_in_ms=2000 t_ms=<ms>
step=arm_show n=<k> sent=show raise=1 arm_ready=1 t_ms=<ms>
step=arm_shown n=<k> accepted=1 t_ms=<ms>
step=arm_lower n=<k> send=none (the raise's clip carries on) accepted=1 lock_ms=3500 t_ms=<ms>
step=arm_raise_done n=<k> result=<gave_up|refused> accepted=0 tries=<t> waited_ms=<w> show_in_ms=0 t_ms=<ms>
step=arm_show n=<k> sent=show raise=<gave_up|refused> arm_ready=<0|1> t_ms=<ms>
step=arm_shown n=<k> accepted=0 t_ms=<ms>
step=arm_lower n=<k> send=none (the raise's clip carries on) accepted=0 lock_ms=0 t_ms=<ms>
```
- **OWNER TEST (Visual & Feel — Recorded by Lead):**
  1. In first person with weapon holstered after picking up the Pip-Boy, press `F7`: judge whether `idleexaminewatch` raises the wrist to a natural angle at `ArmRaiseMs=2000` before `FO4SF_Fo4Shell` (`STAT`) appears, and whether `Tab` / `F7` lowers the arm smoothly over `ArmLowerMs=3500`.
  2. In third person or with a weapon drawn, press `F7`: confirm the Pip-Boy still opens cleanly without hanging (`accepted=0` fallback) and closes with `0 ms` lock.

### Install, Sidecar & Opt-In INI Commands (Game Closed)
- **Sidecar & `reputation/` Note (`H3`):** `sidecar-install` installs `<test-bundle-dir>/sfse_sidecar/SFSE/Plugins/*` with SHA-256 byte backups (`Data/FO4SFSidecar.install.json`) and restores/removes them on `sidecar-undo`. `<test-bundle-dir>/sfse_sidecar/reputation/*` (`FO4SFPipboyKit.ini` / `FO4SFPipboyReputation.*`) is reference-only and **not installed** into `<starfield-dir>/Data`.
```bash
python scripts/core/make_core_bundle.py verify --bundle-dir <test-bundle-dir>
python scripts/game/exp_install.py install --exp-dir <test-bundle-dir> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4SFMission.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFCoreCandidate.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <test-bundle-dir> --starfield <starfield-dir>
python scripts/ui/make_pipboy_stage_ini.py --stage <pipboy-stage-dir> --out <stage-ini-path> --populate-in-call 1 --arm 1 --stat-actions 1 --inv-data-answers 1 --special-menu 1 --special-max-points 40
```

### Undo Command (Game Closed — Restore Sidecar Backups & Release Any `plugin_toggle.py` Hold)
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
```

### Required PASS Log Lines (`FO4SFPipboyMenu.log`)
```log
step=populate page=<p> tab=<t> hp=<cur>/<max> ap=<cur>/<max> level=<lvl> special=<s>,<p>,<e>,<c>,<i>,<a>,<l> source=<source> paused=<0|1>
step=arm_raise n=<k> result=<res> try=1 accepted=1 t_ms=<ms>
step=arm_raise_done n=<k> result=<res> accepted=1 tries=<t> waited_ms=<w> show_in_ms=<s> t_ms=<ms>
step=arm_lower n=<k> send=none (the raise's clip carries on) accepted=<0|1> lock_ms=<ms> t_ms=<ms>
step=arm_lower n=<k> send=<idle|event> result=<res> try=1 accepted=1 t_ms=<ms>
step=code_call n=<k> name=UseStimpak args=0
step=stat_use item=<hex> hp_before=<X> hp_after=<Y> used=1
step=code_call n=<k> name=UseRadaway args=0
step=stat_use item=<hex> rads_before=<X> rads_after=<Y> used=1
step=stat_sound action=play_perk_sound name=<name>
step=stat_sound action=stop_perk_sound stopped=<0|1>
step=stat_sound action=play_small_transition arg=<arg>
step=stat_stub name=ShowPerksMenu
step=inv_fill when=<when> tab=<T> filter=<hex> n=<N> total_count=<total>
step=inv_select node=<node> form=<hex> wt=<wt> val=<val>
step=inv_equip node=<node> form=<hex> action=<equip|unequip> ok=<0|1>
step=quests_fill when=<when> tab=<T> n=<Q> active=<A> completed=<C>
step=special_done sum=<sum> max_points=<max> written=<w> values=<s>,<p>,<e>,<c>,<i>,<a>,<l> name="<name>" source=<source>
FO4SFPROG rt=<rt> special set S=<s> P=<p> E=<e> C=<c> I=<i> A=<a> L=<l> sum=<sum> source=fo4_menu end=true
```

---

## Explicitly `NOT BUILT` / `NOT WIRED` in `gemini/core-integration`
- **List Dialogue (`G4`):** `TEST-STATION` cell only (`FO4SF_ListTalkCell` `0x000807`); **`NOT WIRED`** to Preston or Codsworth.
- **Native `FO4SF_SpecialMenu` (`UI-3`):** **`NOT WIRED`** to the Vault 111 lift this round (`R14`).
- **Power Armor (`player` profile):** **`NOT REACHABLE`** in `--profile player` (no frame is placed).
- **`1l` (`docs/ui/fo4-menus-hosting.md` & `docs/ui/fo4-hud-options.md`):** Design option notes only (`TOOLING` / docs; nothing built until owner picks).
