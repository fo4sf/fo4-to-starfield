Titles: Fallout 4 | Modes: Story & Warfare | Track: Round 13 Probe P6b (Full Arsenal Rows 1-20, OMODs, Tracked Bones, Impacts, Ash & Goo)

# Round 12 / 13 Test Card — Probe P6b (`r12-p6b`, supersedes `r11-p6-arsenal`)

> **NEW GAME needed (`A16` / `R15`) & Scope / Honesty Banner:**
> - **Scope:** `r12-p6b` (Combat Plan Rows 1–20, `X3` shared `probe_common` prefix stamper, `P6-H1` default OMOD damage/capacity, `P6-H2` blunt melee `WVIS`, `P6-H3` `Gun_*.af` tracked moving bones, `P6-M1` Missile Launcher forward orientation, `OnDying` `GetEquippedWeapon()`, deterministic `bat p6x` goo/ash toggle, `bat p6d` god-mode batch, and moved `WoodTarget` `>= 1.8 m` from chair) | **Mode:** Both (`Warfare` & `Story`) | **Baseline Target:** `candidate-2g-fix4` `player` profile (`test`-profile baseline refused unless `--allow-test-baseline` is passed)
> - **Version Tag:** `r12-p6b-v1`
> - **Stage Placeholders:** `<probes-root>/r12-p6b`, `<starfield-dir>`
> - **Preconditions:** `Starfield.exe` closed; `>= 60.0 GiB` free disk space; start on clean `candidate-2g-fix4` (`player` profile, Bridge off, prior probes uninstalled); **`P6-00..P6-24` require interior `FO4Port_Vault111Cryo`**, **`P6-25` starts from the exterior Sanctuary workbench reached via the candidate's Vault 111 exit**.
> - **Overridden Candidate Files & NIFs (`P6-M2`):** Replaces `Data/FO4SFCoreValues.esm` (`FO4SF_TestModeEnabled=0`; overrides `FO4SF_Stimpak 0x000851` weight `0.1`, value `75 -> 48`, mesh `fo4core\props\stimpack01.nif`) **plus 14 existing candidate NIFs** under `Data/meshes/fo4core/` via `FO4SF_R11P6Arsenal - Main.ba2`: `10mmammo.nif`, `308ammo.nif`, `38ammo.nif`, `45ammo.nif`, `556ammo.nif`, `5mmammo.nif`, `ammofatman.nif`, `flamerfuel.nif`, `microfusioncell.nif`, `missile.nif`, `shotgunshellammo.nif`, `bobbypin.nif`, `bottlecapsingle.nif`, and `stimpack01.nif`. (`FO4SFPipboyMenu.dll` `7d5ba49c` left untouched unless `--ship-pipboy-dll` is passed.)
> - **Truth & Stand-In Policy (`R8` / `R15` / `#32` Owner Direction):** Current `r12-p6b` package is **`OFFLINE VERIFIED — PENDING RE-TEST IN GAME`**. Prior build (`r11-p6-arsenal` at `1b93113b`) ran partially on 24 Nov (`07:11Z-07:19Z` on `candidate-2g-fix2` with manual slot `11`, logs only, zero video), confirming `init 23/13`, `grant_all 23/23`, FO4 `FULL` equip names, `10mm` 12-rd mag + `NoDisintegrate` intact body, `LaserPistol` ash pile, and `PlasmaPistol` green-tube model (`30|30`), while exposing `X3` (`15` vs `11`), stale `eq=FragMine`, no goo on 1 plasma kill, dropped OMODs (`P6-H1`), bladed baton/bat `WVIS` (`P6-H2`), unmapped moving bones (`P6-H3`), and Missile Launcher orientation (`P6-M1`). All weapon anims/audio, `ArcWelder` heavy-grip Flamer, `LaserBeamProjectile` (`0x000A0F51`) Flamer/Plasma ammo stand-in, Fat Man `EXPL` `IS Radius=60 m` / donor `Force=150`, and Starfield UI/HUD screens (weapon inspect, ammo HUD) remain labelled **stand-ins** (Starfield UI stand-ins judged on function until Fallout UI lands).

---

## Staged Artifacts & Baseline Verification (`r12-p6b`)

`manifest.json` SHA-256: `580da3e138786dbefc36efdb68ca588d79c0da7736713c9de12a0917ae692fdb` (`682` verified files, `48` placed refs; `--clean` staged against `candidate-2g-fix3` `FO4ActorRaider.esm` + `FO4Port.esm`).

