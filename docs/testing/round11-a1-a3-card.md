Titles: Fallout 4 -> all 7 Fallout titles (FO4, FO3, FNV, FO1, FO2, Tactics, FO76) | Modes: Story & Warfare (+ Survival hardcore layer) | Track: Track 1 (13-plugin playable path)

# Round 11 `candidate-2g-fix2` — `A1` (`D1`–`D7`), `A2` (`A2.1`–`A2.7`), `E1`–`E7` Fixes, and `A3` (Vault Exit Hand-Play) Session Card (`P2` / `P3` / `R8` / `R11` / `R15`)

> **NEW GAME needed (`A16` / `R15`) & Scope / Honesty Banner:**
> - **Whole Scope:** Title: **Fallout 4** | Mode: **Story** (`--profile player`, `13` Track-1 plugins + `FO4SFMapMarkers.esm`; `FadeHold=false`, `FO4SFRouteLoot.esm` OFF, `FO4SFBridge.esm` OFF, `MapBlockStarMap=0`, `Arm=0`, `BootOnFirstOpen=0`, `InvDataAnswers=0`) | Track: **Track 1 playable path (`candidate-2g-fix2`)** (`A1`, `A2`, `E1`–`E7`, Task `1a`/`1b`/`1i` fixes, and `A3` ONLY; **`A4` Fallout 4 guns and `A5` `S1`–`S9` full first mission are NOT on this card**). Reuses tested **`7d5ba49c`** `FO4SFPipboyMenu.dll` (`sfse/` untouched); **`FO4SFMission.esm` carries `0` `WRLD` overrides** (holding ACHRs in interior `09000B60 FO4SF_MissionHoldingCell`, exterior hosts resolved dynamically from persistent refs `0x005C50`/`0x0A775B` `.GetWorldSpace()`).
> - **Sole Codsworth Build (`--codsworth-race-framing 0` ONLY — Stand-In Disclosure):** `candidate-2g-fix2` builds ONLY `--codsworth-race-framing 0` (`2g`'s exact Codsworth `MiniBotARace` / mesh — **no `codsworth-race-framing-on` variant swap**). Codsworth's choice-list under-body camera framing remains a **`MiniBotARace` stand-in** until Claude's `claude/robot-anim` (`#854`) Mr. Handy skeleton/rig merges on `main`.
> - **PASSED IN GAME (`22–23 Nov`, Candidate `2g` `73ea9a4b` `#32` `7085816241` & `2g-fix` `77a16225` `#852` `7106330359`):** New Game -> Cryo Pod (`stage 20`), Fallout-look `E` on Pip-Boy (`0A00080F`) and Vault Door Console (`0A000819`), `V4` catwalk hint, `48`-round Vault 111 armory cage ammo box (`0A000821`), `33`-point `S.P.E.C.I.A.L.` lift (`40` total), surface landing (`stage 200`, `fade in by=story_landing`), **Cold Reload #1 (surface)**, `C2`/`C6` Codsworth & Preston zero greeting replay, `C3` Concord fight god mode OFF (`startcombat raider 0..4`), **Cold Reload #2 (mid-fight)**, `C1` Preston single real `DialogueMenu` (`via=property`, zero messagebox), completion (`stage 200`, `100` credits, `sanctuary01` started), `C5`/`D2` Preston Fallout 4 tricorn hat + duster + leather gloves + Concord raider Fallout 4 outfits up close (zero spacesuit/helmet), `R1` (`09000A50` `stage 0`), `R3` (`InitiallyDisabled` on later-mission actors), `D7` clear Commonwealth daylight + hidden Starfield wrist watch (`HideStarfieldWatch=1`), `C4`/`D5` opaque Pip-Boy backdrop + real `HP`/`AP` + `"10.23.2287"` + non-overlapping `"PLAYER"` / `"RADAWAY (0)"` + keyboard prompts (in game: `F7` open, `M` map, `Tab`/`Esc` close, mouse header/tabs, `A`/`D` sub-tabs), and `D6` `210.8 deg` heading exact on foot.
> - **`prototype, offline` — `OFFLINE ONLY — UNPROVEN IN GAME` (Task `1a`/`1b`/`1i` + `E1`–`E7`):** **`1b`** Vault 111 death recovery (one-time pod `autosave` on `stage 20` then save-locked `< 200` with `Actor.OnDying` scripted `reload` to pod point), **`1i`** zero-`WRLD` `FO4SFMission.esm` + dynamic `0x005C50`/`0x0A775B` world anchors, **`E1`/`F1`** Codsworth `Phase 2` fix + real `1..3` full-window (`SceneOpenCheckSeconds`/`PrestonSceneCheckSeconds`) retries ignoring own `Stop()` (`ownSceneStopPending`/`ownPrestonSceneStop`), excluding restart `OnEnd`s from `talkFailures`, logging real `retries=<n>`, `09000979` default `0` (`MessageBox` unreachable unless set), and **1-choice goodbye post-mission `09000990`/`090009C0` stand-ins** (`Step 3`, no Concord/MQ102 choice replay or audio mismatch), **`E2`** Codsworth camera-guard facing, **`E3`** non-playable `3`-dmg `0900097A` **`"Eon (Raider Stand-In)"`** + `dmg=3.0 playable=false standin=true`, **`E4`** armory pistol auto-equip (`N4` single `"pistol picked"` line), **`E5`/`N2`** Concord-only dead-raider rescue (`FO4SF_Min00` only; `KeepPreston` & `InitRaiderTracking` never pile displaced corpses), **`F3`/`E6`/`F4`** localized `"Commonwealth"` / `"Massachusetts"` (`HeaderFlag.Localized` + `Data/Strings/FO4SFWorkshop_en.*`), **`SANCTUARY`** scoped strictly to clean bench `0B000849` (**`0`** Starfield Outpost FLST overrides -> swap off shows NO `SANCTUARY` on default bench `04005C50` or other outposts), and **`(Stand-In)`** furniture labels (`0B00084B..0B00084D`), and **`F2`/`E7`** Pip-Boy key guide verified verbatim from `main.cpp:8002-8011` (`PageUp`/`PageDown` + `W`/`S` pages, `A`/`D` sub-tabs, `T` Perk Chart, `E` Stimpak, `Q` effects, `R` RadAway, arrow keys: none) — all **`OFFLINE ONLY — UNPROVEN IN GAME`** until Claude (PC) runs them in Starfield.
> - **`R8` Stand-In Truth Labels:** Codsworth's `MiniBotARace` under-body framing stays a **stand-in** until `#854` (`claude/robot-anim`) lands on `main`; Concord's `5`-raider street fight (`0900097A` non-playable `"Eon (Raider Stand-In)"` until `A4` Pipe Guns land), post-mission `09000990`/`090009C0` 1-choice goodbye scenes, `0B00084B..0B00084D` Starfield furniture placeables (`Wooden Chair (Stand-In)`, `Sleeping Cot (Stand-In)`, `Storage Crate (Stand-In)`), and Preston's Starfield chargen face remain disclosed **stand-ins**.

Truth labels used throughout: **`REACHABLE`**, **`TEST-STATION`**, **`OWNER TEST`**, **`RECORDS ONLY`**, **`TOOLING`**, **`NOT BUILT`**, **`NOT WIRED`**, **`NOT OURS`**.

---

## `P3` Typed-Console & Batch-Filename Zero-`M`/`N`/`V` & `< 200 m`/Axis Hop Rules (`A2.7`)

1. **Accurate `P3` Scope (`A2.7`):** The zero-`M`/`N`/`V` rule applies **ONLY to typed interactive ```` ```console ```` lines and `<bat-id>.txt` batch filenames** (case-insensitive, because typing `M`, `N`, or `V` in Starfield's console can trigger menu hotkeys) — it does **NOT** apply to `.txt` batch file contents (```` ```bat ```` blocks intentionally contain `getglobalvalue`, `sqv`, `player.moveto`, `set 0B00084A to 1`, etc., executed from disk without keystrokes). Both ```` ```console ```` and ```` ```bat ```` forbid stripped mod `GLOB`/`QUST` EditorIDs (`set`/`help FO4SF_*`).
2. **God Mode OFF (`A2.7`):** Never instruct the tester to type a god-mode console toggle; play every fight row with **god mode OFF** (default combat damage active).
3. **`< 180 m` (`< 200 m`) Per-Axis Diagnostic Hops:** Every diagnostic `player.setpos` hop (`r9hop1`, `r9hop2`, `r9hop3`) moves strictly `< 180 m` per axis (`docs/terrain/border.md`). Diagnostic batches are strictly optional shortcuts — **Card R11-3 (`HAND-PLAY`)** requires zero console and zero batch files.

---

