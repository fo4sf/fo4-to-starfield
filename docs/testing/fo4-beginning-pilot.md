# Fallout 4 Playable-Beginning Pilot Checklist (`B1`–`B7`)

Goal: make the Fallout 4 beginning — **Vault 111 cryo pod -> gear door -> exit lift -> Commonwealth hilltop landing -> Sanctuary & Codsworth -> Red Rocket & Concord street fight -> Preston Garvey completion** — playable end-to-end by the owner without opening the developer console (`~`), using the 19-plugin Core Candidate (`#816` at `cd03411a`, `3.740 GiB` `Main.ba2`; or 21 plugins at `3.741 GiB` with `--with-pipboy`).

Offline bundle readiness and post-run log verdicts are checked by `scripts/testing/check_beginning_pilot.py` (`src/fo4sf/beginning_pilot.py`).

---

## 1. End-to-End Beginning Matrix

| Step | Location & Sequence | In Candidate (`#816` `cd03411a`) | Held Off / Out of Slice | Verification State | Who Runs Next |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`B1_pod`** | **Vault 111 Cryo Pod Awakening & Step-Out** | `FO4SFNewGame.esm` (`StartupQuest_DO` override, `-2.5 m` pod step-out `#803`, `PodLift = 0.3 m`, `ClearInventory` + vault suit + `+100` `O2Capacity`), `FO4Port.esm` (`FO4Port_Vault111Cryo`) | `195 / 199` vanilla Starfield quests (`#807` Pass 1+2 `HoldOff` + `MQ101Debug = 2`); pre-war Sanctuary house/vault sprint & cryo spouse scene skipped | **Pod settle (`ok=true`) & `3.0 m` walk-out verified in-game (17 Nov)** on `#802+#803`; `195/199` hold verified offline in `#816` | **Claude (PC)** full `#816` bundle check -> **Owner** |
| **`B2_gear_door`** | **Vault 111 Cryo Corridors -> Gear Door (`stage 30`)** | `FO4SFVaultGearDoor.esm` (`#802`, `89` `.mesh`/`.nif`/`.mat` assets, animated `VltGearDoor01` `0x00126D` + catwalk bridge) + `FO4SFNewGame.esm` `ConsoleRadius = 2.5 m` | Vault-Tec corpse Pip-Boy pickup animation (`F7`/`M` Pip-Boy UI `#817` works directly without skeleton cutscene); scripted interior radroach ambush | **Verified offline (`check-bundle`: `PASS`)**; untested in continuous `#816` bundle walk | **Claude (PC)** in-game gate -> **Owner** |
| **`B3_exit_lift`** | **Vault 111 Floor Platform -> Lift Ascent (`stage 40`)** | `FO4SFExitLift.esm` (`#802`, `48` assets, floor-level platform at `(-77.74, -3.96, -1.75)`, gates open at floor, `+21.6 m` / `~9.9 s` ascent) + `ExitMessage` (`0x801` Ride up / Stay) | Exterior Vault 111 cog-lid sunlight cutscene during cell load | **Verified offline (`check-bundle`: `PASS`)**; untested in continuous `#816` bundle walk | **Claude (PC)** in-game gate -> **Owner** |
| **`B4_surface_landing`** | **Commonwealth Vault 111 Hilltop Arrival (`stage 200`)** | `FO4TerrainCore.esm` (`64x64` heightmap + terrain masks + `ExitAnchorId`) + `FO4SFNewGame.esm` `FinishSurface` (`(-2467.78, -1406.92, 128.11)`, `FallDrop = 3.0 m` fallback guard) + `FO4SFCoreCandidate.esm` | World region beyond `64x64` border (`#495`); `MQ102` journal wrapper (`FO4SFMission.esm` starts `"When Freedom Calls"` `stage 10` immediately) | **Verified offline (`check-bundle`: `PASS`)**; untested with all 19/21 `#816` plugins active together | **Claude (PC)** in-game gate -> **Owner** |
| **`B5_codsworth_sanctuary`** | **Sanctuary Hills Trail, Bridge & Codsworth** | `FO4SFMission.esm` `FO4SF_CodsworthKeeper` (`0x814`, `PlaceRadius = 300 m`, `HeldRadius = 3 m` at `(-2346.71, -1406.16, 111.73)`), converted `codsworth.nif` (`#361`), `20` `RobotMiniBotA` `.wem` voice files, `FO4SFWorkshop.esm` (`#813` scrap + C.A.M.P./settlement kit) | `MQ102` house-to-house Sanctuary bloatfly patrol scenes; pre-linked Sanctuary Red Workshop bench (`Card B-Card-3`) | **Keeper + mesh/voice verified in standalone runs** & **offline (`check-bundle`: `PASS`)**; untested in continuous hilltop -> Sanctuary walk on `#816` | **Claude (PC)** continuous walk -> **Owner** |
| **`B6_concord_raiders`** | **Red Rocket Road -> Concord Street Ambush (`stages 10 -> 20 -> 30`)** | `FO4TerrainCore.esm` road cells, `FO4ActorRaider.esm` Concord raiders (`0x803+`), `FO4SFMission.esm` `FO4SF_Min00Quest` (`EngageRadius = 60 m`, `FindRadius = 20 m`, `Preston.IgnoreFriendlyHits(True)`), `FO4SFCombat.esm` (`#821` limb damage, DT/DR, slow-time VATS) | Red Rocket `Dogmeat` quadruped companion (`Card B-Card-5`); Museum of Freedom interior door (`#410` / historical `0x2bf016b`), roof T-45 frame & Concord Deathclaw (`Card B-Card-4`) | **Standalone Concord combat verified previously** & **offline (`check-bundle`: `PASS`)**; untested in continuous Sanctuary -> Concord walk on `#816` | **Claude (PC)** continuous walk (CrashWatch on) -> **Owner** |
| **`B7_preston_turnin`** | **Preston Garvey Turn-In & `100`-Credit Completion (`stages 40 -> 200`)** | `FO4SFMission.esm` console-free turn-in (`TalkRadius = 3.0 m` or pressing **`E`** at `stage 30` -> `stage 40` -> `+100` Credits -> `stage 200` complete); `FO4SF_COMPreston.pex` (`0x815` follow package `0x0301C5`) | Console-free story recruitment dialogue at `stage 200` (`FO4SF_COMPreston.FollowTest` currently stays test-only per `preston-follow-pc-card.md` until wired in `Card B-Card-2`) | **Verified offline (`check-bundle`: `PASS`)**; `stage 200` turn-in verified in prior standalone run; untested end-to-end on `#816` | **Claude (PC)** gate -> **Owner** (turn-in is console-free today) |

