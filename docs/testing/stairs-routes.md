# Stairs: where the player got stuck, and why (2026-10-13, Claude)

Owner question: the player gets STUCK on a family of converted FO4 stairs (batch_full 0002, 0003, 0006, 0007, 0021,
0022 in BostonPublicLibrary02; supervised_1011 0010 in Vault114). Is it the conversion or the test?

**Answer: the tests.** The converted collision of every stair involved is FO4's own (verified, section 2); each failing
route started or walked where Fallout 4's own collision does not let a player through: in a 0.49 m slot between a wall
and a rail, under a floor slab, against a fallen floor chunk or rebar, 2 m past a top that ends in a collapsed floor, or
on a 0.15 m "flight". `scripts/game/routes.py` now walks every lane offline (`src/fo4sf/walksim.py`) before it writes a
route, and places tilted references the way FO4's precombines do. No converter change: the pinned build's meshes and
plugin stay as they are; only the route files change (`C:\Modding\staging\stairs_fix`).

Evidence labels as in [docs/ai/research-log.md](../ai/research-log.md). Offline checks are not in-game acceptance: the
new routes still need their run (section 5).

## 1. Each failing test: where the player stopped, and what is there

Positions are metres in cell space (in-game OCR reads from `obs.json`; collision from the FO4 archives and from the
pinned build `integ_1011`, build `2470f876`, placed per reference). Screenshots (`r<k>.png`) look up at the ceiling in
all of these runs and show nothing of the steps; the evidence is the reads and the collision.

| test | stair (ref) | read start -> end | where it stopped and why | class |
|---|---|---|---|---|
| batch_full 0006 | BldDecoSmStairs01 `0EBEDE` | 25.58 41.86 1.87 -> 25.58 41.79 1.88 (0.07 m) | Route on the helper's centre line x 25.60 starts on the landing (BldDecoSmFlrOnly01 `0F0289`, z 1.83) in a **0.49 m slot** between the wall BldDecoMdWall01 `0EBEEB` (face x 25.34, 0.26 m away, up to z 3.66) and the rail BldDecoSmRailStraightShort01 `0F02AD` (x 25.83-26.06, z 1.83-2.74). The wall stands on the stair's lower half; debris piles `10122E`, `10122F`, `101236`, `23DD8B` lie on the treads. The player was not pushed out of the slot and never moved. | route |
| batch_full 0007 | BldDecoSmStairs01 `0EBEE3` | 32.93 41.86 1.86 -> 32.93 41.80 1.87 | Mirror of 0006: wall `0EBEE8` face x 33.17, rail `0F02AC` x 32.46-32.69, slot 0.48 m. | route |
| batch_full 0002 | BldDecoSmStairs03 `0EBECE` (rot 90) | 26.25 27.42 4.03 -> 24.35 27.23 5.58 | Start at the flight's foot (z 3.8 + 0.3) **under the gallery floor** BldDecoSmFlrOnly01 `0EBEB4` (z 5.49, 1.69 m over the foot); nothing under the foot but the converted helper's toe. The capsule at the teleport point overlapped the wall plug BldDecoBgWallPlugBBotDblDoor01 `1828D7` (face y 27.77, 0.11 m from the lane, bottom z 5.49); the player was read 0.47 m south of the teleport point, its edge at that face. It climbed the helper, was lifted through the one-sided slab and stopped standing on it. Above the slab the flight is split lengthwise by that wall with a closed static double door (BldWoodPDblDoorStatic01, model BldWoodPDbDoorLoad01, `1828D6`) and the pillar `1828D9` (x 23.34-24.20) standing on the treads; the free half's top ends at 0.9 m of void (x 20.7-21.5) before the next floor. | route (FO4: no usable lane) |
| batch_full 0003 | BldDecoSmStairsBlock03 `0EBED6` | 26.26 31.54 4.02 -> 24.39 31.13 5.55 | Same start under the gallery slab (`0EBEDA`, z 5.49). Lifted onto the slab, stopped on it where the helper comes out of it. The mirrored `0EBED7` (0004) made the same lift and passed (rise 3.75): a lift through a slab is fragile (1 of 3). | route |
| batch_full 0021 | BldDecoSmStairsShort01 `0F032C` | -10.97 46.39 11.30 -> -11.19 47.12 11.51 (0.75 m) | A fallen floor chunk BldDecoSmFlrPlatChunk01 `0F0279` (rot -81.0 / -2.8 / 266.5, scale 1.18) leans across the whole flight from y 47.69 (x -13.14 to -9.26, z 10.0-14.1); brick rubble `15761C` lies in front of it. The player stopped 0.57 m before the chunk, 0.44 m from the rubble; the offline walk stops at the chunk. Every lane is blocked in FO4's collision. | route (FO4: no usable lane) |
| batch_full 0022 | BldDecoSmStairsShort01 `0F032D` | -14.63 51.53 12.80 -> -14.40 45.07 11.56 (FALL) | The climb worked; `walk_ms` 1410 (old formula, 4 m/s + 1 m) walked 6.5 m, 2 m past the top (z 14.63), off the edge into the collapsed floor onto chunk `0F0274` (offline walk ends at -14.63 45.03 11.58). | route (walk too long) |
| supervised_1011 0010 | CinderBlockStairs02 `170F9F` (Vault114) | 20.34 59.23 -20.69 -> 19.92 56.56 -20.62 | Two cinder blocks 62 % buried in the cave floor: 0.15 m of rise is left. The player walked 2.7 m over them; "STUCK" is rise 0.10 against a need of 0.12. | route (no stairs test) |
| batch_full 0423 (also STUCK) | BldWlpSmStairsBlockShort01 `09992E` (FortHagen02) | -> -4.29 -25.40 -13.67 | A rebar chunk BldConcRebarChunk03 `099CC8` (tilted, layer 3) lies on the flight; offline walk stops at -4.28 -25.39 -13.59. Other lanes: fallen floor chunks `099C40`, `099C37`. | route (FO4: no usable lane) |
| batch_full 0136 (FALL) | HitFloorEdgeStairsTop01 `076977` (Cambridge) | 31.06 88.62 3.70 -> 33.61 92.71 4.01 | The "Top" piece's foot is mid-air over the Mid piece's side: the teleport point (z 5.23) was 1.5 m over the floor under it; the player dropped and walked under the stairs. | route |

