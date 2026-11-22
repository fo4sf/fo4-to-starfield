# Next Story Missions (`A7b`): *Reunions* (`MQ106`) & *Dangerous Minds* (`MQ201`/`MQ202`)

**Status:** `prototype, offline` / `design only` — whole-scope mission & places blueprint for the next two Fallout 4 main-story missions after *Getting a Clue* (`A7`), audited directly from `Fallout4.esm`, `FO4SFFortHagen.esm` (`0D`), and already-converted staged interiors (`interiors_b10`, zero reconversion). Offline verified via [`a7b_reunions_places.py`](../../scripts/terrain/a7b_reunions_places.py) (`W6` Normal + Open-Mode reachability); not yet implemented in `FO4SFMission.esm` and not yet run in Starfield (`OFFLINE ONLY — UNPROVEN IN GAME` per `R15`).

> **Whole-scope context:** This work continues the unbroken Fallout 4 main-story path in Starfield — Vault 111 -> Sanctuary -> Concord (*When Freedom Calls*, `A1`) -> *Sanctuary* / *The First Step* / *Jewel of the Commonwealth* (`A4`) -> *Unlikely Valentine* / *Getting a Clue* (`A7`) -> ***Reunions* & *Dangerous Minds* (`A7b`)** -> *The Glowing Sea* (`MQ204`) — while keeping every interior on already-converted staged assets and every quest behind the Story mode (`FO4SF_GameMode == 1`) gate with full Open-Mode dead-giver fallbacks.

---

## 1. Source-First `Fallout4.esm` Audit & FormID Reservations

Read directly from `Fallout4.esm` (no memory guesswork; zero copyrighted dialogue copied into Git):

