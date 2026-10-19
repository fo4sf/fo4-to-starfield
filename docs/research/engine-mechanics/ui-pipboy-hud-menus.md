# UI: Pip-Boy, HUD and menus (FO4 CE1 vs Starfield CE2)

Part of the engine-mechanics reference ([index](README.md)). Author: Claude-cloud, 2026-10-19. Labels: verified /
supported hypothesis / unresolved.

Routes for the Pip-Boy (SFSE menu plugin, reskin, message boxes) and first proof U1 are in
[../next-phase/animations-ui-and-start.md](../next-phase/animations-ui-and-start.md) section 3. This file adds how
each engine builds its menus and which records feed them.

## In short
- **Both engines draw menus with Scaleform** (Flash SWF + ActionScript): FO4 ships 304 `.swf` in Interface.ba2,
  Starfield 250 `.swf` + 29 `.gfx` + 3 `.json` data providers (**verified**, archive counts). Starfield's
  `almanacmenu.swf` is a CWS v12 SWF (**verified**, next-phase note).
- Menus are **engine-coded**: each SWF talks to a C++ menu class through callbacks and data models. An FO4 SWF's
  look can move; its data calls will not find FO4's game code (**supported hypothesis**).
- **Records that feed UI carry well**: MESG (message boxes) and LSCR (loading screens) exist in both with nearly the
  same fields (**verified**, xEdit). Verdict: **translate**.
- **Pip-Boy, HUD, workshop and dialogue menus**: no Starfield counterpart with FO4's behaviour. Verdict: **rebuild**,
  best as our own SWF behind a small **SFSE** menu plugin (owner allows SFSE).
- Hooks: F4SE gives Papyrus `UI.RegisterCustomMenu/OpenMenu/CloseMenu/Get/Set/Invoke`; SFSE gives a native
  menu interface only (no Papyrus UI script found) (**verified**, source files).

## How Fallout 4 does it

### Assets (verified: docs/measurements/fo4_ba2.json)
- `Fallout4 - Interface.ba2`: 546 `.dds`, 304 `.swf`, 4 `.gfx`, 5 `.xml`, string tables. Samples:
  `Interface\BarterMenu.swf`, `Book.swf`, `BSButtonHintBar.swf`, `ButtonBarMenu.swf`,
  `Interface\Exported\RaceSex_menu.gfx`, `TutorialMenu.gfx`. Total 311 `.swf` with DLC.
- Creation Club Pip-Boy skins ship only `.bgsm` materials (e.g. `ccBGSFO4001-PipBoy(Black)`: 5 bgsm), so the
  Pip-Boy 3D device is a mesh with swappable materials and the screen is a render target: **supported hypothesis**.

### Menus (names: supported hypothesis unless marked)
| Menu | Role |
|---|---|
| HUDMenu | compass, health/AP, ammo, quest and location messages, Geiger/rad meter |
| PipboyMenu | STAT (status, SPECIAL, perks), INV (weapons, apparel, aid, misc, junk, mods, ammo), DATA (quests, workshops, stats), MAP (world and local), RADIO; drawn on the 3D Pip-Boy screen, or flat with the Pip-Boy disabled in power armor-style HUDs |
| DialogueMenu | four-option wheel (FO4 player voice; silent in the port) |
| BarterMenu / ContainerMenu | trading, looting (BarterMenu.swf verified) |
| WorkshopMenu | settlement building |
| LooksMenu / RaceSex | character creation (`RaceSex_menu.gfx` verified) |
| LoadingMenu | loading screens from LSCR records |
| MessageBoxMenu | modal MESG boxes |
| TerminalMenu | TERM records, holotapes |
| VATSMenu, LevelUpMenu, CookingMenu, ExamineMenu (workbench) | gameplay menus |

- **Pip-Boy data model**: the engine exposes inventory, quests, map markers, stats and radio stations to the
  PipboyMenu SWF and to the companion app over the network. **Supported hypothesis** (community protocol docs); the
  exact model is engine-internal.
- **Pip-Boy light**: toggled from the Pip-Boy, a light attached to the player: **supported hypothesis**; exact record
  **unresolved**.
