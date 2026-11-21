# Quest Testing Plan — Four-Tier Verification (`W6` / `W7`)

> **Public-Surface & Clean-Room Policy:** Zero verbatim game dialogue, journal text, executable bytes, third-party mod names, or local drive paths appear in this document. Quests, globals, activators, NPCs, and log lines are referenced strictly by clean-room functional descriptions, verified plugin FormIDs, and real Papyrus/C++ trace format strings.

This plan defines how FO4SF verifies quest correctness across **Fallout 4** (playable path first, then main spine), **Fallout 3**, and **Fallout: New Vegas** without requiring the owner to hand-play every side quest, while still catching single-path lockouts, sequence breaks, and **`W7` Open Mode** (Survival/Hardcore essential-NPC-dead) softlocks.

---

## Executive Summary — Exact Quest Counts by Tier

Counts below are computed deterministically by `scripts/testing/check_quest_fragility.py --open-mode` over `src/fo4sf/testing/quest_test_catalog.json` (and verified by `tests/test_quest_fragility.py`):

| Verification Tier | Scope | Fallout 4 | Fallout 3 (`#829`) | Fallout: New Vegas (`#829` + `VMS38`) | Catalog Total | Full Base-ESM Census Scaling (`1,964` Base Quests) |
|---|---|---:|---:|---:|---:|---|
| **Tier 1 — Offline State & Fragility** | Every quest's stages, globals, items, flags, essential NPCs, W7 Open Mode dead-NPC fallbacks, and cut-edge fragility | `19` (`4` staged + `15` spine) | `20` (`10` main + `10` side) | `21` (`10` main + `10` side + `VMS38`) | **`60`** | Scales to `100%` (`1,336` FO4 + `192` FO3 + `436` FNV) as waves convert |
| **Tier 2 — Break-It Batch Cases** | `6` break-it cases per quest (`24` concrete batch recipes for the `4` staged FO4 quests + `6`-case template for `15` FO4 spine targets) | `19` (`4` live + `15` templated) | `0` *(enters at Waves A–D)* | `0` *(enters at Waves A–D)* | **`19`** | Every converted story & major side quest gets `6` batch recipes |
| **Tier 3 — Known-Bug Regressions** | `#820` FO4 ledgers (`19` bugs), `3` FO4 spine community patterns, `#829` FO3/FNV ledgers (`40` bugs), plus `RF-FNV-001` (`VMS38`) | `7` (`4` `#820` + `3` spine) | `20` (`FO3M-01..10`, `FO3S-01..10`) | `21` (`FNVM-01..10`, `FNVS-01..10`, `VMS38`) | **`48`** | `63` concrete bug regressions across `48` quests; fixes faults rather than copying them |
| **Tier 4 — Owner Play** | **Strictly** Main Spine + `FRAGILE` list + Feel items (`14` non-fragile side quests are `100%` offloaded to Tiers 1–3) | `19` (`4` staged feel + `15` spine) | `13` (`10` main + `3` FRAGILE side) | `14` (`10` main + `4` FRAGILE/feel side) | **`46`** | Bounded strictly to main spines + `FRAGILE` list + feel items (`>90%` side quests stay automated) |
| **`FRAGILE` List Subset** | Algorithmically detected single-edge progression chokepoints or high-risk multi-actor/reward sequences | `5` | `6` | `7` | **`18`** | Automatically regenerated on every catalog change |

---

## 1. Tier 1 — Offline State-Machine & Fragility Checker

### 1.1 Architecture & CLI Usage

- **Catalog:** `src/fo4sf/testing/quest_test_catalog.json` (`60` quests modeled with stages, globals, items, flags, essential NPCs, W7 Open Mode fallbacks, reachable entry states, directed transition edges, and reward routes).
- **Checker:** `scripts/testing/check_quest_fragility.py` performs two offline proofs:
  1. **Check (a) — No Dead Ends from Any Reachable Player State:** Starting from every reachable stage, out-of-order arrival state, pre-cleared hostile state, and (under `--open-mode`) every single-essential-NPC-dead state, verifies a directed path exists to a valid completion stage (or clean spine handoff). Any dead end fails with exit code `1`.
  2. **Check (b) — Single-Edge Fragility & Single-Route Reward Detection:** Deletes each normal-play progression edge one at a time to identify cut edges (single-edge chokepoints disconnecting `start_stage` from primary completion) and flags any reward reachable by `< 2` routes. Outputs the deterministic **`FRAGILE` list** and exact per-tier quest counts.
- **Unit Tests:** `tests/test_quest_fragility.py` proves clean pass (`0` dead ends in Normal and `--open-mode`), normal/out-of-order/Open-Mode dead-end mutation detection, cut-edge & single-route reward detection, and `R11`/`P3`/redaction compliance.

```bash
python scripts/testing/check_quest_fragility.py
python scripts/testing/check_quest_fragility.py --open-mode
python scripts/testing/check_quest_fragility.py --game FO4 --open-mode --json
python -m unittest tests.test_quest_fragility
```

### 1.2 Fallout 4 Playable Path (`4` Staged) & Main Spine (`15` Conversion Targets) — Dependencies & `W7` Open Mode Fallbacks

Every Fallout 4 mission below lists its stages, flag/global/item dependencies, transition paths, essential NPCs, and **one-line `W7` Open Mode fallback if each essential NPC dies** (Normal mode keeps essential NPCs unkillable; Survival/Hardcore Open Mode allows any NPC to die while preserving game completion):