---

## 2. Console-Free `PASS` and `FAIL` Lines for the Owner (Zero Console Commands)

Every step below uses normal controls (`W/A/S/D`, `E` to interact, `V` for VATS, `F7`/`M` for Pip-Boy/Map, `Esc` for menu). Never open `~`.

### `B1_pod` — Vault 111 Cryo Pod Awakening & Step-Out
1. Select **New Game** from the Main Menu, then choose **Quick start** (or finish Character Creator) when Vault 111 fades in.
2. Press **`W`** / turn into the cryo bay aisle and walk toward the exit corridor.
- **Owner `PASS`:** Screen fades in cleanly inside Vault 111; walking forward steps straight into the aisle without snagging on the cryo pod; the O2/CO2 ring stays clear (never red); zero Starfield mission banners or companion barks appear.
- **Owner `FAIL`:** Loading spinner hangs indefinitely; character snaps `8 m` sideways onto the cell marker or falls below the floor; O2 bar turns red on normal walking; or any Starfield quest objective appears on screen.
- **Log Check (`check_beginning_pilot.py check-logs`):** `PASS      B1_pod: pod settle ok=true, hold-off pass 2 stopped=195/199`

### `B2_gear_door` — Vault 111 Gear Door & Catwalk (`stage 30`)
1. Follow the Vault 111 corridors to the overseer/exit chamber overlooking the giant Vault 111 gear door.
2. Walk up to the gear-door control console (or gear door `00126D`) and press **`E`**.
- **Owner `PASS`:** The heavy Vault 111 gear plug pulls back and rolls aside, the catwalk connects, you can walk across the catwalk through the open doorway with zero invisible wall, and no elevator popup appears while you are still at the console.
- **Owner `FAIL`:** Pressing `E` does nothing, the gear door opens visually but an invisible barrier blocks the threshold, or the elevator `"Ride up"` prompt fires prematurely at the console.
- **Log Check:** `PASS      B2_gear_door: stage 30 reached (Vault 111 gear door opened)`

