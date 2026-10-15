# Ask the game for the player's position and read it back via OCR.
# Prints "x y z" in game metres, or "fail" if any value could not be read.
# Requires Starfield focused with the console CLOSED; leaves it closed.
# -Ref 02001234: read that placed object's position instead (prid selects it, getpos runs on the selection).
# -Strict: only labelled values of this read's own session (parse_getpos.py --strict; door_trip: a garbled read once
#          passed for a load 2.4 km away). -Angle: also player.getangle z; prints "x y z h" (implies -Strict).
# Every read proves it is this read's: a nonce (fo4sfr<8 hex>) is typed first as an unknown command, the console echoes
# it, and the parser reads only what follows that echo (Codex's review of PR #107, 2026-10-14: an older full triplet
# still on screen passed for a read whose own replies were missing). -Angle types a second nonce before getangle z and
# captures again: the console shows about nine lines, too few for one nonce, three getpos and a getangle with replies.
# Each invocation has its own Work folder (default %TEMP%\fo4sf_ocr\<nonce>) with its capture(s), OCR text and
# read.json (nonce, paths, result): the read's provenance.
param([string]$Work = '', [string]$Ref = '', [switch]$Strict, [switch]$Angle)
if ($Ref -and $Ref -notmatch '^[0-9A-Fa-f]{8}$') { "fail ref"; exit 4 }   # typed into the game: hex ids only
function New-Nonce { return 'fo4sfr' + [guid]::NewGuid().ToString('N').Substring(0, 8) }
$nonce = New-Nonce
if (-not $Work) { $Work = Join-Path $env:TEMP "fo4sf_ocr\$nonce" }
New-Item -ItemType Directory -Force $Work | Out-Null
$env:LEGACY = '1'
$i = (Join-Path $PSScriptRoot 'input.ps1')
$py = $(if ($env:FO4SF_PYTHON) { $env:FO4SF_PYTHON } else { 'python' })
$rec = [ordered]@{ nonce = $nonce; work = $Work; ref = $Ref; strict = [bool]($Strict -or $Angle); result = 'fail' }
function Done([string]$r) { $rec['result'] = $r; $rec | ConvertTo-Json | Set-Content (Join-Path $Work 'read.json') -Encoding utf8; $r }
powershell -NoProfile -ExecutionPolicy Bypass -File $PSScriptRoot\console_open.ps1 -Work $Work | Out-Null
if ($LASTEXITCODE -ne 0) { Done "fail console $LASTEXITCODE"; exit 3 }   # never type unless the console is confirmed open
$who = 'player.'; $sel = ''
if ($Ref) { $who = ''; $sel = "type:prid $Ref|key:enter|wait:350|" }
$mode = @('--nonce', $nonce)
if ($Strict -or $Angle) { $mode = @('--strict') + $mode }
powershell -NoProfile -ExecutionPolicy Bypass -File $i -Seq "${sel}type:$nonce|key:enter|wait:350|type:${who}getpos x|key:enter|wait:350|type:${who}getpos y|key:enter|wait:350|type:${who}getpos z|key:enter|wait:700" | Out-Null
if ($LASTEXITCODE -ne 0) { Done 'fail guard'; exit 2 }
$cap = Join-Path $Work 'readpos_cap.png'; $prep = Join-Path $Work 'readpos_prep.png'; $txt = Join-Path $Work 'readpos_ocr.txt'
powershell -NoProfile -ExecutionPolicy Bypass -File $PSScriptRoot\shot_region.ps1 -Out $cap | Out-Null
$rec['cap'] = $cap; $rec['ocr'] = $txt
$acap = ''
if ($Angle -and -not $Ref) {                              # the heading: its own nonce and capture, the console still open
  $anonce = New-Nonce
  powershell -NoProfile -ExecutionPolicy Bypass -File $i -Seq "type:$anonce|key:enter|wait:350|type:player.getangle z|key:enter|wait:700" | Out-Null
  if ($LASTEXITCODE -ne 0) { Done 'fail guard'; exit 2 }
  $acap = Join-Path $Work 'angle_cap.png'; $aprep = Join-Path $Work 'angle_prep.png'; $atxt = Join-Path $Work 'angle_ocr.txt'
  powershell -NoProfile -ExecutionPolicy Bypass -File $PSScriptRoot\shot_region.ps1 -Out $acap | Out-Null
  $rec['angle_nonce'] = $anonce; $rec['angle_cap'] = $acap; $rec['angle_ocr'] = $atxt
}
powershell -NoProfile -ExecutionPolicy Bypass -File $i -Seq 'key:grave|wait:600' | Out-Null
function Read-Capture([string]$c, [string]$p, [string]$t, $opts) {
  foreach ($th in 135, 140, 130, 145) {                    # console text is ~150 on a dimmed ~85 background
    & $py $PSScriptRoot\ocr_prep.py $c $p $th 12
    (powershell -NoProfile -ExecutionPolicy Bypass -File $PSScriptRoot\ocr.ps1 -Image $p -Scale 1) | Set-Content $t -Encoding utf8
    $r = & $py $PSScriptRoot\parse_getpos.py $t @opts
    if ($r -ne 'fail') { Remove-Item $p -ErrorAction SilentlyContinue; return "$r" }   # the capture is the evidence
  }
  return 'fail'
}
$r = Read-Capture $cap $prep $txt $mode
if ($r -eq 'fail') { Done 'fail'; exit 0 }
if ($acap) {
  $h = Read-Capture $acap $aprep $atxt @('--angle-only', '--nonce', $anonce)
  if ($h -eq 'fail') { Done 'fail'; exit 0 }
  $r = "$r $h"
}
Done $r
