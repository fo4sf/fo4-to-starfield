# New-Game Set-Up Screen Study: S.T.A.L.K.E.R. Anomaly, GAMMA, and FO4SF (`N2`)

> **Author:** Gemini (PC)  
> **Scope:** Pre-world new-game set-up architecture (`N2`, replacing the Vault 111 black-hold flow `H0`). Describes structural flow and data-table design only; copies zero third-party text, art, or assets.

## 1. How S.T.A.L.K.E.R. Anomaly and GAMMA Structure New-Game Set-Up

Both **S.T.A.L.K.E.R. Anomaly** and the **G.A.M.M.A.** modpack separate **character and campaign configuration** completely from **world simulation**:

1. **Zero World Load During Selection:**
   - Clicking **New Game** from the main menu never spawns an actor into a bunker, pod, or tutorial cell while options are still being chosen.
   - Instead, the player stays on a dedicated full-screen 2D set-up interface (`ui_mm_faction_select` in Anomaly's menu layer) until **Start / Confirm** is pressed. The engine loads the target level **once**, directly into the chosen faction's starting point.
2. **All Campaign Decisions on One Unified Set-Up Flow:**
   - **Character Identity & Portrait:** Name and faction-filtered icon/appearance choice.
   - **Mode Toggles:** **Story Mode** (main questlines active; restricted to factions compatible with the narrative arc) vs. open sandbox / **Warfare Mode** (dynamic territory control, squad spawns, faction-vs-faction conquest) vs. Azazel / Ironman / Survival rules.
   - **Faction Picker:** Selecting one of the playable factions dynamically filters the valid starting locations, starting equipment loadout, initial faction relations/goodwill matrix, and whether Story Mode is permitted.
   - **Start Location Picker (Table-Driven):** A per-faction list of starting bases/outposts read from configuration tables (`plugins/faction_quick_start` / start-location LTX tables). Locations unavailable to the chosen faction or mode are hidden or disabled so a player can never select an unbuilt or incompatible spawn.
   - **Difficulty & Progression Economy Presets:** Separate combat difficulty (damage/lethality/AI accuracy) and progression/scavenging economy presets (tourist / scavenger / survivalist), plus optional hardcore toggles (campfire/sleep save rules, radiation/limb/thirst rules).
   - **Point-Buy Starting Loadout / Attributes:** A bounded point pool spent before spawning, committed into starting inventory and stats at world entry.
3. **What GAMMA Changes on Top of Anomaly:**
   - Curates the faction/location matrix and presets around survival, crafting/maintenance progression, and Warfare balance so presets map cleanly to gameplay globals applied on first load, while keeping the single pre-world confirmation boundary intact: **nothing in the 3D world ticks or renders until the start record is finalized**.

---

## 2. Why Pre-World Set-Up Solves `H0` and `Card 4` in Starfield

Session 1 and Session 2 exposed two structural flaws in asking start questions inside Vault 111 under a fade hold:

1. **`H0` (`LoadingMenu` vs. `FaderMenu` Deadlock):**
   - When `StartupQuest_DO` (`0x00562D`) is overridden so `MQ101` never runs, Starfield's New-Game `LoadingMenu` does **not** finish its main-menu handoff while `Game.FadeOutGame(True, True, 0.0, 0.1, True)` (`abFadingOut = True`, `abStayFaded = True`) holds `FaderMenu` opaque black. Calling `FadeOutGame(False, True, 0.0, 0.1, False)` is what finishes main-menu loading (matching Roleplayers' Alternate Start's `";finishes main menu loading"` note and Session 1's console `FadeOutGame 0 1 0.0 0.5 0` immediately releasing `mode loading menu closed`).
   - Worse, `FaderMenu` renders above `MessageBoxMenu` and `Console`, so any `Message.Show()` called under `abStayFaded = True` is invisible and unanswerable, and the console itself cannot be seen to toggle an escape global.
2. **`Card 4` (Warfare S.P.E.C.I.A.L. Strand After `ShowRaceMenu`):**
   - In the old Warfare branch, `Game.SetInChargen(true, true, false)` remained active across `Game.ShowRaceMenu(None, 2)`, and `OpenAttributeAllocation("warfare")` called `SpecialPage1Msg.Show()` at `0.0 s` inside `ChargenMenu` teardown — causing `MessageBoxMenu` to fail to draw while blocking the script forever (`R10` violation).
3. **Multi-Location & Multi-Game Scope (`N2`):**
   - Neither a **Warfare** start nor a future non-Fallout-4 **Story** start belongs in Vault 111. Loading `FO4Port_Vault111Cryo` first wastes a heavy cell load, reveals or ticks vault state prematurely, and strands non-Vault starts if any prompt blocks.

---

## 3. FO4SF `N2` Architecture

### 3.1 Empty Pre-World Staging Room + Two Staged Backdrop Variants (`R5`)
Because Starfield's `StartupQuest_DO` starts a quest on `New Game` while the engine requires a valid player cell to complete initial `3D` load and close `LoadingMenu`, `FO4SFNewGame.esm` authors an owned, empty, Starfield-free interior cell **`FO4SF_StartRoomCell` (`0x00081C`)** containing only persistent **`FO4SF_StartRoomMarkerRef` (`0x00081D`)** (zero props, zero NPCs, dark neutral `XCLL`, first-person geometry hidden via `Game.ShowFirstPersonGeometry(false)` and HUD hidden via `Game.SetCharGenHUDMode(3)`, both restored to `ShowFirstPersonGeometry(true)` / `SetCharGenHUDMode(0)` on world entry):

