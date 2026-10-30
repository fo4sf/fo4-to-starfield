# Local AI engineering team for fo4-to-starfield

A local OpenCode team (Lead + Implementation + Research + QA) running on one LM Studio model, behind a
**Resource Guardian** that deterministically limits local inference. Remote agents (Claude, Codex, Grok, ChatGPT)
keep working through GitHub. Architecture: [docs/ai/architecture.md](../../docs/ai/architecture.md).
Rules every agent follows: [AGENTS.md](../../AGENTS.md).

## Pieces and files

| What | Where |
|---|---|
| OpenCode project config (provider, default agent, permissions, `subagent_depth: 1`) | `opencode.json` (repo root) |
| Agents: `fo4-lead` (primary, default), `fo4-implement`, `fo4-research`, `fo4-qa` | `.opencode/agents/*.md` |
| Guardian settings + agent -> model aliases | `tools/ai-team/config.json` |
| Admission proxy (:1235 -> LM Studio :1234) | `tools/ai-team/guardian/proxy.py` |
| Status / report / pause / resume / stop / shutdown | `tools/ai-team/guardian/guardian.py` |
| Remote usage (Codex, Claude Code, Grok logs; GitHub activity) | `tools/ai-team/remote_usage.py` |
| Board + combined status | `tools/ai-team/team.py` |
| Wake an idle Codex / Grok (forks its last session, one headless turn; idle + cooldown guards) | `tools/ai-team/wake_agent.py` |
| Runtime state, history DB, logs (outside the repo) | `%LOCALAPPDATA%\fo4-ai-team\state\` (`guardian.db`, `proxy.log`; override with `FO4_AI_TEAM_STATE`) |
| Project knowledge, optimization log | `docs/ai/` (`optimization.md`: baselines + before/after entries) |
| Model picker (presets in `config.json` "models", or any downloaded model; the proxy and OpenCode follow the pick) | `tools/ai-team/models.py` |
| The FO4SF AI desktop menu, the agents' terminal, the shortcut maker | `tools/ai-team/menu.ps1`, `terminal.ps1`, `install-shortcut.ps1` |
| Shell and file-write guard (allow-list checker + OpenCode plugin) | `tools/ai-team/guard/allowlist.py`, `.opencode/plugin/fo4-guard.js` |
| The implementation agent's branch and commit wrapper (owner's terminal only) | `tools/ai-team/agent_git.py` |
| The team's slash commands and its one skill (other skills are hidden from it) | `.opencode/commands/*.md`, `.opencode/skills/fo4-allowed-commands/` |
| Claude Code skills for working with the team: delegate, check, review, models | `.claude/skills/local-team-*/` |

## Start

The FO4SF AI desktop shortcut does all of this from one menu (next section). By hand:

1. LM Studio server on (`lms server start` or the app), Starfield closed. Pick and load the model:
   `python tools\ai-team\models.py pick qwen3.6-35b` (the default: 64K context, K/V cache unquantized, LM Studio
   places the layers, no memory mapping), `qwen3.6-35b-128k` (the long window), `qwen3-14b` (the fallback: 32K, all on
   the GPU, q8 K/V cache), or any downloaded model with `pick --model <id> --context <tokens>`. The pick is saved in the
   state dir: the guardian proxy sends every agent to it, and terminal.ps1 and run-lead.ps1 hand its context and output
   limits to OpenCode (`OPENCODE_CONFIG_CONTENT`), so `opencode.json` no longer needs local edits for another window.
   `pick` refuses while requests run, pauses the guardian during the load and unloads the team's other models first
   (only ids a preset names). `load_model.py` still loads one model by hand. It needs LM Studio 0.4.27 or newer: the
   0.3.30 runtime (llama.cpp 1.104.2) rejects the model's `qwen35moe` architecture, the llama.cpp 2.66.0 runtime loads it.
   Don't use `lms load`: it memory-maps the file and holds ~10 GB of system RAM, which makes the guardian block
   (2026-10-29: 16K context reached 98.5% RAM with `lms load`, 78.3% without memory mapping).
2. `powershell -File tools\ai-team\start-team.ps1`: starts the guardian proxy, checks LM Studio, prints status.
3. Interactive: `powershell -File tools\ai-team\terminal.ps1` (next section). Unattended: `powershell -File tools\ai-team\run-lead.ps1`:
   one Lead session per cycle (default 30 min) in its own worktree (branch `ai/local-lead`); skips while Starfield runs or
   the guardian is paused/blocked; loads the picked model if LM Studio unloaded it (`models.py ensure`). `-MaxCycles 1
   -Brief "<task>"` runs one session on one task. Log `lead-cycles.log` in the state dir.
   One OpenCode session at a time.

## The FO4SF AI menu and the agents' terminal

`powershell -File tools\ai-team\install-shortcut.ps1` puts an "FO4SF AI" shortcut on the desktop (run once). It opens
`menu.ps1`: start the local team, talk to the Lead or one agent, start Claude Code in the repo (Opus, Sonnet or Haiku),
status, pick a model, start the unattended Lead in its own window, pause or resume, stop.

The agents' terminal (`terminal.ps1 [-Agent fo4-research] [-Continue]`) is OpenCode's own terminal UI. It starts the
team, then opens in its own worktree next to the repo (`fo4-to-starfield-wt\local-terminal`, branch
`ai/local-terminal`; a clean one follows main), so the main checkout and the unattended Lead are never touched. The
guard checks every command and write as in unattended runs. Because the owner is watching, it also allows
`agent_git.py`: the implementation agent makes its own `ai/<issue>-<slug>` branch and commits named files there, with
no hooks, never on `ai/local-lead`, never a push. Skills from `~/.claude` and `~/.agents` (the claude.ai ones) are
hidden (`OPENCODE_DISABLE_EXTERNAL_SKILLS`, and `permission.skill` allows only `fo4-*`).

The team's commands in the terminal: `/status`, `/board`, `/next [focus]` (one Lead session; it asks before handing
work to fo4-implement), `/research <question>`, `/review <PR number>` (QA, no edits, no posts), `/handoff <what>`
(a `Lead (local): for Claude:` comment on #32 that Claude reads). Claude's side is in `.claude/skills/`:
`local-team-delegate` (issue labelled `agent:local-team` + `ready`, or one `run-lead.ps1 -Brief` session on the PC),
`local-team-check` (#32, logs, local branches), `local-team-review` (local output is a draft until it passes),
`local-team-models`.

Local inference is **blocked while Starfield runs** (the GPU is needed for game tests). Close the game first.

## Status, usage, logs

- `python tools\ai-team\team.py status`: hardware, guardian level/mode, running and queued jobs, recent failures,
  local usage per agent, remote usage, warnings (JSON).
- `python tools\ai-team\team.py board`: GitHub tasks by state (live).
- `python tools\ai-team\guardian\guardian.py status`: just the guardian (exit code 0 ok, 1 restrict, 2 block).
- `python tools\ai-team\guardian\guardian.py report --hours 24`: local requests, tokens, latency, throttling.
- Logs: `%LOCALAPPDATA%\fo4-ai-team\state\proxy.log` (every non-admit decision and job end), `state\guardian.db` (SQLite:
  `jobs`, `decisions`, `samples`, `control`); OpenCode's own logs: `opencode --print-logs`.

## Pause, resume, stop

- Pause (queued and new requests wait, running ones finish): `python tools\ai-team\guardian\guardian.py pause`
- Resume: `... guardian.py resume`
- Graceful shutdown: `powershell -File tools\ai-team\stop-team.ps1`
- Emergency stop (refuse everything at once, then shut down): `... stop-team.ps1 -Emergency`, afterwards
  `guardian.py resume` before the next start. Model unload is manual (`lms unload --all`), never automatic.
- After a crash: start again; jobs left "running"/"queued" are marked `abandoned` (restart recovery).

## What is enforced, and what isn't

Enforced by code (proxy): max 1 concurrent local inference request; resource check before each admission
(RAM 70/89/90%, VRAM 95% block, 94% restrict with a resident model, otherwise the same 89% restrict level also applies to VRAM, game running = block, LM Studio down =
block); queue with a bounded wait (600 s) then HTTP 503; bounded upstream retries (2, backoff 2 s / 4 s) only
before any output was sent; request timeout 900 s; pause / stop switch; every decision logged.
Resources are sampled fresh at every admission attempt (`proxy.py`, `_wait_for_admission`), not taken from an
earlier status call; a queued job re-checks every 2 s. A job that is already running is not interrupted if the game
starts or memory rises afterwards: only new admissions are held.
Enforced by OpenCode config: agent permissions (no push/merge/destructive commands, Lead edits only docs/ai,
QA edits nothing, Research edits only its two docs), Lead may delegate only to the three specialists,
specialists cannot delegate (`task: deny`, `subagent_depth: 1`).

**Not controlled** (bypasses): LM Studio's chat UI or anything calling :1234 directly; the remote agents (Claude,
Codex, Grok, ChatGPT) and their subscriptions; OpenCode's built-in `explore`/`general` subagents are available
to manual `@` use. Remote usage figures are read from local session logs where they exist (Codex also writes its
plan's rate-limit percentages); nothing is invented, ChatGPT shows as unavailable.

## GitHub workflow

Issues = tasks (labels `ready`, `in-progress`, `blocked`, `spike`, `needs-qa`, `review`); comments carry progress,
each starting with the role (`Lead (local):`, `QA (local):`, `Claude:`, ...); substantial work on a branch
`ai/<issue>-<slug>` in its own worktree (`git worktree add ../fo4-to-starfield-wt/<name> -b ai/<issue>-<slug>`);
PR for review; QA review before merge; merging and pushing need the owner's approval. Labels can be stale; the Lead
also reads #32 and docs/CODEX-HANDOFF.md.

## Manual operations

Choosing/downloading/loading the model; starting LM Studio; starting OpenCode; approving PR creation, merges and
pushes; any game deployment or live testing (Claude's lane); installing anything as a service (not done).

## Model change (2026-10-29, Qwen3.6-35B-A3B Q4_K_M, 128K context)

Measured on the team PC (32 GB RAM, RTX 4070 Ti 12 GB), LM Studio 0.4.27, with memory mapping off, the K/V cache
unquantized and flash attention left at LM Studio's default. `load_model.py` now forces flash attention on, so these
numbers need a re-measure. Each size was loaded in ~17 s and answered a short prompt:

| Context | RAM peak | VRAM peak | Short prompt |
|---|---|---|---|
| 16K | 78.3% | 10.1 GB | 24.6 tok/s, first token 0.40 s |
| 32K | 79.1% | 10.3 GB | 25.0 tok/s, first token 0.37 s |
| 64K | 79.9% | 10.6 GB | 25.4 tok/s, first token 0.41 s |
| 128K | 83.4% | 10.9 GB | 24.5 tok/s, first token 0.43 s |

128K is the model card's advice for keeping its thinking; 256K would need ~4 GB more and cross the guardian's 90% RAM
block. The model thinks before every answer (3,000-6,300 reasoning tokens on 1.5-4K-token prompts, ~20 tok/s);
with `chat_template_kwargs: {"enable_thinking": false}` LM Studio still returned reasoning (316 tokens against 733
on the same short prompt). The LM Studio SDK's default idle TTL (1 h, `DEFAULT_TTL` in the SDK) can unload the model
between cycles (after an hour idle, for example during a failure back-off or a pause); `run-lead.ps1` reloads it at
`load_model.py`'s default. The TTL is kept on purpose: it frees the GPU
for game tests when the team is idle.

The default went to 64K the same evening (owner's word): at 128K, once the Lead worked, the PC sat at 87-91% RAM and
92.5% VRAM, the guardian held the Lead's requests, and two Lead sessions failed (16:00 and 16:54 local). At 64K it sat
at 78.8% RAM and 10.6 GB VRAM idle after the load, and up to 90.3% RAM / 10.85 GB VRAM while the Lead worked (one
request held briefly at 19:43 local), so holds are rarer, not gone. OpenCode compacts a session at its context minus
the output limit (`limit.output` 16384, so about 49K tokens); the Lead's sessions reached 46K tokens at 128K. `opencode.json`'s `headerTimeout` (900000 ms, #600) lets a
request outlast the guardian's 600 s hold, and the Lead stays in its own worktree (#602). OpenCode checks each
command of a pipeline, so `gh issue view 32 | head -200` is refused at `head`; `run-lead.ps1`'s prompt tells the Lead
to run gh and git without pipes. The filters are not allowed on purpose: with a path argument they would read files
outside the worktree. Any command containing `>`, `--output` or `--no-index` is denied: these three are the last
bash rules of the global block and of every agent file (OpenCode takes the last matching rule, reads the agent file
after the global block, and matches a redirect as part of the command's text). That blocks the plain forms an
independent review found behind the allowed git commands (`cmd > file`, git's `--output=<file>`, an explicit
`git diff --no-index`). It does not make the shell safe: the rules see single command nodes, so some command shapes
and settings are never checked, and a plain two-path `git diff` reads files outside the repo. **The unattended Lead
reads public issues, so it runs only with the shell guard below in place, and the Lead stays paused until the owner
decides the guard is installed and checked on the PC.** The Lead commits its own
`docs/ai` edits only through `python -I tools/ai-team/lead_commit.py "<what changed>"`, which refuses unless the branch
is `ai/local-lead`, nothing is unmerged, no merge/rebase is in progress and nothing outside `docs/ai/` is staged
(a rename counts as its source too). It still cannot push, and `gh pr review` and `gh pr comment` are denied; it
comments only on #32. `run-lead.ps1` logs a failed pull of main and skips the cycle while the Lead's worktree has
unmerged files or is not on `ai/local-lead`, so a conflict or a moved worktree waits for a person. The `>` deny
also refuses a `>` inside quoted text (a #32 comment with "RAM > 85%"); the prompt tells the Lead to avoid the
character. fo4-implement may still edit any file through its edit permission; the unattended Lead's prompt keeps it
from delegating to fo4-implement (prompt only: `task` still allows it).

### The shell guard

OpenCode's bash rules match text, one pattern at a time, so some command shapes get past any list of patterns. The
guard is a second layer that allows only exact argument lists. `.opencode/plugin/fo4-guard.js` sends each shell call
to `tools/ai-team/guard/allowlist.py` on stdin, and a call goes ahead only if the checker exits 0; a missing Python, a
timeout or unreadable output all refuse. The checker tokenizes the command the way bash and PowerShell read quotes,
refuses every shell metacharacter and expansion outside quotes, refuses `$`, backticks, backslashes, `!` and quote
characters inside quotes, and refuses an unquoted comma. Commands run from the repo root only: a workdir anywhere
else is refused, a subfolder too, because the agents can write under `docs/ai/` and relative script paths, git's repo
discovery, gh's choice of repo and unittest discovery all follow the working directory. It then accepts only:
`gh issue list|view`, `gh pr list|view|diff` (read-only, numbers and the listed flags), `gh issue comment 32 --body
"Lead (local): ..."`; `git status`, `git log`, `git diff`, `git show`, `git worktree list`, `git branch --show-current`
and `git rev-parse` with the listed switches, revisions before `--`, and repo-relative paths after it; `python -I
tools/ai-team/lead_commit.py "<message>"`; `guardian.py status|report`; `team.py board|status`; `scripts/guard.py`; and
`python -m unittest` on `tests.<module>` names or as `discover -s tests`. Everything else is refused, including `git
push`, any `gh` write other than the #32 comment, `wake_agent.py`, and `python -c`. In unattended runs (`run-lead.ps1`
sets `FO4SF_UNATTENDED=1`) the plugin also refuses a `task` call to fo4-implement, which can edit code and then run the
tests it edited; until now only the prompt kept the Lead from doing that. Left open on purpose: the #32 comment body is
free text up to 1500 characters, so anything the Lead can read inside the repo could be posted there. The repo is
public, and reads outside it stay refused.

Two grants are narrowed on purpose. `wake_agent.py codex|grok` is refused: it starts an agent with approvals on a
brief, which the unattended Lead may not do, and the owner decides whether it may. `team.py *` is now `board` and
`status`, the only two subcommands it has. Tests: `tests/test_ai_guard.py`. The guard is one layer: the OpenCode rules
above stay in place, and both must allow a call.

File writes go through the same checker: the plugin sends the paths of every `edit`, `write`, `multiedit`, `patch`
and `apply_patch` call (a patch's paths from its `*** ... File:` lines; a write that names no file is refused). It
refuses a write outside the repo and a write to the team's own rules, tools and instructions: `.opencode/`, `.claude/`,
`.agents/`, `.git/`, `.github/`, `tools/ai-team/`, `opencode.json`, `AGENTS.md`, `docs/CODEX-HANDOFF.md` and
`scripts/guard.py`, compared without case, as Windows does. The agents' edit rules already deny most of these; the
check holds where a rule pattern misses a spelling, and it covers the checker itself. In the owner's terminal only
(`terminal.ps1` sets `FO4SF_OWNER_PRESENT=1`; the plugin ignores it when `FO4SF_UNATTENDED=1`), the checker also allows
`python -I tools/ai-team/agent_git.py branch ai/<name>` and `... commit "<message>" <paths>`, and the wrapper refuses
on its own in an unattended run, on `ai/local-lead`, off an `ai/` branch, and for a protected path. `models.py list`
is allowed everywhere (read only).

## Validation (2026-10-09, Qwen3-14B Q4_K_M, 32K context)

| # | Test | Result |
|---|---|---|
| 1 | LM Studio API responds | pass |
| 2 | OpenCode connects to the model (via the guardian) | pass |
| 3 | Model performs a real tool call (`file_size` with correct args) | pass, 10.4 s, 174/147 tokens |
| 4 | Lead invokes a specialist (`task` -> fo4-research) | pass |
| 5 | Research reads project files (exact first heading of docs/PLAN.md) | pass, whole run 231 s |
| 6 | Implementation works in an isolated test branch (`ai/test-validation`, own worktree) | pass |
| 7 | QA reviews without modifying (its edit attempt was refused by permissions) | pass, whole run 522 s |
| 8 | `gh` reads repository issues | pass |
| 9 | Resource monitoring returns valid JSON | pass |
| 10 | Thresholds trigger the expected scheduling (4 unit tests + live) | pass |
| 11 | Overloaded system queues new work (game running; RAM 88-90%; 1 running >= max 1) | pass |
| 12 | Logs record the activity (26 requests with API token counts, 8 throttling decisions) | pass |
| 13 | Shutdown leaves no orphaned jobs or processes | pass |

Observed: each Lead step takes ~40-135 s; Qwen3 writes long `<think>` reasoning first (next optimization
candidate: measure with thinking off). The Lead once mis-formatted a task call and corrected itself.

## Tests
`python -m unittest tests.test_ai_guardian` (admission policy on synthetic snapshots) and
`python -m unittest tests.test_ai_team_defaults` (the agents' model, the Lead's loaded-model check and the load
settings agree); validation results of the
initial setup are in docs/ai/decisions.md and the setup report.
