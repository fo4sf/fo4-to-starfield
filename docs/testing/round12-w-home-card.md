# Round 12 Test Card — `w-home-v2` Earth Host Swap, `Starfield.exe+0x2540dc6` StarMap Fix & Pip-Boy MAP Slices 3–4

> - **Date / Scope:** 2026-11-24 | `w-home-v2` (`Round 13 Task 6` — `#858` linearly rebased onto `#852` `3d831267` + shared `probe_common` `6f929402`) | Branch `gemini/r13-w2-whome`
> - **Version Tag:** `<W_HOME_VERSION_TAG>`
> - **NEW GAME needed:** YES (launch a fresh **New Game** after installing `w-home-v2` over the `candidate-2g-fix4` player base)
> - **Merge Order:** `#854 > #852 > #851 > #853 > #857 > #864 > #858 > #842 > #848 > #860 > #863`
> - **Gate Rule:** Keep shipped/bundle defaults **`MapBlockStarMap=0`** and **`MapSurvival=0`** in `sfse/FO4SFPipboyMenu/FO4SFPipboyMenu.ini` and `scripts/ui/make_pipboy_stage_ini.py`; the `w-home-v2` probe INI sets **`MapBlockStarMap=1`** and **`MapSurvival=0`** exclusively to verify the `Starfield.exe+0x2540dc6` fix in game.
> - **Status:** `STAGED — OFFLINE VERIFIED (w-home-v2 manifest f255e8463bab9d88038e87ef4bc67f2b3f886a27372f45e59d248e1e202e13c9, UNPROVEN IN GAME)`

---

## 0. Preconditions Before Install & Run (`F5`)

- **Base Bundle:** `candidate-2g-fix4` **player** profile installed cleanly in `<STARFIELD_DIR>` (`FO4TerrainCore.esm`, `FO4SFNewGame.esm`, `FO4SFMission.esm` + assets, `FO4ActorRaider.esm`, etc.).
- **Optional Probes Uninstalled:** **P1 v2**, **P2**, **P5**, and **P6** are **uninstalled** cleanly before installing `w-home-v2`.
- **Base `FO4Port.esm` vs Concord Museum Dependency (`F4`):** `w-home-v2` ships **base `FO4Port.esm`** (`4,261,852 B`, `sha256: 07756819ecf7ab9a88af6421478c7c05f13eb6dbef062a1a61b98ec63e7bbe60` from `candidate-2g-fix4`), **not** P1 v2's appended `77ab885e...`. Concord Museum (`0x0100EDEC`) requires `P1 v2` / `2h` and is **gated** on a clean `P1 v2` **PASS** (its 24 Nov run did not pass). Step 6 below tests an interior present on base `FO4Port.esm` (`FO4Port_Vault111Cryo` `0x010011F3` via the Vault 111 return lift).
- **Game Process State:** `Starfield.exe` is **CLOSED** before staging, installing, or uninstalling (verified via `check_starfield_not_running`).
- **Save State:** Launch a fresh **New Game** after install.

---

## 1. Install, Verify, Status & Rollback (`probe_common` Atomic Stager — `<STARFIELD_DIR>` Closed)

All staging lives in `<W_HOME_V2_PROBE>` (never inside a Git worktree, never inside frozen `candidate-*` / `r11-p*` / `w-home` directories). Requires `>= 60 GiB` free space on the target drive and `Starfield.exe` stopped. `probe_common.install_probe` stamps `--card` **before** any file, backup, or `Plugins.txt` mutation and emits a `RuntimeWarning` without rollback if `--card` is missing (`F3`).

