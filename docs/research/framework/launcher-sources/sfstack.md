# Starfield PC modding stack, as of October 2026: research for the fo4-to-starfield launcher

Author: Claude (research subagent). Date: 2026-10-19. Scope: web research plus a re-read of this repo's measured BA2 data.
Labels follow docs/ai/research-log.md:
- **verified**: I read the cited page, and the claim is on it. This is a page claim, not an in-game test.
- **supported hypothesis**: I inferred it from read sources, or it comes from a search snippet or user reports.
- **unresolved**: no source I read settles it.

"Verified" here means *the source says so*. None of it is an in-game acceptance test on the owner's machine.

Pages I could not read: docs.rs `ba2` module docs, `github.com/ryan-rsm-mckenzie/bsa-rs` (it was later read
through another fetcher), Nexus mods 165 and 14468 and primagames (rate-limited, HTTP 429, on the first fetcher; 165 and
primagames were read later). Also the Bethesda Starfield EULA page (empty), Nexus article 578 and Address Library posts (timeouts), and
several Steam discussion threads (only the language picker came back). No claim below depends on a page I failed to read.

---

## 1. Update cadence 2024–2026 and what each update broke

### Version timeline (Steam runtimes that got an SFSE build)
Source for all rows: SFSE posts tab, https://www.nexusmods.com/starfield/mods/106?tab=posts (**verified** that the page lists these).

| Game runtime | Date | SFSE | Mod impact noted |
|---|---|---|---|
| 1.11.36 | 2024-05-15 | yes | – |
| 1.12.30 / 1.12.32 | June 2024 | yes | Creation Kit + Creations launch; plugins.txt now read natively (see §2) |
| 1.12.36 | 2024-07-03 | yes | – |
| 1.13.61 | 2024-08-21 | yes (0.2.12 hotfix 2024-08-23 for "serialization code" problems) | – |
| 1.14.70 | 2024-09-30 | yes | Bethesda "changed the base form type"; gameplay SFSE plugins had to be recompiled; some crashed |
| 1.14.74 | 2024-11-19 | yes | – |
| 1.15.214 / .215 / .222 | May–Aug 2025 (Steam beta) | betas not supported until main branch | – |
| 1.15.216 | 2025-05-22/23 | 0.2.17 | "has broken most if not all plugins, as well as the Address Library" |
| 1.16.236 | 2026-04-07 | 0.2.19 | Free Lanes update / Terran Armada DLC / PS5 launch; `sTestFile` ordering changed (LOOT changelog, below) |
| 1.16.242 | 2026-05-14 | 0.2.20 | Creations crash fixes |
| 1.16.244 | 2026-06-11 | 0.2.21 | current patch as of 2026-10-12 |

- An SFSE update has followed every Steam runtime change. DLL plugins also need an Address Library update: version 22
  was updated 2026-06-13, and its files tab says "Contains all versions up to game version 1.16.244.0 of Steam".
  **verified** from https://www.nexusmods.com/starfield/mods/3256 (page date) and the search snippet for `?tab=files`
  (the snippet itself is a **supported hypothesis**).
- Address Library post: "Version 1.15.216 made many changes in code (changed compiler options), that made creating new
  address library impossible". This is a **supported hypothesis** because I only saw it as a search snippet of
  https://www.nexusmods.com/starfield/mods/3256?tab=posts; the page timed out.
- Address Library ships separate MS Store builds (`versionlib-x.y.z.0.1.bin`, where the trailing 1 means MS Store).
  **verified**, https://www.nexusmods.com/starfield/mods/3256
- Release dates and current patch 1.16.244: **verified**, https://starfield.gg/starfield-latest-update/ (page dated 2026-10-12).
  1.16.242 contents: **verified**, https://starfield.gg/starfield-update-1-16-242-patch-notes-may-2026/
- Official 1.15.216 notes: Creations bundles, a 2 GB Creation upload limit, a fix for an error "restoring load order after a large number of
  mods were installed and then deleted", a CK fix for ingredient forms. Nothing about plugin format. **verified**,
  https://bethesda.net/article/3eFYYUUqzOpOSv086XWMh9/starfield-update-notes-may
