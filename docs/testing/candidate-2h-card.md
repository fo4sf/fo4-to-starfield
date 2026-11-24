# Session Card — `candidate-2h-2`: Round 13 Task 2 (`P1 v2` Fixes + Vault Roaches `S2` + Codsworth `S3` + Concord/Museum `S4`–`S6` + `2g-fix2` Parity)

> **Build Profile & Verdict (`24 Nov 2026`):** **`OFFLINE STAGED — UNPROVEN IN GAME`** (`NEW GAME needed`; clean start from Vault 111 required — do NOT load a `2g`/`2g-fix2` save created before `FO4SF_R11FullMission`, `FO4SF_LoadDoorQuest` `0x000BDE`, or merged `NAVI` `FO4Port.esm`).
>
> - **Branch & Fixes Included (`#853` Must-Fix / Should-Fix / `P1 v2`):** `gemini/r13-w2-2h` (`candidate-2h-2` re-staged by coordinator with `@r13-w2-p6b`). Fixes **`B1`** (real converted FO4 `.nif` models + non-zero `ObjectBounds` + `bhkNPCollisionObject` on every placed `ACTI` + hidden overlapping FO4Core/FO4Port doors), **`F9`** (`s5_roof_out` at FO4 `0002C1C6` `XTEL` `(-1990.58, -1724.19, 97.56)` `1.77 m` from `ExtRoofIn`), **`L3`** (lossless `NAVI 0x00000FF1` merge + `FO4SF_S5_MuseumRaiderPursuePack` `09000BE1` + periodic pursue/combat re-engagement), **`FO4SF_LoadDoorQuest`** (`09000BDE`, `OnPlayerLoadGame` `reload_ready` + `0x0A775B` primary / `0x0A775C` fallback + `12 s` watchdog), **`H1`** (`!EnableS6ToS9Full` guard on `Min00` stage `40`), **`H2`** (stand-in `Settler Clothes` `09000BE4`/`09000BE5` on `09000A00`, `09000BC3`, `09000BC5`, `09000BC7`), **`M2`** (`creature-slots` default OFF `ready=false`, `""`/`0`), **`M3`** (`--fo4-human-anims 0`; links `FO4SFHumanAnims.esm` when ON, never local `0xBDC`), **`M7`** (Codsworth-only `<= 10 m` S3 arrival), **`L1`** (`0C000809` Fusion Core), and **`L2`** (dual S2 completion/exit lines).
> - **Optional Flags Held OFF by Default (`#854`/`#855`/`#856` unmerged):** `--r11-full-mission 1`, `--task1b-vault-recovery 1`, **`--fo4-human-anims 0`** (`09000B8E=0.0`), **`creature_slot=empty`** (`09000B8C=0.0`), **`--codsworth-race-framing 0`**, `--codsworth-handy` OFF (`S1` Pre-War belongs to Task 6), `09000979` `FO4SF_MissionTalkUseMessageBox = 0.0`, `0 WRLD` overrides in `FO4SFMission.esm`.
> - **Single-Archive `4.000 GiB` Asset Scope (`R15` Honesty Disclosure):** `make_core_bundle.py` enforces `< 4.000 GiB` single-`Main.ba2` packing: `candidate-2h-2` folds all `372` non-texture P6b arsenal files + all `129` `.dds` textures for Rows `1`–`5`, all `13` ammos, and all `4` core items (Rows `6`–`20` `.dds` omitted to stay under `4.000 GiB`).
> - **`H2` Clothing Disclosure:** Because converted Fallout 4 settler clothing NIFs for **Sturges**, **Mama Murphy**, **Marcy Long**, and **Jun Long** do not exist in the repository asset pipeline, those four NPCs wear **`Settler Clothes`** (`FO4SF_S6_SettlerClothes_StandIn` `09000BE4` / `FO4SF_S6_SettlerOutfit_StandIn` `09000BE5`, Starfield mechanic clothes stand-in with `ForceHideSpacesuit=1.0`, zero spacesuits), while **Preston Garvey** (`09000801`) and **Concord/Museum Raiders** (`09000986`) wear converted Fallout 4 outfits.
> - **Starfield UI Stand-In Policy (`#32` Owner Direction):** All UI screens (Starfield HUD, Outpost/Workshop builder on the Sanctuary workbench, Novice lockpicking UI, S.P.E.C.I.A.L./Perk menus, DialogueMenu) are labelled **Starfield UI stand-ins** until Fallout UI skins replace them; judge them here strictly on **function** (open cleanly, list right items, zero wrong/blank text such as `"."`, never lock up).
> - **Placeholders:** `<cand2h-player-bundle>`, `<cand2h-test-bundle>`, `<cand2h-port-dir>`, `<mapmarkers-stage-dir>`, `<starfield-dir>` (`>= 60.0 GiB` free on target drive; zero edits to `Starfield/Data` outside explicit install/uninstall steps).

---

## 1. Staged File Scope & Re-Staged Receipts

> Coordinator re-stages `candidate-2h-2` after integrating `@r13-w2-p6b` + `@r13-w2-2h` (`0` stale hashes fabricated here; `FO4Port.*`, `FO4SFMission.esm`, and `FO4SFCoreValues.esm` are refreshed at integration stage).