```powershell
# 1. Stage w-home-v2 probe (checks Starfield.exe closed, PapyrusCompiler, FO4SFHome Sol/Earth build, 310-marker store,
#    <180m/axis collision+BTD hops, zero-M/N/V P3 batches, BA2 packing & hash verify, CoreValues --commonwealth-weather 0, zero-Mars census)
python scripts/probes/make_whome_probe.py stage `
  --starfield "<STARFIELD_DIR>" `
  --out "<W_HOME_V2_PROBE>" `
  --baseline-dir "<CANDIDATE_2G_FIX4_PLAYER>" `
  --port "<BASE_FO4PORT_ESM>" `
  --map-markers "<MAP_MARKERS_ESM>" `
  --pipboy-dll "<BUILT_PIPBOY_DLL>" `
  --pipboy-build-json "<BUILT_PIPBOY_BUILD_JSON>" `
  --mission "<REBUILT_MISSION_ESM>" `
  --newgame "<CANDIDATE_2G_FIX4_PLAYER>/FO4SFNewGame.esm" `
  --mission-scripts-dir "<REBUILT_MISSION_SCRIPTS>" `
  --newgame-scripts-dir "<CANDIDATE_2G_FIX4_03_NEWGAME_SCRIPTS>" `
  --core "<CANDIDATE_2G_FIX4_PLAYER>/FO4TerrainCore.esm"

# 2. Offline verify staged w-home-v2 package (manifest SHA-256, st_nlink==1, F14 Sol/FO4SF_EarthPlanetData, P3/hops, BA2s, base FO4Port.esm)
python scripts/probes/make_whome_probe.py verify --dir "<W_HOME_V2_PROBE>" --require-base-port --starfield "<STARFIELD_DIR>" --core "<CANDIDATE_2G_FIX4_PLAYER>/FO4TerrainCore.esm" --baseline-dir "<CANDIDATE_2G_FIX4_PLAYER>"

# 3. Install atomically into <STARFIELD_DIR> (checks candidate-2g-fix4 baseline, backs up swapped files, activates Home stack, unticks FO4TerrainCore_Mars.esm)
python scripts/probes/make_whome_probe.py install --dir "<W_HOME_V2_PROBE>" --starfield "<STARFIELD_DIR>" --version-tag "<W_HOME_VERSION_TAG>" --card "docs/testing/round12-w-home-card.md"

# 4. Check receipt & file/plugin integrity
python scripts/probes/make_whome_probe.py status --starfield "<STARFIELD_DIR>"

# 5. Roll back byte-for-byte after testing (restores Plugins.txt including *FO4TerrainCore_Mars.esm and every swapped file)
python scripts/probes/make_whome_probe.py uninstall --starfield "<STARFIELD_DIR>"
```

---

## 2. Offline Disassembly & Fix Summary (`Starfield.exe+0x2540dc6` — Null Read + Latent Refcount UAF)

Read-only PE/Capstone inspection of `Starfield.exe` (`ImageBase 0x140000000`) around `RVA +0x2540dc6`:

- **Exact Function:** `REL::ID 130446` (`UI::ProcessMessages`), `RUNTIME_FUNCTION` `0x14253fe10..0x14254148a` (`RVA 0x253fe10..0x254148a`, size `0x167a`), direct caller `0x141890e3d`, reading `UI::Singleton` (`RVA 0x5fd9b80`) and `UI::menuMap` (`UI+0x470`, entry stride `0x38`).
- **Root Cause (`null read + latent refcount UAF`, `F15`):**
  1. On `kShow` (`0x142540d28..0x142540d45`), `entry.initFunc(&temp)` fills `[rbp-50h]` raw without `AddRef` and immediately calls `Scaleform::Ptr::Release(temp)` (`lock xadd [rcx+8], -1`).
  2. When `*a_out` was left empty (`+0xB0` missing / `nullptr`), `0x142540d97 -> 0x142540dc6` executed `mov rax, qword ptr [rdx+0B0h]` with `rdx == 0` (**null-pointer read**), and with `ctorRefs == 1` the temporary release dropped `refCount 1 -> 0` (**latent refcount UAF**).
