Titles: Fallout 4 | Modes: Story & Warfare | Track: Round 12 Probe P6 (Full Arsenal Rows 1-20, Impacts, Ash & Goo)

# Round 12 Test / Probe Card — Probe P6 (`r11-p6-arsenal`)

> **NEW GAME needed (`A16` / `R15`) & Scope / Honesty Banner:**
> - **Scope:** `r11-p6-arsenal` (Combat Plan Rows 1–20, `P5` Fixes `F1`–`F6`, `WEAP.WVIS`/`EXPL.ENAM` Impacts, Laser Ash & Plasma Goo, `NoDisintegrate` Guard) | **Mode:** Both (`Warfare` & `Story`) | **Baseline Target:** `candidate-2g-fix2` (`baseline != 2g-fix2` emits warning at install time)
> - **Version Tag:** `r12-p6-arsenal-v1`
> - **Stage Placeholders:** `<probes-root>/r11-p6-arsenal`, `<starfield-dir>`
> - **Disk Need:** `378.36 MB` installed under `<starfield-dir>/Data` (`>= 60.0 GiB` free required before staging/install; `Starfield.exe` closed)
> - **Overridden Candidate Files:** `["Data/FO4SFCoreValues.esm"]` (`FO4SFPipboyMenu.dll` `7d5ba49c` left untouched on installed candidate unless `--ship-pipboy-dll` is explicitly supplied)
> - **Truth & Stand-In Policy (`R8` / `R15`):** All P6 records and converted weapon/impact/ash-goo behaviors are **`OFFLINE ONLY — UNPROVEN IN GAME`** (no separate Claude P5 run was posted on `#32` before P6 staging; P6 supersedes P5 with `F1`–`F6` fixes + Rows 5–20). Every weapon NIF preserves `sgoKeep` moving-part `NiNode` names mapped onto Starfield donor-tracked names (`TRIGGER`, `Magazine`, `Bolt`, `MiscA..MiscA14`) with original FO4 names in `fo4_part_map` and NIF controller blocks exported to per-weapon `*_controllers.json` sidecars for future `.rig`/`.af` work on `claude/robot-anim`. Firing/reload/melee/throw animations, heavy-grip ArcWelder Flamer handling, and Wwise `SNDR` audio remain labelled Starfield stand-ins; donor Havok collision hulls replace unported FO4 `bhk` shapes. Zero `Starfield`/`FO4SF` prefixes in user-facing weapon/ammo `FULL` names.

---

## Staged Artifacts & Baseline Verification

`manifest.json` SHA-256: `b566202ec6c7bcd7ca7ae1a86c4fc10db053b488eff3342b0f059a8a148a4a8c` (`675` verified files, `48` placed refs bounds-checked above `z=0.000` / tabletop `z=0.825`).