| Artifact (`Data/...`) | Source / Reuse Status | Expected Size | Expected SHA-256 | Notes |
|---|---|---|---|---|
| `Data/FO4SFCoreValues.esm` | Rebuilt `--fo4-arsenal 1` (`st_nlink == 1` copied) | `76,995` B | `5b788a97006cc5e3d97847f9ca6b35a5567d380404356c75b3a8c05e0ff9cb5c` | `0` `FO4Core_Commonwealth` overrides; adds `P6-H1` OMOD dmg/cap & `P6-H2` blunt `0x000116F1` `WVIS`; updates `FO4SF_Stimpak 0x000851` (`val=48`) |
| `Data/FO4SF_R11P6Arsenal.esm` | Built for `r12-p6b` (`st_nlink == 1` copied) | `7,649` B | `bdcb395a24d5bec41d49a491230cd961a30cf4345a8c423865fcee966ee06279` | Vault111Cryo 3-table rack, 23 weapons, 13 ammos, 3 props, 5 targets (`WoodTarget` at `(-45.55, 28.10, 0.01)`, `2.10 m` clear of folding chair), QUST `0x000830` w/ `INDX 25` & `CritPlasmaSpell`/`CritLaserSpell` |
| `Data/FO4SF_R11P6Arsenal - Main.ba2` | Packed GNRL (`pack_gnrl_ba2`, `BS CRC32` verified) | `4,318,794` B | `bf82fc9d0bd6dfea89113142bd5f4cd628804483fbec09fc946b3511f4c91f81` | `373` GNRL entries: `23` `Gun_*.af`-tracked weapon NIFs (`missilelauncher` `ProjectileNode.y=+0.5458 m`), `13` ammo NIFs (11 candidate overrides), `4` core NIFs (3 candidate overrides + `ashpileplasmagoo.nif`), `2` proj NIFs, controller JSONs, `.mesh`, `.mat`, `FO4SF_R11P6Quest.pex` |
| `Data/FO4SF_R11P6Arsenal - Textures.ba2` | Packed DX10 (`pack_dx10_ba2`, `BS CRC32` verified) | `392,297,647` B | `62792bfb52a13d56fbb18ea684426aa102e77cf4eb791bd5e8cc65d453d33eb0` | `293` BC1/BC4/BC5/DX10 `.dds` textures |
| `Data/SFSE/Plugins/FO4SFPipboyMenu.dll` | Preserved untouched on installed candidate (`7d5ba49c`) | `1,453,568` B | `7d5ba49c0c6ab2aa...` | Untouched unless `--ship-pipboy-dll --tested-pipboy-dll <path>` is passed |

---

## OMOD Stat Formula & Type Rounding Rule (`P6-H1`)

- Every base weapon `WEAP` (`Fallout4.esm`) is evaluated with its default `ObjectTemplate[0]` OMODs (`[2]` Rifle variants for Pipe Rifle / Laser Rifle / Plasma Rifle) using additive multiplier `base * (1 + sum(add_pct))`:
  - **`SF.Weapon.AttackDamage` (`WDMG` subrecord):** IEEE `float32` exact value. Only `FO4_SubmachineGun` (`0015B043`) changes physical damage in default mods: `0015B044` (`mod_SubmachineGun_Receiver_Automatic1`, `AttackDamage = -0.25`) -> `13 * (1 - 0.25) = 9.75f` (stored exact `9.75` IEEE float32).
  - **`SF.Weapon.AmmoCapacity` (`WAM2` `uint32`):** Unsigned integer rounded `MidpointRounding.AwayFromZero`:
    - `FO4_AssaultRifle` (`0000463F`) + `0018896B` (`mod_AssaultRifle_Mag_Medium`, `AmmoCapacity = +0.50`) -> `20 * 1.50 = 30` exact.
    - `FO4_LaserRifle` (`0009983B`) + `00091FB5` (`mod_LaserGun_BarrelLaser_Long_A`, `AmmoCapacity = -0.10`) -> `30 * 0.90 = 27` exact.
    - `FO4_GaussRifle` (`000D1EB0`) + `001AC252` (`mod_GaussRifle_GaussMag_Medium`, `AmmoCapacity = +0.50`) -> `5 * 1.50 = 7.5` -> **`8`** (`MidpointRounding.AwayFromZero`).
  - **`SF.Weapon.DamageTypes` (`DAMA`, `dtEnergy 0x00060A81` `uint16`):** Unsigned 16-bit integer rounded `MidpointRounding.AwayFromZero`:
    - `FO4_LaserRifle` (`0009983B`) + `00091FB5` (`mod_LaserGun_BarrelLaser_Long_A`, `dtEnergy = +0.096`) -> `24 * 1.096 = 26.304` -> **`26`**.
  - All other 19 weapons carry `0.0` default OMOD deltas on `AttackDamage`/`dtEnergy`/`AmmoCapacity` (weight/value already match default OMODs on all 20 rows).

---

## `P3` Console, Batch & Interior vs Exterior Rules (`P6-M4`, `P6-M5`, `X3`)

