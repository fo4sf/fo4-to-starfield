# SANDBOX ONLY: opens the simulated console, and like console_open.ps1 leaves its HUD check picture in -Work.
# FAKE_CONSOLE_REFUSE=3 (or 4) plays a refusal instead (nothing pressed), from call FAKE_CONSOLE_REFUSE_AFTER + 1 on
# (default every call); FAKE_CONSOLE_NOSHOT=1 makes that refusal write no picture (the screenshot itself failed).
param([string]$Work = '')
$n = 1
if ($Work) {
  New-Item -ItemType Directory -Force $Work | Out-Null
  $calls = Join-Path $Work 'fake_calls.txt'
  if (Test-Path $calls) { $n = [int](Get-Content $calls) + 1 }
  Set-Content $calls "$n"
}
$after = 0; if ($env:FAKE_CONSOLE_REFUSE_AFTER) { $after = [int]$env:FAKE_CONSOLE_REFUSE_AFTER }
if ($env:FAKE_CONSOLE_REFUSE -and $n -gt $after) {
  if ($Work -and -not $env:FAKE_CONSOLE_NOSHOT) { Set-Content (Join-Path $Work 'hud_check.png') "fake $n" }
  exit [int]$env:FAKE_CONSOLE_REFUSE
}
if ($Work) { Set-Content (Join-Path $Work 'hud_check.png') "fake $n" }
& $env:FO4SF_PYTHON (Join-Path $PSScriptRoot 'fake_game.py') type 'key:grave'
exit 0
