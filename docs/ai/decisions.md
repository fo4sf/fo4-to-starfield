# Decisions (local AI team)

Format: date, decision, why, alternatives considered.

## 2026-10-16 FO4 "open by default" is written on converted doors; FO4 locks are not (Claude, proposed)
PluginSpike sets `OpenByDefault` (`ONAM`) on every placed reference of an animated, non-load DOOR base whose FO4
reference is open by default (pinned cells: 47 hinged-door refs; 68 with the sliding doors), so a doorway FO4 shows open
starts open instead of shut (review of PR #242). FO4 lock data (13 / 23 refs; Vault 111 levels 253 / 254) is counted
per cell and not written: the keys, terminals and quests that open those doors are not in the build, so a ported lock
would shut a door nothing can open. Alternatives: port locks with their levels (blocks routes until terminals and keys
exist), leave both out (FO4-open doorways become shut doors that a never-played rig must open). The route planner
already treats open-by-default doors as open (`scripts/game/routes.py` `moves_aside`).

## 2026-10-16 Sliding, lifting and trapdoor FO4 doors get their own rig, not a vanilla sliding template (Claude, proposed)
FO4 door models matching `NOT_HINGED_RE` (vault, elevator, hatch, ...) that are not load doors are converted like the
multi-part doors (`convert_multipart_door`: one rig bone per FO4 node, FO4's own Open / Close keys written with CALUMI, a
keyframed box per moving part) on the vanilla graph `SimpleOpenClose01.agx`, when `--door-anim-dll` is given; without
it they stay passable. Why: all 123 vanilla door rigs were read back; sliding and lifting doors use the same graph as
hinged ones and carry their motion in their own rig and clips, but none moves like the FO4 doors: no vanilla rig
drops a panel straight down or splits two panels up and down (the vault doors' lower panel drops 0.98 m; the nearest,
a NASA prototype door, moves two panels 0.52 m down and 0.52 m sideways) and the vanilla sliding pairs travel 1.00 / 1.50 / 4.00 m
against FO4's 0.64-0.91 m. A template would leave a panel shut or push it 0.09-0.36 m into the wall; FO4's keys give
the exact travel and timing. Alternatives: `ElvGen_ExSm_DoorInner01` as a template for the elevator doors (9-56 % too
far), `StsGenIntRmSmWallMid_DoorD01` for the vault doors (upper panel only, the lower one would block), keeping them
passable (the owner's row 1). Risk shared with #79: our rig and clips have not played in game. Evidence:
docs/spikes/sliding-doors.md.

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

## 2026-10-12 Fallout 4 marker load doors become the vanilla automatic cave door; experiment plugins load after their masters (Claude)
A Fallout 4 load door whose model is an editor marker (`AutoloadDoor` 01ED77, `AutoLoadMarker01.nif`, Automatic) is
written as a reference of Starfield's own `AutoloadDoor_Cave` (24F9CE): same name, flag and marker (the Starfield marker
is the FO4 one at 1/70, so the FO4 scale carries over), persistent, XTEL to the other end; an exterior end goes into the
worldspace's persistent cell, as all 45 vanilla overlay-world references of that door and all 345 worldspace XTEL
references do. The first one is the Red Rocket cave (docs/slice/redrocket-door.md), in a small link plugin that
masters FO4Port.esm and the terrain experiment instead of changing either. Because the runner's deploy activates
FO4Port.esm after an experiment's plugins on every launch, cycle.ps1 now runs `exp_install.py order` before the launch:
every plugin the experiment installed moves after its masters (runner feature `plugin_order`).
Why: the converter never places marker models, so both ends were missing; vanilla uses this exact door and layout for
its planet caves, which keeps the unknowns to our overlay's merge, not to the door record.
Alternatives: a converted FO4Port load door base (a visible door with an E prompt the cave never had); a new DOOR
copying 24F9CE without its environment script (a configuration vanilla never uses); placing the doors in FO4Port.esm or
FO4TerrainExp2.esm (would change the pinned build or a measured experiment); leaving the plugin before its master (in
Fallout 4 / Skyrim a load crash; in Starfield untested).

## 2026-10-12 door_trip: a door "does not work" only from a stand in its range; a PASS needs the walk-in (Claude)
After QA on PR #78: FAIL NOLOAD needs the player standing (settled) within the door's range (`activate_m`, 3 m) with
no load and GetInCell not saying the far side; a player never in range is INCONCLUSIVE NOREACH, a contradiction
INCONCLUSIVE CELLREAD. The step reads the position after every walk step and before E or the last-try teleport, so a
load that no HUD screenshot caught is counted and never followed by a teleport to the other side's coordinates. A
trip that loaded only from the last-try teleport is INCONCLUSIVE NEARONLY, because the owner's slice means walking in.
Before `load` the player is moved back to the coc arrival, so the position shows the reload by itself.
Why: a wrong FAIL on the slice's main question costs more than a retry; the HUD sampling (one screenshot about 1.5 s
after each 500 ms step) can miss a short loading screen, and the old step then teleported into the void.
Alternatives: keep NOLOAD on "near the start, no loading screen" (refuted by QA's synthetic cases); detect loads by
comparing screenshots (fragile at night and in caves); PASS with a NEAR class (the report's tally counts every PASS as
one, so the caveat would vanish from the summary).

## 2026-10-13 Movable tests: only the walk passes; furniture the walk did not reach is ELEVATED; the impulse is a diagnostic (Claude)
A movable test asks whether the player pushes the item, so only the walk passes it. A walk whose closest approach came
within reach and left the item in place is FAIL NOTMOVED. When planned (`--impulse`), `ApplyHavokImpulse` on the
confirmed selection (dv 1.5, 6, 24 m/s times its mass) follows: an impulse that moves the item only adds "the body is
simulated" to the detail, FAIL STUCK when nothing moves it. An item more than 0.5 m above the player's highest feet read
that the walk came no closer than 0.5 m to (or more than 1.8 m above them) is INCONCLUSIVE ELEVATED (final, never
counted by the circuit breaker). The converter keeps FO4's masses and bodies unchanged for now. A vanilla-controlled
queue (`movable_control_1013b`, QASmoke) compares our items with vanilla items of the same size, and the book and the
box again at 5 kg (`SetRigidBodyMass`, judged only when `GetMass` reads 5 kg back), before any converter change.
Why: the cigarette pack lay on a desk the walk stopped 0.67 m short of, and three flat books were walked over
(research-log 2026-10-13); every motion, layer and flag field matches vanilla items. Six inconclusive results in a row
switched the movable kind off for about 610 tests. The first version of this decision passed an item the walk could
not push as PASS IMPULSE and made every item 0.5 m up ELEVATED; the verifier of PR #110 showed that the impulse ladder
cancels the mass by construction (it would hide exactly the failure FO4's heavier items could cause) and that the pin
box of batch_full 0100, 0.81 m up, lay where the walk passed 0.26 m from it and did not move.
Alternatives: lighten FO4's masses now (2-10 times Starfield's for small items; unresolved whether mass is the cause:
the 25 kg book moved, the 50 kg box 0100 did not); a separate non-PASS class for "simulated but not pushed" (the detail
carries it, and NOTMOVED keeps the class every earlier report used); plan only items the walk can push (needs each
item's height and floor, and the batch would still not know whether a skipped item's body moves); MiscItem records
(pick-up and inventory semantics FO4 statics never had, decisions 2026-10-10).
## 2026-10-13 Codex: verified private evidence capsules before cleanup (#105)

Keep native screenshots and compact reports/source pins together in private lossless capsules,
with a per-file SHA-256 manifest and an external whole-capsule hash/index. Reopen and verify every
member plus the unchanged source before publication; never overwrite an existing archive. Linked
paths and restore-manifest aliases refuse archiving. Reclaim only explicitly identified inactive,
regenerable owned outputs after verification; retain cleanup receipts. Active/pinned campaigns and
unresolved configuration recovery stay in place. A second local volume is not an offsite backup.
Alternatives rejected: unverified moves, age-based screenshot deletion, lossy originals, or putting
private archives/game assets in Git. [Procedure](../testing/progress-storage.md).

## 2026-10-13 Stairs routes are walked offline before they go to the game (Claude; amended after QA on PR #111)
`scripts/game/routes.py` writes a stairs route only for a lane that an offline player walk (`src/fo4sf/walksim.py`)
climbs over FO4's own collision of the stair and its neighbours: a free start, no lift through a floor, at least 80 %
of the flight, no drop within 0.5 m past the end; otherwise the stair is skipped with the reason. References are placed
Z first (R = Rx(-x) Ry(-y) Rz(-z)), as FO4's precombined physics shows. What the walk cannot vouch for is written on
the route instead of hidden: `helper_crossing` (the walk meets a converted stair helper coming up through a floor at a
place the converter's flattening moved) and `movable_near` (movable objects the walk leaves out); a lane that would
touch a movable object is the last choice; `--probes-out` plans probes around each helper crossing. Planned routes for
an unchanged build go into their own folder (`testqueue.py plan --routes-dir`), never into the pinned staging, and a
queue keeps its own copy of the route files it uses (with their sha256).
Why: most stairs FAILs in batch_full and supervised_1011 were routes the player could not walk in Fallout 4 either (a
start wedged between a wall and a rail, against fallen floor chunks or rebar, a walk 2 m past a top that ends in a
collapsed floor, a 0.15 m "flight"), while the converted collision equals FO4's except the flattened helpers
([docs/testing/stairs-routes.md](../testing/stairs-routes.md)). A FAIL must point at the port, not at the test. But
0002 / 0003 stopped at a converted helper's slab crossing that the walk climbs (cause unresolved), so a route the walk
passes is not a route the port passes: the planner names such places and the queue tests them. The walk gives the
game's verdict on 59 of 64 recorded stairs results, 57 also at the same place (`scripts/game/stairs_calib.py`).
Alternatives: keep one centre-line route per stair and read every FAIL by hand (each costs a game run and an offline
analysis); hand-written skip lists for the library and Fort Hagen (do not carry to new cells); start every route from
the top floor and walk down (does not test climbing, the owner's complaint); skip every route through a helper crossing
(would drop the very tests that decide whether the converter's flattening is at fault); change the converter now (not
before the probes say the crossing is the cause).

## 2026-10-14 Codex: Windows read sharing during source fingerprints (#117)

Acquire an existing read-only Windows file handle sharing only reads, then retain it
through digest and metadata verification. Refuse incompatible writers/mappings and
do not fall back to permissive sharing. This closes the same-size/equal-metadata
race without changing persisted identities or reading every archive twice. Preserve
the immutable-source contract across the conversion run; POSIX metadata checks remain
best effort. Alternatives rejected: accepting a green retry of the intermittent test,
timestamp-only detection, or claiming that two hashes create an atomic snapshot.
[Contract, evidence and limits](../testing/archive-fingerprints.md).

## 2026-10-15 Codex: bridge publication and activation keep write-ahead ownership (#124)

Reuse the existing exclusive validated publisher and packed-resource verifier.
Record file intent before publication, confirmation afterward, and exact current
profile/activation bytes before changing Plugins.txt. Ambiguous or changed targets
keep a retryable journal; complete legacy ownership remains compatible. Cleanup
must be profile-bound and idempotent when a restored inactive line is already
present. Integrate Claude's bridge-last order caller without replacing its policy.
Alternatives rejected: direct final-path copies, minting identity from a copied
file without checking its source, or erasing an incomplete journal with untracked
artifacts still present. [Recovery boundaries](../testing/bridge-recovery.md).

## 2026-10-15 — Codex: reserve FormIDs before plugin publication (#132)

Persist the complete plain JSON identity map through a flushed same-directory
temporary file and replacement before PluginSpike writes its plugin. A map error
must not publish new plugin bytes. A subsequent plugin error keeps reservations,
including unused keys, so a retry cannot reassign them by conversion order.
Saving the map afterward left a synthetic plugin with no map on write failure;
rolling reservations back would permit ID reuse after interrupted builds.
This assumes one writer and an immutable input map during the run. It does not
make the plugin itself transactional, provide concurrent-writer exclusion or
claim power-loss durability/savegame acceptance. Complete build/deploy recovery
remains a separate control.

- 2026-10-15 (Claude): the Commonwealth is built from the existing 64 x 64 core (terrain + all 648,358 exterior statics already placed), not by adding cells: next come doors/interiors, semantic object classes via the R05 promotion path with ids retained (#150), navmesh per R06, actors, environment. One plugin for the exterior, interiors stay in FO4Port.esm. Alternatives considered: regional plugins (unneeded: the record count is far under the 16.7 M FormID space), a wider overlay (the playable area already fits). docs/terrain/commonwealth-build-plan.md.
- 2026-10-16 (Claude): FO4 settlement workshops become native ACTI build stations in the vanilla pre-placed pattern (OutpostPlayerHouseActivator 00024DC7: WorkshopKeyword + its OutpostCategory keywords read from the master, PRPS OutpostBuildAreaRadius 250, no VMAD; temporary REFR in the original slot), and FO4 crafting benches bind their REFR to the vanilla Starfield bench of their kind (weapon 2B6A63, armor 2B6A62, chem 2B6A61, cooking 2B6A65) with no record of ours; power armor stations stay statics. Why: build mode and the crafting menu are engine behaviour of these records (no script), the vanilla bench carries the animation and menu a converted mesh cannot yet, and a vanilla base keeps every FormID. Alternatives considered: the outpost beacon ACTI 2C60E9 (needs its quest script's mandatory properties), an outpost beacon pack-in (creates an overlay instance, unverified on ours), our own FURN with the FO4 mesh (second step: the animation over a boneless model is unresolved). docs/terrain/stations.md.

## 2026-10-16 Converted compressed meshes must pass the decoder simulation (Claude)
- Decision: src/fo4sf/meshcheck.py (CLI scripts/oracles/collision_mesh_keys.py) walks every compressed mesh of a
  converted NIF as Starfield's hknp decoder does and a build with violations is not deployed. The converter writes
  what vanilla meshes have and nothing else: one SIMD leaf per primitive, primitive slots the decoder cannot type
  replaced by a neighbour copy, FO4's special-primitive section flag cleared, primitiveStoresIsFlatConvex 0xFF; every
  other FO4 byte is copied as before (docs/ai/research-log.md 2026-10-16).
- Why: the owner's crashes since 10-12 are this decoder reading our per-triangle SIMD keys as primitives (vault_cart_01:
  key 79 + 1 -> primitive 40 of 40). Vanilla gives one invariant set to test against (837 of 837 meshes).
- Alternatives: dropping bodies with FO4 special primitives (loses the precombines' collision), re-encoding the trees
  (no vanilla evidence that the engine wants anything but what it has), leaving the flat-convex byte at FO4's 0 (a
  code path no vanilla asset exercises).
- 2026-10-16 (Claude): FO4 exterior load doors into the converted interiors become scripted doors (docs/terrain/scripted-doors.md): every record stays temporary on the exterior side (the overlay merge), the door REFR keeps its slot on an ACTI with the converted door mesh and carries the FO4SF_LoadDoor VMAD (PR #243: DestinationPlugin + DestinationId, resolved at run time, no master link between the plugins), each side gets an arrival XMarker at the FO4 XTEL point (exterior: temporary, appended after the lights with the ACTIs; interior: persistent, so it resolves from outside). The exterior side is written by Mutagen (its VMAD bytes equal the raw codec's and vanilla's), the interior side by a raw record-level patch of a copy of the pinned FO4Port.esm (scripts/terrain/vmad_patch.py), proved by a byte diff of every other record. Alternatives rejected: a vanilla XTEL door (persistent references read unmerged, 4 in-game runs); MoveTo onto the interior door itself (temporary: unresolvable from outside, and the player would land in the mesh); rewriting FO4Port.esm with Mutagen (no byte-level proof that nothing else moved); allocating the door ACTIs with the other promoted bases (would shift every NAVM and light id of core64i). Open until Step 0 runs in game: whether a temporary exterior marker resolves from inside (else a persistent twin plus the (-1200, -2700) offset).

### 2026-10-16 - preserve door-stage inputs before output (Codex)

A hard-linked README/report can overwrite the pinned source through the new
folder. Exclude generated names and replace generated files atomically; checking
an older hard-linked report must also detach it. Refuse any existing selected
REFR VMAD before changing the plugin, rather than erase or implicitly merge
unreviewed behavior. Validate marker-map collisions and disjoint output paths
before copying. Full-directory transactional publication remains separate.

- 2026-10-17 (Claude): the door return trip, writer side (docs/terrain/scripted-doors.md "Return trip"). Step 0 answered in game: the temporary exterior marker 0A76FD does not resolve from inside (door_trip_sdm_1018, `FO4SF_LoadDoor refused`), and a MoveTo onto a persistent overlay reference lands at its unmerged position, from where a setpos to the merged one stands on the overlay (probe (e)). So each exterior arrival marker itself becomes persistent (flag 0x400, same id: the slot and append rules of #272 and formids.json stay as they were) in the overlay world's persistent cell beside the anchor, and both door VMADs gain DestinationX / Y / Z (float, edited; the names of Codex's draft PR #291): the exterior door the interior marker's position, the interior door the exterior marker's merged position = local + overlays_params planet_target_cell x 100 m, refused unless it equals the measured (-1200, -2700, 0). Why the world's persistent cell and not the exterior cell's persistent children: the only persistent overlay reference seen to resolve and MoveTo in game is the anchor there, and vanilla keeps every persistent worldspace reference there (Starfield.esm 16,057 of 16,057, Fallout4.esm 33,571 of 33,571; 0 in an exterior cell's persistent children; read raw with C:\Modding\scratch\doorreturn\survey_persistent.py). Alternatives rejected: a persistent twin beside the temporary marker (a fourth id per door for no use: nothing resolves the temporary one); a marker written at local + offset (supported, not run: the MoveTo lands at the written position in the unmerged instance, 2.95 km from the door's terrain there, and the position leaves the overlay's cells); the offset as a bare constant (it follows the overlay's registration: a build registered elsewhere is refused until measured).
- 2026-10-17 (Claude): both door VMADs now carry `UseDestinationPosition` (bool, edited, true) as the sixth property, right after DestinationZ (docs/terrain/scripted-doors.md "Restage with the bool"). Why: PR #291's FO4SF_LoadDoor applies DestinationX/Y/Z with SetPosition only when that bool is true (zero is a valid coordinate, so the values cannot be the switch), so the five-property VMADs staged earlier the same day would have kept the plain MoveTo and ignored the coordinates. The reader (`vmad_patch.load_door_target`, hence `check_port` and `make_core64c.door_record_problems`) refuses floats without the bool, a false bool and the bool without floats; the two-property door stays valid. #291's psc declares the bool before the floats: the names and types match, the order differs, and Papyrus binds VMAD properties by name, so the reader takes both orders and the writer keeps the sixth position. terrain_core64l and integ_1018_doors2 were regenerated (265 of 265, 49 of 49; formids, objects and plan byte-identical to core64k). Alternative rejected: leaving the bool out (the psc defaults it to False, so the coordinates would never be applied).
- 2026-10-17 (Claude): exterior light lumens scaled 0.375 as a raw patch (terrain_core64l_l125) pending the owner's night check; the build default stays 333 until then. Alternatives: a full rebuild with --lumens-per-m2 125 (hours); a patch plugin (a second master). docs/terrain/exterior-lights.md "Calibration (17 Oct)".


## 2026-10-15 Claude: the leader's state is an append-only ledger; GitHub stays the human-readable bus

The leader core (`src/fo4sf/core/`, to be built per [leader-core.md](leader-core.md)) keeps one append-only
`leader/ledger.jsonl` of typed events beside the test queues; current state is a fold over it, and existing records
(queue `results.jsonl`/`state.json`, deploy and install manifests, watchdog state) are imported as events, never
rewritten. `SKIPPED` and `CIRCUIT_BROKEN` are terminal but undecided outcomes; only an `IN_GAME` `PASS` on the pinned
build verifies a capability. Why: the 2026-10-14 power cut and the #84 controller races both came from state spread
over labels, prose and per-queue files; a fold over a ledger resumes without guessing, a truncated last line is the
worst crash case, and the work-period report generated from the fold cannot drift from the state. Alternatives:
a SQLite store like `guardian.db` (harder to diff and attach as evidence; a crash mid-write is worse than a
truncated JSON line); GitHub labels as the state (not machine-checkable, no history of who held the controller);
rewriting old queue results into a new format (would touch original campaign evidence).

## 2026-10-16 Claude-cloud: the controller lease is a file beside the ledger, consulted only behind an opt-in switch

`src/fo4sf/core/controller.py` keeps the lease in `<leader>/controller.json` and writes every claim, renewal and
release to the ledger first (the ledger is the record; the file is the cache the PowerShell scripts read through
`scripts/game/lease.py`). `testqueue.py run`, `cycle.ps1` and `watchdog.ps1` consult it only when `FO4SF_LEASE_DIR`
(the watchdog: `lease_dir` in `watchdog.json`) is set; unset, every script behaves as before, so the owner's PC does
not change until the PC session turns the switch on in a window it watches. Why: the live runner, the chain and the
watchdog are the PC session's, and a cloud session cannot test them against the game; a default-off switch lets the
code merge and be read without a behaviour change. An expired lease is ambiguous and refuses every claim but the
holder's own or a forced one with a reason, because a crash leaves exactly that state and the ledger must say who took
over and why. Alternatives: a lock file alone (no record of who held it and no expiry: the #84 race again); a fold of
the ledger in PowerShell (duplicated logic in two languages); a key in the PC's `config.toml` (not in git, and the
runner reads none today); shipping the wiring on by default (would change the next chain on the PC untested).

## 2026-10-16 Claude-cloud: the preflight gate reads through a probe, refuses on UNKNOWN, and ships off

`src/fo4sf/core/preflight.py` keeps every check pure (a probe object supplies the readings; the runner's
`PreflightProbe` reads the PC, the tests a fake), so the Windows-only readings never enter the core and every check
has a synthetic PASS and FAIL. A reading the probe cannot give is UNKNOWN and refuses like FAIL, as the owner's brief
asks; that includes a game version nobody pinned yet, so turning the gate on is a deliberate step by the PC session
(pin the version, set `--preflight`). Why a probe and not direct reads: the same functions must run on Linux CI and on
the PC, and a check that raises must become one UNKNOWN line, not a crash of the runner. Alternatives: a PowerShell
preflight in cycle.ps1 (not testable here, and the runner needs the result in its log and the ledger); making the
gate always-on (would refuse every current queue, none pins a game version); verifying the absolute load index
against the game's implicit plugins (which of them the owner's install loads is unresolved: left as a note).

## 2026-10-16 Claude-cloud: task cards and worker results are validated data; a lost attempt expires, never vanishes

`src/fo4sf/core/tasks.py` and `worker.py` make the §4 card and the worker's result typed records the ledger checks
before it takes them (an undecided outcome never completes, a PASS or FAIL carries evidence, only an IN_GAME PASS
may claim `verified`, one attempt at a time, dependencies by PASS), and `Worker.expire` turns an attempt past its
timeout into an INCONCLUSIVE result that says so. Why: the brief's cards were prose, and the two failure modes of
the last weeks were a result nobody could trace to evidence and a run nobody could tell apart from a lost one; data
with rules closes both. Alternatives: free-form result dicts (what the queue rows are today; the importer keeps
reading those unchanged); a scheduler that retries on its own (a retry is a decision the leader records, not a loop).

## 2026-10-16 Claude-cloud: the core carries one reference matrix, in #102's Z-first order, and leaves the old copies in place

`src/fo4sf/core/adapters/transform.py` is the core's only `ref_matrix` (`R = Rx(-x) Ry(-y) Rz(-z)`, the order PR #102
verified on 146,463 of 146,728 tilted precombined references and on 52 of 52 core64c readings); a parity test pins
where the two Python copies agree (`routes.py` everywhere, `exterior.py` on heading-only rotations) and where they do
not. `exterior.ref_matrix` and `PluginSpike.RotateOffset` stay X first on purpose: switching either moves every
tilted placement or every rigged door hinge, which is a re-staged build, a rebuilt plugin and re-pinned campaigns,
so each is its own PR by the PC session (leader-core.md §9 lists the cost). Why not fix them now: a cloud session
cannot rebuild or re-pin, and a silently changed `objects.json` would invalidate pinned evidence. Alternatives:
one shared function imported by both scripts today (ties `scripts/game` to `fo4sf.core` before the PC session has
decided the import path); keeping the order as a parameter (two orders in the core is the bug #102 found).

## 2026-10-18 Claude-cloud: SetRigidBodyMass tests when GetMass cannot be read
- **Decision:** a movable_control test with `set_mass_kg` whose GetMass probe answers "No script named ..." is judged
  on a move only. PASS WALKED or PASS IMPULSE stands, with "mass not read back" in the detail. No move stays
  INCONCLUSIVE MASS.
- **Why:** in movable_1019c, `cf "ObjectReference.GetMass"` answered "No script named ObjectReference is attached to
  the object" (**verified**), so the old rule ("judged only when GetMass reads the mass set back") would leave every
  5 kg test unjudged forever. The set mass can only have made the body lighter or left it unchanged:
  - A move shows the body moves at a mass no higher than its own.
  - No move cannot tell a mass that did not take from a heavy body, which is the verifier's "thinness, not mass"
    concern on PR #110, so a non-move is still not judged.
- **Alternatives:**
  - Drop the 5 kg tests: this loses the one comparison that can show mass is the cause.
  - Judge both ways: this risks a false "mass is not the cause".
  - Find another GetMass route: none is known (no console command; the CallFunction route refuses).
- Taken under the owner's standing rule (2026-10-18 03:56Z) that threads take their recommended option on reversible
  choices.

## 2026-10-18: interior usable objects reuse the exterior promotion rules (Claude-cloud)
- Decision: FO4Port.esm promotes containers, inventory items, activators and terminals with the core's make_cluster rules
  and tables, through an optional promote.json PluginSpike reads (docs/terrain/port-promotions.md).
- Why: the owner found these unusable indoors (18 Oct); the exterior path is already verified in game.
- Alternatives: a Python record patch of the pinned plugin (vmad_patch style): rejected, new record types would need a
  hand-written layout Mutagen already writes; copying the table logic into C#: rejected, two rule sets would drift.

## 2026-10-20: one stable DOOR base per converted model and FO4 name (Claude-cloud)
- **Decision:** PluginSpike's DoorNames.cs gives each FO4 name of a converted door model its own DOOR base, under the
  identity `DOOR:<editor id>|name:<name>`, and moves that name's references to it. The model's own base
  `DOOR:<editor id>` keeps the name "Door" and the references without a usable FO4 name, and it is emitted even when
  no reference uses it. Copies keep the base's open and own-rig roles.
- **Why:** the first version gave the model base the name most of its references had. Codex showed on #400 (review
  5580232495) that a grown export with the same formids.json flips the winner. Old references then move to another
  base, and a published base gets another name, while every REFR ID stays the same. Bases and their names are what
  saves and other plugins see, so they must not depend on reference counts. The fix was confirmed in review 5581794458.
- **Alternatives:**
  - Keep the election and record each base's owner name in formids.json. This adds a map entry that is not a record,
    and a new name can still win the election.
  - Name the model base after the first name in ordinal order. A new name that sorts earlier still flips it.
- **Boundary:** this is not a migration. A plugin or map built with the 4f0ad57 election is not compatible with it,
  but no staged or installed build used that version. Not verified in game.
