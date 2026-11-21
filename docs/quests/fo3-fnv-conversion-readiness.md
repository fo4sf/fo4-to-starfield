# Fallout 3 & Fallout: New Vegas Quest Conversion Readiness (`40`-Quest Audit)

This document fulfills **Job 4** of the multi-title quest and script census: a clean-room conversion readiness audit of the **first `10` main-story quests and first `10` side quests** in **Fallout 3** (`20` quests in `Fallout3.esm`) and **Fallout: New Vegas** (`20` quests in `FalloutNV.esm`, `40` quests total). Every record count, `EditorID`, `FormID`, `Begin` block signature, GECK function dependency, `DIAL`/`INFO` linkage, and `PACK` dependency below was measured read-only from the installed masters by [`scripts/research/all_games_census.py`](../../scripts/research/all_games_census.py), mapped onto Job 1 ([`all-games-quests-scripts.md`](../research/all-games-quests-scripts.md)) and Job 2 ([`core-fit-by-title.md`](../research/core-fit-by-title.md)).

Companion clean-room known-bug ledgers and owner read-approval queues:
- **Fallout 3 (`20` quests):** [`known-bugs/fo3-main-and-side.md`](known-bugs/fo3-main-and-side.md) (`FO3M-01`..`FO3M-10`, `FO3S-01`..`FO3S-10`, `REQ-FO3NV-KB-01`..`REQ-FO3NV-KB-06`)
- **Fallout: New Vegas (`20` quests):** [`known-bugs/fnv-main-and-side.md`](known-bugs/fnv-main-and-side.md) (`FNVM-01`..`FNVM-10`, `FNVS-01`..`FNVS-10`, `REQ-FO3NV-KB-07`..`REQ-FO3NV-KB-12`)

> **Public-Surface & Clean-Room Policy:** Zero dialogue strings, quest journal descriptions, `FULL` display text, or decompiled script bodies appear in this document. Quests, scripts, and AI packages are referenced strictly by `EditorID`, hex `FormID`, structural counts, GECK function/block identifiers, and `CF-1`..`CF-10` shared-system bindings.

---

## 1. Aggregate Structural Comparison (`Fallout 3` vs `Fallout: New Vegas` `20`-Quest Slices)

| Metric (Measured from Base `.esm`) | `FO3` Main `10` (`CG01`..`MQ06`) | `FO3` Side `10` (`MS01`..`MS11`) | `FO3` `20`-Quest Total | `FNV` Main `10` (`VCG01`..`VMQ05`) | `FNV` Side `10` (`VMS16`..`VMS29`) | `FNV` `20`-Quest Total |
|---|---:|---:|---:|---:|---:|---:|
| Quests Audited (`QUST`) | `10` | `10` | `20` | `10` | `10` | `20` |
| Quest Stages (`INDX`) | `213` | `133` | `346` | `113` | `78` | `191` |
| Quest Objectives (`QOBJ`) | `84` | `120` | `204` | `120` | `98` | `218` |
| Attached `QUST.SCRI` Quest Scripts | `10` | `10` | `20` | `10` | `10` | `20` |
| Quest Script Local Variables (`SCHR`) | `257` | `631` | `888` | `128` | `212` | `340` |
| External Referencing `SCPT` Records (`SCRO`) | `164` | `91` | `255` | `171` | `93` | `264` |
| Directly Owned `DIAL` Topics (`QSTI`) | `805` | `1,111` | `1,916` | `283` | `229` | `512` |
| Directly Owned `INFO` Responses | `2,241` | `2,772` | `5,013` | `509` | `322` | `831` |
| Cross-Quest `INFO` `SCRO` References | `331` | `460` | `791` | `525` | `485` | `1,010` |
| Owned-`INFO` Result Scripts (`SCTX`) | `908` | `1,252` | `2,160` | `617` | `328` | `945` |
| `INFO` Skill / ActorValue `CTDA` Checks | `28` | `152` | `180` | `23` | `53` | `76` |
| `INFO` Faction / Reputation / Karma `CTDA` Checks | `198` | `167` | `365` | `28` | `65` | `93` |
| Quest-Linked `PACK` AI Packages | `308` | `321` | `629` | `103` | `72` | `175` |

### Three Structural Findings Driving Converter Architecture

1. **Quest-Owned Dialogue (`FO3`) vs Hub-Owned Cross-Quest Dialogue (`FNV`):**
   - In `Fallout3.esm`, `19` of `20` audited quests directly own their `DIAL` topics via `QSTI` (`5,013` owned `INFO`s vs `791` cross-quest `SCRO` references; only `MQ02` owns `0` `DIAL` topics because its dialogue lives on the GNR hub quest and `ThreeDogScript`).
   - In `FalloutNV.esm`, **`12` of `20` audited quests own `0` `INFO` records directly** (`VMQ01`, `VMQHouse1`, `VMQYesMan01`, `VMQ02`, `VMQ03a`, `VMQ04`, `VMQ05`, `VMS16`, `VMS16b`, `VMS53`, `VMS01`, `VMS20`). Instead, dialogue resides in town or NPC hub quests (`VDialogueGoodsprings`, `VDialogueNovac`, `VDialogueREPCONN`, `VDialogueBoulderCity`, `VDialogueLucky38`, `VDialogueFreeside`) that mutate quest state across **`1,010` cross-quest `INFO` `SCRO` references** (`SetStage`, `SetObjectiveDisplayed`, and `QuestID.varName` assignments).
   - **Converter Rule:** Every converted `QUST` must generate its `QuestScript` Papyrus class with public `Auto` properties for all `SCHR` variables **before** compiling `TopicInfo` fragments, and `DIAL`/`INFO` conversion must pull the closure of cross-referencing hub `INFO`s alongside `QSTI`-owned `INFO`s.
2. **Active `Begin GameMode` Controllers vs Variable-Struct Quest Scripts:**
   - `38` of `40` `QUST.SCRI` scripts declare `Begin GameMode` (`3` also declare `Begin MenuMode`: `CG01SCRIPT`, `MS10QuestScript`, and `VCG01SCRIPT` for chargen UI and sleep-hour transitions).
   - `2` `QUST.SCRI` scripts (`VMQYesMan01script` with `5` vars; `VMS53SCRIPT` with `7` vars) have **`0` `Begin` blocks**, and `3` more (`MS08QuestScript` `116` vars, `REPCONGhoulQuestScript` `35` vars, `VMS29Script` `14` vars) hold shared state variables mutated almost entirely by `INFO` result scripts and external actor/trigger `SCPT`s.
