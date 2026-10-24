# World, cells and navigation (FO4 CE1 vs Starfield CE2)

Part of the engine-mechanics reference ([index](README.md)). Author: Claude-cloud, 2026-10-19. Labels: verified /
supported hypothesis / unresolved. This is a mechanism summary. Plans and measurements live in
[../next-phase/world-maps-lod-fasttravel.md](../next-phase/world-maps-lod-fasttravel.md) (extent, DLC worlds, maps,
LOD, fast travel) and [../next-phase/trees-grass-terrain.md](../next-phase/trees-grass-terrain.md) (ground, grass,
trees, water).

## In short
- Both engines use WRLD (worldspace) holding exterior CELLs on a grid, interior CELLs on their own, and placed
  REFR/ACHR children, with a per-world persistent cell for always-present refs (**verified**, xEdit both games).
- FO4 terrain is per-cell `LAND` records (33x33 height grid `VHGT`, normals, colours, texture layers). Starfield has
  no LAND record at all (0 in Starfield.esm vs 37,020 in Fallout4.esm, **verified**, docs/measurements). Its ground
  comes from planet data (PNDT, BIOM, SFBK surface blocks, `.btd` terrain files). Verdict: **rebuild** (done for the
  core as a native BTD overlay).
- Exterior cells are about 58.5 m in FO4 (4096 units, **supported hypothesis**) and 100 m in Starfield (**verified**,
  project navmesh cut at "Starfield's 100 m cell lines"); the project scales FO4 units by 1/70 (**verified**,
  core64c.md). Verdict: refs **translate** (position remap, regrid).
- NAVM navmesh geometry (`NVNM`) has the same triangle layout in both, version 15 vs 17 (**verified**: xEdit defaults;
  layout checked on 63,875 FO4 and 256,726 Starfield triangles, research-log 2026-10-11). Verdict: **translate**
  (cut to 100 m cells, rewrite NVMI); already working offline.
- Load doors (`XTEL`) are identical in layout (**verified**, xEdit), but persistent refs in our overlay resolve at
  unmerged coordinates, so the port uses scripted doors (MoveTo) today (**verified**, JOURNAL 16 Oct).
- Map markers keep the same idea (REFR with a Map Marker struct, linked from LCTN) with a wider flag set and a new
  type enum in Starfield (**verified**, xEdit). Verdict: **translate** the marker type table.

## How Fallout 4 does it
**WRLD** (**verified**, wbDefinitionsFO4.pas 13110): EDID, `XEZN` encounter zone, `XLCN` location, parent world
(`WNAM` + `PNAM` use-flags), `CNAM` climate, `NAM2` water, `ICON` map image, map data (`MNAM` bounds), `NAMA`
distant LOD multiplier, `DATA` flags, `ZNAM` music, `TNAM`/`UNAM` HD LOD textures, object bounds, offset data.
5 WRLD in Fallout4.esm: Commonwealth, SanctuaryHillsWorld, DiamondCity, Goodneighbor, DiamondCityFX; the city ones are
child worlds that reuse the Commonwealth's land (**verified**, trees-grass-terrain.md section 2).

**CELL** (**verified**, wbDefinitionsFO4.pas 5953): `DATA` u16 flags (Is Interior, Has Water, Can't Travel From
Here, Public Area, Show Sky, ...), `XCLL` lighting, `LTMP` lighting template, `XCLW` water height, `XLCN`
location, `XEZN`, `XCIM` image space, precombine and previs fields (`PCMB`, `VISI`, `RVIS`, `XPRI`, `XCRI`).
40,164 CELL in Fallout4.esm (**verified**).

**LAND**: one per exterior cell, `VHGT` height map (33 rows), `VCLR` vertex colours (**verified**, xEdit
wbDefinitionsCommon.pas), normals and the `BTXT`/`ATXT`/`VTXT` texture layers (**supported hypothesis** here; see
trees-grass-terrain.md section 3). LTEX carries a grass list.

**REFR / ACHR**: position and rotation, `XTEL` teleport (door REFR, arrival pos/rot, flags No Alarm / No Load Screen /
Relative Position, Transition Interior CELL), `XLKR` linked refs, `XLRT` location ref types, `XLRL` location ref,
`XESP` enable parent, Map Marker struct (**verified**, wbDefinitionsFO4.pas 11550-11740). Map Marker: `XMRK` empty
marker, `FNAM` u8 flags (Visible, Can Travel To, "Show All" Hidden, Use Location Name), `FULL`, `TNAM` type u8
(Cave, City, Diamond City, Encampment, Factory, ... Sanctuary, ...) (**verified**, same).

