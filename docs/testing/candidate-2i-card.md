# Session Card — `candidate-2i-2`: Round 13 `S7`–`S9` Full Story (`candidate-2h-2` `S1`–`S6` + `Concord` Roof PA/Minigun `S7` + `DN092` Wave 2 & Deathclaw `S8` + `S9` Lobby, Walk Home & `Min01` 1000 Hard Stop)

> **Build Profile & Verdict (`24 Nov 2026`):** **`OFFLINE STAGED — UNPROVEN IN GAME`** (`NEW GAME needed`; clean start from Vault 111 required — do NOT load a pre-`2h-2`/`2i-2` save created before `FO4SF_R11FullMission`, `FO4SF_LoadDoorQuest` `09000BDE`, `REFR 09000C0D`, or merged `NAVI` Slot 1 `FO4Port.esm`).
>
> - **Branch & Stacked Scope (`0` merges above `#857` `d3d9d0b7`):** `gemini/r13-w3-864` (`OFFLINE ONLY — UNPROVEN IN GAME`). Inherits full **Slot 1** lossless museum + `NAVI` extension (`NextObjectID=0x00EFAB`, local FormIDs `0x00E200..0x00EFAA`, `<cand2h-port-dir>/FO4Port.esm`) and `S2`–`S6` (`0xB8C..0xBE5`) from `#853`/`#857` (`candidate-2h-2`), adds **`F1`–`F13`** fixes over P2 `FO4SFPowerArmor.esm` (`4b33acea...`) and `S7`–`S9` (`0xBE6..0xC12`) with `StopAtFusionCorePowerArmor = false`.
> - **Optional Flags Held OFF by Default (`#854`/`#855`/`#856` unmerged):** `--r11-full-mission 1`, `--task1b-vault-recovery 1`, **`--fo4-human-anims 0`** (`09000B8E=0.0`, `#856` human-anim race keyword `FO4SF_AnimArchetypeFO4` unlinked), **`--creature-slots` OFF (`empty`)** (`09000B8C=0.0`; Deathclaw `0xC0F` / claw `0xC0E` from FO4 `0002C969` excluded until `creature-slots.json` enables it), **`--codsworth-race-framing 0`**, **`--codsworth-handy` OFF** (`MiniBotARace` Codsworth stand-in from `2h-2`), `09000979` `FO4SF_MissionTalkUseMessageBox = 0.0` (MessageBox fallbacks `0x0990..0x0992` & `0xC04`/`0xC05` unreachable in live dialogue; **zero** silent `direct_no_scene` fallback), `0 WRLD` overrides in `FO4SFMission.esm`.
> - **Single-Archive `4.000 GiB` Asset Scope (`R15` Honesty Disclosure):** `make_core_bundle.py` enforces `< 4.000 GiB` single-`Main.ba2` packing: `02b-mission` packs the P6b arsenal non-texture files + Rows `1`–`5`, ammo, and core item `.dds` textures (matching `candidate-2h-2`; Rows `6`–`20` `.dds` omitted under `4.000 GiB`) **plus** the P2 Power Armor & Vertibird Minigun assets (`vertibirdminigun.nif`, `powerarmorfurniture.nif`, `fusioncore.nif`, PA `.dds`/`.mat`/`.mesh`).
> - **Starfield UI Stand-In Policy (`#32` Owner Direction):** All UI screens (Starfield HUD, Outpost/Workshop builder on the Sanctuary workbench, Novice lockpicking UI, S.P.E.C.I.A.L./Perk menus, DialogueMenu, Pip-Boy item cards) are labelled **Starfield UI stand-ins** until Fallout UI skins replace them; judge them here strictly on **function** (open cleanly, display accurate prompts/counters, never render bare `"."`, never lock up; **`audio: not judged`**).
> - **Resolving Placeholders & Batch Rules (`P3` Zero-`M`/`N`/`V`):** Typed ```` ```console ```` lines and `bat <id>` filenames contain **zero** `m`, `n`, `v` characters (`bat s7r`, `bat s8w`, `bat s9p`, `bat s9q`) and **zero** stripped `FO4SF_*` `GLOB`/`QUST` EditorIDs; every `player.setpos` hop moves **`< 180 m` per axis**.
>   - `<starfield-dir>`: target Steam Starfield root (`>= 60.0 GiB` decimal / `55.88 GiB` free before install; zero edits outside explicit install/rollback steps while game/CK/OBS are closed).
>   - `<cand2i-player-bundle>` / `<cand2i-test-bundle>`: staged `--profile player` (`13` plugins) and `--profile test` (`22` plugins) folders under `<core-tests-root>/candidate-2i-2/`.
>   - `<cand2h-port-dir>`: Slot 1 `FO4Port` folder (`<core-tests-root>/candidate-2h-2/port`, `FO4Port.esm` `8163ca9a...`).
>   - `<mapmarkers-stage-dir>`: staged map markers directory containing `core.json` pinned to `FO4TerrainCore.esm` `dc751664...` (e.g. `mapmarkers_v6i_dark` / `mapmarkers_v6i_reload` / `mapmarkers_v6i_starmap` under `<staging-dir>`, or staged fresh via `python scripts/mapmarkers/make_map_markers.py stage --core <cand2i-player-bundle>/FO4TerrainCore.esm --out <mapmarkers-stage-dir>`).

---

## 1. Staged File Inventory & SHA-256 Receipts (`OFFLINE VERIFIED`)

| Artifact / Stage Component | Bytes | SHA-256 | Notes / Contract |
|---|---:|---|---|
| `<cand2h-port-dir>/FO4Port.esm` | `4,612,735` | `8163ca9a7187bd07fdd09f20ad7c16d511577f91d91c858ed28ec0fc434fef39` | Slot 1 (`0` diffs on `55,071` baseline records from base `07756819...`; `L3` merged `NAVI 0x00000FF1`; `3,500` museum/prewar records `0x0100E200..0x0100EFAA`, `NextObjectID=0x00EFAB`, `0` `WRLD`/`PNDT`) |
| `<cand2h-port-dir>/FO4Port - Main.ba2` | `117,755,711` | `064c762499a1cc975df81da2c12ea3a20aec5f84cae0c89f4d9cdac12d094c7e` | `BTDX` v2 `GNRL` (`17,023` entries; `nlink=1`) |
| `<cand2h-port-dir>/FO4Port - Textures.ba2` | `2,289,478,621` | `f4664dd0a4fb49a3adb17440596bbb936b0ffa47516024be9fff07c7b1a69a48` | `BTDX` v2 `DX10` (`4,711` entries; `nlink=1`) |
| `FO4SFCoreValues.esm` (`player`, `--test-mode 0`) | `76,995` | `5b788a97006cc5e3d97847f9ca6b35a5567d380404356c75b3a8c05e0ff9cb5c` | Inherited from `candidate-2h-2` (`0x000860=0.0`, P6b arsenal + `0x0008A0` Minigun, `0x00089F` 5mm, `0x00089B` Fusion Cell, `0x0008A4` Caps, Row 5 Pipe Guns) |
| `FO4SFCoreValues.esm` (`test`, `--test-mode 1`) | `76,995` | `36cea4072b3ba95201d969c2a323fd07c7acea767ecd21b668600444f5a2f039` | Inherited from `candidate-2h-2` (`0x000860=1.0`) |
| `FO4SFMission.esm` (`02b-mission`) | `128,429` | `0e3ab52aaed34b5a43fd15914c30e519a2e71f122b2c41c02eb1c24abd639012` | **`F1`–`F13`**: `15 QUST` (incl. `0xBDE` `FO4SF_LoadDoor`), `28 NPC_` (F7 `0xC0A`/`0xC0B`/`0xC10` + F7 softened NonPlayable `0xC11`/`0xC12`), `0 WRLD`, F4 renamed `CELL 0xBF5` `"Concord Roof & Wave Staging"` + `0xB60`, F9 `(-1990.58, -1724.19, 97.56)`, F12 `REFR 0xC0D`, `16` `.pex`, `714` Data files (`39` `.wem` incl. `00f4c301..04.wem`, P6b + P2 meshes/textures) |
| `FO4SFNewGame.esm` (`03-newgame`, `player`) | `12,688` | `0163600cbbe974a0344a858ddd483472a59e90b079632b394bac535cbd9d50f2` | Inherited from `candidate-2h-2` (`fade_hold=false`, `vault_death_recovery=autosave`) |
| `FO4SFNewGame.esm` (`03-newgame-fadehold`, `test`) | `12,688` | `5c9edb843ced9eeaf505f8e0fd9255122d6bbbe4248308ccedbb36dbcc9a9e65` | Inherited from `candidate-2h-2` (`fade_hold=true`) |
| `FO4SFVaultGearDoor.esm` (`01-cog-door`) | `597` | `7aada8bafa027bfd158c63e0728e10e7239401dde57429ba601b7b96a2ea8533` | Inherited from `candidate-2h-2` |
| `FO4SFExitLift.esm` (`02-exit-lift`) | `590` | `34d0db71d1116742d5d644a7772e8f31e43019b72bab9d01c91eec308665d9d4` | Inherited from `candidate-2h-2` |
| `FO4SFWorkshop.esm` (`06-workshop`) | `21,237` | `53eb1e1691a9b4b888ded08fc349a38f0407f3aa829130c493ddb08aa2b8ada1` | Inherited from `candidate-2h-2` (`candidate-2g-fix4` parity, non-Localized) |
| `FO4SFPowerArmor.esm` (`player` / `test`) | `85,768` / `87,684` | `4b33acea762e9c3acfc7b4c1a97a106f302c2f908122d8448e1511206653bba0` / `a669c3369cf1d0e828fbdd351e17c03fc26f4755d487742ca084bdf05870612b` | **`F1` P2 rebuild:** `FO4SFPowerArmor.esm` (`4b33acea...` in `player`: `FURN 0x000801` `powerarmorfurniture.nif`, `RACE 0x000802`, `FO4SF_FusionCore 0x000809` -> `0C000809`, `PERK 0x00081E` fall guard, `0` `"FO4SF "` `FULL`s) |
| `FO4SFPipboyMenu.dll` (`sfse_sidecar`) | `1,453,568` | `7d5ba49c0c6ab2aa8db24ab1bfb643839259d12404cc95afaa38e2f42201c9a8` | Tested DLL reused untouched (`ShellBackdrop=1`, `ShellVitalsFill=1`, `SuppressDataMenu=0`, `TabOpensPipboy=0`, `HideStarfieldWatch=1`) |

---

## 2. Preconditions, Reversible `FO4Port` Base-Hash Gate, Install & Rollback Commands (Game Closed)

### Preconditions & `FO4Port` Base-Hash Gate
1. **Processes closed:** `Starfield.exe == 0`, `CreationKit.exe == 0`, `Archive2.exe == 0`. Clean any earlier installed candidate/probe before installing `candidate-2i-2`.
2. **Base `FO4Port.esm` gate (`07756819...`):** Before backing up `<starfield-dir>/Data/FO4Port.*`, verify `<starfield-dir>/Data/FO4Port.esm` matches the unextended animated-doors base SHA-256 `07756819ecf7ab9a88af6421478c7c05f13eb6dbef062a1a61b98ec63e7bbe60` (or verify `<starfield-dir>/Data/FO4Port_pre2i_backup/FO4Port.esm` already holds `07756819...`, or if upgrading cleanly from Slot 1 `candidate-2h-2` `8163ca9a...`, confirm `FO4Port_pre2h_backup/FO4Port.esm` holds `07756819...` and copy/rename that backup first). **Abort swap immediately if the backup source hash is NOT `07756819...`.**
3. **`13`-Plugin `--profile player` Load Order (`Plugins.txt`):** `FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm` (with `<cand2h-port-dir>/FO4Port.*` active in `Data/`).
4. **`22`-Plugin Optional `--profile test` Load Order (`<cand2i-test-bundle>`):** `FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFCoreCandidate.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm` (zero `FO4SFRouteLoot.esm` / `FO4SFBridge.esm`).

```bash
# 1. Verify bundle, F1 P2 PA + ACTI mesh readiness, and lossless Slot 1 FO4Port.esm
python scripts/core/make_core_bundle.py verify --bundle-dir <cand2i-player-bundle> --port <cand2h-port-dir>/FO4Port.esm
python scripts/testing/check_beginning_pilot.py check-bundle --bundle-dir <cand2i-player-bundle>

