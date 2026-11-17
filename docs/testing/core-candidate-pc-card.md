# Core Candidate Bundle — Combined PC Card (`CF-10`)

> [!IMPORTANT]
> **Candidate Branch Scope (`gemini/core-candidate`, Not for Direct Merge):** Combines `main` + `#799` + `#802` + `#803` (`8cb46ed8`) + `#805` + `#806` (`d16d7e70`) + `#807` (`161d1b43`) + `#808` + `#809` + `#810` + `#811` + `#812` + `#813` + `#814` + `#815` + `#817` (`be0b7dec`) + `#818` + `#819` + `#820` + `#821` (`FO4SFCombat.esm` + `FO4SFCombat.dll`) + `#822` (`FO4SFCompanions.esm`) + `#823` (`FO4SFReputation.esm`) into **one install** and **one console-free New Game (Quick Start) walk** across all **11** core verification steps.
> Any finding from the Vault 111 walk (`#803`) outranks all downstream steps.

---

## 1. Build, Clean-Core Fold, Install & Rollback (Game Closed)

`scripts/core/make_core_bundle.py` refuses to run if `Starfield.exe` is open (`System.pids`), stages all core components from one checkout, builds a hardlinked clean copy of the core set (dropping any prior `FO4SFNewGame.esm` and rewriting `README.txt` as a new file), folds all components, runs `verify` + plugin-count (`<= 245`) + `4 GiB` BA2 archive checks, and prints **one** `exp_install.py install ... --pack` command plus its matching rollback:

```powershell
# 1. Stage all components, fold into clean copy of owner-set, and verify (game closed)
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
  --combat-sfse-build "<COMBAT_SFSE_BUILD_DIR>"
  # Optional Pip-Boy stack: add --with-pipboy --pipboy-stage "<PIPBOY_STAGE_DIR>"
```

- **Expected Offline `PASS` Lines & Capacity Margins:**
  - `folded plugins (19): FO4ActorRaider.esm, FO4TerrainCore.esm, FO4SFMission.esm, FO4TerrainCore_Mars.esm, FO4SFVaultGearDoor.esm, FO4SFExitLift.esm, FO4SFNewGame.esm, FO4SFRads.esm, FO4SFHardcore.esm, FO4SFWorkshop.esm, FO4SFPowerArmor.esm, FO4SFProgression.esm, FO4SFListDialogue.esm, FO4SFCombat.esm, FO4SFReputation.esm, FO4SFCompanions.esm, FO4SFALife.esm, FO4SFFortHagen.esm, FO4SFCoreCandidate.esm` *(or **`21` plugins** `<= 245` limit with `--with-pipboy`: `+ FO4SFPipboyProbe.esm, FO4SFPipboyTravel.esm`)*
  - `archive check: 52,746 Data/ files, estimated Main.ba2 = 4,015,455,514 B (3.740 GiB <= 4.000 GiB limit)` *(or `52,774` `Data/` files, `4,016,632,538 B` / `3.741 GiB <= 4.000 GiB` with `--with-pipboy`)*
  - `verify: ok`
  - **`CF-1` `StartWorld` Descriptor Table (`src/fo4sf/core/start_worlds.py`):** Standard title starts (`vault111`, `vault101`, `goodsprings`, `vault76`, `vault13`, `arroyo`) initialize neutral `Karma = 0`, `0` faction `Fame`/`Infamy`, and `squad_base_cap = 2`; tactical and faction alternate starts (`bunkeralpha`, `minuteman_volunteer`, `brotherhood_initiate`, `ncr_trooper`, `desert_ranger`) seed explicit `combat_title_rule`, `initial_fame`, and `squad_base_cap = 4` descriptors.

