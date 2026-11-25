# Pip-Boy DATA > JOBS Sub-Tab Design (Task 2c)

## Scope and Rules
- **Branch:** `gemini/r14-pipboy-menus` (stacked on `#860`).
- **Rule 12 (pending decisions):** Bounties / pay rates / standing integration and whether `JOBS` ultimately stays a `DATA` sub-tab (`7148866314`, recommended default) or moves to a top-level tab (`7148165105`) remain design-only here. No runtime economy payout or standing side-effects exist in code.
- **Evidence policy:** All bytecode findings below come directly from disassembling Fallout 4's `pipboy_datapage.swf` (`QuestsTab`, `WorkshopsTab`, `QuestsListEntry`) and SFSE source (`sfse/FO4SFPipboyMenu/src/main.cpp`, `sfse/FO4SFPipboyMenu/src/pipboy_menus_r14.h`).

---

## 1. Verified `pipboy_datapage.swf` `QuestsTab` Behaviour for `formID == 0`

Disassembly of `pipboy_datapage.swf` (`DoABC2`) establishes exact behaviour when an entry in `DataObj.QuestsList` carries `formID == 0`:

1. **`QuestsListEntry.SetEntryText` (list row rendering):**
   - Renders divider header only if `entry.isDivider == true`.
   - When `isDivider` is unset/false and `formID == 0`, renders a normal selectable quest row using `text`, `active`, `enabled`, `completed`.
2. **`QuestsTab.onQuestSelectionChange`:**
   - Checks `selectedEntry.formID == 0`: sets `ObjectivesList_mc.disableSelection = false` so rows inside `ObjectivesList_mc` are focusable/selectable.
   - Always calls `updateQuestDescription()`, `updateQuestAnimation()`, and `refreshObjectiveList()`, which invokes `BGSExternalInterface.call("onQuestSelection", ObjectivesList_mc.entryList, QuestsList_mc.selectedEntry, this)`.
3. **`QuestsTab.onQuestPress`:**
   - Branches on `QuestsList_mc.selectedEntry.formID == 0`:
     - If `formID == 0`, calls `onRightThumbstickInput(2)` to move focus directly into `ObjectivesList_mc` rather than calling `SetQuestActive` on the group header itself.
     - If `formID != 0`, invokes `BGSExternalInterface.call("SetQuestActive", QuestsList_mc.selectedEntry)`.
4. **`QuestsTab.onObjectivePress`:**
   - Selecting an individual row inside `ObjectivesList_mc` calls `BGSExternalInterface.call("SetQuestActive", ObjectivesList_mc.selectedEntry)`.
5. **`QuestsTab.onShowOnMap` / `ProcessUserEvent` (`XButton` / `Cancel`):**
   - `formID == 0` suppresses quest map-jump on the group header (`ShowOnMapButton` checks `selectedEntry.formID != 0`). Pressing `Cancel` while focused in `ObjectivesList_mc` returns focus to `QuestsList_mc`.

**Conclusion (Task 2c):** Adding a `"JOBS"` entry with `formID = 0` (`isDivider` omitted/false) renders cleanly as a collapsible/inspectable group inside `DATA > QUESTS` (`QuestsList`) and displays each loaded job as a selectable row inside `ObjectivesList_mc`, matching Fallout 4's `Miscellaneous` group pattern with zero SWF modification.

---

## 2. Step 1 Implementation (`ShowJobsGroup=0` default, Generic JSON Reader)

- **INI switches (default OFF):**
  - `ShowJobsGroup=0` (`scripts/ui/make_pipboy_stage_ini.py`, `sfse/FO4SFPipboyMenu/FO4SFPipboyMenu.ini`).
  - `JobsJson=FO4SFPipboyJobs.json` (resolved relative to the SFSE plugin directory if not absolute).
