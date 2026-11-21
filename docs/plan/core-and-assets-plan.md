# Core Systems Finish Line & Multi-Title Asset Plan

- **Baseline `main`:** `713ed97a35440c9c5058d3383a55a3da8427e215` (verified against GitHub on `2026-11-16`)
- **Scope:** Phase A master consolidation plan for finishing the shared Fallout gameplay core in Starfield first, resolving open branch collisions, and sequencing volume asset conversion across all installed Fallout titles without rework.
- **Evidence Hygiene:** Every file count, archive version, record signature count, script total, and merge-conflict line below was measured directly from read-only local game headers/tables and repository git history; unverified gameplay tuning targets (such as squad caps and upkeep percentages) are explicitly marked as proposals for owner balancing. Zero game text, dialogue strings, decompiled bodies, machine-specific paths, or third-party mod names are included.

---

## Settled Direction (16 November 2026)

1. **Finish the Core before volume assets:** Parallel feature slices were colliding on shared plugin, script, UI, and installer files. All Fallout core mechanics must first work together in Starfield as one modular, data-driven base (`FO4SF` core bundle) before volume world/interior/content conversion expands.
2. **Vault 111 clean exit comes first:** PR `#803` (`647635c898cddcea609234c8946325059dea6c87`) + Group 4 quest holds `#802` (`b129e901920e3f8a14e52c4409b01c2bac06699a`) are staged and installed for the walk test; any regression reported from that walk outranks all other work.
3. **Starfield's Star Map is blocked completely:** Players never open Starfield's surface, planet, or galaxy star map. Intra-world fast travel and inter-world travel between wastelands run exclusively through our Pip-Boy `MAP` page and scripted travel chokepoints.
4. **Hold off every unneeded Starfield quest:** Continue testing the remaining Starfield cold-start quest groups (`radiant: 9`, `ships: 21`, `system: 4`) after `#802` (`48`) until only the `5` Warfare squad quests and `7` core engine plumbing quests remain running (`195` of `207` cold-start quests stopped).
5. **Designed once for all titles:** Every core system is designed from day one to serve **all seven Fallout titles** — *Fallout* (1), *Fallout 2*, *Fallout Tactics*, *Fallout 3*, *Fallout: New Vegas*, *Fallout 4*, and *Fallout 76* — running on *Starfield* as the engine.
6. **Confirmed Progression & Mechanics Decisions (`#806` `#issuecomment-6930665309`, 16 Nov):**
   - **Working-plan acceptance:** This plan is accepted as the active working plan, unblocking Phase B PR construction immediately; Grok `CLEAR` remains required before merging any slice (and Grok review or Claude (PC) go-ahead gates the first in-game test of `CF-6`).
   - **Progression (`Section 0.1`):** **Backgrounds and Traits** (not trades or professions) on a **New Vegas-style base**: **`40`-point S.P.E.C.I.A.L.** pool (`28`-point preset kept only as an off-by-default `GLOB`), `13` Skills, **`0–2` Traits** at creation with **one free respec** at the Vault exit, and **Perk cadence driven by a `GLOB`** (`1` per `2` levels default, undecided/tunable with zero fixed-cadence assumptions).
   - **Karma AND Faction Reputation (independent axes):** Both built simultaneously — global `Karma` (`[-1000..+1000]`, FO3 style: dialogue checks, moral-aligned companions, endings) **plus** per-faction `Fame`/`Infamy` (`REPU`, NV style: drives `FACT` disposition and prices, never karma — *"you can be a bad person but still be liked by certain groups"*).
   - **Radiation (both rules behind one gameplay switch):** Mode A caps Max HP (`FO4` rule) and Mode B applies 5-stage rad-sickness stat penalties (`FO3`/`NV` rule), sharing one switch, one RadAway cure path, and one Pip-Boy `STAT` display; FO76-style Mutations (`PERK`s) sit behind a separate option (`OFF` by default).
   - **Power Armor (both forms):** Real Power Armor uses the FO4 climb-in frame (`FURN` + `PowerArmorRace` with `6` limb `AVIF`s on `BPTD` + `FusionCore` drain); FNV salvaged NCR power armor stays plain worn `ARMO` with no frame and no climb-in.
   - **Warfare Squad Cap & Cost Proposal (earned-cap & logistical upkeep proposal for owner balancing, not blind *Tactics* `6`):** Proposed base active squad cap of **`2`**, rising by **`+2` to `4` max** (`GLOB`-tunable) only at top veteran/legend standing, gated by faction `REPU` goodwill, player rank > recruit rank, and `Karma` alignment, and balanced by real ammo/medical inventory upkeep, bleedout/mortality stakes, contract/XP splits, and carry encumbrance (all numeric thresholds `GLOB`-driven for owner tuning).
