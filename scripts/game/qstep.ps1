# One queued in-game test step for testqueue.py: performs the actions, writes raw observations, judges nothing.
# usage: qstep.ps1 -Spec <test.json> -Out <test dir>      (Starfield in front, in the test's cell, console closed)
# Writes <Out>\obs.json. Every key press goes through input.ps1's foreground guard; testqueue.py sets
# FO4SF_NO_FOCUS_STEAL=1, so a guard stop (the owner switched windows) ends the step with exit 2 and nothing more is sent.
# Exit 0: observations written (they may still be incomplete: the judge decides). 2: input guard. 3: console could not be
# opened safely (nothing typed). 4: bad spec.
# Kinds (spec.kind): route (stairs/door, via route_run.ps1), fall (drop onto a floor point), movable (walk into an item and
# read its position before and after), travel (activate a load door, read where the player arrives), terrain (drop onto
# points of known height), npc_nav (spawn a vanilla actor at A, make it walk to the player at B, sample, remove it),
# godmode, save, load, recover.
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
function Read-Pos([string]$ref = '') {
  # up to 3 reads: OCR sometimes drops or shifts a column; a read with x == z or a missing value is retried
  $p = 'fail'
  for ($n = 0; $n -lt 3; $n++) {
    if ($ref) { $p = powershell -NoProfile -ExecutionPolicy Bypass -File $readpos -Ref $ref } else { $p = powershell -NoProfile -ExecutionPolicy Bypass -File $readpos }
    if ("$p" -like 'fail guard*') { $obs['stopped'] = 'input guard'; Save-Obs; exit 2 }
    $v = "$p".Trim().Split(' ', [StringSplitOptions]::RemoveEmptyEntries)
    if ($v.Count -eq 3 -and $v[0] -ne $v[2]) { return "$p".Trim() }
  }
  return $null
}
function Shot($name) { $f = Join-Path $Out $name; powershell -NoProfile -ExecutionPolicy Bypass -File $shot -Out $f | Out-Null; if (Test-Path $f) { return $name } else { return $null } }
function F($x) { ([double]$x).ToString('0.###', $inv) }
function Teleport($pos, $heading, $pitch = 10) {
  Console-Open
  Send ("type:player.setpos x $(F $pos[0])|key:enter|wait:350|type:player.setpos y $(F $pos[1])|key:enter|wait:350|" +
        "type:player.setpos z $(F $pos[2])|key:enter|wait:350|type:player.setangle z $(F $heading)|key:enter|wait:350|" +
        "type:player.setangle x $pitch|key:enter|wait:400|key:grave|wait:1800")
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
      Teleport @($tx, $ty, $dropz) 0 15
      Start-Sleep -Milliseconds $settle               # a fall from 80 m takes about 4 s on Earth gravity
      $rd = Read-Pos
      # still hanging at the drop height: the cells around a far point were not loaded yet (exp3 2026-10-11 read 170.00
      # at points ~700 m from the arrival); wait and read again, twice at most
      for ($w = 0; $w -lt 2 -and "$rd" -match '^\s*\S+\s+\S+\s+(-?\d+(\.\d+)?)\s*$' -and [Math]::Abs([double]$Matches[1] - $dropz) -lt 0.05; $w++) {
        Start-Sleep -Milliseconds 8000; $rd = Read-Pos
      }
      $pts += [ordered]@{ label = $p.label; read = $rd; shot = (Shot "pt$k.png") }
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
    # A, order it to walk to the player standing at B, sample where it is, remove it. Commands that act on the console
    # selection (the walk command, disable, markfordelete) are typed only in a console session in which the game has
    # just confirmed the selection (GetIsID <npc> read 1 by OCR). Everything typed is validated here again.
    $hex8 = '^[0-9A-Fa-f]{8}$'
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
    $parse = Join-Path $here 'parse_npc.py'
    # step budget (testqueue.py step_timeout minus a margin): samples stop early so that the removal always has
    # $reserve seconds left before the runner would kill the step and leave the actor behind
    $stepStart = Get-Date
    $budget = if ($t.budget_s) { [double]$t.budget_s } else { 1e9 }
    $reserve = 300.0
    function Left-S { $budget - ((Get-Date) - $stepStart).TotalSeconds }
    function Npc-Capture([string[]]$cmds, [string[]]$need) {
      # console open: clear its log (ClearConsole), type the commands, OCR this session's replies (parse_npc.py, told
      # which values the commands produce, in typing order, so the column layout of the OCR reads too)
      $seq = 'type:ClearConsole|key:enter|wait:500'
      foreach ($c in $cmds) { $seq += "|type:$c|key:enter|wait:600" }
      Send "$seq|wait:400"
      $exp = @(); $typed = @()
      foreach ($c in $cmds) {
        if ($c -like 'GetIsID *') { $exp += 'isid' } elseif ($c -match '^getpos ([xyz])$') { $exp += $Matches[1] }
        elseif ($c -eq 'GetSelf') { $exp += 'self' } elseif ($c -eq 'GetDisabled') { $exp += 'disabled' }
        elseif ($c -match '^prid ([0-9A-Fa-f]{8})$') { $typed += $Matches[1] }
      }
      $cap = Join-Path $Out 'npc_cap.png'; $prep = Join-Path $Out 'npc_prep.png'; $txt = Join-Path $Out 'npc_ocr.txt'
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
    $script:npcRef = $null                            # FFxxxxxx from GetSelf; used only while the game confirms it
    function Select-Npc {
      # Opens the console and selects the actor: by its id, by the console selection as it is, or by PickLastRef. Returns
      # with the console OPEN and the actor confirmed (GetIsID 1 in this session) plus its position, or closes the
      # console and returns $null.
      Console-Open
      $tries = @(); if ($script:npcRef) { $tries += "prid $($script:npcRef)" }; $tries += 'selection'; $tries += 'plr'
      foreach ($how in $tries) {
        $cmds = @(); if ($how -ne 'selection') { $cmds += $how }
        $cmds += "GetIsID $npc", 'getpos x', 'getpos y', 'getpos z'
        $r = Npc-Capture $cmds @('isid', 'pos')
        if ($r -and $r.isid -eq 1) {
          $p = $null; if ("$($r.pos)" -match $num3) { $p = "$($r.pos)" }
          return [ordered]@{ via = $how.Split(' ')[0]; isid = 1; read = $p; how = $r.how; ocr = $r.ocr }
        }
      }
      Send 'key:grave|wait:600'
      return $null
    }
    function Read-Settled([int]$tries = 5, [int]$gapMs = 3000) {
      # the arrival, read until two reads 3 s apart agree within 0.3 m: exp1d (2026-10-11) read it mid-fall (z -500)
      $prev = Read-Pos; $reads = @("$prev")
      for ($n = 1; $n -lt $tries; $n++) {
        Start-Sleep -Milliseconds $gapMs
        $cur = Read-Pos; $reads += "$cur"
        if ("$prev" -match $num3 -and "$cur" -match $num3) {
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

    # 1. travel (coc <cell editor id>: the console travel that works), wait for the HUD, read the arrival until it stops
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
    # feet: placeatme, PickLastRef selects it, GetIsID confirms it, GetSelf may give its id
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
    $s1 = Npc-Capture @("player.placeatme $npc 1", 'plr', "GetIsID $npc", 'GetSelf') @('isid')
    $obs['spawn'] = [ordered]@{ isid = $s1.isid; self = $s1.self; how = $s1.how; ocr = $s1.ocr }
    $spawnSelf = $null                                # the runtime id PickLastRef gave right after placeatme
    if ("$($s1.self)" -match '^FF[0-9A-F]{6}$') { $spawnSelf = "$($s1.self)" }
    if ($s1.isid -eq 1) {
      $script:npcRef = $spawnSelf
      $s2 = Npc-Capture @("GetIsID $npc", 'getpos x', 'getpos y', 'getpos z') @('isid', 'pos')
      if ($s2.isid -eq 1 -and "$($s2.pos)" -match $num3) { $obs['spawn']['read'] = "$($s2.pos)" }
    }
    Send 'key:grave|wait:600'
    $obs['spawn_shot'] = Shot 'spawn.png'
    Save-Obs
    if ($s1.isid -eq 1) {
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
    # 7. remove the actor so no test leaves an NPC behind: disable + markfordelete, only on a confirmed selection (an
    # unconfirmed spawn may still have created one: PickLastRef finds it). When GetIsID never read 1 (e.g. a leveled
    # actor whose base differs), the runtime id read right after placeatme is used, if GetSelf reads it back and the
    # ref stands within 40 m of A or B (a lossy or stale id must not disable someone else's ref).
    $clean = [ordered]@{ removed = $false }
    $sel = Select-Npc
    if (-not $sel -and $spawnSelf) {
      Console-Open
      $r = Npc-Capture @("prid $spawnSelf", 'GetSelf', 'getpos x', 'getpos y', 'getpos z') @('self', 'pos')
      $near = $false
      if ("$($r.pos)" -match $num3) {
        $v = "$($r.pos)".Trim().Split(' ', [StringSplitOptions]::RemoveEmptyEntries)
        $da = [Math]::Sqrt([Math]::Pow([double]$v[0] - $ax, 2) + [Math]::Pow([double]$v[1] - $ay, 2))
        $db = [Math]::Sqrt([Math]::Pow([double]$v[0] - $bx, 2) + [Math]::Pow([double]$v[1] - $by, 2))
        $near = [Math]::Min($da, $db) -lt 40
      }
      $clean['by_id'] = [ordered]@{ self = $r.self; read = $r.pos; near = $near }
      if ("$($r.self)" -eq $spawnSelf -and $near) { $sel = [ordered]@{ via = 'id' } } else { Send 'key:grave|wait:600' }
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
