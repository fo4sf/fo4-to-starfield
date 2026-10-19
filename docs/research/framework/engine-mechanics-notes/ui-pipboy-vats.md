# UI, Pip-Boy and V.A.T.S.: research findings and question framework

Area: ui-pipboy-vats. Author: Claude (research agent), 2026-10-19. Builds on the engine-mechanics pages
`ui-pipboy-hud-menus.md`, `vats.md`, `terminals-holotapes-locks.md` and `../next-phase/animations-ui-and-start.md`
section 3; it does not repeat their record layouts or port verdicts. Labels: **verified** (read on the source page or in
a file), **supported hypothesis** (evidence, not confirmed), **unresolved**. "Page" below means the Nexus or web page in
the source column was read on 2026-10-19; mod pages are the authors' own claims.

## What the community and tools offer today

Current baseline: the frameworks below target Starfield **1.16.244** with **SFSE 0.2.21** and the Address Library for
1.16.244 (**verified**, SFSE Menu Framework README and Carbon UI page). Every SFSE plugin is tied to that game build.

### Four ways to put UI on screen in Starfield
1. **Replace a vanilla Scaleform movie (SWF/GFX) in `Data\Interface`.** The most used route and the only one that also
   reaches Xbox and PS5.
   - StarUI Inventory (Nexus SF 773) v2.5.2, updated 8 Sep 2026: rewrites inventory, container, ship cargo and barter
     screens with Interface files plus an INI; "no plugins and no quests"; needs archive invalidation (**verified**, page).
     https://www.nexusmods.com/starfield/mods/773
   - Venworks Customizable HUD (Nexus SF 17104), beta, updated 1 Sep 2026: replaces the on-foot HUD movies
     `hudmenu.gfx`, `hudmenu_lrg.gfx`, `hudmessagesmenu.gfx`, `hudmessagesmenu_lrg.gfx`; built in Scaleform and
     ActionScript, ships GFX/SWF in a BA2 with an ESM and a loose `layout.xml`; offered on PC, Xbox and PS5 through
     Bethesda Creations; adds a radar, tracked-objective panel and status panels (**verified**, page).
     https://www.nexusmods.com/starfield/mods/17104
   - AstraHUD (Nexus SF 15507) v2.2: ship HUD from replaced SWFs such as `shipreticle.swf`, configured by INI, reloads
     when the player re-seats (**verified**, page). https://www.nexusmods.com/starfield/mods/15507
   - No Scanner Circle and Vignette (Nexus SF 9422) v12: the hand scanner is `monoclemenu.swf` / `monoclemenu_lrg.swf`
     in `Starfield - Interface.ba2`; edited by extracting with BAE and replacing shapes in JPEXS; v12 is "built from the
     1.16.244.0 source files" (**verified**, page). https://www.nexusmods.com/starfield/mods/9422
   - Less Intrusive Scanner (Nexus SF 1545): SWF shapes exported to PNG, edited and re-imported in an SWF editor
     (**verified**, page). https://www.nexusmods.com/starfield/mods/1545
   - Custom Weapon Icon Template (Nexus SF 13816) v2.0.1: since beta 1.15.214 the HUD and Favorites menu load a
     per-weapon icon SWF by linkage name; a builder tool bundles JPEXS FFDec; Ammo HUD v4 reads these icons (**verified**,
     page). This is the first sign that Bethesda opened HUD movies to per-mod content. https://www.nexusmods.com/starfield/mods/13816
   - JPEXS FFDec decompiles Starfield SWFs and "everything you would expect is in there" (**verified**, forum post); the
     Scaleform version number is not stated there (**unresolved**; the project already knows `almanacmenu.swf` is CWS v12).
     https://forums.nexusmods.com/topic/13087164-it-looks-like-bethesda-will-keep-using-scaleform-for-starfield-ui
2. **SFSE plugin that hooks or drives vanilla menus** (PC only).
   - Dynamic Hud (Nexus SF 16590): "a pure SFSE plugin", `HideHUD.dll`, hides HUD widgets until health, ammo, O2 or
     stealth need attention (**verified**, page). https://www.nexusmods.com/starfield/mods/16590
   - Cassiopeia Papyrus Extender (LarannKiar) v6.3: Papyrus natives `OpenMenu`, `CloseMenu`, `DumpMenuFlags`,
     `DisableMenuRenderers`, `SuppressHUDNotifications`, `OpenTextInputMenu`, `GetContainerMenuTarget/Mode/SelectedItem`,
     `IsHUDWatchAlertActive`, `Get3DPosition`, timestamps (**verified** on a mirror page; latest explicit game version
     there is 1.15.222, so 1.16.244 support is **unresolved**).
     https://allmods.net/starfield-mods/starfield-miscellaneous/cassiopeia-papyrus-extender-v1-1/
   - Vanilla Papyrus `RegisterForMenuOpenCloseEvent` works with menu names `DataMenu`, `InventoryMenu`, `FaderMenu`
     (**supported hypothesis**, forum thread; no full Starfield menu name list found).
     https://forums.nexusmods.com/topic/13453810-registerformenuopencloseeventdatamenu
