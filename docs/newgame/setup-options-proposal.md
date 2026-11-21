# New-Game Set-Up Options Proposal: Fallout Settings Layer (`S2`)

> **Author:** Gemini (PC)  
> **Status:** **PROPOSAL FOR OWNER DECISION — BUILD NONE OF THE NEW OPTIONS THIS ROUND.**  
> **Scope:** Settings-layer options that a Fallout counterpart to the S.T.A.L.K.E.R. Anomaly / GAMMA pre-world set-up screen ([setup-screen-study.md](setup-screen-study.md)) could expose alongside Mode, Story Line / Faction, and Start Place (`S1`). Every shared cross-plugin state value follows Rule `R13` (owned once in `FO4SFCoreValues.esm`, currently at `next_form_id = 0x000898`, leaving `0x0008A0+` contiguous for approved settings).

---

## 1. Sizing Key (`exists` / `small` / `large`)

- **`exists`:** Already owned and wired in our shipped store (`FO4SFCoreValues.esm`) and slice plugins today; exposing or grouping it on `FO4SF_SetupMenu` requires only a UI row binding.
- **`small`:** Needs `1–2` new mutable `GLOB` records in `FO4SFCoreValues.esm` (`0x0008A0+`) plus a scalar multiplier or conditional check inside an existing Papyrus quest or `GPOF`/`PERK` entry we already build (`0` new plugins, `0` new native hooks).
- **`large`:** Needs world-wide leveled-list/container rewrites, new native SFSE hooks, new weather/disguise subsystems, or an owner scope decision currently on `HOLD`.

---

## 2. Proposed Set-Up Options Matrix

### 2.1 Difficulty of Fights & Combat Lethality

| ID | Option | What It Changes for the Player | Our Records / Store Globals (`R13`) | Exists Today? | Effort | Proposed Default |
|---|---|---|---|---|---|---|
| **OPT-01** | **Campaign Combat Difficulty** (`Easy` / `Normal` / `Hard` / `Very Hard`) | Sets the baseline combat difficulty tier and filters difficulty-gated **Warfare** deployment rows (`min_difficulty..max_difficulty` in `start_places.json`). | `FO4SFCoreValues.esm` `GLOB` `FO4SF_StartDifficulty` (`0x000873`, `0..3`), consumed by `FO4SF_NewGameQuest` and `FO4SFCombat.esm`. | **Yes** | **`exists`** | **`Normal` (`1`)** |
| **OPT-02** | **Outgoing & Incoming Damage Multipliers** (`Story 1.0x/1.0x`, `Scavenger 1.25x/1.5x`, `Lethal 2.0x/2.5x`) | Separates bullet lethality from enemy spongeiness (Anomaly/GAMMA style) so gunfights can be fast and punishing in both directions even on non-Survival runs. | Proposed `FO4SFCoreValues.esm` `GLOB` `FO4SF_DamageOutMult` (`0x0008A0`) & `FO4SF_DamageInMult` (`0x0008A1`), driving a `PERK` `Mod Incoming/Outgoing Weapon Damage` spell on `PlayerRef` in `FO4SFCombat.esm` (aligned with `N3` gunplay decision). | **No** (awaiting `N3` lethality answer) | **`small`** | **`1.0x / 1.0x`** (until `N3` answer lands) |

### 2.2 Survival Needs, Medical & Limb Rules

