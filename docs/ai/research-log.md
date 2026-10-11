# Research log

New findings go here (newest first). Each entry: question, method, evidence, **status**: verified /
supported hypothesis / unresolved. Older research lives in docs/JOURNAL.md and docs/spikes/; link, don't copy.

## 2026-10-11 Claude: FO4 precombine hull primitives (known-unknown #2)
- Question: what primitive encoding do the 38 `SCOL\CM*.NIF` bodies use that failed with "shared vertex index 2130
  out of range" (36 models on guessed boxes, 2 with a skipped part; entry 2026-10-09 below)?
- Method: dumped the raw `hknpCompressedMeshShapeData` of all 38 models from `Fallout4 - Meshes.ba2` (scratch scripts,
  not in the repo), compared with 6 ordinary FO4 models and 4 clean precombines, and checked every reading against the
  whole shared-vertex array and the render mesh bounds. Web search found no public Havok source or document naming the
  structure (GitHub code search needs a login), so there is no reference decoder to compare with.
- Evidence:
  - The failing primitives are `(a, b, b, b)`. `a - numPackedVertices` is a slot in the section's `sharedVerticesIndex`
    range holding a 3 x u16 record `(w0, first, w2)`; records sit in triples (`CM00163A1B`: 34 such primitives,
    `a` = 0, 3, ..., 99, 102 shared indices, 0 packed vertices).
  - `w0` low byte = 0x52 in 286 of 286 records. Count rule `V = (w0 >> 9) + ((w0 >> 8) & 1)`: the ranges
    `sharedVertices[first : first + V]` plus the shared vertices referenced by triangles tile the shared array exactly in
    all 38 models (0 unreferenced, 0 in two hulls, 0 shared between a hull and a triangle); every range has V distinct
    points. The high byte is 2V for 278 records and 2V - 1 for 8 (V = 36 x5, 44, 47 x2): why bit 8 carries the odd unit is
    **unresolved**; the sum is what tiles. `V + faces` was tested and refuted (124 mismatches).
  - Sizes: V = 4 for 250 of 286 (planks and rods 1.3 to 1.9 m long, 5 mm to 35 cm thick: the "thin rods"), V = 5 to 53
    for the rest (hulls up to 4.3 m: the ~3 m groups of the 2026-10-09 correction). So the earlier "4 shared vertices per
    primitive" reading is **refuted**: the count is per record. 281 of 286 hulls lie inside the render mesh bounds
    (+5 cm) once the collision node transform is applied; the 5 outside are two 6.5 x 3.7 x 3.5 m four-point wedges in
    `CM00075A6C` / `CM000D456C` reaching 0.5 m past the render mesh in y and three 1 m rods in `CM000ABFFB` reaching 9 cm
    below it. 2 records (`CM000C5371` / `CM000C5373` prim 3) have 2 points: a 0.55 m segment, no volume.
  - Section flags: all 38 hull-carrying sections have flags 1; the 10 plain sections of the same files and 6 sections of
    ordinary models have flags 0. Vanilla Starfield sections (`ak_int_wallmid03`, `test_fbx_collision_same_node01`) have
    flags 0.
  - `b` < section node count in 286 of 286; in 44 primitives of 4 models the section tree node `b` is a leaf whose data
    byte is 2 x primitive index (the primitive's shape key), so `b` is the primitive's leaf node. Hull sections have
    2N - 1 nodes for N primitives. A hull counts one shape key (`CM0014060B`: numPrimitiveKeys 66 = 32 quads x 2 + 2
    hulls), consistent with maxKeyValue.
  - `w2` reads as a half float in 0.81..1.33 (34 distinct values, identical for hulls of one source: 1.0352 for all 7
    hulls of `CM001D4F96` / `98`). Not the convex radius (a 2-point hull would be a 1 m capsule). **Unresolved**;
    hypothesis: the source reference's scale (needs the cell's XCRI members' XSCL, not read by the pipeline).
- Status: "section flags bit 0 + `(a, b, b, b)` = convex hull of `sharedVertices[first : first + V]`, V from `w0`":
  **supported hypothesis** (38 models, 286 hulls, exact tiling, bounds, key count), not **verified** against a reference
  decoder. Bit 8 of `w0` and `w2`: **unresolved**. How FO4 uses `w2` at runtime is unknown; the converter ignores it.
- Result (branch `claude/precombine-primitives`): `fo4collision` decodes hull primitives (`compressed_mesh_hulls`,
  `hull_surface`; `_compressed_mesh` returns their closed surfaces for route planning), `meshcollision.convert_bodies`
  emits one Starfield convex body per hull (rebuilt closed hull, radius 0, FO4 layer kept, part transform baked in) and
  neutralises the hull primitives in the copied mesh arrays (degenerate point, record word 0 -> a valid vertex, section
  flags 0). Sections without the flag keep the old explicit fallback. Side check on the 38 models with the real template:
  all 38 convert natively, 284 hull bodies + 21 mesh bodies, 0 skipped parts (was 36 guessed + 2 partial). Unverified in
  game.

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