- **Preserved `#852` + Rebuilt `#858` Fix (`FO4SFPipboyMenu.dll`, `1,455,104 B`, `sha256: d6d761689acaca2cc0cc068200e7561b353c5540f531432061484d971d1f753c`, `build.json` `sha256: efa5c30b...`):**
  1. **Preserves all `#852` (`8fed4642`) game-tested Pip-Boy edits (`F9`):** Keeps `D5`, `D7`, and `HideStarfieldWatch=1` channel handling intact in `sfse/FO4SFPipboyMenu/src/main.cpp`.
  2. **`CreateBlockedMapMenuInstance` (`src/main.cpp`):** Increments `refCount 1 -> 2` via `InterlockedIncrement(refs)` when `ctorRefs == 1`, keeping the self-hiding `BlockedMapMenu` (`+0xB0` set) alive past `0x142540d40` until `UI::HideMenu` releases it once.
  3. **`BlockedMapMenuCreateForSlot` & `InstallStarMapBlock` (`src/pipboy_map.cpp`):** Eliminated empty-pointer fallback across all `16` slots (`0..15`), requires non-null `g_blockedFactoryFn`, saves original creators in `g_origMapMenuCreators[slot]`, and intercepts `Map`, `QuickMap`, `SurfaceMap`, `PlanetMap`, `GalaxyMap`, `StarMap`, `LocalMap`, and `OpenMap`.
  4. **`SurfaceMap` menu status (`F10`):** `SurfaceMap` remains guarded in `kMapUserEvents` as defensive input blocking; at install time `FO4SFPipboyMenu.log` (`step=starmap_block_install`) logs `found=0/1` for `SurfaceMap` alongside `GalaxyStarMapMenu` (`slot=0`) depending on UI menu-map registration state.

---

## 3. Offline Host-Swap, Mission `F8` & Swapped File Inventory (`F1`, `F4`, `F7`, `F8`, `F13`, `F14`, `F15`)

- **`FO4SFHome.esm` & `FO4TerrainCore_Home.esm` (`F14`, `F13`):** Registers `FO4Core_Commonwealth` (`FO4TerrainCore.esm:0x000803`) exclusively on `FO4SF_EarthPlanetData` (`FO4SFHome.esm:0x000805`, `PNDT`, renamed to avoid `Starfield.esm:0x0005DEB5` `EarthPlanetData`) in system display **`Sol`** (`FO4SFHomeStar` `0x000800` / `SFO4SFHome` `0x000801`, `FULL = "Sol"`, zero `"FO4SF "` prefix), HUD planet name **`Earth`**, breathable O2/1g/temperate traits, zero fauna/flora/resources, and all `5` `WL1` hand-scanner / PCM / random-ship exclusion keywords. `cross_plugin_check.py` drops nonexistent `0x80B`/`0x80D` on `#858` (`F13`). `FO4TerrainCore.esm` and base `FO4Port.esm` remain byte-identical.
- **Zero Mars Weather (`F11`) & All-Quest Persistent Anchor Resolution (`F7` + `F8`):**
  - `make_whome_probe.py` passes `*weather_flags` (`--commonwealth-weather 0`) to `make_core_values.main(...)` (`F11`), giving `0` overrides of `ClimateUniqueCydonia` (`0x00310DB1`), `ClimateUniqueCydoniaFrozen` (`0x002EDEA5`), or `ATMO_Mars` (`0x0000C9D2`).
  - `FO4SFMission.esm` (`88,670 B`, `sha256: 2c3f0e730dbb18bb8fec63e0a7fabf968d3ca40ffd989863c8185f3ee09a60e3`, rebuilt on `#852` `3d831267` with `2g-fix4` weapons/outfits, Codsworth + `C5` actor looks, zero `WRLD` overrides, holding cell `0x000B60`) and **all** `11` quest/newgame scripts (`FO4SF_NewGameQuest`, `FO4SF_Min00Quest` with zero `UnequipAll`, `FO4SF_Sanctuary01Quest`, `FO4SF_MQ103Quest`, `FO4SF_MinRecruit00Quest`, `FO4SF_MQ104Quest`, `FO4SF_MQ105Quest`, `FO4SF_MQ106Quest`, `FO4SF_MQ203Quest`, `FO4SF_MQ204Quest`, `FO4SF_MQ206Quest`) resolve the live Commonwealth `WorldSpace` from persistent `0x0A775B` (`FO4Core_CommonwealthMapMarkerVault111`) **first**, falling back to `0x005C50` (`FO4Core_SanctuaryWorkbenchRef`), with **zero** static `0x000803` `WRLD` lookups or `MarsPlanetWorld` references.