| Artifact (`Data/...`) | Source / Reuse Status | Expected Size | Expected SHA-256 | Notes |
|---|---|---|---|---|
| `Data/FO4SFCoreValues.esm` | Rebuilt `--fo4-arsenal 1` (`st_nlink == 1` copied) | `76,995` B | `bfe6d99a75230b1dbb795c5cd0fcdb30a3b4ffb26e03bc667a73e59570b505d9` | Byte-identical parity with P2 (`#857`); `0` `FO4Core_Commonwealth` overrides; adds `0x0898..0x08A5` & `0x08B0..0x08D6` |
| `Data/FO4SF_R11P6Arsenal.esm` | Built for P6 (`st_nlink == 1` copied) | `7,579` B | `9beb45675dcdc13847749ef08a0728f1ecdbce52f3675ca173ef74e0ccee2f51` | Vault111Cryo 3-table rack, 23 weapons, 13 ammos, 3 props, 5 targets (`Flesh`, `Robot`, `NoDisint`, `Stone`, `Wood`), QUST `0x000830` |
| `Data/FO4SF_R11P6Arsenal - Main.ba2` | Packed GNRL (`pack_gnrl_ba2`, `BS CRC32` verified) | `4,336,094` B | `19d2aa5cb1c738d88857e46eefc71a2e901ec96ee6bbed95fff95b54e9514e66` | `368` entries: `23` weapon NIFs, `13` ammo NIFs, `4` core item NIFs, `2` proj NIFs, controller JSONs, `.mesh`, `.mat`, `FO4SF_R11P6Quest.pex` |
| `Data/FO4SF_R11P6Arsenal - Textures.ba2` | Packed DX10 (`pack_dx10_ba2`, `BS CRC32` verified) | `392,297,647` B | `62792bfb52a13d56fbb18ea684426aa102e77cf4eb791bd5e8cc65d453d33eb0` | `293` BC1/BC4/BC5/DX10 `.dds` textures |
| `SFSE/Plugins/FO4SFPipboyMenu.dll` | Preserved untouched on installed candidate (`7d5ba49c`) | `1,453,568` B | `7d5ba49c0c6ab2aa...` | Not overridden unless `--ship-pipboy-dll --tested-pipboy-dll <path>` is passed (`reuse_tested_binary` enforced) |

---

## `P3` Console, Batch & `< 200 m`/Axis Hop Rules

