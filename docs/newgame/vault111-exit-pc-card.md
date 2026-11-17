# Vault 111 Clean Exit PC Card (Main-Based Production Slice)

## Purpose

Enable leaving Vault 111 end-to-end in a real New Game on `main` (both **Create character** and **Quick start**) with **zero console commands and zero `tcl`**:

1. **Walkable pod start (`--pod-step -2.5` default):** `dotnet/NewGame` (`DefaultPodStep = -2.5f`) and `make_newgame.py` (`DEFAULT_POD_STEP = -2.5`) place the player 2.5 m along `-Y` in front of `MQPlayerCryopodREF` (`0004A011`) at `(9.143, -6.614, -1.029)` m (`PodLift = 0.3` -> settle drop `~0.12 m`), avoiding the rear wall pocket behind `+1.0 m` and the canopy collision at `-1.0 m`. Pod rotation and `PodHeading = 0` are unchanged (the player turns around after stepping out).
2. **Production gear door and catwalk (`FO4SFVaultGearDoor.esm`):** `make_cog_door.py stage --production-cog` packages the seam-repaired animated gear door override (`DOOR 0x00DEF9` on `REFR 00126D`, `_anim` asset path) without `FO4SF_CogDoorQuest` or probe scripts. `InVault` advances `stage 20 -> 30` whether the player presses `E` directly on the gear door (`openState` `1` or `2`) or stands at the console (`ConsoleX/Y/Z`).
3. **Floor-waiting, open-gate carrying lift (`FO4SFExitLift.esm`) and platform-only prompt:**
   - `make_anim_console.py stage --production-lift` builds `FO4SFExitLift.esm` (`stage3=StateA_Play,stage2=StateB_Play`, `toggle`, `--rest-after stage2`, `37` moving collision bodies, zero probe quest/PEX). `StateA_Idle` holds the final frame of `stage2`: `b_Platform` rests at the bottom of the shaft (`-139.1` FO4 units) while `b_Gate01` (`+175.0`), `b_Gate02` (`+93.6`), and their moving collision bodies (`c_Gate01B`, `c_Gate02B`) wait **OPEN** overhead.
   - **Measured `moving_bodies = 37` provenance (`12` vs `45` vs `37`):** The earlier `12` figure came from pre-`fo4_door_bodies` commit `5e8da96a` (one bounding box per moving geometry bone across `12` bones). Once `fo4_door_bodies` (`convert_static.py`) carried `VltElevator.nif`'s Havok `bhkPhysicsSystem` (`block 715`, `17` `bhkNPCollisionObject` attachments), `door_collision.plan` previously treated `anim_object.fill_static_tracks`'s `"static": True` root track on stationary `VltElevator` as animated, leaking `8` stationary shaft-collar frame bodies (`c_ShaftCollision01..08`, `body_id 0..7`) into `moving_bodies` (`37 + 8 = 45`). Filtering `if not track.get("static")` in `door_collision.py` leaves the exact `37` genuinely moving FO4 convex hull parts: `25` on `b_Platform` (`Cylinder001 (190 Radius)`, `body_id 10`), `3` on `b_Gate01` (`c_Gate01B`, `body_id 11`), `3` on `b_Gate02` (`c_Gate02B`, `body_id 12`), `1` on `b_Hatch Left` (`body_id 13`), `1` on `b_Hatch Right` (`body_id 14`), `2` on `b_CounterWeight` (`c_Weight` + `c_Cable`, `body_id 15..16`), `1` on `c_ExteriorLightR` (`body_id 8`), and `1` on `c_ExteriorLightL` (`body_id 9`).
   - Choosing **Ride up** plays `Play01` (`StateA_Play` = `stage3`, `9.8667 s`), which **closes the gates during the first ~1.2 s of the ride** and carries the player `+21.6 m` up the shaft (`-1.72 m -> +19.88 m`). `LiftDoneMargin = 0.25` s (`~7.5` frames at `30 Hz`) accepts the observed `9.794 s` `Done` timestamp (`>= 9.6167 s`) while rejecting the stale `0.068 s` `Done` from an earlier clip.
   - `Points` resolves `PlatformX/Y/Z` from `RespecMoveMarker` (`0001B29E`, `(-77.742, -3.958, -1.751)` m on the center of `b_Platform`) rather than `V111ElevatorREF`'s NIF origin (`000244EB`, `(-70.392, -2.742, -0.114)` m out on the catwalk approach), with `PlatformRadius = 2.0` m and `stage >= 30` required. The prompt therefore fires **only inside the lift cage**, never at the console (`-53.7 m`) or catwalk (`-70.4 m`).
