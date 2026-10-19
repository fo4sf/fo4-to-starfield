# World and planet: the Commonwealth, Far Harbor and Nuka-World on one Earth-like planet

Framework research agent **world-planet** (Claude-cloud), 2026-10-19. Repo read-only at 447ec09. Labels:
**verified** (read in a linked source or file), **supported hypothesis**, **unresolved**. Nothing here was run in game.
Builds on, and does not repeat: next-phase/world-maps-lod-fasttravel.md, next-phase/trees-grass-terrain.md,
engine-mechanics/weather-time-climate.md, world-cells-navigation.md, vehicles-and-travel.md, and
docs/terrain/commonwealth-scale.md (engine INI defaults, CNAM lat/long order, H_ll).

Research limits, stated plainly: the shared web-search budget ran out partway through, and two pages were refused
by the fetch proxy (HTTP 429): the Nexus forum tutorial on Planet Content Manager POIs
(https://forums.nexusmods.com/topic/13491382-tutorial-creating-your-own-randomly-placed-pois/) and the Steam guide
"(Almost) Step-By-Step Creation of a Primitive Unique Point of Interest"
(https://steamcommunity.com/sharedfiles/filedetails/?id=3266682879). Both are unread. Questions that depend on them
are marked **unresolved**. The xEdit Starfield definitions (`Core/wbDefinitionsSF1.pas`, dev-4.1.6) were downloaded to
my scratchpad and read directly. Line numbers below refer to that file.

## Bottom line

"One Earth-like planet" is three landings on one planet, not one worldspace. A landing holds about 90 usable cells
(engine default 100 minus a 5-cell buffer, already decoded in commonwealth-scale.md). The Commonwealth core is 64
cells, so Far Harbor and Nuka-World each need their own overlay and landing, joined by scripted travel. What is new
here: (1) **Starfield's own Earth already has a 24 h day, the real Sun and Moon, and handmade overlays placed at real
city latitudes and longitudes.** That makes "host on Earth, at Boston's real coordinates" a serious option beside
"clone a planet". Its air, temperature, hazards and biome map would then need overriding. (2) **Landable custom
planets are now a shipped mod pattern.** Tridasha's SFStarEditor clones a STDT/PNDT/LCTN and copies the `.biom`
file, and the Pytheas system (July 2026) and the Star Wars galaxy (200+ planets) were built with this kind of
cloning. No public mod has yet put a 64-cell handmade landscape on such a planet. Project Tamriel, the one
announced "whole game world on one Starfield planet" mod, was cancelled after five days. (3) The schema has two
overlay-placement mechanisms the project has not used yet: PNDT `EOVR` "Edited Worldspaces" (add or remove an
overlay without overriding `CNAM`) and the unique-pattern components (`UniqueOverlayList`, `UniquePatternPlacementInfo`,
`BGSOverlayDesignatedPlacementInfo`), which place overlays on a grid inside a 16 x 16-block surface pattern. That
second one may be how Bethesda builds large multi-overlay regions such as Shattered Space's Va'ruun'kai. (4) Day
length, gravity, temperature and atmosphere are all planet data (PNDT `ENAM`, `FNAM`, `TEMP`, `INAM`, plus WRLD
`GNAM` gravity scale). Hazards are tested through planet-trait keywords (`BodyIsAtmosphereType`,
`BodyIsTemperatureType`). So an Earth-like feel is a data problem, except for the sky look (WTHS/ATMO reflection
blobs, still opaque).

## Findings

### 1. How a planet surface is put together (schema verified, behaviour as labelled)

| Piece | What the schema says | Label | Source |
|---|---|---|---|
| PNDT `CNAM` Master Worldspaces | array of (lat, long, WRLD) | verified (schema; order already verified in game data, commonwealth-scale.md 2) | sf1.pas 16054 |
| PNDT `EOVR` Edited Worldspaces | array of (lat, long, WRLD, Type u8: 0 Removed / 1 Added) | verified schema; how the engine merges EOVR across plugins: **unresolved** | sf1.pas 16068 |
| PNDT `PPBD` Biomes | per biome: BIOM, chance, resource generation, fauna, keywords, flora | verified | sf1.pas 16086 |
| PNDT `FNAM` Surface Tree | SFTR (procedural surface pattern map) | verified | sf1.pas 16120 |
| PNDT `ENAM` Orbital Data | axes, eccentricity, incline, **axial tilt**, **rotational velocity**, start angle, geostationary | verified | sf1.pas 16140 |
| PNDT `FNAM` Orbited Data | gravity well, mass, radius km, **surface gravity** | verified | sf1.pas 16155 |
| PNDT `HNAM` catalogue | magnetosphere, life, type, heat, hydro, habitable zone, **year length in days**, random seed | verified | sf1.pas 16166 |
| PNDT `INAM` Atmosphere Data | ATMO, density, Rayleigh, Mie | verified | sf1.pas 16196 |
| PNDT `KNAM` Biome Noise | noise file, biome and terrain-height frequency, **Terrain Max Height (m)** | verified | sf1.pas 16202 |
| PNDT `TEMP`, `DENS` | temperature in C, density | verified | sf1.pas 16219 |
| SFBK Surface Block | BTD data file, size, height, placement mode, **`WHGT` Water Height**, cell min/max | verified | sf1.pas 17525 |
| SFPT Surface Pattern | 16 x 16 grid of SFBK plus rotations, with master and override grids; `DNAM` worldspaces | verified | sf1.pas 17607 |
| SFTR Surface Tree | lists of SFPT, edge size (256, matching `uPlanetBiomMapFaceDim`) | verified schema; edge value verified in commonwealth-scale.md 1.2 | sf1.pas 17656 |
| Components `UniqueOverlayList` (WRLD + grid X/Y), `UniquePatternPlacementInfo` (PNDT + lat/long), `BGSOverlayDesignatedPlacementInfo` (overlay WRLD + X/Y) | DAT2 component data | verified schema; which records carry them and what they do: **supported hypothesis**, a unique surface pattern pinned to a planet location, with overlays at grid slots | sf1.pas 1511-1515, 6734-6770 |
| `BlockHeightAdjustment` component | 16 x 16 grid of (terrain height, water height), each normalised to -800..800 | verified schema; meaning **supported** (per-block height and sea-level offsets in a pattern) | sf1.pas 6775 |
| PCMT/PCBN/PCCN Planet Content Manager | tree of branch and content nodes; a content node can be a **WRLD**, LVLP or PKIN; conditions; per-planet, per-system and global limits | verified schema | sf1.pas 15764-15815, 6179 |

What this means for us (supported hypothesis): the planet's procedural surface is SFTR, then SFPT, then SFBK
blocks, with biomes from the `.biom` map. Handmade areas are overlays, placed either fixed (`CNAM`/`EOVR` at a
lat/long) or procedurally (PCM content nodes pointing at a WRLD). Our core uses the fixed path. The unique-pattern
components suggest a third path, a hand-placed grid of overlays inside one pattern. That would be the native way to
build something bigger than 14 cells out of standard-sized pieces.

The CK side (verified, Steam guide by a modder,
https://steamcommunity.com/sharedfiles/filedetails/?id=3385012985): "Worldspaces have to have terrain associated
with them". New worldspaces come from duplicating one, "terrain cutting from a terrain block", or "terrain cutting from
a planet location grid". An overlay "does not exist in the game world yet" until a location reference ties it to
planet coordinates chosen in the Galaxy View. This matches the project's own route (BTD + SFBK + PNDT CNAM)
without the CK.

Biome editing (verified, Nexus article 643, https://www.nexusmods.com/starfield/articles/643): biome maps are
`.biom` files in `Starfield - PlanetData.ba2`. They are edited with PixelRick's `biom.py` (swap biome FormIDs in the
north and south grids) and installed loose in `Data\planetdata\biomemaps`. Then the CK runs "Generate Biome
Placements", which "changes records for every planet" (clean in xEdit). "A biome doesn't affect the shape of the
terrain". Releases should be ESM, and medium masters "should be avoided".

### 2. Custom planets: what mods have done

| Precedent | What | How | Label |
|---|---|---|---|
| SFStarEditor (Tridasha), https://www.nexusmods.com/starfield/mods/11384 , source https://github.com/tridashafox/SFStarEditor | Clones a star and planets (and moons) from Starfield.esm into a plugin; "Creates the require locations to ensure navigation is possible"; copies the `.biom` "so the planet can be landed on" | C++ tool; source files `espreadstdt.cpp`, `espreadpntd.cpp`, `espreadlctn.cpp`. The biom file is renamed to the new planet's name; for an ESM it goes in `planetdata/biomemaps/<ESM>.esm/` (author: untested). Planet position in the system is not implemented, so it is set in the CK. "Only very limited changes ... once cloned" | verified as described |
| Pytheas System (SF_Eclipse), https://www.nexusmods.com/starfield/mods/15571 | 8 orbits, "Fully landable, biome complete planets", life-bearing worlds; small master; v2, 2 July 2026 | "I use Tridashafox's system creation tool" | verified as described |
| Star Wars Resources - Galaxy, https://www.nexusmods.com/starfield/mods/16954 | "50 new star systems, 200+ new planets, 900+ new moons", a master for later mods; some planets not landable yet (WIP); handmade Tatooine, Endor and Mos Eisley sold as separate "Planet Expansion Packs" by other authors | method not described | verified as described |
| Nexus forum, Jan 2024, https://forums.nexusmods.com/topic/13462799-hm-so-i-take-it-modded-planets-cant-be-a-thing-o_o/ | Before the CK: a new system loaded but "you can't land on the planet because the base biome map seems to be tied to the planet"; new galaxy data needed a new game; "bad ones can destroy your save" | trial and error | verified as reported (historical; the later tool solved landing) |
| Project Tamriel, https://starfieldportal.com/article/project-tamriel-ambitiously-plans-to-add-all-elders-scrolls-region-in-starfield , https://starfieldportal.com/article/starfield-project-tamriel-is-cancelled | "a single planet with all of these regions" (Skyrim, Oblivion, Morrowind): the same idea as ours | cancelled within days (reported 2 July 2024) for lack of community interest, not for a technical reason | verified as reported |
| Shattered Space (Bethesda DLC), https://80.lv/articles/starfield-dev-explained-how-shattered-space-s-world-was-created/ | "an explorable landmass with lots of hand-crafted content", contained so players "explore like they used to in Fallout and Skyrim" | not described; size not given | verified quote; build method **unresolved** (a PC read of its esm would tell) |
| Starfield's own Earth | 11 overlays at real city coordinates (Kyoto, Hong Kong, Cairo, St. Louis, Orlando ...) | `CNAM` lat/long = real geography | verified (commonwealth-scale.md 2) |

### 3. Landing size and "Boundary Reached"

- Engine values (already in commonwealth-scale.md 1.2, verified values): landing 100 cells, 5-cell playable buffer,
  1-cell overlay merge zone, landing keep-buffer 3, `uMinCellsFromBorder` 17.
- Community mods that push past the boundary: "Remove Planetary Tile Boundary" (an INI file; its key is not shown on
  the page; the author reports "some mixed results", https://www.nexusmods.com/starfield/mods/261). Press coverage
  says that "after a certain point the game just crashes"
  (https://finance.yahoo.com/news/modders-already-got-around-starfields-132556059.html). "Border Regions Unlock"
  (SFSE + Console Command Runner) sets `bBorderRegionsEnabled` and claims "over 10 km away from their ship without
  losing life or biomes", but "POI are still not spawning beyond the standard border limits"
  (https://www.nexusmods.com/starfield/mods/14643). Label: **verified as described**. The crashes and the 10 km figure
  are the authors' claims, not measured by us.
- Consequence (supported hypothesis): border unlocks extend *procedural* ground. They do not make a second handmade
  overlay load in the same landing (the project's exp3 already showed a landing loads only the overlay it arrives in).
  They are not a route to one seamless Commonwealth + Far Harbor + Nuka-World.

### 4. Day, night, sun, moon, gravity, temperature, hazards

- **Day length**: PNDT `ENAM` Rotational Velocity, read as rotations per 24 h (project supported hypothesis,
  test-queue.md). Independent check: Jemison "A day lasts 50 hours" (https://nukesdragons.com/starfield/db/planets/jemison),
  which matches the project's 0.48, so the formula gains support (**supported**, now with one outside check). Earth = 1.0,
  so 24 h.
- **Local time depends on where the overlay is registered**: arrivals at (0.3, -1.2) were night 18 of 18 times, and at
  (0.2, 1.2) day 13 of 13 times, from the same save (verified data, test-queue.md). So three worlds on one planet at
  different longitudes have different local times, as on Earth. Placing them at real longitudes gives a real offset
  (Boston to Mount Desert Island is about 3 degrees, so about 12 minutes; general geography, **supported**).
- **Year and seasons**: PNDT `HNAM` has "Year length in days". No season mechanism was found in the schema (no
  seasonal weather or foliage field; **supported hypothesis** that Starfield has no seasons). FO4 has none either, so
  nothing is lost.
- **Sun and moons**: the star's look is STDT `PNAM` Sun Preset (SUNP) plus `HNAM` Time of Day (TODD); BIOM `NAM0` can
  set TODD too (verified, sf1.pas 17915, BIOM). Moons in the sky are the system's other bodies (PNDT body type Moon,
  orbital data), so a host in Sol under Earth gets Luna for free. A cloned planet gets whatever moons are cloned with
  it (**supported hypothesis**: sky bodies are drawn from orbital data, not a texture).
- **Gravity**: PNDT `FNAM` Surface Gravity, and WRLD `GNAM` "Gravity Scale" (default 1) per worldspace; conditions
  `GetBodyGravity` 871 and `GetPlayerGravityScale` 944 (verified, sf1.pas 686, 745, WRLD). So a 1.0 g feel can be set on
  our WRLD even on a 0.38 g Mars, if `GNAM` multiplies the planet value (**unresolved**: whether it multiplies or sets).
- **Temperature, air and hazards**: PNDT `TEMP` (C), `INAM` ATMO; conditions `BodyIsAtmosphereType` 867 and
  `BodyIsTemperatureType` 868 take a **keyword** (verified, sf1.pas 682-684). So environmental hazards are driven by
  planet-trait keywords checked by conditions (**supported hypothesis**: the damage comes from a quest or spell that
  tests these). For the port, the host must carry "standard O2 / temperate" keywords, or the hazard effects must be
  disabled.
- **Weather**: WTHS (weather settings) carry **conditions** (verified, sf1.pas 18931), which the weather note did not
  record. CLMT `WSLT` picks WTHS by chance and global; BIOM `ENAM` names the climate; `BiomeHasWeather` 889 exists. So
  weather can be conditioned per world or region without REGN (**supported hypothesis**).

### 5. Water and sea level

- Schema (verified): SFBK `WHGT` Water Height (required); WRLD `NAM2` water (default 24), `NAM7` water material, water
  height data (required), parent flag "Use Water Data", DATA "No LOD Water"; BIOM Water Data (Has Water, WATR, material);
  `BlockHeightAdjustment` per-block water height.
- FO4 needs sea at 0 m: 55 % of Commonwealth LAND cells average below 0 (commonwealth-scale.md 1.3). Far Harbor is an
  island, so it needs sea on every side, beyond the overlay too. Supported hypothesis: inside the overlay the SFBK
  `WHGT` sets the sea. Beyond it, the planet's biome water decides, so the host biome around the island must be Ocean
  (Starfield has a `TNAM` biome type Ocean; Jemison is 60 % ocean, https://starfieldwiki.net/wiki/Starfield:Jemison).
  Whether an overlay's water height can differ from the surrounding planet's sea without a visible step: **unresolved**.

### 6. Fast travel, map, ship (extends vehicles-and-travel.md)

- PCM limits ("Number of Times Allowed (per planet world)", "Save Placement") and the WRLD `FNAM` flags "Prevent Merge
  Cell Content", "Allow ProcGen", "Allow Cell Content" (verified schema) give data-only levers to keep procedural POIs
  out of our landings. Today's core inherits whatever the template set: **unresolved**, an xEdit read.
- `iPlanetContentBlockOverlaySafeZoneBufferSize` 10 already keeps procedural content 10 cells from overlays
  (commonwealth-scale.md 1.2), so inside a 64-cell overlay no Starfield POI should spawn. The outer procedural ring of the
  landing (about 18 cells per side) may still get Starfield POIs (**supported hypothesis**).

## Precedents and what they teach us

1. **SFStarEditor and Pytheas**: a landable custom planet is achievable as plugin data plus a copied `.biom`, without
   SFSE. Lesson: our launcher could clone a planet record deterministically on the user's PC (no Bethesda asset
   shipped, since the `.biom` is copied from the user's own archive). Rotation, gravity, temperature and atmosphere
   would then be our edits. The risk is galaxy data. Early experiments needed a new game, and a bad star entry "can
   destroy your save".
2. **Starfield's Earth**: Bethesda already places handmade overlays at real coordinates on a 24 h planet with the Sun
   and Moon. Lesson: real geography (Boston, Mount Desert Island, and a Nuka-World site) costs nothing extra in placement
   math. It is the same `CNAM` path we use on Mars.
3. **Article 643 biome swap**: the procedural ground around our overlays (the buffer ring and beyond) can be made
   Earth-like by pointing a planet's biome map at our own BIOM, without new terrain shape. Lesson: the horizon outside
   the BTD becomes New England-ish forest and ocean instead of Mars, before any LOD work.
4. **Project Tamriel**: the one public attempt at our exact shape died socially, not technically. Lesson: there is
   no community pipeline to borrow, and community interest needs a demo early.
5. **Border unlock mods**: past the landing edge the game crashes or degrades. Lesson: do not design for one seamless
   giant landing.
6. **Shattered Space**: Bethesda's own large handmade landmass is the best structural reference. Lesson: read its esm
   before inventing a multi-overlay scheme.

## Risks

| Risk | Likelihood | Why |
|---|---|---|
| Galaxy edits (new STDT/PNDT) break saves or need a new game | medium | Forum reports from Jan 2024; our start is a new game anyway (phase 1), which lowers the cost. Adding a planet mid-playthrough is the risk |
| Hosting on Starfield Earth collides with vanilla quests and overlays, or with other mods editing Earth | medium | Earth is a vanilla quest location; overriding its PNDT (air, temperature, biomes) is a whole-record override; `EOVR` may avoid overriding `CNAM` (unresolved) |
| Sky look stays alien (WTHS/ATMO/CLDF are reflection blobs) | high for v1 | Only vanilla presets can be referenced; pick the most Earth-like (Jemison/New Atlantis) |
| Second and third overlays merge at unmeasured offsets; the persistent-ref merge problem repeats per world | high | Already open for the core (#376 runtime mover) |
| Far Harbor's sea: overlay water vs planet ocean mismatch at the edge | medium | No measurement; island geography makes the edge visible on every side |
| Hazard and temperature systems damage the player on a cloned planet | medium | Keyword-driven; a missed keyword means suit warnings in the Commonwealth |
| Biome placement regeneration ("Generate Biome Placements" touches every planet) creates a huge dirty plugin | medium | Article 643 says so; our launcher must write only the records it needs |
| Overlays above 14 cells keep being unusual | known | Core 64 works in game; Far Harbor (about 18 cells) and Nuka-World (about 14) are smaller (trees-grass-terrain.md 2) |
| Fast travel between landings touches the ship path and hangs | medium | Playtest row 7; scripted travel avoids it |

## Questions for the framework

### New game
1. **Where does a new game spawn the player's planet and time?** Why: the Vault 111 exit should be morning in the
   Commonwealth, and local time depends on lat/long plus the save's universal time. Options: `SetLocalTime` at the
   vault exit (Bethesda uses it in `QF_MQ101`, test-queue.md); choose the registration longitude so the default start
   time lands in daylight. Evidence: one run reading local time at the core after a fresh start. Who: PC probe.
2. **Does a new galaxy entry (if we clone a planet) need a new game, and is that acceptable?** Why: the forum reported
   new systems need a new game; phase 1 is a new game anyway. Evidence: install the plugin on an existing save and see
   whether the planet appears. Who: PC probe, owner decision.

### World and planet
3. **Host: Starfield's Earth, a cloned Earth-like planet, or keep Mars?** Why: it decides sky, sun, moon, day length,
   ground beyond the BTD, and mod conflicts. Options: (a) Earth, edited (24 h, Sol, Luna, real coordinates; needs air,
   temperature, keyword and biome overrides on a quest-bearing vanilla planet); (b) a clone (SFStarEditor pattern) in its
   own system, maybe named for the setting; full control, but a galaxy edit; (c) Mars (today: 25 h, 0.38 g, Mars sky).
   Evidence: SfInspect dump of Earth's PNDT (`INAM` ATMO, `TEMP`, keywords, PPBD biomes, `CNAM`/`EOVR`) and of Jemison.
   Who: offline research plus owner decision.
4. **Can a plugin add our overlays to a planet through PNDT `EOVR` (Added) instead of overriding `CNAM`?** Why:
   overriding `CNAM` copies the whole list and conflicts with any other mod touching that planet. Evidence: find vanilla
   or DLC uses of `EOVR` (ShatteredSpace.esm, SFBGS00x) and one terrain-only test that registers via `EOVR` alone. Who:
   offline xEdit read, then a PC probe.
5. **How did Bethesda build Shattered Space's handmade landmass: one big overlay, several overlays, or a unique surface
   pattern with `UniqueOverlayList`?** Why: it is the closest vanilla model of a large handmade region. Evidence: read
   the DLC esm: SFBK sizes, WRLDs, PNDT `CNAM`/`EOVR`, SFPT with unique components. Who: offline (PC read-only walker).
6. **What do `UniqueOverlayList`, `UniquePatternPlacementInfo` and `BGSOverlayDesignatedPlacementInfo` do, and on which
   records?** Why: a grid of overlays in one pattern might give seamless 12-cell-pitch tiles and an official
   multi-overlay path (fallback (b) in commonwealth-scale.md). Evidence: a census of DAT2 components by record type in
   Starfield.esm. Who: offline.
7. **Real geography or compact layout for the three worlds?** Why: real lat/long (Boston about 42.4 N 71.1 W; Far
   Harbor at Mount Desert Island about 44.4 N 68.2 W) gives real local-time offsets and a credible map. A compact layout
   keeps them on one surface-map view. Options: real coordinates; a stylised layout at more than 100 cells apart.
   Evidence: H_ll scale on Earth (R 6,371 km, about 63,710 cells per radian) puts them about 3,800 cells apart, which is
   harmless. Who: owner decision.
8. **Where is Nuka-World on the planet?** Why: FO4 places it by monorail from a Commonwealth station; its real-world
   position is not given in the sources read (**unresolved**). Options: a fictional inland site west of Boston; the lore
   location if the census or game text gives one. Who: offline research (FO4 data and lore), owner decision.
9. **Does WRLD `GNAM` gravity scale multiply the planet's gravity or replace it?** Why: 1 g in the Commonwealth on any
   host. Evidence: set `GNAM` 2.63 on a Mars overlay and read `GetPlayerGravityScale` (or jump height). Who: PC probe.
10. **Which planet-trait keywords stop hazards and suit warnings?** Why: no oxygen or temperature damage in Boston.
    Evidence: list the keywords that `BodyIsAtmosphereType`/`BodyIsTemperatureType` are tested with in Starfield.esm
    (the hazard quest or spells) and the ones Jemison carries. Who: offline.
11. **Which day length do we want: a real 24 h (rotation 1.0), or FO4's feel?** Why: FO4 runs `TimeScale` 20, so a
    24 h day is 72 real minutes, the same as Starfield on Earth. With rotation 1.0 nothing changes for the player.
    Evidence: compare `Planet.GetDayLength()` in game with the formula. Who: PC probe.
12. **Can the procedural ground outside our BTDs be made New England-like by a biome map edit?** Why: the horizon
    without LOD, and the buffer ring. Options: biom.py swap to our BIOM (article 643); clone Jemison's forest biomes.
    Evidence: one biome swap on the host and a look from the core's edge. Who: offline build plus PC look.
13. **Is the `.biom` keyed by planet name, FormID or edid, and can the launcher write it from the user's archive?** Why:
    the launcher ships no assets; SFStarEditor copies and renames it by planet name. Evidence: read SFStarEditor source.
    Who: offline.
14. **Overlay sea level vs planet ocean: does SFBK `WHGT` + BIOM water give a seamless coast?** Why: Far Harbor, Boston
    Harbor, the Charles. Evidence: a terrain-only island overlay at 0 m water, surrounded by an Ocean biome; look at the
    merge ring. Who: PC probe.
15. **One overlay per DLC world, or a grid of smaller overlays?** Why: Far Harbor is about 18 x 18 Starfield cells and
    Nuka-World about 14 (community size, unverified). One overlay each fits the proven path. Evidence: the DLC census.
    Who: PC read-only after the DLC install.
16. **Do we keep FO4's unplayable outer ring (114 vs 64 cells) as terrain, LOD, or procedural Earth biome?** Why: the
    horizon. Options in world-maps note section 1; new here: an Earth biome as option D (cheap). Who: owner, after Q12.
17. **Does `KNAM` "Terrain Max Height" or the biome noise of the host shape the merge ring around a 64-cell overlay?**
    Why: cliffs at the overlay edge. Evidence: compare edge heights on hosts with different `KNAM`. Who: PC probe.
18. **Weather per world: one CLMT for the planet, or per-world climates via WRLD `CNAM`, BIOM `ENAM` and WTHS
    conditions?** Why: Far Harbor's fog and the Glowing Sea's radstorms in one climate system. Evidence: confirm which of
    WRLD `CNAM` and BIOM `ENAM` wins on an overlay (one `fw` test each). Who: PC probe.
19. **Which vanilla WTHS/ATMO set reads most Earth-like (clear, overcast, rain, fog)?** Why: v1 sky. Evidence: the
    runner's sky_light script over Jemison and New Atlantis weathers. Who: PC probe.
20. **Can the PCM be told to place nothing on our planet?** Why: Starfield POIs in the Commonwealth's buffer ring.
    Options: no PCM tree conditions matching our planet's keywords; WRLD `FNAM` flags; per-planet limits of 0. Evidence:
    walk the landing edge and count spawned POIs. Who: offline xEdit, then PC.

### Travel, map and ship
21. **Ship: fenced out completely, or kept as a disguised fast-travel vehicle (a vertibird skin)?** Why: between
    landings Starfield's native path is the ship; fencing it out means scripted travel only. Options: scripted
    boat/monorail (vehicles note); a ship reskinned as a vertibird using the native landing UI. Who: owner decision.
22. **Does the surface map show and fast travel to markers of another landing on the same planet without the ship?**
    Why: one-planet fast travel between the Commonwealth and Far Harbor. Evidence: two terrain-only landings, one map look.
    Who: PC probe (already listed in the vehicles note; it gains weight here).
23. **How do we hide the star map, grav jump and orbit view on an Earth host?** Why: opening the star map in Boston
    breaks the setting. Options: menu blocks by script; SFSE only if needed (**unresolved**). Who: offline research.
24. **Do border unlock settings (`bBorderRegionsEnabled`) interfere with our landings?** Why: users may run those
    mods. Evidence: a compatibility note test. Who: PC probe, community contact.

### Launcher
25. **Can the launcher generate the planet records (clone, rotation, gravity, keywords, `.biom` copy)
    deterministically?** Why: no CK on the user's PC, no shipped assets. Evidence: a synthetic-fixture writer test
    against Mutagen. Who: offline.
26. **Does the planet live in its own small master that the world plugins depend on?** Why: load order and future
    FO3/New Vegas on the same core (a second planet or the same one). Who: owner decision.

### Performance
27. **What does a fast travel or landing into a 64-cell overlay with 648k refs cost in load time and memory?** Why: three
    of them, plus later FO3/NV. Evidence: timed `coc` and first-frame times; memory at the core. Who: PC probe, numbers
    to docs/ai/optimization.md.
28. **Does a larger host-planet atmosphere (fog volumes, clouds) change frame time over the dense core?** Why: an Earth
    sky with clouds costs more than Mars. Who: PC probe.

### Release and community
29. **Would hosting on Starfield's Earth conflict with popular Earth overhaul mods?** Why: a Nexus release. Evidence:
    survey of Earth-editing mods. Who: community research.
30. **Is a custom star system (FO4 "Sol" lookalike) a release liability for saves?** Why: removing a galaxy-edit mod
    may break saves. Evidence: SFStarEditor and Pytheas comment threads. Who: community research.

### Tooling and testing
31. **Can SfInspect dump PNDT `ENAM`/`FNAM`/`INAM`/`TEMP`/keywords for all 1,765 planets?** Why: choose a host by data
    (rotation 0.9-1.1, about 1 g, standard O2, temperate). Who: offline (PC read-only).
32. **Can the runner read local time, gravity and hazard state in one probe?** Why: one acceptance step per world.
    Who: PC runner design.

### Cross-cutting
33. **FO3 and New Vegas later: the same planet at other coordinates (DC, Mojave), or other planets?** Why: decides
    whether the planet master is "Earth" generically. Who: owner decision.
34. **Do we model the Glowing Sea as a separate biome or climate inside the Commonwealth overlay?** Why: its radstorm
    weather and colour. Options: REGN weather (Starfield keeps REGN `RDWT`); WTHS conditions. Who: offline, then PC.

## Corrections

- No project note was found wrong. Two extensions to recorded facts: (a) weather-time-climate.md lists WTHS as
  "REFL + RFDP + RDIF"; it also carries **conditions** (CTDA) (verified, sf1.pas 18931). (b) world-maps note section 2
  says each DLC world is "registered as its own PNDT CNAM entry"; the schema also offers **`EOVR` Edited Worldspaces**
  with Added/Removed, a possible conflict-free path (verified schema, behaviour unresolved).
- Outside source to avoid: dotesports says local time is "tied to how long that planet takes to orbit its sun"
  (https://dotesports.com/starfield/news/the-difference-between-ut-and-local-time-in-starfield). That is rotation, not
  orbit (project's PNDT `ENAM` Rotational Velocity reading, plus the Jemison 50 h day). Do not cite it.

## Sources

- xEdit Starfield definitions, TES5Edit dev-4.1.6 `Core/wbDefinitionsSF1.pas`: https://github.com/TES5Edit/TES5Edit
  (raw file read: PNDT 16048, BIOM 10119, WRLD, SFBK 17525, SFPT 17607, SFTR 17656, STDT 17915, CLMT 10843, WTHS 18931,
  PCBN/PCCN/PCMT 15764-15815, components 6179, 6554, 6700-6790, conditions 238-745)
- https://www.nexusmods.com/starfield/mods/11384 ; https://github.com/tridashafox/SFStarEditor
- https://www.nexusmods.com/starfield/mods/15571
- https://www.nexusmods.com/starfield/mods/16954?tab=description
- https://www.nexusmods.com/starfield/articles/643
- https://forums.nexusmods.com/topic/13462799-hm-so-i-take-it-modded-planets-cant-be-a-thing-o_o/
- https://steamcommunity.com/sharedfiles/filedetails/?id=3385012985
- https://starfieldportal.com/article/project-tamriel-ambitiously-plans-to-add-all-elders-scrolls-region-in-starfield
- https://starfieldportal.com/article/starfield-project-tamriel-is-cancelled
- https://80.lv/articles/starfield-dev-explained-how-shattered-space-s-world-was-created/
- https://www.nexusmods.com/starfield/mods/261
- https://www.nexusmods.com/starfield/mods/14643
- https://finance.yahoo.com/news/modders-already-got-around-starfields-132556059.html
- https://www.cgmagonline.com/news/starfield-boundary-reached-controversy (no size figure)
- https://starfieldportal.com/article/starfield-invisible-walls-boundaries-more (no size figure)
- https://nukesdragons.com/starfield/db/planets/jemison
- https://starfieldwiki.net/wiki/Starfield:Jemison
- https://dotesports.com/starfield/news/the-difference-between-ut-and-local-time-in-starfield (cited only as a wrong claim)
- Not readable (HTTP 429): https://forums.nexusmods.com/topic/13491382-tutorial-creating-your-own-randomly-placed-pois/ ,
  https://steamcommunity.com/sharedfiles/filedetails/?id=3266682879
- Project notes: /mnt/project-files/research/next-phase/world-maps-lod-fasttravel.md, trees-grass-terrain.md;
  /mnt/project-files/research/engine-mechanics/weather-time-climate.md, world-cells-navigation.md, vehicles-and-travel.md;
  repo docs/terrain/commonwealth-scale.md, docs/ai/test-queue.md

## Wave 2 additions (2026-10-19)

Wave 2 read the two pages that were rate-limited in wave 1 and looked again at Shattered Space, LOD and the PCM. Same
labels.

### W2-1. Planet Content Manager: placing a POI (MikkoK141 tutorial, forum topic 13491382; answers Q20 in part)
- **verified** ([forum 13491382, MikkoK141, 14 Jun 2024, edited 19 Jun 2024; page 1 of 3 read](https://forums.nexusmods.com/topic/13491382-tutorial-creating-your-own-randomly-placed-pois/)):
  1. WorldData > Blocks: pick a terrain block; Ctrl+H opens the terrain cutting tools; cut an area (author used 3x3
     cells) and "create overlay".
  2. On the overlay's WRLD add `BSGPlanetContentManagerContentProperties_Component`.
  3. Create a Location with keywords `LocTypeOE_Keyword` and `LocTypeOverlay`; assign it to the overlay.
  4. Optional pre-discovered MapMarker.
  5. WorldData > **Planet Content Manager Tree** > `PCM_BlockCreationRequest` > `PCM_BlockCreation_DRsRLs`: right-click
     "add worldspacecontent", pick the POI. Removing competing entries makes it spawn more often.
  6. Test with the console command `AddWorldSpaceToPlanetBiome <WorldSpace> <Planet> <biomeIndex>`; random spawning is
     "not guaranteed". `RE_PackIn_Overlay` adds random-encounter triggers; removing its landing areas stops ship encounters.
  Gotchas: terrain sometimes missing in the cell view (redo the cut; a reply ties it to **underscores in the overlay
  name**); distant LOD for the POI was unsolved in the thread.
- **verified** ([Anig, Steam guide 3269084567, Jun 2024 / Jun 2025](https://steamcommunity.com/sharedfiles/filedetails/?id=3269084567)):
  PCM branches (e.g. `PCM_BlockCreation_OEWorlds_Natural`) apply their **conditions** to the content added to them,
  e.g. a biome must be Snowfield; a Location with keyword **`PCM_OverlayExclusionZone`** makes PCM keep random POIs at
  least **4,000 units** away. Random POIs from mods show no model on the local map.
- **What this answers**: Q20 ("Can the PCM be told to place nothing on our planet?"): there are two levers in the data:
  `PCM_OverlayExclusionZone` on our Locations (a 4,000-unit ring, verified as described) and PCM tree **conditions**
  (planet/biome conditions on branches; supported hypothesis that a condition excluding our host planet stops all
  random content there, which needs an override of vanilla branches: a conflict risk with PCM mods). Q6 is partly
  answered: overlay WRLDs carry the PCM content component.

### W2-2. Unique POI at fixed coordinates (Anig, Steam guide 3266682879; answers Q4/Q15 context)
- **verified** ([Anig, 12 Jun 2024, upd. 19 Jun 2024; the page now carries a Steam removal notice but the text is visible](https://steamcommunity.com/sharedfiles/filedetails/?id=3266682879)):
  Galaxy View > system > planet > pick a surface position > Overlays tab "+" > cut an area (recommended **no larger than
  6x6** cells), lock, name, tick **"Unique"**. Then place MapMarker, `ShipLandingMarker_80m_Large`, `XMarkerHeading`;
  link MapMarker > landing marker > heading marker (Linked Ref) so the ship lands there; set Marker Data (Visible,
  Visible on Star Map, Allow Grav Jump, Can Travel To, Radius). Cells whose name ends in `*` "MUST BE GIVEN a UNIQUE
  NAME" or the POI does not appear on the planet map. Placing a POI far from the central cell can crash the CK; the
  workable limits are unknown to the author. Landscape edits show in the CK but not in game (fixed by exporting the
  terrain `.btd`, starfield-toolchain.md W2-1).
- **Implication (supported hypothesis)**: the CK's own overlay workflow is tuned for small (≤ 6x6) overlays. Our 64-cell
  (and Far Harbor ~18x18) overlays are 10-100x that, written by our converter, not cut in the CK. Q15 (one overlay or a
  grid) gains weight: a grid of smaller overlays stays inside the size the community has seen working.
- **verified**: mods that override cells of a vanilla worldspace (NEON Core, The Well, Cydonia in `SFBGS008.esm`) broke
  surface maps and POI scanner markers until a patch re-copied the affected sub-blocks (user report, 1.13.61,
  [forum 13497605](https://forums.nexusmods.com/topic/13497605-info-mods-changing-world-spaces-may-break-surface-maps-poi-markers)).
  Relevant to Q29 if we host on vanilla Earth.

### W2-3. LOD for our worlds (extends Q15, Q16 and "Performance")
- ~~**verified**~~ [Correction 2026-10-19: ~~**unresolved (sources conflict)**~~: web guides say the switch exists; ~~a
  job 18 string dump of the installed CreationKit.exe does not show it (a wide string the filter missed, or absent in
  the current CK)~~ [Correction 2026-10-19: that dump printed only strings matching its default patterns (Generate,
  Compile, Lip, AnimInfo, -Convert, -Build), so it had filtered the switch out; job 20 found it: **verified (Starfield
  CK, job 20)**, not in the FO4 CK, usage "-MockWorldSpaceLOD:(ESMFilename) (WorldSpaceName0) [WorldSpaceName1]
  [...]" (an ESM filename)]; the job 18 dump does show the **verified** LOD-related switches `-GenerateMeshLODAssociations`,
  `-GenerateMeshLODFailureReport`, `-GenerateMeshLODStats`. See starfield-toolchain.md W2-1.]: object LOD via `CreationKit.exe -MockWorldSpaceLOD:<Plugin> <Worldspace,...>`, objects chosen by layers
  with the LOD box; output in `Data\Meshes\Terrain\<Worldspace>\` and `Data\LODSettings\`; cells can fail in multi-cell
  worldspaces ([modding.wiki](https://modding.wiki/en/starfield/developers/tutorials/creatingworldspacelod)). Full detail in
  starfield-toolchain.md W2-1. A Reddit snippet (not read in full) ties this LOD run to the **local map** rendering
  ([r/starfieldmods](https://www.reddit.com/r/starfieldmods/comments/1ntdwu9/starfields_local_maps/), **supported
  hypothesis**).
- ~~**supported hypothesis**: Starfield has no precombine/previs step (no such CELL fields in xEdit's SF1 definitions), so
  the world plan needs object LOD + terrain BTD, not a previs bake.~~ [Correction 2026-10-19: weakened: no such CELL
  fields, but the Starfield CK has the GUI actions "Generate Precombined Visibility for Current Cell" and "... All
  Loaded Cells" (interiors.md T9; no precombine or previs switch, job 20). Whether the world plan needs that bake, what
  it writes and whether it matters for performance is **unresolved**; `-GenerateCellAndRefCounts` (possibly per-cell
  reference counts) is **unresolved**.]

### W2-4. How Shattered Space's landmass was built (Q5) — still **unresolved** on method
- **verified**: Emil Pagliarulo (design director): "We knew very early on that we needed to add an explorable landmass with
  lots of hand-crafted content ... as opposed to the base game's method of providing systemic and procedural content";
  "content is contained to a single, large landmass"; "there's definitely some procedural, repeatable content in Shattered
  Space". The team tested "the limitations of what they could do" in "the creation tools" (eternal eclipse, pools of
  mercury) ([GamesRadar+, 30 Sep 2024](https://www.gamesradar.com/games/rpg/players-can-explore-like-they-used-to-in-fallout-and-skyrim-how-shattered-space-brings-the-bespoke-goodness-of-past-bethesda-rpgs-to-starfield/)).
  Size: "at least 50 unique locations" ([Kotaku AU](https://kotaku.com.au/2024/09/9-minute-starfield-deep-dive-gives-a-tour-of-the-expansions-new-handcrafted-planet));
  no km or cell figure in any source read.
- **No public source** describes the build (one big overlay vs several, unique surface, BTD size). The answer is a PC
  read: list `ShatteredSpace.esm` WRLD records with their bounds and PNDT `EOVR`/`CNAM` entries for Va'ruun'kai, and the
  sizes of the `.btd` files in its archives. That gives Bethesda's own precedent for a large handmade area on one planet.

### Questions changed or added
- **Q20**: options now named (exclusion-zone keyword; branch conditions). Remaining: does an exclusion zone scale beyond
  4,000 units, or do we need conditions? Experiment: one test planet, both levers, land 10 times.
- **Q15**: add "the CK overlay tool is used at ≤ 6x6; is a converter-written 64-cell overlay stable in the CK and the game?"
- **New Q35**: do overlay names with underscores break terrain (two independent user reports)? Our generated EDIDs must
  avoid the pattern until disproved. Who: offline rule now, PC probe later.
- **New Q36**: do we need `BSGPlanetContentManagerContentProperties_Component` and `LocTypeOverlay` on our WRLDs even for
  fixed (unique) overlays? Who: xEdit read of a vanilla unique overlay (e.g. an Earth city).

### Sources (wave 2)
- https://forums.nexusmods.com/topic/13491382-tutorial-creating-your-own-randomly-placed-pois/
- https://steamcommunity.com/sharedfiles/filedetails/?id=3266682879 ; https://steamcommunity.com/sharedfiles/filedetails/?id=3269084567
- https://forums.nexusmods.com/topic/13497605-info-mods-changing-world-spaces-may-break-surface-maps-poi-markers
- https://modding.wiki/en/starfield/developers/tutorials/creatingworldspacelod ; https://www.reddit.com/r/starfieldmods/comments/1ntdwu9/starfields_local_maps/ (snippet only)
- https://www.gamesradar.com/games/rpg/players-can-explore-like-they-used-to-in-fallout-and-skyrim-how-shattered-space-brings-the-bespoke-goodness-of-past-bethesda-rpgs-to-starfield/
- https://80.lv/articles/starfield-dev-explained-how-shattered-space-s-world-was-created/ ; https://kotaku.com.au/2024/09/9-minute-starfield-deep-dive-gives-a-tour-of-the-expansions-new-handcrafted-planet
