# Starfield's "This save uses a different Creations Load Order than your current Load Order. Would you like to use the
# Load Order from this save, or your current Load Order?" dialog (seen 2026-10-13, launch frames 23:20): "Save" is
# preselected, so the E that clears load-time notices picked it, Starfield switched to the save's load order and rewrote
# Plugins.txt with every experiment plugin inactive; each later coc into our worldspaces froze. This script keeps the
# CURRENT load order: if the dialog is on screen, it moves the highlight to "Current" (Down), checks the highlight, and
# only then confirms with E. Presses nothing when the dialog is not shown.
# Exit codes: 0 no dialog, 10 dialog answered "Current" and gone, 9 dialog shown but "Current" not selected or the dialog
# stayed (E not pressed on "Save"), 5 a screen check could not run, 2 input guard.
param([string]$Out = (Join-Path $env:TEMP 'fo4sf_loadorder.png'))
$here = $PSScriptRoot
$py = if ($env:FO4SF_PYTHON) { $env:FO4SF_PYTHON } else { 'python' }
function Shot { powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $here 'shot.ps1') -Out $Out | Out-Null }
function Send($seq) {
  powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $here 'input.ps1') -Seq $seq | Out-Null
  if ($LASTEXITCODE -ne 0) { "input guard stopped the sequence (someone else has focus)"; exit 2 }
}
function Shown {
  $t = powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $here 'ocr.ps1') -Image $Out -X 400 -Y 230 -W 480 -H 95
  if ($LASTEXITCODE -ne 0) { "load order dialog OCR failed (ocr.ps1 exit $LASTEXITCODE): nothing pressed"; exit 5 }
  return (($t | Out-String) -match 'Load\s*Order')
}
function Row {
  $r = & $py (Join-Path $here 'loadorder_row.py') $Out 2>$null
  if ($LASTEXITCODE -ne 0 -or @('save', 'current', 'none') -notcontains "$r") {
    "load order highlight check failed (python exit $LASTEXITCODE; set FO4SF_PYTHON to a Python with Pillow): nothing pressed"; exit 5
  }
  return "$r"
}
Shot
if (-not (Shown)) { "no load order dialog"; exit 0 }
foreach ($k in @('down', 's')) {                                 # arrow first; WASD if the menu ignores arrows
  if ((Row) -eq 'current') { break }
  Send "key:$k|wait:700"; Shot
}
$r = Row
if ($r -ne 'current') { "load order dialog: 'Current' could not be selected (highlight: $r): nothing confirmed"; exit 9 }
Send 'hold:e,300|wait:2500'; Shot
if (Shown) { "load order dialog still shown after confirming 'Current'"; exit 9 }
"load order dialog answered: Current (the experiment plugins stay active)"
exit 10
