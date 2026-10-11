# Research log

New findings go here (newest first). Each entry: question, method, evidence, **status**: verified /
supported hypothesis / unresolved. Older research lives in docs/JOURNAL.md and docs/spikes/; link, don't copy.

## 2026-10-11 Claude: Starfield `.af` channel layout (known-unknown #1)
- Question: where are each bone's rotation / translation keys in a Starfield `.af`, how are they quantised, and
  are they absolute transforms or deltas from the `.rig` bind pose?
- Method: structure and field names read from CALUMI.Animation (`SFBGS_Animation.h`, `SFBGS_AnimationEntries.h`,
  `SFBGS_SkeletonRig.h`; LGPL-3.0, read only, no code copied; sf_animation_io is a Blender wrapper around its DLL
  and documents no layout). Own reader `src/fo4sf/af.py` (`parse`, `parse_rig`, `sample`, `pose_at`), 16 synthetic
  tests in `tests/test_af.py`. Checked read-only against the owner's `Starfield - Animations.ba2` with
  `scripts/af_inspect.py` (`--scan` for the whole archive, rig-folder fragments for door families).
- Evidence, whole archive (`af_inspect.py --scan`): 19,358 of 19,358 `.af` files parse to exactly their byte
  length with: 64-byte header; preamble blob of the header's size (u16 at 0x32, a multiple of 4); u32 per suffix
  block (u16 at 0x30); u8 run-length atlas (length u16 at 0x2E) alternating bones without / with a block, empty run
  first; one block per bone (6 counters, frame indices, 3-byte rotation entries, 4-byte rotation prefixes, 3-byte
  translation entries, 2-aligned 8-byte translation prefixes, 2-aligned i16 scalars, u8 priorities); then the suffix
  blocks. Version 5 and magic 0 in every file; flags 0 / 4 / 6 / 8 / 12 / 14 (bit1 u16 counters, bit2 u16 frame
  indices, bit3 scalar channel). 15,954 files carry a preamble; its inner structure fits all of them.
- Evidence, door families (`open.af` / `close.af` against `characterassets\skeleton.rig`, rig units = metres):
  Akila `ak_ext_bld_walla_doora_01` (218 B, 31 frames): only `Hinge01_Point` has keys, 16 rotation keys, identity ->
  90.0 deg about -z; `close.af` runs it back. Generic `genintrmsmwallmid_doora00a` (1140 / 952 B, 61 frames):
  `DoorPanel01_Point` 90.0 deg about -y and (-0.336, 0, -0.014) m, panels 02 / 03 180 deg about y, four latches
  +-0.097 m y. Ship `shpgenintpersmwallmid_exsm_door01` (882 / 874 B, 81 frames, rig precision 0.25 / 0.002):
  `DoorLower01` slides +0.920 m z, `Brace01` 90.0 deg, `HandleFront01` 25.0 deg, `HandleBack01` 60.0 deg, `Arm01`
  62.9 deg. Elevator `elvgen_exsm_doorinner01` (848 / 720 B, 31 frames): `InnerDoorLeft01` / `Right01` slide
  -1.000 / +1.000 m x. Also decoded: `genintrmsmwallmid_doora00b` (panels 90 deg + 0.542 m), `..._exlg_door01`
  (19 animated bones), `elvgen_exlg_doorouter01` (+-1.500 m), `genhatch_door01` (hatch 90 deg, piston -90.8 deg),
  `na_transit_car_doors01` (+2.612 m y). In all 9 families every `open.af` channel starts at identity / zero,
  every `close.af` channel ends there, and open's last key equals close's first (57 channels, 0 mismatches).
- Status:
  - Section order, atlas rule and per-bone block layout (counter order, run+1 rotation runs, run translation
    runs, dropped-component index in the top 2 bits, 2-byte alignment of 16-bit fields): **verified** (exact
    consumption of 19,358 files; no other parity or run rule consumes the Akila file).
  - Header u16 at 0x2A = the rig's *animated* bone count (rig u16 at 58; 82 of 97 for human, all bones for the
    door rigs): **verified** (7 rigs). 0x2C frame count: **verified**. 0x2E atlas length in bytes: **verified**
    (corrects the 2026-10-09 entry, where "field 4 = 2" was unresolved). Frame rate: **supported hypothesis**
    30 fps (31 / 61 / 91 / 301 frames = 1 / 2 / 3 / 10 s; not in the file). Header rotation (0x08) and
    translation (0x18), the three floats at 0x34, flag bit0: **unresolved** (not needed for doors).
  - Rotation: coarse step sqrt(1/2)/64 per 7-bit signed prefix value: **verified** (the 90.0 deg swings need
    |z| = w, i.e. exactly 64 steps = sqrt(1/2)); fine step sqrt(1/2)/16384 per i8 entry, x8 with the prefix top bit:
    **supported hypothesis** (60.0 / 25.0 deg handle swings decode clean). Dropped component = the largest one,
    index order x y z w: **verified** (180 deg about y drops y, small swings drop w).
  - Translation: coarse step = the rig header float at 48 (0.03125, or 0.25 for ship rigs): **verified** (the
    elevator panels slide exactly their 1.000 / 1.500 m bind offsets); fine step = the rig float at 52 (always
    1/125 of the coarse step): **supported hypothesis** (0.088 / 0.606 / 0.097 decode clean).
  - Channel values are deltas from the bind pose, not absolute local transforms: **verified** (37 of the 57 door
    channels sit on bones whose bind pose is not identity / zero, yet all start at identity / zero). How the delta
    composes with a non-identity bind: **supported hypothesis** parent frame, translation = bind + delta,
    rotation = delta * bind (the generic door's mirrored latches, bind-twisted 180 deg, carry opposite-sign
    deltas and retract symmetrically only in the parent frame; the ship door's `Arm01`, bind 105.5 deg about an
    oblique axis, swings about the root y axis every other hinge of that door uses). Moot for the door hinge /
    panel bones, whose bind rotation is identity. Not verified in game.
  - Preamble inner structure (u32 count; entries u16 n, 2n + frame_count f32, n i16, n i8, padded to 4):
    **supported hypothesis** (fits all 15,954 files); its meaning: **unresolved**. Suffix u32 ids (same values for
    the same prop across files, e.g. 0xFFF1BB1A first in every slate animation) and suffix blocks: **unresolved**.
    Scalar / priority channels: **unresolved**. Interpolation between sparse keys: **unresolved** (reader: linear).
- `.rig` (7 vanilla rigs: 3 doors, human, terrormorph, turret, bipedA): 80-byte header (u32 version 5, file size,
  header size, 0, bone-map offset = 80 + 96 * bones, 0; 3 u64; f32 coarse / fine step; u16 bones; u16 animated),
  96-byte bone records (local and global rotation wxyz, position, u32 type, u64 absolute name offset, i32 parent),
  bone map of 157 u16 (all 0xFFFF in the door rigs, 94 mapped in human), then the names: **verified** for these
  fields; the remaining 36 bytes per bone and the bone map's meaning: **unresolved**.
- Next: pick sliding templates for the vault / elevator doors from the decoded motions (elevator panels +-1.0 /
  1.5 m sideways, ship small door lower panel +0.92 m up, generic panels), then confirm one decoded pose against
  an in-game panel position (that also settles the composition order and the frame rate).

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
