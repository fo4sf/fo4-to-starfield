# Full test cycle: close Starfield, redeploy staging, launch, load the last save, clear dialogs, coc into a cell, screenshot.
# usage: cycle.ps1 -Staging <staging dir> -Starfield <game dir> -Cell FO4Port_Vault111Cryo -Shot <out.png> [-CellJson <cell.json>]
# -Save <name>: load that save by name from the main menu's console (`load <name>`, the line qstep.ps1's load step types
# in game) instead of Continue, which loads the NEWEST save: the owner's own play (new-game autosaves, 2026-10-28) then
# took every save-based run into ship combat, where the HUD guard never passed (door check (a) INCONCLUSIVE
# NOT_ACTIVATED, a cockpit in end_state.png; Install). testqueue.py passes the session's dedicated save
# fo4sf_test_<build> once it exists. <name>.sfs must be in the Saves folder (FO4SF_SAVES_DIR, else
# OneDrive\Documents\My Games\Starfield\Saves, else Documents\My Games\Starfield\Saves) before anything is closed,
# deployed or launched, and the save must load (the HUD seen) or the run stops: exit 11 either way.
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
# 7 an installed experiment plugin's master is not active (exp_install.py order; the game is not launched), or the port
# to test is wrong: -Staging is an interior batch stage, or with FO4SF_PORT=installed the installed port is not the one
# its deploy record (or FO4SF_PORT_SHA256) names (nothing launched),
# 8 the experiment plugins are no longer active after the save loaded, or the load order dialog could not be answered
# with "Current" (loadorder.ps1; nothing tested, the game is left running for the runner to close),
# 9 no valid controller lease for this owner, or python could not run the check (only with FO4SF_LEASE_DIR set;
# nothing closed, deployed or launched), 10 Steam (or Starfield.exe, FO4SF_LAUNCH=exe, or sfse_loader.exe, FO4SF_LAUNCH=sfse) was asked to start the game and no Starfield process was alive 20 s
# after it appeared (the screen is saved to -Shot; nothing tested; the runner may launch again after its own checks),
# 11 -Save names a save that is not in the Saves folder (nothing closed, deployed or launched), or that save did not
# load (no HUD within the wait after the console load; the screen is saved to -Shot; nothing tested; the game is left
# running for the runner to close).
param([Parameter(Mandatory)][string]$Staging, [Parameter(Mandatory)][string]$Starfield, [string]$Cell = 'FO4Port_Vault111Cryo',
      [string]$Shot = (Join-Path $env:TEMP 'fo4sf_cycle.png'), [string]$CellJson = '', [string]$Save = '')
