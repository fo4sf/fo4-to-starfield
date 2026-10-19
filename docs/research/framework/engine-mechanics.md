# Next-phase framework: engine mechanics and the Fallout systems rebuild

Owner's ask (2026-10-19 17:41Z, paraphrased): keep sending research agents out on each area (the modding communities,
the tools, precedents, the possibilities) and build a framework of questions for the next phases; it can be large, it
should be built right. This file covers the engine mechanics and the Fallout systems we rebuild on Starfield (Pip-Boy,
VATS, workshop, power armor, perks, companions, dialogue, quests, radio and the rest) and the tools behind them. The
world and planet, people and story, release and legal, and tooling and testing areas are in the framework index
(README.md beside this file, owned by the framework thread).

Author: Claude-cloud (Mechanics thread). Status: **first wave complete, wave 2 rechecks folded in** (all seven areas, about 400 questions in the notes; 18:10Z). Wave 2 re-reads the pages
the agents could not reach (web rate limits). Labels:
**verified** / **supported hypothesis** / **unresolved**.

## How to read it

- Each area below has: what the community and tools offer today, precedents, possibilities and hard limits, and a
  **question table**. Every question says why it matters, what we know, the cheapest way to answer it, what it depends
  on or blocks, and its phase. **Key** questions decide a design; the rest refine it.
- Phases: **P1** new game (Vault 111 start), **P2** interiors and doors, **P3** quests and people, **P4** Fallout
  systems (Pip-Boy, VATS, power armor, workshop, perks), **P5** release (launcher, Nexus).
- How things work is in the reference: [../engine-mechanics/README.md](../engine-mechanics/README.md). This file asks
  what we still need to find out and decide.
- Agent notes, one per area, are in [engine-mechanics-notes/](engine-mechanics-notes/); this file folds them in.

## The decisions this framework drives (first wave)

The questions below decide the most; each links to its area. Owner decisions are marked.

1. **Voice reuse (owner, before release).** Reusing FO4's voice files inside Starfield is the Capital Wasteland case
   (Bethesda licenses voice acting, cannot grant reuse); ask Bethesda, or plan text-first and silent files. (quests A1)
2. **UI stack.** Replace vanilla menu files (consoles, but breaks on patches) or an SFSE HTML framework (OSF UI with a
   Papyrus API; Carbon UI pinned to one build) or our own SFSE menu. Decides Pip-Boy, HUD, SPECIAL display. (UI 1.1 to
   1.3, L3)
3. **How much SFSE we require.** Command mode, affinity, slow time, legendaries and most progression work without it;
   menus, radio outside Wwise and a faithful VATS need it. SFSE co-save is off, so state lives in records and Papyrus.
   Game updates broke native plugins four times. (X1, X7, companions R2)
4. **Our own frameworks, never Starfield's quests.** Follower framework, settlement rules layer and build categories are
   ours; Starfield's follower lines are locked behind MQ101 and its build lists are shared by every outpost mod.
   (companions F2, workshop B1)
5. **Hostility through relations.** The likely fix for Preston turning hostile is a Friend or Ally relation to the
   player's faction (hit allowance), testable in one run. (companions H2)
6. **New sounds and new animations are unproven.** Every sound mod replaces existing `.wem` by id; adding clips or
   graphs is disputed. These gate radio, creatures, power armor enter and exit. (animation B1, B2, H1, H2)
7. **Power armor route.** No furniture-based power armor exists in Starfield; the options are an outfit, a race swap,
   or furniture plus `SwitchToPowerArmor` (declared, behaviour unknown). (character A1 to A4)
8. **VATS shape.** Full VATS or bullet time; whichever we pick, the VATS perks are redesigned with it. (UI 11.1)
9. **Plugin layout.** Full or medium masters per output plugin, fixed before release. (tools)
10. **Headless CK steps.** Compiling about 10,000 scripts and lip generation from the launcher, or in the CK GUI.
    (tools, quests L1)

## Areas and status

