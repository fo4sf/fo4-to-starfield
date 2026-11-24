# Weapon Impacts, Surface Materials, and Ash/Goo Disintegration (`FO4SFCoreValues.esm`)

Binary-verified Starfield `IPDS` / `MATT` wiring across all 25 Fallout 4 weapons (`FO4SFCoreValues.esm:0x000899..0x0008A0`, `0x0008A2..0x0008A3`, `0x0008C5..0x0008D6`), 4 explosives (`0x0008B9..0x0008BC`), Laser Ash & Plasma Goo critical spells (`0x0008C1..0x0008C4`), and robot/creature `RACE.NAM4` guidance for `#32`.

---

## 1. `Starfield.esm` Impact Data Sets (`IPDS`)

Verified directly against `Starfield.esm`:

| `Starfield.esm` FormID | EditorID | Role |
|---|---|---|
| `0x0000D02C` | `FXProjectileBulletImpactSet` | Ballistic guns (`10mm`, `Minigun`, `Pipe Pistol/Rifle`, `Pipe Revolver`, `Hunting Rifle`, `Submachine Gun`, `Assault Rifle`) |
| `0x00055DC3` | `WPNHandBladeSmall_ImpactSet` | Light melee (`Baton`) |
| `0x0005C498` | `WPNMeleeImpactBladeMediumSet` | Medium melee (`Baseball Bat`) |
| `0x00252B4C` | `WPNMeleeBashHandImpactSet` | Unarmed (`UnarmedHuman`) |
| `0x00239D0F` | `FXProjectileShotgunImpactSet` | Pump/combat shotgun (`Combat Shotgun`) |
| `0x001D7FEC` | `FXProjectileShotgunCoachmanSet` | Break-action shotgun (`Double-Barrel Shotgun`) |
| `0x001C1162` | `FXProjectileOrionLaserImpactSet` | Heavy/crank laser (`Laser Musket`, `Preston's Laser Musket`) |
| `0x001F5DA1` | `FXProjectileEquinoxLaserImpactSet` | Standard laser (`Laser Pistol`, `Laser Rifle`) |
| `0x00115BE5` | `FXProjectileFlamethrowerImpactSet` | Flame stream (`Flamer`) |
| `0x00164E05` | `FXParticlePistoltImpactSet` | Plasma pistol (`Plasma Pistol`) |
| `0x00164E03` | `FXParticletImpactSet` | Plasma rifle (`Plasma Rifle`) |
| `0x0034BE5D` | `FXProjectileBulletMagImpactSet` | Electromagnetic rail (`Gauss Rifle`) |
| `0x0015CCFD` | `FXProjectileExplosiveImpactSet` | `WEAP.WVIS` for `Frag Grenade`, `Frag Mine`, `Missile Launcher`, `Fat Man`; `EXPL.ENAM` for Missile & Fat Man |
| `0x003A5907` | `FXProjectileRocketImpactSet` | `EXPL.ENAM` for `Frag Grenade` & `Frag Mine` (matches `Starfield.esm` `fragGrenadeExplosion` `0x000E574F`) |

---

## 2. Explicit `WEAP.WVIS` (bytes `12..15`) & `EXPL.ENAM` (offset `84`)

Every weapon written by `dotnet/CoreValues/Program.cs` sets `Weapon.ImpactDataSet` explicitly (`WEAP.WVIS` bytes `12..15`, verified in binary ESM output), eliminating reliance on unverified donor templates:

