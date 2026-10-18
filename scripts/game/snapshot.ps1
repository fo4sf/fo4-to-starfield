# snapshot.ps1 (Claude, 2026-10-16): what the owner is looking at, for Claude to read. Sends NOTHING to the game: one
# screenshot of the whole screen (shot.ps1), the bridge's newest line (bridge_log.py latest: position, cell, worldspace,
# loaded; the owner's session must have FO4SFBridge.esm active, as every pinned build does), the game's newest Papyrus
# log tail, and the installed experiment record. Everything goes to -Out (default C:\Modding\snapshots\<timestamp>):
# screen.png, state.json, papyrus_tail.txt, and one summary line on stdout. The owner says "look" and what they see;
# Claude runs this and reads screen.png. docs/owner/in-game-test-sheet.md section 7.
# -Ask (2026-10-18): after the screenshot (so the box is never in the picture) a small box asks "what is wrong?"; the text
# goes to description.txt and state.json's description. "Screenshot only" or an empty box keeps the plain snapshot.
# -Submit (2026-10-18, players): after saving, opens the repository's "Player report" form in the browser already filled
# in (description, position, cell, the port's plugin names; never a folder path) and puts screen.png on the clipboard, so
# the player pastes it (Ctrl+V) and presses Submit. Nothing is sent without that click and the player's GitHub sign-in;
# the form labels it community + needs-triage, so it waits for the owner's review. The link is kept in issue_url.txt.
# $env:FO4SF_SUBMIT_DRYRUN: write issue_url.txt only (tests: no browser, no clipboard).
# usage: snapshot.ps1 [-Out <folder>] [-Note "<what the owner said>"] [-MaxAge 900] [-Ask] [-Submit]
param([string]$Out = '', [string]$Note = '', [double]$MaxAge = 900, [switch]$Ask, [switch]$Submit)
$ErrorActionPreference = 'Continue'
$here = $PSScriptRoot
$py = if ($env:FO4SF_PYTHON) { $env:FO4SF_PYTHON } else { 'C:\Modding\venv-render\Scripts\python.exe' }
$root = $(if ($env:FO4SF_SNAPSHOT_ROOT) { $env:FO4SF_SNAPSHOT_ROOT } else { 'C:\Modding\snapshots' })   # tests: a temp root
if (-not $Out) { $Out = Join-Path $root (Get-Date -Format 'yyyyMMdd-HHmmss') }
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
# the description box (-Ask): after the capture; $env:FO4SF_ASK_ANSWER stands in for the typed text in tests (no window)
if ($Ask) {
  $text = $null
  if ($null -ne $env:FO4SF_ASK_ANSWER) { $text = $env:FO4SF_ASK_ANSWER }
  else {
    try {
      Add-Type -AssemblyName System.Windows.Forms, System.Drawing
      $f = New-Object System.Windows.Forms.Form
      $f.Text = 'FO4SF report: what is wrong?'; $f.TopMost = $true; $f.StartPosition = 'CenterScreen'
      $f.Size = New-Object System.Drawing.Size 520, 300; $f.FormBorderStyle = 'FixedDialog'; $f.MaximizeBox = $false; $f.MinimizeBox = $false
      $lbl = New-Object System.Windows.Forms.Label
      $lbl.Text = 'The screenshot is saved. Describe what is wrong (what you did, what you expected, what happened):'
      $lbl.SetBounds(10, 8, 490, 34)
      $tb = New-Object System.Windows.Forms.TextBox
      $tb.Multiline = $true; $tb.ScrollBars = 'Vertical'; $tb.AcceptsReturn = $true; $tb.SetBounds(10, 44, 485, 160)
      $ok = New-Object System.Windows.Forms.Button; $ok.Text = 'Save'; $ok.SetBounds(300, 215, 90, 30); $ok.DialogResult = 'OK'
      $skip = New-Object System.Windows.Forms.Button; $skip.Text = 'Screenshot only'; $skip.SetBounds(395, 215, 100, 30); $skip.DialogResult = 'Cancel'
      $f.Controls.AddRange(@($lbl, $tb, $ok, $skip)); $f.AcceptButton = $null; $f.CancelButton = $skip
      $f.Add_Shown({ $f.Activate(); $tb.Focus() })
      if ($f.ShowDialog() -eq 'OK') { $text = $tb.Text }
      $f.Dispose()
    } catch { $state.description_error = "$_" }
  }
  if ($text -and $text.Trim()) {
    $state.description = $text.Trim()
    Set-Content -LiteralPath (Join-Path $Out 'description.txt') -Value $state.description -Encoding utf8
    $state.description_file = 'description.txt'
  } else { $state.description = $null }
}
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
# no screenshot, no form: the link promises one on the clipboard (Codex's review of #350); the local failure stays recorded
if ($Submit -and -not $shotOk) { $state.submit_skipped = 'no screenshot' }
if ($Submit -and $shotOk) {
  $repo = $(if ($env:FO4SF_REPORT_REPO) { $env:FO4SF_REPORT_REPO } else { 'fo4sf/fo4-to-starfield' })
  $desc = $(if ($state.description) { $state.description } else { '' })
  $first = ($desc -split "`r?`n")[0]
  $title = '[Player report]: ' + $(if ($first) { $first.Substring(0, [Math]::Min(80, $first.Length)) } else { 'screenshot' })
  $where = $(if ($state.bridge.pos) { "pos $($state.bridge.pos -join ' ') cell $($state.bridge.cell) world $($state.bridge.world)" } else { '' })
  $ports = @($state.plugins_txt | Where-Object { "$_".StartsWith('*') } | ForEach-Object { "$_".Substring(1) } | Where-Object { $_ -like 'FO4*' })   # '*' = enabled
  $cap = "Captured $($state.taken); game running: $($state.game_running). Port plugins active: $(if ($ports) { $ports -join ', ' } else { 'none found' }).`n`nPaste the screenshot here (it is on your clipboard: Ctrl+V)."
  $fields = [ordered]@{ template = 'community_report.yml'; title = $title; what = $desc; where = $where; capture = $cap }
  $q = ($fields.GetEnumerator() | ForEach-Object { "$($_.Key)=$([uri]::EscapeDataString(($_.Value + '').Substring(0, [Math]::Min(1500, ($_.Value + '').Length))))" }) -join '&'
  $url = "https://github.com/$repo/issues/new?$q"
  Set-Content -LiteralPath (Join-Path $Out 'issue_url.txt') -Value $url -Encoding utf8
  $state.issue_url = 'issue_url.txt'
  if (-not $env:FO4SF_SUBMIT_DRYRUN) {
    try { Add-Type -AssemblyName System.Windows.Forms, System.Drawing
          $img = [System.Drawing.Image]::FromFile($shot); [System.Windows.Forms.Clipboard]::SetImage($img); $img.Dispose() }
    catch { $state.clipboard_error = "$_" }
    try { Start-Process $url } catch { $state.submit_error = "$_" }
  }
}
if ($Submit) { $state | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $Out 'state.json') -Encoding utf8 }
$posTxt = $(if ($state.bridge.pos) { "pos $($state.bridge.pos -join ' ') cell $($state.bridge.cell) world $($state.bridge.world) loaded $($state.bridge.loaded) age $($state.bridge.age_s)s" } else { "bridge: $($state.bridge.why)" })
"snapshot ${Out}: game=$($state.game_running) foreground=$($state.game_foreground) screen=$($state.screen)$(if ($state.description) { ' described=yes' }) | $posTxt"
if (-not $shotOk) { exit 3 }