- **Re-Parenting & Zero-Mars Census (`probe_manifest.json` `sha256: f255e8463bab9d88038e87ef4bc67f2b3f886a27372f45e59d248e1e202e13c9`, `66` files, all `st_nlink == 1`, `5/5` BA2s verified):** `FO4TerrainCore_Home.esm` overrides both `FO4Core_CommonwealthLocation` (`0x000802`) and `FO4Port_InteriorsLocation` (`0x00E18A`) to `PNAM = FO4SFHome.esm:0x000804` (`SFO4SFHome_PEarth_Surface`), keeping all `16/16` base `FO4Port` child chains rooted under Earth (`0` `MarsPlanetData` or `SSol_PMars_Surface` winning refs).

### Swapped & Added Files in `w-home-v2` (`F1` & `F4` — Complete `66`-File Inventory)

| Target Path in `<STARFIELD_DIR>` | Action | Exact Source / Notes | Size (B) / SHA-256 |
|---|---|---|---|
| `Data/FO4Port.esm` | Swap | Base `FO4Port.esm` (`candidate-2g-fix4`, NOT P1 v2 append `77ab885e`) | `4,261,852` / `07756819ecf7ab9a88af6421478c7c05f13eb6dbef062a1a61b98ec63e7bbe60` |
| `Data/FO4SFMapMarkers.esm` | Swap | Starfield map markers master (`310` markers) | `77,406` / `b8677959caee00c452cda16434af9474a81d15a9e1bdc8cd2c7ba37b926404ec` |
| `Data/FO4SFCoreValues.esm` | Swap | Built with `--commonwealth-weather 0` (`F11`, `70` records) | `6,946` / `c2e3a3a69a1f2fc72151f30146c06147c1c221e534e76a9ab0c521b38886e73c` |
| `Data/FO4SFMission.esm` | Swap | Rebuilt on `#852` `3d831267` (`2g-fix4` Codsworth + C5 + `0x0B60`, zero `(Stand-In)`) | `88,670` / `2c3f0e730dbb18bb8fec63e0a7fabf968d3ca40ffd989863c8185f3ee09a60e3` |
| `Data/FO4SFMission - Main.ba2` + `12` Mission `Data/Scripts/*.pex` | Swap | Compiled on `3d831267` (`2g-fix4` `Min00`) + `F7`/`F8` persistent `0x0A775B` (`MinRecruit00`, `MQ103`–`MQ206`) | `192,313` / `3bde1d280f62cd9e8bf4fb01b65c45ad1a4ff01c357ba4008dad2f8c96a44dce` |
| `Data/FO4SFNewGame.esm` + `FO4SFNewGame - Main.ba2` + `4` NewGame `.pex`s | Swap | `candidate-2g-fix4` (`03-newgame`, `1b` Quick Start + `ResolveHostWorld` `0x0A775B` first) | `12,688` / `0163600cbbe974a0344a858ddd483472a59e90b079632b394bac535cbd9d50f2` (BA2 `73,495` / `a89bf762...`) |
| `Data/SFSE/Plugins/FO4SFPipboyMenu.dll` | Swap | Rebuilt `#852` (`D5`/`D7`/`HideStarfieldWatch=1`) + `#858` StarMap fix | `1,455,104` / `d6d761689acaca2cc0cc068200e7561b353c5540f531432061484d971d1f753c` |
| `Data/SFSE/Plugins/FO4SFPipboyMenu.build.json` | Swap | `F15` build provenance JSON (`null read + latent refcount UAF`) | `2,275` / `efa5c30b5b23d032c5a5f05b979172da35b130856142e423b83b6b319752d3be` |
| `Data/SFSE/Plugins/FO4SFPipboyMenu.ini` | Swap | Probe INI (`Stage=2`, `Map=1`, `MapBlockStarMap=1`, `MapSurvival=0`) | `2,232` / `f416750496c77e378b378df3816c058e17abfb87ee80675e82b762758127f5c4` |
| `Data/SFSE/Plugins/FO4SFPipboyMapMarkers.tsv` | Swap | `310` rows (incl. Diamond City `idx=309` -> `0x000800`) | `26,687` / `1533bd7e9899d0b712e6456903c84a3bff89ebba895713929b8dc2335c426fb0` |
| `Data/FO4SFPipboyTravel.esm` + `FO4SFPipboyTravel - Main.ba2` + `FO4SF_PipboyTravel.pex` | Swap | Rebuilt `w-home-v2` travel stub + compiled PEX | `1,362` / `ab06612e89434b0b3ebf07b83bdf790090386236c576750b8c819cc5c9b4c0f5` (BA2 `4,894` / `f1209837...`) |
| `Data/FO4SFHome.esm` + `FO4SFHome - Main.ba2` (`2,292 B`) + `FO4SFHome - Textures.ba2` (`961,356 B`) + `.biom`/`.mat`/`.dds` | Add | `F14`: display star **`Sol`**, `FO4SF_EarthPlanetData` `PNDT`, `WB1`–`WB3` | `8,763` / `153269f38fc6830e80ebfa8b3e902081572938a8f085f2e934cbd68e742c840d` |
| `Data/FO4TerrainCore_Home.esm` | Add | Overrides `0x000802` + `0x00E18A` -> `Earth`, `Plugins.txt` unticks `FO4TerrainCore_Mars.esm` | `7,925` / `2c3e26ae048efa692c4c07384117fa45e40e19b4e59ce2064dd0134a4ac5d16f` |
| `bat/*.txt` -> `<STARFIELD_DIR>\*.txt` (`26` batch files) | Add | `w1`–`w4`, `k1`–`k8` (`F2`), `ktg`, `ea`–`ej`, `we1`, `we2` (`F5`), `r1` | Validated `<180 m`/axis, `0` `M`/`N`/`V` |

