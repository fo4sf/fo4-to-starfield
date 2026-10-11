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

Per worldspace (`SfInspect navm <name>`; the scratch scanner gives the same numbers, two independent readers):

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
overlay is 10..26 cells but carries one navmesh. NPCs and fauna still walk on generated terrain in normal play.

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

**No, plan on it not moving** (supported hypothesis). Reasons: authored worldspaces, including every master worldspace
a planet registers, ship their navmesh as NAVM (cities: 820..2,708 each); the engine's runtime generator is tied to
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

The 6 Starfield records that do not parse have vertex indices outside i16 (large navmeshes); **unresolved**.
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
| hostile humanoid (combat step) | **0010DD71** | `LvlSpacer_Male` | NPC_, HumanRace, `csSpacer_Assault`, template chain `LvlSpacer` 27BB7B; `EncSpacer01Template` 270255 carries `SpacerFaction` 27BB8C (hostility itself: supported, check in game) |
| hostile creature (later) | 001F3E89 | `PCM_Narion_Kreet_StalkerPredatorA` | NPC_, CCT_DummyRace |
| target marker | 0000003B / 00000034 | `XMarker` / `XMarkerHeading` | STAT |
| seed marker (probe N3) | 000001F8 | `NavMeshSeedMarker` | STAT |

Control cell: **`QASmoke`** (002BE3A9), an interior with one navmesh `002BE3AA`: 12 vertices, 14 triangles, a flat
554.7 m^2 rectangle x -14.8..8.9, y -8.8..14.8 at z = 0. Points A = (-8, -4, 0) and B = (5, 10, 0) are both on it
(verified, point-in-triangle), 19.1 m apart, on the **same** navmesh.

### 3.2 Console recipe (N0, control; run by the queue runner, never by hand while the test chain runs)

```
coc QASmoke
tgm
player.setpos x -8          ; player.setpos y -4 ; player.setpos z 0.5
player.placeatme 0000CF96 1
plr                         ; selects the actor just created (PickLastRef)
GetIsID 0000CF96            ; must print 1, else INCONCLUSIVE (wrong selection)
getpos x ; getpos y ; getpos z ; GetCurrentAIProcedure          -> t = 0
player.setpos x 5           ; player.setpos y 10 ; player.setpos z 0.5   (selection stays on the actor)
tpl                         ; path line on for the screenshots
cf "Actor.PathToReference" 14 1.0                                 ; walk to the player (ref 00000014)
getpos x ; getpos y ; getpos z ; GetCurrentAIProcedure          -> t = 3, 8, 15, 30 s; screenshot at each
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
| `EDID` / `FULL` | LvlRaider / "Raider" | `EditorID` / `Name` | `FO4_LvlRaider`, "Raider" (keep) |
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

## Inspector commands added

```
dotnet run --project dotnet/SfInspect -- <Starfield.esm> navm <substr|*>     # NAVM per worldspace + interior total
dotnet run --project dotnet/SfInspect -- <Starfield.esm> npcfind <substr> [n]  # NPC_ by EditorID or race EditorID
dotnet run --project dotnet/SfInspect -- <Starfield.esm> npc 0000CF96,0010DD71 # every field; proves the FormID exists
dotnet run --project dotnet/SfInspect -- <Starfield.esm> props NavmeshGeometry # Mutagen schema of a record class
```
