# Full test cycle: close Starfield, redeploy staging, launch, load the last save, clear dialogs, coc into a cell, screenshot.
# usage: cycle.ps1 -Staging <staging dir> -Starfield <game dir> -Cell FO4Port_Vault111Cryo -Shot <out.png> [-CellJson <cell.json>]
# -CellJson: enter the cell with coc.ps1, which verifies the arrival at the cell's COC marker (needs FO4SF_PYTHON = a Python
# with Pillow); exit 4 if the jump did not happen. Without it, coc is typed blind as before.
# Starfield's "Use of certain console commands will disable achievements." popup (2026-10-10, observed step by step):
# - it opens together with the console, the first time the console is opened in a session (main menu or game);
# - while the console is open, keys go to the console line, so E cannot close it; with the console closed, E does;
# - in game it can be open but INVISIBLE and then swallows the keyboard (console, Tab, E) until it is closed.
# So: open + close the console, then press E once (unless an activation prompt is under the crosshair: E would use it),
# then OCR-check and press E again if it is still shown. (Earlier: the popup swallowed the coc; a fixed-time E missed it.)
# coc from the main menu works but is unusable for tests: the blank character is pulled into the new-game start after a
# few minutes (load screen, then a hang).
# Exit codes: 1 bad cell name, 2 input guard, 3 the game was not started by this script, 4 arrival not verified,
# 5 a screen check could not run (nothing pressed), 6 an activation prompt sits under the crosshair (nothing pressed).
param([Parameter(Mandatory)][string]$Staging, [Parameter(Mandatory)][string]$Starfield, [string]$Cell = 'FO4Port_Vault111Cryo',
      [string]$Shot = (Join-Path $env:TEMP 'fo4sf_cycle.png'), [string]$CellJson = '')
if ($Cell -notmatch '^[A-Za-z0-9_]+$') { "cell name must be letters, digits and underscores (it is typed into the game): $Cell"; exit 1 }
$repo = Split-Path (Split-Path $PSScriptRoot); $sf = $Starfield
$i = (Join-Path $PSScriptRoot 'input.ps1'); $env:LEGACY = '1'
$p = Get-Process Starfield -ErrorAction SilentlyContinue
$pidFile = Join-Path $PSScriptRoot 'cycle_pid.txt'           # local only: the PID of the game this script launched
$own = if (Test-Path $pidFile) { [int](Get-Content $pidFile) } else { 0 }
if ($p -and $p.Id -ne $own) { "Starfield is running but was not started by cycle.ps1 (the user's own session): not closing it"; exit 3 }
if ($p) { $p.CloseMainWindow() | Out-Null; Start-Sleep 8; $p.Refresh(); if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force -Confirm:$false }; Start-Sleep 4 }
python -I "$repo\scripts\deploy_starfield.py" uninstall --starfield $sf | Out-Null
python -I "$repo\scripts\deploy_starfield.py" install --staging $Staging --starfield $sf | Select-Object -Last 1
function Wait-Screen($label, $maxSec, $check) {
  # poll a screenshot every 3 s until $check (script block: png path -> bool) is true; prints how long it took.
  # false after $maxSec: the caller goes on as the old fixed timer would have (docs/ai/optimization.md 2026-10-10).
  $t0 = Get-Date
  $png = Join-Path $env:TEMP 'fo4sf_wait.png'
  while (((Get-Date) - $t0).TotalSeconds -lt $maxSec) {
    powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'shot.ps1') -Out $png | Out-Null
    if (& $check $png) { Write-Host ("{0} after {1} s" -f $label, [int]((Get-Date) - $t0).TotalSeconds); return $true }
    Start-Sleep 3
  }
  "{0}: not seen within {1} s, going on" -f $label, $maxSec
  return $false
}
$MenuShown = { param($png)                                      # main menu: "PRESS ANY BUTTON TO START" along the bottom
  $t = powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'ocr.ps1') -Image $png -X 380 -Y 645 -W 520 -H 45
  return (($t | Out-String) -match 'PRESS ANY') }
$HudShown = { param($png)                                       # in game: oxygen ring + health bar (hud_visible.py)
  $py = if ($env:FO4SF_PYTHON) { $env:FO4SF_PYTHON } else { 'python' }
  return ((& $py (Join-Path $PSScriptRoot 'hud_visible.py') $png 2>$null) -eq 'yes') }

