# Research log

New findings go here (newest first). Each entry: question, method, evidence, **status**: verified /
supported hypothesis / unresolved. Older research lives in docs/JOURNAL.md and docs/spikes/; link, don't copy.

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
