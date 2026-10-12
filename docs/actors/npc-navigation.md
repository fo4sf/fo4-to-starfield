# NPC step of the playable slice: navigation and a minimal actor (research, 2026-10-11)

Slice: Commonwealth terrain -> **moving NPC / enemy** -> interaction / combat -> working door -> converted interior ->
save/reload. This page prepares the NPC step. It keeps three failure sources apart, because "the NPC does not walk"
can mean any of them:

| Source | Question | Isolated by |
|---|---|---|
| **World** | Is there ground with collision where the NPC stands? | the existing `terrain` / `fall` queue kinds (drop the *player* at A and B first) |
| **Navigation** | Is there a navmesh the AI can path on, from A to B? | the same vanilla NPC and commands in a vanilla navmeshed cell (control) vs. the test worldspace |
| **Actor conversion** | Does a converted FO4 actor record behave like a vanilla one? | the converted NPC in the vanilla control cell, where navigation is known good |

Labels: **verified** (measured here, number given), **supported hypothesis**, **unresolved**. Nothing on this page was
run in game: Starfield was busy with the test chain, so every in-game step is a proposal.

Tools used (all read-only): `dotnet/SfInspect` (new commands `navm`, `npcfind`, `npc`, `props`, see below) and local
Python scanners over `Starfield.esm` / `Fallout4.esm` / `Starfield.exe` / `CreationKit.exe` strings (scratch, not in the
repo; they walk the GRUP tree and parse `NVNM` byte-exactly).

---

## 1. How Starfield stores and generates navmesh

### 1.1 Records (verified)

| | Starfield.esm | Fallout4.esm |
|---|---|---|
| `NAVM` records | **56,576** | **7,893** |
| worldspaces with NAVM / all WRLD | 424 / 433 | 4 / 5 |
| interior NAVM / interior cells that have any | 7,959 in **475 of 11,985** interior cells | 780 NAVM |
| `NVNM` version (u32 at +0) | **17** in all 56,576 | **15** in all 7,893 |
| `NVNM` magic (u32 at +4) | `0xA5E9A03C` in all | `0xA5E9A03C` in all |
| Navmesh info map | one `NAVI` (`00000FF1`): `NVER`, **56,631 `NVMI`**, `NVPP`; 53.9 MB | one `NAVI` (`00000FF1`): `NVER`, 7,798 `NVMI`, `NVPP`; 1.4 MB |
| Exterior cell size seen in NAVM | **100 m** (navmeshes of NewAtlantis cell (0,1) end exactly at x = 100.0, y = 200.0) | 4,096 units = 58.5 m (Red Rocket cell (-17,19): x -69,632..-65,536 exactly) |

Per worldspace (`SfInspect navm <name>`; the scratch scanner gives the same numbers, two independent readers;
`SfInspect navm '*'`: 48,617 in worldspaces + 7,959 interior = 56,576):

| Worldspace | kind | NAVM | cells with NAVM / cells |
|---|---|---|---|
| `CydoniaCity` 2CFC4A | city (Mars master worldspace) | 2,708 | 51 / 135 |
| `NewAtlantis` 01251B | city (Jemison master worldspace) | 1,970 | 70 / 775 |
| `akilacity` 27CFA2 | city | 1,004 | 36 / 129 |
| `NeonCity` 27CF9E | city | 820 | 26 / 170 |
| `LandingOverlay01..05`, `PCMGenericLandingOverlay`, `DefaultSpaceshipLandingOverlay` | landing-zone overlays stamped into procedural terrain | **1 each** | 1 / 10..26 |
| `PCMShipLanding01..03` / `04` | ship landing overlays | 1 / 2 | 1 / 10..17 |
| `OverlayPOI*` / `*Trait*` (36 / 87 worldspaces that have NAVM) | procedural POI / trait overlays | 621 / 2,959 | |
| `DefaultWorld` 00003C | template parent of the trait overlays; no cells | **0** | 0 / 0 |
| `OutpostOverlayTemplate` 2A39CB | outpost overlay | **0** | 0 / 2 |

The 9 worldspaces without any NAVM: `DefaultWorld`, `oedebugoverlay`, three `OverlayTrait*Water`,
`LC028FreightElevatorExit`, `OutpostOverlayTemplate`, `OverlayPOIBiomeCrystalTrees01`, `OverlayPOIBiomeValleyofTrees01`.

Procedural planet surfaces have **no worldspace record and no NAVM in the ESM** (verified: 1,504 planets have a
procedural `SurfaceTree`, only 45 register a master worldspace; docs/terrain/architecture.md on PR #57). A landing
overlay is 10..26 cells but carries one navmesh. NPCs and fauna still walk on generated terrain in normal play (common
gameplay observation, not measured here), so that terrain is navmeshed at runtime (**supported hypothesis**, 1.3).

### 1.2 Navmesh generation inputs in the data (verified)

- `NavMeshSeedMarker` (STAT **000001F8**) is placed in **2,683 cells**, 357 of them interiors; **every one of those
  357 interiors also has authored NAVM** (0 without). `NavMeshAntiseedMarker` (STAT 000001FA) 1 cell,
  `NavMeshGenExclusionVolume` (STAT 000001FC) 34 cells, `NavMeshSpline` (BNDS 000001F9) 178 cells.
- 825 exterior cells have a seed marker but no NAVM of their own (e.g. `SettleWaggonerFarm` 117, `LC024World` 87,
  `NeonCity` 55, `NewAtlantis` 36). Whether those cells get navmesh at runtime or from a neighbour: **unresolved**.
- GMST: `fDensityMaskNavmeshOfflineGenerationMin/Max` (0.0 / 0.02), `sWorkshopPlacement_NAVMESH_ONLY`,
  `fWorkshopBudgetNavmeshCost`. "Offline generation" implies an online (runtime) counterpart.
- The CK launch notes say: "Creating navmesh is now as easy as dropping down a marker in your interior (manual
  navmeshing is still possible)" ([Nexus Mods news 14993](https://www.nexusmods.com/news/14993), search-result text;
  the page refused a direct fetch, so **unverified** wording).