- **Radio tab** lists stations whose transmitter references are in range (see [radio-music-sound.md](radio-music-sound.md)).
- Actions `APR0`/`APR1` "Action Pipboy Radio Off/On" (AACT) and RACE subgraph role "Pipboy" exist: **verified**,
  xEdit wbDefinitionsFO4.pas. The raise-arm animation is a Pipboy-role subgraph: **supported hypothesis**.

### Records (verified: xEdit wbDefinitionsFO4.pas; counts fo4_esm.json)
| Record | Count | Fields |
|---|---|---|
| MESG | 1,301 | DESC text, FULL title, QNAM owner quest, DNAM flags (bit 0 Message Box), TNAM display time, SNAM SWF, NNAM short title, menu buttons (ITXT text + conditions) |
| LSCR | 358 | DESC, conditions, NNAM loading-screen NIF (STAT/SCOL), TNAM transform, ONAM rotation, ZNAM zoom, MOD2 camera path |
| TERM | 778 | terminal menus |
| DLBR / DLVW | 132 / 1 | dialogue branches / views (DLVW is FO4-only) |

FO4 loading screens are 3D models with rotation and zoom, not images.

### Script hooks
- Vanilla Papyrus: `Debug.MessageBox` and `Message.Show` drive message boxes (**supported hypothesis**; grep FO4
  sources for exact signatures and any Pip-Boy functions).
- **F4SE** (verified, ianpatt/f4se `f4se/PapyrusUI.cpp`): script `UI` with `RegisterCustomMenu(menuName, menuPath,
  rootPath, MenuData)`, `OpenMenu`, `CloseMenu`, `IsMenuOpen`, `IsMenuRegistered`, `Get`, `Set`, `Invoke`, `Load`;
  `PluginAPI.h` has `F4SEScaleformInterface` for native plugins to add ActionScript functions.

## How Starfield does it

### Assets (verified: docs/measurements/sf_ba2.json)
- `Starfield - Interface.ba2`: 250 `.swf`, 114 `.png`, 29 `.gfx`, 29 `.txt`, 3 `.json`, 1 `.bat`. Samples:
  `interface/alertmessage.swf`, `alertmessage_lrg.swf`, `almanacmenu.swf`, `buttonclips.gfx`,
  `explosiveindicator.gfx`, data provider `interface/providers/powersmenudata.json`.
- `_lrg` variants (large text) and JSON "providers" suggest a data-binding layer between engine and SWF:
  **supported hypothesis**.

### Menus (names supported hypothesis unless marked)
| Starfield menu | Closest FO4 menu |
|---|---|
| Data menu (hub: inventory, missions, skills, powers, ship, map) | PipboyMenu |
| Hand scanner (scan, loot preview, outpost build) | none; VATS-like overlay |
| HUD (o2/CO2, health, ammo, compass) | HUDMenu |
| Dialogue (camera close-up, persuasion SPCH) | DialogueMenu |
| Barter / container | BarterMenu / ContainerMenu |
| Outpost build (scanner) | WorkshopMenu |
| Star map | world map (no analogue) |
| Almanac (`almanacmenu.swf`, verified file) | none |
| Terminal (TMLM records, 700) | TerminalMenu (TERM) |

### Records (verified: xEdit wbDefinitionsSF1.pas; counts sf_esm.json)
| Record | Count | Change from FO4 |
|---|---|---|
| MESG | 1,149 | same core; adds ICON, BNAM index chosen on back-out, per-button IBIN event name and DODT reference |
| LSCR | 304 | same core; adds ICON "Loadscreen" (an image path) beside the NIF |
| TERM / TMLM | 368 / 700 | terminals split into TERM + TMLM menu records |
| AACT `APR0`/`APR1` | | "Action Pipboy Radio Off/On" still defined (**verified** xEdit); use in Starfield **unresolved** |

### Script hooks
- **SFSE** (verified, ianpatt/sfse `sfse/PluginAPI.h`, `Hooks_Scaleform.cpp`): `SFSEMenuInterface` v2 with
  `RegisterMenuMovieCreated(callback(IMenu*))` and `RegisterScaleformManagerCreated(callback(BSScaleformManager*))`;
  it hooks `IMenu::LoadMovie`. No `PapyrusUI.cpp` in SFSE (404 on the repo path): Papyrus-level menu control comes from
  community frameworks, not SFSE itself.
- Community UI frameworks: SFSE Menu Framework (ImGui), OSF UI (WebView2 HTML overlay), Carbon UI (next-phase note).