3. **Dialogue Checks Concentrate in `GetActorValue` (`CF-6` / `CF-9`) and Faction / Reputation / Karma (`CF-1`):**
   - Owned `INFO`s across these `40` quests contain `0` direct `HasPerk` `CTDA` rows in the base slice (perk-specific `INFO`s sit primarily in generic/hub greeting quests or DLCs), `256` `GetActorValue` skill/SPECIAL checks (led by `MS03` `69`, `MS08` `32`, `CG04` `15`, `MS01` `13`, `VMQTops` `12`, `VMS02` `11`, `VMS16` `10`), and `458` faction/reputation/karma `CTDA` checks (led by `CG04` `110`, `MS10` `73`, `VMS03` `49`, `MQ04` `46`, `MS01` `46`).

---

## 2. Fallout 3 Conversion Readiness (`20` Quests in `Fallout3.esm`)

> **Selection Note:** The main-story slice covers sequential quests `1..10` from Vault 101 birth through the Citadel/Little Lamplight handoff (`CG01`..`CG04`, `MQ01`..`MQ06`). The side-quest slice covers numbered side quests `MS01`..`MS11` (`MS07` is unused/omitted in shipped `Fallout3.esm`, making `MS11` the 10th shipped side quest).

### 2.1 First `10` Main-Story Quests (`CG01`..`CG04`, `MQ01`..`MQ06`)

| # | `QUST` (`FormID`) | `INDX` / `QOBJ` | `QUST.SCRI` (`FormID`, Vars, Blocks) | Ext `SCPT` | `DIAL` / Owned `INFO` (`+Cross`) | `INFO` Res / Skill / Fact | `PACK` | Core Systems & Key GECK Calls | Bug Ledger |
|---:|---|---:|---|---:|---|---:|---:|---|---|
| 1 | `CG01` (`0x014E83`) | `20` / `8` | `CG01SCRIPT` (`0x030769`, `5`v, `GameMode`+`MenuMode`) | `6` | `1` / `20` (`+0`) | `16` / `5` / `0` | `6` | `CF-6`, `CF-10` (`SetStage`, `GetSecondsPassed`, `CG01SpecialBookSCRIPT`) | `FO3M-01` |
| 2 | `CG02` (`0x014E84`) | `31` / `5` | `CG02SCRIPT` (`0x0304D9`, `18`v, `GameMode`) | `10` | `96` / `343` (`+4`) | `117` / `0` / `14` | `56` | `CF-4`, `CF-10` (`SayTo`, `PlaySound3D`, `CG02RadroachSCRIPT`) | `FO3M-02` |
| 3 | `CG03` (`0x014E85`) | `19` / `5` | `CG03Script` (`0x01CE2E`, `84`v, `GameMode`) | `9` | `66` / `318` (`+0`) | `165` / `1` / `6` | `48` | `CF-6`, `CF-9`, `CF-10` (`EvaluatePackage`, `GetActorValue`, `StartCombat`/`StopCombat`) | `FO3M-03` |
| 4 | `CG04` (`0x014E86`) | `36` / `7` | `CG04Script` (`0x029341`, `33`v, `GameMode`) | `17` | `149` / `465` (`+7`) | `150` / `15` / `110` | `47` | `CF-1`, `CF-9`, `CF-10` (`GetInCell`, `GetOpenState`, `StartRadioConversation`, `Autosave`) | `FO3M-04` |
| 5 | `MQ01` (`0x014E87`) | `44` / `8` | `MQ01Script` (`0x0151CB`, `23`v, `GameMode`) | `17` | `61` / `134` (`+109`) | `109` / `1` / `10` | `48` | `CF-1`, `CF-4` (`Say`, `SayTo`, `MQ01BehemothSCRIPT`, `GNRBehemothTriggerSCRIPT`) | `FO3M-05` |
| 6 | `MQ02` (`0x014E88`) | `8` / `6` | `MQ02QuestScript` (`0x02446D`, `10`v, `GameMode`) | `5` | `0` / `0` (`+20`) | `11` / `0` / `3` | `0` | `CF-1` (`GetDistance`, `GetInCell`, `ThreeDogScript`, `MQ02VirgoIIDishScript`) | `FO3M-06` |
| 7 | `MQ03` (`0x014E89`) | `10` / `8` | `MQ03Script` (`0x044934`, `8`v, `GameMode`) | `7` | `67` / `83` (`+48`) | `42` / `2` / `1` | `7` | `CF-6`, `CF-9` (`GetQuestRunning`, `MQ04PlayerPodShellScript`, `VaultSuit112Script`) | `FO3M-07` |
| 8 | `MQ04` (`0x014E8A`) | `16` / `14` | `MQ04Script` (`0x0254C9`, `37`v, `GameMode`) | `32` | `200` / `516` (`+5`) | `130` / `0` / `46` | `25` | `CF-1` (Karma), `CF-10` (`MoveTo`, `Resurrect`, `RemoveItem`, `EvaluatePackage`) | `FO3M-08` |
| 9 | `MQ05` (`0x014E8B`) | `20` / `16` | `MQ05Script` (`0x01B52E`, `32`v, `GameMode`) | `58` | `119` / `292` (`+100`) | `115` / `4` / `7` | `61` | `CF-1`, `CF-7`, `CF-9` (`MoveTo`, `SetRestrained`, `GetDead`, `DoctorLiScript`) | `FO3M-09` |
| 10 | `MQ06` (`0x014E8C`) | `9` / `7` | `MQ06Script` (`0x0209F7`, `7`v, `GameMode`) | `3` | `46` / `70` (`+38`) | `53` / `0` / `1` | `10` | `CF-8` (PA training gate in Citadel), `CF-9` (`GetInCell`, `ScribeRothchildScript`) | `FO3M-10` |

