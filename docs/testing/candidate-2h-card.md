# Session Card — `candidate-2h`: Round 12 Task 1 (`P1 v2` Fixes + Vault Roaches `S2` + Codsworth Bloatflies/Stage-50 `S3` + Concord/Museum `S4`–`S6` + P6 Arsenal Contract)

> **Build Profile & Verdict (`23 Nov 2026`):** **`OFFLINE STAGED — UNPROVEN IN GAME`** (`NEW GAME needed`; clean start from Vault 111 required — do NOT load a `2g`/`2g-fix2` save created before `FO4SF_R11FullMission` / `0x00EFAB` Slot 1 `FO4Port.esm`).
>
> - **Branch & Slot 1 `FO4Port.esm` Handoff:** `gemini/r12-t1-s2s6-slice` (`OFFLINE ONLY — UNPROVEN IN GAME`). Holds **Slot 1** lossless museum extension (`NextObjectID=0x00EFAB`, local FormIDs strictly `0x00E200..0x00EFAA`; **Slot 2 (`0x00EFAB+`) handed off to `@r12-t6-prewar`**).
> - **Optional Flags Held OFF by Default (`#854`/`#855`/`#856` unmerged):** `--r11-full-mission 1`, `--task1b-vault-recovery 1`, **`--fo4-human-anims 0`** (`09000B8E=0.0`), **`creature_slot=empty`** (`09000B8C=0.0`), **`--codsworth-race-framing 0`**, `--codsworth-handy` OFF (`S1` Pre-War belongs to Task 6), `09000979` `FO4SF_MissionTalkUseMessageBox = 0.0` (MessageBox fallback unreachable in live dialogue), `0 WRLD` overrides in `FO4SFMission.esm`.
> - **Single-Archive `4.000 GiB` Asset Scope (`R15` Honesty Disclosure):** Because `make_core_bundle.py` enforces `< 4.000 GiB` single-`Main.ba2` packing (`docs/ai/test-queue.md`), `candidate-2h` folds **all `367` non-texture weapon/ammo/prop files** (`geometries/`, `materials/`, `meshes/` for Rows `1`–`20`) plus all **`129` `.dds` textures** (`139.40 MiB`) for **Rows `1`–`5`** (`baton`, `10mm`, `lasermusket`, `minigun`, `pipepistol`, `piperifle`), **all `13` ammos**, and **all `4` core items** (`stimpak`, `caps`, `bobbypin`, `goopile`). **Rows `6`–`20` `.dds` textures are omitted from `candidate-2h`'s single `Main.ba2`** to stay under `4.000 GiB` (run `<r11-p6-dir>` standalone for full Rows `6`–`20` textures).
> - **`2g-fix2` (`#852`) Inheritance Note:** `FO4SFPipboyMenu.dll` (`7d5ba49c`) is reused binary-identical; `#762` async `Scene.OnEnd` consumption and full `SceneOpenCheckSeconds`/`PrestonSceneCheckSeconds` window guards are active across S3 Stage-50 (`09000B9A`) and S6 Preston/Sturges room scenes (`09000BC9`, `09000BD0`).
> - **Placeholders:** `<cand2h-player-bundle>`, `<cand2h-test-bundle>`, `<cand2h-port-dir>`, `<mapmarkers-stage-dir>`, `<starfield-dir>` (`>= 60.0 GiB` free on target drive; zero edits to `Starfield/Data` outside explicit install/uninstall steps).

---

## 1. Staged File Inventory & SHA-256 Receipts (`OFFLINE VERIFIED`)

