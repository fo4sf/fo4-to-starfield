Titles: Fallout 4 -> all 7 Fallout titles (FO4, FO3, FNV, FO1, FO2, Tactics, FO76) | Modes: Story & Warfare (+ Survival hardcore layer) | Track: Track 1 (Round 11 Pre-Build Probes P1 & P4)

# Round 11 Pre-Build Probes `P1` (Museum of Freedom Interior, Lossless `FO4Port`, Confirmed Load Doors, `NAVM` Raider Climb & Pre-War Vault 111) and `P4` (`10mm Pistol` Alone) Session Card (`Plan §6 / §6.1 / P3 / R8 / R15`)

> **NEW GAME needed (`A16` / `R15`) & Scope / Honesty Banner:**
> - **Whole Scope:** Title: **Fallout 4** | Mode: **Story** (`candidate-2g-fix` `13`-plugin Track-1 baseline + standalone reversible Probe `P1` or Probe `P4` overlay — **run `P1` and `P4` as short standalone probes and uninstall each cleanly when done**; never touch `candidate-2g`, `candidate-2g-fix`, or any older candidate folder) | Track: **Track 1 pre-build probes (`P1` + `P4` ONLY)** before building full `candidate-2h` (`S2`–`S6` + remaining guns).
> - **`prototype, offline` — `OFFLINE ONLY — UNPROVEN IN GAME`:** Both Probe `P1` (`<p1-stage-dir>`) and Probe `P4` (`<p4-stage-dir>`) are **`TEST-STATION` (`prototype, offline` / OFFLINE ONLY — UNPROVEN IN GAME)** until Claude (PC) runs them in Starfield.
> - **`R8` / `R15` Mandatory Stand-In Disclosures:**
>   - **Probe `P1`:** Confirmed-arrival scripted doors (`FO4SF_ConfirmedLoadDoor.psc` backed by `StartGameEnabled` `FO4SF_LoadDoorQuest.psc` cold-reload `OnPlayerLoadGame` handler + persistent `0x0A775B` primary / `0x0A775C` fallback + `12 s` watchdog) are the **plan of record**; all `6` P1 activators carry visible collidable `FO4Port` NIFs (`paintedwooddoordoubleload01.nif`, `bldwoodpdoorload01.nif`, `terminalwall01.nif`, `terminalconsoleon.nif`) with overlapping base statics disabled (`B1`), roof exit lands at Fallout 4 `0002C1C6` `XTEL` `(-1990.58, -1724.19, 97.56)` (`F9`), `FO4Port.esm` losslessly merges Museum `NVMI`s into `NAVI 0x00000FF1` (`L3`), and the ground raider carries `defaultFollowPlayerPKG` (`0x00021E76`) + continuous pursue re-engagement. The old `xtel_extra` holding-cell `XTEL` extra stays removed (`F4`).
>   - **Probe `P4` (`10mm Pistol` ALONE — zero Laser Musket, Pipe Gun, or Minigun):** The welded `10mm Pistol` mesh (`fo4_10mmpistol.nif`) is rigid — **moving parts (`slide/bolt, hammer, trigger, mag release, detachable magazine`) are welded rigid and do NOT move**, and firing/reload animations (`AnimGripPistol` `0x00E6C5` + `AnimM1919` `0x19A60E`) plus Wwise `SNDR` SFX are **Starfield `XM2311` (`0x24561C`) stand-ins**.

Truth labels used throughout: **`REACHABLE`**, **`TEST-STATION`**, **`OWNER TEST`**, **`RECORDS ONLY`**, **`TOOLING`**, **`NOT BUILT`**, **`NOT WIRED`**, **`NOT OURS`**.

---

## `P3` Typed-Console & Batch-Filename Zero-`M`/`N`/`V` & `< 200 m`/Axis Hop Rules

1. **Zero `M`, `N`, or `V` in Typed Console Lines & Batch Filenames (`P3`):** Every typed interactive ```` ```console ```` command and every batch filename (`bat <stem>` / `<stem>.txt`) below contains **ZERO `M`, `N`, or `V` letters** (case-insensitive). Batch file contents (```` ```bat ````) intentionally hold `coc`, `player.setpos`, `player.setangle`, and hex `SetStage` (executed from disk without keystrokes).
2. **Zero Stripped Mod `FO4SF_*` EditorIDs in Console/Bat (`P3`):** Never use `SetStage FO4SF_*` or `set FO4SF_*`. Both `stage_r11_p1_museum.py install` and `stage_r11_p4_10mm.py install` dynamically read live full-master load order (`(flags & 0x300) == 0`, skipping `FE`/`FD` light/medium masters) from `<starfield-dir>/Data` + `Plugins.txt` and stamp the exact runtime hex prefix (default `0x11` -> `SetStage 11000820 10|20|30`) into `<starfield-dir>/p1*.txt` and `<starfield-dir>/p4*.txt`; in-world **`E`-activators** also trigger key beats without any `SetStage` call.
3. **Every Exterior Hop Strictly `< 200 m` Per Axis (`P1` `max 159.25 m`, `P4` `max 70.75 m`):** Never single-hop `> 200 m` on any axis (`docs/terrain/border.md`).

---

## Card P1 — Probe `P1` (`v2`): Museum of Freedom Interior, Lossless `FO4Port`, Confirmed-Arrival Doors, `NAVM` Raider Climb & `FO4Port_PrewarVault111` (`TEST-STATION`)

