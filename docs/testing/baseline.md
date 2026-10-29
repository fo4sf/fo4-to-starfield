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
| The open-baseline note | `baseline-open.json` in the test runner's state folder (`FO4_AI_TEAM_STATE`, else `%LOCALAPPDATA%\fo4-ai-team\state`). `prepare` writes it when it turns plugins off, and `restore` removes it, so a baseline that was never restored is found wherever its folder is. While it names a baseline whose restore has not run, `testqueue.py run` installs and launches nothing (section 3). The runner and `prepare` read it the same way: a note, or the record it names, that cannot be read counts as open. |
| The lock | `baseline.lock` in the same state folder. `prepare`, `collect` and `restore` run one at a time, whatever their out folders: one that finds another running waits 2 seconds, then refuses and changes nothing. The lock of one that stopped (a crash, a closed window) is taken over after 15 minutes. On Windows, the lock of one that still runs (paused by a click in its window, say) cannot be taken over: the other waits its 2 seconds and refuses. A lock whose age cannot be read is never taken over either: the refusal says so, and the lock is removed by hand once none runs. `check`, `status` and `compare` take no lock. |
| The gate's `loaders` and `start` checks | `src/fo4sf/core/preflight.py`; the table in docs/ai/leader-core.md section 7. `prepare` runs both, and so does `testqueue.py run --preflight` before every test run. |

## 2. The owner's line for the Install thread

> Run the vanilla baseline: turn our plugins off, play one vanilla New Game for 10 minutes, collect its log and put our plugins back.

## 3. Runbook (Install's session, on the PC)

The game folder below is the PC's (`D:\SteamLibrary\steamapps\common\Starfield`), and the out folder is new for each
baseline. The out folder is never in the game folder, a My Games folder or Plugins.txt's folder: `collect` and
`compare` write files there, and they must never write over one of the game's.

1. Close Starfield. Run `python -I scripts\game\baseline.py check --starfield <game dir>`. It must end with
   `check: prepare would go ahead`, and it writes nothing.
2. Run `python -I scripts\game\baseline.py prepare --starfield <game dir> --out D:\Modding\testqueue\baseline_<date>`.
   It writes `baseline.json` first: Plugins.txt as it is (its bytes), the built-in plugins (names, sizes, sha256),
   Starfield.exe's size and sha256, the sha256 of the Papyrus logs already in My Games, and the time. Then it unticks
   every active plugin the game does not ship. It names each one it turned off.
   - The game's own plugins stay on. By the rules in `fo4sf.core.loadset`, those are the official plugins and any
     `SFBGS*` or `BlueprintShips-*` plugin, so a Bethesda Creation named `SFBGS*` stays on too, as it does in our
     runs.
3. Start Starfield the plain way: Steam's Play button, or `Starfield.exe`.
   - **Let Steam finish any update first.** When the game or its built-in plugins change between `prepare` and
     `collect`, which build the session ran on is not known, and `collect` takes no baseline from it.
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
   - It is no baseline either when the game changed since `prepare`: the built-in plugins by name and size, or
     Starfield.exe by size and sha256 (a Steam update).
   - A log that was already there at `prepare` is never taken, even when the game has moved it on since with a new
     time: `prepare` noted its sha256.
   - It refuses, and changes nothing, while the game folder is not readable: run it again once it is.
   - Then `collect` exits 1, says which, and keeps the log as `Papyrus.0.log.not-vanilla`. The baseline gets no log,
     so `compare` refuses it. Run `restore`, then prepare a new baseline in a new folder.
6. Run `python -I scripts\game\baseline.py restore --out <folder>` (section 4), then `status --out <folder>` to see
   where everything stands. `restore` also ends the baseline's time: `collect` takes no log written after it.
7. For any run of ours, run `python -I scripts\game\baseline.py compare --out <folder> --run-log <the run's
   Papyrus.0.log> --report <folder>\compare_<run>.json`.

