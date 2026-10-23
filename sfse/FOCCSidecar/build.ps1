# FOCCSidecar probe plugin, PC step 2: compile FOCCSidecar.dll with MSVC into a NEW staging folder and write build.json
# (sha256 of every source, of the fetched PluginAPI.h and of the dll; the cl.exe version; the commit the header was
# pinned to). Nothing is installed: step 3 of the runbook copies the dll by hand to <Starfield>\Data\SFSE\Plugins\.
# usage: powershell -File build.ps1 -Out D:\Modding\staging\focc_sfse_<date>
# Needs: check_toolchain.ps1 exit 0 (vcvars64.bat is found the same way) and fetch_pluginapi.ps1 done (PluginAPI.h
# beside this script). Refuses an -Out folder that already holds a FOCCSidecar.dll (never overwrites, never deletes).
# Compiler line (plan item B): cl.exe /nologo /std:c++20 /EHsc /O2 /W4 /DUNICODE /D_UNICODE /LD FOCCSidecar.cpp
# sha256.cpp; kernel32 is a default library, so no extra /link input is needed (the SHA-256 is our own portable code,
# not BCrypt, so bcrypt.lib is not linked).
param([Parameter(Mandatory)][string]$Out)
$ErrorActionPreference = 'Stop'
$src = $PSScriptRoot
$sources = @('FOCCSidecar.cpp', 'sha256.cpp', 'sha256.h', 'codec.h')
foreach ($s in $sources + @('PluginAPI.h', 'PluginAPI.pin.json')) {
  if (-not (Test-Path (Join-Path $src $s))) { "missing $s in $src" + $(if ($s -like 'PluginAPI*') { ' (run fetch_pluginapi.ps1 first)' }); exit 1 }
}
# The commit PluginAPI.h was fetched from, as fetch_pluginapi.ps1 recorded it; the header must be the bytes it pinned.
$pin = Get-Content -Raw (Join-Path $src 'PluginAPI.pin.json') | ConvertFrom-Json
$headerSha = (Get-FileHash -Algorithm SHA256 (Join-Path $src 'PluginAPI.h')).Hash.ToLower()
if ($pin.commit -notmatch '^[0-9a-f]{40}$' -or $pin.pluginapi_h_sha256 -ne $headerSha) {
  "PluginAPI.pin.json does not match PluginAPI.h (pin $($pin.pluginapi_h_sha256), header $headerSha): run fetch_pluginapi.ps1 again"; exit 1
}
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
if (-not (Test-Path $vswhere)) { 'vswhere.exe not found; run check_toolchain.ps1'; exit 1 }
$inst = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (-not $inst) { 'no VS instance with the C++ x64 tools; run check_toolchain.ps1'; exit 1 }
$vcvars = Join-Path $inst 'VC\Auxiliary\Build\vcvars64.bat'
if (-not (Test-Path $vcvars)) { "vcvars64.bat missing under $inst"; exit 1 }

$dll = Join-Path $Out 'FOCCSidecar.dll'
if (Test-Path $dll) { "$dll already exists: pick a new -Out folder (this script never overwrites)"; exit 1 }
New-Item -ItemType Directory -Path $Out -Force | Out-Null
$obj = Join-Path $Out 'obj'
New-Item -ItemType Directory -Path $obj -Force | Out-Null

# A batch file runs vcvars64 and cl in one environment (a quoted command line handed to cmd /c from PowerShell gets its
# quotes mangled; a file does not). The trailing \\ in /Fo is for the CRT argument parser: "dir\\" ends in one
# backslash. The compiler's output is kept in the staging folder.
$log = Join-Path $Out 'cl_output.txt'
$bat = Join-Path $Out 'build.cmd'
@("@echo off", "call `"$vcvars`" >nul || exit /b 90", "cd /d `"$src`" || exit /b 91",
  "cl.exe /nologo /std:c++20 /EHsc /O2 /W4 /DUNICODE /D_UNICODE /LD /Fo`"$obj\\`" /Fe`"$dll`" FOCCSidecar.cpp sha256.cpp " +
  "/link /PDB:`"$Out\FOCCSidecar.pdb`" /IMPLIB:`"$obj\FOCCSidecar.lib`"",
  "exit /b %ERRORLEVEL%") | Set-Content -Encoding ASCII $bat
& cmd.exe /c $bat 2>&1 | Tee-Object -FilePath $log
$code = $LASTEXITCODE
if ($code -ne 0 -or -not (Test-Path $dll)) { "build.cmd exit $code (90 = vcvars64 failed, 91 = source folder); no dll produced. Output: $log"; exit 1 }
$verBat = Join-Path $obj 'clver.cmd'
@("@echo off", "call `"$vcvars`" >nul", "cl.exe 2>&1") | Set-Content -Encoding ASCII $verBat
$clVersion = (& cmd.exe /c $verBat | Select-Object -First 1) -join ''

$hash = { param($p) (Get-FileHash -Algorithm SHA256 $p).Hash.ToLower() }
$build = [ordered]@{
  plugin = 'FOCCSidecar'; plugin_version = 1; built_at = (Get-Date).ToUniversalTime().ToString('o')
  compiler = $clVersion; vs_instance = $inst
  sources = [ordered]@{}
  pluginapi_h = [ordered]@{ sha256 = $headerSha; commit = $pin.commit }
  output = [ordered]@{ path = $dll; sha256 = (& $hash $dll); bytes = (Get-Item $dll).Length }
  install_to = 'Data\SFSE\Plugins\FOCCSidecar.dll (copied by hand, game closed; uninstall = delete that one file)'
}
foreach ($s in $sources) { $build.sources[$s] = & $hash (Join-Path $src $s) }
$build | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 (Join-Path $Out 'build.json')
# The ini with the kill switch OFF: the owner flips bEnabled to 1 by hand when installing (README.md "Kill switch").
"[FOCCSidecar]`r`nbEnabled=0`r`n" | Set-Content -Encoding ASCII (Join-Path $Out 'FOCCSidecar.ini')
"wrote $dll ($((Get-Item $dll).Length) bytes) sha256 $($build.output.sha256); build.json and FOCCSidecar.ini (bEnabled=0) beside it"
exit 0
