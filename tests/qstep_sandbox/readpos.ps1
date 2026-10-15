# SANDBOX ONLY: the player's (or a ref's) position in the simulated game. -Strict changes nothing here (the fake prints
# what a parser would return; garble_after_walks simulates a garbled read); -Angle adds the heading. As the real one it
# types its nonce (fo4sfr<8 hex>) into the simulated console first and keeps read.json (nonce, result) in its own Work.
param([string]$Work = '', [string]$Ref = '', [switch]$Strict, [switch]$Angle)
if ($Ref -and $Ref -notmatch '^[0-9A-Fa-f]{8}$') { "fail ref"; exit 4 }
$nonce = 'fo4sfr' + [guid]::NewGuid().ToString('N').Substring(0, 8)
if (-not $Work) { $Work = Join-Path $env:TEMP "fo4sf_ocr\$nonce" }
New-Item -ItemType Directory -Force $Work | Out-Null
& $env:FO4SF_PYTHON (Join-Path $PSScriptRoot 'fake_game.py') type "type:$nonce|key:enter" | Out-Null
$a = @('readpos')
if ($Ref) { $a += $Ref }
if ($Angle -and -not $Ref) { $a += '--angle' }
$r = & $env:FO4SF_PYTHON (Join-Path $PSScriptRoot 'fake_game.py') @a
[ordered]@{ nonce = $nonce; work = $Work; ref = $Ref; result = "$r" } | ConvertTo-Json | Set-Content (Join-Path $Work 'read.json') -Encoding utf8
"$r"