### 1.3 Runtime generation in the engine (strings in Starfield.exe, verified to exist; behaviour unresolved)

- A Recast-style generator in the game binary: `[NavMeshGen]` `bEnableNavMeshGenerator`, **`bDisableNavMeshRuntimeGen`**,
  `uNavMeshGenerationMode`, `uInputTerrainClipmapLevel`, **`bIgnoreProcGenMask`**, **`bIgnoreMissingNavMeshSeed`**,
  `bIgnoreTerrainTriangles`, `bEnableRemoveInvalidRecastTriangles`, `fVoxelWidth`, `fAgentWidth`, `fAgentHeight`,
  `fWalkableSlope`, `fWalkableStepHeight`, `fRegionMinSize`, `bEnableLinkDoors`, `bEnableGenerateCovers`,
  `bEnableGenerateWaypoints`, `bEnableNavMeshGenerationWait`, log `GameNavMeshGenStats.log`, task `PlanetNavMeshGen`.
- Dynamic cutting/injection (outposts, ships): `[DynamicNavmesh] bEnableDynamicNavmesh`, `DynamicNavmeshService`,
  `[Spaceship] bUseEmbeddedSpaceshipNavmesh`, `[LoadGame] fLoadGameDynamicNavMeshOpTimeoutInSec`,
  keywords `UpdatesDynamicNavmeshKeyword_DO`, `CutNavmeshWhenLandedKeyword_DO`.
- **Console command `GenerateNavMesh` (`gnm`): "Generates nav-mesh on the current cell."** Also `ToggleNavMesh`
  (`TNM`), `TogglePathLine` (`TPL`, "Toggle path display."), `PickLastRef` (`PLR`, "Select the last created ref for the
  console."), `GetCurrentAIProcedure`. (Help strings stand next to the names in the console table; `gnm` and `plr` pair
  unambiguously.)
- Pathing failures are logged as "Start Location is not on the navmesh", "<Cell %s has no navmesh>",
  "No Navmesh found, object not moved"; "Start and Goal are on the same Navmesh: 0x%08x" is a separate case from the
  `NavmeshInfo` (NAVI) search. `bFixNavmeshInfosOnLoad:Pathfinding` exists.
- None of the 15 shipped INI files sets any navmesh key (verified: no "nav"/"path" match), so defaults live in the exe.

