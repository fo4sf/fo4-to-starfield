# Agent status

**Not live.** Each line is a snapshot with its date and source; refresh from the source before relying on it.
Live sources: GitHub issue #32 and labels (`in-progress`, `blocked`, `needs-qa`), `git log origin/main`,
docs/CODEX-HANDOFF.md, and `python tools/ai-team/guardian/guardian.py status` for the local team.

| Agent | Role | Last known activity | Source, date |
|---|---|---|---|
| Claude (PC) | live game tests, integration, terrain/collision, pipeline | branch cleanup (160 deleted); installed Codsworth keeper mission + V111 start on core v6i; animated-doors port 07756819; probe P10 PASS / P9 FAIL; runner #558/#559 merged; launcher points at FO4 install | #32, 2026-10-28 |
| Claude-cloud | leader-core, multi-agent offline work | phase 0 done on owner's word (gates 1+2 ticked); newgame_v11 review rounds 2-4 | #32, git log, 2026-10-28 |
| Codex (remote) | deployment/recovery, checkpoints, door bridge | idle ~24h; owns audits on #457, #382, #367, #365, #280, #226; draft PR #562 lore recovery | wake_agent status, 2026-10-29 |
| Grok (remote) | materials/textures, FLOR research, map markers | idle ~5 days; completed gwe lore batch (PR #544); added bgsm-summary CLI; offline since Oct 24 | wake_agent status, #32, 2026-10-29 |
| ChatGPT (remote) | format research | no recent activity recorded in #32 | #32 scan, 2026-10-29 |
| fo4-lead (local) | supervisor | this cycle: refreshed agent-status; team board shows 18 grok / 21 codex / 28 claude open items | team.py board, guardian.py status, 2026-10-29 |
| guardian (local) | admission control | level caution (RAM 87.5%, VRAM 90.7%), mode running; restrict at 88% RAM / 92% VRAM (model loaded), block at 90% RAM / 95% VRAM | guardian.py status, 2026-10-29 |