#### Per-Quest Script & Package Dependencies (`FO3` Main `10`)
- **`CG01` (`0x014E83`):** Opening birth/toddler interior sequence. Depends on `CG01DadSCRIPT` (`0x02EA3B`), `CG01SpecialBookSCRIPT` (`0x02ECB9` -> `CF-6` `40`-point SPECIAL allocator), `CG01PlaypenGateSCRIPT` (`0x02EA3C`), `CG01ExitCribTriggerSCRIPT` (`0x02ECBA`), `CG01DadTriggerSCRIPT` (`0x081983`), `CG01EndQuestTriggerSCRIPT` (`0x02ECBB`), and `6` `CG01Dad*` packages (`0x02EAAF`, `0x02ECC3`, `0x02ECC4`, `0x03A181`, `0x0457C4`, `0x0C6DE4`). `MenuMode` polls chargen completion (`CF-10`).
- **`CG02` (`0x014E84`):** Vault 101 age-10 sequence & first weapon tutorial. Depends on `CG02DadSCRIPT` (`0x0304DA`), `CG02JonasSCRIPT` (`0x0306D8`), `CG02RadroachSCRIPT` (`0x0306CE`), `CG02SweetrollSCRIPT` (`0x0C79DF`), `CG02DinerIntercomSCRIPT` (`0x077786`), and `56` party/conversation packages (`CG02AmataTalkTo*`, `CG02AmataGreetPlayerBeginning` `0x0319C0`) driven by `SayTo` timers.
- **`CG03` (`0x014E85`):** Vault 101 age-16 exam & tag-skill assignment. `CG03Script` (`84` vars) coordinates `CG03AmataScript` (`0x01CE2D`), `CG03ButchScript` (`0x01CE34`), `CG03PaulScript` (`0x01CE37`), `CG03ClassroomTriggerSCRIPT` (`0x034908`), and `48` classroom/hallway packages (`CG03AmataSitInClass` `0x034200`, `CG03AmataTakeTest` `0x05F9C1`) before computing `3` tag skills (`+15` `AVIF` in `CF-6`).
- **`CG04` (`0x014E86`):** Vault 101 escape & exterior handoff (`CF-10`). Uses `17` external scripts (`CG04AmataSCRIPT` `0x0230D4`, `CG04OverseerSCRIPT` `0x0230D5`, `CG04ButchRadroachSCRIPT` `0x02A16F`, `CG04RadroachSpawnSCRIPT` `0x064E2C`), `47` packages (`CG04AmataForceGreet` `0x02AE36`), `15` skill checks, and `110` faction/disposition checks. Must hand off at the Vault 101 exterior door into `CF-6` character rebuild prompt + `Game.SetInChargen(false, false, false)`.
- **`MQ01` (`0x014E87`):** Megaton -> GNR plaza progression (`109` cross-quest `INFO` refs across Megaton/Rivet City/GNR). Depends on `ColinMoriartySCRIPT` (`0x01FEFE`), `GNRBehemothTriggerSCRIPT` (`0x0541D4`), `MQ01BehemothSCRIPT` (`0x020285`), `MQ01CorpseWithFatmanSCRIPT` (`0x074F89`), `MQ01GNRmutantSCRIPT` (`0x01F927`), and `48` Brotherhood patrol packages (`MQ01BoSPatrol1` `0x021EA0`).
- **`MQ02` (`0x014E88`):** Museum of Technology -> Washington Monument relay dish. Zero owned `DIAL` topics (`20` cross-quest `INFO` refs on `ThreeDogScript` `0x05A59D` and GNR dialogue); depends on `MQ02MuseumPlanetariumTrigger01Script` (`0x027932`), `MQ02VirgoIIDishScript` (`0x02446E`), `MQ02RelayBeforeScript` (`0x02446F`), and `GNRBroadcastEffectSCRIPT` (`0x0C0547`).
- **`MQ03` (`0x014E89`):** Rivet City -> Project Purity -> Smith Casey's Garage (`Vault 112`). Bridges directly into `MQ04`/`MQ05` (`MQ03purityMutantsSCRIPT` `0x078802`, `VaultSuit112Script` `0x04B1D0`, `MQ04PlayerPodShellScript` `0x02A45D`, `MQ04PlayerPodActivationTriggerScript` `0x06F27D`, `MQAPanelScript` `0x03D20A`).
- **`MQ04` (`0x014E8A`):** Tranquility Lane virtual simulation (`32` external scripts: `BettyScript` `0x07DC71`, `JanetRockwellScript` `0x02870C`, `MQ04ChineseSoldierScript` `0x02B8ED`, `MQ04DadPodScript` `0x05AE43`, `MQ04ChandelierScript` `0x059BC8`). Heavy use of `MoveTo`, `RemoveItem` (inventory stash/restore), `Resurrect` (simulated NPC resets), and Karma penalties/bonuses (`CF-1`).
- **`MQ05` (`0x014E8B`):** Project Purity activation, Enclave arrival & Taft Tunnels escort (`58` external scripts — highest in `FO3` slice: `DoctorLiScript` `0x01CC62`, `ColonelAutumnScript` `0x01B52F`, `CitadelCraneScript` `0x0C339A`, Vertibird strafe/flyover scripts, and `61` escort/hold packages such as `MQ05AnnaInProjectPurityPostMutants` `0x0BAC0E` and `MQ05AutumnInterrogateDad` `0x01B56B`). Exercises `SetRestrained`, `GetDead`, and radiation chamber scripting (`CF-7`).
- **`MQ06` (`0x014E8C`):** Citadel arrival, Vault-Tec/GECK research & Vault 87 lead (`ScribeRothchildScript` `0x0B881E`, `MQ06LLBridgeTerminalScript` `0x003A17`, `MQ06LockControlsTriggerScript` `0x071978`, `10` Citadel scene packages `MQ06ElderTalktoLi` `0x05FD14`, `MQ06JosephActivateTerminal` `0x01A4D7`). Unlocks Citadel Power Armor training access (`CF-8` `pa_training_required = True`).

### 2.2 First `10` Side Quests (`MS01`..`MS06`, `MS08`..`MS11`)

