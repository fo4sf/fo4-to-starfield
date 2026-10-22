# Launcher window — Codex, issue #456

This first window is a front end to the existing launcher, with Status, Settings and Command log tabs.
It ships no assets and adds no build, install, game-start or crash-watcher implementation.

```text
python scripts/launcher.py gui --settings <settings.json>
python scripts/launcher.py gui --settings <settings.json> --recipe <recipe.json> --fo4-data <Data> --starfield <game>
```

The recipe and game folders can also be entered in the window. Repeated `--fo4-data` arguments become one folder
per line. `--set name=value` supplies recipe variables for Build status. Paths are passed as individual subprocess
arguments, with no shell. Status and installation checks request no report file and run on a worker thread.
The window shows their output, including refusals and nonzero exit codes.

Settings controls, labels, choices and cost captions come from `settings.SPEC` and `settings.LABELS`. Save uses the
existing `settings --settings ... --set ...` command, with only the fields the player changed. An unchanged Save
does not call the command or write a file, so it preserves the exact bytes of an existing settings file and does not
create a missing one. The CLI allows an incomplete setup to be saved; its `play would refuse` messages are shown,
and the Play button stays disabled until `settings.problems()` is satisfied. Reload settings discards unsaved edits
and reads the file again. Play refuses an externally changed settings file until it is reloaded.

Play delegates to the existing `play --settings ... --starfield ...` command: that command owns Steam/exe routing,
plugin toggling, Papyrus logging and the crash watcher. The window disables Play while a command is running,
the process check is unknown or failed, Starfield is already running, settings have unsaved changes, or settings
validation refuses play. The CLI retains its own pre-launch checks. The window does not claim an atomic lock with
other programs changing the settings or starting the game.

The log tab retains the most recent 2,000 lines. Open crash log folder opens the saved dump folder, if it exists.
Closing the window during a command is refused: it never terminates a game or a watcher to close its UI.

## Delegation and review boundaries

| Window use | Existing entry point |
| --- | --- |
| Defaults, loading, coercion, setup problems | `settings.load`, `settings.coerce`, `settings.problems` |
| Save changed settings | `launcher.py settings` → `cmd_settings` → `settings.assign` / `settings.save` |
| Build status | `launcher.py status` → `cmd_status` → `driver.load_recipe` / `driver.status` |
| Installation checks | `launcher.py detect` → `cmd_detect` → `detect.detect` |
| Play | `launcher.py play` → `cmd_play` → `crashwatch.play` |
| Read running game PIDs | `crashwatch.System.pids` |
| Open log folder | OS folder opener; no game or watcher control |

Tkinter is imported only when the window is opened. Importing the module and `gui --help` work without tkinter or a
display. The model and command runner are tested headlessly; real settings-CLI tests use synthetic temporary files.
They never run Play, Steam, ProcDump, detection against an installed game or a private profile.

Independent QA and Claude's Windows PC checks remain required: actual window layout/focus/scrolling, live process
polling, folder opening, both real launch routes, watcher attachment through game exit and visible error handling.
Headless tests do not establish those results. Existing `settings.py`, `crashwatch.py` and existing subcommand
behavior are unchanged by this proposal.

Local validation, October 22: the final GUI tests pass (15 cases), and guard/diff checks pass. The full pytest attempt
returned 2,780 passed, 85 skipped, 47 failed and one collection error. All 47 failed node IDs and the collection error
also reproduce in a clean checkout of the unchanged base. They include Windows campaign fixtures expecting a
nonexistent Python path, the existing CLI dry-run test expecting a closed game, a lease-log expectation, and pytest
collecting a helper as a test. Those files were not changed for this window. A full green suite and independent GUI
review remain gates; the baseline failures are retained rather than relabeled as passes.
