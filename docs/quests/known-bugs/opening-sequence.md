# Known-Bug Ledger: Opening Sequence (Vault 111 Cryo -> Gear Door -> Surface / Sanctuary Handoff)

**Scope:** `FO4SFNewGame.esm` (`QUST FO4SF_NewGame`), `dotnet/NewGame/Program.cs`, `scripts/newgame/FO4SF_NewGameQuest.psc`, `scripts/newgame/FO4SF_NewGameVersion.psc`, and Sanctuary robot placement in `FO4SFMission.esm` (`FO4SF_CodsworthKeeper` `0x814`, `scripts/mission/FO4SF_Min00Quest.psc`).

## Summary Matrix

| Bug ID | Short Functional Name | Occurs in Our Conversion? | Resolution Category |
|---|---|---|---|
| `OPEN-01` | Cryo Pod Exit Floor Clipping / Infinite First Load Stall | `Mitigated` | `Fix directly (ours)` |
| `OPEN-02` | Vault 111 Gear Door Stuck Closed on Console Activation | `Mitigated` | `Fix directly (ours)` |
| `OPEN-03` | Character Creation Save / HUD Lock Persisting After Vault Exit | `Mitigated` | `Fix directly (ours)` |
| `OPEN-04` | Exterior Vault Lift Platform Fall-Through on Surface Arrival | `Mitigated` | `Fix directly (ours)` |
| `OPEN-05` | Sanctuary House-Sweep Patrol Stall & Unmerged Drift | `Not applicable yet` | `Study community patch's documented change (owner approval needed if external read/download required)` |
| `OPEN-06` | Skipping Sanctuary Straight to Concord Desyncs Early Objectives | `Mitigated` | `Fix directly (ours)` |

---

## Detailed Bug Entries

### `OPEN-01` — Cryo Pod Exit Floor Clipping / Infinite First Load Stall
- **Plain Functional Description:** From shipped known-issue lists and community unofficial-patch changelogs, releasing the player from the opening cryo pod before interior collision finishes loading—or failing to execute a startup `MoveTo` from the `StartupQuest_DO` quest—leaves the player sunk below the pod floor or trapped on an infinite main-menu loading screen.
- **Occurs in Our Conversion?:** `Mitigated` — `scripts/newgame/FO4SF_NewGameQuest.psc` (`Begin`, `EnterVault`, `CheckPod`, stages `0 -> 10`) runs from whichever of `OnQuestStarted` / `OnQuestInit` fires first, places the player at `PodZ + PodLift` (`PodLift = 0.3 m` above the raw pod Z so they settle onto floor collision rather than beneath it), waits on `player.WaitFor3DLoad()` before `FadeIn`, and calls `StandDown` -> `HandBack` if the vault anchor fails to resolve so the initial load screen never hangs silently.
- **Proposed Resolution:** `Fix directly (ours)` — Keep `PodLift = 0.3` and the `CheckPod` audit (`PodRadius = 1.0`, `PodDrop = 0.5`); if `pod settle ok=false` is ever logged on slow storage, issue one corrective `SetPosition(PodX, PodY, PodZ + PodLift)` once 3D is confirmed loaded.
- **PC Card Reproduction & Check:** Start a New Game from the main menu; verify the vault fades in at the cryo pod without snapping to the cell's COC marker, and verify `fo4sf_newgame.0.log` contains `enter vault ok=true`, `fade in`, and `pod settle ok=true` (`drop <= 0.5`).

### `OPEN-02` — Vault 111 Gear Door Stuck Closed on Console Activation
- **Plain Functional Description:** In shipped Vault 111 exits, activating the door control console frequently fails to open the main vault gear door when the wrist-device plug-in animation or door open-state transition stalls, trapping the player inside the vault interior.
- **Occurs in Our Conversion?:** `Mitigated` — `scripts/newgame/FO4SF_NewGameQuest.psc` (`InVault`, stage `20 -> 30`) bypasses the fragile wrist-plug animation and opens `CogDoorId` (`VltGearDoor01`) via `cogDoor.SetOpen(True)` once the player enters `ConsoleRadius` (`2.5 m`), logging `cog door open_state before=... after=...`. Residual risk: stage `30` is set immediately on the first call, so if `SetOpen(True)` is dropped while the door reference is still streaming, `InVault` does not retry on stage `30`.
- **Proposed Resolution:** `Fix directly (ours)` — Keep polling `cogDoor.GetOpenState()` during stage `30` while `player.IsInInterior()` is true, re-issuing `cogDoor.SetOpen(True)` (up to 5 ticks) if the door still reports closed (`3`).
- **PC Card Reproduction & Check:** At stage `20` inside Vault 111, walk within `2.5 m` of the gear door console; confirm the gear door opens visually and `fo4sf_newgame.0.log` records `cog door open_state` and `stage 30`.

