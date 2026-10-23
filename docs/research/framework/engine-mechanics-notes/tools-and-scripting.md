# Tools and scripting: research findings and question framework

Area: the Starfield Creation Kit, Papyrus toolchains, SFSE and its plugin ecosystem, record tools (xEdit, Mutagen,
Spriggit), archive tools, mesh and material tools, Havok and Wwise tooling, converter precedents, and how game updates
break tools. Author: Claude-cloud (framework research agent), 2026-10-19. Labels: **verified** (read on the source page
or in a file), **supported hypothesis** (evidence, not confirmed), **unresolved**.

Builds on, and does not repeat: `../../engine-mechanics/papyrus-and-script-extenders.md` (VMAD layout, native gap of
about 77 names, SFSE 0.2.21 basics, shim plan), `records-and-plugins.md` (condition map, deterministic FormIDs),
`materials-textures-lighting.md` (cloned `.mat`, LMSW blob), `physics-and-collision.md` (hknp packfile to tagfile),
and `../../next-phase/launcher-gamma-model-and-community-tools.md` (licences, TTW model, tool list).

Pages I could not read in this session (the fetch proxy returned HTTP 429, rate limited, and asked not to retry): the
Mutagen GitHub README, the Address Library for SFSE Nexus page (mods/3256), and a Windows Central article on the
Fallout 4 next-gen downgrader. The GitHub API was also closed to this session, so repo licences and release dates
below come from the rendered GitHub pages only. Claims that would have come from those pages are marked unresolved.

## What the community and tools offer today

