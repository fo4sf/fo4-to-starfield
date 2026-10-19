# Leveled lists, encounter zones and respawn (FO4 CE1 vs Starfield CE2)

Part of the engine-mechanics reference ([index](README.md)). Author: Claude-cloud, 2026-10-19. Labels: verified /
supported hypothesis / unresolved. "xEdit" = TES5Edit dev-4.1.6 `Core/wbDefinitionsFO4.pas` / `wbDefinitionsSF1.pas`.

## In short
- Leveled lists keep their shape in both engines (`LVLD` chance none, `LVLF` flags, `LLCT` count, entries of level +
  form + count, `COED` extra data, filter keyword chances, `LVLG` global) (**verified**, xEdit). Starfield widens `LVLF`
  to 16 bits and adds conditions on the list and on each entry. Verdict: **translate** (FO4 lists convert cleanly once
  their targets exist).
- FO4's ECZN encounter zone (276 records, FO4-only) holds owner, location, rank, min/max level and flags. Starfield
  has no ECZN; the same fields sit in LCTN `DATA` as "Encounter Leveling Data" with an extra flag "Use Parent's Locked
  Level", and the REFR/ACHR `XEZN` subrecord now points at an LCTN ("Location Override") (**verified**, xEdit).
  Verdict: **translate** each ECZN into the level block of its LCTN (or a new child LCTN).
- Starfield adds LVLB (leveled base form, 356), LVLP (leveled pack-in, 51) and LVSC (leveled space cell, 6)
  (**verified**, xEdit + measurements). The port needs none of them for FO4 content; LVLP/LVLB are optional tools.
- Respawn: containers keep a `Respawns` flag in both (**verified**, xEdit); cell-reset timers and "cleared" rules are
  documented for Skyrim and assumed the same lineage in FO4 and Starfield (**supported hypothesis**).
- Location ref types (LCRT, `XLRT` on references) exist in both (704 vs 3,053) (**verified**). Verdict: **data copy**
  of FO4 LCRTs as our own records.

## How Fallout 4 does it
### Leveled lists (**verified**, xEdit; counts docs/measurements/fo4_esm.json)
| Record | Count | Entries | Flags (`LVLF`, u8) | Extra |
|---|---|---|---|---|
| LVLI | 2,094 | any base object | 0x01 calc from all levels <= player, 0x02 calc for each item in count, 0x04 use all | `LVSG` Epic Loot Chance (GLOB), `ONAM` override name |
| LVLN | 228 | LVLN, NPC_ | same, 0x04 "calculate all (still picks one)" | `MODL` generic model |
| LVSP | 0 in Fallout4.esm | LVSP, SPEL | same | defined by xEdit, unused in the base master |

