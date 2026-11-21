# Vault 111 Exit Lift Rules Audit (13–15 Nov Decisions vs Current Build)

This audit checks each of the seven 13–15 Nov owner rules for the Vault 111 exit lift against the repository state immediately before Phase 2, recording exact `file:line` citations, what the current `gemini/beginning-real` build implements (`S1`–`S5`, `X1`–`X5`), and what remains `NOT BUILT` this round.

---

## Stage Contract Extension (`FO4SF_NewGameQuest`)

Alongside the base Vault 111 start stages documented in `docs/newgame/vault111-start.md` (`0`, `1`, `10`, `20`, `30`, `40`, `200`), the mode-choice and Warfare start branches (`S4`, `S5`) add two stages to `STAGE_CONTRACT`:

| Stage | Meaning |
|---|---|
| 5 | mode chosen: start mode and survival choice stored |
| 210 | warfare complete: landed at the faction start spot |

> [!NOTE]
> **Version Disclosures (`S2`, `X3`):**
> - **Start Survival Lock (`S2`):** Survival picked at the start (`FO4SF_SurvivalStart = 1`) stays on for that game in this version (`FO4SF_SurvivalLocked = 1`); when Survival is not picked at the start (`FO4SF_SurvivalStart = 0`), the gameplay options switch turns hardcore mode on and off dynamically.
> - **Lift Tag Skills, Background & Traits (`X3`):** Driving tag skills, background, and traits from the Vault 111 lift prompt is **`NOT BUILT`** this round. On the lift, `S.P.E.C.I.A.L.` runs Progression's `40`-point allocator (`OpenAttributeAllocation`, writing `FO4SFCoreValues.esm`) and `Character` opens the looks-only character creator (`1` respec). In Warfare (`S5`), starting background is set automatically from the chosen faction start row (`ApplyWarfareBackground`).

---

## Summary Matrix

| # | Rule (13–15 Nov) | Pre-Phase-2 Status | Pre-Phase-2 Citations | Current Implementation (`X1`–`X5`, `S4`–`S5`) |
|---|---|---|---|---|
| 1 | Platform waits at the vault floor | **Already implemented** | `scripts/newgame/make_anim_console.py:293-296,440-441`, `dotnet/NewGame/Program.cs:202-203,425-426` | Preserved; surface return ride down (`#6`) also restores the floor cycle |
| 2 | Lift cage door is open while waiting at the vault floor and closes only for the ride | **Asset pose implemented; quest log tracking added** | `scripts/newgame/make_anim_console.py:410-420,438-451`, `scripts/newgame/FO4SF_NewGameQuest.psc:873-902` | Fixed-text script markers (`lift platform waiting cage_door=open` at prompt -> `lift cage_door=closing` before `Play01`, not live mesh readings) paired with converted `StateA_Idle` / `StateA_Play` clips; `X5` added a read-only Havok `TAG0` check only (no collision added) |
| 3 | Stepping on shows a prompt to change S.P.E.C.I.A.L. and character before `"Continue"` rides up | **Partial (`Ride up` / `Stay` only)** | `dotnet/NewGame/Program.cs:745-752`, `scripts/newgame/FO4SF_NewGameQuest.psc:874-920` | 4-button `FO4SF_NewGameElevator` (`Continue`, `S.P.E.C.I.A.L.`, `Character`, `Stay`); `Continue` blocked until `40`-point S.P.E.C.I.A.L. confirmed; after 3 cancelled/failed tries offers standard spread (`special default sum=<pool> source=lift`); after 3 failed lift rides offers `FO4SF_NewGameExitFallback` (`exit fallback by=move`); `Character` opens looks creator (`1` respec); lift tag skills/background/traits **`NOT BUILT`** this round |
| 4 | Map set-up runs during the ride, hidden by it, with no visible wait | **Not hidden during ride (ran after arrival wait)** | `scripts/newgame/FO4SF_NewGameQuest.psc:854-857,870,892-946` | Single shared `RunSharedMapSetup()` runs inside `StartAscent` during the ride (and in `RunWarfareBranch` for `S5`), preparing all markers as known + undiscovered (`map setup done markers=<n> elapsed=<s>`) while pre-attaching `0x0A775B` on surface transfer |
| 5 | On exit **ONLY Vault 111** is discovered, and fast travel is possible from that first discovery | **Already implemented** | `dotnet/NewGame/Program.cs:676`, `scripts/newgame/FO4SF_NewGameQuest.psc:902-946` | Preserved (`SetMarkerDiscovered()` called once on `0x0A775B` only in Story, or via `FO4SF_MapMarkers.DiscoverSingleMarker` on the chosen start marker in Warfare; landing completes to `stage 200 by=trigger` even if marker attach times out (`B2`)) |
| 6 | Standing on the platform later offers `"Ride down"` or `"Stay"` | **Missing** | `scripts/newgame/FO4SF_NewGameQuest.psc:467-469` | Adds `MESG 0x80B` (`FO4SF_NewGameReturn`: `Ride down to Vault 111` / `Stay`) and a `5.0 s` post-`200` surface pad check once the player walks `> 12 m` away and steps back within `PlatformRadius` |
| 7 | Creation sheet runs through real `Message` menus (`40`-point S.P.E.C.I.A.L., `3` tag skills, `1` background, `0..2` traits), writing to `FO4SFCoreValues.esm` | **Backend math only; interactive `Message` menus missing** | `scripts/progression/FO4SF_ProgressionQuest.psc:360-520` | Splits S.P.E.C.I.A.L. across `<= 7`-button `MESG` pages (`0x870` `FO4SF_CreationSpecialBox` `7` buttons, `0x878` `FO4SF_CreationSpecialPage2Box` `7` buttons, `0x87B` `FO4SF_CreationSpecialFallbackBox` `2` buttons), logging `special box shown box=<edid> buttons=<n>` from writer-filled arrays (`B3`), `special set ... sum=40 source=<lift\|warfare>`, and `special default sum=<pool> source=<lift\|warfare>` after 3 failed tries; lift tag/background/trait wiring **`NOT BUILT`** this round |

