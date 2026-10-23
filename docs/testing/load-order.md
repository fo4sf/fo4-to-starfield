# Load order on the test PC: what writes Plugins.txt, and why ref ids move between sessions

Written 22 Oct 2026 from the code on main and the Install thread's reads of the owner's PC. There is no single
enforced load order today; this page records the three orders that exist and who changes the file. Nothing here is
verified beyond what each line says.

## Who writes Plugins.txt

- `scripts/deploy_starfield.py install` activates the port and records in its manifest only the line it owns
  (`plan_plugin_activation`): with no FO4Port line in the file it appends `*FO4Port.esm` and owns it; with an inactive
  `FO4Port.esm` line it activates that line in place and restores it on uninstall; with an active `*FO4Port.esm`
  already there it owns nothing and leaves the line where it is. `uninstall` removes exactly the owned lines. The
  runner's `scripts/game/cycle.ps1:49-50` runs uninstall then install before every cycle, so FO4Port lands after
  every other line only where the manifest owns the appended line (the usual runner case); a FO4Port line the owner
  put in by hand keeps its position through the cycle.
- `scripts/game/exp_install.py install` appends the experiment's plugins; `order` guarantees before launch that each
  experiment plugin comes after all of its active masters (`order_lines`): a plugin that stands before one of its
  masters is moved to just after the last of them, and a plugin already after them is left where it is, so an
  unrelated line can sit between a master and the experiment. It refuses missing or disabled masters.
- `scripts/game/map_markers_install.py order` moves `*FO4SFMapMarkers.esm` to the end; cycle.ps1 runs it before the
  bridge's order, so the planned read indexes of the experiment and FO4Port stay as they were (module doc).
- The launcher (`src/fo4sf/launcher/crashwatch.py`, #449, #481, #487) writes Plugins.txt only before start: when the
  bridge toggle changes, and, since #487 (merged 22 Oct, after the run below), through `scripts/game/load_order.py`
  when the `load_order` setting is `fix` (the default) and the order differs from the target (`apply_load_order`,
  run after the bridge step; `check` refuses a different order instead, `off` leaves the file alone). Since #481 it
  compares the order at start and at exit and reports a change in its own output
  ("Plugins.txt load order changed while the game ran: ..."). The crashwatch.log line for it is written only when the
  crash watcher is on (`crash_watch.enabled`; `play()` has no log path otherwise), so an ordinary launcher run with
  the watcher off leaves no persistent record of the change.
- The game itself: `docs/PLAY-AND-TEST.md` says to choose **Current** at the "load order changed" dialog because
  saving it can switch the port's plugins off, and `map_markers_install.py active` notes that loading a save can
  restore the save's own order after `order` ran.

## What Install read on the owner's PC, 22 Oct

- The map markers install at 05:50 local recorded FO4Port first in Plugins.txt (so the mission's index was 06 in the
  morning session: `prid 06000811` worked for Codsworth).
- At 11:26:20 local, 25 s after the owner started the game through the launcher, Plugins.txt was rewritten (not by
  Install) as: FO4TerrainCore, FO4TerrainCore_Mars, FO4ActorRaider, FO4SFMission, FO4Port, FO4SFMapMarkers,
  FO4SFBridge, all active. The mission became 05, and `prid 05000811` worked in the afternoon session. The launcher
  thread's reading of its own code is that the launcher did not write it (the bridge setting was unchanged, and the
  load-order fixer of #487 did not exist yet), so the rewrite is the game's; the cause is inferred, not traced.

## Consequences

- Console ids of our records (`prid`, `placeatme`) are not stable across sessions. Owner instructions should name the
  object, or Install reads the current Plugins.txt first and gives the index for that session.
- The door judge (`scripts/bridge/door_rounds.py`) plans its read indexes from the order the stage predicted and never
  turns a changed index into a pass or a fail, but it does not always name it: `judge_test` checks the runner's
  activation proof and the ack first, so an index change that breaks the GetIsID proof against the planned door id
  comes back as INCONCLUSIVE NOT_ACTIVATED (or NO_ACK), and only a leg that got as far as resolving its destination
  marker at the wrong index reads INCONCLUSIVE INDEX. Any INCONCLUSIVE after an order change is a cue to read
  Plugins.txt before diagnosing the harness. The walk judge
  (`scripts/game/walk_eval.py`) has no such gate: it judges positions, ground, crossings and screenshots without
  comparing the planned index to the runtime one, so a walk run after an order change needs its indexes checked by
  hand.
- Planner drift (Card J, 22 Oct): `door_rounds.py order` at 7ecc3185 gave `--port-index 07` for the same Plugins.txt
  where main db7c015c gives 06 (a43afefa puts the map markers plugin right after the port, as cycle.ps1 does), and the
  live game had 06 (settling runs activated 06008EB2). The v6i plan made at 07 was discarded unrun. Plans take their
  indices from a checkout at db7c015c or later (the doors plan refuses older ones) and check them against the
  Plugins.txt the game wrote after a launch before staging.
- #481's report is detection only. #487 (merged 22 Oct) adds `scripts/game/load_order.py check|fix`, which defines
  the target order (the order the game wrote on 22 Oct, each plugin after its masters) and a launcher setting that
  runs it before every play; the Launcher thread documents the target order on this page next. Open: the runner
  (cycle.ps1) does not call it yet, so runner and owner installs can still differ.

## Target order

`scripts/game/load_order.py` (module doc) is the one definition. Lines that are not ours keep their own order and
come first; ours follow in five groups, each keeping its current order:

1. the cores (`FO4Terrain*`, `FO4Actor*`),
2. the other `FO4SF*` plugins (experiments such as FO4SFMission),
3. FO4Port,
4. FO4SFMapMarkers,
5. FO4SFBridge, last.

Over the groups, every plugin loads after each of its masters that has a line, and a plugin that is not ours but
masters one of ours (a patch) comes right after that master. On the owner's PC this gives FO4TerrainCore,
FO4TerrainCore_Mars, FO4ActorRaider, FO4SFMission, FO4Port, FO4SFMapMarkers, FO4SFBridge: the order the game wrote at
11:26 on 22 Oct, so a game that writes that order again changes nothing. A morning file with FO4Port first is moved
by `fix` (Port from line 1 to after the mission; `tests/test_load_order.py`). `fix` copies the old file to
`Plugins.txt.bak-<time>` before writing and never ticks or unticks a line; both `check` and `fix` refuse (exit 6) a
missing or inactive master, a master cycle or a duplicated line. In the launcher, `load_order=fix` (the default)
runs it before each start, `check` refuses to start on a different order, and `off` leaves the file alone; `play
--dry-run` only reports what `fix` would move.
