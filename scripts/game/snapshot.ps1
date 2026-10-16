# snapshot.ps1 (Claude, 2026-10-16): what the owner is looking at, for Claude to read. Sends NOTHING to the game: one
# screenshot of the whole screen (shot.ps1), the bridge's newest line (bridge_log.py latest: position, cell, worldspace,
# loaded; the owner's session must have FO4SFBridge.esm active, as every pinned build does), the game's newest Papyrus
# log tail, and the installed experiment record. Everything goes to -Out (default C:\Modding\snapshots\<timestamp>):
# screen.png, state.json, papyrus_tail.txt, and one summary line on stdout. The owner says "look" and what they see;
# Claude runs this and reads screen.png. docs/owner/in-game-test-sheet.md section 7.
# usage: snapshot.ps1 [-Out <folder>] [-Note "<what the owner said>"] [-MaxAge 900]
param([string]$Out = '', [string]$Note = '', [double]$MaxAge = 900)
$ErrorActionPreference = 'Continue'
$here = $PSScriptRoot
$py = if ($env:FO4SF_PYTHON) { $env:FO4SF_PYTHON } else { 'C:\Modding\venv-render\Scripts\python.exe' }
if (-not $Out) { $Out = Join-Path 'C:\Modding\snapshots' (Get-Date -Format 'yyyyMMdd-HHmmss') }
New-Item -ItemType Directory -Force $Out | Out-Null
$state = [ordered]@{ taken = (Get-Date -Format s); note = $Note; game_running = $false; game_foreground = $null }
$g = Get-Process Starfield -ErrorAction SilentlyContinue
if ($g) {
  $state.game_running = $true
  Add-Type -Namespace W -Name U -MemberDefinition '[DllImport("user32.dll")] public static extern System.IntPtr GetForegroundWindow(); [DllImport("user32.dll")] public static extern int GetWindowThreadProcessId(System.IntPtr h, out int pid);'
  $fpid = 0; [W.U]::GetWindowThreadProcessId([W.U]::GetForegroundWindow(), [ref]$fpid) | Out-Null
  $state.game_foreground = ($fpid -eq $g.Id)
}
$shot = Join-Path $Out 'screen.png'
# never a stale picture: a reused folder's screen.png goes first, and the capture must exit 0 and leave a new file
# (Codex's review of #175); without one, screen is null and the tool exits 3
Remove-Item -LiteralPath $shot -Force -ErrorAction SilentlyContinue
$shotScript = $(if ($env:FO4SF_SHOT_SCRIPT) { $env:FO4SF_SHOT_SCRIPT } else { Join-Path $here 'shot.ps1' })   # the test's stub
powershell -NoProfile -ExecutionPolicy Bypass -File $shotScript -Out $shot | Out-Null
$shotCode = $LASTEXITCODE
$shotOk = ($shotCode -eq 0) -and (Test-Path -LiteralPath $shot) -and ((Get-Item -LiteralPath $shot).Length -gt 0)
$state.screen = $(if ($shotOk) { 'screen.png' } else { $null })
if (-not $shotOk) { $state.screen_error = "shot.ps1 exit $shotCode"; Remove-Item -LiteralPath $shot -Force -ErrorAction SilentlyContinue }
# the bridge's newest line (any age up to MaxAge: the owner may have paused; the age is reported, never hidden)
$b = $null
try { $b = (& $py (Join-Path $here 'bridge_log.py') latest --max-age $MaxAge) | ConvertFrom-Json } catch { $b = $null }
if ($b -and $b.ok) {
  $state.bridge = [ordered]@{ pos = @($b.pos); ang = $b.ang; cell = $b.cell; world = $b.world; loaded = $b.loaded; rt = $b.rt; line = $b.n; age_s = $b.age_s }
} else { $state.bridge = [ordered]@{ why = $(if ($b) { "$($b.why)" } else { 'bridge_log.py gave nothing (no log, or no FO4SFBridge.esm in this session)' }) } }
# the newest Papyrus log's tail (script errors the owner cannot see)
$pap = Join-Path $env:USERPROFILE 'OneDrive\Documents\My Games\Starfield\Logs\Script\Papyrus.0.log'
if (-not (Test-Path $pap)) { $pap = Join-Path $env:USERPROFILE 'Documents\My Games\Starfield\Logs\Script\Papyrus.0.log' }
if (Test-Path $pap) { Get-Content $pap -Tail 40 | Set-Content (Join-Path $Out 'papyrus_tail.txt'); $state.papyrus_tail = 'papyrus_tail.txt' }
# what is installed (exp_install's record) and active
$rec = 'D:\SteamLibrary\steamapps\common\Starfield\Data\FO4SFExp.install.json'
if (Test-Path $rec) { try { $r = Get-Content $rec -Raw | ConvertFrom-Json; $state.installed = [ordered]@{ exp_dir = $r.exp_dir; plugins = @($r.files.PSObject.Properties.Name | Where-Object { $_ -like '*.esm' }) } } catch { } }
$pl = Join-Path $env:LOCALAPPDATA 'Starfield\Plugins.txt'
if (Test-Path $pl) { $state.plugins_txt = @(Get-Content $pl | Where-Object { $_ -and -not $_.StartsWith('#') }) }
$state | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $Out 'state.json') -Encoding utf8
$posTxt = $(if ($state.bridge.pos) { "pos $($state.bridge.pos -join ' ') cell $($state.bridge.cell) world $($state.bridge.world) loaded $($state.bridge.loaded) age $($state.bridge.age_s)s" } else { "bridge: $($state.bridge.why)" })
"snapshot ${Out}: game=$($state.game_running) foreground=$($state.game_foreground) screen=$($state.screen) | $posTxt"
if (-not $shotOk) { exit 3 }
