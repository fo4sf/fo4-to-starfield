# Round 11 `D4` & `A2.1`: Sanctuary Workshop Bench Cleanup and Open-Menu Sturges Guard

> **Scope & Truth Status:** `OFFLINE VERIFIED ONLY — UNPROVEN IN GAME`. Binary plugin records, Papyrus compilation (`PapyrusCompiler.exe`), `WorkshopCore selftest` (including `11` negative tamper controls), real `Starfield.esm` build/check, and cross-OS unit tests all pass offline. No real settlement building is added in this round (next mission).

---

## 1. `D4`: What Starfield's Sanctuary Workshop List & Footer Draw From

Observed in `2g` still `11-workshop-opens-no-box-starfield-builder.png` and verified directly against the binary records of `FO4TerrainCore.esm`, `FO4TerrainCore_Mars.esm`, `Starfield.esm`, and `Starfield - Interface.ba2`:

### 1.1 Buildable List (`Industrial Workbench`, `Cooking Station`, `Pharmaceutical Lab`, `Weapon Workbench`, `Spacesuit Workbench`, `Research Lab` + `Iron`/`Aluminum` costs)
- The pre-placed Sanctuary Hills workbench (`FO4TerrainCore.esm` `REFR 0x01005C50`) instantiates base `ACTI 0x010A2ECD` (`FO4Core_wkshp_0c1aeb_fallout4`, `FULL = "Workshop"`, `MODL = fo4core\setdressing\garage\workbenchgarage01.nif`, `PRPS OutpostBuildAreaRadius 0x063FC5 = 250.0 m`).
- `ACTI 0x010A2ECD`'s `KWDA` copies `WorkshopKeyword` (`0x00054BA7`) plus **7 Starfield `OutpostCategory*` (`TNAM = 9` / `RecipeFilter`) keywords** from `OutpostPlayerHouseActivator` (`0x00024DC7`):
  - `0x002CFDE6` `OutpostCategoryCrafting` — matches the **6** Starfield `COBJ` records shown in the `CRAFTING` tab (`0x2E2F2C` Industrial Workbench, `0x2CFDE5` Cooking Station, `0x2CFDE4` Pharmaceutical Lab, `0x2CFDE3` Weapon Workbench, `0x2CFDE2` Spacesuit Workbench, `0x2CFDE1` Research Lab), all `6` carrying `BNAM = 0x002CFDE6`, `FNAM = [0x002CFDE6]`, `0` conditions, and Starfield `IRES` components (`ResInorgCommonIron` `0x0057C7`, `ResInorgCommonAluminum` `0x0057D6`).
  - `0x002BE3B5` `OutpostCategoryFurniture`, `0x00293ADF` `OutpostCategoryDecorations`, `0x0002BD59` `OutpostCategoryTestAssets`, `0x00397027` `OutpostCategoryDisplays`, `0x0028F890` `OutpostCategoryPower_InteriorLights`, `0x000E6A3E` `OutpostCategoryMiscInterior` — **261** Starfield `COBJ` records in total.
- As confirmed in-game by `docs/research/build-pieces.md` (PC run `#740`, 11 Nov), Starfield's `WorkshopMenu` lists only `COBJ` records whose `BNAM` (`WorkbenchKeyword`) is present on the activated Workshop `ACTI`'s `KWDA`.

### 1.2 Footer (`WORKSHOP` / `MARS, SOL`)
- `interface/workshopmenu.swf` (`FooterContainer_mc` / `FooterInfo_26`) binds two `WorkshopStatusData` strings:
  - `sOutpostName` (`"WORKSHOP"`): read from the activated Workshop `ACTI`'s `FULL` string (`FO4TerrainCore.esm:0x010A2ECD` `FULL = "Workshop"`).
  - `sOutpostLocation` (`"MARS, SOL"`): read from the worldspace's Mars/Sol location and planetary registration:
    - `LCTN` parent chain: `FO4Core_Commonwealth` (`WRLD 0x01000803`) -> `XLCN 0x01000802` (`FO4Core_CommonwealthLocation`) -> `PNAM = Starfield.esm:0x0001B736` (`SSol_PMars_Surface`, `FULL = "Mars"`) -> `PNAM = Starfield.esm:0x0001B735` (`SSol_PMars`, `FULL = "Mars"`, `LocTypePlanet`) -> `PNAM = Starfield.esm:0x00061527` (`SSol`, `FULL = "Sol"`, `LocTypeStarSystem`).
    - Planet & Star records: `FO4TerrainCore_Mars.esm` overrides `PNDT 0x0003F59A` (`MarsPlanetData`, `FULL = "Mars"`, `ANAM = "Mars"`, `GNAM = (0, 0, 4)`) inside `Starfield.esm:0x0005E5CB` (`STDT SolStar`, `FULL = "Sol"`, `ANAM = "SOL"`).