### Creation Kit and plugin types
- The Starfield Creation Kit came out on 10 June 2024 (Xbox Showcase). **verified**
  ([Nexus news 14993](https://nexusmods.com/news/14993))
- Three master types: a **full master** takes one of 253 load order slots; **medium masters** share slot 254 (`FD`),
  each holds about 65,535 new records, and 256 can load at once; **small masters** share slot 255 (`FE`), each holds
  4,095 new records, and up to 4,096 can load. "Changing the master type in an update will break any patches or other
  mods which use your plugin as a master." **verified** (same page)
- ESP files are meant as work in progress and "currently cause bugs in normal gameplay"; shared mods should be ESM.
  Game 1.12.30 enabled mod loading by default, so Plugins.txt Enabler and SFSE are no longer needed just to load
  plugins. The CK ships VSCode integration for Papyrus. At launch "there is no public documentation for Starfield".
  **verified** (same page)
- The CK must sit on the same drive volume as Starfield, and `Starfield.esm` must be loaded before saving a plugin.
  **verified** ([starfieldwiki, Starfield Creation Kit](https://starfieldwiki.net/wiki/Starfield_Mod:Starfield_Creation_Kit))
- Before the CK, Nexus warned that Starfield treats light and regular plugins as two separate load orders and that
  changing a master's light flag is fragile. **verified** as Nexus's statement of 2 November 2023
  ([Nexus news 14888](https://www.nexusmods.com/news/14888)); whether that still holds after the CK is **unresolved**.
- Lip sync in the Starfield CK is a GUI step: Audio menu, "Run FaceFX Compiler", pick the master, Compile; progress in
  `ffxc_00.log`; it writes `.animset` then `.ffxanim` into the voice folder; no command line is described. **verified**
  ([starfieldwiki, Audio File Conversion](https://dev.starfieldwiki.net/wiki/Starfield_Mod:Audio_File_Conversion)).
  Skyrim's CK had `CreationKit.exe -GenerateLips:YourMod.esm` and `-GenerateSingleLip` **verified**
  ([ck.uesp.net](https://ck.uesp.net/wiki/How_to_generate_voice_files_by_batch)); whether the Starfield CK keeps
  any such switch is **unresolved**. (The project already found `ffxc.exe` and `LipGenerator.exe` in Starfield's Tools
  folder; see `next-phase/voice-lipsync-companions.md`.)

### Papyrus toolchain
- **CK compiler.** SKKMods' "CK Papyrus Compiler command files" (Nexus SF 10320, 1 July 2024) are `.cmd` wrappers
  that call the CK's `PapyrusCompiler.exe` for single files or a prefix batch, debug or release, with sources from
  `ContentResources.zip` and `ReloadScript` for hot reload. The author moved all compiling to the CK compiler because
  Caprica "does not support the GUARD functionality". **verified**
  ([Nexus SF 10320](https://www.nexusmods.com/starfield/mods/10320)). So the CK compiler runs headless from a command
  line: **supported hypothesis** (a batch file calls it; the project has not run it).
- **Caprica** (Orvid): MIT licensed; its README says it compiles "all of the scripts in Fallout 4" and only builds with
  MSVC; Starfield is not mentioned in the README. **verified**
  ([github.com/Orvid/Caprica](https://github.com/Orvid/Caprica)). Champollion's 1.2.1 notes say Starfield output
  reached a state "that Caprica would be modified to accept". **verified**
  ([Champollion releases](https://github.com/Orvid/Champollion/releases)). Net: Caprica parses some Starfield syntax
  but not guards. **supported hypothesis** (two sources agree, no test).
- **Champollion**: v1.3.2 is the latest release; v1.3.1 added Starfield support and marks guessed syntax with `;***`;
  Guard, TryGuard and `ArrayGetAllMatchingStructs` output is experimental. **verified** (same releases page).
- A community wrapper, "bgs-papyrus" (a skill pack on skillsmp.com), drives the installed CK compiler with
  `--backend ck|caprica|russo|auto`, says "Caprica and russo are non-Guard fallbacks", and rewrites Champollion's
  `Guard ... EndGuard` to `LockGuard ... EndLockGuard` (and TryGuard to TryLockGuard), checked by recompiling with the
  real CK compiler. **verified** as stated on
  [the page](https://skillsmp.com/creators/bb-84c/bgs-modding-superpowers/plugins-bgs-modding-superpowers-skills-using-bgs-papyrus);
  what "russo" is I could not find (**unresolved**), and this is one third-party claim (**supported hypothesis** for
  the rewrite rule).
- "Papyrus API" (FrostWyrm98, Nexus SF 7333, v1.2.1, 4 December 2023) wraps Caprica and Champollion in one CLI.
  **verified** ([Nexus SF 7333](https://www.nexusmods.com/starfield/mods/7333)). Old; it predates later guard fixes.
- Starfield's flags file name: not found on any page read (**unresolved**; already an open check in the reference).

### SFSE and native plugins
- SFSE whatsnew, newest first: 0.2.21 (1.16.244), 0.2.20 (1.16.242), 0.2.19 (1.16.236), 0.2.18 (1.15.222), 0.2.17
  (1.15.216: "compiler setting changes in the most recent game patch have changed the code enough to invalidate the
  Address Library"; plugins must declare version 2), 0.2.16 (1.14.74), 0.2.13 (1.14.70: "major changes have been made
  to the root game form class", many plugins need a recompile), 0.2.12 disabled the preliminary serialization API,
  0.2.0 flagged breaking changes in 1.8.86. **verified**
  ([sfse_whatsnew.txt](https://raw.githubusercontent.com/ianpatt/sfse/master/sfse_whatsnew.txt))
- Custom Papyrus natives work in practice: **Cassiopeia Papyrus Extender** (LarannKiar, Nexus SF 10896) is at 9.6,
  version 9.0 targets 1.16.244, 1.3 added "over 350 native events", and since 4.0 it "doesn't use the Address Library
  or CommonLibSF" (its own environment). 4.0 was a rewrite for 1.15.216 and dropped many events; 7.1 and 9.3 fixed
  crashes from "unannounced vanilla" changes in the Free Lanes update. **verified**
  ([Nexus SF 10896 changelog](https://www.nexusmods.com/starfield/mods/10896?tab=logs)). This settles the reference's
  open conflict with Custom Command Framework's page: plugins do register natives. **supported hypothesis** (true for
  Cassiopeia's own approach; whether SFSE's own native API or a custom hook does it is not stated).
- **Starfield Engine Fixes** (LarannKiar, Nexus SF 10457) 21.2, last updated 4 October 2026, supports 1.16.244,
  requires only SFSE, no Address Library, and ships an experimental save cleaner. **verified**
  ([Nexus SF 10457](https://www.nexusmods.com/starfield/mods/10457);
  [Nexus article 702](https://www.nexusmods.com/starfield/articles/702) for the save cleaner)
- **CommonLibSF**: the original repo is archived (read-only since 16 September 2025), badge 1.14.70, "please go to
  libxse/commonlibsf"; the successor needs XMake 3.0+, C++23, MSVC or clang-cl; licence GPL-3.0-or-later with a
  Modding Exception and a GPL-3.0 Linking Exception; "intended to replace SFSE as a static dependency" while the SFSE
  runtime is still required. **verified**
  ([archived repo](https://github.com/Starfield-Reverse-Engineering/CommonLibSF),
  [libxse/commonlibsf](https://github.com/libxse/commonlibsf))
- Address Library for SFSE is by meh321 (**verified**,
  [STEP wiki](https://stepmodifications.org/wiki/Starfield:Address%20Library%20for%20SFSE%20Plugins)); its current
  version and 1.16.244 status are **unresolved** (Nexus page rate limited).
- Bethesda "tries to" give script extender authors an early look at new builds (Todd Howard, reported 17 March 2026),
  "but even that is tricky". **verified**
  ([TweakTown](https://www.tweaktown.com/news/110512/bethesda-gives-script-extender-creators-early-preview-access-of-new-game-updates-to-prepare-fose-and-skse-tools/index.html))

### Record tools
- **xEdit 4.1.5q** (about February 2026, Discord-distributed): Starfield `.esp` editing enabled "with restrictions";
  plugins with a blueprint master cannot be saved; "up to 252 full, 4095 light, and 254 medium masters in one file";
  creating Update files disabled; Starfield form version 581. **verified** as quoted in a snapshot of the r/skyrimmods
  release post ([snapshot](https://reddit.sentinel-team.org/posts/1u6jz38/snapshots/2026-06-16T07%3A02%3A42.6264Z)).
  Builds are on Discord, GitHub builds lag about a year, and some users in 2025 to 2026 reported crashes and believed
  Starfield support had stopped. **verified** as reported in comments
  ([Nexus article 659](https://www.nexusmods.com/starfield/articles/659)); actual status is **supported hypothesis**:
  maintained but hard to obtain.
- **Mutagen**: the project writes Starfield plugins with `Mutagen.Bethesda.Starfield` 0.55.0-alpha.67 (**verified**,
  `dotnet/*.csproj`); its output carries **form version 576** while vanilla is 581, and the game loaded it (**verified**,
  docs/spikes/S2-S4-S9-plugin-units-loading.md). Current upstream status for Starfield is **unresolved** (README not
  readable this session; the launcher note saw 2.8.x prereleases on NuGet).
- **Spriggit** (Noggog): plugins to YAML or JSON, one file per record, CLI `serialize` / `deserialize`, GPL-3.0, WPF UI
  Windows only, CLI needs a .NET runtime. **verified** ([github.com/Mutagen-Modding/Spriggit](https://github.com/Mutagen-Modding/Spriggit)).
  It was built for the Starfield Community Patch (MIT licensed project, released as ESM). **verified**
  ([Nexus news 14877](https://www.nexusmods.com/news/14877)). Starfield coverage completeness is **unresolved**.

### Archives
- Starfield uses BA2 versions 2 and 3; **BAMgr** (Unikko, Nexus SF 14468, 1.4.0, 26 May 2026) creates and extracts v1,
  v2, v3, v7, v8. **verified** ([Nexus SF 14468](https://www.nexusmods.com/starfield/mods/14468))
- "Starfield BA2 Manager and Compressor" (Sonic1SVK, Nexus SF 17849, 1.0, 3 August 2026): Python, MIT, Linux and
  Windows, packs General and DX10. **verified** ([Nexus SF 17849](https://www.nexusmods.com/starfield/mods/17849))
- xEdit 4.1.5q also updated BSArch. **verified** (snapshot above); its Starfield v3 write support is **unresolved**.
- Our own `src/fo4sf/ba2.py` reads v1 and v2, not v3 LZ4 textures. **verified** (file docstring). Archive2 ships with
  the CK (**supported hypothesis**, launcher note).

### Meshes and materials
- **NifSkope fork (fo76utils)**, 2.0.dev11: renders Starfield materials, edits materials "with limitations" for
  Starfield, converts external `.mesh` to internal geometry and back headless, generates mesh LODs; vertex removal may
  break morph files. **verified** ([github.com/fo76utils/nifskope](https://github.com/fo76utils/nifskope))
- **PyNifly**: "Experimental support for Starfield": meshes, materials, facial morphs, facebones; HKX only for FO4 and
  Skyrim; GPL-3.0. **verified** ([github.com/BadDogSkyrim/PyNifly](https://github.com/BadDogSkyrim/PyNifly/))
- **Void SFG Bridge** (Nexus SF 17968, 1.8.10, 20 September 2026), a fork of SesamePaste233's Starfield Geometry
  Bridge: Starfield NIF and `.mesh` import and export, skinning, `morph.dat`, hashed `Data\geometries` paths; "final
  acceptance still requires testing in NifSkope, the Creation Kit, and Starfield". **verified**
  ([Nexus SF 17968](https://www.nexusmods.com/starfield/mods/17968))
- **Material Editor Lite** (Nexus SF 14659, 2.3, 7 August 2026) edits Standard1Layer, StandardTwoSided1Layer and
  ColorEmissive `.mat`, other shaders read-only, batch DDS. **Material Editor Studio** (SF 17879, beta, 8 August 2026)
  adds NIF. **verified** ([SF 14659](https://www.nexusmods.com/starfield/mods/14659),
  [SF 17879](https://www.nexusmods.com/starfield/mods/17879)). A ColorEmissive template answers part of the
  reference's "not done: emissive" gap. **supported hypothesis**
- Layered material swaps are driven by keywords on the **biome or worldspace**, not on the flora; the CK's material
  editor is "way too complicated" for more than recolours. **verified** as one modder's account
  ([blog, 16 Sep 2024](https://thecommabandit.bearblog.dev/learning-to-use-material-swaps/))

### Havok and Wwise
- Wwise for Starfield modders: Audiokinetic Launcher with **Wwise 2021.1.14.8108**, Microsoft platform, project
  conversion "XboxCreation", Convert All Audio Files, output in `.cache/XboxCreation/Voices/English(US)`. **verified**
  ([starfieldwiki, Porting Custom Audio to Xbox](https://dev.starfieldwiki.net/wiki/Starfield_Mod:Porting_Custom_Audio_Files_to_Xbox)).
  WwiseConsole is not mentioned there (**unresolved** whether the launcher can drive Wwise headless).
- No public Havok authoring tool for Starfield physics was found in this session (**unresolved**; the reference's
  physics note says the available tools cover cloth only). The project's own `hktagfile.py` remains the path.

### Converter precedents
- No FO4-to-Starfield or Skyrim-to-Starfield converter tool was found (**unresolved**, searches returned none). The
  "Skywind moves to Starfield as Starwind" story is an April Fools' joke (**verified**,
  [Starfield Portal, 1 April 2024](https://starfieldportal.com/article/the-elder-scrolls-morrowind-remake-shifts-to-starfield-engine)).
  Do not cite it as a precedent.
- Cross-game asset conversions do exist between FO4 and Fallout 76 on Nexus (for example "conversion from Fallout 4"
  power armor pages). **verified** that such pages exist
  ([Nexus FO76 4139](https://www.nexusmods.com/fallout76/mods/4139)); their permission basis is **unresolved**.

## Precedents and lessons

- **Game updates break native plugins, repeatedly.** 1.8.86, 1.14.70 (root form class), 1.15.216 (compiler settings
  invalidated the Address Library) and 1.16.236 (silent data structure changes) each forced plugin rewrites or
  recompiles. **verified** (SFSE whatsnew, Cassiopeia changelog). Lesson: any SFSE plugin we ship needs a pinned game
  version, a fast rebuild path, and a Papyrus-only fallback.
- **Big plugin authors moved off Address Library and CommonLibSF** (Cassiopeia, Engine Fixes since their 2025
  rewrites). **verified**. Lesson: the "standard" stack is not as stable as on Skyrim; ask the authors why before we
  pick a stack.
- **After 1.8.86 players could not launch at all until SFSE and its dependents updated.** **verified** as reported
  ([Nexus forum](https://forums.nexusmods.com/topic/13453760-version-18860-problems)). Lesson: the launcher must detect
  the game version and refuse to start an SFSE-dependent build on an unknown version.
- **Fallout 4's next-gen update (2024) broke F4SE mods and led to a community downgrader.** **supported hypothesis**
  (several headlines: [Windows Central](https://www.windowscentral.com/gaming/roll-back-fallout-4s-horrible-next-gen-update-with-this-nifty-downgrader-mod),
  [Shacknews](https://shacknews.com/article/139690/fallout-4-script-extender-makers-fixing-mod); article text not read).
  Lesson for the FO4 side: our reader is pinned to 1.10.163, and next-gen players need a hash table or a refusal.
- **Changing master type later breaks dependents** (CK warning above, **verified**). Lesson: choose full or medium
  master per output plugin before release; mods built on the core depend on it.
- **Caprica and the CK compiler disagree on guards**; a working community answer is to compile with the CK and
  rewrite decompiled guard syntax. **verified** / **supported hypothesis** as above. Lesson: our recompile step should
  target the CK compiler first.
- **xEdit for Starfield is Discord-gated and lagging on GitHub.** **verified** (reports). Lesson: do not make xEdit a
  player-side dependency; use it for QA only.
- **Spriggit was built for a Starfield collaborative patch.** **verified**. Lesson: a text form of our generated
  plugins is a proven way to review and diff builds.

## Possibilities and hard limits in CE2

- **Possible:** headless CK compiler runs via batch (**supported hypothesis**, SKKMods' `.cmd` files); Papyrus natives
  from SFSE plugins (**verified** in practice, Cassiopeia); BA2 v2 and v3 packing without Archive2 (**verified**, BAMgr,
  open-source Python tool); Starfield NIF and `.mesh` round trips with community tools (**verified** as claimed by
  their pages); emissive `.mat` editing (**verified**, Material Editor Lite).
- **Limit: load order.** 253 full slots, 256 medium masters at about 65,535 new records each, 4,096 small masters at
  4,095 each. **verified**. The core (683,870 deterministic FormIDs, from records-and-plugins.md) cannot fit one medium
  master; it needs a full master or a split into several medium masters. **supported hypothesis** (arithmetic; record
  counts per plugin to be checked).
- **Limit: ESP plugins** are discouraged in gameplay (**verified**, CK announcement); ship ESM only.
- **Limit: SFSE serialization API is disabled** since 0.2.12 (**verified**), so SFSE plugins cannot store their own
  co-save data the official way; state must live in Papyrus or records. **supported hypothesis** for the consequence.
- **Limit: SFSE is Steam only** in the reference (**verified** there); Game Pass players need another loader
  (**unresolved** which one works for native plugins today).
- **Limit: lip generation has no documented command line** in the Starfield CK (**unresolved**; GUI path verified).
- **Limit: no public Starfield Havok physics authoring** (**unresolved**; nothing found).
- **Limit: form version.** Mutagen alpha writes 576 and the game accepts it (**verified**); xEdit expects 581
  (**verified** as quoted). Whether CK or xEdit refuse or silently upgrade 576 plugins is **unresolved**.

## Question framework

### 1. Plugin layout and load order
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| 1.1 | How many output plugins, and which master type each (full, medium, small)? | Master type cannot change after release without breaking dependents; sets slot use and record caps | Caps verified (Nexus 14993); core holds 683,870 FormIDs (records-and-plugins.md) | Count new records per planned plugin from the build manifest; offline | Blocks the deterministic FormID map layout, add-on mods | new game | **key** |
| 1.2 | Does a Mutagen-written medium master load and resolve FormIDs in slot `FD` correctly? | Medium masters save slots for players with many mods | Mutagen full master loads (S2 spike); medium untested | Write a two-record medium master, load in game, `help` the forms | 1.1 | new game | **key** |
| 1.3 | Should we write form version 581 instead of 576? | CK and xEdit may treat 576 differently; later Bethesda patches may stop accepting it | Game accepts 576 (verified); xEdit uses 581 (verified, quoted) | Open our plugin in CK and xEdit 4.1.5q; check warnings and what save does to the header | Mutagen upgrade (3.2) | new game | |
| 1.4 | Does the light/regular "two load orders" fragility from 2023 still apply after 1.12? | Determines whether small masters are safe for optional pieces | Nexus warning 2023 verified; post-CK status unresolved | Ask in the Starfield modding Discord or check xEdit notes; one in-game test with a small master depending on a full master | 1.1 | interiors | |
| 1.5 | How do we name and split plugins so mods built on the core can depend on stable masters? | Add-on ecosystem; Nexus release | Launcher note wants FormID manifests | Decision record in docs/ai/decisions.md | 1.1 | release | |
| 1.6 | Which Starfield masters (SFBGS00x, Shattered Space, Terran Armada) must ours list, if any? | A missing optional master crashes or refuses load for players without that DLC | SFBGS006 needed for Empty Ship Habs assets (starfieldwiki) | List masters our records reference in a build; offline scan | Fence decisions (starfield-systems-to-reuse.md) | new game | **key** |

### 2. Papyrus compile on the player's PC
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| 2.1 | Can the launcher run the CK's `PapyrusCompiler.exe` headless, with which arguments and flags file? **Answered (verified):** yes for Starfield's compiler; the project already runs PapyrusCompiler.exe from scripts (scripts/mission/make_mission.py, scripts/bridge/make_bridge.py) to build the installed mission and bridge scripts. Launcher use on a player's PC is the same call. | Every FO4 script must be recompiled on the player's PC | SKKMods `.cmd` files call it (verified); flags file name unresolved | Read-only PC job: `PapyrusCompiler.exe -?` and list the CK's Scripts folder; then compile one synthetic `.psc` | Blocks all quest conversion | quests/people | **key** |
| 2.2 | How long does compiling about 10,000 FO4 scripts take, and can it run in parallel? | Launcher time budget (TTW took 40 min for audio alone) | Unknown | Time 200 scripts on the PC; extrapolate | 2.1 | quests/people | **key** |
| 2.3 | Do FO4 sources (Base.zip) compile unchanged against Starfield's sources plus our shim? Which errors, how many? | Size of the rewrite pass | ~77 missing names (reference); signatures unresolved | Compile `QF_MQ102_0001CC2A` and 50 random FO4 scripts; bucket errors | 2.1, shim design | quests/people | **key** |
| 2.4 | Is Caprica a usable fallback for players without the CK (no guards in FO4 code)? | Fewer player prerequisites | Caprica lacks guards (SKKMods); FO4 code has no guards | Compile the same 50 scripts with Caprica; byte-compare `.pex` behaviour in one in-game test | 2.3 | quests/people | |
| 2.5 | Do Champollion outputs for FO4 `.pex` match Base.zip sources well enough for players without the FO4 CK? | Fallback when the player lacks the FO4 CK | Champollion 1.3.2 latest; FO4 listed | Decompile 20 FO4 `.pex`, diff against Base.zip sources; offline | Launcher prerequisite list | quests/people | |
| 2.6 | Where do compiled `.pex` go: loose (needs loose files enabled) or packed into our BA2? | This install reads no loose files (records-and-plugins.md) | Loose reading off on the PC (verified) | Pack one `.pex` into a BA2 and confirm it runs | 4.1 | new game | |
| 2.7 | Our script namespace (`FO4SF:`) vs FO4 namespaces: do folder namespaces collide with Starfield's? | Names are global | Both games ship `CompanionActorScript` | Offline name diff of FO4 sources vs ContentResources.zip | Decision record before bulk conversion | quests/people | |

### 3. Record tooling (Mutagen, Spriggit, xEdit)
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| 3.1 | What is current upstream Mutagen's Starfield status, and do we upgrade from 0.55.0-alpha.67? | Bug fixes, newer record coverage (LMSW, MTPT, AFFE); risk of breaking our build | Pinned alpha works; NuGet shows 2.8.x prereleases (launcher note) | Read Mutagen changelog; build our solution on a branch with the new version; run tests | 1.3, every record writer | new game | **key** |
| 3.2 | Which Starfield record types does Mutagen write as typed fields vs raw bytes (REFL blobs)? | LMSW, MTPT, IMGS bodies are reflection data; we need to know where we must hand-write bytes | xEdit cannot decode them either (materials note) | List Mutagen's Starfield record classes; check LMSW/MTPT for typed members | Materials swaps, decals | interiors | |
| 3.3 | Can Spriggit serialize our generated plugins for review and determinism checks? | Proves two PCs build identical output (L4) | Spriggit exists, GPL-3, Starfield patch use (verified) | Run Spriggit CLI on one built plugin twice; diff | 3.1 | release | |
| 3.4 | Is xEdit 4.1.5q usable for QA of our plugins, and where do we obtain it reliably? | Human QA; Discord-only distribution | 4.1.5q features verified (quoted); GitHub lags | Ask the owner to fetch the Discord build; open one built plugin | none | new game | |
| 3.5 | Can Mutagen write the faction ties (FACT relations, crime values, vendor data) the owner wants to reuse? **Answered (verified at the schema level, wave 2):** Mutagen types Starfield FACT fully; see wave2-rechecks.md section 2. | Factions are the first Starfield system we reuse (starfield-systems-to-reuse.md) | FACT layout carries (reference) | Write one FO4 faction with relations to two others via Mutagen; read back in xEdit; in-game `GetFactionReaction` check | 3.1 | quests/people | **key** |

### 4. Archives
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| 4.1 | Which BA2 writer does the launcher use: Archive2 (player's CK), BSArch, or our own? | Load speed, no loose files on the PC, licence for shipping | BAMgr writes v2/v3 (verified); our reader lacks v3 | Pack one converted mesh+texture set with each; load in game; time it | 2.6 | new game | **key** |
| 4.2 | Must textures be v3 (LZ4) or does v2 zlib suffice in 1.16.244? | Writer complexity; our reader | Game loaded our `FO4Port - Main.ba2` (S2) | Check header of a vanilla texture BA2 and our test archive; offline | 4.1 | new game | |
| 4.3 | How big can one BA2 be, and how many can load before limits or slowdowns? | Full world output will be tens of GB | Unknown | Ask community; pack a 4 GB test archive | 4.1 | interiors | |

### 5. SFSE plugins and custom natives
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| 5.1 | Which FO4-only natives truly need native code (menus, Pip-Boy, power armor camera, VATS time) and which can be Papyrus? | Every native plugin is an update liability | ~77 missing names (reference); SFSE pinned 0.2.21 | Classify the 77 names by call count in FO4 sources; offline | 2.3 | Fallout systems | **key** |
| 5.2 | Which SFSE stack do we build on: libxse/commonlibsf, plain SFSE API, or a dependency on Cassiopeia's natives? | Update resilience, licence (GPL-3 with exceptions), build tools | CommonLibSF moved to libxse; Cassiopeia avoids Address Library (verified) | Ask LarannKiar and the libxse maintainers why; build a hello-world native with commonlibsf | 5.1 | Fallout systems | **key** |
| 5.3 | How fast after a game patch do SFSE, Address Library and big plugins update? | Sets how long players are broken and whether we pin versions | Release pairs in whatsnew and changelogs (verified) | Tabulate patch date vs SFSE and Cassiopeia release dates from their logs | 5.2 | release | **key** |
| 5.4 | With serialization disabled, where does native-plugin state live across saves? | Pip-Boy, power armor state | Serialization off since 0.2.12 (verified) | Read SFSE PluginAPI.h; design state in Papyrus globals or records | 5.2 | Fallout systems | |
| 5.5 | What do Game Pass players use, if anything? | Player reach | SFSE Steam only (reference) | Ask on Nexus forums or the SFSE page posts | release scope decision | release | |
| 5.6 | Can a script reach an SFSE native from a fragment without a `.psc` stub in the player's install? | Packaging of native stubs | Cassiopeia ships stubs (supported hypothesis) | Inspect Cassiopeia's file list; test one call | 5.2 | Fallout systems | |

### 6. Creation Kit headless and batch steps
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| 6.1 | Does the Starfield CK accept any command-line switches (lip generation, compile, export)? **Answered (verified, PC jobs 18 to 21):** the Starfield CK has switches (-CompileFaceFXAnims, -GenerateAnimInfo, -ExportFaceGenData, -RunValidationSuite and more) but no -GenerateLips; see engine-mechanics.md, PC checks. | Unattended launcher stages | Skyrim had `-GenerateLips` (verified); Starfield documented only as GUI | Read-only PC job: `strings CreationKit.exe` grep for `-Generate`, `-Export`, `-Compile`; then try one | Voice and lip stage | quests/people | **key** |
| 6.2 | Can `ffxc.exe` or `LipGenerator.exe` run without the CK for 120k lines? **Answered (verified, PC jobs 24 to 33):** yes, headless: LipGenerator.exe makes the animation, ffxc.exe compiles it to a game-format .ffxanim bound to the shipped actor; in-game playback still open; see engine-mechanics.md and dialogue.md. | Lip sync at scale | Tools present on the PC (voice note) | `-h` on each; one WAV in, one `.ffxanim` out | 6.1 | quests/people | **key** |
| 6.3 | Does the CK open our Mutagen plugins without errors, and does saving in the CK change them? | Hand fixes in the CK; CK-only records (LMSW, MTPT) | Unknown | Load the current core in the CK on the PC; read its warnings log | 1.3 | interiors | |
| 6.4 | Can the CK author LMSW and MTPT records we then template from? | Material swaps and impact decals | CK material editor exists; complex (blog) | Make one LMSW in the CK, dump it, compare with vanilla | 3.2 | interiors | |
| 6.5 | Does the launcher require players to install the CK (about how many GB), or only the CK's Tools zip? | Prerequisite friction | CK required is a settled option | Measure CK install size on the PC | 2.1, 6.1 | release | |

### 7. Meshes, materials and textures tooling
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| 7.1 | Which community tool is our reference validator for converted NIF/`.mesh` (NifSkope fork, SFG Bridge, PyNifly)? | Catch writer bugs before in-game tests | All three claim Starfield support (verified pages) | Open 20 converted meshes in the NifSkope fork headless; log errors | none | interiors | |
| 7.2 | Can a ColorEmissive `.mat` template from Material Editor Lite drive our emissive conversion? | Glowing signs, terminals still missing | Tool edits ColorEmissive (verified) | Clone one vanilla emissive `.mat`, apply to a converted sign; in game | Materials lane | interiors | **key** |
| 7.3 | Do we need `morph.dat` or LODs for converted meshes, and can the NifSkope fork generate LODs headless? | Distant objects, performance | Fork generates mesh LODs (verified) | Run the headless LOD option on one mesh | world LOD lane | interiors | |
| 7.4 | Biome-keyed material swaps: can FO4 MSWP-by-area become LMSW keyed on our planet's biomes? | Seasonal or regional looks without new meshes | Swap keywords go on biome/worldspace (blog) | One test biome keyword with a swapped bark material | 6.4 | interiors | |

### 8. Havok and Wwise tooling
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| 8.1 | Is there any community tool that writes Starfield hknp constraints, or must `hktagfile.py` do it? | Ragdolls, hinges | None found (unresolved) | Ask on the Starfield modding Discord; dump one vanilla constraint | physics lane | interiors | |
| 8.2 | Can the launcher convert WAV to `.wem` headless (WwiseConsole for 2021.1.14), and is the Wwise licence OK for player-side use? | 278k voice files; legal | Wwise 2021.1.14.8108 is the modders' version (verified) | Install Wwise on the PC; run WwiseConsole convert on one file; read Audiokinetic's free licence terms | Voice stage | quests/people | **key** |
| 8.3 | Is there an open-source `.wem` encoder (Vorbis or Opus) the game accepts, to avoid Wwise? | Drops a heavy prerequisite | Unknown | Search vgmstream and community encoders; test one file in game | 8.2 | quests/people | |

### 9. Game update resilience and versions
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| 9.1 | What does the launcher do when Starfield updates past 1.16.244? | Players broken overnight | Pinned 1.16.244 (PLAN.md); history of breakage (verified) | Write the policy: detect exe version, refuse SFSE stages, keep plugin-only build working | 5.3 | release | **key** |
| 9.2 | Which of our outputs are update-proof (plugins, BA2, `.mat`) and which are fragile (SFSE DLLs, form version, Papyrus natives)? | Release risk register | Partly known | Table in docs/RISKS.md; review per patch | 9.1 | release | |
| 9.3 | Which FO4 versions (1.10.163, next-gen) do we accept as input? | Next-gen changed archives (BA2 v7/v8, verified BAMgr) | 1.10.163 pinned | Hash tables per version; test reading one next-gen BA2 | Launcher input check | release | |
| 9.4 | Do Bethesda updates rename or remove Papyrus natives we use? | Silent script failures | Unknown | Diff ContentResources.zip after each patch; automate | 2.1 | release | |

### 10. Distribution rules and licences
| # | question | why it matters | known so far | cheapest way to answer | depends on / blocks | phase | key |
|---|---|---|---|---|---|---|---|
| 10.1 | Do Bethesda's Creations rules allow script extender dependencies, and does it matter for us? | Rules out Creations as a channel early | Not found (unresolved); converted assets cannot be uploaded anyway (launcher note) | Read the Creations content guidelines on Bethesda.net | release channel | release | |
| 10.2 | Which tools may we bundle (Caprica MIT, Champollion, BAMgr, Spriggit GPL-3, PyNifly GPL-3) and which must players install (CK, Archive2, Wwise, SFSE)? | GPL-3 release plan | Licences partly verified above | Licence table in decisions.md | 2.4, 4.1, 8.2 | release | **key** |
| 10.3 | Does a GPL-3 native plugin built on commonlibsf fit our GPL-3 plan, given its Modding Exception? | Licence consistency | Licence terms verified | Read the exception text; decision record | 5.2 | release | |

## Sources

- Nexus news 14993, Starfield Creation Kit is now available (10 June 2024): https://nexusmods.com/news/14993
- Nexus news 14888, Starfield: an update on plugin mods (2 November 2023): https://www.nexusmods.com/news/14888
- Nexus news 14877, Starfield Community Patch: https://www.nexusmods.com/news/14877
- starfieldwiki, Starfield Creation Kit: https://starfieldwiki.net/wiki/Starfield_Mod:Starfield_Creation_Kit
- starfieldwiki, Audio File Conversion: https://dev.starfieldwiki.net/wiki/Starfield_Mod:Audio_File_Conversion
- starfieldwiki, Porting Custom Audio Files to Xbox: https://dev.starfieldwiki.net/wiki/Starfield_Mod:Porting_Custom_Audio_Files_to_Xbox
- ck.uesp.net, How to generate voice files by batch: https://ck.uesp.net/wiki/How_to_generate_voice_files_by_batch
- SFSE whatsnew: https://raw.githubusercontent.com/ianpatt/sfse/master/sfse_whatsnew.txt
- Cassiopeia Papyrus Extender changelog: https://www.nexusmods.com/starfield/mods/10896?tab=logs
- Starfield Engine Fixes: https://www.nexusmods.com/starfield/mods/10457
- Nexus article 702 (save cleaner mention): https://www.nexusmods.com/starfield/articles/702
- CommonLibSF (archived): https://github.com/Starfield-Reverse-Engineering/CommonLibSF ; successor https://github.com/libxse/commonlibsf
- Address Library for SFSE (STEP wiki): https://stepmodifications.org/wiki/Starfield:Address%20Library%20for%20SFSE%20Plugins
- TweakTown, 17 March 2026, early access for script extender authors: https://www.tweaktown.com/news/110512/bethesda-gives-script-extender-creators-early-preview-access-of-new-game-updates-to-prepare-fose-and-skse-tools/index.html
- Nexus forum, version 1.8.86 problems: https://forums.nexusmods.com/topic/13453760-version-18860-problems
- CK Papyrus Compiler command files (SKKMods): https://www.nexusmods.com/starfield/mods/10320
- Papyrus API (FrostWyrm98): https://www.nexusmods.com/starfield/mods/7333
- Caprica: https://github.com/Orvid/Caprica ; Champollion releases: https://github.com/Orvid/Champollion/releases
- bgs-papyrus skill page: https://skillsmp.com/creators/bb-84c/bgs-modding-superpowers/plugins-bgs-modding-superpowers-skills-using-bgs-papyrus
- xEdit 4.1.5q release post (snapshot): https://reddit.sentinel-team.org/posts/1u6jz38/snapshots/2026-06-16T07%3A02%3A42.6264Z
- Nexus article 659, xEdit patching tutorial and comments: https://www.nexusmods.com/starfield/articles/659
- STEP xEdit guide: https://stepmodifications.org/wiki/Guide:XEdit
- Spriggit: https://github.com/Mutagen-Modding/Spriggit
- BAMgr: https://www.nexusmods.com/starfield/mods/14468 ; Starfield BA2 Manager and Compressor: https://www.nexusmods.com/starfield/mods/17849
- NifSkope fork: https://github.com/fo76utils/nifskope ; PyNifly: https://github.com/BadDogSkyrim/PyNifly/
- Void SFG Bridge: https://www.nexusmods.com/starfield/mods/17968
- Material Editor Lite: https://www.nexusmods.com/starfield/mods/14659 ; Material Editor Studio: https://www.nexusmods.com/starfield/mods/17879
- Material swaps blog: https://thecommabandit.bearblog.dev/learning-to-use-material-swaps/
- Starfield Portal April Fools' article: https://starfieldportal.com/article/the-elder-scrolls-morrowind-remake-shifts-to-starfield-engine
- Nexus FO76 conversion example: https://www.nexusmods.com/fallout76/mods/4139
- FO4 next-gen headlines (not read): https://www.windowscentral.com/gaming/roll-back-fallout-4s-horrible-next-gen-update-with-this-nifty-downgrader-mod ; https://shacknews.com/article/139690/fallout-4-script-extender-makers-fixing-mod
- Repo: dotnet/*.csproj (Mutagen 0.55.0-alpha.67), src/fo4sf/ba2.py, docs/spikes/S2-S4-S9-plugin-units-loading.md, docs/PLAN.md (pins).
