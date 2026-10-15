# SANDBOX ONLY: opens the simulated console.
param([string]$Work = '')
& $env:FO4SF_PYTHON (Join-Path $PSScriptRoot 'fake_game.py') type 'key:grave'
exit 0
