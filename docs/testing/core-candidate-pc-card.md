# Core Candidate Bundle — Combined PC Card (`CF-10`)

> [!IMPORTANT]
> **Candidate Branch Scope (`gemini/core-candidate`, Not for Direct Merge):** Combines `main` + `#799` + `#802` + `#803` (`8cb46ed8`) + `#805` + `#806` (`d16d7e70`) + `#807` (`161d1b43`) + `#808` + `#809` + `#810` + `#811` + `#812` + `#813` + `#814` + `#815` + `#817` (`be0b7dec`, Pip-Boy stack `FO4SFPipboyProbe.esm` + `FO4SFPipboyTravel.esm` + `FO4SFPipboyMenu.dll`) + `#818` + `#819` + `#820` + `#821` (`c07ca48e`, `FO4SFCombat.esm` + `FO4SFCombat.dll`) + `#822` (`a14b2101`, `FO4SFCompanions.esm`) + `#823` (`1ee84359`, `FO4SFReputation.esm`) into **one install** and **one console-free New Game (Quick Start) walk** across all **12** core verification steps.
> Any finding from the Vault 111 walk (`#803`) outranks all downstream steps.

---

## 1. Build, Clean-Core Fold, Archive Budget, Install & Rollback (Game Closed)

`scripts/core/make_core_bundle.py` refuses to run if `Starfield.exe` is open (`System.pids`), stages all core components from one checkout, builds a hardlinked clean copy of the core set (dropping any prior slice `.esm`/`.pex` and writing `README.txt` as a new file), folds all components including `--with-pipboy` and `--combat-sfse-build`, runs `verify` + plugin-count (`<= 245`) + `4 GiB` BA2 archive checks, and prints **one** `exp_install.py install ... --pack` command plus its matching rollback:

```powershell
# 1. Stage all components (including Combat SFSE sidecar + Pip-Boy stack), fold into clean copy, and verify (game closed)
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
```

*(If rebuilding `<COMBAT_SFSE_BUILD_DIR>` or `<PIPBOY_STAGE_DIR>` on a fresh folder first, see [combat-core-pc-card.md](../combat/combat-core-pc-card.md) Section 1 and [pipboy-stack-candidate.md](../ui/pipboy-stack-candidate.md) Offline Build & Stage Commands. Omitting `--with-pipboy --pipboy-stage` builds the `19`-plugin bundle at `3.740 GiB`.)*

