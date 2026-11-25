Titles: Fallout 4 -> all 7 Fallout titles (FO4, FO3, FNV, FO1, FO2, Tactics, FO76) | Modes: Story & Warfare (+ Survival hardcore layer) | Track: Track 1 (Round 11 Pre-Build Probe P5: Baton, 10mm Pistol, Laser Musket & Minigun)

# Round 11 Pre-Build Probe `P5` (`Baton`, `10mm Pistol`, `Laser Musket` & `Minigun` + Moving-Part NIF Hierarchy) Session Card (`Step 4 / P3 / R8 / R15`)

> **NEW GAME recommended (`A16` / `R15`) & Scope / Honesty Banner:**
> - **Whole Scope:** Title: **Fallout 4** | Mode: **Story** (`candidate-2g-fix2` `13`-plugin Track-1 baseline + standalone reversible Probe `P5` overlay — run `P5` as a short standalone probe and uninstall cleanly when done; never touch `candidate-2g`, `candidate-2g-fix`, `candidate-2g-fix2`, `r11-p1-museum`, or `r11-p4-10mm`) | Track: **Track 1 pre-build probe (`P5` ONLY — `Baton`, `10mm Pistol`, `Laser Musket`, `Minigun` + `FO4` ammo)**.
> - **`prototype, offline` — `OFFLINE ONLY — UNPROVEN IN GAME`:** Probe `P5` (`<p5-stage-dir>`) is **`TEST-STATION` (`prototype, offline` / OFFLINE ONLY — UNPROVEN IN GAME)** until Claude (PC) runs it in Starfield.
> - **`R8` / `R15` Mandatory Stand-In Disclosures (NEVER call these "done"):**
>   - **Donor Starfield Animations & Wwise `SNDR` Audio are STAND-INS for ALL four weapons:**
>     - `FO4_Baton` (`0x00089A`): **`Starfield.esm:0x0004F760` (`RescueAxe`) stand-in** — chosen over `CombatKnife` because `RescueAxe` uses a 1-handed hafted bludgeon/chop swing matching the Baton's grip, reach, and side-swing arc rather than a short stabbing thrust.
>     - `FO4_10mmPistol` (`0x000899`): **`Starfield.esm:0x0024561C` (`XM2311`) stand-in** (animations + Wwise audio).
>     - `FO4_LaserMusket` (`0x00089D`) & `FO4_CompPrestonLaserMusket` (`0x00089E`): **`Starfield.esm:0x002773C8` (`Orion`) stand-in** (2H semi-auto laser rifle + beam + iron sights + Wwise audio; crank does not spin yet under donor anims).
>     - `FO4_Minigun` (`0x0008A0`): **`Starfield.esm:0x000546CD` (`Microgun`) stand-in** (2H heavy rotary gun animations + Wwise audio).
>   - **Hierarchical Moving-Part `NiNode` Preservation (for Claude's `claude/robot-anim` `.rig`/`.af` route):** Unlike Probe `P4`'s single flattened mesh, all four `P5` weapon NIFs preserve Fallout 4's named moving-part `NiNode` subtrees (`sgoKeep` + FO4 pivots) owning their moving `BSGeometry` shapes so Claude's future animation work can drive them without rebuilding the meshes. Under today's Starfield donor stand-in animations, those moving sub-parts remain stationary (`stand-in`).

Truth labels used throughout: **`REACHABLE`**, **`TEST-STATION`**, **`OWNER TEST`**, **`RECORDS ONLY`**, **`TOOLING`**, **`NOT BUILT`**, **`NOT WIRED`**, **`NOT OURS`**.

---

## `P3` Typed-Console & Batch-Filename Rules + `< 200 m`/Axis Hop Table

1. **Zero `M`, `N`, or `V` in Typed Console Lines & Batch Filenames (`P3`):** Every typed ```` ```console ```` command and every batch filename (`bat <stem>` / `<stem>.txt`) below contains **ZERO `M`, `N`, or `V` letters** (case-insensitive). Batch file contents (```` ```bat ````) execute from disk without keystrokes.
2. **Zero Stripped Mod `FO4SF_*` EditorIDs inside `bat/*.txt` (`P3`):** `stage_r11_p5_weapons.py install` reads live full-master load order (`(flags & 0x300) == 0`, skipping `FE`/`FD` light/medium masters) from `<starfield-dir>/Data` + `Plugins.txt` and stamps the exact runtime hex prefix (default `0x11` -> `SetStage 11000820 10|20|30`) into `<starfield-dir>/p5*.txt`.
3. **Both `P4` Notes Fixed Cleanly in `P5`:**
   - **Zero non-persistent cross-plugin `VMAD` properties:** `ArmoryCageDoor` (`FO4Port.esm:0x001539`) is resolved at runtime via `Game.GetFormFromFile(ArmoryCageDoorLocalId, PortPlugin)` (`0` `<nullptr form>` errors).
   - **Logs from game start:** `FO4SF_R11P5Quest` (`0x04000820`) sets `QUST DNAM = 0x00000009` (`StartGameEnabled | AllowRepeatedStages`) and logs `FO4SF_R11P5 init ...` + `summary tag=init` immediately on load/new game.
   - **Unarmed, restrained, resettable target:** `SpawnPracticeTarget` calls `TargetDummy.RemoveAllItems(None, false)` and `SetRestrained(true)` (`30.0 HP`), and pressing **`E`** on `FO4SF_P5_TargetTriggerRef` (`[Spawn / Reset] P5 Weapons Target`) or running `bat p5t` resets the target cleanly between Baton melee and ranged weapon checks.