| Component / Artifact | Contract & Changes in `candidate-2h-2` | Notes |
|---|---|---|
| `<cand2h-port-dir>/FO4Port.*` | Lossless Slot 1 (`0` diffs on `55,071` baseline records; `L3` lossless merge of Museum `NVMI`s into `NAVI 0x00000FF1` preserving base `NVER`/`NVMI`/`NVPP` + `LTMP 0x0006BCF8` + `XLOC 25`/`XLKR`) | Re-staged `FO4Port.esm`, `FO4Port - Main.ba2`, `FO4Port - Textures.ba2` |
| `FO4SFCoreValues.esm` | `@r13-w2-p6b` P6 Arsenal + Row 5 Pipe Guns (`060008A1`–`060008A5`, `06000851`); `--test-mode 0` (`player`) / `--test-mode 1` (`test`) | Integrated by coordinator |
| `FO4SFMission.esm` | `15 QUST` (adds StartGameEnabled `FO4SF_LoadDoor` `09000BDE`), `25 NPC_`, `0 WRLD`; `B1` NIF+OBND on `0xBA7`–`0xBE0`; `0xBE1` ground raider pursue pack; `H2` `0xBE4`/`0xBE5` `Settler Clothes` (stand-in disclosed in card/EDIDs); `M2` OFF; `M3` no local `0xBDC`; `F9` `(-1990.58, -1724.19, 97.56)` | Re-built + `Data/meshes/fo4sf/powerarmor/fusioncore.nif` packed |
| `FO4SFNewGame.esm`, `FO4SFVaultGearDoor.esm`, `FO4SFExitLift.esm`, `FO4SFWorkshop.esm` | `1b` cryo-pod `autosave` w/ `skips=<n>`, zero `OnDying` save; `FO4SFWorkshop.esm` non-Localized (`0` `LCTN`/`STDT`/`PNDT` overrides, `0x058606`/`0x1A5507` `FLST` + `CTDA 0x00084A == 1.0`, `candidate-2g-fix4` parity) | Inherited / re-linked against `FO4Port.esm` |
| `FO4SFPowerArmor.esm` | Unchanged from `candidate-2g-fix2`; owns `FO4SF_FusionCore` (**`0C000809`** in player load order; `0x000809` local) | `L1` ID corrected from `0A` to `0C` |
| `FO4SFPipboyMenu.dll` (`sfse_sidecar`) | Tested DLL reused (`ShellBackdrop=1`, `ShellVitalsFill=1`, `SuppressDataMenu=0`, `TabOpensPipboy=0`, `HideStarfieldWatch=1`, `F7` opens `STAT`) | Verified `24 Nov` in `2g-fix2` |

---

## 2. Uninstall Preconditions, Install & Reversible Rollback Commands (Game Closed)

### Uninstall / Install Preconditions (`MUST` satisfy before any install or swap)
1. **All game/tool processes closed:** `Starfield.exe == 0`, `CreationKit.exe == 0`, `Archive2.exe == 0`.
2. **Clean prior probe/candidate state first:** If `P1` (`FO4SF_R11P1Museum.esm`), `P4`, `candidate-2g-fix2`, or `candidate-2h` is currently installed, run its full uninstall + `FO4Port` backup restore BEFORE installing `candidate-2h-2`, so `Plugins.txt`, `Data/`, and `FO4Port.*` start from a verified clean Vanilla baseline. Never keep two `FO4SF_*` candidate bundles or probes installed simultaneously.
3. **Verify offline first** (`verify --bundle-dir ... --port ...`) and **start a clean New Game** after install; delete throwaway test saves after logging completes.

- **`13`-Plugin `--profile player` Load Order (`Plugins.txt`):** `FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm` (with `<cand2h-port-dir>/FO4Port.*` backed up and swapped onto `<starfield-dir>/Data/FO4Port.*`).
- **`22`-Plugin Optional `--profile test` Load Order:** `FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFCoreCandidate.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm`.

```bash
# 1. Verify player bundle + lossless FO4Port.esm + B1 placed ACTI assets before touching Starfield\Data
python scripts/core/make_core_bundle.py verify --bundle-dir <cand2h-player-bundle> --port <cand2h-port-dir>/FO4Port.esm
python scripts/testing/check_beginning_pilot.py check-bundle --bundle-dir <cand2h-player-bundle>

# 2. Reversible FO4Port.* backup (skip if <starfield-dir>/Data/FO4Port_pre2h_backup already holds original SHA-256) and swap
mkdir -p <starfield-dir>/Data/FO4Port_pre2h_backup
cp -n <starfield-dir>/Data/FO4Port.esm "<starfield-dir>/Data/FO4Port - Main.ba2" "<starfield-dir>/Data/FO4Port - Textures.ba2" <starfield-dir>/Data/FO4Port_pre2h_backup/
cp -f <cand2h-port-dir>/FO4Port.esm "<cand2h-port-dir>/FO4Port - Main.ba2" "<cand2h-port-dir>/FO4Port - Textures.ba2" <starfield-dir>/Data/

# 3. Install 13-plugin player bundle + SFSE sidecar + map markers + staged P3 batches (<cand2h-player-bundle>/bat/*.txt -> <starfield-dir>/)
python scripts/game/exp_install.py install --exp-dir <cand2h-player-bundle> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2h-player-bundle> --starfield <starfield-dir>
python scripts/game/map_markers_install.py install --stage <mapmarkers-stage-dir> --starfield <starfield-dir>
cp -f <cand2h-player-bundle>/bat/*.txt <starfield-dir>/
```