### `B3_exit_lift` — Vault 111 Floor Platform & Lift Ascent (`stage 40`)
1. Walk across the catwalk onto the round Vault 111 elevator platform waiting at floor level `(-77.74, -3.96, -1.75)`.
2. When the **Vault 111 elevator** prompt appears, choose **Ride up** (button `0`).
- **Owner `PASS`:** The platform sits flush with the catwalk with its perimeter gates open; stepping aboard shows **Ride up**; the gates close and the platform carries you smoothly up the shaft (`~10 s`) into the surface load transition.
- **Owner `FAIL`:** The platform is stuck high up the shaft out of reach, closed gates block boarding, the player falls through the moving platform, or the ride finishes still inside Vault 111.
- **Log Check:** `PASS      B3_exit_lift: stage 40 reached (Vault 111 lift ride completed)`

### `B4_surface_landing` — Commonwealth Hilltop Surface Landing (`stage 200`)
1. Wait `3–5 s` after the exterior loading screen finishes on the Vault 111 hilltop `(-2467.78, -1406.92, 128.11)`.
- **Owner `PASS`:** You stand on solid rocky hilltop terrain above Sanctuary Hills (no drop or teleport rescue), and the HUD displays **`When Freedom Calls: find the Last Minutemen`** (plus **`FO4SF Core Walk ready ahead...`** when `FO4SFCoreCandidate.esm` is active).
- **Owner `FAIL`:** You drop through the ground on arrival, land in water or grey void, or freeze during exterior loading.
- **Log Check:** `PASS      B4_surface_landing: stage 200 reached cleanly on Commonwealth hilltop`

### `B5_codsworth_sanctuary` — Sanctuary Hills & Codsworth (`~120 m` East)
1. Walk east down the Vault 111 hillside path into Sanctuary Hills (`(-2346.71, -1406.16, 111.73)`).
2. Approach **Codsworth** outside the Sanctuary cul-de-sac house and press **`E`**. *(Optional: deploy `FO4SF_SettlementKit` / `FO4SF_CAMPKit` from **Inventory -> Misc** to test workshop scrap & build mode right in Sanctuary.)*
- **Owner `PASS`:** Codsworth hovers calmly in front of the Sanctuary house with intact Mister Handy chrome geometry/materials and plays voiced audio when activated (`E`).
- **Owner `FAIL`:** Codsworth is absent, floating/drifting > 25 m away, missing meshes/textures, or silent/crashing when activated.
- **Log Check:** `PASS      B5_codsworth_sanctuary: Codsworth placed/held in Sanctuary without failures`

### `B6_concord_raiders` — Red Rocket Road & Concord Street Fight (`stages 10 -> 20 -> 30`)
1. Cross the Sanctuary wooden bridge, follow the road south past the Red Rocket truck stop into Concord (`~450 m` southeast, toward `(-2011.14, -1697.54, 89.09)`).
2. Engage the Concord street raiders within `60 m` (using firearms from the hilltop Combat rack or starter gear, and **`V`** for slow-time VATS if desired) until all street raiders are down.
- **Owner `PASS`:** Raiders and Preston materialize cleanly in Concord without hitching or crashing; approaching within `60 m` (or `20 m` of Preston) updates the HUD to **`When Freedom Calls: kill the raiders`**; Preston stays friendly even if grazed; defeating the last raider updates the HUD to **`When Freedom Calls: talk to Preston Garvey`**.
- **Owner `FAIL`:** Game crashes approaching Concord/Museum, raiders fail to appear or sink below the street, Preston turns hostile against the player, or the objective never advances after the raiders die.
- **Log Check:** `PASS      B6_concord_raiders: When Freedom Calls stages 10 -> 20 -> 30 completed`