Start-Process 'steam://rungameid/1716740'
$deadline = (Get-Date).AddSeconds(150); while ((Get-Date) -lt $deadline) { $q = Get-Process Starfield -ErrorAction SilentlyContinue; if ($q) { $q.Id | Set-Content $pidFile; break }; Start-Sleep 3 }
Start-Sleep 10
Wait-Screen 'main menu' 120 $MenuShown | Out-Null

function Send($seq) {
  powershell -NoProfile -ExecutionPolicy Bypass -File $i -Seq $seq | Out-Null
  if ($LASTEXITCODE -ne 0) { "input guard stopped the sequence (someone else has focus)"; exit 2 }
}
function Popup-Shown {
  # true if the achievements popup is on screen (OCR of its text box); presses nothing
  $tmp = Join-Path $env:TEMP 'fo4sf_popup.png'
  powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'shot.ps1') -Out $tmp | Out-Null
  $text = powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'ocr.ps1') -Image $tmp -X 390 -Y 285 -W 500 -H 60
  if ($LASTEXITCODE -ne 0) { "popup OCR check failed (ocr.ps1 exit $LASTEXITCODE): nothing pressed"; exit 5 }   # fail closed
  return (($text | Out-String) -match 'achievement')
}
function Clear-AchievementsPopup {
  # true if the popup was on screen and E was sent to close it (the console must be closed: keys go to its line otherwise)
  if (Popup-Shown) { Send 'hold:e,300|wait:1500'; return $true }
  return $false
}

# main menu: Continue, clear load-time notices, wait for the save to load
Send 'click:768,432|wait:6000|key:up|wait:700|key:enter|wait:2500|hold:e,300|wait:2500|hold:e,300|wait:3000'
Wait-Screen 'save loaded' 120 $HudShown | Out-Null
function Prompt-Visible {
  # an activation prompt (door, NPC, item) under the crosshair: E would use it
  $tmp = Join-Path $env:TEMP 'fo4sf_prompt.png'
  powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'shot.ps1') -Out $tmp | Out-Null
  $py = if ($env:FO4SF_PYTHON) { $env:FO4SF_PYTHON } else { 'python' }
  $out = & $py (Join-Path $PSScriptRoot 'prompt_visible.py') $tmp 2>$null
  if ($LASTEXITCODE -ne 0 -or @('yes', 'no') -notcontains "$out") {   # fail closed (QA 2026-10-10: a missing Pillow read as "no prompt")
    "prompt check failed (python exit $LASTEXITCODE; set FO4SF_PYTHON to a Python with Pillow): nothing pressed"; exit 5
  }
  return ("$out" -eq 'yes')
}
# first console opening of the session raises the popup (possibly invisible); close the console, then E closes the popup
Send 'key:grave|wait:1500|type:fov 90|wait:300|key:enter|wait:2500|key:grave|wait:1500'
if (Prompt-Visible) { Send 'move:300,0|wait:800' }           # look away from the prompt before E
if (Prompt-Visible) { "activation prompt still under the crosshair after looking away: E would use it, stopping"; exit 6 }
Send 'hold:e,300|wait:1500'
Clear-AchievementsPopup | Out-Null
if ($CellJson) {
  $name = $Cell -replace '^FO4Port_', ''
  powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'coc.ps1') -Cell $name -CellJson $CellJson
  if ($LASTEXITCODE -ne 0) { "coc.ps1 could not verify the arrival in $Cell (exit $LASTEXITCODE)"; exit 4 }
} else {
  $clear = 'key:back|' * 40                                    # empties the console line, whatever was left in it
  Send "key:grave|wait:1500|${clear}type:coc $Cell|wait:400|key:enter|wait:3000"
  if (Popup-Shown) {                                          # the popup swallowed the coc and the console is still open
    Send 'key:grave|wait:1200'                                 # close the console first, or E goes to its line
    Clear-AchievementsPopup | Out-Null
    Send "key:grave|wait:1500|${clear}type:coc $Cell|wait:400|key:enter|wait:3000"
  }
  Wait-Screen 'cell loaded' 90 $HudShown | Out-Null
}
powershell -NoProfile -ExecutionPolicy Bypass -File $PSScriptRoot\shot.ps1 -Out $Shot | Out-Null
"cycle done -> $Shot"