| area | covers | reference pages | notes | status |
|---|---|---|---|---|
| UI, Pip-Boy, VATS | Pip-Boy, HUD, menus, dialogue and barter UI, terminals, map, Missions menu, V.A.T.S. | ui-pipboy-hud-menus, vats, terminals-holotapes-locks | [ui-pipboy-vats.md](engine-mechanics-notes/ui-pipboy-vats.md) | **done** (11 question tables) |
| Quests, dialogue, voice | quest authoring, Story Manager, radiant, scenes, choice list, voice, lip sync, strings | quests, dialogue | [quests-dialogue-voice.md](engine-mechanics-notes/quests-dialogue-voice.md) | **done** (13 mechanisms, about 60 questions) |
| Companions, AI, factions, combat | follower frameworks, affinity, packages, factions, crime, combat, stealth | companions, ai-packages-and-schedules, factions-crime-relationships, combat-detection-stealth, starfield-systems-to-reuse | [companions-ai-factions-combat.md](engine-mechanics-notes/companions-ai-factions-combat.md) | **done** (10 mechanisms, about 65 questions) |
| Character systems | SPECIAL, perks, leveling, health, limbs, radiation, survival, power armor, races, faces, creation | special-perks-leveling, health-damage-effects, power-armor, actors-and-npcs, saves-and-new-game | [character-systems.md](engine-mechanics-notes/character-systems.md) | **done** (49 questions, 21 key) |
| Workshop, items, economy | settlements, build mode, crafting, mods, legendaries, caps, vendors, loot | workshop-and-settlements, items-crafting-modding, economy-vendors-barter, leveled-lists-and-encounter-zones, dlc-mechanics | [workshop-items-economy.md](engine-mechanics-notes/workshop-items-economy.md) | **done** (58 questions, 30 key) |
| Tools and scripting | Creation Kit, Papyrus compilers, SFSE and plugins, xEdit, Mutagen, archives, mesh and material tools, Wwise | papyrus-and-script-extenders, records-and-plugins, materials-textures-lighting, physics-and-collision | [tools-and-scripting.md](engine-mechanics-notes/tools-and-scripting.md) | **done** (10 question groups) |
| Animation, audio, physics | behaviour graphs, clips, furniture, radio, music, Wwise, Havok | animations, radio-music-sound, physics-and-collision, doors-activators-furniture | [animation-audio-physics.md](engine-mechanics-notes/animation-audio-physics.md) | **done** (13 groups, 22 key) |

## Cross-cutting key questions (seeded from the reference; agents will extend them)

| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase |
|---|---|---|---|---|---|---|
| X1 | Which FO4 systems need SFSE natives, and can each be done in plain Papyrus first? | decides whether players must install SFSE for each feature | about 77 FO4 engine function names are missing in Starfield's core scripts (verified, PC probe job 15) | map each of the 77 to a feature; prototype the Papyrus-only ones | blocks the shim library | P3, P4 |
| X2 | Do we compile converted scripts on the player's PC (CK compiler) or ship compiled `.pex` built from FO4 sources? | ships no game assets vs. player setup burden | FO4 sources come with the free FO4 CK (verified); Starfield's compiler ships with CK2 | ask whether compiled scripts from Bethesda sources count as assets (legal area); test Caprica | launcher design, release | P5 |
| X3 | Which Starfield systems do we reuse (affinity, legendaries, build mode, Missions menu, barter) and which do we fence out? | reuse saves rebuild work but risks Starfield progression leaking in | first list in [starfield-systems-to-reuse.md](../engine-mechanics/starfield-systems-to-reuse.md) | one in-game check per reused system | most P3 and P4 designs | P3, P4 |
| X4 | How do we name and namespace converted scripts and editor ids? | Papyrus names are global; clashes replace Starfield's scripts (both games ship `CompanionActorScript`) | verified clash | decide once, record in docs/ai/decisions.md | every script conversion | P3 |
| X5 | Voice and lip sync at FO4's scale (78,089 INFO records, 122,857 base-game `.fuz` files, project counts): CK batch lip generation, another tool, or text first? Also: may the launcher reuse FO4's voice files at all? | the biggest single cost, and a legal risk (Capital Wasteland precedent) | the player is silent (settled); voice acting is licensed, not owned by Bethesda (PCGamesN) | try `-GenerateLips:<plugin>` on Starfield's CK; owner decides whether to ask Bethesda | quests, companions | P3 |
| X6 | Pip-Boy: rebuild as a menu, reuse Starfield menus, or both in stages? | the most visible Fallout system | Missions menu reuse first for quests (reference) | survey SFSE menu frameworks | UI, quests | P4 |
| X7 | How do game updates break SFSE plugins and our tools, and how do we stay safe? | a Starfield update can break players' installs overnight | unresolved | read the SFSE and Address Library history | release | P5 |

## Questions already open in the reference

About 160 smaller open questions sit at the end of each reference page (section "Open questions and cheap checks").
They are folded into the area tables as agents return; until then, the pages with the most are vats, special-perks,
power-armor, papyrus, health-damage-effects and ai-packages (7 each).

