# Companions, AI, factions and combat: research findings and question framework

Area notes for the next-phase framework. Author: Claude (cloud research agent), 2026-10-19. Builds on
`/mnt/project-files/research/engine-mechanics/` pages companions.md, ai-packages-and-schedules.md,
factions-crime-relationships.md, combat-detection-stealth.md and starfield-systems-to-reuse.md, and does not repeat
their record layouts. Labels: **verified** (read on the source page or in a file), **supported hypothesis** (evidence,
not confirmed), **unresolved**.

Pages that could not be read during this pass (the fetch proxy answered HTTP 429, rate limited): Nexus "PEAK - Enemy
Combat AI" (starfield/mods/7120), starfieldwiki Affinity, ck.uesp.net Relationship, falloutck.uesp.net
SetCommandState, the Starfield Portal articles on faction warfare and improved follower behaviour, and Nether's
Follower Framework (Skyrim). Claims that would rest on them are marked unresolved below.

## What the community and tools offer today

Companions and followers in Starfield

- **No public Starfield companion framework exists that a modder builds on the way Skyrim and FO4 modders build on
  AFT or NFF.** What exists are multi-follower and command mods that extend Bethesda's own follower quest, each with its
  own scripts. **supported hypothesis** (searches of Nexus found only the mods below; absence is not proof).
- **Swiftly Order Squad** (wankingSkeever, v0.1.5, 2026-04-18, CC BY-SA 4.0): unlimited followers, group commands
  through a communicator item that counts as a weapon (so it can be hotkeyed), ESM built with xEdit. Only one
  romanceable Constellation companion can be active "because the vanilla companion quest commentary assumes just one";
  the author will not allow recruiting arbitrary NPCs because "most voice types lack follower dialog"; changelog fixed a
  script race "on systems where the script runs too quickly". **verified**
  https://www.nexusmods.com/starfield/mods/6439
- **Liga of Followers** (Iggdrasil7, v1.04): per-follower and group commands (follow, stay, sneak, guard, relax, camp,
  distance), terminal control, commands limited to 50 m and one cell, own AI packages "to stop followers getting stuck
  in dialogue". Known issues: followers break (not walking, silent, stuck, cannot stand); a three-level "Help" reset whose
  last level "can permanently break quests"; behaviour "depends heavily on engine load"; the game can block dismissal
  during a companion's quest; starts only after the player reaches an exterior to avoid the early main quest.
  **verified** https://www.nexusmods.com/starfield/mods/12598?tab=docs
- **Command NPCs - Order your followers and allies** (xtcrefugee, v1.5/1.51, 2026-04-15; no modification or conversion
  permitted): built in the Creation Kit, cleaned in xEdit; a Command prompt beside Talk (reload key) puts the NPC in a
  command state until released. The page states **"the game's own command feature was cut"** and that leftover CANCEL
  and TRADE options sometimes appear; eligibility is `ConstellationFaction` or `AvailableCrewFaction`; one NPC at a
  time; fast travel or leaving an interior releases them; followers refuse owned furniture and stealing; a looted
  unowned item shows as stolen; pathing fails between ship habs and on some stairs; Sarah and Barrett have voiced
  command lines. Tested on Starfield 1.16.236.0. **verified** (as the author states it)
  https://www.nexusmods.com/starfield/mods/10533 ; summary also at
  https://starfieldportal.com/article/xbox-mod-highlight-command-npcs-mod
- **Dogmetal - Robotic K9 Companions** (OCD Insomniac, v3.0, 2023-11): a Dogmeat-like robot dog built "from the ground
  up in xEdit", no Papyrus. Spawned and recruited by console: `player.placeatme`, `ssq D773`,
  `forcerefintoalias ActiveFollowers`, `setplayerteammate 1`; essential; outside the crew and companion lists.
  **verified** https://www.nexusmods.com/starfield/mods/5190 . Inference: Starfield's follower quest is FormID
  `0000D773` with an alias `ActiveFollowers` that supplies follow behaviour. **supported hypothesis** (one mod's
  console recipe; check in Starfield.esm).
- **SKK Global Utility Script (Legacy)** (SKKmods, 006): follower helpers by `cgf`; names `PlayerAllyFaction`,
  `PlayerFriendFaction`, `PlayerEnemyFaction`, `PlayerFaction`, the three crew factions, and
  `TeammateDontUseAmmoKeyword`; **companion Join / Leave / Wait dialogue stays locked until MQ101 (00003448) is
  completed or stopped**. Author says it is outdated and points to SKK Stalkers and Followers. **verified**
  https://www.nexusmods.com/starfield/mods/3622
- **Aflin and DJLegend's Starfield NPC Template** (2026-07): a design document for voiced followers (biography,
  event-driven dialogue, conversation, useful conditions, affinity events); says there is "no public Creation Kit wiki
  yet" and that Starfield's follower implementation differs from Skyrim's. **verified**
  https://www.nexusmods.com/starfield/mods/17694
- **Relationship Progression Control** article (Aurelianis): first talk at 100 affinity, then 200 to 800; story gate
  timers 30 min then 1 h real time; **timers run only while the companion is the active follower and pause on
  dismissal**; zero timers cause back-to-back talks because talks themselves give affinity. **verified**
  https://www.nexusmods.com/starfield/articles/412
