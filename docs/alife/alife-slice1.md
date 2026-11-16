# A-Life slice 1: one squad moves A to B (rung 1a loaded, then rung 1b offline)

Queue item 25. The first build step of the living-world ladder (item 22, Part F rung 1): a controller quest, a pool of
reusable waymarkers, a 4-member Minutemen squad that walks Red Rocket to Concord in 3D (1a), then one abstract squad
that walks the north-west offline graph (1b). The native simulation plugin stays for a later slice: a 20-node graph
fits Papyrus arrays (at most 128 elements each), so this slice is Papyrus only.

**Scope boundary (no online/offline switch yet):** the 450 m / 620 m online/offline switch-in and switch-out
(materialising an offline squad into 3D actors when the player approaches, and dematerialising loaded actors back onto
the offline graph when the player leaves) is **not implemented in slice 1** -- that hand-off belongs to a later rung
(Part F rung 3). Slice 1 runs rung 1a (loaded 3D walk) and rung 1b (actorless offline graph walk) as two sequential,
independent steps.

Status: **offline only.** Build, check, compile and unit tests pass on the PC (below). Nothing has run in game. Every
in-game claim here is a **supported hypothesis** until the two PC cards come back.

## What is built

| Part | Where | What |
| --- | --- | --- |
| Graph | `scripts/alife/nw_subgraph.json`, `make_alife.py graph` | 20 smart-terrain nodes and 36 edges cut from the item 22 extraction (place rows: FormIDs, EditorIDs, core-frame metres; k-nearest edges with relay road nodes). Relays are contracted: two anchors are joined when a shortest path between them passes no other anchor, length summed. Each node keeps its 3 shortest such edges, then the shortest bridges until the graph is connected. Garrison capacity per node is the extraction's `max_squad_cap`. |
| Plugin | `dotnet/ALife` (`write`, `check`, `selftest`) | `FO4SFALife.esm`: QUST `FO4SF_ALife` 0x800 (start game enabled, not run once, out of the HUD, no alias); FACT `FO4SF_ALifeMinutemenFaction` 0x801 (Ally to PlayerFaction 01C21C); NPC_ `FO4SF_ALife_Minuteman` 0x802 (a copy of the raider plugin's calm probe `FO4_LvlRaider_Calm` F04801, in our faction only, not unique or essential, no respawn); four persistent `XMarkerHeading` (Starfield.esm 000034) REFRs `FO4SF_ALife_Waymarker_01..04` 0x810-0x813 in the core world's persistent cell (WRLD 000803 / CELL 001805 override holding only them, as dotnet/Mission); the graph as script array properties. |
| Controller | `scripts/alife/FO4SF_ALifeControllerQuest.psc` | Rung 1a, rung 1b, the garrison capacity rule, telemetry. Idle until a console command (`Mode` 0). |
| Stage | `scripts/alife/make_alife.py` (`stage`, `fold`, `verify`, `log`, `log1b`, `route`) | Same shape as `make_mission.py`: partial folder, master hashes before and after, plan.json, fold into a copy of the core experiment folder, install preflight. The log judge re-derives every verdict from the raw lines and never trusts the script's own summary. |
| Tests | `tests/test_alife.py` | Contract (properties, ids, defaults, Papyrus rules, telemetry names, linked-ref-only walk, merged placement, 1b waits for 1a), graph build and checks, the offline walk against its analytic arrival tick, garrison and reroute, waypoints and pool reuse, the judge on good and broken synthetic logs, fold and verify. |

## Rung 1a: loaded 3D walk (first)

- **Start spot:** `RedRocketTruckStopLocation` at the Red Rocket map marker's spot (XMRK 024FBE, core frame
  (-991.13, 1144.97, 104.88) m; the LCTN row itself is a cell centre at z 0). **Destination:** `ConcordLocation`
  (XMRK 082138, (-861.23, 1042.54, 93.02) m). Straight line 165.4 m. Part F quoted 439 m: that is P9's measured route,
  not this pair; the slice keeps the extraction's numbers.
- **Merged world.** The plugin's refs sit in the core world, which the game places away from the world the player walks
  in. The controller uses the verified recipe of `FO4SF_Min00Quest`: merged spot = local spot + (-1200, -2700), placed
  by `MoveTo(player, target - player position)`, then `MoveToNearestNavmeshLocation`. It starts only when the player
  stands outdoors within 300 m of the merged start spot (coordinates alone cannot tell two exterior worlds apart).
- **Squad:** four `PlaceActorAtMe` of the squad NPC_ on pool marker 0 (`SquadSize` 1..16 supported, default 4; values
  outside 1..16 are refused with `reason=bad_squad_size`), 1.5 m apart, each `SetGroupFaction` to our faction. The walk
  is the P9 recipe (docs/combined-core.md CC-63): `SetLinkedRef(waymarker)` + `EvaluatePackage()`, no alias, no
  `PathToReference`. Garrison `occupancy` resets on `Shutdown` (`StopAll`) and at the start of every `StartRung1a` and
  `StartRung1b`, and `Actor.OnPlayerLoadGame` rebases `GetCurrentRealTime` timers across game restarts.
