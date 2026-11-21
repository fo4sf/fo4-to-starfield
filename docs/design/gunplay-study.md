# FO4SF Gunplay & Weapon Progression Study (`N3`)

**Author:** Gemini (PC)  
**Branch:** `gemini/gunplay-study` (cut from `main`)  
**Scope:** Design and record-schema study only (`N3`, Rounds 4–5; **HOLD: zero proposals built until owner answers return**). Zero plugins built or modified; zero external mod dependencies; zero copied external mod files, text, or numbers.  
**Evidence Labels:**
- **Verified (schema / repo):** Confirmed directly in `Mutagen.Bethesda.Starfield` and `Mutagen.Bethesda.Fallout4` (`0.55.0-alpha.67`), `docs/measurements/esm_compare.json`, `dotnet/CombatCore/Program.cs`, `sfse/FO4SFCombat/`, `src/fo4sf/combat/tables.py`, or read-only `xEdit` / `SfInspect` probes recorded in `docs/`.
- **Supported hypothesis:** Grounded in Creation Engine lineage, record layouts, or published community tool documentation, awaiting a targeted probe in our test cell.
- **Unverified in-game:** Schema field or native hook exists, but runtime engine execution on Starfield `1.16.244.0` requires an in-game test run by Claude (PC).

---

## Executive Diagnosis: Why Both Base Games Miss the Mark

1. **Why vanilla Starfield gunplay pushes players to melee:**
   - **Compounding sponge math:** Weapons stack invisible, attach-point-less quality tier `OMOD`s (`Calibrated` -> `Refined` -> `Advanced` -> `Superior`) on top of `WEAP` base damage while `LVLN` enemy templates (`LCharSpacer` tiers `1..10`, up to level `94` in `docs/actors/raider-conversion.md`) inflate hit points exponentially and `Automatic` fire-mode `OMOD`s slash per-bullet damage. Shooting an upper-tier enemy with an un-tiered rifle turns firefights into looter-shooter health-bar attrition.
   - **Dead hit locations:** As verified in `docs/combat/combat-core.md`, vanilla `Starfield.esm` `HumanBodyPartData` (`0x003481`), `ModelABodyPartData` (`0x00562C`), and `TerrormorphBodyPartData` (`0x21E736`) still reference unmigrated Fallout 4 `AVIF` FormIDs (`0x00038A..0x00038F`) and set `DamageMult = 1.0` across torso, arms, legs, and feet (`2.0` on head only). Limb hits neither cripple enemies natively nor differentiate anatomy.
   - **Floaty, assisted aiming:** Starfield's `AAMD` (`AimAssistModel`) applies rotational friction and `BulletBendingConeAngleDegrees` even outside heavy controller snap, while `AMDL` (`AimModel`) recoil springs and `WCIM` (`ImageSpaceAdapter`) screen impulses are tuned softly on ballistic firearms, making shots feel weightless.
2. **Why vanilla Fallout 4 gunplay lacks progression and identity:**
   - **Linear receiver bloat instead of gunsmithing:** Almost all `Fallout4.esm` `AMMO` records carry `Damage = 0`; kinetic output sits on `WEAP.BaseDamage` multiplied by a mandatory ladder of receiver `OMOD`s (`Standard` -> `Hardened` -> `Powerful` -> `Calibrated Powerful` -> `Advanced`). Every player upgrades down the exact same numeric track, and a `.308` cartridge changes lethality wildly depending on which receiver name is bolted on.
   - **Flattened manufacture and zero upkeep:** Classic Fallout's industrial lore (*Colt 6520*, *Wattz 2000*, *Winchester P94*, *H&K*, *Gun Runners*) was collapsed into generic silhouettes ("Combat Rifle", "Assault Rifle", "10mm Pistol") with zero weapon condition, zero `Strength` or skill handling gates, and no ammunition subtype choice (`AP` / `JHP` / `+P` / `Slug`).

