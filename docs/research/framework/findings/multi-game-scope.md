# Multi-game scope: Fallout 3, New Vegas and others on the same core, one playthrough

Author: multi-game-scope (Claude-cloud research agent), 2026-10-19. Labels: **verified** (read in the linked source or
a file), **supported hypothesis**, **unresolved**. Builds on docs/ROADMAP.md C3 build 2 ("All games, one
playthrough") and on engine-mechanics/special-perks-leveling.md, which this note does not repeat.

**Bottom line.** Tale of Two Wastelands (TTW) shows that a merged FO3 + New Vegas playthrough works when four things are
true: the installer **builds everything from the player's own game files** (TTW ships patches, not Bethesda assets, and
Bethesda checked that); one game's systems become the **single rule set** (TTW moved FO3 onto NV's rules: Damage
Threshold, NV perks, NV level cap, with one shared character); travel between worlds is a **scripted chokepoint** (a
train station at each end, with quest variables that the console must not bypass); and the team **rebalances** rather
than ports each game's numbers. The Fallout 4 remakes teach the other half. Capital Wasteland (FO3 in FO4) stalled in
2018 over **voice audio**: the team could not ship it, the extract-from-your-own-copy plan fell through, and Bethesda
said it could not license voice work it does not own; the team turned to re-voicing. F4NV rebuilds rather than ports.
The one direct converter precedent, terry-haire's **fnv-to-fo4** (GPL-3, user-run, needs FNV, FO4 and the FO4 CK),
converts the world, cells, landscape and placed objects but **no NPCs, creatures, quests or scripts**, and dropped
navmeshes because they crashed. For us that splits the job in two. A second *reader* (Gamebryo NIF 20.2.0.7 bsver 34,
ESM form version 15 era, BSA 104) feeding our existing world pipeline is realistic, and Mutagen already has a Fallout 3
project. *Behaviour* (ObScript in SCPT records, creatures as CREA, a hardcoded 77-entry actor value enum, karma,
NV reputation, hardcore needs, challenges) has no FO4 counterpart, so it must be **rebuilt as data and Papyrus on our
core**, not translated. Geography forces scripted travel: DC to Las Vegas is about 3,350 km great-circle, versus
about 630 km DC to Boston, so one "Earth-like planet" can hold these worlds only as separate landings joined by
travel scenes. The biggest design decision is the one TTW made early: **whose rules win** (FO4 perks-only, or the
skills, karma and reputation of FO3/NV), because every later converter step depends on it.

## Findings

### 1. How TTW merged FO3 into New Vegas

