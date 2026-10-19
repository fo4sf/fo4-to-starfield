# Character systems: research findings and question framework

Area: SPECIAL, perks and the perk chart, XP and leveling, health, limbs and crippling, radiation, chems and addiction,
survival mode, power armor, races, bodies, faces and character creation (including ghouls, super mutants, synths,
creatures and robots). Author: Claude (cloud research agent), 2026-10-19. Builds on
[special-perks-leveling.md](../../engine-mechanics/special-perks-leveling.md),
[health-damage-effects.md](../../engine-mechanics/health-damage-effects.md),
[power-armor.md](../../engine-mechanics/power-armor.md),
[actors-and-npcs.md](../../engine-mechanics/actors-and-npcs.md) and
[saves-and-new-game.md](../../engine-mechanics/saves-and-new-game.md); it does not repeat their record layouts.

Labels: **verified** (read on the source page or in a file), **supported hypothesis** (evidence, not confirmed),
**unresolved**. "Page says" means the Nexus or wiki page was read on 2026-10-19; mod pages are author claims, so the
mod's existence and stated method are verified, its technical claims are supported hypothesis until we read its files.

Two pages could not be read because the fetch proxy rate-limited them (HTTP 429): the Skywind FAQ
(https://tesrskywind.com/faq/) and the Nexus forum thread on restoring FO4 skills
(https://forums.nexusmods.com/topic/3742365-theory-on-restoring-skills-and-the-leveling-system). Nothing below rests on
them; recheck later.

## What the community and tools offer today

### Progression (XP, perk points, skills)
- **Variable Progression Settings** (Chickenlord19, v1.5, April 2026): adds XP multiplier and perk-points-per-level
  options to the Gameplay Options menu using GPOF (Gameplay Option Form) records; a Papyrus script sets the XP game
  settings through `Debug.ExecuteConsole()` (the page names `fXPModBase` and `fXPModMult`) and grants extra perk
  points on level-up; "no SFSE". **verified** (page); the GMST names are **supported hypothesis** until dumped.
  https://www.nexusmods.com/starfield/mods/16279
- **PerkPointsPerLevel** (TheLich, v1.7, updated July 2026): native plugin loaded by SFSE or the Ultimate ASI Loader,
  sets perk points per level from `pppl.ini`, logs a table to level 400; changelog mentions a crash with the
  `Game.AddPerkPoints` console command. **verified** (page). Shows the per-level point grant is reachable from native
  code. https://www.nexusmods.com/starfield/mods/1779
- **A.C.T. Autonomic Challenge Training** (EphemeralSagacity, v1.1, Feb 2025): grants skills automatically from
  challenges; disables manual perk points by INI; extensible through `ACT_FormList` form lists; needs Cassiopeia Papyrus
  Extender and Starfield Engine Fixes (to set `bPapyrusArrayNoLimit=1`). **verified** (page). Precedent for
  "no manual Starfield skill points", which our FO4 player needs. https://www.nexusmods.com/starfield/mods/12911
- **Flat Perk Tree** (Frib, Oct 2023): removes the "points in tree to unlock next tier" rule with an xEdit-made ESM,
  so the tier gate is data, not menu code. **verified** (page says ESM made in xEdit); which field holds the gate is
  **unresolved**. https://www.nexusmods.com/starfield/mods/5538
- **Lively's Enhanced Skills** (Lively, author of FO4's Magnum Opus; Nov 2023): perk overhaul by editing rank entry
  points, conditions and values in an ESM; no SFSE named. **verified** (page). Shows PERK rank blocks are editable
  without breaking the skills menu. https://www.nexusmods.com/starfield/mods/5928
- **Skill ReSpec Terminal** (JonathanOstrus, v1.20, April 2026): refunds skill points with Papyrus and Condition Forms
  (CNDF) to read exact ranks; no SFSE named. **verified** (page). A respec pattern for our SPECIAL/perk respec, if
  wanted. https://www.nexusmods.com/starfield/mods/6484

### UI and script frameworks (for a perk chart, SPECIAL screen, PA HUD)
- **Carbon UI** (Squeetsquib / CarbonNode, v0.11.0, Oct 2026, targets Starfield 1.16.244): SFSE plugin that renders
  HTML/CSS/JS menus with Ultralight over the D3D12 frame; C API for other SFSE plugins. The Nexus page says GPL-3.0+
  with an Ultralight linking exception; the GitHub README calls it source-available with no public redistribution of
  modified versions, a port of Skyrim's PrismaUI, input capture "planned for v0.2+". **verified** (both pages);
  licence and maturity **unresolved** (the two pages disagree). https://www.nexusmods.com/starfield/mods/17899,
  https://github.com/CarbonNode/CarbonUI
- **CharGenMenu** (Expired6978, v1.1.0.23, Aug 2026, game 1.16.244): edits Starfield's character creation menu (numeric
  sliders, JSON presets via SFSE, custom sliders from SFSE plugin folders). **verified** (page). The author made
  LooksMenu for FO4 and RaceMenu for Skyrim (**supported hypothesis**, common knowledge, not on this page).
  https://www.nexusmods.com/starfield/mods/6850
