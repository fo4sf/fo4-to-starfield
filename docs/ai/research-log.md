# Research log

New findings go here (newest first). Each entry: question, method, evidence, **status**: verified /
supported hypothesis / unresolved. Older research lives in docs/JOURNAL.md and docs/spikes/; link, don't copy.

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