| Artifact / Stage Component | Bytes | SHA-256 | Notes / Contract |
|---|---:|---|---|
| `<cand2h-port-dir>/FO4Port.esm` | `4,612,735` | `8163ca9a7187bd07fdd09f20ad7c16d511577f91d91c858ed28ec0fc434fef39` | Lossless Slot 1 (`0` diffs on `55,071` baseline records; `3,500` museum/prewar records `0x0100E200..0x0100EFAA`, `NextObjectID=0x00EFAB`, `0` `WRLD`/`PNDT`) |
| `<cand2h-port-dir>/FO4Port - Main.ba2` | `117,755,711` | `064c762499a1cc975df81da2c12ea3a20aec5f84cae0c89f4d9cdac12d094c7e` | `BTDX` v2 `GNRL` (`17,023` entries; museum + prewar mesh/mat delta; `nlink=1`) |
| `<cand2h-port-dir>/FO4Port - Textures.ba2` | `2,289,478,621` | `f4664dd0a4fb49a3adb17440596bbb936b0ffa47516024be9fff07c7b1a69a48` | `BTDX` v2 `DX10` (`4,711` entries; museum texture delta; `nlink=1`) |
| `FO4SFCoreValues.esm` (`player`, `--test-mode 0`) | `76,995` | `bfe6d99a75230b1dbb795c5cd0fcdb30a3b4ffb26e03bc667a73e59570b505d9` | Byte-identical to cleared `r11-p6-arsenal` / `1b93113b` (`0x000860=0.0`, P6 arsenal + Row 5 Pipe Pistol `0x0008A2` / Rifle `0x0008A3` / `.38` `0x0008A1` / Stimpak `0x000851` / Caps `0x0008A4` / Bobby Pin `0x0008A5`) |
| `FO4SFCoreValues.esm` (`test`, `--test-mode 1`) | `76,995` | `425aa3cca7299c560c9735753dee24b2bed8debd989fc5d035cb63210609b4be` | Same schema with `FO4SF_TestModeEnabled (0x000860) = 1.0` |
| `FO4SFMission.esm` (`02b-mission`) | `103,759` | `9b69cc599f017a8a273bdb97c055819b6377c347669c38b7aa21d15e9ccc5c1e` | `14 QUST`, `25 NPC_`, `0 WRLD` (`0x000979=0.0`, `0x000B8B=1.0`, `0x000B8C=0.0`, `0x000B8D=1.0`, `0x000B8E=0.0`), `15` `.pex` scripts, `88` assets (`35` `.wem` + Codsworth + C5 outfits) |
| `FO4SFNewGame.esm` (`03-newgame`, `player`) | `12,688` | `0163600cbbe974a0344a858ddd483472a59e90b079632b394bac535cbd9d50f2` | Built against `<cand2h-port-dir>/FO4Port.esm`; `fade_hold=false`, `vault anchor 001338 persistent` |
| `FO4SFNewGame.esm` (`03-newgame-fadehold`, `test`) | `12,688` | `5c9edb843ced9eeaf505f8e0fd9255122d6bbbe4248308ccedbb36dbcc9a9e65` | Built against `<cand2h-port-dir>/FO4Port.esm`; `fade_hold=true` |
| `FO4SFVaultGearDoor.esm` (`01-cog-door`) | `597` | `7aada8bafa027bfd158c63e0728e10e7239401dde57429ba601b7b96a2ea8533` | Built against `<cand2h-port-dir>/FO4Port.esm`; zero probe scripts |
| `FO4SFExitLift.esm` (`02-exit-lift`) | `590` | `34d0db71d1116742d5d644a7772e8f31e43019b72bab9d01c91eec308665d9d4` | Built against `<cand2h-port-dir>/FO4Port.esm`; `37` moving bodies, zero probe scripts |
| `FO4SFWorkshop.esm` (`06-workshop`) | `120,300` | `1b98ebc3eed1dd0decf4e66a2815a52ef8181141326ad8fdded0387f78082a82` | `HeaderFlag.Localized` + `Strings/FO4SFWorkshop_en.*` (`701`/`8`/`688` B) |
| `FO4SFPowerArmor.esm` (`player` / `test`) | `84,270` / `86,186` | `c3332aef3891f4cd647882e80da4f1c6238ba558b12d2c80c2fb32e5fd885c4c` / `d7f0fc494cca47c2cdf570b82368b6f7f4aca96b478aff179e230fed0a45e09d` | Unchanged from `candidate-2g-fix2`; owns `FO4SF_FusionCore (0x0A000809)` |
| `FO4SFPipboyMenu.dll` (`sfse_sidecar`) | `1,453,568` | `7d5ba49c0c6ab2aa8db24ab1bfb643839259d12404cc95afaa38e2f42201c9a8` | Tested DLL reused unchanged (`ShellBackdrop=1`, `ShellVitalsFill=1`, `SuppressDataMenu=0`, `TabOpensPipboy=0`) |

---