---

## 2. `D4`: Smallest Clean Change Implemented (Zero Real Building Yet)

Implemented strictly inside `FO4SFWorkshop.esm` (`dotnet/WorkshopCore/Program.cs`, already loaded in the 13-plugin player bundle with masters `[Starfield.esm, FO4SFCoreValues.esm]` and no `FO4TerrainCore.esm` master) and `scripts/mission/FO4SF_Sanctuary01Quest.psc`:

1. **Clean Sanctuary Workshop Bench & Runtime Switch (`FO4SFWorkshop.esm` `0x000848..0x00084A`):**
   - `KYWD 0x000848` `FO4SF_WorkshopCategorySanctuary`: `FULL = "Sanctuary"`, `TNAM = 9` (`RecipeFilter`). Zero Starfield `COBJ` records reference it.
   - `ACTI 0x000849` `FO4SF_SanctuaryWorkshopBench`: `FULL = "Sanctuary Hills Workshop"` (replaces bare `"WORKSHOP"` in both the prompt and `sOutpostName`), `MODL = fo4core\setdressing\garage\workbenchgarage01.nif` (same converted Fallout 4 red workshop mesh), `ActivationAngle = 360`, `PRPS OutpostBuildAreaRadius = 250.0 m`, `KWDA = [MustPersist (0x04AF68), WorkshopKeyword (0x054BA7), FO4SF_WorkshopCategorySanctuary (0x000848)]`. All `7` Starfield `OutpostCategory*` keywords are absent, so **0 of 261** Starfield outpost recipes match.
   - `GLOB 0x00084A` `FO4SF_SanctuaryCleanBenchSwap`: **default `0.0` (OFF in `candidate-2g-fix`)**. Paired with `bool Property EnableCleanBenchSwap = False Auto` on `FO4SF_Sanctuary01Quest.psc` so `04005C50` stays active and bound by default until the clean bench swap is explicitly opted in for its dedicated probe step (`0B00084A == 1`).
2. **Gated Runtime Bench Swap & `3.5 s` Self-Heal (`FO4SF_Sanctuary01Quest.psc` `TryBindBench`, `RestoreCoreBench`, `OnTimer(3)`):**
   - **Default (`0B00084A == 0`, `EnableCleanBenchSwap == False`):** `TryBindBench` leaves `04005C50` enabled and bound (`sanctuary01 bench_bound ref=<ref> loaded=<bool>` + `sanctuary01 clean_bench_swap active=false ref=<ref>`). If a loaded save previously had `sanctuaryBenchOverride` active while the switch is now `0`, `TryBindBench` / `RestoreCoreBench` automatically disables `sanctuaryBenchOverride`, re-enables `04005C50`, and re-binds `boundBench` + Alias `0` to `04005C50`.
   - **Opt-In Probe (`0B00084A == 1`):** Once `04005C50` is 3D-loaded and `FO4SFWorkshop.esm` is installed, `TryBindBench` (also triggered within `1 s` on `OnTimer(1)` if flipped live) spawns persistent `sanctuaryBenchOverride` (`FO4SFWorkshop.esm:0x000849`) at `04005C50`'s exact position/rotation (`MoveTo(..., abMatchRotation=True)`), disables `04005C50`, binds `boundBench` + Alias `0`, preserves `sanctuary01 bench_bound ref=<ref> loaded=<bool>`, and logs `sanctuary01 clean_bench_swap active=true ref=<ref>`.
   - **`3.5 s` Self-Heal (`Timer 3`):** Activating `sanctuaryBenchOverride` starts Timer `3` (`3.5 s`). If `OnWorkshopMode(True)` or a workshop menu (`WorkshopMenu`, `WorkshopBuilderMenu`, `WorkshopQuickMenu`, `Workshop_BlueprintMenu`) opens within `3.5 s`, Timer `3` cancels cleanly. If workshop mode/menu does not open within `3.5 s`, `OnTimer(3)` logs `sanctuary01 clean_bench_swap self_heal reason=no_workshop_menu`, disables `sanctuaryBenchOverride`, re-enables `04005C50`, and re-binds `boundBench` + Alias `0` back to `04005C50`.
