Titles: All 7 Fallout titles (Fallout 4 first) | Modes: Story & Warfare (+ Survival hardcore layer) | Track: Track 2 (experimental core) — prototype, offline

# World-State Radiant Missions from Local People & A-Life (`X9`)

> **Scope & Status:** **Design note + offline SDK prototype (`prototype, offline` — Track 2, Round 9 `X9`).** Implements `src/fo4sf/alife/radiant_missions.py`, `scripts/alife/demo_radiant_missions.py`, and `tests/test_alife_radiant_missions.py` on top of the standalone A-Life simulator (`#841`). Zero runtime `.esm`/`.pex` behaviour is presented as done in game, and hand-authored story missions on Track 1 (*When Freedom Calls*, *Sanctuary*, *The First Step*, *Jewel of the Commonwealth*, and every title's main/side quests) are **never** replaced by procedural requests.

---

## 1. Research Baseline, Citations & Evidence Boundaries

1. **Creation Engine Radiant Story & Story Manager:**
   - Skyrim introduced **Radiant Story** paired with the **Story Manager** — an event-driven node tree (`SM Event Node` -> Branch Nodes -> Quest Nodes) evaluated on engine events (`Kill Actor Event`, `Change Location Event`, `Script Event`) that starts non-`StartGameEnabled` quests and populates `ReferenceAlias` / `LocationAlias` slots dynamically at runtime ([CK Wiki: SM Event Node](https://ck.uesp.net/wiki/SM_Event_Node); [CK Wiki: Quest Data Tab](https://ck.uesp.net/wiki/Quest_Data_Tab); [CK Wiki: Quest Alias Tab](https://ck.uesp.net/wiki/Quest_Alias_Tab)).
   - Bethesda lead designer Bruce Nesmith noted at the 2012 Vancouver Game Design Expo that pushing Radiant generation into the main questline *"sounds great, would play horribly"* because algorithmic slot-filling cannot replace authored narrative pacing ([VentureBeat coverage of Nesmith's Radiant Story talk](https://venturebeat.com/games/bethedsas-nesmith-reflects-the-difficult-birth-of-skyrims-radiant-story-system/)).
2. ***S.T.A.L.K.E.R. Anomaly* Dynamic Tasks & A-Life Coupling:**
   - In *Anomaly* (and *GAMMA* task packs such as [iTheon's New Tasks Addon](https://github.com/lTheon/iTheon-New-Tasks-Addon)), bartenders, mechanics, medics, squad leaders, and ordinary stalkers offer dynamic retrieval, assassination, defense, and escort tasks whose targets and destinations come from live **A-Life** smart-terrain ownership and roaming squads, with completion rewards scaled by distance, rank, and danger. Vanilla single-step templates still suffer from repetition when uncoupled from cooldowns or world consequences.
3. **Procedural Quest Generation (PQG) Quality Studies:**
   - Structural and planning studies — notably Doran & Parberry (2011, [*A Prototype Quest Generator Based on a Structural Analysis of Quests from Four MMORPGs*](https://ianparberry.com/research/quests/larc2011-02.pdf)) and Soares de Lima, Feijó & Furtado (2022, [*Procedural Generation of Branching Quests for Games*](https://www.sciencedirect.com/science/article/pii/S187595212200032X)) — identify the **three failure modes** of random quests: **(i) mad-libs incoherence** (unmotivated pairings of giver, target, and place), **(ii) template repetition** (sending the player back to the same dungeon twice in a row), and **(iii) zero world impact** (completing or ignoring a request changes nothing in the persistent world).
4. **Where Public Evidence Was Not Found:**
   - While Fallout 4 carried Skyrim's Story Manager and `LocationAlias` architecture forward for Preston Garvey's Minutemen settlement jobs, **no official Bethesda engineering write-up or Creation Kit documentation detailing Fallout 4's Minutemen radiant selection weights or failure lessons was found**. Rather than imitating random Story Manager dice rolls, our design generates requests strictly from **causal events and state transitions already tracked by our A-Life simulation**.

---

## 2. World-State Radiant Mission Architecture (`(a)`–`(g)`)

### (a) Local Area Givers (`GIVER_ROLES`)
Requests are held by persistent or garrisoned people stationed at friendly or neutral A-Life `base` and `checkpoint` nodes (`player_relation != "enemy"` and node not occupied by a hostile faction):
- **Settlers (`settler`):** Local residents / spokespersons at allied `base` nodes who report missing scouts, fallen neighbours, or urgent salvage shortages.
- **Traders (`trader`):** Caravan merchants and quartermasters who need supply convoys escorted along safe graph corridors or nearby roadblock warlords cleared.
- **Guards / Militia Officers (`guard`):** Garrison sentries and patrol leaders who issue frontline retake orders, raid-interception bounties, and battle-site investigations.

### (b) Five World-State Request Types (`REQUEST_TYPES`)

| Request Type | Player Objective | Required A-Life World-State Trigger | World Consequence (Success vs Ignored/Failed) |
| :--- | :--- | :--- | :--- |
| **`fetch_or_rescue`** | Recover critical salvage from a `resource`/`lair` node, or free a scout pinned after a battle. | `captured_scout_after_battle` (`battle` recorded at contested `lair`/`resource`) or `settlement_resource_need` (reachable unowned/hostile `resource` node). | **Success:** `SpawnSquadAtNode` / garrison replenish at giver base.<br>**Failure:** Garrison supply shortage penalty. |
| **`kill_named_threat`** | Eliminate a named hostile raid warlord or ringleader staging near allied territory. | `active_hostile_raid_order` (living hostile squad issued `order="raid"`) or `hostile_garrison_threat` (hostile squad occupying reachable node). | **Success:** Disrupts active raid / weakens hostile garrison + `+10` Fame.<br>**Failure:** Hostile `OrderRaid` launched against giver node. |
| **`avenge_or_investigate`** | Inspect an ambush/skirmish site, recover fallen tags, and eliminate the culprit warband. | `friendly_squad_defeated` (`squad_defeated` event on friendly squad) or `skirmish_casualty_report` (`battle` attrition event). | **Success:** `+10` Fame + patrol morale/slot recovery.<br>**Failure:** Hostile `OrderRaid` / increased patrol pressure on giver node. |
| **`clear_or_retake_node`** | Clear a hostile-occupied `base`/`checkpoint` and restore allied control. | `hostile_captured_node` (`capture` event where hostiles seized a node, highest priority `95` when previously friendly-owned) or `hostile_frontline_occupation`. | **Success:** `FO4SF_ALifeAPI.SetNodeOwner(target, giver_faction)`.<br>**Failure:** Hostile `OrderRaid` launched from the uncontested node. |
| **`escort_or_deliver`** | Escort a relief trader or deliver medical/ammo crates along a connected route. | `allied_supply_corridor` (two distinct friendly nodes connected on `Graph`) or `frontier_outpost_relief` (friendly base to unowned reachable outpost). | **Success:** `SpawnSquadAtNode` / reinforces destination outpost.<br>**Failure:** Convoy cargo lost (`failed_with_consequence`). |

### (c) Structured Request Components
Every `RadiantMission` in `src/fo4sf/alife/radiant_missions.py` is assembled from verified graph and event components rather than free-floating random picks:
- **Who:** `giver_npc_tag`, `giver_role` (`settler | trader | guard`), `giver_faction_id`, `giver_node_id`.
- **What & Where:** `what_tag`, `target_node_id`, `target_faction_id`, shortest Dijkstra `route_nodes` (`>= 2` nodes), and exact path `distance_m`.
- **Causal Trigger:** `trigger` dictionary recording exact event `kind`, simulation `tick`, squad ID, or prior node owner.
- **Scaled Reward & Deadline:** `reward_caps` (`(base + 0.12 * distance_m) * max(1.0, combat_power)` rounded to `10` caps), `reward_fame` (`+5` logistics / `+10` combat), and `deadline_s` (`>= 4.5x` offline travel time + `180 s` buffer).
- **Bidirectional World Consequence:** Explicit `consequence_on_success` and `consequence_on_failure` payloads mapped to `FO4SF_ALifeAPI` calls (`SetNodeOwner`, `OrderRaid`, `SpawnSquadAtNode`) and `FO4SFReputation` Fame deltas.

### (d) Completion, Failure, Ally Pre-Clear & `"Giver Died"` (`W7` Open-Mode Safety)
Per the `W7` Survival/Hardcore Open-Mode contract (`docs/core/port-requirements.md` Section 7), **any NPC in the world can die and no quest may ever dead-end**:
1. **Living Giver (`completed`):** Standard face-to-face turn-in to `giver_npc_tag`; awards full caps/Fame and applies `consequence_on_success`.
2. **Primary Giver Died -> Role Succession (`completed_via_deputy`, `W7` Pattern `ROLE`):** Every request pre-assigns a `deputy_role` (`guard` or `quartermaster`) at the settlement or nearest allied fallback base (`deputy_node_index`) who accepts turn-in seamlessly if `GiverAlias.IsDead()`.
3. **Entire Settlement Wiped Out -> Comms Dropbox (`completed_via_comms`, `W7` Pattern `ITEM`):** If both primary giver and local deputy are dead/unloaded, completion routes through the secondary faction device's **`Faction Comms`** tab (or settlement dropbox locker), closing the quest and releasing the slot with zero orphaned objectives.
4. **Target Pre-Cleared by Friendly A-Life Squad (`resolved_by_alife_ally`):** Because A-Life runs continuously, an allied patrol can capture or clear `target_node` while the player is walking there. Instead of stranding the player on `"Kill 0/1 enemies"`, the state machine transitions cleanly to `resolved_by_alife_ally`, applies `consequence_on_success`, and pays a `50%` reconnaissance/assist stipend.
5. **Escort Charge Killed or Deadline Exceeded (`failed_with_consequence` / `expired_with_consequence`):** Applies `consequence_on_failure` (e.g., hostile `OrderRaid` or lost convoy) and frees the active slot cleanly.

### (e) Save/Reload Safety & Active Request Cap
- **Hard Active Cap (`DEFAULT_MAX_ACTIVE = 3`, configurable `1..5`):** Prevents Fallout 4's quest-log spam (`MissionBoardState.accept()` refuses a 4th active mission until an active slot reaches a terminal state).
- **Zero-Pointer Primitive Serialization:** `MissionBoardState.to_papyrus_arrays()` and `from_papyrus_arrays()` persist active requests solely as fixed-length `Int[]`, `Float[]`, and `String[]` parallel arrays (`slot_occupied`, `slot_state`, `slot_type`, `slot_giver_node`, `slot_target_node`, `slot_reward_caps`, `slot_deadline_s`, etc.), avoiding transient object graphs so `OnPlayerLoadGame` restores state idempotently.

### (f) Quality Guard Against Repeats & Nonsense Combinations
1. **`verify_mission_completable(mission, snapshot)` (Hard Structural Gate):** Rejects self-loops (`giver_node == target_node`), zero-capacity nodes, disconnected subgraphs (`dist == inf`), enemy factions offering friendly jobs, friendly-fire bounties (`!hostile[giver][target]`), escort routes into hostile-occupied strongholds, impossible deadlines (`< 2.5x` travel time), missing `W7` fallbacks, or invalid UI tabs.
2. **`QualityGuard` (Anti-Repetition Filter):** Forbids duplicate `target_node_index` within any active batch, blocks `(request_type, target_node_index)` pairs inside a rolling `cooldown_window` (`8` requests), and adds novelty bonuses (`+25` unseen request type in batch, `+15` fresh node, `+12` fresh type) so local NPCs surface varied jobs across the map.

### (g) UI Surface Split: Secondary Faction Device vs Real Pip-Boy (`13 Nov` Rule) & Track Fit
Per the owner's `13 November` UI separation rule, job-board browsing and tactical dispatches belong on the **secondary faction device** (our `6`-tab page kit), **never** on the wrist Pip-Boy's personal `STAT` or `INV` pages:

| UI Device & Page | What Appears Here | What Never Appears Here |
| :--- | :--- | :--- |
| **Secondary Faction Device -> `Bounties`** | Open `kill_named_threat` & `avenge_or_investigate` contracts posted in the region (with trigger reason, distance, reward, deadline). | Personal character stats, health/rad meters, inventory items. |
| **Secondary Faction Device -> `Settlements`** | Open `fetch_or_rescue` & `escort_or_deliver` requests from allied settlements and traders, plus supply-line health. | Main-story quest spoilers or personal `STAT` perks. |
| **Secondary Faction Device -> `Warfare`** | Open `clear_or_retake_node` frontline operations, contested sector ownership, and squad raid alerts. | Unaccepted civilian chatter. |
| **Secondary Faction Device -> `Faction Comms`** | Remote radio dispatches, ally pre-clear notifications, and **`W7` dead-giver remote turn-in** when a local giver perished. | Vendor barter inventories. |
| **Secondary Faction Device -> `Quests` & `Map`** | Tactical filter over active faction/radiant jobs and A-Life sector pins. | Hand-made personal Vault/main-story journal clutter if filtered to faction ops. |
| **Wrist Pip-Boy -> `DATA / Quests` & `MAP`** | **Accepted requests only** (whether accepted face-to-face from a settler/trader/guard or pinned from the secondary device) + active objective marker (`A5`). | Unaccepted job-board listings; **`STAT` and `INV` remain `100%` untouched.** |

- **Track 1 vs Track 2 Fit:** This system sits strictly in **Track 2 (`--profile test`, experimental core)**. Track 1 (`--profile player`) ships Fallout 4's hand-made story missions in order and never substitutes random missions for authored quests. Once Track 1's opening spine and `FO4SFALife` runtime are verified in game, Track 2 radiant requests plug into **Warfare** (frontline jobs) and optional **Story / Survival** side work between hand-made chapters across all titles.

---

## 3. Offline 25-Seed Verification Receipt & Papyrus Runtime Requirements

### 1. Offline Simulator Benchmark (`scripts/alife/demo_radiant_missions.py`)
Running `run_multi_seed_verification` across **`25` seeds** (`600` ticks/seed, `max_per_seed = 4`) on `fo4sf_commonwealth.json` (`20` NW Commonwealth nodes, `3` factions) and **`20` seeds** (`500` ticks/seed, `max_per_seed = 3`) on `vanilla_new_atlantis.json`:

| Preset | Seeds × Ticks | Missions Generated | Completable (`verify_mission_completable`) | Request-Type Distribution | Secondary-Device Tab Split | Unique Target Nodes |
| :--- | :---: | :---: | :---: | :--- | :--- | :---: |
| **`fo4sf_commonwealth`** | `25 × 600` | `100` | **`100 / 100` (`100%`)** | `fetch_or_rescue`: `21`, `kill_named_threat`: `20`, `avenge_or_investigate`: `16`, `clear_or_retake_node`: `21`, `escort_or_deliver`: `22` | `settlements`: `43`, `bounties`: `36`, `warfare`: `21` (`+ faction_comms` fallback on all `100`) | `20 / 20` |
| **`vanilla_new_atlantis`** | `20 × 500` | `60` | **`60 / 60` (`100%`)** | All `5` request types represented, `0` self-loops, `0` friendly-fire or hostile-escort errors | Only `bounties`, `settlements`, `warfare` (`0` `stat`/`inv`) | `100%` reachable |

### 2. Required Papyrus & Plugin Pieces (For Future Runtime Wiring — Not Built Here)

| Component | Exact Runtime Construct |Creation Engine 2 / Papyrus Limit & Safety Margin |
| :--- | :--- | :--- |
| **Quest Pool (`QUST`)** | `3` reusable slot quests (`FO4SF_RadiantSlot01..03`, `StartGameEnabled = false`, `AllowRepeatedStages = true`, `Stop()` on terminal state to release aliases). | `3` static `QUST` records (`0` dynamic quest records, `0` `PlaceAtMe` save bloat; hard cap `<= 5`). |
| **Aliases per Slot (`QUST` Aliases)** | `5` optional `ReferenceAlias` slots per quest: `GiverAlias`, `DeputyFallbackAlias`, `TargetActorAlias`, `TargetMarkerAlias`, `EscortChargeAlias` (`Optional` + `AllowDead` where needed so alias fill never blocks start). | `5 × 3 = 15` aliases total across the controller (`well below` quest alias ceilings; unloaded targets track via A-Life node index until within `450 m` online bubble). |
| **Controller State Arrays (`FO4SF_RadiantController.psc`)** | `17` parallel primitive arrays of length `max_active` (`3..5`) + `3` cooldown ring-buffer arrays (`recent_types[8]`, `recent_targets[8]`, `recent_ticks[8]`). | Max array length **`8` elements** — **`16x` below Papyrus's `128`-element array ceiling**. Total script properties `~24` (well below property limits). |
| **A-Life API Hooks (`FO4SF_ALifeAPI.psc`)** | Existing: `GetNodeOwner`, `SetNodeOwner`, `GetSquadState`, `GetSquadFaction`, `GetSquadNode`, `OrderRaid`, `SpawnSquadAtNode`.<br>Proposed additions when wired: `GetLastBattleNode(int aiSlot)` & `GetLastDefeatedSquadFaction()` (`8`-entry event ring buffer on `FO4SF_ALifeSimQuest`). | Soft-dependency via `Game.GetFormFromFile`; returns `-1 / False` safely when A-Life is disabled. |

---

## Questions for the Owner

1. **Active request cap (`Section 2(e)`):** Is a default cap of **`3` simultaneous active radiant requests** (configurable `1..5`) right so the quest log stays focused, or should Warfare mode allow more?
2. **Preston & vanilla Fallout 4 radiant quests (`Section 2(g)`):** Once Track 2 A-Life radiant missions are wired later, should vanilla Fallout 4's timer-driven settlement quests (*MinRecruit* / *Defend*) stay as Fallout 4's native implementation in Story mode while Warfare uses A-Life world-state requests, or should A-Life's world-state generator drive settlement requests in both modes (preventing repeats and unmotivated across-the-map picks)?
3. **Target pre-cleared by friendly A-Life squads (`Section 2(d)`):** When an allied A-Life patrol captures or clears a target node while the player is en route, do you prefer **auto-completing with a `50%` assist reward via `Faction Comms`** (current prototype behaviour), or **cancelling with `0` reward and offering a follow-up `escort_or_deliver` garrison job**?
4. **Deadline failure consequences (`Section 2(b)`):** Should ignoring an accepted `kill_named_threat` or `clear_or_retake_node` past its deadline trigger an actual hostile `OrderRaid` against the giver's settlement in both Story and Warfare, or **only in Warfare and Survival** (leaving standard Story mode penalty-free on expiration)?
