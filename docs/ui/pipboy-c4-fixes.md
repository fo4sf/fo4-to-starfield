# Pip-Boy Screen Fixes (`C4`) & Native Scan Cache / Vector Locks (`R6`)

> **Whole-scope:** Titles: Fallout 4 -> all 7 Fallout titles (`FO4`, `FO3`, `FNV`, `FO1`, `FO2`, `Tactics`, `FO76`) | Modes: Story & Warfare (+ Survival hardcore layer) | Track: **Track 1 (playable path)** — `FO4SFPipboyMenu.dll`
> **Playable status:** `pushed, not run` — built locally with MSVC x64 (`build.ps1`) and covered by offline regression tests; **not yet verified in game** until the `candidate-2g` PC run captures fresh stills and `FO4SFPipboyMenu.log`.

---

## 1. Evidence from `candidate-2f` (`22 Nov`)

Two in-game stills and `FO4SFPipboyMenu.log` from `candidate-2f` exposed four visual/UX defects (`C4-1` through `C4-4`) alongside two native runtime hygiene findings (`R6`):

| ID | Observed in `candidate-2f` | Root cause | Fix in this slice (`FO4SFPipboyMenu`) | Activation / rollback |
| --- | --- | --- | --- | --- |
| **`C4-1`** | STAT page rendered directly over Concord street / Preston with zero dark backing; MAP page had Concord bleeding through left/right 16:9 margins. | `FO4SF_Fo4Shell` (`PipboyMenu.swf`, `876x700`) was authored for a 3D wrist CRT render target and has a transparent stage. | `ApplyShellBackdrop` draws a two-layer opaque dark CRT backing (`#020804` outer matte `alpha=0.92` covering 16:9 & ultrawide margins + `#041409` screen fill `alpha=0.97` with `#185228` bezel) on `root.graphics` (fallback `Menu_mc.graphics`) behind `Menu_mc`. | **`ShellBackdrop=1`** (default `1` in C++, shipped INI, and `make_pipboy_stage_ini.py`). Rollback: set `ShellBackdrop=0` (one line, no rebuild). |
| **`C4-2`** | STAT footer showed `HP 0/0` and `AP --/--` on `F7` open. | `candidate-2f` shipped with `PopulateInCall=0` (the 1a crash-proof safe default). `CollectShellVitalsMainThread` already resolved `ActorValueOwner::GetActorValue` (`owner_offset=0x70`, `slot=0x19776f0`) and collected live S.P.E.C.I.A.L., Health, and Oxygen/AP, but `ShellShowInit`, `AnswerPageOrTabSynchronously`, and `ProcessPendingShellEvents` skipped `FillPipboyDataObj` whenever `PopulateInCall=0`, leaving `DataObj` at Flash defaults (`0/0`, `--/--`). | Added INI switch **`ShellVitalsFill`** (C++ fallback `0` if omitted; emitted as **`ShellVitalsFill=1`** in shipped `FO4SFPipboyMenu.ini` and `make_pipboy_stage_ini.py` so `candidate-2g` has real HP/AP out of the box). When `ShellVitalsFill=1` (or `PopulateInCall=1`), `ShellShowInit`, `AnswerPageOrTabSynchronously`, and `ProcessPendingShellEvents` call `FillPipboyDataObj` with live `HP`/`AP`/S.P.E.C.I.A.L./`Date`/`Time`/`Location` (while keeping `PopulatePipboyInfoObj` as a non-mutating stub when `PopulateInCall=0`). `CollectShellVitalsMainThread` also guards against uninitialized `0.0f` AV reads before any positive reading (`everPositiveHp`/`everPositiveAp`) using Fallout 4 END/Level HP (`80 + 5*END + (LVL-1)*(0.5*END + 2.5)`) and AGI AP (`60 + 10*AGI`) formulas. | **Emitted as `ShellVitalsFill=1` in staged/shipped INI.** Rollback: set `ShellVitalsFill=0` to restore the exact `2f` `PopulateInCall=0` path byte-for-byte without rebuilding. |
| **`C4-3`** | MAP footer clipped `"10.23.2287"` to `"10.23.228"`. | In `BottomBar_Info_3` Frame 6 (`Menu_mc.BottomBar_mc.Info_mc.Date_tf`), `Date_tf` starts at `x=8.0` with `width=150.0` (right edge `158.0`) while `Time_tf` starts at `x=207.0` (`49 px` unused gap). Starfield's wider fallback UI font overflows `150 px` at character 10. | `ApplyBottomBarDateFix` sets `Date_tf.wordWrap = false`, `Date_tf.width = 194.0` (`5 px` clear of `Time_tf`), and `Date_tf.autoSize = "left"` (plus `Time_tf.width = 156.0`, clear of `Location_tf` at `x=409.0`) after `InvalidateData` / `InvalidatePartialData` / `ShellUpdate`. | Active on `FO4SF_Fo4Shell` whenever Frame 6 `Date_tf` is present. |
| **`C4-4`** | Pressing `Tab` while Pip-Boy was closed opened Starfield's `DataMenu` (`"Mars - Commonwealth 00 (FO4 terrain)"`), which also caused `M` to be ignored (`step=map_key ... ignored=menu_open menu=DataMenu`). | `DataMenu` was listed in `blocking_menus.h` but never suppressed, and closed-Pip-Boy `Tab` (`0x09`) was not wired to `FO4SF_PipboyMenu`. | Added two explicit opt-in INI switches (both **`0`** in C++, shipped INI, and `make_pipboy_stage_ini.py`): **`SuppressDataMenu`** (hide-only `kHide` on `DataMenu`, zero `initFunc` replacement) and **`TabOpensPipboy`** (opens `FO4SF_PipboyMenu` on closed `Tab`, guarded by a main-thread-polled `g_nonDataBlockingOpen` + **`500 ms`** cooldown `kBlockingMenuCooldownMs` so pressing `Tab` to close Starfield's `DialogueMenu`, `ContainerMenu`, `WorkshopMenu`, `TerminalMenu`, `LockpickingMenu`, `InventoryMenu`, `PauseMenu`, etc. NEVER pops the Pip-Boy, plus a `350 ms` Pip-Boy anti-bounce cooldown `kShellTabCooldownMs`). | **Explicit opt-in (`SuppressDataMenu=0`, `TabOpensPipboy=0` as shipped).** Card opt-in step: set `SuppressDataMenu=1` (or `--suppress-data-menu 1`). |
| **`R6-1`** | `CollectQuestAndStatsMainThread` ran `0x800..0xBFF` (`1,024` `LookupById` calls per `FO4SF*` plugin) every `500 ms` even when `InvDataAnswers=0`. | No post-load cache of resolved `TESQuest*` pointers; full DATA list building ran even for the MAP-only `InvDataAnswers=0` path. | One-time `PostDataLoad` discovery cache (`g_cachedQuestForms`, keyed to `TESDataHandler*`) scans `0x800..0xBFF` once (`step=quest_cache_build`) and iterates only cached `TESQuest*` pointers on subsequent ticks. When `InvDataAnswers=0`, skips `quests`/`workshops`/`statCategories` construction and only updates `PipboyMap::SetActiveQuestObjectives`. | Always active; transparent optimization. |
| **`R6-2`** | `g_pushedStoreIndices` and `g_pushedQuestIndices` in `pipboy_map.cpp` were read/written across `PopulateMapDataObj`, `OnCodeObjCall("FastTravel")`, `OnShellUpdate`, `ReleaseMovieRefs`, and `ResetMapMovieState` without synchronization. | Missing mutex around the two index-mapping vectors. | Added dedicated leaf `std::mutex g_pushedIndicesLock` guarding every read, clear, and `emplace_back` on both vectors. The mutex is never held across Scaleform `GFx` or engine API calls, guaranteeing zero deadlock risk. | Always active; transparent concurrency fix. |

