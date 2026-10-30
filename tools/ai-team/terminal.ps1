# Open the local agents' terminal: OpenCode's own terminal UI on the team's agents, for the owner to talk to.
#   powershell -ExecutionPolicy Bypass -File tools\ai-team\terminal.ps1 [-Agent fo4-lead] [-Continue]
# It starts the team (guardian proxy, picked model), then runs OpenCode in its own worktree next to the repo
# (fo4-to-starfield-wt\local-terminal, branch ai/local-terminal), so the main checkout and the unattended Lead's worktree
# are never touched. The guard plugin checks every command and file write as in unattended runs; because the owner is
# present, it also lets the implementation agent make its own ai/ branch and commit there (agent_git.py). Nothing
# pushes. Skills from ~/.claude and ~/.agents (the claude.ai ones) stay hidden from the agents.
param([string]$Agent = 'fo4-lead', [switch]$Continue,
      [string]$Python = $(if ($env:FO4SF_PYTHON) { $env:FO4SF_PYTHON } else { 'python' }))
$repo = Split-Path (Split-Path $PSScriptRoot)
$Host.UI.RawUI.WindowTitle = "FO4SF local agents ($Agent)"
$models = Join-Path $PSScriptRoot 'models.py'

powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'start-team.ps1')
$ensure = (& $Python $models ensure | Out-String).Trim()
if ($LASTEXITCODE -ne 0) { "WARNING: the picked model is not loaded ($ensure). Pick one in the FO4SF AI menu." }
else { try { "model: $(($ensure | ConvertFrom-Json).picked.model)" } catch { $ensure } }

$wt = Join-Path (Split-Path $repo) 'fo4-to-starfield-wt\local-terminal'
git -C $repo fetch -q origin main
if (-not (Test-Path $wt)) {
  if (git -C $repo branch --list ai/local-terminal) { git -C $repo worktree add $wt ai/local-terminal | Out-Null }
  else { git -C $repo worktree add -b ai/local-terminal $wt origin/main | Out-Null }
  "made the terminal's worktree $wt (branch ai/local-terminal)"
} elseif (-not (git -C $wt status --porcelain) -and "$(git -C $wt rev-parse --abbrev-ref HEAD)".Trim() -eq 'ai/local-terminal') {
  git -C $wt merge -q --ff-only origin/main 2>$null                    # a clean worktree follows main
  if ($LASTEXITCODE -ne 0) { "note: ai/local-terminal has its own commits, so it stays where it is" }
} else {
  "note: $wt has changes or another branch checked out ($("$(git -C $wt rev-parse --abbrev-ref HEAD)".Trim())); left as it is"
}

foreach ($f in @('.opencode\plugin\fo4-guard.js', 'tools\ai-team\guard\allowlist.py')) {
  if (-not (Test-Path (Join-Path $wt $f))) { "$wt has no $f, so the guard would be off: not starting"; exit 1 }
}
if (-not (Get-Command opencode -ErrorAction SilentlyContinue)) { "OpenCode (opencode) is not on PATH"; exit 1 }

Remove-Item Env:FO4SF_UNATTENDED -ErrorAction SilentlyContinue
$env:FO4SF_OWNER_PRESENT = '1'                      # the guard adds agent_git.py; never set by run-lead.ps1
$env:OPENCODE_DISABLE_EXTERNAL_SKILLS = '1'         # no skills from ~/.claude or ~/.agents (the claude.ai ones)
$env:OPENCODE_DISABLE_CLAUDE_CODE_SKILLS = '1'      # the same switch under its older name
$env:OPENCODE_CONFIG_CONTENT = (& $Python $models opencode | Out-String).Trim()   # OpenCode's limits = the loaded window

# npm installs a .ps1 shim; use the real binary behind it, as run-lead.ps1 does
$opencode = Join-Path (Split-Path (Get-Command opencode).Source) 'node_modules\opencode-ai\bin\opencode.exe'
if (-not (Test-Path $opencode)) { $opencode = 'opencode' }
$argv = @()
if ($Agent -ne 'fo4-lead') { $argv += @('--agent', $Agent) }
if ($Continue) { $argv += '--continue' }
"Type /help for OpenCode's commands, or /status, /board, /next, /research, /review, /handoff for the team's."
Set-Location $wt
& $opencode @argv
