# SANDBOX ONLY: writes the simulated game's screenshot (a small PNG whose top rows have the simulated sky's brightness).
param([string]$Out)
& $env:FO4SF_PYTHON (Join-Path $PSScriptRoot 'fake_game.py') shot $Out; "saved (sandbox)"
