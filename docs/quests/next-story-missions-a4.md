# Next Story Missions in Order (`A4` — Source-First Audit, Known-Bug Ledgers & `W6` Break-It Suite)

> **Whole Scope:** Titles: Fallout 4 | Modes: Story & Warfare (+ Survival hardcore layer) | Track: Track 1 (playable path) — **source-first audit & offline `W6` verification, unproven in game (`R15`)**.
>
> **Source-First & Clean-Room Compliance:** All FormIDs, stages, objectives, aliases, global variables, scene structures, and Papyrus script names below were read directly from the owner's local `Fallout4.esm` and `Fallout4 - Misc.ba2` / `Fallout4 - Interface.ba2` (read-only). Zero verbatim copyrighted dialogue is copied into Git; all objective and stage descriptions are clean-room functional summaries. Zero third-party mod names appear anywhere in this document.
>
> **In-Place Completion Rule (`FO4SF_Sanctuary01` `09000817`):** `FO4SF_Sanctuary01` (`0x000817` in `FO4SFMission.esm`) **already exists** as a stage-10 workbench stub targeting `04005C50` (`0250FE:Fallout4.esm`). We **complete `09000817` in place** from Fallout 4's `Min01` (`0x05DEE4`) — **do NOT create a second Sanctuary quest**. All three missions sit behind the `FO4SF_GameMode == 1` (Story) mission gate and stop silently in Warfare mode (`FO4SF_GameMode == 2`).

---

## 1. Story Order & `FO4SFMission.esm` FormID Reservation Table (Zero Overlap with `A1(d)`)

Existing `FO4SFMission.esm` (`09`) reserves `0x800..0x82F` (`Min00`, `CodsworthKeeper`, `COMPreston`, `Codsworth01`, `Sanctuary01` `0x817`, `CodsworthRace` `0x818`, `CodsworthVoice` `0x819`, `MinutemenFaction` `0x81F`, `CodsworthHellos` `0x820+`) and `0x900..0x978` (Preston & Codsworth scenes + `V2` talk messages; `0x980..0x9BF` left clear for `A1(d)` real-talk records). `A4` expands `0x817` in place and reserves **`0xA00..0xA7F`** so `A4` merges cleanly right after `A1(d)` with zero FormID collisions:

| Story Order | Mission | Fallout 4 Source `QUST` | Starfield `FO4SFMission.esm` ID | Reserved Companion Records (`0xA00..0xA7F`) | Required Places & NPCs |
|---|---|---|---|---|---|
| **1** | **Sanctuary** | `Min01` (`0x05DEE4`) | **`0x000817`** (`FO4SF_Sanctuary01`, **completed in place**) | `0xA00..0xA1F` (`FO4_Sturges` `NPC_`/`ACHR`, `Min01` bed/water/food/safety `GLOB`s, Sturges dialogue scene/fallback `MESG`s) | Sanctuary Hills exterior + Workbench `04005C50` (`0250FE`), `FO4SFWorkshop.esm` (`0B`), Preston (`09000802`), Sturges (`0x019FDA`) |
| **2** | **The First Step** | `MinRecruit00` (`0x11B36E`) | **`0x000A20`** (`FO4SF_MinRecruit00`) | `0xA21..0xA4F` (`TenpinesSpokesman` `NPC_`/`ACHR`, Corvega boss + guards, `FO4SF_FlareGun` reward `WEAP`/`MISC`, request note) | Tenpines Bluff workbench `0401A793` (`09B1AC`), `FO4Port_CorvegaAssemblyPlant01` (`0201535A`, `5` real-mesh doors in `A3`), Preston (`09000802`) |
| **3** | **Jewel of the Commonwealth** | `MQ103` (`0x0229E5`) + `DialogueDiamondCityEntrance` (`0x0190BC`) | **`0x000A50`** (`FO4SF_MQ103`) | `0xA51..0xA7F` (`FO4_Piper` `0x002F1E`, `FO4_MayorMcDonough` `0x002F08`, `FO4_ElliePerkins` `0x0222A2`, DC gate intercom/door activator, case dossier fallback) | Commonwealth road to `DmndGateREF` `04013E79` (`077A87`), `FO4Port_DmndValentines01` (`02006B30`, staged in `interiors_b10`), `MQ104` hook -> `Vault114` (`02002593`, already door-wired!) |

