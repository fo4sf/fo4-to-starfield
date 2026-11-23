# Round 11 `D4` & `A2.1`: Sanctuary Workshop Bench Cleanup and Open-Menu Sturges Guard

> **Scope & Truth Status:** `OFFLINE VERIFIED ONLY — UNPROVEN IN GAME`. Binary plugin records, Papyrus compilation (`PapyrusCompiler.exe`), `WorkshopCore selftest` (including `10` negative tamper controls), real `Starfield.esm` build/check, and cross-OS unit tests all pass offline. No real settlement building is added in this round (next mission).

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

1. **Clean Sanctuary Workshop Bench (`FO4SFWorkshop.esm` `0x000848..0x000849`):**
   - `KYWD 0x000848` `FO4SF_WorkshopCategorySanctuary`: `FULL = "Sanctuary"`, `TNAM = 9` (`RecipeFilter`). Zero Starfield `COBJ` records reference it.
   - `ACTI 0x000849` `FO4SF_SanctuaryWorkshopBench`: `FULL = "Sanctuary Hills Workshop"` (replaces bare `"WORKSHOP"` in both the prompt and `sOutpostName`), `MODL = fo4core\setdressing\garage\workbenchgarage01.nif` (same converted Fallout 4 red workshop mesh), `ActivationAngle = 360`, `PRPS OutpostBuildAreaRadius = 250.0 m`, `KWDA = [MustPersist (0x04AF68), WorkshopKeyword (0x054BA7), FO4SF_WorkshopCategorySanctuary (0x000848)]`. All `7` Starfield `OutpostCategory*` keywords are absent, so **0 of 261** Starfield outpost recipes match.
2. **Runtime Bench Swap (`FO4SF_Sanctuary01Quest.psc` `TryBindBench`):**
   - Once `FO4TerrainCore.esm:0x005C50` is 3D-loaded and `FO4SFWorkshop.esm` is installed, `TryBindBench` spawns persistent `sanctuaryBenchOverride` (`FO4SFWorkshop.esm:0x000849`) at `0x005C50`'s exact position and rotation (`MoveTo(..., abMatchRotation=True)`), disables `0x005C50`, binds `boundBench` + Alias `0` (`SanctuaryWorkbench`) to the clean bench, keeps the existing `sanctuary01 bench_bound ref=<ref> loaded=<bool>` log line unchanged for backwards compatibility, and logs `sanctuary01 clean_bench_swap active=true ref=<ref>`.
   - On `OnPlayerLoadGame`, `sanctuaryBenchOverride` is reused without double-spawning while keeping `0x005C50` disabled. If `FO4SFWorkshop.esm` is not installed, `TryBindBench` falls back to `0x005C50` (`sanctuary01 clean_bench_swap active=false ref=<ref>`).
3. **Scoped Mars/Sol Location & Star Display-Name Overrides (`FO4SFWorkshop.esm`):**
   - Deep-copies only `Starfield.esm`'s `LCTN 0x0001B736` (`SSol_PMars_Surface` -> `"Commonwealth"`), `LCTN 0x0001B735` (`SSol_PMars` -> `"Commonwealth"`), `LCTN 0x00061527` (`SSol` -> `"Massachusetts"`), and `STDT 0x0005E5CB` (`SolStar` -> both `FULL` via `FullNameComponent` and `ANAM` = `"Massachusetts"`).
   - **Explicit boundary (`PNDT 0x0003F59A` untouched):** `FO4SFWorkshop.esm` NEVER overrides `Planet` (`PNDT 0x0003F59A` belongs to `FO4TerrainCore_Mars.esm`, where `R11-W4` handles `D7` weather). `WorkshopCore check` enforces `mod.Planets.Count == 0` and rejects any foreign override outside the 4 allowlisted `LCTN`/`STDT` records.
   - **Cross-slice note for `R11-W4` (`FO4TerrainCore_Mars.esm`):** If `WorkshopMenu`'s `sOutpostLocation` reads `PNDT.FULL` rather than `LCTN.FULL` for the planet portion of `"MARS, SOL"`, setting `PNDT 0x0003F59A` `FullNameComponent` + `ANAM` to `"Commonwealth"` in `FO4TerrainCore_Mars.esm` covers both the workshop footer and the `D7` planet display without plugin conflict.

