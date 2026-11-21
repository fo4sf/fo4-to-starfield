Titles: All 7 Fallout titles (FO4, FO3, FNV, FO1, FO2, Tactics, FO76) + Standalone Starfield A-Life SDK | Modes: Story & Warfare (+ Survival hardcore layer) | Track: Track 2 (experimental core, stacked on #841) — prototype, offline

# A-Life: Better Methods Research & Scored-Orders Offline Prototype (`X7`)

> **Status:** **Prototype, offline (no game launch, no new Papyrus runtime behavior pushed as done, defaults unchanged).** The `order_mode: "scored"` implementation lives strictly in the offline SDK simulator (`src/fo4sf/alife/sim_math.py`, `src/fo4sf/alife/schema.py`, `scripts/alife/build_alife_mod.py`) with `order_mode` defaulting to `"random"` so every existing config behaves identically. Items `2`–`5` are **design only**.
>
> **Scope Context:** Our current two-tier A-Life design (offline navigation graph + `450 m / 620 m` hysteresis 3D materialization bubble in `FO4SF_ALifeSimQuest.psc` and `src/fo4sf/alife/sim_math.py`) already mirrors GSC Game World's *S.T.A.L.K.E.R.* A-Life offline/online LOD architecture ([Game Developer interview with Dmitriy Iassenev](https://www.gamedeveloper.com/game-platforms/interview-inside-the-ai-of-i-s-t-a-l-k-e-r-i-)). This note evaluates five targeted upgrades against real 30-seed offline simulator measurements and Starfield's Papyrus constraints.

---

## 1. Scored Orders Instead of the 40 / 30 / 30 Dice (Offline Prototype)

### Motivation & Prior Art
In `#841`, a garrisoned squad finishes its `45..75 s` dwell and rolls a fixed **`40%` Raid / `30%` Reinforce / `30%` Patrol** die: Raid always targets the nearest hostile/unowned node regardless of garrison strength, Reinforce targets the nearest non-full own node regardless of threat, and Patrol picks uniformly across the whole graph.

*Mount & Blade II: Bannerlord*'s campaign AI instead scores candidate actions against party needs, target value, defender strength, and travel distance ([TaleWorlds Dev Blog — Campaign AI](https://www.taleworlds.com/en/News/273)). Note that while community mods and internal engine editors discuss spatial heat maps / influence maps, we did **not** find a published TaleWorlds dev blog documenting a campaign-layer heat map mechanic (see Section 6).

### Prototype Implementation (`order_mode: "random" | "scored"`)
- **Config key (`src/fo4sf/alife/schema.py`):** `simulation.order_mode`, valid values `"random"` | `"scored"`, **default `"random"`** (existing configs produce bit-for-bit identical output).
- **CLI override:** `python -m fo4sf.alife.sim_math <config> --order-mode scored` and `python scripts/alife/build_alife_mod.py simulate --config <config> --order-mode scored`.
- **Scoring model (`src/fo4sf/alife/sim_math.py:give_order_scored`):** Evaluates every reachable node `i != src` (`cap[i] > 0`) on a common utility scale divided by `dist_cost = 1 + dist / mean_edge_len`, with `±10%` deterministic RNG jitter for multi-seed variety:
  1. **`raid`** (hostile-owned or unowned capturable): weighs **enemy weakness** `s.strength / (s.strength + enemy_str[i] + 0.5 * power)`, **squad readiness** (`0.25 + 0.75 * hp_frac`), **node kind value** (`base > checkpoint > resource > lair`, `+0.30` unowned bonus), **frontline adjacency** (`1.25x` adjacent to own node vs. `0.80x` deep behind lines), **inbound spread** (`0.70 ** friendly_in[i]`), **overextension dampening** (`max(0.50, 1.15 - 0.85 * own_share)`), and a `0.65x` penalty for abandoning an exposed sole-garrisoned own node.
  2. **`reinforce`** (own node with free capacity): weighs **own garrison gap** `(cap - occ - friendly_in) / cap`, **frontline & inbound threat** (`0.75 + 0.50 * adj_hostile + 1.35 * hostile_in[i]`), empty own-base defense (`+0.75`), and **wounded-squad base replenishment pull** (`+1.35 * (1 - hp_frac)` when `hp_frac < 0.85` at an own `base`).
  3. **`patrol`** (nearby border, unowned non-capturable `lair`/`resource`, or low-occupancy nodes): `0.90 * border_mult * free_ratio * (0.75 ** occ_plus_in) / dist_cost`, keeping scouts active near borders instead of marching across the entire map.
  4. **Hold-at-base guard:** A sole or battered defender at an exposed own `base` / `checkpoint` may choose to hold and re-dwell instead of deserting its post.

### 30-Seed Offline Benchmark (`seeds 1..30`, `sim_math.benchmark_order_modes`)

Measured deterministically across **30 seeds** (`>= 20` required) on both shipped presets at `1,000` ticks (`33.3` sim-min) and `2,500` ticks (`83.3` sim-min):

| Preset & Horizon | Mode | Mean Captures | Mean Flip-Flops | Mean Battles | Mean Replenishes | Garrison Util. | Mean Early Max Share (`T/2`) | Mean Final Max Share (`T`) | Early Dom `>=75%` (`/30`) | Final Dom `>=75%` (`/30`) | Factions Surviving | Order Split (`R / Rf / P`, 30-seed sum) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| **`fo4sf_commonwealth`** (`1,000` ticks) | `random` | `9.60` | `3.57` | `8.13` | `6.13` | `3.85%` | `41.6%` | `45.0%` | `0` | `0` | `3.00` | `679 / 462 / 483` |
| **`fo4sf_commonwealth`** (`1,000` ticks) | `scored` | `8.03` | **`2.30`** (`-35.6%`) | `5.97` | **`13.67`** (`2.23x`) | **`9.48%`** (`2.46x`) | `41.4%` | **`42.6%`** | `0` | `0` | `3.00` | `669 / 997 / 313` |
| **`fo4sf_commonwealth`** (`2,500` ticks) | `random` | `16.73` | `9.73` | `13.53` | `13.33` | `3.64%` | `47.0%` | `55.1%` | `0` | `1` | `2.97` | `1574 / 1117 / 1202` |
| **`fo4sf_commonwealth`** (`2,500` ticks) | `scored` | `10.87` | **`4.97`** (`-48.9%`) | `8.27` | **`17.43`** (`1.31x`) | **`10.07%`** (`2.77x`) | **`43.3%`** | **`44.5%`** | `0` | **`0`** | **`3.00`** | `1589 / 2848 / 1186` |
| **`vanilla_new_atlantis`** (`1,000` ticks) | `random` | `10.50` | `4.97` | `21.50` | `5.33` | `7.60%` | `51.3%` | `55.1%` | `1` | `2` | `3.00` | `797 / 425 / 662` |
| **`vanilla_new_atlantis`** (`1,000` ticks) | `scored` | `8.93` | **`4.33`** (`-12.9%`) | `17.63` | **`25.33`** (`4.75x`) | **`12.60%`** (`1.66x`) | `55.9%` | `58.9%` | `3` | `7` | `3.00` | `637 / 1426 / 137` |
| **`vanilla_new_atlantis`** (`2,500` ticks) | `random` | `20.27` | `13.77` | `36.53` | `12.67` | `7.31%` | `59.4%` | `72.3%` | `5` | `21` | `3.00` | `1854 / 1172 / 1532` |
| **`vanilla_new_atlantis`** (`2,500` ticks) | `scored` | `12.27` | **`7.03`** (`-48.9%`) | `23.80` | **`39.73`** (`3.14x`) | **`13.85%`** (`1.89x`) | `65.3%` | `76.7%` | `11` | `25` | `3.00` | `1043 / 4242 / 862` |

### Honest Assessment: What Improved vs. What Did Not
- **Clearly improved:**
  - **Ownership churn (`flip_flops`) dropped sharply across every scenario:** **`-35.6%` to `-48.9%`** on `fo4sf_commonwealth` and **`-12.9%` to `-48.9%`** on `vanilla_new_atlantis`. Squads stop abandoning defended checkpoints only to trade them back and forth randomly.
  - **Garrison presence & healing jumped dramatically:** Garrison utilization increased **`1.66x–2.77x`** and base replenishes increased **`1.31x–4.75x`**, making territories visibly held rather than perpetually empty.
  - **Balanced-map anti-snowballing improved:** On `fo4sf_commonwealth` (`2,500` ticks), peak faction territory share dropped from `55.1%` to **`44.5%`**, eliminating all `>= 75%` dominance seeds (`1 -> 0`) and keeping `3.00/3.00` factions alive.
- **Did NOT improve / explicit trade-offs:**
  - **Asymmetric-map snowballing got slightly *worse* on `vanilla_new_atlantis`:** `early_dominance_ge75` rose from `5/30` to `11/30` at `2,500` ticks (`final_max_share` `72.3% -> 76.7%`). Why: in `vanilla_new_atlantis.json`, `uc_security` starts with `5` owned nodes and the **only `base` nodes** (`na_spaceport`, `na_mast`), whereas `spacers` and `ecliptic` spawn from `lair` nodes (which cannot replenish). Smarter AI exploits that structural advantage instead of masking it with random wandering.
  - **Fewer raw battles (`-18%` to `-39%`):** Because damaged squads pull back to heal and avoid attacking fortified garrisons alone, battle tempo is steadier and slower. That looks more believable in Warfare, but a modder wanting constant skirmishes may still prefer `"random"` or higher raid weights.
- **Verdict:** Keep `order_mode: "random"` as the default for now; expose `"scored"` as a verified offline prototype (`sim_math` + `build_alife_mod simulate`) ready for owner review and optional Papyrus porting once asymmetric `lair` replenishment / balance tuning is decided.

---

## 2. Job Slots at Nodes (STALKER Smart Terrains — Design Only)

In *S.T.A.L.K.E.R.*'s A-Life, each smart terrain (`gulag`) owns prioritized **job slots** (guard post, campfire rest, patrol loop, sniper watch) that resident squads claim when occupying the terrain ([Game Developer — Dmitriy Iassenev](https://www.gamedeveloper.com/game-platforms/interview-inside-the-ai-of-i-s-t-a-l-k-e-r-i-)). Today our garrisoned squads materialize onto a single reusable `XMarkerHeading` per squad (`Waymarkers[0..15]`) and idle around it.

### Proposed 4-Job Slot Set (Track 2 Design)
| Job ID | Role | Online Package Behavior | Offline Effect |
|---:|---|---|---|
| `0` | **`guard`** | Hold perimeter / watch choke point (`DefaultSandbox` restricted radius or guard furniture). | `+10%` defensive combat modifier while garrisoned. |
| `1` | **`rest`** | Sit/sleep/recover at owned `base` or `checkpoint`. | Priority slot for damaged squads (`hp_frac < 0.85`) awaiting `replenish`. |
| `2` | **`camp`** | Gather around campfire / workbench / scavenging spot (`resource`/`lair`). | Social immersion when player enters the `450 m` bubble. |
| `3` | **`patrol-loop`** | Walk a local 2–3 marker perimeter loop around the node while online. | Visible local movement without leaving garrison status. |

### Exact Papyrus Runtime Requirements & 128-Element Limits
Inspecting `scripts/alife/FO4SF_ALifeSimQuest.psc` directly:
- **Current budget already spent:** `32` `Auto Const` properties (`16` arrays, `8` scalars, `4` `GlobalVariable`s, `3` `GameplayOption`s, `1` `Potion`) + `23` runtime state arrays. Crucially, `Actor[] sqActors` is **`16` squads × `8` members = `128` elements** — already sitting right at Papyrus's hard **`128`-element array ceiling**.
- **What fits inside `128`:**
  - `int[] NodeJobMask` (`len <= 128`, 1 bitmask/packed-count int per node encoding which of the 4 jobs the node offers)
  - `int[] sqJob` (`len = 16`, current job ID per squad)
  - `Package[] JobPackages` (`len = 4`, one AI package template per job)
  - Total addition: **`+2` `Auto Const` properties, `+1` runtime array** — completely safe up to `128` nodes.
- **Where the `128` ceiling breaks:**
  - **Per-slot world coordinates (`JobX/Y/Z/Heading`):** A flat array of `4` markers per node overflows `128` at just **`33` nodes** (`33 × 4 = 132 > 128`). Even `2` markers per node overflows at `65` nodes.
  - **Workarounds in pure Papyrus:** Either (a) keep 1 center marker per node and derive deterministic radial offsets (`±12 m`) by job index at materialization time (zero extra arrays, loses hand-placed guard posts), or (b) shard job markers into per-region helper quests (`4` shards × `128` = `512` slots, adding Mutagen writer complexity and cross-quest property lookups). True arbitrary hand-placed smart-terrain job tables across `> 32` nodes push strongly toward the optional native layer (Section 5).

---

## 3. Event-Driven Reactions (`AlifePlus`-Style — Design Only)

*AlifePlus* for *S.T.A.L.K.E.R. Anomaly* ([damiansirbu-stalker/AlifePlus](https://github.com/damiansirbu-stalker/AlifePlus)) replaces arbitrary timed spawning with **cause-and-consequence callbacks**: engine events (wounded stalker, squad massacre, outpost capture) immediately dispatch nearby existing squads to react.

### Proposed Reaction Table Mapped to Existing `FO4SF_ALifeAPI.psc` Hooks

`scripts/alife/FO4SF_ALifeAPI.psc` **already exposes** these global hooks for external quests and soft-dependent mods:
`IsRunning`, `SetEnabled`, `SpawnSquadAtNode(faction, node)`, `OrderRaid(faction, targetNode)`, `GetNodeOwner(node)`, `SetNodeOwner(node, faction)`, `GetActiveSquadCount()`, `GetNodeCount()`, `GetFactionCount()`, `GetSquadState(squad)`, `GetSquadFaction(squad)`, `GetSquadNode(squad)`, and `PrintStatusSummary()`.

| Trigger Event | Reaction Rule (Design) | Existing `FO4SF_ALifeAPI` Hook Used | Missing Small Hook Needed Later |
|---|---|---|---|
| **Base / Checkpoint Under Attack** | Nearest idle friendly squad within `<= 2` hops cancels dwell and marches to defend the contested node. | `OrderRaid(defenderFaction, contestedNode)` + `GetNodeOwner` | `OrderReinforce(faction, node)` (or allow `OrderRaid` on own node) + per-faction reaction cooldown (`>= 60 s`) to prevent dogpiling. |
| **Ambush on an Edge** | When two hostile squads clash on edge `(u, v)`, adjacent friendly garrison at `u` or `v` has a bounded chance (`35%`) to sally out along that edge. | `GetSquadState` (`4 = in_combat_offline`), `GetSquadNode` | `OnALifeBattleStarted(squadA, squadB, nodeOrEdge)` custom quest event (`SendCustomEvent`). |
| **Player Kills a Materialized Squad** | Faction logs an alert at that node: nearby enemy patrol avoids or sends a heavier retaliation squad from its nearest own base (and feeds `X9` radiant avenge missions). | `OrderRaid(victimFaction, incidentNode)`, `GetSquadFaction`, `GetSquadNode` | `OnALifeSquadDefeated(squad, faction, node, byPlayer)` custom event + `FO4SFReputation` infamy hook. |
| **Node Captured** | Former owner prioritizes counter-attack or reinforces adjacent border; allies update Pip-Boy map / `X9` radiant board. | `GetNodeOwner`, `OrderRaid` | `OnALifeNodeCaptured(node, oldOwner, newOwner)` custom event. |

*(Every reaction MUST carry a per-node/per-faction cooldown and respect `MaxActiveSquads` so reactions redirect existing squads rather than spawning infinite reinforcement waves.)*

---

## 4. Fog of War (Design Only — Tied to Our Pip-Boy Map Page)

In Warfare and Story modes, showing every enemy squad's real-time exact position on the Pip-Boy `MAP` tab destroys exploration tension and ambush risk. Our Pip-Boy stack (`FO4SFPipboyMenu.dll` + `FO4SFPipboyMapMarkers.tsv`, `WorldMapMarkers`) already renders marker state per location (`discovered` vs. `undiscovered`, marker type, and quest overlays).

### Proposed 3-Tier Intel Visibility Model
| Intel Tier | What the Player Sees on Pip-Boy `MAP` | How a Node / Squad Enters This Tier |
|---|---|---|
| **1. Live Intel (`Clear`)** | Current faction owner badge, garrison count band (`Light`/`Heavy`), and active friendly/hostile squads within radius. | (a) Within player recon radius (`<= 450 m`, matching the online bubble, boosted by `Perception` / `FieldTransponder`), OR (b) any node currently owned by an **allied** faction (`player_relation == "ally"`), OR (c) within `1` hop of an allied garrison with an active radio/beacon. |
| **2. Stale Intel (`Last Known`)** | Last observed owner + timestamp age (`"Last seen 2h ago"`), zero live squad movement pins. | Any node the player previously visited/scouted or received intel on (via NPC dialogue / `X9` radiant report / captured PDA) once outside Live Intel radius. Decays after `24` in-game hours (configurable). |
| **3. Fogged (`Unknown`)** | Location marker only (or undiscovered silhouette); **no** owner badge and **no** squad pins. | Hostile or neutral territory never scouted and not adjacent to an allied garrison. |

- **Integration Point:** A compact per-node bitfield (`int[] nodeIntelState`, `<= 128` ints, or sidecar TSV/INI snapshot written alongside `FO4SFPipboyMapMarkers.tsv`) lets `FO4SFPipboyMenu.dll` filter `WorldMapMarkers` and secondary Warfare-device squad pins without modifying Starfield's StarMap or breaking `MapBlockStarMap=0`.
- **Gameplay Toggle:** Expose `FogOfWar` as a runtime option (ON by default in Warfare/Survival; optional OFF "Debug / Full Map" toggle for modders testing graphs).

---

## 5. Native Option vs. Plugin + Papyrus Default (Portability & Limits)

### Why Papyrus Hits a Ceiling
Vanilla Starfield's Papyrus VM enforces a hardcoded **`128`-element maximum array length**. That caps:
- Graph size at `<= 128` nodes and `<= 128` edges (`schema.py:ARRAY_CAP = 128`),
- Active actor pool at `16` squads × `8` members = `128` (`sqActors`),
- Per-node job coordinates at `<= 32` nodes for `4` slots/node (Section 2).

### What SFSE / Native Plugins Change
- **SFSE** ([ianpatt/sfse](https://github.com/ianpatt/sfse)) supports the **Steam PC** build of Starfield (not Xbox/Creations, and not officially Microsoft Store/Game Pass).
- **Starfield Engine Fixes - SFSE** by LarannKiar ([Nexus Mods #10457](https://www.nexusmods.com/starfield/mods/10457)) includes an optional **Papyrus No Array Limit** setting (introduced in v5.6, toggled via `StarfieldEngineFixes.ini`) that patches out the 128-element Papyrus array cap.
- **Our Own Optional Native Companion DLL (`FO4SFALifeNative.dll`, Steam PC Only — Design Only):** Remember our project rule: we depend on **no third-party mod** (`Starfield Engine Fixes` is cited for technical feasibility only, never as a dependency!). Instead, an optional, separate FO4SF native SFSE plugin could move graph storage, Dijkstra/A* routing, scored-order evaluation, spatial influence grids, job-slot tables, and Fog-of-War snapshots out of Papyrus into C++:
  - **What it unlocks:** Unlimited graph nodes/edges (`500+` nodes for a full Commonwealth + DLC or Mojave + Capital Wasteland map), unlimited hand-placed job markers, sub-millisecond scored-order + event evaluation, and direct shared-memory feed to `FO4SFPipboyMenu.dll`'s map layer.
  - **Portability & maintenance cost:** **Steam PC only** (breaks Xbox/Creations and MS Store portability unless paired with a Papyrus fallback), requires C++ Address Library / offset updates on every Starfield executable patch, and needs a clean Papyrus-to-native bridge contract so saves do not corrupt if a player disables the DLL.
- **Recommended Route:** **Keep Plugin + Papyrus (`<= 128` nodes/region) as the public, cross-platform baseline** (partitioning huge maps into `<= 128`-node regional graphs if needed), and treat a native SFSE backend strictly as a **separate, optional accelerator package** for Steam PC Warfare megamaps later.

---

## 6. Evidence Gaps (Stated Plainly)

To stay strictly honest about what our research verified vs. what could not be independently documented:
1. **Bethesda Radiant AI schedule internals:** No authoritative primary technical documentation was found describing Starfield's or Fallout 4's internal Radiant AI schedule evaluator or unloaded-cell schedule stepping beyond standard Creation Kit package flags.
2. **Mount & Blade II: Bannerlord distant-party simplification & campaign heat maps:** While TaleWorlds' official Campaign AI dev blog ([News #273](https://www.taleworlds.com/en/News/273)) documents lord decision factors (distance, supplies, recruitment, target safety/priority), we found **no** official TaleWorlds dev blog documenting how distant off-screen parties are simplified mathematically or confirming an active campaign-AI heat map mechanic.
3. **Native C++ vs. Papyrus A-Life benchmarks in Starfield:** No controlled, reproducible Starfield benchmark comparing native SFSE C++ tick cost against Papyrus `FO4SF_ALifeSimQuest` tick cost was found (and none has been run in-game here; all measurements in Section 1 are pure-Python offline simulator benchmarks).

---

## 7. Sources

1. Dmitriy Iassenev (GSC Game World), *"Interview: Inside the AI of S.T.A.L.K.E.R."*, Game Developer (formerly Gamasutra) — A-Life offline/online switching, smart terrains, and job slots: https://www.gamedeveloper.com/game-platforms/interview-inside-the-ai-of-i-s-t-a-l-k-e-r-i-
2. TaleWorlds Entertainment, *"Dev Blog 20/12/19 — Campaign AI"* (*Mount & Blade II: Bannerlord*) — distance, party needs, and strategic target scoring: https://www.taleworlds.com/en/News/273
3. Damian Sirbu, *AlifePlus* (event-driven A-Life reaction framework for *S.T.A.L.K.E.R. Anomaly*): https://github.com/damiansirbu-stalker/AlifePlus
4. Ian Patterson, Stephen Abel & Expired, *Starfield Script Extender (SFSE)* (Steam PC plugin loader): https://github.com/ianpatt/sfse
5. LarannKiar, *Starfield Engine Fixes - SFSE* (Nexus Mods #10457 — documents optional v5.6+ `Papyrus No Array Limit` lifting the 128-element Papyrus array ceiling): https://www.nexusmods.com/starfield/mods/10457

---

## 8. Owner Questions

1. **Scored Orders Promotion & Asymmetric Map Tuning:** Given the 30-seed benchmark (where `scored` cut flip-flops by `36%–49%` and reduced snowballing on symmetric `fo4sf_commonwealth`, but amplified `uc_security`'s early lead on asymmetric `vanilla_new_atlantis` because `lair` spawn nodes cannot replenish), should we keep `order_mode: "random"` as the default for now, and if you want `scored` ported to Papyrus later, should `lair` spawn nodes also replenish squads (at a slower rate) to prevent asymmetric base-only snowballs?
2. **Job Slots Strategy (`<= 128` Array Ceiling):** For smart-terrain jobs (`guard`, `rest`, `camp`, `patrol-loop`), do you prefer the zero-extra-array **radial-offset Papyrus version** (works on all platforms up to `128` nodes with no hand-placed job markers) or **regional shards / optional native SFSE markers** for hand-placed guard posts?
3. **Fog of War Default:** Should Fog of War on the Pip-Boy `MAP` (Live / Stale / Fogged tiers) default to **ON in Warfare and Survival** and **OFF in casual Story**, or ON across all modes with a gameplay toggle?
4. **Optional Native SFSE Accelerator:** Do you want A-Life to stay strictly **Plugin + Papyrus** (`<= 128` nodes per region) through Track 1, deferring any Steam-PC-only native SFSE A-Life DLL until multi-region Warfare megamaps actually hit the `128`-node cap?
