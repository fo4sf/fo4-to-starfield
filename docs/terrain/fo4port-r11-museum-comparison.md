# Round 11 Step 3b + 3c — Lossless `FO4Port.esm` Museum & Pre-War Vault 111 Extension Comparison

> **Verification status:** **OFFLINE ONLY — UNPROVEN IN GAME** (Rule R15). All binary comparisons, navmesh conversions, BA2 delta merges, and Papyrus compilations were verified offline on PC without launching `Starfield.exe` or modifying Starfield's live `Data` folder.

## 1. Objective & Design

Extend the proven `doors_anim_b00` `FO4Port.esm` baseline with two story-critical interiors from `interiors_b10` — **`FO4Port_ConcordMuseum01`** (Museum of Freedom, *When Freedom Calls*) and **`FO4Port_PrewarVault111`** (pre-war cryo wing, *War Never Changes*) — plus the converted Starfield v17 **`NAVM` + `NAVI` (`0x00000FF1`)** for `FO4Port_ConcordMuseum01` and a **minimal asset/texture delta** merged directly into `FO4Port - Main.ba2` and `FO4Port - Textures.ba2`:

- **Builder & self-verifier:** [build_fo4port_r11_museum.py](../../scripts/terrain/build_fo4port_r11_museum.py)
- **Confirmed-arrival load-door bridge:** [FO4SF_ConfirmedLoadDoor.psc](../../scripts/doors/FO4SF_ConfirmedLoadDoor.psc)
- **Automated test suite (CI-safe + live staging):** [test_r11_fo4port_museum.py](../../tests/test_r11_fo4port_museum.py)

Why a lossless raw-record appender instead of shipping `interiors_b10/port/FO4Port.esm` directly:

1. `doors_anim_b00/port/FO4Port.esm` (`4,261,852 B`, `55,071` non-`TES4` records, max local FormID `0x00E199`) is the exact master pinned by `FO4SFNewGame.esm`, `FO4SFVaultGearDoor.esm`, and `FO4SFExitLift.esm`.
2. In `interiors_b10/port/FO4Port.esm`, at least one reused door record — **`0x0100693B` (`FO4Port_paintedwooddoordoubleload01`, Museum of Freedom front double door)** — lost its `BGSAnimationGraph_Component` (`SimpleOpenClose01.agx`, `skeleton.rig`, `animations`, `DOSH`, `DCSH`). Preserving all `55,071` baseline records byte-for-byte keeps `b00`'s animated door graph intact.
3. Shipping `interiors_b10` bulk archives adds `1.75 GiB` of unrelated textures plus a second `FO4PortTextures2.esm` companion stub plugin (`+1` plugin). Tracing only the transitive dependencies of `FO4Port_ConcordMuseum01` and `FO4Port_PrewarVault111` adds only **`4.43 MiB` packed** to `FO4Port - Main.ba2` and **`126.33 MiB` packed** to `FO4Port - Textures.ba2` — keeping the single `FO4Port - Textures.ba2` at **`2.132 GiB`** (well below the `4.0 GiB` BA2 ceiling) with **`0` companion stubs** and **`+0` extra plugins**.

---

## 2. Lossless Binary Comparison Proof (`doors_anim_b00` vs Extended Output)