### Exact Undo / Rollback Command (Game Closed — Restores Original `FO4Port.*` + Clean `Starfield/Data`)

```bash
rm -f <starfield-dir>/h2st.txt <starfield-dir>/h2h2.txt <starfield-dir>/h2h3.txt <starfield-dir>/h2h4.txt <starfield-dir>/h2f.txt <starfield-dir>/h2b.txt <starfield-dir>/h2k.txt <starfield-dir>/h2p.txt <starfield-dir>/h2r.txt
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/map_markers_install.py uninstall --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
cp -f <starfield-dir>/Data/FO4Port_pre2h_backup/FO4Port.esm "<starfield-dir>/Data/FO4Port_pre2h_backup/FO4Port - Main.ba2" "<starfield-dir>/Data/FO4Port_pre2h_backup/FO4Port - Textures.ba2" <starfield-dir>/Data/
rm -rf <starfield-dir>/Data/FO4Port_pre2h_backup
```

---

## 3. Card 2h-1 (`S1` Pre-Flight, `1b` Vault Recovery, `S2` Roaches & `2g-fix2` Parity — `OWNER / TEST-STATION`)

| Step | Action | Expected In-Game & Log Result | Status | VIDEO |
|---|---|---|---|---|
| **1a. New Game (`NEW GAME needed`)** | Launch SFSE -> **New Game -> Vault 111 / Story**. | Cryo pod wakes clearly with Starfield lower-left wrist watch hidden (`HideStarfieldWatch=1`); `FO4SF_NEWGAME rt=<rt> stage 20 by=Trigger`; pod autosave logs `vault_death_recovery=autosave stage=20 skips=<n>` (and `< stage 200` Vault death recovers cleanly with zero `OnDying` save). | Pending | Take `v111-pod`: `>= 4 s` cryo wake to lower-left HUD; at `1 fps`, **PASS** if cryo room clears and watch stays hidden; **FAIL** if stuck black or `MARS`/`O2` watch draws; **`audio: not judged`**; opening flash **`needs a slowed take`**. |
| **1b. `S2` Vault 111 Roaches (`09000B90`, `L2`)** | Walk Vault 111 corridor toward Overseer/lift (`09000B8D=1`, `09000B8C=0` empty creature slot). Either sweep all 5 markers (`09000B91..09000B95`, `<= 12 m`) or proceed straight to lift. | `s2 vault_roaches stage 10 armed`, `s2 vault_roaches creature_slot=empty fallback=stage_gate`, and completes with **EITHER** `s2 vault_roaches complete creature_slot=empty stage=100` *(all 5 markers visited <= 12 m)* **OR** `s2 vault_roaches stopped reason=left_vault_stage_200` *(exited Vault early)*. | Pending | Take `v111-corridor`: `>= 6 s` corridor walk; at `1 fps`, **PASS** if corridor stays traversable with zero placeholder freeze; **FAIL** if player snags or un-skinned placeholder blocks hall; **`audio: not judged`**. |
| **1c. Pistol (`10mm`), Pip-Boy (`F7`), & Lift -> Daylight (`E4`/`E6`)** | Press **`E`** on Armory desk pistol (`0A000820`) & ammo (`0A000821`), Pip-Boy (`0A00080F`), and Vault console (`0A000819`), spend 33 S.P.E.C.I.A.L., ride lift -> hilltop (`stage 200`), press **`F7`** + `PageDown`/`A`/`D`/`T`/`M`/`Tab`. | Auto-equips pistol (`pistol picked ... equipped=True`), lands outdoors in **clear Commonwealth daylight** (`z ≈ 128 m`, `fallback=false`), `06000865=1.0`, `09000B8B=1.0`, `09000816=10`, Pip-Boy cycles `STAT <-> INV` -> `APPAREL` -> `Perk Chart` with `E) STIMPAK R) RADAWAY T) PERK CHART` and zero wrist watch. | Pending | Take `v111-surface-pipboy`: `>= 10 s` lift fade + `F7` Pip-Boy paging; at `1 fps`, **PASS** if daylight lands without orange dust storm and `APPAREL` / Perk Chart render cleanly; **FAIL** if stuck black, `MARS` watch appears, or Pip-Boy freezes; **`audio: not judged`**; equip/page frames **`needs a slowed take`**. |

---

## 4. Card 2h-2 (`S3` Codsworth House Walk `M7` & Stage-50 + `2g-fix2` Sanctuary Bench Parity — `TEST-STATION`)

