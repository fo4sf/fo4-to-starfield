# DLC mechanics (FO4 CE1 vs Starfield CE2)

Part of the engine-mechanics reference ([index](README.md)). Author: Claude-cloud, 2026-10-19. Labels: verified /
supported hypothesis / unresolved. "xEdit" = TES5Edit dev-4.1.6 `wbDefinitionsFO4.pas` / `wbDefinitionsSF1.pas`.

**Scope and limit.** One section per FO4 add-on: what it adds as a mechanism, the records and scripts involved, the
Starfield counterpart and a verdict. **The project has not measured any DLC plugin yet**: docs/measurements covers
Fallout4.esm only, and the owner's PC has DLCRobot + DLCworkshop01 installed, not DLCCoast, DLCworkshop02,
DLCworkshop03, DLCNukaWorld (**verified**, [../next-phase/world-maps-lod-fasttravel.md](../next-phase/world-maps-lod-fasttravel.md)
facts table, PR #371 E1). So every per-DLC record count and editor id below is from xEdit or public wikis, not from
the files. Build-mode and settlement rules are in [workshop-and-settlements.md](workshop-and-settlements.md); world
layout in [world-cells-navigation.md](world-cells-navigation.md); robots as actors in [actors-and-npcs.md](actors-and-npcs.md).

## In short
- Six add-ons, seven official plugins: `DLCRobot.esm`, `DLCworkshop01.esm`, `DLCCoast.esm`, `DLCworkshop02.esm`,
  `DLCworkshop03.esm`, `DLCNukaWorld.esm`, plus `DLCUltraHighResolution.esm` (textures) (**verified**, xEdit
  `wbOfficialDLC`, wbDefinitionsFO4.pas 13351-13358).
- Almost no DLC mechanic is a new record type. They are data on existing records (NPC_, OMOD, FURN, COBJ, WRLD, QUST)
  plus a large Papyrus layer. Only a few native hooks are DLC specific: `IsInRobotWorkbench` (817), FURN bench type 9
  "Robot Mod", REFR power-grid subrecords, map marker types 65-80 (**verified**, xEdit).
- Starfield has counterparts for little: a bench enum that still lists "Robot Mod", outposts with power, a FOGV
  record. Verdict overall: **world and items carry as data; DLC rules are rebuilt as our own Papyrus**, after the
  base game's settlement layer exists. Nothing here blocks the current phases.
- DLC quest type enum in FO4 QUST: `DLC01`..`DLC07` (**verified**, xEdit 10722-10728). Editor id prefixes seen in
  public wikis: DLC01 Automatron, DLC02 Wasteland Workshop, DLC03 Far Harbor, DLC04 Nuka-World, DLC05 Contraptions,
  DLC06 Vault-Tec Workshop (**supported hypothesis**: DLC02 and DLC06 seen on fandom pages, the others not checked).

## Automatron (DLCRobot.esm, released 2016-03-22)
**FO4:** a robot workbench FURN with `WBDT` bench type 9 "Robot Mod" (**verified**, xEdit 6896). Robot companions are
NPC_ records whose parts are object mods: NPC_ carries an object template and attach parent slots (APPR), so OMODs
apply to the actor much as to a weapon (**verified** fields; the run-time path is a **supported hypothesis**, see
[actors-and-npcs.md](actors-and-npcs.md)). Condition `IsInRobotWorkbench` (index 817) gates bench dialogue and
packages (**verified**, ctda_FO4). Robot races and 421 extra `.hkx` clips ship in DLCRobot (**verified**,
[animations.md](animations.md)). Stats "Robots Improved", "Robots Disabled" exist (**verified**, xEdit 5075-5077).
Quests (Mechanist, robot raids) are ordinary QUST + scripts. The Mechanist's Lair is an interior
(`DLC01Lair01` [CELL:010008A3], **verified**, xEdit comment 6086).

**Starfield:** bench type 9 "Robot Mod" survives in the enum (with new 10 Extractor, 11 Research) (**verified**,
wbDefinitionsSF1.pas 12183-12196), but the only station found is `WorkbenchRobotStation` 2B6A64 marked DONOTUSE
(**verified**, [power-armor.md](power-armor.md)). Index 817 is reused for `IsDockedWith` (ships) (**verified**).
Starfield's robots are NPC_ with their own races; its object-template path exists on NPC_ (**supported hypothesis**).

**Verdict:** rebuild. Robot NPC_, OMOD, COBJ translate as data; the bench needs either a native type-9 menu test
(unresolved whether CE2 still opens it) or a scripted menu; condition 817 must be remapped by name, never by number.

## Wasteland Workshop (DLCworkshop01.esm, 2016-04-12)
**FO4:** cages that catch creatures or people (bait in the cage, a creature spawns on a timer, **supported
hypothesis**), a Beta Wave Emitter that makes caught animals friendly, arena pieces for staged fights, plus decor
(neon letters, concrete shipments `DLC02shipment...`) (**verified** as described, fandom Wasteland Workshop page). Build
items need perks (Animal Friend, Wasteland Whisperer, Science!) (**verified** as described there). Mechanically:
COBJ build recipes, ACTI/FURN with Papyrus (cage, emitter, arena), leveled actors, faction changes for taming.
No new map marker types (**verified**, xEdit comment "No new map markers for Automatron or Workshop").

**Starfield:** no cage or taming system. Outpost build mode places objects; creature faction changes and leveled
spawns exist in both engines.

**Verdict:** data for decor; cages, taming and arena are **script rebuilds** on top of our settlement layer. Low
priority.

## Far Harbor (DLCCoast.esm, 2016-05-19)
| Mechanism | FO4 | Starfield | Verdict |
|---|---|---|---|
| Island worldspace | own exterior WRLD; reached by boat from the Commonwealth (scripted travel) | an overlay landing on our planet ([../next-phase/world-maps-lod-fasttravel.md](../next-phase/world-maps-lod-fasttravel.md) section 2, option A) | rebuild as a second overlay; size in cells **unresolved** |
| Fog | radioactive weather and lighting; fog colour and distances are WTHR / lighting fields (**verified** fields exist, xEdit 5997-6031, [weather-time-climate.md](weather-time-climate.md)); radiation by hazard or script (**unresolved**) | Starfield adds FOGV "Fog Volume" (opaque REFL blob) and WTHS weather settings (**verified**, weather note) | translate fog colours into our weather; radiation as our own hazard/MGEF |
| Fog condensers | workshop object that clears fog in a small area and produces Condensed Fog (form xx03EF36) (**verified** as described, fallout.wiki); how the clearing is done (script vs volume) **unresolved** | none | rebuild (script + local weather or image space) |
| Acadia, Vim, factions | ordinary NPC_, FACT, QUST, vendors; Vim is a drink item with Nuka-like variants (**supported hypothesis**) | n/a | data plus dialogue path |
| DiMA memory puzzle | a five-level puzzle in DiMA's memories, entered at a terminal; first three levels needed, last two optional (**verified** as described, Twinfinite). That it reuses workshop build mode in puzzle cells is a **supported hypothesis** (community knowledge, not read from files) | none | rebuild or skip; depends on our build mode |
| Island settlements | normal workshops | outpost build mode | as base settlements |

## Contraptions Workshop (DLCworkshop02.esm, 2016-06-21)
**FO4:** conveyors, manufacturing machines (builders that turn components into items), sorters, logic gates,
switches, displays (**verified** that conveyors, builders and logic gates exist, fandom page; sorters and switches
**supported hypothesis**). Native support: REFR carries `XPLK` "Spline Connection" and a "Power Grid" (`XWPG` count,
`XWPN` node 1 / node 2 / line ref) (**verified**, xEdit 11836-11848). Whether logic signals and item movement are
native workshop power or Papyrus is **unresolved** (also open in [workshop-and-settlements.md](workshop-and-settlements.md)).
Conveyor item transport is likely Havok physics on dropped items (**supported hypothesis**).

**Starfield:** REFR keeps `XPLK` but renamed "Power Links" (ref + unknown enum), and has **no** `XWPG`/`XWPN`
(**verified**, wbDefinitionsSF1.pas 7053-7060). Outposts have power (perk entry "Mod Power Generated", **verified**,
xEdit) and cargo links that move resources between outposts (**supported hypothesis**). No logic gates or sorters.

**Verdict:** rebuild. Power wiring must be translated to Starfield power links (format test needed); manufacturing
and sorting as Papyrus; logic gates as Papyrus state. Late phase.

## Vault-Tec Workshop (DLCworkshop03.esm, 2016-07-26)
**FO4:** Vault 88 as a buildable settlement (interior cells under a Commonwealth entrance, **supported hypothesis**),
vault prefab pieces with built-in wiring and conduits, an Overseer's desk built once, quest-driven experiment objects
(`DLC06MQ01`..`DLC06MQ04`, `DLC06E01`..`DLC06E04`, `DLC06VaultTecPrototypes`), dweller idle lines from Fallout
Shelter (**verified** as described, fandom Vault-Tec Workshop page). xEdit's comment on the `XPLK` spline connection's
unknown field reads "always 00 00 00 00 so far in DLCWorkshop03.esm", so that plugin uses spline connections
(wires) (**verified** comment, xEdit 4597-4599 and 11836-11839). A dedicated dweller needs or happiness system beyond the base
settlement rules is **unresolved** (the wiki page describes none).

**Starfield:** outpost build mode works in exteriors; interior build areas are **unresolved** for CE2 (Starfield
builds ship interiors and outposts, not cave interiors, as far as checked).

**Verdict:** rebuild. Pieces and decor are data; interior build mode is a CE2 test; experiments are quest scripts.

## Nuka-World (DLCNukaWorld.esm, 2016-08-30)
| Mechanism | FO4 | Starfield | Verdict |
|---|---|---|---|
| Park worldspace(s) | own exterior world reached by the Nuka-Express monorail from the Commonwealth; six park zones (Nuka-Town, Kiddie Kingdom, Dry Rock Gulch, Safari Adventure, Galactic Zone, bottling plant) (**verified** as described, Wikipedia) | overlay landing on our planet | rebuild as overlay |
| Gauntlet | scripted trap course ending in a boss fight (Colter) (**verified** as described) | n/a | data + scripts (traps are ordinary hazards/activators) |
| Raider gangs | three gangs (Operators, Pack, Disciples) as factions with favour and rivalry handled by quest scripts (**supported hypothesis** for the script side) | Starfield factions/crime are fenced out | data (FACT) + rebuilt quest logic |
| Outposts and vassals | park zones and Commonwealth settlements given to gangs; map marker types 66 "Raider settlement", 67 "Vassal settlement", 68 "Potential Vassal settlement" (**verified**, xEdit TNAM enum); tribute and raids by script (**supported hypothesis**) | none | rebuild on our settlement layer |
| Nuka-Cola mixing station | crafting bench (COBJ recipes) for flavours; stat "Nuka Cola Flavors Created" (**verified**, xEdit 5059); bench type **unresolved** (Alchemy 5 likely) | Starfield benches: Alchemy covers cooking/industrial/pharma (**verified** enum comment) | data (COBJ + FURN), test bench type |
| Park map markers | types 69-80 (Bottling Plant, Galactic, HUB, Kiddie Kingdom, Monorail, Rides, Safari, Wild West, POI, Disciples, Operators, Pack) (**verified**, xEdit) | Starfield marker types differ | translate to our own marker icons |

## Mapping for the port
| FO4 piece | Starfield counterpart | Verdict | Notes |
|---|---|---|---|
| DLC plugins as masters | extra masters in our build | data | own FormID range each (E-own-ecosystem item 6) |
| FURN WBDT 9 robot bench | enum value present, no live station | test native, else scripted menu | |
| `IsInRobotWorkbench` 817 | 817 = `IsDockedWith` | remap by name, drop or shim | records-and-plugins.md |
| REFR power grid XWPG/XWPN | XPLK "Power Links" only | translate (test) | |
| Marker types 65-80 | own icons | translate | |
| DLC worlds (Far Harbor, Nuka-World) | overlay landings on one planet | rebuild | settled one-planet decision |
| Fog | weather fog fields, FOGV | translate + rebuild radiation | |
| DLC quests and gang/settlement rules | none | own Papyrus | after base game |

## What must be rebuilt, and what needs SFSE or the Creation Kit
- Rebuild in Papyrus: robot bench menu (if native fails), cages/taming/arena, fog condensers, memory puzzle,
  contraptions logic, vault experiments, gang favour and vassal tribute.
- CK: second and third overlay landings (one per DLC world) follow the core's path; LOD per DLC world (see the world
  maps note section 4).
