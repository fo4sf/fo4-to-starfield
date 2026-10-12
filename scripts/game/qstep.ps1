# One queued in-game test step for testqueue.py: performs the actions, writes raw observations, judges nothing.
# usage: qstep.ps1 -Spec <test.json> -Out <test dir>      (Starfield in front, in the test's cell, console closed)
# Writes <Out>\obs.json. Every key press goes through input.ps1's foreground guard; testqueue.py sets
# FO4SF_NO_FOCUS_STEAL=1, so a guard stop (the owner switched windows) ends the step with exit 2 and nothing more is sent.
# Exit 0: observations written (they may still be incomplete: the judge decides). 2: input guard. 3: console could not be
# opened safely (nothing typed). 4: bad spec.
# Kinds (spec.kind): route (stairs/door, via route_run.ps1), fall (drop onto a floor point), movable (walk into an item and
# read its position before and after), travel (activate a load door, read where the player arrives), terrain (drop onto
# points of known height), npc_nav (spawn a vanilla actor at A, make it walk to the player at B, sample, remove it),
# door_trip (coc into a world, through a load door into an interior and back out, save, load: every arrival read),
# godmode, save, load, recover. terrain and npc_nav may set the time of day / weather after the arrival (time_of_day,
# time_methods, time_repin, weather, weather_lock, light_wait_ms: Apply-Light) and record the light before and after
# (terrain: also on every probe shot; the time command that worked is typed again before each probe), and type
# whitelisted console_pre (before the travel) / console_post (after the arrival) commands, OCR'd into obs.console.
param([Parameter(Mandatory)][string]$Spec, [Parameter(Mandatory)][string]$Out, [string]$PluginIndex = '02')
$env:LEGACY = '1'
if (-not $env:FO4SF_PYTHON) { $env:FO4SF_PYTHON = 'C:\Modding\venv-render\Scripts\python.exe' }
$here = $PSScriptRoot
$i = Join-Path $here 'input.ps1'; $shot = Join-Path $here 'shot.ps1'; $readpos = Join-Path $here 'readpos.ps1'
$t = Get-Content $Spec -Raw | ConvertFrom-Json
New-Item -ItemType Directory -Force $Out | Out-Null
$inv = [Globalization.CultureInfo]::InvariantCulture
$obs = [ordered]@{ kind = $t.kind; started = (Get-Date).ToString('s') }

function Save-Obs { $obs['finished'] = (Get-Date).ToString('s'); $obs | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $Out 'obs.json') -Encoding utf8 }
function Send($seq) {
  # Windows PowerShell 5.1 (and 7.0-7.2) drops the double quotes inside a native argument: 'cf "Actor.PathToReference"'
  # reached input.ps1 as 'cf Actor.PathToReference' (2026-10-11). Written as \" they arrive as typed.
  $arg = $seq
  if ($PSVersionTable.PSVersion.Major -lt 7 -or "$PSNativeCommandArgumentPassing" -in '', 'Legacy') { $arg = $seq -replace '"', '\"' }
  powershell -NoProfile -ExecutionPolicy Bypass -File $i -Seq $arg | Out-Null
  if ($LASTEXITCODE -ne 0) { $obs['stopped'] = 'input guard'; Save-Obs; exit 2 }
}
function Console-Open {
  powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $here 'console_open.ps1') | Out-Null
  $c = $LASTEXITCODE
  if ($c -eq 2) { $obs['stopped'] = 'input guard'; Save-Obs; exit 2 }
  if ($c -ne 0) { $obs['stopped'] = "console not opened safely ($c)"; Save-Obs; exit 3 }
}
function Read-Pos([string]$ref = '', [int]$tries = 3) {
  # up to 3 reads: OCR sometimes drops or shifts a column; a read with x == z or a missing value is retried
  $p = 'fail'
  for ($n = 0; $n -lt $tries; $n++) {
    if ($ref) { $p = powershell -NoProfile -ExecutionPolicy Bypass -File $readpos -Ref $ref } else { $p = powershell -NoProfile -ExecutionPolicy Bypass -File $readpos }
    if ("$p" -like 'fail guard*') { $obs['stopped'] = 'input guard'; Save-Obs; exit 2 }
    $v = "$p".Trim().Split(' ', [StringSplitOptions]::RemoveEmptyEntries)
    if ($v.Count -eq 3 -and $v[0] -ne $v[2]) { return "$p".Trim() }
  }
  return $null
}
function Shot($name) { $f = Join-Path $Out $name; powershell -NoProfile -ExecutionPolicy Bypass -File $shot -Out $f | Out-Null; if (Test-Path $f) { return $name } else { return $null } }
$pos3 = '^\s*-?\d+(\.\d+)?\s+-?\d+(\.\d+)?\s+-?\d+(\.\d+)?\s*$'   # "x y z" as readpos prints it ("fail console 3" is not)
function Read-Settled([int]$tries = 5, [int]$gapMs = 3000) {
  # the arrival, read until two reads 3 s apart agree within 0.3 m: exp1d (2026-10-11) read it mid-fall (z -500)
  $prev = Read-Pos; $reads = @("$prev")
  for ($n = 1; $n -lt $tries; $n++) {
    Start-Sleep -Milliseconds $gapMs
    $cur = Read-Pos; $reads += "$cur"
    if ("$prev" -match $pos3 -and "$cur" -match $pos3) {
      $a = "$prev".Trim().Split(' ', [StringSplitOptions]::RemoveEmptyEntries)
      $b = "$cur".Trim().Split(' ', [StringSplitOptions]::RemoveEmptyEntries)
      $still = $true
      for ($k = 0; $k -lt 3; $k++) { if ([Math]::Abs([double]$a[$k] - [double]$b[$k]) -ge 0.3) { $still = $false } }
      if ($still) { return @{ read = "$cur"; settled = $true; reads = $reads } }
    }
    $prev = $cur
  }
  return @{ read = $prev; settled = $false; reads = $reads }
}
function Hud-Shown([string]$name = 'hud.png') {
  # the plain HUD on screen (hud_visible.py): $false during a fade, a loading screen, the console or a menu
  $f = Join-Path $Out $name
  powershell -NoProfile -ExecutionPolicy Bypass -File $shot -Out $f | Out-Null
  return ((& $env:FO4SF_PYTHON (Join-Path $here 'hud_visible.py') $f) -eq 'yes')
}
function Wait-Hud([int]$maxSec, [string]$name = 'hud.png') {
  # after a load started: poll every 2 s until the HUD is back; @{ up; secs }
  $t0 = Get-Date
  do { Start-Sleep 2; $up = Hud-Shown $name } until ($up -or ((Get-Date) - $t0).TotalSeconds -gt $maxSec)
  return @{ up = $up; secs = [int]((Get-Date) - $t0).TotalSeconds }
}
function F($x) { ([double]$x).ToString('0.###', $inv) }
function Teleport($pos, $heading, $pitch = 10, [string]$first = '') {
  # $first: a light command Apply-Light found working (from its validated table), typed in the same console session
  Console-Open
  $pre = ''; if ($first) { $pre = "type:$first|key:enter|wait:400|" }
  Send ($pre + "type:player.setpos x $(F $pos[0])|key:enter|wait:350|type:player.setpos y $(F $pos[1])|key:enter|wait:350|" +
        "type:player.setpos z $(F $pos[2])|key:enter|wait:350|type:player.setangle z $(F $heading)|key:enter|wait:350|" +
        "type:player.setangle x $pitch|key:enter|wait:400|key:grave|wait:1800")
}

