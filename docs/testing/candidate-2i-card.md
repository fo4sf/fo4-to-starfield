# Session Card — `candidate-2i`: Round 11 `S7`–`S9` Full Story (`candidate-2h` `S1`–`S6` + `Concord` Roof PA/Minigun `S7` + `DN092` Wave 2 & Deathclaw `S8` + `S9` Lobby, Walk Home & `Min01` 1000 Hard Stop)

> **Build Profile & Verdict (`23 Nov 2026`):** **`OFFLINE STAGED — UNPROVEN IN GAME`** (`NEW GAME needed`; clean start from Vault 111 required — do NOT load a pre-`2h`/`2i` save created before `FO4SF_R11FullMission` / `0x00EFAB` Slot 1 `FO4Port.esm`).
>
> - **Branch & Stacked Scope (`0` merges above cleared `candidate-2h` `51d37bc6`):** `gemini/round11-s7-s9-2i` (`OFFLINE ONLY — UNPROVEN IN GAME`). Inherits full **Slot 1** lossless museum extension (`NextObjectID=0x00EFAB`, local FormIDs `0x00E200..0x00EFAA`, `<cand2h-port-dir>/FO4Port.esm`) and `S2`–`S6` (`0xB8C..0xBDD`) from cleared `candidate-2h`, adding `S7`–`S9` (`0xBE0..0xC05`) with `StopAtFusionCorePowerArmor = false`.
> - **Optional Flags Held OFF by Default (`#854`/`#855`/`#856` unmerged):** `--r11-full-mission 1`, `--task1b-vault-recovery 1`, **`--fo4-human-anims 0`** (`09000B8E=0.0`), **`creature_slot=empty`** (`09000B8C=0.0`, Deathclaw logs `deathclaw_slot=empty` at `DN092 79`), **`--codsworth-race-framing 0`**, `--codsworth-handy` OFF (`S1` Pre-War reserved for Task 6), `09000979` `FO4SF_MissionTalkUseMessageBox = 0.0` (MessageBox fallbacks `0x0990..0x0992` & `0xC04`/`0xC05` unreachable in live dialogue), `0 WRLD` overrides in `FO4SFMission.esm`.
> - **Single-Archive `4.000 GiB` Asset Scope (`R15` Honesty Disclosure):** Inherited from `candidate-2h`'s `make_core_bundle.py` `< 4.000 GiB` single-`Main.ba2` limit (`docs/ai/test-queue.md`), `candidate-2i` packs **all `367` non-texture weapon/ammo/prop files** (`geometries/`, `materials/`, `meshes/` for Rows `1`–`20`) plus all **`129` `.dds` textures** (`139.40 MiB`) for **Rows `1`–`5`** (`baton`, `10mm`, `lasermusket`, `minigun`, `pipepistol`, `piperifle`), **all `13` ammos**, and **all `4` core items** (`stimpak`, `caps`, `bobbypin`, `goopile`). **Rows `6`–`20` `.dds` textures are omitted from `candidate-2i`'s single `Main.ba2`** to stay under `4.000 GiB` (run `<r11-p6-dir>` standalone for full Rows `6`–`20` textures).
> - **`2g-fix2` (`#852`) Inheritance & `#780` Race Hardening:** Reuses tested binary `FO4SFPipboyMenu.dll` (`7d5ba49c`, `MapBlockStarMap=0`) untouched; includes `#780` / `#799` async `DialogueMenu` Close-before-`Scene.OnEnd` (`*AttemptOpened` latches), `ownS9*StopPending` retry guards, non-overlapping S9 lobby timer `7`, dynamic `PlaceRefInMuseumOffset`, and `s8RespawningCount` wait guard.
> - **`P3` Console Rules & Placeholders:** Typed ```` ```console ```` lines and `bat <id>` filenames contain **zero** `m`, `n`, `v` characters (`bat s7r`, `bat s8w`, `bat s9p`, `bat s9q`) and **zero** stripped `FO4SF_*` `GLOB`/`QUST` EditorIDs. Every `setpos` hop moves **`< 180 m` per axis**. Placeholders: `<cand2i-player-bundle>`, `<cand2i-test-bundle>`, `<cand2h-port-dir>`, `<mapmarkers-stage-dir>`, `<starfield-dir>` (`>= 60.0 GiB` free on target drive; zero edits to `Starfield/Data` outside explicit install/uninstall steps).

---

## 1. Staged File Inventory & SHA-256 Receipts (`OFFLINE VERIFIED`)

| Artifact / Stage Component | Bytes | SHA-256 | Notes / Contract |
|---|---:|---|---|
| `<cand2h-port-dir>/FO4Port.esm` | `4,612,735` | `8163ca9a7187bd07fdd09f20ad7c16d511577f91d91c858ed28ec0fc434fef39` | Lossless Slot 1 (`0` diffs on `55,071` baseline records; `3,500` museum/prewar records `0x0100E200..0x0100EFAA`, `NextObjectID=0x00EFAB`, `0` `WRLD`/`PNDT`) |
| `<cand2h-port-dir>/FO4Port - Main.ba2` | `117,755,711` | `064c762499a1cc975df81da2c12ea3a20aec5f84cae0c89f4d9cdac12d094c7e` | `BTDX` v2 `GNRL` (`17,023` entries; museum + prewar mesh/mat delta; `nlink=1`) |
| `<cand2h-port-dir>/FO4Port - Textures.ba2` | `2,289,478,621` | `f4664dd0a4fb49a3adb17440596bbb936b0ffa47516024be9fff07c7b1a69a48` | `BTDX` v2 `DX10` (`4,711` entries; museum texture delta; `nlink=1`) |
| `FO4SFCoreValues.esm` (`player`, `--test-mode 0`) | `76,995` | `bfe6d99a75230b1dbb795c5cd0fcdb30a3b4ffb26e03bc667a73e59570b505d9` | Byte-identical to cleared `r11-p6-arsenal` / `candidate-2h` (`0x000860=0.0`, P6 arsenal + Minigun `0x0008A0`, 5mm `0x00089F`, Fusion Cell `0x00089B`, Caps `0x0008A4`, Pipe `.38`, Stimpak, Bobby Pin) |
| `FO4SFCoreValues.esm` (`test`, `--test-mode 1`) | `76,995` | `425aa3cca7299c560c9735753dee24b2bed8debd989fc5d035cb63210609b4be` | Same schema with `FO4SF_TestModeEnabled (0x000860) = 1.0` |
| `FO4SFMission.esm` (`02b-mission`) | `111,933` | `730fd71187a3fc94c7f705a7e4ac8130baba926f5b052d924523203e794ae73c` | `14 QUST`, `27 NPC_`, `0 WRLD` (`0x000979=0.0`, `0x000B8B=1.0`, `0x000BF4=1.0`, `StopAtFusionCorePowerArmor=false`), `0xBF5` holding cell, `15` `.pex`, `92` assets (`39` `.wem` incl. `00f4c301..00f4c304.wem`) |
| `FO4SFNewGame.esm` (`03-newgame`, `player`) | `12,688` | `0163600cbbe974a0344a858ddd483472a59e90b079632b394bac535cbd9d50f2` | Built against `<cand2h-port-dir>/FO4Port.esm`; `fade_hold=false`, `vault anchor 001338 persistent` |
| `FO4SFNewGame.esm` (`03-newgame-fadehold`, `test`) | `12,688` | `5c9edb843ced9eeaf505f8e0fd9255122d6bbbe4248308ccedbb36dbcc9a9e65` | Built against `<cand2h-port-dir>/FO4Port.esm`; `fade_hold=true` |
| `FO4SFVaultGearDoor.esm` (`01-cog-door`) | `597` | `7aada8bafa027bfd158c63e0728e10e7239401dde57429ba601b7b96a2ea8533` | Built against `<cand2h-port-dir>/FO4Port.esm`; zero probe scripts |
| `FO4SFExitLift.esm` (`02-exit-lift`) | `590` | `34d0db71d1116742d5d644a7772e8f31e43019b72bab9d01c91eec308665d9d4` | Built against `<cand2h-port-dir>/FO4Port.esm`; `37` moving bodies, zero probe scripts |
| `FO4SFWorkshop.esm` (`06-workshop`) | `120,300` | `1b98ebc3eed1dd0decf4e66a2815a52ef8181141326ad8fdded0387f78082a82` | `HeaderFlag.Localized` + `Strings/FO4SFWorkshop_en.*` (`701`/`8`/`688` B) |
| `FO4SFPowerArmor.esm` (`player` / `test`) | `84,270` / `86,186` | `c3332aef3891f4cd647882e80da4f1c6238ba558b12d2c80c2fb32e5fd885c4c` / `d7f0fc494cca47c2cdf570b82368b6f7f4aca96b478aff179e230fed0a45e09d` | Unchanged from `candidate-2h`; owns roof PA frame `0x0801`, `FO4SF_FusionCore` (`0x0A000809`), and fall-damage guard `0x081E` |
| `FO4SFPipboyMenu.dll` (`sfse_sidecar`) | `1,453,568` | `7d5ba49c0c6ab2aa8db24ab1bfb643839259d12404cc95afaa38e2f42201c9a8` | Tested DLL reused unchanged (`ShellBackdrop=1`, `ShellVitalsFill=1`, `SuppressDataMenu=0`, `TabOpensPipboy=0`, `MapBlockStarMap=0`) |

---

## 2. Install & Reversible Port Swap Commands (Game Closed)

- **`13`-Plugin `--profile player` Load Order (`Plugins.txt`):** `FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm` (with `<cand2h-port-dir>/FO4Port.*` backed up and swapped onto `<starfield-dir>/Data/FO4Port.*`).
- **`22`-Plugin Optional `--profile test` Load Order (`<cand2i-test-bundle>`):** `FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFCoreCandidate.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm` (zero `FO4SFRouteLoot.esm` / `FO4SFBridge.esm`).

```bash
# 1. Verify player bundle + lossless Slot 1 FO4Port.esm before touching Starfield\Data
python scripts/core/make_core_bundle.py verify --bundle-dir <cand2i-player-bundle> --port <cand2h-port-dir>/FO4Port.esm

