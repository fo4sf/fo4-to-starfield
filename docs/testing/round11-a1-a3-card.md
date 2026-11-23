Titles: Fallout 4 -> all 7 Fallout titles (FO4, FO3, FNV, FO1, FO2, Tactics, FO76) | Modes: Story & Warfare (+ Survival hardcore layer) | Track: Track 1 (13-plugin playable path)

# Round 11 `candidate-2g-fix` — `A1` (`D1`–`D7`), `A2` (`A2.1`–`A2.7`), Review Fixes `#1`–`#10`, and `A3` (Vault Exit Hand-Play) Session Card (`P2` / `P3` / `R8` / `R11` / `R15`)

> **NEW GAME needed (`A16` / `R15`) & Scope / Honesty Banner:**
> - **Whole Scope:** Title: **Fallout 4** | Mode: **Story** (`--profile player`, `13` Track-1 plugins + `FO4SFMapMarkers.esm`; `FadeHold=false`, `FO4SFRouteLoot.esm` OFF, `FO4SFBridge.esm` OFF, `MapBlockStarMap=0`, `Arm=0`, `BootOnFirstOpen=0`, `InvDataAnswers=0`) | Track: **Track 1 playable path (`candidate-2g-fix`)** (`A1`, `A2`, PR `#852` Review Fixes `#1`–`#10`, and `A3` ONLY; **`A4` Fallout 4 guns and `A5` `S1`–`S9` full first mission are NOT on this card** and belong to `candidate-2h` / `candidate-2i` per `docs/plans/round11-first-mission-plan.md`).
> - **PASSED IN GAME (`22 Nov 20:35Z–21:07Z`, Candidate `2g` `73ea9a4b` == `main` `fb22fa2b`, `#32` comment `7085816241`, `32 min`, `3` launches, `2` cold quit-to-desktop reloads, `0` crashes):** New Game -> Cryo Pod (`stage 20`), Fallout-look `E` on Pip-Boy (`0A00080F`) and Vault Door Console (`0A000819`), `V4` catwalk hint, `33`-point `S.P.E.C.I.A.L.` lift (`40` total), surface landing (`stage 200`, `fade in by=story_landing`), **Cold Reload #1 (surface)**, `C2`/`C6` Codsworth greeting framed outside (`safe_d=1.85`) with zero greeting replay and asked line greyed, `C3` Concord street fight with god mode OFF (`startcombat raider 0..4`, zero `2.85 km` return, raiders advance/shoot and kill player), **Cold Reload #2 (mid-fight `dead=2/5`)**, `C1` Preston single real `DialogueMenu` (`via=property`, zero messagebox), completion (`stage 200`, `100` credits, `sanctuary01` started), `C5` Preston Fallout 4 duster/gloves/boots (zero spacesuit/helmet), `R1` (`09000A50` `stage 0`), `R3` (`InitiallyDisabled` on Sturges/Kellogg/Corvega/Courser), `R2` Sanctuary workbench (`04005C50`) opens workshop with zero messagebox (`complete=false stage=100`), `C4` opaque Pip-Boy backdrop + real `HP 205/205`, `AP 100/110`, `"10.23.2287"`, single `quest_cache_build`, and `D6` `210.8 deg` heading exact on foot (`5a`, `5b`).
> - **`prototype, offline` — `OFFLINE ONLY — UNPROVEN IN GAME` (`candidate-2g-fix` Round 11 `A1`–`A3` + Review Fixes `#1`–`#10`):** Every fix on this card — **`D1` + `#6`** Codsworth choice-list camera (`Game.StopDialogueCamera(False, True)` alone by default; 5 race-framing edits **OFF** by default via `--codsworth-race-framing 0` + separate 1-launch variant `variants/codsworth-race-framing-on/FO4SFMission.esm`), **`D2` + `#7`** Preston's hat (`0` `MO2F`/`MO3F`/`XFLG`, `BO64` `0x10`/`0x12`, gloved body `BO64 = 0x68`), console-free close-up Concord raider inspection, and `0x3D094D` spacesuit strip across later-mission `FO4SFMission.esm` raiders/NPCs (`09000A23`, `09000AD1`, `09000B31`), **`D3`** deterministic ammo (`ammo=60`) + balanced stand-in sidearm (`Eon` + `36` `7.77mm`, `Coachman` removed), **`D4` + `#2`/`#3`/`#8`** default `04005C50` preserved with clean bench swap **OFF** by default (`0B00084A = 0`) + separate `bat r11swp1` opt-in & `3.5 s` self-heal + non-stalling `stage 100` when Sturges has not arrived + `openMenuCount` removed, **`D5`** Pip-Boy `"PLAYER"`/`"RADAWAY (0)"` layout (`ButtonHintBar_mc.y = 672.0`) + keyboard glyphs (`SetPlatform(0, false)`) + Preston asked-question greying (`ENAM`/`INAM`), **`D6`** measured-speed (`4.8 m/s`) walk times & safe overshoot margins across `97` segments (`L1`–`L9`), **`D7` + `#4`/`#5`/`#9`** clear Commonwealth weather (with **Mars-wide weather override known side effect** & `--commonwealth-weather 0` rollback) + `HideStarfieldWatch=1` retry (`try=<n>`) + non-fatal Stage 2 channel ID check, **`#1`** Preston talk lock fixes (`late_dialogue_open`, `< 35` exit, post-`200` press), and **`A3` + `#10`** Vault-exit console-free hand-play proof (dead `HandleLiftControlActivate` removed) — is **`TEST-STATION` (`prototype, offline` / OFFLINE ONLY — UNPROVEN IN GAME)** until Claude (PC) runs `candidate-2g-fix` in Starfield.
> - **`R8` Stand-In Truth Labels:** The current `5`-raider street fight (`WEAP 0x0476C4 Eon` stand-in sidearm until `A4` Pipe Guns land) and Museum-door Preston talk (`FO4SF_Min00`) remain a **stand-in** for the full *When Freedom Calls* sequence (`S1`–`S9` pending `candidate-2h`/`2i`); Preston's face remains a **Starfield chargen approximation** (FO4 FaceGen head not converted); and `09000A15` opt-in Sanctuary helper remains a **stand-in** (real building waits for the next mission).

