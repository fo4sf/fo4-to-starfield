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
| `src/fo4sf/core/loadset.py` | The rules, which read nothing: the plugins the game ships, which plugins and names are ours (they start with FO4 or FOCC), and the start records. |
| `src/fo4sf/launcher/loadprobe.py` | Reads what Starfield will load on the PC: the built-in plugins, `Starfield.ccc`, `sTestFile`, plugin copies in `My Games\Starfield\Data`, and the plugins that override the start records. |
| The open-baseline note | `baseline-open.json` in the test runner's state folder (`FO4_AI_TEAM_STATE`, else `%LOCALAPPDATA%\fo4-ai-team\state`). `prepare` writes it when it turns plugins off, and `restore` removes it, so a baseline that was never restored is found wherever its folder is. |
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
   - It takes every Papyrus log in `Logs\Script` of the My Games folders that was written after `prepare` and before
     `restore`: `Papyrus.0.log`, and the older `Papyrus.1.log` and so on when the game was started more than once.
     It joins them, oldest first, into `Papyrus.0.log` in the out folder, and says so when there were several
     sessions. It runs only while Starfield is closed, and only once.
   - The session was not vanilla, and is no baseline, when any of these is true:
     - the log names any of ours (FO4* or FOCC*);
     - Plugins.txt has a plugin the game does not ship ticked again (now, or when `restore` ran first): the Creations
       menu, a mod manager or our launcher can tick plugins (`sfstack.md`);
     - SFSE wrote a file in `My Games\Starfield\SFSE\Logs` meanwhile: the game was started through `sfse_loader.exe`.
   - Then `collect` exits 1, says which, and keeps the log as `Papyrus.0.log.not-vanilla`. The baseline gets no log,
     so `compare` refuses it. Run `restore`, then prepare a new baseline in a new folder.
6. Run `python -I scripts\game\baseline.py restore --out <folder>` (section 4), then `status --out <folder>` to see
   where everything stands. `restore` also ends the baseline's time: `collect` takes no log written after it.
7. For any run of ours, run `python -I scripts\game\baseline.py compare --out <folder> --run-log <the run's
   Papyrus.0.log> --report <folder>\compare_<run>.json`.

### What `prepare` refuses (nothing is changed)

- Starfield is running, or its state is unknown.
- The out folder already holds a baseline. When that one was never restored, its record holds the only copy of
  Plugins.txt as it was, so `prepare` says to run `restore` on it first.
- A baseline of the same Plugins.txt was never restored: the one the open-baseline note names, wherever it is, or one
  in a folder next to the out folder (the same parent folder).
- Nothing is on to turn off, but our plugins are off in Plugins.txt already. That is what an earlier baseline that was
  never restored leaves behind, when its note is gone too. `--allow-off` goes ahead when no baseline turned them off:
  the game also adds a new plugin it finds in `Data` unticked (verified, `sfstack.md`).
