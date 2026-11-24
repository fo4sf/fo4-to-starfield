# Candidate 2i — Round 11 `S7`–`S9` Full Story (`Concord` Roof -> `DN092` Wave 2 & Deathclaw -> `S9` Lobby, Walk Home & `Min01` 1000 Hard Stop) Test Card

> **NEW GAME needed (`A16` / `R15`):** Start a **NEW GAME** after folding `--r11-full-mission 1` `FO4SFMission.esm` onto the cleared `candidate-2h` bundle (`FO4SFCoreValues.esm`, `FO4SFPowerArmor.esm`, `FO4TerrainCore.esm`, `FO4ActorRaider.esm`, tested `FO4SFPipboyMenu.dll` with `MapBlockStarMap=0`, `FO4SFBridge.esm` & `FO4SFRouteLoot.esm` OFF).
> **Bundle Status:** `TEST-STATION` (`OFFLINE ONLY — UNPROVEN IN GAME`) until owner playtest / OBS recording (`VIDEO` column below). Code branch `gemini/round11-s7-s9-2i` (`0` merge commits above base) stacks cleanly onto finished `candidate-2h` (`S2`–`S6`).
> **P3 Console Rules:** Typed ```` ```console ```` lines and `bat <id>` filenames contain **zero** `m`, `n`, `v` characters (`bat s7r`, `bat s7f`, `bat s8w`, `bat s9p`, `bat s9q`) and **zero** stripped `FO4SF_*` `GLOB`/`QUST` EditorIDs. Every `setpos` hop moves **`< 180 m` per axis**.

---

## 1. Install, Fold & Exact Undo Commands (`<STARFIELD_DIR>`, Game Closed)

Stage Placeholders: `<CAND2H_BUNDLE_DIR>`, `<MISSION_2I_STAGE_DIR>`, `<CAND2I_FOLDED_DIR>`, `<STARFIELD_DIR>`.

```powershell
python scripts/mission/make_mission.py fold --mission <MISSION_2I_STAGE_DIR> --core-dir <CAND2H_BUNDLE_DIR> --out <CAND2I_FOLDED_DIR>
python scripts/mission/make_mission.py verify --exp-dir <CAND2I_FOLDED_DIR> --plan <MISSION_2I_STAGE_DIR>/plan.json
python scripts/game/exp_install.py install --exp-dir <CAND2I_FOLDED_DIR> --starfield <STARFIELD_DIR> --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFCoreValues.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFMission.esm,FO4SFNewGame.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFFortHagen.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack
# Exact Undo (Game Closed):
python scripts/game/exp_install.py uninstall --starfield <STARFIELD_DIR>
```

---

## 2. S7–S9 Key FormIDs & Holding Cell Layout (`FO4SFMission.esm` `0xBE0..0xC05`)

- **`0xBF5` (`CELL FO4SF_S7S9_HoldingCell`):** Dedicated `IsInteriorCell` holding cell (`0` `WRLD` overrides added by S7–S9). Persistent S7/S8 refs start in `0xBF5` and relocate to merged Concord coords at runtime via `0x005C50` / `0x0A775B`.
- **`S7` Roof (`0xBE0..0xBE3` + `FO4SFPowerArmor.esm`):** `0xBE0` `Vertibird Minigun` `ACTI`, `0xBE1` persistent roof minigun ref (`(-2004.72, -1715.40, 102.68)`), `0xBE2` `S7RoofFrameMarker` (`(-1995.73, -1723.10, 97.54)` spawning coreless `FURN 0x000801`), `0xBE3` `S7RoofDoorMarker` (`(-2008.49, -1722.39, 97.42)`). Grants `1x FO4_Minigun` (`0x0008A0`) + `1,200x FO4_Ammo5mm` (`0x00089F`). Zero fall damage perk is owned solely by `FO4SF_PowerArmorCoreQuest` on PA enter/exit (`0x00081E`); roof frame activation locks (`BlockActivation(True)`) while player holds `0` `FO4SF_FusionCore` (`0x000809`) items.
- **`S8` Concord Wave 2 & Deathclaw (`0xBE4..0xBF3`):** `0xBE4` `FO4_Gristle` (non-essential/non-respawning boss), `0xBE5` `FO4_WaveRaiderHeavy`, `0xBE6..0xBEA` 5 persistent wave `ACHR`s (`WaveRaider01..03`, `RoofLookout`, `Gristle`), `0xBEB..0xBF0` 6 `DN092WaveSpawner01..06` markers, `0xBF1` failsafe `DN092_WavePost02`, `0xBF2` grate trigger (`<= 17 m`), `0xBF3` `ConcordAmbushDeathclaw` spawn (`(-2068.22, -1640.18, 88.22)`). `respawnPool = 8` respawns only `WaveRaider01..03` between `DN092` `75..79`; `s8RespawningCount` prevents premature completion during `0.5 s` respawn wait.
- **`S9` Real Starfield `SCEN`s, Lobby Reward, Patrol Walk & `Min01` 1000 Hard Stop (`0xBF4`, `0xBF6..0xC05`):**
  - `0xBF6` `FO4SF_S9_PrestonLobbyScene` (`DEVT` Starfield `SCEN` on `FO4SF_Min00` stage `80`, Alias `0`) with FO4 `.wem` audio (`0x00F4C301..2`). MessageBox `0xC04` strictly gated behind `TalkUseMessageBox != 0`.
  - Rewards `100` `Caps` (`FO4SFCoreValues.esm:0x0008A4`) + `50` `Fusion Cells` (`0x00089B`), **`0` Starfield `Credits`**. Sets `DialogueConcordArea 50 -> Min01 20 -> Min00 100`, reveals Diamond City map marker (`150`).
  - Patrol walk home past Red Rocket to Sanctuary using `SetLinkedRef` + keeper failsafe that **never teleports in player view** (`> 65 m` or unloaded cell only).
  - Arriving in Sanctuary sets `FO4SF_Sanctuary01` (`0x817`, `HasDialogueData`) to stage `220`; `0xBFD` `FO4SF_S9_SturgesIntroScene` (`Min01SturgesIntro 001188B4` Starfield `SCEN`, Alias `1`) with FO4 Sturges `.wem` clips (`0x00F4C303..4`) advances to stage `1000` (`"Build sheltered beds"`). Fallback MessageBox `0xC05` gated behind `TalkUseMessageBox != 0`.
  - `0xBF4` `FO4SF_S9_HardStopAtMin01_1000` (`1.0`) holds `FO4SF_MinRecruit00` & `FO4SF_MQ103` strictly OFF at hard stop.

---

## 3. Diagnostic Console & Batch Checks (`P3`-Clean: Zero `M`/`N`/`V`, `< 180 m`/Axis)

Optional P3-clean batches (`bat s7r`, `bat s7f`, `bat s8w`, `bat s9p`, `bat s9q`) use numeric FormIDs only (never stripped `FO4SF_*` `GLOB`/`QUST` EditorIDs):

```console
bat s7r
bat s8w
bat s9p
bat s9q
```

---

## 4. Verification Matrix (`VIDEO` Required — All Offline Verified, Unproven in Game)

| Check ID | Stage / Trigger | Expected In-Game & `fo4sf_mission.0.log` Behaviour | Result | VIDEO |
|---|---|---|---|---|
| `2i-01` | Play S1–S6 (`candidate-2h`) -> enter Concord Museum -> exit to roof (`Min00 60`) | Roof frame spawns at `(-1995.73, -1723.10, 97.54)` with **no pre-installed core** (`s7 roof confirmed frame_no_core=true`); roof Vertibird Minigun enabled at `(-2004.72, -1715.40, 102.68)`. `0` `WRLD` refs left in `0xBF5` before relocation | `UNPROVEN IN GAME` (`offline PASS`) | `pending` |
| `2i-02` | Activate roof PA frame w/ `0` `Fusion Core`s (`0x000809`) | Frame locks activation (`BlockActivation(True, False)`): `"Fusion Core required to enter Power Armor."`, `s7 roof_frame refused reason=no_fusion_core cores=0` | `UNPROVEN IN GAME` (`offline PASS`) | `pending` |
| `2i-03` | Carry `Fusion Core` (`0x000809`) from S6 -> `[E]` roof PA frame -> `[E]` Vertibird Minigun -> drop to street | Enters PA frame (`s7 roof_frame entered core=0x0809`); Minigun activator hides and grants `1x FO4_Minigun` + `1,200x 5mm` (`count_minigun=1 count_5mm=1200`); `0` fall damage on street landing (`0x00081E` owned by `FO4SF_PowerArmorCoreQuest`) | `UNPROVEN IN GAME` (`offline PASS`) | `pending` |
| `2i-04` | Street drop initiates `Min00 65` `"Clear Concord of Hostiles"` (`DN092 75`, `respawnPool=8`) | Only `WaveRaider01..03` respawn across `0xBEB..0xBF0` (`failsafe 0xBF1` when player blocks spawners); `Gristle` & `RoofLookout` stay dead; no premature S8 completion during `0.5 s` respawn wait (`s8RespawningCount` guard) | `UNPROVEN IN GAME` (`offline PASS`) | `pending` |
| `2i-05` | First of `8` wave kills, `<= 17 m` of grate (`0xBF2`), or `300 s` timer | `DN092` hits `79`; logs `s8 deathclaw spawn trigger=<wave_kills/grate_proximity/timer_300s> dn092_stage=79` (with `deathclaw_slot=empty` if creature slot uninstalled, or `615 HP / 100 DR / 150 ER`) -> clearing wave + bosses sets `Min00 80` (`obj 140`) | `UNPROVEN IN GAME` (`offline PASS`) | `pending` |
| `2i-06` | Re-enter Concord Museum lobby & talk to Preston (`Min00 80`, `TalkUseMessageBox=0`) | Native `DialogueMenu` opens `FO4SF_S9_PrestonLobbyScene` (`0xBF6`, voiced FO4 `.wem` audio, `0` MessageBox) -> grants **`100` Caps + `50` Fusion Cells (`credits=0`)**, sets `DialogueConcordArea=50 -> Min01=20 -> Min00=100`, reveals Diamond City marker (`Min00 150`) | `UNPROVEN IN GAME` (`offline PASS`) | `pending` |
| `2i-07` | Exit Museum with Preston + Minutemen party & walk north past Red Rocket toward Sanctuary | Party walks Concord -> Red Rocket -> Sanctuary (`SetLinkedRef`); walking ahead `> 65 m` or unloading triggers safe off-screen keeper catches (`never teleported in player view`) | `UNPROVEN IN GAME` (`offline PASS`) | `pending` |
| `2i-08` | Reach Sanctuary -> `Min01 220` Talk to Sturges (`TalkUseMessageBox=0`) -> `Min01 1000` | Native `DialogueMenu` opens `FO4SF_S9_SturgesIntroScene` (`0xBFD`, `001188B4` voiced FO4 `.wem` clips, `0` MessageBox) -> advances `FO4SF_Sanctuary01` to `1000` (`"Build sheltered beds"`) and stops hard (`FO4SF_MinRecruit00` & `FO4SF_MQ103` remain OFF via `0xBF4`) | `UNPROVEN IN GAME` (`offline PASS`) | `pending` |

---

## 5. Claude's Additions (Pending / On-Hold Boundaries)

| Track / ID | Owner / Lane | Status vs Candidate `2i` | Boundary for `2i` |
|---|---|---|---|
| `#854` Robot / Codsworth (`robot-anim`) | Claude animation track | External / separate lane | Codsworth animations untouched; existing S1–S5 Codsworth behaviour inherited from `2h` |
| `#855` Creature / Deathclaw (`creature-anim`) | Claude creature/anim track | Pending Deathclaw creature slot | `S8` fires `trigger=wave_kills, grate_proximity, timer_300s` + stage `79`; logs `deathclaw_slot=empty` cleanly when creature slot absent, or configures `615 HP / 100 DR / 150 ER` when bound |
| `#856` Human & Power Armor Animations | Claude animation track | Pending | `S7` roof PA frame (`0x000801`) uses P2 `fade_equip_standin` + human-skeleton T-45 worn stand-ins until true `#856` PA animations ship |
| Gun Moving Parts (`GunPart` / Minigun) | Claude animation + rig track | Moving barrel/drum/belt nodes preserved in `2h`/P6 assets | True spinning barrel / `GunPart` weapon rig animation deferred; `S7` grants static/rigged `CoreValues` `FO4_Minigun` (`0x0008A0`) via `vertibirdminigun.nif` activator |
| Gun & Power Armor Sounds (`SNDR` Banks) | Audio lane | On hold / Starfield defaults | Weapon & PA `SNDR` banks remain on hold; `S9` Preston Lobby (`0xBF6`) & Sturges Intro (`0xBFD`) dialogue `SCEN`s ship converted FO4 `.wem` voice lines |
