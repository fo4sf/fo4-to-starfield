# One queued in-game test step for testqueue.py: performs the actions, writes raw observations, judges nothing.
# usage: qstep.ps1 -Spec <test.json> -Out <test dir>      (Starfield in front, in the test's cell, console closed)
# Writes <Out>\obs.json. Every key press goes through input.ps1's foreground guard; testqueue.py sets
# FO4SF_NO_FOCUS_STEAL=1, so a guard stop (the owner switched windows) ends the step with exit 2 and nothing more is sent.
# Exit 0: observations written (they may still be incomplete: the judge decides). 2: input guard. 3: console could not be
# opened safely (nothing typed). 4: bad spec.
# Kinds (spec.kind): route (stairs/door, via route_run.ps1), fall (drop onto a floor point), movable (walk into an item and
# read its position before and after; with impulses, ApplyHavokImpulse when the walk did not move it), movable_control
# (place an item in a vanilla cell, walk over it, then the impulses), travel (activate a load door, read where the player arrives), terrain (drop onto
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
$script:bridge = [bool]$t.bridge_reads                     # the player's position from the game's own log (Bridge-Read); "bridge" itself is a walk plan's deck
$script:bridgeMaxAge = $(if ($t.bridge_max_age_s) { [double]$t.bridge_max_age_s } else { 2.0 })   # (the sandbox: longer)
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
  if ($LASTEXITCODE -eq 5) {                             # holdg: a STOP file (walk, FO4SF_STOP_FILES) appeared mid-hold
    $hit = @("$env:FO4SF_STOP_FILES".Split(';') | Where-Object { $_ -and (Test-Path -LiteralPath $_) })
    $obs['stopped'] = "STOP file $($hit -join ', ') (during a hold; the key was released)"; $obs['walk_stopped'] = 'stopped'
    Save-Obs; exit 2
  }
  if ($LASTEXITCODE -ne 0) { $obs['stopped'] = 'input guard'; Save-Obs; exit 2 }
}
function Console-Open {
  powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $here 'console_open.ps1') | Out-Null
  $c = $LASTEXITCODE
  if ($c -eq 2) { $obs['stopped'] = 'input guard'; Save-Obs; exit 2 }
  if ($c -ne 0) { $obs['stopped'] = "console not opened safely ($c)"; Save-Obs; exit 3 }
}
$script:strictReads = $false     # door_trip: readpos -Strict (labelled values of the read's own session only)
$script:lastHeading = $null      # the heading of the last Read-Pos with -Angle ($null: not read)
$script:readN = 0                # readpos.ps1 runs so far: each gets its own folder <Out>\reads\NNNN
function Bridge-Ref-Read([string]$ref, [int]$tries = 2) {
  # a reference's position through the bridge, no OCR (docs/ai/test-queue.md "Bridge", 2026-10-15): one console session
  # types cgf "FO4SF_Probe.Pos" <decimal ref> (FO4SF_Probe.psc replies "FO4SF ref=.. pos=.. loaded=.." in the bridge's
  # log: verified in game, nine R05 runs) and bridge_log.py wait-ref returns the first reply written after the mark
  # taken before the command (an older reply never passes for this read). "x y z" in the game's frame (the numbers
  # getpos prints) or $null, when the caller falls back to readpos. obs.read_log: via = bridge-ref, the log line.
  if ($ref -notmatch '^[0-9A-Fa-f]{8}$') { return $null }
  $u = [Convert]::ToUInt32($ref, 16); $dec = [int64]$u
  if ($u -gt 2147483647) { $dec = $dec - 4294967296 }   # the script takes a Papyrus int: load index FF.. is negative
  $py = Join-Path $here 'bridge_log.py'; $logArg = @(); if ($env:FO4SF_BRIDGE_LOG) { $logArg = @('--log', $env:FO4SF_BRIDGE_LOG) }
  for ($n = 0; $n -lt $tries; $n++) {
    $script:readN++
    $mark = "$(& $env:FO4SF_PYTHON $py mark @logArg)".Trim(); if ($mark -notmatch '^\d+$') { $mark = '0' }
    Console-Open
    Send "type:cgf `"FO4SF_Probe.Pos`" $dec|key:enter|wait:500|key:grave|wait:800"
    $j = $null
    try { $j = (& $env:FO4SF_PYTHON $py wait-ref $ref --since $mark --timeout 8 @logArg) | ConvertFrom-Json } catch { $j = $null }
    if (-not $obs.Contains('read_log')) { $obs['read_log'] = @() }
    $ok = [bool]($j -and $j.ok -and @($j.pos).Count -eq 3)
    $pos = $(if ($ok) { (@($j.pos) | ForEach-Object { ([double]$_).ToString([Globalization.CultureInfo]::InvariantCulture) }) -join ' ' } else { "fail $($j.why)" })
    $rec = [ordered]@{ n = $script:readN; via = 'bridge-ref'; ref = $ref; nonce = $null; result = $pos }
    if ($ok) { $rec['line'] = $j.line; $rec['loaded'] = $j.loaded }
    $obs['read_log'] += $rec
    if ($ok) { return $pos }
  }
  return $null
}
function Bridge-Read([bool]$angle = $false, [int]$tries = 12) {
  # the player's position from the newest line of the bridge's log (bridge_log.py latest: the game's FO4SF_Bridge
  # script writes one every half second; docs/ai/test-queue.md "Bridge"), not older than $script:bridgeMaxAge s:
  # "x y z" (the game's six decimals) or $null; the heading to $script:lastHeading when $angle. No console, no
  # capture: a stale log (the game or its quest not running) is a failed read, never an old position. Every try is
  # listed in obs.read_log with via = bridge and the line's rt / n (the read's provenance, as readpos's nonce is).
  # Freshness is the line's own clock stamp (bridge_log.py latest), and the tries span about 8 s: the game writes
  # nothing while paused (a loading screen, the console open), and resumes a few seconds after the console closes
  # (bridge_probe_1015 a1, 2026-10-14: the first line after a hop came 3 s after the reads had given up).
  $script:lastHeading = $null
  $cmd = @((Join-Path $here 'bridge_log.py'), 'latest', '--max-age', "$($script:bridgeMaxAge)")
  if ($env:FO4SF_BRIDGE_LOG) { $cmd += @('--log', $env:FO4SF_BRIDGE_LOG) }     # the sandbox's log
  for ($n = 0; $n -lt $tries; $n++) {
    $script:readN++
    $j = $null
    try { $j = (& $env:FO4SF_PYTHON @cmd) | ConvertFrom-Json } catch { $j = $null }
    if (-not $obs.Contains('read_log')) { $obs['read_log'] = @() }
    $ok = [bool]($j -and $j.ok -and @($j.pos).Count -eq 3)
    $pos = $(if ($ok) { (@($j.pos) | ForEach-Object { ([double]$_).ToString([Globalization.CultureInfo]::InvariantCulture) }) -join ' ' } else { "fail $($j.why)" })
    $rec = [ordered]@{ n = $script:readN; via = 'bridge'; ref = ''; nonce = $null; result = $pos }
    if ($ok) { $rec['rt'] = $j.rt; $rec['line'] = $j.n }
    $obs['read_log'] += $rec
    if ($ok) {
      if ($angle -and $null -ne $j.ang) { $script:lastHeading = [double]$j.ang }
      return $pos
    }
    Start-Sleep -Milliseconds 700
  }
  return $null
}
function Read-Pos([string]$ref = '', [int]$tries = 3, [bool]$angle = $false) {
  # the player: the bridge; a ref: readpos. A caller's small try count (Read-Settled's 3) is a readpos retry budget;
  # a bridge read needs its ~8 s of patience whatever the caller asked (bridge_probe_1015b: 3 tries gave up 2 s before
  # the first line after the loading screen)
  if ($script:bridge -and -not $ref) { return (Bridge-Read $angle ([Math]::Max($tries, 12))) }
  if ($script:bridge -and $ref) {                       # a reference: the bridge's probe reply; readpos's OCR only if it fails
    $br = Bridge-Ref-Read $ref
    if ($null -ne $br) { return $br }
  }
  # up to 3 reads: OCR sometimes drops or shifts a column; a read with x == z or a missing value is retried. With
  # $angle (door_trip arrivals) readpos also types player.getangle z: the read returns "x y z" and the heading goes to
  # $script:lastHeading. Every readpos run keeps its capture, OCR text and read.json (its nonce) in its own folder,
  # listed in obs.read_log (Codex's review of PR #107: one shared folder, every read overwrote the last one's evidence)
  $p = 'fail'
  $extra = @()
  if ($script:strictReads) { $extra += '-Strict' }
  if ($angle -and -not $ref) { $extra += '-Angle' }
  $script:lastHeading = $null
  for ($n = 0; $n -lt $tries; $n++) {
    $script:readN++
    $rel = 'reads\{0:D4}' -f $script:readN; $work = Join-Path $Out $rel
    if ($ref) { $p = powershell -NoProfile -ExecutionPolicy Bypass -File $readpos -Work $work -Ref $ref @extra } else { $p = powershell -NoProfile -ExecutionPolicy Bypass -File $readpos -Work $work @extra }
    $rj = Join-Path $work 'read.json'; $nonce = $null
    if (Test-Path $rj) { try { $nonce = (Get-Content $rj -Raw | ConvertFrom-Json).nonce } catch { $nonce = $null } }
    if (-not $obs.Contains('read_log')) { $obs['read_log'] = @() }
    $obs['read_log'] += [ordered]@{ n = $script:readN; work = $rel; ref = $ref; nonce = $nonce; result = "$p" }
    if ("$p" -like 'fail guard*') { $obs['stopped'] = 'input guard'; Save-Obs; exit 2 }
    $v = "$p".Trim().Split(' ', [StringSplitOptions]::RemoveEmptyEntries)
    if ($extra -contains '-Angle' -and $v.Count -eq 4 -and $v[0] -ne $v[2]) {
      $script:lastHeading = [double]::Parse($v[3], [Globalization.CultureInfo]::InvariantCulture)
      return ($v[0..2] -join ' ')
    }
    if ($extra -notcontains '-Angle' -and $v.Count -eq 3 -and $v[0] -ne $v[2]) { return "$p".Trim() }
  }
  return $null
}
function Shot($name) { $f = Join-Path $Out $name; powershell -NoProfile -ExecutionPolicy Bypass -File $shot -Out $f | Out-Null; if (Test-Path $f) { return $name } else { return $null } }
$pos3 = '^\s*-?\d+(\.\d+)?\s+-?\d+(\.\d+)?\s+-?\d+(\.\d+)?\s*$'   # "x y z" as readpos prints it ("fail console 3" is not)
function Read-Settled([int]$tries = 5, [int]$gapMs = 3000, [bool]$angle = $false) {
  # the arrival, read until two reads 3 s apart agree within 0.3 m: exp1d (2026-10-11) read it mid-fall (z -500).
  # With $angle every read also reads the heading; heading = the first heading read (before anything turned the
  # player: the facing the arrival gave), headings = all of them
  $prev = Read-Pos '' 3 $angle; $reads = @("$prev"); $hs = @($script:lastHeading)
  for ($n = 1; $n -lt $tries; $n++) {
    Start-Sleep -Milliseconds $gapMs
    $cur = Read-Pos '' 3 $angle; $reads += "$cur"; $hs += $script:lastHeading
    if ("$prev" -match $pos3 -and "$cur" -match $pos3) {
      $a = "$prev".Trim().Split(' ', [StringSplitOptions]::RemoveEmptyEntries)
      $b = "$cur".Trim().Split(' ', [StringSplitOptions]::RemoveEmptyEntries)
      $still = $true
      for ($k = 0; $k -lt 3; $k++) { if ([Math]::Abs([double]$a[$k] - [double]$b[$k]) -ge 0.3) { $still = $false } }
      if ($still) { return @{ read = "$cur"; settled = $true; reads = $reads; heading = @($hs | Where-Object { $null -ne $_ })[0]; headings = $hs } }
    }
    $prev = $cur
  }
  return @{ read = $prev; settled = $false; reads = $reads; heading = @($hs | Where-Object { $null -ne $_ })[0]; headings = $hs }
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
$script:tpCapture = $false; $script:tpN = 0        # terrain teleport_console: capture each teleport's console session
function Teleport($pos, $heading, $pitch = 10, [string]$first = '') {
  # $first: a light command Apply-Light found working (from its validated table), typed in the same console session.
  # With $script:tpCapture (terrain "teleport_console": true, 2026-10-15: r05_medkit_1015/b/c/e, where player.setpos
  # left the player at the arrival) the session's console is captured and OCR'd before it closes (tp<n>.png,
  # obs.teleports): the game's own reply to the typed lines is the evidence nothing else keeps.
  Console-Open
  $pre = ''; if ($first) { $pre = "type:$first|key:enter|wait:400|" }
  $typed = ($pre + "type:player.setpos x $(F $pos[0])|key:enter|wait:350|type:player.setpos y $(F $pos[1])|key:enter|wait:350|" +
            "type:player.setpos z $(F $pos[2])|key:enter|wait:350|type:player.setangle z $(F $heading)|key:enter|wait:350|" +
            "type:player.setangle x $pitch|key:enter|wait:400")
  if ($script:tpCapture) {
    Send $typed
    $script:tpN++; $r = Read-Console "tp$($script:tpN)"
    if (-not $obs.Contains('teleports')) { $obs['teleports'] = @() }
    $obs['teleports'] += [ordered]@{ n = $script:tpN; target = @($pos | ForEach-Object { F $_ }); ocr = $r.ocr; shot = $r.shot }; Save-Obs
    Send 'key:grave|wait:1800'
  } else { Send ($typed + '|key:grave|wait:1800') }
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
$consoleOk = '^(?:GetINI "[A-Za-z0-9_]{1,64}:[A-Za-z0-9_]{1,64}"|SetINI "[A-Za-z0-9_]{1,64}:[A-Za-z0-9_]{1,64}" -?\d{1,9}(?:\.\d{1,6})?|SetLocalTime (?:1?\d|2[0-3])(?:\.\d{1,2})?(?: 1)?|cgf "Game\.SetLocalTime" (?:1?\d|2[0-3])(?:\.\d{1,2})?|fw [0-9A-Fa-f]{8}(?: 1)?|cgf "FO4SF_Probe\.Pos" \d{1,10}|cgf "FO4SF_Probe\.Ack" "[A-Za-z0-9_.-]{1,40}"|cgf "FO4SF_Probe\.Player"|cgf "Debug\.TraceUser" "fo4sf" "[A-Za-z0-9_ .-]{1,60}")\z'
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

# Movable items (movable with impulses, movable_control; docs/ai/test-queue.md "Movable items: walk, then impulse"). The
# item is selected by its id (prid) and confirmed with GetIsID <base> 1 in the same console session before anything reads
# its position or acts on it (npc_nav's handle rules: opening the console selects what is under the crosshair). Every
# line typed for it matches one of these patterns (testqueue.py builds them; a bad line ends the step with exit 4 before
# anything is typed).
$hexId = '^[0-9A-Fa-f]{8}$'
$impulseOk = '^ApplyHavokImpulse -?\d{1,2}(\.\d{1,3})? -?\d{1,2}(\.\d{1,3})? -?\d{1,2}(\.\d{1,3})? \d{1,6}(\.\d{1,2})?$'
$setMassOk = '^SetRigidBodyMass \d{1,4}(\.\d{1,2})?$'
$massProbe = 'cf "ObjectReference.GetMass"'
function Item-Capture([string[]]$cmds, [string[]]$need, [string]$tag = 'item') {
  # as npc_nav's Npc-Capture: ClearConsole first (its echo marks where this session begins), the commands, then
  # parse_npc.py on this session's OCR (up to four thresholds until $need is read); the capture and the OCR text stay
  # as <tag>_cap.png / <tag>_ocr.txt
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
    $r = (& $env:FO4SF_PYTHON (Join-Path $here 'parse_npc.py') $txt "--expect=$($exp -join ',')" "--typed=$($typed -join ',')") | ConvertFrom-Json
    $missing = @($need | Where-Object { $null -eq $r.$_ })
    if ($r -and $missing.Count -eq 0) { break }
  }
  return $r
}
function Select-Item([string]$ref, [string]$base, [string]$tag = 'item') {
  # console open, prid <ref>, GetIsID <base> must read 1 (a second try only repeats the session: an OCR miss). Returns
  # with the console OPEN and the item's read, or closes the console and returns $null
  if ("$ref" -notmatch $hexId -or "$base" -notmatch $hexId) { return $null }
  Console-Open
  foreach ($n in 1, 2) {
    $r = Item-Capture @("prid $ref", "GetIsID $base", 'getpos x', 'getpos y', 'getpos z') @('isid', 'pos') $tag
    if ($r -and $r.isid -eq 1) {
      $p = $null; if ("$($r.pos)" -match $pos3) { $p = "$($r.pos)" }
      return [ordered]@{ isid = 1; read = $p; how = $r.how }
    }
  }
  Send 'key:grave|wait:600'
  return $null
}
function Item-Read([string]$ref, [string]$base, [string]$tag = 'item') {
  # the item's confirmed position ("x y z"), console closed afterwards; $null when not selected or not read
  $s = Select-Item $ref $base $tag
  if (-not $s) { return $null }
  Send 'key:grave|wait:600'
  return $s.read
}
function Dist-3([string]$a, [string]$b) {
  if ("$a" -notmatch $pos3 -or "$b" -notmatch $pos3) { return $null }
  $u = "$a".Trim().Split(' ', [StringSplitOptions]::RemoveEmptyEntries); $v = "$b".Trim().Split(' ', [StringSplitOptions]::RemoveEmptyEntries)
  return [Math]::Sqrt([Math]::Pow([double]$u[0] - [double]$v[0], 2) + [Math]::Pow([double]$u[1] - [double]$v[1], 2) +
                      [Math]::Pow([double]$u[2] - [double]$v[2], 2))
}
function Item-DistXY([string]$read, $p) {
  if ("$read" -notmatch $pos3) { return $null }
  $v = "$read".Trim().Split(' ', [StringSplitOptions]::RemoveEmptyEntries)
  return [Math]::Sqrt([Math]::Pow([double]$v[0] - [double]$p[0], 2) + [Math]::Pow([double]$v[1] - [double]$p[1], 2))
}
function Impulse-Lines {
  # the planned impulse ladder, validated before anything is typed (exit 4 on a bad line)
  $out = @()
  foreach ($imp in @($t.impulses | Where-Object { $null -ne $_ })) {
    if ("$($imp.cmd)" -cnotmatch $impulseOk) { "bad impulse"; exit 4 }
    $out += $imp
  }
  if ($out.Count -gt 5) { "bad impulse"; exit 4 }
  return ,$out
}
function Push-Impulses([string]$ref, [string]$base, [string]$from, $lines) {
  # The impulse ladder after a walk that did not move the item ($from: its read after the walk). Each impulse in its own
  # confirmed session: Select-Item, then the line (its OCR kept as impulse_<k>_cmd), the console closed for
  # impulse_wait_ms (the game runs: the item hops and lands), a confirmed read and a screenshot. Stops at the first
  # impulse that moved the item moved_m. Everything goes to obs.json "impulses" after every step.
  $wait = 3000; if ($null -ne $t.impulse_wait_ms) { $wait = [int]$t.impulse_wait_ms }
  $min = 0.05; if ($null -ne $t.moved_m) { $min = [double]$t.moved_m }
  $done = @(); $k = 0
  foreach ($imp in $lines) {
    $k++
    $rec = [ordered]@{ dv = $imp.dv; magnitude = $imp.magnitude; cmd = "$($imp.cmd)"; applied = $false; read = $null }
    $s = Select-Item $ref $base "impulse_${k}_sel"
    if ($s) {
      $c = Item-Capture @("$($imp.cmd)") @() "impulse_${k}_cmd"
      $rec['ocr'] = $c.ocr; $rec['applied'] = $true
      Send "key:grave|wait:$wait"
      $rec['read'] = Item-Read $ref $base "impulse_${k}_read"
      $rec['shot'] = Shot "impulse_$k.png"
    }
    $done += $rec
    $obs['impulses'] = $done; Save-Obs
    $d = Dist-3 $rec['read'] $from
    if ($null -ne $d -and $d -ge $min) { break }
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
    # walk into an item of the build; with impulses (testqueue.py plan --impulse) the ladder follows a walk that did not
    # move it, on the item selected by prid <sf_ref> and confirmed by GetIsID <sf_base> 1
    $imps = Impulse-Lines
    if ($imps.Count -gt 0 -and ("$($t.sf_ref)" -notmatch $hexId -or "$($t.sf_base)" -notmatch $hexId)) { "bad sf_ref / sf_base"; exit 4 }
    $obs['item_before'] = Read-Pos $t.sf_ref
    Teleport $t.stand $t.heading 25
    $obs['player_start'] = Read-Pos
    $obs['shot_before'] = Shot 'before.png'
    Send "hold:w,$($t.walk_ms)|wait:1500"
    $obs['player_end'] = Read-Pos
    $obs['item_after'] = Read-Pos $t.sf_ref
    $obs['shot_after'] = Shot 'after.png'
    if ($imps.Count -gt 0) {
      $d = Dist-3 $obs['item_before'] $obs['item_after']
      $min = 0.05; if ($null -ne $t.moved_m) { $min = [double]$t.moved_m }
      if ($null -ne $d -and $d -lt $min) { Save-Obs; Push-Impulses "$($t.sf_ref)" "$($t.sf_base)" "$($obs['item_after'])" $imps }
    }
  }
  'movable_control' {
    # docs/ai/test-queue.md "Movable items: walk, then impulse". coc into a vanilla cell and read the arrival until it
    # settles; the player to the spot; the item placed at the player's feet (placeatme) while the player moves on to the
    # park point in the same console session (the game is paused while the console is open), so the item drops onto a
    # free floor during spawn_wait_ms; its handle confirmed as npc_nav's (PickLastRef's id, GetSelf names no other ref,
    # GetIsID <base> 1, within handle_tol of the spot); the GetMass probe / SetRigidBodyMass on the confirmed selection
    # when planned (their OCR kept; after SetRigidBodyMass the console closed mass_wait_ms and GetMass read again on a
    # second confirmed selection: the judge needs that reading); the player stand_m before the item facing heading, the
    # item's confirmed read, the walk (hold W walk_ms), the player's and the item's reads; the impulse ladder when the
    # walk did not move it; then
    # the item removed (disable, markfordelete) on a confirmed selection only. Everything typed is validated here again.
    if ("$($t.travel)" -notmatch '^coc [A-Za-z0-9_]+$') { "bad travel"; exit 4 }
    $base = "$($t.base)"; if ($base -notmatch $hexId) { "bad base"; exit 4 }
    $spot = @($t.spot); $park = @($t.park)
    if ($spot.Count -ne 3 -or $park.Count -ne 3) { "bad spot / park"; exit 4 }
    foreach ($x in @($spot + $park)) {
      if ($x -is [string] -or $x -is [bool] -or $null -eq $x) { "bad spot / park"; exit 4 }
      $dx = [double]$x; if ([double]::IsNaN($dx) -or [Math]::Abs($dx) -gt 1e6) { "bad spot / park"; exit 4 }
    }
    $heading = [double]$t.heading; $standM = [double]$t.stand_m; $drop = [double]$t.drop
    if ($heading -lt 0 -or $heading -gt 360 -or $standM -lt 0.5 -or $standM -gt 5 -or $drop -lt 0 -or $drop -gt 5) { "bad heading / stand_m / drop"; exit 4 }
    $setMass = ''; if ($t.set_mass_cmd) { $setMass = "$($t.set_mass_cmd)"; if ($setMass -cnotmatch $setMassOk) { "bad set_mass_cmd"; exit 4 } }
    $probe = ''; if ($t.probe_cmd) { $probe = "$($t.probe_cmd)"; if ($probe -cne $massProbe) { "bad probe_cmd"; exit 4 } }
    if ($setMass -and -not $probe) { "set_mass_cmd without probe_cmd: the mass set would never be read back"; exit 4 }
    $massWait = 1000; if ($null -ne $t.mass_wait_ms) { $massWait = [int]$t.mass_wait_ms }
    if ($massWait -lt 200 -or $massWait -gt 10000) { "bad mass_wait_ms"; exit 4 }
    $imps = Impulse-Lines
    $spawnWait = [int]$t.spawn_wait_ms; $handleTol = [double]$t.handle_tol; $settle = [int]$t.settle_ms
    $walkMs = [int]$t.walk_ms; $min = [double]$t.moved_m
    if ($spawnWait -lt 500 -or $spawnWait -gt 30000 -or $handleTol -lt 0.3 -or $handleTol -gt 10 -or $settle -lt 0 -or
        $settle -gt 30000 -or $walkMs -lt 100 -or $walkMs -gt 5000 -or $min -lt 0.01 -or $min -gt 1) { "bad timing / tolerances"; exit 4 }
    $preCmds = Console-List $t.console_pre 'console_pre'; $postCmds = Console-List $t.console_post 'console_post'
    # 1. travel, the arrival read until it stops
    Run-Console $preCmds 'pre'                       # after the save has loaded, before the travel
    Console-Open
    Send "type:$($t.travel)|key:enter|wait:400|key:grave|wait:3000"
    $w0 = Wait-Hud 90 'hud.png'; $obs['load_s'] = $w0.secs; $obs['hud_back'] = $w0.up
    Start-Sleep 3
    $arr = Read-Settled
    $obs['arrival_read'] = $arr.read; $obs['arrival_settled'] = $arr.settled; $obs['arrival_reads'] = $arr.reads
    $obs['shot'] = Shot 'arrival.png'
    Save-Obs
    Run-Console $postCmds 'post'                     # after the arrival, before the item is placed
    # 2. the player at the spot (placeatme puts the item at the player's feet)
    Teleport @([double]$spot[0], [double]$spot[1], ([double]$spot[2] + $drop)) $heading 10
    Start-Sleep -Milliseconds $settle
    $obs['player_spot'] = Read-Pos
    Save-Obs
    $ds = Item-DistXY $obs['player_spot'] $spot
    if ($null -eq $ds -or $ds -gt 1.0) { exit 0 }      # not at the spot: nothing placed (judged START)
    # not on the floor planned at the spot (testqueue.py SPOT_Z_M, 0.4 m): nothing placed (judged START)
    $sz0 = [double]("$($obs['player_spot'])".Trim().Split(' ', [StringSplitOptions]::RemoveEmptyEntries)[2])
    if ([Math]::Abs($sz0 - [double]$spot[2]) -gt 0.4) { exit 0 }
    # 3. the item placed, the player to the park point in the same session, the console closed for spawn_wait_ms
    Console-Open
    $s0 = Item-Capture @("player.placeatme $base 1") @() 'place'
    Send ("type:player.setpos x $(F $park[0])|key:enter|wait:350|type:player.setpos y $(F $park[1])|key:enter|wait:350|" +
          "type:player.setpos z $(F ([double]$park[2] + $drop))|key:enter|wait:350|type:player.setangle z $(F $heading)|key:enter|" +
          "wait:350|key:grave|wait:$spawnWait")
    # 4. the handle (npc_nav's Pick-Npc): plr alone, prid <id> + GetSelf, GetIsID <base> + getpos
    Console-Open
    $r1 = Item-Capture @('plr') @('ref') 'spawn_plr'
    $pk = [ordered]@{ 'ref' = $null; self = $null; isid = $null; read = $null; place_ocr = $s0.ocr; plr_ocr = $r1.ocr }
    if ("$($r1.ref)" -cmatch '^FF[0-9A-F]{6}$') {
      $pk['ref'] = "$($r1.ref)"
      $r2 = Item-Capture @("prid $($pk['ref'])", 'GetSelf') @('self') 'spawn_self'
      if ("$($r2.self)" -match $hexId) { $pk['self'] = "$($r2.self)" }
      $r3 = Item-Capture @("GetIsID $base", 'getpos x', 'getpos y', 'getpos z') @('isid', 'pos') 'spawn_isid'
      $pk['isid'] = $r3.isid
      if ("$($r3.pos)" -match $pos3) { $pk['read'] = "$($r3.pos)" }
    }
    Send 'key:grave|wait:600'
    $dist = Item-DistXY $pk['read'] $spot
    $why = @()
    if (-not $pk['ref']) { $why += 'PickLastRef gave no FFxxxxxx id' }
    else {
      if ($pk['self'] -and $pk['self'] -ne $pk['ref']) { $why += "after prid $($pk['ref']) GetSelf named $($pk['self']): another ref is selected" }
      if ($pk['isid'] -ne 1) { $why += "GetIsID $base read $(if ($null -eq $pk['isid']) { 'nothing' } else { $pk['isid'] })" }
      if ($null -eq $dist) { $why += 'its position was not read' }
      elseif ($dist -gt $handleTol) { $why += "it lies $([math]::Round($dist, 2)) m from the spot (more than $handleTol m)" }
    }
    $pk['dist'] = $(if ($null -ne $dist) { [math]::Round($dist, 2) } else { $null })
    $pk['confirmed'] = ($why.Count -eq 0); $pk['why'] = ($why -join '; ')
    $obs['spawn'] = $pk
    $obs['spawn_shot'] = Shot 'spawn.png'
    Save-Obs
    $ref = "$($pk['ref'])"
    if ($pk['confirmed']) {
      # 5. the GetMass probe and SetRigidBodyMass on the confirmed selection (their replies' OCR is kept). After
      # SetRigidBodyMass the console is closed for mass_wait_ms (the game runs) and GetMass is read again on a second
      # confirmed selection: the judge reads a set_mass test only when that reading is the mass set (else MASS)
      if ($setMass -or $probe) {
        $mp = [ordered]@{}
        $sel = Select-Item $ref $base 'mass_sel'
        if ($sel) {
          if ($probe) { $mp['before'] = (Item-Capture @($probe) @() 'probe_before').ocr }
          if ($setMass) { $obs['set_mass'] = [ordered]@{ typed = $true; cmd = $setMass; ocr = (Item-Capture @($setMass) @() 'set_mass').ocr } }
          Send "key:grave|wait:$(if ($setMass) { $massWait } else { 600 })"
          if ($setMass) {
            $sel2 = Select-Item $ref $base 'mass_sel2'
            if ($sel2) {
              $mp['after'] = (Item-Capture @($probe) @() 'probe_after').ocr
              Send 'key:grave|wait:600'
            } else { $mp['after_note'] = 'the item was not selected again for the reading after SetRigidBodyMass' }
          }
        } elseif ($setMass) { $obs['set_mass'] = [ordered]@{ typed = $false; cmd = $setMass } }
        if ($probe) { $obs['mass_probe'] = $mp }
        Save-Obs
      }
      # 6. the player stand_m before the item (its spawn read), facing it along heading, on the floor read at the spot
      $iv = "$($pk['read'])".Trim().Split(' ', [StringSplitOptions]::RemoveEmptyEntries)
      $hr = $heading * [Math]::PI / 180
      $sx = [double]$iv[0] - [Math]::Sin($hr) * $standM; $sy = [double]$iv[1] - [Math]::Cos($hr) * $standM
      $sz = [double]("$($obs['player_spot'])".Trim().Split(' ', [StringSplitOptions]::RemoveEmptyEntries)[2])
      $obs['stand'] = @([math]::Round($sx, 3), [math]::Round($sy, 3), [math]::Round($sz, 3))
      Teleport @($sx, $sy, ($sz + $drop)) $heading 25
      Start-Sleep -Milliseconds $settle
      $obs['player_start'] = Read-Pos
      $obs['item_before'] = Item-Read $ref $base 'item_before'
      $obs['shot_before'] = Shot 'before.png'
      Save-Obs
      # 7. the walk over the item, then the player's and the item's reads
      Send "hold:w,$walkMs|wait:1500"
      $obs['player_end'] = Read-Pos
      $obs['item_after'] = Item-Read $ref $base 'item_after'
      $obs['shot_after'] = Shot 'after.png'
      Save-Obs
      # 8. the impulse ladder when the walk did not move it
      $d = Dist-3 $obs['item_before'] $obs['item_after']
      if ($imps.Count -gt 0 -and $null -ne $d -and $d -lt $min) { Push-Impulses $ref $base "$($obs['item_after'])" $imps }
    }
    # 9. remove the item: disable and markfordelete on a confirmed selection only (a world ref is never touched)
    $clean = [ordered]@{ removed = $false }
    if ($pk['confirmed']) {
      $sel = Select-Item $ref $base 'remove_sel'
      if ($sel) {
        $dd = Item-Capture @('disable', 'GetDisabled') @('disabled') 'remove'
        Send 'type:markfordelete|key:enter|wait:600|key:grave|wait:600'
        $clean['removed'] = $true; $clean['disabled'] = $dd.disabled
      } else { $clean['note'] = 'the item could not be selected again: it may be left in the cell' }
    } else { $clean['note'] = 'no confirmed handle: an item may be left in the cell' }
    $obs['cleanup'] = $clean
    $obs['end_shot'] = Shot 'cleanup.png'
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
    $hud = Join-Path $Out 'hud.png'; $t0 = Get-Date; $lo = 0; $up = $false
    do { Start-Sleep 3
         if ($lo -eq 0) {                            # "different Creations Load Order" dialog: keep Current (loadorder.ps1)
           powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $here 'loadorder.ps1') -Out (Join-Path $Out 'loadorder.png') | Out-Null
           $lo = $LASTEXITCODE; if ($lo -ne 0) { $obs['load_order_dialog'] = $lo }
           if ($lo -eq 2) { $obs['stopped'] = 'input guard'; Save-Obs; exit 2 }
           if ($lo -eq 9) { break }                  # not answered: nothing confirmed, the save is not loaded
           if ($lo -eq 5) { $lo = 0 } }               # check could not run: try again on the next pass
         powershell -NoProfile -ExecutionPolicy Bypass -File $shot -Out $hud | Out-Null
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
    $script:tpCapture = [bool]$t.teleport_console      # diagnostic: each teleport's console captured (obs.teleports)
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
    if ($t.activate) {
      # activate (R05 interaction acceptance, docs/ai/test-queue.md "Activate"): the container's menu opened from the
      # console with the player as the activator, no facing and no E. One console session: "prid <ref>" selects the
      # reference, "GetIsID <base>" must reply 1 (the selection is a reference of that base; a refused prid leaves the
      # previous selection, which "activate player" would open: Codex's review of #145), and only then "activate
      # player"; the console closes and the menu opens. The whole screen is captured and OCR'd (the container's name and
      # items, read by testqueue.py activate_summary, shown and never judged), then the menu is closed with Tab. Without
      # the proof nothing is activated and obs.activate says so (selected = false, the console's text kept).
      $aref = "$($t.activate.ref)"; $abase = "$($t.activate.base)"
      if ($aref -notmatch '^[0-9A-Fa-f]{8}$' -or $abase -notmatch '^[0-9A-Fa-f]{8}$') { "bad activate"; exit 4 }
      Console-Open
      Send "type:prid $aref|key:enter|wait:400|type:GetIsID $abase|key:enter|wait:700"
      $sel = Read-Console 'activate_sel'
      # the reply "GetIsID >> 1.00": on the echo's line, or (r05_medkit_1015f: the OCR split the row) as ">> 1.00" on the
      # line after the echo "GetIsID <8 hex>"; OCR confuses l/I/1 and sometimes loses the >>. The line anchor keeps a
      # base id that starts with 1 from passing (the echo never ends in a lone 1)
      $selected = [bool]("$($sel.ocr)" -match '(?m)Get[Il1]s[Il1]D[ \t]*(?:[0-9A-Fa-f]{8}[ \t]*\r?\n[ \t]*)?(?:[>»][ \t]*[>»]?[ \t]*)?1(?:[.,][ \t]?0{1,2})?[ \t]*$')
      $obs['activate'] = [ordered]@{ ref = $aref; base = $abase; selected = $selected; sel_shot = $sel.shot; sel_ocr = $sel.ocr }
      Save-Obs
      if ($selected) {
        Send "type:activate player|key:enter|wait:400|key:grave|wait:2500"
        $aShot = Shot 'activate.png'; $aTxt = ''
        if ($aShot) {
          $aCap = Join-Path $Out 'activate.png'; $aPrep = Join-Path $Out 'activate_prep.png'
          & $env:FO4SF_PYTHON (Join-Path $here 'ocr_prep.py') $aCap $aPrep 135 12 | Out-Null
          $aTxt = ((powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $here 'ocr.ps1') -Image $aPrep -Scale 1) -join "`n")
        }
        $obs['activate']['shot'] = $aShot; $obs['activate']['ocr'] = $aTxt; Save-Obs
        # the container UI's "BACK / HOLD TO EXIT [TAB]": a tap only goes back a level (r05_medkit_1015d a1: the menu
        # stayed open and the next console open failed), a held Tab exits; a second hold if the HUD is still not back
        Send 'hold:tab,1200|wait:1500'
        $obs['activate']['closed_shot'] = Shot 'activate_closed.png'
        if ($obs['activate']['closed_shot'] -and -not (Hud-Shown 'activate_closed.png')) {
          Send 'hold:tab,1500|wait:1500'; $obs['activate']['closed_retry'] = Shot 'activate_closed2.png'
        }
      } else {
        Send 'key:grave|wait:800'                     # selection not proven: nothing activated
      }
      Save-Obs
    }
    # Unscored plan diagnostic: use the same merged frame/drop height as the judged points.
    Teleport @(([double]$t.beyond.x + $ox), ([double]$t.beyond.y + $oy), $dropz) 90 5
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
    # combat_reads (docs/ai/test-queue.md "Combat engagement"): every sample's session also asks the combat manager,
    # exactly these three lines (the same table as testqueue.py NPC_COMBAT_READS); their replies are parsed
    # defensively (parse_npc.py: formats unverified in game) and kept raw. Only with methods none / combat_player.
    $combatCmds = @('GetCombatState', 'GetCombatTarget', 'GetLineOfSight player')
    $combatReads = $false
    if ($null -ne $t.combat_reads) {
      if ($t.combat_reads -isnot [bool]) { "bad combat_reads"; exit 4 }
      $combatReads = [bool]$t.combat_reads
      if ($combatReads -and @('none', 'combat_player') -cnotcontains "$($t.method)") { "bad combat_reads method"; exit 4 }
    }
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
        elseif ($c -match '^GetIsID ([0-9A-Fa-f]{8})$') { $exp += 'isid'; $typed += $Matches[1] }
        elseif ($c -match '^getpos ([xyz])$') { $exp += $Matches[1] }
        elseif ($c -eq 'GetSelf') { $exp += 'self' } elseif ($c -eq 'GetDisabled') { $exp += 'disabled' }
        elseif ($c -eq 'GetCombatState') { $exp += 'combat' } elseif ($c -eq 'GetCombatTarget') { $exp += 'target' }
        elseif ($c -eq 'GetLineOfSight player') { $exp += 'los' }
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
    function Select-Npc([switch]$Combat) {
      # Opening the console selects what is under the crosshair (supported hypothesis: N0_base's selection was the floor
      # static 0024A824 at A and again at B), so every session selects the actor by its id (prid, the confirmed
      # PickLastRef id) and confirms it: GetIsID <npc> 1 in the same session. Returns with the console OPEN plus its
      # position, or closes the console and returns $null. A second try only repeats the session (an OCR miss).
      # -Combat: once the selection is confirmed, a second capture in the same console open (the selection stays on
      # the prid'ed ref while the console is open, as Pick-Npc's captures rely on) types ClearConsole, GetIsID <npc>
      # again and the combat reads ($combatCmds): nine lines, what the console shows. All of it in one capture would
      # scroll the GetIsID and position replies off screen (the sandbox showed that). The replies are returned as read
      # (null when not parsed); combat_isid is that capture's GetIsID (0: another ref answered, the judge drops them).
      if ("$($script:npcRef)" -cnotmatch $ffid) { return $null }
      Console-Open
      foreach ($n in 1, 2) {
        $r = Npc-Capture @("prid $($script:npcRef)", "GetIsID $npc", 'getpos x', 'getpos y', 'getpos z') @('isid', 'pos')
        if ($r -and $r.isid -eq 1) {
          $p = $null; if ("$($r.pos)" -match $num3) { $p = "$($r.pos)" }
          $o = [ordered]@{ via = 'prid'; isid = 1; read = $p; how = $r.how; ocr = $r.ocr }
          if ($Combat) {
            $c = Npc-Capture (@("GetIsID $npc") + $combatCmds) @('isid') 'npc_combat'
            $o['combat_isid'] = $c.isid; $o['combat'] = $c.combat; $o['target'] = $c.target; $o['los'] = $c.los
            $o['combat_ocr'] = $c.ocr
          }
          return $o
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
          $r = Select-Npc -Combat:$combatReads
          if ($r) { Send 'key:grave|wait:300' }
          $closedAt = Get-Date
          $smp = [ordered]@{ t_game = [math]::Round($game, 1); t_wall = [math]::Round(((Get-Date) - $cmdAt).TotalSeconds, 1)
                             isid = $(if ($r) { 1 } else { $null }); read = $(if ($r) { $r.read } else { $null })
                             via = $(if ($r) { $r.via } else { '' }); shot = (Shot "npc$k.png") }
          if ($combatReads) {
            # the combat manager's answers on the confirmed selection (parsed, else null), that capture's GetIsID and
            # its raw OCR
            $smp['combat_isid'] = $(if ($r) { $r.combat_isid } else { $null })
            $smp['combat'] = $(if ($r) { $r.combat } else { $null }); $smp['target'] = $(if ($r) { $r.target } else { $null })
            $smp['los'] = $(if ($r) { $r.los } else { $null }); $smp['combat_ocr'] = $(if ($r) { $r.combat_ocr } else { $null })
          }
          $samples += $smp
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
    # The playable slice's working door (docs/slice/redrocket-door.md, docs/slice/door-frames.md): coc into the world,
    # read the arrival until it settles (the overlay's merge offset O = arrival - spawn_local), then two legs through a
    # load door: "in" towards outside.door + O, "out" towards inside.door. A leg either
    #   - walks a route (outside.route / inside.route: waypoints from where the player stands, the coc arrival or the
    #     previous leg's arrival, to the door): no teleport; per step player.setangle z at the next waypoint, a timed W
    #     hold, a HUD check and a position read; or
    #   - (no route) teleports to the start facing the door and walks straight at it in walk_step_ms steps.
    # An automatic door loads within fAutoDoorActivateDistance (3 m in Starfield.esm) behind a fade and a loading
    # screen. E when an activation prompt shows; as a last try a teleport to the "near" point (1 m in front of the door;
    # the judge makes such a trip NEARONLY). Every read is strict (readpos -Strict: labelled values of the read's own
    # session) and a load is never taken from one read: a read far from the start needs a second far read that agrees
    # within 1 m, and a read whose axes look swapped against the last read on this side is rejected (the first live run,
    # 2026-10-13: "99.74 -2195.27 99.41" for (-2195.27, -1593.51, 99.41) ended the walk 3 m before the door). Nothing is
    # pressed or teleported unless a read put the player on this side. Then the HUD back, the arrival read until it
    # settles, with the heading (player.getangle z: the facing the door gave), and a screenshot. player.GetInCell only
    # with inside.cell_id (a form id; the EditorID is refused by the console: "Item '...' not found for parameter Cell"),
    # recorded as a diagnostic. A leg that does not arrive where expected ends the step. Then save <save> (its file must
    # appear in the Saves folder), a teleport away (back to the coc arrival: the save/load check, not the walk), load
    # <save> (the player must come back with the saved heading), the position and heading read until they settle, a
    # screenshot. With outside.ref the door's own getpos is read after the coc arrival (a diagnostic).
    # Everything typed is validated here again.
    $script:strictReads = $true
    $nameRe = '^[A-Za-z0-9_]{1,64}$'
    if ("$($t.travel)" -notmatch '^coc [A-Za-z0-9_]+$') { "bad travel"; exit 4 }
    $cell = "$($t.inside.cell)"
    if ($cell -cnotmatch $nameRe) { "bad inside.cell"; exit 4 }
    $cellId = ''
    if ($null -ne $t.inside.cell_id) {
      $cellId = "$($t.inside.cell_id)"; if ($cellId -cnotmatch '^[0-9A-Fa-f]{8}$') { "bad inside.cell_id"; exit 4 }
    }
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
    function Route($v, [string]$what) {
      # a list of 2 to 64 waypoints (x, y, z), or $null
      if ($null -eq $v) { return $null }
      $a = @($v)
      if ($a.Count -lt 2 -or $a.Count -gt 64) { "bad $what"; exit 4 }
      $out = @()
      foreach ($p in $a) { $out += ,(Vec3 $p $what) }
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
    $oRoute = Route $t.outside.route 'outside.route'; $iRoute = Route $t.inside.route 'inside.route'
    $sl = @($t.spawn_local); if ($sl.Count -lt 2 -or $sl.Count -gt 3) { "bad spawn_local"; exit 4 }
    $radius = Num $t.radius 4.0 0.5 50 'radius'
    $walkMs = [int](Num $t.walk_ms 8000 0 60000 'walk_ms'); $stepMs = [int](Num $t.walk_step_ms 500 100 5000 'walk_step_ms')
    $settle = [int](Num $t.settle_ms 6000 0 30000 'settle_ms'); $drop = Num $t.drop 0.5 0 50 'drop'
    $nearWait = [int](Num $t.near_wait_ms 6000 0 60000 'near_wait_ms'); $loadWait = [int](Num $t.load_wait_s 90 10 600 'load_wait_s')
    $hOut = Num $t.heading_out 0 0 360 'heading_out'; $hIn = Num $t.heading_in 0 0 360 'heading_in'
    $startTol = Num $t.start_tol 3.0 0.5 50 'start_tol'; $movedM = Num $t.moved_m 30.0 5 1000 'moved_m'
    $holdMax = [int](Num $t.route_hold_ms 2000 300 10000 'route_hold_ms'); $reachM = Num $t.route_reach_m 0.8 0.2 5 'route_reach_m'
    $speed0 = Num $t.route_speed 4.6 0.5 20 'route_speed'; $routeMs = [int](Num $t.route_walk_ms 60000 1000 600000 'route_walk_ms')
    $routeSteps = [int](Num $t.route_max_steps 40 2 400 'route_max_steps'); $finalMax = [int](Num $t.route_final_steps 6 1 40 'route_final_steps')
    $oRef = ''
    if ($null -ne $t.outside.ref) {
      $oRef = "$($t.outside.ref)"; if ($oRef -cnotmatch '^[0-9A-Fa-f]{8}$') { "bad outside.ref"; exit 4 }
    }
    $probeRefs = @()                                      # probes: refs whose getpos is read after the arrival
    foreach ($q in @($t.probes | Where-Object { $null -ne $_ })) {
      $rf = "$($q.ref)"; if ($rf -cnotmatch '^[0-9A-Fa-f]{8}$') { "bad probes"; exit 4 }
      $probeRefs += $rf
    }
    if ($probeRefs.Count -gt 8) { "bad probes"; exit 4 }
    $lightCmds = Light-Commands
    $preCmds = Console-List $t.console_pre 'console_pre'; $postCmds = Console-List $t.console_post 'console_post'
    $parse = Join-Path $here 'parse_npc.py'
    function Dist3([string]$read, $p) {
      if ("$read" -notmatch $pos3) { return $null }
      $v = "$read".Trim().Split(' ', [StringSplitOptions]::RemoveEmptyEntries)
      return [Math]::Sqrt([Math]::Pow([double]$v[0] - $p[0], 2) + [Math]::Pow([double]$v[1] - $p[1], 2) + [Math]::Pow([double]$v[2] - $p[2], 2))
    }
    function HDist($a, $b) { return [Math]::Sqrt([Math]::Pow($a[0] - $b[0], 2) + [Math]::Pow($a[1] - $b[1], 2)) }
    function Head($a, $b) {
      $d = [Math]::Atan2($b[0] - $a[0], $b[1] - $a[1]) * 180.0 / [Math]::PI
      if ($d -lt 0) { $d += 360.0 }
      return [Math]::Round($d, 1) % 360
    }
    function Prompt-Up([string]$png) {
      $f = Join-Path $Out $png
      if (-not (Test-Path $f)) { return $false }
      return ((& $env:FO4SF_PYTHON (Join-Path $here 'prompt_visible.py') $f) -eq 'yes')
    }
    function In-Cell([string]$tag) {
      # player.GetInCell <cell form id> in its own console session (ClearConsole first: its echo marks the session
      # start for parse_npc.py), the capture and OCR kept as <tag>_cap.png / <tag>_ocr.txt: 1, 0 or $null (not read,
      # or the console refused the cell: incell_error). Only with inside.cell_id; a diagnostic, never judged.
      if (-not $cellId) { return @{ incell = $null; ocr = ''; skipped = 'no inside.cell_id' } }
      Console-Open
      Send "type:ClearConsole|key:enter|wait:500|type:player.GetInCell $cellId|key:enter|wait:900"
      $cap = Join-Path $Out "${tag}_cap.png"; $prep = Join-Path $Out "${tag}_prep.png"; $txt = Join-Path $Out "${tag}_ocr.txt"
      powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $here 'shot_region.ps1') -Out $cap | Out-Null
      $r = $null
      foreach ($th in 135, 140, 130, 145) {
        & $env:FO4SF_PYTHON (Join-Path $here 'ocr_prep.py') $cap $prep $th 12 | Out-Null
        (powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $here 'ocr.ps1') -Image $prep -Scale 1) | Set-Content $txt -Encoding utf8
        $r = (& $env:FO4SF_PYTHON $parse $txt '--expect=incell') | ConvertFrom-Json
        if ($r -and ($null -ne $r.incell -or $r.incell_error)) { break }
      }
      Send 'key:grave|wait:600'
      return @{ incell = $(if ($r) { $r.incell } else { $null }); ocr = $(if ($r) { $r.ocr } else { '' })
                error = $(if ($r) { $r.incell_error } else { $null }) }
    }
    function Vec-Of([string]$read) {
      if ("$read" -notmatch $pos3) { return $null }
      $v = "$read".Trim().Split(' ', [StringSplitOptions]::RemoveEmptyEntries)
      return ,@([double]$v[0], [double]$v[1], [double]$v[2])
    }
    function Swapped($p, $q) {
      # a read whose axes look swapped against the last read on this side ($q): one of its values is far from the same
      # axis of $q but within 3 m of another axis of $q (the live garble put the previous z into x and x into y)
      for ($k = 0; $k -lt 3; $k++) {
        if ([Math]::Abs($p[$k] - $q[$k]) -le $movedM) { continue }
        for ($j = 0; $j -lt 3; $j++) { if ($j -ne $k -and [Math]::Abs($p[$k] - $q[$j]) -lt 3.0) { return $true } }
      }
      return $false
    }
    $script:lastGood = $null                              # the last read that put the player on this side
    function Leg-Check($L, [string]$tag, $start, $door, [int]$ms, [int]$tries) {
      # Which side of the door is the player on (after a walk step, after E, before the last-try teleport)? 'loaded':
      # the HUD is gone (a fade or a loading screen), or two consecutive reads more than moved_m from the leg's start
      # agree within 1 m (a load whose fade and loading screen both fell between two HUD checks: the two sides are
      # about 2.7 km apart); 'here': a read within moved_m of the start (then $script:lastGood), its distances kept in
      # $L.checks; 'unread': no read while the HUD is up, or a far read not confirmed. A read whose axes look swapped
      # against the last read on this side is rejected. One read never makes a load.
      if (-not (Hud-Shown "$($L['name'])_$tag.png")) { $L['load_by'] = 'hud'; return 'loaded' }
      $p = Read-Pos '' $tries
      $c = [ordered]@{ tag = $tag; ms = $ms; read = $p }
      $L['checks'] += $c
      if ("$p" -notmatch $pos3) {
        if (-not (Hud-Shown "$($L['name'])_${tag}_after.png")) { $L['load_by'] = 'hud'; return 'loaded' }
        return 'unread'
      }
      $last = Vec-Of $script:lastGood
      $ds = Dist3 $p $start
      $c['from_start'] = [Math]::Round($ds, 2); $c['to_door'] = [Math]::Round((Dist3 $p $door), 2)
      $far = $p
      if ($null -ne $last -and (Swapped (Vec-Of $p) $last)) { $c['rejected'] = 'axes swapped'; $far = $null }
      elseif ($ds -le $movedM) { $script:lastGood = $p; return 'here' }
      for ($n = 0; $n -lt 2; $n++) {                      # confirm: up to two more reads
        $q = Read-Pos '' 3
        $cq = [ordered]@{ tag = "${tag}_confirm"; ms = $ms; read = $q }
        $L['checks'] += $cq
        if ("$q" -notmatch $pos3) { continue }
        $dq = Dist3 $q $start
        $cq['from_start'] = [Math]::Round($dq, 2); $cq['to_door'] = [Math]::Round((Dist3 $q $door), 2)
        if ($null -ne $last -and (Swapped (Vec-Of $q) $last)) { $cq['rejected'] = 'axes swapped'; $far = $null; continue }
        if ($dq -le $movedM) {
          if ($null -ne $far) { $c['rejected'] = 'not confirmed' }
          $script:lastGood = $q; return 'here'
        }
        if ($null -ne $far -and (Dist3 $q (Vec-Of $far)) -le 1.0) { $L['load_by'] = 'position'; $cq['confirms'] = $true; return 'loaded' }
        $far = $q
      }
      if (-not $c.Contains('rejected')) { $c['rejected'] = 'not confirmed' }
      return 'unread'
    }
    function Turn([double]$h, [bool]$pitch) {
      # face heading $h (degrees clockwise from north) in one console session; the pitch once per leg
      Console-Open
      $seq = "type:player.setangle z $(F $h)|key:enter|wait:350|"
      if ($pitch) { $seq += "type:player.setangle x 10|key:enter|wait:350|" }
      Send ($seq + "key:grave|wait:900")
    }
    function Route-Walk($L, $wps, $start, $door) {
      # Walk the waypoints from where the player stands: steer at the next waypoint not yet reached (within
      # route_reach_m, or passed along its leg), hold W for the time the remaining distance needs at the speed the last
      # step showed (at most route_hold_ms), check; after the last waypoint steer at the door itself in walk_step_ms
      # steps (at most route_final_steps). Ends on a load, two steps without 0.2 m of progress, a position not read
      # twice, or the budget (route_walk_ms of W, route_max_steps). Returns the leg state.
      $cur = Vec-Of $L['start_read']; $k = 1; $walked = 0; $steps = 0; $still = 0; $finals = 0
      $speed = $speed0; $lastH = $null; $L['steps'] = @()
      while ($true) {
        if ($walked -ge $routeMs -or $steps -ge $routeSteps) { $L['walk_stopped'] = 'route budget used up'; return 'here' }
        while ($k -lt $wps.Count) {                        # waypoints reached or passed
          $a = $wps[$k - 1]; $b = $wps[$k]; $len = HDist $a $b
          $along = $(if ($len -gt 0) { (($cur[0] - $a[0]) * ($b[0] - $a[0]) + ($cur[1] - $a[1]) * ($b[1] - $a[1])) / $len } else { 0 })
          if ((HDist $cur $b) -le $reachM -or $along -ge $len - 0.3) { $k++ } else { break }
        }
        $final = $k -ge $wps.Count
        if ($final) { $finals++; if ($finals -gt $finalMax) { $L['walk_stopped'] = 'at the door, no load'; return 'here' } }
        $tgt = $(if ($final) { $door } else { $wps[$k] })
        $dist = HDist $cur $tgt
        $h = Head $cur $tgt
        if ($null -eq $lastH -or [Math]::Abs(((($h - $lastH) % 360) + 540) % 360 - 180) -gt 3) { Turn $h ($null -eq $lastH); $lastH = $h }
        $ms = $(if ($final) { $stepMs } else { [int][Math]::Min($holdMax, [Math]::Max(300, $dist / $speed * 1000)) })
        Send "hold:w,$ms|wait:250"
        $walked += $ms; $steps++
        $L['walked_ms'] = $walked
        $state = Leg-Check $L 'walk' $start $door $walked 1
        if ($state -eq 'unread') { $state = Leg-Check $L 'reread' $start $door $walked 3 }
        $L['steps'] += [ordered]@{ wp = $k; heading = $h; ms = $ms; state = $state; read = $(if ($state -eq 'here') { $script:lastGood } else { $null }) }
        if ($state -eq 'loaded') { return 'loaded' }
        if ($state -eq 'unread') { $L['walk_stopped'] = 'position unread'; return 'unread' }
        $new = Vec-Of $script:lastGood
        $moved = HDist $cur $new
        if ($moved -lt 0.2) { $still++ } else { $still = 0; $speed = [Math]::Min(8.0, [Math]::Max(1.5, $moved / ($ms / 1000.0))) }
        $cur = $new
        if ($still -ge 2) { $L['walk_stopped'] = 'no progress in two steps'; return 'here' }
      }
    }
    function Door-Leg([string]$name, $start, $door, $near, [double]$heading, $route) {
      # With a route: start where the player stands (no teleport) and walk it (Route-Walk). Without: teleport to the
      # start facing the door, walk straight at it in walk_step_ms steps. Both: E only when a prompt showed, the
      # last-try teleport to "near" only after a read put the player on this side (a load the HUD checks missed must
      # never be followed by a teleport to this side's coordinates in the other cell).
      $L = [ordered]@{ name = $name; start_target = $start; door = $door; checks = @(); mode = $(if ($route) { 'route' } else { 'straight' }); teleports = 0 }
      if ($route) {
        $L['route'] = $route
        $L['start_read'] = Read-Pos '' 3
      } else {
        Teleport @($start[0], $start[1], ($start[2] + $drop)) $heading 10
        $L['teleports'] = 1
        Start-Sleep -Milliseconds $settle
        $L['start_read'] = Read-Pos
      }
      $L['start_shot'] = Shot "${name}_start.png"
      $L['prompt'] = Prompt-Up "${name}_start.png"
      $walked = 0; $trig = ''; $act = 'walk'; $state = 'unread'
      $sv0 = Vec-Of $L['start_read']
      $script:lastGood = $L['start_read']
      $go = $false
      if ($null -eq $sv0) { $L['walk_skipped'] = 'the start was not read' }
      elseif ([Math]::Sqrt([Math]::Pow($sv0[0] - $start[0], 2) + [Math]::Pow($sv0[1] - $start[1], 2)) -gt $startTol) {
        $L['walk_skipped'] = 'the start read is not at the start'
      } else { $go = $true; $state = 'here' }
      if ($go -and $route) {
        $state = Route-Walk $L $route $start $door
        $walked = [int]$L['walked_ms']
        if ($state -eq 'loaded') { $trig = 'walk' }
      } elseif ($go) {
        $prev = $sv0; $still = 0
        while ($walked -lt $walkMs) {                     # walk at the door
          $ms = [Math]::Min($stepMs, $walkMs - $walked)
          Send "hold:w,$ms|wait:250"
          $walked += $ms
          $state = Leg-Check $L 'walk' $start $door $walked 1
          if ($state -eq 'unread') { $state = Leg-Check $L 'reread' $start $door $walked 3 }
          if ($state -eq 'loaded') { $trig = 'walk'; break }
          if ($state -eq 'unread') { $L['walk_stopped'] = 'position unread'; break }
          if (-not $L['prompt'] -and (Prompt-Up "${name}_walk.png")) { $L['prompt'] = $true }
          $cur = Vec-Of $script:lastGood
          if ($null -ne $prev -and (HDist $cur $prev) -lt 0.2) { $still++ } else { $still = 0 }
          $prev = $cur
          if ($still -ge 2) { $L['walk_stopped'] = 'no progress in two steps'; break }
        }
      }
      if ($go) {
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
            Teleport @($near[0], $near[1], ($near[2] + $drop)) (Head $near $door) 10
            $L['teleports'] += 1
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
      $arr = Read-Settled 5 3000 $true
      $L['arrival_read'] = $arr.read; $L['arrival_settled'] = $arr.settled; $L['arrival_reads'] = $arr.reads
      $L['arrival_heading'] = $arr.heading; $L['arrival_headings'] = $arr.headings
      if ($go -and -not $loaded -and "$($arr.read)" -match $pos3 -and (Dist3 $arr.read $start) -gt $movedM) {
        $L['trigger'] = $act; $L['load_by'] = 'position'     # a load after the last action: two settled reads agree
      }
      $c = In-Cell "${name}_cell"
      $L['incell'] = $c.incell; $L['incell_ocr'] = $c.ocr; $L['incell_error'] = $c.error
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
    if ($probeRefs.Count -gt 0) {                        # the merge probes: which storage the overlay merge moves
      $pr = @()
      foreach ($rf in $probeRefs) { $pr += [ordered]@{ ref = $rf; read = (Read-Pos $rf) } }
      $obs['probe_reads'] = $pr; Save-Obs
    }
    function Plus($p, $o) { if ($null -eq $p) { return $null }; return @(($p[0] + $o[0]), ($p[1] + $o[1]), ($p[2] + $o[2])) }
    $oRouteM = $null
    if ($oRoute) { $oRouteM = @(); foreach ($p in $oRoute) { $oRouteM += ,(Plus $p $O) } }
    # 2. in: through the door in the world, into the interior (with a route: walked from the coc arrival)
    $inStart = $(if ($oRoute) { $oRouteM[0] } else { Plus $oStart $O })
    $legIn = Door-Leg 'in' $inStart (Plus $oDoor $O) (Plus $oNear $O) $hOut $oRouteM
    $obs['legs'] = @($legIn); Save-Obs
    $d = Dist3 $legIn['arrival_read'] $iArr
    if ($null -eq $d -or $d -gt $radius) { Save-Obs; exit 0 }
    # 3. out: through the interior door, back onto the terrain (the merged frame); with a route: walked from the
    # interior arrival
    $outStart = $(if ($iRoute) { $iRoute[0] } else { $iStart })
    $legOut = Door-Leg 'out' $outStart $iDoor $iNear $hIn $iRoute
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
    # 5. away from the saved spot (back to the settled coc arrival, facing north: the save/load check, not the walk),
    # then load it: the load must bring the player back with the saved heading, so the position shows it even when no
    # HUD check saw the loading screen
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
    $r2 = Read-Settled 5 3000 $true
    $R['read'] = $r2.read; $R['settled'] = $r2.settled; $R['reads'] = $r2.reads
    $R['heading'] = $r2.heading; $R['headings'] = $r2.headings
    $c = In-Cell 'reload_cell'; $R['incell'] = $c.incell; $R['incell_ocr'] = $c.ocr; $R['incell_error'] = $c.error
    $R['shot'] = Shot 'reload.png'
    $obs['reload'] = $R
  }
  'walk' {
    # A continuous walk (docs/terrain/walk-redrocket-sanctuary.md; the controller and the judge are walk_eval.py): coc,
    # the arrival read until it settles (the overlay's merge offset O = arrival - spawn_local), for a test with "setup"
    # ONE teleport to the route's start before the walk begins (setup, not walking evidence), then legs until the
    # controller says done or stop. A leg: one console session (ClearConsole, player.getpos x / y / z, the console OCR'd
    # with parse_npc.py; a failed read is read again in a fresh session, Walk-Session), the controller's decision on that read (walk_eval.py
    # steer), "player.setangle z <heading>" typed in the same session, the console closed, W held for hold_ms
    # (input.ps1 holdg: released at once when the game loses the foreground), then one screenshot: the HUD
    # (hud_visible.py; gone -> wait up to 20 s for it) and the screen centre's text (ocr.ps1: "BOUNDARY REACHED" stops the
    # walk; nothing is pressed to close it). Every leg records the console lines it typed: during the walk only
    # ClearConsole, player.getpos and player.setangle, never a setpos (the judge checks). A screenshot is kept every
    # shot_every legs and at every event. Everything typed is validated here again.
    # The owner's stop controls (spec.stop, testqueue.py stop_controls: the runner's STOP files and the Resource
    # Guardian) are honoured inside the walk: the files before every action (Walk-Stop) and during the hold (input.ps1
    # holdg, FO4SF_STOP_FILES), the Guardian once per leg (walk_eval.py steer). A stop ends the step like a guard stop:
    # exit 2, nothing more typed, obs.json with the legs so far and `stopped` (the runner counts no attempt).
    if ("$($t.travel)" -notmatch '^coc [A-Za-z0-9_]+$') { "bad travel"; exit 4 }
    function Num-W($v, [double]$def, [double]$lo, [double]$hi, [string]$what) {
      if ($null -eq $v) { return $def }
      if ($v -is [bool] -or $v -is [string]) { "bad $what"; exit 4 }
      $d = [double]$v; if ([double]::IsNaN($d) -or $d -lt $lo -or $d -gt $hi) { "bad $what"; exit 4 }
      return $d
    }
    function Vec-W($v, [int[]]$sizes, [string]$what) {
      $a = @($v)
      if ($sizes -notcontains $a.Count) { "bad $what"; exit 4 }
      $out = @()
      foreach ($x in $a) {
        if ($x -isnot [double] -and $x -isnot [int] -and $x -isnot [long] -and $x -isnot [decimal]) { "bad $what"; exit 4 }
        $d = [double]$x; if ([double]::IsNaN($d) -or [double]::IsInfinity($d) -or [Math]::Abs($d) -gt 1e6) { "bad $what"; exit 4 }
        $out += $d
      }
      return ,$out
    }
    $sl = Vec-W $t.spawn_local @(2, 3) 'spawn_local'
    $wps = @($t.waypoints)
    if ($wps.Count -lt 2 -or $wps.Count -gt 400) { "bad waypoints"; exit 4 }
    $W = @(); foreach ($w in $wps) { $W += ,(Vec-W $w @(4, 5) 'waypoint') }      # x, y, z, reach[, keep]
    $start = Vec-W $t.start @(3) 'start'
    $maxLegs = [int](Num-W $t.max_legs 60 1 400 'max_legs'); $shotEvery = [int](Num-W $t.shot_every 3 1 50 'shot_every')
    $drop = Num-W $t.drop 1.0 0 50 'drop'; $settle = [int](Num-W $t.settle_ms 6000 0 30000 'settle_ms')
    if ($null -ne $t.setup -and $t.setup -isnot [bool]) { "bad setup"; exit 4 }
    $stopFiles = @()
    if ($null -ne $t.stop -and $null -ne $t.stop.files) {
      foreach ($f in @($t.stop.files)) { if ($f -isnot [string] -or -not $f) { "bad stop.files"; exit 4 }; $stopFiles += $f }
    }
    $env:FO4SF_STOP_FILES = ($stopFiles -join ';')        # input.ps1 holdg checks them while W is down
    $lightCmds = Light-Commands
    $preCmds = Console-List $t.console_pre 'console_pre'; $postCmds = Console-List $t.console_post 'console_post'
    $wpy = Join-Path $here 'walk_eval.py'; $parse = Join-Path $here 'parse_npc.py'
    $state = Join-Path $Out 'walk_state.json'
    $stepStart = Get-Date
    $budget = if ($t.budget_s) { [double]$t.budget_s } else { 1e9 }
    function Walk-Left { $budget - ((Get-Date) - $stepStart).TotalSeconds }
    function Walk-Read {
      # console OPEN: ClearConsole (its echo marks this session's start for parse_npc.py) and the three getpos; returns
      # "x y z" or $null, the console stays open. parse_npc.py reads nothing before this session's start and gives a
      # position only when all three values are this session's ($script:readHow: its reading, "order" / "inline").
      if ($script:bridge) { $script:readHow = 'bridge'; return (Bridge-Read $false 1) }   # no console session at all
      Send 'type:ClearConsole|key:enter|wait:500|type:player.getpos x|key:enter|wait:450|type:player.getpos y|key:enter|wait:450|type:player.getpos z|key:enter|wait:700'
      $script:legCmds += @('ClearConsole', 'player.getpos x', 'player.getpos y', 'player.getpos z')
      $cap = Join-Path $Out 'walk_cap.png'; $prep = Join-Path $Out 'walk_prep.png'; $txt = Join-Path $Out 'walk_ocr.txt'
      powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $here 'shot_region.ps1') -Out $cap | Out-Null
      $script:readHow = ''
      foreach ($th in 135, 140, 130, 145) {
        & $env:FO4SF_PYTHON (Join-Path $here 'ocr_prep.py') $cap $prep $th 12 | Out-Null
        (powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $here 'ocr.ps1') -Image $prep -Scale 1) | Set-Content $txt -Encoding utf8
        $r = $null
        try { $r = (& $env:FO4SF_PYTHON $parse $txt '--expect=x,y,z') | ConvertFrom-Json } catch { $r = $null }
        if ($r -and "$($r.pos)" -match $pos3) { $script:readHow = "$($r.how)"; return "$($r.pos)".Trim() }
      }
      return $null
    }
    function Walk-Session([int]$tries) {
      # console CLOSED before and after: up to $tries fresh sessions of the same ClearConsole-marked read (a failed
      # first read, the second read of an implausible move). Never readpos.ps1: its parse_getpos.py takes the last X,
      # Y and Z anywhere on screen, so a capture missing this session's Z joined the current x / y with an older
      # session's z (Codex on PR #103); here all three values come from one current session or there is no read.
      if ($script:bridge) {
        for ($k = 0; $k -lt $tries; $k++) { $p = Walk-Read; if ($p) { return $p }; Start-Sleep -Milliseconds 400 }
        return $null
      }
      for ($k = 0; $k -lt $tries; $k++) {
        Console-Open
        $p = Walk-Read
        Send 'key:grave|wait:600'
        if ($p) { return $p }
        Start-Sleep -Milliseconds 400
      }
      return $null
    }
    function Steer([string]$read, [bool]$again = $false) {
      # walk_eval.py steer: the next action for this read ("none" when unread); $null when it gave no answer
      $rd = $(if ($read) { $read } else { 'none' })
      $a = @($wpy, 'steer', '--spec', $Spec, '--state', $state, "--read=$rd")
      if ($again) { $a += '--reread' }
      $j = & $env:FO4SF_PYTHON @a
      try { return ("$j" | ConvertFrom-Json) } catch { return $null }
    }
    function Popup-Text([string]$png) {
      # the screen centre's text (the "BOUNDARY REACHED" box sits there and leaves the HUD on screen, 2026-10-12)
      $f = Join-Path $Out $png
      if (-not (Test-Path $f)) { return '' }
      return ((powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $here 'ocr.ps1') -Image $f -X 320 -Y 150 -W 640 -H 330 -Scale 2) -join ' ')
    }
    function Walk-Stop {
      # the first STOP file of the spec that exists (cheap: tested before every action of a leg), else ''
      foreach ($f in $stopFiles) { if (Test-Path -LiteralPath $f) { return "STOP file $f" } }
      return ''
    }
    function Stop-Walk([string]$why, $L) {
      # a stop control tripped: the unfinished leg and the reason go into obs.json, nothing more is typed, exit 2
      $L['action'] = 'stop'; $L['reason'] = 'stopped'; $L['cmds'] = $script:legCmds
      $obs['legs'] = @($legs) + @($L); $obs['walk_stopped'] = 'stopped'; $obs['stopped'] = $why
      Save-Obs; exit 2
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
    $O = @(([double]$sv[0] - $sl[0]), ([double]$sv[1] - $sl[1]), 0.0)
    if ($sl.Count -ge 3) { $O[2] = [double]$sv[2] - $sl[2] }
    $obs['offset'] = $O; $obs['offset_from'] = 'spawn'
    Save-Obs
    # 2. setup (the reverse test): one teleport to the route's start, facing the next waypoint, before the walk
    if ($t.setup) {
      $h0 = ([Math]::Atan2($W[1][0] - $W[0][0], $W[1][1] - $W[0][1]) * 180.0 / [Math]::PI + 360.0) % 360.0
      $tgt = @(($start[0] + $O[0]), ($start[1] + $O[1]), ($start[2] + $O[2]))
      Teleport @($tgt[0], $tgt[1], ($tgt[2] + $drop)) $h0 5
      Start-Sleep -Milliseconds $settle
      $s2 = Read-Settled
      $obs['setup'] = [ordered]@{ target = $tgt; read = $s2.read; settled = $s2.settled; reads = $s2.reads; shot = (Shot 'setup.png') }
      Save-Obs
      if (-not $s2.settled -or "$($s2.read)" -notmatch $pos3) { exit 0 }
    }
    # 3. the walk
    $init = & $env:FO4SF_PYTHON $wpy init --spec $Spec --state $state "--offset=$(F $O[0]) $(F $O[1]) $(F $O[2])"
    if ("$init" -notmatch '"init"') { $obs['walk_stopped'] = 'steer'; $obs['steer_init'] = "$init"; Save-Obs; exit 0 }
    $legs = @(); $n = 0; $walkStart = Get-Date; $pitched = $false; $stopReason = ''
    while ($true) {
      if ((Walk-Left) -lt 150) { $stopReason = 'budget'; break }
      $script:legCmds = @()
      $L = [ordered]@{ n = $n; t = [Math]::Round(((Get-Date) - $walkStart).TotalSeconds, 1) }
      $why = Walk-Stop; if ($why) { Stop-Walk $why $L }
      if ($script:bridge) {                                # the bridge: no console session for the read
        $open = $false
        $p = Walk-Session 3; $L['via'] = 'bridge'; $L['read_how'] = $script:readHow
      } else {
        Console-Open
        $open = $true
        $p = Walk-Read; $L['via'] = 'console'; $L['read_how'] = $script:readHow
        if (-not $p) { Send 'key:grave|wait:600'; $open = $false; $p = Walk-Session 2; $L['via'] = 'console_retry'; $L['read_how'] = $script:readHow }
      }
      $L['read'] = $p
      $d = Steer $p
      if ($d -and $d.action -eq 'reread') {
        if ($open) { Send 'key:grave|wait:600'; $open = $false }
        Start-Sleep -Milliseconds 500
        $p2 = Walk-Session 2
        $L['reread'] = $p2; $L['reread_why'] = "$($d.reason)"; $L['reread_via'] = $(if ($script:bridge) { 'bridge' } else { 'console' }); $L['reread_how'] = $script:readHow
        $d = Steer $p2 $true
        if ($d -and ($d.action -in 'aim', 'done' -or "$($d.reason)" -eq 'jump')) { $L['used'] = $p2 }
        $L['confirmed'] = [bool]($d -and $d.confirmed)
      } elseif ($p) { $L['used'] = $p }
      if (-not $d) { if ($open) { Send 'key:grave|wait:600' }; $L['action'] = 'stop'; $L['reason'] = 'steer'; $L['cmds'] = $script:legCmds
                     $legs += $L; $obs['legs'] = $legs; $stopReason = 'steer'; break }
      if ("$($d.reason)" -eq 'stopped') { Stop-Walk "$($d.stopped)" $L }       # a STOP file or the Guardian (steer)
      $L['action'] = "$($d.action)"; $L['reason'] = "$($d.reason)"; $L['wp'] = $d.wp; $L['local'] = $d.local
      $event = $false
      if ($d.action -eq 'aim') {
        $h = [double]$d.heading; $hold = [int]$d.hold_ms
        if ([double]::IsNaN($h) -or $h -lt 0 -or $h -gt 360 -or $hold -lt 100 -or $hold -gt 10000) { "bad steer answer"; exit 4 }
        if (-not $open) { Console-Open; $open = $true }
        $cmd = "player.setangle z $(([Math]::Round($h, 1)).ToString('0.#', $inv))"
        $seq = "type:$cmd|key:enter|wait:300"
        $script:legCmds += $cmd
        if (-not $pitched) { $seq += '|type:player.setangle x 5|key:enter|wait:300'; $script:legCmds += 'player.setangle x 5'; $pitched = $true }
        Send "$seq|key:grave|wait:500"; $open = $false
        $L['heading'] = $h; $L['hold_ms'] = $hold; $L['dist'] = $d.dist; $L['detour'] = [bool]$d.detour; $L['speed'] = $d.speed
        $why = Walk-Stop; if ($why) { Stop-Walk $why $L }
        $obs['legs'] = @($legs) + @($L)                   # a stop during the hold (Send) keeps this leg's state
        Send "holdg:w,$hold|wait:500"
        # the screen after the walk: HUD and popup
        $up = Hud-Shown 'walk_last.png'
        $L['hud'] = [bool]$up
        $pop = Popup-Text 'walk_last.png'
        if ($pop -match 'BOUNDARY|REACHED|FAST TRAVEL|PLANET MAP') { $L['popup'] = "$pop".Trim(); $event = $true }
        if (-not $up) {
          $event = $true
          $keep = Join-Path $Out ('walk_{0:D3}_nohud.png' -f $n); Copy-Item (Join-Path $Out 'walk_last.png') $keep -ErrorAction SilentlyContinue
          $wb = Wait-Hud 20 'walk_hud.png'; $L['hud_gap_s'] = $wb.secs; $L['hud_back'] = [bool]$wb.up
        }
        if ($d.detour) { $event = $true }
        if ((($n % $shotEvery) -eq 0) -or $event) {
          $name = 'walk_{0:D3}.png' -f $n
          Copy-Item (Join-Path $Out 'walk_last.png') (Join-Path $Out $name) -ErrorAction SilentlyContinue
          if (Test-Path (Join-Path $Out $name)) { $L['shot'] = $name }
        }
      } elseif ($open) { Send 'key:grave|wait:600'; $open = $false }
      $L['cmds'] = $script:legCmds
      $legs += $L; $obs['legs'] = $legs; Save-Obs        # after every leg: a cut-off keeps what was read
      if ($d.action -ne 'aim') { $stopReason = "$($d.reason)"; break }
      if ($L['popup'] -and "$($L['popup'])" -match 'BOUNDARY|REACHED') { $stopReason = 'boundary'; break }
      if ($L['hud'] -eq $false -and -not $L['hud_back']) { $stopReason = 'nohud'; break }
      $n++
    }
    $obs['walk_stopped'] = $stopReason
    $obs['walk_s'] = [int]((Get-Date) - $walkStart).TotalSeconds
    $obs['end_shot'] = Shot 'end.png'
    $obs['step_s'] = [int]((Get-Date) - $stepStart).TotalSeconds
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