---

## 2. Defaults, Out-of-the-Box `2g` Sidecar INI, and One-Line Rollback (`FO4SFPipboyMenu.ini`)

- **Out-of-the-box `candidate-2g` INI (`sfse/FO4SFPipboyMenu/FO4SFPipboyMenu.ini` and `scripts/ui/make_pipboy_stage_ini.py`):**
  ```ini
  ShellBackdrop=1
  ShellVitalsFill=1
  SuppressDataMenu=0
  TabOpensPipboy=0
  ```
  When `candidate-2g` is staged without manual INI edits, pressing `F7` gets **both the opaque dark Pip-Boy background (`C4-1`) AND real player `HP`/`AP` (`C4-2`)** plus the widened MAP date (`C4-3`) and `R6` optimizations immediately. Existing safe defaults (`PopulateInCall=0`, `MapBlockStarMap=0`, `Arm=0`, `BootOnFirstOpen=0`, `StatActions=0`, `InvDataAnswers=0`) remain unchanged.
- **C++ fallback if a legacy INI omits the new keys:** `ShellBackdrop` defaults to `1`; `ShellVitalsFill`, `SuppressDataMenu`, and `TabOpensPipboy` default to `0`.
- **Why `SuppressDataMenu=0` and `TabOpensPipboy=0` stay explicit opt-in:**
  - Starfield uses `Tab` as its universal "Back / Exit" key for `DialogueMenu`, `ContainerMenu`, `WorkshopMenu`, `InventoryMenu`, and `PauseMenu`. Keeping both `0` by default keeps Starfield's `DataMenu` accessible until explicitly tested on the `2g` card (`SuppressDataMenu=1, TabOpensPipboy=0` hides `DataMenu` alone; `TabOpensPipboy=1` also wires closed-`Tab` open behind the `500 ms` `kBlockingMenuCooldownMs` + `g_nonDataBlockingOpen` guard).
