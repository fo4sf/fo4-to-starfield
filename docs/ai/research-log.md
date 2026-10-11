# Research log

New findings go here (newest first). Each entry: question, method, evidence, **status**: verified /
supported hypothesis / unresolved. Older research lives in docs/JOURNAL.md and docs/spikes/; link, don't copy.

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