## Area findings (folded in as agents return)

### UI, Pip-Boy and V.A.T.S. ([notes](engine-mechanics-notes/ui-pipboy-vats.md), 11 question tables)

Findings (labels and sources in the notes):
- Four ways to put UI on screen: replacing vanilla Scaleform menu files, SFSE plugins, HTML overlays, ImGui overlays.
  Two HTML overlay frameworks run on game 1.16.244 with SFSE 0.2.21; Carbon UI's code is GPL-3+ with exceptions for Ultralight, the game and SFSE, but its Nexus page asks for permission before modifying (wave 2: ask the author before forking or depending on it); OSF UI is GPL-3.0, OSF UI
  has a Papyrus API. Only menu-file replacement also reaches consoles. (verified, mod pages)
- Replaced menu files break on game patches and clash with other UI mods (StarUI after Free Lanes). If we override
  vanilla menus, the launcher should rebuild them from the player's current files. (verified, mod pages)
- Slow time is solved in open code: Slow Time SFSE (GPL-3) scales the global time multiplier and keeps the player at
  normal speed; `sgtm` works per mod pages. (verified as documented; our own test still needed)
- No Starfield VATS mod with body-part targeting turned up (absence of evidence). An FO4 bullet-time VATS mod found that
  changing VATS settings breaks perks (Gun Fu, Concentrated Fire, Penetrator) and that per-limb tracking was too heavy
  for Papyrus. (supported hypothesis)
- Skyblivion precedent: rebuild the menus that carry identity (character creation, lockpicking), keep the engine's list
  menus. For us: rebuild Pip-Boy and VATS, keep Starfield's dialogue, barter and container menus. (supported
  hypothesis)
- No digipick replacement or terminal hacking mod found; Auto Unlock SFSE shows locks are reachable from SFSE.

Key questions: 1.1 which UI stack builds our menus; 1.2 can SFSE register a new Scaleform movie as a real engine menu;
1.3 do we override vanilla menu files at all; 2.1 faithful Pip-Boy or Starfield's data menu restyled; 2.2 the minimum
Pip-Boy for the first new game; 3.1 can a menu render onto the 3D wrist mesh; 4.1 radiation bar and Geiger clicks on
the HUD; 7.1 and 7.3 digipick or bobby pins, and how terminal hacking is gated; 9.1 what the surface map shows for our
planet; 9.4 do FO4 quests read cleanly in the Missions menu; 11.1 to 11.4 full VATS or bullet time, slow time, limb
positions for targeting, how queued shots fire.

Still open from this agent: SFSE / CommonLibSF source not read (needed for 1.2); Cassiopeia Papyrus Extender support
for 1.16.244 (answered by the tools agent: 9.x supports it); Fallout London and TTW not yet read for UI lessons.

### Tools and scripting ([notes](engine-mechanics-notes/tools-and-scripting.md), 10 question groups)

Findings (labels and sources in the notes):
- Plugin limits (verified): full masters 253 slots; medium masters about 65,535 new records each, up to 256; small
  masters 4,095 each. Changing a plugin's master type after release breaks everything built on it. The converted
  data (683,870 FormIDs in the v6 builds) needs full masters or several medium ones.
- Game updates broke native plugins four times (1.8.86, 1.14.70, 1.15.216, 1.16.236; verified). The biggest SFSE
  plugin authors left Address Library and CommonLibSF; CommonLibSF moved to libxse/commonlibsf.
- Custom Papyrus natives through SFSE work: Cassiopeia Papyrus Extender 9.x supports 1.16.244 and adds over 350
  native events (verified). SFSE's save-data API has been off since 0.2.12, so plugin state lives in Papyrus or records.
- Compiler: the community compiles with the CK's PapyrusCompiler.exe from batch files; Caprica lacks Starfield guards
  but FO4 code has none, so it may still serve as a fallback; Champollion's guard output is a guess. (supported
  hypothesis)
- xEdit 4.1.5q edits Starfield plugins "with restrictions" and expects form version 581; our Mutagen alpha writes 576
  and the game loads it; how the CK and xEdit treat 576 is unresolved.
- CK lip sync is a GUI step (FaceFX compiler from the Audio menu); no command line documented. Modders use Wwise
  2021.1.14.8108.
- Community tools: BAMgr reads and writes BA2 v2 and v3 (our ba2.py cannot read v3 LZ4 textures); a NifSkope fork,
  the Void SFG Bridge Blender add-on and PyNifly handle meshes; Material Editor Lite edits emissive .mat files (a route
  for our missing glow materials); no public tool writes Starfield physics constraints.
