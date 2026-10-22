# Door round trips through the scripted load doors on the installed set (v6e by default). Cloud thread 2026-10-21;
# run on v6i 2026-10-22 as -Tag v6ib (Card J).
# Planner: scripts/bridge/door_rounds.py (docs/terrain/door-rounds.md), the one the v6c door queues used; judge: the same.
# Two queues from ONE stage: doors_out (the OUT legs only, as v6c's doors_out2: comparable with its 5 PASS / 3 FAIL)
# and doors_rounds (every door in, then out). Needs the repo at main db7c015c or later (refused below).
# Usage (PowerShell, game closed):   .\plan.ps1        plan + dry runs only
#                                    .\plan.ps1 -Run   also run doors_out, judge it, then doors_rounds, judge it
# -Tag <name>: a retest into NEW queue folders (<queue>_<name>); -PortStaging: the value the earlier v6e runs used.
# Another installed core (Bugs' v6i doors, 2026-10-22): -CorePin <first 8 hex of its sha256> -CoreBuild <its core build
# folder> -OutMinM <metres>; the defaults are v6e's (-OutMinM has none: 0 keeps every exit, the v6e doors value).
# The load indices come from the repo's door_rounds.py order (step 1): run it from a checkout at main db7c015c or later
# (7ecc3185 gave port 07 where the live game had 06, 2026-10-22), and read Plugins.txt after a launch, not before: the
# game rewrites it about 25 s after start (docs/testing/load-order.md).
param([switch]$Run, [string]$Tag = '', [string]$PortStaging = '', [switch]$RoundsOnly, [string]$CorePin = '06C0DECD',
      [string]$CoreBuild = 'D:\Modding\staging\terrain_core64v6e_l125_mission_wfc11', [string]$OutMinM = '<FILL: metres>')