| Quest (`Plugin` / `FormID`) | Status | Stages (Comp) | Key Flags, Globals & Items | Transition Paths | Essential NPCs & `W7` Open Mode Fallback (One Line Each) | Fragile? |
|---|---|---|---|---|---|---|
| `FO4SF_NewGame` (`FO4SFNewGame.esm:0x000800`) | **Staged** | `0, 1, 5, 10, 20, 30, 40, 200, 210` (`200, 210`) | `FO4SF_GameMode` (`0x000870`), `FO4SF_SurvivalStart` (`0x000871`), `FO4SF_PipboyAcquired` (`0x000865`), `FO4SF_PipboyWrist` (`0x00080D`), `FO4SF_Vault111PistolRef` (`0x000820`), `0x00080F` pickup -> `0x000819` console | `0->5->10->20->30->40->200` (Story); `0->5->210` (Warfare); `0->1` (NG+ stand-down); `10->20` `120s` fallback; `30->40` exit fallback; `40->200` fall recovery | None (solo Vault 111 interior opening). | **FRAGILE** (`20->30` `R10` console gate; `U1` break) |
| `FO4SF_Codsworth01` (`FO4SFMission.esm:0x000816`) | **Staged** | `0, 10, 20, 30, 40, 100` (`100`) | `FO4SF_GameMode != 2`, `FO4SF_Codsworth01_Scene` (`0x000940`), `FO4SF_CodsworthKeeper` (`0x000814`) | `0->10->(20\|30\|40)->100` (Choice 4 -> `FO4SF_Min00` stage `10`); `10->100` Concord `<=150 m` proximity bypass | `FO4_Codsworth` (`0x000811`): Walking within `150 m` of Concord auto-starts `FO4SF_Min00` stage `10` and clears objective `10` (`ClearObjectiveOnConcordStart`); Sanctuary terminal/holotape also supplies the Concord breadcrumb. | No |
| `FO4SF_Min00` (`FO4SFMission.esm:0x000800`) | **Staged** | `0, 10, 20, 30, 35, 40, 200` (`200`) | `FO4SF_GameMode != 2`, `FO4SF_TestModeEnabled` (`0x000860`), `FO4SF_MinutemenFaction` (`0x00081F`), `PrestonTalkScene` (`0x000900`/`0x00092A`), `Credits` (`0x00000F` x100) | `0->10` (Codsworth or `<=150 m` Concord) -> `20` (raiders `<=60 m` or Preston `<=20 m`) -> `30` (raiders dead or `WFC-01` write-off) -> `35/40` (scene or `120s` `TalkRadius`) -> `200` | `FO4_PrestonGarvey` (`0x000802`): Loot Minutemen Dispatch note from Preston's corpse (or Museum front terminal) to unlock Sanctuary/Diamond City leads; main spine proceeds directly via Diamond City (`MQ103`) without Minutemen. | **FRAGILE** (`20->30` raider gate + Preston turn-in) |
| `FO4SF_Sanctuary01` (`FO4SFMission.esm:0x000817`) | **Staged** | `0, 10, 100` (`100`) | `FO4SF_GameMode != 2`, `FO4SF_Min00 >= 200`, Sanctuary workbench `FO4TerrainCore.esm:0x005C50` (`ACTI 0x0A2ECD`) | `0->10->100` via `OnActivate`, `OnWorkshopMode`, or `120 s` (`8 s` test mode) proximity fallback if bench unbound | None (object-driven settlement objective). | No |
| `MQ103` (`FO4:MQ103`) | Spine Target | `0, 10, 20, 30, 100` (`100`) | `FO4SF_DCGateOpen`, `FO4SF_NickLeadFound`, DC gate intercom | `0->10->20->30->100` (Piper gate scene OR intercom/lockpick bypass -> Agency lead) | `FO4_Piper`: Activate DC front intercom or lockpick/terminal-override gate and read Agency sign. `FO4_MayorMcDonough`: Intercom override or looted Mayor's Gate Key opens DC. `FO4_ElliePerkins`: Read Nick's case-file terminal on the Agency desk to start `MQ104`. | No |
| `MQ104` (`FO4:MQ104`) | Spine Target | `0, 10, 20, 30, 100` (`100`) | `FO4SF_NickRescued`, `FO4SF_Vault114Opened`, Overseer key/password | `0->10->20->30->100` (combat, stealth, or Speech exit with Triggermen) | `FO4_NickValentine`: Loot Nick's Detective Case Holotape from his body (or read Agency terminal) to unlock Kellogg's house investigation and start `MQ105`. | No |
| `MQ105` (`FO4:MQ105`) | Spine Target | `0, 10, 20, 30, 100` (`100`) | `FO4SF_KelloggHouseSearched`, `FO4SF_FortHagenLocated`, Kellogg's House Key, cigar | `0->10->20->30->100` (Dogmeat scent trail OR direct Fort Hagen discovery) | `FO4_Dogmeat`: Inspecting the cigar/route notes in Kellogg's secret room places the Fort Hagen marker directly. `FO4_NickValentine`: Pick Kellogg's house lock or loot key from Mayor's office and travel straight to Fort Hagen. | No |
| `MQ106` (`FO4:MQ106`) | Spine Target | `0, 10, 20, 30, 100` (`100`) | `FO4SF_FortHagenRoofOpened` (`FO4SF_FortHagenQuest`), `FO4SF_PrydwenArrived`, Cybernetic Brain Augment | `0->10->20->30->100` (Fort Hagen elevators -> Kellogg -> roof gate) | `FO4_NickValentine`: Reading Kellogg's terminal + looting his Cybernetic Brain Augment points directly to the Memory Den (`MQ201`). | **FRAGILE** (`20->30` Fort Hagen elevators + brain loot) |
| `MQ201` (`FO4:MQ201`) | Spine Target | `0, 10, 20, 30, 100` (`100`) | `FO4SF_MemoryDiveComplete`, `FO4SF_VirgilLeadFound`, Cybernetic Brain Augment | `0->10->20->30->100` (Memory lounger dive OR automated terminal playback) | `FO4_DoctorAmari`: Use the Memory Den mainframe terminal (Science or looted Amari password) for automated playback, or walk directly to Virgil's Cave. `FO4_Irma`: Walk straight into the basement lab. | No |
| `MQ202` (`FO4:MQ202`) | Spine Target | `0, 10, 20, 30, 100` (`100`) | `FO4SF_VirgilMet`, `FO4SF_CourserLeadFound`, `CF-7` rad protection | `0->10->20->30->100` (Crater of Atom lead OR direct Glowing Sea navigation) | `FO4_Virgil`: Loot Virgil's Relay Schematics & Courser tracking frequency from his cave terminal/footlocker to start `MQ203`. | No |
| `MQ203` (`FO4:MQ203`) | Spine Target | `0, 10, 20, 30, 100` (`100`) | `FO4SF_CourserSignalTracked`, `FO4SF_CourserChipLooted`, Courser Chip | `0->10->20->30->100` (radio triangulation OR direct Greenetech Genetics climb; combat or recall-code speech) | None (Courser Z2-47 is an intended combat/recall target; chip is always lootable). | No |
| `MQ204` (`FO4:MQ204`) | Spine Target | `0, 10, 20, 30, 100` (`100`) | `FO4SF_ChipDecoded`, `FO4SF_InterceptorBuilt`, `FO4SF_InterceptorFaction`, Decoded Chip | `0->10->20->30->100` (decode chip -> build & power 4 Signal Interceptor pieces) | `FO4_TinkerTom`: Self-decode on Railroad HQ terminal (Science or looted Tom cipher holotape). `FO4_Desdemona` / `FO4_Sturges` / `FO4_ProctorIngram`: Switch to any surviving faction engineer or self-assemble at an owned workshop schematic terminal. | **FRAGILE** (`20->30` decode + workshop wiring gate) |
| `MQ205` (`FO4:MQ205`) | Spine Target | `0, 10, 20, 30, 100` (`100`) | `FO4SF_InstituteEntered`, `FO4SF_InstituteBanished`, `FO4SF_NetworkScannerDone`, Network Scanner Holotape | `0->10->20->30->100` (meet department heads OR kill Father -> emergency relay exit) | `FO4_Father`: Killing Father immediately triggers Banished from the Institute, activates the emergency relay override terminal to exit, and opens Minutemen/BoS assault. `FO4_DoctorLi_FO4`: Install Pip-Boy relay chip at Advanced Systems terminal. | No |
| `MQ206` (`FO4:MQ206`) | Spine Target | `0, 10, 20, 30, 100` (`100`) | `FO4SF_BunkerHillOutcome`, `FO4SF_InstituteHostile`, `FO4SF_RailroadHostile`, utility key | `0->10->20->30->100` (Institute, Railroad, BoS, or double-cross pivot) | `FO4_Father` / `FO4_Desdemona` / `FO4_ElderMaxson`: Warning/report steps for any dead faction leader skip cleanly; resolve through any surviving aligned faction. | **FRAGILE** (`20->30` 3-faction crossfire pivot) |
| `MQ207` (`FO4:MQ207`) | Spine Target | `0, 10, 20, 30, 100` (`100`) | `FO4SF_AgitatorOwner`, `FO4SF_BoSHostile`, `FO4SF_InstituteHostile`, Beryllium Agitator | `0->10->20->30->100` (Institute relay OR BoS Vertibird / on-foot entry) | `FO4_AllieFilmore` / `FO4_ProctorIngram`: Mass Fusion elevator terminal or Vertibird deck dispatches directly; if faction hostile, continue with surviving aligned faction. | No |
| `MQ302Min` (`FO4:MQ302Min`) | Spine Target | `0, 10, 20, 30, 100` (`100`) | `FO4SF_EndgameFaction=Minutemen`, `FO4SF_InstituteDestroyed`, Fusion Pulse Charge | `0->10->20->30->100` (independent/Minutemen endgame fallback) | `FO4_PrestonGarvey`: Minutemen Radio Officer / Castle terminal dispatches Castle defense and assault squad. `FO4_Sturges`: Castle relay terminal + looted Fusion Pulse Charge schematic lets the player breach the reactor solo. | No |
| `MQ302BoS` (`FO4:MQ302BoS`) | Spine Target | `0, 10, 20, 30, 100` (`100`) | `FO4SF_EndgameFaction=BoS`, `FO4SF_LibertyPrimeReady`, Fusion Pulse Charge | `0->10->20->30->100` (Brotherhood endgame) | `FO4_ElderMaxson`: Proctor Ingram or Lancer-Captain Kells assumes command (if entire BoS wiped out, finish via Minutemen, Railroad, or Institute). `FO4_ProctorIngram`: Liberty Prime launch console activates directly once Agitator is installed. | No |
| `MQ302RR` (`FO4:MQ302RR`) | Spine Target | `0, 10, 20, 30, 100` (`100`) | `FO4SF_EndgameFaction=Railroad`, `FO4SF_UndergroundUndercoverDone`, Relay Access Code | `0->10->20->30->100` (Railroad endgame) | `FO4_Desdemona`: Deacon or Tinker Tom leads the assault (if entire Railroad wiped out, finish via Minutemen, BoS, or Institute). `FO4_TinkerTom`: Relay control terminal + Vertibird autopilot beacon replaces Tom. | No |
| `MQ302Inst` (`FO4:MQ302Inst`) | Spine Target | `0, 10, 20, 30, 100` (`100`) | `FO4SF_EndgameFaction=Institute`, `FO4SF_PrydwenDestroyed`, Relay Targeting Chip | `0->10->20->30->100` (Institute endgame) | `FO4_Father`: Killing Father fails Institute cleanly and routes endgame to Minutemen, BoS, or Railroad. `FO4_JustinAyo`: Directorate terminal or surviving division head issues deployment orders. | No |

### 1.3 Fallout 3 Census (`20` Quests from `#829` `Fallout3.esm`)

