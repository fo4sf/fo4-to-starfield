# Run the local Lead in cycles (interactive; not a Windows service or scheduled task). Stop with Ctrl+C,
# `guardian.py stop` (exits at the next check) or by deleting the pid file.
#   powershell -File tools\ai-team\run-lead.ps1 [-Interval 1800] [-MaxCycles 0] [-SessionTimeout 2700]
# Each cycle: skip if Starfield runs or the guardian is paused/stopped/blocked; make sure the guardian proxy and the
# model are up; run ONE Lead session in the Lead's own worktree (branch ai/local-lead, so its doc edits never collide
# with other agents in the main checkout); log it. Failures back off (x2, up to 4 h); success resets the interval.
param([int]$Interval = 1800, [int]$MaxCycles = 0, [int]$SessionTimeout = 2700,
      [string]$Python = $(if ($env:FO4SF_PYTHON) { $env:FO4SF_PYTHON } else { 'python' }))
$repo = Split-Path (Split-Path $PSScriptRoot)
$state = if ($env:FO4_AI_TEAM_STATE) { $env:FO4_AI_TEAM_STATE } else { Join-Path $env:LOCALAPPDATA 'fo4-ai-team\state' }
New-Item -ItemType Directory -Force $state | Out-Null
$log = Join-Path $state 'lead-cycles.log'
$pidFile = Join-Path $state 'run-lead.pid'
function Log($m) { $l = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss ') + $m; $l; Add-Content $log $l }

# Both resolved first, so a bad -Python or a missing OpenCode stops the script before it writes the pid file or sets
# anything. The plugin runs its checker with this Python, as a full path: it starts it from the Lead's worktree.
$pythonPath = (Get-Command $Python -ErrorAction Stop).Source
# npm installs a .ps1 shim that Start-Process can't run: use the real binary behind it
$opencode = Join-Path (Split-Path (Get-Command opencode -ErrorAction Stop).Source) 'node_modules\opencode-ai\bin\opencode.exe'

if (Test-Path $pidFile) {                                   # single instance
  $old = [int](Get-Content $pidFile)
  if (Get-Process -Id $old -ErrorAction SilentlyContinue) { "run-lead already running (pid $old)"; exit 1 }
}

$wt = Join-Path (Split-Path $repo) 'fo4-to-starfield-wt\local-lead'
$g = Join-Path $repo 'tools\ai-team\guardian\guardian.py'
$prompt = "Run ONE session of your operating procedure (your agent file + AGENTS.md). Do at most one task, then stop. " +
          "Good tasks for this team: research questions from docs/ai/known-unknowns.md (fo4-research, findings into " +
          "docs/ai/research-log.md); refreshing docs/ai/agent-status.md from live sources; open issues labelled " +
          "agent:local-team and ready that need only docs/ai edits or research (no code changes, no fo4-implement). " +
          "Do not call fo4-qa in this session: unattended runs take no QA reviews. " +
          "Run gh and git commands on their own, without pipes or redirects (no | head, | tail, | grep, 2>&1): " +
          "each stage of a pipeline is checked separately, the filters are not allowed, and any command containing " +
          "the character > is refused, so do not put that character in comment text either. " +
          "Commit your own docs/ai edits on this branch with python -I tools/ai-team/lead_commit.py 'what changed' " +
          "(it commits only docs/ai; the message is at most 500 characters); never push. " +
          "At most one comment on #32, prefixed 'Lead (local):', on one line of at most 1500 characters. The comment " +
          "and the commit message are plain ASCII text with no quote marks, apostrophes, dollar signs, backslashes, " +
          "exclamation marks, backticks, ampersands, pipes, carets, percent signs or angle brackets (the guard refuses " +
          "those), and the comment does not contain -R or -F (in either case), --repo, --output, --no-index, " +
          "--body-file, --edit-last or --delete-last (the rules refuse those). Do not comment on other issues or " +
          "change labels: name the issue you worked on in the #32 comment, and the owner sets labels. If nothing is " +
          "ready, say so and stop."
function Test-GuardGate {                           # does the running proxy refuse a request with no guard header?
  try {
    Invoke-WebRequest -UseBasicParsing -Method Post -Uri 'http://127.0.0.1:1235/v1/chat/completions' -Body '{}' `
      -ContentType 'application/json' -TimeoutSec 10 | Out-Null
    return $false
  } catch { return ($_.Exception.Response -and [int]$_.Exception.Response.StatusCode -eq 403) }
}
$saved = @{ FO4SF_UNATTENDED = $env:FO4SF_UNATTENDED; FO4SF_PYTHON = $env:FO4SF_PYTHON }   # put back at the end
$wait = $Interval; $cycle = 0
try {
  $PID | Set-Content $pidFile
  if (-not (Test-Path $wt)) {
    git -C $repo fetch -q origin main
    if (git -C $repo branch --list ai/local-lead) { git -C $repo worktree add $wt ai/local-lead | Out-Null }
    else { git -C $repo worktree add -b ai/local-lead $wt origin/main | Out-Null }
    Log "created Lead worktree $wt (branch ai/local-lead)"
  }
  $env:FO4SF_UNATTENDED = '1'                       # the guard plugin then refuses delegation to fo4-implement
  $env:FO4SF_PYTHON = $pythonPath
  while ($MaxCycles -eq 0 -or $cycle -lt $MaxCycles) {
    $cycle++
    $st = & $Python $g status | ConvertFrom-Json
    if ($st.mode -eq 'stopped') { Log "guardian mode stopped: exiting"; break }
    $game = Get-Process Starfield, Fallout4 -ErrorAction SilentlyContinue
    if ($st.mode -eq 'paused' -or $game -or $st.level -eq 'block') {
      Log "cycle $cycle skipped: mode $($st.mode), level $($st.level), game $([bool]$game)"; Start-Sleep $Interval; continue
    }
    powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'start-team.ps1') | Out-Null
    if (-not ((lms ps 2>&1 | Out-String) -match 'qwen3\.6-35b-a3b')) {
      Log "model not loaded: loading"; & $Python (Join-Path $PSScriptRoot 'load_model.py') | Out-Null
    }
    $branch = "$(git -C $wt rev-parse --abbrev-ref HEAD 2>$null)".Trim()
    if ($branch -ne 'ai/local-lead') {                  # checked before the pull, so no other branch is rebased
      Log "cycle ${cycle}: skipped: $wt is on '$branch', not ai/local-lead"; Start-Sleep $Interval; continue
    }
    $gitDir = "$(git -C $wt rev-parse --absolute-git-dir 2>$null)".Trim()
    $busy = @('rebase-merge','rebase-apply','MERGE_HEAD','CHERRY_PICK_HEAD','REVERT_HEAD') |
            Where-Object { $gitDir -and (Test-Path (Join-Path $gitDir $_)) }
    if ($busy) {                                        # a stopped rebase/merge/cherry-pick: let a person resolve it
      Log "cycle ${cycle}: skipped: a git operation is in progress in $wt ($(@($busy) -join ', '))"; Start-Sleep $Interval; continue
    }
    $pull = git -C $wt pull -q --rebase --autostash origin main 2>&1
    $pullFailed = $LASTEXITCODE -ne 0
    $unmerged = git -C $wt ls-files -u
    if ($unmerged) {                                    # an autostash or rebase conflict: a person resolves it
      Log "cycle ${cycle}: skipped: unmerged files in $wt after pulling main: $(($pull | Out-String).Trim())"; Start-Sleep $Interval; continue
    }
    if ($pullFailed) {                                  # an old tree may predate the guard: no session on it
      Log "cycle ${cycle}: skipped: git pull of main failed: $(($pull | Out-String).Trim())"; Start-Sleep $Interval; continue
    }
    if (-not (Test-GuardGate)) {                        # a proxy started before the guard header check serves anyone
      Log "cycle ${cycle}: skipped: the guardian proxy does not refuse requests without the guard header (started before #605?): run stop-team.ps1, then start-team.ps1"; Start-Sleep $Interval; continue
    }
    $missing = @('.opencode\plugin\fo4-guard.js', 'tools\ai-team\guard\allowlist.py') |
               Where-Object { -not (Test-Path (Join-Path $wt $_)) }
    if ($missing) {                                     # OpenCode would start without the guard (it only logs that)
      Log "cycle ${cycle}: skipped: $wt has no $(@($missing) -join ', '), so the guard would be off"; Start-Sleep $Interval; continue
    }
    Log "cycle ${cycle}: Lead session start (timeout $SessionTimeout s)"
    $out = Join-Path $state ("lead-session-{0}.log" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
    $p = Start-Process -FilePath $opencode -ArgumentList @('run', '--agent', 'fo4-lead', "`"$prompt`"") `
         -WorkingDirectory $wt -WindowStyle Hidden -PassThru -RedirectStandardOutput $out -RedirectStandardError "$out.err"
    $null = $p.Handle                                   # hold the handle, or ExitCode is lost (redirected Start-Process)
    if (-not $p.WaitForExit($SessionTimeout * 1000)) {
      Stop-Process -Id $p.Id -Force -Confirm:$false; Log "cycle ${cycle}: session timed out, stopped"
      $wait = [Math]::Min($wait * 2, 14400)
    } elseif ($p.ExitCode -ne 0) {
      Log "cycle ${cycle}: session failed (exit $($p.ExitCode)), see $out"; $wait = [Math]::Min($wait * 2, 14400)
    } else {
      Log "cycle ${cycle}: session done, see $out"; $wait = $Interval
    }
    if ($MaxCycles -ne 0 -and $cycle -ge $MaxCycles) { break }
    Start-Sleep $wait
  }
} finally {
  Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
  foreach ($k in $saved.Keys) {                     # in case this ran dot-sourced: the window gets its own values back
    if ($null -eq $saved[$k]) { Remove-Item "Env:$k" -ErrorAction SilentlyContinue } else { Set-Item "Env:$k" $saved[$k] }
  }
  Log "run-lead stopped"
}