3. **Scoped Mars/Sol Location & Star Display-Name Overrides (`FO4SFWorkshop.esm`):**
   - Deep-copies only `Starfield.esm`'s `LCTN 0x0001B736` (`SSol_PMars_Surface` -> `"Commonwealth"`), `LCTN 0x0001B735` (`SSol_PMars` -> `"Commonwealth"`), `LCTN 0x00061527` (`SSol` -> `"Massachusetts"`), and `STDT 0x0005E5CB` (`SolStar` -> both `FULL` via `FullNameComponent` and `ANAM` = `"Massachusetts"`).
   - **Explicit boundary (`PNDT 0x0003F59A` untouched):** `FO4SFWorkshop.esm` NEVER overrides `Planet` (`PNDT 0x0003F59A` belongs to `FO4TerrainCore_Mars.esm`, where `R11-W4` handles `D7` weather). `WorkshopCore check` enforces `mod.Planets.Count == 0` and rejects any foreign override outside the 4 allowlisted `LCTN`/`STDT` records.
   - **Cross-slice note for `R11-W4` (`FO4TerrainCore_Mars.esm`):** If `WorkshopMenu`'s `sOutpostLocation` reads `PNDT.FULL` rather than `LCTN.FULL` for the planet portion of `"MARS, SOL"`, setting `PNDT 0x0003F59A` `FullNameComponent` + `ANAM` to `"Commonwealth"` in `FO4TerrainCore_Mars.esm` covers both the workshop footer and the `D7` planet display without plugin conflict.

### 2.1 Offline-Provable vs In-Game-Only (`R15`)

| Claim | Proven Offline | Requires Game Verification |
|---|---|---|
| `0x000849` carries `WorkshopKeyword` + `FO4SF_WorkshopCategorySanctuary` and `0` Starfield `OutpostCategory*` keywords (`0/261` Starfield `COBJ` match) | Yes (`WorkshopCore check` + `Starfield.esm` scan + tamper control `#9`) | How `WorkshopMenu` renders a workshop whose only `RecipeFilter` category has `0` buildable `COBJ`s (empty panel vs tab bar hidden) |
| `0x000849` uses exact FO4 mesh `fo4core\setdressing\garage\workbenchgarage01.nif` and `FULL = "Sanctuary Hills Workshop"` | Yes (binary readback against real `Starfield.esm`) | Prompt text (`SANCTUARY HILLS WORKSHOP / BUILD [E]`) and `sOutpostName` in `WorkshopMenu` footer |
| `LCTN`/`STDT`/`PNDT` overrides in `FO4SFWorkshop.esm`: `0` (`E6` fix removed localized `LCTN 0x01B735` / `STDT 0x05E5CB` overrides); `PNDT 0x0003F59A` stays in `FO4SFCoreValues.esm`, while footer `"MARS, SOL"` stays until `#858`. | Yes (`fix4` / `WS0a` `WorkshopCore check` + tamper controls `#14`–`#17`: `42` own + `2` unlocalized `FLST` overrides `0x058606`/`0x1A5507` = `44` major records; `0x000858` opening-toast switch default `0.0`; `0x000843` C.A.M.P. kit TestMode-gated `until owner Q6`) | `sOutpostLocation` reads `FO4SFCoreValues` / `#858` world location (`"COMMONWEALTH, MASSACHUSETTS"` once `#858` lands) |

---

## 3. `A2.1`: `CheckSturgesTalkFallback` Open-Menu Suppression, `run3` Explanation, and `S9` Gate

