# Animations (FO4 CE1 vs Starfield CE2)

Part of the engine-mechanics reference ([index](README.md)). Author: Claude-cloud, 2026-10-19. Labels: verified /
supported hypothesis / unresolved.

Plan-level research, first proofs and the clip pipeline are in
[../next-phase/animations-ui-and-start.md](../next-phase/animations-ui-and-start.md) section 2. This file adds the
mechanism detail (records, file types, how an actor picks a clip) and does not repeat that plan.

## In short
- **FO4** runs Havok Behavior: `.hkx` behavior graphs, skeletons and clips (Havok 2014 packfiles), selected through
  RACE behavior graphs, keyword-driven Subgraph Data, IDLE records and anim events. Face animation comes from lip data
  inside each `.fuz`.
- **Starfield** has no `.hkx` at all. It uses Bethesda's own files: `.af` clips, `.afx` event XML, `.rig` skeletons,
  `.agx` graphs and `.xtbl` lookup tables, with FaceFX `.ffxanim` for faces (all **verified** by archive counts).
- The **record side is close**: IDLE, IDLM, AACT, ANIO, FURN and RACE Subgraph Data exist in both, with the same core
  subrecords (DNAM graph, ENAM event, ANAM parent/previous, GNAM file; SAKD/SGNM/SAPT/STKD/SRAF). Verdict: **translate**.
- The **asset side is a rebuild**: every FO4 clip must be decoded, retargeted 129 to 97 bones and written as `.af`.
  FO4 behavior graphs do not convert; actors use Starfield's `.agx` graphs (settled: Starfield animations first).
- New graphs or new events may need **CK2 or SFSE**; replacing clips at existing paths is proven by players.

## How Fallout 4 does it

