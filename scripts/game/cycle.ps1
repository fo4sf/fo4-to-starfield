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
# 5 a screen check could not run (nothing pressed), 6 an activation prompt sits under the crosshair (nothing pressed),
# 7 an installed experiment plugin's master is not active (exp_install.py order; the game is not launched),
# 8 the experiment plugins are no longer active after the save loaded, or the load order dialog could not be answered
# with "Current" (loadorder.ps1; nothing tested, the game is left running for the runner to close),
# 9 no valid controller lease for this owner, or python could not run the check (only with FO4SF_LEASE_DIR set;
# nothing closed, deployed or launched), 10 Starfield.exe (or Steam, FO4SF_LAUNCH=steam) was asked to start the game and no Starfield process was alive 20 s
# after it appeared (the screen is saved to -Shot; nothing tested; the runner may launch again after its own checks).
param([Parameter(Mandatory)][string]$Staging, [Parameter(Mandatory)][string]$Starfield, [string]$Cell = 'FO4Port_Vault111Cryo',
      [string]$Shot = (Join-Path $env:TEMP 'fo4sf_cycle.png'), [string]$CellJson = '')
if ($Cell -notmatch '^[A-Za-z0-9_]+$') { "cell name must be letters, digits and underscores (it is typed into the game): $Cell"; exit 1 }
$repo = Split-Path (Split-Path $PSScriptRoot); $sf = $Starfield
$i = (Join-Path $PSScriptRoot 'input.ps1'); $env:LEGACY = '1'
# Controller lease (docs/ai/leader-core.md section 6; opt-in, default off): with FO4SF_LEASE_DIR set, the game is only
# closed, redeployed and launched while FO4SF_LEASE_OWNER (default Claude) holds an unexpired lease in that folder;
# otherwise exit 9 before anything is touched. Unset, this block does nothing and the script behaves as before.
# lease.py reads the folder from FO4SF_LEASE_DIR itself: passed as an argument, a folder with a space and a trailing
# backslash would reach python mangled (PowerShell 5.1 quoting) and the check could fail open.
# The gate fails closed on the invocation itself, not only on lease.py's exit code (QA on #179): python that cannot be
# resolved raises CommandNotFoundException and leaves $LASTEXITCODE as it was, so in a reused host (& cycle.ps1 after
# another command) an earlier 0 passed the old guard. Now python is resolved first, the stale code is cleared, an
# invocation error is caught, and only lease.py's own fresh exit 0 launches.
if ($env:FO4SF_LEASE_DIR) {
  $leaseOwner = if ($env:FO4SF_LEASE_OWNER) { $env:FO4SF_LEASE_OWNER } else { 'Claude' }
  if (-not (Get-Command python -ErrorAction SilentlyContinue)) { "python not found: the controller lease for $leaseOwner in $($env:FO4SF_LEASE_DIR) cannot be checked: not launching"; exit 9 }
  $global:LASTEXITCODE = $null   # global: native commands set the global variable, a plain assignment here would shadow it
  try { $leaseOut = python -I "$repo\scripts\game\lease.py" status --require $leaseOwner; $leaseCode = $LASTEXITCODE }
  catch { $leaseOut = "lease.py could not be run: $_"; $leaseCode = $null }
  $leaseOut | Select-Object -Last 1
  if ($null -eq $leaseCode -or $leaseCode -ne 0) { "no valid controller lease for $leaseOwner in $($env:FO4SF_LEASE_DIR) (lease.py exit $leaseCode): not launching"; exit 9 }
}
$p = Get-Process Starfield -ErrorAction SilentlyContinue
$pidFile = Join-Path $PSScriptRoot 'cycle_pid.txt'           # local only: the PID of the game this script launched
$own = if (Test-Path $pidFile) { [int](Get-Content $pidFile) } else { 0 }
if ($p -and $p.Id -ne $own) { "Starfield is running but was not started by cycle.ps1 (the user's own session): not closing it"; exit 3 }
if ($p) { $p.CloseMainWindow() | Out-Null; Start-Sleep 8; $p.Refresh(); if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force -Confirm:$false }; Start-Sleep 4 }
python -I "$repo\scripts\deploy_starfield.py" uninstall --starfield $sf | Out-Null
python -I "$repo\scripts\deploy_starfield.py" install --staging $Staging --starfield $sf | Select-Object -Last 1
# A staged experiment installed before this launch (testqueue.py pre_launch) was appended to Plugins.txt before the
# deploy above appended FO4Port.esm again: a plugin of it that masters FO4Port.esm (the slice door plugin) is moved
# after its masters here. Nothing installed or nothing to move: no change. A master missing: exit 7, no launch.
if (Test-Path (Join-Path $sf 'Data\FO4SFExp.install.json')) {
  $ord = python -I "$repo\scripts\game\exp_install.py" order --starfield $sf
  $ordCode = $LASTEXITCODE
  $ord | Select-Object -Last 1
  if ($ordCode -ne 0) { "experiment plugin order could not be fixed (exit $ordCode): not launching"; exit 7 }
}
# The observation bridge (bridge_install.py) goes LAST: the planned reads address the experiment's records by load
# index, and a bridge line above them shifted every index by one (cave_core64c_1015 a1, 2026-10-15)
if (Test-Path (Join-Path $sf 'Data\FO4SFBridge.install.json')) {
  python -I "$repo\scripts\game\bridge_install.py" order --starfield $sf | Select-Object -Last 1
}
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
  Write-Host ("{0}: not seen within {1} s, going on" -f $label, $maxSec)   # Write-Host: callers pipe the result to Out-Null
  return $false
}
$MenuShown = { param($png)                                      # main menu: "PRESS ANY BUTTON TO START" along the bottom
  $t = powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'ocr.ps1') -Image $png -X 380 -Y 645 -W 520 -H 45
  return (($t | Out-String) -match 'PRESS ANY') }