- Plugins.txt is read-only, when there is something to turn off.
- Plugins.txt is not UTF-8 (the game's own file is).
- There is no `Data` folder under `--starfield`, or `LOCALAPPDATA` is not set (not Windows).
- The `[Papyrus]` logging keys are not in effect. Without them the session writes no log, and
  `scripts/bridge/make_bridge.py ini` sets them.
- `loaders` fails or is UNKNOWN. That means an `sTestFile` is set in an INI (the game then ignores Plugins.txt), a
  `Starfield.ccc` lists a mod (it loads first, whatever Plugins.txt says), a plugin in `My Games\Starfield\Data` is
  named like one in `Data` (unless that folder is linked to `Data` itself, as Vortex can do), or no My Games folder
  was found.
- `start` fails with the start pinned as vanilla (`start_overrides: []`). That means a plugin that loads anyway (a
  `.ccc` one) overrides `StartupQuest_DO`, `MQ101` or `MQ101Debug`.
- Starfield was started while `prepare` read the game folder (hashing the built-in plugins takes a while).
- The open-baseline note could not be written. The record is removed.
- Plugins.txt changed between the read and the write. The record and the note are removed, and Plugins.txt keeps the
  other writer's version.
- Plugins.txt could not be written (on Windows, a read-only file or one another program holds open). The record and
  the note are removed, and Plugins.txt is as it was.

## 4. How `restore` decides

The game rewrites Plugins.txt at startup. It inserts `.ccc` entries at the top and removes implicitly active
plugins (verified: docs/research/framework/launcher-sources/sfstack.md, from Ortham's "Load order in Starfield").

| Plugins.txt now | What `restore` does |
|---|---|
| Anything, when `prepare` turned nothing off | Writes nothing, and records the restore. |
| As `prepare` wrote it | Writes the recorded bytes back. |
| Already the recorded bytes | Writes nothing, and records the restore. |
| Rewritten, with no plugin the game does not ship ticked | Keeps the rewrite as `Plugins.txt.at-restore` in the out folder (it can hold the owner's own edits), then writes the recorded bytes over it. |
| Gone | Writes the recorded bytes. |
| With such a plugin ticked again | Refuses and names it (the session may not have been vanilla). `--force` keeps the current file as `Plugins.txt.at-restore`, then writes the recorded bytes. |

Every restore records its time, which ends the time `collect` takes logs from, and the plugins the game does not
ship that were ticked in the file it found. When there were any (the recorded bytes count too: someone put them
back before `restore` ran, and nobody knows when), `collect` after it keeps no log as the baseline. A log collected
before `restore` was checked against Plugins.txt then.

A Plugins.txt that is not UTF-8 (the game may write a name in another encoding) is read with the odd bytes
replaced, so a ticked plugin is still found and `--force` still works.

Every write is guarded: the file must still be the one just read (`fo4sf.launcher.restore.write_plugins_txt`). When
Plugins.txt changes during `restore`, or cannot be written, nothing is written, and `restore` says to run it again.
A restore removes the open-baseline note when it names this baseline. Nothing here touches a plugin, an archive or
an INI.

## 5. Reading `compare`

`compare` puts every kind of error and warning in the run into one group: the first row below that fits it. A kind is
one message with one stack, and runtime FF ids are read as `FF??????`.

| Group | Means |
|---|---|
| `both` | The same kind in both runs. Starfield's own, so it is not ours to chase. |
| `ours` | Not in the baseline, and it names one of ours: our EditorIDs and scripts start with FO4 or FOCC. Ours to fix, even at a script line where vanilla errors too: then the report says how many baseline lines came there. |
| `both_place` | The same message at the same script line in both runs, from another caller or object. |
| `starfield` | Only in the run, from Starfield's own scripts. What our changes cost Starfield, unless the baseline did not get that far (below). |
| `baseline` | Only in the baseline, at a script line no `both_place` kind of the run has. |

Every baseline line counts in one group only, so the groups' baseline lines add up to the baseline's errors and
warnings.

A group says where a message came from, not why. A Starfield error that comes only in our run can still be one that
Starfield makes later in its own opening, if the baseline stopped before that point. That is why step 4 notes where
the baseline stopped.

`compare` also re-reads the built-in plugins' names and sizes, and says when they differ from the recorded ones (a
Starfield update, or a new Creation). Then it is time for a new baseline.

`compare` refuses a run log that is not there, and a `--report` path that is one of the baseline's own files (the
record, the kept logs, `Plugins.txt.at-restore`), the run's log, Plugins.txt or the open-baseline note.

## 6. Assumptions

- **Verified:**
  - The log format. Each message is a time of day in brackets, then `error:`, `warning:` or a note, then an optional
    `stack:` with tab-indented frames. The source is Install's copy of the 28 Oct run 3 log, on Starfield 1.16.244.
  - `Papyrus.0.log` is the newest log and `Papyrus.1.log` the one before
    (docs/research/framework/newgame-notes/05-tools-ecosystem.md, from the Nexus logging guide).
  - The loader rules. `Starfield.ccc`, `sTestFile`, the rewrite at startup and the My Games Data rule are all from
    `sfstack.md`. So is the game adding a new plugin it finds in `Data` unticked, and resetting a read-only
    Plugins.txt.
  - The start records. In Starfield.esm, `StartupQuest_DO` is 00562D (DFOB), `MQ101` is 003448 and `MQ101Debug` is
    0A7D31 (`fo4sf.core.loadset` module doc).
- **Supported hypothesis:**
  - A plugin copy in `My Games\Starfield\Data` stands in for the one in `Data`. The loader rule implies it, so the
    `loaders` check refuses either way.
  - SFSE writes its log to `My Games\Starfield\SFSE\Logs` (`sfse.log`, from SFSE's readme as
    sfse/FOCCSidecar/README.md cites it), and so do our SFSE plugins (sfse/FOCCPing/README.md). A plain start writes
    nothing there.
- **Unknown:**
  - Whether the game writes the end of its log when it is killed instead of quit. Step 4 quits from the game's menu
    for that reason, and `collect` refuses while the game runs.
  - Whether the game reads a `Starfield.ccc` that starts with a byte-order mark. The `loaders` check reads past the
    mark, so the first name still counts as listed.
  - Whether the game reads the `[Papyrus]` keys from a `StarfieldCustom.ini` saved with a byte-order mark before its
    first line. The check reads a `[Papyrus]` header right after the mark as not there, so `prepare` refuses.
  - Whether the game reads `sTestFile` from `Starfield_<language>.ini` (`sfstack.md` question 18 lists that INI).
    The `loaders` check reads it, so it only refuses more.
