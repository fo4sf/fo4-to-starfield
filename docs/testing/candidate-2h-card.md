# Session Card — `candidate-2h-4`: Round 16 (`I1`–`I8` on `#853`: CryoPod Exit, Lit Wrist Screen, Ride Speed & Single Load, Ride Down Robustness, `Main.ba2` Translate & Toast Fix, Codsworth E-Talk & Thruster)

> **Build Profile & Verdict (`27 Nov 2026`):** **`OFFLINE STAGED — UNPROVEN IN GAME`** (`NEW GAME needed`; clean start from Vault 111 required — do NOT load pre-`candidate-2h-4` saves).
>
> - **Branch & Stack Integrated (`I1`–`I8`):** `gemini/round11-s2-s6-2h` (`#853`, on top of `2h-3` `96d98fe0`, `#852` `fix7b` `da4e7902`, `#868`, `#867`, and `#854`).
> - **Round 16 Fixes Included (`I1`–`I8`):**
>   - **`I1` (CryoPod Start & Step-Out):** Builds `FO4SFVaultPod.esm` (`ACTI 0x800` `FO4SF_PlayerCryoPod` + persistent `REFR 0x801` + Initially Disabled `0x001617`); sets `pod_exit_mode="cryopod_anim"` on EVERY FO4 start (`safe_spawn` is fallback only); places player inside closed pod (`seat_step_m=-0.55`, clearance gate `min_clearance=0.0531 m`, `"Use preset look"` renamed button 0), runs setup under black before `StartMessage.Show()`, plays `5.3333 s` FO4 `Exit`, and lets player walk out before `stage 20` autosave.
>   - **`I2` (Lit Green Wrist Screen & Slot `55`):** Renders lit green FO4 status screen (`pipboy_screen_idle_color.dds` + `_emissive.dds`, fixed geometry `PipboyScreen` on all 8 NIFs), moves completely off bit `54` (`ChronoWatch` clash) to single bit-`55` addon `0x823` (`0x824` retired), logs `pipboy wrist 3d housing=<bool> screen=<bool>` and `step=pipboy_screen wrist_draw=none|static|rtt`.
>   - **`I3` (Ride Up — No Sit, One Load, Rising Arrival):** Queues `QueueSharedMapSetup("pickup")` non-blockingly (`CallFunctionNoWait`), sets `fade_lead_s=1.4` + `fade_out` log, lands via persistent merged arrival marker `0x000826` inside `04000CF0` (`surface one_move off=<m> set=False`), polls `EnsureSurfaceLiftCog` (`<= 3 s` `wait_3d`), plays rise BEFORE `SetPosition`, and shares a plain-black `LoadingMenu` cover fallback (`SetLoadingBlackCover`).
>   - **`I4` (Ride Down & Lift Robustness):** Restores control at `reset_motion_s=9.9 s` (`arrived dir=down`), guards `Done` (`interior busy until_done`), unifies `ArriveOnInteriorLift`, prevents prompt soft-locks, suppresses repeat arrival banners on every ride up, resets refused cog safely, and ticks `1.0 s` near pad at stage `200`.
>   - **`I5` (`QUEST` Label & Toast Fix):** Stops stripping `Data/Interface/Translate_en.txt` to loose `sfse_sidecar/` so `exp_install.py --pack --textures-archive` puts it in `FO4ActorRaider - Main.ba2` (`runtime_ok=1` + `G12(d)` `"Quest"`, `"Quests"`, `"Quest Log"`), checks `Main.ba2` in `hud_quest_label.h` & `check-bundle`, and removes stage-`200` `CompleteQuest` toast spam under `single_quest`.
>   - **`I6` (Codsworth):** Invisible collision-volume talk proxy (`codsworth_talk_proxy.nif`, `09000970`), clears 4 `Skin_MiniBotA_Base` / `MiniBotARace` bindings so `E2` `LegsHandyThruster` draws with zero legs, gates greeting `0x942` with `SayOnce` + `0x97C` (`0x943` repeat), and yields `FO4SF_Min00Quest.PlaceCodsworth` during `S3` house walk (`24/30/32 -> 34 -> 36/38 -> 40 -> 50 -> 100 -> min00 given`).
>   - **`I7` & `I8` (Minors & Tooling):** Tops up `10mm Round` pickup to `count=48`, switches arrival weather to existing `WTHS 0x001034AB` (`WeatherUniqueNA_Clear_Unique`), wires death reload to `SetLoadingBlackCover(true, "death_reload")`, renames `"Use preset look"`, updates timed `10 s` `3b` row (`bat h2hp`), and fixes `exp_install.py` casefold + `verify_texture_archive` DDS pixel-payload hash.
> - **P3 Scope Note:** P3 (`0` `M`/`N`/`V`) applies to **typed interactive** console lines and **batch filenames** (`pod_seat.txt`, `pod_step.txt`, `h2s.txt`, `h2hp.txt`, `h2*.txt`); `getglobalvalue`, `getav`, `moveto`, and `additem` stay inside `bat/*.txt`.
> - **Logging Preflight (`G3`, Required Before Running):** Confirm `StarfieldCustom.ini` sets all `3` `[Papyrus]` keys (`bEnableLogging=1`, `bEnableTrace=1`, `bLoadDebugInformation=1`); wait `10 s` after New Game launch and verify `Documents/My Games/Starfield/Logs/Script/User/fo4sf_newgame.0.log` is non-empty before proceeding.