# 2. Reversible FO4Port.* backup (skip if <starfield-dir>\Data\FO4Port_pre2i_backup already holds original SHA-256) and swap
mkdir -p <starfield-dir>/Data/FO4Port_pre2i_backup
cp -n <starfield-dir>/Data/FO4Port.esm "<starfield-dir>/Data/FO4Port - Main.ba2" "<starfield-dir>/Data/FO4Port - Textures.ba2" <starfield-dir>/Data/FO4Port_pre2i_backup/
cp -f <cand2h-port-dir>/FO4Port.esm "<cand2h-port-dir>/FO4Port - Main.ba2" "<cand2h-port-dir>/FO4Port - Textures.ba2" <starfield-dir>/Data/

# 3. Install 13-plugin player bundle + SFSE sidecar + map markers
python scripts/game/exp_install.py install --exp-dir <cand2i-player-bundle> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2i-player-bundle> --starfield <starfield-dir>
python scripts/game/map_markers_install.py install --stage <mapmarkers-stage-dir> --starfield <starfield-dir>
```

### Exact Undo / Rollback Command (Game Closed — Restores Original `FO4Port.*` + Clean `Starfield/Data`)

```bash
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/map_markers_install.py uninstall --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
cp -f <starfield-dir>/Data/FO4Port_pre2i_backup/FO4Port.esm "<starfield-dir>/Data/FO4Port_pre2i_backup/FO4Port - Main.ba2" "<starfield-dir>/Data/FO4Port_pre2i_backup/FO4Port - Textures.ba2" <starfield-dir>/Data/
rm -rf <starfield-dir>/Data/FO4Port_pre2i_backup
```

---

## 3. S7–S9 Key FormIDs & Holding Cell Layout (`FO4SFMission.esm` `0xBE0..0xC05`)

- **`0xBF5` (`CELL FO4SF_S7S9_HoldingCell`):** Dedicated `IsInteriorCell` holding cell (`0` `WRLD` overrides added by S7–S9). Persistent S7/S8 refs start in `0xBF5` and relocate to merged Concord coords at runtime via `0x005C50` / `0x0A775B`.
- **`S7` Roof (`0xBE0..0xBE3` + `FO4SFPowerArmor.esm`):** `0xBE0` `Vertibird Minigun` `ACTI`, `0xBE1` persistent roof minigun ref (`(-2004.72, -1715.40, 102.68)`), `0xBE2` `S7RoofFrameMarker` (`(-1995.73, -1723.10, 97.54)` spawning coreless `FURN 0x000801`), `0xBE3` `S7RoofDoorMarker` (`(-2008.49, -1722.39, 97.42)`). Grants `1x FO4_Minigun` (`0x0008A0`) + `1,200x FO4_Ammo5mm` (`0x00089F`). Zero fall damage perk is owned solely by `FO4SF_PowerArmorCoreQuest` on PA enter/exit (`0x00081E`); roof frame activation locks (`BlockActivation(True)`) while player holds `0` `FO4SF_FusionCore` (`0x000809`) items, and completes Objective `95` when activated with `cores > 0`.
- **`S8` Concord Wave 2 & Deathclaw (`0xBE4..0xBF3`):** `0xBE4` `FO4_Gristle` (non-essential/non-respawning boss, `0x988` non-spacesuit FO4 outfit), `0xBE5` `FO4_WaveRaiderHeavy` (`0x988` outfit), `0xBE6..0xBEA` 5 persistent wave `ACHR`s (`WaveRaider01..03`, `RoofLookout`, `Gristle`), `0xBEB..0xBF0` 6 `DN092WaveSpawner01..06` markers, `0xBF1` failsafe `DN092_WavePost02`, `0xBF2` grate trigger (`<= 17 m`), `0xBF3` `ConcordAmbushDeathclaw` spawn (`(-2068.22, -1640.18, 88.22)`). `respawnPool = 8` respawns only `WaveRaider01..03` between `DN092` `75..79`; `s8RespawningCount` prevents premature completion during `0.5 s` respawn wait.
- **`S9` Real Starfield `SCEN`s, Lobby Reward, Patrol Walk & `Min01` 1000 Hard Stop (`0xBF4`, `0xBF6..0xC05`):**
  - `0xBF6` `FO4SF_S9_PrestonLobbyScene` (`DEVT` Starfield `SCEN` on `FO4SF_Min00` stage `80`, Alias `0`, dedicated timer `7`) with FO4 `.wem` audio (`0x00F4C301..2`). MessageBox `0xC04` strictly gated behind `TalkUseMessageBox != 0`.
  - Rewards `100` `Caps` (`FO4SFCoreValues.esm:0x0008A4`) + `50` `Fusion Cells` (`0x00089B`), **`0` Starfield `Credits`**. Sets `DialogueConcordArea 50 -> Min01 20 -> Min00 100`, reveals Diamond City map marker (`150`).
  - Patrol walk home past Red Rocket to Sanctuary (`MinutemenGroup` preserves all 4 settlers: `Sturges`, `Mama Murphy`, `Marcy Long`, `Jun Long`) using `SetLinkedRef` + keeper failsafe that **never teleports in player view** (`> 65 m` or unloaded cell only).
  - Arriving in Sanctuary sets `FO4SF_Sanctuary01` (`0x817`, `HasDialogueData`) to stage `220`; `0xBFD` `FO4SF_S9_SturgesIntroScene` (`Min01SturgesIntro 001188B4` Starfield `SCEN`, Alias `1`) with FO4 Sturges `.wem` clips (`0x00F4C303..4`) advances to stage `1000` (`"Build sheltered beds"`). Fallback MessageBox `0xC05` gated behind `TalkUseMessageBox != 0`.
  - `0xBF4` `FO4SF_S9_HardStopAtMin01_1000` (`1.0`) holds `FO4SF_MinRecruit00` & `FO4SF_MQ103` strictly OFF at hard stop.

---

## 4. Diagnostic Console & Batch Checks (`P3`-Clean: Zero `M`/`N`/`V`, `< 180 m`/Axis)

Planned optional P3-clean diagnostic batch names (`bat s7r`, `bat s8w`, `bat s9p`, `bat s9q`; **not emitted by `make_mission.py stage` yet**) use numeric FormIDs only when supplied separately (never stripped `FO4SF_*` `GLOB`/`QUST` EditorIDs); test S7–S9 end-to-end via the natural gameplay path from `candidate-2h` S1–S6 (`candidate-2h-card.md`) into Section 5 below:

```console
bat s7r
bat s8w
bat s9p
bat s9q
```

---

## 5. Verification Matrix (`VIDEO` Required — All Offline Verified, Unproven in Game)

| Check ID | Stage / Trigger | Expected In-Game & `fo4sf_mission.0.log` Behaviour | Result | VIDEO |
|---|---|---|---|---|
| `2i-01` | Play S1–S6 (`candidate-2h` stages `01..50`) -> grab Fusion Core (`0A000809`) -> exit to roof (`Min00 60`) | Roof frame spawns at `(-1995.73, -1723.10, 97.54)` with **no pre-installed core** (`s7 roof confirmed frame_no_core=true`); roof Vertibird Minigun enabled at `(-2004.72, -1715.40, 102.68)`. `0` `WRLD` refs left in `0xBF5` before relocation | `UNPROVEN IN GAME` (`offline PASS`) | `pending` |
| `2i-02` | Activate roof PA frame w/ `0` `Fusion Core`s (`0x000809`) | Frame locks activation (`BlockActivation(True, False)`): `"Fusion Core required to enter Power Armor."`, `s7 roof_frame refused reason=no_fusion_core cores=0` | `UNPROVEN IN GAME` (`offline PASS`) | `pending` |
| `2i-03` | Carry `Fusion Core` (`0x000809`) from S6 -> `[E]` roof PA frame -> `[E]` Vertibird Minigun -> drop to street | Enters PA frame (`s7 roof_frame entered core=0x0809`, completes Obj `95`); Minigun activator hides and grants `1x FO4_Minigun` + `1,200x 5mm` (`count_minigun=1 count_5mm=1200`); `0` fall damage on street landing (`0x00081E` owned by `FO4SF_PowerArmorCoreQuest`) | `UNPROVEN IN GAME` (`offline PASS`) | `pending` |
| `2i-04` | Street drop initiates `Min00 65` `"Clear Concord of Hostiles"` (`DN092 75`, `respawnPool=8`) | Only `WaveRaider01..03` respawn across `0xBEB..0xBF0` (`failsafe 0xBF1` when player blocks spawners); `Gristle` & `RoofLookout` stay dead; no premature S8 completion during `0.5 s` respawn wait (`s8RespawningCount` guard) | `UNPROVEN IN GAME` (`offline PASS`) | `pending` |
| `2i-05` | First of `8` wave kills, `<= 17 m` of grate (`0xBF2`), or `300 s` timer | `DN092` hits `79`; logs `s8 deathclaw spawn trigger=<wave_kills/grate_proximity/timer_300s> dn092_stage=79` (with `deathclaw_slot=empty` if creature slot uninstalled, or `615 HP / 100 DR / 150 ER`) -> clearing wave + bosses sets `Min00 80` (`obj 140`) | `UNPROVEN IN GAME` (`offline PASS`) | `pending` |
| `2i-06` | Re-enter Concord Museum lobby & talk to Preston (`Min00 80`, `TalkUseMessageBox=0`) | Native `DialogueMenu` opens `FO4SF_S9_PrestonLobbyScene` (`0xBF6`, voiced FO4 `.wem` audio, `0` MessageBox) -> grants **`100` Caps + `50` Fusion Cells (`credits=0`)**, sets `DialogueConcordArea=50 -> Min01=20 -> Min00=100`, reveals Diamond City marker (`Min00 150`) | `UNPROVEN IN GAME` (`offline PASS`) | `pending` |
| `2i-07` | Exit Museum with Preston + Minutemen party (`Sturges`, `Mama Murphy`, `Marcy`, `Jun`) & walk north past Red Rocket toward Sanctuary | Party walks Concord -> Red Rocket -> Sanctuary (`SetLinkedRef`); walking ahead `> 65 m` or unloading triggers safe off-screen keeper catches (`never teleported in player view`) | `UNPROVEN IN GAME` (`offline PASS`) | `pending` |
| `2i-08` | Reach Sanctuary -> `Min01 220` Talk to Sturges (`TalkUseMessageBox=0`) -> `Min01 1000` | Native `DialogueMenu` opens `FO4SF_S9_SturgesIntroScene` (`0xBFD`, `001188B4` voiced FO4 `.wem` clips, `0` MessageBox) -> advances `FO4SF_Sanctuary01` to `1000` (`"Build sheltered beds"`) and stops hard (`FO4SF_MinRecruit00` & `FO4SF_MQ103` remain OFF via `0xBF4`) | `UNPROVEN IN GAME` (`offline PASS`) | `pending` |

---

## 6. Claude's Additions (5 Rows — Pending / On-Hold Boundaries)

| Track / ID | Owner / Lane | Status vs Candidate `2i` | Boundary for `2i` |
|---|---|---|---|
| `#854` Robot / Codsworth (`robot-anim`) | Claude animation track | External / separate lane | Codsworth animations untouched; existing S1–S5 Codsworth behaviour inherited from `2h` (`--codsworth-handy` OFF) |
| `#855` Creature / Deathclaw (`creature-anim`) | Claude creature/anim track | Pending Deathclaw creature slot | `S8` fires `trigger=wave_kills, grate_proximity, timer_300s` + stage `79`; logs `deathclaw_slot=empty` cleanly when creature slot absent, or configures `615 HP / 100 DR / 150 ER` when bound |
| `#856` Human & Power Armor Animations | Claude animation track | Pending (`--fo4-human-anims 0`) | `S7` roof PA frame (`0x000801`) uses P2 `fade_equip_standin` + human-skeleton T-45 worn stand-ins until true `#856` PA animations ship |
| Gun Moving Parts (`GunPart` / Minigun) | Claude animation + rig track | Moving barrel/drum/belt nodes preserved in `2h`/P6 assets | True spinning barrel / `GunPart` weapon rig animation deferred; `S7` grants static/rigged `CoreValues` `FO4_Minigun` (`0x0008A0`) via `vertibirdminigun.nif` activator (`Rows 1–5` `.dds` packed in `Main.ba2`) |
| Gun & Power Armor Sounds (`SNDR` Banks) | Audio lane | On hold / Starfield defaults | Weapon & PA `SNDR` banks remain on hold; `S9` Preston Lobby (`0xBF6`) & Sturges Intro (`0xBFD`) dialogue `SCEN`s ship converted FO4 `.wem` voice lines (`00f4c301..04.wem`) |