| # | `QUST` (`FormID`) | `INDX` / `QOBJ` | `QUST.SCRI` (`FormID`, Vars, Blocks) | Ext `SCPT` | `DIAL` / Owned `INFO` (`+Cross`) | `INFO` Res / Skill / Fact | `PACK` | Core Systems & Key GECK Calls | Bug Ledger |
|---:|---|---:|---|---:|---|---:|---:|---|---|
| 1 | `MS01` (`0x014E94`) | `22` / `8` | `MS01QuestScript` (`0x02B4FB`, `61`v, `GameMode`) | `13` | `60` / `225` (`+43`) | `127` / `13` / `46` | `79` | `CF-6`, `CF-9` (`SetActorValue`, `EvaluatePackage`, `SetGhost`, `MS01ProtectronScript`) | `FO3S-01` |
| 2 | `MS02` (`0x014E95`) | `14` / `7` | `MS02QuestScript` (`0x037364`, `60`v, `GameMode`) | `4` | `51` / `169` (`+5`) | `81` / `5` / `4` | `19` | `CF-1`, `CF-9` (`AddScriptPackage`, `StopCombat`, `AntAgonizerScript`, `MechanistScript`) | `FO3S-02` |
| 3 | `MS03` (`0x014E96`) | `34` / `34` | `MS03script` (`0x02D271`, `71`v, `GameMode`) | `9` | `120` / `462` (`+54`) | `255` / `69` / `1` | `4` | `CF-6`, `CF-7`, `CF-9` (`GetHealthPercentage`, `GetActorValue` rads/limbs, `69` skill/SPECIAL checks) | `FO3S-03` |
| 4 | `MS04` (`0x014E97`) | `8` / `11` | `MS04Script` (`0x0307C6`, `77`v, `GameMode`) | `6` | `167` / `258` (`+34`) | `91` / `10` / `4` | `24` | `CF-6`, `CF-9` (`GetDeadCount`, `DoctorLeskoScript`, `MS04QueenAntScript`, quest reward perk) | `FO3S-04` |
| 5 | `MS05` (`0x014E98`) | `7` / `6` | `MS05QuestScript` (`0x038A79`, `47`v, `GameMode`) | `3` | `98` / `184` (`+28`) | `74` / `2` / `4` | `5` | `CF-1`, `CF-6` (`GetItemCount`, `RemoveItem`, `SierraPetrovitaScript`, `RonaldLarenScript`) | `FO3S-05` |
| 6 | `MS06` (`0x014E99`) | `11` / `16` | `MS06Script` (`0x0239CA`, `56`v, `GameMode`) | `16` | `73` / `276` (`+110`) | `175` / `8` / `18` | `60` | `CF-1` (Karma), `CF-9` (`SetEnemy`, `GetItemCount`, `HannibalHamlinScript`, `60` travel/listen `PACK`s) | `FO3S-06` |
| 7 | `MS08` (`0x014E9B`) | `10` / `8` | `MS08QuestScript` (`0x023A15`, `116`v, `GameMode`) | `7` | `121` / `385` (`+21`) | `193` / `32` / `3` | `7` | `CF-1`, `CF-6`, `CF-9` (`116` quest vars, `32` skill checks, `VictoriaWattsScript`, `MS08TerminalScript`) | `FO3S-07` |
| 8 | `MS09` (`0x014E9C`) | `9` / `10` | `MS09QuestScript` (`0x014BBF`, `67`v, `GameMode`) | `11` | `201` / `380` (`+32`) | `103` / `5` / `10` | `39` | `CF-1`, `CF-6`, `CF-9` (`GetInSameCell`, `MoveTo`, `MS09FamilyVanceScript`, `MS09CorpseScript`) | `FO3S-08` |
| 9 | `MS10` (`0x02A274`) | `8` / `8` | `MS10QuestScript` (`0x02A2DE`, `46`v, `GameMode`+`MenuMode`) | `15` | `156` / `285` (`+99`) | `65` / `2` / `73` | `57` | `CF-1`, `CF-6` (`GetPCSleepHours`, `RemoveImageSpaceModifier`, `HaroldScript`, `MS10HaroldsHeartScript`) | `FO3S-09` |
| 10 | `MS11` (`0x014E9E`) | `10` / `12` | `MS11Script` (`0x014EBA`, `30`v, `GameMode`) | `7` | `64` / `148` (`+34`) | `88` / `6` / `4` | `27` | `CF-1` (Karma +/-1000), `CF-9` (`LucasSimmsScript`, `MS11BombScript`, `MS11DetonatorSCRIPT`) | `FO3S-10` |

#### Per-Quest Script & Package Dependencies (`FO3` Side `10`)
- **`MS01` (`0x014E94` — Big Town rescue & defense):** `13` external scripts (`BigTownResidentSCRIPT` `0x02C117`, `MS01BigTownSuperMutantScript` `0x02DEAF`, `MS01ProtectronScript` `0x02C11C`) and `79` town defense/training sandbox packages (`FFEU12SandboxBigtown*`). Uses `13` skill checks (Small Guns, Sneak, Explosives, Science, Medicine) to select town defense mode (`CF-9`).
- **`MS02` (`0x014E95` — Canterbury Commons costumed confrontation):** `AntAgonizerScript` (`0x038AB0`), `MechanistScript` (`0x038AAF`), `UncleRoeSCRIPT` (`0x068E7C`), and `19` duel/retreat packages (`MS02AntAgonizerBattle` `0x03736B`, `MS02AntAgonizerEscape` `0x03736D`) driven by `AddScriptPackage` and `StopCombat`.
- **`MS03` (`0x014E96` — Megaton multi-chapter survival research):** Highest objective (`34`), owned `INFO` result-script (`255`), and skill/SPECIAL `CTDA` count (`69`) in the `40`-quest audit. Polls player radiation (`GetActorValue RadiationRads` -> `CF-7`), health/limb condition (`GetHealthPercentage` -> `CF-4`/`CF-6`), and `9` chapter-specific item/terminal scripts (`MS03MoiraScript` `0x02D2C0`, `MS03MoleRatRepellantScript` `0x02EF50`, `MS03MirelurkScript` `0x02EF57`, `MS03RobCoMainframeTerminalScript` `0x05A707`), plus post-`MS11` ghoulified fallback packages (`MoiraGhoulSandboxDefault` `0x05CFC0`).
- **`MS04` (`0x014E97` — Grayditch fire ants & resettlement):** Tracks nest clearance via `GetDeadCount` across `MS04NestGuardianAntScript` (`0x06020C`) and `MS04QueenAntScript` (`0x0C20E4`), grants a quest-mutagen `PERK` via `DoctorLeskoScript` (`0x0C21D5` -> `CF-6`), and routes resettlement across `24` post-quest packages (`MS04BryanWilksPost*`).
- **`MS05` (`0x014E98` — Girdershade Nuka-Cola Quantum collection):** Inventory-counter state machine (`GetItemCount`, `RemoveItem`) across `SierraPetrovitaScript` (`0x049075`), `RonaldLarenScript` (`0x048124`), `MS05TerminalDataModuleScript` (`0x04DDDD`), and `5` tour/confrontation packages (`MS05RonaldLarenBlackWidow` `0x0AC3EB`).
- **`MS06` (`0x014E99` — Temple of the Union / Lincoln Memorial):** Multi-site faction confrontation (`110` cross-quest `INFO` refs, `60` march/speech packages `HannibalAtMemorial` `0x02DD03`, `HannibalHamlinSpeech` `0x0284F1`, and `16` scripts including `HannibalHamlinScript` `0x027FAE`, `LeroyWalkerScript` `0x028EDA`, `EndingBinksScript` `0x068A9E`).
- **`MS08` (`0x014E9B` — Rivet City android investigation):** Pure dialogue/clue-flag architecture: `MS08QuestScript` (`0x023A15`) declares **`116` quest variables** and delegates stage mutations to `193` `INFO` result scripts (`32` skill/Medicine/Science/Speech checks), `MS08NoteScript` (`0x05FAE5`), `MS08TerminalScript` (`0x05FAF4`), `VictoriaWattsScript` (`0x079A15`), and `DoctorLiScript` (`0x01CC62`).
- **`MS09` (`0x014E9C` — Arefu & Meresti Metro settlement accord):** `11` external scripts (`MS09ArefuResidentScriptEvanKing` `0x07C118`, `MS09CorpseScript` `0x019422` Medicine inspection, `MS09FamilyVanceScript` `0x070882`, `MS09FamilyFailsafeTriggerScript` `0x07E1DB`) and `39` guard/schedule packages.
- **`MS10` (`0x02A274` — Oasis ceremony & cavern heart):** Uses `Begin MenuMode` (`GetPCSleepHours`) + `RemoveImageSpaceModifier` for the sap ceremony transition (`MS10BowlScript` `0x0AC034`, `MS10CeremonyAreaTriggercScript` `0x0BCDA8`), `HaroldScript` (`0x0315EB`), `MS10HaroldsHeartScript` (`0x031491` three-way outcome perk/reward -> `CF-6`/`CF-1`), and `57` escort/ceremony packages.
- **`MS11` (`0x014E9E` — Megaton atomic bomb disarm / detonation):** Branching world-state controller (`LucasSimmsScript` `0x003B8D`, `MS11BombScript` `0x078CB3` Explosives skill check, `MS11DetonatorSCRIPT` `0x01E9AB`, `MS11FinScript` `0x03DA2B`, `27` saloon/balcony packages `MS11ColinMoriarityWatchBurkeKillSimms` `0x06ED0E`, `MS11BurkeForceGreetAtDetonator` `0x01502D`). Coupled with `MS03` survivor handoff and major `CF-1` Karma delta.

