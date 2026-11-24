# Round 11 Probe P2 — Concord Roof Power Armor, T-45 Stand-In, Fusion Core Gate & Vertibird Minigun Test Card

> **NEW GAME needed** — Start a **NEW GAME** after installing Probe P2 over `candidate-2g-fix4` (`player` profile) and activating `FO4SFCoreValues.esm`, `FO4SFPowerArmor.esm`, and `FO4SF_R11P2PowerArmor.esm`.
> - **Version Tag:** `p2-v2` (recorded in install receipt `.fo4sf_probe_r11_p2_powerarmor.json` with `live_prefix` & `quest_form_id`; `install` never mutates this tracked card).
> - **Bundle Status:** Probe P2 (`r12-p2-powerarmor-v2`, stacked onto `#853`) — **OFFLINE ONLY — UNPROVEN IN GAME** until owner playtest/OBS recording (`VIDEO` column below).
> - **P3 Console Rules:** Batch filenames and typed console commands avoid `m`, `n`, `v` (`bat p2h1`, `bat p2h2`, `bat p2r`, `bat p2f`, `bat p2g`, `bat p2w`, `bat p2d`, `bat p2c`, `bat p2x`, `bat p2s`, `bat p2q`) and stripped mod EDIDs.

## 1. Probe Scope, Baseline, Swapped Files & Preconditions

