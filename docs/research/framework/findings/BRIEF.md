# Brief for every framework research agent (2026-10-19)

You are one of several research agents building a **framework of questions and possibilities for the next phases** of
fo4-to-starfield, a project that converts Fallout 4 (Creation Engine 1) into Starfield's engine (Creation Engine 2)
through a GAMMA-style launcher that ships no game assets: the player must own both games and the conversion runs on
their PC. Repo checkout (read-only for you): the repo checkout.

Phase order the owner approved: (1) new game start, a Vault 111 start with no Starfield intro; (2) door enter and exit
animations; (3) all interiors; (4) the launcher. After that the order is open: world breadth (the Commonwealth, Far
Harbor and Nuka-World on ONE Earth-like planet with real days, nights and weather), people and story (quests, dialogue,
companions), Fallout systems (Pip-Boy, VATS, workshop, power armor, perks, radio). Settled: silent player by default;
Starfield's own animations first, FO4 clips later; SFSE and the free Starfield Creation Kit MAY be required; GitHub
release first, then Nexus (GPL-3 notice for Mutagen); breadth before polish. The owner may later add other Fallout
games (FO3, New Vegas) on the same core.

## Rules
- Research on the web (load WebSearch and WebFetch with ToolSearch "select:WebSearch,WebFetch"). Prefer primary sources:
  official docs, tool repos and READMEs, Nexus pages, project wikis/FAQs, Bethesda pages, developer posts.
- Every claim gets a label: **verified** (you read it in a linked source or a file), **supported hypothesis**,
  **unresolved**. Never state a game fact, tool capability or console command you did not read in a source; mark
  inferences as inferences. Give the URL for every verified claim.
- Read the project notes named in your task first, and do NOT repeat what they already establish; go deeper, verify,
  correct, or extend. If you find a project note is wrong, say so in a "Corrections" section with the source.
- Offline research only. Do not install anything, do not use any mcp__remote-devices__ or mcp__hearthbot__ tools,
  do not write to GitHub, do not run anything against a game.
- /mnt/project-files is a shared network mount: write ONLY your own output file, never search the whole folder's
  contents (read named files only). After writing, wait ~10 s and read your file back to confirm it saved.

## Output file (Markdown, in /mnt/project-files/research/framework/findings/<your-name>.md)
1. `# <Area>`: one-paragraph bottom line.
2. `## Findings`: what you learned, labelled, with sources.
3. `## Precedents and what they teach us` (where relevant).
4. `## Risks` (what could sink or stall us, with likelihood reasoning).
5. `## Questions for the framework`: the core deliverable. Numbered questions grouped by where they bite (New game,
   Door animations, All interiors, Launcher, World and planet, People and story, Fallout systems, Release and
   community, Tooling and testing, Cross-cutting). For each: the question; why it matters; the options or
   possibilities you found (with sources); what evidence or experiment would answer it; who could answer (owner
   decision, offline research, a PC probe, a community contact). Aim for depth: 20 to 40 good questions.
6. `## Sources`: every URL.

Return to your caller a summary under 300 words: the 10 most important questions and any surprising facts.