- No FO4-to-Starfield or Skyrim-to-Starfield converter exists; "Skywind moves to Starfield" was an April Fools' story.

Key questions: master type per output plugin; can the CK compiler and lip tools run headless from the launcher, and
how long do about 10,000 scripts take; which SFSE stack, and what the launcher does when Starfield updates past
1.16.244; can Mutagen write faction relations (factions reuse) and when to move past 0.55.0-alpha.67; which BA2
writer; can WAV to .wem run without opening Wwise; which tools we may bundle and which players install.

Still open: Mutagen's README, Address Library's page and one FO4 next-gen article were rate-limited (unresolved).

### Character systems and power armor ([notes](engine-mechanics-notes/character-systems.md), 49 questions, 21 key)

Findings (labels and sources in the notes):
- Starfield now has a "Power Assist Armor" suit (tied by mod pages to the Terran Armada DLC, April 2026, which also
  added the robot companion Delta); mod pages describe it as armor with an enchantment (supported hypothesis). Every
  exosuit mod found is an outfit on the human skeleton; none uses furniture or a skeleton swap.
- Progression works mostly in data and Papyrus: perk tier gates are data (Flat Perk Tree), settings menus use Gameplay
  Option (GPOF) records, and a mod sets `fXPModBase` / `fXPModMult` and grants perk points without SFSE.
- CharGenMenu already edits Starfield's character creator and saves JSON presets; Deadly Hazards edited HUD SWF files
  without SFSE.
- No limb crippling in Starfield, only injury afflictions (Fractured Limb); afflictions are SPEL data a mod can attach
  to attacks without SFSE. Starfield's planet and water radiation run on environment conditions our planet must switch
  off or reuse.
- No FO4 face converter, no new creature skeleton or behaviour graph mod, no ghoul or super mutant mod found. NAF can
  play glTF clips per race skeleton as an interim.
- SFSE co-save is disabled, so SPECIAL, Rads, fusion core charge and survival needs must live in actor values, globals
  or Papyrus variables. StarPatcher is closed source and forbids conversion use: a pattern, not a dependency.
- Ties to Starfield: Gameplay Options, afflictions, challenge trackers for XP, Power Assist Armor, Terran Armada robots,
  and faction relations to carry super mutant, ghoul, synth and robot hostility.

Key questions: A1 to A4 power armor (what the Power Assist suit is in xEdit; what `SwitchToPowerArmor` does with a
furniture ref; a `SetRace` skeleton swap at runtime; FO4 power armor meshes worn as an outfit); S1, S2 SPECIAL actor
values and derived stats; P1 fold perk rank chains or one record per rank; P2 can Starfield's skills menu list our
perks; X1, X2 XP settings in both games and a stray skill-point prompt on level-up; H1, H2 does the cripple path fire
in CE2, or crippling on afflictions; R1 do Rads still lower max HP; V1, V2 how much of Survival is script, bed-only
saves; F1 to F8 face route, super mutant skeleton, Starfield robot rigs for FO4 robots, hiding backgrounds and traits.

### Workshop, items and economy ([notes](engine-mechanics-notes/workshop-items-economy.md), 58 questions, 30 key)

Findings (labels and sources in the notes):
- Build categories are keywords in Starfield's `OutpostRecipeCategories` list and on the build activators; categories
  cannot be added from Papyrus and mods editing those forms overwrite each other, so our activators get their own list
  and keywords. Which recipe field carries the keyword is open.
- Starfield keeps `OnWorkshopObjectPlaced` but lacks the destroyed and repaired events, `RecalculateResources`,
  `RemoveComponents`, `StoreInWorkshop`, `SellItem` and the settlement menu; no `WorkshopParentScript`. The settlement
  rules layer is ours (verified, PC probe job 15).
- No Sim Settlements for Starfield; Workshop Framework's public-API model is the one to copy under our names. SS2's
  known issues: overwriting vanilla workshop scripts causes most conflicts; "scrap everything" breaks precombined
  geometry. SS2's permissions forbid conversion, so the launcher converts only Bethesda's FO4 plugins.
- Candidate for supply lines: Free Lanes (April 2026) added a Shared Outpost Container that moves items between outposts
  (untested).
- LGDI legendaries are editable; since Free Lanes Starfield has Tier 4 effects, X-Tech rerolls and quality tiers, which
  we hide from our world.
- No precedent for renaming Credits to Caps (mods change only the model); vendor restock needed SFSE to change; vendor
  credits sit in leveled lists.