- **Probe ID:** `r11-p2-powerarmor` (`FO4SF_R11P2PowerArmor.esm` + `FO4SFCoreValues.esm` + `FO4SFPowerArmor.esm`, `0` `WRLD`/`PNDT`/exterior `CELL` overrides).
- **Baseline Target (`P2-F4`):** **`candidate-2g-fix4` (`player` profile)**. Installing onto `test`, `candidate-2g-fix2`, or `candidate-2g-fix3` emits a baseline mismatch warning.
- **Files Swapped & Added on Install:**
  - **Swapped (`allow_swap=True`):** `Data\FO4SFCoreValues.esm`, `Data\FO4SFPowerArmor.esm`, `Data\Scripts\FO4SF_PowerArmorCoreQuest.pex`. (`--include-sfse` stays OFF by default so `candidate-2g-fix4`'s tested `7d5ba49c` `FO4SFPipboyMenu.dll` & `FO4SFPipboyMenu.ini` remain untouched.)
  - **Added:** `Data\FO4SF_R11P2PowerArmor.esm`, `Data\FO4SF_R11P2PowerArmor - Main.ba2`, `Data\FO4SF_R11P2PowerArmor - Textures.ba2`, `Data\Scripts\FO4SF_R11P2Quest.pex`, and `11` P3-clean batch files (`p2h1.txt`, `p2h2.txt`, `p2r.txt`, `p2f.txt`, `p2g.txt`, `p2w.txt`, `p2d.txt`, `p2c.txt`, `p2x.txt`, `p2s.txt`, `p2q.txt`).
  - **CoreValues Records Note:** Staged `FO4SFCoreValues.esm` (`127` records) inherits `#853`'s `0x00089F` (`FO4_Ammo5mm`) and `0x0008A0` (`FO4_Minigun`) alongside the full CoreValues record set (including Mars weather overrides `CLMT` `0x00310DB1`/`0x002EDEA5` and `ATMO` `0x0000C9D2` present in `FO4SFCoreValues.esm`).
- **Preconditions & New Game Route (`P2-F4`):**
  1. Close `Starfield.exe` (`Starfield.exe == 0`) and keep `>= 60.0 GiB` free on the target drive before staging or installing.
  2. **Uninstall Rule:** Run `uninstall` before any candidate install or update (`Data\.fo4sf_probe_r11_p2_powerarmor.json` restores every swapped file & `Plugins.txt` byte-for-byte).
  3. **New Game Route:** Start a **NEW GAME** (`Vault 111 Cryo Pod` -> exit Vault 111 -> Sanctuary Hills). From Sanctuary (`(-2329.00, -1420.00, 99.00)`), walk or run `bat p2h1` then `bat p2h2` to reach Concord Museum street front (`(-2012.50, -1697.94, 88.70)`).
  4. **Concord Raiders Dead Precondition:** Clear/ensure **all Concord street raiders are dead** before running roof rows (`P2-01`..`P2-08`); 24 Nov game runs showed Concord street/door gunfire can kill an unarmored player in `< 30 s`.
- **FO4 Roof Power Armor Frame & Duplicate Suppression (`P2-F1`, `P2-F2`, `P2-F3`):**
  - Rebuilds Concord Museum roof `REFR 000370E3` (`FURN 0019DED9`) on `FO4SFPowerArmor.esm:0x000801` using converted `Meshes\Furniture\PowerArmor\CharacterAssets\PowerArmorFurniture.nif`.
  - **Live Slot Prefix (`P2-F1`):** All `SetStage` batches (`p2r`, `p2f`, `p2g`, `p2w`, `p2d`, `p2c`, `p2x`, `p2s`, `p2q`) use placeholder `XX000820` while staged and are stamped at `install` time via `probe_common.stamp_batch_formid_prefix` / `compute_full_master_load_index` (skipping light `FE` / medium `FD` plugins; e.g. `11000820` on `candidate-2g-fix4` Bridge-off, never hardcoded `07000820`). `install` prints `"live_prefix"` & `"quest_form_id"` and records both in the install receipt.
  - **Terrain Duplicate Disable (`P2-F2`):** Both `FO4SF_R11P2Quest.psc` and `FO4SF_PowerArmorCoreQuest.psc` resolve `FO4TerrainCore.esm` non-persistent `0x008913` (`FO4Core_powerarmorfurniture`) and `0x005119` (`Vertibird Minigun` ACTI) when the Concord roof cell loads, call `DisableNoWait(false)` on both, and log `terrain_dupes_disabled frame_static=... minigun_acti=...`.
  - **Persistent Roof Sync (`P2-F3`):** Event-driven (`OnPlayerLoadGame`, `OnLocationChange`) + continuous `2.0 s` proximity poll (no `180 s` / 90-tick cutoff!) + `Stage 20` fallback syncs roof placements on late arrival or save reload.
  - **In-World Exit Activator (`P2-F1 exit`):** `Power Armor Exit Terminal` (`FO4SF_P2_ExitActi 0x000803`, visible converted FO4 `StandingTerminal01.nif` `pa_exit_terminal.nif`, NOT an editor marker) is placed on the roof beside arrival (`0x000813` at `(-1992.20, -1725.60, 97.44)`) and on Concord street near the drop zone (`0x000814` at `(-1995.00, -1735.00, 86.90)`) with prompt `[E] Exit Power Armor`.
- **Fusion Core Gate (`0x0809`), T-45 Stand-In (`0x0802`), Fall Perk (`0x081E`) & Minigun (`0x08A0`/`0x089F`):**
  - Entry refuses with HUD message + `entry_refused ... reason=no_fusion_core` when charge `<= 0` and held `Fusion Core` (`0x000809`) count `== 0`. Spare `Fusion Core` sits on the roof at `(-1993.50, -1723.40, 97.56)` between `p2r` arrival and the PA frame.
  - T-45 chest/helmet/arms/legs + `frame`/`frame_exo` equip on `FO4SF_PowerArmorRace` (`0x000802`, `RACE.NAM4 = 0x0009150B`); `0` `"FO4SF "` FULL prefixes; `0` template `INRD`/`OBTE`/`MOD2`/`MOD4`.
  - `FO4SF_PANoFallDamagePerk` (`0x00081E`, `ModFallingDamage Set 0`) prevents fall damage in PA; both `FO4SF_R11P2Quest` and `FO4SF_PowerArmorCoreQuest` log `hp_before=` and `hp_after=` (`HealthAV 0x0002D4`) on drops, compared against unarmored control drop `bat p2c` from the exact same spot `(-1995.73, -1738.00, 104.54)`.
  - Vertibird Minigun (`0001F582`/`0001F583`) at `(-2004.72, -1715.40, 102.68)` grants `1x FO4_Minigun` (`0x0008A0`, `fo4_minigun.nif` w/ `MiscA01` barrels & `Magazine` drum) + `1,200x FO4_Ammo5mm` (`0x00089F`, `wt=0.009`).
- **Stand-In Disclosure (Labelled):**
  - Entry/exit uses scripted `FadeOutGame` + equip/unequip (`fade_equip_standin`), and worn T-45 pieces use `HumanRace` bone-rebound meshes until true PA skeleton/animations land.
  - Starfield's own HUD, inventory/item cards, pause/main menus, and audio are labelled Starfield **stand-ins** (`#32` — judge function only: HUD notifications, grants, and HP bar changes register with no blank/wrong text or lockup; do not judge look/style; `audio: not judged`).

## 2. Stage, Verify, Install & Uninstall Commands (Game Closed)

```powershell
python scripts/probes/stage_r11_p2_powerarmor.py stage --stage-dir <PROBE_STAGE_DIR> --fo4-data <FO4_DATA_DIR> --starfield-dir <STARFIELD_DIR> --core-values <CORE_VALUES_ESM> --weapons-assets <WEAPONS_ASSETS_DIR> --tested-pipboy-dll <PIPBOY_DLL> --clean
python scripts/probes/stage_r11_p2_powerarmor.py verify --stage-dir <PROBE_STAGE_DIR>
python scripts/probes/stage_r11_p2_powerarmor.py install --stage-dir <PROBE_STAGE_DIR> --starfield-dir <STARFIELD_DIR>
# Inspect live_prefix & quest_form_id in install stdout / <STARFIELD_DIR>/Data/.fo4sf_probe_r11_p2_powerarmor.json
python scripts/probes/stage_r11_p2_powerarmor.py status --starfield-dir <STARFIELD_DIR>
# Revert cleanly before any candidate update:
python scripts/probes/stage_r11_p2_powerarmor.py uninstall --starfield-dir <STARFIELD_DIR>
```

## 3. Concord Exterior Travel Hops (`< 200 m / axis`) & P3-Clean Batches

Live `quest_form_id` (`<live_prefix>000820`, printed by `install`) is stamped automatically into `p2r`, `p2f`, `p2g`, `p2w`, `p2d`, `p2c`, `p2x`, `p2s`, `p2q` (`0` `m`/`n`/`v` in any batch filename or console line):

| Hop / Batch | From Anchor | Target `(x, y, z)` | `max(\|dx\|,\|dy\|,\|dz\|)` | Purpose |
|---|---|---|---|---|
| `bat p2h1` | `sanctuary_wb` `(-2329.00, -1420.00, 99.00)` | `(-2170.00, -1560.00, 102.00)` | `159.00 m` | Exterior mid-hop toward Concord |
| `bat p2h2` | `mid_hop_1` `(-2170.00, -1560.00, 102.00)` | `(-2012.50, -1697.94, 88.70)` | `157.50 m` | Concord Museum street front (`concord_marker`) |
| `bat p2r` | `concord_marker` | `(-1990.58, -1724.19, 97.56)` | `26.25 m` | Museum roof landing (`0002C1C6` XTEL beside `000370E3`) + sync + disable `FO4TerrainCore` dupes |
| `bat p2w` | `concord_marker` | `(-2004.72, -1717.00, 102.40)` | `19.06 m` | Perch next to Vertibird minigun + grant `1x Minigun + 1,200x 5mm` |
| `bat p2d` | `concord_marker` | `(-1995.73, -1738.00, 104.54)` | `40.06 m` | Armored roof drop (`~18 m` above street `z~86.5`; `Stage 75` + `setpos`, `hp_before`/`hp_after`) |
| `bat p2c` | `concord_marker` | `(-1995.73, -1738.00, 104.54)` | `40.06 m` | Unarmored control drop from exact same spot after exiting PA (`Stage 80` + `setpos`, `hp_before`/`hp_after`) |

Typed console sequence (Sanctuary -> Concord street -> Roof, raiders cleared first, all `0` `m`/`n`/`v`):

```console
bat p2h1
bat p2h2
bat p2r
```

And step-by-step roof, minigun, armored drop, in-world exit, and control drop checks:

```console
bat p2f
bat p2g
bat p2f
bat p2w
bat p2d
bat p2c
bat p2q
```

## 4. Verification Matrix (`VIDEO` Required)

| Check ID | Batch / Input | Expected In-Game & Log Behaviour | Result | VIDEO |
|---|---|---|---|---|
| `P2-01` | `bat p2r` on roof (raiders cleared) | Player lands on solid Museum roof at `(-1990.58, -1724.19, 97.56)` facing PA frame `(-1995.73, -1723.10, 97.54)`, spare `Fusion Core` at `(-1993.50, -1723.40, 97.56)`, `Power Armor Exit Terminal` at `(-1992.20, -1725.60, 97.44)`, `Vertibird Minigun` at `(-2004.72, -1715.40, 102.68)`. Both logs show `terrain_dupes_disabled frame_static=... minigun_acti=...` (`0` ghost dupes). | `OFFLINE ONLY — UNPROVEN IN GAME` | `needed (<date>/p2-01-roof-arrival.mp4 — 1 fps walk around roof; PASS: player stands on roof, single frame/minigun/exit terminal/core visible; FAIL: off-roof fall or duplicate frame/minigun; audio: not judged)` |
| `P2-02` | `[E]` roof frame (or `bat p2f`) w/ `0` cores | Entry refused cleanly: HUD `"Fusion Core required to enter Power Armor (0 cores)."` + `FO4SFPACore.0.log` `entry_refused reason=no_fusion_core` | `OFFLINE ONLY — UNPROVEN IN GAME` (offline unit test PASS) | `needed (<date>/p2-02-zero-core-refusal.mp4 — aim & press E on frame; PASS: HUD refusal shown and player stays unarmored; FAIL: climbs in with 0 cores; audio: not judged)` |
| `P2-03` | Pick up spare `Fusion Core` (or `bat p2g`), then `[E]` frame / `bat p2f` | Scripted `fade_equip_standin` equips inner frame/exo + T-45 chest/helm/arms/legs (`0` `"FO4SF "` FULL prefix), `FO4SF_PowerArmorRace` `NAM4=0x0009150B`, core charge active & draining, standing roof frame disappears cleanly (`0` `0x01008913` ghost left behind). | `OFFLINE ONLY — UNPROVEN IN GAME` | `needed (<date>/p2-03-enter-t45.mp4 — pick core, enter frame, 3rdP orbit; PASS: single frame vanishes, full T-45 suit visible, no ghost frame; FAIL: leftover static frame or missing armor piece; audio: not judged)` |
| `P2-04` | `[E]` Vertibird Minigun (or `bat p2w`) | Activator hides cleanly (`0` `0x01005119` ghost left behind); grants `1x Minigun` (`0x0008A0`) + `1,200x 5mm Round` (`0x00089F`); `fo4sf_r11p2.0.log` logs `minigun_grabbed count_minigun=1 count_5mm=1200`. | `OFFLINE ONLY — UNPROVEN IN GAME` | `needed (<date>/p2-04-minigun-pickup.mp4 — aim & press E on Vertibird Minigun; PASS: minigun disappears completely with HUD/inventory grant; FAIL: second static minigun stays on Vertibird; audio: not judged)` |
| `P2-07` | Equip `Minigun` (`0x0008A0` + `5mm` `0x00089F`) & fire burst | Minigun equips in 1st/3rdP and fires `5mm` rounds cleanly; `MiscA01` barrels & `Magazine` drum rig/geometry visible during sustained fire (`fo4sf_r11p2.0.log` `eq_weapon=` on `bat p2q`). | `OFFLINE ONLY — UNPROVEN IN GAME` | `needed (<date>/p2-07-minigun-fire-slowed.mp4 — **slowed take** watching MiscA01 barrels & Magazine drum during trigger pull; PASS: rounds fire and barrels/drum stay attached or spin cleanly; FAIL: detached/invisible parts or no fire; audio: not judged)` |
| `P2-05` | Armored drop (`bat p2d` from `(-1995.73, -1738.00, 104.54)` to street `z~86.5`) | `0` fall damage taken in Power Armor (`0x00081E` `ModFallingDamage Set 0`). Logs report `fall_long` / `drop_settled` with `inpa=True`, `no_fall_perk=True`, `hp_before=<n>`, `hp_after=<n>` (`hp_lost=0.0`). | `OFFLINE ONLY — UNPROVEN IN GAME` (offline perk+script PASS) | `needed (<date>/p2-05-armored-drop.mp4 — 1 fps clip from drop ledge to street landing; PASS: player lands on street with unchanged HP bar; FAIL: player takes HP damage or lands on roof; audio: not judged)` |
| `P2-06` | `[E]` on `Power Armor Exit Terminal` (street or roof; `bat p2x` fallback) | In-world exit (`p2_inworld_exit_activate`) leaves standing PA frame behind player, restores worn gear & race, preserves core charge, removes `0x00081E` (`no_fall_perk=False`). | `OFFLINE ONLY — UNPROVEN IN GAME` (offline unit test PASS) | `needed (<date>/p2-06-inworld-exit.mp4 — aim at StandingTerminal01 Exit Terminal and press E; PASS: player exits without console, standing frame remains; FAIL: invisible marker or stuck in PA; audio: not judged)` |
| `P2-08` | Unarmored control drop (`bat p2c` from exact same `(-1995.73, -1738.00, 104.54)`) then `bat p2q` | Unarmored drop from the exact same spot takes real fall damage (`inpa=False`, `no_fall_perk=False`, `hp_after < hp_before` in `fo4sf_r11p2.0.log` & `FO4SFPACore.0.log`), proving `0x00081E` caused `P2-05` immunity; `bat p2q` writes full summary. | `OFFLINE ONLY — UNPROVEN IN GAME` | `needed (<date>/p2-08-control-drop.mp4 — unarmored drop after P2-06; PASS: visible HP drop / fall reaction on street landing; FAIL: 0 HP lost unarmored; audio: not judged)` |

## 5. Offline Build & Cross-Plugin Contract Receipts

- **FormIDs Registered (`src/fo4sf/core/cross_plugin_check.py`):**
  - `FO4SFCoreValues.esm`: `0x00089F` (`AMMO FO4_Ammo5mm`), `0x0008A0` (`WEAP FO4_Minigun`) — **inherited from `#853` (`FO4SFCoreValues.esm` + `cross_plugin_check.py`) and verified against built `FO4SFCoreValues.esm` at stage time**.
  - `FO4SFPowerArmor.esm`: `0x000801` (`FURN FO4SF_PowerArmorFrameFurn`), `0x000802` (`RACE FO4SF_PowerArmorRace`, `NAM4=0x0009150B`), `0x000805` (`QUST FO4SF_PowerArmorCoreQuest`), `0x000809` (`MISC FO4SF_FusionCore`), `0x000816..0x000819` + `0x00082A..0x00082D` (PA frame + T-45 pieces), `0x000830..0x000837` (PA ARMAs), `0x00081E` (`PERK FO4SF_PANoFallDamagePerk`).
  - `FO4SF_R11P2PowerArmor.esm`: `0x000801` (`ACTI FO4SF_P2_MinigunActi`), `0x000802` (`CELL FO4SF_P2_HoldingCell`), `0x000803` (`ACTI FO4SF_P2_ExitActi`), `0x000810..0x000814` (`PERSISTENT REFR`s incl. `RoofExitRef`/`StreetExitRef`), `0x000820` (`QUST FO4SF_R11P2Quest`).
  - `FO4TerrainCore.esm`: `0x005119` (`REFR FO4Core_VertibirdMinigunRef`), `0x008913` (`REFR FO4Core_PowerArmorFurnitureRef`).
- **Build & SHA-256 Receipts (`<PROBE_STAGE_DIR>/manifest.json` `sha256 ac1655c0bce8c291c5822b315c8e7511ab74f35fe7990b0374afe84b5dfc0a3e` — staged for `r12-p2-powerarmor-v2` on integrated `#853` `c7127121`):**
  - `core/FO4SFCoreValues.esm`: `76,995` bytes (`sha256 5b788a97006cc5e3d97847f9ca6b35a5567d380404356c75b3a8c05e0ff9cb5c`)
  - `core/FO4SFPowerArmor.esm`: `85,768` bytes (`sha256 4b33acea762e9c3acfc7b4c1a97a106f302c2f908122d8448e1511206653bba0`)
  - `exp/FO4SF_R11P2PowerArmor.esm`: `1,788` bytes (`sha256 db001531b1607548c7d0ba0f8a6b78d4c4a197fa4f9f701e8abd66fa2fdca756`)
  - `exp/FO4SF_R11P2PowerArmor - Main.ba2`: `2,889,353` bytes, `70` entries (`sha256 ac0f02dcbc17db12c90be95d4cb014b9fd4a9638ec1854ca98abf4872325d9a4`)
  - `exp/FO4SF_R11P2PowerArmor - Textures.ba2`: `93,517,314` bytes, `74` entries (`sha256 4161db6927012a3f765a4ac32b2f862810c8435c5fdd4d959e97bad17bc6509f`)
  - `FO4SF_PowerArmorCoreQuest.pex`: `sha256 5101116ec10d3107a5c393a2ae6938200da0955fb7ec2cd79f114023edabe38b`
  - `FO4SF_R11P2Quest.pex`: `sha256 f7534ee162eb412faa3ba1a86b0fd521edac12d8083dbb1dd4be375aa7e1a727`
  - `sfse/SFSE/Plugins/FO4SFPipboyMenu.dll`: `1,453,568` bytes (`sha256 7d5ba49c0c6ab2aa8db24ab1bfb643839259d12404cc95afaa38e2f42201c9a8`, tested binary reused without rebuild)

## 6. Claude's Additions

| Addition | PR / Track | Integration Status | Boundary / Detail in Probe P2 |
|---|---|---|---|
| **Robot animations & Codsworth** | `#854` (`claude/robot-anim`) | `not applicable` | Codsworth / Mr. Handy robot animations are unused in Probe P2. |
| **Creature animations** | `#855` (`claude/creature-anim`) | `not applicable` | Radroach / Deathclaw creature rigs and animations are unused in Probe P2. |
| **Human animations** | `#856` (`claude/human-anim`) | `not applicable` | `#856` human-anim sprint/idle is unused here; true Power Armor climb-in/walk animations are `gated (on future PA skeleton/anim track)` (P2 uses labelled `fade_equip_standin` and human-bone T-45 stand-ins). |
| **Gun moving parts / part-node contract** | `#853` (`fo4_part_map` + `Gun_*.af`) | `built in` | `FO4_Minigun` (`0x0008A0`) carries `fo4_minigun.nif` with `MiscA01`, `Magazine`, `ProjectileNode`, `Minigun_Barrel` + `fo4_minigun_controllers.json` inherited from `#853`. |
| **Gun sounds / SNDR banks** | `#32` (`sound-bank-study`) | `gated (on per-item sound-bank loading fix)` | On hold: keeps labelled Starfield stand-in audio (`SNDR` banks not overridden; `audio: not judged`). |
