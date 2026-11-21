# FO4SFCombat, PC build: xmake against the libxse CommonLibSF checkout, into a NEW staging folder; build.json records
# every sha256 and both library commits. Nothing is installed into any game folder.
param([Parameter(Mandatory)][string]$Out, [Parameter(Mandatory)][string]$Lib, [string]$Env = '', [string]$Sdk = '')
$ErrorActionPreference = 'Stop'
$PinnedLib = '9d090c4c521f4f2c1aa00bb05923c380d47ae596'
$PinnedShared = '9fbb74d628134ab4ea3a3cf5c0ed3f7eeabbd01d'
function New-Junction([string]$Path, [string]$Target) {
  if (Test-Path $Path) {
    $have = @((Get-Item $Path -Force).Target) -join ''
    if (-not $have -or $have.TrimEnd('\', '/') -ieq $Target.TrimEnd('\', '/')) { "reusing $Path"; return }
    "$Path exists and points at '$have', not ${Target}: pick a new -Out folder (this script never overwrites)"; exit 1
  }
  New-Item -ItemType Junction -Path $Path -Target $Target | Out-Null
}
if ($Env) {
  if (-not (Test-Path $Env)) { "-Env $Env not found"; exit 1 }
  . $Env
}
if (-not (Get-Command xmake.exe -ErrorAction SilentlyContinue)) { 'xmake.exe is not on PATH: load the environment that has it (-Env)'; exit 1 }
$xmakeVersion = ((& xmake.exe --version) | Select-Object -First 1) -join ''
if ($xmakeVersion -notmatch 'v(\d+)\.') { "xmake --version gave '$xmakeVersion'"; exit 1 }
if ([int]$Matches[1] -lt 3) { "xmake 3.0 or newer is needed; found: $xmakeVersion"; exit 1 }
if (Get-Command cl.exe -ErrorAction SilentlyContinue) {
  $banner = (& cmd.exe /c 'cl.exe 2>&1' | Select-Object -First 1) -join ''
  if ($banner -notmatch '\bx64\b') { "cl.exe on PATH does not target x64 (banner: $banner); load the x64 environment."; exit 1 }
} else { $banner = $null }
foreach ($need in 'xmake.lua', 'include\SFSE\SFSE.h', 'lib\commonlib-shared\xmake.lua', 'lib\commonlib-shared\src\REL\IDDB.cpp') {
  if (-not (Test-Path (Join-Path $Lib $need))) { "-Lib $Lib is missing $need"; exit 1 }
}
$libCommit = $null; $sharedCommit = $null
if (Get-Command git.exe -ErrorAction SilentlyContinue) {
  $eap = $ErrorActionPreference; $ErrorActionPreference = 'SilentlyContinue'
  $libCommit = (& git.exe -C $Lib rev-parse HEAD 2>$null) -join ''
  $sharedCommit = (& git.exe -C (Join-Path $Lib 'lib\commonlib-shared') rev-parse HEAD 2>$null) -join ''
  $ErrorActionPreference = $eap
  if (-not $libCommit) { $libCommit = $null }
  elseif ($libCommit -ne $PinnedLib) { "note: -Lib is at $libCommit, not the pinned $PinnedLib" }
  if (-not $sharedCommit) { $sharedCommit = $null }
  elseif ($sharedCommit -ne $PinnedShared) { "note: lib\commonlib-shared is at $sharedCommit, not the pinned $PinnedShared" }
}
$src = $PSScriptRoot
$commonHeader = Join-Path $src '..\common\blocking_menus.h'
$sources = @('xmake.lua', 'FO4SFCombat.ini', 'src\main.cpp', 'src\pch.h')
foreach ($s in $sources) { if (-not (Test-Path (Join-Path $src $s))) { "missing $s in $src"; exit 1 } }
if (-not (Test-Path $commonHeader)) { "missing ..\common\blocking_menus.h from $src"; exit 1 }
if ($Sdk -and -not (Test-Path (Join-Path $Sdk 'VC\Tools\MSVC'))) { "-Sdk $Sdk has no VC\Tools\MSVC folder"; exit 1 }

$dll = Join-Path $Out 'FO4SFCombat.dll'
if (Test-Path $dll) { "$dll already exists: pick a new -Out folder (this script never overwrites)"; exit 1 }
New-Item -ItemType Directory -Path $Out -Force | Out-Null
if (-not $Sdk -and $env:VCToolsInstallDir -and $env:WindowsSdkDir) {
  $vcRoot = Split-Path (Split-Path (Split-Path $env:VCToolsInstallDir.TrimEnd('\', '/')))
  $kits = Split-Path $env:WindowsSdkDir.TrimEnd('\', '/')
  if ((Split-Path $vcRoot -Leaf) -eq 'VC' -and (Split-Path $kits -Leaf) -eq 'Windows Kits' -and (Test-Path $vcRoot) -and (Test-Path $kits)) {
    $Sdk = Join-Path $Out 'vsroot'
    New-Item -ItemType Directory -Path $Sdk -Force | Out-Null
    New-Junction (Join-Path $Sdk 'VC') $vcRoot
    New-Junction (Join-Path $Sdk 'Windows Kits') $kits
  }
}
$proj = Join-Path $Out 'proj'
New-Item -ItemType Directory -Path (Join-Path $proj 'src') -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $proj 'common') -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $proj 'lib') -Force | Out-Null
foreach ($s in $sources) { Copy-Item (Join-Path $src $s) (Join-Path $proj $s) }
Copy-Item $commonHeader (Join-Path $proj 'common\blocking_menus.h')
New-Junction (Join-Path $proj 'lib\commonlibsf') (Resolve-Path $Lib).Path
Remove-Item Env:XSE_SF_MODS_PATH -ErrorAction SilentlyContinue
Remove-Item Env:XSE_SF_GAME_PATH -ErrorAction SilentlyContinue

$log = Join-Path $Out 'xmake_output.txt'
$bat = Join-Path $Out 'build.cmd'
$sdkArg = $(if ($Sdk) { " --sdk=`"$($Sdk.TrimEnd('\', '/'))`"" } else { '' })
@("@echo off",
  "cd /d `"$proj`" || exit /b 89",
  "xmake.exe f -y -p windows -a x64 -m releasedbg --toolchain=msvc$sdkArg 2>&1 || exit /b 90",
  "xmake.exe build -y FO4SFCombat 2>&1 || exit /b 91",
  "exit /b 0") | Set-Content -Encoding ASCII $bat
& cmd.exe /c $bat | Tee-Object -FilePath $log
$code = $LASTEXITCODE
$built = Join-Path $proj 'build\windows\x64\releasedbg\FO4SFCombat.dll'
if (-not (Test-Path $built)) {
  $found = Get-ChildItem -Path (Join-Path $proj 'build') -Recurse -Filter 'FO4SFCombat.dll' -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($found) { $built = $found.FullName }
}
if ($code -ne 0 -or -not (Test-Path $built)) { "build.cmd exit $code; no dll produced. Output: $log"; exit 1 }
Copy-Item $built $dll
Copy-Item (Join-Path $src 'FO4SFCombat.ini') (Join-Path $Out 'FO4SFCombat.ini')
$pdb = [System.IO.Path]::ChangeExtension($built, '.pdb')
if (Test-Path $pdb) { Copy-Item $pdb (Join-Path $Out 'FO4SFCombat.pdb') }

$hash = { param($p) (Get-FileHash -Algorithm SHA256 $p).Hash.ToLower() }
$record = [ordered]@{
  plugin = 'FO4SFCombat'; plugin_version = '0.1.0'; built_at = (Get-Date).ToUniversalTime().ToString('o')
  xmake = $xmakeVersion; compiler = $banner; sdk_root = $(if ($Sdk) { (Resolve-Path $Sdk).Path } else { $null })
  env_script = $(if ($Env) { (Resolve-Path $Env).Path } else { $null })
  library = [ordered]@{ path = (Resolve-Path $Lib).Path; commit = $libCommit; pinned = $PinnedLib; shared_commit = $sharedCommit; shared_pinned = $PinnedShared }
  sources = [ordered]@{}
  output = [ordered]@{ path = $dll; sha256 = (& $hash $dll); bytes = (Get-Item $dll).Length }
  install = 'copy FO4SFCombat.dll, FO4SFCombat.ini and versionlib-1-16-244-0.bin (format 5) to <Starfield>\Data\SFSE\Plugins\ by hand (game closed)'
}
foreach ($s in $sources) { $record.sources[$s] = (& $hash (Join-Path $src $s)) }
$record.sources['common\blocking_menus.h'] = (& $hash $commonHeader)
$json = $record | ConvertTo-Json -Depth 4
$json | Set-Content -Encoding UTF8 (Join-Path $Out 'build.json')
$json
"FO4SFCombat: built $dll"
exit 0