---

## Pinned FormID Contract & Preserved FO4 Moving-Part `NiNode` Hierarchy

| Weapon / Ammo | `FO4SFCoreValues.esm` FormID | Donor Stand-In (`Starfield.esm`) | NIF Path (`Main.ba2`) | Preserved FO4 Moving-Part `NiNode` -> `BSGeometry` Subtrees (`stand-in` under donor anims) |
|---|---|---|---|---|
| `FO4_Baton` (`"Baton"`, `10` phys) | `0x00089A` | `RescueAxe` (`0x0004F760`) — 1H hafted swing | `meshes/fo4sf/weapons/baton/fo4_baton.nif` | **`3` telescoping shapes** (`baton.nif`, `0` `BloodWeapon.BGSM` shells; `+Z` `[-0.1018..+0.5185] m`, laid flat on table/crate via `rx=-pi/2`): `WeaponExtra1` -> `BatonLowExt01` -> `BatonLowExt01:0`; `WeaponExtra2` -> `BatonLowExt02` -> `BatonLowExt02:0`; `BatonLowHandle` -> `BatonLowHandle:0` |
| `FO4_10mmPistol` (`"10mm Pistol"`, `18` phys, cap `12`) | `0x000899` | `XM2311` (`0x0024561C`) | `meshes/fo4sf/weapons/10mm/fo4_10mmpistol.nif` | **`8` shapes:** `WeaponBolt` -> `Pistol10mmBolt:0`; `WeaponMagazine` -> `Magazine:0`; `WeaponTrigger` -> `10mmTrigger:0`; `WeaponExtra1` -> `Pistol10mmRelease:0`; `WeaponExtra2` -> `Pistol10mmHammer:0`; `WeaponExtra3` -> `Pistol10mmBoltRelease:0`; `Pistol10mmReceiver` -> `[Pistol10mmReceiver:0, 10mmGrip:0, ProjectileNode]` |
| `FO4_LaserMusket` (`"Laser Musket"`, `30` energy, cap `2`) | `0x00089D` | `Orion` (`0x002773C8`) | `meshes/fo4sf/weapons/lasermusket/fo4_lasermusket.nif` | **`17` opaque shapes** (`OBTS[0]`, `6` `BSEffectShaderProperty` FX shells skipped): `LaserMusketReceiver` -> `WeaponMagazine` -> `LaserMusketCrank:0`, `WeaponTrigger` -> `LaserMusketTrigger:0`, `WeaponExtra1` -> `LaserMusketMagnet1:0/:2`, `WeaponExtra2` -> `LaserMusketRotor:0/:2`, `WeaponExtra3` -> `LaserMusketMagnet2:0/:2`, `LaserMusketMaresLeg` -> `:1`, `LaserRifleBarrelMusket004` -> `[..., LaserMusketBarrelExtension2Lens -> :0/:1]`, `LaserMusketIronSight` -> `:0/:1`, plus `ProjectileNode` & `Scope` (`Z=0.1695 m`) |
| `FO4_CompPrestonLaserMusket` (`"Preston's Laser Musket"`, `18` energy, `NonPlayable`) | `0x00089E` | `Orion` (`0x002773C8`) | `meshes/fo4sf/weapons/lasermusket/fo4_lasermusket.nif` | Same `17`-shape preserved Laser Musket `NiNode` hierarchy (companion record, uses `0x00089C`) |
| `FO4_Minigun` (`"Minigun"`, `8` phys, cap `500`) | `0x0008A0` | `Microgun` (`0x000546CD`) | `meshes/fo4sf/weapons/minigun/fo4_minigun.nif` | **`6` opaque shapes** (`OBTS[0]`, `BaseRefractionMesh:0` `SLSF1_REFRACTION` skipped): `WeaponBolt` -> `BarrelRoot` -> `Minigun_Barrel` -> `Minigun_Barrel:0` (rotating 6-barrel cluster); `WeaponMagazine` -> `Minigun_AmmoDrum` -> `Minigun_AmmoDrum:0`; `Minigun001` -> `[Minigun001:0, Minigun_Rear:0, Minigun_Rear:1, AmmoBelt:0]` + `ProjectileNode` |
| `FO4_Ammo10mm` (`"10mm Round"`) | `0x000898` | `Ammo45Caliber` (`0x002B5598`) | `meshes/fo4core/ammo/10mm/10mmammo.nif` | World pickup box (`48` rds on Vault 111 armory cage shelf via `FO4SFNewGame.esm:0x000821`) |
| `FO4_AmmoFusionCell` (`"Fusion Cell"`) / `FO4_CompanionAmmoFusionCell` (`NonPlayable`) | `0x00089B` / `0x00089C` | `AmmoLaser` (`0x0000E8EC`) | `meshes/fo4core/ammo/laserammo/microfusioncell.nif` | `3` range boxes (`24` rds each = `72` total, `0x04000815..0x04000817`) |
| `FO4_Ammo5mm` (`"5mm Round"`) | `0x00089F` | `Ammo777mm` (`0x0004AD3E`) | `meshes/fo4core/ammo/5mm/5mmammo.nif` | `1` range box (`500` rds, `0x04000819`) |

