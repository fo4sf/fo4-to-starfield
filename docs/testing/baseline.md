# The vanilla baseline

One plain Starfield New Game, played with every plugin the game does not ship turned off. Its Papyrus log is the list
of errors Starfield makes on its own. A run of ours is compared with it, and only what is new is ours to chase.

The owner asked for this on 29 Oct 2026 in the strip-down thread ("Strip down Starfield and add our own planet"):

- **Pick I:** the switches that quiet Starfield's own quests go straight into the mod. There is no test-only profile
  plugin.
- **Pick T:** Install's session plays the baseline on the owner's PC.

Run 3's log (28 Oct) mixed our errors (28 from our map marker script, `FO4SF_MapMarkers.psc` line 116) with errors
from Starfield's own scripts, such as SFBGS003's shutdown script. Nobody could tell which of Starfield's errors come
in a vanilla game too.

## 1. The pieces

| Piece | What it does |
|---|---|
| `scripts/game/baseline.py` | `check`, `prepare`, `collect`, `restore`, `status` and `compare` (its module doc, and section 3 below). |
| `src/fo4sf/core/papyrus_log.py` | Reads a Papyrus log into messages with their stacks, and compares two logs (section 5). |
| `src/fo4sf/core/loadset.py` | Reads what Starfield will load: the built-in plugins, `Starfield.ccc`, `sTestFile`, plugin copies in `My Games\Starfield\Data`, and the plugins that override the start records. |
| The gate's `loaders` and `start` checks | `src/fo4sf/core/preflight.py`; the table in docs/ai/leader-core.md section 7. `prepare` runs both, and so does `testqueue.py run --preflight` before every test run. |

## 2. The owner's line for the Install thread

> Run the vanilla baseline: turn our plugins off, play one vanilla New Game for 10 minutes, collect its log and put our plugins back.

## 3. Runbook (Install's session, on the PC)

The game folder below is the PC's (`D:\SteamLibrary\steamapps\common\Starfield`), and the out folder is new for each
baseline.

1. Close Starfield. Run `python -I scripts\game\baseline.py check --starfield <game dir>`. It must end with
   `check: prepare would go ahead`, and it writes nothing.
2. Run `python -I scripts\game\baseline.py prepare --starfield <game dir> --out D:\Modding\testqueue\baseline_<date>`.
   It writes `baseline.json` first: Plugins.txt as it is (its bytes), the built-in plugins (names, sizes, sha256),
   Starfield.exe's size and sha256, and the time. Then it unticks every active plugin the game does not ship. It
   names each one it turned off.
3. Start Starfield the plain way: Steam's Play button, or `Starfield.exe`.
   - **Not the FO4SF Launcher.** It can write Plugins.txt before the start (docs/testing/load-order.md).
   - **Not `sfse_loader.exe`.** SFSE loads only through it (verified,
     docs/research/framework/newgame-notes/05-tools-ecosystem.md), and with it our SFSE plugins would load.
4. Choose New, and play about 10 minutes of the opening. Note in the Install thread where you stopped. Then quit to
   the desktop from the game's menu.
5. Run `python -I scripts\game\baseline.py collect --out <folder>`.
   - It copies the newest `Logs\Script\Papyrus.0.log` of the My Games folders into the out folder. It takes only a
     log written after `prepare`.
   - It exits 1 when the log names any of ours (FO4* or FOCC*). Then the session loaded something of ours, and it is
     no baseline.
6. Run `python -I scripts\game\baseline.py restore --out <folder>` (section 4), then `status --out <folder>` to see
   where everything stands.
7. For any run of ours, run `python -I scripts\game\baseline.py compare --out <folder> --run-log <the run's
   Papyrus.0.log> --report <folder>\compare_<run>.json`.

### What `prepare` refuses (nothing is changed)

- Starfield is running, or its state is unknown.
- The out folder already holds a baseline.
- There is no `Data` folder under `--starfield`, or `LOCALAPPDATA` is not set (not Windows).
- The `[Papyrus]` logging keys are not in effect. Without them the session writes no log, and
  `scripts/bridge/make_bridge.py ini` sets them.
- `loaders` fails. That means an `sTestFile` is set in an INI (the game then ignores Plugins.txt), a `Starfield.ccc`
  lists a mod (it loads first, whatever Plugins.txt says), or a plugin in `My Games\Starfield\Data` is named like one
  in `Data`.
- `start` fails with the start pinned as vanilla (`start_overrides: []`). That means a plugin that loads anyway (a
  `.ccc` one) overrides `StartupQuest_DO`, `MQ101` or `MQ101Debug`.
- Plugins.txt changed between the read and the write. The record is removed, and Plugins.txt keeps the other
  writer's version.

## 4. How `restore` decides

The game rewrites Plugins.txt at startup. It inserts `.ccc` entries at the top and removes implicitly active
plugins (verified: docs/research/framework/launcher-sources/sfstack.md, from Ortham's "Load order in Starfield").

| Plugins.txt now | What `restore` does |
|---|---|
| As `prepare` wrote it | Writes the recorded bytes back. |
| Already the recorded bytes | Writes nothing, and records the restore. |
| Rewritten, with no plugin the game does not ship ticked | Writes the recorded bytes over the rewrite. |
| Gone | Writes the recorded bytes. |
| With such a plugin ticked again | Refuses and names it (the session may not have been vanilla). `--force` keeps the current file as `Plugins.txt.at-restore` in the out folder, then writes the recorded bytes. |

Every write is guarded: the file must still be the one just read (`fo4sf.launcher.restore.write_plugins_txt`).
Nothing here touches a plugin, an archive or an INI.

## 5. Reading `compare`

`compare` puts every kind of error and warning in the run into one group. A kind is one message with one stack, and
runtime FF ids are read as `FF??????`.

| Group | Means |
|---|---|
| `ours` | Only in the run, and it names one of ours: our EditorIDs and scripts start with FO4 or FOCC. Ours to fix. |
| `starfield` | Only in the run, from Starfield's own scripts. What our changes cost Starfield, unless the baseline did not get that far (below). |
| `both_place` | The same message at the same script line in both runs, from another caller or object. |
| `both` | The same kind in both runs. Starfield's own, so it is not ours to chase. |
| `baseline` | Only in the baseline. |

A group says where a message came from, not why. A Starfield error that comes only in our run can still be one that
Starfield makes later in its own opening, if the baseline stopped before that point. That is why step 4 notes where
the baseline stopped.

`compare` also re-reads the built-in plugins' names and sizes, and says when they differ from the recorded ones (a
Starfield update, or a new Creation). Then it is time for a new baseline.

## 6. Assumptions

- **Verified:**
  - The log format. Each message is a time of day in brackets, then `error:`, `warning:` or a note, then an optional
    `stack:` with tab-indented frames. The source is Install's copy of the 28 Oct run 3 log, on Starfield 1.16.244.
  - The loader rules. `Starfield.ccc`, `sTestFile`, the rewrite at startup and the My Games Data rule are all from
    `sfstack.md`.
  - The start records. In Starfield.esm, `StartupQuest_DO` is 00562D (DFOB), `MQ101` is 003448 and `MQ101Debug` is
    0A7D31 (`fo4sf.core.loadset` module doc).
- **Supported hypothesis:** a plugin copy in `My Games\Starfield\Data` stands in for the one in `Data`. The loader
  rule implies it, so the `loaders` check refuses either way.
- **Unknown:** whether the game writes the end of its log when it is killed instead of quit. Step 4 quits from the
  game's menu for that reason.