---

## 2. Source-First Audits (Read Directly from `Fallout4.esm`)

### 2.1 Mission 1 — *Sanctuary* (`Min01` `0x05DEE4` -> Completing `FO4SF_Sanctuary01` `09000817` In Place)

**Observed `Fallout4.esm` Source Structure:**
- **Record:** `QUST Min01` (`0x05DEE4`, `DNAM flags=0x0100`, `priority=75`), script `Min01Script` (`scripts/min01script.pex`, quest fragment `QF_Min01_0008C39B.pex`, `245` `DIAL`s, `26` `SCEN`s including `Min01PrestonSanctuaryIntro`, `Min01SturgesNextObjectiveWater/Food/Safety`, `Min01PrestonFinishAllObjectives`, `Min01PrestonOutroFinal`, and the Concord-to-Sanctuary travel scenes `Min01ConcordTravel*`).
- **Source Aliases (`16`):** `[0]` `preston` (`0x019FD9`), `[5]` `Sturges` (`0x019FDA`), `[6]` `MamaMurphy` (`0x019FD8`), `[7]` `MarcyLong` (`0x019FDC`), `[8]` `JunLong` (`0x019FDB`), `[9]` `Codsworth` (`0x0179FF`), `[17]` `Companion`, `[3]` `SanctuaryLocation` (`0x01F228`), `[1]` `SanctuaryMapMarker`, `[4]` `Workshop` (`0x0250FE`), `[10]` `ConcordLocation` (`0x017E00`), plus travel look markers (`0x1188B0`, `0x11808C`, `0x11808D`).
- **Source Global Resource Targets (Read from `GLOB` records in `Fallout4.esm`):**
  - Beds: `Min01BedTotal` (`0x05FD8E`) = **`5.0`**, tracked via `Min01BedCount` (`0x05FD8D`) & `Min01BedPercent` (`0x0A190D`).
  - Water: `Min01WaterTotal` (`0x073041`) = **`5.0`**, tracked via `Min01WaterCount` (`0x073042`) & `Min01WaterPercent` (`0x0A190F`).
  - Food: `Min01FoodTotal` (`0x073040`) = **`5.0`**, tracked via `Min01FoodCount` (`0x073043`) & `Min01FoodPercent` (`0x0A190E`).
  - Defense / Safety: `Min01SafetyTotal` (`0x1DE910`) = **`2.0`**, tracked via `Min01SafetyCount` (`0x1DE90E`) & `Min01SafetyPercent` (`0x1DE90F`).
  - *(Note: vanilla `Min01` also defines an unused power objective `1100`/`1150` that shipped Fallout 4 skips straight from beds `1050` -> water `1200`; we preserve the exact shipped 4-resource cadence: Beds -> Water -> Food -> Defense.)*
- **Source Stages & Objectives -> In-Place Mapping on `FO4SF_Sanctuary01` (`09000817`):**
  - **Start:** Triggered automatically when `FO4SF_Min00` (`09000800`) reaches stage `200` (existing contract in `FO4SF_Min00Quest.psc`), gated by `FO4SF_GameMode == 1`.
  - **Stage `10` (existing stub preserved!):** Objective `10` — meet Preston / activate Sanctuary workbench (`04005C50`). Preserves compatibility with current `candidate-2e` cards; activating `04005C50` or talking to Sturges advances to stage `50` (and legacy saves already at stub stage `100` upgrade cleanly to `1500` without breaking!).
  - **Stage `50`:** Objective `50` — speak with Sturges (`FO4_Sturges`) in Sanctuary Hills.
  - **Stage `1000` -> `1050`:** Objective `1000` — provide `5` sheltered beds (`FO4SFWorkshop` settlement bed count >= `5`) -> Objective `1050` report to Sturges.
  - **Stage `1200` -> `1250`:** Objective `1200` — provide `5` clean water -> Objective `1250` report to Sturges.
  - **Stage `1300` -> `1350`:** Objective `1300` — provide `5` food -> Objective `1350` report to Sturges.
  - **Stage `1400` -> `1450`:** Objective `1400` — build `2` defense -> Objective `1450` report to Sturges.
  - **Stage `1500` (Completion):** Completes `FO4SF_Sanctuary01` (`09000817`), awards XP/credits, marks Sanctuary Hills active in `FO4SFWorkshop`, and signals Preston to offer `FO4SF_MinRecruit00` (*The First Step*).
