# FOCCPing, PC build: cmake + ninja with the loaded MSVC environment, against an installed CommonLibSF and the spdlog /
# fmt its vcpkg run built, into a NEW staging folder; build.json records every sha256. Nothing is installed: the dll is
# copied by hand to <Starfield>\Data\SFSE\Plugins\ (runbook section B0, job B0-2, the owner's line).
# usage: powershell -File build.ps1 -Out D:\Modding\staging\focc_ping_<date> -CommonLibSF <install prefix>
#        -Vcpkg <CommonLibSF build>\vcpkg_installed\x64-windows-static-md-release -Env D:\Modding\tools\msvc_env.ps1
# -CommonLibSF is the prefix `cmake --install` wrote (lib\cmake\CommonLibSF\CommonLibSFConfig.cmake inside it); -Vcpkg
# the triplet folder of the library's build (share\spdlog\spdlogConfig.cmake inside it). The environment must target
# x64 (cl.exe's banner is read, as sfse/FOCCSidecar's scripts do). Refuses an -Out that already holds a FOCCPing.dll
# (never overwrites, never deletes). cmake and ninja run from a batch file with stderr merged, as FOCCSidecar's build.
param([Parameter(Mandatory)][string]$Out, [Parameter(Mandatory)][string]$CommonLibSF, [Parameter(Mandatory)][string]$Vcpkg, [string]$Env = '')
$ErrorActionPreference = 'Stop'
if ($Env) {
  if (-not (Test-Path $Env)) { "-Env $Env not found"; exit 1 }
  . $Env
}
foreach ($tool in 'cl.exe', 'cmake.exe', 'ninja.exe') {
  if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) { "$tool is not on PATH: load the MSVC environment (-Env D:\Modding\tools\msvc_env.ps1, which also puts cmake and ninja on PATH)"; exit 1 }
}
if (-not ($env:INCLUDE -and $env:LIB)) { 'INCLUDE or LIB is not set: dot-source the MSVC environment script first, or pass it as -Env'; exit 1 }
$banner = (& cmd.exe /c 'cl.exe 2>&1' | Select-Object -First 1) -join ''
if ($banner -notmatch '\bx64\b') { "cl.exe on PATH does not target x64 (banner: $banner); load the x64 environment. Nothing was built."; exit 1 }
$config = Join-Path $CommonLibSF 'lib\cmake\CommonLibSF\CommonLibSFConfig.cmake'
if (-not (Test-Path $config)) { "-CommonLibSF $CommonLibSF is not an installed CommonLibSF prefix: $config missing (run cmake --install on the library's build tree first)"; exit 1 }
$spdlog = Join-Path $Vcpkg 'share\spdlog\spdlogConfig.cmake'
if (-not (Test-Path $spdlog)) { "-Vcpkg $Vcpkg is not a vcpkg_installed triplet folder: $spdlog missing"; exit 1 }
$src = $PSScriptRoot
$sources = @('CMakeLists.txt', 'src\main.cpp', 'src\Plugin.h')
foreach ($s in $sources) { if (-not (Test-Path (Join-Path $src $s))) { "missing $s in $src"; exit 1 } }

$dll = Join-Path $Out 'FOCCPing.dll'
if (Test-Path $dll) { "$dll already exists: pick a new -Out folder (this script never overwrites)"; exit 1 }
New-Item -ItemType Directory -Path $Out -Force | Out-Null
$build = Join-Path $Out 'build'
$log = Join-Path $Out 'cmake_output.txt'
$bat = Join-Path $Out 'build.cmd'
$prefix = "$CommonLibSF;$Vcpkg"
# cmake writes its warnings to stderr; merged inside cmd.exe so the Stop preference above does not read them as errors
@("@echo off",
  "cmake.exe -S `"$src`" -B `"$build`" -G Ninja -DCMAKE_BUILD_TYPE=Release `"-DCMAKE_PREFIX_PATH=$prefix`" 2>&1 || exit /b 90",
  "cmake.exe --build `"$build`" 2>&1 || exit /b 91",
  "exit /b 0") | Set-Content -Encoding ASCII $bat
& cmd.exe /c $bat | Tee-Object -FilePath $log
$code = $LASTEXITCODE
$built = Join-Path $build 'FOCCPing.dll'
if ($code -ne 0 -or -not (Test-Path $built)) { "build.cmd exit $code (90 = configure, 91 = build); no dll produced. Output: $log"; exit 1 }
Copy-Item $built $dll
$pdb = Join-Path $build 'FOCCPing.pdb'
if (Test-Path $pdb) { Copy-Item $pdb (Join-Path $Out 'FOCCPing.pdb') }

$hash = { param($p) (Get-FileHash -Algorithm SHA256 $p).Hash.ToLower() }
$cmakeVersion = ((& cmake.exe --version) | Select-Object -First 1) -join ''
$record = [ordered]@{
  plugin = 'FOCCPing'; plugin_version = '0.1.0'; built_at = (Get-Date).ToUniversalTime().ToString('o')
  compiler = $banner; cmake = $cmakeVersion; toolchain = 'environment'
  cl = (Get-Command cl.exe).Source; env_script = $(if ($Env) { (Resolve-Path $Env).Path } else { $null })
  commonlibsf_prefix = (Resolve-Path $CommonLibSF).Path; commonlibsf_config_sha256 = (& $hash $config)
  vcpkg_installed = (Resolve-Path $Vcpkg).Path
  sources = [ordered]@{}
  output = [ordered]@{ path = $dll; sha256 = (& $hash $dll); bytes = (Get-Item $dll).Length }
  install = 'copy FOCCPing.dll to <Starfield>\Data\SFSE\Plugins\ by hand (game closed); needs versionlib-1-16-244-0.bin there'
}
foreach ($s in $sources) { $record.sources[$s] = (& $hash (Join-Path $src $s)) }
$json = $record | ConvertTo-Json -Depth 4
$json | Set-Content -Encoding UTF8 (Join-Path $Out 'build.json')
$json
"FOCCPing: built $dll"
exit 0