- **Stage Placeholder:** `<p1-stage-dir>` (`r11-p1-museum-v2`, standalone folder outside every `candidate-*` folder; previous frozen `r11-p1-museum` stays untouched), `<starfield-dir>`
- **Disk Need:** `~2.30 GB` staged (`FO4Port.esm` `4,612,735 B`, `FO4Port - Main.ba2` `117,755,711 B`, `FO4Port - Textures.ba2` `2,289,478,621 B` = `2.132 GiB`, `FO4SF_R11P1Museum.esm` `5,037 B`, plus `FO4SF_R11P1Museum - Main.ba2` `32,883 B` packed from compiled v2 `.pex`; **`+0` companion plugins**, **`0` `WRLD`/`PNDT` overrides**, **`0` `3.60 GiB` bulk `b10` textures**, **`0` `FO4PortTextures2.esm` stub**, **`0` `xtel_extra` holding-cell trap**; `--reuse-port-ba2-dir` copies `.ba2`/`.esm` cleanly with exact SHA-256 backup). Requires `>= 60.0 GB` free on target drive before staging/installing.
- **Starting State:** `candidate-2g-fix2` (or `candidate-2g-fix`) Track-1 baseline installed in `<starfield-dir>`. `stage_r11_p1_museum.py install` backs up and swaps existing `Data/FO4Port.*` cleanly and adds `*FO4SF_R11P1Museum.esm` (leaving all `candidate-*` folders untouched).
- **Round 11 Part 3 `v2` Fixes Applied (Binary-Bisected from P1 v1 Live Evidence + Review Items):**
  1. **Zero `WRLD`/`PNDT` Overrides (`Bare Mars z=12.6` Root Cause Fixed):** Removed `TopGrup(b"WRLD")` completely from `FO4SF_R11P1Museum.esm` and deleted the old `xtel_extra` module (`P1v2 F4`). Previously, overriding `WRLD 0x02000803` with a 21-byte stub wiped `FO4TerrainCore.esm:0x01000803`'s 23 subrecords (`flags=0x04`, `ONAM`, `MNAM`, `NAM0`, `NAM9`, `DATA`) and broke `FO4TerrainCore_Mars.esm`'s `PNDT 0x0003F59A` world splice, dropping exterior Concord onto bare Mars (`z ≈ 12.6 m`). Exterior entry activators `FO4SF_P1_ExtFrontInRef` (`0x04000810`) and `FO4SF_P1_ExtRoofInRef` (`0x04000813`) now live in probe-owned holding cell **`CELL 0x0400080F` (`FO4SF_P1_HoldingCell`)** and are dynamically placed onto `MarsPlanetWorld` via `FO4SF_R11P1Quest.SyncExteriorDoors` whenever the player is outdoors within `350 m` of Concord.
  2. **Non-Blocking `StartTimer`/`OnTimer` `FO4SF_ConfirmedLoadDoor.psc` (`dir=out` Infinite Load Screen Fixed):** `OnActivate` now logs `FO4SF_LOADDOOR activate_begin` BEFORE `MoveTo`, accepts `akActionRef == player || akActionRef == None` (so console `<ref>.activate` works), calls `player.MoveTo(activeAnchor, ...)`, arms `TIMER_ARRIVAL`, and returns immediately so CE2 interior-cell unload never stalls in a `while + Utility.Wait` loop. Includes `FallbackTargetFormId = 0x0A775B` fallback and `OnInit`/`OnCellAttach` tracing.
  3. **Proven Interior Lighting Template (`LTMP = 0x0006BCF8` `KreetBase01LGTtemplate`) & Full `CELL 0x0100E2F4` Override:** Both `FO4Port_ConcordMuseum01` (`0x0100E2F4`) and `FO4Port_PrewarVault111` (`0x0100EDFB`) now use `LTMP = 0x0006BCF8` (matching proven lit `FO4Port_Vault111Cryo` `0x010011F3`), and `FO4SF_R11P1Museum.esm` copies all 6 `CELL` subrecords (`EDID`, `DATA`, `LTMP`, `XLCN`, `XCIM`, `XEMP`) verbatim rather than a 2-subrecord stub.
  4. **Quest Autostart, Persistent `0x0100EDF0`/`0x0100E35E`/`0x0100EFA9`/`0x0100EFAA`, `XLOC 25` + `XLKR`:** Fixed `QUST DNAM` flags to `0x00000009` (`StartGameEnabled | AllowRepeatedStages`) with `OnInit`/`OnQuestInit`/`OnQuestStarted` -> `EnsureStarted`, promoted Museum basement gate `0x0100EDF0` (`XLOC 25`), basement terminal `0x0100E35E` (`XLOC 25` + `XLKR -> 0x0100EDF0`), and key doors/medkit into persistent `GRUP(8)` (`flags |= 0x400`) inside `FO4Port.esm`, synthesized `FO4Port_PrestonDoorREF` (`0x0100EFA9`) & `FO4Port_PrestonExitDoor` (`0x0100EFAA`), and resolved forms at runtime via `Game.GetFormFromFile(..., PortPlugin)` (zero `<nullptr form>`).

### Staged File Inventory & SHA-256 Receipts (`r11-p1-museum-v2/manifest.json` — Deterministic Binary Receipts Verified Offline)