---

## Detailed Rule-by-Rule Audit

### 1. Platform waits at the vault floor
- **Before Phase 2:** **Implemented.**
  - `scripts/newgame/make_anim_console.py:293-296` enforces `--production-lift` with `stage3=StateA_Play,stage2=StateB_Play`, `idles="toggle"`, and `--rest-after stage2`.
  - `scripts/newgame/make_anim_console.py:440-441` validates that `StateA_Idle` holds the `last` frame of `StateB_Play` (`stage2`, the downward clip), keeping `b_Platform` stationary at the bottom of the Vault 111 shaft (`-1.751 m`).
  - `dotnet/NewGame/Program.cs:202-203,425-426,452-453` reads `Fo4PlatformMarker = 0x01B29E` (`RespecMoveMarker`) on the center of `b_Platform` (`(-77.742, -3.958, -1.751) m`) rather than `V111ElevatorREF`'s catwalk origin (`0x0244EB`).
- **Current Build:** Preserved unchanged; when the player later chooses `"Ride down to Vault 111"` from the surface pad (`#6`), `FO4SF_NewGameQuest.psc` triggers `Play02` if needed and moves the player back onto the floor platform coordinates.

### 2. Lift cage door is open while waiting at the vault floor and closes only for the ride
- **Before Phase 2:** **Implemented in the converted lift asset (`02-exit-lift`); not explicitly logged as cage-door state in `FO4SF_NewGameQuest.psc`.**
  - `scripts/newgame/make_anim_console.py:410-420` carries all `37` moving Havok convex hulls (`layer=2`, `L_ANIMSTATIC`) from the lift mesh: `b_Platform` (`25`), `b_Gate01` (`3`), `b_Gate02` (`3`), `b_Hatch Left` (`1`), `b_Hatch Right` (`1`), `b_CounterWeight` (`2`), `c_ExteriorLightL` (`1`), and `c_ExteriorLightR` (`1`).
  - `StateA_Idle` (`hold_of = StateB_Play`, `hold_frame = last`) keeps `b_Platform` at the vault floor with `b_Gate01` and `b_Gate02` raised open overhead so the player can walk onto the platform; `Play01` (`StateA_Play`, `9.8667 s`, `+21.6 m`) closes `b_Gate01` and `b_Gate02` before lifting `b_Platform` up the shaft.
- **Current Build (`B13`):** Keeps `StateA_Idle` untouched while the player stands on the floor or uses the lift menus, triggers `Play01` exclusively after `S.P.E.C.I.A.L.` is confirmed and `"Continue"` (`button == 0`) is pressed, and prints fixed-text script markers (`lift platform waiting cage_door=open` before `ExitMessage.Show()` and `lift cage_door=closing` before `StartAscent` — fixed script strings, not live collision/bone readings). `X5` (`scripts/newgame/make_anim_console.py:inspect_nif_collision_layers`) added a **read-only** Havok `TAG0` check and added no collision bodies:
  - `vltgeardoor01_anim.nif` (`FO4SFVaultGearDoor`): `26/26` `hknpBodyCinfo` entries on `L_ANIMSTATIC` (`layer=2`), `0` non-collidable bodies.
  - `vltelevator_anim.nif` (`FO4SFExitLift`): `37/37` `hknpBodyCinfo` entries on `L_ANIMSTATIC` (`layer=2`), `0` non-collidable bodies.
  - `v111gearroomgate01.nif`, `v111gearroomgate01_xrgd_e3c6933a65.nif`, and `v111gearroomgate02.nif` (base interior port archive): each carries `4` `L_STATIC` (`layer=1`, `hknpConvexShape`) panel hulls (`Collision1`..`Collision4`) plus `1` `L_NONCOLLIDABLE` (`layer=15`, `hknpSphereShape`) root helper body named **`Collision0`**.