# 2. Gate FO4Port backup/swap on base SHA-256 07756819ecf7ab9a88af6421478c7c05f13eb6dbef062a1a61b98ec63e7bbe60
BASE_PORT_SHA="07756819ecf7ab9a88af6421478c7c05f13eb6dbef062a1a61b98ec63e7bbe60"
mkdir -p <starfield-dir>/Data/FO4Port_pre2i_backup
if [ ! -f <starfield-dir>/Data/FO4Port_pre2i_backup/FO4Port.esm ]; then
  CUR_SHA=$(sha256sum <starfield-dir>/Data/FO4Port.esm | awk '{print $1}')
  [ "$CUR_SHA" = "$BASE_PORT_SHA" ] || { echo "ABORT: FO4Port.esm is $CUR_SHA, expected base $BASE_PORT_SHA"; exit 1; }
  cp -n <starfield-dir>/Data/FO4Port.esm "<starfield-dir>/Data/FO4Port - Main.ba2" "<starfield-dir>/Data/FO4Port - Textures.ba2" <starfield-dir>/Data/FO4Port_pre2i_backup/
fi
BK_SHA=$(sha256sum <starfield-dir>/Data/FO4Port_pre2i_backup/FO4Port.esm | awk '{print $1}')
[ "$BK_SHA" = "$BASE_PORT_SHA" ] || { echo "ABORT: backup FO4Port.esm is $BK_SHA, expected base $BASE_PORT_SHA"; exit 1; }
cp -f <cand2h-port-dir>/FO4Port.esm "<cand2h-port-dir>/FO4Port - Main.ba2" "<cand2h-port-dir>/FO4Port - Textures.ba2" <starfield-dir>/Data/

