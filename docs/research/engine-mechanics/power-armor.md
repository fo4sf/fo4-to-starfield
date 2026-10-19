# Power armor (FO4 CE1 vs Starfield CE2)

Part of the engine-mechanics reference ([index](README.md)). Author: Claude-cloud, 2026-10-19. Labels: verified /
supported hypothesis / unresolved.

## In short
- FO4: a power armor suit in the world is a FURN with the record flag "Power Armor" (bit 25). Activating it plays an
  enter animation, the actor switches to a power armor skeleton/behavior (via race subgraph data and keywords), the
  frame and pieces become worn ARMO (pieces upgraded by OMOD), a fusion core drains while worn, a dedicated HUD and
  helmet image space run, and the PA station is a FURN with WBDT bench type 8. Papyrus: `Actor.SwitchToPowerArmor`,
  `Actor.IsInPowerArmor`. **verified** (xEdit; falloutck).
- Starfield: no power armor. The FURN "Power Armor" record flag is gone (bit 25 is now "Obstacle"), NPC_ PFRN "Power
  Armor Stand" is commented out as absent, but WBDT bench type 8 "Power Armor" and the default object "ImageSpaceModifier
  for Pipboy menu in Power armor" survive in the format as vestiges. **verified** (xEdit). The engine code behind them
  is **unresolved** (assume gone).
- Verdict: **rebuild**. Pieces and frames carry as ARMO/ARMA/OMOD data (translate); the enter/exit, skeleton swap,
  movement feel, fusion core drain, HUD and PA station are a new system: Papyrus + a furniture with our own enter
  animation first, SFSE for HUD and anything that swaps the behavior graph at runtime.
- Phase fit: power armor first appears in MQ102 (Concord museum roof). The current conversion keeps PA frames and
  stations as statics (docs/terrain/stations.md); B4 dropped the PA part of the mission. A rebuild is "Fallout systems"
  phase work, not phase 1.

## How Fallout 4 does it
| Piece | Records / fields | Label |
|---|---|---|
| Suit in the world | FURN, record flag 25 "Power Armor"; keywords; MNAM furniture markers | verified (xEdit) |
| PA station | FURN WBDT Bench Type 8 "Power Armor"; vanilla WorkbenchPowerArmor 157FEB, WorkbenchPowerArmorSmall 13BD08 | verified (xEdit; docs/terrain/stations.md) |
| NPC default suit | NPC_ PFRN "Power Armor Stand" [FURN] | verified (xEdit) |
| Frame | worn ARMO with keyword `isPowerArmorFrame` (falloutck suggests `WornHasKeyword(isPowerArmorFrame)` for NPCs) | verified (falloutck note) |
| Pieces | ARMO + ARMA + MISC + OMOD per piece; MSWP paint swaps; six slots (helmet, torso, 2 arms, 2 legs) | records: supported hypothesis (Nexus forum thread); slots: Fallout wiki |
| PA race / skeleton | ARMA models attached to a "PA race"; RACE "Subgraph Data" (SAKD actor keywords, SGNM behavior graph, SAPT animation paths, STKD target keywords) selects graphs by keyword | subgraph fields verified (xEdit, falloutck Subgraphs); PA race editor id unresolved |
| Enter / exit | furniture activation; `OnSit` fires three times (core insert, enter, exit); `SwitchToPowerArmor(ObjectReference aArmorFurniture)` snaps in, `None` exits; the left suit is `GetLinkedRef(LinkPowerArmorKeyword)` | verified (falloutck) |
| Fusion core | an ammo-like item inserted into the suit; drains over time and faster with AP actions; empty: slow walk, no VATS; NPCs and companions do not drain cores | behaviour supported hypothesis (Fallout wiki); record type (AMMO?) unresolved |
| Stats | Strength boost up to 14 with mods; each piece 5% damage reduction and 14% rad reduction (wiki values); no fall damage, landing damage around the player | supported hypothesis (Fallout wiki) |
| HUD | dedicated PA HUD and helmet image space; default object IMPP "ImageSpaceModifier for Pipboy menu in Power armor" | IMPP verified (xEdit); HUD SWF names unresolved |
| Game stat | "Fusion Cores Consumed" | verified (xEdit) |
| Vanilla example | MQ102 museum suit (power armor 000370E3 per B4 spike), Danse never leaves his suit, raiders with `usePowerArmorFrameRaider` keyword | verified (docs/spikes/B4-mission-anatomy.md; docs/actors/raider-conversion.md) |