| ID | Option | What It Changes for the Player | Our Records / Store Globals (`R13`) | Exists Today? | Effort | Proposed Default |
|---|---|---|---|---|---|---|
| **OPT-03** | **Hardcore Survival Mode & Lock** (`Off` / `On` / `Locked On`) | Enables hunger, thirst, sleep deprivation, heal-over-time Stimpaks/RadAway, ammo weight, reduced carry weight, and Doctor's Bag limb-cure requirement; locks Survival on in Warfare when selected at start. | `FO4SFCoreValues.esm` `GLOB` `FO4SF_SurvivalStart` (`0x000871`), `FO4SF_SurvivalLocked` (`0x000872`), `FO4SF_HardcoreEnabled` (`0x000840`), `FO4SF_Hunger`..`FO4SF_SleepDeprivationStage` (`0x000842..0x000847`); `FO4SFHardcore.esm` `GPOF`s (`0x000801..0x000805`) & `FO4SF_HardcoreQuest` (`0x000830`). | **Yes** | **`exists`** | **`Off` (`0`)** (`On` recommended preset for GAMMA-style runs) |
| **OPT-04** | **Needs Drain Rate** (`Relaxed 0.5x` / `Standard 1.0x` / `Harsh 1.5x`) | Scales hourly hunger, thirst, and sleep accumulation rates independently of combat lethality. | Proposed `FO4SFCoreValues.esm` `GLOB` `FO4SF_SurvivalRateMult` (`0x0008A2`), multiplying `FO4SF_HardcoreQuest`'s periodic tick delta (`FO4SFHardcore.esm:0x000830`). | **No** (`1.0x` fixed in `FO4SF_HardcoreQuest`) | **`small`** | **`Standard 1.0x`** (active when Survival is `On`) |
| **OPT-05** | **Weighted Ammunition Outside Survival** (`Off` / `On`) | Applies ballistic/energy/explosive ammo carry weight even if hunger/thirst meters are turned off. | `FO4SFHardcore.esm` `GPOF` `FO4SF_GPOF_AmmoWeight` (`0x000803`) + proposed `FO4SFCoreValues.esm` `GLOB` `FO4SF_SetupAmmoWeight` (`0x0008A3`) decoupling ammo weight from master `FO4SF_HardcoreEnabled`. | **Partial** (`GPOF` exists; coupled to master Survival toggle) | **`small`** | **`Follow Survival`** (`Off` when Survival `Off`, `On` when `On`) |

### 2.3 Economy & Loot Scarcity

| ID | Option | What It Changes for the Player | Our Records / Store Globals (`R13`) | Exists Today? | Effort | Proposed Default |
|---|---|---|---|---|---|---|
| **OPT-06** | **Barter & Contract Economy** (`Abundant` / `Commonwealth Standard` / `Scavenger` / `Famine`) | Tightens vendor buy/sell margins and caps/supply rewards on A-Life jobs and faction bounties so caps, ammo, and chems matter early. | Proposed `FO4SFCoreValues.esm` `GLOB` `FO4SF_EconomyPreset` (`0x0008A8`, `0..3`), scaling `FO4SFReputation.esm`'s vendor price perk (`0x000800+`) and `FO4SFALife.esm`'s job payout multiplier. | **Partial** (reputation buy-multiplier perk exists in `FO4SFReputation.esm`) | **`small`** | **`Commonwealth Standard` (`1`)** |
| **OPT-07** | **World Container Loot Scarcity** (`Full` / `Reduced` / `Picked Clean`) | Reduces ammo, Stimpak, RadAway, and fusion-core drop counts inside exterior/interior containers across the wasteland (GAMMA scavenging loop). | Proposed `FO4SFCoreValues.esm` `GLOB` `FO4SF_LootScarcity` (`0x0008A9`, `0..2`), requiring conditioned `LVLI` chance-none entries across `FO4SFRouteLoot.esm` and converted `CONT` records rather than fixed `CNTO` counts. | **No** (`FO4SFRouteLoot.esm` writes fixed `CNTO` counts today) | **`large`** | **`Full` (`0`)** |

### 2.4 Save Rules

