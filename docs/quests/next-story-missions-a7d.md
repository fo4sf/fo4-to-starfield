Titles: Fallout 4 -> all 7 Fallout titles (FO4, FO3, FNV, FO1, FO2, Tactics, FO76) | Modes: Story & Warfare (+ Survival hardcore layer) | Track: Track 1 (13-plugin playable path) & Track 2 (22-plugin experimental core + W7 Open Mode)

# Next Story Missions (`A7d`): *The Glowing Sea* (`MQ204`), *Hunter/Hunted* (`MQ205` Bridge) & *The Molecular Level* (`MQ206`)

**Status:** `prototype, offline` — places, doors, and clean-room multi-track specification for the Act II climax after *Dangerous Minds* (`MQ203`), audited directly from `Fallout4.esm` and already-converted staged `FO4Port.esm` (`interiors_b10`, 269 interior `CELL`s — zero interior reconversion). Verified offline via [`a7d_glowing_sea_places.py`](../../scripts/terrain/a7d_glowing_sea_places.py) (`W6` Normal + Open-Mode reachability and read-only binary `interiors_b10` audit); not yet verified in live Starfield (`OFFLINE ONLY — UNPROVEN IN GAME` per `R15`).

> **Whole-scope context:** Continues the unbroken Fallout 4 main-story path in Starfield — Vault 111 -> *When Freedom Calls* (`A1`) -> *Sanctuary* / *The First Step* / *Jewel of the Commonwealth* (`A4`) -> *Unlikely Valentine* / *Getting a Clue* (`A7`) -> *Reunions* / *Dangerous Minds* (`A7c`) -> ***The Glowing Sea* & *The Molecular Level* (`A7d`)** -> Institute Concourse (`MQ207`) — keeping every quest behind the Story mode (`FO4SF_GameMode == 1`) gate with full Open-Mode dead-giver fallbacks.

---

## 1. Source-First `Fallout4.esm` Audit & Push 6 FormID Reservations

Read directly from `Fallout4.esm` (no memory guesswork; zero copyrighted dialogue copied into Git):

| Playable Mission | `FO4SFMission.esm` Reservation | `Fallout4.esm` Source Record(s) | Exact Vanilla Structure & Key Forms | Handoff Target |
| --- | --- | --- | --- | --- |
| **`FO4SF_MQ204`** (*The Glowing Sea*) | **`0x000B10`** (`0x000B10..0x000B2F`) | `QUST MQ204` (`0x0006B500`); faction dialogue stubs `MQ204Min/RR/BoS` (`0x0006B4FD..FF`) | `8` stages (`0, 5, 10, 15, 17, 20, 50, 200`), `QOBJ 15, 20`; `Virgil` (`0x0006B503`), `DoctorAmari` (`0x0009A680`), `CoAMotherIsolde` (`0x0012DB48`), `GlowingSea_COA_Virgil_Note` (`0x0019CBAE`), `GlowingSeaEntranceMarker` (`0x001A43EE`), `GlowingSeaMarker` (`0x000C02DF`), `MQ204CarMoved` (`0x0018932D`), triggers `0x002491B8` / `0x0023F984`. | Completion (`stage 200`) -> Courser hunt & `FO4SF_MQ206` (`0x000B30`). |
| **`MQ205` Bridge** (*Hunter/Hunted*) | Integrated opening phase of `FO4SF_MQ206` (`0x000B30`) | `QUST MQ205` (`0x000229EB`), `MISC MQ205_CourserChip` (`0x0006D0E8`) | Stages `10, 15, 20, 30, 40, 100`; Courser `Z2-47` (`0x0004EFEC`), `K1-98` (`0x0004EFE2`), `GreenetechDoor` (`0x00021EDD`) at `GreenetechGenetics01/02`. | Acquiring `CourserChip` advances directly into Railroad decode (`stage 20`). |
| **`FO4SF_MQ206`** (*The Molecular Level*) | **`0x000B30`** (`0x000B30..0x000B6F`) | `QUST MQ206` (`0x000B1752`) + branch controllers `MQ206Min` (`0x000B26BE`), `MQ206RR` (`0x000B26BC`), `MQ206BoS` (`0x000B26BD`) | `25` stages (`0..2000`), `QOBJ 10..250`, `42` aliases; `MISC MQ206SignalInterceptorPlans` (`0x0003FC16`), `NOTE MQ206CourserChipHolotape` (`0x0008575B`), `TinkerTomScanner` (`0x0016FF08`); `FURN`/`COBJ`: `ReflectorPlatform` (`0x001E0782`/`0x000CEA79`), `BeamEmitter` (`0x001E077F`/`0x000CEA6F`), `RelayDish` (`0x001E0783`/`0x000CEA7A`), `Console` (`0x00154AD6`/`0x000CEA7B`); `GLOB`s `MQ206Built*` (`0x000CEA7F..82`), `MQ206BeamEmitterMisaligned` (`0x000451A0`), `MQ206TeleporterFaction` (`0x000C9ACE`), `MQ206ScientistAtTeleporter` (`0x000CEA6D`), `MQ206ReadyToTeleport` (`0x0012C0BE`); `TeleporterMarker` (`0x000CF9CD`), `TeleporterTrigger` (`0x000CEA87`), `HoldingCellMarker` (`0x00030BA5`). | Relay `MoveTo` -> `FO4Port_InstituteConcourse` (`0x0103D252`) -> arms `MQ207`. |