1. On `New Game`, `Begin()` moves the player to `FO4SF_StartRoomMarkerRef` (`0x00081D`) — **never** Vault 111 — runs `HoldOffPass(1)`, writes `MQ101Debug = 2`, waits for `3D`, and **immediately lifts the fade** (`Game.FadeOutGame(False, True, 0.0, 0.1, False)`, `Game.SetInChargen(false, false, false)`) so `LoadingMenu` closes cleanly and every subsequent UI element is 100% visible.
2. Before showing any box or screen, `WaitForStartUiReady()` waits until `LoadingMenu` has closed — bounded by **`StartLoadTimeout = 15.0 s`**, which forces fade lift and logs `mode fade lifted by=timeout s=15` (`R10`) if the close event never arrives.
3. **`StartChoiceBackdrop` (`--start-choice-backdrop`, `R5` staged variants):**
   - **Variant `(a)` — `empty_cell` (`1`, default):** Sequential message boxes over our empty held backdrop (`FO4SF_StartRoomCell`, HUD and first-person body hidden, zero fade covering any box). Default this round because every step uses proven native `MessageBoxMenu` input without custom Scaleform cursor/button hit-testing risks.
   - **Variant `(b)` — `title_card` (`2`, staged for owner comparison):** Registers non-modal **`FO4SF_StartCardMenu`** (`Interface/FO4SF_StartCard.swf`, `depth = 0`, `StartCardShouldHandleEvent -> false`) in `FO4SFPipboyMenu.dll`, driven by store global **`FO4SF_StartCardOpen` (`FO4SFCoreValues.esm:0x000866`, `R13`)**, drawing a full-frame Fallout-styled Pip-Boy-green slate backdrop behind the prompts. A full single-page Anomaly-style Confirm screen (`FO4SF_StartSetupMenu.swf`) requires a dedicated AS3 multi-column form movie + native `BGSCodeObj` commit callback in `FO4SFPipboyMenu.dll`; its store schema and start-place table below are already its exact backend contract.

### 3.2 Unified Choice Flow -> Store Start Record (`R13`) -> Table-Driven Spawn
All choices happen in one pre-world sequence inside `FO4SF_StartRoomCell` with **zero fade active**:

1. **Mode:** `Story` (`1`) or `Warfare` (`2`).
2. **Branch Choices:**
   - **Story:** Story line (`0 = Fallout 4: Commonwealth`; future titles remain disabled/unlisted until their start cells exist so an unplayable start is never offered).
   - **Warfare:** Difficulty (`0..3`), Allegiance/Faction (filtered to factions with loadable start rows), and Start Place (filtered to loadable rows in the start-place table).
3. **Survival & Settings Layer:** `Survival: No` (`0`) or `Survival: Yes` (`1`, locking Survival in Warfare).
4. **S.P.E.C.I.A.L. Allocation (`Warfare`):** Runs **before** any `ShowRaceMenu` call while `SetInChargen` is `false` and no menu is tearing down (eliminating the `Card 4` strand; `3` cancelled tries fall back to `OfferStandardSpread`).
5. **Character Appearance (`Looks`):**
   - Lift `"Character"` button is removed (`H00(c)`).
   - Appearance is offered in the pre-world set-up flow (`Create character` / `Quick start`) **after** S.P.E.C.I.A.L. and **before** moving to the chosen start place, waiting cleanly for `ChargenMenu` close (bounded by `LooksWait`) plus a `2.0 s` post-close settle and `SetInChargen(false, false, false)`. *(Note: `Game.ShowRaceMenu(None, 2)` is still Starfield's **NOT OURS** appearance menu this round; replacing it requires our own Vault-Tec face/body morph Scaleform menu.)*
6. **Commit Start Record & Move Once:**
   - Writes one global per choice in `FO4SFCoreValues.esm` (`R13`):
     - `FO4SF_GameMode` (`0x000870`), `FO4SF_StoryLine` (`0x000878`), `FO4SF_WarfareFaction` (`0x000874`), `FO4SF_WarfareStartIndex` (`0x000875`), `FO4SF_StartPlaceRow` (`0x000879`), `FO4SF_SurvivalStart` (`0x000871`), `FO4SF_SurvivalLocked` (`0x000872`), `FO4SF_StartDifficulty` (`0x000873`), `FO4SF_StartChoiceDone` (`0x000876`).
   - Logs **once**:
     `start record mode=<story|warfare> story=<id> faction=<n> place=<id> survival=<0|1> difficulty=<n> backdrop=<name>`
   - Looks up the chosen row in the unified **Start-Place Table** (`StartPlaceIds`, `StartPlaceModes`, `StartPlaceSpaces`, `StartPlacePlugins`, `StartPlaceMarkerIds`, `StartPlaceX/Y/Z`, `StartPlaceHeadings`, `StartPlaceIsInterior`, `StartPlaceQuestMask`) and moves the player to a game location **for the very first time** (with `3x` retry + fallback to the default Vault 111 / `ExitAnchorId` start and log line under `R10`).
