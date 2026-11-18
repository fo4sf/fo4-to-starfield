# Task 0 & Task 1 Lead Verification Cards (`gemini/core-integration`)

Truth labels used throughout: **`REACHABLE`**, **`TEST-STATION`**, **`RECORDS ONLY`**, **`TOOLING`**, **`NOT BUILT`**, **`NOT WIRED`**.

> **Save & Master Break Notice:** The rebuilt `FO4SFNewGame.esm` masters `FO4SFCoreValues.esm` and requires a **NEW GAME** (old saves lose S.P.E.C.I.A.L., skills, karma, rads, and survival meters).

---

## Card A — `G4` List-Dialogue Scene & Speaker Route Proof (`TEST-STATION`)

- **Purpose:** Verify in game that pressing `E` on `FO4SF_ListSpeakerNpc` (`0x000806` in `FO4SFListDialogue.esm`, placed as ref `0x000808` inside `FO4SF_ListTalkCell` `0x000807`, allied with the player via `FO4SF_ListSpeakerFaction` `0x000805` and reusing a human template whose own `VoiceType` carries `AllowDefaultDialog`) opens Starfield's `DialogueMenu`, renders silent-player list choices, and sets quest `FO4SF_ListDialogueQuest` (`0x000810`) outcome stages on selection.
- **Wiring Status:** List dialogue stays a **`TEST-STATION`** cell this round; it is **`NOT WIRED`** to Preston or Codsworth.
- **Stage Placeholders:** `<test-bundle-dir>`, `<starfield-dir>`
- **Disk Need:** `~4.2 GB` free under `<starfield-dir>/Data` (`FO4ActorRaider - Main.ba2` plus `22` `.esm` plugins; `FO4SFCoreValues.esm` is built with `--test-mode 1` so `FO4SF_TestModeEnabled` `0x000860` defaults to `1.0`).
- **Plugin List (`Plugins.txt`, `--profile test`, `22` plugins):**
  `FO4ActorRaider.esm,FO4TerrainCore.esm,FO4SFMission.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFCoreCandidate.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm`

### Install Command (Game Closed)
```bash
python scripts/core/make_core_bundle.py verify --bundle-dir <test-bundle-dir>
python scripts/game/exp_install.py install --exp-dir <test-bundle-dir> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4SFMission.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFCoreCandidate.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
```

### In-Game Steps & Console Commands
1. Start a new session on the `--profile test` bundle (`FO4SF_TestModeEnabled` `0x000860` in `FO4SFCoreValues.esm` is `1.0`; if running against an unbundled manual install where test mode is `0`, inspect the runtime FormID via `help FO4SF_TestModeEnabled 4 GLOB` and set it to `1` in Console).
2. Move to the list-dialogue room (`FO4SF_ListTalkCell` `0x000807`, arrival marker `0x000809`, `COC` marker `0x00080A`), snapshot the low baseline sheet (`stage 10`), press `E` on `FO4SF_ListSpeakerNpc` (`0x000808`) to exercise failing checks (`21`, `31`), qualify the high sheet (`stage 15`), press `E` again to exercise passing checks (`20`, `22`, `30`, `40`, `50`) and goodbye (`60`), then restore the player sheet (`stage 70`):
```console
help FO4SF_TestModeEnabled 4 GLOB
coc FO4SF_ListTalkCell
setstage FO4SF_ListDialogueQuest 10
setstage FO4SF_ListDialogueQuest 15
setstage FO4SF_ListDialogueQuest 70
```

