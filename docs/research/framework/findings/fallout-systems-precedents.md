# Fallout systems: community precedents in Starfield (and sister games)

Author: fallout-systems-precedents (Claude, framework research), 2026-10-19. Labels: **verified** (read in the linked
source), **supported hypothesis**, **unresolved**. Builds on, and does not repeat, the engine-mechanics notes
`ui-pipboy-hud-menus.md`, `vats.md`, `power-armor.md`, `workshop-and-settlements.md`, `radio-music-sound.md`,
`starfield-systems-to-reuse.md`.

**Bottom line.** By October 2026 the Starfield community has working precedents for almost every Fallout system
except two: **no furniture-based power armor and no real VATS mode exist on Starfield** (only time-scale hotkeys and
outfit "exosuits"). Everything else has a pattern we can copy. (1) **UI comes in three proven stacks**: pure SWF/GFX
replacement in `Data\Interface` with an INI the SWF reads (StarUI, Astral UI, AstraHUD, Venworks HUD; no SFSE, even
ships to Xbox via Creations), and two **SFSE HTML overlay frameworks**, OSF UI (WebView2, Papyrus + C++ API, menu
manifest with `pausesGame`/`capturesInput`) and Carbon UI (Ultralight, C API). A Pip-Boy built as an HTML view
opened by an inventory item is already demonstrated by Starcade OS. (2) **Radio and music can bypass Wwise entirely**:
three SFSE plugins decode MP3/OGG/FLAC/WAV themselves, one with positional fade and outpost-buildable radios. (3)
**Survival, SPECIAL, perks and legendaries** are done as ordinary plugin data plus light Papyrus, and the SPECIAL mod
shows the hard limit: without a UI bridge, Papyrus cannot push numbers into Starfield's menus, so the author fell back
to terminal menus. (4) The FO4 community's VATS rewrites show that **any VATS replacement must re-implement the
VATS perks**, because entry points tied to the engine mode stop firing. The main risks are SFSE/framework version
pinning (Carbon UI pins one exact game build), single-maintainer frameworks, and SWF-replacement conflicts with the
UI mods our users already run.

## Findings

### F1. Starfield UI modding: what the community actually does

