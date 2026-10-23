# Precedents: growing settlements and acting factions

Research worker note, 2026-10-19. Scope: what existing games and mods did for living settlements, faction
reputation, territory and connected regions, so the combined core builds on proven ideas and avoids known traps.

**Labels.** **verified** = the cited page states it (we have NOT tested it in game; a page's claim is not in-game
acceptance). **supported hypothesis** = our inference from cited facts. **unresolved** = we looked and found no source.
No game content, code or assets from any of these is planned for reuse; licences are recorded so nobody assumes otherwise.

---

## 1. Fallout 4 mods

### Sim Settlements 2 (SS2), Sim Settlements Team / kinggath
- **verified** Settlements can be built three ways: manual plots, a **City Plan** (builds over time, paid from the
  settlement economy) or a **Layout** (built at once, free). A Capital City is required for the Marketplace trade system.
  https://wiki.simsettlements2.com/gameplay/settlements
- **verified** City Plans level from L0 to L3. An upgrade needs population >= 80% of capacity, full food/water/defense
  bars, available virtual resources and enough days at enough happiness (L0->L1: 10 days at 70; L1->L2: 20 at 80;
  L2->L3: 30 at 90). Same page.
- **verified** Plot types: Residential, Industrial, Agricultural, Martial, Municipal, Commercial, Recreational. Each
  settler can have a home, a job and a hobby. Auto-assignment fills vacancies first, then resource deficits, then plot
  priority. Baseline of 1 food, 1 water and 1 sheltered bed per settler gives 80 happiness; recreation boosters
  lose effect as population grows; raids, deaths, disease, pollution and poor cleanliness lower happiness. Same page.
- **verified** Leaders: any settler can be Mayor, but Leader Traits need a "Leader Card" (vanilla/DLC companions and some
  unique settlers). The Mayor must live there and the player must own the settlement. Same page.
- **verified** Industries: industrial plots produce **virtual resources** (junk, then Building Materials, Organic
  Materials, Machine Parts, Rare Materials). Production plans consume inputs (example: the Crusher consumes Circuitry
  and Steel) and output goods for commercial shops. Surplus goes to local shops first, then **by caravan to the nearest
  connected settlement with room**, then onward by distance. Settler Strength boosts output.
  https://wiki.simsettlements2.com/gameplay/plots-and-plans/industrial
- **verified** Virtual Storage is a per-settlement inventory separate from the workbench, spendable only on building,
  upgrades and upkeep; donations cannot be taken back. Its stated purpose is a resource/cap sink so players do not
  pile up near-infinite resources. Settlements joined by **Caravan Supply Lines** pool virtual storage (own storage,
  then connected settlements, then workbench, then player inventory). A supply line stops if its Caravaneer plot is
  damaged in an unattended attack, unpaid, unstaffed, or the caravaneer is sick.
  https://wiki.simsettlements2.com/gameplay/basics/Virtual-Storage
- **verified** Chapters: the main quest ships in episodes; Chapter 2 (Gunner Outbreak) and Chapter 3 (Last Stand of the
  Commonwealth) are separate Nexus mods. Over 120 building plans, tagged by theme. https://www.nexusmods.com/fallout4/mods/47976
- **verified** Chapter 3 (reported 2023-08-02) adds an army against a Gunner invasion, alliances with existing factions
  and a new New Liberty Trading Company, multiple endings, and claiming almost any map spot to secure and patrol.
  https://www.gfinityesports.com/article/fallout-4-mod-sim-settlements-2-chapter-3-war
- **verified** War mechanics: settlements convert to **Outposts** (War Planner's Desk; only martial/municipal/residential/
  recreational plots). Soldier roles Warrior/Guard/Support/Patrol; daily auto-recruit of one soldier per outpost if
  beds allow. Assault types: Establish Outpost, Make Vassal, Liberate Settlement, Attack For Resources, Capture
  Territory. Almost any non-settlement location can become a **Territory** with a flag, a "Beneficiary" settlement and
  guard-based defense; higher defense makes enemy retaking less likely. **Vassals** pay daily supplies and need
  defenders from your empire. Assault results are scored against expectations (squad strength, enemy strength,
  casualties). https://wiki.simsettlements2.com/gameplay/War-Mechanics/