The 12 stairs tests that passed in BostonPublicLibrary02 (0001, 0004, 0005, 0008, 0009, 0010, 0012, 0016-0020) are the
same models (BldDecoSmStairs01 / Block01 / Block03, BldBrickSmStairsHalfBlockShort01) on lanes with nothing in the way:
the model is not what differs.

## 2. The conversion of these stairs is FO4's (verified)

- **Per model:** the 16 stair models involved re-converted with this branch's converter into
  `stairs_fix\reconvert` read back (`fo4sf.sfbodies`) **body for body identical** to `integ_1011` (same layers, same
  triangles to 0.1 mm). Their bodies match FO4's: same layer (1 mesh, 31 helper), same tread heights (e.g.
  BldDecoSmStairs01: 16 treads of 0.229 m; BldDecoSmStairs03 / Block03: 11 of 0.333 m), same bounds. The only change
  is the intended one: helpers steeper than 40 degrees are flattened (BldDecoSmStairs03 / Block03 / BldWoodBSmStairs03
  45.7 -> 40.3, toe 0.78 m further out; ShackStairs01 45.0 -> 39.7; BldWoodPSmStairsHalfTiny03 46.0 -> 41.1).
  Each helper model alone, floors at its foot and top, climbs fully in the offline walk (rise = its height).
- **Per scene:** within 4-5 m of the failing lanes, every neighbour's converted collision has FO4's bounds to 2 cm,
  except the flattened helpers; no neighbour fell back to a guessed box.
- **Placement:** the references are placed by the game from FO4's angles (the plugin writes them unchanged). Our
  offline placement had the rotation order wrong for tilted references (next section); that only affected our tools.

## 3. What was wrong in the tools

- **Rotation order (verified):** `routes.ref_matrix` composed a reference's rotation X first (Rz Ry Rx). FO4's own
  precombined physics places tilted references Z first, `R = Rx(-x) Ry(-y) Rz(-z)`: in BostonPublicLibrary02's
  precombine 312 tilted references match only that order, 3 only the old one, 85 both; the debris piles and floor
  chunks on the library stairs match 93-100 % of their vertices against 0-13 %. The old order put those debris piles
  up to about 1 m higher over the treads than FO4 has them. Pure Z rotations (most stairs, doors and walls) are the
  same either way.
  `exterior.ref_matrix` and `PluginSpike.RotateOffset` still use the old order (not changed here: follow-up).
- **Start buried under a slab:** a floor up to 1.5 m over the ramp counted as burying it; the gallery slab is 1.69 m
  over the BldDecoSmStairs03 foot. Now up to the player's height (1.8 m), and a flight hanging over nothing starts where
  the floor it ends on covers it.
- **No check of the lane:** start and walk were never checked against the neighbours. Walls, rails, doors, debris and
  fallen chunks on or beside a flight are FO4 level design (the library is a ruin).
