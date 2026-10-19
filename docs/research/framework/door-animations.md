# Door enter and exit animations: research framework (phase 2)

Owner: the "Door animations" thread (Claude-cloud). Started 2026-10-19 17:45Z. Status: **two waves written; door graphs read (A1); Starfield Papyrus API read (§1); 40 questions in section 6**. Labels: **verified** (read from a file or a command we ran), **supported** (sourced, not yet tested here),
**unresolved**. Sources are linked inline. The index of every phase's framework is this folder's README.md (owned by the
"Next-phase research framework" thread).

Where we are (verified, draft PR #392, docs/spikes/load-door-animations.md; all switches off, nothing installed):
- Load doors can be rigged like ordinary doors (`convert_batch.py --rig-load-doors`); 16 of the 20 FO4 load-door models
  in the port cells have their own Open sequence (PC read A5).
- One DOOR record opens and then travels. Scripted doors (exterior <-> interior) use FO4SF_AnimatedLoadDoor, which
  compiles (A4). XTEL doors (interior <-> interior) get a copy of the record with the vanilla `*_Load` graph (A1).
- Vanilla door sounds are mapped from Starfield.esm (A7: 310 doors with sounds, WWise GUIDs only).
- Not done: the outdoor side (the core's ACTI becomes a DOOR; after the v6e test), and every in-game check (G1 to G3).

Sections (filled as agents return):
1. How Starfield's doors and load doors work (records, graphs, XTEL, load screens, Papyrus, sounds)
2. How Fallout 4's doors work and what we must carry over (NIF sequences, elevators, vault doors, scripted doors)
3. Tools and pipelines (Creation Kit, xEdit, Mutagen, NIF and animation tools, Havok, WWise)
4. Prior art and modding communities (ports, total conversions, door and animation mods, what broke for them)
5. Player and NPC side (interaction animations, NPCs using doors, navmesh door links, followers)
6. The framework of questions (by phase step, each with what answers it)

## 1. How Starfield's doors and load doors work (agent report 2026-10-19; read from xEdit, Mutagen and CommonLibSF source, and CK wiki pages)

The DOOR record:
- **Subrecords** (verified, Mutagen `Door.xml`, xEdit `wbDefinitionsSF1.pas:11575-11618`): VMAD, OBND, the component block
  (AnimationGraphComponent), FULL, Model, KWDA, NTRM (native terminal), **DOSH open sound, DCSH close sound, DLSH loop
  sound**, FNAM flags, ONAM/CNAM alternate texts, DEVT sound level, ANAM facing axis, NVNM.
- **FNAM bits** (verified): 0x01 No Quest Target, 0x02 Automatic, 0x04 Hidden, 0x08 Minimal Use, 0x10 Sliding, 0x20 Do
  Not Open in Combat Search, 0x40 No "To" Text, 0x80 No Direct Activation. FO4's bits 0x02 to 0x40 mean the same, so
  **FO4 flags can be copied bit for bit**; 0x01 and 0x80 are new in Starfield.
- FO4 has random teleport destinations (TNAM); Starfield's record definition does not, though the runtime struct keeps
  the field (CommonLibSF `TESObjectDOOR.h:58`). CommonLibSF calls DLSH a *lock* sound; Mutagen and xEdit call it a
  *loop* sound (unresolved).
- **AnimationGraphComponent** has five fields (verified): ANAM graph, BNAM rig, CNAM animations path, **DNAM response
  file**, **ENAM "controls base skeleton"**. We write the first three; whether vanilla `*_Load` doors set DNAM or ENAM
  is unresolved (PC read).
- `SimpleOpenClose01.agx` builds on `SimpleOpenClose_Base01`, with the events `Open`/`Close` and the variables `AnimSpeed`
  and `OpenCloseFormState`; clips are found through `.afx` descriptors next to `.af` files (verified, repo
  `docs/handoff-archive/2026-10-07-codex-history.md:439`). **What a `*_Load` graph adds is the biggest unknown:** there
  is no public spec of `.agx` (unresolved; a PC diff of the graphs answers it).

**Graph read (PC read A1 / job 17, 2026-10-19, `extract_door_graphs.py` at fd26932: 30 door graphs from Starfield -
Animations.ba2, summary in D:\Modding\scratch\door_graphs; verified unless marked).** `.agx` is XML: nodes
(NT_STATE_MACHINE_EMBEDDED, NT_BLEND_TREE_EMBEDDED, NT_ANIMATION_NODE, NT_ASSIGN_VARIABLE, NT_GRAPH_REF, ...) with
property sheets.
- `SimpleOpenClose01` is a thin wrapper: a Graph Ref to `SimpleOpenClose_Base01` plus "Capacity" effect states.
- `SimpleOpenClose_Base01` is a four-state machine. Each state assigns `OpenCloseFormState`: Opened 1, Opening 2,
  Closed 3, Closing 4. **These are exactly GetOpenState's values**, so the script's wait on state 1 reads the graph
  (supported: the variable name and the matching numbers). The event `Open` enters Opening, which plays the `Open`
  clip at `AnimSpeed` (default 1), whole; `Close` is the mirror. Opening and Closing send `Trans01` on entry and
  **`Done` on exit**, so `PlayAnimationAndWait("Open", "Done")` is a safe call on these doors (supported).
- **The `*_Load` graphs are self-contained, not wrappers.** In `SimpleOpenClose02_Load`, Opening plays `Open` at speed
  **0.8 with the last 20 frames cropped**, then moves to Opened. Opened plays the `Close` clip cropped at both ends and,
  when that ends, **sends `Close` by itself**. **A vanilla load door shuts itself after opening**, with no script.
- `SimpleOpenClose01_Load` to `10_Load` are near-identical (39,429 to 41,125 bytes); 02 against 06 differs only in
  whether Opened's speed is `AnimSpeed`. The rig and clips make the difference, not the graph.
  `07_Load` and `StateOpenClose01_Load` add Graph Refs; `SpecialOpenCloseAirlock01_Load` adds effect sequences.
- **Consequence:** a `*_Load` graph crops 20 frames (0.67 s at 30 fps). FO4's own clips run 4 to 40 frames (A5), so
  most would play nothing, or almost nothing, under a load graph. **Own-rig load doors must keep `SimpleOpenClose01`**
  (as the writer does). The `_XtelLoad` copy stays limited to Akila-template doors, whose 31-frame clip leaves 11 frames
  at speed 0.8, about 0.46 s (inferred from the numbers above).

Teleport (XTEL) and load doors:
- XTEL (verified): the destination door, position, rotation, flags (No Alarm 0x1, **No Load Screen 0x2**, Relative
  Position 0x4) and a Transition Interior cell. XTNM is the teleport name. Vanilla data uses No Load Screen on 4 of 964
  references and Transition Interior on none.
- A reference also carries Lock (XLOC: levels 0 to 100, plus 251 Barred, 252 Chained, 253 Requires Terminal, 254
  Inaccessible, 255 Requires Key), the navmesh door link XNDP, OpenByDefault and TeleportName (verified, Mutagen dev).
- The engine plays a graph-bearing load door's open before the load screen (supported, Instant Doors 2313). What ends
  the wait is unresolved, but it is not an ini timer: INSTANT DOORS' ini lines only remove fades, and its speed-up ships
  as loose files (verified, its files tab; correction of an earlier claim here). Mod 2489's door files are graphs, so the
  `*_Load` graph's playback most likely sets the wait (supported); G2's stopwatch decides.
- Load elevators: a visible `*_Load` DOOR animates while a hidden `LoadElevator_InvisibleDoor` (322 refs) carries the
  XTEL (verified, repo). This "visible door plus hidden load door" pattern could serve the outdoor side.

Papyrus (CK wiki, Skyrim and FO4 lineage; Starfield names verified by our A3 read):
- GetOpenState: 0 none, 1 open, 2 opening, 3 closed, 4 closing. **OnOpen fires when a door has finished opening**, so it
  can replace FO4SF_AnimatedLoadDoor's polling loop.
- OnActivate runs after the door's own activation has started, and **still fires on a locked door**, so the script
  needs a lock check (verified, falloutck OnActivate). FO4SF_AnimatedLoadDoor has none today.
- BlockActivation plus `Activate(ref, True)` gives full control of the order (open by script, wait for OnOpen, then
  travel) (verified, ck.uesp BlockActivation).
- PlayAnimationAndWait never returns if the graph never sends the named event (verified), so it stays unused until we
  know a door graph's output events. Vanilla uses `PlayAnimationAndWait("Play01", "done")` on an elevator helper.
- Starfield 1.16's own sources (verified, rux616/modding-sf1-scripts-vanilla, cross-checked with the Community Patch
  mirror; file:line):
  | Function or event | Where |
  |---|---|
  | `RegisterForAnimationEvent(akSender, asEventName)` (native, selfonly), `OnAnimationEvent`, `OnAnimationEventUnregistered` | ScriptObject.psc:81, 368, 373 |
  | `RegisterForPlayerTeleport()`, `OnPlayerTeleport()` (load door, fast travel, MoveTo) | ScriptObject.psc:178, 441 |
  | `IsLocked()`, `GetLockLevel`, `SetLockLevel`, `OnLockStateChanged` | ObjectReference.psc:764, 497, 1058, 1661 |
  | `Lock(abLock, abAsOwner, abTraverseLinkedLockables = true)` | ObjectReference.psc:801 |
  | `GetOpenState` (0 none, 1 open, 2 opening, 3 closed, 4 closing), `SetOpen`, `OnOpen`, `OnClose` | ObjectReference.psc:514, 1090, 1673, 1607 |
  | `BlockActivation`, `IsActivationBlocked`, `PlayAnimation`, `PlayAnimationAndWait`, `WaitFor3DLoad` | ObjectReference.psc:245, 702, 879, 882, 1201 |
  | `GetTeleportCell`, `GetTransitionCell`, `IsRefInTransitionCell`, `IsTeleportAreaLoaded` | ObjectReference.psc:584, 587, 785, 788 |
- **Risk:** Starfield's `Lock` has a third parameter FO4's lacks and, by default, also locks "linked lockable" references,
  which may include a door's XTEL partner. Our scripts pass `abTraverseLinkedLockables = False` unless that is wanted.
  What counts as linked lockable is unresolved; FO4 closes an open door at once when it is locked (verified FO4 only).
- Animation-event registration needs the 3D loaded and drops when the graph unloads (verified FO4 wiki; supported
  for Starfield).

Sounds: SoundReference is a WWise start GUID, a stop GUID, a condition and an event mapping (verified; A7 found only the
GUIDs used). That a plugin can play vanilla events by GUID without its own soundbank is a supported hypothesis to check
by ear in game.

Known limits: stuck doors are a vanilla bug that a reload clears (supported). Our overlay's persistent references keep
unmerged positions, which breaks native exterior XTEL; that is why exterior doors are scripted (verified, repo).

## 2. How Fallout 4's doors work and what must carry over (agent report 2026-10-19; counts from docs/terrain/data/interior-backlog.json)

- **The record** (supported, xEdit `wbDefinitionsFO4.pas:6477-6503`; meanings verified, https://falloutck.uesp.net/wiki/Door):
  sounds are SNDR forms (SNAM open, ANAM close, BNAM loop), so they cannot be copied and must be mapped (A7 does this).
  FNAM bits 1 to 6 match Starfield's. TNAM holds random teleport destinations, which Starfield lacks. A load door differs
  from a normal door "only cosmetically"; the trip comes from the linked references (XTEL).
- **XTEL and XLOC** have the same layout and the same lock levels in both games (supported, xEdit), so locks copy byte for
  byte. Whether Starfield honours 251 to 254 (Barred, Chained, Requires Terminal, Inaccessible) the way FO4 does is
  unresolved.
- **Motion** comes from NIF Open/Close sequences with `Sound:` text keys (verified, repo). No FO4 DOOR with a behaviour
  graph was found. Whether FO4 plays the whole Open sequence before the load is unresolved; our wait is a design choice.
- The backlog lists **230 interiors** behind Commonwealth doors; the whole census is 271 (see the count reconciliation in
  section 5).

Door families, by exterior load-door references (373 in all, the agent's grouping by base name):

| Family | Refs | Examples | What carries over |
|---|---|---|---|
| Hinged single | ~203 | IndMetalDoorLoad01 53, PaintedWoodDoorLoadA01 26 | rig, open then trip, sounds, Minimal Use |
| Double | ~70 | IndMetalDbDoorLoad01 20, BldWoodPDbDoorLoad01 12 | own rig (the template has one leaf) |
| Trapdoor, hatch, manhole | ~48 | MetalTrapdoor01 26, RoofHatch01 9 | horizontal leaf; ladder sides stay instant |
| Load elevator | ~21 | LoadElevatorDoorHiTech 8, ...Utility 7 | panel, door and meter chain; transition cell; quest gating |
| Automatic or invisible | ~17 | AutoloadDoor 13, InvisibleLoad01HiddenMinUse 3 | never animate or wait; keep Automatic |
| Special | ~14 | SubDoor02LeftLoad 6, TrinityDoor01 4, one-way grate | case by case |

- **Elevators** (supported, Nexus FO4 73623 and forum posts quoting the scripts): the player rides through an
  elevator-car transition cell while the next area loads. `LoadElevatorPanelScript` chains the button, the door and the
  interior panel, and plays `Play01`/`Play02`. Quests gate them with `MakeElevatorFunctional` (Fort Hagen in MQ106,
  https://afktrack.afkmods.com/index.php?a=issues&i=23192). Starfield has scripts of the same name (`ElevatorMasterScript`,
  `LoadElevatorManagerScript`), but whether the APIs match is unresolved.
- **Vault 111** (verified, repo B4-mission-anatomy.md): the cog door is an Activator played by the quest script, and the
  exit elevator is an activator ride plus an Automatic invisible door (`AutoloadDoorNoText` 0007ECFC). Neither is an
  animated load door; this belongs to the new-game thread's path.
- **Locks and quests:** XLOC 253 means a terminal or script unlocks the door. Quest scripts call Unlock and SetOpen
  (Preston's door). Enable parents and object swaps decide whether some doors can be used at all (Fort Hagen blockers,
  supported).

## 3. Tools and pipelines (agent report 2026-10-19, plus leads from findings/asset-conversion.md)

| Tool | Use for us | Licence | State |
|---|---|---|---|
| [CALUMI.Animation](https://github.com/Calaverah/CALUMI.Animation) | writes `.af` clips and `skeleton.rig` (our own-rig doors) | LGPL-3.0 | alpha; full `.af`/`.rig` decoding and compression "planned" (verified) |
| [Animation IO](https://www.nexusmods.com/starfield/mods/16184) | Blender import/export of `.af`/`.rig` via CALUMI | MIT in its manifest, but the Nexus terms forbid redistribution or conversion to other games: **conflicting** | 1.0.0 |
| [CALUMI Motion](https://www.nexusmods.com/starfield/mods/16181) | views `.agx` graphs | Nexus: no redistribution | 0.1.1.1 |
| [Starfield-Behavior-Editor](https://github.com/Monitor221hz/Starfield-Behavior-Editor) | `.agx` editor; **parses `.agx` as XML** | GPL-3.0 | stale since 2023-12 |
| [PyNifly](https://github.com/BadDogSkyrim/PyNifly) | imports FO4 NIF door sequences and FO4 `.hkx` into Blender | GPL-3.0 | active; Windows only |
| [Mutagen](https://github.com/Mutagen-Modding/Mutagen) / [Spriggit](https://github.com/Mutagen-Modding/Spriggit) | DOOR records with graph and WWise sounds / text diffs of plugins | GPL-3.0 | pinned 0.55.0-alpha.67 |
| [xEdit](https://github.com/TES5Edit/TES5Edit) | record inspection | MPL-2.0 | active |
| [wwiser](https://github.com/bnnm/wwiser) | reads `.bnk` (read-only) | no licence file: avoid as a dependency | active |
| Wwise 2021.1.14.8108 + the CK's `Starfield.wproj` | new sound events and banks | Audiokinetic terms unresolved | community guide [12561](https://www.nexusmods.com/starfield/mods/12561) |
| [NAF](https://www.nexusmods.com/starfield/mods/7360), [SAF](https://www.nexusmods.com/starfield/mods/16124), [OSF](https://www.nexusmods.com/starfield/mods/17457) | SFSE frameworks that play glTF or `.af` clips on actors without `.agx` | NAF GPL-3; others per page | for actor animations, not doors |

- **Formats.** `.agx` is an XML graph (verified from the Behavior-Editor's serializer: a `<root>` with `node`, `node_group`
  and `property_sheet`), so Python's standard library can read and diff it. `.af` holds keyframe clips; CALUMI's headers
  show no event field, so FO4's sound text keys cannot ride in `.af` (supported). Starfield uses its own behaviour
  system, not Havok, for animation; Havok remains for physics (supported). FO4 behaviour graphs therefore cannot be
  converted. The rule is to **map onto a vanilla `.agx` and never edit a shared one**.
- **No FO4-to-Starfield animation converter exists** apart from ours (`native_door.py`: NiControllerSequence keys sampled at 30 fps,
  written through CALUMI). PyNifly plus Animation IO make a manual chain that can serve as an **independent check** of our
  converter, though not as a batch path.
- HavokLib reads FO4 Havok 2014 clips (GPL-3; lead from the framework thread, for actor animations later).
- **Sounds.** Referencing vanilla WWise events needs no Wwise tools and ships no audio (our A7 path). New events need
  Wwise authoring and the CK project; replacing a `.wem` by id changes the sound for every vanilla use (not acceptable).
- **Release licences.** Built .NET tools that include Mutagen are GPL-3 works. CALUMI (LGPL) is best supplied by the
  user (`--door-anim-dll`) or shipped unmodified with its notices, built from CALUMI's own source and not from the Animation IO copy.
  Nexus-only tools are optional user tools at most. Bethesda and Audiokinetic tools are never bundled.

## 4. Prior art and modding communities (agent report 2026-10-19; some pages unread because of a fetch rate limit)

Starfield door and load mods:
- **Customisable Animation Speed** (Nexus SF 2489, verified, https://www.nexusmods.com/starfield/mods/2489) ships loose
  `.agx` graphs (`simpleopenclose_base01.agx`, `specialhybridopenclose01.agx`, `specialopencloseairlock01_load.agx`).
  So a load door's open timing lives in its `*_Load` graph. Editing a shared graph changed every object on it and
  conflicted with other mods; door audio drifted out of sync. The Redux version (17655, verified) had to swap door sound
  files to resync, and its author notes that weapon sounds follow animation events but door sounds do not (supported).
- **INSTANT DOORS** (Nexus SF 2313, verified, https://www.nexusmods.com/starfield/mods/2313): its `StarfieldCustom.ini`
  lines (`fAutoDoorFadeSecs`, `fNormalDoorFadeSecs`, `fNormalFadeSecs`, `fLoadGameFadeSecs`, `fFadeToBlackFadeSeconds`,
  plus the `[Archive]` loose-file switch) **only remove fades**; the author says to skip the `[General]` lines to keep
  fades and the door speed-up still works. **Correction:** an earlier version of this section said an ini setting
  shortens the load-door wait; it does not. The speed-up ships as loose files, likely `.agx` graphs as in 2489 (supported;
  file names unresolved until the archive is opened). A second file adds "loading airlocks like the ones in Cydonia". So
  the engine already does "open, then the trip" for animated load doors. The author calls stuck doors a vanilla bug that a
  quicksave and reload fixes.
- **The Real Elevator for Starfield** (Nexus SF 10904, verified, https://www.nexusmods.com/starfield/mods/10904): copies
  of `ElevatorMasterScript` / `MovingPlatformMasterScript`, trigger volumes and linked-ref keywords; walking up calls the
  car. It broke two faction quests until v2.0.0 was rebuilt to touch no QUEST.
- **Neon Core Disguised Seamless** (10976, verified): fake elevators hide interior-to-interior loads; many rapid trips
  crash, freeze or black-screen, and some saves needed a new game.
- **Seamless Neon** (17340, verified) moves interiors into the exterior worldspace: lower FPS, duplicated effects, and a
  mid-playthrough uninstall can break saves.
- Ship doors (EVA Hatches 17151, Place Doors Yourself 6601, verified): proximity doors and HAB connectivity problems.
- No Starfield mod was found that ports FO4 or Skyrim doors or levels (searched; unresolved, not proof).

Fallout 4 and Skyrim:
- **Faster Transition** (Nexus FO4 73623, verified, https://www.nexusmods.com/fallout4/mods/73623): FO4 load elevators
  move the player through a **transition cell** while the next area loads. Blanking that link falls back to a plain door
  transition. One removed reference broke the quest DN151 ("Troubled Waters").
- **MS Workshop Framework Door Additions** (94208, verified): a close sent during the open animation can wedge a door
  open (the Diamond City gate needs about 20 s before it auto-closes).
- **Breakable Doors** (53552, verified) and other door mods exclude load doors "because they act as portals".
- Skyrim **No Load Door NPC Fade** (SSE 170693, verified): NPCs fading at load doors is vanilla behaviour. A forum answer
  (supported, https://forums.nexusmods.com/topic/11397993-npc-position-using-load-doors) says NPC placement at a door
  comes from the activate animation and the **navmesh door link**, not from the door model.

Total conversions and rules:
- **Tale of Two Wastelands**: users own both games, and install-time builders combine the archives. Versions that shipped
  asset payloads were reportedly removed (supported).
- **Fallout London** (verified, GOG page): needs the user's own FO4 and makes irreversible changes to the install.
- **Fallout: Capital Wasteland** was cancelled. Even extracting voice files from the user's own copy was judged unworkable
  (supported, PCGamesN).
- **Skywind** is approved by Bethesda and redesigns its assets (supported). **Skyblivion** uses only its own team's assets
  and checks for the user's own Oblivion copy (verified, Nexus news 13125).
- Nexus moderators say assets from other Bethesda games need permission (supported, forum). Paid Creations must be
  standalone, all-new and free of generative AI (supported). Whether free Creations have the same rules is unresolved.
- Starfield saves do not support removing mods; changing a plugin's master type is a risk (verified, Nexus article 702).

Lessons for our design:
1. Never edit or ship vanilla `.agx` files. Use our own record copies, as `_XtelLoad` already does.
2. Don't rely on graph events for door sounds; the DOOR record's sounds (A7) are the way.
3. **Never close a door while it is still opening.** FO4SF_AnimatedLoadDoor calls `SetOpen(False)` even when its wait
   timed out mid-open. Fix it to close only once open state is 1 (groundwork, this thread).
4. XTEL plus a `*_Load` graph is the native path; the scripted MoveTo path is the fallback.
5. Touch no quest or quest-linked reference, and classify every FO4 elevator (transition cell, moving platform, or plain
   load door; a blank transition cell is the safe default).
6. Add a soak test: many round trips through one door while watching memory.
7. Carry FO4's navmesh door links onto the new door references, or followers will stall or stand at the hinge.
8. Treat a changed door base under an existing save as save-breaking until tested; keep FormIDs stable.
9. GitHub first, then Nexus, is the release channel (owner, roadmap approved 07:23Z); Creations is not planned. Only the free-Creations rules stay open (J40).

## 5. Player and NPC side

- NPC placement at a door comes from the actor's activate animation and the **navmesh door link** (XNDP on the
  reference: navmesh plus teleport-marker triangle), not from the door model (supported, §4). Converted load doors
  need XNDP pointing at our navmesh, or followers will stall or fade at the wrong side (unresolved for our builds).
- NPCs fading at load doors is vanilla behaviour (Skyrim, verified; Starfield likely). Compare with a vanilla door
  before filing it as our bug.
- Minimal Use (0x08) and Do Not Open in Combat Search (0x20) shape NPC pathing; both carry over bit for bit.
- Scenes and escorts that cross load doors (FO4 escorts into Vault 111 and Sanctuary) must keep dialogue running
  across the door (findings/people-story.md Q4; unresolved).
- The player has no "use door" animation on Starfield's ordinary doors. A walk-through animation would be a separate
  feature (SFSE players such as SAF or OSF), out of scope for phase 2.

**Offline answers (second wave, 2026-10-19, verified from code unless marked):**
- **G28, navmesh door links:** exterior navmesh conversion keeps FO4 door triangles only for rigged opening doors.
  Load doors are dropped (`scripts/actors/navmesh_core64n_convert.py:49-62`), no writer sets `NavigationDoorLink`
  (XNDP), and interiors have no navmesh at all. **NPCs and followers cannot path through our load doors today.** Fix
  path: send load-door refs to the navmesh writer, export FO4's XNDP in Fo4Export, and set it in TerrainOverlays.
  Interiors wait for interior navmesh.
- **D13, FNAM flags:** no DOOR writer copies flags (PluginSpike `Program.cs:94-176`, TerrainOverlays `:223-227`).
  Fo4Export already exports `door_bases[..].record.Flags`. PluginSpike keys door bases by model, so FO4 bases that share
  a model but differ in flags (the `*MinUse` variants) cannot be told apart yet.
- **D17:** automatic and invisible doors are markers and never reach the converter, and a door without an Open
  sequence cannot be rigged. **Gap found and fixed** (aa5173a): a trapdoor whose name says "door" (not "hatch") swung on
  the upright template; under `--rig-load-doors` it now takes the own-rig route (`door_rig.flips`).
- **E22:** pinned Mutagen 0.55.0-alpha.67 has `PlacedObject.Lock`, `TeleportName` and `NavigationDoorLink`, and
  `Door.Flag` NoQuestTarget/NoDirectActivation (reflection). Lock is already written (`ReferenceLinks/Relationships.cs:299`).
- **D14:** in the backlog, 10 double-door bases (61 refs) and 12 trapdoor or hatch bases (49 refs) were counted by name.
  The two-leaf and horizontal-axis own-rig paths are tested for ordinary doors. A two-leaf load-door test is still to add.
- **E23:** enable parents are exported and written. 24 of 350 exterior load doors have one (Institute rotunda 8/8, USS
  Constitution 6/6, ...). Quest aliases are not exported at all.
- **Count reconciliation** (Interiors thread): use 230 for interiors behind Commonwealth doors and 271 for the whole census
  (it adds 41 interiors entered from Diamond City and Goodneighbor).

## 6. The framework of questions

Each question names what answers it: **PC read** (read-only on the PC, small output), **offline** (cloud, repo code),
**in game** (the owner's test window), **source** (a page to read), or **owner** (a decision). ★ marks the ones that
block the next build step.

### A. The engine contract (how "open, then trip" works)
1. **Answered (A1, §1):** a self-contained machine whose open is 0.8x speed minus 20 frames and which closes itself. ★ What does a `*_Load` graph add over `SimpleOpenClose01` (states, events, `AnimSpeed`, an end tag)? *PC read:* pull
   `SimpleOpenClose01`, `_Base01`, `02_Load` and `06_Load` `.agx` from Starfield - Animations.ba2 and diff them as XML.
2. ★ What ends the engine's wait before an XTEL trip: a graph event, the end of the clip, or a timer, and is a long FO4
   clip cut short? *PC read* (Q1), then *in game* G2 with a stopwatch. (INSTANT DOORS' ini is fades only, §4, so no ini
   timer is known; its loose file names are a *PC read* of its archive if wanted.)
3. **Answered (A1, §1):** `Done` when opening or closing ends. Which output events does a door graph send (Opened, Done, Closed), so `PlayAnimationAndWait` or
   `RegisterForAnimationEvent` is safe? *PC read* (Q1); also grep `ScriptObject.psc` for RegisterForAnimationEvent.
4. Do vanilla `*_Load` doors set AnimationGraphComponent DNAM (response file) or ENAM? *PC read:* `SfInspect doorrec`.
5. Do the four vanilla XTELs with No Load Screen animate and then move without a load screen? *PC read:* `SfInspect
   teleports` filtered on flag 2; then *in game*.
6. Is DLSH a loop or a lock sound? *PC read:* count DLSH in doorsounds.tsv (A7 found loop GUIDs only; check), then by ear.

### B. Our scripted doors (exterior <-> interior)
7. ★ Should FO4SF_AnimatedLoadDoor use `OnOpen` instead of polling, or BlockActivation, then SetOpen, then OnOpen, then
   travel? *In game:* both variants on the SDM pair, timing E to arrival. (All the functions exist in Starfield, §1, so
   both variants compile; close only at GetOpenState 1.)
8. ★ Does it refuse the trip on a locked door? OnActivate fires on locked doors. `IsLocked()` exists (§1, verified), so
   *offline:* add the check; *in game* once on a locked pair. Never call `Lock()` without
   `abTraverseLinkedLockables = False` until we know what it traverses.
9. Does `SetOpen(False)` take effect after the player has left the cell (G3)? Fallbacks: close in OnLoad, or on
   `OnPlayerTeleport` (exists, §1). *In game.*
10. The edited script (e11478e) must be recompiled on the PC before any test. *PC read* (compile only, no install).

### C. The outdoor side (step C, after the v6e test; the bugs thread owns the core writer)
11. ★ Should the exterior be one animated DOOR, or the vanilla elevator pattern (a visible animated non-load DOOR plus a
    hidden scripted load door)? *PC read* of one vanilla load elevator's references and links; then *owner* or design
    review with the bugs thread.
12. Do compare-ids show only the door ACTIs replaced? *Offline*, on the staged build.

### D. Door families (counts from the interior backlog)
13. ★ Which FNAM flags do the 373 exterior and the second-hop load-door bases carry (Automatic, Hidden, Minimal Use, No
    To Text)? Copy them bit for bit. *PC read* (the `door_bases[..].record.Flags` export exists).
14. Do double doors (~70 refs) all get their own two-leaf rig, and do trapdoors and hatches (~48) open correctly on a
    horizontal axis? *Offline* (convert with `--rig-load-doors`, count `own` vs failures), then *in game* on one
    MetalTrapdoor01.
15. ★ Which FO4 load elevators set XTEL Transition Interior, and to which cells? Do Starfield XTELs honour it (0 of 964
    use it)? *PC read* of Fo4Export over door XTELs; *in game* one test cell. Safe default: drop the transition cell
    (a plain door trip, as Nexus FO4 73623 does). Transition cells are a live Starfield concept (`GetTransitionCell`,
    `IsRefInTransitionCell`, `IsTeleportAreaLoaded`, §1), so the in-game test is worth one cell.
16. Where does `MakeElevatorFunctional` live, what does `LoadElevatorDoorScript` do, and which quests gate which
    elevators (Fort Hagen MQ106)? *PC read* of the elevator VMADs and the user's FO4 script sources (policy P8).
17. **Answered (§5):** they are markers and never rigged. Automatic and invisible doors (~17) must never wait on an animation. *Offline:* a test that refuses `anim` on them.
18. Do any FO4 door NIFs carry text keys other than `Sound:`, or a behaviour graph? *PC read:* scan door NIFs.
19. How is `IndBgPipe1WayGrateDoor01` one-way (script, lock, or flag)? *PC read* of both references.
20. Do FO4 doors use TNAM random destinations anywhere? Starfield has no such field. *PC read* (count).
21. Vault 111's cog door and exit elevator are activators and an Automatic door, not animated load doors. *Owner:*
    confirm that they stay with the new-game thread.

### E. Locks, quests and saves
22. (Mutagen half answered in §5: all fields exist.) Does Starfield honour lock levels 251 to 254 (Barred, Chained, Requires Terminal, Inaccessible) as FO4 does? *In game*,
    one synthetic door each. Does pinned Mutagen expose `Lock`, `NavigationDoorLink`, `TeleportName` and the
    `NoDirectActivation` flag? *PC read* (reflection, check P3).
23. Which converted door references are quest aliases, script properties or enable-parent children (Fort Hagen
    blockers)? *Offline* cross-reference against FO4 QUST aliases and XESP.
24. ★ Does moving references onto `_XtelLoad` (or ACTI to DOOR outside) break a save that has already loaded them?
    *In game* A/B: save, swap the build, load, use the door. Until tested, treat it as save-breaking.

### F. Sound
25. Does a plugin play vanilla WWise events by GUID without its own bank? *In game*, by ear on one animated door.
26. Do the A7 pairs suit FO4's door types (wood, metal, vault), or does each FO4 SNDR category need a hand-picked vanilla
    pair? *Offline* table (FO4 SNAM/ANAM/BNAM against A7), then by ear on about 10 door types.
27. Are new sounds ever needed, and what does the Wwise licence allow for a free mod? *Source, partly answered:*
    Audiokinetic's indie post says a Non-commercial key covers "totally free games (no monetisation at all)" with no
    asset limit; ads, sponsorship or promotional ties make it commercial; mods are not named, and the pricing page and
    software EULA are unread (verified, blog.audiokinetic.com). CDPR's REDkit gets modders keys via Audiokinetic School,
    renewed every 3 months (another game). Borrowing vanilla events still avoids the question. *Owner.*

### G. NPCs and followers
28. **Answered (§5): no**, a gap with a fix path. ★ Do our converted load doors get navmesh door links (XNDP) to our navmesh? *Offline* dump of output NAVM door
    links matched against FO4's.
29. Do followers use our `_XtelLoad` and scripted doors, and is their fade the same as vanilla? *In game* with a vanilla
    follower at Fort Hagen and at one exterior pair. Precedent: a Skyrim thread (verified, forum 13474629) fixed
    followers on linked doors only by putting both doors in one cell; a Starfield thread (13509472) has an unsolved
    one-way door with an endless load screen, with leads on one-sided navmesh, arrival markers and instanced interiors.
    New check: none of our target cells is flagged as an instanced interior unless meant (*offline* dump).
30. Do escort scenes keep running across our doors (FO4 escorts into Vault 111 and Sanctuary)? *In game* (people track).

### H. Tools and pipeline
31. Can PyNifly plus Animation IO serve as an independent check of `native_door`'s keys for one two-leaf door?
    *Offline or PC*, one manual round trip, compared within 1e-3.
32. What do the rig `PrecisionSet` and the `.af` header flags do, and do our rigs match vanilla door rigs? *PC read:*
    tabulate them over the vanilla door rigs.
33. Can CALUMI clips cover every FO4 door family without the compression it lacks? *Offline:* convert all door models
    and compare clip sizes with vanilla.
34. Build CALUMI `b0f3b5c` from source and compare it byte for byte with the pinned DLL. *PC.*
35. Can we author our own `.agx` (new file names only) for doors with more than open and close (cog doors, multi-stage)?
    *PC read* of vanilla graphs (Q1), then one test.

### I. Stability and acceptance
36. ★ Do many round trips through one door leak memory or crash (as one Starfield seamless mod did)? *In game:* a
    50-trip soak under the crash watcher.
37. G1 to G3 pass criteria (unchanged): a screenshot of the open leaf before each load screen, the bridge log's
    arrival line, and the door shut on return.

### J. Release and policy (owner)
38. Built .NET tools are GPL-3 through Mutagen: release source only, or binaries under GPL-3? *Owner*, recorded in
    decisions.md.
40. **Channel answered by lesson 9** (GitHub, then Nexus). Still open, and only if Creations is ever reconsidered: do
    free Creations carry the paid ones' rules (no generative AI, standalone, all-new)? PCGamesN (secondary) reports
    those rules without saying; the official page (help.bethesda.net a_id 51731) refuses fetches, so a browser read is
    needed. For the chosen channels: Nexus forbids uploading copyrighted game files (verified, submission guidelines)
    and moderators say other Bethesda games' assets need permission (supported, forum 9720278); Tale of Two Wastelands
    builds everything from the player's own installed games and claims no Bethesda permission (verified, its FAQ).
    *Source* (browser read), no owner decision needed now.installed games and claims no Bethesda permission (verified, its FAQ). *Owner.*