| Step | Action | Expected In-Game & Log Result | Status | VIDEO |
|---|---|---|---|---|
| **2a. Cold Reload #1 (`Throwaway_2h_Surface`)** | Save on Vault 111 hilltop -> `Quit to Desktop` -> relaunch SFSE -> load save. | `reload mission stage=0 relocate_fails=0`, `codsworth01 reload stage=10 choices=0`, `FO4SF_LOADDOOR reload_ready`, daylight restored, zero spurious hilltop return-lift popup. | Pending | Take `surface-cold-reload`: `>= 5 s` after save load; at `1 fps`, **PASS** if hilltop loads in daylight with zero return-lift menu; **FAIL** if black fade or return-lift prompt fires; **`audio: not judged`**. |
| **2b. `S3` Walk With Codsworth (`M7` — NO `bat h2h1`!)** | Walk down on foot to Sanctuary Hills (`09000811`). Press **`E`** on Codsworth (`DialogueMenu` `09000979=0.0`, zero `MessageBox`) -> ask Concord -> **walk on foot beside Codsworth** from House 01 (`(-2313.44, -1372.02)`) to House 02 (`(-2296.17, -1424.97)`) -> press **`E`** at Stage `50`, then press **`E`** once more after Stage `100` (`Step 3` goodbye). | S3 advances **ONLY when Codsworth arrives `<= 10 m`** (`codsworth_dist<=10`): logs `codsworth01 s3 creature_slot=empty fallback=arrival_advance`, **`codsworth01 house1_cleared dead=3/3 stage=34`** + **`codsworth_dist=`**, **`codsworth01 house2_cleared dead=3/3 stage=40`** + **`codsworth_dist=`**; Stage `50` opens `FO4SF_S3_Stage50Scene` (`09000B9A`) cleanly (`0` `fallback=messagebox`) -> `codsworth01 stage 100 concord_pointed=true`, `min00 given by=codsworth`; repeat `E` opens 1-choice goodbye `090009C0`. | Pending | Take `sanctuary-codsworth-s3`: `>= 15 s` walking beside Codsworth between houses + Stage `50` DialogueMenu + post-`100` goodbye; at `1 fps`, **PASS** if Codsworth leads to both houses & `DialogueMenu` renders both times; **FAIL** if houses clear without Codsworth near (`> 10 m`) or `MessageBox` shows; **`audio: not judged`**. |
| **2c. `2g-fix2` Workbench Parity (`D4`/`E6`/`F3`/`F4`)** | Press **`E`** on default Sanctuary bench (`04005C50`) -> close -> test clean swap `bat r11swp1` (`0B000849`) -> close -> restore `bat r11swp0`. | BOTH benches show non-blank footer (ZERO lone `"."`); `SANCTUARY` category + `"Wooden Chair"`, `"Sleeping Cot"`, `"Storage Crate"` appear ONLY on `0B000849` after `bat r11swp1` (`0B00084A == 1.0` CTDA), zero Sturges open-mode popup. | Pending | Take `sanctuary-bench-parity`: `>= 6 s` bottom-left workshop footer & `SANCTUARY` tab; at `1 fps`, **PASS** if footer is non-blank (zero `"."`) and `SANCTUARY` stays scoped; **FAIL** if `"."` draws or `SANCTUARY` is empty on `0B000849`; **`audio: not judged`**. |

---

## 5. Card 2h-3 (`S4` Concord Exterior `z ~88`, `30 s` Pipe-Gun Survival, Preston Balcony & Display Musket — `TEST-STATION`)

| Step | Action | Expected In-Game & Log Result | Status | VIDEO |
|---|---|---|---|---|
| **3a. Hop Chain (`< 200 m`/axis) & Concord Exterior `z ≈ 88 m` Gate** | Walk or run `bat h2h2` -> wait `3 s` -> `bat h2h3` -> wait `3 s` -> `bat h2h4` -> Concord Museum street. | Zero skips `>= 200 m`/axis; Concord buildings, street, & Museum facade render on solid ground at **`z ≈ 88.3..90.0 m`** (NEVER bare Mars `z ≈ 12.6 m`!). | Pending | Take `concord-exterior-z88`: `>= 5 s` street pan facing Museum of Freedom facade; at `1 fps`, **PASS** if Concord buildings & street (`z ~88 m`) render cleanly with visible front doors; **FAIL** if bare Mars terrain appears; **`audio: not judged`**. |
| **3b. `2g-fix2` `30 s` Street Fight Survival (`>= 50%` HP, God Mode OFF)** | With **god mode OFF**, engage `3` Concord street raiders (`09000803..09000805`, wielding pipe guns / softened stand-ins) continuously for `>= 30 s` using street cover; inspect fallen raiders up close (`D2`). | Player HUD HP bar stays **`>= 50%` (`half health or more`) at `30 s`** with god mode OFF; raiders wear FO4 raider clothes (`0` spacesuits); `ArmRaiderForCombat` logs real `dmg=` & `eff_dmg=`. | Pending | Take `concord-survival-30s`: `>= 30 s` uninterrupted Concord street combat HUD; at `1 fps`, **PASS** if HUD HP stays `>= 50%` after `30 s` & raiders wear FO4 outfits; **FAIL** if HP drops `< 50%` or player dies `< 30 s`; **`audio: not judged`**; incoming shot flashes **`needs a slowed take`**. |
| **3c. Preston Balcony & **`press E`** Display Musket (`09000BA8`) + Cells (`09000BAA..BAC`)** | Observe Preston on 3F balcony (`(-2010.51, -1697.71, 98.51)` m) firing `0600089E`. Walk to fallen Minuteman items outside front door: **press `E` on `FO4SF_S4_DisplayLaserMusketRef` (`09000BA8`, `fo4_lasermusket.nif`)** and **press `E` on all `3` Fusion Cell pickups (`09000BAA..09000BAC`, `microfusioncell.nif`)**. *(Zero `<ref>.activate player`!)* | Visible FO4 meshes + `[Take]` prompts without console activate: `s4 balcony preston_z=98.51 ext_raiders=3`, `s4 preston equipped comp_laser_musket=0x089E`, `s4 laser_musket granted cells=15` (`FO4_LaserMusket` `0600089D` + `15` `0600089B`, completes obj `70`), plus `+3x5` Fusion Cells (`pickup fusion_cell count=5 granted=true`). Zero Red Rocket / Dogmeat triggers. | Pending | Take `concord-musket-pickups`: `>= 6 s` aiming at & pressing `E` on musket + 3 cells (`balcony` pan included); at `1 fps`, **PASS** if real FO4 musket/cell models show `Take [E]` and vanish on press; **FAIL** if invisible/no prompt or console activate needed; **`audio: not judged`**. |

