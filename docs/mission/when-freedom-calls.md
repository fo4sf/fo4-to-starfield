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
| ACHR 0x803 on | up to 8 raiders (FO4_LvlRaider) at Fallout 4's own Concord positions: the enabled placed raiders within 120 m of that door, without the dead-body loot placements (Loot_Corpse*, Starts Dead) |
| NPC_ `FO4_Codsworth` 0x810 | Codsworth (ROADMAP B2 stretch): a copy of Starfield's `OutpostRobotMiniBotA_Garden` (04297C, "Garden Mini Bot", MiniBotARace, a hovering robot) under his Fallout 4 name, Essential, Unique, without its factions and scripts; `write --codsworth-body EDID` picks another body, `--no-codsworth` leaves him out |
| ACHR 0x811 | Codsworth at Fallout 4's own Sanctuary placement, ACHR 01CA7D of NPC_ 0179FF: (-1146.709, 1293.837, 111.734) m, rot z 2.356 |
| WRLD + CELL override | the core world `FO4Core_Commonwealth` and its persistent cell, holding only the ACHRs above |

Positions are Fallout 4's divided by 70, the core's frame (make_core64c.py). Because the plugin copies the core's world
record, it is rebuilt whenever FO4TerrainCore.esm changes; plan.json records the masters' hashes.

## What the script does (scripts/mission/FO4SF_Min00Quest.psc)

A one-second check replaces Fallout 4's triggers, scenes and fragments:

1. Stage 10 at start: "Find the Last Minutemen" (marker on Preston).
2. The fight counts as started as soon as any raider fights or is dead, whoever started it (a quest that starts or
   reloads mid-fight still advances). A living raider within 60 m of the player that is not fighting is put into combat with the player (Fallout 4's
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

## In game 18 Oct: the actors were not in the world the player walks in (fixed by Relocate)

**Verified** (the PC's read of `fo4sf_mission.0.log`, v5 + the Codsworth set, save fo4sf_test_1d4591b6_s100): the
quest started (`init raiders=5`, stage 10), but every status line read `nearest_raider` and `preston` = float max
(3.4e38), also at 13:25:38 with the player standing on Preston's merged spot (-2011.1, -1697.2): local (-811.1, 1002.5)
+ the merge offset (-1200, -2700). So persistent references added to the core's persistent cell by a later plugin
exist at their LOCAL position in the base world, as probe (a) found for the core's own anchor (scripted-doors.md); the
"unresolved" item above is answered "no". Fix: the script's `Relocate` moves Preston, the raiders and Codsworth once,
when the player is within 3 km of Preston's merged spot and still cannot reach him: each actor's local position +
`MergeOffsetX/Y` (vmad_patch.MERGE_MEASURED, a test pins them equal), z kept, by `MoveTo(player, dx, dy, dz)`. Log lines
`moved <who> to ... target ...` and `relocated preston=<m>`. **Unresolved** until the next run: that MoveTo with an
offset lands an actor in the merged world's cell at that spot.

## Codsworth (2026-10-18)

The owner asked for a Codsworth test. A Mr. Handy has no Starfield skeleton (ROADMAP B2), so the first one is a
Starfield robot body under his name at his own spot. **Verified** by `dotnet/Mission npcs` on the PC (read only):
Fallout4.esm NPC_ 0179FF `Codsworth` (HandyRace) has one placed ACHR, 01CA7D, in the Commonwealth's persistent cell
at the core-frame position above (about 30 m from the walk route's Sanctuary goal); Starfield.esm has no Mr. Handy
(the robot races are ModelARace, ModelSRace and MiniBotARace). The Garden Mini Bot was chosen as the closest look (a
small hovering robot, not a companion with quests like Vasco). **Unresolved:** whether the bot's AI packages and
template run without its outpost, and how he behaves (sandbox, hover, idle). No dialogue or voice yet (WP-15).
Check in game: travel to Sanctuary; a robot named Codsworth hovers near his house, does not attack, and stays.

## Commands (on the PC)

`exp_install.py` holds one experiment at a time, so the mission goes in with the core set: `fold` copies the core's
experiment folder and adds the plugin and the script; `verify` (run by `fold`, and again before install) refuses a
plugin, script, core or raider plugin whose SHA-256 differs from the stage's plan.json. A stage or fold never
overwrites an existing folder; a failed one publishes nothing.

```powershell
& $py scripts\mission\make_mission.py stage --out D:\Modding\staging\mission_wfcN --fo4 $f4\Fallout4.esm `
      --core <core experiment dir>\FO4TerrainCore.esm --raider $sf\Data\FO4ActorRaider.esm
& $py scripts\mission\make_mission.py fold --mission D:\Modding\staging\mission_wfcN --core-dir <core experiment dir> `
      --out <core experiment dir>_mission --raider $sf\Data\FO4ActorRaider.esm
& $py scripts\mission\make_mission.py verify --exp-dir <core experiment dir>_mission --plan D:\Modding\staging\mission_wfcN\plan.json --raider $sf\Data\FO4ActorRaider.esm
# the swap, on the owner's words: the core set's usual install with --exp-dir <core experiment dir>_mission and
# FO4SFMission.esm appended to its --plugins list (--pack), then exp_install.py order
& $py scripts\mission\make_mission.py log
```
