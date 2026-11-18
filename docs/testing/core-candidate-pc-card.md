# Core Candidate Bundle — Combined PC Card (`CF-10` + Beginning Pilot `Steps 1–15`)

> [!IMPORTANT]
> **Candidate Branch Scope (`gemini/core-candidate`, `#816` at `cd03411a`):** Combines the 19-plugin Core Candidate (`3.740 GiB`, or 21 plugins at `3.741 GiB` with `--with-pipboy`) into **one install** and **one console-free New Game (Quick Start) walk** covering both the **hilltop core station line (`Steps 1–12`)** and the **scripted Fallout 4 beginning route (`Steps 13–15`: Sanctuary & Codsworth -> Red Rocket & Concord -> Preston Garvey)** documented in [fo4-beginning-pilot.md](fo4-beginning-pilot.md).
>
> **Scope Labels & Placeholders:** Every step below carries an explicit reality label (`REACHABLE`, `TEST-STATION`, `RECORDS ONLY`, `TOOLING`, `NOT BUILT`) and calls out active **placeholders**. `FO4SFCoreCandidate.esm` (`FO4SF_CoreCandidateWalk.psc`) is a **`TEST-STATION`** hilltop harness (`12 m`–`56 m`) that spawns test stations, kits, and a hardcoded `40`-point `SPECIAL` sheet; it is not world content.

---

## 1. Build, Clean-Core Fold, Archive Budget, Install & Rollback (`TOOLING`, Game Closed)

`scripts/core/make_core_bundle.py` (`TOOLING`) refuses to run if `Starfield.exe` is open (`System.pids`), stages all core components from one checkout, builds a hardlinked clean copy of the core set, folds components, runs `verify` + plugin-count (`<= 245`) + `4 GiB` BA2 archive checks, and prints install and rollback commands:

```powershell
# 1. Stage all components, fold into clean copy, and verify offline (game closed)
#    Note: pass the Pip-Boy stage root directly to --pipboy-stage so all 21 plugins fold cleanly.
python scripts/core/make_core_bundle.py build `
  --owner-set "<OWNER_SET_DIR>" `
  --work "<SCRATCH_DIR>\stages" `
  --clean-core-out "<SCRATCH_DIR>\clean-core" `
  --out "<SCRATCH_DIR>\core-candidate-bundle" `
  --starfield-dir "<STARFIELD_DIR>" `
  --fo4-data "<FO4_DIR>\Data" `
  --port "<STARFIELD_DIR>\Data\FO4Port.esm" `
  --port-ids "<PORT_FORMIDS_JSON>" `
  --door-anim-dll "<CALUMI_ANIMATION_DLL>" `
  --collision-template "<COLLISION_TEMPLATE_NIF>" `
  --texconv "<TEXCONV_EXE>" `
  --render-python "<RENDER_VENV_PYTHON>" `
  --combat-sfse-build "<COMBAT_SFSE_BUILD_DIR>" `
  --with-pipboy --pipboy-stage "<PIPBOY_STAGE_DIR>"

# 2. Verify all 7 Fallout 4 beginning steps (B1..B7) are present in the staged bundle:
python scripts/testing/check_beginning_pilot.py check-bundle --bundle-dir "<SCRATCH_DIR>\core-candidate-bundle"
```

---

## 2. Step Reality Labels, Placeholders & Save-Slot Plan (`Steps 1–15`)

Steps `5`, `10`, and `11` share **one single save-quit-reload** into throwaway slot **`fo4sf_candidate_throwaway`** at the end of the walk; the remaining **12** steps require **`0` saves**:

