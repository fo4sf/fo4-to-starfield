# Dead man's switch for the unattended test chain (Claude, 2026-10-11; the owner asked: "if you don't make any changes in
# XYZ time, have Codex run the test program").
# Every check_minutes it measures how long Claude has been inactive: the newer of the last "Claude:" commit on any branch
# (local or fetched) and the heartbeat file Claude touches while it works. After threshold_hours of inactivity it
#   1. starts the test chain (C:\Modding\testqueue\chain.ps1; no AI needed: the runner is deterministic) when the chain is
#      not running and C:\Modding\testqueue\chain_queue.txt still lists queues, and
#   2. hands over to Codex (codex exec, sandbox workspace-write in C:\Modding\testqueue, network on for gh) at most every
#      codex_every_hours: Codex follows docs/ai/codex-runbook.md (watch the chain, read the reports, post to issue #32;
#      no code changes, no game input of its own).
# The chain keeps every owner control: launches only after 15 min without input, never touches a game the owner started,
# STOP files and the Resource Guardian stop it. The watchdog itself does nothing while a STOP file exists.
# Config (optional): C:\Modding\testqueue\watchdog.json  {"threshold_hours": 3, "check_minutes": 10, "codex": true,
#   "codex_every_hours": 6, "codex_exe": "...\\codex.exe"}.  Log: C:\Modding\testqueue\watchdog.log
# usage: watchdog.ps1 [-Once]   (-Once: one check and exit, for tests and for a manual "would it fire now?")
param([switch]$Once, [string]$Config = 'C:\Modding\testqueue\watchdog.json')
$ErrorActionPreference = 'Continue'
$tq = 'C:\Modding\testqueue'
# the checkout this script runs from (worktrees share one repository, so its refs include every branch)
$repo = Split-Path (Split-Path $PSScriptRoot)
$wt = $repo
$log = Join-Path $tq 'watchdog.log'
$stateFile = Join-Path $tq 'watchdog_state.json'
$heartbeat = Join-Path $tq 'claude_heartbeat.txt'
function Note($m) { try { "$(Get-Date -Format s) $m" | Add-Content $log -ErrorAction Stop } catch { } }
function Cfg {
  $c = @{ threshold_hours = 3.0; check_minutes = 10; codex = $true; codex_every_hours = 6.0
          codex_exe = "$env:USERPROFILE\.codex\.sandbox-bin\codex.exe" }
  if (Test-Path $Config) {
    try { (Get-Content $Config -Raw | ConvertFrom-Json).PSObject.Properties | ForEach-Object { $c[$_.Name] = $_.Value } }
    catch { Note "config unreadable, defaults used: $_" }
  }
  return $c
}
function Stopped { (Test-Path (Join-Path $tq 'STOP_ALL')) -or (Test-Path "$env:LOCALAPPDATA\fo4-ai-team\state\testqueue.STOP") }
function ClaudeLast {
  # newest of: heartbeat file, last "Claude:" commit on any ref (fetch first; a failed fetch keeps the local refs)
  $t = [DateTime]::MinValue
  if (Test-Path $heartbeat) { $t = (Get-Item $heartbeat).LastWriteTime }
  # fetch with a time limit: a hung fetch (network down) must not freeze the loop
  $job = Start-Job -ScriptBlock { param($r) git -C $r fetch -q origin 2>$null } -ArgumentList $repo
  if (-not (Wait-Job $job -Timeout 60)) { Stop-Job $job; Note "git fetch timed out: local refs used" }
  Remove-Job $job -Force -ErrorAction SilentlyContinue
  $ct = git -C $repo log --all --grep '^Claude' -1 --format=%ct 2>$null
  if ("$ct" -match '^\d+$') {
    $c = [DateTimeOffset]::FromUnixTimeSeconds([long]$ct).LocalDateTime
    if ($c -gt $t) { $t = $c }
  }
  return $t
}
function ChainRunning {
  $p = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
       Where-Object { $_.CommandLine -match 'chain\.ps1|overnight\.ps1|testqueue\.py' -and $_.ProcessId -ne $PID }
  return @($p).Count -gt 0
}
function QueueLeft { @(Get-Content (Join-Path $tq 'chain_queue.txt') -ErrorAction SilentlyContinue | Where-Object { $_.Trim() -and -not $_.Trim().StartsWith('#') }).Count }
function State { if (Test-Path $stateFile) { try { return Get-Content $stateFile -Raw | ConvertFrom-Json } catch { } }; return $null }
function SaveState($s) { $s | ConvertTo-Json | Set-Content -Encoding utf8 $stateFile }
function CodexHandOver($cfg, $idleH) {
  $exe = $cfg.codex_exe
  if (-not (Test-Path $exe)) { Note "codex not found at ${exe}: no hand-over"; return }
  $runbook = Join-Path $wt 'docs\ai\codex-runbook.md'
  if (-not (Test-Path $runbook)) { $runbook = Join-Path $repo 'docs\ai\codex-runbook.md' }
  $prompt = "Codex: Claude has been inactive for $([Math]::Round($idleH,1)) hours, so the test hand-over in $runbook applies. " +
            "Read that runbook and follow it exactly: check the unattended test chain in C:\Modding\testqueue, read the queue " +
            "states and reports, and post one concise status comment to GitHub issue #32 starting with 'Codex:'. " +
            "Do not edit code or repo files, do not send any input to Starfield yourself, do not touch the game folder or " +
            "Plugins.txt, and never write the owner's previous GitHub username anywhere."
  $out = Join-Path $tq ("codex_handover_{0}.md" -f (Get-Date -Format 'yyyyMMdd_HHmm'))
  # the prompt goes in on stdin ("-"): Start-Process in PowerShell 5.1 does not quote arguments with spaces
  $promptFile = Join-Path $tq 'codex_prompt.txt'
  Set-Content -Encoding utf8 $promptFile $prompt
  $cargs = "exec --skip-git-repo-check -C `"$tq`" -s workspace-write -c sandbox_workspace_write.network_access=true -o `"$out`" -"
  try {
    Start-Process -FilePath $exe -ArgumentList $cargs -WindowStyle Hidden -RedirectStandardInput $promptFile `
                  -RedirectStandardOutput "$out.log" -RedirectStandardError "$out.err" | Out-Null
    Note "Codex hand-over started (report $out)"
  } catch { Note "Codex hand-over failed to start: $_" }
}

Note "watchdog start (pid $PID, config $Config)"
while ($true) {
  $cfg = Cfg
  if (Stopped) {
    Note "STOP file present: nothing started"
  } else {
    $last = ClaudeLast
    $idleH = ((Get-Date) - $last).TotalHours
    $st = State
    if ($idleH -ge [double]$cfg.threshold_hours) {
      $running = ChainRunning
      # at most 3 chain starts per 6 hours: a queue that keeps failing at once must not be restarted every check
      $starts = @(if ($st -and $st.starts) { $st.starts | Where-Object { ((Get-Date) - [DateTime]$_).TotalHours -lt 6 } })
      if (-not $running -and (QueueLeft) -gt 0 -and $starts.Count -lt 3) {
        Note ("Claude inactive {0:N1} h (last {1:s}): starting the test chain" -f $idleH, $last)
        Start-Process powershell -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $tq 'chain.ps1')) `
                      -WindowStyle Hidden | Out-Null
        $starts += (Get-Date).ToString('s')
        SaveState @{ last_codex = $(if ($st) { $st.last_codex } else { $null }); starts = $starts; claude_last = $last.ToString('s') }
        $st = State
      } elseif (-not $running -and (QueueLeft) -gt 0) {
        Note "chain not restarted: 3 starts in the last 6 hours already (see overnight.log)"
      }
      $lastCodex = if ($st -and $st.last_codex) { [DateTime]$st.last_codex } else { [DateTime]::MinValue }
      if ($cfg.codex -and ((Get-Date) - $lastCodex).TotalHours -ge [double]$cfg.codex_every_hours) {
        CodexHandOver $cfg $idleH
        SaveState @{ last_codex = (Get-Date).ToString('s'); starts = $(if ($st) { @($st.starts) } else { @() });
                     claude_last = $last.ToString('s') }
      }
    }
  }
  if ($Once) { break }
  Start-Sleep -Seconds ([int]$cfg.check_minutes * 60)
}
