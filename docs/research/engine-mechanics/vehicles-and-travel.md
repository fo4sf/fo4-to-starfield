# Vehicles and travel (FO4 CE1 vs Starfield CE2)

Part of the engine-mechanics reference ([index](README.md)). Author: Claude-cloud, 2026-10-19. Labels: verified /
supported hypothesis / unresolved. "xEdit" = TES5Edit dev-4.1.6 `wbDefinitionsFO4.pas` / `wbDefinitionsSF1.pas`;
condition indices from the extracted tables `ctda_FO4.txt` / `ctda_SF1.txt` of the same files.

**Read first:** [../next-phase/world-maps-lod-fasttravel.md](../next-phase/world-maps-lod-fasttravel.md) section 5
(fast travel and travel between worlds: where the project is, the merged-position problem, the recommendation) and
[world-cells-navigation.md](world-cells-navigation.md) (map markers, WRLD/CELL layout). This file adds the vehicle
and travel-rule mechanics. Elevators are in [../next-phase/doors-activators-workshops.md](../next-phase/doors-activators-workshops.md)
sections 2.2 and 3.2.

## In short
- FO4 has no land vehicles. Its one vehicle is the **vertibird**, a flying actor the player rides in a seat, called
  with a Brotherhood signal grenade and flown by script (**verified** for the actor-and-seat model; the rest
  **supported hypothesis**). DLC worlds are reached by scripted travel (boat, monorail).
- FO4 fast travel: Pip-Boy map, any discovered marker with "Can Travel To" in the current world; blocked when
  over-encumbered and in Survival difficulty (**verified**), and near enemies or in combat (**supported hypothesis**).
- Starfield: on-planet fast travel only within the current landing, plus star map and ship travel between landings
  and planets; the REV-8 land buggy (August 2024 update) is a vehicle parked by the ship (**verified** as described).
  Its record side is a base-form component `BGSVehicleConfig`, not a vehicle record type (**verified**, xEdit).
- Verdict: marker fast travel **carries** (same marker flags, same condition functions); vertibird **rebuilt** as a
  scripted ride, first as fade + MoveTo; Starfield ship travel and the REV-8 **fenced out**; travel between the
  Commonwealth, Far Harbor and Nuka-World is **scripted** door/activator travel on one planet.

## How Fallout 4 does it

### Vertibirds
| Piece | Detail | Label |
|---|---|---|
| Actor model | the vertibird is an actor with seats; `Actor.IsSeatOccupied(Keyword apKeyword)`, falloutck's example is `Vertibird.IsSeatOccupied(pilotSeatKeyword)` | verified (falloutck) |
| Flying race | RACE flag `Flies` (0x80), `Flight Radius`, flags 2 `Flight - Defer Kill`, `Flight - Allow Procedural Crash Land`; MOVT `FLMV` fly defaults; combat style `CSFL` Flight block | verified (xEdit 11090, 11131, 11148-11150, 11263, 6289) |
| Flight control | `Actor.SetAllowFlying(abAllowed, abAllowCrash, abAllowSearch)`; conditions `GetIsFlying` 594, `GetFlyingState` 633, `IsAllowedToFly` 698, `CanFlyHere` 735 | verified (falloutck; ctda_FO4) |
| Riding | `IsRidingMount` 327, `IsSeatOccupied` 783 (conditions); event `OnPlayerEnterVertibird(Actor, ObjectReference akVertibird)`; there is no matching exit event | verified (ctda_FO4; event signature in a Nexus thread and in [papyrus-and-script-extenders.md](papyrus-and-script-extenders.md)); no exit event: supported |
| Door gunner | `VertibirdTurretScript` (state `TurretActive`, function `ExitTurret`); a `VertibirdMenu` UI | supported hypothesis (Nexus thread) |
| Calling one | a Brotherhood signal grenade item summons a vertibird after the Brotherhood questline; the ride flies to a chosen map marker | supported hypothesis (general game knowledge, not read from files) |

### Travel between worlds
- Far Harbor: boat trip from the Commonwealth to the island's own WRLD; Nuka-World: Nuka-Express monorail from a
  transit station in the Commonwealth (**verified** monorail, Wikipedia; Transit Center location **supported**, world
  maps note section 1). Both are scripted load transitions, not map fast travel between worldspaces.

