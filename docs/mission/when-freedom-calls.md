# A first mission: cut-down "When Freedom Calls" (2026-10-18, Claude-cloud)

Phase B4 of docs/ROADMAP.md, built from the anatomy in docs/spikes/B4-mission-anatomy.md. Status: **built and checked
offline on synthetic masters only; not yet run on the real game files or in game.** Labels as in docs/ai/research-log.md.

## What the plugin holds

`FO4SFMission.esm` (dotnet/Mission), masters Starfield.esm, FO4TerrainCore.esm, FO4ActorRaider.esm:

| record | what |
|---|---|
| QUST `FO4SF_Min00` 0x800 | the quest, start game enabled, named from Fallout 4's Min00; stages 10 / 20 / 30 / 40 / 200 (200 completes it); objectives 10 / 85 / 86 with Min00's own texts (Find the Last Minutemen, Kill the Raiders, Talk to Preston Garvey); a reference alias forced to Preston (objective markers; `--no-alias` drops it) |
| NPC_ `FO4_PrestonGarvey` 0x801 | the raider plugin's calm probe (no factions, Spacer template) under Preston's Fallout 4 name, Essential, Unique: Preston's identity on a Starfield stand-in body, as ROADMAP B2 allows while the face pipeline is open |
| ACHR 0x802 | Preston, at the point where Fallout 4 puts the player outside the Museum of Freedom's front door |
| ACHR 0x803 on | up to 8 raiders (FO4_LvlRaider) at Fallout 4's own Concord positions: the enabled placed raiders within 120 m of that door |
| WRLD + CELL override | the core world `FO4Core_Commonwealth` and its persistent cell, holding only the ACHRs above |

Positions are Fallout 4's divided by 70, the core's frame (make_core64c.py). Because the plugin copies the core's world
record, it is rebuilt whenever FO4TerrainCore.esm changes; plan.json records the masters' hashes.

## What the script does (scripts/mission/FO4SF_Min00Quest.psc)

A one-second check replaces Fallout 4's triggers, scenes and fragments:

1. Stage 10 at start: "Find the Last Minutemen" (marker on Preston).
2. A living raider within 60 m of the player that is not fighting is put into combat with the player (Fallout 4's
   DN092 does the same with StartCombat; our raider never engaged unprompted, npc_combat_c1, and engaged when forced,
   npc_combat_c2/c4): stage 20, "Kill the Raiders".
3. Every raider dead: stage 30, "Talk to Preston Garvey".
4. Activating Preston, or standing within 3 m of him: stage 40, 100 credits for Fallout 4's 100 caps, then stage 200,
   quest complete.

Every stage and a status line every 5 s go to `fo4sf_mission.0.log` (the Papyrus user log); `make_mission.py log`
summarises it (exit 0 when stage 200 was reached).

## Stand-ins and gaps (stated, not hidden)

- No dialogue, voice or scenes: "talk" is activation or proximity. Dialogue is the next step (DialogueConcordArea).
- Preston and the raiders wear Starfield Spacer looks; Preston carries the calm probe's weapon.
- The fight takes place in the street outside the museum; the museum interior, Preston's door, the power armor, the
  minigun, the deathclaw and the waves are left out (B4 spike's cut list).
- **Unresolved:** whether the engine fills the alias and shows the markers from these records; whether persistent
  actors added to the core's persistent cell by a later plugin load there; the quest flags (StartGameEnabled,
  RunOnce, DisplaysInHud) were chosen, not copied from a vanilla quest.

## Commands (on the PC)

```powershell
& $py scripts\mission\make_mission.py stage --out D:\Modding\staging\mission_wfc1 --fo4 $f4\Fallout4.esm `
      --core <core staging>\FO4TerrainCore.esm --raider $sf\Data\FO4ActorRaider.esm
& $py scripts\game\exp_install.py install --exp-dir D:\Modding\staging\mission_wfc1 --starfield $sf --plugins FO4SFMission.esm --pack
& $py scripts\mission\make_mission.py log
```
