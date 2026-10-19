# World and planet

Part of the [next-phase framework](README.md). Wave 1, 2026-10-19. Sources: findings/world-planet.md,
findings/multi-game-scope.md (geography and travel), findings/precedents.md (world parts: FNV to FO4, TTW),
findings/versions-performance.md (budget parts).

Builds on, does not repeat: research/next-phase/world-maps-lod-fasttravel.md (core extent, DLC overlays, maps, LOD,
fast travel, persistent-ref merge problem and #376). Where a topic is fully covered there, this file points to it.
Short names below: WP = findings/world-planet.md, MG = findings/multi-game-scope.md, PR = findings/precedents.md,
VP = findings/versions-performance.md, WM = next-phase/world-maps-lod-fasttravel.md, sf1.pas = xEdit
`Core/wbDefinitionsSF1.pas` dev-4.1.6.

## In short

- "One Earth-like planet" means three landings on one planet, not one worldspace. A landing holds about 90 usable cells;
  the core alone is 64, so Far Harbor and Nuka-World each need their own overlay and landing, joined by scripted travel.
- An Earth-like feel is mostly planet data: day length, gravity, temperature and air are PNDT and WRLD fields, and
  hazards are tested through planet-trait keywords. The sky look (WTHS/ATMO) is the part that stays opaque.
- New option: Starfield's own Earth already has a 24 h day, the real Sun and Moon, and overlays at real city coordinates.
  Cloning a planet (SFStarEditor pattern) is the other serious host; Mars is today's host.
- Most uncertain: whether PNDT `EOVR` can add our overlays without overriding `CNAM`; how Bethesda built Shattered
  Space's landmass; whether the surface map fast travels between landings without the ship; how a coast looks where
  overlay sea meets planet ocean.
- Three decisions that unlock the most: **WP-01 host planet**, **WP-14 real geography or compact layout**, **WP-27 the
  ship: fenced out or disguised**.

## What is settled

| Fact or decision | Label | Source |
|---|---|---|
| Owner: the Commonwealth, Far Harbor and Nuka-World on ONE Earth-like planet with real days, nights and weather; breadth before polish; SFSE and the Starfield CK MAY be required | owner decision | findings/BRIEF.md |
| Core today: one overlay `FO4Core_Commonwealth`, 64 x 64 Starfield cells, on Mars; holds all 648,358 converting Fallout4.esm exterior refs | verified | WM facts table (docs/terrain/core64c.md) |
| Landing default 100 cells, 5-cell playable buffer, 1-cell merge zone; largest planet-registered vanilla overlay is 14 cells | verified values | WP 3; WM (commonwealth-scale.md 1.1-1.2) |
| Each world is its own overlay landing, joined by scripted travel (the settled layout) | settled in project notes | MG 5; WM 2 (vehicles-and-travel.md) |
| A landing loads only the overlay it arrives in (exp3); border-unlock mods extend procedural ground only, and past the edge the game crashes or degrades (author claims) | verified (exp3), supported hypothesis (consequence) | WP 3; Nexus mods 261, 14643 |
| Local time depends on the overlay's registered lat/long: night 18 of 18 at (0.3, -1.2), day 13 of 13 at (0.2, 1.2), same save | verified data | WP 4 (docs/ai/test-queue.md) |
| Day length is PNDT `ENAM` Rotational Velocity as rotations per 24 h; Earth 1.0 = 24 h; Jemison 0.48 matches its 50 h day | supported hypothesis, one outside check | WP 4; nukesdragons Jemison |
| Planet data fields exist: PNDT `CNAM` (lat, long, WRLD), `EOVR` (Added/Removed), `PPBD` biomes, `ENAM` orbit incl. axial tilt and rotation, `FNAM` surface gravity, `HNAM` year length, `INAM` atmosphere, `KNAM` terrain max height, `TEMP`; WRLD `GNAM` gravity scale; SFBK `WHGT` water height | verified schema | WP 1 (sf1.pas 16054-16219, 17525) |
| Hazard conditions `BodyIsAtmosphereType` (867) and `BodyIsTemperatureType` (868) take a keyword | verified schema | WP 4 (sf1.pas 682-684) |
| WTHS carries conditions (CTDA), which weather-time-climate.md did not record | verified schema | WP Corrections (sf1.pas 18931) |
| Starfield's Earth: 11 overlays at real city coordinates via `CNAM` | verified | WP 2 (commonwealth-scale.md 2) |
| Landable custom planets are a shipped mod pattern (SFStarEditor clones STDT/PNDT/LCTN and copies the `.biom`; Pytheas, Star Wars galaxy) | verified as described | WP 2 |
| Project Tamriel (whole game world on one Starfield planet) was cancelled in days for lack of interest, not for a technical reason | verified as reported | WP 2 |
| No seasons mechanism found in the schema; FO4 has none either | supported hypothesis | WP 4 |
| Real distances rule out continuous terrain between worlds: Boston to Bar Harbor 323 km, DC to Boston 634 km, DC to Las Vegas 3,349 km | computed (inference) | MG 5 |
| Anchorage is a VR simulation, Zeta is in orbit: sealed worlds that need no planet position | verified | MG 4 (Wikipedia FO3 DLC) |
| TTW kept separate worldspaces joined by a train chokepoint with quest state; console travel breaks it | verified | MG 1; PR 1 |
| A player-side cross-engine converter that ships world, cells, landscape and placements only (FNV to FO4) is tolerated on Nexus; it dropped navmesh because it crashed | verified | PR 6; MG 2 |
| Engine ceilings: 256 active BA2s (8-bit index; SFSE "BA2 Limit Fix" raises it), 253 full-master slots, soft instability near 100 to 120 plugins; 4 GiB per archive unresolved; full-res 64-cell core needs about 8.5 GiB | verified (as published claims) / unresolved (4 GiB) | VP engine limits |
| A Starfield patch changed planet data storage (USFP 1.0.7a/b, 1.15.222) | verified | VP Starfield versions |
| Target runtime Starfield 1.16.244 + SFSE 0.2.21, Steam only; SFSE supports only the latest Steam runtime | verified | VP |

## Possibilities

### Host planet

| Option | What it gives | Cost or risk | Precedent | Label |
|---|---|---|---|---|
| Keep Mars (today) | Proven path; nothing new to build | 25 h day, 0.38 g, Mars sky and ground; not "Earth-like" | current core | verified (in use) |
| Starfield's Earth, edited | 24 h day, Sun and Moon free, real coordinates | Must override air, temperature, keywords and biomes on a quest-bearing vanilla planet; conflicts with Earth mods | Bethesda's 11 Earth overlays | supported hypothesis |
| Cloned Earth-like planet in its own system | Full control of rotation, gravity, air, biomes; can be named for the setting | Galaxy edit; early reports of new-game need and save damage; `.biom` must be copied from the user's archive | SFStarEditor, Pytheas, Star Wars galaxy | verified pattern, our use unresolved |
| Planet records in their own small master | Clean load order; later games can reuse it | One more plugin slot | none read | supported hypothesis |

### Placing overlays on the planet

| Option | What it gives | Cost or risk | Precedent | Label |
|---|---|---|---|---|
| PNDT `CNAM` override (today) | Proven on Mars | Copies the whole list; conflicts with any mod touching that planet | our core; Bethesda Earth | verified |
| PNDT `EOVR` Added | Adds an overlay without overriding `CNAM` | Engine merge behaviour across plugins unknown | none found yet | verified schema, behaviour unresolved |
| Unique surface pattern with `UniqueOverlayList` / `BGSOverlayDesignatedPlacementInfo` | A grid of standard-sized overlays in one 16 x 16-block pattern; a native way past 14 cells | Which records carry them is unknown | possibly Shattered Space | supported hypothesis |
| PCM content node pointing at a WRLD | Procedural placement | Wrong tool for fixed worlds; useful to know so POIs stay out | vanilla POIs | verified schema |
| CK "terrain cutting from a planet location grid" | Bethesda-tool route to new worldspaces | Needs the CK on the user's PC | Steam guide 3385012985 | verified as described |

### Layout and geography

| Option | What it gives | Cost or risk | Precedent | Label |
|---|---|---|---|---|
| Real coordinates (Boston about 42.4 N 71.1 W, Mount Desert Island about 44.4 N 68.2 W) | Real local-time offsets (about 12 min), credible map; about 3,800 cells apart on Earth scale, harmless | Worlds do not share one surface-map view | Bethesda Earth | supported hypothesis |
| Compact stylised layout (more than 100 cells apart) | One map view for all three | Breaks real geography | none | supported hypothesis |
| East-coast cluster at real relative positions, Mojave across the continent | Later FO3, Pitt, Point Lookout, Appalachia fit near Boston | Mojave is far: travel scene only | TTW train | supported hypothesis |

### Day, sky and weather

| Option | What it gives | Cost or risk | Label |
|---|---|---|---|
| Rotation 1.0 (24 h) | Same as Starfield's Earth; with FO4's `TimeScale` 20 a day is 72 real minutes, so nothing changes for the player | none known | supported hypothesis |
| `SetLocalTime` at the vault exit, or choose the longitude so the default start is daylight | Morning exit from Vault 111 | Bethesda uses `SetLocalTime` in `QF_MQ101` | verified use (test-queue.md) |
| One CLMT for the planet | Simple | Far Harbor fog and Glowing Sea storms need variety | supported hypothesis |
| Per-world climate via WRLD `CNAM`, BIOM `ENAM` and WTHS conditions, or REGN `RDWT` | Fog, radstorms, regional weather without new systems | Which of WRLD and BIOM wins on an overlay is unknown | supported hypothesis |
| Vanilla Earth-like WTHS/ATMO presets (Jemison, New Atlantis) | v1 sky without editing opaque blobs | Sky may still read alien | unresolved |

### Hazards, gravity, temperature

| Option | What it gives | Cost or risk | Label |
|---|---|---|---|
| Host carries "standard O2 / temperate" planet-trait keywords | No suit warnings or damage | Wrong or missing keyword shows hazards in Boston | supported hypothesis |
| WRLD `GNAM` gravity scale on our worlds | 1 g on any host | Multiply or set is unknown (2.63 on Mars if it multiplies) | unresolved |
| PNDT `FNAM` surface gravity on a cloned planet | 1 g everywhere | Only on a planet we own | verified schema |

### Sea, coasts and ground beyond the overlay

| Option | What it gives | Cost or risk | Precedent | Label |
|---|---|---|---|---|
| SFBK `WHGT` sea at 0 m inside the overlay | Boston Harbor and the Charles (55 % of core LAND cells average below 0) | Edge meets the planet's own water | our core | supported hypothesis |
| Ocean biome (`TNAM` Ocean) around Far Harbor | Sea on every side of the island | Possible visible step at the merge ring | Jemison 60 % ocean | unresolved |
| Biome map swap to our own BIOM (biom.py, article 643) | New England forest and sea on the horizon before any LOD | "Generate Biome Placements" touches every planet; launcher must write only needed records | Nexus article 643 | verified method |
| `BlockHeightAdjustment` per-block terrain and water heights | Fine sea-level control inside a pattern | Meaning only supported | none | supported hypothesis |
| Outer FO4 ring (114 vs 64 cells) as terrain, LOD, or procedural Earth biome (new option D) | Horizon | See WM section 1 for options A to C | none | supported hypothesis |

### LOD and horizon

Covered in WM section 4 (no `lodsettings`, no generated LOD, xLODGen does not list Starfield, CK or own generator).
New here only: the Earth biome around overlays (above) is a cheap horizon before LOD, and the FNV to FO4 converter
shows a world-only release can ship with rough horizon edges (PR 6).

### Map, fast travel and the ship

| Option | What it gives | Cost or risk | Precedent | Label |
|---|---|---|---|---|
| Scripted travel scene (boat, monorail, vertibird, "travel menu" activator) through one chokepoint | Full control; matches TTW | Every arrival path must run the same handler, or world-state breaks | TTW Union Station | verified precedent |
| Ship reskinned as a vertibird, native landing UI | Native fast travel between landings | Star map, grav jump, orbit view must be hidden | none | unresolved |
| Surface-map fast travel between landings without the ship | Seamless one-planet travel | Not yet known to work; playtest row 7 hang risk on the ship path | none | unresolved |
| PCM limits and WRLD `FNAM` flags ("Prevent Merge Cell Content", "Allow ProcGen") | Keep Starfield POIs out of the buffer ring | Today's flags inherited from the template, unread | vanilla | verified schema |

### Performance and budgets

| Item | Number or option | Label | Source |
|---|---|---|---|
| Exterior refs per 64 cells | about 650k, placed one by one (no precombines) | verified count; draw-call cost supported hypothesis | VP |
| Archive and plugin budget | 256 BA2s, 253 full slots, soft limit 100 to 120 plugins; plan few plugins, ESM + medium masters, few large archives | verified (published) | VP |
| Traversal stutter | SFEF ships "Reduce Traversal Stutter"; vanilla pain point | supported hypothesis | VP |
| Owner PC vs player floor | 7950X3D / 4070 Ti 12 GB / 32 GB vs 16 GB / GTX 1070 Ti; no data at the floor | verified | VP |
| Texture caps | 1024 colour / 512 normal, chosen for archive size, not VRAM | verified | VP |
| Patch exposure | Planet and worldspace overrides are the data Bethesda changed in 1.15.222 | verified precedent | VP |

### Where later games could sit

| Option | What it gives | Cost or risk | Label |
|---|---|---|---|
| Same planet, real coordinates (DC, Pittsburgh, Point Lookout, Mojave) | "One Earth" holds; planet master reused | More landings and save state; Mojave by travel scene only | supported hypothesis |
| Stylised "regions" map | Simple map | Loses real geography | supported hypothesis |
| Separate planets per game | Suits Starfield travel | Breaks the "one Earth" premise | supported hypothesis |
| Anchorage and Zeta as sealed worldspaces (Zeta could use Starfield's space engine) | No planet slot needed | Zeta-in-space is a fun option only | verified facts, option supported |

## Questions

### Host planet and planet data

**WP-01. Host: Starfield's Earth, a cloned Earth-like planet, or keep Mars?**
- Why: decides sky, sun, moon, day length, ground beyond the BTD, and mod conflicts.
- Options: (a) Earth, edited; (b) a clone in its own system (SFStarEditor pattern); (c) Mars. (WP Q3; also WM owner Q3)
- Answer by: dump of Earth's and Jemison's PNDT (`INAM`, `TEMP`, keywords, `PPBD`, `CNAM`/`EOVR`), then WP-08 result; owner decision.
- Blocks: World, Multi-game. Status: open.

**WP-02. Does a new galaxy entry (a cloned planet) need a new game, and is that acceptable?**
- Why: forum reports say new systems needed a new game and bad entries "can destroy your save"; phase 1 is a new game anyway.
- Options: accept new-game-only; host on an existing planet to avoid galaxy edits. (WP Q2)
- Answer by: install the plugin on an existing save and see if the planet appears; PC probe, then owner decision.
- Blocks: World, Release. Status: open.

**WP-03. Can the launcher generate the planet records (clone, rotation, gravity, keywords) and copy the `.biom` from the user's own archive deterministically, and is the `.biom` keyed by planet name, FormID or edid?**
- Why: no CK on the user's PC and no shipped assets; SFStarEditor renames the `.biom` by planet name.
- Options: Mutagen writer with a synthetic-fixture test; copy-and-rename like SFStarEditor. (WP Q13, Q25)
- Answer by: read SFStarEditor source (`espreadpntd.cpp`, `espreadlctn.cpp`); fixture test; offline research.
- Blocks: World, Launcher. Status: open.

**WP-04. Does the planet live in its own small master that the world plugins depend on?**
- Why: load order and reuse by FO3/NV later. (WP Q26)
- Options: planet master; planet records inside the core ESM.
- Answer by: owner decision after WP-01. Blocks: World, Launcher, Multi-game. Status: open.

**WP-05. Can SfInspect dump PNDT `ENAM`/`FNAM`/`INAM`/`TEMP`/keywords for all 1,765 planets, to pick a host by data?**
- Why: choose rotation 0.9 to 1.1, about 1 g, standard O2, temperate. (WP Q31)
- Answer by: PC read-only walker run. Blocks: World. Status: open.

**WP-06. Would hosting on Starfield's Earth conflict with vanilla Earth quests and popular Earth overhaul mods?**
- Why: whole-record PNDT override on a quest planet; Nexus release. (WP Q29)
- Options: `EOVR` to avoid `CNAM` override (WP-08); a clone instead.
- Answer by: survey of Earth-editing mods; list of vanilla quests on Earth; community research.
- Blocks: World, Release. Status: open.

**WP-07. Is a custom star system a release liability for saves (removing it later)?**
- Why: removing a galaxy-edit mod may break saves. (WP Q30)
- Answer by: SFStarEditor and Pytheas comment threads; community research. Blocks: Release. Status: open.

### Overlays and worldspaces

**WP-08. Can a plugin add our overlays through PNDT `EOVR` (Added) instead of overriding `CNAM`?**
- Why: conflict-free registration on any host. (WP Q4; extends WM 2)
- Answer by: find vanilla or DLC uses of `EOVR` (ShatteredSpace.esm, SFBGS00x) offline, then one terrain-only overlay registered by `EOVR` alone; PC probe.
- Blocks: World, Multi-game. Status: open.

**WP-09. How did Bethesda build Shattered Space's handmade landmass: one big overlay, several, or a unique surface pattern?**
- Why: the closest vanilla model of a large handmade region. (WP Q5)
- Answer by: read the DLC esm (SFBK sizes, WRLDs, PNDT `CNAM`/`EOVR`, SFPT components); PC read-only walker.
- Blocks: World. Status: open.

**WP-10. What do `UniqueOverlayList`, `UniquePatternPlacementInfo` and `BGSOverlayDesignatedPlacementInfo` do, and on which records?**
- Why: a grid of overlays in one pattern might give seamless 12-cell-pitch tiles and an official multi-overlay path. (WP Q6)
- Answer by: census of DAT2 components by record type in Starfield.esm; offline (PC read-only).
- Blocks: World. Status: open.

**WP-11. One overlay per DLC world, or a grid of smaller overlays, and do TTW's separate worldspaces apply?**
- Why: Far Harbor is about 18 x 18 cells and Nuka-World about 14 (community size, unverified); one overlay each fits the proven path. TTW kept separate worldspaces joined by travel. (WP Q15; also PR Q14)
- Answer by: DLC census after the owner installs the DLC (WM step 2); WP-09/10 results.
- Blocks: World. Status: open.

**WP-12. Do border-unlock settings (`bBorderRegionsEnabled`, "Remove Planetary Tile Boundary") interfere with our landings?**
- Why: users may run those mods; authors report crashes past the edge. (WP Q24)
- Answer by: compatibility test; PC probe, community contact. Blocks: Release. Status: open.

**WP-13. Can the Planet Content Manager be told to place nothing on our worlds?**
- Why: Starfield POIs in the outer ring (about 18 cells per side) of a landing; the 10-cell safe zone covers only the overlay. (WP Q20, section 6)
- Options: no PCM conditions matching our planet's keywords; WRLD `FNAM` flags; per-planet limit 0.
- Answer by: xEdit read of our WRLD flags offline; walk the landing edge and count POIs; PC probe.
- Blocks: World. Status: open.

### Geography and layout

**WP-14. Real geography or a compact layout for the worlds?**
- Why: real lat/long gives real local-time offsets and a credible map; compact keeps one map view. (WP Q7; also MG Q11)
- Options: real coordinates; stylised layout over 100 cells apart.
- Answer by: owner decision. Blocks: World, Multi-game. Status: open.

**WP-15. Where is Nuka-World on the planet?**
- Why: FO4 reaches it by monorail; its real-world position was not in the sources read. (WP Q8)
- Options: a fictional inland site west of Boston; the lore location if FO4 data or game text gives one.
- Answer by: offline research (FO4 data and lore), then owner decision. Blocks: World. Status: open.

**WP-16. Do we keep FO4's unplayable outer ring (114 vs 64 cells) as terrain, LOD, or a procedural Earth biome?**
- Why: the horizon. WM section 1 has options A to C; new option D is an Earth biome (cheap). (WP Q16)
- Answer by: owner decision after WP-25. Blocks: World. Status: open.

**WP-17. Does the host's `KNAM` "Terrain Max Height" or biome noise shape the merge ring around a 64-cell overlay?**
- Why: cliffs at the overlay edge. (WP Q17)
- Answer by: compare edge heights on hosts with different `KNAM`; PC probe. Blocks: World. Status: open.

### Day, night, sky and weather

**WP-18. Which day length: a real 24 h (rotation 1.0) or something else?**
- Why: with FO4's `TimeScale` 20 a 24 h day is 72 real minutes, the same as Starfield's Earth. (WP Q11)
- Answer by: compare `Planet.GetDayLength()` in game with the `ENAM` formula; PC probe, then owner decision.
- Blocks: World. Status: open.

**WP-19. What local time does a new game give at the Vault 111 exit, and how do we make it morning?**
- Why: local time depends on lat/long plus the save's universal time. (WP Q1; cross-cutting with newgame.md)
- Options: `SetLocalTime` at the vault exit (Bethesda's `QF_MQ101`); choose the registration longitude.
- Answer by: one fresh-start run reading local time at the core; PC probe. Blocks: New game, World. Status: open.

**WP-20. Weather per world: one planet CLMT, or per-world climates via WRLD `CNAM`, BIOM `ENAM` and WTHS conditions?**
- Why: Far Harbor's fog and the Glowing Sea's radstorms. (WP Q18)
- Answer by: one `fw` test each to see whether WRLD `CNAM` or BIOM `ENAM` wins on an overlay; PC probe.
- Blocks: World. Status: open.

**WP-21. Which vanilla WTHS/ATMO set reads most Earth-like (clear, overcast, rain, fog)?**
- Why: the v1 sky; WTHS/ATMO/CLDF are opaque reflection blobs, so only vanilla presets can be referenced. (WP Q19)
- Answer by: the runner's sky_light script over Jemison and New Atlantis weathers; PC probe. Blocks: World. Status: open.

**WP-22. Is the Glowing Sea a separate biome or climate inside the Commonwealth overlay?**
- Why: its radstorm weather and colour. (WP Q34)
- Options: REGN weather (Starfield keeps REGN `RDWT`); WTHS conditions.
- Answer by: offline record read, then PC probe. Blocks: World, Fallout systems. Status: open.

### Hazards, gravity and temperature

**WP-23. Does WRLD `GNAM` gravity scale multiply the planet's gravity or replace it?**
- Why: 1 g in the Commonwealth on any host. (WP Q9)
- Answer by: set `GNAM` 2.63 on a Mars overlay and read `GetPlayerGravityScale` or jump height; PC probe.
- Blocks: World. Status: open.

**WP-24. Which planet-trait keywords stop hazards and suit warnings?**
- Why: no oxygen or temperature damage in Boston. (WP Q10)
- Answer by: list the keywords that `BodyIsAtmosphereType`/`BodyIsTemperatureType` test in Starfield.esm and the ones Jemison carries; offline.
- Blocks: World. Status: open.

### Sea, coasts and ground beyond the overlay

**WP-25. Can the procedural ground outside our BTDs be made New England-like by a biome map edit?**
- Why: horizon without LOD, and the buffer ring. (WP Q12)
- Options: biom.py swap to our BIOM (article 643); clone Jemison's forest biomes.
- Answer by: one biome swap on the host and a look from the core's edge; offline build plus PC look.
- Blocks: World. Status: open.

**WP-26. Overlay sea vs planet ocean: does SFBK `WHGT` plus BIOM water give a seamless coast?**
- Why: Far Harbor (sea on every side), Boston Harbor, the Charles. (WP Q14)
- Answer by: a terrain-only island overlay at 0 m water inside an Ocean biome; look at the merge ring; PC probe.
- Blocks: World. Status: open.

### Map, fast travel and the ship

**WP-27. The ship: fenced out completely, or kept as a disguised fast-travel vehicle (a vertibird skin)?**
- Why: between landings Starfield's native path is the ship. (WP Q21)
- Options: scripted boat or monorail (vehicles-and-travel.md); ship reskinned with the native landing UI.
- Answer by: owner decision, informed by WP-28 and WP-29. Blocks: World, Fallout systems. Status: open.

**WP-28. Does the surface map show, and fast travel to, markers of another landing on the same planet without the ship?**
- Why: one-planet fast travel between worlds. (WP Q22; also MG Q12; already listed in vehicles-and-travel.md, gains weight here)
- Answer by: two terrain-only landings and one map look; PC probe. Blocks: World, Multi-game. Status: open.

**WP-29. How do we hide the star map, grav jump and orbit view on an Earth-like host?**
- Why: opening the star map in Boston breaks the setting. (WP Q23)
- Options: menu blocks by script; SFSE only if needed (unresolved).
- Answer by: offline research. Blocks: World, Fallout systems. Status: open.

**WP-30. Does every route into a world (travel scene, fast travel, `coc`, our test teleports) run one arrival handler that sets world-state?**
- Why: TTW's FAQ warns that console travel bypasses the variables its train sets. (MG precedent 3, MG Q12)
- Options: one arrival quest per world called from all paths; test harness calls it after `coc`.
- Answer by: design review plus one route-run test; offline design, then PC. Blocks: World, People and story, Multi-game. Status: open.

### Performance and budgets

**WP-31. What does a landing or fast travel into a 64-cell overlay with about 648k refs cost in load time and memory?**
- Why: three such worlds, more later. (WP Q27)
- Answer by: timed `coc` and first-frame times, memory at the core; numbers to docs/ai/optimization.md; PC probe.
- Blocks: World, Release. Status: open.

**WP-32. Does a heavier Earth-like atmosphere (fog volumes, clouds) change frame time over the dense core?** (WP Q28)
- Answer by: frame time with Mars vs an Earth-like weather on the same route; PC probe. Blocks: World. Status: open.

**WP-33. Does an exterior with 650k+ individually placed refs stream without traversal stutter?**
- Why: no precombines on our side; SFEF's stutter fix exists because vanilla stutters. (VP Q18)
- Answer by: frame-time capture on a walking route over core64 (the route runner exists); PC probe.
- Blocks: World, Release. Status: open.

**WP-34. How many BA2 archives and plugin slots will the full world use, and does it need the BA2 Limit Fix?**
- Why: 256 archives and 253 full slots are shared with the player's mods. (VP Q17)
- Options: one ESM + 1 to 3 archives for the core; medium masters for DLC areas.
- Answer by: archive count with Starfield Engine Fixes' counter on the owner's PC; PC probe. Blocks: World, Launcher, Release. Status: open.

**WP-35. After each Starfield patch, do the planet and worldspace overrides still hold?**
- Why: 1.15.222 changed planet data storage (USFP). (VP Q19)
- Answer by: scripted record diff of overridden records against each new Starfield.esm; offline tooling.
- Blocks: World, Release. Status: open.

**WP-36. What texture caps should the default world build use per VRAM tier?**
- Why: current caps were chosen for archive size, not VRAM. (VP Q20)
- Options: three presets keyed to detected VRAM.
- Answer by: VRAM use at each cap on an 8 GB card; PC probe on lower-end hardware (community). Blocks: World, Launcher. Status: open.

**WP-37. Can the runner read local time, gravity and hazard state in one probe, as an acceptance step per world?** (WP Q32)
- Answer by: PC runner design. Blocks: World. Status: open.

### Release scope and later games

**WP-38. Should a "walkable world" release (world, placements, landscape, no people) ship before people and story?**
- Why: FNV to FO4 shipped exactly that scope and has an audience on Nexus. (PR Q15)
- Answer by: owner decision. Blocks: Release, World. Status: open.

**WP-39. FO3 and New Vegas later: the same planet at other coordinates (DC, Mojave), a stylised map, or other planets?**
- Why: decides whether the planet master is "Earth" generically. (WP Q33; MG Q11)
- Answer by: owner decision after WP-01 and WP-14. Blocks: Multi-game. Status: open.

**WP-40. Are Anchorage and Zeta sealed worldspaces with no planet position, and could Zeta use Starfield's space engine?**
- Why: fewer landings; a fun option. (MG Q13)
- Answer by: owner decision; offline research. Blocks: Multi-game. Status: open (facts verified, choice open).

**WP-41. What weather and climate model do the DC and Mojave landings use (FO3 green tint, NV desert)?** (MG Q14)
- Answer by: map FO3/NV CLMT/WTHR onto Starfield biomes and weather; offline research. Blocks: Multi-game. Status: open.

**WP-42. How many landings, plugins and loaded worlds can one save carry before performance or plugin limits bite?**
- Why: FO4 + FO3 + NV + 11 DLC is about 15 source masters' worth of content. (MG Q15; ties to WP-34)
- Answer by: PC stress test with terrain-only landings. Blocks: Multi-game, Release. Status: open.

## Owner decisions in this area

- **WP-01 host planet.** Recommendation: keep Mars until WP-05, WP-08 and WP-24 report; then prefer Earth via `EOVR`
  if `EOVR` works (Sun, Moon, 24 h for free, no galaxy edit), otherwise a clone in its own small master.
- **WP-02 new-game-only for a cloned planet.** Recommendation: acceptable, since phase 1 is a new game anyway.
- **WP-04 planet master.** Recommendation: its own small master, so later games reuse it.
- **WP-14 layout.** Recommendation: real coordinates; placement math is the same `CNAM` path and the offsets are harmless.
- **WP-15 Nuka-World site.** Recommendation: decide after offline lore research; default a fictional inland site.
- **WP-16 outer ring.** Recommendation: option D (Earth biome) first as the cheap horizon; terrain or LOD later (breadth before polish).
- **WP-18 day length.** Recommendation: rotation 1.0 (24 h); it matches FO4's feel at `TimeScale` 20.
- **WP-27 ship.** Recommendation: fence the ship out for v1 and use scripted travel through one chokepoint (TTW model, avoids the playtest row 7 hang).
- **WP-38 world-only release.** Recommendation: yes, as an early public demo; Project Tamriel shows interest needs a demo early.
- **WP-39 later games.** Recommendation: same planet, real coordinates, so the planet master is reused; Anchorage and Zeta sealed (WP-40).

## Cheapest experiments

Offline first:
1. **Planet and component census (xEdit or SfInspect read of Starfield.esm, ShatteredSpace.esm, SFBGS00x):** Earth and
   Jemison PNDT fields and keywords, all `EOVR` uses, DAT2 unique-pattern components by record type, keywords tested
   by the hazard conditions, our WRLD `FNAM` flags. Closes WP-05, WP-09, WP-10, WP-24; feeds WP-01, WP-08, WP-13.
2. **Read SFStarEditor source** for `.biom` keying and records written. Closes WP-03 (design half); feeds WP-02.
3. **Record diff of overridden planet and worldspace records across Starfield 1.16.236, .242, .244.** Closes WP-35.
4. **FO4 data read for Nuka-World's position and the Glowing Sea's weather records.** Feeds WP-15, WP-22.

PC read-only or terrain-only probes:
5. **One terrain-only island overlay at a second lat/long**, registered by `EOVR` alone, with `GNAM` 2.63, 0 m water in
   an Ocean biome, and one map marker. Closes WP-08, WP-23, WP-26, WP-17 (edge look), WP-28 (map look) and measures the
   second merge offset (WM 5).
6. **Fresh start, read local time and `GetDayLength()` at the core.** Closes WP-18, WP-19.
7. **Weather `fw` tests on an overlay plus sky_light over Jemison/New Atlantis presets.** Closes WP-20, WP-21; feeds WP-22, WP-32.
8. **Timed `coc` into core64, frame-time walk on the route runner, SFEF archive counter.** Closes WP-31, WP-33, WP-34; feeds WP-32, WP-42.
9. **Install a cloned-planet plugin on an existing save.** Closes WP-02; feeds WP-07.

## Gaps for wave 2

- Two unread Planet Content Manager POI tutorials (HTTP 429): Nexus forum topic 13491382 and Steam guide 3266682879. Read them for WP-13.
- Shattered Space's landmass size and build method (only a quote read). Feeds WP-09.
- Nuka-World's lore or real-world location. Feeds WP-15.
- Survey of Earth-editing Starfield mods. Feeds WP-06.
- SFStarEditor and Pytheas comment threads on save safety. Feeds WP-02, WP-07.
- Starfield draw-call budget, reference streaming and any precombine/previs equivalent (no primary source found). Feeds WP-33.
- Starfield total conversions on Nexus (not researched). Feeds WP-38.
- Engine merge of `EOVR` across several plugins (no source). Feeds WP-08.
- How TTW structures its worldspaces in detail (only "separate worldspaces plus a train" read). Feeds WP-11.

## Handed to phase files

| Question | Target file |
|---|---|
| Which game does a multi-game playthrough start in, and must phase 1 have a "start world" hook? (MG Q1, Q3) | newgame.md |
| Local time at the Vault 111 exit (kept here as WP-19, cross-cutting) | newgame.md |
| Do FO3/NV load doors need the same enter/exit treatment; DOOR/XTEL compatibility (MG Q4) | door-animations.md |
| Can the interior pipeline take FO3/NV cells; navmesh regenerate vs convert (MG Q5, PR Q5) | interiors.md |
| Disk space check, Creation Kit requirement for LOD, archive packing (VP Q15; WM owner Q4) | launcher.md |
| Arrival scripts and save state across worlds, game-time handling (WP-30 is the world side) | engine-mechanics.md |

## Sources

- xEdit Starfield definitions, `Core/wbDefinitionsSF1.pas` dev-4.1.6: https://github.com/TES5Edit/TES5Edit
- https://www.nexusmods.com/starfield/mods/11384
- https://github.com/tridashafox/SFStarEditor
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
- https://nukesdragons.com/starfield/db/planets/jemison
- https://starfieldwiki.net/wiki/Starfield:Jemison
- Unread (HTTP 429): https://forums.nexusmods.com/topic/13491382-tutorial-creating-your-own-randomly-placed-pois/ ,
  https://steamcommunity.com/sharedfiles/filedetails/?id=3266682879
- https://thebestoftimes.moddinglinked.com/faq.html
- https://fallout.wiki/wiki/Mod:Tale_of_Two_Wastelands
- https://nexusmods.com/fallout4/mods/75425
- https://github.com/terry-haire/fnv-to-fo4
- https://en.wikipedia.org/wiki/Fallout_3_downloadable_content
- https://www.nexusmods.com/starfield/mods/17936
- https://forums.nexusmods.com/topic/13518743-crash-issue-too-many-ba2-files-causing-ctds-%E2%80%93-looking-for-fix-or-insight/
- https://www.nexusmods.com/starfield/articles/688
- https://www.nexusmods.com/starfield/mods/10457?tab=files
- https://www.afkmods.com/Unofficial%20Starfield%20Patch%20Version%20History.html
- https://starfieldwiki.net/wiki/Starfield:System_Requirements
- https://sfse.silverlock.org/
- Project notes: research/next-phase/world-maps-lod-fasttravel.md, trees-grass-terrain.md;
  research/engine-mechanics/weather-time-climate.md, vehicles-and-travel.md; repo docs/terrain/commonwealth-scale.md,
  docs/terrain/core64c.md, docs/ai/test-queue.md, docs/ai/optimization.md, docs/ai/decisions.md (2026-10-12)