---

## 1. Staged Component Scope & Check-Bundle Gates

| Component / Artifact | Contract & Changes in `candidate-2h-4` | Notes |
|---|---|---|
| `<cand2h-port-dir>/FO4Port.*` + `FO4TerrainCore.esm` + `FO4SFExitLift.esm` | Lossless Slot 1 (`L3` merged `NAVI 0x00000FF1` + Museum cells; Vault 111 surface cog `ref=0x04005A77` `base=fo4terraincore.esm:0x000A2D4B` `FO4Core_acti_19d22f_fallout4` "Vault 111 Elevator" overridden by `FO4SFExitLift.esm` at `(-2475.58, -1403.93, 33.25)` `G4`) | Passed `--port <cand2h-port-dir>/FO4Port.esm` |
| `FO4SFVaultPod.esm` (`I1`) | `ACTI 0x800` `FO4SF_PlayerCryoPod` (`ActivatorStateGraph01.agx`, `Exit=StateA_Play`), persistent `REFR 0x801` in cell `0x0011F3` at `(9.142858, -4.114286, -1.0285715)`, Initially Disabled override `0x001617`; offline clearance `min_clearance=0.0531 m` at `seat_step_m=-0.55` | Enforced by `check-bundle` (`pod_anim`) |
| `FO4SFCoreValues.esm` | `--fo4-arsenal 1 --fo4-10mm 1` (`25/25` arsenal WEAPs `0x000899..0x0008D6`, P6b ammo/items, `--test-mode 0` in `player`) | Verified by `check-bundle --require-arsenal` |
| `FO4SFMission.esm` | Zero `SCEN` VMAD properties (`H2`); `FO4SF_CodsworthTalkActi` (`0x970` invisible collision volume `I6a`); zero `Skin_MiniBotA_Base` / `MiniBotARace` on Codsworth (`I6b`); `SayOnce` greeting gate `0x942`/`0x97C`/`0x943` (`I6c`); `Min00` keeper yield during house walk (`I6d`); `load_doors.json` (`H5`); `FO4SFWorkshop` (`H6`) | `codsworth_talk_proxy.nif` staged beside `E2` |
| `FO4SFNewGame.esm` | `pod_exit_mode="cryopod_anim"`, `"Use preset look"` (`I7`), `PipboyScreen` single bit-`55` addon `0x823` (`0x824` retired `I2`), `VaultAmmoCount=48` (`I7`), `ArrivalWeatherId=0x001034AB` (`WTHS` `I7`), `ArrivalMergedMarkerId=0x000826` (`I3`), `fade_lead_s=1.4` & `reset_motion_s=9.9` (`I3`/`I4`), `SetLoadingBlackCover` shared hook (`I3`/`I7`) | Zero Quest-Complete spam at stage `200` (`I5`) |
| `FO4SFWorkshop.esm` | `FO4SF_WorkshopCoreQuest` (`0x800`) + `ACTI 0x849` bound from `settlement_rules.json` (`FO4TerrainCore.esm`, `0x005C50`, `250.0 m`); W5/W6 `"NOT WIRED"` | `#867` clean |
| `FO4SFMapMarkers` (`map-markers/`) | Verified `--require-map-markers` (`PrepareKnownUndiscoveredAll` queued non-blockingly `I3A`; silent `DiscoverSingleMarkerSilent` on every arrival `I4f`) | Installed via `map_markers_install.py` |
| `FO4SFPipboyMenu.dll` + `Main.ba2` (`sfse_sidecar` + `Data/Interface/Translate_en.txt`) | Rebuilt merged DLL (`I2` `step=pipboy_screen wrist_draw=...` + `3d_rtt` stub + `I5` `Main.ba2` translate check); `Data/Interface/Translate_en.txt` packed into `FO4ActorRaider - Main.ba2` (`QUEST`, `Quest`, `QUESTS`, `QUEST LOG` `I5`/`G12(d)`) | Enforced by `check-bundle` (`quest_translate`) |

---

## 2. Offline Verification, Install & Rollback (Game Closed)

```bash
# 1. Offline gates (Game closed: Starfield.exe == 0, CreationKit.exe == 0, Archive2.exe == 0)
python scripts/core/make_core_bundle.py verify --bundle-dir <cand2h-player-bundle> --port <cand2h-port-dir>/FO4Port.esm --require-map-markers
python scripts/testing/check_beginning_pilot.py check-bundle --bundle-dir <cand2h-player-bundle> --require-arsenal

# 2. Reversible FO4Port.* swap (backup vanilla/prior port if backup folder absent)
mkdir -p <starfield-dir>/Data/FO4Port_pre2h_backup
cp -n <starfield-dir>/Data/FO4Port.esm "<starfield-dir>/Data/FO4Port - Main.ba2" "<starfield-dir>/Data/FO4Port - Textures.ba2" <starfield-dir>/Data/FO4Port_pre2h_backup/
cp -f <cand2h-port-dir>/FO4Port.esm "<cand2h-port-dir>/FO4Port - Main.ba2" "<cand2h-port-dir>/FO4Port - Textures.ba2" <starfield-dir>/Data/

# 3. Install 14-plugin player bundle (--pack --textures-archive) + SFSE sidecar + map-markers + bat/*.txt
python scripts/game/exp_install.py install --exp-dir <cand2h-player-bundle> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFVaultPod.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack --textures-archive
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2h-player-bundle> --starfield <starfield-dir>
python scripts/game/map_markers_install.py install --dir <cand2h-player-bundle>/map-markers --starfield <starfield-dir>
cp -f <cand2h-player-bundle>/bat/*.txt <starfield-dir>/
```

