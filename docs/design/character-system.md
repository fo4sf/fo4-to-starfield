Titles: All 7 Fallout titles (FO4, FO3, FNV, FO1, FO2, Tactics, FO76) | Modes: Story & Warfare (+ Survival hardcore layer) | Track: Track 2 (experimental core) shaping Track 1 character sheet — design only

# In-Game Character System & Fallout 4 Perk-Chart Fit (`X8(c2)`)

> **Status:** **Design only (no code or plugin changes in this PR).** Nothing in this document claims an in-game PASS for unrun systems. The `40`-point S.P.E.C.I.A.L. code change lands separately in Lane A (`A1(b)`), and the full 70-perk row-by-row classification table lands separately in `X10` (`docs/progression/fo4-perks-to-skills.md`).
>
> **Evidence Basis:** All record counts, FormIDs, `EditorID`s, `GMST` values, and `CTDA` condition totals below were read directly from `FalloutNV.esm`, `Fallout4.esm`, and official Fallout 4 add-on `.esm` files (read-only), cross-checked against `docs/progression/progression-core.md` (`#806`), `docs/core/port-requirements.md`, `src/fo4sf/core/core_values.json`, `src/fo4sf/progression/tables.py`, `dotnet/ProgressionCore/Program.cs`, `dotnet/NewGame/Program.cs`, `dotnet/CoreValues/Program.cs`, and `sfse/FO4SFPipboyMenu/`. Zero verbatim game dialogue, zero executable bytes, and zero local machine paths appear here.

---

## 1. What Is Already Settled (Do Not Reopen)

The owner's `16 Nov` design sign-off on PR `#806` (`docs/progression/progression-core.md`, `#issuecomment-6930665309`) and `21 Nov` directives already settle the core character-system architecture. This note summarizes those settled decisions only as the frame for the one open question in Section 4 — it does **not** reopen or rewrite `#806`.

| Settled Pillar | Owner-Confirmed Rule (`#806` & `21 Nov`) | Implemented / Tracked In |
|---|---|---|
| **In-Game vs. Launcher Boundary** | Only choices that require a game restart if changed mid-game belong in the launcher (world/title, plugin profile, SFSE/INI layer). S.P.E.C.I.A.L., skills, tag skills, backgrounds, traits, perks, difficulty, and hardcore/survival rules are chosen **in game**. | `docs/core/port-requirements.md` §2.2, `FO4SFNewGame.esm`, `FO4SFProgression.esm` |
| **Core Progression Frame** | Expanded **New Vegas-style base** (`BASE-PLUS-DATA`): **`13` skills** (`1..100`), **`3` personal Tag Skills** (`+15` each), initial skill formula `2 + 2*GovSPECIAL + ceil(LCK/2)`, and **`10 + floor(INT/2)`** skill points per level (`+2` with `Educated`). | `docs/progression/progression-core.md` §1.2, `src/fo4sf/progression/tables.py`, `FO4SFCoreValues.esm` (`0x820..0x82D`) |
| **S.P.E.C.I.A.L. Pool (`21 Nov`: "40 for all")** | **`40` total points across all 7 titles** (`1..10` base at creation: equivalently `5` base each + `5` unallocated, or `1` base each + `33` to spend). Fallout 4's `28`-point preset is no longer the default anywhere; legacy `21`-point constants are migrated in Lane A `A1(b)`. | `FO4SFCoreValues.esm` (`0x810..0x817`), `FO4SFProgression.esm`, `FO4SFNewGame.esm` (see Section 3) |
| **Backgrounds AND Traits** | Both coexist: choose **`1` of `9` Starfield-style Wasteland Backgrounds** (`+10` to `3` signature skills + `[Background]` dialogue flag; never trades/professions) **and `0..2` trade-off Traits** with **`1` free Vault/opening-exit respec** (`FO4SF_TraitRespecUsed`). | `FO4SFProgression.esm` (`0x820..0x828`, `0x830..0x838`, `0x80B`) |
| **Perk Cadence (`GLOB`-Driven)** | Driven strictly by `GLOB FO4SF_PerkCadenceLevels` (`0x809`, default `2` = `1` perk per `2` levels, tunable at runtime to `1`, `2`, `3`, etc. with zero fixed-cadence assumptions). Exact final cadence remains open for `X10` discussion without reopening the `GLOB` mechanism. | `FO4SFProgression.esm` (`0x809`, `0x80A`) |
| **Moral & Faction Axes** | **`Karma`** (`[-1000..+1000]`) and per-faction **`REPU`** (`Fame`/`Infamy` `4x4 = 16`-state New Vegas matrix) are **two completely independent axes**. | `FO4SFCoreValues.esm` (`0x830..0x832`), `FO4SFReputation.esm` |
| **Dual Radiation Rule** | Both rules exist behind a runtime gameplay option (`FO4SF_RadsRule`: Mode A FO4 Max-HP cap vs. Mode B FO3/FNV 5-stage stat sickness); per-title defaults come from world data. | `FO4SFRads.esm`, `FO4SFCoreValues.esm` (`0x800..0x805`) |
| **Survival Layer** | **Survival / Hardcore is a configurable layer** (GAMMA-style settings) over **Story** or **Warfare** — never a third game mode. | `FO4SFHardcore.esm`, `FO4SFCoreValues.esm` (`0x840..0x847`, `0x871..0x872`) |
| **Multi-Title Scope Classification** | Every character subsystem is classed **`SHARED`** (identical engine store/UI), **`BASE-PLUS-DATA`** (one engine rule fed by per-title tables), or **`PER-TITLE`** (title-only catalog/content) across all 7 Fallout titles (`FO4`, `FO3`, `FNV`, `FO1`, `FO2`, `Tactics`, `FO76`). | `docs/core/port-requirements.md` §1–2, `docs/research/core-fit-by-title.md` |