---

## 6. Card 2h-4 (`P1 v2` Door Round-Trips, Cold Reload Inside Door, `S5` 7 Raiders + Ground Climb & `A4.5` Pickups — `TEST-STATION`)

| Step | Action | Expected In-Game & Log Result | Status | VIDEO |
|---|---|---|---|---|
| **4a. Front Door `5x` Round-Trip (**`press E`**, NO `<ref>.activate`)** | Walk up to Museum front double door (`(-2010.69, -1698.04, 89.26)`), confirm visible collidable FO4 wood doors (`paintedwooddoordoubleload01.nif`) show **`[Open] Museum of Freedom`**, and **press `E` on `FO4SF_S5_ExtFrontInRef` (`09000BB8`)** -> Lobby `(7.73, 0.91, -0.90)` -> turn & **press `E` on `FO4SF_S5_IntFrontOutRef` (`09000BB9`)** -> Concord street `(-2012.50, -1697.94, 88.24)` (`z ≈ 88.24 m`). Repeat **`5` complete round trips (`5x` in + `5x` out)**. | Overlapping `FO4Core` / `FO4Port` statics hidden cleanly; every press shows legible `Open [E]` prompt and logs `FO4SF_LOADDOOR activate_begin` -> `FO4SF_LOADDOOR confirmed tag=s5_front_in` / `s5_front_out ... core_cell=true` (inside Museum lit by `LTMP 0x0006BCF8`, outside at **`z ≈ 88.24 m`**, `0` bounces/`ILS`). | Pending | Take `museum-front-door-5x`: `>= 15 s` showing visible door aim prompt `Open [E]` + exterior->interior->exterior round trip; at `1 fps`, **PASS** if door model shows prompt, lobby loads lit, and street exits cleanly `z ~88 m`; **FAIL** if invisible/unclickable or `ILS`/Mars bounce; **`audio: not judged`**; load-fade boundary **`needs a slowed take`**. |
| **4a2. Cold Reload Inside Museum Front Door (`FO4SF_LoadDoorQuest` Fix)** | Inside `FO4Port_ConcordMuseum01`, save **`Throwaway_2h_MidMuseum`**, **`Quit to Desktop`**, relaunch SFSE, load `Throwaway_2h_MidMuseum`, walk to front door, and **press `E` on `FO4SF_S5_IntFrontOutRef` (`09000BB9`)**. | `OnPlayerLoadGame` cancels stale timers, clears `busy`/`inFlight`, and logs `FO4SF_LOADDOOR reload_ready`; pressing **`E`** on `09000BB9` immediately resolves persistent `0x0A775B` (`0x0A775C` fallback) -> logs `FO4SF_LOADDOOR confirmed tag=s5_front_out dir=out ... core_cell=true` (never stalls after `activate_begin`!). | Pending | Take `museum-cold-reload-door`: `>= 8 s` after save reload -> press `E` on interior front door -> Concord street; at `1 fps`, **PASS** if exiting lands on Concord street (`z ~88 m`); **FAIL** if door hangs on `activate_begin`; **`audio: not judged`**. |
| **4b. `S5` 7 Raiders + Ground Climb (`L3`) + `press E` Pickups -> `Min00 35`** | Engage `7` museum raiders (`09000BBC..09000BC2`). Stand on 2F/3F balcony & watch ground raider (`09000BBC`) climb atrium stairs via merged `NAVM`/`NAVI 0x00000FF1` + `09000BE1` pursue AI (without silent tick-5 drop). **Press `E`** on `2` visible Stimpaks (`09000BAE..BAF`), Caps (`09000BB1`), Bobby Pin (`09000BB3`), and Pipe Pistol + `.38` (`09000BB5`). | Ground raider actively pursues & climbs stairs (`climbed_stairs` / active combat); all `5` item activators display visible FO4 meshes + `Take [E]` prompts (`pickup stimpak/caps/bobbypin/pipe_weapon ... granted=true`); killing all `7` raiders logs `s5 museum_cleared dead=7/7 stage=35 preston_door=unlocked`. *(Keep `2` throwaway saves inside before basement gate `0100EDF0` unlocks for Row 5b!)* | Pending | Take `museum-raider-climb-pickups`: `>= 15 s` showing ground raider moving up stairs + item `Take [E]` pickups + `7/7` door unlock; at `1 fps`, **PASS** if ground raider advances toward stairs & FO4 item meshes respond to `E`; **FAIL** if raider freezes permanently at tick 5 or items lack meshes; **`audio: not judged`**. |