| `FO4SFCoreValues.esm` | EditorID | `Fallout4.esm` Source | Donor (`Starfield.esm`) | `WEAP.WVIS[12:16]` (`IPDS`) |
|---|---|---|---|---|
| `0x000899` | `FO4_10mmPistol` | `00004822` | `XM2311` (`0024561C`) | `0x0000D02C` (`FXProjectileBulletImpactSet`) |
| `0x00089A` | `FO4_Baton` | `0008C14D` | `RescueAxe` (`0004F760`) | `0x00055DC3` (`WPNHandBladeSmall_ImpactSet`) |
| `0x00089D` | `FO4_LaserMusket` | `0001DACF` | `Orion` (`002773C8`) | `0x001C1162` (`FXProjectileOrionLaserImpactSet`) |
| `0x00089E` | `FO4_CompPrestonLaserMusket` | `00062AA6` | `Orion` (`002773C8`) | `0x001C1162` (`FXProjectileOrionLaserImpactSet`) |
| `0x0008A0` | `FO4_Minigun` | `0001F669` | `Microgun` (`000546CD`) | `0x0000D02C` (`FXProjectileBulletImpactSet`) |
| `0x0008A2` | `FO4_PipePistol` | `00024F55` | `Eon` (`000476C4`) | `0x0000D02C` (`FXProjectileBulletImpactSet`) |
| `0x0008A3` | `FO4_PipeRifle` | `00024F55` | `Beowulf` (`0004716C`) | `0x0000D02C` (`FXProjectileBulletImpactSet`) |
| `0x0008C5` | `FO4_UnarmedHuman` | `000C2C27` | `Unarmed` (`000001F4`) | `0x00252B4C` (`WPNMeleeBashHandImpactSet`) |
| `0x0008C6` | `FO4_FragGrenade` | `000EEBED` | `FragGrenade` (`000115EF`) | `0x0015CCFD` (`FXProjectileExplosiveImpactSet`) |
| `0x0008C7` | `FO4_FragMine` | `000E56C2` | `FragMine` (`0004A41A`) | `0x0015CCFD` (`FXProjectileExplosiveImpactSet`) |
| `0x0008C8` | `FO4_PipeRevolver` | `0014831B` | `Razorback` (`00000FD6`) | `0x0000D02C` (`FXProjectileBulletImpactSet`) |
| `0x0008C9` | `FO4_HuntingRifle` | `0004F46A` | `Lawgiver` (`0002D7F4`) | `0x0000D02C` (`FXProjectileBulletImpactSet`) |
| `0x0008CA` | `FO4_CombatShotgun` | `0014831C` | `Pacifier` (`002953F8`) | `0x00239D0F` (`FXProjectileShotgunImpactSet`) |
| `0x0008CB` | `FO4_DoubleBarrelShotgun` | `00092217` | `Coachman` (`0026D96B`) | `0x001D7FEC` (`FXProjectileShotgunCoachmanSet`) |
| `0x0008CC` | `FO4_SubmachineGun` | `0015B043` | `Maelstrom` (`002984DF`) | `0x0000D02C` (`FXProjectileBulletImpactSet`) |
| `0x0008CD` | `FO4_AssaultRifle` | `0000463F` | `AA99` (`002BF65B`) | `0x0000D02C` (`FXProjectileBulletImpactSet`) |
| `0x0008CE` | `FO4_LaserPistol` | `0009983B` | `Solstice` (`0026D961`) | `0x001F5DA1` (`FXProjectileEquinoxLaserImpactSet`) |
| `0x0008CF` | `FO4_LaserRifle` | `0009983B` | `Equinox` (`0001BC4F`) | `0x001F5DA1` (`FXProjectileEquinoxLaserImpactSet`) |
| `0x0008D0` | `FO4_BaseballBat` | `0008E736` | `RescueAxe` (`0004F760`) | `0x0005C498` (`WPNMeleeImpactBladeMediumSet`) |
| `0x0008D1` | `FO4_MissileLauncher` | `0003F6F8` | `Bridger` (`0026D96A`) | `0x0015CCFD` (`FXProjectileExplosiveImpactSet`) |
| `0x0008D2` | `FO4_FatMan` | `000BD56F` | `Bridger` (`0026D96A`) | `0x0015CCFD` (`FXProjectileExplosiveImpactSet`) |
| `0x0008D3` | `FO4_Flamer` | `000E5881` | `ArcWelder` (`0026D965`) | `0x00115BE5` (`FXProjectileFlamethrowerImpactSet`) |
| `0x0008D4` | `FO4_PlasmaPistol` | `00100AE9` | `Novalight` (`0026D967`) | `0x00164E05` (`FXParticlePistoltImpactSet`) |
| `0x0008D5` | `FO4_PlasmaRifle` | `00100AE9` | `Va'ruun Inflictor` (`0026D8A0`) | `0x00164E03` (`FXParticletImpactSet`) |
| `0x0008D6` | `FO4_GaussRifle` | `000D1EB0` | `Magsniper` (`0002EB45`) | `0x0034BE5D` (`FXProjectileBulletMagImpactSet`) |

### `EXPL.ENAM` Offset `84` (Radii Converted FO4 Units -> Starfield Meters `/ 70.0`)

