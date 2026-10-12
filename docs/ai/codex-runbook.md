# Codex runbook: unattended test hand-over

When Claude has been inactive for the watchdog's threshold (default 3 hours, `C:\Modding\testqueue\watchdog.json`),
`scripts/game/watchdog.ps1` starts the unattended test chain itself and then calls Codex (`codex exec`, sandbox
workspace-write in `C:\Modding\testqueue`, network on for `gh`) with a pointer to this file. The owner asked for this
hand-over on 2026-10-11: if Claude makes no changes for a while (out of credits or busy elsewhere), Codex makes sure the
test program runs and reports.

## What runs without any agent

- `C:\Modding\testqueue\chain.ps1` reads `C:\Modding\testqueue\chain_queue.txt` (one queue per line, `?name` = optional)
  and runs each queue with `scripts\game\testqueue.py run` from the integration worktree
  `C:\Users\great\Desktop\codehell\fo4-to-starfield-wt\integ` (pinned build `C:\Modding\staging\integ_1011`).
- Owner controls stay in force: the game is launched only after 15 min without keyboard/mouse input (or right after the
  runner's own input); a Starfield the runner did not start is never touched (the chain waits until it is closed); a STOP
  file (`C:\Modding\testqueue\STOP_ALL`, `%LOCALAPPDATA%\fo4-ai-team\state\testqueue.STOP`) or a Resource Guardian
  pause/stop ends it.
- Results per queue: `C:\Modding\testqueue\<queue>\` with `state.json`, `results.jsonl`, `run.log`, `report.md`,
  `tests\<id>\a<n>\` (screenshots, `obs.json`). Chain log: `C:\Modding\testqueue\overnight.log`.

## What Codex does (and only this)

1. Status: for every queue folder in `C:\Modding\testqueue` that has a `queue.json`, run
   `C:\Modding\venv-render\Scripts\python.exe C:\Users\great\Desktop\codehell\fo4-to-starfield-wt\integ\scripts\game\testqueue.py status --queue <folder>`,
   and read the last 30 lines of `overnight.log` and `watchdog.log`. Is the chain running? (process with `chain.ps1` in its
   command line). Which queue is active, how many tests are done?
2. Reports: for every queue that has `results.jsonl`, run
   `... testqueue.py report --queue <folder>` (writes `report.md`/`report.json` in that folder) and read `report.md`.
3. Post ONE comment to GitHub issue #32 (`gh issue comment 32 --repo fo4sf/fo4-to-starfield --body-file <file>`), starting
   with `Codex:`. Contents: chain state (running / waiting for an idle PC / waiting for the owner's own game / stopped and
   why), per queue PASS / FAIL / INCONCLUSIVE counts, the top 5 ranked problems (kind, class, model, count, one example
   with its folder), terrain results (heights vs expected) and NPC results (verdicts) if those queues ran. Keep it short;
   numbers, no speculation. Write the same text to `C:\Modding\testqueue\codex_report_<date>.md`.
4. If the chain is NOT running, `chain_queue.txt` still lists queues, no STOP file exists and no Starfield is running:
   say so in the comment (the watchdog restarts the chain on its next check; Codex does not start it: from the
   sandbox the chain cannot write to the game folder).

## What Codex must not do

- No code or repo edits, no commits, no PRs, no merges; no edits to `chain_queue.txt`, queue folders or staging folders.
- No input to Starfield (no `input.ps1`, `qstep.ps1`, `cycle.ps1`, console commands), no deploys, no changes to the game
  folder, `Plugins.txt`, ini files, the Resource Guardian or any scheduled task / automation.
- Never write the owner's previous GitHub username anywhere; say "the owner".
- Nothing involving money, passwords, outreach beyond the one #32 comment.

## For Claude when it is back

Touch `C:\Modding\testqueue\claude_heartbeat.txt` (or commit) while working, so the watchdog does not fire; read the
newest `codex_report_*.md` / `codex_handover_*.md` and the #32 comment first.
