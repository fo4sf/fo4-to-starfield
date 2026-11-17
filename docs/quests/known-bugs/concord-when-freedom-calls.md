# Known-Bug Ledger: Concord — *When Freedom Calls* (`Min00`)

**Scope:** `FO4SFMission.esm` (`QUST FO4SF_Min00` `0x800`, `QUST FO4SF_CodsworthKeeper` `0x814`, `NPC_ FO4_PrestonGarvey` `0x801`, `ACHR 0x802`, `ACHR 0x803..`), `dotnet/Mission/Program.cs`, and `scripts/mission/FO4SF_Min00Quest.psc`.

## Summary Matrix

| Bug ID | Short Functional Name | Occurs in Our Conversion? | Resolution Category |
|---|---|---|---|
| `WFC-01` | Exterior Raider Straggler / Unloaded-3D Stall on Stage `20 -> 30` | `Yes` | `Fix directly (ours)` |
| `WFC-02` | Direct Approach to Preston Fails to Start Fight when Raiders Exceed `60 m` | `Mitigated` | `Fix directly (ours)` |
| `WFC-03` | Stray Friendly Fire Turns Preston Hostile to the Player | `Mitigated` | `Fix directly (ours)` |
| `WFC-04` | Museum Balcony / Upstairs Door & Post-Fight Dialogue Lockout | `Not applicable yet` | `Study community patch's documented change (owner approval needed if external read/download required)` |
| `WFC-05` | Preston Vanishes or Snaps Back to Unmerged Coordinates After Completion / Reload | `Mitigated` | `Fix directly (ours)` |
| `WFC-06` | Wave-2 Sewer Grate Deathclaw Snags Below Street Geometry | `Not applicable yet` | `Left / N-A in current cut-down stage` |
| `WFC-07` | Silent `OnStageSet` Callback Drop Skips Objectives, UI Listing, and Reward | `Mitigated` | `Fix directly (ours)` |

---

## Detailed Bug Entries

### `WFC-01` — Exterior Raider Straggler / Unloaded-3D Stall on Stage `20 -> 30`
- **Plain Functional Description:** Across shipped known-issue lists and community unofficial-patch changelogs, *When Freedom Calls* frequently stalls on the "Kill the Raiders / Clear Concord of Hostiles" objective when one raider falls under street geometry, wanders out of loaded cells, or never enters combat so the kill counter never reaches total raiders.
- **Occurs in Our Conversion?:** `Yes` (partially mitigated, edge case open) — `scripts/mission/FO4SF_Min00Quest.psc` (`OnTimer`, lines `256-281`, and `NextStage`, lines `312-329`) requires `dead == Raiders.Length` to advance from stage `20` to `30`, and puts every non-fighting raider into `StartCombat(player)` once `prestonFound` or `stage >= 20` **only while `r.Is3DLoaded()` is true**. If a raider's initial `MoveOver` missed `10` times (`relocateFails >= 10` budget exhausted at line `248`), or if a living raider clips below terrain / unloads beyond 3D distance mid-fight, `dead` stays at `N - 1` and stage `20` never advances to `30`.
- **Proposed Resolution:** `Fix directly (ours)` — In `FO4SF_Min00Quest.psc`: (1) reset `relocateFails` on `OnPlayerLoadGame` for `FO4SF_Min00` as the keeper already does (`FO4SF_Min00` currently does not register `OnPlayerLoadGame` when `KeeperOnly == False`, line `172`), and (2) during stage `20`, if any living raider stands below `PrestonLocalZ - 15.0` m or remains `> PlaceRadius` (`300 m`) from the museum door for `> 30` ticks while the player is at the museum street, `MoveTo` that straggler onto a street offset `25 m` in front of the museum door.
- **PC Card Reproduction & Check:** Trigger stage `20` at Concord, kite one raider far down the street or reload mid-fight, eliminate visible raiders, and inspect `fo4sf_mission.0.log` (`status stage=20 dead=X/N nearest_raider=...`) to verify all `N` raiders remain reachable and `dead=N/N` transitions cleanly to `stage 30`.

