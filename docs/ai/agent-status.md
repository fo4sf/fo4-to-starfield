# Agent status

**Not live.** Each line is a snapshot with its date and source; refresh from the source before relying on it.
Live sources: GitHub issue #32 and labels (`in-progress`, `blocked`, `needs-qa`), `git log origin/main`,
docs/CODEX-HANDOFF.md, and `python tools/ai-team/guardian/guardian.py status` for the local team.

| Agent | Role | Last known activity | Source, date |
|---|---|---|---|
| Claude (PC) | live game tests, integration, terrain/collision, pipeline | branch cleanup (160 deleted); installed Codsworth keeper mission + V111 start on core v6i; animated-doors port 07756819; probe P10 PASS / P9 INCONCLUSIVE; runner #558/#559 merged; launcher points at FO4 install | #32, 2026-10-28 |
| Claude-cloud | leader-core, multi-agent offline work | phase 0 done on owner's word, 24 Oct (all four gates 0-3 ticked); newgame_v11 review rounds 2-4 | #32, git log, 2026-10-29 |
| Codex (remote) | deployment/recovery, checkpoints, door bridge | idle ~24h; the six issues #457, #382, #367, #365, #280, #226 were delivered by 22 Oct and wait on review (#457 and #382 are audits; drafts #482, #368, #366, #281, #227; #382 answered); #562 is the lore inbox (second reads, new Commonwealth entries) | wake_agent status, GitHub labels, 2026-10-29 |
| Grok (remote) | acceptance/diagnostics; materials/textures, FLOR research, map markers | PC session idle ~5 days (last PC commit b63f7e30, 25 Oct); research on #579, #580 and #582-#586 through GitHub on 29 Oct; lore batch PR #544 (draft, not for merge) | wake_agent status, #32, GitHub, 2026-10-29 |
| ChatGPT (remote) | format research | no recent activity recorded in #32 | #32 scan, 2026-10-29 |
| fo4-lead (local) | supervisor | this cycle: refreshed agent-status; open items 36 grok / 70 codex / 49 claude (issues and PRs; the team board counts only the first 30 PRs, team.py:31) | GitHub labels, team.py:31, guardian.py status, 2026-10-29 |
| guardian (local) | admission control | level caution (RAM 87.5%, VRAM 90.7%), mode running; restrict at 88% RAM / 92% VRAM (model loaded), block at 90% RAM / 95% VRAM | guardian.py status, 2026-10-29 |