- **Walk length:** `250 + 1000 (run + 1) / 4` ms walked about 2 m past the top (the player runs 4.4-4.9 m/s from the
  first 631 ms on).
- **Trivial flights:** a 0.15 m remainder of a buried flight was planned as a stairs test.
- **Neighbours far from their origin were missed:** a model's collision can lie 16-22 m from its origin
  (VltGearDoorStairs01, precombined `CM*.NIF`); the 6 m margin left them out. Now each model's reach is used.

## 4. The fix (route planner) and the offline proof

`scripts/game/routes.py` plans every stairs route through `fo4sf.walksim`, over FO4's own collision of the stair and
its neighbours (compound furniture included, steep helpers flattened as the converter does, doors open by default and
movable objects left out, references placed Z first):
1. the foot moves to where the ramp comes out of the neighbours' floors (slab up to 1.8 m over it);
2. lanes across the ramp, the centre first, then 0.25 m steps, first with 0.1 m more room than the 0.35 m capsule
   needs, then without it (marked `"tight"`); the start stands 0.8 m before the foot, or 0.5 / 0.3 m when that spot is
   taken or has no floor;
3. a lane is kept when the player stands free at the start (no push-out needed), is not lifted through a floor, climbs
   at least 0.8 of the flight, and walking 0.5 m further would not fall or stand over the edge of a drop; the walk ends
   0.6 m past the top, or 0.2 m / right at the top when a drop is that close;
4. a flight rising less than 0.2 m above its surroundings is no stairs test;
5. a stair with no such lane is skipped with the reason (`skipped_stairs_without_ramp`, and per stair in the new
   `stairs_checked` list).
Route files gain `lane`, `sim_end` (where the offline walk ended), `emerges` and `tight`; `route_run.ps1` and the
judge ignore them.

**The offline walk against the game (supported hypothesis):** replaying the 64 decided in-game stairs results
(batch_full, supervised_1011) on the converted collision, it gives the game's verdict for 59. The 5 others: the
0.15 m cinder blocks (judge artefact, now no test); 0003's lift through the slab (the planner refuses lifts); 0010 just
under the threshold (rise 2.96 of 2.99; game 3.14); 0136's start 1.5 m over the floor (the planner refuses such
starts); 0287, whose start the game pushed up onto toppled file cabinets (the planner picks a free lane instead). It
puts the stop on the same object as the game for 0006 / 0007 (start wedged), 0021 (floor chunk), 0022 (end within
0.25 m), 0423 (rebar, end within 0.1 m).

