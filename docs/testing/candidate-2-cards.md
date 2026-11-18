# Candidate 2 — Player-Profile Swap Test Cards (Cards 1–5)

Target bundle: **Candidate 2 (`--profile player`, `22` plugins, `FO4SF_TestModeEnabled == 0`, `FO4SFCoreCandidate.esm` omitted)**.

## Truth Labels Before Swap Run

- **`TEST-STATION` / `RECORDS ONLY` (Current Pre-Run Status):** Every Candidate-2 feature below is built and verified offline (unit tests, `16/16` Mutagen C# writer self-tests, cross-plugin FormID/EditorID/VMAD parity check, and `make_core_bundle.py verify`), and awaits the swap-session game run. No card upgrades to **`REACHABLE`** until its console-free game session writes the required PASS log lines with zero FAIL conditions.
- **`OWNER TEST` Boundary:** Automated log checks verify state transitions, FormIDs, coordinates, and crash-free menu lifecycles. Visual appearance, UI readability, animation smoothness, lighting, sound, and gameplay feel are judged exclusively by the owner.
- **Explicitly `NOT BUILT` in Candidate 2:**
  - **Museum of Freedom interior quest chain (`Task 5`):** `laser musket`, `balcony talk`, `power armor + fusion core` on the museum roof (test-cell station only), `minigun`, `second wave` raiders, and `deathclaw` emergence.
  - **Vault 111 lift character sheet extras (`X3`):** Tag skills, background selection, and trait selection from the Story lift prompt (Warfare sets faction background automatically; full creation sheet remains test-station).
  - **Pip-Boy deferred steps (`Task 1` NEXT):** `1b` same-call real vitals fill order (gated until `1a` passes in game), `1i` first-person arm idle (`Arm=1`), `1j` STAT `UseStimpak` / `UseRadaway` actions, and `1k` `INV` / `DATA` pages.

---

## Card 1 — Pip-Boy Crash Proof and Pages (`1a`, `1c`–`1g`, `X2`)

- **Pre-Run Label:** **`TEST-STATION`** (upgraded to **`REACHABLE`** once `1a`–`1g` pass in game).
- **Bundle & INI Preconditions:**
  - Candidate-2 `player` bundle (`22` plugins + `FO4SFPipboyMenu.dll` + generated stage `FO4SFPipboyMenu.ini`).
  - Shipped `FO4SFPipboyMenu.ini` contains `Pause=1`, `RequirePickup=0` (**default OFF** so `F7` and `M` keys remain free for the crash proof before Vault 111 Pip-Boy pickup), `kMaxCodeNames` up to `64` covering all movie-called code names, and **zero** `[Kit]` or `[Page ...]` sections.

### Steps
1. Launch a fresh session, wait until the character stands in gameplay (`Is3DLoaded == true`), press **`F7`** to open the Pip-Boy on **`STAT`**, and hold open for at least **`10 s`**.
2. Press **`E`** on `STAT` and confirm the page does **not** advance (`ProcessUserEvent` Fallout 4 input routing). Switch across `STAT` subpages and `MAP` using the configured Pip-Boy navigation keys.
3. On **`MAP`**, verify Commonwealth markers render, trigger a fast-travel confirmation box if standing outdoors with a discovered marker, and press **`Esc`** once to confirm **`Esc`** closes only the modal box rather than tearing down the whole menu prematurely; press **`Tab`** or **`Esc`** again to close the Pip-Boy cleanly.
4. Re-open with **`M`** directly to **`MAP`**, then close with **`M`** / **`Tab`**.
5. Attempt to open Starfield's hand scanner (**`F`**) and surface/star maps to confirm input-layer and menu-creation blocks hold without crashing.
6. Open a text-entry or blocking menu (such as character naming or the console input line) and type `m`, `v`, and `n` to verify hotkeys are suppressed while another menu is open.
7. *(Optional `X2` boot check during Card 2):* After picking up the Vault 111 Pip-Boy (`pipboy pickup equipped flag=1`), open the Pip-Boy once to play the first-open boot sequence.

### Required PASS Log Lines (`FO4SFPipboyMenu.log` & `fo4sf_newgame.0.log`)
- **Crash proof & code object (`1a`):**
  - Menu stays up `>= 10 s` with zero Windows error events and zero `refuse step=` or `step=watchdog_busy` lines.
  - Code-object holder line reports object type (`type=object`) and full code-name registration (`kMaxCodeNames` capacity `64`, `CheckHardcoreModeFastTravel` and `RefreshMapMarkers` bound).
- **Clean teardown (`1c`, every close):**
  - `code_obj_destruction called=1`
  - `UnregisterMap` (whenever `MAP` was loaded during that open)
  - `step=destroy` (with zero movie writes after `code_obj_destruction`)
- **Key routing & menu-open guard (`1d`):**
  - `ignored=menu_open menu=<name>` when `m`, `v`, or `n` is pressed inside an open blocking menu.
- **Map page & Commonwealth markers (`1e`, after `X4` / `S5` arrival):**
  - `step=map_markers ... discovered=1` (or `discovered>=1` after walking) with `corners_set=3/3 read_back=match`
  - Zero `map_file ... skipped=` lines.
- **Blocked Starfield scanner & maps (`1g`):**
  - `handscanner disabled=true` / `blocked input=handscanner` (`fo4sf_newgame.0.log` / `FO4SFPipboyMenu.log`)
  - `blocked menu=<name> route=create` (or `step=starmap_blocked ... route=create`) with zero crash.

### Negative / FAIL Conditions
- Any crash, freeze, `refuse step=`, `step=watchdog_busy`, `[Kit]` / `[Page ...]` contamination in shipped `FO4SFPipboyMenu.ini`, `map_file ... skipped=`, or `"FO4SF"` developer banner text on screen (`1h`).

### OWNER TEST Items
- Visual inspection of the `STAT` Vault-Boy / condition presentation, tab header alignment, font legibility, `Pause=1` background world pause feel, Commonwealth map image alignment beneath map pins, and first-open boot sequence look.

---

## Card 2 — Story Start and Console-Free Vault 111 Exit (`S4`, `X1`–`X5`)

- **Pre-Run Label:** **`TEST-STATION`** (upgraded to **`REACHABLE`** after one uninterrupted console-free walk from New Game to Commonwealth hilltop landing).
- **Setup:** Start a **New Game** from the main menu with `FO4SF_TestModeEnabled == 0`. Keep the developer console closed (`~` never pressed).

### Console-Free Steps
1. **Black-screen mode prompt (`S4`):** While the screen fade is held black (`FadeHold = true`) and saving is disabled, select **`Story`** in Box 1 and **`Survival: No`** in Box 2. Confirm the screen fades in at the Vault 111 cryo pod (`stage 5` -> `stage 10`).
2. **Vault armory & pre-Pip-Boy console gate (`M2`, `X1`, `X2`):**
   - Walk through Vault 111 to the overseer/armory path and pick up the placeholder ballistic pistol, matching rounds, and `FO4SF_Stimpak`s (`FO4SFRouteLoot.esm`).
   - Press **`E`** directly on the Vault 111 gear door (`VltGearDoor01`) and verify it stays shut.
   - Press **`E`** on the gear-door console **before** picking up the Pip-Boy and verify `NoPipboyMsg` refuses opening.
3. **Pip-Boy pickup & gear-door console (`X1`, `X2`):**
   - Activate (`E`) the Pip-Boy 3000 pickup (`FO4SF_PipboyCorpsePickupRef` `0x080F`) beside the skeleton so `FO4SF_PipboyWrist` equips.
   - Press **`E`** on the gear-door console (`MQ102GearDoorConsoleREF`) to open the gear door (`stage 30`) and walk through the doorway and yellow security gates (`X5` collision bodies).
4. **Vault 111 lift `40`-point S.P.E.C.I.A.L. & optional Character respec (`X3`):**
   - Step onto the floor-level Vault 111 elevator platform (`RespecMoveMarker`).
   - Verify the 4-button prompt (`Continue`, `S.P.E.C.I.A.L.`, `Character`, `Stay`) keeps **`Continue`** gated until **`S.P.E.C.I.A.L.`** is confirmed once.
   - Select **`S.P.E.C.I.A.L.`**, allocate all **`40` points** across the 10-button Progression allocator (`FO4SFCoreValues.esm` `0x0810`–`0x0816`), and confirm (`button=8`).
   - Optionally select **`Character`** once (`RaceMenuMode = 2`, looks-only) and verify a second attempt logs the 1-use limit, then select **`Continue`**.
5. **Carrying ascent, shared map setup & hilltop landing (`X4`):**
   - Ride the elevator platform to the top of the shaft without console commands while shared map setup prepares all Commonwealth markers as known-undiscovered, then complete exterior hilltop arrival (`stage 40` -> `stage 200`) with only Vault 111 discovered (`discovered=1`).

### Required PASS Log Lines (`fo4sf_newgame.0.log`, `FO4SFProgression.0.log`, `FO4SFPipboyMenu.log`)
- `mode fade held`
- `mode choice mode=story survival=0`
- `stage 5` -> `stage 10`
- `pod settle ok=True`
- `hold-off pass 2 stopped=196 of 199` (or `N - stopped <= 4` with zero `running_after=True` on pass 2)
- `pistol picked item=... count=...`
- `cog door activate blocked by=player open_state=...`
- `console refused: no pipboy`
- `pipboy pickup equipped flag=1 worn=True`
- `cog door console activated ref=... before=... after=2` -> `stage 30`
- `special box shown buttons=10 unspent=...` and per-press `special box press=...`
- `special set S=... P=... E=... C=... I=... A=... L=... sum=40 source=lift` (between two elevator prompts; **never** `special skipped`)
- `ascent play accepted=True`
- `map setup done markers=<n> elapsed=<s>` (completed during the ride)
- `ascent carried confirmed elapsed=... z=...`
- `stage 40` -> `landed ... fallback=False` -> `stage 200`
- `FO4SFPipboyMenu.log`: `step=map_markers ... discovered=1`

### Negative / FAIL Conditions
- Message boxes failing to draw over the held black fade (`S4` LEAD check), `cog door opened directly`, console opening without `pipboy pickup equipped flag=1`, `special skipped`, S.P.E.C.I.A.L. `sum != 40`, `exit failed reason=`, `fell z=`, `fallback=True`, walking through yellow gear-room or lift gates without collision (`X5`), or any mission objective banner appearing while still inside Vault 111 (`M1`).

### OWNER TEST Items
- How the start message boxes draw over the held black fade (`FadeHold`), Vault 111 interior lighting and atmosphere, gear-door opening animation/audio, yellow gate solid collision feel, 10-button S.P.E.C.I.A.L. box usability, elevator platform ride smoothness, and Commonwealth hilltop arrival look.

---

## Card 3 — Story with Survival Across Save and Reload (`S2`)

- **Pre-Run Label:** **`TEST-STATION`** (upgraded to **`REACHABLE`** once save/quit/reload persistence passes in game).
- **Version Disclosure (`S2` / Owner Defaults):**
  > **Important:** In this version, **picking `Survival: Yes` at New Game start locks Survival ON for that character's playthrough** (`FO4SF_SurvivalStart == 1`, `FO4SF_SurvivalLocked == 1`) — turning the Starfield Gameplay Options Hardcore switch OFF will **not** disable Survival on that save. Conversely, choosing **`Survival: No`** at start leaves Survival unlocked so the Gameplay Options switch toggles Hardcore ON and OFF freely.

### Console-Free Steps
1. Start a **New Game**, select **`Story`** in Box 1, and select **`Survival: Yes`** in Box 2 (keep Starfield's Gameplay Options Hardcore switch at its default OFF / `gpof=0`).
2. Confirm fade-in at the Vault 111 cryo pod (`stage 10`), verify saving is re-enabled after mode selection, and create a normal manual save.
3. Quit to desktop (or main menu), reload that save, and wait `5 s` for `OnPlayerLoadGame` evaluation.
4. *(Optional unlocked check):* On a `Survival: No` save, toggle the Hardcore option ON then OFF in Starfield's Gameplay Options menu and confirm `enabled=1` -> `enabled=0`.

### Required PASS Log Lines (`fo4sf_newgame.0.log` & `FO4SFHardcore.0.log`)
- At start choice (`fo4sf_newgame.0.log`):
  - `mode choice mode=story survival=1`
- Immediately upon start choice (`FO4SFHardcore.0.log`):
  - `FO4SFHC ... hardcore source gpof=0 start=1 enabled=1 why=start_choice end=true`
  - `FO4SFHC ... sync reason=start_choice hardcore=1 ... ft_blocked=1 sq_env_running=False end=true`
- After save, quit, and reload (`FO4SFHardcore.0.log`):
  - `FO4SFHC ... hardcore source gpof=0 start=1 enabled=1 why=reload end=true`
  - `FO4SFHC ... sync reason=reload hardcore=1 ... ft_blocked=1 sq_env_running=False end=true`

### Negative / FAIL Conditions
- `enabled=0` after reload when `start=1`, `sq_env_running=True`, or saving remaining blocked after `FadeIn`.

### OWNER TEST Items
- Confirming the `Survival: Yes` prompt wording and HUD/Pip-Boy survival feel match expectations before and after reload.

---

## Card 4 — Warfare Start (`S3`, `S5`)

- **Pre-Run Label:** **`TEST-STATION`** (upgraded to **`REACHABLE`** once console-free Warfare deployment to Sanctuary Hills passes in game).
- **Setup:** Start a **New Game** with `FO4SF_TestModeEnabled == 0` and no console commands.

### Console-Free Steps
1. At the start message-box chain (`S4` / `S5`):
   - Box 1: **`Warfare`**
   - Box 2: **`Survival: No`** (or `Yes`)
   - Box 3: Select starting difficulty (e.g. `Normal`, `difficulty=1`)
   - Box 4: **`Minutemen`** (`faction=0`)
   - Box 5: **`Sanctuary Hills`** (`minutemen_sanctuary`, the single validated row in `warfare_starts.json` for Candidate 2)
2. Complete the character looks creator (`ChargenMenu`, `RaceMenuMode = 2`) when it opens.
3. Complete the **`40`-point S.P.E.C.I.A.L.** allocation (`source=warfare`) and confirm (`sum=40`).
4. Verify the character fades in **directly outdoors at Sanctuary Hills** wearing Minutemen faction starter gear and the wrist Pip-Boy, having **never seen Vault 111**, with **zero Story mission objectives** in the HUD/Missions tab, and open the Pip-Boy `MAP` (`M`) to confirm only Sanctuary Hills is discovered (`discovered=1`).

### Required PASS Log Lines (`fo4sf_newgame.0.log`, `FO4SFProgression.0.log`, `fo4sf_mission.0.log`, `FO4SFPipboyMenu.log`)
- `mode fade held`
- `mode choice mode=warfare survival=0` (or `1`)
- `warfare pick faction=0 start=minutemen_sanctuary difficulty=<0..3>`
- `warfare creator open mode=2` -> `warfare creator closed`
- `special set S=... P=... E=... C=... I=... A=... L=... sum=40 source=warfare`
- `FO4SFProgression.0.log`: `warfare_bg bg=8`
- `warfare gear n=4`
- `warfare move ok=True marker=... dist=... z=...`
- `map setup done markers=<n> elapsed=<s>` (same shared function as `X4`)
- `warfare standing slot=0 fame=... infamy=... karma=... squad_cap=4`
- `fade in by=warfare ...` -> `stage 210`
- Story mission suppression (`fo4sf_newgame.0.log` & `fo4sf_mission.0.log`):
  - `mission gate mode=2 started=False`
  - `mission gate mode=2 started=false` (`FO4SF_Min00`), `quest=keeper`, `quest=codsworth01` (all immediately `Stop()` with zero objectives shown)
- `FO4SFPipboyMenu.log`:
  - `step=map_markers ... discovered=1`

### Negative / FAIL Conditions
- Character Creator (`ShowRaceMenu`) failing to draw over held fade (`S4` LEAD check), `warfare move ok=False`, Vault 111 interior flashing on screen, `stage 20` / `stage 30` / `stage 40` running on Warfare, `discovered != 1`, or any Codsworth/Concord objective appearing in Warfare mode.

### OWNER TEST Items
- Character Creator visibility and transition during Warfare start, Sanctuary Hills spawn placement and facing, equipped faction outfit/weapon appearance, and absence of any Vault 111 flash.

---

## Card 5 — Console-Free Mission Walk (`M1`–`M6`, `V1`, `#820`)

- **Pre-Run Label:** **`TEST-STATION` / `RECORDS ONLY` for `M4` & `M6` until `G4` in-game dialogue proof passes** (upgraded to **`REACHABLE`** only when both `E` conversations open `DialogueMenu` and complete without fallback in the same console-free session as Card 2).
- **Critical `G4` Dependency (`M4` & `M6`):**
  > On 18 Nov, pressing `E` on dialogue speakers did nothing before the `G4` scene/race/voice fix (`TopLevel` `PlayerDialogueSceneAction`, `HumanRace` + `AllowDefaultDialog` voice on Preston, `FO4SF_CodsworthRace` `AllowPcDialog` + `FO4SF_CodsworthVoice` `AllowDefaultDialog` on Codsworth). If `E` fails to open `DialogueMenu` in game, **`M4` and `M6` remain `NOT BUILT` for `REACHABLE`** regardless of offline record checks.

### Console-Free Steps (Continuing Directly from Card 2 `stage 200` Landing)
1. **Silent start on hilltop (`M1`):** At `stage 200` on the Vault 111 hilltop, confirm **no Concord objective** is displayed yet while `FO4SF_Codsworth01` points to Sanctuary Hills.
2. **Route container loot (`M2`):** On the walk from Vault 111 through Sanctuary Hills and Red Rocket toward Concord (`<= 600 m` corridor), open at least `3` exterior containers (`FO4SFRouteLoot.esm`, `439` non-credit route containers over `83` `CONT` overrides) and confirm non-credit loot (`aid`, `ammo`, `junk`) spawns alongside credits.
3. **Codsworth Sanctuary conversation (`M6`):**
   - Approach Codsworth in Sanctuary Hills (`off <= 25 m`), verify his brushed-steel Mr. Handy model (non-black `.mat` fix) and talk prompt, and press **`E`**.
   - Step through the 4-choice `DialogueMenu` scene (`stage 20`, `30`, `40`, `100`) so his final line reveals `FO4SF_Min00` `stage 10` (`min00 given by=codsworth`; or verify walking within `150 m` of the Concord museum door reveals `min00 given by=concord` if Codsworth was bypassed).
4. **Concord street raider fight + `stage 20` save/reload (`M3`):**
   - Walk down to Concord Museum street to engage the exterior raiders (`stage 20`, `DefaultCombatMasterPackage` `0x042240` + `DefaultSandboxCurrentLocation` `0x089605`).
   - **Mid-fight reload check (`M3`):** While at `stage 20` with at least one raider remaining, save the game, quit, reload, confirm `reload mission stage=20 ... relocate_fails=0`, and eliminate the remaining raiders to reach `stage 30` (any subterranean/drifted raider is pulled back via `wfc01 rescue`, and any raider unreachable `> 60 s` auto-clears via `wfc01 raider cleared absent`).
5. **Preston Garvey `DialogueMenu` turn-in (`M4`):**
   - Approach Preston Garvey outside the museum (`HumanRace` + colonial/frontier placeholder outfit + `Orion` placeholder rifle), press **`E`**, and complete all `3` dialogue exchanges on Starfield's `DialogueMenu` to reach `stage 40` -> `100` credits reward -> `stage 200` (**do not** idle `120 s` for the proximity fallback: `stage 40 by=fallback` is an automatic **`FAIL`** for `REACHABLE`).
6. **Sanctuary workbench hand-over (`M5`):**
   - Follow the newly started `FO4SF_Sanctuary01` (`0x0817`) HUD marker back to the Sanctuary Hills workshop workbench (`0x005C50` / `0250FE`) and activate (`E`) the workbench to complete `stage 100`.
7. **Run Beginning Pilot Verifier (`V1`):**
   - Run `python scripts/testing/check_beginning_pilot.py check-logs --newgame-log <fo4sf_newgame.0.log> --mission-log <fo4sf_mission.0.log> --require-all-pass` and confirm `B1`–`B8` all report **`PASS`**.

### Required PASS Log Lines (`fo4sf_mission.0.log`)
- All mission log timestamps (`rt=`) appear **after** `fo4sf_newgame.0.log` `stage 200`.
- `mission gate mode=1 started=true`
- `codsworth01 init stage=10` -> `codsworth talk end -> min00 stage 10` -> `codsworth01 complete choices=... concord_pointed=true`
- `min00 given by=codsworth` (or `min00 given by=concord` when testing the `< 150 m` proximity trigger)
- `stage 10` -> `stage 20` -> `reload mission stage=20 ... relocate_fails=0` -> `stage 30` (plus `wfc01 rescue` / `wfc01 raider cleared absent` if triggered)
- `preston talk end info=0x092A -> stage 40` -> `stage 40` -> `reward credits=100` -> `stage 200`
- `min01 stage 10 objective bench` -> `sanctuary01 bench_bound ref=...` -> `min01 bench activated -> stage 100` -> `sanctuary01 bench_activated=true ... complete=true`

### Negative / FAIL Conditions
- Any mission line logged before `FO4SFNewGame` `stage 200`, `stage 40 by=fallback` (**counts as `FAIL` for `REACHABLE`**), `E` failing to open `DialogueMenu` on Codsworth or Preston, `relocate_fails >= 10`, Preston turning hostile on stray friendly fire, or Sanctuary workbench failing to complete `stage 100`.

### Known-Bug Ledger Summary (`#820`) & Cut Scope (`NOT BUILT`)
- **Fixed in Candidate 2:**
  - `WFC-01` (Exterior raider straggler / unloaded-3D stall): fixed via `OnPlayerLoadGame` `relocateFails` reset, raider combat/sandbox packages, `wfc01 rescue` pullback, and `60 s` `wfc01 raider cleared absent` write-off (`M3`).
  - `WFC-02` (Direct approach to Preston): retained `20 m` `FindRadius` + `OnActivate` combat start.
  - `WFC-03` (Friendly-fire hostility): retained `FO4SF_MinutemenFaction` `Ally` relation + `IgnoreFriendlyHits(True)`.
  - `WFC-05` (Post-completion / reload actor drift): `FO4SF_CodsworthKeeper` (`0x0814`) starts at `stage 200` in Story mode and maintains merged coordinates across reloads (`M1`).
  - `WFC-07` (Silent `OnStageSet` drop / debug banners): synchronous `AdvanceTo` idempotency with developer `Debug.Notification` banners gated behind test mode (`1h`).
- **Gated as `TEST-STATION`:**
  - `COMP-01`..`COMP-06` (`FO4SF_COMPreston` follow stand-in): gated behind `FO4SF_TestModeEnabled != 0` (`follow preston test-only refused: test mode off` in normal play).
- **Cut / Deferred (`NOT BUILT` in Candidate 2):**
  - `WFC-04` (Museum balcony / upstairs door lockout) & `WFC-06` (Wave-2 sewer grate Deathclaw snag), together with all Museum of Freedom interior quest stages: **`laser musket`**, **`balcony talk`**, **`power armor + fusion core`**, **`minigun`**, **`second wave`**, and **`deathclaw`** (`NOT BUILT`).

### OWNER TEST Items
- Codsworth's brushed-steel material appearance (confirming the black-mesh bug is gone), Codsworth `.wem` voice playback and subtitle sync in `DialogueMenu`, outdoor container loot variety along the Sanctuary-to-Concord road, raider combat responsiveness in Concord, Preston's `HumanRace` placeholder appearance and `DialogueMenu` pacing, and Sanctuary workbench activation feel.
