# FOCCSidecar probe plugin, PC step 0: can the SFSE plugin be built and loaded on this PC? Read-only; nothing is
# installed or changed. Prints one JSON object (and writes it to -Out) and exits 1 when the build cannot start, so the
# runbook stops here and the owner decides about installing Visual Studio Build Tools 2022 (C++ workload) or SFSE.
# usage: powershell -File check_toolchain.ps1 -Starfield <game dir> [-Out toolchain.json] [-Env <msvc env .ps1>]
# Two compilers count: a cl.exe already on PATH with INCLUDE and LIB set and a banner that says x64 (the PC's portable MSVC under D:\Modding\tools,
# 28 Oct 2026, loaded by dot-sourcing its msvc_env.ps1, which -Env does for you; nothing registered, no vswhere), else a
# Visual Studio instance found by vswhere. The JSON's `toolchain` says which (`environment` or `visual-studio`).
# Checks: vswhere -> a VS instance with the C++ x64 tools (cl.exe, vcvars64.bat), a Windows 10/11 SDK (registry
# KitsRoot10 + an Include folder), sfse_loader.exe and sfse_*.dll next to Starfield.exe (file names as SFSE's readme
# describes "the dll and exe files starting with sfse_"; the exact dll name on this PC is reported, not assumed),
# Starfield.exe's file version. The Address Library is NOT required: the plugin uses no game addresses.
param([Parameter(Mandatory)][string]$Starfield, [string]$Out = (Join-Path (Get-Location) 'toolchain.json'), [string]$Env = '')
$ErrorActionPreference = 'Stop'
if ($Env) {
  if (-not (Test-Path $Env)) { "-Env $Env not found"; exit 1 }
  . $Env
}
$r = [ordered]@{ ok = $false; problems = @(); toolchain = $null; env_script = $(if ($Env) { (Resolve-Path $Env).Path } else { $null });
                 vswhere = $null; vs_instance = $null; cl = $null; cl_banner = $null; cl_x64 = $null; vcvars64 = $null;
                 windows_sdk = $null; starfield_exe = $null; starfield_version = $null; sfse_loader = $null; sfse_dlls = @();
                 sfse_plugins_dir = $null; checked_at = (Get-Date).ToUniversalTime().ToString('o') }

# 1. The compiler. First a cl.exe already on PATH with INCLUDE and LIB set (a loaded MSVC environment: the portable
# toolchain, or a developer prompt); else Visual Studio C++ tools via vswhere (ships with the VS installer; absent = no VS).
$clOnPath = Get-Command cl.exe -ErrorAction SilentlyContinue
if ($clOnPath -and $env:INCLUDE -and $env:LIB) {
  $r.toolchain = 'environment'
  $r.cl = $clOnPath.Source
  # The loaded environment must target x64: an x86 developer prompt also puts cl.exe, INCLUDE and LIB in place, and a
  # 32-bit dll cannot load into Starfield's 64-bit process. cl.exe's banner names its target ("... Compiler Version
  # 19.44.35229 for x64"); cmd.exe merges the stderr it is printed on, so the Stop preference above does not trip on it.
  $r.cl_banner = (& cmd.exe /c 'cl.exe 2>&1' | Select-Object -First 1) -join ''
  $r.cl_x64 = [bool]($r.cl_banner -match '\bx64\b')
  if (-not $r.cl_x64) { $r.problems += "cl.exe on PATH does not target x64 (banner: $($r.cl_banner)); load the x64 environment (-Env D:\Modding\tools\msvc_env.ps1) or open an x64 developer prompt" }
} else {
  $r.toolchain = 'visual-studio'
  if ($clOnPath) { $r.problems += 'cl.exe is on PATH but INCLUDE or LIB is not set: dot-source the MSVC environment script first, or pass it as -Env' }
  $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
  if (Test-Path $vswhere) {
    $r.vswhere = $vswhere
    $inst = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath 2>$null
    if ($inst) {
      $r.vs_instance = $inst
      $vcvars = Join-Path $inst 'VC\Auxiliary\Build\vcvars64.bat'
      if (Test-Path $vcvars) { $r.vcvars64 = $vcvars } else { $r.problems += "vcvars64.bat missing under $inst" }
      $cl = Get-ChildItem (Join-Path $inst 'VC\Tools\MSVC') -Filter cl.exe -Recurse -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -like '*\bin\Hostx64\x64\cl.exe' } | Sort-Object FullName -Descending | Select-Object -First 1
      if ($cl) { $r.cl = $cl.FullName } else { $r.problems += 'no x64 cl.exe under the VS instance' }
    } else { $r.problems += 'no Visual Studio instance with the C++ x64 build tools (component VC.Tools.x86.x64)' }
  } else { $r.problems += 'vswhere.exe not found: Visual Studio / Build Tools are not installed' }
}