| ID | Option | What It Changes for the Player | Our Records / Store Globals (`R13`) | Exists Today? | Effort | Proposed Default |
|---|---|---|---|---|---|---|
| **OPT-08** | **Save Rule** (`Anywhere` / `Beds & C.A.M.P. Only`) | Restricts manual/quicksave to owned/rented beds or a deployed C.A.M.P. kit (`FO4SFWorkshop.esm`), matching Fallout 4 Survival and Anomaly campfire-save modes. | Proposed `FO4SFCoreValues.esm` `GLOB` `FO4SF_SaveRule` (`0x0008AA`, `0..1`), toggling `InputEnableLayer` save gate / `Game.SetInChargen(false, false, disableSave)` and temporarily releasing on bed/C.A.M.P. sleep events. | **No** | **`small`** | **`Anywhere` (`0`)** (`Beds & C.A.M.P. Only` optional even with Survival `On`) |
| **OPT-09** | **Ironman / Life-Limit Mode** (`Off` / `1 Life` / `3 Lives` / `Respawn Timer`) | Deletes or locks the character's run lineage after the chosen death count (Anomaly Ironman). | Proposed `FO4SFCoreValues.esm` `GLOB` `FO4SF_IronmanLives` (`0x0008AB`), requiring native SFSE save-slot tagging and load-menu filtering so one character's death never touches another save (`R4`). | **No** | **`large`** | **`Off` (`0`)** |

### 2.5 Fast Travel

| ID | Option | What It Changes for the Player | Our Records / Store Globals (`R13`) | Exists Today? | Effort | Proposed Default |
|---|---|---|---|---|---|---|
| **OPT-10** | **Pip-Boy Fast Travel** (`Enabled` / `Disabled`) | Allows or blocks direct point-to-point fast travel from the Pip-Boy Map (`M`) while keeping Starfield's star map blocked. | `FO4SFCoreValues.esm` `GLOB` `FO4SF_HardcoreFastTravelBlocked` (`0x000841`), already read natively by `FO4SFPipboyMenu.dll` (`CheckHardcoreModeFastTravel`) and set by `FO4SFHardcore.esm`. | **Yes** | **`exists`** | **`Enabled` (`0`)** (`Disabled` when Survival is `On`) |
| **OPT-11** | **Fast-Travel Network Rule** (`Any Discovered` / `Linked Settlements & C.A.M.P.s Only` / `None`) | Permits travel between claimed workshops/C.A.M.P.s (`FO4SFWorkshop.esm`) even when wilderness fast travel is disabled. | Proposed `FO4SFCoreValues.esm` `GLOB` `FO4SF_FastTravelRule` (`0x0008A4`, `0..2`), read by `FO4SF_PipboyTravel.psc` (`FO4SFPipboyTravel.esm`) before executing `MoveTo`. | **No** (`FO4SF_PipboyTravel.psc` currently checks discovered status + `0x000841` binary block) | **`small`** | **`Any Discovered` (`0`)** |

### 2.6 Radiation & Environmental Hazards

| ID | Option | What It Changes for the Player | Our Records / Store Globals (`R13`) | Exists Today? | Effort | Proposed Default |
|---|---|---|---|---|---|---|
| **OPT-12** | **Radiation Model & Mutations** (`FO4 Max-HP Penalty` / `Classic Stat Sickness` + `Mutations On/Off`) | Chooses whether rads cap max HP (`FO4`) or apply tiered `END/AGI/STR` debuffs (`FO3/FNV`), and whether high rad exposure can trigger `FO4SFRads.esm` mutations. | `FO4SFCoreValues.esm` `AVIF` `FO4SF_Rads` (`0x000800`), `GLOB` `FO4SF_RadPenaltyMode` (`0x000805`); `FO4SFRads.esm` `GLOB` `FO4SF_MutationsEnabled` (`0x000807`, candidate for promotion to `FO4SFCoreValues.esm` under `R13`). | **Yes** | **`exists`** | **`FO4 Max-HP Penalty` (`0`) + `Mutations On` (`1`)** |
| **OPT-13** | **Radiation Gain Multiplier** (`0.5x` / `1.0x` / `2.0x`) | Scales environmental, water, food, and combat radiation intake rate. | Proposed `FO4SFCoreValues.esm` `GLOB` `FO4SF_RadGainMult` (`0x0008A5`), multiplying `FO4SF_RadsCoreQuest`'s hazard/emitter intake math (`FO4SFRads.esm`). | **No** | **`small`** | **`1.0x`** |
| **OPT-14** | **Dynamic Radstorms** (`Off` / `Rare` / `Frequent`) | Schedules glowing green atmospheric rad-weather sweeps outdoors in exterior wastelands. | Requires custom `WTHR` records overriding planetary climate weather lists + interior shelter detection in `FO4SFRads.esm`. | **No** | **`large`** | **`Off` (`0`)** (until dedicated exterior `WRLD` climate table lands) |

