Titles: Fallout 4 -> all 7 Fallout titles (FO4, FO3, FNV, FO1, FO2, Tactics, FO76) | Modes: Story & Warfare (+ Survival hardcore layer) | Track: Track 1 (Fallout 4 playable path)

# A7 — Next Two Story Missions & Places: *Unlikely Valentine* (`MQ104`) and *Getting a Clue* (`MQ105`)

> **Status (`R15`):** `prototype, offline` / `design only` — source-first binary audit of `Fallout4.esm` and staged `FO4Port.esm` (`interiors_b10`, zero reconversion), plus deterministic `W6` 4-axis reachability checks in `scripts/terrain/a7_valentine_places.py`. Nothing here has run in the game yet.

---

## 1. FormID Reservation & Pip-Boy (`A5`) Alignment

To keep zero collisions with `A1(d)` (`FO4SFMission.esm:0x000800..0x0009FF`) and `A4` (`0x000A00..0x000A7F`), `A7` reserves **`FO4SFMission.esm:0x000A80..0x000AFF`** — which sits directly inside `A5`'s live Pip-Boy `DATA / Quests` scan window (`0x800..0xAFF`):

| Mission | FO4 Source `QUST` | Reserved `FO4SFMission.esm` ID | Reserved Block | Pip-Boy `A5` Objectives |
|---|---|---|---|---|
| ***Unlikely Valentine*** | `MQ104` (`0x0001F25E`, `49` stages, `4` objectives, `28` aliases) | **`0x000A80`** (`FO4SF_MQ104`) | `0x000A80..0x000AAF` | `10, 20, 30, 40` (Park Street Station, Vault 114, Diamond City) |
| ***Getting a Clue*** | `MQ105` (`0x000229E6`, `51` stages, `9` objectives, `36` aliases) | **`0x000AB0`** (`FO4SF_MQ105`) | `0x000AB0..0x000AFF` | `10, 30, 60, 80` (Diamond City, Kellogg's House, Fort Hagen) |

---

## 2. Places Audit — All Six Interiors Already Staged (`interiors_b10`, Zero Reconversion)

Binary inspection of `Fallout4.esm` and staged `FO4Port.esm` confirms two critical source-first facts:
1. **Park Street Station is inside `Vault114` (`0x000428E4`), not a separate cell:** `Fallout4.esm` has no `ParkStreetStation01` cell; the metro station and upper vault tunnels live in `Vault114`, and the lower overseer/prison wing lives in `Vault11402` (`0x0007BEF3`).
2. **Kellogg's House is `DmndStandsKellogg01` (`0x00001E50`)**, not `DmndKelloggsHouse01`, and is already converted and staged in `interiors_b10`.

| FO4 Interior Cell (`Fallout4.esm`) | Staged `FO4Port.esm` Cell (`interiors_b10`) | Refs | Internal `XTEL` Doors | What It Needs to Work Beyond Loading |
|---|---|---|---|---|
| `Vault114` (`0x000428E4`) | `FO4Port_Vault114` (`0x01002593`) | `5,147` | `2` (`0x0100383E <-> 0x01011916`, `0x01003840 <-> 0x01011917`) | Two-way `FO4SF_LoadDoor` VMAD pairs for `0x0008E70F <-> 0x0004BAF6` (Park Street Station metro entrance) and `0x000428E6 MQ104ServiceLadderREF <-> 0x00042908` (Boston Common escape ladder); scripted unlock on `0x0007C051` (lock `255`); confrontation trigger at `MQ104SkinnyMaloneMarker01` (`0x00083FB6`); side locks (`0x0004BC21` & `0x0013B6EB`, lock `75`). |
| `Vault11402` (`0x0007BEF3`) | `FO4Port_Vault11402` (`0x010109FA`) | `3,861` | `2` (paired back to `FO4Port_Vault114`) | Dual unlock on `NickPrisonDoorREF` (`0x0007E7A4`, lock `25` Novice) via Overseer terminal `0x000ADA18` OR Lockpick; scripted unlock + `R10` proximity override on `MQ104NickDoor02REF` (`0x0008A80C`, lock `255`); enable state on `Vault114AtriumGoonsEnableMarker` (`0x0011B183`). |
| `DmndValentines01` (`0x00001E47`) | `FO4Port_DmndValentines01` (`0x01006B30`) | `277` | `0` (`DiamondCityWorld` child worldspace) | Two-way `FO4SF_LoadDoor` bridge from Diamond City exterior hub / `DmndGateREF` to `0x000022CB` until `DiamondCityWorld` is staged; `NickValentineREF` (`0x00002F25`), chair alias (`60`), and Open-Mode Kellogg dossier activator on Nick's desk. |
| `DmndStandsKellogg01` (`0x00001E50`) | `FO4Port_DmndStandsKellogg01` (`0x0106B72C`) | `224` | `0` (`DiamondCityWorld` child worldspace) | Two-way `FO4SF_LoadDoor` bridge on `KelloggHouseDoorREF` (`0x000021B4`, lock `100` Master OR Mayor/Geneva key); first-person `E` activation on `KelloggSecretDoorButtonREF` (`0x0011E23C` under `MQ105KelloggDesk` `0x0011E23B`) opening `MQ106KelloggSecretDoorREF` (`0x0011E235`, lock `254`); explicit enable on `MQ105KelloggItemsEnableMarker` (`0x00065F88`) & `MQ105InvestigateTableEnableMarker` (`0x0014586A`) for `KelloggCigar01`. |
| `FortHagen01` (`0x000BB078`) | `FO4Port_FortHagen01` (`0x0100BA4B`) | `3,446` | `1` (`0x0100C7A7 <-> 0x0100DE51`) | **Already wired by `FO4SFFortHagen.esm` (`0D` in Track-1 player bundle):** roof load door `0x0547B0`, roof security gate `0x0232E1`, roof terminal `0x0232E0`, and interior elevator rig (`0x00C580` / `0x00C7AB..0x00C7B4`). |
| `FortHagen02` (`0x000CD2AE`) | `FO4Port_FortHagen02` (`0x0100CFC6`) | `3,735` | `1` (`0x0100DE51 <-> 0x0100C7A7`) | **Already wired by `FO4SFFortHagen.esm` (`0D`):** lower elevator (`0x00DE52`/`0x00DE53`) to `RoofMarkerId` (`0x0A774C`); `KelloggREF` (`0x0009BC71`) + `DN057_KelloggTerminal01REF` (`0x000CD4AC`) for `MQ106` (*Reunions*) handoff. |

---

## 3. Mission Specs, Key NPCs & Known-Bug Ledgers

### 3.1 *Unlikely Valentine* (`FO4SF_MQ104` `0x000A80`)
- **Start / Completion:** Starts from `FO4SF_MQ103` (*Jewel of the Commonwealth*, Ellie Perkins `0x000222A2`) OR out-of-order by entering Park Street Station / `Vault114` (`0x000428E4`). Completes at `stage 200` on escaping Vault 114 and debriefing Nick Valentine (`0x00002F24`, Essential in FO4) or recovering his case file in Open Mode, starting `FO4SF_MQ105`.
- **Key NPCs:** `CompanionNickValentine` (`0x00002F24`, FO4 Essential=true), `MQ104SkinnyMalone` (`0x00083FB4`, Essential=false), `MQ104Darla` (`0x000969D9`, Essential=false), `MQ104MobsterTaunter` (`0x0017412F`, Essential=false).
- **Known-Bug Ledger (`UVAL-01..05`):**
  - `UVAL-01`: `NickPrisonDoorREF` (`0x0007E7A4`) stuck locked if terminal `0x000ADA18` fails -> wire both terminal unlock and Novice Lockpick (`25`) + triggerman overseer key fallback.
  - `UVAL-02`: `MQ104NickDoor02REF` (`0x0008A80C`, lock `255`) or `0x0007C051` stalls escape if Nick pathing stalls -> bounded `5 s` proximity auto-unlock once stage >= `60` (`R10`).
  - `UVAL-03`: Skinny Malone / Darla confrontation (`stage 85 -> 100`) stalls if player engages early -> accept Speech persuasion (Darla or Malone) OR combat victory interchangeably.
  - `UVAL-04`: Nick left behind inside Vault 114 on cell transition -> bounded `MoveTo` tether on exiting to Boston Common + `OnPlayerLoadGame` re-check.
  - `UVAL-05`: Open-Mode (`W7`) dead-giver safety -> if Nick or Ellie die, reading the Overseer case notes/agency dossier still advances `40 -> 60 -> 85 -> 100 -> 200` and unlocks `FO4SF_MQ105`.

### 3.2 *Getting a Clue* (`FO4SF_MQ105` `0x000AB0`)
- **Start / Completion:** Starts on `FO4SF_MQ104` stage `200` (or out-of-order on discovering Kellogg's hidden armory in `DmndStandsKellogg01`). Completes at `stage 200` on reaching Fort Hagen (`00090A`, FO4 `(-87978.54, -5674.82)`) / `FO4Port_FortHagen01` roof door (`0x0547B0`), handing off to *Reunions* (`MQ106` `0x000229E7`).
- **Key NPCs:** `CompanionNickValentine` (`0x00002F24`, Essential=true), `ElliePerkins` (`0x000222A2`, Essential=true), `Geneva` (`0x00002F0A`, Essential=true), `MayorMcDonough` (`0x00002F08`, Essential=true), Dogmeat (`alias 17`), `Kellogg` (`0x0009BC6C`, Essential=false, inside `FortHagen02`).
- **Known-Bug Ledger (`CLUE-01..05`):**
  - `CLUE-01`: `KelloggHouseDoorREF` (`0x000021B4`, lock `100` Master) soft-locks if Geneva/McDonough dialogue fails or they die in Open Mode -> keep Mayor's desk key (`MayorDesk` `alias 12`) lootable and Master lockpick always valid.
  - `CLUE-02`: `KelloggSecretDoorButtonREF` (`0x0011E23C`, tucked under `MQ105KelloggDesk` `0x0011E23B`) hard to hit in first person -> verify standing/crouched `E` hitbox and mirror trigger on desk inspection (`R10`).
  - `CLUE-03`: `MQ105KelloggItemsEnableMarker` (`0x00065F88`) leaves `KelloggCigar01` disabled when `XESP` is stripped -> explicitly enable clue refs on entering `DmndStandsKellogg01` at stage >= `30`.
  - `CLUE-04`: Dogmeat scent-tracking pathing stall across exterior cells / fast travel -> allow BOTH Dogmeat trail tracking AND direct player arrival at Fort Hagen (`00090A` / `FO4SFFortHagen.esm` roof entry) to finish `stage 200`.
  - `CLUE-05`: Open-Mode (`W7`) dead-giver safety -> if Nick, Geneva, McDonough, or Dogmeat are dead/absent, reading the agency dossier + opening Kellogg's secret room + inspecting the cigar advances directly to Fort Hagen (`stage 200`).

---

## 4. `W6` 4-Axis Break-It Matrix & Offline Verification (`scripts/terrain/a7_valentine_places.py`)

Both quests pass `python scripts/terrain/a7_valentine_places.py audit-a7` (`pass: true`, `0` unreachable stages, `0` stuck stages in both Normal Mode and Open-Mode dead-giver simulation where every `npc_gated` transition is removed):
- **Giver Dead (`W7` Open Mode):** Every NPC-gated edge (`40->60`, `60->85`, `85->100`, `100->200` in `FO4SF_MQ104`; `10->30`, `30->60`, `80->100` in `FO4SF_MQ105`) has an explicit non-NPC fallback edge verified by single-edge removal mutation tests.
- **Out of Order:** Direct Vault 114 entry, early Skinny Malone combat, direct Master lockpick on Kellogg's House, and direct Fort Hagen arrival all converge cleanly.
- **Save & Reload Every Stage:** `OnPlayerLoadGame` re-asserts scripted door lock/unlock states, clue enable markers, and Nick tether across all `7 + 6 = 13` stages.
- **Fast Travel Away:** Leaving Boston Common, Diamond City, or the Dogmeat trail mid-quest never strands objectives or breaks Fort Hagen arrival completion.
- **`P3` Zero-`M`/`N`/`V` Console Batch IDs (Future PC Card):** `bat a7p1` (Park Street Station / Vault 114 check), `bat a7p2` (Kellogg's House secret room check), `bat a7fh` (Fort Hagen arrival handoff check).

---

## 5. `A5` Pip-Boy `FO4SFPipboyQuestObjectives.tsv` Rows

Generated by `python scripts/terrain/a7_valentine_places.py emit-tsv` (exact Commonwealth coords from `FO4SFPipboyMapMarkers.tsv`):
- `FO4SFMission.esm` `000A80` obj `10` -> Park Street Station `(14878.14, -15941.30)`
- `FO4SFMission.esm` `000A80` obj `20` & `30` -> Vault 114 `(8019.57, -18075.20)`
- `FO4SFMission.esm` `000A80` obj `40` -> Diamond City `(-16384.00, -27852.80)`
- `FO4SFMission.esm` `000AB0` obj `10`, `30`, `60` -> Diamond City `(-16384.00, -27852.80)`
- `FO4SFMission.esm` `000AB0` obj `80` -> Fort Hagen `(-87978.54, -5674.82)`

---

## 6. Owner Questions (Consolidated)

1. **Dogmeat Scent Trail (`FO4SF_MQ105` `CLUE-04`):** Until full multi-cell companion navmesh following is verified in game, should *Getting a Clue* use waypoint-to-waypoint clue markers (cigar -> red bandana -> bloodied rags -> Fort Hagen) with Dogmeat warping between clue stops, or wait for full continuous multi-cell Dogmeat pathing?
2. **Diamond City Interior Hub Bridge (`DmndValentines01` / `DmndStandsKellogg01`):** Until `DiamondCityWorld` is staged as a child worldspace, do you approve keeping the temporary `DmndGateREF` exterior hub doors to Valentine's Agency (`0x01006B30`) and Kellogg's House (`0x0106B72C`) so `A4` + `A7` are playable end-to-end immediately?