$HudShown = { param($png)                                       # in game: oxygen ring + health bar (hud_visible.py)
  $py = if ($env:FO4SF_PYTHON) { $env:FO4SF_PYTHON } else { 'python' }
  return ((& $py (Join-Path $PSScriptRoot 'hud_visible.py') $png 2>$null) -eq 'yes') }

# One Steam launch; it counts once a Starfield process is still alive 20 s after it appeared. The first launch of a
# session can exit within ~2 s (2026-10-18: the runner's launch at 14:32:38 and the owner's own first try at 14:38:16
# both died after 2 s; the owner's second try stayed up; Steam console_log.txt, no error line). Another try is the
# runner's (exit 10): it re-checks the lease, STOP, the Guardian and idle before every launch (Codex, #358).
# The launch (2026-10-19): Starfield.exe from the game folder, as the owner launches it ("from the .exe; admin is only
# the first run after an update", 14:34Z). The night run's steam:// launch at 07:46Z failed with Steam error 84.
# FO4SF_LAUNCH=steam keeps the old steam:// launch. The exe inherits this script's token: a runner that is not
# elevated starts a game that is not elevated, which its input can reach (UIPI, supported). A missing exe is a dead start.
$launch = Join-Path $sf 'Starfield.exe'
if ($env:FO4SF_LAUNCH -eq 'steam') {
  $launch = 'steam://rungameid/1716740'
  Start-Process $launch
} else {
  if (-not (Test-Path -LiteralPath $launch -PathType Leaf)) { "$launch is missing: nothing launched, nothing tested"; exit 10 }
  Start-Process -FilePath $launch -WorkingDirectory $sf
}
$q = $null
$deadline = (Get-Date).AddSeconds(150)
while ((Get-Date) -lt $deadline) {
  $q = Get-Process Starfield -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($q) { break }
  Start-Sleep 1
}
if ($q) {
  Start-Sleep 20
  $q = Get-Process -Id $q.Id -ErrorAction SilentlyContinue
  if ($q) { $q.Id | Set-Content $pidFile }
}
if (-not $q) {
  # no game to drive: say so, with the screen (a Steam dialog, say), instead of failing later as an input-guard exit 2
  # (door_rounds_sdm, 2026-10-18 20:32Z: cycle exit 2 after 5 minutes with no Starfield process)
  powershell -NoProfile -ExecutionPolicy Bypass -File $PSScriptRoot\shot.ps1 -Out $Shot | Out-Null
  "Starfield did not stay up 20 s after $launch (screen: $Shot): nothing tested"; exit 10
}
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

# main menu: Continue (E confirms "Continue from your last saved game?"), answer Starfield's "different Creations Load
# Order" dialog with "Current" (loadorder.ps1), clear load-time notices, wait for the save to load. 2026-10-13 (launch
# frames 23:20): the second E picked the preselected "Save", Starfield deactivated every experiment plugin and each later
# coc into our worldspaces froze.
Send 'click:768,432|wait:6000|key:up|wait:700|key:enter|wait:2500|hold:e,300|wait:2500'
powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'loadorder.ps1')
$lo = $LASTEXITCODE
if ($lo -eq 2) { "input guard stopped the sequence (someone else has focus)"; exit 2 }
if ($lo -eq 5) { exit 5 }
if ($lo -eq 9) { "the load order dialog could not be answered with 'Current': not confirming 'Save'"; exit 8 }
Send 'hold:e,300|wait:3000'
Wait-Screen 'save loaded' 120 $HudShown | Out-Null
if (Test-Path (Join-Path $sf 'Data\FO4SFExp.install.json')) {   # Starfield can still have switched the load order
  $act = python -I "$repo\scripts\game\exp_install.py" active --starfield $sf
  $actCode = $LASTEXITCODE
  $act | Select-Object -Last 1
  if ($actCode -ne 0) { "Starfield deactivated the experiment plugins while loading the save: not testing (exit $actCode)"; exit 8 }
}
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