## Mapping for the port
| FO4 piece | Starfield counterpart | Verdict | Notes |
|---|---|---|---|
| PipboyMenu (STAT/INV/DATA/MAP/RADIO) | data menu | rebuild (SFSE + SWF) | data model fed by our plugin; reskin of data menu is the no-SFSE fallback |
| 3D Pip-Boy arm + screen | none | rebuild | mesh converts like other NIFs; the render-to-screen path **unresolved** |
| Pip-Boy light | player light (ARMO/LIGH effect) | script shim | a toggle via a hotkey or menu item |
| HUDMenu (Geiger, rads, compass) | Starfield HUD | reskin / SFSE | compass markers may come free; rads need a new meter |
| DialogueMenu (wheel) | Starfield dialogue | carries | player is silent (settled); Starfield's list UI is acceptable |
| BarterMenu / ContainerMenu | barter / container | carries | data-driven in both |
| WorkshopMenu | outpost build | rebuild | settlement work is "Fallout systems" phase |
| LooksMenu / RaceSex | Starfield character creation | carries / skip | owner decides (next-phase Q3) |
| LSCR (3D model) | LSCR (NIF + ICON) | translate | NNAM model converts as a STAT; ICON can stay empty or point at a rendered image |
| MESG | MESG | data copy + translate | SNAM SWF names differ; button conditions translate |
| TERM | TERM + TMLM | translate | see [terminals-holotapes-locks.md](terminals-holotapes-locks.md) |
| Quest log | data menu missions | carries | quest objectives drive it in both |
| Map | surface map / Pip-Boy map later | rebuild later | see world-maps note |

## What must be rebuilt, and what needs SFSE or the Creation Kit
- **SFSE**: registering a new menu (Pip-Boy) and feeding it data. Without SFSE, only overriding an existing SWF path.
- **Rebuild**: Pip-Boy SWF (built on the player's PC from their FO4 SWF art), radio tab, rad meter, workshop menu.
- **CK2**: not needed for UI except MESG/LSCR authoring, which our plugin writer can do.
- FO4 SWFs are the player's files: read them locally, never ship them.

## Port status and links
- Nothing converted yet. U1 (list ActionScript classes and external calls of FO4's Pip-Boy SWF) is the first proof:
  [../next-phase/animations-ui-and-start.md](../next-phase/animations-ui-and-start.md).
- Map markers and the surface map: [../next-phase/world-maps-lod-fasttravel.md](../next-phase/world-maps-lod-fasttravel.md).
- docs/PLAN.md P5 lists "Pip-Boy/VATS equivalents".

## Open questions and cheap checks
- FO4 SWF list: dump all 304 Interface `.swf` names from Interface.ba2 (PC, read-only) and confirm menu names above.
- Starfield SWF list: same for the 250 SWFs; find the data menu, scanner and HUD files.
- Scaleform version: read the SWF header version of FO4 `PipboyMenu`-like files vs Starfield (CWS v12 known).
- Does the Starfield runtime still accept AS3 `BSScaleformManager` external calls named like FO4's? Grep FO4 SWF
  strings for `root.BGSCodeObj`-style names (decompile with JPEXS, offline).
- Starfield Papyrus: grep ContentResources.zip for `Debug.MessageBox`, `Message.Show`, `UI.` script names.
- Pip-Boy light record: search Fallout4.esm for a LIGH/SPEL named like Pipboy (xEdit, PC).

## Sources
- Repo: docs/measurements/fo4_ba2.json, sf_ba2.json, fo4_esm.json, sf_esm.json.
- xEdit (TES5Edit dev-4.1.6): `Core/wbDefinitionsFO4.pas`, `Core/wbDefinitionsSF1.pas`, https://github.com/TES5Edit/TES5Edit
- F4SE: https://github.com/ianpatt/f4se (`f4se/PapyrusUI.cpp`, `f4se/PluginAPI.h`)
- SFSE: https://github.com/ianpatt/sfse (`sfse/PluginAPI.h`, `sfse/Hooks_Scaleform.cpp`)
- [SFSE Menu Framework](https://github.com/QTR-Modding/SFSE-Menu-Framework); [OSF UI](https://www.nexusmods.com/starfield/mods/17711); [Carbon UI](https://www.nexusmods.com/starfield/mods/17899)
