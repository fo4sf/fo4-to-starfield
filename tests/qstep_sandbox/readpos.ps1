# SANDBOX ONLY: the player's (or a ref's) position in the simulated game. -Strict changes nothing here (the fake prints
# what a parser would return; garble_after_walks simulates a garbled read); -Angle adds the heading.
param([string]$Work = '', [string]$Ref = '', [switch]$Strict, [switch]$Angle)
if ($Ref -and $Ref -notmatch '^[0-9A-Fa-f]{8}$') { "fail ref"; exit 4 }
$a = @('readpos')
if ($Ref) { $a += $Ref }
if ($Angle -and -not $Ref) { $a += '--angle' }
& $env:FO4SF_PYTHON (Join-Path $PSScriptRoot 'fake_game.py') @a
