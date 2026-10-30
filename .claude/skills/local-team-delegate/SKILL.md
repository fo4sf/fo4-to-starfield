---
name: local-team-delegate
description: Hand a job to the fo4 local AI team (Qwen in LM Studio, the OpenCode agents on the owner's PC) - write the brief, open or label the GitHub issue, or start one Lead session on the PC. Use when work fits the local team, such as docs/ai research, status refreshes or a small issue with an acceptance test.
---
# Hand the local team a job

The local team is the Lead, research, implementation and QA agents in OpenCode on the owner's PC, on a local model
behind the Resource Guardian (tools/ai-team/README.md). It suits:

- research questions (fo4-research writes docs/ai/research-log.md with method, evidence and class);
- refreshing docs/ai/agent-status.md from live sources;
- small, well-specified code issues with a synthetic-fixture test, run in the owner's terminal only (unattended runs
  never hand work to fo4-implement).

It does not suit anything that needs the game, a tool the guard does not allow, a push, a merge or a new PR.

## 1. Write the brief

One task: the issue number, the files it may change, the test it must add or pass, what it must not touch, and what
to report. A brief the local model has to interpret is a brief it will get wrong.

## 2. Hand it over

From anywhere (cloud or PC): open or update a GitHub issue with the brief, labelled `agent:local-team` and `ready`
(a research question also `spike`). The Lead's procedure picks ready issues with that label, and
`python tools/ai-team/team.py board` lists them as available. Point to it once on #32.

On the owner's PC, only when the owner asked for a session now, one unattended Lead session with the brief:

```
powershell -NoProfile -ExecutionPolicy Bypass -File tools\ai-team\run-lead.ps1 -MaxCycles 1 -Brief "Issue 123: <brief>"
```

It runs in the Lead's worktree with the guard on and skips if the game runs or the guardian is paused, blocked or
busy. The output lands in %LOCALAPPDATA%\fo4-ai-team\state\lead-session-<time>.log. Implementation work goes to the
owner's terminal instead (FO4SF AI menu, option 2, then `/next issue 123`).

## 3. Rules

- Never start the unattended Lead's cycles, pick a model or load one without the owner's word.
- The local team's output is a draft until a fresh review passes (the local-team-review skill).
- Codex and Grok are tasked through their own routes, not through the local team.
