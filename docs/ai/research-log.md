# Research log

New findings go here (newest first). Each entry: question, method, evidence, **status**: verified /
supported hypothesis / unresolved. Older research lives in docs/JOURNAL.md and docs/spikes/; link, don't copy.

## 2026-10-12 Claude: where the shutter door's second panel is lost (multi-part FO4 doors)
- Question: FortHagen01 `0BD6A1` (`BldWoodPDoorShutter01`) shows OPEN, flips to CLOSE, but only one louvered panel
  swings (supervised_1011 tests 0004/0005, `r4_pre.png` / `r4_open.png`). The FO4 source animates two nodes; where is the
  second panel lost, and how many doors share the defect?
- Method (offline, local scripts; no game data in the repo): `door_motion.inspect` / `door_rig.plan` on the FO4 NIF;
  the converted NIF, manifest entry and FO4Port.esm of the pinned build `integ_1011` read back; vanilla Starfield doors
  from `Starfield - Meshes01.ba2` / `Starfield - Animations.ba2` (rig + `.af` read back with the external CALUMI library,
  `LoadAnimationSceneFromSFBGSFormatAndSaveToJsonC`) and their DOOR records from Starfield.esm; Fallout4.esm DOOR
  records (MODL) and the 16 pinned cell exports scanned with `door_motion.inspect`.
- Evidence, source: `Open` and `Close` each drive two nodes, `Left` (pivot 17.87, -24, 123.89 units, -107 degrees about z)
  and `Right` (pivot 17.87, +24, 123.89, +114 degrees), 1.0 / 0.97 s; each node holds one shape and its own
  `bhkNPCollisionObject` (body 0 / 1 of one compressed-mesh physics system).
- Evidence, converted (`integ_1011`): the manifest's door entry names the Akila template rig and animations; the NIF is
  root > `AK_Door_Anim_02_Root` > `Hinge01_Point` > `mesh001` (keyframed box, layer 2) > `Left:30`, and root > `Frame` >
  `Right:30` with no bone and no body. The template's own clip (Akila `open.af` read back) has **one track** of its 6
  bones: `Hinge01_Point`, 16 rotation keys to -90 degrees, no translation. So the Right panel has 0 bones, 0 tracks and
  0 bodies; nothing could move it.
- Cause in code: `nif.door_hinge` reads only the first controlled block of `Open` (offset 12 + 9), and
  `convert_static.convert_door` moves only that node's descendants; every other shape lands under the static `Frame`.
  The pipeline gate (`pipeline.Converter.convert_nif`) checks `door_hinge` alone and never consulted
  `door_motion.inspect`, which already reports `requires_additional_motion_support: true` for this model.
- Evidence, vanilla double door `IndIntRmSmWallMid_DoorA01` (`2BF4DA`): the same graph as the Akila door
  (`SimpleOpenClose01.agx`) but its own rig (7 bones) and clips: `Open` has one track per leaf (`Hinge01_Point` -93,
  `Hinge02_Point` +93 degrees, 48 rotation and 39 translation keys, a 0.149 m outward slide, frames 0-60); the NIF holds
  one physics system with 3 bodies: 0 on the root (frame), 1 on `Door02_Mesh`, 2 on `Door01_Mesh`. The graph is not
  the limit; a door moves as many parts as its own rig and clips have tracks.
- Evidence, clip convention (126 vanilla door rigs, first clip each): no clip has a track for every bone (tracks for
  animated bones only); all 391 translation tracks of bones with a nonzero bind start at 0 and all 83 rotation tracks
  of bones with a rotated bind start at identity, none at the bind: **clip keys are offsets from the bind**. CALUMI
  stores the values as given (no bind arithmetic in `SFBGS_AnimationScene.cpp`), and the independent `.af` reader of
  PR #53 (`claude/af-channel-layout`, 2026-10-11 entry there, 9 door families) found the same. `native_door.prepare`
  wrote absolute local keys for every bone, which would apply each bind twice; it had never run in game.
- Side finding: both FortHagen01 shutters (`0BD6A1`, `0BD69F`) are window shutters. Their walls
  (`BldWoodPSmWallWindowHole01`, render triangles within 12 units of the door plane projected onto it) are solid from
  the floor to 1.03 m above the reference; the opening is the panels' own span, 1.08-2.46 m high and about 0.65 m wide.
  The walk test cannot pass with both panels open. Side 1 stopped at x 12.16, beside a fallen static
  `FederalistChair01` (origin x 12.09, y 58.52, z 7.80; probably what stopped it), side -1 0.37 m before the plane,
  about one capsule radius from the wall below the sill.
- Blast radius, 16-cell build: 59 placed door models, 36 animate more than one node; 10 rigged models (38 references,
  76 batch_full door tests) have geometry outside the first node and lose it: `BldWoodPDbDoor01` (second leaf + knob),
  `BldWoodPDoorShutter01`, `HitDoorSm01` / `HitDoorLg01` (3 of 4 sliding panels frozen; the 4th swings on the Akila
  hinge instead of sliding), `IndMetalDbDoor01`, `UtilMetalDbDoor01`, `PaintedWoodDoorDouble01` (Parsons `06CF29`, the
  0.30 m block in the journal), `SwitchDoorExSmLatch01/02` (latches), `FancyBureauDoor01`. Fallout4.esm: 369 DOOR
  records, 227 models; 106 models (175 records) animate more than one node, 80 (139 records) have geometry outside the
  first node: 33 models (48 records) take the rig path, 17 are load doors (static by design), 18 not hinged (passable),
  12 not door-named (static).
- Fix (branch `claude/door-two-panels`): rigged doors with parts outside the first node
  (`convert_static.frozen_door_parts`) get their own rig and clips when `convert_batch.py --door-anim-dll` names the
  CALUMI library: `convert_static.convert_multipart_door` makes one rig bone per FO4 node (placed: root transform left
  out), one clip track per animated node keyed from the bind (`native_door.prepare`; animated bones get identity binds,
  `door_rig.animated_identity_binds`), one keyframed box per moving bone, the rig and `Open`/`Close` `.af` + `.afx` under
  `meshes/<model>/characterassets` and `/animations`, and a DOOR entry with origin offset 0 whose BNAM / CNAM point there.
  Without the library the template door stays and the manifest lists `door_frozen_parts`.
- Offline checks (re-conversion of every placed door model into `C:\Modding\staging\door_two_panels`, 57 models, 17 s):
  47 models byte-identical to `integ_1011` (NIF and manifest entry), the 10 above changed. `scripts/oracles/door_panels.py`
  with CALUMI read-back: before 23 of 40 parts move (17 frozen), after 40 of 40 have an Open and a Close track and a
  moving body; `door_bodies.py` 0 errors (moving bodies per door 1 -> 2 or 4). Shutter: rig 3 bones, `Open.af` 2 tracks
  (`Left` -107, `Right` +114 degrees, 31 rotation keys, no translation), `Close.af` 2 tracks (30 keys), bodies on `Left`
  and `Right`. Plugin overlay (`C:\Modding\staging\door_two_panels_esm`, pinned manifest with the 10 items swapped):
  54,271 records, 48 changed: 10 DOOR (BNAM, CNAM, OBND) and their 38 REFR (position only; shutter `00BE6A` now at the
  FO4 position 12.8, 58.514, 7.314); FormIDs unchanged.
- Status: where the panel is lost **verified** (offline: code path, converted NIF, manifest, template clip read-back;
  symptom from the in-game screenshots). Vanilla clips store offsets from the bind: **verified** offline (two readers);
  that the engine applies ours that way: **supported hypothesis** (no clip of ours has played yet; the composition order
  with a rotated bind stays open, which identity binds on animated bones make moot). "Our rig + clips + per-leaf
  keyframed boxes open both panels in game" **unresolved** (in-game test plan: docs/spikes/WP-doors-research.md,
  "Multi-part doors"). Shutter walk test impossible **verified** for `0BD6A1` (wall geometry), **supported** for
  `0BD69F` (same wall pieces).

## 2026-10-12 Claude: why the NPC control N0 could not tell a commanded walk from wandering
- Question: N0 (`npc_nav_n0`, QASmoke) passed `PathToRef` twice and failed its no-command baseline; is that a walk, a
  navmesh problem, or wander? What pair and rule would separate them (N0b)?
- Method: N0's obs.json reads and console OCR (read only); `scripts/actors/navmesh_points.py analyze` on Starfield.esm:
  QASmoke's NAVM parsed with `src/fo4sf/navmesh.py`, triangle graph and components, every reference's OBND (Starfield:
  6 f32, metres) placed and classified, free space at 0.1 m, corridor path (funnel), free path, segment clearance and
  "drift progress" (how much closer to B an actor gets by going where actors went on their own); NPC_ AIDT bytes.
  Details: [docs/actors/npc-navigation.md](../actors/npc-navigation.md) section 5.