if ($Cell -notmatch '^[A-Za-z0-9_]+$') { "cell name must be letters, digits and underscores (it is typed into the game): $Cell"; exit 1 }
if ($Save -and $Save -notmatch '^[A-Za-z0-9_]+$') { "save name must be letters, digits and underscores (it is typed into the game): $Save"; exit 1 }
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
# An interior batch stage (result.json; doors_anim_b00 and its port folder, 2026-10-28) holds a built port: FO4Port.esm
# and its archives, no loose meshes or textures. deploy_starfield.py install --staging would pack new archives from
# nothing after the uninstall below had removed the installed port. Such a port goes in with install --batch, and the
# runs test it with FO4SF_PORT=installed. Checked before anything is closed or touched.
if ($Save) {
  # the named save must exist before anything is touched (the runner's dedicated_save() reads the same folder; a save
  # set aside as <name>.sfs.bak or a <name>_s100 does not count, 2026-10-17)
  $savesDir = $env:FO4SF_SAVES_DIR
  if (-not $savesDir) {
    $savesDir = Join-Path $env:USERPROFILE 'OneDrive\Documents\My Games\Starfield\Saves'
    if (-not (Test-Path $savesDir)) { $savesDir = Join-Path $env:USERPROFILE 'Documents\My Games\Starfield\Saves' }
  }
  $sfs = @(Get-ChildItem -Path $savesDir -Filter '*.sfs' -File -ErrorAction SilentlyContinue)
  $saveFile = $sfs | Where-Object { $_.Name -ieq "$Save.sfs" } | Select-Object -First 1
  if (-not $saveFile) { "-Save ${Save}: no $Save.sfs in $savesDir (nothing closed, deployed or launched)"; exit 11 }
  $newest = $sfs | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  "save to load by name: $($saveFile.Name) ($($saveFile.Length) bytes, $($saveFile.LastWriteTime.ToString('s')))" +
    $(if ($newest.Name -ine $saveFile.Name) { "; the newest save is $($newest.Name), which Continue would have loaded" } else { '; it is the newest save' })
  # the named route stops on "no HUD", so the HUD check itself must be able to run (Prompt-Visible's rule: a Python
  # without Pillow read as "no HUD" would blame the save): a shot of whatever is on screen now must read yes or no
  $probe = Join-Path $env:TEMP 'fo4sf_hudprobe.png'
  powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'shot.ps1') -Out $probe | Out-Null
  $hudPy = if ($env:FO4SF_PYTHON) { $env:FO4SF_PYTHON } else { 'python' }
  $global:LASTEXITCODE = $null
  $hudAns = & $hudPy (Join-Path $PSScriptRoot 'hud_visible.py') $probe 2>$null
  if ($LASTEXITCODE -ne 0 -or @('yes', 'no') -notcontains "$hudAns") {
    "the HUD check cannot run (python exit $LASTEXITCODE; set FO4SF_PYTHON to a Python with Pillow): a load by name could not be judged; nothing closed, deployed or launched"; exit 5
  }
}
if ($env:FO4SF_PORT -ne 'installed') {
  $stg = $Staging.TrimEnd('\', '/')
  $stageRoot = if ((Split-Path -Leaf $stg) -eq 'port') { Split-Path $stg } else { $stg }
  if (Test-Path -LiteralPath (Join-Path $stageRoot 'result.json')) {
    "$Staging is an interior batch stage (result.json): install it with deploy_starfield.py install --batch and run with FO4SF_PORT=installed: not launching"; exit 7
  }
}
$p = Get-Process Starfield -ErrorAction SilentlyContinue
$pidFile = Join-Path $PSScriptRoot 'cycle_pid.txt'           # local only: the PID of the game this script launched
$own = if (Test-Path $pidFile) { [int](Get-Content $pidFile) } else { 0 }
if ($p -and $p.Id -ne $own) { "Starfield is running but was not started by cycle.ps1 (the user's own session): not closing it"; exit 3 }
if ($p) { $p.CloseMainWindow() | Out-Null; Start-Sleep 8; $p.Refresh(); if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force -Confirm:$false }; Start-Sleep 4 }
# FO4SF_PORT=installed (opt-in, 2026-10-28; set by testqueue.py for a queue planned with --port installed): the port
# already installed is the one this launch tests, so nothing is uninstalled or deployed (a redeploy of -Staging would
# silently put the older port back over an installed one such as doors_anim_b00). deploy_starfield.py verify checks it
# against its own record instead: every file's size and sha256, FO4Port.esm and its companions active in Plugins.txt,
# and with FO4SF_PORT_SHA256 the plugin the queue pinned. Any difference: exit 7, nothing launched.
# Fail closed as the lease gate does (Codex on #558): python resolved first, the stale exit code cleared, an invocation
# error caught, so a reused host's earlier 0 never passes. The game folder goes in without a trailing backslash:
# PowerShell 5.1 quotes a path with a space as "...\", and the closing quote, escaped by that backslash, would swallow
# the pin that follows (Codex on #558).
if ($env:FO4SF_PORT -eq 'installed') {
  if (-not (Get-Command python -ErrorAction SilentlyContinue)) { "python not found: the installed port cannot be checked: not launching"; exit 7 }
  $sfArg = $sf.TrimEnd('\', '/')
  if ($sfArg -match ':$') { $sfArg = $sf }                       # a drive root keeps its backslash ("D:" is D:'s cwd)
  $verArgs = @('verify', '--starfield', $sfArg)
  if ($env:FO4SF_PORT_SHA256) { $verArgs += @('--plugin-sha256', $env:FO4SF_PORT_SHA256) }
  $global:LASTEXITCODE = $null
  try { $ver = python -I "$repo\scripts\deploy_starfield.py" @verArgs; $verCode = $LASTEXITCODE }
  catch { $ver = "deploy_starfield.py could not be run: $_"; $verCode = $null }
  $ver | Select-Object -Last 1
  if ($null -eq $verCode -or $verCode -ne 0) { "the installed port is not the recorded one (deploy_starfield.py verify exit $verCode): not launching"; exit 7 }
} else {
  python -I "$repo\scripts\deploy_starfield.py" uninstall --starfield $sf | Out-Null
  python -I "$repo\scripts\deploy_starfield.py" install --staging $Staging --starfield $sf | Select-Object -Last 1
}
# A staged experiment installed before this launch (testqueue.py pre_launch) was appended to Plugins.txt before the
# deploy above appended FO4Port.esm again: a plugin of it that masters FO4Port.esm (the slice door plugin) is moved
# after its masters here. Nothing installed or nothing to move: no change. A master missing: exit 7, no launch.
if (Test-Path (Join-Path $sf 'Data\FO4SFExp.install.json')) {
  $ord = python -I "$repo\scripts\game\exp_install.py" order --starfield $sf
  $ordCode = $LASTEXITCODE
  $ord | Select-Object -Last 1
  if ($ordCode -ne 0) { "experiment plugin order could not be fixed (exit $ordCode): not launching"; exit 7 }
}
# The map markers plugin (map_markers_install.py) goes after FO4Port, so the planned reads' load indexes stay as they were.
# A master of it inactive or missing from Data: it refuses before writing, exit 7, no launch (Codex, #399).
if (Test-Path (Join-Path $sf 'Data\FO4SFMapMarkers.install.json')) {
  $mmOrd = python -I "$repo\scripts\game\map_markers_install.py" order --starfield $sf
  $mmCode = $LASTEXITCODE
  $mmOrd | Select-Object -Last 1
  if ($mmCode -ne 0) { "map markers plugin order refused (exit $mmCode): not launching"; exit 7 }
}
# The observation bridge (bridge_install.py) goes LAST: the planned reads address the experiment's records by load
# index, and a bridge line above them shifted every index by one (cave_core64c_1015 a1, 2026-10-15)
# A bridge held off by plugin_toggle.py that the game ticked again makes order exit nonzero: no launch, or a bridge-off
# run would be judged with the bridge active (Codex on #407)
if (Test-Path (Join-Path $sf 'Data\FO4SFBridge.install.json')) {
  $bord = python -I "$repo\scripts\game\bridge_install.py" order --starfield $sf
  $bordCode = $LASTEXITCODE
  $bord | Select-Object -Last 1
  if ($bordCode -ne 0) { "bridge plugin order refused (exit $bordCode): not launching"; exit 7 }
}
function Wait-Screen($label, $maxSec, $check, $each = $null) {
  # poll a screenshot every 3 s until $check (script block: png path -> bool) is true; prints how long it took.
  # false after $maxSec: the caller goes on as the old fixed timer would have (docs/ai/optimization.md 2026-10-10).
  # $each (script block, optional) runs before every poll: the named load's load order probe.
  $t0 = Get-Date
  $png = Join-Path $env:TEMP 'fo4sf_wait.png'
  while (((Get-Date) - $t0).TotalSeconds -lt $maxSec) {
    if ($each) { & $each }
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
# FO4SF_LAUNCH=exe (opt-in, 2026-10-19): start Starfield.exe from the game folder instead of asking Steam; the game
# inherits this script's token. Steam error 84 on the night run (07:46Z) was the game's own exit code 0x54 about 3 s
# after start; crashwatch's ProcDump (-w, waiting for Starfield.exe) logged a BREAKPOINT on that process a second
# before, as on every short-lived start since Oct 18 (supported: the debugger attach ends the game). An exe launch is
# not expected to avoid that; stop the watcher for runner launches. Unset or any other value: the steam:// launch.
# FO4SF_LAUNCH=sfse (opt-in, 2026-10-28; set by testqueue.py for a queue planned with --launch sfse): start
# sfse_loader.exe from the game folder, which starts Starfield.exe with SFSE (the launcher's route=sfse). A Steam or exe
# launch loads no SFSE plugin, so a run that compares FO4SFBorder modes through them compared nothing (Install,
# 2026-10-28). The wait below follows the Starfield process, not the loader, as before.
$launch = 'steam://rungameid/1716740'
$exe = if ($env:FO4SF_LAUNCH -eq 'exe') { 'Starfield.exe' } elseif ($env:FO4SF_LAUNCH -eq 'sfse') { 'sfse_loader.exe' } else { '' }
if ($exe) {
  $launch = Join-Path $sf $exe
  if (-not (Test-Path -LiteralPath $launch -PathType Leaf)) { "FO4SF_LAUNCH=$($env:FO4SF_LAUNCH) but $launch is missing: nothing launched, nothing tested"; exit 10 }
  Start-Process -FilePath $launch -WorkingDirectory $sf
} else {
  Start-Process $launch
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
# 240 s and 300 s (were 120 s): the first v6e launch (2026-10-21, doors_out and the evidence launch) reached gameplay
# after both 120 s waits had run out, so coc.ps1 found no HUD; a wait ends as soon as its screen is seen
Wait-Screen 'main menu' 240 $MenuShown | Out-Null

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
if ($Save) {
  # the console works at the main menu (the probe sessions coc from there); `load <name>` is the line qstep.ps1's load step
  # types in game, and no Continue confirmation follows. The achievements popup opens with this first console opening of
  # the session, and keys still go to the console line while it is open; after the load, Clear-AchievementsPopup reads
  # the screen before it presses anything, as on the Continue route
  Send "click:768,432|wait:6000|key:grave|wait:1500|type:load $Save|wait:400|key:enter|wait:3000"
} else {
  Send 'click:768,432|wait:6000|key:up|wait:700|key:enter|wait:2500|hold:e,300|wait:2500'
}
powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'loadorder.ps1')
$lo = $LASTEXITCODE
if ($lo -eq 2) { "input guard stopped the sequence (someone else has focus)"; exit 2 }
if ($lo -eq 5) { exit 5 }
if ($lo -eq 9) { "the load order dialog could not be answered with 'Current': not confirming 'Save'"; exit 8 }
# On the named route the dialog can open later than this one probe 3 s after Enter, and an unanswered dialog would end
# in exit 11 ("did not load"): as qstep.ps1's load step does, probe again before every HUD poll until the dialog has
# been seen (loadorder.ps1 exit 0 = no dialog, 10 = answered with Current, 5 = check could not run: again next pass)
$ProbeLoadOrder = {
  if ($script:lo -ne 0) { return }
  powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'loadorder.ps1') | Out-Null
  $script:lo = $LASTEXITCODE
  # Write-Host for every line here: the block runs inside Wait-Screen, whose result is assigned, so a string on the
  # output stream would be collected for that assignment and lost when exit unwinds the script
  if ($script:lo -eq 2) { Write-Host "input guard stopped the sequence (someone else has focus)"; exit 2 }
  if ($script:lo -eq 9) { Write-Host "the load order dialog could not be answered with 'Current': not confirming 'Save'"; exit 8 }
  if ($script:lo -eq 10) { Write-Host 'load order dialog answered: Current (the experiment plugins stay active)' }
  if ($script:lo -eq 5) { $script:lo = 0 }
}
# No blind E here: Continue loads the newest save, and on the owner's vanilla save the player faces Vasco. An E sent
# after the load most likely opened his dialogue and hid the HUD for the whole 300 s wait (v6e retry 4, 2026-10-21:
# "save loaded: not seen within 300 s", then the runner's recover got the HUD back with one Escape; supported, not
# seen on screen). E now only closes the achievements popup, when its text is read.
Clear-AchievementsPopup | Out-Null
$hudSeen = Wait-Screen 'save loaded' 300 $HudShown $(if ($Save) { $ProbeLoadOrder } else { $null })
if (-not $hudSeen) {
  # a dialogue, menu or popup hides the HUD: up to two Escapes, each followed by a check. Two, not recover's three: if
  # the HUD check itself missed, the first Escape opens the pause menu and the second closes it again
  $n = 0
  while ($n -lt 2) {
    Send 'key:esc|wait:2000'; $n++
    if (Wait-Screen "save loaded after $n Escape(s)" 15 $HudShown) { $hudSeen = $true; break }
  }
}
if ($Save -and -not $hudSeen) {
  # the Continue route goes on without the HUD, as the old fixed timer did; a named load that shows no HUD loaded
  # something else or nothing, and a run on it would test the wrong state
  powershell -NoProfile -ExecutionPolicy Bypass -File $PSScriptRoot\shot.ps1 -Out $Shot | Out-Null
  "the save $Save did not load: no HUD within the wait (screen: $Shot): nothing tested; the game is left running for the runner to close"; exit 11
}
# Starfield can still have switched the load order. Either record: a bridge held off by itself (a bridge-only crash
# split) the game ticked again must stop the run too (Codex on #407)
if ((Test-Path (Join-Path $sf 'Data\FO4SFExp.install.json')) -or (Test-Path (Join-Path $sf 'Data\FO4SFBridge.install.json'))) {
  $act = python -I "$repo\scripts\game\exp_install.py" active --starfield $sf
  $actCode = $LASTEXITCODE
  $act | Select-Object -Last 1
  if ($actCode -ne 0) { "Starfield changed our plugins' activation while loading the save: not testing (exit $actCode)"; exit 8 }
}
if (Test-Path (Join-Path $sf 'Data\FO4SFMapMarkers.install.json')) {   # the same check for the map markers plugin (Codex, #399)
  $mmAct = python -I "$repo\scripts\game\map_markers_install.py" active --starfield $sf
  $mmActCode = $LASTEXITCODE
  $mmAct | Select-Object -Last 1
  if ($mmActCode -ne 0) { "Starfield deactivated the map markers plugin while loading the save: not testing (exit $mmActCode)"; exit 8 }
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
  $cocArgs = @('-Cell', $name, '-CellJson', $CellJson)
  if (Test-Path (Join-Path $sf 'Data\FO4SFBridge.install.json')) { $cocArgs += '-Bridge' }   # the arrival read from the bridge
  powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'coc.ps1') @cocArgs
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