- 2023 history: 1.8.86 (Nov 2023) crashed for users whose SFSE was out of date. **verified** (user thread),
  https://forums.nexusmods.com/topic/13453760-version-18860-problems
- **Supported hypothesis:** updates have broken SFSE/DLL mods several times (1.14.70, 1.15.216). No source says an
  update broke plain ESM+BA2 content. Our content does not depend on SFSE, so update risk for us is mostly plugin-format
  and load-order behaviour (form versions, record definitions, Plugins.txt handling). That needs our own regression
  check after each patch.
- **Unresolved:** whether any 2025–2026 patch bumped the plugin HEDR version or form version in a way that makes
  older-built ESMs load wrong. No source I read covers it.

### Pinning versions
- **Steam depot downgrade (verified page claim):** https://genesismodlist.com/downgrading-starfield/ (2024-08-23, edited 2024-12-15)
  uses the Steam console (`steam://open/console`) with `download_depot 1716740 1716741 <manifest>` and
  `1716740 1716742 <manifest>`. Extra depots are 2401180 (Premium upgrade) and 2401181 (preorder). It copies
  `steamapps\content\app_1716740\*` over the install, turns off automatic updates in Steam, and keeps the downloaded folder for re-use.
  Its target was 1.13.61. The manifest IDs are version-specific and that page's IDs are for 1.13.61 only.
- **Supported hypothesis:** DepotDownloader (the community CLI) uses the same app/depot/manifest triple and is the
  scriptable equivalent. I did not read its docs this session.
- **Supported hypothesis:** Steam has no true "never update" switch. The setting "only update when launched" plus
  launching the exe directly is the common practice. The Genesis guide says only "turn off automatic updates" and warns
  that launching through MO2 may update the game.
- **Supported hypothesis:** the big modlists (for example Star Wars Genesis) pin a runtime and tell users to downgrade.
  A launcher shipping plain ESM+BA2 content may not need to pin, if our content is tested on each new runtime.

### Game Pass / Microsoft Store
- Vortex's Starfield extension supports Steam **and** Game Pass. Game Pass installs in the default WindowsApps location
  are restricted, so it recommends installing to `C:\XboxGames` and setting the game folder manually. SFSE is
  Steam-only, and ASI Loader is used on Game Pass. **verified**, https://www.nexusmods.com/site/mods/634 (v1.10.5, updated 2026-06-10)
- A Game Pass manual guide (Dec 2023, edited Feb 2024) gives: install `D:\XboxGames\Starfield\Content` with
  `Starfield.exe` visible, plugins in `Content\Data`, `Plugins.txt` in `%LOCALAPPDATA%\Starfield`, and
  `StarfieldCustom.ini` in `Documents\My Games\Starfield`. **verified** page claim (but pre-CK, old),
  https://forums.nexusmods.com/topic/13459379-a-guide-to-game-pass-modding-no-mod-manager
- libloot 0.28.2 (2025-10-03) added "DLC install paths used by the Microsoft Store distribution". **verified**,
  https://loot-api.readthedocs.io/en/stable/api/changelog.html
- SFSE page: "Game Pass discussion is off topic", and a 2026 answer says SFSE is not for Windows/Xbox. **verified**,
  https://www.nexusmods.com/starfield/mods/106?tab=posts
- **Supported hypothesis:** since 1.12.30 the native Plugins.txt works on every PC store. Game Pass players can therefore
  install ESM+BA2 content if the game is in an accessible folder such as `XboxGames\Starfield\Content`, which is the
  default for newer Xbox app installs. Nothing says they cannot. **Unresolved:** whether Game Pass Plugins.txt now sits at the same
  `%LOCALAPPDATA%\Starfield` path, and whether the 2026 Xbox app still installs outside WindowsApps by default.

---

## 2. Plugins

### Types and limits
From Nexus's CK launch post (Pickysaurus, 2024-06-10), **verified**, https://nexusmods.com/news/14993:
- **Full master:** one of 253 load-order slots (counted after base game and DLC).
- **Medium master:** shares slot 254 (`FD`), about 65,535 new records each, up to 256 loaded.
- **Small master:** shares slot 255 (`FE`), 4,095 new records each, up to 4,096 loaded.
- Bethesda: "Changing the flag on an existing creation [plugin] isn't supported." The article: "All mods being shared
  with the community should be using ESM format plugins." 1.12.30 "enables mod loading by default", so Plugins.txt Enabler
  and SFSE are no longer needed.

