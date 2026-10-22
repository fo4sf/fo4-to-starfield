# Door round trips through the scripted load doors on the installed v6e set. DRAFT, cloud thread 2026-10-21, not run.
# Planner: scripts/bridge/door_rounds.py (docs/terrain/door-rounds.md), the one the v6c door queues used; judge: the same.
# Two queues from ONE stage: doors_out (the OUT legs only, as v6c's doors_out2: comparable with its 5 PASS / 3 FAIL)
# and doors_rounds (every door in, then out). Assumes the repo at main 88c5aad (or c60d9a7: convert_batch.py only).
# Usage (PowerShell, game closed):   .\plan.ps1        plan + dry runs only
#                                    .\plan.ps1 -Run   also run doors_out, judge it, then doors_rounds, judge it
# -Tag <name>: a retest into NEW queue folders (<queue>_<name>); -PortStaging: the value the earlier v6e runs used.
param([switch]$Run, [string]$Tag = '', [string]$PortStaging = '', [switch]$RoundsOnly)
$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------- pins and placeholders (check every line before use)
$py          = 'C:\Modding\venv-render\Scripts\python.exe'
$Repo        = 'D:\Modding\wt_nightrun'      # PLACEHOLDER (supported): campaign_arm.py example on the launchexe branch; must be at 88c5aad or later
if (-not $PortStaging) { $PortStaging = '<FILL: full path of integ_v6_specmask_doors_c>' }
$CoreBuild   = 'D:\Modding\staging\terrain_core64v6e_l125_mission_wfc11'   # door_rounds stage --core: needs objects.json,
                                             # formids.json, plan.json, overlays_params.json (checked below; else FILL the core build dir)
$Bridge      = 'C:\Modding\staging\bridge_t4'
$Starfield   = 'D:\SteamLibrary\steamapps\common\Starfield'
$PluginsTxt  = "$env:LOCALAPPDATA\Starfield\Plugins.txt"                    # docs/terrain/door-rounds.md:33
$OutMinM     = '<FILL: metres>'              # PLACEHOLDER: door_out_legs.py min distance from the Red Rocket arrival; use
                                             # doors_out2's value for a like-for-like v6c comparison, or 0 to keep every exit
$Stage       = 'D:\Modding\staging\doors_v6e_rounds'                        # NEW folders (the stage refuses an existing one)
$StageOut    = 'D:\Modding\staging\doors_v6e_out'
$QOut        = 'D:\Modding\testqueue_v6e\doors_out'
$QRounds     = 'D:\Modding\testqueue_v6e\doors_rounds'
$Caps        = @('--max-attempts','1','--max-relaunch','1','--crash-budget','1','--min-free-gb','40','--dump-drive','D:\')
$WorldPin    = @()   # after a first judge: e.g. @('--world-instance','FF00552F=02000803') ONLY for the pair that run shows

if ($Tag) { $Stage += "_$Tag"; $QRounds += "_$Tag"; $QOut += "_$Tag" }   # a retest: a NEW stage (rounds.json core_worlds,
                                             # #446: the judge then ties the runtime world itself) and new queues

function Need($ok, $why) { if (-not $ok) { throw "STOP: $why" } }
function Ok($what) { if ($LASTEXITCODE -ne 0) { throw "STOP: $what exit $LASTEXITCODE" } }
function Sha8($p) { (Get-FileHash -Algorithm SHA256 $p).Hash.Substring(0,8) }

# ---------------------------------------------------------------- 0. checks (read-only)
Need (-not $PortStaging.StartsWith('<')) 'fill $PortStaging'
Need ($RoundsOnly -or -not $OutMinM.StartsWith('<')) 'fill $OutMinM'
Need ((Sha8 "$PortStaging\FO4Port.esm") -eq '9AF962D2') 'staged FO4Port.esm is not build 9AF962D2'
Need ((Sha8 "$Starfield\Data\FO4TerrainCore.esm") -eq '06C0DECD') 'installed FO4TerrainCore.esm is not 06C0DECD'
Need ((Sha8 "$Starfield\Data\FO4SFBridge.esm") -eq '63C746BB') 'installed bridge is not 63C746BB'
foreach ($f in 'objects.json','formids.json','plan.json','overlays_params.json') {
  Need (Test-Path "$CoreBuild\$f") "$CoreBuild has no ${f}: set `$CoreBuild to the v6e core build folder" }
Need ((Get-PSDrive D).Free / 1GB -ge 40) 'less than 40 GB free on D:'
Need (-not (Get-Process Starfield -ErrorAction SilentlyContinue)) 'Starfield is running: close it first'
Set-Location $Repo
git merge-base --is-ancestor 6c7884b HEAD; Need ($LASTEXITCODE -eq 0) 'the repo checkout is older than 6c7884b (#446 and #447): git fetch and check out main first'
Write-Host "repo HEAD $(git rev-parse HEAD)  (6c7884b or later)"

# ---------------------------------------------------------------- 1. load indices of the runner's launch
# cycle.ps1 re-deploys FO4Port.esm at the end of Plugins.txt and the bridge goes last (door_rounds.py order)
$ord = & $py scripts\bridge\door_rounds.py order --plugins-txt $PluginsTxt
$ord | Write-Host
$m = [regex]::Match(($ord -join "`n"), '--core-index ([0-9A-F]{2}) --port-index ([0-9A-F]{2})')
Need $m.Success 'door_rounds.py order did not give both indices (FO4TerrainCore.esm not active?)'
$CoreIndex = $m.Groups[1].Value; $PortIndex = $m.Groups[2].Value

# ---------------------------------------------------------------- 2. stage every door against the INSTALLED plugins
if (Test-Path $Stage) { Write-Host "stage exists, reused: $Stage" }
else { & $py scripts\bridge\door_rounds.py stage --core $CoreBuild --core-plugin "$Starfield\Data\FO4TerrainCore.esm" `
          --port $PortStaging --core-index $CoreIndex --port-index $PortIndex --out $Stage; Ok 'scripts\bridge\door_rounds.py' }
if ($RoundsOnly) { Write-Host 'doors_rounds only: no OUT stage or queue' }
elseif (Test-Path $StageOut) { Write-Host "OUT stage exists, reused: $StageOut" }
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