7. **Converted-Quest Known-Bug Rule (`#806` `#issuecomment-6932576663`, 16 Nov):** Converting the original games' quest records and scripts verbatim also copies their shipped bugs (broken stages, stuck NPCs, unreachable objectives, unfixed script errors). Every converted quest carries a per-quest known-bug list (drawn from the shipped games' known-issue lists and community unofficial-patch changelogs — bug names and plain descriptions only); each bug is evaluated case by case and fixed either directly by us or by studying the documented fix description (reading documented changes only, **never** copying any third-party mod's files into Git, with any external download gated on explicit owner approval per download); and every converted quest's PC card states which known bugs were fixed, which were left, and how to reproduce each.

---

## 0. Multi-Title Architecture: Progression Design & Isometric Boundaries

### 0.1 Confirmed Progression Design: Backgrounds & Traits on a New Vegas-Style Base (`BASE-PLUS-DATA`)

> [!IMPORTANT]
> **Gate Status (`16 Nov`):** Owner sign-off and questionnaire decisions are recorded (`#806` `#issuecomment-6930665309`). `CF-6` is scheduled after `CF-8`/`CF-9` (`2a–2d`), and its first in-game test waits for Grok's review on `#806` or explicit Claude (PC) go-ahead on the `CF-6` PR.

#### Why This Maps Natively onto Starfield's Engine Records
Read-only inspection of `Starfield.esm` (`3,829,246` records), `FalloutNV.esm` (`465,016` records), and `Fallout4.esm` (`1,549,276` records) shows Starfield already provides the exact record primitives required without C++ struct patching:
- **`AVIF` (Actor Value Info — `1,107` in `Starfield.esm`):** Arbitrary custom Actor Values persist in saves and evaluate in `CTDA`/`CNDF` conditions and `PERK` entry points (`FO4SFNewGame.esm` already proves `7` custom S.P.E.C.I.A.L. `AVIF`s; `RadsProbe` proved custom `DamageIsPositive` `AVIF` persistence).
- **`PERK` (`502` in `Starfield.esm`):** Starfield's `ChargenMenu.swf` natively represents **both** Backgrounds (`21` `Background*` `PERK`s, each granting 3 rank-1 starting skills and unlocking `[Background]` dialogue tags) and Traits (`17` `TRAIT_*` `PERK`s, selectable at creation with `[Trait]` dialogue tags) as standard `PERK` records — the exact same architecture `FalloutNV.esm` uses for its `10` creation traits (`PERK` `DATA.isTrait = 1` in `trait_menu.xml`).
- **`CNDF` (Condition Forms — `899` in `Starfield.esm`) & `PERK` Entry Points (`0..157`):** Starfield preserves `156` of Fallout 4's `158` perk entry point indices (`character-systems.md`), plus `PlayerSkills` (`0x2C59E4`, kept running in the core engine boundary).

#### How S.P.E.C.I.A.L., Skills, Perks, Backgrounds, and Traits Work Together

| Layer | Core Rule (`SHARED` Mechanics) | Starfield Record Backing | Per-Title Data Adaptation (`BASE-PLUS-DATA`) |
| :--- | :--- | :--- | :--- |
| **1. S.P.E.C.I.A.L. (`7` Attributes)** | **`40` points at creation** (`5` base each + `5` pool, NV standard); `28`-point FO4 preset kept **only** as a `GLOB` option (`FO4SF_SpecialPool28 = 0`, off by default). Range `1–10` base (`1–15+` effective with gear/chems). Drives derived `CarryWeight` (`STR`), `Perception` compass/VATS accuracy (`PER`), `MaxHP` & rad/disease resist (`END`), `Companion Nerve` & command leadership (`CHA`), skill points/level (`INT`), `ActionPoints`/O2 & reload (`AGI`), and crit/loot (`LCK`). | `7` core `AVIF` forms (`FO4SF_Special_Strength..Luck`) + `GLOB` pool selector + constant `SPEL`/`MGEF` ability on player alias computing derived stats. | Shared across all `7` Fallout titles. FO76 punch-card respec (`LOUT`, `13` records in `SeventySix.esm`) is exposed only as an optional C.A.M.P./settlement respec station rule, off in Hardcore. |
| **2. Skills (`13` NV Base Skills)** | `13` skills (`1–100`): `Barter`, `Energy Weapons`, `Explosives`, `Guns`, `Lockpick`, `Medicine`, `Melee Weapons`, `Repair`, `Science`, `Sneak`, `Speech`, `Survival`, `Unarmed`. Initial value `= 2 + (2 x Governing SPECIAL) + ceil(LCK / 2)`. Level-up grants `10 + floor(INT / 2)` skill points (`Educated` adds `+2`). **3 Tag Skills** receive `+15` at creation. | `13` core `AVIF` forms (`FO4SF_Skill_*`) + deterministic `CTDA`/`CNDF` evaluators for dialogue, terminals, locks, and recipes. | **FNV:** `1:1`. **FO3 (`13` skills):** `Small Guns` + `Big Guns` -> `Guns` (with Heavy Weapons STR/perk tier); adds `Survival`. **FO1/FO2/Tactics (`18` skills, `0–200%/300%`):** scaled `x 0.5` into `1–100`; `First Aid`+`Doctor` -> `Medicine`, `Traps` -> `Explosives`, `Steal` -> `Sneak`, `Outdoorsman` -> `Survival`, `Throwing` -> `Explosives`, `Gambling` -> `Barter`+`LCK`. **FO4/FO76 (`0` skills):** rank-gated perks (`Gun Nut`, `Locksmith`, `Hacker`, `Science!`) unlock via `Skill >= 25/50/75/100` OR perk ownership (`CNDF` OR-gate). |
| **3. Backgrounds (`Choose 1` at Start)** | Authored Wasteland origin chosen in creation (replaces Starfield's `21` space backgrounds; **never** trades/professions). Grants: (a) `+10` to `3` signature Skills (stacking with player's `3` personal Tag Skills), (b) starting outfit/gear kit, (c) permanent `[Background]` `PERK` flag for dialogue/world checks, and (d) optional faction-start spawn & initial `REPU` disposition in Combined/Warfare mode. | `PERK` records (`FO4SF_BG_*`) registered in our creation `FLST`; `DialogueMenu` natively displays `[Background]` on `INFO` lines conditioned on `HasPerk`. | Core ships game-neutral archetypes (`Vault Dweller`, `Wasteland Scavenger`, `Caravan Guard`, `Field Medic`, `Brotherhood Scribe/Initiate`, `Enclave Remnant`, `Tribal Hunter`, `Desert Ranger`, `Minuteman Volunteer`) + per-title pack backgrounds (`Courier`, `Lone Wanderer`, `Chosen One`, `Warrior`, `76 Resident`). |
| **4. Traits (`Choose 0–2` at Start)** | Confirmed: **`0` to `2` Traits** at creation (every upside paired with a trade-off), with **one free respec at the Vault / opening exit** rebuild prompt. | `PERK` records (`FO4SF_Trait_*`) combining `PERK` entry points + passive `SPEL` abilities + `[Trait]` dialogue conditions. | Unifies FO1/FO2/Tactics/FNV traits (`Small Frame`, `Trigger Discipline`, `Fast Shot`, `Kamikaze`, `Heavy Handed`, `Four Eyes`, `Good Natured`, `Skilled`, `Wild Wasteland` toggle) with Starfield-inspired world/squad traits (`Taskmaster`-style crew buff, `Wanted`-style bounty hunter squads, `Terra Firma`-style interior/exterior grit). |
| **5. Perks (`GLOB`-Driven Cadence)** | **Cadence is undecided ("we will see") and purely `GLOB`-driven (`FO4SF_PerkCadenceLevels = 2`, default `1` Perk per `2` levels):** changeable to `1`, `2`, `3`, etc. at runtime with **zero rebuild and zero design assumptions** that cadence is fixed. Perks require `Level`, `S.P.E.C.I.A.L.`, and `Skill` minimums — never a 70-cell SPECIAL-only grid alone and never FO76 RNG card packs (`PPAK`). Starfield's vanilla skill-point HUD prompt is suppressed; leveling queues a Pip-Boy `STAT -> Perks` allocation whenever `(Level % Cadence) == 0`. | `GLOB` `FO4SF_PerkCadenceLevels` + multi-rank `PERK` records (`FO4SF_Perk_*`) using Starfield's native rank blocks (`character-systems.md` P1) + `PERK` entry points `0..157`. | Per-title `PERK` packs import FO3 (`61` playable), FNV (`101` playable), FO4 (`323` playable, mapped from NNAM rank chains into rank blocks), FO1/2/Tactics (`PERK.MSG` / `perks.txt`), and curated FO76 non-online perks (`PCRD` -> passive `PERK`). |
| **6. Karma & Faction Reputation (`2` Independent Axes)** | **Both active simultaneously and decoupled:** (a) **Global `Karma` (`[-1000..+1000]`, FO3 style):** moral axis (`Very Evil`..`Very Good`) gating karma-specific dialogue, moral-aligned companion loyalty, and ending slides; (b) **Per-Faction `Fame` & `Infamy` (`REPU`, NV 16-state matrix):** drives `FACT` hostility/ally disposition, disguises, and vendor prices — **never** driven by `Karma` (*"you can be a bad person but still be liked by certain groups"*). | `FO4SF_Karma` `AVIF`/`GLOB` + per-faction `Fame`/`Infamy` `GLOB`/quest arrays synced to `FACT` combat reactions. | **FNV:** `13` `REPU` + `Karma` `1:1`. **FO3:** `Karma` `1:1` + major faction `REPU` added (`BoS`, `Outcasts`, `Enclave`, `Slavers`, `Rivet City`, `Megaton`). **FO1/2/Tactics:** `VAULT13.GAM`/`genrep.txt` town reps -> `REPU` + `Karma`. **FO4/76:** `Minutemen`/`BoS`/`Railroad`/`Institute`/Raider/Settler standings -> `REPU` + restored `Karma` triggers on theft/murder/charity. |

#### How Backgrounds & Traits Expand Warfare Squads (Proposed Earned-Cap & Upkeep Rules), Factions, Settlements & Crew
1. **Warfare Squad Cap, Recruitment Gates & Logistical Cost Proposal (`SQ_Followers` `00D773` + `SQ_Groups` `1A9565` — Unverified Design Proposal for Owner Balancing, Not Blind *Tactics* `6`):**
   - **Proposed Earned Cap (`GLOB`-Tunable, Proposed Default `2` -> Max `4`):** Do **not** grant `6` soldiers freely. Proposed base active squad cap is **`2`** (`FO4SF_SquadBaseCap = 2`: e.g. `1` companion + `1` recruit or `2` recruits; `Lone Wanderer` trait drops to `0` for solo buffs). Reaching top veteran/legend standing (`CHA >= 8` + high-rank Leadership Perk / "Folk Hero"-tier milestone) is proposed to unlock **`+2` slots up to `4` max** (`FO4SF_SquadMaxCap = 4`; owner-tunable via `GLOB` without code changes).
   - **Three Recruitment Gates (Stopping Free Fireteam Snowballing):**
     1. *Faction Goodwill (`REPU`):* Recruits from a faction require `Accepted` / `Friendly` or higher faction `Fame/Infamy` standing (mercenaries/drifters substitute an upfront Caps signing fee).
     2. *Rank / Level Hierarchy:* Player rank tier (`Rookie -> Regular -> Veteran -> Elite -> Legend`) must **exceed** the NPC's tier — a low-level player cannot recruit Veteran Rangers or Paladins.
     3. *Moral (`Karma`) & Personal Loyalty:* Good-aligned settlers/soldiers refuse low-`Karma` players (while Raider/Outlaw/Merc recruits tolerate or prefer negative `Karma`); friendly fire or abandoning downed squadmates tanks personal loyalty, causing desertion or hostility.
   - **Logistical Upkeep & Anti-Trivialization Costs (Proposal for Owner Tuning):**
     1. *Real Material Upkeep:* Recruited squadmates consume **real ammo** from their inventory (falling back to sidearm/melee when empty), require player-supplied **Stimpaks / Doctor's Bags** to heal/uncripple, and consume food/water when Hardcore is ON.
     2. *Bleedout & Mortality:* Generic Warfare recruits are **mortal** (timed bleedout requiring revival or permanent loss; named story companions follow a Hardcore mortality `GPOF` toggle).
     3. *Bounty/Contract Cut, XP Split & Encumbrance:* Hired guns are proposed to take a configurable share (proposed initial default `-15%` per merc via `GLOB`, owner-tunable) of contract/bounty Caps rewards, split combat XP when landing kills without player contribution, and suffer real carry-weight movement slowdown when overloaded with scavenged loot. Leadership Backgrounds/Perks scale `Companion Nerve` (`+5%` damage/resist per `CHA`) and unlock `SQ_Groups` tactical stances (`Hold`, `Suppress`, `Flank`, `Regroup`, `Loot Policy`).
2. **Faction Starts & Initial `REPU` Dispositions:**
   - In Story mode, New Game starts in Vault 111 (`#803`, or the chosen title's story opening) and Background sets lore/dialogue tags + `+10` skill bonuses only. In Combined / Warfare mode (`combined-core.md` `CC-51`), Faction Backgrounds set starting `REPU` Fame/Infamy (`Idolized`/`Accepted` with home faction, `Shunned`/`Vilified` with rivals) and route `FO4SFNewGame`'s start-world descriptor directly to that faction's garrison.
3. **Settlements, C.A.M.P.s & Caravans:**
   - Engineering/Salvage/Homestead Backgrounds and Traits modify `CMPO -> IRES` junk-breakdown efficiency, unlock specialist settlement buildings/defenses early, grant `+1` portable C.A.M.P. beacon (`OutpostBeaconActivator` `002C60E9`) budget tier, and improve off-screen caravan survival in A-Life (`L2` route simulation).
4. **Follower & Crew Specialist Roles:**
   - Adapts Starfield's outpost/ship crew role bonuses (`SQ_Crew` patterns rebuilt under our `FO4SF_` namespace) so recruited followers assigned to a settlement, C.A.M.P., or active squad apply background-synergized role perks (`Field Medic` boosts clinic healing/chems, `Tech Scribe` boosts turret/power output, `Scout` extends A-Life recon/marker reveal radius).

---

### 0.2 Isometric & Turn-Based Titles (*Fallout 1*, *Fallout 2*, *Fallout Tactics*): Plain Capabilities, Limits & Owner Decisions

Read-only disk inspection of `Fallout` (`MASTER.DAT` v1: `19,784` entries + `CRITTER.DAT`: `5,459` entries; `0.55 GiB`), `Fallout 2` (`master.dat` v2: `23,140` entries + `critter.dat`: `7,120` entries; `0.55 GiB`), and `Fallout Tactics` (`40` `core\*.bos` PKZIP archives: `36,470` entries; `1.57 GiB`) establishes the exact boundary:

- **What the Shared Core Gives FO1, FO2 & Tactics Out of the Box:**
  1. **Character Sheet & Combat Math:** All `7` S.P.E.C.I.A.L. stats, `18 -> 13` mapped Skills, Traits (`TRAIT.MSG` / `traits.txt`), Perks (`PERK.MSG` / `perks.txt`), Karma & town/faction `REPU` (`VAULT13.GAM`, `karmavar.txt`, `genrep.txt`), `.PRO` / `.ent` weapon damage, range, AP cost, DT/DR armor stats, and FO1/FO2 `.PRO` ammo modifiers (`ac_adjust`, `dr_adjust`, `dam_mult`, `dam_div`).
  2. **Dialogue, Quests & Overland Travel:** `.MSG` dialogue tables (`621` in FO1, `802` in FO2) + condition trees convert into Starfield `DIAL`/`INFO` list menus with deterministic `[Speech]`/`[Science]`/`[Doctor]` and low-`INT` (`INT <= 3`) checks. Overland grid maps (`worldmap.txt` / `worldmap.dat` / `encounters.txt`) run directly on our Pip-Boy `MAP` world selector with scripted `Survival` encounter interdictions.
  3. **Squads & Vehicles (*Tactics*):** *Tactics*' `70` recruitable soldiers (`entities/recruits/*.ent`) plug directly into our `SQ_Followers` + `SQ_Groups` `GLOB`-capped Warfare squad core (`2` base, `4` earned max by default); its `7` vehicle `.ent` archetypes align with Starfield's ground-vehicle (`SFBGS008.esm`) / vertibird travel hooks.
- **What the Shared Core CANNOT Automatically Convert:**
  1. **No 3D Geometry or Heightmaps in Source Archives:** FO1 (`72` `.MAP` files), FO2 (`155` `.MAP` files), and Tactics (`103` `.mis` files + `29,957` `.til` tiles) contain **zero 3D meshes and zero heightmaps** — only 2D oblique/isometric sprite art (`.FRM`, `.til`, `.spr`) on `200 x 200` hex/tile grids (up to `3` elevations per `.MAP`). A converter can read exact wall/floor/scenery/blocker coordinates and `.PRO` IDs from `.MAP`/`.mis` files and **extrude/stamp 3D kit prefabs** (vault corridors, desert terrain, adobe walls, ruined city blocks, Brotherhood bunkers) drawn from converted FO3/FNV/FO4/Starfield 3D kits, but cannot turn a 2D `.FRM` sprite into a 3D building without a tile-to-3D-prefab mapping table and art/layout review.
  2. **Turn-Based Hex AP Queue vs Real-Time 3D Engine:** Starfield's combat, physics, AI packages, and animation graphs run in continuous real time. True alternating hex-grid turn-based combat would require freezing AI/physics globally via custom C++ SFSE hooks and building a custom movement-hex cursor, whereas 1st/3rd-person real-time combat with VATS (`8` aimed-shot zones: Head, Eyes, R/L Arm, Torso, Groin, R/L Leg) uses the exact same core as FO3/FNV/FO4/76.
  3. **Compiled `.INT` SSL Bytecode (`952` FO1 + `1,443` FO2) & `.mis` FSMs (`103` Tactics):** Unlike FO3/FNV (`100%` plain-text `SCTX` source shipped in the ESMs), FO1/FO2 ship compiled `.INT` bytecode without `.SSL` text. Automating their quests requires an offline `.INT` bytecode decompiler/transpiler (~320 SSL opcodes) into Papyrus.
- **Owner Decisions Required Before FO1/FO2/Tactics Volume Conversion (Does Not Block Core Finish Line):**
  - **ISO-1 (Play Perspective & Combat):** **(A) Recommended:** Play FO1/FO2/Tactics as 1st/3rd-person 3D RPGs with VATS / Aimed-Shot (`8` zones) + real-time tactical squad commands (`100%` shared core); or **(B)** build a top-down camera + SFSE turn-freeze mode.
  - **ISO-2 (3D Level Construction):** **(A) Recommended:** Auto-layout `.MAP`/`.mis` footprints onto `.btd` terrain + 3D kit prefabs (FO3/FNV/FO4/SF vault/desert/ruin kits) with landmark polish; or **(B)** hand-build key story hubs only.
  - **ISO-3 (FO1/FO2 Talking Heads):** **(A) Recommended:** Standard 3D NPCs in `DialogueMenu`; or **(B)** animated Pip-Boy/dialogue portrait inset for the `21` talking-head characters.

---

## 1. Master Core Systems Table & Eight-Game Evidence

### 1.1 Master Systems Matrix (`origin/main` `713ed97a` Verified State)

| # | Core System | Class | Live State (`16 Nov`) | Repo / PR Evidence | What "Done" Means as an In-Game Test | Next Slice | Systems Touched |
|---:|:---|:---|:---|:---|:---|:---|:---|
| 1 | **New game & Vault 111 exit** | `SHARED` (framework) + `BASE-PLUS-DATA` (world start table) | **Installed, awaiting walk** (`main` start merged; `#803` exit installed) | Merged `#791`, `#794`; Open `#803` (`647635c8`) | Fresh New Game (both *Create character* and *Quick start*), zero console/`tcl`: walk from pod `(-2.5 m)` -> open gear door -> cross catwalk -> step onto open-gate floor lift -> ride `+21.6 m` -> land on merged Commonwealth cell `03......`, reach `stage 200`, `make_newgame.py log` exits `0`. | Owner/Claude (PC) walk of `#803` (`647635c8`); merge `#803`; add data-driven `StartWorld` table (`CF-1`). | Quest holds, Pip-Boy pickup, Progression chargen, Map discovery, Launcher |
| 2 | **Pip-Boy pages (`STAT`, `INV`, `DATA`, `MAP`, `RADIO`) & SPECIAL UI** | `SHARED` (SFSE + AS3 shell) + `BASE-PLUS-DATA` (tabs/skins) | **In review, not installed** | Open `#762` (`b2f33d34`), `#764` (`a115045e`), `#804` (`0469b8d4`), `#780` (`da38e386`) | Pressing Pip-Boy key opens real FO4 `PipboyMenu.swf` in 3D/fullscreen with zero crash on `STAT` (`ConditionClips` + `SPECIALList[0..6]` populated before `InvalidateData`), reads live HP/AP/Weight/Caps/SPECIAL/Perks/Inventory/Quests/Radio, and survives 20 open/tab/close cycles + save/reload. | Rebase `#762`+`#764` onto `main`, fold `#804` (`0469b8d4`), PC boot test (`CF-3`), then wire `PopulatePipboyInfoObj` live backends (`CF-6`). | Progression, Map, Inventory/Crafting, Quests, Rads/Survival, Dialogue |
| 3 | **Map, discovery, fast travel & cross-world travel (Star Map blocked)** | `SHARED` (Pip-Boy Map + travel chokepoint) + `BASE-PLUS-DATA` (world maps & `XMRK` stores) | **In review, not installed** | Merged `#781`, `#783`; Open `#801` (`80520c20`) | Pressing `M` (and every menu tab/key path to Starfield's surface/planet/star map) opens **only** Pip-Boy `MAP` (vanilla Star Map `0` opens); Commonwealth texture + `309` markers render with live engine discovery state; clicking a discovered marker fast-travels, advances `GameHour`/`GameDaysPassed`, teleports followers, and cross-world gateway travels to a second worldspace with zero Star Map. | Fold `#801` (`80520c20`) onto rebased `#764`+`#804`; add hard Star Map input/menu block + `WorldId` selector (`CF-4`). | Pip-Boy UI, New Game arrival discovery, Survival (fast-travel rule), Companions, Worlds |
| 4 | **Quest layer & Starfield hold groups (`radiant 9`, `ships 21`, `system 4`)** | `SHARED` (hold lists & boundaries) + `PER-TITLE` (story quests) | **`117` merged (`main`); `48` installed (`#802`); `34` open** | Merged `#794` (`5`), `#795` (`18`), `#798` (`14`), `#800` (`80`); Open `#802` (`b129e901`, `48`); Mission `FO4SFMission.esm` | On New Game stage `20`, `DefaultHold = 199` (`117` on `main` + `48` in `#802` = `165` + `34` in Group 5 `radiant 9` + `ships 21` + `system 4` = `199`, including `4` non-running `MQ*`), stopping all `195` running targets (`199 - 4`) out of Starfield's `207` cold-start quests so `0` Starfield quest popups/chatter appear and the `12` protected quests (`5` Warfare squad + `7` core engine) remain running cleanly. | PC walk + merge `#802` (`48`); stage & PC-test Group 5 (`radiant 9`, `ships 21`, `system 4` -> `199` total in `DefaultHold`, `CF-2`). | New Game, Companions/Warfare, Dialogue, A-Life, Ships/Vertibird |
| 5 | **Script runtime, FO4->SF Papyrus function map, ObScript, converter `VMAD`/`XLKR`/`XESP` & converted-quest bug audit** | `SHARED` (`FO4SF_Shim_*` + `FO4SF_NativeBridge` + `ReferenceLinks` + `SCTX` transpiler + per-quest known-bug manifest) | **In review / Partially built** (`#710`, `#805`, `ReferenceLinks`) | Open `#710` (`a07ad404`), `#805` (`28bff5c5`), `#477`; `dotnet/ReferenceLinks` | (a) All `826` non-identical FO4 scripts rewrite/compile cleanly against Starfield v4.2 (`99.87%` pure Papyrus + `5` SFSE natives in `FO4SF_NativeBridge.dll`); (b) converter preserves initial `XESP` enable states (`3,330` wrong-state refs fixed), `XLOC` locks, `XLKR` links, `XAPR` chains, and `XTEL` doors; (c) every converted quest carries its known-bug audit (fixed vs left + repro steps on its PC card, zero third-party mod files); (d) Fort Hagen + Concord scripted doors/elevators pass in game. | Build `FO4SF_Shim_*` (`8` scripts) + `XESP`/`XLOC`/`XAPR` converter pass (`CF-5`); add `fold`/installer to `#805` (`CF-5b`). | Every interactive world object, Quests, Dialogue, Workshop, Power Armor, FO3/NV `SCTX` |
| 6 | **Progression: S.P.E.C.I.A.L., Skills, Perks, Backgrounds & Traits** | `BASE-PLUS-DATA` | **Owner decisions confirmed (`#806`); `7` SPECIAL `AVIF` stub merged** | `FO4SF_NewGameSpecial.psc` (`main`); `#806` `#issuecomment-6930665309` | New Game creation selects Face/Body -> `1` Background -> `0–2` Traits (`1` free respec at Vault exit) -> **`40`-point** `S.P.E.C.I.A.L.` (`28`-pt `GLOB` off) + `3` Tag Skills (`13` `AVIF`s); derived stats update live; `[Background]`/`[Trait]`/`[Skill >= N]` gate dialogue/locks; leveling grants skill points + Perks on `GLOB` cadence (`1/2 lvls` default, zero fixed-cadence dependency). | Build `CF-6` design doc, data tables, unit tests & plugin after `CF-8`/`CF-9` (`2a–2d`); gate first game run on Grok `#806` review / Claude (PC) go-ahead. | New Game, Pip-Boy `STAT`, Dialogue, Locks/Terminals, Gunplay, Warfare, Settlements |
| 7 | **Dialogue & skill / SPECIAL / trait / background checks** | `BASE-PLUS-DATA` | **In review (`#792` `CLEAR`ed by Grok, not installed)** | Open `#792` (`bc8c7a86`); Starfield native `DialogueMenu.swf` + `SpeechChallenge` (`0128D0`) | (a) 4-option FO4 scenes (`#792` Concord stand-in) render N/E/S/W wheel options without crash and advance quest stages; (b) silent-player list conversations render `[Speech 50]` / `[Strength 7]` / `[Background]` / `[Trait]` options and evaluate deterministically (`NV` rule) or via speech check (`FO3`/`FO4` rule). | Claude (PC) runs `#792` Concord 4-option card, merges `#792`, and wires unified `[Skill/SPECIAL/Background/Trait]` `CNDF` helpers (`CF-7`). | Quests, Progression, Companions, Karma/Reputation, Audio/Voice |
| 8 | **NPCs, creatures & A-Life (`531` places, `1,317` routes, `450/620 m` switch)** | `SHARED` (L1–L3 sim & switch) + `BASE-PLUS-DATA` (world graphs & rosters) | **Slice 1 `CLEAR`ed by Grok (`#799`), not installed; exterior navmesh verified** | `FO4ActorRaider.esm`; Open `#799` (`5a24a138`); `combined-core-notes/prototype/` | Rung 1a/1b (`#799`): 4-member squad walks Red Rocket -> Concord loaded and unloaded across save/reload; Rung 2 (`CF-9`): off-screen graph ticks `10+` faction squads across `531` places, materializes actors inside `450 m`, dissolves beyond `620 m` with `0` orphan refs and `< 2 ms` tick cost. | Convert `#799` to ride-along/bundle install, run `#799` PC Card A & B, merge `#799`, then build `450/620 m` materializer + `REPU` territory hook (`CF-9`). | Navmesh, Factions/`REPU`, Companions/Warfare, Settlements, Performance |
| 9 | **Gunplay (VATS, `BPTD` hit locations, limb damage) & NV ammo types** | `SHARED` (combat/VATS/ammo swap) + `BASE-PLUS-DATA` (caliber & weapon tables) | **Not started (`0%`), engine `BPTD` verified on disk** | `Starfield.esm` (`27` `BPTD`s, `HumanBodyPartData` = `8` parts); `FalloutNV.esm` (`54` `AMEF`) | Head/torso/arm/leg hits apply distinct `BPTD` multipliers and limb-cripple penalties (cured by Stimpak / Doctor's Bag in Hardcore); slow-time VATS overlay targets limbs by AP cost; hotkey cycles ammo subtypes (`Standard`, `AP`, `JHP`, `+P`, `Slug`) modifying DT/DR penetration across all weapons. | Run `BPTD` locational-damage + hotkey `AMMO`/`OMOD` swap slice (`CF-8`). | Progression (Guns/Perks), Pip-Boy `STAT` ConditionBoy & `INV`, Hardcore, Animations |
| 10 | **Karma & faction reputation (`Karma` + `REPU` independent axes)** | `BASE-PLUS-DATA` | **Owner decision confirmed (`#806`); not started** | `FalloutNV.esm` (`13` `REPU`), `Fallout3.esm` (`10` Karma `GMST`s), `Starfield.esm` (`812` `FACT`) | **Both axes run independently:** (a) per-faction `Fame`/`Infamy` (`REPU`, 16-state NV matrix) drives `FACT` hostility/ally disposition and vendor prices; (b) global `Karma` (`[-1000..+1000]`, FO3 style) gates karma dialogue checks, moral-aligned companion loyalty, and endings — a low-`Karma` player can still be `Idolized` by a faction. | Build decoupled `FO4SF_Karma` + `FO4SF_Reputation` (`Fame`/`Infamy` store + `FACT` disposition sync) in `CF-6`. | Dialogue, A-Life territory, Companions/Squads, Warfare faction starts, Pip-Boy `STAT`/`DATA` |
| 11 | **Survival layer & hardcore settings (`DEHY`/`HUNG`/`SLPD`, toggleable)** | `SHARED` (framework) + `BASE-PLUS-DATA` (item/disease tables) | **Starfield `SQ_ENV` held off (`#794`); custom survival layer not started** | Merged `#794` (`SQ_ENV` held); `Starfield.esm` `GPOF` gameplay options | Toggling Hardcore/Survival ON in Gameplay Options (`GPOF`) activates `Hunger`, `Dehydration`, and `Sleep` meters (`0–1000`, 5 stages), ammo weight, stimpak heal-over-time, crippled-limb `Medicine`/Doctor's Bag requirement, and Pip-Boy `MAP` `CheckHardcoreModeFastTravel`; toggling OFF cleanly disables all penalties (`0` conflict with held `SQ_ENV`). | Build unified `FO4SF_Hardcore` rule-list quest + `GPOF` toggles (`CF-8` `2b`). | Radiation, Pip-Boy `STAT`/`MAP`, Settlements (food/water), Ammo weight |
| 12 | **Radiation (dual-mode `GPOF`: FO4 HP-cap OR FO3/NV thresholds) & optional mutations** | `SHARED` (rads/mutation engine) + `BASE-PLUS-DATA` (hazards & mutation list) | **Probe passed (`RadsProbe`); dual-rule option confirmed (`#806`)** | `dotnet/RadsProbe`, `docs/research/rads-probe.md` (`probe-rads5` PASS) | `HAZD` zones, irradiated water, and irradiated ingestibles raise `FO4SF_Rads`; **one gameplay option switch** selects between **(a) FO4 Max-HP cap** (`10 Rads = -1%`) and **(b) FO3/NV 5-stage rad-sickness stat penalties** (`200..1000`); both cure via RadAway and feed **one** Pip-Boy `STAT` display; FO76-style `Mutation_*` `PERK`s sit behind a separate option (`OFF` by default). | Build `FO4SFRads.esm` (`HAZD`/water/ingestibles + dual-rule switch + RadAway + optional Mutations, `CF-8` `2a`). | Survival/Hardcore, Pip-Boy `STAT`/`INV`, HUD, Progression Perks |
| 13 | **Settlements, C.A.M.P.s & crafting (`Workshop`, `COBJ`, `CMPO -> IRES`, `RCPE`)** | `SHARED` (builder/beacon/scrap engine) + `BASE-PLUS-DATA` (build sets & recipes) | **In testing (`85%` FO4 benches/workshops placed; `WorkshopProbe` hand card PASS)** | `FO4TerrainCore.esm` (`29` workshops, `269` benches); `dotnet/WorkshopProbe` (`c82b2858` PASS) | Fixed settlement workbenches (`0A2ECD`) AND portable C.A.M.P. beacons (`002C60E9`) open build mode, scrap Fallout `MISC` junk (`CMPO -> IRES` mapping), craft FO4 `COBJ` + FNV `RCPE` recipes at weapon/armor/chem/cooking/reloading benches, track settler food/water/power/defense ratings, and **persist across save and reload**. | Build `CF-9` (`2c`) from `dotnet/WorkshopProbe`: save/reload persistence, `CMPO -> IRES`, `COBJ`+`RCPE` benches, C.A.M.P. beacon. | Converter (`FURN`), Pip-Boy `DATA`, A-Life raids/caravans, Progression (`Repair`/`Science`) |
| 14 | **Power armor (climb-in `FURN` frame + FNV NCR salvaged worn `ARMO`)** | `SHARED` (entry/frame/HUD/core drain) + `BASE-PLUS-DATA` (armor sets & salvaged suits) | **Script stand-in built; `BPTD` crash root-caused; dual-form decision confirmed (`#806`)** | `dotnet/PowerArmorProbe`, `docs/research/power-armor-probe.md`; Open `#729` | **(a) Real Power Armor:** activating a placed `FURN` frame (`PowerArmorRace` carrying `6` limb-condition `AVIF`s on `BPTD`) climbs in, equips modular pieces, drains `FusionCore`, restores prior outfit on exit, and survives save/reload; **(b) Salvaged NCR Power Armor:** equips directly from inventory as plain worn `ARMO` with **no frame, no `FusionCore`, and no climb-in**. | Build `CF-9` (`2d`) from `dotnet/PowerArmorProbe`: `6`-limb `BPTD` climb-in frame + `FusionCore` + outfit restore + salvaged worn `ARMO` class. | Converter (`FURN`), Animations/97-bone rig, Gunplay (`BPTD`), Pip-Boy/PA HUD |
| 15 | **Companions, crew & Warfare squads (proposed earned-cap & upkeep rules)** | `SHARED` (follower/wheel/squad framework) + `BASE-PLUS-DATA` (NPC companions) | **Started (`Preston` merged `#793`; `5` Warfare quests protected `#798`; cap proposal recorded `#806`)** | Merged `#793` (`9ff2067c`), `#798` (`bd562a4e`); `SQ_Followers` (`00D773`), `SQ_Groups` (`1A9565`) | Proposed base active squad cap is **`2`** (`+2 -> 4` max via `GLOB` at Legend/Leadership standing for owner tuning, never blind `6`); recruitment checks faction `REPU` goodwill, player rank > NPC rank, and `Karma` alignment; squadmates consume real inventory ammo/meds, face bleedout/mortality, split contract/XP shares (`GLOB`-tunable), and sync cleanly across doors, lifts, and fast travel (`#801`). | Build `FO4SF_CompanionFramework` + proposed `GLOB`-tunable recruitment/upkeep rules over `SQ_Followers` + `SQ_Groups` (`CF-9`). | Quest holds, Dialogue, Pip-Boy fast travel (`#801`), A-Life/Warfare, `REPU`/`Karma` |
| 16 | **Launcher, multi-game detection & packaging** | `SHARED` (CLI/GUI, `BA2`/`BSA`/`.DAT`/`.bos` readers, snapshot/restore) | **In testing (`40%`, `176` Windows launcher tests pass; `#716` open with 3 conflicts)** | `src/fo4sf/launcher/*`, Merged `#723` (`4655e446`); Open `#716` (`deb09fb1`), `#706` | Launcher detects owned Steam/GOG installs across all `8` titles by hash, builds selected core/world modules offline on a player PC within `< 110 GB` scratch disk, packs `BA2` archives (`<= 4 GiB` each, `< 256` total), binds saves to release manifests, and cleanly snapshots/restores `Starfield\Data` + `Plugins.txt`. | Register all core plugins in `restore.py`/`crashwatch.py`, unify single `FO4SFCore` bundle installer (`CF-10`), add Python `bsa.py` (`v0x68`) + `.dat`/`.bos` readers before Phase C volume work. | Every plugin/BA2, Save version check, Asset pipeline |
| 17 | **Stabilize, recovery & beta test harness** | `SHARED` | **Started (`10%`: `guard.py`, `crashwatch.py`, `exp_install.py`, CI suite)** | `scripts/guard.py`, `src/fo4sf/launcher/crashwatch.py`, Open `#702`, `#712`, `#725` | Offline `plugin_verify` (`#712`/`#725`) refuses exterior persistent-group crashes and broken form refs before install; full core bundle runs a 60-minute continuous New Game -> Vault 111 exit -> Sanctuary -> Red Rocket -> Concord -> fast-travel -> save/reload soak with `0` crashes, `0` Papyrus stack dumps, and `< 70%` budget CPU/VRAM. | Merge offline `plugin_verify` guards (`#712`/`#725`) + run unified Core Finish Line soak (`CF-10`). | All systems |

---

### 1.2 Measured Per-Game Implementation Breakdown Across All Eight Installed Titles

Every line below is measured from the read-only local installs (`Fallout`, `Fallout 2`, `Fallout Tactics`, `Fallout 3 GOTY`, `Fallout: New Vegas`, `Fallout 4` `1.11.240`, `Fallout 76`, `Starfield` `1.16.244`):

1. **New game & opening exit**
   - **FO1:** Pre-game character sheet -> spawns outside Vault 13 cave (`V13ENT.MAP` / `V13CAV.MAP`, state in `DATA\VAULT13.GAM`).
   - **FO2:** Pre-game character sheet -> `artemple.map` (Temple of Trials) -> `arvillag.map` (Arroyo).
   - **Tactics:** Pre-game character sheet -> `mission01.mis` (Brahmin Wood) -> `bunker01.mis` (Bunker Alpha hub).
   - **FO3:** `CG00`..`CG04` staged Vault 101 childhood (`Fallout3.esm`, `5` quests) ending at `CG04` exit tunnel rebuild prompt.
   - **FNV:** `VCG01` -> `VCG02` in `GSDocMitchellHouse` (face, Vit-o-Matic SPECIAL, couch skills/traits) -> Goodsprings border `VGSummary` rebuild prompt.
   - **FO4:** `MQ101` -> `MQ102` (Sanctuary mirror -> `Vault111Cryo` pod -> Pip-Boy -> gear door `00126D` -> `VltElevator` `000244EB` -> Commonwealth surface).
   - **FO76:** `Vault76` bedroom ID mirror -> kiosk SPECIAL/C.A.M.P. -> Reclamation Day door into Appalachia (`SeventySix.esm`).
   - **Starfield (Engine):** `DFOB StartupQuest_DO` (`00562D`) overridden by `FO4SFNewGame.esm` (`000800`), parametrized by a per-title `StartWorld` table.

2. **Pip-Boy & Game UI**
   - **FO1:** `305` `ART\INTRFACE\*.FRM` 2D bitmaps (`PIP.FRM` status/automap/archives/alarm; separate `INVBOX.FRM` & `CHARWIN.FRM`).
   - **FO2:** `459` `art\intrface\*.frm` bitmaps across `master.dat` + `patch000.dat`.
   - **Tactics:** `1,083` files in `gui_0.bos` (`839` `.zar` bitmaps + `214` `.txt` layouts, `431` under `gui/pip/`, persistent real-time squad bar).
   - **FO3:** `0` `.swf`; `99` XML UI DOM files in `Fallout - Misc.bsa` (`stats_menu.xml`, `inventory_menu.xml`, `map_menu.xml` projected onto wrist NIF).
   - **FNV:** `0` `.swf`; `121` `menus\*.xml` files (adds `trait_menu.xml`, `companion_wheel_menu.xml`, `recipe_menu.xml`, `caravan_menu.xml`).
   - **FO4:** `351` unique `.swf` movies (`8` core `Pipboy*.swf` v15 + `225` `Components\*\*.swf` v17; `Pipboy_DataObj` `60` slots, `22` getter-only arrays/points).
   - **FO76:** `411` unique `.swf` movies (`pipboymenu.swf`, `quickboymenu.swf` HUD mode, `perkcardmenu.swf`, `campmenu.swf`).
   - **Starfield (Engine):** `251` `.swf` movies (`DataMenu.swf`, `DataSlateMenu.swf` `ScaleformToTextureRenderPass`); `UI.psc` absent -> SFSE `FO4SFPipboyMenu.dll` (`BGSCodeObj` C++ bridge) hosts the shared Pip-Boy UI.

3. **Map, discovery & travel**
   - **FO1:** Tile overland map (`WRLDMP*.FRM`, `CITY.TXT`) with green-line travel + `Outdoorsman` encounter rolls.
   - **FO2:** Overland map (`worldmap.txt` + `worldmap.dat` `9,516` B + `city.txt`) with car (`Highwayman`) fuel/speed rules.
   - **Tactics:** Region overland map (`locale/game/encounters.txt`) between bunker hubs and `103` `.mis` tactical maps.
   - **FO3:** `32` `WRLD`, `222` `REFR`s with `XMRK` map-marker subrecords (`0` `LCTN`), DLC boat/train/teleporter chokepoints.
   - **FNV:** `14` `WRLD`, `189` `XMRK` markers (`0` `LCTN`), canyon/gate DLC travel chokepoints.
   - **FO4:** `5` `WRLD`, `315` `XMRK` markers + `393` `LCTN` locations (`Survival` disables fast travel except Institute/Vertibird).
   - **FO76:** `56` `WRLD`, `482` `XMRK` markers + `1,899` `LCTN` (Caps-cost fast travel + free Vault 76 / C.A.M.P. hubs).
   - **Starfield (Engine):** `433` `WRLD`, `517` `XMRK`, `6,017` `LCTN`; runtime planet overlay assigns `0xFF` world IDs that break vanilla surface-map marker listing until reload — solved cleanly by blocking Starfield's Star Map completely and reading our own `XMRK` store in `FO4SFPipboyMenu` (`#801`).

4. **Quests & scripting runtime**
   - **FO1:** Quest state in `VAULT13.GAM` globals + `952` compiled SSL `.INT` scripts in `MASTER.DAT` (`0` `.ssl` sources shipped).
   - **FO2:** `data\quests.txt` + `1,443` `.int` scripts in `master.dat` (`+445` overrides in `patch000.dat`, `0` `.ssl` sources).
   - **Tactics:** `103` binary `.mis` mission files with embedded trigger/condition/action FSM tables (`0` text scripts).
   - **FO3:** `192` `QUST` + `1,257` `SCPT` ObScript records — **`1,257 / 1,257` (`100%`) carry unstripped plain-text `SCTX` source** inside `Fallout3.esm` (+ embedded scripts on `INFO`/`PACK`/`TERM`/`PERK`).
   - **FNV:** `436` `QUST` + `2,576` `SCPT` ObScript records — **`2,576 / 2,576` (`100%`) carry unstripped plain-text `SCTX` source** inside `FalloutNV.esm`.
   - **FO4:** `1,336` `QUST` + `7,875` base `.pex` (`10,342` total across DLC/CC BA2s; `10,282` `.psc` in CK zips); `89.36%` (`6,937 / 7,763`) runtime-clean on Starfield before shims; `97.32%` of `74,723` calls `IDENTICAL`, `2.54%` Papyrus-shimmable, `0.13%` (`98` calls / `5` functions) SFSE native.
   - **FO76:** `2,232` `QUST` in `SeventySix.esm` + `7,234` client `.pex` in `SeventySix - MiscClient.ba2` (server-side quest `.pex` omitted from client install; quests require reconstruction from `QUST`/`DIAL`/`INFO`/`VMAD` records if authorized).
   - **Starfield (Engine):** `2,077` `QUST` (`207` running at cold start -> `195` holdable + `12` protected), `5,034` v4.2 `.pex` (`5,033` `.psc` in `ContentResources.zip`), new `Guard` lock opcodes (`0x30..0x32`).

5. **Progression (S.P.E.C.I.A.L., Skills, Perks, Traits, Backgrounds)**
   - **FO1:** `7` SPECIAL, `18` Skills (`0–200%`), `3` Tags, `0–2` Traits (`TRAIT.MSG`), Perk/3 lvls (`312` `CRITTERS/*.PRO`).
   - **FO2:** `7` SPECIAL, `18` Skills (`0–300%`), `3` Tags, `0–2` Traits, Perk/3 lvls (`483` `critters/*.pro`).
   - **Tactics:** `7` SPECIAL, `18` Skills (`0–300%`), `6` playable Races (`Human`, `Super Mutant`, `Ghoul`, `Deathclaw`, `Dog`, `Robot`), `0–2` Traits.
   - **FO3:** `60` `AVIF` (`77` hardcoded enum slots: `7` SPECIAL, `13` Skills `1–100`), `87` `PERK` (`61` playable, `1/lvl`), `0` Traits.
   - **FNV:** `64` `AVIF` (`7` SPECIAL, `13` Skills w/ `Survival`), `176` `PERK` (`101` playable at `1/2 lvls` + **`10` `isTrait=1` Traits**).
   - **FO4:** `359` `AVIF` forms (`7` SPECIAL, `0` Skills), `538` `PERK` (`323` playable on 70-cell grid, `1/lvl`), `0` Traits.
   - **FO76:** `3,284` `AVIF`, `1,992` `PERK` + `401` `PCRD` Perk Cards + `8` `PPAK` + `13` `LOUT` loadouts (`0` Skills).
   - **Starfield (Engine):** `1,107` `AVIF` + `502` `PERK` (`21` `Background*`, `17` `TRAIT_*`, `84` 4-rank `Skill_*`).

6. **Dialogue & skill checks**
   - **FO1:** `621` `.MSG` files + `21` talking heads (`330` `.FRM`, `1,601` `.LIP`), scrollable list, SSL skill/SPECIAL/low-INT branches.
   - **FO2:** `802` `.MSG` files + talking heads (`186` `.FRM`, `1,029` `.LIP`), scrollable list, SSL skill/SPECIAL/Karma branches.
   - **Tactics:** `29` mission briefing/speech `.txt` files (`0` branching dialogue menu; floating real-time barks).
   - **FO3:** `6,381` `DIAL`, `22,327` `INFO`, `0` `SCEN`; 1st-person zoom list, `%` roll Speech + deterministic Skill/SPECIAL/Perk `CTDA`s.
   - **FNV:** `18,215` `DIAL`, `23,247` `INFO`, `0` `SCEN`; 1st-person zoom list, deterministic `[Speech 50]` / `[Barter 35]` threshold `CTDA`s.
   - **FO4:** `35,443` `DIAL`, `78,087` `INFO`, `3,568` `SCEN`, `1` `DLVW`; voiced player, 4-button wheel, `CHA` `%` rolls (`122,857` `.fuz`).
   - **FO76:** `40,182` `DIAL`, `65,818` `INFO`, `4,769` `SCEN`, `0` `DLVW`; silent player, numbered list + deterministic `[SPECIAL N+]` checks.
   - **Starfield (Engine):** `68,154` `DIAL`, `126,347` `INFO`, `7,613` `SCEN`, `160` `SPCH`; silent player, numbered list `DialogueMenu.swf` with native `[Background]`/`[Trait]`/`[Skill]` tags + `#792` 4-option wheel mode.

7. **Gunplay, VATS, hit locations & ammo types**
   - **FO1 / FO2 / Tactics:** `8`-zone aimed-shot overlay (`CALLED.FRM` / `accuracy.zar`) + `.PRO`/`.ent` per-ammo `ac_adjust`/`dr_adjust`/`dam_mult`/`dam_div` (`25` ammo `.pro`s in FO2).
   - **FO3:** `32` `BPTD`, `229` `CAMS`, `307` `CPTH` (time-stop VATS); `30` `AMMO`, `160` `WEAP`, pure `DR%`, `0` `AMEF`/`IMOD`.
   - **FNV:** `49` `BPTD`, `276` `CAMS`, `418` `CPTH`; `92` `AMMO`, `261` `WEAP`, **`54` `AMEF` ammo effects**, **`50` `IMOD`**, hotkey ammo swap vs `DT`+`DR`.
   - **FO4:** `40` `BPTD`, `772` `CAMS`, `447` `CPTH` (slow-time VATS + manual crit bar); `57` `AMMO`, `252` `WEAP`, `2,409` `OMOD`, `8` `DMGT`.
   - **FO76:** `117` `BPTD`, `773` `CAMS` (real-time VATS); `176` `AMMO`, `1,549` `WEAP`, `12,736` `OMOD`, `10` `DMGT`.
   - **Starfield (Engine):** **`27` native `BPTD` records** (`HumanBodyPartData` `00003481` has `8` `BPND` parts), `272` `CAMS`, `148` `CPTH`, `150` `AMMO`, `406` `WEAP`, `2,682` `OMOD`, `11` `DMGT`.

8. **Karma, faction reputation, survival & radiation**
   - **FO1 & FO2:** Global `Karma` + town reputations (`VAULT13.GAM` / `karmavar.txt` / `genrep.txt`); critter radiation/poison timers.
   - **Tactics:** Brotherhood rank/reputation + radiation/poison item timers.
   - **FO3:** `326` `FACT` (`666` `XNAM`), `10` Karma `GMST`s (`AV 23`), `0` `REPU`; `5` `RADS` stages (`0–1000`), `0` hunger/thirst tables.
   - **FNV:** `682` `FACT` (`1,314` `XNAM`), **`13` `REPU` dual-axis Fame/Infamy records**, disguise scripts; `5` `RADS` + **`5` `DEHY` + `5` `HUNG` + `5` `SLPD`**.
   - **FO4:** `699` `FACT` (`0` `REPU`, `0` Karma); `Rads` caps Max HP% (`10 Rads = -1%`); `HC_Manager` Survival quest + `HC_*` diseases/needs.
   - **FO76:** `954` `FACT` (quest/currency faction rep); real-time food/water meters + diseases + **`Mutation_*` `SPEL`/`PERK`s + Serums**.
   - **Starfield (Engine):** `812` `FACT` (`1,007` `XNAM`), `1,360` `AFFE` companion events; `SQ_ENV` (`248D20`, held off) + `80+` `ENV_*` affliction forms; `FO4SF_Rads` `AVIF` proven in `RadsProbe`.

9. **Settlements, C.A.M.P.s, crafting, power armor & companions**
   - **FO1 & FO2:** `0` settlements/crafting; Power Armor is `Armor` `.PRO` (`16` in FO2); FO2 `party.txt` (`CHA/2` cap) + combat control UI.
   - **Tactics:** `0` settlements; `18` PA `.ent` + `7` multi-crew vehicles; `6`-soldier squad bar (`70` recruit `.ent`s).
   - **FO3:** `0` settlements (`0` active `COBJ`, scripted schematic notes); `21` `ARMO` PA suits (`PowerArmorTraining` `PERK`); `1+1` followers.
   - **FNV:** `0` settlements; **`105` `RCPE` recipes / `10` `RCCT` categories** (`recipe_menu.xml`); `56` `ARMO` PA suits; `8`-slice `companion_wheel_menu.xml` + `Companion Nerve`.
   - **FO4:** `29` Commonwealth workshops + `2,161` `COBJ` + `31` `CMPO`; `25` climb-in PA `FURN`s (`PowerArmorRace` `0001D31E` + `FusionCore`); `1` companion (`CA_*` affinity).
   - **FO76:** Portable **C.A.M.P.** + Blueprints + `14,797` `COBJ` + `44` `CMPO`; `25` PA `FURN`s + `315` PA `ARMO`s + inventory chassis recall; `1` Lite Ally.
   - **Starfield (Engine):** `WorkshopKeyword` (`00054BA7`) + `OutpostBeaconActivator` (`002C60E9`) + `3,009` `COBJ` + `332` `IRES` (`WorkshopProbe` PASS); live `SwitchToPowerArmor` (`+0x1fcb100`, needs `6` `BPTD` limb `AVIF`s); live `SQ_Followers` (`00D773` uncapped `ActiveFollowers`) + `SQ_Groups` (`1A9565`).

---

## 2. The Collision Map, Build Routes & Merge Order

### 2.1 File-Level Collisions Across Open Branches (`git merge-tree` Verified)

#### A. Pip-Boy Plugin & UI Stack (`#762`, `#764`, `#780`, `#804`, `#801`)
- **Topology:** `b36369b5` (`main` `-199` commits) -> `#762` (`b2f33d34`) -> `#764` (`a115045e`) -> forks into `#804` (`0469b8d4`) and `#801` (`80520c20`). Meanwhile `#780` (`da38e386`) branched off newer `main` (`e65b50d0`, `-50` commits).
- **Exact Conflicts:**
  - **`#762`/`#764` vs `origin/main` (`6` conflicting files):** `scripts/ui/make_pipboy_kit.py`, `scripts/ui/pipboy_probe_install.py`, `sfse/FO4SFPipboyMenu/FO4SFPipboyMenu.ini`, `sfse/FO4SFPipboyMenu/README.md`, `sfse/FO4SFPipboyMenu/src/main.cpp`, `tests/test_pipboy_probe_install.py` (caused by `#752`, `#758`, `#759`, `#761`, `#723` merging to `main` after `b36369b5`).
  - **`#780` vs `#764` (`7` conflicting files):** the `6` files above plus **`sfse/native_components.json`** (`lines 70–92`, where `#764` adds `arm_holder`/`arm_id`/`arm_idle` refuse steps and `#780` adds probe-1 refuse steps on the same array lines; enforced 1:1 against `src/main.cpp` by `tests/test_native_components.py`).
  - **`#804` vs `#801` (`git merge-tree` = `100% CLEAN`):** Disjoint hunks in `src/main.cpp` (`#804` at `+148, +914..921, +3763..3788, +3972..3975`; `#801` at `+130, +3389, +3673, +3973, +4335..5505` — verify braces around line `3973` on compile).
- **The Two Native C++ Build Routes (Mandatory Parity Rule):**
  1. **Route 1 (`sfse/FO4SFPipboyMenu/xmake.lua:29-30`):** Uses wildcard globs `add_files("src/**.cpp")` and `add_headerfiles("src/**.h")`.
  2. **Route 2 (`sfse/FO4SFPipboyMenu/build.ps1:60`):** Out-of-tree staging script copies **only** the hardcoded `$sources` array into `$Out\proj\`. Any new `.cpp`/`.h` file (such as `#801`'s `src\pipboy_map.cpp` and `src\pipboy_map.h`) **must** be added to `$sources` in `build.ps1:60` and `tests/test_sfse_sidecar_scripts.py`, or Route 2 fails while Route 1 passes.
- **The Two Pip-Boy UI / SWF Routes:**
  1. **Synthetic Kit Route (`make_pipboy_kit.py`, `Stage=5`):** Clean-room no-AS3 SWF 12 probe (`Interface/FO4SF_PipboyMenu.swf`), used for early render/channel tests (`#762`, `#780`).
  2. **Real FO4 AS3 Route (`#764` `pipboy_probe_install.py` + `#801` `pipboy_map_store.py`, `Stage=2, CodeObj=1`):** Extracts the player's local FO4 `PipboyMenu.swf`, `5` page SWFs, and `225` `Components\*\*.swf` clips into `FO4SFPipboyProbe - Main.ba2` + `FO4SFPipboyTravel.esm`. **Decision:** Standardize production Pip-Boy work on **Route 2 (`#764` + `#804` + `#801`)** once `#762`+`#764` rebase onto `main`.

#### B. `FO4SFNewGame.esm` & Quest Writer Hold Lists (`#803` vs `#802`)
- **Shared Files (`4`):** `dotnet/NewGame/Program.cs`, `scripts/newgame/FO4SF_NewGameQuest.psc`, `scripts/newgame/make_newgame.py`, `tests/test_newgame.py`.
- **3-Way `git merge-tree` (`origin/main`, `#803` `647635c8`, `#802` `b129e901`):** **`100% CLEAN` (zero conflicts).** `#802` edits hold arrays (`Program.cs:258-278`, `make_newgame.py:122-141`, `.psc:84` comment `1,409 B <= 3,072 B` cap); `#803` edits pod/door/lift/arrival/fold logic (`Program.cs:7-204, 288-1043`, `.psc:134-873`, `make_newgame.py:158-999`).
- **Superseded Vault 111 PRs (Close/Retire After `#803` Merges):** `#796` (`4aaaa2c0`), `#790` (`34e62421`), `#741` (`9387c5d6`), `#726` (`4e323ead`).

#### C. Other Open Slices & Installer / `BA2` / Registry Collisions
- **`FO4SFExp.install.json` Single-Experiment Contention (`#803` + `#802` vs `#799` vs `#805`):** `scripts/game/exp_install.py` manages **one** active experiment folder (`Data\FO4SFExp.install.json`). Both `make_newgame.py fold` (`#803`/`#802`) and `make_alife.py fold` (`#799`) fold into a core set, while `make_fort_hagen.py` (`#805`) currently has `stage|verify|log` with **no** `fold` or ride-along installer. **Fix (`CF-5b` / `CF-10`):** Chain `fold` steps into one unified core staging directory (or give slice probes their own `Data\FO4SF<Name>.install.json` ride-along record like `#792` and `#797`).
- **`#792` Concord Dialogue (`bc8c7a86`):** Git-clean vs `main`; ride-along `FO4SFConcordTalk.install.json`; note its `BA2` overrides `Interface/DialogueMenu.swf` whenever `*FO4SFConcordTalk.esm` is active.
- **`#716` Launcher Save-Bindings (`deb09fb1`):** Conflicts with `main` in `scripts/launcher.py`, `docs/JOURNAL.md`, and `docs/ai/decisions.md`, and touches `tests/test_native_components.py`. Defer rebasing `#716` until Pip-Boy (`#764`/`#804`/`#801`) and Core plugins stabilize (`CF-10`).
- **Launcher Registry Gap:** `src/fo4sf/launcher/restore.py`, `test_kits.py`, and `crashwatch.py:549` (`SCRIPT_PLUGINS`) must register `FO4SFVaultGearDoor.esm`, `FO4SFExitLift.esm`, `FO4SFPipboyTravel.esm`, `FO4SFConcordTalk.esm`, `FO4SFALife.esm`, and `FO4SFFortHagen.esm`.

---

### 2.2 Sequenced Merge Order & Single Owner Per Area

| Merge Order | Area / Domain | PRs & Exact Heads | Area Owner | Gate to Merge |
|---:|:---|:---|:---|:---|
| **M1** | **Vault 111 Exit + Hold Group 4 (`FO4SFNewGame.esm`)** | `#803` (`647635c8`) then `#802` (`b129e901`) -> `main` | **Gemini (PC)** (code fixes) / **Claude (PC)** (walk test & merge) | Owner/Claude (PC) walk PASS on installed `#803`+`#802` build + Grok `CLEAR` on `#803` (`#802` already `CLEAR`ed). Retire `#796`, `#790`, `#741`. |
| **M2** | **Hold Group 5 (`radiant 9`, `ships 21`, `system 4`)** | New small PR `CF-2` on `dotnet/NewGame` (`165 -> 199` held) | **Gemini (PC)** (stage/tests) / **Claude (PC)** (walk & merge) | Grok `CLEAR` + 1 New Game cold-start log check confirming `195/207` stopped and `12` protected quests healthy. |
| **M3** | **Pip-Boy Host Rebase + Crash Fix + Map Slices 1–4** | Rebase `#762`+`#764` onto `main` (folding `#780` or retiring `#780`), then merge `#804` (`0469b8d4`) + `#801` (`80520c20`) | **Sole Survivor / Claude** (host `main.cpp` rebase) / **Gemini (PC)** (`#804` forwarders & `#801` `pipboy_map.*`) | Grok `CLEAR` on `#804` & `#801`; `test_sfse_sidecar_scripts.py` + `test_native_components.py` green; Claude (PC) runs STAT no-crash boot + Map `M`-key/travel card. |
| **M4** | **4-Option & List Dialogue** | `#792` (`bc8c7a86`, already Grok `CLEAR`ed) -> `main` | **Scribe** (author) / **Claude (PC)** (Concord talk test & merge) | Claude (PC) Concord 4-option in-game check PASS. |
| **M5** | **World Mechanics, Elevators & A-Life Slice 1** | `#799` (`5a24a138`, Grok `CLEAR`ed) + `#805` (`28bff5c5` + installer/fold) + `#710` (`a07ad404`) + `#712`/`#725` | **Gemini (PC)** (`#799`, `#805`, shim/converter slices) / **Claude (PC)** (PC cards & merge) | Grok `CLEAR` on `#805`; Claude (PC) runs `#799` Cards A/B and `#805` Fort Hagen card. |
| **M6** | **Core Systems Finish Slices (`CF-5`..`CF-10`)** | One small PR per slice (`CF-5`..`CF-10` in order below) | **Gemini (PC)** (build/test/card) / **Grok** (review) / **Claude (PC)** (run/merge) | Strict serial execution under Section 5 Stop Rule. |

---

## 3. The Core's Finish Line (Ranked Pre-Volume Checklist & PC Cards)

Nothing in Phase C (bulk interiors, DLCs, or *Fallout 3 / New Vegas / 1 / 2 / Tactics / 76* world conversion) starts until **CF-1 through CF-10** are installed and passing together, ensuring zero FO4-only hard-coding leaks into volume data.

### CF-1 (Rank 1) — Clean Vault 111 Exit + Multi-World `StartWorld` Hook (`#803` + Hook)
- **Why before volume:** Proves end-to-end New Game without console/`tcl` and replaces any hardcoded `Vault111Cryo` assumption with a `StartWorld` descriptor table (`vault111`, `vault101`, `goodsprings`, `vault76`, `vault13`, `arroyo`, `bunkeralpha`, plus faction starts).
- **PC Card for Claude (PC):**
  - *Stage/Install:* Already staged/installed for `#803` (`647635c8`) via `docs/newgame/vault111-exit-pc-card.md` Steps 1–4 (`make_cog_door.py stage --production-cog`, `make_anim_console.py stage --production-lift`, `make_newgame.py stage`, `make_newgame.py fold` + `verify`).
  - *Run:* Two fresh New Games (*Create character* and *Quick start*), zero console commands: walk from pod -> `E` on gear door -> walk onto open floor lift -> *Ride up* -> settle 3 s on Commonwealth surface.
  - *PASS:* `python scripts/newgame/make_newgame.py log` exits `0` on both sessions (`stages=[10,20,30,40,200]`, `pod_settle ok=true`, `ascent carried confirmed`, `core_cell=True`, `arrival_discovery_requested` non-null).

### CF-2 (Rank 2) — Complete Starfield Quest Hold-Off (`#802` Group 4 + Group 5 `radiant 9`, `ships 21`, `system 4`)
- **Why before volume:** Eliminates all `195` holdable Starfield background quests (`DefaultHold` = `199` incl. `4` non-running `MQ*`), proving the exact `12`-quest engine/Warfare floor (`SQ_Followers`, `SQ_Groups`, `SQ_COM_CREW_AngerCombatOverride`, `SQ_Captive`, `SQ_Airlock` + `SQ_PlayerShip`, `SQ_Parent`, `PlayerSkills`, `DialogueGeneric`, `DialogueGenericPlayer`, `SpeechChallenge`, `Achievements_Quest`).
- **PC Card for Claude (PC):**
  - *Stage:* `python scripts/newgame/make_newgame.py stage --out <STAGE>/ng-g5 ...` then `fold` + `verify` (`offline_check.txt` prints `hold 199`).
  - *Run:* Start fresh New Game through stage `20`, walk exterior 3 minutes, test follower command and weapon/damage HUD.
  - *PASS:* `fo4sf_newgame.0.log` records `hold-off pass 1` + `pass 2` stopping all `195` running targets, `0` Starfield quest objectives/chatter fire, and `SQ_Followers` + `PlayerSkills` report `IsRunning() == true`.

### CF-3 (Rank 3) — Crash-Free Pip-Boy Shell (`#762` + `#764` Rebased + `#804`)
- **Why before volume:** Unblocks every UI-backed system (`STAT`, `INV`, `DATA`, `MAP`, `RADIO`, Perks, Reputation, Hardcore).
- **PC Card for Claude (PC):**
  - *Build/Stage:* `powershell -File sfse/FO4SFPipboyMenu/build.ps1 -Out <STAGE>/pb-dll` and `python scripts/ui/pipboy_probe_install.py stage --out <STAGE>/pb-stage --fo4-data <FO4_DATA> --dll <STAGE>/pb-dll/FO4SFPipboyMenu.dll`.
  - *Run:* Open Pip-Boy (`Tab`), cycle `STAT` (Status / SPECIAL / Perks), `INV`, `DATA`, `MAP`, `RADIO` 10 times, save and reload.
  - *PASS:* `FO4SFPipboyMenu.log` shows `refuse=none`, `ConditionClips` staged (`18/18`), `SpecialReady=1` before every `InvalidateData`, `0` Scaleform `TypeError #1010`/`#1006`, `0` crashes.

### CF-4 (Rank 4) — Pip-Boy Map, Engine Discovery, Complete Star Map Block & Multi-World Selector (`#801` + World Selector)
- **Why before volume:** Enforces the owner's rule that Starfield's Star Map never opens and establishes the multi-world `WorldId` coordinate/marker schema (`Commonwealth`, `CapitalWasteland`, `Mojave`, `Appalachia`, overland maps) before extra worlds are built.
- **PC Card for Claude (PC):**
  - *Stage:* `python scripts/ui/pipboy_map_store.py build --fo4 <FO4_DATA>/Fallout4.esm --core <CORE_DIR>/FO4TerrainCore.esm --out <STAGE>/map-store` + stage `FO4SFPipboyTravel.esm`.
  - *Run:* Press `M` and pause-menu Map entry indoors and outdoors (confirm Pip-Boy `MAP` opens and vanilla Star Map never opens); discover a marker; click discovered marker to fast-travel; trigger world-selector gateway to a test secondary worldspace cell and back.
  - *PASS:* `FO4SFPipboyMenu.log` logs `starmap_blocked>=1`, `map_store markers=309`, live discovery state matches engine marker, `fo4sf_pipboy_travel.0.log` logs `travel ok=true clock_advanced=true followers_synced=true`, and cross-world trip completes with `0` Star Map frames.

### CF-5 (Rank 5) — Converter Interactive Fidelity (`XESP`, `XLOC`, `XLKR`, `XAPR`, `TERM`), Papyrus Bridge (`FO4SF_Shim_*` & `FO4SF_NativeBridge`) & Per-Quest Known-Bug Audit
- **Why before volume:** Running volume interiors or FO3/NV worlds with the current strip behavior would bake in `3,330` wrong-enable-state objects, `520` unlocked safes/doors, `206` empty terminals, stripped scripts/links, and shipped original-game quest script bugs (broken stage transitions, stuck NPCs, unreachable objectives). Fixing the converter + compiling the `8` `FO4SF_Shim_*` libraries + `FO4SF_NativeBridge` + `#805` Fort Hagen controller + instituting the per-quest known-bug audit (names/descriptions from shipped known-issue lists and community unofficial-patch changelogs, clean-room case-by-case fixes, zero third-party mod files, owner approval per download) makes places and quests work systematically.
- **PC Card for Claude (PC):**
  - *Build/Stage:* Run `python scripts/papyrus/compile_census.py --with-shims` (verifying `826` shimmed FO4 scripts compile to v4.2 `.pex`), stage updated `ReferenceLinks` pass + `FO4SFFortHagen.esm` (`#805`), and include the per-quest known-bug table (fixed vs left + exact reproduction steps) on every converted quest slice card.
  - *Run:* Visit Vault 111, Red Rocket, Concord, Super Duper Mart, and Fort Hagen (`0BB078` / `0CD2AE`): test `XESP` pre-disabled clutter, pick a Novice `XLOC` lock, use a linked terminal door/turret switch, ride Fort Hagen's interior/roof elevators (`docs/mission/fort-hagen-elevators.md`), and run any converted quest's fixed-bug reproduction checks.
  - *PASS:* `0` frame-1 opposite-state `XESP` bugs in audited cells; lockpick UI opens and unlocks `XLOC` ref; terminal menu item opens linked `DOOR`; `make_fort_hagen.py log` exits `0`; documented quest-bug repros match the card's fixed/left ledger.

### CF-6 (Rank 6) — Progression Core (`Backgrounds`, `Traits`, `40`-Point `S.P.E.C.I.A.L.`, `13` Skills, `GLOB`-Cadence `Perks`, Independent `Karma` + `REPU`)
- **Why before volume:** Every converted quest, dialogue check (`[Speech 50]`, `[Science 75]`, `[Background]`, `[Trait]`, `[Karma]`), lock/terminal tier, crafting bench, and Warfare squad cap across all 7 Fallout titles binds to these `AVIF`, `PERK`, `Karma`, and `REPU` FormIDs. *(Owner decisions confirmed in `#806` `#issuecomment-6930665309`; built after `CF-8`/`CF-9` `2a–2d`, with first in-game test gated on Grok `#806` review or Claude (PC) go-ahead.)*
- **PC Card for Claude (PC):**
  - *Stage:* Stage `FO4SFProgression.esm` (`7` SPECIAL `AVIF`s w/ `40`-pt pool + off-by-default `28`-pt `GLOB`, `13` Skill `AVIF`s, Background/Trait/Perk `FLST`s, `FO4SF_PerkCadenceLevels` `GLOB` = `2`, independent `FO4SF_Karma` + `REPU` faction globals, `FO4SF_ProgressionQuest.pex`).
  - *Run:* New Game -> select Background + `0–2` Traits + `40`-point SPECIAL + `3` Tag Skills -> verify `1` free Trait respec at Vault exit -> verify `CarryWeight`/`MaxHP`/Skills in Pip-Boy `STAT` -> level up & test `GLOB` cadence (`2` vs `1`) -> verify low `Karma` + high faction `REPU` keeps faction friendly -> save and reload.
  - *PASS:* `make_progression.py log` exits `0`; vanilla Starfield skill-tree prompt does not appear; all `20` `AVIF`s, chosen Background/Traits/Perk, and decoupled `Karma` + `REPU` values match pre/post-reload.

### CF-7 (Rank 7) — Unified Dialogue Host (`#792` 4-Option Wheel + Silent-Player Skill-Check List) & Dialogue Bug Audit
- **Why before volume:** Supports FO4's 4-option `SCEN` wheel alongside FO1/2/3/NV/76's numbered list + `[Skill/SPECIAL/Background/Trait]` prefix tags in one non-conflicting `DialogueMenu` layer (built beside `#792` without editing `#792`'s files), with silent-voice `.wem` timing hooks ready for subtitling — while auditing converted `DIAL`/`INFO`/`SCEN` stage-setters against each quest's known-bug list (broken topic conditions, stuck greeting loops, unfireable stage callbacks) under the clean-room rule.
- **PC Card for Claude (PC):**
  - *Stage/Install:* `python scripts/dialogue/concord_talk_install.py install --dir <STAGE>/concord-talk --starfield <SF_DIR>` + list-check companion plugin, accompanied by the converted conversation's known-bug ledger (fixed vs left + reproduction steps).
  - *Run:* Run Concord 4-option conversation + a multi-option `[Speech N]`/`[SPECIAL N]`/`[Background]`/`[Trait]` list conversation, including each listed dialogue/stage bug repro.
  - *PASS:* Both wheel (`<= 4` options) and list (`> 4` or list-tagged) conversations display cleanly, pass/fail deterministic NV-style checks accurately, advance quest stages per the known-bug ledger, and exit with `0` UI lockups.

### CF-8 (Rank 8) — Dual-Mode Radiation & Optional Mutations (`2a`), Hardcore `GPOF` Toggle (`2b`), and Gunplay (`BPTD` Hit Locations, VATS, NV Ammo Swap)
- **Why before volume:** Establishes the dual-mode radiation switch (`FO4` Max-HP cap vs `FO3/NV` 5-stage rad sickness, one RadAway cure, one Pip-Boy `STAT` display, optional FO76 `Mutation_*` `PERK`s off by default), the `GPOF` Hardcore toggle (`DEHY`/`HUNG`/`SLPD`, ammo weight, stimpak HoT, `0` conflict with held `SQ_ENV`), and shared `BPTD`/ammo combat rules so records from every game convert once.
- **PC Card for Claude (PC):**
  - *Stage:* Stage `FO4SFRads.esm` (`2a`), `FO4SFHardcore.esm` (`2b`), and combat/ammo hook.
  - *Run:* Enter `HAZD` zone / irradiated water / eat irradiated food -> verify Mode A (Max-HP cap) AND switch option to Mode B (FO3/NV stat-penalty thresholds) -> cure with RadAway -> test optional Mutation toggle -> toggle Hardcore `GPOF` ON/OFF -> test `BPTD` limb multipliers & ammo swap.
  - *PASS:* Log readers exit `0` across both radiation modes, RadAway cure, Pip-Boy `STAT` sync, Hardcore `GPOF` ON/OFF (`SQ_ENV` stays stopped), and limb/DT checks.

### CF-9 (Rank 9) — Settlements & C.A.M.P.s (`2c`), Dual-Form Power Armor (`2d`), A-Life Switch (`450/620 m`) & Earned-Cap Warfare Squads
- **Why before volume:** Proves save/reload persistence for workshops + C.A.M.P. beacons (`CMPO -> IRES`, FO4 `COBJ` + FNV `RCPE`), **both** Power Armor forms (climb-in `FURN` + `PowerArmorRace` w/ `6` limb `AVIF`s on `BPTD` + `FusionCore` drain + outfit restore, AND FNV NCR salvaged worn `ARMO` with no frame), `#799` A-Life `450/620 m` materialization, and the proposed `2 -> 4` `GLOB`-capped Warfare squad & upkeep rules.
- **PC Card for Claude (PC):**
  - *Stage:* Stage `FO4SFWorkshop.esm` (`2c`), `FO4SFPowerArmor.esm` (`2d`), and `FO4SFALife.esm` (`#799` + switch).
  - *Run:* (1) Deploy C.A.M.P. beacon (`002C60E9`), scrap FO4 junk (`CMPO -> IRES`), craft at bench, **save throwaway save, quit, reload**, verify station & workshop prompt persist; (2) climb into PA `FURN` frame, verify `FusionCore` drain, exit & verify outfit restore across save/reload, AND equip salvaged NCR PA directly as worn armor; (3) test `#799` `450/620 m` switch + `2`-cap Warfare squad recruitment/upkeep gates.
  - *PASS:* All log readers exit `0` with `0` crashes across save/quit/reload.

### CF-10 (Rank 10) — Unified Core Bundle, Registry Registration & 60-Minute Soak
- **Why before volume:** Replaces colliding ad-hoc probe installers with one deterministic `make_core_bundle.py` fold + registers every core plugin in `launcher/restore.py`, `test_kits.py`, and `crashwatch.py`, verified by `plugin_verify.py` (`#712`/`#725`).
- **PC Card for Claude (PC):**
  - *Stage/Verify:* Build & `verify` the single combined Core Bundle (`FO4TerrainCore.esm`, `FO4TerrainCore_Mars.esm`, `FO4Port.esm`, `FO4ActorRaider.esm`, `FO4SFMission.esm`, `FO4SFVaultGearDoor.esm`, `FO4SFExitLift.esm`, `FO4SFNewGame.esm`, `FO4SFPipboyTravel.esm`, `FO4SFALife.esm`, `FO4SFFortHagen.esm`, `FO4SFConcordTalk.esm`, `FO4SFListDialogue.esm`, `FO4SFProgression.esm`, `FO4SFRads.esm`, `FO4SFHardcore.esm`, `FO4SFWorkshop.esm`, `FO4SFPowerArmor.esm` — `<= 18` plugins, naming every plugin staged in `CF-1`..`CF-9` and well under Starfield's `253` full-master / `256` `BA2` limits).
  - *Run:* 60-minute continuous New Game -> Vault 111 exit -> Sanctuary -> Red Rocket workshop -> Concord fight & 4-option talk -> Pip-Boy Map fast travel -> save & reload soak.
  - *PASS:* `0` crashes, `0` `plugin_verify` warnings, `crashwatch` clean, all stage logs `ok`. **Volume asset work unlocks immediately upon CF-10 PASS.**

---

## 4. Multi-Title Asset Conversion Plan

### 4.1 Measured Source Inventory Across All Eight Installed Games

| Title | Install Size (Clean) | Archives on Disk | Archive Entries | Primary Plugin(s) & Walked Non-`GRUP` Records | Exterior / Interior `CELL`s | Terrain Source | Scripts (`Compiled` / `Source`) |
| :--- | ---: | :--- | ---: | :--- | ---: | :--- | :--- |
| **Fallout (1)** | `0.55 GiB` | `2` `.DAT` **v1** (BE tree, LZSS `0x40`) | `25,243` | `VAULT13.GAM` + `312` critter `.PRO` | `72` `.MAP` (`200x200` hex) | 2D `.FRM` tiles | `952` `.INT` / `0` `.ssl` |
| **Fallout 2** | `0.55 GiB` | `4` `.dat` **v2** (LE footer, zlib) | `30,926` | `data\*.txt` + `483` critter `.pro` | `155` `.MAP` (`200x200` hex) | 2D `.FRM` tiles | `1,443` `.int` (`+445` patch) / `0` `.ssl` |
| **Fallout Tactics** | `1.57 GiB` | `40` `.bos` (`PK\x03\x04` ZIP) | `36,470` | `1,498` `.ent` + `locale\*.txt` | `103` `.mis` | `29,957` `.til` tiles | `103` `.mis` FSMs / `0` text |
| **Fallout 3 GOTY** | `8.71 GiB` | `16` `.bsa` **v`0x68` (`104`)** | `159,030` unique | `Fallout3.esm` (`718,951`) + `5` DLC `.esm`s | `41,989` ext / `421` int | `40,256` `LAND` (`33x33` `VHGT`) | `1,257` `SCPT` / **`1,257` (`100%`) `SCTX`!** |
| **Fallout: New Vegas** | `9.23 GiB` | `21` `.bsa` **v`0x68` (`104`)** | `181,642` unique | `FalloutNV.esm` (`465,016`) + `9` DLC/pack `.esm`s | `30,109` ext / `388` int | `29,363` `LAND` (`33x33` `VHGT`) | `2,576` `SCPT` / **`2,576` (`100%`) `SCTX`!** |
| **Fallout 4 (`1.11.240`)** | `94.18 GiB` | `95` `.ba2` (`BTDX` **v1, v7, v8**) | `544,391` | `Fallout4.esm` (`1,549,276`) + `7` DLC + `9` CC | `38,970` ext / `1,195` int | `37,020` `LAND` (`33x33` `VHGT`) | `10,342` `.pex` (`7,875` base) / `10,282` `.psc` |
| **Fallout 76** | `92.97 GiB` | `43` `.ba2` (`BTDX` **v1**) | `688,096` | `SeventySix.esm` (`5,645,887`) + `NW.esm` | `50,532` ext / `2,664` int | **`Appalachia.btd` (`BTDB v6`, `1.45 GiB`)** | `7,234` client `.pex` / `0` `.psc` *(server `.pex` absent)* |
| **Starfield (`1.16.244`)** | `130.84 GiB` | `79` `.ba2` (`BTDX` **v2, v3** LZ4) | `1,581,655` | `Starfield.esm` (`3,829,246`) + `8` official `.esm`s | `18,732` ext / `11,985` int | `2,107` `.btd` tiles | `5,034` `.pex` / `5,033` `.psc` |

---

### 4.2 What the Pipeline Already Converts vs Shared & Per-Title Readers Needed

1. **Already Working & Verified on Fallout 4 (`src/fo4sf/` + `dotnet/`):**
   - **Archives (`src/fo4sf/ba2.py`):** Already reads `BTDX` `GNRL` and `DX10` across versions `1`, `7`, and `8` (`v1` 24-byte header layout for FO4 original, FO4 `1.11.x` Next-Gen/Anniversary, and FO76) as well as version `2` (Starfield uncompressed/`zlib`); Starfield version `3` `LZ4`-compressed entries remain the unsupported case documented in the module, while `src/fo4sf/bsa.py` (`v0x68`) is queued for FO3 and FNV ahead of their volume stages.
   - **Exterior Terrain, Statics & Navmesh (`90%` FO4 done):** `648,334 / 701,754` exterior objects placed (`FO4TerrainCore.esm`), `12,104 / 12,104` navmeshes, `6,249 / 6,275` lights, `5,185 / 5,294` containers, `12,438 / 13,241` items, `29 / 29` workshops, `269 / 344` benches, byte-exact S1 `.mesh` writer (`u16` index / `65,536`-vertex split check needed for oversized shapes), S3 `.mat` cloner + `texconv.exe` `BC1/BC4/BC5`, and `meshcollision.py` Havok tagfile transplant.
   - **Interiors (`325` load-door-reachable across `7` plugins; `269` converted in staged base + Automatron, `49` net-new DLC exported):** Out of `1,411` interior `CELL`s across seven plugins (`1,086` with no load door in; `371` in the earlier draft was the `test_name`-flagged count), `325` interiors are reachable by a load door (`298` from worldspaces + `27` behind interiors, including `7` `CTEST`/`cc*` test or Creation Club hook cells): **`269` are already converted in the staged base + Automatron build** (`16` installed in `FO4Port.esm` with `15` wired exterior load doors + `253` in `interiors_b01..b10`, `484,286` refs, `~4.44 GB` packed BA2s, covering every non-hook reachable base-game interior plus Automatron's `2`), and **`54` reachable DLC cell exports** (`49` net-new DLC cells across Nuka-World `28`, Far Harbor `20`, and Vault-Tec Workshop `1`, plus `5` overlapping cells already in `interiors_b10`) cover the remaining DLCs — **the gate is door wiring, the animated-door rebuild, and the CF-5 fidelity pass (`XESP`/`XLOC`/`XLKR`/`XAPR`/`TERM`), not conversion**.
2. **Directly Reusable Across Other 3D Titles (`SHARED` Pipeline Stages):**
   - **Heightmaps (`LAND` -> `.btd`):** `Fallout3.esm` (`40,256` `LAND`) and `FalloutNV.esm` (`29,363` `LAND`) use the **exact same `33 x 33` `VHGT` vertex heightgrid** as `Fallout4.esm` (`37,020` `LAND`), feeding our `.btd` writer directly. `Fallout 76` (`Appalachia.btd`, `BTDB v6`) is already in `.btd` format.
   - **Static `.mesh` + `.mat` + `texconv` + `BA2` Packaging:** Identical output stage for every title (`Archive2.exe` packing into `<Plugin> - Main.ba2` + `<Plugin> - Textures.ba2`).
3. **New Per-Engine Readers & Converters Required (`PER-TITLE` / `PER-ERA`):**
   - **FO3 & FNV Reader Pack (Built Once, Serves Both FO3 + FNV + All `14` DLCs):**
     1. **`src/fo4sf/bsa.py` (~180 lines, pure Python stdlib `zlib`):** Reads `BSA\x00` **version `0x68` (`104`)** (`offset 36`), handling folder/file hash tables and **bit `0x0100` embedded BString filenames** inside compressed payload blocks (`archive_flags = 0x0107` in `Fallout - Textures.bsa`). Zero external downloads needed.
     2. **`nif_bs34.py` (`v20.2.0.7`, `user=11`, `bsver=34`):** Reads `NiTriShape` / `NiTriStrips` geometry, extracts inline `BSShaderPPLightingProperty` / `BSShaderTextureSet` paths directly into our S3 `.mat` generator (FO3/FNV have no `.bgsm`), and converts Havok `hk_550`/`hk_660` `bhkRigidBody` / `bhkMoppBvTreeShape` primitives into `meshcollision.py`.
     3. **`esm_fo3nv.py` (`TES4` form version `2`, `HEDR` `0.94`/`1.34`):** Streams `WRLD`, `CELL`, `LAND`, `REFR`, `NAVM`, maps `CREA` (`533` FO3 / `1,578` FNV) + `ACRE` -> `NPC_` + creature `RACE`, maps `IMOD` (`50`) -> `OMOD`, `RCPE` (`105`) -> `COBJ`, `AMEF` (`54`) -> core ammo tables, and `REPU` (`13`) -> core reputation tables.
     4. **`obscript_transpile.py` (`SCTX` -> Starfield `.psc`):** Deterministic AST transpiler over the **verified `100%` unstripped `SCTX` sources** (`1,257` FO3 + `2,576` FNV `SCPT`s + embedded `INFO`/`PACK`/`TERM`/`PERK` `SCTX` snippets) targeting our `FO4SF_Shim_*` + `AVIF` core.
     5. **Audio/Voice Policy Compliance:** Per settled project policy (`combined-core.md` / `multi-game-future.md` `MG-03`), FO3 and FNV voice lines are **not** converted; the pipeline emits silent `.wem` files matched to source line durations so subtitles pace naturally.
   - **FO1, FO2 & Tactics Reader Pack:**
     1. **`dat_fo1.py` (`DAT v1` big-endian LZSS `0x40`), `dat_fo2.py` (`DAT v2` LE footer + `zlib`), and `zipfile` (`.bos` PKZIP):** Pure-Python streaming readers.
     2. **`.PRO` / `.MSG` / `.GAM` / `.ent` Importers + `.INT` Decompiler:** Emits items, critters, dialogue trees, quests, and overland nodes into Starfield `ESM` data; `.MAP`/`.mis` layout reader stamps 3D kit prefabs per Owner Decision `ISO-2`.
   - **FO4 Shared Actor/Animation Upgrade (`SHARED` for 3D Actors):**
     - Skinned Starfield `.mesh` writer + `129 -> 97` bone `.hkx -> .af/.rig` retargeter (`CALUMI.Animation` / SFSE clip player) + `.bgem` effect materials + `MSWP -> LMSW` swaps.
   - **Fallout 76 Reader Notes & Policy Gate:**
     - `ba2.py` already reads FO76's `43` `BTDX v1` archives; needs a `BSMesh` (`SeventySix - GeneratedMeshes.ba2`) reader and offline quest reconstruction for server-omitted `.pex` scripts. **Gated:** Per `docs/research/framework/findings/fo76-terms.md` and `combined-core.md` (`REL-60`), no FO76 extraction/conversion executes until the owner gives explicit go-ahead on the Bethesda ToS question.

---

### 4.3 Order of Titles, Disk Budgets & Time Budgets

#### Order of Titles (Maximizing Reuse at Every Step)
1. **Stage 1 — Fallout 4 Complete (`325` Load-Door-Reachable Interiors Across `7` Plugins: `269` Staged Base + Automatron + `49` Net-New DLC):** Exercises exterior door wiring (`347` Commonwealth exterior doors into `190` cells), the animated-door rebuild (`--animated-doors` with `--prev`), and CF-5's fidelity pass (`XESP`/`XLOC`/`XLKR`/`XTEL`/`TERM` + Papyrus shims) across the `269` already-converted base + `DLCRobot` interiors (`16` installed + `253` staged in `interiors_b10`, leaving zero non-hook base-game interiors to convert) and the `54` DLC interior exports (`49` net-new DLC cells + `5` overlapping cells) across `DLCworkshop01..03`, `DLCCoast` (Far Harbor), and `DLCNukaWorld` — gated on door wiring, the animated-door rebuild, and the fidelity pass, not conversion.
2. **Stage 2 — Fallout: New Vegas + `9` DLC/Packs:** Shares **100%** of the core's NV-style progression (`S.P.E.C.I.A.L.`, `13` Skills, `Traits`, `REPU`, `AMEF` ammo, `DEHY`/`HUNG`/`SLPD` Hardcore, `RCPE` crafting), proving `bsa.py` (`v0x68`), `nif_bs34.py`, `LAND -> .btd`, and `SCTX` ObScript transpilation on a `9.23 GiB` source footprint.
3. **Stage 3 — Fallout 3 GOTY + `5` DLCs:** Reuses **100%** of Stage 2's `BSA v0x68` + `bsver 34` + `SCTX` pipeline (`8.71 GiB` source; Pitt, Point Lookout, Broken Steel, plus sealed VR/orbit worlds Anchorage & Zeta).
4. **Stage 4 — Fallout (1) & Fallout 2:** Tiny source footprint (`1.10 GiB` combined); reuses 3D desert/vault/ruin kits already built in Stages 1–3 once Owner Decisions `ISO-1..3` are set.
5. **Stage 5 — Fallout Tactics:** (`1.57 GiB` source); reuses Stage 4's isometric tile-to-3D-kit pipeline + CF-9's `GLOB`-capped Warfare squad core (`2 -> 4` default, tunable for *Tactics* mission presets).
6. **Stage 6 — Fallout 76 (Appalachia Offline Story & World):** (`92.97 GiB` source); reuses FO4 `BA2 v1` + Starfield `.btd` pipeline; held behind owner `REL-60` gate.

#### Strict Disk & Time Budgets (`200 GB` Free Today, `60 GB` Hard Stop Floor)
- **Hard Disk Rule:** Work drive currently has **`~200 GB` free**; hard stop threshold is **`60 GB` free** (`140 GB` absolute ceiling; **operational cap `<= 100 GB` used so free disk stays `>= 100 GB`**).
- **Streaming Zero-Unpack Architecture:** Never bulk-extract whole `.ba2` or `.bsa` archives to loose files on disk. Stream entries directly in memory from read-only game archives -> convert -> pack directly into `<= 4.0 GiB` `.ba2` chunks via `Archive2.exe` -> delete staging loose scratch after each batch `verify` passes:

| Stage | Source Read (Read-Only) | Peak Transient Scratch | Final Packed `.ba2` + `.esm` Output | Est. PC Build Time | Active `BA2` Count |
| :--- | ---: | ---: | ---: | ---: | ---: |
| **Core Finish Line (`CF-1..CF-10`)** | Existing install | `<= 8 GB` | `~6.5 GB` (replaces current experiment set) | `~25 min` total across slices | `4–6` |
| **Stage 1a: FO4 Base + Automatron Interiors (`269` of `325` Reachable Staged)** | `94.2 GB` FO4 | `<= 15 GB` (door wiring, animated-door rebuild & CF-5 fidelity pass) | `~4.5 GB` (`3` `.ba2`s; `269` cells already converted; `54` DLC exports = `49` net-new + `5` overlap in Stage 1b) | `~30–45 min` (`269` cells cached; gated on door wiring, animated-door rebuild & fidelity pass, not conversion) | `+3` |
| **Stage 1b: FO4 DLCs (`Far Harbor`, `Nuka-World`, `Automatron`, `Workshops`)** | FO4 DLC BA2s | `<= 20 GB` | `~14 GB` (`5–6` `.ba2`s) | `~60–90 min` | `+6` |
| **Stage 2: Fallout: New Vegas + All DLC** | `9.2 GB` FNV | `<= 12 GB` | `~7.5 GB` (`3` `.ba2`s) | `~35–50 min` | `+3` |
| **Stage 3: Fallout 3 GOTY + All DLC** | `8.7 GB` FO3 | `<= 12 GB` | `~7.0 GB` (`3` `.ba2`s) | `~35–50 min` | `+3` |
| **Stage 4 & 5: FO1 + FO2 + Tactics** | `2.7 GB` total | `<= 5 GB` | `~2.5 GB` (`2` `.ba2`s, reuses 3D kits) | `~20–30 min` | `+2` |
| **Stage 6: Fallout 76 Appalachia *(if authorized)*** | `93.0 GB` FO76 | `<= 25 GB` (streamed by region) | `~22 GB` (`6–8` `.ba2`s) | `~90–140 min` | `+8` |
| **Cumulative All-Games Total** | *Already on disk* | **`<= 25 GB` peak at any moment** | **`~69 GB` packed** (`> 105 GB` free preserved!) | **`~5–7 hrs` unattended batch total** | **`~32` (`+79` vanilla = `111 < 256` cap)** |

#### Per-Title Converted-Quest Known-Bug Audit & Clean-Room Fix Protocol (Stages 1–6)
Converting `QUST` records, `Papyrus` `.psc` scripts (FO4/FO76), `SCTX` ObScript sources (FO3/FNV), `.INT` bytecode (FO1/FO2), or `.mis` mission FSMs (Tactics) mechanically also ports every unfixed bug shipped in the original games. Across **every** per-title volume stage above (Stages 1 through 6) and every converted-quest slice:
1. **Per-Quest Known-Bug Ledger:** Maintain a structured per-quest list of known bugs (broken stages, stuck NPCs/scenes, unreachable objectives, condition/variable typos, script errors) compiled from the original games' known-issue lists and community unofficial-patch changelogs — **recording bug names and plain functional descriptions only**.
2. **Case-by-Case Resolution:** For each listed bug, explicitly decide whether to fix it directly in our converter/quest pass, study how a community patch resolved it, or leave it deferred with rationale.
3. **Clean-Room & Zero-Mod-File Boundary:** "Studying" a community patch means reading its public changelog or documented change notes only — **zero files, scripts, records, or assets from any third-party mod ever enter Git or staging**, and **any external download requires explicit owner approval per download** requested via Claude (PC).
4. **Mandatory PC Card Bug Section:** Every converted quest's PC card explicitly lists: (a) which known bugs were fixed, (b) which known bugs were left as-is, and (c) the exact in-game or offline steps to reproduce and verify each one.

#### What the PC Must Run During Volume Stages
1. **Offline Converter Driver (Gemini PC or Launcher CLI, no game running):** Streams source archives, runs `dotnet` writers, `PapyrusCompiler.exe`, `texconv.exe`, `CALUMI.Animation`, and `Archive2.exe`, runs `plugin_verify.py` + `verify`, checks free disk `>= 60 GB` before and after every batch, and emits a PC test card + `plan.json` SHA-256 manifest.
2. **Creation Kit Headless/Batch Steps (Claude PC only when required):** `-MockWorldSpaceLOD:<Plugin>.esm <Worldspace>` for distant object LOD (`asset-pipeline.md`), and `-CompileFaceFXAnims` only if/when voiced FO4 lip-sync is enabled.
3. **In-Game Acceptance Walk (Claude PC only):** Installs packed `.ba2` + `.esm` via launcher/bundle installer, runs automated door/marker/quest/FPS smoke route, and records PASS receipt before moving to the next stage.

---

## 5. Binding Stop Rule & Execution Protocol

1. **Hard Stop on Unplanned Slices:** **No new branch, probe, or parallel feature slice opens unless it is explicitly listed in Section 2.2 (M1–M5) or Section 3 (CF-1..CF-10) of this plan.**
2. **One Active PR Per Collision Domain:** At most **one** open PR may modify each collision domain (`FO4SFNewGame` / `FO4SFPipboyMenu` / `DialogueMenu` / `ReferenceLinks` / `Launcher`) at a time, interleaving Area 1 (Quests, Dialogue, Scripts) and Area 2 (Fallout Mechanics) across independent domains. Grok `CLEAR` is required before any slice is **merged** (not before Phase B slices are built).
3. **Vault 111 Walk Outranks Everything:** Any issue reported by Claude (PC) from the owner's in-game walk of `#803` (`647635c8`) interrupts current work immediately until fixed, tested, pushed, and verified.
4. **Shared-File Coordination Rule:** Do not rework other agents' branches. Before touching shared Pip-Boy plugin host files (`sfse/FO4SFPipboyMenu/src/main.cpp`, `FO4SFPipboyMenu.ini`, `build.ps1`), `#792`'s dialogue slot files (build beside them instead), or `dotnet/NewGame` hold lists, post a one-line plan notice on GitHub Issue `#32` and restrict `main.cpp` edits to clean forwarders into dedicated module files.
5. **Progression Gate (`CF-6`):** Owner questionnaire decisions (`#806` `#issuecomment-6930665309`) satisfy the owner design gate; `CF-6` runs after `2a–2d`, and its first in-game test waits for Grok's review on `#806` or explicit Claude (PC) go-ahead on the `CF-6` PR.
6. **Converted-Quest Known-Bug Gate:** No converted quest slice merges without its per-quest known-bug list (names and descriptions only; clean-room fixes; zero third-party mod files; owner approval per download) and its PC card listing fixed bugs, unfixed bugs, and reproduction steps for each.
