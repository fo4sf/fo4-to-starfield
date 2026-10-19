# Physics and collision (FO4 CE1 vs Starfield CE2)

Part of the engine-mechanics reference ([index](README.md)). Author: Claude-cloud, 2026-10-19. Labels: verified /
supported hypothesis / unresolved.

This is a mechanism summary. The project's verified physics work lives in
[S6-collision.md](../../spikes/S6-collision.md) (Starfield's NIF collision layout, box blobs),
docs/JOURNAL.md 2026-10-08 (FO4 collision transplanted, verified in game on the Prydwen stairs) and 2026-10-10
(movable items, verified in game), docs/ai/research-log.md ("how Starfield makes a body movable", FO4 motion data),
[FORMAT-GAP.md](../../FORMAT-GAP.md), and the scale plan
[../next-phase/physics-conversion.md](../next-phase/physics-conversion.md). Record layouts are **verified with xEdit**
(`wbDefinitionsFO4.pas`, `wbDefinitionsSF1.pas`, dev-4.1.6) unless marked otherwise.

## In short
- **Both games use Havok's hknp ("new physics") family**, but FO4 stores it as a Havok 2014.1.0-r1 *packfile* and
  Starfield as a *tagfile* (`TAG0` / `SDKV` / `TYPE` sections) with its own type table (**verified**, FORMAT-GAP.md and
  the project's `hkpackfile.py` / `hktagfile.py`). The compressed-mesh tree layout is the same in both, so FO4's
  authored collision can be transplanted. Verdict: **translate** (done for static, keyframed and single dynamic bodies).
- **Collision layers are records (COLL) with the same indices** in both games except 37 and 43 (**verified**,
  `meshcollision.py`). Verdict: **data copy** with two refusals.
- **Constraints are not converted yet** (ragdoll and hinge joints): skeletons and breakables become one rigid body.
  Verdict: **rebuild** after one vanilla Starfield constraint blob is decoded.
- **Destruction, impacts and material types keep their record model** (DEST, IPCT, IPDS, MATT), with Wwise sounds and
  projected decals in Starfield. Verdict: **translate**.
- No SFSE need found. Actor ragdolls follow the actor's skeleton, so FO4 creatures wait for the animation lane.

## How Fallout 4 does it

### In the NIF (verified, project code and journal)
- A node's `bhkNPCollisionObject` (target node, flags u16, data, body index) points at a `bhkPhysicsSystem` whose
  payload is a Havok 2014.1.0-r1 packfile holding `hknpPhysicsSystemData`: body cinfos, motion cinfos, motion
  properties, shapes, constraints. Several collision objects can share one system; each owns the body its index names
  (journal 2026-10-08, Prydwen stairs).
- Shapes seen: `hknpCompressedMeshShape`, convex polytopes, boxes, capsules (as hulls), spheres,
  `hknpDynamicCompoundShape` (journal 2026-10-08; `fo4collision.py`, `fo4_compounds.py`).
- Body cinfo +12 is a motion index (0x7FFFFFFF = static); dynamic bodies have a motion cinfo with a motion-properties
  id and inverse mass (skeleton body 10 kg, pencil 0.5 kg); keyframed bodies have id 0xFFFF and inverse mass 0
  (**supported hypothesis**, 2-4 files read: research-log 2026-10-1x "how an FO4 bhkPhysicsSystem marks a body as
  movable").
- Joints: ragdoll props carry `hkpRagdollConstraintData` and `hkpLimitedHingeConstraintData` (skeleton: 17 bodies, 16
  constraints, layer 10; **verified** on one file). Scan of 4,014 models: 490 with one moving body, 59 with several and
  no joints, 29 ragdolls with joints (research-log).
- Animated doors and platforms: keyframed bodies moved by the NIF's controller sequences.

### Records
| Record | Key fields (verified, xEdit) | Count (fo4_esm.json) |
|---|---|---:|
| COLL collision layer | `BNAM` index, `GNAM` flags (Trigger Volume, Sensor, Navmesh Obstacle), `MNAM` name, `CNAM` collides-with list, `INTV` interactables count, `DESC`, `FNAM` debug colour | 57 |
| MATT material type | `PNAM` parent, `MNAM` name, `BNAM` buoyancy, `FNAM` flags (Stair Material, Arrows Stick, Can Tunnel), `HNAM` impact data set, `ANAM` breakable FX | 147 |
| IPCT impact | model; `DATA` duration, orientation, angle threshold, placement radius, sound level, No Decal Data flag, result (Default / Destroy / Bounce / Impale / Stick); `DODT` decal data; `DNAM` / `ENAM` **texture sets** for the decal; `SNAM` / `NAM1` sounds (SNDR); `NAM3` footstep explosion; `NAM2` hazard | 619 |
| IPDS impact data set | list of (MATT, IPCT) pairs | 293 |
| MSTT movable static | model, DEST, keywords, `DATA` On Local Map, `SNAM` looping sound | 961 |
| DEST (subrecord block on many bases) | `DEST` health, stage count, flags (VATS Targetable, Large Actor Destroys); `DAMC` resistances; per stage `DSTD` (health %, model damage stage, flags Cap Damage / Disable / Destroy / Ignore External Dmg / **Becomes Dynamic**, self damage, explosion, debris + count), `DSTA` **sequence name**, `DMDL` replacement model | n/a |
| REFR | `XTRI` collision layer override, `XPRM` primitive (trigger box / sphere / plane / line / ellipsoid), `XRGD` ragdoll pose (Common def; decoded by the project, 28 bytes per body) | |

Also physics-related: EXPL 238, PROJ 139, DEBR 5, HAZD 59, BPTD 40 (body parts; see
[health-damage-effects.md](health-damage-effects.md)). Actor ragdolls use the race skeleton's physics
(**supported hypothesis**; not read by the project).

## How Starfield does it

### In the NIF (verified, S6-collision.md and research-log)
- Root `NiNode` -> `bhkNPCollisionObject` (14 bytes: target 0, flags 0x0080, data, body id 0) -> `bhkPhysicsSystem`
  = u32 size + tagfile. `BSXFlags` 2 when collision exists, 0x42 on movable items (145 of 150 MiscItem NIFs).
- Shapes in 2,500 vanilla setdressing NIFs: 596 single `hknpConvexShape`, 411 `hknpCompressedMeshShape`, 232
  `hknpBoxShape`, 183 convex + compound. Every vanilla mesh shape has a SIMD tree (journal 2026-10-08).
- Body cinfo: `motionType` static 0 / keyframed 1 / dynamic 2; flags 0 / 0x4 / 0x8a; `collisionFilterInfo` = layer
  (1 STATIC, 2 ANIMSTATIC, 4 CLUTTER, 26 ...); dynamic bodies add `mass`, a motion-properties entry and
  `hknpRefMassDistribution` (inertia = grown box x 1.5, 30 of 30). Movable compounds: 273 vanilla, one
  `hknpCompoundShape` body each.
- Multi-panel vanilla doors use **one** physics system with one keyframed body per panel (sliding-doors.md).
- Havok SDK version: the project calls it Havok 2019 (journal 2026-10-08; **supported hypothesis**, the `SDKV` string
  is readable with `hktagfile.py`).

### Records (verified, xEdit; counts sf_esm.json)
| Record | Same | Changed / new | Count |
|---|---|---|---:|
| COLL | BNAM index, GNAM flags, MNAM name, CNAM collides-with, FNAM colour | adds VMAD, components, `NLDT`; no DESC, no INTV | 62 |
| MATT | parent, name, buoyancy, HNAM, ANAM | flag **Is Slippery**; `FLLD` | 249 |
| IPCT | DATA struct identical | decals are **PDCL projected decals** (`GNAM`, scatter `HNAM`) instead of TXST; Wwise sounds `IDSH` / `IDP1` / `IDP3`; `INAM` decal lifetime | 1,088 |
| IPDS | (MATT, IPCT) pairs | `ENAM` **parent impact data set** (inheritance) | 274 |
| MSTT | model, DEST, keywords | `DATA` mass override flags (Use Mass Override, Scale; default 4), `MSMO` mass override value, Wwise looping sound | 1,771 |
| DEST | health, stages, DSTD fields, Becomes Dynamic | header flag Resist All Except; `DAMC` gains a curve table; `DSDL` secondary damage list; stage flags Object Cleared, Fallback Spawn At Bounds Center; replacement model delay; `DSTA` is an **anim event**, not a NIF sequence | n/a |
| REFR | `XPRM` (adds Cylinder), `XRGD` | collision override is `XCOL` (layer + MATT) instead of `XTRI` | |

## Mapping for the port

| FO4 piece | Starfield counterpart | Verdict | Notes |
|---|---|---|---|
| Compressed mesh, convex, box, sphere, compound shapes | same hknp shapes in a tagfile | translate | done (`meshcollision.py`, `sfbodies.py`); 3,006 of 3,490 models native at last count |
| Static / keyframed body | motionType 0 / 1 | translate | keyframed needed for door leaves (WP-doors-research attempt 3) |
| Single dynamic body | dynamic body on MoveableStatic, BSXFlags 0x42 | translate | done; FO4 mass kept (`--mass-scale`) |
| Multi-body system, ragdoll props | joints | rebuild | today merged into one rigid body ("phase A") |
| Constraints (ragdoll, limited hinge) | hknp constraints (**supported hypothesis**) | rebuild | needs one decoded vanilla blob |
| COLL layers | COLL | data copy | 37 L_DOORDETECTION and 43 L_CUSTOMPICK1 refused; layer 55 handled specially |
| REFR XTRI | REFR XCOL | translate | |
| MATT | MATT | translate | map by name; Starfield adds Is Slippery |
| IPCT decal TXST | PDCL | rebuild | new PDCL per FO4 decal texture set; see materials file |
| IPCT / MSTT / DEST sounds | Wwise refs | translate | audio lane |
| DEST stages | DEST stages | translate | `DSTA` sequence name must become a graph event; damaged models are NIFs to convert |
| XRGD placement pose | XRGD or baked pose | translate | 147 articulated refs baked per pose; 214 single bodies open |
| Actor ragdoll (FO4 races) | Starfield race skeleton | rebuild | follows the animation lane |
| Triggers (XPRM + Trigger Volume layer) | same | data copy | |

## What must be rebuilt, and what needs SFSE or the Creation Kit
- Rebuild: constraints (props, hanging objects, ragdolls), breakage (DEST damaged models and events), FO4-creature
  ragdolls, per-class mass feel.
- SFSE: none known. CK2: not needed; Havok authoring tools for Starfield cover cloth only (physics-conversion note).

## Port status and links
- **In game (verified):** box collision on a converted chair (S6, 2026-10-07); FO4's own collision on the Prydwen
  stairs and Hotel Rexford doorway (journal 2026-10-08); keyframed door leaves swing and block (2026-10-08); a pushed tin
  can and a rigid skeleton moved (journal 2026-10-10, Vault 114). Moving items PASS by hand on 2026-10-17
  (physics-conversion note).
- **Offline only:** compound, capsule and sphere conversion; dynamic compounds; placement poses from XRGD.
- **Not done:** constraints, destructibles, activator and trap physics, actor ragdolls, weapon and projectile physics.
- Plan: [../next-phase/physics-conversion.md](../next-phase/physics-conversion.md). Related:
  [doors-activators-furniture.md](doors-activators-furniture.md) (door bodies, triggers),
  [health-damage-effects.md](health-damage-effects.md) (BPTD, damage), [materials-textures-lighting.md](materials-textures-lighting.md)
  (decals).

## Open questions and cheap checks
- Read the `SDKV` string of one vanilla Starfield `bhkPhysicsSystem` with `hktagfile.py` (settles the Havok version).
- Dump one vanilla Starfield NIF with a joint (hanging sign or corpse) and list its constraint types.
- Compare FO4 and Starfield COLL records by index and name (xEdit or a raw walk) to recheck the 37 / 43 rule.
- Count FO4 bases with DEST and how many stages swap models (Fo4Export or xEdit filter).
- Does Starfield's MSTT mass override apply to converted dynamic bodies (one test item with `MSMO` set)?

## Sources
- xEdit dev-4.1.6: `wbDefinitionsFO4.pas` DEST 4275, MSTT 7067, MATT 7958, IPCT 7978, IPDS 8014, COLL 9547, REFR
  XPRM 11457, XTRI 11633; `wbDefinitionsSF1.pas` DEST 3829, REFR XCOL 8823, COLL 10953, IPCT 13147, IPDS 13186, MATT
  14291, MSTT 14652; `wbDefinitionsCommon.pas` XRGD 9411.
- Repo: docs/spikes/S6-collision.md, docs/FORMAT-GAP.md, docs/JOURNAL.md (2026-10-07, 10-08, 10-10), docs/ai/research-log.md
  (2026-10-10 movable bodies, FO4 motion index), src/fo4sf/hkpackfile.py, hktagfile.py, meshcollision.py (layer map),
  sfcollision.py, sfbodies.py, convert_static.py; docs/measurements/fo4_esm.json, sf_esm.json.
- Plan: [../next-phase/physics-conversion.md](../next-phase/physics-conversion.md).