# 2. Windows SDK (windows.h and the import libraries): first the INCLUDE folders of a loaded environment (the portable
# SDK is registered nowhere), else the registry (KitsRoot10).
$sdkInc = $null
if ($env:INCLUDE) {
  $sdkInc = $env:INCLUDE -split ';' | Where-Object { $_ -and (Test-Path (Join-Path $_ 'windows.h')) } | Select-Object -First 1
}
if ($sdkInc) {
  $verDir = Split-Path $sdkInc
  $r.windows_sdk = [ordered]@{ root = (Split-Path (Split-Path $verDir)); version = (Split-Path $verDir -Leaf); source = 'INCLUDE' }
} else {
  $kits = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows Kits\Installed Roots' -ErrorAction SilentlyContinue
  if ($kits -and $kits.KitsRoot10) {
    $inc = Get-ChildItem (Join-Path $kits.KitsRoot10 'Include') -Directory -ErrorAction SilentlyContinue |
           Where-Object { Test-Path (Join-Path $_.FullName 'um\windows.h') } | Sort-Object Name -Descending | Select-Object -First 1
    if ($inc) { $r.windows_sdk = [ordered]@{ root = $kits.KitsRoot10; version = $inc.Name } }
    else { $r.problems += "Windows SDK root $($kits.KitsRoot10) has no Include\<ver>\um\windows.h" }
  } else { $r.problems += 'no Windows 10/11 SDK registered (KitsRoot10)' }
}

# 3. The game and SFSE (read-only looks at the game folder).
$exe = Join-Path $Starfield 'Starfield.exe'
if (Test-Path $exe) {
  $r.starfield_exe = $exe
  $vi = (Get-Item $exe).VersionInfo
  $r.starfield_version = "$($vi.FileMajorPart).$($vi.FileMinorPart).$($vi.FileBuildPart).$($vi.FilePrivatePart)"
} else { $r.problems += "Starfield.exe not found in $Starfield" }
$loader = Join-Path $Starfield 'sfse_loader.exe'
if (Test-Path $loader) { $r.sfse_loader = $loader } else { $r.problems += "sfse_loader.exe not found in $Starfield (SFSE 0.2.21 from its Nexus page, installed by the owner; never bundled)" }
$r.sfse_dlls = @(Get-ChildItem $Starfield -Filter 'sfse_*.dll' -ErrorAction SilentlyContinue | ForEach-Object {
  [ordered]@{ name = $_.Name; file_version = $_.VersionInfo.FileVersion; sha256 = (Get-FileHash -Algorithm SHA256 $_.FullName).Hash.ToLower() } })
if ($r.sfse_dlls.Count -eq 0) { $r.problems += 'no sfse_*.dll next to Starfield.exe' }
$r.sfse_plugins_dir = Join-Path $Starfield 'Data\SFSE\Plugins'
if (-not (Test-Path $r.sfse_plugins_dir)) { $r.problems += "$($r.sfse_plugins_dir) does not exist yet (SFSE creates it on first run; build.ps1 does not create it)" }

$r.ok = ($r.cl -and (($r.toolchain -eq 'environment' -and $r.cl_x64) -or $r.vcvars64) -and $r.windows_sdk -and $r.sfse_loader -and $r.sfse_dlls.Count -gt 0)
$json = $r | ConvertTo-Json -Depth 4
$json | Set-Content -Encoding UTF8 $Out
$json
if (-not $r.ok) { 'FOCCSidecar: the build cannot start on this PC; see problems above. Nothing was changed.'; exit 1 }
"FOCCSidecar: toolchain present ($($r.toolchain))"
exit 0
