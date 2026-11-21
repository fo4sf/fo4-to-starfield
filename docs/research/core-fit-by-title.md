# Core Systems Fit Matrix Across All Seven Fallout Titles (`CF-1`..`CF-10`)

Maps the measured quest, script, and record census from [all-games-quests-scripts.md](all-games-quests-scripts.md) onto the shared gameplay core (`CF-1`..`CF-10` in `gemini/core-candidate`), specifying:
1. How each title (`FO1`, `FO2`, `FOT`, `FO3`, `FNV`, `FO4`, `FO76`) maps onto our implemented C#, Papyrus, SFSE, and Python core modules,
2. Exact per-title data-table columns required by each system,
3. Systems where a title's shipped model diverges from our core (flagged with concrete options for the owner, keeping `FO1`/`FO2`/`FOT` isometric boundaries explicitly gated on **Owner Decisions `ISO-1..ISO-3`**), and
4. Small, concrete code/table gaps suitable for self-contained Job 3 fit PRs that keep Fallout 4 behavior byte-for-byte unchanged.

---

## 1. Master System-by-Title Fit Matrix (`CF-1`..`CF-10`)

Legend:
- **`FIT (1:1)`** — Title's native model matches our core runtime directly via data rows.
- **`FIT (ADAPT)`** — Title's data maps cleanly through a deterministic conversion rule or runtime switch already designed in the core.
- **`GAP (SMALL)`** — Core mechanics fit, but a small per-title column, slot expansion, or table sync is needed before volume import (see Section 4).
- **`OWNER GATE`** — Requires an explicit owner design or policy decision before volume conversion (`ISO-1..ISO-3` for classic isometric titles; `REL-60` + server-stub reconstruction policy for `FO76`).