Community: a Nexus forum thread ([13490792](https://forums.nexusmods.com/topic/13490792-npcs-not-moving-on-cold-load-boot),
search snippet only, page refused fetch; **unverified**, game not confirmed from the page) describes "very robust navmesh
generation" and NPCs stuck after loading at procedurally generated locations.

### 1.4 Decision: does a vanilla NPC move in a plugin worldspace with only BTD terrain and no NAVM?

**No, plan on it not moving** (supported hypothesis). Reasons: authored worldspaces ship their navmesh as NAVM (424 of
433 worldspaces; the four cities measured 820..2,708 each); the engine's runtime generator is tied to
planet/procgen generation (`PlanetNavMeshGen`, `bIgnoreProcGenMask`) and to seed markers (`bIgnoreMissingNavMeshSeed`);
the pathing code fails when "Start Location is not on the navmesh". Expected behaviour without navmesh: the actor spawns,
idles, turns, falls if there is no collision, but does not path (Fallout 4 / Skyrim experience; not measured in Starfield).

Unresolved, and cheap to test (section 3): whether `gnm` or placed `NavMeshSeedMarker` refs make the runtime generator
fill a plugin worldspace. If one of them works it is a quick path for test cells, not a faithful conversion.

---

## 2. Fallout 4 navmesh vs Starfield, and conversion vs generation

### 2.1 Checking FORMAT-GAP's "NAVM overlap 1.0" (verified on all records)

The claim holds for the **subrecord envelope only**: FO4 NAVM = `NVNM MNAM` (7,798) or `NVNM ONAM NNAM MNAM` (95);
Starfield = `NVNM MNAM` (56,573) plus 2 with `VMAD` and 1 with component subrecords. **Inside `NVNM` the layout differs.**
Parsing every record with each layout and requiring the parser to end exactly at the subrecord end:

| `NVNM` section | Fallout 4 v15 (7,893 / 7,893 exact) | Starfield v17 (56,570 / 56,576 exact) |
|---|---|---|
| header | version, magic, parent worldspace, (grid y,x i16 \| parent cell) | same |
| vertices | count + **12 B** (x,y,z f32), **game units** | count + **16 B** (x,y,z f32 + i32), **metres** |
| triangles | count + **21 B**: 3 vertex i16, 3 edge i16, height f32, 5 B flags | same size and order |
| edge links | count + 11 B (type u32, NAVM FormID, triangle i16, edge u8) | same |
| door triangles | count + 10 B (triangle i16, u32, door REFR FormID) | same |
| cover | count + **8 B** | count + **12 B** (u16, u16, u64 in Mutagen's schema) |
| cover-triangle map | count + 4 B | same |
| waypoints | count + 18 B | same |
| grid | divisor u32, max-distance 2 f32, min/max 6 f32, divisor^2 triangle lists | same |
| trailing | none | **4 B** (`0c 00 08 00` in 55,994 of 56,570) |

The 6 Starfield records that do not parse fail the vertex-index check when indices are read as i16 (probably u16
indices in very large navmeshes; **unresolved**).
Mutagen's Starfield schema (`SfInspect props NavmeshGeometry` / `NavmeshVertex` / `NavmeshTriangle` / `NavmeshCover`)
has exactly these fields, with the unknowns named `Unknown` (vertex i32, triangle byte) and `Unknown3` (trailing 4 B):
an independent confirmation, and it means a Mutagen writer can emit Starfield NAVM with typed fields.

Value comparison (all records):
- Triangle flags (u16 after the height) share the common values 0 / 16384 / 4 / 16388 / 2 in both games: same meaning,
  **supported hypothesis**. The last of the 5 bytes after the height (Mutagen: `Unknown` byte, `Flags` u16, `CoverFlags`
  u16) is 0 in every frequent FO4 value but 64 / 128 / 192 in at least 2.99 M Starfield triangles: new data,
  **unresolved**.
- Vertex extra i32: 1 (7.06 M) or 0 (2.89 M), a few hundred float-like values: **unresolved**.
- Edge-link types: FO4 0 (269,296), 1 (6,996), 2 (6,995); types 1/2 link a navmesh to itself (Red Rocket cave: 4 links,
  all to `0005FA8E` itself), i.e. ledge up/down (**supported hypothesis**). Starfield uses **only type 0** (163,630);
  jumps there are "traversal data" (`bEnableGenerateTraversalData`; **unresolved**).
- Doors: FO4 959 door triangles in 638 navmeshes, Starfield 929 in 641. Waypoints: FO4 11,060 in 377, Starfield 28,672
  in 2,264. Cover: FO4 1.15 M entries in 7,348 navmeshes, Starfield 7.86 M in 54,367.
- Navmesh size: FO4 median span 1,664 units (23.8 m), Starfield 5.3 m (Starfield splits much finer).

### 2.2 Red Rocket inventory (verified)

| Cell | NAVM | vertices / triangles | edge links (type 0/1/2) | doors | cover | waypoints |
|---|---|---|---|---|---|---|
| `RedRocketExt` (-17,19) | 001A0D0A | 1,495 / 2,354 | 154 / 4 / 3 | 0 | 333 | 0 |
| | 001ED4DD | 77 / 43 | 1 / 0 / 1 | 0 | 42 | 0 |
| | 001A0D0B | 11 / 9 | 2 / 0 / 0 | 0 | 3 | 0 |
| `RedRocketExt02` (-18,19) | 4 navmeshes | 957+124+9+7 / 1,493+159+3+5 | 139 / 2 / 2 | 0 | | |
| `RedRocketCaveExt` (-17,18) | 00019A70 | 1,298 / 1,995 | 144 / 0 / 0 | 0 | 262 | 3 |
| `POICC07` (-18,18) | 0015DC7A | 1,276 / 1,822 | 138 / 15 / 15 | 1 | 376 | 0 |
| `RedRocket01` (interior, the cave) | 0005FA8E | 327 / 377 | 0 / 2 / 2 | **1**: triangle 41 -> door REFR `0005E844` (base `0001ED77`, XTEL -> `0008EB65`) | 219 | 11 |
| | 0005FA98 | 4 / 2 | 0 | 0 | 4 | 0 |

**Cell grid mismatch** (verified arithmetic, FO4 units / 70 = metres as in S4): FO4 cells are 58.5 m, Starfield cells
100 m. With absolute positions and no origin shift, FO4 cell (-17,19) spans x -994.7..-936.2, y 1,111.8..1,170.3 and lies
**entirely inside Starfield cell (-10, 11)**; it holds the Red Rocket building (REFR `000211C0`). Cells x = -18 and
y = 18 each straddle a 100 m line (-1,000 and 1,100). Exterior navmeshes are per cell and must not cross cell borders
(CK wiki [Navmesh](https://ck.uesp.net/wiki/Navmesh), Skyrim-era; search snippet, **unverified** for Starfield, matching
the exact 100 m edges seen above).

### 2.3 Conversion: what it takes (supported hypothesis unless marked)

Per navmesh: scale vertices, grid bounds and finite triangle heights by 1/70; vertex 12 -> 16 B (extra i32: copy the
common value 1 or 0, **unresolved** which); triangles copy as is (flag meaning shared; set the new last byte to 0);
remap edge-link and door FormIDs to the converted plugin's stable FormIDs (`formids.json`); drop type 1/2 ledge links;
drop cover (8 -> 12 B semantics **unresolved**) for the first test; keep waypoints; recompute nothing in the grid
(uniform scaling keeps every triangle in the same bucket); append `0c 00 08 00`; parent = new worldspace + Starfield
grid cell. Interior navmeshes need only this. Exterior cells other than (-17,19) also need clipping at the 100 m lines,
re-welding across the old 58.5 m borders (FO4 type-0 portals say which edges are shared) and new portal links: medium
effort, plain geometry.

Navmesh info map: a plugin NAVM probably needs `NVMI` entries for paths that cross navmeshes; a path whose start and
goal lie on one navmesh uses a separate code path ("Start and Goal are on the same Navmesh"). **Unresolved** whether a
plugin must override the 53.9 MB `NAVI` (Mutagen models it: `NavigationMeshInfoMap.MapInfos`). First tests keep A and B
on one navmesh.

### 2.4 Generation with the Creation Kit (documented, not run)

`CreationKit.exe` is installed next to the game. Its command line (strings, verified to exist):

```
-FinalizeNavmeshes/UpdateNavmeshGeneration/UpdateNavmeshFinalization:<esm>
   (-Mode <all|main|ints|other> | -File <file> | Cell IDs...)
   [-Range <minX>,<maxX>,<minY>,<maxY> | -Part <part> <count>] [-Exclude <excludes>] [-Include <includes>]
   [-Basename <basename>] [-NoExplicitFilename] [-NoCheckIn] [-Combine]
 -File: a file of cell IDs (base 16); <Cell IDs...>: cell IDs (base 16)
 -Range: cell range of the main world space (implies -Mode main); -Part: split the job for parallel builds
 -Basename: default ESP basename; -NoCheckIn: "Generate an esp the classical way - not optimized for automated check-ins"
```

So `CreationKit.exe -UpdateNavmeshGeneration:FO4Port.esm <cell ids>` then `-FinalizeNavmeshes:...` is a plausible
batch route that writes the result to a separate ESP (**unresolved**: which worldspace "main" is, whether it loads a
plugin worldspace's BTD; "Unable to get land bounds from terrain manager during navmesh generation" suggests it uses the
terrain). CK GUI: navmesh tool with seed markers (generation needs a seed unless `bIgnoreMissingNavMeshSeed`), inclusion /
exclusion volumes. Running the CK is the owner's call; agents must not run it while the test chain owns the PC.

### 2.5 Options

| # | Route | Effort | For | Against | Use |
|---|---|---|---|---|---|
| R0 | nothing (hope for runtime generation) | 0 | generator exists | tied to planets / seeds (1.4) | measured by N1 |
| R1 | `gnm` in the cell | trivial | console command exists | debug aid; persistence and save behaviour unknown | probe N2 |
| R2 | place `NavMeshSeedMarker` refs | small | 2,683 vanilla cells use them | may be a CK-only input | probe N3 |
| R3 | **synthetic NAVM** from our writer (flat quad) | small | layout verified on 56,570 records; Mutagen typed | needs NAVI? finalization? | **first**: proves the writer, independent of FO4 data |
| R4 | **converted FO4 NAVM** | medium | faithful paths, doors, waypoints; one exterior cell needs no clipping | 100 m re-cut for other cells; cover / unknown bytes | **the slice route** |
| R5 | CK generation (GUI or `-UpdateNavmeshGeneration`) | owner time | official, finalizes | not FO4's navmesh; CK must load our worldspace | fallback, and to compare against R4 |

Recommendation: R3 then R4 for the slice; R1/R2 as 5-minute probes in the same session because they answer the open
runtime question for free.

---

## 3. The smallest in-game NPC test

### 3.1 Vanilla FormIDs (verified in Starfield.esm with `SfInspect npc`)

| Role | FormID | EditorID | Evidence |
|---|---|---|---|
| harmless humanoid | **0000CF96** | `LvlCitizen_NoOld` | NPC_, HumanRace 00347D, Unaggressive / Cowardly, `DefaultMasterPackageList_Human` 2C55CA, template `LCharCitizen` |
| creature (passive) | **001F3E88** | `PCM_Narion_Kreet_GrazerPreyA` | NPC_, OctopedeARace 015B13, Unaggressive, `DefaultMasterPackageList_Creature` 26F68A, flee/curious reaction lists; risk: a PCM creature may expect planet context |
| hostile humanoid (combat step) | **0010DD71** | `LvlSpacer_Male` | NPC_, HumanRace, `csSpacer_Assault`, `DefaultTemplate` `LvlSpacer` (NPC_ 27BB7B); the spacer template `EncSpacer01Template` 270255 carries `SpacerFaction` 27BB8C (chain between them not traced; hostility: supported, check in game) |
| hostile creature (later) | 001F3E89 | `PCM_Narion_Kreet_StalkerPredatorA` | NPC_, CCT_DummyRace |
| target marker | 0000003B / 00000034 | `XMarker` / `XMarkerHeading` | STAT |
| seed marker (probe N3) | 000001F8 | `NavMeshSeedMarker` | STAT |

Control cell: **`QASmoke`** (002BE3A9), an interior with one navmesh `002BE3AA`: 12 vertices, 14 triangles, a flat
554.7 m^2 rectangle x -14.8..8.9, y -8.8..14.8 at z = 0. Points A = (-8, -4, 0) and B = (5, 10, 0) are both on it
(verified, point-in-triangle), 19.1 m apart, on the **same** navmesh. (2026-10-12: still true, but N0 showed that this
pair cannot tell a walk from wandering; section 5 has the result and the replacement pair of N0b.)

### 3.2 Console recipe (N0, control; run by the queue runner, never by hand while the test chain runs)

One console command per line; the text after `#` is a note for this page, not console input.

```
coc QASmoke
tgm
player.setpos x -8
player.setpos y -4
player.setpos z 0.5
player.placeatme 0000CF96 1
plr                                   # PickLastRef: selects the actor just created
GetIsID 0000CF96                      # must print 1, else INCONCLUSIVE (wrong selection)
getpos x                              # t = 0: getpos x / y / z and GetCurrentAIProcedure
getpos y
getpos z
GetCurrentAIProcedure
player.setpos x 5                     # player to B; the console selection stays on the actor
player.setpos y 10
player.setpos z 0.5
tpl                                   # path line on, for the screenshots
cf "Actor.PathToReference" 14 1.0     # walk to the player (ref 00000014)
getpos x                              # repeat the four reads at t = 3, 8, 15, 30 s, screenshot each time
getpos y
getpos z
GetCurrentAIProcedure
```

`PathToReference` is in the exe's script-function table (next to Starfield-only functions such as `IsRampDown`), and
`cf` is "Calls a papyrus function on the targeted ref". The exact `cf` argument syntax for a reference (`14` vs
`player`) is **unresolved**; N0 settles it. Fallbacks in order: `cf "Actor.PathToReference" player 1.0`; for the hostile
actor `StartCombat player` (chase, needs `tgm`); `evp` after `SetPlayerTeammate 1` (follow). Never `MoveTo` /
`MoveToPackageLocation`: they teleport and prove nothing.

### 3.3 Experiment ladder (same steps, one variable each)

| Run | Place | Navmesh | Actor | Expect | A failure means |
|---|---|---|---|---|---|
| N0 | `QASmoke` | vanilla | vanilla citizen | ARRIVED | the command chain is wrong (fix before anything else) |
| W | test worldspace A and B | (player drop, existing `terrain` kind) | player | PASS | world problem, stop |
| N1 | test worldspace (TerrainExp1 flat ground, PR #57, e.g. A (-70,-70,10), B (-50,-50,10)) | none | vanilla citizen | NOMOVE (1.4) | if ARRIVED: runtime generation covers plugin worldspaces (R0 works) |
| N2 | same, `gnm` first, wait 5 s, `tnm` screenshot | runtime (console) | vanilla | ? | R1 does not work |
| N3 | same plugin + `NavMeshSeedMarker` refs at A, B | runtime (seed) | vanilla | ? | R2 does not work |
| N4 | same plugin + synthetic 2-triangle NAVM 40 x 40 m at z = 10 | ours | vanilla | ARRIVED | our NAVM writer or NAVI/finalization (navigation) |
| N5 | Commonwealth worldspace, Starfield cell (-10,11) | converted FO4 `RedRocketExt` (-17,19) | vanilla | ARRIVED | conversion of FO4 navmesh |
| N6 | `QASmoke`, then N5's place | vanilla / converted | **converted raider** (section 4) | ARRIVED | actor conversion |
| C1 | N5's place | converted | `LvlSpacer_Male` + `StartCombat player` | approaches within 10 m | combat AI / hostility |
| S1 | after N5 ARRIVED: `save npcnav`, `load npcnav`, re-read | | | same position +-0.5 m | persistence |

### 3.4 Proposed queue kind `npc_nav` (for scripts/game/testqueue.py, PR #59)

Spec (one test = one actor walk):

```json
{"kind": "npc_nav", "coc": "QASmoke", "npc": "0000CF96", "plugin_npc": false,
 "a": [-8, -4, 0], "b": [5, 10, 0], "method": "pathto_player", "speed": 1.0,
 "pre": [], "reads_s": [0, 3, 8, 15, 30], "expect": "ARRIVED", "control": true}
```

`pre` holds probe commands (`["gnm"]` for N2). `npc` gets the plugin index prefix when `plugin_npc` is true.
qstep steps: `coc`, wait for HUD, `tgm`, set player at A, `pre`, `placeatme`, `plr`, `GetIsID` (OCR must read 1),
position + `GetCurrentAIProcedure` reads (existing `readpos` OCR, extended to the selected ref), player to B, `tpl`,
the method command, timed reads and screenshots, `disable` the actor at the end (keeps the save clean).

Judge (positions in metres; `d` = horizontal distance to B):

| Verdict | Class | Rule |
|---|---|---|
| PASS | ARRIVED | min `d` <= 2.5 m within 30 s |
| FAIL | NOMOVE | moved < 0.5 m from t = 0 over 30 s (navigation, if the control passed and `W` passed) |
| FAIL | STALLED | moved >= 0.5 m, final `d` > 2.5 m (partial navmesh, blocked path) |
| FAIL | FELL | z below A.z - 3 m at any read (world, not navigation) |
| INCONCLUSIVE | SPAWN | `GetIsID` not 1, or t = 0 position more than 3 m from A |
| INCONCLUSIVE | UNREAD | a read or screenshot missing |
| INCONCLUSIVE | CONTROL | the batch's `control: true` test did not PASS (method broken, nothing else is judged) |

Report columns: verdict, class, `d0`, min `d`, path length from the reads, AI procedure codes, screenshots. This keeps
world (FELL, `W`), navigation (NOMOVE / STALLED with a passing control) and actor (N6 vs N0) apart.

---

## 4. Minimal FO4 NPC conversion (native behaviour, placeholder look)

Source: FO4 `LvlRaider` (NPC_ **0002898B**, the base of 210 placed raiders), whose template list `LCharRaider` (LVLN
00022E48) starts with `EncRaider01Template` (NPC_ 0003183A). Starfield analogue: `EncSpacer01Template` (NPC_ 270255).
Field mapping (FO4 subrecord -> Mutagen `Npc` property; all target properties exist in Mutagen 0.55.0-alpha.67,
verified with `SfInspect props Npc`):

| FO4 | value in LvlRaider | Starfield `Npc` | first conversion |
|---|---|---|---|
| `EDID` / `FULL` | LvlRaider / none (the template's `FULL` is a localized string ID) | `EditorID` / `Name` | `FO4_LvlRaider`, "Raider" |
| `RNAM` race | HumanRace 00013746 | `Race` | **HumanRace 00347D** |
| `TPLT` + `TPTA` (13 per-data-type templates) + ACBS template flags | LCharRaider, LCharRaiderFaceAndGender | `DefaultTemplate`, `TemplateActors`, `UseTemplateActors` | template = **LvlSpacer 27BB7B** for traits (look), inventory, voice: the placeholder |
| `SNAM` factions | RaiderFaction 0001CBED rank 0 | `Factions` | SpacerFaction 27BB8C first; own `FO4_RaiderFaction` later |
| `AIDT` | aggression/confidence/... | `Aggression`, `Confidence`, `EnergyLevel`, `Responsibility`, `Mood`, `Assistance` | copy (same enums) |
| `DPLT` / `ECOR` | DefaultMasterPackageList 00022B33 / DefaultCombatMasterPackageList 0004223F | `DefaultPackageList` / `CombatOverridePackageList` | `DefaultMasterPackageList_Human` 2C55CA / `DefaultCombatMasterPackageList` 0102ED (same EditorID) |
| `PKID` packages | none | `Packages` | none |
| `ZNAM` combat style | csRaiderRanged 0003183B | `CombatStyle` | csSpacer_Assault 2C562D (or csHuman_Ranged 2C5F7D) |
| `CNTO` items, `DOFT` outfit, `INAM` death item | LLI_Raider_Weapons, Outfit_Raider, LLD_Raider | `Items`, `DefaultOutfit`, `DeathItem` | inherit from the template (FO4 weapons and outfits need the weapon/skinning milestones) |
| `VTCK`, `CNAM` class | RaiderMale01, raiderClass | `Voice`, `Class` | inherit |
| `PNAM` head parts, `HCLF`, `FMRI/FMRS`, `MSDK/MSDV`, `QNAM`, `TETI/TEND` | FO4 face | `HeadParts`, `FaceMorphs`, `MorphBlends`, `Tints`, ... | placeholder: inherit traits |
| `PRKR`, `PRPS` (actor values) | | `Perks`, `Properties` | map by EditorID where it exists, else drop |
| `KWDA` | 2 keywords | `Keywords` | drop at first |
| `MWGT`, `NAM6`, `NAM4` | weight, height 1.0 | `Weight`, `HeightMin/Max` | copy height |
| (none) | | `SpaceOutfit`, `RDSAs`, `Components`, `ObjectTemplates`, `Pronoun` | inherit / empty |

Smallest converter step (proposal, PluginSpike is Claude's): one `NPC_` `FO4_LvlRaider` (stable FormID key
`NPC_:0002898B`) as above, plus one `ACHR` in the Commonwealth worldspace ~15 m from the Red Rocket building (REFR
`000211C0` at FO4 (-69,232, 80,304, 7,360) -> (-989.0, 1,147.2, 105.1) m, Starfield cell (-10,11)). Test it first with
`placeatme` in `QASmoke` (N6), where navigation is known good.

Mutagen: Starfield `Npc` is fully typed for the fields above; a few remain raw (`XALG`, `NAM5`, `UnknownAIDT`,
`HCLR/BCLR`, `ONA2`, `EYEC`). The repo already writes STAT/CELL/REFR/DOOR with it; NPC_ and NAVM writing are untested.
First offline check before any game run: copy `EncSpacer01Template` and `QASmoke`'s navmesh as new records, write,
re-read, compare bytes.

## 5. N0 result and the N0b design (2026-10-12)

N0 ran in game (queue `npc_nav_n0`, Starfield.exe 1.16.244, build 2470f876, 2026-10-12 00:17-01:12); everything else in
this section is offline. Tools: `scripts/actors/navmesh_points.py` (read-only analysis of a cell's navmesh and objects in
Starfield.esm) and `scripts/actors/npc_control.py` (the N0b plan and the N1 / N2 plans derived for it).

### 5.1 What N0 measured (verified: the runner's obs.json reads and console OCR)

The actor spawns at the player's feet at A (-8, -4, 0); the player is teleported to B (5, 10, 0), facing A, **before**
the command; then the reads at 3 / 8 / 15 / 30 s of game time. The arrival (`coc QASmoke`) reads -3.40 -1.10 0.00.

| Test | Actor | Command (console reply) | t0 -> reads (x, y) | Closer to B | Verdict (rule 2.5 m / 5 m) |
|---|---|---|---|---|---|
| N0_base | 002B211C | none | (-7.83, -5.28) -> (-8.28, -4.46), (-10.37, -0.68), (0.02, -3.72) | 5.4 m | FAIL WANDER |
| N0_ptr | 002B211C | `PathToRef player` (no error) | (-8.45, -5.54) -> (-11.43, -0.36), (-6.89, -2.44), (-3.14, -1.03) x2 | 6.8 m | PASS |
| N0_cf | 002B211C | `cf "Actor.PathToReference" player 1.0` -> "No script named Actor is attached to the object" | (-4.36, -2.46) -> (-3.37, -1.48), (-10.39, -6.11), (-0.09, -3.05) x2 | 1.6 m | FAIL STALLED |
| N0_follow | 002B211C | `SetPlayerTeammate 1`, `EvaluatePackage` | (-7.44, -5.68), never moved in 30 s | 0 | FAIL NONAV |
| N0_ptr_lvl | 0000CF96 | `PathToRef player` (no error) | (-7.62, -5.25) -> (-2.45, -1.85) x2, (-7.27, -0.70), (-2.26, 1.96) | 9.0 m | PASS |

Every actor, commanded or not, stayed in x -11.4..0.0, y -6.1..2.0, at most 8.6 m from the arrival marker, and never
came closer than **10.8 m** to B. N0_ptr ended 0.3 m from the arrival marker, 13.7 m from the player. A robot visible
near the camera in the shots from B is also in the baseline's shots (supported hypothesis: the save's companion); no
shot from B shows the actor.

- **Refuted:** "N0_ptr / N0_ptr_lvl PASS = PathToRef walks the citizen to the player". Their reads are N0_base's
  pattern, and the 5 m progress rule counted that pattern as a walk.
- **Verified:** `cf "Actor.PathToReference"` does not reach the native function (the reply above): the `cf` method is
  broken as written. `SetPlayerTeammate 1` + `EvaluatePackage` did not move the citizen in 30 s.
- **Unresolved:** whether `PathToRef` does anything on a sandboxing actor; it showed no effect beyond the baseline.

### 5.2 Why N0 could not tell them apart (verified offline, `navmesh_points.py analyze`)

`QASmoke` (002BE3A9) holds one NAVM, `002BE3AA`: 12 vertices, 14 triangles, 0 edge links, 0 door triangles, cover or
waypoints, all triangle flags 0x840, triangle heights 2.23..6.00 m; **one connected component** (shared edges only),
554.7 m^2, x -14.83..8.90, y -8.77..14.82, z 0, centre (-3.0, 3.1), 8 open border edges. The cell's 156 references:
80 floor tiles (`xxxMineGroundGravel6x6A`, 6 x 6 m) covering x -39..33, y -9..63, so the navmesh covers only the south
room of a much larger hall; 56 obstacles (`xxxMineWallSmooth6x6A` walls 6 m high, `xxxMineWallRoughPillarA` pillars),
16 ceiling panels at 6 m, 3 lights, 1 marker: `COCMarkerHeading` 002BE3AF at (-3.4, -1.1, 0), the `coc` arrival. Around
the navmesh: walls on the west (x -15), south (y -8.7) and east (x 9), pillars in the south-west and south-east corners,
**open to the north** (no wall between x -14.9 and 8.8 at y 15.1). No furniture, idle marker or other sandbox target on
the navmesh (a container and an activator stand in the hall at (28.8, 35.8) and (-33.7, 19.5)). Free space (navmesh
minus obstacles grown by 0.35 m): 509 m^2, one piece. The NAVM records cut no holes for the walls; the planner sees
the rectangle, a body needs the free space.

Old pair: A and B on the same component, navmesh path = free path = straight line = 19.1 m, the segment 3.8 m clear of
every obstacle. **The navmesh and the walls did not stop N0's walk.** What fits N0's numbers instead: an actor at A
that goes to the arrival marker gets 5.2 m closer to B, to the navmesh centre 8.5 m ("drift progress": the most an
actor gains by going where actors went on their own). N0 measured 5.4 / 6.8 / 9.0 m. **Supported hypothesis:** the
citizens' own package (sandbox) took them to the middle of the room, and on this pair that is 5-9 m "towards B".

### 5.3 N0b: a pair and a rule that separate them

Pair, chosen by rule (`navmesh_points.py`, deterministic; the candidates and their numbers are in the staged
`qasmoke_points.json`): **A (-12, 12, 0) -> B (6, 12, 0), 18.0 m along the open north side**; one navmesh
(triangles 9 and 2), navmesh path = free path = straight (ratio 1.00), the segment 2.83 m clear, the ends 2.84 / 2.83 m
clear (walls and the open navmesh edge; placeatme puts the actor up to ~1.7 m from the player), A 15.7 m and B 16.1 m
from the arrival marker, B 13.0 m from every N0 read. Going to the arrival marker gains 1.9 m, to the navmesh centre
(the worst place N0's actors went) 5.3 m. The rules: 15..25 m apart, both ends >= 2.5 m and the segment >= 1 m clear,
free path <= 1.05 x straight, A >= 8 m and B >= 12 m from the arrival marker, B >= 10 m from every N0 read, drift
progress <= 6 m; ranked by distance near the old 19.1 m, small drift, wide margins.

Rule (existing plan keys, so the integration-1012 runner plans and judges it unchanged): **PASS = within 3 m of the
player at B (not at the first read) or 12 m closer than at t0**; a baseline FAILs WANDER on the same numbers. 12 m is
3 m above N0's largest uncommanded progress (9.0 m) and twice the new pair's drift bound. Reads at 0 / 1 / 3 / 8 / 15 /
30 s (a 1 s read, so an actor that runs to the player is seen on the way, not INCONCLUSIVE EARLY). PR #75's spawn-read
approach rule stays (a commanded actor that came 12 m closer before the command is INCONCLUSIVE PRECOMMAND).
`tests/test_npc_control.py` judges N0's own reads both ways: the old rule gives N0's report (PASS for N0_ptr and
N0_ptr_lvl), the N0b rule gives N0_base PASS and FAIL STALLED for both PathToRef runs. No judge code changed.

| Test | Actor | Method | Expected | Basis |
|---|---|---|---|---|
| N0b_base | 002B211C EncCitizen01Template | none | PASS | supported hypothesis: N0's wander, B far from it (above) |
| N0b_ptr | same | `PathToRef player` | FAIL STALLED | supported hypothesis: N0 showed no effect; a PASS here proves PathToRef works |
| N0b_combat | same | `StartCombat player` | FAIL STALLED | supported hypothesis: AIDT Unaggressive, **Cowardly** (00 00 32 03 00 01 00, verified): it flees |
| N0b_spacer_base | 00270255 EncSpacer01Template | none | FAIL WANDER | supported hypothesis: SpacerFaction Enemy to the player and 6 reaction radii (verified), as N2b |
| N0b_spacer_combat | same | `StartCombat player` | PASS | AIDT Unaggressive, **Brave** (00 03 32 03 00 01 01, verified); may stop at weapon range |
| N0b_spacer_ptr | same | `PathToRef player` | PASS | comes anyway (hostile); credited only if N0b_spacer_base stays away |

The commanded tests are controls (`control: true`): they gate N1 / N2 FAILs of the same actor and method. The Spacer
gets `handle_tol` 3 m as in N2b. `cf_pathto_player` and `follow_player` have no N0b control: they failed in N0.

Reading: N0b_base PASS + a commanded citizen PASS = that command walks the citizen, and N1 / N2a FAILs with it count.
N0b_base PASS with both citizen commands failing = no console command walks a calm citizen (StartCombat's flight shows
as end d > d0); then only a PASS or the hostile Spacer says something about navigation. N0b_spacer_base WANDER = the
Spacer comes for the player on its own on this navmesh: a navigation reference that needs no command (its commanded
PASSes are not credited to the command). Risks (**unresolved**): the save's companion may fight the Spacer; a
cowardly citizen may flee off the navmesh to the north.

### 5.4 N1 and N2 switch their control to N0b

The control gate (`--control-queue`) finds N0b's controls by actor and method, so every queue judged against N0 should
be re-planned against N0b, into new queue folders, from plans derived with `npc_control.py derive`: the N0b rule,
`cf` / `follow` dropped (their FAIL could never count), a `combat_player` twin of the first `ptr_player` test, a
baseline of the actor in that world where the plan had none (it credits or voids the queue's commanded PASSes), N2's
QASmoke tests moved to the N0b pair. Staged in `C:\Modding\staging\npc_nav_<n>_b`:

| Plan | Tests | Switch? |
|---|---|---|
| `npc_nav_n1c_b` (exp2d, converted navmesh) | N1c_base, N1c_ptr_player, N1c_combat_player, N1c_cross_ptr | **yes**, the run that matters |
| `npc_nav_n2a_b` (raider calm probe in QASmoke) | N2a_base, N2a_ptr, N2a_combat (control_npc 002B211C) | **yes** |
| `npc_nav_n2b_b` (raider and Spacer baselines) | N2b_spacer_base, N2b_base (requires N2a_base in `npc_nav_n2a_b`) | yes (points and rule; no control queue, as N2b) |
| `npc_nav_n1a_b` / `npc_nav_n1b_b` (exp2b2 terrain only / + `gnm`) | base, ptr, combat, cross | optional: N1a's NONAV (0.0 m in 30 s) stands as raw evidence; the gate only re-labels it |

Each staged README has the exact `plan-npc` command (staging, install and plugins taken from the old queue,
`--control-queue C:\Modding\testqueue\npc_nav_n0b`, `--fresh`); plan `npc_nav_n2a_b` before `npc_nav_n2b_b`. The old
queues are not touched.

## Inspector commands added

```
dotnet run --project dotnet/SfInspect -- <Starfield.esm> navm <substr|*>     # NAVM per worldspace + interior total
dotnet run --project dotnet/SfInspect -- <Starfield.esm> npcfind <substr> [n]  # NPC_ by EditorID or race EditorID
dotnet run --project dotnet/SfInspect -- <Starfield.esm> npc 0000CF96,0010DD71 # every field; proves the FormID exists
dotnet run --project dotnet/SfInspect -- <Starfield.esm> props NavmeshGeometry # Mutagen schema of a record class
```