| Staged File (`<p1-stage-dir>/...`) | Size (Bytes) | Exact SHA-256 | Role |
|---|---:|---|---|
| `port/FO4Port.esm` | `4,612,735` | `8163ca9a7187bd07fdd09f20ad7c16d511577f91d91c858ed28ec0fc434fef39` | Lossless append over `07756819...` (`55,071` unchanged baseline records + `3,500` new records `0x0100E200..0x0100EFAA`, `NextObjectID=0x00EFAB`, `0` missing/type/body diffs, `0` `WRLD`/`PNDT`, `LTMP 0x0006BCF8` on `0x0100E2F4`/`0x0100EDFB`, persistent `0x0100E35E`/`0x0100EDF0`/`0x0100EFA9`/`0x0100EFAA`, `XLOC 25` + `XLKR`, `NAVM 0x0100EFA8` `2,002` tris + `NAVI 0x00000FF1`) |
| `port/FO4Port - Main.ba2` | `117,755,711` | `064c762499a1cc975df81da2c12ea3a20aec5f84cae0c89f4d9cdac12d094c7e` | `BTDX` v2 `GNRL` (`17,023` entries; `+960` Museum + Pre-War Vault 111 delta entries, `+4.43 MiB`; copied cleanly without frozen hardlinks) |
| `port/FO4Port - Textures.ba2` | `2,289,478,621` | `f4664dd0a4fb49a3adb17440596bbb936b0ffa47516024be9fff07c7b1a69a48` | `BTDX` v2 `DX10` (`4,711` entries; `+220` Museum texture delta only, `+126.33 MiB`, `2.132 GiB` total; copied cleanly) |
| `exp/FO4SF_R11P1Museum.esm` | `5,037` | `63e0862f22c43838f4738a790710a2754d3f28ca74d38b8e62e17c90fffdcd11` | `17` records (`0` `WRLD`/`PNDT`!): holding `CELL 0x0400080F`, full 6-subrecord `CELL 0x0100E2F4` (`LTMP 0x0006BCF8`), `4` confirmed-arrival doors (`0x04000810..0x04000813`), basement terminal (`0x04000814`), 3F `E`-trigger (`0x04000816`), `InitiallyDisabled` ground raider (`0x04000815`), `QUST` (`0x04000820`, `DNAM=0x00000009`) |
| `exp/FO4SF_R11P1Museum - Main.ba2` | `32,883` | `1d4580c17e7b7d619c44ac6531db7ac28a478dea055d762cdea08e34a3899c02` | `BTDX` v2 `GNRL` via `Archive2.exe` (`2` `.pex`: non-blocking `FO4SF_ConfirmedLoadDoor.pex` + `FO4SF_R11P1Quest.pex`, `bs_crc32` verified) |

### Install Command (Game Closed — Reversible Swap Over `candidate-2g-fix`)
```bash
python scripts/probes/stage_r11_p1_museum.py verify --stage-dir <p1-stage-dir>
python scripts/probes/stage_r11_p1_museum.py install --stage-dir <p1-stage-dir> --starfield <starfield-dir>
python scripts/probes/stage_r11_p1_museum.py status --starfield <starfield-dir>
```

### `< 200 m`/Axis Exterior Hop Table (`P1` — All Hops `<= 159.25 m` Per Axis)

| Hop / Batch | From -> To (Merged Exterior Coords, m) | `|dx|` (m) | `|dy|` (m) | `|dz|` (m) | Max Axis (m) | `< 200 m`/axis |
|---|---|---:|---:|---:|---:|---|
| `bat p1h1` | Sanctuary workbench `(-2329.25, -1420.19, 112.09)` -> mid-hop `(-2170.00, -1560.00, 102.00)` | `159.25` | `139.81` | `10.09` | **`159.25`** | PASS |
| `bat p1c` | `p1h1` `(-2170.00, -1560.00, 102.00)` -> Museum front `(-2012.50, -1697.94, 88.70)` | `157.50` | `137.94` | `13.70` | **`157.50`** | PASS |
| `040A775C -> p1c` | Concord anchor `(-2061.23, -1657.46, 86.93)` -> Museum front `(-2012.50, -1697.94, 88.64)` | `48.73` | `40.48` | `1.71` | **`48.73`** | PASS |
| `040A775C -> door` | Concord anchor `(-2061.23, -1657.46, 86.93)` -> Front door `(-2010.69, -1698.04, 89.26)` | `50.54` | `40.58` | `2.33` | **`50.54`** | PASS |
| `bat p1r` | Museum front `(-2012.50, -1697.94, 88.64)` -> Museum 3F roof `(-1990.58, -1724.19, 97.82)` | `21.92` | `26.25` | `9.18` | **`26.25`** | PASS |

### Ordered 6-Part Probe `P1` (`v2+`) Procedure (`P3`-Clean Batches: `p1h1`, `p1c`, `p1r`, `p1f`, `p1b`, `p1k`, `p1p`, `p1q`)
0. **Row 1 — Exterior-Loads Gate (MANDATORY FIRST CHECK BEFORE ENTERING MUSEUM):**
   - Start New Game (`Quick start` / emerge from Vault 111 to Sanctuary) and hop to Concord Museum front via `bat p1h1` (wait `3–5 s`) -> `bat p1c` (`(-2012.50, -1697.94, 88.64)`).
   - **PASS:** Concord exterior street, buildings, and Museum of Freedom facade are fully rendered at **`z ≈ 88.3 m`** (NOT bare Mars red sand at `z ≈ 12.6 m`!), `FO4SF_R11P1 ext_door_placed tag=p1_front_in ...` logs in `fo4sf_r11p1.0.log`, and `FO4SF_P1_ExtFrontInRef` (visible double wood door `paintedwooddoordoubleload01.nif`, `[Open] Museum of Freedom (Enter)`) is clickable directly in front of the facade. *(If bare Mars `z ≈ 12.6 m` ever appears, STOP immediately and FAIL Row 1!)*