---

## 7. Card 2h-5 (`S6` 3F Scenes `H1`/`H2`, Basement Gate Terminal **AND** Bobby Pin `5b`, `0C000809` & `F9` Roof `3x` Round-Trip — `TEST-STATION`)

| Step | Action | Expected In-Game & Log Result | Status | VIDEO |
|---|---|---|---|---|
| **5a. `S6` 3F Room (`H1` No Early 200 + `H2` `Settler Clothes` Stand-In)** | Enter 3F room (`Preston 09000802` FO4 duster/hat; `Sturges 09000A01`, `Mama Murphy 09000BC4`, `Marcy 09000BC6`, `Jun 09000BC8` in **`Settler Clothes`** stand-in `09000BE4`/`09000BE5`, `0` spacesuits). **Press `E`** on Preston (`09000BC9`) & Sturges (`09000BD0`), then repeat `E` on Preston. | `s6 preston room scene started` -> `s6 preston room dialogue menu opened` (`0` `fallback=messagebox`) -> **`s6 stage 40 preston_group talk` does NOT finish `Min00` at `200`** (`H1`: held open for basement gate & Fusion Core!); Sturges opens `09000BD0`; zero spacesuits on all 5 NPCs. | Pending | Take `museum-3f-room-h1-h2`: `>= 10 s` panning across Preston + 4 settlers & Preston/Sturges `DialogueMenu`s + `Missions` HUD check; at `1 fps`, **PASS** if zero spacesuits appear & quest stays active at stage `40`; **FAIL** if spacesuits appear or `"When Freedom Calls"` completes early; **`audio: not judged`**. |
| **5b. Basement Gate (`0x0100EDF0`, `XLOC 25`) — Terminal AND Bobby Pin (`bat h2p`) + `0C000809`** | **Test BOTH unlock paths** on Novice gate `0100EDF0` (`DOOR 000BA4B5`, lock `25`):<br>1. **Terminal path:** **Press `E` on visible terminal `FO4SF_S6_BasementTermRef` (`09000BD9`, `terminalwall01.nif`)** -> confirm gate opens cleanly.<br>2. **Bobby Pin / Digipick path:** Load pre-unlock save (`bat h2b` or walk to `0100EDF0`), ensure pin inventory via collected `09000BB3` or **`bat h2p`** (`player.additem 0000000A 2`, `060008A5 2`), and **press `E` on locked gate `0100EDF0`** to pick Novice lock directly.<br>3. Walk inside generator cage & **press `E` on visible `MQ102FusionCoreREF` (`09000BDB`, `fusioncore.nif`)**. | Path 1 logs `pickup basement_terminal unlocked=true`, `s6 basement_gate unlocked reason=terminal`, `s6 stage 45 basement_gate opened`. Path 2 opens Novice lockpicking UI & unlocks `0100EDF0` cleanly with Bobby Pin/Digipick (`s6 stage 45 basement_gate opened`). Pressing **`E`** on `09000BDB` logs `pickup fusion_core granted=true fid=2057` -> grants `FO4SF_FusionCore` (**`0C000809`** `L1`) -> `s6 stage 50 fusion_core picked obj=95 stop=put_fusion_core_in_pa` (**HARD STOP at `"Put the Fusion Core in the Power Armor"`**). | Pending | Take `museum-basement-both-paths`: `>= 15 s` showing visible wall terminal `E` unlock, reload -> `bat h2p` lockpick on `0100EDF0`, & `E` on `09000BDB` Fusion Core + inventory check `0C000809`; at `1 fps`, **PASS** if terminal & lockpick both unlock gate & visible core vanishes into inventory; **FAIL** if only one path works or core is invisible; **`audio: not judged`**. |
| **5c. Roof Door `3x` Round-Trip (`F9` `(-1990.58, -1724.19, 97.56)` — NO Roof Drop!)** | Walk to 3F roof doorway (`(-21.943, 9.02, 9.143)`), **press `E` on visible `FO4SF_S5_IntRoofOutRef` (`09000BBA`, `bldwoodpdoorload01.nif`)** -> lands on exterior roof bulkhead **`(-1990.58, -1724.19, 97.56)`** (`z ≈ 97.56`, **`1.77 m`** from `FO4SF_S5_ExtRoofInRef` at `(-1991.27, -1722.57, 97.42)`), turn NNW & **press `E` on `09000BBB`** -> interior `(-21.90, 8.68, 9.15)`. Repeat **`3` complete round trips (`3x` out + `3x` in)**. | Every leg confirms (`core_cell=true` outdoors at `z ≈ 97.56`), player stands solidly on roof bulkhead beside `ExtRoofIn` (ZERO drop off roof to `z ≈ 88.2`!), zero `ILS` or `2.9 km` bounce. Delete throwaway saves when done. | Pending | Take `museum-roof-door-3x`: `>= 12 s` showing `IntRoofOut` `Open [E]` -> solid standing arrival on roof bulkhead (`z ~97.56`) beside `ExtRoofIn` -> re-entry; at `1 fps`, **PASS** if player stands firmly on roof near bulkhead across `3x` trips; **FAIL** if falling off roof to `z ~88` or `ExtRoofIn` unclickable; **`audio: not judged`**. |