| Step | Feature Under Test | Reality Label | Active Placeholders & `NOT BUILT` Boundaries | Second Save Slot? |
| :--- | :--- | :--- | :--- | :--- |
| **Step 1** | Pod walk-out -> gear door (`#803`) -> lift (`#803`) -> hilltop landing (`B1`–`B4`) | **`REACHABLE`** | Pre-war/spouse cutscenes, console terminal `OnActivate`, corpse Pip-Boy pickup, and exterior lid cutscene are `NOT BUILT`. Lift ride is proven by `'ascent carried confirmed'`; `stage 40` is `FinishSurface` hilltop `SetPosition`, and `stage 200` is `CheckLanding`. | **No** *(Optional Slot A baseline)* |
| **Step 2** | Hold-off Pass 2 count (`195` of `199`, `#802`/`#807`/group 5) | **`REACHABLE`** + **`TOOLING`** | `FO4SF_Min00` banner still fires in the vault at New Game start (`StartGameEnabled`). | **No (`0` saves)** |
| **Step 3** | Radiation zone (`12 m`) & `RadAway` (`#809`) | **`TEST-STATION`** *(source)* / **`REACHABLE`** *(math)* | Hazard/aid items come from the hilltop `TEST-STATION` kit (world rad placements/loot lists are `RECORDS ONLY`; water rads trigger on any water; readout is `Debug.Notification` **placeholder**). | **No (`0` saves)** |
| **Step 4** | Hardcore `GPOF` toggle ON and OFF (`#810`) | **`REACHABLE`** *(meters)* / **`NOT BUILT`** *(fast-travel gate)* | Uses hilltop `TEST-STATION` ration/water/`FO4SF_Stimpak` items (vanilla food/med packs unmapped); `FO4SF_HardcoreFastTravelBlocked` global has no reader (`NOT BUILT`). | **No (`0` saves)** |
| **Step 5** | Workshop scrap, C.A.M.P. deploy & reload (`#813`, `20 m`) | **`TEST-STATION`** *(kit drop)* / **`RECORDS ONLY`** *(`COBJ`)* | Drops inventory kit items to `PlaceAtMe` a bench or **placeholder** Starfield `OutpostBeaconActivator`; scraps `4` hardcoded junk items; settlement economy ratings (settlers/food/water/power/defence) are `NOT BUILT`. | **Yes (`fo4sf_candidate_throwaway`)** |
| **Step 6** | Power Armor climb-in & exit (`#814`, `28 m`) | **`TEST-STATION`** | Frame is a **placeholder** cloned Starfield chair (`NPCChairTech03`); armor pieces are **placeholder** `Spacesuit_Mark1` reskins (`SetRace`); exit works only via the `TEST-STATION` exit chair (limb repair `NOT BUILT`). | **No (`0` saves)** |
| **Step 7** | List dialogue with `[Speech 50]` check (`#812`, `34 m`) | **`RECORDS ONLY`** / **`TEST-STATION`** | Single `TEST-STATION` speaker using slice-local `Speech`/`Science` actor values (not linked to `FO4SFProgression`); dialogue converter `NOT BUILT`. | **No (`0` saves)** |
| **Step 8** | Creation sheet (`1` Background + `2` Traits + `40`-pt SPECIAL, `#815`, `38 m`) | **`TEST-STATION`** | Driven by the walk harness's hardcoded `40`-pt preset (`7/5/6/6/6/5/5`); player creation/perk-spend UI is `NOT BUILT`; `26` perk records are `RECORDS ONLY` empty perks. | **No (`0` saves)** |
| **Step 9** | Combat Core: zone plates, ammo cycle, leg cripple & VATS (`#821`, `44 m`) | **`TEST-STATION`** *(targets)* / **`RECORDS ONLY`** *(ammo)* | Zone multipliers and message-box VATS hit fixed `TEST-STATION` plates (not world NPCs); ammo cycling sets a global (`RECORDS ONLY` in normal gunfire); hilltop weapons are **placeholder** Starfield firearms. | **No (`0` saves)** |
| **Step 10** | Karma & 16-state Reputation (`#823`, `50 m`) | **`TEST-STATION`** *(vendor)* | `8` new factions contain only the `TEST-STATION` vendor NPC (world faction mapping `NOT BUILT`; Pip-Boy bridge `TOOLING` only). | **Yes (`fo4sf_candidate_throwaway`)** |
| **Step 11** | Companions & 4-NPC Fireteam muster, wheel & teleport (`#822`, `56 m`) | **`TEST-STATION`** *(muster)* | Mustered by test stage (normal-play recruit UI and faction warfare territory mode `NOT BUILT`; bleedout stabilize does not restore HP yet). | **Yes (`fo4sf_candidate_throwaway`)** |
| **Step 12** | Pip-Boy Stack: shell/`STAT`, `M`-key `MAP` & Star-Map block (`#817`, `--with-pipboy`) | **`TEST-STATION`** *(`STAT`)* / **`REACHABLE`** *(`MAP`/block)* | FO4 `STAT` page displays **placeholder** `SPECIAL` values (`1`, modifier `0`); `MAP` discovery/travel and `GalaxyStarMapMenu` null-creator block are `REACHABLE` runtime code. | **No (`0` saves)** |
| **Step 13** | Sanctuary Hills Walk & Codsworth Keeper (`B5_codsworth_sanctuary`) | **`REACHABLE`** *(keeper)* / **`NOT BUILT`** *(`MQ102`)* | Codsworth uses a **placeholder** Starfield `OutpostRobotMiniBotA_Garden` base with converted `codsworth.nif` and `20` `Hello` `.wem` lines (`MQ102` dialogue/sweep & house interiors `NOT BUILT`). | **No (`0` saves)** |
| **Step 14** | Red Rocket Approach & Concord Raider Fight (`B6_concord_raiders`) | **`REACHABLE`** *(street fight)* / **`NOT BUILT`** *(Museum)* | Up to `8` relocated `FO4_LvlRaider` street enemies (`stages 10 -> 20 -> 30`); containers hold **placeholder** Starfield `Credits`; `Dogmeat`, Museum interior, T-45 roof frame, and Deathclaw are `NOT BUILT`. | **No (`0` saves)** |
| **Step 15** | Preston Garvey Turn-In & `100`-Credit Completion (`B7_preston_turnin`) | **`REACHABLE`** *(turn-in)* / **`TEST-STATION`** *(follow)* | Preston is a **placeholder** renamed `FO4_LvlRaider_Calm` NPC (raider face/body/outfit, zero dialogue); awards `100` **placeholder** Starfield `Credits` (`0x00000F`, not Caps); `FO4SF_COMPreston.FollowTest` is console-only (`Card B-Card-2`). | **No (`0` saves)** |