### Where `#806` Already Answers Part of the Fallout 4 Fit

`#806` and `docs/core/port-requirements.md` §2.3 already established:
1. The shared `AVIF` store (`FO4SFCoreValues.esm` `0x810..0x816` S.P.E.C.I.A.L. and `0x820..0x82C` `13` NV skills) is **`SHARED`** across all titles — Fallout 4 runs on these `13` skills too, rather than dropping skills.
2. The `40`-point S.P.E.C.I.A.L. pool, `9` Backgrounds, `0..2` Traits + exit respec, `GLOB` perk cadence, and decoupled `Karma` + `REPU` are **`SHARED` / `BASE-PLUS-DATA`**.
3. The **only open structural question** for this note is how **Fallout 4's skill-less `7x10` Perk Chart** (and all FO4 content that tests its perks via `HasPerk`) is carried inside that settled New Vegas-style frame.

---

## 2. Source Data Comparison: `FalloutNV.esm` vs. `Fallout4.esm`

Direct read-only inspection of the owner's `FalloutNV.esm` and `Fallout4.esm` (+ official DLCs) establishes the exact structural gap we must bridge:

| Dimension | `FalloutNV.esm` (Measured) | `Fallout4.esm` + Official DLCs (Measured) |
|---|---|---|
| **Starting S.P.E.C.I.A.L. Pool** | `40` points (`5` base each + `5` unallocated; `1..10`) | `GMST uSPECIALPoints = 28` (`1` base each + `21` to spend; `1..10`) |
| **Skills (`AVIF`)** | `13` dedicated skill `AVIF`s (`64` total `AVIF`s); `iLevelUpSkillPointsBase = 11` (+ `INT/2`), `fAVDTagSkillBonus = 15.0` | **`0` skill `AVIF`s** (`359` `AVIF`s total: `7` S.P.E.C.I.A.L. `0x2C2..0x2C8` + combat/companion/workshop variables) |
| **Traits** | `10` trait `PERK`s (`iTraitMenuMaxNumTraits = 2`) | **`0` traits** (`DATA.isTrait == 0` on all `538` `PERK`s) |
| **Playable Perks & Ranks** | `176` total `PERK`s: `10` traits, `91` playable perks (`175` w/ DLC), `75` non-playable; gated by `Level` + `Skill` + `SPECIAL` (`1` perk per `2` levels, `iMaxCharacterLevel = 30` base) | `538` total base `PERK`s: **`70` unique chart slots** (`7` SPECIAL × `10` rows) spanning **`229` unique base ranks** (`239` records incl. `4` gender-paired chains: `Aquaboy/girl`, `LadyKiller/BlackWidow`, `PartyBoy/Girl`, `ActionBoy/Girl`), **`+15` DLC chart ranks** (`+8` Far Harbor, `+7` Nuka-World -> **`244` unique ranks**), plus **`63` `Training*` (`7×9`)** S.P.E.C.I.A.L.-increase records (`302` base / `317` total playable chart records). Gated only by `GetBaseValue(SPECIAL)` (`CTDA fn=277`) + `Level` (`1` point/level, no level cap). Circular `NNAM` rank links. |
| **Crafting Recipes (`RCPE` / `COBJ`)** | `105` base `RCPE`s (`291` w/ DLC) gated primarily by skill `AVIF` thresholds (`Repair`, `Science`, `Survival`) + `17` `HasPerk` checks | **`2,161` base `COBJ`s**: **`1,009` recipes (`46.7%`) contain `1,204` `HasPerk` (`fn=448`) `CTDA`s**, overwhelmingly concentrated on **9 perk chains**: `Science01..04` (`415`), `Armorer01..04` (`371`), `GunNut01..04` (`286`), `Blacksmith01..03` (`53`), `LocalLeader02` (`45`), `CapCollector02` (`10`), `DemolitionExpert01..04` (`10`), `Chemist01` (`8`), `Medic01` (`6`). Official DLCs add **`+656` more `COBJ`s with `HasPerk`** (`DLCRobot`: `348`, `DLCNukaWorld`: `185`, `DLCCoast`: `113`, `DLCworkshop02`: `8`, `DLCworkshop01`: `2`) -> **`1,665` `HasPerk`-gated `COBJ`s total**. |
| **Dialogue Checks (`INFO` `CTDA`)** | `18,215` `DIAL` / `23,247` `INFO` with **`1,264` `GetActorValue` (`fn=14`)** conditions driving deterministic `[Skill N]` and `[SPECIAL N]` lines | `35,443` `DIAL` / `78,087` `INFO` with **only `126` `HasPerk` (`fn=448`) `CTDA`s** across just **`10` distinct perks**: `PowerArmorPerk` (`81`), `MS04ShroudCostumePerk` (`19`), `Locksmith01..03` (`13`), `PowerArmorCheaperSprinting` (`6`), `Hacker01..03` (`6`), `AnimalFriend01` (`1`). Zero weapon/crafting dialogue checks; persuasion uses `Charisma` `GMST`s (`fAVDCharismaBaseEasy=-35`, `Medium=-50`, `Hard=-65`, `Mult=15`). |
| **Books & Magazines (`BOOK`)** | `27` `BOOK`s (`17` permanent skill books `+3`/`+4` + temporary magazines) | `327` `BOOK`s: **`100` base perk-teaching magazines** (`DNAM` flag `0x10`, teaching **`41` distinct `PERK`s**), plus `+5` Far Harbor and `+5` Nuka-World (`110` total). |
| **Bobbleheads** | `0` (`7` implants + `Snow Globes` instead) | **`20` `BobbleHead_*` `MISC` items**: **`7` S.P.E.C.I.A.L.** (`+1` stat) + **`13` skill-named `PerkBobblehead*` `PERK` records** (`Barter`, `BigGuns`, `EnergyWeapons`, `Explosives`, `Lockpicking`, `Medicine`, `MeleeWeapons`, `Repair`, `Science`, `SmallGuns`, `Sneak`, `Speech`, `Unarmed`). |

