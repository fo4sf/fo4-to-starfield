# Game versions, engine budgets and long-term maintenance

Part of the [next-phase framework](README.md). Wave 1, 2026-10-19. Sources: findings/versions-performance.md, plus the
version and store parts of findings/starfield-toolchain.md, findings/distribution-community.md and findings/precedents.md.

Short names used below: **VP** = findings/versions-performance.md, **TC** = findings/starfield-toolchain.md,
**DC** = findings/distribution-community.md, **PR** = findings/precedents.md. "(also: TC Q9)" means the same question
appears there as question 9.

## In short

- We pin Fallout 4 **1.10.163** and Starfield **1.16.244** + SFSE 0.2.21, Steam only. A player on today's Steam has
  Fallout 4 **1.11.240** (Aug 2026), so our source pin does not match what most players own (VP, **verified**).
- Starfield has been calm since 11 June 2026 and SFSE shipped the same day as each 2026 patch. Fallout 4 moved four
  times since the Anniversary Edition (Nov 2025), with about 15 days of F4SE lag at launch (VP, **verified**).
- Most uncertain: whether next-gen and Anniversary updates changed Fallout 4 **data** (Fallout4.esm, DLC .esm, BA2
  headers). Our BA2 reader accepts header versions 1 to 3 only; next-gen v7/v8 is **unresolved**. If true, the converter
  cannot read a current install at all.
- Also uncertain: real engine ceilings for a full conversion (one archive past 4 GiB, medium master limit, draw calls
  without precombines) and how the build and the game run below the owner's high-end PC.
- Three decisions unlock the most: (1) which Fallout 4 data versions the launcher accepts (VM-01); (2) a data-only core
  with SFSE as an optional layer (VM-17); (3) the Starfield patch-day policy: pin, refuse, and how fast we follow
  (VM-12, VM-36).

## What is settled

