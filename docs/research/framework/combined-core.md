# The combined core: the GAMMA-style way to play

Owner: the Combined core thread (Claude-cloud). Started 2026-10-19 23:20Z on the owner's ask (23:19Z): "continue work
towards my second idea of a stalker gamma style thing because that has more value of being made without the stuff with
legal implications". Part of the [next-phase framework](README.md); this file is indexed there by the Framework thread,
not edited from here. Raw notes and prototypes: [combined-core-notes/](combined-core-notes/).

Evidence labels follow docs/ai/research-log.md: **verified**, **supported hypothesis**, **unresolved**. Nothing here is
decided unless a line says "decided by owner" with a date. Question IDs are `CC-nn` (stable; new ones are appended).

Revision 2 (2026-10-19 ~23:55Z): revision 1 (definition, fence, layers, plan, questions) plus the three research notes
and the simulation prototype folded in; CC-02 corrected (SFSE has no co-save today); PC probes listed.

## In short

- **What it is.** The second way to play (MU-3): one large, curated Fallout on Starfield's engine for players who own
  every included game plus Starfield, built like S.T.A.L.K.E.R. GAMMA is built on Anomaly: one cohesive experience on
  games the player already owns, not a pile of mods. Where GAMMA leans on survival, ours leans on **settlements that
  grow, factions that act on the world and a connected wasteland**; survival is one layer. Each game's main story stays
  playable as written, and a clean, low-effort option plays all the stories in chronological order.
- **Why now.** Its value is in our own systems and writing (simulation, settlements, factions, economy, events), which
  carry none of the open legal items (voice, Fallout 76, licensed music). It can be designed and prototyped now and,
  if the owner agrees (CC-01), first played on the converted Commonwealth alone, with the other worlds plugging in as
  their converters and Bethesda's answer allow.
- **Order (default, owner can change).** The approved phases keep their order: new game, door animations, all
  interiors, launcher. Both ways to play stand on them. The combined core runs beside them as design and PC-free
  groundwork. **Owner, 23:24Z:** keep going where we are and get the stories working, but going forward build these
  systems first, ahead of the single-game mode's extras (CC-01). First in-game work waits for the v6e test and the PC
  being free; small probes only on the owner's word.
- **Shape.** A game-neutral world-state model (who holds which place, what each settlement has and needs, which routes
  join them), an off-screen simulation that advances it on game time, and a presentation layer that turns it into
  actors, quests, radio and terminal news when the player is near. Converted worlds are content packs on top. It is
  the same "pack on a shared core" model the owner set on 2026-10-17 (GAMMA on Anomaly).

## What the owner has said (the source of truth for this file)

Quoted as written; dates are 2026-10-19 unless marked.

| When | Where | Words | What it settles here |
|---|---|---|---|
| 2026-10-17 15:34Z | project chat, recorded in plans/core-launcher/core-launcher-plan-2026-10-17.md section 7 | the STALKER-style build is a pack on the shared core, like GAMMA on Anomaly, and the core is what modders target | packs on a shared core, not a fork |
| 21:37Z | Questions page, MU-3 note | "There's going to be two options one that allows you to pick through whichever games You own ... The other core is going to require you to have all of the games and Starfield So it is going to lock out a lot of players, but I don't care" | two cores; this one requires every game |
| 21:37Z | MU-4 note | "the larger core it's gonna be a combination of systems from previous games because the faction system didn't exist in fallout four like it did in NV" | superset of systems |
| 21:37Z | MU-2 note | Fallout 76: no online parts, "just the gameplay story stuff"; "mostly just for the other core To have access to the location"; "We will likely add the best version of a location If there's multiple like the pit" | 76 places for this core (now waiting on Bethesda, REL-60); one version of repeated places |
| 21:37Z | NG-4 note | the second way "will build off of starfields and take the original skills and stuff from previous games and build a good RP style version of the special system" | an RP-style SPECIAL plus skills on Starfield's character system |
| 21:37Z | FS-4 note | power armor in "fallout four and 76 and the other big core" is climb-in, "a secondary suit that makes things different" | climb-in power armor here |
| 21:37Z | NG-9 note | "don't take away the idea of using the ship as a virtabird to maybe be used for the second core" | the ship as a vertibird is a candidate here |
| 21:37Z | NG-20 note | "Like stalker gamma you will be given a menu to pick for the core ... The second one will be just pike gamma just a little different" | chosen from the same in-game menu |
| 21:37Z | WO-4 note | placing places has "its own issues if we have world generation that we allow players to go through that re-create certain locations to an idea of what they might be like based off of all of the lore" | assisted or procedural world generation is in scope later |
| 21:37Z | RE-8 note | "I just really want a stalker Gamma style fallout experience." | this is the project's goal |
| 22:24Z | Framework thread | the second build should be "kind of like what stalker gamma does with more of a push to expand settlements and faction features ... to differ from gamma and even the normal fallout experience to not just way more on survival but other factors mods have only really scraped" | pillars: settlements, factions; survival not the focus |
| 22:24Z | Framework thread | "it just has a way to play through all of the stories in chronological order, but that's not really gonna be something that has a lot of effort put into it just something that's made clean" | chronological option, low effort, clean |
| 22:29Z | the letter as sent (research/outreach/bethesda-letter-draft.md) | "The combined mode is the heart of the project"; settlements, factions, connected wasteland, survival as one layer; original stories stay playable | what Bethesda was told; the design must not contradict it |
| 22:38Z, 22:54Z | project chat (per project memory) | voice reuse is a known no for Fallout 3 and New Vegas | no FO3 or NV voice, ever, unless that changes |
| 23:19Z | this thread | GAMMA-style first "because that has more value of being made without the stuff with legal implications" | this workstream |

