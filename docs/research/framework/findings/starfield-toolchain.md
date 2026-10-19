# Starfield modding toolchain and its limits (2026)

Author: starfield-toolchain (Claude, framework research agent), 2026-10-19. Labels: **verified** (read in the linked
source or a repo file), **supported hypothesis**, **unresolved**.

**Bottom line.** The toolchain the project depends on is alive and tracking the game, but unevenly. Starfield is still
at **1.16.244 (11 June 2026)**; SFSE 0.2.21 shipped for it **the same day** and the Address Library followed two days
later, so the "SFSE lags a patch" risk is days, not months, except when Bethesda changes compiler settings (1.15.216
broke "most if not all" SFSE plugins). Mutagen (our writer) is in active development (0.55 alphas weekly, last one
today) and Spriggit has a Starfield package; xEdit's Starfield mode (4.1.5q, about Feb 2026) can now edit ESPs and
small/medium masters but is distributed through Discord only and still refuses to create update (overlay) files.
NifSkope (fo76utils) and Starfield Geometry Bridge cover meshes; PyNifly's Starfield support is still "experimental".
The weak spots for us are the jobs only the Creation Kit does and that have no public command line or documentation:
**lip sync (FaceFX compiler, GUI only as documented), LOD, and anything resembling precombines/previs**, plus
**.wem audio encoding** for 122,857 FO4 voice files. Navmesh is the exception: CreationKit.exe carries a navmesh
batch command line (repo, strings). The Microsoft Store / Game Pass build is out for SFSE. Downgrading needs Steam
depot tools that require the player's own login; the launcher should pin and refuse, not downgrade.

Research limits of this session: the shared web-search budget ran out part way, and Nexus Mods and some news sites
rate-limited fetches (HTTP 429); pages I could not read are listed under Sources as "not read". Items that would have
needed them are marked **unresolved**, not guessed.

## Findings

