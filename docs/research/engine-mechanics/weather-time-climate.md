# Weather, time and climate (FO4 CE1 vs Starfield CE2)

Part of the engine-mechanics reference ([index](README.md)). Author: Claude-cloud, 2026-10-19. Labels: verified /
supported hypothesis / unresolved.

Read with [../next-phase/lighting.md](../next-phase/lighting.md) (cell lighting, image spaces, host planet) and
[../next-phase/world-maps-lod-fasttravel.md](../next-phase/world-maps-lod-fasttravel.md) (overlay worldspaces on a
planet). This file adds the record mechanics behind them.

## In short
- **FO4**: a worldspace (WRLD CNAM) or region (REGN RDWT) names a climate (CLMT); the climate holds a weighted weather
  list and sunrise/sunset timing; each weather (WTHR) holds cloud texture layers, colours for 8 times of day, fog,
  precipitation, lightning, sounds, image spaces and spells. The clock is global (`GameHour`, `TimeScale`).
- **Starfield**: the same WTHR/CLMT records exist, but Starfield.esm has only **3 WTHR** against **181 WTHS**
  (Weather Settings) and 594 ATMO; the climate gained a WSLT list of WTHS; planets (PNDT) carry rotation, atmosphere
  and biomes; biomes (BIOM) name the climate, ambience and music (**verified**, counts + xEdit). WTHS, ATMO, SUNP,
  CLDF, FOGV and TODD are opaque "reflection" blobs in xEdit (**verified**: `REFL`/`RDIF` only).
- Time is per planet: one universal clock (`GameHour`, `TimeScale` 20) plus a local time from the planet's rotation
  (**verified** globals; day-length formula **supported hypothesis**, docs/ai/test-queue.md).
- **Port verdict**: FO4 WTHR/CLMT **translate** as data for precipitation, lightning, wind, sounds and keywords, but the
  sky look (clouds, sky colours) belongs to WTHS/ATMO/CLDF, which we can only **reuse** from vanilla until the
  reflection format is decoded or CK2 authors them. "One Earth-like planet with real days" = a host PNDT with a
  ~24 h rotation and breathable-looking atmosphere, plus our CLMT/BIOM weather lists.

## How Fallout 4 does it

### Records (verified: xEdit wbDefinitionsFO4.pas / wbDefinitionsCommon.pas; counts fo4_esm.json)
| Record | Count | Key fields |
|---|---|---|
| CLMT Climate | 7 | WLST weathers (WTHR, chance, optional GLOB), FNAM sun texture, GNAM sun glare texture, model, TNAM timing: sunrise begin/end, sunset begin/end (u8 in 10-minute steps, 144 per day), volatility, moons/phase length |
| WTHR Weather | 71 | cloud layer textures (`00TX`..`D0TX` sampled; up to 32 layers), LNAM max cloud layers, MNAM precipitation (SPGD), NNAM visual effect (RFCT), RNAM/QNAM cloud speeds, PNAM cloud colours, JNAM cloud alphas, NAM0 weather colours, FNAM fog distances, DATA, NAM1 disabled cloud layers, SNAM sounds, TNAM sky statics, IMSP image spaces, WGDR god rays, DALC directional ambient, GNAM sun glare lens flare (LENS), UNAM magic, VNAM volatility mult, WNAM visibility mult |
| WTHR DATA | | wind speed, sun glare, precipitation fade in/out, thunder/lightning fade in/out and frequency, flags (Pleasant, Cloudy, Rainy, Snow, aurora flags), lightning colour, visual effect begin/end, wind direction + range, turbulence |
| WTHR NAM0 colours | | sky-upper, fog near, ambient, sunlight, sun, stars, sky-lower, horizon, clouds-upper, effect lighting, cloud LOD, fog far, sky statics, water multiplier, sun/moon glare, fog near/far high, each for Sunrise, Day, Sunset, Night, Early/Late Sunrise, Early/Late Sunset (8 slots from form version 111) |
| WTHR SNAM | | sound (SNDR/SOUN) typed Default / Precipitation / Wind / Thunder |
| WTHR UNAM Magic | | lightning-strike spell + threshold, weather-activate spell + threshold |
| IMGS / IMAD | 293 / 247 | image spaces and adapters (per time of day via IMSP) |
| LGTM | 66 | lighting templates; WRLD LTMP names one for the world's interiors-style lighting (see lighting note) |
| REGN | 106 | region data incl. RDWT weather list (overrides the climate inside the region) |
| WRLD CNAM | | climate per worldspace |

