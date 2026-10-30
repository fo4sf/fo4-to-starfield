# Open the local agents' terminal: OpenCode's own terminal UI on the team's agents, for the owner to talk to.
#   powershell -ExecutionPolicy Bypass -File tools\ai-team\terminal.ps1 [-Agent fo4-lead] [-Continue]
# It starts the team (guardian proxy, picked model), then runs OpenCode in its own worktree next to the repo
# (fo4-to-starfield-wt\local-terminal), so the main checkout and the unattended Lead's worktree are never touched. A
# clean worktree goes back to main's newest commit (no branch) at every start unless another terminal window is open
# on it, so a guard fix on main reaches it, and the terminal does not start while the worktree has a change to a file
# the guard refuses an agent to write, or is on a branch that differs from main in one. The guard plugin checks each
# command and file write an agent makes, as in unattended runs; because the owner is present, it also lets an agent
# make its own ai/ branch from main and commit named files there (agent_git.py). It cannot check what a test does:
# the coding agent writes tests, and a test it runs can run any code
# with the owner's rights (push with their git login, or change the guard's own files). So OpenCode asks the owner
# before each test run, as long as the owner answers Allow once (Allow always or auto-accept stops the asking until
# OpenCode exits), and in this terminal "nothing pushes" rests on the model and on the owner reading those prompts.
# The owner's own OpenCode config (~/.config/opencode) is not checked. Skills from ~/.claude and ~/.agents (the
# claude.ai ones) stay hidden from the agents.
param([string]$Agent = 'fo4-lead', [switch]$Continue,
      [string]$Python = $(if ($env:FO4SF_PYTHON) { $env:FO4SF_PYTHON } else { 'python' }))
$repo = Split-Path (Split-Path $PSScriptRoot)
$Host.UI.RawUI.WindowTitle = "FO4SF local agents ($Agent)"
$models = Join-Path $PSScriptRoot 'models.py'
# The guard plugin runs its checker with this Python, as a full path, so it is resolved first, as run-lead.ps1 does:
# a program (not an alias or function from a profile), then the program Python says it runs as. The Microsoft Store's
# python.exe alias is refused: OpenCode cannot start it, so every guarded call would come back "no verdict".
$pythonPath = (Get-Command $Python -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
if (-not [IO.Path]::IsPathRooted("$pythonPath")) { throw "-Python $Python is not a program with a full path" }
$pythonPath = "$(& $pythonPath -I -c 'import sys; print(sys.executable)')".Trim()
if (-not [IO.Path]::IsPathRooted($pythonPath) -or $pythonPath -match '\\WindowsApps\\' -or
    -not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
  throw ("-Python $Python runs as '$pythonPath', which OpenCode cannot start: pass -Python with the full path " +
         "of a python.exe from python.org or the Python install manager")
}

powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'start-team.ps1')
$ensure = (& $pythonPath $models ensure | Out-String).Trim()
if ($LASTEXITCODE -ne 0) { "WARNING: the picked model is not loaded ($ensure). Pick one in the FO4SF AI menu." }
else { try { "model: $(($ensure | ConvertFrom-Json).picked.model)" } catch { $ensure } }

