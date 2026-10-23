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

Neither leg has a `beyond` point: the runner's diagnostic teleport after a terrain test would move the player away
from where the door put them, and the judge reads the last position. In J2 (v6i, 2026-10-23) it did exactly that: every
IN leg read 1450 to 4250 m off its marker while the door's own trace put the player on it, and an OUT leg's beyond was its arrival
marker's merged position, so its 0.0 m in xy is inferred to be the teleport's spot, not proof of the door's. A queue planned with a `beyond` on a judged leg is INCONCLUSIVE BEYOND; re-plan it.

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

Coming out, the player stands in the overlay's runtime instance (an FF world whose id changes every launch), while the
marker resolves in our base WRLD. The judge takes the runtime world as the marker's in two cases. The first is a pin
the operator gives (`--world-instance FF005511=02000803`). The second needs no pin: the player's cell is one of the
core's own cells and the stage recorded exactly one core worldspace (rounds.json `core_worlds`). A cell belongs to one
WRLD, and the bridge reports a player in the runtime instance inside the core's cell ids (verified: JOURNAL 2026-10-16
"Step 0 probes" (e)). A stage from before `core_worlds` still needs the pin; re-stage it to drop the pin.

The expected spot is the marker's own record position. Coming out, the core's measured merge offset is added to it.
The door's VMAD position is never the expectation: the stage refuses a door whose VMAD return position is more than
1 cm off its marker's merged position. Missing or contradictory evidence is INCONCLUSIVE, never a PASS. INDEX means
the plan used the wrong load indices: re-plan.

## Not covered

- Doors that only auto-load (Red Rocket and Vault 111 are coc-only).
- Opening (non-load) doors.
- Locks and prompts. Those belong to the doors review.

## Presence

`scripts/bridge/presence.py` is a readout, not a test. It reports where each installed actor and named reference
actually is, with nobody at the PC, for the NPC, mission and map threads.

- `stage` reads every placed actor (ACHR) of a plugin, such as FO4SFMission.esm, and groups actors that stand within
  300 m of each other.
  - For each group it writes one terrain test. The test hops from the Red Rocket arrival to stand next to the group,
    then resolves each actor with `FO4SF_Probe.Resolve`.
  - `--extra <plugin>:<id>:<index>` adds one test at the arrival that resolves named references, such as the four map
    markers.
- `judge` gives each reference one state:
  - MISSING, INDEX, DISABLED or NOT_A_REF;
  - for an actor, by coordinates only: NEAR_MERGED (within 25 m of its record position plus the merge), AT_LOCAL
    (within 25 m of its record position itself) or ELSEWHERE, with both distances. These compare positions; they do
    not prove which world the actor is in or whether it moved. The resolved world id is kept beside them;
  - for an extra reference: PRESENT and its position.

  `judge` also counts the papyrus.log lines in each attempt that mention "moved" or "relocat". It never says a mission
  works.
