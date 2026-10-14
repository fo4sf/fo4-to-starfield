# door_trip after the first live runs: strict reads, position frames, facing, routes, and the merge of persistent refs

Author: Claude (runner role on branch `claude/core64c-cave-door`), 2026-10-13. Stacked on `claude/integration-1013`
(129b9ae). Starfield 1.16.244. Labels: **verified** = checked here (file, command, number), **supported** = supported
hypothesis, **unresolved**, **refuted**. Offline checks are not in-game acceptance. Companion page for the core64c door
itself (plugin, staging, routes, plan): [cave-routes.md](cave-routes.md). The door_trip design this changes:
[redrocket-door.md](redrocket-door.md) (PR #78).

## 1. What the first live runs showed (queue `slice_door_1013`, exp2d + `FO4SliceRedRocket.esm`, runner 129b9ae)

Attempt a1 (2026-10-13 16:13-16:22, `obs.json`, `in_*.png`, `in_cell_*`; read-only here), INCONCLUSIVE UNREAD:

- The coc arrival settled at -2189.03, -1552.80, 105.26: merge offset (-1200.0014, -2700.0000, -0.0009) (**verified**).
- The door's own getpos (`prid 05000800`) read **-994.95 1109.49 98.68: its unmerged local position**, as our persistent
  XMarker anchors always did (exp1d, exp2b, 2026-10-11) (**verified**).
- The in leg started where planned (read -2195.53 -1595.86 99.74). After the first 500 ms walk step the read came back
  **"99.74 -2195.27 99.41"**: the previous read's z, this read's x and z, its y lost (the default parser's bare-number
  fallback, `parse_getpos.py`; a test reproduces the exact read from a column-layout OCR text). The player really stood
  at (-2195.27, -1593.51, 99.41), 3.0 m south of the door's merged position, but the read was 2,372 m from the start,
  so the step declared a load "by position" and stopped walking (**verified**: obs.json, the GetInCell capture shows
  "GetPos: Y >> -1593.51" and "GetPos: Z >> 99.41" on screen).
- Four of the five arrival reads then failed; one read "-2195.27 -1.59 99.41" (OCR split "-1593.51" into "-1 593.51",
  which the default parser takes as -1.59) (**verified**, obs.json). In `in_cell_cap.png` the HUD's O2 / CO2 dial
  crosses the console's newest lines in the bottom-left corner: the likely reason the OCR loses lines there
  (**supported**; not measured).
- `player.GetInCell FO4Port_RedRocket01` was refused: **"Item 'FO4Port_RedRocket01' not found for parameter Cell."** and
  "Compiled script not saved!" (`in_cell_cap.png`) although `coc FO4Port_RedRocket01` works. The PR #78 hypothesis
  "GetInCell <EditorID> answers like GetIsID" is **refuted** for our cells' EditorIDs.
- The capture also shows the console's selection "DOOR 'FO4SL_F...'". That is the `prid 05000800` of the getpos
  diagnostic (the console keeps its selection), not a crosshair pick (**supported**): it says nothing about where the
  door stands.

Attempt a2 (reported by the lead), FAIL NOLOAD: 2.5 s of walking, then the last try 1 m from the door's merged position,
standing inside its 3 m range: no load; the door's getpos read its local position again.

## 2. Runner fixes (scripts/game, runner features `door_frames`, `door_route`)

| Change | Where | Why |
|---|---|---|
| Strict reads: `readpos.ps1 -Strict` -> `parse_getpos.py --strict`: only "GetPos: X >> v" style replies (a ':' after the label or a '>' after the axis), two decimals, never bare numbers, all three after this read's last X reply with exactly one Y and one Z after it, no `getpos x` echo after that X (this session's X lost), no number glued to more digits ("-1 593.51") | parse_getpos.py, readpos.ps1, qstep.ps1 (door_trip only: `$script:strictReads`) | a1's garble and its "-1.59" |
| A load is never taken from one read: a read more than `moved_m` from the leg's start needs a second one within 1 m of it; a read whose axes look swapped against the last read on this side (a value far from its own axis but within 3 m of another axis) is rejected; an unread step is re-read once (3 tries) and then the walk stops instead of walking blind | qstep.ps1 Leg-Check, Door-Leg | a1 |
| GetInCell is typed only with `inside.cell_id` (a form id; **unresolved** whether the console accepts it, not verifiable offline) and never judged; the console's refusal is parsed (`incell_error`) | qstep.ps1 In-Cell, parse_npc.py, testqueue.judge_door | a1 |
| Which side of the door: position frames. Interior frame = within `frame_m` (150 m) of the interior door, merged exterior frame = of the outside door + O, unmerged = of the outside door. FAIL ELSEWHERE (loaded into the far frame, away from its arrival point), FAIL WRONGCELL (loaded, but in the wrong frame), INCONCLUSIVE ELSEWHERE (no known frame); CELLREAD is gone | testqueue.judge_door | GetInCell unusable |
| Facing: every arrival read also reads `player.getangle z` (`readpos -Angle`; reply format "GetAngle: Z >> v" **supported**, as GetPos's); with `<side>.arrival_heading` (the XTEL marker's rotation, degrees) the first heading after the arrival must be within `facing_tol` (20 degrees), and after the load the saved heading must come back (the away teleport faces north, so a load that keeps the player's current yaw shows). FAIL FACING / INCONCLUSIVE NOFACING after every position check | qstep.ps1 Read-Settled, testqueue.judge_door | owner's acceptance: "correct position/facing" |
| Routes: with `outside.route` / `inside.route` (waypoints from where the player stands to the door) a leg does not teleport to a start: it walks from the coc arrival (in) or the interior arrival (out), per step `player.setangle z` at the next waypoint not yet reached or passed, a W hold for the remaining distance at the speed the last step showed (at most `route_hold_ms`), a HUD check and a strict read; after the last waypoint, `walk_step_ms` steps at the door itself (at most `route_final_steps`). The last-try teleport stays (NEARONLY). The judge names the steps and teleports | qstep.ps1 Route-Walk, testqueue | owner's acceptance: "Initial COC/ray hops are setup/loading evidence, not walking or door acceptance" |
| Merge probes: `probes` [{ref, local, what}]: their getpos after the arrival, reported as merged / local / neither, also when a leg fails | qstep.ps1, testqueue | section 3 |

Every door_trip test planned now carries `"reads": "strict"` (runner feature `door_frames`); a route adds
`door_route`. An older runner refuses such a queue before launching (`exp_install.py --needs`). Queues planned before
(PR #78's `slice_redrocket_door_b`, the running `slice_door_1013`) run on the new runner with the same fixes (the step
is strict for every door_trip test; GetInCell is no longer typed without a `cell_id`).

**Note for PR #78:** the read and GetInCell fixes apply to its door_trip as well; its `slice_redrocket_door_b` plan
needs no change, but its NOLOAD result is not a door verdict while section 3 is open.

Tests: `tests/test_parse_getpos_strict.py` (the a1 garble from a column-layout OCR text, the split number, older
sessions on screen, the angle), `tests/test_door_trip.py` (frames, facing, routes, probes, rejected reads, the a1
GetInCell refusal parsed), `tests/test_qstep_sandbox.py` (`FO4SF_QSTEP_SANDBOX=1`): the a1 garble after the first walk
step (rejected, confirmed by the next read, the door loads by walking: PASS, exactly 2 loads), the garble twice, a
cell form id the console refuses (PASS on the positions, the refusal reported), a route walked from the coc arrival
with no teleport before the first load, the wrong facing on return (FAIL FACING).

## 3. Persistent references and the overlay merge (the a2 NOLOAD)

The question: our persistent references in the overlay world's persistent cell read their unmerged local position
(anchors since 2026-10-11, the door in a1 and a2) and the door did not load 1 m from its merged position. Vanilla
LC172World's persistent COC marker `0010238E` read **merged** in `terrain_A2_lc172` (2026-10-11: offset -500, -2300,
-3.62 from that anchor, and the probes matched its BTD) (**verified**, results.jsonl). Where is the difference?