4. **Core-cell surface arrival and post-arrival discovery:** `FinishSurface` applies `SetPosition` onto the merged exterior arrival `(-2467.78, -1406.92, 128.11)` **before** checking that `GetParentCell()` belongs to `FO4TerrainCore.esm`, then confirms landing and requests Vault 111 discovery (`SetMarkerDiscovered`) on the exterior surface after the load.

---

## Architecture Notes (Prompt Questions 1b & 1c)

### 1. Why `MoveTo` Reached a Procedural `Surface (FF...)` Cell in `MarsPlanetWorld (FF...)`

- **Why the runtime world ID is `MarsPlanetWorld... (FF...)`:** `FO4Core_Commonwealth` (`03000803`) is mounted as a planetary surface overlay world. When Starfield instantiates the planet tile at runtime, it creates a dynamic `WorldSpace` (`MarsPlanetWorld...`, form prefix `0xFF`) and merges `FO4TerrainCore.esm`'s exterior grid cells into that runtime world shifted by `MergeOffset = (-1200.0, -2700.0)` m.
- **Why `MoveTo(anchor)` landed on bare ground in `Surface (FF...)`:** Persistent references stored in the overlay world's persistent cell (`030A775B` `FO4Core_CommonwealthMapMarkerVault111` at unmerged `(-1275.31, +1305.28, 127.21)` m) are **not** shifted by the grid merge. Calling `player.MoveTo(anchor)` places the player in `MarsPlanetWorld... (FF...)` at unmerged `(-1275.31, +1305.28)` m, `2,954 m` northeast of the merged Commonwealth grid, where Starfield generates a plain procedural planet cell (`Surface FF00A492`).
- **Why `#796` failed and why `main`'s two-step move works:** `#796` checked `currentCell.GetFormID() / 16777216 == anchor.GetFormID() / 16777216` *before* calling `player.SetPosition`, aborting on tick 1 with `surface_cell_not_core`. Calling `player.SetPosition(ArrivalX + MergeOffsetX, ArrivalY + MergeOffsetY, ArrivalZ)` (`(-2467.78, -1406.92, 128.11)` m) *first* synchronously loads the merged `FO4TerrainCore.esm` exterior cell (`03......`, e.g. `Surface 03000CF0`) inside that same runtime `MarsPlanetWorld... (FF...)`. `FinishSurface` now verifies the `0x03` core cell prefix and 3D coordinates *after* `SetPosition` (with up to `SurfaceTries = 3` ticks if cell streaming takes an extra tick).
- **Self-contained marker attachment on arrival:** When `FO4SFMapMarkers.esm` is not active in a clean New Game load order, nothing else moves `030A775B` from unmerged `(-1275.31, +1305.28)` to merged `(-2475.31, -1394.72)`. In `RequestArrivalDiscovery`, if `030A775B` is not yet in `arrivalWorld` at `(Fallback + MergeOffset)`, the quest moves it once (`Enable(False)` + `MoveTo(player, ...)` + `SetPosition`), waits for the next loaded tick to confirm world and merged XYZ, and then calls `SetMarkerDiscovered()` once.

### 2. Comparison with Starfield's Elevators and Fort Hagen's Elevators

