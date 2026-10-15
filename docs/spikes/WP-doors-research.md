# Doors: how they animate in each game (research, 2026-10-08)

**Status: working** (2026-10-08). Hinged FO4 doors open and close in game. Turn it on with `convert_batch.py --starfield-data <Starfield Data>`, which needs the vanilla door body as a donor. Without it, doors stay static and walk-through.

## Fallout 4
Door NIFs (`meshes\SetDressing\Doors\*`, 28 sampled) carry their own keyframe animation:
`NiControllerManager` + `NiControllerSequence` ("Open" / "Close") + `NiMultiTargetTransformController` +
`NiTransformInterpolator`/`NiTransformData`, plus `NiTextKeyExtraData`. The moving part is a named node.

## Starfield
Door NIFs (520 in `Starfield - Meshes01.ba2`, 60 sampled) contain **no controller blocks**. They contain named nodes
(e.g. `AK_Door_Anim_02_Root`, `Hinge01_Point`, `REF_ATTACH_NODE`, `LookAtNode`) and `NiStringExtraData "sgoKeep"` tags on nodes
that must survive optimisation. The animation is attached by the **DOOR record** through an `AnimationGraphComponent`:

| Field | Example (`AK_Ext_Bld_WallA_DoorA_01_Alt02`, 0AA24A) |
|---|---|
| ANAM (graph) | `AnimTextData\Tables\Graphs\SimpleOpenClose01.agx` (shared by many doors) |
| BNAM (skeleton) | `architecture\city\akila\animated\doors\ak_ext_bld_walla_doora_01\characterassets\skeleton.rig` |
| CNAM (animations) | `architecture\city\akila\animated\doors\ak_ext_bld_walla_doora_01\animations` |

