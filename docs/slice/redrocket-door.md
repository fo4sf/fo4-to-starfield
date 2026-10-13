# Slice: the working door (Red Rocket cave)

Author: Claude, 2026-10-12. Branch `claude/slice-redrocket-door`, stacked on `claude/integration-1012` (runner #59,
npc_nav #68, daylight #73, raider #75, core64c #76, N0b #77). Starfield 1.16.244, Fallout 4 1.10.163.
Status: **built and checked offline, staged, queue planned, not deployed, not run.** Offline checks are not in-game
acceptance. After QA on PR #78 (fix pass, section 6 "Fix pass"): staged `C:\Modding\staging\slice_redrocket_door_b`,
queue `C:\Modding\testqueue\slice_redrocket_door_b` (queue.json only, planned at 95552f8; not in the chain: that is
the owner's call, after the chain's runner checkout has this branch). The first staging and queue
(`slice_redrocket_door`, bf7c853) are superseded: never run them (their judge could call a stand 5 m from the door
"the door does not work", their interior start stood 4.50 m from the door, and the runner of that commit could
teleport after a load it did not see).
Labels: **verified** = checked here on files (number given), **supported** = supported hypothesis, **unresolved**,
**refuted**.

The owner's playable slice is: Commonwealth terrain -> moving NPC -> interaction/combat -> **working door ->
converted interior -> save/reload**. This page covers the bold part: the Fallout 4 load door between the Commonwealth
and RedRocket01 (the mole-rat cave behind the Red Rocket truck stop), placed on the converted terrain of experiment 2d,
leading into the converted interior of the pinned build, and a runner test that goes through it and back, saves,
loads and reads where the player is after every step.

## In short

- Fallout 4 links RedRocket01 and the Commonwealth with a pair of **automatic** load doors (`AutoloadDoor`, an
  invisible trigger the player walks into), 38 m south of the Red Rocket arrival used by every terrain test.
- Neither end existed on our side: the pinned build never placed the interior one (its model is an editor marker) and
  experiment 2d skipped the exterior one for the same reason. Nothing is placed twice.
- `FO4SliceRedRocket.esm` (1,123 bytes) adds both ends as the vanilla Starfield automatic cave door
  `AutoloadDoor_Cave` (24F9CE), each persistent, each XTEL naming the other, at the Fallout 4 positions / 70. Vanilla
  uses exactly this door in exactly this layout for its own cave entrances on planets (45 of them).
- One install (`C:\Modding\staging\slice_redrocket_door`) = experiment 2d (terrain, 8,069 objects, navmesh) + the door.
- The runner gets a new kind, `door_trip`: coc to Red Rocket, walk into the cave mouth, arrive in RedRocket01, walk
  into the exit, arrive on the terrain, save, move away, load, read again. Every arrival must be read (position,
  GetInCell, screenshot) for a PASS; a load is noticed by the HUD or by the position, whichever comes first; a trip
  that loaded only from the last-try teleport is not a PASS (NEARONLY).
- The game must load `FO4SliceRedRocket.esm` after `FO4Port.esm`, which the runner's deploy activates last: cycle.ps1
  now moves an experiment plugin after its masters (`exp_install.py order`).

## 1. The Fallout 4 link (verified)

Read from Fallout4.esm with `dotnet/SliceDoor fo4` (Mutagen 0.55.0-alpha.67; evidence JSON in the staging folder,
`evidence\fo4_door_link.json`).

| | interior door | exterior door |
|---|---|---|
| FormID | `05E844` | `08EB65` |
| cell | RedRocket01 (`05E62F`), persistent group | Commonwealth persistent cell `018AA2` (exterior cell -18, 18) |
| record flags | 0x400 (persistent) | 0x400 |
| base | `01ED77` AutoloadDoor | `01ED77` AutoloadDoor |
| position (FO4 units) | -116.13465, 169.1064, 0 | -69646.37, 77664.305, 6907.905 |
| rotation (rad) | 0, 0, 5.759587 | 0, 0, 0.24999945 |
| scale | 0.93 | 0.23 |
| XTEL door | `08EB65` | `05E844` |
| XTEL arrival (FO4 units) | -69687.12, 77290, 6984 | 3.4483528, -463.53928, -0.43591836 |
| XTEL rotation (rad) | 0, 0, -3.1081858 | 0, 0, 2.7014012 |
| XTEL flags | 0 | 0 |

Base `01ED77` AutoloadDoor: name "Auto Door", model `AutoLoadMarker01.nif`, flags **Automatic**, no script, OBND all
zero. The model is an editor marker (one `EditorMarker` BSTriShape, x -64..64, y -8..8, z 0..192 units, no
collision; read from `Fallout4 - Meshes.ba2`).

In the converted frames (position / 70, as PluginSpike and experiment 2c place everything):

| | world's own frame (m) | merged frame with exp2d's last offset (-1200.0, -2699.8, 0.01) |
|---|---|---|
| exterior door | -994.948, 1109.490, 98.684 | -2194.95, -1590.31, 98.69 |
| arrival outside (interior door's XTEL) | -995.530, 1104.143, 99.771 | -2195.53, -1595.66, 99.78 |
| exp2d's coc arrival (pump island, `spawn_local`) | -989.029, 1147.200, 105.261 | -2189.03, -1552.60, 105.27 |

So the exterior door is **38.2 m south (bearing 189 degrees) and 6.6 m below the exp2d arrival**, in the hole of the
cave entrance static `CaveEntrGround01_Grass` (`08CCF2`, placed by exp2c / exp2d) under tree roots; the arrival
outside is 5.5 m south of it. Inside (interior frame, m): the door at -1.659, 2.416, 0.000 at the mouth of the cave
hall, the arrival inside at 0.049, -6.622, -0.006, 9.2 m to the south. The exp2d offset is the one the runner measured
on 2026-10-12 00:13 (`terrain_exp2d` a1, "offset -1200.0, -2699.8, 0.01 from spawn"); the runner measures its own at
every arrival.

## 2. Our side before this branch (verified)

- **Pinned build** (`C:\Modding\staging\integ_1011\FO4Port.esm`, `dotnet/SliceDoor port`): `FO4Port_RedRocket01` is
  `002338:FO4Port.esm`, 0 persistent and 616 temporary references, **no reference with an XTEL and none with a DOOR
  base**; the whole plugin has 2 XTEL references (the FortHagen pair). `formids.json` has no key for `05E844`. The
  converter never places marker models, which is why: the 2026-10-11 research-log entry lists `05E844`
  (`autoloadmarker01.nif`) among the 4 load-door sources not placed. So there was no interior door to override and no
  XTEL to inspect: this branch adds one.
- **Experiment 2d**: `skipped.json` lists `08EB65` with reason `editor_marker` ("editor marker model
  AutoLoadMarker01.nif"); `objects.json` has no reference of it. The cave mouth itself is there: `CaveEntrGround01_Grass`,
  the tree roots, rocks and debris around it are placed. The exterior door therefore exists once, as the new trigger;
  nothing is replaced or skipped.

## 3. The door base: vanilla `AutoloadDoor_Cave` (decision)

FO4Port has no converted base for `01ED77` (marker model, never converted), so the door uses a vanilla Starfield
load door. `AutoloadDoor_Cave` (`24F9CE:Starfield.esm`) is Starfield's own version of the same object (verified,
`dotnet/SliceDoor sf-door`, `evidence\sf_autoload_door.json`):

| | Fallout 4 `AutoloadDoor` 01ED77 | Starfield `AutoloadDoor_Cave` 24F9CE |
|---|---|---|
| name | Auto Door | Auto Door |
| flags | Automatic | Automatic |
| model | `AutoLoadMarker01.nif` | `Meshes\autoloadmarker01.nif` |
| marker size | 128 x 16 x 192 units | 1.8288 x 0.2286 x 2.7432 m (BSGeometry bounds, `Starfield - Meshes01.ba2`: 6 ft x 9 in x 9 ft) = the FO4 marker / 70 to within 0.013 % (128 / 70 = 1.82857 m) |
| script | none | `ENV_NotSealedLocationDoorScript` (properties `ENV_Loc_NotSealedEnvironment` 0EF1E0, `..._BreathableAtmosphere` 20E1D9) |
| components | | none (no animation graph) |

- Vanilla references: 92 (47 in interior cells, 45 in worldspaces). **All 45 worldspace ones are in overlay
  worldspaces, in the worldspace's persistent cell**, linked to interior caves (e.g. `OEAF014CaveWorld` `005791` <->
  `OEAF014Cave` `290FA2`), scales 0.56 to 2.55. All 345 XTEL references in Starfield.esm's worldspaces sit in the
  worldspace's persistent cell, none in an exterior cell. Every vanilla one also carries an XNDP navmesh door link.
- Because the marker is the FO4 marker at 1/70, the Fallout 4 scales (0.23 outside, 0.93 inside) carry over unchanged.
- Game settings (Starfield.esm GMST, verified): `fAutoDoorActivateDistance` (051542) = 3, `fAutoDoorDisplayDistance`
  (051543) = 12, `fDistanceAutomaticallyActivateDoor` (003420) = 3.571875 (= 250 FO4 units). Starfield.exe also holds
  `fAutoDoorFadeSecs:General`, `AutoLoadDoorRolloverEvent` and `BusyActivatingTeleportAutoDoor` (strings, verified).
  That the door loads when the player comes within 3 m of it, behind a fade and a loading screen: **supported**.

Alternatives: a converted FO4Port load door base (e.g. `FO4Port_IndMetalDoorLoad01`): a visible metal door in a
cave hole, with an E prompt the Fallout 4 cave never had; a new DOOR record copying 24F9CE without its script: a
configuration vanilla never uses (the script handles the breathable-atmosphere state on planets); the hidden
elevator door `LoadElevator_InvisibleDoor` (21F2A7): Hidden, activated by scripts, not by walking into it. Decision
recorded in docs/ai/decisions.md (2026-10-12).

## 4. The plugin (verified offline)

`FO4SliceRedRocket.esm`, written by `dotnet/SliceDoor build` from `slice_params.json` (which
`scripts/slice/make_redrocket_door.py stage` derives from the evidence above):

| record | FormID (file) | what |
|---|---|---|
| WRLD `FO4CW_Commonwealth` | 01000802 | override of FO4TerrainExp2.esm's worldspace, **byte-identical** to it |
| CELL (the world's persistent cell) | 01000B4E | override, byte-identical; holds the exterior door |
| REFR `FO4SL_RedRocketCaveDoorExt` | 03000800 | base 24F9CE, persistent (0x400), -994.94814, 1109.49007, 98.68436, rot z 0.25, scale 0.23, XTEL -> 03000801 at 0.04926, -6.62199, -0.00623, rot z 2.7014, flags 0 |
| CELL `FO4Port_RedRocket01` | 02002338 | override of the pinned build's cell, byte-identical data; holds the interior door |
| REFR `FO4SL_RedRocketCaveDoorInt` | 03000801 | base 24F9CE, persistent, -1.65907, 2.41581, 0, rot z 5.7596, scale 0.93, XTEL -> 03000800 at -995.53029, 1104.14286, 99.77143, rot z -3.1082, flags 0 |

Masters: Starfield.esm, FO4TerrainExp2.esm, FO4Port.esm (in that order). No XNDP navmesh door link is written: NPCs
will not path through the door (out of scope here). The exterior door sits in the world's persistent cell like the
45 vanilla ones and like exp2b's anchor; the anchor read back its unmerged local position (exp2b, 2026-10-11), so
whether a persistent door stands at the merged position is **unresolved**. An in-leg PASS shows that it does; a NOLOAD
alone cannot tell a door at its unmerged local position from an automatic door that does not fire, so the step also
reads the door's own getpos (section 6, a diagnostic: our anchors read local coordinates there, a vanilla ref did not).

**Load order.** The runner installs the experiment's plugins before the launch (`pre_launch`), then cycle.ps1's
deploy removes and re-appends `*FO4Port.esm`, so FO4Port.esm would load after the plugin that masters it (Plugins.txt
of the last exp2d run: `*FO4TerrainExp2.esm`, `*FO4TerrainExp2_Mars.esm`, `*FO4Port.esm`). A master loading after its
plugin is unsafe (in Fallout 4 / Skyrim a crash at load; Starfield's behaviour **unresolved**, not tried). So cycle.ps1
now runs `exp_install.py order` after the deploy and before the launch: every plugin the experiment install added
moves right after the last of its masters that Plugins.txt lists; a master that is neither listed nor one of the
game's own files ends the launch (cycle exit 7, the runner stops). The planned order is `*FO4TerrainExp2.esm`,
`*FO4TerrainExp2_Mars.esm`, `*FO4Port.esm`, `*FO4SliceRedRocket.esm`. Console load-order bytes: FO4TerrainExp2.esm =
02 (**verified**: its anchor read as `02000800` in every exp2 run), so FO4TerrainExp2_Mars.esm = 03, FO4Port.esm = 04
and `FO4SliceRedRocket.esm` = 05 (both TES4 flags 0x1, full plugins: **supported**), the doors `05000800` /
`05000801`. The verdict does not depend on these numbers; plan.json's `outside.ref` `05000800` is only used for the
getpos diagnostic (section 6).

## 5. Offline checks (verified; `offline_check.json` in the staging folder: 27 checks pass, one of them SliceDoor's 28)

- **Mutagen read-back** (`SliceDoor check`, 28 checks): the masters; exactly 5 records; the WRLD, its persistent cell
  and the interior CELL equal their masters' records (same FormKey, every field, children aside); each door one
  persistent reference with flag 0x400, base resolving to `AutoloadDoor_Cave` (Automatic) in a link cache over
  Starfield.esm, FO4TerrainExp2.esm, FO4Port.esm and the plugin; **each XTEL names the other door, resolves in that
  load order, and the other door's XTEL links back**; positions, rotations, scales and XTEL values as staged; the
  world and the interior cell resolve to this plugin's overrides.
- **Raw**: the three override records' data byte-identical to the masters' records (raw group walk, zlib-aware);
  the door references are this plugin's 0x800 / 0x801.
- **exp2d copies**: both plugins byte for byte (SHA-256), the Data tree 7,736 files / 2,358,899,092 B.
- **Ground** (exp2d's BTD and converted collision; the interior against the pinned build's own converted NIFs,
  `src/fo4sf/sfbodies.py`, placed as PluginSpike places them):

| | value |
|---|---|
| exterior door | z 98.684, floor under it 97.729 (the cave entrance static's floor; the BTD is 95.25 there, a pit under the static): the 0.63 m marker stands 0.96 m above the floor in the cave mouth |
| arrival outside | XTEL z 99.771 over the terrain at 99.734; a returning player lands at 99.734 (the judge's `ground`) |
| walk outside | from the arrival (the start) to the door: floor all the way down the cave mouth, 99.73 -> 97.73 m over 5.38 m, no rise over 0.02 m; the assumed capsule (0.35 m x 1.8 m) clear until the door itself (it first touches the cave entrance static at the door's own xy, 5.38 m), so the player can touch the marker; within 2.7 m of the door's origin after about 3 m |
| interior door | origin z 0.000 over a column's rock base whose top is 0.275 m: the origin stands 0.27 m inside the rock base (the check allows 0.3 m); the hall floor 0.143. Fallout 4 has the same geometry (position / 70) |
| arrival inside | XTEL z -0.006: 0.25 m below the top of a rock mound (0.244) and 2 cm below the hall floor (0.013), as Fallout 4's XTEL / 70; the capsule touches `CaveMoundRocksMed04` there |
| walk inside | the straight line from the arrival crosses mounds (capsule blocked from 4.1 to 5.9 m). No start 5.27 to 8 m from the door, within 90 degrees of the arrival's bearing, has a straight walk with the capsule clear to the door's marker: the tall column `CaveColmRockTall` stands beside the door. The runner starts 5.27 m west of the door (-6.837, 1.437, 0.064; 10.6 m from the arrival; heading 79 degrees): floor all the way, the capsule clear for 3.01 m, until 2.26 m from the door's origin, where it first touches that column. Walking in from inside therefore needs the 3 m range measured to the door's origin (**supported**, not shown); otherwise only the last try loads (NEARONLY) |
| start distance | each start at least `fDistanceAutomaticallyActivateDoor` 3.57 m + half the scaled marker width + the capsule radius 0.35 + 0.5 m from its door: outside 4.63 m (the arrival is 5.49 m away), inside 5.27 m (the first staging had 4.50 m, close enough to fire the door at the start teleport if the range is measured to the marker) |
| last-try spots | outside 1.0 m in front of the door (-995.056, 1108.496, 98.311); inside 1.5 m (-2.155, 1.000, -0.008); both on the floor, capsule clear |

- Both arrivals stand outside the 3 m activation range of their own side's door (5.5 m and 9.2 m), so an arriving
  player does not bounce back. The hop from the coc arrival to the outside start is 6.5 m east-west, 43.1 m
  north-south (within the 2-cells-per-axis teleport rule).
- The plan passes the runner's own `door_test`; the queue needs `door_check`, `door_trip` and `plugin_order`.

## 6. The runner test: `door_trip`

New kind in `scripts/game/testqueue.py` (plan, judge, timeout) and `scripts/game/qstep.ps1` (the step). One test does
the whole trip in one game session (planned with `--fresh`: a new launch first):

1. `coc FO4CW_RedRocketSpawn`, the HUD back, the arrival read until two reads 3 s apart agree within 0.3 m; the merge
   offset O = arrival - `spawn_local`. Not settled: INCONCLUSIVE ANCHOR, nothing else is done.
   With `outside.ref` (plan.json: `05000800`) the exterior door's own `getpos` (`prid`, nothing moves) goes to
   `obs.door_read`: a diagnostic only. Our persistent anchors read their unmerged local position in exp1d / exp2b
   while a vanilla persistent ref in LC172World read the merged one, so the detail names which this door reads; a
   local read does not prove where the door stands.
2. **in**: teleport to `outside.start` + O (0.5 m above the floor) facing the door (`heading_out` 6.2 degrees), read
   the position and take `in_start.png`; nothing more is tried in this leg unless that read is at the start (within
   `start_tol`). Walk at the door in 500 ms steps (`hold:w`), after each a HUD check (the fade and the loading screen
   hide it) and a position read (one readpos run): a HUD gone, or a read more than `moved_m` (30 m) from the start, is
   a load (`load_by` hud / position) and ends the walk at once; two steps without 0.2 m of progress end it too
   (`walk_stopped`); at most 8 s. If a prompt showed, E (after a read on this side). If nothing loaded, the last try:
   a teleport to `outside.near` + O, only after a read put the player on this side of the door (else `near_skipped`),
   then 6 s of HUD checks. Then the HUD back (up to 90 s) if a loading screen was seen, the arrival read until it
   settles (an arrival far from the start that no check saw load is credited to the last action, `load_by`
   position), `player.GetInCell FO4Port_RedRocket01` (OCR'd like GetIsID) and `in_arrival.png`. Not within 4 m of
   `inside.arrival`: the step ends here.
3. **out**: the same from `inside.start` (heading 79.3 degrees) to the interior door; expect `outside.arrival` + O.
4. `save fo4sf_slice_rrdoor`; the file must appear in the Saves folder within 30 s (`obs.save`).
5. A teleport back to the settled coc arrival (about 44 m from the saved spot, read as `reload.away_read`), then
   `load fo4sf_slice_rrdoor`: a loading screen is looked for (20 s; the HUD goes away), the HUD back, the position
   read until it settles, GetInCell and `reload.png`. The player must come back to the saved spot, which shows the
   load whether or not a HUD check caught its loading screen.

`obs.json`: `spawn_read`, `offset`, `door_read`, `legs` [{`name`, `start_read`, `start_shot`, `prompt`, `checks`
[{`tag` (walk / pre_e / e / pre_near), `ms`, `read`, `from_start`, `to_door`}], `walk_stopped`, `walk_skipped`,
`trigger` (walk / e / near / ""), `load_by` (hud / position), `walked_ms`, `near_m`, `near_skipped`, `load_seen` (the
HUD went away), `hud_back`, `load_s`, `arrival_read`, `arrival_settled`, `arrival_reads`, `incell`, `incell_ocr`,
`shot`}], `save` {`name`, `found`, `file`, `size`, `mtime`, `why`}, `reload` {`away_read`, `away_shot`, `load_seen`,
`hud_back`, `load_s`, `read`, `settled`, `incell`, `shot`}.

### Verdicts (the first leg that does not pass decides)

| verdict | class | means |
|---|---|---|
| PASS | PASS | walked (or E) through: arrived inside within 4 m of the interior arrival point (settled; GetInCell 1 or unread), back outside within 4 m of the arrival point + O (settled; GetInCell 0 or unread), the save file written, after `load` back within 1 m of where the save was made (from 44 m away, or with a loading screen seen), settled, within 1 m of the ground (99.73 + O.z), GetInCell 0 or unread |
| INCONCLUSIVE | NEARONLY | all of the above, but a leg loaded only from the last-try teleport 1 m from the door: the door works, walking in is not shown (retried) |
| INCONCLUSIVE | ANCHOR | the coc arrival never settled: no offset, no door tried |
| INCONCLUSIVE | START | the start in front of a door not reached (> 3 m) or not read: nothing else tried in that leg |
| FAIL | NOLOAD | no load, and the player stood (settled) within `activate_m` (3 m) of the door at the end (after the last try: 1 m), GetInCell not saying the far side: the door does not fire where it stands. With `outside.ref` the in leg's detail adds where getpos reports the door |
| INCONCLUSIVE | NOREACH | no load, but the player ended more than 3 m from the door (the walk blocked, no last try): the door was not tried; the detail names the closest read |
| INCONCLUSIVE | NOMOVE | the HUD went away but the player did not move: a menu or popup, not a load |
| FAIL | UNMERGED | back outside, but at the arrival point's position in the world's own frame (the overlay's merge offset not applied to the XTEL arrival) |
| FAIL | REMERGED | back outside at the arrival point shifted by whole cells: the overlay merged at another offset than at the coc arrival |
| FAIL | FELL | over the arrival point but falling (more than 3 m below it, not settled), or after the load more than 3 m below the ground |
| FAIL | WRONGCELL | loaded, but GetInCell says the wrong side (still in, or not in, RedRocket01) |
| FAIL / INCONCLUSIVE | ELSEWHERE | in RedRocket01 (GetInCell 1) but away from the arrival point / somewhere unexplained |
| INCONCLUSIVE | CELLREAD | the position says one side, GetInCell the other (after a leg, including a player still at this side's door with GetInCell saying the far side, or after the load): an OCR or console question, retried; never a PASS or a FAIL |
| INCONCLUSIVE | NOSAVE | the save file was not seen: the load is not tried (a load of a missing save proves nothing) |
| INCONCLUSIVE | RELOAD_UNSEEN | after `load` the player is still where it was moved to (the load did not happen), or no loading screen was seen and the player had not been moved away: the read after it says nothing |
| FAIL | RELOAD | after the load more than 1 m from where the save was made |
| FAIL | OFFGROUND | after the load at the saved spot, but not within 1 m of the expected ground |
| INCONCLUSIVE | UNREAD / NOSHOT | a position not read or not settled, a screenshot missing |

The detail names the trigger of each leg and how the load was noticed, the load times, GetInCell, the offset and the
door's getpos. Files per attempt: `arrival.png`, `in_start.png`, `in_arrival.png`, `out_start.png`,
`out_arrival.png`, `saved.png`, `away.png`, `reload.png`, the walk / HUD checks, the GetInCell captures and OCR
(`in_cell_*`, `out_cell_*`, `reload_cell_*`).

### Fix pass after QA (PR #78, 2026-10-12)

- **NOLOAD only from a stand in range.** The first judge returned FAIL NOLOAD for any leg that ended within 30 m of
  its start without a loading screen, without looking at GetInCell or at how close the player got: a player 5 m from
  the door, or one GetInCell put inside RedRocket01, was "the door does not work". Now NOLOAD needs the final stand
  (settled) within `activate_m` of the door and GetInCell not saying the far side; otherwise NOREACH, CELLREAD or
  UNREAD (`tests/test_door_trip.py`, the QA cases among them).
- **A load the HUD checks missed.** The first step noticed a load only from one HUD screenshot after each walk step.
  If the fade, the loading screen and the fade-in all fell between two screenshots, it walked on in the new cell and
  then teleported to this side's last-try spot there (the in leg: exterior coordinates inside RedRocket01, the void;
  the out leg: interior coordinates on Mars, 99 m under the terrain). The sandbox, given an instant loading screen,
  made 6 loads of a trip planned as 2. Now every walk step is followed by a position read, E and the last try need a
  read on this side, and the same sandbox makes exactly 2 (`test_a_load_no_hud_check_saw_is_found_by_the_position`).
  How long Starfield's loading screen lasts against the about 1.5 s between a step and its screenshot is
  **unresolved**; the step no longer depends on it.
- The load after the save is shown by the position (moved 44 m away first), GetInCell after it is judged, a trip that
  loaded only from the last try is NEARONLY, the interior start keeps 5.27 m from its door, the door's getpos is read
  as a diagnostic, and the offline check labels say what the code checks (section 5).

### Plan and run (C:\Modding\testqueue\slice_redrocket_door_b)

The queue needs runner features `door_check`, `door_trip` and `plugin_order`: the chain's runner must first be on a
checkout with this branch at or after the fix pass (an older runner refuses the queue before launching: its
`exp_install.py` rejects `--needs` or lacks the features, exit 2 / 5; the first door_trip runner, bf7c853, lacks
`door_check`).

```powershell
$py = 'C:\Modding\venv-render\Scripts\python.exe'
& $py scripts\game\testqueue.py plan-door --staging C:\Modding\staging\integ_1011 --exp-dir C:\Modding\staging\slice_redrocket_door_b `
      --out C:\Modding\testqueue\slice_redrocket_door_b --plugins FO4TerrainExp2.esm,FO4TerrainExp2_Mars.esm,FO4SliceRedRocket.esm --fresh
& $py scripts\game\testqueue.py run --queue C:\Modding\testqueue\slice_redrocket_door_b --wait-for-idle --refocus --max-hours 2
& $py scripts\game\testqueue.py report --queue C:\Modding\testqueue\slice_redrocket_door_b
```

Optional: `--time-of-day 12` (the exp2d site is the night site; the runner's light ladder, PR #73) for lit exterior
screenshots; it adds the `light` need. Step timeout 4,676 s (worst case: every walk step with a position read, every
read retried); about 8 to 12 minutes expected.

Planned with the first command at 95552f8 (build `2470f876`, test `0000_door_trip_rr_cave_door`, needs `door_check`,
`door_trip`, `plugin_order`, `pre_launch` = the runner's own `exp_install.py install ... --plugins
FO4TerrainExp2.esm,FO4TerrainExp2_Mars.esm,FO4SliceRedRocket.esm --pack --needs door_check,door_trip,plugin_order`,
step timeout 4,676 s); a dry run of a copy of that queue.json in a scratch folder: "dry run: would run
0000_door_trip_rr_cave_door". The chain's current checkout (`fo4-to-starfield-wt\integ`, integration-1011) has no
`runner_features.py`; its `exp_install.py` rejects `--needs` (exit 2), so it would stop at "pre-launch exit 2" without
launching. The superseded first queue (`slice_redrocket_door`, planned at bf7c853 from the first staging, never run)
is left as it was: do not add it to the chain.

## 7. Unknowns and risks

1. Whether the persistent exterior door stands at the merged position (the in leg; vanilla's 45 overlay cave doors
   say yes, our own persistent anchor read local coordinates: **unresolved**).
2. Whether the XTEL arrival into our overlay gets the merge offset (the out leg; UNMERGED / REMERGED name the two
   ways it can fail: **unresolved**).
3. The activation distance (3 m `fAutoDoorActivateDistance` or 3.57 m `fDistanceAutomaticallyActivateDoor`, to what
   point of the player and of the door) and whether a teleport into the range loads as a walk does (**supported**:
   vanilla's automatic doors are entered by walking; the runner tries both, and a load from the teleport alone is
   NEARONLY). Outside the player can walk until it touches the marker; inside the capsule first touches a column
   2.26 m from the door's origin, so walking out needs the range measured to the origin (**supported**, not shown).
4. `ENV_NotSealedLocationDoorScript` on Mars from an overlay: vanilla runs it on every planet cave (**supported**
   harmless).
5. `player.GetInCell <cell>` in the console and its reply format (`GetInCell >> 1.00`, like GetIsID's: **supported**;
   GetInCell is in Starfield.exe next to "Is the reference in the specified cell?"). Unread is allowed, a contradiction
   is not.
6. Save and load inside a merged overlay world: what the test is for (**unresolved**). The save `fo4sf_slice_rrdoor`
   stays in the owner's Saves folder (overwritten by every run).
7. The interior start is in the hall's west branch, 5.27 m from the door (offline: floor and an assumed capsule).
   If the walk stops short of the range, the last-try spot 1.5 m from the door loads it (NEARONLY) or not (NOLOAD).
8. How long Starfield's fade and loading screen last against the about 1.5 s between the end of a walk step and its
   HUD screenshot (**unresolved**): the step reads the position after every step, so it no longer depends on it.

## 8. Reproduce

```powershell
$py = 'C:\Modding\venv-render\Scripts\python.exe'
& $py scripts\slice\make_redrocket_door.py stage --fo4 <FO4 Data>\Fallout4.esm --sf-esm <Starfield Data>\Starfield.esm `
      --port C:\Modding\staging\integ_1011 --exp2d C:\Modding\staging\terrain_exp2d --out C:\Modding\staging\slice_redrocket_door_b
& $py scripts\slice\make_redrocket_door.py check --sf-esm <Starfield Data>\Starfield.esm --port C:\Modding\staging\integ_1011 `
      --exp2d C:\Modding\staging\terrain_exp2d --out C:\Modding\staging\slice_redrocket_door_b
& $py -m unittest tests.test_slice_redrocket_door tests.test_door_trip
$env:FO4SF_QSTEP_SANDBOX = '1'; & $py -m unittest tests.test_qstep_sandbox.QstepDoorSandboxTests
```

stage runs `dotnet/SliceDoor` (fo4, sf-door, port, build) itself, about 50 s with the 2.3 GB copy (47 s for `_b`);
check about 30 s. Rebuild the slice whenever exp2d's plugin or the pinned build's RedRocket01 cell changes: the
overrides copy them (check compares them byte for byte).