---

## 3. Exact Console-Free Walk (`Steps 1–15`)

### Steps 1–12 — Vault 111 Exit (`B1`–`B4`, `#803`) & Hilltop `TEST-STATION` Line (`12 m`–`56 m`)
1. **Step 1 (`B1_pod`..`B4_surface_landing`, `#803`):** New Game -> Quick Start -> walk from cryo pod `(9.14, -6.61, -1.03)` to the Vault 111 gear-door console (`ConsoleRadius = 2.5 m` proximity or press `E` on door `00126D` -> `stage 30`) -> step onto floor platform `(-77.74, -3.96, -1.75)` -> **Ride up** (`Play01` `+21.6 m` ascent -> `'ascent carried confirmed'`) -> `FinishSurface` places player on merged hilltop cell (`stage 40`) -> `CheckLanding` confirms solid terrain at `(-2467.78, -1406.92, 128.11)` (`stage 200`, zero `exit failed reason=` or `fell z=` fallback).
2. **Step 2:** Confirm zero Starfield quest banners (`hold-off pass 2 stopped=195 of 199`).
3. **Steps 3–12:** Walk the hilltop `TEST-STATION` line (`12 m` Rads + `RadAway`, `GPOF` Hardcore ON/OFF, `20 m` Workshop scrap + C.A.M.P. kit drop, `28 m` Power Armor chair/Mark1 **placeholder** enter + test-chair exit, `34 m` `[Speech 50]` test speaker, `38 m` harness `40`-pt SPECIAL preset, `44 m` target-plate combat rack, `50 m` test vendor reputation, `56 m` 4-NPC fireteam muster/teleport, `F7`/`M`/`G` Pip-Boy & Star-Map block when built with `--with-pipboy`).