### Reversible Rollback (Game Closed)

```bash
rm -f <starfield-dir>/pod_seat.txt <starfield-dir>/pod_step.txt <starfield-dir>/h2s.txt <starfield-dir>/h2hp.txt <starfield-dir>/h2st.txt <starfield-dir>/h2h2.txt <starfield-dir>/h2h3.txt <starfield-dir>/h2h4.txt <starfield-dir>/h2f.txt <starfield-dir>/h2b.txt <starfield-dir>/h2k.txt <starfield-dir>/h2p.txt <starfield-dir>/h2r.txt
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/map_markers_install.py uninstall --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
cp -f <starfield-dir>/Data/FO4Port_pre2h_backup/FO4Port.esm "<starfield-dir>/Data/FO4Port_pre2h_backup/FO4Port - Main.ba2" "<starfield-dir>/Data/FO4Port_pre2h_backup/FO4Port - Textures.ba2" <starfield-dir>/Data/
rm -rf <starfield-dir>/Data/FO4Port_pre2h_backup
```

---

## 3. Card 2h-1 (`I1` CryoPod, `S2` Roaches, `I2` Lit Wrist Screen, `I3`/`I4` Lift, `I5` QUEST & Toasts — `REACHABLE` / `TEST-STATION`)

| Step | Action | Expected In-Game & Log Result | Status | VIDEO / Media |
|---|---|---|---|---|
| **1a. `I1` CryoPod Wake, `"Use preset look"` & Door Walk-Out (`NEW GAME needed`)** | Launch SFSE -> **New Game -> Vault 111 / Story** (`10 s` `fo4sf_newgame.0.log` preflight). Verify `WASD`/mouse blocked while appearance box (`Create character` / `Use preset look`) shows inside closed pod; pick `Use preset look`; walk out once `Exit` door finishes rising (`~5.3 s`). | First visible frame shows inside of closed pod (`Window` corridor view through glass), NOT 2.5 m outside; `enter vault mode=pod_seat` < `pod_hold on` < `stage 15 by=cryopod_anim` < `pod_open accepted=true` < door rises `~5.33 s` -> `pod_step_out by=walk` -> player steps out (`pod_exit mode=cryopod_anim ... by=walk`) -> `stage 20` autosave; HUD watch hidden, `QUEST` label (`G9`/`G12d`). *(Creator uses black cover by default.)* | `REACHABLE` | **VIDEO** `v111-pod`: `>= 10 s` closed-pod wake -> choice -> `5.3 s` door open -> walk step-out; **`audio: not judged`**. |
| **1a-probe. `I1` CryoPod Inside Static vs `SetPosition` Probe** | Type `tcl`, run `bat pod_seat`, take interior still, `tcl` off to check push; run `bat pod_step` to check whether `SetPosition` causes a black frame. | `pod_seat` places camera inside closed pod without clipping shell; `pod_step` logs `SetPosition` black-frame observation (`bat/pod_seat.txt`, `bat/pod_step.txt`). | `TEST-STATION` | Still + clip `v111-pod-probe`: interior frame + `SetPosition` result. |
| **1a-fallback. `I1` CryoPod Fallback Path** | Disable `0x000801` (`FO4SFVaultPod.esm`) before choosing `Use preset look`. | `pod_exit mode=safe_spawn fallback_from=cryopod_anim reason=play_refused` or `reason=not_loaded` within `8 s`; controls returned cleanly. | `REACHABLE` | Take `v111-pod-fallback` (when testing fallback branch). |
| **1b. `S2` Vault 111 Roaches (`09000B90`, `L2`)** | Walk Vault 111 corridor toward Overseer/lift (`09000B8D=1`, `09000B8C=0` empty slot). | `s2 vault_roaches creature_slot=empty fallback=stage_gate` -> completes with `stage=100` *(5 markers visited <= 12 m)* or `stopped reason=left_vault_stage_200`. | `REACHABLE` | Take `v111-corridor`: `>= 6 s` hall traversal. |
| **1c. `I2` Lit Wrist Pip-Boy, `I7` `10mm Round` (`48`) & `I3` Ride Up #1** | Walk `L10` armory leg; **press `E`** on Armory pistol (`0A000820`), ammo box (`0A000821`), and Pip-Boy (`0A00080F` -> triggers `pipboy_pickup` autosave + `QueueSharedMapSetup("pickup")` + bit-`55` equip); press **`F7`** (`Arm=1` raise -> 2D menu -> lower); **press `E`** on Vault console (`0A000819`), spend all S.P.E.C.I.A.L. points (`pool == 0`), ride cog up. | **`10mm Pistol` + `10mm Round` (`count=48`, HUD `12\|36` / `48` total)**; wrist draws FO4 housing + **lit green `PipboyScreen`** (`pipboy_screen_idle_color.dds` + `_emissive.dds`) at rest/idle/`F7` (`pipboy wrist 3d housing=True screen=True`, `step=pipboy_screen wrist_draw=static`); **`I3` stopwatch from `ride start dir=Up`**: `0.0 s` platform start -> `~8.47 s` `fade_out` (`fade_lead_s=1.4`) -> `~9.8-10.0 s` `transfer` (ZERO sit at top!) -> **1 `LoadingMenu`** to `0x000826` (`set=False` in `04000CF0`, zero dark-mountain/trailer flashes!) -> `wait_3d` (`<= 3 s`) -> `PlaySurfaceCogRise` carries rider up (`rise carry t=2.0`) -> clear New Atlantis hilltop daylight (`WTHS 0x001034AB`), zero Red Rocket banner. | `REACHABLE` | **VIDEO** `v111-wrist-lit`: `>= 6 s` lit green wrist + `F7`; **VIDEO** `v111-lift-up-1`: stopwatch points `0.0 s` start -> `~8.5 s` black -> `<= 3 s` hilltop rise, 1 load, zero flashes. |
| **1c-suit. `I2(c)` Spacesuit Co-Equip Check (`1E2B18`)** | Equip Starfield spacesuit on bit `54` via `bat h2s` (`player.additem 1E2B18 1` / `equipitem`); inspect 1P & 3P left forearm. | Spacesuit (`SSChronoMark` on bit `54`) does NOT hide or unequip bit-`55` `FO4SF_PipboyWrist` (`0x80D`); wrist housing + lit green `PipboyScreen` remain drawn. | `TEST-STATION` | **VIDEO** / Still `wrist-spacesuit-h2s`: `>= 6 s` 1P + 3P wearing `1E2B18`. |
| **1d. `I5` & `G12(d)` `QUEST` Label in `Main.ba2` + Landing `"Out of Time"` Handoff (`stage 40 -> 200 -> Codsworth01`)** | Watch landing toasts (`stage 40 -> 200`) and open Pause / Quests menu. | `FO4ActorRaider - Main.ba2` serves `interface/translate_en.txt` (`runtime_ok=1`); HUD & menus read `QUEST` / `QUEST STATUS` / `NEW QUEST` / `Quest` / `QUESTS` / `QUEST LOG` (`0` `MISSION`); ONE `"Leave Vault 111"` objective-complete toast + ZERO `"OUT OF TIME"` quest-complete toast spam + ONE `"Go home"` toast. | `REACHABLE` | Included in `v111-armory-lift` + pause menu still. |
| **1e. `I4` Vault 111 Roundtrip Ride Down + Busy Guard + Repeat Ride Up** | From hilltop cog console, choose **RIDE LIFT DOWN TO VAULT 111**; step onto pad immediately (`< 23.8 s`); wait for `Done`, then ride back up. | **Stopwatch from `ride start dir=Down`**: cog drops -> interior `Play02` lowers rider from top (`z ~19.8 -> -1.78`) -> control returns at **`~9.9 s`** (`arrived dir=down`, NOT `24.5 s`!); stepping on before `Done` (`23.83 s`) stays closed with `lift_pair interior busy until_done`; repeat ride up uses state recovery + `1.0 s` pad tick, shows **ZERO `"VAULT 111 - LOCATION DISCOVERED"` banner**, and rises on surface cog. | `REACHABLE` | **VIDEO** `v111-lift-roundtrip`: `0.0 s` down -> `~9.9 s` arrival -> early pad guard -> repeat rise + zero banner. |