- **One-line rollback (no DLL rebuild):**
  - `ShellVitalsFill=0` restores the exact `2f` `PopulateInCall=0` `SpecialReady`-only path byte-for-byte.
  - `ShellBackdrop=0` disables the `C4-1` `root.graphics` backdrop.
  - `SuppressDataMenu=0` / `TabOpensPipboy=0` disables `C4-4`.

---

## 3. Exact `FO4SFPipboyMenu.log` PASS Lines for `candidate-2g`

For `docs/testing/candidate-2g-card.md`, verify the following log tokens alongside visual stills of STAT (`F7`) and MAP (`M`):

1. **Startup config (out-of-the-box `2g` INI):**
   - `step=shell_c4_config shell_backdrop=1 shell_vitals_fill=1 suppress_data_menu=0 tab_opens_pipboy=0` (or `suppress_data_menu=1` on the opt-in `C4-4` card step)
2. **Background (`C4-1`):**
   - `step=shell_backdrop movie=0x... ok=1 target=root_graphics color=0x041409 alpha=0.97`
   - Visual PASS: solid dark Pip-Boy CRT backing behind STAT/INV/DATA/RADIO and dark matte margins around MAP (zero Concord bleed-through).
3. **Real HP & AP (`C4-2`, with `ShellVitalsFill=1`):**
   - `step=shell_vitals when=kShow page=0 tab=0 hp=<cur>/<max> ap=<cur>/<max> lvl=<n> hp_src=<av|formula> ap_src=<av|formula>` with `<cur> > 0` and `<max> >= 80`
   - `step=data_obj_fill when=kShow page=0 tab=0 hp=<cur>/<max> ap=<cur>/<max> ... date=10.23.2287`
   - Visual PASS: STAT bottom bar displays real non-zero `HP` and `AP` (never `HP 0/0` or `AP --/--`).
   - Fallback if `ShellVitalsFill=1` regresses: set `ShellVitalsFill=0` in `FO4SFPipboyMenu.ini` (exact `2f` path).
4. **Map Footer Date (`C4-3`):**
   - `step=shell_date_fix when=<kShow|onNewPage|update> old_w=150.0 new_w=<w> auto_size=1 word_wrap=1 width_set=1`
   - Visual PASS: MAP bottom-left footer reads full `10.23.2287` (all 4 year digits visible, no overlap with time).
5. **Closed-Pip-Boy `Tab` / `DataMenu` (`C4-4`, with `SuppressDataMenu=1`):**
   - Pressing `Tab` in gameplay with Pip-Boy closed does NOT leave Starfield's `DataMenu` open (`step=data_menu_suppress n=... menu=DataMenu sent=hide`), and pressing `M` immediately afterward opens Pip-Boy MAP rather than logging `ignored=menu_open menu=DataMenu`.
   - If `TabOpensPipboy=1` is tested: pressing `Tab` in open gameplay logs `step=tab_key n=1 vk=0x9 page=... sent=request_open`; pressing `Tab` to exit `DialogueMenu`/`WorkshopMenu`/`ContainerMenu` logs `step=tab_key ... ignored=recent_blocking_menu` (or is filtered at key-down) and does NOT pop the Pip-Boy.
   - `Esc` still opens `PauseMenu` (Save/Load/Settings/Quit) and `` ` `` still opens `Console`.
6. **Quest Scan Cache (`R6`):**
   - `step=quest_cache_build plugins=<n> quests=<m> workshop=<0|1> scanned=<k>` appears **once** per session (never repeating every `500 ms`).

---

## 4. Owner Questions

1. **Closed-Pip-Boy `Tab` (`C4-4`):** Does hiding Starfield's `DataMenu` alone (`SuppressDataMenu=1, TabOpensPipboy=0`, keeping `F7`/`M` as open keys) answer what you want, or do you also want closed-Pip-Boy `Tab` to open the Pip-Boy (`TabOpensPipboy=1`, guarded by the `500 ms` dialogue/workshop/container back-key cooldown)?
2. **Backdrop opacity (`C4-1`):** After seeing the `candidate-2g` stills, should the area outside the `876x700` CRT bezel stay at `alpha=0.92` or go pure solid `1.0` black?