Other decisions this file builds on, not re-asked: SFSE required with our own small plugins (and the owner's NG-1 note
on our own script extender for older games' scripts later); silent player; FO4 1.10.163; all DLC required; Steam only
for v1; no money or store listing before 1.0; ship no assets; Starfield kept and stripped step by step (WO-3); copy
Alternate Start and BACUP code where useful, GPL-3 with credit (LA-13, WO-8); Vault 111 start with a start-world hook
(MG-18 / NG-8); light flags only between worlds for companions and story state (MG-19 / MU-6); same planet at real
relative positions (MU-5); FO4 names now, rename later for shared stats (FS-1); full VATS (FS-5); dismemberment kept via
SFSE (FS-6); bobby-pin locks (FS-3); converted FO4 outfits (PE-5).

## The legal fence

What this core may use, so the owner's reason for starting it holds. Readings, not legal advice.

| In | Out until the owner or Bethesda says otherwise |
|---|---|
| Our own systems, scripts, SFSE plugins, data tables, writing (notes, terminal text, radio news text, quest text we author), our own UI | Voice lines from Fallout 3 and New Vegas (known no) |
| The converted Fallout 4 world, built on the player's PC from their own install (same basis as the single-game mode) | Fallout 4 voice reuse beyond what the single-game mode settles (open until Bethesda answers question 3) |
| Starfield's own records and assets, referenced in place (never copied out) | Any Fallout 76 content (REL-60; Bethesda's answer to question 5) |
| Ideas from GAMMA, Anomaly, Sim Settlements, New Vegas and others, rebuilt in our own work | Code, scripts or assets from STALKER, Anomaly, GAMMA's addons or Fallout mods, unless their licence allows it (GPL-3 code such as Alternate Start and BACUP, with credit) |
| Silent voice files we generate per text line (PS-38, PS-39) | Licensed music (a separate question from voice) |
| Fallout 3 and New Vegas worlds, records and text, later, converted on the player's PC (MU-3; Bethesda question 2) | AI-generated voices (the letter says we are not making them) |

Consequence: **every system here is designed to run on one world (the Commonwealth) and to take more worlds as data**.
Nothing in the systems may assume a second game is present; nothing may assume it is absent.

## Definition: the five pillars

Each pillar lists what the owner asked for, what we add on top as a default to argue with, and its ID range.

1. **Settlements that grow** (CC-10 to CC-19). Owner: "more to build, settlers with roles and needs, trade and supply
   lines between settlements, and settlements that matter to the world around them" (letter). Default: a settlement
   is a world-state entry with population, roles (farmer, guard, trader, crafter, scavenger, doctor), stock of food,
   water, scrap, ammo and medicine, defence, morale and a growth stage. It grows by stages even when the player is not
   building (the simulation places our own prefab layouts), and the player's own building feeds the same numbers. A
   grown settlement attracts trade, raids and faction interest.