### Fast travel rules
| Rule | Mechanism | Label |
|---|---|---|
| Destination | discovered map marker REFR with FNAM flag "Can Travel To" (0x02); flags Visible, "Show All" Hidden, Use Location Name; TNAM type 0-80 | verified (xEdit 11715-11800) |
| Script | `ObjectReference.AddToMap(abAllowFastTravel)`, `Game.FastTravel` | verified names (falloutck; papyrus note); a global toggle `Game.EnableFastTravel` is a supported hypothesis (Skyrim-era name, not checked on falloutck) |
| No travel from here | WRLD DATA flag 1 "Can't Fast Travel"; CELL DATA flag 2 "Can't Travel From Here", flag 13 "Player Followers Can't Travel Here" | verified (xEdit 13158, 5970-5981) |
| Over-encumbered | cannot fast travel; condition `IsOverEncumbered` 769; perk entry 131 "Set Run While Over Encumbered" (Strong Back runs, and in non-Survival allows fast travel) | verified block (fandom Encumbered); Strong Back detail supported |
| Combat / enemies near | blocked | supported hypothesis |
| Survival difficulty | fast travel disabled (plus bed-only saving) | verified (Fextralife Survival page) |
| Followers | arrive with the player unless the cell forbids it | supported hypothesis |

## How Starfield does it

### Land vehicle (REV-8)
| Piece | Detail | Label |
|---|---|---|
| Availability | added in the 20 August 2024 update; bought from a Ship Services Technician (25,000 credits); appears next to the landed ship | verified as described (Dexerto, starfieldwiki Rev-8) |
| Record side | no vehicle record signature in xEdit. The config is a base-form component `BGSVehicleConfig`: `VCSB` suspension bone modifiers (BMOD), `VCCD` vehicle config data (suspension and wheel node names, chassis mass, torque, inertia, friction ...), `VWWD` Wwise sounds (motor, tyres, headlights, horn), `VMRT` material audio table. A `BGSVehicleManagement` component name also exists | verified (wbDefinitionsSF1.pas 6031-6032, 6259-6530) |
| Which base form carries it | **unresolved** (the 300-record samples in docs/measurements/sf_esm.json do not include `VCCD`) | unresolved |
| Conditions | `IsInVehicle` 965, `AreVehiclesUnlocked` 966; FO4's `IsRidingMount`, `IsSeatOccupied`, flight functions all still present | verified (ctda_SF1) |
| Animation | subgraph actions "Vehicle Passenger Enter Vehicle", "... Engage Boost", "... Kill With Collision" and others | verified (xEdit 4626-4640, 11505-11515) |
| Papyrus | vehicle functions on Actor/ObjectReference: **unresolved** (not checked in ContentResources.zip) | unresolved |

### Fast travel and ships
- On-planet fast travel goes to discovered markers of the current landing; between landings and planets the player
  uses the star map and ship (grav jump) (**verified** as described, world maps note section 5).
- Marker FNAM flags keep FO4's four (Visible, Can Travel To, "Show All" Hidden, Use Location Name) and add Visible on
  Star Map, Discovered, Requires Scanning, Allow Grav Jump, Suppress Discovery, Use Accurate Z-Height, Limit Map
  Visibility To Compass Range, Must Cruise to First (**verified**, wbDefinitionsSF1.pas 8862-8877).
- WRLD flag 1 is "Can't Fast Travel From Here"; CELL flags 2 and 13 as FO4 (**verified**, xEdit 18996, 10610-10620).
- Condition functions for ship travel are new (`IsPlayerSpaceFarTravelling` 886 and siblings, `IsInSpaceship` 824,
  `CurrentShipLanded` 830) (**verified**, ctda_SF1).
- `TRAV` in Starfield is **Traversal** (jump up/down navigation pieces), not travel (**verified**, xEdit `wbRecord(TRAV`).
  A package-group enum lists `TravelBetweenLandings` (xEdit marks those names as guesses: **supported hypothesis**).
- Over-encumbered blocks fast travel in Starfield too (**supported hypothesis**; `IsOverEncumbered` 769 exists,
  **verified**). Interior fast-travel targets need an exterior MapMarker linked to an interior XMarker (community mod
  12719, **supported**, world maps note).