### 1. Game version and update history
- **verified**: newest Starfield is 1.16.244, 11 June 2026; before it 1.16.242 (14 May 2026) and 1.16.236 (7 April
  2026: Free Lanes, Terran Armada DLC, PS5). No patch since June; Bethesda has confirmed more Starborn content for 2027
  without a date ([starfield.gg latest update](https://starfield.gg/starfield-latest-update/)). This confirms the
  project note's 1.16.244 pin as still current on 2026-10-19 (it was only a supported hypothesis on 10-12).
- **verified**: 1.16.242 and 1.16.244 notes touch Creations only as crash fixes ("crash when viewing Creations",
  "Creations with legacy data"); no Creation Kit, plugin or load-order notes
  ([1.16.242 notes](https://bethesda.net/en/article/2HBTwuF9g9baAQkEud4WZ9/starfield-update-1-16-242-may-14-2026),
  [1.16.244 notes](https://bethesda.net/en-US/news/starfield-update-1-16-244-june-2026)). The 1.16.242 page said a
  June update was planned, which matched; Bethesda does pre-announce patches a month ahead sometimes.
- **verified**: Creation Kit changes ride inside game patch notes: 1.15.214 (Steam beta, 6 May 2025) lists "Creators
  can now add new icons", Creations up to 2 GB, and a CK crash fix; same patch fixed "Creations load order
  restoration" ([SteamDB 18285521](https://steamdb.info/patchnotes/18285521)).
- **verified** mod-breaking updates, from tool changelogs:
  - 1.11.36: vanilla mesh paths renamed; a migration tool maps ~323,099 meshes so older custom `.nif` keep working
    ([NIF path migration tool, Nexus 9234](https://www.nexusmods.com/starfield/mods/9234)).
  - 1.12.30: mod loading on by default, CK era begins (project note; [Nexus news 14993](https://www.nexusmods.com/news/14993)).
  - 1.14.70: "major changes have been made to the root game form class, so many older plugins will need to be
    recompiled" (SFSE 0.2.13, [sfse_whatsnew](https://raw.githubusercontent.com/ianpatt/sfse/master/sfse_whatsnew.txt)).
    That version is the Shattered Space era (LOOT 0.24.0, 2024-10-05, adds `ShatteredSpace.esm` to the hard-coded
    order, [LOOT changelog](https://loot.readthedocs.io/en/0.24.1/app/changelog.html)); the exact 1.14.70 date is
    **supported hypothesis** (late Sep 2024).
  - 1.15.216: "compiler setting changes ... invalidate the Address Library and most if not all existing plugins";
    plugins must now flag Address Library version 2 (SFSE 0.2.17, same file).
  - 1.15.214 / 1.15.216 also needed a NifSkope update ("Updates for Starfield version 1.15.214", 30 May 2025,
    [fo76utils releases](https://github.com/fo76utils/nifskope/releases)): a mesh/format-touching patch.
  - 1.16.236 / 242 / 244 needed SFSE builds 0.2.19-0.2.21 only ("support for ..."), no API break noted.
- **Correction-grade nuance**: SFSE's own changelog has no dates. Nexus shows 0.2.21 "last updated 11 June 2026, 3:06PM"
  ([SFSE Nexus 106](https://www.nexusmods.com/starfield/mods/106)), the same day as 1.16.244: **verified** same-day
  turnaround for that patch.

### 2. Creation Kit (CK2)
- **verified**: released 9 June 2024; separate Steam tool, ~823 MB, visible only to owners
  ([starfieldwiki Creation Kit](https://starfieldwiki.net/wiki/Starfield_Mod:Creation_Kit)); Steam app id 2722710
  ([STEP wiki](https://stepmodifications.org/wiki/Starfield:Creation_Kit)). Archive2 ships in
  `Starfield\Tools\Archive2` with it (repo, docs/spikes/S2-S4-S9-plugin-units-loading.md).
- **verified** features (Nexus news 14993): Planet Content Manager, Galaxy View, worldspace overlays (terrain, not
  overlay plugins), particle editor, marker-seeded navmesh generation in interiors ("a marker placed in an interior
  generates navmesh", manual still possible), render-window layers, PackIns replacing static collections, export in
  the three master formats, VSCode Papyrus integration, 3ds Max integration. At launch "no public Starfield
  documentation exists".
- **verified (repo)**: CreationKit.exe contains a navmesh batch command line: `-UpdateNavmeshGeneration`,
  `-FinalizeNavmeshes`, `-UpdateNavmeshFinalization:<esm>` with `-Mode`, `-Range`, `-Part`, `-NoCheckIn`,
  `-Basename` (docs/actors/npc-navigation.md section 2.4, strings only, never run). `-Part <part> <count>` suggests
  Bethesda's own build farm used it. **unresolved**: whether it loads a plugin worldspace and BTD terrain.
- **verified**: lip sync = CK menu Audio > "Run FaceFX Compiler": reads `Data\Sound\Voice\<plugin>.esm\<VoiceType>\<id>.wav`,
  writes `.animset` then `.ffxanim`; needs WAV for lip sync and `.wem` for playback; no spaces in names; body type
  must match the voice type; slow on large batches; log `ffxc_00.log`
  ([starfieldwiki Audio File Conversion](https://dev.starfieldwiki.net/wiki/Starfield_Mod:Audio_File_Conversion),
  [Nexus guide 12576](https://nexusmods.com/starfield/mods/12576)). FaceFX staff: FaceFX is embedded in the Starfield
  CK and support is Bethesda's ([facefx.com node 4600](https://facefx.com/node/4600), Nov 2024).
  **unresolved**: any command-line switch for the FaceFX compiler (not found in sources; a strings scan of
  CreationKit.exe like the navmesh one would answer it).
- **unresolved**: LOD generation for Starfield worldspaces in the CK (no source found this session). Starfield's terrain
  LOD uses `.btd` / `.lod` files, not FO4's `.btr`/`.bto` (repo, docs/FORMAT-GAP.md line 41, **verified**); the project
  already notes no public `.btd` writer.
- **unresolved**: precombine / previs equivalents. Not found in any source read. FO4 precombines are a known pain point
  in the project (docs/ai/known-unknowns.md #2). Whether CE2 has a precombine step at all is open.
- **supported hypothesis**: the CK is updated by Bethesda alongside game patches through Steam (1.15.214 notes carry CK
  items), but whether every game patch has a matching CK build is not verified.

### 3. SFSE and native plugins
- **verified**: SFSE 0.2.21 for 1.16.244; "SFSE supports the latest release of Starfield on Steam. Other stores (Windows
  Store/Game Pass/EGS) are not supported" ([SFSE Nexus 106](https://www.nexusmods.com/starfield/mods/106)). It
  supports only the latest release: pinning the game pins SFSE.
- **verified** capabilities (whatsnew): plugin manager 0.1.0; "preliminary custom papyrus native function support"
  0.1.1; Scaleform menu plugin interface 0.1.3; task interface 0.1.6; serialization API disabled in 0.2.12
  "stability issues to be resolved later" (still disabled: no later entry re-enables it); code-signed SFSE components
  0.2.14; Address Library v2 flag 0.2.17. The project note covers most of this; new here: no co-save serialization
  means an SFSE plugin cannot persist its own state in saves (**supported hypothesis** about the consequence).
- **verified**: Address Library for SFSE Plugins (Nexus 3256), file version 22, updated 13 June 2026 (two days after
  1.16.244). It ships separate `.bin` files for the MS Store build ("the 1 at the end ... says it is MS store")
  ([Address Library Nexus 3256](https://www.nexusmods.com/starfield/mods/3256)). So the address database covers Game
  Pass even though SFSE's loader does not.
- **verified**: an SFSE SDK mirror for VS2022 plugins exists (Ez-SFSE-Plugins, 2025-08-18,
  [Nexus 14577](https://www.nexusmods.com/starfield/mods/14577)); SFSE ASI Loader (Steam only, last updated Oct 2023,
  [Nexus 857](https://www.nexusmods.com/starfield/mods/857)).
- **unresolved** (carried from the project note): Custom Command Framework's claim that SFSE lacks custom Papyrus
  functions vs Cassiopeia's ~115 natives. Not re-checked (Nexus rate limit).

### 4. Record tools
- **xEdit / SF1Edit — verified**: 4.1.5 (Nov, year not shown; Starfield era 2023) added Starfield with editing, launched
  with `-sf1` or renamed `SF1Edit.exe`; limits then: ESM-only saving, no saving of modules with ESL or Overlay flag or
  with such masters, PKIN and reflection-stream records cannot be copied as overrides, unmapped FormID fields only
  `00xxxxxx` with Starfield.esm as first master, official masters read-only, `BlueprintShips-Starfield.esm` forced as a
  master, 64-bit only, 4-5 GB RAM and 10+ min first load
  ([xEdit 4.1.5 release](https://github.com/TES5Edit/TES5Edit/releases/tag/xedit-4.1.5)). Latest public GitHub release
  is 4.1.5f ([releases](https://github.com/TES5Edit/TES5Edit/releases)).
  4.1.5q (posted about 10 Feb 2026, Discord-only builds): ".esp editing is now enabled (with restrictions), including
  ... small or medium masters"; an ESP cannot be saved as a master; modules with a blueprint master cannot be saved;
  the small/medium flag cannot be changed in xEdit (export from the CK instead); update-file creation disabled; Free
  Lanes and DLC record updates; BSArch gains Xbox textures
  ([reddit snapshot](https://reddit.sentinel-team.org/posts/1u6jz38/snapshots/2026-06-16T07%3A02%3A42.6264Z)).
  *Implication (inference)*: xEdit is a viewer/oracle for us, not a writer, and builds are not fetchable by a script
  from a public URL.
- **Mutagen.Bethesda.Starfield — verified**: stable 0.54.4 (2026-08-08, "Improved index overflow potential in Starfield
  mod index calculations"), prerelease 0.55.0-alpha.75 dated 2026-10-19, GPL-3.0-only, 425k downloads
  ([NuGet](https://www.nuget.org/packages/Mutagen.Bethesda.Starfield),
  [GitHub releases API](https://api.github.com/repos/Mutagen-Modding/Mutagen/releases?per_page=8)). Docs do not state
  Starfield maturity (**unresolved**: per-record completeness; the project's own round-trip tests are the oracle).
- **Spriggit — verified**: plugin to YAML/JSON per-record text for Git, CLI `serialize`/`deserialize`, Linux CLI,
  GPL-3.0 ([GitHub](https://github.com/Mutagen-Modding/Spriggit)); `Spriggit.Yaml.Starfield` 0.41.0 (2026-07-08),
  30.1k downloads ([NuGet](https://www.nuget.org/packages/Spriggit.Yaml.Starfield)).
- **Synthesis — unresolved**: its README and docs name no games; no Starfield patcher evidence found.
- **LOOT — verified**: medium plugins supported from 0.23.0 (2024-07-10); reads/writes `Starfield.ccc`; "Overlay plugins
  are now referred to as update plugins"; "Update plugins no longer avoid taking up a load order slot when active, to
  reflect a change in Starfield's behaviour"; blueprint master type 0.24.0; hard-coded positions for `Starfield.esm`,
  `ShatteredSpace.esm`, `Constellation.esm`, `OldMars.esm`, `SFBGS003.esm`, `SFBGS004.esm` ...
  ([LOOT changelog](https://loot.readthedocs.io/en/0.24.1/app/changelog.html)).
- **MO2 plugin manager (Re Extended, 31 May 2026) — verified as stated, partly suspect**: medium = flag 0x400, FD
  space, 256 slots; overlay = 0x200, "XX" index, no record space; blueprint `blueprintships-*.esm` force-disabled and
  activated with its main plugin, sorted after others. It also says medium ObjectIDs must be ≤0xFF, which contradicts
  Bethesda's ~65,535 records per medium master ([Nexus 17318](https://www.nexusmods.com/starfield/mods/17318);
  conflict **unresolved**, Bethesda wins until measured).

### 5. Mesh and material tools
- **NifSkope (fo76utils) — verified**: rolling `2.0.dev11` builds, latest 2025-12-30; Starfield 1.15.214 update
  (2025-05-30); glTF export/import (incl. `.glb`, 2025-08-24); batch processing of multiple NIFs; extraction of compiled
  Starfield materials fixed 2025-05-05 ([releases](https://github.com/fo76utils/nifskope/releases)). No 2026 release
  seen: **supported hypothesis** that 1.16.x did not change mesh formats.
- **Starfield Geometry Bridge (Blender) — verified**: imports/exports `.nif`, `.mesh`, `.dat` morphs; exports cloth data
  and `.mat`; models must have < 65,536 vertices per `.mesh`; animation "future plan"; last updated 30 July 2024
  ([Nexus 4360](https://nexusmods.com/starfield/mods/4360)).
- **PyNifly — verified**: Starfield "experimental", WIP: meshes, materials, facial morphs, facebones
  ([GitHub](https://github.com/BadDogSkyrim/PyNifly/)).
- **Materials — verified (repo)**: one compiled `materials/materialsbeta.cdb`, loose `.mat` JSON supported
  (docs/FORMAT-GAP.md line 37). Standalone CDB editors: **unresolved** (search budget ran out before this query).

### 6. Archives and INI
- **verified**: BA2 v2 (GNRL/DX10) and v3 (LZ4 textures) (repo FORMAT-GAP); 4,095 MB per archive, split large sets;
  BA2Upgrader turns v2 textures into v3/LZ4; Archive2 ships with the CK; BSArchPro ships with xEdit
  ([ejams1 guide](https://github.com/ejams1/starfield-modding-guide)). Archive2 output for us is BA2 v2 GNRL (repo S9).
- **verified**: loose files need `sResourceDataDirsFinal=` and `bInvalidateOlderFiles=1` in `StarfieldCustom.ini`
  `[Archive]`; the archive lists are `sResourceIndexFileList`, `SResourceArchiveList`,
  `SResourceArchiveMemoryCacheList`, `sResourceStartUpArchiveList` (ejams1 guide). `<plugin> - Main.ba2` loads
  automatically beside its plugin (repo S9, used in deploy). Windows Controlled Folder Access blocked writes to
  Documents on the owner's PC (repo S9).
- **verified**: on Game Pass, loose asset folders live in `Documents\My Games\Starfield\Data`, plugins and BA2 in
  `<XboxGames>\Starfield\Content\Data`, Plugins.txt in `%LOCALAPPDATA%\Starfield`
  ([Nexus forum Game Pass guide](https://forums.nexusmods.com/topic/13459379-a-guide-to-game-pass-modding-no-mod-manager), Dec 2023/Feb 2024).

### 7. Plugin types and limits (beyond the project note)
- The note's numbers are confirmed (Nexus news 14993, **verified**): 253 full, 256 medium in FD (~65,535 records each),
  4,096 small in FE (4,095 records each), about 4,605 total.
- **verified** additions: there are two more types the note does not list: **update** plugins (formerly "overlay";
  since 1.12.30 they take a load-order slot) and **blueprint** masters (ship blueprints, force-paired with their main
  plugin) (LOOT, MO2 BPM above). xEdit cannot write either.
- **verified**: Starfield's hard-coded master order now includes `ShatteredSpace.esm` and `SFBGS003/004.esm` (LOOT), and
  CC/Creations order comes from `Starfield.ccc`.

### 8. Store versions, pinning, downgrading
- **verified**: SFSE is Steam-only; repo docs already require Steam 1.16.244 (docs/SETUP.md, docs/PLAY-AND-TEST.md).
- **verified**: copying the game to an MO2 "Stock Game" folder keeps its version "even if an update is released"
  (ejams1 guide).
- **unresolved** (not re-verified this session): Steam depot downgrade route (Steam console `download_depot` or
  DepotDownloader with the owner's login). The project roadmap already rules out asking for store credentials
  (docs/ROADMAP.md C1). Inference: the launcher pins and refuses on mismatch rather than downgrading.

## Corrections to project notes
- `engine-mechanics/records-and-plugins.md` (Plugins table) labels the Starfield **medium** master tier a "supported
  hypothesis ... not measured". It is **verified** in Bethesda's CK release article as relayed by Nexus (news 14993)
  and in LOOT 0.23.0 ("Support for medium plugins when Starfield is the current game"). Measuring its real record limit
  in game is still open (question 32).
- `leader-core-and-starfield-modding-2026-10-14.md` section 3 lists three plugin types. Starfield has two more that
  tools treat specially: **update** plugins (formerly "overlay", which take a load-order slot since Starfield 1.12.30
  per LOOT 0.23.0) and **blueprint** masters (LOOT 0.24.0). Note also that Bethesda's "worldspace overlays" (terrain)
  are not "overlay plugins" (Nexus news 14993).
- The same section calls 1.16.244 the newest version only as a supported hypothesis as of 12 Oct. It is still the newest
  on 19 Oct per starfield.gg ("no new patch since June"). This is **verified** to the level that source allows.

## Precedents and what they teach us
- **1.15.216 compiler change** (SFSE 0.2.17): a patch with no gameplay notes invalidated every SFSE plugin. Lesson: any
  SFSE shim we ship is a per-patch maintenance item; keep native code minimal and Papyrus-first.
- **1.11.36 mesh renames**: a patch silently renamed vanilla mesh paths; a 323k-entry mapping tool was needed. Lesson:
  our converter must resolve vanilla Starfield asset paths at build time on the player's PC, never hard-code them.
- **1.14.70 root form class change**: record-layer code (SFSE) had to recompile. Mutagen/xEdit gained a header `BNAM`
  from 1.9.51 (xEdit 4.1.5c). Lesson: re-run our Mutagen round-trip and header tests on each game version.
- **xEdit Discord-only distribution**: a key community tool can become unscriptable to fetch. Lesson: depend only on
  tools with stable public packages (NuGet Mutagen, GitHub NifSkope), use others as optional oracles.
- **Fallout: London downgrader** (project roadmap): pinning a game version through credentials is a support and trust
  cost we already decided not to pay.

## Risks
1. **A Starfield patch lands mid-release (medium likelihood over a year; low within weeks).** Cadence in 2026: April,
   May, June, then silence; 2027 content announced. Steam auto-updates. SFSE same-day turnaround for small patches,
   but a compiler-setting patch breaks all SFSE plugins until each author rebuilds.
2. **CK-only steps cannot be automated (high likelihood for lip sync, unknown for LOD).** FaceFX compiler documented as
   a GUI menu; 122,857 FO4 `.fuz` voice lines would need WAV extraction, `.wem` encoding and `.ffxanim` generation on
   each player's PC. If no batch path exists, voiced dialogue stalls.
3. **`.wem` encoding (high).** Starfield plays `.wem`; producing it normally needs Audiokinetic Wwise (licensing and
   install burden; **supported hypothesis** from general knowledge, not read this session).
4. **Plugin type budget (medium).** Converted world content must stay full masters; update plugins now cost a slot;
   blueprint masters have special rules. A many-plugin design hits 253 sooner than expected with Creations installed.
5. **xEdit cannot open what we write (medium).** If our plugins use update/overlay flags or blueprint masters, xEdit
   (our oracle) refuses them; keep oracle-friendly flags in test builds.
6. **Mutagen alpha churn (low-medium).** 0.55 alphas change weekly; Starfield mod-index fixes landed in 0.54.4. Pin a
   version, upgrade deliberately with round-trip tests.
7. **Game Pass players (certain, scope).** No SFSE; different paths for loose files. Either exclude or design an
   SFSE-free tier.
8. **LOD/precombines unknown (medium).** Exterior breadth (one planet with the Commonwealth) depends on distant LOD; no
   public `.btd`/`.lod` writer and no documented CK LOD batch.

## Questions for the framework

### New game
1. **Which game version does the new-game start require, and what does the launcher do on mismatch?** Why: SFSE and our
   shims bind to one runtime. Options: hard refuse (current docs), warn and run data-only tier, maintain a version
   matrix. Evidence: SFSE whatsnew plus Address Library dates per patch. Who: owner decision.
2. **Can the Vault 111 start be built with no SFSE at all (data + Papyrus only)?** Why: keeps the first phase alive
   through a compiler-setting patch. Options: Papyrus-only quest start (`ShowRaceMenu`, `SetInChargen` exist in SF);
   SFSE only for later menus. Evidence: PC probe of a no-SFSE launch. Who: PC probe.
3. **Does a Starfield patch reset Plugins.txt / `Starfield.ccc` or re-enable Creations order?** Why: 1.15.214 touched
   "Creations load order restoration". Evidence: diff Plugins.txt and `.ccc` before/after the next patch. Who: PC probe.

### Door animations
4. **Do door clip assets (`.af` via CALUMI) survive game patches, or do path renames like 1.11.36 recur for animation
   files?** Evidence: keep a hash list of vanilla paths we reference; re-check after each patch. Who: offline tooling.
5. **Can the CK preview our door PackIns/doors, or must every check be in-game?** Why: CK is an oracle (PLAN L2). Evidence:
   load our ESM in the CK once and scrape its log. Who: PC probe (owner time).

### All interiors
6. **Is CK batch navmesh (`-UpdateNavmeshGeneration ... -Part`) usable on our ESM for 1,000+ interiors?** Why: converted
   FO4 navmesh is the plan, CK generation the fallback. Options: R4 converted, R5 CK batch. Evidence: run on 3 cells,
   time it, diff output. Who: PC probe.
7. **Does Starfield have a precombine/previs step at all, and does missing it cost interior frame time?** Evidence: scan
   Starfield.esm for precombine-like data on vanilla interiors (xEdit/Mutagen), CK menu strings. Who: offline research + PC.
8. **Interiors as small/medium masters?** A medium master holds ~65,535 records; FO4 interior clusters could be split
   by region into medium masters to save full slots. Changing type later is unsupported (Bethesda). Who: owner decision
   with a record count per cluster (offline).

### Launcher
9. **How does the launcher detect the game version and store?** Options: exe file version, Steam `appmanifest`, presence
   of `XboxGames` path. Evidence: one PC read. Who: offline + PC probe.
10. **Does the launcher fetch SFSE and Address Library, or ask the player?** SFSE is on GitHub/silverlock and Nexus;
    Address Library is Nexus-only (account, rate limits). Redistribution permissions **unresolved**. Who: owner + author
    contact.
11. **Where does the launcher get Archive2 and the Papyrus compiler: the CK install (Steam app 2722710), or bundled
    open alternatives (bsa-rs, Caprica)?** Why: requiring an 823 MB CK install is acceptable (settled) but adds a step.
    Evidence: test our pipeline with CK absent. Who: offline + owner.
12. **INI: write `StarfieldCustom.ini` or avoid it?** Controlled Folder Access blocked Documents writes on the owner's PC;
    `- Main.ba2` per plugin avoids INI edits. Decide a rule: no INI writes unless the player opts in. Who: owner decision.
13. **Pin strategy: Stock Game copy (MO2 style), Steam "update only when launched", or refuse?** Stock Game copy doubles
    disk use (~100+ GB, **supported hypothesis**). Who: owner decision.
14. **Archive budget: per-archive 4,095 MB, per-plugin `- Main.ba2` and `- Textures.ba2` naming; how many archives can a
    plugin auto-load (`- Main01.ba2`?)?** **unresolved**. Evidence: PC probe with two numbered archives. Who: PC probe.

### World and planet
15. **How is LOD made for an Earth-like planet with the Commonwealth: CK LOD generation, our own `.btd`/`.lod` writer, or
    none?** Evidence: CK strings scan for LOD switches; `.lod` format spike. Who: offline research then PC.
16. **Does the CK load our worldspace overlay plugin without crashing, so we can use its tools on it?** Who: PC probe.
17. **Plugin slots for world breadth:** Commonwealth + Far Harbor + Nuka-World as full masters vs split; how many slots do
    typical players' Creations take? Evidence: LOOT/plugins.txt counts from testers. Who: community contact.

### People and story
18. **Can FaceFX lip generation be run in batch (command line or scripted CK) for ~123k lines?** Options: CK GUI per
    plugin (documented), a CreationKit.exe switch (unknown), keep FO4 `.lip` data and convert to `.ffxanim` (format
    unknown), silent fallback without lip sync. Evidence: strings scan of CreationKit.exe for FaceFX switches; one test
    batch timing. Who: offline + PC probe.
19. **How do we make `.wem` without shipping Wwise?** Options: Wwise CLI on player PC (licence), community encoders,
    replace `.wem` playback by another sound path. Evidence: Wwise licence terms; test whether Starfield plays other
    formats. Who: offline research + legal-ish owner decision.
20. **Voice type and body type must match for lip generation**: does our NPC conversion keep FO4 voice types mapped
    consistently? Who: offline (converter test).

### Fallout systems
21. **Which systems need SFSE natives, and what is our policy when a patch breaks SFSE plugins?** Options: degrade (hide
    Pip-Boy menu), block launch, ship Papyrus fallback. Who: owner decision.
22. **Without SFSE serialization (disabled since 0.2.12), where does SFSE-plugin state live?** Options: Papyrus
    properties/globals only; separate file next to saves. Who: offline design.
23. **Scaleform menu interface (SFSE 0.1.3) for Pip-Boy: is it still working on 1.16.244?** Evidence: one known mod that
    uses it. Who: community contact / PC probe.

### Release and community
24. **Game Pass players: excluded, or an SFSE-free tier?** Address Library has MS Store bins but SFSE refuses non-Steam.
    Who: owner decision.
25. **Which tools do we require players to install vs only the team?** (CK yes; xEdit no, Discord-only; NifSkope no.)
    Who: owner decision.
26. **GPL-3 obligations for Mutagen and Spriggit in the launcher** (source offer, licence text). Who: owner, with a short
    licence check.
27. **Nexus distribution of a tool that needs SFSE + CK**: tag requirements and Nexus requirement links. Who: owner.

### Tooling and testing
28. **Which Mutagen version do we pin, and how do we test upgrades?** 0.55 alphas weekly; Starfield index fix in 0.54.4.
    Evidence: round-trip tests on both. Who: offline.
29. **Adopt Spriggit to diff our generated plugins in CI?** It gives per-record YAML diffs on Linux. Risk: 683k-record
    plugins may be slow/large. Evidence: time a serialize of core64c. Who: offline.
30. **Which oracle reads our plugins if xEdit refuses update/blueprint flags?** Options: Mutagen re-read, CK load, game.
    Who: offline decision.
31. **A "patch day" checklist**: what we re-run after each Starfield patch (SFSE/Address Library versions, NifSkope
    loads vanilla mesh, Mutagen reads Starfield.esm header, our plugin loads, vanilla path hash list). Who: owner to
    approve; QA to own.

### Cross-cutting
32. **Medium master record limit: ~65,535 (Bethesda) or ObjectID ≤ 0xFF (MO2 BPM page)?** Evidence: write a synthetic
    medium master with 4,000 and 60,000 records and load it. Who: PC probe.
33. **Update (overlay) plugins: useful for us (records overriding Starfield without new forms) now that they cost a slot?**
    Who: offline design.
34. **Does the CK track game versions exactly, i.e. does a CK older than the game refuse or corrupt plugins?** Evidence:
    CK version in its exe after next patch. Who: PC probe.

## Sources
- SFSE changelog: https://raw.githubusercontent.com/ianpatt/sfse/master/sfse_whatsnew.txt
- SFSE Nexus: https://www.nexusmods.com/starfield/mods/106
- Address Library: https://www.nexusmods.com/starfield/mods/3256 ; STEP page https://stepmodifications.org/wiki/Starfield:Address%20Library%20for%20SFSE%20Plugins
- SFSE ASI Loader: https://www.nexusmods.com/starfield/mods/857
- Ez-SFSE-Plugins: https://www.nexusmods.com/starfield/mods/14577
- Game updates: https://starfield.gg/starfield-latest-update/ ; https://www.gamewatcher.com/Starfield/guides/patch-notes-hub-and-roadmap-of-updates-for-2026 ; https://bethesda.net/en/article/2HBTwuF9g9baAQkEud4WZ9/starfield-update-1-16-242-may-14-2026 ; https://bethesda.net/en-US/news/starfield-update-1-16-244-june-2026 ; https://steamdb.info/patchnotes/18285521
- CK: https://www.nexusmods.com/news/14993 ; https://starfieldwiki.net/wiki/Starfield_Mod:Creation_Kit ; https://stepmodifications.org/wiki/Starfield:Creation_Kit ; https://dev.starfieldwiki.net/wiki/Starfield_Mod:Main_Page
- Lip sync: https://dev.starfieldwiki.net/wiki/Starfield_Mod:Audio_File_Conversion ; https://nexusmods.com/starfield/mods/12576 ; https://facefx.com/node/4600
- xEdit: https://github.com/TES5Edit/TES5Edit/releases ; https://github.com/TES5Edit/TES5Edit/releases/tag/xedit-4.1.5 ; https://reddit.sentinel-team.org/posts/1u6jz38/snapshots/2026-06-16T07%3A02%3A42.6264Z
- Mutagen: https://www.nuget.org/packages/Mutagen.Bethesda.Starfield ; https://github.com/Mutagen-Modding/Mutagen ; https://api.github.com/repos/Mutagen-Modding/Mutagen/releases?per_page=8 ; https://mutagen-modding.github.io/Mutagen/
- Spriggit: https://github.com/Mutagen-Modding/Spriggit ; https://www.nuget.org/packages/Spriggit.Yaml.Starfield ; https://api.github.com/repos/Mutagen-Modding/Spriggit/releases?per_page=6
- Synthesis: https://github.com/Mutagen-Modding/Synthesis ; https://mutagen-modding.github.io/Synthesis/
- LOOT: https://loot.readthedocs.io/en/0.24.1/app/changelog.html
- MO2 plugin manager: https://www.nexusmods.com/starfield/mods/17318
- Meshes: https://github.com/fo76utils/nifskope/releases ; https://nexusmods.com/starfield/mods/4360 ; https://github.com/BadDogSkyrim/PyNifly/ ; https://www.nexusmods.com/starfield/mods/9234
- Archives/INI: https://github.com/ejams1/starfield-modding-guide ; https://forums.nexusmods.com/topic/13459379-a-guide-to-game-pass-modding-no-mod-manager
- Repo (447ec09): docs/actors/npc-navigation.md §2.4; docs/spikes/S2-S4-S9-plugin-units-loading.md; docs/FORMAT-GAP.md; docs/ROADMAP.md C1; docs/SETUP.md; docs/PLAY-AND-TEST.md; docs/ai/known-unknowns.md
- Not read (HTTP 429 rate limit): https://www.nexusmods.com/starfield/mods/17161 ; https://www.nexusmods.com/starfield/mods/7830 ; https://github.com/JMPZ11/nifskope-sf-mesh/ ; mp1st 1.16.244 article ; kitguru CK improvements article. Steam Community threads were behind a content gate.