2. **Factions that act** (CC-20 to CC-29). Owner: "the factions of every game present at once, with reputation that
   carries across regions, territory that can change hands, and choices that shift how each faction treats the
   player" (letter); "the faction system didn't exist in fallout four like it did in NV" (MU-4). Default: each faction
   has goals, strength, holdings and relations with other factions; abstract squads move between places off-screen and
   become real actors near the player; territory is held per location; reputation is New Vegas-style (fame and infamy
   per faction, per region later) on top of Starfield's faction relation records.
3. **A connected wasteland** (CC-30 to CC-39). Owner: "travel, trade and conflict linking the Commonwealth, the Capital
   Wasteland, the Mojave and Appalachia, so events in one region can be felt in another" (letter). Default: a route
   graph of places (settlements, faction bases, landmarks, region gateways) carries caravans, patrols and news; events
   are world-state changes that spread along it at travel speed. Region-to-region travel uses the scripted travel
   already decided (NG-9), with the ship-as-vertibird idea kept for this core.
4. **Survival as one layer** (CC-40 to CC-44). Owner: "Survival as one layer among these, not the whole point"
   (letter). Default: an optional module with its own switches (hunger, thirst, sleep, disease, carry weight, gear
   wear), off by default in story-only play, shaped by the settlement economy (food and water come from somewhere) and
   never required by the other pillars.
5. **Stories** (CC-50 to CC-54). Owner: each game's main story "stays playable as it was written"; a chronological
   option "made clean" with little effort. Default: the sandbox is the frame and the converted main quests run inside
   it untouched; the chronological option is a start setting that unlocks each game's opening in date order (FO3
   2277, NV 2281, FO4 2287; dates from multi-game-future.md MG-18) and mutes the sandbox's pressure on story places
   while a story is active.

Cross-pillar systems the owner placed here: the RP-style SPECIAL plus older skills on Starfield's character system
(NG-4), climb-in power armor (FS-4), the superset rule set (MU-4), one version of repeated places (MU-2), assisted world
generation for lore places later (WO-4), the ship as a vertibird (NG-9). They get IDs CC-60 onward.

## Architecture: layers

```
L5  Content packs        Commonwealth pack (first) | Capital Wasteland | Mojave | Appalachia (gated) | community packs
L4  Player systems       reputation UI | settlement management | survival module | RP SPECIAL + skills | power armor
L3  Presentation         materialize squads and caravans near the player | radiant quests | radio and terminal news
L2  Simulation           faction AI (goals, squads, territory) | settlement growth | supply and trade | events
L1  World-state model    places | holders | settlements | factions | routes | events  (game-neutral, data-first)
L0  Converted worlds     per-game modules from the single-game pipeline (FO4 now), shared with the other way to play
```

Rules for the layers (defaults):

- **L1 is data, not script.** Place, faction and route tables are generated offline (from the converted records plus
  our own authored tables) and shipped as our data. At runtime the state lives in one place we control, so saves stay
  small and repairable (CC-02). This is the layer the owner's "get a choice right early" applies to most.
- **L2 runs on game time in coarse ticks**, entirely on the abstract data, never on loaded actors. It must be
  deterministic for a given seed so it can be tested offline and replayed from a save.
- **L3 is the only layer that spawns things.** It materializes what L2 says is near the player and dissolves it back
  into data when the player leaves. No permanent spawned references.
- **L5 packs only add data and content.** A pack declares its places, factions, routes, region gateway and story
  quests; it never changes L1 to L4 code. That is what keeps the Commonwealth-first build from forcing a rebuild later.
- **Engine specifics stay in adapters**, the way the project topic asks for the leader core: L1 and L2 do not know
  Starfield's record layouts; an adapter maps state to globals, quest aliases, faction relations or an SFSE co-save.
- **Not the leader core.** `src/fo4sf/core/` in the repo is the build-and-test orchestrator (ledger, lease, preflight).
  The combined core is game runtime. Names must not collide (CC-03).

## How it relates to the other way to play and the approved phases

- **Shared:** the converters, the new-game start (Vault 111, with the start-world hook from MG-18), door animations,
  interiors, the launcher, map markers, SFSE base plugin, the Fallout systems (VATS, Pip-Boy, power armor, locks).
- **Needs from the approved phases (no extra work asked of them now, just keep the door open):**
  - Interiors: a location record per interior (already a required consequence in project memory) and encounter-zone
    and cleared state; territory is per location, so without locations there is nothing to hold.
  - New game: the in-game menu entry (NG-20) chooses between the two ways to play; the start-world hook (MG-18) is
    where faction starts would hang (CC-51).
  - Launcher: a module list that can say "combined core: requires every game"; the DLC and game checks it already has.
  - Workshop conversion (later phase): settlements in this core are FO4 workshops plus our state; how the workbench
    and Starfield's outpost layer are reused is engine-mechanics/workshop-and-settlements.md's open question.