- **Custom Command Framework** (Snapdragon/Deweh, v1.0.2, GPLv3, source on GitHub): lets SFSE plugins add console
  commands; works with `Debug.ExecuteConsole()` as a Papyrus-to-native bridge. **verified** (page).
  https://www.nexusmods.com/starfield/mods/9779
- **Cassiopeia Papyrus Extender** (credits LarannKiar; v6.3 Nov 2025): Papyrus natives incl. `OpenMenu`, `CloseMenu`,
  `GetPerks`, `TESFurnitureEvent`, HUD notification control. **verified** only via a mirror page (allmods.net);
  Nexus page and licence **unresolved**.
  https://allmods.net/starfield-mods/starfield-miscellaneous/cassiopeia-papyrus-extender-v1-1/
- **Faster Menu Fix** and **Native Ultrawide Menus - SFSE** show SFSE hooks into menu classes are routine.
  **verified** (pages). https://www.nexusmods.com/starfield/mods/16990, https://www.nexusmods.com/starfield/mods/15699

### Health, damage, afflictions, radiation, survival
- **StarPatcher** (Zzyxzz, v3.5.0, June 2026): SFSE + CommonLibSF plugin that patches records at runtime from INI
  rules (ammo, NPCs, races, weapons, leveled lists, containers); same author family as RobCo Patcher (FO4) and
  SkyPatcher. Licence: closed, "no conversion to other games". **verified** (page).
  https://www.nexusmods.com/starfield/mods/12855
- **StarValor** (Zzyxzz, v1.7.0, April 2026): combat overhaul built on StarPatcher; removes HP gain on level-up and
  adjusts locational (limb) damage multipliers. **verified** (page). Shows Starfield has per-limb damage multipliers
  (BPTD) that are live. https://nexusmods.com/starfield/mods/13283
- **SMB Custom Independent Damage Modifiers** (SMB92, April 2026): player-only damage settings through hidden perks
  (entry points) plus Gameplay Option forms; notes a rounding error in option values. **verified** (page). Pattern for
  FO4 difficulty and survival damage settings. https://www.nexusmods.com/starfield/mods/16830
- **Alien Afflictions** (RetchERezzed, May 2026): makes creature attacks cause vanilla afflictions by editing attack
  records and "hitspell and affliction spell records"; no SFSE. **verified** (page). So afflictions are reachable as
  SPEL data. https://www.nexusmods.com/starfield/mods/17071
- Nexus forum (May 2025): `ENV_AfflictionScript` runs most affliction progression and recovery. **supported
  hypothesis** (one reply, not checked in the sources).
  https://forums.nexusmods.com/topic/13515870-has-anyone-ever-modded-starfields-afflictionprognosis-system-where-would-i-start