- **Reusable waymarkers:** the line is cut into `ceil(165.4 / 40)` = 5 waypoints; waypoint i uses `Waymarkers[i % 4]`,
  moved into place only when the squad's leader comes within 10 m of the previous one, so waypoint 5 reuses marker 1.
  A marker read more than 25 m from its waypoint is placed again (persistent refs read their editor spot again after
  a cell reload: docs/mission/when-freedom-calls.md, 19 Oct).
- **Every 2 s:** each member's step speed, the squad spread (farthest member from the leader), loaded count, the
  leader's distance to its waypoint and to Concord, its cell (cell changes are counted), the player's distance, the
  leader's package. Stuck: no 2 m move for 60 s while the player is farther than 35 m (P9's rule) logs `rung1a_stuck`
  and relinks.
- **Arrival:** every live member within 15 m (XY) of Concord's merged spot, then `garrison_cap_check` at Concord
  (capacity 1).
- **PASS (script and judge alike):** 4 of 4 spawned and arrived within 500 s; every step under 6 m/s (no teleport);
  spread within 25 m on at least 90 % of samples; spawn height error under 0.5 m; at least one cell crossed; admitted
  at Concord; at least one waymarker reused.

## Rung 1b: offline subgraph walk (second)

- **Refused until rung 1a passed on this save** (`rung1b_refused reason=rung1a_not_passed`). `force=1` runs it anyway
  for debugging; the summary then never says PASS and the judge fails `not_forced`.
- Rung 1a's actors are deleted first; the 1b squad has none (`live_actors=0` on every tick).
- The script runs its own Dijkstra over the property arrays (ties to the lower index, as `make_alife.py`), from
  `RedRocketTruckStopLocation` to `StarlightDriveInLocation`: `RedRocketTruckStop > ConcordMuseum > BedfordStation >
  StarlightDriveIn`, 823.38 m. A full goal reroutes to the nearest node with room; relays (capacity 0) never garrison;
  a full node can be passed through.
- Each tick walks 1.35 m (speed 1.35 m/s, step 1 s), carrying the remainder over each node. Due on tick
  `ceil(823.38 / 1.35)` = 610. `Rung1b <ticks per timer>` sets how many ticks run per real second (10: about a minute).
- **PASS:** not forced; the player at least 1,000 m from the start spot; no live actor; progress strictly rising by
  1.35 m a tick; arrival within one tick of 610; the script's route length equal to the plan's within 0.5 m;
  garrisoned at the goal.

## Telemetry

User log `FO4SF_ALife` (`Logs/Script/User/FO4SF_ALife.0.log`), one line per event:
`FO4SF_ALIFE rt=<real s> step=<name> key=value ...`. Steps: `init`, `load_game`, `rung1a_waymarker_place`, `rung1a_spawn`,
`rung1a_start`, `rung1a_progress`, `rung1a_waymarker_advance`, `rung1a_waymarker_replace`, `rung1a_stuck`,
`rung1a_arrived`, `garrison_cap_check`, `rung1b_start`, `rung1b_route`, `rung1b_tick`, `rung1b_edge_step`,
`rung1b_node_arrive`, `summary rung=1a|1b result=PASS|FAIL`, plus `rung1a_refused`, `rung1b_refused`, `status`,
`stop`. Node numbers in the log are indices into `nw_subgraph.json`.

## Offline evidence (PC, 16 Nov 2026)

- `dotnet build -c Release`: 0 warnings, 0 errors. `selftest`: write + check, a 128-node / 128-edge graph, 7 refusals
  (129 nodes, 129 edges, bad edge, zero length, a destination that cannot garrison, pool 1, pool 17), 18 mutations
  rejected.
- Real build against the PC's core and raider plugins: `write` + `check` "all checks pass"; masters Starfield.esm and
  FO4TerrainCore.esm (the calm-probe copy keeps no link into the raider plugin); WRLD 000803, persistent CELL 001805.
- Papyrus compile against ContentResources.zip: "Compilation succeeded", 0 errors.
- `python -m unittest tests.test_alife`: 34 tests pass (the C# self-test case runs with `FO4SF_DOTNET_TESTS=1`).

## Open, said plainly

- **Unresolved:** whether the calm probe copy walks under the linked ref as P9's citizen did (N2a's follow PASS is the
  nearest evidence). The progress lines name the package every sample.