---

## 4. Card 2h-2 (`2a` Cold Reload, `H3` `#854` Codsworth Mr. Handy & Chrome, `S3` Walk, `H6` Sanctuary Bench — `REACHABLE` / `TEST-STATION`)

| Step | Action | Expected In-Game & Log Result | Status | VIDEO / Still |
|---|---|---|---|---|
| **2a. Cold Reload #1 (`Throwaway_2h_Surface`)** | Save on Vault 111 hilltop -> `Quit to Desktop` -> relaunch SFSE -> load save. | `reload mission stage=0 relocate_fails=0`, `codsworth01 reload stage=10 choices=0`, `FO4SF_LOADDOOR reload_ready`, daylight restored, zero spurious return-lift popup. | `REACHABLE` | Take `surface-cold-reload`: `>= 5 s` post-load hilltop view. |
| **2b. `I6` Codsworth `E` Talk (`2 m` Front & Side), Thruster Body, Greeting & `24/30/32 -> 100 -> min00 given`** | Walk to Sanctuary Hills (`09000811`). Take a **daylight still beside an FO4 reference**; aim at Codsworth from **`2 m` front and `2 m` side** and **press `E`** (`[E] Talk` via invisible `09000970` proxy -> `09000940`); exit & re-talk (greeting must NOT replay); pick Choice 3 (`stage 24`), then Choice 4 (`30 -> 32`), walk beside Codsworth House 1 -> House 2 (`34 -> 36/38 -> 40 -> 50`) -> finish Stage `50` (`000B9A`) -> `stage 100` -> `min00 given`. *(NO `bat h2h1`.)* | Codsworth hovers on **`FO4SF_HandyRace` (`09000818`) thruster (`LegsHandyThruster`) with ZERO MiniBot legs** (`Skin_MiniBotA_Base` cleared); `E` at `2 m` front & side fires `codsworth scene talk requested`; greeting does not replay on 2nd talk (`SayOnce` + `0x97C` -> `0x943`); `Min00` keeper yields during `S3` walk -> `stage 100 concord_pointed=true`, `min00 given by=codsworth`. | `TEST-STATION` (still + video judged by owner) | **Daylight Still** + **VIDEO** `sanctuary-codsworth-h3`: `>= 15 s` showing idle, turn, **thruster hover (zero legs)**, `E` talk front/side, House `01->02` walk -> `min00`. |
| **2c. `H6` Sanctuary Bench After First Settlement (`04005C50`)** | After *First Settlement* (`FO4SF_Sanctuary01` `09000817`) starts (`Row 5a`), press **`E`** on the Sanctuary workbench (`04005C50`) and **build one object**. | Bench plugin (`FO4TerrainCore.esm`), ID (`0x005C50` / `23632`), and radius (`250.0 m`) are read dynamically from `FO4SFWorkshop.esm` `0x000800` (`sanctuary01 bench_rule ...`); non-blank footer (zero `"."`); object places cleanly -> `min01 bench activated -> stage 100`. (`clean_swap_bench_runtime_hex` dropped; W5/W6 `"NOT WIRED"`.) | `REACHABLE` | Take `sanctuary-bench-h6`: `>= 6 s` opening bench & building `1` object after `FO4SF_Sanctuary01` starts. |