## Card R11-1 — `2g` Regression Protection + `E1` Zero-MessageBox & Repeat Talks, `E2` Codsworth Camera Facing, `E3` `3`-Dmg Fight (`sidearm_ammo=36`), `E4` Pistol Auto-Equip, `E5` Dead Raiders on Reload, `E7` Pip-Boy Keys (`TEST-STATION`)

- **Stage Placeholders:** `<cand2g-fix2-player-bundle>`, `<mapmarkers-stage-dir>`, `<starfield-dir>`
- **Disk Need:** `~4.2 GB` free under `<starfield-dir>/Data` plus `~5 MB` under `<starfield-dir>/Data/SFSE/Plugins`. Leave `candidate-2g-fix`, `candidate-2g`, and every older candidate folder untouched.
- **Plugin List (`Plugins.txt`, `13` Track-1 plugins + `*FO4SFMapMarkers.esm`; `FO4SFRouteLoot.esm` & `FO4SFBridge.esm` OFF):**
  `FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm`

### Install Command (`candidate-2g-fix2` — Sole `--codsworth-race-framing 0` Build, Game Closed)
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/map_markers_install.py uninstall --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
python scripts/core/make_core_bundle.py verify --bundle-dir <cand2g-fix2-player-bundle>
python scripts/testing/check_beginning_pilot.py check-bundle --bundle-dir <cand2g-fix2-player-bundle>
python scripts/game/exp_install.py install --exp-dir <cand2g-fix2-player-bundle> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/game/map_markers_install.py install --dir <mapmarkers-stage-dir> --starfield <starfield-dir>
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2g-fix2-player-bundle> --starfield <starfield-dir>
python scripts/game/plugin_toggle.py off --plugins FO4SFBridge.esm --starfield <starfield-dir> --why cand2g-fix2-bridge-off
```

### Part 1 — Short `2g` Regression Protection, `1b` Vault 111 Death Recovery, & `E4` Pistol Auto-Equip
1. **New Game -> Vault 111 (`1b` Pod Autosave + `E4` Armory Cage Shelf Pickup `0A000820`/`0A000821`) -> Surface -> Cold Reload #1 (`Throwaway_2gFix2_Surface`):**
   - Confirm Cryo Pod opens (`stage 20`), triggering the one-time **Vault 111 pod recovery autosave** (`saving allowed for that moment only`, `vault_death_recovery=autosave stage=20`, then manual saving locks inside Vault 111 `< 200` via `Timer 6`), Fallout-look `E` on Pip-Boy (`0A00080F`) and Console (`0A000819`), `V4` catwalk hint, and detour to the **open wire armory cage** beside the Overseer's office (`(-57.03, 30.01, 1.29)`, see Card R11-3 `HAND-PLAY` Step 4b).
   - **`1b` Recovery PASS (`OFFLINE ONLY — UNPROVEN IN GAME`):** If the player dies inside Vault 111 (`stage < 200`, Story mode) after the pod autosave, Starfield reloads the pod autosave (`vault_death_recovery=autosave stage=<n>`); if `Actor.OnDying` fires before `autosave` ran (`< 200`), the script restores HP, returns the player to the known-good pod spot, requests an autosave, and logs `vault_death_recovery=reload stage=<n>`.
   - **`E4` PASS:** The Vault 111 stand-in pistol (`0A000820`) lies on the **top shelf inside the open wire armory cage** with the ammo box (`0A000821`, `48` rounds by hand) **one shelf below**. Pressing **`E`** on `0A000820` (`stage < 40`) **automatically equips the pistol into the player's hand** (`FO4SF_NEWGAME rt=<rt> pistol picked item=<item> count=1 equipped=True`, single `N4` line, no manual `I` / inventory equip step required!).
   - Spend `33` `S.P.E.C.I.A.L.` points (`40` total) on the lift -> `stage 40 by=Trigger` unlocks Vault saving -> `stage 200` + `fade in by=story_landing` -> **Save -> Quit to Desktop -> Relaunch -> Load** with daylight restored and `reload mission stage=0 relocate_fails=0`. *(Note: **`stage 40 by=fallback`** is a **FAIL** on the clean elevator-ride row!)*
2. **`F2` / `E7` Pip-Boy Navigation Keys (`sfse/FO4SFPipboyMenu/src/main.cpp:7993-8014` — Quick Reference):**
   - **Open / Close (seen in game):** **`F7`** (`Key=0x76` in staged player INI; **`F10`** `Key=0x79` in source default INI) toggles open/close; **`M`** (`MapKey`) opens `MAP`; **`Tab`** or **`Esc`** closes while open.
   - **Switch top-level pages (`STAT`, `INV`, `DATA`, `MAP`, `RADIO`):** **`PageUp`** (`0x21` -> `LTrigger`, prev page) and **`PageDown`** (`0x22` -> `RTrigger`, next page), plus **`W`** / **`S`** (`0x57`/`0x53`, prev/next page unless consumed by page — unused/unproven in game) or **mouse click** on the top header (**seen in game**). *(Important: **`Q` and `E` do NOT switch pages** — see below!)*
   - **Switch sub-tabs (`STATUS / SPECIAL / PERKS`):** **`A`** (`StrafeLeft`) and **`D`** (`StrafeRight`) (**seen in game**), plus mouse click (**seen in game**).
   - **Action / Shortcut Keys (`main.cpp:8008-8011`, unverified on player run):** **`T`** -> **Perk Chart / Grid View** (`YButton`); **`E`** -> **Use Stimpak** (native `Keyboard.E`); **`Q`** -> **Toggle Showing Effects** (`RShoulder`); **`R`** -> **Use RadAway / Drop** (`XButton`).
   - **Arrow keys:** **NONE** (not bound to pages or tabs by `FO4SFPipboyMenu.dll`; forwarded natively to Scaleform only).

### Part 2 — `candidate-2g-fix2` + Task `1a`/`1i` Fixes (`E1`/`F1`/`Step 3`, `E2`, `E3`, `E5`/`N2`, `D2`/`#7`, `D5`)
1. **`E1` + `F1` + `Step 3` + `E2` — Codsworth Real `DialogueMenu`, Bounded Full-Window Retries, 1-Choice Post Scene, & Camera-Guard Facing (`09000811` / `09000940`):**
   - **Sole build (`--codsworth-race-framing 0`):** Keeps `2g`'s exact `FO4SF_CodsworthRace` (`AllowPcDialog` + `ArmorRace` only; no variant swap). `Game.StopDialogueCamera(False, True)` is **removed** from `Scene.OnPhaseBegin` (`E1`), restoring `2g`'s clean `Phase 2` (`TOPLEVELNEST`) choice loop.
   - Approach Codsworth in Sanctuary (`(-2346.71, -1406.16, 111.73)` m) from `~2.0 m` AND test close activation (`~0.6 m` via optional diagnostic `bat cods06`).
   - **`E2` Camera-Guard Facing PASS + Stand-In Disclosure:** When stepping back from `< 1.65 m`, `EnsureSafeCodsworthCameraDistance()` checks ground-Z (`|pz - cz| <= 1.5 m`) and Sanctuary Player House NW wall clearance (`A2.5`), then calls `player.SetAngle(0.0, 0.0, facingDeg)` facing Codsworth and logs `facing_deg=<deg>` on `codsworth talk camera_guard` so the **greeting frames Codsworth rather than the street or houses**. *(Honest `R8` stand-in disclosure: once the choice list appears, under-body framing stays `2g`'s `MiniBotARace` **stand-in** until `#854` `claude/robot-anim` lands on `main`.)*
   - **`E1` + `F1` + `Step 3` Codsworth Initial + Repeat Talk PASS (`ZERO fallback=messagebox`):**
     - Complete Codsworth's initial 4-choice real `DialogueMenu` conversation (ask a non-ending question -> verify zero greeting replay and asked line greyed -> pick Concord lead -> `codsworth01 stage 100 by=info`, `"New mission: When Freedom Calls"`).
     - **Repeat `E` Talk After Stage `100` (`Step 3` Stand-In):** Press **`E`** on Codsworth **again** after `stage 100` completes -> opens repeatable `1`-choice goodbye stand-in scene **`090009C0`** (hosted on `09000814`, short FO4 post-mission lines ref `DialogueCodsworthPostWar` `0x01E64E`, zero Concord/MQ102 choice replay or mismatched WEMs!) with **ZERO `fallback=messagebox`**. *(F1 retry rule: `09000979` defaults `0.0` so `Message.Show` is unreachable unless `set 09000979 to 1`; if a scene stalls, script marks `ownSceneStopPending` before own `Stop()`, ignores & clears it in `Scene.OnEnd`, counts each `1..3` retry strictly after the full `SceneOpenCheckSeconds` window, and logs real `codsworth talk ERROR scene_failed retries=<n> ...` — e.g. `retries=0` for `no_scene`.)*
2. **`E3` (superseding `D3`) — Concord Street Fight (`3`-Dmg Non-Playable `0900097A` Sidearm & Deterministic `sidearm_ammo=36`, God Mode OFF; Stand-In Fight):**
   - Enter Concord Main Street (`(-2061.23, -1657.46, 86.93)` m -> `(-2011.14, -1697.54, 89.09)` m) armed with your auto-equipped Vault 111 stand-in pistol (`0A000820` + `48` rounds `0A000821`) and **god mode OFF** (do NOT enable console god mode).
   - **Fix (`E3`):** Raiders equip duplicated `WEAP 0900097A` named **`"Eon (Raider Stand-In)"`** (`AttackDamage = 3`, `AmmoList` / `ObjectTemplates` / `AttachParentSlots` cleared, **`NonPlayable` major flag set** until `A4` Pipe Guns land), removing `Coachman` + `AmmoShotshell` FIRST and clamping `Ammo777mm` to exact `36` AFTERWARD while logging effective damage on arm.
   - **`E3` PASS:** `fo4sf_mission.0.log` logs exact `arm raider 0..4 ammo=60` AND exact **`arm raider 0..4 sidearm=eon sidearm_ammo=36 dmg=3.0 playable=false standin=true`** on all `5` raiders (never `41..52`); standing at the Museum door for `30 s` leaves `~half+` HP and fighting from cover is very survivable with god mode OFF; zero `2.85 km` live raider return (`before=2846..2868`).
3. **`E5` + `N2` + `D2` — Cold Reload #2 Preserving Dead Raiders (`FO4SF_Min00` `wfc01 rescue_dead`) & Close-Up Inspection (`Zero Console!`):**
   - Defeat `2–3` raiders (`stage 20`), save **`Throwaway_2gFix2_MidWFC`**, **Quit to Desktop** (full process exit), relaunch via SFSE, and load `Throwaway_2gFix2_MidWFC`; also test a post-fight (`stage 30`) cold reload if verifying all `5` corpses.
   - **`E5` + `N2` PASS:** Dead raiders stay at their Concord street spot after cold relaunch (`FO4SF_Min00` rescues displaced dead raiders via `wfc01 rescue_dead raider=<i>`; **`N2`** removes `KeepPreston -> CheckConcordRaidersWfc01` and ensures `InitRaiderTracking` keeps already-dead displaced coords without piling corpses at `doorX - 18.0`).
   - **`D2` Raider Close-Up PASS (Zero Console!) & `A2.3` / `#7`:** After clearing all `5` raiders (`stage 30`), walk up on foot (`1–2 m`, zero console) to at least two fallen raider bodies (`09000803..09000807`) and confirm Fallout 4 raider clothes (`09000988..0900098A`, local `09000986` `FO4_ConcordRaider`, `0` foreign `0xF04800` overrides, `0x3D094D` stripped across `09000A23` / `09000AD1` / `09000B31` as well) with **zero Starfield spacesuits or helmets**.
4. **`E1` + `F1` + `Step 3` + `D2` + `D5` + `C1` — Preston's Hat, Stage-`30` Real Talk, & Repeat `E` Talk After Stage `200` (`ZERO fallback=messagebox`):**
   - Inspect **Preston Garvey (`09000802`)** at the Museum door (`(-2011.14, -1697.54, 89.09)` m): confirm his **Fallout 4 Minuteman tricorn hat (`09000984`/`09000985`)**, duster, and clean leather gloves (`BO64 = 0x68`, no bare-finger overlap; `face = Starfield chargen approximation`).
   - **`C1` + `D5` + `F1` Stage-`30` PASS:** Press **`E`** on Preston -> single real `DialogueMenu` opens via `preston scene resolved via=<property|file> scene=<ref>` (either `via=property` **OR** `via=file`, never requiring both) with **ZERO `fallback=messagebox`**. Ask a non-ending question -> returns to `phase=1` with zero greeting replay; **move the cursor/highlight off Row 0 (e.g. down to Row 1)** so `dialoguemenu.swf`'s silver bar doesn't mask dimmed `AlreadySaid_Unselected` greying. Finish dialogue -> `stage 35 -> 40 -> 200`, `100` credits, `FO4SF_Sanctuary01` (`09000817`) started, `09000A50` (`FO4SF_MQ103`) still `stage 0` (`R1`), Keeper Timer 2 still running (`A2.4`). *(F1: `ownPrestonSceneStop` prevents `Scene.OnEnd` restart loops from counting toward `talkFailures`, retries count strictly after full `PrestonSceneCheckSeconds` window, and logs real `retries=<n>`.)*
   - **`E1` + `Step 3` Repeat `E` Talk After Stage `200` PASS (`ZERO fallback=messagebox`):** Press **`E`** on Preston **again** after `stage 200` completes -> verify Preston opens his real Starfield `DialogueMenu` post-`200` `1`-choice goodbye stand-in scene (`09000990`, hosted on `FO4SF_CodsworthKeeper` `09000814`, short FO4 post-mission lines ref `COMPreston` `0x0F5D0B`/`0x0F5D0D`, null WEMs) cleanly with **ZERO `fallback=messagebox`**, zero lock-up, and zero stage-`30`/reward re-trigger!
   - **Full-Run Zero-MessageBox Gate (`E1`):** At session end, grep `fo4sf_mission.0.log` and confirm **`0` occurrences of `fallback=messagebox`** across the entire player run (initial AND repeat talks on BOTH Codsworth and Preston!).

```console
help "Calls" 4 QUST
getstage 09000816
getstage 09000800
getstage 09000817
getstage 09000A50
sqs 09000800
bat r11stat
bat cods06
bat r9hop1
bat r9hop2
bat r9hop3
```

```bat
; <starfield-dir>/r11stat.txt — read-only globals & quest state (09=Mission, 06=CoreValues)
getglobalvalue 06000865
getglobalvalue 06000870
sqv 09000800
sqv 09000816
sqv 09000817
sqv 09000A50

; <starfield-dir>/cods06.txt — optional diagnostic C6/E2/A2.5 close check (~0.6 m onto Codsworth 09000811)
player.moveto 09000811

; <starfield-dir>/r9hop1.txt — optional <180 m/axis hop: Vault 111 hilltop -> Sanctuary Codsworth (wait 3-5 s)
player.setpos x -2347
player.setpos y -1406
player.setpos z 113.0

; <starfield-dir>/r9hop2.txt — optional <180 m/axis hop: Sanctuary -> Red Rocket open ground (wait 3-5 s)
player.setpos x -2185
player.setpos y -1561
player.setpos z 106.5

; <starfield-dir>/r9hop3.txt — optional <180 m/axis hop: Red Rocket -> Concord Museum door
player.setpos x -2015
player.setpos y -1700
player.setpos z 90.5
```

### Exact Undo Command (Game Closed)
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/map_markers_install.py uninstall --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
```

### Required PASS Log Lines (`fo4sf_newgame.0.log` & `fo4sf_mission.0.log`; for `C1`, either `via=property` OR `via=file` passes, never both; ZERO `fallback=messagebox` lines in entire run)
```log
FO4SF_NEWGAME rt=<rt> stage 20 by=Trigger
FO4SF_NEWGAME rt=<rt> vault_death_recovery=<autosave|reload> stage=<st>
FO4SF_NEWGAME rt=<rt> pipboy pickup equipped flag=1 worn=true
FO4SF_NEWGAME rt=<rt> stage 30 by=vault_console
FO4SF_NEWGAME rt=<rt> catwalk hint shown
FO4SF_NEWGAME rt=<rt> pistol picked item=<item> count=<cnt> equipped=True
FO4SF_NEWGAME rt=<rt> special set S=<s> P=<p> E=<e> C=<c> I=<i> A=<a> L=<l> readback=<r0> <r6>
FO4SF_NEWGAME rt=<rt> landed z=<z> confirmed=True fallback=false world=<world>
FO4SF_NEWGAME rt=<rt> stage 200 by=Trigger
FO4SF_NEWGAME rt=<rt> fade in by=story_landing loaded=true cell=<cell>; saving and HUD on
FO4SF_MISSION rt=<rt> codsworth01 reload stage=<st> choices=<cnt>
FO4SF_MISSION rt=<rt> reload mission stage=<st> relocate_fails=0
FO4SF_MISSION rt=<rt> codsworth talk camera_guard prev_d=<d> safe_d=1.85 wall_avoid=<true|false> facing_deg=<deg>
FO4SF_MISSION rt=<rt> codsworth talk scene phase=<n> stage=<st>
FO4SF_MISSION rt=<rt> codsworth dialogue menu opened
FO4SF_MISSION rt=<rt> codsworth01 stage 100 by=info
FO4SF_MISSION rt=<rt> min00 given by=codsworth
FO4SF_MISSION rt=<rt> arm raider <i> ammo=60
FO4SF_MISSION rt=<rt> arm raider <i> sidearm=eon sidearm_ammo=36 dmg=<dmg> playable=false standin=true
FO4SF_MISSION rt=<rt> startcombat raider <i> d=<d>
FO4SF_MISSION rt=<rt> preston activated at stage 30
FO4SF_MISSION rt=<rt> preston scene resolved via=<property|file> scene=<ref>
FO4SF_MISSION rt=<rt> preston scene talk requested scene=<ref> stage=30
FO4SF_MISSION rt=<rt> preston talk scene started stage=30
FO4SF_MISSION rt=<rt> preston talk scene phase=<n> stage=30
FO4SF_MISSION rt=<rt> preston dialogue menu opened
FO4SF_MISSION rt=<rt> stage 35 by=info
FO4SF_MISSION rt=<rt> preston talk end info=0x092A -> stage 40
FO4SF_MISSION rt=<rt> reward credits=100
FO4SF_MISSION rt=<rt> stage 200 by=Trigger
FO4SF_MISSION rt=<rt> sanctuary01 start_requested ok=True
FO4SF_MISSION rt=<rt> complete stage=200
```

### Negative / FAIL Conditions
- **`E1` / `F1` FAIL:** ANY `fallback=messagebox` line anywhere in `fo4sf_mission.0.log` during the full player run (initial OR repeat talks on Codsworth `090009C0` or Preston `09000990`), Codsworth's `DialogueMenu` closing prematurely on `Phase 2`, `Scene.OnEnd` from own `Stop()` burning retries or counting into `talkFailures`, retries firing before the full `SceneOpenCheckSeconds`/`PrestonSceneCheckSeconds` window, hardcoded `retries=3` when fewer retries ran, or **`stage 40 by=fallback`** on the elevator-exit row (exit-lift fallback triggered instead of clean lift boarding); **`1b` FAIL:** player dying inside Vault 111 (`stage < 200`, Story mode) without pod `autosave` or `reload` recovery; **`E2` FAIL:** camera guard facing the player away from Codsworth toward street/houses; **`E3` FAIL:** `sidearm_ammo != 36` (`41..52`), `Coachman` re-equipped, missing `playable=false`, or standing player dying in `15 s` with god mode OFF; **`E4` FAIL:** Vault 111 armory cage pistol failing to auto-equip on `E` pickup (`equipped=False`) or duplicate `"pistol picked"` lines (`N4`); **`E5` / `N2` FAIL:** dead raiders vanishing `2.9 km` to `(-3229, -4392)` after cold relaunch, or `KeepPreston` / `InitRaiderTracking` piling corpses; **`D2` / `#7` FAIL:** Preston missing hat or spacesuit on any `FO4SFMission.esm` raider/boss; **`D5` FAIL:** Preston's asked line not greyed after moving cursor off Row 0; **`1i` FAIL:** any `WRLD` override in `FO4SFMission.esm` or hardcoded Starfield planet world in runtime resolvers.

---

## Card R11-2 — `F3`/`E6`/`F4` Sanctuary Workshop (Localized `Commonwealth / Massachusetts` Footer + Scoped Clean Bench `SANCTUARY` Only + Stand-In Furniture Labels), `F2`/`D5`/`E7` Pip-Boy Keys (`main.cpp:8002-8011`), `A2.6` `INV`/`DATA`/`RADIO`, & `D7` Weather + Watch Hide (`TEST-STATION`)

- **Stage Placeholders:** `<cand2g-fix2-player-bundle>`, `<mapmarkers-stage-dir>`, `<starfield-dir>`
- **Disk Need:** `~4.2 GB` (`0 B` extra on installed Card R11-1).
- **Plugin List (`Plugins.txt`):** Same `13` Track-1 plugins as Card R11-1 (`FO4SFRouteLoot.esm` & `FO4SFBridge.esm` OFF).

### Install Command (Same Installed `13`-Plugin Bundle as Card R11-1)
```bash
python scripts/core/make_core_bundle.py verify --bundle-dir <cand2g-fix2-player-bundle>
python scripts/game/exp_install.py install --exp-dir <cand2g-fix2-player-bundle> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2g-fix2-player-bundle> --starfield <starfield-dir>
```

### Step-by-Step Verification Rows (`F3` / `E6` / `F4` / `D4` + `#2`/`#3`/`#8`/`A2.1`, `F2` / `D5` + `E7`, `A2.6`, `D7` + `#4`/`#5`/`#9`)
1. **`F3` / `E6` / `F4` / `D4` — Localized `Commonwealth, Massachusetts` Footer (`LCTN`/`STDT`), Default Bench (`04005C50`, `0B00084A = 0` OFF), & Scoped Clean Bench `SANCTUARY` Category (`bat r11swp1` -> `0B000849` + `3.5 s` Self-Heal):**
   - **Localized `E6` Restored Overrides (`HeaderFlag.Localized` + `Data/Strings/FO4SFWorkshop_en.{STRINGS,DLSTRINGS,ILSTRINGS}`):** `FO4SFWorkshop.esm` restores the D4 display-name overrides (`LCTN 0x01B736`/`0x01B735` -> `"Commonwealth"`, `0x061527` & `STDT 0x05E5CB` -> `"Massachusetts"`, `0` `PNDT` overrides) compiled with `HeaderFlag.Localized` + binary string tables so Starfield reads **"Commonwealth, Massachusetts"** cleanly instead of `2g-fix`'s blank `", "` / `"."`!
   - **Default `candidate-2g-fix2` (`F3` + `#2` OFF by default):** `FO4SFWorkshop.esm` ships `GLOB 0B00084A` (`default = 0.0`, `EnableCleanBenchSwap = False`) so `04005C50` stays active/bound (`sanctuary01 clean_bench_swap active=false ref=<ref>`), AND carries **`0` Starfield-wide Outpost `FLST` overrides** (`0x058606` / `0x1A5507` untouched!).
   - Return to Sanctuary Hills workbench `04005C50` (`(-2329.25, -1420.19, 112.09)` m) after `Min00` reaches `stage 200` and press **`E`**.
   - **Default Bench PASS (`F3` + `E6` + `#3` + `#8` + `A2.1`):**
     - Footer shows **"COMMONWEALTH, MASSACHUSETTS"** (localized, non-blank — NO lone `"."` or `", "` and NO `"Mars"` / `"Sol"`!).
     - **Swap off (`0B00084A = 0`):** **NO `SANCTUARY` category** appears on the default bench (`04005C50`) or on any other Starfield outpost workbench (`0` Starfield-wide `FLST` pollution!).
     - Bench activation skips Objective `50` (`"Talk to Sturges"`, disabled until `S9`), logs `sanctuary01 open_mode sturges_unavailable -> stage 1000`, and advances straight to **Objective `1000`** (`sanctuary01 bench_activated=true ref=<ref> complete=false stage=1000`, keeping `09000A50` at `stage 0` per `R1`).
     - Stay inside `WorkshopMenu` for **`>= 10 s`** within `3.5 m` -> `CheckSturgesTalkFallback` (explicit boolean flags only, `openMenuCount` deleted) NEVER pops a messagebox.
   - **Dedicated Separate Opt-In Step — Scoped Clean Sanctuary Bench (`F3` + `F4` + `E6` + `#2`, `bat r11swp1` -> `0B000849`):**
     - Save a throwaway save, run `P3`-safe **`bat r11swp1`** (`set 0B00084A to 1`), and verify `TryBindBench` swaps `04005C50` -> `ACTI 0B000849` (`sanctuary01 clean_bench_swap active=true ref=<ref>`). `FO4SFWorkshop.esm` scopes `0B000848` (`SANCTUARY`) strictly to `0B000849` via its keyword (`0` Starfield-wide `FLST` overrides), registering `3` zero-perk Starfield **`(Stand-In)`** placeables (`0B00084B` **`"Wooden Chair (Stand-In)"`** [`AK_Chair_Wood_01_Free`], `0B00084C` **`"Sleeping Cot (Stand-In)"`** [`FoundScrapCot01`], `0B00084D` **`"Storage Crate (Stand-In)"`** [`Loot_Storage_Miscbox05_Common_Empty`] / `COBJ 0B00084E..0B000850`).
     - Press **`E`** on `0B000849`:
       - **`F3`/`F4`/`E6` Clean-Bench PASS:** Opens **`SANCTUARY`** showing **`Wooden Chair (Stand-In)`**, **`Sleeping Cot (Stand-In)`**, **`Storage Crate (Stand-In)`** — **ZERO `"Industrial Workbench"`**, **ZERO `"Spacesuit Workbench"`**, **ZERO `"Research Lab"`**, and **ZERO `"Cannot place item: Skill requirements not met."`**!
       - **`3.5 s` Self-Heal (`#2`):** If `WorkshopMenu` ever fails to open within `3.5 s` of activating `0B000849`, Timer `3` logs `sanctuary01 clean_bench_swap self_heal reason=no_workshop_menu` and restores `04005C50` automatically.
     - **Immediate Rollback:** Run `P3`-safe **`bat r11swp0`** (`set 0B00084A to 0`) to restore `04005C50` on load.
2. **`F2` + `D5` + `E7` Pip-Boy Layout & Exact Key Bindings (`main.cpp:8002-8011`) + `A2.6` + One-Line Rollbacks:**
   - **Shipped Player INI & Tested DLL (`<starfield-dir>/Data/SFSE/Plugins/FO4SFPipboyMenu.{dll,ini}`, `N3` reused `7d5ba49c` DLL, zero C++ edits):**
     - Out-of-the-box: `Key=0x76` (`F7`; source default `Key=0x79` `F10`), `ShellBackdrop=1`, `ShellVitalsFill=1`, `HideStarfieldWatch=1`, `SuppressDataMenu=0`, `TabOpensPipboy=0`.
     - **One-line rollbacks:** **`ShellVitalsFill=0`**, **`ShellBackdrop=0`**, **`HideStarfieldWatch=0`**, and **`--commonwealth-weather 0`**.
   - **`F2` + `D5` + `E7` + `A2.6` PASS:** Press **`F7`** (or **`F10`** on source INI; **seen in game**) to open `STAT`, confirm `"PLAYER"` clears `"RADAWAY (0)"` (`step=shell_hintbar_layout ... new_y=672.0 ok=1`) and keyboard prompts show (`step=shell_platform ... platform=0 ... triggers_hidden=2`), then verify **`F2` controls from `sfse/FO4SFPipboyMenu/src/main.cpp:8002-8011`**:
     - **`PageUp` / `PageDown`** (`LTrigger` / `RTrigger`, plus secondary **`W` / `S`** `"Forward"`/`"Back"` — unproven in game) or **mouse click** (seen in game) switches top-level **`STAT` -> `INV` -> `DATA` -> `MAP` -> `RADIO`** pages.
     - **`A` / `D`** (`StrafeLeft` / `StrafeRight`; seen in game) switches sub-tabs (`STATUS / SPECIAL / PERKS`).
     - **`T`** (`YButton`, unproven in game) opens **Perk Chart / Grid View**; **`E`** (native `Keyboard.E`) uses **Stimpak**; **`Q`** (`RShoulder`) toggles **Showing Effects**; **`R`** (`XButton`) uses **RadAway / Drop**.
     - **Arrow keys:** **NONE** (not intercepted in `main.cpp:8002-8011`); **`M`** opens `MAP` (**seen in game**); **`Tab`** or **`Esc`** closes cleanly (**seen in game**, zero crashes across `INV`/`DATA`/`RADIO`, single `step=quest_cache_build`).
3. **`D7` + Review `#4` + `#5` + `#9` — Clear Commonwealth Weather (Known Side Effect) & Watch-Hide Retry (`try=<n>`, Non-Fatal Stage 2):**
   - **`D7` + `#4` Weather PASS & Known Side Effect:** `FO4SFCoreValues.esm` validates exact source `EditorID`s (`ClimateUniqueNewAtlantis`, `ClimateUniqueCydonia`, `ClimateUniqueCydoniaFrozen`, `ATMO_Mars`, `ATMO_Jemison`) and copies `naClmt.WeatherSettings` (`DeepCopy()`) onto Mars climates + `ATMO_Jemison` onto `ATMO_Mars`. Confirm clear Commonwealth daylight (no orange Mars dust storm). **Known Side Effect (`#4`):** Overriding `ClimateUniqueCydonia`, `ClimateUniqueCydoniaFrozen`, and `ATMO_Mars` clears weather **Mars-wide** across Starfield's Mars surface; one-line build rollback is **`--commonwealth-weather 0`**.
   - **`D7` + `#5` + `#9` Watch Hide PASS:** `HideStarfieldWatch=1` retries cleanly until `BottomLeftGroup_mc` is hidden (`step=hud_watch_hide when=<when> try=<n> movie=<hex> ok=1 target=BottomLeftGroup_mc children_hidden=<n>`), keeping Stage 2 non-fatal if channel IDs are missing (`step=hud_watch_hide_init ok=0 reason=channel_ids_unavailable` disables ONLY watch hide). Confirm bottom-left `"MARS"`/`O2`/`CO2` watch is hidden (`HideStarfieldWatch=0` one-line rollback).

```console
sqs 09000817
getstage 09000817
getstage 09000A50
bat r11swp1
bat r11swp0
```

```bat
; <starfield-dir>/r11swp1.txt — separate #2/E6 opt-in Sanctuary clean bench swap ON (0B00084A = 1)
set 0B00084A to 1

; <starfield-dir>/r11swp0.txt — rollback #2 Sanctuary clean bench swap OFF (0B00084A = 0, restores 04005C50 on load)
set 0B00084A to 0
```

### Exact Undo Command (Game Closed)
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/map_markers_install.py uninstall --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
```

### Required PASS Log Lines (`fo4sf_mission.0.log` & `FO4SFPipboyMenu.log`)
```log
FO4SF_MISSION rt=<rt> sanctuary01 init stage=10 bench_ref=0x005C50
FO4SF_MISSION rt=<rt> sanctuary01 clean_bench_swap active=false ref=<ref>
FO4SF_MISSION rt=<rt> sanctuary01 clean_bench_swap active=true ref=<ref>
FO4SF_MISSION rt=<rt> sanctuary01 open_mode sturges_unavailable -> stage 1000
FO4SF_MISSION rt=<rt> sanctuary01 bench_activated=true ref=<ref> complete=false stage=1000
step=shell_c4_config shell_backdrop=1 shell_vitals_fill=1 suppress_data_menu=0 tab_opens_pipboy=0 hide_starfield_watch=1
step=hud_watch_hide when=<when> try=<n> movie=<hex> ok=1 target=BottomLeftGroup_mc children_hidden=<n>
step=shell_backdrop movie=<hex> ok=1 target=root_graphics color=0x041409 alpha=0.97
step=shell_hintbar_layout when=kShow old_y=575.0 new_y=672.0 ok=1
step=shell_platform when=kShow platform=0 called=1 triggers_hidden=2
step=shell_vitals when=kShow page=0 tab=0 hp=<cur>/<max> ap=<cur>/<max> lvl=<n> hp_src=<av|formula> ap_src=<av|formula>
step=shell_date_fix when=<when> old_w=150.0 new_w=<w> auto_size=1 word_wrap=1 width_set=1
step=quest_cache_build plugins=<n> quests=<m> workshop=<0|1> scanned=<k>
step=map_config map_key=<vk> map_page=3 menus=<menus> block_starmap=0 store=<store> markers=<cnt> travel=<script>.<fn> survival=<0|1> heading_at=<sign>+<off>
```
*(In default `candidate-2g-fix2`, `clean_bench_swap active=false` logs first; `clean_bench_swap active=true` logs on the separate `bat r11swp1` opt-in step, and `sanctuary01 clean_bench_swap self_heal reason=no_workshop_menu` fires ONLY if `0B000849` fails to open `WorkshopMenu` within `3.5 s`.)*

### Negative / FAIL Conditions
- **`E6` / `F3` / `F4` / `#2` / `#3` FAIL:** Default bench (`04005C50`) showing a blank `", "` or lone `"."` footer instead of localized `"COMMONWEALTH, MASSACHUSETTS"`; `SANCTUARY` category appearing on `04005C50` or another outpost when swap is OFF (`bat r11swp0` / before `bat r11swp1`); `0B000849` swapping on by default before `bat r11swp1`; `0B000849` showing `"Industrial Workbench"` or `"Cannot place item: Skill requirements not met."` instead of `SANCTUARY` with `(Stand-In)` furniture labels; objective `50` appearing while Sturges is disabled; **`#8` / `A2.1` FAIL:** Sturges fallback messagebox firing while any menu is open; **`D5` / `F2` / `A2.6` FAIL:** `"PLAYER"` overlapping `"RADAWAY (0)"`, controller glyphs (`A, X, Y, LT, RT`) on keyboard, `PageUp`/`PageDown` or `W`/`S` failing to step top-level pages, `A`/`D` failing sub-tabs, `T` failing Perk Chart, `E`/`Q`/`R` failing Stimpak/Effects/RadAway, or crash cycling pages; **`D7` / `#4` / `#5` / `#9` FAIL:** orange Mars dust storm or visible Starfield `"MARS"`/`O2`/`CO2` wrist watch with `HideStarfieldWatch=1`.

---

## Card R11-3 — `D6` Measured-Speed Walk Table (`4.8 m/s`, `97` Segments `L1`–`L9` + Overshoot Margins) & `A3` + `E4`/`E7` Owner's Plain Console-Free `HAND-PLAY` Vault-Exit Walkthrough (`TEST-STATION` / `OWNER TEST`)

- **Stage Placeholders:** `<cand2g-fix2-player-bundle>`, `<mapmarkers-stage-dir>`, `<starfield-dir>`
- **Disk Need:** `~4.2 GB` (`0 B` extra on installed Card R11-1).
- **Plugin List (`Plugins.txt`):** Same `13` Track-1 plugins as Card R11-1 (`FO4SFRouteLoot.esm` & `FO4SFBridge.esm` OFF).

### Install Command (Same Installed `13`-Plugin Bundle as Card R11-1)
```bash
python scripts/core/make_core_bundle.py verify --bundle-dir <cand2g-fix2-player-bundle>
python scripts/game/exp_install.py install --exp-dir <cand2g-fix2-player-bundle> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2g-fix2-player-bundle> --starfield <starfield-dir>
```

### `D6` Corrected Walk-Table Parameters (`docs/testing/console-free-walk-list.md`)
- **Measured Run Speed:** Recomputed from `2g`'s measured **`4.6–5.0 m/s`** (`4.8 m/s` default parameter in `scripts/newgame/walk_headings.py --run-speed`, replacing `3.7 m/s`; `5a` is now **`6.97 s`** instead of `9.04 s`, preventing `2g` still `14`'s `11 m` overshoot into the house wall). Compass headings (`210.8 deg` verified exact on foot in `2g`) stay unchanged.
- **Target `(x, y, z)` & Overshoot Margin:** Every segment across all **`97` navmesh-verified segments (`L1`–`L9`)** keeps exact target `(x, y, z)` coordinates for position-correcting drivers AND states its binary-verified **safe overshoot margin (m)** (`safe_overshoot_m`) and hazard before a wall, railing, or drop.
- **Added Extended Place Legs (`63` New Segments, `L6`–`L9`):**
  - **`L6` (`6a`–`6t`, `20` segs, `237.77 m`):** Sanctuary Hills houses (Player House, Codsworth search houses `MQ102CodsworthSearchMarker01`/`04`, and Sanctuary Workbench `04005C50`).
  - **`L7` (`7a`–`7v`, `22` segs, `157.37 m`):** Museum of Freedom interior (front door -> stairs -> Preston's room).
  - **`L8` (`8a`–`8p`, `16` segs, `113.83 m`):** Museum basement (Preston's room -> `ConcordMuseumBasementTerminal` `020125AB` -> `MQ03SecurityGateREF` `02013042`; honestly noting the `2.2 m` cage alcove to `PowerGenerator01` `02012585` has `0` FO4 `NAVM` tris by design).
  - **`L9` (`9a`–`9e`, `5` segs, `57.39 m`):** Museum roof (exit door -> roof -> T-45 Power Armor `04008913` -> Crashed Vertibird Minigun `04005119`).

### `A3` + `F2` `HAND-PLAY` — Owner's Plain Console-Free Walkthrough (Keyboard + Mouse Only, Zero Console!)

> **Rule for the Owner:** Do **NOT** open the `~` console, do **NOT** run any `bat` file, and do **NOT** use `moveto` or `setpos`. Play strictly with **`W`/`A`/`S`/`D`**, **mouse look**, **`E`**, **left-click / aim**, **`I`**, **`F7`** (or **`F10`** on source default INI), **`M`**, **`PageUp`/`PageDown`** or **`W`/`S`** (Pip-Boy top-level pages), **`A`/`D`** (Pip-Boy sub-tabs), **`T`** (Perk Chart), **`E`/`Q`/`R`** (Stimpak / Effects / RadAway), and **`Tab`/`Esc`**.
> - **`F2` Pip-Boy Key Truth (`sfse/FO4SFPipboyMenu/src/main.cpp:7993-8014`):** **`F7`** (staged player INI `Key=0x76`; **`F10`** on source INI `Key=0x79`) opens/closes (`M` opens `MAP`; `Tab`/`Esc` closes); **`PageUp`/`PageDown`** (`LTrigger`/`RTrigger`) and **`W`/`S`** (`Forward`/`Back`) cycle top-level **`STAT` / `INV` / `DATA` / `MAP` / `RADIO`** pages *(code truth — not yet verified in live game)*; **`A`/`D`** (`StrafeLeft`/`StrafeRight`) switches sub-tabs *(seen working in game)*; **`T`** (`YButton`) opens **Perk Chart** *(seen working in game)*; **`E`** (`Use Stimpak`), **`Q`** (`RShoulder` + `Toggle Showing Effects`), **`R`** (`XButton` + `Use RadAway`); **arrow keys: none** (unmapped in `main.cpp`).

| Step | Plain Keyboard + Mouse Action (Zero Console) | What You Should See | VIDEO |
|---|---|---|---|
| **1. Start New Game (`1b`)** | From the Main Menu, click **New Game**. Wait `~2 s` for the single `"Character Appearance"` prompt and click **`Quick start`** (or **`Create character`**). | Cryo pod opens inside **Vault 111** in clear first-person view (zero stuck black screen, zero double prompt); one-time Vault autosave fires once (`vault_death_recovery=autosave stage=20`) while Vault save lock holds until surface arrival (if killed inside Vault `< stage 200` before autosave, `Actor.OnDying` reloads/returns to known-good pod point). | Pending |
| **2. Walk to the Pip-Boy (`L1`)** | Turn west down the main Vault 111 corridor. Press **`E`** to open the two closed vault interior doors (`0200126E`, `02001234`; all `4/4` Vault 111 walk-path doors are unlocked), walk through the open third doorway (`02001608`), bear slightly right around the corridor pillar, turn north to the foot of the control-deck ramp, and walk up the ramp to the skeleton beside the console (`1g` stance `(-54.50, 0.00, 0.59)`, `1.815 m` eye reach). | Both interior doors swing open smoothly on **`E`**, corridor footing holds without getting stuck, and the **Fallout 4 Pip-Boy 3000** (`0A00080F`) sits on the deck with **zero Starfield scanner box**. | Pending |
| **3. Pick Up the Pip-Boy** | Look down at the Pip-Boy 3000 on the deck and press **`E`**. | Prompt reads **`Pip-Boy 3000, Take [E]`**; picking it up equips the Pip-Boy (`F7`/`F10` and `M` now work). | Pending |
| **4. Open the Vault Gear Door (`L2`)** | Turn slightly left toward the **Vault Door Controls** console (`0A000819`, `1.342 m` eye reach, Fallout 4 console mesh) and press **`E`**. Wait `~5 s`. | Prompt reads **`Vault Door Controls, Activate [E]`** (zero Starfield scanner box), the giant Vault 111 gear door rolls open, and a short catwalk hint tells you to head across to the exit lift. | Pending |
| **4b. Detour to the Open Armory Cage Shelf & Pick Up the Stand-In Pistol (`E4`, BEFORE the Lift!)** | Do **NOT** walk straight north from the control deck (solid wall at `x = -53, y = 4..14`). From the control-deck room (`y = 0`), walk **east** through unlocked doors `02001607` `(-40.23, 0.00, 0.00)` and `02001609` `(-32.91, 3.66, 0.00)` into the north-south hall (`x = -33`), walk **north** to `y = 14`, turn **west** down the security hall to `(-53.03, 18.29, 0.00)`, press **`E`** to open unlocked Overseer office door `0200160A`, and walk north through open wire gate `02001539` `(-54.92, 29.71, 0.00)` to the **armory cage shelf** `(-57.03, 30.01, 1.29)`. Press **`E`** on the **Vault 111 stand-in pistol (`0A000820`) on the top shelf** and **`E`** on the **ammo box (`0A000821`, `48` rounds by hand) one shelf below** while still inside Vault 111 (`stage < 40`), then retrace your steps back to the control deck. | Picking up the pistol with **`E`** **automatically equips it into your hand** (`pistol picked ... equipped=True`; if you ever unequip it, `I` / `Tab -> Inventory -> Weapons` re-equips it), and the box below gives `48` rounds by hand *(Starfield stand-in until `A4`'s Fallout 4 `10mm` lands)*. | Pending |
| **5. Walk Across the Catwalk & Onto the Exit Lift (`L3`, NO `setpos`!)** | Walk back down the control-deck ramp, turn south to face the open gear door, and walk straight out onto the catwalk. **Stop before the west railing** (`1.6 m` safe overshoot), turn right (north) onto the stair landing, walk down the stairs to the elevator cavern floor, and walk straight west into the open **Exit Lift cage** onto the center of the platform (`PlatformRadius = 2.0 m`). *(Like Fallout 4's buttonless `RespecTriggerREF` `0x08C94A`, the lift has no wall button; if you click **`Stay`**, simply step `~2 m` back out the open cage entrance and step back onto the platform to re-open the prompt!)* | You walk cleanly off the ramp, through the open gear door, down the stairs without snagging, and stepping onto the platform automatically opens the **`S.P.E.C.I.A.L.`** screen with **`33` points to spend** (`40` total). | Pending |
| **6. Spend `33` `S.P.E.C.I.A.L.` Points & Ride Up (`1i`)** | Allocate your **`33`** points across `S.P.E.C.I.A.L.` and click **`Continue`**. Wait `0–7 s` as the lift rises to the surface. | The lift rides up to the Vault 111 hilltop (`world` resolved dynamically from persistent `0x005C50`/`0x0A775B`, zero hardcoded `MarsPlanetWorld`, NEVER hitting `stage 40 by=fallback`) and **automatically fades into clear Commonwealth daylight** (no orange Mars dust storm, no Starfield wrist watch, no stuck black screen, no false return-lift popup). | Pending |
| **7. Walk Down to Sanctuary & Talk to Codsworth (`L4`, `F1` + `Step 3`)** | Follow the paved Vault 111 hilltop trail north-northeast around the switchback, down the slope, across the creek footbridge (`04014BA7`), and up the Sanctuary street to **Codsworth** (`09000811`). Aim at Codsworth, press **`E`**, finish his 4-choice real dialogue (ending with Concord), then press **`E`** once more after `stage 100`. | Ground holds all the way down; Codsworth's greeting faces him cleanly (`MiniBotARace` stand-in until `#854` lands on `main`), asked questions grey out cleanly (`retries=0` when clean, accurate `retries=<n>` after full `SceneOpenCheckSeconds`), Concord pops **`"New mission: When Freedom Calls"`**, and repeat **`E`** opens his `DialogueCodsworthPostWar` 1-choice goodbye stand-in (`090009C0`, zero `MessageBox`). | Pending |
| **8. Walk to Concord & Fight the Raiders (`L5`, `E3` + `N2` + God Mode OFF)** | Walk south down Sanctuary street, turn east across **Sanctuary North Bridge** (`04005199`), follow the paved highway past **Red Rocket Truck Stop**, and descend into **Concord Main Street**. Use cover and defeat all `5` raiders with your auto-equipped Vault 111 stand-in pistol and **god mode OFF** (optionally test a mid-fight Quit-to-Desktop cold reload to verify dead raiders stay in Concord street). | Paved road stays solid under foot; all `5` raiders fire `NonPlayable` `3`-dmg `"Eon (Raider Stand-In)"` (`0900097A`, `dmg=3.0 playable=false standin=true`, `sidearm_ammo=36`, not `Coachman`) without warping away, dead raiders stay on Main Street after cold reload (`E5`, `KeepPreston` & `InitRaiderTracking` never pile corpses), and an armed cover-using player survives and clears the street (`Talk to Preston Garvey`). | Pending |
| **9. Close-Up Raider Look (`D2`) & Talk to Preston (Stage `30` + `Step 3`)** | Walk up on foot to `1–2 m` of two defeated raider bodies on Main Street and look down, then walk to the Museum of Freedom door, inspect **Preston Garvey** (`09000802`), press **`E`**, ask a non-ending question, **move the cursor/highlight off Row 0 (e.g. down to Row 1)** before finishing, and press **`E`** once more after `stage 200`. | Raiders wear Fallout 4 raider clothes up close (zero spacesuits/helmets); **Preston wears his Fallout 4 Minuteman tricorn hat on his head** and duster (clean leather gloves); pressing **`E`** opens one real `DialogueMenu` (`09000979 = 0.0`, `Message.Show` unreachable), moving the highlight off Row 0 shows dimmed `AlreadySaid_Unselected` text, finishing awards `100` credits and starts **`"New mission: First Settlement"`**, and repeat **`E`** opens his 1-choice goodbye stand-in (`09000990`, zero `MessageBox`). | Pending |
| **10. Return to Sanctuary Workbench & Check Pip-Boy (`E6`, `F3`, `F4`, `F2`)** | Walk back to the Sanctuary workbench (`04005C50` by default in `candidate-2g-fix2`, or `0B000849` under the separate `bat r11swp1` test) and press **`E`**; close it and press **`F7`** (or **`F10`** on source INI), test **`PageUp`/`PageDown`** + **`W`/`S`** (top pages), **`A`/`D`** (sub-tabs), **`T`** (Perk Chart), **`E`/`Q`/`R`** (Stimpak/Effects/RadAway), **`M`** (`MAP`), and **`Tab`/`Esc`** to close. | Swap off (`F3`): default bench `04005C50` shows localized **`"COMMONWEALTH, MASSACHUSETTS"`** (`E6`, `HeaderFlag.Localized` + `FO4SFWorkshop_en.*`) with zero `SANCTUARY` category on `04005C50` or other outposts and zero Sturges popup, advancing to Objective `1000` (`#3`); swap on (`bat r11swp1`): clean bench `0B000849` shows `SANCTUARY` with `(Stand-In)` furniture labels (`F4`); Pip-Boy shows opaque dark backing, non-overlapping `"PLAYER"` / `"RADAWAY (0)"`, keyboard prompts, real `HP`/`AP`, and `"10.23.2287"`. | Pending |

### `A3` + Review `#10` Honest Boundary — Offline-Proven vs Only The Game Can Prove (`R15`)

| Check | Offline-Proven (`prototype, offline`) | Only Starfield In Game Can Prove (`R15`) |
|---|---|---|
| **Vault 111 Interior Path (`L1`–`L3`)** | `469/469` (`100%`) 2D navmesh checks on `Vault111Cryo` `NAVM 0x000B11DC` (`max_step_dz = 0.239 m`), `4/4` Vault 111 doors unlocked, `1.815 m` Pip-Boy / `1.342 m` console eye reach, `ACTI 0x0100E0E6` `FULL == ""` (dead `HandleLiftControlActivate` / `liftRegistered` removed per **Review `#10`**; buttonless `PlatformRadius = 2.0 m` trigger; `Stay` -> step `~2 m` out & back in re-triggers), and `QOBJ`/`QSTA` audit (honestly flagging `FO4SF_NewGame` Obj `10` `targets=[]` and `FO4SF_Min00` Obj `85` `targets=[]`). | Live Starfield Havok character-controller collision on the ramp, gear-door threshold, and catwalk stairs; live first-person `E` reachability after walking on foot; live `ExitLift` boarding & `Stay` re-entry trigger without `setpos`. |
| **Commonwealth Exterior Walk (`L4`–`L5`)** | `1,993/1,993` (`100%`) 2D navmesh checks on `WRLD 0x0000003C` `NAVM` (`269` cells, `167,724` tris), measured-speed (`4.8 m/s`) durations, and per-segment `safe_overshoot_m` (`D6`). | Converted Commonwealth terrain slope/footing along the full `L4` switchback/footbridge and `L5` Red Rocket/Concord highway (only `5a` and `5b` ran on foot in `2g`), plus live objective marker icons on screen. |
| **Sanctuary Houses & Museum Interior/Basement/Roof (`L6`–`L9`)** | `1,306/1,306` (`100%`) 3D Z-aware `ConcordMuseum01` `NAVM 0x197BB0` checks (`2,002` tris, `max_step_dz = 0.207 m`) + Sanctuary house/workbench navmesh segments & overshoot margins (noting `2.2 m` basement cage alcove to `02012585` has `0` FO4 `NAVM` tris by design). | Live interior doors, collision, stairs, and combat flow inside Sanctuary houses and the Museum of Freedom (verified once `A5` `S3`–`S7` land on `candidate-2h`/`2i`). |

```console
sqs 0A000800
getstage 09000800
```

### Exact Undo Command (Game Closed)
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/map_markers_install.py uninstall --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
```

### Required PASS Log Lines (`fo4sf_newgame.0.log` & `fo4sf_mission.0.log`)
```log
FO4SF_NEWGAME rt=<rt> stage 20 by=Trigger
FO4SF_NEWGAME rt=<rt> vault_death_recovery=autosave stage=20
FO4SF_NEWGAME rt=<rt> pipboy pickup equipped flag=1 worn=true
FO4SF_NEWGAME rt=<rt> stage 30 by=vault_console
FO4SF_NEWGAME rt=<rt> catwalk hint shown
FO4SF_NEWGAME rt=<rt> pistol picked item=<item> count=<cnt> equipped=True
FO4SF_NEWGAME rt=<rt> landed z=<z> confirmed=True fallback=false world=<world>
FO4SF_NEWGAME rt=<rt> stage 200 by=Trigger
FO4SF_NEWGAME rt=<rt> fade in by=story_landing loaded=true cell=<cell>; saving and HUD on
FO4SF_MISSION rt=<rt> codsworth01 complete choices=<cnt> concord_pointed=true
FO4SF_MISSION rt=<rt> complete stage=200
```

### Negative / FAIL Conditions
- **FAIL (`stage 40 by=fallback`):** Any occurrence of `FO4SF_NEWGAME ... stage 40 by=fallback` (lift failed or timed out), `vault_death_recovery` failing inside Vault 111 (`< stage 200`), any Vault 111 door, ramp, gear-door threshold, catwalk stair, or exit-lift platform requiring console `moveto`/`setpos` to pass, falling through converted Commonwealth terrain along `L4`/`L5`, or walk-table hold times overshooting walls/railings at `4.8 m/s`.

---

## Round 12 Verification Matrix (Task 1a / 1b / 1i)

| Row | Focus / Requirement | Console / Check | PASS / FAIL Criterion | Stand-In / Code Truth | Result | VIDEO |
|---|---|---|---|---|---|---|
| **R12-1 (`FAIL` Gate)** | Lift fallback (`Stage 40`) & `TalkUseMessageBox` (`09000979`) | Inspect `fo4sf_newgame.0.log` + `fo4sf_mission.0.log` | **FAIL** on `stage 40 by=fallback`; **PASS** on `stage 40 by=Trigger`, `09000979 = 0.0` (`Message.Show` unreachable unless forced) | Real lift landing required | Offline selftest PASS | Pending |
| **R12-2 (`1b`)** | Vault 111 Death Recovery (Cryo pod autosave + `< 200` `Actor.OnDying`) | Cryo pod `stage 20` open -> optional test kill `< 200` | One-time pod autosave on `stage 20`; Timer 6 save lock until surface; `< 200` dying reloads/recovers to known-good pod point `(PodX, PodY, PodZ + PodLift)`; logs `vault_death_recovery=<autosave or reload> stage=<n>` | Vault 111 scripted pod recovery while save-locked | `test_newgame.py` PASS | Pending |
| **R12-3 (`F1`)** | Bounded Full-Window Scene Retries (`Codsworth01` & `Min00`) | Trigger repeat `E` / blocked talk on Codsworth & Preston | `ownSceneStopPending` & `ownPrestonSceneStop` ignore own `Stop()` in `OnEnd`; retry waits full `SceneOpenCheckSeconds`/`PrestonSceneCheckSeconds`; excludes restart `OnEnd` from `talkFailures`; logs real `retries=<n>` (`retries=0` when clean) | Full-window timer state machine | `test_mission.py` & `test_r11_part3_2gfix2.py` PASS | Pending |
| **R12-4 (`F2`)** | Pip-Boy Key Truth (`sfse/FO4SFPipboyMenu/src/main.cpp:7993-8014`) | Live keyboard check inside Pip-Boy | `F7`/`F10` open, `M` map, `Tab`/`Esc` close, `PageUp`/`PageDown` + `W`/`S` page *(unverified in game)*, `A`/`D` sub-tab *(seen)*, `T` Perk Chart *(seen)*, `E` Stimpak, `Q` Effects, `R` RadAway, arrow keys: none | Reuse tested `7d5ba49c` `FO4SFPipboyMenu.dll` (`sfse/` untouched) | Code-matched in card | Pending |
| **R12-5 (`F3`)** | Scoped `SANCTUARY` Workbench | Inspect default `04005C50`, another Starfield outpost, then `bat r11swp1` `0B000849` | Swap off: NO `SANCTUARY` category on `04005C50` or any other outpost (`0` overrides on Starfield FLST `0x058606`/`0x1A5507`); swap on: `SANCTUARY` exclusive to clean bench `0B000849` | Clean bench swap via `0B00084A = 1` | `test_r11_d4_sanctuary_bench.py` PASS | Pending |
| **R12-6 (`E6`)** | Localized `"COMMONWEALTH, MASSACHUSETTS"` Footer | Open default workbench `04005C50` / inspect Sanctuary footer | Shows `"COMMONWEALTH, MASSACHUSETTS"` (`HeaderFlag.Localized` + `Data/Strings/FO4SFWorkshop_en.{STRINGS,DLSTRINGS,ILSTRINGS}`, `LCTN 0x01B736`/`0x01B735`, `0x061527`/`STDT 0x05E5CB`) | D4 localization string table restore | `test_workshop_core.py` PASS | Pending |
| **R12-7 (`F4`)** | 3 Starfield Furniture Stand-In Labels | Inspect `SANCTUARY` build menu on `0B000849` | Shows `"Wooden Chair (Stand-In)"`, `"Sleeping Cot (Stand-In)"`, `"Storage Crate (Stand-In)"` (`0B00084B`..`0B00084D`) | Starfield mesh stand-ins explicitly labelled | `test_workshop_core.py` PASS | Pending |
| **R12-8 (`E3`)** | Raider Sidearm Stand-In | Fight Concord raiders (`Min00`) | `"Eon (Raider Stand-In)"` (`0900097A`), `NonPlayable`, `OBTF`/`OBTS` cleared, `dmg=3.0` logged (`playable=false standin=true`) | Non-playable `Eon` stand-in until A4 | `test_r11_d1_d3_min00.py` & `test_r11_part3_2gfix2.py` PASS | Pending |
| **R12-9 (`Step 3`)** | Post-Mission Repeat-Talk Goodbye Scenes | Press `E` on Codsworth after `100` & Preston after `200` | 1-choice goodbye stand-in scenes (`090009C0` / `09000990`, topics `090009D8`/`090009E8` & `090009A8`/`090009B8`, null WEM/TROT) | Stand-in repeat-talk greeting | `test_r11_part3_2gfix2.py` PASS | Pending |
| **R12-10 (`N2`–`N4`)** | No Corpse Pile (`KeepPreston` / `InitRaiderTracking`) & Log Cleanup | Inspect `FO4SF_Min00Quest.psc`, `FO4SF_NewGameQuest.psc`, `Mission/Program.cs` | `KeepPreston` does NOT rescue raiders (only `CheckConcordRaidersWfc01` rescues concord corpses), dead coords kept on cold reload; `7d5ba49c` DLL reused (`sfse/` untouched); duplicate `"pistol picked"` removed | Rescue scoped to active fight state | `test_r11_part3_2gfix2.py` PASS | Pending |
| **R12-11 (`1i`)** | Dynamic World Anchors & Zero-`WRLD` `FO4SFMission.esm` | `Mission check` + Vault exit / `Min00` / `Sanctuary01` exterior log | `FO4SFMission.esm` has `0` `WRLD` overrides & `0` Mars biome `0x002A3777`; persistent ACHRs parked in `FO4SF_MissionHoldingCell` (`09000B60`); exterior anchors resolve `.GetWorldSpace()` from `0x005C50` / `0x0A775B` | Dynamic persistent-ref host world lookup | `Mission selftest` & `test_cross_plugin_ids.py` PASS | Pending |

## Claude's Additions (5 Rows — 23 Nov In-Game Baseline)

| Item / PR | What Passed Live (`23 Nov`) | What Remains / Unverified | Card / Stand-In Handling | VIDEO |
|---|---|---|---|---|
| **#854 (`claude/robot-anim`)** | FO4 Mr. Handy body + animations; Codsworth 4-line Sanctuary talk `completed=true`, `fallback=0` | Close camera framing + greeting replay noted; branch not yet on `main` | Card stays `--codsworth-race-framing 0` (`MiniBotARace` `2g framing stand-in`, gated on `#854` merge); M1 conflict resolution verified separately | Pending |
| **#855 (`claude/creature-anim`)** | Radroach idle and deathclaw tail/spines animated in game test | Walk, attack, death + bloatfly, mole rat, dog remain unverified | Main creature slot stays unaffected (`creature_slot=empty` / `slot=empty`) in Round 12 build | Pending |
| **#856 (`claude/human-anim`)** | Add-on race keyword NPC played FO4 surrender idle vs normal control | Walk and 1st-person gun animations remain unverified | Feature flag defaults OFF | Pending |
| **Gun moving parts proof (`#32` `gunpart-slide-vanilla-vs-ours-1123.jpg`)** | Proved `Gun_*.af` moves `XM2311` slide nodes (`TRIGGER`, `Magazine`, `Bolt`, `MiscA..MiscA14`) | Full `A4` FO4 10mm swap and live reload wiring | Keeps Vault 111 stand-in pistol (`0A000820`) + non-playable `Eon (Raider Stand-In)` (`0900097A`) until `A4` lands | `#32` proof / Pending |
| **Gun sounds (`#32` `sound-bank-study`)** | Tested custom Wwise bank (`v174` vs SF `v140`) & direct `SNDR` override paths | **ON HOLD:** silent in game (`v174` / override bank mismatch) | Keeps Starfield `SNDR` sound stand-ins | Pending |