| Metric | Baseline (`doors_anim_b00`) | Extended Output (R11 3b+3c v2 / Slot 1) | Diff / Status |
|---|---:|---:|---|
| `FO4Port.esm` size | `4,261,852 B` | `4,612,735 B` | `+350,883 B` (`+342.7 KiB`) |
| `FO4Port.esm` SHA-256 | `07756819ecf7ab9a88af6421478c7c05f13eb6dbef062a1a61b98ec63e7bbe60` | `8163ca9a7187bd07fdd09f20ad7c16d511577f91d91c858ed28ec0fc434fef39` | Deterministic (`v2` Slot 1: `LTMP 0x0006BCF8`, `XLOC 25` + `XLKR`, persistent `0x0100E35E..0x0100EFAA`) |
| `TES4` masters (`MAST`) | `['Starfield.esm']` | `['Starfield.esm']` | Identical (`local_prefix = 0x01`) |
| Non-`TES4` records | `55,071` | `58,571` | `+3,500` (`244` base + `2` `CELL` + `3,252` `REFR` + `1` `NAVM` + `1` `NAVI`; `0` `WRLD`/`PNDT`) |
| Max local FormID (`0x01xxxxxx`) | `0x00E199` | `0x00EFAA` (`NextObjectID = 0x00EFAB`) | All new local IDs strictly `>= 0x00E200`; Slot 2 starts cleanly at `>= 0x00EFAB` |
| **Missing baseline FormIDs** | — | **`0`** | **PASS** |
| **Baseline record type (`sig`) changes** | — | **`0`** | **PASS** |
| **Baseline header/body byte changes** | — | **`0`** (all `55,071` records byte-identical) | **PASS** |
| **Dangling local FormID references** | — | **`0`** | **PASS** |
| Reused `(sig, EDID)` records from `b00` | — | `445` (`1` body diff preserved as `b00`: `0x0100693B`) | **PASS** |
| Independent walker check (`overlay_records.walk_plugin`) | `55,071` | `58,569` (`masters=['Starfield.esm']`) | **PASS** |

---

## 3. Existing Plugin `FO4Port.esm` FormID Dependency Audit

Every `FO4Port.esm` FormID referenced across the active candidate plugins (`candidate-2g` player stack and staged map markers) sits strictly in `0x01000800 .. 0x0100E199` and is preserved **100% byte-identical**:

| Plugin | Lists `FO4Port.esm` as Master? | Referenced `FO4Port.esm` FormIDs | Record Role & Preservation Status |
|---|---|---|---|
| `FO4SFNewGame.esm` | **Yes** (master index `0x01`) | `0x010011F3` (`CELL FO4Port_Vault111Cryo`) | Cell override + `GRUP(6)` child anchor container — **preserved byte-identical** |
| `FO4SFNewGame.esm` | **Yes** | `0x0100E195` (`LCTN FO4Port_Vault111Location`) | `CELL.XLCN` reference — **preserved byte-identical** |
| `FO4SFNewGame.esm` | **Yes** | `0x01001338` (`REFR` persistent COC/vault anchor in `FO4Port_Vault111Cryo`) | Runtime `QUST.VMAD` `VaultAnchorId = 0x001338` (`plan.json` `anchor.id = "001338"`) — **preserved byte-identical** |
| `FO4SFNewGame.esm` | **Yes** | `0x0100126D` (`REFR` cog door in `FO4Port_Vault111Cryo`) | Runtime `QUST.VMAD` cog-door activation target (`plan.json` `cog_door.ref = "00126D"`) — **preserved byte-identical** |
| `FO4SFNewGame.esm` | **Yes** | `0x01001319` (`REFR` in `FO4Port_Vault111Cryo`) | Runtime `QUST.VMAD` `ConsoleRefId = 0x001319` — **preserved byte-identical** |
| `FO4SFNewGame.esm` | **Yes** | `0x01001616` (`REFR` in `FO4Port_Vault111Cryo`) | Runtime `QUST.VMAD` `PortPipboyStaticId = 0x001616` — **preserved byte-identical** |
| `FO4SFNewGame.esm` | **Yes** | `0x01001618` (`REFR` in `FO4Port_Vault111Cryo`) | Runtime `QUST.VMAD` `LiftId = 0x001618` — **preserved byte-identical** |
| `FO4SFNewGame.esm` | **Yes** | `0x0100E0E6` (`ACTI FO4Port_acti_0244ef_fallout4`) | Runtime `QUST.VMAD` `LiftBaseId = 0x00E0E6` (shared with `FO4SFExitLift.esm`) — **preserved byte-identical** |
| `FO4SFNewGame.esm` (A3 hand-play walk path) | **Yes** | `0x0100126E`, `0x01001234`, `0x01001608`, `0x01001607`, `0x01001609`, `0x0100160A`, `0x01001539` | Vault 111 corridor & Overseer `DOOR` `REFR`s in `FO4Port_Vault111Cryo` — **all preserved byte-identical** |
| `FO4SFVaultGearDoor.esm` | **Yes** (master index `0x01`) | `0x0100DEF9` (`DOOR FO4Port_VltGearDoor01`) | `DOOR` override supplying animated vault gear door model/graph — **preserved byte-identical** |
| `FO4SFVaultGearDoor.esm` | **Yes** | `0x0100126D` (`REFR` cog door placement) | Target reference documented in `01-cog-door/plan.json` (`ref = "00126D"`) — **preserved byte-identical** |
| `FO4SFExitLift.esm` | **Yes** (master index `0x01`) | `0x0100E0E6` (`ACTI FO4Port_acti_0244ef_fallout4`) | `ACTI` override supplying animated Vault 111 exit elevator platform (`StateA_Play` / `StateB_Play`) — **preserved byte-identical** |
| `FO4SFMapMarkers.esm` | **No** (`masters = ['Starfield.esm', 'FO4TerrainCore.esm']`) | None (`0`) | Exterior `FO4TerrainCore.esm` markers only — unaffected |
| `FO4SFMission.esm` | **No** (`masters = ['Starfield.esm', 'FO4TerrainCore.esm', 'FO4ActorRaider.esm']`) | None (`0` direct master refs today) | Future Museum entry/exit door scripts resolve new `>= 0x00E200` anchors at runtime via `Game.GetFormFromFile(..., "FO4Port.esm")` without altering any baseline FormID |