- **Pre-Built Resource Evaluation Rule:** Whenever a resource stage (`1000`, `1200`, `1300`, `1400`) enters or reloads (`OnPlayerLoadGame`), `FO4SF_Sanctuary01Quest` immediately queries the current Sanctuary resource total; if already `>=` target (e.g., player built beds/pumps before talking to Sturges), it advances directly to the report stage (`1050`/`1250`/`1350`/`1450`) without forcing the player to scrap and rebuild.

---

### 2.2 Mission 2 — *The First Step* (`MinRecruit00` `0x11B36E` -> `FO4SF_MinRecruit00` `09000A20`)

**Observed `Fallout4.esm` Source Structure:**
- **Record:** `QUST MinRecruit00` (`0x11B36E`, `DNAM flags=0x0000`, `priority=76`), scripts `minrecruitquestscript` + `defaultcounterquesta` (`QF_MinRecruit00_0011B36E.pex`, `47` `DIAL`s, `4` `SCEN`s: `MinRecruit00SettlementIntro` `0x11B3BA`, `MinRecruit00SettlementReward` `0x11B3BB`, `MinRecruit00PrestonOutro` `0x11B3B9`, `MinRecruit00PrestonGiveFlareGun` `0x15A163`).
- **Source Aliases (`19`):**
  - Settlement selection cascade: `[28]` `TenPinesBluffWorkshop` (primary target: `09B1AC:Fallout4.esm` -> **ALREADY promoted** in `FO4TerrainCore.esm:0x01A793`, merged `(-1517.00, -1423.63, 87.71)` m) -> `[25]` `OberlandWorkshop` (`09B18F` -> `0x01A78F`) -> `[23]` `UnownedWorkshop` -> `[24]` `AnyWorkshop` -> `[9]` `Workshop`.
  - Raider target cascade: `[26]` `CorvegaDungeon` (`CorvegaAssemblyPlant01`, `057127:Fallout4.esm` -> **ALREADY converted & staged** in `FO4Port.esm:0x01535A`, `5` real-mesh doors audited in `A3`!) -> `[27]` `ClosestDungeon` -> `[4]` `RaiderDungeon` -> `[21]` `RaiderBosses`.
  - Key NPCs: `[7]` `PrestonGarvey` (`0x019FD9`), `[6]` `SettlementSpokesman`, `[13]` `SettlementLeader`, `[14]` `SettlementBoss`, `[20]` `SettlementNPCs`.
  - Important script flags observed in `VMAD`: `StopQuestWhenAliasesUnloaded = False`, `StopQuestWhenAliasesDead = False` (prevents silent quest abortion if a settler dies or unloads!).
- **Source Stages & Objectives -> `FO4SF_MinRecruit00` (`09000A20`):**
  - **Start (`Stage 10`):** Offered by Preston Garvey after *When Freedom Calls* (`FO4SF_Min00` stage `200`) and/or *Sanctuary* (`FO4SF_Sanctuary01` stage `>= 50`); also discoverable out-of-order by visiting Tenpines Bluff (`0401A793`).
  - **Stage `50` / Objective `10`:** Travel to Tenpines Bluff (`(-1517.00, -1423.63, 87.71)` m) and speak with the settlement spokesman (or inspect the settlement request note / workbench if spokesman is dead).
  - **Stage `100` / Objective `20`:** Travel to **Corvega Assembly Plant** (`FO4Port_CorvegaAssemblyPlant01` `0201535A`, main door `0400DF1B` <-> `02017957`), eliminate the raider leader (Jared) and boss alias group.
  - **Stage `200` / Objective `30`:** Return to Tenpines Bluff and report success to the spokesman -> Tenpines Bluff workbench (`0401A793`) unlocks for player settlement control.
  - **Stage `450` / Objective `40`:** Report back to Preston Garvey -> player formally joins the Minutemen (`FO4SF_MinutemenFaction` `0900081F` rank set), receives the **Flare Gun** (`FO4SF_FlareGun` + starter flares), and unlocks the `Min02` (*Taking Independence*) story flag.
  - **Stage `500` (Completion):** `CompleteQuest()`.

---