Truth labels used throughout: **`REACHABLE`**, **`TEST-STATION`**, **`OWNER TEST`**, **`RECORDS ONLY`**, **`TOOLING`**, **`NOT BUILT`**, **`NOT WIRED`**, **`NOT OURS`**.

---

## `P3` Typed-Console & Batch-Filename Zero-`M`/`N`/`V` & `< 200 m`/Axis Hop Rules (`A2.7`)

1. **Accurate `P3` Scope (`A2.7`):** The zero-`M`/`N`/`V` rule applies **ONLY to typed interactive ```` ```console ```` lines and `<bat-id>.txt` batch filenames** (case-insensitive, because typing `M`, `N`, or `V` in Starfield's console can trigger menu hotkeys) — it does **NOT** apply to `.txt` batch file contents (```` ```bat ```` blocks intentionally contain `getglobalvalue`, `sqv`, `player.moveto`, `set 0B00084A to 1`, etc., executed from disk without keystrokes). Both ```` ```console ```` and ```` ```bat ```` forbid stripped mod `GLOB`/`QUST` EditorIDs (`set`/`help FO4SF_*`).
2. **God Mode OFF (`A2.7`):** Never instruct the tester to type a god-mode console toggle; play every fight row with **god mode OFF** (default combat damage active).
3. **`< 180 m` (`< 200 m`) Per-Axis Diagnostic Hops:** Every diagnostic `player.setpos` hop (`r9hop1`, `r9hop2`, `r9hop3`) moves strictly `< 180 m` per axis (`docs/terrain/border.md`). Diagnostic batches are strictly optional shortcuts — **Card R11-3 (`HAND-PLAY`)** requires zero console and zero batch files.

---

## Card R11-1 — `2g` Regression Protection + `D1` (`#6` Default + Variant), `D2` (`#7` Spacesuit Strip + Raider Close-Up), `D3`, `D5` Preston Greying, & `#1`/`A2.2`/`A2.4`/`A2.5` (`TEST-STATION`)

- **Stage Placeholders:** `<cand2g-fix-player-bundle>`, `<mapmarkers-stage-dir>`, `<starfield-dir>`
- **Disk Need:** `~4.2 GB` free under `<starfield-dir>/Data` plus `~5 MB` under `<starfield-dir>/Data/SFSE/Plugins`. Leave `candidate-2g` and every older candidate folder untouched.
- **Plugin List (`Plugins.txt`, `13` Track-1 plugins + `*FO4SFMapMarkers.esm`; `FO4SFRouteLoot.esm` & `FO4SFBridge.esm` OFF):**
  `FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm`

### Install Command (`candidate-2g-fix` Default — Game Closed)
```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/map_markers_install.py uninstall --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
python scripts/core/make_core_bundle.py verify --bundle-dir <cand2g-fix-player-bundle>
python scripts/testing/check_beginning_pilot.py check-bundle --bundle-dir <cand2g-fix-player-bundle>
python scripts/game/exp_install.py install --exp-dir <cand2g-fix-player-bundle> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/game/map_markers_install.py install --dir <mapmarkers-stage-dir> --starfield <starfield-dir>
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2g-fix-player-bundle> --starfield <starfield-dir>
python scripts/game/plugin_toggle.py off --plugins FO4SFBridge.esm --starfield <starfield-dir> --why cand2g-fix-bridge-off
```

### Part 1 — Short `2g` Regression Protection (One Proof Line Per Passed Step)
1. **New Game -> Vault 111 (Incl. Stand-In Pistol Pickup `0A000820`/`0A000821`) -> Surface -> Cold Reload #1 (`Throwaway_2gFix_Surface`):** Confirm Cryo Pod `stage 20`, Fallout-look `E` on Pip-Boy (`0A00080F`) and Console (`0A000819`), `V4` catwalk hint, **detour to the Overseer's desk (`(-57.03, 30.01, 1.29)`, see Card R11-3 `HAND-PLAY` Step 4b) to pick up and equip the Vault 111 stand-in pistol (`0A000820`) + `48` rounds (`0A000821`) BEFORE stepping onto the exit lift (`stage < 40`, logging `pistol picked item=<item> count=<cnt>`)**, `33` `S.P.E.C.I.A.L.` points (`40` total), `stage 200` + `fade in by=story_landing`, then **Save -> Quit to Desktop -> Relaunch -> Load** with daylight restored and `reload mission stage=0 relocate_fails=0`.
2. **Cold Reload #2 (`Throwaway_2gFix_MidWFC`) & `R1`/`R3` Protection:** Mid-fight save/quit/relaunch at `stage 20` (`dead=1..4/5`) preserves dead/living raiders; `09000A50` (`FO4SF_MQ103`) stays `stage 0` at `Min00` `stage 200`; later-mission actors (`09000A01` Sturges, Kellogg, Corvega, Courser) stay `InitiallyDisabled` (`0x800`) on frame 1.