### 3.1 Why `CheckSturgesTalkFallback` Did Not Fire in `2g` `run3` (50 s Window)
Observed facts from `run3/fo4sf_mission.0.log`:
- At `14:03:30` (`rt=542.54`) and `14:05:09` (`rt=641.42`), the player stood stationary at `(-2329.241, -1418.718, 112.081)` — `2.25 m` from Sturges's target `(-2327.0, -1418.5, 112.1)` (`<= 3.5 m` `TalkFallbackRadius`).
- At `14:03:32`, `OnActivate` + `OnWorkshopMode(True)` advanced `FO4SF_Sanctuary01` to stage `100` (`talkBoxOpen = False`, `benchMenuOpen = False`).
- At `14:03:33` (`rt=545.58..545.96`), `KeepSturges` logged `sanctuary01 sturges enabled stage=100`, `keeper sturges placed held=true`, and `sturges talk_proxy spawned`. `sturges enabled` did not repeat on later ticks, proving `st.IsDisabled()` became `False`.
- No `sanctuary01 talk_fallback` line ever fired during the 20 s inside `WorkshopMenu` or the 30 s after closing it.
- **Honest conclusion:** Because the `2g` script did not log `stActor.Is3DLoaded()` or `player.GetDistance(stActor)` on timer ticks, the `run3` logs alone cannot distinguish whether `!stActor.Is3DLoaded()` stayed true after same-tick `EnableNoWait(False)` + `MoveTo`, or whether `MoveTo` placed/pushed Sturges past `3.5 m` (inside `KeepSturges`'s `25 m` `625.0` drift tolerance) across the carport wall. What IS proven is that `CheckSturgesTalkFallback` had **no open-menu guard** and relied on incidental conditions rather than a real lock.

### 3.2 Fix Implemented in `scripts/mission/FO4SF_Sanctuary01Quest.psc`
1. **Multi-layer open-menu guard (`IsAnyMenuOrWorkshopOpen()`, zero `openMenuCount`):**
   - Registers `RegisterForMenuOpenCloseEvent` (`RegisterMenuGuards()`, called in `StartQuestInstance` and inside `TryBindBench`, which also runs on every active `OnPlayerLoadGame`) for `WorkshopMenu`, `WorkshopBuilderMenu`, `WorkshopQuickMenu`, `Workshop_BlueprintMenu`, `DialogueMenu`, `MessageBoxMenu`, `ContainerMenu`, `BarterMenu`, `TerminalMenu`, `BookMenu`, `DataMenu`, `InventoryMenu`, `PauseMenu`, `Console`, and `FO4SF_PipboyMenu`.
   - Removes `openMenuCount` completely so a missed close event can never leave a counter stuck above `0`; relies strictly on explicit boolean workshop/dialog flags (`workshopModeActive`, `workshopMenuOpen`, `talkBoxOpen`, `benchMenuOpen`, with `OnWorkshopMode(False)` also clearing `workshopMenuOpen`) plus native Starfield Papyrus globals `Utility.IsGameMenuPaused()`, `Game.IsPlayerInDialogue()`, `!Game.IsMovementControlsEnabled()`, and `!Game.IsActivateControlsEnabled()`.
   - Enforced at the top of **both** `CheckSturgesTalkFallback` (pauses and resets `sturgesNearSec = 0.0`; re-checked again immediately before `RunSturgesTalk()`) and `RunSturgesTalk()` itself.
2. **`S9` Sturges Arrival Gate & Unblocked Stage-100 Open-Mode Path (`IsSturgesReadyForSanctuary()`, `IsSturgesDeadOrMissing()`, `OnSturgesArrivedFromConcord()`):**
   - Stage `100` of `FO4SF_Sanctuary01` no longer enables or teleports Sturges (`0x000A01`) onto the Sanctuary workbench in normal play (`FO4SF_TestModeEnabled == 0`).
   - `IsSturgesDeadOrMissing()` treats `!IsSturgesReadyForSanctuary()` ("not yet arrived from `S9`", i.e. disabled in `candidate-2g-fix`) identically to missing/dead: `ApplyStage(100)` NEVER displays objective `50` (`"Talk to Sturges"`) while Sturges is disabled, and instead advances cleanly through the Open-Mode workbench path (`stage 1000` -> `1500`, preserving honest `sanctuary01 bench_activated=true ref=<ref> complete=<bool>` logging).
   - Once `S9` brings Preston's group from Concord to Sanctuary and calls `OnSturgesArrivedFromConcord()` (or enables Sturges), `IsSturgesReadyForSanctuary()` returns `True` and normal play binds dialogue + spawns his `0x000A0E` talk proxy at his standing position without teleporting him onto the workbench.
