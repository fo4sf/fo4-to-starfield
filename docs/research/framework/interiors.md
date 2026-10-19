# Interiors: research framework (phase 3, "all interiors")

Owner: the "Convert all interiors" thread (Claude-cloud). Started 2026-10-19 17:45Z. Status: **first pass done (7 agents)**. Labels: **verified** (read from a file or command we ran), **supported** (sourced, not yet tested
here), **unresolved**. Sources are linked inline. The index of every phase's framework is this folder's README.md
(owned by the "Next-phase research framework" thread).

Where we are (verified, docs/terrain/interior-batches.md on PR #396): 1,194 interiors in Fallout4.esm, 271 behind a
load door, 16 in the installed port; batches 0 to 4 built offline (104 interiors staged, ids kept); Automatron adds 2
(batch 10). Batches 5 to 9 wait for disk space. New interiors are reachable by `coc` only until a core is rebuilt
with their outside doors.

**Count reconciliation (verified, 2026-10-19 from docs/terrain/data/interior-census.json and interior-backlog.json): 271 and 230 are both right.** The backlog's 230 counts only interiors behind the Commonwealth worldspace's exterior load doors: 203 (13 already in the port, 190 to do) plus 27 second-hop interiors behind those (1 in the port). The census's 271 adds the 41 interiors entered from the separate Diamond City and Goodneighbor worldspaces. That is 33 in Diamond City and 6 in Goodneighbor still to do, plus DmndValentines01 and GoodneighborHotelRexford, which are already in the port. Check: 190 + 26 + 39 still to do + 16 in the port = 271. The batch plan converts 251 of the 255 still to do; 4 are left out because their doors' bases have no model in this Fallout4.esm (one of them is the Creation Club cell ccTOSFO4002Interior01). Automatron adds 2, making 253 across 10 batches.

Sections (filled as agents return):
1. Starfield's engine and interiors (cells, size limits, occlusion, previs, performance)
2. Navmesh and AI in converted interiors
3. Lighting, imagespace, sound and atmosphere
4. Doors, locations, map markers, fast travel
5. Content inside: containers, loot, terminals, notes, traps, NPCs, quests
6. Tools and pipelines (Creation Kit, xEdit, Mutagen, Spriggit, NIF and BA2 tools)
7. Prior art and modding communities (ports, total conversions, rules on ported assets)
8. The framework of questions (by phase step, each with what answers it)

---

## 1. Starfield's engine and interiors

Evidence base: very little is published on Starfield's internals; the strongest sources are the two schema
definitions our tools share (xEdit wbDefinitionsSF1/FO4.pas dev-4.1.6, Mutagen dev Cell.xml / PlacedObject.xml).
"verified (schema)" below means both agree on the plugin format, not on runtime behaviour.

- **Plugin types** (**verified**, [Nexus news 14993](https://nexusmods.com/news/14993),
  [Nexus article 688](https://www.nexusmods.com/starfield/articles/688)): full masters (~16.7 M records, 253 slots),
  medium (65,535 records, shared slot FD), small (4,095, slot FE); changing a released plugin's type breaks its
  dependents. FO4Port.esm at ~600,000 records must stay a full master (PluginSpike sets only the Master flag,
  dotnet/PluginSpike/Program.cs:33) and must never change type after release. Overrides may cost extra slots
  (**supported**). SF1Edit saved only full ESMs early on ([Nexus](https://www.nexusmods.com/hellpoint/news/14888)).
- **No precombines or previs** (**verified, schema**): FO4 CELL's VISI/RVIS/PCMB/XPRI/XCRI and precombine levels do
  not exist in Starfield's CELL; what remains is a "No Pre Vis" record flag and an XCLL Interior Type (Interior, Ship
  Cell, Space Cell, PackIn, Instanceable Interior). That Starfield has no previs system at all is **supported**
  ([Nexus forum](https://forums.nexusmods.com/topic/13346328-experienced-modders-can-this-game-be-fixed/page/2/), low-medium
  confidence). So nothing needs generating, but every FO4 reference becomes its own draw: the Mechanist's Lair hands
  the engine ~28,000 objects. No source gives a per-cell budget (**unresolved**).
- **No authored occlusion** (**verified, schema**): Starfield REFRs have no room portal / room links / occlusion plane /
  portal / multibound data, only XPRM primitives. FO4 roombounds and portals cannot carry over as records; how
  Starfield culls interiors is **unresolved**.
- **Packins vs static collections** (**verified, schema**): a PKIN points at a storage CELL whose refs are its
  content (flags Instanced, Instanced Static); it is not a renamed SCOL. SCOL still exists in Starfield with the FO4
  shape; whether Starfield.esm uses or renders SCOLs is **unresolved** (our converter merges SCOLs into statics).
- **Limits and crashes** (**supported**): runtime ref IDs are not recycled
  ([forum](https://forums.nexusmods.com/topic/13461079-game-crashes-when-trying-to-enter-huge-ships/)); Starfield Engine Fixes
  adds a low-reference-handle warning, a BA2 counter and a file-handle limit raise
  ([mod 10457](https://www.nexusmods.com/starfield/mods/10457)), so such limits exist, numbers **unresolved**; plugins
  made outside the CK can crash the CK while xEdit reports clean
  ([forum](https://forums.nexusmods.com/topic/13493071-starfield-ck-crashing-when-opening-specific-sf1edit-create-mod)).
  The wikis say nothing on interior size, reference counts or attach/detach (**unresolved**).

## 2. Navmesh and AI in converted interiors

Builds on docs/actors/npc-navigation.md, navmesh-conversion.md and navmesh-losses.md (NVNM v15 vs v17 byte layout,
the CK switches `-UpdateNavmeshGeneration` / `-FinalizeNavmeshes`, the exterior converter src/fo4sf/navmesh.py).

Findings:
- **verified** (interior-census.json): 272 of the 273 door-reachable interiors carry FO4 NAVM (517 NAVM, at most 35 in
  one cell; only RelayTowerInt17 has none). Converting FO4 navmesh is the default route, not generating it.
- **verified** (xEdit [wbDefinitionsSF1.pas](https://raw.githubusercontent.com/TES5Edit/TES5Edit/dev-4.1.6/Core/wbDefinitionsSF1.pas),
  [wbDefinitionsFO4.pas](https://raw.githubusercontent.com/TES5Edit/TES5Edit/dev-4.1.6/Core/wbDefinitionsFO4.pas)):
  NVNM 15 to 17; vertex 12 B to 16 B (4 unknown bytes); cover entry 8 B to 12 B (unknown); the 21-byte triangle,
  11-byte edge links and door links {triangle, CRC 'PathingDoor', door REFR} are unchanged. Starfield adds NVMI
  "Traversals" (PathingTraversalLink; FO4's ledge edge links 1/2 have no direct home), VMAD/components on NAVM, and a
  NOCM obstacle-manager record. NVPP precomputed pathing and the AutoGen / Navmesh Gen Cell flags exist in both.
- **unresolved**: Starfield's cover bytes and the vertex extra field (xEdit leaves them unknown).
- **verified**: Starfield's CK generates interior navmesh from a seed marker
  ([Bethesda notes via Nexus](https://www.nexusmods.com/actsofblood/news/14993)); finalize adds door portal edges and must
  run after cover ([CK wiki](https://ck.uesp.net/wiki/Navmesh_Menu), FO4/Skyrim era, **supported** for Starfield). No
  public documentation of headless navmesh switches; no community tool converts navmesh between Bethesda games
  (**supported**, absence of evidence: ours appears to be the first).
- **verified**: without navmesh actors cannot move and cannot cross load doors
  ([CK wiki](https://ck.uesp.net/wiki/Why_aren%27t_my_actors_entering_or_exiting_an_interior_cell%3F)); followers do not
  follow into unfinalized interiors ([Nexus](https://forums.nexusmods.com/topic/4783015-companions-not-appearingfollowing)).
  **supported**: in Starfield, malformed multi-cell navmesh crashed a modder's game on revisit
  ([Nexus](https://forums.nexusmods.com/topic/13498237-please-need-help-with-ctd-when-mod-is-navmeshed)); missing navmesh
  means idle or teleporting actors, malformed navmesh can crash.
- **verified**: a door link exists twice (NVNM triangle and NAVI/NVMI door links), and the teleport marker must sit
  over a navmesh triangle in front of the door on both sides.
- Precedents: Skyblivion hand-draws navmesh ([volunteer page](https://skyblivion.com/volunteer/)); TTW finalizes per cell in
  GECK ([TTW forum](https://taleoftwowastelands.com/viewtopic.php@t=8436)); Fallout London, Beyond Skyrim, Cascadia
  appear to re-author in the target CK (**supported**).

## 3. Lighting, atmosphere and sound

Sources: xEdit Starfield and FO4 definitions (TES5Edit dev-4.1.6, `wbDefinitionsSF1.pas`, `wbDefinitionsFO4.pas`), Mutagen Starfield records (Cell, LightingTemplate, AcousticSpace, Light, PlacedObject), fo76utils `material.hpp`, the STEP list of Starfield INI settings, and Nexus mods 1244, 11452, 6410 and 54. This section adds to research/next-phase/lighting.md and docs/terrain/exterior-lights.md and does not repeat them.

**Cell lighting**
- **Verified:** Starfield CELL has a per-cell lighting override (XCLL). It holds ambient and directional colour, fog (near, far, power, max, clip), light fade, height fog, and a new Interior Type byte (Interior, Ship, Space, PackIn, Instanceable). The CELL also has LTMP, XCIM image space, XCAS acoustic space, XCMO music, XEMP env map, XCCM sky region and TODD.
- **Verified gaps:** FO4's 32-byte directional ambient cube and its 11 "Inherits" flags have no place in Starfield's XCLL. The directional ambient lives only on the lighting template (LGTM). How a cell's XCLL blends with its template is **unresolved**.
- **Unresolved:** XCLL offset +28 is DirectionalFade according to Mutagen and "Gravity Scale" according to xEdit. Do not write it until vanilla cells settle which.
- **Verified:** image space (IMGS), fog volume (FOGV), volumetric lighting (VOLI) and time-of-day data (TODD) are opaque reflection blobs. FO4 image spaces cannot be converted field for field. Choosing vanilla records per cell family is the realistic path (**supported**).
- **Verified:** references can carry volumes (REFR XVL2 points at an IMGS and a FOGV), so a cell can get a local fog or exposure zone from a vanilla FOGV.
- **Verified:** FO4 god rays (GDRY on cells, lights and weathers) have no Starfield record. Starfield's light shafts come from per-light volumetrics and from VOLI and FOGV.

**Lights and budget**
- **Verified:** Starfield lights carry area-light size, barn doors, gobos, a light layer and a volumetric scale. References can override the volumetric amount, the falloff and the layer, and can switch on a cached static shadow map (XLSM). Converted lights stay on the Default layer.
- **Verified conflict:** Mutagen and xEdit put the LIGH flag bits from bit 4 up one bit apart (Off by Default 0x20 or 0x10, Disable Specular 0x40 or 0x20, Use PBR 0x200 or 0x100). We use Mutagen's bits. Our PBR census fits Mutagen, but this needs one vanilla check.
- **Supported:** clustered lighting makes unshadowed lights cheap. Shadowed lights draw on a per-frame budget (`TotalDynamicShadowMapRenderCount`, `AdditionalDynamicOnlyLightsBudget`), and going over it shows as shadow glitches, not crashes. No source reports a crash from light count.
- **Supported:** every Starfield light is volumetric by default, so cells with about 1,000 converted lights may look hazy. We probably need to lower the volumetric scale.

**Emissive and reflections**
- **Verified:** Starfield materials have emissive components (luminous emittance, tint, adaptive exposure, ignores fog). **Verified (repo):** we do not convert emissive yet. `pipeline.py` skips effect-shader glow shapes, and the glow field in `convert_material.py` is parsed but not used. As a result, terminals, signs and lit glass come out dark.
- **Supported:** diffuse GI probes sample emissive, so converted glow maps would also add a little light to rooms.
- **Verified:** FO4 cells have no environment-map field. The ENV_MAP value in our lighting.json is our own choice. **Supported:** Starfield's reflection probes are captured at run time and placed as objects. Which base object is the probe is **unresolved**. Placing probes is likely the real fix beyond the XEMP fallback cubemap.

**Sound**
- **Verified:** FO4 sound records cannot be reused. Starfield has no SNDR record. Its acoustic spaces, sound markers, music and ambience sets all reference Wwise events, and its audio is Wwise .wem in WwiseSounds ba2s.
- **Supported:** adding new sounds needs a Wwise project build (the CK ships `Tools/wwise/Starfield/Starfield.wproj`, used with Wwise 2021.1.14). That step is manual and bound by Wwise's licence, so a user-side automatic build cannot do it.
- **Supported:** therefore we map FO4 acoustic spaces, sound markers and music to vanilla Starfield ones by family: cave drip, vault hum, industrial, metro wind, and silence. Ambience sets also key on marker keywords.

**Gaps in our own tools:** Fo4Export does not dump a cell's XCAS, XCMO, XCIM or XGDR yet. That is the first step for every sound and image-space mapping question in section 8.

## 4. Doors, locations, map markers, fast travel

Sources: xEdit dev-4.1.6 `wbDefinitionsSF1.pas` and `wbDefinitionsFO4.pas` (line numbers below), Mutagen dev Starfield records, docs/measurements/*_esm.json and repo docs. Nexus mods 15742 and 12719 and one Steam thread were rate-limited, so community pitfalls are thin. This section does not repeat doors-activators-workshops.md or map-markers.md. Per-batch door pairs: docs/terrain/data/interior-door-rounds.json. New interiors' outside doors need a core built against their port, so they are coc-only until then (#397). Door animations and sounds belong to door-animations.md.

**Locations**
- **Verified (repo):** PluginSpike writes no XLCN on converted interior cells. Our interiors have no location, leveling, cleared state or parent chain today. This is the biggest gap in this section.
- **Verified:** the Starfield LCTN DATA carries ownership and FO4's encounter-zone leveling fields (min and max level; Never Resets, Match PC Level, Disable Combat Boundary, Workshop), plus a new "Use Parent's Locked Level" flag (SF1.pas:13376-13575; FO4.pas:8022-8037). The Starfield CELL has XLCN but no XEZN, so each FO4 ECZN folds into its LCTN.
- **Verified:** most Starfield LCTNs carry a parent plus star and planet ids. In a sample of 300: PNAM 272, XNAM/YNAM 255. What a location with no planet parent does (cleared state, bounty, discovery) is **unresolved**. **Supported** default: chain interior LCTNs to our overlay location, whose parent is SSol_PMars_Surface.
- **Verified:** Starfield location ref rows (LCSR, ACSR, LCPR, ACPR) have 4 extra bytes per row that FO4's lack. "Master" lists and "Added" lists (ACSR and the others) are separate. A converter must append the bytes and pick the right list.
- **Verified:** CELL DATA grows to u32 and adds bit 16 "Use Location as Name". "Can't Travel From Here" (bit 2) and "Followers Can't Travel Here" (bit 13) are the same in both games. LCTN flags add Off Limits, Can't Wait and Public Area.

**Load doors**
- **Verified:** XTEL is byte-identical in both games, so the /70 scale is all a converted door needs (FO4.pas:11550, SF1.pas:8756). XTNM (teleport name, a MESG) exists in both.
- **Supported:** the "Enter X" text comes from XTNM if set, otherwise from the destination cell's FULL, or from the LCTN name when the cell sets bit 16. The runtime order is not verified.
- **Verified:** DOOR changes. FNAM bit 0 is now "No Quest Target" and bit 7 "No Direct Activation". Sounds become Wwise references (DOSH, DCSH, DLSH). FO4's random teleport destinations are gone. Starfield adds a facing axis and an embedded NVNM.
- **Verified:** every vanilla load door carries an XNDP navmesh door link; ours write none (redrocket-door.md:107, :133). Same question as N2 and N11.
- **Verified:** LSCR keeps FO4's layout, but Mutagen dev can write only VMAD, DESC, Conditions and ICON. So we keep vanilla load screens for now.

**Map markers, local map, fast travel**
- **Verified (schema):** the FO4 marker block (FNAM u8, TNAM u8 type) maps to Starfield's FNAM u32 and TNAM u16. Starfield adds Discovered, Requires Scanning, Suppress Discovery, Use Accurate Z-Height and others, plus VNAM, UNAM and VISI. This closes map-markers.md's open XMRK question at the schema level. Mutagen reads VNAM, UNAM and VISI as unknown.
- **Supported:** no Starfield marker type matches FO4's Vault, Metro or Diamond City, so a lossy type table is needed.
- **Unresolved:** whether Starfield draws an interior local map at all. A "Hidden From Local Map" flag exists on LCRT.
- **Supported:** fast travel into an interior goes through an exterior marker linked to an interior XMarker (mod 12719). Leaving is governed by CELL DATA bit 2.

**Aliases and ref types**
- **Verified:** REFR XLRT (location ref types) and XLCN exist in both games. Starfield XLRL accepts only LCTN. The Starfield LCRT is a richer record than FO4's. Whether FO4's Boss and BossContainer types have Starfield equivalents is **unresolved** and needs Starfield.esm on the PC.

## 5. Content inside interiors (loot, terminals, notes, traps, locks, actors, story cells)

Findings (record structure **verified** from the same xEdit definitions and Mutagen dev; game behaviour **supported**
until tested):
- **Leveled lists**: LVLI keeps its structure (chance none, LVLG, flags, conditions, epic chance, override name);
  Starfield adds biome and resource links and new flags. The hard part is the entries: FO4 WEAP/AMMO/ALCH/MISC and
  object templates do not exist in Starfield (docs/slice/r05-cluster-plan.md). Routes: map to Starfield lists by
  category, convert the items, or mix.
- **Encounter zones**: Starfield has no ECZN; its leveling data sits in LCTN DATA with the same fields, and XEZN
  ("Location Override") points at an LCTN. So each FO4 ECZN folds 1:1 into its LCTN.
- **Respawn**: a container respawns only with the CONT Respawns flag and a cell that is not Never Resets; FO4 timers
  10/30 days ([CK wiki](https://ck.uesp.net/wiki/Cell_Reset)); Starfield's values **unresolved**.
- **Terminals**: FO4 TERM holds its menu inline; Starfield's TERM points (DNAM) at a TMLM with body text, menu items
  (Display Text, Submenu, Return, Force Redraw, DataSlate-BOOK), a lock per item, and fragments on TMLM.
- **Holotapes and notes**: Starfield.esm has no NOTE records (FORMAT-GAP.md); the carrier is BOOK with a Data Slate
  Type (Text, Image, Audio). Text holotapes map to Text slates; voice ones need the Wwise path; program holotapes have
  no target.
- **Traps**: FO4 traps are scripted ACTI plus HAZD/EXPL/WEAP; Starfield keeps HAZD and mines; vanilla trap
  activators/scripts in Starfield **unresolved**. `oiltrappuddle01.nif` and `gastrap01.nif` fail to convert today.
- **Locks**: XLOC is byte-identical (levels 25/50/75/100, Barred, Chained, Requires Terminal, Requires Key; key link;
  leveled flag), so FO4 lock levels copy 1:1 to the digipick system. Our pinned Mutagen 0.55.0-alpha.67 has
  `PlacedObject.Lock` (**verified**, door-animations.md E22; written at ReferenceLinks/Relationships.cs:299, which no port build
  runs yet).
- **Actors**: ACHR on an LVLN with XLCM is identical; a hostile interior needs LCTN leveling, LVLN entries for
  converted actors, hostile factions, navmesh and sandbox/guard packages; Location Ref Types drive cleared state.
- **Story cells**: Initially Disabled (0x800), XESP enable parents and LCTN master enable parents exist in both games.
  Copying them hides quest-only refs forever (no quest enables them); dropping them shows every state at once
  (Parsons, Vault 111, Kellogg's memory, [MQ203](https://fallout-archive.fandom.com/wiki/Dangerous_Minds)).

## 6. Tools and pipelines

Sources: Mutagen dev records and the NuGet index; TES5Edit whatsnew.md (dev-4.1.6); evildarkarchon/generateprevisibines; Spriggit docs (cli.md, omissions.md); the fo76utils NifSkope README; DirectXTex; the CKPE repo; Nexus forum threads 13493071 and 13498237. The proxy rate-limited Nexus mods 14659 and 7830, the Spriggit docs site and the starfieldwiki Archive2 page.

**Mutagen**
- **Verified:** Mutagen's dev branch defines CELL, REFR, NAVM, LIGH, PKIN, TERM/TMLM, ASPC and LCTN. Some subrecords are still raw "unknown" bytes: PKIN FNAM, five TERM fields, CELL XILS and 56 REFR fields. REFR still has no ActivateParents (XAPD).
- **Verified:** our pin is 0.55.0-alpha.67 (published Oct 6). Newer versions are alpha.72 (Oct 17) and alpha.75 (today, Oct 19).
- **Correction for launcher-gamma-model-and-community-tools.md:** "Fallout4 2.8.1-prerelease002" is an unlisted 2021 package, not a newer one.
- Our existing workarounds stay: form version 576 vs vanilla 581, and the NAVM quirks (research-log.md:836, :1130).

**SF1Edit (xEdit, MPL-2.0)**
- **Verified:** Starfield editing is limited. PKIN cannot be overridden. Unmapped FormID fields may be non-null only when the first master is Starfield.esm. Check For Errors has been expanded.
- **Verified:** batch switches are `-sf1 -autoload -autoexit -script: -log:`. In FO4 practice, unattended runs need SendKeys past module selection and a kill when xEdit hangs.
- BSArch, in the same repo, now has exit codes, lz4 compression, split archives and filters. Its Starfield BA2 support is **supported** only.

**Spriggit (GPL-3)**
- **Verified:** the CLI converts both ways and fails on unknown fields by default. For Starfield it needs the game's Data folder, so it runs as a PC job.
- **Verified:** it leaves out unused fields and timestamps, so a round trip is not byte-identical. Use it for review diffs only, not as proof of determinism.
- The latest Starfield package, 0.42.0-alpha.2 (Jul 10), predates our Mutagen pin.

**Creation Kit**
- **Verified, FO4 CK only:** headless precombine and previs switches exist (`-GeneratePrecombined`, `-GeneratePreVisData`, `-CompressPSG`, `-BuildCDX`). Whether Starfield's CK accepts them is **unresolved**. No headless navmesh or lip generation is documented.
- **Verified:** CKPE (LGPL-3 from v0.6) supports the Starfield CK.
- **Supported, one forum thread each:**
  - Terminal menus written outside the CK crash the CK on load, though the game loads them. We write TERM records.
  - Multi-cell exterior navmesh crashed on a second visit; interiors were fine.

**Meshes and textures**
- **Verified, high value:** the fo76utils NifSkope fork (BSD-style licence, the base of our sfmesh layout) runs headless with `-no-gui`. It can convert geometry internal/external, update bounds, optimise indices, generate mesh LODs, add tangents and sanitise. It works on folders, recursively. That makes it a second implementation to check our .mesh writer against.
- **Verified:** PyNifly (GPL-3) has experimental Starfield support. The MrTrilB Blender extension has no licence, so it is for reference only.
- **Verified:** texconv (MIT) accepts a file list (`-flist`) and does GPU compression only for BC6H/BC7. Our pipeline starts one texconv process per texture (pipeline.py:243-432), which is an optimisation candidate to measure.

**Community QA**
- **Supported, snippets only:** Trainwreck is the SFSE crash logger in use. Its licence and whether it works with our game version are unknown.
- **Unresolved:** no community tool visits every Starfield cell. We build our own runner (testing-automation.md).

## 7. Prior art and modding communities

| Project | Interiors | Navmesh, lighting, previs | What went wrong |
|---|---|---|---|
| Skyblivion (Oblivion in Skyrim SE) | Began as an automated port (Zilav's tool); broken map sections and crashes led to a full hand remake ([Wikipedia](https://en.wikipedia.org/wiki/Skyblivion)); interior designers polish enemies, traps, clutter, local maps ([volunteer page](https://skyblivion.com/volunteer/)) | Navmesh hand-drawn, a dedicated role, still on the critical path ([delay post](https://skyblivion.com/?p=10677)) | The automated port failed on quality; slipped to 2026, "living project" |
| Skywind | Hand remake | | Nexus moderated it while it exchanged assets between Bethesda games ([Nexus](https://www.nexusmods.com/uno/news/12752)) |
| TTW (Fallout 3 in New Vegas) | Automated: rebuilt from the player's own files, same engine generation | Not published | Saves break across version bumps ([FAQ](https://thebestoftimes.moddinglinked.com/faq.html)) |
| Capital Wasteland (FO3 in FO4) | Hand remake plus an audio extraction tool | | Stopped once over legality: Bethesda licenses, not owns, the voice acting ([PCGamesN](https://pcgamesn.com/fallout-4/fallout-4-fallout-3-capital-wasteland-mod)) |
| Fallout London | Original, by hand | Patch 1.02 regenerated previs/precombines for crashes and culling ([Wccftech](https://wccftech.com/fallout-londons-patch-1-02-is-out-now-with-hundreds-of-fixes-and-a-specific-focus-on-graphical-improvements/amp/)) | A Bethesda update broke it before launch; buggy reception |
| Cascadia, Fallout 4: New Vegas, Beyond Skyrim | Hand-built; Beyond Skyrim shipped a separate interiors beta ([blog](https://beyondskyrim.org/blog/bruma-interiors-go-beta)) | | Long silences; side releases in the meantime |
| fnv-to-fo4 (GitHub, GPL-3.0) | Automated converter on the player's PC; models "fully", plugins "partially" ([repo](https://github.com/terry-haire/fnv-to-fo4)) | Not documented | The closest technical precedent |
| Fallout 4 to Starfield | Only an outfit porter beta found ([Nexus 18458](https://www.nexusmods.com/starfield/mods/18458)); **no port of whole interiors or worlds found** (**supported**) | | |

Legality (sources as reported, not legal advice):
- A Nexus moderator: Bethesda does not allow porting assets between its games; a mod that requires the user to own
  both games is "a different case" ([forum, 2019](https://forums.nexusmods.com/topic/7312551-fallout-4-assets-modded-into-skyrim)).
- The Skyrim CK EULA licenses mods "solely in connection with the Product" and "originally created by You"
  ([UESP copy](https://en.uesp.net/wiki/Tes5Mod:EULA)); Starfield's CK EULA wording is **unresolved**.
- **Voice is the sharpest risk** (Capital Wasteland); interiors hold terminals, holotapes and barks.
- Creations: no published rule on ports found (**unresolved**); converted content cannot go there (**supported**).
  Nexus wants public Starfield mods as ESM ([Nexus](https://www.nexusmods.com/news/14993)).

Communities and etiquette: xEdit/SF1Edit Discord and the TES5Edit tracker (ElminsterAU, Hlp, Sharlikran, Zilav;
don't pressure them for updates); the fo76utils NifSkope fork for Starfield meshes
([GitHub](https://github.com/fo76utils/nifskope)); PJM for precombine/previs automation in FO4
([mod 69978](https://www.nexusmods.com/fallout4/mods/69978)); TTW / ModdingLinked, Skyblivion / TESRenewal and Beyond
Skyrim Discords (piracy talk is a ban); starfieldwiki.net (forms and formats, no navmesh). Ask with evidence, credit
tool authors by name, never post converted assets.

Lessons for 271 automated interiors (**supported**):
1. A naive automated port has failed before: ship an automated baseline with a per-cell tier (works / playable with
   known issues / disabled).
2. Navmesh is the long pole everywhere; we need converted or generated navmesh plus a per-cell quality metric.
3. Previs/precombines cause crashes after release; a first release may skip them or rebuild them on the player's PC.
4. Pin the Starfield and Fallout 4 builds; updates break total conversions and saves.
5. Release in stages and never present a stage as finished.
6. Beta-test interiors on each player configuration and keep a known-issues list.

## 8. The framework of questions

Every question from sections 1 to 7 is listed below in the order the phase can answer it. The full wording, the reason and the cheapest test for each are in this file's question tables, which follow this section (N navmesh, C content, P prior art, E engine, L lighting and sound, T tools). Nothing here is installed or run in game without the owner's word.

**Step A: offline, in the cloud or from files we already have (start now)**
- Navmesh shape: N3 (door triangles after scaling), N5 (NVMI against vanilla), N6 (ledge links), N7 (vertex counts), N12 (unknown bytes).
- Content census: C1 (disabled refs and enable parents), C3 (loot leaf types), C7 (terminal menu depth), C9 (traps by type).
- Engine survey: E2 (largest vanilla interior), E3 (cell flags), E5 (roombounds and primitives), E8 (extents), E9 (bounds).
- Lighting survey: L2 (XCLL +28), L3 (light flag bits), L8 to L10 (vanilla image spaces, volumes, probes), L16 and L17 (music precedence, Interior Type).
- Tools: T5 (masters and PKIN overrides), T9 (CK command-line strings).
- Doors and locations: D1 (offline part), D3, D8.
- Exporter gap: add XCAS, XCMO, XCIM and XGDR to Fo4Export (feeds L14 and L15).

**Step B: on the PC, read-only or staged (one job at a time, through the coordinator)**
- D4 and D7 (vanilla door links and LCRT list, read-only), P1 (CK EULA), L4 (shadow budgets in the preset INIs).
- T1 (Mutagen alpha.75 against alpha.67 on one batch), T4 and T3 (SF1Edit error baseline, then the unattended gate).
- T6 and T7 (Spriggit as a review diff), T12 (NifSkope headless as a second .mesh check).
- T14 and T15 (texconv batching, BSArch against Archive2; recorded in optimization.md).

**Step C: first in-game checks (after the v6e test, on the owner's word)**
- Stability first: N4 (revisit and save/load), E7 and E11 (load time, RAM, archive size and stutter), N11 (dangling door links).
- AI: N1 (no navmesh), N2 (door links without the CK), N10 (cover, companions, sandbox).
- Doors: D2, D4 (with a follower), D5, D6, and D1's level check.
- Worst case: E1 with L5 (Mechanist's Lair, references and 1,082 lights).
- Look and feel: L6 (volumetric haze), L18 (sky-open cells), L11 (XEMP cubemap with probes present), L12 and L13 (emissive), C5 and C8 (locks, holotapes as data slates).

**Step D: engine and tool decisions (from the results of A to C)**
- T8 and E10 (does the CK open the port), then N9, T10 and T11 (CK navmesh and previs, or our own).
- E4 (SCOL and PKIN for repeated groups), E6 (reference-handle budget), L7 (cached shadows), T13 (mesh LODs), T16 (crash logger).
- Each decision gets an entry in docs/ai/decisions.md.

**Step E: content decisions (the owner's)**
- C2 (story cells now or with the quest track), C3 (loot source), P2 (voice: default text only).
- C4 (level bands), C6 (terminal locks), C10 (respawn and cleared locations), C11 (first combat room).
- Outreach only on the owner's word: P3 (ask Nexus or Bethesda), P11 (fnv-to-fo4's author).

**Step F: release**
- P4 and P5 (what "done" means, with an automatic navmesh score), P6 (which interiors ship first).
- P7 and P8 (pinned game build, saves surviving a rebuild), P9 (local maps), P10 (credits and wording), T17 (bundled tool licences).

**Already answered by this phase's batches (verified):** FormIDs stay the same across batches (`--prev` chaining); DLC interiors export with their master; and disk need is per batch, not from nothing.

**Leads from the framework thread's findings (findings/*.md; leads to verify, not settled):**
- X1 (starfield-toolchain Q6, precedents Q5): the CK batch navmesh command line (`-UpdateNavmeshGeneration`, `-FinalizeNavmeshes`, `-Part`) was found as strings only. Same question as N9 and T11; Step D. Cheapest test: 3 cells, timed, with the FormIDs diffed.
- X2 (starfield-toolchain Q8, versions-performance Q4): should interiors be split into medium masters? Not for us: FO4Port.esm holds about 600k records and must stay a full master (section 1). The conflict over the medium master's limit (65,535 forms per Bethesda, ObjectIDs up to 0xFF per one MO2 plugin) only matters if a later design splits regions. A synthetic-plugin PC test settles it then, not in this phase.
- X3 (versions-performance Q4, starfield-toolchain Q14): vanilla archives stop just under 4 GiB, and whether the engine reads a larger one is unresolved. **Verified:** batch 4's Textures.ba2 measures 3,590,442,691 bytes, 0.81 of the plan's estimate. At that ratio the textures archive passes 4,095 MiB around batch 7 (supported). Since commit f70d118 on PR #396, interior_batch.py fails any batch whose archive reaches the limit. Still open: how to split. The choices are a second textures archive (its auto-load name is unverified), a small companion plugin carrying its own `- Textures.ba2`, or a smaller texture set; the in-game probe of a larger archive is Step C.
- X4 (versions-performance: 256 active BA2s): one port means one to three archives, far below the limit. Watch the count only if batches ever ship as separate plugins.
- X5 (testing-qa Q6): add a 360-degree camera spin after each coc in the interior smoke runs, so a bad mesh in any direction crashes during smoke. Step C, with #405's smoke-first queue.
- X6 (testing-qa Q7, precedents Q5): an offline navmesh connectivity checker (reachability between door markers over the converted NAVM) before any in-game test. Extends N3 and P5; Step A.
- X7 (testing-qa Q8): screenshot diff per interior at the coc marker against the last accepted build, after measuring the noise floor (the same cell shot 5 times). Step C.
- X8 (precedents Q4): hash the FO4 source files (Fallout4.esm, the DLC .esm files, the BA2s) and refuse to build against unknown versions. The launcher's build record already records hashes; check that the interior batches carry them too. Step A.
- X9 (precedents Q6): the QA budget for 271 interiors: automated cell cycling (the watchdog chain), a community beta, or both. The owner's call; Step E.

**BACUP compared (2026-10-19; github.com/Bryant-21/bacup cfa3d0d and py-creation-lib 2860078, GPL-3; read only, nothing run).** BACUP has a world-only `fo4:starfield` pair: no actors or quests, and FO4 navmesh is skipped. It writes with its own Rust writer driven by xEdit-derived schemas, uses form version 581 and outputs `Fallout4_SF.esm`. Its evidence is synthetic tests only; there is no sign its output loads in game.

| Area | BACUP | Ours | Take away |
|---|---|---|---|
| Interior CELL | FO4 DATA flags copied to u32; LTMP, XCAS, XCMO kept; drops XCLL, XCIM, XLCN; no XEMP | Interior flag; vanilla LGTM, IMGS, XEMP cubemap | Theirs lacks the image space whose absence gave us the pink wash |
| LCTN/XLCN | none | none | D1 still open for both |
| REFR | scales DATA, XTEL, XPRM, XRDS; zeroes the XTEL transition cell when that cell isn't written; drops XLOC, XLIG | XTEL, doors persistent | Borrow the dangling-transition rule for coc-only batches |
| Scale | 1/69.99125 (Havok constant) | /70 | Ratio 1.000125, under 1 cm per interior; no change |
| LIGH flags | xEdit bits 0x10/0x20/0x100, from the schema only | Mutagen bits 0x20/0x40/0x200 | Still L3; test: in our light census, see whether lights with non-default lumens carry 0x100 or 0x200 |
| OBND | 6 x i16 | 6 x f32 (vanilla measured) | Theirs is likely wrong |
| SCOL | writes real SCOL records | places merged CM*.nif as one static | Idea for E4 |
| LGTM/WATR | rebuilds FO4 LGTM (DATA truncated to 108 B, DALC to 24 B) | vanilla LGTM per cell family | Option for L1/L8: keep each cell's FO4 lighting mood |
| Navmesh | Starfield v17 to FO4 v15 only | FO4 to Starfield plus NVMI | Their parser accepts 12 B-vertex and 32 B-trailer NVNM variants; make ours tolerate them |

Their schema labels XCLL +28 "Gravity Scale" and +104 "Interior Type", both xEdit-derived. So L2 leans to gravity: never write FO4's directional fade there. Verdict: no code worth taking; two ideas and three value checks, as in the table. Reusing their code or contacting the author is the owner's call (AP-60).

**Answered since the first pass:**
- T9 (verified, 2026-10-19, from the job 18 string dumps D:\Modding\research\ck_switches_1.txt for the Starfield CK and _2.txt for the FO4 CK): FO4's CK has `-GeneratePreCombined` and `-GeneratePreVisData`, each taking `<ESM> [clean,filtered] [all,main,ints,other] [set] [count]`. Starfield's dump has neither. Its dash switches include `-GenerateMeshLODAssociations`, `-GenerateMeshLODStats`, `-GenerateMeshLODFailureReport`, `-GenerateCellAndRefCounts` and `-GenerateWarnings`. It does still have the GUI actions "Generate Precombined Visibility for Current Cell" and "... for All Loaded Cells", so an in-editor previs step may exist, but not a batch one in this dump. Correction (verified by job 20's full usage-string scan, 18:29Z): `-MockWorldSpaceLOD:<ESM> <WorldSpace0> [WorldSpace1 ...]` exists in the Starfield CK only; the first dump's filter had hidden it. That full scan also confirms that the Starfield CK has no precombine or previs switch. It lists `-ExportESM`, `-RunValidationSuite`, `-DepersistRefs`, `-CheckInPlugin` and `-ImportScalingData`. `-RunValidationSuite` is a candidate for T3 (an unattended plugin check) next to SF1Edit. Its scope and output are unresolved. The full lists are in the engine-mechanics notes. `-GenerateCellAndRefCounts` may serve E2 and E7 (reference counts per cell) without our own tool; its output format is unresolved.

### Question tables

#### Navmesh and AI
| # | Question | Why it matters | Cheapest test |
|---|---|---|---|
| N1 | Zero navmesh in a converted interior: do actors idle, teleport or crash? | Sets the risk of shipping batches before navmesh | One interior without NAVM, a vanilla NPC and a companion, the npc_nav runner |
| N2 | Do the two door links (NVNM door triangle + NVMI door link) work without CK finalize? | Decides whether the CK is needed at all | One converted door pair (RedRocket01), an NPC sent through it |
| N3 | Does each converted XTEL point land on its door triangle after the /70 scaling? | Off-mesh markers block NPCs at doors | Offline distance check over all 517 interior NAVM |
| N4 | Can malformed converted navmesh crash on revisit? | Worst failure for a 251-cell batch | Enter/leave/re-enter/save/load one cell 5 times with the runner |
| N5 | Do interior NAVI/NVMI need island data, Approx Location, NVPP entries? | A wrong NVMI breaks cross-cell pathing silently | Offline diff against a vanilla Starfield interior NVMI (SfInspect) |
| N6 | Do FO4 ledge links (types 1/2) need translating into NVMI Traversals? | Drops and stairs in interiors | Offline count of type 1/2 links in the 517 NAVM |
| N7 | Max vertex count in the 517 interior NAVM: does any exceed i16 indexing? | Large interiors may need u16 indices | Offline count |
| N8 | Must AutoGen / Navmesh Gen Cell flags be set or cleared? Does the runtime generator overwrite our navmesh? | Runtime regeneration could replace converted meshes | Offline flag scan of vanilla interior NAVM; one seed marker in a converted cell |
| N9 | Does `CreationKit.exe -UpdateNavmeshGeneration` run headless on our ESM, and does finalize keep our FormIDs? | Fallback generator; FormID stability is a project rule | One cell on the PC (owner-run, GPU free); diff FormIDs |
| N10 | Do Starfield cover bytes matter for combat? Do companions path or warp into converted interiors? Do sandbox packages find converted furniture? | Core gameplay quality | One raider fight with empty cover; Sarah through one door pair; one settler with a sandbox package |
| N11 | Is a dangling NVMI door link (exterior door to an interior not yet shipped) safe? | Batches ship incrementally | A test build with one interior deliberately left out |
| N12 | What do Starfield's vertex extra i32 and triangle unknown byte mean? | Wrong values may change AI behaviour | Offline histogram against slope in vanilla data |

#### Content inside interiors
| # | Question | Why it matters | Cheapest test |
|---|---|---|---|
| C1 | Initially-disabled refs and enable-parent trees in story cells: copy, drop, or pick one state per cell? | Decides what the player sees in Parsons, Vault 111, Kellogg's memory | Offline count of 0x800 / XESP refs per cell |
| C2 | Story cells (Kellogg's memory, PrewarVault111): ship as walkable scenery behind coc, or hold for the quest track? | They look broken without their scripted sequences | Owner decision |
| C3 | Loot: converted FO4 items, Starfield lists, or a mix? | Decides the size of the weapons/armour job | Owner decision after an offline census of FO4 LVLI leaf types |
| C4 | Fold each ECZN into its LCTN 1:1, or one flat level band? Keep FO4's level curve or clamp to Starfield's? | Leveled actors and loot follow it | One cell with an XEZN LCTN (min 5, max 10), GetLevel on a spawned actor |
| C5 | First half verified (door-animations.md E22: the pinned Mutagen alpha.67 has `PlacedObject.Lock`, and ReferenceLinks writes it at Relationships.cs:299; Papyrus Lock() also locks linked lockables by default). Still open: does XLOC 25/50/75/100 bring up the digipick on converted CONT/DOOR, and does any port build run ReferenceLinks yet (none has)? | Locks copy 1:1 only if both hold | One locked container in game, after a build that runs ReferenceLinks |
| C6 | How do "Requires Terminal" (253) locks map, and do FO4 terminal fragments become TMLM fragments? | Doors and turrets opened from terminals | Scan TMLM fragments in Starfield.esm; one TMLM calling Unlock() on a linked ref |
| C7 | Full nested TMLM trees now, or "name + one body line"? | Lore and quest hooks live in submenus | Offline depth distribution of FO4 TERM menus |
| C8 | Holotapes to BOOK data slates: Text now, Audio after the Wwise path? Does a TMLM DataSlate-BOOK item show a converted BOOK? | Replaces FO4's "play holotape in terminal" | One text holotape picked up and read; one TERM with a BOOK item |
| C9 | Traps: drop, stub (static + HAZD / inert ACTI) or rebuild with our own script on OnTrapHit? Why do gastrap01/oiltrappuddle01 fail? | Traps are part of FO4's interiors | Census of trap refs by type; grep Starfield script names for Trap; read the convert log reason |
| C10 | Starfield's cell reset timer, and should converted containers respawn? Do Starfield's cleared-location systems attach to our LCTNs without a planet parent? | Respawn and bounty/mission systems | GMST dump; clear one cell with leveling data and wait past the timer |
| C11 | Minimum hostile-interior kit (LCTN + LVLN + faction + package + navmesh) for one raider room | First playable combat interior | One Concord cell with 3 leveled raiders |

#### Prior art, legality and release
| # | Question | Why it matters | Cheapest test |
|---|---|---|---|
| P1 | Does Starfield's CK EULA limit mods to content "originally created by You" for Starfield? | Sets the legal room | Read the EULA in the Creation Kit folder on the PC |
| P2 | Voice in interiors (terminals, holotapes, barks): leave out, text only, or convert from the player's files? | Capital Wasteland was stopped over voice | Owner decision; default text only |
| P3 | Ask Nexus or Bethesda staff before the first public interiors build? | Precedents differ (Capital Wasteland asked and stopped) | One Nexus support ticket, on the owner's word |
| P4 | What counts as "done" for an interior: tiers and pass criteria? | 271 cells cannot each be checked by hand | Write a rubric from Skyblivion's polish list (navmesh, enemies, clutter, local map) |
| P5 | How do we score navmesh quality automatically (coverage, islands, door links)? | Needed to auto-tier cells | Prototype a metric on existing navmesh JSON |
| P6 | Which interiors ship first: most visited, or simplest? | A staged release protects reception | Rank by refs and quest links from the census |
| P7 | Which Starfield build do we pin, and how does the launcher react to an update? | Updates broke Fallout London | Decide and log in decisions.md |
| P8 | Do saves survive a re-converted interior? | TTW breaks saves on version bumps | Build, save, rebuild, load (ids are now kept across batches) |
| P9 | Local maps and map markers per interior? | Skyblivion lists local maps as polish work | One cell in game |
| P10 | Credits, testers' report channel, public wording that never implies "complete" | Etiquette, licences, reception | Credits file; reuse community_report.yml; owner-approved release notes |
| P11 | Talk to fnv-to-fo4's author about cells, navmesh and previs? | The only automated cross-engine cell converter found | One GitHub discussion post, on the owner's word |

#### Engine and performance
| # | Question | Why it matters | Cheapest test |
|---|---|---|---|
| E1 | Does a 28,000-reference interior (Mechanist's Lair) run at an acceptable frame rate? If not, split it into cells joined by load doors? | No precombines: every reference is a draw | In game: coc into batch 10's Lair, frame-time log vs a dense vanilla interior |
| E2 | What is the largest reference count in any vanilla Starfield interior? | Our safe ceiling | Offline SfInspect count over Starfield.esm |
| E3 | Do vanilla cells set "No Pre Vis" or a non-default XCLL Interior Type; must we? | Wrong cell type may change loading or culling | Offline survey |
| E4 | Does Starfield.esm use SCOL, does a placed SCOL render, and should repeated FO4 groups become PKINs? | Record count and draw count | Offline survey, then one in-game spike |
| E5 | Do FO4 roombound / portal / plane marker refs reach FO4Port.esm today, and do vanilla interiors use XPRM primitives for culling? | Dead markers or missing culling | Offline grep of the exports; XPRM survey of vanilla interiors |
| E6 | Reference-handle budget: how close do 271 cells plus the Commonwealth get? | Engine limit with no published number | SFEF's handle dump in game (installing SFEF needs the owner) |
| E7 | Load time and RAM for a ~600k-record full ESM at batches 4, 9, 10; do persistent groups load at start? | Startup cost grows with each batch | Time to main menu and first coc; persistent ref counts per batch |
| E8 | Are any converted interiors larger than vanilla's largest (physics or culling trouble)? | Large FO4 interiors | Offline extents from the census exports |
| E9 | Do converted bases need OBND matching the NIF bounds for culling? | Pop-in | Offline OBND vs mesh bounds check |
| E10 | Does the CK open FO4Port.esm without crashing? | Needed if the CK is used for navmesh or debugging | CK load-only on the PC |
| E11 | Archive count/size limits if archives grow past 4 GB or split per batch? First-entry stutter with thousands of new models? | Batch 9 archives ~5.7 GB | Check Archive2 >4 GB; time load door to control, cold and warm |

#### Doors, locations, markers
| # | Question | Cheapest test |
|---|---|---|
| D1 | Does each converted interior need an XLCN and an LCTN (leveled spawns, cleared state, door prompt)? | Offline: write one LCTN with PluginSpike (parent = overlay LCTN, leveling from FO4 ECZN) and read it back; in game, coc there and check a leveled actor's level |
| D2 | Which source does the "Enter X" prompt use: XTNM, the cell name, or the LCTN with bit 16? | In game: one door pair, three variants |
| D3 | Location ref rows: is the 4-byte tail needed, and should our port use the Added lists? | Offline Mutagen round trip; PC read-only byte check of an ACSR in SFBGS003.esm |
| D4 | Do interior load doors need XNDP/NVMI door links for followers and enemies? | PC read-only XNDP count on vanilla interior doors; in game, one pair with and one without, with a follower |
| D5 | Is there an interior local map; does the LCTN flag put the player's marker on the surface map? | In game: open the map in a vanilla cave and in one converted interior |
| D6 | Does a marker without star or planet ids raise "location discovered"? | In game: one marker, walk up to it |
| D7 | FO4 LCRT (Boss, BossContainer and others) to Starfield LCRT | PC read-only: list Starfield LCRT EditorIDs, diff against FO4's 704 |
| D8 | FO4 load screens: carry them over, or keep Starfield's? | Offline: Mutagen LoadScreen code; default vanilla screens |
| D9 | Community pitfalls with new interiors on an existing world | Retry the rate-limited Nexus and Steam pages later |

#### Lighting and sound
| # | Question | Cheapest test |
|---|---|---|
| L1 | XCLL vs LGTM blend | SfInspect count of vanilla interiors with both; one cell rendered three ways |
| L2 | XCLL +28 fade or gravity | SfInspect histogram over vanilla interiors |
| L3 | LIGH flag bits Mutagen or xEdit | EditorID-to-bit census in light_census.py |
| L4 | shadow budget defaults per preset | read Ultra.ini/Medium.ini on the PC, read only |
| L5 | Mechanist's Lair 1,082 lights frame cost | runner pass, three variants: all, no shadows, 50% cull |
| L6 | lower volumetric scale on converted lights | A/B FVLD 0 vs vanilla screenshots |
| L7 | XLSM cached shadow keeps FO4 shadow lights cheap | SfInspect count, runner A/B |
| L8 | which vanilla IMGS/FOGV/VOLI per cell family | extend SfInspect imgs/templates survey |
| L9 | XVL2 volumes for local fog (Glowing Sea caves, flooded metro) | SfInspect list of XVL2 refs |
| L10 | which object is a reflection probe, how many per vanilla interior | SfInspect component search |
| L11 | XEMP cubemap still used with probes | screenshot A/B |
| L12 | FO4 glow to EmissiveSettings mapping | dump one vanilla terminal .mat, convert one FO4 terminal |
| L13 | emissive GI lets us cull fill lights | brightness A/B |
| L14 | vanilla ASPC per FO4 acoustic family | add XCAS/XCMO/XCIM/XGDR to Fo4Export, group |
| L15 | FO4 SOUN markers to vanilla SOUN by keyword | name-matching table |
| L16 | MUSC on cell vs ASPC precedence | SfInspect |
| L17 | Interior Type (Interior/PackIn/Instanceable) effects | SfInspect census, two-copy test |
| L18 | Show Sky / Use Sky Lighting for sky-open FO4 interiors | one runner pass noon and midnight |

#### Tools
| # | Question | Cheapest test |
|---|---|---|
| T1 | Mutagen alpha.67 to alpha.75 | build one batch with both; byte and Spriggit diff |
| T2 | stamp form version 581 | SF1Edit Check For Errors on both |
| T3 | SF1Edit Check For Errors unattended as a gate | -sf1 -autoload -autoexit -script:, SendKeys fallback |
| T4 | SF1Edit error baseline for FO4Port.esm | one run, saved as a fixture |
| T5 | first master Starfield.esm, any PKIN overrides | cloud header read |
| T6 | Spriggit as review aid or CI artifact | serialize twice and across builds, diff |
| T7 | Spriggit reads our records with ErrorOnUnknown | one PC run |
| T8 | Starfield CK opens FO4Port.esm, terminals | open with CKPE log; retry without TERM/TMLM |
| T9 | CreationKit.exe has GeneratePrecombined/GeneratePreVisData strings | string scanner |
| T10 | do converted interiors need previs at all | fps and draw calls with/without |
| T11 | converted NAVM vs CK-generated | one interior both ways, NPC pathing |
| T12 | NifSkope -no-gui as .mesh validator | run on a copy of one batch, diff, count warnings |
| T13 | NifSkope GenerateMeshLODs | one mesh, frame cost |
| T14 | texconv -flist and GPU BC7 saving | time stages of one batch, swap one |
| T15 | BSArch vs Archive2 | pack one batch both ways, coc |
| T16 | crash logger for 1.16.244 / SFSE 0.2.21 | install, reproduce Red Rocket crash |
| T17 | launcher bundles texconv and NifSkope | decisions.md entry |
