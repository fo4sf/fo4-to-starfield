# Load order on the test PC: what writes Plugins.txt, and why ref ids move between sessions

Written 22 Oct 2026 from the code on main and the Install thread's reads of the owner's PC. There is no single
enforced load order today; this page records the three orders that exist and who changes the file. Nothing here is
verified beyond what each line says.

## Who writes Plugins.txt

- `scripts/deploy_starfield.py install` activates the port by appending its `*FO4Port.esm` line, and `uninstall`
  removes exactly the lines it added (`plugins_added` in the manifest). The runner's `scripts/game/cycle.ps1:49-50`
  runs uninstall then install before every cycle, so in runner sessions FO4Port lands after every other line.
- `scripts/game/exp_install.py install` appends the experiment's plugins; `order` moves each experiment plugin right
  after its active masters before launch (module doc, `order_lines`). It refuses missing or disabled masters.
- `scripts/game/map_markers_install.py order` moves `*FO4SFMapMarkers.esm` to the end; cycle.ps1 runs it before the
  bridge's order, so the planned read indexes of the experiment and FO4Port stay as they were (module doc).
- The launcher (`src/fo4sf/launcher/crashwatch.py`, #449, #481) writes Plugins.txt only before start and only when the
  bridge toggle changes; since #481 it compares the order at start and at exit and reports a change in crashwatch.log.
- The game itself: `docs/PLAY-AND-TEST.md` says to choose **Current** at the "load order changed" dialog because
  saving it can switch the port's plugins off, and `map_markers_install.py active` notes that loading a save can
  restore the save's own order after `order` ran.

## What Install read on the owner's PC, 22 Oct

- The map markers install at 05:50 local recorded FO4Port first in Plugins.txt (so the mission's index was 06 in the
  morning session: `prid 06000811` worked for Codsworth).
- At 11:26:20 local, 25 s after the owner started the game through the launcher, Plugins.txt was rewritten (not by
  Install) as: FO4TerrainCore, FO4TerrainCore_Mars, FO4ActorRaider, FO4SFMission, FO4Port, FO4SFMapMarkers,
  FO4SFBridge, all active. The mission became 05, and `prid 05000811` worked in the afternoon session. The launcher
  thread's reading of its own code is that the launcher did not write it (the bridge setting was unchanged), so the
  rewrite is the game's; the cause is inferred, not traced.

## Consequences

- Console ids of our records (`prid`, `placeatme`) are not stable across sessions. Owner instructions should name the
  object, or Install reads the current Plugins.txt first and gives the index for that session.
- Automated door and walk judges plan their read indexes from the order the stage predicted (`door_rounds.py`); a
  changed index is reported as INCONCLUSIVE INDEX, not as a pass or a fail.
- Open: one documented target order (runner and owner installs the same), and an enforcement step before launch that
  refuses a mismatch. #481's report is detection only.
