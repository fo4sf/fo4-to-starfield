# Run the local Lead in cycles (interactive; not a Windows service or scheduled task). Stop with the FO4SF AI menu
# (option 7 again: stops this and its session), Ctrl+C here (the same), or `guardian.py stop` (exits at the next check).
#   powershell -File tools\ai-team\run-lead.ps1 [-Interval 1800] [-MaxCycles 0] [-SessionTimeout 2700] [-Brief "<task>"]
# -Brief hands the session one task (Claude's local-team-delegate skill runs -MaxCycles 1 -Brief ...).
# Each cycle: skip if Starfield runs or the guardian is paused/stopped/blocked; make sure the guardian proxy and the
# model are up; run ONE Lead session in the Lead's own worktree (branch ai/local-lead, so its doc edits never collide
# with other agents in the main checkout); log it. Failures back off (x2, up to 4 h); success resets the interval.
param([int]$Interval = 1800, [int]$MaxCycles = 0, [int]$SessionTimeout = 2700, [string]$Brief = '',
      [string]$Python = $(if ($env:FO4SF_PYTHON) { $env:FO4SF_PYTHON } else { 'python' }))
$repo = Split-Path (Split-Path $PSScriptRoot)
$state = if ($env:FO4_AI_TEAM_STATE) { $env:FO4_AI_TEAM_STATE } else { Join-Path $env:LOCALAPPDATA 'fo4-ai-team\state' }
New-Item -ItemType Directory -Force $state | Out-Null
$log = Join-Path $state 'lead-cycles.log'
$pidFile = Join-Path $state 'run-lead.pid'
$sessionFile = Join-Path $state 'lead-session.pid'    # the running OpenCode session, for the menu's status and stop
function Log($m) { $l = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss ') + $m; $l; Add-Content $log $l }
function Wait-Next { if ($MaxCycles -eq 0 -or $cycle -lt $MaxCycles) { Start-Sleep $Interval } }   # none after the last

if (Test-Path $pidFile) {                                   # single instance
  $old = [int](Get-Content $pidFile)
  if (Get-Process -Id $old -ErrorAction SilentlyContinue) { "run-lead already running (pid $old)"; exit 1 }
}
$PID | Set-Content $pidFile

$wt = Join-Path (Split-Path $repo) 'fo4-to-starfield-wt\local-lead'
if (-not (Test-Path $wt)) {
  git -C $repo fetch -q origin main
  if (git -C $repo branch --list ai/local-lead) { git -C $repo worktree add $wt ai/local-lead | Out-Null }
  else { git -C $repo worktree add -b ai/local-lead $wt origin/main | Out-Null }
  Log "created Lead worktree $wt (branch ai/local-lead)"
}
$g = Join-Path $repo 'tools\ai-team\guardian\guardian.py'
# npm installs a .ps1 shim that Start-Process can't run: use the real binary behind it
$opencode = Join-Path (Split-Path (Get-Command opencode).Source) 'node_modules\opencode-ai\bin\opencode.exe'
$prompt = "Run ONE session of your operating procedure (your agent file + AGENTS.md). Do at most one task, then stop. " +
          "Good tasks for this team: research questions from docs/ai/known-unknowns.md (fo4-research, findings into " +
          "docs/ai/research-log.md); refreshing docs/ai/agent-status.md from live sources; open issues labelled " +
          "agent:local-team and ready that need only docs/ai edits or research (no code changes, no fo4-implement). " +
          "Do not call fo4-qa in this session: unattended runs take no QA reviews. " +
          "Run gh and git commands on their own, without pipes or redirects (no | head, | tail, | grep, 2>&1): " +
          "each stage of a pipeline is checked separately, the filters are not allowed, and any command containing " +
          "the character > is refused, so do not put that character in comment text either. " +
          "Commit your own docs/ai edits on this branch with python -I tools/ai-team/lead_commit.py '<what changed>' " +
          "(it commits only docs/ai); never push. " +
          "At most one comment on #32, prefixed 'Lead (local):', on one line of plain ASCII text with no quote marks, " +
          "apostrophes, dollar signs, backslashes, exclamation marks, backticks, ampersands, pipes, carets, percent " +
          "signs or angle brackets (the guard refuses those). If nothing is ready, say so and stop."
if ($Brief) {                                       # one line, and no character that ends the quoted argument
  $prompt += " Your task for this session, from the owner or Claude: " + (($Brief -replace '\s+', ' ') -replace '["`$\\]', "'")
}
$env:FO4SF_UNATTENDED = '1'                         # the guard plugin then refuses delegation to fo4-implement
$env:FO4SF_PYTHON = $Python                         # the plugin runs its checker with the same Python
Remove-Item Env:FO4SF_OWNER_PRESENT -ErrorAction SilentlyContinue   # and nothing here counts as the owner's terminal
$env:OPENCODE_DISABLE_EXTERNAL_SKILLS = '1'         # no skills from ~/.claude or ~/.agents (the claude.ai ones)
$env:OPENCODE_DISABLE_CLAUDE_CODE_SKILLS = '1'      # the same switch under its older name
$models = Join-Path $PSScriptRoot 'models.py'
$wait = $Interval; $cycle = 0
try {
  while ($MaxCycles -eq 0 -or $cycle -lt $MaxCycles) {
    $cycle++
    $st = & $Python $g status | ConvertFrom-Json
    if ($st.mode -eq 'stopped') { Log "guardian mode stopped: exiting"; break }
    $game = Get-Process Starfield, Fallout4 -ErrorAction SilentlyContinue
    if ($st.mode -eq 'paused' -or $game -or $st.level -eq 'block') {
      Log "cycle $cycle skipped: mode $($st.mode), level $($st.level), game $([bool]$game)"; Wait-Next; continue
    }
    powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'start-team.ps1') | Out-Null
    $ensure = (& $Python $models ensure 2>&1 | Out-String).Trim()    # the picked model (models.py), loaded if missing
    if ($LASTEXITCODE -ne 0) { Log "cycle ${cycle}: skipped: the picked model is not loaded: $ensure"; Wait-Next; continue }
    $env:OPENCODE_CONFIG_CONTENT = (& $Python $models opencode | Out-String).Trim()   # OpenCode's limits = the loaded window
    $branch = "$(git -C $wt rev-parse --abbrev-ref HEAD 2>$null)".Trim()
    if ($branch -ne 'ai/local-lead') {                  # checked before the pull, so no other branch is rebased
      Log "cycle ${cycle}: skipped: $wt is on '$branch', not ai/local-lead"; Wait-Next; continue
    }
    $gitDir = "$(git -C $wt rev-parse --absolute-git-dir 2>$null)".Trim()
    $busy = @('rebase-merge','rebase-apply','MERGE_HEAD','CHERRY_PICK_HEAD','REVERT_HEAD') |
            Where-Object { $gitDir -and (Test-Path (Join-Path $gitDir $_)) }
    if ($busy) {                                        # a stopped rebase/merge/cherry-pick: let a person resolve it
      Log "cycle ${cycle}: skipped: a git operation is in progress in $wt ($(@($busy) -join ', '))"; Wait-Next; continue
    }
    $pull = git -C $wt pull -q --rebase --autostash origin main 2>&1
    $pullFailed = $LASTEXITCODE -ne 0
    $unmerged = git -C $wt ls-files -u
    if ($unmerged) {                                    # an autostash or rebase conflict: a person resolves it
      Log "cycle ${cycle}: skipped: unmerged files in $wt after pulling main: $(($pull | Out-String).Trim())"; Wait-Next; continue
    }
    if ($pullFailed) {                                  # an old tree may predate the guard: no session on it
      Log "cycle ${cycle}: skipped: git pull of main failed: $(($pull | Out-String).Trim())"; Wait-Next; continue
    }
    $missing = @('.opencode\plugin\fo4-guard.js', 'tools\ai-team\guard\allowlist.py') |
               Where-Object { -not (Test-Path (Join-Path $wt $_)) }
    if ($missing) {                                     # OpenCode would start without the guard (it only logs that)
      Log "cycle ${cycle}: skipped: $wt has no $(@($missing) -join ', '), so the guard would be off"; Wait-Next; continue
    }
    Log "cycle ${cycle}: Lead session start (timeout $SessionTimeout s)"
    $out = Join-Path $state ("lead-session-{0}.log" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
    $p = Start-Process -FilePath $opencode -ArgumentList @('run', '--agent', 'fo4-lead', "`"$prompt`"") `
         -WorkingDirectory $wt -WindowStyle Hidden -PassThru -RedirectStandardOutput $out -RedirectStandardError "$out.err"
    $null = $p.Handle                                   # hold the handle, or ExitCode is lost (redirected Start-Process)
    $p.Id | Set-Content $sessionFile
    if (-not $p.WaitForExit($SessionTimeout * 1000)) {
      Stop-Process -Id $p.Id -Force -Confirm:$false; Log "cycle ${cycle}: session timed out, stopped"
      $wait = [Math]::Min($wait * 2, 14400)
    } elseif ($p.ExitCode -ne 0) {
      Log "cycle ${cycle}: session failed (exit $($p.ExitCode)), see $out"; $wait = [Math]::Min($wait * 2, 14400)
    } else {
      Log "cycle ${cycle}: session done, see $out"; $wait = $Interval
    }
    Remove-Item -LiteralPath $sessionFile -Force -ErrorAction SilentlyContinue
    if ($MaxCycles -ne 0 -and $cycle -ge $MaxCycles) { break }
    Start-Sleep $wait
  }
} finally {
  if ($p -and -not $p.HasExited) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue; Log "stopped the running Lead session" }
  Remove-Item -LiteralPath $sessionFile, $pidFile -Force -ErrorAction SilentlyContinue
  Remove-Item Env:FO4SF_UNATTENDED -ErrorAction SilentlyContinue   # in case this ran dot-sourced in an open window
  Log "run-lead stopped"
}
