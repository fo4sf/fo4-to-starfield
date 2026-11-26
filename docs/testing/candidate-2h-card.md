# Session Card — `candidate-2h-3`: Round 15 Wave B (`H1`–`H6` + `fix7b` + `#854` Handy Chrome + `#867` Workshop + `#868` Decisions)

> **Build Profile & Verdict (`26 Nov 2026`):** **`OFFLINE STAGED — UNPROVEN IN GAME`** (`NEW GAME needed`; clean start from Vault 111 required — do NOT load pre-`candidate-2h-3` saves).
>
> - **Branch & Stack Integrated (`H1`–`H6`):** `gemini/round11-s2-s6-2h` (`#853`) rebased/merged onto **`#852` (`da4e7902` `fix7b`: `G1`–`G13`, `B1`–`B8` PASS)**, **`#868` (`origin/gemini/r14-decisions` `73af2b29`)**, **`#867` (`origin/gemini/r14-workshop` `de001cef`)**, and **`#854` (`origin/claude/robot-anim` `abfa189c`, Claude (PC) -> `gemini/r15-wb-854-handy`)**.
> - **Key Wave B Fixes Included (`H1`–`H6`):**
>   - **`H1` (`--fo4-arsenal 1` + Looks Parity):** Builds `FO4SFCoreValues.esm` with `--fo4-arsenal 1` (`25/25` WEAP set verified by `check-bundle`), folds P6b weapon meshes/geometries/materials/textures + `fusioncore.nif`, stages with `D:\Modding\staging\c5_actor_looks_r14_fix6`, updates Concord street fight row **`3b`** to Wave A bar, keeps **`2a`** and **`4a2`** as **`REACHABLE`** cold reloads.
>   - **`H2` (Scene Bindings & Stage-35 Unblock):** Removes Scene VMAD bindings `S3Stage50Scene` (`0xB9A`), `S6PrestonRoomScene` (`0xBC9`), `S6SturgesRoomScene` (`0xBD0`); Mission check refuses any `SCEN`-targeting VMAD property; extends fix6 Task 0c resolvers (`FO4SF_Codsworth01Quest.psc` / `FO4SF_Min00Quest.psc`) with dynamic `OnBegin`/`OnEnd` registration and `AdvanceS6PrestonGroupTalk()` fallback (`s6 preston fallback stage=40 reason=no_scene`) so `EnableS6ToS9Full=1` advances `35 -> 40 -> 200 -> FO4SF_Sanctuary01 (0x817)`.
>   - **`H3` (`#854` Codsworth Mr. Handy Skeleton & Chrome):** Built with `--codsworth-handy <E2-bundle> --codsworth-assets <codsworth_handy_chrome> --actor-looks-assets <c5_actor_looks_r14_fix6>` (NO `--codsworth-race-framing`; mutually refused). Extracts & converts all `5` FO4 `Handy*_s.DDS` specular/gloss maps from `Fallout4 - Textures1.ba2` into real BC4 `_rough.dds` textures paired with `Metalness=0.85` + adds `HandyLens.BGEM` material; `DirectAt` (`z=0.984447 m`) sits on `COM`.
>   - **`H4` (One `10mm` Seam):** `src/fo4sf/core/game_start_config.json` `games.fo4.vault_pistol` drives `0A000820` (`FO4_10mmPistol` `06000899`) + `0A000821` (`FO4_Ammo10mm` `06000898`, `"10mm Round"`) and fills `VaultPistolBase`/`VaultAmmoBase`; `FO4SF_NewGameQuest.psc` uses ONLY those properties (no `.45 CALIBER` / `0x000822` / arithmetic hard-codes).
>   - **`H5` (Museum Door Seam):** `FO4SF_ConfirmedLoadDoor.psc` requires `LoadDoorController` (no `0xBDE`/`0x821` fallbacks); `FO4SF_LoadDoorQuest.psc` (`09000BDE`) & builder read anchors from `src/fo4sf/core/load_doors.json` `games.fo4` and log properties directly.
>   - **`H6` (Sanctuary Workshop Wiring):** `FO4SFWorkshop.esm` (`0x000800` + `ACTI 0x000849`), `FO4SF_WorkshopCoreQuest.psc`, and `FO4SF_Sanctuary01Quest.psc` read `SanctuaryWorkbenchPlugin` (`FO4TerrainCore.esm`), `SanctuaryWorkbenchRefId` (`0x005C50`), and `SanctuaryBuildRadiusM` (`250.0`) dynamically from `settlement_rules.json` (hardcoded `0x005C50` and `clean_swap_bench_runtime_hex` dropped; W5/W6 attack/population rows marked **`NOT WIRED`**).
> - **P3 Scope Note:** P3 (`0` `M`/`N`/`V`) applies to **typed interactive** console lines and **batch filenames**; `getglobalvalue`, `moveto`, and `additem` stay inside `bat/h2*.txt`.
> - **Logging Preflight (`G3`, Required Before Running):** Confirm `StarfieldCustom.ini` sets all `3` `[Papyrus]` keys (`bEnableLogging=1`, `bEnableTrace=1`, `bLoadDebugInformation=1`); wait `10 s` after New Game launch and verify `Documents/My Games/Starfield/Logs/Script/User/fo4sf_newgame.0.log` is non-empty before proceeding.

