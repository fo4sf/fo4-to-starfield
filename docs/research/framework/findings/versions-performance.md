# Game versions, performance and long-term maintenance

Written 2026-10-19 by versions-performance (Claude, research agent). Offline web research plus read-only reads of the repo.

**Bottom line.** The project's pins (Fallout 4 **1.10.163**, Starfield **1.16.244** + SFSE 0.2.21, Steam only) are
sound for development, but a player on today's Steam will usually have **Fallout 4 1.11.240** (August 2026, the
Anniversary Edition line) and Starfield 1.16.244, which has been the latest build since 11 June 2026. Starfield is now
the calmer of the two: SFSE shipped on the same day as each of the three 2026 Starfield patches. Fallout 4 has moved
four times since the Anniversary Edition (1.11.169, .191, .221 and .240), and the launch-week F4SE lag was about 15
days. Because the converter only *reads* Fallout 4 data, the real question is whether the next-gen and Anniversary
updates changed the **data files** (Fallout4.esm, DLC .esm files, BA2 headers, about 150 new Creation Club files), not
the exe. No source I could read answers that, and the repo's BA2 reader accepts only header versions 1 to 3. The launcher
therefore needs a source-version detector and a per-version test fixture before players arrive, not a demand that
players downgrade. On the Starfield side, the hard ceilings that a full conversion will meet are engine limits rather
than hardware: 256 active BA2 archives, 253 full-master slots, a soft limit of about 100 to 120 plugins, the open
question of whether one archive can pass 4 GiB, and the cost of about 650k unprecombined references per 64 cells. The
project currently diagnoses crashes with WER and ProcDump. A version-independent SFSE crash logger (Trainwreck, or Starfield Engine
Fixes' logger) would make player crash reports usable.

## Findings

### Fallout 4 versions in the wild

| Runtime | When | Script extender | Source / label |
|---|---|---|---|
| 1.10.163 ("old-gen") | 2019 to April 2024 | F4SE 0.6.23 (13 Oct 2022) | **verified** [F4SE files](https://www.nexusmods.com/fallout4/mods/42147?tab=files) |
| 1.10.980 (next-gen) | April 2024 | F4SE 0.7.1 (3 May 2024); the F4SE page calls 1.10.980 "unstable" | **verified**, same page |
| 1.10.984 (next-gen hotfix) | 13 May 2024 | F4SE 0.7.2 (13 May 2024) | **verified**, same page and [Nexus news 15400](https://www.nexusmods.com/news/15400) |
| 1.11.137 (Anniversary "Creations Menu Update") | 10 Nov 2025 | none at launch; "F4SE team has not been given early access" | release date and no early access: **verified** [Nexus news 15400](https://www.nexusmods.com/news/15400); the version number comes from a community guide on the [Nexus forum](https://forums.nexusmods.com/topic/13525754-how-to-downgrade-fallout-4-game-of-the-year-edition-after-the-anniversary-update-rollback-from-111137-to-110984/) (**supported hypothesis**) |
| 1.11.169 | Nov 2025 | F4SE 0.7.6 (25 Nov 2025) | **verified** F4SE page, [downgrader thread](https://steamcommunity.com/app/377160/discussions/0/685239894022330731/) |
| 1.11.191 | Dec 2025 | F4SE 0.7.7 (16 Dec 2025) | **verified**, same |
| 1.11.221 | May 2026 | F4SE 0.7.8 (27 May 2026) | **verified**, same |
| 1.11.240 (current) | Aug 2026 | F4SE 0.7.9 (18 Aug 2026) | **verified**, same |

- The Anniversary Edition bundles "all six official DLCs" and "over 150 pieces of Creation Club content", some of it
  new (**verified**, [Nexus news 15400](https://www.nexusmods.com/news/15400)). A commenter there says Creation Club skins use up
  BA2 archive slots (**unresolved**, a user opinion).
- GOG: a commenter says GOG "never got the last update" (**unresolved**, a single comment on the same page). I found no
  primary source on which runtime GOG or the Microsoft Store/Game Pass Fallout 4 ships today.
- Pages I could read say nothing about whether Fallout4.esm, the DLC .esm files or the BA2 archives changed in
  1.10.98x or 1.11.x. The Steam rollback guide replaces **only Fallout4.exe** (depot 377162, manifest
  5698952341602575696, about 38 MB, the 13 May 2024 build, runtime 1.10.984)
  (**verified** [Nexus forum guide](https://forums.nexusmods.com/topic/13525754-how-to-downgrade-fallout-4-game-of-the-year-edition-after-the-anniversary-update-rollback-from-111137-to-110984/)).
  A second guide pulls **six** depots (377161, 377162, 377163, 393885, 435871, 435880, each with its own manifest), so
  some data depots changed too (**verified** that the guide lists them,
  [Steam guide 3604110005](https://steamcommunity.com/sharedfiles/filedetails/?id=3604110005). Steam Community has since
  removed that guide, and its manifest IDs don't agree with each other). *Inference:* the base and DLC data
  depots were re-issued, so Fallout4.esm and the BA2 files probably differ between 1.10.163, 1.10.984 and 1.11.x
  (**supported hypothesis**; the depot list proves new depot content, not which records changed).
- The **universal downgrader** (Steam thread) applies xdelta3 patches to the changed files. It asks for Fallout4.exe's
  location, detects language and the DLC it can downgrade, needs no Steam login, can block Steam updates, and goes from
  1.11.240 to 1.11.221, 1.11.191, 1.10.984 or 1.10.163 (**verified**,
  [Steam thread](https://steamcommunity.com/app/377160/discussions/0/685239894022330731/)). Because it ships xdelta
  patches for "the modified files" and detects DLC, the update must have changed more than the exe, but the thread does not list the files
  (**supported hypothesis**).
- **Repo fact (verified):** `src/fo4sf/ba2.py` line 59 accepts BA2 header versions `{1, 2, 3}` only and raises
  `unsupported version` otherwise. From memory, not from a source read today, next-gen Fallout 4 archives use header
  versions 7/8 (**unresolved**: the search budget ran out before I could confirm it). If that is true, the converter
  cannot read a player's unmodified 1.10.984 or 1.11.x install. A 1-minute PC probe answers it: the first 8 bytes of
  each `Fallout4 - *.ba2` on a current install.

### Starfield versions (2024 to 2026)

SFSE release per game runtime (**verified**, [SFSE files on Nexus](https://www.nexusmods.com/starfield/mods/106?tab=files)).
Game patch dates from [patched.gg](https://patched.gg/games/starfield) and [patchbot](https://patchbot.io/games/starfield/articles/507-update-116244-june-11-2026):

| Runtime | Game date | SFSE (date) | Lag | Notes |
|---|---|---|---|---|
| 1.12.30 / .32 / .36 | Jun–Jul 2024 | 0.2.8 (10 Jun), 0.2.9 (15 Jun), 0.2.10 (3 Jul) | **unresolved** | Creations era begins |
| 1.13.61 | Aug 2024 | 0.2.12 (23 Aug) | unresolved | |
| 1.14.70 | Sep/Oct 2024 (Shattered Space, 30 Sep 2024) | 0.2.13 (1 Oct) | about 1 day | "Bethesda updated the game code"; many plugins needed a recompile (**verified** [SFSE page](https://www.nexusmods.com/starfield/mods/106)) |
| 1.14.74 | Nov 2024 | 0.2.16 (19 Nov) | unresolved | |
| 1.15.214 | 6 May 2025, **Steam `beta` branch** | n/a | n/a | public beta through Steam Properties > Betas (**verified** [r/Starfield mirror](https://twt.omada.cafe/r/Starfield/comments/1kg7k32/starfield_update_115214_may_6_2025_beta)) |
| 1.15.216 | May 2025 | 0.2.17 (24 May) | unresolved | "compiler setting changes ... invalidate the Address Library"; most plugins broke (**verified** SFSE page) |
| 1.15.222 | 2025 (Starfield Engine Fixes calls it "2025 August update"; the USFP history requires it from 22 May 2025) | 0.2.18 (6 Aug 2025) | **unresolved**, the sources disagree | |
| 1.16.236 "Free Lanes" | 7 Apr 2026, with **Terran Armada** DLC and the PS5 launch | 0.2.19 (7 Apr) | **same day** | |
| 1.16.242 | 14 May 2026 | 0.2.20 (14 May) | **same day** | fixes for Creations and autosaves |
| 1.16.244 | 11 Jun 2026 | 0.2.21 (11 Jun) | **same day** | still the latest as of 12 Oct 2026 ([starfield.gg](https://starfield.gg/starfield-latest-update/), fansite) |

- SFSE "will support the latest version of Starfield available on Steam, and **only** this version" and "does not
  support the Windows Store/Game Pass release" (**verified** [sfse.silverlock.org](https://sfse.silverlock.org/)). The
  project's SETUP/PLAY-AND-TEST pages already say this. What follows extends them: SFSE drops the old runtime when it
  supports a new one, so after every patch the player either updates both or rolls back both.
- Game Pass / Xbox PC modding goes through the Ultimate ASI Loader (via `bink2w64.dll`) instead of SFSE. The data
  folder is `XboxGames\Starfield\Content\Data`, loose meshes and textures go in `Documents\My Games\Starfield\Data`, and
  Plugins.txt is in `%LOCALAPPDATA%\Starfield` (**verified**, a 2023/24 guide:
  [Nexus forum](https://forums.nexusmods.com/topic/13459379-a-guide-to-game-pass-modding-no-mod-manager)). *Inference:*
  plugin + BA2 content without SFSE could load on Game Pass, so a "no-SFSE" build could support that store
  (**supported hypothesis**).
- Bethesda announced new Starborn content for 2027 (**unresolved**, fansite [starfield.gg](https://starfield.gg/starfield-latest-update/)).
  Starfield is not finished changing.
- The Creation Kit gained 2 GB Creation uploads in 1.15.214 (**verified**, same r/Starfield mirror). That matters only if we ever used Creations.
- The Unofficial Starfield Patch had to redo planet data after Bethesda "changed its planet data storage" (USFP
  1.0.7a/b, 1.15.222). Patch 1.14.74 began disabling a blueprint-edit plugin
  (**verified** [USFP history](https://www.afkmods.com/Unofficial%20Starfield%20Patch%20Version%20History.html)). So
  Starfield patches do change record semantics, not only the exe. Our planet/worldspace overrides (FO4TerrainCore over
  Mars) are exactly the kind of data such a change breaks.

### Engine limits a large conversion meets

- **BA2 limit:** the engine indexes loaded archives with 8 bits, so 256 active archives at most; past that, assets go
  missing or the game crashes. The SFSE plugin "BA2 Limit Fix" (14 Aug 2026, runtimes 1.16.236 and .244) raises it
  (**verified** [Nexus 17936](https://www.nexusmods.com/starfield/mods/17936)). Starfield Engine Fixes has an optional
  BA2 counter, and "not all archives count toward the limit"
  (**verified** [Nexus forum](https://forums.nexusmods.com/topic/13518743-crash-issue-too-many-ba2-files-causing-ctds-%E2%80%93-looking-for-fix-or-insight/)).
- **Plugin slots:** 253 full-master slots; medium masters up to 65,535 forms and 256 files; small masters up to 4,095
  forms and 4,096 files. A soft instability appears around 100 to 120 plugins because overrides use extra index slots. The 254-plugin bug
  was fixed in 1.14.68 (**verified** as the article's claims,
  [Nexus article 688](https://www.nexusmods.com/starfield/articles/688), Oct 2024; the slot-per-override claim rests on "one study").
- **Archive size:** every large vanilla archive stops just under 4 GiB, and whether the engine reads past it is
  unresolved (**verified** as the project's own unresolved note, `docs/ai/decisions.md` 2026-10-12). A full-resolution
  64-cell core needs about 8.5 GiB.
- **Hardware floor (official):** Windows 10 22H2, Ryzen 5 2600X / i7-6800K, 16 GB RAM, GTX 1070 Ti / RX 5700, 125 GB
  on an **SSD (required)**; recommended RX 6800 XT / RTX 2080. No VRAM figure is published
  (**verified** [UESP-style wiki](https://starfieldwiki.net/wiki/Starfield:System_Requirements)). The owner's
  baseline PC is a 7950X3D, RTX 4070 Ti 12 GB and 32 GB RAM (**verified**, `docs/ai/optimization.md`), well above that floor. We have no data at the floor.
- **Build cost so far:** 15 cells / 4,014 models take 311 to 373 s for a full conversion (**verified**,
  `docs/ai/optimization.md`). The 64-cell core holds 649,596 convertible exterior references and 11,769 models
  (**verified**, decisions 2026-10-12). Whole-game numbers don't exist (the launcher note already says so).
- **Performance bottlenecks:** I found no primary source on Starfield draw-call budgets, how the engine handles
  hundreds of thousands of individual references, or whether it has a precombine/previs equivalent
  (**unresolved**). Starfield Engine Fixes ships "Engine Load Optimizations", "Reduce Traversal Stutter" (early beta)
  and an "Increase File Handle Limit" option (**verified** as feature names,
  [Nexus 10457](https://www.nexusmods.com/starfield/mods/10457?tab=files)). *Inference:* file handles, load stutter
  and traversal are the known pain points in vanilla (**supported hypothesis**). Fallout 4 relies on precombined meshes
  (the repo meets them as `SCOL\CM*.NIF`). We place converted references one by one, so draw calls per cell may grow sharply compared with FO4
  (**supported hypothesis**, to be measured).

### Crash diagnosis

- **Trainwreck** is a crash logger that loads through SFSE or as an `.asi`, is "compatible with all versions of the game
  past, present, and future", and writes to `Documents\My Games\Starfield\SFSE\Crashlogs` (**verified**
  [allmods mirror](https://allmods.net/starfield-mods/starfield-miscellaneous/trainwreck-a-crash-logger-v1-1/)). A Nexus
  article recommends it as universal across versions (**verified**
  [Nexus article 559](https://www.nexusmods.com/starfield/articles/559)). Author credited: Ryan McKenzie. I could not
  read the GitHub page or the license (**unresolved**).
- **Starfield Engine Fixes** (LarannKiar, v21.2, 4 Oct 2026, runtime 1.16.244) includes a "Detailed Crash Logger" and
  a Save Cleaner (experimental) (**verified** [Nexus 10457](https://www.nexusmods.com/starfield/mods/10457?tab=files)).
  It is version-pinned and updates after each patch.
- The project uses WER reports plus ProcDump full dumps (17.4 GB for one crash). The Havok `HK_ASSERT` int3 ends the
  process with no WER entry at all (**verified**, `docs/JOURNAL.md` 2026-10-16). One earlier launch ended "with no crash
  log" (journal line 259). This is the gap a crash logger fills for players.

## Precedents and what they teach us

- **Fallout 4 Anniversary (Nov 2025):** an unannounced runtime bump with no early access for F4SE broke every DLL mod
  for about 15 days. The community answer was a downgrader that patches files with xdelta and blocks Steam updates. **Lesson:** don't
  depend on Fallout 4's exe at all (we don't). If any version-specific code ever reads Fallout 4 (F4SE, Address
  Library), it will break four times a year.
- **Starfield 1.14.70 and 1.15.216:** Bethesda's compiler changes invalidated the Address Library and forced plugin
  recompiles. **Lesson:** any SFSE plugin we ship (the bridge, door/Pip-Boy helpers) needs a maintained build per
  runtime. Papyrus-only or data-only solutions survive patches better.
- **USFP 1.0.7a/b:** a patch changed how planet data is stored and POIs vanished. **Lesson:** our planet overrides
  (one Earth-like planet for the Commonwealth) sit on the most volatile data Bethesda touches; re-verify them after every patch.
- **Starfield modders on big lists** hit the 256-archive limit, then wrote a runtime SFSE fix (Aug 2026), and merge archives with Archive2.
  **Lesson:** a GAMMA-scale conversion should count archives and plugin slots as a budget from day one.
- **GAMMA / Wabbajack style (general knowledge, not read today, unresolved):** they pin one exact game version and
  refuse others. The Fallout 4 downgrader shows a player-run patcher is accepted practice. For Starfield the
  equivalent would be Steam's `download_depot` console or DepotDownloader (**unresolved**: I did not read a primary
  source for Starfield depot IDs).

## Risks

1. **The converter refuses a current Fallout 4 install** (BA2 header version, changed records): high likelihood if NG
   archives are v7/v8 (unconfirmed). Cheap to detect, moderate to fix.
2. **Fallout 4 data drift between runtimes changes FormIDs or record contents.** We then build different games on
   different PCs, which breaks the launcher's determinism gate (launcher note L4) across players, not only across
   machines. Likelihood: medium. Next-gen added content, and 150+ Creation Club files now ship with the Anniversary Edition.
3. **A Starfield patch breaks SFSE-dependent pieces.** SFSE itself has kept pace in 2026 (same day), but third-party SFSE plugins
   we might depend on (BA2 Limit Fix, Engine Fixes) lag. Likelihood: high per patch, low impact if the core is data-only.
4. **A Starfield patch changes planet/worldspace data semantics** (as in the USFP case). Medium likelihood, high impact
   on World and planet.
5. **The engine ceilings (256 BA2s, 253 full slots, ~4 GiB archive, references per cell) are reached before content
   breadth is done.** High likelihood for the full Commonwealth + Far Harbor + Nuka-World. Mitigation: plan the
   packing now (few plugins, ESM + medium masters, a few large archives).
6. **Player hardware:** the owner's PC is far above the minimum, so nothing tells us how a 16 GB / 8 GB VRAM machine
   fares. Uncapped FO4 textures plus Starfield's own memory use may overrun on GTX 1070 Ti-class GPUs. Medium.
7. **Disk:** Starfield 125 GB + Fallout 4 (about 30+ GB with DLC, **unresolved**) + the build work folder + output
   (8.5 GiB for 64 cells at full resolution) + temporary archives. The owner's D: is already nearly full (launcher note).
   High likelihood that players with one SSD run short.
8. **Game Pass players are excluded** wherever SFSE is required. Certain while any SFSE dependency exists.

## Questions for the framework

### New game
1. **Does the Vault 111 start survive a Starfield patch without changes?** Why: the start overrides Starfield start
   quests, and patches change quest data (USFP precedent). Options: a pure-data override; an SFSE hook; Papyrus.
   Evidence: diff Starfield.esm quest records across 1.16.236/242/244, offline, with the repo's record tools.
   Who: offline research.
2. **Which Fallout 4 runtime's Fallout4.esm is canonical for the new-game content** (Vault 111 cells, the intro quest
   MQ101)? Why: if 1.10.163 and 1.11.240 differ in those records, the start differs by player. Evidence: a record-level
   diff of the two .esm files' Vault 111 cells and quests. Who: a PC probe (owner keeps a 1.10.163 copy; one current install is needed).

### Door animations
3. **Do door hooks rely on SFSE or on runtime addresses?** Why: an exe-dependent door system breaks on every patch
   (Address Library invalidation in 1.15.216). Options: Papyrus plus vanilla animation graphs (patch-safe); an SFSE plugin per
   runtime. Evidence: list what the door work package calls. Who: offline research in the repo.

### All interiors
4. **How many interiors fit in one plugin and one archive before engine limits bite?** Why: 4 GiB per archive
   (unresolved) and form counts per master type (65,535 for medium). Options: one full ESM; several medium masters; a
   BA2 split by kind (Main/Textures). Evidence: a synthetic archive of more than 4 GiB loaded in game (an S9-style spike). Who: PC probe.
5. **What is the per-cell reference and draw-call budget that keeps interiors at 60 fps on a minimum-spec GPU?**
   Why: FO4 interiors depend on precombines; we place references one by one. Options: rebuild combined meshes ourselves
   (merge static geometry per cell at build time); accept the cost; reduce clutter. Evidence: frame time and
   reference count in the densest FO4 interiors (Vault 111, Diamond City Market's interior, Mass Fusion), with the
   game's own performance overlay or PresentMon. Who: PC probe.
6. **Does Starfield have a precombine/previs equivalent that our build could produce?** Why: it decides between
   writing our own merged meshes or finding an engine feature. Evidence: search Starfield.esm for SCOL/precombined
   data and the CK docs. Who: offline research (unresolved today).

### Launcher
7. **Which Fallout 4 runtimes does the launcher accept as a source: 1.10.163 only, 1.10.984, 1.11.x, or all?**
   Why: most players will be on 1.11.240. Options: (a) require a downgrade with the community downgrader; (b) support
   every runtime through per-version fixtures; (c) normalise inputs (detect the version, map FormIDs and record
   differences to a canonical set). Evidence: a record and archive diff between 1.10.163, 1.10.984 and 1.11.240 data.
   Who: owner decision after a PC probe.
8. **How does the launcher identify the Fallout 4 runtime from data alone?** Why: the converter never runs FO4, so it
   should not rely on the exe. Options: hash Fallout4.esm and each DLC .esm against a known table; read BA2 header
   versions; check that the Anniversary Creation Club files exist. Evidence: hashes from three installs. Who: PC probe plus community contacts.
9. **Does the BA2 reader need v7/v8 support?** Why: `ba2.py` rejects anything but 1 to 3. Evidence: header bytes of a
   1.10.984/1.11.x archive; xEdit/BSArch source code for the layout. Who: PC probe (minutes) plus offline research.
10. **Are the ~150 Anniversary Creation Club files inputs, ignored, or forbidden?** Why: they change what "the
    player's FO4" means. Some are new content a player may expect, but converting them widens the asset surface and
    the legal surface. Options: ignore every `cc*.esl`; opt-in per file. Who: owner decision.
11. **Do GOG and Microsoft Store Fallout 4 installs work as sources?** Why: the converter only needs data, so the store
    could be irrelevant, but file layout, BA2 versions and the runtime may differ. Evidence: a file listing and hashes from a GOG and a Game Pass install. Who: community contact.
12. **What does the launcher do when Steam updates Starfield?** Options: refuse to launch until SFSE and the project
    publish support (the current preflight `game_version` gate already FAILs on a mismatch); guide a rollback with
    Steam's `download_depot` or DepotDownloader; keep a backup exe. Why: SFSE supports only the latest Steam runtime,
    so a rollback must roll back both. Evidence: a measured patch-day timeline (SFSE was same-day in 2026). Who: owner decision.
13. **Should the launcher stop Steam from auto-updating Starfield** (the "update only when I launch" setting, or the
    downgrader-style block)? Why: an update in the middle of a session breaks a built set. Trade-off: players miss fixes, and
    Steam's settings belong to the player. Who: owner decision plus offline research on what Steam allows.
14. **Is a build keyed to the Starfield runtime?** Why: the build graph caches by input hash + converter version (launcher
    note). If Starfield.esm changes, overrides of its records may need a rebuild. Options: include the Starfield.esm
    hash in the cache key, or only the records we override. Who: offline design.
15. **What disk space must the launcher check for before building?** Why: 125 GB Starfield + FO4 + work folder +
    output + temporary archive, on an SSD. Evidence: measure the whole-core build's peak disk use (work folder + archive
    + checkpoint), then scale by cell count (the launcher note's open question, now with the temporary-archive term). Who: PC probe.
16. **Can the build run on a minimum-spec PC (16 GB RAM, 6 cores) within acceptable time?** Why: the owner's 7950X3D
    hides costs. Evidence: run the 15-cell build with a process memory cap and a limited core count; record peak RSS and time.
    Who: PC probe (or a cloud VM with matching cores).

### World and planet
17. **How many BA2 archives and plugin slots will the full world use, and does it need the BA2 Limit Fix?** Why: 256
    archives and 253 full slots are shared with the player's other mods and Creations. Options: keep the core to
    one ESM + 1 to 3 archives; medium masters for DLC areas. Evidence: archive counts with Starfield Engine Fixes' counter on the
    owner's PC. Who: PC probe.
18. **Does an exterior with 650k+ references stream without traversal stutter?** Why: SFEF's "Reduce Traversal Stutter"
    exists because vanilla stutters. Evidence: frame-time capture on a walking route over core64. Who: PC probe
    (the route runner already exists).
19. **After each Starfield patch, do the planet/worldspace overrides still hold?** Why: the USFP case shows planet data
    storage changed in 1.15.222. Evidence: a scripted record diff of overridden records against each new Starfield.esm.
    Who: offline tooling.
20. **What texture caps should the default build use per VRAM tier?** Why: the 2026-10-12 caps (1024 colour / 512 normal)
    were chosen for the archive size, not for VRAM. Options: three presets keyed to detected VRAM. Evidence: VRAM use at
    each cap on a 8 GB card. Who: PC probe on lower-end hardware (community).

### People and story
21. **Will NPC/quest scripts depend on SFSE functions?** Why: each SFSE dependency excludes Game Pass and adds
    patch-day risk. Options: Papyrus with vanilla functions only; SFSE as an optional layer. Who: offline design.
22. **Do saves survive a Starfield patch with our plugins loaded?** Why: long playthroughs span patches. Evidence: save
    on 1.16.242, load on 1.16.244 (both builds are on Steam depots). Who: PC probe.

### Fallout systems
23. **Which Fallout systems (Pip-Boy UI, VATS, workshop) need native code, and who maintains it per runtime?** Why:
    UI and time-scaling hooks are the kind of thing BetterConsole-style mods break on. Options: Scaleform/Papyrus-only
    designs; an SFSE plugin with CommonLibSF and the Address Library. Who: offline research plus an owner decision.

### Release and community
24. **Which crash logger do we tell players to install, and do we ask for its log in bug reports?** Options:
    Trainwreck (version-independent; SFSE or ASI), Starfield Engine Fixes' crash logger (pinned per runtime, more
    features). Evidence: trigger the known Havok assert crash (the vault cart case) with each logger and see whether it is
    caught; the int3 currently leaves no WER entry. Who: PC probe.
25. **What is the support matrix printed on the release page?** Why: players need one line (e.g. "Steam Starfield
    1.16.244 + SFSE 0.2.21; Fallout 4 data from 1.10.163 or 1.11.240"). Who: owner decision after Q7.
26. **How fast do we promise to follow a Starfield patch?** Why: SFSE was same-day in 2026; our own fixes are the
    bottleneck. Options: "within a week, use the previous build until then"; an automated patch-day regression run.
    Who: owner decision.
27. **Do we support Game Pass Starfield at all?** Options: no (current); a no-SFSE build loaded through plugins.txt and
    archives (possible if the core stays data-only). Evidence: load the S9 test plugin on a Game Pass install. Who: community contact.

### Tooling and testing
28. **Can we keep a "previous Starfield runtime" test machine/profile?** Why: to reproduce reports from players who
    have not updated, or who rolled back. Options: Steam beta branches (Bethesda uses `beta` for previews; older public
    builds are not offered as branches, **unresolved**); depot download; a copy of the exe. Who: offline research plus PC probe.
29. **Should the patch-day regression run be automated?** Why: the test runner and preflight exist. On a new
    `Starfield.exe` version, run the S1/S2/S9 smoke routes and a record diff, then post to #32. Evidence: time one
    full smoke chain. Who: offline design.
30. **Should Bethesda's Steam `beta` branch be watched for upcoming runtimes?** Why: 1.15.214 was public on the beta
    branch before release, which gives warning ahead of a patch. Who: offline research (who monitors, how).
31. **Should Fallout 4 runtime fixtures enter the test suite?** Why: unit tests use synthetic fixtures. A per-runtime
    header/record fixture (BA2 v1 vs v7/8, a changed record) keeps the converter honest without shipping game data.
    Who: offline tooling after the PC probe in Q9.

### Cross-cutting
32. **Data-only core as the long-term maintenance strategy?** Why: everything exe-bound (F4SE, SFSE, Address Library)
    breaks on patches. Everything data-bound breaks less often (records, archives) and can be caught by a diff. The
    decision sets the maintenance cost for years. Who: owner decision (record in decisions.md).
33. **Who owns patch-day duty when the project is quiet?** Why: Starfield has 2027 content announced and Fallout 4 is
    still being patched in 2026. Who: owner decision (the watchdog/Codex runbook could carry the detection step).

## Corrections

- No project statement I read is contradicted. Two extensions: (1) `docs/SETUP.md` and `docs/PLAN.md` pin Fallout 4
  1.10.163 for good reasons, but the repo's BA2 reader (`src/fo4sf/ba2.py`, versions 1 to 3 only) means the
  converter may reject the runtime most players have today. This is unverified until the header probe runs.
  (2) The launcher note's "check its version" (detect stage) should check the **data** version (esm hashes, BA2
  headers, Creation Club files), not Fallout4.exe.

## Limits of this report

The web-search budget for this turn ran out. Several pages were rate-limited (HTTP 429) and could not be read: a Steam
discussion on downgrading the Anniversary update (steamcommunity.com/app/377160/discussions/0/802331493180395957), a
Sportskeeda downgrade guide, and an mp1st page with the 1.16.242 notes. The Trainwreck GitHub page also failed to
fetch. Not researched for that reason: BA2 v7/v8 confirmation, Starfield depot IDs, Fallout 4 GOG/Game Pass runtimes,
and Starfield draw-call/VRAM profiles.

## Sources

- https://www.nexusmods.com/fallout4/mods/42147?tab=files
- https://www.nexusmods.com/news/15400
- https://forums.nexusmods.com/topic/13525754-how-to-downgrade-fallout-4-game-of-the-year-edition-after-the-anniversary-update-rollback-from-111137-to-110984/
- https://steamcommunity.com/sharedfiles/filedetails/?id=3604110005
- https://steamcommunity.com/app/377160/discussions/0/685239894022330731/
- https://www.nexusmods.com/starfield/mods/106?tab=files
- https://www.nexusmods.com/starfield/mods/106
- https://sfse.silverlock.org/
- https://patched.gg/games/starfield
- https://patchbot.io/games/starfield/articles/507-update-116244-june-11-2026
- https://starfield.gg/starfield-latest-update/
- https://starfield.gg/starfield-update-1-16-236-patch-notes-free-lanes/
- https://twt.omada.cafe/r/Starfield/comments/1kg7k32/starfield_update_115214_may_6_2025_beta
- https://www.afkmods.com/Unofficial%20Starfield%20Patch%20Version%20History.html
- https://www.nexusmods.com/starfield/mods/10457?tab=files
- https://www.nexusmods.com/starfield/mods/17936
- https://forums.nexusmods.com/topic/13518743-crash-issue-too-many-ba2-files-causing-ctds-%E2%80%93-looking-for-fix-or-insight/
- https://www.nexusmods.com/starfield/articles/688
- https://www.nexusmods.com/starfield/articles/559
- https://allmods.net/starfield-mods/starfield-miscellaneous/trainwreck-a-crash-logger-v1-1/
- https://forums.nexusmods.com/topic/13459379-a-guide-to-game-pass-modding-no-mod-manager
- https://starfieldwiki.net/wiki/Starfield:System_Requirements
- Repo (read-only): docs/RISKS.md, docs/SETUP.md, docs/PLAN.md, docs/PLAY-AND-TEST.md, docs/ai/optimization.md,
  docs/ai/decisions.md (2026-10-12), docs/JOURNAL.md (2026-10-16), src/fo4sf/ba2.py, src/fo4sf/core/preflight.py;
  /mnt/project-files/research/next-phase/launcher-architecture.md

## Wave 2 additions (2026-10-19)

Wave 2 fills gaps this report left **unresolved**. Same labels. xEdit line numbers refer to `Core/*.pas` at
`dev-4.1.6` on raw.githubusercontent.com; OpenMW lines to `components/bsa/*` on gitlab.com master (both read today).

### W2-1. Fallout 4 next-gen / Anniversary BA2 header versions (answers "versions 7/8 unresolved" and Q9)
- **verified**: the April 2024 next-gen update "introduced archive versions 7 and 8"; NG archives show
  `07 00 00 00` or `08 00 00 00` in the version bytes; NG Archive2 "may save archives as Version 7 or 8", which "are
  incompatible with many pre-2024 versions of the game or external tools"; the old-gen exe "can only load archives up to
  Archive2 v1.1.0.4"; the fix for old-gen users is a version patcher or a hex edit of the version byte to `01`
  ([Nexus article 5844 "BA2 and Archive2", Qrsr, May 2025, edited Sep 2026](https://www.nexusmods.com/fallout4/articles/5844)).
- **verified**: xEdit defines `HEADER_VERSION_FO4v7 = $07; // FO4 NG/AE` and `HEADER_VERSION_FO4v8 = $08; // FO4 NG/AE`
  and maps 1, 7 and 8 to the same archive type `baFO4` with the same 24-byte header; only Starfield v2 (+8 bytes) and v3
  (+8 bytes and a compression field) differ (wbBSArchive.pas 545-553, 1336-1346, 1441-1443). xEdit **writes** FO4
  archives as v1 (1600-1608).
- **verified**: OpenMW reads `Fallout4NextGen_v7 = 7` and `Fallout4NextGen_v8 = 8` in the same `case` as v1 in both the
  GNRL and DX10 readers, with no extra header read (`ba2gnrlfile.cpp` 92-104, `ba2dx10file.cpp` 95-109); its merge request
  calls them "apparently unchanged" ([OpenMW MR 4055](https://gitlab.com/OpenMW/openmw/-/merge_requests/4055),
  [rename commit](https://git.cijber.net/mirror/openmw/commit/a5d936993fb017f1c6bc17aecdc95e760c270edd)).
- **supported hypothesis** (three independent readers + the hex-edit-to-01 workaround agree): **v7/v8 changed only
  the version number**, not the header, file table or compression. The fix for `src/fo4sf/ba2.py` line 59 is to accept
  `{1, 7, 8}` with the v1 layout. Not shown: which vanilla archives are 7 and which are 8, and whether the Anniversary
  update (1.11.x) changed anything beyond NG (xEdit's comment labels both "NG/AE"). A PC probe that reads the first
  8 bytes of every `Fallout4 - *.ba2` and `cc*.ba2` settles it; a synthetic v7/v8 fixture test covers the code.
- **Corrections**: wave 1 said "from memory" v7/v8; that is now **verified**. The worst case the wave-1 text feared
  ("cannot read a player's unmodified 1.10.984 or 1.11.x install") is real for the current reader but is a one-line fix,
  not a format project.

### W2-2. Draw calls, VRAM and dense content (extends "Performance bottlenecks: unresolved", Q5, Q18, Q20)
- **verified**: Starfield's D3D12 renderer generates indirect draw arguments with a compute shader and issues
  **ExecuteIndirect** calls, several back to back, often with a draw count of 0; vkd3d-proton added a Starfield workaround
  ([vkd3d-proton PR 1694](https://github.com/HansKristian-Work/vkd3d-proton/pull/1694)). The author later said the gains
  are "very minute", "single percent range" (same PR). Press summary:
  [Destructoid](https://www.destructoid.com/open-source-community-figures-out-problems-with-performance-in-starfield/).
- **supported hypothesis**: rendering is largely **GPU-driven** (culling/argument generation on the GPU), so per-object
  CPU draw-call cost, the reason FO4 needed precombines, matters less. CE2 has no precombine/previs records at all
  (starfield-toolchain.md W2-2). [Correction 2026-10-19: but the Starfield CK has the GUI actions "Generate
  Precombined Visibility for Current Cell" and "... All Loaded Cells" (interiors.md T9, job 18; no such switch, job 20),
  so a precombined-visibility bake may exist; what it writes and whether it matters for performance is **unresolved**;
  `-GenerateCellAndRefCounts` (possibly per-cell reference counts) is **unresolved**.] The remaining cost of 650k refs is likely on the CPU side in **reference loading,
  scripts/havok and streaming**, not draw submission. Unproven: no source measures a dense modded cell.
- **verified**: Starfield "can take advantage of up to eight CPU cores"; the heaviest test scene was New Atlantis with
  "a lot of NPCs" ([DSOGaming, Sep 2023](https://www.dsogaming.com/pc-performance-analyses/starfield-pc-performance-analysis/)).
  No draw-call figures there.
- **verified (single test, vanilla)**: VRAM on an RTX 3080 12 GB: under 3 GB at 1080p low, 3.8 GB at 1080p ultra,
  4.4 GB at 1440p low, 5.7 GB at 1440p max, about 6.5 GB at 4K ultra with FSR2 Ultra Performance (indoors only)
  ([Noticias3D, 1 Sep 2023, NJ Tech tests](https://www.noticias3d.com/noticia/92797/starfield-requisitos-4k-cuanta-memoria-grafica-consume.html)).
  Vanilla leaves headroom on the owner's 12 GB card; our converted textures add to that. **unresolved**: VRAM with
  our core loaded. Corsair recommends 32 GB system RAM over 16 GB without published numbers in text
  ([Corsair](https://www.corsair.com/us/de/explorer/diy-builder/memory/how-memory-capacity-affects-starfield/)).
- **Experiment** (for Q5/Q18/Q20): on the PC, stand at 3 fixed spots in the core (dense downtown, open wasteland,
  interior) and log fps, frame time, VRAM and RAM (PresentMon + GPU counters), vanilla vs core vs core-with-LOD; repeat with
  the texture caps halved. Numbers to docs/ai/optimization.md.

### W2-3. Medium masters and archives over 4 GiB (answers the unresolved part of Q4)
- **verified**: medium ObjectIDs 0x0000-0xFFFF, 256 medium slots (xEdit, details in starfield-toolchain.md W2-5).
- **verified (format)**: BA2 offsets are 64-bit (wbBSArchive.pas 54, 75), so nothing in the file format stops at 4 GiB.
  FO4 users report 9.5 GB and 14.7 GB BA2s loading
  ([forum 11091353](https://forums.nexusmods.com/topic/11091353-ba2-size-limits-and-splitting-textures-between-ba2s), user
  reports). **unresolved for Starfield**: vanilla archives still stop just under 4 GiB, which may be Bethesda's packing
  habit or an engine limit. Until a PC probe loads a >4 GiB archive, keep splitting at 4,095 MB (no cost but archive
  slots; see Q17).

### Sources (wave 2)
- https://www.nexusmods.com/fallout4/articles/5844
- https://raw.githubusercontent.com/TES5Edit/TES5Edit/dev-4.1.6/Core/wbBSArchive.pas
- https://gitlab.com/OpenMW/openmw/-/raw/master/components/bsa/ba2gnrlfile.cpp , ba2dx10file.cpp , ba2file.hpp
- https://gitlab.com/OpenMW/openmw/-/merge_requests/4055 ; https://git.cijber.net/mirror/openmw/commit/a5d936993fb017f1c6bc17aecdc95e760c270edd
- https://forums.nexusmods.com/topic/13484961-solved-nifskope-and-next-gen-ba2-archives (NifSkope needed fo76utils fork for the NG BA2 version)
- https://github.com/HansKristian-Work/vkd3d-proton/pull/1694 ; https://www.destructoid.com/open-source-community-figures-out-problems-with-performance-in-starfield/
- https://www.dsogaming.com/pc-performance-analyses/starfield-pc-performance-analysis/
- https://www.noticias3d.com/noticia/92797/starfield-requisitos-4k-cuanta-memoria-grafica-consume.html
- https://www.corsair.com/us/de/explorer/diy-builder/memory/how-memory-capacity-affects-starfield/
- https://forums.nexusmods.com/topic/11091353-ba2-size-limits-and-splitting-textures-between-ba2s
