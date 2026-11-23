# Pip-Boy Screen Fixes (`C4` / `D5` / `A2.6`), Starfield Watch Hide (`D7b`), Clear Commonwealth Weather (`D7a`), & Native Hygiene (`R6`)

> **Whole-scope:** Titles: Fallout 4 -> all 7 Fallout titles (`FO4`, `FO3`, `FNV`, `FO1`, `FO2`, `Tactics`, `FO76`) | Modes: Story & Warfare (+ Survival hardcore layer) | Track: **Track 1 (playable path)** — `FO4SFPipboyMenu.dll` & `FO4SFCoreValues.esm`
> **Playable status:**
> - **Round 10 (`C4-1..C4-3` & `R6`):** `ran in game` — **PASSED** on `candidate-2g` (22 Nov, 32 min, 3 launches, 0 crashes: `step=shell_backdrop ok=1`, `hp=205/205 ap=100/110`, map footer `10.23.2287`, `step=quest_cache_build` once).
> - **Round 11 (`D5` Parts 1 & 2, `D7` (a) & (b), `A2.6`):** `pushed, not run` — built locally with MSVC x64 (`build.ps1`) and .NET (`CoreValues.csproj`) and verified by offline regression tests; **not yet verified in game** until the next PC candidate run captures fresh stills and `FO4SFPipboyMenu.log`.

---

## 1. Round 10 (`candidate-2g` — `ran in game`, PASSED)

| ID | Observed in `candidate-2f` | Fix shipped in `main` | `candidate-2g` result (`ran in game`) | Activation / rollback |
| --- | --- | --- | --- | --- |
| **`C4-1`** | Transparent Pip-Boy stage let Concord / Preston bleed through STAT and MAP margins. | `ApplyShellBackdrop` draws opaque `#020804` outer matte (`alpha=0.92`) + `#041409` CRT fill (`alpha=0.97`) + `#185228` bezel on `root.graphics` (fallback `Menu_mc.graphics`). | **PASSED** (`step=shell_backdrop ok=1 target=root_graphics`; solid dark CRT backing on stills 12 & 13). | `ShellBackdrop=1` (rollback: `ShellBackdrop=0`). |
| **`C4-2`** | STAT footer showed `HP 0/0` and `AP --/--` under `PopulateInCall=0`. | `ShellVitalsFill=1` in staged/shipped INI (C++ fallback `0`) populates live HP/AP/S.P.E.C.I.A.L./Date on `kShow`, page/tab switch, and partial updates while keeping `PopulatePipboyInfoObj` non-mutating when `PopulateInCall=0`. | **PASSED** (`step=shell_vitals`, `hp=205/205 ap=100/110`, real `HP` & `AP` shown on still 12). | `ShellVitalsFill=1` (rollback: `ShellVitalsFill=0` restores exact `2f` path). |
| **`C4-3`** | MAP footer clipped `10.23.2287` to `10.23.228`. | `ApplyBottomBarDateFix` sets `Date_tf.wordWrap = false`, `width = 194.0`, `autoSize = "left"`, and widens `Time_tf` to `156.0`. | **PASSED** (`step=shell_date_fix`, `old_w=150.0 new_w=164.0`; full `10.23.2287` visible on still 13). | Active on DATA/MAP Frame 6 `Date_tf`. |
| **`C4-4`** | Closed-Pip-Boy `Tab` opened Starfield's `DataMenu`. | Opt-in `SuppressDataMenu` (hide-only `kHide`, `step=data_menu_suppress`) and `TabOpensPipboy` (500 ms `kBlockingMenuCooldownMs` + `g_nonDataBlockingOpen` guard, `step=tab_key`). | Shipped OFF by default (`0`). | Opt-in (`SuppressDataMenu=0`, `TabOpensPipboy=0`). |
| **`R6`** | `0x800..0xBFF` quest scan repeated every `500 ms`; map index vectors unsynchronized. | One-time `PostDataLoad` `g_cachedQuestForms` (`step=quest_cache_build`) + leaf `g_pushedIndicesLock` mutex in `pipboy_map.cpp`. | **PASSED** (`step=quest_cache_build` logged once). | Always active. |

---

## 2. Round 11 Fixes (`pushed, not run` — Offline Verified Only)

