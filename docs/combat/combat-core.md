# Combat Core (`FO4SFCombat.esm` + `FO4SFCombat.dll`)

Unified CF-8 combat slice covering **1a. Hit locations and limb damage**, **1b. Slow-time VATS targeting**, and **1c. Calibre-table New Vegas ammo subtypes and reloading-bench recipes**.

---

## 1. Cross-Title ESM Evidence (Read-Only Record Counts & Names)

Before designing `FO4SFCombat.esm`, read-only header and group scans were run against `Fallout3.esm`, `FalloutNV.esm`, `Fallout4.esm`, and `Starfield.esm` (record names and counts only; zero game text extracted):

| Record / Primitive | `Fallout3.esm` | `FalloutNV.esm` | `Fallout4.esm` | `Starfield.esm` |
|---|---:|---:|---:|---:|
| `BPTD` (Body Part Data) | `32` (`PlayerBodyPartData` `0x00001C`, `DefaultBodyPartData` `0x00001D`, `6` targetable `BPND` parts) | `49` (`PlayerBodyPartData` `0x00001C`, `DefaultBodyPartData` `0x00001D`, `6` targetable `BPND` parts) | `40` (`HumanBodyPartData` `0x017AD4` w/ `12` `BPND` parts, `DefaultBodyPartData` `0x00001D`) | `27` (`HumanBodyPartData` `0x003481`, `ModelABodyPartData` `0x00562C`, `TerrormorphBodyPartData` `0x21E736`, `24` others) |
| `AMMO` (Ammunition) | `30` | `92` (`Ammo9mmP`, `Ammo5mmHollowPoint`, `Ammo127mmHollowPoint`, `Ammo12GaMagnum`, `Ammo20GaMagnum`) | `57` | `150` (`Ammo777mm` `0x04AD3E`, `Ammo11mm` `0x04AD3F`, `AmmoShotgun` `0x0547A1`, `AmmoLaser` `0x00E8EC`, `Ammo50Cal` `0x2B559A`) |
| `AMEF` (Ammo Effect) | `0` | `54` (`AmmoEffect5mmAPDTReduction`, `AmmoEffect5mmHPDTPenalty`, `AmmoEffectBuckshotDamageBonus`, `AmmoEffectOCDTBypass`, `AmmoEffectMCDTBypass`, `AmmoEffectMagnumDamageBonus`, `AmmoEffectJSPConditionPenalty`) | `0` | `0` (Starfield dropped `AMEF`; subtypes must resolve via calibre table) |
| `WEAP` (Weapons) | `160` | `261` | `252` | `406` (`Grendel` `0x028A02`, `Breach` `0x0547A3`, `EquiNOX` `0x01BC4F`, `Eon` `0x0476C4`, `Lawgiver` `0x02D7F4`) |
| `IMOD` / `OMOD` (Weapon Mods) | `0` / `0` | `50` / `0` | `0` / `2,409` | `0` / `2,682` |
| `RCPE` / `COBJ` (Crafting & Reloading) | `0` / `0` | `105` `RCPE` (`20` `RecipeBreakdown*` / `RecipeAmmo*` handload & reloading recipes) | `0` / `2,161` `COBJ` | `0` / `3,009` `COBJ` (`WorkbenchIndustrialKeyword` `0x0AA209`) |
| `CAMS` / `CPTH` (Killcam / VATS Cameras) | `229` / `307` | `276` / `418` | `772` / `447` | `272` / `148` |
| VATS `GMST` Settings | `40` (`fVATSRangeSpreadMax`, `fVATSStrangerDistance`, `fVATSPlaybackDelay`) | `42` (`fVATSFortuneOdds`, `fVATSCriticalChanceBonus`) | `50` (`fVATSCriticalChargeBase`, `fVATSCameraHitSec`) | `51` (`fVATSChanceConeDistanceMult`, `fVATSMeleeMaxDistance`) |

### Key `Starfield.esm` Engine Findings