# Time of day and weather (terrain and npc_nav; docs/ai/test-queue.md "Time of day and weather", sky_light.py). Every
# line comes from the table below (the same as sky_light.py TIME_METHODS) and is validated before anything is typed.
$skyPy = Join-Path $here 'sky_light.py'
function Light-Commands {
  # this test's light commands in typing order (weather first, then the time ladder); exit 4 on a bad value
  $cmds = @()
  if ($t.weather) {
    if ("$($t.weather)" -notmatch '^[0-9A-Fa-f]{8}$') { "bad weather"; exit 4 }
    $c = "fw $($t.weather)"; if ($t.weather_lock) { $c += ' 1' }
    $cmds += [ordered]@{ method = 'weather'; cmd = $c }
  }
  if ($null -ne $t.time_of_day) {
    if ($t.time_of_day -is [bool]) { "bad time_of_day"; exit 4 }
    $hv = [Math]::Round([double]$t.time_of_day, 2)
    if ([double]::IsNaN($hv) -or $hv -lt 0 -or $hv -ge 24) { "bad time_of_day"; exit 4 }
    $h = $hv.ToString('0.##', $inv)
    $table = @{ 'slt' = "SetLocalTime $h"; 'slt_galaxy' = "SetLocalTime $h 1"; 'cgf' = "cgf `"Game.SetLocalTime`" $h" }
    $ladder = @($t.time_methods | Where-Object { $_ })
    if ($ladder.Count -eq 0) { $ladder = @('slt', 'slt_galaxy', 'cgf') }
    foreach ($m in $ladder) {
      if (-not $table.ContainsKey("$m")) { "bad time method"; exit 4 }
      $cmds += [ordered]@{ method = "$m"; cmd = $table["$m"] }
    }
  }
  return ,$cmds
}
# console_pre (after the save has loaded, before the travel) and console_post (after the arrival, before the probes or
# the spawn): only lines that match this whitelist are typed (the same pattern as console_plan.py PATTERN; .NET \z, so a
# trailing newline never passes); a bad line ends the step with exit 4 before anything is typed.
$consoleOk = '^(?:GetINI "[A-Za-z0-9_]{1,64}:[A-Za-z0-9_]{1,64}"|SetINI "[A-Za-z0-9_]{1,64}:[A-Za-z0-9_]{1,64}" -?\d{1,9}(?:\.\d{1,6})?|SetLocalTime (?:1?\d|2[0-3])(?:\.\d{1,2})?(?: 1)?|cgf "Game\.SetLocalTime" (?:1?\d|2[0-3])(?:\.\d{1,2})?|fw [0-9A-Fa-f]{8}(?: 1)?)\z'
function Console-List($list, [string]$what) {
  $out = @()
  foreach ($c in @($list | Where-Object { $null -ne $_ })) {
    if ($c -isnot [string] -or $c -cnotmatch $consoleOk) { "bad $what"; exit 4 }
    $out += $c
  }
  if ($out.Count -gt 12) { "bad $what"; exit 4 }
  return ,$out
}
function Read-Console([string]$name) {
  # the open console's text: capture its region ($name.png in $Out), prepare and OCR it (as the god mode reply)
  $cap = Join-Path $Out "$name.png"; $prep = Join-Path $Out "${name}_prep.png"
  powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $here 'shot_region.ps1') -Out $cap | Out-Null
  & $env:FO4SF_PYTHON (Join-Path $here 'ocr_prep.py') $cap $prep 135 12 | Out-Null
  $txt = ((powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $here 'ocr.ps1') -Image $prep -Scale 1) -join "`n")
  return @{ ocr = $txt; shot = $(if (Test-Path $cap) { "$name.png" } else { $null }) }
}
function Run-Console($cmds, [string]$phase) {
  # one console session per command: type it, capture the console, OCR, close. The OCR text and the capture
  # (console_<k>.png) go to obs.json "console"; testqueue.py reads the reply (console_plan.reply)
  if ($cmds.Count -eq 0) { return }
  if (-not $obs.Contains('console')) { $obs['console'] = @() }
  $k = @($obs['console']).Count
  foreach ($c in $cmds) {
    $k++
    Console-Open
    Send "type:$c|key:enter|wait:900"
    $r = Read-Console "console_$k"
    Send 'key:grave|wait:800'
    $obs['console'] += [ordered]@{ phase = $phase; cmd = $c; ocr = $r.ocr; shot = $r.shot }
    Save-Obs
  }
}
function Sky-Measure([string]$name, $before, [string]$hour) {
  # sky brightness of a screenshot in $Out (sky_light.py measure: mean of its top 200 rows), $null when not read
  $f = Join-Path $Out $name
  if (-not $name -or -not (Test-Path $f)) { return $null }
  $a = @('measure', $f)
  if ($null -ne $before) { $a += @('--before', ([double]$before).ToString('0.###', $inv)) }
  if ($hour) { $a += @('--hour', $hour) }
  $j = & $env:FO4SF_PYTHON $skyPy @a
  try { return ("$j" | ConvertFrom-Json) } catch { return $null }
}
$script:repin = ''                                    # the time command that worked, typed again before every probe
function Apply-Light($cmds, [string]$beforeShot) {
  # After the arrival, before the step's other screenshots. The arrival's own screenshot is the "before" sky. Each
  # command in its own console session: typed, the console's reply captured and OCR'd ("SetLocalTime only works on a
  # planet." tells a refused command from one without a visible effect), closed; then light_wait_ms with the console
  # closed, a screenshot (sky_<k>.png) and its sky. A time command whose shot does not read as the requested hour gets a
  # second shot after another light_wait_ms (sky_<k>_late.png), so a slow change is credited to the command that made
  # it and not to the next one. The ladder stops at the first command after which the sky reads as the requested hour
  # (sky_light.done); terrain types that command again before every probe (time_repin, default on). Everything goes to
  # obs.json "light"; the judge (sky_light.verdict) decides the run's light, with the probe shots when there are some.
  if ($cmds.Count -eq 0) { return }
  $hour = ''; if ($null -ne $t.time_of_day) { $hour = ([Math]::Round([double]$t.time_of_day, 2)).ToString('0.##', $inv) }
  $wait = 4000; if ($null -ne $t.light_wait_ms) { $wait = [int]$t.light_wait_ms }
  $b = Sky-Measure $beforeShot $null ''
  $bs = $null; if ($b) { $bs = $b.sky }
  $L = [ordered]@{ time_of_day = $t.time_of_day; weather = $t.weather; before = [ordered]@{ shot = $beforeShot; sky = $bs }
                   tries = @() }
  $obs['light'] = $L; Save-Obs
  $k = 0
  foreach ($c in $cmds) {
    $k++
    Console-Open
    Send "type:$($c.cmd)|key:enter|wait:900"
    $r = Read-Console "sky_${k}_console"
    Send "key:grave|wait:$wait"
    $name = Shot "sky_$k.png"
    $h = $(if ($c.method -eq 'weather') { '' } else { $hour })
    $m = Sky-Measure $name $bs $h
    $try = [ordered]@{ method = $c.method; cmd = $c.cmd; ocr = $r.ocr; console = $r.shot; shot = $name
                       sky = $(if ($m) { $m.sky } else { $null }); class = $(if ($m) { $m.class } else { 'unread' })
                       done = [bool]($m -and $m.done) }
    if ($c.method -ne 'weather' -and -not $try.done) {
      Start-Sleep -Milliseconds $wait
      $late = Shot "sky_${k}_late.png"
      $m2 = Sky-Measure $late $bs $h
      $try['shot_late'] = $late; $try['sky_late'] = $(if ($m2) { $m2.sky } else { $null })
      $try['done'] = [bool]($m2 -and $m2.done)
    }
    $L['tries'] += $try
    $obs['light'] = $L; Save-Obs
    if ($c.method -ne 'weather' -and $try.done) {
      if ($t.kind -eq 'terrain' -and $t.time_repin -ne $false) { $script:repin = $c.cmd; $L['repin'] = $c.cmd; Save-Obs }
      break
    }
  }
}

$kind = $t.kind
if ($kind -in 'stairs', 'door') { $kind = 'route' }     # testqueue.py plans stairs and door tests; both are routes
switch ($kind) {
  'route' {
    # stairs or door: route_run.ps1 does the walk (door reset incl. the twin leaf, prompt search, OPEN check)
    $rr = Join-Path $here 'route_run.ps1'
    $out1 = powershell -NoProfile -ExecutionPolicy Bypass -File $rr -Routes $t.routes_file -Out $Out -Only "$($t.route_index)" -PluginIndex $PluginIndex
    $obs['runner'] = ($out1 | Out-String).Trim()
    $res = Join-Path $Out 'results.jsonl'
    if (Test-Path $res) { $obs['result'] = (Get-Content $res | Select-Object -Last 1 | ConvertFrom-Json) }
    if ("$($obs['runner'])" -match 'guard stopped') { $obs['stopped'] = 'input guard'; Save-Obs; exit 2 }
    $obs['shots'] = @(Get-ChildItem $Out -Filter 'r*.png' | ForEach-Object { $_.Name })
  }
  'fall' {
    # drop from 1.5 m above a floor point (god mode is on for the session): landed, fell through, held above
    $p = $t.point
    Teleport @($p[0], $p[1], ([double]$p[2] + 1.5)) $t.heading 10
    Start-Sleep -Milliseconds 1500
    $obs['end_read'] = Read-Pos
    $obs['shot'] = Shot 'fall.png'
  }
  'movable' {
    $obs['item_before'] = Read-Pos $t.sf_ref
    Teleport $t.stand $t.heading 25
    $obs['player_start'] = Read-Pos
    $obs['shot_before'] = Shot 'before.png'
    Send "hold:w,$($t.walk_ms)|wait:1500"
    $obs['player_end'] = Read-Pos
    $obs['item_after'] = Read-Pos $t.sf_ref
    $obs['shot_after'] = Shot 'after.png'
  }
  'travel' {
    Teleport $t.start $t.heading 10
    $obs['start_read'] = Read-Pos
    $pre = Join-Path $Out 'pre.png'
    $obs['prompt'] = $false
    for ($k = 0; $k -lt 6; $k++) {                     # tilt down until the activation prompt shows (as route_run.ps1)
      powershell -NoProfile -ExecutionPolicy Bypass -File $shot -Out $pre | Out-Null
      if ((& $env:FO4SF_PYTHON (Join-Path $here 'prompt_visible.py') $pre) -eq 'yes') { $obs['prompt'] = $true; break }
      Send 'move:0,150|wait:450'
    }
    if ($obs['prompt']) {
      Send 'key:e|wait:3000'
      $hud = Join-Path $Out 'hud.png'; $t0 = Get-Date
      do {                                            # load screen, then the HUD again in the destination cell
        Start-Sleep 2
        powershell -NoProfile -ExecutionPolicy Bypass -File $shot -Out $hud | Out-Null
        $up = (& $env:FO4SF_PYTHON (Join-Path $here 'hud_visible.py') $hud) -eq 'yes'
      } until ($up -or ((Get-Date) - $t0).TotalSeconds -gt 60)
      $obs['load_s'] = [int]((Get-Date) - $t0).TotalSeconds
      $obs['hud_back'] = $up
    }
    $obs['end_read'] = Read-Pos
    $obs['shot'] = Shot 'arrival.png'
  }
  'godmode' {
    # tgm toggles: read the reply ("God Mode ON/OFF") and toggle again when it reports OFF
    Console-Open
    Send 'type:tgm|key:enter|wait:700'
    $cap = Join-Path $Out 'tgm.png'; $prep = Join-Path $Out 'tgm_prep.png'
    powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $here 'shot_region.ps1') -Out $cap | Out-Null
    & $env:FO4SF_PYTHON (Join-Path $here 'ocr_prep.py') $cap $prep 135 12
    $txt = ((powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $here 'ocr.ps1') -Image $prep -Scale 1) -join ' ')
    $obs['reply'] = $txt
    # Starfield replies "God Mode enabled." / "God Mode disabled." (2026-10-11); the last match is this command's reply
    $last = [regex]::Matches($txt, 'Mode\s*(enabled|disabled|ON|OFF)', 'IgnoreCase') | Select-Object -Last 1
    $state = if ($last) { $last.Groups[1].Value.ToLower() } else { '' }
    if ($state -in 'disabled', 'off') { Send 'type:tgm|key:enter|wait:700'; $obs['toggled_again'] = $true }
    Send 'key:grave|wait:900'
    $obs['god'] = if ($state -in 'enabled', 'on') { 'on' } elseif ($state -in 'disabled', 'off') { 'on (second toggle)' } else { 'unknown' }
  }
  'companion_off' {
    # The test save's companion (Vasco, Starfield.esm ACHR 000057BE VascoREF) follows the player: it stood in front of a
    # load door (FortHagen01 0CD469 NOPROMPT, 2026-10-12) and in every NPC sample shot. Disabled for this session only
    # (the runner's own save; nothing is saved here). GetDisabled >> 1 confirms it.
    if ("$($t.ref)" -notmatch '^[0-9A-Fa-f]{8}$') { "bad ref"; exit 4 }
    Console-Open
    Send "type:prid $($t.ref)|key:enter|wait:500|type:disable|key:enter|wait:500|type:GetDisabled|key:enter|wait:700"
    $cap = Join-Path $Out 'companion.png'; $prep = Join-Path $Out 'companion_prep.png'
    powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $here 'shot_region.ps1') -Out $cap | Out-Null
    & $env:FO4SF_PYTHON (Join-Path $here 'ocr_prep.py') $cap $prep 135 12
    $txt = ((powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $here 'ocr.ps1') -Image $prep -Scale 1) -join ' ')
    Send 'key:grave|wait:900'
    $obs['reply'] = $txt
    $last = [regex]::Matches($txt, 'GetDisabled\s*>+\s*([01])', 'IgnoreCase') | Select-Object -Last 1
    $obs['companion'] = if ($last -and $last.Groups[1].Value -eq '1') { 'disabled' } else { 'unknown' }
  }
  'save' {
    if ($t.name -notmatch '^[A-Za-z0-9_]+$') { "bad save name"; exit 4 }
    Console-Open
    Send "type:save $($t.name)|key:enter|wait:4000|key:grave|wait:1200"
    $obs['shot'] = Shot 'saved.png'
  }
  'load' {
    if ($t.name -notmatch '^[A-Za-z0-9_]+$') { "bad save name"; exit 4 }
    Console-Open
    Send "type:load $($t.name)|key:enter|wait:3000"
    $hud = Join-Path $Out 'hud.png'; $t0 = Get-Date
    do { Start-Sleep 3; powershell -NoProfile -ExecutionPolicy Bypass -File $shot -Out $hud | Out-Null
         $up = (& $env:FO4SF_PYTHON (Join-Path $here 'hud_visible.py') $hud) -eq 'yes' } until ($up -or ((Get-Date) - $t0).TotalSeconds -gt 120)
    $obs['hud_back'] = $up; $obs['load_s'] = [int]((Get-Date) - $t0).TotalSeconds
    $obs['end_read'] = Read-Pos
  }
  'terrain' {
    # terrain experiment: coc into a test worldspace, then drop onto points of known terrain height and read z
    if ($t.world_coc -notmatch '^[A-Za-z0-9_]+$') { "bad world name"; exit 4 }
    # travel: "cow <world> x y" reaches a vanilla worldspace without a COC cell (control runs); default coc <world_coc>
    $go = "coc $($t.world_coc)"
    if ($t.travel) { if ($t.travel -notmatch '^((coc|cow) [A-Za-z0-9_]+( -?\d+ -?\d+)?|player\.moveto [0-9A-Fa-f]{8})$') { "bad travel"; exit 4 }; $go = $t.travel }
    $lightCmds = Light-Commands
    $preCmds = Console-List $t.console_pre 'console_pre'; $postCmds = Console-List $t.console_post 'console_post'
    Run-Console $preCmds 'pre'                       # after the save has loaded, before the travel
    Console-Open
    Send "type:$go|key:enter|wait:400|key:grave|wait:3000"
    $hud = Join-Path $Out 'hud.png'; $t0 = Get-Date
    do { Start-Sleep 2; powershell -NoProfile -ExecutionPolicy Bypass -File $shot -Out $hud | Out-Null
         $up = (& $env:FO4SF_PYTHON (Join-Path $here 'hud_visible.py') $hud) -eq 'yes' } until ($up -or ((Get-Date) - $t0).TotalSeconds -gt 90)
    $obs['load_s'] = [int]((Get-Date) - $t0).TotalSeconds
    Start-Sleep 3
    $obs['spawn_read'] = Read-Pos
    $obs['shot'] = Shot 'spawn.png'
    Save-Obs
    Apply-Light $lightCmds "$($obs['shot'])"         # time of day / weather before the probes' screenshots
    Run-Console $postCmds 'post'                     # after the arrival, before the probes
    $pts = @()
    $k = 0
    # Points are in the worldspace's own frame. An activated overlay is merged into the planet worldspace at a whole-cell
    # offset plus a Z offset (Mars runs 2026-10-11: COC marker (50, 50) arrived at (3050, -3450)). The offset comes from
    # anchor (a persistent ref: {ref, local [x,y,z]}, read with prid + getpos) or else from spawn_local (where the
    # player stands after coc, [x,y] or [x,y,z]); with a z component the expected heights shift by the same Z offset.
    $ox = 0.0; $oy = 0.0; $oz = 0.0
    if ($t.anchor) {
      if ("$($t.anchor.ref)" -notmatch '^[0-9A-Fa-f]{8}$') { "bad anchor"; exit 4 }
      $ar = Read-Pos "$($t.anchor.ref)"
      $obs['anchor_read'] = $ar
      $av = "$ar".Trim().Split(' ', [StringSplitOptions]::RemoveEmptyEntries)
      if ("$ar" -match '^\s*-?\d+(\.\d+)?\s+-?\d+(\.\d+)?\s+-?\d+(\.\d+)?\s*$') {               # "fail console 3" also has three words
        $ox = [double]$av[0] - [double]$t.anchor.local[0]; $oy = [double]$av[1] - [double]$t.anchor.local[1]
        $oz = [double]$av[2] - [double]$t.anchor.local[2]; $obs['offset'] = @($ox, $oy, $oz); $obs['offset_from'] = 'anchor'
        # our own persistent marker read back its unmerged local position (exp1d 2026-10-11: 50 50 10 while the
        # overlay sat at +3000 -3500): an all-zero offset says nothing, use the spawn instead
        if ([Math]::Abs($ox) -lt 0.01 -and [Math]::Abs($oy) -lt 0.01 -and $t.spawn_local) {
          $ox = 0.0; $oy = 0.0; $oz = 0.0; $obs.Remove('offset'); $obs['anchor_unmerged'] = $true
        }
      }
    }
    if (-not $obs['offset'] -and $t.spawn_local -and $obs['spawn_read']) {
      $sv = "$($obs['spawn_read'])".Trim().Split(' ', [StringSplitOptions]::RemoveEmptyEntries)
      if ("$($obs['spawn_read'])" -match '^\s*-?\d+(\.\d+)?\s+-?\d+(\.\d+)?\s+-?\d+(\.\d+)?\s*$') {
        $ox = [double]$sv[0] - [double]$t.spawn_local[0]; $oy = [double]$sv[1] - [double]$t.spawn_local[1]
        if ($t.spawn_local.Count -ge 3) { $oz = [double]$sv[2] - [double]$t.spawn_local[2] }
        $obs['offset'] = @($ox, $oy, $oz); $obs['offset_from'] = 'spawn'
      }
    }
    Save-Obs
    # drop_above_spawn: drop height relative to the arrival (terrain height unknown in a relocated world);
    # settle_ms: wait before reading (a 60 m fall at Mars gravity takes about 6 s)
    $dropz = [double]$t.drop_z + $oz                # drop_z is in the worldspace's own frame
    if ($t.drop_above_spawn -and $obs['spawn_read']) {
      $sv = "$($obs['spawn_read'])".Trim().Split(' ', [StringSplitOptions]::RemoveEmptyEntries)
      if ("$($obs['spawn_read'])" -match '^\s*-?\d+(\.\d+)?\s+-?\d+(\.\d+)?\s+-?\d+(\.\d+)?\s*$') { $dropz = [double]$sv[2] + [double]$t.drop_above_spawn }
    }
    $settle = if ($t.settle_ms) { [int]$t.settle_ms } else { 4500 }
    # hop_m: reach a far point in hops of at most hop_m metres (each hop waits hop_wait_ms), so terrain streams in
    # behind the player as it would while travelling (core64 2026-10-11: single 1-2 km jumps hung at the drop height)
    $hx = [double]$ox + [double]$t.points[0].x; $hy = [double]$oy + [double]$t.points[0].y
    foreach ($p in $t.points) {
      $tx = [double]$p.x + $ox; $ty = [double]$p.y + $oy
      if ($t.hop_m) {
        $dist = [Math]::Sqrt(($tx - $hx) * ($tx - $hx) + ($ty - $hy) * ($ty - $hy))
        $n = [Math]::Ceiling($dist / [double]$t.hop_m)
        for ($h = 1; $h -lt $n; $h++) {
          Teleport @(($hx + ($tx - $hx) * $h / $n), ($hy + ($ty - $hy) * $h / $n), $dropz) 0 15
          Start-Sleep -Milliseconds $(if ($t.hop_wait_ms) { [int]$t.hop_wait_ms } else { 6000 })
        }
        $obs['hops'] = 1 + [int]$obs['hops'] + [Math]::Max(0, $n - 1)
      }
      $hx = $tx; $hy = $ty
      Teleport @($tx, $ty, $dropz) 0 15 $script:repin    # with the time command that worked: noon at every probe
      Start-Sleep -Milliseconds $settle               # a fall from 80 m takes about 4 s on Earth gravity
      $rd = Read-Pos
      # still hanging at the drop height: the cells around a far point were not loaded yet (exp3 2026-10-11 read 170.00
      # at points ~700 m from the arrival); wait and read again, twice at most
      for ($w = 0; $w -lt 2 -and "$rd" -match '^\s*\S+\s+\S+\s+(-?\d+(\.\d+)?)\s*$' -and [Math]::Abs([double]$Matches[1] - $dropz) -lt 0.05; $w++) {
        Start-Sleep -Milliseconds 8000; $rd = Read-Pos
      }
      $pt = [ordered]@{ label = $p.label; read = $rd; shot = (Shot "pt$k.png") }
      if ($script:repin) { $pt['repin'] = $true }
      if ($lightCmds.Count -gt 0 -and $pt.shot) {          # the probe shot's light: its corners decide the run's light
        $pm = Sky-Measure $pt.shot $null ''
        if ($pm) { $pt['sky'] = $pm.sky; $pt['corners'] = $pm.corners }
      }
      $pts += $pt
      $obs['points'] = $pts; Save-Obs                 # after every point: a cut-off keeps the heights already read
      $k++
    }
    $obs['points'] = $pts
    # beyond the BTD's edge: void, flat default, water or the host planet? recorded, not judged
    Teleport @($t.beyond.x, $t.beyond.y, $t.drop_z) 90 5
    Start-Sleep -Milliseconds 4500
    $obs['beyond_read'] = Read-Pos
    $obs['beyond_shot'] = Shot 'beyond.png'
  }
  'npc_nav' {
    # NPC navigation (PR #61 docs/actors/npc-navigation.md 3.4, docs/ai/test-queue.md): travel, spawn a vanilla actor at
    # A, order it to walk to the player standing at B, sample where it is, remove it. The actor's handle is the runtime
    # id PickLastRef names after the spawn (FFxxxxxx, checked: GetSelf names no other ref, GetIsID <npc> 1, at the
    # player's feet). Commands that act on the console selection (the walk command, disable, markfordelete) are typed
    # only in a console session that selected that id with prid and in which GetIsID read 1. Everything typed is
    # validated here again.
    $hex8 = '^[0-9A-Fa-f]{8}$'
    $ffid = '^FF[0-9A-F]{6}$'                         # a runtime ref id as parse_npc.py prints it (upper case)
    $num3 = '^\s*-?\d+(\.\d+)?\s+-?\d+(\.\d+)?\s+-?\d+(\.\d+)?\s*$'   # "fail console 3" is not a position
    # the same table as testqueue.py NPC_METHODS: nothing else is ever typed for a method ('none': the baseline)
    $methods = @{ 'none' = @(); 'ptr_player' = @('PathToRef player'); 'cf_pathto_player' = @('cf "Actor.PathToReference" player 1.0')
                  'follow_player' = @('SetPlayerTeammate 1', 'EvaluatePackage'); 'combat_player' = @('StartCombat player') }
    if ("$($t.travel)" -notmatch '^coc [A-Za-z0-9_]+$') { "bad travel"; exit 4 }
    $npc = "$($t.npc)"
    if ($npc -notmatch $hex8) { "bad npc"; exit 4 }
    if (-not $methods.ContainsKey("$($t.method)")) { "bad method"; exit 4 }
    $pre = @($t.pre | Where-Object { $_ })
    foreach ($c in $pre) { if (@('gnm') -cnotcontains "$c") { "bad pre"; exit 4 } }
    if ($t.anchor -and "$($t.anchor.ref)" -notmatch $hex8) { "bad anchor"; exit 4 }
    $spawnWait = 2000; if ($null -ne $t.spawn_wait_ms) { $spawnWait = [int]$t.spawn_wait_ms }
    $handleTol = 2.0; if ($null -ne $t.handle_tol) { $handleTol = [double]$t.handle_tol }
    if ($spawnWait -lt 0 -or $spawnWait -gt 30000 -or $handleTol -lt 0.5 -or $handleTol -gt 10) { "bad spawn_wait_ms / handle_tol"; exit 4 }
    $lightCmds = Light-Commands
    $preCmds = Console-List $t.console_pre 'console_pre'; $postCmds = Console-List $t.console_post 'console_post'
    $parse = Join-Path $here 'parse_npc.py'
    # step budget (testqueue.py step_timeout minus a margin): samples stop early so that the removal always has
    # $reserve seconds left before the runner would kill the step and leave the actor behind
    $stepStart = Get-Date
    $budget = if ($t.budget_s) { [double]$t.budget_s } else { 1e9 }
    $reserve = 300.0
    function Left-S { $budget - ((Get-Date) - $stepStart).TotalSeconds }
    function Npc-Capture([string[]]$cmds, [string[]]$need, [string]$tag = 'npc') {
      # console open: ClearConsole first (it does NOT clear what the console shows, N0_base 2026-10-11, but its echo marks
      # where this session begins), the commands, then OCR of this session's replies (parse_npc.py, told what the
      # commands produce in typing order, reads only what follows the session start, in both OCR layouts). The capture
      # and the OCR text are kept as <tag>_cap.png / <tag>_ocr.txt (the samples share 'npc', the last one stays).
      $seq = 'type:ClearConsole|key:enter|wait:500'
      foreach ($c in $cmds) { $seq += "|type:$c|key:enter|wait:600" }
      Send "$seq|wait:400"
      $exp = @(); $typed = @()
      foreach ($c in $cmds) {
        if ($c -eq 'plr') { $exp += 'ref' }
        elseif ($c -like 'GetIsID *') { $exp += 'isid' } elseif ($c -match '^getpos ([xyz])$') { $exp += $Matches[1] }
        elseif ($c -eq 'GetSelf') { $exp += 'self' } elseif ($c -eq 'GetDisabled') { $exp += 'disabled' }
        elseif ($c -match '^prid ([0-9A-Fa-f]{8})$') { $typed += $Matches[1] }
      }
      $cap = Join-Path $Out "${tag}_cap.png"; $prep = Join-Path $Out "${tag}_prep.png"; $txt = Join-Path $Out "${tag}_ocr.txt"
      powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $here 'shot_region.ps1') -Out $cap | Out-Null
      $r = $null
      foreach ($th in 135, 140, 130, 145) {
        & $env:FO4SF_PYTHON (Join-Path $here 'ocr_prep.py') $cap $prep $th 12 | Out-Null
        (powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $here 'ocr.ps1') -Image $prep -Scale 1) | Set-Content $txt -Encoding utf8
        $r = (& $env:FO4SF_PYTHON $parse $txt "--expect=$($exp -join ',')" "--typed=$($typed -join ',')") | ConvertFrom-Json
        $missing = @($need | Where-Object { $null -eq $r.$_ })
        if ($r -and $missing.Count -eq 0) { break }
      }
      return $r
    }
    $script:npcRef = $null                            # FFxxxxxx: PickLastRef's id, set once the spawn is confirmed
    function Dist-XY([string]$read, [double]$x, [double]$y) {
      if ("$read" -notmatch $num3) { return $null }
      $v = "$read".Trim().Split(' ', [StringSplitOptions]::RemoveEmptyEntries)
      return [Math]::Sqrt([Math]::Pow([double]$v[0] - $x, 2) + [Math]::Pow([double]$v[1] - $y, 2))
    }
    function Pick-Npc([string]$tag) {
      # Console open. Reads the last created ref: PickLastRef's id (its own session, plr alone), then prid <that id> and
      # GetSelf (the console's selection: N0_base's GetSelf named the floor static 0024A824 while PickLastRef named
      # FF010D65), then GetIsID <npc> and its position (the selection stays on the prid'ed ref while the console is
      # open). Returns everything read; the caller decides. Nothing that acts on the selection is typed here.
      $p = [ordered]@{ 'ref' = $null; self = $null; isid = $null; read = $null; how = ''; plr_ocr = $null; self_ocr = $null; ocr = $null }
      $r1 = Npc-Capture @('plr') @('ref') "${tag}_plr"
      $p['plr_ocr'] = $r1.ocr
      if ("$($r1.ref)" -cnotmatch $ffid) { return $p }
      $p['ref'] = "$($r1.ref)"
      $r2 = Npc-Capture @("prid $($p['ref'])", 'GetSelf') @('self') "${tag}_self"
      if ("$($r2.self)" -match $hex8) { $p['self'] = "$($r2.self)" }
      $p['self_ocr'] = $r2.ocr
      $r3 = Npc-Capture @("GetIsID $npc", 'getpos x', 'getpos y', 'getpos z') @('isid', 'pos') "${tag}_isid"
      $p['isid'] = $r3.isid; $p['how'] = $r3.how; $p['ocr'] = $r3.ocr
      if ("$($r3.pos)" -match $num3) { $p['read'] = "$($r3.pos)" }
      return $p
    }
    function Select-Npc {
      # Opening the console selects what is under the crosshair (supported hypothesis: N0_base's selection was the floor
      # static 0024A824 at A and again at B), so every session selects the actor by its id (prid, the confirmed
      # PickLastRef id) and confirms it: GetIsID <npc> 1 in the same session. Returns with the console OPEN plus its
      # position, or closes the console and returns $null. A second try only repeats the session (an OCR miss).
      if ("$($script:npcRef)" -cnotmatch $ffid) { return $null }
      Console-Open
      foreach ($n in 1, 2) {
        $r = Npc-Capture @("prid $($script:npcRef)", "GetIsID $npc", 'getpos x', 'getpos y', 'getpos z') @('isid', 'pos')
        if ($r -and $r.isid -eq 1) {
          $p = $null; if ("$($r.pos)" -match $num3) { $p = "$($r.pos)" }
          return [ordered]@{ via = 'prid'; isid = 1; read = $p; how = $r.how; ocr = $r.ocr }
        }
      }
      Send 'key:grave|wait:600'
      return $null
    }
    # 1. travel (coc <cell editor id>: the console travel that works), wait for the HUD, read the arrival until it stops
    Run-Console $preCmds 'pre'                       # after the save has loaded, before the travel
    Console-Open
    Send "type:$($t.travel)|key:enter|wait:400|key:grave|wait:3000"
    $hud = Join-Path $Out 'hud.png'; $t0 = Get-Date
    do { Start-Sleep 2; powershell -NoProfile -ExecutionPolicy Bypass -File $shot -Out $hud | Out-Null
         $up = (& $env:FO4SF_PYTHON (Join-Path $here 'hud_visible.py') $hud) -eq 'yes' } until ($up -or ((Get-Date) - $t0).TotalSeconds -gt 90)
    $obs['load_s'] = [int]((Get-Date) - $t0).TotalSeconds; $obs['hud_back'] = $up
    Start-Sleep 3
    $arr = Read-Settled
    $obs['spawn_read'] = $arr.read; $obs['spawn_settled'] = $arr.settled; $obs['spawn_reads'] = $arr.reads
    $obs['shot'] = Shot 'arrival.png'
    Apply-Light $lightCmds "$($obs['shot'])"         # time of day / weather before the spawn and the samples' shots
    Run-Console $postCmds 'post'                     # after the arrival, before the offset and the spawn
    # 2. frame offset, as the terrain kind: A and B are in the worldspace's own frame; an activated overlay is merged into
    # the planet worldspace at an offset, read from a persistent anchor ref (prid + getpos) or from the arrival point
    $ox = 0.0; $oy = 0.0; $oz = 0.0
    if ($t.anchor) {
      $ar = Read-Pos "$($t.anchor.ref)"
      $obs['anchor_read'] = $ar
      if ("$ar" -match $num3) {
        $av = "$ar".Trim().Split(' ', [StringSplitOptions]::RemoveEmptyEntries)
        $ox = [double]$av[0] - [double]$t.anchor.local[0]; $oy = [double]$av[1] - [double]$t.anchor.local[1]
        $oz = [double]$av[2] - [double]$t.anchor.local[2]; $obs['offset'] = @($ox, $oy, $oz); $obs['offset_from'] = 'anchor'
        # our own persistent marker reads back its unmerged local position (exp1d: 50 50 10; exp2b: -989.03 1147.20
        # 105.14, 2026-10-11) while the overlay sits elsewhere: an all-zero offset says nothing, use the arrival
        if ([Math]::Abs($ox) -lt 0.01 -and [Math]::Abs($oy) -lt 0.01 -and $t.spawn_local) {
          $ox = 0.0; $oy = 0.0; $oz = 0.0; $obs.Remove('offset'); $obs.Remove('offset_from'); $obs['anchor_unmerged'] = $true
        }
      }
    }
    if (-not $obs['offset'] -and $t.spawn_local -and ("$($obs['spawn_read'])" -match $num3)) {
      if ($arr.settled) {
        $sv = "$($obs['spawn_read'])".Trim().Split(' ', [StringSplitOptions]::RemoveEmptyEntries)
        $ox = [double]$sv[0] - [double]$t.spawn_local[0]; $oy = [double]$sv[1] - [double]$t.spawn_local[1]
        if ($t.spawn_local.Count -ge 3) { $oz = [double]$sv[2] - [double]$t.spawn_local[2] }
        $obs['offset'] = @($ox, $oy, $oz); $obs['offset_from'] = 'spawn'
      } else { $obs['offset_missing'] = 'the arrival was still moving (falling?) after 5 reads: no offset from it' }
    }
    if (($t.anchor -or $t.spawn_local) -and -not $obs['offset']) {
      if (-not $obs['offset_missing']) { $obs['offset_missing'] = 'neither the anchor nor the arrival gave an offset' }
      Save-Obs; exit 0                                # nothing spawned
    }
    Save-Obs
    $ax = [double]$t.a[0] + $ox; $ay = [double]$t.a[1] + $oy; $az = [double]$t.a[2] + $oz
    $bx = [double]$t.b[0] + $ox; $by = [double]$t.b[1] + $oy; $bz = [double]$t.b[2] + $oz
    $settle = [int]$t.settle_ms
    # 3. the player to A (dropped from $t.drop m: god mode is on), optional probes (gnm), then the actor at the player's
    # feet. N0_base (2026-10-11) typed placeatme, plr, GetIsID and GetSelf in one console session: PickLastRef named
    # FF010D65, but GetIsID read 0.00 and GetSelf (0024a824), the floor static the console had selected (its label read
    # "STAT '' (0024A824)" later); three minutes later plr selected the citizen (GetIsID 1.00, 1.3 m from A). So the
    # console is closed after placeatme and the game runs spawn_wait_ms before the handle is read, and the handle is
    # PickLastRef's id, confirmed when: GetSelf after prid <id> names no other ref, GetIsID <npc> reads 1, and the ref
    # stands within handle_tol of the player at A.
    Teleport @($ax, $ay, ($az + [double]$t.drop)) $t.heading_a 10
    Start-Sleep -Milliseconds $settle
    $obs['player_a'] = Read-Pos
    if ($pre.Count -gt 0) {
      Console-Open
      Send ((($pre | ForEach-Object { "type:$_|key:enter|wait:600" }) -join '|') + '|key:grave|wait:600')
      Start-Sleep -Milliseconds ([int]$t.pre_wait_ms)
      $obs['pre'] = ($pre -join '; '); $obs['pre_shot'] = Shot 'pre.png'
    }
    Console-Open
    $s0 = Npc-Capture @("player.placeatme $npc 1") @() 'place'
    Send "key:grave|wait:$spawnWait"                  # console closed: the game runs (the console pauses it)
    Console-Open
    $pk = Pick-Npc 'spawn'
    $hx = $ax; $hy = $ay                              # the player's read at A, else A itself
    if ("$($obs['player_a'])" -match $num3) {
      $pv = "$($obs['player_a'])".Trim().Split(' ', [StringSplitOptions]::RemoveEmptyEntries); $hx = [double]$pv[0]; $hy = [double]$pv[1]
    }
    $dist = Dist-XY $pk['read'] $hx $hy
    $why = @()
    if (-not $pk['ref']) { $why += 'PickLastRef gave no FFxxxxxx id' }
    else {
      if ($pk['self'] -and $pk['self'] -ne $pk['ref']) { $why += "after prid $($pk['ref']) GetSelf named $($pk['self']): another ref is selected" }
      if ($pk['isid'] -ne 1) { $why += "GetIsID $npc read $(if ($null -eq $pk['isid']) { 'nothing' } else { $pk['isid'] })" }
      if ($null -eq $dist) { $why += 'its position was not read' }
      elseif ($dist -gt $handleTol) { $why += "it stands $([math]::Round($dist, 2)) m from the player at A (more than $handleTol m)" }
    }
    $confirmed = ($why.Count -eq 0)
    $spawnRef = $pk['ref']                            # kept for the removal (step 7) even when not confirmed
    $spawnNear = ($null -ne $dist) -and ($dist -le $handleTol)
    $obs['spawn'] = [ordered]@{ 'ref' = $pk['ref']; self = $pk['self']; isid = $pk['isid']; read = $pk['read']
                                dist_a = $(if ($null -ne $dist) { [math]::Round($dist, 2) } else { $null }); confirmed = $confirmed
                                why = ($why -join '; '); how = $pk['how']; place_ocr = $s0.ocr; plr_ocr = $pk['plr_ocr']
                                self_ocr = $pk['self_ocr']; ocr = $pk['ocr'] }
    if ($confirmed) { $script:npcRef = $pk['ref'] }
    Send 'key:grave|wait:600'
    $obs['spawn_shot'] = Shot 'spawn.png'
    Save-Obs
    if ($confirmed) {
      # 4. the player to B, facing A: the walk target
      Teleport @($bx, $by, ($bz + [double]$t.drop)) $t.heading_b 10
      Start-Sleep -Milliseconds $settle
      $pb = Read-Pos
      $obs['player_b'] = $null; if ("$pb" -match $num3) { $obs['player_b'] = "$pb" }
      # 5. the walk command, on the confirmed selection; t = 0 read in the same session ('none': no command, the baseline)
      $sel = Select-Npc
      if ($sel) {
        $obs['t0'] = $sel
        $lines = @($methods["$($t.method)"])
        $cmds = @(); if ($t.path_line) { $cmds += 'tpl' }; $cmds += $lines
        if ($cmds.Count -gt 0) {
          $c = Npc-Capture $cmds @()
          $obs['command_ocr'] = $c.ocr                # the console's reply settles the command syntax (unresolved)
        }
        Send 'key:grave|wait:300'
        $obs['command_sent'] = $true; $obs['command'] = ($lines -join '; ')
        # 6. samples. The console pauses the game (supported hypothesis), so time counts only while it is closed
        # (t_game, about +-2 s); t_wall is the clock time since the command.
        $cmdAt = Get-Date; $closedAt = $cmdAt; $game = 0.0; $samples = @(); $k = 0
        foreach ($s in @($t.reads_s)) {
          if ([double]$s -le 0) { continue }            # t = 0 is the read above
          $game += ((Get-Date) - $closedAt).TotalSeconds
          $wait = [Math]::Max(0.0, [double]$s - $game)
          if ((Left-S) - $wait -lt $reserve) {          # no time left for this read and the removal: stop sampling
            $obs['samples_cut'] = "step budget: $([int](Left-S)) s left at t_game $([math]::Round($game, 1)), $reserve s kept for the removal"
            break
          }
          if ($wait -gt 0) { Start-Sleep -Milliseconds ([int]($wait * 1000)); $game = [double]$s }
          $r = Select-Npc
          if ($r) { Send 'key:grave|wait:300' }
          $closedAt = Get-Date
          $samples += [ordered]@{ t_game = [math]::Round($game, 1); t_wall = [math]::Round(((Get-Date) - $cmdAt).TotalSeconds, 1)
                                  isid = $(if ($r) { 1 } else { $null }); read = $(if ($r) { $r.read } else { $null })
                                  via = $(if ($r) { $r.via } else { '' }); shot = (Shot "npc$k.png") }
          $obs['samples'] = $samples; Save-Obs           # after every read: a cut-off keeps what was read
          $k++
        }
      } else { $obs['command_sent'] = $false }
    }
    # 7. remove the actor so no test leaves an NPC behind: disable + markfordelete, only on a selection the game confirmed
    # in the same console session. First the confirmed handle (Select-Npc: prid <id>, GetIsID 1). Otherwise (no
    # confirmed handle, or it could not be read) PickLastRef again, now that the game has run since the spawn (N0_base:
    # plr found the citizen 3 min after the spawn): the ref it names is removed when GetSelf after prid <id> names no
    # other ref, it stands within 40 m of A or B, and either GetIsID reads 1, or it is the very ref PickLastRef named at
    # the spawn (then within handle_tol of the player) and GetSelf names it (a templated actor whose GetIsID may not
    # match). A selection that stayed on a static (N0_base's spawn session) never gets disable.
    $clean = [ordered]@{ removed = $false }
    $sel = $null
    if ($script:npcRef) { $sel = Select-Npc }
    if (-not $sel) {
      Console-Open
      $pk2 = Pick-Npc 'remove'
      $da = Dist-XY $pk2['read'] $ax $ay; $db = Dist-XY $pk2['read'] $bx $by
      $near = ($null -ne $da) -and ([Math]::Min($da, $db) -lt 40)
      $selfOk = (-not $pk2['self']) -or ($pk2['self'] -eq $pk2['ref'])
      $same = $pk2['ref'] -and ($pk2['ref'] -eq $spawnRef) -and $spawnNear -and ($pk2['self'] -eq $pk2['ref'])
      $ok = $pk2['ref'] -and $selfOk -and $near -and (($pk2['isid'] -eq 1) -or $same)
      $clean['by_plr'] = [ordered]@{ 'ref' = $pk2['ref']; self = $pk2['self']; isid = $pk2['isid']; read = $pk2['read']; near = $near }
      if ($ok) { $sel = [ordered]@{ via = 'plr' } } else { Send 'key:grave|wait:600' }
    }
    if ($sel) {
      $d = Npc-Capture @('disable', 'GetDisabled') @('disabled')
      Send 'type:markfordelete|key:enter|wait:600|key:grave|wait:600'
      $clean['removed'] = $true; $clean['disabled'] = $d.disabled; $clean['via'] = $sel.via
    } else { $clean['note'] = 'no confirmed handle: an actor may be left in the world' }
    if ($t.path_line -and $obs['command_sent']) { Console-Open; Send 'type:tpl|key:enter|wait:500|key:grave|wait:600' }
    $obs['cleanup'] = $clean
    $obs['end_shot'] = Shot 'cleanup.png'
    $obs['step_s'] = [int]((Get-Date) - $stepStart).TotalSeconds
  }
  'door_trip' {
    # The playable slice's working door (docs/slice/redrocket-door.md): coc into the world, read the arrival until it
    # settles (the overlay's merge offset O = arrival - spawn_local), then two legs through a load door: "in" from
    # outside.start + O towards outside.door + O, "out" from inside.start towards inside.door. Each leg: teleport to the
    # start facing the door, read it, then walk at the door in walk_step_ms steps with a HUD check after each (an
    # automatic door loads within fAutoDoorActivateDistance, 3 m in Starfield.esm, behind a fade and a loading screen),
    # E when an activation prompt shows, and as a last try a teleport to the "near" point (1 m in front of the door);
    # after every walk step and before E or the last try the position is read too (Leg-Check): a load whose loading
    # screen fell between two HUD checks is found by the position, and nothing is pressed or teleported unless a read
    # put the player on this side of the door. Then the HUD back, the arrival read until it settles, player.GetInCell
    # <inside.cell> and a screenshot. A leg that does not arrive where expected ends the step (the judge names why).
    # Then save <save> (its file must appear in the Saves folder), a teleport away (back to the coc arrival), load
    # <save> (the player must come back; a loading screen is looked for), the position read until it settles,
    # GetInCell, a screenshot. With outside.ref the door's own getpos is read after the coc arrival (a diagnostic).
    # Everything typed is validated here again.
    $nameRe = '^[A-Za-z0-9_]{1,64}$'
    if ("$($t.travel)" -notmatch '^coc [A-Za-z0-9_]+$') { "bad travel"; exit 4 }
    $cell = "$($t.inside.cell)"
    if ($cell -cnotmatch $nameRe) { "bad inside.cell"; exit 4 }
    $save = "$($t.save)"
    if ($save -cnotmatch $nameRe -or $save -notmatch '^fo4sf_' -or $save -match '^fo4sf_test_') { "bad save"; exit 4 }
    function Vec3($v, [string]$what, [bool]$optional = $false) {
      if ($null -eq $v -and $optional) { return $null }
      $a = @($v)
      if ($a.Count -ne 3) { "bad $what"; exit 4 }
      $out = @()
      foreach ($x in $a) {
        if ($x -isnot [double] -and $x -isnot [int] -and $x -isnot [long] -and $x -isnot [decimal]) { "bad $what"; exit 4 }
        $d = [double]$x; if ([double]::IsNaN($d) -or [double]::IsInfinity($d) -or [Math]::Abs($d) -gt 1e6) { "bad $what"; exit 4 }
        $out += $d
      }
      return ,$out
    }
    function Num($v, [double]$def, [double]$lo, [double]$hi, [string]$what) {
      if ($null -eq $v) { return $def }
      if ($v -is [bool] -or $v -is [string]) { "bad $what"; exit 4 }
      $d = [double]$v; if ([double]::IsNaN($d) -or $d -lt $lo -or $d -gt $hi) { "bad $what"; exit 4 }
      return $d
    }
    $oStart = Vec3 $t.outside.start 'outside.start'; $oDoor = Vec3 $t.outside.door 'outside.door'
    $oArr = Vec3 $t.outside.arrival 'outside.arrival'; $oNear = Vec3 $t.outside.near 'outside.near' $true
    $iStart = Vec3 $t.inside.start 'inside.start'; $iDoor = Vec3 $t.inside.door 'inside.door'
    $iArr = Vec3 $t.inside.arrival 'inside.arrival'; $iNear = Vec3 $t.inside.near 'inside.near' $true
    $sl = @($t.spawn_local); if ($sl.Count -lt 2 -or $sl.Count -gt 3) { "bad spawn_local"; exit 4 }
    $radius = Num $t.radius 4.0 0.5 50 'radius'
    $walkMs = [int](Num $t.walk_ms 8000 0 60000 'walk_ms'); $stepMs = [int](Num $t.walk_step_ms 500 100 5000 'walk_step_ms')
    $settle = [int](Num $t.settle_ms 6000 0 30000 'settle_ms'); $drop = Num $t.drop 0.5 0 50 'drop'
    $nearWait = [int](Num $t.near_wait_ms 6000 0 60000 'near_wait_ms'); $loadWait = [int](Num $t.load_wait_s 90 10 600 'load_wait_s')
    $hOut = Num $t.heading_out 0 0 360 'heading_out'; $hIn = Num $t.heading_in 0 0 360 'heading_in'
    $startTol = Num $t.start_tol 3.0 0.5 50 'start_tol'; $movedM = Num $t.moved_m 30.0 5 1000 'moved_m'
    $oRef = ''
    if ($null -ne $t.outside.ref) {
      $oRef = "$($t.outside.ref)"; if ($oRef -cnotmatch '^[0-9A-Fa-f]{8}$') { "bad outside.ref"; exit 4 }
    }
    $lightCmds = Light-Commands
    $preCmds = Console-List $t.console_pre 'console_pre'; $postCmds = Console-List $t.console_post 'console_post'
    $parse = Join-Path $here 'parse_npc.py'
    function Dist3([string]$read, $p) {
      if ("$read" -notmatch $pos3) { return $null }
      $v = "$read".Trim().Split(' ', [StringSplitOptions]::RemoveEmptyEntries)
      return [Math]::Sqrt([Math]::Pow([double]$v[0] - $p[0], 2) + [Math]::Pow([double]$v[1] - $p[1], 2) + [Math]::Pow([double]$v[2] - $p[2], 2))
    }
    function Prompt-Up([string]$png) {
      $f = Join-Path $Out $png
      if (-not (Test-Path $f)) { return $false }
      return ((& $env:FO4SF_PYTHON (Join-Path $here 'prompt_visible.py') $f) -eq 'yes')
    }
    function In-Cell([string]$tag) {
      # player.GetInCell <cell> in its own console session (ClearConsole first: its echo marks the session start for
      # parse_npc.py), the capture and OCR kept as <tag>_cap.png / <tag>_ocr.txt; 1, 0 or $null (not read)
      Console-Open
      Send "type:ClearConsole|key:enter|wait:500|type:player.GetInCell $cell|key:enter|wait:900"
      $cap = Join-Path $Out "${tag}_cap.png"; $prep = Join-Path $Out "${tag}_prep.png"; $txt = Join-Path $Out "${tag}_ocr.txt"
      powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $here 'shot_region.ps1') -Out $cap | Out-Null
      $r = $null
      foreach ($th in 135, 140, 130, 145) {
        & $env:FO4SF_PYTHON (Join-Path $here 'ocr_prep.py') $cap $prep $th 12 | Out-Null
        (powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $here 'ocr.ps1') -Image $prep -Scale 1) | Set-Content $txt -Encoding utf8
        $r = (& $env:FO4SF_PYTHON $parse $txt '--expect=incell') | ConvertFrom-Json
        if ($r -and $null -ne $r.incell) { break }
      }
      Send 'key:grave|wait:600'
      return @{ incell = $(if ($r) { $r.incell } else { $null }); ocr = $(if ($r) { $r.ocr } else { '' }) }
    }
    function Vec-Of([string]$read) {
      if ("$read" -notmatch $pos3) { return $null }
      $v = "$read".Trim().Split(' ', [StringSplitOptions]::RemoveEmptyEntries)
      return ,@([double]$v[0], [double]$v[1], [double]$v[2])
    }
    function Leg-Check($L, [string]$tag, $start, $door, [int]$ms, [int]$tries) {
      # Which side of the door is the player on (after a walk step, after E, before the last-try teleport)? 'loaded':
      # the HUD is gone (a fade or a loading screen) or the position reads more than moved_m from the leg's start (a
      # load whose fade and loading screen both fell between two HUD checks; the two sides are about 2.7 km apart);
      # 'here': a read within moved_m of the start, kept in $L.checks with its distances; 'unread': no read while the
      # HUD is up (an OCR miss). Nothing is teleported or pressed on the strength of 'unread'.
      if (-not (Hud-Shown "$($L['name'])_$tag.png")) { $L['load_by'] = 'hud'; return 'loaded' }
      $p = Read-Pos '' $tries
      $c = [ordered]@{ tag = $tag; ms = $ms; read = $p }
      $L['checks'] += $c
      if ("$p" -notmatch $pos3) {
        if (-not (Hud-Shown "$($L['name'])_${tag}_after.png")) { $L['load_by'] = 'hud'; return 'loaded' }
        return 'unread'
      }
      $ds = Dist3 $p $start
      $c['from_start'] = [Math]::Round($ds, 2); $c['to_door'] = [Math]::Round((Dist3 $p $door), 2)
      if ($ds -gt $movedM) { $L['load_by'] = 'position'; return 'loaded' }
      return 'here'
    }
    function Door-Leg([string]$name, $start, $door, $near, [double]$heading) {
      # Teleport to the start facing the door and read it; walk at the door in walk_step_ms steps, after each a HUD
      # check and a position read (Leg-Check): a load ends the walk at once, so the player never walks on in the new
      # cell; two steps without progress (0.2 m) end it too. E only when a prompt showed, the last-try teleport to
      # "near" only after a read put the player on this side: a load the HUD checks missed must never be followed by
      # a teleport to this side's coordinates in the other cell (the interior's void, or 99 m under the terrain).
      $L = [ordered]@{ name = $name; start_target = $start; door = $door; checks = @() }
      Teleport @($start[0], $start[1], ($start[2] + $drop)) $heading 10
      Start-Sleep -Milliseconds $settle
      $L['start_read'] = Read-Pos
      $L['start_shot'] = Shot "${name}_start.png"
      $L['prompt'] = Prompt-Up "${name}_start.png"
      $walked = 0; $trig = ''; $act = 'walk'; $state = 'unread'
      $sv0 = Vec-Of $L['start_read']
      $go = $false
      if ($null -eq $sv0) { $L['walk_skipped'] = 'the start was not read' }
      elseif ([Math]::Sqrt([Math]::Pow($sv0[0] - $start[0], 2) + [Math]::Pow($sv0[1] - $start[1], 2)) -gt $startTol) {
        $L['walk_skipped'] = 'the start read is not at the start'
      } else { $go = $true; $state = 'here' }
      if ($go) {
        $prev = $sv0; $still = 0
        while ($walked -lt $walkMs) {                     # walk at the door
          $ms = [Math]::Min($stepMs, $walkMs - $walked)
          Send "hold:w,$ms|wait:250"
          $walked += $ms
          $state = Leg-Check $L 'walk' $start $door $walked 1
          if ($state -eq 'loaded') { $trig = 'walk'; break }
          if (-not $L['prompt'] -and (Prompt-Up "${name}_walk.png")) { $L['prompt'] = $true }
          if ($state -eq 'here') {
            $cur = Vec-Of $L['checks'][-1]['read']
            if ($null -ne $prev -and (Dist3 $L['checks'][-1]['read'] $prev) -lt 0.2) { $still++ } else { $still = 0 }
            $prev = $cur
            if ($still -ge 2) { $L['walk_stopped'] = 'no progress in two steps'; break }
          }
        }
        if ($state -ne 'loaded' -and $L['prompt']) {     # a door with an activation prompt: E
          if ($state -ne 'here') { $state = Leg-Check $L 'pre_e' $start $door $walked 3; if ($state -eq 'loaded') { $trig = $act } }
          if ($state -eq 'here') {
            $pre = Join-Path $Out "${name}_pre_e.png"
            powershell -NoProfile -ExecutionPolicy Bypass -File $shot -Out $pre | Out-Null
            if (Prompt-Up "${name}_pre_e.png") {
              Send 'key:e|wait:2500'
              $act = 'e'
              $state = Leg-Check $L 'e' $start $door $walked 3
              if ($state -eq 'loaded') { $trig = 'e' }
            }
          }
        }
        if ($state -ne 'loaded' -and $near) {             # last try: stand 1 m in front of the door
          if ($state -ne 'here') { $state = Leg-Check $L 'pre_near' $start $door $walked 3; if ($state -eq 'loaded') { $trig = $act } }
          if ($state -eq 'here') {
            $L['near_m'] = [Math]::Round([Math]::Sqrt([Math]::Pow($near[0] - $door[0], 2) + [Math]::Pow($near[1] - $door[1], 2)), 2)
            Teleport @($near[0], $near[1], ($near[2] + $drop)) $heading 10
            $act = 'near'
            $t1 = Get-Date
            while (((Get-Date) - $t1).TotalMilliseconds -lt $nearWait) {
              if (-not (Hud-Shown "${name}_near.png")) { $state = 'loaded'; $trig = 'near'; $L['load_by'] = 'hud'; break }
              Start-Sleep -Milliseconds 1000
            }
          } elseif ($state -ne 'loaded') { $L['near_skipped'] = 'the player was not read on this side of the door' }
        }
      }
      $loaded = $state -eq 'loaded'
      $L['trigger'] = $trig; $L['walked_ms'] = $walked; $L['load_seen'] = [bool]($loaded -and $L['load_by'] -eq 'hud')
      if ($L['load_seen']) { $w = Wait-Hud $loadWait "${name}_hud.png"; $L['hud_back'] = $w.up; $L['load_s'] = $w.secs }
      Start-Sleep 3
      $arr = Read-Settled
      $L['arrival_read'] = $arr.read; $L['arrival_settled'] = $arr.settled; $L['arrival_reads'] = $arr.reads
      if ($go -and -not $loaded -and "$($arr.read)" -match $pos3 -and (Dist3 $arr.read $start) -gt $movedM) {
        $L['trigger'] = $act; $L['load_by'] = 'position'     # a load after the last action that no HUD check saw
      }
      $c = In-Cell "${name}_cell"
      $L['incell'] = $c.incell; $L['incell_ocr'] = $c.ocr
      $L['shot'] = Shot "${name}_arrival.png"
      return $L
    }

    # 1. the coc arrival and the overlay's merge offset
    Run-Console $preCmds 'pre'
    Console-Open
    Send "type:$($t.travel)|key:enter|wait:400|key:grave|wait:3000"
    $w0 = Wait-Hud 90 'hud.png'; $obs['load_s'] = $w0.secs; $obs['hud_back'] = $w0.up
    Start-Sleep 3
    $arr = Read-Settled
    $obs['spawn_read'] = $arr.read; $obs['spawn_settled'] = $arr.settled; $obs['spawn_reads'] = $arr.reads
    $obs['shot'] = Shot 'arrival.png'
    Apply-Light $lightCmds "$($obs['shot'])"
    Run-Console $postCmds 'post'
    if (-not $arr.settled -or "$($arr.read)" -notmatch $pos3) {
      $obs['offset_missing'] = 'the arrival was not read or still moving after 5 reads'; Save-Obs; exit 0
    }
    $sv = "$($arr.read)".Trim().Split(' ', [StringSplitOptions]::RemoveEmptyEntries)
    $O = @(([double]$sv[0] - [double]$sl[0]), ([double]$sv[1] - [double]$sl[1]), 0.0)
    if ($sl.Count -ge 3) { $O[2] = [double]$sv[2] - [double]$sl[2] }
    $obs['offset'] = $O; $obs['offset_from'] = 'spawn'
    $spawnRead = "$($arr.read)"
    Save-Obs
    if ($oRef) {                                         # a diagnostic: where the engine reports the persistent door
      $obs['door_read'] = Read-Pos $oRef; Save-Obs        # (prid + getpos; nothing moves)
    }
    function Plus($p, $o) { if ($null -eq $p) { return $null }; return @(($p[0] + $o[0]), ($p[1] + $o[1]), ($p[2] + $o[2])) }
    # 2. in: through the door in the world, into the interior
    $legIn = Door-Leg 'in' (Plus $oStart $O) (Plus $oDoor $O) (Plus $oNear $O) $hOut
    $obs['legs'] = @($legIn); Save-Obs
    $d = Dist3 $legIn['arrival_read'] $iArr
    if ($null -eq $d -or $d -gt $radius) { Save-Obs; exit 0 }
    # 3. out: through the interior door, back onto the terrain (the merged frame)
    $legOut = Door-Leg 'out' $iStart $iDoor $iNear $hIn
    $obs['legs'] = @($legIn, $legOut); Save-Obs
    $d = Dist3 $legOut['arrival_read'] (Plus $oArr $O)
    if ($null -eq $d -or $d -gt $radius) { Save-Obs; exit 0 }
    # 4. save under the test's own name; its file must appear in the Saves folder
    $saves = $env:FO4SF_SAVES_DIR
    if (-not $saves) {
      $saves = Join-Path $env:USERPROFILE 'OneDrive\Documents\My Games\Starfield\Saves'
      if (-not (Test-Path $saves)) { $saves = Join-Path $env:USERPROFILE 'Documents\My Games\Starfield\Saves' }
    }
    $S = [ordered]@{ name = $save; dir_found = (Test-Path $saves); found = $false }
    $saveAt = (Get-Date).AddSeconds(-2)
    Console-Open
    Send "type:save $save|key:enter|wait:5000|key:grave|wait:1500"
    $t1 = Get-Date
    do {
      $f = Get-ChildItem -Path $saves -Filter "*$save*" -File -ErrorAction SilentlyContinue |
           Where-Object { $_.LastWriteTime -ge $saveAt } | Sort-Object LastWriteTime -Descending | Select-Object -First 1
      if (-not $f) { Start-Sleep 2 }
    } until ($f -or ((Get-Date) - $t1).TotalSeconds -gt 30)
    if ($f) { $S['found'] = $true; $S['file'] = $f.Name; $S['size'] = $f.Length; $S['mtime'] = $f.LastWriteTime.ToString('s') }
    else { $S['why'] = $(if ($S['dir_found']) { "no file *$save* written in the Saves folder within 30 s" } else { 'Saves folder not found' }) }
    $obs['save'] = $S; $obs['save_shot'] = Shot 'saved.png'; Save-Obs
    if (-not $S['found']) { exit 0 }
    # 5. away from the saved spot (back to the settled coc arrival, about 40 m north on the terrain), then load it: the
    # load must bring the player back, so the position shows it even when no HUD check saw the loading screen
    $R = [ordered]@{ name = $save }
    $away = Vec-Of $spawnRead
    if ($null -ne $away) {
      Teleport @($away[0], $away[1], ($away[2] + $drop)) 0 10
      Start-Sleep -Milliseconds $settle
      $R['away_read'] = Read-Pos
      $R['away_shot'] = Shot 'away.png'
      $obs['reload'] = $R; Save-Obs
    }
    Console-Open
    Send "type:load $save|key:enter|wait:2500"
    $gone = $false; $t1 = Get-Date
    while (-not $gone -and ((Get-Date) - $t1).TotalSeconds -lt 20) {
      if (-not (Hud-Shown 'reload_hud.png')) { $gone = $true } else { Start-Sleep -Milliseconds 1000 }
    }
    $R['load_seen'] = $gone
    if ($gone) { $w = Wait-Hud 120 'reload_hud.png'; $R['hud_back'] = $w.up; $R['load_s'] = $w.secs }
    Start-Sleep 3
    $r2 = Read-Settled
    $R['read'] = $r2.read; $R['settled'] = $r2.settled; $R['reads'] = $r2.reads
    $c = In-Cell 'reload_cell'; $R['incell'] = $c.incell; $R['incell_ocr'] = $c.ocr
    $R['shot'] = Shot 'reload.png'
    $obs['reload'] = $R
  }
  'recover' {
    # testqueue.py calls this only when nobody touched the PC since its last input: a menu, the Steam overlay or a
    # popup hides the HUD. Nudge the mouse (ends the idle camera), then up to three Escapes, each followed by a check.
    $hud = Join-Path $Out 'hud.png'
    function Hud-Up { powershell -NoProfile -ExecutionPolicy Bypass -File $shot -Out $hud | Out-Null
                      (& $env:FO4SF_PYTHON (Join-Path $here 'hud_visible.py') $hud) -eq 'yes' }
    Send 'move:1,0|wait:300|move:-1,0|wait:1500'
    $obs['hud_before'] = Hud-Up
    $n = 0
    while (-not (Hud-Up) -and $n -lt 3) { Send 'key:esc|wait:2000'; $n++ }
    $obs['escapes'] = $n
    # Starfield's "Boundary Reached" popup closes with Tab (its Cancel), not Escape (exp3 2026-10-11)
    if (-not (Hud-Up)) { Send 'key:tab|wait:2000'; $obs['tab'] = $true
                         if (-not (Hud-Up)) { Send 'key:esc|wait:2000' } }
    $obs['hud_after'] = Hud-Up
    $obs['shot'] = Shot 'recover.png'
  }
  default { "unknown kind $($t.kind)"; exit 4 }
}
Save-Obs
exit 0
