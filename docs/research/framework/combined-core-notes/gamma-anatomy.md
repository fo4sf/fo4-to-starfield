# S.T.A.L.K.E.R. GAMMA: what it is, how it works, lessons for a Fallout combined core

Author: Claude (research worker), 2026-10-19. Status: desk research, web sources only; nothing tested in-game.
Labels: **V** = verified (read in the linked source), **H** = supported hypothesis (my inference from sources), **U** = unresolved.
Where sources disagree, both are given.

Short source keys (full URLs):
- [README] https://github.com/Grokitach/Stalker_GAMMA (GAMMA repo README, read 2026-10-19)
- [PATCH] https://github.com/Grokitach/Stalker_GAMMA/blob/main/Patchnotes.md
- [GOG-ANOM] https://www.gog.com/en/game/stalker_anomaly
- [GOG-OCM] https://www.gog.com/news/stalker_anomaly_gmdx_realrtcw_and_more_join_gog_oneclick_mods
- [MODDB-ANOM] https://www.moddb.com/mods/stalker-anomaly
- [ANOM151] https://www.moddb.com/news/stalker-anomaly-version-151-release
- [ANOMB3] https://www.moddb.com/news/stalker-anomaly-150-beta-30-is-here
- [DSO-ANOM] https://www.dsogaming.com/news/free-standalone-mod-s-t-a-l-k-e-r-anomaly-beta-1-5-available-for-download-uses-xray-monolith-engine/
- [WARFARE-OVH] https://www.moddb.com/mods/stalker-anomaly/addons/warfare-alife-overhaul
- [GD-ALIFE] https://gamedeveloper.com/design/a-life-an-insight-into-ambitious-ai
- [DEVUA] https://dev.ua/en/news/stalker-gamma-v-gog-1764754258
- [MEZHA] https://mezha.ua/en/news/stalker-gamma-out-on-gog-306717/amp/
- [ITC] https://itc.ua/news/v-gog-dobavyly-s-t-a-l-k-e-r-g-a-m-m-a-teper-mod-mozhno-ustanovyt-v-odyn-klyk/amp/
- [GOL] https://www.gamingonlinux.com/2025/12/gog-add-stalker-gamma-as-a-one-click-mod-install/page=1
- [PCGH] https://www.pcgameshardware.de/Stalker-2-Spiel-34596/News/Gamma-Mod-Release-Survival-Overhaul-1488234/
- [GP] https://www.gamepressure.com/download/stalker-call-of-pripyat-stalker-gamma-v09-mod/zd1424b
- [DTF] https://dtf.ru/5257372-stalker-gamma-plyusy-i-minusy-da-da-net-net (Russian player review)
- [R093] r/stalker "GAMMA 0.9.3 release" thread (Dec 2024), read via mirror: https://pol1.lr.ggtyler.dev/r/stalker/comments/1h3ylar/gamma_093_release/ (comment ids cited inline)
- [MODDB-CF] https://www.moddb.com/forum/thread/cli-installer-hitting-cloudflare-challenge

---

## 1. What GAMMA is