---

## 3. Fallout: New Vegas Conversion Readiness (`20` Quests in `FalloutNV.esm`)

> **Selection Note:** The main-story slice covers sequential quests `1..10` along the Act I -> Act II junction (`VCG01`, `VCG02`, `VMQ01`, `VMQTops`, `VMQHouse1`, `VMQYesMan01`, `VMQ02`, `VMQ03a`, `VMQ04`, `VMQ05`). The side-quest slice covers the first `10` named `VMS*` quests encountered along the canonical Goodsprings -> Primm -> Mojave Outpost -> Nipton -> Novac -> HELIOS One -> Boulder City -> Freeside route (`VMS16`, `VMS16b`, `VMS02`, `VMS33`, `VMS44`, `VMS53`, `VMS01`, `VMS03`, `VMS20`, `VMS29`).

### 3.1 First `10` Main-Story Quests (`VCG01`..`VMQ05`)

| # | `QUST` (`FormID`) | `INDX` / `QOBJ` | `QUST.SCRI` (`FormID`, Vars, Blocks) | Ext `SCPT` | `DIAL` / Owned `INFO` (`+Cross`) | `INFO` Res / Skill / Repu | `PACK` | Core Systems & Key GECK Calls | Bug Ledger |
|---:|---|---:|---|---:|---|---:|---:|---|---|
| 1 | `VCG01` (`0x104C1C`) | `38` / `4` | `VCG01SCRIPT` (`0x104C00`, `13`v, `GameMode`+`MenuMode`) | `10` | `92` / `128` (`+5`) | `126` / `4` / `0` | `7` | `CF-3`, `CF-6`, `CF-10` (`SexChange`, `ShowMessage`, `GetButtonPressed`, `VCG01VigorTesterSCRIPT`) | `FNVM-01` |
| 2 | `VCG02` (`0x10A214`) | `10` / `9` | `VCG02SCRIPT` (`0x10A1F0`, `4`v, `GameMode`) | `14` | `17` / `31` (`+4`) | `21` / `0` / `0` | `14` | `CF-3`, `CF-5`, `CF-10` (`EvaluatePackage`, `GSSunnySmilesScript`, `VCG02GeckoDeathSCRIPT`, campfire/hardcore prompt) | `FNVM-02` |
| 3 | `VMQ01` (`0x0842DD`) | `6` / `12` | `VMQ01QuestScript` (`0x119995`, `4`v, `GameMode`) | `7` | `0` / `0` (`+26`) | `16` / `0` / `0` | `1` | `CF-1` (`GetHasNote`, `GetMapMarkerVisible`, `VictorScript`, `PrimmDeputyScript`) | `FNVM-03` |
| 4 | `VMQTops` (`0x11345D`) | `16` / `13` | `VMQTopsScript` (`0x115F03`, `37`v, `GameMode`) | `24` | `173` / `350` (`+94`) | `188` / `12` / `10` | `24` | `CF-1`, `CF-9` (`BennySCRIPT`, `TopsExteriorDoorSCRIPT`, weapon-holdout & suite `PACK`s) | `FNVM-04` |
| 5 | `VMQHouse1` (`0x147885`) | `8` / `9` | `VMQHouse1script` (`0x16ADDD`, `6`v, `GameMode`) | `10` | `0` / `0` (`+43`) | `42` / `0` / `4` | `0` | `CF-1` (`Lucky38VictorElevatorScript`, `Lucky38UpgradeSecuritronsSCRIPT`, `FortCaesarScript`) | `FNVM-05` |
| 6 | `VMQYesMan01` (`0x157321`) | `5` / `10` | `VMQYesMan01script` (`0x15827E`, `5`v, `None`) | `16` | `0` / `0` (`+56`) | `49` / `0` / `0` | `4` | `CF-1` (`NVCRMrHouseSCRIPT`, `Lucky38MrHouseTerminalCodeSCRIPT`, `VMQYesManTravel38Casino`) | `FNVM-06` |
| 7 | `VMQ02` (`0x129D14`) | `12` / `35` | `VMQ02QuestScript` (`0x129D15`, `15`v, `GameMode`) | `40` | `1` / `0` (`+123`) | `96` / `4` / `0` | `2` | `CF-1` (`16`-state `REPU` reset & `35`-objective minor-faction matrix, `FortCaesarScript`) | `FNVM-07` |
| 8 | `VMQ03a` (`0x131F08`) | `6` / `8` | `VMQ03aQuestScript` (`0x131F0A`, `39`v, `GameMode`) | `32` | `0` / `0` (`+65`) | `34` / `1` / `5` | `47` | `CF-1` (`GetReputationThreshold`, disguise `GetEquipped`), `CF-9` (`47` speech/defense `PACK`s) | `FNVM-08` |
| 9 | `VMQ04` (`0x1344E8`) | `3` / `2` | `VMQ04QuestScript` (`0x1344EB`, `4`v, `GameMode`) | `0` | `0` / `0` (`+0`) | `0` / `0` / `0` | `4` | `CF-4` (`PlaceAtMe`, `KillActor`, `SVSentryBot01Travel`..`04Travel` substation battle) | `FNVM-09` |
| 10 | `VMQ05` (`0x136166`) | `9` / `18` | `VMQ05QuestScript` (`0x174083`, `1`v, `GameMode`) | `18` | `0` / `0` (`+69`) | `45` / `2` / `9` | `0` | `CF-1` (NCR `REPU` + failsafe `VMQNCRFail`), `CF-8` (BoS bunker `HVOuterRoomScript`) | `FNVM-10` |