- **unresolved** How SS2 resolves battles at locations the player is not in. The War Mechanics page does not say.
- **Wasteland Reconstruction Kit, verified:** a build kit of "over 10,000 buildable items provided through Sim
  Settlements 2", including scripted objects (NPC spawners, guard patrol routes, navmesh blocks). Requires SS2 and
  Workshop Framework; no SS2-free version is planned, partly to keep file sizes small enough for Xbox sharing.
  Third-party items are used with their authors' permission.
  https://wiki.simsettlements2.com/customization/suggested-mods/wasteland-reconstruction-kit
- **Performance, verified:** a pinned FAQ on the mod page warns of "a lot of script lag" on lower-end CPUs or with many
  script/quest-heavy mods; users there report save-corruption warnings ("SS2 has detected an error"). These are user
  reports, not measurements. https://www.nexusmods.com/fallout4/mods/47976/?tab=posts
- **Performance, verified:** the SS2 known-issues page warns that settlement mods near Sanctuary "may put too much of a
  load on this already highly populated part of the map, causing script lag", that scrap mods break precombines,
  and that load order between Workshop Framework and the Unofficial Patch can stop City Plans building.
  https://wiki.simsettlements2.com/getting-started/known-issues and https://wiki.simsettlements2.com/gameplay/settlements
- **unresolved** Measured SS2 save-size growth. We found no source with numbers.
- **Licence, verified:** upload "not allowed ... under any circumstances"; modification needs permission; conversion to
  other games "not allowed ... under any circumstances"; asset use needs permission. https://www.nexusmods.com/fallout4/mods/47976
  -> We cannot copy or port SS2 code or assets. Design ideas only.

### Sim Settlements Conqueror (SS1 era)
- **verified** Option to "prestart the game with pre-built settlements run by NPCs for you to explore and Conquer";
  tagline "It's time to take the settlements to War." The fetched page was truncated. https://www.nexusmods.com/fallout4/mods/37000
- **unresolved** Its full feature list, author line and permission text (truncated in our fetch).

### Workshop Framework (WSFW), kinggath
- **verified** Adds settlement rules (Charisma-based recruit caps, bed caps, resource consumption, happiness-based loss
  of settlements), assignment controls, layout export/import, recovery tools, and a framework so other mods can
  change settlement features without overwriting vanilla files. A Max Threads option (10-50) trades speed for
  stability; persisting workshop resource objects is on by default to avoid unload issues.
  https://wiki.simsettlements2.com/gameplay/basics/workshop-framework
- **verified** Core workshop scripts are based on the Unofficial Fallout 4 Patch team's; 1000101 wrote the threading
  engine and locking. v1.0.5 added a random 0.10-0.50 s lock wait "to reduce deadlocks from many simultaneous calls";
  v1.1.5 warned extra draw/triangle queries "slow the thread". https://nexusmods.com/fallout4/mods/35004
- **Licence, verified (and mixed):** "You are not allowed to modify my files ... under any circumstances"; asset use
  needs permission. But author notes say "You are free to reuse sections of code found in this framework, so long as
  it does not interfere with this framework" and to credit contributors listed at the top of each script; do not
  release same-named scripts. https://nexusmods.com/fallout4/mods/35004
  -> **supported hypothesis:** small Papyrus code sections could be reused with credit, but our target is CE2/Starfield
  and the page does not reconcile this with its conversion ban. Ask the owner (and if needed kinggath) before reusing
  any line; default is write our own.

### Settlement Ambush Kit (Creation Club, Bethesda)
- **verified** Player-triggered "Endless Raids": a lure picks one enemy type, waves of 10 rounds with rising numbers and
  levels and a named boss per wave; a **morale** system based on clear speed and downed settlers can cost the
  settlement resources. https://fallout.fandom.com/wiki/Settlement_Ambush_Kit
- Licence: Bethesda paid content. Not reusable; design note only (player-chosen, opt-in pressure).

### War of the Commonwealth (WotC), Engager and Corey Carcano
- **verified** Reworked spawns across the map, faction vertibirds that hunt hostile groups after the airship arrives,
  rooftop and highway patrols, story factions joining settlement patrols, an optional system to reduce faction
  hostility to player settlements ("some conflicts remain"), and MCM spawn limiter and presets.
  https://www.nexusmods.com/fallout4/mods/12395?tab=logs
- **unresolved** WotC permission text (not in the fetched changelog tab).
- **verified** A 2016 Nexus forum request for a "Total War-like" strategic layer cites WotC's patrol spawning as the model;
  the only reply warns Fallout 4 rarely has more than ~6 people in one place, so scale down.
  https://forums.nexusmods.com/topic/5173335-mod-project-request-add-a-strategic-aspect-to-fallout-4