> **Key Empirical Takeaway:** Fallout 4's perk dependency surface is **much narrower in dialogue** (`126` `INFO` checks, only `20` of which touch chart perks: `Locksmith01..03`, `Hacker01..03`, `AnimalFriend01`) and **massively concentrated in crafting** (`1,665` `COBJ` recipes across base + DLCs, `99%+` of which test only `9` perk chains: `Science`, `Armorer`, `GunNut`, `Blacksmith`, `LocalLeader`, `CapCollector`, `DemolitionExpert`, `Chemist`, `Medic`).

---

## 3. Exact Inventory: Every Place the S.P.E.C.I.A.L. Pool Number Lives in the Codebase

Per the `21 Nov` owner directive (**"40 for all"**), the actual code changes land in **Lane A `A1(b)`**, not in this design-only PR. The table below records every exact file, record, constant, and line number holding `28`, `21`, `40`, or `33` on `origin/main` (`92dcc0eb`) — plus the frozen Round 8 reference on `#840` (`086edc15`) — so `A1(b)` and future audits have a single complete map:

| Layer / File | Exact Lines / Record IDs | Current Value (`origin/main` `92dcc0eb`) | Role & `A1(b)` Disposition |
|---|---|---|---|
| `dotnet/NewGame/Program.cs` | Line `230`: `SpecialBase = 1, SpecialPoints = 21, SpecialMax = 10` | **`21` spendable (`28` total)** (`GAP-J3-05`) | **Must change in `A1(b)`** -> `SpecialPoints = 33` (`7 * 1 + 33 = 40` total). |
| `scripts/newgame/FO4SF_NewGameSpecial.psc` | Lines `37–39, 185`: `SpecialBase = 1`, `SpecialPoints = 21`, `SpecialMax = 10` | **`21` spendable (`28` total)** | **Must change in `A1(b)`** -> `SpecialPoints = 33` (`40` total). |
| `scripts/newgame/make_newgame.py` | Lines `202, 335`: `SPECIAL_BASE, SPECIAL_POINTS, SPECIAL_MAX = 1, 21, 10` | **`21` spendable (`28` total)** | **Must change in `A1(b)`** -> `SPECIAL_POINTS = 33` (`SPECIAL_MAX_PRESSES` verified `> 10 * (33 + 1)`). |
| `tests/test_newgame.py` | Lines `644–697, 1785`: parity assertions on `SpecialPoints` and log string `"21 points unspent"` | Expects `21` | **Must update in `A1(b)`** to `33` (`40` total). |
| `dotnet/ProgressionCore/Program.cs` | Lines `9, 38, 61, 91, 133–134, 241, 352, 430, 582–594`: `GLOB FO4SF_SpecialPool28` (`0x808`, default `0`), `StandardSpread40 = {6,5,5,6,7,6,5}`, `StandardSpread28 = {4,4,4,4,4,4,4}` | Default **`40`** (`pool28 = 0`); `28` opt-in `GLOB` | Already defaults to `40`. Keep `FO4SF_SpecialPool28` (`0x808`, default `0`) **only** if existing tests/scripts read it; never default it to `1` (`A1(b)` records whether kept or retired). |
| `scripts/progression/FO4SF_ProgressionQuest.psc` | Lines `12, 35–36, 212, 270–274, 371–373, 472, 496–508, 907, 956`: `ActiveSpecialPool()` returns `28` if `Pool28Global >= 0.5` else `40` | Default **`40`** (`Pool28Global = 0`) | Already defaults to `40` (`StandardSpread40`). |
| `scripts/progression/make_progression.py` | Lines `186, 212, 223, 407`: CLI `--pool28` (`0\|1`, default `0`) | Default **`0` (`40` pts)** | Already defaults to `40`. |
| `src/fo4sf/progression/tables.py` | Lines `25–26, 114–125`: `SPECIAL_POOL_DEFAULT = 40`, `SPECIAL_POOL_FO4_OPT = 28`, `validate_special_allocation(..., use_fo4_pool_28=False)` | Default **`40`** | Already defaults to `40`. |
| `src/fo4sf/core/core_values.json` (+ `dotnet/CoreValues/Program.cs`) | Lines `61–143` (`AVIF 0x000810..0x000816` `FO4SF_Special_*`, `default: 5.0`, `min: 1.0`, `max: 15.0`); Lines `530–578` (`GLOB 0x000880..0x000886` `FO4SF_SpecialMenuPendingS..L`, `default: 5.0`) | Base `5.0 × 7 = 35` (`+5` unallocated = **`40`**) | Already aligned to `40` (`5` each + `5` pool). Note: `FO4SF_SpecialPool28` is not yet promoted into `FO4SFCoreValues.esm` (`docs/core/port-requirements.md` §2.1). |
| `sfse/FO4SFPipboyMenu/FO4SFPipboyMenu.ini` | Line `61`: `SpecialMaxPoints=40` | **`40`** | Already `40`. |
| `sfse/FO4SFPipboyMenu/src/main.cpp` | Lines `565, 7412–7683, 9894`: `g_specialMaxPoints = 40` (`std::clamp(ReadNumber(ini, L"SpecialMaxPoints", 40), 7u, 70u)`) | **`40`** | Already `40`. |
| `scripts/ui/make_pipboy_stage_ini.py` | Lines `492, 513, 545, 623, 699, 749, 796`: `--special-max-points` default `40` | **`40`** | Already `40`. |
| `tests/test_progression_core.py`, `tests/test_pipboy_stage_ini.py`, `tests/test_bundle_log_judges.py` | `test_special_40_pool_default_and_28_glob_option`, `SpecialMaxPoints=40`, `pool28=0` | Tests default **`40`** + `pool28=1` opt-in | Keep green; adjust only if `A1(b)` retires `pool28`. |
| `docs/testing/candidate-2e-card.md` (frozen on `#840` `086edc15`) | References `"28-pt"` lift fallback (`FO4SF_NewGameSpecial`) | **`28`-pt** (frozen) | Do **not** edit `candidate-2e-card.md`; `candidate-2f-card.md` (`A1(f)`) states `40` total (`33` points to spend from base `1`). |