### 2.3 Mission 3 — *Jewel of the Commonwealth* (`MQ103` `0x0229E5` + `DialogueDiamondCityEntrance` `0x0190BC` -> `FO4SF_MQ103` `09000A50`)

**Observed `Fallout4.esm` Source Structure:**
- **Records:**
  - `QUST MQ103` (`0x0229E5`, `DNAM flags=0x0100`, `priority=70`, fragment `QF_MQ103_000229E5.pex`, `1` `DIAL`, `1` `SCEN`: `MQ103DetectiveSignScene` `0x0865AB`).
  - `QUST DialogueDiamondCityEntrance` (`0x0190BC`, `DNAM flags=0x0500`, `priority=40`, script `DiamondCityEntranceScript.pex`, `105` `DIAL`s, `10` `SCEN`s: `01DmndIntroSceneLong`, `04PiperIntroScene1`, `05PiperIntroScene2`, `06PiperIntroScene3`, `07MayorIntroScene1`, `08MayorIntroScene2a`, `09MayorIntroScene3`, `10MayorIntroScene4`, `DmndPiperNatScene01/02`).
- **Source Aliases:**
  - `MQ103` (`5`): `[3]` `DiamondCityLocation` (`0x002CEF`), `[0]` `DiamondCityMapMarker` (`0x01CAD5`), `[1]` `Ellie` (`0x0222A2`, Ellie Perkins), `[2]` `DetectiveSign01`, `[4]` `DetectiveSign02`.
  - `DialogueDiamondCityEntrance` (`11`): `[1]` `PiperAlias` (`0x002F1E`), `[2]` `TicketTakerAlias` (`0x018FD6` `DCgateIntercom`, merged `(-1425.33, -3133.98, 19.29)` m), `[3]` `Gate` (`0x077A87` `DmndGateREF` -> **ALREADY placed** at `FO4TerrainCore.esm:0x013E79`, `DExtMainGateDoorAnim01`, lock `254` Requires Terminal/Script, merged `(-1416.36, -3129.39, 19.20)` m), `[4]` `Mayor` (`0x002F08`, Mayor McDonough), `[6]` `Nat` (`0x002F20`), `[7]` `DannySullivan` (`0x0190BF`), `[8]` `Nick` (`0x002F24`).