`scripts/slice/persistent_refs.py` (new, read-only raw walk) on Starfield.esm and our plugins (**verified**):

| | LC172World (vanilla, merged) | OEJP006CaveWorld / DR008World (vanilla cave doors) | FO4TerrainCore.esm / FO4TerrainExp2.esm (ours, unmerged) |
|---|---|---|---|
| persistent cell record flags | 0x400 (+ compression) | 0x400 | **0x0** |
| persistent cell subrecords | DATA 02000000, XCLC (0x7FFFFFFF, 0x7FFFFFFF: no grid), LTMP 0, XCLW FLT_MAX, XILS 1.0 | the same (DR008World: XCLC (0, 0)) | **DATA 02000000 only** |
| the persistent ref | 0010238E COCMarkerHeading: NAME DATA, flag 0x400 | doors 1D2E06 / 2B1F6A: NAME XTEL XLYR XNDP (XSCL) DATA, flag 0x400 | anchor: EDID NAME DATA, flag 0x400; door: EDID NAME XTEL XSCL DATA |
| where | the world's persistent cell | the world's persistent cell | the world's persistent cell |
| WRLD OFST / CLSZ | present | present | **absent** |

- Every one of Starfield.esm's 432 worldspace persistent cells has record flag 0x400 and DATA XCLC LTMP XCLW XILS (267
  with a grid, 124 with the no-grid sentinel, 41 with XCLA/XCLD extras); ours is the only shape without them
  (**verified**, survey of every CELL directly in a world's children group).
- 432 of Starfield.esm's 433 WRLD records have OFST and CLSZ; ours have neither (TerrainOverlays clears them)
  (**verified**).
- Vanilla keeps all 345 XTEL references of its worldspaces in the persistent cell, none in an exterior cell (PR #78
  evidence), and writes the XTEL arrival into an overlay world in that world's **local** frame: the 44 arrivals into
  overlay worlds lie at most 19.6 m (median 12.2 m) from their destination door's local position (**verified**,
  `sf_autoload_door.json`). Our XTELs are written the same way.