3. **HTML/CSS/JS overlay frameworks** (PC only, new in 2026).
   - Carbon UI (Nexus SF 17899) v0.11.0, 3 Oct 2026: SFSE plugin embedding Ultralight (WebKit) drawn into the D3D12
     swapchain; C ABI header `CarbonUI_API.h` requested over SFSE messaging, so mods can soft-depend; JS bridge
     `window.carbonui.call()`; input captured while a view is focused; GPL-3.0-or-later with an Ultralight linking
     exception; four Ultralight DLLs must sit next to `Starfield.exe`; Better Console listed incompatible (**verified**,
     page). https://www.nexusmods.com/starfield/mods/17899
   - Starfield Radio on Carbon UI (Nexus SF 17900): a station menu on F6, a HUD now-playing widget, custom MP3 stations
     from a local web server, "touches zero game state" (**verified**, page). A working precedent for an FO4-style radio
     tab that is not Scaleform. https://www.nexusmods.com/starfield/mods/17900
   - OSF UI (Nexus SF 17711) v2.0, 2 Oct 2026: WebView2 HTML overlay with GPU rendering and gamepad support; mods ship a
     `manifest.json` and web files and use a **C++ or Papyrus API** to open views, send commands, publish events and
     update state; needs the Edge WebView2 runtime and OSF Settings; licence not named on the page (**verified**, page).
     https://www.nexusmods.com/starfield/mods/17711
   - OSF Animation (Nexus SF 17457) v1.4.0 renders its browser, emote wheel and actor "Picker" through OSF UI
     (**verified**, page): an in-world target picker already exists on this stack. https://www.nexusmods.com/starfield/mods/17457
4. **ImGui overlay.** SFSE Menu Framework (QTR-Modding): ImGui settings panel, GPL-3.0-only with an MIT client SDK,
   register on `kPostLoad`; GitHub shows 26 commits, no releases, 0 stars (**verified**, README). Good for a mod settings
   page, not for an in-fiction Pip-Boy. https://github.com/QTR-Modding/SFSE-Menu-Framework

### Time scale and bullet time
- Console `sgtm` / `setglobaltimemultiplier` works in Starfield: bound to hotkeys through `StarfieldConsole.ini` with
  `bUseConsole_Hotkeys=1` (Nexus SF 939) and used at 0.2 in a hotkey macro (Nexus SF 4348) (**verified**, pages). This
  answers the vats.md open check "does sgtm exist" at the level of mod pages; an in-game check by us is still pending.
  https://www.nexusmods.com/starfield/mods/939 https://www.nexusmods.com/starfield/mods/4348