### Files (verified: docs/measurements/fo4_ba2.json)
| Item | Evidence |
|---|---|
| `Fallout4 - Animations.ba2`: 15,320 `.hkx` + 14,396 `.txt`; DLCRobot adds 421 `.hkx`; total 15,741 `.hkx` | fo4_ba2.json |
| Behavior graphs live under `Meshes\Actors\Character\Behaviors\`, e.g. `SyncedAnimBehavior.hkx`, `SingleAnimFurniture.hkx`, `LeftArmInjuredWeaponWrappingBehavior.hkx` | fo4_ba2.json extension_samples |
| Per-race text tables under `CharacterAssets\` (bone scales, facial bone regions), e.g. `HumanRaceFacialBoneRegionsMale.txt` | fo4_ba2.json |
| Packfile layout `hk_2014.1.0-r1`, file version 11, 8-byte pointers, sections `__classnames__` / `__types__` / `__data__` | **supported hypothesis** (PyNifly wiki; project `hkpackfile.py` reads objects) |
| Clips are `hkaSplineCompressedAnimation` in 256-frame blocks; annotations are `hkaAnnotationTrack` text events | **supported hypothesis** (PyNifly wiki); share of interleaved clips **unresolved** |
| Human `skeleton.nif`: 129 NiNodes | **verified**, job AT (next-phase note) |

What the 14,396 `.txt` files in Animations.ba2 are (annotation/sound data, per-clip data tables) is **unresolved**;
Starfield's equivalent sits at `meshes/animtextdata/animationfiledata/*.txt` (verified path).

### Records (verified: xEdit wbDefinitionsFO4.pas; counts from fo4_esm.json)
| Record | Count | Key fields |
|---|---|---|
| IDLE "Idle Animation" | 3,025 | CTDA conditions, DNAM behavior graph, ENAM animation event, ANAM parent + previous (AACT/IDLE), DATA (looping min/max seconds, flags Loose/Sequence/No Attacking/Blocking, animation group section, replay delay), GNAM animation file |
| IDLM "Idle Marker" | 39 | keywords, idle animation list, model, PNAM anim archetype (KYWD), QNAM flavor anim (KYWD) |
| AACT "Action" | 173 | named actions the graph reacts to (e.g. `APR0`/`APR1` Pip-Boy radio off/on) |
| ANIO "Animated Object" | 145 | model + BNAM unload event (props such as cigarettes, clipboards held during idles) |
| FURN | 598 | marker entry points (FNPR), XMRK marker model, workbench data, NAM0 disabled entry points |
| RACE | 45 | male/female behavior graph model (MNAM/FNAM + MODL), SRAC subgraph template race, SADD subgraph additive race, Subgraph Data: SAKD actor keywords, SGNM behaviour graph, SAPT animation paths, STKD target keywords, SRAF role (MT / Weapon / Furniture / Idle / Pipboy) + perspective (3rd / 1st) |
| MOVT | 90 | movement types (speeds per stance) |
| KSSM | 139 | keyword to sound mapping (weapon and foot sounds) |

Sampled RACE subrecords include SAPT 16,730 and SAKD 6,472 rows (fo4_esm.json): subgraphs are how FO4 swaps clip
sets per weapon, furniture, idle and Pip-Boy role, and per first/third person. **Verified** schema; behaviour
**supported hypothesis** (CK wiki, community).

### Engine behaviour (supported hypothesis unless marked)
- An idle plays when a package, scene, furniture or Papyrus call (`PlayIdle`, `PlayIdleAction`,
  `PlayAnimation` on ObjectReference) sends an anim event that the actor's graph accepts. IDLE trees are filtered by
  conditions from the root down.
- First person uses separate `_1stperson` skeleton and clip sets; the SRAF perspective value picks the subgraph.
- Paired animations (killmoves, synced idles) run through the synced behavior (`SyncedAnimBehavior.hkx` verified as a
  file); how killmove IDLEs are chosen per weapon and target race is **unresolved** here.
- Faces: lip data sits in each `.fuz` (`FUZE`, version, lip size, lip data, xWMA; **verified**, PR #361). The FO4 CK
  made it with FaceFX: **supported hypothesis**.

## How Starfield does it

### Files (verified: docs/measurements/sf_ba2.json)
| Item | Count / path |
|---|---|
| `Starfield - Animations.ba2` | 19,358 `.af`, 19,303 `.afx`, 7,744 `.txt`, 390 `.rig`, 347 `.agx`, 12 `.xtbl`, 3 `.csv` |
| Tables | `meshes/animtextdata/tables/anim_actions.xtbl`, `anim_events.xtbl`, `anim_files.xtbl`, `anim_flags.xtbl` (+8 more) |
| Graphs | `meshes/animtextdata/tables/graphs/*.agx` (e.g. `shiptransitionoutfx.agx`, `sfbgs047_vehicle.agx`) |
| Rigs | `meshes/actors/<...>/human/characterassets/skeleton.rig`, `female/skeleton.rig`, `_1stperson/characterassets/skeleton.rig` |
| Furniture clips | `.../animations/furniture/<name>/enterfromstand.af`, `enterinstant.af`, `exittostand.af`, `idle.af` (+ `.afx`) |
| Face | 278,582 `.ffxanim` in FaceAnimation01-04 + Patch, plus `.ffxactor` / `.ffxbones` |
| Human rig | 97 named bones, name table at 0x80 (**verified**, job AU) |

- `.af` header: u16 field 2 = rig bone count (**verified** 4 of 4 door families); field 1 version, field 3 frame
  count (**supported hypothesis**); field 4 **unresolved** (docs/ai/research-log.md 2026-10-09).
- `.afx` is XML of events by frame (state, tag, file, sound or foot events): **verified** (job AS).
- The project already writes `.af` + `.rig` through CALUMI.Animation (`src/fo4sf/native_door.py`): **verified**.
- Whether `.af` is a Havok derivative or a Bethesda format: **unresolved**; public tools describe it only as decoded by
  CALUMI. Starfield still uses Havok for physics (see the physics notes), not for animation files.
- Faces are FaceFX: the CK compiles `.ffxanim` per line with `ffxc.exe` and ships `.facefx` actors (**verified**, see
  [../next-phase/voice-lipsync-companions.md](../next-phase/voice-lipsync-companions.md)).

### Records (verified: xEdit wbDefinitionsSF1.pas; counts from sf_esm.json)
| Record | Count | Change from FO4 |
|---|---|---|
| IDLE (named "Animation") | 1,158 | same CTDA/DNAM/ENAM/ANAM/GNAM; DATA is gone, replaced by FNAM flags (Loose, Preview); adds FULL. Sampled: 300 of 300 IDLE have FNAM, none DATA (sf_esm.json) |
| IDLM | 18 | adds VMAD, components, RNAM actor action (AACT); keeps QNAM flavor and PNAM archetype |
| AACT | 222 | same role |
| ANIO | 63 | BNAM unload event gone; adds VMAD, XALG and components |
| FURN | 899 | entry points FNPR kept; adds activation angles (JNAM/GNAM), FTMP furniture template, NNAM marker files |
| RACE | 31 | Subgraph Data kept (SAKD/SGNM/SAPT/STKD/SRAF); SADD moved inside each subgraph entry; roles now MT / Weapon / Furniture / Linking Only / Pipboy / MT, Weapon and Furniture Generation |
| MOVT / KSSM | 43 / 500 | kept |
| Base-form graph | | an "Animation Graph" component carries ANAM root animation graph (doors: `SimpleOpenClose01.agx`, verified 215 of 339 DOOR) |

The Pipboy role still exists in Starfield's subgraph enum: a hook for an arm-mounted menu, use **unresolved**.

## Mapping for the port
| FO4 piece | Starfield counterpart | Verdict | Notes |
|---|---|---|---|
| `.hkx` clip | `.af` + `.afx` | rebuild (tool) | decode spline, retarget via `human_bones.py`, write via CALUMI; next-phase steps 1-3 |
| `.hkx` annotations | `.afx` events | translate | event names must exist in `anim_events.xtbl` or an override |
| `.hkx` behavior graph / project | `.agx` graph | drop / rebuild later | use Starfield graphs; new graph authoring **unresolved** |
| `skeleton.hkx` / `skeleton.nif` | `.rig` | rebuild | humans: Starfield rig; creatures need own rigs (no counterpart) |
| IDLE | IDLE | translate | DNAM graph path and ENAM event must point at Starfield graphs/events; DATA loop and replay values have no slot (**unresolved** where they went) |
| IDLM | IDLM | translate | archetype/flavor keywords need Starfield keyword equivalents |
| ANIO | ANIO | translate | unload event lost; held props still need graph support |
| FURN entry points | FURN + furniture clips | translate + rebuild | FO4 furniture clips must be retargeted |
| RACE Subgraph Data | RACE Subgraph Data | translate | paths (SAPT) must name Starfield folders; FO4 "Idle" role maps to? **unresolved** |
| Killmoves / paired | unknown | rebuild later | Starfield paired system **unresolved** |
| `.fuz` lip data | `.ffxanim` | rebuild | regenerate with FaceFX from WAV + text (preferred) |
| First person | `_1stperson` rigs | carries as concept | Starfield has 1st-person rigs (verified paths) |

## What must be rebuilt, and what needs SFSE or the Creation Kit
- Rebuild: every clip (decoder + retarget + writer), every creature rig, every face line, FO4-only furniture clips.
- **CK2:** adding entries to `.xtbl` tables or new `.agx` graphs is likely CK-side or hand-edited data; whether a
  plugin can ship a new graph that the engine loads is **unresolved**.
- **SFSE:** not needed for clip replacement. Possibly needed for runtime graph-variable access beyond Papyrus.
- FaceFX lip generation needs Starfield's Tools (`ffxc.exe`) or the CK2 compiler on the player's PC.

## Port status and links
- Door clips: `.af`/`.rig` written and read back (docs/spikes/sliding-doors.md, decisions.md); graph unchanged.
- Bone map FO4 129 to Starfield 97: `src/fo4sf/human_bones.py` (PR #371).
- Plan, first proofs A1-A4: [../next-phase/animations-ui-and-start.md](../next-phase/animations-ui-and-start.md).
- Lip sync plan: [../next-phase/voice-lipsync-companions.md](../next-phase/voice-lipsync-companions.md).
- Furniture and doors: [../next-phase/doors-activators-workshops.md](../next-phase/doors-activators-workshops.md).

## Open questions and cheap checks
- What the FO4 `.txt` files in Animations.ba2 hold: list 20 names and read 3 (PC, read-only).
- Spline vs interleaved share: count `hkaSplineCompressedAnimation` vs `hkaInterleavedUncompressedAnimation` class
  names across FO4 `.hkx` with `hkpackfile.py` (PC, read-only).
- Where FO4 IDLE DATA loop/replay went: dump 10 Starfield IDLE records with FNAM and compare to their `.afx` (SfInspect).
- Can a plugin add an `.agx`? Grep `.agx` names referenced by Starfield.esm vs files on disk; any orphan graphs?
- Killmoves: search `anim_events.xtbl` for "paired", "killmove", "sync" strings.
- Is `PlayIdle` in Starfield's `ObjectReference.psc`/`Actor.psc`? Grep ContentResources.zip.

## Sources
- Repo: docs/measurements/fo4_ba2.json, sf_ba2.json, fo4_esm.json, sf_esm.json; docs/ai/research-log.md (2026-10-09
  `.af` header); docs/spikes/sliding-doors.md; docs/ai/decisions.md.
- xEdit record definitions (TES5Edit dev-4.1.6): `Core/wbDefinitionsFO4.pas`, `Core/wbDefinitionsSF1.pas`,
  https://github.com/TES5Edit/TES5Edit
- [PyNifly wiki: HKX Animation Format (FO4, Skyrim)](https://github-wiki-see.page/m/BadDogSkyrim/PyNifly/wiki/HKX-Animation-Format-(FO4---Skyrim))
- [Animation IO for Starfield (Nexus 16184)](https://www.nexusmods.com/starfield/mods/16184), [CALUMI.Animation](https://github.com/Calaverah/CALUMI.Animation)
- [Behavior Graph Studio (Nexus FO4 107691)](https://www.nexusmods.com/fallout4/mods/107691)