1. Batch filenames (`p6r`, `p6t`, `p6a`, `p6g`, `p6c`, `p6d`, `p6x`, `p6h1`, `p6e`, `p6s`, `p6q`) and typed ```` ```console ```` / `bat <stem>` commands contain **zero `m`, `n`, or `v` letters** and **zero stripped `FO4SF_*` EditorIDs**.
2. **`p6r` / `p6t` / `p6a` are INTERIOR-ONLY (`FO4Port_Vault111Cryo`):** Never run them outside in the Commonwealth (`~2,300 m` mismatch jump).
3. **`p6h1` / `p6e` are EXTERIOR-ONLY (`P6-25`):** Always start `P6-25` from the exterior Sanctuary workbench (`-2329.25, -1420.19, 112.09`, reached via the candidate's Vault 111 exit) before calling `bat p6h1` (`dX=-70.75 m`) -> `bat p6e` (`dX=-67.78 m`).
4. **Explosives in `11 m` Room (`P6-M5`):** Run `bat p6d` (`tgm` toggle) before firing `FragGrenade`, `FragMine`, `Missile Launcher`, or `Fat Man` (`450` dmg, `12.14 m` outer radius vs `4-5 m` target range).
5. **Deterministic Goo / Ash Toggle (`bat p6x`):** Calls `SetStage <XX>000830 25` to toggle `forceCritDisint`; when enabled, Laser/Plasma kills cast `CritLaserSpell`/`CritPlasmaSpell` unless `NoDisintegrate` (`0x0022DB8F`) is present.
6. **`X3` Prefix Stamping:** `install` calls `probe_common.stamp_batch_formid_prefix` counting existing non-`FE`/non-`FD` `IMPLICIT_FULL_MASTERS` and `*`-active existing plugins (`0x11` on 24 Nov Bridge-off load order).

---

## Verification Rows (Every Row Carries `VIDEO` — Rule 10: `audio: not judged`; `1 fps` / Slowed Take Policy)

### A. Range Infrastructure, `P5` Fixes (`F1`–`F6`) & `Rows 1–20` Weapon Rack

| Row | Weapon (`CoreValues` & FO4 Source, AP Cost, Default OMODs) | Donor (`Starfield.esm`), Retained KWs (`KWDA`), & `.af` Track Map (`fo4_part_map`) | Batch / Expected Stats & `WVIS` Impact | Stand-In / Truth | Result (`r12-p6b`) | VIDEO |
|---|---|---|---|---|---|---|
| `P6-00` | **Quest Init, 3-Table Rack & `F4` Bounds** (`0x000810..0x000840`) | Quest `FO4SF_R11P6Quest` `0x000830`; `WoodTarget` at `(-45.55, 28.10, 0.01)` (`2.10 m >= 1.8 m` from chair `0x01001441`) | `bat p6r` + `bat p6t` (**interior-only**); `init weapons=23 ammos=13`; `48/48` placed refs (`minigun` `world_min_z=+0.830 m > 0.825 m`) | `24 Nov 1b93113b`: `init`+`grant_all`+`23/23` PASS; `r12-p6b` pending | `PENDING` | `needed: 1 fps clip sweeping Rack 1 (p6r) and Tables 2-3 (p6a) showing guns above tabletops and Wood crate clear of chair; audio: not judged` |
| `P6-01` | **Row 1: `Baton`** (`0x00089A`, FO4 `0008C14D`, AP `30`, OMOD: none) | `RescueAxe` `0004F760`; KWs (`7`): `000143AA, 00230326, 00244895, 000F4AEA, 000245A3, 002811D0, 0004A0A4` (stripped `ModAssocRescueAxe`); `+Z` shaft (`BatonLowHandle`, `WeaponExtra1->BatonLowExt01`, `WeaponExtra2->BatonLowExt02`), blood skipped | `bat p6r` -> `bat p6c`; `11` melee dmg, reach `0.80`, wt `2.0`, val `15`; **`WVIS=0x000116F1`** (`WPNMeleeBashGunSmallImpactSet`, `P6-H2` blunt) | `RescueAxe` melee anim/audio stand-in (`OFFLINE VERIFIED`) | `PENDING` | `needed: 1 fps + slowed swing take hitting FleshDummy & WoodTarget confirming blunt sparks/no blood blade marks; audio: not judged` |
| `P6-02` | **Row 2: `10mm Pistol`** (`0x000899`, FO4 `00004822`, AP `28`, OMODs `00091FC4, 000231AB, 00100E27, 00091FC2, 00148409`) | `XM2311` `0024561C`; KWs (`12`): `0000E6C5, 0019A60E, 000FAEBF, 000F4AEA, 0010C485, 0002459D, 0026BA10, 0003ADB3, 00092A86, 002811CA, 0004A0A0, 0002B714`; `xm2311` `.af`: `MiscA06` (`WeaponBolt`), `Magazine`, `TRIGGER`, `MiscA01` (`WeaponExtra1`), `MiscA02` (`WeaponExtra2` hammer), `MiscA03` (`WeaponExtra3`) | `bat p6r` -> `bat p6c`; `18` dmg, `12`-rd cap (`0.2143 s`), wt `3.525`, val `51`, `+ 10mm Round` (`0x000898`); `WVIS=0x0000D02C` | `24 Nov` 1stP model & `12 / 36` mag PASS (`1b93113b`); `XM2311` anim/coll stand-in | `PENDING` | `needed: slowed 1stP fire+reload take checking hammer MiscA02 & slide MiscA06 motion (`1 fps` misses rapid blowback); audio: not judged` |
| `P6-03` | **Row 3: `Laser Musket`** (`0x00089D`, `0001DACF` + Preston `0x00089E`, `00062AA6`, AP `30`, OMODs `0002C0D3, 0002BF01, 000ECE69, 0002BF04`) | `Orion` `002773C8`; KWs (`13`/`14`): `00042AD4, 002773C7, 000FAEC0..0004A0A1` (`+ 0023F1CA` Preston); `orion` `.af`: `Magazine` (`WeaponMagazine` crank), `TRIGGER`, `MiscA01..03` (`WeaponExtra1..3`); `ProjectileNode (0,0.935,0.079)` m | `bat p6r` -> `bat p6c`; `0` phys + `30` `dtEnergy` (`18` Preston, val `195`), `2` cap, `0.667 s`, wt `12.6`, val `61`; `WVIS=0x001C1162` | `Orion` anim/`0.667s` rate stand-in (`OFFLINE VERIFIED`) | `PENDING` | `needed: 1 fps muzzle alignment + slowed crank/trigger fire take watching Magazine crank & rotor MiscA02; audio: not judged` |
| `P6-04` | **Row 4: `Minigun`** (`0x0008A0`, FO4 `0001F669`, AP `30`, OMODs `00121D53, 00188A05`) | `Microgun` `000546CD`; KWs (`15`): `00016759, 001C4C33, 00103805..0002B714`; `microgun` `.af`: `MiscA01`->`BarrelRoot`->`Minigun_Barrel`, `Magazine`->`Minigun_AmmoDrum`; 23 FO4 ctrl blocks saved | `bat p6r` -> `bat p6c`; `8` dmg, `500`-rd drum, speed `3.0`, wt `27.45`, val `383` (`+ 5mm 0x00089F`); `WVIS=0x0000D02C` | `Microgun` rate/anim stand-in (`24 Nov` not run) | `PENDING` | `needed: slowed burst take showing barrel cluster spin (`MiscA01`) & brass/recoil (`1 fps` cannot judge spin rate); audio: not judged` |
| `P6-05` | **Row 5: `Pipe Pistol` (`0x0008A2`) & `Pipe Rifle` (`0x0008A3`)** (`00024F55`, AP `30`, OMODs Pistol `0003ADB6,00024F07,00024F0E,000BB017,0014840B`, Rifle `0004A095,00024007`) | `Eon` `000476C4` (`12` KWs `0000E6C5, 000476C5..`) & `Beowulf` `0004716C` (`13` KWs `0004AABF, 00015EAD..`); `eon` `.af`: `MiscB01..03, Magazine, TRIGGER`; `beowulf` `.af`: `MiscA..02, Magazine, TRIGGER` | `bat p6r` -> `bat p6c`; `13` dmg, `12` cap, `0.18 s`, wt `2.35`/`3.40`, val `23`/`28` (`+ .38 0x0008A1`); `WVIS=0x0000D02C` | `Eon`/`Beowulf` anim/coll stand-in (`OFFLINE VERIFIED`) | `PENDING` | `needed: 1 fps 1stP/3rdP silhouettes + slowed fire take watching bolt `MiscB01`/`MiscA` cycle; audio: not judged` |
| `P6-06` | **Row 6: `Unarmed`** (`0x0008C5`, `000C2C27`, AP `20`, `NonPlayable`) | `Unarmed` `000001F4`; KWs (`6`): `0002405E, 00230326, 001283C9, 001283CA, 000245A3, 0005240E` | Binary + unarmed dummy check; `8` dmg, reach `0.68`, `WVIS=0x00252B4C` | Starfield `Unarmed` donor anim/coll (`OFFLINE VERIFIED`) | `PENDING` | `needed: optional 1 fps bare-hand punch check if exercised; ESM verified offline; audio: not judged` |
| `P6-07` | **Row 7: `Frag Grenade`** (`0x0008C6`, `000EEBED`, AP `20`) + `PROJ 0x0008BD` + `EXPL 0x0008B9` | `FragGrenade` `000115EF`; KWs (`6`): `00012345, 0010C415, 000F4AEA, 001CC46A, 0004C922, 0004A0A6`; `GrenadeFrag` | **`bat p6d` (`tgm`)** -> `bat p6a` -> `bat p6c`; `150` `EXPL` (`2.14 / 7.14 / 14.3 m`, **donor `Force=120.0`**), `ENAM=0x003A5907`, `WVIS=0x0015CCFD` | `FragGrenade` anim & donor `Force=120` stand-in (`24 Nov` not run) | `PENDING` | `needed: 1 fps / slowed throw clip showing grenade arc & blast on room floor under tgm; audio: not judged` |
| `P6-08` | **Row 8: `Frag Mine`** (`0x0008C7`, `000E56C2`, AP `20`) + `PROJ 0x0008BE` + `EXPL 0x0008BA` | `FragMine` `0004A41A`; KWs (`6`): `000E56C4, 0010C415, 000F4AEA, 001CC46A, 0004C922, 0010C414`; `TestMine` | **`bat p6d` (`tgm`)** -> `bat p6a` -> `bat p6c`; `100` `EXPL` (`1.43 / 7.14 / 11.0 m`, **donor `Force=120.0`**), `ENAM=0x003A5907`, `WVIS=0x0015CCFD` | `FragMine` anim & donor `Force=120` stand-in (`24 Nov` not run) | `PENDING` | `needed: 1 fps clip showing mine deploy + detonation near FleshDummy under tgm; audio: not judged` |
| `P6-09` | **Row 9: `Pipe Revolver`** (`0x0008C8`, `0014831B`, AP `35`, OMODs `00148365, 001483BA, 001483A3, 00148414`) | `Razorback` `00000FD6`; KWs (`13`): `0000E6C5, 002B3F83..`; `razorback` `.af`: `Bolt`, `Magazine`, `Magazine01..03` (`WeaponMagazineChild1..3`), `MiscA01` (`WeaponExtra1`), `TRIGGER` | `bat p6a` -> `bat p6c`; `24` dmg, `6` cap, `0.15 s`, wt `4.30`, val `28` (`+ .45 0x0008B1`); `WVIS=0x0000D02C` | `Razorback` anim stand-in (`OFFLINE VERIFIED`) | `PENDING` | `needed: 1 fps silhouette + slowed hammer/cylinder fire+reload take (`MiscA01`/`Magazine01`); audio: not judged` |
| `P6-10` | **Row 10: `Hunting Rifle`** (`0x0008C9`, `0004F46A`, AP `28`, OMODs `000498A2, 0004F46B, 0004F474, 0004F46E, 0005D4D8, 00148418`) | `Lawgiver` `0002D7F4`; KWs (`14`): `00015EAD, 000476C8..`; `lawgiver` `.af`: `MiscA`, `Magazine`, `TRIGGER` | `bat p6a` -> `bat p6c`; `37` dmg, `5` cap, speed `1.25`, wt `9.60`, val `55` (`+ .308 0x0008B0`); `WVIS=0x0000D02C` | `Lawgiver` anim stand-in (`OFFLINE VERIFIED`) | `PENDING` | `needed: 1 fps ADS sight check + slowed bolt-action shot take (`MiscA`); audio: not judged` |
| `P6-11` | **Row 11: `Combat Shotgun`** (`0x0008CA`, `0014831C`, AP `35`, OMODs `000498A1, 000A7678, 001483AB, 001483C0, 000A7682, 000DF42F`) | `Pacifier` `002953F8`; KWs (`12`): `00015EAD, 00268C6F..`; `pacifier` `.af`: `Bolt`, `Magazine` | `bat p6a` -> `bat p6c`; `50` dmg, `8` cap, `0.50 s`, wt `11.20`, val `89` (`+ Shell 0x0008B2`); `WVIS=0x00239D0F` | `Pacifier` anim stand-in (`OFFLINE VERIFIED`) | `PENDING` | `needed: 1 fps pellet spread wall/target impact + slowed bolt reciprocation (`Bolt`); audio: not judged` |
| `P6-12` | **Row 12: `Double-Barrel Shotgun`** (`0x0008CB`, `00092217`, AP `30`, OMODs `000498A1, 00149CA9, 00149CA4, 00149CA7, 001C6F35`) | `Coachman` `0026D96B`; KWs (`14`): `001C4C36, 00015EAD..`; `coachman` `.af`: `MiscA` (`Shotgun_Barrel_Medium`), `MiscA01..03` (`WeaponExtra1`, `Child1..2`), `TRIGGER` | `bat p6a` -> `bat p6c`; `45` dmg, `2` cap, `0.275 s`, wt `9.00`, val `41`; `WVIS=0x001D7FEC` | `Coachman` anim stand-in (`OFFLINE VERIFIED`) | `PENDING` | `needed: slowed 2-shot reload take verifying break barrel (`MiscA`) & shells (`MiscA02/03`); audio: not judged` |
| `P6-13` | **Row 13: `Submachine Gun`** (`0x0008CC`, `0015B043`, AP `35`, OMODs **`0015B044`**, `00188A67, 0015B045, 0015B047, 001CA8D2`) | `Maelstrom` `002984DF`; KWs (`14`): `00015EAD, 0029C65D..`; `maelstrom` `.af`: `Bolt`, `Magazine`, `TRIGGER` | `bat p6a` -> `bat p6c`; **`9.75` dmg (`P6-H1` exact float32: `13 * 0.75` via `0015B044`)**, `50` cap, spd `1.40`, wt `12.775`, val `110`; `WVIS=0x0000D02C` | `Maelstrom` anim stand-in (`OFFLINE VERIFIED`) | `PENDING` | `needed: 1 fps UI inspect showing dmg=10/9.75 + slowed burst take checking `Bolt` motion; audio: not judged` |
| `P6-14` | **Row 14: `Assault Rifle`** (`0x0008CD`, `0000463F`, AP `32`, OMODs `001C6F4C, 00129DC0, 00129DC2`, **`0018896B`**, `00129DC3`) | `AA99` `002BF65B`; KWs (`14`): `002A9DEA, 0001EC33..`; `aa99` `.af`: `Magazine`, `MiscA01` (`WeaponExtra1` carry handle) | `bat p6a` -> `bat p6c`; `30` dmg, **`30` cap (`P6-H1` `20 * 1.50` exact via `0018896B`)**, `0.25 s`, wt `13.20`, val `145`; `WVIS=0x0000D02C` | `AA99` anim stand-in (`OFFLINE VERIFIED`) | `PENDING` | `needed: 1 fps HUD ammo readout `30 / ...` + slowed reload/fire take (`Magazine`); audio: not judged` |
| `P6-15` | **Row 15: `Laser Pistol` (`0x0008CE`) & `Laser Rifle` (`0x0008CF`)** (`0009983B`, AP `25`, Pistol `0012ECED,0009983D,00099836,001877FA`; Rifle **`00091FB5`**`,00091FB7`) | `Solstice` `0026D961` (`13` KWs; `MiscA..03` w/ `CSlide->MiscA03`, `Magazine`) & `Equinox` `0001BC4F` (`14` KWs; `MiscB`, `MiscA01..02`, `Magazine`) | `bat p6a` -> `bat p6c`; Pistol `24` `dtEnergy`, `30` cap; **Rifle `26` `dtEnergy` (`24*1.096=26.304->26` ushort) & `27` cap (`30*0.9` via `00091FB5`, `P6-H1`)**; `WVIS=0x001F5DA1`, `Crit=0x0008C4` | `Solstice`/`Equinox` anim stand-in (`24 Nov` `LaserPistol` ash & `30` cell PASS) | `PENDING` | `needed: 1 fps HUD showing Laser Rifle `27 / ...` + slowed beam fire/bolt (`MiscA`/`MiscB`) clip; audio: not judged` |
| `P6-16` | **Row 16: `Baseball Bat`** (`0x0008D0`, FO4 `0008E736`, AP `35`, OMOD `001A0352`) | `RescueAxe` `0004F760`; KWs (`7`): `000143AA, 00230326..`; `+Z` mesh `BaseballBat`, `Mod_Grip_Leather` | `bat p6a` -> `bat p6c`; `16` dmg, reach `0.80`, wt `3.00`, val `25`; **`WVIS=0x000116F1`** (`WPNMeleeBashGunSmallImpactSet`, `P6-H2` blunt) | `RescueAxe` melee anim/audio stand-in (`OFFLINE VERIFIED`) | `PENDING` | `needed: 1 fps grip orientation + slowed swing hitting WoodTarget/FleshDummy confirming blunt impact; audio: not judged` |
| `P6-17` | **Row 17: `Missile Launcher`** (`0x0008D1`, `0003F6F8`, AP `45`, OMODs `00170374, 000A2D77`) + `PROJ 0x0008BF` + `EXPL 0x0008BB` | `Bridger` `0026D96A`; KWs (`13`): `00255D9C, 00042AD4..`; `bridger` `.af`: `TRIGGER`, `MiscA` (`WeaponExtra2`), `MiscA01` (`CBarrelPivot`), `Bolt` (`CBarrelHandle`), `Magazine01` (`CMissile`); **`P6-M1` forward `+Y` (`ProjectileNode y=+0.5458 m`)** | **`bat p6d` (`tgm`)** -> `bat p6a` -> `bat p6c`; `15` impact + `135` `EXPL` (`2.14 / 7.14 / 28.6 m`, **donor `Force=120.0`**), `1` cap, wt `21.00`, val `315`; `WVIS=0x0015CCFD` | `Bridger` anim & donor `Force=120` stand-in (`24 Nov` not run) | `PENDING` | `needed: 1 fps muzzle-forward silhouette + fire clip proving forward rocket flight (NOT backwards!) under tgm; audio: not judged` |
| `P6-18` | **Row 18: `Fat Man`** (`0x0008D2`, `000BD56F`, AP `60`, OMOD `001C6C03`) + `PROJ 0x0008C0` + `EXPL 0x0008BC` | `Bridger` `0026D96A`; KWs (`13`): `00255D9C, 00042AD4..`; `bridger` `.af`: `Bolt`, `Magazine`, `TRIGGER`, `Magazine01` (`CNuke`) | **`bat p6d` (`tgm`)** -> `bat p6a` -> `bat p6c`; `18` impact + `450` `EXPL` (`4.29 / 12.14 m`; **labelled stand-ins: `IS Radius=60.0 m` vs FO4 `214.29 m`, donor `Force=150.0` `P6-L2`**), wt `30.75`, val `513`; `WVIS=0x0015CCFD` | `Bridger` anim + `EXPL` `IS Radius=60m` / `Force=150` stand-ins (`24 Nov` not run) | `PENDING` | `needed: 1 fps mini-nuke parabolic drop + blast survival under `bat p6d` (`tgm`); audio: not judged` |
| `P6-19` | **Row 19: `Flamer`** (`0x0008D3`, `000E5881`, AP `30`, OMODs `00147AFF, 00147AF9, 00147AFB, 00147AFD`) | `ArcWelder` `0026D965`; KWs (`12`): `00167663, 00016759..`; `arcwelder/reload.af`: `Magazine` (`WeaponExtra3`), `MiscA` (`WeaponExtra1+Extra2+Optics2`), `TRIGGER` | `bat p6a` -> `bat p6c`; `9` `dtEnergy`, `100` cap, `0.15 s`, wt `16.125`, val `138`; **Ammo `0x0008B6` uses labelled `LaserBeamProjectile 0x000A0F51` stand-in (`P6-L3`)**; `WVIS=0x00115BE5` | **Heavy-grip `ArcWelder` + `LaserBeamProjectile` `000A0F51` stand-ins** (`24 Nov` not run) | `PENDING` | `needed: 1 fps heavy-grip 3rdP stance + fire stream on FleshDummy confirming projectile stand-in (`000A0F51`); audio: not judged` |
| `P6-20` | **Row 20: `Plasma Pistol` (`0x0008D4`) & `Plasma Rifle` (`0x0008D5`)** (`00100AE9`, AP `30`, Pistol `00100AE6,00100AE7,00127792,00188A1A`; Rifle `00111F7C`) | `Novalight` `0026D967` (`13` KWs; `Magazine, TRIGGER, MiscA..03` for `PlasmaValve1..5`) & `InflictorRifle` `0026D8A0` (`14` KWs; `Magazine, TRIGGER`, valves rigid on `PlasmaReceiver`) | `bat p6a` -> `bat p6c`; `24` phys + `24` `dtEnergy`, `30` cap, `0.30 s`; **Ammo `0x0008B7` uses labelled `LaserBeamProjectile 0x000A0F51` stand-in (`P6-L3`)**; `WVIS=0x00164E05`/`03`, `Crit=0x0008C3` | `24 Nov` PlasmaPistol `30 / 30` model PASS (`1b93113b`); `LaserBeamProjectile` `000A0F51` stand-in | `PENDING` | `needed: 1 fps Plasma Rifle 1stP model + slowed Plasma Pistol firing watching valve `MiscA..03` & `000A0F51` beam; audio: not judged` |
| `P6-21` | **Row 20b: `Gauss Rifle`** (`0x0008D6`, `000D1EB0`, AP `30`, OMODs `00179B53`, **`001AC252`**, `00179B4E, 00179B54`) | `Magsniper` `0002EB45`; KWs (`15`): `0001EC33, 0023F59B..`; `magsniper` `.af`: `MiscA`, `Magazine`, `TRIGGER` (empty `WeaponOptics1` removed) | `bat p6a` -> `bat p6c`; `110` dmg, **`8` cap (`P6-H1` `5 * 1.50 = 7.5 -> 8` AwayFromZero via `001AC252`)**, `0.15 s`, wt `15.80`, val `229`; `WVIS=0x0034BE5D` | `Magsniper` anim stand-in (`OFFLINE VERIFIED`) | `PENDING` | `needed: 1 fps HUD ammo counter confirming `8 / ...` + slowed recoil/bolt (`MiscA`) shot clip; audio: not judged` |

### B. Surface Impacts, Laser Ash / Plasma Goo (`bat p6x`), `NoDisintegrate`, & Exterior Daylight

| Row | Impact / Disintegration Focus | Batch / Console (`P3` Clean) | Expected Result / PASS Log | Stand-In / Truth | Result (`r12-p6b`) | VIDEO |
|---|---|---|---|---|---|---|
| `P6-22` | **Flesh, Metal (SF Robot), Stone & Wood Impacts** (`0x000811, 0x000812, 0x000814, 0x000815`) | `bat p6t` (**interior-only**) -> shoot 4 targets w/ ballistic, shotgun, blunt melee, laser | Distinct Starfield `IPDS` impacts: blood on `FleshDummy`, metallic sparks on `OutpostRobotMiniBotA_Garden` (`0x0004297C`), rock chips on `RockPittedA`, wood chips on `AK_Crate_WoodenSmall` (crate `2.10 m` clear of folding chair) | `24 Nov` not run (`1b93113b`); `OFFLINE VERIFIED` | `PENDING` | `needed: 1 fps / slowed hit-burst clips across Flesh, Robot, Stone, and Wood targets distinguishing sparks vs dust vs wood splinters; audio: not judged` |
| `P6-23` | **Laser Ash & Plasma Goo Disintegration** (`0x0008C1`–`0x0008C4`) | `bat p6t` (**interior-only**) -> **`bat p6x`** (`forceCritDisint=true`, or repeat crits) -> kill `FleshDummy` w/ Laser & Plasma | Laser leaves `AshPile01` (`0x0009142E`, shader `0x0026319B`); Plasma leaves `FO4_GooPile01` (`0x0008C1`); `FO4SF_R11P6 kill target=flesh eq=laserpistol` / `eq=plasmapistol force_crit=...` (never stale `FragMine`!) | `24 Nov`: Laser ash PASS (`eq=FragMine` bug), Plasma 1-kill no goo (`bat p6x` fixes determinism) | `PENDING` | `needed: 1 fps clip showing FleshDummy dissolving into AshPile01 and bright green FO4_GooPile01; audio: not judged` |
| `P6-24` | **`NoDisintegrate` Guard** (`0x04000802` carrying `Starfield.esm:0x0022DB8F`) | `bat p6t` (**interior-only**) -> **`bat p6x`** ON -> kill `NoDisintDummy` (`0x000813`) w/ Plasma Rifle & Laser Rifle | Target dies WITHOUT dissolving even with `bat p6x` ON; `FO4SF_R11P6 kill target=nodisint no_disintegrate=true eq=plasmarifle force_crit=suppressed_nodisint` | `24 Nov` 10mm `no_disintegrate=true` PASS; Plasma/Laser re-test needed | `PENDING` | `needed: 1 fps clip showing NoDisintDummy corpse remaining intact after fatal Plasma/Laser shots w/ p6x on; audio: not judged` |
| `P6-25` | **Exterior Vault 111 Daylight & Scorecard (`< 200 m`/axis)** | **Start at Sanctuary bench** (after vault exit) -> `bat p6h1` -> `bat p6e` -> `bat p6s` (**exterior-only**) | Clean daylight geometry/textures across sampled arsenal weapons, `0` crashes, `FO4SF_R11P6 summary tag=stage_30 eq=<weapon_tag> owned_weapons=23/23` | `24 Nov` not run; `r12-p6b` pending | `PENDING` | `needed: 1 fps clip panning sampled weapons in Vault 111 exterior daylight after bat p6e; audio: not judged` |

---

## Install, Status & Exact Undo Commands (Game Closed)

```bash
# Inspect staged package / verify BA2 BS-CRC32, Gun_*.af tracked bones, ProjectileNode.y > 0 & hashes (never use bundle_install.py)
python scripts/probes/stage_r11_p6_arsenal.py verify --stage-dir <probes-root>/r12-p6b

