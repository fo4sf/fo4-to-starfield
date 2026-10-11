# Research log

New findings go here (newest first). Each entry: question, method, evidence, **status**: verified /
supported hypothesis / unresolved. Older research lives in docs/JOURNAL.md and docs/spikes/; link, don't copy.

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