| Playable Mission | `FO4SFMission.esm` Reservation | `Fallout4.esm` Source Record(s) | Exact `Fallout4.esm` Title & Structure | Handoff Target |
| --- | --- | --- | --- | --- |
| **`FO4SF_MQ106`** (*Reunions*) | **`0x000B00`** (`0x000B00..0x000B3F`) | `QUST MQ106` (`0x000229E7`) | *Reunions*: `35` stages (`0..2000`), `14` objectives (`10, 11..15, 40, 50, 75, 100, 125, 150, 200, 250`); aliases `Kellogg` (`0x0009BC6C`), `CyberBrain` (`0x0009BC6E`), `KelloggTerminal` (`0x000CD4AC`), `NickValentine` (`0x00002F24`), `Piper` (`0x00002F1E`), `dogmeat` (`0x0001D15C`). | Roof exit -> *Prydwen* arrival (`BoS200` `0x0002BF20` / `BoS100` `0x0005DDAB`); debrief -> `FO4SF_MQ201` (`0x000B40`). |
| **`FO4SF_MQ201`** (*Dangerous Minds*) | **`0x000B40`** (`0x000B40..0x000B7F`) | `QUST MQ202` (`0x000229E9`, *Dangerous Minds*) + `MQ201` (`0x000229E8`, *The Enemy of My Enemy* 0-obj bridge) + `MQ203` (`0x000229EA`, *Shattered* 0-obj dreamscape controller) | *Dangerous Minds*: `25` stages (`0..1000`), `5` objectives (`5` Brain Augmenter, `10` Talk to Doctor Amari, `100` Memory Lounger, `110` Explore Kellogg's memories, `120` Talk to Doctor Amari); aliases `Amari` (`0x0009A680`), `Irma` (`0x000228A5`), `NickValentine` (`0x00002F24`), `PlayerMemoryLounger` (`0x00053468`), `AmariLabDoor` (`0x000537C3`), `MemoryH_ExitDoor`. | Completion (`stage 300`) -> `MQ204` (*The Glowing Sea* `0x0006B500`, `Virgil` `0x0006B503`, `VirgilsLab01` `0x01069B10`). |

### Important Source-First Notes
1. **Fallout 4 quest numbering vs slot naming:** In `Fallout4.esm`, `MQ201` (`0x000229E8`) is the 0-objective Valentine's Agency transition scene (*The Enemy of My Enemy*), while **`MQ202` (`0x000229E9`)** carries the actual *Dangerous Minds* stages and objectives and **`MQ203` (`0x000229EA`)** controls the 8 memory vignettes (`MemoryA..MemoryH`) inside `MQ203KelloggsBrain`. Our unified Starfield quest record `FO4SF_MQ201` (`0x000B40`) folds all three into one clean, save/reload-safe quest so players never stall across three chained 0-objective handoffs.
2. **Disjoint FormID allocation:** `0x000B00..0x000B7F` is 100% disjoint from `A1(d)` (`0x800..0x9FF`), `A4` (`0xA00..0xA7F`), and `A7` (`0xA80..0xAFF`).
3. **`A5` Pip-Boy live quest scan window note:** `A5`'s current C++ `DATA / Quests` live scan window in `FO4SFPipboyMenu.dll` scans `FO4SFMission.esm` local IDs `0x000800..0x000AFF`. When `A7b` is implemented in `FO4SFMission.esm`, bump that C++ scan ceiling by one constant (`0xAFF -> 0xBFF`) so `0x000B00` and `0x000B40` appear automatically in `DATA / Quests` and on `MAP`.

---

## 2. Already-Converted & Staged Places Audit (`interiors_b10`, Zero Reconversion)

All **6** primary interior cells (plus all 3 *Prydwen* decks) are **already converted and staged** inside `interiors_b10` (`FO4Port.esm`) — **zero interior reconversion is required**:

| FO4 Cell (`Fallout4.esm`) | Staged Cell (`FO4Port.esm`, `interiors_b10`) | Staged Refs | Missions | Door / Lock / Trigger Integration Notes |
| --- | --- | ---: | --- | --- |
| `FortHagen01` (`0x000BB078`) | **`FO4Port_FortHagen01` (`0x0100BA4B`)** | 3,446 | `MQ106` | **Already wired by `FO4SFFortHagen.esm` (`0D`):** `RoofLoadDoorId 0x0547B0`, `RoofGateId 0x0232E1`, `RoofTermId 0x0232E0`, `Car01 0x00C580`, `MidLoadDoor01Id 0x00C7A7`, and stripped-`XESP` blockers (`Planks01Id 0x00C641`, `BlockerDoor01Id 0x00C7A8`, `BlockerBoards01Id 0x00C13A`). |
| `FortHagen02` (`0x000CD2AE`) | **`FO4Port_FortHagen02` (`0x0100CFC6`)** | 3,735 | `MQ106`, `MQ201` | **Already wired by `FO4SFFortHagen.esm` (`0D`):** `LoadDoor02Id 0x00DE53` (`FortHagen02LoadElevatorToExtREF` `0x0016850D`) <-> `RoofMarkerId 0x0A774C`. Contains Kellogg (`0x0009BC6C`), `MQ201CyberBrain` (`0x0009BC6E`), `DN057_KelloggTerminalPassword` (`0x000A02D8`), `DN057_KelloggTerminal01REF` (`0x000CD4AC`, lock `255`), `DN057_CommandCenterDoorREF` (`0x000CFF43`). |
| `GoodneighborTheMemoryDen` (`0x00022884`) | **`FO4Port_GoodneighborTheMemoryDen` (`0x0100ED4A`)** | 1,258 | `MQ201` | Needs exterior two-way load-door bridge `0x00022886 <-> 0x00022971` at Goodneighbor `(20826.12, -11904.71)`. Key interior refs: `DoctorAmariLabDoorREF` (`0x000537C3`, lock `255`), `PlayerMemoryLoungerREF` (`0x00053468`), `MQ203InstantEnterLoungerREF` (`0x0017FC1D`), `MQ203MemoryDenMagicDoor` (`0x00175522`), `MQ203MemoryDenReturnMarker` (`0x000D3CA0`). |
| `MQ203KelloggsBrain` (`0x000D393F`) | **`FO4Port_MQ203KelloggsBrain` (`0x0100F23E`)** | 1,136 | `MQ201` | Already staged (`4` `XTEL` markers incl. `MQ203MagicDoortoMemoryDen 0x00175521 <-> 0x00175522`). Key refs: `MQ203MemoryA/BExitBridgeCollision` (`0x0012BC38`/`0x0012BC37`), `MQ203MemoryHVirgilsFileRef` (`0x000D9749`). |
| `PrydwenHull01` (`0x0005C92E`) | **`FO4Port_PrydwenHull01` (`0x01003846`)** | 3,652 | `MQ106` | Paired with `FO4Port_PrydwenHull02` (`0x0104026D`, `483` refs) and `FO4Port_PrydwenHull03` (`0x0101099A`, `95` refs) for post-roof *Prydwen* arrival (`BoS200` `0x0002BF20` / `BoS100` `0x0005DDAB` at Boston Airport `48073.90, -3331.96`). |
| `VirgilsLab01` (`0x00156C0E`) | **`FO4Port_VirgilsLab01` (`0x01069B10`)** | 539 | `MQ201` | Already staged at Rocky Cave `(-116397.02, -136728.78)` for `MQ204` (*The Glowing Sea* `0x0006B500`, `Virgil` `0x0006B503`) handoff. |

---

## 3. Known-Bug Ledgers (`REUN-01..05` & `MIND-01..05`)

### *Reunions* (`FO4SF_MQ106`, `0x000B00`)
- **`REUN-01` (Dogmeat trail / breadcrumb stall):** In Fallout 4, Dogmeat stops along `TrailSite01..03` (`0x001337B5..7`) or clips terrain. **Mitigation:** Walking directly to Fort Hagen roof (`RoofLoadDoorId 0x0547B0`) or entering `FO4Port_FortHagen01` (`0x0100BA4B`) auto-advances `10 -> 50 -> 75` even if Dogmeat is dismissed or downed.
- **`REUN-02` (Fort Hagen elevator / blocker planks / roof gate trap):** Stripped-`XESP` planks (`0x00C641`, `0x00C7A8`, `0x00C13A`) and `RoofGateId 0x0232E1` can soft-lock interior traversal. **Mitigation:** Reuse `FO4SFFortHagen.esm` (`0D`, `FO4SF_FortHagenElevators 0x800`) directly and allow Open-Mode override on `RoofTermId 0x0232E0`.
- **`REUN-03` (Kellogg pre-attack / missing `MQ201CyberBrain` `0x0009BC6E` or password `0x000A02D8`):** Shooting Kellogg before dialogue or losing his corpse blocks `stage 125 -> 150`. **Mitigation:** Pre-attacking cleanly advances `100 -> 125`, and a desk backup container beside `DN057_KelloggTerminal01REF` (`0x000CD4AC`) always holds `MQ201CyberBrain` + `DN057_KelloggTerminalPassword` if Kellogg's corpse is unreachable.
- **`REUN-04` (Roof exit *Prydwen* arrival skipped by fast travel):** Exiting via backdoor or fast travel skips the roof elevator trigger (`LoadDoor02Id 0x00DE53 -> RoofMarkerId 0x0A774C`). **Mitigation:** Arm `FO4SF_PrydwenArrived=1` and the `BoS200`/`BoS100` radio/arrival hook on the next Commonwealth exterior load after `stage 150` regardless of exit route.
- **`REUN-05` (Nick/Piper dead or absent at debrief `stage 200`):** Open Mode allows completing `stage 200 -> 500` via Valentine's Agency desk log (`FO4Port_DmndValentines01` `0x01006B30`) OR arriving directly at `FO4Port_GoodneighborTheMemoryDen` (`0x0100ED4A`) carrying `MQ201CyberBrain`.

### *Dangerous Minds* (`FO4SF_MQ201`, `0x000B40`)
- **`MIND-01` (`DoctorAmariLabDoorREF` `0x000537C3` lock `255` soft-lock):** Scripted basement door stays locked if Irma/Amari stall or die. **Mitigation:** Open-Mode reception terminal or carrying `MQ201CyberBrain` (`0x0009BC6E`) unlocks `0x000537C3` directly (`10 -> 100`).
- **`MIND-02` (`MQ203KelloggsBrain` `0x0100F23E` neural bridge collision stall):** `MQ203MemoryA/BExitBridgeCollision` (`0x0012BC38`/`0x0012BC37`) can block progress if voiceover timers stall. **Mitigation:** Bounded `R10` watchdog enables each bridge automatically or on direct `E` activate, with direct skip to `MemoryH` (`MQ203MemoryHVirgilsFileRef 0x000D9749`) on reload/recovery.
- **`MIND-03` (Memory Lounger furniture sit-lock on `0x00053468`):** Starfield furniture anim mismatch can freeze camera/controls if forced into FO4 sit idle. **Mitigation:** Activating `PlayerMemoryLoungerREF` (`0x00053468`) or `MQ203InstantEnterLoungerREF` (`0x0017FC1D`) opens a clean `MessageBox` confirmation -> `MoveTo` `FO4Port_MQ203KelloggsBrain` (`0x0100F23E`), returning cleanly to `MQ203MemoryDenReturnMarker` (`0x000D3CA0`).
- **`MIND-04` (Arriving at Memory Den without `MQ201CyberBrain` `0x0009BC6E`):** Preserves `MQ202` `stage 5` (*Retrieve a Piece of Kellogg's Brain*) with a marker back to Fort Hagen Command Center (`0x0100CFC6`) backup container — zero dead end.
- **`MIND-05` (Doctor Amari dead / save-reload inside `0x0100F23E` breaks `MQ204` handoff):** Reading `MQ203MemoryHVirgilsFileRef` (`0x000D9749`) or Amari's lab terminal after returning to `0x0100ED4A` completes `stage 120 -> 300` and arms `MQ204` (*The Glowing Sea* -> `FO4Port_VirgilsLab01` `0x01069B10`).

---

## 4. `W6` 4-Axis Break-It Matrix (`P3`-Safe Batch IDs — Zero `M`/`N`/`V`)

Verified offline by `python scripts/terrain/a7b_reunions_places.py audit-a7b` (`0` unreachable stages, `0` stuck stages in both Normal Mode and Open-Mode dead-giver simulation):

| Mission | Axis | `P3`-Safe Batch | Scenario & Verified Recovery |
| --- | --- | --- | --- |
| `FO4SF_MQ106` (`0x000B00`) | Out of order | `bat a7b1` | Bypass Dogmeat, go straight to Fort Hagen roof (`0D 0x0547B0`) -> auto-advances `10 -> 50 -> 75`. |
| `FO4SF_MQ106` (`0x000B00`) | Giver/NPC dead | `bat a7b2` | Pre-attack Kellogg (`100 -> 125`), loot backup augmenter/password at `0x000CD4AC`, complete `200 -> 500` via agency desk or Memory Den arrival with Nick/Piper dead. |
| `FO4SF_MQ106` (`0x000B00`) | Save/reload & fast travel | `bat a7b1` / `bat a7b2` | Reload inside `FortHagen01`/`FortHagen02` preserves `0D` elevator state; fast travel after `stage 150` still fires *Prydwen* arrival on next exterior load (`REUN-04`). |
| `FO4SF_MQ201` (`0x000B40`) | Giver/NPC dead | `bat a7b3` | Irma & Doctor Amari dead -> `DoctorAmariLabDoorREF` (`0x000537C3`) unlocked by terminal/augmenter (`10 -> 100`), lounger `MessageBox` -> `MoveTo` `0x0100F23E` (`MIND-01`/`MIND-03`). |
| `FO4SF_MQ201` (`0x000B40`) | Save/reload & out of order | `bat a7b4` | Reload inside `MQ203KelloggsBrain` (`0x0100F23E`) -> `R10` bridge bypass to `MQ203MemoryHVirgilsFileRef` (`0x000D9749`) -> return to `0x000D3CA0` -> lab terminal completes `120 -> 300` & arms `MQ204` (`MIND-02`/`MIND-05`). |

---

## 5. `A5` `FO4SFPipboyQuestObjectives.tsv` Rows (`10` Verified Rows)

Generated deterministically by `python scripts/terrain/a7b_reunions_places.py emit-tsv` using verified Commonwealth map coordinates (`Fort Hagen (-87978.54, -5674.82)`, `Diamond City (-16384.00, -27852.80)`, `Goodneighbor (20826.12, -11904.71)`, `Edge of the Glowing Sea (-56092.31, -78515.81)`):

```tsv
0x000B00	10	Reunions	Follow Dogmeat to Fort Hagen	-87978.54	-5674.82	Fort Hagen
0x000B00	50	Reunions	Enter Fort Hagen and reach the Command Center	-87978.54	-5674.82	Fort Hagen
0x000B00	100	Reunions	Confront and defeat Kellogg	-87978.54	-5674.82	Fort Hagen
0x000B00	150	Reunions	Search Kellogg and his terminal, then exit to the roof	-87978.54	-5674.82	Fort Hagen
0x000B00	200	Reunions	Return to Diamond City and report to Nick or Piper	-16384.00	-27852.80	Diamond City
0x000B40	5	Dangerous Minds	Bring Kellogg's cybernetic brain augmenter to the Memory Den	20826.12	-11904.71	Goodneighbor
0x000B40	10	Dangerous Minds	Speak with Doctor Amari in Goodneighbor's Memory Den	20826.12	-11904.71	Goodneighbor
0x000B40	100	Dangerous Minds	Enter the Memory Lounger in Doctor Amari's lab	20826.12	-11904.71	Goodneighbor
0x000B40	110	Dangerous Minds	Explore Kellogg's memories to locate Virgil's trail	20826.12	-11904.71	Goodneighbor
0x000B40	120	Dangerous Minds	Speak with Doctor Amari and prepare for the Glowing Sea	-56092.31	-78515.81	Edge of the Glowing Sea
```

---

## 6. Consolidated Owner Questions

1. **Memory walk pacing in `MQ203KelloggsBrain` (`0x0100F23E`):** Should `FO4SF_MQ201` walk all 8 FO4 memory vignettes (`MemoryA..MemoryH`) with a skip-ahead `E` prompt on every bridge, or ship a concise 3-beat highlight walk (`MemoryA` -> `MemoryE` Vault 111 -> `MemoryH` Virgil file) first and expand to all 8 vignettes once voiced `.wem` scenes are wired?
2. **Brotherhood *Prydwen* roof flyover at Fort Hagen exit (`REUN-04`):** Until the animated exterior airship mesh flyover is ported, is an exterior radio/log arrival hook (`FO4SF_PrydwenArrived=1` + `BoS100`/`BoS200` quest unlock + staged `FO4Port_PrydwenHull01..03` boarding) acceptable as the initial in-game milestone?
3. **Goodneighbor worldspace hub vs direct Memory Den exterior door (`0x0100ED4A`):** Goodneighbor is a walled interior-like child worldspace in FO4; should `A7b` initially place the two-way Memory Den door (`0x00022886`) right at Goodneighbor's Commonwealth gate `(20826.12, -11904.71)` until the Goodneighbor child-worldspace pass lands?