| Fact | Label | Source |
|---|---|---|
| Name: "Grok's Automated Modular Modpack for Anomaly". GamingOnLinux quotes the site as "Gigantic Automated Modular Modpack", so the expansion varies. | V (both forms seen) | [README], [DEVUA], [GOL] |
| Led by Grokitach (repo owner; credited as author). | V | [README], [GP] |
| Base game is S.T.A.L.K.E.R. Anomaly: a free standalone mod (originally for Call of Pripyat, built on the Last Day mod), running on "Monolith 64-bit engine, a custom fork of the X-Ray engine". | V | [DSO-ANOM], [MODDB-ANOM] |
| Anomaly ships 32 maps from the series, with Story, Sandbox and Warfare modes. | V | [GOG-ANOM] |
| Anomaly is credited to "Anomaly Developers"; it is fan-made and not a GSC product. | V | [MODDB-ANOM], [GOG-ANOM] |
| Size of the pack: GOG says "over 400 carefully selected mods" plus 100+ additional elements. An older (v0.9) install guide says about 380 mods in MO2. | V | [DEVUA], [MEZHA], [GP] |
| Install model (classic route): unpack Anomaly, then run the GAMMA launcher. It sets up a Mod Organizer 2 instance and "downloads every add-on directly from moddb or github, and installs them automatically". In MO2 each addon links back to its ModDB page. | V | [README], [GP] |
| Support and in-depth install guide are on Discord (discord.gg/stalker-gamma); the wiki guide is shorter. | V | [README] |
| GOG One-click Mod: GAMMA went live on GOG about 1-2 Dec 2025. It is free, needs an owned base game (CoP per Mezha; a GoL reader quotes "CoP Enhanced or S.T.A.L.K.E.R. 2"), and needs 130 GB of storage. Anomaly itself joined One-click Mods on 2 Sept 2025. | V (date, free, 130 GB, CoP); H (exact ownership list) | [GOL], [MEZHA], [ITC], [GOG-OCM] |
| The README says the original games "are not needed to play GAMMA" by the non-GOG route. | V | [README] |
| Repo licence is AGPL-3.0; about 6.7k commits; current badges show GAMMA v0.9.5 and launcher v8.6. | V | [README] |
| Update cadence: "updates happen quite often". Named major releases are 0.9.1 ("2nd Anniversary", engine 2023.11), 0.9.3 ("3rd Anniversary", Dec 2024), 0.9.4 (engine 2025.7) and 0.9.5 (engine 2026.5). That suggests one big release a year plus a rolling git update stream. | V (releases); H (annual rhythm) | [README], [PATCH], [R093] |
| First public release was around late 2021, inferred from "3rd Anniversary" being Dec 2024. | H | [PATCH], [R093] |
| Save-compatibility policy: not stated in the README or patch notes. A Reddit user says GAMMA must be installed onto a clean Anomaly (lzx04j7). | U (policy); V (that comment) | [README], [PATCH], [R093] |

## 2. Systems, in concrete terms

### 2.1 Economy and traders
- GAMMA removes weapon and armor trading: you cannot buy or sell them. **V** [README]
- Traders sell attachments, ammo, food and medicine, and their stock depends on reputation. **V** (player review) [DTF]; "Supply Tier" stock gating appears in the patch notes (for example, "Ecologs sell Gauss Ammo at Supply Tier 4"). **V** [PATCH]
- Anti-farming rules: specialised traders blacklist ammo and attachments "to limit money farming". Traders buy items above 5% condition (previously 50%). **V** [PATCH]
- 0.9.5 adds a "trading_computer" that reaches allied traders within a 150 m radius. **V** [PATCH]
- "Removes random stash loot"; good gear is tied to dangerous areas and longer runs. **V** [README], [PCGH]
- Money comes mainly from tasks: one player says tasks are "so much more currency-efficient" than artifact selling (lzvat9r). **V** (player claim) [R093]

### 2.2 Degradation, repair, crafting (parts)
- Anomaly base: "Weapons jam. Armor fails"; you can fix gear, cook and craft ammo from scavenged materials. **V** [GOG-ANOM]
- GAMMA: gear taken from enemies must be repaired with repair kits, and the kits are crafted using toolkits. Toolkits come from rare stashes unlocked by completing maps. **V** [README]
- Guns with green barrels deal full damage and need only a few good parts to stop jamming. **V** [README]
- 0.9.3 dropped %-based gun condition. Parts at or above 60% condition are restored with cleaning kits and parts below that need repair kits; old tools became crafting ingredients. **V** [PATCH], [R093 lzur74b]
- Mechanics do not repair guns for you; tools come in three tiers. **V** (player review) [DTF]
- 0.9.5 adds an armor overhaul and a new upgrade system. Exo repair kit recipes are drop-only (0.9.1). **V** [PATCH]

### 2.3 Healing and body health
- Damage is tracked per body part. You heal with first-aid kits, bandages or stimpacks, then need follow-up drugs (antibiotics, antidotes, painkillers, anti-inflammatories). **V** [README]
- Bleeding, pain, infection and radiation interact, and treating them needs planning. **V** [DEVUA], [PCGH]
- Bandages reduce bleeding over time, so tourniquets matter (0.9.3). Bleed chance went up in 0.9.4. **V** [PATCH]

