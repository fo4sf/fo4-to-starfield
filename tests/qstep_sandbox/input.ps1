# SANDBOX ONLY (tests/test_qstep_sandbox.py): stands in for scripts/game/input.ps1. Never sends a key or a click:
# the sequence goes to the simulated console (fake_game.py).
param([string]$Proc = 'Starfield', [string]$Seq)
& $env:FO4SF_PYTHON (Join-Path $PSScriptRoot 'fake_game.py') type $Seq
"sent (sandbox)"