- Starfield's Fractured Limb injury: stages raise incoming damage, then O2 cost, then melee and accuracy penalties;
  cured by Immobilizer or Panacea. **verified** (database page; record type not given). Starfield's "Crippling" is a
  combat skill about downing enemies, not limb crippling. **verified**
  (https://nukesdragons.com/starfield/db/effects/affliction-fractured-limb, https://starfield.wiki.fextralife.com/Crippling).
- **Atmosphere Affects Radiation** (Faolyn, July 2025): overrides the environment conditions
  `ENV_CND_OnExtremePlanet_WeakMagnetosphere_DayTime` (0004787D) and `ENV_CND_Water_Apply_Radiation` (001F761F).
  **verified** (page). These are the hooks our planet must keep quiet or reuse for FO4 water and Glowing Sea rads.
  https://www.nexusmods.com/starfield/mods/14298
- **Deadly Hazards** (Space Pigeon, v1.2.3.0, inactive since June 2024): environment overhaul with Papyrus (Caprica,
  Champollion), xEdit-edited ESM, and edited SWF/GFX via JPEXS for UI. **verified** (page). Toolchain precedent for a
  HUD meter (Rads, needs) without SFSE. https://www.nexusmods.com/starfield/mods/5800
- **Peak Performance - Immersive Needs** (rbtRvlt, v2.5, June 2026; CC BY-SA 4.0, "open source"): hunger, thirst,
  exhaustion, intoxication, hygiene; food recognized by vanilla keywords, chems by form lists; small master.
  **verified** (page). Licence is compatible with study; check before reuse in GPL-3 code. https://www.nexusmods.com/starfield/mods/12420
- **Stellar Needs** (Darkfox127, v3, May 2026): needs as 0 to 100 with five stages; effects attached to food items;
  replaces vanilla Sustenance. **verified** (page). https://www.nexusmods.com/starfield/mods/12970

### Power armor, exosuits, mechs
- **Starfield now has a "Power Assist Armor" spacesuit** added with the Terran Armada DLC (Bethesda story DLC, released
  7 April 2026 with the Free Lanes update). The DLC is **verified** (Shacknews, RPGamer); the suit being part of it is
  **supported hypothesis** from two mod pages ("requires Terran Armada"). A mod (Power Assist Armor Enhanced) treats
  it as ordinary armor records with an enchantment, separate helmet and pack. **verified** (page). How it is worn (slot,
  any skeleton or movement change) is **unresolved**: check its ARMO/ARMA in xEdit.
  https://www.shacknews.com/article/148343/starfield-story-dlc-content-update,
  https://rpgamer.com/2026/03/starfield-hitting-ps5-in-april-alongside-new-update-dlc/,
  https://www.nexusmods.com/starfield/mods/17038, https://www.nexusmods.com/starfield/mods/16913
- Terran Armada also adds a robot companion, Delta, and robot enemies (Watchtower Mechs named on the mod page).
  **verified** (RPGamer; mod 17038). Relevant to robots and Automatron.
- Exosuit mods found are all spacesuit-slot outfits on the human skeleton: District 9 Prawns (510deshawn, July 2025,
  "standard spacesuit and helmet slots in one piece", rigged to HumanRace), Fallout 42 Power Armor (Lam0rak, 2023),
  N7 armor. None uses furniture, scripts or a skeleton swap. **verified** (pages).
  https://www.nexusmods.com/starfield/mods/14443, https://www.nexusmods.com/starfield/mods/6038,
  https://www.nexusmods.com/starfield/mods/10167
- Korodic's pilotable mech mod (2023 teaser): no technical detail, no release date. **verified** (PCGamesN) as still
  unreleased at that article; current status **unresolved**. https://www.pcgamesn.com/starfield/mech-mod

### Races, bodies, faces, animation tools
- **Exo Playable Race** (ExoWarlock313, v2.0, 2024): a playable look built by overriding chargen head-part lists
  (`HeadPartsChargenOptionsMale/Female`), `CharGenPresets` and the undersuit armor; a crafted aid item reopens chargen
  on old saves. Whether it adds a RACE record is not stated. **verified** (page). Most "races" on Nexus (e.g. Chiss) are
  skin and eye texture swaps. **verified** (https://www.nexusmods.com/starfield/mods/2547).
  https://www.nexusmods.com/starfield/mods/7992
- No Starfield mod adding a new creature skeleton with its own behavior graph was found; no Starfield ghoul or super
  mutant mod was found. **unresolved** (absence in search, not proof).
- **Native Animation Framework SF** (Snapdragon/Deweh, v1.2.3): SFSE plugin that plays glTF animations over the normal
  animation system, maps skeletons per race by JSON, needs CCF. It "can override vanilla animations but not replace
  them". **verified** (page). A possible route for FO4 creature or PA clips without authoring Havok behavior graphs.
  https://www.nexusmods.com/starfield/mods/7360
- **Starfield Blender Extension** (MrTrilB et al., 1.6.0 beta, May 2026): NIF/.mesh, morph, material, collision and
  skeleton-matching tools; behavior graphs not mentioned. **verified** (page). https://www.nexusmods.com/starfield/mods/16979
- **Body Morph Console** (Daimos22, 2024): SFSE plugin driving up to 100 body morph sliders at runtime. **verified**
  (page). Shows body morphs are runtime-addressable (useful for super mutant or ghoul body shapes on the human mesh is
  a **supported hypothesis** at best). https://www.nexusmods.com/starfield/mods/9427

## Precedents and lessons
- **Fallout London** (FO4 total conversion) kept FO4's SPECIAL/perk engine and swapped content: its own traits chosen
  at character creation (Acrobat, Hoarder, Chem Head, Puritan) and SPECIAL-gated perks. **verified** (Prima Games guide).
  Lesson: data-level perks and traits on the engine's own machinery are the cheap path; we lose that because CE2's
  menu is skills-shaped. https://primagames.com/gaming/fallout-london-character-creation-guide-best-traits-perks-and-starting-stats
- **SKK FastStart / SyntheticPlayer** (FO4): a start must set the stages that other systems listen to (already in
  saves-and-new-game.md). Applies to SPECIAL allocation at the vault exit and the Pip-Boy pickup.
- **Starfield needs mods** (Peak Performance, Stellar Needs) both state they replace or require disabling vanilla
  Sustenance. Lesson: our survival rebuild must decide early whether Starfield's Sustenance and affliction sliders are
  off or reused, or players get two systems stacked. **verified** (pages).
- **Exo race**: shipping a player "race" as chargen list overrides plus a re-open item works without a new skeleton.
  Lesson for synths (Gen 3 are human) and for ghoul player looks: a head-part and skin route is cheap. **supported
  hypothesis**.
- **Variable Progression Settings** uses `Debug.ExecuteConsole()` to set GMSTs from Papyrus. Lesson: GMST tuning of the
  XP curve may not need SFSE, but console use from scripts is a fragile pattern (it collides with other XP mods, per
  the page). **verified** (page).
- **StarPatcher's licence forbids "conversion to other games"** and it is closed source; it is a pattern to learn from,
  not a dependency to ship. **verified** (page).
- Deadly Hazards went inactive and survives through third-party patches: anything we build on a single-maintainer
  SFSE plugin needs a fallback. **verified** (page).

## Possibilities and hard limits in CE2
- **Possible, data only:** FO4 perk effects ride Starfield PERK entry points 0 to 157 (only 136 and 155 differ);
  perk rank and tier gates are data (Flat Perk Tree, Lively); settings menus via GPOF records (Variable Progression,
  SMB). **verified** (xEdit per special-perks-leveling.md; mod pages).
- **Possible, Papyrus only:** perk point grants on level-up, XP GMSTs through console calls, respec terminals,
  needs systems, afflictions as SPEL data. **verified** (mod pages, as claimed by authors).
- **Possible with SFSE:** custom HTML menus (Carbon UI, early), menu hooks and edits (CharGenMenu, ultrawide),
  runtime record patching (StarPatcher pattern), custom animation playback per race skeleton (NAF), perk point tables
  (PerkPointsPerLevel). **verified** (pages).
- **Limit:** SFSE co-save serialization is disabled since 0.2.12, so an SFSE plugin cannot store its own state in
  the save; SPECIAL, Rads, fusion core charge and needs must live in actor values, globals or Papyrus variables.
  **verified** (saves-and-new-game.md, sfse_whatsnew).
- **Limit:** no power armor runtime in CE2: the FURN flag is gone and every exosuit mod is a spacesuit outfit.
  A skeleton or behavior swap at runtime is **unresolved** (`SwitchToPowerArmor` and `SetRace` are declared; untested).
- **Limit:** no community tool authors new Havok behavior graphs for Starfield that we found; new creature skeletons
  are **unresolved** territory. NAF overrides animations but does not replace the graph.
- **Limit:** Starfield faces use face-dial and morph `.dat` data; no tool converts FO4 morph/tint data to it.
  **verified** (actors-and-npcs.md; no tool found in search).
- **Unknown:** whether the engine still applies Rads-to-max-HP (entry points 101/106) and the BPTD cripple path
  (`OnCripple`) in CE2. Starfield uses afflictions instead of crippled limbs. **unresolved**.

## Ties to Starfield systems (owner's note on reusable mechanics)
Candidates where FO4 data rides a Starfield system instead of a rebuild (each needs a check in the tables below):
- **Gameplay Options (GPOF)** for survival mode, difficulty, XP rate and immersion toggles. **verified** pattern.
- **Afflictions** for limb crippling stages, addiction and withdrawal, radiation sickness, survival diseases.
  **supported hypothesis**.
- **Activity Trackers** (Starfield's challenge counters) as an event source for XP or perk unlock conditions
  (kills, lockpicks, hacks, cripples). **supported hypothesis** (ATAN types verified in xEdit).
- **Level and XP engine** (one level curve, perk points per level). **verified** exists; tuning **unresolved**.
- **Factions and relationships**: races and creature families should map to FO4 factions on Starfield's FACT
  records (super mutants, ghouls feral vs non-feral, synths, robots), so hostility follows faction relations, not
  AIDT. See factions-crime-relationships.md and starfield-systems-to-reuse.md. **supported hypothesis**.
- **Power Assist Armor and spacesuit helmet logic** as the base for a stage-1 power armor. **unresolved**.
- **Robots from Terran Armada** (Delta and robot enemies) as rigs for Codsworth, protectrons and Automatron, if their
  skeletons fit. **unresolved**.

## Question framework

### SPECIAL
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| S1 | Does Starfield.esm have unused AVIFs of type Special (Attribute), or must we add seven new AVIFs? | decides FormIDs for SPECIAL in every converted condition and perk | FO4 SPECIAL are hardcoded AVIFs (xEdit note); SF has no SPECIAL (special-perks-leveling.md) | xEdit filter on Starfield.esm AVIF NAM1 = Special | blocks all perk and dialogue condition conversion (CTDA GetValue SPECIAL) | Fallout systems | key |
| S2 | How are derived stats (carry weight from STR, AP from AGI, HP from END) bound in CE2 when SPECIAL changes? | without it SPECIAL is cosmetic | FO4 binds in engine code (unresolved); SF has no binding | CK test: AV modifier MGEF conditioned on our STR AVIF; check carry weight updates live | needs S1; feeds power armor STR boost | Fallout systems | key |
| S3 | Where does SPECIAL allocation happen for the Vault 111 start (vault rep scene is prewar, phase 1 skips it)? | the first menu the player sees after chargen | FO4: "You're SPECIAL!" book and vault rep card (supported hypothesis) | read FO4 MQ101/MQ102 fragments in Base.zip for the SPECIAL menu call | needs SP1 (UI route); new game flow | new game | key |
| S4 | How do bobbleheads and the "SPECIAL book" add permanent points (script, perk, or ALCH)? | determines translator vs rebuild | unresolved | FO4 Base.zip: grep bobblehead scripts; xEdit one bobblehead MISC VMAD | needs S1 | Fallout systems | |
| S5 | Do SPECIAL-gated dialogue checks (Charisma persuasion) use SPECIAL or a speech challenge form? | dialogue conversion depends on it | Starfield moved speech challenges to SPCH (README) | xEdit: count FO4 INFO with CTDA on Charisma | dialogue converter | quests/people | |

### Perks and the perk chart
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| P1 | Fold FO4's NNAM rank chains into one Starfield PERK with N rank blocks, or keep one record per rank? | shapes the converter and every HasPerk check in FO4 scripts | SF PERK has rank blocks; NNAM not in SF (xEdit) | prototype both on one perk (e.g. Gun Nut) and test HasPerk and rank conditions in game | blocks perk converter | Fallout systems | key |
| P2 | Can Starfield's skills menu list our perks (a new category or reused one) and stay out of the way, or must the perk chart be a separate menu? | interim UI before a perk chart exists | tier gates are data (Flat Perk Tree); categories are a fixed enum (xEdit) | CK test: one perk with Category None and Playable flag; see where it shows | needs P1; decides SP1 scope | Fallout systems | key |
| P3 | Which FO4 perk effects use entry points 136/155 or FO4-only archetypes, and how many need a script shim? | sizes the shim | only 136 and 155 changed (xEdit) | offline Mutagen scan of FO4 PRKE entry point indices | perk converter | Fallout systems | |
| P4 | How do we keep Starfield skill perks, traits, backgrounds and Starborn powers off the player and out of loot (skill magazines)? | fence; avoids mixed systems | 144 start quests; magazines use BOOK Add Perk (supported) | xEdit: SF BOOK with Teaches PERK; chargen quest grants | new game flow | new game | |
| P5 | Do FO4 magazines (BOOK Add Perk) work unchanged in CE2? | cheap data win | field verified in both (xEdit) | CK test: one converted magazine | P1 | Fallout systems | |
| P6 | Companion perks (Idiot Savant, Lone Wanderer conditions on followers) map to which Starfield follower checks? | perk conditions reference follower state | companions.md covers affinity | grep FO4 perk CTDAs for follower functions | companion framework | quests/people | |

### XP and leveling
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| X1 | What are FO4's and Starfield's XP GMSTs (level curve, kill XP, lock/hack XP) and their values? | FO4 pacing on CE2 | VPS mod names `fXPModBase`, `fXPModMult` (page); FO4 values unresolved | xEdit GMST dump in both masters (one filter `XP|Level`) | X2 | Fallout systems | key |
| X2 | Does the vanilla level-up give Starfield skill points and a skills-menu prompt we cannot suppress? | a stray "skill point available" prompt breaks the FO4 feel | PerkPointsPerLevel and A.C.T. change it (one native, one INI) | in game: level up with a perk-point GMST/INI at 0; watch HUD | needs X1; blocks SP1 | Fallout systems | key |
| X3 | Does Starfield still award XP for FO4 actions (lockpick, hack, discover location, speech) natively, or only through scripts? | missing XP sources | `RewardPlayerXP` declared in SF (PC probe) | in game: pick a converted lock; read XP change | X1 | Fallout systems | |
| X4 | Can Activity Trackers (ATAN types) count FO4 events for XP or perk unlocks? | reuse of a Starfield system | 30 ATAN types incl. Kill, Lockpick, Cripple Limb (xEdit) | CK test: tracker on a hidden perk rank counting kills | P1 | Fallout systems | |

### Health, limbs and crippling
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| H1 | Does CE2 still cripple limbs from BPTD limb condition AVs and fire `OnCripple`, or are limbs only damage multipliers? | decides rebuild vs data copy for crippling | SF BPTD keeps cripple fields (xEdit); StarValor edits locational damage (page); SF uses afflictions | in game: converted FO4 BPTD on a test actor, damage a leg AV to 0, watch movement and event | V.A.T.S. limb targeting; stimpak behaviour | Fallout systems | key |
| H2 | If H1 fails, can crippling ride Starfield's injury afflictions (Fractured Limb stages) with a per-limb hit spell? | cheapest rebuild | afflictions are SPEL data (Alien Afflictions); `ENV_AfflictionScript` drives progression (forum) | xEdit: read SF affliction SPEL/MGEF; read ENV_AfflictionScript.psc | needs H1 | Fallout systems | key |
| H3 | Does the Stimpak MGEF archetype (31) heal limbs and health in CE2 like FO4? | basic healing loop | archetype index same (xEdit); engine use unresolved | CK test: converted stimpak on a crippled test actor | H1 | Fallout systems | |
| H4 | How do we show limb condition (Pip-Boy STAT, HUD vault boy) without the Pip-Boy rebuild? | player feedback | needs UI | design decision after SP1 | SP1 | Fallout systems | |
| H5 | Does Starfield's O2/CO2 stamina conflict with FO4 AP (sprinting, V.A.T.S.)? | AP is renamed Oxygen in entry points | supported hypothesis | in game: does sprinting drain the AV our AP maps to | V.A.T.S. | Fallout systems | |

### Radiation
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| R1 | Does a Rads AV still reduce max HP in CE2 (entry points 101/106)? | the core radiation rule | entry points exist (xEdit); engine use unresolved | in game: apply converted rad MGEF, read max HP | HUD red bar | Fallout systems | key |
| R2 | Do we reuse Starfield's environmental radiation (ENV conditions, radiation affliction) or turn it off on our planet and use FO4 HAZD? | avoids double radiation and wrong water radiation | Atmosphere Affects Radiation overrides two ENV conditions (page) | xEdit: list ENV_CND_* conditions and which planet data triggers them | world planet record; Glowing Sea | interiors | key |
| R3 | Can the HP bar show a red rads segment without SFSE (SWF edit like Deadly Hazards) or does it need Carbon UI/SFSE? | player feedback | Deadly Hazards edited SWF/GFX with JPEXS (page) | JPEXS: open SF HUD SWF, look for health bar clip | SP1 | Fallout systems | |
| R4 | Do RadAway/Rad-X (ALCH) convert as data? | cheap data win | ALCH layout translates (health page) | converter test on two records | R1 | Fallout systems | |

### Chems and addiction
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| C1 | Does an FO4 ALCH with an Addiction SPEL (Type Addiction) produce withdrawal in CE2, and does Starfield's own addiction affliction share that path? | data copy vs rebuild | SPEL Type Addiction exists in both (xEdit) | CK test: converted Jet with 100% addiction chance | Addictol (Cure Addiction archetype 28) | Fallout systems | key |
| C2 | Do Starfield's chem/aid crafting benches (Pharmaceutical Lab, WBDT 05) accept FO4 chem recipes? | crafting | keyword 102158 shared (stations.md) | CK test: one COBJ | items converter | Fallout systems | |
| C3 | Does a needs mod's or our addiction state conflict with vanilla affliction sliders in Gameplay Options? | stacked systems | needs mods require disabling Sustenance (pages) | read GPOF list in xEdit | S/V1 | Fallout systems | |

### Survival mode
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| V1 | How much of FO4 Survival is script (HC_ quest and scripts) vs engine settings (bed-only saves, no fast travel, ammo weight)? | port FO4's own scripts vs rebuild | supported hypothesis: mostly script | FO4 Base.zip: list `HC_*` scripts; grep for `Game.` calls that touch saving and travel | needs Papyrus shim list | Fallout systems | key |
| V2 | Can bed-only saving and the fast travel block be done with Papyrus or GMSTs in CE2, or need SFSE? | survival rules | unresolved | grep SF Game.psc for save and fast travel toggles; in game test | V1 | Fallout systems | key |
| V3 | Expose survival and difficulty as GPOF Gameplay Options? | native settings UI, no SFSE | GPOF used by VPS and SMB mods (pages) | CK test: one GPOF toggling a global | V1 | Fallout systems | |
| V4 | Turn off Starfield Sustenance, affliction and environmental sliders on new game, or reuse them? | avoids double needs | Sustenance option exists (health page) | read SF GPOF records and their globals | V3 | new game | |
| V5 | Should we study or reuse an open needs mod (Peak Performance, CC BY-SA) or port FO4's HC scripts? | build effort and licence | CC BY-SA 4.0 stated (page) | licence review vs GPL-3; read its source | V1 | Fallout systems | |

### Power armor
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| A1 | What is Starfield's Power Assist Armor (Terran Armada) in records: slot, race, skeleton, movement, HUD? **Talk through first (owner, 2026-10-19, page FS-4); still undecided.** Owner's note: "Depends the game for the older titles. It’s going to be a worn suit Like normal armor that you need to get training to wear, and In fallout four and 76 and the other big core it is going to be like fallout four and 76 where you need to climb in it and it is a secondary suit that makes things different" | a native "heavy suit" base for stage 1 | it is armor with an enchantment, helmet and pack (mod page); details unresolved | xEdit: open the Terran Armada plugin, find the suit ARMO/ARMA and its MGEFs | stage 1 of the PA rebuild | Fallout systems | key |
| A2 | What does Starfield's declared `SwitchToPowerArmor` do when called with a furniture ref? **Talk through first (owner, 2026-10-19, page FS-4); still undecided.** Owner's note: "Depends the game for the older titles. It’s going to be a worn suit Like normal armor that you need to get training to wear, and In fallout four and 76 and the other big core it is going to be like fallout four and 76 where you need to climb in it and it is a secondary suit that makes things different" | might be a working vestige | declared in SF scripts (PC probe) | in game: one Papyrus call on a test FURN | A3 | Fallout systems | key |
| A3 | Can `SetRace` (or a subgraph keyword) switch the player to a PA skeleton and graph at runtime, and back? **Talk through first (owner, 2026-10-19, page FS-4); still undecided.** Owner's note: "Depends the game for the older titles. It’s going to be a worn suit Like normal armor that you need to get training to wear, and In fallout four and 76 and the other big core it is going to be like fallout four and 76 where you need to climb in it and it is a secondary suit that makes things different" | true PA feel | SetRace declared; RACE subgraph layout same (xEdit) | in game: SetRace to a copy of HumanRace with a different skeleton path | animation track | Fallout systems | key |
| A4 | Can the FO4 PA mesh render on the human skeleton as a worn outfit (spacesuit slot) like the Prawn suits? **Talk through first (owner, 2026-10-19, page FS-4); still undecided.** Owner's note: "Depends the game for the older titles. It’s going to be a worn suit Like normal armor that you need to get training to wear, and In fallout four and 76 and the other big core it is going to be like fallout four and 76 where you need to climb in it and it is a secondary suit that makes things different" | cheapest playable PA | Prawn and N7 suits are human-rigged outfits (pages) | convert one PA piece mesh, equip in game | meshes converter | Fallout systems | key |
| A5 | Fusion core: AV plus timer, or ammo-like item consumed by a script? | drain and empty-core rules | record type unresolved | xEdit: FO4 fusion core record type and editor id | A1 | Fallout systems | |
| A6 | PA HUD: SWF edit of Starfield's helmet HUD, or Carbon UI / SFSE overlay? | presentation | Carbon UI exists, early; input capture not yet done (README) | JPEXS: SF HUD SWF; follow Carbon UI v0.2 | SP1 | Fallout systems | |
| A7 | What does MQ102 need from PA to be playable (stage 47 already in PA, stage 90 fusion core)? | phase-1 quest blocker | B4 spike marks the stages | read MQ102 stage conditions; decide a scripted skip | new game quest line | quests/people | |
| A8 | Can PA stations reuse Starfield's armor/spacesuit workbench menu for OMOD slots? | modding pieces | supported hypothesis (power-armor.md) | CK test: PA piece ARMO with OMOD at bench 07 | A4 | Fallout systems | |

### Races, bodies and faces
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| F1 | Which face route for the named cast: Starfield chargen faces tuned by hand (presets via CharGenMenu JSON), or FO4 facegen head as a skin/armor mesh? | 100+ named NPCs; recognisability | no converter exists; CharGenMenu saves JSON presets (page) | prototype Preston both ways; compare in game screenshots | blocks named NPC polish | quests/people | key |
| F2 | Does the CharGenMenu JSON preset format let us generate Starfield faces from data (offline), approximating FO4 morphs? | an automated face path | JSON presets exist (page); format unread | download nothing; ask the author or read the SFSE plugin docs on Nexus | F1 | quests/people | key |
| F3 | Ghouls: human race with ghoul head parts and skin (Exo-style chargen lists), or a separate race? | ghoul NPCs and a ghoul player option | Exo race uses chargen list overrides (page) | xEdit: FO4 GhoulRace vs HumanRace differences (skeleton, behavior) | factions (ghoul hostility); F4 | quests/people | |
| F4 | Super mutants: new race on a scaled human skeleton, or a FO4 skeleton import? | many enemies and Strong | FO4 SuperMutantRace uses its own skeleton (supported hypothesis) | xEdit: FO4 SuperMutantRace skeleton path; test scaling the human skeleton | animation track | Fallout systems | key |
| F5 | Synths: Gen 3 as human NPCs with a keyword; Gen 1/2 as robots | Institute content | supported hypothesis | xEdit: FO4 SynthRace vs Gen 1/2 races | F6 | quests/people | |
| F6 | Do Terran Armada robots (Delta) or Vasco give a skeleton and graph we can drive protectrons, Mr. Handy and Assaultrons with? | robots without new graphs | Delta exists (RPGamer) | xEdit: SF robot RACE skeleton and graph paths; compare to FO4 robot races | Automatron; NAF fallback | Fallout systems | key |
| F7 | Can NAF (glTF per race skeleton) play converted FO4 creature clips on a new race, as an interim to behavior graphs? | creature animation without Havok graph authoring | NAF maps skeletons per race (page); overrides, not replaces | CK + NAF test on one creature race (radroach) | animation track | Fallout systems | |
| F8 | Opening Starfield's chargen from our start quest: does it offer backgrounds and traits we must hide, and does CharGenMenu's edit change that? | first player screen | ShowRaceMenu and SetInChargen exist (saves page) | in game: our start quest calls ShowRaceMenu | P4 | new game | key |
| F9 | Body morphs for FO4 body shapes (heavy NPCs, mutants) via Starfield morphs at runtime? | variety | Body Morph Console drives morphs via SFSE (page) | read MRPH records count and slider names | F4 | interiors | |

### Cross-cutting: UI platform for character menus
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| SP1 | One UI route for perk chart, SPECIAL, level-up, PA HUD and Pip-Boy: edited Starfield SWFs, FO4 SWFs from the player's files, our own Scaleform, or Carbon UI (HTML)? | the biggest shared decision in this area | Scaleform in both games (next-phase); Carbon UI exists with disputed licence and early input support | decision record in docs/ai/decisions.md after U1 and a Carbon UI licence check | blocks S3, P2, R3, A6, H4 | Fallout systems | key |
| SP2 | Is Carbon UI's licence (GPL vs source-available) and SFSE version tracking good enough to depend on? | dependency risk | the Nexus page and README disagree | ask the author in the mod's posts (owner approval needed for outreach) | SP1 | release | key |
| SP3 | Which SFSE Papyrus extenders (Cassiopeia, CCF) are maintained, open and needed for OpenMenu or furniture events? | dependency list for the launcher | CCF GPLv3 on GitHub; Cassiopeia licence unknown | read Nexus pages and repos | SP1, A2 | release | |
| SP4 | Where does character state live, given no SFSE co-save (AV, global, Papyrus variable)? | save robustness | serialization disabled (sfse_whatsnew) | design note; test persistence over save/load | all | Fallout systems | |

## Sources
- Engine-mechanics pages (project): special-perks-leveling.md, health-damage-effects.md, power-armor.md,
  actors-and-npcs.md, saves-and-new-game.md in /mnt/project-files/research/engine-mechanics/
- Nexus Mods (Starfield): 16279 Variable Progression Settings; 1779 PerkPointsPerLevel; 12911 A.C.T.; 5538 Flat Perk
  Tree; 5928 Lively's Enhanced Skills; 6484 Skill ReSpec Terminal; 17899 Carbon UI; 6850 CharGenMenu; 9779 Custom
  Command Framework; 16990 Faster Menu Fix; 15699 Ultrawide Menu Replacer; 12855 StarPatcher; 13283 StarValor; 16830
  SMB Damage Modifiers; 17071 Alien Afflictions; 14298 Atmosphere Affects Radiation; 5800 Deadly Hazards; 12420 Peak
  Performance; 12970 Stellar Needs; 17038 Power Assist Armor Enhanced; 16913 Varia retexture; 14443 District 9 Prawns;
  6038 Fallout 42 Power Armor; 10167 N7 armor; 7992 Exo Playable Race; 2547 Chiss; 7360 NAF SF; 16979 Starfield Blender
  Extension; 9427 Body Morph Console (all https://www.nexusmods.com/starfield/mods/<id>)
- https://github.com/CarbonNode/CarbonUI
- https://allmods.net/starfield-mods/starfield-miscellaneous/cassiopeia-papyrus-extender-v1-1/
- https://forums.nexusmods.com/topic/13515870-has-anyone-ever-modded-starfields-afflictionprognosis-system-where-would-i-start
- https://nukesdragons.com/starfield/db/effects/affliction-fractured-limb; https://starfield.wiki.fextralife.com/Crippling
- https://www.shacknews.com/article/148343/starfield-story-dlc-content-update;
  https://rpgamer.com/2026/03/starfield-hitting-ps5-in-april-alongside-new-update-dlc/
- https://www.pcgamesn.com/starfield/mech-mod
- https://primagames.com/gaming/fallout-london-character-creation-guide-best-traits-perks-and-starting-stats
- Not read (rate-limited): https://tesrskywind.com/faq/,
  https://forums.nexusmods.com/topic/3742365-theory-on-restoring-skills-and-the-leveling-system