**LCTN** (**verified**, wbDefinitionsFO4.pas 8039): persistent refs (`ACPR`/`LCPR`/`RCPR`), unique NPCs (`ACUN`/`LCUN`),
special refs (`ACSR`/`LCSR`, how map markers and boss refs are tied to a location), initially disabled refs
(`LCID`), enable parents (`LCEP`), `PNAM` parent location, `FNAM` unreported crime faction, `MNAM` world location marker
ref, `RNAM` radius, keywords. **LCRT** location ref types (`Boss`, `MapMarker`, and so on) are KYWD-like records used by
`XLRT` on refs and by quest aliases (**supported hypothesis** for the alias use). 393 LCTN / 704 LCRT (**verified**).

**NAVM / NAVI** (**verified**, wbDefinitionsFO4.pas 7212-7240): NAVM = `NVNM` geometry (vertices, triangles,
edge links, door links, cover, parent cell or world grid), `ONAM` base objects, `PNAM` preferred and `NNAM` non
connectors, `MNAM` precut map. NAVI (one per master) = `NVER` plus one `NVMI` per navmesh, `NVPP` precomputed pathing.
7,893 NAVM (**verified**).

**Loaded area**: an exterior grid of cells around the player is attached (INI `uGridsToLoad`, 5 by default;
**supported hypothesis**), refs outside it are detached and only LOD draws. Scripts see `OnCellAttach`, `OnCellDetach`,
`OnLoad`, `OnUnload`. Persistent refs stay in memory when their cell is detached.

**Fast travel**: Pip-Boy map, any discovered marker in the current world with Can Travel To; `ObjectReference.AddToMap`
(**verified**, falloutck); DLC worlds reached through scripted travel.

## How Starfield does it
**WRLD** (**verified**, wbDefinitionsSF1.pas 18940): kept: `XLCN`, parent world (`WNAM` + `PNAM` flags: Use Land,
LOD, Map, Water, Climate, Sky Cell), `CNAM`, `NAM2`, `ICON`, map data, `NAMA`, `DATA` flags (Small World, Can't Fast
Travel, No LOD Water, **No Landscape**, No Sky, Fixed Dimensions, No Grass), object bounds, offset and cell size
data. New: `BNAM` biome, `NAM7` water material, `FNAM` flags (Player Followers Can't Warp, Show Space, Prevent Merge
Cell Content, Allow ProcGen, Allow Cell Content), `WAMB` ambient set, `GNAM` gravity scale, ordered `LNAM` land
textures, Wwise event data. Gone: `XEZN`, `LTMP`, HD LOD textures. 433 WRLD in Starfield.esm (**verified**).

**CELL** (**verified**, wbDefinitionsSF1.pas 10589): `DATA` widened to u32 with Use Location as Name, Use Planet
Gravity, IS Volumes criteria, no biome material swaps; new `XCWM` water type, `XBPS` ship blueprint snap links, `XCGD`
material, `XCIB` inherit biome layer, `TODD` time of day, `CHAL`. Precombine/previs fields are gone. 30,717 CELL.

**Terrain**: no LAND. Planets (PNDT 1,765) with biomes (BIOM 431) generate ground; hand-made areas are overlay
worldspaces with surface blocks (SFBK 1,753) and `.btd` heightfield files; overlays merge into the planet's landing at
an offset (**verified** counts; merge mechanism **supported**, commonwealth-scale.md). Details and what the core
build does: trees-grass-terrain.md section 1, docs/terrain/architecture.md.

**REFR**: same `XTEL` struct and flags (**verified**). New: `XRFG` reference group, `XBPO` blueprint part origin,
`XSL1` snap links. Map Marker `FNAM` is u32 with new bits: Visible on Star Map, Discovered, Requires Scanning, Allow
Grav Jump, Suppress Discovery, Use Accurate Z-Height, Limit Map Visibility To Compass Range, Must Cruise to First;
`TNAM` is a u16 Starfield type enum (Akila City, Cydonia, ... New Atlantis, The Lodge, ...) (**verified**,
wbDefinitionsSF1.pas 8756-8890). Markers are REFRs of STAT `MapMarker` 00000010 linked via LCTN `LCSR`
(**verified**, docs/terrain/map-markers.md).

**LCTN** (**verified**, wbDefinitionsSF1.pas 13376): same persist / unique / special / disabled / enable-parent
arrays, plus `ACUR`/`LCUR` unique base forms, `TNAM` random conversation timer, `XNAM` Star ID, `YNAM` Planet ID,
`LENS`. LCTN 6,017 / LCRT 3,053 (**verified**). Locations nest star system > planet > surface > overlay; our core's
location has parent `SSol_PMars_Surface` (**verified**, map-markers.md).

**NAVM / NAVI** (**verified**, wbDefinitionsSF1.pas 14770-14930): NAVM adds `VMAD` and base form components; the
FO4 `ONAM`/`PNAM`/`NNAM` lists are gone; new `NOCM` navmesh obstacle manager record. NVMI entries carry traversals and
a cell-border tail; official plugins override NAVI `00000FF1` with only their own entries (**verified**,
research-log 2026-10-11). `TRAV` (23) are traversal forms (**verified** record; use **supported hypothesis**: jump
and climb links). NAVM 56,576.

