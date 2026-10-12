# Decisions (local AI team)

Format: date, decision, why, alternatives considered.

## 2026-10-11 Ground-texture experiment as a five-step ladder at a daylight site (Claude)
exp2t is staged as five variants that each change one thing against the previous one (t0 control: exp2b2's BTD;
ta: exp2b2's 7-entry template + 4 LTEX that vanilla gameplay tables carry, 11 entries; tb: as ta with 4 LTEX no BTD
uses; tc: template + full mapping, 31; t: full mapping, 24, no placeholders), all registered on Mars at exp1's site
(0.2, 1.2) instead of exp2b2's (0.3, -1.2). Run t0, ta, t; tc and tb only if t differs from ta. Why: every vanilla
table carries the six placeholders and at most 18 entries, so a single exp2t run could not tell which departure
broke it; and every run at exp2's longitude arrived at night, which hides colour and tint. Alternatives: one run
with the full mapping (cannot attribute a failure), a full factorial (8 runs), a game-hour step in the runner (whether
`set gamehour` moves the sun on a planet is untested, and the runner lives on the test-queue branch). Evidence:
docs/terrain/ground-textures.md 2.2 and 5.

## 2026-10-11 FO4 ground textures: vanilla Starfield land textures first, new terrain materials later (Claude)
The Commonwealth BTD carries FO4's ground textures as vanilla `Starfield.esm` LTEX in its LTEX table: every FO4 land
texture maps to one of 27 Earth-like vanilla LTEX by hand category + nearest average colour, reviewed by eye
(`src/fo4sf/ground_map.py`). Why: vanilla BTDs already name concrete LTEX (akilacity, overlay traits; always next to
the six placeholders, in tables of at most 18 entries, see the ladder entry above), so it needs no plugin record
and no new material; all 27 materials exist in the run-time material database. Alternatives: new LTEX
+ `.mat` from converted FO4 textures (no official plugin adds an LTEX; a BTD table has no master list, so a plugin
FormID would bake in a load-order byte; terrain material loading from a plugin archive is untested) and the six
`LDefault*` placeholders (they take the planet's look, the opposite of the goal). Revisit after exp2t runs. Evidence:
docs/terrain/ground-textures.md.

## 2026-10-11 FO4 terrain heights: own Python reader following fo4land, Mutagen as the cross-check (Claude)
`src/fo4sf/fo4land.py` reads LAND/VHGT with the algorithm of fo76utils `fo4land` (MIT); `dotnet/Fo4Land` decodes the
same cells through Mutagen as a second, independent parse. Why: fo4land needs scons + a C++ compiler, which this
machine lacks and the rules forbid installing; its output is 16-bit normalised (0.81-unit step for the Commonwealth)
and drops the shared 33rd edge vertex we need for seam checks; Python fits the converter and unittest stack.
Alternatives: build fo4land (blocked), Mutagen only (C# outside the Python pipeline), extend Codex's Fo4Export
(not ours). Evidence: docs/terrain/source-patch.md.

## 2026-10-09 Enforce local concurrency with a proxy, not with prompts
OpenCode has no cross-agent concurrency limit for a provider. A small stdlib-Python proxy (:1235) in front of
LM Studio (:1234) admits at most 1 inference request at a time after a resource check, queues the rest, and logs
every decision to SQLite. Agents get per-agent model aliases so usage is attributed without OpenCode changes.
Alternatives: LM Studio's own parallel-request setting (no resource checks, no attribution); an OpenCode plugin
(more coupling to an evolving plugin API).

## 2026-10-09 Thresholds adjusted for a resident model and for game tests
The owner's starting thresholds (70 / 85 / 95 VRAM / 90 RAM) apply as given to RAM. For VRAM, a loaded model
permanently holds most of the 12 GB, so with a model resident the restrict level starts at 92% (block stays 95%).
While Starfield runs, local inference is blocked (`game_blocks_inference`): measured 2026-10-09 with the game in
Parsons: VRAM 83%, GPU 99%, RAM 85%, which leaves no room for a model and would distort game tests. All values
are in tools/ai-team/config.json and are starting points to adjust from observed behaviour.

## 2026-10-09 One model, aliases per agent
One loaded model is shared by all local agents (12 GB VRAM cannot hold two). The alias decides only attribution.

## 2026-10-09 Lead does not edit code
The Lead's `edit` permission is limited to docs/ai/**; implementation happens in the implementation agent's own
worktree. `subagent_depth: 1` and `task: deny` on the specialists prevent delegation chains.

## 2026-10-09 Local model: Qwen3-14B Q4_K_M
Chosen by Claude and Codex on #32 (owner asked the agents to decide; Grok not yet answered). Fits the 12 GB card
fully with a 16K context; the 30B-A3B coder model is tested only if 14B fails the tool-calling eval, and only with the
game closed (it needs CPU offload). File: lmstudio-community/Qwen3-14B-GGUF, Qwen3-14B-Q4_K_M.gguf, 9,001,753,376
bytes, SHA-256 712c0791...c58555 (matches Hugging Face). Downloaded with curl because `lms get` stalled at 0 bytes.

## 2026-10-09 Lead may wake idle remote agents (owner request)
The owner asked the local Lead to start Codex and Grok itself. `tools/ai-team/wake_agent.py` forks the agent's most
recent session (full history, new session id) and runs one headless turn with the Lead's brief (`codex exec fork`,
`grok -c --fork-session -p`). Forking avoids writing into a session file an open window may hold; nothing is typed into
any window. Deterministic guards: refuses if the agent was active in the last 10 min (two writers in one repo) or
was woken in the last 30 min (their usage comes from the owner's plans); every attempt is logged (wakes.jsonl).
Alternatives: keystrokes into the agents' terminals (focus stealing, wrong-window risk); GitHub comments only (agents
don't poll while idle).