Sampled FO4 WTHR (all 71): TNAM rows 1,908, DALC 552, cloud textures present in 56 (fo4_esm.json): **verified**.

### Behaviour (supported hypothesis unless marked)
- Radstorms and the Glowing Sea are weathers; their radiation and lightning come through the UNAM spells and the
  precipitation/visual-effect fields. Which exact spells: **unresolved** here (an xEdit look).
- Weather choice: every few game hours the climate rolls its weighted list; regions override; Papyrus
  Weather script functions (`ForceActive`, `SetActive`, `ReleaseOverride`; names from the FO4 CK wiki, to grep in
  FO4 sources) and console `fw`/`sw` force one.
- Time: globals `GameHour`, `GameDaysPassed`, `TimeScale` (default 20: 1 real minute = 20 game minutes). Sun and
  moons move from CLMT timing; there is one sun and one sky per worldspace.

## How Starfield does it

### Records (verified: xEdit wbDefinitionsSF1.pas; counts sf_esm.json)
| Record | Count | Fields / change from FO4 |
|---|---|---|
| WTHR | 3 | same LNAM, MNAM, cloud speeds/colours/alphas, NAM0, NAM4, FNAM, DATA, NAM1, TNAM, IMSP, DALC, GNAM, UNAM, VNAM, WNAM; **adds** KWDA keywords, CLDC cloud type (CLDF), HNAM volumetric lighting (VOLI per time of day), WSLS/WSLD sound references; **drops** cloud texture paths; NNAM visual effect now ARTO; DATA adds Trans Delta and Sun Damage; flags add Rain Occlusion, HUD Rain Effects |
| Vanilla WTHR | | `DefaultWeather` 0000015E, `SpaceWeather` 00249FA6, `NewAtlantisWeather50` 0027CF9B (**verified** raw scan, test-queue.md) |
| CLMT | 47 | WLST weathers + **WSLT weather settings** (WTHS, chance, GLOB) + TNAM timing without moons/phase |
| WTHS Weather Settings (new) | 181 | REFL reflection data, RFDP parent, RDIF diff, conditions |
| ATMO Atmosphere (new) | 594 | REFL + RFDP parent + RDIF |
| SUNP Sun Preset (new) | 52 | REFL + RFDP + RDIF; named by STDT star PNAM |
| CLDF Clouds (new) | 16 | REFL |
| FOGV Fog Volume (new) | 73 | REFL |
| TODD Time of Day Data (new) | 14 | REFL; named by STDT HNAM and BIOM NAM0 |
| BIOM Biome | 431 | ENAM climate, BIAS ambience set, BIMT music type, NAM0 time-of-day data, water, flora, terrain, colours |
| PNDT Planet | 1,765 | CNAM master worldspaces at lat/long, PPBD biomes with chance, ENAM orbital data (axial tilt, rotational velocity, ...), GNAM galaxy data, HNAM catalogue data (year length in days), INAM atmosphere data (ATMO, density, Rayleigh and Mie scattering), TEMP temperature |
| STDT Star | 123 | SNAM binary star, PNAM sun preset, HNAM time-of-day data |
| WRLD | | CNAM climate (default 351), parent flag "Use Climate Data" |
| IMGS / IMAD / LGTM / REGN | 232 / 190 / 6 / 4 | kept, far fewer templates and regions |

The `REFL` blobs are Bethesda's reflection-serialised component data: their field layout is **unresolved** in xEdit
(shown as raw), so WTHS/ATMO/SUNP/CLDF/TODD values cannot yet be generated by our writer.

### Behaviour
- Clock (**verified**, test-queue.md): Starfield.esm globals `GameYear` 330, `GameMonth` 5, `GameDay` 7, `GameHour` 8.0,
  `GameDaysPassed` 0, `TimeScale` 20; settings `fCalendarTimeScaleGround` / `fCalendarTimeScaleSpace`.
- Local time (**supported hypothesis**): PNDT `RotationalVelocity` is rotations per 24 h: Earth 1 (24 h), Mars 0.96
  (25 h), Akila 0.857 (28 h), Jemison 0.48 (50 h); `Game.SetLocalTime(h)` rotates the planet (Bethesda's
  `QF_MQ101_00003448.psc` calls it). `GameHour` is universal and drifts from local time off Earth.
- Console (**verified** decoded entries): `ForceWeather`/`fw`, `SetWeather`/`sw`, `ReleaseWeatherOverride`/`rwo`,
  `PassTime`, `SetLocalTime` (only on a planet).
- How a planet surface picks its weather: BIOM ENAM climate, then CLMT WSLT weather settings, is the
  **supported hypothesis** from the schema; in-game confirmation **unresolved** (the Mars runs never set a weather).