## 2. Install & Reversible Port Swap Commands (Game Closed)

- **`13`-Plugin `--profile player` Load Order (`Plugins.txt`):** `FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm` (with `<cand2h-port-dir>/FO4Port.*` backed up and swapped onto `<starfield-dir>/Data/FO4Port.*`).
- **`22`-Plugin Optional `--profile test` Load Order:** `FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFCoreCandidate.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm` (zero `FO4SFRouteLoot.esm` / `FO4SFBridge.esm`).

```bash
# 1. Verify player bundle + lossless FO4Port.esm before touching Starfield\Data
python scripts/core/make_core_bundle.py verify --bundle-dir <cand2h-player-bundle> --port <cand2h-port-dir>/FO4Port.esm

# 2. Reversible FO4Port.* backup (skip if <starfield-dir>\Data\FO4Port_pre2h_backup already holds original SHA-256) and swap
mkdir -p <starfield-dir>/Data/FO4Port_pre2h_backup
cp -n <starfield-dir>/Data/FO4Port.esm "<starfield-dir>/Data/FO4Port - Main.ba2" "<starfield-dir>/Data/FO4Port - Textures.ba2" <starfield-dir>/Data/FO4Port_pre2h_backup/
cp -f <cand2h-port-dir>/FO4Port.esm "<cand2h-port-dir>/FO4Port - Main.ba2" "<cand2h-port-dir>/FO4Port - Textures.ba2" <starfield-dir>/Data/

# 3. Install 13-plugin player bundle + SFSE sidecar + map markers
python scripts/game/exp_install.py install --exp-dir <cand2h-player-bundle> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2h-player-bundle> --starfield <starfield-dir>
python scripts/game/map_markers_install.py install --stage <mapmarkers-stage-dir> --starfield <starfield-dir>
```

### Exact Undo / Rollback Command (Game Closed — Restores Original `FO4Port.*` + Clean `Starfield/Data`)

```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/map_markers_install.py uninstall --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
cp -f <starfield-dir>/Data/FO4Port_pre2h_backup/FO4Port.esm "<starfield-dir>/Data/FO4Port_pre2h_backup/FO4Port - Main.ba2" "<starfield-dir>/Data/FO4Port_pre2h_backup/FO4Port - Textures.ba2" <starfield-dir>/Data/
rm -rf <starfield-dir>/Data/FO4Port_pre2h_backup
```

---

## 3. Card 2h-1 (`S1` Pre-Flight, `1b` Vault Death Recovery & `S2` Vault 111 Roaches — `OWNER / TEST-STATION`)

| Step | Action | Expected In-Game & Log Result | Status | VIDEO |
|---|---|---|---|---|
| **1a. New Game (`NEW GAME needed`)** | Launch SFSE -> **New Game -> Vault 111 / Story**. | Cryo pod wake -> `FO4SF_NEWGAME rt=<rt> stage 20 by=Trigger`; `vault_death_recovery=autosave stage=20`. | Pending | `Pending` |
| **1b. `S2` Vault 111 Roaches (`09000B90`)** | Walk Vault 111 stages `10..40` toward Overseer/lift. Verify `09000B8D=1` (`Task1b`) gates spawn while `creature_slot=empty` (`09000B8C=0`) cleanly logs stage gates `09000B91..09000B95`. | `s2 vault_roaches stage 10 armed`, `s2 vault_roaches creature_slot=empty fallback=stage_gate`, `s2 vault_roaches complete creature_slot=empty stage=100` (if `creature-slots.json` populated: `5` `LvlRadRoachAmbush` kills -> `stage=100`). **Test 1 death in Vault 111 (`< stage 200`):** confirms `vault_death_recovery=reload`. | Pending | `Pending` |
| **1c. Pistol (`10mm`), Pip-Boy & Lift** | Armory cage `0A000820` auto-equips (`pistol picked ... equipped=True base=...`), Pip-Boy (`0A00080F`), cog door (`stage 30`), lift -> hilltop `stage 200`. | Clean hilltop in daylight; `06000865=1.0`, `09000B8B=1.0`, `09000816=10`. | Pending | `Pending` |

---

## 4. Card 2h-2 (`S3` Codsworth Bloatflies & Stage-50 Scene + Cold Reloads — `TEST-STATION`)

