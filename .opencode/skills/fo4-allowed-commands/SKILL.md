---
name: fo4-allowed-commands
description: "The exact shell commands the fo4 team's guard lets through, and how to write a command so it is not refused. Load it before your first command in a session, and after any guard refused the command error."
---
Every shell command goes through the guard (tools/ai-team/guard/allowlist.py), in the unattended runs and in the
owner's terminal alike. It runs commands from the repo root only and allows exactly the shapes below. Anything else is
refused, however it is written, so do not retry a refused command in another spelling: use a shape from this list, or
say what you need and stop.

## Allowed shapes

```text
gh issue list --state open --label agent:local-team --limit 20
gh issue view 32 --comments
gh pr list --state open
gh pr view 605 --json 'title,state,files'
gh pr diff 605 --name-only
gh pr checks 605
gh pr view 605 --json statusCheckRollup
gh issue comment 32 --body 'Lead (local): CI on 605 is green, ready for review'
git status --short
git log --oneline -10
git log --oneline origin/main..HEAD
git diff --stat origin/main
git diff -- docs/ai/agent-status.md
git show --stat HEAD
git branch --show-current
python tools/ai-team/team.py status
python tools/ai-team/team.py board
python tools/ai-team/guardian/guardian.py status
python tools/ai-team/models.py list
python -m unittest discover -s tests
python -m unittest tests.test_ai_guard
python scripts/guard.py
python -I tools/ai-team/lead_commit.py 'Lead (local): refresh agent status'
```

The unattended Lead commits its docs/ai notes with lead_commit.py, on its branch ai/local-lead only.

In the owner's terminal only, the implementation agent also has the commit wrapper. The Lead's docs/ai notes are
committed there only when the owner approves the call at OpenCode's prompt. The terminal starts on main with no branch:
make the task's branch first (it starts from main), then commit there; the same `branch` command with an existing
name switches back to that branch. A commit message starts with your own tag (`Implement (local): `,
`Lead (local): `). In the terminal OpenCode asks the owner before each `python -m unittest` run while the owner answers
Allow once (Allow always, or auto-accept, stops the asking until OpenCode exits).
Only this terminal can post a #32 comment that starts `Lead (local): for Claude:` (the /handoff command).

```text
python -I tools/ai-team/agent_git.py branch ai/123-short-name
python -I tools/ai-team/agent_git.py commit 'Implement (local): what changed' src/module.py tests/test_module.py
```

## Refused, and what to do instead

- Pipes, redirects, `;` and `&&`: run each command on its own and read its whole output (`git log --oneline -20`,
  not `git log | head`).
- An unquoted comma: quote the value (`--json 'title,state'`).
- A quote mark, apostrophe, dollar sign, backslash, exclamation mark, backtick, ampersand, pipe, caret, percent
  sign or angle bracket inside a quoted value, or the character > anywhere: write the text without them.
- `cd`, or a working directory other than the repo root: run from the root with relative paths.
- `git add`, `git commit`, `git switch`, `git push`: use the wrappers above. Nobody on the team pushes.
- A GitHub comment anywhere but #32, a review approval, a merge, `gh api`: not for the team.
- Other programs (curl, rm, powershell, cmd, node, pip): say what you need; the owner decides.
- Writing files under .opencode/, .claude/, .github/, tools/ai-team/, or to opencode.json, AGENTS.md,
  docs/CODEX-HANDOFF.md or scripts/guard.py: the team's own rules and tools are changed by people, not by an agent.