- Robots: no live robot workbench station in Starfield mods; junk to resources needed a vending-machine workaround.

Key questions: B1, B2 does an activator we own show only our categories; B5 do built objects persist in our worldspace;
B6 can build mode scrap pre-placed objects without breaking precombines; C1, C2 do our 31 FO4 components work as IRES
resources and scrap natively; S2 may the launcher read the player's FO4 workshop scripts (owner); T1, T3 supply lines,
settlement attacks and which Story Manager events still fire; T2 Shared Outpost Container as linked storage; D1, D2
type-9 robot bench menu and object mods on actors; W1 converted FO4 weapons on Starfield animation graphs; E1 renamed
currency in the barter menu and HUD; L2 encounter-zone fold keeps FO4's level locking.

### Quests, dialogue and voice ([notes](engine-mechanics-notes/quests-dialogue-voice.md), 13 mechanisms, about 60 questions)

Findings (labels and sources in the notes):
- **Voice rights are the biggest risk, and it is legal, not technical.** Capital Wasteland (Fallout 3 in FO4) dropped
  letting players extract Fallout 3's voices as "untenable": Bethesda licenses voice acting rather than owning it, so it
  cannot grant reuse (PCGamesN). Tale of Two Wastelands converts the player's own install and has lasted years, but our
  launcher reusing FO4 voices inside Starfield is the Capital Wasteland case. (supported hypothesis, press report)
- AI voice: Bethesda Creations bans generative-AI content (as reported); Nexus allows it with AI tags and removes it on a
  rights holder's complaint; voice actors object publicly. Any AI voice route rules out a Creations release.
- Lip sync runs only through the Starfield CK (Audio, Run FaceFX Compiler); traps are spaces in paths and voice type to
  body type matching. A Japanese lip-sync mod regenerated a whole voice set this way, so our scale is plausible.
  Skyrim's and FO4's CKs take `-GenerateLips:<plugin>`; trying it on Starfield's CK is the cheapest probe.
- Voice encoding: Wwise 2021.1.14.8108 and vgmstream per guides; Starfield Silent Voice (SFSE) exists because unvoiced
  mod lines need silent files, which matters for shipping text before voice.
- Quests: a quest alias that fails to fill can stop a quest without a log line; `bEnableStoryManagerLogging`,
  `bEnableConditionLogging` and `bEnablePlanetContentManagerLogging` are the debugging switches.
- Faction ties: drive FO4 faction standing from quest stages on our own FACTs and quest faction keywords; companion
  reactions on AFFE fields.
- Scale: Tale of Two Wastelands takes about 40 minutes to install and writes about 17 GB (comparison point).

Key questions: A1 do we ask Bethesda about reusing FO4 voices (owner, before release); A2 AI voice policy and the
Creations release; L1, L2 headless lip generation and time per 1,000 lines; V1 Codsworth's Wwise 2026 encoding heard
in game; V2 voice path rule for our master; V5, D6 silent files for text-first lines; Q1 external aliases across
quests; Q3 our own quest-type heading in the Missions menu; S1 why `OnStageSet` and stage fragments did not fire; R1
our own Story Manager branch; R3 does the Planet Content Manager run in our world; D1 topic line order; D2 FO4's four
slots in the choice list; D3 short prompt or full player line for a silent player; T1 localized strings files; X1, X2
DLC line totals and first-run time with resume.

### Companions, AI, factions and combat ([notes](engine-mechanics-notes/companions-ai-factions-combat.md), 10 mechanisms, about 65 questions)

Findings (labels and sources in the notes):
- **Why Preston turned hostile:** in both engines a neutral NPC turns hostile on the first hit from the player; friends
  and allies get a hit allowance (Skyrim's documented defaults: a friend tolerates 3 hits in combat, an ally ignores
  hits in combat; assumed, not confirmed, for Starfield). Likely cheap fix: a Friend or Ally relation to the player's
  faction for companions and friendly FO4 groups, not `IgnoreFriendlyHits`. One in-game test. (supported hypothesis)
- **Command mode:** the Command NPCs author says Starfield's own command feature was cut and rebuilt it in the CK
  without SFSE (an activation prompt plus a command state; only three extra options per NPC). With `SetCommandState`
  still declared, a faithful FO4 command mode looks possible without SFSE. (supported hypothesis)
- Starfield's Join / Leave / Wait follower lines stay locked until MQ101 is done or stopped; our new game skips the
  intro, so we build our own follower framework.
