# Fallout 4 Beginning Pilot Checklist (`B1`–`B7`)

Goal: evaluate the scripted Fallout 4 opening path — **Vault 111 cryo pod -> gear door -> exit lift -> Commonwealth hilltop landing -> Sanctuary & Codsworth -> Red Rocket & Concord street fight -> Preston Garvey turn-in** — without opening the developer console (`~`), using the 19-plugin Core Candidate (`#816` at `cd03411a`, `3.740 GiB` `Main.ba2`; or 21 plugins at `3.741 GiB` with `--with-pipboy`).

Status labels used across this document and [core-candidate-pc-card.md](core-candidate-pc-card.md):
- **`REACHABLE`**: Runtime Papyrus/native logic wired along the console-free route (in-game proof status noted per row).
- **`TEST-STATION`**: Works only via a test station, test reference, hardcoded preset, or console stand-in.
- **`RECORDS ONLY`**: ESM records/assets exist offline with little or no in-world runtime hookup.
- **`TOOLING`**: Offline bundle verifier or post-run log evaluator (`scripts/testing/check_beginning_pilot.py`, `src/fo4sf/beginning_pilot.py`).
- **`NOT BUILT`**: Absent in code today (tracked in follow-up cards).

> [!NOTE]
> **Current Thin-Chain Scope & Placeholders:** `B1`–`B7` is currently a thin scripted chain rather than a content-complete Fallout 4 opening:
> - **Quest banner timing:** `FO4SF_Min00` currently carries `StartGameEnabled`, so its HUD objective (`When Freedom Calls: find the Last Minutemen`) fires during Vault 111 initialization rather than waiting for `stage 200` hilltop arrival.
> - **Stage `40` vs lift completion:** In `FO4SF_NewGameQuest.psc`, `stage 40` is set inside `FinishSurface` *after* the exterior `MoveTo` and surface `SetPosition` onto the merged `FO4TerrainCore.esm` hilltop cell succeed. The Vault 111 lift ride itself runs at `stage 30` and is proven in `fo4sf_newgame.0.log` by `'ascent carried confirmed'` with zero `'exit failed reason=lift_*'` lines.
> - **Explicit placeholders:** Codsworth uses a **placeholder** Starfield `OutpostRobotMiniBotA_Garden` actor record reskinned with converted `codsworth.nif` and `20` random `Hello` `.wem` greeting lines (`MQ102` dialogue/sweep `NOT BUILT`). Preston Garvey uses a **placeholder** duplicate of the calm converted raider (`FO4_LvlRaider_Calm` body, face, voice, and outfit; zero ported dialogue). The quest completion reward pays `100` **placeholder** Starfield `Credits` (`0x00000F`, not Bottlecaps). World containers (`5,156`) hold **placeholder** Starfield `Credits` (`0x00000F` / `0x00000A`), `3,685` placed world NPCs/creatures are deferred, and hilltop starter weapons/stations come from the `FO4SFCoreCandidate.esm` `TEST-STATION` harness.

---

## 1. End-to-End Beginning Matrix (`B1`–`B7`)