---

## 4. In-Game Verification Plan (`w-home-v2`, P3 Safe — Zero `M`/`N`/`V` Console Typed)

> **Exterior `<180 m`/axis hops & god-mode batch (`F2`, `F5`):** Toggle god mode with `bat ktg` before long chains; use `bat w1`..`bat w4`, `bat k1`..`bat k8` (`ground_z + 2.5 m` verified against `FO4TerrainCore.esm` BTD + converted collision NIFs; `k3` clears rooftop mesh, `k7` sits on ground at `z=12.60`, `k8` stands `5.15 m` SW of `DmndGateREF` door), and `bat ea`..`bat ej` -> `bat we1` -> `bat we2` (`64`-cell west edge). Every batch filename stem and every console command omits `m`, `n`, `v`.
> **Video & Audio Rule (`F6`):** Real clip names use `1 fps` / slowed takes where noted; **`audio: not judged`** during headless/visual clip inspection.

| Step | Action / Command | Expected Result | VIDEO | Status |
|---|---|---|---|---|
| 1 | Launch game -> **New Game** -> clear cryo pod -> exit Vault 111 lift to surface | Spawn in **Earth / Commonwealth** (star system **`Sol`**, planet HUD **`Earth`**, breathable O2 HUD, zero Starfield fauna/flora/resources, `FO4SFHomeGroundDirt01` outer ring); log shows `step=map_config ... block_starmap=1 ... survival=0`, `step=starmap_block_install ... slot=0` (and `SurfaceMap` `found=0/1` per `F10`), and `Vault 111` discovered (`idx=2`) | Pending clip: `r13_whome_step1_host_hud` (`1 fps` + full-motion lift, `audio: not judged`) | Not Run |
| 2 | **5 tries each** (`F5`): press **`M`** (`5x`), open **`DataMenu`** Starmap tile (`5x`), press **`G`** (`5x`), and run **`bat r1`** in console (`5x`); also press **`F`** (hand scanner) | Hand scanner blocked (`blocked input=handscanner`); across all `20` star-map triggers (`M` x5, `DataMenu` x5, `G` x5, `bat r1` x5), **zero** `+0x2540dc6` crashes (`null read + latent refcount UAF` fixed), `step=starmap_blocked ... non_null=1` logged cleanly, and `FO4SF_PipboyMenu` MAP opens cleanly | Pending clip: `r13_whome_step2_starmap_5tries` (`1 fps` + interactive input capture, `audio: not judged`) | Not Run |
| 3 | Run `bat ktg`, then step **`bat w1`** (`-2353.83, -1440.36, 112.76`), **`bat w2`**, **`bat w3`**, **`bat w4`** (`-2014.45, -1694.40, 89.89`) -> open MAP (`M`) after each | **Sanctuary Hills** (`idx=1`), **Red Rocket** (`idx=0`), **Concord** (`idx=3`), and **Museum of Freedom** (`idx=240`, ground `z ~ 89.89`) flip to **discovered** and render markers cleanly on MAP | Pending clip: `r13_whome_step3_w1_w4_discovery` (`1 fps`, `audio: not judged`) | Not Run |
| 4 | Chain **`bat k1`** .. **`bat k8`** (`F2`: `k3` clears roof; `k7` at `(-1495.06, -2952.20, 12.60)` NOT on `26.35 m` roof; `k8` at `(-1420.86, -3131.89, 21.93)`, `5.15 m` SW off `DmndGateREF`) -> open MAP | Smooth `<180 m`/axis hops (`max_drop <= 2.5 m`), player lands outside Diamond City Gate facing gate, **Diamond City** (`idx=309`) discovers cleanly | Pending clip: `r13_whome_step4_k1_k8_dcgate` (`1 fps` + slowed take, `audio: not judged`) | Not Run |
| 5 | In Pip-Boy **MAP** (`Stage=2`, `MapSurvival=0`), fast-travel **Diamond City -> Vault 111 -> Sanctuary Hills -> Red Rocket -> Museum of Freedom -> Diamond City** | Every fast-travel hop lands in **Earth / Commonwealth** without triggering Starfield's star map (`FO4SF_PipboyTravel.0.log` `step=go`, `FO4SFHome` intact) | Pending clip: `r13_whome_step5_map_fast_travel` (`1 fps`, `audio: not judged`) | Not Run |
| 6 | Check reachable base **`FO4Port.esm` (`07756819`) interior transition** (`F4`): enter Vault 111 return lift (`ExitMessage`) into **`FO4Port_Vault111Cryo` (`0x010011F3`)**, then exit back to Commonwealth exterior (*Concord Museum `0x0100EDEC` is gated on `P1 v2` PASS*) | Interior cell parent chain resolves cleanly via `FO4Port_InteriorsLocation` -> `FO4SFHome` Earth (`0` Mars HUD/O2 artifacts); `0` crashes on entry or return | Pending clip: `r13_whome_step6_port_vault111_interior` (`1 fps`, `audio: not judged`) | Not Run |
| 7 | **64-cell west edge probe (`F5`):** from `Vault111`, run **`bat ktg`** -> **`bat ea`** .. **`bat ej`** -> **`bat we1`** (`-4350.00, -1394.72, 312.90`, inside `-4400` edge) -> **`bat we2`** (`-4460.00, -1394.72, 312.90`, `60 m` outside west edge) | Crossing the west `64`-cell border lands on **Earth outer-ring ground (`FO4SFHomeGroundDirt01`, breathable O2 HUD)** — **zero** red/Mars ground bleed outside the world boundary | Pending clip: `r13_whome_step7_west_edge_we1_we2` (`1 fps`, `audio: not judged`) | Not Run |
| 8 | **Complete `2g-fix4` opening through Stage 200 (`F1`, `F5`):** Sanctuary **Codsworth** talk (`FO4SF_Codsworth01`, verify ground under Codsworth dialogue camera) -> Concord **5 raiders** -> **Preston** (`FO4SF_Min00` Stage `200`, `SCEN 0x990`/`0x9C0`, `FO4SF_Sanctuary01`) | Real Codsworth & Preston dialogue (zero fallback lines), Codsworth's FO4 animations/look render with **zero Mars ground bleed** beneath camera, all 5 Concord raiders wear stripped FO4 outfits + weapons (`#856`/`2g-fix4`), pistol/ammo work cleanly | Pending clip: `r13_whome_step8_2g_fix4_opening_st200` (`1 fps` + dialogue camera close-up, `audio: not judged`) | Not Run |
| 9 | **Cold Reload (`F5`):** Save after Stage `200`, quit Starfield completely, relaunch game, load that save (**cold reload**), inspect pistol/ammo/dead raiders, and reopen Pip-Boy MAP | Host stays **Earth / `Sol`**, pistol, ammo, dead raiders, and quest stage `200` persist cleanly across cold reload; Pip-Boy MAP + fast travel work with zero crash | Pending clip: `r13_whome_step9_cold_reload` (`1 fps`, `audio: not judged`) | Not Run |