While a baseline is open (step 2 done, step 6 not yet), the test runner installs and launches nothing: `testqueue.py
run` stops with `a vanilla baseline is open in <folder>`. A launch would install our plugins and load them into the
baseline's session.

- The runner also stops when it cannot read the note, or the record the note names (a drive that is not there, or a
  damaged `baseline.json`): a baseline may be open. Restore it, or remove the note once you know none is open.
- It checks before its installs, and again just before the launch. A `prepare` run while the runner installs can
  still find our plugins ticked by those installs, and `collect` then catches them.
- The run's status says why it stopped (`stopped: baseline: ...` in `state.json`).
- It reads a note as stale, and runs, only when the note's baseline folder is there without a record, or the record
  says it was restored.
- When `prepare` turned nothing off (only the game's own plugins were on), it writes no note, and nothing stops the
  runner. A session the runner starts then still shows in `collect`'s checks: our names in the log, a plugin ticked
  again, or an SFSE log.

`prepare`, `collect` and `restore` run one at a time (the lock, section 1). When one says another is running, wait
for it to finish, then run it again.

### What `prepare` refuses (nothing is changed)

- Starfield is running, or its state is unknown.
- Another `prepare`, `collect` or `restore` is running (the lock), or the lock cannot be made in the state folder.
- The out folder already holds a baseline. When that one was never restored, its record holds the only copy of
  Plugins.txt as it was, so `prepare` says to run `restore` on it first.
- The out folder is in the game folder, a My Games folder or Plugins.txt's folder.
- The open-baseline note names a baseline that may be open, wherever its folder is. That is one never restored, or
  one whose note or record cannot be read (a drive that is not there, or a damaged file). `prepare` would write over
  the only pointer to it, so restore it first, or remove the note once you know none is open. `check` says so too.
- A baseline of the same Plugins.txt in a folder next to the out folder (the same parent folder) was never restored.
- None of ours is on, but our plugins are off in Plugins.txt already (another mod may be on). That is what an earlier
  baseline that was never restored leaves behind, when its note is gone too. `--allow-off` goes ahead when no baseline
  turned them off: the game also adds a new plugin it finds in `Data` unticked (verified, `sfstack.md`).
- Plugins.txt is read-only, or a link, when there is something to turn off. `prepare` would put a plain file in the
  link's place, and `restore` would bring the bytes back but not the link.
- A line of Plugins.txt would still read as active once unticked, such as `* *Mod.esm`.
- Plugins.txt is not UTF-8: `prepare` cannot untick bytes it cannot read (that the game writes UTF-8 is a hypothesis,
  section 6).
- There is no `Data` folder under `--starfield`, or `LOCALAPPDATA` is not set (not Windows).
- The `[Papyrus]` logging keys are not in effect. Without them the session writes no log, and
  `scripts/bridge/make_bridge.py ini` sets them.
- `loaders` fails or is UNKNOWN. That means an `sTestFile` is set in an INI (the game then ignores Plugins.txt), a
  `Starfield.ccc` lists a mod (it loads first, whatever Plugins.txt says), a plugin in `My Games\Starfield\Data` is
  named like one in `Data` (unless that folder is linked to `Data` itself, as Vortex can do), or no My Games folder
  was found.
- `start` fails with the start pinned as vanilla (`start_overrides: []`), or is UNKNOWN. A FAIL means a plugin that
  loads anyway (a `.ccc` one) overrides `StartupQuest_DO`, `MQ101` or `MQ101Debug`. UNKNOWN means such a plugin cannot
  be read.
- Starfield was started while `prepare` read the game folder (hashing the built-in plugins takes a while).
- The open-baseline note could not be written. The record is removed.
- Starfield was started after that read, before Plugins.txt is written: `prepare` checks once more, last. The record
  and the note are removed, and Plugins.txt is as it was.
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
| Rewritten, with no plugin the game does not ship ticked | Keeps the rewrite as `Plugins.txt.at-restore` in the out folder (it can hold the owner's own edits), then writes the recorded bytes over it. When a copy is there already (an earlier restore that did not finish), the new one is `Plugins.txt.at-restore.2`, then `.3`: no copy is written over. |
| Gone | Writes the recorded bytes, and makes its folder again when that is gone too. |
| With such a plugin ticked again | Refuses and names it (the session may not have been vanilla). `--force` keeps the current file as `Plugins.txt.at-restore` (or the next free number), then writes the recorded bytes. |

Every restore records its time, which ends the time `collect` takes logs from, and the plugins the game does not
ship that were ticked in the file it found. When there were any (the recorded bytes count too: someone put them
back before `restore` ran, and nobody knows when), `collect` after it keeps no log as the baseline. A log collected
before `restore` was checked against Plugins.txt then.

It also records the SFSE logs written in the baseline's time (after `prepare`, up to the restore). A later start
through `sfse_loader.exe` can write over SFSE's log, so `collect` after a restore counts what the restore found as
well as what it finds itself.

A Plugins.txt that is not UTF-8 (the game may write a name in another encoding) is read with the odd bytes
replaced, so a ticked plugin is still found and `--force` still works.

Every write is guarded: the file must still be the one just read (`fo4sf.launcher.restore.write_plugins_txt`). When
Plugins.txt changes during `restore`, or cannot be written, nothing is written, and `restore` says to run it again.
A restore removes the open-baseline note when it names this baseline. Nothing here touches a plugin, an archive or
an INI.

Before it writes Plugins.txt, `restore` checks the record's copy against the sha256 `prepare` recorded, and refuses a
record that was changed or damaged since. Then it notes in the record what it found and when. When it stops after
that note and before the record is updated (Ctrl+C, a closed window, a power cut, or a record that cannot be
written), whether Plugins.txt is back yet or not, `status` says so and when, `collect` refuses, and the open-baseline
note stays, so the runner still launches nothing. Running `restore` again finishes the record with what the first run
found and its time, so the baseline's time still ends at the restore that stopped, not at the rerun.

- When Plugins.txt has the same plugins on in other bytes since (the game's rewrite at startup drops the plugins that
  load on their own; another program can write them in another order), the rerun keeps that file as
  `Plugins.txt.at-restore` (or the next free number), writes the recorded bytes back, and finishes the record.
- When other plugins are on now, it refuses and names the restore that stopped. `--force` keeps the current file and
  writes the recorded one back. Either way, the baseline's time ended at the restore that stopped, with what it found
  then.

`restore` also closes the note of a baseline whose folder was moved since `prepare`: the note names the same
Plugins.txt and prepare time. The copy `restore` keeps of the file it writes over is on disk before Plugins.txt is
written.

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

Beside each `both` and `both_place` kind, the report gives the baseline's count: the same kind's lines for `both`,
and all the baseline's lines at that script line for `both_place`. A kind that came 10 times as often as in the
baseline, or more, is marked `10x or more`: a Starfield error that comes far more often in our run is still ours to
look at.

`ours` goes by name. A reference of ours can print with no name (`[ (0A001234)]`), and then its kind is not found as
ours: it is `both_place` at a script line where vanilla errors too, and `starfield` elsewhere. That it can is a
supported hypothesis: in the verified log sample (the `fo4sf.core.papyrus_log` module doc), the quests print their
EditorIDs and one object prints none.

A group says where a message came from, not why. A Starfield error that comes only in our run can still be one that
Starfield makes later in its own opening, if the baseline stopped before that point. That is why step 4 notes where
the baseline stopped.

`compare` also re-reads the built-in plugins' names and sizes and Starfield.exe's size and sha256, and says when they
differ from the recorded ones (a Starfield update, or a new Creation). Then it is time for a new baseline. When the
baseline also turned off plugins that are not ours (another mod that was on), `compare` names them: in a run with them
on, their errors count as Starfield's own.

`compare` refuses a run log that is not there. Its `--report` must be a `.json` file of its own: never one of the
baseline's own files (the record, the kept logs, `Plugins.txt.at-restore`), the run's log, Plugins.txt or the
open-baseline note, and never in the game folder, a My Games folder or Plugins.txt's folder. It writes over no file
but an earlier compare report, so it never writes over another baseline's record or a queue's file.

## 6. Assumptions

- **Verified:**
  - The log format. Each message is a time of day in brackets, then `error:`, `warning:` or a note, then an optional
    `stack:` with tab-indented frames. The source is Install's copy of the 28 Oct run 3 log, on Starfield 1.16.244.
  - `Papyrus.0.log` is the newest log and `Papyrus.1.log` the one before
    (docs/research/framework/newgame-notes/05-tools-ecosystem.md, from the Nexus logging guide). How the game moves
    one on (a rename, or a copy with a new time) is not known, and `collect` does not need it: a log that was there at
    `prepare` is known by its sha256.
  - The loader rules. `Starfield.ccc`, `sTestFile`, the rewrite at startup and the My Games Data rule are all from
    `sfstack.md`. So is the game adding a new plugin it finds in `Data` unticked, and resetting a read-only
    Plugins.txt.
  - The start records. In Starfield.esm, `StartupQuest_DO` is 00562D (DFOB), `MQ101` is 003448 and `MQ101Debug` is
    0A7D31 (`fo4sf.core.loadset` module doc).
  - Loose files in `Data` do not load on the PC, so the loose files an experiment left there stay out of the baseline.
    Its `Starfield.ini` sets `sResourceDataDirsFinal=STRINGS\` (read on 11 Oct 2026, docs/JOURNAL.md), and the 16 Oct
    playtest's loose install loaded none of its meshes or terrain (docs/owner/playtest-issues.md, row 9). `check`
    does not read that setting: an INI that lets loose files load (the loose-file recipe in `sfstack.md`, an empty
    `sResourceDataDirsFinal=`) would let them into the baseline too.
- **Supported hypothesis:**
  - A plugin copy in `My Games\Starfield\Data` stands in for the one in `Data`. The loader rule implies it, so the
    `loaders` check refuses either way.
  - SFSE writes its log to `My Games\Starfield\SFSE\Logs` (`sfse.log`, from SFSE's readme as
    sfse/FOCCSidecar/README.md cites it), and so do our SFSE plugins (sfse/FOCCPing/README.md). A plain start writes
    nothing there.
- **Hypothesis:**
  - Plugins.txt is UTF-8, as the game writes it. `prepare` refuses a file that is not, and `restore` reads one with
    the odd bytes replaced.
  - An archive of ours left in `Data` (`<plugin> - Main.ba2`) stays out while its plugin is unticked. That it loads
    with its plugin is verified (docs/spikes/S2-S4-S9-plugin-units-loading.md). `check` does not read the INI archive
    lists (`sResourceIndexFileList`, `sfstack.md`), which could load one by its name.
  - None of Starfield's EditorIDs or script names starts with FO4 or FOCC (none of its plugins does). The first
    baseline tests it: `collect` keeps no log that names one as the baseline.
- **Unknown:**
  - Whether the game writes the end of its log when it is killed instead of quit. Step 4 quits from the game's menu
    for that reason, and `collect` refuses while the game runs.
  - Whether the game reads a `Starfield.ccc` that starts with a byte-order mark. The `loaders` check reads past the
    mark, so the first name still counts as listed.
  - Whether the game reads the `[Papyrus]` keys from a `StarfieldCustom.ini` saved with a byte-order mark before its
    first line. The check reads a `[Papyrus]` header right after the mark as not there, so `prepare` refuses.
  - Whether the game reads `sTestFile` from its language INIs (`sfstack.md` question 18 lists them). The game folder
    holds `Starfield_de`, `_es`, `_fr`, `_it`, `_ja`, `_pl`, `_ptbr` and `_zhhans.ini` (verified on the owner's
    1.16.244 install, 29 Oct 2026; English has none). The `loaders` check reads them, so it only refuses more.