## Plan to make FO4 doors open
1. Pick a vanilla Starfield hinged door and a vanilla sliding door as templates.
2. Rebuild each FO4 door NIF as root -> `<template root node>` -> `Hinge01_Point` (placed at the FO4 animated node's pivot) ->
   geometry in the pivot's local space; tag nodes with `sgoKeep`.
3. Write a `DOOR` record with the template's `AnimationGraphComponent` (ANAM/BNAM/CNAM), open/close sounds and keywords.
4. Risk: the template's `.rig` / `.af` may encode the template's own hinge *position*, not only a rotation. Test in game; if the
   door jumps, the `.af`/`.rig` formats need decoding (no public spec known) or per-size template doors must be chosen.

## Attempt 1 (2026-10-08): rigged FO4 doors on the Akila template

Implemented:
- `nif.door_hinge` reads the node the FO4 `Open` sequence animates first (24 of the doors in our 8 cells are hinged).
- `convert_static.convert_door` and `sfnif.build_door_nif` rebuild the door as root > `AK_Door_Anim_02_Root` >
  `Hinge01_Point` (at the rig's hinge position, -0.823 / 1.698 / 0) > leaf geometry re-centred on the FO4 pivot, plus
  `REF_ATTACH_NODE` and `LookAtNode` (sgoKeep tags), a box body on the leaf, and the static frame under a `Frame` node.
- The plugin writes a `DOOR` record with the template's `AnimationGraphComponent`, real `OBND`, `SoundLevel` (DEVT) and
  `FacingAxisOverride` (trailing ANAM). The reference is shifted by `origin_offset` (door-local, rotated) so the door stays in
  its frame.

Verified in game (Hotel Rexford door 10AD60, `C:\Modding\research\s1\doortest.ps1`):
- The door sits exactly in its frame and shows **DOOR / Open (E)** ([screenshot](../media/door-rigged-prompt.jpg)).
- E toggles the state to Close and back, and the leaf body blocks the player.
- **The leaf never swings.**

What did not fix the swing: a `door` node (the rig's bone 2, child of the hinge), geometry directly on the hinge,
vanilla-like node order, `BSXFlags` 0xA, and record bounds, sound level and facing axis.

Clues:
- `skeleton.rig` is a plain bone table: 96-byte records (rotation, translation, parent index, name offset); bones are
  `AK_Door_Anim_02_Root`(-1) > `Hinge01_Point`(0) > `door`(1) > `REF_ATTACH_NODE`, `LookAtNode`, `C_..._Static_02`(2).
- FO4's rest pose for `BldWoodPDoor01` is **open**: its hinge node is rotated about 97 degrees, and the static conversion shows
  the leaf open ([screenshot](../media/door-static-restpose.jpg)). Every rigged build showed it **closed** at rest. So the
  graph probably does pose `Hinge01_Point` on load, and only the open transition does not show up.
- In the first build (`LookAtNode` directly under the hinge) the activation marker did swing aside when opened.
- With the vanilla door mesh on our record, or the vanilla DOOR 0AA24A placed in our cell, no prompt could be aimed at with
  scripted input. That test is still open.

Next: place vanilla DOOR 0AA24A somewhere easy to aim at, to confirm a vanilla door animates in our cell (lighting
template, cell flags). Then compare its node poses (`sgoKeep` nodes, open.af) with ours. Decoding `.af` is the fallback.
## Attempt 2 (2026-10-08)

- **A vanilla door animates in our cells.** With the vanilla DOOR `0AA24A` placed at the Rexford door spot
  (`FO4PORT_DOOR_BASE=0AA24A`, a PluginSpike test hook), E swings its leaf ([screenshot](../media/door-vanilla-swings.jpg)).
  So the cell, lighting and graph loading are fine, and the difference is in our NIF or our DOOR record.
- **Collision body.** Our leaf body was cloned from a static box. Diffing it against the vanilla leaf body (same 6,168-byte
  box layout) leaves only a few non-geometry words: 240 (2 vs 1, likely motion type), 232 and 264 (filter / flags), 448,
  456 and 472, and the mass block at 1064-1095. `sfcollision.keyframed()` copies those words from a donor (read from the
  user's install with `physics_blob_from_nif`, so no game data enters the repo). With a keyframed leaf the doorway became
  passable and the leaf rested in FO4's rest pose (swung about 97 degrees). I could not aim at it with scripted input to
  confirm a swing.
- **Record.** Vanilla records also carry `FLLD` (on the model), keywords, `NTRM` and open/close sounds. Not yet tested
  in isolation: aiming at a vanilla NIF placed with our record failed (the teleport landed inside a stall wall).

Next:
1. Build a dedicated door test cell: a floor, one door, the player spawned 1.5 m in front of it facing it. That removes
   the aiming problem.
2. Then test separately: vanilla NIF + our record, our NIF + the vanilla record (via an ESM copy), and the keyframed leaf.
3. Put the leaf in FO4's *closed* pose: the hinge rotation at the end of the FO4 `Close` sequence (NiTransformData), not
   its rest pose.

## Attempt 3 (2026-10-08): it works

A one-door test cell (`FO4PORT_DOORTEST=<door editor id>` in PluginSpike) holds a vanilla 8x8 m platform, the converted door,
vanilla door 0AA24A 3 m to the side, and a COC marker. With it, scripted aiming is no longer a problem.

**The fix was the keyframed leaf body** (`sfcollision.keyframed`). A body cloned from a static prop pins its node, so the
animation could not move the leaf.
- Test cell: the leaf swings open on E ([screenshot](../media/door-testcell-swing.jpg)).
- Hotel Rexford: the door is closed at rest, swings into the bathroom on E, and the player walks through
  ([screenshot](../media/door-rexford-opens.jpg)).

Known limits:
- The swing angle, direction and speed come from the Akila template, not from the FO4 door.
- The static frame part (`Frame` node) has no collision.
- Open/close sounds are not set.
- Sliding vault doors and elevators are excluded (`NOT_HINGED_RE`). They need a sliding template.
- Only the FIRST node the FO4 `Open` sequence moves rides the template hinge; a second leaf, a shutter's other panel or
  the other panels of a sliding set stay closed under `Frame`. Addressed offline on 2026-10-12 (in-game test pending),
  see "Multi-part doors" below.
## Sliding doors (2026-10-08, offline research)

**Which vanilla graph do sliding doors use?** `SfInspect graphs` groups every Starfield `DOOR` by its
`AnimationGraphComponent`. 215 doors use `SimpleOpenClose01.agx`. That includes the hinged Akila door
*and* the sliding ship interior doors (`ShpGenIntPerSmWallMid_ExSm_Door01`, rig `ships\gen\interiors\animated\doors\...`).
The graph only sequences Open/Close; the motion comes from each door's own `skeleton.rig` + `animations\*.af`. So a sliding
FO4 door can be rigged exactly like the hinged ones: hang each FO4 moving part under the vanilla template node that moves the
same way, and reuse the template's ANAM/BNAM/CNAM.

**What the 8 passable FO4 doors do** (their FO4 `Open` sequence, end-pose keys, metres):

| FO4 model | moving nodes | motion |
|---|---|---|
| `VltDoorRes01A/B/C` (vault rooms) | `VaultDoorUpper`, `VaultDoorLower` (+ switches rotate) | upper +2.12 m up, lower -0.98 m down |
| `VltElevatorDoor02` | `Door01L`, `Door02R` | -0.80 / +0.80 m sideways |
| `VltElevatorDoorCarInt02` | `Door01L001`, `Door02R` | +0.91 / -0.91 m sideways |
| `UtilMetalElevatorOut01` | `Door` | rotation keys: actually hinged, try the hinged path |

**Template candidates (vanilla):**
- horizontal split: `ElvGen_ExSm_DoorFull01` (elevator, `SimpleOpenClose03_Load`) and `GenIntRmSmWallMid_DoorA00*`
  (generic interior, separate `panel01` / `panel02` NIFs).
- vertical split: Starfield ship interior doors (`ShpGenIntPerSmWallMid_*_Door01`), still to check which split vertically.

**Blocker:** the motion of each template node (direction, distance) is in the `.af` files, which aren't decoded. Either decode
`.af` (the FO4 side is already known exactly), or watch each template door open in game once (`FO4PORT_DOORTEST`-style test
cell) and read which node moves where. Distances will be the template's, not FO4's; a template whose panels open less than
the FO4 door would leave the doorway partly blocked, so measure the clear opening in game before accepting it.
Until then these doors stay passable and are listed as `door_not_opening` in the manifest.

**`.af` first look (Akila `open.af`, 218 bytes; `close.af` same size):** float 1.0 at 0x08; at 0x28 u16s 5, 6, 31, 2
(6 = bones in the rig, 31 = frames); at 0x4E-0x5D a 16-entry keyframe-time table (frames 0,1,2,3,5,7,9,12,19,22,24,26,
27,28,29,30); 3-byte packed values from 0x60; from 0x90 one u32 per key whose low u16 runs smoothly
(0xC100, 0xC07F ... 0xC042, 0xC141, 0xC140). `close.af` has the same run reversed. It looks like a single quantized
rotation channel on `Hinge01_Point` (the hinge swing), the other channels constant. Sizes: elevator `open.af` is 848
bytes (more moving bones). Not decoded further. Watching each template open in game is cheaper and gives the clear
opening directly; decode only if many templates are needed. `.afx` is XML: `<tag>Open</tag><filename>Open.af</filename>`.

### Follow-up byte comparison (local Starfield archive; 2026-10-09)

Read paired `open.af` / `close.af` entries directly from `Starfield - Animations.ba2` with the repository BA2 reader; no game files were copied to the repo. These observations invalidate treating the Akila size/layout as a general record template:

| Door family | Open / close bytes | u16 values at 0x28 (open) |
|---|---:|---|
| Akila exterior hinged `ak_ext_bld_walla_doora_01` | 218 / 218 | 5, 6, 31, 2 |
| Generic interior `genintrmsmwallmid_doora00a` | 1140 / 952 | 5, 21, 61, 2 |
| Ship interior `shpgenintpersmwallmid_exsm_door01` | 882 / 874 | 5, 24, 81, 2 |
| Ship large interior `shpgenintpersmwallmid_exlg_door01` | 2580 / 2512 | 5, 49, 91, 2 |

All four `.afx` companions identify the `Open` tag and filename only; they do not expose track mappings. Open and Close lengths can differ within one rig, so parse each file's structure and bounds rather than assume paired files are equal-sized. Claude's subsequent name-table cross-check identifies the second u16 at 0x28 as the rig bone count in all four families (see below); frame-rate interpretation and the apparent Akila rotation channel remain unverified. Next: map channels to bones and validate a decoded pose against in-game panel displacement. Do not implement from the Akila sample alone.

### Header fields vs rig bone tables (Claude, 2026-10-09, offline)

Checked against each family's `characterassets\skeleton.rig` (name table at the end of the rig):

| Family | rig u32[0] | rig node names | `open.af` u16s at 0x28 |
|---|---:|---:|---|
| Akila hinged | 5 | 6 | 5, **6**, 31, 2 |
| Generic `genintrmsmwallmid_doora00a` | 5 | 21 | 5, **21**, 61, 2 |
| Ship `..._exsm_door01` | 5 | 24 | 5, **24**, 81, 2 |
| Ship `..._exlg_door01` | 5 | 49 | 5, **49**, 91, 2 |

So in all four: field 1 = 5 matches the rig's leading u32 (likely format version); **field 2 = the rig's bone count**;
field 3 is a frame count (31/61/81/91; 30 fps is assumed, not confirmed); field 4 = 2 in all four (meaning unknown). Template hints from the
rig names: the small ship door has `DoorUpper01` / `DoorUpperMesh01` (candidate for FO4's vertically split vault doors),
the generic door has `DoorPanel01_Point` / `DoorPanel02_Point` (candidate for the sideways elevator doors). Still needed
before a decoder: which bytes hold per-bone channel masks, then one decoded pose checked against an in-game panel position.

## Multi-part doors (2026-10-12, Claude; offline, in-game test pending)

**Symptom.** FortHagen01's shutter `0BD6A1` (`BldWoodPDoorShutter01`) shows OPEN, flips to CLOSE, and only one of its
two panels swings (supervised_1011 tests 0004/0005).

**Where the second panel is lost** (evidence and counts: docs/ai/research-log.md, 2026-10-12):
1. `nif.door_hinge` returns the first node of the FO4 `Open` sequence only (`Left`).
2. `convert_static.convert_door` hangs that node's shapes under the Akila hinge; every other shape (`Right:30`) goes
   under the static `Frame` node, with no bone and no body.
3. The DOOR record points at the Akila rig and clips, whose `open.af` has exactly one track (`Hinge01_Point`), so a
   second part could not move even if it were there.
4. `pipeline.Converter` only checked `door_hinge`; `door_motion.inspect` already flagged the door
   (`requires_additional_motion_support`).

**What vanilla does.** A vanilla double door (`IndIntRmSmWallMid_DoorA01`) uses the same graph
(`SimpleOpenClose01.agx`) with its own rig (7 bones) and clips: one track per leaf, one body per leaf in its NIF. The
graph only sequences Open and Close; the parts that move are whatever the rig and clips name. Vanilla clips carry tracks
for animated bones only, keyed as offsets from the bone's bind.

**Fix.** A rigged door whose `Open` sequence moves geometry outside its first node
(`convert_static.frozen_door_parts`) is converted by `convert_static.convert_multipart_door` when
`convert_batch.py --door-anim-dll <CALUMI.Animation.dll>` is given (external library, not distributed; pinned in the
2026-10-07 Codex history):
- NIF: `FO4Port_<model>` > the FO4 scene root (its stored transform left out, as for placed models) > one node per FO4
  node the sequences animate plus their static ancestors and shape parents, named as in FO4 and tagged `sgoKeep`; each
  shape under its own node; an animated node with a rotated bind gets a static `<name>_Bind` parent so it can keep an
  identity bind.
- Collision: one keyframed box per moving node that holds geometry (bone-local, the same box template and vanilla leaf
  donor as the template doors), so each panel's body follows its panel. Static frame geometry keeps no body, as before.
- Rig and clips (`native_door.export_files`): `meshes/<model>/characterassets/skeleton.rig` with every node as a bone,
  `meshes/<model>/animations/Open.af` / `Close.af` (one track per animated node: rotation keys every frame, translation
  keys when the node slides, offsets from the bind, 30 fps; FO4's own keys and timing) and `.afx` descriptors.
- Manifest door entry: `rig: native`, origin offset 0 (the NIF keeps FO4's origin), bounds, `skeleton` / `animations`
  pointing at those files (the plugin writer puts them in BNAM / CNAM, unchanged code), `animated_bones`,
  `moving_bodies`, `files` (checkpoint inventory).
- Without `--door-anim-dll` (or if the multi-part build fails: `door_error` says why) the template door is kept and the
  manifest lists the parts left closed in `door_frozen_parts`. Single-part doors keep the template path unchanged.

Offline checks (16-cell door models re-converted into `C:\Modding\staging\door_two_panels`): 47 of 57 models
byte-identical to the pinned build, the 10 multi-part models changed; `scripts/oracles/door_panels.py` (new: every FO4
moving part needs an Open and a Close track and a moving body; `--dll` reads the clips back) goes from 23 of 40 parts to
40 of 40; `scripts/oracles/door_bodies.py` (now per bone for native doors) 0 errors.

Known limits and unknowns:
- In game nothing of this is verified yet: whether Starfield loads a rig and clips from our `Main.ba2` (vanilla ones
  live in `Starfield - Animations.ba2`), the bind-offset convention (from the vanilla survey only), and two separate
  keyframed physics systems in one NIF (vanilla double doors share one system with a body per leaf).
- Knobs, handles and latches that FO4 animates get their own small keyframed boxes.
- Text-key events (FO4 door sounds) are not encoded; DOOR sounds stay unset.
- Load doors and `NOT_HINGED_RE` doors (vault doors, elevators: 36 records in Fallout4.esm) are unchanged; their FO4 keys
  (including slides) would work the same way.
- The FortHagen01 shutters are window shutters (sill 1.08 m above the floor): their walk test cannot pass even with
  both panels open. The route planner should skip raised openings (leaf bottom above step height); not changed here.
  `FancyBureauDoor01` is furniture (bureau doors): same.

### In-game test plan (not run)

What a new pinned build changes against `integ_1011`:
- `FO4Port.esm`: 10 DOOR records (BNAM, CNAM, OBND) and their 38 references (position only: the template doors' origin
  shift is gone). Nothing else; FormIDs unchanged (checked offline with an overlay plugin, 48 of 54,271 records differ).
- `FO4Port - Main.ba2`: the 10 door NIFs, 10 rigs, 20 `.af`, 20 `.afx`, and the shape-local meshes of these doors.
  Textures and materials do not change.
- A fresh test save: the queue's save is named after the plugin hash, so a new plugin gets one; doors opened in an older
  save keep their old positions (journal 2026-10-09).

Overlay staging (the pinned build plus only these doors; never write into `integ_1011`), from a worktree of this
branch:
```powershell
$pin = 'C:\Modding\staging\integ_1011'; $doors = 'C:\Modding\staging\door_two_panels'; $ov = 'C:\Modding\staging\integ_1011_doors'
# 1. door models only (17 s); editor IDs from the pinned build
New-Item -ItemType Directory $doors; Copy-Item "$pin\editorids.json" $doors
python scripts\convert_batch.py --fo4-data <FO4 Data> --staging $doors --content-resources <ContentResources.zip> `
  --texconv <Texconvx64.exe> --collision-template <template.nif> --starfield-data <Starfield Data> `
  --door-anim-dll <CALUMI.Animation.dll> --cell-json "$pin\merged.json" --types Door --limit 100000
# 2. copy of the pinned staging + the new door files + overlay manifest
robocopy $pin $ov /E /XF *.ba2 FO4Port.esm /XD .checkpoints
robocopy "$doors\meshes" "$ov\meshes" /E; robocopy "$doors\geometries" "$ov\geometries" /E
python scripts\overlay_manifest.py "$pin\manifest.json" "$doors\manifest.json" "$ov\manifest.json" --native-doors-only
# 3. plugin (same writer as the pinned build; formids.json came with the copy)
cd dotnet\PluginSpike; $env:STARFIELD_DATA = '<Starfield Data>'
dotnet run -c Release -- $ov "$ov\manifest.json" @(Get-ChildItem C:\Modding\staging\exports_1011\*.json | % { "$ov\$($_.Name)" })
# 4. offline checks before any deploy
python scripts\oracles\door_panels.py --manifest "$ov\manifest.json" --staging $ov --fo4-data <FO4 Data> --dll <CALUMI.Animation.dll>
python scripts\oracles\door_bodies.py --manifest "$ov\manifest.json" --staging $ov
```
Deploy (`deploy_starfield.py install --staging $ov`) only when the owner or the chain switches the pinned build; the
running batch_full queue must finish on `integ_1011` first.

Runner tests that verify it (`testqueue.py plan --staging $ov --kinds door --routes-prefix routesfull_`, then keep the
tests on the 10 models; route files are computed from the FO4 models and positions, so they stay valid):
- supervised_1011 0004/0005 and batch_full 0334-0337 (`BldWoodPDoorShutter01`, FortHagen01 `0BD6A1` / `0BD69F`): pass =
  both panels swung in `r*_open.png`; the walk verdict stays BLOCKED (window).
- batch_full walk tests expected to PASS from both sides: `PaintedWoodDoorDouble01` 0830-0837, 0848-0849 (Parsons
  `06CF29`), 0852-0855; `BldWoodPDbDoor01` 0071-0072, 0091-0094 (library twins), 0184-0185, 0200-0201, 0627-0628;
  `IndMetalDbDoor01` 0491-0492, 0507-0508, 0850-0851, 1155-1156, 1159-1160, 1516-1517; `UtilMetalDbDoor01` 0358-0359,
  0509-0510; `HitDoorSm01` 0190-0199, 0204-0207 and `HitDoorLg01` 0186-0187 (Cambridge: all four panels slide);
  `SwitchDoorExSmLatch01` 0378-0379, 0475-0476, 0525-0526, 0995-0996, 1265-1266 and `SwitchDoorExSmLatch02` 0360-0361.
- batch_full 0503-0504 (`FancyBureauDoor01`, furniture): both doors swung in the screenshot; no walk.
- Controls: a few template doors from the same cells (e.g. `BldWoodPDoor01`, `SubDoor01Right`) must still pass.
The batch_full results of these 76 tests on `integ_1011` are the before.