1. **Stale `BPTD` ActorValue Links vs Live `AVIF` Forms (`0x00036C..0x000372`):**
   - `Starfield.esm` retains all seven Fallout limb-condition `AVIF` records with `DefaultValue = 100`:
     - `0x00036C` `PerceptionCondition` (Head)
     - `0x00036D` `EnduranceCondition` (Torso)
     - `0x00036E` `LeftAttackCondition` (Left Arm)
     - `0x00036F` `RightAttackCondition` (Right Arm)
     - `0x000370` `LeftMobilityCondition` (Left Leg)
     - `0x000371` `RightMobilityCondition` (Right Leg)
     - `0x000372` `BrainCondition` (Head Condition / Robot Inhibitor)
   - However, `HumanBodyPartData` (`0x003481`), `ModelABodyPartData` (`0x00562C`), and `TerrormorphBodyPartData` (`0x21E736`) in `Starfield.esm` still reference the unmigrated Fallout 4 form IDs `0x00038A..0x00038F` (which do not exist as major records in `Starfield.esm`) and set `DamageMult = 1.0` on Torso, Arms, Legs, and Feet (`2.0` on Head only).
   - `HumanBodyPartData` (`0x003481`) contains `13` `BodyPart` entries: `4` non-targetable utility nodes (`COM`, `LookAt`, `Camera`, `Root`) plus the **8-part human anatomical set** (`Head`, `Torso`, `LeftArm`, `RightArm`, `LeftLeg`, `RightLeg`, `LeftFoot`, `RightFoot`) and dorsal `Boostpack`.
   - `FO4SFCombat.esm` clones `HumanBodyPartData` (`FO4SF_CombatHumanBptd` `0x840`), `ModelABodyPartData` (`FO4SF_CombatRobotBptd` `0x841`), and `TerrormorphBodyPartData` (`FO4SF_CombatCreatureBptd` `0x842`), repairing every `BodyPart.ActorValue` onto live `0x00036C..0x000372` and writing explicit zone `DamageMult` values without overriding any vanilla `Starfield.esm` record.
2. **Unconditional Slow-Time Ability (`abBoostAssaultSlowTime` `0x0B0885` -> `SlowTimeChem` `0x2A34F1`):**
   - `Starfield.esm` `abBoostAssaultSlowTime` (`SPEL 0x0B0885`) applies `SlowTimeChem` (`MGEF 0x2A34F1`) as a self `Ability`, gated by `IsBoostPackHovering == 1`. Cloning `0x0B0885` into `FO4SF_VatsSlowTimeAb` (`0x814`) with `Conditions.Clear()` gives an unconditional engine time-dilation toggle (`player.AddSpell` / `player.RemoveSpell`).
3. **Zero-Edit Calibre Lookup & Queued Shot (`Weapon.psc`):**
   - `Ammo Function GetAmmo() native` returns the equipped weapon's base calibre `AMMO` form at runtime without editing any `WEAP` record.
   - `Function Fire(ObjectReference akSource, Ammo akAmmo = None) native` fires the queued VATS shot from the player using the active ammo subtype `AMMO` form.

---

## 2. Unified Hit Locations, Limb Cripple & Cure (`1a`)

One rule set (`src/fo4sf/combat/tables.py` + `scripts/combat/FO4SF_CombatQuest.psc`) governs **humans, robots, and creatures**:

| Zone | Starfield `AVIF` | Human Mult | Robot Mult | Creature Mult | Cripple Penalty (`Condition <= 0`) |
|---|---|---:|---:|---:|---|
| `head` | `PerceptionCondition` (`0x00036C`) | `2.00x` | `1.25x` | `1.75x` | `-4 PER`, `+20` aim sway |
| `torso` | `EnduranceCondition` (`0x00036D`) | `1.00x` | `0.75x` | `0.90x` | Stagger / bleed check |
| `left_arm` | `LeftAttackCondition` (`0x00036E`) | `0.85x` | `0.85x` | `0.85x` | `+35` aim sway (`+65` both arms), `-20%` VATS hit chance |
| `right_arm` | `RightAttackCondition` (`0x00036F`) | `0.85x` | `0.85x` | `0.85x` | `+35` aim sway, **weapon drop / unequip** on cripple transition |
| `left_leg` / `left_foot` | `LeftMobilityCondition` (`0x000370`) | `0.85x` | `0.85x` | `0.85x` | `-40` `SpeedMult` slow walk (`-60` both legs) |
| `right_leg` / `right_foot` | `RightMobilityCondition` (`0x000371`) | `0.85x` | `0.85x` | `0.85x` | `-40` `SpeedMult` slow walk (`-60` both legs) |
| `special_optic` | `PerceptionCondition` (`0x00036C`) | `2.20x` | `1.75x` | `2.00x` | Blinded / `-4 PER`, `+20` aim sway |
| `special_core` | `BrainCondition` (`0x000372`) | `1.50x` | `1.65x` | `1.85x` | Robot Combat Inhibitor / Boostpack / Belly critical |

### Cure Rule (Normal vs Hardcore `#809`)
- `FO4SF_CombatQuest` reads `FO4SFHardcore.esm` `0x802` (`FO4SF_HardcoreEnabled`) via `Game.GetFormFromFile` (or local `FO4SF_CombatHardcoreOverride` `0x804` in standalone tests).
- **Normal (`Hardcore == 0`):** Using `FO4SF_CombatStimpak` (`0x813`, or vanilla medpack hook) **or** `FO4SF_DoctorsBag` (`0x811`) restores all limb `AVIF`s to `100` and removes `SpeedMult` / `FO4SF_AimSwayPenalty` debuffs.
- **Hardcore (`Hardcore == 1`):** Stimpak heals HP over time only and **refuses** to restore crippled limbs (`cured=0`); `FO4SF_DoctorsBag` (`0x811`) cures all crippled limbs (`cured=1`).