From Ortham (LOOT author), "Load order in Starfield", 2024-06-28 (tested on 1.12.30/1.12.32), **verified**,
https://blog.ortham.net/posts/2024-06-28-load-order-in-starfield/:
- Flags: small `0x100` (was `0x200` in FO4), update `0x200`, medium `0x400`. The `.esl` extension also means small.
- Medium: maximum 256 active, 65,535 records. Light/small: maximum 4,096 active, 4,095 records. Runtime FormIDs are `FDxxyyyy`.
- **Critical:** a Starfield plugin file does **not** record what type each master was when it was saved. Resolving
  FormIDs needs the masters' current flags. "If a plugin is saved with a master and that master's type is then
  changed ... everything breaks." Ortham also reports a CK bug that makes it easy to change a plugin's type by accident when saving.
- Update plugins have taken a normal slot since 1.12.30.
- `Starfield.ccc` is read from `My Games\Starfield\` first, then the install directory. Plugins listed there load first.
- A plugin in `My Games\Starfield\Data` is loaded **only** if a same-named plugin exists in the install `Data`.
- Defining any `sTestFile1..10` makes the game **ignore Plugins.txt and Starfield.ccc**.
- The game **rewrites Plugins.txt at startup.** It inserts `.ccc` entries at the top and removes implicitly active plugins.

Other plugin facts:
- Blueprint plugins (flag `0x800`) are hidden in the CK unless `bShowBluePrintMastersInDataFiles=1`, and Starfield removes them from
  Plugins.txt at startup. Blueprint *masters* load **after all other plugins**, and a non-blueprint plugin that masters
  one cannot hoist it, so its overrides of blueprint records are not seen in game. **verified**,
  https://blog.ortham.net/posts/2024-07-30-blueprint-plugins/
- "BlueprintShips plugins" (any `BlueprintShips-X.esm`) are implicitly activated when `X.esm/.esp/.esl` is active, and
  removed from Plugins.txt at startup. LOOT, MO2, xEdit, Wrye Bash and Vortex agreed (May 2026) not to write blueprint
  or BlueprintShips plugins to Plugins.txt. Since 1.16.236, `sTestFile` plugins get written to Plugins.txt, ahead of the others.
  **verified**, https://blog.ortham.net/posts/2026-05-04-starfield-blueprintships-plugins/ and libloot 0.29.4 notes
  (https://loot-api.readthedocs.io/en/stable/api/changelog.html)
- Hardcoded official positions since 1.14.70: Starfield, Constellation, OldMars, ShatteredSpace (index 01), SFBGS003…008;
  SFBGS00D/047/050 added 2026-04. **verified**, same libloot changelog.
- Mods that list `BlueprintShips-Starfield.esm` as a master are a known problem. Older xEdit (before 4.1.5m) added it
  automatically, and users report stutter and load-order shifts. **verified** (community PSA, April 2025),
  https://www.reddit.com/r/starfieldmods/comments/1jyl6zv/ . A 2026 thread reports that removing it with the current
  CK can corrupt plugins ("HITME" errors). **verified** user report,
  https://stepmodifications.org/forum/topic/21417-i-have-to-choose-between-the-devil-and-the-deep-blue-sea-for-starfield/
- Mod-index limit: a user says the "old mod index limit" was "supposedly fixed" with the Oct 2024 (Shattered Space)
  update, and LarannKiar mentions a fix "in v1.14.70". **supported hypothesis** (forum posts),
  https://forums.nexusmods.com/topic/13518743-crash-issue-too-many-ba2-files-causing-ctds-%E2%80%93-looking-for-fix-or-insight/

### Plugins.txt format
- Location `%LOCALAPPDATA%\Starfield\Plugins.txt`. The first line(s) must be the header, and each enabled plugin is `*Name.esm`.
  **verified**, https://nexusmods.com/starfield/articles/303 (edited 2024-03-14)
- Header text: `# This file is used by Starfield to keep track of your downloaded content.` /
  `# Please do not modify this file.` This is a **supported hypothesis** from a search snippet of
  https://www.nexusmods.com/starfield/mods/4157?tab=posts. The repo's deploy already writes `*FO4Port.esm` and it works
  (docs/spikes/S2-S4-S9-plugin-units-loading.md), which is **verified locally**.