## Mapping for the port
| FO4 piece | Starfield counterpart | Verdict | Notes |
|---|---|---|---|
| CLMT WLST | CLMT WLST (+ WSLT) | translate | weights and globals carry; add a WSLT entry per weather family pointing at a vanilla WTHS |
| CLMT sunrise/sunset timing | CLMT TNAM + planet rotation | translate | timing format matches; moons/phase dropped |
| CLMT sun textures | SUNP / STDT | drop | sun comes from the host star |
| WTHR precipitation, lightning, wind, flags | WTHR DATA/MNAM | translate | SPGD precipitation shaders must convert too |
| WTHR cloud textures, sky colours | CLDF + ATMO + WTHS | reuse vanilla | REFL format unresolved; choose nearest vanilla set per family |
| WTHR sounds | WTHR WSLS/WSLD | rebuild | Wwise events (see [radio-music-sound.md](radio-music-sound.md)) |
| WTHR image spaces (IMSP) | WTHR IMSP | translate / reuse | physically based exposure: pick vanilla IMGS (lighting note) |
| WTHR UNAM spells (radstorm) | WTHR UNAM | translate | spells and rads are a Fallout system |
| WTHR visual effect (RFCT) | NNAM (ARTO) | translate | RFCT is FO4-only; map to an ARTO |
| REGN RDWT | REGN RDWT / BIOM | translate | Starfield uses 4 REGN only; biomes are the native path |
| WRLD CNAM | WRLD CNAM + parent flags | data copy | our overlay must not inherit Mars's climate (check "Use Climate Data") |
| `GameHour` / `TimeScale` | same globals | carries | real days need a host planet with rotation 1.0 |
| Commonwealth, Far Harbor, Nuka-World on one planet | one PNDT, several CNAM worldspaces, one BIOM per world | rebuild (plugin) | settled decision |

## What must be rebuilt, and what needs SFSE or the Creation Kit
- **Host planet**: either reuse a vanilla planet with rotation ~1.0 and an Earth-like ATMO, or add our own PNDT.
  Earth itself has rotation 1 but Starfield's Earth is airless (lore; its ATMO **unresolved**). Adding a new PNDT
  touches the galaxy data (GNAM star system) and is **unresolved** as plugin-only work.
- **Sky look**: new WTHS/ATMO/CLDF need the REFL format or **CK2** authoring. Breadth path: reference vanilla ones.
- **Radstorm**: our WTHR + UNAM spell + Geiger sound; the rad gameplay is the Fallout-systems phase.
- No SFSE need is known; Papyrus `SetLocalTime` and `ForceWeather` cover tests.

## Port status and links
- Today the overlay copies LC172World (Mars): Mars sky, 25 h day, Mars night (lighting note section 1, **verified**).
- Runner can force time and weather and judge sky light (`scripts/game/sky_light.py`, docs/ai/test-queue.md).
- Plan: [../next-phase/lighting.md](../next-phase/lighting.md) steps 4-5 (host planet, weather families);
  overlays and landings: [../next-phase/world-maps-lod-fasttravel.md](../next-phase/world-maps-lod-fasttravel.md).

## Open questions and cheap checks
- Planet survey: SfInspect over PNDT listing rotational velocity, INAM ATMO, TEMP, biome climates; pick rotation 0.9-1.1
  with thick air (PC, read-only).
- Which CLMT/WSLT does LC172World's biome use? Follow BIOM ENAM from Mars's PPBD (SfInspect).
- Decode one WTHS REFL blob: compare two WTHS that differ by one parent (RFDP) field in a hex diff.
- FO4 weather families: list all 71 WTHR edids with DATA flags and climates (Fo4Export, read-only).
- Radstorm spells: read the UNAM of FO4's radstorm WTHR (xEdit, PC).
- Does `ForceWeather` with one of our WTHR records change the sky over the overlay? One runner step.

## Sources
- Repo: docs/measurements/fo4_esm.json, sf_esm.json; docs/ai/test-queue.md (globals, rotation, console entries,
  WTHR ids); next-phase lighting and world-maps notes.
- xEdit (TES5Edit dev-4.1.6): `Core/wbDefinitionsFO4.pas`, `Core/wbDefinitionsSF1.pas`, `Core/wbDefinitionsCommon.pas`
  (`wbClimateTiming`, `wbClmtTime`, `wbWeather*`), https://github.com/TES5Edit/TES5Edit
- [CK wiki (Skyrim): ForceWeather](https://ck.uesp.net/wiki/ForceWeather) (earlier-game syntax)