### P3 Console Batch Reference (`<STARFIELD_DIR>\*.txt` installed via `w-home-v2`)

```console
bat ktg
bat w1
bat w2
bat w3
bat w4
bat k1
bat k2
bat k3
bat k4
bat k5
bat k6
bat k7
bat k8
bat ea
bat eb
bat ec
bat ed
bat ee
bat ef
bat eg
bat eh
bat ei
bat ej
bat we1
bat we2
bat r1
```

---

## Claude's Additions

| Addition | Ref | Status | Note | What Next |
|---|---|---|---|---|
| **Codsworth & Mr. Handy** | `#854` | `gated (#854 merge)` | `candidate-2g-fix4` carries Codsworth body/voice (`#854`); `#858` rebuild keeps `#852` `3d831267` Mission + Codsworth dialogue ground camera check | Merge `#854` before `#852`/`#858` per merge order; verify ground under Codsworth in `w-home-v2` Step 8 |
| **Creatures (Radroach)** | `#855` | `gated (S2 track / #855)` | Standalone Commonwealth creature spawns are outside `w-home-v2` host-swap delta | Verify in `candidate-2h` / `r12-t1b-s2s6` S2 run |
| **Humans (Anims / Raiders / Settlers)** | `#856` | `not applicable` | Standard Starfield human animation pipeline on `candidate-2g-fix4` (`0` custom human animation edits or `WRLD`/`Mars` overrides in `w-home-v2`) | Confirm Concord Raiders / Preston host cleanly on Earth |
| **Gun Moving Parts** | `gun_*.af` | `gated (weapon pack / #859)` | Moving-part gun rig (`gunpart`) is built into dedicated weapon packs outside `w-home-v2` host-swap scope | Keep outside `w-home-v2` scope; verify on weapon card |
| **Gun Sounds** | `SNDR` | `not applicable` | Outside `w-home-v2` host-swap scope (`0` `SNDR`/sound-bank edits or plans; custom bank remains **ON HOLD**) | Leave audio banks untouched on `w-home-v2` |
