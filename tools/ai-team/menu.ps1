# The FO4SF AI menu, which the "FO4SF AI" desktop shortcut opens (install-shortcut.ps1 makes the shortcut).
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\ai-team\menu.ps1
# One place to start the local team, talk to its agents, start Claude Code, see the status, pick the model and stop.
# Each terminal opens in its own window, so the menu stays open. Interactive only; nothing here runs on a schedule.
param([string]$Python = $(if ($env:FO4SF_PYTHON) { $env:FO4SF_PYTHON } else { 'python' }))
$here = $PSScriptRoot
$repo = Split-Path (Split-Path $here)
$models = Join-Path $here 'models.py'
$guardian = Join-Path $here 'guardian\guardian.py'
$Host.UI.RawUI.WindowTitle = 'FO4SF AI'

function Open-Window($file, [string[]]$more = @()) {
  Start-Process powershell -WorkingDirectory $repo -ArgumentList (@('-NoExit', '-NoProfile', '-ExecutionPolicy', 'Bypass',
    '-File', "`"$(Join-Path $here $file)`"") + $more)
}

function Show-Status {
  $g = & $Python $guardian status | Out-String | ConvertFrom-Json
  $p = (& $Python $models list | Out-String | ConvertFrom-Json)
  $s = $g.snapshot
  "guardian: level $($g.level), mode $($g.mode); RAM $($s.ram.used_pct)%, VRAM $($s.gpu.vram_pct)%"
  if ($g.reasons) { "  why: $($g.reasons -join '; ')" }
  "requests: $(@($g.running).Count) running, $(@($g.queued).Count) queued"
  $pick = $p.picked
  "model picked: $($pick.model) at $($pick.context / 1024)K$(if ($pick.preset) { " (preset $($pick.preset))" })"
  if ($p.loaded) { "LM Studio has loaded: $($p.loaded -join ', ')" } elseif ($p.lmstudio) { "LM Studio: $($p.lmstudio)" }
  else { "LM Studio has no model loaded" }
  $state = if ($env:FO4_AI_TEAM_STATE) { $env:FO4_AI_TEAM_STATE } else { Join-Path $env:LOCALAPPDATA 'fo4-ai-team\state' }
  $pidFile = Join-Path $state 'run-lead.pid'
  $leadPid = if (Test-Path $pidFile) { "$(Get-Content $pidFile -ErrorAction SilentlyContinue)".Trim() } else { '' }
  $lead = ($leadPid -match '^[0-9]+$') -and (Get-Process -Id ([int]$leadPid) -ErrorAction SilentlyContinue)
  "unattended Lead: $(if ($lead) { 'running' } else { 'not running' })"
  $log = Join-Path $state 'lead-cycles.log'
  if (Test-Path $log) { "last Lead log lines:"; Get-Content $log -Tail 3 | ForEach-Object { "  $_" } }
}

function Pick-Model {
  $p = & $Python $models list | Out-String | ConvertFrom-Json
  $names = @($p.presets.PSObject.Properties.Name)
  for ($i = 0; $i -lt $names.Count; $i++) {
    $m = $p.presets.($names[$i])
    "  $($i + 1)  $($names[$i]): $($m.model) at $($m.context / 1024)K. $($m.note)"
  }
  "  o  another model LM Studio has downloaded"
  $c = Read-Host 'Pick (Enter to go back)'
  if ($c -match '^[0-9]+$' -and [int]$c -ge 1 -and [int]$c -le $names.Count) {
    & $Python $models pick $names[[int]$c - 1]
  } elseif ($c -eq 'o') {
    if ($p.downloaded) { "downloaded:"; $p.downloaded | ForEach-Object { "  $_" } } else { "LM Studio: $($p.lmstudio)" }
    $id = Read-Host 'Model id (as listed)'
    $ctx = Read-Host 'Context in tokens (for example 32768)'
    if ($id -and $ctx -match '^[0-9]+$') { & $Python $models pick --model $id --context ([int]$ctx) }
  }
  "Open terminals keep the old limits: close them and open a new one."
}

function Start-Claude {
  "  1  Opus   2  Sonnet   3  Haiku   Enter  your default"
  $c = Read-Host 'Model'
  $m = @{ '1' = 'opus'; '2' = 'sonnet'; '3' = 'haiku' }[$c]
  if (-not (Get-Command claude -ErrorAction SilentlyContinue)) { "Claude Code (claude) is not on PATH"; return }
  $cmd = 'claude' + $(if ($m) { " --model $m" } else { '' })
  Start-Process powershell -WorkingDirectory $repo -ArgumentList @('-NoExit', '-NoProfile', '-Command', $cmd)
}

while ($true) {
  ''
  'FO4SF AI'
  '  1  Start the local team (guardian proxy and the picked model)'
  '  2  Talk to the local agents (the Lead)'
  '  3  Talk to one agent: research, implement or QA'
  '  4  Start Claude Code in the repo'
  '  5  Status'
  '  6  Pick a model'
  '  7  Start the unattended Lead (its own window; close the window to stop it)'
  '  8  Pause or resume the local team'
  '  9  Stop the local team'
  '  0  Close this menu'
  switch (Read-Host 'Choose') {
    '1' { powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $here 'start-team.ps1'); & $Python $models ensure }
    '2' { Open-Window 'terminal.ps1' }
    '3' {
      $a = @{ 'r' = 'fo4-research'; 'i' = 'fo4-implement'; 'q' = 'fo4-qa' }[(Read-Host 'r = research, i = implement, q = QA')]
      if ($a) { Open-Window 'terminal.ps1' @('-Agent', $a) }
    }
    '4' { Start-Claude }
    '5' { Show-Status }
    '6' { Pick-Model }
    '7' {
      if ((Read-Host 'Type yes to start the unattended Lead') -eq 'yes') { Open-Window 'run-lead.ps1' }
    }
    '8' {
      $mode = (& $Python $guardian status | Out-String | ConvertFrom-Json).mode
      if ($mode -eq 'running') { & $Python $guardian pause } else { & $Python $guardian resume }
    }
    '9' { powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $here 'stop-team.ps1') }
    '0' { return }
  }
}