# Atomic install (checks Starfield.exe==0, refuses test-profile candidate unless --allow-test-baseline, stamps X3 prefix, writes receipt)
python scripts/probes/stage_r11_p6_arsenal.py install --stage-dir <probes-root>/r12-p6b --starfield <starfield-dir>

# Read-only status check
python scripts/probes/stage_r11_p6_arsenal.py status --starfield <starfield-dir>

# One-command atomic rollback (restores Plugins.txt + pre-existing FO4SFCoreValues.esm by SHA-256)
python scripts/probes/stage_r11_p6_arsenal.py uninstall --starfield <starfield-dir>
```

### Interactive Console & Batches (`P3` Zero-`M`/`N`/`V`)

```console
bat p6r
bat p6t
bat p6g
bat p6c
bat p6a
bat p6d
bat p6x
bat p6h1
bat p6e
bat p6s
bat p6q
```

```bat
; <starfield-dir>/p6d.txt (toggle god mode before explosive rows inside 11 m Vault room)
tgm

; <starfield-dir>/p6x.txt (toggle deterministic critical goo/ash on kill; 11 dynamic slot example)
SetStage 11000830 25

; <starfield-dir>/p6t.txt (INTERIOR-ONLY inside FO4Port_Vault111Cryo; 11 dynamic full-master slot example)
player.setpos x -52.40
player.setpos y 29.85
player.setpos z 0.05
player.setangle z 90
SetStage 11000830 20
```

### Required PASS Log Lines (`My Games/Starfield/Logs/Script/User/fo4sf_r11p6.0.log`)

```log
FO4SF_R11P6 init source=on_quest_init weapons=23 ammos=13 targets=flesh,robot,nodisint,stone,wood
FO4SF_R11P6 target_reset tag=flesh hp=40.000000 no_disintegrate=false
FO4SF_R11P6 target_reset tag=robot_metal hp=120.000000 no_disintegrate=false
FO4SF_R11P6 target_reset tag=nodisint hp=40.000000 no_disintegrate=true
FO4SF_R11P6 force_crit_disint=true
FO4SF_R11P6 kill target=flesh eq=laserpistol force_crit=laser total=1
FO4SF_R11P6 kill target=flesh eq=plasmapistol force_crit=plasma total=2
FO4SF_R11P6 kill target=nodisint no_disintegrate=true eq=plasmarifle force_crit=suppressed_nodisint total=1
FO4SF_R11P6 summary tag=stage_30 eq=<weapon_tag> force_crit_disint=<bool> owned_weapons=23/23 flesh_kills=<n> robot_kills=<n> nodisint_kills=<n>
```

---

## Claude's Additions (5 Rows — 24 Nov Baseline)

| Addition | PR / Track | Status Verdict | Integration / Dependency in This Card | Guard / Note |
|---|---|---|---|---|
| **Robot animations & Codsworth** | `#854` (`claude/robot-anim`) | **`not applicable`** (`r12-p6b` weapon/impact probe is self-contained) | `r12-p6b` robot metal target uses vanilla `OutpostRobotMiniBotA_Garden` (`0x0004297C`) while documenting FO4->SF robot `RACE.NAM4` `MATT` mapping in `docs/combat/impacts.md`; no `#854` dependency | Partial 23 Nov robot run unaffected |
| **Creature animations** | `#855` (`claude/creature-anim`) | **`not applicable`** (no creature `.rig`/`.af` or race edits here) | Vanilla `HumanRace` (`0x0000347D`) and creature `RACE.NAM4` stay untouched; exact creature `MATT` mapping documented in `docs/combat/impacts.md` | Stacked on `#854` |
| **Human animations** | `#856` (`claude/human-anim`) | **`not applicable`** (`--fo4-human-anims` stays OFF) | `FO4_UnarmedHuman` (`0x0008C5`) is `NonPlayable` and Starfield `HumanRace` is untouched; P6 relies on donor human animation keywords only | Stacked on `#854` |
| **Gun moving parts proof** | `#32` (`gunpart-slide-vanilla-vs-ours-1123.jpg` / `XM2311`) | **`built in`** (enforced on all 19 ranged guns in `r12-p6b`) | Every ranged gun's moving parts map onto its donor's exact `Starfield - Animations.ba2` `.af` track list (`DONOR_AF_TRACKS`: `TRIGGER`, `Magazine..01`, `Bolt`, `MiscA..A06`, `MiscB..B03`), zero `Weapon*`/`C*` leftovers survive, `verify` rejects untracked nodes, and `*_controllers.json` saves FO4 blocks | Requires slowed take (`1 fps` cannot judge fast bolt/hammer motion) |
| **Gun sounds** | `#32` (`sound-bank-study`) | **`gated`** (on Starfield add-on Wwise `.afx`/bank resolution) | All 23 `r12-p6b` weapons retain labelled Starfield donor `SNDR` stand-ins; zero `.afx`, `WAUD`, or sound banks touched; `audio: not judged` on all video checks | Awaits next sound probe |