## How Starfield does it
- No power armor, no mechs as a player system. Mechs exist only as static/destroyed set dressing in vanilla; a
  pilotable-mech mod by Korodic was shown in 2023 without technical detail. **supported hypothesis** (PCGamesN).
- "Power armor" mods for Starfield found so far are spacesuits styled after FO4 PA (e.g. Nexus SF 6038 "Fallout 42
  Power Armor": a helmet + spacesuit pair). **verified** (mod page). No furniture-based PA precedent found:
  **unresolved**, recheck.
- Format vestiges: WBDT bench type 8 "Power Armor" still in the enum; DFOB/DOBJ IMPP still listed; FURN flag 25 is
  now "Obstacle"; NPC_ PFRN commented out ("not in Starfield"). **verified** (xEdit).
- Useful native parts: FURN with furniture markers and enter/exit animations (doors and benches already use them);
  RACE subgraph data (same SAKD/SGNM/SAPT layout, verified xEdit); Boostpack archetype (48) for jump assists; ARMO
  slots for the suit; spacesuit/helmet logic (helmet toggling, own HUD overlay of O2/CO2).

## Mapping for the port
| FO4 piece | Starfield counterpart | Verdict | Notes |
|---|---|---|---|
| PA frame/suit FURN (flag 25) | FURN without PA flag | rebuild | our FURN + activator script; today a static |
| PA station FURN (WBDT 8) | no working bench type 8 (2B6A64 WorkbenchRobotStation is DONOTUSE) | rebuild / interim static | modding at a regular SF armor workbench (07) is a fallback |
| PA pieces ARMO/ARMA/OMOD/MSWP | ARMO/ARMA/OMOD; MSWP gone (SF has no MSWP) | translate | paint swaps need SF material swap equivalent (see S3-materials spike) |
| Frame ARMO + keyword | ARMO | translate | keep `isPowerArmorFrame` as our own keyword |
| PA skeleton / race / graphs | SF human graph only | rebuild | phase rule: SF animations first; FO4 PA clips later |
| `SwitchToPowerArmor`, `IsInPowerArmor` | not listed on starfieldwiki's Actor page | script shim | presence in SF Actor.psc unresolved |
| `LinkPowerArmorKeyword` linked ref | REFR linked refs | data copy | our keyword |
| Fusion core drain | none | rebuild (script + AV) | |
| PA HUD, helmet IMAD | SF helmet overlay | rebuild (Scaleform; SFSE likely) | |
| NPC_ PFRN | none | rebuild | script spawns the suit on load |
| Raider `usePowerArmorFrameRaider` | none | drop for now | as in raider-conversion.md |

## What must be rebuilt, and what needs SFSE or the Creation Kit
A staged rebuild, smallest proof first:
1. **Static suit with an activator** (CK2/plugin only): the converted FO4 PA mesh as a FURN or ACTI; activating it
   equips the frame + pieces as ARMO on the human player and disables the world ref. No skeleton swap: the suit is
   worn like heavy armor. Proves data conversion.
2. **Enter/exit feel**: a furniture enter animation (SF's own first, FO4's clip later), camera change, movement speed
   and jump/fall changes via AV modifiers and spells (Strength boost, carry weight, fall damage immunity through an MGEF).
3. **Fusion core**: an AV + script timer, cores as items; empty core = speed penalty spell.
4. **HUD**: SFSE menu or Scaleform overlay (same decision as the Pip-Boy, ../next-phase/animations-ui-and-start.md).
5. **True PA skeleton**: a race or subgraph swap at runtime. Starfield has no `SwitchToPowerArmor`-like native that we
   know of; a race switch via Papyrus `SetRace` (presence in SF unresolved) or an SFSE plugin is required, plus a
   converted PA skeleton and behavior graph (big asset work; see ../next-phase/animations-ui-and-start.md).
6. **PA station**: furniture with an OMOD-modding menu; SF's armor workbench menu may be reusable if PA pieces are
   ordinary ARMO with OMOD slots (supported hypothesis).

## Port status and links
- docs/terrain/stations.md: 75 PA stations and the frames stay statics ("Starfield has no bench type 8"). **verified**.
- docs/ai/research-log.md: power armor on the museum roof is out of the current pass (skinned rest pose / furniture
  class). docs/ROADMAP.md lists "Elevator and power armor rest poses" as known and queued.
- docs/owner/playtest-issues.md #15: museum roof power armor seen in playtest.
- docs/spikes/B4-mission-anatomy.md: MQ102's PA (000370E3) and MQ102 stages 47 ("already in power armor"), 90 (get a
  fusion core) mark where PA matters in the first quest line.