| Quest (`FormID`) | Track | `INDX` / `QOBJ` | Key Script, Flag & Item Dependencies | `W7` Open Mode Essential-NPC Fallback | Bug Ledger | Fragile? |
|---|---|---:|---|---|---|---|
| `CG01` (`0x014E83`) | Main | `20` / `8` | `CG01SCRIPT` (`MenuMode`+`GameMode`), `CG01SpecialBookSCRIPT` (`CF-6`) | `FO3_Dad`: Interior tutorial; Open Mode quick-start uses exit rebuild prompt | `FO3M-01` | No |
| `CG02` (`0x014E84`) | Main | `31` / `5` | `CG02SCRIPT` (`56` `PACK`s), `SayTo` `<=12s` watchdog, BB Gun | `FO3_Amata`: `SayTo` watchdog unlocks diner door into reactor tutorial | `FO3M-02` | No |
| `CG03` (`0x014E85`) | Main | `19` / `5` | `CG03Script` (`84` vars), hallway `StopCombatAlarm`, `3` tag skills | `FO3_MrBrotch`: Classroom desk terminal opens `CF-6` `3`-tag-skill selector | `FO3M-03` | **FRAGILE** |
| `CG04` (`0x014E86`) | Main | `36` / `7` | `CG04Script` (`110` faction checks), `CF-10` exterior exit landing | `FO3_Amata`: Loot Overseer password or pick office lock to open tunnel | `FO3M-04` | No |
| `MQ01` (`0x014E87`) | Main | `44` / `8` | `MQ01Script` (`109` cross-`INFO`), sequence-skip catch-up, Fat Man | `FO3_ColinMoriarty` / `FO3_ThreeDog`: Hack Moriarty/GNR terminal or walk directly to Rivet City (`MQ03`) / Vault 112 (`MQ04`) | `FO3M-05` | No |
| `MQ02` (`0x014E88`) | Main | `8` / `6` | `MQ02QuestScript` (`0` owned `DIAL`, `20` cross-`INFO`), Virgo II dish | `FO3_ThreeDog`: Monument activator completes `MQ02`; Rivet City / Vault 112 remain open | `FO3M-06` | No |
| `MQ03` (`0x014E89`) | Main | `10` / `8` | `MQ03Script`, Vault 112 suit (`0x04B1D0`), Purity holotapes | `FO3_DoctorLi`: Listen to Purity holotapes or enter Smith Casey's Garage directly | `FO3M-07` | No |
| `MQ04` (`0x014E8A`) | Main | `16` / `14` | `MQ04Script` (`32` ext scripts), persistent inventory stash checksum, `CF-1` Karma | `FO3_Dad`: Tranquility Lane failsafe terminal exits simulation and logs Jefferson Memorial | `FO3M-08` | **FRAGILE** |
| `MQ05` (`0x014E8B`) | Main | `20` / `16` | `MQ05Script` (`58` ext scripts, `61` `PACK`s), `CF-7` chamber rads, `SetRestrained` clear | `FO3_DoctorLi`: Loot Citadel entry pass from Li and use Taft Tunnels gate intercom | `FO3M-09` | **FRAGILE** |
| `MQ06` (`0x014E8C`) | Main | `9` / `7` | `MQ06Script`, `20s` courtyard watchdog, `CF-8` PA training gate | `FO3_ElderLyons`: Citadel Lab Vault-Tec mainframe grants Vault 87 data and PA manual | `FO3M-10` | No |
| `MS01` (`0x014E94`) | Side | `22` / `8` | `MS01QuestScript` (`61` vars, `79` `PACK`s), `13` defense skill checks | `FO3_Red`: Bittercup/Timebomb leads briefing; if all residents die, closes cleanly | `FO3S-01` | **FRAGILE** |
| `MS02` (`0x014E95`) | Side | `14` / `7` | `MS02QuestScript` (`60` vars), `StopCombatAlarm` on lair entry | `FO3_UncleRoe`: Resolving both lairs completes `MS02`; caps lootable from safe | `FO3S-02` | No |
| `MS03` (`0x014E96`) | Side | `34` / `34` | `MS03script` (`71` vars, `255` `INFO`s, `69` skill checks), `CF-7` rads | `FO3_MoiraBrown`: Survives `MS11` in Underworld; if killed, her terminal publishes earned tier | `FO3S-03` | **FRAGILE** |
| `MS04` (`0x014E97`) | Side | `8` / `11` | `MS04Script` (`77` vars), explicit `Ref.IsDead()` on `5` guardians | `FO3_BryanWilks`: Clearing nest or helping Dr. Lesko resolves Grayditch independently | `FO3S-04` | No |
| `MS05` (`0x014E98`) | Side | `7` / `6` | `MS05QuestScript` (`47` vars), live `GetItemCount >= 30` gate | `FO3_SierraPetrovita`: Turn in to Ronald Laren, or loot schematic from Sierra's safe | `FO3S-05` | No |
| `MS06` (`0x014E99`) | Side | `11` / `16` | `MS06Script` (`60` `PACK`s, `110` cross-`INFO`), `24h` march `MoveTo` | `FO3_HannibalHamlin`: Caleb Smith leads march, or Leroy Walker branch completes `MS06` | `FO3S-06` | No |
| `MS08` (`0x014E9B`) | Side | `10` / `8` | `MS08QuestScript` (`116` vars, `32` skill checks), `!IsCompleted()` lock | `FO3_Zimmer`: Resolve via Harkness, Victoria Watts, or Pinkerton's terminal | `FO3S-07` | No |
| `MS09` (`0x014E9C`) | Side | `9` / `10` | `MS09QuestScript` (`67` vars, `39` `PACK`s), treaty `StopCombatAlarm` | `FO3_EvanKing`: Rescuing Ian West directly from Meresti completes `MS09` | `FO3S-08` | No |
| `MS10` (`0x02A274`) | Side | `8` / `8` | `MS10QuestScript` (`MenuMode`+`GameMode`), atomic `IMOD` clear | `FO3_TreefatherBirch`: Enter Oasis caves via looted key/lockpick and resolve heart | `FO3S-09` | No |
| `MS11` (`0x014E9E`) | Side | `10` / `12` | `MS11Script` (`CF-1` Karma `+/-1000`), `Explosives 25` check | `FO3_LucasSimms`: Harden Simms issues house key if Simms dies; Tenpenny branch stays open | `FO3S-10` | **FRAGILE** |

### 1.4 Fallout: New Vegas Census (`20` Quests from `#829` + `VMS38` Pimp-Boy 3 Billion)

