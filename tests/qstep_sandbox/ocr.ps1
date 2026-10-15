# SANDBOX ONLY: "reads" the simulated console's last lines; with a region (-W > 0: the screen centre, qstep.ps1 walk's
# popup check) the simulated popup's text instead.
param([string]$Image, [int]$X = 0, [int]$Y = 0, [int]$W = 0, [int]$H = 0, [int]$Scale = 2)
if ($W -gt 0) { & $env:FO4SF_PYTHON (Join-Path $PSScriptRoot 'fake_game.py') popup; exit 0 }
& $env:FO4SF_PYTHON (Join-Path $PSScriptRoot 'fake_game.py') screen