- Related: [vats.md](vats.md), [health-damage-effects.md](health-damage-effects.md),
  [../next-phase/doors-activators-workshops.md](../next-phase/doors-activators-workshops.md) (furniture, benches),
  [../next-phase/animations-ui-and-start.md](../next-phase/animations-ui-and-start.md).

## Open questions and cheap checks
- xEdit: Fallout4.esm RACE list for a power armor race (editor id containing "PowerArmor") and its SGNM/SAPT paths.
- xEdit: the FURN of a vanilla PA frame (flag 25 set, keywords, MNAM markers, VMAD script name).
- xEdit: the fusion core item record type and editor id (AMMO or MISC), and keywords on PA ARMO (`isPowerArmorFrame`,
  piece keywords).
- FO4 CK Base.zip: list scripts with "PowerArmor" in the name (furniture, core, HUD helpers).
- ContentResources.zip: `grep -n "PowerArmor\|SetRace" Actor.psc ObjectReference.psc` (vestigial natives?).
- Starfield Interface.ba2: any power armor SWF left (`grep -i power` over the 250 SWF names).
- Nexus: recheck for a Starfield furniture-based exosuit or mech mod with SFSE source.

## Sources
- xEdit definitions, TES5Edit dev-4.1.6: [wbDefinitionsFO4.pas](https://github.com/TES5Edit/TES5Edit/blob/dev-4.1.6/Core/wbDefinitionsFO4.pas),
  [wbDefinitionsSF1.pas](https://github.com/TES5Edit/TES5Edit/blob/dev-4.1.6/Core/wbDefinitionsSF1.pas) (FURN flags and
  WBDT, NPC_ PFRN, RACE subgraph data, DOBJ IMPP, misc stats)
- [SwitchToPowerArmor - Actor](https://falloutck.uesp.net/wiki/SwitchToPowerArmor_-_Actor),
  [IsInPowerArmor - Actor](https://falloutck.uesp.net/wiki/IsInPowerArmor_-_Actor),
  [OnSit - Actor](https://falloutck.uesp.net/wiki/OnSit_-_Actor), [Subgraphs](https://falloutck.uesp.net/wiki/Subgraphs) (falloutck)
- [Power armor (Fallout 4), Fallout wiki](https://fallout.fandom.com/wiki/Power_armor_(Fallout_4))
- [Implementing custom power armour (Nexus forums)](https://forums.nexusmods.com/topic/6308206-implementing-custom-power-armour)
- [Starfield Mod:Script-Actor (starfieldwiki)](https://dev.starfieldwiki.net/wiki/Starfield_Mod:Script-Actor)
- [Fallout 42 Power Armor (Nexus SF 6038)](https://www.nexusmods.com/starfield/mods/6038);
  [Starfield mech mod (PCGamesN)](https://www.pcgamesn.com/starfield/mech-mod)
- Project: docs/terrain/stations.md, docs/spikes/B4-mission-anatomy.md, docs/actors/raider-conversion.md,
  docs/ai/research-log.md, docs/ROADMAP.md