- So the storage place and the XTEL frame match vanilla. The difference that stands out is the persistent cell
  record itself. **Supported hypothesis (A):** the engine moves a world's persistent references with the overlay merge
  only when the persistent cell is recognisably one (record flag 0x400 and / or the XCLC sentinel); ours is not, so
  its references stay at their local coordinates, about 2.9 km from the merged cave mouth, which explains a1's local
  getpos, the anchors' local reads and a2's NOLOAD at the merged spot. **Unresolved alternative (E):** the missing
  OFST / CLSZ.

Candidate fixes:

| | Fix | Cost | Status |
|---|---|---|---|
| A | The slice plugin's override of the world's persistent cell takes the vanilla record shape: `SliceDoor build` with `"persistent_cell": {"template_world": "LC172World"}` copies LC172World's persistent cell record (flag 0x400, DATA, XCLC sentinel, LTMP, XCLW, XILS) under our master's FormKey. Built and checked: the raw walk shows `0x400 DATA XCLC LTMP XCLW XILS` with the template's bytes; `SliceDoor check` adds "persistent cell equals LC172World's persistent cell record (compression aside)", the flag and the sentinel (33 of 33 on a trial core64c plugin). Only the slice plugin changes: core64c's 46 MB plugin stays as staged, and its own anchor (`02000800`, in the same cell) becomes a free witness | none (plugin only) | **supported**, to be shown in game |
| B | The door as a persistent ref in its exterior cell's persistent children | plugin only | vanilla never does it for worldspaces (0 of 345); probed, not used |
| C | Temporary refs in exterior cells: the 648,358 core64c objects stand merged (roof drops) | none | **verified** for statics; a load door must be persistent (the CK makes linked doors persistent), so not a door fix; probed as the control |
| D | Write the door at local + the measured offset (-1200, -2700) | plugin only | fallback only: it depends on the offset staying the same and double-shifts once A works; the XTEL arrival frame question stays |
| E | WRLD OFST / CLSZ | a TerrainOverlays change and a core64c rebuild | **unresolved**; next if A fails |

`SliceDoor build` also takes `"probes"`: XMarkers in an exterior cell, persistent (its persistent children, B) or
temporary (C). With the door (A) and core64c's anchor (A) they make **the discriminating test**, read by the door_trip
step itself right after the coc arrival, before any walk (`probes` in plan.json, `door_read` for the door):

| ref (load-order bytes supported: FO4TerrainCore 02, Mars 03, FO4Port 04, the slice 05) | storage | merged means |
|---|---|---|
| `05000800` the door | persistent cell, vanilla-shaped (A) | A works for the door |
| `02000800` core64c's anchor | persistent cell, vanilla-shaped by the override (A) | A works for a plain XMarker as well |
| `05000802` probe | exterior cell (-10, 11), persistent children (B) | B would work |
| `05000803` probe | exterior cell (-10, 11), temporary (C) | the control: should read merged |

Reading: door and anchor merged -> A is the fix (then the walk decides the door); both local and B merged -> move
the door to B; all local except C -> E next. Vanilla control in the current setup: `C:\Modding\staging\merge_ctrl_lc172`
(terrain_A2_lc172's entry cut to two points: coc LC172Ext01, anchor 0010238E), queue
`C:\Modding\testqueue\merge_ctrl_lc172` (vanilla only, nothing installed, one fresh launch, a few minutes).

Reproduce:

```powershell
$py = 'C:\Modding\venv-render\Scripts\python.exe'
& $py scripts\slice\persistent_refs.py <Starfield Data>\Starfield.esm --worlds LC172World,OEJP006CaveWorld,DR008World --refs 10238E,1D2E06,2B1F6A
& $py scripts\slice\persistent_refs.py C:\Modding\staging\terrain_core64c\FO4TerrainCore.esm --worlds FO4Core_Commonwealth --refs 000800
& $py -m unittest tests.test_parse_getpos_strict tests.test_door_trip tests.test_persistent_refs
$env:FO4SF_QSTEP_SANDBOX = '1'; & $py -m unittest tests.test_qstep_sandbox.QstepDoorSandboxTests
```

## 4. Unknowns

1. Whether fix A moves persistent refs in game (section 3); whether the XTEL arrival into our overlay then gets the
   merge offset (the out leg's UNMERGED / REMERGED).
2. Whether `player.GetInCell <form id>` resolves our cell (not typed unless a plan gives `inside.cell_id`).
3. The GetAngle reply format (a missing heading makes the trip NOFACING, never PASS).
4. How often strict reads fail in the cave mouth (the O2 dial over the console lines): a run with many unread steps
   stops its walk early (walk stopped: position unread) and only the last try can load (NEARONLY).
5. Whether an automatic door fires for a player teleported into its range, or only for one walking in (a2 stood in
   range after a teleport; with A unshown, a2 cannot tell).