### 2.7 Progression Speed & Character Build Rules

| ID | Option | What It Changes for the Player | Our Records / Store Globals (`R13`) | Exists Today? | Effort | Proposed Default |
|---|---|---|---|---|---|---|
| **OPT-15** | **Starting S.P.E.C.I.A.L. Pool & Perk Cadence** (`Classic/FNV 40 pts, Perk/2 Lvls` vs. `FO4 28 pts, Perk/1 Lvl`) | Switches between classic `40`-point S.P.E.C.I.A.L. + traits + 13 skills and Fallout 4's `28`-point S.P.E.C.I.A.L. + every-level perk cadence. | `FO4SFProgression.esm` `GLOB` `FO4SF_StartingSpecialPool` (`0x000808`, default `40`) & `FO4SF_PerkEveryNLevels` (`0x000809`, default `2`), plus `FO4SFPipboyMenu.ini` `SpecialMaxPoints` (promote to `FO4SFCoreValues.esm` `0x0008A6` so native + Papyrus read one store global). | **Yes** (in `FO4SFProgression.esm`; store promotion is `small`) | **`exists`** | **`Classic/FNV: 40 pts, Perk every 2 levels`** (per owner `D1–D4`) |
| **OPT-16** | **XP & Skill Gain Speed** (`Slow 0.5x` / `Standard 1.0x` / `Fast 1.5x`) | Slows or accelerates XP awards and skill-point/level pacing for long sandbox/Warfare campaigns. | Proposed `FO4SFCoreValues.esm` `GLOB` `FO4SF_XpRateMult` (`0x0008A7`), feeding a player `PERK` `Mod Experience` entry in `FO4SFProgression.esm`. | **No** | **`small`** | **`Standard 1.0x`** |

### 2.8 Warfare Intensity, Squads & A-Life Density

| ID | Option | What It Changes for the Player | Our Records / Store Globals (`R13`) | Exists Today? | Effort | Proposed Default |
|---|---|---|---|---|---|---|
| **OPT-17** | **Companion / Fireteam Cap** (`Lone Wanderer 0` / `Story Duo 2` / `Tactical Squad 4` / `Full Squad 6`) | Caps how many followers/squadmates can travel with the player simultaneously. | `FO4SFCompanions.esm` `GLOB` `FO4SF_SquadBaseCap` (`0x000801`) & `FO4SF_SquadEffectiveCap` (`0x000802`) (already set to `2` in Story and `4` in Warfare via `start_worlds.py`). | **Yes** | **`exists`** | **`Mode Default`** (`2` Story / `4` Warfare) |
| **OPT-18** | **A-Life Patrol & Encounter Frequency** (`Quiet 0.5x` / `Balanced 1.0x` / `Chaotic 2.0x`) | Adjusts `FO4SFALife.esm` background patrol spawn cadence and encounter cooldowns across exterior smart terrains. | Proposed `FO4SFCoreValues.esm` `GLOB` `FO4SF_ALifePopFactor` (`0x0008AC`), scaling `FO4SF_ALifeControllerQuest` tick interval and active squad cap (`FO4SFALife.esm`). | **No** (currently fixed constants on `FO4SF_ALifeControllerQuest`) | **`small`** | **`Balanced 1.0x`** |
| **OPT-19** | **Full Territory Conquest & Outpost Flipping** (`Patrol Skirmishes` / `Active Conquest` / `Total War`) | Enables autonomous faction-vs-faction capture of named Commonwealth/DLC markers, garrison reinforcement waves, and base ownership flips (Anomaly Warfare overhaul). | Proposed `FO4SFCoreValues.esm` `GLOB` `FO4SF_WarfareIntensity` (`0x0008AD`), requiring multi-faction marker ownership tables, reinforcement budgets, and quest-hub protection rules across all 8 faction slots. | **No** (`FO4SFALife.esm` runs smart-terrain patrols + jobs today, not full map-wide territory flipping) | **`large`** | **`Patrol Skirmishes` (`0`)** |