---

## 3. Slow-Time VATS Targeting Mode (`1b`)

1. Pressing **`V`** (`VatsKey=0x56` in `FO4SFCombat.ini`, or dropping `FO4SF_VatsTriggerToken` `0x816` in console-free non-SFSE sessions) calls `FO4SF_CombatInput.OnVatsKey()`.
2. `FO4SF_CombatQuest.ToggleVats()` applies `FO4SF_VatsSlowTimeAb` (`0x814`, `25%` time scale), finds the nearest valid combat target in front of the player, computes per-zone AP cost (`pistol 20`, `energy 25`, `rifle 28`, `shotgun 30`, `heavy 38`, plus `+0..+5` zone surcharge) and clamped `[5%, 95%]` hit chance from `distance_m`, weapon skill, `PER`, zone geometry, and crippled-arm penalty, and opens `FO4SF_VatsLimbPickerMsg` (`0x815`).
3. Selecting a limb deducts AP from `FO4SF_VatsApPool` (`0x805`), fires the equipped weapon via `weap.Fire(player, activeSubtypeAmmo)`, rolls against hit chance, applies `ApplyZoneHit`, and removes `FO4SF_VatsSlowTimeAb`.

---

## 4. Calibre-Table Ammo Subtypes & `#813` Reloading Bench (`1c`)

- Pressing **`N`** (`AmmoKey=0x4E` in `FO4SFCombat.ini`, or activating the Ammo Cycle Pedestal / dropping `FO4SF_AmmoCycleToken` `0x817`) calls `FO4SF_CombatInput.OnAmmoKey()`.
- `FO4SF_CombatQuest.CycleAmmoSubtype()` inspects `player.GetEquippedWeapon(0).GetAmmo()` against `FO4SF_CalibreBaseAmmoList` (`0x82C`) and advances `FO4SF_ActiveAmmoSubtype` (`0..3`) across parallel `FLST`s (`0x82D..0x82F`), applying across **every** weapon of that calibre with **zero per-weapon record edits**:
  - **Ballistic (`7.77mm`, `11mm`, `.50 Cal`):** `Standard` (`1.00x dmg`, `0 DT`), `AP` (`0.95x dmg`, `-15 DT`), `JHP` (`1.65x dmg`, `2.0x target DT`), `+P` (`1.25x dmg`, `-5 DT`, `1.25x wear`).
  - **Shotgun (`12ga`):** `Buckshot` (`1.20x dmg`, `1.5x target DT`), `Slug` (`1.15x dmg`, `-10 DT`, `0.45x spread`), `Flechette` (`0.95x dmg`, `-14 DT`), `Magnum` (`1.30x dmg`, `-4 DT`).
  - **Energy (`Laser`):** `Standard Cell`, `Overcharge` (`1.25x dmg`, `-10 DT`), `Optimized` (`1.30x dmg`, `-5 DT`), `Max Charge` (`1.50x dmg`, `-15 DT`).
- **Reloading Bench Hook (`#813`):** Six `COBJ` recipes (`0x830..0x835`, indexed in `FO4SF_ReloadingRecipesList` `0x836`) bind to `WorkbenchIndustrialKeyword` (`0x0AA209`) and consume `#813`'s `Starfield.esm` `IRES` salvage (`ResInorgCommonLead`, `ResInorgCommonCopper`, `ResInorgCommonIron`, `ResInorgUncommonTungsten`, `ResOrgExoticLubricant`, `ResInorgCommonUranium`), making handloads craftable at every `#813` settlement and C.A.M.P. bench.

---

## 5. Native SFSE Plugin (`sfse/FO4SFCombat`)

- Native code is restricted strictly to what Papyrus lacks on Starfield 1.16.244: **live gameplay hotkey polling (`V` for VATS, `N` for Ammo Cycle)** and main-thread zero-arg dispatch (`IVirtualMachine::DispatchStaticCall`, slot `0x2F`) to `FO4SF_CombatInput.OnVatsKey` / `FO4SF_CombatInput.OnAmmoKey`.
- Built via `sfse/FO4SFCombat/build.ps1` against pinned `libxse/commonlibsf` (`9d090c4c521f4f2c1aa00bb05923c380d47ae596` / `9fbb74d628134ab4ea3a3cf5c0ed3f7eeabbd01d`), checking `1.16.244.0` (`Refuse("version")`) and `versionlib-1-16-244-0.bin` (`format 5`) before any game call, and registered in `sfse/native_components.json`.