---

## 1. Staged Component Scope & Check-Bundle Gates

| Component / Artifact | Contract & Changes in `candidate-2h-3` | Notes |
|---|---|---|
| `<cand2h-port-dir>/FO4Port.*` | Lossless Slot 1 (`L3` merged `NAVI 0x00000FF1` + Museum cells + Vault 111 surface cog `0x025128` at `(-2467.78, -1406.93, 127.85)` `G4`) | Passed `--port <cand2h-port-dir>/FO4Port.esm` |
| `FO4SFCoreValues.esm` | `--fo4-arsenal 1 --fo4-10mm 1` (`25/25` arsenal WEAPs `0x000899..0x0008D6`, P6b ammo/items, `--test-mode 0` in `player`) | Verified by `check-bundle --require-arsenal` |
| `FO4SFMission.esm` | Zero `SCEN` VMAD properties (`H2`); `FO4SF_HandyRace` (`09000818`) + `0900081A` (`H3`); `load_doors.json` anchors (`H5`); dynamic `FO4SFWorkshop` bench rule (`H6`); `WRLD == 0` | P6b weapon/ammo/item assets folded via `--arsenal-assets` |
| `FO4SFNewGame.esm` | `games.fo4.vault_pistol` bound (`VaultPistolBase`=`0x899`, `VaultAmmoBase`=`0x898`), stage `15` pod exit (`G6`), pickup autosave (`G12a`), `pool==0` lift gate (`G12c`) | Uses `FO4SFCoreValues.esm` |
| `FO4SFWorkshop.esm` | `FO4SF_WorkshopCoreQuest` (`0x800`) + `ACTI 0x849` bound from `settlement_rules.json` (`FO4TerrainCore.esm`, `0x005C50`, `250.0 m`); W5/W6 `"NOT WIRED"` | `#867` clean |
| `FO4SFMapMarkers` (`map-markers/`) | Verified `--require-map-markers` (`DiscoverSingleMarkerSilent`; zero arrival discovery banners `G10`) | Installed via `map_markers_install.py` |
| `FO4SFPipboyMenu.dll` (`sfse_sidecar`) | Merged Wave B DLL (`Arm=1` wrist raise `G12b`, `lift_menu.h`, `hud_quest_label.h` = `QUEST`, `pipboy_screen_source.h`, `Translate_en.txt` Quest strings `G12d`) | Tested via `sidecar-install` |

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

