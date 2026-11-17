# Known-Bug Ledger: Preston Companion & Follow Slice (`COMPreston` Stand-In)

**Scope:** `FO4SFMission.esm` (`QUST FO4SF_COMPreston` `0x815`, alias `0` `Preston` with `DefaultMaster_FollowPackage` `0x0301C5`), `dotnet/Mission/Program.cs` (lines `106-115`), `scripts/mission/FO4SF_COMPreston.psc`, `scripts/mission/FO4SF_Min00Quest.psc` (`BeginFollow`, `PlacePreston`, `KeepCodsworthLoad`), and `docs/mission/preston-follow-pc-card.md`.

## Summary Matrix

| Bug ID | Short Functional Name | Occurs in Our Conversion? | Resolution Category |
|---|---|---|---|
| `COMP-01` | Museum-Door Restraint Re-Assertion or Premature Stage-40 Trigger | `Mitigated` | `Fix directly (ours)` |
| `COMP-02` | Reserved-Alias Collision or Unchecked `ForceRefTo` Fill Result | `Mitigated` | `Fix directly (ours)` |
| `COMP-03` | Follower Stranded Behind Scripted Interior Load Doors / Long Cell Gaps | `Yes` | `Fix directly (ours)` |
| `COMP-04` | Missing Wait / Trade / Settlement-Dismiss State Machine | `Yes` | `Study community patch's documented change (owner approval needed if external read/download required)` |
| `COMP-05` | Post-Bleedout / Post-Combat Follow Package Stall | `Yes` | `Fix directly (ours)` |
| `COMP-06` | Save-Quit-Reload Drops Runtime `SetLinkedRef` or Active Follow Package | `Yes` | `Fix directly (ours)` |

---

## Detailed Bug Entries

### `COMP-01` — Museum-Door Restraint Re-Assertion or Premature Stage-40 Trigger
- **Plain Functional Description:** When transitioning Preston from his post-battle museum-door hold into an active follower, any quest instance (`FO4SF_Min00` or `FO4SF_CodsworthKeeper`) left un-disarmed will teleport him back to the museum door and re-apply `SetRestrained(True)` within `5 s`; conversely, starting follow before stage `30` completes triggers the `3.0 m` `TalkRadius` rule as soon as he closes distance.
- **Occurs in Our Conversion?:** `Mitigated` (door hold) / `Yes` (if invoked mid-mission via test console) — `scripts/mission/FO4SF_COMPreston.psc` (`FollowTest`, lines `22-27`) calls `BeginFollow()` on both `FO4SF_Min00` (`0x800`) and `FO4SF_CodsworthKeeper` (`0x814`) before calling `preston.SetRestrained(False)`, and `KeepCodsworthLoad()` (`FO4SF_Min00Quest.psc` line `161`) preserves `prestonFollow` across reloads. However, `prestonFollow` is stored separately on two script instances rather than one shared `GLOB`, and invoking `FollowTest` at stage `30` immediately satisfies `dp < TalkRadius` (`docs/mission/preston-follow-pc-card.md` line `43`).
- **Proposed Resolution:** `Fix directly (ours)` — Store follow state in a single non-constant `GLOB` (`FO4SF_PrestonFollowing`) read by both `FO4SF_Min00` and `FO4SF_CodsworthKeeper`, and gate story recruitment behind `FO4SF_Min00.GetStage() >= 200` when wired to the Concord completion talk.
- **PC Card Reproduction & Check:** At the museum door with Preston held, run `cgf "FO4SF_COMPreston.FollowTest"`, walk `> 25 m` away, wait `65 s`, and verify `fo4sf_mission.0.log` logs `follow preston armed by=mission`, `follow preston armed by=keeper`, `follow preston test-only`, and **zero** subsequent `hold preston` or `moved Preston` lines.

### `COMP-02` — Reserved-Alias Collision or Unchecked `ForceRefTo` Fill Result
- **Plain Functional Description:** In Creation Engine / Starfield quests, forcing an actor into a follower `ReferenceAlias` fails silently when an active mission quest (`FO4SF_Min00` objective-marker alias `0`) already holds a `Reserved` lock on that actor and the follower alias lacks `AllowReserved`.
- **Occurs in Our Conversion?:** `Mitigated` (record flags) / minor script logging gap — `dotnet/Mission/Program.cs` (lines `109-115`) sets `Optional` + `AllowReserved` on `FO4SF_COMPreston` (`0x815`) alias `0` (`Preston`). Note in `scripts/mission/FO4SF_COMPreston.psc` (lines `58-60`): `filled = 1` is assigned whenever `followAlias != None` without reading back `followAlias.GetActorReference() == preston` after `ForceRefTo(preston)`.
- **Proposed Resolution:** `Fix directly (ours)` — Keep `Optional | AllowReserved` enforced in `dotnet/Mission check`, and update `FO4SF_COMPreston.psc` to set `filled = 1` only when `followAlias.GetReference() == (preston as ObjectReference)` reads true after `ForceRefTo`.
- **PC Card Reproduction & Check:** Run `cgf "FO4SF_COMPreston.FollowTest"` on an install containing `FO4SF_COMPreston.pex`; check `fo4sf_mission.0.log` for `filled=1 linked=player released=True` followed `2 s` later by `follow preston package=<id>` matching `0301C5` low hex digits.