| Step | Action | Expected In-Game & Log Result | Status | VIDEO |
|---|---|---|---|---|
| **2a. Cold Reload #1 (`Throwaway_2h_Surface`)** | Save on Vault 111 hilltop -> `Quit to Desktop` -> relaunch SFSE -> load save. | `reload mission stage=0 relocate_fails=0`, `codsworth01 reload stage=10 choices=0`, daylight restored, zero spurious hilltop return-lift popup. | Pending | `Pending` |
| **2b. `S3` Codsworth House 01 -> House 02 (`09000816`)** | Walk (or `bat h2h1`) to Sanctuary Hills (`(-2346.71, -1406.16, 111.73)` m). Press **`E`** on Codsworth (`09000811`): advance `20 -> 30` (House 01 `09000B98` `(-2313.44, -1372.02, 112.66)`) `-> 34 -> 36` (House 02 `09000B99` `(-2296.17, -1424.97, 111.77)`) `-> 40 -> 50 -> 100`. | With `09000B8C=0`: `codsworth01 s3 creature_slot=empty fallback=arrival_advance`, `codsworth01 house1_cleared dead=0/0 stage=34`, `codsworth01 house2_cleared dead=0/0 stage=40`; stage `50` starts `FO4SF_S3_Stage50Scene` (`09000B9A`) cleanly -> picks Concord lead (`codsworth01 stage 100 concord_pointed=true`, `min00 given by=codsworth`). | Pending | `Pending` |

---

## 5. Card 2h-3 (`S4` Concord Street Fight + Preston Balcony `0x0600089E` + Display Laser Musket & Fusion Cells — `TEST-STATION`)

| Step | Action | Expected In-Game & Log Result | Status | VIDEO |
|---|---|---|---|---|
| **3a. Hop Chain (`< 200 m` Every Step)** | Walk or run `bat h2h2` (`(-2210, -1520, 108.0)`, `<= 156 m`) -> wait `3 s` -> `bat h2h3` (`(-2120, -1615, 98.0)`, `<= 131 m`) -> wait `3 s` -> `bat h2h4` (`(-2015, -1700, 90.0)`, `<= 135 m`) -> Concord Museum front. | Zero fast-travel skips `>= 200 m`/axis; loaded Concord terrain `z ≈ 88.3..90.0 m`. | Pending | `Pending` |
| **3b. `S4` Concord Street & Display Musket** | Engage `3` Concord street raiders (`09000803..09000805` armed w/ pipe guns) with **god mode OFF**; observe Preston on 3F balcony (`09000B60`, `(-2010.51, -1697.71, 98.51)` m) firing `FO4_CompPrestonLaserMusket` (`0600089E`). Collect **Fallen Minuteman's display musket (`09000BA8`)** & **`3` Fusion Cell pickups (`09000BAA..09000BAC`)** outside door. | `s4 balcony preston_z=98.51 ext_raiders=3`, `s4 preston equipped comp_laser_musket=0x089E`, `s4 laser_musket granted cells=15` (real `FO4_LaserMusket` `0600089D` + `15` `FO4_AmmoFusionCell` `0600089B`, completes opt obj `70`), plus `+3x5` Fusion Cells (`pickup fusion_cell count=5 granted=true`). Zero Red Rocket / Dogmeat triggers. | Pending | `Pending` |

---

## 6. Card 2h-4 (`P1 v2` Fixes, `S5` Floor-by-Floor Museum + `A4.5` Pickups + Confirmed Doors — `TEST-STATION`)