| Stack | Example (Nexus SF id) | How it works | Needs | Label |
|---|---|---|---|---|
| Pure SWF/GFX replacement | Astral UI (16405), v1.8.1, Cybernav, 2026-04/06 | Replaces `inventorymenu.swf`, `containermenu.swf` etc. in `Data\Interface\`; no ESP/ESM; settings in `AstralUI.ini`, applied on menu reopen; translations under `AstralUI_Translations\`; optional SFSE plugin for in-game editing | `StarfieldCustom.ini` `[Archive] bInvalidateOlderFiles=1`, `sResourceDataDirsFinal=` | verified ([page](https://www.nexusmods.com/starfield/mods/16405)) |
| SWF + INI read by the SWF | StarUI Inventory (773) by m8r98a4f2 | "No plugins or quests"; options in `Data\Interface\StarUI Inventory.ini` | none beyond loose files | verified via translation page ([797](https://www.nexusmods.com/starfield/mods/797)) |
| External configurator | StarUI Configurator (5467) | An `.hta`/HTML tool that writes the StarUI INI files; reopen menu or save/load to apply; "open configuration API" for profiles | Windows `.hta` or browser | verified ([page](https://nexusmods.com/starfield/mods/5467)) |
| HUD replacement, XML-driven | Venworks Customizable HUD (17104), 2026-05/09 | Replaces `hudmenu.gfx`, `hudmenu_lrg.gfx`, `hudmessagesmenu.gfx`, `hudmessagesmenu_lrg.gfx`; each ships as GFX **and** SWF in the BA2; a `venworkscui.swf` runtime; layout/palette XML in `Interface\VenworksCUI\`; radar, compass, exposure bars; ships to **consoles via Creations** | ESM + BA2, or fully loose | verified ([page](https://www.nexusmods.com/starfield/mods/17104)) |
| Ship HUD, INI-driven | AstraHUD (15507) | Loose SWFs in `Data\Interface`; AS code in `shipreticle.swf`; per-panel INI; refresh by re-sitting in the pilot seat | loose-file INI | verified ([page](https://www.nexusmods.com/starfield/mods/15507)) |
| Hand edit in JPEXS | Remove HUD as you wish (4655), 2023 | Edit `playerhudcomponents_lrg.gfx`, `shipreticle_lrg.swf` in JPEXS, delete frame icons, keep DefineSprite | JPEXS | verified ([page](https://www.nexusmods.com/starfield/mods/4655)) |
| HTML overlay framework (WebView2) | OSF UI (17711) by ozooma10, v2.0, 2026-07/10 | Edge WebView2 renderer; Papyrus API or C++ SFSE plugin; Papyrus and JS push forms to each other (v1.3); `manifest.json` per view with `entry`, `kind` (menu/HUD), `capturesInput`, `pausesGame`, `launcher`; HUDs are passive overlays; DevTools (F12) and hot reload in dev mode; no ESM | SFSE, Address Library, OSF Settings (its MCM), WebView2 runtime | verified ([page](https://www.nexusmods.com/starfield/mods/17711)) |
| HTML overlay framework (Ultralight) | Carbon UI (17899) by Squeetsquib/CarbonNode, v0.11.0, 2026-08/10 | Ultralight 1.3 (WebKit) drawn in the game's UI render pass; works with DLSS/FSR3/XeSS frame gen; input captured as DOM events; C-style API resolved through SFSE messaging (soft dependency); `window.carbonui.call` bridge; `SetFreeze` (pause world) experimental; **author says AI-generated, lightly tested**; no Papyrus mentioned | **exact** game 1.16.244 + matching SFSE, Address Library, 4 Ultralight DLLs copied next to `Starfield.exe` by hand | verified ([page](https://www.nexusmods.com/starfield/mods/17899)) |
| SFSE plugin SDK | Ez-SFSE-Plugins (14577) | SFSE SDK mirror building with VS2022; notes SDK moved to CMake | SFSE | verified ([page](https://www.nexusmods.com/starfield/mods/14577)) |
| SWF + SFSE for widescreen | Faster Menu Fix (16990), 2026 | Menus at 60 FPS (120 crashed in v1), shorter fades; Ultrawide variant needs `sfse_loader.exe`; built-in StarUI patches; Astral UI patch conflicts with StarUI HUD/Inventory | SFSE for ultrawide only | verified ([page](https://www.nexusmods.com/starfield/mods/16990)) |

Further UI facts:
- Starfield's current build named by mods: **1.16.244 (11 June 2026)**, after the "Free Lanes" update (Astral UI and
  Carbon UI pages). **verified**.
- A modder who decompiled Starfield SWFs with JPEXS reported some are an **older SWF format than Fallout 4's**; the
  Papyrus VM gained new `Guard*` lock opcodes. Forum claims, **supported hypothesis**
  ([forum](https://forums.nexusmods.com/topic/13087164-it-looks-like-bethesda-will-keep-using-scaleform-for-starfield-ui)).
- **Windows "blocked file" trap**: files downloaded from Nexus, "especially flash files in Data\Interface", can be
  silently ignored until unblocked (`Unblock-File`) ([loose-files article](https://www.nexusmods.com/starfield/articles/578)).
  **verified** as documented; mechanism (Mark of the Web) is my **supported hypothesis**.
- **Archive packing**: Archive2 ships with the CK at `Starfield\Tools\Archive2\Archive2.exe`; the article recommends an
  uncompressed General archive for Interface files, DDS/LZ4 for textures; BA2s whose name starts with a loaded
  plugin's name load automatically; loose files carry a growing performance cost, textures worst; loose files may be
  read from either `<game>\Data` or `Documents\My Games\Starfield\Data`, and mixing the two can make the game ignore
  one ([article 578](https://www.nexusmods.com/starfield/articles/578)). **verified** as documented.
- Plugin loading without the Creations menu: SFSE + "Plugins.txt Enabler", or up to 10 `sTestFile` entries
  ([article 303](https://nexusmods.com/starfield/articles/303)). **verified** as documented.
- Lineage: **m8r98a4f2**, author of StarUI (SF), also made **FallUI** for Fallout 4
  ([Gfinity](https://www.gfinityesports.com/article/starfield-mod-starui-hud-loot-menu-changes)). **verified**. A natural
  community contact for both games' Scaleform.

### F2. Pip-Boy / wrist computer
- **No Starfield Pip-Boy mod was found** in this pass (search returned only FO3/FNV/FO4 pages). **unresolved**
  (search budget ran out; recheck).
- **Closest pattern: Starcade OS (SF 17729, X2357, 2026-07/09)**: a "Starcade Pad" inventory item, delivered by a
  startup quest, opens an HTML/JS UI through OSF UI (or F9); a native SFSE plugin + `x2357starcade.esm` stores state
  in `Documents/My Games/Starfield/Starcade/state.json`; Papyrus runs the item effect; GPLv3 plugin, MIT games, full
  source. **verified** ([page](https://www.nexusmods.com/starfield/mods/17729)). This is a Pip-Boy skeleton: item or
  hotkey, Papyrus glue, HTML menu, native store.
- FO4 precedent for replacing the Pip-Boy's form: **PIP-Pad (FO4 21953)** swaps the wrist Pip-Boy for a handheld
  tablet with ESP + BA2, needs F4SE and MCM, conflicts with every other Pip-Boy mod, and warns not to install before
  leaving Vault 111. **verified** ([page](https://www.nexusmods.com/fallout4/mods/21953)). FNV has the same idea
  (Pip-Boy 2500 handheld, [NV 38844](https://www.nexusmods.com/newvegas/mods/38844), page not read: **unresolved**).

### F3. VATS / slow-motion targeting
- **Starfield already has a slow-time targeting mode**: ship "targeting mode" runs at **0.65x** time; a tweak raises
  it to 0.85x and the author reports 1.0 "seems buggy". **verified** ([SF 8063](https://www.nexusmods.com/starfield/mods/8063)).
  How the tweak is done is not stated (likely a GMST or a spell value: **supported hypothesis**).
- **Global time multiplier works from the console**: "Bullet Time" (SF 939, 2023) binds F2/F3/F4 to
  `setglobaltimemultiplier 0.45 / 1 / 2` through `StarfieldConsole.ini` hotkeys with `[Menu] bUseConsole_Hotkeys=1`
  in `StarfieldCustom.ini`, or AutoHotkey. **verified** as documented
  ([page](https://www.nexusmods.com/starfield/mods/939)). This partly answers vats.md's open `sgtm` check (see
  Corrections).
- Perk precedent: Lively's Enhanced Skills (SF 5928) makes Boost Pack Training rank 4 **slow time while hovering**,
  editing perk entry points in a plain ESM. **verified** ([page](https://www.nexusmods.com/starfield/mods/5928)). So a
  perk/spell can drive time slow without SFSE (**supported hypothesis** for the exact mechanism).
- FO4 precedents for "VATS rebuilt outside the engine mode":
  - **VAFS (FO4 15875, Ashnal, 2016-18)**: real-time slow-mo toggled by an AID item, AP drain over time and per
    attack, slow scales with Perception, manual criticals; pure scripts (one on actor hit, one on the `WeaponFire`
    anim event); tunables as GLOBs; holotape settings; crit meter needs **HUDFramework**. **verified**
    ([page](https://www.nexusmods.com/fallout4/mods/15875)).
  - **Bullet Time VATS VR (FO4 72502, Cobal, 2023)**: says the common bullet-time conversions "break perks and
    hit-based effects"; reworks Concentrated Fire (flat limb damage, per-limb tracking "too heavy on the script
    engine"), Gun Fu (count kills, no target list), Critical Banker (raise crit chance instead of banking). Needs F4SE.
    **verified** ([page](https://www.nexusmods.com/fallout4/mods/72502)).
  - **Fallout 76 VATS - F4SE (FO4 102703, 2026)**: real-time VATS as an F4SE DLL + an ESP that redesigns the VATS
    perks + scripts; hit chance from distance, visibility, weapon range and cone of fire, body part; INI settings.
    **verified** ([page](https://www.nexusmods.com/fallout4/mods/102703)).
- Skyrim precedent: **Locational Damage (Skyrim 12615, 2012)**: 14 body zones, criticals, cripple-like effects
  (stagger, disarm, paralysis) by Papyrus + ESP + SKSE (armor per zone via `getArmorRating()`), MCM config; warns that
  latent `Cast()` queues scripts and stacks at load. **verified** ([page](https://www.nexusmods.com/skyrim/mods/12615)).
  Pattern for limb targeting with no VATS camera at all.
- Skyrim pattern "prototype in data, then move it into the engine": **Wade In Water Redone (SSE 71418)** keeps the old
  mod's magic effects for animation compatibility but neutralises them and applies the slow in an SKSE plugin.
  **verified** ([page](https://www.nexusmods.com/skyrimspecialedition/mods/71418)).

### F4. Power armor
- Still **no furniture-based or skeleton-swapping PA mod on Starfield** found. **unresolved** (recheck).
- What exists: outfit exosuits filling spacesuit + helmet slots on the standard human skeleton (District 9 Prawns,
  SF 14443, 2025; crafted at the Industrial Workbench). **verified** ([page](https://www.nexusmods.com/starfield/mods/14443)).
  Fallout 42 Power Armor (SF 6038) is the same kind (power-armor.md).
- The 2024 "pilotable mech" was made by **Jared Kohr** by attaching the existing Vasco mech-parts mod to a Model A
  robot and turning the player into it with "a customized version of Skyrim's polymorph spells", "a little crude".
  **verified** ([Starfield Portal](https://starfieldportal.com/article/player-finds-out-how-to-turn-starfield-character-into-mechs),
  [TweakTown](https://www.tweaktown.com/news/95288/starfield-modder-adds-pilotable-mechs-to-the-game-great-news-for-fallout-power-armor-fans/)).
  So a **polymorph (race-swap magic effect) works on the Starfield player** for a non-human body: **supported
  hypothesis** (video only; no released mod found).
- **OSF Animation (SF 17457, ozooma10, 2026-07)**: SFSE native scene engine on CommonLibSF; plays synced multi-actor
  `.af` / GLTF / GLB animations, controls camera, locks controls, hides/restores equipment, Wwise audio with
  subtitles; JSON scene graphs; Papyrus API (`OSF.*`); adapted from NAF. **verified**
  ([page](https://www.nexusmods.com/starfield/mods/17457)). A candidate engine for PA enter/exit clips and later FO4
  animations (an inference; animation is another thread's area).

### F5. Settlements / outposts
- Only settlement *content* mods were found (e.g. New Homestead - New Dawn, SF 16325: a scriptless small-master
  plugin that disables, not deletes, vanilla objects and avoids navmesh edits). **verified**
  ([page](https://www.nexusmods.com/starfield/mods/16325)). **No Starfield equivalent of FO4 settlers, happiness or
  attacks found** (**unresolved**; search budget ran out before checking outpost-crew mods).
- Closest systems precedent: **Trade Wars Gates of Janus (SF 16871, 2026)**: a station "fed" by breaking down loot
  (weapons, junk, food) against cycle quotas with stat penalties, scrap tokens, a buildable **Deconstruction Box** at
  ship/outpost/home. **verified** at feature level ([page](https://www.nexusmods.com/starfield/mods/16871)). Shows a
  junk-to-resource loop and a rules layer running on outposts; implementation not described.
- FO4's own big rules-layer precedent, Sim Settlements 2, could not be read this pass: **unresolved**.

### F6. Radio and music
| Mod | How | Notes | Label |
|---|---|---|---|
| Starfield Galactic Radio (SF 3775, n00854180t, 2023) | SFSE DLL `StarfieldRadio.dll` + `.toml`; local MP3s in a `tracks` folder or stream URLs; credits CommonLibSF and ConsoleCommandRunner (`ExecuteConsole` address); source on GitHub ChairGraveyard/StarfieldRadio | plays independent of game audio: **keeps playing through menus and loading screens**; media keys desync its volume | verified ([page](https://www.nexusmods.com/starfield/mods/3775?tab=docs)) |
| The Other Starfield Radio (SF 10286, 2024) | **station pack as data** for Galactic Radio: a `.toml` in `Data/SFSE/Plugins` + tracks folder; AI (ElevenLabs) DJ voices | shows "stations as content on a framework" | verified ([page](https://www.nexusmods.com/starfield/mods/10286)) |
| Star Radio Player (SF 16135, comespm, 2026) | `star_radio.esm` + BA2 (models, SFX) + `RadioSFSE.dll` + INI; MP3/OGG/FLAC/WAV, streams, YouTube via yt-dlp; portable radios and headsets crafted at the Industrial Workbench; **fixed radios placed through the outpost/ship build menu**; **placed radios fade with distance and pan**; **music lowers during dialogue**; station folders with jingles/ads by filename prefix; Papyrus trace logs | the closest thing to FO4's world radios; positional audio done in the DLL, not Wwise | verified ([page](https://www.nexusmods.com/starfield/mods/16135)) |
| Starfield Radio - Carbon UI (SF 17900, 2026) | SFSE DLL on Carbon UI; streams starfieldradio.com; HUD now-playing widget; custom MP3 station via a local web server; "touches zero game state", no Papyrus, no save footprint | | verified ([page](https://www.nexusmods.com/starfield/mods/17900)) |

### F7. Survival (hunger, thirst, sleep, radiation)
- **Vanilla Starfield has a "Sustenance" gameplay setting** (Positive Only / Positive & Negative) built on magic
  effects, with three hydration/nourishment tiers that Bethesda set to tier 2 for all items; it unlocks after meeting
  Barrett on Vectera; Survival Sandwich (SF 9485) re-tiered it in CK as a light ESM; waiting/sleeping side effects.
  **verified** ([page](https://www.nexusmods.com/starfield/mods/9485)). The Gameplay Options menu also has options for
  environment, sleep, addiction, food and water ([Prima](https://primagames.com/gaming/how-to-turn-off-survival-options-in-starfield-food-environment-and-more)).
  **verified** at category level; exact names and update **unresolved** (page rate-limited).
- **Stellar Needs (SF 12970, 2026)**: standalone hunger/thirst/fatigue 100 -> 0 in five stages, effects added to the
  food items' forms (so it conflicts with item edits), **replaces vanilla Sustenance which must be off**, uninstall
  toggle that stops scripts and unregisters updates. **verified** ([page](https://www.nexusmods.com/starfield/mods/12970)).
- **Peak Performance - Immersive Needs (SF 12420, rbtRvlt, 2024-26, CC BY-SA, open source, also on Creations)**:
  hunger 8 h, thirst 5 h, rest 14 h stages; thirst drives O2 recovery; "Tension" pauses needs in dangerous locations;
  food classified by **vanilla keywords** (so mod food works), alcohol/chems by FLST; vanilla records untouched;
  starts after the first sleep; credits Skyrim's Last Seed. **verified** ([page](https://www.nexusmods.com/starfield/mods/12420)).
- Radiation as a player meter: **no Starfield rads mod found** (**unresolved**). Starfield has environmental
  exposure bars for hazard categories that HUD mods already redraw (Venworks).

### F8. Perks, SPECIAL, leveling, legendaries, crafting
- **VaultTec S.P.E.C.I.A.L. System (SF 13025, Chaosnhatred, part of "Project Regenesys", 2025)**: attributes shown in
  the status menu under Character; points allocated **through terminal menus** on a "Regenesys Assistant" dataslate,
  "a workaround until scripts can pass information to the UI without sideloading"; bonuses via perks and skill
  patches; skill-patch textures regenerated for Xbox; GitHub mirror (HelixTechGroup). **verified**
  ([page](https://www.nexusmods.com/starfield/mods/13025)). A follow-up (SF 15073) moves the SPECIAL perks to the
  master row and says perks stay active there. **verified** ([page](https://www.nexusmods.com/starfield/mods/15073)).
- Lively's Enhanced Skills (SF 5928): a plain ESM editing perk entry points, conditions, values (e.g. Multiply ->
  Set Value), FOMOD with a no-challenges option. **verified**. Author also made FO4's Magnum Opus.
- **Legendaries**: Legend 'O' Matic + "expanded" patch (SF 17225, 2026) attach legendary effects to slots at a
  workbench, add 4th-slot effects, extract effects for resources; small-master ESM made in CK 1.16.242 + xEdit 4.1.5p.
  **verified** ([page](https://www.nexusmods.com/starfield/mods/17225)). Confirms Starfield's slot-based legendaries are
  data-moddable (starfield-systems-to-reuse.md already proposes LGDI reuse).
- **Junk breakdown**: Trade Wars' Deconstruction Box (F5). No FO4-style "every junk item has components" overhaul was
  read. **unresolved**.

### F9. Fallout-themed content already on Starfield
- Vault-Tec / Nuka-Cola credit sticks and digipicks (SF 3905): a **texture replacer** with no plugin. **verified**
  ([page](https://www.nexusmods.com/starfield/mods/3905)). Fallout food/drink replacers and outfits exist (search hits,
  not read).
- **Vault 77 Alternate Start (SF 7260, 2023)**: an alternate start shipped **as a save file** ("extract save file and
  load"), not a plugin. **verified** ([page](https://www.nexusmods.com/starfield/mods/7260)). Relevant to Phase 1 (see
  Q1).
- Some Nexus authors forbid converting their assets to other games (District 9 Prawns). **verified**. Not a problem
  for us (we ship no assets) but rules out pulling in community assets.

## Precedents and what they teach us
1. **Data-driven UI with an INI/XML sidecar is the norm** (StarUI, Astral, AstraHUD, Venworks). Our launcher could
   write a Pip-Boy/HUD config file instead of patching SWF bytecode per user.
2. **SWF replacement collides.** Every HUD/inventory replacer conflicts with every other that touches the same movie
   (Astral vs StarUI, Venworks vs HONKCORE). New menus/overlays (OSF UI, Carbon UI, SFSE `RegisterMenuMovieCreated`)
   avoid that; replacing `hudmenu.gfx` invites it.
3. **HTML overlays are now the fast route for new menus** (Starcade OS, Starfield Radio, OSF Animation browser). They
   cost an SFSE dependency, a framework dependency, and for OSF a WebView2 runtime; Carbon UI pins one exact game build.
4. **Papyrus cannot feed vanilla menus**; the SPECIAL mod proves the wall and shows the cheap fallback (terminals /
   message boxes). A Pip-Boy STAT page therefore needs a UI bridge (OSF UI's Papyrus API, or our own SFSE plugin).
5. **VATS rewrites break perks** unless they re-implement them (VAFS, VR Bullet Time, F76 VATS all redesign the same
   ~7 perks). Plan the perk list together with the mode.
6. **Audio outside Wwise works and ships today** (three radio DLLs), with known side effects: plays through menus and
   loading screens, ignores game volume sliders unless the DLL handles them, separate ducking logic.
7. **Survival layers sit best on vanilla keywords** (Peak Performance) and conflict when they add effects to item
   records (Stellar Needs). Vanilla Sustenance is a switch the player owns.
8. **Script first, native later** (VAFS -> F76 VATS F4SE; Loki's Wade in Water -> SKSE Redone): prove behaviour in
   Papyrus, move hot paths to a DLL.
9. **Frameworks with soft dependencies** (Carbon UI resolves its API via SFSE messaging so dependants still load)
   are a good model for our own SFSE plugin.

## Risks
- **R1 Framework abandonment / version pinning** (likely): Carbon UI is AI-generated, lightly tested, pinned to
  1.16.244; Galactic Radio needed a "reupload for game update"; Faster Menu Fix v1 crashed at 120 FPS menus. Every
  Starfield patch can break SFSE plugins until Address Library and SFSE update. Depending on a third-party UI framework
  multiplies this.
- **R2 UI conflicts with users' existing mods** (likely for HUD replacement, low for new overlay menus): our HUD
  changes (Geiger, rads, compass) would collide with StarUI HUD, Venworks, HONKCORE.
- **R3 WebView2 / Ultralight footprint** (medium): extra runtime install, GPU cost, frame-gen interplay (Carbon fixed
  FSR3 white screens); unknown cost while the GPU is reserved for game tests.
- **R4 Licences** (medium): OSF UI licence not read; Star Radio, Galactic Radio licences not read; Starcade is GPLv3
  (compatible with our GPL-3 Mutagen notice). Bundling or forking needs each licence checked.
- **R5 No PA / VATS precedent** (certain): we would be first; effort estimates have nothing to lean on.
- **R6 Blocked downloaded SWFs** (medium for Nexus release): Windows may silently ignore downloaded Interface files.
- **R7 Off-Wwise audio** (medium): radio music outside Wwise ignores pause, menu volume and occlusion unless we code it.

## Questions for the framework

### New game
1. **Should the Vault 111 start offer a save-file fallback like the Vault 77 Alternate Start (SF 7260)?** Why: that mod
   skipped the intro by shipping a save, not a quest. Options: our quest start (plan); a generated save as a debug
   shortcut; both. Evidence: can the launcher produce a save legally and portably (saves embed plugin lists)? Who:
   owner decision + PC probe.
2. **Is Starfield's vanilla Sustenance setting on or off in our new game, and does FO4 Survival map to it?** Why:
   needs mods require it off (Stellar Needs) or on (Survival Sandwich); it unlocks after meeting Barrett, a Starfield
   quest we fence out. Options: force off; reuse its magic effects for FO4 food buffs; own system. Evidence: read the
   Sustenance gating (quest/global) in Starfield.esm. Who: offline xEdit.

### Door animations
3. **Can OSF Animation's scene engine play our door enter/exit (and later PA enter) clips, or should we stay on
   furniture markers?** Why: it already plays `.af`/GLTF synced with camera and control locks. Evidence: read its
   source/licence; one test scene. Who: offline research + PC probe (animation thread owns the decision).

### All interiors
4. **Do interior acoustic spaces need to duck an off-Wwise radio?** Why: Star Radio Player does distance fade and
   dialogue ducking in its DLL, not in Wwise. Evidence: its source or behaviour in an interior. Who: PC probe.

### Launcher
5. **Do we ship our UI as loose files or as a BA2 named after our plugin?** Why: loose files cost performance and need
   the `[Archive]` INI edits; BA2s named like the plugin auto-load; Interface BA2 should be General/uncompressed
   ([578](https://www.nexusmods.com/starfield/articles/578)). Options: loose for dev, BA2 for release. Evidence: one
   SWF override test both ways. Who: PC probe.
6. **Does the launcher need to unblock files (Mark of the Web) after extracting our release zip?** Why: blocked Flash
   files in Data\Interface are silently ignored. Options: `Unblock-File` step; generate SWFs locally (never
   downloaded). Evidence: a downloaded zip test. Who: PC probe.
7. **Which `Data` folder do we install into (game root vs Documents) and do we detect the other one?** Why: mixing them
   makes the game ignore files. Who: owner decision + launcher check.
8. **Which game build do we pin, and how does the launcher react to a Starfield update?** Why: SFSE DLLs (ours and any
   framework) break per patch; Carbon UI requires exactly 1.16.244. Options: Address Library-only plugin; version check
   with a clear message; refuse to launch. Who: owner decision.
9. **Should the launcher write INI/XML sidecars that our SWFs read (StarUI pattern) instead of rebuilding SWFs?**
   Why: per-user config without bytecode patching. Evidence: confirm how StarUI's SWF reads its INI (decompile). Who:
   offline research.

### World and planet
10. **Can FO4 world radios (Diamond City Radio receivers) be placed objects driven by a DLL with positional fade, like
    Star Radio Player?** Why: avoids Wwise authoring for ~hours of music. Evidence: Star Radio source; how it ties a
    placed ref to its audio. Who: offline research + community contact (comespm).
11. **Does a radio transmitter range (FO4 XRDO) need engine support at all, or can the DLL compute signal by
    distance?** Options: DLL distance check; Papyrus distance + DLL playback. Who: offline design.

### People and story
12. **How do DJ lines (Travis, Three Dog later) play: through our dialogue/voice path (Wwise) or the off-Wwise radio
    DLL?** Why: The Other Starfield Radio bakes DJ talk into tracks; FO4 DJ lines are dialogue with conditions (story
    progress). Who: owner decision + voice thread.

### Fallout systems
13. **Pip-Boy stack: own SFSE menu (Scaleform), OSF UI (HTML), or Carbon UI?** Why: decides dependency count, Papyrus
    access, pause behaviour. Options: OSF UI gives Papyrus API, `pausesGame`, DevTools, an MCM; Carbon is lighter but
    pinned and AI-generated; own Scaleform plugin reuses the player's FO4 Pip-Boy SWF art (ui note). Evidence: a
    one-page "STAT" prototype in OSF UI vs one SWF via `RegisterMenuMovieCreated`. Who: owner decision after a spike.
14. **Can the FO4 Pip-Boy SWF be hosted as-is in Starfield's Scaleform, given reports that Starfield's SWFs are an older
    format than FO4's?** Why: if not, the HTML route wins. Evidence: SWF header version compare (U1 check in the ui
    note). Who: offline (JPEXS on the user's PC).
15. **Pip-Boy trigger: item (Starcade Pad pattern), hotkey, or replacing the Data menu key?** Who: owner decision.
16. **Do we reuse Starfield's ship targeting slow-time (0.65x) machinery for VATS?** Why: it exists and works; the 8063
    tweak suggests it is a tunable value. Evidence: find the GMST/spell the tweak edits (download and read the ESM in
    xEdit). Who: offline research.
17. **Is `setglobaltimemultiplier` callable from Papyrus or only the console?** Why: the console works (SF 939); a
    no-SFSE VATS needs a script path. Options: `ExecuteConsole` from an SFSE DLL (Galactic Radio uses it); Slow Time
    MGEF; native call. Evidence: grep ContentResources.zip `Game.psc`/`Utility.psc`. Who: offline (PC files).
18. **Which FO4 perks must be redesigned for our VATS, and to what?** Why: three FO4 rewrites converged on Concentrated
    Fire, Gun Fu, Critical Banker, Grim Reaper's Sprint, Four Leaf Clover, Blitz, Mysterious Stranger. Options: queue
    VATS (FO4) vs real-time (F76-style, easier without a cinematic camera). Who: owner decision (feel) + design.
19. **Real-time (F76-style) or queued (FO4-style) VATS first?** Why: real-time needs no camera and no queue execution,
    the hardest steps in vats.md. Who: owner decision.
20. **Power armor body: polymorph race swap (proven crude on Starfield for a mech) or `SwitchToPowerArmor` (declared,
    untested)?** Evidence: one polymorph test with a converted PA race; one `SwitchToPowerArmor` call. Who: PC probe.
21. **Is any Starfield modder working on furniture-based exosuits we could coordinate with?** Who: community contact
    (Nexus forums, Starfield modding Discords).
22. **SPECIAL display: can we write SPECIAL into Starfield's status menu like the Regenesys mod did, and how did it get
    there without a UI bridge?** Why: it says attributes appear in the status menu under Character. Evidence: read its
    GitHub mirror. Who: offline research.
23. **Settlements: is there any Starfield outpost-crew mod with settler needs we can learn from, or do we write FO4's
    rules fresh?** Who: offline research (budget ran out here).
24. **Junk: do we make every FO4 junk item scrap at a Deconstruction-Box-style container or only in workshop mode?**
    Who: owner decision.
25. **Survival: keyword-based (Peak Performance) or item-effect-based (Stellar Needs) design for FO4 Survival mode?**
    Why: keyword-based survives other mods editing food. Who: design decision.
26. **Radiation: a new AV + HUD meter (needs UI work) or Starfield's environmental exposure/affliction bars?** Why:
    exposure bars are already HUD-native and moddable (Venworks). Evidence: xEdit hazard AVIFs. Who: offline.
27. **Legendaries: does Legend 'O' Matic's slot model match FO4's one-effect legendaries closely enough to fill LGDI
    with FO4 effects?** Who: offline (xEdit of LGDI + the mod).

### Release and community
28. **Which external frameworks are we willing to require on Nexus (OSF UI, Address Library, WebView2 runtime)?** Why:
    each is a support burden and a breakage point; licences unknown. Who: owner decision after licence check.
29. **Do we coordinate with m8r98a4f2 (FallUI/StarUI), ozooma10 (OSF), Chaosnhatred (SPECIAL)?** Why: users will run
    their mods next to ours; compatibility patches avoid conflicts. Who: owner (outreach is owner-only per AGENTS.md).
30. **Should our HUD changes avoid replacing `hudmenu.gfx` entirely (overlay only) to stay compatible with StarUI
    HUD / Venworks?** Who: design decision.

### Tooling and testing
31. **Do we build SFSE plugins with CommonLibSF (used by OSF Animation, Galactic Radio) or the bare SFSE SDK?** Why:
    CommonLibSF + Address Library survive patches better (supported hypothesis). Who: offline research.
32. **Is OSF UI's DevTools/hot reload worth it for fast Pip-Boy iteration without restarting the game?** Who: PC probe.

### Cross-cutting
33. **One project SFSE plugin for all Fallout systems (Pip-Boy data bridge, VATS time, radio audio, PA HUD) or
    several?** Why: every DLL is a patch-day risk; one plugin with soft feature flags (Carbon's pattern) limits it.
    Who: owner decision + architecture note in docs/ai/decisions.md.

## Corrections
- **vats.md** says "no Starfield VATS mod was found ... only timescale mods" and lists `sgtm` as unresolved. Extension:
  `setglobaltimemultiplier` is used by a published mod via console hotkeys (SF 939), and vanilla ship targeting mode
  already slows time to 0.65x (SF 8063). Still no player VATS mod. Sources above.
- **power-armor.md** credits the 2023 mech to "Korodic" (PCGamesN). Starfield Portal and TweakTown name **Jared Kohr**
  and describe a polymorph-spell approach on top of the Vasco mech mod. Either PCGamesN covered a different mech or
  the name differs; **unresolved**, worth one check.
- **ui-pipboy-hud-menus.md** lists OSF UI as "WebView2 HTML overlay" (confirmed) and Carbon UI without details; add:
  Carbon UI is Ultralight-based, pinned to 1.16.244, and self-described AI-generated and lightly tested.

## Gaps (not read this pass)
Web search budget ran out and Nexus then rate-limited fetches (HTTP 429). Not read: rbtUI2 (SF 17873), Starfield
Portal survival-options article, Fallout 42 PA (SF 6038, covered in power-armor.md), Pip-Boy 2500 (NV 38844), FO4
106120; not searched: Sim Settlements 2, PrismaUI (Skyrim), FallUI page, HUDFramework page, Fallout London, FNV-in-FO4
recreations, Starfield outpost-crew and junk-scrap overhauls, SFSE Menu Framework (ImGui) page.

## Sources
- https://www.nexusmods.com/starfield/mods/16405 (Astral UI)
- https://www.nexusmods.com/starfield/mods/797 (StarUI Inventory translation; original 773)
- https://nexusmods.com/starfield/mods/5467 (StarUI Configurator)
- https://www.nexusmods.com/starfield/mods/17104 (Venworks HUD)
- https://www.nexusmods.com/starfield/mods/15507 (AstraHUD)
- https://www.nexusmods.com/starfield/mods/4655 (Remove HUD as you wish)
- https://www.nexusmods.com/starfield/mods/17218 (HONKCORE preset)
- https://www.nexusmods.com/starfield/mods/17711 (OSF UI)
- https://www.nexusmods.com/starfield/mods/17899 (Carbon UI)
- https://www.nexusmods.com/starfield/mods/14577 (Ez-SFSE-Plugins)
- https://www.nexusmods.com/starfield/mods/16990 (Faster Menu Fix)
- https://www.nexusmods.com/starfield/mods/13181 (hidden; points to rbtUI2 17873)
- https://www.nexusmods.com/starfield/mods/17729 (Starcade OS)
- https://www.nexusmods.com/starfield/mods/17457 (OSF Animation)
- https://www.nexusmods.com/starfield/mods/8063 (Less Time in Targeting Mode)
- https://www.nexusmods.com/starfield/mods/939 (Bullet Time)
- https://www.nexusmods.com/starfield/mods/5928 (Lively's Enhanced Skills)
- https://www.nexusmods.com/starfield/mods/14443 (District 9 Prawns)
- https://www.nexusmods.com/starfield/mods/16325 (New Homestead - New Dawn)
- https://www.nexusmods.com/starfield/mods/16871 (Trade Wars Gates of Janus)
- https://www.nexusmods.com/starfield/mods/3775?tab=docs (Starfield Galactic Radio)
- https://www.nexusmods.com/starfield/mods/10286 (The Other Starfield Radio)
- https://www.nexusmods.com/starfield/mods/16135 (Star Radio Player)
- https://www.nexusmods.com/starfield/mods/17900 (Starfield Radio - Carbon UI)
- https://www.nexusmods.com/starfield/mods/9485 (Survival Sandwich)
- https://www.nexusmods.com/starfield/mods/12970 (Stellar Needs)
- https://www.nexusmods.com/starfield/mods/12420 (Peak Performance)
- https://www.nexusmods.com/starfield/mods/13025 (VaultTec S.P.E.C.I.A.L. System)
- https://www.nexusmods.com/starfield/mods/15073 (SPECIAL master-row patch)
- https://www.nexusmods.com/starfield/mods/17225 (Legend 'O' Matic expanded)
- https://www.nexusmods.com/starfield/mods/3905 (Fallout credit sticks)
- https://www.nexusmods.com/starfield/mods/7260 (Vault 77 Alternate Start)
- https://www.nexusmods.com/starfield/articles/578 (loose files and BA2 guide)
- https://nexusmods.com/starfield/articles/303 (plugin loading guide)
- https://forums.nexusmods.com/topic/13087164-it-looks-like-bethesda-will-keep-using-scaleform-for-starfield-ui
- https://www.gfinityesports.com/article/starfield-mod-starui-hud-loot-menu-changes (StarUI HUD, SF 3444)
- https://starfieldportal.com/article/player-finds-out-how-to-turn-starfield-character-into-mechs
- https://www.tweaktown.com/news/95288/starfield-modder-adds-pilotable-mechs-to-the-game-great-news-for-fallout-power-armor-fans/
- https://starfieldportal.com/article/mod-creates-new-starfield-intro-that-involves-earths-vault-77
- https://primagames.com/gaming/how-to-turn-off-survival-options-in-starfield-food-environment-and-more
- https://www.nexusmods.com/fallout4/mods/21953 (PIP-Pad)
- https://www.nexusmods.com/fallout4/mods/15875 (VAFS)
- https://www.nexusmods.com/fallout4/mods/72502 (Bullet Time VATS VR)
- https://www.nexusmods.com/fallout4/mods/102703 (Fallout 76 VATS - F4SE)
- https://www.nexusmods.com/skyrim/mods/12615 (Locational Damage)
- https://www.nexusmods.com/skyrimspecialedition/mods/71418 (Wade In Water Redone)
- https://www.nexusmods.com/newvegas/mods/38844 (Pip-Boy 2500, not read)