---

## 8. Console Inspection & `< 200 m` Hop Batch Blocks (`P3` Zero-`M`/`N`/`V` Enforced)

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

*(Staged in `<cand2h-player-bundle>/bat/h2*.txt`; copied to `<starfield-dir>/` during install. Note: `bat h2h1` is removed per **`M7`** so Codsworth leads house-to-house on foot; `bat h2b` and `bat h2k` are strictly **INTERIOR-ONLY** inside `FO4Port_ConcordMuseum01` after `bat h2f`.)*

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

; <starfield-dir>/h2f.txt — direct interior Museum lobby (0x0100E2F4, NAVM tri 87)
coc FO4Port_ConcordMuseum01
player.setpos x 7.73
player.setpos y 0.91
player.setpos z -0.90
player.setangle z 270

; <starfield-dir>/h2b.txt — INTERIOR-ONLY (run ONLY AFTER `bat h2f` inside FO4Port_ConcordMuseum01): basement Novice gate 0x0100EDF0 (-13.714, -0.457, -3.657)
player.setpos x -14.38
player.setpos y -0.10
player.setpos z -3.32
player.setangle z 90

; <starfield-dir>/h2k.txt — INTERIOR-ONLY (run ONLY AFTER `bat h2f` inside FO4Port_ConcordMuseum01): outside 3F PrestonDoorREF (5.486, -7.314, 9.143)
player.setpos x 4.20
player.setpos y -7.25
player.setpos z 9.15
player.setangle z 90

; <starfield-dir>/h2p.txt — Grant Bobby Pin & Starfield Digipick for Row 5b Novice lock 0x0100EDF0 testing
player.additem 0000000A 2
player.additem 060008A5 2