| Step | Label | In Candidate (`#816` `cd03411a`) | Placeholders & `NOT BUILT` Scope | Verification State | Who Runs Next |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`B1_pod`** | **`REACHABLE`** | `FO4SFNewGame.esm` (`StartupQuest_DO` override, `-2.5 m` pod step-out `#803`, `PodLift = 0.3 m`, `ClearInventory` + vault suit + `+100` `O2Capacity`), `FO4Port.esm` (`FO4Port_Vault111Cryo`), `DefaultHold = 199` (`#802` + `#807` + group 5) | Pre-war Sanctuary prologue, mirror chargen, and cryo spouse scene are `NOT BUILT` (uses Quick Start preset or Starfield `ChargenMenu` fallback); `FO4SF_Min00` banner fires early in vault | Pod settle (`ok=true`) & `3.0 m` walk-out verified in-game (17 Nov) on `#802+#803`; `199`-quest hold list verified offline (`TOOLING`) | **Claude (PC)** full `#816` bundle check -> **Owner** |
| **`B2_gear_door`** | **`REACHABLE`** | `FO4SFVaultGearDoor.esm` (**`#803`**, `89` `.mesh`/`.nif`/`.mat` assets, animated `VltGearDoor01` `0x00126D` + catwalk bridge) + `FO4SFNewGame.esm` `ConsoleRadius = 2.5 m` proximity trigger (or direct door open) -> `stage 30` | Console terminal `OnActivate` script, Vault-Tec skeleton Pip-Boy pickup/equip scene, overseer terminal gating, vault loot, and radroach ambush are `NOT BUILT` (`#817` Pip-Boy UI requires `--with-pipboy`) | Verified offline (`TOOLING` `check-bundle`: `PASS`); `stage 30` door open seen in earlier vault log; untested in continuous `#816` walk | **Claude (PC)** in-game gate -> **Owner** |
| **`B3_exit_lift`** | **`REACHABLE`** | `FO4SFExitLift.esm` (**`#803`**, `48` assets, floor-level platform at `(-77.74, -3.96, -1.75)`, gates open at floor, `Play01` `+21.6 m` / `~9.9 s` ascent confirmed by `'ascent carried confirmed'`) + `ExitMessage` (`0x801` Ride up / Stay) | Exterior Vault 111 cog-lid sunlight cutscene is `NOT BUILT` | Verified offline (`TOOLING` `check-bundle`: `PASS`); `'ascent carried confirmed'` unproven in-game on `#816` | **Claude (PC)** in-game gate -> **Owner** |
| **`B4_surface_landing`** | **`REACHABLE`** | `FO4TerrainCore.esm` (`64x64` heightmap + terrain masks + `ExitAnchorId`) + `FO4SFNewGame.esm` `Surface` (`MoveTo`) -> `FinishSurface` (`SetPosition` onto merged cell -> **`stage 40`**) -> `CheckLanding` (`3.0 s` check -> **`stage 200`**) | Region beyond `64x64` border (`#495`) is `NOT BUILT`; `FO4SFCoreCandidate.esm` hilltop station line is a `TEST-STATION` harness | Verified offline (`TOOLING` `check-bundle`: `PASS`); prior pre-`#803` run caught `exit failed reason=surface_cell_not_core` | **Claude (PC)** in-game gate -> **Owner** |
| **`B5_codsworth_sanctuary`** | **`REACHABLE`** *(keeper)* / **`NOT BUILT`** *(`MQ102`)* | `FO4SFMission.esm` `FO4SF_CodsworthKeeper` (`0x814`, `PlaceRadius = 300 m`, `HeldRadius = 3 m` at `(-2346.71, -1406.16, 111.73)`), converted `codsworth.nif` (`#361`), `20` `RobotMiniBotA` `.wem` greeting files | **Placeholder** Starfield `OutpostRobotMiniBotA_Garden` base actor; `MQ102` conversation/house sweep, Sanctuary house interiors, and bloatflies are `NOT BUILT`; Sanctuary workshop bench `0250FE` is `RECORDS ONLY` until tested in-game | Proximity `moved Codsworth` + `hold Codsworth` (`off=0.04 m`) verified in 17 Nov exterior log; untested in continuous `#816` walk | **Claude (PC)** continuous walk -> **Owner** |
| **`B6_concord_raiders`** | **`REACHABLE`** *(street fight)* / **`NOT BUILT`** *(Museum)* | `FO4TerrainCore.esm` road cells, `FO4ActorRaider.esm` up to `8` street raiders (`FO4_LvlRaider`), `FO4SFMission.esm` `FO4SF_Min00Quest` (`EngageRadius = 60 m`, `FindRadius = 20 m`, `stages 10 -> 20 -> 30`) | **Placeholder** Starfield firearms from hilltop `TEST-STATION` rack; **placeholder** Starfield `Credits` in world containers; Red Rocket `Dogmeat`, Museum interior (`0` load doors within `400 m`), roof T-45 frame, minigun, and Concord Deathclaw are `NOT BUILT` | Standalone Concord street fight verified previously; untested in continuous Sanctuary -> Concord walk on `#816` | **Claude (PC)** continuous walk (CrashWatch on) -> **Owner** |
| **`B7_preston_turnin`** | **`REACHABLE`** *(turn-in)* / **`TEST-STATION`** *(follow)* | `FO4SFMission.esm` proximity/activate turn-in (`TalkRadius = 3.0 m` or pressing **`E`** at `stage 30` -> `stage 40` -> `stage 200` complete) | **Placeholder** `FO4_LvlRaider_Calm` NPC record renamed to Preston (raider face/body/outfit, zero dialogue; Concord settlers `NOT BUILT`); **placeholder** `100` Starfield `Credits` (`0x00000F`, not Caps); `FO4SF_COMPreston.FollowTest` is a console-only `TEST-STATION` stand-in (`Card B-Card-2`) | `stage 200` proximity turn-in verified in prior standalone run; untested end-to-end on `#816` | **Claude (PC)** gate -> **Owner** |

