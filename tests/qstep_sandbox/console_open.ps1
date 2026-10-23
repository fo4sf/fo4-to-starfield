# SANDBOX ONLY: opens the simulated console. FAKE_CONSOLE_REFUSE=3 (or 4) plays a refusal instead: the HUD check's
# picture is written to -Work and nothing is pressed, as console_open.ps1 does.
param([string]$Work = '')
if ($env:FAKE_CONSOLE_REFUSE) {
  if ($Work) { New-Item -ItemType Directory -Force $Work | Out-Null; Set-Content (Join-Path $Work 'hud_check.png') 'fake' }
  exit [int]$env:FAKE_CONSOLE_REFUSE
}
& $env:FO4SF_PYTHON (Join-Path $PSScriptRoot 'fake_game.py') type 'key:grave'
exit 0