1. **Front Door Confirmed-Arrival (`5x` Each Way — `p1_front_in` & `p1_front_out`):**
   - Facing east (`90 deg`) at `bat p1c`, press **`E`** on `FO4SF_P1_ExtFrontInRef` (`(-2010.69, -1698.04, 89.26)`) to enter `FO4Port_ConcordMuseum01` (`0x0100E2F4`, `LTMP 0x0006BCF8`, landing on `NAVM tri 87` at `(7.73, 0.91, -0.90)` facing west `270 deg` into lobby); turn around and press **`E`** on `FO4SF_P1_IntFrontOutRef` (`(9.02, 0.0, -0.914)` replacing disabled `0x0100EDEC`) to exit to `(-2012.50, -1697.94, 88.24)` facing west `270 deg` onto Concord street (`core_cell=true`).
   - **PASS:** Repeat **`5` complete round-trips (`5x` in + `5x` out)** by pressing **`E`** (zero `<ref>.activate`) with `0` crashes, `0` infinite loading screens, `0` falls through floor, `0` `2.9 km` anchor bounces, and both `FO4SF_LOADDOOR activate_begin` and `FO4SF_LOADDOOR confirmed` on every leg.
2. **Roof Door Confirmed-Arrival (`3x` Each Way — `p1_roof_out` & `p1_roof_in`, `F9` Fix):**
   - Walk up to the 3F roof door inside the Museum (`(-21.943, 9.02, 9.143)` replacing disabled `0x0100EDF5`) OR hop outside with `bat p1r` (`(-1990.58, -1724.19, 97.82)` facing NNW `335 deg` toward `FO4SF_P1_ExtRoofInRef` at `(-1991.27, -1722.57, 97.42)`).
   - Press **`E`** on `FO4SF_P1_IntRoofOutRef` -> exterior roof bulkhead **`(-1990.58, -1724.19, 97.56)`** (`F9`, `1.77 m` from `ExtRoofInRef`, `core_cell=true`), then step & press **`E`** on `FO4SF_P1_ExtRoofInRef` (`bldwoodpdoorload01.nif`) -> interior 3F landing `(-21.90, 8.68, 9.15)` facing east `90 deg` into 3F corridor.
   - **PASS:** Complete **`3` full round-trips (`3x` out + `3x` in)** standing firmly on the roof bulkhead (`z ≈ 97.56`, NO falling off roof!) and `FO4SF_LOADDOOR confirmed` on every leg.
3. **Save Inside Museum -> Full Quit to Desktop -> Relaunch -> Load -> Walk Out Front Door (`FO4SF_LoadDoorQuest` Fix):**
   - Stand inside `FO4Port_ConcordMuseum01` (enter via front door or `bat p1f`), run `bat p1q`, save **`Throwaway_R11P1_Inside`**, **Quit to Desktop**, relaunch SFSE, load `Throwaway_R11P1_Inside`, and press **`E`** on `FO4SF_P1_IntFrontOutRef`.
   - **PASS:** `FO4SF_LoadDoorQuest.OnPlayerLoadGame` cancels stale timers & logs `FO4SF_LOADDOOR reload_ready`; walking out front door resolves `0x0A775B` immediately and lands confirmed on Concord street (`core_cell=true`, never hangs on `activate_begin`). Delete throwaway save when done.
4. **Full Museum Walk + Basement Terminal (`0x0100E35E`) & Novice-Locked Security Gate (`0x0100EDF0`, Opened Once Without Relocking):**
   - Walk from the front lobby down to the basement (`(-14.38, -0.10, -3.32)`, `NAVM tri 1011`; interior-only shortcut `bat p1b` enforces `IsPlayerInMuseum()` guard and sets stage `10`), confirm `0x0100EDF0` & `0x0100E35E` start **Novice-locked (`level=25`)**, then unlock via **`E`** on `FO4SF_P1_BasementTermRef` (`[Unlock Security Gate]`) / terminal `0x0100E35E` (`XLKR -> 0x0100EDF0`) or Digipicking `0x0100EDF0`.
   - Walk through the opened gate into the fusion-core generator cage, then walk all the way up through the main atrium stairs to the 3F balcony/Preston's room and the 3F roof doorway.
   - **PASS:** Logs `FO4SF_R11P1 basement_gate opened=true already_open=false ... locked_before=true lock_level_before=25 locked_after=false`, gate stays unlocked/open without relocking (even across save/load), and player traverses basement -> atrium -> 3F -> roof door on foot with solid floor & stairs.
5. **Ground-Floor Hostile Raider Climbing Converted `NAVM 0x0100EFA8` (`195`-Hop Multi-Floor Path):**
   - Stand on the 3F atrium balcony (`(-4.00, 7.50, 9.15)`, `NAVM tri 817`, facing south `180 deg`; interior-only shortcut `bat p1k` enforces `IsPlayerInMuseum()` guard and sets stage `20`). Note `FO4SF_P1_GroundRaiderRef` (`0x04000815`) starts **`InitiallyDisabled` (`0x0C00`)** so it never fights early.
   - Trigger via **pressing `E` on the 3F activator right in front of the camera (`FO4SF_P1_RaiderNavTriggerRef` `(-4.00, 6.20, 9.55)` — works even with zero `SetStage`!)** OR via `bat p1k`'s dynamically stamped hex `SetStage <XX>000820 20`.
   - Watch for `30 s` (`15` ticks at `2.0 s` in `fo4sf_r11p1.0.log`): does the ground-floor hostile raider (`(-3.00, 0.00, 0.25)`, `Aggression=2`, `Confidence=4`, `HideSpacesuitAV=1`) navigate the atrium stairs on `NAVM 0x0100EFA8` toward the player on 3F (`climbed_stairs=true` when `rz > 4.0`)? Record exact behavior + stills honestly!