| System | Mechanism | Doors / Gates | Player Trigger & Transfer |
| :--- | :--- | :--- | :--- |
| **Starfield short-rise lifts** (`MovingPlatformMasterScript`, `ElevatorMasterScript`) | Single animated `ACTI` with Havok keyframed collision bodies driven between two graph states via `PlayAnimation`. | Optional paired door refs or animated barrier sub-bones. | Activator / trigger volume mounted on the platform car itself; physics carries the rider. |
| **Starfield load elevators** (`LoadElevatorManagerScript`, `CityNAMASTElevatorActivatorScript`) | Separate inner/outer door `ACTI`s + cab shell; no full-shaft travel needed across interior/exterior load boundaries. | Close cab doors before transfer; open outer doors after destination load. | Panel button inside the cab triggers door close -> `MoveTo` / load door -> arrival door open. |
| **Fort Hagen interior 2-stop lift** (`00134462` `ElevatorMasterScript` + `00134467` `platformhelperfree01`) | Multi-record linked-ref kit: controller `ACTI` (`00134462`), helper platform (`00134467`), call buttons, and upper/lower doors, plus `XESP` enable-parent planks (`0013A357`). | Separate `DOOR` records opened/closed by controller script; currently blocked in `FO4Port.esm` when controller/helper refs and `XESP` scripts are absent. | Call button / cab panel activator scripts linked to the master controller. |
| **Fort Hagen load elevators** (`0016850D` Command Center, `0016852C` Roof, `LoadElevatorDoorUtility`) | Paired load-door elevator cabs plus scripted roof security gate (`000BF414`). | Utility script opens cab door on cell entry and closes on exit; roof gate (`000BF414`) requires script/SetOpen. | Autoload / activator door inside the cab after the outer door opens. |
| **Vault 111 exit (`FO4SFExitLift.esm` + `FO4SF_NewGameQuest`)** | Hybrid: real `21.6 m` animated shaft inside `Vault111Cryo` (`VltElevator.nif` on `000244EB`, `37` moving collision hulls across `8` animated bones) + cross-world transfer at shaft top (`+19.88 m`, matching `0001F180` at `+22.34 m`). | Self-contained in `VltElevator.nif`: `StateA_Idle` (`stage2` end) holds `b_Gate01`/`b_Gate02` open; `Play01` (`stage3`) closes gates in `~1.2 s` before lifting. | Stand check on `RespecMoveMarker` (`0001B29E`, `2.0 m` radius) inside the cage -> `Play01` carries rider `+21.6 m` -> `Surface` / `FinishSurface` / `CheckLanding`. |

---

## Exact Build & Stage Commands for Claude (PC)

Run with the game closed in a fresh staging folder, using the repo's standard tool paths (`<SF_DATA>`, `<FO4_DATA>`, `<PORT_DIR>`, `<CORE_SET_DIR>`, `<CALUMI_DLL>`, `<COLLISION_NIF>`, `<TEXCONV>`, `<CONTENT_ZIP>`, `<PAPYRUS_COMPILER>`):

### Step 1 — Stage Production Gear Door (`FO4SFVaultGearDoor.esm`, no probe quest)

```powershell
python scripts/newgame/make_cog_door.py stage `
  --production-cog `
  --out <STAGE_ROOT>/cog-door-prod `
  --starfield-data <SF_DATA> `
  --port-data <PORT_DIR> `
  --fo4-data <FO4_DATA> `
  --door-anim-dll <CALUMI_DLL> `
  --collision-template <COLLISION_NIF> `
  --texconv <TEXCONV> `
  --content-resources <CONTENT_ZIP>