### 2.1 Offline-Provable vs In-Game-Only (`R15`)

| Claim | Proven Offline | Requires Game Verification |
|---|---|---|
| `0x000849` carries `WorkshopKeyword` + `FO4SF_WorkshopCategorySanctuary` and `0` Starfield `OutpostCategory*` keywords (`0/261` Starfield `COBJ` match) | Yes (`WorkshopCore check` + `Starfield.esm` scan + tamper control `#9`) | How `WorkshopMenu` renders a workshop whose only `RecipeFilter` category has `0` buildable `COBJ`s (empty panel vs tab bar hidden) |
| `0x000849` uses exact FO4 mesh `fo4core\setdressing\garage\workbenchgarage01.nif` and `FULL = "Sanctuary Hills Workshop"` | Yes (binary readback against real `Starfield.esm`) | Prompt text (`SANCTUARY HILLS WORKSHOP / BUILD [E]`) and `sOutpostName` in `WorkshopMenu` footer |
| `LCTN 0x01B736`, `0x01B735`, `0x061527` and `STDT 0x05E5CB` (`FULL` + `ANAM`) carry `"Commonwealth"` / `"Massachusetts"` with `0` `PNDT` overrides | Yes (raw binary subrecord inspection + tamper control `#10`) | Whether `sOutpostLocation` reads `LCTN` + `STDT` (now `"COMMONWEALTH, MASSACHUSETTS"`) or `PNDT.FULL` + `STDT.FULL` |

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
1. **Multi-layer open-menu guard (`IsAnyMenuOrWorkshopOpen()`):**
   - Registers `RegisterForMenuOpenCloseEvent` (`RegisterMenuGuards()`, called in `StartQuestInstance` and inside `TryBindBench`, which also runs on every active `OnPlayerLoadGame`) for `WorkshopMenu`, `WorkshopBuilderMenu`, `WorkshopQuickMenu`, `Workshop_BlueprintMenu`, `DialogueMenu`, `MessageBoxMenu`, `ContainerMenu`, `BarterMenu`, `TerminalMenu`, `BookMenu`, `DataMenu`, `InventoryMenu`, `PauseMenu`, `Console`, and `FO4SF_PipboyMenu`.
   - Tracks `openMenuCount`, `workshopMenuOpen` (`OnMenuOpenCloseEvent`), and `workshopModeActive` (`OnWorkshopMode(akSender, aStart)`), resetting `sturgesNearSec = 0.0` immediately on any menu open or workshop entry and resetting flags cleanly on `OnPlayerLoadGame`.
   - Also checks native Starfield Papyrus globals `Utility.IsGameMenuPaused()`, `Game.IsPlayerInDialogue()`, `!Game.IsMovementControlsEnabled()`, and `!Game.IsActivateControlsEnabled()`.
   - Enforced at the top of **both** `CheckSturgesTalkFallback` (pauses and resets `sturgesNearSec = 0.0`; re-checked again immediately before `RunSturgesTalk()`) and `RunSturgesTalk()` itself.
2. **`S9` Sturges Arrival Gate (`IsSturgesReadyForSanctuary()`, `OnSturgesArrivedFromConcord()`):**
   - Stage `100` of `FO4SF_Sanctuary01` no longer enables or teleports Sturges (`0x000A01`) onto the Sanctuary workbench in normal play (`FO4SF_TestModeEnabled == 0`).
   - Sturges stays `InitiallyDisabled` until `S9` brings Preston's group from Concord to Sanctuary and calls `OnSturgesArrivedFromConcord()` (or enables Sturges). Even after arrival, normal play binds dialogue and spawns his `0x000A0E` talk proxy at his actual standing position without teleporting him onto the workbench.