1. Every batch filename (`p6r`, `p6t`, `p6a`, `p6g`, `p6c`, `p6h1`, `p6e`, `p6s`, `p6q`) and every ```` ```console ```` / `bat <name>` activation contains **zero `m`, `n`, or `v` letters** and **zero stripped `FO4SF_*` EditorIDs**.
2. Interior hops (`p6r`, `p6t`, `p6a`) stay inside `FO4Port_Vault111Cryo`; exterior daylight hops move strictly `< 200 m` per axis from `sanctuary_bench (-2329.25, -1420.19, 112.09)` -> `p6h1 (-2400.00, -1413.00, 120.00)` (`dX=-70.75 m`) -> `p6e (-2467.78, -1406.93, 127.85)` (`dX=-67.78 m`).
3. `FO4SF_R11P6Quest.psc` resolves `FO4Port_SwitchDoorExSmLatch01` (`0x001539`) at runtime via `Game.GetFormFromFile` and stamps the dynamic full-master load slot prefix into `<XX>000830` during `install`.

---

## Verification Rows (Every Row Has a `VIDEO` Column)

### A. Range Infrastructure, `P5` Fixes (`F1`–`F6`) & `Rows 1–20` Weapon Rack

| Row | Weapon / Focus (CoreValues FormID & FO4 Source) | Batch / Console (`P3` Clean) | Expected Stats (`DNAM`/`DAMA`+OMOD), Part Mapping (`F1`–`F6`), & `WVIS` Impact | Stand-In / Truth | Result | VIDEO |
|---|---|---|---|---|---|---|
| `P6-00` | **Quest Init, 3-Table Rack & `F4` Floor Clearance** (`0x000810..0x000840`) | `bat p6r` + `bat p6t` | `FO4SF_R11P6 init weapons=23 ammos=13`; tables `z=0.00`; upright Minigun (`0x00081E`) drum `world_min_z=+0.830 m` strictly above `0.825 m` tabletop (`48/48` placed refs verified) | `OFFLINE ONLY — UNPROVEN IN GAME` | `PENDING` | `needed (tabletop clearance & targets spawn)` |
| `P6-01` | **Row 1: `Security Baton`** (`0x00089A`, FO4 `0008C14D`) | `bat p6r` -> pick up / `bat p6c` | `11` melee dmg (zero DAMA), `wt=2.0`, `val=15`; blood overlay skipped; `WVIS=0x00055DC3` (`WPNHandBladeSmall_ImpactSet`) | `RescueAxe` `0x04F760` anim/audio stand-in; `OFFLINE ONLY` | `PENDING` | `needed (1stP/3rdP swing & melee sparks)` |
| `P6-02` | **Row 2: `10mm Pistol`** (`0x000899`, FO4 `00004822`) + `10mm Round` (`0x000898`, `0.025` wt, val `2`) | `bat p6r` -> `bat p6c` | `18` dmg, `12`-round mag, `0.2143 s`, `wt=3.525`, `val=51`; `F1` moving parts `MiscA06`/`Magazine`/`TRIGGER` (zero empty helpers); `WVIS=0x0000D02C` | `XM2311` `0x24561C` anim/audio/coll stand-in; `OFFLINE ONLY` | `PENDING` | `needed (10mm mag fire & reload)` |
| `P6-03` | **Row 3: `Laser Musket`** (`0x00089D`, `0001DACF`) + Preston `0x00089E` (`00062AA6`) + `Fusion Cell` (`0x00089B`, `000C1897`, wt `0.029`, val `3`) | `bat p6r` -> `bat p6c` | `0` phys + `30` `DAMA` energy (`18` Preston, val `195` from base `150`), `0.667 s` combat-plan rate, `wt=12.6`, `val=61`; `F3` `ProjectileNode` at `~(0.000,0.935,0.079)` m; `F1` `TRIGGER`+`WeaponMagazine` crank; `F6` FX controllers saved; `WVIS=0x001C1162` | `Orion` `0x2773C8` anim/audio stand-in (`0.667s` plan rate); `OFFLINE ONLY` | `PENDING` | `needed (barrel muzzle aim, fire & ash check)` |
| `P6-04` | **Row 4: `Minigun`** (`0x0008A0`, `0001F669`) + `5mm Round` (`0x00089F`, `0001F66C`, wt `0.009`, val `1`) | `bat p6r` -> `bat p6c` | `8` dmg, `500`-rd drum, `wt=27.45`, `val=383`; `F1` `MiscA01`->`BarrelRoot`->`Minigun_Barrel` & `Magazine`->`Minigun_AmmoDrum`; `F4` elevated tabletop drum; `F6` 23 controller blocks saved; `WVIS=0x0000D02C` | `Microgun` `0x0546CD` fire rate/anim/audio stand-in; `OFFLINE ONLY` | `PENDING` | `needed (burst spin/recoil & drum above table)` |
| `P6-05` | **Row 5: `Pipe Pistol` (`0x0008A2`) & `Pipe Rifle` (`0x0008A3`)** (`00024F55`) + `.38 Round` (`0x0008A1`, `0004CE87`, wt `0.015`, val `1`) | `bat p6r` -> `bat p6c` | `13` dmg, `12` cap, `0.18 s`, wt `2.35`/`3.40`, val `23`/`28`; `MiscB`/`MiscA` bolt + `Magazine` + `TRIGGER`; `WVIS=0x0000D02C` (contract consumed by Task 1 `S4`–`S6`) | `Eon`/`Beowulf` anim/audio/coll stand-in; `OFFLINE ONLY` | `PENDING` | `needed (1stP/3rdP pistol & rifle fire)` |
| `P6-06` | **Row 6: `Unarmed`** (`0x0008C5`, FO4 `000C2C27`, `NonPlayable`) | `FO4SFCoreValues.esm` binary + dummy unarmed target | `8` dmg, reach `0.68`, `WVIS=0x00252B4C` (`WPNMeleeBashHandImpactSet`); `FO4_UnarmedHuman` `NonPlayable` for `HumanRace` UNWP parity | `Starfield` `Unarmed` `0x0001F4` donor anim/coll; `OFFLINE ONLY` | `PENDING` | `needed (optional bare-hand impact / ESM verified)` |
| `P6-07` | **Row 7: `Frag Grenade`** (`0x0008C6`, `000EEBED`) + `PROJ` `0x0008BD` + `EXPL` `0x0008B9` | `bat p6a` -> `bat p6g` -> `bat p6c` | `EXPL` `150` dmg (`2.14`–`7.14 m`), `ENAM[84:88]=0x003A5907` (`FXProjectileRocketImpactSet`), `WVIS=0x0015CCFD`, wt `0.5`, val `50` | `FragGrenade` `0x0115EF` throw anim/audio stand-in; `OFFLINE ONLY` | `PENDING` | `needed (throw arc & floor explosion)` |
| `P6-08` | **Row 8: `Frag Mine`** (`0x0008C7`, `000E56C2`) + `PROJ` `0x0008BE` + `EXPL` `0x0008BA` | `bat p6a` -> `bat p6g` -> `bat p6c` | `EXPL` `100` dmg (`1.43`–`7.14 m`), `ENAM[84:88]=0x003A5907`, `WVIS=0x0015CCFD`, wt `0.5`, val `50` | `FragMine` `0x04A41A` place anim/audio stand-in; `OFFLINE ONLY` | `PENDING` | `needed (mine arming & detonation)` |
| `P6-09` | **Row 9: `Pipe Revolver`** (`0x0008C8`, `0014831B`) + `.45 Round` (`0x0008B1`, wt `0.030`, val `2`) | `bat p6a` -> `bat p6c` | `24` dmg, `6` cap, `0.15 s`, wt `4.30`, val `28`; `Bolt`+`Magazine`+`TRIGGER`; `WVIS=0x0000D02C` | `Razorback` `0x000FD6` anim/audio stand-in; `OFFLINE ONLY` | `PENDING` | `needed (1stP/3rdP fire & cylinder visual)` |
| `P6-10` | **Row 10: `Hunting Rifle`** (`0x0008C9`, `0004F46A`) + `.308 Round` (`0x0008B0`, `0001F66B`, wt `0.041`, val `3`) | `bat p6a` -> `bat p6c` | `37` dmg, `5` cap, `0.15 s` / speed `1.25`, wt `9.60`, val `55`; `MiscA` bolt+`Magazine`+`TRIGGER`; `WVIS=0x0000D02C` | `Lawgiver` `0x02D7F4` anim/audio stand-in; `OFFLINE ONLY` | `PENDING` | `needed (rifle fire & iron-sight ADS)` |
| `P6-11` | **Row 11: `Combat Shotgun`** (`0x0008CA`, `0014831C`) + `Shotgun Shell` (`0x0008B2`, wt `0.100`, val `3`) | `bat p6a` -> `bat p6c` | `50` dmg, `8` cap, `0.50 s`, wt `11.20`, val `89`; `Bolt`+`Magazine`; `WVIS=0x00239D0F` (`FXProjectileShotgunImpactSet`) | `Pacifier` `0x2953F8` anim/audio stand-in; `OFFLINE ONLY` | `PENDING` | `needed (shotgun blast & spread impact)` |
| `P6-12` | **Row 12: `Double-Barrel Shotgun`** (`0x0008CB`, `00092217`) + `Shotgun Shell` (`0x0008B2`) | `bat p6a` -> `bat p6c` | `45` dmg, `2` cap, `0.275 s`, wt `9.00`, val `41`; `MiscA`->`Shotgun_Barrel_Medium`+`TRIGGER`; `WVIS=0x001D7FEC` (`FXProjectileShotgunCoachmanSet`) | `Coachman` `0x26D96B` anim/audio stand-in; `OFFLINE ONLY` | `PENDING` | `needed (2-shot barrel & reload)` |
| `P6-13` | **Row 13: `Submachine Gun`** (`0x0008CC`, `0015B043`) + `.45 Round` (`0x0008B1`) | `bat p6a` -> `bat p6c` | `13` dmg, `50`-rd drum, `0.15 s` / speed `1.40`, wt `12.775`, val `110`; `Bolt`+`TRIGGER`+`Magazine`; `WVIS=0x0000D02C` | `Maelstrom` `0x2984DF` anim/audio stand-in; `OFFLINE ONLY` | `PENDING` | `needed (full-auto burst & drum look)` |
| `P6-14` | **Row 14: `Assault Rifle`** (`0x0008CD`, `0000463F`) + `5.56 Round` (`0x0008B3`, wt `0.035`, val `2`) | `bat p6a` -> `bat p6c` | `30` dmg, `20` cap, `0.25 s`, wt `13.20`, val `145`; `Magazine`+`WeaponExtra1`; `WVIS=0x0000D02C` | `AA99` `0x2BF65B` anim/audio stand-in; `OFFLINE ONLY` | `PENDING` | `needed (1stP/3rdP rifle fire)` |
| `P6-15` | **Row 15: `Laser Pistol` (`0x0008CE`) & `Laser Rifle` (`0x0008CF`)** (`0009983B`) + `Fusion Cell` (`0x00089B`) | `bat p6a` -> `bat p6c` | `24` energy dmg, `30` cap, `0.20 s`, wt `3.975`/`5.25`, val `68`/`81`; `MiscA`/`MiscB`+`Magazine`; `WVIS=0x001F5DA1`; `CritSpell=0x0008C4` (`FO4_CritLaser`) | `Solstice`/`Equinox` anim/audio stand-in; `OFFLINE ONLY` | `PENDING` | `needed (laser beam fire & ash pile)` |
| `P6-16` | **Row 16: `Baseball Bat`** (`0x0008D0`, `0008E736`) | `bat p6a` -> `bat p6c` | `16` melee dmg, reach `0.80`, wt `3.00`, val `25`; `WVIS=0x0005C498` (`WPNMeleeImpactBladeMediumSet`) | `RescueAxe` `0x04F760` anim/audio stand-in; `OFFLINE ONLY` | `PENDING` | `needed (bat 1stP/3rdP swing & wood/flesh hit)` |
| `P6-17` | **Row 17: `Missile Launcher`** (`0x0008D1`, `0003F6F8`) + `Missile` (`0x0008B4`, wt `7.0`) + `PROJ` `0x0008BF` + `EXPL` `0x0008BB` | `bat p6a` -> `bat p6c` | `15` impact + `135` `EXPL` (`2.14`–`7.14 m`, `ENAM=0x0015CCFD`), `WVIS=0x0015CCFD`, wt `21.00`, val `315`; `TRIGGER` node | `Bridger` `0x26D96A` anim/audio stand-in; `OFFLINE ONLY` | `PENDING` | `needed (missile flight & explosion)` |
| `P6-18` | **Row 18: `Fat Man`** (`0x0008D2`, `000BD56F`) + `Mini Nuke` (`0x0008B5`, wt `12.0`) + `PROJ` `0x0008C0` + `EXPL` `0x0008BC` | `bat p6a` -> `bat p6c` | `18` impact + `450` `EXPL` (`4.29`–`12.14 m`, `ENAM=0x0015CCFD`), `WVIS=0x0015CCFD`, wt `30.75`, val `513`; `Bolt`+`Magazine`+`TRIGGER` | `Bridger` `0x26D96A` anim/audio stand-in; `OFFLINE ONLY` | `PENDING` | `needed (mini nuke arc & blast)` |
| `P6-19` | **Row 19: `Flamer`** (`0x0008D3`, `000E5881`) + `Flamer Fuel` (`0x0008B6`, wt `0.01`, val `1`) | `bat p6a` -> `bat p6c` | `9` energy dmg, `100` cap, `0.15 s`, wt `16.125`, val `138`; `Magazine` fuel tank; `WVIS=0x00115BE5` (`FXProjectileFlamethrowerImpactSet`) | **Heavy-grip `ArcWelder` (`0x26D965`) stand-in**; `OFFLINE ONLY` | `PENDING` | `needed (flamer jet & heavy-grip stance)` |
| `P6-20` | **Row 20: `Plasma Pistol` (`0x0008D4`) & `Plasma Rifle` (`0x0008D5`)** (`00100AE9`) + `Plasma Cartridge` (`0x0008B7`, wt `0.03`, val `5`) | `bat p6a` -> `bat p6c` | `24` phys + `24` `DAMA` energy (`0`–`30` cap, `0.30 s`), wt `3.975`/`4.80`, val `126`/`157`; `TRIGGER`+`Magazine`; `WVIS=0x00164E05`/`0x00164E03`; `CritSpell=0x0008C3` (`FO4_CritPlasma`) | `Novalight`/`Va'ruun Inflictor` anim/audio stand-in; `OFFLINE ONLY` | `PENDING` | `needed (plasma fire & goo pile)` |
| `P6-21` | **Row 20b: `Gauss Rifle`** (`0x0008D6`, `000D1EB0`) + `2mm EC` (`0x0008B8`, wt `0.128`, val `10`) | `bat p6a` -> `bat p6c` | `110` phys dmg, `5` cap, `0.15 s`, wt `15.80`, val `229`; `MiscA`+`Magazine`+`TRIGGER`; `WVIS=0x0034BE5D` (`FXProjectileBulletMagImpactSet`) | `Magsniper` `0x02EB45` anim/audio stand-in; `OFFLINE ONLY` | `PENDING` | `needed (gauss shot & mag-bullet impact)` |