- SFSE: none identified yet; a native robot bench menu might need it if CE2 removed the type-9 UI (**unresolved**).

## Port status and links
Nothing converted. Only synthetic tests name `DLCCoast.esm` ids (tests/test_make_core64c.py:498, per the world maps
note). Plan: [../next-phase/world-maps-lod-fasttravel.md](../next-phase/world-maps-lod-fasttravel.md) sections 1-2
(DLC census, overlays), [../next-phase/doors-activators-workshops.md](../next-phase/doors-activators-workshops.md)
(workshop hybrid). Travel between worlds: [vehicles-and-travel.md](vehicles-and-travel.md).

## Open questions and cheap checks
- Owner installs the four missing DLC; then the read-only DLC census (world maps note section 2): per esm record
  counts, WRLD bounds, marker counts, overrides of Fallout4.esm.
- xEdit: open one Automatron robot NPC_ and its object template; confirm OMODs on actors.
- xEdit: the fog condenser base (xx03EF36 in DLCCoast) and its script; tells script vs volume.
- xEdit: a Contraptions logic gate ACTI and its scripts; count REFRs with XWPN in DLCworkshop02.
- CE2 test: place a FURN with WBDT 9 in a test cell and activate it; does a menu open?
- Starfield source grep (ContentResources.zip): any script using power links (`XPLK`) from Papyrus.

## Sources
- xEdit: https://github.com/TES5Edit/TES5Edit (Core/wbDefinitionsFO4.pas, wbDefinitionsSF1.pas, local copy)
- https://en.wikipedia.org/wiki/Fallout_4 (add-on dates) ; https://en.wikipedia.org/wiki/Fallout_4:_Nuka-World
- https://fallout.fandom.com/wiki/Wasteland_Workshop ; https://fallout.fandom.com/wiki/Contraptions_Workshop ;
  https://fallout.fandom.com/wiki/Vault-Tec_Workshop
- https://fallout.wiki/wiki/Fog_Condenser ; https://dev.fallout.wiki/wiki/The_Fog
- https://twinfinite.net/news/fallout-4-far-harbor-psa-the-memory-puzzles-are-optional/
- Project: docs/measurements/fo4_esm.json, sibling files linked above, /mnt/project-files/research/next-phase/
