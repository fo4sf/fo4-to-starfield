# Research log

New findings go here (newest first). Each entry: question, method, evidence, **status**: verified /
supported hypothesis / unresolved. Older research lives in docs/JOURNAL.md and docs/spikes/; link, don't copy.

## 2026-10-11 Claude: `XRGD` ragdoll pose decoded (bone world transforms from per-placement data)
- Question: which body each 28-byte `XRGD` entry belongs to, what its position / rotation are relative to, and the
  Euler convention (follow-up of "why the converted skeleton spawns standing", below).
- Method: all 8,919 `XRGD` subrecords of Fallout4.esm (75,292 entries; local script: linear record walk, zlib records)
  against the node trees, `hknpPhysicsSystemData` bodies and constraints of the placed models (`nif`, `hkpackfile`;
  `SkeletonClothed01.nif`, `SkeletonBareBody01.nif`, the destructible saw horses and barriers). Acceptance on the 62
  Vault 114 placements (cell `0428E4`) with ragdoll data, the floor taken from the cell's static collision
  (`routes.walkable_triangles`). Implementation: `src/fo4sf/ragdoll_pose.py` (`pose_bones`), 10 synthetic tests.
- Evidence (order): entry k belongs to physics body k (the `body` field of the `bhkNPCollisionObject` that attaches it
  to a node, i.e. the system's body-cinfo order); the clothed skeleton's 17 collision objects are bodies 0..16 in block
  order (TorsoLower, LeftUpperLeg, LeftLowerLeg, LeftFoot, RightUpperLeg, ..., LeftHand). Entry count = body count
  for 57 of the 62 placements; the other 5 carry entries for a different model (`Sawhorse01`: 6 entries, 1 body;
  `TrashCanMetal` 2/1; two `MetalBarrel01Fire*_Static` 3/1; `TrapGrenadeBouquet` 40/27): stale data, rejected.
  The first 4 bytes of an entry are uninitialised memory, not a bone id: ESM-wide the u8 is 0 in 71% of the entries
  and the 3 bytes after it are non-zero in 45%, often ASCII fragments of file paths (`617465 69616c 5c4d61 576561`
  = "ate", "ial", "\Ma", "Wea"); only 314 of 8,919 records happen to count 0..n-1.
- Evidence (frame): an entry replaces its body's node **local** transform (relative to the parent node; to the
  reference for a node under the root). For the 69 Vault 114 joints whose parent node is also a body, |entry position|
  equals the NIF bone length (relative error mean 0.36%, median 0.11%, max 3.7%: joint slack of a settled ragdoll)
  and the entry sits 0.12 units (mean; max 0.89) from the NIF local translation. 8 bodies (gear-room gate, oxygen
  tank, skeletons) with a non-trivial bind rotation kept their NIF translation to 0.01 units; 6 of them also keep the
  NIF rotation exactly (0.0001 rad), the other 2 turned in place (0.72 rad). The skeleton's constraints use the same frame: pivot A is
  the child node origin, pivot B the child's NIF local translation in the parent (c8: B (-0.100, 0.027, -0.191) m =
  LeftUpperLegBone01 (-6.99, 1.87, -13.39) units), B's axes are the child's local rotation columns (z, y, -x). Shape
  vertices are in the node frame (a leg hull spans z -0.8..30.7 along its node with the child joint at 32.9; the torso
  hull lies at z -18.9..-0.6 under the pelvis node); the body cinfo position is the node origin for torso / skull
  bodies and the hull centre for limbs, and is not needed for posing.
- Evidence (Euler): R = Rx(-x) Ry(-y) Rz(-z), the NIF's own NiMatrix3 convention. Of the 8 unmoved bodies above
  (selected by position only), 6 match their NIF rotation within 0.002 rad under this order; 4 under
  Ry(-y)Rx(-x)Rz(-z), 2 under Rz(-z)Ry(-y)Rx(-x) and Rz(-z)Rx(-x)Ry(-y), 0 under Rz(z)Ry(y)Rx(x) and Rx(x)Ry(y)Rz(z)
  (mean errors 0.11 / 0.15 / 1.46 / 1.46 / 2.15 / 2.99 rad). The 29
  posed limited hinges (knees, elbows, saw-horse legs): the hinge axis of the child frame mapped by the posed local
  rotation meets the parent's axis within 0.08 deg median (mean 0.60, max 5.8); the three alternatives 1.4-9.8 deg
  median, 13-77 max.
- Acceptance (57 posed placements, game units): the lowest posed collision point is within +/-3 of the surface under
  it for **53 of 57** (bind pose: 41), and within +/-3 of the placement's floor for 44 (median -0.01; bind 35).
  Skeletons: `05C942` (SkeletonClothed, placed z -1107.4, floor -1120) posed bones span z -1115.5..-1102.7 (spread
  12.8, pelvis->skull -12 deg), hull from 1.1 below to 21.7 above the floor, where the bind pose stands 129 tall;
  `05C94F` spread 10.9, hull -0.75..21.5; `1B4E17` -1.6..34.1; `1B4F92` rests 150 above the cave floor on the stone
  coffin beside it (clearance -0.36). The 4 of 57 off their surface are saw horses / a barrier posed partly through
  FO4 geometry (`171007`: 4.9 under the floor) or with no surface found under the lowest point.
- Side finding (REFR `DATA` rotation order): placing the cell's 164 tilted placements (|rx| or |ry| > 0.05 rad: 149
  loose items, 15 ragdolls) with each of the 12 Euler orders, Rx(-x)Ry(-y)Rz(-z) rests the most of them on their
  support (gap within +/-3: 129 of 164, median |gap| 0.56) against 100 (median 1.60) for the project's
  `routes.ref_matrix` order Rz(-z)Ry(-y)Rx(-x). **Supported hypothesis**; `routes.py` is not changed here (the route
  runs are its in-game check). Known unknown #7.
- Status: entry order = body index, entry = node local transform in the parent frame, Euler Rx(-x)Ry(-y)Rz(-z):
  **verified** offline (bind-exact entries and hinge axes on real data, floor test on 57 placements). First 4 bytes
  are garbage: **verified** (ESM-wide). Whether Starfield shows the posed skeletons lying as FO4 does: **unresolved**
  until the pose is baked into the converted mesh and body (needs the skin weights of PR #45 / #46) and seen in game.
  Both skeleton NIFs have an identity root; `pose_bones` composes a root transform like any node: **unresolved** for
  models with a non-identity root.

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
  in-game test. Open: vanilla dynamic shapes also carry `hknpShapeMassProperties`; ours don't (not needed by Havok when
  the body has a mass distribution: **unresolved** until tested).

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