# 3. Install 13-plugin player bundle + SFSE sidecar + map markers (--dir, NOT --stage) + P3 batches
python scripts/game/exp_install.py install --exp-dir <cand2i-player-bundle> --starfield <starfield-dir> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
python scripts/core/make_core_bundle.py sidecar-install --bundle-dir <cand2i-player-bundle> --starfield <starfield-dir>
python scripts/game/map_markers_install.py install --dir <mapmarkers-stage-dir> --starfield <starfield-dir>
cp -f <cand2i-player-bundle>/bat/*.txt <starfield-dir>/
```

### Exact Undo / Rollback Command (Game Closed — Restores `07756819...` `FO4Port.*` + Clean `Starfield/Data`)

```bash
rm -f <starfield-dir>/h2st.txt <starfield-dir>/h2h2.txt <starfield-dir>/h2h3.txt <starfield-dir>/h2h4.txt <starfield-dir>/h2f.txt <starfield-dir>/h2b.txt <starfield-dir>/h2k.txt <starfield-dir>/h2p.txt <starfield-dir>/h2r.txt <starfield-dir>/s7r.txt <starfield-dir>/s8w.txt <starfield-dir>/s9p.txt <starfield-dir>/s9q.txt
python scripts/core/make_core_bundle.py sidecar-undo --starfield <starfield-dir>
python scripts/game/plugin_toggle.py on --starfield <starfield-dir>
python scripts/game/map_markers_install.py uninstall --starfield <starfield-dir>
python scripts/game/exp_install.py uninstall --starfield <starfield-dir>
cp -f <starfield-dir>/Data/FO4Port_pre2i_backup/FO4Port.esm "<starfield-dir>/Data/FO4Port_pre2i_backup/FO4Port - Main.ba2" "<starfield-dir>/Data/FO4Port_pre2i_backup/FO4Port - Textures.ba2" <starfield-dir>/Data/
rm -rf <starfield-dir>/Data/FO4Port_pre2i_backup
```

---

## 3. `S7`–`S9` FormIDs & Holding Cell Layout (`FO4SFMission.esm` `0xBE6..0xC12`)

- **`0xBF5` (`CELL FO4SF_S7S9_HoldingCell`, `FULL`: `"Concord Roof & Wave Staging"`):** `IsInteriorCell` holding cell (`0` `WRLD` overrides, zero `"FO4SF "` or `"(Stand-In)"` `FULL` strings across staged plugins). Persistent `S7`/`S8` refs start in `0xBF5` and relocate to merged Concord coords at runtime via `0x005C50` / `0x0A775B`.
- **`S7` Roof (`0xC06..0xC09`, `0xC0C..0xC0D` + `FO4SFPowerArmor.esm`):**
  - `0xC06` `FO4SF_S7_RoofMinigunActi` (`ACTI`, `vertibirdminigun.nif`, `"Vertibird Minigun"`), `0xC07` persistent roof minigun `REFR` (`(-2004.72, -1715.40, 102.68)`).
  - `0xC0C` `FO4SF_S7_RoofFrameFurn` (`FURN`, `powerarmorfurniture.nif`, `"Power Armor"`), **`0xC0D` `FO4SF_S7_RoofFrameRef`** persistent `REFR` relocated onto `0xC08` `S7RoofFrameMarker` (`(-1995.73, -1723.10, 97.54)`, zero `PlaceAtMe`, invokes `FO4SF_PowerArmorCoreQuest.EnterFrame` on `0x000805`).
  - `0xC09` `S7RoofDoorMarker` at FO4 `0002C1C6` landing **`(-1990.58, -1724.19, 97.56)`**.
  - Grants `1x FO4_Minigun` (`060008A0`) + `1,200x FO4_Ammo5mm` (`0600089F`). Zero fall damage perk (`0x00081E`) is owned by P2 `FO4SFPowerArmor.esm`; `s7 street_drop` logs real `hp_before=`, `hp_after=`, and `dmg=`; roof frame blocks (`BlockActivation(True, False)`) when held `FO4SF_FusionCore` (`0C000809` in `player`, local `0x000809`) count `== 0`, and completes Obj `95` when activated with `cores > 0`.
- **`S8` Concord Wave 2 & Deathclaw (`0xBE6..0xBF3`, `0xC0A..0xC0B`, `0xC0E..0xC12`):**
  - `F7` NPCs & softened NonPlayable weapons: `0xC10` `FO4_LvlRaiderBoltAction` (from `000CE987`, equips `0xC11` `FO4SF_WaveRaiderBoltWeapon` `6.0` dmg, `0x988` FO4 outfit), `0xC0B` `FO4_WaveRaiderHeavy` (from `0007B620`, equips `0xC12` `FO4SF_WaveRaiderHeavyWeapon` `2.0` dmg, `0x988` outfit), `0xC0A` `FO4_Gristle` (from `00019567`, non-essential/non-respawning boss, `85 HP`, `15 DR`, `0xC12` weapon).
  - `0xBE6..0xBEA`: `5` persistent wave `ACHR`s (`WaveRaider01..03`, `RoofLookout`, `Gristle`); `0xBEB..0xBF0`: `6` `DN092WaveSpawner01..06` markers; `0xBF1`: `DN092_WavePost02` failsafe; `0xBF2`: grate trigger (`<= 17 m`); `0xBF3`: `ConcordAmbushDeathclaw` spawn (`(-2068.22, -1640.18, 88.22)`).
  - `F3` Creature Slot (behind `--creature-slots`, default OFF): `0xC0E` `FO4SF_S8_DeathclawClawWeap` (`AttackDamage=60`) + `0xC0F` `FO4SF_S8_DeathclawNpc` (from FO4 `0002C969`, `615 HP / 100 DR / 150 ER`, claw attack) built cleanly when `creature-slots.json` enables it.
  - `F8` / `F12`: Deathclaw trigger sets `DN092` stage **`77`** (NOT `79`) so `WaveRaider01..03` keep respawning via fresh `PlaceAtMe` at unseen spawners (`respawnPool = 8`, zero `Resurrect()`); `DN092` hits `79` on Deathclaw defeat when bound, OR ONLY on the **`300 s` timer** when `deathclaw_slot=empty`.
- **`S9` Real Starfield `SCEN`s, Exterior Patrol, Lobby Reward & `Min01` 1000 Hard Stop (`0xBF4`, `0xBF6..0xC05`):**
  - `0xBF6` `FO4SF_S9_PrestonLobbyScene` (`Min00 80 -> 90`, Alias `0`, FO4 `.wem` audio `00f4c301..02.wem`); `F13`: rewards (`100` Caps `060008A4` + `50` Fusion Cells `0600089B`, `credits=0`, sets `DialogueConcordArea 50 -> Min01 20 -> Min00 100`, Diamond City marker `150`) pay **ONLY** when reply completes (`stage 90`), logging `s9 lobby scene cancelled_early ... reward=0` on early escape/close. MessageBox `0xC04` strictly behind `TalkUseMessageBox != 0`.
  - `F2`: Patrol move-to-front (`DeployS9PatrolExterior`) waits until `!player.IsInInterior() && IsCommonwealthExterior(player)` (logs `min01 patrol deferred_until_exterior=true` while still in lobby), then moves Preston + all `4` settlers (`Sturges`, `Mama Murphy`, `Marcy`, `Jun`) outside the front door and chains `S9PatrolWaypoints` outdoors; keeper failsafe checks **all** `MinutemenGroup` members so nobody teleports in player view.
  - `F5` / `F6` / `F13` `Min01`: While `0xBF4` (`FO4SF_S9_HardStopAtMin01_1000 = 1.0`) is set, `FO4SF_Sanctuary01` (`09000817`) initializes quietly at stage `20` (no premature Objective `10` workbench prompt in Concord), ignores workbench activations `< 220`, routes Sturges at `220` strictly through `0xBFD` `FO4SF_S9_SturgesIntroScene` (`001188B4`, FO4 `.wem` audio `00f4c303..04.wem`), refuses `direct_no_scene` (`ERROR` log instead), and sets stage **`1000`** with Fallout 4's `"Build sheltered beds for Sanctuary settlers (<Global=FO4SF_Min01BedPercent>%)"` while keeping `FO4SF_MinRecruit00` & `FO4SF_MQ103` OFF.

---

## 4. Emitted `P3`-Clean Console & Batch Checks (`Zero M/N/V`, `< 180 m`/Axis)

`make_mission.py stage` emits `s7r.txt`, `s8w.txt`, `s9p.txt`, and `s9q.txt` alongside `h2*.txt` into `<cand2i-player-bundle>/bat/` (installed to `<starfield-dir>/`):

````console
bat s7r
bat s8w
bat s9p
bat s9q
````

```bat
; <starfield-dir>/s7r.txt — S7 Concord Museum roof Power Armor & Vertibird Minigun inspection spot (near FO4 0002C1C6 roof landing)
player.setpos x -1997.50
player.setpos y -1721.50
player.setpos z 97.80
player.setangle z 310

; <starfield-dir>/s8w.txt — S8 Concord street DN092 Wave 2 & Deathclaw grate inspection (-2068.22, -1640.23, 88.22; outdoors in Concord)
player.setpos x -2048.00
player.setpos y -1662.00
player.setpos z 88.80
player.setangle z 315

; <starfield-dir>/s9p.txt — S9 Concord exit -> Red Rocket patrol corridor midpoint (< 115 m hop outdoors)
player.setpos x -2105.00
player.setpos y -1625.00
player.setpos z 94.00
player.setangle z 315

; <starfield-dir>/s9q.txt — S9 Red Rocket North -> Sanctuary Hills workbench & Sturges arrival (< 156 m hop from Red Rocket North)
player.setpos x -2325.00
player.setpos y -1425.00
player.setpos z 112.50
player.setangle z 30
```

---

## 5. Verification Matrix (`VIDEO` Required — All Offline Verified, Unproven in Game)

| Check ID | Stage / Trigger | Expected In-Game & `fo4sf_mission.0.log` Behaviour | Result | VIDEO |
|---|---|---|---|---|
| `2i-01` | Play S1–S6 -> grab `Fusion Core` (`0C000809`) -> exit roof door (`Min00 60`) -> stand on bulkhead (`(-1990.58, -1724.19, 97.56)`) | Lands solidly on roof bulkhead (`z ~ 97.56`, ZERO drop off roof); persistent frame `09000C0D` placed on `(-1995.73, -1723.10, 97.54)` (`powerarmorfurniture.nif`, zero pre-installed core); `vertibirdminigun.nif` (`09000C07`) visible & clickable (`s7 roof confirmed frame_no_core=true frame_persistent=true minigun_enabled=true`); zero `"FO4SF "` player-facing names on Fusion Core or cells | `UNPROVEN IN GAME` (`offline PASS`) | `cand2i-01-roof-arrival`: `>= 8 s` roof exit -> pan across bulkhead, `powerarmorfurniture.nif`, & `vertibirdminigun.nif`; at `1 fps`, **PASS** if player stands on bulkhead `z~97.56` with real PA frame & minigun meshes visible; **FAIL** if falling to street `z~88`, invisible/chair frame, or marker box; **`audio: not judged`**. |
| `2i-02` | Activate roof PA frame (`09000C0D`) w/ `0` `Fusion Core`s (`0C000809`) | Frame locks activation (`BlockActivation(True, False)`), displays HUD notice `"Fusion Core required to enter Power Armor."`, logs `s7 roof_frame refused reason=no_fusion_core cores=0 frame_blocked=true` | `UNPROVEN IN GAME` (`offline PASS`) | `cand2i-02-pa-nocore-gate`: `>= 5 s` aiming & pressing `E` on `09000C0D` with 0 cores; at `1 fps`, **PASS** if entry stays locked with HUD refusal message; **FAIL** if player enters without a core or UI hangs; **`audio: not judged`**. |
| `2i-03` | Carry `0C000809` Fusion Core -> **`press E`** roof PA frame (`09000C0D`) -> **`press E`** Vertibird Minigun (`09000C07`) -> drop to street | Enters PA via `0x000805` `EnterFrame` (`s7 roof_frame entered core=0x0809`, completes Obj `95`); minigun grants `1x FO4_Minigun` (`060008A0`) + `1,200x 5mm` (`0600089F`); armored street drop (`no_fall_perk=true` `0x00081E`) logs real `hp_before=` / `hp_after=` / `dmg=` (`dmg=0` unhurt) | `UNPROVEN IN GAME` (`offline PASS`) | `cand2i-03-pa-enter-drop`: `>= 10 s` PA entry fade + minigun grab + roof-to-street drop HUD HP bar; at `1 fps`, **PASS** if PA equips, HUD stays full HP on landing, and Minigun enters inventory; **FAIL** if HP drops on landing or minigun lacks prompt; **`audio: not judged`**; equip fade **`needs a slowed take`**. |
| `2i-04` | Equip & fire `FO4_Minigun` (`060008A0`) with `1,200x 5mm` (`0600089F`) in Concord street combat | `fo4_minigun.nif` renders in 1st/3rd person, fires `5mm` projectiles at Wave 2 raiders, decrements `1,200` 5mm count, deals real combat damage (`count_minigun=1`, non-jamming firing loop) | `UNPROVEN IN GAME` (`offline PASS`) | `cand2i-04-minigun-fires`: `>= 8 s` equipping & sustained firing `FO4_Minigun` into street wave; at `1 fps`, **PASS** if visible minigun model muzzle-flashes/impacts & `5mm` ammo decreases; **FAIL** if weapon invisible, refuses to fire, or freezes; **`audio: not judged`**; barrel/bolt frames **`needs a slowed take`**. |
| `2i-05` | `Min00 65` `"Clear Concord of Hostiles"` (`DN092 75`, `respawnPool=8`): fight `F7` Wave 2 raiders | `WaveRaider01..03` respawn via fresh out-of-view `PlaceAtMe` (`s8 wave respawn idx=... fresh=true spawner=...`, zero `Resurrect()`), carrying softened `0xC11`/`0xC12` weapons + FO4 outfits; `RoofLookout` & `Gristle` stay dead; no premature finish during respawn | `UNPROVEN IN GAME` (`offline PASS`) | `cand2i-05-wave2-respawns`: `>= 15 s` street Wave 2 firefight + inspecting `Gristle`/`WaveRaider` corpses; at `1 fps`, **PASS** if wave wear FO4 clothes, HP remains manageable, and no corpse visibly pops back in front of camera; **FAIL** if corpse resurrects on screen or player dies unfairly fast; **`audio: not judged`**. |
| `2i-06` | `F8` Deathclaw gate & `Deathclaw` dies / `300 s` slot parity (`<= 17 m` grate `0xBF2`, `8` wave kills, or `300 s`) | Trigger logs `s8 deathclaw spawn trigger=<...> dn092_stage=77` (NOT `79`; pool stays open until `79`!); **with `--creature-slots` ON:** `0xC0F` (`615 HP / 100 DR / 150 ER`, `60` claw dmg) spawns from grate and killing it logs `s8 deathclaw defeated dn092_stage=79`; **with default empty slot:** stays `77` waiting (`waiting_timer=300s`), completes `79` ONLY at `300 s` (`timer_300s_complete`); clearing all sets `Min00 80` (`obj 140`) | `UNPROVEN IN GAME` (`offline PASS`) | `cand2i-06-deathclaw-dies`: `>= 10 s` grate trigger -> Deathclaw fight & death killfeed (`--creature-slots` run) OR `300 s` completion log HUD (`default empty` run); at `1 fps`, **PASS** if objective `65` completes into `obj 140` (`Return to Preston`) cleanly after stage `79`; **FAIL** if `79` fires early before `300 s` (empty) or Deathclaw unkillable/absent (bound); **`audio: not judged`**. |
| `2i-07` | Cold reload inside Concord / Museum (`Throwaway_2i_Concord` -> `Quit to Desktop` -> relaunch -> load save -> exit/continue) | `OnPlayerLoadGame` logs `FO4SF_LOADDOOR reload_ready`, restores S7/S8/S9 state cleanly without duplicating rewards or hanging Museum front/roof doors (`confirmed core_cell=true`), and completes deferred patrol deploy when stepping outdoors if saved post-lobby | `UNPROVEN IN GAME` (`offline PASS`) | `cand2i-07-cold-reload`: `>= 8 s` after save load -> exiting Museum door / verifying Concord mission continuity; at `1 fps`, **PASS** if door transitions cleanly to `z~88 m` street and patrol/quest stage matches pre-quit state; **FAIL** if door hangs on `activate_begin` or resets stage/rewards; **`audio: not judged`**. |
| `2i-08` | Re-enter Museum lobby (`Min00 80`) -> test **early cancel** then **complete** Preston Lobby `SCEN` (`0xBF6`) | Early `Esc`/close before stage `90` logs `cancelled_early ... reward=0` (`0` caps/cells paid!); completing `0xBF6` DialogueMenu opens real choices + VO (`0` MessageBox), grants **`100` Caps + `50` Fusion Cells (`credits=0`)**, sets `DialogueConcordArea 50 -> Min01 20 -> Min00 100`, reveals Diamond City (`150`); logs **`min01 patrol deferred_until_exterior=true`** inside lobby (never moves settlers indoors!) | `UNPROVEN IN GAME` (`offline PASS`) | `cand2i-08-lobby-scen-f2-f13`: `>= 12 s` early escape check + full `DialogueMenu` choice + inventory `Caps`/`Fusion Cell` popup; at `1 fps`, **PASS** if escape pays nothing and full choice opens Lobby DialogueMenu & pays `100` Caps / `50` Cells with `0` MessageBox; **FAIL** if MessageBox pops up, early cancel rewards, or settlers vanish indoors before exit; **`audio: not judged`**. |
| `2i-09` | Exit Museum front door outdoors -> walk with Preston + `4` settlers (`Sturges`, `Murphy`, `Marcy`, `Jun`) past Red Rocket -> Sanctuary (`bat s9p` / `bat s9q` optional hops) | On first outdoor tick, logs `min01 museum_exit moveto_front=true` + `min01 patrol deployed_outdoors=true`; all `5` walk Red Rocket -> Sanctuary; walking ahead triggers `unloaded_failsafe` ONLY when **every** member failsafe check is off-screen (`> 65 m` or unloaded); arrival sets `Min01 220` (`Sanctuary01`) | `UNPROVEN IN GAME` (`offline PASS`) | `cand2i-09-patrol-walk-home`: `>= 15 s` Museum exit spawn + Red Rocket corridor follow + Sanctuary arrival; at `1 fps`, **PASS** if Preston + all 4 settlers emerge outside front door and walk north cleanly with zero mid-screen pops; **FAIL** if spawned indoors, stuck behind, or teleported in view; **`audio: not judged`**. |
| `2i-10` | Before `Min01 220`: test Sanctuary workbench -> Reach Sanctuary `Min01 220` -> **`press E`** Sturges (`0xBFD`) -> verify `Min01 1000` & **Zero Fallback** audit | `Sanctuary01` shows **0** Obj `10` in Concord lobby, ignores workbench `< 220`; at `220` Sturges opens `0xBFD` `FO4SF_S9_SturgesIntroScene` (`001188B4`, zero `MESG 0xA10`, zero `direct_no_scene`), sets **`1000`** **`"Build sheltered beds for Sanctuary settlers (0%)"`** (`FO4SF_Min01BedPercent` global), and holds `MinRecruit00` & `MQ103` OFF (`0xBF4`); **`0`** `fallback=messagebox` / `by=fallback` / `direct_no_scene` across full `fo4sf_mission.0.log` | `UNPROVEN IN GAME` (`offline PASS`) | `cand2i-10-sturges-1000-zerofb`: `>= 10 s` Sturges `DialogueMenu` -> HUD objective `"Build sheltered beds for Sanctuary settlers (0%)"` -> Missions screen (`MinRecruit00`/`MQ103` absent); at `1 fps`, **PASS** if HUD matches FO4 text and `DialogueMenu` completes into hard stop with zero MessageBoxes; **FAIL** if premature Obj `10`, `"Provide sheltered beds (5)"`, MessageBox popup, or `MinRecruit00` starts; **`audio: not judged`**. |

---

## 6. Claude's Additions (5 Rows — Built-In / Gated / Not Applicable Boundaries)

| Track / Addition | Owner / Lane | Status in `candidate-2i-2` | Boundary & Exact Contract | VIDEO |
|---|---|---|---|---|
| **Robot animations & `#854` Codsworth (`robot-anim`)** | Claude animation track | **`gated`** *(gated on `#854` `--codsworth-handy` & `--codsworth-race-framing 1`)* | Built with `--codsworth-handy` OFF & `--codsworth-race-framing 0`; Codsworth stays the **`MiniBotARace` stand-in** inherited from `2h-2` across `S1`–`S5` (zero `S1` Pre-War overlap). | Reuse `cand2h-2` `sanctuary-codsworth-s3`: `>= 5 s` Codsworth framing; **PASS** if stand-in frames cleanly without clipping; **FAIL** if camera clips; **`audio: not judged`**. |
| **Creature animations & `#855` Deathclaw (`creature-anim`)** | Claude creature/anim track | **`gated`** *(gated on `--creature-slots` `creature-slots.json` `ready=true` / `FO4SFCreatures.esm`)* | `F3` offline Deathclaw `NPC_` (`0xC0F` from `0002C969`, `615 HP / 100 DR / 150 ER`) + claw `WEAP` (`0xC0E`, `60` dmg) are wired behind `--creature-slots`; **default bundle leaves slot OFF (`empty`, `09000B8C=0.0`)**, holding `DN092` at `77` until `300 s` `timer_300s_complete` (`79`). | `cand2i-06-deathclaw-dies`: `>= 10 s` (`--creature-slots` bound kill OR default `300 s` completion); **PASS** per row `2i-06`; **FAIL** on early `79` or broken unskinned placeholder; **`audio: not judged`**. |
| **Human & Power Armor animations (`#856` `human-anim`)** | Claude animation track | **`gated`** *(gated on `#856` `--fo4-human-anims 1` / `FO4SFHumanAnims.esm`)* | `--fo4-human-anims 0` (`09000B8E=0.0`) keeps `#856`'s human-anim race keyword (`FO4SF_AnimArchetypeFO4`) OFF; `S7` PA frame (`0x000801` / `0xC0D`) uses P2 `fade_equip_standin` + human-skeleton T-45 stand-ins, while wave raiders wear FO4 clothes (`0x988`) & Sanctuary settlers wear labelled `Settler Clothes` stand-ins. | `cand2i-03-pa-enter-drop` & `cand2i-09-patrol-walk-home`: `>= 8 s` PA equip & settler walk; **PASS** if zero T-poses or spacesuits; **FAIL** if NPCs wear spacesuits or freeze; **`audio: not judged`**. |
| **Gun moving parts (`GunPart` / `MiscA01` / Minigun)** | `#32` (`Gun_*.af` rig) + `P2`/`P6b` assets | **`built in`** *(consumes P6b + P2 minigun assets inside `02b-mission`)* | Packs `fo4_minigun.nif` (`MiscA01` barrel + `Magazine` drum) & `vertibirdminigun.nif` + P6b Row `1`–`5`/ammo meshes/textures in single `< 4.000 GiB` `Main.ba2`; weapon-anim rig itself remains Starfield default when `Gun_*.af` is absent. | `cand2i-04-minigun-fires`: `>= 8 s` equipping & firing `FO4_Minigun`; **PASS** if visible minigun model renders & fires `5mm`; **FAIL** if invisible mesh or firing stall; **`audio: not judged`**; moving barrel inspection **`needs a slowed take`**. |
| **Gun & Power Armor sounds (`SNDR` banks)** | Audio lane (`#32` sound-bank hold) | **`not applicable`** *(on hold — retained Starfield `SNDR` stand-ins)* | Zero `.afx` or `WAUD` banks modified; all `FO4SFCoreValues.esm`, wave weapons (`0xC11`/`0xC12`), and PA events keep Starfield `SNDR` defaults while `S9` Lobby (`0xBF6`) & Sturges (`0xBFD`) `SCEN`s ship converted FO4 `.wem` voice clips (`00f4c301..04.wem`). | All captures (`>= 3 s`): **`audio: not judged`** on weapon/PA SFX across every capture; **`needs a slowed take`** does not apply to audio calibration. |
