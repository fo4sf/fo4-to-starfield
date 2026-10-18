# Door round trips on the installed set

`scripts/bridge/door_rounds.py` plans one round trip per scripted load door (docs/terrain/scripted-doors.md): a test
going in and a test coming out, both judged from the bridge's log. It is the baseline the door fixes (#354 and the
doors review) are measured against.

## Why

The Super Duper Mart round trip of 2026-10-17 passed both ways, but its two tests were planned by hand against core
1d4591b6's ids. The v5 reconvert added 47 FLOR bases and shifted every appended core id, so those queues now point at
other records. This planner reads the doors from the core build and checks each one in the plugins that are actually
installed before it writes a test.

## What each test does

- **In**: a launch at `FO4Core_RedRocketSpawn`, hops of 185 m to the door's exterior arrival marker, then the runner
  activates the exterior door from the console (only after `GetIsID` proves the selection). The bridge must then put
  the player within 3 m of the interior arrival marker, in that interior's cell.
- **Out**: `coc` into the interior, a drop onto the interior arrival marker, then the interior door is activated. The
  bridge must put the player within 3 m of the exterior arrival marker's merged position, in the exterior world.

The runner turns the save's companion off at the start of every session unless the queue says `"companion": "keep"`;
these queues leave it off.

Every check the stage makes is against the installed plugins: the door REFR exists, its base is the one the build
names (a DOOR, or an ACTI as the core writes its exterior load doors), its `FO4SF_LoadDoor` VMAD leads to the other
side's marker, and both markers exist. A door that fails a check is listed under `skipped` in rounds.json, with the reason, and is not planned.

## How to run (PC, game closed)

1. Read the load indices the runner's launch will give. `cycle.ps1` re-deploys FO4Port.esm at the end of Plugins.txt
   and puts the bridge last:
   `python scripts\bridge\door_rounds.py order --plugins-txt %LOCALAPPDATA%\Starfield\Plugins.txt`
2. Stage the plan against the installed core and port:
   `python scripts\bridge\door_rounds.py stage --core <core build> --core-plugin <installed FO4TerrainCore.esm> --port <installed FO4Port staging> --core-index HH --port-index HH --out <new folder>`
3. Plan the queue without `--plugins`, so the installed set is left as it is:
   `python scripts\game\testqueue.py plan-terrain --staging <installed FO4Port staging> --exp-dir <new folder> --out <queue> --bridge <installed bridge staging>`
4. Run the queue: `python scripts\game\testqueue.py run --queue <queue> --max-attempts 1`
5. Judge it: `python scripts\bridge\door_rounds.py judge --queue <queue>`. This writes door_rounds_judge.json into the
   queue folder.

The judge gives a PASS only with every proof from the test's own attempt:
- the runner's activation (obs.json `activate.selected` true);
- the test's ack line;
- the destination marker resolved after the ack, at the planned load index;
- a loaded player position after the ack, in the marker's cell (going in) or in the world the marker resolves in
  (coming out), within 3 m.

The expected spot is the marker's own record position. Coming out, the core's measured merge offset is added to it.
The door's VMAD position is never the expectation: the stage refuses a door whose VMAD return position is more than
1 cm off its marker's merged position. Missing or contradictory evidence is INCONCLUSIVE, never a PASS. INDEX means
the plan used the wrong load indices: re-plan.

## Not covered

- Doors that only auto-load (Red Rocket and Vault 111 are coc-only).
- Opening (non-load) doors.
- Locks and prompts. Those belong to the doors review.