> **Arithmetic Consistency Note (`#806` vs. `FO4SF_NewGameSpecial`):** `#806` defines the `40`-point pool as **`5` base in each of 7 attributes + `5` unallocated (`35 + 5 = 40`)** with stats lowerable to `1` (`min 1`, `max 10`), whereas `FO4SF_NewGameSpecial` starts at **`1` base in each + `33` to spend (`7 + 33 = 40`)**. Both represent the exact same mathematical domain (`7` integers in `1..10` summing to **`40`**). When the native `SPECIALMenu.swf` or Progression's paged menu is used, starting at `5` each (`+5` unallocated) is faster to tweak; in `FO4SF_NewGameSpecial`'s additive `+1`-button fallback, starting at `1` each (`+33` to spend) avoids needing decrement buttons while enforcing the identical `sum == 40` invariant.

---

## 4. The Open Problem: Fitting Fallout 4's Perk Chart Into the Decided NV-Style Frame

Fallout 4 removed skills and traits entirely, compensating by turning its `7x10` Perk Chart into **three systems mashed into one grid**:
1. **Skill replacements** (weapon damage scaling like *Rifleman*/*Commando*/*Gunslinger*/*Heavy Gunner*/*Big Leagues*/*Iron Fist*, gatekeepers like *Locksmith* and *Hacker*, crafting tiers like *Gun Nut*/*Armorer*/*Science!*/*Blacksmith*/*Chemist*, healing/stealth/barter scaling like *Medic*/*Sneak*/*Cap Collector*).
2. **S.P.E.C.I.A.L. boosts** (`63` `Training*` records — needed because FO4 started at `28` points instead of `40`).
3. **Genuine build-defining perks** (*Bloody Mess*, *Idiot Savant*, *Grim Reaper's Sprint*, *Blitz*, *Nerd Rage!*, *Pain Train*, *Ricochet*, *Mysterious Stranger*, *Local Leader*, *Robotics Expert*, *Intimidation*, etc.).

Because `#806` restores `13` skills, `40` S.P.E.C.I.A.L. points, Backgrounds, Traits, and a `GLOB`-driven perk cadence (default `1` perk every `2` levels), dropping FO4's unmodified `7x10` chart (`229` base / `244` DLC unique ranks + `63` Training ranks) straight onto our NV base breaks progression math unless we choose a clean architectural bridge.

Below are **three concrete options** evaluated against `Fallout4.esm`'s measured records and all 7 Fallout titles.

---

### Option 1: Split & Fold (`BASE-PLUS-DATA`)

**How it works:**
- **Skill-like FO4 perk ranks fold directly into the `13` NV skills** at canonical `25 / 50 / 75 / 100` thresholds (Novice `0`, Advanced `25`, Expert `50`, Master `75`, pinnacle/bonus `100`). Examples: *Locksmith 1–3* -> `Lockpick 25/50/75`; *Hacker 1–3* -> `Science 25/50/75`; *Gun Nut 1–4* & *Armorer 1–4* -> `Repair` (or split with `Science`); *Science! 1–4* -> `Science`; weapon-class linear `+20%` ranks -> continuous skill scaling (`Guns`, `Energy Weapons`, `Explosives`, `Melee Weapons`, `Unarmed`). (Exact perk-by-perk mapping belongs to `X10` `docs/progression/fo4-perks-to-skills.md`.)
- **Unique FO4 perks** (and non-linear milestone effects from split perks, such as *Locksmith 4* unbreakable bobby pins or *Demolition Expert 2* throwing arc) stay in the selectable perk list as **`PER-TITLE` / `BASE-PLUS-DATA` perk entries** using NV-style requirements: **`(MinLevel + S.P.E.C.I.A.L. + optional Skill)`**.
- **Top-row stat rescale (`9..10 -> 8..9 + Skill/Level`):** Under a `40`-point pool without `63` `Training*` perk ranks (`Intense Training` optional, capped), FO4's row-9 and row-10 perks (`14` chart slots) rescale to `SPECIAL 7..9` plus a Skill/Level gate (matching FNV's perk requirement spread, where only rare capstone perks ask for `8–9` in a single stat).
- **Converter rewrite:** The FO4 -> Starfield converter rewrites every `COBJ` `HasPerk` (`1,009` base + `656` DLC), lock/terminal check, and `INFO` `HasPerk` (`20` chart-perk dialogue lines) into `GetValue(FO4SF_Skill_*) >= threshold` `CTDA` conditions.

**Strengths:**
- Cleanest gameplay feel: **zero double-dipping** (spending skill points actually unlocks locks, terminals, and crafting tiers just like FO3/FNV; perk picks remain meaningful build definers under a `1`-per-`2`-levels cadence).
- True `BASE-PLUS-DATA` parity across `FO4`, `FO3`, `FNV`, `FO1`, `FO2`, `Tactics`, and `FO76` — one character sheet, one UI, one rule set.
- Retires the `63` `Training*` bloat cleanly under the `40`-point pool.

**Risks / Costs:**
- **High converter fragility for FO4 `HasPerk` callers:** Rewriting `1,665` `COBJ`s (`1,204+` `CTDA`s) is mechanical, **but** FO4 also checks `HasPerk` inside **compiled Papyrus quest/terminal/workshop/item scripts** (not only `COBJ`/`INFO` `CTDA`s), plus `100+` magazines and `20` bobbleheads have custom effects tied to FO4 perk mechanics. Any missed script `HasPerk(Locksmith02)` or `HasPerk(Science01)` silently fails unless patched in every Papyrus script.

---

### Option 2: `PER-TITLE` Chart Preserved Over Derived Skills

**How it works:**
- Keep Fallout 4's full `7x10` Perk Chart (`70` perks, `229` base / `244` DLC ranks) as Fallout 4's **`PER-TITLE`** perk catalog alongside the `13` NV skills.
- Skills still advance via `10 + floor(INT/2)` skill points per level, and either:
  - **(2a) Mirror/Additive:** Skills scale baseline weapon accuracy/damage/barter/healing while FO4's perk ranks remain manually purchasable on top; or
  - **(2b) Double-Gated:** Skills act as prerequisites (`Guns >= 40` to buy *Rifleman 2*), while the player still has to spend a perk point to buy the rank.

**Strengths:**
- Zero `COBJ` or `HasPerk` rewrite needed: all `1,665` `COBJ` recipes, `126` `INFO` lines, and FO4 Papyrus scripts work unmodified.
- Preserves Fallout 4's visual `7x10` chart identity for players expecting FO4's exact perk names and ranks.

**Critical Traps (Why Option 2 Fails Under `#806`):**
1. **The Double-Dipping / Stacking Trap (2a):** If `Guns = 100` already doubles ballistic damage (NV formula `0.5 + 0.005 * skill`) **and** *Rifleman 5* adds another `+100%` damage, FO4 combat math explodes (`4x` unintended damage multiplier) — or if skills are nerfed to cosmetic `±10%` to avoid stacking, the `13` NV skills become meaningless busywork in FO4.
2. **The Double-Tax / Cadence Starvation Trap (2b):** Under `#806`'s default `FO4SF_PerkCadenceLevels = 2` (`1` perk every `2` levels), a level-30 character gets **`15` perk points total**. Buying just *Locksmith 1–3* (`3`), *Hacker 1–3* (`3`), *Gun Nut 1–4* (`4`), and *Armorer 1–4* (`4`) consumes **`14` of `15` perk points** — leaving literally **1 real perk** by level 30, even though the player already invested hundreds of skill points into `Lockpick`, `Science`, and `Repair`! Forcing `cadence = 1` to feed `244` chart ranks breaks cross-title character parity with FNV/FO1/FO2.
3. **Cross-Title Carry Breakage:** A carried character crossing from FNV (`Lockpick 100`, `Science 100`, `Repair 100`) into FO4 cannot pick an Advanced lock or mod a receiver until they burn `10+` FO4 perk points re-buying skills they already mastered.

---

### Option 3: Hybrid Dual-Gate Adapter (Hidden Compatibility Perk Shim)

**How it works:**
- Keep Fallout 4's skill-tier `PERK` records (`Locksmith01..03`, `Hacker01..03`, `GunNut01..04`, `Armorer01..04`, `Science01..04`, `Blacksmith01..03`, `Chemist01`, etc.) **present in the FO4 title plugin as hidden, non-selectable compatibility records** (`playable = 0, hidden = 1`) — stripped of duplicate damage/stat entry points so they **never double-dip** with skill formulas.
- A single lightweight Progression sync handler (`SyncSkillTierPerks()`, called on creation, level-up, skill book/bobblehead grant, and respec) **automatically grants/revokes** those hidden compatibility perks whenever the player's `FO4SFCoreValues.esm` skill crosses its threshold (`25 / 50 / 75 / 100`):
  - e.g., `FO4SF_Skill_Lockpick >= 25` -> auto-grants `Locksmith01` (compatibility flag only); `>= 50` -> `Locksmith02`; `>= 75` -> `Locksmith03`.
  - e.g., `FO4SF_Skill_Science >= 25/50/75/100` -> auto-grants `Hacker01..03` and `Science01..04` (compatibility flags only).
- **Unique FO4 perks** (and unique milestone ranks like *Locksmith 4* unbreakable picks) remain **normal player-selectable perks** under `#806`'s NV-style `(Level + S.P.E.C.I.A.L. + Skill)` list and `GLOB` cadence.

**Strengths:**
- **Zero broken `HasPerk` checks anywhere in Fallout 4** — all `1,009` base + `656` DLC `COBJ` recipes, all `20` chart-perk `INFO` dialogue lines, and every vanilla Papyrus script calling `Player.HasPerk(GunNut02)` or `HasPerk(Hacker03)` work **immediately and identically** without hand-editing `1,665` recipes or hunting hidden script checks.
- **Zero double-dipping** because the auto-synced shim perks carry no redundant damage/healing `PRKE` entry points (skills own the scaling; the shim perks act purely as compatibility gate tokens).
- **Clean carried-character transfer:** A character arriving in the Commonwealth from New Vegas with `Science 75` and `Repair 50` automatically syncs the matching FO4 crafting/hacking shims on entry — zero re-buying.
- **Progressive migration path:** Over time, the FO4 converter can still replace `COBJ` `HasPerk` `CTDA`s with direct `GetValue(FO4SF_Skill_*)` checks (so workbench tooltips show `"Requires Repair 50"` instead of `"Requires Gun Nut Rank 2"`), while the shim guarantees nothing ever breaks in between.

**Risks / Costs:**
- Workbench UI tooltips still display the FO4 perk name (`"Requires Science! Rank 2"`) until the `COBJ` converter rewrites the `CTDA` (or renames the hidden shim perk's `FULL` string to `"Science 50"` — a 1-line data trick that makes stock workbench tooltips read `"Requires Science 50"` immediately!).
- Adds ~`25–30` hidden compatibility `PERK` records inside the `FO4` title plugin (`PER-TITLE` adapter layer) and one small deterministic `SyncSkillTierPerks()` pass (pure `O(N)` table loop, zero polling).

---

## 5. Content Impact Matrix: Fallout 4 Content & Later Titles

| Content / Title Area | Option 1 (Pure Split & Fold) | Option 2 (`PER-TITLE` Chart Over Skills) | Option 3 / Recommended (**Option 1 + Hidden `HasPerk` Shim**) |
|---|---|---|---|
| **FO4 Skill Checks It Never Had vs. `126` `HasPerk` Dialogue Lines** | `20` chart-perk `INFO` lines (`Locksmith`, `Hacker`, `AnimalFriend`) rewritten to skill `CTDA`s; `Charisma` persuasion maps cleanly onto `Speech` (+ `CHA` bonus) in `FO4SFListDialogue`; future optional FO4 dialogue skill checks plug directly into `FO4SF_Skill_*`. | `126` `INFO` lines stay untouched, but `Speech` skill fights FO4's raw `Charisma` persuasion formula unless one is disabled; players still have no skill-based lock/hack dialogue unless they buy perks. | `100%` of `126` `INFO` `HasPerk` lines work immediately via shim (`PowerArmorPerk`/`MS04ShroudCostumePerk` untouched; `Locksmith`/`Hacker` synced from skills); `Speech` replaces raw `CHA` RNG cleanly; new skill checks read `FO4SF_Skill_*` directly. |
| **FO4 `COBJ` Workbench Recipes (`1,009` base + `656` DLC)** | Converter must rewrite all `1,665` `COBJ` `HasPerk` `CTDA`s (`9` perk chains) to `GetValue(FO4SF_Skill_*) >= 25/50/75/100`. One missed DLC/script check breaks crafting. | All `1,665` recipes work unmodified, **but** players are forced to spend scarce perk points (`14+` ranks) on crafting gates instead of skills. | All `1,665` recipes work **out of the box** via auto-synced shim perks (renamed `"Repair 50"`, `"Science 75"`, etc. for clean UI text), and converter can migrate `COBJ`s to native skill `CTDA`s cleanly at its own pace. |
| **Lockpicking & Terminal Tiers (`Novice..Master`)** | Directly read `FO4SF_Skill_Lockpick` / `FO4SF_Skill_Science` at `0/25/50/75` (NV standard). | Double-gated or ignores `Lockpick`/`Science` skills completely. | Reads `0/25/50/75` skill thresholds cleanly; hidden `Locksmith01..03` / `Hacker01..03` shims satisfy any Starfield/FO4 engine or quest lock check. |
| **FO4 Magazines (`100` base + `10` DLC, `41` distinct perks)** | Unique-effect magazines (e.g., *Picket Fences*, *Total Hack*, *Hot Rodder*, *Astoundingly Awesome Tales*) stay as permanent `PERK` rewards; weapon/stealth/barter scaling magazines convert cleanly to small permanent skill bonuses (`+2..+3` skill, matching FNV skill books) or keep their small `5%` perk bonuses without conflicting with skills. | Keep all `110` magazines untouched; risk stacking on top of already-stacked skill + chart multipliers. | Same clean rule as Option 1: unique unlock magazines keep their `PERK`s untouched (`HasPerk` intact); numeric skill magazines grant either their exact vanilla micro-perk or `+2/+3` permanent skill points (controlled by `X10` balance pass). |
| **FO4 Bobbleheads (`7` S.P.E.C.I.A.L. + `13` Skill-Named)** | **`7` S.P.E.C.I.A.L. bobbleheads** grant `+1` stat (allow `10 -> 11` like FO4, or cap `10` per NV rule); **`13` skill-named bobbleheads** map almost `1:1` to the `13` NV skills (`+10` permanent skill like FO3, or keep FO4 micro-perk). Only `SmallGuns` + `BigGuns` both feed `Guns` (e.g., `+5` `Guns` each, or `BigGuns` gives `+5` `Guns` + heavy handling) while `Survival` gets its bonus from an existing magazine/DLC collectible or *Wasteland Survival Guide*. | `13` skill bobbleheads keep FO4's flat `+10%`/micro-perks, leaving no permanent skill bobbleheads in FO4 despite having `13` skills. | Maps `7` S.P.E.C.I.A.L. (`+1` stat) and `13` skill-named bobbleheads directly onto `FO4SF_Skill_*` (`+10` skill, or `+5` split for `SmallGuns`/`BigGuns` -> `Guns`) while optionally keeping `PerkBobblehead*` as hidden completion flags for any display-stand / achievement check. |
| **FO4 `Training*` (`63` stat-up records)** | Retired from the chart (replaced by the `40`-point pool + optional capped *Intense Training* perk / bobbleheads / implants). | Remains on the chart, letting a `40`-point character max all `7` stats to `10` cheaply and breaking build trade-offs. | Retired from the chart (same as Option 1); `40`-point pool + bobbleheads/implants preserve meaningful S.P.E.C.I.A.L. build identity. |
| **Later Titles: `FO3` & `FNV`** | **`1:1` native fit.** `FO3` (`Big+Small Guns -> Guns`, `93` perks) and `FNV` (`13` skills, `10` traits, `175` perks, `105/291` `RCPE`) drop straight into the identical `BASE-PLUS-DATA` system with zero special cases. | Forces two completely incompatible progression paradigms (NV skill-driven in `FO3`/`FNV` vs. perk-chart-driven in `FO4`), breaking cross-game carry and UI consistency. | **`1:1` native fit.** `FO3` and `FNV` need zero shims (`SyncSkillTierPerks()` is simply a no-op when FO4's title perk pack is not loaded). |
| **Later Titles: `FO1`, `FO2` & `Tactics`** | **`18 -> 13` skill fold** (`First Aid+Doctor -> Medicine`, `Traps+Throwing -> Explosives`, `Steal -> Sneak`, `Outdoorsman -> Survival`, `Gambling -> Barter+LCK`), `0..2` traits, `40`-pt pool, `GLOB` cadence (`3`). Clean uniform ruleset across all classic titles. | FO4 becomes an outlier that shares neither UI nor build math with `FO1`/`FO2`/`Tactics`. | Same clean `18 -> 13` fold as Option 1; every title from `FO1` through `FO4` uses the exact same `7` S.P.E.C.I.A.L. + `13` Skills + Backgrounds + Traits + `GLOB`-cadence Perks character sheet. |
| **Later Title: `FO76`** | `401` `PCRD` cards map into the same split: skill-tier cards (`Picklock`, `Hacker`, `Gunsmith`, `Armorer`) fold into skills, unique cards become perks, `LOUT` punch-card respec stays optional outside Hardcore. | Would require yet another separate per-title card-slot UI incompatible with both NV and FO4. | Same clean `BASE-PLUS-DATA` fold + optional hidden compatibility tokens if any `FO76` recipe/quest checks a `PCRD` `PERK`. |

---

## 6. Recommendation

**Recommend: Option 1 (Split & Fold — `BASE-PLUS-DATA`) backed by Option 3's Hidden `HasPerk` Compatibility Shim.**

Why this combination is strictly strongest across Track 1 (Fallout 4 playable path) and Track 2 (all 7 Fallout titles):
1. **Honors every settled `#806` and `21 Nov` decision cleanly:** One unified New Vegas-style character sheet (`40`-point S.P.E.C.I.A.L., `13` skills + `3` tags, `9` Backgrounds, `0..2` Traits + exit respec, `GLOB`-driven perk cadence) governs all 7 Fallout titles, both modes (`Story` & `Warfare`), and `Survival` without double-dipping or perk-cadence starvation.
2. **Eliminates Fallout 4 conversion breakage (`1,665` `COBJ` recipes + `126` `INFO` lines + Papyrus `HasPerk`):** By keeping FO4's folded skill-tier perks as hidden, zero-bonus compatibility tokens auto-synced at `25 / 50 / 75 / 100` skill thresholds (with their display names set to `"Repair 50"`, `"Science 75"`, etc. until `COBJ` `CTDA`s are natively rewritten), Track 1 gets immediate, 100% compatible crafting, lockpicking, hacking, and dialogue with zero manual recipe surgery.
3. **Preserves Fallout 4's best unique perks and collectibles:** Genuine build-defining FO4 perks (*Blitz*, *Idiot Savant*, *Pain Train*, *Nerd Rage!*, *Local Leader*, *Robotics Expert*, etc.) remain selectable perks with rescaled `(Level + S.P.E.C.I.A.L. + Skill)` gates (`9..10` rows eased to `7..9 + Skill/Level`), `110` magazines stay meaningful rewards, and `20` bobbleheads (`7` S.P.E.C.I.A.L. + `13` skill-named) fit the `13`-skill sheet naturally.
4. **Zero rework when `FO3`, `FNV`, `FO1`, `FO2`, `Tactics`, and `FO76` arrive:** The hidden compatibility shim lives strictly inside the Fallout 4 title perk pack (`PER-TITLE` adapter), keeping `FO4SFProgression.esm` and `FO4SFCoreValues.esm` 100% game-agnostic.

*(Detailed perk-by-perk classification of all 70 Fallout 4 chart perks + DLC ranks, plus analysis of whether crafting/leadership warrant any new skill beyond the 13, is handled in companion note `X10` `docs/progression/fo4-perks-to-skills.md`.)*

---

## 7. Owner Decision Needed

1. **Fallout 4 Perk-Chart Fit (`X8(c2)`):** Do you approve the recommended **Option 1 (Split & Fold into the `13` skills) + Option 3's Hidden `HasPerk` Compatibility Shim** so Fallout 4 uses the exact same NV-style `13`-skill + perk-list character sheet as all other titles while keeping all `1,665` FO4 `COBJ` recipes and `HasPerk` checks working unmodified — or do you prefer pure **Option 1** (rewrite every `COBJ`/`INFO`/script `HasPerk` directly with no shim) or **Option 2** (preserve Fallout 4's full `7x10` chart as a `PER-TITLE` catalog over skills)?
