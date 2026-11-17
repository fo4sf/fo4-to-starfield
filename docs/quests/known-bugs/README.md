# Converted Quest Known-Bug Ledgers & Clean-Room Verification Index

This directory tracks known quest progression, AI package, coordinate-frame, and persistence bugs for the quest slices converted into Starfield (`FO4SFNewGame.esm` and `FO4SFMission.esm`). Each ledger maps functional failure modes known from shipped issue lists and community unofficial-patch changelogs against our actual C# Mutagen generators and Papyrus state machines.

## 1. Quest Ledgers

| Quest Slice | Plugin & Scripts | Ledger File | Bug Count |
|---|---|---|---|
| Opening Sequence (Vault 111 Cryo -> Gear Door -> Lift -> Surface / Sanctuary Handoff) | `FO4SFNewGame.esm`, `scripts/newgame/FO4SF_NewGameQuest.psc`, `dotnet/NewGame/Program.cs` | [opening-sequence.md](opening-sequence.md) | 6 |
| Concord: *When Freedom Calls* (`Min00` Cut-Down Street Fight & Garvey Turn-In) | `FO4SFMission.esm` (`0x800`, `0x814`), `scripts/mission/FO4SF_Min00Quest.psc`, `dotnet/Mission/Program.cs` | [concord-when-freedom-calls.md](concord-when-freedom-calls.md) | 7 |
| Preston Companion / Follow Slice (`COMPreston` Stand-In & Hold Hand-Off) | `FO4SFMission.esm` (`0x815`), `scripts/mission/FO4SF_COMPreston.psc`, `scripts/mission/FO4SF_Min00Quest.psc` | [preston-follow.md](preston-follow.md) | 6 |

---

## 2. Ledger Schema

Every bug entry in each quest ledger MUST include all five fields below:

1. **Bug ID & Functional Name:** Stable identifier (`OPEN-XX`, `WFC-XX`, `COMP-XX`) and short clean-room functional title.
2. **Plain Functional Description:** Concise clean-room description of the failure mode synthesized from shipped known-issue lists, community unofficial-patch changelogs, and observed conversion architecture.
3. **Occurs in Our Conversion?:** One of `Yes`, `Mitigated`, or `Not applicable yet`, citing the exact file, function, stage, or record condition in our repository.
4. **Proposed Resolution:** One of:
   - `Fix directly (ours)` — concrete record/Papyrus mechanism we own and can implement directly.
   - `Study community patch's documented change (owner approval needed if external read/download required)` — links to a queued item in Section 4 below.
   - `Left / N-A in current cut-down stage` — explicitly out of scope until the corresponding cut content is restored.
5. **PC Card Reproduction & Check:** Deterministic in-game steps and structured user-log assertions for Claude (PC) to verify absence or presence of the defect.

---

## 3. Clean-Room & Public-Surface Policy

- **Functional facts only:** Record only functional bug names and plain-language behavioral descriptions. Never copy verbatim prose, script source, or record data from external mods or wikis.
- **Zero third-party mod names:** Refer generically to `"shipped known-issue lists"` and `"community unofficial-patch changelogs"`; never name specific third-party patches, mod packs, or authors.
- **Zero unapproved downloads or external reads:** No external files or web pages are downloaded in this workflow. Any external public changelog or wiki page that would clarify an edge case is queued in Section 4 for explicit per-item owner approval first.

---

## 4. Owner Download / Read Approval Request Queue

No downloads or external web fetches were performed for these ledgers. The following public documentation/changelog reads are requested for **per-item owner approval** before converting the next quest stages:

| Request ID | Public Documentation / Changelog Target (Read-Only, No Binary Download) | Target Quest Slice | Specific Engineering Question to Answer | Status |
|---|---|---|---|---|
| `REQ-KB-01` | Public community unofficial-patch quest changelog section covering opening Vault 111 (`MQ101`) and Sanctuary Hills (`MQ102`) stage transitions | `opening-sequence.md` (`OPEN-05`, `OPEN-06`) | Which exact quest-stage completion flags and dialogue conditions prevent Sanctuary patrol/conversation deadlocks when the player bypasses Sanctuary Hills and enters Concord first? | **Awaiting Owner Approval** |
| `REQ-KB-02` | Public community wiki known-bugs and stage table documentation for `Min00` (Concord Museum interior, balcony scene, roof Power Armor, and Deathclaw wave) | `concord-when-freedom-calls.md` (`WFC-01`, `WFC-04`, `WFC-06`) | Which interior trigger/scene lockouts and exterior wave-2 spawn stuck states occur most often between the upstairs Garvey room and the street Deathclaw fight so our stage machine can guard them upfront? | **Awaiting Owner Approval** |
| `REQ-KB-03` | Public community unofficial-patch companion/follower changelog entries for Garvey recruitment, package priority, and Sanctuary settlement sandbox hand-off | `preston-follow.md` (`COMP-04`, `COMP-05`) | What package-stack or alias-clearing conditions prevent a dismissed quest-giver follower from walking endlessly between Concord and Sanctuary or locking trade/recruitment prompts? | **Awaiting Owner Approval** |
| `REQ-KB-04` | Public community wiki stage & bug notes for the Concord-to-Sanctuary group march and post-Concord Minutemen radiant hand-off (`Min01`) | `concord-when-freedom-calls.md` / `preston-follow.md` | Which arrival conditions at Sanctuary Hills fail when the player fast-travels or unloads Concord mid-march after stage `200`? | **Awaiting Owner Approval** |