### 3. Stepping on shows a prompt to change S.P.E.C.I.A.L. and the character (`0..2` traits, `1` respec here) before `"Continue"` rides up
- **Before Phase 2:** **Partial.**
  - `dotnet/NewGame/Program.cs:745-752` wrote `MESG 0x801` (`FO4SF_NewGameElevator`) with two buttons only (`"Ride up"`, `"Stay"`).
  - `scripts/newgame/FO4SF_NewGameQuest.psc:663-680` checked `Near(player, PlatformX, PlatformY, PlatformZ, PlatformRadius)` once `stage >= 30`, showed `ExitMessage`, and started ascent on `button == 0`, while `FO4SF_NewGameSpecial.psc` ran a separate `21`-point terminal picker that logged `special skipped` at `stage 40`.
- **Current Build (`X3` / `B1` / `B3`):**
  - Updates `MESG 0x801` (`FO4SF_NewGameElevator`) to four buttons (`<= 4` buttons): `[0] Continue`, `[1] S.P.E.C.I.A.L.`, `[2] Character`, `[3] Stay`.
  - Pressing `[0] Continue` before `S.P.E.C.I.A.L.` has been confirmed logs `elevator continue refused: special unconfirmed` and re-opens `ExitMessage`.
  - Pressing `[1] S.P.E.C.I.A.L.` calls `OpenLiftAttributeAllocation()` -> `FO4SF_ProgressionQuest.OpenAttributeAllocation("lift")`, running Progression's `<= 7`-button paged `40`-point allocator (`28` only when `FO4SF_SpecialCreationPool28 != 0`), logging `special box shown box=<edid> buttons=<count>` (read from writer-populated `SpecialBoxNames` / `SpecialBoxButtonCounts`) and `special box press=<n> box=<edid> button=<btn> unspent=<u> step=<step>`, writing all seven attributes + skills + derived stats to `FO4SFCoreValues.esm` through `CommitSpecialAllocation`, logging `special set S=... P=... E=... C=... I=... A=... L=... sum=40 source=lift` between two `elevator prompt` lines, setting `liftSpecConfirmed = true`, and re-showing `ExitMessage`. After 3 cancelled/failed tries (`B3`), `FO4SF_CreationSpecialFallbackBox` (`0x87B`, `2` buttons) offers `"Use standard spread"` (`6/5/5/6/7/6/5` for pool `40`, `4/4/4/4/4/4/4` for pool `28`), logging `special default sum=<pool> source=lift`.
  - Any failed lift ride (`FailExit(reason)`, `B1`) increments `exitFailures`, resets ride state, returns the player to the vault platform, and logs `exit retry n=<k> reason=<r> stage=<s>` without stopping `OnTimer`; after `exitFailures >= 3`, `FO4SF_NewGameExitFallback` (`0x81A`, `2` buttons) offers `"Go up to the Commonwealth"` (`exit fallback by=move` -> `stage 40 by=fallback`) or `"Retry lift"`.
  - Pressing `[2] Character` calls `OpenLiftCharacterRespec()`, opening the looks-only creator (`Game.ShowRaceMenu(None, RaceMenuMode)`) once (`liftCharRespecUsed = true`) and logging `elevator character respec refused: limit_1` on a second attempt.
  - Sets `LegacyTerminalEnabled = false` on `FO4SF_NewGameSpecial.psc` so `special skipped` never fires on a normal run.
  - **Explicitly `NOT BUILT` this round (`X3`):** Driving tag skills, background, and traits from the Vault 111 lift prompt is **`NOT BUILT`** this round.

### 4. Map set-up runs during the ride, hidden by it, with no visible wait
- **Before Phase 2:** **Not hidden during the ride.**
  - `scripts/newgame/FO4SF_NewGameQuest.psc:854-857,870,892-937` waited until `CheckLanding` (`3.0 s` after `stage 40`) before touching `ArrivalDiscoveryId`, forcing an extra exterior tick, and did not run shared marker preparation during the ride.
