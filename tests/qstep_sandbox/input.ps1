# SANDBOX ONLY (tests/test_qstep_sandbox.py): stands in for scripts/game/input.ps1. Never sends a key or a click:
# the sequence goes to the simulated console (fake_game.py). It goes through an environment variable, not a native
# argument, so the simulated console receives exactly the $Seq this script got (Windows PowerShell 5.1 would drop its
# double quotes on the way to python; the real input.ps1 types $Seq itself).
param([string]$Proc = 'Starfield', [string]$Seq)
$env:FAKE_SEQ = $Seq
& $env:FO4SF_PYTHON (Join-Path $PSScriptRoot 'fake_game.py') type -
"sent (sandbox)"