### 2.4 A-Life (offline simulation)
- Vanilla A-Life: AI within about 150 m runs "online" in full detail. Beyond that, an "offline" simulation keeps moving NPCs and monsters on a graph as game time passes. Smart terrains apply behaviour rules to AI that enter them. **V** [GD-ALIFE]
- Anomaly: "Stalkers travel more often and report their activity in other parts of the Zone". It also has dynamic anomalies and mutants, NPC trading and upgrading, paid escorts, bribes that pause a hostile faction, and disguise, rank and reputation. **V** [ANOM151]
- GAMMA tunes population (stalker pop 0.45 -> 0.55). The south empties and the north fills as the story progresses. Faction relations change (Clear Sky vs Duty hostile in 0.9.5). **V** [PATCH]
- "Dynamic news" as a named PDA feed: the sources I read only say stalkers "report their activity". The exact news system was not confirmed. **U** [ANOM151]

### 2.5 Warfare mode (Anomaly)
- Warfare is a game mode where "factions fight for influence and control of zone areas". You join a faction; "bases can fall and frontlines shift". **V** [MODDB-ANOM], [GOG-ANOM]
- Mechanics (Beta 3.0): the player controls their faction at runtime and picks dynamic or manual expansion. An **offline combat simulator** lets squads intercept each other, and a PDA tab tracks faction progress. **V** [ANOMB3]
- Point types, from a Warfare overhaul addon describing the system: **bases** (housing, emission cover, defensibility), **resource points** (one per anomaly field), **territories**, and **lairs** where mutants spawn.
  - A single squad can capture a non-base point. A base needs more of your squads present than theirs.
  - Respawn time depends on how many bases a faction controls.
  - Squads move between points to build invasion forces, and the player is notified of points that need reinforcement.
  - **V** for the addon's model [WARFARE-OVH]; **H** that vanilla Warfare matches it in detail.

### 2.6 Tasks, artifacts, stashes, survival needs, stealth
- Tasks: storylines, faction questlines and many repeatable tasks. Most show target info before you accept. **V** [ANOM151]
- Criticism: most tasks are radiant ("bring 10 bandit patches") and pay only money. **V** (player review) [DTF]
- Artifacts are usable right away but must be "empowered by combining artefacts". Tiers T0-T3 add artifact and mutant-part costs; recipe books are priced items. **V** [README], [PATCH]
- Stashes: no random stash loot. Toolkits come from rare stashes. **V** [README]
- Survival needs (Anomaly base): hunger, thirst, stamina, sleep, radiation. **V** [GOG-ANOM]
- GAMMA adds food spoilage (raw meat 4 days, cooked 10; a fridge stops decay) and shows satiety, thirst and sleep values as percentages. **V** [PATCH]
- Stealth: Anomaly has a disguise system. GAMMA makes NPCs see through disguises more easily, gives subsonic ammo a stealth bonus, and tunes bush transparency. **V** [ANOM151], [PATCH]

### 2.7 Progression and "GAMMA philosophy"
- Stated aims: a balanced "survival, scavenging, cooking, crafting and repairing experience" with "a meaningful and enjoyable sense of progression". "The more to the north you go, the more dangerous the Zone is" (and the better the rewards). The north is locked behind story beats (Miracle Machine, Brain Scorcher). **V** [README]
- The release post warns that GAMMA "will punish the ignorant and uninformed" (R093 OP). **V**
- "Hard but fair / every item matters": this exact wording was not found in a primary source. The design intent it describes is supported by the scarcity rules above. **H**
- Modular: difficulty presets, faction options and curated progression paths. Configure in-game through MCM, or toggle mods in MO2. **V** [GOL], [ITC]

## 3. Reception

