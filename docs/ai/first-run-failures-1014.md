# Why scripts failed on their first run (14-15 Oct 2026) and what now stops each one

The owner asked, after watching the evening's runs: "figure out why some of your scripts you're trying to run aren't
working in the beginning." Every first-run failure of 14 Oct, its cause as established (verified = reproduced or read
in the evidence; hypothesis = consistent with the evidence, not reproduced), and the guard that is now in place.

| # | What failed first | Cause | Guard now | Status |
|---|---|---|---|---|
| 1 | Both walks of `walk_core64c_1014` "position not read" before the first step | The HUD's compass dial crosses the console text; Windows OCR put the labels in one line and the numbers in another, so the session-scoped parser saw labels without values | `ocr.ps1` rebuilds screen rows from the engine's word boxes (`ccddf80`); then the bridge replaced OCR position reads altogether | verified on the captures; superseded by the bridge |
| 2 | Every coc froze the night of 13 Oct | The runner's second E after Continue answered Starfield's load-order dialog with "Save", which rewrote Plugins.txt with the experiment plugins inactive | `loadorder.ps1` answers "Current" and checks the highlight; `cycle.ps1` exits 8 when a plugin went inactive (`68adac4`) | verified in game |
| 3 | My first bridge go/no-go: the console never opened, the walk key worked | `input.ps1` sends keys through `keybd_event` only when `LEGACY=1`; every runner script sets it, my direct call did not; Starfield takes the console key and typed text only through that path | `input.ps1` defaults to the legacy path; `LEGACY=0` opts out (`600b4f3`) | verified (the next call opened the console) |
| 4 | `make_bridge.py ini` "file not found" while creating `StarfieldCustom.ini` | Windows Controlled Folder Access blocks python.exe and powershell.exe from writing in Documents and reports it as a missing file (Defender event 1123) | `ini` explains the block and writes the `[Papyrus]` keys into the game folder's `Starfield.ini` with a backup (`32a5f5b`) | verified (event log; the fallback worked) |
| 5 | `set FO4SF_Cmd to 7` "Unknown variable", also by form id | The game keeps no EditorID strings for a plugin's GLOB records (`help FO4SF_Cmd 4` finds nothing); `set` takes names only | The command channel is `cgf "Debug.TraceUser"` / `cgf "FO4SF_Probe.*"` (both verified in game); the global stays for a later Papyrus-side setter | verified |
| 6 | `bridge_probe_1015` a1/a2: arrival read 30 s old, probe reads "40 s old", verdict INCONCLUSIVE | Two causes. (a) Freshness was the file's mtime, which the game touches while paused without writing a line. (b) The real one: on a planet the script prints the worldspace form id as a negative number (Papyrus signed int, load index FF..); the line regex accepted digits only, so **no planet line parsed** and every read fell back to the last Vault line | (a) freshness is the line's own clock stamp (`f772fd5`); (b) ids accept a sign, with the real line as a test (`600b4f3`); a 330 s live poll showed the file itself is not buffered | verified: `bridge_probe_1015c` PASS, the walk PASS |
| 7 | `Read-Settled` gave up 2 s before the first line after a loading screen | The caller's readpos retry count (3) was passed to the bridge read as its patience | A bridge read keeps at least 12 tries (~8 s) whatever the caller passes (`600b4f3`) | verified (the walk's arrival read) |
| 8 | The walk at 00:00:03 stopped at leg 17 "owner switched windows" | Something took the foreground from Starfield for a moment at midnight (not the owner: no input; cause not identified: hypothesis, a scheduled task or a toast) | None needed: the input guard did its job (never types into another window) and the runner re-ran the test, which passed | hypothesis (cause), verified (guard) |
| 9 | `make_cave_core64c.py check` refused: "--out is required" | My call left the option out; the README's one-line recipe does not show it | the usage line of `make_cave_core64c.py` shows `--out` | fixed |
| 10 | `python -m unittest tests.test_testqueue` errored on `ba2_fixture` | The fixture module lives in `tests/`, importable under `discover` but not under a module-name run | The pack test puts `tests/` on `sys.path` itself (`600b4f3`) | verified |
| 11 | `test_archive_identity::test_archive_modified_during_hash_is_rejected` failed twice in full-suite runs | A timing window: the test changes a file while hashing it; under CPU load (the sandbox suite running beside it) the change lands before the hash starts. Passes alone every time | Not touched (Codex's area); noted on #32 for Codex | hypothesis |
| 12 | `Start-Grok-FO4SF.ps1` refused: "Grok is already running" | Codex had launched Grok headless from a hidden pwsh at 19:37; that instance never got a reply (weekly credits at 100 %) and sat polling billing | Stopped it; the visible launcher opened at 22:02; `grok-usage.txt` sets the budget rules | verified (its session log: 1 user message, 0 replies, 1 error) |

## The pattern

Nine of the twelve were in how the runner observes and drives the game (OCR, key paths, dialogs, log parsing), not
in the conversion. Three were my own invocation mistakes (3, 9, 10). The bridge removes the whole OCR class for
positions; what remains on OCR is pop-ups, HUD checks and reference reads, and the probe result (cgf loads
`FO4SF_Probe`) gives a route off OCR for the reference reads too.

Two rules that would have saved most of the evening, now in the docs and memory:

1. **A first-run script is tested against real captured evidence before a night is spent on it**: the dial split, the
   signed id and the mtime freshness were all visible in captures and logs the runner already kept.
2. **Driving the game by hand uses the runner's own scripts with the runner's own environment** (`LEGACY=1`,
   `FO4SF_PYTHON`, the STOP files), never bare calls.