| ID | Observed in `candidate-2g` | Binary Root Cause | Fix in Round 11 (`R11-W4`) | Activation / Rollback |
| --- | --- | --- | --- | --- |
| **`D5` Part 1** | `"PLAYER"` (`StatusTab_mc.Name_tf`) drew directly over `"RADAWAY (0)"` (`still 12`). | In `PipboyMenu.swf` (`Sprite 79`), `ButtonHintBar_mc` sits at `y=575.0` while `Pipboy_StatsPage.swf` (`Sprite 176 StatusTab`) places `Name_tf` at `y=580.0` (`5 px` vertical collision). `BottomBar_mc` occupies `y=629.8..668.0` inside the `708.0` CRT bezel. | `ApplyShellHintBarLayout` moves `Menu_mc.ButtonHintBar_mc.y` to **`672.0`** (just below `BottomBar_mc`, well inside the `708.0` CRT bezel) once per movie (`g_hintBarDoneMovie`), leaving `Name_tf` completely clear in the `76 px` band between `DMG/DR` (`y=553`) and `BottomBar_mc` (`y=629.8`). | Active on `FO4SF_Fo4Shell` (`step=shell_hintbar_layout`). |
| **`D5` Part 2** | Controller glyphs `(A)`, `(X)`, `(Y)`, `[LT]`, `[RT]` showed while playing on keyboard + mouse (`still 12`). | `PipboyMenu.swf` initializes `_uiPlatform = PLATFORM_INVALID` (`0xFFFFFFFF`) because Starfield never invokes `SetPlatform`; `BSButtonHint` and `Pipboy_Header` (`Sprite 51`: `LeftTriggerButton_mc`, `RightTriggerButton_mc`) fall back to Xbox controller icons. | `ApplyShellPlatform` invokes `Menu_mc.SetPlatform(0u, false)` (`PLATFORM_PC_KB_MOUSE = 0`), forwards `SetPlatform(0u, false)` to `ButtonHintBar_mc` and `Header_mc`, and explicitly hides `Header_mc.LeftTriggerButton_mc` and `Header_mc.RightTriggerButton_mc` (`visible = false`, `alpha = 0.0`). Guarded once per movie (`g_platformDoneMovie`) with a page-switch refresh on `onNewPage` so newly loaded page SWFs (`INV`/`DATA`/`MAP`/`RADIO`) also receive `PLATFORM_PC_KB_MOUSE = 0`. | Active on `FO4SF_Fo4Shell` (`step=shell_platform`). |
| **`D7` (a)** | Heavy orange Mars dust storm hung over the Commonwealth for all 32 minutes (`every still`). | **Two binary causes in `Starfield.esm` + `FO4TerrainCore.esm` + `FO4TerrainCore_Mars.esm`:** (1) `FO4Core_Commonwealth` (`WRLD 0x01000803`) has no `CNAM` (Worldspace Climate) and points `BNAM` (Biome) to `Starfield.esm` `BIOM 0x002A3777` (`DesertRockyNoLifeMars`), whose `ENAM` Climate is `CLMT 0x00310DB1` (`ClimateUniqueCydonia`), whose `WSLT` Weather Settings List is 100% Mars/Cydonia dusty orange/sandstorm weather (`0x00310DB8` 50%, `0x0031FC49` 40%, `0x0031FC4A` 10% sandstorm; secondary Mars biome `0x00084E12` uses `CLMT 0x002EDEA5` `ClimateUniqueCydoniaFrozen`). (2) `MarsPlanetData` (`PNDT 0x0003F59A`, retained by `FO4TerrainCore_Mars.esm`) embeds `ATMO 0x0000C9D2` (`ATMO_Mars`), which drives Mars's rusty-orange atmospheric scattering. | `dotnet/CoreValues/Program.cs` (`FO4SFCoreValues.esm`, rebuilt automatically by `make_core_bundle.py build` in the exact 13-plugin player bundle with zero extra masters or plugins) validates the exact `EditorID`s of all five `Starfield.esm` source records (`ClimateUniqueNewAtlantis`, `ClimateUniqueCydonia`, `ClimateUniqueCydoniaFrozen`, `ATMO_Mars`, `ATMO_Jemison` — refusing the build on any mismatch), copies `Weathers` and `WeatherSettings` directly from `CLMT 0x0024E982` (`ClimateUniqueNewAtlantis`, `DeepCopy`) onto `CLMT 0x00310DB1` (`ClimateUniqueCydonia`) and `CLMT 0x002EDEA5` (`ClimateUniqueCydoniaFrozen`), and overrides `ATMO 0x0000C9D2` (`ATMO_Mars`) from `ATMO 0x0000C010` (`ATMO_Jemison`) for clear blue-sky Earth-like Commonwealth daylight. **Known side effect:** this Mars-wide override affects all Mars locations (including Cydonia) while active. | **`--commonwealth-weather 1`** (default ON in `CoreValues` and `make_core_values.py`; only emitted when `Starfield.esm` contains the Mars/NewAtlantis records, so synthetic fixtures stay byte-identical). One-line rollback: `--commonwealth-weather 0`. |
| **`D7` (b)** | Starfield's bottom-left wrist watch read `"MARS"` with `O2` and `CO2` gauges. | `hudmenu.swf` places `BottomLeftGroup_mc` (root depth 2, class `BottomLeftGroup` in `playerhudcomponents.swf`) hosting `WatchOutline_mc`, `WatchPointerOutline_mc`, `WatchIconsWidget_mc`, `O2CO2_mc`, `O2CO2thin_mc`, `locationNameBase_mc`, and planetary readout clips. | Added `HideStarfieldWatch` INI setting (C++ fallback `0`; emitted as **`HideStarfieldWatch=1`** in shipped `FO4SFPipboyMenu.ini` and `make_pipboy_stage_ini.py`). Non-fatal `TryInitHudWatchIds` resolves watch-hide channel IDs without ever refusing `FO4SFPipboyMenu.dll` at Stage 2 (on failure, logs `step=hud_watch_hide_init ok=0 reason=channel_ids_unavailable` and disables only watch-hide). In `OnMovieCreated`, `ApplyHudWatchHide` uses isolated `HudRootOf(a_menu)` (never mutating `g_checkedMovie` or `g_channelOff`) to hide `root.BottomLeftGroup_mc` (`visible=false`, `alpha=0.0`, `x=-10000.0`) and its 17 watch/planet/O2/CO2 child clips while leaving `RightMeters_mc` (Health/Ammo), `CenterGroup_mc` (Crosshair), `RolloverWidget_mc` (`[E]` prompts), `TopCenterGroup_mc`, and `EnemyHealthHolder_mc` untouched. If `no_root` or `missing_bottom_left` occurs early, `g_hudWatchTryCount` + `g_hudWatchRetryPending` retry cleanly across `MenuOpenCloseEvent` transitions (`HudWatchMenuEventSink`) and the main-thread UI poll hook (`RetryHudWatchHideMainThread`) until hidden or `HUDMenu` unloads, logging `try=<n>` on the attempt that succeeds. `LoadingMenu` and `HUDMenu` close reset the watch-hide state so cold reloads always re-hide cleanly. | **`HideStarfieldWatch=1`** ON in player bundle INI. **One-line rollback:** `HideStarfieldWatch=0` (no DLL rebuild). |
| **`A2.6`** | `FillPipboyDataObj` cleared AS3 lists before `CreateObject`, rebuilt static lists on every partial update, had only run on STAT/MAP, and `ShellUpdate` re-ran `ApplyShellBackdrop` + `ApplyBottomBarDateFix` `ReadPath` on every `500 ms` update. | Direct `ClearAs3ArrayInPlace` -> `CreateObject` loops; unguarded `ShellUpdate` post-update block. | (1) `ReplaceAs3ArrayFromStaged` stages every `CreateObject` entry into a local `std::vector` BEFORE clearing any AS3 array (`SPECIALList`, `SlotResists`, `TotalResists`, `ActiveEffects`, plus `InvItems`, `FavoritesList`, `QuestsList`, `WorkshopsList`, `GeneralStatsList` in `FillInvAndDataIntoDataObj`) — any failed `CreateObject` logs `step=data_obj_stage_abort` and leaves the prior AS3 list intact. (2) Partial vitals refreshes skip static structural lists (`SlotResists`, `PerksList`, `StatsCategories`, `RadioList`, and unchanged `SPECIALList`) once `g_staticListsInitMovie == movie`; initial full fills ensure `INV`, `DATA`, and `RADIO` arrays (`RadioList`, `InvItems`, `QuestsList`, `WorkshopsList`, `GeneralStatsList`, `InvSelectedItems`, `FavoritesList`, `InvComponents`) remain valid Arrays when `ShellVitalsFill=1`. (3) `ApplyBottomBarDateFix` is guarded once per `(movie, page)` (`g_dateFixDoneMovie` / `g_dateFixDonePage`, DATA/MAP only), and `ShellUpdate` skips its `ReadPath(top, g_codeObjAt, menuMc)` block entirely once backdrop, hint bar, platform, and date fix have succeeded for the movie. | Always active; transparent safety and performance fix. |

