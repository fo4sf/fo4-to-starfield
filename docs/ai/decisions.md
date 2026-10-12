# Decisions (local AI team)

Format: date, decision, why, alternatives considered.

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

## 2026-10-11 Converted actors: own identity, inherited Starfield behaviour (Claude)
A converted Fallout 4 NPC_ keeps what makes it that actor: its name, faction intent, weapon, death loot and combat
style intent. It inherits behaviour from a vanilla Starfield template of the same role through the ACBS template flags:
traits, stats, AI data and packages, attack data, keywords, scripts, and template slots 13 / 14. The first record
(`FO4_LvlRaider`, docs/actors/raider-conversion.md) templates directly on NPC_ records (EncSpacer01Template,
EncSpacerFaceM01), not on the leveled lists, so its look and level are the same in every test.
Why: Starfield runs the actor with its own systems (reaction radii, combat AI, faces), and the plugin stays small
(547 B). The behaviour template can be swapped without touching the identity, and a failure in the vanilla control
cell points at the record, not at the world.
Alternatives considered:
- Copying every FO4 field: FO4 AI semantics differ (hostility through aggression rather than faction relations), and
  FO4 faces and outfits need the skinning milestones.
- Duplicating a vanilla NPC_ (DeepCopy): carries the vanilla identity, and so hides what the conversion contributes.
- Templating on LvlSpacer / LCharSpacer: random per spawn, and the spawn may get a generated base that `GetIsID` does
  not confirm (N0_ptr_lvl).
Note (2026-10-12): the death item and combat style are written as the record's own, but under xEdit's Skyrim / FO4
template semantics (a supported hypothesis for Starfield) they go with Traits and AI Data, both inherited, so they are
probably overridden (docs/actors/raider-conversion.md section 3). Every converted NPC_ also carries PRPS, STON, PRON and
EDCT and form version 581, as all 7,131 vanilla NPC_ do (copied from the templates it inherits from).

## 2026-10-12 Converted actors are tested calm against calm, hostile against hostile (Claude)
A commanded walk (PathToRef, SetPlayerTeammate) of a converted actor is tested on a calm probe: the conversion without
factions, written into the same plugin (`FO4_LvlRaider_Calm`). Its FAILs are gated by the calm vanilla actor of N0 and
its PASS is credited to the command only when its own baseline stayed away. The hostile conversion is judged without a
command against the vanilla actor it inherits its behaviour from (N2b: both baselines). The runner measures the approach
from the spawn read as well as from t0, and every N2 test waits for the first one's spawn (`requires` DECIDED).
Why: QA on PR #75. With the hostile raider, combat AI would drive any walk, so a PASS said nothing about the command
and a raider holding its firing distance would have read as a conversion failure against a calm control; StartCombat
on an actor that is already hostile cannot be told from its own hostility; and t0 comes after the player moved to B.
Alternatives considered:
- A hostile vanilla control (the Spacer) for each command: also fair, but every test would then measure combat
  pursuit, not the command, twice the launches for one question.
- Console commands that calm the spawned raider (StopCombat, faction changes): unverified in Starfield, and they would
  add untested console lines to the step.
- tcai (combat AI off): global, and it would differ from N0's conditions.