### B. Surface Impacts, Laser Ash / Plasma Goo / `NoDisintegrate`, & Exterior Daylight

| Row | Impact / Disintegration Focus | Batch / Console (`P3` Clean) | Expected Result / PASS Log | Stand-In / Truth | Result | VIDEO |
|---|---|---|---|---|---|---|
| `P6-22` | **Flesh, Metal (SF Robot), Stone & Wood Impacts** (`0x000811`, `0x000812`, `0x000814`, `0x000815`) | `bat p6t` -> shoot 4 targets w/ ballistic, shotgun, melee, laser | Distinct Starfield `IPDS` impacts: blood on `FleshDummy`, sparks/clang on `OutpostRobotMiniBotA_Garden` (`0x0004297C`), dust/chips on `RockPittedA` (`0x000012E5`) & `AK_Crate_WoodenSmall` (`0x0013E8CA`) | `OFFLINE ONLY — UNPROVEN IN GAME` | `PENDING` | `needed (flesh/robot/stone/wood impacts)` |
| `P6-23` | **Laser Ash & Plasma Goo Disintegration** (`0x0008C1`–`0x0008C4`) | `bat p6t` -> kill `FleshDummy` (`0x000811`) w/ Laser Pistol/Rifle & Plasma Pistol/Rifle | Laser kill leaves Starfield `AshPile01` (`0x0009142E`, `CritLaserDisintegration` `0x0026319B`); Plasma kill leaves converted `FO4_GooPile01` (`0x0008C1`) + `FO4SF_R11P6 kill target=flesh` | `OFFLINE ONLY — UNPROVEN IN GAME` | `PENDING` | `needed (ash pile & green goo pile on death)` |
| `P6-24` | **`NoDisintegrate` Guard** (`0x04000802` carrying `Starfield.esm:0x0022DB8F`) | `bat p6t` -> kill `NoDisintDummy` (`0x000813`) w/ Plasma Rifle & Laser Rifle | Target dies WITHOUT dissolving into Ash or Goo; `FO4SF_R11P6 kill target=nodisint no_disintegrate=true` | `OFFLINE ONLY — UNPROVEN IN GAME` | `PENDING` | `needed (body stays intact with NoDisintegrate)` |
| `P6-25` | **Exterior Vault 111 Daylight Inspection & Scorecard (`< 200 m`/axis hops)** | `bat p6h1` -> `bat p6e` -> `bat p6s` | Clean daylight silhouette/materials on sampled weapons, `0` crashes, `FO4SF_R11P6 summary tag=stage_30 owned_weapons=23/23` | `OFFLINE ONLY — UNPROVEN IN GAME` | `PENDING` | `needed (exterior Vault 111 daylight showcase)` |