### Part 2 — Round 11 Fixes (`D1` + `#6`, `D2` + `#7`, `D3`, `D5` Preston Greying, `#1` / `A2.2` / `A2.4` / `A2.5`)
1. **`D1` + Review `#6` — Codsworth Choice-List Camera (Race Edits OFF by Default + Separate 1-Launch Variant) & `A2.5` Safe Camera Guard (`09000811` / `09000940`):**
   - **Root cause (`docs/quests/r11-d1-d3-dialogue-camera-and-ammo.md`):** `MiniBotA` `skeleton.nif` has `Root (0)` -> `COM (0.506 m)` and `MiniBotABodyPartData` (`0x227704`) binds `Head1 = C_Chassis` (`z = 0.506 m`) while `codsworth.nif` floats `~0.85 m` higher (`z = 1.36 m`); Phase 1 `PlayerDialogueSceneAction` engaged Starfield's dialogue camera aimed at `0.506 m`.
   - **Default `candidate-2g-fix` (`#6` — `--codsworth-race-framing 0` OFF by default):** Ships `2g`'s exact `FO4SF_CodsworthRace` (`AllowPcDialog` + `ArmorRace` only — all 5 race edits OFF) and runs `Game.StopDialogueCamera(False, True)` alone on `Scene.OnPhaseBegin(>=2)`.
   - Approach Codsworth in Sanctuary (`(-2346.71, -1406.16, 111.73)` m) from `~2.0 m` AND test close activation (`~0.6 m` via optional diagnostic `bat cods06`).
   - **`D1` Default PASS:** Logs `codsworth talk dialogue_camera stopped phase=2`; both the initial greeting (`phase=0`) **AND** the `DialogueMenu` choice list (`phase=1`) frame Codsworth cleanly from outside his body (NOT sitting under his chassis looking at his thrusters and the ground as in `2g` still `04`; rendered framing is game-only).
   - **Separate 1-Launch Variant Check (`#6` — ONLY if `StopDialogueCamera` alone still clips under Codsworth):** With Starfield closed, copy `<cand2g-fix-player-bundle>/variants/codsworth-race-framing-on/FO4SFMission.esm` (built with `--codsworth-race-framing 1`, enabling the 5 race-framing edits on `0x818`) over `<starfield-dir>/Data/FO4SFMission.esm`, load `Throwaway_2gFix_Surface` for 1 focused Codsworth `phase=0`/`phase=1` check, then restore `<cand2g-fix-player-bundle>/FO4SFMission.esm`.
   - **`A2.5` PASS:** `EnsureSafeCodsworthCameraDistance()` checks ground-Z (`|pz - cz| <= 1.5 m`, clamping `[cz - 0.35, cz + 0.60]`) and Sanctuary Player House NW exterior wall clearance before `SetPosition`, logging `codsworth talk camera_guard prev_d=<d> safe_d=1.85 wall_avoid=<true|false>` (never snapping into a wall or below terrain).
   - **`C2` Protection:** Selecting a non-ending question returns straight to `phase=1` with zero greeting replay and the asked line greyed out.
