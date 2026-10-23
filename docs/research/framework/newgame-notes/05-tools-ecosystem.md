# 05: Tools and modding ecosystem for the Vault 111 new-game start

Author: Claude (research agent), 2026-10-19. Area: the tools, managers, extenders and rules that a Starfield
start mod (and the wider fo4-to-starfield conversion) depends on.

Labels follow docs/ai/research-log.md: **verified** (a primary or first-hand source states it, or our own repo
evidence shows it), **supported hypothesis** (secondary source or inference with a cited basis),
**unresolved** (no reliable source found). "Verified (web)" means verified only from a published source, not
on our PC. Offline and web checks are not in-game acceptance.

## Research limits (read first)

- WebFetch hit an HTTP 429 rate limit part-way through. Pages I could **not** read, so claims about them are
  missing or unresolved: Bethesda's own modding guidelines page
  (https://help.bethesda.net/app/answers/detail/a_id/51731/), the Nexus "Porting content" wiki page
  (https://wiki.nexusmods.com/index.php/Porting_content, fetch error), the Nexus lip-sync guide
  (https://www.nexusmods.com/starfield/mods/12576), the Starfield wiki Papyrus syntax reference
  (https://dev.starfieldwiki.net/wiki/Starfield_Mod:Papyrus_Syntax_Reference), the Address Library page on STEP,
  Steam CK discussion threads, the Mutagen and Spriggit GitHub pages.
- GitHub API access was not enabled for this session, so release lists for Caprica, Champollion, xEdit and SFSE
  came from web pages, not the API.
- NuGet versions came from the public NuGet API (`api.nuget.org`, commands quoted below).

## 1. Starfield Creation Kit (2024)

| Claim | Label | Source |
|---|---|---|
| Released to the public on 9 June 2024, free on Steam (app 2722710 in our SETUP.md); needs Starfield on the same drive volume to launch | verified (web) | https://starfieldwiki.net/wiki/Starfield_Mod:Starfield_Creation_Kit ; docs/SETUP.md line 22 |
| Launch features named by Nexus: Planet Content Manager (procedural content, "similar to (but not replacing) Story Manager"), Galaxy View, worldspace overlays, Particle Editor, "easier navmesh", Render Window Layers, PackIns (replace Static Collections), VSCode for Papyrus, 3DSMax for 3D | verified (web) | https://nexusmods.com/news/14993 |
| No public Starfield-specific documentation at launch; Nexus pointed to the Skyrim/FO4 CK wiki for concepts | verified (web, as of June 2024) | https://nexusmods.com/news/14993 |
| Ships `Tools\Archive2\Archive2.exe` and the Papyrus compiler; base script sources come in `Tools\ContentResources.zip` | verified (our repo: scripts/deploy_starfield.py line 155, scripts/mission/make_mission.py lines 89-101, 293) | repo |
| The CK's FaceFX integration: a modder reported FaceFX failing to build an `.animset` and attributed it to case sensitivity with plugin names containing spaces; FaceFX staff said the tool is embedded in the CK and Bethesda supports it | supported hypothesis (one user report, Nov 2024) | https://facefx.com/node/4600 |
| CK can generate lip sync for new Starfield voice lines (a community guide exists) | unresolved (guide page could not be read) | https://www.nexusmods.com/starfield/mods/12576 |
| CK command-line options for Starfield (e.g. batch lip generation, precombine/previs generation as in FO4's CK, ESL conversion) | **unresolved**: no source found listing Starfield CK switches. Do not assume FO4 switches work | searches returned nothing usable; FO4 precedent: https://diskmaster.github.io/ModernPrecombines/Creating_PRP_patches_for_other_mods.html |
| Headless CK use | unresolved; no source says the Starfield CK runs without a window | (none found) |
| The CK saves an extra patch file instead of editing the master directly, and has "somewhat restrictive" system requirements (one modder's view) | supported hypothesis | https://www.nexusmods.com/starfield/articles/659 |
| Quests, scenes, dialogue editors exist in the Starfield CK (inherited from FO4's CK) | supported hypothesis: the CK is described as an updated FO4/Skyrim CK; no page I read lists the Starfield quest/scene UI | https://starfieldwiki.net/wiki/Starfield_Mod:Starfield_Creation_Kit |

**Licensing/EULA.** I could not read the Starfield CK EULA itself. The Skyrim CK EULA (transcribed by UESP)
limits the editor to personal non-commercial use, forbids charging for mods, allows distributing mods only to
people who bought the game, requires a "NOT MADE, GUARANTEED OR SUPPORTED BY ZENIMAX" disclaimer, and requires
the creator to warrant that each mod is "originally created by You" and infringes nobody's IP
(https://en.uesp.net/wiki/Tes5Mod:EULA). That page has **no clause on porting assets between Bethesda games**.
Whether the Starfield CK EULA has the same clauses, or anything on automation: **unresolved**.

## 2. Plugin and script tools

### Mutagen (our plugin writer)
- `Mutagen.Bethesda.Starfield` on NuGet: 444 versions; latest stable 0.54.4 (published 2026-08-08), latest
  prerelease **0.55.0-alpha.75 published 2026-10-19** (today). Package description: "A C# library for
  manipulating, creating, and analyzing Starfield mods". **Verified** with
  `curl https://api.nuget.org/v3-flatcontainer/mutagen.bethesda.starfield/index.json` and the registration
  endpoint. Implication: the 0.55 alpha line moves daily; we must pin an exact alpha build.
- Our own spike: a Mutagen-written plugin (form version 576) loads in game and its record spawns.
  **Verified** in game (docs/RISKS.md S2; docs/spikes/S2-S4-S9-plugin-units-loading.md).
- The "alpha" is the prerelease tag of the whole 0.55 line, not necessarily a Starfield-only maturity label.
  **Supported hypothesis** (the stable 0.54.x Starfield packages also exist).

### Spriggit (plugin <-> text, for version control)
- Announced by Noggog for the Starfield Community Patch (Aug 2023) to "compile Creation Engine plugins to and
  from plain text" for Git-style collaboration; the shipped patch is still a normal ESM.
  **Verified (web)**: https://www.nexusmods.com/news/14877
- `Spriggit.Json.Starfield` on NuGet: latest 0.42.0-alpha.2 (2026-07-10), stable 0.41.0. **Verified** via the
  NuGet API (same commands). Useful to us as a readable diff of our generated start plugin; round-trip fidelity
  for our records is **unresolved**.

### xEdit / SF1Edit
- Nexus, Nov 2023: SF1Edit planned; would save only regular ESMs and restrict unmapped sub-records to
  Starfield.esm. **Verified (web)**: https://www.nexusmods.com/transformersdevastation/news/14888
- June 2024: SF1Edit "needs an update to support the latest changes" (CK, new plugin types).
  **Verified (web)**: https://nexusmods.com/news/14993
- A 2024 tutorial (edited June 2025): rename `xEdit64.exe` to `SF1Edit64.exe`; latest build (4.1.5o) on the
  xEdit Discord; GitHub release "may no longer work properly". A Sept 2026 comment claims "Xedit is no longer
  supporting Starfield" with crashes. **Supported hypothesis** (tutorial author and one commenter, not xEdit devs):
  https://www.nexusmods.com/starfield/articles/659
- Implication: xEdit is a viewer/oracle we cannot rely on for 1.16.244 plugins without testing.
  SETUP.md lists `xSFEdit.exe`; whether our installed build reads current Starfield.esm cleanly is unresolved.

### Papyrus: compiler, Caprica, Champollion
- Official compiler: our scripts already compile with `PapyrusCompiler.exe <file> -f=Starfield_Papyrus_Flags.flg
  -i=<imports> -o=<out>` from `Tools\Papyrus Compiler\`, with sources and the flags file extracted from
  `ContentResources.zip`. **Verified** (repo: scripts/mission/make_mission.py lines 89-101, 293;
  scripts/door_bridge/compile_load_door.py line 65). A third-party LSP also uses `PapyrusCompiler.exe -noasm`
  for semantic checks: https://github.com/0xra0/Papyrus-Lsp (**verified (web)**, a cheap syntax-only check).
- Caprica (Orvid, open-source compiler) and Champollion (decompiler) got pre-CK Starfield support. Champollion
  v1.3.1 notes: guessed syntax for `Guard`, `TryGuard`, `ArrayGetAllMatchingStructs` "is experimental", marked
  with `;***` comments, and proper syntax was expected with the CK. Latest release v1.3.2 notes do not mention
  Starfield. **Verified (web)**: https://github.com/Orvid/Champollion/releases
- Community wrappers (pre-CK): Papyrus API (Caprica + Champollion, Nov-Dec 2023,
  https://www.nexusmods.com/starfield/mods/7333) and a Caprica command-file kit whose thread shows namespace
  errors (e.g. `QOG:JunkRecycler`) and "Unknown flag 'selfonly'" problems; **no confirmation that
  Caprica-compiled .pex loads in game** (https://www.nexusmods.com/starfield/mods/3921?tab=posts). After the CK,
  SKKMods published `.cmd` wrappers around the CK's `PapyrusCompiler.exe` (v001, 1 July 2024;
  https://www.nexusmods.com/starfield/mods/10320). **Verified (web)**.
- Conclusion: use the official compiler (already proven in our repo); treat Caprica as unproven for Starfield;
  use Champollion only for reading .pex, with Starfield-specific constructs possibly wrong.
- Fragment naming (`Fragments:Quests:QF_...` namespace) for Starfield: **unresolved** from the web (the syntax
  reference page could not be read). It can be answered offline by listing `ContentResources.zip` (see Q4).

### BA2 tools
- Archive2 (ships with the CK in `Tools\Archive2`): usage `Archive2 <archive, files/folders> [<arguments>]`;
  `-create`, `-extract`, `-root`, `-format=General|DDS|XBoxDDS`, `-compression=None|Default|XBox|LZ4`,
  `-sourceFile`, `-excludeFile`, `-quiet`, `-tempFiles`, `-cleanup` (unsafe with parallel copies),
  `-include/-excludeFilters`; naming `<Mod> - Main.ba2`, `<Mod> - Textures.ba2` (and `_Xbox` variants).
  **Verified (web)**: https://starfieldwiki.net/wiki/Starfield_Mod:Archive2 . Our deploy already uses it
  headlessly (**verified**, scripts/deploy_starfield.py; terrain scripts use `-format=General -compression=None`).
- The game loads `<plugin> - Main.ba2` beside an enabled plugin without any ini change. **Verified in game**
  (docs/spikes/S2-S4-S9-plugin-units-loading.md lines 46-65).
- BSArch for Starfield, and a "BA2 version 3" format used by some texture mods: **unresolved / supported
  hypothesis** (only a texture mod's page mentions "BA2 version 3": https://www.nexusmods.com/starfield/mods/16602).
  Our spike recorded Archive2 writing version 2 GNRL (S2-S4-S9 line 48).

## 3. SFSE and Address Library

- SFSE latest **0.2.21 (11 June 2026), "support for 1.16.244"**; earlier: 0.2.20 = 1.16.242, 0.2.19 = 1.16.236,
  0.2.18 = 1.15.222, 0.2.17 = 1.15.216. Steam only: "Other stores (Windows Store/Game Pass/EGS) are not
  supported." Must launch through `sfse_loader.exe`; files go in the game folder, not Data. **Verified (web)**:
  https://www.nexusmods.com/starfield/mods/106 . Matches our pin (docs/SETUP.md lines 10-11).
- What it adds: plugin manager, "preliminary custom papyrus native function support", Post/PostDataLoad
  messages, scaleform menu plugin interface, `GetSFSEVersion` console command. **Verified (web)**, same page.
- Fragility: each game patch needs a new SFSE build. 0.2.17: a game patch's compiler changes "invalidate the
  Address Library and most if not all existing plugins"; 0.2.12-0.2.13: root form class changes for 1.14.70
  forced recompiles. **Verified (web)**, same page.
- Address Library for SFSE Plugins: a database that makes SFSE DLL plugins version independent
  (https://www.nexusmods.com/starfield/mods/3256 , page snapshot showed only 1.7.23 files, so the current
  version list is **unresolved**).
- Plugins.txt Enabler (needed SFSE) is obsolete since 9 June 2024 / game 1.12.30. **Verified (web)**:
  https://www.nexusmods.com/starfield/mods/4157 ; https://nexusmods.com/news/14993
- Consequence for a Vault 111 start: a pure plugin + Papyrus start needs **no SFSE**. SFSE becomes a
  requirement only if we need native Papyrus functions, custom menus (Pip-Boy UI), or a crash logger.
  **Supported hypothesis** (from the feature list; to be confirmed by design).

## 4. Mod managers, plugins.txt, load order

- Game 1.12.30 (June 2024) "enables mod loading by default"; Plugins.txt Enabler and SFSE/ASI loader no longer
  needed. **Verified (web)**: https://nexusmods.com/news/14993
- Native Plugins.txt: `%LOCALAPPDATA%\Starfield\Plugins.txt`, first line a `#` comment, one `*Plugin.esm` per
  line; **ignored if any `sTestFile` INI variable is set**. **Verified (web)**:
  https://www.nexusmods.com/starfield/mods/4157 ; our spike enabled `*FO4Port.esm` this way (**verified in game**).
- Plugin types: full master (one of 253 slots), medium master (slot FD, ~65,535 records, 256 loadable),
  small master (slot FE, 4,095 records, 4,096 loadable); about 4,605 plugins total. "Changing the flag on an
  existing creation isn't supported" (Bethesda). ESPs are for work in progress; shared mods should be ESM.
  **Verified (web)**: https://nexusmods.com/news/14993
- Pre-CK warning: some sub-record references (IPDS, SCEN, KSSM, STND, SFPT, SFTR) were resolved by in-plugin
  position, not load order, so adding masters or reordering could break them. **Verified (web) as of Nov 2023**;
  whether still true on 1.16.244 is **unresolved** and matters for our SCEN records:
  https://www.nexusmods.com/transformersdevastation/news/14888
- Mod Organizer 2: v2.5.0 needed the Enabler and removing `sTestFile`; v2.5.2 made the Enabler obsolete, added
  "medium"-flagged plugins (warns on light+medium both set) and "Creations parsing from ContentCatalog.txt".
  **Verified (web)**: https://github.com/Modorganizer2/modorganizer/releases
- Vortex (Dec 2023 extension): load-order management off by default; migrates `sTestFile` entries into
  plugins.txt; leftover INI entries block plugin management "by Bethesda's design". **Verified (web)**:
  https://forums.nexusmods.com/topic/13458887-starfield-extension-has-been-updated-to-support-load-ordering-and-pluginstxt
- MO2 keeps INI files in its profile folder, so editing `My Games\Starfield\StarfieldCustom.ini` may have no
  effect under MO2. **Verified (web)**: https://www.nexusmods.com/starfield/articles/780
- `sResourceDataDirsFinal` / loose-file switches: not researched to a primary source (Nexus "Archive
  Invalidation" how-to could not be fetched: https://nexusmods.com/starfield/articles/116). Our test PC reads no
  loose files (project constraint), so BA2-only remains the safe path. **Unresolved** for loose files.

## 5. Bethesda's rules on other games' assets; precedent

- I could not read Bethesda's modding guidelines page (rate limit). **Unresolved**: whether Creations or
  Bethesda.net forbid assets from other Bethesda games. Source to read:
  https://help.bethesda.net/app/answers/detail/a_id/51731/
- Skyrim CK EULA requires mods be "originally created by You" and not infringe IP; no explicit cross-game clause.
  **Verified (web)**: https://en.uesp.net/wiki/Tes5Mod:EULA
- Precedents (all **supported hypothesis** about Bethesda's position; none is a written license):
  - Skyblivion: Bethesda required the team to "fully replace 100% of all assets from the original" so it would
    not redistribute Bethesda content; players must own both games. https://en.wikipedia.org/wiki/Skyblivion
  - Tale of Two Wastelands: installer "Patches and creates all non-unique assets dynamically from original game
    files"; requires both games installed; "Piracy is not supported". https://thebestoftimes.moddinglinked.com/faq.html
  - "Tales From Appalachia" (FO76 into FO4, unreleased, July 2026): requires legal copies of both games; no
    Bethesda response reported. https://boingboing.net/?p=1116303
  - Forum members (not staff) say "Bethesda does not allow use of assets from one game to another" and that
    vanilla assets are what Bethesda gets "cranky about". https://forums.nexusmods.com/topic/13519139-simple-question-about-assets-usage-from-other-games/
- Reading for us: the TTW model (build from the user's install, ship no Bethesda files) is the strongest
  community precedent and matches our launcher plan; Skyblivion shows Bethesda can insist on zero original
  assets even when users own both games. Distribution through Creations is the riskiest channel. Owner decision.

## 6. Testing, logging and automation tools

- Papyrus logging: in `My Games\Starfield\StarfieldCustom.ini` (or the MO2 profile copy) set `[Papyrus]
  bEnableLogging=1, bEnableTrace=1, bLoadDebugInformation=1, bEnableProfiling=0`; logs in
  `My Games\Starfield\Logs\Script\Papyrus.0.log` (newest), `Papyrus.1.log` (previous). Type, don't paste
  (invisible characters). **Verified (web)**: https://www.nexusmods.com/starfield/articles/780
- Crash loggers: "Trainwreck - A Crash Logger" and "Starfield Engine Fixes - SFSE" exist (mirror listings,
  https://allmods.net/starfield-mods/starfield-miscellaneous/trainwreck-a-crash-logger-v1-1/ ;
  https://www.nexusmods.com/starfield/mods/10457). Whether they support 1.16.244: **unresolved**. Both need SFSE.
- SFSE ASI Loader logs ASI loading to `SFSEASILoader.log` (v1.0.4, Oct 2023): https://www.nexusmods.com/starfield/mods/857
- Console `bat` files and `sStartingConsoleCommand`: a Nexus forum guide is titled "sStartingConsoleCommand not
  always working" (https://forums.nexusmods.com/topic/13253886-guide-how-to-properly-merge-mods-fixes-bat-files-sstartingconsolecommand-not-always-working).
  Behaviour on 1.16.244: **unresolved**. Our existing test chain already does console-driven checks
  (docs/PLAY-AND-TEST.md, scripts/game/); this ecosystem adds no new required tool.
- Existing alternate-start mods (e.g. https://www.nexusmods.com/starfield/mods/3673) are prior art for skipping
  the intro; how they do it is **unresolved** (not read). Worth reading their scripts (Q15).

## QUESTIONS for the next phases

1. **Which exact Mutagen 0.55 alpha do we pin, and do we re-test on each bump?** Why: alpha.75 shipped today;
   record layout changes could silently alter our start plugin. How: offline (pin in csproj, golden-file test of
   the written ESM bytes).
2. **Does the Starfield CK accept any command-line switches (lip gen, ESL/medium conversion, precombines)?**
   Why: the launcher can only use the CK if it runs unattended. How: read-only PC check (`CreationKit.exe` strings
   for `-` switches), then a manual CK run.
3. **Can we avoid the CK entirely for the start plugin?** Why: the CK is a heavy dependency for users. How:
   in-game test of a Mutagen-only quest + scene + Papyrus fragment start.
4. **What are the exact fragment script names and namespaces Starfield uses (QF_/SF_/TIF_, `Fragments:Quests:`)?**
   Why: VMAD fragment records must name the compiled .pex exactly. How: offline, list `ContentResources.zip`
   (`unzip -l ... | grep -i fragments`) and read a vanilla QUST VMAD with Mutagen.
5. **Is the pre-CK warning about position-mapped SCEN/IPDS references still true on 1.16.244?** Why: our start
   scene records would break when masters change. How: offline Mutagen read of Starfield.esm SCEN records, then an
   in-game test with an extra master added.
6. **Small, medium or full master for the start plugin?** Why: flag changes later are unsupported; record count
   decides it (4,095 / ~65,535). How: owner decision after an offline record count of the start plugin.
7. **Does Plugins.txt get rewritten or overridden when the user has Creations installed (ContentCatalog.txt)?**
   Why: the launcher writes Plugins.txt. How: read-only PC check of `%LOCALAPPDATA%\Starfield\` after enabling a
   free Creation; in-game test.
8. **Must the launcher detect and refuse `sTestFile` INI entries?** Why: they make the game ignore Plugins.txt.
   How: offline (launcher reads StarfieldCustom.ini/Starfield.ini) plus a read-only PC check.
9. **Do we need SFSE for phase one (Vault 111 start) at all?** Why: SFSE breaks on every game patch and excludes
   Game Pass users. How: owner decision after listing which start features need native functions or UI.
10. **If SFSE is used, which crash logger supports 1.16.244?** Why: crash triage without logs is guesswork. How:
    read-only PC check of installed SFSE plugins and their logs; in-game test.
11. **Does our installed xSFEdit build read 1.16.244 Starfield.esm and our ESM without errors?** Why: we list it as
    an L1 oracle. How: read-only PC check (open, check messages).
12. **Is Spriggit worth adding as a readable diff of generated plugins in CI?** Why: reviewers cannot diff ESM
    bytes. How: offline round-trip test on a synthetic Mutagen plugin.
13. **Is Champollion's Starfield decompile reliable enough to read vanilla .pex not in ContentResources.zip?**
    Why: some vanilla behaviour may only exist compiled. How: offline, decompile a .pex whose .psc we have, diff.
14. **Can the CK generate lip files for new or reused FO4 voice lines, and in what format/archive?** Why: Vault 111
    dialogue (Codsworth, the vault-tec rep) needs lip sync. How: manual CK test; read the guide at
    https://www.nexusmods.com/starfield/mods/12576 when fetch limits allow.
15. **How do existing Starfield alternate-start mods skip the intro (which quests stopped, which stages set)?**
    Why: prior art for our start plugin and its compatibility. How: offline, read their plugins/scripts from a
    download the owner approves.
16. **What exactly do Bethesda's modding guidelines say about assets from other games?** Why: decides whether any
    Creations/Bethesda.net release is possible. How: read help.bethesda.net answer 51731; owner decision.
17. **Does the Starfield CK EULA differ from Skyrim's on non-commercial use, originality and automation?** Why: the
    launcher may drive CK tools (Archive2, compiler) on users' PCs. How: read the EULA text in the CK install
    (read-only PC check); owner decision.
18. **Is "build from the user's own FO4 install, ship no Bethesda files" (TTW model) our stated distribution
    policy?** Why: it is the strongest precedent and must be in the README before any release. How: owner decision.
19. **Should the launcher target Game Pass users?** Why: SFSE and its plugins do not work there; Archive2 and
    the CK may differ. How: owner decision.
20. **Does `sStartingConsoleCommand` or a `bat` file run reliably on 1.16.244 for test setup?** Why: unattended
    tests could start from a known state. How: in-game test (owned by Claude per AGENTS.md).
21. **Do MO2 or Vortex users break our deploy (INI in profile folder, virtual Data folder)?** Why: the launcher
    must work beside a mod manager. How: read-only PC check of which manager, if any, is installed; offline docs.
22. **Does Archive2 output (BA2 v2 GNRL) remain correct for Papyrus scripts in a `- Main.ba2`, and do we need
    BA2 v3?** Why: the test PC reads no loose files. How: offline header check of a vanilla BA2 vs ours; in-game
    script-load test (Papyrus log shows the script).

## Top 5 findings

1. **Mod loading is native since 1.12.30 (June 2024)**: Plugins.txt in `%LOCALAPPDATA%\Starfield`, but it is
   ignored if any `sTestFile` INI entry exists; the start mod needs neither SFSE nor an INI change (verified web
   and in game).
2. **SFSE 0.2.21 targets exactly 1.16.244, Steam only**, and every game patch has broken SFSE plugins before;
   keep SFSE optional for the Vault 111 start (verified web).
3. **Use only the official Papyrus compiler**: Caprica has no confirmed in-game Starfield result and
   Champollion's Starfield syntax is self-described as guessed (verified web; our compile path verified in repo).
4. **Starfield CK command-line/headless use is undocumented**: anything the launcher needs from the CK beyond
   Archive2 and the compiler must be proven by a PC test first (unresolved).
5. **Cross-game assets: the safe precedent is build-on-the-user's-PC, ship nothing** (TTW); Bethesda has demanded
   100% replacement before (Skyblivion); the official guideline text is still unread (supported hypothesis /
   unresolved).