```

Expected output: `FO4SFVaultGearDoor.esm`, converted `_anim` mesh/rig/clips/geometries/materials, `offline_check.txt` (`all checks pass`), `plan.json` (`kind = "cog-door-production"`), and **no** `Data/Scripts/*.pex`.

### Step 2 — Stage Production Floor-Start Lift (`FO4SFExitLift.esm`, no probe quest)

```powershell
python scripts/newgame/make_anim_console.py stage `
  --production-lift `
  --edid FO4Port_acti_0244ef_fallout4 `
  --states stage3=StateA_Play,stage2=StateB_Play `
  --idles toggle `
  --rest-after stage2 `
  --out <STAGE_ROOT>/exit-lift-prod `
  --starfield-data <SF_DATA> `
  --port-data <PORT_DIR> `
  --fo4-data <FO4_DATA> `
  --door-anim-dll <CALUMI_DLL> `
  --collision-template <COLLISION_NIF> `
  --texconv <TEXCONV> `
  --content-resources <CONTENT_ZIP>
```

Expected output: `FO4SFExitLift.esm`, converted `_anim` mesh/rig/clips (`37` moving bodies: `25` `b_Platform` + `3` `b_Gate01` + `3` `b_Gate02` + `6` hatch/counterweight/light hulls, `StateA_Idle` = `stage2` end pose, `StateA_Play` = `9.8667 s` `+21.6 m`), `offline_check.txt` (`all checks pass`), `plan.json` (`kind = "exit-lift"`), and **no** `Data/Scripts/*.pex`.

### Step 3 — Stage `FO4SFNewGame.esm` (with `--cog-door` + `--exit-lift`; `--pod-step -2.5` is automatic)

```powershell
python scripts/newgame/make_newgame.py stage `
  --out <STAGE_ROOT>/newgame-stage `
  --cog-door <STAGE_ROOT>/cog-door-prod `
  --exit-lift <STAGE_ROOT>/exit-lift-prod `
  --fo4 <FO4_DATA>/Fallout4.esm `
  --port <PORT_DIR>/FO4Port.esm `
  --port-ids <PORT_DIR>/formids.json `
  --core <CORE_SET_DIR>/FO4TerrainCore.esm `
  --starfield <SF_DATA>/Starfield.esm `
  --compiler <PAPYRUS_COMPILER> `
  --content-resources <CONTENT_ZIP>
```

Verify in `<STAGE_ROOT>/newgame-stage/plan.json`:
- `points.pod.step_m == -2.5`, `points.pod.pos` near `[9.143, -6.614, -1.029]`, `points.pod.heading == 0.0`
- `points.platform.stand_src == "0001B29E"`, `points.platform.pos` near `[-77.742, -3.958, -1.751]`
- `options.hold` includes all S13 groups (`MQ00`, `MQ101`, `MQ101PostQuest`, `MQ_TutorialQuest_Misc04`, `SQ_ENV`, companions, audio/tutorials, city/faction)

### Step 4 — Prepare Clean Core (if starting from an already-folded set), Fold & Verify

If your core set (`<INSTALLED_SET_DIR>`) already includes an earlier `FO4SFNewGame.esm`, prepare `<STAGE_ROOT>/clean-core` first by hardlinking every file **except** `FO4SFNewGame.esm` (and any prior `FO4SFVaultGearDoor.esm` / `FO4SFExitLift.esm`), its four `Data/Scripts/FO4SF_NewGame*.pex` files, and `README.txt`, then writing `<STAGE_ROOT>/clean-core/README.txt` as a **new file** (never editing a hardlink in place) that drops `FO4SFNewGame.esm` from its `exp_install.py install ... --plugins ...` line:

```powershell
python -c "
import os, re, sys
from pathlib import Path
src, dst = Path(sys.argv[1]), Path(sys.argv[2])
drop_esm = {'fo4sfnewgame.esm', 'fo4sfvaultgeardoor.esm', 'fo4sfexitlift.esm'}
drop_pex = {f'data/scripts/fo4sf_newgame{s}.pex' for s in ('quest', 'looks', 'special', 'version')}
for dp, _, fns in os.walk(src):
    out_d = dst / Path(dp).relative_to(src)
    out_d.mkdir(parents=True, exist_ok=True)
    for fn in fns:
        s = Path(dp) / fn
        r = s.relative_to(src).as_posix().lower()
        if r == 'readme.txt' or r in drop_esm or r in drop_pex:
            continue
        os.link(s, out_d / fn)
rx = re.compile(r'(exp_install\.py install\b.*--plugins )(\S+)')
lines = (src / 'README.txt').read_text(encoding='utf-8').splitlines()
fix = lambda ln: rx.sub(lambda m: m.group(1) + ','.join(p for p in m.group(2).split(',') if p.lower() not in drop_esm), ln)
(dst / 'README.txt').write_text('\n'.join(fix(ln) for ln in lines) + '\n', encoding='utf-8', newline='\n')
" <INSTALLED_SET_DIR> <STAGE_ROOT>/clean-core
```

*(If `<CORE_SET_DIR>` has never had `FO4SFNewGame.esm` folded into it, pass `<CORE_SET_DIR>` directly below in place of `<STAGE_ROOT>/clean-core`. Byte-identical shared assets already in the core set — such as `Data/materials/fo4port/_neutral.mat` — are verified by `sha256` during `fold` without copying; differing files are refused.)*

```powershell
python scripts/newgame/make_newgame.py fold `
  --core-dir <STAGE_ROOT>/clean-core `
  --stage <STAGE_ROOT>/newgame-stage `
  --out <STAGE_ROOT>/folded-v111-exit `
  --port <PORT_DIR>/FO4Port.esm

python scripts/newgame/make_newgame.py verify `
  --exp-dir <STAGE_ROOT>/folded-v111-exit `
  --plan <STAGE_ROOT>/newgame-stage/plan.json `
  --port <PORT_DIR>/FO4Port.esm
```

Expected output: `verify: ok` (exit `0`), with `<STAGE_ROOT>/folded-v111-exit/README.txt` widening the clean core set's `--plugins` list by appending `,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFNewGame.esm` (for example `FO4ActorRaider.esm,FO4SFMission.esm,FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4SFVaultGearDoor.esm,FO4SFExitLift.esm,FO4SFNewGame.esm`, with `FO4Port.esm` active alongside it in the game load order).
Install when authorized (game closed) using the exact `exp_install.py install ... --pack` command printed by `fold`.

---

## In-Game Test Procedure (Both Starts, Zero Console / Zero `tcl`)

Run **two** fresh **New Game** sessions from the main menu with **no console commands** (`tcl`, `moveto`, `setstage` forbidden):

1. **Session 1 — Character Creator (`button=0`):**
   - Start **New Game** -> Vault 111 loads -> choose **Create character** (`button=0`) -> confirm looks-only menu (`RaceMenuMode=2`) -> finish/close creator (`stage 20`).
   - Turn around from `(9.143, -6.614, -1.029)` and walk normally (collision on, no `tcl`) through the cryo hall and corridors to the Vault 111 gear door.
   - Press `E` on the gear door (or walk to the console): verify the gear door opens and the catwalk bridge connects (`stage 30`), with **no** elevator prompt firing at the console or along the catwalk.
   - Walk across the catwalk to the shaft: verify the lift platform is **waiting at the bottom** and its safety gate is **OPEN**.
   - Walk onto the platform floor (`(-77.742, -3.958, -1.751)`): verify the **Vault 111 elevator** prompt appears **only** once on the platform -> choose **Ride up** (`button=0`).
   - Verify the safety gate **closes at the start of the ride** and the platform physically carries the player upward `+21.6 m` over `~9.9 s`.
   - Verify exterior transfer lands on the Commonwealth Vault 111 surface (`(-2467.78, -1406.92, 128.11)`, core cell `03......`), settles for `3 s`, logs `arrival discovery requested`, and completes at `stage 200`.
2. **Session 2 — Quick Start (`button=1`):**
   - Quit to main menu / desktop, start a fresh **New Game**, choose **Quick start** (`button=1`), and repeat the identical walk -> `E` on gear door -> walk onto open platform -> ride up -> surface arrival flow with zero console usage.

### Log Check (`python scripts/newgame/make_newgame.py log`)

**PASS Criteria (both sessions):**
- Exit code `0` from `make_newgame.py log`, `exit_failure` is `null`, `stood_down` is `false`.
- `stages` contains `[10, 20, 30, 40, 200]`.
- `pod_settle` shows `ok=true` near `(9.143, -6.614, -0.85.. -0.90)` (`drop ~0.12 m`), and the player walks cleanly to the door and lift with zero `tcl`.
- Zero `elevator prompt` lines while `pos` is near console `(-53.7, -3.7)` or catwalk `(-70.4, -2.7)`; `elevator prompt button=0` occurs only near `(-77.7, -4.0, -1.7)`.
- `ascent` contains `play accepted=True`, `done elapsed=...` (`>= 9.6167 s` from `LiftSeconds - LiftDoneMargin`), and `carried confirmed elapsed=... z=19.8...`.
- `surfaced` shows `surface setposition ok=True set=1 pos=... target=... core_cell=True cell=Cell <Surface (03......)> world=WorldSpace <MarsPlanetWorld... (FF......)>`.
- `arrival_discovery_requested` is non-null (`ref=...0A775B...`), `landed` is `true`, and `stage 200` is reached.