---

## 5. Card 2h-3 (`S4` Concord Exterior `z ~88`, `H1` Updated Fight Bar `3b`, Preston Balcony & Musket — `REACHABLE`)

| Step | Action | Expected In-Game & Log Result | Status | VIDEO |
|---|---|---|---|---|
| **3a. Hop Chain (`< 200 m`/axis) & Concord Exterior `z ~88 m`** | Walk or run `bat h2h2` -> `3 s` -> `bat h2h3` -> `3 s` -> `bat h2h4`. | Zero skips `>= 200 m`/axis; Concord buildings & Museum facade render solidly at **`z ~88.3..90.0 m`**. | `REACHABLE` | Take `concord-exterior-z88`: `>= 5 s` facade pan. |
| **3b. Updated Concord Street Fight (`H1` / `G11`, God Mode OFF, Timed `10 s` HP Read) & `I7` Death Reload Black Cover** | With **god mode OFF**, let Concord street raiders (`09000803..09000805`) fire while standing idle `10 s`, run `bat h2hp` at **`10 s`** (`player.getav health` inside `h2hp.txt`), then use cover & shooting to clear street raiders and inspect fallen raiders (`D2`). If testing death reload, verify plain-black cover (`0` Starfield loading planet/tip screen). | **PASS:** HP at `10 s` drops **`>= 20` while staying alive at `10 s`**, and cover + shooting clears cleanly to **`stage 30` (S4 Museum objective `60`) within `60` rounds**; raiders wear FO4 raider outfits (`0` spacesuits); death reload uses plain-black cover; **FAIL:** idle death in `< 10 s`, HP drop `< 20`, or out of ammo. | `REACHABLE` | Take `concord-fight-g11`: `>= 15 s` (`10 s` idle exposure + `bat h2hp` HP read at `10 s` + cover clear to `stage 30`). |
| **3c. Preston Balcony & `E` Display Musket (`09000BA8`) + Cells (`09000BAA..BAC`)** | Check Preston on 3F balcony (`z=98.51`); **press `E`** on display Laser Musket (`09000BA8`) and `3` Fusion Cell pickups (`09000BAA..BAC`). | `s4 balcony preston_z=98.51`, `s4 laser_musket granted cells=15` (`FO4_LaserMusket` `0600089D`), `+3x5` Fusion Cells. | `REACHABLE` | Take `concord-musket-pickups`: `>= 6 s` aiming & `Take [E]`. |

---

## 6. Card 2h-4 (`H5` Front Door Seam `4a`, Cold Reload `4a2`, `S5` 7 Raiders + Ground Climb `L3` — `REACHABLE`)

| Step | Action | Expected In-Game & Log Result | Status | VIDEO |
|---|---|---|---|---|
| **4a. `H5` Front Door `5x` Round-Trip (`E`, `LoadDoorController` Required)** | **Press `E`** on `FO4SF_S5_ExtFrontInRef` (`09000BB8`) -> Lobby -> **press `E`** on `FO4SF_S5_IntFrontOutRef` (`09000BB9`) -> Concord street; repeat `5x` round trips. | `FO4SF_LoadDoorQuest` (`09000BDE`) logs `FO4SF_LOADDOOR quest_init cell=<cell> exit_plugin=FO4TerrainCore.esm exit_anchor=0x0A775B secondary_plugin=FO4TerrainCore.esm secondary_anchor=0x0A775C` from `src/fo4sf/core/load_doors.json`; `FO4SF_ConfirmedLoadDoor` requires bound `LoadDoorController` (no `0xBDE`/`0x821` fallback); every press logs `confirmed ... core_cell=true`. | `REACHABLE` | Take `museum-front-door-5x`: `>= 15 s` door `Open [E]` + round trip. |
| **4a2. Cold Reload Inside Museum Front Door (`H1` / `H5`)** | Inside `FO4Port_ConcordMuseum01`, save **`Throwaway_2h_MidMuseum`**, **`Quit to Desktop`**, relaunch SFSE, load save, and **press `E` on `09000BB9`**. | `FO4SF_LOADDOOR reload_ready` -> pressing **`E`** resolves anchor from `FO4SF_LoadDoorQuest` (`0x0A775B` / `0x0A775C`) -> `FO4SF_LOADDOOR confirmed tag=s5_front_out dir=out ... core_cell=true` (zero hang after `activate_begin`). | `REACHABLE` | Take `museum-cold-reload-door`: `>= 8 s` post-reload exit. |
| **4b. `S5` 7 Raiders + Ground Climb (`L3`) + `E` Pickups -> `Min00 35`** | Engage `7` museum raiders (`09000BBC..09000BC2`); **press `E`** on Stimpaks (`09000BAE..BAF`), Caps (`09000BB1`), Bobby Pin (`09000BB3`), Pipe Pistol + `.38` (`09000BB5`). | Ground raider climbs atrium stairs via `NAVI 0x00000FF1` + `09000BE1`; `s5 museum_cleared dead=7/7 stage=35 preston_door=unlocked`. *(Keep throwaway save before `0100EDF0` unlocks for `5b`.)* | `REACHABLE` | Take `museum-raider-climb-pickups`: `>= 15 s` stair climb + pickups. |

