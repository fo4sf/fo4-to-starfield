# Stairs: where the player got stuck, and why (2026-10-13, Claude; corrected after QA on PR #111)

Owner question: the player gets STUCK on a family of converted FO4 stairs (batch_full 0002, 0003, 0006, 0007, 0021,
0022 in BostonPublicLibrary02; supervised_1011 0010 in Vault114). Is it the conversion or the test?

**Answer: the tests for 0006, 0007, 0021, 0022 and supervised 0010** (and for batch_full 0423 and 0136): each of those
routes started or walked where Fallout 4's own collision does not let a player through (a 0.49 m slot between a wall
and a rail, a fallen floor chunk across the flight, 2 m past a top that ends in a collapsed floor, a 0.15 m "flight",
rebar on the flight, a start 1.5 m over the floor). **For 0002 and 0003 it is unresolved, and the conversion is a live
suspect** (section 1a): both players stopped on the gallery slab 0.01-0.05 m before the place where the converter's
flattened stair helper comes up through that slab, 0.46-0.50 m from where FO4's own helper does. That place exists
only in the converted build. The first version of this page said the slab lift explained them; QA showed it does not
(the lift had worked; the player stopped 1.3 m later).

What changed: `scripts/game/routes.py` walks every lane offline (`src/fo4sf/walksim.py`) before it writes a route,
places tilted references the way FO4's precombines do, and now marks on each route what the offline walk cannot vouch
for (a converted helper crossing, movable objects on the lane) and plans probes that tell the 0002 / 0003 hypotheses
apart. No converter change yet: the pinned build's meshes and plugin stay as they are; only route files change
(`C:\Modding\staging\stairs_fix_1014`; the first pass's `stairs_fix` is superseded).

Evidence labels as in [docs/ai/research-log.md](../ai/research-log.md). Offline checks are not in-game acceptance: the
new routes and probes still need their run (section 5).

## 1. Each failing test: where the player stopped, and what is there

Positions are metres in cell space (in-game OCR reads from `obs.json`; collision from the FO4 archives and from the
pinned build `integ_1011`, build `2470f876`, placed per reference). Screenshots (`r<k>.png`) look up at the ceiling in
all of these runs and show nothing of the steps; the evidence is the reads and the collision.

| test | stair (ref) | read start -> end | where it stopped and why | class |
|---|---|---|---|---|
| batch_full 0006 | BldDecoSmStairs01 `0EBEDE` | 25.58 41.86 1.87 -> 25.58 41.79 1.88 (0.07 m) | Route on the helper's centre line x 25.60 starts on the landing (BldDecoSmFlrOnly01 `0F0289`, z 1.83) in a **0.49 m slot** between the wall BldDecoMdWall01 `0EBEEB` (face x 25.34, 0.26 m away, up to z 3.66) and the rail BldDecoSmRailStraightShort01 `0F02AD` (x 25.83-26.06, z 1.83-2.74). The wall stands on the stair's lower half; debris piles `10122E`, `10122F`, `101236`, `23DD8B` lie on the treads. The player was not pushed out of the slot and never moved. | route (verified offline) |
| batch_full 0007 | BldDecoSmStairs01 `0EBEE3` | 32.93 41.86 1.86 -> 32.93 41.80 1.87 | Mirror of 0006: wall `0EBEE8` face x 33.17, rail `0F02AC` x 32.46-32.69, slot 0.48 m. | route (verified offline) |
| batch_full 0002 | BldDecoSmStairs03 `0EBECE` (rot 90) | 26.25 27.42 4.03 -> 24.35 27.23 5.58 | Teleport point 26.26 27.89 4.10, at the flight's foot **under the gallery floor** BldDecoSmFlrOnly01 `0EBEB4` (z 5.49). There the capsule's top overlaps the closed static load door BldWoodPDbDoorLoad01 `1828D6` that stands on the slab in the wall plug `1828D7` (door face y 28.00, 0.11 m north of the lane, bottom z 5.49); the game read the start 0.47 m south. The player came up onto the slab and **stopped 0.01 m before the converted helper's crossing of the slab** (x 24.34; FO4's at 23.89): section 1a. | **unresolved** (1a) |
| batch_full 0003 | BldDecoSmStairsBlock03 `0EBED6` | 26.26 31.54 4.02 -> 24.39 31.13 5.55 | Same approach under the gallery slab (BldDecoSmFlrOnly05 `0EBEDA`, z 5.49), no push-out. Came up onto the slab and **stopped 0.05 m before the converted crossing** (x 24.34; FO4's 23.89). The mirrored `0EBED7` (0004) came the same way and passed its crossing (rise 3.75). | **unresolved** (1a) |
| batch_full 0021 | BldDecoSmStairsShort01 `0F032C` | -10.97 46.39 11.30 -> -11.19 47.12 11.51 (0.75 m) | A fallen floor chunk BldDecoSmFlrPlatChunk01 `0F0279` (rot -81.0 / -2.8 / 266.5, scale 1.18) leans across the whole flight from y 47.69 (x -13.14 to -9.26, z 10.0-14.1); brick rubble `15761C` lies in front of it. The player stopped 0.57 m before the chunk, 0.44 m from the rubble; the offline walk stops at the chunk (0.61 m across and 0.69 m higher than the game's stop: not the same place). Every lane is blocked in FO4's collision. | route (FO4: no usable lane; verified offline) |
| batch_full 0022 | BldDecoSmStairsShort01 `0F032D` | -14.63 51.53 12.80 -> -14.40 45.07 11.56 (FALL) | The climb worked; `walk_ms` 1410 (old formula, 4 m/s + 1 m) walked 6.5 m, 2 m past the top (z 14.63), off the edge into the collapsed floor onto chunk `0F0274` (offline walk ends at -14.63 45.03 11.58). | route (walk too long; verified offline) |
| supervised_1011 0010 | CinderBlockStairs02 `170F9F` (Vault114) | 20.34 59.23 -20.69 -> 19.92 56.56 -20.62 | Two cinder blocks 62 % buried in the cave floor: 0.15 m of rise is left. The player walked 2.7 m over them; "STUCK" is rise 0.10 against a need of 0.12. | route (no stairs test; verified) |
| batch_full 0423 (also STUCK) | BldWlpSmStairsBlockShort01 `09992E` (FortHagen02) | -> -4.29 -25.40 -13.67 | A rebar chunk BldConcRebarChunk03 `099CC8` (tilted, layer 3) lies on the flight; offline walk stops at -4.28 -25.39 -13.59. Other lanes: fallen floor chunks `099C40`, `099C37`. | route (FO4: no usable lane; verified offline) |
| batch_full 0136 (FALL) | HitFloorEdgeStairsTop01 `076977` (Cambridge) | 31.06 88.62 3.70 -> 33.61 92.71 4.01 | The "Top" piece's foot is mid-air over the Mid piece's side: the teleport point (z 5.23) was 1.5 m over the floor under it; the player dropped and walked under the stairs. | route (verified offline) |

The 12 stairs tests that passed in BostonPublicLibrary02 (0001, 0004, 0005, 0008, 0009, 0010, 0012, 0016-0020) are the
same models (BldDecoSmStairs01 / Block01 / Block03, BldBrickSmStairsHalfBlockShort01).

**Correction (QA on PR #111):** the first version of this table said 0002's teleport point overlapped the wall plug
`1828D7` "at face y 27.77" and that the player was pushed out until its edge touched that face, and used that as
evidence for the 0.35 m capsule radius. The overlapping face is the load door `1828D6`'s at y 28.00 (both the
converted and the planner's scene); the game moved the player 0.23 m further than a 0.35 m capsule needs, so the
push-out does not pin the radius (now labelled assumed). The three blockers named for 0002 were at three places:
the door `1828D6` overlaps the old teleport point; the offline walk then pushes the player only 0.25 m (to y 27.64),
where the base of the trash pile TrashPileWall03 `1B0865`, sunk 0.16 m into the slab, stops its first step (the game
had pushed the player to y 27.42 and walked on, so the offline STUCK there is an artefact of the offline push-out); the
planner's own start for this flight, on the slab at x 24.7, overlaps the door `1828D6` and the plank
Shack_Single_PlankLng01 `1015B4`.

## 1a. 0002 / 0003: the stop is where the converted helper comes up through the gallery slab (unresolved)

BldDecoSmStairs03 / StairsBlock03 bridge the 2.05 m from the gallery (z 5.49) to the floor above (7.54), their lower
half under the gallery slab. The stair helper is a 0.095 m thick slab; its top face is 44.7 degrees in FO4 and 39.3 in
the converted build (the converter's flattening moves its bottom edge 0.78 m out). It pierces the gallery slab: the
top face comes up through the slab top at

| stair | FO4's helper | flattened as the planner models it | converted build (read back) | in-game stop | stop to converted / FO4 |
|---|---|---|---|---|---|
| `0EBECE` (0002) | x 23.89 | 24.32 | 24.34 | 24.35 27.23 5.58 | 0.01 m / 0.46 m |
| `0EBED6` (0003) | 23.89 | 24.32 | 24.34 | 24.39 31.13 5.55 | 0.05 m / 0.50 m |
| `0EBED7` (0004, PASS) | 34.65 | 34.22 | 34.20 | 37.00 32.34 7.55 (top) | passed it |

(verified: `offline\crossings_library.txt`; the crossing is the same on every lane of the flight). Both stops are the
capsule's centre on the slab just before the crossing, with its front half over the rising helper; the reads are
0.06-0.09 m above the slab, where flat-floor stops read +0.01-0.02 m (0001, 0004), as if the capsule had started up
the helper and stopped. The lift onto the slab had worked in all three runs: the offline walk of the old 0003 route
lifts the player onto the slab at x 25.66, 0.6 m after the start, then walks 1.3 m on the slab to the crossing and
climbs on (`offline\crossings_library.txt`). From the game's own stop points the offline walk climbs freely to z 7.54:
**the offline walk cannot predict this stop.**

Other converted helper crossings that players walked into from a floor in game: 7 of 7 passed, supervised_1011 0000 /
0001 and batch_full 0282 / 0284 / 0285 / 0293 (Fort Hagen BldWoodPSmStairsHalfTiny03 / BlockTiny03: crossing moved
0.08-0.18 m, converted top face 37.0 degrees, 0.02-0.48 m above its toe) and batch_full 0248 (Diamond City
ShackStairs01 `0C6B00`: moved 0.54 m, 39.7 degrees, 0.10 m above its toe). None is as deep as the library's (1.63 m
above the toe), and only 0248 is as steep.

Live hypotheses (neither verified):
- **H1, conversion:** Starfield's controller stops at the converted helper's crossing of the gallery slab (a place the
  flattening moved and made 39.3 degrees). For: both stops lie 0.01-0.05 m before it, 0.46-0.50 m from FO4's. Against:
  0004 passed its mirrored crossing; 7 of 7 floor approaches to other converted crossings passed.
- **H2, approach:** coming from under the slab (the old routes' teleport point; FO4's level design never puts a player
  there), the lift onto the slab leaves the player in a state that stops at the next slope. For: all three under-slab
  approaches were these library runs (2 of 3 stopped); every floor approach passed. Against: nothing direct.

If H1 holds, the fix belongs in the converter (for example: flatten a helper without moving where it comes out of a
floor it pierces, or clip it at that floor), with an in-game check. The tests that tell H1 from H2 are in section 5.

## 2. The conversion of these stairs is FO4's, except the flattened helpers (verified)

- **Per model:** the 16 stair models involved re-converted with this branch's converter into
  `stairs_fix\reconvert` read back (`fo4sf.sfbodies`) **body for body identical** to `integ_1011` (same layers, same
  triangles to 0.1 mm). Their bodies match FO4's: same layer (1 mesh, 31 helper), same tread heights (e.g.
  BldDecoSmStairs01: 16 treads of 0.229 m; BldDecoSmStairs03 / Block03: 11 of 0.333 m), same bounds. The only change
  is the intended one: helpers steeper than 40 degrees are flattened (BldDecoSmStairs03 / Block03 / BldWoodBSmStairs03
  45.7 -> 40.3 end to end, top face 44.7 -> 39.3, toe 0.78 m further out; ShackStairs01 45.0 -> 39.7;
  BldWoodPSmStairsHalfTiny03 46.0 -> 41.1). Each helper model alone, floors at its foot and top, climbs fully in the
  offline walk (rise = its height). That the flattening moves where a helper comes out of a floor it pierces is the
  open question of section 1a.
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
  same either way. PR #102 (core64c's northeast probe) found the same order independently on a far larger set: the
  rotation matrices FO4's precombines store equal Z first for 146,463 of 146,728 tilted references in 4,497 cells.
  In game, 0005's start read z 3.07 at 29.26 39.02, which fits Z-first debris about 0.25 m over the ramp (the old
  order's start was z 3.84; QA on PR #111). `exterior.ref_matrix`, `navmesh_points.py` and `PluginSpike.RotateOffset`
  still use the old order (not changed here; #102 lists them as its follow-up).
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

## 4. The planner, and what the offline walk shows

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
4. a lane whose capsule would touch a movable object (within 0.45 m of the walk line) is taken only when no other lane
   with the same room avoids one (new after QA);
5. a flight rising less than 0.2 m above its surroundings is no stairs test;
6. a stair with no such lane is skipped with the reason (`skipped_stairs_without_ramp`, and per stair in
   `stairs_checked`).

Route entries carry `lane`, `sim_end` (where the offline walk ended), `emerges` (where the ramp comes out of the
neighbours' floors, as a fraction of it), `tight`, and, for what the walk cannot vouch for, `helper_crossing` (the walk
meets a converted helper coming up through the floor it starts on, moved from FO4's: `at`, `fo4_at`, `moved`, `depth`,
`slope`) and `movable_near` (movable objects within 0.8 m of the walk line, with their distance). `route_run.ps1` and
the judge ignore them. `--probes-out` writes probe routes for each route with a helper crossing (section 5).

**The offline walk against the game (supported hypothesis as a model):** `scripts/game/stairs_calib.py results`
replays the 64 decided in-game stairs results of batch_full and supervised_1011 on the converted collision of
`integ_1011` (start push-out allowed, bare capsule) and counts a stop as agreeing only when the offline walk also ends
within 0.75 m across and 0.5 m in height of the game's read (`offline\calib_converted.txt`):

| scene | same verdict | same verdict and place | same verdict, another place | another verdict |
|---|---|---|---|---|
| converted collision of `integ_1011` | 59 | **57** | 2 (0002, 0021) | 5 |
| the planner's scene (FO4 collision, flattened helpers) | 60 | 58 | 2 (0002, 0021) | 4 |

The first version of this page counted 59 of 64 as agreements, 0002 among them; the offline walk stops 0002 at its
start (the artefact above), 1.95 m from where the game stopped, so that was an agreement for the wrong reason. The
other verdicts: 0003 (game STUCK at the converted crossing; the walk climbs it), 0010 (`0EBEE7`, rise 2.96 of 2.99;
game PASS 3.14), 0136 (start 1.5 m over the floor; the planner refuses such starts), 0287 (the game pushed the start
onto toppled file cabinets; the planner picks a free lane instead), supervised 0010 (the 0.15 m cinder blocks, now no
test). The same place as the game: 0006 / 0007 (start wedged), 0022 (end within 0.25 m), 0423 (rebar, within 0.1 m);
for 0021 the walk stops at the floor chunk, the game 0.57 m before it. Movable objects kept in the scene change none
of these counts.

**New routes for the 16 cells** (`--max 400`, `stairs_fix_1014\routesfull_*.json`): 214 stairs routes (226 in the
pinned build): 175 keep their start and heading (all get the new `walk_ms`), 39 moved, 12 skipped, 0 added. Against
the first pass of this branch, 5 lanes moved away from movable objects (`0EBEDD`, FortHagen01 `0C1D8A`, Parsons
`10D230`, Vault111 `0AD64B`, Vault95 `130691`). `stairs_calib.py routes` replays all 214 as PASS on the converted
collision of `integ_1011`. That is a consistency check, not evidence that the routes are right: the planner keeps only
lanes this walk climbs, and the replay is looser (start push-out allowed, bare capsule).
- Stairs with an in-game PASS before: 54 of 54 still planned; 41 with the start that passed, **13 moved, which makes
  them new tests, not controls**: library `0EBED7`, `0EBEDD`, `0EBEE5`, `0EBEE7`, `0EF8FD`; Cambridge `076978`,
  `09837F`, `149E0E`, `149E15`, `16D87C`; FortHagen01 `0C1D8A`, `131159`; Vault114 `1BDD03`. Their old routes are
  replayed as regression controls (section 5). Examples: `0EBEDD` moved from its mid-ramp start (y 39.02) to the shared
  landing (y 41.93), lane 0.5 m west of the boxes of papers `1AB9CB` / `1AB9CC` its walk would cross; `131159` moved to
  lane +1.0 and passes 0.17 m from the movable skeleton `131146`, which spawns standing and topples.
- In-game FAIL before: 0006 / 0007 move to lanes x 26.60 / 31.91 east / west of the rails; 0007's lane runs over the
  box of papers `1AB9BF` (0.01 m; no lane of that flight with the planner's 0.1 m of room avoids it), 0006's passes 0.49 m from `1AB9BE`. 0003 / 0004
  start on the gallery slab (z 5.79) 0.37 / 0.28 m before the converted crossing (the capsule's front within 0.07 m of
  it) and climb 2.05 m to z 7.54 (section 1a: their
  result is the test of H1). 0022 keeps its start, walks 965 ms instead of 1410 (ends 0.6 m past the top); 0136 moves
  to lane +0.75 m on a floor. Skipped with the reason, because FO4's collision has no lane: 0002 `0EBECE` (door, plank,
  pillar; the free half's top ends over void), 0021 `0F032C` (floor chunk), 0423 `09992E` (rebar and floor chunks),
  supervised 0010 `170F9F` (rises 0.15 m).
- Skipped that never ran: library `0EBECA` (as `0EBECE`), Museum `1609EF` (wall at the start, ceiling over the
  flight), Parsons RWResStairs02 x4 (no floor at the start: the foot is in ground the interior does not have), Vault75
  `0C22AA` (a concrete floor `0C22AE` closes the top), Vault114 VltGearDoorStairs01 `0BA406` (see section 6).
- What the walk cannot vouch for: 11 routes meet a converted helper crossing (library `0EBED6`, `0EBED7`; Diamond City
  `0C6B00`; FortHagen01 `0BB3F6`, `0BB405`, `0BD5E5`, `0BD670`, `0BD781`, `1344C6`; Parsons `10D230`; Vault75
  `0C22AD`); 28 list a movable object within 0.8 m (14 of them moved or new lanes), 9 would touch one because no lane
  of their flight with the same room avoids it (library `0EBEE3`; `0C6B00`; `131159`; Museum `1609F8`; Parsons `10D1D5`; Vault114
  `1BDD03`; Vault75 `0C20F5`, `0C234A`, `0D8690`). That the player pushes such objects aside is a supported hypothesis
  only (research log, 2026-10-10); a STUCK at one of them is not a stairs result.

## 5. In-game plan (not run)

**Build:** no new plugin or archive. The meshes and FO4Port.esm of `integ_1011` (build `2470f876`) are what the
routes were checked against, so the queues keep that build pinned and take the route files from `stairs_fix_1014`
(`testqueue.py plan --routes-dir`). The queue copies the route files it uses into `<queue>\routes` and records their
sha256 (`routes_sha256`), so re-planning `stairs_fix_1014` cannot change how a planned queue runs or is judged. If the
door overlay `integ_1011_doors` becomes the pinned build first, plan with `--staging` that folder: the route files are
computed from FO4 data and the cell exports, which the overlay keeps.

Three queues, planned (no results yet), in this order:

```powershell
$py = 'C:\Modding\venv-render\Scripts\python.exe'
# 1. probes for section 1a (8 tests, ~12 min)
& $py scripts\game\testqueue.py plan --staging C:\Modding\staging\integ_1011 --out C:\Modding\testqueue\stairs_probe_1014 `
  --kinds stairs --routes-prefix routesprobe_ --routes-dir C:\Modding\staging\stairs_fix_1014 --refs 0EBED6,0EBED7,0C6B00
# 2. the old routes, unchanged: the two under-slab runs and the 13 passed routes that moved (14 tests, ~20 min)
& $py scripts\game\testqueue.py plan --staging C:\Modding\staging\integ_1011 --out C:\Modding\testqueue\stairs_replay_1014 `
  --kinds stairs --routes-prefix routesfull_ --refs 0EBED6,0EBED7,0EBEDD,0EBEE5,0EBEE7,0EF8FD,076978,09837F,149E0E,149E15,16D87C,0C1D8A,131159,1BDD03
# 3. the new routes, former failures and controls first (214 tests, ~5 h)
& $py scripts\game\testqueue.py plan --staging C:\Modding\staging\integ_1011 --out C:\Modding\testqueue\stairs_fix_1014 `
  --kinds stairs --routes-prefix routesfull_ --routes-dir C:\Modding\staging\stairs_fix_1014 `
  --first 0EBEDE,0EBEE3,0EBED6,0EBED7,0F032D,076977,0EBEDD,0EBEE5,0EBEE7,0EF6A4,0EF797,0EF798,076978,09837F,149E0E,149E15,16D87C,0EBECC,0EBEF2,0F0280,0EF8F8,0CB908,0CB909,0CB9C1,0CB9C2,0CB9D3,0CB9D4,0CB9E1,0CB9E2,13115A,0998C5
& $py scripts\game\testqueue.py run --queue C:\Modding\testqueue\stairs_probe_1014 --wait-for-idle --refocus
```

**Probes (queue 1, section 1a):** for `0EBED6` and `0EBED7`, three routes each on the centre lane: `through_crossing`
(the new route: start on the slab, the capsule's front within 0.07 m of the converted crossing), `runup` (start on the
slab 1.3 m before the crossing, the run-up 0003 had) and `past_crossing` (start on the helper 0.6 m past the
crossing); for Diamond City `0C6B00`, `through_crossing` and `past_crossing` as a control (it passed in game). Reading:
- a through / run-up route STUCK within about 0.1 m before the crossing while `past_crossing` passes: the crossing
  stops the player, **H1 supported** (a converter change, section 1a);
- through, run-up and past all pass, and the old under-slab route of `0EBED6` (queue 2) stops again: **H2 supported**
  (the old route, not the conversion);
- everything passes, the old route too: the stops do not reproduce; still unresolved (run again);
- `past_crossing` STUCK as well: the helper itself, neither H1 nor H2.

**Expected for queue 3:** the former failures `0EBEDE` / `0EBEE3` PASS from the landing on the lanes east / west of the
rails (supported hypothesis; `0EBEE3`'s lane runs over a box of papers), `0F032D` PASS without the FALL, Cambridge
`076977` PASS; `0EBED6` / `0EBED7` **unresolved** (section 1a; they are the probes' `through_crossing` routes); the 13
moved routes that passed before are new tests (their old routes run in queue 2); the 41 unchanged starts are controls.
A FAIL on a route whose `sim_end` climbs is a disagreement with the offline walk: compare the read end with `sim_end`,
`helper_crossing` and `movable_near` before changing anything.

To regenerate the routes (a later routes.py, another build): `routes.py --fo4-data <FO4 Data> --cell-json
<staging>\<cell>.json --manifest <staging>\manifest.json --formids <staging>\formids.json --max 400 --out
<dir>\routesfull_<cell>.json --probes-out <dir>\routesprobe_<cell>.json` for each cell (about 10 s per cell), into a
**new** folder. To check them: `stairs_calib.py routes --routes-dir <dir> --staging <staging> --fo4-data <FO4 Data>`;
to check the walk against new in-game results: `stairs_calib.py results --queue <queue> [--queue ...] --staging
<staging> --fo4-data <FO4 Data>`.

## 6. Blast radius and what is left

- **Routes (16 cells):** section 4. The rotation fix also moves the neighbours of every tilted reference in the
  planner's ground and walk scene; door routes use only Z rotations here and are unchanged.
- **Converter, flattened helpers:** 24 placements of 14 models in the 16 cells have an FO4 helper steeper than 40
  degrees that the converter flattens; the toe moves 0.12-1.06 m further out (ScaffFrameSladder01 / 02 1.06 m,
  BldDecoSmStairs03 / Block03 / BldWoodBSmStairs03 / BldWoodBSmStairsHalf03 / BldConcSmStairsBlock03 0.78 m). For 17
  the toe lies on a floor or under a mound. The other 7: the library's 4 Stairs03 / Block03 toes hang in the void under
  the gallery, **but their helpers pierce the gallery slab, and the converted crossing lies on the walked slab 0.43-0.45 m
  from FO4's: 2 of the 3 in-game runs there stopped at it** (section 1a; the first version of this page said "nobody
  gets there", which was wrong: the toe scan looked only at the toe, not at where the helper comes out of a floor); the
  2 V111HallStairs01 toes are over no floor this check finds, although the planner's walk stands at their foot and both
  flights pass in game (unresolved which piece the check misses); the tip of one ScaffFrameSladder02 (Parsons
  `10D351`) is 3.1 m over the floor beyond a scaffold edge. Every planned route that meets a moved crossing now carries
  `helper_crossing` (11 routes, section 4). Supported hypothesis: a toe 0.3-1 m out is a low wedge a player walking
  across in front of the stairs could catch. (HitFloorThruFullEdge02DblRampOnly and ShackBridgeFree01 have 82-90
  degree "helpers" the flattening leaves alone.)
- **Not solved here: helper-less stairs with tall risers.** Vault114's VltGearDoorStairs01 (no stair helper, treads
  0.29-0.31 m, one 0.58 m step) was STUCK at 1.41 of 3.22 m on 2026-10-09; Starfield's controller did not climb 0.30 m
  treads without a helper (V111HallStairs01, 2026-10-08). The planner now skips it (the offline walk stops on its
  steps). Unresolved: a synthesized helper ramp for such stairs in the converter, with an in-game check. It is the only
  helper-less stair the planner routes in the 16 cells.

## Files

- `scripts/game/routes.py` (`--probes-out`), `src/fo4sf/walksim.py`, `scripts/game/testqueue.py` (`plan --routes-dir`
  with the queue's own copy, `--refs`, `--first`), `scripts/game/stairs_calib.py` (offline walk vs in-game results;
  replay of route files).
- Tests: `tests/test_walksim.py`, `tests/test_routes_stairs_lanes.py` (crossings, probes, movable objects, route
  fields), `tests/test_testqueue.py` (`test_plan_takes_routes_planned_again_from_another_folder`,
  `test_judge_reads_the_queue_copy_of_the_routes`, `test_plan_puts_listed_references_first_or_keeps_only_them`),
  `tests/test_stairs_calib.py`.
- Staging (local, not in git): `C:\Modding\staging\stairs_fix_1014` (route and probe files, `offline\` with the
  calibration in both scenes, the replays, the per-stair comparison with the pinned build and the first pass, and the
  library crossing measurements); `C:\Modding\staging\stairs_fix` (first pass: `reconvert\` with the 16 re-converted
  stair models, read-back, toe scan, rotation check; its route files are superseded).