| Core Slice & Repo Backing | `FO1` (*Fallout*) | `FO2` (*Fallout 2*) | `FOT` (*Tactics*) | `FO3` (*GOTY*) | `FNV` (*New Vegas*) | `FO4` (*Fallout 4*) | `FO76` (*Appalachia*) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`CF-1` New Game & `StartWorld`**<br>`src/fo4sf/core/start_worlds.py`<br>`dotnet/NewGame/Program.cs` | `FIT (ADAPT)` (`vault13` row in `START_WORLD_TABLE`; 3D cave awaits `ISO-2`) | `FIT (ADAPT)` (`arroyo` row in `START_WORLD_TABLE`; awaits `ISO-2`) | `FIT (ADAPT)` (`bunkeralpha` row, `squad_base_cap=4`; awaits `ISO-2`) | `GAP (SMALL)` (`vault101` row defined; `CG01..CG04` childhood vs `CG04` skip choice) | `FIT (ADAPT)` (`goodsprings`, `ncr_trooper`, `desert_ranger` rows defined) | `FIT (1:1)` (`vault111`, `minuteman_volunteer`, `brotherhood_initiate`) | `OWNER GATE` (`vault76` row defined; gated on `REL-60`) |
| **`CF-2` Quest Layer & Journal**<br>`dotnet/NewGame/Program.cs` (`DefaultHold`)<br>`FO4SFMission.esm` | `FIT (ADAPT)` (`618` `VAULT13.GAM` `GVAR`s -> wrapper `QUST` stages) | `FIT (ADAPT)` (`110` `quests.txt` rows across `14` towns -> `QUST` + `QOBJ`) | `FIT (ADAPT)` (`103` `.mis`, `39` `Add Objective` -> mission `QUST`s) | `FIT (1:1)` (`298` `QUST`, `1,343` `INDX`, `542` `QOBJ`) | `FIT (1:1)` (`642` `QUST`, `1,423` `INDX`, `1,479` `QOBJ` + cross-quest `SCRO`) | `FIT (1:1)` (`1,916` `QUST`, `13,071` `INDX`, `16,380` aliases) | `OWNER GATE` (`2,281` `QUST` present; `2,652` server `.pex` stubs omitted) |
| **`CF-3/4` Pip-Boy & Multi-World Map**<br>`sfse/FO4SFPipboyMenu`<br>`scripts/ui/pipboy_map_store.py` | `OWNER GATE` (Overland tile grid + `Outdoorsman` encounters -> `WorldId` map) | `OWNER GATE` (`worldmap.txt` + Highwayman fuel -> `WorldId` map) | `OWNER GATE` (`encounters.txt` bunker regions -> `WorldId` map) | `FIT (1:1)` (`32` base `WRLD`, `222` `XMRK` -> `WorldId="CapitalWasteland"`) | `FIT (1:1)` (`14` base `WRLD`, `189` `XMRK` -> `WorldId="MojaveWasteland"`) | `FIT (1:1)` (`309` Commonwealth markers + Star Map blocked) | `OWNER GATE` (`56` `WRLD`, `482` `XMRK`, Caps travel fee rule) |
| **`CF-5` Interactive Refs & Script Runtime**<br>`dotnet/InteractiveFidelity`<br>`scripts/papyrus/shims/FO4SF_Shim_*.psc` | `OWNER GATE` (`952` `.int` SSL binaries, `0` `.ssl`; needs `.int -> .psc` transpiler + `ISO-1/2`) | `OWNER GATE` (`1,443` `.int` SSL binaries, `0` `.ssl`; needs `.int -> .psc` transpiler + `ISO-1/2`) | `OWNER GATE` (`1,310` `<Trigger>` / `63` `<esh>` FSM ops -> `.psc` + `ISO-1/2`) | `FIT (ADAPT)` (`2,320/2,320` `100%` `SCTX` + `8,095` emb. -> ObScript-to-Papyrus AST pass) | `FIT (ADAPT)` (`3,715/3,715` `100%` `SCTX` + `8,769` emb. -> ObScript-to-Papyrus AST pass) | `FIT (1:1)` (`99.92%` `7,757/7,763` `.psc` compile w/ `16` shims; `XESP/XLOC/XLKR/XAPR/XTEL`) | `OWNER GATE` (`787` client `.pex` active; `2,652` server quest `.pex` stripped) |
| **`CF-6` Progression (`SPECIAL`, Skills, Perks, Traits)**<br>`src/fo4sf/progression/tables.py`<br>`FO4SFProgression.esm` | `FIT (ADAPT)` (`40`-pt SPECIAL, `18->13` skills `x0.5`, `0–2` Traits, `GLOB` cadence `=3`) | `FIT (ADAPT)` (`40`-pt SPECIAL, `18->13` skills `x0.5`, `0–2` Traits, `GLOB` cadence `=3`) | `GAP (SMALL)` (`6` playable Races in `race.txt`: Mutant/Ghoul/Deathclaw/Dog/Robot) | `FIT (ADAPT)` (`13` skills `Big+Small Guns -> Guns`, `93` playable `PERK`, cadence `=1`) | `FIT (1:1)` (`40`-pt SPECIAL, `13` NV skills `1:1`, `10` Traits, `175` `PERK`, cadence `=2`) | `FIT (1:1)` (`FO4SF_SpecialPool28` `GLOB` opt-in, `CNDF` Skill-OR-Perk gate, `384` `PERK`) | `GAP (SMALL)` (`401` `PCRD` cards -> passive `PERK`; `13` `LOUT` station respec rule) |
| **`CF-6 / #817` Karma & 16-State `REPU`**<br>`src/fo4sf/reputation/tables.py`<br>`FO4SFReputation.esm` | `GAP (SMALL)` (Karma `1:1`; `4` towns share `core_slot=4` in 8-slot array) | `GAP (SMALL)` (Karma `1:1`; `karmavar.txt` + `genrep.txt` towns share `core_slot=4`) | `FIT (ADAPT)` (`Brotherhood_Midwest` on `core_slot=1` + Karma) | `GAP (SMALL)` (Karma `1:1`; `8` Capital Wasteland factions share `core_slot=4/1/7`) | `GAP (SMALL)` (`16`-state math `1:1`, but **`13` `REPU`s > `8` `CORE_FACTIONS` slots** + disguise hook) | `FIT (1:1)` (`8` Commonwealth factions + restored Global Karma) | `FIT (ADAPT)` (`FO76_TIER_TO_FAME_INFAMY` `7`-tier curve -> 16-state matrix) |
| **`CF-7` Unified Dialogue & Skill Checks**<br>`src/fo4sf/dialogue/list_checks.py`<br>`FO4SFListDialogue.esm` + `#792` | `OWNER GATE` (`giq_option` list + `[Skill]` + low-`INT <= 3` fits `list_host`; `21` talking heads -> `ISO-3`) | `OWNER GATE` (`giq_option` list + low-`INT` fits `list_host`; talking heads -> `ISO-3`) | `FIT (ADAPT)` (`0` branching dialogue; `<speech_node>` barks -> `Say`/subtitles) | `GAP (SMALL)` (`list_host` fits `100%`; FO3 `%`-roll Speech vs NV deterministic `GLOB` mode) | `FIT (1:1)` (`list_host` + deterministic `[Skill N]` / `[SPECIAL N]` / `[Perk]` dual `INFO`s) | `FIT (1:1)` (`#792` `wheel_4` for 4-slot `SCEN` + `list_host` for tagged turns) | `FIT (1:1)` (Silent-player list + `8,330` deterministic `GetValue` checks) |
| **`CF-8 (1a–1c)` VATS, `BPTD` & Ammo / DT-DR**<br>`src/fo4sf/combat/tables.py`<br>`FO4SFCombat.esm` + `FO4SFCombat.dll` | `OWNER GATE` (`dt_then_dr` + `.pro` ammo mods in `TITLE_COMBAT_TABLES["FO1"]`; turn-based vs slow-time -> `ISO-1`) | `OWNER GATE` (`dt_then_dr` + `25` `.pro` ammo types; turn-based vs slow-time -> `ISO-1`) | `OWNER GATE` (`dt_then_dr` + CTB `0.25x` slow-time fits `FO4SFCombat`; camera -> `ISO-1`) | `FIT (ADAPT)` (`dr_only` `85%` cap in `TITLE_COMBAT_TABLES["FO3"]`, `8`-zone `BPTD`) | `GAP (SMALL)` (`dr_then_dt` `20%` floor `1:1`; expand `5` Starfield calibres to cover `92` `AMMO` / `54` `AMEF`) | `FIT (1:1)` (`power_law_dr` / `FO4SF` unified rule, `8`-zone `BPTD`, `V`/`N` hotkeys) | `FIT (ADAPT)` (`vats_time_scale=1.0` real-time VATS option in `TITLE_COMBAT_TABLES["FO76"]`) |
| **`CF-8 (2a)` Dual-Mode Radiation & Mutations**<br>`dotnet/RadsCore/Program.cs`<br>`FO4SFRads.esm` | `FIT (ADAPT)` (Mode B `FO4SF_RadsRule=1` stat sickness + `radiation_inc`/`dec` shim) | `FIT (ADAPT)` (Mode B `FO4SF_RadsRule=1` stat sickness + Rad-X / RadAway) | `FIT (ADAPT)` (Mode B `FO4SF_RadsRule=1` + `chems.txt` RadAway/Rad-X) | `FIT (1:1)` (Mode B `FO4SF_RadsRule=1`: `200..1000` `-END/-AGI/-STR` + Fatal `1000`) | `FIT (1:1)` (Mode B `FO4SF_RadsRule=1`: `200..1000` 5-stage `RADS` + `WATR`/ingestibles) | `FIT (1:1)` (Mode A `FO4SF_RadsRule=0`: `-10%` Max HP per `100` rads, `59` `HAZD`) | `FIT (1:1)` (Mode A `FO4SF_RadsRule=0` + `FO4SF_MutationsEnabled=1` + `StarchedGenes`) |
| **`CF-8 (2b)` Hardcore / Survival `GPOF`**<br>`dotnet/HardcoreToggle/Program.cs`<br>`FO4SFHardcore.esm` | `FIT (1:1)` (`GPOF` default `OFF` = vanilla FO1; opt-in `ON` works cleanly) | `FIT (1:1)` (`GPOF` default `OFF` = vanilla FO2; opt-in `ON` works cleanly) | `FIT (1:1)` (`GPOF` default `OFF` = vanilla FOT; opt-in `ON` works cleanly) | `FIT (1:1)` (`GPOF` default `OFF` = vanilla FO3; opt-in `ON` adds Mojave-style Hardcore) | `FIT (1:1)` (`1:1` `0..1000` `HUNG`/`DEHY`/`SLPD` 5-stage meters, ammo weight, Stimpak HoT, Doctor's Bag limb rule) | `FIT (ADAPT)` (Unified meter + fast-travel lock + ammo weight; FO4 diseases/adrenaline optional) | `FIT (ADAPT)` (Toggleable survival meters; FO76 well-fed buff variant optional) |
| **`CF-9 (2c)` Settlements, Crafting & C.A.M.P.**<br>`dotnet/WorkshopCore/Program.cs`<br>`FO4SFWorkshop.esm` | `FIT (1:1)` (`0` native workshops; optional portable C.A.M.P. kit available in Combined mode) | `FIT (1:1)` (`0` native workshops; optional portable C.A.M.P. kit) | `FIT (1:1)` (`0` native workshops; bunker quartermaster + optional C.A.M.P.) | `FIT (ADAPT)` (`0` settlements; FO3 schematic weapons map onto `WorkbenchIndustrial` `COBJ`) | `FIT (1:1)` (`291` `RCPE`campfire/reloading/workbench recipes map onto `COBJ` + `IRES`) | `FIT (1:1)` (`29` Commonwealth workshops, `18` `CMPO -> IRES` scrap pairs, `4,152` `COBJ`) | `FIT (1:1)` (`OutpostBeaconActivator` `0x2C60E9` portable C.A.M.P. + `45 m` exclusion + pack-up) |
| **`CF-9 (2d)` Dual-Form Power Armor**<br>`dotnet/PowerArmorCore/Program.cs`<br>`FO4SFPowerArmor.esm` | `FIT (ADAPT)` (`T-51b` / `Hardened PA` `.pro` -> climb-in `FURN` frame OR classic worn option) | `FIT (ADAPT)` (`APA` / `T-51b` `.pro` -> climb-in `FURN` frame) | `FIT (ADAPT)` (`Midwest PA` `.ent` -> climb-in `FURN` frame) | `GAP (SMALL)` (`21` PA `ARMO`s + `PowerArmorTraining` `PERK` gate option on frame/worn PA) | `FIT (1:1)` (Remnants/BoS PA -> climb-in `FURN`; **Salvaged NCR PA -> plain worn `ARMO` `0x81A..0x81B`**) | `FIT (1:1)` (`PowerArmorRace` + `6`-limb `BPTD` + `FusionCore` drain + outfit restore) | `FIT (ADAPT)` (`25` PA `FURN`s; optional chassis-to-inventory recall token) |
| **`CF-9` Companions, Squads & A-Life**<br>`dotnet/CompanionsCore/Program.cs`<br>`FO4SFCompanions.esm` + `FO4SFALife.esm` | `FIT (ADAPT)` (`Ian`, `Tycho`, `Katja`, `Dogmeat` -> `SQ_Followers` + `FO4SFCompanions`) | `FIT (ADAPT)` (`party.txt` stages/tactics + `Companion Nerve` -> `FO4SFCompanions`) | `FIT (1:1)` (`70` `recruits/*.ent` -> `SQ_Followers`+`SQ_Groups` w/ `FO4SF_SquadMaxCap` `GLOB`) | `FIT (1:1)` (`8` followers + Karma loyalty reaction `0x807` -> `FO4SFCompanions`) | `FIT (1:1)` (`8`-button `FO4SF_CompanionWheelMsg` `0x815` + `Companion Nerve` `0x80B` + affinity) | `FIT (1:1)` (`CA_*` `0..1000` affinity `0x807` -> `UnitedWeStand` `0x810` + `450/620 m` A-Life) | `FIT (1:1)` (C.A.M.P. Lite Allies -> `1`-slot settlement/C.A.M.P. companion assignment) |

---

## 2. Exact Per-Title Data-Table Columns Required by Each Core System

To import content from any of the seven Fallout titles without hard-coding title branches in C++ or Papyrus, per-title data packs populate the following exact schemas:

### 2.1 `StartWorld` & Quest Layer (`CF-1`, `CF-2`)
- **`StartWorld` Table (`src/fo4sf/core/start_worlds.py`):**
  `key`, `title` (`FO1|FO2|FOT|FO3|FNV|FO4|FO76`), `world_id`, `start_cell`, `surface_anchor`, `combat_title_rule` (`0..4`), `initial_karma` (`-1000..+1000`), `initial_fame` (`dict[faction_slug, 0..100]`), `squad_base_cap` (`int`), `default_background` (`EditorID`), plus *(proposed Job 3 column)* `speech_check_mode` (`"deterministic" | "roll_pct"`) and `perk_cadence_default` (`1 | 2 | 3`).
- **Per-Title Quest Descriptor Table:**
  `title`, `source_quest_id` (`FormID` hex, `quests.txt` row, or `.mis` name), `target_edid`, `priority`, `flags` (`StartGameEnabled`, `AllowRepeatedStages`, `Radiant`), `stages` (`list[indx]`), `objectives` (`list[qobj_idx]`), `gvar_or_cvar_bindings` (`dict[var_name, global_edid]` for `FO1`/`FO2`/`FOT`), `attached_script`, `known_bug_ledger_id`.

### 2.2 Script Event & Function Emulation Map (`CF-5`)
| Source Title Era | Source Event / Callback | Target Starfield Papyrus Event / Helper (`FO4SF_Shim_*`) |
| :--- | :--- | :--- |
| **FO1 / FO2 (`.int` SSL)** | `start`, `map_enter_p_proc`, `map_update_p_proc`, `map_exit_p_proc` | `OnInit()`, `OnCellAttach()`, `OnTimer()` (`map_update` tick), `OnCellDetach()` |
| **FO1 / FO2 (`.int` SSL)** | `talk_p_proc`, `critter_p_proc`, `combat_p_proc`, `timed_event_p_proc` | `DIAL`/`INFO` topic activation, AI `PACK` + `OnTimer(aiTimerID)` (`add_timer_event`) |
| **FO1 / FO2 (`.int` SSL)** | `use_p_proc`, `use_skill_on_p_proc`, `use_obj_on_p_proc`, `pickup_p_proc`, `destroy_p_proc`, `damage_p_proc`, `spatial_p_proc` | `OnActivate`, `FO4SF_SkillUseActivator`, `OnItemAdded`, `OnDeath`, `OnHit`, `OnTriggerEnter` |
| **Tactics (`.mis` FSM)** | `<Trigger>` (`before_first_tick`, `Always`, `Speech Occured`, `All Alive at Exit Grid`, `Quantity - Team`) | `Quest.OnQuestInit()`, `OnTimer()` poll on `RefCollectionAlias` alive count, `OnTriggerEnter` exit-grid volume |
| **FO3 / FNV (`SCTX` ObScript)** | `Begin GameMode` (quest vs object), `Begin MenuMode [N]` | Quest/Object `OnTimer(kGameModeTick)` (activated on `OnQuestInit` / `OnCellAttach`, paused on `OnCellDetach` so unloaded objects never spin CPU!), `Utility.IsGameMenuPaused()` |
| **FO3 / FNV (`SCTX` ObScript)** | `Begin OnActivate`, `OnTriggerEnter`, `OnTriggerLeave`, `OnLoad`, `OnDeath`, `OnHit`, `OnAdd`, `OnEquip`, `ScriptEffectStart/Update/Finish`, `OnPackageStart/End/Done`, `SayToDone` | Direct `1:1` Starfield `ObjectReference`, `Actor`, `ActiveMagicEffect`, and `Package` events |
| **FO4 (`Base.zip` `.psc`)** | `7,763` scripts (`97.32%` identical calls + `2.54%` `FO4SF_Shim_*` + `0.13%` `FO4SF_NativeBridge`) | Direct v4.2 `.pex` compilation via `compile_census.py --with-shims` |

### 2.3 Progression, Karma & 16-State Reputation (`CF-6`, `#817`)
- **Progression Table (`src/fo4sf/progression/tables.py`):**
  `title`, `source_perk_id`, `edid`, `is_trait` (`bool`), `is_background` (`bool`), `ranks` (`1..N`), `min_level`, `req_special` (`dict[STR..LCK, int]`), `req_skills` (`dict[Skill13, int]`, mapped via `Small/Big Guns -> Guns`, `First Aid/Doctor -> Medicine`, `Traps/Throwing -> Explosives`, `Steal -> Sneak`, `Outdoorsman -> Survival`), `entry_point_data`.
- **Reputation & Karma Table (`src/fo4sf/reputation/tables.py`):**
  `title`, `faction_id`, `source_repu_or_gvar_id` (`REPU FormID` in FNV, `GVAR_TOWN_REP_*` in FO1/FO2, `FACT FormID` in FO3/FO4/FO76), `fame_av_id`, `infamy_av_id`, `state_glob_id`, `rival_faction_id`, `disguise_armor_flst_id` (FNV faction armor `FLST`), `karma_enabled` (`bool`).

### 2.4 Companions & Warfare Squads (`CF-9`)
- **Companion / Recruit Definition Table:**
  `title`, `npc_edid`, `source_form_or_ent_id`, `slot_class` (`"story_humanoid" | "story_nonhuman" | "warfare_recruit" | "camp_ally"`), `moral_alignment` (`"Good" | "Neutral" | "Evil"` -> binds `FO4SF_CompanionMoralReaction` `0x807`), `faction_slug` (goodwill gate), `recruit_rank_tier` (`0..4`), `hire_cost_caps` (`int`), `affinity_perk_edid`, `combat_prefer_ranged` (`bool`).

### 2.5 Gunplay, `BPTD`, Ammo Subtypes, Radiation, Hardcore & Workshops (`CF-8`, `CF-9`)
- **Weapon & Calibre Subtype Table (`src/fo4sf/combat/tables.py`):**
  `title`, `source_ammo_id` (`AMMO FormID` or `.pro` PID), `calibre_family` (`standard_ballistic | shotgun | energy | heavy_ordnance`), `starfield_base_ammo_id`, `subtype_slot` (`0..3`), `dmg_mult`, `dt_pierce`, `dt_mult`, `spread_mult`, `wear_mult`, `ammo_weight_lb` (for `FO4SFHardcore.esm` `WeightedAmmoList`), `reloading_ires_recipe`.
- **Armor & Power Armor Table (`FO4SFCombat` + `FO4SFPowerArmor`):**
  `title`, `source_armo_id`, `pa_form_mode` (`"none" | "climb_in_frame" | "worn_salvaged_heavy"`), `requires_pa_training_perk` (`bool`), `ballistic_dt`, `ballistic_dr_pct`, `energy_dt`, `energy_dr_pct`.
- **Radiation & Survival Consumables Table (`FO4SFRads` + `FO4SFHardcore`):**
  `title`, `source_item_or_watr_id`, `raw_rads`, `rad_resist_bonus`, `rad_cure_amount`, `hunger_relief`, `thirst_relief`, `sleep_relief`, `is_doctors_bag` (`bool`).
- **Workshop / Crafting / Scrap Table (`FO4SFWorkshop`):**
  `title`, `source_misc_or_rcpe_id`, `kind` (`"scrap_junk" | "bench_recipe"`), `bench_keyword` (`Industrial | Chemlab | Cooking | Weapons | Armor`), `ires_vector` (`tuple[(archetype_0_to_17, count), ...]`), `req_skill_or_perk`.

---

## 3. Non-Fit Flags & Concrete Engineering Options for the Owner

### 3.1 Isometric & Turn-Based Titles (`Fallout 1`, `Fallout 2`, `Fallout Tactics`) — **Awaiting Owner `ISO` Decisions**
As established in `docs/plan/core-and-assets-plan.md` (PR `#806`) Section `0.2`, all three classic titles remain explicitly marked as **needing the owner's `ISO` decisions** before volume world conversion:
1. **`ISO-1` — Turn-Based Hex AP Combat vs Real-Time + Slow-Time VATS (`FO1`, `FO2`, `FOT`):**
   - *Why it diverges:* Starfield's physics, Havok ragdolls, animation graphs, and AI packages run in continuous real time; FO1/FO2 `.map` combat freezes non-acting critters on a 200x200 hex queue.
   - *Options:* **(A — Recommended)** Play in 1st/3rd-person real time using our unified `FO4SFCombat` `8`-zone slow-time VATS (`25%` time scale, matching *Tactics* CTB) + tactical squad commands (`100%` core reuse); or **(B)** build a top-down camera + SFSE global AI/time-freeze turn scheduler.
2. **`ISO-2` — 2D `.FRM` / `.til` Isometric Sprites vs 3D `.mesh` / `.btd` Worlds (`72` FO1 `.map`, `155` FO2 `.map`, `103` FOT `.mis`):**
   - *Why it diverges:* Zero 3D geometry or heightmaps exist in `.DAT` or `.bos` archives.
   - *Options:* **(A — Recommended)** Auto-stamp `.map`/`.mis` wall/scenery/blocker grids onto `.btd` heightmaps using 3D architectural kits already converted from FO3/FNV/FO4/Starfield (vaults, adobe, desert ruins, bunkers) + landmark pass; or **(B)** hand-author key story hubs only.
3. **`ISO-3` — FO1/FO2 Talking Heads (`21` heads, `2,630` `.lip` files) & `.int` Bytecode (`2,395` `.int` scripts, `0` `.ssl`):**
   - *Options:* **(A — Recommended)** Standard 3D NPCs in `DialogueMenu` (`list_host`) + deterministic offline `.int -> .psc` SSL opcode transpiler (`195` distinct ops verified); or **(B)** render 2D `.frm` talking-head portraits in a UI inset widget during `list_host` dialogue.

### 3.2 3D Title Divergences & Owner Options (`FO3`, `FNV`, `FO76`)

1. **FNV Faction Armor Disguises (`FalloutNV.esm` Outfit Scripts vs `FO4SFReputation.esm`):**
   - *Divergence:* `FO4SFReputation.esm` drives `FACT` reactions from permanent `Fame`/`Infamy` `AVIF`s, whereas New Vegas temporarily overrides faction Fame/Infamy to *Neutral* while wearing faction armor (and lets guard/dog `Sentry` actors see through disguises).
   - *Options:* **(A — Recommended)** Add an `OnItemEquipped`/`OnItemUnequipped` faction-armor `FLST` layer in `FO4SFReputation` that snapshots real `Fame`/`Infamy` and applies temporary Neutral `FACT` reaction until unequipped or exposed; or **(B)** omit disguise overrides and treat faction armor as plain `ARMO`.
2. **FO3 Percentage Speech Rolls vs FNV/FO76 Deterministic `[Skill >= N]` Thresholds (`CF-7`):**
   - *Divergence:* `FO4SFListDialogue.esm` implements New Vegas's deterministic `[Speech 50]` pass/fail check (`0%` RNG savescumming), whereas `Fallout3.esm` (`650` `INFO` AV checks) and `Fallout4.esm` use percentage Speech rolls.
   - *Options:* **(A — Recommended)** Standardize all silent-player list checks (`FO1`, `FO2`, `FO3`, `FNV`, `FO76`) on deterministic `[Skill N]` thresholds (converting FO3 Speech difficulty tiers to `25/40/55/75/90` thresholds), with an optional `GLOB` (`FO4SF_SpeechRollMode`) for purist FO3 `%` rolls; or **(B)** keep FO3 checks RNG-rolled by default.
3. **FO3 Vault 101 Childhood Stages (`CG01..CG03`: Toddler & Age-10 Player Scale/Controls):**
   - *Divergence:* `CG01` (toddler in playpen) and `CG02`/`CG03` (childhood birthday & G.O.A.T.) rely on child race/scale and restricted HUD/weapon states, whereas `CG04` (`0x014E86`) is the adult Vault 101 escape ending at the exit tunnel rebuild prompt.
   - *Options:* **(A — Recommended for first FO3 slice)** Start playable FO3 conversion at `CG04` (`Vault101` adult escape -> Wasteland exit respec, matching `START_WORLD_TABLE["vault101"]`) with a concise interactive memory/G.O.A.T. tag-skill terminal before stage `10`; or **(B)** convert `CG01..CG03` in full using camera-height/speed scaling.
4. **Tactics Playable Non-Human Squad/Player Races (`6` Races in `race.txt`: Super Mutant, Ghoul, Deathclaw, Dog, Robot):**
   - *Divergence:* Starfield player chargen uses `HumanRace` (`0x00347D`).
   - *Options:* **(A — Recommended)** Support non-human *Tactics* recruits (`Super Mutant`, `Ghoul`, `Robot`, `Dog`, `Deathclaw`) as **squad followers** on their converted creature/robot `RACE`s while keeping the player `Human` (with optional Ghoul cosmetic/perk trait); or **(B)** defer non-human playable races.
5. **Fallout 76 Server-Stripped Quest Scripts (`2,652 / 7,234` Empty `.pex` Stubs) & `REL-60` Gate:**
   - *Divergence:* `SeventySix.esm` ships all `2,232` `QUST`, `40,182` `DIAL`, and `65,818` `INFO` records, but `SeventySix - MiscClient.ba2` strips bytecode from `2,652` server-side quest/scene `.pex` files (`0` instructions).
   - *Options:* Keep **100% gated on owner `REL-60` decision**; if authorized later, reconstruct offline single-player quest stage drivers from `SeventySix.esm`'s intact `QUST` `INDX`/`QOBJ`/`VMAD` property graphs and `INFO` `CTDA` conditions rather than `.pex` translation.

---

## 4. Concrete Small Code & Data-Table Gaps (Job 3 Fit Candidates)

Inspection of `gemini/core-candidate` (`cd03411a`) against the 8-game census identified **five small, isolated code/table gaps** suitable for small Job 3 PRs (each keeping Fallout 4 behavior byte-for-byte identical):

1. **`GAP-J3-01` — `progression/tables.py` vs `reputation/tables.py` 16-State `REPU` Matrix & Tier Cutoff Drift (`CF-6` / `#817`):**
   - *Exact Location:* `src/fo4sf/progression/tables.py` (`REPU_MATRIX` lines `107–112` and `_repu_axis_tier` line `251`) vs `src/fo4sf/reputation/tables.py` (`DEFAULT_TIER_THRESHOLDS = (15.0, 40.0, 75.0)` line `23` and `NV_16_STATE_MATRIX` lines `113–134`).
   - *Concrete Defect:* `progression/tables.py` uses `45.0` instead of `40.0` for the `Medium` cutoff and transposes off-diagonal Fame/Infamy titles (returning `"Sneering Punk"` instead of `"Mixed"` at `(fame=1, infamy=1)` and `"Mixed"` instead of `"Unpredictable"` at `(fame=2, infamy=2)`).
   - *Small Fix:* Delegate `progression/tables.py` `evaluate_faction_repu` directly to `reputation/tables.py`'s `NV_16_STATE_MATRIX` and `(15.0, 40.0, 75.0)` thresholds so both plugins/modules agree `16/16`. Zero FO4 impact.

2. **`GAP-J3-02` — `FO4SFReputation` 8-Slot `CORE_FACTIONS` Collision on New Vegas's `13` `REPU` Records (`#817`):**
   - *Exact Location:* `src/fo4sf/reputation/tables.py` (`CORE_FACTIONS` lines `64–96` vs `TITLE_REPUTATION_TABLES["FNV"]` lines `196–210`).
   - *Concrete Defect:* Because `CORE_FACTIONS` currently defines only `8` runtime slots (`0..7`), `7` distinct New Vegas `REPU` records (`Goodsprings`, `Primm`, `Novac`, `Freeside`, `TheStrip`, `Boomer`, `WhiteGloveSociety`) all map to `core_slot: 4` (`Settlers`), and `Khans` (`REPU 0x11989B`) + `PowderGanger` collide on `core_slot: 7` (`Outlaws`).
   - *Small Fix:* Widen `FO4SFReputation` faction slot capacity (or add a `local_slot` / per-title bank index `0..15`) while keeping slots `0..7` at identical FormIDs `0x810..0x877` so FO4's 8 slots remain byte-identical.

3. **`GAP-J3-03` — `combat/tables.py` Calibre Table Missing Source `AMMO` / `AMEF` Mapping Column & Additional Ballistic/Energy Families (`CF-8`):**
   - *Exact Location:* `src/fo4sf/combat/tables.py` (`CALIBRE_FAMILIES` lines `205–236`).
   - *Concrete Defect:* `CALIBRE_FAMILIES` covers `5` Starfield base `AMMO` forms (`7.77mm`, `11mm`, `Shotgun`, `Laser`, `.50 Cal`, where `.50 Cal` reuses `FO4SF_Ammo777_JHP`/`PlusP` strings) and lacks a `source_ammo_map` column binding FO3 (`33` `AMMO`), FNV (`145` `AMMO`, `80` `AMEF`), FO4 (`106` `AMMO`), and FO1/2 `.pro` calibres onto Starfield calibre families.
   - *Small Fix:* Add dedicated `.50 Cal` JHP/+P subtype IDs and a read-only `TITLE_AMMO_CALIBRE_MAP` lookup table in `src/fo4sf/combat/tables.py` without altering existing FO4/Starfield `0x82C..0x836` FormIDs.

4. **`GAP-J3-04` — `start_worlds.py` Missing `perk_cadence_default`, `rads_rule_default`, and `speech_check_mode` Columns (`CF-1` / `CF-6` / `CF-8`):**
   - *Exact Location:* `src/fo4sf/core/start_worlds.py` (`StartWorldDescriptor` lines `16–28`).
   - *Concrete Defect:* `StartWorldDescriptor` seeds `combat_title_rule`, `initial_karma`, `initial_fame`, and `squad_base_cap`, but does not yet carry `perk_cadence_default` (`3` for FO1/FO2/FOT, `1` for FO3/FO4, `2` for FNV), `rads_rule_default` (`0` HP-cap for FO4/FO76 vs `1` stat-sickness for FO1/2/Tactics/FO3/FNV), or `pa_training_required` (`True` for FO3, `False` for FO4/FNV salvaged).
   - *Small Fix:* Add defaulted fields (`perk_cadence_default: int = 2`, `rads_rule_default: int = 0`, `pa_training_required: bool = False`) to `StartWorldDescriptor` — `100%` backward-compatible with `vault111`.

5. **`GAP-J3-05` — `dotnet/NewGame` Hardcoded `SpecialPoints = 21` (`28`-pt FO4 Pool) vs `CF-6` `40`-Point Default (`CF-1` / `CF-6`):**
   - *Exact Location:* `dotnet/NewGame/Program.cs` line `148` (`SpecialBase = 1, SpecialPoints = 21` -> `28` total) vs `src/fo4sf/progression/tables.py` line `20` (`SPECIAL_POOL_DEFAULT = 40`, `FO4SF_SpecialPool28 = 0`).
   - *Concrete Defect:* Vault 111's standalone terminal allocator still defaults to `28` points on `0x810..0x816` unless `--no-special` hands creation off to `FO4SFProgression.esm` (`0x800..0x806`).
   - *Small Fix:* Keep `FO4SFNewGame` default CLI flags byte-identical for `#803` walk stability, and add `--special-points 33` (40 total) / `FO4SFProgression` handoff option in `make_newgame.py` once `#803` walk merges.
