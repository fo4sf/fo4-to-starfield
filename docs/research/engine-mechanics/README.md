# Engine mechanics reference: Fallout 4 (Creation Engine) vs Starfield (Creation Engine 2)

A reference for every thread and agent on this project: how each game mechanism works in Fallout 4 and in Starfield,
what carries across as data, what must be rebuilt, and what needs SFSE or Starfield's Creation Kit. Started
2026-10-19 by Claude-cloud on the owner's request; extended breadth first.

Where it lives: `/mnt/project-files/research/engine-mechanics/` (shared folder) and `docs/research/engine-mechanics/`
in the repo (branch `claude/engine-mechanics-reference-kxomgu`). The plan-level notes it builds on are in
[../next-phase/](../next-phase/) (draft PR #380): those say what to do next; this reference says how things work.

## How to use it

- Each file has the same parts: In short, How Fallout 4 does it, How Starfield does it, Mapping for the port, What
  must be rebuilt (and what needs SFSE or the CK), Port status, Open questions, Sources.
- Every claim carries a label from docs/ai/research-log.md: **verified** (read from a file, a record definition or a
  project measurement), **supported hypothesis** (evidence, not confirmed), **unresolved**.
- The main primary source for record layouts is xEdit's definitions (`wbDefinitionsFO4.pas`, `wbDefinitionsSF1.pas`,
  TES5Edit dev-4.1.6), read side by side. They are reverse engineered; where the project read the real files, that
  wins.

## Settled decisions this reference takes as given

The player is silent. Starfield's animations first, FO4 clips later. SFSE and the free Starfield Creation Kit may be
required. The Commonwealth, Far Harbor and Nuka-World share one Earth-like planet with real days and weather. The new
game (Vault 111 start, no Starfield intro) comes first. Breadth before polish. Starfield's own systems are fenced out
of our world unless reused on purpose.

## Mechanisms

| area | file | one line |
|---|---|---|
| foundations | [records-and-plugins.md](records-and-plugins.md) | plugins, FormIDs, the **condition function map** (458 of 479 carry over by name), scripts on forms, name clashes |
| foundations | [record-counts.md](record-counts.md) | every record type with its count in each game |
| missions | [quests.md](quests.md) | QUST, aliases, stages, objectives, Story Manager (Starfield dropped Kill, Arrest, Craft and other events) |
| conversations | [dialogue.md](dialogue.md) | DIAL, INFO, scenes; FO4's four-slot wheel becomes Starfield's choice list; voice and lip sync |
| companions | [companions.md](companions.md) | follower framework, affinity (FO4 scripted, Starfield AFFE records), perks, command mode |
| scripting | [papyrus-and-script-extenders.md](papyrus-and-script-extenders.md) | Papyrus in both engines, fragments, native gaps, F4SE vs SFSE, sources |
| actors | [actors-and-npcs.md](actors-and-npcs.md) | NPC_, races, templates, faces, leveled actors, creatures and robots |
| AI | [ai-packages-and-schedules.md](ai-packages-and-schedules.md) | packages, procedures, schedules, sandboxing, idle markers |
| factions | [factions-crime-relationships.md](factions-crime-relationships.md) | factions, relationships, crime, keeping Starfield's crime out |
| combat | [combat-detection-stealth.md](combat-detection-stealth.md) | combat styles, AI combat, detection, stealth |
| character | [special-perks-leveling.md](special-perks-leveling.md) | SPECIAL, perks, XP and levels vs Starfield's skills |
| character | [health-damage-effects.md](health-damage-effects.md) | health, limbs, damage, effects, chems, survival, radiation |
| Fallout system | [vats.md](vats.md) | V.A.T.S. and what rebuilding it needs |
| Fallout system | [power-armor.md](power-armor.md) | frames, pieces, fusion cores, enter and exit, HUD |
| items | [items-crafting-modding.md](items-crafting-modding.md) | weapons, armor, junk and components, object mods, workbenches |
| settlements | [workshop-and-settlements.md](workshop-and-settlements.md) | workshop build mode, resources, settlers, supply lines |
| world objects | [terminals-holotapes-locks.md](terminals-holotapes-locks.md) | terminals, holotapes, notes, lockpicking and hacking |
| loot | [leveled-lists-and-encounter-zones.md](leveled-lists-and-encounter-zones.md) | leveled lists, encounter zones, respawn |
| presentation | [animations.md](animations.md) | Havok behaviours and clips in both engines, idles, furniture, faces |
| presentation | [ui-pipboy-hud-menus.md](ui-pipboy-hud-menus.md) | Scaleform menus, HUD, Pip-Boy, dialogue and barter menus |
| presentation | [radio-music-sound.md](radio-music-sound.md) | radio stations, music, sound descriptors vs Wwise |
| world | [weather-time-climate.md](weather-time-climate.md) | climate, weather, time of day vs planets, atmospheres, biomes |
| world | [world-cells-navigation.md](world-cells-navigation.md) | worldspaces, cells, terrain, navmesh, locations, map markers, doors |
| lifecycle | [saves-and-new-game.md](saves-and-new-game.md) | save files, new game flow, character creation, skipping Starfield's intro |
| world objects | [doors-activators-furniture.md](doors-activators-furniture.md) | doors and teleports, door motion, activators, furniture, containers |
| world objects | [physics-and-collision.md](physics-and-collision.md) | Havok formats, collision layers, motion types, destruction, impacts |
| presentation | [materials-textures-lighting.md](materials-textures-lighting.md) | BGSM/BGEM vs .mat, material swaps, texture sets, decals, lights, image spaces |
| DLC | [dlc-mechanics.md](dlc-mechanics.md) | Automatron, Far Harbor, Nuka-World, Vault-Tec, Contraptions, Wasteland Workshop |
| world | [vehicles-and-travel.md](vehicles-and-travel.md) | vertibirds, fast travel, elevators, travel across the one planet |
| economy | [economy-vendors-barter.md](economy-vendors-barter.md) | caps, vendors, barter, restock, pickpocketing |
| foundations | [supporting-records.md](supporting-records.md) | the leftover record types (reference groups, layers, splines, flora ...) |