| Step | Action | Expected In-Game & Log Result | Status | VIDEO |
|---|---|---|---|---|
| **4a. Front Door Entry (`FO4SF_ConfirmedLoadDoor` + `P1 v2` `F4` Fix)** | Face east (`90 deg`) at `(-2012.50, -1697.94, 88.70)` and press **`E`** on `FO4SF_S5_ExtFrontInRef` (`09000BB8`, `FO4Port_ExtFrontIn` `...0DEF`). Confirm removed/marked `xtel_extra` lobby trap (`F4`) does NOT misroute or bounce. | `FO4SF_LOADDOOR activate_begin tag=s5_front_in dir=in` -> `FO4SF_LOADDOOR confirmed tag=s5_front_in dir=in ... cell=<0100E2F4>` (`LTMP 0x0006BCF8` lighting lit cleanly). | Pending | `Pending` |
| **4b. `S5` 7 Raiders + `A4.5` Pickups -> `Min00 35`** | Fight `7` museum raiders floor-by-floor (`09000BBC..09000BC2`, matching FO4 `00018D6B, 0001D808, 0001CB6E, 0001E2E0, 0001D809, 0001E2E2, 0001E2E1`). Test Cold Reload #2 (`Throwaway_2h_MidMuseum`) mid-clear. Collect `2` Stimpaks (`09000BAE..09000BAF` -> `06000851`), Caps (`09000BB1` -> `060008A4`), Bobby Pin (`09000BB3` -> `060008A5`), Pipe Pistol/Rifle + `.38` (`09000BB5` -> `060008A2`/`060008A1`). | `pickup stimpak count=1 granted=true` (`x2`), `pickup caps ...`, `pickup bobbypin ...`, `pickup pipe_weapon granted=true ammo=true`. Killing all `7` raiders logs `s5 museum_cleared dead=7/7 stage=35 preston_door=unlocked` and unlocks `PrestonDoorREF` (`0100EFA9`). | Pending | `Pending` |

---

## 7. Card 2h-5 (`S6` 3F Room Scenes, Basement Gate `0x0100EDF0`, Fusion Core `0x0A000809` & `F9` Roof Exit — `TEST-STATION`)

| Step | Action | Expected In-Game & Log Result | Status | VIDEO |
|---|---|---|---|---|
| **5a. `S6` 3F Room (`Preston` `09000BC9` & `Sturges` `09000BD0` Scenes)** | Enter 3F room (`Preston`, `Sturges 09000A01`, `Mama Murphy 09000BC4`, `Marcy 09000BC6`, `Jun 09000BC8`; all `SF HumanRace`, non-spacesuit FO4 outfits, `09000B8E=0`). Press **`E`** on Preston (`09000802`), then Sturges (`09000A01`). | Zero spacesuits; `s6 preston room scene started` -> `s6 preston room dialogue menu opened`, `s6 sturges room dialogue menu opened` (zero `fallback=messagebox`; async `#762` retry guard clean) -> `s6 stage 40 preston_group talk`, advancing to unlock basement security gate. | Pending | `Pending` |
| **5b. Basement Gate (`0x0100EDF0`, `XLOC 25` + `XLKR`) & Fusion Core (`0x0A000809`)** | Descend to basement gate `0100EDF0` (`DOOR 000BA4B5`, Novice lock `25`). Unlock via terminal proxy `09000BD9` (`XLKR` link to `0100E35E` -> `0100EDF0`) **OR** pick with Bobby Pin (`060008A5`). Grab **`MQ102FusionCoreREF` (`09000BDB`)**. | `pickup basement_terminal unlocked=true`, `s6 basement_gate unlocked reason=...`, `s6 stage 45 basement_gate opened`, then `pickup fusion_core granted=true fid=2057` -> grants `FO4SF_FusionCore` (`0A000809`) -> `s6 stage 50 fusion_core picked obj=95 stop=put_fusion_core_in_pa` (**HARD STOP at `"Put the Fusion Core in the Power Armor"`** — Task 3 S7 starts after this!). | Pending | `Pending` |
| **5c. Roof Exit (`F9` Separate Refs `0x0100EFA9` vs `0x0100EFAA`)** | Exit onto 3F roof via `FO4SF_S5_IntRoofOutRef` (`09000BBA`) -> confirm `0100EFAA` exit landing is separate from `0100EFA9` roof entry activator (`F9`), `core_cell=true` on Concord roof, and delete throwaway saves. | `FO4SF_LOADDOOR confirmed tag=s5_roof_out dir=out ... core_cell=true ... pos=... heading=180.0`, zero infinite loading screen or `2.9 km` bounce. | Pending | `Pending` |

---

## 8. Console Inspection & `< 200 m` Hop Batch Blocks (`P3` Zero-`M`/`N`/`V` Enforced)

```console
help "Calls" 4 QUST
getstage 09000816
getstage 09000800
getstage 09000B90
getstage 09000817
sqs 09000800
sqs 09000816
bat h2st
bat h2h1
bat h2h2
bat h2h3
bat h2h4
bat h2f
bat h2r
```

