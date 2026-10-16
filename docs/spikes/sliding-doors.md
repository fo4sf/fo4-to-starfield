# Sliding, lifting and trapdoor FO4 doors (2026-10-16, Claude; offline)

**Status:** implemented offline (branch `claude/slide-doors`); **not run in game**. Owner playtest rows 1 and 6
(docs/owner/playtest-issues.md): the Vault 111 doors do not open, the exit elevator cannot move.

## Answer in short

- **Which vanilla doors slide, lift or flip** (verified, survey below; recounted in the PR #242 review): of 123 vanilla
  door rigs, 51 move a bone sideways or diagonally by 0.25 m or more, 12 lift one (5 do both), 59 only rotate, 4 move
  no bone that far (nor turn one 20°), 2 have no `open.af`. All of them use the same graphs as hinged doors
  (`SimpleOpenClose01.agx`, and `*_Load` variants for load doors). The graph only sequences Open / Close; **the motion
  is each door's own `skeleton.rig` + `animations\open.af` / `close.af`**.
- **Can a vanilla rig drive the FO4 parts, as the Akila template drives hinged leaves?** For none of the 10 doors
  without changing what FO4 does: no vanilla rig splits two panels up and down, and none drops a panel straight down
  (the FO4 vault doors' lower panel drops 0.98 m; the nearest, `LC017NASA_GravDrivePrototype_Door01`, moves two panels
  0.52 m down *and* 0.52 m sideways), and the vanilla sliding pairs travel 1.00 / 1.50 / 4.00 m where the FO4 panels travel 0.64-0.91 m (9-56 % too far).
  Template table below.
- **What this branch does instead:** these doors get **their own rig and clips built from FO4's own keys**, the path
  the multi-part doors already take (PR #79: `convert_static.convert_multipart_door`, CALUMI writer), on the same
  vanilla graph `SimpleOpenClose01.agx`. Each FO4 node becomes a rig bone of the same name, so node names and the rig
  match by construction, and every panel moves exactly as in FO4. All 10 door bases map cleanly this way.
- **Elevator:** not in reach as a whole. Starfield's own elevators are a scripted platform helper or a
  `TranslateToRef` platform plus linked buttons and doors (records only, vanilla scripts). The ride up the shaft looks
  buildable after two pieces of converter work. The exit to the surface needs the interior-to-exterior door link,
  which is still open. Section "Elevator" below.

## The 10 door bases (all now rigged when `--door-anim-dll` is given)

Refs = placed references in the 16 pinned cells (`integ_1011` exports): 106 in all.

| FO4 model (DOOR records) | Refs | What FO4's `Open` moves (end offset) | Nearest vanilla template | Why the template does not fit | This branch |
|---|---:|---|---|---|---|
| `V111Door01` (V111Door01b 0244EE) | 17 (Vault111Cryo) | `Door Upper` +2.116 m up, `Object042` (lower, handles) -0.976 m down, 2 floor slats 90° about x; 1.3 s | `StsGenIntRmSmWallMid_DoorD01` (4 telescoping panels up +0.62 / 1.22 / 1.82 / 2.32 m, 3 s) | no bone moves down; 4 panels, not 2 | own rig: 10 bones, 6 tracks, 6 keyframed bodies |
| `V111DoorSpecial01` (04D9C1) | 3 (Vault111Cryo) | same as V111Door01 | same | same | same |
| `VltDoorRes01A` (0AC5E9, 13B859 NoName) | 32 (Vault114, 75, 81, 95) | upper +2.116 m, lower -0.976 m; 2 switches (end where they start); override-box light glow (shader float) | same | same | own rig: 7 bones, 4 tracks, 4 bodies; the 2 shader tracks listed in `ignored_tracks` |
| `VltDoorRes01B` (0AC5EA) | 35 | same | same | same | same |
| `VltDoorRes01C` (0AC5EB) | 5 | same | same | same | same |
| `VltElevatorDoor02` (183356, Load 13FECD) | 4 (Vault75, 81, 95) | `Door01L` / `Door02R` ±0.80 m along x; 1.0 s | `ElvGen_ExSm_DoorOuter01` / `DoorInner01` (two panels ±1.00 m along x, 1.0 s) | 25 % too far | own rig: 3 bones, 2 tracks, 2 bodies |
| `VltElevatorDoorCarInt02` (183355, Load 13FECB) | 3 | ±0.914 m along x; 1.0 s | same | 9 % too far (closest fit of all) | same |
| `UtilMetalElevatorIn01` (0A2782, Load 09C01F) | 2 (FortHagen01, 02) | `Door` / `Door@#0` ±0.68 m along x; 1.33 s | same | 47 % too far | same |
| `UtilMetalElevatorOut01` (0A2783, Load 046966) | 4 (FortHagen01, 02, ParsonsState01) | ±0.64 m along x; one panel node is named `REF_ATTACH_NODE` | same | 56 % too far | same (the bone keeps the name; 29 vanilla rigs have a `REF_ATTACH_NODE` bone, 28 of them under a moving bone, but none keys it: an animated `REF_ATTACH_NODE` is untested, see the risks) |
| `UtilMetalElevatorHatch01` (02281C) | 1 (FortHagen01) | `MetalTrapdoor01` flips 100.5° about -y (a hatch 2.9 m up) | `GenHatch_Door01` (`Hatch_Door` 90° about -y, plus piston and handle bones) | 10.5° short; its own extra animated parts | own rig: 2 bones, 1 track, 1 body |

Named in the task but **not** door bases: the Vault 111 cog door `VltGearDoor01` (an FO4 Activator, 0330C2) and the
exit elevator `VltElevator` (Activator 0244EF). Both are covered further down.

## Vanilla survey (method)

All read-only, from the user's install; files extracted only to `C:\Modding\scratch\slide_doors\vanilla` (outside the
repo).
- `SfInspect doortsv` (new): one row per DOOR. 339 records, 310 with an AnimationGraphComponent, 18 graphs:
  `SimpleOpenClose01.agx` 215, `SimpleOpenClose07_Load` 18, `06_Load` 17, `05_Load` 13, `HybridOpenClose01` 9,
  `SpecialHybridOpenClose01` 8, others 1-8.
- 123 distinct rig + clip folders (124 BNAM / CNAM pairs; the 124th, `genericbehaviors\skeleton.rig`, has no clip
  folder). Each `skeleton.rig` and every `.af` in the folder was read back with
  CALUMI (`LoadSFBGSSkeletonRigFromFileC`, `LoadAnimationSceneFromSFBGSFormatC`; per bone the rotation and translation
  keys). The end offset of each `open.af` track was put in model space with the parent bone's global bind rotation
  (clip keys are offsets from the bind: research-log 2026-10-12).
- Classes (end offset of `open.af`, thresholds 0.25 m / 20°; corrected after the PR #242 review, which recounted
  `vanilla_survey.json`: the first count left diagonal moves out): 51 folders have a bone that
  moves sideways or diagonally, 12 a lifting bone (5 both), 59 rotate only, 4 move no bone past the thresholds, 2 have
  no `open.af` (state graphs `HybridOpenClose01` / `StateOpenClose01_Load`).
  In 5 of the 123 rigs a bone ends 0.25 m or more *down*: release helpers of the two docking doors (-0.26 m), the
  `Latch_Release02_Point` latch of `ShpGenIntPerSmWallMid_ExLg_Door01/02` (-0.32 m, with +0.26 m sideways), and the
  panels `Door01` / `Door04` of `LC017NASA_GravDrivePrototype_Door01` (0.52 m down and 0.52 m sideways, diagonally).
  No rig drops a panel straight down or splits two panels up and down as the FO4 vault doors do.
- Sliding and lifting doors share the graph with hinged ones: `ElvGen_ExSm_DoorInner01` (non-load records),
  `StsGenIntRmSmWallMid_DoorD01`, `HangarDoor_4x4` and the ship doors all use `SimpleOpenClose01.agx`; their load
  variants use `*_Load` graphs (elevator: `SimpleOpenClose03_Load`).
- Collision of multi-panel vanilla doors (9 NIFs: ElvGen ExSm inner / outer / full, HangarDoor_4x4, DoorD01 and
  D01s, GenHatch_Door01 and GenHatch_LadderDoor01, NA_SecureShelving): **one** `bhkPhysicsSystem` with one body per panel. Our own-rig doors
  write one system per moving part. #79 already listed that as its main in-game risk.

Template candidates read back (`open.af`, model space):

| Vanilla rig (doors) | Frames (30 fps) | Moving bones and end offset |
|---|---:|---|
| `elvgen_exsm_doorinner01` (8) / `doorouter01` (3) | 31 | `InnerDoorLeft01` / `InnerDoorRight01` -1.00 / +1.00 m x (outer: `OuterDoorLeft01` / `OuterDoorRight01` +1.00 / -1.00 m) |
| `elvgen_exlg_doorinner01` (7) / `doorouter01` (2) | 31 | the same pairs, 1.50 m each way along x |
| `secure_shelving` (1) | 26 | `doorR_helper` / `doorL_helper` -1.00 / +1.00 m y |
| `hangardoor_4x4` (1) | 56 | `HangarDoor_Left` / `HangarDoor_Right` -4.00 / +4.00 m y |
| `stsgenintrmsmwallmid_doord01` (3) | 91 | 4 panels +0.615 / +1.22 / +1.82 / +2.32 m z |
| `shpgenintpersmwallmid_exsm_door01` (9) | 81 | `DoorLower01` +0.92 m z, braces and handles rotate |
| `genhatch_door01` (3) | 51 | `Hatch_Door` 90° about -y, `Piston_Base` 90.8°, `Handle` 90° about -z, `LockSlide01` +0.25 m y |

The template route would also need our NIF to repeat each template rig's bone chain and bind pivots, with the FO4
panels hung under the moving bones, as the hinged path does for the Akila rig. At these travel differences a panel
would end 0.09-0.36 m inside the wall, or, for the vault doors, the lower panel would stay shut.

## What changed in code

- `pipeline.Converter.convert_nif`: a door-named model matching `NOT_HINGED_RE` (vault|elevator|garage|gate|hatch|slid)
  that is not a load door and has an FO4 `Open` sequence goes to `convert_multipart_door` when the CALUMI library is
  given (`convert_batch.py --door-anim-dll`). Without the library, or if the build fails (`door_error`: "own rig: ..."),
  it stays passable as before (`door_not_opening`). Hinged and load doors keep their paths.
- `door_motion.inspect`: a controlled block of a known non-transform kind (shader float / color, alpha test,
  visibility, material color or particle emitter controller on a float / bool / point3 interpolator, or such an
  interpolator with no controller type) is listed in `ignored_targets` and is no longer a "binding" issue. These blocks
  stopped `VltDoorRes01A/B/C` (`BSLightingShaderPropertyFloatController` on the override-box shapes `...:0` / `...:1`).
  `door_rig.plan` carries them as `ignored_tracks`; the manifest's door entry names them. Any other block (a B-spline or
  unknown transform interpolator, an unknown controller type) stays a track, so the rig is refused rather than built
  with that part frozen (Codex review of #242). Over every FO4 mesh with an `Open` sequence (1,380 Open / Close blocks)
  the verdict is the same as before this narrowing.
- Manifest door entry (own-rig doors): `open_motion`, one row per animated bone: `travel_m` (end offset, model space,
  the parents' bind rotation and scale applied), `rotation_deg`, `axis`. Example for V111Door01: `Door Upper`
  [0, 0, 2.1164], `Object042` [0, 0, -0.9762], floor slats 90° about ±x.
- Rest pose (this route only): a door whose `Open` does not start, or whose `Close` does not end, at its bind pose is
  refused and stays passable (`door_rig.rest_pose_issue`). Of the 23 FO4 models the route takes, 21 pass (the 10 above
  exactly); `BHMarketGateDoor01` (bind = Open's end, 170°) and `DExtMainGateDoor01` (Close ends with `ArmTop` 43° open)
  are refused. Both are outside the 16 cells.
- PluginSpike: a placed reference of an animated (non-load) DOOR base gets FO4's "open by default" (`ONAM`); FO4 lock
  data is counted per cell and not written (its keys and terminals are not in the build). A load reference whose base
  is an own-rig door (manifest `rig: native`) gets no XTEL and is listed as a teleport issue.
- `SfInspect doortsv` and `SfInspect scripted <ScriptName>` (read-only research commands).
- Tests: `tests/test_sliding_doors.py` (23, synthetic fixtures), `dotnet/PluginSpike.Tests` (open state and locks end to
  end through PluginSpike's entry point, the own-rig XTEL guard).

## Offline evidence (2026-10-16)

- **Unchanged without the library (verified):** the 57 door models of the 16 cells were converted with origin/main and
  with this branch. Without `--door-anim-dll` the results are byte-identical: 57 manifest entries, 301 files.
- **With the library (verified):** 20 entries differ. The 10 doors above are rigged (`door_not_opening` gone). The 10
  earlier multi-part doors only gain `open_motion`; their NIF, rig and clips are byte-identical.
- **Clips say what FO4 says (verified with the same library, CALUMI read-back of our files):** Open / Close end
  offsets per bone are V111 and VltDoorRes upper +2.116 / lower -0.976 m z, VltElevatorDoor02 ±0.800 m x, CarInt02
  ±0.914 m, UtilMetalElevatorIn01 -0.676 / +0.682 m, Out01 -0.635 / +0.645 m, the hatch 100.5° about -y, the V111
  slats 90° about ±x. Frames: 30 fps on FO4's own durations (31-55).
- **Oracles (verified):** `scripts/oracles/door_panels.py --dll` before (main + library): 15 multi-part doors, 40 of 40
  parts move; after: 24 doors, 72 of 72 parts have an Open and a Close track and a moving body (the hatch has one part
  and is not audited). `door_bodies.py`: 0 errors; rigged models 29 to 39, moving bodies 49 to 82.
- **Plugin (verified):** PluginSpike on the pinned `integ_1011` inputs writes a control `FO4Port.esm` byte-identical to
  the pinned one. With the 10 entries swapped in (`overlay_manifest.overlay`), both builds hold 54,271 records. 10 STAT
  are replaced by 10 DOOR (`ANAM SimpleOpenClose01.agx`, `BNAM` / `CNAM` our rig and clips, OBND from the bounds), and
  106 REFR differ only in `NAME` (the base). Positions do not change (origin offset 0). Teleports are the same (2
  linked, 28 destinations not in the build).
- **Open by default (verified, after the review fixes):** PluginSpike with the open-state change on the same pinned
  inputs: against the pinned `FO4Port.esm`, 54,271 records in both, 47 REFR differ, each only by an added `ONAM` (the 47
  FO4-open hinged doors). With the 10 entries swapped in: 68 REFR gain `ONAM` (47 + the 21 vault / elevator refs FO4
  shows open); the cells report 13 (control) / 23 (overlay) refs FO4 locks, not written. `teleports.json` unchanged.

## Limits and in-game risks (unresolved until a game window)

- Our own rig and clips have not played in game yet. Neither have #79's multi-part doors (they need the same overlay
  build). Open: whether Starfield loads a rig and clips from our `Main.ba2`, and whether one physics system per
  moving part works (vanilla shares one per door).
- The elevator load doors (`LoadElevatorDoor*`) share their model's DOOR record, so they are rigged too, with the
  non-load graph. Vanilla gives load variants their own record with `SimpleOpenClose03_Load`. None of their destinations
  is in this build, so no teleport changes; a separate load-door record is follow-up work. Until then PluginSpike
  refuses an XTEL on an own-rig door and lists it, so a later build that places a destination does not link it unseen.
- `UtilMetalElevatorOut01` keys a bone named `REF_ATTACH_NODE` (4 refs). Vanilla rigs never key that bone (29 have it,
  none animates it); whether the engine treats an animated `REF_ATTACH_NODE` normally is unknown.
- FO4 locks are not ported (13 refs in the pinned cells, 23 with these doors; Vault 111: levels 253 / 254 on
  `V111DoorSpecial01` 0A6C08 and `V111Door01b` 0A1693). Doors FO4 opens from a terminal or with a key open freely here.
- Not ported: FO4's text-key sound events (DOOR sounds stay unset) and the vault doors' override-box light glow.
  Handles and switches get small keyframed boxes of their own, as #79's knobs do.

## In-game test (not run; needs an owner window)

Build the overlay (docs/spikes/WP-doors-research.md "Multi-part doors" recipe, with `--door-anim-dll`; it now swaps
these 10 models plus #79's 10). Then:
1. Vault 111 (owner row 1: cell 020011F3, pos -3.83 -7.44 0.01, door `V111Door01b` 001977): E opens both panels (upper
   up into the frame, lower into the floor), the player walks through, E closes, and the closed door blocks.
2. A Vault 81 / 95 `VltDoorRes01A` room door: the same check.
3. A Vault 75 `ElevatorDoorOutVault` pair: both panels slide apart.
4. Open by default: the 8 Vault 111 doorways FO4 shows open (V111Door01b 0ADC9F, 0ADC9E, 0AD5E9, 0AD5F1, 0AD633,
   0AD606, 0AD64E and V111DoorSpecial01 0AB2A3) load open and passable; E closes one. The FO4-locked V111DoorSpecial01
   0A6C08 opens with E (lock not ported).
5. The `UtilMetalElevatorOut01` pair in FortHagen01 (the `REF_ATTACH_NODE` panel) slides like the other one.
6. Controls: one Akila-template door (`BldWoodPDoor01`) and one #79 double door (`PaintedWoodDoorDouble01`, Parsons
   06CF29).

## Elevator (owner row 6): what it needs

**FO4 (verified, `Fallout4 - Meshes.ba2` + the Vault111Cryo export):**
- `VltElevator` is an Activator (0244EF, persistent ref 0244EB): one NIF, 16 shapes (12 skinned to bones such as
  `b_Platform`, `b_Gate01`, `b_Hatch Left`), sequences `stage1`..`stage8`. `stage2` (23.8 s) lowers the platform
  21.6 m and opens the gate; `stage3` (9.9 s) raises it 21.6 m; `stage4` (11.7 s) raises it 26.0 m and opens the
  roof hatches ±3.66 m; `stage8` (18.7 s) lowers it 59.1 m with `FadeToBlack` / `ToggleCollision` events. The quest
  script (not in our export) plays them.
- `vaultExitElevatorDown` (020C39, ref 020C3A) is a trigger box (primitive 426 x 1096 x 394 units), not a button. The
  ride ends with teleports to the Commonwealth (248AAD -> 248AAE and 01F180 -> 0998E3, exterior cell 018AA2). This
  build places neither source (`teleports.json` "UnplacedSources").

**Starfield (verified, Starfield.esm via `SfInspect scripted`, scripts from `ContentResources.zip`):** three vanilla
mechanisms.
1. `ElevatorMasterScript` (2 refs, e.g. `VecteraMineElevator` 0175B9, base `DefaultElevatorControl` 017597): linked
   refs by keyword (`Elevator_PlatformHelper`, `_InteriorButton`, `_TopButton` / `_BottomButton`, `_InteriorDoor` /
   `_TopDoor` / `_BottomDoor`, `_DisableAfterLoad`, `_SoundMarker01`). The helper `PlatformHelperFree01` (ACTI 0162EC,
   flag UsedasPlatform, graph `HelperElevatorMoveHelper.agx` with its own rig and clips) is driven by the graph
   variables `Position` / `Speed` and `PlayAnimationAndWait("Play01", "done")`; parts ride it by AttachRef.
2. `MovingPlatformMasterScript` (22 refs, base `MovingPlatform_AnchorMarker` 2A4AFF): a translation helper
   (`RotationHelperFree01` 02F0F3) moved by `TranslateToRef(nextNodeMarker, TravelSpeed)` between linked
   `MovingPlatform_FloorNodeMarker` refs (29344A). The interior buttons (`Gen_Switch_02_Inverted`) and the interior
   door ride the helper by AttachRef (WarehouseMovingPlatforms: 2A58B9 and 2A58BB attach to 2A58B8). No animation file
   sets the distance.
3. Load elevators (`LoadElevatorManagerScript`, `LoadElevatorFloorScript`; teleport doors such as
   `ElvGen_ExSm_DoorFull01_Load`).

**In reach?** Not as a whole.
- The ride inside the cell, via option 2, is a **supported hypothesis**: it needs only records. Vanilla scripts,
  keywords and markers come from Starfield.esm, and Mutagen 0.55 `PlacedObject` has `LinkedReferences`, `AttachRef` and
  `VirtualMachineAdapter` (reflection). The vanilla refs carry the script on the placed ref too. Missing pieces:
  (a) the platform's 12 skinned shapes taken as rigid parts per bone (today they are frozen in bind pose); (b)
  PluginSpike writing linked refs, attach refs and the anchor's VMAD; (c) floor markers at FO4's stage heights; (d) a
  button instead of FO4's trigger box.
- The exit to the surface needs the interior (FO4Port.esm) to exterior (FO4TerrainCore.esm) link. That door gate is
  still open (journal 2026-10-15/16: add-on overrides refuted; next is a native DOOR + XTEL inside FO4TerrainCore.esm).
- Suggested order: door gate, then the in-cell ride (option 2 with a rigid platform), then a teleport at the top.

## The cog door `VltGearDoor01` (owner row 6)

FO4 Activator 0330C2 (ref 0330C3): 48 shapes (5 skinned), sequences `Stage0`..`Stage3`. `Stage2` (43.3 s) rolls the
cog back and aside (-1.77 / -5.55 m), slides the catwalk sections out 2.0-9.3 m and fires sound events. It is played by the quest after
the console `V111GearDoorConsole01`. It is not a DOOR, so Open / Close graphs do not apply. It needs an activator graph
that plays named clips on `PlayAnimation` (vanilla graphs for that are not surveyed yet) plus a trigger. It stays a
solid static (27 FO4 bodies), so the vault exit stays shut. Not in this item.
