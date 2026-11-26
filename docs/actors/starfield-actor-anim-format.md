# Starfield actor rigs and clips: measured conventions

Date: 2026-11-23. Module: `src/fo4sf/actor_anim.py`; tests: `tests/test_actor_anim.py`.

What this covers: the `skeleton.rig` and `.af` / `.afx` files an actor's race points at (RACE NAM5 = rig, DNAM = clip
folder). Everything below was measured offline by reading vanilla files through the external CALUMI library
(`CALUMI.Animation.dll`, SHA-256 8C138844...4BF4D89, kept outside the repository) and by reading raw bytes. Nothing here
was run in the game.

Sources measured:
- Garden Mini Bot (MiniBotARace 00227705): `meshes/actors/minibota/characterassets/skeleton.rig` (12 bones) and all 55
  clips with their `.afx` under `meshes/actors/minibota/animations/` in `Starfield - Animations.ba2`.
- All 390 `.rig` files in that archive (precision, bone order).
- All 19,358 `.af` headers in that archive; a random 1,500 of the clips that sit below their own actor's
  `characterassets/skeleton.rig` for the root-motion check (1,112 of them were full clips that CALUMI reads).

Measurement scripts and their outputs (not in Git): `D:\FO4SF-Owner-Tests\robot-anim\B\` (`roundtrip\roundtrip_report.json`,
`rig_survey.json`, `af_header_survey.json`, `quant\quant.json`).

## Conventions

| Item | Measured | Evidence |
|---|---|---|
| Units | metres | COM bind z 0.5057 above Root; walkforward Root travel 1.09 per cycle; mesh NIF `C_Arm1` translation equals the rig's (0, 0.145, -0.143) |
| Axes | right-handed, Z up, +Y forward, +X right | walkforward / walkbackward Root +Y / -Y; walkright +X; turninplace_left90 header rotation +90 deg about +Z (a left turn) |
| Rotation | quaternions (no Euler order); API order x, y, z, w; files store w first (rig record, .af header) | rig bytes of `C_Arm1` begin 0.0531 (= w); header of turninplace_left90 = (0.7071, 0, 0, 0.7071) as w, x, y, z |
| Rig bind | parent-local translation + rotation, scale 1 | `C_Arm1` / `C_Arm2` quaternions equal the mesh NIF nodes' local rotations (sign aside) |
| Bone order | one root at index 0, every parent before its child (not depth-first: `C_RightSideRef`, child of COM, is index 8) | 390 of 390 vanilla rigs |
| Clip values | offsets from the bind in the bone's own rest frame, not local and not model space | every vanilla track of a bone with a rotated bind starts at identity (`C_Arm2`, bind 172 deg, lookdirections.af); COM keys z -0.00075 against a bind of 0.5057 |
| Tracks | only bones that move; a constant offset is one key at frame 0; blocks in rig-index order; no scale tracks | 55 Mini Bot clips (Root 40, COM 47, C_Chassis 40, C_Base 8, C_Axle 2, C_Hatch 1, C_Arm2 1 clips) |
| Frame rate | 30 fps assumed: no fps field exists | walkforward: 31 frames, SyncLeftFoot 15, SyncRightFoot 30, 1.09 m per cycle (1.09 m/s at 30 fps; run 5.2, jog 3.3) |
| Frame count | header u16 at 0x2c; CALUMI writes last key + 1 | idle.af: 41 frames and no block at all; CALUMI reads it as 1 frame |
| Root motion | the Root bone's own track (Root bind = identity) AND a header copy of the Root offset at the last frame: w, x, y, z f32 at 0x08, x, y, z f32 at 0x18 | 1,111 of 1,112 sampled vanilla full clips match within 2 mm / 2.5e-4 rad; the miss is a ship clip (31.5 m, ship precision 2 mm) |
| COM | carries the body's bob / tilt as offsets; bind 0.5057 m above Root | walkforward: one constant key, -4 deg about X and (0, 0.028, -0.00075) |
| Bone map | SFBGSRigPackage keys: Root 0, COM 9, DirectAt 137 | read through `SFBGSRigPackage_GetBoneKeyC`; the rig file has a 256-entry u16 table key -> bone index |
| Precision | rig-wide presets only: default (0.00025 / 0.03125) 305 rigs, ship (0.002 / 0.25) 83, first_person (6.25e-5 / 0.0078125) 2; Mini Bot: default | all 390 rigs |

`.af` header (offsets in bytes, all little-endian): 0x00 two u32 = 0 (19,309 of 19,358); 0x08 root rotation (w, x, y, z);
0x18 root translation; 0x24 u32 (0 in 17,203); 0x28 u16 = 5 (version); 0x2a u16 bone count; 0x2c u16 frame count;
0x2e u16 layout kind: 2 (full clip) in 14,487 files, 4..16 in the rest (`lookdirections.af` is kind 4, bone count 8, followed by
what looks like a table 1, 2, 3 ... 15; not decoded). CALUMI writes kind 2 only. The two floats at 0x38 / 0x3c are -0.0 or 0 in most files (CALUMI: -0.0 and
0); their meaning is unknown.

`.afx` (XML, Mini Bot): `<root><is_state/><tag/><filename/>[<events><event><frame/><name/><payload/></event>...</events>]
[<audios><audio><frame/><foley/></audio>...</audios>]</root>`. 24 of 55 clips have `is_state` 1 (loops and one-shots that
are graph states: Idle, WalkForward, the deaths), 31 have 0 (starts / stops, turns, staggers, getups, attacks). Events seen:
SyncLeftFoot 18, PathingBegin / PathingEnd 12, SyncRightFoot 9, AddRagdollToWorld 7, RemoveCharacterControllerFromWorld 7,
SetOrientEnd 7, GetUpEnd 4, WeaponFire, PreHitFrame, WeaponSwing, HitFrame, SetOrientBegin, SetPosBegin, SetPosEnd. The tag
is what the graph asks for and need not match the file: knockdown_backward and knockdown_forward both carry tag `Knockdown`;
relaxed_idle_flavor01 carries `Idle_Flavor01`. Archive names are lower case; `<filename>` is CamelCase.

## The writer and how it composes

`actor_anim.build_blocks(bones, poses, n, keys_are='local')` turns per-frame parent-local poses (what a FO4 `.hkx` decodes
to) into offsets: `q_o = q_b^-1 q`, `t_o = q_b^-1 (t - t_b)`; the inverse is `offset_to_local`: `q = q_b q_o`,
`t = t_b + q_b t_o`. This is the composition the CALUMI Blender add-on uses (`API/Animation.py` exports `convert_space(POSE
-> LOCAL)`, Blender's rest-relative basis; `API/RigUtils.py` builds the rest pose as `parent @ T(t) R(q)`). For a bone whose
bind rotation is the identity the order cannot matter. For a rotated bind it is the add-on's rule and **not verified in the
game** (no vanilla Mini Bot clip moves a rotated-bind bone in a way that tells the two orders apart).

## Round trip (vanilla Mini Bot, `D:\FO4SF-Owner-Tests\robot-anim\B\roundtrip\roundtrip_report.json`)

- Rig: read, written with `Calumi.write_rig`, read again: 12 bones, translation and rotation difference 0.0, bone-map keys
  and mirror indices equal, precision default kept. The file is 1,639 bytes like vanilla but 164 bytes differ: three
  8-byte values at 0x18 (pointer-like in vanilla, 0 from CALUMI), a CALUMI signature in padding at 0x42, per bone a u32
  index (vanilla 0..11, CALUMI -1), a u32 (vanilla 5/4/3/2, CALUMI 0) and an f32 (vanilla 1.0, 2.0 for C_Arm1, 5.0 C_Arm2 and
  C_Hatch, 10.0 C_Arm3; CALUMI 0), and last-bit noise in two quaternions. The meaning of those per-bone fields is unknown.
- Clips, key-exact (the 55 vanilla clips' own keys written back): largest difference 1.5e-8 m and 3.0e-8 rad over every
  bone and frame; key frames identical; frame counts kept in all 55 (with the hold-key rule below); header root motion
  within 2.5e-4 m / 1.2e-4 rad of vanilla (vanilla stores the unquantised value, ours the quantised key). Bar 1e-4: met.
- Clips, dense (every frame resampled through local poses and written as one key per frame): largest difference
  1.67e-4 m and 1.07e-4 rad. These are values off the quantisation grid; the difference is the format's quantisation,
  not the conversion (the conversion alone is exact to 1e-12 in the unit tests).
- Byte layout of the clip bodies differs from vanilla (Bethesda's encoder packs differently) although the decoded keys
  agree; idle.af gains a Root block (see below), lookdirections.af is rewritten as a kind-2 clip.

## Quantisation (synthetic keys, `quant\quant.json`)

- Translation: largest error about 2/3 of the rig's high-precision step whatever the range: default 1.67e-4 m,
  first_person 4.2e-5 m, ship 1.33e-3 m. Only first_person meets 1e-4 for arbitrary data; vanilla actors use default.
- Rotation: typically 8e-5 to 1.4e-4 rad, independent of the rig precision; it grows near 180-degree offsets (w near 0) to
  4e-3 rad (0.23 deg), consistent with w rebuilt from x, y, z.
- `SFBGSRigPackage_SetPrecisionToCustomC` exists, but no vanilla rig uses a custom precision, so the module offers only the
  three presets.

## Known limits

- The composition order for bones with a rotated bind, the 30 fps rate and the engine's interpolation between keys are
  not proven (offline evidence only).
- CALUMI derives the frame count from the last key. `write_clip` adds a hold key at frame n-1 to the first block that ends
  earlier, and a clip with no block gets an identity Root rotation at frames 0 and n-1 (vanilla idle.af has no block).
- CALUMI leaves the header's root motion at identity / zero; `write_clip` patches it (`patch_root_motion`) from the
  unquantised input. A file of another layout kind is refused.
- Only full clips (kind 2) are written; additive / partial layouts (kinds 4..16, a quarter of vanilla) are not.
- Rig per-bone fields CALUMI does not write (see the round trip) keep CALUMI's values; their effect on an actor is unknown.

## Agreement with the sf_animation_io documentation (D:\Modding\research\sf_animation_io\docs)

- `docs_rig.md`: "Index ... should start from 0 (root bone should be zero) and increment" agrees (390 of 390 rigs).
  "Precision: a value found to differ on various rigs" agrees: three presets, default / ship / first_person.
  "Twist bones cannot be animated": the Mini Bot has none; not tested.
- `old_docs.md` (static rigs): "the NiNode should have the position data offset from its parent, just as the transform of
  its corresponding bone in the rig" agrees with the Mini Bot mesh NIF (C_Arm1 / C_Arm2 local transforms equal the rig's).
- The docs say nothing about clip values being offsets from the bind, root motion, the header copy of it, frame count,
  fps or quantisation; those are this measurement's. The add-on's code (not its docs) agrees on offsets from the bind.