### Other faction / territory mods
- **Missions Committee, verified:** area-control missions (clear and hold a flag), ally with a faction such as the
  Minutemen, and "captured areas can be retaken by enemy factions". https://pcgamer.com/custom-quests-bring-huge-battles-to-fallout-4
- **Minutemen Takeover - Nuka World (hxhunter15), verified:** alternative end to "Open Season"; caps each gang at ~15 actors
  outside and 25 Minutemen active "to manage performance"; optional corpse removal with loot to a War Chest.
  Modification allowed with credit; conversion not allowed. https://www.nexusmods.com/fallout4/mods/30509
- **In the Shadow of the Valley (JamseySilence), verified:** four factions in a new valley with a New Vegas-style
  reputation system the author says "still has issues"; territory war is a stated goal, not shipped.
  https://nexusmods.com/fallout4/mods/28259
- **SKK Settlement Attack System, verified:** timer-driven attacks (+-20% jitter); attacker count from defense rating plus
  non-guard settlers, clamped 2-64; attack ends when hostiles unload outside the player's area or after a 30-minute
  failsafe. https://www.nexusmods.com/fallout4/articles/1597
- **Better Settlers (Thom293), verified:** 240+ settler NPCs added to levelled lists; "uses no scripts"; permission section
  is empty. https://nexusmods.com/fallout4/mods/4772
- **unresolved** A Fallout 4 mod that implements region-wide, dynamic faction territory with off-screen simulation. We
  found requests and partial systems (above) but no such mod page.

## 2. Fallout New Vegas, Fallout 3, Fallout 76

- **NV reputation, verified:** two independent scales per faction, **Fame** and **Infamy**, each 4 levels; the 4x4 grid
  yields named states (Accepted/Liked/Idolized, Shunned/Hated/Vilified, and mixed states like "Smiling Troublemaker",
  "Dark Hero"). Each change uses an editor tier 1-5 worth 1/2/4/7/12 points; per-faction thresholds.
  https://fallout-archive.fandom.com/wiki/Fallout:_New_Vegas_reputations
- **verified** Script functions `AddReputation`, `GetReputationThreshold` exist in the NV GECK.
  https://geck.uesp.net/wiki/AddReputation , https://geck.uesp.net/wiki/GetReputationThreshold
- **NV disguises, verified:** faction armor sets standing with that faction to Neutral; officers, guards and dogs see
  through it; enemies of that faction become hostile; only five major factions have disguises; a bug can leave
  standing un-restored after removing armor. Vilified triggers hit squads (NCR warns, then pursues after three days).
  https://fallout-archive.fandom.com/wiki/Fallout:_New_Vegas_reputations
- **NV endings, verified:** ordered slides: Dam outcome by winning faction, a Courier slide by winner plus karma, then
  faction/companion/location slides chosen by specific quest outcomes. https://fallout-archive.fandom.com/wiki/Fallout:_New_Vegas_endings
- **Fallout 3 karma, verified:** one global value starting at 0, shown as good/neutral/evil; reaching good karma ever
  makes Talon Company hostile, reaching evil ever makes Regulators hostile (latched); affects companions, dialogue,
  Three Dog broadcasts. https://fallout-archive.fandom.com/wiki/Karma
- **Fallout 76 public workshops (design note only), verified for 2018:** claim by clearing enemies and using the workbench;
  owned workshops are contested by other players; repeated enemy waves; resource collectors; claims last only while
  online. https://www.gameshedge.com/fallout-76-workshops-guide/ (dated Nov 2018; may have changed).

## 3. Starfield (our engine)

- **Cargo links, verified (guide):** need two outposts; cost 2 Zero Wire, 2 Beryllium, 12 Aluminum, 20 Iron; each link has
  outgoing and incoming containers; a cargo ship periodically moves goods both ways; a console switches destination.
  https://www.wepc.com/gaming/starfield-cargo-link/
- **Crew at outposts, verified (guide):** build a Crew Station (two crew per station), assign from the ship crew menu; the
  Outpost Management skill raises crew slots and cargo-link counts. https://www.rpgsite.net/feature/14837-starfield-how-to-assign-crew-to-outposts
- **Factions, verified (guide):** the four main factions can all be joined and "never acknowledge membership in a rival
  faction"; the page mentions no reputation meter. https://primagames.com/tips/does-your-faction-matter-in-starfield-answered
- **unresolved** Whether Starfield has a hidden per-faction reputation value in its data. Needs a Creation Kit / plugin check,
  not a guide.