- Evidence: every N0 actor, commanded or not, stayed in x -11.4..0.0, y -6.1..2.0 and never came closer than 10.8 m to B
  (5, 10); base 5.4 m, PathToRef 6.8 / 9.0 m, `cf "Actor.PathToReference"` replied "No script named Actor is attached to
  the object", SetPlayerTeammate + EvaluatePackage stood still 30 s. NAVM 002BE3AA: 12 vertices, 14 triangles, no
  links, one component of 554.7 m^2; the old straight path = navmesh path = free path, 3.8 m clear of every wall and
  pillar; going to the arrival marker (COCMarkerHeading 002BE3AF, -3.4, -1.1) gains 5.2 m, to the navmesh centre 8.5 m.
  No sandbox furniture or idle marker on the navmesh. AIDT: EncCitizen01Template Unaggressive / Cowardly, EncSpacer01Template
  Unaggressive / Brave.
- Status: the navmesh did not block N0 (**verified**); the `cf` method as written cannot reach PathToReference
  (**verified**); "N0's PathToRef PASSes were a walk" **refuted** (wander pattern, judged by a 5 m rule); what moved
  the citizens (their package towards the middle of the room, the player, or both) **unresolved** (fix pass: N0_base
  ended 4.3 m from the marker and 7.4 m from the centre, and three citizens walked up to the player before the
  command: N0_cf 4.4 m, N1c_ptr_player 9.5 m, N1c_follow_player 3.4 m; the largest move from t0 on record is 14.1 m,
  N1c_cross_ptr); whether PathToRef or StartCombat walks an actor to the player (**unresolved**, N0b: A (5.5, -4.5, 0)
  -> B (-12, 12, 0), 24 m, the walk judged from t0, PASS = within 3 m after 18 m or 18 m closer, staged
  `C:\Modding\staging\npc_nav_n0b`, queue `npc_nav_n0b`). Also found: QASmoke's 16 ceiling panels (rotation 0, 90,
  270 degrees) lie flat only when rotated Z first; `fo4sf.exterior.ref_matrix` (X, Y, Z) stands them on edge
  (**unresolved** for references that combine Y and Z rotations; no effect on this analysis).

## 2026-10-10 Claude: how Starfield makes a body movable
- Question: what must a converted body and record carry so Starfield simulates it (FO4 loose items, known unknown #6)?
- Method: field-level dumps with `hktagfile` (field names from the files' own type tables) of vanilla Static, MiscItem,
  MoveableStatic and animated-door bodies; `SfInspect models` / `mstt` for which records use which meshes; scans of
  ~10,400 vanilla item NIFs and 400 models per record type (local scripts, not in the repo).
- Evidence (body cinfo): `motionType` static 0 / keyframed 1 / **dynamic 2**; `flags` 0 / 0x4 / **0x8a**;
  `collisionFilterInfo` = collision layer (1 STATIC, 2 ANIMSTATIC, 4 CLUTTER, 26); dynamic bodies have `mass` (kg),
  `motionPropertiesId` 0 into the system's `motionProperties` array (Bethesda defaults: gravity 1, max speed 100 / 200,
  damping 0.1 / 0.05) and an `hknpRefMassDistribution`. Static box blob offsets: 232 flags, 240 layer, 264 motionType
  (an older comment called 240 the motion type: **corrected**).
- Evidence (mass distribution, 30 of 30 vanilla box items): centre of mass = box centre; volume = the box grown by its
  convex radius (ratio 1.000); inertia = per-kg inertia of that grown box x **1.5** (ratios 1.499-1.500); axes identity.
- Evidence (records / NIF): layer CLUTTER alone does not move anything (the ingot `Ingot_PreciousMetal_01` is a Static);
  movable set dressing is **MoveableStatic** (`DATA = 4` on every vanilla one checked) or MiscItem. 145 of 150 MiscItem
  NIFs have **BSXFlags 0x42** (statics mostly 0x2); the collision object is on the root node. MiscItem physics layouts
  add exactly one class over the static ones: `hknpMassDistribution`.
- FO4 side: motion cinfo stride **112** bytes (skeleton: ids 0..16, inverse masses 0.1 / 0.2); pencil 0.5 kg, tin can
  5 kg, clipboard 4 kg.
- Status: field meanings **verified** (named by the type tables, consistent across samples); inertia factor 1.5
  **verified** (30 items); "a dynamic body on a MoveableStatic is pushable in game" **supported hypothesis** until the
  in-game test. Vanilla dynamic shapes also carry `hknpShapeMassProperties`; ours don't: a converted can, a compound cone and the rigid skeleton moved when pushed in game (journal 2026-10-10), so the body's mass distribution is enough: **supported hypothesis**. Principal axes of non-box hulls come out in ascending-moment order where vanilla keeps the near-identity order; the tensors agree (QA on PR #41, 12 items, |dot| >= 0.988): a convention difference, not an error.

## 2026-10-10 Claude: why the converted skeleton spawns standing (FO4 `XRGD` ragdoll pose)
- Question: in game the rigid skeleton (Vault 114 `05C942`) ended about 1 m sideways and 0.88 m lower than placed. Why?
- Method: render bounds vs collision bounds of the converted NIF; `XRGD` of the Vault 114 skeleton REFRs read straight
  from Fallout4.esm (local script: linear record walk, zlib records, `recon.iter_subrecords`).
- Evidence: the converted render mesh is the skinned mesh in its bind pose, a standing figure (z 0.01-1.88 m, 0.44 m
  deep); the collision built from the NIF's bone nodes does not match it (y -0.54..0.92). FO4 lays placed skeletons down
  with per-reference ragdoll data: `05C942` (SkeletonClothed01, 17 bodies) has `XRGD` of 476 bytes = 17 x 28; `05C94F`
  (SkeletonBareBody01) 504 = 18 x 28. Entry: u8 0 (+3 bytes that look like garbage), 3 floats position, 3 floats
  rotation; the first entry has position 0 and a rotation, the others bone-length offsets (13-33 game units) and
  rotations in radians. Loose bone props (BonesSkull, BonesRibCage) have no `XRGD`. Mutagen's Fallout 4 library reads
  it (`PlacedObject.RagdollData`, type `RagdollData`).
- Status: "one 28-byte entry per ragdoll body, in body order, local position (game units) + rotation (radians)":
  **supported hypothesis** (2 references; parent order and Euler convention unverified). Consequence: phase A spawns
  skeletons in bind pose (standing) and they topple; FO4 shows them lying. Fix: export `XRGD` (Fo4Export, Codex's file)
  and bake each placement's pose into its mesh and rigid body (needs skin weights: phase B work).

## 2026-10-10 Claude: Starfield dynamic compound bodies
- Question: how does Starfield store one movable body made of several convex pieces (FO4 boxes, cones, tools)?
- Method: field dumps (`hktagfile`) of vanilla single-body dynamic MiscItem / MoveableStatic NIFs; checks against the
  children decoded through the instance pointers (local scripts).
- Evidence: single-body dynamic shapes in vanilla: convex 540, **compound 273**, box 109, LOD 19, cylinder 17, sphere 2.
  A dynamic compound is one `hknpCompoundShape` (type 11, dispatch 3): instances (identity transforms in every sample;
  vertices are already in compound space), `numShapeKeyBits` = bit length of the instance count (2->2, 3->2, 4->3,
  8->4, 19->5; 40 of 40), `estimatedNumShapeKeys` = `numAllocated` = count, `aabb` = union of child boxes (child
  vertices +/- child convex radius; 25 of 25 exact), a SIMD tree whose root is always an inner node and whose leaf boxes
  are the child boxes (exact), `boundingRadius` between 0.78 and 1.0 of the aabb half-diagonal.
- Mass distribution: a compound's is a **solid box equal to its aabb** (centre, volume, inertia per kg x 1.5, identity
  axes; 40 of 40 exact). A single convex body's is the grown hull (40 vanilla convex items: volume 0.98-1.0 for most,
  worst 0.82; centre within 7 mm), not its aabb.
- Status: compound layout and both mass rules **verified** on vanilla files; converted FO4 compounds pass the same checks
  offline. In-game behaviour: **supported hypothesis** until tested.
## 2026-10-11 Claude: load-door teleports checked against the re-exported 16 cells (follow-up to 2026-10-10)
- Question: the 2026-10-10 entry left open which load-door pairs exist among the pinned cells, because 12 of the 15 cell
  exports predated the exporter's persistent-reference export and held no XTEL.
- Method: the 15 pinned cells plus FortHagen02 re-exported with the current Fo4Export (schema 2; owner's local copy
  C:\Modding\staging\exports_1011, read-only, not in Git); `teleport_destination` entries counted per cell (Python over
  the JSON); then `dotnet/PluginSpike` (branch claude/load-door-teleport) offline on the staging manifest (4,014 items,
  10 load doors) + those 16 exports into a scratch folder seeded with the staging formids.json; the written FO4Port.esm
  read back with `PluginSpike teleports`. No deploy, no game.
- Evidence: 34 XTELs in the 16 exports (1 to 4 per cell). Exactly 2 have their destination reference in the set:
  FortHagen01 `0CD469` <-> FortHagen02 `0CD46A` (UtilMetalDbDoorLoad01, flags 0). Of the other 32, 28 lead to references
  outside the set (4 of them FO4 elevator doors with transition_interior set) and 4 sit on marker-based doors the
  converter never places (RedRocket01 `05E844` AutoloadDoor `autoloadmarker01.nif`; Vault111Cryo `248AAD` and `148B69`
  InvisibleLoad01HiddenMinUse `invisibledoor01.nif`, `01F180` AutoloadDoorNoText). XTEL flags: 32 x 0, 2 x NoLoadScreen.
  Writer output: "2 references linked (1 mutual pairs, 0 one-way), 28 destinations not in this build, 4 sources not
  placed, 0 issues"; `teleports.json` now carries `SourceNotPlaced` and `UnplacedSources` (new, so all 34 are accounted
  for: 2 + 28 + 4; PluginSpike.Tests asserts it). Read-back: FO4Port_FortHagen01 `00C7A7` <-> FO4Port_FortHagen02 `00DA69`,
  base FO4Port_utilmetaldbdoorload01, both persistent, record flags 0x400, back=True, arrival (-54.52, 19.27, -7.31) m
  and (-10.05, 43.95, -10.97) m, rotZ +1.571 / -1.571, transition Null. Stable FormIDs against the staging map: 0 changed,
  0 removed, 3,317 new (3,312 REFR from the now-exported persistent references and FortHagen02, 4 `DOOR:`, 1 `CELL:`).