### 2.9 Additional Anomaly / GAMMA Study Candidates

| ID | Option | What It Changes for the Player | Our Records / Store Globals (`R13`) | Exists Today? | Effort | Proposed Default |
|---|---|---|---|---|---|---|
| **OPT-20** | **Starting Loadout Tier (Warfare)** (`Rags & Pipe Pistol` / `Standard Faction Issue` / `Veteran Kit`) | Scales the starting gear granted in `RunWarfareBranch` (`warfare_starts.json`) from pure zero-to-hero scavenging up to full faction kit. | Proposed `FO4SFCoreValues.esm` `GLOB` `FO4SF_StartingLoadoutTier` (`0x0008AE`, `0..2`), selecting sub-loadout arrays in `warfare_starts.json`. | **Partial** (`warfare_starts.json` grants `1` fixed kit per row today) | **`small`** | **`Standard Faction Issue` (`1`)** |
| **OPT-21** | **Companion Mortality** (`Essential Downed` / `Doctor's Bag Revive` / `Permadeath`) | Controls whether downed companions recover after combat, stay downed until healed, or can die permanently in hardcore Warfare runs. | Proposed `FO4SFCoreValues.esm` `GLOB` `FO4SF_CompanionMortality` (`0x0008AF`, `0..2`), driving alias essential/protected flags in `FO4SFCompanions.esm`. | **No** | **`small`** | **`Essential Downed` (`0`)** |
| **OPT-22** | **Faction Armor Disguise System** (`Off` / `On`) | Wearing a faction's uniform temporarily masks player standing until close inspection by guards/officers (FNV + Anomaly disguise mechanic). | Would extend `FO4SFReputation.esm` (`0x000800+`) with armor-keyword polling, suspicion detection cones, and temporary faction-ally swaps. | **No** | **`large`** | **`Off` (`0`)** |
| **OPT-23** | **Weapon & Armor Condition / Jamming** (`Off` / `Degradation + Repair Kits`) | Tracks item wear, receiver jams, and workbench/part maintenance (FO3/FNV + GAMMA core loop). | Currently on explicit **`HOLD`** pending owner answer on `N3` ([gunplay-study.md](../design/gunplay-study.md) Proposal 4: Starfield strips `OBTE` health fields, requiring native SFSE extra-data + UI hooks). | **No (`HOLD` per `N3`)** | **`large`** | **`Off` (`0`)** (awaiting owner `N3` answer) |

---

## 3. Summary Count & Recommended Next Step After Owner Review

- **`exists` (`6` options):** `OPT-01`, `OPT-03`, `OPT-10`, `OPT-12`, `OPT-15`, `OPT-17` — already backed by live records and scripts today (`OPT-01` and `OPT-03` are already on Page 1 of `FO4SF_SetupMenu` in `S1`).
- **`small` (`11` options):** `OPT-02`, `OPT-04`, `OPT-05`, `OPT-06`, `OPT-08`, `OPT-11`, `OPT-13`, `OPT-16`, `OPT-18`, `OPT-20`, `OPT-21` — can be added cleanly as a Page 2 **"SETTINGS / PRESETS"** tab on `FO4SF_SetupScreen.swf` backed by `FO4SFCoreValues.esm` `0x0008A0..0x0008AF` once the owner picks which sliders belong in scope.
- **`large` (`6` options):** `OPT-07`, `OPT-09`, `OPT-14`, `OPT-19`, `OPT-22`, `OPT-23` — each touches broad world records or native engine subsystems and should only be scheduled individually if explicitly chosen by the owner.