- **Upgraded Companions** (Aurelianis, v1.5): quest headers flagged Partial Form; some quest changes done by script, not
  by quest header edits, to cut load-order conflicts; removed the Constant flag on globals it changes; compressed sound
  in BA2 did not play, so it ships an uncompressed BA2; new and changed affinity events for Andreja. **verified**
  https://www.nexusmods.com/starfield/mods/12030
- **Visible Companion Affinity** (CDante): shows affinity percentages and the last ten events; implementation not
  described. **verified** (article) https://www.pcgamesn.com/starfield/companion-affinity-mod
- **Grugnar's Companion Makeover Compilation** (v1.0): appearance, gear and skill overhaul of crew; a data-only
  example. **verified** https://www.nexusmods.com/starfield/mods/11353

Fallout 4 follower frameworks (lessons)

- **Amazing Follower Tweaks Plus** (Sranger, after Dheuster's AFT; v4.39, 2026-09-12): modifies `followersscript.pex`
  and the vanilla follower quest and **warns on load if something overrides them**; cap 10 plus Dogmeat; needs F4SE and
  Garden of Eden Papyrus Script Extender (dynamic names, multi-companion scene audio); Command Mode, All Attack and All
  Retreat on hotkeys. Lessons it records: the CK wipes Partial Form flags on save (re-add them); adding aliases to
  generic NPCs (automatrons, settlers) wiped their names and workshop recognition; gear changes wipe magic effects on
  NPCs; `RemoveAllItems` can crash; looting pulls non-playable items; dismissing a companion in the vertibird during
  RR303 makes them hostile; uninstalling complex scripted follower mods is "too variable", AFT packages can softlock;
  incompatible with Unlimited Companion Framework, Everyone's Best Friend, Liga of my companions and Dogmeat Follow
  Behind. **verified** https://www.nexusmods.com/fallout4/mods/59699 and
  https://www.nexusmods.com/fallout4/mods/103072
- **Everyone's Best Friend** (Valdacil, v3.0.0, 2017): Dogmeat plus a companion by editing two checks in
  `FollowersScript.pex` and some recruitment dialogue; a Bethesda script comment shows the two-slot design was dropped
  late. Conflicts with anything editing that script or that dialogue. **verified**
  https://www.nexusmods.com/fallout4/mods/13459 ; https://www.nexusmods.com/fallout4/mods/22911?tab=docs

Hostility, combat, stealth

- **Simple Offence Suppression SFSE** (powerofthree, v2.0.0, 2025-05-28, needs SFSE and Address Library, game
  1.15.214+): "Neutral NPCs and spaceships normally turn hostile immediately when hit"; friends and allies get hit
  allowances; the plugin treats neutrals as friends or allies only for player hits; ini setting
  `iFriendHitCombatAllowed`; source on GitHub. **verified** https://www.nexusmods.com/starfield/mods/4456/ . The F4SE
  twin (v1.2.1) documents the same rule for FO4, source `powerof3/SimpleOffenceSuppressionF4SE`. **verified**
  https://www.nexusmods.com/fallout4/mods/75292
- **The friend and ally hit rules** (Skyrim CK, same lineage): neutral = no allowance; friend tolerates
  `iFriendHitCombatAllowed` 3 hits in combat and `iFriendHitNonCombatAllowed` 0 out of combat; ally tolerates
  `iAllyHitCombatAllowed` 1000 (infinite) and `iAllyHitNonCombatAllowed` 3; timer `fFriendHitTimer` 10.0,
  `fFriendMinimumLastHitTime` 0.5; condition `GetFriendHit`. **verified** for Skyrim
  https://ck.uesp.net/wiki/Friendly_Fire ; that the same settings drive FO4 and Starfield is a **supported
  hypothesis** (both Offence Suppression pages name `iFriendHitCombatAllowed`).
- **FO4 Gameplay Setting Merge** (bdar, v1.1, Starfield): applies FO4 game settings in Starfield by `setgs`:
  `fSneakEquippedWeightBase`, `fSneakLightMult`, `fSneakLightExteriorMult`, `fSneakLightMoveMult`,
  `fSneakLightRunMult`, `fSneakPerceptionSkillMin`, `iSoundLevelQuiet` 25, `iSoundLevelNormal` 50,
  `fDetectionVisualDistanceMult{Exterior,Interior}`, view-angle settings, `fCombatStealthPoint*MaxValue`,
  `fCombatDetectionLostRemoveDistance`, `fConfidence{Brave,Average,Cautious}`, `fFleeIsSafeTimer`. The author says some
  may be deprecated. **verified** (as listed) https://www.nexusmods.com/starfield/mods/6528 . This is the closest
  precedent to "make Starfield detect like FO4".
- **Tweak - Nearly Vanilla Stealth** (JaeDL): gives the vanilla Starfield values `fSneakExteriorDistanceMult` 1.25,
  `fSneakLightMult` 1, `fSneakSoundLosMult` 0.4, `fSneakMaxDistance` 60, `fSneakEquippedWeightBase` -4,
  `fDetectionViewCone` 190, and says vanilla let the player get very close to exterior enemies
  (`fHostileActorExteriorDistance`). **verified** (as the author states) https://www.nexusmods.com/starfield/mods/7579
- **Combat overhauls**: Focus (pietro0games, v1.4): vanilla difficulty matters little on foot, vanilla stealth "behaves
  oddly", starlight can be weaker than a spotlight. **verified** https://www.nexusmods.com/starfield/mods/11067 .
  GRiNDTerra (v5): vanilla NPC level relative to the player 0.4x / 0.7x / 1x / 1.25x by difficulty, raises the
  in-combat NPC cap to 125, adds its own combat styles. **verified** https://www.nexusmods.com/starfield/mods/9907 .
  Brutal Starfield (v52): damage GMSTs `fDiffMultHPByPCV*` / `fDiffMultHPToPCV*`; an ini cannot set some values on save
  load; "encounter zone levels lock when a system is first visited". **verified** (author's claims)
  https://www.nexusmods.com/starfield/mods/3049 . None of these pages documents which CSTY fields they change.

## Precedents and lessons

- **No shipped CE1-to-CE2 total conversion found.** "Starwind" (Skywind moving to Starfield's engine) was an April
  Fools article. **verified**
  https://starfieldportal.com/article/the-elder-scrolls-morrowind-remake-shifts-to-starfield-engine . So no one has
  published how FO4 companions or factions behave on CE2; we are first. **supported hypothesis**
- **Fallout: London** (FO4 total conversion): one canine companion (Churchill), over 100 mostly volunteer voice
  actors, launch crashes and quest problems, about 20 testers against FO4's 150, and the mod pinned to the
  pre-next-gen FO4 build after the April 2024 update. **verified** https://en.wikipedia.org/wiki/Fallout:_London .
  Lessons: plan QA capacity for companion and quest content, and pin to a known game build because SFSE plugins
  (Offence Suppression lists game versions per release) break on updates.
- **Follower frameworks fight each other.** AFT Plus lists four incompatible frameworks; Everyone's Best Friend
  conflicts with any edit to the same script; Swiftly Order Squad and Dogmetal "act a little funny" together.
  **verified** (pages above). Lesson: a converted FO4 game needs **one** framework, ours, that does not edit Starfield's
  follower quest or script, so player-installed Starfield follower mods cannot collide with it.
- **Aliases on shared NPCs have side effects** (AFT Plus: names and workshop links wiped). Our settlers and
  automatrons will carry workshop aliases too. **verified** lesson, applicability **supported hypothesis**.
- **Uninstalling scripted follower systems is unsafe** (AFT Plus, Liga, Everyone's Best Friend all document leftovers
  or softlocks). Lesson for release: our launcher should say "new game only, no removal mid-save" for the companion
  layer. **verified** lesson.
- **Starfield companion progression is timer and follower-state driven** (story gate timers pause when dismissed).
  FO4 has no real-time timers. **verified** (articles/412). Lesson: if we ride on AFFE we must decide whether to use
  Starfield's real-time gates at all.
- **Voice gates follower features**: Swiftly Order Squad refuses generic recruits because generic voices lack follower
  lines. **verified**. FO4's generic settler voices do have some command barks (DIAL Command subtypes exist in FO4,
  per companions.md), so this matters for automatrons and settlers we let follow. **supported hypothesis**
- **Crime flows are dialogue-heavy** (Skyrim custom crime faction: guards need `IsGuardFaction` and
  `GuardDialogueFaction`, a copy of `DialogueCrimeGuards`, linked prison markers, evidence chests; "assigned crime
  faction" silently unsets in the CK). **verified** https://ck.uesp.net/wiki/Creating_a_Custom_Crime_Faction .
  Starfield's arrest flow is a **supported hypothesis** of the same shape; FO4 guards have no arrest lines.

## Possibilities and hard limits in CE2

- **Command mode as FO4 had it is cut from Starfield's player-facing game**; a CK mod rebuilt it with an activation
  prompt and a command state. **supported hypothesis** (Command NPCs author's statement; the PC probe already found
  `SetCommandState` declared in Starfield scripts, companions.md). So a faithful FO4 command mode is possible without
  SFSE, at the cost of an activation-menu slot (only three extra options per NPC show, per Command NPCs).
- **Follow behaviour comes from a quest alias, not from `SetPlayerTeammate` alone.** The project's own tests: N0_follow
  (`SetPlayerTeammate 1` + `EvaluatePackage`) left a vanilla citizen standing for 30 s (FAIL NONAV, npc-navigation.md),
  while N2a on a calm probe passed; Dogmetal adds `forcerefintoalias ActiveFollowers`. **supported hypothesis**
- **Neutral NPCs turn hostile on the first player hit in both engines; friends and allies get allowances.** **verified**
  for the rule as documented (Offence Suppression pages, Skyrim CK). This explains the Preston finding
  (factions-crime-relationships.md): Preston was neutral. Fix in data: Friend or Ally relations to the player's faction
  for friendly FO4 groups and companions, not `IgnoreFriendlyHits`. **supported hypothesis** until tested.
- **Vanilla follower dialogue depends on MQ101.** Starfield's Join / Leave / Wait lines are locked until MQ101 is done
  or stopped. **verified** (SKK page). Our new game skips Starfield's intro, so any reuse of Starfield's follower
  dialogue depends on MQ101's state. Our own framework avoids this. **supported hypothesis**
- **Detection and stealth are tunable by game settings, and the FO4 names largely exist in Starfield.** **supported
  hypothesis** (FO4 Gameplay Setting Merge applies them with `setgs`). Values differ (vanilla `fSneakEquippedWeightBase`
  -4 vs 12 in that mod). A plugin can carry GMST records; Brutal Starfield shows some values do not stick from an ini.
- **Starfield's stealth meter is gated by its Stealth skill**, which we fence out. **unresolved** whether a perk added
  at new game can show the meter (combat-detection-stealth.md lists the check).
- **Friendly-fire allowances are global GMSTs**, so tuning them changes Starfield's own game too while our plugin is
  loaded. **supported hypothesis**
- **Herds, formation groups, faction voices** exist as FACT fields (verified, xEdit); no community page found that
  documents their in-game behaviour. **unresolved**
- **Arrest and prison** exist in Starfield (player guides) and in FACT PRIS; a working arrest needs voiced guard
  dialogue and markers. **supported hypothesis**; behaviour with empty ship and contraband markers **unresolved**.
- **SFSE route for hostility exists** (Offence Suppression patches the hit rule), so a data fix is not the only
  option; it costs an SFSE dependency per game build. **verified**

## Question framework

Phases: **NG** new game (Vault 111 to Sanctuary and Concord), **INT** interiors, **QP** quests and people, **FS**
Fallout systems, **REL** release.

### 1. Follower framework (our own quest, aliases, teammate state)

| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| F1 | What exactly is Starfield's follower quest (FormID D773?), its aliases (`ActiveFollowers`?), the packages and factions those aliases add, and its scripts (`SQ_FollowersScript`)? | Tells us what our own framework must replicate (follow package, teammate flags, factions) and what to stay away from | Dogmetal console recipe (supported); PC probe found `SQ_FollowersScript`, `SQ_CompanionsScript`, `SQ_CrewScript` (verified, companions.md) | offline Mutagen dump of QUST 0000D773 aliases (ALFA flags, alias packages, alias factions, scripts) in Starfield.esm | blocks F2, F3; input to the converter for FO4 `Followers` | NG | key |
| F2 | Can our own framework quest make an FO4 companion follow, fight beside the player and travel through load doors, with no Starfield follower quest involved? | The core decision: own framework vs riding on SQ_Followers | N0_follow FAIL vs N2a PASS in project tests (supported); alias packages are the CE pattern | one CK test quest: an alias with a Follow package and the teammate flag on a converted Codsworth; walk through a load door; in-game test chain | needs F1; blocks every companion | NG | key |
| F3 | Which Starfield factions must a follower carry (PlayerAllyFaction, CurrentFollowerFaction-like, crew factions) for combat assistance, the affinity system and AI to treat it as a follower, and which pull in crew/ship hooks? | The fence: crew factions bring crew and outpost assignment | faction names known from SKK page (verified names); effects unresolved | offline: list factions added by SQ_Followers aliases; in game: add/remove one faction on a test follower and watch crew menu and combat | needs F1 | NG | key |
| F4 | Does `SetPlayerTeammate` in CE2 give the same things as FO4 (shared XP, no theft on pickup, combat assistance, follower carry and trade) and does `TeammateDontUseAmmoKeyword` match FO4's ammo rule? | FO4 companions use infinite ammo by default; inventory handling for trade | keyword name verified (SKK); behaviour unresolved | in-game test with a teammate set by script; check ammo count after a fight | none | NG | |
| F5 | One companion plus Dogmeat (FO4 rule) or more? | Design decision with engine cost: FO4's single-slot design is baked into scripts and scenes (EBF, AFT lessons) | FO4 rule verified by EBF page; Starfield vanilla commentary assumes one (Swiftly Order Squad) | owner decision; then count FO4 scenes that assume one companion alias | blocks F7 and commentary work | QP | key |
| F6 | How do our companions behave across travel the FO4 way (vertibird, elevators, fast travel, interior doors), and does Starfield's follower teleport on fast travel work in our one-planet world? | FO4 `FollowersScript` handles teleport and vertibird events (98 functions, verified); Command NPCs says fast travel releases commanded NPCs | partial | in-game: fast travel with a test follower between two of our map markers; vertibird later | needs F2; vehicles-and-travel.md | NG | |
| F7 | How does the framework handle essential/protected, bleedout and recovery for followers? | FO4 companions bleed out and rise; Dogmetal uses essential | ACBS flags identical (verified, combat page) | CK flag test, one fight | needs F2 | NG | |
| F8 | Does the framework survive save and load, and what happens if the player removes the mod mid-save? | Every FO4 framework mod documents leftovers and softlocks | AFT Plus, Liga, EBF lessons (verified) | save/reload test in the chain; release note "new game only" | REL | REL | |
| F9 | How do settler and automatron aliases coexist with follower aliases without wiping names or workshop links? | AFT Plus hit exactly this | verified lesson in FO4 | defer to workshop phase; one test settler with two aliases | workshop-and-settlements.md | FS | |
| F10 | Does a player-installed Starfield follower mod (Swiftly Order Squad, Liga, Command NPCs) break our companions? | Players will run them | each extends Starfield's follower quest (supported) | one compatibility pass before release with the two most endorsed mods | needs F2 | REL | |

### 2. Affinity on AFFE

| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| A1 | Does an AFFE event of ours move an actor value on our own companion with no Starfield companion quest, `COM_` globals or `CompanionActorScript`? | Decides AFFE reuse vs a scripted FO4-style affinity layer | `AffinityEvent.Send` and `Reset` exist (verified, PC probe job 16); whether events reach an NPC outside Starfield's companion quests is unresolved | one CK test: our AVIF, one AFFE with our NPC and a GLOB, fire it from an INFO; read the AV in console | needs F2 | QP | key |
| A2 | What do NPC_ QSTA / BNAM (affinity quest and branch) and AFFE "Fill Companion Dialogue" require, and do they assume Starfield's `COM_` quest layout? | These fields may hard-wire Starfield's companion quests | fields verified (xEdit); semantics unresolved | offline dump of Sarah's NPC_ and three vanilla AFFE; read `CompanionActorScript.psc` in ContentResources.zip | blocks A1 design | QP | key |
| A3 | Use Starfield's real-time story gate timers, or FO4's pure-affinity tiers (250/500/750/1000) with no timers? | Pacing; Starfield timers pause on dismissal (verified, articles/412) | FO4 tiers supported (Fallout wiki) | owner decision; then globals only | needs A1 | QP | key |
| A4 | How are FO4's 48 in-game hour cooldowns expressed when AFFE cooldowns are in real minutes, given our day length? | Wrong cooldown spams or starves affinity | AFFE cooldown GLOB in minutes (verified); timescale unresolved | arithmetic once weather-time-climate decides timescale | weather-time-climate.md | QP | |
| A5 | Which FO4 reaction events have no trigger in CE2 (lockpicking with bobby pins, power armor entry, chems, workshop building, terminal hacking)? | Each needs a script sender or a Starfield equivalent event | FO4 event keywords listed in companions.md (supported) | grep FO4 CK sources for `CA_Event_` senders; map each to a CE2 event or our script | Papyrus census | FS | |
| A6 | Do Starfield's affinity UI messages ("X liked that") fire for our AFFE and can the text be ours? | Feedback the player expects from FO4 | Visible Companion Affinity shows the UI can be extended (verified article) | same test as A1 | A1 | QP | |
| A7 | How do companion perks at max affinity attach (PERK added by our script) given our perk layer? | FO4 companion perks are a reward the player expects | perk entry points carry by index (verified, README) | after the SPECIAL/perk decision | special-perks-leveling.md | FS | |
| A8 | Companion leave and hatred (FO4 -1000 leaves for good) and the crime-faction "turn hostile on assault" rules: AFFE plus our faction, or script? | Correct FO4 behaviour; avoids a companion turning hostile by a stray hit | FO4 uses `CompanionCrimeFaction_<Name>` (verified for Preston) | design note plus one test with an Ally relation (see H2) | H2 | QP | |

### 3. Command mode and orders

| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| C1 | Does `SetCommandState(true)` on a CE2 follower enter a working command state (target selection, `OnCommandModeGiveCommand` events)? | If yes, FO4 command mode is a UI and script job, no SFSE | declared in Starfield scripts (verified names); Command NPCs says vanilla feature cut but rebuilt in CK (supported) | console `setcommandstate` on a test follower; grep Starfield `Actor.psc` for `OnCommandMode*` events | needs F2 | QP | key |
| C2 | Which FO4 DIAL Command subtypes still fire in CE2 (Call, Follow, Move, Attack, Inspect, Retrieve, Stay, Release, Trade)? | 2,421 Preston lines include these barks; unfired subtypes waste voice work | subtypes verified (xEdit); Sarah and Barrett have voiced command lines (Command NPCs page) | offline: count vanilla Starfield INFOs per Command subtype | dialogue.md | QP | key |
| C3 | Breadth-first fallback: dialogue orders (follow, wait, trade, dismiss) only? | Ships companions earlier | planned in companions.md | owner decision | C1 | QP | |
| C4 | Activation menu space: how many extra prompts can our companions show next to Talk without clashing with other mods? | Command NPCs: three extra options per NPC | verified (author statement) | CK test of an activation entry on our NPC | C1 | QP | |
| C5 | Workshop assignment by command mode (FO4 sends settlers to jobs by command) | Settlement play depends on it | FO4 behaviour; CE2 unresolved | defer to workshop phase | C1, workshop | FS | |

### 4. AI packages, sandboxing and schedules

| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| P1 | Do converted FO4 sandbox packages make our NPCs use converted FO4 furniture and idle markers (sit, sleep, lean, eat)? | Towns look dead otherwise | PACK translates (verified); FURN keyword and marker match unresolved | one Concord settler test (already planned, next-phase note section 9) | furniture conversion, animations | INT | key |
| P2 | Do owned furniture and ownership (XOWN) behave as in FO4 for sandbox `UseOwnedOnly` and for followers? | Command NPCs: followers refuse owned furniture; looting marks items stolen | verified as reported for Starfield | include ownership in the P1 test | factions crime section | INT | |
| P3 | Do our NPCs path through CE2 navmesh with advanced traversals (stairs, ladders) without the follower stalls reported on ships and stairs? | Follower pathing problems are the commonest complaint | Command NPCs and Liga report stalls (verified as reported) | in-game follow test through Red Rocket and a Concord interior | navmesh conversion | INT | key |
| P4 | Does the alias-package-over-actor-package order hold in CE2 for companion scenes and force greets (FO4 `CA_WantsToTalk` talks)? | Affinity talks start by force greet | lineage supported | one test quest (already listed in the AI page) | A1 | QP | |
| P5 | Schedules: does PSDT fire at the right local hour on our planet's day length? | Vendors, sleep and guard shifts | unresolved (AI page) | in-game check after timescale decision | weather-time-climate.md | INT | |
| P6 | How heavy is AI load with many FO4 sandboxers in Diamond City and Goodneighbor? | Liga: follower behaviour depends on engine load; GRiNDTerra raises combat cap to 125 | supported hypothesis | profile one dense cell once Diamond City exists | INT | INT | |
| P7 | Do Starfield-only package hooks (RPLD, RPLI, RDSA package lists, FLEE) need values on our NPCs for sane reactions to the player, gunfire and bodies? | Empty lists may leave NPCs inert | fields verified (xEdit); defaults unresolved | histogram in Starfield.esm; copy from a template | H5 | QP | |

### 5. Factions, relations and hostility

| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| H1 | Which of FO4's 699 factions are Friend or Ally to PlayerFaction, which are neutral, and which friendly NPCs (settlers, Diamond City, companions) end up neutral after conversion? | Neutral actors turn hostile on the first stray hit (verified rule) | Preston turned hostile twice (verified project finding) | offline scan of FO4 FACT XNAM to PlayerFaction and NPC_ faction lists | blocks H2 | NG | key |
| H2 | Does giving friendly FO4 groups an explicit Friend or Ally relation to the player's faction give them the hit allowances in CE2 (3 in combat for Friend, unlimited for Ally)? | Cheapest fix for accidental hostility, no SFSE | Skyrim CK documents the allowances (verified); CE2 values supported | in-game: shoot a Friend and an Ally test NPC; read `GetFriendHit`; dump `iFriendHit*` / `iAllyHit*` GMSTs from Starfield.esm offline | needs H1; unblocks companions | NG | key |
| H3 | Which Starfield faction is the player's, and do FO4 relations re-pointed at it behave as in FO4? | Every hostile and friendly relation points there | listed in the reuse page as an open check | offline lookup plus the H2 test | N3 converter | NG | key |
| H4 | Rule for FO4 aggression-driven hostility: write Enemy relations to the player for every Very Aggressive group without one, or keep FO4 aggression and add RDSA radii? | Raiders, creatures, Gunners and so on | raider conversion verified the difference | offline count of affected factions; one test with each option | combat C-section | NG | key |
| H5 | Do RELA records load and drive `GetRelationshipRank` and friend/ally status in CE2? | FO4 uses 64 RELA; in Skyrim relationship rank can make an NPC a friend or ally of the player (lineage, ck.uesp Relationship page not read) | definition present in xEdit SF1 (verified) | one plugin with a RELA, console check | none | QP | |
| H6 | How do companion crime factions (`CompanionCrimeFaction_<Name>`) map: our own faction per companion, or the AFFE layer only? | Companion reaction to assault and murder | supported hypothesis | read FO4 CK sources for the crime hostility script on Preston | A8 | QP | |
| H7 | Do Starfield factions ever touch our actors (e.g. ecliptic, spacers spawned by Starfield's own radiant systems landing in our worldspace)? | The fence | unresolved | one long idle test in our worldspace, log spawns | world fence | NG | |

### 6. Starfield faction features to reuse (herds, formations, faction voice, arrest and prison)

| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| S1 | What does a FACT Herd block do in game (grouping, following a leader, idle chatter) and which vanilla factions use it? | Mirelurk, mole rat and raider packs for free | fields and conditions verified (xEdit); behaviour unresolved; no community doc found | offline scan of Starfield.esm FACT with Herd data, then watch one vanilla creature group in game | creature races | FS | key |
| S2 | What does Create Group with formation radius plus NPC_ HEFA do: real formation movement on patrol? | Brotherhood squads, Minutemen patrols | fields verified; behaviour unresolved | offline scan for vanilla users (UC marines?), then one patrol test | patrol packages | QP | key |
| S3 | Does FACT VTCK faction voice give members barks without a per-NPC voice type, and does it override or fill gaps? | Thousands of generic FO4 NPCs | field verified; use unresolved | offline: list vanilla FACT with VTCK and their members' own VTCK | dialogue.md | QP | |
| S4 | Is a working arrest in Diamond City possible: Starfield guard dialogue quest, IsGuard-style faction, PRIS with empty ship and contraband markers, our voiced guard lines? | Feature, not port (FO4 crime was off) | Skyrim needs guard factions, a copy of the guard dialogue quest and markers (verified); Starfield structure supported | offline: find Starfield's guard crime dialogue quest and guard factions; owner decides if wanted | owner decision; voice (FO4 guards have no arrest lines) | FS | key |
| S5 | Is the DNAM faction type keyword read by Starfield systems (e.g. reputation UI, bounty UI) that would show our factions? | Avoid our factions appearing in Starfield UI by accident | field verified; use unresolved | offline: list values in Starfield.esm; grep scripts for faction type keywords | fence | REL | |
| S6 | Can the bounty HUD or crime UI show our town factions correctly without Starfield crime factions? | Feature quality if S4 goes ahead | unresolved | in-game test once S4 is decided | S4 | FS | |

### 7. Crime, ownership and theft (FO4's live subset)

| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| K1 | Does Track Crime plus Attack On Sight on our town faction reproduce FO4 behaviour (Diamond City turns hostile on murder) with no bounty or arrest? | FO4's only live crime | fields identical (verified) | in-game: kill a test NPC in a test town faction | H2 | QP | key |
| K2 | Does any global Starfield crime system (contraband scan, guard greeting about bounty) run in our worldspace without Starfield factions? | The fence | unresolved | walk past a guard with a stolen item; land nowhere (no ship) | fence | NG | key |
| K3 | Does theft from owned containers and pickpocketing work with our XOWN owners and report to our faction only? | Economy and companion reactions (FO4 companions dislike stealing) | XOWN identical (verified); companion reaction needs A5 | in-game test in a Concord interior with an owner | A5 | INT | |
| K4 | Does Starfield's Morality AIDT and witness logic make our NPCs report crimes FO4 NPCs ignored? | Unexpected hostility | Morality enum identical (verified) | same test as K1 with a witness | K1 | QP | |

### 8. Combat AI and combat styles

| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| B1 | Convert all 112 FO4 CSTY field by field, or map each FO4 actor class to the nearest Starfield style (csSpacer_Assault and so on)? | Effort vs feel; the raider already rides csSpacer_Assault | layouts verified; the cheap-first plan exists | convert three FO4 styles and A/B one fight each against the Starfield stand-in | creature combat | QP | key |
| B2 | How do Starfield-only CSTY fields (suppression sensitivity, group cohesion, attack from cover until suppressed, retreat) change FO4 enemies, and what defaults reproduce FO4? | Raiders that suppress and retreat feel un-FO4 | fields verified; behaviour unresolved | dump three Starfield styles; set FO4-like defaults; one fight | B1 | QP | |
| B3 | Do FO4 aggro radii map well to RDSA entries (Warn, Warn and Attack, Attack), including warning barks? | FO4 Gunners and turrets warn before shooting | AIDT and RDSA verified | converter rule plus one test of a warning actor | H4 | QP | key |
| B4 | Do CE2 level-scaling and difficulty multipliers distort FO4 encounter balance (NPC level 0.4x to 1.25x of player; damage multipliers by difficulty)? | Balance of the whole Commonwealth | GRiNDTerra and Brutal Starfield name the settings (verified as stated) | offline dump of `fDiffMult*` and level-mult GMSTs in both games; diff | leveled lists, encounter zones | FS | key |
| B5 | Do encounter levels lock on first visit in CE2 (Brutal Starfield's claim) and does that hold for LCTN-based levels in our one worldspace? | FO4 encounter zones lock per zone on first visit too; behaviour must match | supported hypothesis (one mod author) | in-game: visit a test location, level up, revisit | leveled-lists page | FS | |
| B6 | Creature combat: what does each FO4 creature need from a Starfield race (attack data, behaviour graph) until FO4 clips arrive? | Deathclaws, mirelurks, robots | stand-ins planned | defer to actors track | animations | FS | |
| B7 | Can legendary mutation (heal and power up at low health) run on Starfield's legendary system (LGDI, ranks) or must it be script? | FO4 signature feature | LTPT/LTPC verified both | read FO4 CK sources for legendary scripts | items converter | FS | |
| B8 | Companion combat: do FO4 companion combat styles (`csPreston`) and "follower defends player" behave, and do companions use stimpaks on the player (FO4 behaviour)? | Companion usefulness | CSTY verified; heal behaviour unresolved | one fight with Preston as follower | F2 | QP | |

### 9. Detection and stealth

| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| D1 | Which FO4 detection and sneak GMSTs exist in Starfield.esm under the same names, and with what values? | Cheapest route to FO4 stealth feel is GMST records in our plugin | FO4 Gameplay Setting Merge applies them (supported); vanilla Starfield values from one mod author | offline: list all `fSneak*`, `fDetection*`, `iSoundLevel*`, `fCombatStealth*` GMSTs in both esm files; diff | none | FS | key |
| D2 | Does Starfield show a stealth meter without its Stealth skill, and can a perk at new game turn it on? | FO4 always shows Hidden / Caution / Danger | unresolved (combat page) | in-game: fresh character sneaks; then add the skill's perk by console | fence on skills | NG | key |
| D3 | Do GMST overrides from our plugin change Starfield's own game when both load (global effect), and is that acceptable? | Players who mix in Starfield content | supported hypothesis | owner decision; document in release notes | D1 | REL | |
| D4 | Does light level in our converted interiors (which already read dark) make sneaking trivially easy? | Lighting and stealth interact (Focus: starlight weaker than spotlights) | interiors read dark (project report) | measure `GetLightLevel` in two interiors | lighting track | INT | |
| D5 | Do companions sneak with the player and stop giving the player away (FO4 companions crouch with the player)? | Common FO4 complaint; Liga offers a sneak command | unresolved | in-game with a test follower | F2 | QP | |

### 10. Release, compatibility and licences

| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| R1 | Which community tools may we reuse or study, given licences (Swiftly Order Squad CC BY-SA 4.0; Command NPCs, GRiNDTerra and the NPC template forbid modification or conversion; Offence Suppression has public source)? | GPL-3 code; we may learn from but not copy restricted mods | licences as listed on pages (verified) | keep a licence table in the release checklist; ask authors before any reuse | REL | REL | key |
| R2 | Do we ship an SFSE plugin for hostility or command mode, or keep the companion layer data and Papyrus only? | Each SFSE plugin breaks on game updates (version lists on Offence Suppression) | SFSE allowed by settled decision | decide after H2 and C1 results | H2, C1 | REL | key |
| R3 | Which Starfield game build do we pin to, as Fallout London pinned FO4? | Script and SFSE stability | Fallout London precedent (verified) | owner decision at release | R2 | REL | |
| R4 | QA capacity for companion and quest content (Fallout London: 20 testers vs 150) | Companions are the most scripted, most voiced content | precedent verified | plan the test chain coverage per companion | test automation | REL | |

## Sources

Starfield mods and articles (all read 2026-10-19 unless noted)
- https://www.nexusmods.com/starfield/mods/6439 (Swiftly Order Squad)
- https://www.nexusmods.com/starfield/mods/12598?tab=docs (Liga of Followers)
- https://www.nexusmods.com/starfield/mods/10533 (Command NPCs)
- https://starfieldportal.com/article/xbox-mod-highlight-command-npcs-mod
- https://www.nexusmods.com/starfield/mods/5190 (Dogmetal)
- https://www.nexusmods.com/starfield/mods/3622 (SKK Global Utility Script)
- https://www.nexusmods.com/starfield/mods/17694 (NPC Template)
- https://www.nexusmods.com/starfield/articles/412 (Relationship Progression Control article)
- https://www.nexusmods.com/starfield/mods/12030 (Upgraded Companions)
- https://www.nexusmods.com/starfield/mods/11353 (Grugnar's Companion Makeover)
- https://www.nexusmods.com/starfield/mods/12839 (SKK Elite Command; no hostility detail)
- https://www.pcgamesn.com/starfield/companion-affinity-mod (Visible Companion Affinity)
- https://www.nexusmods.com/starfield/mods/4456/ (Simple Offence Suppression SFSE)
- https://www.nexusmods.com/starfield/mods/6528 (FO4 Gameplay Setting Merge)
- https://www.nexusmods.com/starfield/mods/7579 (Tweak - Nearly Vanilla Stealth)
- https://www.nexusmods.com/starfield/mods/11067 (Focus - Combat Overhaul)
- https://www.nexusmods.com/starfield/mods/9907 (GRiNDTerra Combat Overhaul)
- https://www.nexusmods.com/starfield/mods/3049 (Brutal Starfield)
- https://starfieldportal.com/article/the-elder-scrolls-morrowind-remake-shifts-to-starfield-engine (April Fools)

Fallout 4 and Skyrim
- https://www.nexusmods.com/fallout4/mods/59699 and https://www.nexusmods.com/fallout4/mods/103072 (AFT Plus)
- https://www.nexusmods.com/fallout4/mods/13459 and https://www.nexusmods.com/fallout4/mods/22911?tab=docs
  (Everyone's Best Friend)
- https://www.nexusmods.com/fallout4/mods/75292 (Simple Offence Suppression F4)
- https://ck.uesp.net/wiki/Friendly_Fire
- https://ck.uesp.net/wiki/Creating_a_Custom_Crime_Faction
- https://en.wikipedia.org/wiki/Fallout:_London

Not read (HTTP 429, to retry): https://www.nexusmods.com/starfield/mods/7120 (PEAK),
https://starfieldwiki.net/wiki/Starfield:Affinity, https://ck.uesp.net/wiki/Relationship,
https://falloutck.uesp.net/wiki/SetCommandState_-_Actor,
https://falloutck.uesp.net/wiki/OnCommandModeGiveCommand_-_Actor,
https://starfieldportal.com/article/new-starfield-mod-on-nexus-brings-faction-warfare,
https://starfieldportal.com/article/xbox-mod-highlight-improved-follower-behavior,
https://nexusmods.com/skyrimspecialedition/mods/55653 (Nether's Follower Framework).

Project files
- /mnt/project-files/research/engine-mechanics/ companions.md, ai-packages-and-schedules.md,
  factions-crime-relationships.md, combat-detection-stealth.md, starfield-systems-to-reuse.md
- Repo: docs/actors/npc-navigation.md (N0_follow FAIL NONAV), docs/actors/raider-conversion.md (N2a_follow PASS),
  docs/ai/test-queue.md (`follow_player`, combat reads)