### `B7_preston_turnin` — Preston Garvey Turn-In & `100`-Credit Reward (`stages 40 -> 200`)
1. Walk up to **Preston Garvey** outside the Museum entrance (`within 3 m`) or press **`E`** on him.
- **Owner `PASS`:** Objective completes, **`100` Credits** are added to your inventory, and the HUD displays **`When Freedom Calls: complete`**, with Preston standing calmly at the Museum entrance. *(Note: Preston remains stationed at the entrance until `Card B-Card-2` wires console-free recruitment dialogue to `FO4SF_COMPreston`.)*
- **Owner `FAIL`:** Approaching/pressing `E` on Preston at `stage 30` awards no Credits or leaves `"talk to Preston Garvey"` incomplete.
- **Log Check:** `PASS      B7_preston_turnin: stages 40 -> 200 reached, reward=100 credits`

---

## 3. Offline Verification Commands (Fixed & Available Now)

```bash
# 1. Verify offline that a staged bundle carries all B1..B7 plugins, scripts, meshes, and voices:
python scripts/testing/check_beginning_pilot.py check-bundle --bundle-dir <path/to/core-candidate-bundle>

# 2. Evaluate logs after a Claude (PC) or Owner play session (zero console needed):
python scripts/testing/check_beginning_pilot.py check-logs \
  --newgame-log <path/to/fo4sf_newgame.0.log> \
  --mission-log <path/to/fo4sf_mission.0.log>
```

---

## 4. Follow-Up Cards for Remaining Non-Offline Work

1. **`B-Card-1` (Claude (PC) Continuous In-Game Pilot Run on `#816`):** Install `#816` (`cd03411a`) via `bundle_install.py`, run one continuous console-free New Game walk from `B1_pod` through `B7_preston_turnin` (`Steps 1–15` in [core-candidate-pc-card.md](core-candidate-pc-card.md)) with CrashWatch armed, and run `check_beginning_pilot.py check-logs --require-all-pass`.
2. **`B-Card-2` (Console-Free Preston Recruitment Dialogue at `stage 200`):** Wire `FO4SFListDialogue` / `OnActivate` at `FO4SF_Min00Quest` `stage 200` so selecting *"Join me"* invokes the `FO4SF_COMPreston` follow sequence (`BeginFollow` + `DefaultMaster_FollowPackage` `0x0301C5`) without opening the console (`cgf "FO4SF_COMPreston.FollowTest"`), while preserving Courier's `preston-follow-pc-card.md` contract before `stage 200`.
3. **`B-Card-3` (`MQ102` Sanctuary Sweep & Pre-Placed Sanctuary Workshop Bench):** Add optional Codsworth Sanctuary sweep stages (`MQ102`) and link Sanctuary's native exterior Red Workshop bench directly into `FO4SFWorkshop.esm` so building in Sanctuary needs no dropped `FO4SF_CAMPKit`.
4. **`B-Card-4` (Museum of Freedom Interior, Roof T-45 Frame & Concord Deathclaw):** Connect Concord Museum paired load door (`#410`, after `meshcheck` clearance for historical `0x2bf016b`), place a `FO4SFPowerArmor.esm` (`#814`) frame on the Museum roof, and stage the exterior Deathclaw finale.
5. **`B-Card-5` (Red Rocket `Dogmeat` Quadruped Companion):** Extend creature skeleton/animation binding for canine rigs and register `Dogmeat` at Red Rocket (`(-2145, -1555)`) into `FO4SFCompanions.esm`'s dog/humanoid companion slot.
