# Library stairs (BostonPublicLibrary02, the 20 stairs of the earlier sets) on the installed v6e set, routes planned
# again on this build. DRAFT, cloud thread 2026-10-21, not run. Assumes the repo at main 88c5aad (or c60d9a7).
# Usage (PowerShell, game closed):   .\plan.ps1        plan + dry run only
#                                    .\plan.ps1 -Run   also run (one launch, caps below) and report
# -Tag <name>: a retest into NEW queue folders (<queue>_<name>); -PortStaging: the value the earlier v6e runs used.
param([switch]$Run, [string]$Tag = '', [string]$PortStaging = '')
$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------- pins and placeholders (check every line before use)
$py          = 'C:\Modding\venv-render\Scripts\python.exe'
$Repo        = 'D:\Modding\wt_nightrun'      # PLACEHOLDER (supported): campaign_arm.py example on the launchexe branch; must be at 88c5aad or later
if (-not $PortStaging) { $PortStaging = '<FILL: full path of integ_v6_specmask_doors_c>' }
$Starfield   = 'D:\SteamLibrary\steamapps\common\Starfield'
$PluginsTxt  = "$env:LOCALAPPDATA\Starfield\Plugins.txt"
$Fo4Data     = 'C:\Program Files (x86)\Steam\steamapps\content\app_377160\depot_377163\Data'
$Cell        = 'BostonPublicLibrary02'
$RoutesDir   = 'D:\Modding\staging\stairs_bpl_v6e'                         # NEW folder: routes planned on this build
$Queue       = 'D:\Modding\testqueue_v6e\stairs'
# the 20 stairs of queues-1019/stairs (stairs_fix_1014's library tests), in that order
$Refs        = '0EBEDE,0EBEE3,0EBED6,0EBED7,0F032D,0EBEDD,0EBEE5,0EBEE7,0EF6A4,0EF797,0EF798,0EBECC,0EBEF2,0F0280,0EF8F8,0EBEE6,0EBEF1,0EF8F9,0EF8FB,0EF8FD'
$Caps        = @('--max-attempts','1','--max-relaunch','1','--crash-budget','1','--min-free-gb','40','--dump-drive','D:\')

if ($Tag) { $Queue += "_$Tag" }                           # a retest: a new queue, the same routes

function Need($ok, $why) { if (-not $ok) { throw "STOP: $why" } }
function Ok($what) { if ($LASTEXITCODE -ne 0) { throw "STOP: $what exit $LASTEXITCODE" } }
function Sha8($p) { (Get-FileHash -Algorithm SHA256 $p).Hash.Substring(0,8) }

# ---------------------------------------------------------------- 0. checks (read-only)
Need (-not $PortStaging.StartsWith('<')) 'fill $PortStaging'
Need ((Sha8 "$PortStaging\FO4Port.esm") -eq '9AF962D2') 'staged FO4Port.esm is not build 9AF962D2'
foreach ($f in "$Cell.json", 'manifest.json', 'formids.json') { Need (Test-Path "$PortStaging\$f") "no $f in the port staging" }
Need ((Get-PSDrive D).Free / 1GB -ge 40) 'less than 40 GB free on D:'
Need (-not (Get-Process Starfield -ErrorAction SilentlyContinue)) 'Starfield is running: close it first'
Set-Location $Repo
git merge-base --is-ancestor 6c7884b HEAD; Need ($LASTEXITCODE -eq 0) 'the repo checkout is older than 6c7884b (#446 and #447): git fetch and check out main first'
Write-Host "repo HEAD $(git rev-parse HEAD)  (6c7884b or later)"
# FO4Port's index in the runner's launch (cycle.ps1 deploys it after the other plugins; door_rounds.py order)
$ord = & $py scripts\bridge\door_rounds.py order --plugins-txt $PluginsTxt
$m = [regex]::Match(($ord -join "`n"), '--port-index ([0-9A-F]{2})')
Need $m.Success 'door_rounds.py order gave no port index'
$PortIndex = $m.Groups[1].Value

# ---------------------------------------------------------------- 1. routes on this build (docs/testing/stairs-routes.md:250-253)
if (Test-Path $RoutesDir) { Write-Host "routes folder exists, reused: $RoutesDir" }
else {
  New-Item -ItemType Directory $RoutesDir | Out-Null
  & $py scripts\game\routes.py --fo4-data $Fo4Data --cell-json "$PortStaging\$Cell.json" --manifest "$PortStaging\manifest.json" `
     --formids "$PortStaging\formids.json" --max 400 --out "$RoutesDir\routesfull_$Cell.json"; Ok 'scripts\game\routes.py'
}

# ---------------------------------------------------------------- 2. the queue (docs/ai/test-queue.md:72-75)
if (Test-Path "$Queue\results.jsonl") { Write-Host "queue has results: resuming, NOT re-planned: $Queue" } else {
  & $py scripts\game\testqueue.py plan --staging $PortStaging --out $Queue --cells $Cell --kinds stairs `
     --routes-prefix routesfull_ --routes-dir $RoutesDir --refs $Refs --plugin-index $PortIndex; Ok 'scripts\game\testqueue.py'
  $n = @((Get-Content "$Queue\queue.json" -Raw | ConvertFrom-Json).tests).Count
  Write-Host "$n of 20 stairs planned (a stair routes.py now skips is missing here: read its reason in $RoutesDir\routesfull_$Cell.json)"
  & $py scripts\game\testqueue.py run --queue $Queue --dry-run @Caps; Ok 'scripts\game\testqueue.py'
  Get-FileHash -Algorithm SHA256 "$Queue\queue.json" | Format-List Hash, Path
}
if (-not $Run) { Write-Host 'planned; re-run with -Run when the PC is idle'; return }

# ---------------------------------------------------------------- 3. run (resumable) and report
& $py scripts\game\testqueue.py run --queue $Queue --wait-for-idle --refocus @Caps
Write-Host "run exit $LASTEXITCODE (0 all decided, 4 budget pause)"
& $py scripts\game\testqueue.py report --queue $Queue; Ok 'scripts\game\testqueue.py'
