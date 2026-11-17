# Core Candidate Bundle — Combined PC Card (`CF-10` + Playable Beginning `Steps 1–15`)

> [!IMPORTANT]
> **Candidate Branch Scope (`gemini/core-candidate`, `#816` at `cd03411a`):** Combines the 19-plugin Core Candidate (`3.740 GiB`, or 21 plugins at `3.741 GiB` with `--with-pipboy`) into **one install** and **one console-free New Game (Quick Start) walk** covering both the **12 core systems (`Steps 1–12`)** on the Vault 111 hilltop and the **Fallout 4 beginning route (`Steps 13–15`: Sanctuary & Codsworth -> Red Rocket & Concord -> Preston Garvey)** documented in [fo4-beginning-pilot.md](fo4-beginning-pilot.md).

---

## 1. Build, Clean-Core Fold, Archive Budget, Install & Rollback (Game Closed)

`scripts/core/make_core_bundle.py` refuses to run if `Starfield.exe` is open (`System.pids`), stages all core components from one checkout, builds a hardlinked clean copy of the core set, folds all components, runs `verify` + plugin-count (`<= 245`) + `4 GiB` BA2 archive checks, and prints **one** install command plus its matching rollback:

```powershell
# 1. Stage all components, fold into clean copy, and verify offline (game closed)
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

## 2. Step Independence & Save-Slot Plan (`Steps 1–15`)

Steps `5`, `10`, and `11` share **one single save-quit-reload** into the dedicated second save slot **`fo4sf_candidate_throwaway`** at the end of the walk; all remaining **12** steps (including **Steps 13–15** from Sanctuary through Concord and Preston) require **`0` saves**:

| Step | Feature Under Test | Second Save Slot Needed? | Independence & Failure Isolation |
| :--- | :--- | :--- | :--- |
| **Step 1** | Pod walk-out -> gear door -> lift -> Commonwealth landing (`#803`, `B1`–`B4`) | **No** *(Optional Slot A baseline save)* | **Entry gate** for exterior walk. |
| **Step 2** | Hold-off Pass 2 count (`195` of `199`, `#807`) | **No (`0` saves — Independent)** | **Independent** read-only check on `fo4sf_newgame.0.log`. |
| **Step 3** | Radiation zone (`12 m`) & `RadAway` (`#809`) | **No (`0` saves — Independent)** | **Independent** (`FO4SFRads.esm`). |
| **Step 4** | Hardcore `GPOF` toggle ON and OFF (`#810`) | **No (`0` saves — Independent)** | **Independent** (`FO4SFHardcore.esm`); ends `OFF`. |
| **Step 5** | Workshop scrap, C.A.M.P. deploy & reload persistence (`#813`, `20 m`) | **Yes (`fo4sf_candidate_throwaway`)** | **Independent** (`FO4SFWorkshop.esm`). |
| **Step 6** | Power Armor climb-in & exit (`#814`, `28 m`) | **No (`0` saves — Independent)** | **Independent** (`FO4SFPowerArmor.esm`). |
| **Step 7** | List dialogue with `[Speech 50]` check (`#812`, `34 m`) | **No (`0` saves — Independent)** | **Independent** (`FO4SFListDialogue.esm`). |
| **Step 8** | Creation flow (`1` Background + `2` Traits + `40`-pt SPECIAL, `#815`, `38 m`) | **No (`0` saves — Independent)** | **Independent** (`FO4SFProgression.esm`). |
| **Step 9** | Combat Core: 6-zone hits, High-DT ammo cycle, leg cripple/cure & VATS (`#821`, `44 m`) | **No (`0` saves — Independent)** | **Independent** (`FO4SFCombat.esm` + `FO4SFCombat.dll`). |
| **Step 10** | Karma & 16-state Reputation (`Very Evil + Idolized`, `#823`, `50 m`) | **Yes (`fo4sf_candidate_throwaway`)** | **Independent** (`FO4SFReputation.esm`). |
| **Step 11** | Companions & 4-NPC Warfare Fireteam muster, commands & teleport (`#822`, `56 m`) | **Yes (`fo4sf_candidate_throwaway`)** | **Independent** (`FO4SFCompanions.esm`). |
| **Step 12** | Pip-Boy Stack: FO4 shell/`STAT`, `M`-key `MAP` & Star-Map block (`#817`) | **No (`0` saves — Independent)** | **Independent** (`FO4SFPipboyProbe.esm` + `FO4SFPipboyTravel.esm`). |
| **Step 13** | **Sanctuary Hills Walk & Codsworth Keeper (`B5_codsworth_sanctuary`)** | **No (`0` saves — Independent)** | **Independent** (`FO4SFMission.esm` `FO4SF_CodsworthKeeper` + `codsworth.nif` + `20` `.wem` voices). |
| **Step 14** | **Red Rocket Approach & Concord Raider Fight (`B6_concord_raiders`)** | **No (`0` saves — Independent)** | **Independent** (`FO4ActorRaider.esm` + `FO4SFMission.esm` `stages 10 -> 20 -> 30`). |
| **Step 15** | **Preston Garvey Turn-In & `100`-Credit Completion (`B7_preston_turnin`)** | **No (`0` saves — Independent)** | **Independent** (`FO4SFMission.esm` `stages 30 -> 40 -> 200` console-free turn-in). |