- The game deletes listed plugins it cannot find in Data, adds new `.esm` files unchecked, and setting the file read-only does not help
  because the game resets the read-only attribute. **verified** (tool author / forum),
  https://www.nexusmods.com/starfield/mods/10432?tab=posts and
  https://forums.nexusmods.com/topic/13490787-the-game-changes-my-load-order/
- `ContentCatalog.txt` tracks Creations (version etc.). MO2 2.5.2 parses Creations from it. **verified**,
  https://www.nexusmods.com/starfield/mods/10432?tab=posts and https://github.com/Modorganizer2/modorganizer/releases

### INI and loose files
- Standard loose-file recipe: `[Archive] bInvalidateOlderFiles=1` and `sResourceDataDirsFinal=` (empty) in
  `Documents\My Games\Starfield\StarfieldCustom.ini`. **verified**, https://nexusmods.com/starfield/articles/116 and
  https://modding.wiki/en/starfield/users/loose-file-modding
- Loose files load from `Documents\My Games\Starfield\Data` *or* the install `Data`. If both are present, Documents wins, so the
  install's loose files won't load. The MOTD image and photo mode write into Documents `Data\Textures`, so add
  `[General] bEnableMessageOfTheDay=0`. **verified**, modding.wiki page above.
- Vortex checks and offers to add the minimum loose-file INI settings. **verified**, https://www.nexusmods.com/site/mods/634
- **Supported hypothesis (consistent with owner's machine):** the stock `Starfield.ini` ships
  `sResourceDataDirsFinal=STRINGS\`, so without the override, loose files outside STRINGS don't load. Loose files
  still work in 2026 with the override (no source says it was removed), but **unresolved** for 1.16.244 specifically.
- Local evidence (repo): Windows Controlled Folder Access blocked writes to Documents on the owner's PC, so the project uses
  BA2 + Plugins.txt and no INI. `<plugin> - Main.ba2` loads automatically beside `<plugin>.esm`. **verified locally**,
  docs/spikes/S2-S4-S9-plugin-units-loading.md
- `sResourceIndexFileList` (comma-separated) can force-load named BA2s. This is the FO4-era method and one Starfield mod page
  describes it. **supported hypothesis** for Starfield, https://www.nexusmods.com/starfield/mods/9183

---

## 3. BA2 archives

- **Verified locally** (repo `docs/measurements/sf_ba2.json`, 78 vanilla archives on the owner's install): 57 are
  v2 GNRL with no compression field, 6 are v2 DX10, and 15 are **v3 DX10 with compression_method 3** (e.g.
  `Starfield - LODTextures01.ba2`). The repo's own Archive2-made archive is v2 GNRL (S9 spike). docs/FORMAT-GAP.md records
  "2 (GNRL / DX10), 3 (LZ4 textures)".
- OpenMW MR on BA2: "version 2 is not a valid Starfield DDS BA2 version"(sic, as quoted on the page). It adds zlib-compressed Starfield DDS BA2 support
  ("limited usefulness"), and says LZ4 DDS BA2s use block (not frame) compression. FO4 next-gen v7/v8 are "apparently
  unchanged". **verified** page claim, https://gitlab.com/OpenMW/openmw/-/merge_requests/4055. The claim about v2 DDS
  conflicts with our 6 vanilla v2 DX10 archives, so **unresolved** what OpenMW meant.
- **Archive2** ships with the free Starfield CK in `Starfield\Tools\Archive2`. It has a CLI: `Archive2 <archive, files/folders>
  [args]` with `-create/-c`, `-extract/-e`, `-root/-r`, `-format General|DDS|XBoxDDS`,
  `-compression None|Default|XBox|LZ4`, `-maxSizeMB`, `-count`, `-sourceFile`, `-includeFilters`, `-quiet`,
  `-tempFiles`, `-cleanup` (don't use with parallel instances). **verified**,
  https://starfieldwiki.net/wiki/Starfield_Mod:Archive2
- The FO4-era Step guide says to keep the archive size at "4095 MB maximum for the engine to properly load the archive". **verified** for FO4
  (https://stepmodifications.org/wiki/Guide:Archive2). It is a **supported hypothesis** for Starfield and **unresolved** whether Starfield's
  v2/v3 header removes the 4 GB limit.
- Texture and non-texture assets must be in separate archives, and a plugin is needed to load them (an empty small master
  works). WEM sounds moved into a compressed archive "will most likely not play". **supported hypothesis** (forum
  advice), https://forums.nexusmods.com/topic/13518743-…
- **Archive2 licence:** the Starfield CK EULA (https://store.steampowered.com/eula/2722710_eula_0, **verified**)
  grants "a limited, personal, non-exclusive, non-transferable ... license ... to (i) install a copy of the Editor on
  computers that You own and (ii) use the Editor solely for the purpose of creating and developing Game Mods". It
  forbids renting, selling, sublicensing, copying or reproducing the Editor, and limits use to "personal non-commercial use ... or ... Game Mods,
  approved by Bethesda ... distributed through Bethesda Creations". **Supported hypothesis:** Archive2 counts as part
  of "the Editor". We therefore cannot **redistribute** Archive2. A launcher that calls the player's *own* installed Archive2
  probably fits "personal non-commercial use", but that is a legal reading, so it stays **unresolved** until the owner decides.
  The cleaner path is to ship prebuilt BA2s (built on the owner's machine) or build them with an OSS writer.
- **Alternatives:**
  - B.A.E. (hexabit) 0.18, extract-only. "0.13 - Starfield support, 0.15 - Fixed Version 3 Texture BA2s". No licence is
    stated on the page. **verified**, https://www.nexusmods.com/starfield/mods/165
  - `ba2` Rust crate / bsa-rs: "near-complete support for all archive variants from Morrowind up to Starfield",
    reader **and writer**, **0BSD licence**. **verified**, https://github.com/ryan-rsm-mckenzie/bsa-rs
  - "Starfield BA2 Manager and Compressor" (Python/Tk, MIT, v1.0, 2026-08-03) reads and creates General and DX10
    archives. It is new and unproven. **verified** page claim, https://www.nexusmods.com/starfield/mods/17849
  - xEdit 4.1.5f reads FO4 v7/v8 BA2. **verified**, https://github.com/TES5Edit/TES5Edit/releases/
  - **Unresolved:** BSArch's current Starfield write support (v2 GNRL / v3 DX10 LZ4) and its licence (xEdit's code is
    MPL-2.0 in my memory, which is unverified). BSA Browser's Starfield support and licence are also not checked.

---

## 4. Mod managers and Creations

- **MO2:** the latest public release is **v2.5.2 (Aug 2024)**. It added Starfield Creation support: CK executable,
  ContentCatalog parsing, `Starfield.ccc` to "fix" core order, **medium plugin support (FD)**, and a warning on
  light+medium flags. Plugins.txt Enabler is obsolete. MO2 2.5.0 virtualises both the My Games `Data` and the game `Data`.
  **verified**, https://github.com/Modorganizer2/modorganizer/releases. Release notes don't mention blueprints or root builder.
  - 2026 users say the Nexus build "doesn't properly work": it auto-disables some game masters on every launch and the
    saves tab crashes. Current builds are Discord-only betas. **verified** user reports (May 2026),
    https://www.reddit.com/r/starfieldmods/comments/1tiz8b6/
  - "Bethesda Plugin Manager - Re Extended" (2026-05-31, needs MO2 ≥ 2.5.2) force-enables and sorts blueprint plugins and
    supports medium and overlay. **verified**, https://www.nexusmods.com/starfield/mods/17318
  - **Unresolved:** whether MO2's USVFS reliably covers Starfield's `My Games\Data` + install-Data rule, and whether
    Root Builder is needed for anything we ship. With BA2 + ESM in `Data` only, we probably don't need it.
- **Vortex:** Starfield extension 1.10.5 (2026-06-10). Drag-and-drop or LOOT ordering, native plugins not written to
  plugins.txt, an opt-in junction linking `My Games\Starfield\Data` to the game Data (warns about OneDrive data loss),
  INI check, ASI Loader, Game Pass support. Symlinks are disabled ("some files work and others don't"). **verified**,
  https://www.nexusmods.com/site/mods/634. One user fixed self-disabling plugins by switching Vortex to
  "Rules-based (Classic)". **verified** user report (2026), https://forums.nexusmods.com/topic/13537716-…
- **Creations menu coexistence:**
  - The game rewrites Plugins.txt and removes missing entries. With Steam offline, opening the Creations menu can sort and
    activate everything alphabetically. Creations updates can overwrite Nexus copies of the same mod. Users suspect
    Creations reorders and disables externally managed plugins, which links to the "use current load order / use load
    order from save" prompt. These are **verified** user reports, but the cause is a **supported hypothesis**.
    https://www.nexusmods.com/starfield/mods/10432?tab=posts and https://forums.nexusmods.com/topic/13537716-…
  - 1.15.216 fixed an error "restoring load order after a large number of mods were installed and then deleted".
    **verified**, bethesda.net May 2025 notes.
- **Achievements:** mods or console use mark the save as modded and disable achievements (2023). **verified**,
  https://primagames.com/tips/do-mods-disable-achievements-in-starfield-answered. Bethesda added
  "achievement-friendly" Creations (Nov 2024), and later reports say premium Creations are achievement-friendly. This is a
  **supported hypothesis** (search snippets: trueachievements 2024-11-20, reddit). External ESMs like ours will
  disable achievements unless the player uses a community enabler (SFAE / Baka Achievement Enabler, which are SFSE/ASI
  DLLs). **Supported hypothesis.**

---

## 5. Tools

- **xEdit / SF1Edit:** the latest GitHub release is **4.1.5f (Apr 2024)**. Newer builds (4.1.5o as of mid-2025) are Discord-only.
  Run it with `-sf1` or rename the exe to SF1Edit64. The 4.1.5 notes say: only the 64-bit build copes with the data; it saves **only .esm**; it refuses
  ESL/Overlay-flagged files (4.1.5 era); `Starfield.esm` and `BlueprintShips-Starfield.esm` are forced masters in that
  version; it warns that overriding PKIN is unpredictable and GBFM copy crashes. **verified**,
  https://github.com/TES5Edit/TES5Edit/releases/ and https://www.nexusmods.com/starfield/articles/659 (edited
  2025-06-01). A Sept 2026 comment claims "xEdit no longer supports Starfield", which is **unresolved**. A 2026 Step forum post
  says the xEdit Discord channel was renamed "Starfailed", which is a **supported hypothesis** about maintainer sentiment.
- **Mutagen:** has Starfield modules (`Mutagen.Records.Starfield.sln`), **GPL-3.0**. **verified**,
  https://github.com/Mutagen-Modding/Mutagen. The maturity of Starfield support is **unresolved**: the page states none.
  NuGet `Mutagen.Bethesda.Starfield` exists (nightly 2023-09). That rests on a search result only, so it's a **supported hypothesis**.
- **Spriggit:** converts plugins to and from YAML/JSON for Git, has a CLI (`serialize` / `deserialize --GameRelease ...
  --PackageName Spriggit.Yaml`), uses Mutagen, **GPL-3.0**, and pulls translation packages from NuGet at runtime.
  **verified**, https://github.com/Mutagen-Modding/Spriggit. Starfield as a `GameRelease` is **supported hypothesis**,
  not confirmed on the page.
- **Starfield Creation Kit:** Steam app **2722710**, free, released 2024-06-09, needs a 3rd-party EULA. Minimum spec is **32 GB RAM**,
  Win10 21H1, SSD; recommended is 48 GB. **verified**,
  https://store.steampowered.com/app/2722710/Starfield_Creation_Kit/. It "requires an installation of Starfield on the
  same drive volume". **verified**, https://starfieldwiki.net/wiki/Starfield_Mod:Starfield_Creation_Kit. CLI
  automation of the CK itself is **unresolved**.
- **Papyrus:** the CK ships a Papyrus compiler plus VS Code integration (Nexus CK post). Users hit a missing
  `Starfield_Papyrus_Flags.flg` (Steam CK forum snippet). Community alternative: **Caprica**
  (`caprica.exe --game starfield --import ... --output ... --recurse ...`) and Champollion for decompiling. **verified**,
  https://www.nexusmods.com/starfield/mods/3921. Whether the CK compiler's CLI flags match FO4's `PapyrusCompiler.exe`
  is a **supported hypothesis**.
- **LOOT / libloot:** actively maintained for Starfield through 2026 (0.29.x). It handles medium, blueprint,
  BlueprintShips, hardcoded plugins and MS Store paths. **verified**, the LOOT changelogs above.

---

## 6. Size, performance and limits

- **BA2 count limit: 256 active archives** (8-bit index), with separate registries for GNRL and DX10. "BA2 Limit Fix"
  (SFSE plugin, 2026-08-14, for 1.16.236/1.16.244) extends each to 65,535. Its author tested 260+260 fixture archives,
  and a tester ran 350 GNRL + 277 DX10. **verified** page claim, https://www.nexusmods.com/starfield/mods/17936
- Players with about 375 BA2-loading mods hit crashes and invisible assets. LarannKiar: "Not all archives count toward the limit, it
  depends on how they are loaded"; he added a BA2 counter (`bBA2Counter`) to Starfield Engine Fixes v11.1 (July 2025).
  **verified** forum posts, https://forums.nexusmods.com/topic/13518743-…
- **Supported hypothesis:** vanilla uses about 78 archives (our measurement covers 78 files on the owner's install; it may
  not include every Creation). That leaves roughly 178 slots shared by all of a player's mods. Splitting a total
  conversion into many plugin+archive pairs uses those slots up fast, so few large archives are better.
- Per-archive size: FO4 guidance is ≤ 4095 MB. Whether that holds for Starfield is **unresolved**. Archive2 has `-maxSizeMB`
  / `-count` for splitting.
- Load times with very large BA2 mods: no measured data found. **Unresolved.**
- Creations uploads are capped at 2 GB (1.15.216). That matters only if we ever publish on Creations, and our size makes
  Creations distribution impractical anyway. **verified** cap; the implication is a supported hypothesis.

---

## Questions this raises for our launcher

Each question gives why it matters (W) and what would answer it (A).

1. **Which game runtimes do we support, and do we pin?**
   W: patches have changed record definitions (1.14.70 base form type) and load-order rules (1.16.236). A silent Steam
   update could break a 10+ GB install. A: run our deploy + smoke test on 1.16.244 now and after every patch.
   Record `Starfield.exe` file version and SHA-256 in the launcher manifest, and decide whether to warn or block on
   unknown versions.
2. **Does our content load correctly with no SFSE, no INI edits and no Documents writes on a clean Steam install?**
   W: Controlled Folder Access blocks Documents on the owner's PC, and many players will be in the same position. A: deploy to a clean
   profile (fresh `%LOCALAPPDATA%\Starfield`, no StarfieldCustom.ini), check the plugins are active, and check that
   assets from BA2 render in game.
3. **What plugin type(s) do we ship: one full ESM, several medium ESMs, or a mix?** W: full masters use 1 of 253
   slots. Medium allows 65,535 new records each. A FO4 conversion likely exceeds 65k records, and the type can never change
   after release without breaking saves and patches. A: count records the converter generates per unit (from
   our record counters), then fix the split before the first public release. Write it down in docs/ai/decisions.md.
4. **How many BA2s will we ship, and how many slots will players have left?** W: 256-archive limit per
   registry, with about 78 vanilla archives on the owner's install. A: count vanilla GNRL vs DX10 archives on a fully updated
   install with common Creations, and plan for at most N GNRL + M DX10 archives in total (for example 1–3 of each per plugin).
5. **Is there a per-archive size cap for Starfield v2/v3 BA2s?** W: FO4 breaks above 4 GB, and our texture set may be
   tens of GB. A: build a test BA2 of 4.5 GB with Archive2 and with the `ba2` crate, load it in game, and read an asset
   stored past the 4 GiB offset.
6. **Who builds the BA2s: the owner's Archive2, a player's Archive2, or our own writer?** W: the CK EULA forbids
   redistributing the Editor and limits its use, and players need the CK (32 GB RAM spec) installed to run it locally. A: the owner
   decides on the EULA reading. Test-write v2 GNRL and v3 DX10 LZ4 with the 0BSD `ba2` crate and check byte-level
   and in-game parity against Archive2 output.
7. **Can we ship prebuilt BA2s at all, given FO4 asset rights?** W: converted Bethesda assets cannot sit in Git or on
   a public host. The launcher may have to convert on the player's PC from their own FO4 install. A: the owner's distribution decision.
   That then decides whether the player needs Archive2 or we need an OSS writer (Q6).
8. **How does the launcher keep our plugins in Plugins.txt when the game rewrites it?** W: the game removes missing
   plugins, adds new ones unchecked, strips implicit and blueprint plugins, and Creations or the offline menu can re-sort
   everything. A: scripted test of launching the game, closing it, and diffing Plugins.txt. Repeat with Creations
   installed, with Steam offline, and after "use load order from save". Decide whether the launcher re-asserts the order
   before each launch.
9. **Must our plugins avoid `BlueprintShips-Starfield.esm` as a master, and do we generate any blueprint records?**
   W: blueprint masters load last and can't be overridden by normal plugins, and the dependency causes order shifts. A: check our
   ESM headers' MAST lists in a unit test, and grep converted records for ship blueprint usage.
10. **Do we coexist with MO2 and Vortex users?** W: many players will already use one. MO2's public build is from 2024 and
    has known Starfield bugs, and Vortex can junction `My Games\Data`. A: decide whether the launcher detects
    MO2/Vortex and either refuses, exports an MO2/Vortex-installable package, or writes directly. Test one install
    under Vortex 1.10.5 and one under MO2 2.5.2.
11. **Game Pass / MS Store support: yes or no?** W: different install paths, possible WindowsApps lockout, and
    different exe versions (Address Library `.1` builds show that MS Store builds differ). A: get one Game Pass install, then
    confirm the Data path, Plugins.txt path and plugin loading without SFSE.
12. **What do we tell players about achievements?** W: external ESMs flag the save as modded, so achievements are off. A: confirm in game that
    loading our ESM sets the modded flag. Decide whether to document the enablers (SFSE/ASI DLLs that we would not ship).
13. **Which form version / HEDR version must our plugins use, and does it change between patches?** W: an outdated
    form version may make the engine read fields wrong. A: compare HEDR and form versions in `Starfield.esm` across
    1.16.236 and 1.16.244 (repo measurement scripts), and add a guard test pinned to the target runtime.
14. **Do v3 DX10 archives need LZ4 *block* compression exactly as vanilla uses it, and does Archive2 `-compression LZ4`
    produce that?** W: textures are the bulk of our size, and wrong compression means invisible textures. A: build one DX10 v3
    archive with Archive2 `-format DDS -compression LZ4`, then compare its header and chunk layout with
    `Starfield - LODTextures01.ba2` using our reader.
15. **Can sound (`.wem`) live in a compressed GNRL archive?** W: a forum report says relocated `.wem` in
    compressed archives does not play. A: pack one converted `.wem` in compressed vs uncompressed GNRL and play it in game.
16. **Which validation tool do we rely on: SF1Edit (Discord-only, possibly unmaintained), Mutagen (GPL-3.0), or our
    own parser?** W: the licence affects whether we can link it, and maintenance affects long-term trust. A: try loading a
    converted ESM in Mutagen's Starfield reader and in the latest SF1Edit, and record what each reports. A GPL tool used only as an
    external checker doesn't affect our licence.
17. **What is load-time cost for one big archive vs many small ones?** W: no community data exists. A: time from
    main menu to the first cell with our content, on the same machine, for 1×N GB vs k×(N/k) GB archives. Record it in
    docs/ai/optimization.md.
18. **Should the launcher refuse to run if `sTestFile1..10` is set in any INI?** W: any sTestFile makes the game
    ignore Plugins.txt entirely, so our plugins would silently not load. A: the launcher reads Starfield.ini,
    Starfield_<lang>.ini and StarfieldCustom.ini read-only and warns. Test by setting sTestFile1 on a test profile.
19. **Does a `Starfield.ccc` in My Games or the install folder interfere with our order?** W: `.ccc` plugins load
    first and get injected into Plugins.txt. A: check for the file on player installs, and document whether the launcher
    ever writes one. Probably never, since tools like LOOT stopped writing it.