- **Different from the single-game mode:** this core changes the world's behaviour (factions move, places change
  hands). The single-game mode stays faithful to each game's rules. Both read the same converted worlds.

## Groundwork that needs no PC (in order)

| # | What | Output | Status |
|---|---|---|---|
| G1 | Definition, fence, layers, questions | this file | revision 1 |
| G2 | GAMMA anatomy and lessons | combined-core-notes/gamma-anatomy.md | done |
| G3 | Precedents for growing settlements and acting factions (Sim Settlements 2, New Vegas reputation, Skyrim Civil War, Starfield outposts, Mount & Blade, Kenshi) | combined-core-notes/settlements-factions-precedents.md | done |
| G4 | Engine fit: how each system maps to Starfield's engine, what needs SFSE, risks, smallest probes | combined-core-notes/engine-feasibility.md | done |
| G5 | World-state schema (L1), game-neutral | combined-core-notes/prototype/ | first cut done |
| G6 | Offline simulation prototype (L2) on synthetic data, deterministic, with tests, to tune rules on paper before any game work | combined-core-notes/prototype/ | first cut done, 9 tests |
| G7 | Commonwealth seed tables: which FO4 locations, workshops and factions become L1 places and factions, generated from the player's FO4 data by a reader (written and tested on synthetic fixtures; run on the PC later) | combined-core-notes/ then a branch | after G5 |
| G8 | PC probe list for after v6e (off-screen actors, co-save, Story Manager events, outpost reuse) | this file, "Probes" | done (P1 to P10) |

Nothing here is pushed to the repository yet (thread rule). When G5 to G7 are stable they go to a draft PR on the
owner's word, with tests per AGENTS.md.

## Questions

### Decide early (a wrong choice means a rebuild)

**CC-01. Where does the combined core first run?**
- Why: the systems carry no legal items; the other worlds do. Waiting for every game means nothing playable for a long
  time.
- Options: A. On the converted Commonwealth first; other worlds plug in later as packs. B. Only once every game is
  converted.
- Recommend A. Who: owner. Status: **decided by owner, 2026-10-19 23:24Z (A, as read by this thread):** "So I still
  want to get the stories working let's continue where we're at but forward focus on building these other things first
  instead of the other one for now". Read as: work in flight continues and the stories still get made working; going
  forward, the combined core's systems are built ahead of the single-game mode's extras, first on the Commonwealth.

**CC-02. Where does runtime world state live?**
- Why: decides save size, repairability and how much needs SFSE. Script-heavy state is the known save-bloat and lag
  risk in Sim Settlements 2 (its FAQ) and Skyrim's Warzones (settlements-factions-precedents.md, **verified** as the
  mods' own warnings; no measured save growth found).
- Correction (revision 2): **SFSE has no co-save today.** Serialization was disabled in SFSE 0.2.12 and is still off in
  0.2.21 (**verified**, sfse_whatsnew.txt); SFSE does send PreSaveGame, PostSaveGame, PreLoadGame and PostLoadGame
  messages with the save name (**verified**, PluginAPI.h, Hooks_Serialization.cpp), so a plugin can keep a sidecar
  file per save. Risks: no message when a save is deleted (orphans), Steam Cloud likely skips the sidecar.
- Options: A. Papyrus quests, globals and arrays only. B. SFSE plugin with a sidecar per save, Papyrus as front end.
  C'. Hybrid: the state the game must read (holder per place, reputation tiers, story-mode switch) in records the save
  keeps (globals, location keyword data, quest variables), readable by conditions, dialogue and leveled lists without
  SFSE; the bulk simulation in the SFSE plugin and its sidecar. If a patch breaks SFSE the world freezes rather than
  the save corrupting.
- Recommend C' (engine-feasibility.md), with A as the fallback for about 20 places. Probes P1 and P2 decide it. Who:
  team, then owner. Status: open.

**CC-03. Naming.** New records for this core need a prefix that is not the leader core's and not `FO4SF_`.
- Options: A. `FOCC_`. B. per-pillar prefixes. Recommend A for records made only for this core; shared Fallout systems
  keep FS-1's rule. Who: team. Status: default A.

### Pillar questions (answer later, listed so nothing is forgotten)

