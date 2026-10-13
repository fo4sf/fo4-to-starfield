# Walking routes to the Red Rocket cave door (core64c)

Author: Claude, 2026-10-13. Branch `claude/core64c-cave-door`. This page covers the routes only. The door, the runner
and the test are in the cave-door slice page for core64c (cave-core64c.md); the exp2d door it builds on is in
[redrocket-door.md](redrocket-door.md).
Labels: **verified** = checked here on files (numbers given), **supported** = supported hypothesis, **unresolved**.
Offline checks are not in-game acceptance.

## Why routes

The owner's acceptance says initial COC and ray hops are setup evidence, not walking or door acceptance. The exp2d
door test (PR #78) teleported the player 5.5 m in front of each door and walked from there. On core64c each leg of the
door test should instead walk from where the player already stands:

- in: from the coc arrival on the Red Rocket pump island (core64c `spawn_local`);
- out: from the XTEL arrival inside RedRocket01.

The runner (Route-Walk) steers through the waypoints with `player.setangle z` and timed W holds, reading the position
after every hold. After the last waypoint it walks straight at the door. The only teleport left is the last try 1 m in
front of a door, and a trip that loads only from it is INCONCLUSIVE NEARONLY.

## How a route is found (`scripts/slice/door_route.py`, `scripts/slice/plan_cave_routes.py`)

- **Walk model.** Samples every 0.25 m along a line. Each sample stands on the highest floor at most 0.3 m above the
  previous one (a step or a 50 degree slope) and at most 1 m below it (a ledge). These limits are assumed, not
  measured.
- **Grid search.** A* runs on a 0.5 m grid of such walks, then the node path is pulled into the fewest straight legs
  that still walk.
- **Walkability oracle 1: Fallout 4's navmesh.** Fallout4.esm NAVM records for the exterior cells (-18..-17, 18..19)
  and for RedRocket01, in metres. A sample must lie over a navmesh triangle within 1 m of its floor. The tightest level
  also keeps 0.3 m from the navmesh's open borders, which FO4 draws about one agent radius from walls. This is FO4's own
  record of where characters walk.
- **Walkability oracle 2: the converted collision.** An assumed capsule of 0.35 m x 1.8 m (contacts below 0.3 m
  ignored; **unresolved**) against core64c's converted collision outside and the pinned build's RedRocket01 collision
  inside.
- **Levels.** Searched strictest first: navmesh margin 0.3 with a 0.5 m capsule (room for 0.15 m of steering drift),
  then a 0.35 m capsule, then margin 0, then the navmesh alone. Whatever capsule contacts the chosen route still has
  are reported, not hidden.

## FO4's navmesh at the doors (verified, Fallout4.esm)

| Side | Door triangle | Its door | Centre (m, FO4 / 70) | Where that is |
|---|---|---|---|---|
| exterior | navmesh `15DC7A`, triangle 1525 | `08EB65` | -996.068, 1103.803, 99.798 | at the interior door's XTEL point (-995.530, 1104.143), 5.5 m south of the exterior door |
| interior | navmesh `05FA8E`, triangle 41 | `05E844` | 0.673, -7.079, -0.017 | at the exterior door's XTEL point (0.049, -6.622), 9.2 m south of the interior door |

FO4 NPCs use a load door from its XTEL point, not from the door marker. The exterior navmesh also has a hole in the
cave mouth between that point and the door. So the outside route ends within 0.75 m of the XTEL point, and the last
part is the runner's straight walk at the door. That final walk is checked with the capsule (`final_walk`).

## Results (verified offline, 2026-10-13; `plan_cave_routes.py`, about 33 s)

### Outside: core64c world frame (the runner adds the merge offset)

- **Route.** 53.2 m in 7 legs, at level margin 0.3 with a 0.5 m capsule (the strictest level was found).
- **Waypoints.** From the pump island (floor `FO4Core_swisland9x1str01`, 105.26) the route leaves the canopy
  south-east, runs south along the east side of the station, turns south-west down the slope, and ends in front of
  the cave mouth:

  | | x | y | z |
  |---|---|---|---|
  | start (pump island) | -989.2571 | 1146.5143 | 105.2609 |
  | | -986.2571 | 1142.0143 | 105.1311 |
  | | -982.7571 | 1127.5143 | 105.0253 |
  | | -985.2571 | 1109.5143 | 102.0821 |
  | | -986.2571 | 1106.5143 | 100.9236 |
  | | -992.2571 | 1101.5143 | 99.5939 |
  | | -993.7571 | 1102.0143 | 99.5701 |
  | end (in front of the cave mouth) | -995.2571 | 1103.5143 | 99.6857 |

- **Climb and drop.** Largest rise 0.09 m and largest drop 0.10 m per 0.25 m. The whole route descends 5.6 m.
- **Capsule.** 0 contacts with the 0.35 m capsule. Shifted 0.2 m to the left of the walking direction: 3 contacts.
  Shifted to the right: 0. Off the navmesh: 0 either way.
- **Final walk at the door.** 3.5 m straight from the last waypoint, capsule clear, floor 99.71 down to 99.05. It
  reaches 2.52 m from the door's origin, inside the 3 m `fAutoDoorActivateDistance` if that range is measured to the
  origin (**supported**).
- **W-hold budget.** 26.5 s (`door_route.walk_ms`: 1.6 x the route at 4.6 m/s, plus 8 s).

### Inside: RedRocket01 frame

- **Route.** 6.7 m in 3 legs, found only at the level "navmesh alone, margin 0.3". Neither capsule finds a way at any
  margin.
- **Waypoints.** From the XTEL arrival (floor `cavemoundrocksmed03`, 0.244) the route goes north up the hall and stops
  short of the door:

  | | x | y | z |
  |---|---|---|---|
  | start (XTEL arrival) | 0.0493 | -6.622 | 0.2442 |
  | | -0.4507 | -2.122 | 0.6504 |
  | | -0.9507 | -1.622 | 0.6809 |
  | end | -0.9507 | -0.122 | 0.5021 |

  It ends 2.68 m from the door's origin. The final walk at the door reaches 2.43 m after 0.24 m.
- **Cave-mound climb (supported hypothesis).** The route crosses the low mound `cavemoundrockslow04`. Its floor rises
  to z 1.11 with up to 0.28 m per 0.25 m, close to the assumed 0.3 m limit.
- **Capsule contacts (supported hypothesis).** The assumed capsule touches 8 samples on legs 0 to 2, against that mound
  and the hall wall `cavehall2way01` (x -0.62 to -0.95, y -2.12 to -0.62). The route is still taken as walkable
  because FO4's own navmesh crosses the mound there, so FO4 characters walk it. The converted collision is FO4's own
  shapes. The contacts may come from the conservative capsule model: a vertical cylinder that treats any steep
  triangle above 0.3 m as a wall. This is not shown in game.
- **What the run shows.** If the player stalls on the mound, the runner's walk stops ("no progress in two steps"). A
  load from the last-try teleport is then NEARONLY, not a PASS.
- **Start.** The arrival's own capsule touches `cavemoundrocksmed04`, as on exp2d (redrocket-door.md section 5). The
  route leaves from there: samples within 0.8 m of the start are not checked for the capsule.
- **W-hold budget.** 10.3 s.

## Unknowns

1. The capsule (radius, height, step height, maximum slope) and how the character controller climbs cave mounds
   (**unresolved**). The routes take FO4's navmesh as the walkability record, and the capsule as a margin where it
   fits.
2. Steering: `player.setangle z` turns the actor, and W walks along that heading. Earlier route runs showed this
   (**supported**). The planned clearance (0.5 m capsule outside) leaves 0.15 m for drift against the assumed 0.35 m
   capsule.
3. The run speed of 4.6 m/s comes from earlier route runs. On Mars, with its lower gravity, a downhill walk may differ.
   The runner measures its own speed after every hold.

## Reproduce

```powershell
python scripts\slice\plan_cave_routes.py --fo4 <Fallout4.esm> --core <terrain_core64c> --port <pinned build> `
       --out <routes.json> --png <routes.png>
python -m unittest tests.test_door_route
```