- Lists nest; NPC_ templates (`TPLT`) can point at an LVLN, and actors placed from leveled bases resolve against the
  encounter zone level (**verified** example: `LvlRaider` with `LCharRaider` 00022E48, "calculate from all levels <=
  player", 7 tiers from level 1 to 39, docs/actors/raider-conversion.md:35-45).
- Placed leveled actors carry `XLCM` Level Modifier (Easy, Medium, Hard, Very Hard) (**verified**, xEdit, same enum in
  both games).

### Encounter zones (ECZN, FO4-only)
- `DATA`: Owner (NPC_/FACT), Location (LCTN), Rank (s8), Min Level (s8), Flags (Never Resets, Match PC Below Minimum
  Level, Disable Combat Boundary, Workshop), Max Level (s8) (**verified**, xEdit).
- Behaviour: when the player first enters, the zone locks a level between min and max; below min it uses min unless
  "Match PC Below Minimum Level"; "Never Resets" stops everything that starts in the zone from resetting; "Disable
  Combat Boundary" lets combat follow through load doors (**verified** as documented,
  https://falloutck.uesp.net/wiki/Encounter_Zone). The level lock itself ("zone level stays once set") is
  **supported hypothesis** (documented for Skyrim, https://ck.uesp.net/wiki/Encounter_Zone).
- Assigned via `XEZN` on CELL, REFR and ACHR (**verified**, xEdit).

### Locations, ref types, respawn
- LCTN (393): persistent/unique/special reference lists, `PNAM` parent, `MNAM` world location marker, `RNAM` radius,
  `FNAM` unreported-crime faction, keywords such as `LocTypeWorkshopSettlement` (**verified**, xEdit + falloutck
  Workshop page). FO4 LCTN has no level data: levels live on ECZN.
- LCRT (704): location reference types (Boss, map marker, etc.) set by `XLRT` on references and used by quest aliases and
  the "cleared" check (**verified** field; Boss-clears-location rule **supported hypothesis** via Skyrim's Cell Reset page).
- Containers: CONT `DATA` flags include `Respawns` (**verified**, xEdit). Reset timers: Skyrim uses
  `iHoursToRespawnCell` (10 days) and `iHoursToRespawnCellCleared` (30 days); actors, containers, placed items, doors
  and locks reset on re-entry, except refs in a Never Resets zone, refs with respawn off, enable state, created refs
  (**verified** for Skyrim, https://ck.uesp.net/wiki/Cell_Reset; same names and values in FO4 **supported hypothesis**).

## How Starfield does it
### Leveled lists (**verified**, xEdit; counts docs/measurements/sf_esm.json)
| Record | Count | Entries | New vs FO4 |
|---|---|---|---|
| LVLI | 5,556 | any base object | `LVLF` u16 (adds Show as Marker 1/2, Eval As Stack, Get Chance From Required Biome, Do All Before Repeating); list and entry `CTDA`; `LLRB` required biome; `LLRV` required resource vein (IRES); `LVLL` legendary default list rank; `LIMC` marker color |
| LVLN | 243 | LVLN, NPC_ | `LVLF` adds Disable If Does Not Resolve 1/2, Eval As Stack, Allow Shift Up, Do All Before Repeating; conditions |
| LVLB | 356 | GBFM, LVLB | leveled generic base forms; flag "Contains Only Spaceship Base Forms" |
| LVLP | 51 | LVLP, PKIN | leveled pack-ins (11,281 PKIN in Starfield.esm vs 872 in FO4) |
| LVSC | 6 | CELL, LVSC | leveled space cells |

### Location level replaces encounter zones
- LCTN (6,017) `DATA`: Ownership, Faction Rank, then "Encounter Leveling Data": Min Level (u8), Flags (Never Resets,
  Match PC Level, Disable Combat Boundary, Workshop, Use Parent's Locked Level), Max Level (u8) (**verified**, xEdit).
- REFR/ACHR `XEZN` is "Location Override" pointing at an LCTN; Starfield CELL has `XLCN` Location and no `XEZN`
  (**verified**, xEdit).
- "Use Parent's Locked Level" plus `PNAM` parent location means a child location can inherit its parent's locked
  level (**supported hypothesis** from the field names). Starfield's per-system levels shown in the star map likely
  come from this chain (**supported hypothesis**; not traced).
- LCRT (3,053) and `XLRT` unchanged in shape; LCRT gains a `Restricted` record flag (**verified**, xEdit).
- Containers keep `Respawns` (CONT `DATA` flags; Starfield's CONT `DATA` no longer carries the weight float FO4 had)
  (**verified**, xEdit). Reset timers in Starfield: **unresolved** (procedural POIs add their own reset logic).

## Mapping for the port
| FO4 piece | Starfield counterpart | Verdict | Notes |
|---|---|---|---|
| LVLI | LVLI | translate | widen flags to u16; no conditions needed; `LVSG` kept |
| LVLN | LVLN | translate | targets must be converted NPC_; today avoided (raider uses direct templates, docs/actors/raider-conversion.md:80-92) |
| LVSP (0 in base) | none | drop | check DLC masters |
| ECZN | LCTN Encounter Leveling Data | translate | one zone per location usually; zones without a location, or several zones per location, need our own child LCTNs |
| CELL/REFR `XEZN` (ECZN) | CELL `XLCN` / REFR `XEZN` (LCTN) | translate | rewrite to the LCTN that holds the zone's levels |
| ECZN Never Resets / Match PC / Disable Combat Boundary / Workshop | same LCTN flags | data copy | "Match PC Below Minimum Level" vs "Match PC Level": same meaning **supported hypothesis** |
| LCTN hierarchy | LCTN hierarchy | data copy | our planet's LCTN as root; FO4 `Commonwealth` etc. as children |
| LCRT + `XLRT` | LCRT + `XLRT` | data copy | own LCRT records (no reuse of Starfield's 3,053) |
| CONT Respawns, leveled container inventory | same | data copy | today containers get table-driven vanilla inventories |
| Reset timers (GMST) | GMST | unresolved | check Starfield values before relying on them |

## What must be rebuilt, and what needs SFSE or the Creation Kit
- An ECZN fold step in the converter: for each ECZN, find or create the LCTN that carries its levels; rewrite every
  `XEZN` and CELL reference. Pure data; no SFSE.
- Item targets: leveled lists only become useful when WEAP/ARMO/AMMO/ALCH convert ([items note](items-crafting-modding.md)).
  Until then the owner's container table is the stand-in (scripts/terrain/clusters/container_table.json: "FO4's
  leveled lists do not resolve in Starfield").
- Starfield's own scaling (system level, planet tiers) must not leak in: keep our LCTN chain outside Starfield's
  universe locations ("own ecosystem").
- SFSE / CK: not needed on current evidence; the CK is handy to see how vanilla LCTN levels inherit.

## Port status and links
- Containers: table names and vanilla inventories (Credits `00000F`, Digipick `00000A`), not FO4 lists (**verified**,
  container_table.json; docs/terrain/port-promotions.md:15-16).
- NPCs: raider conversion uses Starfield Spacer templates directly, without leveled lists, because a leveled chain may
  break `GetIsID` (**unresolved**, docs/actors/raider-conversion.md:80-92, docs/ai/research-log.md:1174-1175).
- NPC/faction plan: ../next-phase/npcs-ai-factions-dialogue-quests.md. World/location layout:
  ../next-phase/world-maps-lod-fasttravel.md.

## Open questions and cheap checks
- Fo4Export: ECZN to LCTN multiplicity (zones per location, zones with no location) over Fallout4.esm + DLC.
- SfInspect: 10 vanilla LCTN with non-zero Min/Max level and their parents; is "Use Parent's Locked Level" common?
- Read GMSTs `iHoursToRespawnCell` / `iHoursToRespawnCellCleared` in both masters (confirms the names and values).
- Count FO4 REFR/ACHR with `XEZN` and `XLCM` (scope of the rewrite).
- Do DLC masters carry LVSP records? (counts only for Fallout4.esm so far).

## Sources
- xEdit definitions: https://github.com/TES5Edit/TES5Edit (Core/wbDefinitionsFO4.pas, Core/wbDefinitionsSF1.pas)
- https://falloutck.uesp.net/wiki/Encounter_Zone
- https://ck.uesp.net/wiki/Encounter_Zone (Skyrim, lineage)
- https://ck.uesp.net/wiki/Cell_Reset (Skyrim, lineage)
- https://falloutck.uesp.net/wiki/Workshop
- Repo: docs/measurements/*.json; docs/actors/raider-conversion.md; scripts/terrain/clusters/container_table.json;
  docs/terrain/port-promotions.md