$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------- pins and placeholders (check every line before use)
$py          = 'C:\Modding\venv-render\Scripts\python.exe'
$Repo        = 'D:\Modding\wt_nightrun'      # PLACEHOLDER (supported): Card J used C:\Modding\scratch\wt_testcell at main; db7c015c or later
if (-not $PortStaging) { $PortStaging = '<FILL: full path of integ_v6_specmask_doors_c>' }
# $CoreBuild (a parameter): door_rounds stage --core; needs objects.json, formids.json, plan.json, overlays_params.json
$Bridge      = 'C:\Modding\staging\bridge_t4'
$Starfield   = 'D:\SteamLibrary\steamapps\common\Starfield'
$PluginsTxt  = "$env:LOCALAPPDATA\Starfield\Plugins.txt"                    # docs/terrain/door-rounds.md:33
# $OutMinM (a parameter): door_out_legs.py min distance from the Red Rocket arrival; doors_out2's value for a
# like-for-like v6c comparison, or 0 to keep every exit
$Stage       = 'D:\Modding\staging\doors_v6e_rounds'                        # NEW folders (the stage refuses an existing one)
$StageOut    = 'D:\Modding\staging\doors_v6e_out'
$QOut        = 'D:\Modding\testqueue_v6e\doors_out'
$QRounds     = 'D:\Modding\testqueue_v6e\doors_rounds'
$Caps        = @('--max-attempts','1','--max-relaunch','1','--crash-budget','1','--min-free-gb','40','--dump-drive','D:\')
$WorldPin    = @()   # after a first judge: e.g. @('--world-instance','FF00552F=02000803') ONLY for the pair that run shows

if ($Tag) { $Stage += "_$Tag"; $StageOut += "_$Tag"; $QRounds += "_$Tag"; $QOut += "_$Tag" }   # a retest: a NEW stage (rounds.json core_worlds,
                                             # #446: the judge then ties the runtime world itself), a NEW OUT stage
                                             # (untagged, 2026-10-22 v6i reused the Oct 21 v6e one) and new queues

function Need($ok, $why) { if (-not $ok) { throw "STOP: $why" } }
function Ok($what) { if ($LASTEXITCODE -ne 0) { throw "STOP: $what exit $LASTEXITCODE" } }
function Sha8($p) { (Get-FileHash -Algorithm SHA256 $p).Hash.Substring(0,8) }
function Full($p) { [IO.Path]::GetFullPath($p).TrimEnd('\') }
# a reused stage must come from this core build at this run's load indices (Codex on #500): else a stale plan meets
# the live order and targets the wrong records
function SameStage($dir) {
  $r = Get-Content "$dir\rounds.json" -Raw | ConvertFrom-Json
  Need ((Full $r.core) -ieq (Full $CoreBuild)) "$dir was staged from $($r.core), not -CoreBuild ${CoreBuild}: pass a new -Tag"
  Need ($r.core_index -eq $CoreIndex -and $r.port_index -eq $PortIndex) `
    "$dir was staged at core $($r.core_index) port $($r.port_index), this run's order is $CoreIndex $PortIndex`: pass a new -Tag"
}

# ---------------------------------------------------------------- 0. checks (read-only)
Need (-not $PortStaging.StartsWith('<')) 'fill $PortStaging'
Need ($RoundsOnly -or -not $OutMinM.StartsWith('<')) 'fill $OutMinM'
Need ((Sha8 "$PortStaging\FO4Port.esm") -eq '9AF962D2') 'staged FO4Port.esm is not build 9AF962D2'
Need ($CorePin -match '^[0-9A-Fa-f]{8}$') '-CorePin takes the first 8 hex digits of the core sha256'
Need ((Sha8 "$Starfield\Data\FO4TerrainCore.esm") -eq $CorePin.ToUpper()) "installed FO4TerrainCore.esm is not $CorePin"
Need ((Sha8 "$Starfield\Data\FO4SFBridge.esm") -eq '63C746BB') 'installed bridge is not 63C746BB'
foreach ($f in 'objects.json','formids.json','plan.json','overlays_params.json') {
  Need (Test-Path "$CoreBuild\$f") "$CoreBuild has no ${f}: pass -CoreBuild, the installed core's build folder" }
# the build gives the pairs, offsets and spawn, the installed ESM the records: both must be the same core (Codex on #500)
Need (Test-Path "$CoreBuild\FO4TerrainCore.esm") "$CoreBuild has no FO4TerrainCore.esm to check against -CorePin"
Need ((Sha8 "$CoreBuild\FO4TerrainCore.esm") -eq $CorePin.ToUpper()) "$CoreBuild\FO4TerrainCore.esm is not $CorePin`: -CoreBuild is another core's build"
Need ((Get-PSDrive D).Free / 1GB -ge 40) 'less than 40 GB free on D:'
Need (-not (Get-Process Starfield -ErrorAction SilentlyContinue)) 'Starfield is running: close it first'
Set-Location $Repo
git merge-base --is-ancestor db7c015c HEAD; Need ($LASTEXITCODE -eq 0) 'the repo checkout is older than db7c015c (its door_rounds.py order places the map markers after the port): git fetch and check out main first'
Write-Host "repo HEAD $(git rev-parse HEAD)  (db7c015c or later)"

# ---------------------------------------------------------------- 1. load indices of the runner's launch
# cycle.ps1 re-deploys FO4Port.esm at the end of Plugins.txt and the bridge goes last (door_rounds.py order)
$ord = & $py scripts\bridge\door_rounds.py order --plugins-txt $PluginsTxt
$ord | Write-Host
$m = [regex]::Match(($ord -join "`n"), '--core-index ([0-9A-F]{2}) --port-index ([0-9A-F]{2})')
Need $m.Success 'door_rounds.py order did not give both indices (FO4TerrainCore.esm not active?)'
$CoreIndex = $m.Groups[1].Value; $PortIndex = $m.Groups[2].Value

# ---------------------------------------------------------------- 2. stage every door against the INSTALLED plugins
if (Test-Path $Stage) { SameStage $Stage; Write-Host "stage exists, reused (same core build and indices): $Stage" }
else { & $py scripts\bridge\door_rounds.py stage --core $CoreBuild --core-plugin "$Starfield\Data\FO4TerrainCore.esm" `
          --port $PortStaging --core-index $CoreIndex --port-index $PortIndex --out $Stage; Ok 'scripts\bridge\door_rounds.py' }
if ($RoundsOnly) { Write-Host 'doors_rounds only: no OUT stage or queue' }
elseif (Test-Path $StageOut) {
  SameStage $StageOut                                            # door_out_legs.py records its threshold (Codex on #500)
  $om = (Get-Content "$StageOut\rounds.json" -Raw | ConvertFrom-Json).out_min_m
  Need ($null -ne $om -and [double]$om -eq [double]$OutMinM) "$StageOut kept exits at $om m, not -OutMinM ${OutMinM}: pass a new -Tag"
  Write-Host "OUT stage exists, reused (same core build, indices and -OutMinM): $StageOut" }
else { & $py scripts\bridge\door_out_legs.py $Stage $StageOut $OutMinM; Ok 'scripts\bridge\door_out_legs.py' }

# ---------------------------------------------------------------- 3. queues: no --plugins, the installed set stays
# (docs/terrain/door-rounds.md:37); --plugin-index = FO4Port's index in the runner's launch
# one [exp, queue] pair per element: an if's output is unrolled, so @(, @($Stage, $QRounds)) became two strings and
# -RoundsOnly planned with --exp-dir 'D' (watcher1 retest 2026-10-21: plan-terrain's exp[btd] TypeError)
$pairs = @()
if (-not $RoundsOnly) { $pairs += , @($StageOut, $QOut) }
$pairs += , @($Stage, $QRounds)
foreach ($p in $pairs) {
  $exp = $p[0]; $qq = $p[1]
  Need (Test-Path "$exp\plan.json") "no plan.json in the stage $exp"
  if (Test-Path "$qq\results.jsonl") { Write-Host "queue has results: resuming, NOT re-planned: $qq"; continue }
  & $py scripts\game\testqueue.py plan-terrain --staging $PortStaging --exp-dir $exp --out $qq --bridge $Bridge --plugin-index $PortIndex; Ok 'scripts\game\testqueue.py'
  & $py scripts\game\testqueue.py run --queue $qq --dry-run @Caps; Ok 'scripts\game\testqueue.py'
  Get-FileHash -Algorithm SHA256 "$qq\queue.json" | Format-List Hash, Path
}
if (-not $Run) { Write-Host 'planned; re-run with -Run when the PC is idle'; return }

# ---------------------------------------------------------------- 4. run + judge; doors_rounds only if doors_out ran clean
foreach ($q in $(if ($RoundsOnly) { @($QRounds) } else { @($QOut, $QRounds) })) {
  & $py scripts\game\testqueue.py run --queue $q --wait-for-idle --refocus @Caps
  $rc = $LASTEXITCODE; Write-Host "run $q exit $rc (0 all decided, 4 budget pause)"
  & $py scripts\bridge\door_rounds.py judge --queue $q @WorldPin      # writes $q\door_rounds_judge.json
  & $py scripts\game\testqueue.py report --queue $q; Ok 'scripts\game\testqueue.py'
  $st = Get-Content "$q\state.json" -Raw | ConvertFrom-Json
  if ($rc -ne 0 -or $st.crashes -gt 0 -or $st.start_deaths -gt 0) { Write-Host "STOP after $q (exit $rc, crashes $($st.crashes))"; break }
}