6. **`FO4Port_PrewarVault111` (`0x0100EDFB`, `LTMP 0x0006BCF8`) Pod Wing Visual & Lighting Check:**
   - Run `bat p1p` (`coc FO4Port_PrewarVault111`). Capture stills of the Pre-War Vault 111 cryo/pod wing geometry, floor collision, and `KreetBase01LGTtemplate` (`0x0006BCF8`) lighting.

```console
bat p1h1
bat p1c
bat p1r
bat p1f
bat p1b
bat p1k
bat p1p
bat p1q
getstage 11000820
sqs 11000820
```

```bat
; <starfield-dir>/p1h1.txt — exterior mid-hop from Sanctuary workbench (-2329.25,-1420.19) toward Concord (<160 m/axis)
player.setpos x -2170.00
player.setpos y -1560.00
player.setpos z 102.00
player.setangle z 135

; <starfield-dir>/p1c.txt — Museum exterior front door approach (<158 m/axis from p1h1)
player.setpos x -2012.50
player.setpos y -1697.94
player.setpos z 88.70
player.setangle z 90

; <starfield-dir>/p1r.txt — Museum exterior 3F roof approach (<27 m/axis from p1c, facing NNW toward ExtRoofIn)
player.setpos x -1990.58
player.setpos y -1724.19
player.setpos z 97.82
player.setangle z 335

; <starfield-dir>/p1f.txt — direct interior Museum lobby (0x0100E2F4, NAVM tri 87)
coc FO4Port_ConcordMuseum01
player.setpos x 7.73
player.setpos y 0.91
player.setpos z -0.90
player.setangle z 270

; <starfield-dir>/p1b.txt — INTERIOR-ONLY (requires bat p1f): basement gate (NAVM tri 1011) + stamped hex stage 10
SetStage 11000820 10

; <starfield-dir>/p1k.txt — INTERIOR-ONLY (requires bat p1f): 3F vantage (NAVM tri 817) + stamped hex stage 20
SetStage 11000820 20

; <starfield-dir>/p1p.txt — Pre-War Vault 111 interior check (0x0100EDFB)
coc FO4Port_PrewarVault111

; <starfield-dir>/p1q.txt — status snapshot to fo4sf_r11p1.0.log (stamped hex stage 30)
SetStage 11000820 30
```

### Exact One-Line Undo / Rollback Command (`P1` — Game Closed, Restores Original `FO4Port.*` by SHA-256)
```bash
python scripts/probes/stage_r11_p1_museum.py uninstall --starfield <starfield-dir>
```

### Required PASS Log Lines (`P1` — `fo4sf_loaddoor.0.log` & `fo4sf_r11p1.0.log`)
```log
FO4SF_R11P1 ext_door_placed tag=p1_front_in source=<init|on_init|load_game|stage_30|timer> pos=<x> <y> <z> world=<world>
FO4SF_LOADDOOR activate_begin tag=p1_front_in dir=in caller=<caller> cell=<cell> pos=<x> <y> <z>
FO4SF_LOADDOOR confirmed tag=p1_front_in dir=in attempts=<n> core_cell=<true|false> cell=<cell> world=<world> pos=<x> <y> <z> heading=270.0
FO4SF_LOADDOOR activate_begin tag=p1_front_out dir=out caller=<caller> cell=<cell> pos=<x> <y> <z>
FO4SF_LOADDOOR confirmed tag=p1_front_out dir=out attempts=<n> core_cell=true cell=<cell> world=<world> pos=<x> <y> <z> heading=270.0
FO4SF_LOADDOOR reload_ready cell=<cell> interior=<true|false>
FO4SF_LOADDOOR confirmed tag=p1_roof_out dir=out attempts=<n> core_cell=true cell=<cell> world=<world> pos=<x> <y> <z> heading=335.0
FO4SF_LOADDOOR confirmed tag=p1_roof_in dir=in attempts=<n> core_cell=<true|false> cell=<cell> world=<world> pos=<x> <y> <z> heading=90.0
FO4SF_R11P1 basement_gate opened=true already_open=false source=<terminal_activate|port_terminal_activate|gate_picked_activate|stage_10> locked_before=true lock_level_before=25 locked_after=false ref=<ref>
FO4SF_R11P1 raider_combat started=true loaded=true wait_steps=<w> raider=<ref> raider_pos=<rx> <ry> <rz> player_pos=<px> <py> <pz> dist=<d>
FO4SF_R11P1 raider_nav tick=<k>/15 dead=<true|false> combat=<true|false> climbed_stairs=<true|false> raider_pos=<rx> <ry> <rz> player_z=<pz> dist=<d>
FO4SF_R11P1 snapshot tag=<init|load_game|stage_30> cell=<cell> interior=<true|false> world=<world> pos=<x> <y> <z> gate_opened=<true|false> gate_locked=<true|false> gate_lock_level=<n> raider_dead=<true|false>
```

### Negative / FAIL Conditions (`P1`)
- **Row 1 Exterior-Loads Gate failure:** Bare Mars terrain (`z ≈ 12.6 m`) instead of Concord (`z ≈ 88.3 m`), or any `WRLD`/`PNDT` override present in `FO4SF_R11P1Museum.esm`.
- Any infinite loading screen on `dir=out`, `FO4SF_LOADDOOR failed`, or `surface_cell_not_core` / `2.9 km` bounce during `5x` front or `3x` roof trips; crash or stuck `busy=true` after save/quit/load inside Museum; persistent basement gate `0x0100EDF0` failing to open or relocking on reload; falling through Museum floor/stairs; `FO4Port_PrewarVault111` black/unlit (`LTMP != 0x0006BCF8`) or missing collision; or any modification to `candidate-2g` / `candidate-2g-fix` / `candidate-2g-fix2`. *(Note: whether the ground-floor raider climbs stairs on `NAVM 0x0100EFA8` is a factual probe answer — record `climbed_stairs=true|false` honestly!)*