### `COMP-03` — Follower Stranded Behind Scripted Interior Load Doors / Long Cell Gaps
- **Plain Functional Description:** Shipped and custom followers driven solely by an AI follow package frequently fail to cross scripted `MoveTo` interior load doors (`FO4SF_LoadDoor`) or get stranded in unloaded exterior cells when the player sprints or teleports ahead.
- **Occurs in Our Conversion?:** `Yes` — `FO4SF_COMPreston` (`0x815`) attaches `DefaultMaster_FollowPackage` (`0x0301C5`) without starting Starfield's host follower quest (`0x0000D773`) or registering a player cell-change catch-up handler (`FO4SF_COMPreston.psc` lines `3-9`, `55-62`).
- **Proposed Resolution:** `Fix directly (ours)` — Add a quest script on `FO4SF_COMPreston` (`0x815`) polling or listening on player interior/cell transitions while alias `0` is filled: when `player.GetParentCell() != preston.GetParentCell()` (across an interior door) or `player.GetDistance(preston) > 120.0` m outside combat, `MoveTo` Preston `2.0 m` behind the player and call `preston.EvaluatePackage()`.
- **PC Card Reproduction & Check:** Arm follow with `cgf "FO4SF_COMPreston.FollowTest"`, enter a converted interior via a `FO4SF_LoadDoor` door and exit back to the Commonwealth; check whether Preston appears in the player's cell within `5 s` (`GetDistance(player) < 15 m`).

### `COMP-04` — Missing Wait / Trade / Settlement-Dismiss State Machine
- **Plain Functional Description:** From shipped known-issue lists and community unofficial-patch changelogs, dismissing Preston or toggling Wait/Follow frequently causes him to walk endlessly back to Concord/Sanctuary mid-dialogue, lose his settlement home assignment, or lock out companion trade prompts.
- **Occurs in Our Conversion?:** `Yes` (explicitly deferred in current slice) — `FO4SF_COMPreston.psc` (lines `2-5`) and `docs/mission/preston-follow-pc-card.md` (line `13`) implement only `FollowTest`; Wait, Trade (`OpenInventory`), and Dismiss (clearing `SetLinkedRef(None)` and `followAlias.Clear()` without re-arming museum-door `SetRestrained(True)`) are not yet implemented.
- **Proposed Resolution:** `Study community patch's documented change (owner approval needed if external read/download required)` — Queue `REQ-KB-03` for package/dismiss edge cases, then implement explicit `Follow`, `WaitHere`, `Trade`, and `DismissToHome` entry points on `FO4SF_COMPreston` so Dismiss assigns a Sanctuary/settlement anchor instead of reverting to the museum-door restraint.
- **PC Card Reproduction & Check:** Confirm current card boundary (`NOT_BUILT` for Wait/Trade/Dismiss in `preston-follow-pc-card.md`); once implemented, verify Dismiss clears alias `0`, leaves `SetRestrained` false, and keeps Preston within his assigned settlement radius.

### `COMP-05` — Post-Bleedout / Post-Combat Follow Package Stall
- **Plain Functional Description:** Essential followers knocked into bleedout during combat can stand idle at the combat site after hostiles die instead of resuming their follow package as the player walks away.
- **Occurs in Our Conversion?:** `Yes` — `FO4_PrestonGarvey` (`0x801`) is `Essential`, and `FO4SF_COMPreston.psc` calls `preston.EvaluatePackage()` only once inside `FollowTest()` (line `62`), with no `OnCombatStateChanged` or `OnExitBleedout` listener on alias `0`.
- **Proposed Resolution:** `Fix directly (ours)` — Attach a `ReferenceAlias` script on `FO4SF_COMPreston` alias `0` handling `OnCombatStateChanged(Actor akTarget, int aeCombatState)` that calls `GetActorReference().EvaluatePackage()` whenever `aeCombatState == 0`.
- **PC Card Reproduction & Check:** With Preston following, lure raiders until Preston enters bleedout, defeat the raiders, walk `40 m` away, and verify Preston stands up and closes distance to `< 10 m` within `15 s`.

### `COMP-06` — Save-Quit-Reload Drops Runtime `SetLinkedRef` or Active Follow Package
- **Plain Functional Description:** Runtime `SetLinkedRef(player)` links applied by a one-shot global function without a persistent load-game check can fail to re-select `DefaultMaster_FollowPackage` after quitting to desktop and reloading a save.
- **Occurs in Our Conversion?:** `Yes` (unverified in game; no reload hook on `FO4SF_COMPreston`) — `KeepCodsworthLoad` keeps `prestonFollow = True` on `FO4SF_CodsworthKeeper`, preventing the museum-door hold from returning, but `FO4SF_COMPreston` (`0x815`) has no `Actor.OnPlayerLoadGame` handler to re-assert `SetLinkedRef(player)` + `EvaluatePackage()` and log post-load package state.
- **Proposed Resolution:** `Fix directly (ours)` — Register `Actor.OnPlayerLoadGame` on `FO4SF_COMPreston` so every save load where alias `0` is filled re-asserts `preston.SetLinkedRef(player)`, calls `preston.EvaluatePackage()`, and logs `follow reload linked=... package=...`.
- **PC Card Reproduction & Check:** Run `cgf "FO4SF_COMPreston.FollowTest"`, confirm Preston follows `> 25 m`, save to throwaway save `FO4SF_Throwaway_PrestonFollow_DeleteMe`, quit to desktop, relaunch and load that save, walk `30 m` to verify Preston still follows, then quit without saving and delete `FO4SF_Throwaway_PrestonFollow_DeleteMe`.