- **Expected Offline `PASS` Lines & Capacity Margins (`21` Plugins With `--with-pipboy`):**
  - `folded plugins (21): FO4ActorRaider.esm, FO4TerrainCore.esm, FO4SFMission.esm, FO4TerrainCore_Mars.esm, FO4SFVaultGearDoor.esm, FO4SFExitLift.esm, FO4SFNewGame.esm, FO4SFRads.esm, FO4SFHardcore.esm, FO4SFWorkshop.esm, FO4SFPowerArmor.esm, FO4SFProgression.esm, FO4SFListDialogue.esm, FO4SFCombat.esm, FO4SFReputation.esm, FO4SFCompanions.esm, FO4SFALife.esm, FO4SFFortHagen.esm, FO4SFCoreCandidate.esm, FO4SFPipboyProbe.esm, FO4SFPipboyTravel.esm` (`21 <= 245` Starfield plugin ceiling)
  - `archive check: 52,774 Data/ files, estimated Main.ba2 = 4,016,634,881 B (3.741 GiB <= 4.000 GiB limit)` (`~0.259 GiB` / `278,332,414 B` headroom under the `4,294,967,295 B` unsigned 32-bit BA2 ceiling; SFSE `.dll`/`.ini`/`.tsv` sidecars stay in `<BUNDLE>\sfse_sidecar\` outside `Data/`)
  - `verify: ok`
  - **`> 4 GiB` Archive Split Contingency (Never Drop a Gameplay Slice):** If future volume world/asset additions push `<BUNDLE>\Data` past `4,294,967,295 B`, split assets into a second archive rather than dropping any slice: (a) pack `Data/Textures/*` into `<first_plugin> - Textures.ba2` (`DX10`) while keeping meshes, materials, scripts, and `Interface/*.swf` in `<first_plugin> - Main.ba2` (`GNRL`), or (b) keep base terrain geometry in `FO4TerrainCore - Main.ba2` and pack the gameplay/UI slices into `FO4SFCoreCandidate - Main.ba2`.
  - **`CF-1` `StartWorld` Descriptor Table (`src/fo4sf/core/start_worlds.py`):** Standard title starts (`vault111`, `vault101`, `goodsprings`, `vault76`, `vault13`, `arroyo`) initialize neutral `Karma = 0`, `0` faction `Fame`/`Infamy`, and `squad_base_cap = 2`; tactical and faction alternate starts (`bunkeralpha`, `minuteman_volunteer`, `brotherhood_initiate`, `ncr_trooper`, `desert_ranger`) seed explicit `combat_title_rule`, `initial_fame`, and `squad_base_cap = 4` descriptors.

- **Single Install Command, SFSE Sidecar Copy & Matching Rollback (Printed by `make_core_bundle.py`):**
  ```powershell
  # 1. Install bundle BA2 + all 21 plugins (game closed):
  python scripts/game/exp_install.py install --exp-dir "<SCRATCH_DIR>\core-candidate-bundle" --starfield "<STARFIELD_DIR>" --plugins FO4ActorRaider.esm,FO4TerrainCore.esm,FO4SFMission.esm,FO4TerrainCore_Mars.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFNewGame.esm,FO4SFRads.esm,FO4SFHardcore.esm,FO4SFWorkshop.esm,FO4SFPowerArmor.esm,FO4SFProgression.esm,FO4SFListDialogue.esm,FO4SFCombat.esm,FO4SFReputation.esm,FO4SFCompanions.esm,FO4SFALife.esm,FO4SFFortHagen.esm,FO4SFCoreCandidate.esm,FO4SFPipboyProbe.esm,FO4SFPipboyTravel.esm --pack

  # 2. Copy SFSE sidecars beside versionlib-1-16-244-0.bin (game closed):
  Copy-Item "<SCRATCH_DIR>\core-candidate-bundle\sfse_sidecar\SFSE\Plugins\*" "<STARFIELD_DIR>\Data\SFSE\Plugins\" -Force

  # Matching Rollback (game closed, after walk & log capture):
  Remove-Item "<STARFIELD_DIR>\Data\SFSE\Plugins\FO4SFCombat.dll","<STARFIELD_DIR>\Data\SFSE\Plugins\FO4SFCombat.ini","<STARFIELD_DIR>\Data\SFSE\Plugins\FO4SFPipboyMenu.dll","<STARFIELD_DIR>\Data\SFSE\Plugins\FO4SFPipboyMenu.ini","<STARFIELD_DIR>\Data\SFSE\Plugins\FO4SFPipboyMapMarkers.tsv" -Force -ErrorAction SilentlyContinue
  python scripts/game/exp_install.py uninstall --starfield "<STARFIELD_DIR>"
  ```

---

## 2. Step Independence & Save-Slot Plan (`0` Saves vs Second Save Slot)

Once Step 1 lands on the Commonwealth Vault 111 hilltop (`stage 200`), `FO4SFCoreCandidate.esm` (`FO4SF_CoreCandidateWalk`) automatically places a spaced field-station line `12 m`–`56 m` ahead of the player and adds the starter field kit to inventory so **Steps 2–12 run 100% console-free and independently**.

Steps `5`, `10`, and `11` share **one single save-quit-reload** into the dedicated second save slot **`fo4sf_candidate_throwaway`** at the end of the walk (after Step 12), so Starfield only restarts **once** and all 8 remaining gameplay steps require **`0` saves**:

| Step | Feature Under Test | Second Save Slot Needed? | Independence & Failure Isolation |
| :--- | :--- | :--- | :--- |
| **Step 1** | Pod walk-out -> gear door -> lift -> Commonwealth landing (`#803`) | **No** *(Optional Slot A post-landing baseline save if desired; deleted at end)* | **Entry gate** for exterior walk. If Step 1 fails inside Vault 111, stop and report on `#803` immediately. |
| **Step 2** | Hold-off Pass 2 count (`195` of `199`, `#807`) | **No (`0` saves — Independent)** | **Independent** read-only check on `fo4sf_newgame.0.log` written during Step 1. Cannot block Steps 3–12. |
| **Step 3** | Radiation zone (`12 m`) & `RadAway` (`#809`) | **No (`0` saves — Independent)** | **Independent** (`FO4SFRads.esm`). If Step 3 fails, step past the `12 m` emitter and continue to Step 4. |
| **Step 4** | Hardcore `GPOF` toggle ON and OFF (`#810`) | **No (`0` saves — Independent)** | **Independent** (`FO4SFHardcore.esm` Settings menu). Ends in `OFF` state so survival burden never affects Steps 5–12. |
| **Step 5** | Workshop scrap, C.A.M.P. deploy & reload persistence (`#813`, `20 m`) | **Yes — Second Save Slot (`fo4sf_candidate_throwaway`)** *(verified in the single reload after Step 12)* | **Independent** (`FO4SFWorkshop.esm`). Scrap + workbench placement run at `20 m`; reload persistence (`FO4SFWorkshopCore.0.log`) is verified by the single end-of-walk reload. |
| **Step 6** | Power Armor climb-in & exit (`#814`, `28 m`) | **No (`0` saves — Independent)** | **Independent** (`FO4SFPowerArmor.esm`). If exit ever fails to restore race/gear, reload Optional Slot A (if kept) and continue at `34 m`. |
| **Step 7** | List dialogue with `[Speech 50]` check (`#812`, `34 m`) | **No (`0` saves — Independent)** | **Independent** (`FO4SFListDialogue.esm`). Starter kit holds `Wasteland Speech Primer` (`+35`/`60` Speech on drop) so `[Speech 50]` fail & pass work even if Step 8 is skipped. |
| **Step 8** | Creation flow (`1` Background + `2` Traits + `40`-pt SPECIAL, `#815`, `38 m`) | **No (`0` saves — Independent)** | **Independent** (`FO4SFProgression.esm` + kiosk at `38 m`). *(Confirm Claude (PC) go-ahead per `#815` / `#806` gate.)* |
| **Step 9** | Combat Core: 6-zone hits, High-DT ammo cycle, leg cripple/cure & slow-time VATS (`#821`, `44 m`) | **No (`0` saves — Independent)** | **Independent** (`FO4SFCombat.esm` + `FO4SFCombat.dll` firing range at `41–44 m`). Ends with all limbs restored to `100`. |
| **Step 10** | Karma & 16-state Reputation (`Very Evil + Idolized` orthogonality & reload parity, `#823`, `50 m`) | **Yes — Second Save Slot (`fo4sf_candidate_throwaway`)** *(shares the single reload after Step 12)* | **Independent** (`FO4SFReputation.esm` vendor & walk tokens at `49–50 m`). Orthogonality runs live; `reload_audit` fires automatically on the end-of-walk reload. |
| **Step 11** | Companions & 4-NPC Warfare Fireteam muster, commands, teleport & reload (`#822`, `56 m`) | **Yes — Second Save Slot (`fo4sf_candidate_throwaway`)** *(shares the single reload after Step 12)* | **Independent** (`FO4SFCompanions.esm` 4-NPC fireteam at `56 m`). Muster, radio commands, and teleport run live; `reload_audit` fires automatically on the end-of-walk reload. |
| **Step 12** | Pip-Boy Stack: FO4 shell/`STAT`, `M`-key `MAP` open/close & Star-Map block (`#817`) | **No (`0` saves — Independent)** | **Independent** (`FO4SFPipboyProbe.esm` + `FO4SFPipboyTravel.esm` + `FO4SFPipboyMenu.dll`). Pure UI/input/map check (`F7`, `M`, scanner `F -> G`); `0` saves required. |

---

## 3. Exact Console-Free Walk & Per-Step Verdicts (`Steps 1–12`)

Launch Starfield via SFSE (`0` console commands required during play: no `tcl`, `coc`, `moveto`, or `setstage`).

### Step 1 — Pod Walk-Out, Gear Door, Lift & Commonwealth Landing (*No Second Save Slot; Optional Baseline Slot A*)
- **Console-Free Steps:**
  1. From the Main Menu, select **New Game** -> when Vault 111 loads, select **Quick start** (`button=1` on the start prompt).
  2. Turn around from the pod start `(9.14, -6.61, -1.03)` and walk normally through the cryo bay and corridors to the Vault 111 gear door.
  3. Press **`E`** on the gear door (`00126D`) -> confirm the gear door animates open and the catwalk connects (`stage 30`), with **no** elevator prompt firing at the console or catwalk.
  4. Walk across the catwalk onto the waiting floor platform (`(-77.74, -3.96, -1.75)`, gates open overhead) -> confirm the **Vault 111 elevator** prompt appears -> select **Ride up**.
  5. Ride `+21.6 m` (`~9.9 s`, gates close at start of ascent) -> confirm exterior transfer lands on the Commonwealth Vault 111 hilltop (`(-2467.78, -1406.92, 128.11)`), wait `5 s` until HUD notification `"FO4SF Core Walk ready ahead: Rads (12m)..Chargen (38m), Combat (44m), Reputation (50m), Squad (56m)."` appears.
  6. *(Optional safety Slot A)* Pause (`Esc -> Save`) once on the hilltop if desired as a fallback slot; delete at end of session.
- **Log Reader:** `python scripts/core/make_core_bundle.py log --step exit`
- **PASS Line:** `PASS  exit: stages=[10, 20, 30, 40, 200] pod_ok=True carried_ok=True core_cell=True landed=True exit_failure=None`
- **What to Capture:** `fo4sf_newgame.0.log` (or `.1.log` after reload), `FO4SFCoreCandidate.0.log`, and 1 exterior screenshot facing Sanctuary from the hilltop.

### Step 2 — Starfield Quest Hold-Off Pass 2 Count (`195` of `199`) (*Independent — `0` Saves*)
- **Console-Free Steps:** Automatic during Step 1 (`stage 10 -> 20`). Confirm during the walk that **zero** Starfield Constellation/ship/city quest popups or companion barks appear on HUD.
- **Log Reader:** `python scripts/core/make_core_bundle.py log --step hold`
- **PASS Line:** `PASS  hold: stopped_unique=195/199 (expect 195) pass1=... pass2=...`

### Step 3 — Radiation Zone & `RadAway` Cure (`12 m` Ahead) (*Independent — `0` Saves*)
- **Console-Free Steps:**
  1. Walk `12 m` forward to **Station A** (placed `FO4SF_RadsEmitter`) and stand within `5 m` for `~10 s` (or consume `1x Irradiated Food` from **Inventory -> Aid**) until HUD/health reflects radiation gain (`>= 25` rads, Mode A Max-HP cap).
  2. Step `10 m` clear of the emitter, open **Inventory -> Aid**, and use **`1x FO4SF_RadAway`** -> confirm rads drop (`-300` rads back to `0`) and Max HP restores.
- **Log Reader:** `python scripts/core/make_core_bundle.py log --step rads`
- **PASS Line:** `PASS  rads: exposed=True cured=True peak_rads=... final_rads=0.0`

### Step 4 — Hardcore & Survival `GPOF` Toggle ON and OFF (*Independent — `0` Saves*)
- **Console-Free Steps:**
  1. Press `Esc` -> **Settings -> Gameplay Options** -> locate **Survival & Hardcore Options -> Hardcore Survival Mode** -> switch **ON**, exit Settings, wait `5 s` (carried `100x FO4SF_CaliberRifle` applies `-5.0` ammo carry-weight burden; `SQ_ENV` remains stopped).
  2. Press `Esc` -> **Settings -> Gameplay Options** -> switch **Hardcore Survival Mode** back **OFF**, exit Settings, wait `3 s` -> confirm ammo weight burden reverts to `0.0` cleanly.
- **Log Reader:** `python scripts/core/make_core_bundle.py log --step hardcore`
- **PASS Line:** `PASS  hardcore: saw_on=True saw_off=True sq_env_conflict=False`

### Step 5 — Workshop Scrap & C.A.M.P. Build (`20 m` Ahead) (*Uses Second Save Slot `fo4sf_candidate_throwaway` at End of Walk*)
- **Console-Free Steps:**
  1. Stand on open ground `~20 m` ahead of landing. Open **Inventory -> Misc** and **drop `FO4SF_ScrapToken`** (*Field Scrapper Kit*) -> `FO4SF_WorkshopCoreQuest` scraps the `16` starter junk items (`4x DeskFan`, `4x DuctTape`, `4x HotPlate`, `4x TinCan`) into `16 Iron`, `8 Aluminum`, `8 Adhesive`, `12 Tungsten`, `8 Copper`, `4 ZeroWire`, `8 AdaptiveFrame`, `4 Fiber`.
  2. Open **Inventory -> Misc** and **drop `FO4SF_CAMPKit`** (or `FO4SF_SettlementKit`) -> deploys a live workshop / C.A.M.P. beacon `2.5 m` ahead.
  3. Look at the deployed beacon/workbench (`BUILD [E]`), press **`E`** to open Build Mode, place **`1x Industrial Workbench`** on the ground using the scrapped `Iron` and `Aluminum`, and press **`Esc`** to exit Build Mode. *(Leave it standing — reload persistence is verified together with Steps 10 & 11 in Section 3.13 below.)*
- **Log Reader:** `python scripts/core/make_core_bundle.py log --step workshop`
- **PASS Line:** `PASS  workshop: scrapped=True placed=True reload_persisted=True`

### Step 6 — Power Armor Climb-In & Exit (`28 m` Ahead) (*Independent — `0` Saves*)
- **Console-Free Steps:**
  1. Walk to **Station C (`28 m` ahead)**: press **`E`** on `FO4SF_PowerArmorFrameFurn` to climb in -> stand up/move once `"Power Armor ON"` appears (`1x FO4SF_FusionCore` loaded at `100%`, third-person Mark 1 PA body/hands/suit visible, `6` limb `AVIF`s at `100`).
  2. Walk around for `10–15 s` so `FO4SF_PAFusionCharge` drains below `100`.
  3. Activate the adjacent **Exit Chair** (`3 m` to the right, **`E`**) and stand up -> confirm `"Power Armor OFF"`, `HumanRace` and prior outfit restored, and the empty frame stands re-enabled at the exit spot.
- **Log Reader:** `python scripts/core/make_core_bundle.py log --step powerarmor`
- **PASS Line:** `PASS  powerarmor: entered=True exited=True frame_standing=True`

### Step 7 — Silent-Player List Dialogue With `[Speech 50]` Skill Check (`34 m` Ahead) (*Independent — `0` Saves*)
- **Console-Free Steps:**
  1. Walk to **Station D1 (`34 m` ahead)** and press **`E`** on **`Relay Operator`** (`FO4SF_ListSpeakerNpc`): confirm Starfield's native `DialogueMenu` opens an `8`-entry silent-player numbered list (`> 4` choices, zero crash).
  2. With baseline `Speech < 50`, select the **`[Speech 50]`** failing line (`stage 21`), then select the unconditional exit line (`"Step away from the relay station."`, `stage 60`).
  3. Open **Inventory -> Misc** and **drop `Wasteland Speech Primer`** (`+35`/`60` Speech), press **`E`** on `Relay Operator` again, select the passing **`[Speech 50]`** line (`stage 20`), and exit cleanly.
- **Log Reader:** `python scripts/core/make_core_bundle.py log --step dialogue`
- **PASS Line:** `PASS  dialogue: skill_or_tag_branch_recorded=True`

### Step 8 — Player Creation Flow: `1` Background + `2` Traits + `40`-Point S.P.E.C.I.A.L. (`38 m` Ahead) (*Independent — `0` Saves*)
- **Console-Free Steps:**
  1. Walk to **Station D2 (`38 m` ahead)** and press **`E`** on **`Wasteland Character Rebuild Kiosk`** *(or drop `Wasteland Character Rebuild Slate` from Misc inventory)*:
     - **Menu 1 (Background):** Select **`Vault Dweller (+Speech/Science/Medicine)`** (button `0`) — or **`Brotherhood Scribe`** (button `3`).
     - **Menu 2 (Trait #1):** Select **`Good Natured (+5 Social, -5 Combat)`** (button `0`).
     - **Menu 3 (Trait #2):** Select **`Small Frame (+1 AGI, -15 Carry)`** (button `0`).
  2. Confirm HUD notification `"Character built: ... (2 trait(s), Speech ..., 40-pt SPECIAL)."`.
- **Log Reader:** `python scripts/core/make_core_bundle.py log --step progression`
- **PASS Line:** `PASS  progression: source=walk_kiosk bg=VaultDweller traits_count=2 (expect 2) special_sum=40`

### Step 9 — Combat Core: 6-Zone Silhouette, High-DT Ammo Cycle, Leg Cripple/Cure & Slow-Time VATS (`44 m` Ahead) (*Independent — `0` Saves*)
- **Console-Free Steps:**
  1. Walk to **Station E (`41–44 m` ahead)** and press **`E`** on **Combat Core Weapon & Medical Supply Rack** (`Grendel` `7.77mm` auto-equipped, `Breach` `12g`, `AP`/`JHP`/`+P`/`Slug` subtypes, `Wasteland Stimpak`, `Doctor's Bag`).
  2. Fire one round into each of the **6 anatomical silhouette plates** (`Head`, `Torso`, `Left Arm`, `Right Arm`, `Left Leg`, `Right Leg`).
  3. Shoot **High-DT Armored Target (`DT=18, DR=15%`)** once with `Standard`, press **`N`** (or activate **Ammo Subtype Cycler**) to select `AP` (`-15 DT`), and shoot again (`16.38` vs `4.8` damage).
  4. Activate **Leg-Cripple Fracture Rig** (`-40%` `SpeedMult` slow walk), activate **Hardcore Cure Rule Toggle** (`Stimpak` refused `cured=0`), use **`Doctor's Bag`** from Aid (`cured=1`, walk speed restored), and toggle **Hardcore Cure Rule Toggle** back to Normal (`0`).
  5. Face **VATS Combat Target Dummy**, press **`V`** (or drop `VATS Targeting Slate`), pick **Head**, and observe `25%` slow-time + queued `Weapon.Fire` shot.
- **Log Reader:** `python scripts/core/make_core_bundle.py log --step combat`
- **PASS Line:** `PASS  combat: zones=6/6 ammo_dt=True cripple_cure=True vats=True`

### Step 10 — Karma & 16-State Faction Reputation (`50 m` Ahead) (*Uses Second Save Slot `fo4sf_candidate_throwaway` at End of Walk*)
- **Console-Free Steps:**
  1. Walk to **Station F (`49–50 m` ahead)** and pick up **`3x FO4SF_TheftToken`** (`-350` Karma each -> `Very Evil`, `-1000`) and **`1x FO4SF_FactionAidToken`** (`+80` Fame -> `Idolized`, state `3` in `states=3,0,0,0,0,0,0,0` with `Minutemen`).
  2. Confirm `FO4SF_RepVendorNpc` remains non-hostile (`Ally` reaction `2`, `0.75x` vendor buy discount) despite `Very Evil` Karma. *(Reload parity is verified in Section 3.13 below.)*
- **Log Reader:** `python scripts/core/make_core_bundle.py log --step reputation`
- **PASS Line:** `PASS  reputation: evil_idolized_orthogonality=True reload_persisted=True`

### Step 11 — Companions, Crew & 4-NPC Warfare Fireteam (`56 m` Ahead) (*Uses Second Save Slot `fo4sf_candidate_throwaway` at End of Walk*)
- **Console-Free Steps:**
  1. Walk to **Station G (`56 m` ahead)** (*Rifleman Alpha*, *Medic Bravo*, *Heavy Charlie*, *Scout Delta*) and press **`E`** on *Rifleman Alpha*: `FO4SF_CoreCandidateWalk` musters all **4** Warfare fireteam members (`stage 20`, unlocking the `4`-slot cap and registering all `4/4` into `ActiveSquad` within `2 s`).
  2. Open **Inventory -> Misc** and **drop `Tactical Fireteam Radio`** (`FO4SF_SquadRadioToken`) -> issue **`All Hold Position`** (button `1`), drop again -> **`All Follow`** (button `0`), drop again -> **`Aggressive`** (button `2`) / **`Defensive`** (button `3`), drop again -> **`Sync / Teleport Squad`** (button `5`, verifying `teleport` formation warp), and **`Inspect 4 Slots`** (button `6`). *(Optionally press `E` directly on *Rifleman Alpha* to inspect the individual 8-button `Companion Tactical Wheel`.)*
- **Log Reader:** `python scripts/core/make_core_bundle.py log --step companions`
- **PASS Line:** `PASS  companions: fireteam_4npc=True teleport=True reload_persisted=True`

### Step 12 — Pip-Boy Stack: FO4 Shell/`STAT`, `M`-Key `MAP` & Complete Star-Map Block (`#817`) (*Independent — `0` Saves*)
- **Console-Free Steps:**
  1. Press **`F7`** (`0x76`): confirm the Fallout 4 Pip-Boy shell (`FO4SF_Fo4Shell`) opens cleanly on `STAT` with `SPECIALList` populated (`pushed=7`), `ConditionClips` loaded, and `E`/`Q` cycling `STAT -> INV -> DATA -> MAP -> RADIO` with zero crash; press **`F7`** to close.
  2. Press **`M`** (`0x4D`): confirm `FO4SF_PipboyMenu` opens directly on **`MAP` (`page=3`)** with the `2048x2048` Commonwealth world map texture (`loaded=1`) and `309`-row marker store (`corners_set=3/3`); press **`M`** again and confirm it closes cleanly with **zero** reopen bounce.
  3. Press **`F`** to open the hand scanner, then press **`G`** (Surface/Star Map bind): confirm Starfield's vanilla `GalaxyStarMapMenu` **never** opens (`step=starmap_blocked ... route=create` in `FO4SFPipboyMenu.log`), then close scanner (`F`).
- **Log Reader:** `python scripts/core/make_core_bundle.py log --step pipboy`
- **PASS Line:** `PASS  pipboy: no_refuse=True shell_special=True map_open_close=True map_data=True starmap_blocked=True`

### 3.13 Single Shared Second-Slot Save, Quit & Reload (`fo4sf_candidate_throwaway` — Covers Steps 5, 10 & 11 Together)
1. Save **once** into a **dedicated second throwaway save slot** treated as **`fo4sf_candidate_throwaway`** (`Esc -> Save -> New Save` for a strictly console-free walk, noting the created `.sfs` filename so only that throwaway slot is deleted afterward; or `save fo4sf_candidate_throwaway` if your harness names `.sfs` files explicitly).
2. **Quit Starfield completely to Desktop** (rotating `.0.log` -> `.1.log` across Workshop, Reputation, and Companions).
3. **Relaunch Starfield via SFSE**, **Load** that `fo4sf_candidate_throwaway` save, and wait `5 s`:
   - Confirm visually that the built `Industrial Workbench` + C.A.M.P. (`BUILD [E]` at `20 m`), the `Very Evil + Idolized` non-hostile `Minutemen` vendor (`50 m`), and all `4` recruited Warfare fireteam members (`56 m`) persist in place while `OnPlayerLoadGame` writes `reload_audit` to `FO4SFWorkshopCore.0.log`, `FO4SFReputation.0.log`, and `FO4SFCompanions.0.log`.

---

## 4. Combined Final Verdict, Throwaway Save Cleanup & Rollback

Quit Starfield **without overwriting any permanent save**, run the single combined log check across all **12** steps, delete **`fo4sf_candidate_throwaway`** (and optional Slot A if made), and run rollback:

```powershell
# 1. Evaluate all 12 steps at once (exits 0 only when all 12 steps PASS; add --no-pipboy if built without --with-pipboy)
python scripts/core/make_core_bundle.py log --step all

# 2. Delete throwaway save file(s) from My Games\Starfield\Saves\
Remove-Item "$HOME\Documents\My Games\Starfield\Saves\fo4sf_candidate_throwaway*.sfs" -Force -ErrorAction SilentlyContinue

# 3. Remove SFSE sidecars and roll back the candidate bundle (game closed)
Remove-Item "<STARFIELD_DIR>\Data\SFSE\Plugins\FO4SFCombat.dll","<STARFIELD_DIR>\Data\SFSE\Plugins\FO4SFCombat.ini","<STARFIELD_DIR>\Data\SFSE\Plugins\FO4SFPipboyMenu.dll","<STARFIELD_DIR>\Data\SFSE\Plugins\FO4SFPipboyMenu.ini","<STARFIELD_DIR>\Data\SFSE\Plugins\FO4SFPipboyMapMarkers.tsv" -Force -ErrorAction SilentlyContinue
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
PASS  pipboy: no_refuse=True shell_special=True map_open_close=True map_data=True starmap_blocked=True
verdict: PASS
```