2. **`D3` Concord Street Fight Balance & Deterministic Raider Ammo (God Mode OFF; Stand-In Fight):**
   - **Root cause of `2g`'s `30, 70, 30, 30, 20` log:** `WEAP 0x26D96B Coachman` `WAM2` -> `LLW_Ammo_Coachman (0x2B4B15)` -> `LL_Ammo_Shotshell (0x279274)` (`{10, 15, 20, 25, 30}`) rolled `30, 10, 30, 30, 20` on spawn, and old `< 12 -> +60` turned `10` into `70` while leaving `30, 30, 30, 20`. Fix uses exact-delta normalization (`ammo=60`) and then `EquipBalancedRaiderSidearm` **removes `Coachman` + `AmmoShotshell`** from each raider's inventory and equips the balanced Starfield **stand-in** sidearm (`WEAP 0x0476C4 Eon`, `abPreventRemoval=True`, `10` dmg vs `Coachman` `52` dmg -> `21` hits vs `4` hits at `205 HP`, with exact `36` `AMMO 0x04AD3E Ammo777mm`) so NPC combat AI (`SelectBestWeapon`) never switches back to the `52`-dmg shotgun (including after a mid-fight cold reload), until `A4` Fallout 4 Pipe Guns land.
   - Confirm you picked up & equipped the **Vault 111 stand-in pistol (`0A000820`) + `48` rounds (`0A000821`)** before leaving Vault 111 so you enter Concord armed. Walk (or `< 180 m`/axis hops `bat r9hop2` -> wait `3–5 s` -> `bat r9hop3`) to Concord Main Street (`(-2061.23, -1657.46, 86.93)` m -> `(-2011.14, -1697.54, 89.09)` m). Play with **god mode OFF** (do NOT enable console god mode).
   - **`D3` PASS:** Verify `fo4sf_mission.0.log` shows exact deterministic `arm raider 0..4 ammo=60` AND `arm raider 0..4 sidearm=eon sidearm_ammo=36`, all `5` raiders enter active combat (`startcombat raider 0..4 d=<d>`) firing `Eon` (not `Coachman`) with zero `2.85 km` return (`before=2846..2868`), and an armed Level-1 player (`205 HP`) using street cover survives and defeats all `5` raiders without god mode (including after Cold Reload #2).
3. **`D2` Console-Free Close-Up Concord Raider Body Inspection & `A2.3` + Review `#7` Scoped Spacesuit Strip (Zero Console!):**
   - Right after defeating the `5` Concord raiders (`stage 30` active, before leaving Main Street), **walk up on foot using keyboard + mouse ONLY (zero `~` console, zero `moveto`) to `1–2 m`** from at least two defeated Concord raider bodies (`09000803..09000807`, around `(-2029, -1698)`), aim down at torso/limbs/head, and capture a close-up still.
   - **`D2` Raider Close-Up PASS:** Confirm Fallout 4 raider underarmor/armor (`09000988..0900098A`, gloved full-body `BO64 = 0x68`) and human face/limbs up close with **zero Starfield spacesuits or helmets** (closing `2g`'s `40 m`-only observation).
   - **`A2.3` + Review `#7` PASS (Offline-Verified):** Concord outfit assignment uses local `NPC_ 09000986` (`FO4_ConcordRaider`, `FormVersion = 581`) on Concord raiders (`09000803..09000807`) with **zero foreign overrides of shared `FO4ActorRaider.esm:0xF04800`**, AND all later-mission `FO4_LvlRaider`-cloned `NPC_` records in `FO4SFMission.esm` (`09000A23` `FO4_CorvegaBoss`, `09000AD1` `FO4_Kellogg`, `09000B31` `FO4_CourserZ247`) have `0x3D094D` stripped (`DOFT = SOFT = 09000988`, `ActorShouldForceHideSpacesuit_AV = 1.0`, asserting **zero** `NPC_` records in `FO4SFMission.esm` carry `0x3D094D`).
4. **`D2` Preston's Hat + `D5` Preston Asked-Question Greying + `C1` / Review `#1` / `A2.2` / `A2.4` (`09000802` / `09000900`):**
   - **Root cause of missing hat in `2g` stills `07`/`08`:** `ARMA 09000984` retained `MO2F = 0x01` / `MO3F = 0x01` (`HasFaceBonesModel`) + `XFLG = 0x01`, making Starfield request absent `prestongarveyhat_m_facebones.nif`. Fix emits `0` `MO2F`/`MO3F`/`XFLG` across `09000981`/`09000984`/`09000989`, sets hat `BO64` to `0x10` (`ARMO 09000985`) / `0x12` (`ARMA 09000984`, activating `FadedAfro_Cap_Mask`), and sets gloved body `BO64 = 0x68` (fixing `2g` still `07`'s duplicate bare fingers behind leather gloves).
   - Walk up to **Preston Garvey (`09000802`)** at the Museum of Freedom door (`(-2011.14, -1697.54, 89.09)` m) and capture a close-up still before pressing **`E`**.
   - **`D2` Preston Hat PASS:** Preston wears his **Fallout 4 Minuteman tricorn hat (`09000984`/`09000985`) visibly on his head** alongside his Fallout 4 duster, leather gloves (no bare-finger overlap), and boots (`09000980..09000983`), with zero spacesuit/helmet (`face = Starfield chargen approximation`, FO4 FaceGen head not converted).
   - **`C1` + Review `#1` + `A2.2` PASS:** Press **`E`** on Preston -> single real `DialogueMenu` opens via `preston scene resolved via=<property|file> scene=<ref>` (either `via=property` **OR** `via=file` passes, never requiring both in one run) with **ZERO `preston talk fallback=messagebox reason=no_scene`** and **ZERO coexistence** of the `1.45 s` messagebox fallback and a late-opening `DialogueMenu`. **Review `#1` Lock-Freedom:** `prestonFallbackActive` clears on `late_dialogue_open`, clears (along with `prestonTalkBoxOpen`) when exiting `RunPrestonTalk` with `stage < 35` or reaching `stage >= 200`, and `OnActivate` resets stale `prestonFallbackActive` when no box/menu/scene is open — **confirm pressing `E` on Preston once more after `stage 200` opens his post-`200` summary prompt cleanly without locking or re-running `stage 30` / rewards** *(at `stage 30`, zero messagebox opens; at `stage >= 200`, `RunPrestonTalk(stage, postMsg)` intentionally opens the post-completion summary prompt)*. *(Note: `2f` and `2g` `QUST 0x800` VMAD bytes for `PrestonTalkScene` are byte-identical, so `2f`'s runtime `None` is unprovable from ESM/logs alone.)*
   - **`D5` Preston Greying PASS:** Pick a non-ending question on Preston -> returns to `phase=1` with **zero greeting replay**. Because `dialoguemenu.swf` defaults the bright silver selection bar to **Row 0** on `TOPLEVELNEST` loop-back (`AlreadySaid_Selected` renders dark text on the bright bar, masking the greying seen in `2g` still `08`), **move the cursor/highlight off the asked row (e.g. down to Row 1)** to verify the asked question renders in dimmed **`AlreadySaid_Unselected`** grey text (explicit `ENAM`/`INAM` on `0x918..0x91A` & `0x928..0x92A`; Scaleform greying is game-only). Finish dialogue -> `stage 35 -> 40 -> 200`, `100` credits, `FO4SF_Sanctuary01` (`09000817`) started.
   - **`A2.4` PASS:** Keeper Timer 2 reaching its placement budgets (`KeeperOnly`) keeps running so later proximity-start checks never stall.

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

; <starfield-dir>/cods06.txt — optional diagnostic C6/D1/A2.5 close check (~0.6 m onto Codsworth 09000811)
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

### Required PASS Log Lines (`fo4sf_newgame.0.log` & `fo4sf_mission.0.log`; for `C1`, either `via=property` OR `via=file` passes, never both)
```log
FO4SF_NEWGAME rt=<rt> stage 20 by=Trigger
FO4SF_NEWGAME rt=<rt> pipboy pickup equipped flag=1 worn=true
FO4SF_NEWGAME rt=<rt> stage 30 by=vault_console
FO4SF_NEWGAME rt=<rt> catwalk hint shown
FO4SF_NEWGAME rt=<rt> pistol picked item=<item> count=<cnt>
FO4SF_NEWGAME rt=<rt> special set S=<s> P=<p> E=<e> C=<c> I=<i> A=<a> L=<l> readback=<r0> <r6>
FO4SF_NEWGAME rt=<rt> landed z=<z> confirmed=True fallback=false world=<world>
FO4SF_NEWGAME rt=<rt> stage 200 by=Trigger
FO4SF_NEWGAME rt=<rt> fade in by=story_landing loaded=true cell=<cell>; saving and HUD on
FO4SF_MISSION rt=<rt> codsworth01 reload stage=<st> choices=<cnt>
FO4SF_MISSION rt=<rt> reload mission stage=<st> relocate_fails=0
FO4SF_MISSION rt=<rt> codsworth talk camera_guard prev_d=<d> safe_d=1.85 wall_avoid=<true|false>
FO4SF_MISSION rt=<rt> codsworth talk dialogue_camera stopped phase=2
FO4SF_MISSION rt=<rt> codsworth talk scene phase=<n> stage=<st>
FO4SF_MISSION rt=<rt> codsworth dialogue menu opened
FO4SF_MISSION rt=<rt> codsworth01 stage 100 by=info
FO4SF_MISSION rt=<rt> min00 given by=codsworth
FO4SF_MISSION rt=<rt> arm raider <i> ammo=60
FO4SF_MISSION rt=<rt> arm raider <i> sidearm=eon sidearm_ammo=36
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
- **`D1` / `#6` FAIL:** Codsworth's choice-list camera still sits under his chassis looking at thrusters/ground (in default AND variant); **`D2` / `#7` FAIL:** Preston's hat missing on his head, duplicate bare fingers through leather gloves, or close-up Concord raider body (or later-mission `FO4SFMission.esm` NPC) carrying a Starfield spacesuit/helmet; **`D3` FAIL:** non-`60` shotshell counts, missing `sidearm=eon sidearm_ammo=36`, `before=2846..2868` `2.85 km` raider snap-back, or unwinnable opening street fight under cover with god mode OFF; **`D5` FAIL:** Preston's asked dialogue question NOT greyed out after moving cursor off Row 0; **`#1` / `A2.2` FAIL:** Preston locked after `late_dialogue_open` / `< 35` exit / post-`200` press, OR both messagebox and `DialogueMenu` opening; **`A2.5` FAIL:** camera guard placing the player inside a wall/floor; or any `2g` regression.

---

## Card R11-2 — `D4` Sanctuary Workshop (`#2` OFF by Default + Separate `bat r11swp1` & `3.5 s` Self-Heal, `#3` Stage 100 Non-Stall, `#8`/`A2.1`), `D5` Pip-Boy Layout & Keyboard Glyphs, `A2.6` `INV`/`DATA`/`RADIO`, & `D7` (`#4` Mars Side Effect, `#5` Retry `try=<n>`, `#9` Non-Fatal Stage 2) (`TEST-STATION`)

- **Stage Placeholders:** `<cand2g-fix-player-bundle>`, `<mapmarkers-stage-dir>`, `<starfield-dir>`
- **Disk Need:** `~4.2 GB` (`0 B` extra on installed Card R11-1).
- **Plugin List (`Plugins.txt`):** Same `13` Track-1 plugins as Card R11-1 (`FO4SFRouteLoot.esm` & `FO4SFBridge.esm` OFF).

### Install Command (Same Installed `13`-Plugin Bundle as Card R11-1)
```bash
python scripts/core/make_core_bundle.py verify --bundle-dir <cand2g-fix-player-bundle>
python scripts/game/exp_install.py install --exp-dir <cand2g-fix-player-bundle> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2g-fix-player-bundle> --starfield <starfield-dir>
```

### Step-by-Step Verification Rows (`D4` + `#2`/`#3`/`#8`/`A2.1`, `D5`, `A2.6`, `D7` + `#4`/`#5`/`#9`)
1. **`D4` + Review `#2` + `#3` + `#8` + `A2.1` — Sanctuary Workshop Default (`0B00084A = 0` OFF) & Separate Clean-Bench Swap Step (`bat r11swp1` + `3.5 s` Self-Heal):**
   - **Default `candidate-2g-fix` (`#2` OFF by default):** `FO4SFWorkshop.esm` ships `GLOB 0B00084A` (`default = 0.0`) and `FO4SF_Sanctuary01Quest.psc` sets `EnableCleanBenchSwap = False`, so **`04005C50` stays active and bound by default** (`sanctuary01 clean_bench_swap active=false ref=<ref>`). Return to Sanctuary Hills workbench `04005C50` (`(-2329.25, -1420.19, 112.09)` m) after `Min00` reaches `stage 200` (`FO4SF_Sanctuary01` active) and press **`E`**.
   - **Review `#3` & `#8` & `A2.1` Default PASS:**
     - Workshop opens cleanly on `04005C50` with zero modal messagebox (`R2` preserved) and `"Commonwealth"` / `"Massachusetts"` display overrides (`LCTN 0x01B736`/`0x01B735`, `LCTN 0x061527`/`STDT 0x05E5CB`).
     - **`#3` Stage-100 Non-Stall:** Because Sturges (`09000A01`) has not arrived yet (`!IsSturgesReadyForSanctuary()`, disabled until `S9`), `"not arrived"` is treated like `"missing"` — bench activation skips Objective `50` (`"Talk to Sturges"`) completely, logs `sanctuary01 open_mode sturges_unavailable -> stage 1000`, and advances straight to **Objective `1000`** with `sanctuary01 bench_activated=true ref=<ref> complete=false stage=1000` (keeping `09000A50` `FO4SF_MQ103` at `stage 0` per `R1`).
     - **`#8` / `A2.1` Menu Guard (`openMenuCount` Removed):** Stay inside `WorkshopMenu` for **`>= 10 s`** within `3.5 m` of the bench — verify `CheckSturgesTalkFallback` (now using explicit boolean workshop flags `workshopModeActive`, `workshopMenuOpen`, `talkBoxOpen`, `benchMenuOpen` + `Utility.IsGameMenuPaused()`, `Game.IsPlayerInDialogue()`, and control-lock checks with `openMenuCount` deleted) NEVER fires a four-button messagebox while any menu is open.
   - **Dedicated Separate Opt-In Step — Turn Clean Bench Swap ON (`#2`, `0B00084A = 1` via `bat r11swp1`) & `3.5 s` Self-Heal Proof:**
     - Save a throwaway save before testing; run `P3`-safe **`bat r11swp1`** (`set 0B00084A to 1`) and reload / re-enter Sanctuary so `TryBindBench` swaps `04005C50` -> persistent `ACTI 0B000849` (`"Sanctuary Hills Workshop"`, `KYWD 0B000848`, `0/7` Starfield `OutpostCategory*` KWs -> `0/261` Starfield `COBJ` records match; logs `sanctuary01 clean_bench_swap active=true ref=<ref>`).
     - Press **`E`** on `0B000849`:
       - **Clean-Swap PASS:** `WorkshopMenu` opens with **ZERO Starfield outpost entries** (`"Industrial Workbench"`, `"Spacesuit Workbench"`, `"Research Lab"`, iron/aluminum outpost costs) and **ZERO `"WORKSHOP, MARS, SOL"` footer** *(real settlement building is the next mission, not this round)*.
       - **`3.5 s` Self-Heal Safety Proof (`#2`):** Activating `0B000849` arms Timer `3` (`3.5 s`). If `WorkshopMenu`/workshop mode does NOT open within `3.5 s`, Timer `3` automatically logs `sanctuary01 clean_bench_swap self_heal reason=no_workshop_menu`, re-enables `04005C50`, disables `0B000849`, and re-binds `boundBench` + Alias `0` back to `04005C50` so the player is never stranded without a bench!
     - **Immediate Rollback:** Run `P3`-safe **`bat r11swp0`** (`set 0B00084A to 0`) — reloading automatically restores `04005C50` whenever `0B00084A == 0`.
2. **`D5` Pip-Boy Overlap & Keyboard/Controller Glyphs + `A2.6` `INV`/`DATA`/`RADIO` Staged Fill & One-Line Rollbacks (`F7`, `M`, `Tab`):**
   - **Shipped Player INI & One-Line Rollbacks (`<starfield-dir>/Data/SFSE/Plugins/FO4SFPipboyMenu.ini`, no DLL rebuild):**
     - Out-of-the-box: `ShellBackdrop=1`, `ShellVitalsFill=1`, `HideStarfieldWatch=1`, `SuppressDataMenu=0`, `TabOpensPipboy=0`.
     - **One-line rollbacks:** set **`ShellVitalsFill=0`** (reverts to `2f` vitals path), **`ShellBackdrop=0`** (reverts opaque dark CRT backdrop), **`HideStarfieldWatch=0`** (restores Starfield wrist watch HUD), and/or build `FO4SFCoreValues.esm` with **`--commonwealth-weather 0`** (reverts `D7` Mars-wide weather override).
   - **`D5` Overlap PASS:** Press **`F7`** (`STAT` page) -> `ApplyShellHintBarLayout` shifts `ButtonHintBar_mc.y` from `575.0` to `672.0` (`step=shell_hintbar_layout when=kShow old_y=575.0 new_y=672.0 ok=1`); confirm `"PLAYER"` no longer overlaps `"RADAWAY (0)"` (fixing `2g` still `12`), while keeping `2g`'s opaque dark backdrop, real `HP`/`AP` (`> 0`, never `HP 0/0` or `AP --/--`), and full `"10.23.2287"` date.
   - **`D5` Keyboard Glyphs PASS:** On keyboard + mouse (no controller connected), `ApplyShellPlatform` sends `SetPlatform(0, false)` and hides `LeftTriggerButton_mc`/`RightTriggerButton_mc` (`step=shell_platform when=kShow platform=0 called=1 triggers_hidden=2`); confirm controller glyphs (`A, X, Y, LT, RT`) do NOT clutter the Pip-Boy bar.
   - **`A2.6` `INV`, `DATA`, and `RADIO` Page Checks (`ShellVitalsFill=1`):** Cycle across **STAT -> INV -> DATA -> MAP -> RADIO** and close/reopen with `F7`/`M`/`Tab`. Confirm zero crash or blanked lists (`ReplaceAs3ArrayFromStaged` preserves prior lists on any failed `CreateObject`, logging `step=data_obj_stage_abort` if tripped), `ApplyBottomBarDateFix` and `ShellBackdrop` run once per movie/page without per-tick spam, and `step=quest_cache_build` runs once per session (`R6` preserved).
3. **`D7` + Review `#4` + `#5` + `#9` — Clear Commonwealth Weather (Known Side Effect) & Watch-Hide Retry (`try=<n>`, Non-Fatal Stage 2):**
   - **`D7` + Review `#4` Weather PASS & Known Side Effect:** `FO4SFCoreValues.esm` validates exact source `EditorID`s (`ClimateUniqueNewAtlantis`, `ClimateUniqueCydonia`, `ClimateUniqueCydoniaFrozen`, `ATMO_Mars`, `ATMO_Jemison` — refusing build on mismatch) and copies `naClmt.WeatherSettings` (`DeepCopy()`) onto `CLMT 0x00310DB1`/`0x002EDEA5` plus `ATMO_Jemison` (`0x0000C010`) onto `ATMO_Mars` (`0x0000C9D2`) with zero extra plugins. Outdoors at Vault 111 hilltop, Sanctuary Hills, and Concord, capture daylight stills confirming **clear Commonwealth weather** (NO heavy orange Mars dust storm!). **Known Side Effect (`#4`):** Overriding `ClimateUniqueCydonia`, `ClimateUniqueCydoniaFrozen`, and `ATMO_Mars` clears weather **Mars-wide** across Starfield's Mars surface; one-line build rollback is **`--commonwealth-weather 0`**.
   - **`D7` + Review `#5` + `#9` Watch Hide PASS:** With `HideStarfieldWatch=1` in the player bundle INI, `ApplyHudWatchHide` retries cleanly across `MenuOpenCloseEvent` transitions + main-thread UI poll if `no_root`/`missing_bottom_left` occurs on first tick, logging **`step=hud_watch_hide when=<when> try=<n> movie=<hex> ok=1 target=BottomLeftGroup_mc children_hidden=<n>`** once hidden (stopping retries afterward). Under **Review `#9`**, `g_hideStarfieldWatch` is removed from `ChannelIdsNeeded()` so missing channel IDs are non-fatal at Stage 2 (logging `step=hud_watch_hide_init ok=0 reason=channel_ids_unavailable` and disabling ONLY watch hide while `FO4SFPipboyMenu.dll` stays loaded). Confirm Starfield's bottom-left wrist watch (`"MARS"`, `O2`, `CO2`) is hidden while combat/center/rollover HUD stays visible, and optionally confirm **`HideStarfieldWatch=0`** restores it cleanly in one line with no rebuild.

```console
sqs 09000817
getstage 09000817
getstage 09000A50
bat r11swp1
bat r11swp0
```

```bat
; <starfield-dir>/r11swp1.txt — separate #2 opt-in Sanctuary clean bench swap ON (0B00084A = 1)
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
*(In default `candidate-2g-fix`, `clean_bench_swap active=false` logs first; `clean_bench_swap active=true` logs on the separate `bat r11swp1` opt-in step, and `sanctuary01 clean_bench_swap self_heal reason=no_workshop_menu` fires ONLY if `0B000849` fails to open `WorkshopMenu` within `3.5 s`.)*

### Negative / FAIL Conditions
- **`#2` FAIL:** `0B000849` swapping on by default before `bat r11swp1`, OR `0B000849` failing to open `WorkshopMenu` without triggering `3.5 s` self-heal back to `04005C50`; **`#3` FAIL:** objective `50` (`"Talk to Sturges"`) appearing while Sturges is disabled or `FO4SF_Sanctuary01` stalling at `stage 100`; **`D4` FAIL:** `"Industrial Workbench"`, `"Spacesuit Workbench"`, `"Research Lab"`, or `"WORKSHOP, MARS, SOL"` appearing on `0B000849` under `bat r11swp1`; **`#8` / `A2.1` FAIL:** Sturges fallback messagebox firing while `WorkshopMenu` or any menu is open; **`D5` FAIL:** `"PLAYER"` still overlapping `"RADAWAY (0)"` or controller glyphs (`A, X, Y, LT, RT`) stuck on keyboard+mouse; **`A2.6` FAIL:** crash/blank list cycling `INV`/`DATA`/`RADIO` or per-tick backdrop/date spam; **`D7` / `#4` / `#5` / `#9` FAIL:** orange Mars dust storm still covering the Commonwealth, watch-hide failing without retrying, Stage 2 refusing to load `FO4SFPipboyMenu.dll` on channel-ID lookup failure, or Starfield `"MARS"`/`O2`/`CO2` wrist watch still visible with `HideStarfieldWatch=1`.

---

## Card R11-3 — `D6` Measured-Speed Walk Table (`4.8 m/s`, `97` Segments `L1`–`L9` + Overshoot Margins) & `A3` + Review `#10` Owner's Plain Console-Free `HAND-PLAY` Vault-Exit Walkthrough (`TEST-STATION` / `OWNER TEST`)

- **Stage Placeholders:** `<cand2g-fix-player-bundle>`, `<mapmarkers-stage-dir>`, `<starfield-dir>`
- **Disk Need:** `~4.2 GB` (`0 B` extra on installed Card R11-1).
- **Plugin List (`Plugins.txt`):** Same `13` Track-1 plugins as Card R11-1 (`FO4SFRouteLoot.esm` & `FO4SFBridge.esm` OFF).

### Install Command (Same Installed `13`-Plugin Bundle as Card R11-1)
```bash
python scripts/core/make_core_bundle.py verify --bundle-dir <cand2g-fix-player-bundle>
python scripts/game/exp_install.py install --exp-dir <cand2g-fix-player-bundle> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2g-fix-player-bundle> --starfield <starfield-dir>
```

### `D6` Corrected Walk-Table Parameters (`docs/testing/console-free-walk-list.md`)
- **Measured Run Speed:** Recomputed from `2g`'s measured **`4.6–5.0 m/s`** (`4.8 m/s` default parameter in `scripts/newgame/walk_headings.py --run-speed`, replacing `3.7 m/s`; `5a` is now **`6.97 s`** instead of `9.04 s`, preventing `2g` still `14`'s `11 m` overshoot into the house wall). Compass headings (`210.8 deg` verified exact on foot in `2g`) stay unchanged.
- **Target `(x, y, z)` & Overshoot Margin:** Every segment across all **`97` navmesh-verified segments (`L1`–`L9`)** keeps exact target `(x, y, z)` coordinates for position-correcting drivers AND states its binary-verified **safe overshoot margin (m)** (`safe_overshoot_m`) and hazard before a wall, railing, or drop.
- **Added Extended Place Legs (`63` New Segments, `L6`–`L9`):**
  - **`L6` (`6a`–`6t`, `20` segs, `237.77 m`):** Sanctuary Hills houses (Player House, Codsworth search houses `MQ102CodsworthSearchMarker01`/`04`, and Sanctuary Workbench `04005C50`).
  - **`L7` (`7a`–`7v`, `22` segs, `157.37 m`):** Museum of Freedom interior (front door -> stairs -> Preston's room).
  - **`L8` (`8a`–`8p`, `16` segs, `113.83 m`):** Museum basement (Preston's room -> `ConcordMuseumBasementTerminal` `020125AB` -> `MQ03SecurityGateREF` `02013042`; honestly noting the `2.2 m` cage alcove to `PowerGenerator01` `02012585` has `0` FO4 `NAVM` tris by design).
  - **`L9` (`9a`–`9e`, `5` segs, `57.39 m`):** Museum roof (exit door -> roof -> T-45 Power Armor `04008913` -> Crashed Vertibird Minigun `04005119`).

### `A3` `HAND-PLAY` — Owner's Plain Console-Free Walkthrough (Keyboard + Mouse Only, Zero Console!)

> **Rule for the Owner:** Do **NOT** open the `~` console, do **NOT** run any `bat` file, and do **NOT** use `moveto` or `setpos`. Play strictly with **`W`/`A`/`S`/`D`**, **mouse look**, **`E`**, **left-click / aim**, **`I`**, **`F7`**, **`M`**, and **`Tab`**.

| Step | Plain Keyboard + Mouse Action (Zero Console) | What You Should See |
|---|---|---|
| **1. Start New Game** | From the Main Menu, click **New Game**. Wait `~2 s` for the single `"Character Appearance"` prompt and click **`Quick start`** (or **`Create character`**). | You wake inside **Vault 111** beside the cryo pods in clear first-person view (zero stuck black screen, zero double prompt). |
| **2. Walk to the Pip-Boy (`L1`)** | Turn west down the main Vault 111 corridor. Press **`E`** to open the two closed vault interior doors (`0200126E`, `02001234`; all `4/4` Vault 111 walk-path doors are unlocked), walk through the open third doorway (`02001608`), bear slightly right around the corridor pillar, turn north to the foot of the control-deck ramp, and walk up the ramp to the skeleton beside the console (`1g` stance `(-54.50, 0.00, 0.59)`, `1.815 m` eye reach). | Both interior doors swing open smoothly on **`E`**, corridor footing holds without getting stuck, and the **Fallout 4 Pip-Boy 3000** (`0A00080F`) sits on the deck with **zero Starfield scanner box**. |
| **3. Pick Up the Pip-Boy** | Look down at the Pip-Boy 3000 on the deck and press **`E`**. | Prompt reads **`Pip-Boy 3000, Take [E]`**; picking it up equips the Pip-Boy (`F7` and `M` now work). |
| **4. Open the Vault Gear Door (`L2`)** | Turn slightly left toward the **Vault Door Controls** console (`0A000819`, `1.342 m` eye reach, Fallout 4 console mesh) and press **`E`**. Wait `~5 s`. | Prompt reads **`Vault Door Controls, Activate [E]`** (zero Starfield scanner box), the giant Vault 111 gear door rolls open, and a short catwalk hint tells you to head across to the exit lift. |
| **4b. Detour to Overseer's Desk & Pick Up the Stand-In Pistol (BEFORE the Lift!)** | Do **NOT** walk straight north from the control deck (solid wall at `x = -53, y = 4..14`). From the control-deck room (`y = 0`), walk **east** through unlocked doors `02001607` `(-40.23, 0.00, 0.00)` and `02001609` `(-32.91, 3.66, 0.00)` into the north-south hall (`x = -33`), walk **north** to `y = 14`, turn **west** down the security hall to `(-53.03, 18.29, 0.00)`, press **`E`** to open unlocked Overseer office door `0200160A`, and walk north through open gate `02001539` `(-54.92, 29.71, 0.00)` to the Overseer's desk `(-57.03, 30.01, 1.29)`. Pick up the **Vault 111 stand-in pistol (`0A000820`) + `48` rounds (`0A000821`)**, equip it (hold `E` on the pistol to take-and-equip, or press `I` / `Tab` -> `Inventory` -> `Weapons`) while still inside Vault 111 (`stage < 40`), then retrace your steps back to the control deck. | Both gun and ammo pick up cleanly on **`E`** (`pistol picked item=<item> count=<cnt>`), equip in hand, and arm you for Concord before leaving Vault 111 *(Starfield stand-in until `A4`'s Fallout 4 `10mm` lands)*. |
| **5. Walk Across the Catwalk & Onto the Exit Lift (`L3`, NO `setpos`!)** | Walk back down the control-deck ramp, turn south to face the open gear door, and walk straight out onto the catwalk. **Stop before the west railing** (`1.6 m` safe overshoot), turn right (north) onto the stair landing, walk down the stairs to the elevator cavern floor, and walk straight west into the open **Exit Lift cage** onto the center of the platform (`PlatformRadius = 2.0 m`). *(Like Fallout 4's buttonless `RespecTriggerREF` `0x08C94A`, the lift has no wall button; if you click **`Stay`**, simply step `~2 m` back out the open cage entrance and step back onto the platform to re-open the prompt!)* | You walk cleanly off the ramp, through the open gear door, down the stairs without snagging, and stepping onto the platform automatically opens the **`S.P.E.C.I.A.L.`** screen with **`33` points to spend** (`40` total). |
| **6. Spend `33` `S.P.E.C.I.A.L.` Points & Ride Up** | Allocate your **`33`** points across `S.P.E.C.I.A.L.` and click **`Continue`**. Wait `0–7 s` as the lift rises to the surface. | The lift rides up to the Vault 111 hilltop and **automatically fades into clear Commonwealth daylight** (no orange Mars dust storm, no Starfield wrist watch, no stuck black screen, no false return-lift popup). |
| **7. Walk Down to Sanctuary & Talk to Codsworth (`L4`)** | Follow the paved Vault 111 hilltop trail north-northeast around the switchback, down the slope, across the creek footbridge (`04014BA7`), and up the Sanctuary street to **Codsworth** (`09000811`). Aim at Codsworth and press **`E`**. | Ground holds all the way down; Codsworth's real voiced `DialogueMenu` frames him cleanly on **both** greeting and choice list (never under his body), asked questions grey out with zero greeting replay, and ending with Concord pops **`"New mission: When Freedom Calls"`**. |
| **8. Walk to Concord & Fight the Raiders (`L5`, God Mode OFF)** | Walk south down Sanctuary street, turn east across **Sanctuary North Bridge** (`04005199`), follow the paved highway past **Red Rocket Truck Stop**, and descend into **Concord Main Street**. Use cover and defeat all `5` raiders with your Vault 111 stand-in pistol and **god mode OFF**. | Paved road stays solid under foot; all `5` raiders engage aggressively in the street firing `Eon` (not `Coachman`) without warping away; an armed cover-using player survives and clears the street (`Talk to Preston Garvey`). |
| **9. Close-Up Raider Look (`D2`) & Talk to Preston** | Walk up on foot to `1–2 m` of two defeated raider bodies on Main Street and look down, then walk to the Museum of Freedom door, inspect **Preston Garvey** (`09000802`), press **`E`**, ask a non-ending question, and **move the cursor/highlight off the asked row (e.g. down to Row 1)** before finishing the dialogue. | Raiders wear Fallout 4 raider clothes up close (zero spacesuits/helmets); **Preston wears his Fallout 4 Minuteman tricorn hat on his head** and duster (clean leather gloves); pressing **`E`** opens one real `DialogueMenu` (zero messagebox), moving the silver highlight off Row 0 shows the asked question dimmed (`AlreadySaid_Unselected`) with zero greeting replay, and finishing awards `100` credits and starts **`"New mission: First Settlement"`**. |
| **10. Return to Sanctuary Workbench & Check Pip-Boy** | Walk back to the Sanctuary workbench (`04005C50` by default in `candidate-2g-fix`, or `0B000849` under the separate `bat r11swp1` test) and press **`E`**; close it and press **`F7`** (cycling `STAT` -> `INV` -> `DATA` -> `RADIO`) and **`M`**. | Workbench opens cleanly with zero Sturges popup and advances without stalling on disabled Sturges (`#3`); Pip-Boy shows opaque dark backing, non-overlapping `"PLAYER"` / `"RADAWAY (0)"`, keyboard prompts, real `HP`/`AP`, and `"10.23.2287"`. |

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
FO4SF_NEWGAME rt=<rt> pipboy pickup equipped flag=1 worn=true
FO4SF_NEWGAME rt=<rt> stage 30 by=vault_console
FO4SF_NEWGAME rt=<rt> catwalk hint shown
FO4SF_NEWGAME rt=<rt> pistol picked item=<item> count=<cnt>
FO4SF_NEWGAME rt=<rt> landed z=<z> confirmed=True fallback=false world=<world>
FO4SF_NEWGAME rt=<rt> stage 200 by=Trigger
FO4SF_NEWGAME rt=<rt> fade in by=story_landing loaded=true cell=<cell>; saving and HUD on
FO4SF_MISSION rt=<rt> codsworth01 complete choices=<cnt> concord_pointed=true
FO4SF_MISSION rt=<rt> complete stage=200
```

### Negative / FAIL Conditions
- Any Vault 111 door, ramp, gear-door threshold, catwalk stair, or exit-lift platform requiring a console `moveto`/`setpos` to pass; falling through converted Commonwealth terrain along `L4`/`L5`; or walk-table hold times overshooting walls/railings at `4.8 m/s`.