| Theme | What people say | Label | Source |
|---|---|---|---|
| Progression and purpose | GAMMA "solves... the biggest issue with the sandbox nature of Anomaly - which is a lack of progression, direction & purpose"; "a struggle up the loot ladder". | V | [R093 lzw9ic3] |
| Difficulty | Praised as "excellent" on Master: "no place that is 100% safe". Others call starting there "masochist" and compare it to a full sim. | V | [DTF], [R093 lzz6h1f] |
| Grind and economy | Artifact hunting "never... worth it"; tasks are far more lucrative. The 0.9.3 repair simplification was welcomed as "much more player friendly", while others found it "overly simple". | V | [R093 lzvat9r, lzur74b] |
| Quest depth | Repetitive radiant tasks; tired main storylines; some maps (Jupiter, Zaton) lose tension late. | V (one reviewer) | [DTF] |
| Install friction | Before GOG it was "complicated"/"tricky". Users downloaded 10+ GB of Anomaly plus a 10+ GB installer, with installs "going for 5 hours". "follow discord install method, otherwise in for a headache". ModDB Cloudflare challenges block automated download tools (Aug 2026). Linux needs community launchers; the GOG build reportedly fails under Heroic. Others call it easy, about an hour mostly automated. | V | [GOL], [R093 lzyl2s7, m2p5wzm], [MODDB-CF], [GP], https://steamcommunity.com/app/4500/discussions/0/4631484492942496120 |
| Performance and stability | One reviewer: crashes 1-2 times per 2 hours, FPS spikes from 120 to 5, micro-freezes even on top hardware. GOG recommends an RTX 3060 / 16 GB RAM and 130 GB of disk. | V (single reviewer); breadth of this complaint **U** | [DTF], [ITC] |
| Emergent stories | I found no primary source for this. It is commonly asserted, but none of the sources I read describe a specific emergent story. | U | none |

## 4. How GAMMA is assembled legally (relevant to "ship no assets")
- The README says "This modpack is 100% copyright free since it redistributes little to no copyrighted content developed by other modders". It also says it is "not an official product of GSC Game World and is a derivative work". **V** [README]
- Fetch from origin: the launcher downloads each addon from its ModDB or GitHub page, and MO2 keeps a "visit moddb.com" link per addon. Installing therefore counts downloads for, and "directly support[s]", the original modders. **V** [README]
- Reuse terms: free to use and repost "as long as the source is indicated (original addon author, from Stalker GAMMA)". For "numbered addons (105-)", the original authors must be contacted first. Reposting unmodified parts is discouraged; link to the repo instead. **V** [README]
- The pack's own glue (configs, patches, launcher) lives in an AGPL-3.0 git repo, and updates are delivered as git and download diffs. **V** (licence); **H** (the delivery detail is inferred from the "automatically updated" goal) [README]
- The base engine fork is distributed free by fans. On GOG, both Anomaly and GAMMA are tied to owning a GSC base game. **V** [GOG-ANOM], [MEZHA]
- Fragility: origin-host fetching depends on third parties. ModDB bot detection and Cloudflare challenges break installs, and the old guide suggested waiting or using a VPN. **V** [GP], [MODDB-CF]
- Any permission agreements between GOG and the addon authors are not described in any source I read. **U**

**Fit to our model (H):** GAMMA's pattern of a manifest plus fetch from origin plus a local mod manager plus a per-addon credit link lines up with our "built on the player's PC, ship nothing of Bethesda's" rule. Our version differs in that the *source* is the player's own FO4/Starfield install, not third-party hosts. The main lesson is the failure mode: any third-party fetch needs caching, mirrors that are allowed by licence, and clear errors.

## 5. Lessons for a Fallout combined core

Tag key: **[S]** = survival-centric (owner: one layer only, should be optional or tunable); **[C]** = core (settlements, factions, connected world).