| Fact or decision | Label | Source |
|---|---|---|
| Project pins: Fallout 4 1.10.163; Starfield 1.16.244 + SFSE 0.2.21; Steam only | **verified** (repo) | VP; repo docs/SETUP.md, docs/PLAY-AND-TEST.md, docs/PLAN.md |
| SFSE and the free Starfield Creation Kit MAY be required | owner decision | findings/BRIEF.md |
| The launcher never asks for store credentials (rules out a login-based downgrader) | owner decision | TC section 8; repo docs/ROADMAP.md C1 |
| Starfield 1.16.244 (11 Jun 2026) is still the newest build on 19 Oct 2026 | **verified** (to the level a fansite allows) | TC; [starfield.gg](https://starfield.gg/starfield-latest-update/) |
| SFSE supports only the latest Steam release; not Windows Store, Game Pass or EGS | **verified** | [sfse.silverlock.org](https://sfse.silverlock.org/); [SFSE Nexus 106](https://www.nexusmods.com/starfield/mods/106) |
| SFSE 0.2.21 shipped 11 Jun 2026, same day as 1.16.244; Address Library followed 13 Jun | **verified** | [SFSE Nexus 106](https://www.nexusmods.com/starfield/mods/106); [Address Library Nexus 3256](https://www.nexusmods.com/starfield/mods/3256) |
| The converter only reads Fallout 4 data; it never runs Fallout4.exe | **verified** (design) | VP bottom line and Corrections |
| `src/fo4sf/ba2.py` line 59 accepts BA2 header versions 1, 2, 3 only | **verified** (repo) | VP |
| The preflight `game_version` gate already FAILs on a Starfield version mismatch | **verified** (repo, src/fo4sf/core/preflight.py) | VP Q12 |
| Plugin slots: 253 full masters; 256 medium masters (about 65,535 records each); 4,096 small masters (4,095 records each) | **verified** | [Nexus news 14993](https://www.nexusmods.com/news/14993); [Nexus article 688](https://www.nexusmods.com/starfield/articles/688) |
| The medium master tier exists (corrects a "supported hypothesis" label in engine-mechanics/records-and-plugins.md) | **verified** | TC Corrections; [LOOT changelog](https://loot.readthedocs.io/en/0.24.1/app/changelog.html) |
| Two more plugin kinds: update plugins (formerly "overlay", take a load-order slot since 1.12.30) and blueprint masters | **verified** | TC section 7; LOOT changelog; [MO2 BPM, Nexus 17318](https://www.nexusmods.com/starfield/mods/17318) |
| 256 active BA2 archives at most (8-bit index); "BA2 Limit Fix" SFSE plugin raises it (14 Aug 2026) | **verified** | [Nexus 17936](https://www.nexusmods.com/starfield/mods/17936) |
| Every large vanilla archive stops just under 4 GiB; archives are split at 4,095 MB | **verified** (repo decisions 2026-10-12; [ejams1 guide](https://github.com/ejams1/starfield-modding-guide)) | VP, TC section 6 |
| Official minimum: Win 10 22H2, Ryzen 5 2600X / i7-6800K, 16 GB RAM, GTX 1070 Ti / RX 5700, 125 GB on SSD (required) | **verified** | [starfieldwiki](https://starfieldwiki.net/wiki/Starfield:System_Requirements) |
| Owner's PC: 7950X3D, RTX 4070 Ti 12 GB, 32 GB RAM; 15 cells / 4,014 models build in 311 to 373 s | **verified** (repo docs/ai/optimization.md) | VP |
| core64: 649,596 convertible exterior references, 11,769 models; about 8.5 GiB at full texture resolution | **verified** (repo decisions 2026-10-12) | VP |
| SFSE serialization (co-save) is disabled since 0.2.12 and not re-enabled | **verified** | [sfse_whatsnew](https://raw.githubusercontent.com/ianpatt/sfse/master/sfse_whatsnew.txt) |
| The Havok `HK_ASSERT` int3 ends the process with no WER entry | **verified** (repo docs/JOURNAL.md 2026-10-16) | VP |
| History of Starfield patches that broke SFSE (DC listed it as unresolved) is now answered: 1.14.70 (root form class), 1.15.216 (compiler settings, Address Library v2) | **verified** | sfse_whatsnew; TC section 1 |

## Possibilities

### Fallout 4 as an input

| Option | What it gives | Cost or risk | Precedent | Label |
|---|---|---|---|---|
| Accept 1.10.163 data only; player downgrades with the community downgrader | One canonical input; simplest tests | Most players must patch their game; Steam re-updates undo it | Fallout London (Team FOLON downgrader, needed a Steam login, read-only appmanifest) ([PC Gamer](https://www.pcgamer.com/games/fallout/after-years-fallout-4s-much-anticipated-dlc-sized-mod-fallout-london-is-out-heres-how-to-install-it/)); universal downgrader with xdelta3, no login ([Steam thread](https://steamcommunity.com/app/377160/discussions/0/685239894022330731/)) | **verified** precedents |
| Support every runtime through per-version fixtures | Players keep their game | A matrix to test and maintain; four FO4 updates since Nov 2025 | none found | **supported hypothesis** |
| Normalise inputs: detect the data version, map records to one canonical set | One output for every player; keeps the determinism gate (launcher note L4) | Needs a record-level diff per version first | TTW checks BSAs before patching ([TTW forum t=1031](https://taleoftwowastelands.com/viewtopic.php@t=1031)) | **supported hypothesis** |
| Detect version by data: hash Fallout4.esm and DLC .esm, read BA2 header bytes, check for Anniversary CC files | Never depends on the exe | Needs hashes from real installs (and per language) | Fallout London: right Fallout4.esm is 322,994 KB, wrong is 67,326 KB ([GameStar](https://www.gamestar.de/artikel/fallout-london-absturz-crash-technische-probleme,3417255,seite2.html)) | **verified** precedent; method **supported hypothesis** |
| Treat Anniversary CC files and the High-Res Texture Pack as ignored | Smaller asset and legal surface | Players may expect that content | Fallout London: CC files and the HD pack broke installs; skip the HD pack (GameStar, PC Gamer) | **verified** precedent |

### Fallout 4 stores

| Store | What we know | Label |
|---|---|---|
| Steam | Current 1.11.240; rollback guides list one exe depot (377162) or six depots | **verified** ([Nexus forum guide](https://forums.nexusmods.com/topic/13525754-how-to-downgrade-fallout-4-game-of-the-year-edition-after-the-anniversary-update-rollback-from-111137-to-110984/), [Steam guide 3604110005](https://steamcommunity.com/sharedfiles/filedetails/?id=3604110005), since removed) |
| GOG | One commenter says GOG "never got the last update" | **unresolved** ([Nexus news 15400](https://www.nexusmods.com/news/15400)) |
| Epic | Cannot roll back updates, so Fallout London could not support it | **verified** ([PCGamesN](https://www.pcgamesn.com/fallout-london/epic-games-store)) |
| Microsoft Store / Game Pass | Skyblivion rejects Epic and Game Pass copies as "encrypted and/or different"; TTW does not support the Microsoft Store | **verified** for those projects ([Skyblivion FAQ](https://skyblivion.com/faq), [TTW intro](https://thebestoftimes.moddinglinked.com/intro.html)); for Fallout 4 data **unresolved** |

### Starfield patch day

| Option | What it gives | Cost or risk | Precedent | Label |
|---|---|---|---|---|
| Refuse to launch until SFSE and our project publish support (current preflight gate) | No broken sessions | Players wait; SFSE was same-day in 2026 but our own fixes are the bottleneck | Wabbajack "Platform-locked" Starfield lists ([Wabbajack wiki](https://wiki.wabbajack.org/user_documentation/Supported%20Games%20and%20Mod%20Managers.html)) | **verified** |
| Warn and run a data-only tier | Core keeps working through a compiler-setting patch | Only if no phase needs SFSE | 1.15.216 broke "most if not all" SFSE plugins (sfse_whatsnew) | **verified** risk; option **supported hypothesis** |
| MO2-style "Stock Game" copy | Keeps the version "even if an update is released" | Doubles disk use (about 100+ GB, **supported hypothesis**) | [ejams1 guide](https://github.com/ejams1/starfield-modding-guide) | **verified** |
| Read-only `appmanifest` or "update only when launched" | Stops Steam updates | Steam settings belong to the player; verifying files undoes patches | Fallout London; TTW FAQ (verify reverts patches) | **verified** |
| Steam depot download (`download_depot`, DepotDownloader) | Real rollback | Needs the player's login: ruled out (ROADMAP C1); depot IDs not read | none read | **unresolved** |
| Watch the Steam `beta` branch and Bethesda's #steam-beta-feedback | Weeks of warning (1.15.214 was public beta on 6 May 2025) | Someone must watch | [r/Starfield mirror](https://twt.omada.cafe/r/Starfield/comments/1kg7k32/starfield_update_115214_may_6_2025_beta); [Nexus forum](https://forums.nexusmods.com/topic/13203033-helpful-links-references-and-news/page/36) | **verified** |

### Starfield stores

| Option | What it gives | Cost or risk | Label |
|---|---|---|---|
| Steam only (current) | Matches SFSE, MO2 | Game Pass players excluded | **verified** basis (SFSE, [MO2 releases](https://github.com/Modorganizer2/modorganizer/releases)) |
| Game Pass without SFSE: plugins + BA2 via Ultimate ASI Loader / Vortex | Wider audience | Different folders (`XboxGames\Starfield\Content\Data`, `Documents\My Games\Starfield\Data`, Plugins.txt in `%LOCALAPPDATA%\Starfield`); Vortex calls its ASI loader outdated; MO2 cannot manage Game Pass | paths **verified** ([Nexus forum guide](https://forums.nexusmods.com/topic/13459379-a-guide-to-game-pass-modding-no-mod-manager), [Vortex extension](https://www.nexusmods.com/site/mods/634)); that it would work **supported hypothesis** |
| Note: Address Library ships MS Store `.bin` files, but SFSE's loader refuses non-Steam | n/a | n/a | **verified** ([Nexus 3256](https://www.nexusmods.com/starfield/mods/3256)) |

### Engine budgets and packing

| Option | What it gives | Cost or risk | Label |
|---|---|---|---|
| One full ESM + 1 to 3 large archives for the core | Few slots used | Archive size ceiling near 4 GiB; core64 already about 8.5 GiB at full resolution | **verified** numbers; plan **supported hypothesis** |
| Medium masters for DLC areas or interior clusters | Saves full slots (256 medium) | Record limit conflict: about 65,535 (Bethesda) vs ObjectID up to 0xFF (MO2 BPM page); type cannot be changed later | **verified** both claims; conflict **unresolved** |
| Update plugins for pure overrides of Starfield records | No new forms | Take a slot since 1.12.30; xEdit cannot write them | **verified** (LOOT, TC) |
| Depend on BA2 Limit Fix | Lifts 256 archives | SFSE plugin, pinned per runtime | **verified** |
| Build our own merged static meshes per cell (precombine stand-in) | Fewer draw calls | Engineering; no CE2 precombine feature found | **unresolved** |
| Texture presets keyed to VRAM | Fits 8 GB cards | Current caps (1024 colour / 512 normal) were set for archive size, not VRAM | **supported hypothesis** |

### Crash diagnosis for players

| Option | What it gives | Cost or risk | Label |
|---|---|---|---|
| Trainwreck | "Compatible with all versions of the game past, present, and future"; SFSE or `.asi`; logs to `Documents\My Games\Starfield\SFSE\Crashlogs` | Licence and GitHub page not read | **verified** features ([allmods mirror](https://allmods.net/starfield-mods/starfield-miscellaneous/trainwreck-a-crash-logger-v1-1/), [Nexus article 559](https://www.nexusmods.com/starfield/articles/559)); licence **unresolved** |
| Starfield Engine Fixes' "Detailed Crash Logger" (v21.2, 4 Oct 2026) | More features, BA2 counter, file handle limit option | Pinned per runtime | **verified** ([Nexus 10457](https://www.nexusmods.com/starfield/mods/10457?tab=files)) |
| WER + ProcDump (current) | Full dumps | 17.4 GB per crash; misses the int3 Havok assert | **verified** (repo journal) |

## Questions

### A. Fallout 4 versions and stores as inputs

**VM-01. Which Fallout 4 data versions does the launcher accept: 1.10.163 only, 1.10.984, 1.11.x, or all?**
- Why it matters: most players are on 1.11.240; requiring a downgrade repeats Fallout London's support load.
- Options: (a) require a downgrade (universal downgrader, no login, xdelta3) ([Steam thread](https://steamcommunity.com/app/377160/discussions/0/685239894022330731/)); (b) support each runtime with per-version fixtures; (c) normalise inputs to one canonical record set. Never ask for credentials (ROADMAP C1). (also: precedents Q7)
- Answer by: record and archive diff between 1.10.163, 1.10.984 and 1.11.240 data (VM-02), then owner decision.
- Blocks: Launcher, Release, New game.
- Status: open.

**VM-02. Did the next-gen and Anniversary updates change Fallout4.esm, the DLC .esm files or the BA2 archives, and which records?**
- Why it matters: if records differ, players build different games and the launcher's determinism gate (L4) fails across players. The Vault 111 cells and MQ101 may differ by player.
- Options: evidence so far: one guide replaces only Fallout4.exe (**verified**); another lists six depots (**verified** that it lists them); the downgrader detects DLC and patches "the modified files" (**supported hypothesis** that data changed). (also: versions-performance Q2, precedents Q4, Q30)
- Answer by: hash and record-level diff (Mutagen or xEdit read-only) of the base and DLC masters from a 1.10.163 copy and a 1.11.240 install. PC probe.
- Blocks: Launcher, New game, All interiors, Release.
- Status: open.

**VM-03. Do next-gen Fallout 4 BA2 archives use header versions the reader rejects (v7/v8)?**
- Why it matters: `ba2.py` raises `unsupported version` for anything but 1 to 3 (**verified**). The v7/v8 claim is from memory (**unresolved**).
- Options: add v7/v8 parsing after reading xEdit/BSArch source for the layout; or require 1.10.163 archives.
- Answer by: first 8 bytes of each `Fallout4 - *.ba2` on a current install (a 1-minute PC probe), plus offline source reading.
- Blocks: Launcher, All interiors (any build on a current install).
- Status: open.

**VM-04. How does the launcher identify the Fallout 4 data version, store and language without the exe?**
- Why it matters: the converter never runs Fallout 4; the launcher note's "check its version" should check data (VP Corrections). Fallout London failed on a wrong Fallout4.esm size (**verified**, GameStar).
- Options: hash table of Fallout4.esm and each DLC .esm per version; BA2 header bytes; presence of Anniversary CC files; one hash table per language, or hash only language-neutral files and treat STRINGS separately (DC Q19; TTW requires English installs, **verified**). (also: versions-performance Q8, distribution-community Q19, precedents Q4)
- Answer by: hashes from three installs (1.10.163, 1.10.984, 1.11.240) and one non-English install. PC probe plus community contacts.
- Blocks: Launcher, Release.
- Status: open.

**VM-05. Do GOG, Epic and Microsoft Store / Game Pass Fallout 4 installs work as sources?**
- Why it matters: the converter needs only data, so the store may not matter, but layout, BA2 versions and runtime may differ. Epic cannot roll back (**verified**); Skyblivion and TTW reject some stores (**verified**).
- Options: Steam and GOG only (TTW, Skyblivion mix-and-match); any store whose data hashes match a known table.
- Answer by: file listing and hashes from a GOG, an Epic and a Game Pass install. Community contact. (also: versions-performance Q11, precedents Q8)
- Blocks: Launcher, Release.
- Status: open.

**VM-06. Which Fallout 4 runtime is canonical for our synthetic test fixtures, and do we keep fixtures for more than one?**
- Why it matters: unit tests use synthetic fixtures; a per-runtime header and record fixture (BA2 v1 vs v7/v8, one changed record) catches an FO4 update offline without shipping game data.
- Options: 1.10.163 only; 1.10.163 + current. (also: versions-performance Q31, precedents Q30)
- Answer by: offline tooling after VM-02 and VM-03.
- Blocks: Launcher, Release.
- Status: open.

### B. Creation Club and other official extras

**VM-07. Are the ~150 Anniversary Creation Club files (and the High-Res Texture Pack) inputs, ignored, or refused?**
- Why it matters: they change what "the player's Fallout 4" means; the Anniversary Edition bundles "over 150 pieces of Creation Club content" (**verified**, [Nexus news 15400](https://www.nexusmods.com/news/15400)). CC files and the HD pack broke Fallout London installs (**verified**). A commenter says CC skins use BA2 slots (**unresolved**).
- Options: ignore every `cc*.esl`; opt in per file; refuse to build while they are active.
- Answer by: owner decision; offline list of CC files from a current install.
- Blocks: Launcher, Release, World.
- Status: open.

### C. Starfield versions, patch days and SFSE

**VM-08. Which of our Starfield record overrides break on a patch (start quests, planet and worldspace data)?**
- Why it matters: patches change record semantics, not only the exe. USFP had to redo planet data after Bethesda "changed its planet data storage" (1.15.222) (**verified**, [USFP history](https://www.afkmods.com/Unofficial%20Starfield%20Patch%20Version%20History.html)). Our Vault 111 start overrides Starfield start quests; FO4TerrainCore overrides Mars.
- Options: keep overrides minimal; a scripted record diff of every overridden record against each new Starfield.esm. (also: versions-performance Q1, Q19; precedents Q2)
- Answer by: diff Starfield.esm quest and planet records across 1.16.236, .242 and .244. Offline research with the repo's record tools.
- Blocks: New game, World, Release.
- Status: open.

**VM-09. Do vanilla Starfield asset paths we reference (meshes, door clips) survive patches?**
- Why it matters: 1.11.36 renamed vanilla mesh paths; a migration tool maps about 323,099 meshes (**verified**, [Nexus 9234](https://www.nexusmods.com/starfield/mods/9234)).
- Options: resolve vanilla paths at build time on the player's PC, never hard-code; keep a hash list of referenced paths and re-check after each patch. (also: starfield-toolchain Q4)
- Answer by: offline tooling.
- Blocks: Door animations, All interiors, Release.
- Status: open.

**VM-10. Does a Starfield patch reset Plugins.txt or `Starfield.ccc`, or re-order Creations?**
- Why it matters: 1.15.214 fixed "Creations load order restoration" (**verified**, [SteamDB 18285521](https://steamdb.info/patchnotes/18285521)); a reset would silently unload our plugins.
- Options: preflight re-checks load order after every Starfield version change.
- Answer by: diff Plugins.txt and `.ccc` before and after the next patch. PC probe. (also: starfield-toolchain Q3)
- Blocks: Launcher.
- Status: open.

**VM-11. Is a build keyed to the Starfield runtime?**
- Why it matters: the build graph caches by input hash + converter version; if Starfield.esm changes, overrides may need a rebuild.
- Options: include the Starfield.esm hash in the cache key; or only the hashes of records we override.
- Answer by: offline design. (also: versions-performance Q14)
- Blocks: Launcher.
- Status: open.

**VM-12. What does the launcher do when Steam updates Starfield?**
- Why it matters: SFSE supports only the latest Steam runtime, so a rollback must roll back both; Fallout London's release was blocked by a platform update two days before launch (**verified**, [TechSpot](https://www.techspot.com/community/topics/fallout-london-was-ready-for-launch-until-bethesdas-buggy-next-gen-update-broke-it.285631/)).
- Options: refuse until supported (current preflight gate); warn and run a data-only tier; keep a "known good" build table updated within N days. (also: versions-performance Q12, starfield-toolchain Q1, distribution-community Q9, precedents Q2)
- Answer by: owner decision, informed by the 2026 patch-day timeline (SFSE same day).
- Blocks: Launcher, Release.
- Status: open.

**VM-13. Do saves survive a Starfield patch with our plugins loaded?**
- Why it matters: long playthroughs span patches.
- Options: test each patch; tell players to keep a pre-patch save.
- Answer by: save on 1.16.242, load on 1.16.244 (both on Steam depots). PC probe. (also: versions-performance Q22)
- Blocks: Release, People and story.
- Status: open.

**VM-14. Do we promise save compatibility across our own releases?**
- Why it matters: FormIDs change if the build changes (L4); GAMMA says saves are "mostly" compatible and recommends a fresh start (**verified**, [r/stalker mirror](https://pol1.lr.ggtyler.dev/r/stalker/comments/1h3ylar/gamma_093_release/lzvuf8f/?context=3)); Fallout London's Rabbit & Pork needs a new save (**verified**).
- Options: no promise before 1.0; a "save-safe" flag per release; a migration tool.
- Answer by: determinism test plus a save loaded across two builds; then owner decision. (also: distribution-community Q1)
- Blocks: Release.
- Status: open.

**VM-15. Does the Creation Kit track game versions exactly; does an older CK refuse or corrupt plugins?**
- Why it matters: SFSE and the CK MAY be required; CK changes ride inside game patch notes (**verified**, 1.15.214), but whether every patch ships a matching CK is a **supported hypothesis**.
- Options: record the CK version in preflight; refuse on mismatch.
- Answer by: read the CK exe version after the next patch. PC probe. (also: starfield-toolchain Q34)
- Blocks: Launcher, All interiors (navmesh batch), People and story (lip sync).
- Status: open.

**VM-16. Should someone watch Bethesda's Steam `beta` branch for upcoming runtimes?**
- Why it matters: 1.15.214 was public on the beta branch before release (**verified**); beta feedback runs in the Bethesda Studios Discord's #steam-beta-feedback (**verified**, DC).
- Options: a weekly check in the watchdog/Codex runbook; owner watches.
- Answer by: offline research on who monitors and how. (also: versions-performance Q30)
- Blocks: Release.
- Status: open.

**VM-17. Data-only core with SFSE as an optional layer: is this the long-term strategy?**
- Why it matters: everything exe-bound (SFSE plugins, Address Library) breaks on patches: 1.14.70 needed recompiles and 1.15.216 broke "most if not all" plugins (**verified**). Data breaks less often and a diff catches it. Each SFSE dependency also excludes Game Pass. Third-party SFSE plugins we might use (BA2 Limit Fix, Engine Fixes) lag behind patches.
- Options: Papyrus and data only for the core, SFSE for add-ons; SFSE where needed with a maintained build per runtime (CommonLibSF + Address Library). Precedent: Skywind needs SKSE plugins (**verified**, [Skywind FAQ](https://tesrskywind.com/faq/)). (also: versions-performance Q3, Q21, Q23, Q32; starfield-toolchain Q2, Q21; distribution-community Q36; precedents Q19, Q20)
- Answer by: list what each phase calls (door package, start, Pip-Boy) offline; owner decision recorded in decisions.md.
- Blocks: New game, Door animations, Fallout systems, People and story, Release.
- Status: open.

**VM-18. When a patch breaks SFSE plugins, what does each SFSE-dependent feature do?**
- Why it matters: decides whether a compiler-setting patch takes the whole port down or only some features.
- Options: degrade (hide the feature); block launch; Papyrus fallback. (also: starfield-toolchain Q21)
- Answer by: owner decision after VM-17.
- Blocks: Fallout systems, Release.
- Status: open.

### D. Pinning, rollback and stores for Starfield

**VM-19. Which pin method does the launcher use for Starfield?**
- Why it matters: Steam auto-updates; a mid-session update breaks a built set. Player-run login downgrades are ruled out.
- Options: refuse on mismatch (current); MO2-style Stock Game copy (doubles disk use, **supported hypothesis**); Steam "update only when launched"; read-only `appmanifest` (Fallout London, **verified**); keep a backup exe. (also: versions-performance Q13, starfield-toolchain Q13)
- Answer by: owner decision plus offline research on what Steam allows.
- Blocks: Launcher, Release.
- Status: open.

**VM-20. How does the launcher detect the Starfield version and store?**
- Why it matters: preflight and the support matrix depend on it.
- Options: exe file version; Steam `appmanifest`; presence of the `XboxGames` path; Starfield.exe hash table per build (DC Q9). (also: starfield-toolchain Q9)
- Answer by: one PC read; offline code. PC probe.
- Blocks: Launcher.
- Status: open.

**VM-21. Do we support Game Pass Starfield at all?**
- Why it matters: SFSE and MO2 do not run there; Vortex does via an ASI loader it calls outdated (**verified**). A data-only core might load there.
- Options: Steam-only v1 and say so; a no-SFSE build loaded through Plugins.txt and archives; later. (also: versions-performance Q27, starfield-toolchain Q24, distribution-community Q10)
- Answer by: load the S9 test plugin on a Game Pass install (community contact); owner decision after VM-17.
- Blocks: Release, Launcher.
- Status: open.

**VM-22. Can we keep a "previous Starfield runtime" test profile?**
- Why it matters: to reproduce reports from players who have not updated or rolled back.
- Options: Steam beta branches (older public builds offered as branches: **unresolved**); depot download with the owner's own login on the test PC; a copy of the exe.
- Answer by: offline research plus PC probe. (also: versions-performance Q28)
- Blocks: Release.
- Status: open.

### E. Engine budgets

**VM-23. How many BA2 archives and plugin slots will the full port use, and does it need the BA2 Limit Fix?**
- Why it matters: 256 archives and 253 full slots are shared with the player's other mods and Creations; a soft instability appears around 100 to 120 plugins (**verified** as article claims, slot-per-override rests on "one study").
- Options: core as one ESM + 1 to 3 archives; medium masters for DLC areas; depend on BA2 Limit Fix. (also: versions-performance Q17, starfield-toolchain Q17)
- Answer by: archive counts with Starfield Engine Fixes' counter on the owner's PC; plugins.txt counts from testers. PC probe plus community contact.
- Blocks: World, All interiors, Release.
- Status: open.

**VM-24. Can one archive pass 4 GiB, and how many numbered archives does a plugin auto-load (`- Main01.ba2`?)?**
- Why it matters: core64 needs about 8.5 GiB at full resolution; `<plugin> - Main.ba2` auto-loads (**verified**, repo S9), numbered ones are **unresolved**.
- Options: split by kind (Main/Textures); numbered archives; INI archive lists (avoid: Controlled Folder Access blocked Documents writes, **verified** repo).
- Answer by: a synthetic archive over 4 GiB and two numbered archives loaded in game (an S9-style spike). PC probe. (also: versions-performance Q4, starfield-toolchain Q14)
- Blocks: All interiors, World.
- Status: open.

**VM-25. What is the real medium master record limit, and should interiors or DLC areas be medium masters?**
- Why it matters: about 65,535 (Bethesda) vs ObjectID up to 0xFF (MO2 BPM page); the type cannot be changed later.
- Options: full ESM only; medium masters per region; update plugins for pure overrides (cost a slot since 1.12.30). (also: starfield-toolchain Q8, Q32, Q33)
- Answer by: write synthetic medium masters with 4,000 and 60,000 records and load them (PC probe); record counts per FO4 cluster (offline); owner decision.
- Blocks: All interiors, World.
- Status: open.

**VM-26. Does Starfield have a precombine/previs equivalent our build could produce?**
- Why it matters: decides between writing our own merged meshes or finding an engine feature. FO4 relies on precombines (`SCOL\CM*.NIF`); no CE2 precombine step found in any source (**unresolved**).
- Options: merge static geometry per cell at build time; accept the cost; reduce clutter.
- Answer by: scan Starfield.esm vanilla interiors for precombine-like data (Mutagen/xEdit); strings scan of CreationKit.exe. Offline research plus PC. (also: versions-performance Q6, starfield-toolchain Q7)
- Blocks: All interiors, World.
- Status: open.

**VM-27. What per-cell reference and draw-call budget keeps interiors at 60 fps on a minimum-spec GPU?**
- Why it matters: we place references one by one; draw calls may grow sharply against FO4 (**supported hypothesis**).
- Options: as VM-26.
- Answer by: frame time and reference count in the densest FO4 interiors (Vault 111, Diamond City Market interior, Mass Fusion) with PresentMon or the game's overlay. PC probe. (also: versions-performance Q5)
- Blocks: All interiors.
- Status: open.

**VM-28. Does an exterior with 650k+ references stream without traversal stutter?**
- Why it matters: Starfield Engine Fixes ships "Reduce Traversal Stutter" and "Increase File Handle Limit" (**verified** names), which suggests vanilla pain points (**supported hypothesis**).
- Options: accept; merged meshes; fewer references per cell.
- Answer by: frame-time capture on a walking route over core64 (the route runner exists). PC probe. (also: versions-performance Q18)
- Blocks: World.
- Status: open.

### F. Hardware, disk and build performance

**VM-29. What texture caps should the default build use per VRAM tier?**
- Why it matters: the 2026-10-12 caps (1024 colour / 512 normal) were set for archive size, not VRAM; no official VRAM figure exists (**verified**).
- Options: three presets keyed to detected VRAM.
- Answer by: VRAM use at each cap on an 8 GB card. Community tester. (also: versions-performance Q20)
- Blocks: Launcher, Release.
- Status: open.

**VM-30. What disk space does the launcher check for, and can it build on another drive than Starfield?**
- Why it matters: Starfield 125 GB on SSD + Fallout 4 (about 30+ GB, **unresolved**) + work folder + output + temporary archives; the owner's D: is nearly full. FNV to FO4 states 1 to 2 hours; TTW output is about 17 GB (**verified**).
- Options: measure peak disk of a whole-core build and scale by cell count; separate work drive.
- Answer by: PC probe measuring work folder + archive + checkpoint peak. (also: versions-performance Q15, distribution-community Q16)
- Blocks: Launcher, Release.
- Status: open.

**VM-31. Can the build run on a minimum-spec PC (16 GB RAM, 6 cores) in acceptable time, and how many threads by default?**
- Why it matters: the 7950X3D hides costs. TTW added `-threads:1` after CPU overheating and suggests disabling E-cores (**verified**, [TTW FAQ](https://thebestoftimes.moddinglinked.com/faq.html)).
- Options: configurable worker count with a safe default; memory cap.
- Answer by: run the 15-cell build with a process memory cap and limited cores; record peak RSS and time (PC probe or cloud VM). (also: versions-performance Q16, precedents Q11)
- Blocks: Launcher.
- Status: open.

**VM-32. Do we split the heavy base build from small fix updates, like TTW and YUP?**
- Why it matters: re-running a multi-hour build for each bug fix drives players away; TTW split YUP "so existing installations can be updated more easily" (**verified**).
- Options: stage cache keyed by converter version (proposed); a separate small fix package.
- Answer by: owner plus Implementation; rebuild time vs fix size on one archive. (also: precedents Q9, Q10)
- Blocks: Launcher, Release.
- Status: open.

### G. Maintenance process

**VM-33. Which crash logger do we tell players to install, and do bug reports require its log?**
- Why it matters: the Havok int3 leaves no WER entry; one launch ended "with no crash log" (repo journal).
- Options: Trainwreck (version-independent); Starfield Engine Fixes' logger (pinned per runtime).
- Answer by: trigger the known Havok assert (vault cart case) with each logger. PC probe. (also: versions-performance Q24)
- Blocks: Release.
- Status: open.

**VM-34. What is on the patch-day checklist, and is it automated?**
- Why it matters: Starfield has 2027 content announced (**unresolved**, fansite) and Fallout 4 still patches.
- Options: on a new `Starfield.exe` version run SFSE/Address Library version check, NifSkope loads a vanilla mesh, Mutagen reads Starfield.esm header, our plugin loads, vanilla path hash list (TC Q31), S1/S2/S9 smoke routes, record diff (VM-08), post to #32. (also: versions-performance Q29, starfield-toolchain Q31)
- Answer by: time one full smoke chain; owner approves, QA owns.
- Blocks: Release.
- Status: open.

**VM-35. Which tool versions do we pin, and how do we upgrade them?**
- Why it matters: Mutagen 0.55 alphas change weekly; the Starfield index fix landed in 0.54.4 (**verified**). xEdit 4.1.5q is Discord-only, so it cannot be fetched by script (**verified**).
- Options: pin Mutagen; upgrade with round-trip tests; depend only on tools with stable public packages (NuGet, GitHub), others as optional oracles.
- Answer by: offline round-trip tests on both versions. (also: starfield-toolchain Q28)
- Blocks: Release, all phases.
- Status: open.

**VM-36. What support matrix and patch-follow promise go on the release page?**
- Why it matters: players need one line, and a missed promise costs trust.
- Options: "Steam Starfield 1.16.244 + SFSE 0.2.21; Fallout 4 data from 1.10.163 or 1.11.240"; "within a week, use the previous build until then"; automated patch-day run. (also: versions-performance Q25, Q26)
- Answer by: owner decision after VM-01 and VM-12.
- Blocks: Release.
- Status: open.

**VM-37. Who owns patch-day duty when the project is quiet?**
- Why it matters: both games are still moving; maintenance runs for years.
- Options: owner; the watchdog/Codex runbook carries detection and reporting only (no deploys or code changes).
- Answer by: owner decision. (also: versions-performance Q33)
- Blocks: Release.
- Status: open.

**VM-38. What is the real long-term cost, measured?**
- Why it matters: precedents took 5 years (Enderal, 14 people; Fallout London, about 100) to 13+ (Skyblivion, Skywind) (**verified**); converting is our structural advantage, but maintenance across two moving games adds cost.
- Options: measure hours per converted interior cell and per patch day now, then extrapolate.
- Answer by: owner plus QA, from docs/ai/optimization.md baselines. (also: precedents Q32)
- Blocks: Release, Multi-game.
- Status: open.

## Owner decisions in this area

Each line is a recommendation, not a decision.

- **VM-01 Fallout 4 data versions:** recommend accepting 1.10.163 and the current Steam runtime (1.11.240) through
  data-version detection, once VM-02 and VM-03 show the size of the difference. Most players own 1.11.240, and the
  downgrade route was a large support load for Fallout London.
- **VM-07 Creation Club and HD pack:** recommend ignoring them by default (detected and reported, not converted). This
  keeps the input set small and avoids the install failures Fallout London saw.
- **VM-12 Starfield patch response:** recommend keeping the refuse-on-mismatch gate, with a clear message and a
  "known good" table. SFSE was same-day in 2026, so our own fix time is the variable.
- **VM-14 Save compatibility:** recommend no promise before 1.0, stated in every changelog.
- **VM-17 Data-only core:** recommend a data and Papyrus core with SFSE features as optional add-ons. It sets the
  maintenance cost for years and keeps Game Pass possible; record it in decisions.md.
- **VM-18 SFSE breakage behaviour:** recommend degrade (hide the feature), not block launch, once VM-17 is decided.
- **VM-19 Pin method:** recommend refuse plus guidance ("update only when launched"); no Stock Game copy by default
  because of disk cost; no login-based downgrade (already ruled out).
- **VM-21 Game Pass:** recommend Steam-only for v1 and say so, revisit after a community Game Pass load test.
- **VM-25 Plugin types:** recommend one full ESM for the core until the medium master limit is measured.
- **VM-36 Support matrix and patch-follow promise:** recommend publishing the matrix line and "use the previous build
  until we post support", with no time promise until patch-day timing is measured.
- **VM-37 Patch-day duty:** recommend detection and reporting through the existing watchdog/Codex runbook, with
  fixes owned by Claude and approved by the owner.

## Cheapest experiments

Nothing here runs now; this is a list.

| # | Experiment | Kind | Closes |
|---|---|---|---|
| E1 | On one current Steam Fallout 4 install: read the first 8 bytes of every `Fallout4 - *.ba2`, hash and size Fallout4.esm and each DLC .esm, list `cc*` files. Compare with the owner's 1.10.163 copy | PC read-only probe, minutes | VM-02 (first half), VM-03, VM-04, VM-07 (inputs list) |
| E2 | Record-level diff of base and DLC masters between the two installs (Mutagen read-only) | Offline after E1 copies hashes/records | VM-01, VM-02, VM-06 |
| E3 | Scripted diff of every Starfield record we override (start quests, planet, worldspace) and every vanilla path we reference, against Starfield.esm of 1.16.236/.242/.244 | Offline tooling, reusable each patch day | VM-08, VM-09, VM-11, part of VM-34 |
| E4 | Synthetic load spike: one archive over 4 GiB, two numbered `- Main01.ba2` archives, medium masters with 4,000 and 60,000 records; read the Engine Fixes BA2 counter | PC probe (S9-style) | VM-23, VM-24, VM-25 |
| E5 | Frame-time capture (PresentMon) on the core64 walking route and in three dense interiors, with reference counts and VRAM use | PC probe, route runner exists | VM-27, VM-28, VM-29 (owner tier), VM-26 (cost side) |
| E6 | Trigger the vault cart Havok assert with Trainwreck, then with Engine Fixes' logger | PC probe | VM-33 |
| E7 | 15-cell build under a memory cap and limited cores; record peak RSS, peak disk, time | Offline or cloud VM | VM-30, VM-31 |
| E8 | List every SFSE, Address Library or runtime-address call in the repo's door, start and bridge code | Offline repo read | VM-17, VM-18 |
| E9 | At the next Starfield patch: diff Plugins.txt and `Starfield.ccc`, read the CK exe version, load a 1.16.244 save | PC probe on patch day | VM-10, VM-13, VM-15 |

## Gaps for wave 2

- Confirm Fallout 4 next-gen BA2 header versions (v7/v8) and their layout from xEdit/BSArch source.
- Which files and records changed in Fallout 4 1.10.98x and 1.11.x (patch notes, depot listings, community diffs).
- Fallout 4 runtime and data on GOG, Epic and Microsoft Store / Game Pass today.
- Starfield Steam depot IDs and whether older public builds are offered as beta branches.
- Starfield draw-call budgets, reference streaming, VRAM profiles; any CE2 precombine/previs equivalent.
- Trainwreck's GitHub page and licence.
- Exact dates for 1.14.70 (late Sep 2024, **supported hypothesis**) and 1.15.222 (sources disagree), and SFSE lag for
  the 2024 patches (**unresolved** in VP's table).
- Fallout 4 install size with all DLC (and with the Anniversary content).
- Whether every Starfield patch ships a matching Creation Kit build.
- Whether Fallout London's Rabbit & Pork accepts next-gen Fallout 4 (one reader comment says 1.10.163 only).
- Current Starfield Steam Deck rating (also listed in DC follow-ups).
- Real disk cost of an MO2 Stock Game copy of Starfield.

## Handed to phase files

| Question | Target file |
|---|---|
| Do door hooks rely on SFSE or runtime addresses? (versions-performance Q3; cross-cutting part is VM-17) | door-animations.md |
| Can the Vault 111 start be built with no SFSE (data + Papyrus only)? (starfield-toolchain Q2; cross-cutting part is VM-17) | newgame.md |
| Canonical Fallout 4 records for Vault 111 cells and MQ101 (versions-performance Q2; data diff is VM-02) | newgame.md |
| Is CK batch navmesh (`-UpdateNavmeshGeneration ... -Part`) usable for 1,000+ interiors? (starfield-toolchain Q6, precedents Q5) | interiors.md |
| Without SFSE serialization, where does SFSE plugin state live? (starfield-toolchain Q22) | engine-mechanics.md |
| Does the SFSE Scaleform menu interface still work on 1.16.244, for the Pip-Boy? (starfield-toolchain Q23) | engine-mechanics.md |
| How is LOD made for the Earth-like planet? (starfield-toolchain Q15) | engine-mechanics.md |
| Does the launcher fetch SFSE and Address Library or ask the player; redistribution rights (starfield-toolchain Q10) | launcher.md |
| Where does the launcher get Archive2 and the Papyrus compiler? (starfield-toolchain Q11) | launcher.md |
| Which tools do players install vs only the team? (starfield-toolchain Q25) | launcher.md |
| INI writes: `StarfieldCustom.ini` or none (starfield-toolchain Q12) and `sTestFile` handling (distribution-community Q7) | launcher.md |
| Reading `Starfield.ccc` and ContentCatalog.txt in preflight (distribution-community Q8) | launcher.md |
| CLI first for Linux and Steam Deck; CK Papyrus compiler under Proton (distribution-community Q12, Q37) | launcher.md |
| Robust My Games and Documents paths; non-ASCII paths (distribution-community Q13, Q14) | launcher.md |

## Sources

Findings files: findings/versions-performance.md, findings/starfield-toolchain.md, findings/distribution-community.md,
findings/precedents.md.

Repo files cited through them: docs/SETUP.md, docs/PLAN.md, docs/PLAY-AND-TEST.md, docs/ROADMAP.md (C1),
docs/ai/optimization.md, docs/ai/decisions.md (2026-10-12), docs/JOURNAL.md (2026-10-16), docs/FORMAT-GAP.md,
docs/spikes/S2-S4-S9-plugin-units-loading.md, src/fo4sf/ba2.py, src/fo4sf/core/preflight.py,
scripts/bridge/make_bridge.py; /mnt/project-files/research/next-phase/launcher-architecture.md.

- https://www.nexusmods.com/fallout4/mods/42147?tab=files
- https://www.nexusmods.com/news/15400
- https://forums.nexusmods.com/topic/13525754-how-to-downgrade-fallout-4-game-of-the-year-edition-after-the-anniversary-update-rollback-from-111137-to-110984/
- https://steamcommunity.com/sharedfiles/filedetails/?id=3604110005
- https://steamcommunity.com/app/377160/discussions/0/685239894022330731/
- https://www.nexusmods.com/starfield/mods/106?tab=files
- https://www.nexusmods.com/starfield/mods/106
- https://sfse.silverlock.org/
- https://raw.githubusercontent.com/ianpatt/sfse/master/sfse_whatsnew.txt
- https://www.nexusmods.com/starfield/mods/3256
- https://patched.gg/games/starfield
- https://patchbot.io/games/starfield/articles/507-update-116244-june-11-2026
- https://starfield.gg/starfield-latest-update/
- https://starfield.gg/starfield-update-1-16-236-patch-notes-free-lanes/
- https://bethesda.net/en/article/2HBTwuF9g9baAQkEud4WZ9/starfield-update-1-16-242-may-14-2026
- https://bethesda.net/en-US/news/starfield-update-1-16-244-june-2026
- https://steamdb.info/patchnotes/18285521
- https://twt.omada.cafe/r/Starfield/comments/1kg7k32/starfield_update_115214_may_6_2025_beta
- https://www.afkmods.com/Unofficial%20Starfield%20Patch%20Version%20History.html
- https://www.nexusmods.com/starfield/mods/9234
- https://www.nexusmods.com/news/14993
- https://loot.readthedocs.io/en/0.24.1/app/changelog.html
- https://www.nexusmods.com/starfield/mods/17318
- https://www.nexusmods.com/starfield/mods/10457?tab=files
- https://www.nexusmods.com/starfield/mods/17936
- https://forums.nexusmods.com/topic/13518743-crash-issue-too-many-ba2-files-causing-ctds-%E2%80%93-looking-for-fix-or-insight/
- https://www.nexusmods.com/starfield/articles/688
- https://www.nexusmods.com/starfield/articles/559
- https://allmods.net/starfield-mods/starfield-miscellaneous/trainwreck-a-crash-logger-v1-1/
- https://forums.nexusmods.com/topic/13459379-a-guide-to-game-pass-modding-no-mod-manager
- https://starfieldwiki.net/wiki/Starfield:System_Requirements
- https://github.com/ejams1/starfield-modding-guide
- https://www.nuget.org/packages/Mutagen.Bethesda.Starfield
- https://api.github.com/repos/Mutagen-Modding/Mutagen/releases?per_page=8
- https://github.com/TES5Edit/TES5Edit/releases
- https://reddit.sentinel-team.org/posts/1u6jz38/snapshots/2026-06-16T07%3A02%3A42.6264Z
- https://github.com/fo76utils/nifskope/releases
- https://github.com/Modorganizer2/modorganizer/releases
- https://www.nexusmods.com/site/mods/634
- https://wiki.wabbajack.org/user_documentation/Supported%20Games%20and%20Mod%20Managers.html
- https://forums.nexusmods.com/topic/13203033-helpful-links-references-and-news/page/36
- https://pol1.lr.ggtyler.dev/r/stalker/comments/1h3ylar/gamma_093_release/lzvuf8f/?context=3
- https://nexusmods.com/fallout4/mods/75425
- https://thebestoftimes.moddinglinked.com/intro.html
- https://thebestoftimes.moddinglinked.com/faq.html
- https://thebestoftimes.moddinglinked.com/ttw.html
- https://taleoftwowastelands.com/viewtopic.php@t=1031
- https://taleoftwowastelands.com/viewtopic.php@t=2111
- https://www.techspot.com/community/topics/fallout-london-was-ready-for-launch-until-bethesdas-buggy-next-gen-update-broke-it.285631/
- https://www.pcgamesn.com/fallout-london/epic-games-store
- https://www.pcgamer.com/games/fallout/after-years-fallout-4s-much-anticipated-dlc-sized-mod-fallout-london-is-out-heres-how-to-install-it/
- https://www.gamestar.de/artikel/fallout-london-absturz-crash-technische-probleme,3417255,seite2.html
- https://www.gamingonlinux.com/2025/09/fallout-london-mod-gets-a-huge-upgrade-with-rabbit-pork/page=1/
- https://en.wikipedia.org/wiki/Fallout:_London
- https://skyblivion.com/faq
- https://tesrskywind.com/faq/
- https://en.wikipedia.org/wiki/Enderal
- https://en.wikipedia.org/wiki/Skyblivion
- https://en.wikipedia.org/wiki/Skywind