- Slow Time SFSE (Nexus SF 2952) v1.13.0 for 1.16.244, GPL-3.0 with source on GitHub: manipulates the
  `GlobalTimeMultiplier` with a separate player multiplier (`fPlayerMult`, default 1.0, "keeps player speed not
  changed") (**verified**, page). This is the core of VATS step 1 already solved in open code.
  https://www.nexusmods.com/starfield/mods/2952
- Mojo BulletTime (Nexus SF 15818), Jan 2026: toggle that drains Starborn power and unlocks with the Slow Time power,
  via Console Command Runner (**verified**, page). A precedent for a meter-gated slow time.
  https://www.nexusmods.com/starfield/mods/15818
- **No Starfield VATS mod (body-part targeting with hit chances) was found** on Nexus by two searches (**unresolved**:
  absence of evidence, recheck before design). Results returned only FO4 and FO76 VATS mods.

### Locks, terminals, dialogue, maps
- Auto Unlock SFSE (powerofthree, Nexus SF 5571) v2.0.2 for 1.16.244, open source: auto-unlocks doors, containers and
  terminals when the Security rank meets the lock, spends one digipick; changelog mentions lockpicking events
  (**verified**, page). Shows the lock path is reachable from SFSE. https://www.nexusmods.com/starfield/mods/5571
- CCR Auto Easy Digipick (Nexus SF 2854): makes the digipick game easier with a console command through Console Command
  Runner; console use disables achievements (**verified**, page). https://www.nexusmods.com/starfield/mods/2854
- No mod replacing the digipick minigame with a new minigame, and no terminal hacking minigame mod, was found
  (**unresolved**).
- Dialogue UI: Camera and Dialogue Tweaks (Nexus SF 4687) changes the dialogue camera by `StarfieldCustom.ini` only
  (FOV, skip NPC-to-NPC camera, no depth of field) (**verified**, page); Enhanced Dialogue Interface (Nexus SF 871)
  restyles the dialogue list through an INI (**supported hypothesis**, secondary article).
  https://www.nexusmods.com/starfield/mods/4687
  https://www.gfinityesports.com/article/starfield-mod-enhanced-dialogue-interface-customisable
- Maps: update 1.11.36 (May 2024) "made some big improvements to surface maps", no detail on the page (**verified**,
  bethesda.net). Star map mods exist as an ESM plus SFSE (Nexus SF 4686) and an SFSE plugin (Nexus SF 4347)
  (**verified**, pages). No mod adding a custom local map or a hand-drawn world map for a planet was found
  (**unresolved**). https://bethesda.net/en-US/news/starfield-update-1-11-36-may-15-2024

## Precedents and lessons

- **Skyblivion** keeps Skyrim's list menus for inventory, maps and spells, redesigns the character creation screens and
  writes its own lockpicking minigame (**verified**, TweakTown article). Lesson: a total conversion rebuilds the menus
  that carry identity and lives with the host engine's everyday menus. For us: Pip-Boy and VATS carry identity; barter,
  container and dialogue lists can stay Starfield's.
  https://www.tweaktown.com/news/107458/new-skyblivion-gameplay-video-shows-off-upgraded-lockpicking-new-colorful-menus-remade-gear/images/applenews-v4.png
- **SWF replacers break on game patches.** StarUI Inventory needed a third-party stopgap (Nexus SF 16439) after the Free
  Lanes update while its author was away, and the patch warns against StarUI builds from 6 Sep 2026 (**verified**,
  page). No Scanner Circle is rebuilt "from the 1.16.244.0 source files" (**verified**). Lesson: any vanilla SWF we
  override must be regenerated per game version, so the launcher should build it on the player's PC from their own
  current files, not ship a frozen copy. https://www.nexusmods.com/starfield/mods/16439
- **SWF replacers collide.** Venworks lists every HUD movie it replaces and warns off other mods that touch them
  (**verified**). Lesson: owning `hudmenu.gfx` means incompatibility with all HUD mods; adding our own movie avoids it.
- **FO4 bullet-time VATS rebuilds** (Bullet Time VATS VR, FO4 Nexus 72502): changing VATS ini settings "breaks perks
  and things that are based on hit effects"; Gun Fu was reworked to count kills because the VATS target list is not
  available, Concentrated Fire became flat limb bonuses because per-limb tracking was too heavy for Papyrus, Penetrator
  became armor-ignoring (**verified**, page). Lesson: a rebuilt VATS must re-implement each VATS perk on purpose, and
  heavy per-shot bookkeeping belongs in native code. https://www.nexusmods.com/fallout4/mods/72502
- **Adjustable VATS - F4SE** (FO4 Nexus 94216) v1.5.1 exposes VATS global, player, target and target-phase speeds and
  combines them with Jet-style slow time; names the setting `fVATSPlayerMagicTimeSlowdownMult` (**verified**, page).
  Lesson: FO4 VATS timing is a set of separate multipliers, not one; our rebuild needs at least global and player.
  https://www.nexusmods.com/fallout4/mods/94216
- **F4SE Menu Framework** (FO4 Nexus 105090) is a port of SKSE Menu Framework, as is the Starfield one; it ships a
  "Fallout-inspired" theme and an MCM compatibility layer (**verified**, page). Lesson: the same ImGui stack runs on all
  three games; good for settings, not in-fiction UI. https://www.nexusmods.com/fallout4/mods/105090
- **FallUI FAQ** (FO4): Pip-Boy pitfalls include the PipboyFX screen shader making custom colours dark, blur from
  render resolution, power-armor Pip-Boy brightness, and the gamepad cursor on the Pip-Boy map locking at high
  resolutions (**verified**, article). Lesson: the FO4 Pip-Boy look is a render target plus a post shader; if we
  rebuild it we choose which of those we copy. https://www.nexusmods.com/fallout4/articles/2833
- Fallout London, Tale of Two Wastelands and Capital Wasteland were not researched for UI specifics in this pass
  (they stay inside one engine family); **unresolved** whether any wrote a new Pip-Boy menu.

## Possibilities and hard limits in CE2

- **Possible, no SFSE, all platforms**: restyle any vanilla menu by replacing its SWF/GFX, including the data menu as a
  Pip-Boy look (route 2 of the next-phase note), the HUD (radiation meter, compass restyle), the hand scanner overlay,
  and per-weapon HUD icons (**verified** by the mods above). Data stays Starfield's: a restyled menu shows only what the
  engine already feeds it (**supported hypothesis**; no mod adds new data channels without SFSE).
- **Possible with SFSE on PC**: a new menu with its own data (Carbon UI, OSF UI, or our own plugin via
  `SFSEMenuInterface`), HUD widgets that are not in vanilla movies (Starfield Radio's widget), menu open/close from
  Papyrus (Cassiopeia, OSF UI Papyrus API), slow time with the player at normal speed (Slow Time SFSE) (**verified**).
- **Unresolved**: whether an HTML overlay can sit on a 3D wrist mesh (render to texture) rather than flat on the screen.
  Carbon UI draws into the swapchain as an overlay (**verified**), which suggests flat only (**supported hypothesis**).
- **Unresolved**: whether a brand-new Scaleform movie can be registered as a real engine menu (with pause, input context
  and a menu name Papyrus can see) via `SFSEMenuInterface` alone, or only by hijacking an existing menu class. No public
  Starfield mod doing the former was found.
- **Hard limit for consoles**: SFSE, Carbon UI, OSF UI and every native route are PC only; the settled decision allows
  SFSE, so this only matters if a console release is ever wanted (**verified** for SFSE from mod pages saying SFSE does
  not work on Game Pass, Nexus SF 2854).
- **Hard limit for distribution**: FO4 SWFs are the player's files; Carbon UI's Ultralight DLLs need the game root,
  outside a mod folder (**verified**), which a launcher can handle but a Creation cannot.
- **VATS**: slow time and target picking are solved pieces (Slow Time SFSE; OSF Animation Picker; Cassiopeia
  `Get3DPosition`); hit chance, queued shots with forced aim, kill camera and perk hooks have no Starfield precedent
  (**unresolved**).

## Question framework

Phase names: **new game**, **interiors**, **quests/people**, **Fallout systems**, **release**.

### 1. UI technology route (decides everything below)
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| 1.1 | Which stack builds our new menus: own SFSE plugin + Scaleform SWF, Carbon UI (HTML), OSF UI (HTML, Papyrus API), or ImGui? | Picks languages, licence fit, dependencies, look | All four exist for 1.16.244 (this file); Carbon is GPL-3+ (fits our GPL-3), OSF licence not named | Score each on: GPL-3 fit, Papyrus API, gamepad, can it draw on a 3D mesh, extra runtime (WebView2/Ultralight DLLs), maintenance activity; one-page decision in docs/ai/decisions.md | blocks 2, 4, 8, 11 | Fallout systems | key |
| 1.2 | Can `SFSEMenuInterface` register a new Scaleform movie as a real engine menu (own name, pause, input context)? | Faithful SWF Pip-Boy needs it; else HTML overlay | SFSE hooks `IMenu::LoadMovie` and exposes movie/manager callbacks (ui-pipboy-hud-menus.md); no public mod does a new menu | Read CommonLibSF / SFSE headers for `IMenu` subclassing; ask on the SFSE / Starfield modding Discords; tiny test plugin that opens a blank SWF | blocks 2.1 | Fallout systems | key |
| 1.3 | Do we override vanilla SWFs at all, or only add new movies? | Overrides collide with HUD/inventory mods and break each patch | StarUI broke on Free Lanes; Venworks warns of conflicts (verified) | Policy decision; list which vanilla movies we would need to touch (HUD for rads only?) | 4, 6, release | release | key |
| 1.4 | If we override, does the launcher regenerate the patched SWF from the player's current Starfield files each run? | Avoids shipping Bethesda files and survives patches | Replacers are rebuilt per game version (verified) | Prototype a JPEXS command-line patch of one movie (`monoclemenu.swf` shape hide) from a script | launcher | release | |
| 1.5 | Which Starfield movies are which menus? (full list of 250 SWF + 29 GFX with menu roles) | Needed to target overrides and to find dialogue, barter, lockpick, terminal, map movies | Known: `hudmenu.gfx`, `hudmessagesmenu.gfx`, `monoclemenu.swf`, `shipreticle.swf`, `almanacmenu.swf` (pages above) | Offline BA2 listing on the PC (read-only), then grep each SWF for its document class with JPEXS CLI | 1.3, 5, 6, 7, 9 | Fallout systems | |
| 1.6 | What is the full Starfield menu name list for `RegisterForMenuOpenCloseEvent` / `OpenMenu`? | Scripts that react to Pip-Boy, terminal, lockpick or dialogue menus need names | DataMenu, InventoryMenu, FaderMenu (forum) | Cassiopeia `DumpMenuFlags` in game, or grep Starfield.exe strings for `*Menu` | 3, 9, 11 | quests/people | |
| 1.7 | Is Cassiopeia Papyrus Extender current for 1.16.244 and does its licence allow us to depend on it? | It gives Papyrus menu control without our own plugin | v6.3 has OpenMenu/CloseMenu; last stated game 1.15.222 on a mirror (verified) | Read its Nexus page and changelog | 1.1 | Fallout systems | |
| 1.8 | Who keeps our UI working after each Starfield patch, and how fast? | Every SFSE and SWF route breaks per build | SFSE tied to game version (Carbon page) | Write the patch-day runbook; measure how long SFSE/Address Library took after the last 2 updates | release | release | |

### 2. Pip-Boy as a menu
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| 2.1 | Faithful rebuild (own menu with STAT, INV, DATA, MAP, RADIO) or restyle of Starfield's data menu as a Pip-Boy look? | Biggest UI cost decision | Both routes in next-phase note; restyle works on all platforms but keeps Starfield's tabs and data | Mock both in one page; owner picks; U1 result (FO4 SWF external calls) sizes the rebuild | 1.1, 1.2 | Fallout systems | key |
| 2.2 | For the first playable (new game), what is the minimum: no Pip-Boy, data menu as is, or a restyled data menu? | Breadth before polish; Vault 111 start shows the Pip-Boy pickup | Settled: breadth first | Owner call; check what the new game quests require (Pip-Boy pickup scene in MQ101) | new game quests | new game | key |
| 2.3 | Which FO4 Pip-Boy data can Starfield feed: SPECIAL, perks, limb condition, rads, junk components, holotapes, radio stations? | Defines which tabs need our own data provider | Starfield has skills not SPECIAL; rads and limbs are rebuilds (other pages) | Map each FO4 tab item to a Starfield AV/record or "ours"; table in this repo | special-perks, health pages | Fallout systems | |
| 2.4 | Can the FO4 Pip-Boy SWF art (from the player's files) run inside our chosen stack, or must it be redrawn? | Faithfulness and legal (no shipping FO4 files) | U1 pending; HTML stacks cannot run SWF (supported hypothesis) | U1 offline JPEXS read of FO4 `PipboyMenu`; try exporting its vector art to SVG for an HTML stack | 1.1 | Fallout systems | |
| 2.5 | How does the Pip-Boy open: own hotkey, replace the Tab data menu, or hold Tab? | Input conflicts with Starfield's menu keys and gamepad | Frameworks use F-keys (Carbon F7, Radio F6, Menu Framework F1) | Test key remap of DataMenu open via `RegisterForMenuOpenCloseEvent` + close and open ours | 1.6 | Fallout systems | |
| 2.6 | Pip-Boy light: hotkey toggle of a player light, and does Starfield's helmet/suit light already cover it? | Small shim, frequent use | ui page: shim via light effect | CK test: attach a LIGH effect to player by script | none | Fallout systems | |
| 2.7 | Radio tab: Wwise stations through game audio, or an overlay player like Starfield Radio? | Radio carries identity; determines audio path | Starfield Radio streams outside game audio via Carbon UI (verified) | Read radio-music-sound.md decision; prototype one station either way | radio page | Fallout systems | |

### 3. Pip-Boy as the wrist object
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| 3.1 | Can the Pip-Boy menu be drawn onto a 3D wrist mesh (render target) in CE2, or is it flat on screen only? | The "raise your arm" feel is the Pip-Boy | Carbon UI draws a screen overlay (verified); FO4 uses a render target (supported hypothesis) | Ask SFSE/Carbon authors; look for any Starfield screen-on-mesh effect (ship cockpit screens, terminals) in the Starfield NIF/material data | 1.1 | Fallout systems | key |
| 3.2 | Can the hand-scanner raise-arm animation carry a Pip-Boy mesh on the left wrist? | Reuses Starfield's animation (settled: Starfield animations first) | Scanner is `monoclemenu.swf` overlay (verified); the arm pose behind it unresolved | CK: inspect scanner idle and the first-person arm nodes; test an ARMO on the left forearm slot | animations page | Fallout systems | |
| 3.3 | Is the Pip-Boy a worn item (ARMO with a biped slot) visible in third person and removable? | FO4 lets players hide it; needs a slot that does not clash with suits | FO4: mesh with swappable bgsm (ui page) | Check Starfield biped slots free on spacesuits/apparel; one ARMO test | items page | Fallout systems | |
| 3.4 | Do we keep FO4's Pip-Boy boot sequence and the Vault 111 pickup scene? | New game opening | `ShowPipboyBootSequence` absent in Starfield (papyrus page) | Decide; a scripted image-space and sound may stand in | 2.2 | new game | |

### 4. HUD
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| 4.1 | How do rads, Geiger clicks and the radiation bar appear: new HUD widget via SFSE overlay, or edit `hudmenu.gfx`? | Radiation is core Fallout; touching hudmenu breaks HUD mods | Venworks shows hudmenu edits work; Radio shows overlay widgets work (verified) | Prototype one bar both ways; measure conflict with Venworks | 1.3, health page | Fallout systems | key |
| 4.2 | Can Starfield's environmental hazard display (radiation is already a Starfield hazard) carry FO4 rads without a new widget? | Possibly free | Venworks shows suit protection and hazard panels exist in vanilla HUD data (verified) | In-game: stand in a Starfield radiation hazard and see what the HUD shows; xEdit check of hazard records | health page | Fallout systems | |
| 4.3 | Do we hide Starfield-only HUD parts (O2/CO2 bar, ship indicators, chronowatch) on our planet? | Fence Starfield systems out | Dynamic Hud hides widgets from an SFSE plugin (verified) | Check if HUD visibility can be set per location without SFSE; else small plugin | 11 (AP vs O2) | new game | |
| 4.4 | Are compass map markers and quest markers free on our planet? | Navigation in new game | ui page: compass may come free | In-game test on the converted Commonwealth with one LCTN marker | world-maps note | new game | |
| 4.5 | Quest and location messages ("Location discovered", "Quest updated"): do Starfield's HUD messages read correctly with FO4 text? | Basic feedback | MESG carries (ui page) | In-game check with one converted quest | quests page | quests/people | |

### 5. Dialogue menu and choice list
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| 5.1 | Do we accept Starfield's list UI as is for a silent player, or restyle it? | Settled acceptable; restyle is polish | dialogue page, ui page | None now; revisit at polish | none | quests/people | |
| 5.2 | How do FO4's four-slot prompts (short paraphrase text) show in Starfield's list: one line each, with tone tags (Sarcastic, Question)? | Readability of converted dialogue | FO4 player lines are paraphrased prompts (dialogue page) | Convert 1 FO4 conversation, read it in game | dialogue converter | quests/people | key |
| 5.3 | Do FO4 Charisma speech checks map onto Starfield's persuasion (SPCH) UI or stay plain colour-coded lines? | Speech checks are frequent | Starfield moved speech challenges into SPCH records (README) | Pick 3 FO4 speech checks and prototype both | special-perks page | quests/people | |
| 5.4 | Does the dialogue camera suit FO4 NPCs, or should it default to FO4-style (closer, no cuts)? | Presentation | Camera tweaks are INI-only (verified, SF 4687) | Test INI values; can a plugin set them (GMST vs INI)? | none | quests/people | |

### 6. Barter, container and loot UI
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| 6.1 | Do caps show as a currency in barter, or only as an item? | Economy feel | economy page owns the decision | In-game barter with a converted vendor | economy page | quests/people | key |
| 6.2 | Do FO4 item categories (junk, aid, mods, holotapes) sort sensibly in Starfield's inventory tabs? | Junk-heavy FO4 inventories become unreadable | StarUI shows Starfield's tabs can be rewritten (verified) | Load a FO4-like junk inventory in a test cell; read the tabs | items page | Fallout systems | |
| 6.3 | Do we recommend or support StarUI-style mods, or must our UI work alone? | Compatibility promise | StarUI permissions forbid modification without consent (verified) | Decide stance; test our plugin with StarUI installed | 1.3 | release | |

### 7. Lockpicking, digipick and hacking
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| 7.1 | Do FO4 locks use Starfield's digipick game, or do we build a bobby-pin game? | Hundreds of locks in interiors | XLOC layout identical (terminals page); no digipick replacement mod found | Owner call; digipick costs nothing | items, perks pages | interiors | key |
| 7.2 | Does Starfield's lockpick menu accept FO4's lock levels (Novice to Master) with Security ranks, and what does "Novice" give? | Gates loot in every interior | Same enum (terminals page); Auto Unlock reads rank vs lock (verified) | In-game: three converted locks at three levels | 7.1 | interiors | |
| 7.3 | How do we gate FO4 terminal hacking: digipick on the terminal, a perk check only, or a word-guess game? | 778 FO4 terminals; many locked | No hacking minigame in Starfield found (terminals page); TMLM items have XLOC | In-game: a terminal REFR with XLOC; does it open the digipick game? | 7.1, 9 | interiors | key |
| 7.4 | If we build a word-guess hacking game, which stack (SFSE menu, HTML overlay, or Papyrus message boxes)? | Polish item, but iconic | none in Starfield | Prototype in the chosen stack after 1.1 | 1.1 | Fallout systems | |

### 8. Terminals and holotapes
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| 8.1 | Does the Starfield terminal UI (Windows / Kiosk style) read well for FO4 RobCo text, and can we add a RobCo art theme? | Terminals are everywhere | TERM `NAM1` art themes are a fixed enum (terminals page) | Read the terminal SWF list (1.5); see if a theme is a movie we can add or must override | 1.5 | interiors | key |
| 8.2 | Can a holotape be played from the Pip-Boy, or only as an audio data slate from inventory? | Holotapes drive many quests | NOTE gone; audio slate + scene is the stand-in (terminals page) | Test one audio slate in game | voice note | quests/people | |
| 8.3 | Do we rebuild the holotape games (Atomic Command, Red Menace...) in an HTML overlay? | Fun extra; HTML stacks make it cheap | Carbon/OSF run JS (verified) | Defer; note for Fallout systems polish | 1.1 | Fallout systems | |

### 9. Local map, world map and the Missions menu
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| 9.1 | What does Starfield's surface map show for our planet: generated terrain view with markers, or nothing useful? | FO4 players navigate by the Pip-Boy map | Surface maps were improved in 1.11.36 (verified, no detail) | In-game: open the surface map on the converted Commonwealth | world-maps note | new game | key |
| 9.2 | Can we supply our own world-map image (FO4's Commonwealth map from the player's files) for the planet? | Faithful map | WRLD has `ICON` map image in FO4; Starfield planet map source unresolved | xEdit: Starfield planet/worldspace map fields; ask modders who make new planets | world-cells page | Fallout systems | |
| 9.3 | Do fast travel and "travel from the map" work across one planet without the star map? | Core loop | vehicles page | In-game test with two discovered markers | world-maps note | new game | |
| 9.4 | Do FO4 quest objectives and stages show cleanly in the Missions menu (sorting, Main vs Side, faction tabs)? | Quest log is the player's guide | Quest log carries (ui page) | Convert one main and one misc quest, read the menu | quests page | quests/people | key |
| 9.5 | Does the Missions menu group by faction, and can FO4 factions (Minutemen, Brotherhood, Railroad, Institute) appear as groups? | Owner wants faction mechanics reused | Starfield groups missions by type and faction (supported hypothesis) | Check QUST type field values in Starfield (xEdit) | factions page | quests/people | |

### 10. Shared presentation menus
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| 10.1 | Loading screens: FO4's 3D model screens or Starfield image screens? | First impression | LSCR translates (ui page) | Convert 5 LSCR, view in game | none | new game | |
| 10.2 | Level-up and perk chart: rebuild FO4's Vault Boy chart or reuse Starfield's skill menu restyled? | Big UI if rebuilt | special-perks page owns the system | Decide with 2.1 | 2.1 | Fallout systems | |
| 10.3 | Character creation: Starfield's menu with FO4 presets, or skip? | Vault 111 mirror scene | next-phase Q3 | Owner call | new game | new game | |

### 11. V.A.T.S.
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| 11.1 | Do we build real VATS (queue shots on body parts), a bullet-time "VATS lite", or skip? | Largest Fallout-system UI and combat cost | PLAN non-goal vs ROADMAP C2 (vats.md); FO4 VR mod shows bullet-time VATS is playable with perk rework (verified) | Owner call after 11.2 to 11.4 are cheap-checked | 11.2-11.5 | Fallout systems | key |
| 11.2 | Does Slow Time SFSE's approach (global multiplier + player multiplier) give FO4's VATS feel (world slow, player queue continues)? | Step 1 of VATS | Open GPL-3 code exists for 1.16.244 (verified) | Read its source; in-game try `sgtm 0.2` and the mod | none | Fallout systems | key |
| 11.3 | Can we get body-part screen positions for targeting (BPTD node world position) from SFSE or Cassiopeia? | Target UI needs per-limb points | Cassiopeia has `Get3DPosition` for refs, not nodes (verified); OSF Animation has an actor Picker (verified) | Read CommonLibSF for `NiAVObject` world transform access; ask Cassiopeia author about node position | 1.1 | Fallout systems | key |
| 11.4 | How do queued shots fire at a chosen limb: forced aim, direct damage application, or projectile spawn? | Core of VATS execution | no Starfield precedent (unresolved) | Ask SFSE devs; prototype "apply damage to limb AV" by script as the cheapest fake | 11.3 | Fallout systems | key |
| 11.5 | Does the engine still read VATS perk entry points or GetVATS* conditions if we flag a VATS-like state? | Could save rewriting 25 perks | Fields survive in data (vats.md) | xEdit: any Starfield PERK using entry points 79, 105-153 | special-perks page | Fallout systems | |
| 11.6 | Action Points: reuse Oxygen (sprint drains both), or a new AVIF and HUD bar? | AP is shared with sprinting and VATS | Mojo uses Starborn power as the meter (verified) | Decide with 4.3; check AVIF list | 4.3 | Fallout systems | |
| 11.7 | Kill camera: drop, scripted camera, or later? | Polish, but iconic | OSF Animation controls the camera (verified) | Defer | 11.1 | Fallout systems | |
| 11.8 | Hit chance formula: FO4's (distance, accuracy, Perception, cover) in our code, or simplified? | Balance | vats.md lists inputs | Write the formula from FO4 GMSTs once dumped | 11.5 | Fallout systems | |

## Sources
- Engine-mechanics pages: /mnt/project-files/research/engine-mechanics/ui-pipboy-hud-menus.md, vats.md,
  terminals-holotapes-locks.md, papyrus-and-script-extenders.md; /mnt/project-files/research/next-phase/animations-ui-and-start.md
- Carbon UI: https://www.nexusmods.com/starfield/mods/17899 ; Starfield Radio (Carbon UI): https://www.nexusmods.com/starfield/mods/17900
- OSF UI: https://www.nexusmods.com/starfield/mods/17711 ; OSF Animation: https://www.nexusmods.com/starfield/mods/17457
- SFSE Menu Framework: https://github.com/QTR-Modding/SFSE-Menu-Framework ; F4SE Menu Framework: https://www.nexusmods.com/fallout4/mods/105090
- StarUI Inventory: https://www.nexusmods.com/starfield/mods/773 ; Free Lanes patch: https://www.nexusmods.com/starfield/mods/16439
- Venworks HUD: https://www.nexusmods.com/starfield/mods/17104 ; AstraHUD: https://www.nexusmods.com/starfield/mods/15507 ; Dynamic Hud: https://www.nexusmods.com/starfield/mods/16590
- No Scanner Circle: https://www.nexusmods.com/starfield/mods/9422 ; Less Intrusive Scanner: https://www.nexusmods.com/starfield/mods/1545 ; Custom Weapon Icon Template: https://www.nexusmods.com/starfield/mods/13816
- Scaleform thread: https://forums.nexusmods.com/topic/13087164-it-looks-like-bethesda-will-keep-using-scaleform-for-starfield-ui ; menu names thread: https://forums.nexusmods.com/topic/13453810-registerformenuopencloseeventdatamenu ; JPEXS on the FO4 CK wiki: https://falloutck.uesp.net/wiki/FFDec
- Cassiopeia Papyrus Extender (mirror): https://allmods.net/starfield-mods/starfield-miscellaneous/cassiopeia-papyrus-extender-v1-1/
- Slow time: https://www.nexusmods.com/starfield/mods/2952 , https://www.nexusmods.com/starfield/mods/939 , https://www.nexusmods.com/starfield/mods/4348 , https://www.nexusmods.com/starfield/mods/15818
- FO4 VATS: https://www.nexusmods.com/fallout4/mods/72502 , https://www.nexusmods.com/fallout4/mods/94216 ; F4SE UI script: https://falloutck.uesp.net/wiki/UI_Script
- Locks: https://www.nexusmods.com/starfield/mods/5571 , https://www.nexusmods.com/starfield/mods/2854 , https://www.nexusmods.com/starfield/mods/6399
- Dialogue: https://www.nexusmods.com/starfield/mods/4687 , https://www.gfinityesports.com/article/starfield-mod-enhanced-dialogue-interface-customisable
- Maps: https://bethesda.net/en-US/news/starfield-update-1-11-36-may-15-2024 , https://www.nexusmods.com/starfield/mods/4686 , https://www.nexusmods.com/starfield/mods/4347
- Skyblivion menus and lockpicking (TweakTown): https://www.tweaktown.com/news/107458/new-skyblivion-gameplay-video-shows-off-upgraded-lockpicking-new-colorful-menus-remade-gear/images/applenews-v4.png
- FallUI FAQ: https://www.nexusmods.com/fallout4/articles/2833
