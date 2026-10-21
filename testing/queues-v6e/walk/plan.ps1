# Red Rocket <-> Sanctuary continuous walk on the installed v6e set. DRAFT, cloud thread 2026-10-21, not run.
# Assumes the repo checkout at main 88c5aad (or c60d9a7, which only changes convert_batch.py).
# Usage (PowerShell, game closed, from any folder):   .\plan.ps1          plan + dry run only
#                                                     .\plan.ps1 -Run     also run (one queue, caps below), report, audit
# -Tag <name>: a retest into NEW queue folders (<queue>_<name>); -PortStaging: the value the earlier v6e runs used.
param([switch]$Run, [string]$Tag = '', [string]$PortStaging = '')
$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------- pins and placeholders (check every line before use)
$py          = 'C:\Modding\venv-render\Scripts\python.exe'                      # docs/ai/test-queue.md:9
$Repo        = 'D:\Modding\wt_nightrun'      # PLACEHOLDER (supported): campaign_arm.py example on the launchexe branch; must be at 88c5aad or later
if (-not $PortStaging) { $PortStaging = '<FILL: full path of integ_v6_specmask_doors_c>' }
$CoreStaging = 'D:\Modding\staging\terrain_core64v6e_l125_mission_wfc11'        # the installed core experiment (install session)
$Bridge      = 'C:\Modding\staging\bridge_t4'                                   # real-records FO4SFBridge.install.json "dir"
$Starfield   = 'D:\SteamLibrary\steamapps\common\Starfield'                     # real-records INDEX.md; testqueue.py default
$Fo4Esm      = 'C:\Program Files (x86)\Steam\steamapps\content\app_377160\depot_377163\Data\Fallout4.esm'
$WalkStage   = 'D:\Modding\staging\walk_core64v6e'                              # NEW folder: the route planned on v6e ground
$Queue       = 'D:\Modding\testqueue_v6e\walk'                                  # convention of D:\Modding\testqueue_v6c_out\doors_out2
$Caps        = @('--max-attempts','1','--max-relaunch','1','--crash-budget','1','--min-free-gb','40','--dump-drive','D:\')

if ($Tag) { $Queue += "_$Tag" }                           # a retest: a new queue, the same route

function Need($ok, $why) { if (-not $ok) { throw "STOP: $why" } }
function Ok($what) { if ($LASTEXITCODE -ne 0) { throw "STOP: $what exit $LASTEXITCODE" } }
function Sha8($p) { (Get-FileHash -Algorithm SHA256 $p).Hash.Substring(0,8) }

# ---------------------------------------------------------------- 0. checks (read-only)
Need (-not $PortStaging.StartsWith('<')) 'fill $PortStaging'
Need ((Sha8 "$PortStaging\FO4Port.esm") -eq '9AF962D2') 'staged FO4Port.esm is not build 9AF962D2'
Need ((Sha8 "$Starfield\Data\FO4TerrainCore.esm") -eq '06C0DECD') 'installed FO4TerrainCore.esm is not 06C0DECD'
Need ((Get-PSDrive D).Free / 1GB -ge 40) 'less than 40 GB free on D:'
Need (-not (Get-Process Starfield -ErrorAction SilentlyContinue)) 'Starfield is running: close it first'
Set-Location $Repo
git merge-base --is-ancestor 6c7884b HEAD; Need ($LASTEXITCODE -eq 0) 'the repo checkout is older than 6c7884b (#446 and #447): git fetch and check out main first'
Write-Host "repo HEAD $(git rev-parse HEAD)  (6c7884b or later)"
# The walk queue must pin EXACTLY the installed experiment and plugin list (testqueue.py install_mismatch), so both are
# read from the install record instead of typed here; pre_launch's exp_install.py install of the same set is a no-op
# ("already installed", scripts/game/exp_install.py:591).
$rec = Get-Content "$Starfield\Data\FO4SFExp.install.json" -Raw | ConvertFrom-Json
Need ($rec.complete -eq $true) 'experiment install record is not complete'
Need ($rec.pack -eq $true) 'experiment was installed without --pack: pre_launch (--pack) would refuse it (exp_install.py:592)'
Need ($rec.exp_dir -ieq $CoreStaging) "installed experiment is $($rec.exp_dir), not $CoreStaging"
$Plugins = ($rec.plugins -join ',')
Write-Host "installed experiment plugins: $Plugins"

# ---------------------------------------------------------------- 1. route on v6e's own ground and collision (offline)
# docs/terrain/walk-redrocket-sanctuary.md:64; exit 1 when the walked path is blocked anywhere (walk_route.py docstring)
if (Test-Path $WalkStage) { Write-Host "route folder exists, reused: $WalkStage" }
else { & $py scripts\terrain\walk_route.py plan --fo4 $Fo4Esm --core $CoreStaging --out $WalkStage; Ok 'scripts\terrain\walk_route.py' }
& $py scripts\terrain\walk_route.py show --out $WalkStage; Ok 'scripts\terrain\walk_route.py'

# ---------------------------------------------------------------- 2. the queue (both directions), bridge reads, noon
# Not --fresh: walk_route.py writes "fresh": true into both tests itself (walk_route.py:1108), so the reverse test
# relaunches once; that relaunch is not counted by --max-relaunch (testqueue.py:3512-3518). Two launches, not one.
if (Test-Path "$Queue\results.jsonl") { Write-Host "queue has results: resuming, NOT re-planned: $Queue" } else {
  & $py scripts\game\testqueue.py plan-walk --staging $PortStaging --exp-dir $WalkStage --install-exp $CoreStaging `
     --plugins $Plugins --bridge $Bridge --out $Queue --time-of-day 12; Ok 'scripts\game\testqueue.py'
  & $py scripts\game\testqueue.py run --queue $Queue --dry-run @Caps; Ok 'scripts\game\testqueue.py'
  Get-FileHash -Algorithm SHA256 "$Queue\queue.json" | Format-List Hash, Path
}
if (-not $Run) { Write-Host 'planned; re-run with -Run when the PC is idle'; return }

# ---------------------------------------------------------------- 3. run (resumable), report
& $py scripts\game\testqueue.py run --queue $Queue --wait-for-idle --refocus @Caps
Write-Host "run exit $LASTEXITCODE (0 all decided, 4 budget pause)"
& $py scripts\game\testqueue.py report --queue $Queue; Ok 'scripts\game\testqueue.py'

# ---------------------------------------------------------------- 4. typed-lines audit (independent of the judge)
# The judge already makes any other typed line INCONCLUSIVE TYPED, never PASS (walk_eval.py:433, :506). This re-reads
# every attempt's legs with the same whitelist (walk_eval.py:60): no setpos / coc / moveto may appear during a walk.
$ok = '^(ClearConsole|player\.getpos [xyz]|player\.setangle [xz] -?\d{1,3}(\.\d{1,2})?)$'
$bad = 0
Get-ChildItem "$Queue\tests\*\a*\obs.json" -ErrorAction SilentlyContinue | ForEach-Object {
  $o = Get-Content $_.FullName -Raw | ConvertFrom-Json
  foreach ($leg in @($o.legs)) { foreach ($c in @($leg.cmds)) { if ($c -and ($c -cnotmatch $ok)) { $bad++; Write-Host "TYPED $($_.FullName): $c" } } }
}
Write-Host "typed-lines audit: $bad line(s) outside ClearConsole/getpos/setangle"