---

## 3. Out-of-the-Box Sidecar INI & One-Line Rollbacks (`FO4SFPipboyMenu.ini`)

```ini
ShellBackdrop=1
ShellVitalsFill=1
SuppressDataMenu=0
TabOpensPipboy=0
HideStarfieldWatch=1
```

- **C++ fallback if omitted from a legacy INI:** `ShellBackdrop=1`; `ShellVitalsFill=0`, `SuppressDataMenu=0`, `TabOpensPipboy=0`, `HideStarfieldWatch=0`.
- **One-line rollbacks (no DLL rebuild):**
  - `HideStarfieldWatch=0` — restores Starfield's bottom-left wrist watch (`D7b`).
  - `ShellVitalsFill=0` — restores the exact `2f` `PopulateInCall=0` `SpecialReady`-only path (`C4-2`).
  - `ShellBackdrop=0` — disables the `root.graphics` CRT backdrop (`C4-1`).
  - `SuppressDataMenu=0` / `TabOpensPipboy=0` — disables `C4-4`.
  - `--commonwealth-weather 0` on `scripts/core/make_core_values.py stage` — omits the `CLMT`/`ATMO` clear-weather overrides from `FO4SFCoreValues.esm` (`D7a`).

---

## 4. Exact `FO4SFPipboyMenu.log` PASS Lines for Round 11 Verification (`pushed, not run`)