- **Source Stages & Objectives -> `FO4SF_MQ103` (`09000A50`):**
  - **Start (`Stage 10`):** Started by Mama Murphy / Preston after *When Freedom Calls* (`FO4SF_Min00` stage `200`), by Codsworth / Trashcan Carla dialogue, OR automatically when the player approaches within `150 m` of `DmndGateREF` (`04013E79`) (out-of-order discovery).
  - **Stage `10` / Objective `10`:** Travel south along the Commonwealth road to **Diamond City** (`DmndGateREF` `04013E79` at merged `(-1416.36, -3129.39, 19.20)` m).
  - **Gate Sequence (`DialogueDiamondCityEntrance` folded cleanly into `FO4SF_MQ103`):** Approaching `DCgateIntercom` (`(-1425.33, -3133.98, 19.29)` m) triggers Piper's gate exchange with Danny Sullivan and Mayor McDonough; once Piper talks the player inside (or via Open-Mode intercom/gate override if Piper/Mayor are dead), `DmndGateREF` (`04013E79`) unlocks and advances to stage `20`.
  - **Stage `20` -> `25` / Objective `20`:** Enter Diamond City and inquire about Shaun (Piper, Mayor, or residents point to Nick Valentine).
  - **Stage `30` / Objective `30`:** Proceed to **Valentine Detective Agency** (`FO4Port_DmndValentines01` `02006B30`, **already converted & staged** in `interiors_b10`!).
  - **Worldspace Continuity Bridge (Honest Gap Handling):** In Fallout 4, Diamond City interior market is a separate worldspace (`DiamondCityWorld`) which is not yet built as a Starfield overlay, while `DmndValentines01` (`02006B30`) IS already staged in `FO4Port.esm`. Until `DiamondCityWorld` is converted, activating the unlocked `DmndGateREF` (`04013E79`) via `FO4SF_LoadDoor` transitions the player cleanly into `FO4Port_DmndValentines01` (`02006B30`) (and its exit door `02006C44` returns to `DmndGateREF` merged exterior), allowing full playable completion of `MQ103` without waiting on a new worldspace!
  - **Stage `100` (Completion):** Speaking with Ellie Perkins (`FO4_ElliePerkins`, or reading Nick's case file on the agency desk in Open Mode) completes `FO4SF_MQ103` and sets the handoff flag for **`MQ104` (*Unlikely Valentine*)**, whose dungeon **`Vault114`** (`FO4Port.esm:0x002593`) is **already converted AND two-way door-wired** (`00E177`/`00E178`) in `interiors_b10`!

---

## 3. Known-Bug Ledgers (`SANC-01..05`, `STEP-01..05`, `JOTC-01..05`)

*(Follows the 5-field clean-room schema in `docs/quests/known-bugs/README.md`; zero third-party mod names.)*

### 3.1 *Sanctuary* (`Min01` -> `FO4SF_Sanctuary01` `09000817`)

| Bug ID | Short Functional Name | Occurs in Our Conversion? | Resolution Category |
|---|---|---|---|
| `SANC-01` | Pre-Built Beds/Water/Food/Defense Stall Objective Counter | `Mitigated` (by design) | `Fix directly (ours)` |
| `SANC-02` | Sturges Clips onto House Roof or Unloads Out of 3D Range | `Yes` (risk until keeper wired) | `Fix directly (ours)` |
| `SANC-03` | Concord-to-Sanctuary Settler March Stalls When Player Fast-Travels | `Mitigated` (by design) | `Fix directly (ours)` |
| `SANC-04` | Save/Reload Drops Workbench Event Subscription or Resets Resource Percent | `Mitigated` (`OnPlayerLoadGame` exists) | `Fix directly (ours)` |
| `SANC-05` | Quest Starts or Displays Objectives in Warfare Mode (`FO4SF_GameMode == 2`) | `Mitigated` (`IsWarfareMode()` exists) | `Fix directly (ours)` |

- **`SANC-01` (Pre-Built Resource Stall):** *Description:* Shipped known-issue lists report `Min01` stalling at `0%` when the player crafts beds, water pumps, crops, or turrets before Sturges assigns each stage. *Occurs?* `Mitigated` by querying live `FO4SFWorkshop` settlement counts on stage entry and on `OnTimer`/`OnPlayerLoadGame`, immediately advancing to the report stage if `count >= target`. *PC Check:* Build `5` beds before speaking to Sturges; verify `sanctuary01 stage 1050 by=prebuilt` logs within `2 s`.
- **`SANC-02` (Sturges Roof/Unloaded Stall):** *Description:* Sturges wanders onto Sanctuary rooftops or snaps to unmerged local coordinates on cell reload. *Occurs?* `Yes` unless registered in `FO4SF_CodsworthKeeper`. *Resolution:* `Fix directly (ours)` — add Sturges (`0xA01`) to `FO4SF_CodsworthKeeper`'s merged-position hold table beside the Sanctuary workbench `(-2327.0, -1418.5, 112.1)` m with `PlaceRadius = 300.0 m`. *PC Check:* Reload save in Sanctuary; confirm `keeper status sturges ... off <= 25.0 held=true`.
- **`SANC-03` (March Unload Stall):** *Description:* Waiting for the Concord group to physically pathfind from Concord to Sanctuary fails when exterior cells unload during fast travel. *Occurs?* `Mitigated` — on `FO4SF_Min00` stage `200` + player entering Sanctuary (`<= 300 m`), keeper places Preston and Sturges directly at their Sanctuary merged markers instead of relying on multi-cell AI travel. *PC Check:* Fast-travel via Pip-Boy from Concord to Vault 111/Sanctuary; verify Preston & Sturges appear at Sanctuary workbench.
- **`SANC-04` (Save/Reload Resource Desync):** *Description:* Reloading mid-milestone drops remote `OnWorkshopMode`/`OnActivate` registrations. *Occurs?* `Mitigated` — extend `FO4SF_Sanctuary01Quest.psc`'s existing `Actor.OnPlayerLoadGame` handler to re-bind `04005C50`, re-read all 4 resource counters, and re-arm Timer `1`. *PC Check:* Save/reload at stage `1200`; confirm counter persists and completes cleanly.
- **`SANC-05` (Warfare Mode Leak):** *Description:* Story settlement tutorial firing during Warfare mode breaks sandbox starts. *Occurs?* `Mitigated` — retain `IsWarfareMode()` guard (`FO4SFCoreValues.esm:0x000870 == 2` -> `Stop()`). *PC Check:* Start Warfare mode; confirm `mission gate mode=2 started=false quest=sanctuary01`.

### 3.2 *The First Step* (`MinRecruit00` -> `FO4SF_MinRecruit00` `09000A20`)

| Bug ID | Short Functional Name | Occurs in Our Conversion? | Resolution Category |
|---|---|---|---|
| `STEP-01` | Tenpines Bluff Spokesman Dead or Hostile Blocks Quest Progression | `Mitigated` (Open-Mode fallback) | `Fix directly (ours)` |
| `STEP-02` | Corvega Assembly Plant Pre-Cleared Before Accepting Quest | `Mitigated` (by design) | `Fix directly (ours)` |
| `STEP-03` | Corvega Raider Boss Clips Below Catwalk or Fails to Register Death | `Yes` (risk without leash) | `Fix directly (ours)` |
| `STEP-04` | Settlement Workshop (`0401A793`) Does Not Transfer Ownership on Stage `450` | `Yes` (until wired to WorkshopCore) | `Fix directly (ours)` |
| `STEP-05` | Preston Busy / Relocated Between Concord and Sanctuary on Turn-In | `Mitigated` (keeper sync) | `Fix directly (ours)` |

- **`STEP-01` (Spokesman Dead/Hostile):** *Description:* Shipped known-issue lists note that killing or losing the settlement spokesman breaks `MinRecruit00` stage `50`/`200`. *Resolution:* `Fix directly (ours)` — keep `StopQuestWhenAliasesDead = False` and add an Open-Mode fallback note + workbench (`0401A793`) activation hook that advances `50 -> 100` and `200 -> 450`. *PC Check:* Kill spokesman in throwaway test; activate Tenpines workbench `0401A793` and verify `minrecruit00 open_mode fallback stage=100`.
- **`STEP-02` (Corvega Pre-Cleared):** *Description:* Clearing Corvega before talking to Tenpines leaves Objective `20` pointing at dead enemies. *Resolution:* `Fix directly (ours)` — check `CorvegaBoss.IsDead()` on stage `100` entry and on `OnTimer`; immediately advance `100 -> 200` if already dead. *PC Check:* Kill Corvega boss first, then accept quest; confirm instant `100 -> 200` advance.
- **`STEP-03` (Corvega Boss Stuck/Unloaded):** *Description:* Interior boss falls behind factory machinery or fails death callback on reload. *Resolution:* `Fix directly (ours)` — poll `IsDead()` on `1.0 s` timer while in `FO4Port_CorvegaAssemblyPlant01` (`0201535A`) plus a `WFC-01`-style stuck-Z leash onto the assembly-floor catwalk node. *PC Check:* Reload inside Corvega mid-fight; verify kill advances to stage `200`.
- **`STEP-04` (Workshop Ownership Transfer):** *Description:* Tenpines Bluff stays locked out of player workshop editing after stage `450`. *Resolution:* `Fix directly (ours)` — call `FO4SFWorkshop` ownership unlock on `0401A793` at stage `450`. *PC Check:* Activate `0401A793` after reporting to Tenpines; confirm workshop opens.
- **`STEP-05` (Preston Relocated on Return):** *Description:* Returning from Tenpines to find Preston moved from Concord to Sanctuary leaves marker stale. *Resolution:* `Fix directly (ours)` — alias `PrestonGarvey` directly onto persistent `09000802` so the HUD marker always tracks his current keeper-held spot. *PC Check:* Complete Objective `30` and verify Objective `40` marker tracks `09000802`.

### 3.3 *Jewel of the Commonwealth* (`MQ103` -> `FO4SF_MQ103` `09000A50`)

| Bug ID | Short Functional Name | Occurs in Our Conversion? | Resolution Category |
|---|---|---|---|
| `JOTC-01` | Piper / Mayor Gate Scene Deadlocks Leaving `DmndGateREF` Locked (`254`) | `Yes` (highest-frequency FO4 bug) | `Fix directly (ours)` |
| `JOTC-02` | Player Reaches Diamond City Gate Without Mama Murphy / Codsworth Lead | `Mitigated` (by design) | `Fix directly (ours)` |
| `JOTC-03` | `DmndValentines01` Unreachable Because `DiamondCityWorld` Is Not Yet Built | `Yes` (current architecture gap) | `Fix directly (ours)` |
| `JOTC-04` | Save/Reload Mid-Gate Scene Freezes Piper or Fails to Re-Open Gate | `Yes` (risk without idempotent apply) | `Fix directly (ours)` |
| `JOTC-05` | Ellie Perkins Dead/Missing in Open Mode Stalls `MQ104` Handoff | `Mitigated` (Open-Mode dossier) | `Fix directly (ours)` |

- **`JOTC-01` (Gate Scene Deadlock):** *Description:* Across shipped known-issue lists and community unofficial-patch changelogs, `DialogueDiamondCityEntrance` is notorious for stalling if the player walks past Piper, talks to Danny out of order, or interrupts the intercom scene, leaving `DmndGateREF` (`077A87`) permanently locked (`254`). *Resolution:* `Fix directly (ours)` — (1) never hard-lock `DmndGateREF` behind a single scene fragment; (2) give `DCgateIntercom` AND `DmndGateREF` an idempotent `OnActivate` fallback (if Piper's scene stalls `> 15 s` or Piper/Mayor are dead, unlock gate directly and advance `10 -> 20`). *PC Check:* Walk straight to `04013E79` ignoring Piper; activate gate/intercom and verify unlock + `mq103 stage 20`.
- **`JOTC-02` (No Prior Lead):** *Description:* Player explores south directly from Vault 111 to Diamond City before visiting Concord. *Resolution:* `Fix directly (ours)` — distance trigger (`<= 150 m` of `04013E79`) auto-starts `FO4SF_MQ103` at stage `10` cleanly without requiring `Min00`. *PC Check:* New Game -> walk south bypassing Concord -> verify `mq103 started by=proximity`.
- **`JOTC-03` (`DiamondCityWorld` Bridge):** *Description:* `DmndValentines01` (`02006B30`) links to `DiamondCityWorld` (`0013FC/0013FD`), which is not yet built. *Resolution:* `Fix directly (ours)` — wire `DmndGateREF` (`04013E79`) with a `FO4SF_LoadDoor` bridge straight into `FO4Port_DmndValentines01` (`02006B30`) once unlocked (with return door `02006C44` returning to merged exterior `(-1416.36, -3129.39, 19.20)` m) until `DiamondCityWorld` lands. *PC Check:* Activate unlocked `04013E79` -> verify clean entry into `FO4Port_DmndValentines01` and clean return.
- **`JOTC-04` (Save/Reload Mid-Gate Scene):** *Description:* Reloading while Piper stands at the intercom stalls stage `10 -> 20`. *Resolution:* `Fix directly (ours)` — `OnPlayerLoadGame` re-checks `GetStage()` and re-asserts gate unlock / scene state synchronously via `AdvanceTo()` -> `Apply()`. *PC Check:* Save/reload mid-scene; verify gate still unlocks.
- **`JOTC-05` (Ellie Dead in Open Mode):** *Description:* Killing Ellie inside `DmndValentines01` breaks the `MQ104` lead to Park Street Station / Vault 114. *Resolution:* `Fix directly (ours)` — place Nick's Park Street Station case dossier on the agency desk; activating/reading it sets stage `100` and arms `MQ104`. *PC Check:* Activate dossier in `02006B30`; confirm `mq103 stage 100 by=dossier` and `mq104 armed`.

---

## 4. `W6` Reachability, Fragility & Break-It Batch Verification (`OFFLINE PASS`)

Verified offline via `python scripts/terrain/a3_path_places.py audit-a4`:
- **Missions checked:** `3` (`FO4SF_Sanctuary01`, `FO4SF_MinRecruit00`, `FO4SF_MQ103`)
- **Normal-mode dead ends:** **`0`** (all `23` total stages across all `3` quests reach their terminal completion stage)
- **Open-Mode dead-giver failures:** **`0`** (`13` explicit `open_mode_fallback` transitions; every essential NPC has a deterministic non-dialogue fallback)
- **Out-of-order edges:** **`10`** (`5` Sanctuary, `3` First Step, `2` Jewel of the Commonwealth)

### Break-It Matrix (All 4 Required `W6` Stress Axes per Mission)

| Mission | Break-It 1: Giver Dead (Open Mode) | Break-It 2: Out of Order | Break-It 3: Save & Reload at Every Stage | Break-It 4: Fast Travel Away Mid-Quest |
|---|---|---|---|---|
| **Sanctuary** (`09000817`) | Kill Sturges + Preston -> activate workbench `04005C50` -> workbench checklist advances `10 -> 1000 -> 1200 -> 1300 -> 1400 -> 1500` | Build `5` beds, `5` water, `5` food, `2` defense BEFORE talking to Sturges -> each stage auto-advances on entry | Manual save -> quit -> reload at `10`, `50`, `1000`, `1200`, `1300`, `1400`, `1450` -> `OnPlayerLoadGame` re-binds `04005C50` & preserves counts | Pip-Boy fast travel to Concord/Vault 111 mid-build -> return to Sanctuary -> timer resumes & counts persist |
| **The First Step** (`09000A20`) | Kill Tenpines spokesman and/or Preston -> Tenpines note/workbench `0401A793` sets `100`, claims settlement at `450`, Sanctuary locker grants Flare Gun at `500` | Clear Corvega (`0201535A`) BEFORE talking to Tenpines or Preston -> boss death flag jumps `50 -> 200` / `100 -> 200` immediately | Save/reload at `10`, `50`, `100` (inside Corvega), `200`, `450` -> `StopQuestWhenAliasesUnloaded=False` keeps aliases intact | Fast travel from Corvega exterior back to Sanctuary mid-clear -> re-enter Corvega -> boss state intact |
| **Jewel of the Commonwealth** (`09000A50`) | Kill Piper, Mayor, and/or Ellie -> intercom/gate manual override opens `04013E79` (`10 -> 20`); desk dossier in `02006B30` completes `30 -> 100` & arms `MQ104` | Walk straight from Vault 111 to Diamond City gate skipping Sanctuary/Concord -> `150 m` proximity starts `10`; inspecting agency sign jumps `20 -> 30` | Save/reload at `10`, `20`, `25`, `30` (inside `02006B30`) -> idempotent `AdvanceTo` keeps gate unlocked & objective active | Fast travel back to Red Rocket mid-gate scene -> return to `04013E79` -> Piper/intercom resumes without locking gate |

---

## 5. Same-Hour Implementation Handoff (Ready Once `A1(d)` Merges)

1. Expand `FO4SF_Sanctuary01` (`0x000817`) **in place** inside `dotnet/Mission/Program.cs` + `scripts/mission/FO4SF_Sanctuary01Quest.psc` (adding stages `50`, `1000..1500` while retaining stage `100` compatibility, plus `FO4_Sturges` `0xA00..0xA1F`).
2. Add `FO4SF_MinRecruit00` (`0x000A20`, `scripts/mission/FO4SF_MinRecruit00Quest.psc`) and `FO4SF_MQ103` (`0x000A50`, `scripts/mission/FO4SF_MQ103Quest.psc`) in `dotnet/Mission/Program.cs` with synthetic clean-room defaults in source and local `Fallout4.esm` string lookup at build time (zero copyrighted dialogue in Git).
3. Wire all `3` quests behind `FO4SF_GameMode == 1` (Story) and extend `dotnet/Mission check` + `tests/test_a3_path_places.py` + `candidate-2f`/`2g` PC cards.

---

## 6. Questions for the Owner

1. **Diamond City Entry Before `DiamondCityWorld` Exists (`JOTC-03`):** For *Jewel of the Commonwealth* (`FO4SF_MQ103`), do you approve wiring the unlocked Diamond City main gate (`04013E79`) directly into the already-staged `FO4Port_DmndValentines01` (`02006B30`) interior as a playable Track-1 bridge so *Jewel of the Commonwealth* -> *Unlikely Valentine* (`Vault114`) is playable end-to-end immediately, until `DiamondCityWorld` is converted?
2. ***Sanctuary* (`Min01`) Resource Targets:** Keep Fallout 4's exact `GLOB` thresholds (`5` beds, `5` water, `5` food, `2` defense) in `FO4SF_Sanctuary01` (`09000817`), or expose a lower quick-test threshold behind `FO4SF_TestModeEnabled` (`06000860`)?