- **Outpost raids, verified (guide):** raiders target outposts holding valuables in the Armillary; turrets and security
  robots defend. https://itemlevel.net/starfield-how-to-defend-your-outposts/
- **Mods, verified:** Galactic Colonies Expanse (TankGirl444) adds food production, livestock, biodomes, mechs/turrets;
  survival needs for working NPCs were *planned*, not shipped. https://www.pcgamesn.com/starfield/mod-city-builder
  Outpost Stats Enhanced (lxyman, 2026) raises build area to 200 and adds crew-capacity furniture; known issue: build
  page can spin. https://www.nexusmods.com/starfield/mods/17637 ZeeOgre's AIO Tweaks raises outpost radius to 250 m and
  baseline cargo links/crew stations/robots to 6 (permissive licence with credit). https://www.nexusmods.com/starfield/mods/10558
  Build Outposts in restricted zones (PeakTWCE) lets outposts include generic POIs; v1.2 fixed cargo-link and
  post-load interaction bugs. https://www.nexusmods.com/starfield/mods/4639
- **supported hypothesis** What these prove: plugins can change outpost limits, crew capacity and outpost placement, and
  the stock engine already ships an off-screen goods-transfer loop (cargo links) and crew-to-location assignment.
- **unresolved** A released Starfield mod with a true settler population (generic settlers living, working and
  needing things) or a faction-territory war. We found none.

## 4. Skyrim and other Bethesda

- **Skyrim Civil War, verified:** holds change via fort-capture quests or defeating the Jarl; the Jarl route can leave old
  guards and court in place ("Further bugs have also reportedly been triggered"); fort defenders sometimes fail to
  spawn and block the quest. Leftover data suggests a cut, more dynamic system (villages, sieges, counterattacks,
  losing a capital). https://app.uesp.net/wiki/Skyrim:Civil_War
- **The Second Great War (Reath), verified:** post-war sieges with reinforcement pools, a retaliation-chance slider,
  ownership shown via banners and shrine swaps, a debug menu to set each hold's owner "useful for fixing problems";
  incompatible with mods that edit forts/cities or move towns to own worldspaces; summon spells "may cause crashing".
  All rights reserved-style permissions. https://nexusmods.com/skyrim/mods/86075
- **Warzones Civil Unrest (MyGoodEye), verified:** battles from fixed spawn points (~3 per faction), randomized per
  playthrough, cooldowns, Performance Mode that skips spawns; the old "God of Warzones" helper script was "the main
  cause of save bloat" and was removed. Author forbids reuse "in ANY WAY, SHAPE or FORM" without permission.
  https://www.nexusmods.com/skyrim/mods/9494
