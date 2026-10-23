# Brief for framework synthesis agents (2026-10-19)

You turn raw research findings into ONE cross-cutting framework file in /mnt/project-files/research/framework/.
Read /mnt/project-files/research/framework/findings/BRIEF.md for the project context first. No web research: work
only from the findings files named in your task (and project notes they cite). Do not drop sources or evidence labels.

## Rules
- Keep every claim's label (**verified** / **supported hypothesis** / **unresolved**) and its source link. Never add a
  game fact, tool capability or console command that is not in the findings.
- Merge duplicate questions across findings files into one; keep the strongest evidence; note "(also: <file> Qn)".
- Questions that belong to a phase file owned by another thread (newgame.md, door-animations.md, interiors.md,
  launcher.md, engine-mechanics.md) still go in your file if they are cross-cutting; otherwise list them briefly under
  "Handed to phase files" with a pointer, so nothing is lost. Never edit those five files.
- Plain, short sentences. Tables where they help. No em-dashes.
- Shared network mount: write only your own file. After writing, wait ~10 s and read the top back to confirm.
- Do not use mcp__hearthbot__ or mcp__remote-devices__ tools, GitHub, or installs.

## File layout (exactly these sections)
1. `# <Area>`, then a line: `Part of the [next-phase framework](README.md). Wave 1, 2026-10-19. Sources: findings/<files>.`
2. `## In short`: 5 to 8 lines: what we now know, what is most uncertain, the 3 decisions that unlock the most.
3. `## What is settled` (owner decisions and verified facts that close questions; cite).
4. `## Possibilities`: the option space per sub-area, as tables: option, what it gives, cost or risk, precedent, evidence label.
5. `## Questions`: numbered with stable IDs `<PREFIX>-NN` (prefix given in your task). Group by sub-area. Each question:
   - **Question** (one line, bold)
   - Why it matters (one or two lines)
   - Options (short, with sources)
   - Answer by: what evidence or experiment; who (owner decision / offline research / PC probe / community contact /
     Bethesda or Nexus contact)
   - Blocks: which phase or later work waits on it (New game, Door animations, All interiors, Launcher, World, People
     and story, Fallout systems, Release, Multi-game)
   - Status: `open` (all are open in wave 1 unless a finding already answers it; then `answered: ...` with source)
6. `## Owner decisions in this area`: the subset of questions only the owner can decide, one line each with the
   recommended default and why (mark it as a recommendation).
7. `## Cheapest experiments`: bounded probes that would close several questions at once (offline first, then PC
   read-only probes), each with the question IDs it closes. Nothing here runs now; it is a list.
8. `## Gaps for wave 2`: what the findings could not verify (search budget ran out), as research tasks.
9. `## Handed to phase files`: pointers (question text, target file).
10. `## Sources`: all URLs used, deduplicated.

Return to your caller under 200 words: counts of questions, the owner decisions, the top 3 experiments.