| Finding | Label | Source |
|---|---|---|
| TTW is a total conversion that merges *Fallout 3* and its DLC into *Fallout: New Vegas*, so both play in one playthrough with one character. It runs on the NV engine and moves FO3 onto NV's mechanics. | verified | fallout.wiki TTW page; ModPub TTW page |
| Its installer builds TTW from the player's own files: it "patches and creates non-unique assets dynamically from the originals", decompresses both games' BSAs, writes the Custom INI, updates Vorbis libraries and converts audio. It needs English FO3 and FNV with **all DLC**, both run once first. Steam, GOG and Epic copies are supported (mixing stores is fine); Microsoft Store copies are not. It needs about 40 GB free (TTW itself about 17 GB). | verified | TTW guide FAQ, TTW guide intro |
| Bethesda reportedly checked that TTW did not distribute FO3 assets, which is why the special installer exists. Bethesda reportedly asked modding sites not to host TTW, so it lived on its own site and later moved to ModPub. | verified as reported (the wiki says "reportedly") | fallout.wiki TTW page |
| Travel: a custom **Union Station** in a new DC worldspace (Columbus Circle) runs a train to the Mojave; the return is Union Station in Freeside. A short quest unlocks the route. The FAQ warns: do not use console commands or old mods to move between wastelands, because "TTW sets specific variables and quests that these bypass." | verified | TTW guide FAQ; fallout.wiki TTW page |
| Continuity: the Lone Wanderer becomes the Courier. A 2014 player report says that on arrival a screen says "several years have past", NV starts in Doc Mitchell's house, and character creation is skipped because it happened in Vault 101. A newer FAQ mentions a "wasteland selection" at start, configured through the Custom INI. | verified (fallout.wiki / tropedia for the continuity, the TTW FAQ for the selection); the 2014 arrival detail is a player report and may be out of date | tropedia TTW page; Steam thread 522728813700378577; TTW guide FAQ |
| Level cap: **60** in current TTW (ModPub 3.4.0 page and the FAQ say the cap goes "from 50 to 60"). An older TTW forum thread says 50 (NV's cap) and describes a reduced-XP plugin and a perk-per-level change to offset it. The cap changed between versions. | verified (both statements; the forum one is older) | ModPub; TTW guide FAQ; TTW forum t=6908 |
| Perks: one perk per level normally, **one every two levels in Hardcore**. FO3 bobbleheads give "mini perks" instead of SPECIAL/skill points, because those are otherwise easy to max. FO3 companions gain NV-style companion perks; a new perk, Stay Frosty, was added. | verified | TTW guide FAQ; fallout.wiki TTW page |
| NV features carried into FO3 content: companion wheel, weapon mods, crafting and recipes, harvestable plants, poisons. FO3's Damage Reduction gives way to NV's Damage Threshold. | verified (features); DT vs DR from a 2017 forum post, supported hypothesis | fallout.wiki; TTW forum t=1935 |
| Balance: some items and perks were changed because the games balance differently. For example, NV-balanced super mutants could be far too hard in FO3 areas. | verified | tropedia TTW page |
| Hardcore restores FO3's vanilla ending: if the player activates Project Purity, they die and the game ends. | verified | TTW guide FAQ |
| DLC: FO3 and its DLC sit in the load order at fixed console indices (FO3 06, Anchorage 07, Pitt 08, Broken Steel 09, Point Lookout 0A, Zeta 0B). TTW ships its own cleaned plugins. The Pitt's ammo press was reworked; Sally gives Liquid Nitrogen after Zeta. | verified | TTW guide FAQ |
| Faction relations did not carry between worlds in 2014 ("Nah, they don't at the moment"). Talon Company and Regulators exist only in the FO3 world. | verified as a 2014 player report; current state unresolved | Steam thread 522728813700378577 |
| Karma vs reputation: TTW keeps FO3 karma challenges (for example, reach a level with Good/Neutral/Evil karma). Its Speech bobblehead lets you hire any companion regardless of karma. How TTW reconciles FO3 karma with NV reputation is **not documented** in the pages read. | verified (the challenges); unresolved (the reconciliation) | TTW guide FAQ |
| TTW has been out since 2012. The team will not port to the rumoured remasters: "It would be a mammoth effort and would require an entire rebuild of the project." | verified | fallout.wiki; Insider Gaming |
| History: TTW grew out of Requiem for the Capital Wasteland. Scripting support in xEdit renewed the project. Zilav wrote the installer and tools. | verified | fallout.wiki; ModPub |

### 2. Porting older Fallouts into Fallout 4: what worked, what did not

| Finding | Label | Source |
|---|---|---|
| **Capital Wasteland** (FO3 in FO4) stopped in March 2018 after the team asked Bethesda. The blocker was FO3's **voice recordings**. Shipping them was not viable, and having players extract them from their own copies "also fell through". The mod lead said Bethesda could not grant rights to voice work it licenses rather than owns. A lawyer reportedly called the plan "sketchy as all hell". | verified | PCGamesN |
| Capital Wasteland resumed in January 2019 as a **re-voiced recreation** ("Not identical"), probably with FO4's music and ambience. The extraction and conversion were also hard because of the Gamebryo-to-Creation Engine move. The team was under 10 people. DSOGaming cites about 45,000 FO3 voice lines. | verified | PC Gamer UK; DSOGaming |
| **F4NV** (NV in FO4) remakes every quest "as they were in New Vegas" and wants "all of the legacy systems ... functional in the Creation Engine", naming **skills, damage threshold and weapon condition**. The narrative is unchanged. There is no release date. | verified | Nexus Mods news 13916 |
| A separate NV-in-FO4 release covered by PCGamesN says "Nothing is directly ported" and offers a sandbox of about a quarter of the map with no quests yet. Whether it is F4NV or another project is unresolved here. | verified quote; identity unresolved | PCGamesN |
| **fnv-to-fo4** (terry-haire, GPL-3.0, Nexus FO4 mod 75425) is the closest precedent to our model: a user-run exe needing FNV, FO4 and the FO4 Creation Kit installed, about 1 to 2 hours. It converts the NV base game's worldspace, cells, landscape and placed objects, and most models. **It does not convert** NPCs, creatures, quests or scripts. Weapons and armor appear but cannot be equipped. v58 removed navmeshes ("causing a lot of crashes"). It builds BA2s and has a terrain "black holes" workaround. Latest is v63 (20 June 2024), which fixed "some TTW related issues". Tools credited: xEdit, NifSkope, BSA Browser. | verified | Nexus FO4 mod 75425; GitHub terry-haire/fnv-to-fo4 |

### 3. Formats: what a FO3/NV reader has to handle

| Item | FO3 / FNV | FO4 / Starfield (project data) | Label | Source |
|---|---|---|---|---|
| NIF | 20.2.0.7, user 11, bsver 34 (final; earlier bsver 14 to 33 also tagged FO3/NV) | FO4 20.2.0.7 user 12 bsver 130; FO76 bsver 155; Starfield bsver 172 | verified | niftools nif.xml lines 199-217 |
| Plugin header | TES4 with HEDR; form versions are older than FO4's | FO4 header form version 131, HEDR 1.0; SF 581, HEDR 0.96 | FO4/SF verified (docs/measurements/fo4_esm.json, sf_esm.json); FO3/NV form version unresolved here | project files |
| Record types | FO3 has 89 `wbRecord` types in xEdit (TES4 included), FNV 106; FNV adds 17: ALOC, AMEF, CCRD, CDCK, CHAL, CHIP, CMNY, CSNO, DEHY, HUNG, IMOD, LSCT, MSET, RCCT, RCPE, REPU, SLPD | FO4 has no CREA, SCPT, REPU or CHAL (checked in fo4_esm.json); FO4 has KYWD | verified | xEdit wbDefinitionsFO3.pas / FNV.pas (dev-4.1.6), diff of `wbRecord(` signatures; fo4_esm.json |
| Creatures | separate CREA base records (and ACRE placed refs) beside NPC_ | FO4 creatures are NPC_ with a race | verified (record lists) | xEdit; fo4_esm.json |
| Scripts | **ObScript**: SCPT records with SCHR header, SCDA compiled bytecode, **SCTX source text**, SLSD/SCVR locals, SCRO references; object/quest/effect types; attached via SCRI; "embedded scripts" also live inside INFO, PACK, TERM and PERK entries; xNVSE adds string/array local types | Papyrus .pex, attached through VMAD | verified (layout) | xEdit wbDefinitionsFNV.pas 3035-3110, 4919 |
| Script source in shipped masters | whether Fallout3.esm/FalloutNV.esm keep SCTX filled (readable source with no decompiler) | n/a | **supported hypothesis** (the field exists and xEdit shows it; not checked in a real file) | xEdit |
| Actor values | a **hardcoded enum** of 77 entries (Strength..Luck 5-11, Karma 23, XP 24, skills 32-45, FNV adds Dehydration 73, Hunger 74, Sleep Deprivation 75, Damage Threshold 76). FO3 index 41 is "Small Guns"; FNV renames it "Guns" and uses 44 for "Survival" | FO4/SF use AVIF forms (special-perks-leveling.md) | verified | xEdit FNV 3335-3417; FO3 2515-2560 |
| NV reputation | REPU record = EDID, FULL, ICON, DATA float Value; conditions GetReputation / GetReputationPct / GetReputationThreshold (indices 573-575) | none | verified | xEdit FNV 8482, 415-417 |
| NV challenges | CHAL with 14 types (kill from list, discover map marker, use skill, craft ... scripted), threshold, recurring flag | FO4 has no CHAL; SF's activity trackers (special-perks-leveling.md) are the closest | verified | xEdit FNV 8249 |
| NV hardcore | IsHardcore (586), IsAlwaysHardcore (619), GetHardcoreTracking condition; DEHY/HUNG/SLPD stage records (threshold + SPEL) | FO4 Survival is a different design | verified (records); mapping supported hypothesis | xEdit FNV |
| Perk entry points | FO3/NV entry points include Get Bad/Good Karma and Modify Damage Threshold (defender/attacker, 56/58) | FO4/SF table (special-perks-leveling.md) lacks DT | verified (FNV list) | xEdit FNV 1591-1631 |
| Archives | BSA (pre-BA2). TTW unpacks them. | BA2 | verified that TTW decompresses BSAs (TTW FAQ); the BSA version number is unresolved here | TTW guide FAQ |
| Library support | Mutagen's repo has a `Mutagen.Bethesda.Fallout3` project and a Fallout3 records solution; New Vegas is not named. | Mutagen covers FO4 and Starfield | verified (project folders exist); maturity and NV coverage unresolved | GitHub Mutagen-Modding/Mutagen |

### 4. Systems that differ between the games (supplements special-perks-leveling.md)

- **Karma (FO3)**: from -1000 to +1000 in five bands (Very Evil -750 and below; Evil; Neutral -249..+249; Good;
  Very Good +750 and up). It decides who joins: Clover and Jericho need evil karma; Butch and RL-3 neutral; Fawkes and
  Cross good, and they leave if you turn evil; Dogmeat and Charon join at any karma. It also triggers Talon Company or
  Regulator hit squads and Three Dog's comments. The console shows it as `player.getav karma`, and it is AV 23 in
  the enum. **verified** (fallout.fandom Karma (Fallout 3); xEdit). NPCs carry a "Karma (Alignment)" float in their
  AI data (xEdit FNV 4362). **verified**.
- **Reputation (NV)**: a per-faction REPU value with threshold conditions (above). The fame/infamy split and the exact
  thresholds are **unresolved** here (search budget ran out before a primary source on them).
- **Level caps**: FO3 starts at 20, and Broken Steel raises it to 30 (**verified**, Wikipedia FO3 DLC). TTW is at 60,
  as above. NV's base cap of 30, raised by DLC to 50, is **supported hypothesis** (common knowledge, not re-read).
- **Skills**: FO3/NV have 13 skills as hardcoded AVs (above); FO4 dropped skills for perks only. F4NV restores skills.
  **verified** (enum; F4NV quote).
- **Damage Threshold** (NV) versus Damage Reduction (FO3) and FO4's resistance model. TTW unified on DT; F4NV
  restores DT. **verified** (xEdit AV 76, F4NV quote).
- **Anchorage is a VR simulation**, Zeta is in orbit, the Pitt is Pittsburgh, and Point Lookout is in southern
  Maryland. **verified** (Wikipedia FO3 DLC). So only the Pitt and Point Lookout need real map positions; Anchorage and
  Zeta are sealed worlds reached by a scripted transition.
- **Broken Steel** changes the FO3 ending so play continues; TTW's Hardcore brings back the death ending. **verified**.

### 5. Geography on one planet

Great-circle distances (**computed** from approximate city-centre coordinates; an inference, not a game fact):

| Pair | km | miles |
|---|---|---|
| DC (Capital Wasteland) to Boston (Commonwealth) | 634 | 394 |
| DC to Las Vegas (Mojave) | 3,349 | 2,081 |
| Boston to Las Vegas | 3,813 | 2,370 |
| DC to Pittsburgh (The Pitt) | 306 | 190 |
| DC to Point Lookout, MD | 114 | 71 |
| Boston to Bar Harbor, ME (Far Harbor area, approx.) | 323 | 200 |
| DC to Charleston, WV (FO76 Appalachia, approx.) | 404 | 251 |
| Las Vegas to Zion, UT (Honest Hearts) | 226 | 141 |

The project's settled layout puts each world on its own overlay landing on one host planet, joined by scripted travel
(engine-mechanics/vehicles-and-travel.md). Whether Starfield's surface map can fast travel between landings without the
ship is still **unresolved** there. The distances above mean no continuous terrain can join these worlds. FO3/NV
worlds would be more landings, reached by a train or vertibird scene, as TTW does with Union Station. The east-coast
cluster (DC, the Pitt, Point Lookout, Boston, Far Harbor, Appalachia) is close enough that **relative map positions**
could follow real geography. The Mojave sits across the continent. **supported hypothesis**

## Precedents and what they teach us

1. **TTW: the user's own files, rebuilt locally, every DLC required.** This is the same model as ours, and Bethesda
   tolerated it after checking. TTW still had hosting friction (sites asked not to host it). Lesson: an FO3/NV module
   for our launcher should require each game plus all its DLC, like TTW, so one rule set holds, and should be built
   like TTW's installer. **supported hypothesis**
2. **TTW: one rule set, then rebalance.** TTW did not run FO3's rules in FO3 areas and NV's rules in NV areas. It made
   NV's rules universal and retuned FO3 content (level cap, bobbleheads, perk rate, enemies). Our equivalent would be
   FO4's rules (SPECIAL and perks, no skills, no karma) everywhere, with FO3/NV systems rebuilt on top. Or we pick a
   superset. Either way, the decision has to come first.
3. **TTW: travel through a chokepoint with quest state.** Variables are set on the train trip, so other ways between
   worlds break things. That is a design rule for us: arrival scripts set world-state, so direct transfers (COC, our
   own test teleports) must run the same handler.
4. **Capital Wasteland: voice is the legal wall, even with your own copy.** Its extract-at-home plan "fell through". Our
   launcher already converts the player's own copy, and TTW does the same, including audio conversion. That suggests
   the problem was distribution, not local conversion, but it is the riskiest unknown and needs owner/legal judgement.
   **unresolved**
5. **fnv-to-fo4: the world converts, behaviour does not.** Even a mature, GPL-3, user-run converter stopped at
   statics, cells and landscape. It dropped navmesh conversion. This mirrors our own finding that records translate
   and scripts, voice and animation are rebuilds, but harder: ObScript has no Papyrus counterpart to recompile against.
6. **F4NV: keep legacy systems working.** F4NV chose to rebuild skills, DT and weapon condition in CE1. That is the
   "superset core" option, at the cost of a long build with no release date.
7. **TTW will not move engines** ("would require an entire rebuild"). Nobody has moved a merged FO3+NV to a newer
   engine. We would be the first, so expect no reusable logic beyond lessons. **verified** quote; inference.

## Risks

| Risk | Likelihood | Reasoning |
|---|---|---|
| Voice audio for FO3/NV is treated as unshippable even when converted locally | medium | Capital Wasteland stalled on exactly this, but TTW converts audio locally and still ships. Our model matches TTW, not CW's first plan. Needs owner and legal judgement before any FO3/NV work. |
| Hosting friction (Nexus or GitHub asked not to host) | low-medium | Bethesda asked sites not to host TTW (reported), even though it ships no assets. A merged FO3/NV-on-Starfield could draw the same response. |
| ObScript behaviour is the real cost: thousands of SCPT and embedded scripts rewritten by hand or by a transpiler | high | No precedent converted scripts (fnv-to-fo4 explicitly does not). If SCTX source is present, a transpiler is possible but untested. |
| Rule-set conflict (karma/reputation/skills/DT vs FO4 perks) multiplies rebalancing work | high | TTW needed rebalance passes over years; balance is per-content. |
| Second reader quality (NIF bsver 34, FO3/NV collision, CREA) drains time from FO4 breadth | medium | The owner's order puts breadth first. FO3/NV is a "later scope". A reader is moderate work, but bugs in older meshes, havok and skinning are a known long tail (fnv-to-fo4 still had rough edges at v63). |
| FormID and load-order collisions when several converted games share one load order | medium | TTW pins FO3 and its DLC at fixed indices. Our plugin count per game (master + 5 DLC + ours) could press on Starfield's plugin limits; unresolved. |
| Save bloat and world-state across worlds | medium | Every world's quests live in one save. TTW managed it on 32-bit NV, which suggests it is workable, but Starfield save behaviour with this many landings is untested. |
| FO76 is online-only content under separate terms | high that it stays out | Its data is server-driven; ROADMAP already defers it to an owner call. |

## Questions for the framework

### New game
1. **Which game does a multi-game playthrough start in, and can the player choose?** TTW starts in Vault 101 or offers
   a wasteland selection (TTW FAQ). Options: always Vault 111 (FO4 first, chronologically last); chronological (FO3
   2277, NV 2281, FO4 2287), which TTW's Lone Wanderer-to-Courier time skip follows; or player choice. Why it
   matters: chargen happens once, so later arrivals must skip it, like NV's skipped Doc Mitchell creation. Evidence:
   owner decision plus a prototype arrival quest. Who: owner.
2. **What is the player character across games: one person (TTW: Lone Wanderer becomes Courier) or a new identity?**
   A silent player is settled. FO3 and NV protagonists are already silent, which fits, but NV quests name you "Courier".
   Options: one person with lore glue; one person with no lore claims; or a "wanderer" frame outside canon. Who: owner.
3. **Does phase 1's new-game flow need a hook now so a later FO3/NV start can plug in?** Cheap now, costly to retrofit.
   Evidence: review the new-game design for a "start world" parameter. Who: offline review.

### Door animations
4. **Do FO3/NV load doors need the same enter/exit treatment, and are their door records compatible?** FO3/NV doors
   use XTEL-style teleports in an older layout (unresolved). The engine-mechanics notes show FO4 to SF XTEL is
   identical. Evidence: diff DOOR/XTEL in xEdit FO3/FNV vs FO4. Who: offline research.

### All interiors
5. **Can the interior pipeline take FO3/NV cells (no precombines, older lighting) with only a new reader in front?**
   fnv-to-fo4 got cells and objects across but dropped navmesh. Options: regenerate navmesh in the SF CK; convert
   NAVM; or ship without and fix by hand. Evidence: convert one small FO3 interior (Vault 101 entrance) end to end.
   Who: PC probe.
6. **How are FO3/NV lighting and materials (no BGSM, shader flags in NIF) mapped to Starfield .mat?** FO4 has BGSM; FO3
   does not. fnv-to-fo4 had to add material files. Evidence: read fnv-to-fo4's material handling in its GPL-3 source.
   Who: offline research.

### Launcher
7. **Does the launcher need TTW-style edition checks per game (English, all DLC, no Microsoft Store, run once)?**
   TTW's list is concrete (TTW guide intro). Options: require all DLC (one rule set); allow a base-only build; or
   allow per-DLC optional. Evidence: owner decision. Who: owner.
8. **How does the launcher detect and fingerprint FO3 GOTY, NV Ultimate and their store variants (GfWL, Epic, GOG)?**
   TTW lists supported variants and incompatibilities (German No Gore exe). Evidence: a hash table from TTW's
   installer docs, if public, or owner PCs. Who: offline research plus a PC probe.
9. **Can audio conversion run locally for FO3/NV voice, and is that legally different from what Capital Wasteland
   tried?** CW's extract-at-home plan "fell through" (PCGamesN), yet TTW "converts audio" locally (TTW FAQ). Why: voice
   is the bulk of story content (about 45,000 FO3 lines per DSOGaming). Options: local conversion (TTW model);
   subtitles only; or re-voice (CW). Who: owner, possibly a community contact on the TTW team.
10. **Is fnv-to-fo4 (GPL-3) a component we may reuse or learn from, and does its licence fit ours (GPL-3 notice for
    Mutagen already planned)?** Who: offline research plus owner.

### World and planet
11. **Where do the Capital Wasteland and the Mojave sit on our planet: true relative geography, or a stylised layout?**
    Real distances are about 3,350 km DC to Vegas and 630 km DC to Boston (computed). Options: real-geography landings;
    an abstract "regions" map; or separate planets (which breaks the "one Earth" premise but suits SF travel). Who: owner.
12. **How does the player travel between FO4, FO3 and NV worlds?** TTW uses a train at each end, gated by a quest.
    Options: a train scene; vertibird; a "travel menu" activator; or the SF ship (fenced out). Evidence: the
    vehicles-and-travel.md probe on cross-landing surface fast travel. Who: PC probe plus owner.
13. **Are Anchorage and Zeta separate sealed worldspaces (VR, orbit) that need no planet position?** Verified that they
    are a simulation and a spacecraft. Zeta could even use Starfield's space engine. Who: owner (fun option), offline
    research.
14. **What weather and climate model do the DC and Mojave landings use (green tint in FO3, desert in NV)?** Evidence:
    map FO3/NV CLMT/WTHR into SF biomes/weather. Who: offline research.
15. **How many landings, plugins and loaded worlds can one save carry before performance or plugin limits bite?**
    FO4 + FO3 + NV + 11 DLCs is about 15 source masters' worth of content. Evidence: PC stress test with terrain-only
    landings. Who: PC probe.

### People and story
16. **How are FO3/NV ObScript scripts turned into Papyrus: hand port, transpiler, or a quest-by-quest rewrite?**
    SCPT has SCTX source fields (xEdit). Options: a transpiler from SCTX to Papyrus with a shim library; a
    hand rewrite of quest logic on SF records (QUST stages, SPCH, AFFE); or a hybrid. Evidence: confirm SCTX is filled in
    the shipped ESMs; transpile ten varied scripts. Who: offline research plus a PC probe.
17. **What happens to creatures (CREA) and their behaviour, animations and skeletons?** FO4 has no CREA. Options:
    convert CREA to NPC_ + race; or substitute FO4/SF creatures (deathclaw, radroach and ghoul exist in FO4). Evidence:
    a map of FO3/NV creature types to FO4 races. Who: offline research.
18. **Do NPC companions carry across worlds (Dogmeat-FO3 with Dogmeat-FO4; ED-E; Boone in DC)?** TTW lets companions
    travel in-world; cross-world followers are unresolved. Who: owner plus a probe.
19. **How do faction relations cross worlds (Brotherhood in DC and in Boston; NCR only in the West)?** TTW did not
    carry faction relations (2014). Options: shared Brotherhood faction with a lore state; or separate factions per
    game. Who: owner.
20. **Does story state from one game affect another (FO3's ending, Broken Steel's fate, the BoS in FO4)?** Lore links
    exist (the BoS). Options: none (sandboxed games); light flags (dialogue variants); or deep (quests change). Who:
    owner.

### Fallout systems
21. **Whose rule set wins: FO4 SPECIAL and perks only, or a superset with skills, karma, reputation and DT?** TTW made
    NV's rules universal; F4NV restores skills and DT on FO4. Options: (a) FO4 rules everywhere, with FO3/NV skill
    checks converted to SPECIAL/perk checks; (b) a superset core; (c) a per-world rule swap (no precedent, likely
    confusing). Why: every dialogue condition (GetActorValue Speech >= 50), lock level and perk depends on it. Who:
    owner.
22. **If skills are dropped, how are FO3/NV skill checks (speech, lockpick, science, repair) remapped?** Conditions
    reference AVs 32-45. Options: map each to a SPECIAL threshold; map to perk ownership (FO4 style); or keep hidden
    skill AVs. Evidence: count of conditions per skill AV across FalloutNV.esm/Fallout3.esm. Who: offline research
    (xEdit script).
23. **Karma (FO3) vs reputation (NV) vs FO4 affinity: one alignment system or three?** Karma gates FO3 companions and
    spawns hit squads (fandom Karma). Reputation is per-faction REPU. FO4 uses companion affinity. Options: keep karma as
    a world-local AV plus REPU as factions plus affinity; or derive karma from affinity events. Who: owner.
24. **What is the unified level cap and XP curve?** FO3 20/30, NV (supported) 30 to 50, TTW 60 with one perk per
    level, FO4 uncapped. Options: uncapped FO4 curve with rebalanced XP per world; or TTW-style cap. Evidence: XP
    totals of a full FO3+NV run (TTW community). Who: owner plus offline research.
25. **How are FO3/NV bobbleheads, skill books and challenges handled?** TTW turned bobbleheads into mini perks. NV
    CHAL maps loosely to SF activity trackers. Who: offline research.
26. **Is NV hardcore mode (dehydration, hunger, sleep, healing over time, ammo weight) merged with FO4 Survival?**
    Records DEHY/HUNG/SLPD exist (xEdit). Options: one survival mode for all worlds; or per-world. Who: owner.
27. **How are VATS variants reconciled (FO3/NV pause-time VATS vs FO4 slow-time)?** One VATS on the core (vats.md).
    FO3/NV perks that modify VATS need entry point mapping. Who: offline research.
28. **What happens to NV weapon mods (IMOD), recipes (RCPE), ammo effects (AMEF), casinos and Caravan (CSNO, CCRD,
    CDCK, CHIP)?** These are NV-only record types (xEdit). Options: map IMOD to OMOD, RCPE to COBJ, AMEF to an
    OMOD/MGEF; casinos and Caravan rebuilt as mini-games or cut. Who: offline research plus owner.
29. **How are FO3's and NV's item lists and economies (caps, NCR dollars, Legion denarii) unified?** CMNY exists only in
    NV. Who: offline research.

### Release and community
30. **Should the TTW team be contacted before any FO3/NV work, and could they be partners?** They own the know-how and
    the Bethesda relationship history. Who: community contact (owner approves).
31. **Should FO3/NV support ship as a separate optional module of the launcher, so the FO4 build is unaffected if it
    is taken down?** Hosting friction is reported (fallout.wiki). Who: owner.
32. **Do we require all DLC for the multi-game build, like TTW, or allow base-only?** Same as Q7, from the release side
    (support burden). Who: owner.
33. **Fallout 1/2/Tactics and FO76: in or out?** ROADMAP says 1/2 would be hand-built recreations and FO76 is under its
    own terms. Suggest recording "out" for FO76 explicitly unless research finds an offline data path. Who: owner.

### Tooling and testing
34. **Is Mutagen's Fallout 3 support enough to read Fallout3.esm (and does it read FalloutNV.esm)?** The repo has a
    Fallout3 project, with maturity unknown and NV not named. Options: Mutagen FO3; our own reader from xEdit
    definitions; or xEdit scripts export. Evidence: load both masters with Mutagen and count unread subrecords. Who:
    offline research plus a PC probe.
35. **Does our NIF converter extend to bsver 34 (FO3/NV) cheaply?** nif.xml defines all versions (verified). FO3/NV
    use NiTriShape with BSShaderPPLightingProperty rather than BSTriShape plus BGSM (supported hypothesis). Evidence:
    convert three FO3 meshes (static, skinned, havok) through nifly or pynifly to SF. Who: offline research plus a
    probe.
36. **What is the acceptance test for "one playthrough": a route that starts in one world, travels, and keeps
    inventory, level and quest flags?** Evidence: a scripted route-run like our existing ones. Who: tooling design.

### Cross-cutting
37. **Should the core reserve namespaces now (editor id prefixes, script names, FormID ranges) for each game, so FO3,
    NV and FO4 content never clash?** The engine-mechanics notes already show name clashes are real. TTW pins load
    indices. Who: owner (decision log), offline research.
38. **Should actor values, factions and keywords on the core be named game-neutrally (for example `FO_Karma`,
    `FO_Skill_Speech`) even if FO4 does not use them, so later games plug in without a migration?** Cheap now. Who:
    owner.
39. **When is the go/no-go for multi-game: after FO4 is complete (ROADMAP order), or as an early spike to avoid design
    lock-in?** A 1-week spike (Q16, Q21, Q34, Q35) would expose core decisions early without building content. Who:
    owner.

## Corrections

- None found in the project notes read. One note for ROADMAP C3 build 2: "a second reader feeding the same pipeline"
  understates the work. Precedent (fnv-to-fo4) shows a reader gets the world across, but creatures, quests and
  scripts need a separate behaviour track, because ObScript and the hardcoded actor-value enum have no FO4/SF data
  counterpart. (supported hypothesis, from fnv-to-fo4's stated limits and xEdit layouts)
- TTW's level cap is **60** in current versions (ModPub, FAQ). Older forum answers saying 50 are out of date.

## Sources

- fallout.wiki, Mod:Tale of Two Wastelands: https://fallout.wiki/wiki/Mod:Tale_of_Two_Wastelands
- ModPub, Tale of Two Wastelands 3.4.0: https://mod.pub/ttw/133-tale-of-two-wastelands
- TTW installation guide FAQ: https://thebestoftimes.moddinglinked.com/faq.html
- TTW installation guide intro (requirements): https://thebestoftimes.moddinglinked.com/intro.html
- TTW installation guide index: https://thebestoftimes.moddinglinked.com/
- TTW forum index: https://www.taleoftwowastelands.com/
- TTW forum, max level: https://taleoftwowastelands.com/viewtopic.php@t=6908
- TTW forum, The Falcon / DT vs DR: https://taleoftwowastelands.com/viewtopic.php@t=1935
- Steam discussion (2014), TTW start and travel: https://steamcommunity.com/app/22380/discussions/0/522728813700378577
- Tropedia, Tale of Two Wastelands: https://tropedia.fandom.com/wiki/Tale_of_Two_Wastelands
- Bloody Disgusting, TTW 3.2 rebuild (2018): https://bloody-disgusting.com/video-games/3536003/fallout-new-vegas-mod-tale-two-wastelands-updated-total-rebuild/
- Insider Gaming, TTW will not port to remasters: https://insider-gaming.com/?p=170979
- PCGamesN, Capital Wasteland shut down: https://pcgamesn.com/fallout-4/fallout-4-fallout-3-capital-wasteland-mod
- PC Gamer, Capital Wasteland resumes: https://www.pcgamer.com/uk/capital-wasteland-the-fallout-3-remake-in-fallout-4-has-resumed-development/
- DSOGaming, Capital Wasteland back (2019): https://www.dsogaming.com/?p=121487
- Nexus Mods, Project Spotlight F4NV: https://www.nexusmods.com/dispatch/news/13916
- PCGamesN, New Vegas in Fallout 4 sandbox release: https://www.pcgamesn.com/fallout-4/new-vegas-mod
- Nexus Mods, FNV to FO4 (mod 75425): https://nexusmods.com/fallout4/mods/75425
- GitHub, terry-haire/fnv-to-fo4: https://github.com/terry-haire/fnv-to-fo4
- GitHub, Mutagen: https://github.com/Mutagen-Modding/Mutagen
- niftools nif.xml: https://raw.githubusercontent.com/niftools/nifxml/develop/nif.xml
- xEdit definitions (dev-4.1.6): https://raw.githubusercontent.com/TES5Edit/TES5Edit/dev-4.1.6/Core/wbDefinitionsFNV.pas and https://raw.githubusercontent.com/TES5Edit/TES5Edit/dev-4.1.6/Core/wbDefinitionsFO3.pas
- Wikipedia, Fallout 3 downloadable content: https://en.wikipedia.org/wiki/Fallout_3_downloadable_content
- Fallout Wiki (fandom), Karma (Fallout 3): https://fallout.fandom.com/wiki/Karma_(Fallout_3)
- Project files: docs/ROADMAP.md (C3), docs/measurements/fo4_esm.json, sf_esm.json;
  /mnt/project-files/research/engine-mechanics/README.md, special-perks-leveling.md, vehicles-and-travel.md,
  world-cells-navigation.md

Note: the shared web-search budget ran out during this research. Reputation thresholds (fame/infamy), NV's level-cap
steps, the BSA version number and current F4NV/Capital Wasteland status are therefore marked unresolved or supported
hypothesis, not verified.
