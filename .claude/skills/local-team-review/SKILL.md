---
name: local-team-review
description: "Review work by the fo4 local AI team before any of it is kept - diff its branch against main, rerun the tests and the repo guard, check each claim against its source, and report findings with severity. Local-team output stays a draft until this review passes."
---
# Review the local team's work

1. Get the change. On the PC: `git diff origin/main...ai/<branch>` and `git log --oneline origin/main..ai/<branch>`.
   From the cloud: what was posted on #32, or the PR the owner opened from it.
2. Check the scope against the brief: only the files it allowed. A change under .opencode/, .claude/, .github/,
   tools/ai-team/, or to opencode.json, AGENTS.md, docs/CODEX-HANDOFF.md or scripts/guard.py means a write got past
   the guard: report it as high and say so to the owner.
3. Run `python -m unittest discover -s tests` and `python scripts/guard.py` on the branch, and quote any failure.
4. Research: every finding in docs/ai/research-log.md carries a method, evidence and a class (verified, supported
   hypothesis, unresolved). Check the evidence. A hypothesis stated as fact about Fallout 4 or Starfield formats is a
   finding.
5. Code: the acceptance test exists and fails without the change; edge cases; no format assumption without a
   research-log entry.
6. Report each finding with its severity, file and line, and the input that makes it fail, then say plainly whether
   the work is clear. Do not fix it in the same pass: a fix is new work, for the team or for Claude with the owner's
   OK.
7. Keeping it is the owner's call. A PR made from local-team work needs this review and green CI like any other PR.