---

## Install, Status & Exact Undo Commands (Game Closed)

```bash
# Inspect staged package / verify BA2 BS-CRC32 + SHA-256 hashes (never use bundle_install.py)
python scripts/probes/stage_r11_p6_arsenal.py verify --stage-dir <probes-root>/r11-p6-arsenal

# Atomic install (checks Starfield.exe==0, *.txt collisions, baseline!=2g-fix2 warning, writes receipt before swap)
python scripts/probes/stage_r11_p6_arsenal.py install --stage-dir <probes-root>/r11-p6-arsenal --starfield <starfield-dir>

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
bat p6h1
bat p6e
bat p6s
bat p6q
```

```bat
; <starfield-dir>/p6r.txt (Vault111Cryo firing line beside Rack 1)
coc FO4Port_Vault111Cryo
player.setpos x -52.40
player.setpos y 29.85
player.setpos z 0.05
player.setangle z 90

; <starfield-dir>/p6t.txt (Activate range targets; 11 dynamic full-master slot example)
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
FO4SF_R11P6 kill target=flesh eq=laserpistol total=1
FO4SF_R11P6 kill target=nodisint no_disintegrate=true eq=plasmarifle total=1
FO4SF_R11P6 summary tag=stage_30 eq=<weapon_tag> owned_weapons=23/23 flesh_kills=<n> robot_kills=<n> nodisint_kills=<n>
```