### `WFC-02` — Direct Approach to Preston Fails to Start Fight when Raiders Exceed `60 m`
- **Plain Functional Description:** Walking straight to the stage `10` quest marker on Preston along a path > `60 m` from placed exterior raiders leaves all raiders passive and stage `10` unresponsive when activating Preston.
- **Occurs in Our Conversion?:** `Mitigated` — Reproduced in PC run 3 (`nearest_raider` `91..129 m` away, `preston activated at stage 10` five times with no stage change) and mitigated in `scripts/mission/FO4SF_Min00Quest.psc` (`OnActivate` lines `220-221`, `FoundPreston` lines `228-236`, `OnTimer` lines `252-278`): coming within `FindRadius` (`20.0 m`) of a living Preston or activating him sets `prestonFound = True`, advances to stage `20`, and forces `r.StartCombat(player)` on every loaded raider regardless of distance.
- **Proposed Resolution:** `Fix directly (ours)` — Implemented in `FO4SF_Min00Quest.psc`; retain `FindRadius = 20.0` + `OnActivate` trigger and pair with `WFC-01`'s 3D-load leash for raiders `> 90 m` away.
- **PC Card Reproduction & Check:** Approach Preston at stage `10` without passing within `60 m` of a raider, stop at `18 m` (or press `E` on him), and verify `fo4sf_mission.0.log` logs `found preston`, `stage 20`, and `startcombat raider` lines.

### `WFC-03` — Stray Friendly Fire Turns Preston Hostile to the Player
- **Plain Functional Description:** Hitting Preston with stray gunfire or explosives during the Concord street battle causes him to aggro onto the player, blocking post-combat quest turn-in.
- **Occurs in Our Conversion?:** `Mitigated` — Reproduced in early PC sessions (where neutral factionless Preston ignored `IgnoreFriendlyHits`) and mitigated across `dotnet/Mission/Program.cs` (lines `89-93`, placing Preston in `FO4SF_MinutemenFaction` `0x81F` with `Ally` relation to `PlayerFaction` `0x01C21C`) and `scripts/mission/FO4SF_Min00Quest.psc` (`Preston.IgnoreFriendlyHits(True)` at line `129`, `Preston.StopCombat()` at stage `30` line `202`, and per-tick `if Preston.GetCombatTarget() == player -> Preston.StopCombat()` at lines `298-301`).
- **Proposed Resolution:** `Fix directly (ours)` — Retain `FO4SF_MinutemenFaction` `Ally` relation enforced by `dotnet/Mission check` plus `StopCombat()` safety net.
- **PC Card Reproduction & Check:** During stage `20`, fire two stray shots into Preston before killing the final raider; verify Preston does not attack the player at stage `30` and `stage 40 -> 200` completes normally.

### `WFC-04` — Museum Balcony / Upstairs Door & Post-Fight Dialogue Lockout
- **Plain Functional Description:** In shipped `Min00`, the upstairs Museum of Freedom room doors can stay locked or Garvey can loop generic busy barks without starting completion dialogue if interior raiders die before balcony/hallway scene triggers finish or if the player exits mid-conversation.
- **Occurs in Our Conversion?:** `Not applicable yet` (interior museum & dialogue scenes cut; exterior turn-in `Mitigated`) — The current cut-down `FO4SF_Min00` places Preston outside the museum entrance (`ACHR 0x802`) and completes stage `30 -> 40` via either `OnActivate` (line `222`) or `TalkRadius` (`3.0 m` proximity, line `282`), avoiding scene-lock deadlocks.
- **Proposed Resolution:** `Study community patch's documented change (owner approval needed if external read/download required)` — Queue `REQ-KB-02` before restoring `ConcordMuseum01` interior stages and `DialogueConcordArea` scenes, keeping an idempotent activation/proximity fallback if a scene fails to advance after hostiles are dead.
- **PC Card Reproduction & Check:** Once stage `30` ("Talk to Preston Garvey") displays, walk within `2.8 m` of Preston (or press `E`); confirm `stage 40`, `reward credits=100`, and `complete stage=200` in `fo4sf_mission.0.log`.

