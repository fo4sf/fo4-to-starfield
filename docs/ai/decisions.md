# Decisions (local AI team)

Format: date, decision, why, alternatives considered.

## 2026-10-12 Multi-part FO4 doors get their own rig and clips; single-part doors stay on the Akila template (Claude, proposed)
A rigged FO4 door whose `Open` sequence moves geometry outside its first node (second leaf, shutter panel, sliding
panel set, latches) is converted with one rig bone per FO4 node, its own `Open`/`Close` clips written with the external
CALUMI library from FO4's own keys (tracks for animated bones only, keyed from the bind), one keyframed box per moving
part, and a DOOR record whose BNAM / CNAM point at those files (graph unchanged: `SimpleOpenClose01.agx`). Doors with one
moving part keep the verified template path. Why: the template rig's clip has one track, so a second part cannot move
under it; vanilla double doors (`IndIntRmSmWallMid_DoorA01`) are built exactly this way; FO4's keys give the right
pivots, angles, slides and timing for every part. Keeping single-part doors on the template keeps what already works
in game while the native rig is unverified. Alternatives: a vanilla two-leaf template (fixed hinge spacing and swing
that FO4 doors do not share), one DOOR reference per leaf on the Akila template (needs activate-parent links, and the
mirrored leaf would swing the wrong way), leaving the extra parts static (the bug). Evidence: docs/ai/research-log.md
2026-10-12; docs/spikes/WP-doors-research.md "Multi-part doors".