#### Per-Quest Script & Package Dependencies (`FNV` Main `10`)
- **`VCG01` (`0x104C1C` — Doc Mitchell interior character creation):** `VCG01SCRIPT` (`MenuMode` + `GameMode`), `VCG01VigorTesterSCRIPT` (`0x104C03` -> `CF-6` `40`-point SPECIAL), `GSDocMitchellScript` (`0x107230` -> `3` Tag skills + up to `2` Traits), `GSDocMitchellExitTriggerScript` (`0x10722F` -> `CF-3` Hardcore toggle prompt + exterior rebuild boundary), and `7` `VCG01DocMitchell*` packages.
- **`VCG02` (`0x10A214` — Goodsprings shooting, stealth, survival & crafting tutorial):** `14` external scripts (`GSSunnySmilesScript` `0x10D9F4`, `VCG02SunnyPatrolTriggerSCRIPT` `0x10A1F1`, `VCG02GeckoDeathSCRIPT` `0x10A1F2`, `VCG01RemoveDocCarebearModeTriggerSCRIPT` `0x11E65E`, `CGTutorialSCRIPT` `0x059C86`) and `14` packages (`CheyenneShootingTutorialIdle` `0x17267E`). Exercises `CF-5` (`RCPE` campfire recipe) and `CF-3` (`H2O`/`FOD`/`SLP` intro).
- **`VMQ01` (`0x0842DD` — Goodsprings -> Primm -> Novac -> Boulder City -> Strip trail):** Pure cross-quest breadcrumb controller (`0` owned `INFO`s, `26` cross-quest `INFO` refs across Primm, Novac, Boulder City, and Tops). Depends on `PrimmDeputyScript` (`0x0E2885`), `VES01aVictorInNovacQuestSCRIPT` (`0x163C17`), `VMQ01NoteObjectSCRIPT` (`0x16189A`), `VTopsBennyIntroTriggerSCRIPT` (`0x1190A3`), and `PACK 0x110A11` (shared Red Rock travel package with `VMS20`).
- **`VMQTops` (`0x11345D` — Tops Casino confrontation & suite resolution):** Largest owned-dialogue quest in the FNV slice (`173` `DIAL`, `350` owned `INFO`s + `94` cross-quest `INFO` refs, `12` skill checks, `10` faction/reputation checks). Depends on `BennySCRIPT` (`0x11A0C0`), `TopsExteriorDoorSCRIPT` (`0x129016` holdout weapon check), `TopsCombatSCRIPT` (`0x161897`), and `24` casino floor/suite packages (`BennyGoToSuitePACKAGE` `0x1190AF`, `BennyGoToSuiteSeducedPACKAGE` `0x1672B2`).
- **`VMQHouse1` (`0x147885` — Lucky 38 & Fort bunker upgrade arc):** `0` owned `INFO`s (`43` cross-quest `INFO` refs on Mr. House / Victor / Caesar dialogue quests); coordinates `Lucky38VictorEntranceSCRIPT` (`0x1629AA`), `Lucky38VictorElevatorScript` (`0x15725D`), `Lucky38UpgradeSecuritronsSCRIPT` (`0x122808`), `SecuritronVaultExplodeQuestScript` (`0x165E64`), and `FortCaesarScript` (`0x137622`).
- **`VMQYesMan01` (`0x157321` — Independent Strip takeover & Lucky 38 mainframe swap):** `VMQYesMan01script` (`0x15827E`) has `0` `Begin` blocks (`5` quest vars mutated by `49` cross-quest `INFO` result scripts across `56` `INFO` refs) plus `16` external scripts (`NVCRMrHouseSCRIPT` `0x144627`, `Lucky38MrHouseTerminalCodeSCRIPT` `0x1746C1`, `VHouseVIPKeyCardSCRIPT` `0x176A13`) and `4` `VMQYesMan*` travel/wait packages (`0x16A220`, `0x174B6A`, `0x1763C6`, `0x17B66F`).
- **`VMQ02` (`0x129D14` — Minor-faction evaluation & Fort diplomacy):** Highest objective (`35`), external script (`40`), and cross-quest `INFO` count (`123`) in `FNV` Main `10` (spanning Boomers, Brotherhood, White Glove Society, Omertas, Khans `0x11989B`, and Fort). Triggers the Strip-exit Legion infamy reset (`CF-1`) via `VMQ02MessengerDialoguePackage` (`0x14051F`).
- **`VMQ03a` (`0x131F08` — Hoover Dam Presidential visit defense):** Explicitly calls `GetReputationThreshold` + `GetEquipped` (`CF-1` NCR `REPU` + faction armor disguise check), `SendAssaultAlarm`, and `47` crowd/sniper/vertibird packages (`VHDColonelMooreGotoPodiumPackage` `0x145EBF`, `VHDCatoHostiliusEscapePackage` `0x13F377`, `CRHDDogNCRBuddyFollowPlayerClose` `0x13B3E2`) across `32` external scripts.
- **`VMQ04` (`0x1344E8` — El Dorado Substation power routing):** Compact `3`-stage controller (`0` dialogue refs, `0` external `SCPT`s, `4` `SVSentryBot01Travel`..`04Travel` packages) using `PlaceAtMe`, `Enable`/`Disable`, and `GetSecondsPassed`.
- **`VMQ05` (`0x136166` — NCR diplomatic & minor-faction alliance spine):** `18` objectives, `69` cross-quest `INFO` refs (`9` NCR/minor-faction `REPU` checks), and `18` external scripts (`VHDColonelMooreSCRIPT` `0x145EC2`, `HVOuterRoomScript` `0x0E27E0`, `HVBunkerExplosionScript` `0x16007A`, `VHDKimballSpeechSCRIPT` `0x130C77`).

### 3.2 First `10` Side Quests (`VMS16`..`VMS29` Early Mojave Route)

