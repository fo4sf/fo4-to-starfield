# SANDBOX ONLY: "reads" the simulated console's last lines.
param([string]$Image, [int]$X = 0, [int]$Y = 0, [int]$W = 0, [int]$H = 0, [int]$Scale = 2)
& $env:FO4SF_PYTHON (Join-Path $PSScriptRoot 'fake_game.py') screen
