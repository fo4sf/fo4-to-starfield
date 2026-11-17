# Player Creation & Progression Core (`FO4SFProgression.esm`, `CF-6`)

Implements the shared multi-title Fallout progression and character-creation core (`CF-6`, Phase B item `2e`), combining **Backgrounds and Traits on a New Vegas-style base** (`BASE-PLUS-DATA`) per all confirmed owner decisions in PR `#806` (`#issuecomment-6930665309`).

> [!IMPORTANT]
> **In-Game Test Gate (`CF-6` Rule):** Owner design sign-off (`#806` `#issuecomment-6930665309`) unblocks offline construction, unit tests, and clean-core `stage` / `fold` / `verify`. Before the **first in-game test** of `FO4SFProgression.esm`, either **Grok must have reviewed PR `#806`** or **Claude (PC) must have given explicit go-ahead on this PR**. Until one of those two events occurs, stop after Step 1 (`verify: ok`, offline-verified stage).

---

## 1. Confirmed Design Rules & Mathematical Spec

1. **`7` S.P.E.C.I.A.L. Attributes (`0x800..0x806`, **`40`-Point Pool**):**
   - `FO4SF_Special_Strength`, `Perception`, `Endurance`, `Charisma`, `Intelligence`, `Agility`, `Luck` (`1..10` base at creation, `5` each + `5` pool = **`40` total points**, New Vegas standard).
   - `GLOB FO4SF_SpecialPool28` (`0x808`, default `0`): Fallout 4's `28`-point preset is kept **only** as an off-by-default `GLOB` option (`1` switches creation validation from `40` to `28`).
   - Derived stats synced live: `CarryWeight = 150 + 10 * STR (-15 Small Frame)`, `MaxHP = 90 + 20 * END + 5 * (Level - 1)`, `ActionPoints = 65 + 3 * effAGI (+15 Kamikaze)`, `CompanionNervePct = 5 * CHA`.

2. **`13` New Vegas Skills (`0x810..0x81C`, `1..100`):**
   - `Barter` (`CHA`), `Energy Weapons` (`PER`), `Explosives` (`PER`), `Guns` (`AGI`), `Lockpick` (`PER`), `Medicine` (`INT`), `Melee Weapons` (`STR`), `Repair` (`INT`), `Science` (`INT`), `Sneak` (`AGI`), `Speech` (`CHA`), `Survival` (`END`), `Unarmed` (`END`).
   - Initial value: `2 + 2 * GoverningSPECIAL + ceil(LCK / 2)` + **`+10` to the chosen Background's `3` signature skills** + **`+15` to the player's `3` personal Tag Skills** + Trait adjustments, clamped `1..100`.
   - Level-up skill points: `10 + floor(INT / 2)` (`+2` when `FO4SF_Perk_Educated` is held).

3. **Backgrounds (`0x820..0x828`, Choose `1` at Start — Never Trades/Professions):**
   - `9` game-neutral Wasteland origins in `FLST FO4SF_BackgroundPerks` (`0x82F`): `Vault Dweller`, `Wasteland Scavenger`, `Caravan Guard`, `Field Medic`, `Brotherhood Scribe`, `Enclave Remnant`, `Tribal Hunter`, `Desert Ranger`, `Minuteman Volunteer`.
   - Grants `+10` to `3` signature skills, a permanent `[Background]` `PERK` flag for `DialogueMenu` (`CF-7`), and optional Combined/Warfare faction-start hooks.

4. **Traits (`0x830..0x838`, Choose **`0..2`** at Start + **`1` Free Exit Respec**):**
   - `9` trade-off `PERK`s in `FLST FO4SF_TraitPerks` (`0x83F`): `Small Frame`, `Trigger Discipline`, `Fast Shot`, `Kamikaze`, `Heavy Handed`, `Four Eyes`, `Good Natured`, `Skilled`, `Wild Wasteland`.
   - `GLOB FO4SF_TraitRespecUsed` (`0x80B`, default `0`): allows **one free Trait respec** at the Vault / opening exit rebuild prompt (`Stage 25`), after which `FO4SF_TraitRespecUsed` locks at `1`.

5. **Perks on a Purely `GLOB`-Driven Cadence (`0x840..0x847` in `FLST` `0x84F`):**
   - `GLOB FO4SF_PerkCadenceLevels` (`0x809`, default **`2`** = `1` Perk per `2` levels): tunable at runtime to `1`, `2`, `3`, etc. with **zero fixed-cadence assumptions** (`grants_perk_at_level(level, cadence)` queues `FO4SF_QueuedPerkPoints` whenever `level >= 2` and `(level % cadence) == 0` or `cadence == 1`).

6. **Decoupled `Karma` AND Per-Faction `REPU` (`2` Independent Axes):**
   - **`AVIF` / `GLOB` `FO4SF_Karma` (`0x807` / `0x80C`, `[-1000..+1000]`):** Moral axis (`Very Evil`, `Evil`, `Neutral`, `Good`, `Very Good`) gating moral dialogue, good/evil companion loyalty, and ending slides — **never** alters faction hostility or vendor prices.
   - **Per-Faction `Fame` & `Infamy` `GLOB` Pairs (`0x860..0x86B`, `0..100` each) + Allied/Enemy `FACT` Sync (`0x870..0x875`):** Implements the `4 x 4 = 16`-state New Vegas `REPU` matrix (`Neutral`..`Idolized`..`Vilified`..`Wild Child`). A player with `-800` `Karma` (`Very Evil`) and `Fame = 85, Infamy = 0` with a faction evaluates to **`Idolized` (`Ally` disposition, `0.85x` vendor prices)**.