**Loaded area**: `Starfield.ini` `uExterior Cell Buffer=36`; raising it keeps more full-detail cells, but the
project decided not to (**verified**, docs/terrain/object-lod.md). `OnCellAttach`, `OnCellDetach`, `OnLoad`,
`Is3DLoaded` remain on ObjectReference (**verified**, Starfield wiki Script-ObjectReference). Teleports of 2 cells or
less per axis land; 3 or more relocate or hang in 11 of 28 (**supported**, core64c.md).

**Fast travel**: surface map of the current landing plus star map and ship travel between landings; `AddToMap`,
`EnableFastTravel`, `Game.FastTravel` exist (**verified** names, Starfield wiki). Interior fast-travel targets need a
MapMarker in the exterior linked to an XMarker inside (community mod 12719, world-maps note section 5).

## Mapping for the port
| FO4 piece | Starfield counterpart | Verdict | Notes |
|---|---|---|---|
| WRLD Commonwealth | overlay WRLD + SFBK + BTD + LCTN on a host planet | rebuild | core done; DLC worlds one overlay each |
| Child worlds (DiamondCity, Goodneighbor) | own small overlay or interior-like cells | rebuild | parent flags exist but merge is untested |
| CELL exterior (58.5 m grid) | CELL exterior (100 m grid) | translate | regrid refs at FO4 / 70 |
| CELL interior | CELL interior | translate | lighting, water, location fields map; previs dropped |
| LAND | BTD heightfield + LTEX layers | rebuild | heights done; textures next |
| REFR / ACHR | REFR / ACHR | translate | FormID remap, scale, persistence |
| XTEL load doors | XTEL (same) or scripted door | translate / script shim | scripted MoveTo until merge issue solved |
| Map Marker struct | Map Marker struct | translate | FNAM u8 to u32 bits; TNAM type table to our own icons |
| LCTN + LCRT | LCTN + LCRT | data copy + remap | parent under our planet/overlay chain; new Star/Planet IDs |
| NAVM + NAVI | NAVM + NAVI override | translate | cut at 100 m cells; done for Red Rocket offline |
| Precombines / previs | none | drop | Starfield has no such CELL fields |
| uGridsToLoad / LOD | uExterior Cell Buffer + generated LOD | rebuild | object LOD plan in world-maps note section 4 |

## What must be rebuilt, and what needs SFSE or the Creation Kit
- Terrain (BTD) and land textures: our own writers (done / next). No CK needed.
- Object LOD: CK as format oracle, own generator for the launcher (world-maps note section 4).
- Merged-position fix for persistent refs (doors, markers): runtime mover quest (#376) or a writer fix still being
  isolated (world-maps note section 3).
- Navmesh: own converter (`src/fo4sf/navmesh.py`); CK2 navmesh generation is a fallback (**unresolved** whether it
  works on overlays).
- No SFSE need found for cells, doors or navigation.

## Port status and links
- Core overlay and scale: docs/terrain/core64c.md, commonwealth-scale.md, architecture.md, overlay-records.md.
- Doors: [door-behaviour.md](../../spikes/door-behaviour.md), docs/terrain/scripted-doors.md,
  door-arrival-position.md.
- Markers: docs/terrain/map-markers.md, surface-map.md. LOD: docs/terrain/object-lod.md.
- Navmesh: docs/actors/navmesh-conversion.md, navmesh-core64n-convert.md, navmesh-losses.md.

## Open questions and cheap checks
- FO4 exterior cell size: read `XCLC` grid and two neighbouring LAND origins in xEdit (confirms 4096 units).
- Does a Starfield child WRLD with `PNAM` Use Land Data work on an overlay? xEdit look for a vanilla child world.
- How many Starfield LCRT editor ids match FO4 LCRT editor ids (Boss, MapMarker ...)? One dump of both.
- CELL interior field mapping: diff `XCLL` struct sizes in the two xEdit files.
- `NOCM` and `TRAV`: does a plugin need either for NPCs to path on converted navmesh? Check what SFBGS003 overrides.

## Sources
- xEdit definitions dev-4.1.6: wbDefinitionsFO4.pas, wbDefinitionsSF1.pas, wbDefinitionsCommon.pas ([TES5Edit](https://github.com/TES5Edit/TES5Edit)).
- Project measurements: docs/measurements/fo4_esm.json, sf_esm.json.
- [Starfield Mod: Script-ObjectReference](https://dev.starfieldwiki.net/wiki/Starfield_Mod:Script-ObjectReference); [Script-Game](https://dev.starfieldwiki.net/wiki/Starfield_Mod:Script-Game)
- [AddToMap (falloutck)](https://falloutck.uesp.net/wiki/AddToMap_-_ObjectReference)
- [Interior fast travel mod (Nexus 12719)](https://www.nexusmods.com/starfield/mods/12719)