---

## 7. Card 2h-5 (`H2` 3F Scenes & Stage-35->40->200->`0x817`, `5b` Gate & Fusion Core, `F9` Roof — `REACHABLE`)

| Step | Action | Expected In-Game & Log Result | Status | VIDEO |
|---|---|---|---|---|
| **5a. `H2` Preston Talk -> `S9` -> First Settlement (`0x000817`)** | Enter 3F room (`Preston 09000802` + `Sturges/Mama Murphy/Marcy/Jun` in `Settler Clothes` stand-in, `0` spacesuits); **press `E`** on Preston & Sturges (`EnableS6ToS9Full=1` path), complete `5b`, return to Preston -> walk group out to Sanctuary -> trigger **First Settlement** toast. | Dynamic Task 0c resolver logs `scene resolved via=file id=0x000BC9` / `0x000BD0` (no Scene VMAD properties); `s6 preston room scene started` -> `s6 stage 40 preston_group talk` (or fallback `s6 preston fallback stage=40 reason=no_scene` if `0x000BC9` absent) -> `stage 200` -> `min01 group_arrived sanctuary=true` -> `sanctuary01 stage 1000 obj=1000 hard_stop=true` (unlocks **`2c`** bench build). | `REACHABLE` | Take `museum-preston-to-first-settlement`: `>= 15 s` 3F talk, S9 exit, and First Settlement toast. |
| **5b. Basement Gate (`0x0100EDF0`) Terminal + Bobby Pin (`bat h2p`) + Fusion Core (`0C000809`)** | Unlock `0100EDF0` via Wall Terminal (`09000BD9`) AND via reload + `bat h2p` Bobby Pin lockpick; **press `E`** on `MQ102FusionCoreREF` (`09000BDB`). | Terminal & Novice lockpick both log `s6 stage 45 basement_gate opened`; `09000BDB` logs `pickup fusion_core granted=true fid=2057` + `s6 stage 50 fusion_core picked obj=95 stop=put_fusion_core_in_pa`. | `REACHABLE` | Take `museum-basement-both-paths`: `>= 15 s` both unlock paths + core pickup. |
| **5c. Roof Door `3x` Round-Trip (`F9` `(-1990.58, -1724.19, 97.56)`)** | **Press `E`** on `FO4SF_S5_IntRoofOutRef` (`09000BBA`) -> bulkhead -> **press `E`** on `FO4SF_S5_ExtRoofInRef` (`09000BBB`), `3x` round trips. | Solid standing on roof bulkhead at `z ~97.56` (`0` drop to `z ~88`), `confirmed ... core_cell=true` on all `6` legs. | `REACHABLE` | Take `museum-roof-door-3x`: `>= 12 s` roof arrival + re-entry. |

---

## 8. Console Inspection & `< 200 m` Hop Batches (`P3`: zero `M`/`N`/`V` in typed console or batch filenames)

````console
help "Calls" 4 QUST
getstage 09000816
getstage 09000800
getstage 09000B90
getstage 09000817
sqs 09000800
sqs 09000816
bat pod_seat
bat pod_step
bat h2s
bat h2hp
bat h2st
bat h2h2
bat h2h3
bat h2h4
bat h2f
bat h2b
bat h2k
bat h2p
bat h2r
````

### Required PASS Log Lines (Quoted Directly from Source)