- **CC-10.** Do settlements grow without the player (simulation places our prefabs), only through player building, or
  both? Default both.
- **CC-11.** Which places can become settlements: FO4's workshop locations only, or any cleared location? Default
  workshops first.
- **CC-12.** Settler roles and needs list. Default the six roles above; needs food, water, beds, defence, medicine.
- **CC-13.** Supply lines: FO4's provisioners rebuilt, Starfield cargo links reused, or our own caravans? Default our
  own caravans on the route graph, using provisioner behaviour where it fits.
- **CC-20.** Which factions act in the Commonwealth pack (the Minutemen, Brotherhood of Steel, Institute, Railroad,
  raiders, gunners, super mutants, the Children of Atom and others), and which never lose their home base?
- **CC-21.** Can story-critical places change hands while their story is unfinished? Default no: story places are
  locked to their story holder until the story passes them (keeps each game's story "as it was written").
- **CC-22.** Reputation: one global value per faction, or per region (New Vegas-style fame and infamy per faction)?
  Default per faction now, per region when a second world exists.
- **CC-23.** Do the player's story choices (for example siding with one faction in FO4's main quest) drive the
  sandbox's faction strength? Default yes, as light flags.
- **CC-30.** How visible is the off-screen world: radio news, terminal reports, a map overlay of territory? Default
  radio and terminal text first (our writing, silent voice files), map overlay later.
- **CC-40.** Survival module defaults: off, light, or full? Default off with presets.
- **CC-41.** Raid pressure: a player setting (how often factions attack settlements), as GAMMA's critics and SS2's
  attack options suggest? Default yes, three presets.
- **CC-04.** Reuse Workshop Framework code sections with credit, if its author's note allows it despite the page's
  ban on conversion? Default no: write our own (owner decides).
- **CC-50.** Chronological story option: start each game's opening in date order, with the sandbox muted? Default yes.
- **CC-51.** GAMMA-style starts (pick a faction and a starting place) alongside Vault 111? Status: **decided by owner,
  2026-10-19 23:29Z: A** (Vault 111 stays the story start; faction starts added later, using Alternate Start's GPL-3
  code where it fits). The new-game phase needs nothing now beyond the start-world hook it already has (MG-18).
- **CC-60.** RP-style SPECIAL with older games' skills (NG-4): its own design note after G4.
- **CC-61.** The ship as a vertibird (NG-9): its own probe later.
- **CC-62.** Assisted world generation for lore places (WO-4): later, after MU-1's multi-game spike.

## Research folded in

Three notes in [combined-core-notes/](combined-core-notes/) (every fact sourced and labelled there) and the
[prototype](combined-core-notes/prototype/README.md).

**GAMMA** ([gamma-anatomy.md](combined-core-notes/gamma-anatomy.md)):
- GAMMA is 400+ addons on the free Anomaly mod (Monolith, a 64-bit X-Ray fork, with Story, Sandbox and Warfare
  modes); since December 2025 also a free GOG one-click install needing an owned base game; the pack repo is AGPL-3.0
  (**verified**). Its README says it "redistributes little to no copyrighted content"; the launcher fetches each addon
  from its own page into Mod Organizer 2 with credit (**verified**). Same model as ours; its weak spot is third-party
  hosts blocking the installer.