- Status: "the next build of these 16 cells has exactly one teleporting pair (FortHagen01 <-> FortHagen02); every other
  load door stays shut and solid": **verified** offline; closes the 2026-10-10 unresolved item. That the pair teleports
  in game: **unresolved** (not deployed).

## 2026-10-10 Claude: how Starfield load doors teleport (XTEL), and what the port now writes
- Question: how is a vanilla Starfield load door set up (base record, flags, destination, persistence), so an FO4 load
  door between two converted cells can teleport instead of standing shut (docs/JOURNAL.md 2026-10-08, "load doors swung
  open onto the void")?
- Method: new SfInspect verbs, read-only on Starfield.esm: `teleports` (every placed object with a TeleportDestination in
  interior and worldspace cells, its base record, its destination; 17 s for 3,291,860 placed objects) and
  `doorrec <EditorID>` (all properties of a DOOR record).
- Evidence: 964 placed objects carry an XTEL. All 964: the base is a DOOR; the reference is in its cell's persistent group
  with record flag 0x400; the destination reference exists (619 sources in interiors, 244 destinations in the same cell)
  and its own XTEL links back. TransitionInterior: 0 of 964. XTEL flags: 0 for 960, NoLoadScreen (2) for 4,
  RelativePosition never. Arrival point to the destination door's position: median 1.00 m, p10 0.00, p90 5.67 m, so it
  is a separate absolute position in the destination cell. DOOR bases: 506 with an AnimationGraphComponent (visible load
  doors, e.g. `IndIntRmSmWallMid_DoorA01_Load` 2AC325: graph SimpleOpenClose06_Load.agx, Flags 0, SoundLevel Normal,
  FacingAxisOverride BasedOnBounds, Name "Door"), 458 without any component (`LoadElevator_InvisibleDoor` 21F2A7: 322
  references, Flags Hidden, MarkerDummyA.nif; `AutoloadDoor_Cave` 24F9CE: 89, Flags Automatic, scripted).
- Status: "Starfield load door = persistent DOOR reference (flag 0x400) + XTEL (destination door reference, absolute
  arrival position/rotation, flags), both ends linking each other, no TransitionInterior": **verified** (964 of 964).
  "A DOOR without an animation graph teleports": **verified** for the vanilla graph-less bases (458 references), which are
  hidden or automatic; "a visible graph-less DOOR teleports on the player's activation" (what the port writes):
  **supported hypothesis** (same engine lineage as FO4, where XTEL doors teleport whatever their animation); in-game
  check pending.
- Implemented (dotnet/PluginSpike, new TeleportLinks.cs): manifest `load_door` items become graph-less DOOR records
  (Flags 0, SoundLevel Normal, FacingAxisOverride BasedOnBounds, OBND from the model bounds `pipeline.py` now writes
  into the manifest). After all cells are placed, every exported XTEL whose destination reference is placed in the same
  build (any cell JSON given on the command line) is written on the reference (position / 70, rotation and flags as
  exported, TransitionInterior never) and both ends move to the persistent group with flag 0x400. Doors whose other end
  is not in the build get no XTEL (they stay shut and solid) and are listed in `<out>/teleports.json`.
  `PluginSpike teleports <FO4Port.esm>` reads a plugin back (CreateFromBinaryOverlay) and lists its links.
- Offline check: staging manifest (4,014 items, 10 load doors) + the 15 pinned cell JSONs + a fresh export of FortHagen02
  (scratch, not staging): "2 references linked (1 mutual pairs, 0 one-way), 6 destinations not in this build, 0 issues";
  read-back: FO4Port_FortHagen01 0043B7 <-> FO4Port_FortHagen02 00D6C6 (both `FO4Port_utilmetaldbdoorload01`, persistent,
  flags 0x400, back=True), arrival (-10.05, 43.95, -10.97) m = FO4 (-703.2, 3076.6, -768) / 70. Rebuilt on the staging
  formids.json: 0 existing FormIDs changed; new keys are FortHagen02, 4 `DOOR:` ids for load doors that never had one
  (6 others reuse the DOOR: id they had before 2026-10-08) and 54 REFR keys that the origin/main writer adds as well.
  Synthetic test: dotnet/PluginSpike.Tests (pair, one-way, destination outside the build, STAT source, relative-position
  flag, idempotence, binary round trip); tests/test_load_door_policy.py covers the manifest bounds.
- Finding on the pinned build: 12 of the 15 cell JSONs predate the exporter's persistent-group export (no
  `schema_version`, 2026-10-07) and contain no persistent reference at all, so no FO4 load door with an XTEL (they are
  persistent in FO4) and nothing to link. Only FortHagen01, MuseumOfWitchcraft01 and Vault75 (schema 2, 2026-10-08) carry
  XTELs: 6, of which 5 lead to the Commonwealth worldspace (cell 018AA2) and 1 to FortHagen02. **Unresolved** until the
  cells are re-exported: which pairs among the 15 exist at all (resolved 2026-10-11, entry above: one pair). Also open: FO4 teleport "doors" that are not door-named
  (`MetalTrapdoorLadder01`, `RoofHatch01` here) stay STAT bases and would be reported as issues, not linked.
## 2026-10-10 Claude: the 7 Prydwen route falls; FO4 ignores a NIF's root-node transform
- Question: what collision lies under the 7 `FALL` routes of the pinned build's Prydwen run
  (`staging\multi_next\run_PrydwenHull01`, `route_eval`: routes 12, 13, 15, 18, 20, 28, 29)?
- Method (offline; scratch scripts, not in the repo): placed every nearby model's FO4 collision
  (`routes.collision_bodies`) and sampled it under each route's start, its walk (heading, 4.6 m/s x `walk_ms`) and its
  end read; vertical sections and top views; compared with FO4's own cell collision, the precombined physics
  `Meshes\PreCombined\0005C92E_Physics.NIF` (one compressed-mesh body, 209,035 triangles, cell space), and with the
  staged NIFs.
