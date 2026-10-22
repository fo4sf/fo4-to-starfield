# Roadmap: from the Commonwealth test slice to a Fallout core on Creation Engine 2

The owner set this direction on 17 October 2026. It extends [docs/PLAN.md](PLAN.md) (phases P0 to P6) with what
comes after the current testing, and it is the brief Codex and Grok work from. Status words: **done**, **in testing**,
**next**, **later**. Dates are Mountain time. Evidence lives in [docs/JOURNAL.md](JOURNAL.md),
[docs/owner/playtest-issues.md](owner/playtest-issues.md) and [issue #32](https://github.com/fo4sf/fo4-to-starfield/issues/32).
Two independent reviews of this document (17 Oct) are folded in; their corrections are the reason several claims
below are narrower than the first draft.

## Update, 20 October 2026

On 19 October the owner set the combined core as the first priority from here on: a GAMMA-style second way to play
around settlements that grow, factions that act and a connected wasteland, built on the Commonwealth first, because
it has value without the open legal questions. The stories are still wanted, and the work in flight continues (the
v6e test, the mission, the Vault 111 start and the approved phases in their order). The owner's decisions for each
phase, and the critical path, are in docs/research/framework/dependencies.md on draft PR #408; they are not repeated
here. The project is not offered for download or play for now.

## Update, 19 October 2026

Phase A and the start of Phase B overlap: the B4 mission ("When Freedom Calls", cut down) has run to completion in
game on the v6c build (#353, notes in docs/mission/when-freedom-calls.md), and Codsworth stands in Sanctuary as a
robot stand-in (#361). Phase A is not closed: v6 crashes near Red Rocket and the Museum of Freedom are under a
bisect (#375; the v6e test build is staged), and the map markers do not draw yet (#376).

On 19 October the owner approved the order of the next phases. It replaces section 2's order where they differ:

1. **New game:** a Vault 111 start with no Starfield intro, which everything else plugs into.
2. **Doors:** load doors with their enter and exit animations.
3. **Interiors:** all of them (about 190 are still unconverted), in batches.
4. **Launcher:** it ships no assets and builds the port from the player's own Fallout 4 and DLC; it may require
   Starfield's free Creation Kit, and the port may require SFSE.

The owner also decided: the Commonwealth, Far Harbor and Nuka-World share one Earth-like planet with real days and
weather; the player is silent by default; Starfield's own animations come first; releases go to GitHub first. The
order after the launcher is open. Research inputs are in draft PR #380 (docs/research/next-phase/), with Grok's
proposals (#381, PR #386) and Codex's review (#382). Offline work on the four phases has started on separate branches;
nothing from it is installed until the current crash test is done.

Offline work in flight (draft PRs, not merged, nothing installed; 19 Oct):

| Phase | Draft PR | What it holds |
|---|---|---|
| 1. New game | #393 | FO4SFNewGame.esm, a Vault 111 start built offline |
| 2. Doors | #392 | load doors that play their opening before the trip, behind a switch that is off by default |
| 3. Interiors | #396 | a census of all interiors, a 9-batch plan, and staged batch builds that keep the installed port's ids |
| 4. Launcher | #394 | the build manifest, a resumable build, a recorded restore and a same-ids check |
| Testing | #391, #397 | the night-chain arm check and direct exe launch; door round trips per interior batch and the v6e test campaign |
| Map | #399 | an installer for FO4SFMapMarkers.esm next to the core set (#376 is merged) |

## 0. Where we are (17 October 2026): Phase A, the Commonwealth slice, in testing

Phase A is "the playable Commonwealth exterior plus the first interiors, running natively in Starfield". It maps to
PLAN.md's P2 (statics + interior) and P4 (exterior) with parts of P3 (actors) and P6 (scale).

Verified in game (the owner, or the runner from the console):

- the whole 64 x 64 cell exterior as native terrain with 648,358 placed objects (build core64k); the owner walked from
  Red Rocket to the Diamond City gate with no crash and no Boundary Reached (playtest row 25);
- containers and loose items work and the hand scanner tags them (rows 12, 16); the Red Rocket workshop opens
  Starfield's build mode (row 12); 6,249 exterior lights are placed but too bright (row 22). Placed but not yet
  checked in game: the other 28 workshops, the crafting menus of the 269 benches, the 140 terminals; activators show
  their prompt but nothing is wired behind them yet (row 21);
- 16 interiors reachable by `coc` (Vault 111, Red Rocket, Super Duper Mart, Valentine's Detective Agency and more,
  build integ_1018); Vault 111's sliding doors work (owner, rows 1 and 6); the cog door VltGearDoor01 is still a solid
  static, so the vault exit stays shut;
- shooting converted objects no longer crashes (the collision mesh key fix, #274; owner, row 18);
- the first scripted load door: activated from the console by the runner, the exterior Super Duper Mart door put the
  player on the interior arrival marker (journal, 16 Oct night); a walked activation and the return trip are not
  proven yet;
- a converted raider fights the player when combat is forced from the console (npc_combat c2 and c4; unprompted it
  never engaged, c1); a spawned vanilla NPC paths on the converted exterior navmesh.

Open before Phase A closes (the [test sheet](owner/in-game-test-sheet.md) is the checklist; it is refreshed first):

| Item | State | Owner |
|---|---|---|
| Door return trip (interior to exterior) | script merged (#291); the writer side #297 (persistent exterior markers, DestinationX/Y/Z and UseDestinationPosition on both door VMADs) is in the merge queue after Codex's clean delta QA at 3446a99; the round-trip queue is staged; one runner window is needed | Claude, Codex QA |
| Exterior lights too bright at night | cause found (median lumens x fade 2.3x vanilla); #302 scales every LIGH by 0.375 as a raw plugin patch, staged as terrain_core64l_l125 for the owner's night check | Claude |
| Vault 111 gear-room gates passable | cause found: frozen leaves keep FO4's clutter-no-cut layer, which Starfield's character controller passes; the fix writes them as static (PR from branch claude/gate-clutter-nocut-static); needs an interior rebuild | Claude |
| Vault 111 flat grey floor | the gear-room pit's water sheet was converted as an opaque plank; #300 leaves water planes out; needs an interior rebuild | Claude |
| Vault 111 cog door (an activator with Stage clips, played from its console) and the exit elevator | not built | Claude |
| Picking up and carrying objects in the world (not into the inventory) | does not work (owner, row 26); hypothesis: FO4 masses are 2 to 10 times Starfield's for small items (research log); the owner's in-game mass experiment decides | Claude |
| Garage button does nothing | #303 (Grok, open, wire-only): FO4's XAPR link becomes the vanilla DefaultActivateLinkedRefOnActivate plus an XLKR on the button; no Opening/Closing clip alias (that made garage meshes passable). Garage NIF rig is later, Claude on the build side | Grok, Codex QA, Claude build |
| Nothing visible beyond the loaded cells | no distant LOD for converted statics; #303 carries the object-LOD plan (no build yet; next a small LOD trial) | Grok research, Claude build |
| Textures: foliage cutouts, greyscale palettes, vines, white walls | Grok's #288/#289 need the review fixes, then Claude reconverts | Grok, Codex QA |
| Map surface view and markers | what the surface map shows over the Commonwealth is not recorded yet (a playtest row with the owner's screenshot comes first); #296 restores the first marker; the 3D view is section 3's first Grok item | Grok |
| Benches show Starfield's models | low priority (owner) | Claude |
| Elevator and power armor rest poses, FLOR harvest, interior lighting | known, queued | Claude, Grok (#290) |

**Exit criterion for Phase A:** from a save made before this build was installed, the owner arrives at Red Rocket by
fast travel to its map marker (until #296 is proven, one noted `coc FO4Core_RedRocketSpawn`), walks the exterior at
day and night, goes in and out through each of the 15 placed exterior load doors into converted interiors, and nothing
crashes. The runner's door_trip (walk in, walk out, save, load) passes for the same doors. Every line of the refreshed
test sheet reads "works" or carries a dated owner note.

## 1. Phase B (next): one playable slice

The owner's words: "once we get the interior made and show we can bring in one complex NPC and get a working playable
area textured with one simple mission (you can make the NPCs for it also do combat)". This is PLAN.md's P3 and the
first half of P5, on the ground we already have.

### B1. The interiors of the slice, finished

The slice is Vault 111, Sanctuary Hills, Red Rocket, Concord (the Museum of Freedom) and the roads between them.
Every interior in it loads, is lit, has correct physics (no passable gates, no planks over water), and its doors work
both ways. The Vault 111 exit works: the cog door opens from its console, and the exit elevator works or is replaced
by a scripted door of the load-door kind. Interior batch 1 (the ranked backlog in docs/terrain) adds the slice's
missing interiors first, the Museum of Freedom among them.

### B2. One complex NPC

"Complex" means all of: a converted appearance (model and outfit, or a Starfield race stand-in while the face
pipeline is open), a name and the NPC's own Fallout 4 voice lines converted from the player's files (no synthetic or
cloned voice of the original actors), a dialogue tree ported from Fallout 4's dialogue records into Starfield's
quest-dialogue form, AI packages (sandbox, follow, travel), combat (weapon, faction, aggression), and persistence
across save and load.

Candidate: **Preston Garvey**, a human on the Starfield human skeleton, built the way the converted raider is (FO4
identity on a Starfield template, a Starfield face stand-in while the face pipeline is open); he also gives "When
Freedom Calls". Stretch: **Codsworth**. A Mr. Handy has no Starfield skeleton and ACTOR-MILESTONE.md puts creature
rigs last, so a first Codsworth would use a Starfield robot body under his name and lines. Voice: FO4's lines need
WP-15 (.fuz to .wem plus lip sync, not started); until it lands, subtitled silent lines are the declared stand-in.
The team confirms the choice with the owner before building.

### B3. A textured, finished playable area

In the slice: no flat, white or placeholder materials; foliage and vines right; lights calibrated for night; distant
objects visible (LOD); the surface map view from section 3, extended to the slice's markers; fast travel inside the
slice or a clear reason why not yet.

### B4. One simple mission, with combat NPCs

A quest record with stages, objectives and quest markers; a giver with dialogue; a combat objective against converted
raiders; a reward; completion without the console. Candidate: a cut-down **"When Freedom Calls"** (reach the Museum of
Freedom, clear the raiders, talk to Preston). The converted raider fights once combat is forced (StartCombat player,
runner queues npc_combat_c2/c4, 15 Oct); unprompted it never engaged (c1), and it wears its Starfield template's look.
The mission needs raiders that are hostile on sight on the converted navmesh of ConcordMuseum01, which waits for the
near-slice interior batch.

**Exit criterion for Phase B:** the owner, without the console and from a save made before the build was installed,
leaves Vault 111, walks to Preston, takes the objective, fights through Concord, completes the mission, saves,
reloads, and everything persists. The runner covers the same path from the console: door_trip with save and reload on
each slice door, npc_nav with combat reads judged ENGAGED with no forced start for the mission's raiders, and quest
stage and objective reads through the bridge after each step and after the reload (a new bridge probe and runner
kind, built in Phase B).

### Who does what in Phase B

- **Claude** (lead, live game): integration builds, the door and interior path, the mission assembly, acceptance runs,
  the owner's installs, every in-game check, this roadmap.
- **Codex** (records, IDs, deploy): the quest, dialogue, package and faction record machinery (Fallout 4 QUST, DIAL,
  INFO, PACK to Starfield), persistent identity across builds, deploy and recovery, the Papyrus for the mission, and
  independent QA on Grok's PRs.
- **Grok** (oracle, diagnostics, research-first build work): textures and materials to completion in the slice,
  distant LOD, the 3D surface map view and map markers, the garage wiring, the face and voice research for B2, and the
  acceptance oracle for claims it did not build.

## 2. Phase C (later): a launcher and a Fallout core on Creation Engine 2

The owner's words, verbatim: "then lets move to making a launcher like fallout london has where it focuses on the core
of what we need removes the starfield unneeded bits and start building what we need for a base core to make a build to
play any fallout from in creation 2 with the base same idea with fallout 4, a second one that allows a playthrough of
all games as one player then a mode an a third build for a stalker gamma style experience the reason for this i
modding it makes it so people have a build or something better to target".

Read as: a launcher, a shared base core, and three builds on it (any Fallout game on Creation Engine 2, made the way
Fallout 4 is; all games as one playthrough; a STALKER GAMMA style build), so that modders have a common target. "Then
a mode" is not yet resolved: whether the all-games playthrough is its own build or a mode of build 1 is confirmed with
the owner before C3 is designed.

### C1. The launcher

The owner's model is the launcher Fallout London has; what it does step by step is Codex's first Phase C research
item (Fallout London's GOG installer copies that team's own original content into the player's Fallout 4 folder, and
Steam owners run a downgrader that asks for their Steam login and rewrites the install; our builds contain Bethesda's
content, so we cannot ship them, and we never ask for store credentials). Ours, for the user's own Starfield: it checks
both game copies and only reads the Fallout 4 install; runs the converters on the user's machine against the user's
own files (the project ships only its own code, scripts and documentation, never converted records, meshes, textures
or audio); sets the plugin list and INI profile; keeps the Starfield content the build does not need out of play
through override records from our own plugin and a start option (Starfield.esm stays loaded because our plugins master
it; nothing is deleted, no executable is touched, and every change is recorded so the vanilla profile restores the
previous plugin list, INIs and Data folder); and launches. For players it replaces today's exp_install step. It ships
the runtime scripts the observation bridge carries today (FO4SF_LoadDoor), not the bridge's test telemetry.

### C2. The base core

One shared foundation under every build: the conversion toolchain, the Fallout systems on Creation Engine 2 (SPECIAL
and perks, radiation, the Pip-Boy-style interface, the workshop, factions, weapon and armor frameworks, dialogue
camera), the launcher, and the acceptance machinery. Modders target the core, not a particular build. This revisits
PLAN.md's non-goal on reimplementing VATS and the Pip-Boy: the base-core note says which systems get Starfield-native
equivalents and which are rebuilt, and PLAN.md is updated once the owner agrees.

### C3. Three builds on the core

| Build | What it is | Notes |
|---|---|---|
| **1. Any Fallout on Creation Engine 2 (the base)** | each Fallout game playable on its own in Starfield's engine, made the same way as Fallout 4; Fallout 4 comes first and is the end state of this port | the Commonwealth, its interiors, actors, quests; other games follow as their converters exist (build 2's notes) |
| **2. All games, one playthrough** | one character through every Fallout world in sequence | each game needs its own converter and the player's own copy of that game. Fallout 3 and New Vegas are Gamebryo-era (a second reader feeding the same pipeline). Fallout 1, 2 and Tactics are 2D, so they would be hand-built recreations outside the deterministic pipeline (PLAN.md section 2), each a project of Fallout London's size. Fallout 76 is an online game under its own terms; whether it is in scope is the owner's call after research |
| **3. STALKER GAMMA style** | original systems built on build 1 and inspired by the STALKER GAMMA modpack: anomalies, artifacts, A-life style spawns, weapon degradation and repair, hunger, thirst, sleep, faction wars, an economy | no assets, scripts or code from STALKER, Anomaly or GAMMA's component mods, which have their own authors and licenses |

### Constraints that hold for all of Phase C

- Players own every game a build reads (Starfield and each Fallout game it converts), and converters read those copies
  on the player's machine. Nothing of Bethesda's or any other studio's is redistributed, and the launcher never changes
  a game's executable or removes anything from an install.
- Each build is useful on its own, in the spirit of PLAN.md section 5.
- Research before machinery: the launcher and each system start as a written design with a go/no-go, reviewed on
  #32, before code. A launcher alone cannot remove engine limits (#286).

### First steps for Phase C (research, after Phase B's exit)

- **Codex:** extend #286 (the open launcher and streaming spike) with what Fallout London's installer and the FO4
  Downgrader actually do step by step and which steps we must not copy; then a design for install, profile, plugin
  order, INI, verification and rollback on top of scripts/game/exp_install.py and the recoverable deployment work.
- **Grok:** a survey of the Fallout systems that have no Starfield equivalent (SPECIAL, VATS, Pip-Boy, radiation,
  settlements) and how other Creation Engine 2 mods approach each; a design note for the STALKER-style systems set.
- **Claude:** the base-core boundary (what is shared, what belongs to a build) and the order of builds.

## 3. Immediate assignments (while Phase A testing finishes)

- **Grok**, in this order, each item research-first with a go/no-go note on #32:
  1. **the 3D surface view in the map, for this testing stage** (the owner: "lets task grok to make a 3d view for the
     surface view in the map view for this stage in testing"): a short research note on what Starfield's surface map
     draws from (the world's terrain and its LOD, the planet's own data, object LOD), why ours would show Mars (the
     overlay's Location is parented to the Mars surface, docs/terrain/map-markers.md) and whether an overlay world can
     appear there from our own plugin and locally generated files; then the build on #296's marker after its LCSR fix.
     Acceptance: a screenshot of the surface map opened at Red Rocket showing the Commonwealth terrain in 3D with the
     Red Rocket marker (Claude takes it);
  2. the review fixes on #288, #289, #290, #296 and the #303 wire-only review (clip alias out); after Codex's QA, Claude runs the reconversion and
     the in-game checks;
  3. the object-LOD trial from #303's plan, with Claude on the build side (the exterior writer and staging are Claude's;
     Grok hands over patches, or the file scope is agreed on #32 first).
- **Codex:** independent QA of Grok's #303 writer change, the round-trip run's evidence review, #301 (the #293
  follow-up) to merge after QA, then the Phase B record machinery design (quest, dialogue, packages) as a written note
  on #32.
- **Claude:** the round-trip runner window and the owner's next install (door-enabled exterior, dimmed lights, the
  door-script bridge), the interior rebuild with the gate and water fixes, the carry-mass experiment with the owner,
  then the NPC and mission plan with the owner.