| Quest (`FormID`) | Track | `INDX` / `QOBJ` | Key Script, Flag & Item Dependencies | `W7` Open Mode Essential-NPC Fallback | Bug Ledger | Fragile? |
|---|---|---:|---|---|---|---|
| `VCG01` (`0x104C1C`) | Main | `38` / `4` | `VCG01SCRIPT` (`MenuMode`+`GameMode`), `CF-3` Hardcore, `CF-6` SPECIAL/Tags/Traits | `FNV_DocMitchell`: Exiting front door runs `CF-6`/`CF-3` confirmation automatically | `FNVM-01` | No |
| `VCG02` (`0x10A214`) | Main | `10` / `9` | `VCG02SCRIPT`, `CF-5` campfire recipe, `Ref.IsDead()` pre-cleared wells | `FNV_SunnySmiles`: Tutorial skips cleanly; Goodsprings exit rebuild still triggers | `FNVM-02` | No |
| `VMQ01` (`0x0842DD`) | Main | `6` / `12` | `VMQ01QuestScript` (`0` owned `INFO`, `26` cross-`INFO`), Strip breadcrumb catch-up | `FNV_Victor`: Transfers to new Securitron shell or player walks directly to Tops | `FNVM-03` | No |
| `VMQTops` (`0x11345D`) | Main | `16` / `13` | `VMQTopsScript` (`350` owned + `94` cross `INFO`), weapon-stash manifest checksum | `FNV_Benny`: Killing Benny drops Platinum Chip and opens Lucky 38 / Yes Man / Fort | `FNVM-04` | **FRAGILE** |
| `VMQHouse1` (`0x147885`) | Main | `8` / `9` | `VMQHouse1script` (`0` owned `INFO`, `43` cross-`INFO`), pre-upgraded bunker check | `FNV_MrHouse`: Killing House fails `VMQHouse1` cleanly and opens `VMQYesMan01`/NCR/Legion | `FNVM-05` | No |
| `VMQYesMan01` (`0x157321`) | Main | `5` / `10` | `VMQYesMan01script` (`0` `Begin` blocks, `56` cross-`INFO`), Securitron shell respawn | `FNV_YesMan`: Canonical W7 failsafe uploads to a new Securitron shell outside Lucky 38 | `FNVM-06` | No |
| `VMQ02` (`0x129D14`) | Main | `12` / `35` | `VMQ02QuestScript` (`35` objectives, `123` cross-`INFO`), `CF-1` `>=16` isolated `REPU` slots | `FNV_Caesar`: Killing Caesar transfers Legion to Lanius while Yes Man/House/NCR stay open | `FNVM-07` | **FRAGILE** |
| `VMQ03a` (`0x131F08`) | Main | `6` / `8` | `VMQ03aQuestScript` (`47` `PACK`s), `CF-1` disguise & `SendAssaultAlarm` exemptions | `FNV_PresidentKimball`: Kimball's death resolves assassination-failed state without softlock | `FNVM-08` | **FRAGILE** |
| `VMQ04` (`0x1344E8`) | Main | `3` / `2` | `VMQ04QuestScript` (pre-placed sentry refs replacing `PlaceAtMe`), `CF-1` disguise | None (object/terminal power routing) | `FNVM-09` | No |
| `VMQ05` (`0x136166`) | Main | `9` / `18` | `VMQ05QuestScript` (`69` cross-`INFO`), `VMQNCRFailSCRIPT`, pre-completed faction checks | `FNV_ColonelMoore`: Killing Moore trips `VMQNCRFail` cleanly; Yes Man/House/Legion remain open | `FNVM-10` | No |
| `VMS16` (`0x104EAE`) | Side | `10` / `10` | `VMS16QuestScript` (`84` cross-`INFO`), once-only Chet `Barter 25` latch | `FNV_Ringo`: Killing Ringo fails `VMS16` cleanly and opens `VMS16b` without Chet loop | `FNVS-01` | No |
| `VMS16b` (`0x15EC5B`) | Side | `6` / `8` | `VMS16bQuestScript` (`40` cross-`INFO`), atomic mutual exclusion with `VMS16` | `FNV_JoeCobb`: Killing Cobb fails `VMS16b` atomically and keeps `VMS16` playable | `FNVS-02` | No |
| `VMS02` (`0x08D0E3`) | Side | `13` / `10` | `VMS02QuestScript` (`23` vars, `11` skill checks), `CF-1` disguise vs hostility | `FNV_Eddie`: If Eddie dies after raid discovery, Sergeant Lee completes NCR assault branch | `FNVS-03` | No |
| `VMS33` (`0x1271EA`) | Side | `7` / `4` | `VMS33QuestScript`, `Vulpes` `OnDeath` Strip-envoy replacement (`Alerio`) | `FNV_VulpesInculta`: Sniping Vulpes sets `Alerio` fallback and still permits Outpost report | `FNVS-04` | No |
| `VMS44` (`0x14050D`) | Side | `10` / `5` | `VMS44QuestScript`, `CF-7` Searchlight rads, Logan carries station keys from spawn | `FNV_Logan`: Loot Fire & Police Station keys from Logan's body to finish solo | `FNVS-05` | No |
| `VMS53` (`0x151403`) | Side | `1` / `4` | `VMS53SCRIPT` (`0` `Begin` blocks, `7` vars), idempotent note check, `CF-2` Boone unlock | `FNV_Boone`: If Boone dies, `VMS53` closes cleanly; Manny's terminal supplies `VMQ01` clue | `FNVS-06` | **FRAGILE** |
| `VMS01` (`0x080664`) | Side | `10` / `21` | `REPCONGhoulQuestScript` (`189` cross-`INFO`), `CF-7` rads, `30s` exodus `MoveTo` | `FNV_JasonBright`: If Bright's group dies, Manny's terminal/note advances `VMQ01` | `FNVS-07` | **FRAGILE** |
| `VMS03` (`0x0E282D`) | Side | `3` / `10` | `VMS03QuestSCRIPT` (`49` vars, `49` faction checks), once-only Ignacio latch, `24h` cooldown | `FNV_IgnacioRivas`: Solar tower mainframe completes `VMS03` directly even if NPCs die | `FNVS-08` | No |
| `VMS20` (`0x10E908`) | Side | `6` / `9` | `VMS20QuestScript` (`51` vars, `55` cross-`INFO`), temporary NCR/Khan `SetAlly` | `FNV_LtMonroe`: Freeing hostages or looting Jessup's lighter/note advances `VMQ01` | `FNVS-09` | No |
| `VMS29` (`0x11F95B`) | Side | `12` / `17` | `VMS29Script` (`67` `INFO` result scripts), parley `IgnoreCombat` isolation | `FNV_TheKing`: Pacer or direct NCR Embassy report closes tensions without locking `Pimp-Boy` | `FNVS-10` | **FRAGILE** |
| `VMS38` (`FNV:VMS38`) | Reachability / Feel | `5` modeled | `FO4SF_FNV_MickOmertaRestored`, `FO4SF_PipboyStyleUnlockedMask`, `3`-route Pimp-Boy 3 Billion | `FNV_Cachino` / `FNV_Mick`: Route 2 (Barter/Repair/Caps or King's favor) and Route 3 (Gomorrah safe casing + workbench) preserve Pimp-Boy 3 Billion even if Cachino or Mick dies | `RF-FNV-001` | **FRAGILE** |

### 1.5 Generated `FRAGILE` List (`18` Quests)

Generated deterministically by `python scripts/testing/check_quest_fragility.py --open-mode`:

| # | Game | Quest (`FormID`) | Cut Edge / Single-Sequence Risk | Mitigation / Port Fix |
|---:|---|---|---|---|
| 1 | `FO4` | `FO4SF_NewGame` (`0x000800`) | `20->30` (`pipboy_pickup_and_console_activate`): `R10` owner exception — Story gear door opens only via `0x00080F` + `0x000819`; blocked in 2d by break `U1` | Fix `0x00080F` activator hitbox/base + retain test-mode console fallback |
| 2 | `FO4` | `FO4SF_Min00` (`0x000800`) | `20->30` (`all_concord_raiders_dead_or_wfc01_cleared`) + Preston turn-in | `WFC-01` rescue + `60s` absent/stuck write-off; wire W7 corpse-note fallback for Open Mode |
| 3 | `FO4` | `MQ106` (`FO4:MQ106`) | `20->30`: Fort Hagen two-shaft elevator traversal (`FO4SF_FortHagenQuest`) + Kellogg brain loot gate | Bound elevator call/panel/roof-gate re-binds on reload (`FO4SF_FortHagenQuest.psc`) |
| 4 | `FO4` | `MQ204` (`FO4:MQ204`) | `20->30`: Courser chip decode + workshop Signal Interceptor power/wiring assembly | Allow self-decode terminal + validate `4`-piece power link via workshop script |
| 5 | `FO4` | `MQ206` (`FO4:MQ206`) | `20->30`: Three-faction crossfire (Institute/BoS/Railroad) synth disposition pivot | Guard neutral faction combat alarms during Bunker Hill cell entry |
| 6 | `FO3` | `CG03` (`0x014E85`) | `20->30`: Hallway fight `StopCombat` -> seated exam -> `3` tag skills (`FO3M-03`) | `StopCombatAlarm()` + direct instructor bypass into `CF-6` tag selector |
| 7 | `FO3` | `MQ04` (`0x014E8A`) | `20->30`: Tranquility Lane inventory stash/restore + failsafe/pod exit (`FO3M-08`) | Persistent stash container with entry/exit item checksum + `WaitFor3DLoad()` |
| 8 | `FO3` | `MQ05` (`0x014E8B`) | `20->30`: `58`-script / `61`-package Taft Tunnels escort & `SetRestrained` leak (`FO3M-09`) | Per-door alias catch-up `MoveTo` + unconditional `SetRestrained(False)` |
| 9 | `FO3` | `MS01` (`0x014E94`) | `20->30`: Big Town captive travel desync + exterior defense wave spawn (`FO3S-01`) | `OnLocationChange` wave trigger + deterministic `SetGhost(False)` at stage `200` |
| 10 | `FO3` | `MS03` (`0x014E96`) | `20->30`: `34`-objective / `255`-`INFO` chapter chain + post-`MS11` relocation (`FO3S-03`) | Latch `CF-7` rad/limb bonuses + preserve chapter state across Megaton/Underworld |
| 11 | `FO3` | `MS11` (`0x014E9E`) | `20->30`: Saloon arrest timing race + Sheriff heir house-key transfer (`FO3S-10`) | Guard saloon scene timing + deterministic Harden Simms turn-in fallback |
| 12 | `FNV` | `VMQTops` (`0x11345D`) | `20->30`: Casino holdout weapon confiscation + Benny suite/Fort transition (`FNVM-04`) | Per-actor persistent stash containers + exit manifest checksum |
| 13 | `FNV` | `VMQ02` (`0x129D14`) | `20->30`: `35`-objective minor-faction matrix + Strip infamy reset (`FNVM-07`) | Expand `CF-1` `REPU` to `>=16` isolated slots (`GAP-J3-02`) + pre-cleared faction checks |
| 14 | `FNV` | `VMQ03a` (`0x131F08`) | `20->30`: `47`-package Hoover Dam timed defense + disguise/alarm (`FNVM-08`) | Crime/alarm exemptions when neutralizing confirmed infiltrators |
| 15 | `FNV` | `VMS53` (`0x151403`) | `10->100`: `1`-stage `0`-block night-shift beret signal + pre-looted safe (`FNVS-06`) | Idempotent `GetItemCount` evidence check + `12.0 m` exterior trigger zone |
| 16 | `FNV` | `VMS01` (`0x080664`) | `20->30`: `189` cross-`INFO` REPCONN Nightkin hostility + launch deck (`FNVS-07`) | Gate launch console on `ExodusReady` + `30s` catch-up `MoveTo` |
| 17 | `FNV` | `VMS29` (`0x11F95B`) | `20->30`: Freeside parley crossfire coupled to `VMQNCRFailSCRIPT` (`FNVS-10`) | Isolate parley actors (`IgnoreCombat`) from ambient thug aggro |
| 18 | `FNV` | `VMS38` (`FNV:VMS38`) | `10->20`: Gomorrah investigation chain; vanilla Pimp-Boy 3 Billion sat behind `1` unmarked sequence (`RF-FNV-001`) | Upgraded to `3` independent unlock routes in `docs/testing/reachability-fixes.md` |

---

## 2. Tier 2 — Break-It Cases (`R11` & `P3` Self-Contained Batch Recipes)

### 2.1 Candidate 2d / `W1` Load-Order Prefix Table (`<XX>` Substitution — `player` vs `test`)

Under the `W1` safe defaults (`FO4SFRouteLoot.esm` OFF by default in both profiles, `FO4SFBridge.esm` OFF by default), `--profile player` ships **`13` Track-1 plugins** (`FO4SFListDialogue.esm` and Track-2 experimental core slices omitted from `player`) and `--profile test` ships **`22` plugins** (`23` only when `--with-route-loot` is explicitly opted in). Because the first `8` bundle plugins (`FO4ActorRaider.esm`..`FO4SFNewGame.esm`) stay in identical order across both the 21 Nov `2d` run and the rebuilt `W1`/`W4` `player` (`13`) & `test` (`22`) bundles (with `FO4SFBridge.esm` OFF), **`04` (`FO4TerrainCore.esm`), `06` (`FO4SFCoreValues.esm`), `09` (`FO4SFMission.esm`), and `0A` (`FO4SFNewGame.esm`) stay 100% unchanged** (confirmed in Claude's 21 Nov 2d session where `FO4SF_NewGame` was `0A000800`, not `0B000800`):

| Plugin | Local IDs Used Below | `W1`/`W4` `player` (`13` Plugins, `Bridge` OFF) | `W1`/`W4` `test` (`22` Plugins, `Bridge`/`RouteLoot` OFF) | Index if `FO4SFCoreValues.esm = 0x07` (`Bridge` ON) |
|---|---|---:|---:|---:|
| `FO4TerrainCore.esm` | `0x005C50` (Sanctuary Workbench) | `04` (`04005C50`) | `04` (`04005C50`) | `05` (`05005C50`) |
| `FO4SFCoreValues.esm` | `0x000860` (`TestMode`), `0x000865` (`PipboyAcquired`), `0x000870` (`GameMode`), `0x000871` (`SurvivalStart`) | `06` (`06000865`) | `06` (`06000865`) | `07` (`07000865`) |
| `FO4SFMission.esm` | `0x000800` (`Min00`), `0x000802` (`Preston`), `0x000803..` (`Raiders`), `0x000811` (`Codsworth`), `0x000814` (`Keeper`), `0x000816` (`Codsworth01`), `0x000817` (`Sanctuary01`) | `09` (`09000800`) | `09` (`09000800`) | `0A` (`0A000800`) |
| `FO4SFNewGame.esm` | `0x000800` (`NewGame`), `0x00080D` (`PipboyWrist`), `0x00080F` (`PipboyCorpseRef`), `0x000819` (`GearDoorConsoleRef`) | `0A` (`0A000800`) | `0A` (`0A000800`) | `0B` (`0B000800`) |
| `FO4SFListDialogue.esm` | `0x000810` (`ListDialogue`) | `— (test profile only)` | `10` (`10000810`; `11` only with `--with-route-loot`) | `12` (`12000810` w/ `RouteLoot`) |

**How to verify `<XX>` before running any recipe (`P3` — zero `M`, `N`, or `V` typed):**
1. Read `FO4SFPipboyMenu.log`: `step=core_value_resolve name=FO4SF_PipboyAcquired source=FO4SFCoreValues.esm:000865 found=1 form=0x<CV>000865` -> `FO4SFMission.esm = <CV>+3`, `FO4SFNewGame.esm = <CV>+4`, `FO4TerrainCore.esm = <CV>-2`.
2. Or type in Console (zero `M`, `N`, or `V`):

```console
help "Health Cap" 4
```

**`P3` Batch Hygiene Rules Enforced Below:**
- Every interactive ```` ```console ```` line and every batch filename (`q1a`..`q5f`) contains **zero `m`, `M`, `n`, `N`, `v`, or `V` characters**.
- Every ```` ```bat ```` file lives next to `Starfield.exe` as `<starfield-dir>/<bat-id>.txt`, uses **pure valid Starfield console commands** (`setstage`, `getstage`, `sqs`, `sqv`, `prid`, `kill`, `set ... to ...`, `player.moveto`, `player.additem`, `startquest`, `stopquest`, `coc`), and contains **zero uppercase or standalone `M`, `N`, or `V` hotkey tokens in `;` remarks**.

---

### 2.2 Staged Quest 1 — `FO4SF_NewGame` (*Out of Time*, `FO4SFNewGame.esm:0x000800`, 2d: `0A000800`)

**Prerequisites:** `W1`/`W4` `--profile player` bundle installed (`13` Track-1 plugins; `FO4SFRouteLoot.esm` and `FO4SFBridge.esm` OFF; `04`/`06`/`09`/`0A` indices unchanged from the 21 Nov 2d run), New Game -> `Story` -> `Fallout 4: Commonwealth` -> `Survival: No` (or `Yes` for Open Mode) -> `Quick start`. Log file: `fo4sf_newgame.0.log`.

#### Case 1A (`q1a`) — Kill / Lose Quest Giver Early + `W7` Open Mode / `U1` Pickup-Gate Fallback
- **Stages to Force:** Hold at stage `20` inside Vault 111 (`0A000800`). Verify `NoPipboyMsg` (`0x000817`) when activating console before pickup; if `U1` blocks `0x00080F` activation, set `FO4SF_PipboyAcquired` (`06000865`) to `1` and grant `FO4SF_PipboyWrist` (`0A00080D`) via batch.
- **REAL In-World Trigger:** Walk to gear-door console (`0x000819`) and press `E` before pickup (must refuse), then after pickup/fallback press `E` on `0x000819` to open `VltGearDoor01`.

```console
getstage 0A000800
bat q1a
```

```bat
; q1a: stage 20 pickup state check + fallback equip (06=core, 0A=start)
getstage 0A000800
getglobalvalue 06000865
set 06000865 to 1
player.additem 0A00080D 1
```

```log
FO4SF_NEWGAME rt=<rt> console refused: no pipboy
FO4SF_NEWGAME rt=<rt> cog door console activated ref=<ref> before=<b0> after=<b1>
FO4SF_NEWGAME rt=<rt> stage 30 by=vault_console
```

#### Case 1B (`q1b`) — Objectives Out of Order
- **Stages to Force:** Force stage `20`, skip Pip-Boy and attempt console (`0x000819`), then force stage `30` and step onto lift (`0x000801`) choosing `Continue` before confirming `40`-point S.P.E.C.I.A.L.
- **REAL In-World Trigger:** Press `E` on console (`0x000819`) before Pip-Boy, then walk onto lift platform (`RespecMoveMarker`) and choose `Continue` before S.P.E.C.I.A.L., then confirm `40`-pt S.P.E.C.I.A.L. and press `Continue`.

```console
bat q1b
```

```bat
; q1b: verify out-of-order console & lift special gate
set 06000865 to 0
setstage 0A000800 20
getstage 0A000800
```

```log
FO4SF_NEWGAME rt=<rt> console refused: no pipboy
FO4SF_NEWGAME rt=<rt> elevator continue refused: special unconfirmed
FO4SF_NEWGAME rt=<rt> special set S=<s> P=<p> E=<e> C=<c> I=<i> A=<a> L=<l> sum=40 source=Lift
```

#### Case 1C (`q1c`) — Leave Mid-Stage & Return
- **Stages to Force:** None (natural stage `30` -> `40` -> `200`).
- **REAL In-World Trigger:** At stage `30`, step onto lift pad, pick `Stay` (button `2`), walk back into cryo corridor `> 10 m`, return to lift pad and ride to surface; then at stage `200`, step onto surface lift pad (`0x00080B`) -> ride down -> ride back up.

```console
bat q1c
```

```bat
; q1c: inspect stage before and after stay / surface lift round-trip
getstage 0A000800
sqs 0A000800
```

```log
FO4SF_NEWGAME rt=<rt> elevator stay
FO4SF_NEWGAME rt=<rt> landed z=<z> confirmed=True fallback=false world=<world>
FO4SF_NEWGAME rt=<rt> stage 200 by=Trigger
FO4SF_NEWGAME rt=<rt> return lift prompt button=0
```

#### Case 1D (`q1d`) — Save & Reload at Every Stage (`10`, `20`, `30`, `40`, `200`)
- **Stages to Force:** Save to throwaway slot at each stage (`10`, `20`, `30`, `40`, `200`), `Quit to Desktop`, relaunch and load each save.
- **REAL In-World Trigger:** After each reload, complete the next physical vault step (looks/pickup/console/lift/landing) and verify `Timer 1` resumes logging every `5 s` without stalling.

```console
bat q1d
```

```bat
; q1d: verify stage + build version global after quit-to-desktop reload
getstage 0A000800
getglobalvalue 0A000805
```

```log
FO4SF_NEWGAME rt=<rt> status stage=<st> pos=<x> <y> <z> cell=<cell> world=<world>
FO4SF_NEWGAME rt=<rt> exit reload recovered stage=<st> failures=<n>
```

#### Case 1E (`q1e`) — Fast Travel / Cell Jump Mid-Quest
- **Stages to Force:** At stage `20` inside `FO4Port_Vault111Cryo`, jump to exterior marker, then jump back into `FO4Port_Vault111Cryo`.
- **REAL In-World Trigger:** Walk to console (`0x000819`) after returning to `FO4Port_Vault111Cryo`, press `E`, and ride lift to surface.

```console
bat q1e
```

```bat
; q1e: jump out at stage 20 then re-enter cryo cell
getstage 0A000800
coc FO4Port_Vault111Cryo
getstage 0A000800
```

```log
FO4SF_NEWGAME rt=<rt> stage 30 by=vault_console
FO4SF_NEWGAME rt=<rt> stage 40 by=Trigger
FO4SF_NEWGAME rt=<rt> stage 200 by=Trigger
```

#### Case 1F (`q1f`) — Arrive Before Quest Starts (Existing Save / NG+ Guard)
- **Stages to Force:** Load an existing post-intro save (`GameDaysPassed >= 1.0` or player `level > 1`) with `FO4SFNewGame.esm` active.
- **REAL In-World Trigger:** Load save and walk `10 s`; verify `FO4SF_NewGame` does not hijack the existing character (stays `0` or stands down at stage `1`).

```console
bat q1f
```

```bat
; q1f: verify existing-save guard does not hijack stage
getstage 0A000800
sqs 0A000800
```

```log
FO4SF_NEWGAME rt=<rt> not a new game: days=<d> level=<lvl> loading=<bool>: standing down
```

---

### 2.3 Staged Quest 2 — `FO4SF_Codsworth01` (*Sanctuary Talk*, `FO4SFMission.esm:0x000816`, 2d: `09000816`)

**Prerequisites:** `FO4SF_NewGame` at stage `200` (Story mode, `FO4SF_GameMode == 1`, starts `FO4SF_Codsworth01` automatically at stage `10`). Log file: `fo4sf_mission.0.log`.

#### Case 2A (`q2a`) — Kill / Lose Quest Giver Early + **`W7` Open Mode Essential NPC Dead**
- **Stages to Force:** At `FO4SF_Codsworth01` stage `10`, enable Open Mode survival flag (`06000871 = 1`) and kill/disable `FO4_Codsworth` (`09000811`).
- **REAL In-World Trigger:** Walk down the road from Sanctuary to within `150 m` of Concord Museum door; verify `FO4SF_Min00` auto-starts at stage `10` and `FO4SF_Codsworth01` clears objective `10` with zero softlock.

```console
bat q2a
```

```bat
; q2a: open-mode essential actor dead check on codsworth (09000811)
set 06000871 to 1
prid 09000811
kill
getstage 09000816
```

```log
FO4SF_MISSION rt=<rt> min00 given by=concord
FO4SF_MISSION rt=<rt> codsworth01 objective 10 cleared by=concord
```

#### Case 2B (`q2b`) — Objectives Out of Order
- **Stages to Force:** At stage `10`, skip Choices `1–3` (`20`, `30`, `40`) and pick Choice `4` directly inside `FO4SF_Codsworth01_Scene` (`0x000940`).
- **REAL In-World Trigger:** Press `E` on `FO4_Codsworth` (`09000811`) in Sanctuary and select Choice `4` immediately.

```console
bat q2b
```

```bat
; q2b: confirm stage 10 before direct choice-4 conversation
getstage 09000816
getstage 09000800
```

```log
FO4SF_MISSION rt=<rt> codsworth01 stage 100 by=info
FO4SF_MISSION rt=<rt> codsworth talk end -> min00 stage 10
FO4SF_MISSION rt=<rt> codsworth01 complete choices=1 concord_pointed=true
```

#### Case 2C (`q2c`) — Leave Mid-Stage & Return
- **Stages to Force:** None (natural dialogue interruption after stage `20`).
- **REAL In-World Trigger:** Press `E` on Codsworth, pick Choice `1` (`stage 20`), exit conversation, walk `> 400 m` south past Red Rocket, walk back to Sanctuary, press `E` on Codsworth again and pick Choice `4`.

```console
bat q2c
```

```bat
; q2c: check stage after walking away and returning
getstage 09000816
sqs 09000816
```

```log
FO4SF_MISSION rt=<rt> codsworth01 choice=1 choices=1
FO4SF_MISSION rt=<rt> codsworth01 stage 100 by=info
FO4SF_MISSION rt=<rt> codsworth01 complete choices=<n> concord_pointed=true
```

#### Case 2D (`q2d`) — Save & Reload at Every Stage (`10`, `20`, `30`, `40`, `100`)
- **Stages to Force:** Save after each dialogue choice (`10`, `20`, `30`, `40`), `Quit to Desktop`, reload, and finish Choice `4`.
- **REAL In-World Trigger:** Re-open dialogue (`E` on `09000811`) after each reload and advance to the next choice.

```console
bat q2d
```

```bat
; q2d: verify stage persistence after quit-to-desktop reload
getstage 09000816
```

```log
FO4SF_MISSION rt=<rt> codsworth01 reload stage=<st> choices=<n>
FO4SF_MISSION rt=<rt> codsworth01 complete choices=<n> concord_pointed=true
```

#### Case 2E (`q2e`) — Fast Travel Mid-Quest
- **Stages to Force:** At stage `20`, fast travel via Pip-Boy MAP (`M`) to Vault 111 marker and walk/fast-travel back to Sanctuary.
- **REAL In-World Trigger:** Confirm `FO4SF_CodsworthKeeper` (`09000814`) holds Codsworth within `25 m` of Sanctuary home, press `E`, and pick Choice `4`.

```console
bat q2e
```

```bat
; q2e: verify keeper quest running and stage after travel
getstage 09000816
sqs 09000814
```

```log
FO4SF_MISSION rt=<rt> keeper status codsworth d=<d> off=<off> state=<st> moves=<m> held=<h> holds=<hc> at <x> <y> <z> disabled=False dead=False fails=<f> player=<px> <py> <pz> interior=False
FO4SF_MISSION rt=<rt> codsworth01 complete choices=<n> concord_pointed=true
```

#### Case 2F (`q2f`) — Arrive Before Quest Starts (Warfare Mode Gate)
- **Stages to Force:** Start a Warfare New Game (`FO4SF_GameMode == 2`) deploying to Sanctuary Hills (`minutemen_sanctuary`).
- **REAL In-World Trigger:** Stand beside Codsworth in Sanctuary during Warfare mode; confirm `FO4SF_Codsworth01` gates itself off cleanly without showing Story objective `10`.

```console
bat q2f
```

```bat
; q2f: verify story-only gate blocks quest when mode=2
getglobalvalue 06000870
getstage 09000816
```

```log
FO4SF_MISSION rt=<rt> mission gate mode=2 started=false quest=codsworth01
```

---

### 2.4 Staged Quest 3 — `FO4SF_Min00` (*When Freedom Calls*, `FO4SFMission.esm:0x000800`, 2d: `09000800`)

**Prerequisites:** `FO4SF_NewGame` stage `200` (Story mode). Log file: `fo4sf_mission.0.log`.

#### Case 3A (`q3a`) — Kill / Lose Quest Giver Early + **`W7` Open Mode Essential NPC Dead**
- **Stages to Force:**
  - *Normal mode friendly-fire guard (`WFC-03`):* At stage `20`, fire two stray rounds into `FO4_PrestonGarvey` (`09000802`) before killing the last raider -> Preston must stay non-hostile (`FO4SF_MinutemenFaction` Ally + `IgnoreFriendlyHits`).
  - *`W7` Open Mode check:* Set `FO4SF_SurvivalStart` (`06000871`) to `1`, kill `09000802` at stage `10`/`30` -> verifies current cut-down gap (`FoundPreston` checks `!Preston.IsDead()`, so W7 corpse-note/terminal fallback must land before Open Mode ships) and confirms player can proceed to Diamond City (`MQ103`) without Minutemen.
- **REAL In-World Trigger:** Clear final Concord raider, then walk within `3.0 m` / press `E` on Preston (`09000802`) in Normal mode (or loot corpse dispatch note once W7 Open Mode fallback is wired).

```console
bat q3a
```

```bat
; q3a: friendly-fire check (normal) / open-mode preston kill check (09000802)
getstage 09000800
set 06000871 to 1
prid 09000802
kill
```

```log
FO4SF_MISSION rt=<rt> stage 30 by=Trigger
FO4SF_MISSION rt=<rt> stage 40 by=info
FO4SF_MISSION rt=<rt> reward credits=100
FO4SF_MISSION rt=<rt> complete stage=200
```

#### Case 3B (`q3b`) — Objectives Out of Order (Pre-Cleared Raiders)
- **Stages to Force:** Start from Vault 111 surface (`FO4SF_Min00` stage `0`, bypassing Codsworth), kill Concord raiders (`09000803..`) from long range before approaching Preston (`> 20 m`).
- **REAL In-World Trigger:** Eliminate every Concord raider first, then walk to Preston at the Museum door (`09000802`) and press `E` to run `FO4SF_Min00_PrestonScene` (`0x000900`).

```console
bat q3b
```

```bat
; q3b: verify stage catch-up 0->10->20->30 when raiders die early
getstage 09000800
sqs 09000800
```

```log
FO4SF_MISSION rt=<rt> min00 given by=concord
FO4SF_MISSION rt=<rt> stage 10 by=Trigger
FO4SF_MISSION rt=<rt> stage 20 by=Trigger
FO4SF_MISSION rt=<rt> stage 30 by=Trigger
FO4SF_MISSION rt=<rt> preston talk end info=0x092A -> stage 40
FO4SF_MISSION rt=<rt> complete stage=200
```

#### Case 3C (`q3c`) — Leave Mid-Stage & Return (`WFC-01` Straggler / Drift Guard)
- **Stages to Force:** None (natural stage `20` combat).
- **REAL In-World Trigger:** Trigger stage `20` in Concord, kite or leave one raider alive, walk `> 400 m` back toward Sanctuary, then return to Concord Museum door and clear the remaining raider (or wait `60 s` within `100 m` of door if unloaded to verify `WFC-01` write-off).

```console
bat q3c
```

```bat
; q3c: verify stage 20 status after leaving concord and returning
getstage 09000800
sqs 09000800
```

```log
FO4SF_MISSION rt=<rt> status stage=20 dead=<d>/<tot> nearest_raider=<r> preston=<dp> preston_off=<off> held=<h> pos=<x> <y> <z>
FO4SF_MISSION rt=<rt> stage 30 by=Trigger
FO4SF_MISSION rt=<rt> complete stage=200
```

#### Case 3D (`q3d`) — Save & Reload at Every Stage (`10`, `20`, `30`, `40`, `200`)
- **Stages to Force:** Save to throwaway slot at stages `10`, `20` (mid-fight with `>=1` raider alive), `30` (before talking to Preston), and `200`; `Quit to Desktop` and reload each save.
- **REAL In-World Trigger:** Continue the Concord battle / Preston conversation (`E` on `09000802`) after each reload; at stage `200`, confirm `FO4SF_CodsworthKeeper` holds Preston at `preston_off <= 25.0`.

```console
bat q3d
```

```bat
; q3d: check mission and keeper stages after quit-to-desktop reload
getstage 09000800
getstage 09000814
```

```log
FO4SF_MISSION rt=<rt> reload mission stage=<st> relocate_fails=0
FO4SF_MISSION rt=<rt> complete stage=200
FO4SF_MISSION rt=<rt> sanctuary01 start_requested ok=True
```

#### Case 3E (`q3e`) — Fast Travel Mid-Quest
- **Stages to Force:** At stage `20` and again at stage `30`, fast travel to Sanctuary via Pip-Boy MAP (`M`), then fast travel / walk back to Concord.
- **REAL In-World Trigger:** Confirm remaining raiders re-engage at stage `20` and pressing `E` on Preston at stage `30` launches `FO4SF_Min00_PrestonScene` (`0x000900`) cleanly.

```console
bat q3e
```

```bat
; q3e: inspect stage 20/30 state after fast travel round-trip
getstage 09000800
sqs 09000800
```

```log
FO4SF_MISSION rt=<rt> preston talk scene triggered stage=30
FO4SF_MISSION rt=<rt> preston talk end info=0x092A -> stage 40
FO4SF_MISSION rt=<rt> complete stage=200
```

#### Case 3F (`q3f`) — Arrive Before Quest Starts (Skip Sanctuary Straight to Concord)
- **Stages to Force:** Fresh Story save at `FO4SF_NewGame` stage `200`; do NOT enter Sanctuary Hills (`FO4SF_Codsworth01` stays at stage `10`, `FO4SF_Min00` stays at stage `0`).
- **REAL In-World Trigger:** Walk directly south-southeast from Vault 111 to within `150 m` of Concord Museum door, fight raiders, and talk to Preston (`OPEN-06` regression).

```console
bat q3f
```

```bat
; q3f: confirm min00 starts at stage 0 before concord arrival
getstage 09000800
getstage 09000816
```

```log
FO4SF_MISSION rt=<rt> min00 given by=concord
FO4SF_MISSION rt=<rt> codsworth01 objective 10 cleared by=concord
FO4SF_MISSION rt=<rt> complete stage=200
```

---

### 2.5 Staged Quest 4 — `FO4SF_Sanctuary01` (*Sanctuary Workbench*, `FO4SFMission.esm:0x000817`, 2d: `09000817`)

**Prerequisites:** `FO4SF_Min00` stage `200` (starts `FO4SF_Sanctuary01` automatically at stage `10`). Log file: `fo4sf_mission.0.log`.

#### Case 4A (`q4a`) — Kill / Lose Quest Giver Early + `W7` Open Mode / Unbound Bench Fallback
- **Stages to Force:** Force `FO4SF_Sanctuary01` stage `10` with `FO4SF_TestModeEnabled` (`06000860 = 1`) and disable `04005C50` (simulating missing/unbound bench ref in Open Mode or world-load failure).
- **REAL In-World Trigger:** Stand within `3.0 m` of the Sanctuary workbench spot (`-2329.250, -1420.193, 112.086`) for `8 s` (test mode) / `120 s` (normal) and verify the proximity fallback completes stage `100` without stranding the player (`R10`).

```console
bat q4a
```

```bat
; q4a: test unbound-bench fallback with test-mode short timer (8 s)
set 06000860 to 1
startquest 09000817
setstage 09000817 10
getstage 09000817
```

```log
FO4SF_MISSION rt=<rt> sanctuary01 init stage=10 bench_ref=0x005C50
FO4SF_MISSION rt=<rt> sanctuary01 fallback unbound_bench near_sec=<sec>
FO4SF_MISSION rt=<rt> sanctuary01 stage 100 by=fallback
```

#### Case 4B (`q4b`) — Objectives Out of Order (Activate Bench Before `FO4SF_Min00` Stage `200`)
- **Stages to Force:** Before completing `FO4SF_Min00`, walk to Sanctuary workbench (`04005C50`) and press `E`; then force/play `FO4SF_Min00` to stage `200` and activate the workbench again.
- **REAL In-World Trigger:** Press `E` on `04005C50` while `FO4SF_Sanctuary01` is stage `0` (must not break binding), then after `FO4SF_Sanctuary01` starts at stage `10`, press `E` on `04005C50` again.

```console
bat q4b
```

```bat
; q4b: check sanctuary01 is stage 0 prior to min00 stage 200
getstage 09000800
getstage 09000817
```

```log
FO4SF_MISSION rt=<rt> sanctuary01 bench_bound ref=<ref> loaded=True
FO4SF_MISSION rt=<rt> min01 bench activated -> stage 100
FO4SF_MISSION rt=<rt> sanctuary01 bench_activated=true ref=<ref> complete=true
```

#### Case 4C (`q4c`) — Leave Mid-Stage & Return
- **Stages to Force:** None (`FO4SF_Sanctuary01` at stage `10` after `FO4SF_Min00` stage `200`).
- **REAL In-World Trigger:** Walk `> 350 m` away from Sanctuary so the workbench cell unloads, return on foot to `04005C50`, and press `E`.

```console
bat q4c
```

```bat
; q4c: verify stage 10 remains active across cell unload and return
getstage 09000817
sqs 09000817
```

```log
FO4SF_MISSION rt=<rt> sanctuary01 bench_bound ref=<ref> loaded=True
FO4SF_MISSION rt=<rt> min01 bench activated -> stage 100
```

#### Case 4D (`q4d`) — Save & Reload at Every Stage (`10`, `100`)
- **Stages to Force:** Save at stage `10` before activating the workbench, `Quit to Desktop`, reload, activate `04005C50`, save at stage `100`, reload again and confirm no duplicate trigger.
- **REAL In-World Trigger:** Press `E` on `04005C50` after the stage-`10` reload.

```console
bat q4d
```

```bat
; q4d: verify reload re-binds workbench at stage 10 and stays closed at 100
getstage 09000817
```

```log
FO4SF_MISSION rt=<rt> sanctuary01 reload stage=10 complete=False
FO4SF_MISSION rt=<rt> min01 bench activated -> stage 100
FO4SF_MISSION rt=<rt> sanctuary01 reload stage=100 complete=True
```

#### Case 4E (`q4e`) — Fast Travel Mid-Quest
- **Stages to Force:** At stage `10` in Concord (right after `FO4SF_Min00` stage `200`), fast travel straight to Sanctuary via Pip-Boy MAP (`M`).
- **REAL In-World Trigger:** Walk to `04005C50` after fast-travel arrival and press `E`; confirm `XMarker` guide cleans up and stage `100` logs cleanly.

```console
bat q4e
```

```bat
; q4e: verify stage 10 before and after map fast travel to sanctuary
getstage 09000817
```

```log
FO4SF_MISSION rt=<rt> sanctuary01 bench_bound ref=<ref> loaded=True
FO4SF_MISSION rt=<rt> min01 bench activated -> stage 100
```

#### Case 4F (`q4f`) — Arrive Before Quest Starts (Warfare Mode Gate)
- **Stages to Force:** Warfare New Game (`FO4SF_GameMode == 2`) at Sanctuary Hills; attempt `startquest 09000817`.
- **REAL In-World Trigger:** Activate `04005C50` in Warfare mode; confirm `FO4SF_Sanctuary01` immediately stops without displaying Story objective `10`.

```console
bat q4f
```

```bat
; q4f: verify warfare mode gate stops sanctuary01 immediately
getglobalvalue 06000870
startquest 09000817
getstage 09000817
```

```log
FO4SF_MISSION rt=<rt> mission gate mode=2 started=false quest=sanctuary01
```

---

### 2.6 Parameterized 6-Case Template for Next FO4 Spine Missions (`MQ103`..`MQ302Inst`, `15` Quests)

As each of the `15` next FO4 spine quests (`MQ103`..`MQ302Inst`) converts into Starfield plugins, instantiate these `6` batch recipes (`q5a`..`q5f`) with `<XX><quest_local>`, `<XX><npc_local>`, `<entry_stage>`, `<mid_stage>`, and `<complete_stage>`:

```console
getstage <XX><quest_local>
bat q5a
bat q5b
bat q5c
bat q5d
bat q5e
bat q5f
```

```bat
; q5a: open-mode essential actor dead fallback check
set 06000871 to 1
startquest <XX><quest_local>
setstage <XX><quest_local> <entry_stage>
prid <XX><npc_local>
kill
getstage <XX><quest_local>

; q5b: objectives out of order (pre-cleared / late entry)
startquest <XX><quest_local>
setstage <XX><quest_local> <mid_stage>
getstage <XX><quest_local>

; q5c: leave cell mid-stage & return
getstage <XX><quest_local>
sqs <XX><quest_local>

; q5d: quit-to-desktop reload audit at entry/mid/complete
getstage <XX><quest_local>

; q5e: fast travel mid-quest audit
getstage <XX><quest_local>
sqs <XX><quest_local>

; q5f: pre-start arrival / mode-gate check
getglobalvalue 06000870
getstage <XX><quest_local>
```

- **REAL In-World Trigger per Template:**
  - `q5a` (Open Mode Essential Dead): Loot the documented W7 corpse holotape/key or activate the fallback terminal/successor NPC listed in Section 1.2 -> verify the quest (or next spine quest) advances cleanly without softlock.
  - `q5b` (Out of Order): Clear target room or collect quest item before talking to the giver -> verify idempotent `OnStageSet` catch-up.
  - `q5c` / `q5e` (Leave / Fast Travel): Exit cell `> 400 m` or fast-travel away mid-stage, return, and trigger the real door/terminal/NPC scene.
  - `q5d` (Save/Reload): Quit to desktop at each stage, reload, and verify `OnPlayerLoadGame` re-registers remote events and timers (for `MQ106`, also verify `FO4SF_FortHagenQuest` logs `load_game roof_gate_opened=` and re-binds all elevator controls).
  - `q5f` (Pre-Start Arrival): Enter target dungeon/location before quest starts -> verify zero orphaned objectives and clean Warfare mode gating (`mode=2 started=false`).

---

## 3. Tier 3 — Known-Bug Regressions (`#820`, `#829` & Community Patterns)

Every known defect below is converted into a concrete automated/in-game regression test where **our port fixes the fault rather than copying the original game's bug**:

### 3.1 Fallout 4 Known-Bug Regressions (`#820` `19` Bugs + `3` Spine Patterns = `22` Cases)

| Bug ID | Quest | Failure Mode | How Our Port Fixes It (Not Copies It) | Check Tier & Exact Pass Signal |
|---|---|---|---|---|
| `OPEN-01` | `FO4SF_NewGame` | Cryo pod floor clipping / infinite first load | `PodLift = 0.3 m` + `WaitFor3DLoad()` + `HandBack` fallback | Tier 2 (`q1d`): `pod settle ok=true` (`drop <= 0.5`) |
| `OPEN-02` | `FO4SF_NewGame` | Gear door stuck closed on console activation | Direct `SetOpen(True)` on `VltGearDoor01` + state check | Tier 2 (`q1a`): `cog door console activated` + `stage 30 by=vault_console` |
| `OPEN-03` | `FO4SF_NewGame` | Chargen save/HUD lock persisting post-exit | `SetInChargen(false,false,false)` + `LooksWait=120s` + stage-40 re-clear | Tier 2 (`q1d`): Save/Quicksave enabled on Commonwealth surface |
| `OPEN-04` | `FO4SF_NewGame` | Exterior vault lift platform fall-through | Two-phase `MoveTo` + `SurfaceTries=3` `SetPosition` + `CheckLanding` (`FallDrop=3.0m`) | Tier 2 (`q1c`): `landed z=<z> confirmed=True` + `stage 200` |
| `OPEN-05` | `FO4SF_Codsworth01` | Codsworth unmerged drift (`0.34 m/s`) / patrol stall | `FO4SF_CodsworthKeeper` (`0x000814`) holds Codsworth within `25 m` + releases in combat | Tier 2 (`q2e`): `keeper status codsworth` (`off <= 25.0`, `disabled=false`) |
| `OPEN-06` | `FO4SF_Codsworth01` / `Min00` | Skipping Sanctuary to Concord leaves stale objectives | `GiveConcordRadius=150m` auto-starts `Min00` stage `10` + `ClearObjectiveOnConcordStart` | Tier 2 (`q3f`): `min00 given by=concord` + `codsworth01 objective 10 cleared by=concord` |
| `WFC-01` | `FO4SF_Min00` | Exterior raider straggler / unloaded-3D stall at stage `20` | `CheckConcordRaidersWfc01` rescues subterranean/drifted raiders + `60s` absent/stuck write-off | Tier 2 (`q3c`): `wfc01 rescue` / `wfc01 raider cleared` -> `stage 30` |
| `WFC-02` | `FO4SF_Min00` | Approaching Preston when raiders `> 60 m` stalls stage `10` | `FindRadius=20.0m` + `OnActivate` calls `FoundPreston` and forces `StartCombat` | Tier 2 (`q3b`): `found preston` -> `stage 20` + `startcombat raider` |
| `WFC-03` | `FO4SF_Min00` | Stray friendly fire turns Preston hostile | `FO4SF_MinutemenFaction` Ally + `IgnoreFriendlyHits(True)` + per-tick `StopCombat()` | Tier 2 (`q3a`): Preston non-hostile at stage `30` -> `stage 40` |
| `WFC-04` | `FO4SF_Min00` | Post-fight museum/balcony dialogue lockout | `0x1814` `PrestonTalkScene` (`0x000900`) + `3`-retry watchdog + `120s` `TalkRadius` fallback | Tier 2 (`q3e`): `preston talk end info=0x092A -> stage 40` |
| `WFC-05` | `FO4SF_Min00` | Preston snaps `~2,955 m` back to unmerged coords after stage `200` | `FO4SF_CodsworthKeeper` (`0x000814`) keeps Preston at merged museum door across reloads | Tier 2 (`q3d`): `keeper status preston` (`off <= 25.0`, `held=true`) |
| `WFC-06` | `FO4SF_Min00` | Wave-2 Deathclaw snags below street grate (future restoration) | Cut-down reaches `200` cleanly; wave-2 adds subterranean `Z` rescue watchdog | Tier 1 + Tier 2 (`q3b`): clean `complete stage=200` |
| `WFC-07` | `FO4SF_Min00` | Silent `OnStageSet` drop skips objectives/Missions tab/reward | `QuestTypeSideQuest` (`0x047600`) + synchronous `AdvanceTo -> Apply` idempotency | Tier 2 (`q3d`): `stage 10..40`, `reward credits=100`, `complete stage=200` |
| `COMP-01`..`COMP-06` | `FO4SF_Min00` (`COMPreston`) | Restraint re-assertion, `AllowReserved` alias check, load-door stranding, bleedout/reload follow drops | `Optional \| AllowReserved` enforced in `dotnet/Mission check`; shared `GLOB` + `OnPlayerLoadGame` + `OnCombatStateChanged` planned | Tier 2 (`q3d`) + `preston-follow-pc-card.md`: `filled=1 linked=player released=True` |
| `FH-ELEV-01` | `MQ106` | Fort Hagen elevator blockers/panels fail to bind or drop on reload | `FO4SF_FortHagenQuest.psc` disables blockers idempotently and re-binds on `OnPlayerLoadGame` | Tier 1 + Tier 2 (`q5d`): `fh01_ready`, `fh02_ready`, `load_game roof_gate_opened=` |
| `ML-WIRE-01` | `MQ204` | Signal Interceptor wiring/power check deadlocks across 3 faction workshops | Workshop verification script validates powered link + allows self-decode terminal | Tier 1 (`check_quest_fragility.py --open-mode`) + Tier 2 (`q5a`, `q5b`) |
| `BH-HOSTILE-01` | `MQ206` | Stray Bunker Hill crossfire permanently breaks all 3 faction relations | Isolate neutral faction combat alarms during Bunker Hill cell entry | Tier 1 + Tier 2 (`q5a`, `q5c`) |

### 3.2 Fallout 3 Known-Bug Regressions (`#829` `fo3-main-and-side.md` — `20` Quests, `20` Cases)

| Bug IDs | Quests | Port Regression Fix Pattern | Automated / In-Game Gate |
|---|---|---|---|
| `FO3M-01`, `FO3M-04` | `CG01`, `CG04` | `CF-10` menu-close watchdog, `GetOpenState()` door retries, `PodLift = 0.3 m` landing check, unconditional `SetInChargen(false,false,false)` | Tier 1 + Wave A PC card (`special_points_allocated=40`, `landed z`) |
| `FO3M-02`, `FO3M-03`, `FO3M-10` | `CG02`, `CG03`, `MQ06` | Bounded `SayTo`/scene watchdog (`12–20 s`), `StopCombatAlarm()` before `EvaluatePackage()`, direct terminal/instructor bypasses | Tier 1 + Wave A/D PC cards (`combat_cleared=true`, `FO4SF_PATrainingGranted=1`) |
| `FO3M-05`, `FO3M-06`, `FO3M-07` | `MQ01`, `MQ02`, `MQ03` | Idempotent `GetItemCount` / stage catch-up closing skipped breadcrumbs cleanly when entering Rivet City or Vault 112 early | Tier 1 (`out_of_order_mid_entry`) + Wave C PC card (`0` stale objectives) |
| `FO3M-08`, `FO3M-09` | `MQ04`, `MQ05` | Persistent Tranquility Lane stash container with item-count checksum; per-door Taft Tunnels alias `MoveTo` + `SetRestrained(False)` | Tier 1 + Wave D PC card (`100%` inventory checksum, `0` stuck aliases) |
| `FO3S-01`, `FO3S-06` | `MS01`, `MS06` | `OnLocationChange` wave spawn + deterministic `SetGhost(False)` (`MS01`); `24h` deterministic march `MoveTo` + pre-cleared slaver flag (`MS06`) | Tier 1 + Wave C PC card |
| `FO3S-02`, `FO3S-08`, `FO3S-10` | `MS02`, `MS09`, `MS11` | `StopCombatAlarm()` on lair/treaty transitions; deterministic Harden Simms turn-in fallback when Sheriff dies | Tier 1 (`--open-mode`) + Wave B PC card |
| `FO3S-03`, `FO3S-04`, `FO3S-05`, `FO3S-07`, `FO3S-09` | `MS03`, `MS04`, `MS05`, `MS08`, `MS10` | `CF-7` rad/limb chapter latches + post-`MS11` alias relocation; explicit `Ref.IsDead()` for `5` ants; live `GetItemCount >= 30`; `!IsCompleted()` dual-reward lock; atomic `IMOD` clear | Tier 1 + Wave B/D PC cards |

### 3.3 Fallout: New Vegas Known-Bug Regressions (`#829` `fnv-main-and-side.md` + `VMS38` — `21` Quests, `21` Cases)

| Bug IDs | Quests | Port Regression Fix Pattern | Automated / In-Game Gate |
|---|---|---|---|
| `FNVM-01`, `FNVM-02` | `VCG01`, `VCG02` | Structured `CF-6`/`CF-3` exit callbacks (no `MenuMode` `GetButtonPressed` drops); `Ref.IsDead()` pre-cleared well geckos + campfire skip | Tier 1 + Wave A PC card (`hardcore_prompt_shown=true`) |
| `FNVM-03`, `FNVM-05`, `FNVM-06` | `VMQ01`, `VMQHouse1`, `VMQYesMan01` | Direct Strip `VMQ01` catch-up; pre-upgraded Fort bunker reconciliation; `Auto` quest properties across `56` cross-`INFO`s + Securitron respawn | Tier 1 (`--open-mode`) + Wave C/D PC cards |
| `FNVM-04`, `FNVM-07`, `FNVM-08`, `FNVM-09`, `FNVM-10` | `VMQTops`, `VMQ02`, `VMQ03a`, `VMQ04`, `VMQ05` | Per-actor casino weapon-stash checksum; `GAP-J3-02` `>=16` isolated `CF-1` `REPU` slots; `VMQ03a` alarm exemptions; pre-placed sentry refs replacing `PlaceAtMe`; pre-completed minor-faction truce checks | Tier 1 + Wave C/D PC cards (`100%` weapon restore, `0` slot collisions) |
| `FNVS-01`, `FNVS-02`, `FNVS-08` | `VMS16`, `VMS16b`, `VMS03` | Once-only `ChetEquipped` (`VMS16`) and `RewardGiven` (`VMS03`) latches; atomic `VMS16`/`VMS16b` mutual exclusion; monotonic `24h` `Utility.GetCurrentGameTime()` orbital cooldown | Tier 1 + Wave B/D PC cards (`0` infinite XP/item loops) |
| `FNVS-03`, `FNVS-04`, `FNVS-05`, `FNVS-06`, `FNVS-07`, `FNVS-09`, `FNVS-10` | `VMS02`, `VMS33`, `VMS44`, `VMS53`, `VMS01`, `VMS20`, `VMS29` | `Vulpes` `OnDeath` `Alerio` fallback; `Logan` carries station keys from spawn; idempotent `VMS53` safe note + `12m` beret trigger; `30s` REPCONN exodus catch-up; Boulder City truce `SetAlly`; Freeside parley `IgnoreCombat` isolation | Tier 1 (`--open-mode`) + Wave B/C PC cards |
| `RF-FNV-001` | `VMS38` | Fixes vanilla unmarked `bTroikeFreed` / post-quest Mick lockout and upgrades **Pimp-Boy 3 Billion** to `3` independent unlock routes (see `docs/testing/reachability-fixes.md`) | Tier 1 (`rewards.pimp_boy_3_billion` `>= 3` routes) + Tier 4 feel check |

---

## 4. Tier 4 — Owner Play Scope

Owner play time is protected by keeping Tier 4 strictly bounded to **three categories only**:
1. **Main Spine Quests** (`19` FO4 + `10` FO3 + `10` FNV = `39` quests) — end-to-end story pacing, dialogue readability, and choice clarity.
2. **Quests on the `FRAGILE` List** (`18` total across all 3 titles, of which `11` overlap the main spines and `7` are fragile side quests: FO3 `MS01`, `MS03`, `MS11`; FNV `VMS53`, `VMS01`, `VMS29`, `VMS38`).
3. **Feel Items** (`FO4SF_NewGame` Vault 111 ascent & `T7` first-person Pip-Boy arm/boot movie, `FO4SF_Codsworth01` Sanctuary conversation pacing, `FO4SF_Min00` Concord battle & Preston dialogue feel, `FO4SF_Sanctuary01` workshop entry feel, and `VMS38` Pimp-Boy 3 Billion style swap feel).

**Exact Tier 4 Count:** **`46` quests** (`19` FO4, `13` FO3, `14` FNV). The remaining **`14` non-fragile side quests** in the catalog (`FO3`: `MS02`, `MS04`, `MS05`, `MS06`, `MS08`, `MS09`, `MS10`; `FNV`: `VMS16`, `VMS16b`, `VMS02`, `VMS33`, `VMS44`, `VMS03`, `VMS20`) are verified strictly by automated Tiers 1–3 with **zero required owner playthroughs**.
