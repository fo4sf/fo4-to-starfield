# One queued in-game test step for testqueue.py: performs the actions, writes raw observations, judges nothing.
# usage: qstep.ps1 -Spec <test.json> -Out <test dir>      (Starfield in front, in the test's cell, console closed)
# Writes <Out>\obs.json. Every key press goes through input.ps1's foreground guard; testqueue.py sets
# FO4SF_NO_FOCUS_STEAL=1, so a guard stop (the owner switched windows) ends the step with exit 2 and nothing more is sent.
# Exit 0: observations written (they may still be incomplete: the judge decides). 2: input guard. 3: console could not be
# opened safely (nothing typed). 4: bad spec.
# Kinds (spec.kind): route (stairs/door, via route_run.ps1), fall (drop onto a floor point), movable (walk into an item and
# read its position before and after), travel (activate a load door, read where the player arrives), godmode, save, load.
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
  powershell -NoProfile -ExecutionPolicy Bypass -File $i -Seq $seq | Out-Null
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
    foreach ($p in $t.points) {
      Teleport @($p.x, $p.y, $t.drop_z) 0 15
      Start-Sleep -Milliseconds 4500                 # a fall from 80 m takes about 4 s
      $pts += [ordered]@{ label = $p.label; read = (Read-Pos); shot = (Shot "pt$k.png") }
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
    $obs['hud_after'] = Hud-Up
    $obs['shot'] = Shot 'recover.png'
  }
  default { "unknown kind $($t.kind)"; exit 4 }
}
Save-Obs
exit 0