- **Warfare mode (Anomaly's, so also part of GAMMA, which runs on Anomaly; owner 23:29Z) is the closest match to the
  owner's goals:** factions capture points, bases fall, an
  off-screen combat simulator lets squads intercept each other, a PDA tab shows progress (**verified**). An overhaul
  addon adds point types (base, resource, territory, lair) and respawns that scale with bases held (**verified** for
  the addon only).
- A-Life simulates NPCs fully within about 150 m and coarsely elsewhere (**verified**): the L2/L3 split above.
- What players love: progression and purpose in a sandbox, a "struggle up the loot ladder", no fully safe place. What
  they hate: repetitive money-only radiant tasks, install friction, crashes and frame drops (one report).
- GAMMA's economy ties good gear to danger and story progress, removes weapon and armor selling, and stocks traders by
  supply tier and reputation (**verified**). That maps onto settlement supply setting vendor stock.

**Settlements and factions** ([settlements-factions-precedents.md](combined-core-notes/settlements-factions-precedents.md)):
- Sim Settlements 2 proves the settlement ideas (city plans levelling up after days at minimum happiness, leaders,
  plot types, industries, resources as numbers, caravan supply lines that break when the caravaneer is hurt, a
  Chapter 3 war system with outposts and territories) (**verified**, its wiki). Its permissions forbid modification
  and conversion: ideas only. Workshop Framework's page both forbids conversion and allows reuse of sections with
  credit; the owner decides before any reuse (CC-04).
- New Vegas reputation: two scales per faction (fame, infamy), a 4x4 grid of named states, gains in tiers of 1, 2, 4,
  7, 12 (**verified**). No Fallout 4 mod runs dynamic faction territory over the whole map (**supported hypothesis**:
  none found).
- Starfield: cargo links already move goods between outposts and crew can be assigned; no Starfield mod has real
  settler populations or faction wars (**verified** as none found).
- Skyrim's Civil War shows the failure to avoid: hold ownership drifting from what is in the world; Warzones' always-on
  script was its save-bloat cause (**verified**, mod pages).
- Lessons adopted: settlements as data with actors only near the player; real, breakable supply lines; growth from
  needs met over time; NV two-scale reputation; one record of who owns what, plus a repair tool; settle off-screen
  fights with numbers; no always-running global scripts; player control over raid pressure (CC-41 below); measure save
  growth from day one.

**Engine fit** ([engine-feasibility.md](combined-core-notes/engine-feasibility.md)):
- Condition functions exist in Starfield to read the state without script: GetGlobalValue, GetKeywordDataForLocation,
  GetKeywordDataForCurrentLocation, LocationHasKeyword, IsLocationLoaded, GetVMQuestVariable (**verified**, xEdit SF1
  definitions). So a place's holder can be keyword data on its location and spawns can follow it through conditioned
  leveled lists (whether keyword data survives a save: **unresolved**, P2).
- Squads are table rows; they become actors through Story Manager location events and alias quests and go back to data
  when the player leaves (A-Life pattern).
- **Hard prerequisite: a location record on every converted interior** (our interiors have none yet, interiors.md,
  **verified**). Settlements cannot be registered at runtime and FO4's "cleared" functions are missing in Starfield.
- Faction relations are game-wide, so "hated in one region, liked in another" needs our own layer (CC-22).
- Growth stages are pre-built object layers switched on and off, not objects placed at runtime. Starfield's cargo
  links (which are ships) stay out of our world by default; our caravans are our own.
- News: terminals and on-screen text first; spoken radio news waits on the voice question.
- The chronological switch is a global plus stage conditions, no SFSE.

**Prototype** ([prototype/README.md](combined-core-notes/prototype/README.md)): the L1 model and an L2 tick in Python,
9 tests passing (determinism, save replay, story places and homes never change hands, a second region plugs in). It
already showed growth needs a role rule and a cap, faction strength needs upkeep, a region with only faction homes
freezes, and capture must hurt the settlement.

## Probes for the PC (after the v6e test, one at a time, read-only or staged, on the owner's word)

From engine-feasibility.md; none run, none queued. Order: P1, P2, P3 decide CC-02 and the territory design.

| # | Probe | Settles |
|---|---|---|
| P1 | SFSE plugin writes a sidecar on PreSaveGame and reads it on PostLoadGame; save, load, load another save, delete a save | sidecar viability, orphans |
| P2 | SetKeywordData on our location, leave, save, reload, read it back | keyword-data persistence |
| P3 | our location with and without the overlay parent: keyword data, explored state | location data on our interiors |
| P4 | materialize 3 squads at a marker on location change, dissolve, 20 cycles, save size | spawn reliability, save bloat |
| P5 | Papyrus tick over 50 places, timed | script latency baseline |
| P6 | leveled-list entry conditioned on location keyword data; flip it, reset the cell | data-only territory spawns |
| P7 | vendor refuses service by reputation tier | reputation effects |
| P8 | enable-parent stage swap at a converted settlement, save size before and after | build stages |
| P9 | one caravan on a travel package across 4 exterior cells | long-route pathing |
| P10 | SendStoryEvent from our script starts our quest | event plumbing |

## Risks

- Scope: this is the largest thing in the project. Breadth before polish applies: one faction loop and one settlement
  loop end to end on the Commonwealth before any more.
- Save growth and script lag from simulation state (G3 and G4 will cite precedents).
- Story breakage: factions taking story places. CC-21's default prevents it.
- Starfield updates breaking our SFSE plugin; the same risk the project already carries for SFSE (VM).
- Expectations: the repo is private and there are no public promises (project rule); this file makes none.