; <starfield-dir>/h2r.txt — exterior Museum roof bulkhead (FO4 0002C1C6 XTEL arrival, facing ExtRoofIn -1991.27, -1722.57)
player.setpos x -1990.58
player.setpos y -1724.19
player.setpos z 97.82
player.setangle z 335
```

### Required PASS Log Lines (`fo4sf_newgame.0.log`, `fo4sf_mission.0.log`, `fo4sf_loaddoor.0.log`)

```log
FO4SF_NEWGAME rt=<rt> vault_death_recovery=<autosave|reload> stage=<st>
FO4SF_LOADDOOR reload_ready cell=<cell> interior=<true|false>
FO4SF_MISSION rt=<rt> s2 vault_roaches creature_slot=empty fallback=stage_gate
FO4SF_MISSION rt=<rt> s2 vault_roaches <complete creature_slot=empty stage=100|stopped reason=left_vault_stage_200>
FO4SF_MISSION rt=<rt> codsworth01 s3 creature_slot=empty fallback=arrival_advance
FO4SF_MISSION rt=<rt> codsworth01 house1_cleared dead=3/3 stage=34 codsworth_dist=<d>
FO4SF_MISSION rt=<rt> codsworth01 house2_cleared dead=3/3 stage=40 codsworth_dist=<d>
FO4SF_MISSION rt=<rt> codsworth01 stage 50 scene started
FO4SF_MISSION rt=<rt> codsworth01 stage 100 concord_pointed=true
FO4SF_MISSION rt=<rt> s4 balcony preston_z=<z> ext_raiders=3
FO4SF_MISSION rt=<rt> s4 preston equipped comp_laser_musket=0x089E
FO4SF_MISSION rt=<rt> s4 laser_musket granted cells=15
FO4SF_MISSION rt=<rt> pickup stimpak count=1 granted=true
FO4SF_MISSION rt=<rt> pickup pipe_weapon granted=true ammo=true
FO4SF_LOADDOOR confirmed tag=s5_front_in dir=in attempts=<n> core_cell=<true|false> cell=<cell> world=<world> pos=<pos> heading=<hdg>
FO4SF_LOADDOOR confirmed tag=s5_front_out dir=out attempts=<n> core_cell=true cell=<cell> world=<world> pos=<pos> heading=270.0
FO4SF_MISSION rt=<rt> s5 museum_cleared dead=7/7 stage=35 preston_door=unlocked
FO4SF_MISSION rt=<rt> s6 preston room scene started
FO4SF_MISSION rt=<rt> s6 sturges room dialogue menu opened
FO4SF_MISSION rt=<rt> s6 stage 40 preston_group talk
FO4SF_MISSION rt=<rt> s6 basement_gate unlocked reason=<reason> pending_stage40=true
FO4SF_MISSION rt=<rt> s6 stage 45 basement_gate opened
FO4SF_MISSION rt=<rt> pickup fusion_core granted=true fid=2057
FO4SF_MISSION rt=<rt> s6 stage 50 fusion_core picked obj=95 stop=put_fusion_core_in_pa
FO4SF_LOADDOOR confirmed tag=s5_roof_out dir=out attempts=<n> core_cell=true cell=<cell> world=<world> pos=(-1990.58,-1724.19,97.56) heading=335.0
```

### Negative / FAIL Conditions
- Any `2g-fix2` regression (`fallback=messagebox` anywhere, `stage 40 by=fallback`, `FO4SFMission.esm` `WRLD > 0`, non-`0x0006BCF8` museum/Vault 111 lighting, Concord street HP `< 50%` at `30 s` god mode OFF, `"MARS, SOL"` bench footer), any invisible or non-targetable `ACTI` needing `<ref>.activate`, any `2.9 km` bounce / `ILS` / stuck `activate_begin` after cold reload inside Museum front/roof doors, roof exit falling off roof (`z < 97.0`), `Min00` completing at stage `200` before the basement gate (`H1`), failing terminal OR Bobby Pin lockpick path on `0x0100EDF0`, missing `0C000809` Fusion Core grant, or advancing past `"Put the Fusion Core in the Power Armor"`.

---

## Claude's Additions (5 Rows — 23–24 Nov In-Game Baseline)

| Addition | PR / Track | 23–24 Nov In-Game Status | Integration Status in `candidate-2h-2` | VIDEO |
|---|---|---|---|---|
| **Robot animations & Codsworth** | `#854` (`claude/robot-anim`) | Partial pass (`23 Nov` + `24 Nov` `2g-fix2`): FO4 Mr. Handy `15`-part body + animations; Codsworth 4-line talk `completed=true`, `fallback=0`, `camera_guard` (`prev_d=0.62 safe_d=1.85`) | **`gated (#854)`**: `candidate-2h-2` keeps `MiniBotARace` stand-in (`--codsworth-race-framing 0`, `--codsworth-handy` OFF); Codsworth House `01`/`02` travel + Stage-50 scene wired cleanly | Take `sanctuary-codsworth-s3`: `>= 5 s` initial & Stage `50` `E` talk framing; at `1 fps`, **PASS** if camera frames Codsworth cleanly without clipping; **FAIL** if facing away; **`audio: not judged`**. |
| **Creature animations** | `#855` (`claude/creature-anim`) | Partial (`23 Nov`): radroach idle & deathclaw tail/spines moved; walk/attack/death & bloatfly/mole rat/dog unverified | **`not applicable` (default OFF)**: `FO4SF_S2CreatureSlotReady (09000B8C) = 0.0` routes `S2` & `S3` cleanly through `creature_slot=empty` fallback (`M2` ready-path builds `NPC_`s from `FO4SFCreatures.esm` when flipped ON) | Take `v111-corridor` & `sanctuary-codsworth-s3`: `>= 5 s` Vault & house sweeps; at `1 fps`, **PASS** if empty-slot stage fallback advances without broken placeholders; **FAIL** if un-skinned creature freezes hall; **`audio: not judged`**. |
| **Human animations** | `#856` (`claude/human-anim`) | Partial (`23 Nov`): add-on race keyword NPC played FO4 surrender idle vs normal control; walk & 1stP gun unverified | **`not applicable` (default OFF)**: built with `--fo4-human-anims 0` (`09000B8E=0.0`, external link to `FO4SFHumanAnims.esm` wired when ON, `0` local `0xBDC`); `Preston`/raiders wear FO4 outfits while **`Sturges`/`Mama Murphy`/`Marcy`/`Jun` wear `Settler Clothes`** (`09000BE4`/`09000BE5`, Starfield settler clothes stand-in, zero spacesuits) | Take `museum-3f-room-h1-h2`: `>= 5 s` close view of Preston + 4 settlers in 3F room; at `1 fps`, **PASS** if `Preston` wears FO4 duster/hat & settlers wear non-spacesuit clothes stand-in with `0` spacesuits; **FAIL** if any NPC wears a spacesuit or freezes T-pose; **`audio: not judged`**. |
| **Gun moving parts proof** | `#32` (`gunpart-slide-vanilla-vs-ours-1123.jpg`) | Proved `Gun_*.af` moves `XM2311` slide nodes | **`built in`**: consumes `P6` `FO4SFCoreValues.esm` + Row 5 Pipe Pistol/Rifle `.38` (`geometries/`, `materials/`, `meshes/` + Rows `1`–`5`/ammo/core DDSs within `< 4.000 GiB` single `Main.ba2`) | Take `concord-musket-pickups` / `concord-survival-30s`: `>= 4 s` equipping & firing `FO4_PipePistol` / `FO4_LaserMusket`; at `1 fps`, **PASS** if weapon renders & fires cleanly; **FAIL** if invisible mesh; **`audio: not judged`**; moving slide/bolt inspection **`needs a slowed take`**. |
| **Gun sounds** | `#32` (`sound-bank-study`) | **ON HOLD**: custom bank (`v174` vs SF `v140`) silent in game | **`not applicable` (retained Starfield `SNDR` stand-ins)**: all `FO4SFCoreValues.esm` & S4/S5 weapons keep labelled Starfield `SNDR` stand-ins; zero `.afx`/WAUD banks touched | All captures (`>= 3 s`): **`audio: not judged`** across all captures (silent calibration clip audio track per `#32`); **`needs a slowed take`** does not replace audio calibration. |