---

## Card P4 — Probe `P4` (`10mm Pistol` Alone, `A4.1`): Vault 111 Desk Pickup -> Auto-Equip -> 1stP/3rdP/ADS/Fire-12/Reload/Hit-Kill/Inventory Row (`TEST-STATION`)

- **Stage Placeholder:** `<p4-stage-dir>` (`r11-p4-10mm`, standalone folder outside every `candidate-*` folder — frozen on disk; post-P4 code fixes for Notes 1, 2, 5 landed in `stage_r11_p4_10mm.py` & `FO4SF_R11P4Quest.psc` for `candidate-2h` / any future re-stage: `0x001539` runtime lookup via `PortPlugin` + `ArmoryCageDoorLocalId`, `QUST DNAM = 0x00000009` + `OnInit`/`OnQuestStarted` autostart, and `TargetDummy.RemoveAllItems(None, false, true)` + `SetRestrained(true)` so dummy stays unarmed & restrained), `<starfield-dir>`
- **Disk Need:** `~6.2 MB` staged (`FO4SFCoreValues.esm` `11,555 B`, `FO4SFNewGame.esm` `12,688 B`, `FO4SF_R11P4Pistol.esm` `1,348 B`, `FO4SF_R11P4Pistol - Main.ba2` `296,251 B`, `FO4SF_R11P4Pistol - Textures.ba2` `5,909,367 B`; **`+0` companion plugins**; zero Laser Musket, Pipe Gun, or Minigun records). Requires `>= 60.0 GB` free on target drive.
- **Starting State:** Uninstall `P1` first so `candidate-2g-fix` is cleanly restored, then install `P4`. `stage_r11_p4_10mm.py install` backs up live `FO4SFCoreValues.esm` & `FO4SFNewGame.esm` into `backup_pre_p4/`, swaps them via `shutil.copy2` (`os.link` for `.ba2` only), appends `*FO4SF_R11P4Pistol.esm`, and stamps live full-master hex slot (default `0x11` -> `11000820`) into `<starfield-dir>/p4*.txt`.
- **Records Tested (`3a` `130076fa` + `P4` `30a1eb6c`):**
  - `FO4SFCoreValues.esm:0x000898` (`FO4_Ammo10mm`, `"10mm Round"`, `fo4core\ammo\10mm\10mmammo.nif`, donor `Starfield.esm:0x2B5598` `Ammo45Caliber`).
  - `FO4SFCoreValues.esm:0x000899` (`FO4_10mmPistol`, `"10mm Pistol"`, `AttackDamage=18`, `AmmoCapacity=12`, `AttackDelaySeconds=0.214`, `Model` & `FirstPersonModel` = `fo4sf\weapons\10mm\fo4_10mmpistol.nif`, `ObjectTemplates` & `AttachParentSlots` cleared so no Starfield `XM2311` / `M1919` parts spawn).
  - `FO4SFNewGame.esm:0x000820` (`FO4SF_Vault111PistolRef` at `(-57.0338, 30.006, 1.29)` m on Overseer's desk) & `0x000821` (`FO4SF_Vault111AmmoRef` at `(-57.0522, 30.3703, 0.696)` m, `Count = 48` rounds).
  - `FO4SF_R11P4Pistol.esm`: persistent `E`-activator `FO4SF_P4_TargetTriggerRef` (`0x04000810` at `(-55.40, 31.10, 1.35)`), `InitiallyDisabled` (`0xC00`) `30 HP` practice target `FO4SF_P4_TargetDummyRef` (`0x04000811` at `(-48.80, 30.00, 0.15)`), `ArmoryCageDoor` (`0x01001539` auto-unlocked & opened when target spawns), and `FO4SF_R11P4Quest` (`0x04000820`).
- **MANDATORY `R15` Disclosure (Rigid Welded Mesh & Borrowed Stand-In Animations/Audio):**
  - Welded Fallout 4 `10mm Pistol` parts (**`slide/bolt, hammer, trigger, mag release, detachable magazine`**) are **rigid and do NOT move** during firing or reload.
  - Firing/reload animations (`AnimGripPistol` `0x00E6C5` + `AnimM1919` `0x19A60E`) and Wwise `SNDR` weapon SFX are **Starfield `XM2311` (`0x24561C`) stand-ins** (zero converted FO4 weapon `.wem` SFX exist on disk today).

### Staged File Inventory & SHA-256 Receipts (`r11-p4-10mm/manifest.json` — `44/44` Files Verified Offline)

| Staged File (`<p4-stage-dir>/...`) | Size (Bytes) | Exact SHA-256 | Role |
|---|---:|---|---|
| `core/FO4SFCoreValues.esm` | `11,555` | `b6fca94fd98f42654d9cc83a7a4c7ab166f5ff37b2ec8087558aa3ec31ee6ac7` | `--fo4-10mm 1`: adds `0x000898` `FO4_Ammo10mm` & `0x000899` `FO4_10mmPistol` (`0` other guns) |
| `core/FO4SFNewGame.esm` | `12,688` | `7fcbb12ff901daa2b392dba54948ea076f21db22d9eb20a6e2429a6baa45301e` | `--fo4-10mm 1`: Overseer desk `0x0820` `10mm Pistol` + `0x0821` `48x 10mm Round` + auto-equip |
| `exp/FO4SF_R11P4Pistol.esm` | `1,348` | `e6e50ab185670c4b518e7cab047e7a97ce1ec65a36a8a36467d6b05ef17d2f6b` | Persistent `E`-trigger `0x04000810`, `InitiallyDisabled` `30 HP` target `0x04000811`, `ArmoryCageDoor` `0x01001539`, `QUST` `0x04000820` |
| `exp/FO4SF_R11P4Pistol - Main.ba2` | `296,251` | `d112735e2bc2c966c29ed6c9a80a10ed610a160bd0e75f5b0acfc3bc4c24d0bb` | `BTDX` v2 `GNRL` via `Archive2.exe` (`18` uncompressed entries, `bs_crc32` verified: `2` `.pex`, `2` `.nif`, `10` `.mesh`, `4` `.mat`) |
| `exp/FO4SF_R11P4Pistol - Textures.ba2` | `5,909,367` | `9421ae40bc9a36259f53405f2c3cb7d7dff2c26f9ed4fe19bd8433be55e92e1a` | `BTDX` v2 `DX10` via `Archive2.exe` (`13` `.dds` textures for `10mm` pistol & ammo) |
| `assets/meshes/fo4sf/weapons/10mm/fo4_10mmpistol.nif` | `10,796` | `2033561ea31ce4213063d5b8e29ee6af36322b719ce6f8608d1c8ad2ce7559a2` | Rigid welded Fallout 4 `10mm Pistol` BS-173 mesh (`8` `BSGeometry`, `COL_WEAPON` Havok body) |
| `assets/meshes/fo4core/ammo/10mm/10mmammo.nif` | `7,135` | `a08ee05fc4746300669d52c503c8b5836657457be65f7f9fe4b80472efd58f09` | Fallout 4 `10mm Round` BS-173 world pickup mesh |

### Install Command (`P4` — Game Closed, Reversible Swap Over `candidate-2g-fix`)
```bash
python scripts/probes/stage_r11_p4_10mm.py verify --stage-dir <p4-stage-dir>
python scripts/probes/stage_r11_p4_10mm.py install --stage-dir <p4-stage-dir> --starfield <starfield-dir>
python scripts/probes/stage_r11_p4_10mm.py status --starfield <starfield-dir>
```

### `< 200 m`/Axis Exterior Hop Table (`P4` — Optional Daylight Clearing Check, All Hops `<= 70.75 m` Per Axis)

| Hop / Batch | From -> To (Merged Exterior Coords, m) | `|dx|` (m) | `|dy|` (m) | `|dz|` (m) | Max Axis (m) | `< 200 m`/axis |
|---|---|---:|---:|---:|---:|---|
| `bat p4h1` | Sanctuary bench `(-2329.25, -1420.19, 112.09)` -> mid-hop `(-2400.00, -1413.00, 120.00)` | `70.75` | `7.19` | `7.91` | **`70.75`** | PASS |
| `bat p4e` | `p4h1` `(-2400.00, -1413.00, 120.00)` -> Vault 111 hilltop `(-2467.78, -1406.93, 127.85)` | `67.78` | `6.07` | `7.85` | **`67.78`** | PASS |

### Ordered 7-Point Probe `P4` Procedure (`10mm Pistol` Alone — `P3`-Clean Batches: `p4d`, `p4o`, `p4g`, `p4t`, `p4h1`, `p4e`, `p4s`)
1. **Natural Vault 111 Overseer Desk Pickup -> Auto-Equip in Hand:**
   - Start a New Game (`Quick start`, `FO4SF_NewGame` `stage 20`), walk the Vault 111 Overseer floorplan route (OR run interior hop `bat p4d` keeping active `stage 20`; `bat p4o` jumps directly via `coc FO4Port_Vault111Cryo` and `bat p4g` is a non-NewGame fallback grant).
   - Pick up **`10mm Pistol`** (`0A000820`) and **`48` `10mm Round`** (`0A000821`) from the Overseer's desk (`(-57.03, 30.01, 1.29)`) with **`E`**.
   - **PASS:** `FO4SF_NewGameQuest.OnItemAdded` automatically equips the pistol into the player's hand (`FO4SF_NEWGAME rt=<rt> pistol picked equipped=true base=FO4_10mmPistol` + `pistol ammo picked ... count=48 base=FO4_Ammo10mm`) with zero Starfield `XM2311` geometry.
2. **1st-Person & 3rd-Person Hold Stills:**
   - Capture **1st-person** idle still AND toggle to **3rd-person** for a 3rd-person hold still (optionally hop outdoors via `bat p4h1` -> `bat p4e` for bright daylight stills).
   - **PASS:** Fallout 4 `10mm Pistol` silhouette, grip alignment, dark gunmetal textures (`10mmpistol.mat`/`10mmmag.mat`), and zero missing/purple textures or Starfield `XM2311` parts.
3. **ADS (Aim Down Sights) Check:**
   - Hold right-click (ADS) and capture a still.
   - **PASS:** Sight alignment is usable and does not clip the camera inside the receiver.
4. **Fire 1 Full Magazine (`12` Rounds):**
   - Fire all **`12` rounds** (`AmmoCapacity=12`, `AttackDelaySeconds=0.214`), observing muzzle projectile origin (`ProjectileNode`), firing recoil, and stand-in `XM2311` audio (`FO4SF_R11P4 ammo_delta ... full_mag_12_proven=true`).
5. **Reload (`12` Rounds Drawn From `48`-Round Reserve):**
   - Reload from `0/12` -> `12/12` (reserve drops `48 -> 36`). Note honestly that the slide/magazine stay rigid (expected `R15` welded-mesh behavior) while Starfield `XM2311` reload animation plays cleanly without hanging.
6. **Hit & Kill Check (God Mode OFF — `E`-Activator or `bat p4t`):**
   - Press **`E` on `FO4SF_P4_TargetTriggerRef` (`[Spawn] 10mm Target Practice`, `0x04000810` beside the Overseer desk — zero console!)** OR run `bat p4t` (`player.setpos x -53.20, y 29.80, z 0.15`, yaw `90 deg` facing east + `SetStage 11000820 20`). `SpawnPracticeTarget()` automatically unlocks & opens armory cage door `0x01001539` (`ArmoryCageDoor`).
   - Shoot the restrained `30.0 HP` `FO4SF_P4_TargetDummyRef` (`4.40 m` unobstructed sightline east at `(-48.80, 30.00, 0.15)`) with `10mm Pistol` (`AttackDamage=18` -> 2 shots kill).
   - **PASS:** Logs `FO4SF_R11P4 target_hit ...` and `FO4SF_R11P4 target_killed ... pistol_equipped=true`.
7. **Inventory Row Check & Scorecard (`bat p4s`):**
   - Open inventory (`I` / `Tab -> Inventory -> Weapons & Ammo`, and `F7 -> INV` if `InvDataAnswers=1`) and capture a still of both Weapons and Ammo rows; then run `bat p4s` (`SetStage 11000820 30`) to write the final `FO4SF_R11P4 summary` scorecard.
   - **PASS:** Weapon reads **`"10mm Pistol"`** and ammo reads **`"10mm Round"`** — **ZERO `"XM2311"`** (`xm2311_leak=0`) and **ZERO `".45 Caliber"`** (`cal45_leak=0`)!

```console
sqs 0A000800
getstage 0A000800
bat p4d
bat p4o
bat p4g
bat p4t
bat p4h1
bat p4e
bat p4s
getstage 11000820
sqs 11000820
```

```bat
; <starfield-dir>/p4d.txt — interior hop inside Vault 111 to Overseer desk (keeps active stage 20)
player.setpos x -55.40
player.setpos y 29.80
player.setpos z 0.15
player.setangle z 278

; <starfield-dir>/p4o.txt — direct coc into Vault 111 Overseer office facing 10mm Pistol & 48x 10mm Round
coc FO4Port_Vault111Cryo
player.setpos x -55.40
player.setpos y 29.80
player.setpos z 0.15
player.setangle z 278

; <starfield-dir>/p4g.txt — fallback grant + auto-equip 10mm Pistol & 48x 10mm Round (stamped hex stage 10)
SetStage 11000820 10

; <starfield-dir>/p4t.txt — step east of cage doorway (0x01001539 auto-opens) & spawn 30-HP target 4.4 m East
player.setpos x -53.20
player.setpos y 29.80
player.setpos z 0.15
player.setangle z 90
SetStage 11000820 20

; <starfield-dir>/p4h1.txt — exterior mid-hop from Sanctuary toward Vault 111 hilltop (<75 m/axis)
player.setpos x -2400.00
player.setpos y -1413.00
player.setpos z 120.00
player.setangle z 275

; <starfield-dir>/p4e.txt — exterior Vault 111 hilltop clearing (<70 m/axis from p4h1) for daylight stills
player.setpos x -2467.78
player.setpos y -1406.93
player.setpos z 127.85
player.setangle z 90

; <starfield-dir>/p4s.txt — write full scorecard summary line to fo4sf_r11p4.0.log (stamped hex stage 30)
SetStage 11000820 30
```

### Exact One-Line Undo / Rollback Command (`P4` — Game Closed, Verifies Restored SHA-256)
```bash
python scripts/probes/stage_r11_p4_10mm.py uninstall --starfield <starfield-dir>
```

### Required PASS Log Lines (`P4` — `fo4sf_newgame.0.log` & `fo4sf_r11p4.0.log`)
```log
FO4SF_NEWGAME rt=<rt> pistol picked item=<item> count=1 equipped=true base=FO4_10mmPistol
FO4SF_NEWGAME rt=<rt> pistol ammo picked item=<item> count=48 base=FO4_Ammo10mm
FO4SF_R11P4 init rigid_parts=slide_bolt_hammer_trigger_and_mag_do_not_move anim_audio_standin=XM2311_0x24561C
FO4SF_R11P4 target_spawned ok=true source=<trigger_activate|stage_20> hp=30.0 pos=<x> <y> <z> dist=<d>
FO4SF_R11P4 ammo_delta prev=<prev> now=<now> fired=<n> fired_total=<tot> full_mag_12_proven=true
FO4SF_R11P4 target_hit hit_num=<n> dmg=<dmg> hp_after=<hp> dead=<true|false>
FO4SF_R11P4 target_killed hits=<n> killer=<killer> pistol_equipped=true
FO4SF_R11P4 summary tag=<init|item_added|pistol_equipped|stage_30> cell=<cell> pos=<x> <y> <z> equipped=true pistol_10mm=1 ammo_10mm=<cnt> fired_total=<tot> full_mag_12_proven=true target_hits=<hits> target_killed=true xm2311_leak=0 cal45_leak=0 rigid_parts=non_moving_slide_and_mag
```

### Negative / FAIL Conditions (`P4`)
- Pistol failing to auto-equip into hand on Overseer desk pickup (`equipped=false`); Starfield `XM2311` / `M1919` / `BullpupDummyReceiver` geometry or `".45 Caliber"` / `"XM2311"` names appearing (`xm2311_leak != 0` or `cal45_leak != 0`); missing/purple textures; gun failing to fire `12` rounds (`full_mag_12_proven=false`), reload, or register hit/kill damage (`target_killed=false`); or any `candidate-2g` / `candidate-2g-fix` modification.