```bat
; <starfield-dir>/h2st.txt — read-only globals & Slot 1 / S2-S6 state check (06=CoreValues, 09=Mission)
getglobalvalue 06000860
getglobalvalue 06000865
getglobalvalue 09000979
getglobalvalue 09000B8B
getglobalvalue 09000B8C
getglobalvalue 09000B8D
getglobalvalue 09000B8E
sqv 09000800
sqv 09000816
sqv 09000B90

; <starfield-dir>/h2h1.txt — < 140 m hop: Vault 111 hilltop (-2450,-1351,131) -> Sanctuary House 01 / Codsworth
player.setpos x -2313.44
player.setpos y -1372.02
player.setpos z 113.00

; <starfield-dir>/h2h2.txt — < 156 m hop: Sanctuary House 01 -> Red Rocket North
player.setpos x -2210.00
player.setpos y -1520.00
player.setpos z 108.00

; <starfield-dir>/h2h3.txt — < 131 m hop: Red Rocket North -> Red Rocket South
player.setpos x -2120.00
player.setpos y -1615.00
player.setpos z 98.00

; <starfield-dir>/h2h4.txt — < 135 m hop: Red Rocket South -> Concord Museum street
player.setpos x -2015.00
player.setpos y -1700.00
player.setpos z 90.00
player.setangle z 90

; <starfield-dir>/h2f.txt — direct interior Museum lobby (0x0100E2F4, ...0DEF proof)
coc FO4Port_ConcordMuseum01
player.setpos x 7.73
player.setpos y 0.91
player.setpos z -0.90
player.setangle z 270

; <starfield-dir>/h2b.txt — INTERIOR-ONLY (run only AFTER bat h2f inside Museum): jump to basement Novice gate (0x0100EDF0)
player.setpos x 11.40
player.setpos y 16.50
player.setpos z -5.30

; <starfield-dir>/h2k.txt — INTERIOR-ONLY (run only AFTER bat h2f inside Museum): jump to 3F room door (Preston 3F)
player.setpos x -3.80
player.setpos y 10.60
player.setpos z 10.20

; <starfield-dir>/h2r.txt — exterior roof vantage (short < 28 m step from h2h4, separate from roof entry 0x0100EFA9)
player.setpos x -2008.49
player.setpos y -1724.60
player.setpos z 97.82
player.setangle z 180
```

### Required PASS Log Lines (`fo4sf_newgame.0.log`, `fo4sf_mission.0.log`, `fo4sf_loaddoor.0.log`)

```log
FO4SF_NEWGAME rt=<rt> vault_death_recovery=<autosave|reload> stage=<st>
FO4SF_MISSION rt=<rt> s2 vault_roaches creature_slot=empty fallback=stage_gate
FO4SF_MISSION rt=<rt> s2 vault_roaches complete creature_slot=empty stage=100
FO4SF_MISSION rt=<rt> codsworth01 s3 creature_slot=empty fallback=arrival_advance
FO4SF_MISSION rt=<rt> codsworth01 house1_cleared dead=0/0 stage=34
FO4SF_MISSION rt=<rt> codsworth01 house2_cleared dead=0/0 stage=40
FO4SF_MISSION rt=<rt> codsworth01 stage 50 scene started
FO4SF_MISSION rt=<rt> codsworth01 stage 100 concord_pointed=true
FO4SF_MISSION rt=<rt> s4 balcony preston_z=<z> ext_raiders=3
FO4SF_MISSION rt=<rt> s4 preston equipped comp_laser_musket=0x089E
FO4SF_MISSION rt=<rt> s4 laser_musket granted cells=15
FO4SF_MISSION rt=<rt> pickup stimpak count=1 granted=true
FO4SF_MISSION rt=<rt> pickup pipe_weapon granted=true ammo=true
FO4SF_LOADDOOR confirmed tag=s5_front_in dir=in attempts=<n> core_cell=<true|false> cell=<cell> world=<world> pos=<pos> heading=<hdg>
FO4SF_MISSION rt=<rt> s5 museum_cleared dead=7/7 stage=35 preston_door=unlocked
FO4SF_MISSION rt=<rt> s6 preston room scene started
FO4SF_MISSION rt=<rt> s6 sturges room dialogue menu opened
FO4SF_MISSION rt=<rt> s6 stage 40 preston_group talk
FO4SF_MISSION rt=<rt> s6 basement_gate unlocked reason=<reason> pending_stage40=true
FO4SF_MISSION rt=<rt> s6 stage 45 basement_gate opened
FO4SF_MISSION rt=<rt> pickup fusion_core granted=true fid=2057
FO4SF_MISSION rt=<rt> s6 stage 50 fusion_core picked obj=95 stop=put_fusion_core_in_pa
FO4SF_LOADDOOR confirmed tag=s5_roof_out dir=out attempts=<n> core_cell=true cell=<cell> world=<world> pos=<pos> heading=180.0
```

