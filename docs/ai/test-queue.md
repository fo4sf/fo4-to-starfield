# Queued game-test runner

Purpose: collect in-game evidence while no AI agent is running (usage limits, nights), so the next session starts from
results and a ranked problem list instead of spending its own time driving the game. Nothing in the loop calls a model.

## Use

```powershell
$py = 'C:\Modding\venv-render\Scripts\python.exe'
# 1. plan: one pinned build (staging folder with FO4Port.esm, manifest, formids, cell exports, routes_<cell>.json)
& $py scripts\game\testqueue.py plan --staging C:\Modding\staging\<build> --out C:\Modding\testqueue\<batch> --per-cell 12
# 2. run (resumable: run the same command again to continue)
& $py scripts\game\testqueue.py run --queue C:\Modding\testqueue\<batch> --wait-for-idle --refocus --max-hours 8
# 3. read
& $py scripts\game\testqueue.py report --queue C:\Modding\testqueue\<batch>
```

Stop it at any time: create the file `C:\Modding\testqueue\<batch>\STOP` (or `%LOCALAPPDATA%\fo4-ai-team\state\testqueue.STOP`
for every batch), or `python tools\ai-team\guardian\guardian.py pause` / `stop`. Using the keyboard or mouse, or putting
another window in front of the game, also stops it (or makes it wait for an idle PC with `--wait-for-idle`).

## What it tests (owner's priority order)

| kind | from | PASS | FAIL | INCONCLUSIVE |
|---|---|---|---|---|
| stairs | `routes_<cell>.json` (routes.py) | rose at least 80% of the flight | STUCK, FALL | start not reached, misread |
| fall | `probe_points.py` floor points | landed within 0.6 m | dropped more than 3 m | landed 0.6-3 m lower, held above, pushed away |
| door | `routes_<cell>.json`, both sides | crossed the plane after an OPEN this attempt | BLOCKED, NOPROMPT, FALL | already open, misread |
| movable | manifest `movable` items placed in the cell | item moved at least 5 cm when walked into | did not move although reached; fell | player missed it |
| travel | load doors whose XTEL partner is in the same build | arrived within 4 m of the arrival point | no prompt; E did nothing | start not reached, arrived elsewhere |

Every verdict needs its observations: a position that was not read or a screenshot that is missing makes the test
INCONCLUSIVE, never PASS. INCONCLUSIVE tests are retried once more at the end of the queue (`--max-attempts 2`); a FAIL
is final. A game crash during a test is recorded (class CRASH) and the game is relaunched (at most `--max-relaunch`).

## Controls (checked before every launch and every test)

- STOP file, Resource Guardian mode (`paused` / `stopped`, or an unreadable database) stop the run.
- The game is launched only after `--min-idle` seconds (default 900) without keyboard or mouse input, and only through
  `cycle.ps1`. A Starfield the runner did not start (the owner's own session) is never touched: the run stops.
- Owner activity: input the runner did not send, or another window in front of the game, stops the run (or waits with
  `--wait-for-idle`; with `--refocus` it then brings its own game window back to the front once, never another app).
  Every step runs with `FO4SF_NO_FOCUS_STEAL=1`, so `input.ps1` refuses to pull the game in front during a test.
- `queue.json` `"hours"` limits the allowed hours (default `[[0, 24]]`); `--max-hours` and `--max-tests` bound a run.
- The build is pinned: `queue.json` records the SHA-256 of `FO4Port.esm`; the runner will not launch a staging folder
  whose plugin changed. The dedicated save `fo4sf_test_<build id>` is created on the first launch and loaded on later ones.

## Output (in the queue folder)

`queue.json` (tests, build, save), `state.json` (checkpoint), `results.jsonl` (one line per attempt), `run.log`,
`tests/<id>/a<n>/` (spec, raw `obs.json`, screenshots, step log), `report.md` / `report.json` (tally per kind and the
ranked problem list: FAIL groups by severity x count, then INCONCLUSIVE groups).