Our goal is a **grounded, lethal, tactile Fallout gunplay and progression system built 100% as our own** (`FO4SF` C# Mutagen writers, Papyrus quests, and our `FO4SFCombat.dll` SFSE sidecar)—delivering crisp lethality, authentic manufacturer craft, and meaningful bench progression **without Starfield's looter-shooter sponge or S.T.A.L.K.E.R. G.A.M.M.A.'s fifty-part inventory tedium**.

---

## Part (a): How Starfield Governs How a Gun Feels

### Schema Architecture Corrections (`Starfield.esm` & `Mutagen.Bethesda.Starfield` `0.55.0-alpha.67`)

Before examining each mechanic, three record-level facts verified against `Mutagen.Bethesda.Starfield` (`0.55.0-alpha.67`) and `docs/measurements/esm_compare.json` must be pinned explicitly:

1. **Modular `WEAP` Subrecords (`similarity = 0.30` vs FO4):** Starfield split Fallout 4's monolithic `DNAM` + `CRDT` + `WAMD` + `WZMD` layout into dedicated subrecords on `WEAP`: `WGEN` (general/weight/value/speed/O2/barrel), `WAIM` (ADS/aim model/optics/aim assist), `WAM2`/`WAMM` (ammo/capacity/projectile), `WDMG` + `DAMA` (damage/range/crit/damage types), `WFIR` (fire mode/RoF/burst/staged trigger), `WRLO` (reload), `WAUD` + `STCP` (Wwise audio/sound tags), `WMEL` (bash/stagger), `WCHG` (charge), `WVAR` (variable range/aperture), `WVIS` + `WCIM` (1st-person model/impacts/imagespace), `WRUM` (rumble), `QNAM` (power), and `WFLG` (flags). **Verified (schema).**
2. **AimModel is `AMDL` (not `AIM `):** Both `Fallout4.esm` (`51` records) and `Starfield.esm` (`110` records) store Aim Models under the 4-byte record type **`AMDL`**, linked from `WEAP` via subrecord `WAIM` (`Weapon.AimModel`). Starfield adds three companion aiming major records: **`AAMD`** (`AimAssistModel`), **`AAPD`** (`AimAssistPose`), and **`AOPS`** (`AimOpticalSightMarker`), plus **`WBAR`** (`WeaponBarrelModel`). **Verified (schema).**
3. **No `CMSH` or `SNDR` records exist in `Starfield.esm`:** `CMSH` (`0` occurrences in `RecordTypes`) is not a Starfield record; screen shake and camera impulse are split across **`IMAD`** (`ImageSpaceAdapter`, serialized via `REFL` reflection data and linked on `WEAP.WCIM`), **`WEAP.WRUM`**, **`CAMS`/`CPTH`** camera springs, **`FORC`** (`ForceData`), and `.af`/`.afx` camera bone tracks. Likewise, FO4's `SNDR` (`SoundDescriptor`) was removed (`0` records) and replaced by Audiokinetic Wwise **`WWED`** (`WwiseEventData`), inline `SoundReference` GUIDs on `WEAP.WAUD`, **`STCP`** (`SoundTagComponent` -> `STAG`), **`KSSM`** (`SoundKeywordMapping`), and **`WKMF`** (`WwiseKeywordMapping`). **Verified (schema).**

---

### (a.1) Recoil & Recoil Recovery

- **`AMDL` (`AimModel`):** Primary engine record governing angular camera/muzzle climb per shot and spring return.
  - `RecoilDegreesPerShotX`, `RecoilDegreesPerShotY`: Starfield replaced FO4's scalar min/max kick with explicit horizontal (`X`) and vertical (`Y`) angular impulse per shot. **Verified (schema).**
  - `RecoilDiminishSpringForce`: Angular spring restoration velocity pulling the sight picture back toward pre-shot pitch/yaw after firing. **Verified (schema); exact curve formula unverified in-game.**
  - `RecoilDiminishSightsMult`: Multiplier on `RecoilDiminishSpringForce` while aiming down sights (`GetInIronSights == 1`). **Verified (schema).**
  - `RecoilHipMult`: Multiplier on per-shot recoil kick while firing from the hip. **Verified (schema).**
  - `RecoilShotsForRunaway`: Consecutive shots before recoil breaks past damped recovery into runaway climb. **Verified (schema).**
  - `RecoilArc`, `RecoilArcRotate`: Angular fan width (`degrees`) and bias angle (`degrees`, e.g., up-and-right climb for right-handed stamped rifles). **Verified (schema).**
  - `RecoilBaseStability`: Baseline stability scalar shared between recoil damping and sighted sway. **Verified (schema).**
- **`WEAP` (`WAIM` subrecord):** `Weapon.AimModel` (`IFormLinkNullableGetter<IAimModelGetter>`) binds the base `AMDL`. **Verified (schema).**
- **`OMOD` (`WeaponModification`, `Weapon.Property` enum):** Attachments override or `MultAndAdd` recoil via `AimModelTemplate` (`41`), `AimModelBaseStability` (`40`), `AimModelRecoilDiminishSpringForce` (`48`), `AimModelRecoilDiminishSightsMult` (`49`), `AimModelRecoilMaxDegreePerShot` (`50`), `AimModelRecoilMultiplierHipFire` (`51`), and `AimModelRecoilArcRotateDegrees` (`52`). **Verified (schema).**
- **`PERK` (`APerkEntryPointEffect.EntryType`) & `Condition`:** Entry point `[203] ModPlayerZeroGWeaponRecoilScale` scales microgravity recoil/pushback; condition function `[380] IsRecoiling` tests active recoil state. Notice Starfield has **no** general terrestrial `ModWeaponRecoil` perk entry point—on-planet recoil scaling must go through `AMDL`/`OMOD` or native code. **Verified (schema).**
- **First-person `.af` / `.afx` clips & `GMST`:** Visual weapon kickback in first person is driven by the weapon subgraph's fire `.af` bone translation/rotation alongside `AMDL` camera pitch; global `fGun*` / `fCombat*` `GMST` scalars remain **unverified in-game** until dumped via `SfInspect`.

### (a.2) Spread & Aim Wobble (Cone of Fire)

- **`AMDL` (`AimModel`):**
  - `ConeOfFireDegreesX`, `ConeOfFireDegreesY`: Anisotropic horizontal/vertical dispersion cone in degrees (replacing FO4's isotropic `ConeOfFireMinAngle`/`ConeOfFireMaxAngle`). **Verified (schema); whether `X`/`Y` act as min/max or horizontal/vertical axes at runtime requires in-game check.**
  - `ConeOfFireIncreasePerShot`: Bloom added (degrees) per round discharged. **Verified (schema).**
  - `ConeOfFireIncreasePerSec`: Continuous bloom rate while moving or sustaining fire (`OMOD` names the paired recovery `AimModelConeDecreasePerSec` `45`). **Verified (schema).**
  - `ConeOfFireDecreaseDelaySeconds`: Delay in **seconds** after a shot before bloom begins shrinking (critical unit change: FO4 stored milliseconds!). **Verified (schema).**
  - `ConeOfFireSneakMult`, `ConeOfFireIronSightsMult`: Multipliers applied when sneaking (`IsSneaking`) or aiming (`GetInIronSights`). **Verified (schema).**
  - `ConeOfFireIgnoresMovement`: New CE2 boolean preventing locomotion speed from widening hipfire/sighted spread on stabilized weapons. **Verified (schema).**
- **`WEAP` (`WAIM`, `WAM2`, `WVAR`):**
  - `WAIM.AccuracyBonus`, `WAIM.ReticleType` (crosshair style). **Verified (schema).**
  - `WAM2.ProjectilesCount`: Multi-pellet count (shotguns, splitters). **Verified (schema).**
  - `WVAR` (`UseVariableRange`, `ApertureValueMin..Max`, `DistanceValueMin..Max`, `ApertureAcceleration`/`Deceleration`): Dynamic choke/spread-vs-distance system new in CE2. **Verified (schema); runtime behavior unverified in-game.**
- **`PROJ` (`Projectile`):** `ConeSpread` adds intrinsic sub-munition/pellet dispersion; `Projectile.Flag.DisableCombatAimCorrection` disables engine aim-correction toward target center. **Verified (schema).**
- **`OMOD` (`Weapon.Property`):** `AimModelConeMinDegrees` (`42`), `AimModelConeMaxDegrees` (`43`), `AimModelConeIncreasePerShot` (`44`), `AimModelConeDecreasePerSec` (`45`), `AimModelConeDecreaseDelayPerSec` (`46`), `AimModelConeIronSightsMultiplier` (`47`), `AccuracyBonus` (`39`), `ProjectileCount` (`82`). **Verified (schema).**
- **`PERK` (`EntryType`) & `CSTY` (`CombatStyle`):** Perk entry point **`[134] ModConeoffireMult`** dynamically multiplies the player's live cone of fire against any `CTDA` condition (`IsSneaking`, `GetMovementSpeed`, limb condition AVs, skill AVs) with zero script polling! NPC spread is scaled by `CSTY` subrecord `CSRA` (`RangedAccuracyMult`). **Verified (schema).**

### (a.3) Sway, Breath-Holding & Aim Assist Magnetism

- **Idle & Sighted Sway (`AMDL` + `PERK`):**
  - `AMDL.RecoilBaseStability` (and `OMOD` `AimModelBaseStability` `40`) sets the weapon's intrinsic figure-eight sight drift amplitude. **Verified (schema).**
  - `PERK` entry points **`[102] ModActorScopeStability`**, **`[0] ModBreathTimer`**, and **`[142] ModScopeHoldBreathOxygenDrainMult`** govern scope drift and breath-steadying (`Condition` `[588] IsPlayerSteadyingWeapon`, `[381] HasScopeWeaponEquipped`, `[440] GetInIronSights`), draining Starfield's `Oxygen` stamina pool while steadying. **Verified (schema); whether `[102]` affects non-scoped iron sights is unverified in-game.**
- **Limb-Condition Sway (`AVIF` + `BPTD`):**
  - `Starfield.esm` retains `PerceptionCondition` (`0x00036C`), `LeftAttackCondition` (`0x00036E`), and `RightAttackCondition` (`0x00036F`), and `FO4SFCombat.esm` adds `FO4SF_AimSwayPenalty` (`AVIF 0x80A`, `+35` one crippled arm, `+65` both arms, `+20` crippled head). Because vanilla `HumanBodyPartData` had broken `AVIF` links, whether CE2's camera still reads `0x00036E`/`0x00036F` directly for arm-cripple sway is **unverified in-game**, whereas binding `FO4SF_AimSwayPenalty` (`0x80A`) to `PERK` `[102]` / `[134]` is deterministic in data. **Verified (repo, `docs/combat/combat-core.md`).**
- **Aim Assist & Bullet Bending (`AAMD` `AimAssistModel` + `AAPD` `AimAssistPose`):**
  - Linked via `WEAP.WAIM.AimAssistTemplate` (and `OMOD` `Weapon.Property` indices `0..22`).
  - Contains `InnerConeAngleDegrees`, `OuterConeAngleDegrees`, `SteeringDegreesPerSec`, `Friction`, `AdsSnapSteeringMult`, `AdsSnapSeconds`, **`BulletBendingConeAngleDegrees`**, and `AimAssistEnabled`. **Verified (schema).**
  - *Why this matters for feel:* `BulletBendingConeAngleDegrees` steers trajectories inside an angular cone toward `AAPD` skeleton bones (`StartBoneName`, `EndBoneName`, `Radius`, `Weight`), making shots feel "magnetic" rather than crisp ballistic ray/projectile casts. Zeroing `BulletBendingConeAngleDegrees` on our `AAMD` templates is a high-leverage feel win. **Supported hypothesis; requires in-game A/B check.**

### (a.4) Aim-Down-Sights (ADS) Time, Optics & Cover Clearance

- **`WEAP` (`WAIM` subrecord):**
  - `SightedTransitionSeconds`: Blend duration from hipfire pose into sighted pose (modified by `OMOD` `Weapon.Property.SightedTransitionSeconds` `88`). **Verified (schema).**
  - `AimDownSightTemplate` (`FormLink<IZoomGetter>`), `HasScope`, `AimOpticalSightModel` (`FormLink<IAimOpticalSightMarkerGetter>`). **Verified (schema).**
- **`ZOOM` (`Zoom`, `118` in `Starfield.esm`):**
  - `FovMult`, `Overlay` (`Zoom.OverlayType`: `19` reticle types), `CameraOffset` (`ZOFX`/`ZOFY`/`ZOFZ`), `ImagespaceModifier` (`ZIMG`), plus five CE2-only staged ADS fields: `AdsDistanceFromCameraOffset`, `AdsHeightDelayEnabled`, `AdsHeightDelaySeconds`, `AdsDepthEnabled`, and `AdsDepthDelaySeconds` (controlling the two-stage "bring rifle to cheek, then push eye into optic" motion). **Verified (schema); exact visual curve unverified in-game.**
- **`AOPS` (`AimOpticalSightMarker`, Starfield-only):**
  - Controls reflex/holo dot and laser sight behavior (`ActivateSightOnSightedMode`, `OpticalSightAttachNode`, `DelayBeforeSightActivation`, `DelayBeforeSightDeactivation`, `FocalPointDistanceDuringAiming`, `SightControlsFiringDirection`). **Verified (schema).**
- **`WBAR` (`WeaponBarrelModel`, Starfield-only, linked via `WEAP.WGEN.WeaponBarrel`):**
  - Governs barrel collision against cover and ADS cover-peek speed: `AllowCoverState`, `CoverDetectionDistance`, `EnterCoverAnimationTimeSeconds`, `HipfireDuringCoverAnimationTimeSeconds`. **Verified (schema); in-game feel unverified.**
- **`PERK` (`EntryType`):** `[167] ModMagazineDrawSpeed` (draw/ready speed), `[159] IronSightsActivate`, and **`[221] ApplyAimDownSightSpell`** (new CE2 perk hook that casts a `SPEL` whenever the actor enters ADS, enabling zero-polling ADS effects!). **Verified (schema).**

### (a.5) Hit Reactions, Limb Cripple, Dismemberment & Stagger

- **Stagger (`WEAP`, `OMOD`, `PROJ`, `EXPL`, `FORC`, `MGEF`, `PERK`):**
  - `WEAP.WMEL.MeleeStagger` (`Stagger` enum: `None`, `Small`, `Medium`, `Large`, `ExtraLarge`) and `OMOD` `Weapon.Property.Stagger` (`58`). **Verified (schema).**
  - `PROJ.ImpactForce` (Havok impulse on rigidbodies/ragdolls) + `Projectile.Flag.PinsLimbs` + `EXPL.Stagger` / `EXPL.Force` + `FORC` (`ForceData`, CE2 `REFL`). **Verified (schema).**
  - `MGEF` Archetype `Stagger` (applied via `WEAP.WDMG.CriticalHitSpell` or `PERK` `[51] ApplyCombatHitSpell` / `[213] ApplyCombatHitSpellAttacker`), scaled by `PERK` `[33] ModIncomingStagger` and `[34] ModTargetStagger`, and readable via `Condition` `[379] IsStaggered`, `[441] GetActorStaggerDirection`, `[442] GetActorStaggerMagnitude`. **Verified (schema).**
- **Locational Hit Reactions & Limb Cripple (`BPTD` + `AVIF`):**
  - `BodyPart` (`BPD2` in `BPTD`) carries `DamageMult`, `HealthPercent`, `ActorValue`, `ToHitChance`, `HitReactionStart`, `HitReactionEnd`, `TwistVariablePrefix` (procedural bone flinch on bullet impact), and `OnCripple*` debris/explosion/impact links. **Verified (schema).**
  - **Repo Finding (`docs/combat/combat-core.md`):** Vanilla `Starfield.esm` left stale FO4 FormIDs (`0x00038A..0x00038F`) in `BPTD` `ActorValue` fields and `1.0x` multipliers on non-head parts. `FO4SFCombat.esm` (`dotnet/CombatCore/Program.cs`) clones `FO4SF_CombatHumanBptd` (`0x840`), `FO4SF_CombatRobotBptd` (`0x841`), and `FO4SF_CombatCreatureBptd` (`0x842`) onto live `Starfield.esm` `AVIF`s `0x00036C..0x000372` (`PerceptionCondition`..`BrainCondition`). Whether CE2 natively plays cripple animations or fires `OnCripple` once repaired is **unverified in-game** (`FO4SF_CombatQuest.psc` currently enforces `SpeedMult` `-40`/`-60`, right-arm weapon drop, and `FO4SF_AimSwayPenalty` in script).
- **Dismemberment & Gore (`WEAP.HitBehavior` vs `BPTD`):**
  - `WEAP.WDMG.HitBehavior` retains enum `NormalFormula`, `DismemberOnly`, `ExplodeOnly`, `NoDismemberOrExplode`, and `PERK` retains `[143] SetForceDecapitate` and `[146] SetCanExplodePants`, **but `Starfield.esm` `BPTD` stripped all FO4 severable/explodable geometry fields** (`CutMin`/`Max`/`Radius`, `LimbReplacementModel`, `MeatCapTextureSet`) and `Actor.psc` lacks `Dismember` / `IsDismembered` (`126` FO4 call sites). Per Owner Decision `FS-6` (`docs/research/framework/engine-mechanics.md`), dismemberment requires our own SFSE native implementation. **Verified (schema & repo).**

### (a.6) Damage, Armor Mitigation & Health Scaling

- **`WEAP` (`WDMG`, `DAMA`, `WFIR`, `WCHG`):**
  - `WDMG`: `AttackDamage` (physical base), `MinRange`, `MaxRange`, `OutOfRangeDamageMult` (distance falloff floor), `CritDamageMult`, `CritChanceIncMult` (non-VATS critical chance scalar), `CriticalHitSpell`, `CritEffectOnDeathOnly`, `Resistance` (`AVIF`), `Skill` (`AVIF`). **Verified (schema).**
  - `DAMA` (`DamageTypes`): Array of `WeaponDamageType` `{DamageType (DMGT), Value, CurveTable (CURV)}` supporting typed channels (Energy, EM, Thermal, Radiation) scaled by `CURV` tables. **Verified (schema).**
  - `WFIR`: `FiringType` (`SingleOrBinary`, `Burst`, `Automatic`), `BurstCount`, `BurstDelaySeconds`, `ShotsPerSecond`, `OverrideRateOfFire`, `AttackSeconds`, `FireSeconds`, `BoltChargeSeconds`, `BoltAction`, `HasStagedTrigger`, `HasDualTrigger`. **Verified (schema).**
  - `WCHG`: `ChargingAttack`, `ChargeHoldInput`, `ChargeFullPowerSeconds`, `ChargeMinPowerPerShot` (Gauss / laser musket / plasma charge mechanics). **Verified (schema).**
- **Stacking Quality Tier `OMOD`s & `LGDI`:**
  - Starfield's `Quality_##` `OMOD`s attach with **no `AttachPoint`** (`Quality_TiersAny` up to `Superior`/`Exceptional`), stacking multiplicative `DamagePhysical` (`70`) and `DamageTypeValue` (`71`) bonuses onto high-level drops, while `LGDI` (`LegendaryItem`, `84` records) rolls multi-slot legendary `OMOD`s. **Verified (schema & `workshop-items-economy.md`).**
- **Armor Resistance, Actor Scaling & Difficulty (`DMGT`, `CURV`, `NPC_`, `LCTN`, `GMST`, `GPOF`):**
  - `DMGT` (`11` in `Starfield.esm`) pairs each damage type with a `ResistanceActorValue` (`AVIF`) evaluated through Starfield's power-law resistance curve (`CURV` + `GMST`s).
  - `NPC_` health scales across `LVLN` tiers (`EncSpacer01Template`..`EncSpacer10`) and `LCTN` `Encounter Leveling Data` (`MinLevel`, `MaxLevel`, `Match PC Level`), compounded by `GMST` `fDiffMultHPByPC*` / `fDiffMultHPToPC*` and `GPOF` (`GameplayOptions`) damage sliders. **Verified (schema & `companions-ai-factions-combat.md`).**

### (a.7) Ammunition

- **`AMMO` (`Ammunition`, `150` in `Starfield.esm`):**
  - Fields: `Projectile` (`FormLink<IProjectileGetter>`), **`Damage` (`float`)**, **`Health` (`uint32`)**, `Weight` (`float`, kg), `Value` (`uint32`), `Flags` (`IgnoresNormalWeaponResistance`, `NonPlayable`, `HasCountBased3d`), `ShortName`, `CasingModel`, `PickupSound`, `DropdownSound`, `Keywords`. **Verified (schema).**
  - **Key Finding:** `AMMO.Damage` is present in `Mutagen.Bethesda.Starfield`! Whether Starfield's native damage calculator adds `AMMO.Damage` directly onto `WEAP.AttackDamage` for all ballistic weapons is **unverified in-game** and should be tested in one probe; meanwhile, `AMMO` has **no `AMEF`** (`AmmoEffect` was never ported from FNV; `0` records in `Starfield.esm`).
- **`WEAP` (`WAM2` subrecord):**
  - `AmmoType` (`FormLink<IAmmunitionGetter>`), `AmmoCapacity`, **`AmmoList` (`FormLink<IFormListGetter>`)**, `OverrideProjectile`, `OverrideShellCasing`, `ProjectilesCount`, `NpcsUseAmmo` (`False` on vanilla `Coachman` `0x026D96B`; `74` of `84` weapon-bearing vanilla `NPC_` carry no `AMMO`, `docs/actors/raider-conversion.md`). **Verified (schema & repo).**
  - Whether `WEAP.WAM2.AmmoList` (`OMOD` `Weapon.Property.AmmoList` `23`) supports native multi-ammo chambering in CE2 is **unverified in-game**. Our `FO4SFCombat.esm` (`dotnet/CombatCore/Program.cs`) already bypasses per-weapon edits by reading `Weapon.GetAmmo()` and indexing parallel `FLST`s (`0x82C..0x82F`) across `15` New Vegas subtypes. **Verified (repo).**
- **`PKIN` (`PackIn`, `11,281` in `Starfield.esm`):** Groups placed world references (e.g., open ammo cases with loose magazines/cartridges for environmental storytelling) and carries no ballistic parameters. **Verified (schema).**

### (a.8) Weapon Condition & Degradation: Active vs Vestigial Audit

A complete scan of `Mutagen.Bethesda.Starfield` (`0.55.0-alpha.67`) and `docs/measurements/esm_compare.json` establishes the exact state of item condition in CE2:

1. **Removed from `WEAP` (Verified, schema):**
   - `WEAP` has **no `Health` / `MaxCondition` / `DamageToWeaponMult` field** anywhere in `WGEN`, `WDMG`, or `WFIR`.
   - `DEST` / `DSTD` / `DSTF` (`Destructible` world-object health stages, present on FO4 `WEAP`) are **FO4-only on `WEAP`** and stripped in Starfield (`esm_compare.json` lines `1360-1363`).
   - FO4's vestigial `Weapon.Flag.NoJamAfterReload` was **removed** when weapon flags moved to `WFLG`.
2. **Vestigial Condition Plumbing Still Present in Starfield Schema (Verified, schema; runtime effect unverified in-game):**
   - **`ExtraData.ItemCondition` (`COED` subrecord):** Container (`CNTO`) and leveled-list (`LVLO`) entries still serialize `ItemCondition` (`float`) beside `Owner`.
   - **`PlacedObject.HealthPercent` (`XHLT` subrecord):** Placed world `REFR` records still carry a `HealthPercent` float.
   - **`Condition` Function `[398] GetItemHealthPercent`:** Remains in Starfield's `CTDA` function enum at index `398`.
   - **`Ammunition.Health` + `PERK` `[125] ModAmmoHealthMult` & `[118] ModIncomingBatteryDamage`:** Survives from FO4's Fusion Core charge mechanic (`AMMO` health pool drained as battery charge).
   - **`ConstructibleObject.RepairComponents` (`COBJ.REPR`) + `PERK` `[175] ModWorkshopRepairCost`:** Active for repairing damaged **outpost workshop objects**, not equipped weapons.
3. **Engineering Conclusion:** Starfield has **no active native weapon degradation, jam state, or weapon-repair bench loop**, and relying on vestigial `COED.ItemCondition` on player inventory instances is **unverified in-game** (and lacks save/UI guarantees). Any FO4SF weapon condition system should store state in our own `AVIF` / `GLOB` / Papyrus table (`R13`, since SFSE co-saves are disabled since `0.2.12`) and apply gameplay effects through verified `PERK` entry points (`[134]`, `[166]`) or `FO4SFCombat.dll`.

### (a.9) Sound & Acoustic Stealth

- **`WEAP` (`WAUD` subrecord + `STCP` `SoundTagComponent`):**
  - `WAUD` holds `SoundReference` structs (`Start` Wwise GUID, `Stop` Wwise GUID, `Condition` `CNDF`, `EventMapping` `WWED`) for `MeleeOrCreature`, `PrimedExplosive`, `DryFire`, `Idle`, `Equip`, `Unequip`, `FastEquip`, plus **`SoundLevel`** (`Loud`, `Normal`, `Silent`, `VeryLoud`, `Quiet`). **Verified (schema).**
  - Primary gunshot, mechanical action, reload, and exterior tail events bind through `STCP` (`SoundTagComponent.AnimationSound` -> `STAG` `AnimationSoundTagSet`) and `KSSM` (`SoundKeywordMapping`: `WED0`, `Keywords`, `RSMC`/`RSMH` items; e.g., swapping to suppressed audio when a suppressor `OMOD` adds a muzzle keyword!). **Verified (schema).**
- **`WWED` (`WwiseEventData`, `489` records), `WKMF` (`WwiseKeywordMapping`, `79` records), `SOUN` (`SoundMarker`):** Resolve Wwise event GUIDs against `.bnk` soundbanks and `.wem` streams (`Wwise 2021.1.14.8108`). **Verified (`radio-music-sound.md`).**
- **Propagation, Environment & AI Detection (`ASPC`, `REVB`, `WTHR`, `GMST`, `OMOD`):**
  - `OMOD` modifies audibility via `Weapon.Property.SoundLevel` (`89`) and `SoundLevelMult` (`124`), feeding AI stealth detection (`GMST` `iSoundLevelQuiet`, `iSoundLevelNormal`, `fSneakSoundLosMult`).
  - `ASPC` (`AcousticSpace`) + `REVB` (`RABG` Wwise aux bus GUID) switch indoor/outdoor gunshot tails (`WED0`/`WED1`), while `WTHR` (`Weather`) carries ambient wind/rain/thunder sound references. **Verified (schema).**
  - **Hard Constraint (`animation-audio-physics.md` `H2`):** Adding *new* Wwise `.bnk` events has no public CK recipe yet; until solved, converted weapons must either reuse matching vanilla Starfield `STAG`/`KSSM`/`WWED` GUIDs or play external audio via an SFSE sidecar.

### (a.10) Camera Shake, Screen Impulse & Controller Rumble

- **`IMAD` (`ImageSpaceAdapter`) on `WEAP`, `ZOOM`, `OMOD`, and `EXPL`:**
  - `WEAP.ImageSpaceAdapter` (`WCIM` subrecord) triggers a per-shot `IMAD` (radial blur, FOV micro-punch, HDR bloom flash); `ZOOM.ImagespaceModifier` (`ZIMG`) and `OMOD` `ADSImageSpaceModifier` (`126`) override it in ADS; `EXPL` (`ImageSpaceModifier` + `ISRadius`) drives blast shockwaves. Note that Starfield serializes `IMAD` via `REFL` reflection blobs rather than FO4's fixed subrecords. **Verified (schema).**
- **`WEAP.WRUM`:** Per-weapon controller motor rumble subrecord. **Verified (schema).**
- **First-person `.af` / `.afx` Camera Bone & `CAMS` / `CPTH` / `FORC`:**
  - `HumanBodyPartData` (`0x003481`) includes a non-targetable `Camera` node driven by first-person fire/reload `.af` clips and `.afx` event annotations; `CAMS` (`CameraShot`, `272` records: `LocationSpring`, `TargetSpring`, `RotationOffset`, `ImageSpaceModifier`) and `FORC` (`ForceData`, `REFL`) handle cinematic and physics camera impulses. **Verified (schema & `combat-core.md`).**

### Summary Table — Starfield Gunplay Levers & Verification State

| Feel Dimension | Primary Starfield Records & Subrecords | Key Mutagen `0.55.0-alpha.67` Fields / Perk Entry Points | Verification Status |
|---|---|---|---|
| **Recoil & Recovery** | `AMDL`, `WEAP` (`WAIM`), `OMOD`, `PERK` | `RecoilDegreesPerShotX/Y`, `RecoilDiminishSpringForce`, `RecoilDiminishSightsMult`, `RecoilHipMult`, `RecoilShotsForRunaway`, `RecoilArc`, `RecoilArcRotate`; `EntryType.ModPlayerZeroGWeaponRecoilScale` (`203`) | Schema **verified**; spring formula **unverified in-game** |
| **Spread & Wobble** | `AMDL`, `WEAP` (`WAIM`, `WAM2`, `WVAR`), `PROJ`, `OMOD`, `PERK`, `CSTY` | `ConeOfFireDegreesX/Y`, `ConeOfFireIncreasePerShot`, `ConeOfFireDecreaseDelaySeconds`, `ConeOfFireIronSightsMult`, `ConeOfFireIgnoresMovement`, `PROJ.ConeSpread`; `EntryType.ModConeoffireMult` (`134`) | Schema **verified**; `X/Y` vs min/max semantics **unverified in-game** |
| **Sway & Magnetism** | `AMDL`, `PERK`, `AVIF`, `AAMD`, `AAPD` | `RecoilBaseStability`, `EntryType.ModActorScopeStability` (`102`), `ModBreathTimer` (`0`), `ModScopeHoldBreathOxygenDrainMult` (`142`); `AAMD.BulletBendingConeAngleDegrees`, `Friction` | Schema **verified**; zeroing `AAMD` bullet-bending **needs PC test** |
| **ADS Time & Cover** | `WEAP` (`WAIM`, `WGEN`), `ZOOM`, `AOPS`, `WBAR`, `OMOD`, `PERK` | `SightedTransitionSeconds`, `ZOOM.AdsHeightDelaySeconds`, `AdsDepthDelaySeconds`, `WBAR.CoverDetectionDistance`, `EnterCoverAnimationTimeSeconds`; `EntryType.ModMagazineDrawSpeed` (`167`), `ApplyAimDownSightSpell` (`221`) | Schema **verified**; `ZOOM` delay & `WBAR` feel **unverified in-game** |
| **Hit Reactions & Stagger** | `BPTD`, `AVIF`, `WEAP` (`WMEL`, `WDMG`), `PROJ`, `FORC`, `MGEF`, `PERK` | `BodyPart.DamageMult`, `ActorValue` (`0x00036C..0x000372`), `TwistVariablePrefix`, `MeleeStagger`, `OMOD` `Stagger` (`58`), `PROJ.ImpactForce`, `EntryType.ModTargetStagger` (`34`), `ApplyCombatHitSpell` (`51`) | Stale vanilla `BPTD` bug & `0x840..0x842` fix **verified**; native cripple anims **unverified in-game**; dismemberment needs SFSE |
| **Damage & Scaling** | `WEAP` (`WDMG`, `DAMA`, `WFIR`), `OMOD`, `DMGT`, `CURV`, `NPC_`, `LCTN`, `GMST`, `GPOF` | `AttackDamage`, `DamageTypes` (`CurveTable`), `FiringType`, `OutOfRangeDamageMult`, `CritDamageMult`, `CritChanceIncMult`, `Quality_##` `OMOD`s, `fDiffMultHP*` | Schema & `LCharSpacer` tiers **verified** |
| **Ammunition** | `AMMO`, `WEAP` (`WAM2`), `FLST`, `COBJ` (`PKIN` prefabs only) | `AMMO.Projectile`, `AMMO.Damage`, `AMMO.Health`, `IgnoresNormalWeaponResistance`, `WAM2.AmmoType`, `WAM2.AmmoList`, `NpcsUseAmmo` | `FO4SFCombat.esm` `Weapon.GetAmmo()` + `FLST` subtypes **verified**; native `AMMO.Damage` & `WAM2.AmmoList` **unverified in-game** |
| **Weapon Condition** | Absent on `WEAP`; vestigial on `COED`, `REFR` (`XHLT`), `AMMO`, `CTDA` (`398`) | `ExtraData.ItemCondition`, `PlacedObject.HealthPercent`, `Ammunition.Health`, `GetItemHealthPercent` (`398`); `COBJ.RepairComponents` (outpost only) | Schema **verified** (`WEAP` has no CND/jam fields); `COED` runtime effect **unverified in-game** |
| **Sound** | `WEAP` (`WAUD`, `STCP`), `KSSM`, `STAG`, `WWED`, `WKMF`, `ASPC`, `REVB`, `WTHR` | `WAUD` `SoundReference`s, `SoundLevel` enum, `STCP.AnimationSound`, `KSSM` keyword audio swaps | Schema & Wwise `.bnk` limit (`H2`) **verified** |
| **Camera Shake** | `IMAD` (`REFL`), `WEAP` (`WCIM`, `WRUM`), `ZOOM` (`ZIMG`), `CAMS`/`CPTH`, `FORC`, `EXPL` | `WEAP.ImageSpaceAdapter`, `WRUM`, `ZOOM.ImagespaceModifier`, `CAMS.LocationSpring`/`TargetSpring`, `.af` `Camera` bone | Schema **verified** (`CMSH` absent in Starfield) |

---

## Part (b): How `FO4`, `FO3`, `FNV`, and `FO76` Handle the Same Mechanics — and What Converts Automatically

### Cross-Title Mechanical Comparison (`FO3`, `FNV`, `FO4`, `FO76`, `Starfield`)

Counts and rules below are **verified** from `docs/combat/combat-core.md`, `src/fo4sf/combat/tables.py`, `docs/research/framework/findings/multi-game-scope.md`, and `Mutagen.Bethesda.Fallout4` (`0.55.0-alpha.67`):

| Mechanic | Fallout 3 (`FO3`) | Fallout: New Vegas (`FNV`) | Fallout 4 (`FO4`) | Fallout 76 (`FO76` — mechanical reference only) | Starfield (`CE2` Host) |
|---|---|---|---|---|---|
| **Weapon Record & Aiming** | `WEAP` (`160`): `DATA` + `DNAM` (`Spread`, `MinSpread`, `SightFOV`, `SightUsage`). No `AMDL`; camera FOV zoom instead of true iron sights. | `WEAP` (`261`): `DATA` + `DNAM` (`MinSpread`, `Drift` sway, iron-sight anim flags, `SkillRequirement`, `StrengthRequirement` penalized via `fWeapStrengthReqPenalty`). | `WEAP` (`252`) + `AMDL` (`51`) + `ZOOM` (`16`): isotropic `ConeOfFireMin/MaxAngle`, ms delay, scalar `RecoilMin/MaxPerShot`, `SightedTransitionSeconds` in `DNAM`. | `WEAP` + `AMDL` + `ZOOM` + `CURV`: inherits FO4 `AMDL` recoil/cone model with real-time VATS (`1.0x` time scale). | Modular `WEAP` (`406`) + `AMDL` (`110`, X/Y degrees, sec delay) + `ZOOM` (`118`, staged delays) + `AAMD` + `AOPS` + `WBAR`. |
| **Armor & Damage Math** | Pure percentage `DR` (`max_dr_cap_pct = 85%`, `0.05` floor); random crits (`CritDamage`, `CritMult`) on every shot. | **`DR`-then-`DT`** (`max_dr = 85%`, flat `Damage Threshold` subtraction, `20%` `fMinDamMultiplier` floor); random crits + VATS bonus. | **Power-law `DR`** (`Damage / Resistance` ratio curve, `0.15` floor) across typed `DMGT` (`8`); **crits banked in VATS only** (`CRDT`). | Power-law `DR` + leveled `CURV` weapon brackets (`Lvl 1..50`, obsolescing low-level drops). | Power-law `DR` across `DMGT` (`11`) + `CURV` tables + `Quality_##` tier `OMOD`s; restores non-VATS `CritChanceIncMult`. |
| **Ammunition & Reloading** | `AMMO` (`30`): base cartridge link only; `0` `AMEF`, `0` `RCPE`. | `AMMO` (`92`) + **`AMEF` (`54` Ammo Effects)** + **`RCPE` (`105` recipes)**: `AP` (`-DT`), `JHP` (`+Dmg, xDT`), `+P` (`+Dmg, -DT, +Wear`), `Slug`, `Flechette`, `Match`, `Overcharge` / `Max Charge`. | `AMMO` (`57`, `Damage = 0` on nearly all rounds); `0` `AMEF`; calibre swaps only via receiver `OMOD`s; ammo weight in Survival only. | `AMMO` + crafting benches + endgame `Prime` receivers chambering `Ultracite` ammo. | `AMMO` (`150`, has `Damage` & `Health`, `0` `AMEF`) + `WAM2.AmmoList`; `FO4SFCombat.esm` adds `15` FNV calibre subtypes & `COBJ` bench recipes. |
| **Condition (`CND`) & Jamming** | Active `WEAP.DATA.Health` + `DNAM.DamageToWeaponMult`; linear damage loss as `CND` drops; reload jams; repaired by consuming duplicate weapons up to `Repair` skill. | Active `CND` with **peak-performance plateau** (`75%` guns / `66%` energy) before linear damage decay and reload jams; repaired via `Weapon Repair Kits` or *Jury Rigging* class matches. | **Removed** (`WEAP` never degrades or jams; only vestigial `NoJamAfterReload` flag and world `DEST`). | **Reintroduced** (`CND` degrades per hit, `100%` output until `0 CND` break; repaired at benches using junk components, mitigated by *Gunsmith*). | **Absent on `WEAP`** (only vestigial `COED.ItemCondition`, `XHLT`, `AMMO.Health`, `CTDA 398`). |
| **Modifications & Progression** | Fixed unique variants (`Xuanlong`, `Lincoln's Repeater`); `0` `IMOD` / `OMOD`. | `IMOD` (`50`): up to `3` permanent, meaningful physical upgrades per weapon + *Gun Runners' Arsenal* (`GRA`) receivers/ammo. | `OMOD` (`2,408`) + `AttachParentSlots` (`ap_*`) + `INNR` (`7`) + `COBJ` (`CMPO` scrap + `Gun Nut` / `Science!` perks); linear receiver damage bloat. | FO4 `OMOD` slots gated behind learned **Plans/Recipes** + scrapping + leveled item tiers. | `OMOD` (`2,682`) + `INNR` (`5`) + `LGDI` (`84`) + `COBJ` (`IRES` + `RQPK` + `RSPJ` research) + `Quality_##` tier bloat. |
| **Hit Locations & Limbs** | `BPTD` (`32`, `6` targetable parts), `AVIF` limb condition, dismember/explode, stimpak or sleep cures. | `BPTD` (`49`, `6` parts); Hardcore blocks stimpak limb cure (requires *Doctor's Bag* or *Hydra*). | `BPTD` (`40`, `HumanBodyPartData` `0x017AD4` w/ `12` parts), `OnCripple`, live non-lethal dismemberment (feral ghouls, robots). | FO4 `BPTD` limb multipliers + perk limb-damage cards; stimpak cures limbs. | `BPTD` (`27`, `8` human anatomical parts + `Boostpack`); stale `AVIF` links fixed in `FO4SFCombat.esm` (`0x840..0x842`); dismemberment cut. |
| **Sound** | Direct `.wav`/`.ogg` in `SOUN`. | Direct `.wav`/`.ogg` in `SOUN` (`2D` player fire + `3D` world fire + silenced variants). | `SNDR` (`5,476`: `Standard` / `Compound` / `AutoWeapon` `RatesOfFire`), `KSSM` (`139`), `SNCT` (`50`), `SOPM` (`311`). | Wwise transition / hybrid descriptors. | Pure Wwise (`WWED` `489`, `STCP`/`STAG`, `KSSM`, `WKMF`, `.bnk`/`.wem`). |

*(Note on `FO76` scope: per `docs/research/framework/findings/multi-game-scope.md` line 155, `FO76` assets and data are online-only under separate terms and are **never** read or converted by our pipeline; `FO76` is studied strictly for mechanical lessons such as junk-component bench repair and recipe-plan unlocks.)*

---

### What `Fallout4.esm` Gives Us to Convert Automatically vs What Must Be Synthesized

Cross-referencing `Mutagen.Bethesda.Fallout4` against `Mutagen.Bethesda.Starfield` (`0.55.0-alpha.67`) shows exactly what an automated C# Mutagen weapon converter (`Fo4Export` -> `StarfieldMod`) can translate deterministically from the user's installed `Fallout4.esm` + DLC versus what FO4SF must synthesize:

#### 1. Converts Automatically from `Fallout4.esm` (Deterministic Schema Translation)

| Source Record / Block (`Fallout4.esm`) | Target Record / Subrecord (`Starfield`) | Deterministic Conversion Rule |
|---|---|---|
| `WEAP.DNAM` general fields | `WEAP.WGEN` | `Weight * 0.453592f` (lb -> kg, matching `item_table.json`), `Value` -> `BaseValue`, `Speed` -> `BaseSpeed`, `ActionPointCost` -> `AttackOxygenCost`. |
| `WEAP.DNAM` damage & range + `DAMA` + `CRDT` | `WEAP.WDMG` + `DAMA` | `BaseDamage` -> `AttackDamage`, `MinRange`, `MaxRange`, `DamageOutOfRangeMult` -> `OutOfRangeDamageMult`, `HitBehavior` (`0..3` enum identical), `CritDamageMult`, `CritEffect` -> `CriticalHitSpell`, `CritEffectOnDeath` -> `CritEffectOnDeathOnly`, `DamageTypes` mapped via `DMGT` table. |
| `WEAP.DNAM` firing & `WeaponExtraData` | `WEAP.WFIR` | `Flags.Automatic` -> `FiringTypeEnum.Automatic`, else `SingleOrBinary`; `RepeatableSingleFire` -> `RepeatableFire`; `BoltAction`, `DisableShells` -> `DisableShellCaseEject`, `AttackDelay` -> `AttackDelaySeconds`, `AnimationAttackSeconds` -> `AttackSeconds`, `AnimationFireSeconds` -> `FireSeconds`, `BoltAnimSeconds` -> `BoltChargeSeconds`. |
| `WEAP.DNAM` ammo & `WeaponExtraData` | `WEAP.WAM2` | `Ammo` -> `AmmoType`, `Capacity` -> `AmmoCapacity`, `NumProjectiles` -> `ProjectilesCount`, `ProjectileOverride` -> `OverrideProjectile`, `Flags.NpcsUseAmmo` -> `NpcsUseAmmo`. |
| `WEAP.DNAM` reload, charge, bash, flags | `WRLO`, `WCHG`, `WMEL`, `WFLG` | `ReloadSpeed`, `Flags.ChargingReload` -> `ReloadCharging`; `FullPowerSeconds`, `MinPowerPerShot`, `ChargingAttack`, `HoldInputToPower`; `Reach` -> `MeleeReach`, `Stagger` -> `MeleeStagger` (`0..4` enum identical), `BlockBashImpactDataSet`, `AlternateBlockMaterial`; `PlayerOnly`, `CannotDrop`, `MinorCrime`, `NonHostile`, `NotPlayable` -> `NonPlayable`. |
| `WEAP.WAMD`, `WZMD`, `SightedTransitionSeconds` | `WEAP.WAIM` | `SightedTransitionSeconds`, `AccuracyBonus`, `Flags.HasScope` -> `HasScope`, `AimModel` -> converted `AMDL`, `Zoom` -> converted `ZOOM`. |
| `AMDL` (`51` records) | `AMDL` | `ConeOfFireMinAngle`/`MaxAngle` -> `ConeOfFireDegreesX`/`Y`, `ConeOfFireIncreasePerShot`, `ConeOfFireIncreasePerSec`, **`ConeOfFireDecreaseDelayMilliseconds / 1000.0f` -> `ConeOfFireDecreaseDelaySeconds`**, `ConeOfFireSneakMult`, `ConeOfFireIronSightsMult`, `RecoilDiminishSpringForce`, `RecoilDiminishSightsMult`, `RecoilMinPerShot`/`MaxPerShot` -> `RecoilDegreesPerShotX`/`Y`, `RecoilHipMult`, `RunawayRecoilShots` -> `RecoilShotsForRunaway`, `RecoilArc`, `RecoilArcRotate`, `BaseStability` -> `RecoilBaseStability`. |
| `ZOOM` (`16` records) | `ZOOM` | `FovMult`, `Overlay` (first `17` `Zoom.OverlayType` values match 1:1), `CameraOffset` (`X/Y/Z`). |
| `AMMO` (`57`) & `PROJ` (`139`) | `AMMO` & `PROJ` | `Weight`, `Value`, `Flags` (`IgnoresNormalWeaponResistance`, `NonPlayable`, `HasCountBased3d` identical), `ShortName`, `Projectile`; `PROJ` `Flags` (`13` flags identical!), `Gravity`, `Speed`, `Range`, `ImpactForce`, `ConeSpread`, `CollisionRadius`, `TracerFrequency`, `Explosion`. |
| `OMOD` (`2,408`), `APPR`, `INNR` (`7`), `COBJ` | `OMOD`, `APPR`, `INNR`, `COBJ` | Attach-point keywords (`ap_*`), `AttachParentSlots`, `Includes`, `FilterKeywords`, `LooseMod` (`LNAM`), `INNR` naming rules, `COBJ` recipes (`CMPO` -> `FO4SF` `IRES` components, `Gun Nut`/`Science!` -> `RQPK`/`CTDA`), and **`~78` of `91` `FO4 Weapon.Property` enum targets** map 1:1 by name/semantics onto `Starfield Weapon.Property` (e.g., `AttackDamage` -> `DamagePhysical`, `AimModelConeDecreaseDelayMs` -> `AimModelConeDecreaseDelayPerSec`, `AttackActionPointCost` -> `AttackOxygenCost`). |

#### 2. Cannot Convert Automatically — Must Be Synthesized or Rebuilt

1. **Weapon Behaviour Graphs & Clips (`.hkx` -> `.agx` / `.af` / `.afx`):** FO4 weapon animations use Havok `.hkx` subgraphs; Starfield uses in-house `.agx` graphs + `.af` clips + `.afx` frame events. Phase 1 binds converted `WEAP` records to the closest vanilla Starfield weapon animation class (`W1` in `workshop-items-economy.md`), while Phase 2 retargets FO4 clips through `CALUMI` + CK `-GenerateAnimInfo:`.
2. **Wwise Weapon Audio (`SNDR` -> `STCP` / `KSSM` / `WWED` / `WAUD`):** None of FO4's `5,476` `SNDR` descriptors translate byte-for-byte. Initially, weapons map by class/calibre (`10mm`, `.308`, `12ga`, `Laser`, `Plasma`) onto vanilla Starfield `STAG`/`KSSM`/`WWED` sets; authentic Fallout audio requires either custom `.bnk` generation (`H2`) or an SFSE positional audio bridge.
3. **Starfield-Only Handling Records (`WBAR`, `AAMD`, `AOPS`, `WCIM`, `ZOOM` delays):** `Fallout4.esm` has no cover-barrel distance (`WBAR`), no `AimAssistModel` (`AAMD`), no optical dot delay (`AOPS`), and its `IMAD` binary layout (`DNAM` floats) was replaced by CE2 `REFL` blobs—so our writer must assign curated Starfield templates per archetype.
4. **FO3/FNV Legacy Mechanics & Rebalanced Progression:** `Fallout4.esm` has **zero** calibre-based `AMMO.Damage`, **zero** `AP`/`JHP`/`+P` ammo subtypes, **zero** weapon condition or maintenance, **zero** `Strength` / `Skill` handling requirements, **zero** non-VATS critical chance (`CritChanceIncMult`), and **zero** structured manufacturer tiers. All of those belong to our own FO4SF design layer (Part (d)).

---

## Part (c): What Community Overhauls Changed — Ideas, Levers & Anti-Lessons

*(Strict compliance note: This section analyzes the design ideas and mechanical levers pulled by named community projects across Starfield, Fallout 4, and S.T.A.L.K.E.R. Zero files, text, or numeric values are copied from any external mod.)*

### (c.1) Starfield Gunplay & Progression Overhauls

- **Ascension — Gameplay Overhaul** (*SenterPat*):
  - *Ideas & Levers:* Converts Starfield into an unleveled world modeled on classic hardcore RPG overhauls. Deletes weapon quality tier `OMOD`s (`Calibrated`, `Refined`, `Advanced`, `Superior`) outright so a firearm found in the opening hour stays viable at endgame. Moves damage authority onto ammunition calibre rather than weapon drop level, removes the artificial per-bullet damage penalty on automatic receivers, raises baseline weapon sway so stance and patience matter, flattens exponential actor HP growth, and makes unarmored headshots decisive in both directions (player and NPCs). Also decouples character XP from workbench crafting loops.
- **NASAPUNK2330** (*corrosive*):
  - *Ideas & Levers:* Treats gunplay, inventory weight, and resource scarcity as one connected tactical loop. Strips looter-shooter sponge and tier bloat, enforces lethal two-way firefights where cover and suppression matter, tightens carry capacity and ammunition availability so the player commits to a primary weapon and sidearm rather than hauling an arsenal, and sharpens recoil and spread penalties when moving or firing from the hip.
- **Royal Weapon Balance / Royal Galaxy** (*youngneil1*):
  - *Ideas & Levers:* Takes a compatible "Vanilla+" weapon-by-weapon curation route rather than deleting progression tiers. Hand-tunes `WEAP` and `AMDL` profiles so neglected vanilla classes (particularly automatic rifles and energy weapons) remain competitive, differentiates weapon families through physical recoil mass, range falloff, and dispersion (giving laser weapons crisp low-mass recoil and heavy ballistics sharper kick), and fills progression dead zones so players are never forced to abandon a preferred weapon archetype.
- **StarValor** (*Zzyxzz*) & **GRiNDTerra Combat**:
  - *Ideas & Levers:* *StarValor* uses runtime record patching to strip per-level HP gain and activate `BPTD` locational damage multipliers; *GRiNDTerra* narrows the player-to-NPC level ratio and edits `CSTY` combat styles to push flanking, group cohesion, and cover behavior.

### (c.2) Fallout 4 Gunplay, Lethality & Progression Overhauls

- **True Damage** (*timershaft*):
  - *Ideas & Levers:* Strips arbitrary damage multipliers off `WEAP` receiver `OMOD`s and anchors base kinetic energy on the `AMMO` cartridge record. Barrel length and action type apply modest, physically plausible velocity adjustments, while automatic receivers trade recoil control and ammunition consumption instead of magically halving bullet energy.
- **SCOURGE** (*timershaft*):
  - *Ideas & Levers:* Pairs with calibre-based damage by eliminating unbounded per-level NPC health scaling. Assigns bounded, species- and chassis-specific health and armor pools (unarmored humans, ghouls, super mutants, synths, power armor, deathclaws) so calibre selection and armor penetration—not character level—decide time-to-kill.
- **MAIM** (*timershaft*):
  - *Ideas & Levers:* Replaces instant-heal health-bar attrition with localized trauma states (bleeds, concussions, limb fractures, pain-induced aim sway) cured by specific medical tools rather than generic stimpak spam, making limb shots tactically meaningful without inflating HP.
- **Better Locational Damage (BLD)** (*Zzyxzz*):
  - *Ideas & Levers:* Pioneered combining calibre-scaled weapons, helmet-checked headshot lethality, stagger/bleed reactions, and de-sponged actor scaling in one package. *Key architectural lesson for FO4SF:* running complex per-shot hit math in heavy Papyrus `OnHit` scripts causes noticeable VM queue lag under high-rate automatic fire, demonstrating why hot-path hit math belongs in native `BPTD`/`PERK` records or a small native DLL hook.
- **Equilibrium: Weapons** (*DeathMotif*):
  - *Ideas & Levers:* Pure record-level weapon and `OMOD` rebalance fixing dead-end vanilla weapons (miniguns, submachine guns, institute lasers) by tuning recoil recovery, spread, reload cadence, AP cost, and range falloff so every firearm owns a distinct role without touching survival or medical systems.
- **Horizon** (*zawinul*):
  - *Ideas & Levers:* Redesigns weapon progression around structured gunsmithing tech tiers, salvaged weapon parts, specialized ammunition crafting, and settlement workshop infrastructure. Proves how rewarding workbench progression feels when upgrades require genuine salvage and skill perks—while serving as a cautionary tale against building a monolithic, conflict-prone script ecosystem.

### (c.3) S.T.A.L.K.E.R. Anomaly & G.A.M.M.A. (*Grok's Ballistics Overhaul* & Parts System)

- **What Anomaly & G.A.M.M.A. Did Right (The Brilliant Ideas):**
  1. **Earned Firearms via Scavenging & Restoration:** Removing pristine endgame rifles from ordinary shopkeepers turns finding a worn military carbine and restoring it on a workbench into a memorable personal milestone ("this is *my* rifle").
  2. **Barrel Condition Drives Lethality, Internal Action Drives Reliability:** Separating barrel bore integrity (velocity and armor penetration) from trigger/bolt wear (malfunction rate) means even a battered scavenger rifle with a clean barrel hits with authentic ballistic authority—zero bullet sponge.
  3. **Generous Peak-Condition Plateau + Two-Tier Upkeep:** Keeping weapons at full ballistic performance across an upper "green" condition band and splitting upkeep into quick field cleaning (routine maintenance while healthy) versus workbench repair kits (restoring neglected salvage) rewards preventative care instead of constant nagging.
  4. **Calibre + Bullet Construction vs Armor Class & Unarmored Limbs:** Pairing armor-piercing rounds against plated torsos and hollow-point/buckshot rounds against unarmored mutants or exposed limbs turns ammunition cycling into an instant tactical puzzle during every firefight.

- **Why the Owner Said *"Not S.T.A.L.K.E.R. GAMMA Insane"* (Anti-Lessons We Explicitly Reject):**
  1. **Sub-Component Inventory Bloat:** Decomposing every looted firearm into multiple incompatible internal part items across lettered weapon classes floods containers and Pip-Boy inventories with tedious bookkeeping.
  2. **RNG Toolkit Progression Walls:** Gating basic barrel restoration behind rare stash-only toolkit drops stalls character builds on luck rather than skill or caps.
  3. **Punitive Damage Cliffs & Multi-Key Jam Drills:** Steep mid-fight damage/penetration cliffs below a condition threshold and constant multi-step jam-clearing key combinations turn firefights into frustrating UI chores.
  4. **Four-Item Medical Chains:** Requiring sequential tourniquets, bandages, painkillers, and post-heal drugs after routine skirmishes clashes with Fallout's pulp-retro tactical pace.

### (c.4) Six Distilled Design Rules for FO4SF

1. **Bullets own kinetic energy; receivers own mechanics** (fire mode, cycling speed, recoil damping, reliability—never arbitrary multi-hundred-percent damage tiers).
2. **Bounded anatomy-based health & `DR`-then-`DT` armor** (no level-94 human bullet sponges; armor plates stop hollow-points, `AP` punches plates, limbs cripple).
3. **Who made the gun matters** (a makeshift pipe gun and a pre-war Colt or post-war Gun Runners rifle firing the same cartridge deal similar muzzle energy, but feel Night-and-Day different in recoil recovery, sight picture, spread bloom, cover handling, and reliability).
4. **Every workbench mod has a real physical trade-off** (long heavy barrel = range & velocity vs ADS speed & weight; short barrel = CQB snap vs dispersion).
5. **Single-bar condition with a wide "healthy" plateau and two-item upkeep** (Gun Oil / Cleaning Kit in the field while kept clean; standard `FO4SF` scrap at any Weapon Workbench when worn—zero 50-part clutter, optional via `GPOF`).
6. **Data and native C++ on hot paths, never heavy `OnHit` Papyrus loops** (use `BPTD`, `AMDL`, `PERK` entry points `102`/`134`/`166`/`221`, and `FO4SFCombat.dll`).

---

## Part (d): Fallout Manufacturer & Tier Scheme + Four Concrete FO4SF Proposals

### (d.0) Lore-Authentic Fallout Manufacturer & Tier Progression Scheme

Instead of Starfield's generic `Calibrated -> Refined -> Advanced -> Superior` loot tiers or FO4's `Standard -> Hardened -> Powerful -> Advanced` receiver ladder, every firearm in FO4SF belongs to a **canonical Fallout Manufacturer House** (`KYWD` + `INNR` instance naming) and sits on a **4-Tier Chassis & Gunsmithing Architecture**.

#### The Seven Canonical Fallout Manufacturer Houses

| House / Lineage | Canonical Makers & Examples | Tactile Signature (`AMDL` / `WAIM` / `WFIR` / `WAUD`) | Upkeep & Bench Identity |
|---|---|---|---|
| **1. Wasteland Makeshift ("Pipe / Scrap")** | Commonwealth / Rustbelt Pipe Pistols, Pipe Bolt-Actions, Pipe Revolvers, Handmade Raider Rifles, Junk Jet, Railway Rifle | Loose sight alignment, wide `ConeOfFireDegreesX/Y`, sharp asymmetric `RecoilArcRotate`, slow `RecoilDiminishSpringForce`, smoky muzzle flash (`IMAD`), rattly mechanical audio. | Accepts dirty/surplus ammo without penalty; field-repairable anywhere with basic `Steel` & `Springs` (no workbench or perk required). |
| **2. Pre-War Civilian, Police & Sporting** | *Colt* (`6520` 10mm Pistol), *Smith & Wesson* / Police `.44` & Snubnose Revolvers, *Winchester* lever/hunting rifles, Riot & Double-Barrel Shotguns | Fast, natural `SightedTransitionSeconds`, crisp semi-auto reset (`HasStagedTrigger`), light `BaseWeight`, low initial cone, but rapid `ConeOfFireIncreasePerShot` and heat climb if spammed. | Common `Gun Nut 1–2` parts; abundant civilian calibres (`.38`, `10mm`, `.44`, `.308`, `12ga`). |
| **3. Pre-War U.S. & European Military Contractors** | *U.S. Ordnance / Colt* (Service Rifle, Assault Carbine, Marksman Carbine), *Heckler & Koch* / *Rheinmetall* (`G11` / `CAWS` / `MP9` classic Fallout lineage), *Rockwell* (`CZ53` Minigun) | Predictable vertical `RecoilArc`, strong `RecoilDiminishSpringForce`, high `RecoilShotsForRunaway`, full rail/bayonet/suppressor `AttachParentSlots`, rugged wear resistance. | Standard military calibres (`5.56mm`, `7.62mm`/`.308`, `5mm`, `10mm`); `Gun Nut 2–3` + military technical manuals. |
| **4. Pre-War Energy & Defense Corporations** | *Wattz Electronics* (`Wattz 1000`/`2000` precision lasers), *General Atomics / U.S. Army* (`AER9` ruggedized laser rifle), *Winchester / Repconn* (`P94` Plasma Caster), *West Tek*, *RobCo* | Near-zero mass kick (`RecoilDegreesPerShot` minimal) on lasers with instant hitscan/fast beam `PROJ`; slow, heavy plasma globules (`PROJ.Speed`) on *Winchester/Repconn* casters; capacitor charge (`WCHG`) on sniper barrels. | Gated by `Science! 1–3`; sensitive to overcharged cells (`Max Charge` accelerates crystal/coil fouling). |
| **5. Post-War Master Guilds (*Gun Runners* / `GRA`)** | *Gun Runners* hand-milled Service Rifles, Battle Rifles, `12.7mm` / `.45 Auto` Pistols, Anti-Materiel Rifles, Bozar | Match-grade `ConeOfFireIronSightsMult`, fastest `RecoilDiminishSightsMult`, crispest staged triggers, native tolerance for `+P` / `Match` / `AP` handloads without accelerated wear, stamped `[GRA]` via `INNR`. | Crafted or commissioned via `Gun Nut 3–4` + *Gun Runners* schematics (`BOOK`); premium `Springs`/`Screws`/`Oil`. |
| **6. Post-War Covert & Clean-Room Factions (*Institute* & *Railroad*)** | *Institute* polymer/syntho-ceramic pulse-lasers; *Railroad* suppressed Tinker specials & Deliverer-class covert sidearms | *Institute:* ultralight `BaseWeight`, fastest `SightedTransitionSeconds` and high `ShotsPerSecond`, lower per-shot thermal punch than `AER9` until upgraded with clean-room over-capacitors. *Railroad:* `SoundLevel.Silent`, subsonic stealth bonus. | Requires faction salvage (`Institute` polymer/optics) or covert schematics. |
| **7. Post-War Apex Ordinance (*Brotherhood* & *Enclave*)** | *Brotherhood* Scribe-calibrated `AER9` & Gatling Lasers; *Enclave* Urban Plasma (`P94` miniaturized), Gauss (`M72` coilgun lineage), Heavy Incinerator | Highest projectile velocity, armor-piercing `DT` bypass, `WCHG` Gauss coil capacitor lethality, heavy `Strength` handling requirement mitigated by Power Armor. | Top-tier `Science! 3–4` + `Gun Nut 3–4`; rare `Nuclear Material` / `Copper` / `Fiber Optics`. |

#### Clean 4-Axis Progression (Replacing Arbitrary "Advanced Receiver" Tiers)

1. **Axis 1 — Cartridge & Barrel Physics (`AMMO` + Barrel `OMOD`):**
   - Base damage is set by **calibre** (`AMMO` + `WEAP` chamber baseline).
   - **Barrels** shift muzzle velocity/damage only within a grounded physical band (`Short/Stub` CQB barrel: slightly lower velocity & `MaxRange`, much faster `SightedTransitionSeconds` and shorter `WBAR.CoverDetectionDistance`; `Long/Marksman` barrel: higher `MaxRange`, tighter `ConeOfFire`, modest velocity bonus, heavier `BaseWeight` and slower ADS).
2. **Axis 2 — Chassis Tier (`Tier I` Makeshift -> `Tier II` Civilian/Surplus -> `Tier III` Mil-Spec / Guild -> `Tier IV` Faction Masterwork):**
   - Advancing up chassis tiers transforms **how the gun handles under stress**: tighter dispersion, stronger recoil return springs, higher `RecoilShotsForRunaway`, more modular `AttachParentSlots` (`ap_optic`, `ap_muzzle`, `ap_underbarrel`), slower fouling, and higher `+P` / `Max Charge` pressure rating.
3. **Axis 3 — Mechanical Receivers & Calibration (`OMOD` + `COBJ` + `INNR`):**
   - Receivers never grant free linear "+damage ranks". Each receiver is a real mechanical choice:
     - *Hardened / Heavy-Wall Receiver:* Halves `+P` / `Overcharge` wear and reduces sustained `RecoilDegreesPerShotY`, adding slight mass.
     - *Match / Hair-Trigger Receiver:* Enables `HasStagedTrigger`, shortens semi-auto `FireSeconds`, tightens ADS spread (`ConeOfFireIronSightsMult`).
     - *Automatic / Sear-Converted Receiver:* Switches `FiringType` to `Automatic` or `Burst` **at `1.0x` per-bullet damage**, trading higher `RecoilDegreesPerShot` and `ConeOfFireIncreasePerShot`.
     - *Calibre-Conversion Receiver (e.g., `.38` <-> `.45` <-> `.308`, or `Fusion` <-> `Over-Capacitor`):* Re-chambers `WAM2.AmmoType` (updating `FO4SFCombat`'s runtime `Weapon.GetAmmo()` subtype family automatically!).
4. **Axis 4 — Optional Single-Bar Condition & Two-Item Upkeep (`GPOF` Tunable):**
   - One `0–100%` condition bar per equipped weapon: **`70%–100%` = Peak Plateau** (`90%–100%` freshly oiled grants a subtle reload/bolt smoothness bonus); **`35%–69%` = Fouled** (gradual cone bloom & recoil drift); **`<35%` = Worn** (occasional dry-fire hesitation).
   - Maintained above `60%` anywhere in the field with a single **Weapon Cleaning Kit / Gun Oil** item, and restored below `60%` at any **Weapon Workbench (`0x2B6A63`)** using standard `FO4SF` scrap (`Steel`, `Springs`, `Oil`, `Screws`). Zero sub-part clutter.

---

### Four Concrete FO4SF Implementation Proposals (Ordered Smallest First)

All four proposals build strictly on **our own tools** (`dotnet/CombatCore`, new C# Mutagen weapon passes, `src/fo4sf/combat/tables.py`, `FO4SF_CombatQuest.psc`, and `sfse/FO4SFCombat`) with **zero external mod dependencies**. Each proposal layers cleanly onto the previous one.

---

### Proposal 1 (Smallest — Pure ESM Data & GMSTs; Zero New Scripts, Zero New C++)
#### *"Calibre-Anchored Lethality, De-Sponged Actors & Grounded `AMDL`/`WAIM` Handling"*

- **What the Player Feels in Combat & Progression:**
  - Sponge disappears overnight: unarmored raiders drop in `1` headshot or `2–3` center-mass rifle rounds regardless of player level, while the player faces the same lethal respect for cover.
  - Automatic fire hits just as hard per bullet as semi-automatic fire, balanced by real physical muzzle climb (`RecoilArc`) and spread bloom (`ConeOfFireIncreasePerShot`) rather than halved bullet damage.
  - Aiming feels crisp, weighty, and direct: no invisible Starfield `BulletBending` curving shots, distinct ADS snap between pistols (`0.14s`) and long rifles (`0.32s`), subtle per-shot `IMAD` camera punch, and immediate anatomical feedback on headshots (`2.0x`), robot combat inhibitors (`1.65x`), and armored robot torsos (`0.75x`).
  - Looter-shooter `Calibrated / Refined / Advanced / Superior` tier bloat is gone from our world.

- **Exact Records & Writer Changes Needed (Zero Papyrus, Zero SFSE Changes):**
  1. **C# Mutagen Writer (`dotnet/CombatCore` or `dotnet/WeaponBalance`):**
     - Emit archetype `AMDL` (`AimModel`) records for `Pistol`, `Revolver`, `SMG`, `Carbine`, `BattleRifle`, `Shotgun`, `Sniper`, `Laser` (near-zero `RecoilDegreesPerShot`, tight `ConeOfFire`), `Plasma`, and `Heavy`, with `ConeOfFireDecreaseDelaySeconds` in seconds and distinct `RecoilDiminishSpringForce` / `RecoilArcRotate`.
     - Emit one grounded `AAMD` (`AimAssistModel`, `FO4SF_AimAssistGrounded`) with **`BulletBendingConeAngleDegrees = 0.0f`** and reduced rotational `Friction`.
     - Emit `WBAR` (`WeaponBarrelModel`) archetypes (`Short`, `Standard`, `Long`) setting `CoverDetectionDistance` and `EnterCoverAnimationTimeSeconds`, plus subtle ballistic/energy `IMAD` links on `WEAP.WCIM`.
     - Normalize converted/template `WEAP.WDMG.AttackDamage` by calibre family (`src/fo4sf/combat/tables.py`), strip `Quality_##` `OMOD` includes from `ObjectTemplates` (`OBTE`/`OBTS`), and set automatic receiver `OMOD` `DamagePhysical` multipliers to neutral (`1.0x` per round, trading `ShotsPerSecond` and `AMDL` bloom/recoil).
  2. **Actor & Difficulty De-Sponge (`NPC_`, `BPTD`, `GMST`, `GPOF`):**
     - Bind converted human, robot, and creature races/templates to `FO4SFCombat.esm`'s repaired `BPTD` records (`0x840..0x842` -> live `AVIF`s `0x00036C..0x000372`).
     - Cap per-level HP inflation on our `NPC_` templates (`Bounded Health` by species/armor class) and emit `GMST` overrides (`fDiffMultHPByPC*` / `fDiffMultHPToPC*`) + `GPOF` lethality presets so high difficulty raises **both** incoming and outgoing lethality (FO4 Survival style) rather than turning enemies into sponges.

- **Offline Proof vs Claude (PC) In-Game Test:**
  - **Proven Offline:** Mutagen `check` + Python unit tests verify: (a) `0` `Quality_##` `OMOD` links on our weapons; (b) `BulletBendingConeAngleDegrees == 0.0` on all `AAMD` links; (c) semi-auto vs full-auto `OMOD` per-shot damage parity within `1%`; (d) every `BPTD` `ActorValue` resolves to `0x00036C..0x000372`; (e) `FormVersion == 581` and `scripts/guard.py` pass.
  - **Requires Claude (PC) In-Game Test:** One 10-minute session in `FO4SF_CombatTestCell` (`0x850`) + Concord raider encounter verifying shots-to-kill (head vs torso vs limbs), absence of bullet-bending magnetism, `AMDL` spring recovery feel, `WCIM` screen kick, and whether `AMMO.Damage` adds natively to `WEAP.AttackDamage`.

- **Exact Record Bill & Installed-Plugin Footprint for Proposal 1 (`HOLD` — Not Built):**
  1. **Total Records Written: `42–55` records (~20 KB `.esm` delta, `0` `.pex` scripts, `0` `.dll` native changes):**
     - **`16–19` New Owned Records (`0x000860+`):**
       - `10` `AMDL` (`AimModel`) class archetypes (`Pistol`, `Revolver`, `SMG`, `Carbine`, `BattleRifle`, `Shotgun`, `Sniper`, `Laser`, `Plasma`, `Heavy`).
       - `1` `AAMD` (`AimAssistModel`: `FO4SF_AimAssistGrounded` with `BulletBendingConeAngleDegrees = 0.0f`).
       - `3` `WBAR` (`WeaponBarrelModel`: `Short`, `Standard`, `Long`).
       - `2` `IMAD` (`ImageSpaceAdapter` shot micro-impulses: ballistic & energy).
       - *(Optional `+3` records if exposed in Starfield's Gameplay Options UI: `2` `GPOF` + `1` `GPOG`. Reuses the `3` repaired `BPTD` records `0x000840..0x000842` already owned by `FO4SFCombat.esm`, so `0` new `BPTD` records are needed.)*
     - **`26–36` Override Records (targeting `Starfield.esm` forms used by our world/loot/actors):**
       - `5` active `Starfield.esm` `WEAP` records (`0x24561C` Vault/route pistol, `0x26D96B` double-barrel shotgun, `0x2773C8` combat rifle, `0x028A02` sniper rifle, `0x0547A3` heavy weapon — or `8` if starter `Eon`, `Equinox`, and `Lawgiver` are included), updating `WDMG.AttackDamage`, `WAIM`, `WGEN.WeaponBarrel`, `WCIM`, and stripping `Quality_##` tier `OMOD`s from `OBTE`.
       - `6–12` `Starfield.esm` automatic-receiver & quality-tier `OMOD` overrides (`1.0x` per-round damage on automatic receivers; `1.0x` neutralized tier multipliers on `Quality_01..04`).
       - `12` `Starfield.esm` `GMST` overrides (`10` difficulty damage scalars `fDiffMultHPByPCVE`..`VH` & `fDiffMultHPToPCVE`..`VH` + `2` per-level NPC HP scalars `fNPCHealthLevelBonus` & `iAVDhmsLevelUp`).
       - `1–2` `RACE` overrides (`Starfield.esm` `HumanRace` `0x00347D` -> `BodyPartData = FO4SFCombat.esm:0x000840`; optional `FO4SFMission.esm` `FO4SF_CodsworthRace` `0x000818` -> `0x000841`).
       - `1–3` `Starfield.esm` `NPC_` template overrides (`EncSpacer01Template` `0x270255`, inherited by `FO4ActorRaider.esm`'s `FO4_LvlRaider` `0xF04800`, plus optional upper Spacer templates to cap base HP).
  2. **Which of the Owner's Installed Plugins Proposal 1 Touches:**
     - **Converted Asset, Terrain, Bridge & Quest Plugins Touched: `ZERO` (`0` bytes changed, `0` re-conversions, `0` BA2 repacks):**
       - Leaves **`FO4Port.esm`, `FO4PortTextures2.esm`, `FO4TerrainCore.esm`, `FO4TerrainCore_Mars.esm`, `FO4DLC.esm`, `FO4SFBridge.esm`, `FO4ActorRaider.esm`, `FO4SFVaultGearDoor.esm`, `FO4SFExitLift.esm`, `FO4SFNewGame.esm`, `FO4SFRouteLoot.esm`, and `FO4SFCoreValues.esm` 100% untouched**.
     - **Packaging Choice on the Owner's Load List (Candidate 2b/2c 22-plugin player set):**
       - **In-place in `FO4SFCombat.esm`:** Touches **only `1` existing slice plugin (`FO4SFCombat.esm`)**, already active in the 22-plugin Candidate 2b/2c load list (`0` extra plugin slots).
       - **Or as standalone `FO4SFWeaponBalance.esm`:** Touches **`0` existing plugins** and adds `1` ~20 KB overlay `.esm` at the end of `Plugins.txt` that can be toggled `on`/`off` cleanly via `plugin_toggle.py` for instant A/B comparison. *(Note: the older 7-plugin Vault-exit-only set does not load `FO4SFCombat.esm` or `FO4SFCoreValues.esm`, whereas Candidate 2b/2c already loads both.)*

---

### Proposal 2 (Pure Data + Workbench `OMOD`/`INNR` + Zero-Polling `PERK` Entry Points; Zero New C++)
#### *"Fallout Manufacturer Chassis Tiers, Trade-Off Gunsmithing & Native Skill/Strength/Limb Sway"*

- **What the Player Feels in Combat & Progression:**
  - Every gun tells you **who built it and how well it was machined**: looting a `[Colt] 10mm Pistol` or commissioning a `[GRA] Service Rifle` after surviving with a `[Makeshift] Pipe Carbine` feels like stepping from a rattling jalopy into a precision instrument—faster sight acquisition, tighter sustained bursts, cleaner recoil return, and full optic/suppressor rails—without turning early guns into pea-shooters.
  - Character build and posture visibly govern weapon handling **every frame**: firing a heavy rifle below its `Strength` threshold or with a crippled arm noticeably widens reticle bloom and scope drift; crouching or investing in `Guns` / `Energy Weapons` / `Strength` locks the sights steady.
  - At the Weapon Workbench (`0x2B6A63`), every attachment is a meaningful tactical choice rather than a mandatory "+damage" tax, and finding a *Wattz*, *Gun Runners*, or *Brotherhood* schematic (`BOOK`) unlocks coveted manufacturer mods.

- **Exact Records & Writer Changes Needed (Zero New C++ Hooks):**
  1. **Manufacturer `KYWD`s, `INNR` Naming & 4-Tier `OMOD` Trees (`dotnet/WeaponBalance`):**
     - Add manufacturer `KYWD`s (`FO4SF_Mfg_Makeshift`, `FO4SF_Mfg_Colt`, `FO4SF_Mfg_Winchester`, `FO4SF_Mfg_USOrdnance`, `FO4SF_Mfg_HK`, `FO4SF_Mfg_Wattz`, `FO4SF_Mfg_GeneralAtomics`, `FO4SF_Mfg_WestTek`, `FO4SF_Mfg_GunRunners`, `FO4SF_Mfg_Institute`, `FO4SF_Mfg_Railroad`, `FO4SF_Mfg_Brotherhood`, `FO4SF_Mfg_Enclave`) and chassis tier `KYWD`s (`FO4SF_Tier_1_Makeshift` .. `FO4SF_Tier_4_Masterwork`).
     - Author `INNR` (`InstanceNamingRules`) sets so workbench combinations dynamically name weapons (e.g., `Suppressed [Colt] 10mm Pistol`, `Match [GRA] Service Rifle`, `Over-Capacitor [Wattz] Laser Rifle`).
     - Build trade-off `OMOD` + `COBJ` graphs gated by `RQPK` (`FO4SF` `Gun Nut` / `Science!`), `FO4SF` `IRES` components (`31` converted FO4 scrap resources), and schematic `BOOK`/`GLOB` conditions.
  2. **Zero-Polling Handling & Sway via Native `PERK` Entry Points (`FO4SFCombat.esm`):**
     - Add a start-game hidden player ability perk `FO4SF_WeaponHandlingPerk` using **pure engine `PRKE` tabs** (zero script overhead!):
       - **`EntryType.ModConeoffireMult` (`134`)** & **`EntryType.ModActorScopeStability` (`102`)** conditioned (`CTDA`) on:
         - `FO4SF_Special_Strength` (`0x810` area in `FO4SFCoreValues.esm`) vs weapon weight/class keywords (`FO4SF_ReqStr_6`, `FO4SF_ReqStr_8`, mitigated if in Power Armor!).
         - `FO4SF_Skill_Guns` (`0x823`) / `EnergyWeapons` thresholds (FNV `25 / 50 / 75 / 100` tiers).
         - Live limb condition `AVIF`s (`LeftAttackCondition` `0x00036E`, `RightAttackCondition` `0x00036F`, `PerceptionCondition` `0x00036C`, `FO4SF_AimSwayPenalty` `0x80A`).
         - Stance conditions (`IsSneaking`, `GetMovementSpeed`, `GetInIronSights`).
       - **`EntryType.ModWeaponReloadSpeed` (`166`)** & **`EntryType.ModMagazineDrawSpeed` (`167`)** scaled by `Agility` and manufacturer ergonomics.
       - **`EntryType.ModTargetStagger` (`34`)** scaled by heavy-calibre / shotgun slug keywords.

- **Offline Proof vs Claude (PC) In-Game Test:**
  - **Proven Offline:** Mutagen writer/checker validates all `OMOD` `AttachPoint` / `AttachParentSlots` graphs, verifies no `OMOD` exceeds the physical barrel velocity band (`±20%`), checks all `COBJ` `IRES`/`RQPK` links, and validates `PERK` `PRKE` condition indices (`102`, `134`, `166`, `167`, `34`).
  - **Requires Claude (PC) In-Game Test:** Activate Weapon Workbench (`0x2B6A63`), craft and swap barrel/receiver/optic `OMOD`s, confirm `INNR` dynamic naming in inventory, and test live crosshair bloom/scope sway changes when modifying `FO4SF_Special_Strength`, `FO4SF_Skill_Guns`, and `RightAttackCondition` via console (`[102]` iron-sight vs scope check).

---

### Proposal 3 (Light Papyrus + Existing `FO4SFCombat.dll` VM Dispatch; Zero Engine Detours)
#### *"Live Real-Time Calibre Subtype Swapping, Single-Bar Weapon Maintenance & Soft Malfunctions"*

- **What the Player Feels in Combat & Progression:**
  - Pressing **`N`** mid-firefight swaps ammunition subtypes in real time (`Standard` -> `AP` when a Brotherhood Paladin or Sentry Bot steps out -> `JHP` / `Buckshot` when feral ghouls rush -> `+P` / `Max Charge` for desperate high-pressure output), with an immediate chamber-swap sound and HUD notification—not restricted to VATS shots.
  - Firearms feel like real mechanical objects you care for, **never a chore**: a well-kept rifle (`70%–100%` condition) runs flawlessly and reloads crisply when oiled (`90%+`). Firing hundreds of rounds or burning hot `+P` / `Max Charge` loads gradually fouls the bore (`<70%` mild spread bloom), and severely neglected salvage (`<35%`) risks an audible dry-fire click (`WAUD.DryFire`) requiring a quick trigger pull or reload.
  - Wiping a rifle above `60%` takes two seconds with a **Weapon Cleaning Kit**; restoring a `25%` raider salvage find takes standard scrap (`Steel`, `Springs`, `Oil`) at any Weapon Workbench. Players who dislike upkeep can flip one Gameplay Option (`GPOF`) to turn degradation off completely.

- **Exact Records, Scripts & `FO4SFCombat.dll` Changes Needed:**
  1. **Records (`FO4SFCombat.esm` & `FO4SFCoreValues.esm`):**
     - `GPOF` `FO4SF_GPO_WeaponCondition` (`Off` / `Survival Only` / `Always On`) backed by `GLOB` `FO4SF_WeaponConditionEnabled`.
     - `AVIF` `FO4SF_EquippedWeaponCondition` (`DefaultValue = 100.0`, persisted in save via `FO4SFCoreValues.esm` `R13`).
     - `ALCH`/`MISC` `FO4SF_WeaponCleaningKit` (field cleaning `>= 60% -> 100%`, craftable at Chem/Industrial bench from `Oil` + `Cloth`) and workbench `COBJ` restoration recipe (`< 60% -> 100%`).
     - Extend `FO4SF_WeaponHandlingPerk` (`PRKE` `134` & `166`) with tabs conditioned on `GetValue(FO4SF_EquippedWeaponCondition)`: `>= 90` (`+8%` reload speed), `70..89` (`1.0x` neutral plateau), `35..69` (`1.15x–1.35x` cone mult), `< 35` (`1.50x` cone mult).
  2. **Papyrus (`scripts/combat/FO4SF_CombatQuest.psc`) & `sfse/FO4SFCombat`:**
     - Extend `CycleAmmoSubtype()` so pressing **`N`** (`FO4SFCombat.dll` `DispatchStaticCall` -> `FO4SF_CombatInput.OnAmmoKey`) equips the active subtype `AMMO` form directly (`player.EquipItem(subtypeAmmo, false, true)`) or tests `WEAP.WAM2.AmmoList` compatibility, applying subtype `wear_mult` (`+P = 1.25x`, `Max Charge = 1.75x`, `Makeshift = 1.15x`, `Mil-Spec/GRA = 0.70x`).
     - Track shot-batch wear cleanly via ammo-count delta on `OnItemRemoved` (filtered strictly to `CalibreBaseAmmoList` / subtype `FLST`s—zero per-frame polling!) or `ApplyAimDownSightSpell` / reload check, decrementing per-weapon condition in a compact Papyrus array keyed by `Weapon` base/slot and syncing `FO4SF_EquippedWeaponCondition` for the Pip-Boy `INV`/`STAT` page (`FO4SFPipboyMenu.dll` data channel).

- **Offline Proof vs Claude (PC) In-Game Test:**
  - **Proven Offline:** Pure-Python translated simulation in `src/fo4sf/combat/tables.py` + `tests/test_combat_core.py` proving: (a) `70%–100%` zero-penalty plateau; (b) subtype `wear_mult` & manufacturer durability math; (c) Cleaning Kit refusal below `60%` with clear player message (`R10`); (d) `GPOF == 0` bypasses all wear math cleanly.
  - **Requires Claude (PC) In-Game Test:** Test `player.EquipItem(subtypeAmmo)` during live non-VATS firing on a `WEAP` chambered for `Ammo777mm` / `AmmoShotgun` (confirming whether Starfield fires the equipped subtype `PROJ` directly or requires `WEAP.WAM2.AmmoList` / `PerkEntryPoint.OverrideWeaponProjectile` `206`!), plus Cleaning Kit UX and Pip-Boy condition readout.

---

### Proposal 4 (Largest — Native `FO4SFCombat.dll` C++ Engine Hooks + Custom Clip/Audio Pipeline)
#### *"Zero-Latency Native DT/DR & Helmet Hitlocations, Dismemberment, Procedural Camera Impulse & Authentic Fallout Clips/Audio"*

- **What the Player Feels in Combat & Progression:**
  - **Instant, zero-lag automatic fire & shotgun lethality:** Even when hosing a room with a Rockwell Minigun or H&K SMG, every single pellet and bullet evaluates `DR`-then-`DT` armor plates, `AP`/`JHP` penetration, helmet protection (an unhelmeted raider drops to a `9mm JHP` headshot, while a Combat-Helmeted Gunner or Power-Armored Paladin deflects `JHP` with sparks until you switch to `AP` or aim for visor/legs!), localized stagger, and **classic Fallout dismemberment** at native C++ speed with zero Papyrus queue delay.
  - **Visceral mechanical camera & weapon weight:** Every calibre and manufacturer chassis drives a crisp, frame-accurate native recoil recovery curve and micro-impulse camera kick, plus a genuine mechanical jam-clear animation on `<35%` worn makeshift weapons.
  - **100% Fallout sight and sound:** Converted Fallout 4 / New Vegas weapon reload and fire clips (`.af`/`.afx`) and locally converted Fallout gunshot/reload audio replace Starfield's placeholder subgraphs and sci-fi soundbanks.

- **Exact Native `FO4SFCombat.dll` Hooks, Records & Pipeline Needed:**
  1. **Native Combat & Dismemberment Hooks (`sfse/FO4SFCombat/src/`):**
     - Upgrade `SFSE::Init` in `sfse/FO4SFCombat/src/main.cpp` (gated by per-feature flags in `FO4SFCombat.ini`, pinned to `1.16.244.0` + `versionlib-1-16-244-0.bin` `format 5` + RTTI/prologue verification, registered in `sfse/native_components.json`):
       - **Hit-Evaluation Hook:** Intercepts projectile/weapon hit resolution on `Actor`, reads struck `BPTD` part (`0x00036C..0x000372`), inspects target worn `ARMO` biped slots (head/helmet vs torso vs limbs) for zone-specific `DT`/`DR`, applies active `AMMO` subtype (`dt_pierce`, `dt_mult`, `dmg_mult`), and writes final damage + limb `AVIF` delta directly in C++ without waking the Papyrus VM.
       - **Native Dismemberment (`Owner Decision FS-6`):** Exposes `FO4SF_CombatNative.Dismember(Actor, string part)` / `IsDismembered` and triggers limb-hide / gore-cap art (`ARTO` / `BPTD` `GoreTargetBone` node scaling + `DEBR` spawn) on lethal limb/head overkill.
       - **Procedural Recoil/Camera & Subgraph Jam Trigger:** Applies frame-rate-independent camera pitch/roll micro-springs scaled by cartridge impulse and triggers `SetSubGraphFloatVariable` / `PlaySubGraphAnimation` for single-press jam clearing.
  2. **Launcher Asset Pipeline (Local User-Owned Conversion Only):**
     - **Weapon Clips (`.hkx` -> `.af` + `.afx`):** Clean-room Havok spline decoder -> bone retarget onto Starfield 1st/3rd-person weapon rigs -> `CALUMI.Animation` `.af` + `.afx` frame-annotated sound/casing events + CK `-GenerateAnimInfo:`.
     - **Weapon Audio (`.xwm`/`.wav` -> Wwise `.wem`/`.bnk` or `FO4SFCombat` XAudio2 3D Mixer):** Local decode via `ffmpeg` -> either Wwise `Starfield.wproj` CLI soundbank build (once `H2` bank registration passes) or a lightweight 3D positional audio voice pool inside `FO4SFCombat.dll` ducked against game pause/menus and `ASPC` interior flags.

- **Offline Proof vs Claude (PC) In-Game Test:**
  - **Proven Offline:** Host C++ unit tests (`tests/sfse_combat_math_test.cpp` following `tests/sfse_border_scan_test.cpp`) verifying zone-armor `DT`/`DR` math, helmet-slot bitmask checks, `FO4SFCombat.ini` feature-flag isolation, and Address Library / PE bounds refusal (`test_native_components.py`); offline `.af`/`.afx` header validators and `.wem` decoders.
  - **Requires Claude (PC) In-Game Test:** (a) Address Library hook verification on `1.16.244.0`; (b) `10`-NPC automatic-fire stress test confirming `0` Papyrus stack dumps and exact C++ hit log parity; (c) helmeted vs unhelmeted headshot test (`JHP` deflection vs `AP` penetration); (d) live dismemberment visual check and 1st-person converted weapon clip/audio test.

---

### Decision Matrix for Owner Review (`Proposals 1 -> 4`)

| Proposal | Engineering Footprint | External Mods | Key Player Payoff | Primary Technical Gate for Claude (PC) |
|---|---|---|---|---|
| **Proposal 1:** *Calibre Lethality & `AMDL`/`WAIM` Pass* | Small (C# Mutagen ESM + `GMST`/`GPOF` only; `0` scripts, `0` C++) | **Zero** | Ends bullet sponge & tier bloat; equalizes auto/semi bullet energy; crisp recoil, ADS & `2.0x` headshots | 10-min range & Concord TTK/feel check; confirm `AMMO.Damage` behavior |
| **Proposal 2:** *Fallout Manufacturers, Gunsmithing & `PERK` Sway* | Medium (ESM `OMOD`/`COBJ`/`INNR`/`KYWD` + zero-polling `PERK` `102`/`134`/`166`) | **Zero** | Authentic *Colt / Wattz / Gun Runners / Institute / Enclave* identity; trade-off mods; live `STR`/skill/limb sway | Weapon Workbench (`0x2B6A63`) mod swap, `INNR` naming, & `PERK 102/134` sway test |
| **Proposal 3:** *Live Ammo Swap & Single-Bar Maintenance* | Medium-Plus (`FO4SF_CombatQuest.psc` + existing `FO4SFCombat.dll` VM dispatch) | **Zero** | Real-time `N`-key `AP`/`JHP`/`+P` tactical swaps; rewarding `70%` plateau + Cleaning Kit / scrap upkeep (`GPOF` toggle) | Verify real-time `EquipItem(AMMO)` vs `Perk 206 OverrideWeaponProjectile` in live combat |
| **Proposal 4:** *Native C++ Hit/Armor Hooks, Dismemberment & Clips/Audio* | Large (`FO4SFCombat.dll` C++ hooks + local `.af`/`.wem` converter) | **Zero** | Zero-lag full-auto `DT`/`DR`, helmeted vs bare headshots, Fallout dismemberment (`FS-6`), authentic animations & sound | `1.16.244.0` C++ hook validation, auto-fire stress test, `.af` subgraph & audio check |

**Recommended Staged Path:** Approve **Proposal 1 + Proposal 2 together** as our immediate data-only foundation (zero new C++ risk, zero polling scripts, immediate transformation of combat lethality and Fallout manufacturer progression), followed by **Proposal 3** once real-time ammo-override behavior is confirmed in one `FO4SF_CombatTestCell` run, and **Proposal 4** alongside the `FS-6` dismemberment and weapon-animation milestones.