## 2026-10-11 FO4 navmesh: one Starfield NAVM per (FO4 navmesh, 100 m cell) and a NAVI holding only our entries (Claude)
Every Fallout 4 navmesh is cut at Starfield's cell lines into one NAVM per cell it touches (cut points keyed so both
sides are bit-identical; new links along the lines; FO4's own portals kept as links); the plugin carries a NAVI override
(`000FF1:Starfield.esm`) with one NVMI per new navmesh (no outline, no traversals). Why: FO4's portals overlap only in
part, so keeping its navmeshes avoids re-meshing; Red Rocket's navmesh stays one record (a walk on it needs no links and
no NAVI, the cleanest first test); every official plugin ships a partial NAVI the same way. Alternatives: one merged
navmesh per cell (re-weld partial portals), no NAVI (cross-navmesh paths probably fail), a full NAVI copy (53.9 MB,
overriding every vanilla entry), CK generation (not FO4's navmesh; owner time). Evidence:
docs/actors/navmesh-conversion.md.

## 2026-10-12 Terrain test travel: every teleport at most 2 cells per axis, terrain waypoints instead of hops (Claude, proposed)
Plans for the terrain runner keep every teleport within 200 m along each axis (at most 2 Starfield cells whatever the
overlay's merge offset): legs longer than 185 m get open terrain waypoints that are judged like the probes, and
`hop_m` 200 stays as a safety net. Why: in the overlay runs so far, teleports of at most 2 cells per axis landed 144 of
145 times and those of 3 or more relocated the player ("Boundary Reached") or hung 11 of 28 times
(`scripts/terrain/teleport_audit.py`, **supported**); distance alone does not separate them. Waypoints rather than
hops, because the runner's step timeout (150 + 90 s per point) does not count hops. Alternatives: `hop_m` 200 alone
(core64c's entry 1 would run past its timeout), splitting entries (at best 79 s of margin), per-axis hops in the
runner (a runner change, not on the integration branch). Evidence: docs/terrain/core64c.md "Teleport rule".

## 2026-10-12 Whole-core objects: one archive below 4 GiB with capped textures, not a region split (Claude, proposed)
core64c selects 649,596 convertible Fallout4.esm exterior references of the 64-cell core and places the 648,358 whose
models convert (1,238 belong to the 118 models that do not) in core64's plugin, and ships every
converted file in one stored `<plugin> - Main.ba2`, with converted textures capped per kind by dropping top mip levels
(color 1024, normal 512, rough 256, opacity 512 px; `convert_batch.py --max-texture`, off by default). Why: every large
vanilla archive stops just below 4 GiB (whether the engine reads past it is unresolved); full resolution needs about
8.5 GiB; the runner's installer packs one archive; the 11,769 models share 2,632 materials over the whole map, so a
split into 15 regions of 1.6 km would need 28.8 GiB and its four central regions would still exceed 4 GiB each; C:
has too little room for a full-resolution build plus its temporary archive. Alternatives: cap 512 everywhere (1.66
GiB, blurrier albedo), one plugin's Main + Textures archive plus a carrier plugin at full resolution (needs a
per-plugin installer and an in-game check), region plugins (above). Evidence: docs/terrain/core64c.md.

## 2026-10-11 Commonwealth terrain: one large overlay, a grid of overlays as fallback (Claude, proposed)
Plan the whole-map terrain as one overlay worldspace holding the playable Commonwealth plus 1 to 2.5 km around it
(64 to 90 Starfield cells, Absolute alignment), registered on a hidden host planet at a measured lat/long; fall back
to a grid of 14-cell overlays generated edge to edge if large overlays fail in game. Why: one landing is 100 cells
(game terrain width, 5-cell buffer), so the full 114-cell LAND grid never fits; a single overlay has no seams, while
every overlay seam has a 1-cell merge ring of unknown behaviour; both are built by the same generator
(`scripts/terrain/make_cw_overlays.py`). Alternatives: a custom planet surface made of our blocks (exact far terrain,
but four unknown height / blend rules and a planet to build), static mesh tiles (exact, but new collision, material
and LOD pipelines). Gates: an uncompressed rerun of exp2b (exp2b3) must read our BTD heights (exp2b's packed BTD
read flat at its minimum; cause unresolved, packing is one hypothesis), then exp3 (2 x 2 grid: seams, where the tiles
sit, measured from heights since our anchors do not merge), then a 64-cell core overlay. Evidence:
docs/terrain/commonwealth-scale.md.

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

## 2026-10-10 Movable FO4 objects: MoveableStatic records and one rigid body per multi-body system
- Decision: FO4 dynamic bodies convert to Starfield MoveableStatic records (never MiscItem: no inventory, no value, no
  pickup prompt) with vanilla-derived dynamic Havok bodies; a multi-body all-dynamic FO4 system (ragdoll skeleton,
  breakable, hose-and-tank) becomes ONE rigid compound body with the system's total mass ("phase A"), and systems with
  any anchored body stay static.
- Why: pushable objects are FO4 gameplay; MoveableStatic is how Starfield itself places pushable set dressing (431 in
  Starfield.esm); a rigid merge unblocks doorways today while constraints (joints) are a separate format job.
- Alternatives: MiscItem (adds pickup/inventory semantics FO4 statics don't have); leaving them static (blocks doors,
  silently changes gameplay); converting constraints first (weeks; the Vault 114 door needed a fix now). Breakables
  (`*Dest` models) are included in the merge without a check that their union matches the intact mesh: open.
## 2026-10-10 Load-door teleports are written by the plugin writer, not left to the ReferenceLinks post-pass
PluginSpike decides each manifest item's base record type; an XTEL is only valid between DOOR references, and both ends
are only known once every cell of the build is placed. So PluginSpike makes `load_door` items DOOR records and writes
the XTEL for each pair placed in the same build (dotnet/PluginSpike/TeleportLinks.cs), moving both ends to the
persistent group. Codex's ReferenceLinks post-pass (Relationships.Apply) writes the same link when it runs afterwards
(same values, idempotent) and still reports the unresolved ones. Alternatives: ReferenceLinks only (the STAT -> DOOR
change is PluginSpike's anyway, and every build would need the second pass); a DOOR for every FO4 Door base (fake doors,
hatches and trapdoors would become activatable with no destination).
## 2026-10-10 Place models without the NIF scene root's own transform
The converter, the route planner and the collision reader compose a model's node transforms from the children of the
scene root, not from the root itself (`nif.world_transforms(placed=True)`): the engine replaces the root's transform
with the reference's, so a rotation stored on the FO4 root is not applied in game. Why: `PryCatwalkStairsEnt02` has a
180-degree root; converting it with the root turned the stairs the wrong way round (Prydwen routes 20/28/29 fell, 19/27/30
never reached their start), and FO4's own precombined physics matches 89 placements of 15 rooted models only without
the root (docs/ai/research-log.md, 2026-10-10). Alternatives: apply the root as the file stores it (what we did; wrong
for 44 of 4,014 converted models, 232 placements); apply it only to models outside precombines (no evidence that the
engine does, and the stairs are not precombined). The default `world_transforms()` keeps the file's own composition for
tools that want the file as stored (door rig/motion modules, oracles).

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

## 2026-10-12 NPC navigation control N0b: the walk judged from t0 on a 24 m pair, P = pair - 6 m (Claude, proposed)
N0 replaced by N0b in QASmoke: A (5.5, -4.5, 0) -> B (-12, 12, 0), 24.05 m, chosen by
`scripts/actors/navmesh_points.py`; the commanded walk is measured from t0 (new plan keys `precommand_m` 3 m,
`arrive_progress` P; runner feature `npc_t0`): PASS = within 3 m of the player after coming P = 18 m closer than at
t0, or 18 m closer at the end; 3 m of approach before the command makes it INCONCLUSIVE PRECOMMAND; a baseline FAILs
WANDER on 18 m between any two reads; two citizen baselines; the control gate pairs a control with the baselines of its
own queue. Commands PathToRef and StartCombat on the calm citizen, the hostile Spacer as a baseline; N1 / N2 re-planned
with the rule of their own pairs, queued only once `npc_control.py ready` says N0b's controls passed. Why: N0's
actors came 5-9 m towards the old B whatever was typed (the 5 m rule passed wander), and the first N0b plan (18 m north
pair, 12 m, the integration-1012 judge unchanged) still let pre-command wander count: that judge's pre-command guard
is min_progress (12 m) and an arrival needs no progress after the command (verifier of PR #77); actors on record moved
up to 14.1 m from t0 and walked up to 9.5 m towards the player before the command (docs/actors/npc-navigation.md 5.3).
Alternatives: keep the 18 m pair with the new judge (P 12 m: below the 14.1 m move on record); a baseline-relative
judge (PASS only a margin beyond the same actor's measured baseline): needs several baselines per actor and pair to
mean anything; the 18 m pair with a 12 m rule and no runner change: refuted by the finding above.
