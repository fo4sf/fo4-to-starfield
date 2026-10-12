# SANDBOX ONLY: the player's (or a ref's) position in the simulated game.
param([string]$Work = '', [string]$Ref = '')
if ($Ref -and $Ref -notmatch '^[0-9A-Fa-f]{8}$') { "fail ref"; exit 4 }
& $env:FO4SF_PYTHON (Join-Path $PSScriptRoot 'fake_game.py') readpos $Ref