| `FO4SFCoreValues.esm` | EditorID | Damage | Inner / Outer / IS Radius (m) | `EXPL.ENAM[84:88]` (`IPDS`) |
|---|---|---:|---|---|
| `0x0008B9` | `FO4_FragGrenadeExplosion` | `150` | `2.14 / 7.14 / 14.30` | `0x003A5907` (`FXProjectileRocketImpactSet`) |
| `0x0008BA` | `FO4_FragMineExplosion` | `100` | `1.43 / 7.14 / 11.00` | `0x003A5907` (`FXProjectileRocketImpactSet`) |
| `0x0008BB` | `FO4_MissileExplosion` | `135` | `2.14 / 7.14 / 28.60` | `0x0015CCFD` (`FXProjectileExplosiveImpactSet`) |
| `0x0008BC` | `FO4_FatManExplosion` | `450` | `4.29 / 12.14 / 60.00` | `0x0015CCFD` (`FXProjectileExplosiveImpactSet`) |

---

## 3. Actor Surface Materials (`RACE.NAM4 -> MATT`)

- **Owned Power Armor race only:** `FO4SFPowerArmor.esm:0x000802` (`FO4SF_PowerArmorRace`) writes `RACE.NAM4 = 0x0009150B` (`MaterialActorMetalLarge`, verified on `Starfield.esm` `ModelARace` `0x00005629`).
- **Never override `Starfield.esm` `HumanRace` (`0x0000347D`):** already carries `NAM4 = 0x00022954` (`MaterialActorSkin`, identical to `Fallout4.esm` `HumanRace` `0x00013746 -> 0x00022954`).

### Exact FO4 Actor Material -> Starfield `MATT` Table (for Claude `#32` Robot & Creature Races)

Verified against `Fallout4.esm` `RACE.NAM4 -> MATT` and `Starfield.esm` `MATT` / `RACE.NAM4`:

| `Fallout4.esm` `MATT` (`RACE.NAM4`) | FO4 Races Using It | Recommended `Starfield.esm` `MATT` | `Starfield.esm` Reference Race | Notes |
|---|---|---|---|---|
| `0x00022954` `MaterialActorSkin` | `HumanRace` (`00013746`), `GhoulRace`, `FeralGhoulRace`, `SuperMutantRace`, `MoleratRace`, `DogmeatRace`, `YaoGuaiRace`, `BrahminRace`, `RadStagRace` | `0x00022954` `MaterialActorSkin` | `HumanRace` (`0x0000347D`) | Shared FormID between FO4 and Starfield; keep `HumanRace` unedited |
| `0x00022955` `MaterialActorMetal` | `HandyRace` (`000359F4`), `ProtectronRace` (`000DFB33`), `EyeBotRace` (`000A563A`), `LibertyPrimeRace` (`00108019`), `TurretWorkshopRace` (`001A6D64`) | `0x00022955` `MaterialActorMetal` (or `0x000223D1` `Material_Metal` for static workshop turrets) | `ModelSRace` (`0x000130F0`), `ModelTRace` (`0x00045F14`), `MiniBotARace` (`0x00227705`); `BallisticTurretRace` (`0x001CC9BC`) | Shared ID `0x00022955`; matches metallic bullet/laser sparks |
| `0x00056A9B` `MaterialActorMetalArmored` | `AssaultronRace` (`000D8417`), `SentryBotRace` (`000AE0B7`), `VertibirdRace` (`000D77E3`), `TurretBubbleRace` (`000B28D3`), `TurretTripodRace` (`000B1F08`) | `0x0009150B` `MaterialActorMetalLarge` (mobile heavy bots) / `0x000223D1` `Material_Metal` (turrets) | `ModelARace` (`0x00005629`), `BallisticTurretRace` (`0x001CC9BC`), `LaserTurretRace` (`0x001EA1DB`) | Heavy armor metallic impact sparks/ricochets |
| `0x0007646B` `MaterialActorMetalArmoredPower` | `PowerArmorRace` (`0001D31E`) | `0x0009150B` `MaterialActorMetalLarge` | `ModelARace` (`0x00005629`) | Assigned ONLY on owned `FO4SF_PowerArmorRace` (`0x0802`) |
| `0x0016BADA` `MaterialActorSynthGen1` | `SynthGen1Race` (`000E8D09`), `SynthGen2Race` (`0010BD65`), `SynthGen2RaceValentine` (`002261A4`) | `0x00022955` `MaterialActorMetal` (Gen 1/2 chassis) or `0x000F7B65` `MaterialActorSkeleton` | `ModelSRace` (`0x000130F0`), `HumanCorpseRace` (`0x00034FB1`) | Exposed synthetic polymers/alloy frame; Gen 3 uses `0x00022954` |
| `0x00022956` `MaterialActorInsect` | `RadRoachRace` (`0004716C`), `BloatflyRace` (`00029463`), `BloodbugRace` (`0002456D`), `StingwingRace` (`0005FBB1`), `AlienRace` (`00184C4D`) | `0x00022956` `MaterialActorInsect` | `CritterRace` (`0x000176B6`) | Identical FormID `0x00022956` in Starfield! |
| `0x0002295A` `MaterialActorMetalArmoredCrab` | `MirelurkRace` (`00023FFC`), `MirelurkHunterRace` (`00064C60`), `MirelurkKingRace` (`000B7F91`), `MirelurkQueenRace` (`000E12A6`), `RadScorpionRace` (`000636AB`) | `0x00038A6C` `MaterialActorCreatureGenericMedium` (chitin body) or `0x002801BF` `MaterialActorCreatureTerrormorphA` (heavy armored carapace) | `QuadrupedARace` (`0x00050301`), `TerrormorphRace` (`0x0021A8D7`) | Armored crustacean/arachnid shell |
| `0x000C1AD7` `MaterialActorSkinLarge` | `DeathclawRace` (`0001DB4A`), `SupermutantBehemothRace` (`000BB7D9`), `GorillaRace` (`000D9804`) | `0x000C1AD7` `MaterialActorSkinLarge` (or `0x002801BF` `MaterialActorCreatureTerrormorphA` for Deathclaw hide) | `TerrormorphRace` (`0x0021A8D7`) | `0x000C1AD7` exists in `Starfield.esm` |
| `0x001C756F` `MaterialActorGlowing` | `FeralGhoulGlowingRace` (`000A96BF`) | `0x00022954` `MaterialActorSkin` | `HumanRace` (`0x0000347D`) | Bioluminescent flesh; Starfield drops `0x001C756F` |