# 3. Install 13-plugin player bundle (--pack --textures-archive) + SFSE sidecar + map-markers + bat/h2*.txt
python scripts/game/exp_install.py install --exp-dir <cand2h-player-bundle> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack --textures-archive
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2h-player-bundle> --starfield <starfield-dir>
python scripts/game/map_markers_install.py install --dir <cand2h-player-bundle>/map-markers --starfield <starfield-dir>
cp -f <cand2h-player-bundle>/bat/*.txt <starfield-dir>/
```

### Reversible Rollback (Game Closed)

```bash
rm -f <starfield-dir>/h2st.txt <starfield-dir>/h2h2.txt <starfield-dir>/h2h3.txt <starfield-dir>/h2h4.txt <starfield-dir>/h2f.txt <starfield-dir>/h2b.txt <starfield-dir>/h2k.txt <starfield-dir>/h2p.txt <starfield-dir>/h2r.txt
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/map_markers_install.py uninstall --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
cp -f <starfield-dir>/Data/FO4Port_pre2h_backup/FO4Port.esm "<starfield-dir>/Data/FO4Port_pre2h_backup/FO4Port - Main.ba2" "<starfield-dir>/Data/FO4Port_pre2h_backup/FO4Port - Textures.ba2" <starfield-dir>/Data/
rm -rf <starfield-dir>/Data/FO4Port_pre2h_backup
```

---

## 3. Card 2h-1 (`S1` Wake, `S2` Roaches, `H4` One 10mm Armory Walk, Pip-Boy & Lift — `REACHABLE`)

| Step | Action | Expected In-Game & Log Result | Status | VIDEO / Media |
|---|---|---|---|---|
| **1a. New Game (`NEW GAME needed`)** | Launch SFSE -> **New Game -> Vault 111 / Story** (`10 s` `fo4sf_newgame.0.log` preflight). | Cryo pod wakes clearly at stage `15`/`20` (`vault_death_recovery` manual save locked in Vault), HUD watch hidden (`HideStarfieldWatch=1`), Quest label `QUEST` (`G9`/`G12d`). | `REACHABLE` | Take `v111-pod`: `>= 4 s` cryo wake; **`audio: not judged`**. |
| **1b. `S2` Vault 111 Roaches (`09000B90`, `L2`)** | Walk Vault 111 corridor toward Overseer/lift (`09000B8D=1`, `09000B8C=0` empty slot). | `s2 vault_roaches creature_slot=empty fallback=stage_gate` -> completes with `stage=100` *(5 markers visited <= 12 m)* or `stopped reason=left_vault_stage_200`. | `REACHABLE` | Take `v111-corridor`: `>= 6 s` hall traversal. |
| **1c. `H4` Armory Walk (`L10`), `10mm Pistol` + `10mm Round`, `F7` Wrist Pip-Boy & Lift (`G12a`/`b`/`c`)** | Walk `L10` armory leg; **press `E`** on Armory desk pistol (`0A000820`) & ammo box (`0A000821`), Pip-Boy (`0A00080F` -> triggers `pipboy_pickup` autosave), and Vault console (`0A000819`); spend all S.P.E.C.I.A.L. points (`pool == 0` required to unlock Ride); ride rising cog to hilltop; press **`F7`** (`Arm=1` raise -> 2D menu -> lower). | `pistol picked` names **`FO4SFCoreValues.esm` (`FO4_10mmPistol` `06000899`)**; weapon & ammo display Fallout names (**`10mm Pistol`** + **`10mm Round`**, zero `.45 CALIBER` / `.45 ACP`); `12`-round magazine loaded or fueled by `0A000821` (`count=48` `FO4_Ammo10mm` `06000898`); reload works cleanly; `vault_death_recovery=autosave stage=<st> after=pipboy_pickup`; hilltop daylight at `z ~128 m`, zero Red Rocket banner (`G10`). | `REACHABLE` | Take `v111-armory-lift`: `>= 10 s` `10mm` equip/reload + `Arm=1` wrist raise + smooth cog rise. |

---

## 4. Card 2h-2 (`2a` Cold Reload, `H3` `#854` Codsworth Mr. Handy & Chrome, `S3` Walk, `H6` Sanctuary Bench — `REACHABLE` / `TEST-STATION`)

| Step | Action | Expected In-Game & Log Result | Status | VIDEO / Still |
|---|---|---|---|---|
| **2a. Cold Reload #1 (`Throwaway_2h_Surface`)** | Save on Vault 111 hilltop -> `Quit to Desktop` -> relaunch SFSE -> load save. | `reload mission stage=0 relocate_fails=0`, `codsworth01 reload stage=10 choices=0`, `FO4SF_LOADDOOR reload_ready`, daylight restored, zero spurious return-lift popup. | `REACHABLE` | Take `surface-cold-reload`: `>= 5 s` post-load hilltop view. |
| **2b. `H3` `#854` Codsworth Mr. Handy Chrome Still + Walk & `H2` `S3` Stage-50 (`09000B9A`)** | Walk down to Sanctuary Hills (`09000811`). Take a **still in daylight beside an FO4 reference**; observe idle, turn, **walk beside Codsworth** from House 01 (`-2313.44, -1372.02`) to House 02 (`-2296.17, -1424.97`); **press `E`** at initial talk, Stage `50` (`09000B9A`), and post-`100` goodbye. *(NO `bat h2h1`.)* | Codsworth hovers on `FO4SF_HandyRace` (`09000818`) + `FO4SF_CodsworthBodyPartData` (`0900081A`) with brushed-steel `_s.dds`-converted `_rough.dds` specular/matte contrast + `HandyLens.BGEM` (`E2` mesh note below); `scene resolved via=file id=0x000B9A` -> `codsworth01 stage 50 scene started` (`0` `fallback=messagebox`) -> `codsworth01 stage 100 concord_pointed=true`, `min00 given by=codsworth`. | `TEST-STATION` (still + video judged by owner) | **Daylight Still** (beside FO4 reference) + **VIDEO** `sanctuary-codsworth-h3`: `>= 15 s` showing **idle, a turn, and the talk camera** + House `01->02` walk (`DirectAt` on `COM`). |
| **2c. `H6` Sanctuary Bench After First Settlement (`04005C50`)** | After *First Settlement* (`FO4SF_Sanctuary01` `09000817`) starts (`Row 5a`), press **`E`** on the Sanctuary workbench (`04005C50`) and **build one object**. | Bench plugin (`FO4TerrainCore.esm`), ID (`0x005C50` / `23632`), and radius (`250.0 m`) are read dynamically from `FO4SFWorkshop.esm` `0x000800` (`sanctuary01 bench_rule ...`); non-blank footer (zero `"."`); object places cleanly -> `min01 bench activated -> stage 100`. (`clean_swap_bench_runtime_hex` dropped; W5/W6 `"NOT WIRED"`.) | `REACHABLE` | Take `sanctuary-bench-h6`: `>= 6 s` opening bench & building `1` object after `FO4SF_Sanctuary01` starts. |

---

## 5. Card 2h-3 (`S4` Concord Exterior `z ~88`, `H1` Updated Fight Bar `3b`, Preston Balcony & Musket — `REACHABLE`)

| Step | Action | Expected In-Game & Log Result | Status | VIDEO |
|---|---|---|---|---|
| **3a. Hop Chain (`< 200 m`/axis) & Concord Exterior `z ~88 m`** | Walk or run `bat h2h2` -> `3 s` -> `bat h2h3` -> `3 s` -> `bat h2h4`. | Zero skips `>= 200 m`/axis; Concord buildings & Museum facade render solidly at **`z ~88.3..90.0 m`**. | `REACHABLE` | Take `concord-exterior-z88`: `>= 5 s` facade pan. |
| **3b. Updated Concord Street Fight (`H1` / `G11`, God Mode OFF)** | With **god mode OFF**, let Concord street raiders (`09000803..09000805`) fire while standing idle `10 s`, then use cover & shooting to clear street raiders and inspect fallen raiders up close (`D2`). | **PASS:** idle HP drops **`>= 20` within `10 s` while staying alive at `10 s`**, and cover + shooting clears cleanly to **`stage 30` (S4 Museum objective `60`) within `60` rounds**; raiders wear FO4 raider outfits (`0` spacesuits); **FAIL:** idle death in `< 10 s`, or out of ammo. | `REACHABLE` | Take `concord-fight-g11`: `>= 15 s` `10 s` idle HP check + cover clear to `stage 30`. |
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
FO4SF_NEWGAME rt=<rt> vault_death_recovery=autosave stage=<st> after=pipboy_pickup
FO4SF_NEWGAME rt=<rt> pistol picked item=<item> count=1 equipped=True base=<form>
FO4SF_NEWGAME rt=<rt> pistol ammo picked item=<item> count=<cnt> base=<form>
FO4SF_LOADDOOR reload_ready cell=<cell> interior=<true|false>
FO4SF_LOADDOOR quest_init cell=<cell> exit_plugin=<plugin> exit_anchor=<id> secondary_plugin=<sec_plugin> secondary_anchor=<sec_id>
FO4SF_LOADDOOR failed tag=<tag> dir=<dir> attempts=0 reason=controller_unbound
FO4SF_MISSION rt=<rt> s2 vault_roaches creature_slot=empty fallback=stage_gate
FO4SF_MISSION rt=<rt> codsworth01 s3 creature_slot=empty fallback=arrival_advance
FO4SF_MISSION rt=<rt> scene resolved via=file id=0x000B9A scene=<ref>
FO4SF_MISSION rt=<rt> scene missing id=0x000BC9
FO4SF_MISSION rt=<rt> codsworth01 stage 50 scene started
FO4SF_MISSION rt=<rt> codsworth01 stage 100 concord_pointed=true
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

## 9. Later Plug-In Seams (`H1`–`H6` + `S2` Roaches)

| Item | 0.1 Behaviour | Later plug-in |
|---|---|---|
| **H1 / Row 3b (Arsenal & Concord Fight)** | `--fo4-arsenal 1` WEAPs (`check-bundle` verified) + active Concord street fight to `stage 30`. | **Later plug-in:** weapon rows stay in `core_values.json`, so FO3/NV guns are added as rows (`#853` P6b weapons + `L7`–`L9` plug onto `0900097B`/`0900097A` and `Min00` `stage 30`). |
| **H2 (Scene Bindings)** | Zero `SCEN` VMAD properties (`S3Stage50Scene`, `S6PrestonRoomScene`, `S6SturgesRoomScene` resolved via Task 0c + `AdvanceS6PrestonGroupTalk` fallback). | **Later plug-in:** scene ids stay in the per-game mission builder, never in shared scripts. |
| **H3 (`#854` Codsworth Handy & Chrome)** | `FO4SF_HandyRace` (`09000818`) + `0900081A` + FO4 `_s.dds` chrome `_rough.dds` + `HandyLens.BGEM` (`DirectAt` on `COM`; `E2` omits `ModTorsoHandyEye:2` until rebuilt with `lens_material`). | **Later plug-in:** a race template plugin per NPC, so Protectron, Mr. Gutsy, Assaultron, Eyebot and the FO3/NV robots plug in as data. |
| **H4 (One `10mm`)** | `games.fo4.vault_pistol` in `game_start_config.json` drives `0x820`/`0x821` + `VaultPistolBase`/`VaultAmmoBase` (`0x899`/`0x898`). | **Later plug-in:** FO3/NV start weapons are rows. |
| **H5 (Museum Load Doors)** | `LoadDoorController` required (no `0xBDE`/`0x821` fallbacks); `FO4SF_LoadDoorQuest` anchors filled from `src/fo4sf/core/load_doors.json`. | **Later plug-in:** FO3/NV doors are rows. |
| **H6 (Sanctuary Workshop)** | `FO4SFWorkshop.esm` (`0x800`/`0x849`) + `FO4SF_Sanctuary01Quest` read bench plugin/ID/radius from `settlement_rules.json`; W5/W6 attack/population rows marked `"NOT WIRED"`. | **Later plug-in:** W5/W6 rules are added as rows, and their code reads them. |
| **`S2` Roaches (`L2`)** | `FO4SF_S2CreatureSlotReady (09000B8C) = 0.0` routes corridor walk cleanly via `09000B91..09000B95` markers. | **Later plug-in:** creature spawns and patrol markers read a per-game marker table (linking `#855` creature races onto `09000B91..09000B95` when enabled). |

---

## Claude's Additions (5 Rows — Round 15 Wave B Status)

| Addition | PR / Track | Integration Status in `candidate-2h-3` | VIDEO / Still |
|---|---|---|---|
| **Robot animations & Codsworth** | `#854` (`claude/robot-anim` -> `gemini/r15-wb-854-handy`, credited to `#854` & Claude (PC)) | **ENABLED (`H3`)**: `--codsworth-handy E2 --codsworth-assets codsworth_handy_chrome` (no `--codsworth-race-framing`); FO4 `_s.dds` converted to BC4 `_rough.dds` + `HandyLens.BGEM` | Daylight **still** beside FO4 ref + **VIDEO** `sanctuary-codsworth-h3` (idle, turn, talk camera). |
| **Creature animations** | `#855` (`claude/creature-anim`) | **`not applicable` (default OFF)**: `09000B8C = 0.0`; `S2` & `S3` use `creature_slot=empty` fallback (S2 roaches marker table seam ready). | `v111-corridor` (`1 fps` PASS if empty-slot fallback advances cleanly). |
| **Human animations** | `#856` (`claude/human-anim`) | **`not applicable` (default OFF)**: `--fo4-human-anims 0` (`09000B8E=0.0`); Preston/raiders wear FO4 outfits; 4 Sanctuary settlers wear `Settler Clothes` stand-in (`09000BE4`/`09000BE5`, zero spacesuits). | `museum-preston-to-first-settlement` (`>= 5 s` 3F room check, zero spacesuits). |
| **Gun moving parts proof** | `#32` / P6b Arsenal | **BUILT IN (`H1`/`H4`)**: `FO4SFCoreValues.esm` built with `--fo4-arsenal 1 --fo4-10mm 1` (`25/25` WEAPs + P6b meshes/geometries/materials/textures folded). | `v111-armory-lift` & `concord-musket-pickups` (`>= 4 s` `10mm Pistol` / `Laser Musket` render & reload). |
| **Gun sounds** | `#32` (`sound-bank-study`) | **ON HOLD / Starfield `SNDR` stand-ins**: zero `.afx`/WAUD banks touched. | **`audio: not judged`** across captures. |