## Cross-cutting findings so far

1. **Records mostly translate; scripts, voice and animation are the rebuilds.** Quests, dialogue, scenes, packages and
   conditions keep their model in CE2 (verified field by field in the files above). The work is in Papyrus
   (recompile plus a shim for FO4-only natives), audio (Wwise) and lip sync (Creation Kit), and animation.
2. **Map enums by name, never by number.** Dialogue subtypes, scene action types, alias fill types and condition
   function indices were renumbered or reused between the games (verified). Mutagen's typed records make this safe;
   raw byte copies do not.
3. **Starfield moved several FO4 script systems into records**: affinity (AFFE), speech challenges (SPCH), quest
   rewards and timers (QUST stage data). Rebuilding FO4's systems on those records is usually cheaper than porting
   FO4's scripts.
4. **FO4 vanilla script sources exist**: the Fallout 4 Creation Kit installs them as `Data\Scripts\Base.zip`
   (falloutck.uesp.net Papyrus FAQ). The PC probe (Oct 19) found them **not installed** on the owner's PC, so FO4
   scripts need the free FO4 Creation Kit installed, or a decompiler. Starfield's 5,029 sources are there.
5. **Name clashes are real**: Papyrus script names and editor ids are global; converted content needs its own prefix
   or namespace.
6. **More carries over by index than expected**: perk entry points 0 to 157 keep their numbers (only 136 and 155
   changed meaning), magic effect archetypes 0 to 49 are identical, VMAD script data and the door teleport (XTEL) and
   lock (XLOC) layouts are identical, and both games keep their currency item at FormID 0000000F. (verified, xEdit;
   see [special-perks-leveling.md](special-perks-leveling.md), [health-damage-effects.md](health-damage-effects.md),
   [papyrus-and-script-extenders.md](papyrus-and-script-extenders.md), [economy-vendors-barter.md](economy-vendors-barter.md))
7. **Some FO4 records fold into others**: FO4's encounter zones (ECZN) became fields of Starfield's location record;
   FO4's material swaps (MSWP) give way to layered material swaps (LMSW); holotapes (NOTE) map best to data slates
   (BOOK); terminal menus moved into their own record (TMLM). (verified, xEdit)
8. **Bit traps**: package flag bit 29 means "Wear Sleep Outfit" in FO4 and "Weapon Drawn: Ready" in Starfield; door
   flag bits 0 and 7 changed meaning. A converter rewrites flags by name.
9. **Travel across the one planet**: Starfield's own surface fast travel works within one landing and uses the ship
   between landings, which we fence out, so trips between the Commonwealth, Far Harbor and Nuka-World stay scripted
   (boat, monorail, vertibird) as in FO4 ([vehicles-and-travel.md](vehicles-and-travel.md)). (supported hypothesis)

Every Fallout 4 record type now has at least one page; [record-counts.md](record-counts.md) lists where.