> **Note on SHA-256 master pins:** `FO4SFNewGame.esm`, `FO4SFVaultGearDoor.esm`, and `FO4SFExitLift.esm` record `FO4Port.esm`'s SHA-256 in their stage `plan.json` manifests (and `port_restore` / `exp_install` check master pins). Because every baseline FormID in `0x000800 .. 0x00E199` is byte-identical, no FormID re-mapping is required in any existing plugin; only the stage/bundle manifest pin updates when adopting the extended `FO4Port.esm`.

---

## 4. Newly Allocated FormIDs (`>= 0x00E200`)

All `3,497` new local records are allocated deterministically starting at **`0x0100E200`** (plus the `0x00000FF1` `NAVI` override record), replacing `interiors_b10`'s colliding IDs (`0x01012540` for `FO4Port_ConcordMuseum01` and `0x010107EA` for `FO4Port_PrewarVault111`):

### 4.1 Appended Cells, Persistent Anchors, and Museum Navmesh

| Record | EditorID / Role | Source `b10` FormID | New R11 FormID | Children / Notes |
|---|---|---|---|---|
| `CELL` | `FO4Port_ConcordMuseum01` | `0x01012540` | **`0x0100E2F4`** | `9` persistent `REFR`s (`0x0100E2F5`, `0x0100E35E`, `0x0100E3B6`, `0x0100EDEC`, `0x0100EDF0`, `0x0100EDF2`, `0x0100EDF5`, `0x0100EFA9`, `0x0100EFAA`) + `2,816` temp `REFR`s + `1` temp `NAVM` (`XLCN = 0x0100E2EF`, `LTMP = 0x0006BCF8`) |
| `REFR` (persistent) | `FO4Port_ConcordMuseum01` persistent cell anchor (`XMarker 0x00000032`) | `b10` persistent ref | **`0x0100E2F5`** | Target anchor for `FO4SF_ConfirmedLoadDoor` (`Direction = "in"`) |
| `REFR` (persistent, promoted `v2`) | `FO4Port_ConcordMuseum01` basement security gate (`0x0100E20B`, `XLOC 25`) | `b10` temp ref | **`0x0100EDF0`** | Promoted to persistent `GRUP(8)` (`flags |= 0x400`) with Starfield Novice level-25 `XLOC` (`0x19`, `flags=1`) so terminal `XLKR` and `Game.GetFormFromFile(0x00EDF0, "FO4Port.esm")` work reliably |
| `REFR` (persistent, promoted `v2`) | `FO4Port_ConcordMuseum01` basement security terminal (`0x0100E2EE`, `XLOC 25` + `XLKR -> 0x0100EDF0`) | `b10` temp ref | **`0x0100E35E`** | Promoted to persistent `GRUP(8)` with Novice level-25 `XLOC` + `XLKR` keyword link to gate `0x0100EDF0` |
| `REFR` (persistent, promoted `v2`) | `FO4Port_ConcordMuseum01` restroom Medkit (`0x0100DF07`, `CONT`) | `b10` temp ref | **`0x0100E3B6`** | Promoted to persistent `GRUP(8)` at `(-3.645, -21.717, 1.635)` for Story item injection (`FO4SF_Stimpak`) |
| `REFR` (persistent, synthesized `v2`) | `FO4Port_PrestonDoorREF` (`FO4Port_BldWoodPDoor02` `0x010066AF`, `XLOC 255`) | — (FO4 `0x0001E2EA`) | **`0x0100EFA9`** | Synthesized 3F locked door (`5.486, -7.314, 9.143`) for `S5` Preston confrontation reveal |
| `REFR` (persistent, synthesized `v2`) | `FO4Port_PrestonExitDoor` (`FO4Port_BldWoodPDoor01` `0x010066AE`, `XLOC 255`) | — (FO4 `0x0001E2E9`) | **`0x0100EFAA`** | Synthesized 3F exit door (`7.446, 5.354, 9.143`) for `S6` Museum interior room routing |
| `NAVM` (temp child #0) | `FO4Port_ConcordMuseum01` Starfield v17 navmesh | FO4 `0x00197BB0` | **`0x0100EFA8`** | First child of `GRUP(9)` under `0x0100E2F4` (vanilla Starfield convention) |
| `NAVI` (override) | `Starfield.esm` global singleton `NAVI` master record (`master index 0x00`, NOT a local `0x01xxxxxx` ID) | — | **`0x00000FF1`** | `NVER = 17`, `1` interior `NVMI` for `0x0100EFA8`, `NVPP` (`8` zero bytes); `b00` had `0` `NAVI` records, and CE2 merges `NVMI` entries across plugins alongside `FO4TerrainCore.esm` |
| `CELL` | `FO4Port_PrewarVault111` | `0x010107EA` | **`0x0100EDFB`** | `1` persistent `REFR` + `427` temp `REFR`s (`XLCN = 0x0100E2F0`, `LTMP = 0x0006BCF8`) |
| `REFR` (persistent) | `FO4Port_PrewarVault111` persistent cell anchor (`XMarker 0x00000032`) | `b10` persistent ref | **`0x0100EDFC`** | Target anchor for pre-war Vault 111 entry |

### 4.2 Notable Museum of Freedom Door & Gate `REFR`s (Remapped `>= 0x00E200`)

| Museum Door / Gate | New `REFR` FormID | Base `DOOR` FormID & EditorID | Interior Position (metres) | Animation Graph Status |
|---|---|---|---|---|
| **Front Entrance Double Door** (FO4 `0x00077D22`) | **`0x0100EDEC`** | `0x0100693B` (`FO4Port_paintedwooddoordoubleload01`, reused from `b00`, persistent) | `(9.143, 0.000, -0.914)` | **Animated (`b00` preserved):** `SimpleOpenClose01.agx` + custom `skeleton.rig` + `open/close.af` |
| **Basement Security Gate** (Fusion Core room) | **`0x0100EDF0`** | `0x0100E20B` (`FO4Port_switchdoorexsmlatch02_N84C71750`, net-new, persistent, `XLOC 25`) | `(-13.714, -0.457, -3.657)` | **Animated:** `SimpleOpenClose01.agx` + custom `switchdoorexsmlatch02` `skeleton.rig` + `open/close.af/.afx` |
| **2F Front Balcony Load Door** (FO4 `0x0001B94A`) | **`0x0100EDF2`** | `0x0100E207` (`FO4Port_bldwoodpdoorload01`, net-new, persistent, `XLOC 255`) | `(12.621, -0.014, 9.143)` | Load door (`MODL` + collision present; no swing graph needed for load transition) |
| **3F Roof Load Door** (FO4 `0x0002C1C6`, to Power Armor + Vertibird) | **`0x0100EDF5`** | `0x0100E207` (`FO4Port_bldwoodpdoorload01`, net-new, persistent) | `(-21.943, 9.143, 9.143)` | Load door (`MODL` + collision present; wired via `FO4SF_ConfirmedLoadDoor` `dir=out`) |
| **3F Preston Door** (FO4 `0x0001E2EA`) | **`0x0100EFA9`** | `0x010066AF` (`FO4Port_BldWoodPDoor02`, reused from `b00`, persistent, `XLOC 255`) | `(5.486, -7.314, 9.143)` | Synthesized persistent `DOOR` `REFR` for `S5` Preston confrontation unlock |
| **3F Preston Exit Door** (FO4 `0x0001E2E9`) | **`0x0100EFAA`** | `0x010066AE` (`FO4Port_BldWoodPDoor01`, reused from `b00`, persistent, `XLOC 255`) | `(7.446, 5.354, 9.143)` | Synthesized persistent `DOOR` `REFR` for `S6` exit path |

### 4.3 Net-New Non-`STAT` Base Records (`23` of `244` Net-New Base Forms; `221` are `STAT`)

- `ACTI (1)`: `0x0100E200` (`FO4Port_acti_092e6e_fallout4`)
- `CONT (1)`: `0x0100E201` (`FO4Port_cont_01f435_fallout4`)
- `DOOR (10)`: `0x0100E202` (`BRStallDoor01`), `0x0100E203` (`BRStallDoor02`), `0x0100E204` (`KitchenRefrigeratorDoor01`), `0x0100E205` (`V111Door01`), `0x0100E206` (`V111DoorSpecial01`), `0x0100E207` (`bldwoodpdoorload01`), `0x0100E208` (`bldwoodpdoorshutter01`), `0x0100E209` (`laddermetaltall01`), `0x0100E20A` (`metalgatefancy01`), `0x0100E20B` (`switchdoorexsmlatch02`)
- `MISC (2)`: `0x0100E20C` (`FO4Port_misc_00000a_fallout4`), `0x0100E20D` (`FO4Port_misc_178b5d_fallout4`)
- `FURN (1)`: `0x0100E2EB` (`FO4Port_furn_11807c_fallout4`)
- `TERM (3)` + `TMLM (3)`: `0x0100E2EC`/`0x0100E2F1` (`0731b1`), `0x0100E2ED`/`0x0100E2F2` (`07584e`), `0x0100E2EE`/`0x0100E2F3` (`08110c`) — each `TERM.DNAM` remapped cleanly to its paired `TMLM`
- `LCTN (2)`: `0x0100E2EF` (`FO4Port_ConcordMuseumLocation`), `0x0100E2F0` (`FO4Port_PrewarVault111Location`) — both `LCTN.PNAM` point to reused `b00` `FO4Port_InteriorsLocation`

---

## 5. Museum of Freedom `NAVM` Conversion & Walkability Audit

Source: Fallout 4 `ConcordMuseum01` (`0x00017DF7`) single interior `NAVM` (`0x00197BB0`), converted via `fo4sf.navmesh` (`layout="fo4"` -> Starfield v17 `NVNM` + `NVMI`):

| Metric | Value | Notes |
|---|---|---|
| Starfield `NAVM` FormID / Parent `CELL` | `0x0100EFA8` / `0x0100E2F4` | `world = 0x00000000`, `grid = None`, `NVNM` = `85,526 B`, `NVMI` = `86 B` |
| Vertices / Triangles | `2,062` / `2,002` | Scaled `/ 70.0` (FO4 units -> Starfield metres); bounds `[-30.839, -23.548, -3.603]` to `[12.571, 23.480, 15.273]` m |
| Internal edges / Open edges | `4,770` / `1,216` | Open-boundary `vertex_extra = 1`, interior `0` |
| Self-links (`type = 1/2` drop-down ledges) | `20` (`20/20` symmetric) | All `20` links (`10` pairs, `dz = 0.99 .. 2.95 m`) remapped `0x00197BB0 -> 0x0100EFA8`; `0` external links |
| Waypoints / Grid divisor | `115` / `12` | Starfield search grid rebuilt cleanly via `navmesh.build_grid` |
| Matched interior load-door triangles | **`3 / 3` at `0.00000 m`** | `tri 87` -> Front (`0x0100EDEC`), `tri 889` -> 2F Balcony (`0x0100EDF2`), `tri 873` -> 3F Roof (`0x0100EDF5`) |
| `navmesh.validate(..., world=0)` errors | **`0`** | Round-trip parsed from written `FO4Port.esm` (`NAVM` + `NAVI 0x00000FF1`) |
| Multi-floor `navmesh.triangle_path` connectivity | **All 3 pairs reachable** | Front (`87`) <-> 2F Balcony (`889`): `189` hops; Front (`87`) <-> 3F Roof (`873`): `229` hops; 2F Balcony (`889`) <-> 3F Roof (`873`): `54` hops |

---

## 6. Interior Inspection: `switchdoorexsmlatch02`, Lights, and `PrewarVault111` Pod Wing

1. **Basement Security Gate (`FO4Port_switchdoorexsmlatch02_N84C71750`, base `0x0100E20B`, ref `0x0100EDF0`) & Terminal (`0x0100E35E`):**
   - Placed at `(-13.714, -0.457, -3.657)` m inside `FO4Port_ConcordMuseum01` (basement Fusion Core generator alcove).
   - Carries a full Starfield `BGSAnimationGraph_Component` (`AnimTextData\Tables\Graphs\SimpleOpenClose01.agx`, `skeleton.rig`, `open.af`, `open.afx`, `close.af`, `close.afx`) and `FULL = "Security Gate"`. All animation files and referenced materials (`cagemetal01_d_328dbb2e.mat`, `cagemetal01.mat`, `cagemesh01.mat`) are present in the merged `FO4Port - Main.ba2`.
   - **Novice Lock & Terminal Link (P1v2 / S6):** `0x0100EDF0` (`MQ03SecurityGateREF`) is persistent and stamped with a Starfield **Novice lock (`XLOC` level `25`, `flags=1`)**; basement terminal `0x0100E35E` (`FO4Port_term_08110c_fallout4`, `TERM 0x0100E2EE`) is promoted to persistent with a matching Novice lock (`XLOC` level `25`) and `XLKR -> 0x0100EDF0` (mirroring Fallout 4 `0008110D -> 0005C66C`). Missing 3F quest doors `PrestonDoorREF` (`0001E2EA` at `(5.486, -7.314, 9.143)`) and `PrestonExitDoor` (`0001E2E9` at `(7.446, 5.354, 9.143)`) + 3F balcony door `0x0100EDF2` (`0001B94A`) are persistent with `XLOC` level `255` (`Inaccessible`) until quest progression unlocks them.
2. **Interior Lighting Comparison (`Fallout4.esm 0x00017DF7` vs Starfield `LTMP 0x0006BCF8` vs Legacy `0x00006658`):**
   - **Fallout 4 source (`ConcordMuseum01` `0x00017DF7`):** Uses `LGTM 0x0001C903` (`ConcordMuseumTemplate`: fog RGB `(37,43,48)` / far `(45,50,51)` at `1200..7500` units, `DALC` directional ambient `(33,40,46)` / `(37,44,48)` / `(17,19,21)` / `(55,66,74)`) plus `CELL.XCLL` ambient `(28,32,36)` and `75/65` clip settings.
   - **Starfield legacy converter output (`interiors_b10`):** Used `Starfield.esm` `LGTM 0x00006658` (`ShipInteriorLT`: `DATA` ambient `0x00000000` black + `DALC` all zeros), leaving unlit geometry nearly black while `189` `LIGH 0x0003D38C` (`LGT_ShipInterior_Omni_NS_Neutral_2k`) fixtures clipped highlights locally.
   - **Proven Starfield interior lighting (`FO4Port` extension):** Both `FO4Port_ConcordMuseum01` (`0x0100E2F4`, `189` `LIGH 0x0003D38C`) and `FO4Port_PrewarVault111` (`0x0100EDFB`, `117` `LIGH 0x0003D38C`) use **`LTMP = 0x0006BCF8` (`KreetBase01LGTtemplate`)** — proven in-game on `FO4Port_Vault111Cryo` (`0x010011F3`) with ambient `(40,36,23)` + `6`-axis white `DALC` (`0x00FFFFFF`), `DATA = 0x00000001`, `XCIM = 0x00122393`, and `XEMP = Data\Textures\Cubemaps\Cell_HiTechHallCube.dds`.
   - Note: All `55,071` baseline `doors_anim_b00` records remain **100% byte-identical** (`LTMP` override applies strictly to newly appended `0x0100E2F4` and `0x0100EDFB`).
3. **`FO4Port_PrewarVault111` Pod Wing:**
   - Contains **`428`** placements (`1` persistent `XMarker 0x00000032` at `0x0100EDFC` + `427` temp refs), including **`14` `FO4Port_CryoPod02`**, **`14` `FO4Port_CryoPodLever01`**, **`3` `FO4Port_V111DoorSpecial01_NE23F23A0`** (`0x0100E206`, animated `SimpleOpenClose01.agx`), `FO4Port_V111Door01_NE23F23A0` (`0x0100E205`, animated `SimpleOpenClose01.agx`), `4` `FO4Port_V111RadScanner01`, and the Vault 111 cryo pit walls/stairs/pipes.

---

## 7. Minimal Asset & Texture Delta (`FO4Port - Main.ba2` + `FO4Port - Textures.ba2`)

Lossless `BTDX` v2 streaming merge (zero re-compression of baseline entries; every added entry verified byte-for-byte against `interiors_b10` via `fo4sf.ba2.Ba2`):

| Archive | Baseline (`b00`) | Delta Added | Extended Output | Output SHA-256 | Notes |
|---|---:|---:|---:|---|---|
| `FO4Port - Main.ba2` (`GNRL` v2) | `16,063` entries (`113,009,991 B`, `107.77 MiB`) | `+960` entries (`+4,649,558 B` payload, `+4.43 MiB`) | **`17,023` entries (`117,755,711 B`, `112.30 MiB`)** | `064c762499a1cc975df81da2c12ea3a20aec5f84cae0c89f4d9cdac12d094c7e` | `228 .nif`, `662 .mesh`, `65 .mat`, `2 .af`, `2 .afx`, `1 .rig` (`2,004` of `2,964` traced files already in `b00`) |
| `FO4Port - Textures.ba2` (`DX10` v2) | `4,491` entries (`2,156,975,161 B`, `2.009 GiB`) | `+220` entries (`+132,467,670 B` payload, `+126.33 MiB`) | **`4,711` entries (`2,289,478,621 B`, `2.132 GiB`)** | `f4664dd0a4fb49a3adb17440596bbb936b0ffa47516024be9fff07c7b1a69a48` | `215` from `b10` `Textures.ba2` + `5` from `b10` `FO4PortTextures2 - Textures.ba2` (`994` of `1,215` traced textures already in `b00`; `1` vanilla Starfield texture `textures\common\paint\paintscuffed01_normal.dds`) |
| `FO4PortTextures2.esm` companion stub | `0` | **`0`** | **`0` (eliminated)** | — | Saves `~1.75 GiB` vs `interiors_b10`'s `3.60 GiB + 0.28 GiB` bulk archives; `+0` extra plugins |

---

## 8. Confirmed-Arrival Load-Door Script (`FO4SF_ConfirmedLoadDoor.psc` `v2`)

[FO4SF_ConfirmedLoadDoor.psc](../../scripts/doors/FO4SF_ConfirmedLoadDoor.psc) implements non-blocking two-way confirmed-arrival transitions for both Museum entry (`Direction = "in"`, e.g. Concord surface -> `0x0100E2F5` in `FO4Port_ConcordMuseum01`) and merged exterior exits (`Direction = "out"`, e.g. Museum front door `0x0100EDEC` or 3F roof door `0x0100EDF5` -> Concord surface on `FO4TerrainCore.esm`):

- **Non-blocking `StartTimer` / `Event OnTimer(int aiTimerID)` state machine:** `Event OnActivate(ObjectReference akActionRef)` accepts `akActionRef == player || akActionRef == None` (supporting both in-world `E` and console `<ref>.activate`), logs `FO4SF_LOADDOOR activate_begin` BEFORE `MoveTo`, calls `player.MoveTo(activeAnchor, 0.0, 0.0, 0.0, True, False)`, arms `StartTimer(GetPollInterval(), TIMER_ARRIVAL)`, and returns immediately so CE2 never stalls on an interior-cell unload (`dir=out` infinite loading screen fix).
- **Runtime primary + fallback anchor resolution:** Supports `DestinationAnchor`, `Game.GetFormFromFile(TargetFormId, TargetPlugin) as ObjectReference`, and optional `FallbackTargetPlugin` / `FallbackTargetFormId` (`FO4TerrainCore.esm:0x0A775B` Vault 111 surface fallback) on retry.
- **Merged exterior `coreCell` verification & no-bounce-back retry (modeled on `FO4SF_NewGameQuest.FinishSurface` + `CheckLanding`):** Polls `IsTransitionReady(player, activeBeforeCell, activeAnchorCell, activeIsOut)` on `TIMER_ARRIVAL`, applies `player.SetPosition(activeTx, activeTy, activeTz)` + `player.SetAngle(0.0, 0.0, DestinationHeading)`, arms `SettleSeconds`, and verifies `afterCell.GetFormID() / 16777216 == anchor.GetFormID() / 16777216` (`coreCell`), `afterWorld != None`, `dx*dx + dy*dy <= PositionToleranceSq` (`25.0` = `5.0 m` radius), and `dz > -FallDrop && dz < 3.0`. Only re-calls `MoveTo` on retry when `NeedsMoveTo(...)` shows the player is not yet in the target space.
- **Save-reload safety & lifecycle tracing:** Logs `FO4SF_LOADDOOR init` (`OnInit`), `FO4SF_LOADDOOR attached` (`OnCellAttach`), `FO4SF_LOADDOOR activate_begin`, and `FO4SF_LOADDOOR confirmed|retry|failed|ignored` to `fo4sf_loaddoor`; cancels `TIMER_ARRIVAL` and resets `busy = false`, `inFlight = false`, `settlePending = false` in `OnLoad()`.
- **Offline compilation receipt (`v2`):** Compiled cleanly with Starfield Papyrus Compiler `v4.7.0.5` against `ContentResources.zip` (`0` errors, `0` warnings; `.pex` = `15,415 B`, not committed per `.gitignore`).

---

## 9. Binary Bisect of P1 v1 Bare Mars (`z = 12.6 m`) & Offline Core-Cell Proof

1. **Exact Binary Bisect of Bare Mars (`z = 12.6 m`):**
   - `FO4Port.esm` contains **`0` `WRLD` records** and **`0` `PNDT` records**.
   - In Probe `P1` `v1`, `FO4SF_R11P1Museum.esm` emitted a 21-byte stub override of `WRLD 0x02000803` (`FO4Core_Commonwealth`, `flags = 0x0`, only `EDID`), which wiped `FO4TerrainCore.esm:0x01000803`'s 23 subrecords (`flags = 0x04`, `ONAM`, `MNAM`, `NAM0`, `NAM9`, `DATA`) and severed `FO4TerrainCore_Mars.esm`'s `PNDT 0x0003F59A` world splice, dropping exterior Concord onto bare Mars (`z ≈ 12.6 m`).
   - **Fix (`v2`):** Removed `TopGrup(b"WRLD")` completely from BOTH `FO4SF_R11P1Museum.esm` and `FO4SF_R11P1XtelExtra.esm` (**`0` `WRLD` / `0` `PNDT` records**). Exterior doors `0x04000810` and `0x04000813` are authored in probe-owned holding interior **`CELL 0x0400080F` (`FO4SF_P1_HoldingCell`)** and dynamically placed onto `MarsPlanetWorld` via `FO4SF_R11P1Quest.SyncExteriorDoors` when outdoors within `350 m` of Concord.
2. **Offline `FO4TerrainCore.esm` Core-Cell Grid Proof (`4,096` cells, `XCLC` `-32..31` x `-32..31`, `100.0 m` cell size):**
   - Verified directly against `FO4TerrainCore.esm` (`193,662,015 B`): `FO4TerrainCore.esm` stores unshifted local coords (`XCLC`), while runtime placement applies `MergeOffset = (-1200, -2700)`:
     - `p1_front_out`: local `(-812.50, 1002.06)` (merged `(-2012.50, -1697.94)`) -> `FO4TerrainCore` `XCLC (-9, 10)` = **`0x01000DEF`**.
     - `p1_roof_out`: local `(-808.49, 975.40)` (merged `(-2008.49, -1724.60)`, `2.21 m` south of roof entry activator) -> `FO4TerrainCore` `XCLC (-9, 9)` = **`0x01000DEE`**.
   - Every P1 exterior exit coordinate resolves cleanly inside `FO4TerrainCore.esm`'s `4,096`-cell grid (`0x01000DEF` front / `0x01000DEE` roof; `IsCoreCellMatch == true`).
