# SANDBOX ONLY (tests/test_qstep_sandbox.py): stands in for scripts/game/input.ps1. Never sends a key or a click:
# the sequence goes to the simulated console (fake_game.py). It goes through an environment variable, not a native
# argument, so the simulated console receives exactly the $Seq this script got (Windows PowerShell 5.1 would drop its
# double quotes on the way to python; the real input.ps1 types $Seq itself).
param([string]$Proc = 'Starfield', [string]$Seq)
$env:FAKE_SEQ = $Seq
& $env:FO4SF_PYTHON (Join-Path $PSScriptRoot 'fake_game.py') type -
if ($Seq -match 'holdg:') {
  # as the real holdg: a STOP file (FO4SF_STOP_FILES) that exists once the hold ends counts as one that appeared during
  # it (fake_game's stop_box writes it while walking): the key is released and the exit code is 5
  $hit = @("$env:FO4SF_STOP_FILES".Split(';') | Where-Object { $_ -and (Test-Path -LiteralPath $_) })
  if ($hit) { Write-Error "STOP: $($hit[0]) appeared during a hold (sandbox)"; exit 5 }
}
"sent (sandbox)"