| # | `QUST` (`FormID`) | `INDX` / `QOBJ` | `QUST.SCRI` (`FormID`, Vars, Blocks) | Ext `SCPT` | `DIAL` / Owned `INFO` (`+Cross`) | `INFO` Res / Skill / Repu | `PACK` | Core Systems & Key GECK Calls | Bug Ledger |
|---:|---|---:|---|---:|---|---:|---:|---|---|
| 1 | `VMS16` (`0x104EAE`) | `10` / `10` | `VMS16QuestScript` (`0x105D4E`, `15`v, `GameMode`) | `9` | `0` / `0` (`+84`) | `38` / `10` / `0` | `17` | `CF-1` (`NVRepGoodsprings` / Powder Gangers), `CF-9` (`10` Barter/Speech/Explosives/Sneak/Science checks) | `FNVS-01` |
| 2 | `VMS16b` (`0x15EC5B`) | `6` / `8` | `VMS16bQuestScript` (`0x15ED60`, `3`v, `GameMode`) | `6` | `0` / `0` (`+40`) | `13` / `3` / `0` | `8` | `CF-1` (Goodsprings Infamy + Powder Ganger Fame), `CF-9` (`3` Medicine/Barter/Speech checks) | `FNVS-02` |
| 3 | `VMS02` (`0x08D0E3`) | `13` / `10` | `VMS02QuestScript` (`0x08D0E4`, `23`v, `GameMode`) | `5` | `14` / `22` (`+35`) | `26` / `11` / `1` | `0` | `CF-1` (NCR vs Powder Ganger `REPU` + armor disguise), `CF-9` (`11` Speech/Science/Lockpick checks) | `FNVS-03` |
| 4 | `VMS33` (`0x1271EA`) | `7` / `4` | `VMS33QuestScript` (`0x128F5A`, `3`v, `GameMode`) | `5` | `6` / `11` (`+8`) | `9` / `2` / `0` | `2` | `CF-1` (Legion/NCR `REPU`), `CF-9` (`VulpesIncultaNiptonSCRIPT`, `MartinaGroesbeckScript`) | `FNVS-04` |
| 5 | `VMS44` (`0x14050D`) | `10` / `5` | `VMS44QuestScript` (`0x146F6C`, `12`v, `GameMode`) | `9` | `60` / `50` (`+1`) | `14` / `2` / `0` | `8` | `CF-7` (Searchlight radiation zone), `CF-9` (`GetItemCount`, `LoganFollowPlayer` `PACK`) | `FNVS-05` |
| 6 | `VMS53` (`0x151403`) | `1` / `4` | `VMS53SCRIPT` (`0x1513FF`, `7`v, `None`) | `5` | `0` / `0` (`+16`) | `13` / `1` / `0` | `0` | `CF-2` (Companion recruitment unlock `BooneSCRIPT`), `CF-9` (`VMS53NoteTriggerSCRIPT`) | `FNVS-06` |
| 7 | `VMS01` (`0x080664`) | `10` / `21` | `REPCONGhoulQuestScript` (`0x080776`, `35`v, `GameMode`) | `25` | `0` / `0` (`+189`) | `76` / `6` / `9` | `19` | `CF-1` (Novac `REPU` + Karma), `CF-7` (rocket basement rads), `CF-9` (`189` cross-quest `INFO`s) | `FNVS-07` |
| 8 | `VMS03` (`0x0E282D`) | `3` / `10` | `VMS03QuestSCRIPT` (`0x0E282C`, `49`v, `GameMode`) | `15` | `85` / `158` (`+19`) | `50` / `9` / `49` | `1` | `CF-1` (`49` Follower/NCR/BoS/Legion checks), `CF-2` (`ArcadeTriggerActivateArchimedesDialoguePackage`), `CF-9` | `FNVS-08` |
| 9 | `VMS20` (`0x10E908`) | `6` / `9` | `VMS20QuestScript` (`0x110FE0`, `51`v, `GameMode`) | `7` | `0` / `0` (`+55`) | `22` / `3` / `4` | `11` | `CF-1` (Khans `0x11989B` + NCR `REPU`), `CF-9` (`SetEnemy`, `BCJessupScript`, `BCLieutenantMonroeScript`) | `FNVS-09` |
| 10 | `VMS29` (`0x11F95B`) | `12` / `17` | `VMS29Script` (`0x120FB2`, `14`v, `GameMode`) | `7` | `64` / `81` (`+38`) | `67` / `6` / `2` | `6` | `CF-1` (Freeside + NCR `REPU` + `VMQNCRFailSCRIPT`), `CF-9` (`6` Medicine/Speech/Science checks) | `FNVS-10` |

#### Per-Quest Script & Package Dependencies (`FNV` Side `10`)
- **`VMS16` (`0x104EAE`) & `VMS16b` (`0x15EC5B` — Mutually exclusive Goodsprings town defense vs Powder Ganger takeover):** Zero owned `INFO`s (`84` + `40` cross-quest `INFO` refs in `VDialogueGoodsprings`). Share `GoodspringsJoeCobbScript` (`0x104C69`), `GoodspringsPowderGangerScript` (`0x105D4D`), `GSRingoScript` (`0x107814`), and `GSChetScript` (`0x161873`). First live exercise of `CF-1` `16`-state Reputation (`NVRepGoodsprings` + `NVRepPowderGanger`) and `CF-9` multi-skill allied recruitment (`Barter`, `Speech`, `Explosives`, `Sneak`, `Science`, `Medicine`).
- **`VMS02` (`0x08D0E3` — NCRCF Powder Ganger jobs & NCR storming assault):** `23` quest vars across `NCRCFChavezScript` (`0x156FA0`), `NCRCFEddieDeathScript` (`0x0AF9F1`), `PrimmCorporalHayesSCRIPT` (`0x163BEE`), `PrimmSergeantLeeScript` (`0x1587DA`), and `VMS02AmbusherScript` (`0x0A5ACF`), with `11` skill checks and bidirectional switching from Powder Ganger tasks to NCR assault support.
- **`VMS33` (`0x1271EA` — Nipton encounter -> Mojave Outpost report):** Triggered by `VulpesIncultaNiptonSCRIPT` (`0x165AF1`), bridging to `VulpesIncultaStripSCRIPT` (`0x162CAC`), `MartinaGroesbeckScript` (`0x12909F`), and `VMS33ThugScript` (`0x12909D`).
- **`VMS44` (`0x14050D` — Camp Searchlight irradiated salvage):** `9` external scripts (`CampSearchlightLoganSearchFire` `0x1482EF`, `CampSearchlightLoganSearchPolice` `0x1477A0`, `CampSearchlightLootPickups` `0x1482EE`, `LoganDeadScript` `0x1489B2`) and `8` temporary follower/search packages (`LoganFollowPlayer` `0x14BE0C`, `FollowLogan` `0x146F86`) inside a persistent exterior radiation hazard (`CF-7`).
- **`VMS53` (`0x151403` — Novac night-shift investigation & Boone recruitment):** Single-stage (`INDX` count `1`), `4`-objective state machine where `VMS53SCRIPT` (`0x1513FF`) holds `7` investigation variables (`0` `Begin` blocks) mutated by `BooneSCRIPT` (`0x0B160B`), `VNovacJeannieCrawfordScript` (`0x08E236`), `VNovacSniperVictimSCRIPT` (`0x0B7E84` sniper beret signal), and `VMS53NoteTriggerSCRIPT` (`0x151400`). Directly unlocks `Boone` recruitment into `CF-2` (`SQ_Followers` / companion perk slot).
- **`VMS01` (`0x080664` — REPCONN Test Site ghouls, Nightkin & rocket launch):** Highest cross-quest `INFO` count (`189`) in the `40`-quest audit (`21` objectives, `25` external scripts: `GhoulJasonBrightSCRIPT` `0x157F20`, `ChrisHaversamScript` `0x0CE869`, `HarlandAggroTriggerScript` `0x0CCEED`, `REPCONBasementExitSCRIPT` `0x08077E`, and `19` sandbox/launch packages `JasonBrightRocketExodusPACKAGE` `0x08D407`).
- **`VMS03` (`0x0E282D` — HELIOS One solar array & ARCHIMEDES routing):** `49` quest vars, `49` faction/reputation checks (`CF-1`), `9` Science/Repair/Speech checks (`CF-9`), `15` external scripts (`IgnacioRivasSCRIPT` `0x1694BC`, `FantasticSCRIPT` `0x164765`, `VHeliosArchimedesSCRIPT` `0x0E07CE`, `EuclidsCFinderSCRIPT` `0x168A8C`, `VHeliosARCHIMEDESEffectScript` `0x11F676`), and `ArcadeTriggerActivateArchimedesDialoguePackage` (`0x168AE3` -> `CF-2` companion trust point).
- **`VMS20` (`0x10E908` — Boulder City Khans / NCR hostage standoff):** `51` quest vars (`0` owned `INFO`s, `55` cross-quest `INFO` refs), `BCJessupScript` (`0x10E3E2`), `BCLieutenantMonroeScript` (`0x111527`), `BCTrooperHostageScript` (`0x110FE8`), `11` hostage/standoff packages (`BCGuardHostage` `0x15590D`, `PACK 0x110A11`), and direct handoff to `VMQ01` (`VES01bVictorInBoulderQuestSCRIPT` `0x163C19`).
- **`VMS29` (`0x11F95B` — Freeside Kings / NCR diplomatic standoff):** `12` stages, `17` objectives, `VFSTheKingScript` (`0x115E67`), `VFSPacerScript` (`0x1205B7`), `VFSPacerJetScript` (`0x1205B8` psychoactive container taint), `VStreetDennisCrockerSCRIPT` (`0x1622CE`), `VMQNCRFailSCRIPT` (`0x16829F`), and `6` shootout/parley packages (`VFSTheKingFacesOffNCROfferPackage` `0x156420`, `VFSNCRSquadHuntKingsPackage` `0x1558D4`).