---

## 4. Laser Ash & Plasma Goo Critical Disintegration

- **Laser route (`FO4_CritLaser` `FO4SFCoreValues.esm:0x0008C4`):**
  - Duplicates `Starfield.esm` `Crit_LaserWeapDisintegrateSpell` (`0x0024EF1F`, `Mag=10, Area=0, Dur=10` matching FO4 `CritLaser` `0x000731B2`) targeting `Starfield.esm` `CritLaserEffect` (`MGEF 0x0024EF20`).
  - `CritLaserEffect` runs vanilla `AttachAshPile` (`AshPileObject` = `DefaultAshPile1` `0x0000001B` / `AshPile01` `0x0009142E` carrying `IsAshpile` `0x0018FB4B`, shader `CritLaserDisintegration` `0x0026319B`), and honors `NoDisintegrate` (`KYWD 0x0022DB8F`) via its preserved `CTDA` conditions.
  - Bound (`CritEffectOnDeathOnly = true`) on `FO4_LaserMusket` (`0x00089D`), `FO4_CompPrestonLaserMusket` (`0x00089E`), `FO4_LaserPistol` (`0x0008CE`), `FO4_LaserRifle` (`0x0008CF`).
- **Plasma route (`FO4_GooPile01` `0x0008C1`, `FO4_CritPlasmaEffect` `0x0008C2`, `FO4_CritPlasma` `0x0008C3`):**
  - `FO4_GooPile01` (`ACTI 0x0008C1`) duplicates `AshPile01` (`0x0009142E`, retaining `IsAshpile` `0x0018FB4B`) with converted `Fallout4.esm` `GooPile01` (`0x00139F8D`) mesh `fo4core\effects\ashpileplasmagoo.nif`.
  - `FO4_CritPlasmaEffect` (`MGEF 0x0008C2`) duplicates `CritLaserEffect` (`0x0024EF20`), keeps the `NoDisintegrate` (`0x0022DB8F`) condition check, and retargets `VMAD` `AttachAshPile.AshPileObject` to `FO4_GooPile01` (`0x0008C1`).
  - `FO4_CritPlasma` (`SPEL 0x0008C3`) uses `FO4_CritPlasmaEffect` (`Mag=10, Area=0, Dur=10` per FO4 `CritPlasma` `0x00139F8C` / `CritPlasmaEffect` `0x00139F8B`) and is bound (`CritEffectOnDeathOnly = true`) on `FO4_PlasmaPistol` (`0x0008D4`) and `FO4_PlasmaRifle` (`0x0008D5`).