- **Current Build (`X4` / `S5`):**
  - Adds one shared function `RunSharedMapSetup()` in `FO4SF_NewGameQuest.psc`, called both inside `StartAscent` when the lift begins rising (`X4`) and inside `RunWarfareBranch` (`S5`).
  - `RunSharedMapSetup()` invokes `FO4SF_MapMarkers.PrepareKnownUndiscoveredAll()` (enabling every Commonwealth marker and calling `AddToMap(False)` so all markers are known and undiscovered) and logs `map setup done markers=<n> elapsed=<s>` before the ride finishes.
  - During `rideActive`, `PrepareArrivalMarkerDuringRide()` enables `0x0A775B`, and `PreAttachArrivalMarker(player)` snaps `0x0A775B` to `(FallbackX + MergeOffsetX, FallbackY + MergeOffsetY, FallbackZ)` immediately when `FinishSurface` confirms exterior transfer.

### 5. On exit ONLY Vault 111 is discovered, and fast travel is possible from that first discovery
- **Before Phase 2:** **Implemented.**
  - `dotnet/NewGame/Program.cs:113,676` binds `ArrivalDiscoveryId` solely to `FO4Core_CommonwealthMapMarkerVault111` (`0x0A775B` in `FO4TerrainCore.esm`; `0` if a custom `--exit-anchor` is used), and `FO4SF_NewGameQuest.psc:902-946` calls `marker.SetMarkerDiscovered()` once on that single reference.
  - Note: Starfield's engine planetary landing-site marker behavior remains a separate proposal for the owner and is not altered by `FO4SFNewGame.esm`.
- **Current Build:** Preserves single-marker discovery (`SetMarkerDiscovered()` appears once in `FO4SF_NewGameQuest.psc` on `0x0A775B` for Story, while `RunWarfareBranch` discovers only the selected start row's marker via `FO4SF_MapMarkers.DiscoverSingleMarker`).

### 6. Standing on the platform later offers `"Ride down"` or `"Stay"`
- **Before Phase 2:** **Missing.**
  - `scripts/newgame/FO4SF_NewGameQuest.psc:467-469` stopped restarting timer `1` once `GetStage() >= 200`, leaving no surface return interaction on the exterior Vault 111 pad.
- **Current Build:**
  - Adds `MESG 0x80B` (`FO4SF_NewGameReturn`) with `[0] Ride down to Vault 111` and `[1] Stay`.
  - After `stage 200` (Story), maintains a `5.0 s` timer calling `CheckReturnLift(player)` once the player walks `> 12.0 m` away from the exterior arrival pad and later returns within `PlatformRadius` (`2.0 m`).

### 7. Creation sheet runs through real `Message` menus (`40`-point S.P.E.C.I.A.L., `3` tag skills, `1` background, `0..2` traits), writing to `FO4SFCoreValues.esm`
- **Before Phase 2:** **Backend math implemented; interactive `Message` menus missing.**
  - `scripts/progression/FO4SF_ProgressionQuest.psc:185-259,335-354` implemented `ApplyCreationSheet(...)` and `ApplyExitTraitRespec(...)` behind `TestModeGlobal` test stages only, with zero `MESG` records in `FO4SFProgression.esm`.
- **Current Build (`B3`):**
  - Adds `MESG` records `0x870` (`FO4SF_CreationSpecialBox`, `7` buttons: STR/PER/END, `+/-1`, `More (C/I/A/L)...`, `Confirm`, `Cancel`), `0x878` (`FO4SF_CreationSpecialPage2Box`, `7` buttons: CHA/INT/AGI/LCK, `+/-1`, `Back (S/P/E)...`, `Confirm`), `0x87B` (`FO4SF_CreationSpecialFallbackBox`, `2` buttons: `Use standard spread` / `Try again`), and `0x871..0x87A` (skills, background, traits — all `<= 7` buttons) to `FO4SFProgression.esm` (`dotnet/ProgressionCore/Program.cs`).
  - `OpenAttributeAllocation(sourceTag)` drives the paged `<= 7`-button `40`-point S.P.E.C.I.A.L. `Message` boxes on both the Vault 111 lift (`source="lift"`) and Warfare start (`source="warfare"`), logging `special box shown box=<edid> buttons=<count>` and `special box press=<n> box=<edid> button=<btn> unspent=<u> step=<step>` before writing `FO4SFCoreValues.esm` via `CommitSpecialAllocation` (or offering the standard spread after 3 cancelled/failed tries and logging `special default sum=<pool> source=<lift|warfare>`).
  - `ApplyWarfareBackground(bgIdx)` sets the faction background in `FO4SFCoreValues.esm` during Warfare start (`S5`).
  - `OpenCreationSheetMenu()` retains the `<= 7`-button `MESG` menus for tag skills (`0x871..0x872`, `0x879`), background (`0x873..0x874`), and traits (`0x875..0x876`, `0x87A`), while driving tag skills, background, and traits from the Vault 111 lift prompt itself remains **`NOT BUILT`** this round (`X3`).