```log
FO4SF_NEWGAME rt=<rt> enter vault ok=<bool> pos=<x> <y> <z> target=<tx> <ty> <tz> cell=<cell> mode=<mode>
FO4SF_NEWGAME rt=<rt> pod_hold on seat=<x> <y> <z> heading=<heading>
FO4SF_NEWGAME rt=<rt> pod_open play=Play01 accepted=<bool>
FO4SF_NEWGAME rt=<rt> pod_open done elapsed=<elapsed> ref=<ref>
FO4SF_NEWGAME rt=<rt> pod_step_out by=walk
FO4SF_NEWGAME rt=<rt> pod_exit mode=cryopod_anim hook_stage=15 moved=true pos=<x> <y> <z> heading=<heading> open_s=<open_s> by=walk
FO4SF_NEWGAME rt=<rt> pod_exit mode=safe_spawn fallback_from=cryopod_anim reason=<reason>
FO4SF_NEWGAME rt=<rt> pod_state on_load=open
FO4SF_NEWGAME rt=<rt> use preset look: preset kept, creator skipped
FO4SF_NEWGAME rt=<rt> pipboy wrist equipped item=<item> worn=<bool> slot=55
FO4SF_NEWGAME rt=<rt> pipboy wrist 3d housing=<bool> screen=<bool>
step=pipboy_screen wrist_draw=static
step=hud_quest_label_runtime file=present file_ok=1 mission_status=<status> mission_new=<new> runtime_ok=1
FO4SF_NEWGAME rt=<rt> vault_death_recovery=autosave stage=<st> after=pipboy_pickup
FO4SF_NEWGAME rt=<rt> pistol picked item=<item> count=1 equipped=True base=<form>
FO4SF_NEWGAME rt=<rt> pistol ammo picked item=<item> count=48 base=<form>
FO4SF_NEWGAME rt=<rt> map setup queued by=<why>
FO4SF_MAP rt=<rt> q=<q> prepare_all done count=<count> elapsed=<elapsed>
FO4SF_NEWGAME rt=<rt> lift_pair fade_out dir=<dir> elapsed=<elapsed> fade_at=<fade_at>
FO4SF_NEWGAME rt=<rt> surface one_move off=<off> set=<bool> cell=<cell>
FO4SF_NEWGAME rt=<rt> loading cover black opened why=<why>
FO4SF_NEWGAME rt=<rt> lift_pair surface_cog wait_3d n=<n> loaded=<bool>
FO4SF_NEWGAME rt=<rt> lift_pair rise carry t=2.0 z=<z>
FO4SF_NEWGAME rt=<rt> lift_pair ride arrived dir=<up|down> z=<z> cell=<cell> world=<world>
FO4SF_NEWGAME rt=<rt> lift_pair interior busy until_done
FO4SF_NEWGAME rt=<rt> lift_pair interior state=<A|B> why=<why>
FO4SF_NEWGAME rt=<rt> arrival weather id=<id> plugin=<plugin> override=<override> weather=<wthr>
FO4SF_NEWGAME rt=<rt> death_reload plain_black_cover=<bool>
FO4SF_NEWGAME rt=<rt> landing handoff mode=single_quest newgame_completed=False codsworth01_displayed=True
FO4SF_MISSION rt=<rt> codsworth talk proxy model=invisible_volume visible=false
FO4SF_MISSION rt=<rt> codsworth scene talk requested scene=<scene> via=<via> stage=<stage>
FO4SF_MISSION rt=<rt> codsworth01 greeting_played=1
FO4SF_MISSION rt=<rt> codsworth01 stage 24 by=info
FO4SF_MISSION rt=<rt> codsworth01 stage 30 house=1
FO4SF_MISSION rt=<rt> codsworth01 stage 36 house=2
FO4SF_MISSION rt=<rt> codsworth01 stage 50 scene started
FO4SF_MISSION rt=<rt> codsworth01 stage 100 concord_pointed=true
FO4SF_MISSION rt=<rt> min00 given by=codsworth
FO4SF_MISSION rt=<rt> s2 vault_roaches creature_slot=empty fallback=stage_gate
FO4SF_MISSION rt=<rt> codsworth01 s3 creature_slot=empty fallback=arrival_advance
FO4SF_MISSION rt=<rt> scene resolved via=file id=0x000B9A scene=<ref>
FO4SF_MISSION rt=<rt> scene missing id=0x000BC9
FO4SF_MISSION rt=<rt> s5 museum_cleared dead=7/7 stage=35 preston_door=unlocked
FO4SF_MISSION rt=<rt> s6 room_scene requested sturges=false via=activate
FO4SF_MISSION rt=<rt> s6 preston room scene started
FO4SF_MISSION rt=<rt> s6 preston fallback stage=40 reason=no_scene
FO4SF_MISSION rt=<rt> s6 sturges room scene started
FO4SF_MISSION rt=<rt> s6 stage 40 preston_group talk
FO4SF_MISSION rt=<rt> s6 basement_gate unlocked reason=<reason> pending_stage40=true
FO4SF_MISSION rt=<rt> s6 stage 45 basement_gate opened
FO4SF_MISSION rt=<rt> pickup fusion_core granted=true fid=2057
FO4SF_MISSION rt=<rt> s6 stage 50 fusion_core picked obj=95 stop=put_fusion_core_in_pa
FO4SF_MISSION rt=<rt> min01 group_arrived sanctuary=true via=<via>
FO4SF_MISSION rt=<rt> sanctuary01 stage 1000 obj=1000 hard_stop=true
FO4SF_MISSION rt=<rt> sanctuary01 bench_rule plugin=FO4TerrainCore.esm ref=23632 radius=250.0
FO4SF_MISSION rt=<rt> min01 bench activated -> stage 100
```

---

## 9. Later Plug-In Seams (`I1`–`I8` + Wave B)