---

## Vault 111 Exact World Placements (`FO4Port_Vault111Cryo`, `0x010011F3`)

| Placed Reference | Plugin & FormID | Source / Position (`m` in `FO4Port_Vault111Cryo`) | Resting Surface / Notes |
|---|---|---|---|
| `FO4SF_P5_BatonCryoRef` (`Baton` #1) | `FO4SF_R11P5Weapons.esm:0x04000812` | FO4 `0x0019891C` -> `(-2.3651, 28.5789, -1.0123)` | Rests on `FO4Port_Vault_Table_01` (`0x0100147C`, floor `-1.829`); reach via `bat p5b1` |
| `FO4SF_P5_BatonCrateRef` (`Baton` #2) | `FO4SF_R11P5Weapons.esm:0x04000813` | FO4 `0x000AE470` -> `(-18.1756, 13.6082, -1.2248)` | Rests on `FO4Port_Vault_Crate_03` (`0x010014F6`, floor `-1.829`); reach via `bat p5b2` |
| `FO4SF_Vault111PistolRef` (`10mm Pistol`) | `FO4SFNewGame.esm:0x0A000820` | FO4 `0x0005F762` -> `(-57.0338, 30.0060, 1.2850)` | Top shelf of `FO4Port_Vault_Shelf_04` inside armory cage; reach via `bat p5d` / `bat p5o` |
| `FO4SF_Vault111AmmoRef` (`48x 10mm Round`) | `FO4SFNewGame.esm:0x0A000821` | `(-57.0522, 30.3703, 0.6960)` | One shelf below pistol inside armory cage (`XCNT = 48`) |
| `FO4SF_P5_LaserMusketRef` (`Laser Musket`) | `FO4SF_R11P5Weapons.esm:0x04000814` | `(-53.30, 28.80, 0.12)` | Open Overseer range floor (south of firing line); reach via `bat p5r` |
| `FO4SF_P5_FusionCellBox1..3Ref` (`3x 24 Fusion Cell`) | `FO4SF_R11P5Weapons.esm:0x04000815..0817` | `(-53.00..-52.50, 28.60, 0.08)` | Arrayed beside Laser Musket (`72` Fusion Cells total) |
| `FO4SF_P5_MinigunRef` (`Minigun`) | `FO4SF_R11P5Weapons.esm:0x04000818` | `(-52.10, 28.85, 0.18)` | Open Overseer range floor beside Laser Musket; reach via `bat p5r` |
| `FO4SF_P5_Ammo5mmBoxRef` (`500x 5mm Round`) | `FO4SF_R11P5Weapons.esm:0x04000819` | `(-51.60, 28.70, 0.10)` | Beside Minigun (`XCNT = 500`) |
| `FO4SF_P5_TargetTriggerRef` (`E`-activator) | `FO4SF_R11P5Weapons.esm:0x04000810` | `(-55.40, 31.10, 1.35)` | Press **`E`** (`[Spawn / Reset] P5 Weapons Target`) to open cage door `0x01001539` & spawn/reset unarmed `30 HP` dummy |
| `FO4SF_P5_TargetDummyRef` (`InitiallyDisabled` `0xC00`) | `FO4SF_R11P5Weapons.esm:0x04000811` | `(-48.80, 30.00, 0.15)` | Unarmed (`RemoveAllItems`), restrained, `30.0 HP`, `4.40 m` east of firing line |

---

## Install, Verify & Reversible Rollback Commands (`Archive2.exe` + `bs_crc32` Verified)

Game MUST be closed (`Starfield.exe == 0`) and target drive MUST have `>= 60.0 GiB` free. `install` uses `shutil.copy2` for all `.esm`/`.txt` files (`st_nlink == 1`, never hardlinks `.esm`), `os.link` only for `.ba2` archives, and `uninstall` restores pre-probe `FO4SFCoreValues.esm`, `FO4SFNewGame.esm`, and `Plugins.txt` bit-for-bit by SHA-256.

### Staged File Inventory & SHA-256 Receipts (`r11-p5-weapons/manifest.json` — `141/141` Files Verified Offline)

| Staged File (`<p5-stage-dir>/...`) | Size (Bytes) | Exact SHA-256 | Role |
|---|---:|---|---|
| `core/FO4SFCoreValues.esm` | `20,441` | `b69a8078447ab7c83572d58ac5c85e92cd14c3b7f038d5fbf0f9335753b4fadb` | `--fo4-10mm 1 --fo4-p5-weapons 1` (`[Starfield.esm]` master only: `4 AMMO`, `5 WEAP` `0x000898..0x0008A0`) |
| `core/FO4SFNewGame.esm` | `12,688` | `7fcbb12ff901daa2b392dba54948ea076f21db22d9eb20a6e2429a6baa45301e` | `--fo4-10mm 1`: Vault 111 armory cage shelf `0x0820` `10mm Pistol` + `0x0821` `48x 10mm Round` |
| `exp/FO4SF_R11P5Weapons.esm` | `2,411` | `f8b5378339ab726e7f3069e58a084a220082ff63faec29636803e4b8476538ff` | `0` `WRLD`/`PNDT`, `QUST 0x04000820` (`DNAM=0x00000009`), `0` `ArmoryCageDoor` `VMAD` ObjectRef, `2` flat Batons + Laser Musket + `3x24` Cells + Minigun + `500x 5mm` + `0xC00` `TargetDummy` |
| `exp/FO4SF_R11P5Weapons - Main.ba2` | `1,541,379` | `140669b5de6363c54f1beab66e2d187b9dc0a56fbbe12042e2599f023e52cba3` | `BTDX` v2 `GNRL` via `Archive2.exe` (`68` uncompressed entries, `bs_crc32` verified: `2` `.pex`, `7` `.nif`, `.mesh`, `.mat`) |
| `exp/FO4SF_R11P5Weapons - Textures.ba2` | `40,502,897` | `6b22ba04a39d4b13ff7fbebec12d651857a370f93059a240b7deac6508b6556b` | `BTDX` v2 `DX10` via `Archive2.exe` (`56` `.dds` textures across all `4` weapons & `3` ammo types) |
| `assets/meshes/fo4sf/weapons/baton/fo4_baton.nif` | `9,937` | `bc86420f4e293525a8ecb33a7424e07702446e033255f4ea8d76ceb6fbdd22d9` | Hierarchical Fallout 4 `Baton` BS-173 mesh (`3` telescoping shapes) |
| `assets/meshes/fo4sf/weapons/10mm/fo4_10mmpistol.nif` | `12,525` | `9c656214512c89ac3e965e58274d672dd337132c1aebc313389e9f46d38d9ed0` | Hierarchical Fallout 4 `10mm Pistol` BS-173 mesh (`8` shapes on FO4 pivots) |
| `assets/meshes/fo4sf/weapons/lasermusket/fo4_lasermusket.nif` | `15,928` | `839161fc29bdb50709fe43dd9e5799b6e265fe6819ffa328ffffca5101ef3010` | Hierarchical Fallout 4 `Laser Musket` BS-173 mesh (`17` opaque shapes on FO4 pivots) |
| `assets/meshes/fo4sf/weapons/minigun/fo4_minigun.nif` | `12,187` | `010bbb3a19bfc493d70fd0f1cc5bb18d395ce69082109b515fdd22a11b25ebe1` | Hierarchical Fallout 4 `Minigun` BS-173 mesh (`6` opaque shapes on FO4 pivots) |
| `assets/meshes/fo4core/ammo/10mm/10mmammo.nif` | `7,135` | `a08ee05fc4746300669d52c503c8b5836657457be65f7f9fe4b80472efd58f09` | Fallout 4 `10mm Round` BS-173 world pickup mesh |
| `assets/meshes/fo4core/ammo/laserammo/microfusioncell.nif` | `6,881` | `0801bc2abab80ca0914a04b3e298190a52cdab2ebf4518631ff267158ad1dcaf` | Fallout 4 `Fusion Cell` BS-173 world pickup mesh |
| `assets/meshes/fo4core/ammo/5mm/5mmammo.nif` | `7,144` | `006cd6aef3a20addd387e21dcd77dcbe7149c00babc16bbd857f8be5c18677c8` | Fallout 4 `5mm Round` BS-173 world pickup mesh |

```bash
python scripts/probes/stage_r11_p5_weapons.py verify --stage-dir <p5-stage-dir>
python scripts/probes/stage_r11_p5_weapons.py install --stage-dir <p5-stage-dir> --starfield <starfield-dir>
python scripts/probes/stage_r11_p5_weapons.py status --starfield <starfield-dir>
```

### Exact One-Line Undo / Rollback Command (Game Closed)
```bash
python scripts/probes/stage_r11_p5_weapons.py uninstall --starfield <starfield-dir>
```

---

## `< 200 m`/Axis Exterior Hop Table (Optional Daylight Stills — Max `70.75 m`/Axis)

| Hop / Batch | From -> To (Merged Exterior Coords, m) | `|dx|` (m) | `|dy|` (m) | `|dz|` (m) | Max Axis (m) | `< 200 m`/axis |
|---|---|---:|---:|---:|---:|---|
| `bat p5h1` | Sanctuary bench `(-2329.25, -1420.19, 112.09)` -> mid-hop `(-2400.00, -1413.00, 120.00)` | `70.75` | `7.19` | `7.91` | **`70.75`** | PASS |
| `bat p5e` | `p5h1` `(-2400.00, -1413.00, 120.00)` -> Vault 111 hilltop `(-2467.78, -1406.93, 127.85)` | `67.78` | `6.07` | `7.85` | **`67.78`** | PASS |

---

## Ordered Probe `P5` Pass-Gate Matrix (All 4 Weapons — `TEST-STATION`)

Run from a New Game in `FO4Port_Vault111Cryo` (or `bat p5o` to jump directly into Vault 111; `bat p5g` is fallback grant for existing saves). Verify `fo4sf_r11p5.0.log` already contains `FO4SF_R11P5 init ...` from game start BEFORE running any `SetStage`!

| # | Weapon | Pickup by Hand -> Into Hand | 1stP + 3rdP Stills | Sights / Melee Swing | Full Magazine / Charge & Reload | Target Kill (`30 HP` Unarmed Dummy via `E` or `bat p5t`) | Inventory Name & Zero Donor Leak |
|---|---|---|---|---|---|---|---|
| 1 | **`Baton`** (`0x00089A`) | `bat p5b1` (cryo table `0x0019891C`) & `bat p5b2` (crate `0x000AE470`): press **`E`** -> auto-equips into hand (`pickup weapon=baton equipped=true`) | 1stP + 3rdP stills (`FO4` baton mesh, no `RescueAxe` head) | Melee block/swing (`RescueAxe` 1H chop **stand-in**) | N/A (melee) | Spawn target (`E` on trigger or `bat p5t`), walk up, swing Baton (`10` dmg x `3` swings) -> **`target_killed weapon=baton ... baton_kill=true`** | `"Baton"`, `0` `"Rescue Axe"` |
| 2 | **`10mm Pistol`** (`0x000899`) | `bat p5d`: press **`E`** on shelf pistol (`0A000820`) + `48` rounds (`0A000821`) -> auto-equips into hand (`pickup weapon=10mm equipped=true`) | 1stP + 3rdP stills (`FO4` 10mm hierarchy, no `XM2311` parts) | Hold RMB (ADS) still — usable sightline, zero receiver clip | Fire `12` rounds (`full_mag_12_proven=true`), reload `0/12 -> 12/12` (`XM2311` **stand-in** anim/SFX) | Reset target (`E` or `bat p5t`), shoot `2` shots (`18` dmg x `2`) -> `target_killed weapon=10mm` | `"10mm Pistol"` + `"10mm Round"`, `0` `"XM2311"` / `".45 Caliber"` |
| 3 | **`Laser Musket`** (`0x00089D`) | `bat p5r`: press **`E`** on floor `Laser Musket` (`04000814`) + `3x24` `Fusion Cell` boxes (`04000815..0817`) -> auto-equips (`pickup weapon=lasermusket equipped=true`) | 1stP + 3rdP stills (`FO4` musket stock/barrel/crank/sights, no `Orion` parts) | Hold RMB (ADS) still — iron sights usable | Fire full `2`-shot capacity (`full_charge_proven=true`), reload from `72`-cell reserve (`Orion` **stand-in** anim/SFX) | Reset target (`E` or `bat p5t`), shoot (`30` energy dmg -> `1` shot kill) -> `target_killed weapon=lasermusket` | `"Laser Musket"` + `"Fusion Cell"`, `0` `"Orion"` / `"3KV LZR"` |
| 4 | **`Minigun`** (`0x0008A0`) | `bat p5r`: press **`E`** on floor `Minigun` (`04000818`) + `500x` `5mm Round` (`04000819`) -> auto-equips (`pickup weapon=minigun equipped=true`) | 1stP + 3rdP stills (`FO4` 6-barrel cluster & ammo drum, no `Microgun` parts) | Hold RMB (ADS / hip brace) still | Fire sustained burst (`>= 10` rounds, `burst_5mm_proven=true`) + reload (`Microgun` **stand-in** anim/SFX) | Reset target (`E` or `bat p5t`), fire burst (`8` dmg x `4` hits) -> `target_killed weapon=minigun` | `"Minigun"` + `"5mm Round"`, `0` `"Microgun"` / `"7.77mm"` |
| 5 | **Final Scorecard** | Run `bat p5s` (`SetStage <XX>000820 30`) | Open Inventory (`Weapons` + `Ammo`) still | Confirm `0` `<nullptr form>` in `Papyrus.0.log` | Confirm `baton_kill=true`, `ranged_kill=true`, `full_mag_12_proven=true`, `full_charge_proven=true`, `burst_5mm_proven=true` | `donor_leaks=0` |

```console
bat p5b1
bat p5b2
bat p5d
bat p5o
bat p5r
bat p5t
bat p5g
bat p5h1
bat p5e
bat p5s
bat p5q
getstage 11000820
sqs 11000820
```

```bat
; <starfield-dir>/p5b1.txt — FO4 Baton #1 (0x0019891C) on Vault 111 cryo table
player.setpos x -2.37
player.setpos y 27.55
player.setpos z -1.83
player.setangle z 0

; <starfield-dir>/p5b2.txt — FO4 Baton #2 (0x000AE470) on Vault 111 crate
player.setpos x -17.55
player.setpos y 13.65
player.setpos z -1.83
player.setangle z 270

; <starfield-dir>/p5d.txt — Vault 111 armory cage shelf (10mm Pistol + 48x 10mm Round)
player.setpos x -55.40
player.setpos y 29.80
player.setpos z 0.15
player.setangle z 278

; <starfield-dir>/p5o.txt — direct coc into Vault 111 armory cage shelf
coc FO4Port_Vault111Cryo
player.setpos x -55.40
player.setpos y 29.80
player.setpos z 0.15
player.setangle z 278

; <starfield-dir>/p5r.txt — Overseer range pickup bay (Laser Musket + 3x24 Cells, Minigun + 500x 5mm)
player.setpos x -53.20
player.setpos y 29.80
player.setpos z 0.15
player.setangle z 180

; <starfield-dir>/p5t.txt — face east on firing line & spawn/reset unarmed 30-HP dummy
player.setpos x -53.20
player.setpos y 29.80
player.setpos z 0.15
player.setangle z 90
SetStage 11000820 20

; <starfield-dir>/p5g.txt — fallback grant all 4 weapons + ammo
SetStage 11000820 10

; <starfield-dir>/p5h1.txt — exterior mid-hop toward Vault 111 hilltop (<75 m/axis)
player.setpos x -2400.00
player.setpos y -1413.00
player.setpos z 120.00
player.setangle z 275

; <starfield-dir>/p5e.txt — exterior Vault 111 hilltop daylight clearing (<70 m/axis)
player.setpos x -2467.78
player.setpos y -1406.93
player.setpos z 127.85
player.setangle z 90

; <starfield-dir>/p5s.txt — write full scorecard summary to fo4sf_r11p5.0.log
SetStage 11000820 30

; <starfield-dir>/p5q.txt — quick quest stage query
getstage 11000820
sqs 11000820
```

---

## Required PASS Log Lines (`fo4sf_r11p5.0.log`)

```log
FO4SF_R11P5 init source=<on_init|on_quest_init> moving_parts=hierarchical_ninodes_preserved anim_audio_standin=RescueAxe_0x04F760,XM2311_0x24561C,Orion_0x2773C8,Microgun_0x0546CD
FO4SF_R11P5 pickup weapon=baton count=1 equipped=true
FO4SF_R11P5 pickup weapon=10mm count=1 equipped=true
FO4SF_R11P5 pickup weapon=lasermusket count=1 equipped=true
FO4SF_R11P5 pickup weapon=minigun count=1 equipped=true
FO4SF_R11P5 target_spawned ok=true source=<trigger_activate|stage_20> unarmed=true restrained=true cage_door_opened=true hp=30.0 pos=<x> <y> <z> dist=<d>
FO4SF_R11P5 target_killed weapon=baton hits=<n> kills_total=<k> baton_kill=true killer=<killer>
FO4SF_R11P5 ammo_delta ammo=10mm prev=<p> now=<n> fired=<d> fired_total=<tot> full_mag_12_proven=true
FO4SF_R11P5 ammo_delta ammo=cell prev=<p> now=<n> fired=<d> fired_total=<tot> full_charge_proven=true
FO4SF_R11P5 ammo_delta ammo=5mm prev=<p> now=<n> fired=<d> fired_total=<tot> burst_5mm_proven=true
FO4SF_R11P5 summary tag=stage_30 cell=<cell> pos=<x> <y> <z> equipped=<tag> baton=<bCnt> pistol_10mm=<pCnt> laser_musket=<lmCnt> minigun=<mgCnt> ammo_10mm=<a10> ammo_cell=<aCell> ammo_5mm=<a5> shots_10mm=<s10> shots_cell=<sCell> shots_5mm=<s5> full_mag_12_proven=true full_charge_proven=true burst_5mm_proven=true target_hits=<h> target_kills=<k> baton_kill=true ranged_kill=true donor_leaks=0
```

## Negative / FAIL Conditions (`P5`)
- Any `<nullptr form>` VMAD error on `ArmoryCageDoor` (`0x001539`) in `Papyrus.0.log`, or `fo4sf_r11p5.0.log` failing to write `init` automatically at game start (`DNAM != 0x00000009`).
- Any weapon failing to auto-equip on pickup, showing Starfield donor geometry (`RescueAxe`, `XM2311`, `Orion`, `Microgun`), showing purple/missing textures, or leaking donor items/names in inventory (`donor_leaks != 0`).
- Target dummy firing back (`unarmed=false`) or failing to die/reset between Baton melee kill and ranged kills.
- Any modification to `candidate-2g`, `candidate-2g-fix`, `candidate-2g-fix2`, `r11-p1-museum`, or `r11-p4-10mm`, or any `.esm` hardlinked (`st_nlink > 1`).