---

## 3. Exact Console-Free Walk (`Steps 1–15`)

### Steps 1–12 — Vault 111 Exit (`B1`–`B4`) & Hilltop Core Stations (`12 m`–`56 m`)
1. **Step 1 (`B1_pod`..`B4_surface_landing`):** New Game -> Quick Start -> walk from cryo pod `(9.14, -6.61, -1.03)` to gear door (`00126D`, press `E` -> `stage 30`) -> step onto floor platform `(-77.74, -3.96, -1.75)` -> **Ride up** (`stage 40`) -> land on Commonwealth hilltop `(-2467.78, -1406.92, 128.11)` (`stage 200`).
2. **Step 2:** Verify zero Starfield quest banners (`hold-off pass 2 stopped=195 of 199`).
3. **Steps 3–12:** Walk the hilltop station line (`12 m` Rads + `RadAway`, `GPOF` Hardcore ON/OFF, `20 m` Workshop scrap + C.A.M.P. workbench, `28 m` Power Armor enter/exit, `34 m` `[Speech 50]` list dialogue, `38 m` `1` Background + `2` Traits + `40`-pt SPECIAL, `44 m` 6-zone/DT/cripple/VATS combat rack, `50 m` `Very Evil + Idolized` Reputation vendor, `56 m` 4-NPC Warfare fireteam muster/teleport, `F7`/`M`/`F->G` Pip-Boy & Star-Map block).

### Step 13 — Sanctuary Hills Walk & Codsworth (`B5_codsworth_sanctuary`, `0` Saves)
- **Console-Free Steps:**
  1. From the Vault 111 hilltop station line, walk `~120 m` east down the trail into **Sanctuary Hills** toward the cul-de-sac home `(-2346.71, -1406.16, 111.73)`.
  2. Confirm **Codsworth** (`0x811`, `FO4SF_CodsworthKeeper`) is hovering within `<= 3 m` of his Sanctuary spot with intact Mister Handy meshes/materials.
  3. Press **`E`** on Codsworth and confirm voiced `RobotMiniBotA` audio plays without error.
- **PASS Line (`check_beginning_pilot.py check-logs`):** `PASS      B5_codsworth_sanctuary: Codsworth placed/held in Sanctuary without failures`

### Step 14 — Red Rocket Approach & Concord Raider Fight (`B6_concord_raiders`, `0` Saves)
- **Console-Free Steps:**
  1. Cross the Sanctuary bridge and follow the road southeast past the **Red Rocket** truck stop into **Concord** (`(-2011.14, -1697.54, 89.09)`). *(Note: Red Rocket `Dogmeat` quadruped recruitment is tracked separately under `Card B-Card-5` in [fo4-beginning-pilot.md](fo4-beginning-pilot.md).)*
  2. Approach within `60 m` of the Concord street raiders (or `20 m` of Preston outside the Museum entrance) -> confirm HUD notification **`When Freedom Calls: kill the raiders`** (`stage 20`).
  3. Defeat all Concord street raiders (using firearms/VATS from Step 9) -> confirm Preston stays non-hostile (`IgnoreFriendlyHits(True)`) and HUD updates to **`When Freedom Calls: talk to Preston Garvey`** (`stage 30`).
- **PASS Line (`check_beginning_pilot.py check-logs`):** `PASS      B6_concord_raiders: When Freedom Calls stages 10 -> 20 -> 30 completed`

### Step 15 — Preston Garvey Turn-In & `100`-Credit Completion (`B7_preston_turnin`, `0` Saves)
- **Console-Free Steps:**
  1. Walk within `3 m` of **Preston Garvey** at `(-2011.14, -1697.54, 89.09)` or press **`E`** on him.
  2. Confirm **`100` Credits** are added (`stage 40`) and HUD displays **`When Freedom Calls: complete`** (`stage 200`), with Preston remaining calmly stationed at the Museum entrance (`Card B-Card-2` tracks console-free recruitment dialogue at `stage 200`).
- **PASS Line (`check_beginning_pilot.py check-logs`):** `PASS      B7_preston_turnin: stages 40 -> 200 reached, reward=100 credits (door-held; console-free follow is Card B-Card-2)`

### Single End-of-Walk Save, Quit & Reload (`fo4sf_candidate_throwaway` — Covers Steps 5, 10 & 11)
1. Save once into throwaway slot **`fo4sf_candidate_throwaway`**, quit to Desktop, relaunch via SFSE, load `fo4sf_candidate_throwaway`, and wait `5 s` so `OnPlayerLoadGame` writes `reload_audit` across Workshop, Reputation, and Companions (and `FO4SF_CodsworthKeeper` logs `keeper load` for Preston and Codsworth).

---

## 4. Combined Final Verdict & Clean Rollback

```powershell
# 1. Core 12-step log evaluator:
python scripts/core/make_core_bundle.py log --step all

# 2. Beginning B1..B7 log evaluator:
python scripts/testing/check_beginning_pilot.py check-logs `
  --newgame-log "<STARFIELD_LOGS_DIR>\fo4sf_newgame.0.log" `
  --mission-log "<STARFIELD_LOGS_DIR>\fo4sf_mission.0.log" `
  --require-all-pass
```
Delete only the `fo4sf_candidate_throwaway` `.sfs` file afterward and run rollback with the game closed.