---

## 2. Console-Free `PASS` and `FAIL` Lines (`B1`–`B7`)

Every step below uses normal controls (`W/A/S/D`, `E` to interact, `V` for VATS, `F7`/`M` for Pip-Boy/Map when `--with-pipboy` is installed, `Esc` for menu). Never open `~`.

### `B1_pod` — Vault 111 Cryo Pod Awakening & Step-Out (`REACHABLE`)
1. Select **New Game** from the Main Menu, then choose **Quick start** (or finish Character Creator) when Vault 111 fades in.
2. Press **`W`** / turn into the cryo bay aisle and walk toward the exit corridor.
- **Owner `PASS`:** Screen fades in cleanly inside Vault 111; walking forward steps straight into the aisle without snagging on the cryo pod; the O2/CO2 ring stays clear (never red); zero *Starfield* quest popups or companion barks appear. *(Known gap: `FO4SF_Min00`'s own `"When Freedom Calls"` notification currently appears at game start.)*
- **Owner `FAIL`:** Loading spinner hangs indefinitely; character snaps `8 m` sideways onto the cell marker or falls below the floor; O2 bar turns red on normal walking; or any Starfield quest objective appears on screen.
- **Log Check (`TOOLING` — `check_beginning_pilot.py check-logs`):** `PASS         B1_pod: pod settle ok=true, hold-off pass 2 stopped=195/199` *(evaluates `stopped=X of N` dynamically against `N` from that same line, allowing up to `4` non-running quests when `N >= 5`, so historical `2/5`, `34/37`, `162/165`, and `195/199` logs are judged accurately).*

### `B2_gear_door` — Vault 111 Gear Door & Catwalk (`#803`, `stage 30`, `REACHABLE`)
1. Follow the Vault 111 corridors to the overseer/exit chamber overlooking the Vault 111 gear door (`00126D`).
2. Approach within `2.5 m` of the gear-door control console spot (or press **`E`** on the gear door). *(Note: console terminal `OnActivate` is `NOT BUILT`; `InVault` currently triggers on `ConsoleRadius = 2.5 m` proximity or direct door open.)*
- **Owner `PASS`:** The Vault 111 gear plug pulls back and rolls aside, the catwalk connects, you can walk across the catwalk through the open doorway with zero invisible wall, and no elevator popup appears while at the console.
- **Owner `FAIL`:** Gear door fails to open or fails to resolve, an invisible barrier blocks the threshold, or the elevator `"Ride up"` prompt fires prematurely at the console.
- **Log Check:** `PASS         B2_gear_door: stage 30 reached (Vault 111 gear door opened)`

### `B3_exit_lift` — Vault 111 Floor Platform & Lift Ascent (`#803`, `'ascent carried confirmed'`, `REACHABLE`)
1. Walk across the catwalk onto the round Vault 111 elevator platform waiting at floor level `(-77.74, -3.96, -1.75)`.
2. When the **Vault 111 elevator** prompt appears, choose **Ride up** (button `0`).
- **Owner `PASS`:** The platform sits flush with the catwalk with its perimeter gates open; stepping aboard shows **Ride up**; `Play01` carries the player smoothly `+21.6 m` up the shaft (`~9.9 s`) into the exterior transition.
- **Owner `FAIL`:** The platform starts high up the shaft out of reach, closed gates block boarding, the player clips through the rising platform, or any `'exit failed reason=lift_*'` occurs.
- **Log Check:** `PASS         B3_exit_lift: ascent carried confirmed (Vault 111 lift ride completed without lift_ failure)` *(keys strictly on `'ascent carried confirmed'` with no `'exit failed reason=lift_*'`, NOT `stage 40`).*

### `B4_surface_landing` — Commonwealth Hilltop Surface Placement (`stage 40`) & Landing (`stage 200`, `REACHABLE`)
1. Wait `3–5 s` after the exterior loading screen finishes on the Vault 111 hilltop `(-2467.78, -1406.92, 128.11)`.
- **Owner `PASS`:** `FinishSurface` places the player onto the merged `FO4TerrainCore.esm` hilltop cell (`stage 40`), and `3.0 s` later `CheckLanding` confirms solid terrain (`stage 200`) with zero drop/fallback rescue.
- **Owner `FAIL`:** Player falls `> 3 m` onto the fallback marker (`fell z=...: fallback pos=`), `exit failed reason=` is logged (e.g. `surface_cell_not_core` or `landing_position_not_confirmed`), or exterior loading freezes.
- **Log Check:** `PASS         B4_surface_landing: stage 200 reached cleanly on Commonwealth hilltop (no exit failure or fallback)`

### `B5_codsworth_sanctuary` — Sanctuary Hills & Codsworth Keeper (`~120 m` East, `REACHABLE` with Placeholder Base)
1. Walk east down the Vault 111 hillside path into Sanctuary Hills (`(-2346.71, -1406.16, 111.73)`).
2. Approach **Codsworth** (**placeholder** `OutpostRobotMiniBotA_Garden` actor with converted `codsworth.nif` skin) outside the Sanctuary cul-de-sac house and press **`E`**.
- **Owner `PASS`:** Codsworth hovers within `<= 3 m` of his Sanctuary spot with intact Mister Handy geometry/materials and plays one of the `20` voiced greeting lines on `E`.
- **Owner `FAIL`:** Codsworth is absent, keeper relocation fails (`keeper gave up codsworth fails=10`), drifted `> 25 m` away, missing meshes/textures, or silent/crashing when activated.
- **Log Check:** `PASS         B5_codsworth_sanctuary: Codsworth relocated/held near Sanctuary spot without failures` *(ignores quest-init `'keeper load Codsworth'`; requires proximity `'moved Codsworth ... failed=false'` or `'hold Codsworth ... off<=25 ok=true'`).*

### `B6_concord_raiders` — Red Rocket Road & Concord Street Fight (`stages 10 -> 20 -> 30`, `REACHABLE`)
1. Cross the Sanctuary wooden bridge and follow the road southeast past Red Rocket into Concord (`~450 m`, toward `(-2011.14, -1697.54, 89.09)`).
2. Engage the Concord street raiders within `60 m` (using **placeholder** Starfield firearms from the hilltop `TEST-STATION` rack) until all street raiders are defeated.
- **Owner `PASS`:** Raiders and Preston relocate cleanly into Concord; approaching within `60 m` (or `20 m` of Preston) updates the HUD to **`When Freedom Calls: kill the raiders`** (`stage 20`); Preston stays friendly; defeating the last raider advances to **`When Freedom Calls: talk to Preston Garvey`** (`stage 30`).
- **Owner `FAIL`:** Game crashes approaching Concord, mission relocation fails `>= 10` times (`moved raider/Preston ... failed=true` or `keeper gave up preston fails=10`), Preston dies or targets the player, or the fight stalls after the raiders die. *(Mid-fight logs at `stage 20` without a failure report `IN_PROGRESS`, not `FAIL`.)*
- **Log Check:** `PASS         B6_concord_raiders: When Freedom Calls stages 10 -> 20 -> 30 completed`

### `B7_preston_turnin` — Preston Turn-In & Placeholder `100`-Credit Reward (`stages 40 -> 200`, `REACHABLE`)
1. Walk within `3 m` of **Preston Garvey** (**placeholder** `FO4_LvlRaider_Calm` NPC record renamed to Preston) outside the Museum entrance or press **`E`** on him.
- **Owner `PASS`:** Objective completes (`stage 40`), **`100` placeholder Starfield Credits** (`0x00000F`) are added to inventory, and the HUD displays **`When Freedom Calls: complete`** (`stage 200`), with Preston held calmly at the Museum entrance.
- **Owner `FAIL`:** Approaching/pressing `E` on Preston at `stage 30` fails to award `100` Credits, Preston dies/vanishes, or door hold overrides an armed `FO4SF_COMPreston` follow test. *(Logs at `stage 30` prior to turn-in report `IN_PROGRESS`, while `--require-all-pass` still exits non-zero until all 7 steps are `PASS`.)*
- **Log Check:** `PASS         B7_preston_turnin: stages 40 -> 200 reached, reward=100 placeholder credits (door-held; console-free follow is Card B-Card-2)`

---

## 3. Offline Verification Commands (`TOOLING`)

```bash
# 1. Verify offline that a staged bundle carries all B1..B7 plugins, scripts, meshes, and voices:
python scripts/testing/check_beginning_pilot.py check-bundle --bundle-dir <path/to/core-candidate-bundle>

# 2. Evaluate logs after a play session (IN_PROGRESS runs exit 0 unless --require-all-pass is set):
python scripts/testing/check_beginning_pilot.py check-logs \
  --newgame-log <path/to/fo4sf_newgame.0.log> \
  --mission-log <path/to/fo4sf_mission.0.log> \
  --require-all-pass
```

---

## 4. Follow-Up Cards for Remaining Work

1. **`B-Card-1` (`NOT BUILT` — Pending Claude (PC) Continuous In-Game Pilot Run on `#816`):** Install `#816` (`cd03411a`) via `bundle_install.py`, run one continuous console-free New Game walk from `B1_pod` through `B7_preston_turnin` (`Steps 1–15` in [core-candidate-pc-card.md](core-candidate-pc-card.md)) with CrashWatch armed, and run `check_beginning_pilot.py check-logs --require-all-pass`.
2. **`B-Card-2` (`TEST-STATION` Today -> Console-Free Preston Recruitment + Real Appearance):** Replace Preston's `FO4_LvlRaider_Calm` **placeholder** body/outfit, add a Concord turn-in dialogue scene, and wire a console-free `stage 200` recruitment prompt to `FO4SF_COMPreston` + `OnPlayerLoadGame` follow persistence (currently console-only via `cgf "FO4SF_COMPreston.FollowTest"`).
3. **`B-Card-3` (`RECORDS ONLY` Bench `0250FE` / `NOT BUILT` `MQ102` & `Min01`):** Verify in-game whether converted Sanctuary workshop bench `0250FE` opens Starfield build mode directly, and build `MQ102`-lite Codsworth dialogue/sweep plus a first-settlement `Min01`-lite objective.
4. **`B-Card-4` (`NOT BUILT` — Museum of Freedom Interior, Roof T-45 Frame & Concord Deathclaw):** Convert `ConcordMuseum01` interior cells with a paired load door (`#410`), place a `FO4SFPowerArmor.esm` (`#814`) frame on the Museum roof (currently `Spacesuit_Mark1` / chair **placeholders**), and stage the Concord Deathclaw finale.
5. **`B-Card-5` (`NOT BUILT` — Red Rocket `Dogmeat` Companion):** Decide stand-in creature body vs canine rig conversion, then place `Dogmeat` at Red Rocket (`(-2145, -1555)`) with a keeper and companion follow slot.