## Mapping for the port
| FO4 piece | Starfield counterpart | Verdict | Notes |
|---|---|---|---|
| Map marker REFR (XMRK/FNAM/TNAM) | MapMarker REFR + LCTN `LCSR` row | translate | FO4 layout is in xEdit (above); marker position must be the merged one (world maps note section 3) |
| "Can Travel To", AddToMap | same flag, same function | data copy | |
| WRLD/CELL no-travel flags | same bits | data copy | rename only |
| Over-encumbered rule | same engine rule (supported) | carries | check in game |
| Survival no-fast-travel | none native | script (our survival layer) | a global fast-travel toggle (name to check in Starfield sources) |
| Vertibird actor + race | flying RACE fields and fly conditions exist | rebuild | v0: activator + fade + MoveTo to a landing marker; v1: a flying actor with seats if CE2 seats work |
| Vertibird signal grenade | none | script | item + quest that spawns/moves the vertibird |
| Boat / monorail to DLC worlds | none (ship travel fenced out) | scripted load door/activator | same as FO4, see below |
| REV-8, ships, grav jump, star map | not used | **fence out** | hide Ship Services vendors; never grant vehicles |
| Elevators | Starfield load-elevator pattern | see doors note | [../next-phase/doors-activators-workshops.md](../next-phase/doors-activators-workshops.md) |

## One planet: Commonwealth, Far Harbor and Nuka-World
- Settled: the three worlds share one Earth-like planet. Planned layout: one overlay landing per world on the host
  planet, separated by more than one landing (world maps note section 2, option A).
- Consequence: Starfield's surface fast travel works inside a landing. Moving between landings is natively a ship or
  grav-jump path, which the port fences out. Playtest row 7 (fast travel to the Frontier hung) is consistent with
  that path being touched (**supported**, world maps note).
- So travel between worlds stays FO4-shaped: the boat and the monorail are activators that run a scripted MoveTo to a
  COC-style arrival in the other landing (world maps note recommendation). Whether the surface map can list and
  fast travel to markers of a second landing on the same planet without the ship is **unresolved**; until a test
  shows it, mark other-world markers without "Can Travel To" or route them through the travel activator.
- Arrival must use loaded temporary refs or merged positions: MoveTo onto a persistent ref lands at the unmerged spot
  today (**verified**, JOURNAL 16 Oct per the world maps note).

## What must be rebuilt, and what needs SFSE or the Creation Kit
- Rebuild in Papyrus: vertibird ride, signal grenade, boat and monorail trips, survival fast-travel lock.
- Fence out: ship, star map and REV-8 entry points (vendors, quests, `AreVehiclesUnlocked`).
- CK: none beyond the overlay path. SFSE: only if hiding the star map or ship UI needs it (**unresolved**).

## Port status and links
- Phase A exit criterion "fast travel to Red Rocket's marker" is not met; markers are enabled (#356) but not yet at
  merged positions ([../next-phase/world-maps-lod-fasttravel.md](../next-phase/world-maps-lod-fasttravel.md)
  sections 3 and 5). Working arrivals: `coc`, door MoveTo onto loaded temporary refs, hops of 200 m or less.
- docs/terrain/interior-backlog.md lists two Brotherhood vertibird doors leading back to the Commonwealth.

## Open questions and cheap checks
- Starfield esm: which record types carry `VCCD` (a full subrecord scan with the existing walker). Tells us the REV-8
  base form.
- ContentResources.zip: grep `.psc` for `Vehicle`, `IsSeatOccupied`, `SetAllowFlying`, `OnPlayerEnterVertibird`.
- FO4 xEdit: the vertibird NPC_ and RACE (flight fields), the signal grenade item and its script.
- In game, read-only: with two terrain-only landings, open the surface map in one; are the other's markers listed?
- In game: over-encumbered fast travel attempt in our world (expect the engine block).

## Sources
- xEdit: https://github.com/TES5Edit/TES5Edit (local copies of wbDefinitionsFO4.pas, wbDefinitionsSF1.pas)
- https://falloutck.uesp.net/wiki/IsSeatOccupied_-_Actor ; https://falloutck.uesp.net/wiki/SetAllowFlying_-_Actor ;
  https://falloutck.uesp.net/wiki/AddToMap_-_ObjectReference
- https://forums.nexusmods.com/topic/12793296-detecting-when-the-player-exit-vertibird
- https://fallout.fandom.com/wiki/Encumbered ; https://fallout4.wiki.fextralife.com/Survival
- https://en.wikipedia.org/wiki/Fallout_4:_Nuka-World
- https://www.dexerto.com/starfield/how-to-get-rev-8-in-starfield-2911588/ ; https://starfieldwiki.net/wiki/Starfield:Rev-8
- https://www.nexusmods.com/starfield/mods/12719 (interior fast travel, via the world maps note)