| Item | 0.1 Behaviour | Later plug-in |
|---|---|---|
| **I1 (CryoPod `cryopod_anim`)** | `FO4SFVaultPod.esm` (`0x800`/`0x801`/disabled `0x001617`), closed-pose clearance gate (`seat_step_m=-0.55`, `min_clearance=0.0531 m`), FO4 `5.33 s` `Exit` & walk-out. | **Later plug-in:** FO3's Vault 101 and NV's Doc Mitchell starts use the same `pod_anim`-style block in `game_start_config.json`, with their own asset and seat, and no script change. |
| **I2 (Wrist Screen & Bit `55`)** | Lit green `PipboyScreen` emissive page on single bit-`55` addon `0x823` (`0x824` retired), `2d_imenu` on `F7`. | **Later plug-in:** Live 3D wrist projection hooks behind `ScreenSource=3d_rtt` (`FO4SF_PipboyScreenSource=2`) via `OpenPipboy3DRTTMainThread()` onto `PipboyScreen` without touching `2d_imenu`, slot `55`, or ARMO/ARMA builds. |
| **I3 / I4 (Lift Speed, One Load & Robustness)** | `QueueSharedMapSetup` (`CallFunctionNoWait`), `fade_lead_s=1.4`, merged marker `0x000826`, `wait_3d`, `reset_motion_s=9.9`, `SetLoadingBlackCover`, unified `ArriveOnInteriorLift`, silent discovery on every arrival. | **Later plug-in:** FO3/NV exit lifts add per-pair entries in `lift_pairs.json` without editing `FO4SF_NewGameQuest.psc`, and death reloads / world moves reuse `SetLoadingBlackCover(true/false, why)` on the single `LoadingMenu` hook. |
| **I5 (`QUEST` Label & Toasts)** | `Data/Interface/Translate_en.txt` packed inside `FO4ActorRaider - Main.ba2`; zero stage-`200` `CompleteQuest` toast spam under `single_quest`. | **Later plug-in:** Global `Interface/Translate_<lang>.txt` overrides pack inside `<FirstPlugin> - Main.ba2`, while per-game label & handoff policies stay parameterized in `core_bundle.json` / `LandingHandoff`. |
| **I6 (Codsworth `E` Talk & Thruster)** | `09000970` invisible collision proxy (`codsworth_talk_proxy.nif`), zero `Skin_MiniBotA_Base`, `SayOnce` greeting gate `0x97C`, `Min00` keeper yield during `S3` walk. | **Later plug-in:** Robot race templates + invisible collision-proxy volumes apply per NPC race/actor in `Mission` data, with `0x97C`-style greeting gates reusable across companion/quest NPCs. |
| **I7 / I8 (Minors & `--textures-archive`)** | `VaultAmmoCount=48`, `WTHS 0x001034AB` clear arrival weather, `"Use preset look"`, `SetDeathReloadPlainBlackCover`, casefold + DDS pixel-payload `--textures-archive` verification. | **Later plug-in:** Per-game `game_start_config.json` rows supply arrival weather (`WTHS`), fallback suit (`ARMO`), and ammo counts across FO4/FO3/FNV bundles. |
| **H1–H6 / S2** | Arsenal `25/25`, zero `SCEN` VMAD bindings, `load_doors.json` anchors, `settlement_rules.json` bench rule, `S2` empty-slot fallback. | **Later plug-in:** FO3/NV weapons, scene IDs, load doors, W5/W6 rules, and `#855` creature races plug in as data rows. |

---

## Claude's Additions (5 Rows — Round 15 Wave B Status)

| Addition | PR / Track | Integration Status in `candidate-2h-3` | VIDEO / Still |
|---|---|---|---|
| **Robot animations & Codsworth** | `#854` (`claude/robot-anim` -> `gemini/r15-wb-854-handy`, credited to `#854` & Claude (PC)) | **ENABLED (`H3`)**: `--codsworth-handy E2 --codsworth-assets codsworth_handy_chrome` (no `--codsworth-race-framing`); FO4 `_s.dds` converted to BC4 `_rough.dds` + `HandyLens.BGEM` | Daylight **still** beside FO4 ref + **VIDEO** `sanctuary-codsworth-h3` (idle, turn, talk camera). |
| **Creature animations** | `#855` (`claude/creature-anim`) | **`not applicable` (default OFF)**: `09000B8C = 0.0`; `S2` & `S3` use `creature_slot=empty` fallback (S2 roaches marker table seam ready). | `v111-corridor` (`1 fps` PASS if empty-slot fallback advances cleanly). |
| **Human animations** | `#856` (`claude/human-anim`) | **`not applicable` (default OFF)**: `--fo4-human-anims 0` (`09000B8E=0.0`); Preston/raiders wear FO4 outfits; 4 Sanctuary settlers wear `Settler Clothes` stand-in (`09000BE4`/`09000BE5`, zero spacesuits). | `museum-preston-to-first-settlement` (`>= 5 s` 3F room check, zero spacesuits). |
| **Gun moving parts proof** | `#32` / P6b Arsenal | **BUILT IN (`H1`/`H4`)**: `FO4SFCoreValues.esm` built with `--fo4-arsenal 1 --fo4-10mm 1` (`25/25` WEAPs + P6b meshes/geometries/materials/textures folded). | `v111-armory-lift` & `concord-musket-pickups` (`>= 4 s` `10mm Pistol` / `Laser Musket` render & reload). |
| **Gun sounds** | `#32` (`sound-bank-study`) | **ON HOLD / Starfield `SNDR` stand-ins**: zero `.afx`/WAUD banks touched. | **`audio: not judged`** across captures. |