### `OPEN-03` — Character Creation Save / HUD Lock Persisting After Vault Exit
- **Plain Functional Description:** Known opening-sequence bug where missed character-creation menu close callbacks or latched chargen flags leave Quicksave/Save disabled or hide HUD elements permanently after exiting Vault 111.
- **Occurs in Our Conversion?:** `Mitigated` — `scripts/newgame/FO4SF_NewGameQuest.psc` (`FadeIn`, lines `336-338`) explicitly calls `Game.SetInChargen(false, false, false)` and `Game.SetCharGenHUDMode(0)`, and stage `10` enforces a `LooksWait = 120.0` s fallback timer (`OnTimer`, lines `402-405`) so a missed `FO4SF_NewGameLooks` close event cannot stall stage `10 -> 20`.
- **Proposed Resolution:** `Fix directly (ours)` — Re-apply `Game.SetInChargen(false, false, false)` and `Game.SetCharGenHUDMode(0)` defensively at stage `40` (`FinishSurface`) so any late menu interaction inside the vault cannot carry a save/HUD lock onto the Commonwealth exterior.
- **PC Card Reproduction & Check:** Complete the Vault 111 exit to stage `200`, open the pause menu on the Commonwealth surface to confirm Save and Quicksave are enabled, verify HUD crosshair/compass visibility, and check `saving and HUD on` in `fo4sf_newgame.0.log`.

### `OPEN-04` — Exterior Vault Lift Platform Fall-Through on Surface Arrival
- **Plain Functional Description:** Riding the Vault 111 lift to the exterior surface can position the player before exterior cell collision finishes loading (or over an unsolid lift platform mesh), dropping the player beneath the Vault 111 hill terrain.
- **Occurs in Our Conversion?:** `Mitigated` — `scripts/newgame/FO4SF_NewGameQuest.psc` (`Surface`, `FinishSurface`, `CheckLanding`, stages `30 -> 40 -> 200`) splits the transition across ticks (`MoveTo` onto `ExitAnchorId`, wait until `!player.IsInInterior()` and `player.Is3DLoaded()`, up to `SurfaceTries = 3` `SetPosition` calls onto `ArrivalX/Y + MergeOffset`), and `3.0 s` later runs `CheckLanding` (`FallDrop = 3.0 m`), moving a fallen player onto `FallbackX/Y + MergeOffset, FallbackZ + 1.0`.
- **Proposed Resolution:** `Fix directly (ours)` — Retain the two-stage `FinishSurface` + `CheckLanding` fallback until the converted Vault 111 exterior platform collision is proven solid across repeated cold loads.
- **PC Card Reproduction & Check:** Step onto the Vault 111 lift platform (`PlatformRadius = 2.5 m`), choose button `0` to ride up, wait `4 s` on the surface, and confirm `fo4sf_newgame.0.log` logs `surface setposition ok=true`, `landed z=...` (or clean `fallback pos=...` recovery), and `stage 200`.

### `OPEN-05` — Sanctuary House-Sweep Patrol Stall & Unmerged Drift
- **Plain Functional Description:** From shipped known-issue lists and community unofficial-patch changelogs, Codsworth frequently stalls mid-patrol while sweeping Sanctuary Hills houses with the player or walks off / becomes unresponsive if nearby insects die out of order or cell reload resets AI state.
- **Occurs in Our Conversion?:** `Not applicable yet` (patrol/sweep scene cut; drift defect `Mitigated`) — The Sanctuary house-sweep quest stages are not yet converted. For Codsworth's Sanctuary placement (`FO4SFMission.esm` `ACHR 0x811` kept by `FO4SF_CodsworthKeeper` `0x814`), `scripts/mission/FO4SF_Min00Quest.psc` (`PlaceCodsworth` + `HoldCodsworth`) mitigates his observed `0.34 m/s` drift back toward unmerged editor coordinates by moving him to fixed merged coordinates `(-2346.709, -1406.163, 111.734)` within `PlaceRadius = 300.0 m` and calling `SetRestrained(True)` while calm (`ReleaseCodsworthInFight` releases him during combat).
- **Proposed Resolution:** `Study community patch's documented change (owner approval needed if external read/download required)` — Queue `REQ-KB-01` before converting `MQ102` Sanctuary dialogue/patrol stages, and author `ACHR 0x811` directly in merged world coordinates so Codsworth's editor home matches Sanctuary without continuous keeper put-backs.
- **PC Card Reproduction & Check:** Walk to Sanctuary Hills near Codsworth's house, wait `70 s`, and verify `fo4sf_mission.0.log` contains `hold codsworth by=keeper` and `keeper status codsworth` with `off <= 25.0` and `disabled=false`.

### `OPEN-06` — Skipping Sanctuary Straight to Concord Desyncs Early Objectives
- **Plain Functional Description:** Walking directly from Vault 111 to Concord and engaging the Museum street raiders without speaking to Codsworth in Sanctuary can leave early opening objectives uncompleted or stuck in the journal.
- **Occurs in Our Conversion?:** `Mitigated` — `FO4SF_NewGameQuest` finishes cleanly at stage `200` on surface landing (`CheckLanding`) and `FO4SF_Min00` (`0x800`) runs independently from stage `10` with no blocking dependency on Sanctuary dialogue.
- **Proposed Resolution:** `Fix directly (ours)` — When intermediate Sanctuary-to-Concord breadcrumb objectives (`MQ102`) are added, mark them `SetObjectiveCompleted` idempotently whenever `FO4SF_Min00.GetStage() >= 20` is observed so skipping Sanctuary never leaves stale objectives active.
- **PC Card Reproduction & Check:** After reaching `stage 200` on the Vault 111 surface, walk straight to Concord without entering Sanctuary Hills; confirm `FO4SF_Min00` advances `10 -> 20 -> 30 -> 40 -> 200` cleanly in `fo4sf_mission.0.log`.