**Disjointness:** `0x000B10..0x000B6F` is strictly disjoint from `A1(d)` (`0x800..0x9FF`), `A4` (`0xA00..0xA7F`), `A7` (`0xA80..0xACF`), and `A7c` (`0xAD0..0xB0F`), and fits cleanly inside the `A5` Pip-Boy Act II scan range (`0x000800..0x000BFF`).

---

## 2. Already-Converted `FO4Port.esm` (`interiors_b10`) Readiness & Door Audit

All **20** required Act II interior cells are **already converted and staged** inside `interiors_b10` (`FO4Port.esm`, `269` interior `CELL`s, master `Starfield.esm` — **zero interior reconversion required**). Because the port re-IDs records, runtime lookups must always use the verified `FO4Port_*` FormID table below (never `fo4_id & 0xFFFFFF`):

| FO4 Cell (`Fallout4.esm`) | Staged Cell (`FO4Port.esm`, `interiors_b10`) | Refs | Internal `XTEL`s | Exterior Door Status | Wiring & Trigger Notes |
| --- | --- | ---: | ---: | --- | --- |
| `GoodneighborTheMemoryDen` (`0x00022884`) | **`FO4Port_GoodneighborTheMemoryDen` (`0x0100ED4A`)** | 1,258 | 0 | **Unwired** | `MQ203 -> MQ204` handoff (`DoctorAmari` `0x0009A680`); needs exterior `FO4SF_LoadDoor` pair at Goodneighbor. |
| `MQ203KelloggsBrain` (`0x000D393F`) | **`FO4Port_MQ203KelloggsBrain` (`0x0100F23E`)** | 1,136 | 4 | Internal only | `4` internal `XTEL` links (`0x0100F67D<->0x0100F67E`, `0x0100F690<->0x0100F691`); scripted `MoveTo` from lounger. |
| `VirgilsLab01` (`0x00156C0E`) | **`FO4Port_VirgilsLab01` (`0x01069B10`)** | 539 | 0 | **Unwired** | Rocky Cave mouth unwired; place persistent `Virgil` + `MQ206SignalInterceptorPlans` desk/terminal fallback. |
| `SentinelSite01` (`0x001614C5`) | **`FO4Port_SentinelSite01` (`0x010481E9`)** | 5,245 | 0 | **Unwired** | Optional Glowing Sea landmark; exterior hatch unwired. |
| `GlowingSeaPOIDB05Int` (`0x001F4190`) | **`FO4Port_GlowingSeaPOIDB05Int` (`0x0106132A`)** | 161 | 0 | **Unwired** | Optional Glowing Sea interior waypoint; exterior hatch unwired. |
| `GlowingSeaPOIDB06Int` (`0x001F59B9`) | **`FO4Port_GlowingSeaPOIDB06Int` (`0x01047339`)** | 1,254 | 0 | **Unwired** | Optional Glowing Sea interior waypoint; exterior hatch unwired. |
| `GreenetechGenetics01` (`0x0009656C`) | **`FO4Port_GreenetechGenetics01` (`0x01056471`)** | 6,176 | 2 | **Unwired** | `MQ205` Courser `Z2-47` (`0x0004EFEC`); `2` internal `XTEL` pairs to `GreenetechGenetics02` (`0x01057C86<->0x0104C992`, `0x01057C92<->0x0104C99F`); exterior door `0x00021EDD` unwired. |
| `GreenetechGenetics02` (`0x00164A88`) | **`FO4Port_GreenetechGenetics02` (`0x0104BE53`)** | 2,887 | 2 | Internal only | Upper floors paired back to `GreenetechGenetics01` via 2 internal `XTEL` links. |
| `OldNorthChurch01` (`0x00066EF3`) | **`FO4Port_OldNorthChurch01` (`0x0103C790`)** | 1,294 | 1 | **Unwired** | `1` internal `XTEL` link to `RailroadHQ01` (`0x0103CC9E<->0x0103D18A`); exterior church door unwired. |
| `RailroadHQ01` (`0x00092B21`) | **`FO4Port_RailroadHQ01` (`0x0103CC9F`)** | 1,264 | 2 | Internal only | `2` internal `XTEL` links (`OldNorthChurch01` & `EscapeTunnel`); `TinkerTom`, `Desdemona`, `TinkerTomScanner` (`0x0016FF08`). |
| `RailroadHQEscapeTunnel` (`0x00137C87`) | **`FO4Port_RailroadHQEscapeTunnel` (`0x0105AAB9`)** | 692 | 1 | **Unwired** | `1` internal `XTEL` link to `RailroadHQ01` (`0x0105AD6C<->0x0103D189`); exterior exit unwired. |
| **`PrydwenHull01` (`0x0005C92E`)** | **`FO4Port_PrydwenHull01` (`0x01003846`)** | 3,651 | 2 | **WIRED (`0x0045AD`)** | **Already wired in `interiors_b10/port/doors.json`:** interior door `0x0045AD` (`src 1E42ED:Fallout4.esm`), marker `0x00E183` <-> `FO4TerrainCore.esm:0x0A774D` (`local [725.35, -144.39, 79.54]`, `merged [-474.65, -2844.39, 79.54]`); plus 2 internal `XTEL` links to `PrydwenHull02/03`. |
| `PrydwenHull02` (`0x0014FC54`) | **`FO4Port_PrydwenHull02` (`0x0104026D`)** | 483 | 1 | Internal only | Command Deck (`BoSElderMaxson` `0x000642B8`); wired internally `0x0104044C<->0x010045AA`. |
| `PrydwenHull03` (`0x0021630B`) | **`FO4Port_PrydwenHull03` (`0x0101099A`)** | 95 | 1 | Internal only | Forecastle; wired internally `0x010109F9<->0x010045AE`. |
| `BostonAirportRuins01` (`0x00084A56`) | **`FO4Port_BostonAirportRuins01` (`0x0102E5FA`)** | 4,939 | 0 | **Unwired** | Exterior `BostonAirportWorkshopRef` (`0x000B3506`) & `BoSProctorIngram` (`0x000642B5`) live in `FO4TerrainCore`; interior ruins door unwired. |
| `TheCastle01` (`0x000ADEC8`) | **`FO4Port_TheCastle01` (`0x01047D16`)** | 1,228 | 0 | **Unwired** | Optional Minutemen interior; primary Minutemen build site is exterior Sanctuary workbench (`FO4TerrainCore.esm:0x005C50`). |
| `InstituteConcourse` (`0x0002A199`) | **`FO4Port_InstituteConcourse` (`0x0103D252`)** | 5,317 | 6 | Scripted relay | `MQ206` Stage `1200` relay `MoveTo` destination (no exterior load door in vanilla); `6` internal `XTEL` doors connect `BioScience`, `AdvSystems`, `Robotics` (`0x0103FAB4`, `143` refs), and `SRB`. |
| `InstituteAdvSystems` (`0x0002A19A`) | **`FO4Port_InstituteAdvSystems` (`0x0103E757`)** | 306 | 2 | Internal only | Linked internally to `InstituteConcourse` (`0x0103E88B<->0x0103E70A`) and `InstituteReactor` (`0x0105D25A`, `1,979` refs, `0x0103E88A<->0x0105DA11`). |
| `InstituteBioScience` (`0x0002A19C`) | **`FO4Port_InstituteBioScience` (`0x0103E890`)** | 943 | 4 | Internal only | Linked internally to `InstituteConcourse` (`0x0103EC3B<->0x0103E709`) and `InstituteFEVlab` (`0x0103ED77`, `1,183` refs, `0x0103EC3D/E<->0x0103F218/7`). |
| `InstituteSRB` (`0x0002A19D`) | **`FO4Port_InstituteSRB` (`0x0103FB4B`)** | 207 | 1 | Internal only | Linked internally to `InstituteConcourse` (`0x0103FC1A<->0x0103E70B`); `InstituteTunnel01` (`0x0105B3C0`, `5,829` refs) is also staged. |