- **Unresolved:** whether four actors linked to one marker keep together; the spread criterion measures it.
- **Unresolved:** whether `Math.sqrt` behaves in game (it compiles; P9's helper avoided it).
- Rung 1b is abstract by design: no actor moves, and the 450 m / 620 m online/offline switch-in/out hand-off belongs
  to a later rung (Part F rung 3), not slice 1.

## PC card A: rung 1a, loaded (run first)

**Who:** Claude (PC) runs it; the owner checks the visuals with the recorder. Needs the owner's install authorization.

1. **Build** (repository root, the PR's exact head):
   `python scripts/alife/make_alife.py stage --out <new stage dir> --core <core experiment dir>/FO4TerrainCore.esm --raider <FO4ActorRaider.esm> --starfield <game>/Data/Starfield.esm --compiler "<game>/Tools/Papyrus Compiler/PapyrusCompiler.exe" --content-resources <game>/Tools/ContentResources.zip`
   Expect `all checks pass`, `Compilation succeeded`, `staged ...`.
2. **Fold and verify:** `make_alife.py fold --stage <stage dir> --core-dir <core experiment dir> --out <new folded dir> --raider <FO4ActorRaider.esm>`,
   then `make_alife.py verify --exp-dir <folded dir> --plan <stage dir>/plan.json --raider <FO4ActorRaider.esm>` -> `verify: ok`.
   Use a core set on which the Red Rocket crash is solved (ROADMAP: v6i plainshader).
3. **Before-receipt:** `python scripts/game/exp_install.py status --exp-dir <folded dir> --starfield <game>` and a copy
   of Plugins.txt. **Install** (game closed): the core set's usual `exp_install.py install` with `--exp-dir <folded dir>`
   and `FO4SFALife.esm` appended to `--plugins` (`--pack`), then `exp_install.py order`.
4. **Launch:** through SFSE as the core set's sessions do; load a throwaway save in the converted Commonwealth (or a new
   game through the converted start). Logging needs the `[Papyrus]` keys `make_bridge.py ini` sets.
5. **Place the player:** outdoors at Red Rocket on the merged world: console `coc FO4Core_RedRocketSpawn`, wait for the
   arrival to settle, then walk about 25 m off the road between Red Rocket and Concord, `tgm`, and make a pre-run
   throwaway save. The log's `init` line appears at quest start.
6. **Run:** console `cgf "FO4SF_ALifeControllerQuest.Rung1a"`, close the console. A `rung1a_refused` line names why
   (interior, or too far from the start spot: `player_m=`). Do not move the player during the walk; stops near the
   player are expected (P9). **Reload the pre-run save before any retry.**
7. **Watch (recorder):** four Minutemen appear at Red Rocket, walk together along the road to Concord, stop there.
   Record the whole walk.
8. **Read:** `python scripts/alife/make_alife.py log --file "<My Games>/Starfield/Logs/Script/User/FO4SF_ALife.0.log"`
   (always pass `--file`, because `Documents` can be OneDrive-redirected; exit 0 = PASS). Every criterion is printed;
   the script's own `summary rung=1a` line is reported beside it.
9. **Save** a new throwaway save after the PASS (card B loads it: rung 1b needs rung 1a passed on the save).
10. **Rollback:** `cgf "FO4SF_ALifeControllerQuest.StopAll"` deletes the squad and resets garrison occupancy; quit;
    `exp_install.py uninstall --exp-dir <folded dir> --starfield <game>`; Plugins.txt back to the before-receipt.
    Throwaway saves only. Nothing else in the game folder changes.

**Return:** the log (`FO4SF_ALife.0.log`), `make_alife.py log --file ...` output, the recording's description. No game text.

## PC card B: rung 1b, offline (only after card A passed)

1. Same install as card A (still installed, or reinstall the same folded dir: `verify` first).
2. **Load the save made after card A's PASS.** **Reload the card A PASS save before any card B retry** (never the pre-Rung-1a
   save, which has `rung1aPassed == false` and triggers `rung1b_refused reason=rung1a_not_passed`).
3. **Move the player far away (more than 1,000 m from Red Rocket):** **never use `player.setpos` for a jump over 200 m**
   (in Starfield, `setpos` over 200 m throws the player kilometres away). Safe methods: either enter a distant interior
   cell via `coc FO4Port_Vault111Cryo` (its coordinates are ~2,687 m from merged Red Rocket `(-2191.1, -1555.0)` and
   load nothing near the graph), use `player.moveto <ref>` onto a reference/actor over 1,000 m away, or step outdoors in
   incremental hops under 150 m (`<= 150 m` per `setpos`, waiting to settle after each hop, 8 hops south-east).
4. **Run:** `cgf "FO4SF_ALifeControllerQuest.Rung1b" 10 0`, close the console. About 61 s at 10 ticks per second.
   `rung1b_refused reason=rung1a_not_passed` means the save is not card A's: stop and report.
5. **Read:** `python scripts/alife/make_alife.py log1b --file "<My Games>/Starfield/Logs/Script/User/FO4SF_ALife.0.log"`
   (exit 0 = PASS): due tick 610 within one, 1.35 m a tick, no live actor, player far, route length as planned,
   garrisoned at Starlight Drive-In.
6. **Rollback:** as card A step 10.

**Return:** the log and `make_alife.py log1b --file ...` output.