1. **Startup config:**
   - `step=shell_c4_config shell_backdrop=1 shell_vitals_fill=1 suppress_data_menu=0 tab_opens_pipboy=0 hide_starfield_watch=1`
2. **Starfield wrist-watch hide (`D7b`):**
   - `step=hud_watch_hide when=<on_movie_created|menu_open_close|menu_transition|ui_poll> try=<n> movie=0x... ok=1 target=BottomLeftGroup_mc children_hidden=<n>` (with `<n> > 0`)
   - Visual PASS: bottom-left circular `"MARS"` / `O2` / `CO2` watch is hidden in open gameplay; crosshair, `[E]` prompts, health/ammo (`RightMeters_mc`), and quest notifications (`TopCenterGroup_mc`) remain visible.
   - If channel IDs are unavailable at Stage 2 with `CodeObj=0`: `step=hud_watch_hide_init ok=0 reason=channel_ids_unavailable` (disables watch-hide only; `FO4SFPipboyMenu.dll` stays loaded).
3. **Pip-Boy layout & KB+M glyphs (`D5` Parts 1 & 2):**
   - `step=shell_hintbar_layout when=kShow old_y=575.0 new_y=672.0 ok=1`
   - `step=shell_platform when=kShow platform=0 called=1 triggers_hidden=2`
   - Visual PASS on `STAT`: `"PLAYER"` sits cleanly above `BottomBar_mc` with zero overlap on `"RADAWAY (0)"` (which sits below `BottomBar_mc`); `[LT]`/`[RT]` trigger icons are hidden and button hints use keyboard glyphs instead of Xbox `(A)`/`(X)`/`(Y)`.
4. **INV, DATA, and RADIO page safety with `ShellVitalsFill=1` (`A2.6`):**
   - Switch across `STAT` -> `INV` -> `DATA` -> `MAP` -> `RADIO` -> `STAT`; verify zero `step=data_obj_stage_abort`, zero `step=movie_call_failed`, and `step=shell_backdrop` / `step=shell_date_fix` / `step=shell_hintbar_layout` / `step=shell_platform` each log once per movie open (zero per-update spam).
5. **Clear Commonwealth weather (`D7a`):**
   - `FO4SFCoreValues.esm` builds with `2 CLMT, 1 ATMO` (`ClimateUniqueCydonia 0x00310DB1`, `ClimateUniqueCydoniaFrozen 0x002EDEA5`, `ATMO_Mars 0x0000C9D2`).
   - Visual PASS on surface arrival & Sanctuary/Concord walk: clear blue-sky Commonwealth daylight with no persistent orange Mars dust storm.
