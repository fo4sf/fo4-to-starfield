---
name: local-team-check
description: See what the fo4 local AI team did - its #32 comments and handoffs, the Lead's cycle and session logs, its local branches and commits, and the guardian's status. Use before reviewing local-team work, or when the owner asks what the local agents did.
---
# Check what the local team did

## From anywhere (GitHub)

- #32: comments starting `Lead (local):`, newest first. `Lead (local): for Claude:` is a handoff to you (the owner
  ran /handoff in their terminal): what was asked, what was done, what is open, and the next step for Claude.
- Issues labelled `agent:local-team`: state, labels (`in-progress`, `blocked`), comments.
- The team pushes nothing, so its commits exist only on the PC.

## On the owner's PC (Claude Code in the repo)

```
python tools/ai-team/team.py status
python tools/ai-team/models.py list
git worktree list
git log --oneline origin/main..ai/local-lead
git log --oneline origin/main..ai/local-terminal
```

The state folder %LOCALAPPDATA%\fo4-ai-team\state holds lead-cycles.log (one line per cycle: started, skipped and
why, done, failed), lead-session-<time>.log and .err (one session's output) and proxy.log (the guardian's decisions).
The worktrees sit next to the repo: fo4-to-starfield-wt\local-lead (the unattended Lead) and
fo4-to-starfield-wt\local-terminal (the owner's terminal), plus any ai/<issue> branches the implementation agent made.

## Report

What was asked, what was done (commits, files, comments, with ids), what failed or was skipped and why, and what
waits on whom. Quote log lines and numbers as they are; do not round or paraphrase them.