### Step 13 — Sanctuary Hills Walk & Codsworth (`B5_codsworth_sanctuary`, `0` Saves)
- **Console-Free Steps:**
  1. From the Vault 111 hilltop, walk `~120 m` east down the trail into **Sanctuary Hills** toward `(-2346.71, -1406.16, 111.73)`.
  2. Confirm **Codsworth** (`0x811`, `FO4SF_CodsworthKeeper`, `MiniBotA` **placeholder** with `codsworth.nif` mesh) is relocated/held within `<= 3 m` of his Sanctuary spot.
  3. Press **`E`** on Codsworth and confirm voiced `RobotMiniBotA` greeting audio plays without error.
- **PASS Line (`check_beginning_pilot.py check-logs`):** `PASS         B5_codsworth_sanctuary: Codsworth relocated/held near Sanctuary spot without failures`

### Step 14 — Red Rocket Approach & Concord Raider Fight (`B6_concord_raiders`, `0` Saves)
- **Console-Free Steps:**
  1. Cross the Sanctuary bridge and follow the road southeast past **Red Rocket** into **Concord** (`(-2011.14, -1697.54, 89.09)`). *(Red Rocket `Dogmeat` is `NOT BUILT`, `Card B-Card-5`.)*
  2. Approach within `60 m` of the Concord street raiders (or `20 m` of Preston outside the Museum entrance) -> confirm HUD notification **`When Freedom Calls: kill the raiders`** (`stage 20`).
  3. Defeat all Concord street raiders (using **placeholder** Starfield firearms from Step 9) -> confirm Preston stays non-hostile (`IgnoreFriendlyHits(True)`) and HUD updates to **`When Freedom Calls: talk to Preston Garvey`** (`stage 30`).
- **PASS Line (`check_beginning_pilot.py check-logs`):** `PASS         B6_concord_raiders: When Freedom Calls stages 10 -> 20 -> 30 completed`

### Step 15 — Preston Garvey Turn-In & Placeholder `100`-Credit Completion (`B7_preston_turnin`, `0` Saves)
- **Console-Free Steps:**
  1. Walk within `3 m` of **Preston Garvey** (**placeholder** `FO4_LvlRaider_Calm` NPC at `(-2011.14, -1697.54, 89.09)`) or press **`E`** on him.
  2. Confirm **`100` placeholder Starfield Credits** (`0x00000F`) are added (`stage 40`) and HUD displays **`When Freedom Calls: complete`** (`stage 200`), with Preston held calmly at the Museum entrance (`Card B-Card-2` tracks console-free recruitment and real NPC appearance).
- **PASS Line (`check_beginning_pilot.py check-logs`):** `PASS         B7_preston_turnin: stages 40 -> 200 reached, reward=100 placeholder credits (door-held; console-free follow is Card B-Card-2)`

### Single End-of-Walk Save, Quit & Reload (`fo4sf_candidate_throwaway` — Covers Steps 5, 10 & 11)
1. Save once into throwaway slot **`fo4sf_candidate_throwaway`**, quit to Desktop, relaunch via SFSE, load `fo4sf_candidate_throwaway`, and wait `5 s` so `OnPlayerLoadGame` writes `reload_audit` across Workshop, Reputation, and Companions (and `FO4SF_CodsworthKeeper` logs `keeper load` for Preston and Codsworth).

---

## 4. Combined Final Verdict & Clean Rollback (`TOOLING`)

```powershell
# 1. Core 12-step log evaluator:
python scripts/core/make_core_bundle.py log --step all

# 2. Beginning B1..B7 log evaluator (exits non-zero on any FAIL or non-PASS step):
python scripts/testing/check_beginning_pilot.py check-logs `
  --newgame-log "<STARFIELD_LOGS_DIR>\fo4sf_newgame.0.log" `
  --mission-log "<STARFIELD_LOGS_DIR>\fo4sf_mission.0.log" `
  --require-all-pass
```
Delete only the `fo4sf_candidate_throwaway` `.sfs` file afterward and run rollback with the game closed.