---

## 4. GECK-to-Papyrus Translation Patterns & Phased Conversion Sequence

### 4.1 Required Converter Lowering Rules (from the `40`-Quest Dependency Closure)

| GECK Idiom in `FO3` / `FNV` Slice | Quests Using Idiom | Starfield / `CF-*` Target Pattern |
|---|---|---|
| `Begin GameMode` polling `GetStage` / `GetSecondsPassed` | `38 / 40` quests | Event-driven `OnStageSet` + bounded `StartTimer(1.0, TimerId)` only while timed sub-states are active; cancel timer on stage exit so idle quests consume zero Papyrus frames. |
| `Begin MenuMode` (`1001`..`1012`, `GetPCSleepHours`) | `CG01`, `MS10`, `VCG01` | `CF-10` chargen completion callback (`CG01`, `VCG01`) and `OnPlayerSleepStop` event (`MS10` Oasis ceremony transition). |
| Hub-quest cross-`SCRO` `QuestID.varName` mutation | `12 / 20` `FNV` quests + `MQ01`, `MQ02`, `MS06`, `MS10` | Generate `ScriptName FO4SF_<Title>_<QuestEDID> Extends Quest` with typed `Auto` properties for all `SCHR` variables; bind hub `TopicInfo` fragments via `Quest` property cast. |
| `Say` / `SayTo` / `StartRadioConversation` | `CG02`, `CG03`, `CG04`, `MQ01`, `MS01`, `MS02`, `MS10` | Emit single-phase `SCEN` actions (or `Actor.SayCustom` topic wrappers) with completion timer fallbacks so dropped lip/audio callbacks never stall `SetStage`. |
| `AddScriptPackage` / `RemoveScriptPackage` / `EvaluatePackage` | `CG03`, `MQ04`, `MQ05`, `MS01`, `MS02`, `MS09`, `MS10`, `VCG02`, `VMS16` | Bind dynamic packages through high-priority conditional `QUST` Reference Aliases (`ForceRefTo` / `Clear` + `EvaluatePackage()`). |
| `GetReputationThreshold` / `AddReputation` / `RewardKarma` | `VMQ02`, `VMQ03a`, `VMS16`, `VMS16b`, `VMS02`, `VMS01`, `VMS03`, `VMS20`, `VMS29`, `CG04`, `MQ04`, `MS11` | Lower onto `CF-1` (`FO4SF_ReputationQuest` `16`-state fame/infamy `GLOB` slots after resolving `GAP-J3-02` `13`-faction capacity + `FO4SF_PlayerKarma` `GLOB`). |
| Interior -> Exterior / Simulation `MoveTo` + `Resurrect` | `CG04`, `MQ04`, `MQ05`, `MS10`, `VCG01` | Apply `CF-10` two-phase `MoveTo` + `WaitFor3DLoad()` + `MergeOffset` landing verification (`PodLift = 0.3 m`), matching `FO4SF_NewGameQuest.psc`. |

### 4.2 Recommended Four-Wave Conversion Order

1. **Wave A — Opening Sequences & Character Creation (`CF-3`, `CF-6`, `CF-10`):**
   - `FO3`: `CG01` -> `CG02` -> `CG03` -> `CG04` (Vault 101 interior chain + Vault 101 door rebuild prompt).
   - `FNV`: `VCG01` -> `VCG02` (Doc Mitchell house + Goodsprings tutorial chain + Goodsprings edge rebuild prompt).
2. **Wave B — Self-Contained Early Town & Investigation Side Quests (`CF-1`, `CF-2`, `CF-6`, `CF-9`):**
   - `FO3`: `MS02`, `MS04`, `MS05`, `MS08`, `MS09`, `MS11`, `MS03` (exercises `69`-check dialogue list UI, `CF-7` rad checks, and Megaton world-state branching).
   - `FNV`: `VMS16` + `VMS16b`, `VMS33`, `VMS44`, `VMS53` (exercises `16`-state `REPU`, Searchlight rads, and Boone `CF-2` companion unlock).
3. **Wave C — Breadcrumb Main Spines & Multi-Hub Route Side Quests (`CF-1`, `CF-5`, `CF-9`):**
   - `FO3`: `MQ01` -> `MQ02` -> `MQ03`, `MS01`, `MS06`.
   - `FNV`: `VMQ01` -> `VMQTops`, `VMS02`, `VMS20`, `VMS01`, `VMS29` (exercises `VDialogue*` cross-quest `SCRO` binding at `189`-`INFO` scale).
4. **Wave D — Simulation, Escort Setpieces & Multi-Faction Matrix Controllers (`CF-1`, `CF-7`, `CF-8`):**
   - `FO3`: `MQ04` (Tranquility Lane simulation stash/restore), `MQ05` (`58`-script Project Purity / Taft Tunnels escort), `MQ06` (Citadel + PA training gate), `MS10` (`MenuMode` sleep ceremony).
   - `FNV`: `VMS03` (`49` faction checks + ARCHIMEDES orbital/plant controller), `VMQHouse1`, `VMQYesMan01`, `VMQ02` (`35`-objective minor-faction matrix), `VMQ04`, `VMQ05`, `VMQ03a` (`47`-package Hoover Dam speech defense).