- **A. Routes 12, 13, 15, 18 (`PryPlatformInCornerStairs01/02`): route-planning error.** These models are railing
  frames around a stairwell. Their only 20-50 degree triangles are small bevels on the posts; the planner's
  `sloped-collision` ramp had its low and high ends 0.03-0.04 m apart under a 0.91 m rise (88 degrees), so the heading
  was meaningless. Each walk (2.3 m) left the deck (z -7.31) into the stairwell next to it and went down
  `PryCatwalkStairsEnt01`: end z -7.98 / -7.99 / -7.99 at points where FO4's own Ent01 treads are at z -8.06
  (routes 13, 15, 18). Route 12's end repeats its start y (likely OCR); its x and z fit the same walk down Ent01
  `06E066`. The converted collision did what FO4's does. Same bogus ramp on `PryPlatformWallStairs01` (route 14 STUCK,
  rise 0.02 m; routes 33, 43 not run). Every other stair ramp in the 15 cells is at most 46.4 degrees end to end
  (`V111HallStairs01`'s helper). **Verified** (offline, FO4 data).
- **B. Routes 20, 28, 29 (`PryCatwalkStairs01` 068A2A, 06E03B, 06E03D): converter bug.** Each flight continues a
  `PryCatwalkStairsEnt02` (068A29, 06E03A, 06E03E). Ent02's NIF root node is rotated 180 degrees about z and its
  `Stairs` node another 180. The converter (and routes.py) composed the root, so the converted Ent02 climbs north
  instead of south: its foot hangs over the deck opening and the next flight's foot is 1.8 m above it. The three
  starts (z -5.23, 0.8 m before the flight) were over the converted Ent02's lower steps: start reads z -6.86 / -6.90,
  then 0.3 m of walking into the flight's underside, end z -7.04. Staged `prycatwalkstairsent02.nif`: render treads
  rise towards +y (z 0.03 to 1.86) and the helper node sits at y -1.738; staged `prycatwalkstairs01.nif` rises towards
  -y with its helper at +1.73. The same turn explains routes 19, 27, 30 ("start not reached", starts fell through the
  opening to z -12.3 / -14.95).
- **Evidence that the root transform is not applied in game:** all 89 references (15 models, 6 cells) with a rotated
  root whose collision is in their cell's precombined physics match it only with the root left out: 100% of sampled
  collision vertices within 2 cm, against 0-18% with it applied. None matches the other way. 97 references are in no
  precombine; 8 door references (`HitDoorSm01/Lg01`, Cambridge, frame only) match 34-38%, again only without the root. Ent02 itself is not precombined: without
  its root it joins its flight into one straight stair from the deck (z -7.31) to the catwalk (z -3.65), and routes
  20/28/29 then start 0.33 m above its top steps. Posters with rotated roots (`PosterAbraxo`, `PosterCivil`) only hang
  upright without the root. Status: collision **verified** (FO4's precombined physics); render geometry **supported
  hypothesis** (posters, stair layout; no in-game check yet).
- Scope in the pinned build: 44 of 4,014 converted models have a rotated root (none has a root translation or scale),
  232 placements. 30 carry their collision on the root node, so the render was turned and the collision was not
  (`DinerIntCounter01`, `IndFrameCat256x256*` (Vault 114, Vault 95), `DeskLamp01`, `VltCatwalkRailStraight01`, ...).
  4 carry it on child nodes and were turned with the render (Ent02, `Jukebox01`, `HitDoorSmBroken01`,
  `GoreHumanLegR`). 2 are rigged doors (`HitDoorSm01/Lg01`, Cambridge). 8 are render-only posters.
- Fix: `nif.world_transforms(placed=True)` (and `fo4_trishapes` / `door_hinge`) leaves out the scene root's own
  transform. `convert_static` uses it for geometry, native collision nodes and door pivots; `routes.py` uses it, and
  rejects a ramp whose ends are steeper than 60 degrees. Offline reconversion of Ent02: render and collision rise
  towards -y, helper node at y +1.738, as Stairs01. Routes regenerated for all 15 cells (scratch): 510 to 501;
  9 bogus Prydwen platform-stair routes removed; 23 changed (4 Prydwen Ent02 routes now start on the deck at
  y 15.31 / 37.25 heading south; 19 Cambridge routes for `HitDoorSm01/Lg01` and `HitFloorRailStairsFront01L/R`);
  the other 478 are identical.
- Not done: no rebuild or deploy (the pinned build is unchanged), no in-game run. The door modules owned by Codex
  (`door_motion`, `door_rig`) still use the default composition.
## 2026-10-11 Claude: Fallout 4 navmesh converted onto the native Red Rocket terrain (exp2d), NAVI for plugins, N1
- Question: can FO4's NAVM records around Red Rocket become Starfield NAVM records in the overlay worldspace's 100 m
  cells (links across the new cell lines included), does a plugin need navmesh info (NAVI / NVMI) and in what form, and
  which N1 tests separate world, navigation and actor failures? Write-up:
  [docs/actors/navmesh-conversion.md](../actors/navmesh-conversion.md).
- Method: `src/fo4sf/navmesh.py` (both NVNM layouts, NVMI, cell cut with canonical point keys, grid, validator),
  `dotnet/TerrainExp2` navmesh mode (NAVM + NAVI override), `scripts/terrain/make_exp2d.py` (stage / check / npc), raw
  scans of Fallout4.esm, Starfield.esm and the official Starfield plugins (scratch scripts), Mutagen round trips;
  `tests/test_navmesh.py` (synthetic). Staged `C:\Modding\staging\terrain_exp2d`, `terrain_exp2b2_npc`,
  `npc_nav_n1a` / `n1b` / `n1c`. Not deployed, not run in game.
- Evidence:
  - **verified**: triangle field order height, u8 extra, u16 flags, u16 cover (edge-link bits agree with the edge
    values in 63,875 FO4 and 256,726 Starfield triangles, 5,970 / 1 disagreements one byte earlier): corrects PR #61's
    reading of the flags offset; edge links name the target triangle's edge and come in symmetric pairs (7,606 FO4,
    7,196 CydoniaCity); parent grid is y then x (105 + 2,708 of 105 + 2,708).
  - **verified**: the search grid rule (divisor, bounds, cell size) on 1,004 / 1,004 akilacity navmeshes; lists
    identical in 873, a superset in all.
  - **verified**: NVMI layout on all 56,631 Starfield.esm entries (traversals and a 5-byte tail of cell-border bits
    after the doors / outline); merged-to = link targets (56,502 / 56,563), location = vertex mean (56,490), border bits.
  - **verified**: every official plugin with navmesh overrides NAVI `00000FF1` with only its own entries (SFBGS003 920,
    SFBGS00D 4,126, BlueprintShips 507, SFBGS006 71 vs 56,631): the engine merges NVMI per navmesh (**supported**).
  - **verified** (offline): 105 FO4 navmeshes -> 156 NAVM, 68,132 triangles, 4,104 link pairs, every NVNM byte-identical
    to the Python reference writer, 0 structural problems, cell-line links exact, exp2c's 10,301 records unchanged;
    41,207 of 43,901 vertices within 0.5 m of the BTD or the converted collision, 2,674 of the rest equally off FO4's
    own LAND and source collision.
  - **verified**: Mutagen 0.55.0-alpha.67 needs the grid lists as one raw array, the parent coordinates swapped, an
    empty MNAM list; vanilla NAVM/NAVI form version 581.
- Status: conversion and records **verified** offline; that the engine uses them (and the merged-world offset for
  navmesh) **unresolved** until N1c runs; vertex i32 meaning **supported**; triangle extra byte, NVMI f32, cover,
  outline algorithm, traversals **unresolved**. PR #68's staged N1 requires a terrain test that read INCONCLUSIVE MOVED
  and would never run; N1a / N1b / N1c bring their own world checks.

## 2026-10-12 Claude: correction, which teleports raise "Boundary Reached" in a merged overlay
- Question: core64c's first plan (PR #76) and PR #74's commonwealth-scale.md said a single teleport more than about
  4 cells from where the player stood raised "Boundary Reached", and that core64b's 300 m hops were verified safe.
  What do the runner reports actually show?
- Method: `scripts/terrain/teleport_audit.py` (new, synthetic test `test_teleport_audit`) rebuilds every teleport of
  the eight overlay queues (core64, core64b, exp2b, exp2b2, exp2b3, exp2c, exp2d, exp3) from spec.json + obs.json,
  hops as qstep.ps1 makes them, and judges it by the read that follows; counted only from a position where the
  previous teleport landed. qstep types setpos x, then y, then z, so each setpos moves one axis.
- Evidence (**verified** counts): of 145 teleports that moved the player at most 2 cells (100 m) along each axis, 144
  landed (the other in exp2b's second attempt, where the player fell through the world at most points); of 28 that
  moved 3 or more cells, 11 relocated the player 8.2 to 11.8 km further along that axis or hung at the drop height
  (all 6 in core64: 292.6 m east, 303.5 m south, 296.2 m west and three diagonals of 3 to 4 cells), 17 landed. In
  exp3, 250.5 and 267.0 m single-axis moves within 2 cells landed and a 248.7 m move across 3 cells hung. core64b's
  hops were at most 187.4 m per axis.
- Status: "about 4 cells" and "300 m hops are safe" **refuted**; a per-setpos distance limit (230 to 292 m, which
  core64 alone fits) **refuted** by exp3; "at most 2 cells per axis lands, 3 or more is a risk" **supported
  hypothesis**; the mechanism (a 5 x 5 loaded grid?) **unresolved**. core64c's plan now keeps every teleport within
  200 m per axis (docs/terrain/core64c.md "Teleport rule"); PR #74's commonwealth-scale.md still states the old claim.

## 2026-10-12 Claude: core64c, every Fallout4.esm exterior object of the 64-cell core on core64, staged
- Question: can ALL Fallout 4 exterior objects of the core (which covers the whole playable Commonwealth) go onto the
  core64 terrain as one experiment, how large is that, and what has to give? Write-up:
  [docs/terrain/core64c.md](../terrain/core64c.md).
- Method: `Fo4Land export-exterior` in 11 bands, `scripts/terrain/make_core64c.py` (select, measure, stage, check),
  `convert_batch.py --prefix fo4core --max-texture` (new: top mip levels dropped per texture kind, full and written
  size logged), `dotnet/TerrainOverlays` objects mode (new), synthetic tests `test_make_core64c`, `test_texture_cap`.
  Staged `C:\Modding\staging\terrain_core64c`. Not deployed, not run in game.
- Evidence:
  - **verified**: 706,579 FO4 references in the covered cells (701,754 placed objects + 4,825 actors / hazards /
    traps); 649,596 convert-eligible references of 11,887 models; 56,983 skipped with a reason (decals 13,118, lights
    6,275, idle markers 5,828, power lines 4,982, editor markers 13,542, actors 3,685, trigger volumes 2,414, effects
    2,087, water planes 721, ...); 11,769 models convert and 118 do not (exactly the dry run's prediction), so
    **648,358 references** are placed (1,238 more skipped as `conversion_failed`). Conversion 2,499 s, one process.
  - **verified** (directory listing): every large vanilla Starfield archive is 4,294,061,043 to 4,294,946,755 bytes,
    never 2^32 or more. **unresolved**: whether the engine reads past 4 GiB, and whether numbered per-plugin archives
    (`.* - Main[0-9]*\.ba2` in Starfield.exe) load.
  - **verified** (dry run of the converter's material logic over the FO4 texture archives' DX10 records): 2,632
    materials, 8,635 textures, 7.30 GiB at full resolution; the converted set at full resolution with meshes,
    geometries, terrain and materials is 8.47 GiB (an earlier "about 8.3 GiB" left out the terrain and materials).
    **supported** (estimate): a
    split into the 15 occupied 1.6 km regions needs 28.8 GiB (shared materials repeat) and the four central regions
    5.6 to 6.2 GiB each, so a region split does not fit 4 GiB archives either.
  - **verified**: with per-kind caps (color 1024, normal 512, rough 256, opacity 512 px; top mip levels dropped) the
    converted textures are 2.42 GiB (7.26 GiB before the caps, logged per texture); the Data tree is 3.63 GiB and
    Archive2 with the installer's arguments builds one stored archive of 3,899,305,077 bytes (51,821 entries, 0 packed).
  - **verified**: `FO4TerrainCore.esm` 46,114,630 B = core64's 4,102 records, all unchanged, + 11,699 STAT + 70 DOOR
    + 648,358 REFR in 1,708 cells (up to 6,049 per cell); BTD, mask and Mars plugin byte-identical to core64; 0 missing
    model, geometry, material or texture files.
  - **verified**: BTD minus FO4 LAND under all 648,358 origins: median 2.78 mm, p99 86.7 mm, max 3.19 m; 97.3 % within
    5 cm, 673 above 0.25 m. **supported**: the tail is steep FO4 relief (median 3.54 m per terrain quad there, 0.46 m
    overall: quarry walls, cliffs, terrain under building floors) rounded off by the 0.78 m BTD grid.
  - **verified**: plan of 3 entries (terrain probes clear of objects; the Sanctuary player house, Red Rocket shop and
    Concord museum roofs, 4.72 to 14.10 m above the terrain under the landing disc, each dropped on twice;
    informational probes, screenshot spots only with `stage --views`), every teleport at most 2 cells per axis with
    19 terrain waypoints and no runner hops (fix pass, entry below); the judged roofs equal FO4's own collision within
    0.045 mm (the museum's compound bodies through Codex's `fo4_compounds.decode_body`); 252 of 252 offline checks.
- Status: offline **verified**; everything in game **unresolved** (load and streaming of ~1,700 populated cells,
  frame time, whether objects merge with the terrain's offset everywhere, night-time screenshots).

## 2026-10-11 Claude: core64, one 64-cell Commonwealth overlay staged
- Question: does ONE large overlay (option a) load its real heights everywhere around a single arrival? exp2b (one
  29-cell overlay, stored BTD) read FO4 heights within 0.08 m and FO4 objects within 0.02 m in game; exp3 (four
  14-cell overlays) read real terrain only in the arrival tile, probes 500-700 m away in the neighbours hung at the
  drop height even after the runner's two 8 s re-reads, so separate overlays cannot be walked between.
- Method: `make_cw_overlays.py build --plan rays` (new: one overlay, `--world`, `--coc`, `--btd-copy-meshes`, ray
  entries), `dotnet/TerrainOverlays`, `make_cw_overlays.py check` (new: ray entry contract, COC marker, archive inputs,
  CNAM uniqueness), an Archive2 dry run into the scratch folder, 8 new synthetic tests (43 in test_overlay_grid).
- Evidence (**verified** offline, `C:\Modding\staging\terrain_core64`): FO4Core_Commonwealth, 64 x 64 cells = CW
  cells -32..31 (6.4 km, local frame = FO4 / 70), BTD 103,172,485 B, range -120 / 503 m (step 9.506 mm), Absolute
  (INAM 1, HNAM 0), mask ring 255 on all four edges (6400 px BC4, 20,480,128 B); FO4TerrainCore.esm 183,160 B (4,096
  cells), FO4TerrainCore_Mars.esm 6,512 B (MarsPlanetData CNAM 10 vanilla + 1 at exp2b's lat/long 0.3, -1.2, unique,
  nearest other entry 33,561 cells away). Check 208 of 208; 37 plan points decode within one step (worst 9.29 mm).
  Archive2 dry run: 3 entries, all stored (packed 0), byte-identical to the staged files, 226,825,369 B. Build 9.3 s,
  peak working set 2,049 MiB (commit 2,788 MiB); rebuild byte-identical.
- **unresolved** until the run: whether a 64-cell overlay activates and streams everywhere (6 entries, one direction
  each from the Red Rocket arrival, probes at 0 / 200 / 500 / 1000 / 2000 / 3000 m where inside, plus Sanctuary,
  Vault 111, the Sanctuary bridge and Concord).

## 2026-10-11 Claude: the whole Commonwealth at Starfield scale
- Question: can the whole Commonwealth (LAND 192 x 192 FO4 cells, 11.23 km) become native Starfield terrain with
  exact geography, as one overlay, a grid of overlays, a custom planet surface or static meshes, and what limits the
  size? Write-up: [docs/terrain/commonwealth-scale.md](../terrain/commonwealth-scale.md).
- Method: raw scans of Starfield.esm (PNDT, SFBK, SFPT, SFTR, WRLD) and the BTD header survey; INI defaults decoded
  from the setting initialisers in Starfield.exe and the CK (code that references each name string); Fallout4.esm
  placed-reference extents; fits of lat/long -> planet cell against the two measured registrations; vanilla overlay
  clusters under a true-scale model. Then `src/fo4sf/overlay_grid.py`, `scripts/terrain/make_cw_overlays.py`,
  `dotnet/TerrainOverlays`, `tests/test_overlay_grid.py` (35 after QA's review), and experiment 3 staged in
  `C:\Modding\staging\terrain_exp3`. Scratch scripts in `C:\Modding\research\terrain\scale\`.
- Evidence:
  - **verified**: overlay blocks are 3 to 14 cells (430: 207 / 121 / 77 of 3 / 4 / 5, two of 14); procedural surface
    blocks 14 (616) and 26 (217) cells; the 108 BTDs of 100 x 100 cells are editor / test worlds with the default
    -500 / 1000 range, none registered on a planet.
  - **verified** values (meaning supported): `uDefaultGameTerrainWidthInCells` 100, `uPlayableSpaceOverlayCellBuffer`
    5, `uOverlayMergeZoneSize` 1, `uBlockSize` 10, `uBlockMergeZoneSize` 2, `uPlanetBiomMapFaceDim` 256,
    `uAlignment:Overlay` 4; CK `iBlockCutRecommendedMaxDimensionExclusive` 6 (the "maximum recommended cut
    dimensions" message).
  - **verified**: PNDT `CNAM` = latitude first, then longitude, radians (Earth overlays at Kyoto, Hong Kong, Cairo, St.
    Louis, Orlando; CydoniaCity at real Cydonia). Mutagen's names are swapped.
  - **verified**: the playable Commonwealth (cells with >= 20 references) is FO4 x -34..31, y -39..31 = 39 x 42
    Starfield cells; the LAND grid is 114.
  - **unresolved**: the absolute lat/long -> planet cell rule (0 of 7 projections x 13 scales x 20 origin grids fit
    World01 (+30, -35), LC172World (-5, -23) and exp2b (-12, -27)). World01's (+30, -35) holds for the first attempt
    of all five registered runs only; the three second cocs in the same session arrived at non-whole-cell offsets
    (**unresolved**). **supported**: true planet scale locally, bounded only: Cydonia's 8 overlays fit one landing
    without overlap for scale 0.5 to about 1.1 to 1.2.
  - **verified** (raw BA2 headers): the terrain-only vanilla archives (Terrain01..04, TerrainPatch) store all 2,004 of
    their BTDs uncompressed; SFBGS00D Main stores its 108 BTDs uncompressed too, but stores all 11,974 of its entries
    that way, so it says nothing about BTDs in particular; Meshes01 is fully packed; our `--pack` archive held the BTD
    zlib-packed (27,375,606 of 27,612,888 bytes). exp2b attempt 1 (runner obs.json) read z = -116.00, the BTD
    minimum, at 14 of 14 probes, the spawn and the beyond probe outside the overlay; attempt 2 read its spawn mid-fall
    (-354.13), started every drop near -309 m, and 10 of 14 probes fell through (no evidence either way). **unresolved**: why the BTD
    read flat (packed BTDs not readable is one hypothesis; the BTD not used at all is not excluded; exp1c's flat -13.94
    is not raw 0 of its -500..1000 range). The installer stores archives uncompressed since `claude/test-queue`
    f210b91; the rerun exp2b3 is queued and gates experiment 3.
  - **verified** (runner obs.json): our persistent anchors read back their unmerged local position in 4 of 4 attempts
    (exp1d a1, a2; exp2b a1, a2); the vanilla LC172World anchor moved with its merge. So experiment 3 no longer reads
    one tile's anchor from another tile's landing (those "position" entries could not measure anything): every entry
    uses the coc'd tile's own spawn (x, y) and a z_ref probe, and three locate transects find where each tile really
    sits from the heights read (`make_cw_overlays.py analyse`; on simulated runs over the real BTDs it recovers H_ll,
    off-by-one, scale 0.5 and scale 1.2 placements uniquely).
  - **verified** offline: experiment 3 (2 x 2 tiles of 14 cells, Sanctuary / Vault 111 / Red Rocket), re-staged: 9
    entries, 115 points, 490 of 490 checks, worst point 5.167 mm (step 5.173 mm); BTDs and plugins byte-identical to
    the first staging; masks north / south symmetric (mask row order unresolved); synthetic test: four tiles side by
    side = one BTD of the region, sample for sample.
- Status: recommendation (one overlay of the playable core plus surroundings, grid of 14-cell overlays as fallback)
  is a **supported hypothesis** pending exp2b3 and exp3 in game. Why exp2b read flat, landing size, seam blending, the
  lat/long rule, large-overlay behaviour, the even-size grid origin and the mask row order are **unresolved**.

## 2026-10-11 Claude: terrain experiment 2c, the FO4 objects around Red Rocket on the native terrain
- Question: can the real FO4 exterior references (cells x -20..-15, y 16..21) be placed on the exp2b terrain so the
  runner measures object-on-terrain alignment, and what does the converted collision say they stand on?
  Write-up: [docs/terrain/experiment2c.md](../terrain/experiment2c.md).
- Method: new `dotnet/Fo4Land export-exterior` (Fo4Export's serializers compiled in unchanged), `src/fo4sf/exterior.py`
  (skip reasons, placement, surface queries), `src/fo4sf/sfbodies.py` (reads back converted collision),
  `convert_batch.py --prefix`, `dotnet/TerrainExp2` objects mode, `scripts/terrain/make_exp2c.py` (select / stage /
  check); synthetic tests `test_exterior`, `test_sfbodies`, `test_make_exp2c`, `test_batch_prefix`. Staged
  `C:\Modding\staging\terrain_exp2c`. Not deployed, not run in game.
- Evidence:
  - **verified**: export = 8,960 references + 48 actors, the same 9,008 FormIDs, cells and positions (0.004 units)
    as the raw Python reader; 496 persistent references live in the world's persistent cell.
  - **verified**: 8,069 placed (1,385 models), 939 skipped with a reason (decals, lights, power lines, markers,
    effects, triggers, actors, 15 models that do not convert, 2 water planes); trees convert (STAT + BSTriShape).
  - **verified**: converted collision read back = FO4's own (RedRExt_Workshop01: 5,898 triangles, 0 differ).
    Workshop01 has no floor; the shop floor is RedRExt_Workshop02 at origin + 0.0286 m. (Corrected in the fix pass:
    Workshop02 also holds the canopy roof; the COC marker stands 2 m above the terrain and the player falls 1.88 m onto
    the pump island, 0.117 m above the terrain.)
  - **verified**: clockwise heading (PluginSpike / routes.py): 33 references at floor height fall inside the shop
    footprint, 0 with the opposite sign.
  - **verified**: building z - BTD = -0.56 mm (FO4 LAND: 0.00 mm); BTD vs FO4 terrain under all 8,069 origins:
    median 1.43 mm, p99 56.6 mm, max 482 mm (sharp FO4 edge).
  - **verified**: raw walk: all 847 exp2b records unchanged, Mars plugin / BTD / mask byte-identical, 8,071 REFR in
    16 cells as written, 0 missing geometry / material / texture files; 109 checks PASS.
- Status: offline **verified**. Whether overlay references merge with the terrain's offset, texture archive needs,
  object bounds in exteriors and the capsule radius used for point choice are **unresolved** (in-game run pending).
- Fix pass after QA (same day): the first plan lost the runner's new `z_ref` key (its entries copied six keys by
  hand), judged points 0.10 to 0.31 m above the terrain that the 0.5 m tolerance cannot tell from terrain, and mixed
  terrain probes with object probes, while exp2b's first attempt read flat ground (-116.00, the BTD minimum, at all
  14 probes) with its anchor unmerged. Now (**verified** offline, `offline_check.json` 137 checks PASS):
  - every entry carries every key of the base entry and has its own terrain reference `zref_ground` as `z_ref`;
    four entries: terrain gate, object tops >= 1.0 m above the terrain, shop floor (informational), informational;
  - with the runner's own formula: entry 1 fails on flat ground (5.49 m), entry 2 fails without objects (15.99 m),
    entry 3 passes either way (0.142 m: informational); the integ runner plans all four tests with `z_ref`;
  - the judged tops and the floor equal FO4's own collision (source NIFs, `routes.collision_bodies`) within 0.035 mm,
    all on layer 1; the low-drop entry's teleport positions are clear with a 0.4 m x 1.8 m cylinder (walls included);
  - `exterior.place` takes the cell after the rigged-door hinge shift (door `077A83` moved from cell (-10, 10) to
    (-10, 11)); `check` tests every reference's cell against its written position;
  - re-staged on `terrain_exp2b2` (exp2b + BTD also under `meshes/terrain`); not queued until an exp2b-family run
    shows the BTD relief (**unresolved**: compressed BTD storage is the supported cause, PR #67).

## 2026-10-11 Claude: overlay record fixes
- Question: in which records do our terrain experiment plugins differ from vanilla unique overlays, and what must
  SFBK `FNAM` hold? Write-up: [docs/terrain/overlay-records.md](../terrain/overlay-records.md).
- Method: raw walks of Starfield.esm (SFBK, WRLD, LCTN, PNDT, STAT) and per-cell statistics of the raw u16 heights of
  every decodable vanilla BTD with 1..30 cells (1,711 SFBK; scratch scripts, outputs not in the repo); vanilla overlay
  masks decoded with the new BC4 decoder. Then `src/fo4sf/overlay.py`, `scripts/terrain/overlay_records.py`,
  `dotnet/TerrainExp1` overlay mode, `dotnet/TerrainExp2` params, `make_exp2.py restage`, `tests/test_overlay.py`.
  Staged `C:\Modding\staging\terrain_exp1d` and `terrain_exp2b`. Not deployed, not run in game.
- Evidence:
  - **verified**: `FNAM` = `DNAM.x * DNAM.y` u16 in all 1,730 vanilla SFBK with an FNAM. Value = raw height of each
    cell's south-west corner sample, cells from the south row: every cell exact in 1,464 of 1,711 records, 94.6 % of
    all cells; min / max / mean / median / midrange / centre / north-first order: 0 records exact. lc172world 9/9,
    akilacity 89 % of cells, NewAtlantis 91 %, lc001world 4/25.
  - **verified**: all 430 overlay WRLDs have `XLCN`; `LocTypeOverlay` on the location in 11 of the 72 registered
    ones (LC172World among them), city / settlement keywords on the rest. LC172WorldLocation: parent
    `SSol_PMars_Surface` 01B736.
  - **verified**: vanilla masks are DNAM cells x 100 px, legacy `BC4U`, one mip, in a General BA2; ours match the
    format. `INAM` 1 (Absolute) in 10 vanilla blocks, `HNAM` -239..0; 1,743 Relative.
  - **verified**: PNDT `CNAM` entry = f64 (Mutagen Longitude), f64 (Latitude), u32 WRLD; Mars 10 entries + ours.
  - **verified** (offline check, both folders PASS): FNAM 50 B / 1,682 B equal to the rule for every cell, XLCN ->
    LCTN (2CA99D, 01B736), INAM/HNAM 0/0 (exp1d) and 1/0 (exp2b), persistent XMarker anchor `01000800`
    (plan `02000800`), Mars entry, mask decodes exactly, plan points within one quantisation step.
- Status: records **verified** offline. Whether any of the four differences matters in game, the meaning of `HNAM`,
  the stale FNAM of 247 vanilla blocks, mask row order and the run-time load-order byte (02 assumed) are
  **unresolved**.

## 2026-10-11 Claude: terrain experiment 2 staged
- Question: can the real Commonwealth terrain around Red Rocket be one native Starfield BTD at absolute positions,
  ready for the unattended runner, whichever BTD lookup experiment 1 finds?
  Write-up: [docs/terrain/experiment2.md](../terrain/experiment2.md).
- Method:
  - `src/fo4sf/terrain_grid.py`: grid rule, choice of n, separable bilinear resampling with edge clamping, and
    interpolation rules for check points.
  - `scripts/terrain/make_exp2.py`: reads the FO4 cells with the PR #56 `fo4land` module, writes the BTD with
    `btd.py`, then `plan.json` and `expected.json`.
  - `dotnet/TerrainExp2`: writes the plugin from experiment 1's template.
  - Survey of the LTEX quadrant maps of the 753 top-level vanilla BTDs (scratch).
  - Staged in `C:\Modding\staging\terrain_exp2`. Not deployed.
- Evidence (**verified** offline):
  - n = 29: Starfield cells -14..14, samples -1400..1499.22 m. That covers the PR #56 patch plus 300 m.
  - FO4 cells x/y -24..25 (2,500) read, so the whole BTD holds real heights.
  - BTD 27,612,888 B. Heights -114.46..140.67 m, header -116/142, step 3.937 mm.
  - Base texture `001235C2` LDirtFootprints01: the base of 2,334,675 quadrants in vanilla BTDs, and the only texture
    of TempJemisonWorld.
  - Plugin 36,742 B, checked with a raw walk:
    - WRLD `FO4CW_Commonwealth`, overlay `BNAM` pointing to SFBK `ANAM Data\TERRAIN\FO4CW_Commonwealth.btd`
      (record path and name both match), `DNAM` 29 x 29, `ENAM` -116/142;
    - `NAM0`/`NAM9` raw -1400/1500 m (Mutagen shows metres / 4096);
    - 841 cells;
    - COC cell `FO4CW_RedRocketSpawn` (-10, 11) with a marker at (-989.03, 1147.20, 107.14).
  - 14 check points at FO4 vertices (Red Rocket, flat, slope, both seam kinds, resampled). The decoded BTD returns
    every expected height within 3.221 mm under bilinear and both triangle splits.
  - Over all 4,225 patch vertices: median error 1.58 cm, p99 13.4 cm, max 1.42 m at a 75 deg cliff.
  - Rebuilds are byte-identical.
  - SFBK `FNAM[0]` = the BTD's SW corner raw height in 3 of 3 vanilla blocks.
- Status:
  - BTD, plugin and plan are **verified** offline.
  - H (BTD z = FO4 z / 70) and the grid rule remain **supported hypotheses** until experiment 1 or 2 runs in game.
  - **Unresolved**: `FNAM[1..7]`, whether `SmallWorld` or 841 empty cells matter, FO4's triangle split, and cliff
    accuracy at a 0.78 m grid.
  - Next (plan): an exterior exporter for the Red Rocket statics. Fo4Export is interior-only.

## 2026-10-11 Claude: Starfield terrain architecture
- Question: how can native Starfield terrain carry the exact Commonwealth geography (S5 / WP-12)?
  Full write-up: [docs/terrain/architecture.md](../terrain/architecture.md).
- Method: raw record walk of both ESMs; new read-only SfInspect commands (`wrld`, `sfbk`, `planetworlds`, `wcells`,
  `form`); index-only listing of the terrain BA2s and a 44-byte header survey of all 2,112 `.btd`; BTD decoder after
  fo76utils (MIT) checked byte-for-byte on vanilla files; ref-vs-terrain fits; xEdit's Starfield definitions read for
  field names; FO4 `LAND.VHGT` decoded for all Commonwealth cells.
- Evidence: Starfield.esm has 0 `LAND` (Fallout4.esm 37,020). 430/433 WRLD point through an overlay component to an
  SFBK whose `ANAM` is `Data\TERRAIN\<EditorID>.btd`; 72 WRLD are registered by planets (`PNDT.MasterWorldspaces`,
  lat/long). BTD: 128 samples per 100 m cell, u16 heights linear in metres between a per-file min/max, LOD0-4,
  vanilla up to 100 x 100 cells. Commonwealth LAND: 192 x 192 cells, -118.86..641.03 m.
- Status: format, record chain and sizes **verified**; height scale in metres and grid alignment (BTD cell i = world
  cell i - n//2) **supported hypothesis** (pad at 111.4 m vs refs at 112-113.5 m; 130/133 NewAtlantis object cells inside
  the predicted footprint); whether a plugin worldspace with its own BTD loads, and whether it needs a planet entry,
  **unresolved** until experiment 1 (staged in `C:\Modding\staging\terrain_exp1`, not deployed). Recommendation:
  option A, a dedicated worldspace with a native BTD.

## 2026-10-11 Claude: FO4 terrain source patch
- Question: can we read absolute Fallout 4 terrain heights for a small patch, and prove them right, by reusing
  existing work before writing a LAND parser?
- Method:
  - Read fo76utils `fo4land` (MIT, commit `c52da18`) as the reference. It cannot be built here: there is no
    compiler or scons, and nothing was installed.
  - Wrote `src/fo4sf/fo4land.py`, which follows its VHGT algorithm, and `dotnet/Fo4Land`, a Mutagen-based second
    decode.
  - Extracted cells x -18..-17, y 18..19 of `Commonwealth` around the Red Rocket Truck Stop
    (REFR `000211C0`, `RedRExt_Workshop01`).
  - Details and commands: [docs/terrain/source-patch.md](../terrain/source-patch.md).
- Evidence (report.json; all **verified**):
  - Python vs Mutagen decode: max abs difference 0.0 over 4,356 vertices, and the same 1,315 refs.
  - All 1,315 temporary refs lie inside their XCLC cell (min margin 0.21 units).
  - Patch seams: max difference 0.0.
  - The Red Rocket floor z 7360 equals the terrain at its origin (residual 0). Over its footprint the max abs
    residual is 8 units.
  - 100 rocks, stumps, saplings and shrubs: z minus terrain median -7.4 units. Flipped or transposed grids give
    367-653.
  - Patch relief 1840 units, slope median 11.3 deg, max 76.5 deg.
  - Whole world: 36,864 cells. 649 of 73,344 neighbour seams (0.88%) do not match, the worst by 13,056 units in the
    far north-west (x -68..-62, y 76..77).
- Status: VHGT layout and orientation (row 0 = south, col 0 = west, height = 8 * (offset + accumulated gradient),
  origin = XCLC * 4096) are **verified** for Fallout4.esm.
  - The large maple trees sit 266 units deep. That they are planted deep on purpose is a **supported hypothesis**.
  - **Unresolved**: FO4's triangle split (bilinear vs either diagonal differs by up to 19 units at the refs),
    whether the big seams matter (are they in the playable area), and how any of this maps to Starfield terrain
    scale or format. 70 units/m is only the object scale.

## 2026-10-12 Claude: what every vanilla Starfield NPC_ carries; corrections to the raider entry (QA on PR #75)
- Question: which subrecords and header values does every vanilla NPC_ have, and which of them did the converted raider
  (FO4ActorRaider.esm, 2026-10-11) lack? Write-up: docs/actors/raider-conversion.md sections 3, 4 and 8.
- Method: `ActorRaider rawcount` and a read-only Python scan of Starfield.esm's raw NPC_ records (headers, zlib
  data, subrecords); `ActorRaider check`, which now compares each written NPC_ with the list; a scratch Mutagen
  probe for what writes EDCT.
- Evidence and status:
  - **Verified:** 16 subrecord types are in all 7,131 NPC_ (EDID in 7,130), also in all 2,821 that inherit Traits:
    EDID OBND ODTY ACBS RNAM PRPS AIDT DATA DNAM NAM5 NAM6 NAM4 MWGT EDCT STON PRON. The first raider build lacked
    PRPS, STON, EDCT and PRON (`check`: 2 problems for actor_raider1, 0 for actor_raider2).
  - **Verified:** all 7,131 NPC_ have record header form version 581; Mutagen writes 576 unless told (the first
    build); its round trip keeps 581.
  - **Verified:** templated records carry their template's values: PRPS equals the Stats template's in 2,692 of 4,046
    Stats-templated NPC_ whose template is an NPC_; STON / PRON / EDCT equal the Traits template's in 2,287 / 2,317 /
    2,274 of 2,318. EDCT equals the number of tint blocks (MNAM) in all 7,131; Mutagen writes it from a set `Tints`
    list (an empty one: EDCT 0).
  - **Verified:** STOP is in exactly the 4,310 NPC_ that do not inherit Traits (1,722 right after AIDT, 32 after RDSA)
    and in none of the 2,821 that do. Mutagen's round trip adds it to all 3 Traits-inheriting records it copied
    (LvlSpacer_Male and LvlSpacer after RDSA, LvlCitizen_NoOld after KWDA). That a STOP in a Traits-inheriting record
    is harmless is a **supported hypothesis** only.
  - **Verified:** 74 of 84 vanilla NPC_ with a WEAP directly in CNTO carry no AMMO (the companions among them), so
    "an NPC needs no ammo for its weapon" is a **supported hypothesis** (the Coachman's NpcsUseAmmo False is verified).
  - **Verified:** HEFA is in 29 NPC_, never null. A Mutagen link set to FormKey.Null is written as a null subrecord.
  - **Supported hypothesis (xEdit's Skyrim / FO4 template semantics):** the death item goes with Traits and the
    combat style with AI Data; the raider inherits both, so its own INAM is probably overridden (EncSpacerFaceM01 has
    none) and its ZNAM equals the inherited csSpacer_Assault anyway (verified).
  - **Unresolved:** whether the game needed any of these; whether `GetIsID` confirms a templated actor whose chain has
    no leveled list (N2a_base answers it first; every other N2 test waits for that).

## 2026-10-11 Claude: converting one Fallout 4 raider into a native Starfield NPC_
- Question: what does a converted FO4 actor need to run on Starfield's own actor systems, and can Mutagen write it?
  Full write-up: docs/actors/raider-conversion.md.
- Method: `dotnet/ActorRaider` (read-only on both ESMs): `export-fo4` follows the template chain of ACHR 00046458
  `DN092concordRaider01` (Concord); `sf-dump`, `sf-tplstats`, `rawcount`, and `roundtrip` (Mutagen writes 6 vanilla
  NPC_ records back; every subrecord is compared with Starfield.esm).
- Evidence and status:
  - **Verified:** the FO4 chain is LvlRaider 0002898B -> LCharRaider 00022E48 -> EncRaider01Template 0003183A at
    player level 1, with traits from LCharRaiderFaceAndGender 000FD3A3 (14 faces). Starfield's LvlSpacer 0027BB7B ->
    LCharSpacer 0027BB7D (10 tiers) + LCharSpacerFaceAndGender 0027BB7C (7 faces) has the same shape.
  - **Verified:** hostility works differently. FO4 RaiderFaction has no relation to PlayerFaction (9 relations); its
    raiders are VeryAggressive. SpacerFaction 0027BB8C is Enemy to PlayerFaction 01C21C; Spacers are Unaggressive /
    Brave and carry 6 RDSA reaction radii.
  - **Verified:** Starfield NPC_ have 15 template slots; Mutagen 0.55.0-alpha.67 names 13 of them (slots 13 and 14 are
    `TemplateActors.Unknown1/2`, flag bits unnamed). 5,445 of 7,131 NPC_ use templates (bit 13: 2,825, bit 14: 4,253).
    Slots 13 and 14 almost always share the behaviour template, never Traits alone. What they mean is **unresolved**.
  - **Verified:** Mutagen round trip. 1 of 6 records came back byte-identical. 2 differ only in FULL (localized string
    ID -> inline string). 3 gain an empty STOP (corrected 2026-10-12: 2 after RDSA, LvlCitizen_NoOld after KWDA; no
    vanilla NPC_ that inherits Traits has a STOP, see the 2026-10-12 entry), so that it is harmless is a **supported
    hypothesis**. Everything else matched, including TPTA, AIDT, RDSA and the raw subrecords.
  - **Verified:** the Coachman WEAP 0026D96B has `NpcsUseAmmo` False (that the NPC therefore needs no ammo is a
    supported hypothesis, see 2026-10-12). FO4Port.esm's highest local FormID is DE5C, so the raider's F04800 cannot
    collide.
  - **Supported hypothesis:** the plugin's console ID is 02F04800 (first plugin in Plugins.txt = slot 02, as for the
    terrain anchor 02000800).
  - ~~**Supported hypothesis:** a direct NPC_ template, with no leveled list in the chain, keeps `GetIsID` working.~~
    Corrected 2026-10-12: **unresolved**. No evidence supported it (N0_ptr_lvl tests a chain WITH a leveled list).
  - **Unresolved until N2a / N2b run:** whether Starfield spawns, animates and paths the converted record, and
    whether it engages the player.
## 2026-10-11 Claude: NPC navigation and minimal actor conversion research
- Question: will an NPC walk in a plugin worldspace with BTD terrain only; can FO4 navmesh be converted; which vanilla
  NPCs and console steps give the smallest NPC test; how does a FO4 raider map to a Starfield NPC_?
- Method: read-only scans of Starfield.esm / Fallout4.esm (GRUP walk, byte-exact `NVNM` parse), `SfInspect`
  (`navm`, `npcfind`, `npc`, `props`), strings in Starfield.exe and CreationKit.exe. Details:
  [docs/actors/npc-navigation.md](../actors/npc-navigation.md). Nothing run in game.
- Evidence: NAVM 56,576 (Starfield) / 7,893 (FO4); 424 of 433 Starfield worldspaces have NAVM, cities 820..2,708,
  landing overlays 1 each, `DefaultWorld` 0; interiors 7,959 NAVM in 475 of 11,985 cells. `NVNM` v17 vs v15: vertices
  16 B (metres) vs 12 B (units), cover 12 B vs 8 B, +4 trailing bytes; all FO4 records parse exactly, 56,570 of 56,576
  Starfield records; Mutagen's Starfield `NavmeshGeometry` schema has the same fields. Exe: runtime generator settings
  (`bDisableNavMeshRuntimeGen`, `PlanetNavMeshGen`, `bIgnoreMissingNavMeshSeed`), console `GenerateNavMesh` (`gnm`),
  `PickLastRef` (`plr`); CK: `-UpdateNavmeshGeneration` / `-FinalizeNavmeshes:<esm> (cell ids...)`. FormIDs verified:
  `LvlCitizen_NoOld` 0000CF96, `PCM_Narion_Kreet_GrazerPreyA` 001F3E88, `LvlSpacer_Male` 0010DD71, control cell
  `QASmoke` (one flat 554.7 m^2 navmesh).
- Status: Starfield `NVNM` v17 layout **verified** (56,570 records + Mutagen schema); FORMAT-GAP's "NAVM overlap 1.0"
  **verified for subrecord signatures only**, the inner layout differs. "No movement without authored NAVM in a plugin
  worldspace": **supported hypothesis**. Runtime generation for plugin worldspaces (`gnm`, seed markers): **unresolved**,
  probes N1-N3. Meaning of the vertex i32, triangle byte 20, cover and trailing fields: **unresolved**. FO4 navmesh
  conversion for Red Rocket: **supported hypothesis** (FO4 cell (-17,19) lies inside one 100 m Starfield cell).

## 2026-10-09 Claude: which FO4 collision bodies are movable?
- Question: how does an FO4 `bhkPhysicsSystem` mark a body as movable (pushable), so the converter can stop turning
  physics objects into fixed obstacles (Vault 114 door `05C7DC` is blocked by a ragdoll skeleton)?
- Method: compared `SkeletonClothed01.nif` (ragdoll) with `SubPlatformWall01.nif` (static) in the
  `hknpPhysicsSystemData` packfile, then scanned all 4,014 converted models (local script, not in the repo).
- Evidence: body cinfo +12 (u32) is a motion index: skeleton bodies 0..16 with 17 motion entries and 16 constraints
  (`hkpRagdollConstraintData`, `hkpLimitedHingeConstraintData`), layer 10; static wall `0x7FFFFFFF`, layer 1.
- Scan (motion index != 0x7FFFFFFF): 490 models / 5,340 placements with one moving body; 59 / 345 with several and no
  joints (cryo pods, roof hatches); 29 / 167 ragdolls with joints (skeletons, V111 gear-room gates, gurney).
- Status: "+12 = motion index, 0x7FFFFFFF = static": **supported hypothesis** (2 files). "Motion index means
  pushable": **refuted as stated**: placed Statics like `BldgShellWoodStairsRailing01` also have one, so it also covers
  keyframed / animated bodies. **Unresolved:** the motion entries' mass / motion type, which separates pushable
  (dynamic) from keyframed bodies.
- Follow-up (same day): system +32 holds motion *properties* (present only for dynamic bodies; values like 104.375 /
  31.57 / 0.1 / 0.05 identical in skeleton and pencil) and +48 the motion *cinfos*: u16 motion-properties id at +0,
  inverse mass f32 at +4. Skeleton: id 0, inverse mass 0.1 (10 kg); pencil: id 0, 2.0 (0.5 kg); stair railing and cryo
  pod: id 0xFFFF, inverse mass 0 (keyframed). Rule "dynamic = motion index != 0x7FFFFFFF, its cinfo id != 0xFFFF and
  inverse mass > 0": **supported hypothesis** (4 files, consistent across the scan). Rescan of 4,014 models: 373 single
  dynamic (4,642 placements: loose items), 22 multi-body without joints (156: breakable railings, gore), 29 ragdolls
  (167). Railings and cryo pods move to static, which is correct for them.

## 2026-10-09 Starfield `.af` animation header (door rigs)
- Question: what are the u16 fields at 0x28 of `open.af`?
- Method: compared four door families' `open.af` with their `characterassets\skeleton.rig` name tables
  (docs/spikes/WP-doors-research.md, "Header fields vs rig bone tables").
- Evidence: Akila 6 bones / field 6; generic 21/21; ship small 24/24; ship large 49/49.
- Status: field 2 = rig bone count: **verified** (4 of 4). Field 1 = format version: **supported hypothesis**.
  Field 3 = frame count: **supported hypothesis** (30 fps unconfirmed). Field 4: **unresolved**.

## 2026-10-09 FO4 precombine collision bodies with "shared vertex index out of range"
- Question: what primitive encoding do these `SCOL\CM*.NIF` bodies use?
- Evidence: 0 packed vertices, shared-index entries in triples (2130, start, x), primitives like (3,2,2,2);
  docs/JOURNAL.md "Precombine debris parts" and its correction.
- Status: **unresolved**. The "thin rods" reading was **refuted** (groups up to ~3 m in every axis).