### Undo Command (Game Closed)
```bash
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
- **Disk Need:** `~4.2 GB` free under `<starfield-dir>/Data` plus `~3 MB` under `<starfield-dir>/Data/SFSE/Plugins` (copy `<player-bundle-dir>/sfse_sidecar/SFSE/Plugins/*` and format-5 `versionlib-1-16-244-0.bin` beside `FO4SFPipboyMenu.dll`).
- **Plugin List (`Plugins.txt`, `--profile player`, `21` plugins):**
  `FO4ActorRaider.esm,FO4TerrainCore.esm,FO4SFMission.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm`

### Install & INI Generation Commands (Game Closed)
```bash
python scripts/core/make_core_bundle.py verify --bundle-dir <player-bundle-dir>
python scripts/game/exp_install.py install --exp-dir <player-bundle-dir> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4SFMission.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/ui/make_pipboy_stage_ini.py --stage <pipboy-stage-dir> --out <stage-ini-path> --omit StopPerkSound --allow-omit StopPerkSound
python scripts/ui/make_pipboy_stage_ini.py --stage <pipboy-stage-dir> --out <stage-ini-path>
```

### In-Game Steps
1. **Part 1 (Negative `StopPerkSound` omission):** With the `--omit StopPerkSound --allow-omit StopPerkSound` INI copied to `<starfield-dir>/Data/SFSE/Plugins/FO4SFPipboyMenu.ini`, press `F7`, cycle `STAT` subtabs (`Status`, `SPECIAL`, `Perks`), hold `10 s`, and close with `Tab` or `Esc`.
2. **Part 2 (Full `49`-name INI, `10` cycles):** Copy the full `49`-name INI to `<starfield-dir>/Data/SFSE/Plugins/FO4SFPipboyMenu.ini`, press `F7`, verify `E` on `STAT` does **not** switch top-level pages, close with `Tab`/`Esc`, and repeat `10` times.
3. Open Console (`` ` ``) and press `m`, `v`, and `n`; confirm neither Pip-Boy nor combat hotkeys fire while `Console` is open.

### Undo Command (Game Closed)
```bash
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

- **Purpose:** Verify that `GalaxyStarMapMenu`, `SurfaceMap`, and `MapMenu` are blocked via per-slot null-menu creation (`MapBlockStarMap=1`, `kMaxMapMenus = 16`; set `MapBlockStarMap=0` in `FO4SFPipboyMenu.ini` for hide-only fallback in the same session if needed) without crashing when each map shortcut key is pressed, and that `FO4SF_NewGameQuest` logs its hand-scanner input-layer block.
- **Stage Placeholders:** `<player-bundle-dir>`, `<starfield-dir>`
- **Disk Need:** `~4.2 GB` free under `<starfield-dir>/Data` (`0 B` extra when run in the same session as Card B).
- **Plugin List (`Plugins.txt`, `--profile player`, `21` plugins):**
  `FO4ActorRaider.esm,FO4TerrainCore.esm,FO4SFMission.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm`

### Install Command (Game Closed)
```bash
python scripts/core/make_core_bundle.py verify --bundle-dir <player-bundle-dir>
python scripts/game/exp_install.py install --exp-dir <player-bundle-dir> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4SFMission.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
```

### In-Game Steps
1. Outdoors in a new `--profile player` session, press the Star Map, Surface Map, and Planet Map keys once each, and press `F` (hand scanner).
2. Confirm no Starfield map menu opens, no crash occurs, and zero `"FO4SF"` developer banner text (`1h`) appears on screen.

### Undo Command (Game Closed)
```bash
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
```

### Required PASS Log Lines (`FO4SF_NewGame.0.log` & `FO4SFPipboyMenu.log`)
```log
blocked input=handscanner
step=starmap_blocked n=<k> blocked menu=<menu> route=create
```

---

## Card D — `1b`, `1i`, `1j`, `1k` In-Call Vitals, Arm Idle, `STAT` Aid Actions, `INV`/`DATA` Answers & Standalone `SpecialMenu` (`TEST-STATION`, Gated Off Until Card B Passes)

- **Default Safety & Scope Notes:**
  - Default `make_pipboy_stage_ini.py` keeps `PopulateInCall=0`, `Arm=0`, `StatActions=0`, `InvDataAnswers=0`, and `SpecialMenu=0` so Card B runs untouched first. Enable switches only after Card B passes in game.
  - Native `FO4SF_SpecialMenu` is **`NOT WIRED`** to the Vault 111 lift this round (`R14`; testable standalone only via `SpecialMenu=1` and `SpecialKey`).
  - `WorkshopsList` on `DATA` is a fixed placeholder this round.
  - `DropItem` (`inv_drop`) is withheld from Card D until tried separately on a throwaway item.
  - Power armor is **`NOT REACHABLE`** in `--profile player` (no frame is placed outside the `--profile test` cell).
- **Stage Placeholders:** `<test-bundle-dir>`, `<pipboy-stage-dir>`, `<stage-ini-path>`, `<starfield-dir>`
- **Disk Need:** `~4.2 GB` free under `<starfield-dir>/Data` plus `~5 MB` under `<starfield-dir>/Data/SFSE/Plugins`.
- **Plugin List (`Plugins.txt`, `--profile test`, `22` plugins):**
  `FO4ActorRaider.esm,FO4TerrainCore.esm,FO4SFMission.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFCoreCandidate.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm`

### Install & Opt-In INI Commands (Game Closed)
```bash
python scripts/core/make_core_bundle.py verify --bundle-dir <test-bundle-dir>
python scripts/game/exp_install.py install --exp-dir <test-bundle-dir> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4SFMission.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFCoreCandidate.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/ui/make_pipboy_stage_ini.py --stage <pipboy-stage-dir> --out <stage-ini-path> --populate-in-call 1 --arm 1 --stat-actions 1 --inv-data-answers 1 --special-menu 1 --special-max-points 40
```

### Undo Command (Game Closed)
```bash
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
```

---

## Explicitly `NOT BUILT` / `NOT WIRED` in `gemini/core-integration`
- **List Dialogue (`G4`):** `TEST-STATION` cell only (`FO4SF_ListTalkCell` `0x000807`); **`NOT WIRED`** to Preston or Codsworth.
- **Native `FO4SF_SpecialMenu` (`UI-3`):** **`NOT WIRED`** to the Vault 111 lift this round (`R14`).
- **Power Armor (`player` profile):** **`NOT REACHABLE`** in `--profile player` (no frame is placed).
- **`1l` (`docs/ui/fo4-menus-hosting.md` & `docs/ui/fo4-hud-options.md`):** Design option notes only (`TOOLING` / docs; nothing built until owner picks).