### Missing Transition Cells & Unneeded Storage Cells (`interiors_b10` Delta)
- **Missing elevator / transition cells (2 — DO NOT reconvert; bypass cleanly):**
  1. `ElevTransHiTechInstitute` (`0x0021A107`) — absent from `interiors_b10`. **Mitigation:** `MQ206` Stage `1200` relays directly via `player.MoveTo` into `FO4Port_InstituteConcourse` (`0x0103D252`), and all wing transitions use the existing internal `XTEL` doors on `InstituteConcourse`.
  2. `MassFusion02Trans` (`0x0014FC9B`) — absent from `interiors_b10`. **Mitigation:** Not used by `MQ204`/`MQ206` (Act III Mass Fusion only); bypass with direct floor-to-floor `MoveTo` when Act III is built.
- **Absent vanilla alias/storage cells (3 — NOT needed):** `InstituteAliasCell` (`0x0017CA01`), `BostonAirportAliasCell` (`0x00172297`), and `PackInRelayTower` (`0x00191E94`) are vanilla holding/prefab storage cells; our clean-room quests place persistent actors/activators directly in `FO4SFMission.esm`.
- **Exterior door promotion rule:** Preserve all 15 existing `interiors_b10/port/doors.json` markers (`0x00E175..0x00E183`, including `PrydwenHull01` `0x0045AD` / `0x00E183`) byte-identically when promoting unwired Act II exterior doors (`VirgilsLab01`, `GreenetechGenetics01`, `OldNorthChurch01`, `GoodneighborTheMemoryDen`) at `HEDR.nextObjectId >= 0x074CD3` via `FO4SF_LoadDoor`. Until exterior load doors are promoted into a refreshed core bundle, `FO4SF_MQ204Quest` / `FO4SF_MQ206Quest` can also expose `Mission.CodsworthTalkActiModel` (`Effects\sfbgs006\SFBGS006_SBShipDecoratorMarker.nif`, no `Meshes\` prefix) exterior arrival proxies at merged coordinates.

---

## 3. Track 1 (`--profile player`) vs Track 2 (`--profile test` + `W7` Open Mode)

| Concern | Track 1 — `13`-Plugin Playable Bundle (`--profile player`) | Track 2 — `22`-Plugin Experimental Core + `W7` Open Mode (`--profile test`) |
| --- | --- | --- |
| **Glowing Sea Radiation (`MQ204`)** | Quest-local SW Commonwealth polygon ticker on `FO4SF_MQ204Quest` (`ResolveCommonwealthWorld()` `0x0A775B` verified, `ActiveCorePlugin()` `_Mars` fallback) writing `FO4SFCoreValues.esm` `FO4SF_Rads` (`0x000800`) scaled by `FO4SF_RadResist` (`0x000804`) and `FO4SFPowerArmor` (`0x080A`), with zero hard dependency on `FO4SFRads.esm`. | Auto-detects `Game.IsPluginInstalled("FO4SFRads.esm")`; disables the Track 1 fallback ticker and delegates exposure to `FO4SF_RadsHazard` (`0x0828`) / `FO4SF_RadsEmitter` (`0x082A`) volumes & `FO4SF_RadsRule` (`0`/`1`). The quest state machine never blocks progression on a rads value. |
| **Signal Interceptor Build (`MQ206`)** | Console-free **Workbench Signal Interceptor Assembly Menu** (matching `FO4SF_Sanctuary01`'s `0x000A15` pattern) at the chosen faction's workshop (`Sanctuary 0x005C50` always valid): builds Reflector Platform, Beam Emitter, Relay Dish, Console, and +27 Power atomically via `GLOB`s (`MQ206Built*`, `MQ206ReadyToTeleport`) with zero fragile spline-wire or Havok snap dependencies. | Live `FO4SFWorkshop.esm` `COBJ` placement & `FO4SF_CAMPKit` (`0x0810`) support write the same idempotent `GLOB`s, keeping the Track 1 Workbench Assembly Menu active as a zero-softlock fallback whenever physical placement or wiring is skipped. |
| **Faction Branches & Dead-Giver Fallbacks (`W7`)** | Story-mode gate (`FO4SF_GameMode == 1`); supports all 3 branches (`1=Minutemen/Sturges`, `2=Railroad/TinkerTom`, `3=BoS/ProctorIngram`) with `talkSessionId` + `btn >= 0` / `"Leave"` modal guards and female Starfield templates/voices on `DoctorAmari`, `MotherIsolde`, `Desdemona`, and `ProctorIngram`. | Full non-essential **Open Mode**: (1) dead `MotherIsolde` -> `GlowingSea_COA_Virgil_Note` (`0x0019CBAE`) or direct Rocky Cave arrival; (2) dead `Virgil` -> lab desk/terminal grants `MQ206SignalInterceptorPlans` (`0x0003FC16`); (3) dead/hostile Railroad -> `Stage 65` self-decode on `TinkerTomScanner` (`0x0016FF08`); (4) all 3 faction engineers dead -> **Solo Self-Build (`TeleporterFaction = 0`)** + direct console relay `MoveTo` `FO4Port_InstituteConcourse` (`0x0103D252`). |

---

## 4. Top 5 Vanilla Fallout 4 Quest-Breaking Bugs & Clean-Room Defenses

1. **`MOL-01` — Split Power-Grid & `MQ206BeamEmitterMisaligned` (`0x000451A0`) Snap Stall (`MQ206` Stages `350..700`):**
   - *Vanilla Failure:* Powering Emitter, Dish, and Console from separate generators — or failing Havok snap of `MQ206BeamEmitter` (`0x001E077F`) atop `MQ206ReflectorPlatform` (`0x001E0782`) — permanently stalls `QOBJ 150`.
   - *Defense:* Replace wire-graph and Havok overlap checks with idempotent `MQ206Built*` `GLOB` counters re-derived on 1 Hz timer + `OnPlayerLoadGame`, anchoring spawned parts at deterministic local offsets from the platform.
2. **`MOL-02` — Faction Engineer AI Pathing / Furniture Stall (`Sturges` / `TinkerTom` / `ProctorIngram`, `MQ206ScientistAtTeleporter` `0x000CEA6D`):**
   - *Vanilla Failure:* Scientists snag on roofs/stairs or loop generic `Min01`/`RR` chatter instead of walking to `MQ206Console` (`0x00154AD6`), hanging `Stage 700 -> 1000`.
   - *Defense:* Never gate stages on `OnPackageDone` or furniture sit events; release `SetRestrained(False)` on combat/completion (`T1`), run a bounded `R10` watchdog, and allow direct player activation of `MQ206Console` or stepping onto `TeleporterTrigger` (`0x000CEA87`) to arm and fire the relay.
3. **`MOL-03` — Premature Faction Lock-In, Locked `BostonAirportWorkshopRef` (`0x000B3506`), & `PAM` (`0x00045AD3`) Lockdown Deadlock (`Stages 200..320`):**
   - *Vanilla Failure:* Selecting BoS/RR early locks out other branches even when Boston Airport lacks build access or `PAM` is locked down (`QOBJ 105` *Mercer Station* deadlocked), or when the chosen faction turns hostile.
   - *Defense:* Keep `TeleporterFaction` re-selectable until build commit (`Stage 350`), keep Sanctuary (`0x005C50`) universally allowed across all branches, and auto-failover to Solo Open Mode (`TeleporterFaction = 0`) if all faction engineers are dead or hostile.
4. **`GLOW-04` — Power Armor Targeting HUD Aggro on `Virgil` (`0x0006B503`) & Cave-Entrance Car Scene (`MQ204CarMoved` `0x0018932D`) Stall:**
   - *Vanilla Failure:* Entering `VirgilsLab01` (`0x00156C0E`) wearing Power Armor Targeting HUD turns Virgil hostile; bypassing exterior triggers `0x002491B8`/`0x0023F984` or stalling `VirgilPushingCar` (`0x00174E15`) blocks `MQ204` `Stage 20 -> 50` and `MQ206` plans.
   - *Defense:* Apply `Virgil.IgnoreFriendlyHits(True)` on spawn and `OnPlayerLoadGame`, drive `MQ204` stages monotonically from `ResolveCommonwealthWorld()` distance / cell entry (no single-box trigger or car-scene dependency), and keep `MQ206SignalInterceptorPlans` + terminal decode notes reachable in `FO4Port_VirgilsLab01` (`0x01069B10`) even if Virgil is hostile or dead.
5. **`MOL-05` — Pre-Wiped Railroad HQ / Mid-`RR102` Chip Sequence Break (`0x0016FF08`) & `HoldingCellMarker` (`0x00030BA5`) Relay Hang:**
   - *Vanilla Failure:* Arriving at `RailroadHQ01` (`0x00092B21`) after killing the Railroad or mid-`RR102` stalls `TinkerTom` chip decoding; `HoldingCellMarker` relay staging can hang across save/reload.
   - *Defense:* Re-evaluate `CourserChip` possession and `(Desdemona.IsDead() || TinkerTom.IsDead() || IsHostile)` idempotently on `OnStageSet` and `OnPlayerLoadGame`, keeping `TinkerTomScanner` (`Stage 65 -> 100`) always activatable, and execute `Stage 1200` via direct `player.MoveTo` into `FO4Port_InstituteConcourse` (`0x0103D252`) with `EffectiveStage = max(GetStage(), applied)` reload recovery.

---

## 5. `W6` 4-Axis Break-It Matrix (`P3`-Safe Batch IDs — Zero `M`/`N`/`V`) & `A5` TSV Rows

Verified offline by `python scripts/terrain/a7d_glowing_sea_places.py audit-a7d` (`0` unreachable stages, `0` stuck stages in both Normal Mode and Open-Mode dead-giver simulation):

| Mission | Axis | `P3`-Safe Batch | Scenario & Verified Recovery |
| --- | --- | --- | --- |
| `FO4SF_MQ204` (`0x000B10`) | Giver dead | `bat a7d1` | `MotherIsolde` dead -> `Virgil_Note` advances `15 -> 20`; `Virgil` dead -> `VirgilsLab01` terminal advances `50 -> 200` and arms `MQ206`. |
| `FO4SF_MQ204` (`0x000B10`) | Out of order + reload/fast travel | `bat a7d2` | Direct walk to Rocky Cave bypassing Crater (`15 -> 20 -> 50`), reload inside `0x01069B10`, fast travel back to Sanctuary without `WorldSpace` misplacement. |
| `FO4SF_MQ206` (`0x000B30`) | Giver/faction dead | `bat a7d3` | Railroad wiped (`20 -> 65 -> 100` via `TinkerTomScanner`), `Virgil` dead (lab desk plans `100 -> 200`), all 3 faction engineers dead -> Solo Workbench Build (`200 -> 300 -> 350 -> 700 -> 1000 -> 1200`). |
| `FO4SF_MQ206` (`0x000B30`) | Save/reload + faction switch | `bat a7d4` | Reload mid-assembly (`350`/`700`), switch faction before `Stage 350` commit, verify `talkSessionId` modal recovery and direct `MoveTo` `FO4Port_InstituteConcourse` (`0x0103D252`). |

`A5` 7-column `FO4SFPipboyQuestObjectives.tsv` rows (`python scripts/terrain/a7d_glowing_sea_places.py emit-tsv`):

```tsv
0x000B10	15	The Glowing Sea	Travel to the Glowing Sea and search for Virgil	-56092.31	-78515.81	Edge of the Glowing Sea
0x000B10	20	The Glowing Sea	Locate Virgil in the Rocky Cave	-116397.02	-136728.78	Rocky Cave
0x000B10	50	The Glowing Sea	Speak with Virgil inside his laboratory	-116397.02	-136728.78	Virgil's Laboratory
0x000B30	10	The Molecular Level	Eliminate the Institute Courser at Greenetech Genetics and take the Courser Chip	-4120.00	-14800.00	Greenetech Genetics
0x000B30	20	The Molecular Level	Have the Courser Chip decoded at Railroad HQ	32768.00	-4096.00	Old North Church
0x000B30	100	The Molecular Level	Return to Virgil for the Signal Interceptor plans	-116397.02	-136728.78	Virgil's Laboratory
0x000B30	200	The Molecular Level	Recruit a faction engineer or prepare solo assembly	-79872.00	91648.00	Sanctuary Hills
0x000B30	350	The Molecular Level	Build and power the Signal Interceptor at the workbench	-79872.00	91648.00	Sanctuary Hills
0x000B30	1000	The Molecular Level	Step onto the Signal Interceptor platform and relay to the Institute	48073.90	-3331.96	Boston Airport
```

---

## 6. Consolidated Owner Questions

1. **Exterior load-door promotion batching:** Should the 4 core Act II exterior entrances (`VirgilsLab01`, `GreenetechGenetics01`, `OldNorthChurch01`, `GoodneighborTheMemoryDen`) be promoted into `FO4TerrainCore.esm` / `FO4Port.esm` together with the A3/A4 Concord & Corvega doors in the next core-bundle refresh (preserving existing `0x00E175..0x00E183`, including `PrydwenHull01` `0x0045AD`), or kept on `FO4SFMission.esm` arrival proxies until after the `2f` playtest?
2. **Track 1 Signal Interceptor visual pieces:** For the `13`-plugin `--profile player` bundle, are deterministic placeholder static/activator prefabs spawned around the workbench acceptable for the first playable pass, or should converting the 4 vanilla `MQ206` `FURN` meshes (`0x001E0782`, `0x001E077F`, `0x001E0783`, `0x00154AD6`) block Push 6?
3. **`MQ205` *Hunter/Hunted* quest slot:** Is keeping *Hunter/Hunted* integrated as the opening Greenetech Genetics Courser phase (`Stage 10 -> 20`) of `FO4SF_MQ206` (`0x000B30`) preferred for clean `A5` Pip-Boy log pacing, or should it later be split into a dedicated `FO4SF_MQ205` quest record?