---

## 2. Creation Flow & Verification Stages (`FO4SF_ProgressionQuest.psc`)

- **Creation Flow (`Stage 10` / `RunCreationFlow`):** Applies chosen Background (`1` of `9`), `0..2` Traits, `40`-point S.P.E.C.I.A.L. allocation (or `28`-point when `FO4SF_SpecialPool28 == 1`), and `3` Tag Skills -> computes all `13` Skill `AVIF`s and derived stats (`CarryWeight`, `MaxHP`, `ActionPoints`).
- **Vault Exit Free Trait Respec (`Stage 20`):** Swaps initial Traits (`0..2`) once (`FO4SF_TraitRespecUsed: 0 -> 1`), recomputes skills/derived stats cleanly, and refuses any second respec (`respec_second_refused=true`).
- **`GLOB` Perk Cadence Verification (`Stage 30`):** Evaluates levels `2, 3, 4` under `FO4SF_PerkCadenceLevels = 2` (`grants=[true, false, true]`) and dynamically switches `FO4SF_PerkCadenceLevels = 1` (`grants=[true, true, true]`) with zero rebuild.
- **Decoupled `Karma` + `REPU` Verification (`Stage 40`):** Sets `FO4SF_Karma = -800` (`Very Evil`) while setting `Minutemen` `Fame = 85, Infamy = 0` -> verifies `karma_tier=Very_Evil` **and** `repu_title=Idolized`, `disposition=Ally` simultaneously.
- **Clean Reset (`Stage 50`):** Restores baseline player values and writes `summary ok=true`.

---

## 3. PC Card for Claude (PC)

### Step 1 — Offline Unit Tests, Precheck, Stage, Clean-Core Fold & Verify (UNBLOCKED NOW — Game Closed)
```powershell
$env:FO4SF_DOTNET_TESTS = '1'
python -m unittest tests.test_progression_core
python scripts/guard.py

python scripts/progression/make_progression.py precheck `
  --content-resources "<STARFIELD_DIR>\Tools\ContentResources.zip"

python scripts/progression/make_progression.py stage `
  --out "<STAGE_DIR>\progression-stage" `
  --starfield "<STARFIELD_DIR>\Data\Starfield.esm" `
  --compiler "<STARFIELD_DIR>\Tools\Papyrus Compiler\PapyrusCompiler.exe" `
  --content-resources "<STARFIELD_DIR>\Tools\ContentResources.zip"

python scripts/progression/make_progression.py fold `
  --stage "<STAGE_DIR>\progression-stage" `
  --core-dir "<CLEAN_CORE_DIR>" `
  --out "<STAGE_DIR>\folded-progression" `
  --starfield "<STARFIELD_DIR>\Data\Starfield.esm" `
  --hardlink

python scripts/progression/make_progression.py verify `
  --exp-dir "<STAGE_DIR>\folded-progression" `
  --plan "<STAGE_DIR>\progression-stage\plan.json" `
  --starfield "<STARFIELD_DIR>\Data\Starfield.esm"
```
- **Offline PASS lines:**
  - `Ran ... tests ... OK` and `guard: ok`
  - `precheck: ok`
  - `FO4SFProgression.esm: header Master, masters [Starfield.esm], 21 AVIF, 26 PERK, 7 FLST, 18 GLOB, 6 FACT, 1 QUST; all checks pass`
  - `verify: ok`

### Step 2 — Ride-Along In-Game Verification (**GATED: Run ONLY After Grok Reviews `#806` OR Claude (PC) Says Go**)
1. Confirm Grok has posted a review on PR `#806` or Claude (PC) has explicitly authorized Step 2 on this PR.
2. With Starfield closed, install the ride-along package (`Data/FO4SFProgression.install.json`):
   ```powershell
   python scripts/progression/progression_install.py install --dir "<STAGE_DIR>\progression-stage" --starfield "<STARFIELD_DIR>"
   ```
3. Launch Starfield into a throwaway session (`<XX>` = `FO4SFProgression.esm`'s 2-hex load index) and run stages `10, 20, 30, 40, 50` (`2 s` apart):
   ```text
   setstage <XX>000880 10
   setstage <XX>000880 20
   setstage <XX>000880 30
   setstage <XX>000880 40
   setstage <XX>000880 50
   ```
4. Quit without saving, inspect the log, and uninstall:
   ```powershell
   python scripts/progression/make_progression.py log
   python scripts/progression/progression_install.py uninstall --starfield "<STARFIELD_DIR>"
   ```
- **In-Game PASS lines (`make_progression.py log`, exit code `0`):**
  - `PASS  special_40_and_13_skills_created`
  - `PASS  exit_respec_once_and_locked`
  - `PASS  glob_perk_cadence_dynamic`
  - `PASS  karma_and_repu_independent`
  - `PASS  summary_ok`
  - `verdict: PASS`