---

## Claude's Additions (5 Rows — 23 Nov In-Game Baseline)

| Addition | PR / Track | 23 Nov In-Game Status | Integration / Dependency in This Card | Guard / Note |
|---|---|---|---|---|
| **Robot animations & Codsworth** | `#854` (`claude/robot-anim`) | Partial pass: FO4 Mr. Handy body + animations; 4-line Sanctuary talk `completed=true`, `fallback=0` (close camera & greeting replay noted) | Unaffected here; P6 range metal impact uses vanilla Starfield `OutpostRobotMiniBotA_Garden` (`0x0004297C`) while documenting FO4->SF robot `NAM4` mapping in `docs/combat/impacts.md` | Review CLEAR; awaiting owner merge |
| **Creature animations** | `#855` (`claude/creature-anim`) | Partial: radroach idle & deathclaw tail/spines moved in game; walk/attack/death & bloatfly/mole rat/dog unverified | Documented exact FO4 creature material -> Starfield `MATT` mapping in `docs/combat/impacts.md` without modifying Starfield races (`RACE.NAM4` untouched on vanilla races) | Stacked on `#854` |
| **Human animations** | `#856` (`claude/human-anim`) | Partial: add-on race keyword NPC played FO4 surrender idle vs normal control; walk & 1stP gun unverified | `--fo4-human-anims` stays OFF (`FO4_UnarmedHuman` `0x0008C5` authored `NonPlayable`, Starfield `HumanRace` `0x0000347D` never mutated) | Stacked on `#854` |
| **Gun moving parts proof** | `#32` (`gunpart-slide-vanilla-vs-ours-1123.jpg`) | Proved `Gun_*.af` moves `XM2311` slide nodes | P6 applies `F1`/`F6` across all 23 weapons: geometry moved directly onto `TRIGGER`, `Magazine`, `Bolt`, `MiscA..MiscA14` + `fo4_part_map` + per-weapon `*_controllers.json` sidecars | Owner rule: guns NOT ready until parts move |
| **Gun sounds** | `#32` (`sound-bank-study`) | **ON HOLD**: hand-made bank (`v174` vs SF `v140`) & direct override silent (add-on banks load on demand) | All 23 P6 weapons explicitly retain labelled Starfield donor `SNDR` stand-ins; zero `.afx`/WAUD/bank files touched | Next probe tests per-item bank link |
