# Codex runbook: unattended test hand-over

When Claude has been inactive for the watchdog's threshold (default 3 hours, `C:\Modding\testqueue\watchdog.json`),
`scripts/game/watchdog.ps1` starts the unattended test chain itself and then calls Codex (`codex exec`, sandbox
workspace-write in `C:\Modding\testqueue`, network on for `gh`) with a pointer to this file. The owner asked for this
hand-over on 2026-10-11: if Claude makes no changes for a while (out of credits or busy elsewhere), Codex reports the
existing test evidence. Claude retains the live controller; this hand-over grants no game/control ownership.

## What runs without any agent

- `C:\Modding\testqueue\chain.ps1` reads `C:\Modding\testqueue\chain_queue.txt` (one queue per line, `?name` = optional)
  and runs each queue with `scripts\game\testqueue.py run` from the integration worktree
  `%USERPROFILE%\Desktop\codehell\fo4-to-starfield-wt\integ` (pinned build `C:\Modding\staging\integ_1011`).
- Owner controls stay in force: the game is launched only after 15 min without keyboard/mouse input (or right after the
  runner's own input); a Starfield the runner did not start is never touched (the chain waits until it is closed); a STOP
  file (`C:\Modding\testqueue\STOP_ALL`, `%LOCALAPPDATA%\fo4-ai-team\state\testqueue.STOP`) or a Resource Guardian
  pause/stop ends it.
- With the controller lease switched on (`lease_dir` in `watchdog.json`; docs/ai/leader-core.md section 6) the watchdog
  claims the lease as `watchdog` before it starts the chain and never while someone else holds one.
- Results per queue: `C:\Modding\testqueue\<queue>\` with `state.json`, `results.jsonl`, `run.log`, `report.md`,
  `tests\<id>\a<n>\` (screenshots, `obs.json`). Chain log: `C:\Modding\testqueue\overnight.log`.

## What Codex does (and only this)

1. Status is read-only: read existing `chain_queue.txt`, `queue.json`, `state.json`, `results.jsonl`, and the last 30
   lines of `overnight.log` and `watchdog.log`. Inspect process command lines to determine whether the chain is running.
   State which queue is active and how many tests are done, with the record paths and timestamps. Missing, unreadable,
   partial or changing records are unresolved; do not repair or rewrite them. Do not run the queue runner for status.
2. Reports: read existing `report.md` / `report.json` and any existing failure summaries. Check their timestamps and
   source pins against the latest state/results; label stale or mismatched reports explicitly. Never run
   `testqueue.py report`, judges, `route_eval.judge`, rescoring, or evidence regeneration, including on active queues.
   If no current report exists, summarize only recorded results; label missing verdicts INCONCLUSIVE and do not invent
   scores. Keep previously recorded verdicts unchanged.
3. Post ONE comment to GitHub issue #32 (`gh issue comment 32 --repo fo4sf/fo4-to-starfield --body-file <file>`), starting
   with `Codex:`. Contents: chain state (running / waiting for an idle PC / waiting for the owner's own game / stopped and
   why), per queue PASS / FAIL / INCONCLUSIVE counts, the top 5 ranked problems (kind, class, model, count, one example
   with its folder), terrain results (heights vs expected) and NPC results (verdicts) if those queues ran. Keep it short;
   numbers, no speculation. Write the same text to `C:\Modding\testqueue\codex_report_<date>.md`.
4. If the chain is NOT running, `chain_queue.txt` still lists queues, no STOP file exists and no Starfield is running:
   say so in the comment (the watchdog restarts the chain on its next check; Codex does not start it: from the
   sandbox the chain cannot write to the game folder).
5. Preserve #89: runner exit **4** means unfinished work, **0** means complete/dry-run. An old exit 0 does not prove an
   old queue completed; use its pinned state and pending count. Do not restart, resume, re-plan, clear pending work, or
   normalize exit codes. A successful Codex reporting child says nothing about game-test completion.

## What Codex must not do

These restrictions apply to the unattended reporting child. They do not prohibit separately authorized parent
source repairs, validation, or commits.

- No code or repo edits, no commits, no PRs, no merges; no edits to `chain_queue.txt`, queue folders or staging folders.
- No re-running judges, rescoring, rewriting existing reports, or modifying active queues/evidence.
- No input to Starfield (no `input.ps1`, `qstep.ps1`, `cycle.ps1`, console commands), no deploys, no changes to the game
  folder, `Plugins.txt`, ini files, the Resource Guardian or any scheduled task / automation.
- Never write the owner's previous GitHub username anywhere; say "the owner".
- Nothing involving money, passwords, outreach beyond the one #32 comment.

## Handover helper and application review

`scripts/game/codex_handover.ps1` is a dot-sourceable helper with no action on load. Its exact public call is:

```powershell
. <checkout>\scripts\game\codex_handover.ps1
Invoke-CodexHandover -ConfiguredExe $null -Workspace <existing-report-directory> `
  -Prompt <full-prompt-string> -OutputPath <new-report.md> -LogPath <watchdog.log> -ExecTimeoutMilliseconds 600000
```

`ConfiguredExe` is optional (default `$null`). Automatic discovery checks all `codex.exe` PATH applications first,
then complete bundles directly under `%LOCALAPPDATA%\OpenAI\Codex\bin`, newest directory modification time first.
No hashed directory is pinned. Each executable needs sibling `codex-code-mode-host.exe` and `codex-command-runner.exe`.
An explicit absolute `codex_exe` is authoritative: missing executable/companions, empty or malformed configuration
refuses the handover without silently choosing another executable. Windows drive-relative paths such as `C:foo`
and root-relative paths such as `\foo` are refused even when they resolve to a complete bundle. A configured path
must include the drive root (`C:\...`) or a full UNC share (`\\server\share\...`). Use JSON `null` (or omit the key) for discovery.
The obsolete copied `%USERPROFILE%\.codex\.sandbox-bin\codex.exe` is incomplete and must not be explicitly retained.
An absent watchdog config retains automatic discovery. A present config must be readable, valid JSON with an object
root; malformed, unreadable, `null`, array or scalar roots set a derived handover-only invalid marker. Codex handover
then refuses before discovery, probes or exec. The inherited chain-start/inactivity defaults remain unchanged, and a
valid object's existing policy overrides still apply. Config JSON cannot override the derived invalid marker.

Before inference, the selected bundle must pass `--version` and `exec --help` (15 seconds each). A nonzero exit,
unrecognized/empty version, missing required exec flags, timeout or start failure refuses the handover. There is no
fallback after a failed probe. Probes establish CLI/bundle compatibility; they do not establish authentication or
successful inference.

The child runs Hidden with stdin/stdout/stderr redirected, shell execution disabled and Windows native arguments
quoted individually. The full UTF-8 prompt goes through stdin to
`codex exec --skip-git-repo-check -C <directory> --sandbox workspace-write -c sandbox_workspace_write.network_access=true -o <temporary-report> -`.
This preserves the original existing report directory and network scope. See
[official non-interactive documentation](https://learn.chatgpt.com/docs/non-interactive-mode) for `codex exec -` and
workspace-write. The workspace must exist; report and log must be directly inside it, and the report must be new.
The helper does not create directories or change user/private configuration.

The CLI writes a reserved, unique `.codex_handover_<guid>.pending.md` in the existing report directory. After exit 0
and a nonempty temporary report, the helper publishes with the two-argument `File.Move`, which refuses an existing
final path. A final report that appears during probes or exec is preserved, and publication refuses rather than
overwriting it. An initial stale final report still refuses before probes. Failed-child, timeout and publication
failure temporary reports remain in place as diagnostic evidence, and the failure log names their paths.

The call waits for the child to finish and returns exactly one Boolean: `$true` only for exit 0 and successful
publication of a nonempty new report; `$false` for refusal, failed probe/start/child, timeout, absent/empty temporary
report or publication conflict. The watchdog updates `last_codex` only on
`$true`. `ExecTimeoutMilliseconds` is optional, defaults to 600000 (10 minutes), and must be a positive integer.
Tests may inject a shorter limit. The deadline covers stdin delivery, the child exit and output-pipe completion.
On timeout the helper terminates the direct CLI child, allows up to two seconds of bounded cleanup, appends failure
diagnostics and refuses the handover even if a report exists or the recorded exit code is 0. Descendant termination
is not guaranteed. While this synchronous call waits, its next watchdog check waits too; chain execution remains independent.
Diagnostics append to `LogPath`, `OutputPath.log` and `OutputPath.err` (when probes/child produced output).
An unpublished temporary report must not be treated as a completed handover or included as a finished status report.

The source tests in `tests/test_codex_handover.py` are synthetic: discovery is isolated to temporary bundle records,
and native process tests use a compiled fake CLI. Config tests execute only AST-selected functions in temporary
fixtures. They do not probe installed Codex or perform actual inference, watchdog entrypoint execution,
game/controller activity, GitHub posts, commits, STOP changes, timer or automation changes.
Installed-bundle probes and a controlled fixture validation belong to the parent integration stage under its
separate authorization. These source-test limits are not a permanent prohibition on future parent probes or commits.
Future live application requires the owner/parent's protected config replacement procedure; preserve concurrent
edits and refuse unresolved recovery. An explicit stale path must be replaced with `null` or a verified complete
bundle through that procedure. Do not restart a running watchdog while Claude owns control. Keep chain-start logic,
Claude inactivity calculation, and live-controller decisions with Claude.

## For Claude when it is back

Touch `C:\Modding\testqueue\claude_heartbeat.txt` (or commit) while working, so the watchdog does not fire; read the
newest `codex_report_*.md` / `codex_handover_*.md` and the #32 comment first.
