# Pip-Boy Menu Fixes & DATA Pages Test Card (Round 14 Task 2d)

- **Branch / PR:** `gemini/r14-pipboy-menus` (stacked on `#860`)
- **Stage INI Defaults:** `DataPagesFill=1` (`DATA > QUESTS` & `DATA > WORKSHOPS` active), `TabOpensPipboy=0`, `SuppressDataMenu=0`, `ShowJobsGroup=0`, all 8 `Hide*Menu=0` (opt-in OFF until each row passes).
- **Important:** Replace `<STARFIELD_DIR>` and stage folder placeholders when installing on PC; never install while `Starfield.exe` is running.

---

## Verification Rows (Task 2d)

| Row ID | Kind | Action / Setup | Expected Result & Log Evidence | Status |
|---|---|---|---|---|
| `T2-1` | `VIDEO` | Open any converted FO4 crafting bench (Weapons / Armor / Chem / Cooking / Industrial) and press `F7` (or Map `M`) while the bench menu is open. | Pip-Boy MUST stay closed. Log shows `step=request_open ... ignored=menu_open menu=<WeaponsCraftingMenu|...>`. `kBlockingMenus` blocks all 21 curated modal screens (`ArmorCraftingMenu`..`EndGameCreditsMenu`). | Pending in-game run |
| `T2-2` | `REACHABLE` | During normal outdoor gameplay (no crafting bench, container, or pause menu open), press `Tab`. | Starfield's `DataMenu` hub opens as expected (`TabOpensPipboy=0` default until `INV` and `DATA` cards clear). | Pending in-game run |
| `T2-3` | `TEST-STATION` | With default `ShowJobsGroup=0` and `DataPagesFill=1`, open Pip-Boy (`F7`) and inspect `DATA > QUESTS` and `DATA > WORKSHOPS`. | `DATA > QUESTS` lists active/completed `FO4SF*` quests (`step=quests_fill ... n>=1`) and clicking a quest loads its objectives (`step=quest_select ...`); `DATA > WORKSHOPS` shows `Sanctuary Hills` (clean name, no `(Placeholder)` suffix). | Pending in-game run |
| `T2-4` | `TEST-STATION` | Write a sample array to `SFSE/Plugins/FO4SFPipboyJobs.json`, set `ShowJobsGroup=1`, relaunch, open Pip-Boy `DATA > QUESTS`. | `"JOBS"` appears with `formID=0`; selecting `"JOBS"` displays JSON job rows (`step=job_select jobs=N`) and activating a job logs `step=job_active id=... active=...`. | Pending in-game run |
| `T2-5` | `TEST-STATION` | Set each of the 8 `Hide*Menu` switches (`HidePowersMenu`, `HideAlmanacMenu`, `HideResearchMenu`, `HideShipCrewMenu`, `HideShipCrewAssignMenu`, `HideTakeoffMenu`, `HideShipRefuelMenu`, `HideWeaponGroupAssignmentMenu`) to `1` **one at a time** and trigger the corresponding Starfield UI / hotkey. | Target menu is hidden immediately on open without freezing HUD/input; log emits `step=hide_menu n=... menu=<Name> sent=hide`. Always-open overlays remain untouched. | Pending in-game run |

---

## Deferred Menu Census List (`T2-Census`, Do NOT Block Yet)

Record exact registered name behavior in SFSE logs (`World=1` / in-game trigger) before adding to `kBlockingMenus` or `HideMenus`:

1. `MissionMenu` — verify whether open only as modal mission detail or background HUD element.
2. `MarketplaceMenu` — verify Starfield Creations / Store modal lifecycle and `CursorMenu` stacking.
3. `DocAcceptMenu` — verify legal/confirmation overlay lifecycle (`PauseMenu` / startup only vs gameplay).
4. `BoundaryMenu` — verify landing-tile boundary popup lifecycle on Commonwealth exterior borders.
5. `FanfareMenu` — verify non-blocking quest-complete fanfare overlay (blocking could eat `F7`/`M` after quest completion!).
6. `StreamingInstallMenu` — verify content-install modal lifecycle.
7. **Inspect screen & Scanner note:** `Starfield.exe` has no exact `InspectMenu` menu-name string (only `inspectmenu.swf` Flash movie under inventory inspection); both weapon/armor inspect (`inspectmenu.swf`) and `MonocleMenu` (hand scanner) remain deferred/monitored under the star-map & hub removal pass.