- **OBIS, verified:** ~2,500 bandits in 57 gang types placed via levelled lists only ("None of these bandits are anywhere
  but in the level lists"); optional MCM clone-scanning with caps and cooldowns; mid-game install may need cell resets.
  Modification/conversion allowed with credit; asset use needs permission. https://www.nexusmods.com/skyrim/mods/31264/
- **unresolved** A survey of "Immersive" faction mods; not researched in this pass.

## 5. Non-Bethesda references (brief)

- **Mount & Blade (original), verified:** towns gain prosperity only when caravans from other towns arrive safely;
  villages lose prosperity to looting and bandit infestation; fiefs pay weekly taxes scaled by prosperity; kings reassign
  captured fiefs. https://strategywiki.org/wiki/Mount&Blade/Fiefs
- **Kenshi, verified:** attacking a faction makes you its enemy for a period; most factions have no way to repair relations;
  factions war on each other. https://kenshi.fandom.com/wiki/Faction
- **RimWorld, verified:** mood = base (set by difficulty) + summed moodlets; the bar moves toward the target at up to +12/h
  up, -8/h down; break risk below 35/20/5%. https://rimworldwiki.com/wiki/Mood
- **S.T.A.L.K.E.R. Anomaly, verified:** 1.7 announced A-Life factions taking and losing control points, camps and lairs,
  observable without player participation. https://en.gamegpu.com/news/igry/v-patche-1-7-dlya-s-t-a-l-k-e-r-poyavitsya-flangovyj-ii-i-dinamicheskaya-borba-za-territorii
- **unresolved** Anomaly's "Warfare" mode rules in detail (no primary source fetched).

## 6. Engine pitfalls seen in these projects

- **verified** Papyrus persistence: references held by properties are "permanently persistent"; variables, running
  functions and event registrations keep refs alive; persistent refs cost CPU and memory. Use `DumpPapyrusPersistenceInfo`
  (it does not see alias-held persistence). https://falloutck.uesp.net/wiki/Persistence_(Papyrus)
- **verified** Save bloat (Skyrim community): attributed to stuck references and unattached script instances; ends in
  infinite loads / CTD; cleaners treat symptoms, one moderator argues needing them means an unstable list. User reports,
  not measurements. https://stepmodifications.org/forum/topic/5853-save-bloat-what-is-it-why-does-it-cause-ctd-why-does-this-fix-it/
- **verified** A single always-on helper script was Warzones' main save-bloat source (above).
- **verified** Script lag from heavy settlement scripting and dense map areas (SS2 FAQ and known issues, above).
- **verified** Lock contention / deadlocks with many simultaneous workshop calls (WSFW changelog, above).
- **verified** Actor-count caps are used to keep battles playable (Minutemen Takeover ~15+25; SKK clamp 2-64; Warzones
  Performance Mode). Pages above.
- **verified** Territory/quest state can desync from the world (Skyrim Jarl route leaving old guards; Second Great War
  shipping a debug owner-setter). Pages above.
- **unresolved** Fallout 4 vanilla behaviour for attacks on unloaded settlements; the pages we fetched do not say.
- **unresolved** Whether CE2 (Starfield) Papyrus has the same persistence and save-growth behaviour. Plausible
  (same language family) but untested by us: treat as a **supported hypothesis** at most, and measure.

---

## What this means for us

1. **Simulate settlements as data, render them as actors only when loaded.** SS2's virtual storage and pooled supply
   lines, Mount & Blade's prosperity and Starfield's own cargo links all run economy off-screen without actors.
   Keep per-settlement state in a small record, not in live references. (supported hypothesis from §1, §3, §5)
2. **Supply lines are first-class and breakable.** SS2 lines stop when the caravaneer plot is damaged, unpaid, unstaffed
   or sick; M&B towns grow only when caravans arrive. That is our "events in one region felt in another" hook.
3. **Growth gated by sustained needs over time**, like SS2 levels (days at a happiness floor) and RimWorld's mood target
   that moves slowly. Use rates, not instant thresholds, so one bad raid dents but does not wipe a town.
4. **Two-axis reputation per faction (NV fame/infamy)** beats one karma number: it lets the player be feared and liked,
   and mixed states drive unique dialogue. Keep FO3's lesson that latched states (Talon/Regulators) are easy to reason about.
5. **Disguises need explicit limits** (NV: officers and dogs see through; bug when removing armor). If we add them,
   specify who is fooled and test the remove path.
6. **Territory needs a single source of truth plus a repair tool.** Skyrim's civil war desynced; The Second Great War
   shipped a debug owner-setter. Plan an owner table, an idempotent "apply owner to world" step, and a console fix-up.
7. **Cap actors and spawn by budget.** Every working faction-war mod caps live combatants. Resolve off-screen fights
   numerically (SS2-style expectation scoring is a good model) and only spawn the fight the player can see.
8. **No always-running global scripts.** Warzones' helper caused save bloat; WSFW needed lock jitter. Prefer event-driven,
   time-sliced updates; clear references; never put world refs in properties.
9. **Player-controlled pressure has a place.** Settlement Ambush Kit lets players opt into raids; SKK makes attacks
   tunable. Expose difficulty and frequency for faction pressure.
10. **Build on Starfield's outpost/crew/cargo systems before inventing new ones** (§3); mods already show limits are
    data-editable. Measure first, then extend.
11. **Write our own code.** SS2, Warzones, Second Great War and most others forbid modification or conversion. Only WSFW
    states a code-reuse allowance, with ambiguity; ask the owner before using even that.
12. **Measure save growth from day one.** No source gives numbers for SS2-scale bloat; we should record save size and
    script load per in-game week in docs/ai/optimization.md style.

### Gaps (unresolved, worth a follow-up)
- Starfield faction data: is there any hidden reputation/standing form usable for NV-style fame/infamy? (CK check)
- Off-screen battle resolution in SS2 and vanilla FO4 settlement attacks: no primary source found.
- Measured CE2 Papyrus persistence and save growth with many outposts.
- No released Starfield mod with real settler populations or faction wars; we would be first, so budget for unknowns.
- Anomaly Warfare mode rules; Skyrim "Immersive" faction mods; WotC and Conqueror permission text.