- **Generic JSON reader (`sfse/FO4SFPipboyMenu/src/pipboy_menus_r14.h`):**
  - Accepts either a top-level array (`[...]`) or an object wrapper (`{"jobs": [...]}`).
  - Extracts `{ id, title, giver, target, reward_text / rewardText, status }` and skips unknown fields so Claude's finalized job-record schema drops directly into `FO4SFPipboyJobs.json` without plugin recompilation.
- **Runtime handlers (`sfse/FO4SFPipboyMenu/src/main.cpp`):**
  - `onQuestSelection` with `formID == 0` and `ShowJobsGroup=1` populates `ObjectivesList_mc` from `g_jobsSnap` using reserved synthetic IDs `kJobRowFormIdBase + idx` (`0xF0000001u + idx`) and calls `QuestsTab.onObjectivesReady`.
  - `SetQuestActive` toggles in-memory `active` state for tracked job selection and logs `step=job_active id={} active={}` without mutating currency or faction standing.

---

## 3. Full `DATA > JOBS` Sub-Tab Page-Movie Tool Design

When replacing the `formID = 0` group with a dedicated `JOBS` sub-tab alongside `QUESTS | WORKSHOPS | STATS` (recommended default: **`QUESTS | JOBS | WORKSHOPS | STATS` under `DATA`, matching `7148866314`**), `pipboy_datapage.swf` needs one additional tab button, tab index slot in `_TabNames` / `_StoredTabs`, and a list/card view controller (`JobsTab_mc`). Two implementation routes exist:

### Option A — Automated AVM2 DoABC Bytecode Patcher (Recommended Default)
- **Mechanism:** Extend `scripts/ui/swf_names.py` / a new `scripts/ui/patch_pipboy_datapage_swf.py` builder to disassemble `pipboy_datapage.swf` `DoABC2`, clone `QuestsTab` or `WorkshopsTab` MovieClip timeline/ABC traits into `JobsTab`, append `"JOBS"` to `DATA`'s tab array and header bar layout, and emit the staged `Data/Interface/pipboy_datapage.swf` offline into `<stage>/Data/Interface/` without committing any game asset to Git.
- **Pros:**
  - Keeps 100% of Fallout 4's CRT shaders, sound cues, font embeds (`$MAIN_Font`), button hints (`BSButtonHintData`), and Scaleform vector skins intact.
  - Diffable, deterministic Python transformation checked by unit tests against synthetic SWF fixtures.
- **Cons / Risks:**
  - Must carefully re-index ABC constant pool entries, `DefineSprite` DisplayList character IDs, and `ExportAssets` symbols so Flash Player / Scaleform 4 does not encounter symbol-ID collisions.

### Option B — From-Scratch Replacement `pipboy_datapage.swf` Built via `make_probe_swf.py` / Compiler
- **Mechanism:** Author all `DATA` sub-tabs (`QUESTS`, `JOBS`, `WORKSHOPS`, `STATS`) in custom AS3 / SWF tag generator matching `BGSCodeObj` contracts (`QuestsList`, `WorkshopsList`, `GeneralStatsList`, `JobsList`).
- **Pros:** Full control over AS3 layout and extra columns (bounty tier, faction issuer, timer).
- **Cons:** Must re-implement `BSScrollingList`, scrollbar physics, PaperDoll/VaultBoy loader alignment, and button hint bars to match the surrounding Fallout 4 shell (`pipboymenu.swf`, `pipboy_statspage.swf`, `pipboy_invpage.swf`).

### Recommended Path
Use **Option A (bytecode patcher on the staged `pipboy_datapage.swf`)** once the owner confirms `JOBS` placement under `DATA` (`QUESTS | JOBS | WORKSHOPS | STATS`), keeping `Option B` as fallback only if a Scaleform sprite/layout constraint blocks inserting a fourth `DefineSprite` tab on `DATA`. Until then, Step 1 (`formID = 0` `JOBS` group inside `DATA > QUESTS`, `ShowJobsGroup=0` default) serves as the zero-movie-risk integration point.
