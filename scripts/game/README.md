# In-game test tools (Windows)

Drive a running Starfield from scripts to test converted content, without keyboard macros or mods.

| Script | What it does |
|---|---|
| `input.ps1` | Sends keys, text, mouse moves and clicks to the game. **Refuses to send anything unless Starfield is the foreground window** (checked before every step), so it can never type into another app. Starfield ignores `SendInput` keyboard events; set `$env:LEGACY='1'` to use `keybd_event`, which works. Steps: `key:enter`, `type:coc X`, `hold:w,1500`, `move:dx,dy`, `click:x,y`, `wait:ms`, separated by `|`. |
| `shot.ps1`, `shot_region.ps1` | Screenshot (downscaled) / native-resolution capture of a screen region (for OCR). |
| `ocr.ps1`, `ocr_prep.py`, `parse_getpos.py` | Read console replies with the built-in Windows OCR. The console font is light grey (~150) over a dimmed game (~85): `ocr_prep` keeps bright, unsaturated pixels as black-on-white. The parser handles the OCR's quirks (labels and numbers in separate columns, `.` read as a space). |
| `readpos.ps1` | Opens the console, runs `player.getpos x/y/z`, reads the answer by OCR, closes the console. Prints `x y z` (metres). |
| `probe_points.py`, `probe.ps1`, `probe_map.py` | **Collision mapper.** Picks floor-like pieces from an exported FO4 cell, teleports the player 1.5 m above each (`player.setpos`, god mode on), waits, reads the height. `PASS` = landed on it, `FALL` = dropped through (missing collision), `HELD` = stopped well above (e.g. the stair top). Results to CSV and a top-down map image. |
| `walk_route.py`, `walk.ps1` | **Walk check (issue #29).** Chains nearby floor pieces into short aimed steps and holds W. A rise too tall to step ends the route instead of teleporting onto it. Does not toggle god mode or close the game. Exit 0 only when every leg arrives. |
| `cycle.ps1` | Close game, redeploy staging (`deploy_starfield.py`), launch via Steam, load the last save, clear the first-console-use dialog, `coc` into a cell, screenshot. |
| `testqueue.py`, `qstep.ps1` | **Queued test runner** for unattended batches (no AI calls). `plan` turns one pinned build into tests (stairs, falls, doors from both sides, movable items, travel through load doors); `run` launches the build with `cycle.ps1`, uses a dedicated save per build, turns god mode on, runs one `qstep.ps1` per test, judges PASS / FAIL / INCONCLUSIVE (a missing read or screenshot is never a PASS), checkpoints after every test (`state.json`, `results.jsonl`, per-test folders with screenshots and logs) and resumes where it stopped; `report` ranks the problems. It stops, resumable, on a STOP file, a Resource Guardian pause/stop, owner input or another window in front (or waits for an idle PC with `--wait-for-idle`). `plan-terrain` / `plan-npc` plan experiment tests from a plan.json (terrain heights; `npc_nav`: spawn a vanilla actor, make it walk to the player, sample, remove it). See docs/ai/test-queue.md. |
| `parse_npc.py` | Reads one npc_nav console session (PickLastRef's id after `plr`, `GetIsID`, `GetSelf`, `getpos`, `GetDisabled`) from OCR text in either OCR layout (inline, or labels first and values after), told which values the session's commands produce; nothing before the session start (its `ClearConsole` echo, which does not clear the screen, or its first command's echo) is read; tolerant of l / 1 / \| read for I. |
| `exp_install.py` | Installs a staged experiment reversibly; `--pack` puts the whole `Data\` tree, textures included, into one General, stored `<plugin> - Main.ba2` (vanilla's layout for terrain textures), built outside the staged folder. |

Requirements: Starfield running windowed/borderless on the primary screen; the player in the cell; Python with numpy + Pillow
(`$env:FO4SF_PYTHON` can point at a venv's `python.exe`). The console achievements warning appears on the first console command
of a session and swallows input: run one harmless command first (`cycle.ps1` does).

Lessons: `con` is a reserved Windows file name (`con.png` cannot be opened); `scof` accepts a name but never wrote a file here,
hence the OCR route; walking with held keys drifts and gets stuck, teleporting with `player.setpos` is exact.