### `WFC-05` — Preston Vanishes or Snaps Back to Unmerged Coordinates After Completion / Reload
- **Plain Functional Description:** Persistent actors placed in the Commonwealth persistent cell snap back `~2,955 m` to unmerged local coordinates on cell reload or walk away (`~0.9 m/s`) once `FO4SF_Min00` reaches stage `200` and cancels its `1 s` timer.
- **Occurs in Our Conversion?:** `Mitigated` — `FO4SF_CodsworthKeeper` (`0x814`, `scripts/mission/FO4SF_Min00Quest.psc` `KeepPreston`, `PlacePreston`, `HoldPreston`, `ReleaseInFight`, lines `389-573`) runs an uncanceled `5 s` timer across save loads, places Preston at fixed merged coordinates `(-2011.14, -1697.54, 89.09)` when the player is within `PlaceRadius = 300.0 m`, and calls `SetRestrained(True)` when calm (verified in-game 10 Nov with `preston_off = 0.2 m` over `90 s`). Note: `--no-codsworth` builds omit `FO4SF_CodsworthKeeper` and therefore lack post-200 keeping.
- **Proposed Resolution:** `Fix directly (ours)` — Keep `FO4SF_CodsworthKeeper` active in standard builds, and move `FO4SFMission.esm` persistent ACHRs into merged world coordinates during the world-frame consolidation so editor coordinates equal live coordinates natively.
- **PC Card Reproduction & Check:** After `complete stage=200`, walk `> 400 m` away from Concord and return (or reload a completed save); verify Preston stands at the museum door and `fo4sf_mission.0.log` shows `keeper status preston` with `off <= 25.0` and `held=true`.

### `WFC-06` — Wave-2 Sewer Grate Deathclaw Snags Below Street Geometry
- **Plain Functional Description:** In shipped full `Min00`, the Concord Deathclaw emerging from the street civic-access grate frequently gets stuck inside the sewer pit or storefront meshes, stalling the final combat objective.
- **Occurs in Our Conversion?:** `Not applicable yet` — Roof Power Armor, minigun, wave-2 raiders, and the Concord Deathclaw are excluded in the current B4 cut-down slice (`docs/mission/when-freedom-calls.md`).
- **Proposed Resolution:** `Left / N-A in current cut-down stage` — When wave-2 combat is added (`REQ-KB-02`), include a subterranean Z-threshold stuck timer (`> 20 s` below street Z after emerge) that relocates the Deathclaw onto the open street node.
- **PC Card Reproduction & Check:** Confirm cut-down `FO4SF_Min00` reaches `complete stage=200` after the initial Concord raider group without hanging on wave-2 conditions.

### `WFC-07` — Silent `OnStageSet` Callback Drop Skips Objectives, UI Listing, and Reward
- **Plain Functional Description:** Custom `StartGameEnabled` quests in Starfield can advance `GetStage()` without firing `Event OnStageSet`, leaving HUD objectives hidden, Missions-tab listing blank (when `QTYP` is unset), and stage `40` rewards ungranted.
- **Occurs in Our Conversion?:** `Mitigated` — Observed on PC (18 Oct) and mitigated by: (1) setting `QuestTypeSideQuest` (`0x047600`) in `dotnet/Mission/Program.cs` (line `86`), and (2) executing stage actions synchronously inside `AdvanceTo(n)` -> `Apply(n)` guarded by `if auiStageID <= applied return` (`scripts/mission/FO4SF_Min00Quest.psc` lines `177-214`).
- **Proposed Resolution:** `Fix directly (ours)` — Enforce `QuestTypeSideQuest` in `dotnet/Mission check` and synchronous `AdvanceTo` -> `Apply` idempotency across all converted quests.
- **PC Card Reproduction & Check:** Start a session with `FO4SFMission.esm` folded in, open the Missions menu to confirm *When Freedom Calls* is listed, play through stage `200`, and verify `stage 10`, `stage 20`, `stage 30`, `stage 40`, `reward credits=100`, and `stage 200` all appear once in `fo4sf_mission.0.log`.