**New routes for the 16 cells** (`--max 400`, `stairs_fix\routesfull_*.json`): 214 stairs routes (226 before).
178 keep their start and heading (all get the new `walk_ms`), 36 moved, 12 skipped, 0 added. Every one of the 214
replays as PASS on the converted collision of `integ_1011` (start push-out allowed, bare capsule); 1 is tight.
- Stairs with an in-game PASS before: 54 of 54 still planned (41 unchanged starts, 13 moved).
- In-game FAIL before: 0006 / 0007 move to lanes x 26.60 / 31.91 east of the rails; 0003 / 0004 start on the gallery
  slab (z 5.79) and climb 2.05 m to z 7.54; 0022 keeps its start, walks 965 ms instead of 1410 (ends 0.6 m past the
  top); 0136 moves to lane +0.75 m on a floor. Skipped with the reason, because FO4's collision has no lane: 0002
  `0EBECE` (wall, load door, pillar; the free half's top ends over void), 0021 `0F032C` (floor chunk), 0423 `09992E`
  (rebar and floor chunks), supervised 0010 `170F9F` (rises 0.15 m).
- Skipped that never ran: library `0EBECA` (as `0EBECE`), Museum `1609EF` (wall at the start, ceiling over the
  flight), Parsons RWResStairs02 x4 (no floor at the start: the foot is in ground the interior does not have), Vault75
  `0C22AA` (a concrete floor `0C22AE` closes the top), Vault114 VltGearDoorStairs01 `0BA406` (see section 6).

## 5. In-game plan (not run)

**Build:** no new plugin or archive. The meshes and FO4Port.esm of `integ_1011` (build `2470f876`) are what the
routes were checked against, so a queue keeps that build pinned and takes the route files from `stairs_fix`
(`testqueue.py plan --routes-dir`, new). If the door overlay `integ_1011_doors` becomes the pinned build first, plan
with `--staging` that folder: the route files are computed from FO4 data and the cell exports, which the overlay keeps.

```powershell
$py = 'C:\Modding\venv-render\Scripts\python.exe'
# from a worktree of this branch: the stairs of the 16 cells, routes from stairs_fix
& $py scripts\game\testqueue.py plan --staging C:\Modding\staging\integ_1011 --out C:\Modding\testqueue\stairs_fix_1013 `
  --kinds stairs --routes-prefix routesfull_ --routes-dir C:\Modding\staging\stairs_fix
& $py scripts\game\testqueue.py run --queue C:\Modding\testqueue\stairs_fix_1013 --wait-for-idle --refocus
```
To regenerate the routes (a later routes.py, another build): `routes.py --fo4-data <FO4 Data> --cell-json
<staging>\<cell>.json --manifest <staging>\manifest.json --formids <staging>\formids.json --max 400 --out
<dir>\routesfull_<cell>.json` for each cell (about 10 s per cell, 160 s for 16).

Tests that verify it (214 stairs tests, about 85 s each, 5 hours): first the former failures and their controls,
- BostonPublicLibrary02: `0EBEDE`, `0EBEE3` (expect PASS, rise >= 2.99 from the landing on the east / west lanes),
  `0EBED6`, `0EBED7` (expect PASS, 1.64 / 1.61 from the gallery slab), `0F032D` (expect PASS, no FALL), `0EBEDD`,
  `0EBEE5`, `0EBEE7` (moved, passed before), `0EF6A4`, `0EF797`, `0EF798` (never reached before);
- CambridgePolymerLabs01 `076977` (was FALL), the moved `076978`, `09837F`, `149E0E`, `149E15`, `16D87C`;
- controls unchanged from batch_full: BostonPublicLibrary02 `0EBECC`, `0EBEF2`, `0F0280`, `0EF8F8`; Rexford
  `0CB908`-`0CB9E2`; FortHagen01 `13115A`; FortHagen02 `0998C5`.
A new FAIL on a route `sim_end` says climbs is a disagreement with the offline walk: compare the read end with
`sim_end` and the lane's neighbours before changing anything.

## 6. Blast radius and what is left

- **Routes (16 cells):** section 4. The rotation fix also moves the neighbours of every tilted reference in the
  planner's ground and walk scene; door routes use only Z rotations here and are unchanged.
- **Converter, flattened helpers:** 24 placements of 14 models in the 16 cells have an FO4 helper steeper than 40
  degrees that the converter flattens; the toe moves 0.12-1.06 m further out (ScaffFrameSladder01 / 02 1.06 m,
  BldDecoSmStairs03 / Block03 / BldWoodBSmStairs03 / BldWoodBSmStairsHalf03 / BldConcSmStairsBlock03 0.78 m). For 17
  the toe lies on a floor or under a mound. The other 7: the library's 4 Stairs03 / Block03 toes hang in the void under
  the gallery (nobody gets there); the 2 V111HallStairs01 toes are over no floor this check finds, although the
  planner's walk stands at their foot and both flights pass in game (unresolved which piece the check misses); the
  tip of one ScaffFrameSladder02 (Parsons `10D351`) is 3.1 m over the floor beyond a scaffold edge. Supported
  hypothesis: harmless where nobody crosses the foot of the flight; a toe 0.3-1 m out is a low wedge a player walking
  across in front of the stairs could catch. (HitFloorThruFullEdge02DblRampOnly and ShackBridgeFree01 have 82-90
  degree "helpers" the flattening leaves alone.)
- **Not solved here: helper-less stairs with tall risers.** Vault114's VltGearDoorStairs01 (no stair helper, treads
  0.29-0.31 m, one 0.58 m step) was STUCK at 1.41 of 3.22 m on 2026-10-09; Starfield's controller did not climb 0.30 m
  treads without a helper (V111HallStairs01, 2026-10-08). The planner now skips it (the offline walk stops on its
  steps). Unresolved: a synthesized helper ramp for such stairs in the converter, with an in-game check. It is the only
  helper-less stair the planner routes in the 16 cells.

## Files

- `scripts/game/routes.py`, `src/fo4sf/walksim.py`, `scripts/game/testqueue.py` (`plan --routes-dir`).
- Tests: `tests/test_walksim.py`, `tests/test_routes_stairs_lanes.py`, `tests/test_testqueue.py`
  (`test_plan_takes_routes_planned_again_from_another_folder`).
- Staging (local, not in git): `C:\Modding\staging\stairs_fix` (route files, `reconvert\` with the 16 re-converted
  stair models, `offline\` with the calibration, old-vs-new comparison, replay, read-back, toe scan and rotation check).
