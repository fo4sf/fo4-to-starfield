# Everyday Fallout 4 Menus: Hosting vs. Restyle Options

Owner decision note (design comparison only; nothing built in this step, zero game text).

## 1. Measured Surface of Candidate Fallout 4 Movies

Each movie below was inspected via `scripts/ui/swf_names.py` for its ActionScript 3 document class, `BGSCodeObj` slot, outbound native calls, and matching Starfield 1.16.244.0 registered menu name:

| Fallout 4 Movie | Size (B) | Document Class (`extends Shared.IMenu`) | `BGSCodeObj` Outbound Calls | Engine -> Movie Inputs | Starfield Registered Menu (`.rdata` RVA) |
|---|---:|---|---|---|---|
| `SleepWaitMenu.swf` | `15,774` | `SleepWaitMenu` | `Accept(hours)`, `Cancel()` | Current hour string, sit vs. bed prompt mode, `ProcessUserEvent` | `SleepWaitMenu` (`0x4D7E0E0`) |
| `SitWaitMenu.swf` | `13,217` | `SitWaitMenu` | `StartWaiting()`, `Cancel()` | Furniture sit state, wait prompt visibility | `SitWaitMenu` (`0x4D7E0C0`) |
| `FavoritesMenu.swf` | `28,227` | `FavoritesMenu` (`FavoritesCross`, `FavoritesEntry`) | `useQuickkey(slot)`, `closeMenu()` | 12-slot directional cross array (name, icon, count, ammo) | `FavoritesMenu` (`0x4D08C88`) |
| `Book.swf` | `17,147` | `BookMenu` (`RefText`) | None directly from AS3 (engine drives page turn & close) | Paginated plain text, page turn / cancel events | `BookMenu` (`0x4D7DF10`) |
| `MessageBoxMenu.swf` | `20,163` | `MessageBoxMenu` (`MessageBoxButtonList`) | `onButtonPress(index)`, `PlayFocusSound()` (via `BGSExternalInterface.call`) | Body text, button label array, modal input lock | `MessageBoxMenu` (`0x4D7E028`) |
| `ContainerMenu.swf` / `BarterMenu.swf` | `> 60,000` | Dual-pane item transfer & caps settlement | Full item-card, category filter, stack count slider, 3D preview, caps balance | Both player & target inventories, encumbrance, vendor caps | `ContainerMenu` (`0x4D7DD58`), `BarterMenu` (`0x4D7DCF8`) |

## 2. Three Architectural Options for the Owner

### Option 1 — Host All Five Fallout 4 Movies + Container/Barter in Custom SFSE Menus
- **Pros:** 100% Fallout 4 layout, monochrome/amber tinting, and key flow across every interaction.
- **Cons:** Hosting `ContainerMenu` and `BarterMenu` duplicates the entire inventory/item-card serialization surface plus vendor caps math and stack-transfer edge cases before Pip-Boy `INV` is proven; intercepting Starfield's `MessageBoxMenu` also affects engine-generated system prompts and tutorial/mode boxes (`Task 3` `S4`).

### Option 2 — Restyle Starfield's Native Menus Only
- **Pros:** Zero C++ Scaleform hosting or inventory/time plumbing; engine handles controller prompts, item stacks, and save safety natively.
- **Cons:** Starfield's circular/radial `FavoritesMenu` and futuristic `SleepWaitMenu` / `ContainerMenu` retain Starfield geometry and sound cues.

### Option 3 — Mixed Route (Recommended Default)
- **Host Fallout 4's `SleepWaitMenu.swf` (`SitWaitMenu.swf`) and `FavoritesMenu.swf`** as dedicated SFSE `IMenu` hosts using the exact plain-`Object` `BGSCodeObj` pattern proven by `FO4SFPipboyMenu`:
  - `SleepWaitMenu` needs only **2** callbacks (`Accept(hours)` advancing `GameHour` / `GameDaysPassed` + survival sleep/fatigue hook, and `Cancel()`).
  - `FavoritesMenu` needs only **2** callbacks (`useQuickkey(slot)` equipping/consuming the bound form via `ActorEquipManager`, and `closeMenu()`).
  - Optional follow-up: `Book.swf` for readable Fallout notes/journals (`0` outbound callbacks).
- **Keep Starfield's native `MessageBoxMenu` for system/start prompts** (so `Task 3` pre-load mode selection and engine confirmations never risk soft-locking), while using `PipboyMessageBox.swf` inside the Pip-Boy.
- **Restyle Starfield's `ContainerMenu` and `BarterMenu`** (matching the precedent used by other large Creation Engine total conversions) rather than re-implementing dual-inventory transfer C++ logic.

## 3. Suggested Rollout Order (After Task 1 `THIS ROUND` + `1k` Pass)

1. `SleepWaitMenu` (triggered on bed/chair wait input; `step=sleep_wait action=accept hours=<n>`).
2. `FavoritesMenu` (12-slot D-pad / number-row cross synced with Pip-Boy `SetQuickkey`; `step=favorites slot=<0..11> form=<id>`).
3. `BookMenu` / note reader if needed for quest holotapes/notes.