- Starfield's follow behaviour comes from a quest alias (Dogmetal recruits via quest D773, `ActiveFollowers` alias and
  `setplayerteammate 1`), consistent with our tests (`SetPlayerTeammate` alone failed on a citizen, passed on a calm
  probe).
- Follower frameworks conflict with each other and softlock on removal (AFT Plus, Everyone's Best Friend, Swiftly Order
  Squad, Liga); extra aliases on settlers wiped their names; Starfield's story-gate timers pause while a companion is
  dismissed. So: one framework of our own, never edit Starfield's follower quest, "new game only" in release notes.
- Stealth: "FO4 Gameplay Setting Merge" already applies FO4 sneak and detection settings in Starfield, so the names
  largely carry; a settings diff of both esm files is the route to FO4's stealth feel.
- Precedents: no shipped CE1-to-CE2 conversion; Fallout London warns on QA capacity (about 20 testers against FO4's 150)
  and on pinning one game build.
- Licences: Command NPCs, GRiNDTerra and the NPC template forbid conversion; Swiftly Order Squad is CC BY-SA 4.0.

Key questions: F2 can our own alias framework make an FO4 companion follow; A1, A2 do our AFFE records work without
Starfield's companion quests and `COM_` globals; H2 do Friend and Ally relations give hit allowances in CE2; C1 does
`SetCommandState` work; S1, S2 what herd and formation blocks do in game; S4 is an arrest in Diamond City wanted (needs
a guard quest and new voiced lines, owner); B1, B4 combat style conversion and Starfield's level and difficulty
scaling against FO4's balance; R2 do we ship an SFSE plugin at all.

### Leads from the framework thread's first wave (findings/, leads to verify)

From [findings/fallout-systems-precedents.md](findings/fallout-systems-precedents.md) and
[findings/testing-qa.md](findings/testing-qa.md); folded into the reference pages vats, power-armor, radio, UI and
perks on 2026-10-19:
- Pip-Boy shape: Starcade OS opens an HTML menu from an inventory item through OSF UI, with Papyrus glue and a native
  state file (GPL-3 plugin). FO4's PIP-Pad shows replacing the Pip-Boy conflicts with every other Pip-Boy mod.
- Radio outside Wwise: three SFSE players (Galactic Radio, Star Radio Player with placed, distance-faded radios built in
  the outpost menu, Starfield Radio on Carbon UI).
- Time: ship targeting mode runs at 0.65x; `setglobaltimemultiplier` works from console hotkeys; a perk can slow time
  while hovering (Lively's Enhanced Skills) without SFSE.
- SPECIAL: the community SPECIAL mod fell back to terminal menus because Papyrus cannot feed Starfield's menus.
- Power armor: no furniture-based power armor exists; the 2024 mech used a polymorph-style race swap (credit differs
  between sources, unresolved). OSF Animation plays synced `.af`/glTF scenes with a Papyrus API: a candidate for enter
  and exit clips.
- Survival: vanilla Sustenance and Gameplay Options exist; needs mods replace Sustenance and must have it off.
- Testing: Starfield's `Debug` script declares `AutomatedTestLogProgress`, `PlayerMoveToAndWait`, `CenterOnCellAndWait`,
  `StartScriptProfiling` and more; the Starfield wiki says the script is flagged debug-only, so which work in retail is
  **unresolved** (one PC probe from a test quest).

New questions from these leads:

| # | question | why it matters | cheapest way to answer | phase |
|---|---|---|---|---|
| L1 | Which `Debug` test functions work in the retail build? | each one replaces a console step in the test runner | one probe quest calling each and logging | P2 |
| L2 | Radio: Wwise events or our own SFSE player? | world radios with distance fade exist outside Wwise; Wwise needs the user's install | try Star Radio Player's pattern against one FO4 station offline | P4 |
| L3 | Pip-Boy: build on OSF UI, Carbon UI or our own SFSE menu? | single-maintainer frameworks and build pinning are the risk | read both APIs, check update history across 1.15 and 1.16 | P4 |
| L4 | Do we coordinate with the StarUI/FallUI, OSF and SPECIAL authors? | users run their mods next to ours | owner decides (outreach is owner-only) | P5 |
| L5 | Should our HUD changes overlay rather than replace `hudmenu.gfx`? | compatibility with StarUI HUD and Venworks | design decision after L3 | P4 |

### Animation, audio and physics ([notes](engine-mechanics-notes/animation-audio-physics.md), 13 groups, 22 key)

Findings (labels and sources in the notes):
- Animation tools exist but are early: Animation IO (Blender) reads and writes `.af` and `.rig` with the CALUMI library
  our door work uses; CALUMI Motion (LGPL-3) and Starfield-Behavior-Editor (GPL-3, WIP) open and save `.agx` graphs.
  (verified from their pages; not run)
- Adding new clips, not just replacing vanilla ones, is disputed: one user reports a CK launch argument generated
  subgraph data and a custom weapon clip played, another says it does not work. (unresolved)
- **No public recipe for new sounds:** every Starfield sound mod replaces an existing `.wem` by id; a forum thread says
  the CK does not recognise new soundbanks. Some vanilla music slots need PCM, which supports writing PCM `.wem`
  without Wwise; the CK's `Starfield.wproj` pins Wwise 2021.1.14.8108.
- No Starfield radio mod uses the game's own radio; all are SFSE players outside Wwise. The FO4 radio recipe is
  recorded in the notes, including the restart timer against the "radio silence" bug.
- SFSE scene frameworks as fallback: NAF (GPL-3) cannot replace vanilla clips and stops on reload; OSF plays synced
  multi-actor clips with Wwise audio and ships a library of vanilla clips for 27 creature species.
- Physics: editing death `.afx` frames sends actors straight to ragdoll, so `.afx` controls the hand-off; a Blender
  extension claims Havok constraint authoring; official Havok tools cover cloth only.
- Precedents: reusing a vanilla creature skeleton works but limps (CP's Menagerie); Skyblivion found creature animation
  the slowest specialist lane, and thin clip sets look wrong in a richer engine.
- Licences: Animation IO, CALUMI Motion's Nexus release and the Rig Collection forbid redistribution or conversion, so
  the launcher cannot bundle them.

Key questions: B1 can a plugin add a new idle; B2 can a plugin ship its own `.agx` graph; C1 to C4 creature stand-ins,
own rigs, Codsworth; H1 does a `.wem` we write ourselves play; H2 can we make new events and banks; H3 how OSF plays its
own Wwise audio; J1 does the engine radio work without FO4's transmitter and talking-activator records; J2 fall back to
an SFSE player; L1 decode one vanilla Havok constraint; M1, M2 which tools the launcher may call or bundle.

### Wave 2 rechecks ([notes](engine-mechanics-notes/wave2-rechecks.md))

Changed questions (labels and sources in the notes):
- **UI 1.2 (key), own engine menu: partly yes** (supported hypothesis). SFSE alone cannot register a menu (its API only
  offers movie-load callbacks; verified, PluginAPI.h); CommonLibSF wraps the game's `UI::RegisterMenu` (verified); OSF UI
  registers a real engine menu with no Flash movie to handle input for its HTML overlay (verified, source). PULSAR's
  native Flash menu on 1.16.244 hit crashes and stale CommonLibSF addresses. Whether our own SWF draws in such a menu is
  unresolved. New option for UI 1.1: an HTML overlay paired with a movie-less engine menu.
- **Tools 3.5: Mutagen types Starfield's FACT fully** (relations, crime values, prisons, vendors, herd, formation
  radius; verified schema), so the factions reuse can be written; one write-and-load test remains. Tools 3.1: newest
  Starfield package 0.55.0-alpha.75 (2026-10-19); we pin alpha.67.
- **New constraint, companions H5:** Mutagen's Starfield code has no RELA group, so FO4's 64 relationship records need
  raw record writing or a Mutagen contribution.
- Address Library for SFSE supports 1.16.244 (version 22, 13 June 2026; version 21 for 1.16.242, 15 May 2026): input
  for the patch-delay table (tools 5.3).
- CK command line (tools 6.1, voice L1): still no documented Starfield switch. FO4's CK has
  `-GenerateAnimInfo:<esm> <data> <out>` (verified), likely the launch argument behind the custom-clip report
  (animation B1, supported hypothesis). PC check: `strings` on CreationKit.exe for GenerateLips, GenerateAnimInfo and
  compile switches (read-only).
- Companions A3 (key) sourced: reactions +50 / +25 / 0 / -15 / -35; 8 story gates every 100 points, 30 minutes then 1
  hour real time apart. A8: Starfield already dismisses a companion on civilian assault and angers them on a kill
  (overlaps FO4's rules). C1 (key): the command test must call `SetCanDoCommand` first or use a teammate; FO4's
  `OnCommandModeGiveCommand` has 13 command types (Workshop Assign, Ride Vertibird, Enter Power Armor feed C5). H2:
  Skyrim's Friend and Ally effect sourced.
- Licences: OSF Animation GPL-3.0 with a modding exception; Animation IO's Blender manifest says MIT while its Nexus page
  sets custom permissions; CALUMI.Animation listed as LGPL-3.0 (our GPL-3 launcher can call it, if right).
- Animation H3 (key) in outline: OSF Animation plays loose `.wem` and `.wav` through the game's Wwise with its own
  subtitles via SFSE; positional audio falls back to non-3D on 1.16.244; it creates no events or banks, so H2 stays open.
- **New precedent:** BACUP (github.com/Bryant-21/bacup, GPL-3) converts records and assets between Creation Engine
  games, most complete for Fallout 76 to Fallout 4, with a Starfield schema but no pair targeting Starfield. Question
  T-new: reuse its FO4 schema and asset converters, or talk to its author (owner, outreach).

### PC check: Creation Kit command-line switches (job 18, verified, read-only string scan at 9abbb0f)

- **Starfield CK** names `-CompileFaceFXAnims`, `-GenerateAnimInfo:(ESM) (Data) (Output)`, `-CompileMaterials`,
  `-CompileTextExport`, `-GenerateSEQ`, `-GenerateWarnings`, `-GenerateCellAndRefCounts`, mesh LOD reports, icon and
  ship blueprint generators. **No `-GenerateLips`** (FO4's CK has it, plus `-GenerateSingleLip`). Lip sync goes through
  FaceFX: the CK runs `Tools\LipGenerator\LipGenerator.exe` (`sLipGeneratorPath`) as a command-line tool and reports its
  exit code. FO4's CK calls `LipGenerator "(wav)" "(text)" -Language:(lang) -GestureExaggeration:(f)`.
- No script-compile switch in either CK; compiling is `PapyrusCompiler.exe`, which we already run headless.
- What it changes: decision 10 (headless CK steps) now has two concrete probes. (a) Run Starfield's
  `LipGenerator.exe` directly on one WAV plus text, FO4-style arguments first (quests L1, X5). (b) Run
  `-CompileFaceFXAnims` and `-GenerateAnimInfo:` on a test plugin (animation B1: new clips need anim info, which this
  switch likely generates). Both are PC runs that write only to a scratch folder.
- **Job 19 (verified): Starfield's LipGenerator.exe runs headless.** Usage: `LipGenerator wav text actor.facefx
  actoranalysis.facefx [-Language:] [-OutputFileName:] [-AnimationGroupName:]`, eight languages, no window. So lip
  generation can run unattended from the launcher. New key question (quests L3): where are the actor and actor
  analysis `.facefx` files for each face rig, and which fits each converted FO4 voice type? Next check: list `.facefx`
  names in Starfield's archives, then generate one Codsworth line and hear it in game.
- **Jobs 20 and 21 (verified):** the full list of CK usage strings adds, for Starfield, `-ExportFaceGenData`
  (face bake from the command line), `-RunValidationSuite:(ESM) (suite)[:tests]`, `-ExportESM`, `-DepersistRefs`,
  `-CheckInPlugin`, `-ImportScalingData` and `-MockWorldSpaceLOD:(ESM) (worldspaces)` (Starfield only). FO4's CK adds
  `-GeneratePreCombined`, `-GeneratePreVisData`, `-ExportDismemberData`, `-MapMaker`, `-UpdateModelData`. Starfield's
  archives hold **no** `.facefx` actor files, only 278,582 per-line `.ffxanim`; so LipGenerator's actor inputs must
  come from the CK's tools or source data (quests L3 stays key; next PC check searches the Starfield and CK folders and
  ContentResources.zip). New questions: T-new2 can `-ExportFaceGenData` bake converted NPC faces headless (people and
  story); T-new3 what validation suites `-RunValidationSuite` offers (tooling and testing).
- **Job 22 (verified):** the actor files ship with the CK in `Starfield\Tools\FaceFX\` (StarfieldHumanMale,
  StarfieldHumanFemale, GenesisDefault, GenesisDeadHead `.facefx`). So every LipGenerator input is on a player's PC
  once the free CK is installed; next is one trial line from a synthetic WAV into a scratch folder.
- **Job 24 (verified): unattended lip generation works.** A Windows text-to-speech WAV plus its text through
  LipGenerator with the CK's `StarfieldHumanMale` and `GenesisDefault` actors wrote an `.ffxanim` in seconds with no
  window (header `FACE`, "ZeniMax Media", `EFG`). Decision 10 is half answered: lip sync can run inside the launcher on
  the player's PC. Open: compare with a vanilla `.ffxanim`, play one in game, pick actors for robots and creatures.