| GAMMA pillar | Fallout equivalent | Tag | Basis |
|---|---|---|---|
| Warfare point types (base / resource / territory / lair) and capture rules | Every settlement and location gets a type. **Settlement = base** (beds, defense, shelter), **resource** (water, scrap, farms, power), **territory** (roads, chokepoints), **lair** (creatures). A faction captures a territory with one patrol; a settlement needs more of its squads present than the defenders have. | [C] | [WARFARE-OVH] V; mapping H |
| Respawn rate scales with bases held | Faction strength comes from settlements held. Losing Sanctuary-style hubs slows a faction's patrol replenishment, which gives a natural snowball and rubber-band lever. | [C] | [WARFARE-OVH] V; mapping H |
| Offline A-Life plus offline combat simulator | Faction patrols and caravans move on an off-screen graph between locations and resolve fights statistically while unloaded. The player arrives to the aftermath. | [C] | [GD-ALIFE], [ANOMB3] V; mapping H |
| NPCs "report their activity", PDA faction tab | A Pip-Boy feed and radio bulletins of off-screen events: "Raiders took the Red Rocket", "Minutemen relieved Abernathy". Without this the offline sim is invisible. | [C] | [ANOM151] V; Fallout mapping H |
| Player-directed expansion (dynamic or manual) and reinforcement notices | General-style orders: pick the next target settlement, get "needs reinforcement" alerts. This replaces the static vanilla "settlement needs your help" radiant quest. | [C] | [ANOMB3], [WARFARE-OVH] V; mapping H |
| Trader economy: no gun/armor sales, supply tiers, anti-farm blacklists, trading computer (150 m) | **Settlement supply lines:** what a vendor stocks depends on which settlements and resources its faction holds (supply tier = territory). Cut a supply line and stock drops. Use a relay terminal instead of a 150 m trading computer. Keep the anti-farm rule (vendors refuse junk loops). | [C] | [PATCH], [README] V; mapping H |
| Danger and loot gradient (north = harder = better), story-gated north | Regional tiers (Sanctuary to the Glowing Sea). Good gear lives in dangerous regions and sites tied to story progress, not in shops. | [C] | [README] V |
| No random stash loot; toolkits in rare stashes | Curated caches tied to locations and faction control, not random. Keep the key crafting tools rare. | [C] | [README] V |
| Population shifts with progress | Faction presence redistributes as the story advances (for example, Institute or BoS escalation moves patrol density). | [C] | [PATCH] V; mapping H |
| Weapon/armor parts degradation, cleaning vs repair kits | Light-touch condition plus kits, tied to settlement workbenches. Repair capacity is a settlement service, which links it back to the core. | [S]/[C] hybrid | [README], [PATCH] V |
| Body-part medical chain, bleeding/infection | Optional survival layer: limb damage plus treatment items. | [S] | [README] V |
| Hunger/thirst/sleep, spoilage, fridge | Optional survival layer. Spoilage and fridges can feed settlement food logistics, so it is [C]-adjacent. | [S] | [GOG-ANOM], [PATCH] V |
| Artifact empowerment | Legendary-mod or rare-component upgrades with long-term growth instead of instant power. | [C]-neutral | [README] V |
| Modular presets plus MCM plus mod-manager toggles | Every system has an on/off switch and presets ("Settlements and Factions", "+ Survival"). Survival defaults to a preset, not mandatory. | [C] | [GOL] V |
| Annual major release plus rolling updates; save policy unclear | Publish an explicit save-compatibility contract per release. GAMMA's lack of one is a gap to avoid. | [C] | [PATCH] V, policy U |

Anti-lessons from the complaints (H, built on the V quotes in section 3):
1. Radiant tasks that pay only money get called repetitive. Faction tasks should change territory or supply state.
2. Make income sources pay comparably, or players converge on the single best farm.
3. Install friction was the #1 barrier before GOG. One-click and deterministic builds matter more than features.
4. Big open late-game maps lose tension. Faction pressure should scale with player power.
5. Stutter or crashes in an always-on simulation: budget off-screen ticks. CE2 cost is **U** until measured.

## Gaps (unresolved)
1. GAMMA's official save-compatibility policy per update (not in the README or patch notes; Discord likely, but unread).
2. The exact current addon count. The modlist API (stalker-gamma.com/api/list) was blocked from this session; sources say "400+" (GOG) and about 380 (older guide).
3. The vanilla Anomaly Warfare capture formulas. Section 2.5's detail comes from an overhaul addon page.
4. Whether Anomaly has a named "dynamic news" PDA system, and how it works.
5. Primary-source accounts of emergent stories; GOG user reviews and ratings (the GOG GAMMA page failed to load).
6. How widespread the performance and crash complaints are (one detailed reviewer only).
7. GOG's permission arrangements with GAMMA's addon authors.
8. GAMMA's first release date (inferred late 2021) and the exact GOG ownership list (CoP vs CoP-EE vs S2).