### Negative / FAIL Conditions
- Any `2g-fix2` regression (`fallback=messagebox` anywhere, `stage 40 by=fallback`, `FO4SFMission.esm` `WRLD > 0`, non-`0x0006BCF8` museum/Vault 111 lighting), any `2.9 km` bounce or infinite loading screen on front/roof Museum doors, `xtel_extra` lobby door misrouting (`F4`), roof exit colliding with roof entry (`F9`), Novice lock missing on `0x0100EDF0`, missing display musket `+15` Fusion Cells or `0x0A000809` Fusion Core grant, or advancing past `"Put the Fusion Core in the Power Armor"`.

---

## Claude's Additions (5 Rows — 23 Nov In-Game Baseline)

| Addition | PR / Track | 23 Nov In-Game Status | Integration / Dependency in This Card | Guard / Note |
|---|---|---|---|---|
| **Robot animations & Codsworth** | `#854` (`claude/robot-anim`) | Partial pass: FO4 `.rig`/`.af`/`.afx` animations + Codsworth on 15-part Mr. Handy body; 4-line Sanctuary talk `completed=true`, `fallback=0` (close camera & greeting replay noted) | Unmerged `#854`: Sanctuary keeps Codsworth's converted 15-part body + S3 House 01/02 packages & Stage-50 scene with `#762` async `Scene.OnEnd` & full-window retries; `--codsworth-handy` remains OFF (`S1` Pre-War reserved for Task 6) | Review CLEAR; awaiting owner merge |
| **Creature animations** | `#855` (`claude/creature-anim`) | Partial: radroach idle & deathclaw tail/spines moved in game; walk/attack/death & bloatfly/mole rat/dog unverified | Unmerged `#855`: `FO4SF_S2CreatureSlotReady (09000B8C) = 0.0` routes `S2` Vault Roaches & `S3` Sanctuary Bloatflies through `creature_slot=empty` fallback cleanly until `creature-slots.json` clears | Stacked on `#854` |
| **Human animations** | `#856` (`claude/human-anim`) | Partial: add-on race keyword NPC played FO4 surrender idle vs normal control; walk & 1stP gun unverified | Unmerged `#856`: built with `--fo4-human-anims 0` (`FO4SF_Fo4HumanAnimsEnabled 09000B8E = 0.0`); 3F NPCs (`Preston`, `Sturges`, `Mama Murphy`, `Marcy`, `Jun`) stay on vanilla SF `HumanRace` (`0000347D`) with FO4 outfits | Stacked on `#854`; flag flips ON only after `#856` PASS |
| **Gun moving parts proof** | `#32` (`gunpart-slide-vanilla-vs-ours-1123.jpg`) | Proved `Gun_*.af` moves `XM2311` slide nodes | Consumes cleared `@r12-t2-arsenal` P6 `FO4SFCoreValues.esm` (`bfe6d99a...`) + Row 5 Pipe Pistol/Rifle + `.38` (`geometries/`, `materials/`, `meshes/` + Rows 1–5/ammo/core DDSs packed inside `< 4.000 GiB` single `Main.ba2`) | Owner rule: guns NOT ready until parts move |
| **Gun sounds** | `#32` (`sound-bank-study`) | **ON HOLD**: hand-made bank (`v174` vs SF `v140`) & direct override silent (add-on banks load on demand) | All `FO4SFCoreValues.esm` & S4/S5 pipe/musket/10mm weapons retain labelled Starfield donor `SNDR` stand-ins; zero custom `.afx`/WAUD audio banks touched | Next probe tests per-item bank link |