- **Single Install Command & Matching Rollback (Printed by `make_core_bundle.py`):**
  ```powershell
  # Install (game closed):
  python scripts/game/exp_install.py install --exp-dir "<SCRATCH_DIR>\core-candidate-bundle" --starfield "<STARFIELD_DIR>" --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4SFMission.esm,FO4TerrainCore_Mars.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFCoreCandidate.esm --pack

  # Matching Rollback (game closed, after walk & log capture):
  python scripts/game/exp_install.py uninstall --starfield "<STARFIELD_DIR>"
  ```
  *(If testing SFSE hotkeys and `--with-pipboy`, copy `<BUNDLE>\sfse_sidecar\SFSE\Plugins\*` — `FO4SFCombat.dll`, `FO4SFCombat.ini`, `FO4SFPipboyMenu.dll`, `FO4SFPipboyMenu.ini` — into `<STARFIELD_DIR>\Data\SFSE\Plugins\` before launch and remove them on rollback.)*

---

## 2. Step Independence & Save-Slot Plan (Failure Isolation)

Once Step 1 lands on the Commonwealth Vault 111 hilltop (`stage 200`), `FO4SFCoreCandidate.esm` (`FO4SF_CoreCandidateWalk`) automatically places a spaced field-station line `12 m`–`56 m` ahead of the player and adds the starter field kit to inventory so **Steps 3–11 run 100% console-free and independently**:

| Step | Feature Under Test | Save Slot Needed? | Dependency / Failure Isolation |
| :--- | :--- | :--- | :--- |
| **Step 1** | Pod walk-out -> gear door -> lift -> Commonwealth landing | **Optional Slot A** (*post-landing baseline save* right after landing at `stage 200`, deleted at end) | Entry gate for exterior walk. If Step 1 fails inside Vault 111, stop and report on `#803` immediately. |
| **Step 2** | Hold-off Pass 2 count (`195` of `199`) | None (`0` saves) | Read-only check on `fo4sf_newgame.0.log` written automatically during Step 1. Cannot block Steps 3–11. |
| **Step 3** | Radiation zone (`12 m`) & `RadAway` | None (`0` saves) | **Independent** (`FO4SFRads.esm`). If Step 3 fails, step past the `12 m` emitter and continue to Step 4. |
| **Step 4** | Hardcore `GPOF` toggle ON and OFF | None (`0` saves) | **Independent** (`FO4SFHardcore.esm` Settings menu). Ends in `OFF` state so Hunger/Thirst/Ammo burden never affect Steps 5–11. |
| **Step 5** | Workshop scrap, build & save-quit-reload | **Required Throwaway Slot B:** **`fo4sf_candidate_throwaway`** (deleted after reload check) | **Independent** (`FO4SFWorkshop.esm`). Uses its own dedicated throwaway save **`fo4sf_candidate_throwaway`** (separate from Slot A) so a reload hiccup never corrupts any other save. |
| **Step 6** | Power Armor climb-in & exit (`28 m`) | None (`0` saves; reuses Slot A if recovery ever needed) | **Independent** (`FO4SFPowerArmor.esm`). If exit ever fails to restore race/gear, reload Slot A (if kept) and skip directly to Step 7 (`34 m`). |
| **Step 7** | List dialogue with `[Speech 50]` check (`34 m`) | None (`0` saves) | **Independent** (`FO4SFListDialogue.esm`). Player inventory holds `Wasteland Speech Primer` (`+35` Speech on drop) so `[Speech 50]` fail AND pass work even if Step 8 is skipped. |
| **Step 8** | Creation flow (`1` Background + `2` Traits, `38 m`) | None (`0` saves) | **Independent** (`FO4SFProgression.esm` + `FO4SFCoreCandidate.esm` kiosk at `38 m`). *(Note `#815` gate: Grok reviewed `#806` at `#issuecomment-6936222962` and fixes are pushed at `d16d7e70`; confirm Claude (PC) go-ahead.)* |
| **Step 9** | Combat Core: 6-zone hits, High-DT ammo cycle, leg cripple/cure & VATS (`44 m`) | None (`0` saves) | **Independent** (`FO4SFCombat.esm` + `FO4SFCombat.dll` at `44 m`). |
| **Step 10** | Karma & 16-state Reputation (`Very Evil + Idolized` orthogonality, `50 m`) | Shares **`fo4sf_candidate_throwaway`** reload | **Independent** (`FO4SFReputation.esm` vendor & walk tokens at `50 m`). |
| **Step 11** | Companions & 4-NPC Warfare Fireteam commands + teleport (`56 m`) | Shares **`fo4sf_candidate_throwaway`** reload | **Independent** (`FO4SFCompanions.esm` 4-NPC fireteam at `56 m`). |

---

## 3. Exact 30-Minute Console-Free Walk & Per-Step Verdicts

Start Starfield from a fresh launch (`0` console commands: no `tcl`, `coc`, `moveto`, or `setstage` during play).

### Step 1 — Pod Walk-Out, Gear Door, Lift & Commonwealth Landing (~6 min)
- **Console-Free Steps:**
  1. From the Main Menu, select **New Game** -> when Vault 111 loads, select **Quick start** (`button=1` on the start prompt).
  2. Turn around from the pod start `(9.14, -6.61, -1.03)` and walk normally through the cryo bay and corridors to the Vault 111 gear door.
  3. Press **`E`** on the gear door (`00126D`) -> confirm the gear door animates open and the catwalk connects (`stage 30`), with **no** elevator prompt firing at the console or catwalk.
  4. Walk across the catwalk onto the waiting floor platform (`(-77.74, -3.96, -1.75)`, gates open overhead) -> confirm the **Vault 111 elevator** prompt appears -> select **Ride up**.
  5. Ride `+21.6 m` (`~9.9 s`, gates close at start of ascent) -> confirm exterior transfer lands on the Commonwealth Vault 111 hilltop (`(-2467.78, -1406.92, 128.11)`), wait `5 s` until HUD notification `"FO4SF Core Walk ready ahead: Rads (12m), PA (28m), Dialogue (34m), Chargen (38m)"` appears.
  6. *(Optional safety slot A)* Pause (`Esc` -> **Save**) once on the hilltop if desired as a fallback slot; delete at end of session.
- **Log Reader:** `python scripts/core/make_core_bundle.py log --step exit` *(and detailed `python scripts/newgame/make_newgame.py log`)*
- **PASS Line:** `PASS  exit: stages=[10, 20, 30, 40, 200] pod_ok=True carried_ok=True core_cell=True landed=True exit_failure=None`
- **FAIL Line:** `FAIL  exit: ...` (or stuck in pod / missing gear-door prompt / early lift prompt / procedural non-`03` cell landing)
- **What to Capture:** `fo4sf_newgame.0.log`, `FO4SFCoreCandidate.0.log`, and 1 exterior screenshot facing Sanctuary from the hilltop.

### Step 2 — Starfield Quest Hold-Off Pass 2 Count (`195` of `199`) (~1 min)
- **Console-Free Steps:** Automatic during Step 1 (`stage 10 -> 20`). Confirm during the walk that **zero** Starfield Constellation/ship/city quest popups or companion barks appear on HUD.
- **Log Reader:** `python scripts/core/make_core_bundle.py log --step hold`
- **PASS Line:** `PASS  hold: stopped_unique=195/199 (expect 195) pass1=... pass2=...`
- **FAIL Line:** `FAIL  hold: stopped_unique=<N>/199 (expect 195) ...`
- **What to Capture:** `fo4sf_newgame.0.log` (`held off` lines for passes 1 & 2).

### Step 3 — Radiation Zone & `RadAway` Cure (`12 m` Ahead) (~3 min)
- **Console-Free Steps:**
  1. Walk `12 m` forward to **Station A** (placed `FO4SF_RadsEmitter`) and stand within `5 m` for `~10 s` (or consume `1x Irradiated Food` from **Inventory -> Aid**) until HUD/health reflects radiation gain (`>= 50` rads, Mode A Max-HP cap).
  2. Step `10 m` clear of the emitter, open **Inventory -> Aid**, and use **`1x FO4SF_RadAway`** -> confirm rads drop (`-300` rads back to `0`) and Max HP restores.
- **Log Reader:** `python scripts/core/make_core_bundle.py log --step rads`
- **PASS Line:** `PASS  rads: exposed=True cured=True peak_rads=... final_rads=0.0`
- **FAIL Line:** `FAIL  rads: exposed=False ...` or `cured=False ...`
- **What to Capture:** `FO4SFRadsCore.0.log`.

### Step 4 — Hardcore & Survival `GPOF` Toggle ON and OFF (~3 min)
- **Console-Free Steps:**
  1. Press `Esc` -> **Settings -> Gameplay Options** -> locate **Survival & Hardcore Options -> Hardcore Survival Mode** -> switch **ON**, exit Settings, wait `5 s` (carried `100x FO4SF_CaliberRifle` applies `-5.0` ammo carry-weight burden; `SQ_ENV` remains stopped), and optionally use `1x FO4SF_Stimpak` from Aid (heals over time).
  2. Press `Esc` -> **Settings -> Gameplay Options** -> switch **Hardcore Survival Mode** back **OFF**, exit Settings, wait `3 s` -> confirm ammo weight burden reverts to `0.0` cleanly.
- **Log Reader:** `python scripts/core/make_core_bundle.py log --step hardcore` *(and `python scripts/survival/make_hardcore.py log`)*
- **PASS Line:** `PASS  hardcore: saw_on=True saw_off=True sq_env_conflict=False`
- **FAIL Line:** `FAIL  hardcore: ...` (or `sq_env_conflict=True`)
- **What to Capture:** `FO4SFHardcore.0.log`.

### Step 5 — Workshop Scrap, Build & Save-Quit-Reload (`fo4sf_candidate_throwaway`) (~7 min)
- **Console-Free Steps:**
  1. Stand on open ground `~20 m` ahead of landing. Open **Inventory -> Misc** and **drop `FO4SF_ScrapToken`** (*Field Scrapper Kit*) -> `FO4SF_WorkshopCoreQuest` scraps the `16` starter junk items (`4x DeskFan`, `4x DuctTape`, `4x HotPlate`, `4x TinCan`) into `16 Iron`, `8 Aluminum`, `8 Adhesive`, `12 Tungsten`, `8 Copper`, `4 ZeroWire`, `8 AdaptiveFrame`, `4 Fiber`.
  2. Open **Inventory -> Misc** and **drop `FO4SF_CAMPKit`** (or `FO4SF_SettlementKit`) -> deploys a live workshop / C.A.M.P. beacon `2.5 m` ahead.
  3. Look at the deployed beacon/workbench (`BUILD [E]`), press **`E`** to open Build Mode, place **`1x Industrial Workbench`** on the ground using the scrapped `Iron` and `Aluminum`, and press **`Esc`** to exit Build Mode.
  4. Save into a **dedicated second throwaway save slot** treated as **`fo4sf_candidate_throwaway`** (`Esc -> Save -> New Save` for a strictly console-free walk, noting the created `.sfs` file so only that throwaway slot is removed afterward; or `save fo4sf_candidate_throwaway` if your harness names `.sfs` files explicitly), **Quit to Desktop**, relaunch Starfield, and **Load** that throwaway save.
  5. Confirm visually after reload that both the C.A.M.P./workbench (`BUILD [E]`) and built `Industrial Workbench` persist in place (`OnPlayerLoadGame` writes `reload_audit` to `FO4SFWorkshopCore.0.log`).
- **Log Reader:** `python scripts/core/make_core_bundle.py log --step workshop` *(stitches `.1.log` + `.0.log`; also `python scripts/workshop/make_workshop_core.py log`)*
- **PASS Line:** `PASS  workshop: scrapped=True placed=True reload_persisted=True`
- **FAIL Line:** `FAIL  workshop: ...`
- **What to Capture:** `FO4SFWorkshopCore.1.log`, `FO4SFWorkshopCore.0.log`, and 1 post-reload screenshot showing the persisted `Industrial Workbench` + `BUILD [E]` prompt.

### Step 6 — Power Armor Climb-In & Exit (`28 m` Ahead) (~4 min)
- **Console-Free Steps:**
  1. Walk to **Station C (`28 m` ahead)**: press **`E`** on `FO4SF_PowerArmorFrameFurn` to climb in -> stand up/move once `"Power Armor ON"` appears (`1x FO4SF_FusionCore` loaded at `100%`, third-person Mark 1 PA body/hands/suit visible, `6` limb `AVIF`s at `100`).
  2. Walk around for `10–15 s` so `FO4SF_PAFusionCharge` drains below `100`.
  3. Activate the adjacent **Exit Chair** (`3 m` to the right, **`E`**) and stand up -> confirm `"Power Armor OFF"`, `HumanRace` and prior outfit restored, and the empty frame stands re-enabled at the exit spot.
- **Log Reader:** `python scripts/core/make_core_bundle.py log --step powerarmor`
- **PASS Line:** `PASS  powerarmor: entered=True exited=True frame_standing=True`
- **FAIL Line:** `FAIL  powerarmor: ...`
- **What to Capture:** `FO4SFPACore.0.log` (plus `.1.log` if rotated during Step 5).

### Step 7 — Silent-Player List Dialogue With `[Speech 50]` Skill Check (`34 m` Ahead) (~3 min)
- **Console-Free Steps:**
  1. Walk to **Station D1 (`34 m` ahead)** and press **`E`** on **`Relay Operator`** (`FO4SF_ListSpeakerNpc`): confirm Starfield's native `DialogueMenu` opens an `8`-entry silent-player numbered list (`> 4` choices, zero crash).
  2. With baseline `Speech < 50`, select the **`[Speech 50]`** failing line (`stage 21`), then select the unconditional exit line (`"Step away from the relay station."`, `stage 60`).
  3. Open **Inventory -> Misc** and **drop `Wasteland Speech Primer`** (`+35`/`60` Speech), press **`E`** on `Relay Operator` again, select the passing **`[Speech 50]`** line (`stage 20`), and exit cleanly.
- **Log Reader:** `python scripts/core/make_core_bundle.py log --step dialogue`
- **PASS Line:** `PASS  dialogue: skill_or_tag_branch_recorded=True`
- **FAIL Line:** `FAIL  dialogue: skill_or_tag_branch_recorded=False`
- **What to Capture:** `FO4SFListDialogue.0.log` and 1 screenshot of the numbered `[Speech 50]` list menu.

### Step 8 — Player Creation Flow: `1` Background + `2` Traits + `40`-Point S.P.E.C.I.A.L. (`38 m` Ahead) (~3 min)
- **Console-Free Steps:**
  1. Walk to **Station D2 (`38 m` ahead)** and press **`E`** on **`Wasteland Character Rebuild Kiosk`** *(or drop `Wasteland Character Rebuild Slate` from Misc inventory)*:
     - **Menu 1 (Background):** Select **`Vault Dweller (+Speech/Science/Medicine)`** (button `0`).
     - **Menu 2 (Trait #1):** Select **`Good Natured (+5 Social, -5 Combat)`** (button `0`).
     - **Menu 3 (Trait #2):** Select **`Small Frame (+1 AGI, -15 Carry)`** (button `0`).
  2. Confirm HUD notification `"Character built: VaultDweller (2 trait(s), Speech ..., 40-pt SPECIAL)"`. *(Optionally press `E` on `Relay Operator` `4 m` back to confirm `[Vault Dweller]` and `[Good Natured]` dialogue rows are now unlocked too!)*
- **Log Reader:** `python scripts/core/make_core_bundle.py log --step progression`
- **PASS Line:** `PASS  progression: source=walk_kiosk bg=VaultDweller traits_count=2 (expect 2) special_sum=40`
- **FAIL Line:** `FAIL  progression: ...`
- **What to Capture:** `FO4SFCoreCandidate.0.log` and `FO4SFProgression.0.log`.

### Step 9 — Combat Core: 6-Zone Silhouette, High-DT Ammo Cycle, Leg Cripple/Cure & Slow-Time VATS (`44 m` Ahead) (~5 min)
- **Console-Free Steps:**
  1. Walk to **Station E (`41–44 m` ahead)** and activate **Combat Core Weapon & Medical Supply Rack** (`Grendel` `7.77mm`, `Breach` `12g`, `AP`/`JHP`/`+P`/`Slug` subtypes, `Wasteland Stimpak`, `Doctor's Bag`).
  2. Shoot each of the **6 anatomical silhouette plates** (`Head`, `Torso`, `Left Arm`, `Right Arm`, `Left Leg`, `Right Leg`).
  3. Shoot **High-DT Armored Target (`DT=18, DR=15%`)** with `Standard`, press **`N`** (or activate **Ammo Subtype Cycler**) to select `AP` (`-15 DT`), and shoot again (`16.38` vs `4.8` damage).
  4. Activate **Leg-Cripple Fracture Rig** (`-40%` `SpeedMult` slow walk), toggle **Hardcore Cure Rule** (`Stimpak` refused `cured=0`), and use **`Doctor's Bag`** (`cured=1`, speed restored).
  5. Face **VATS Combat Target Dummy**, press **`V`** (or drop `VATS Targeting Slate`), pick **Head**, and observe `25%` slow-time + queued `Weapon.Fire` shot.
- **Log Reader:** `python scripts/core/make_core_bundle.py log --step combat`
- **PASS Line:** `PASS  combat: zones=6/6 ammo_dt=True cripple_cure=True vats=True`
- **FAIL Line:** `FAIL  combat: ...`

### Step 10 — Karma & 16-State Faction Reputation (`50 m` Ahead) (~4 min)
- **Console-Free Steps:**
  1. Walk to **Station F (`49–50 m` ahead)** and pick up **`3x FO4SF_TheftToken`** (`-350` Karma each -> `Very Evil <= -750`) and **`1x FO4SF_FactionAidToken`** (`+80` Fame -> `Idolized`, state `3` with `Minutemen`).
  2. Confirm `FO4SF_RepVendorNpc` remains non-hostile (`Ally` reaction `2`, `0.75x` vendor buy discount) despite `Very Evil` Karma, and verify `STAT`/`DATA` Pip-Boy rows if `--with-pipboy` is active.
- **Log Reader:** `python scripts/core/make_core_bundle.py log --step reputation`
- **PASS Line:** `PASS  reputation: evil_idolized_orthogonality=True reload_persisted=True`
- **FAIL Line:** `FAIL  reputation: ...`

### Step 11 — Companions, Crew & 4-NPC Warfare Fireteam (`56 m` Ahead) (~5 min)
- **Console-Free Steps:**
  1. Walk to **Station G (`56 m` ahead)** (*Rifleman Alpha*, *Medic Bravo*, *Heavy Charlie*, *Scout Delta*). With `Minuteman Volunteer` / `Desert Ranger` background or `Squad Commander`, recruit all **4** fireteam members.
  2. Drop **`Tactical Fireteam Radio`** (`FO4SF_SquadRadioToken`) from Misc inventory -> issue **`All Hold Position`**, **`All Follow`**, **`Aggressive` / `Defensive`**, and **`Inspect 4 Slots`**, then verify following members teleport across a fast-travel or load-door hop AND persist across the throwaway save/quit/reload (`fo4sf_candidate_throwaway`).
- **Log Reader:** `python scripts/core/make_core_bundle.py log --step companions`
- **PASS Line:** `PASS  companions: fireteam_4npc=True teleport=True reload_persisted=True`
- **FAIL Line:** `FAIL  companions: ...`

---

## 4. Combined Final Verdict, Throwaway Save Cleanup & Rollback

Quit Starfield **without overwriting any permanent save**, run the single combined log check across all 11 steps, delete **`fo4sf_candidate_throwaway`** (and optional Slot A if made), and run rollback:

```powershell
# 1. Evaluate all 11 steps at once (exits 0 only when all 11 steps PASS)
python scripts/core/make_core_bundle.py log --step all

# 2. Delete throwaway save file(s) from My Games\Starfield\Saves\
Remove-Item "$HOME\Documents\My Games\Starfield\Saves\fo4sf_candidate_throwaway*.sfs" -Force -ErrorAction SilentlyContinue

# 3. Roll back the candidate bundle (game closed)
python scripts/game/exp_install.py uninstall --starfield "<STARFIELD_DIR>"
```

Expected combined `verdict: PASS` output (`exit 0`):
```text
PASS  exit: ...
PASS  hold: stopped_unique=195/199 (expect 195) ...
PASS  rads: exposed=True cured=True ...
PASS  hardcore: saw_on=True saw_off=True sq_env_conflict=False
PASS  workshop: scrapped=True placed=True reload_persisted=True
PASS  powerarmor: entered=True exited=True frame_standing=True
PASS  dialogue: skill_or_tag_branch_recorded=True
PASS  progression: source=walk_kiosk bg=VaultDweller traits_count=2 (expect 2) special_sum=40
PASS  combat: zones=6/6 ammo_dt=True cripple_cure=True vats=True
PASS  reputation: evil_idolized_orthogonality=True reload_persisted=True
PASS  companions: fireteam_4npc=True teleport=True reload_persisted=True
verdict: PASS
```