$wt = Join-Path (Split-Path $repo) 'fo4-to-starfield-wt\local-terminal'
git -C $repo fetch -q origin main
if ($LASTEXITCODE -ne 0) { "note: could not fetch main (offline?): the terminal opens on the last main fetched" }
# Each open terminal window has a file named by its pid here, so a second window (another agent from the menu) never
# moves the worktree under the first one's agent. A window closed with its X button leaves its file: a pid that is
# no longer a PowerShell process, or one that started after its file was written (Windows gave the pid out again), is
# stale.
$state = if ($env:FO4_AI_TEAM_STATE) { $env:FO4_AI_TEAM_STATE } else { Join-Path $env:LOCALAPPDATA 'fo4-ai-team\state' }
$open = Join-Path $state 'terminal-sessions'
New-Item -ItemType Directory -Force $open | Out-Null
$mine = Join-Path $open "$PID.pid"
try {
  $null = New-Item -ItemType File -Force $mine           # before the check, so two windows started at once see each other
  $others = @()
  foreach ($f in @(Get-ChildItem -LiteralPath $open -Filter '*.pid' -ErrorAction SilentlyContinue)) {
    $id = $f.BaseName
    if ($id -match '^[1-9][0-9]{0,8}$' -and [int]$id -ne $PID -and
        (Get-Process -Id ([int]$id) -ErrorAction SilentlyContinue | Where-Object {
          $started = try { $_.StartTime } catch { $null }
          $_.ProcessName -in 'powershell', 'pwsh' -and $started -and $started -le $f.LastWriteTime.AddSeconds(2) })) {
      $others += $id
    } elseif ($id -ne "$PID") { Remove-Item -LiteralPath $f.FullName -Force -ErrorAction SilentlyContinue }
  }
  if (-not (Test-Path $wt)) {
    git -C $repo worktree add -q --detach $wt origin/main
    if ($LASTEXITCODE -ne 0) { "could not make the terminal's worktree ${wt}: not starting"; exit 1 }
    "made the terminal's worktree $wt (main, no branch)"
  } elseif ($others -or (git -C $wt status --porcelain)) {
    $on = "$(git -C $wt rev-parse --abbrev-ref HEAD)".Trim()
    if ($others) { "note: another terminal window (pid $($others -join ', ')) is open on $wt (on $on), so it stays as it is" }
    else { "note: $wt has uncommitted changes (on $on), so it stays as it is" }
  } else {
    # Clean and no other window: back to main. An agent branch made here keeps its commits, and agent_git.py branch
    # with its name switches back to it; the next new one starts from main.
    git -C $wt switch -q --detach origin/main
    if ($LASTEXITCODE -ne 0) { "could not move $wt to main (a stale index.lock?): not starting"; exit 1 }
  }
  # The guard and OpenCode read their rules, the guard's code and the agents' instructions from the worktree, and a test
  # the coding agent runs can change them (see the top of this file). So the terminal starts only while no file the
  # guard refuses an agent to write is changed or added here (ignored files included, apart from OpenCode's own install
  # files in .opencode), and none differs from main on the branch it is on. The main checkout's guard judges, not the
  # worktree's. Python's caches go first in the folders whose scripts the team runs, as a planted .pyc would run in
  # place of its source. This catches a change; it does not fence a test that sets out to get round it.
  foreach ($d in @('tools\ai-team', 'scripts')) {
    Get-ChildItem -LiteralPath (Join-Path $wt $d) -Recurse -Directory -Force -Filter '__pycache__' -ErrorAction SilentlyContinue |
      Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
  }
  $installFiles = '^\.opencode/(node_modules/|package\.json$|package-lock\.json$|bun\.lock$|\.gitignore$)'
  $local = @(git -C $wt diff --no-renames --name-only HEAD)
  if ($LASTEXITCODE -ne 0) { "could not compare $wt with its last commit: not starting"; exit 1 }
  $untracked = @(git -C $wt ls-files --others)
  if ($LASTEXITCODE -ne 0) { "could not list ${wt}'s files: not starting"; exit 1 }
  $local += @($untracked | Where-Object { $_ -notmatch $installFiles })
  $behind = @(git -C $wt diff --no-renames --name-only HEAD origin/main)
  if ($LASTEXITCODE -ne 0) { "could not compare $wt with main: not starting"; exit 1 }
  $checker = Join-Path $PSScriptRoot 'guard\allowlist.py'      # the main checkout's guard
  $OutputEncoding = New-Object System.Text.UTF8Encoding $false   # the paths go to Python as UTF-8
  $refusedHere = @($local | & $pythonPath -I $checker --refused-writes $wt)
  if ($LASTEXITCODE -ne 0) { "the guard could not check ${wt}'s files: not starting"; exit 1 }
  $refusedBehind = @($behind | & $pythonPath -I $checker --refused-writes $wt)
  if ($LASTEXITCODE -ne 0) { "the guard could not check ${wt}'s branch: not starting"; exit 1 }
  if ($refusedHere) {
    "$wt has changes an agent may not make, so the terminal does not start:"
    $refusedHere | Select-Object -First 20 | ForEach-Object { "  $_" }
    "They may come from a test the agent ran. Have Claude look at them, then reopen."
    exit 1
  }
  if ($refusedBehind) {
    "$wt is on a branch that differs from main in files an agent may not write, so the terminal does not start:"
    $refusedBehind | Select-Object -First 20 | ForEach-Object { "  $_" }
    "Have Claude merge main into that branch, or close the other terminal windows and commit or drop the edits so the"
    "worktree goes back to main, then reopen."
    exit 1
  }

  foreach ($f in @('.opencode\plugin\fo4-guard.js', 'tools\ai-team\guard\allowlist.py')) {
    if (-not (Test-Path (Join-Path $wt $f))) { "$wt has no $f, so the guard would be off: not starting"; exit 1 }
  }
  if (-not (Get-Command opencode -ErrorAction SilentlyContinue)) { "OpenCode (opencode) is not on PATH"; exit 1 }
  try {                                              # the proxy must refuse a request with no guard header
    Invoke-WebRequest -UseBasicParsing -Method Post -Uri 'http://127.0.0.1:1235/v1/chat/completions' -Body '{}' `
      -ContentType 'application/json' -TimeoutSec 10 | Out-Null
    $gate = $false
  } catch { $gate = $_.Exception.Response -and [int]$_.Exception.Response.StatusCode -eq 403 }
  if (-not $gate) {
    "The guardian proxy is not running, or serves requests without the guard header (started before the guard)."
    "Restart the team (FO4SF AI menu: 9, then 1), then open the terminal again. Not starting."; exit 1
  }

  Remove-Item Env:FO4SF_UNATTENDED -ErrorAction SilentlyContinue
  $env:FO4SF_PYTHON = $pythonPath                   # the guard's checker: a full path, never a name looked up later
  $env:FO4SF_OWNER_PRESENT = '1'                    # the guard adds agent_git.py; never set by run-lead.ps1
  $env:OPENCODE_DISABLE_EXTERNAL_SKILLS = '1'       # no skills from ~/.claude or ~/.agents (the claude.ai ones)
  $env:OPENCODE_DISABLE_CLAUDE_CODE_SKILLS = '1'    # the same switch under its older name
  $env:OPENCODE_CONFIG_CONTENT = (& $pythonPath $models opencode | Out-String).Trim()   # OpenCode's limits = the loaded window

  # npm installs a .ps1 shim; use the real binary behind it, as run-lead.ps1 does
  $opencode = Join-Path (Split-Path (Get-Command opencode).Source) 'node_modules\opencode-ai\bin\opencode.exe'
  if (-not (Test-Path $opencode)) { $opencode = 'opencode' }
  $argv = @()
  if ($Agent -ne 'fo4-lead') { $argv += @('--agent', $Agent) }
  if ($Continue) { $argv += '--continue' }
  "Type /help for OpenCode's commands, or /team, /board, /next, /research, /review, /handoff for the team's."
  "Answer a test run's prompt with Allow once: a test can run any code, and Allow always stops the asking."
  Set-Location $wt
  & $opencode @argv
} finally {
  Remove-Item -LiteralPath $mine -Force -ErrorAction SilentlyContinue
}
