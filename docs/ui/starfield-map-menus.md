# Starfield 1.16.244.0 Registered Map & Scanner Menus

Offline binary and interface-archive measurement for blocking Starfield's galaxy, planet, and surface map menus and hand scanner during Fallout 4 play (`FO4SFPipboyMenu` + `FO4SF_NewGameQuest`).

## 1. Hand Scanner (`MonocleMenu`)

- **Registered menu name:** `MonocleMenu` (`Starfield.exe` 1.16.244.0 `UIStringHolder` constructor at RVA `0x253C4D7..0x253E077`; `.rdata` string `"MonocleMenu"` at RVA `0x4C94AE8`; movie `monoclemenu.swf`).
- **Chosen lever (one path only):** `FO4SF_NewGameQuest.DisableHandScanner()` creates an `InputEnableLayer` and calls `EnableHandscanner(false)` once at new-game fade-in, logging:
  ```text
  FO4SF_NEWGAME rt=<t> blocked input=handscanner
  ```
- **Blocking-menu hotkey guard:** `MonocleMenu` is also included in `sfse/common/blocking_menus.h` (`fo4sf::kBlockingMenus`) so `F7`, `M`, `V`, and `N` ignore presses with `ignored=menu_open menu=MonocleMenu` if opened via console before a new game runs.

## 2. Starfield Map Menus (`Starfield.exe` 1.16.244.0 Evidence)

Cross-referencing `UI::RegisterMenu` (`REL::ID 130463`, RVA `0x2543AD0`), the `UIStringHolder` constructor (`0x253C4D7..0x253E077`), static `BSFixedString` `MENU_NAME` getters (`mov r8b, 1; lea rdx, [rip+disp32]`), and `Starfield - Interface.ba2` yields three registered map menu names:

| Menu Name | `.rdata` String RVA | PE File Offset | Code Reference RVA(s) | Interface Movie | Role |
|---|---|---|---|---|---|
| `GalaxyStarMapMenu` | `0x4C96340` | `0x4C95940` | `0x253CFE7` (`UIStringHolder`), `0x16AA5A2` (`MENU_NAME`) | `galaxystarmapmenu.swf` | Galaxy, system, AND planet inspect/scan views (`StarMapMenuPlanetInspectData` at RVA `0x4C92988`, `StarMapMenu_ScanPlanet` at RVA `0x4C97450`) |
| `SurfaceMap` | `0x4C95178` | `0x4C94778` | `0x16989F2` (`MENU_NAME`), `0x22E3402` (UI message sender) | `surfacemap.swf` | Local/planetary surface map (`G` from star map or surface map binding) |
| `MapMenu` | `0x4D7E010` | `0x4D7D610` | `0x253D3F7` (`UIStringHolder`) | — | Legacy `UIStringHolder` map menu slot |

### Non-Existent / Non-Menu Names Checked Offline

- **`PlanetMapMenu`**: `0` occurrences in `Starfield.exe` and `0` occurrences in `Starfield - Interface.ba2`. Planet inspection and scanning live inside `GalaxyStarMapMenu`.
- **`SurfaceMapMenu`**: Not a standalone registered menu name. `SurfaceMapMenu_*` appears only inside C++ `BSTGlobalEvent` template RTTI names (for example `SurfaceMapMenu_EnablePointCloud` at RVA `0x4C98DA0`); the registered menu string itself is **`SurfaceMap`**.

## 3. Native Creation & Fallback Block (`FO4SFPipboyMenu`)

- `sfse/FO4SFPipboyMenu/src/pipboy_map.cpp` raises `kMaxMapMenus` from `8` to `16` and installs per-slot `BlockedStarMapCreateSlot<0..15>` creators on every matching entry in `RE::UI::menuMap`.
- Generated stage INI (`scripts/ui/make_pipboy_stage_ini.py`) sets:
  ```ini
  MapMenus=GalaxyStarMapMenu,SurfaceMap,MapMenu
  MapBlockStarMap=1
  ```
- When any caller attempts to instantiate a menu in `MapMenus=`, the replacement creator constructs an empty `RE::Scaleform::Ptr<RE::IMenu>` and logs:
  ```text
  step=starmap_blocked n=<k> blocked menu=<MenuName> route=create
  ```
- As a secondary safety net on the main thread, `SuppressVanillaMapMenus()` sends `kHide` if any menu in `MapMenus=` reports `IsMenuOpen` (`step=map_suppress n=<k> name=<MenuName> sent=hide`) without reopening `FO4SF_PipboyMenu`.
- **Verification status (`LEAD`):** Returning an empty `Ptr<IMenu>` from `route=create` is built offline and must be verified in game by pressing each map key once and confirming zero crash before shipping as proven. Starfield's `InventoryMenu`, `StatusMenu`, `BSMissionMenu`, and `SkillsMenu` remain unblocked until Pip-Boy `INV` and `DATA` pass in game so the player never loses access.
