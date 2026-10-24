# Doors, activators, furniture and containers (FO4 CE1 vs Starfield CE2)

Part of the engine-mechanics reference ([index](README.md)). Author: Claude-cloud, 2026-10-19. Labels: verified /
supported hypothesis / unresolved.

This is a mechanism summary. The project has already done a lot of verified door work; this file points at it and
does not repeat it:
[door-behaviour.md](../../spikes/door-behaviour.md) (what decides a door's behaviour, per field),
[WP-doors-research.md](../../spikes/WP-doors-research.md) (hinged doors working in game, multi-part doors),
[sliding-doors.md](../../spikes/sliding-doors.md) (123 vanilla door rigs surveyed, own rigs for vault and elevator
doors, Starfield's three elevator mechanisms), docs/terrain/scripted-doors.md and garage-button.md, and the plan in
[../next-phase/doors-activators-workshops.md](../next-phase/doors-activators-workshops.md). Record layouts below are
**verified with xEdit** (`wbDefinitionsFO4.pas`, `wbDefinitionsSF1.pas`, TES5Edit dev-4.1.6) unless marked otherwise.

## In short
- **Door records and load doors carry over almost 1:1.** DOOR, the REFR teleport `XTEL` (door, arrival pos/rot, flags
  No Alarm / No Load Screen / Relative Position, transition interior) and the lock `XLOC` (same level enum, key, Leveled
  Lock flag) have the same layout in both games (**verified**, xEdit). Verdict: **translate**.
- **Door motion is a rebuild.** FO4 animates doors inside the NIF (controller sequences "Open" / "Close"); Starfield
  NIFs have no controllers and the DOOR's animation graph component points at a shared `.agx` graph plus the door's own
  `skeleton.rig` and `open.af` / `close.af` (**verified** by the project, in game for hinged doors).
- **Activate parents are gone in Starfield**: the REFR has no `XAPD` / `XAPR` (**verified**, xEdit). The port wires
  buttons with vanilla `DefaultActivateLinkedRefOnActivate` and a `LinkCustom02` linked ref (**verified**, project).
- **Furniture and containers keep their model**: FURN markers, entry points, interaction flags and bench types, and
  CONT inventory plus Respawns flag, exist in both (**verified**, xEdit). Sounds move to Wwise references; furniture
  animations are an animation-lane rebuild.
- No SFSE need found for this area. Elevators and FO4 quest doors need Papyrus on Starfield's vanilla patterns.

## How Fallout 4 does it

### DOOR (369 records; verified, docs/measurements/fo4_esm.json)
| Field | Meaning (verified, xEdit unless noted) |
|---|---|
| `FULL`, `MODL`, `DEST`, `KWDA`, `NTRM`, `VMAD` | name in the prompt, model, destructible data, keywords, native terminal, scripts |
| `SNAM` / `ANAM` / `BNAM` | open / close / loop sound (SNDR) |
| `FNAM` flags (u8) | bit1 Automatic, bit2 Hidden, bit3 Minimal Use, bit4 Sliding, bit5 Do Not Open in Combat Search, bit6 No "To" Text (bit0 unnamed) |
| `ONAM` / `CNAM` | alternate prompt text for open / close |
| `TNAM` (array) | **random teleport destinations** (CELL or WRLD) |
| record flags | Non Occluder, Has Distant LOD, Random Anim Start, Is Marker |

So `AutoloadDoorNoText` with FNAM 0x42 is Automatic + No "To" Text (bit values **verified** with xEdit; the record is
from docs/spikes/B4-mission-anatomy.md).

### Door behaviour on the placed reference (verified, xEdit REFR)
- `XTEL` teleport (above), `XTNM` teleport location name (MESG).
- `XLOC` lock: level 0 None, 1 / 25 Novice, 50 Advanced, 75 Expert, 100 Master, 251 Barred, 252 Chained,
  253 Requires Terminal, 254 Inaccessible, 255 Requires Key; key (KEYM); flag Leveled Lock.
- `XAPD` Parent Activate Only plus `XAPR` activate parent refs with a delay: a button, plate or terminal activates
  the door.
- `XESP` enable parent (flags: opposite of parent, pop in); `XLKR` linked refs by keyword; `XNDP` navmesh door link;
  `XPRM` primitive (box, sphere, plane, line, ellipsoid) for trigger volumes; open by default.
- Motion: NIF `NiControllerManager` with "Open" / "Close" `NiControllerSequence`s and text keys (**verified**,
  WP-doors-research.md). FO4 doors are hinged, sliding, lifting or multi-part (sliding-doors.md).
- Scripts: Papyrus `ObjectReference` door and lock functions (`SetOpen`, `GetOpenState`, `Lock`, `Unlock`,
  `SetLockLevel`, `Activate`, `BlockActivation`) and events (`OnActivate`, `OnOpen`, `OnClose`) per the FO4 CK wiki
  (**supported hypothesis**: names from https://falloutck.uesp.net/wiki/ObjectReference_Script, not re-read here).
  Preston's door: `Unlock` then `SetOpen` (**verified**, B4-mission-anatomy.md).

### ACTI (1,284), TACT (43)
- ACTI (**verified**, xEdit): FULL, model, DEST, keywords, PRPS, `SNAM` looping / `VNAM` activation sound, `WNAM` water
  type, `ATTX` activate text override, `FNAM` flags (No Displacement, Ignored by Sandbox, Is a Radio), `KNAM`
  interaction keyword, `RADR` radio receiver, conditions, `NVNM`. Record flags include Dangerous, Used as Platform,
  Child Can Use, navmesh cut flags.
- TACT talking activators are FO4-only (none in Starfield.esm, **verified** counts).
- Triggers: an activator REFR with an `XPRM` box; FO4's Vault 111 exit `vaultExitElevatorDown` 020C39 is such a box
  (**verified**, sliding-doors.md). Scripts react with `OnTriggerEnter` / `OnTriggerLeave` (**supported hypothesis**,
  falloutck event list).
- Animated activators play NIF sequences by name from Papyrus (`VltElevator` stage1..stage8, `VltGearDoor01`
  Stage0..Stage3; **verified**, sliding-doors.md).

### FURN (598)
- **verified**, xEdit: `MNAM` active markers / flags (interaction points 0-21, Allow Awake Sound, Enter With Weapon
  Drawn, Play Anim When Full, Disables Activation, Is Perch, Must Exit to Talk, Use Static Avoid Node, Is Sleep
  Furniture); `FNPR` marker entry points (type Sit / Lay / Lean; entry Front / Behind / Right / Left / Up); `ENAM` +
  `NAM0` disabled entry points per marker; `XMRK` marker model; `SNAM` marker parameters (offset, rotation, keyword).
- `WBDT` bench type: Create Object, Weapons, Alchemy (chem and cooking), Armor, Power Armor, Robot Mod; `NAM1`
  associated form; `CNTO` items (Has Container flag); record flag Power Armor.
- The marker positions live in the NIF too (furniture marker nodes: **supported hypothesis**, nif.xml naming, not
  checked by the project). Sit / sleep / work animations: Havok behaviour `SingleAnimFurniture.hkx` and friends
  ([animations.md](animations.md)).

### CONT (471)
- **verified**, xEdit: `CNTO` items (count, optional owner and condition data), `DEST`, `DATA` flags (Allow Sounds
  When Animation, Respawns, Show Owner) + weight, `SNAM` open / `QNAM` close / `TNAM` take-all sounds, `ONAM` filter
  list, `NTRM`, `FTYP`.
- Respawn: a Respawns container refills when its cell resets (**supported hypothesis**; encounter zones and cell reset
  in [leveled-lists-and-encounter-zones.md](leveled-lists-and-encounter-zones.md)).
- The settlement workbench is a CONT with `WorkshopScript` ([workshop-and-settlements.md](workshop-and-settlements.md)).

## How Starfield does it

| Record | Same as FO4 | Changed / new (all **verified**, xEdit) | Count |
|---|---|---|---|
| DOOR | FULL, model, DEST, KWDA, NTRM, VMAD, ONAM / CNAM alt text, FNAM bits 1-6 | FNAM bit0 **No Quest Target**, bit7 **No Direct Activation**; sounds are Wwise refs `DOSH` / `DCSH` / `DLSH`; `DEVT` sound level; `ANAM` facing axis override; base form components (the animation graph component: `BGSAnimationGraph_Component`); `NVNM`; **no TNAM random teleport list** | 339 |
| REFR door fields | `XTEL`, `XTNM`, `XLOC` (same enum), `XESP`, `XLKR`, `XNDP`, `XPRM` (adds Cylinder), open by default | **no `XAPD` / `XAPR`**; `XATR` attach ref (parts riding a platform); `XLMS` layered material swaps | |
| ACTI | model, DEST, keywords, PRPS, ATTX, FNAM (No Displacement, Ignored by Sandbox, Is a Radio), RADR, conditions | Wwise `ALSH` / `ACSH` sounds; water material; `JNAM` / `INAM` activation angle; **KNAM interaction keyword commented out**; FNAM adds Is Water, Non-Planar, Allow Displacements, Use Global Probe | 1,463 |
| FURN | MNAM flags, FNPR entry points, XMRK, SNAM marker params, WBDT, NAM1 | MNAM adds Allow Cloth Sim, Disable Physics; `JNAM` / `GNAM` activation angles (player, sitting actor); `FTMP` furniture template; `NNAM` marker files (name + model); bench types add **Extractor** and **Research** | 899 |
| CONT | CNTO, DEST, Respawns / Show Owner flags, ONAM filter | DATA is flags only (**no weight**); Wwise `WED0` / `WED1` open / close; object template, `APPR` | 707 |

Engine side (project evidence):
- Door motion: 310 of 339 DOORs carry an animation graph component; 18 graphs, `SimpleOpenClose01.agx` on 215; load
  variants use `*_Load` graphs; the motion is each door's rig and clips (**verified**, sliding-doors.md).
- Load doors: 964 of 964 vanilla load-door refs are persistent with both ends linked; 458 load bases have no graph and
  are Hidden or Automatic (e.g. `LoadElevator_InvisibleDoor`, scripted `AutoloadDoor_Cave`) (**verified**,
  next-phase note 2.1).
- Elevators: `ElevatorMasterScript`, `MovingPlatformMasterScript` (`TranslateToRef` between floor markers, parts by
  `XATR`), load elevators (**verified**, sliding-doors.md).
- Activate chains: `DefaultActivateLinkedRefOnActivate` with a keyword linked ref replaces activate parents
  (**verified**, docs/terrain/garage-button.md).

## Mapping for the port

| FO4 piece | Starfield counterpart | Verdict | Notes |
|---|---|---|---|
| DOOR FULL, alt text, FNAM bits 1-6 | same fields | data copy | bit0 / bit7 have new meanings: write 0 |
| DOOR sounds (SNDR) | Wwise sound refs | translate | pick vanilla door sounds per material; audio lane |
| DOOR TNAM random teleports | none | script shim | FO4SF door script picking a destination (count is a cheap check) |
| Door NIF sequences | graph + rig + `.af` | rebuild | done offline for hinged (template), multi-part and sliding (own rig) |
| REFR XTEL | XTEL | data copy | interiors work; exterior side scripted (MoveTo) until the persistent-position issue is fixed |
| REFR XLOC | XLOC | data copy | level 253 needs the terminal fragment; key needs its KEYM in the build |
| REFR XESP | XESP | data copy | write only when the parent is built |
| REFR XAPD / XAPR | `DefaultActivateLinkedRefOnActivate` + XLKR | script shim | one parent, many children needs a small FO4SF script |
| ACTI KNAM interaction keyword | none | drop / script | check what FO4 uses it for before dropping |
| ACTI / trigger XPRM | XPRM | data copy | the trigger's collision layer must exist (see physics file) |
| Animated activators (stage clips) | graph that plays named clips, or `TranslateToRef` platform | rebuild | Vault 111 elevator and cog door: not done |
| FURN markers, FNPR, MNAM | same | translate | marker NIF nodes and furniture clips need the animation lane |
| FURN WBDT benches | WBDT or a vanilla bench REFR | translate | port places the vanilla bench of the kind (stations.md, offline) |
| CONT items, Respawns | CNTO, Respawns | translate | FO4 LVLI must exist in the build; today a fixed vanilla table per kind |
| CONT weight | none | drop | |

## What must be rebuilt, and what needs SFSE or the Creation Kit
- Rebuild: door motion (in progress), animated activators, elevators, furniture enter / exit / idle clips, sounds.
- Script shims: activate parents with several children, random teleport doors, FO4 quest-door scripts, elevator panels.
- SFSE: none known. CK2: not needed for records; the Papyrus compiler from the CK is already used for FO4SF scripts.

## Port status and links
- **In game (verified):** hinged FO4 doors open and close on the Akila template rig with a keyframed leaf body
  (Hotel Rexford, Parsons; WP-doors-research.md attempt 3, journal 2026-10-08/09). Interior load doors teleport between
  converted cells (journal 2026-10-10/11). The first scripted exterior-to-interior door worked (Super Duper Mart,
  journal 2026-10-16 night). A converted FO4 first-aid kit opened Starfield's container menu (journal 2026-10-15).
- **Offline only:** multi-part and sliding doors on own rigs (PR #79, sliding-doors.md), open-by-default, door survey
  tools `door_survey.py` / `door_audit.py`, activate-parent metadata (journal 2026-10-17), containers, activators,
  terminals and benches in the core build plan (docs/terrain/commonwealth-build-plan.md, stations.md).
- **Not written yet:** locks, enable parents on doors, door FNAM flags, FO4 names on exterior doors, door sounds,
  elevators (door-behaviour.md table; next-phase note 3.1).
- Related: [world-cells-navigation.md](world-cells-navigation.md) (load doors, navmesh door links),
  [terminals-holotapes-locks.md](terminals-holotapes-locks.md) (locks, terminal doors),
  [workshop-and-settlements.md](workshop-and-settlements.md), [animations.md](animations.md) (furniture clips),
  [physics-and-collision.md](physics-and-collision.md) (keyframed door bodies, triggers).

## Open questions and cheap checks
- Count FO4 DOORs with `TNAM` random destinations (xEdit filter or Fo4Export over Fallout4.esm + DLC).
- Is FO4 FNAM bit0 ever set on vanilla doors? If yes it would turn into No Quest Target (xEdit scan).
- What does FO4 use ACTI `KNAM` for (xEdit: list ACTIs with KNAM and their keywords)?
- Do `OnOpen` / `OnClose` / `SetOpen` / `Lock` exist in Starfield's `ObjectReference.psc` (grep ContentResources.zip)?
- How does a Starfield NIF mark furniture entry points (dump one vanilla chair NIF and its FURN `NNAM`)?
- Mutagen 0.55 Starfield `PlacedObject` fields for lock and enable parent (next-phase check P3).

## Sources
- xEdit definitions, TES5Edit dev-4.1.6: `wbDefinitionsFO4.pas` DOOR 6477, ACTI 5611, CONT 6176, FURN 6848, REFR
  XTEL / XAPD / XLOC 11550-11700, furniture flags 5279; `wbDefinitionsSF1.pas` DOOR 11575, REFR 8640-9040, XLOC 3776,
  XESP 3892, ACTI 9199, CONT 10982, FURN 12126; `wbDefinitionsCommon.pas` furniture entry flags 8261.
- Repo: docs/spikes/door-behaviour.md, WP-doors-research.md, sliding-doors.md, B4-mission-anatomy.md;
  docs/terrain/scripted-doors.md, garage-button.md, stations.md, commonwealth-build-plan.md; docs/JOURNAL.md
  2026-10-08 to 2026-10-17; docs/measurements/fo4_esm.json, sf_esm.json.
- Plan: [../next-phase/doors-activators-workshops.md](../next-phase/doors-activators-workshops.md).
- FO4 CK wiki: https://falloutck.uesp.net/wiki/Door , https://falloutck.uesp.net/wiki/ObjectReference_Script
