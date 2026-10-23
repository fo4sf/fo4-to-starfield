# Game versions, engine budgets and long-term maintenance

Part of the [next-phase framework](README.md). Waves 1 and 2, 2026-10-19. Sources: findings/versions-performance.md, plus
the version and store parts of findings/starfield-toolchain.md, findings/distribution-community.md and
findings/precedents.md; wave 2 also the SFSE and Game Pass part of findings/legal-policy.md.

Short names used below: **VP** = findings/versions-performance.md, **TC** = findings/starfield-toolchain.md,
**DC** = findings/distribution-community.md, **PR** = findings/precedents.md, **LP** = findings/legal-policy.md.
"(also: TC Q9)" means the same question appears there as question 9. "VP W2-1" means item W2-1 in that file's
"Wave 2 additions" section.

## In short

- We pin Fallout 4 **1.10.163** and Starfield **1.16.244** + SFSE 0.2.21, Steam only. A player on today's Steam has
  Fallout 4 **1.11.240** (Aug 2026), so our source pin does not match what most players own (VP, **verified**).
- Starfield has been calm since 11 June 2026 and SFSE shipped the same day as each 2026 patch. Fallout 4 moved four
  times since the Anniversary Edition (Nov 2025), with about 15 days of F4SE lag at launch (VP, **verified**).
- Most uncertain: whether next-gen and Anniversary updates changed Fallout 4 **data** (Fallout4.esm, DLC .esm). For BA2
  archives wave 2 settled most of it: next-gen archives carry header version 7 or 8 (**verified**), and xEdit and OpenMW
  read them with the v1 layout, so only the version number changed (**supported hypothesis**). Our reader rejects them
  today, but the fix is one line (accept 1, 7, 8), not a format project (VP W2-1).
- Also uncertain: whether Starfield's engine loads one archive past 4 GiB (the format allows it, **verified**), and how
  the build and the game run below the owner's high-end PC. Settled in wave 2: a medium master holds ObjectIDs
  0x0000-0xFFFF (**verified**, xEdit), and CE2 has no precombine/previs records to produce (**verified** schema).
  [Correction 2026-10-19: but the Starfield CK has the GUI actions "Generate Precombined Visibility for Current Cell"
  and "... All Loaded Cells" (interiors.md T9), so a precombined-visibility bake may exist; VM-26 is open again.]
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
| Fallout 4 next-gen (April 2024) introduced BA2 header versions 7 and 8; old-gen exe loads only up to v1; old-gen users hex-edit the byte to `01` | **verified** | VP W2-1; [Nexus article 5844](https://www.nexusmods.com/fallout4/articles/5844) |
| xEdit and OpenMW parse FO4 v7/v8 with the same 24-byte header as v1; xEdit writes FO4 archives as v1 | **verified** (source: wbBSArchive.pas 545-553, 1336-1346; OpenMW `ba2gnrlfile.cpp` 92-104, `ba2dx10file.cpp` 95-109) | VP W2-1, TC W2-6 |
| v7/v8 changed only the version number (header, file table, compression unchanged) | **supported hypothesis** | VP W2-1 |
| BA2 offsets are 64-bit in the format, so the format does not stop at 4 GiB; whether Starfield's engine does is open | **verified** (format); engine **unresolved** | VP W2-3, TC W2-6 |
| A medium master holds ObjectIDs 0x0000-0xFFFF (at most 65,536); 256 medium slots; the MO2 page's "0xFF" is the slot count | **verified** (xEdit wbImplementation.pas 5219, 2464-2468; wbInterface.pas 22600) | TC W2-5 |
| Update-flagged plugins cannot hold new records (override-only) | **verified** (xEdit wbImplementation.pas ~5214) | TC W2-5 |
| Starfield's CELL has no precombine/previs subrecords (`XCRI`, `PCMB`, `XPRI` occur 0 times in sf1.pas); an `OVIS` "Object Visibility Manager" record exists, purpose undocumented | **verified** (schema) | TC W2-2 |
| Starfield's D3D12 renderer generates indirect draw arguments with a compute shader and issues ExecuteIndirect calls | **verified** | VP W2-2; [vkd3d-proton PR 1694](https://github.com/HansKristian-Work/vkd3d-proton/pull/1694) |
| SFSE's licence: MIT covers only `sfse/PluginAPI.h`; "The remainder of the files are currently not under a permissive license"; README: "The MS Store/Gamepass version is not supported" | **verified** | LP W2-C; [raw LICENSE](https://raw.githubusercontent.com/ianpatt/sfse/master/LICENSE), [github.com/ianpatt/sfse](https://github.com/ianpatt/sfse) |
| Loading a save or opening the Creations load-order menu deselected every plugin in `Plugins.txt` for some players (Vortex and plain Steam launches, Oct 2025 to Apr 2026); no root cause posted | **verified** (reports) | DC W2-1; [forum 13524420](https://forums.nexusmods.com/topic/13524420-game-launch-deactivates-starfield-plugins/) |
| Languages: Fallout 4 voiced EN, FR, IT, DE, ES, JA, text-only PL, PT-BR, RU, zh-Hant; Starfield voiced EN, FR, DE, ES, JA, text-only IT, PL, PT-BR, zh-Hans; Starfield CK English only | **verified** (Steam store API, 2026-10-19) | DC W2-4 |

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
| GOG | One commenter says GOG "never got the last update" [Added 2026-10-19: GOG Fallout 4 ships only 1.10.163.0, so GOG players need no downgrade] | ~~**unresolved** ([Nexus news 15400](https://www.nexusmods.com/news/15400))~~ [Correction 2026-10-19: **verified** (gogdb.org, via launcher.md revision 2)] |
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
| Note: Address Library ships MS Store `.bin` files, but SFSE's loader refuses non-Steam; SFSE's README says the MS Store/Game Pass version is not supported, so any phase that needs SFSE excludes Game Pass | n/a | n/a | **verified** ([Nexus 3256](https://www.nexusmods.com/starfield/mods/3256); LP W2-C) |

### Engine budgets and packing

| Option | What it gives | Cost or risk | Label |
|---|---|---|---|
| One full ESM + 1 to 3 large archives for the core | Few slots used | Archive size ceiling near 4 GiB (format allows more, engine **unresolved**, VP W2-3); core64 already about 8.5 GiB at full resolution | **verified** numbers; plan **supported hypothesis** |
| Medium masters for DLC areas or interior clusters | Saves full slots (256 medium) | Up to 65,536 ObjectIDs each (the MO2 "0xFF" is the slot count, TC W2-5); core64's 649,596 refs are about 10x that, so world plugins stay full masters; type cannot be changed later | limit **verified** (xEdit); in-game agreement **unresolved** |
| Update plugins for pure overrides of Starfield records | No new forms (xEdit refuses new records in them, TC W2-5) | Take a slot since 1.12.30; xEdit cannot write them | **verified** (LOOT, TC) |
| Depend on BA2 Limit Fix | Lifts 256 archives | SFSE plugin, pinned per runtime | **verified** |
| Build our own merged static meshes per cell (precombine stand-in) | Fewer draw calls | Engineering; CE2 has no precombine/previs records (**verified** schema) and a GPU-driven renderer (ExecuteIndirect), so per-object CPU draw cost likely matters less (**supported hypothesis**, VP W2-2, TC W2-2) [Correction 2026-10-19: the Starfield CK's "Generate Precombined Visibility" GUI actions (interiors.md T9) may be an engine-side alternative; unresolved, VM-26] | only if a frame-time probe shows a need; **unresolved** |
| Texture presets keyed to VRAM | Fits 8 GB cards | Current caps (1024 colour / 512 normal) were set for archive size, not VRAM; vanilla uses 3.8 GB (1080p ultra) to 5.7 GB (1440p max) on a 12 GB card in one test (VP W2-2) | **supported hypothesis** |

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
- [Added 2026-10-19] GOG Fallout 4 ships only 1.10.163.0, so GOG players need no downgrade (**verified**, gogdb.org, via launcher.md revision 2).
- Answer by: record and archive diff between 1.10.163, 1.10.984 and 1.11.240 data (VM-02), then owner decision.
- Blocks: Launcher, Release, New game.
- Status: **Owner answer, 2026-10-19:** decided by owner in the talk-through, 2026-10-19 (page LA-3): 1.10.163 now, add the current Steam version (1.11.240) after a record diff. Owner's note: "I'd like the most recent one, and then the one with the most mods, so it is easier for anybody bringing theirs over.". Before: open.

**VM-02. Did the next-gen and Anniversary updates change Fallout4.esm, the DLC .esm files or the BA2 archives, and which records?**
- Why it matters: if records differ, players build different games and the launcher's determinism gate (L4) fails across players. The Vault 111 cells and MQ101 may differ by player.
- Options: evidence so far: one guide replaces only Fallout4.exe (**verified**); another lists six depots (**verified** that it lists them); the downgrader detects DLC and patches "the modified files" (**supported hypothesis** that data changed). (also: versions-performance Q2, precedents Q4, Q30)
- Wave 2: for the BA2 archives, next-gen changed the header version to 7 or 8 (**verified**) and, by three independent readers, nothing else (**supported hypothesis**, VP W2-1); the .esm question is untouched.
- Answer by: hash and record-level diff (Mutagen or xEdit read-only) of the base and DLC masters from a 1.10.163 copy and a 1.11.240 install. PC probe.
- Blocks: Launcher, New game, All interiors, Release.
- Status: narrowed (wave 2): archives differ by version number only (supported hypothesis); master records still open [VP W2-1].

**VM-03. Do next-gen Fallout 4 BA2 archives use header versions the reader rejects (v7/v8)?**
- Why it matters: `ba2.py` raises `unsupported version` for anything but 1 to 3 (**verified**). Next-gen archives are v7 or v8 (**verified**, Nexus article 5844, xEdit, OpenMW), so the current reader cannot read a player's unmodified 1.10.984 or 1.11.x install.
- Options: accept `{1, 7, 8}` in `ba2.py` line 59 with the v1 layout (xEdit and OpenMW parse 7/8 exactly like v1, **verified**; that nothing else changed is a **supported hypothesis**); or require 1.10.163 archives. NifSkope needed the fo76utils fork for NG archives (VP W2 sources).
- Answer by: a synthetic v7/v8 fixture test (offline) for the code; first 8 bytes of each `Fallout4 - *.ba2` and `cc*.ba2` on a current install (a 1-minute PC probe) to learn which vanilla archives are 7 and which 8, and whether 1.11.x changed anything beyond next-gen.
- Blocks: Launcher, All interiors (any build on a current install).
- Status: answered (wave 2): yes, v7/v8; layout same as v1 (supported hypothesis); one-line fix; per-archive version list still needs the PC probe [VP W2-1, TC W2-6]. [Update 2026-10-19: fix on PR #394, not merged: draft PR #394 at 1825141 reads FO4 BA2 v7 and v8 with the v1 layout, with a synthetic test; detect lists archive versions and duplicate archive names; 368da05 makes detect refuse sTestFile INIs and report loose files in My Games Data.]

**VM-04. How does the launcher identify the Fallout 4 data version, store and language without the exe?**
- Why it matters: the converter never runs Fallout 4; the launcher note's "check its version" should check data (VP Corrections). Fallout London failed on a wrong Fallout4.esm size (**verified**, GameStar).
- Options: hash table of Fallout4.esm and each DLC .esm per version; BA2 header bytes; presence of Anniversary CC files; one hash table per language, or hash only language-neutral files and treat STRINGS separately (DC Q19; TTW requires English installs, **verified**). (also: versions-performance Q8, distribution-community Q19, precedents Q4)
- Wave 2: BA2 header bytes do tell next-gen (7/8) from old-gen (1) archives (**verified**, VP W2-1). Fallout 4 ships nine Steam languages (six voiced), so a per-language hash table has up to nine rows per version (DC W2-4, **verified**); see VM-39.
- Answer by: hashes from three installs (1.10.163, 1.10.984, 1.11.240) and one non-English install. PC probe plus community contacts.
- Blocks: Launcher, Release.
- Status: narrowed (wave 2): archive version byte is a verified signal; .esm hashes still open [VP W2-1, DC W2-4].

**VM-05. Do GOG, Epic and Microsoft Store / Game Pass Fallout 4 installs work as sources?**
- Why it matters: the converter needs only data, so the store may not matter, but layout, BA2 versions and runtime may differ. Epic cannot roll back (**verified**); Skyblivion and TTW reject some stores (**verified**).
- Options: Steam and GOG only (TTW, Skyblivion mix-and-match); any store whose data hashes match a known table.
- Answer by: file listing and hashes from a GOG, an Epic and a Game Pass install. Community contact. (also: versions-performance Q11, precedents Q8)
- Blocks: Launcher, Release.
- Status: **Owner answer, 2026-10-19:** decided by owner, 2026-10-19 (page LA-5): "Steam, then GOG; refuse others" (as recommended). Before: open.

**VM-06. Which Fallout 4 runtime is canonical for our synthetic test fixtures, and do we keep fixtures for more than one?**
- Why it matters: unit tests use synthetic fixtures; a per-runtime header and record fixture (BA2 v1 vs v7/v8, one changed record) catches an FO4 update offline without shipping game data.
- Options: 1.10.163 only; 1.10.163 + current. (also: versions-performance Q31, precedents Q30)
- Wave 2: a v7/v8 BA2 fixture differs from v1 only in the version field (**supported hypothesis**, VP W2-1), so the archive fixture is cheap; the record fixture still waits on VM-02.
- Answer by: offline tooling after VM-02 and VM-03.
- Blocks: Launcher, Release.
- Status: narrowed (wave 2): BA2 fixture shape known; record fixture open [VP W2-1].

**VM-39. Which Fallout 4 and Starfield language pairs does v1 support?** (new in wave 2)
- Why it matters: the hash tables (VM-04) and the support matrix (VM-36) grow with each language. Voiced in both games: EN, FR, DE, ES, JA; text-only in both: PL, PT-BR; Italian is voiced in FO4 but text-only in Starfield; RU and Traditional Chinese exist only for FO4; the Starfield CK is English only (**verified**, Steam store API). TTW requires English installs (**verified**).
- Options: English-only v1; English-first with string tables passed through for the five shared voiced languages (**supported hypothesis** as the cheapest plan that does not exclude most players, DC W2-4); all pairs.
- Answer by: one build test with a non-English FO4 STRINGS set (PC probe or community contact); owner decision. (also: distribution-community Q18, Q19)
- Blocks: Launcher, Release.
- Status: **Owner answer, 2026-10-19:** decided by owner, 2026-10-19 (page LA-8): "English first, pass through 4 more" (as recommended). Before: narrowed (wave 2): language data verified; policy open [DC W2-4].

### B. Creation Club and other official extras

**VM-07. Are the ~150 Anniversary Creation Club files (and the High-Res Texture Pack) inputs, ignored, or refused?**
- Why it matters: they change what "the player's Fallout 4" means; the Anniversary Edition bundles "over 150 pieces of Creation Club content" (**verified**, [Nexus news 15400](https://www.nexusmods.com/news/15400)). CC files and the HD pack broke Fallout London installs (**verified**). A commenter says CC skins use BA2 slots (**unresolved**).
- Options: ignore every `cc*.esl`; opt in per file; refuse to build while they are active.
- Answer by: owner decision; offline list of CC files from a current install.
- Blocks: Launcher, Release, World.
- Status: **Owner answer, 2026-10-19:** decided by owner in the talk-through, 2026-10-19 (page LA-6): opt in per file: the player picks which Creation Club files and the HD pack to convert (wider scope and more testing). Owner's note: "I want players to be able to pick the most recent version that uses those files, or a previous update; better that you talk it through.". Before: open.

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

**VM-10. Does a Starfield patch (or a save load, or the in-game Creations menu) reset Plugins.txt or `Starfield.ccc`, or re-order Creations?**
- Why it matters: 1.15.214 fixed "Creations load order restoration" (**verified**, [SteamDB 18285521](https://steamdb.info/patchnotes/18285521)); a reset would silently unload our plugins. Wave 2: players on 1.15.222 saw every plugin deselected in `Plugins.txt` on loading a save or opening the Creations load-order menu, with Vortex closed and also from plain Steam (**verified** reports, Oct 2025 to Apr 2026; trigger **unresolved**); separately MO2 2.5.2 disabled `SFBGS004.esm` and `ShatteredSpace.esm` until an updated `game_starfield.dll` (**verified**). That the game itself rewrites `Plugins.txt` when it reconciles Creations is a **supported hypothesis** (DC W2-1).
- Options: preflight re-checks load order after every Starfield version change; the smoke test re-checks `Plugins.txt` after the first save load; the test runner asserts the active plugin list in game, not only the file before launch; tell players not to use the in-game Creations menu.
- Answer by: diff Plugins.txt and `.ccc` before and after the next patch and before and after a save load. PC probe. (also: starfield-toolchain Q3; distribution-community Q7, Q8)
- Blocks: Launcher.
- Status: narrowed (wave 2): a non-patch reset path exists in player reports; trigger and patch behaviour open [DC W2-1].

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
- Status: **Owner answer, 2026-10-19:** decided by owner, 2026-10-19 (page LA-15): "Refuse until we list it as good" (as recommended). Before: open.

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
- Status: **Owner answer, 2026-10-19:** decided by owner, 2026-10-19 (page NG-22): "No promise before 1.0" (as recommended). Before: open. Precedent (engine-mechanics.md, precedents pass): Fallout London's 1.03 patch forced players to start a new game, so a save-compatibility plan is needed before anyone plays on our builds.

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
- Wave 2: SFSE's own README excludes MS Store/Game Pass, and only `sfse/PluginAPI.h` is MIT; the rest is "not under a permissive license", so SFSE is detected and linked, never bundled or mirrored (**verified**, LP W2-C). An SFSE plugin of ours may include `PluginAPI.h`.
- Answer by: list what each phase calls (door package, start, Pip-Boy) offline; owner decision recorded in decisions.md.
- Blocks: New game, Door animations, Fallout systems, People and story, Release.
- Status: **Owner answer, 2026-10-19:** decided by owner in the talk-through, 2026-10-19 (page NG-1): SFSE required; the game is blocked when a patch breaks SFSE (option B, not the recommendation). Our own small SFSE plugins where the older games need them; a full extender of our own only if those are not enough. Owner's note: "We might want to make our own script extender, because we will eventually need scripts from the older Fallouts to work.". Before: open (wave 2 confirmed the Game Pass cost of any SFSE dependency) [LP W2-C].

**VM-18. When a patch breaks SFSE plugins, what does each SFSE-dependent feature do?**
- Why it matters: decides whether a compiler-setting patch takes the whole port down or only some features.
- Options: degrade (hide the feature); block launch; Papyrus fallback. (also: starfield-toolchain Q21)
- Answer by: owner decision after VM-17.
- Blocks: Fallout systems, Release.
- Status: **Owner answer, 2026-10-19:** decided by owner in the talk-through, 2026-10-19 (page NG-1): SFSE required; the game is blocked when a patch breaks SFSE (option B, not the recommendation). Our own small SFSE plugins where the older games need them; a full extender of our own only if those are not enough. Owner's note: "We might want to make our own script extender, because we will eventually need scripts from the older Fallouts to work.". Before: open.

### D. Pinning, rollback and stores for Starfield

**VM-19. Which pin method does the launcher use for Starfield?**
- Why it matters: Steam auto-updates; a mid-session update breaks a built set. Player-run login downgrades are ruled out.
- Options: refuse on mismatch (current); MO2-style Stock Game copy (doubles disk use, **supported hypothesis**); Steam "update only when launched"; read-only `appmanifest` (Fallout London, **verified**); keep a backup exe. (also: versions-performance Q13, starfield-toolchain Q13)
- Answer by: owner decision plus offline research on what Steam allows.
- Blocks: Launcher, Release.
- Status: **Owner answer, 2026-10-19:** decided by owner, 2026-10-19 (page LA-16): "Refuse, advise 'update only when launched'" (as recommended). Before: open.

**VM-20. How does the launcher detect the Starfield version and store?**
- Why it matters: preflight and the support matrix depend on it.
- Options: exe file version; Steam `appmanifest`; presence of the `XboxGames` path; Starfield.exe hash table per build (DC Q9). (also: starfield-toolchain Q9)
- Answer by: one PC read; offline code. PC probe.
- Blocks: Launcher.
- Status: open.

**VM-21. Do we support Game Pass Starfield at all?**
- Why it matters: SFSE and MO2 do not run there; Vortex does via an ASI loader it calls outdated (**verified**). A data-only core might load there.
- Options: Steam-only v1 and say so; a no-SFSE build loaded through Plugins.txt and archives; later. (also: versions-performance Q27, starfield-toolchain Q24, distribution-community Q10)
- Wave 2: SFSE's README: "The MS Store/Gamepass version is not supported" (**verified**, LP W2-C). So the release page states "Steam Starfield only" whenever any phase needs SFSE (legal-policy wave 2 new question 2).
- Answer by: load the S9 test plugin on a Game Pass install (community contact); owner decision after VM-17.
- Blocks: Release, Launcher.
- Status: **Owner answer, 2026-10-19:** decided by owner in the talk-through, 2026-10-19 (page RE-12): Steam only for v1, said plainly; revisit if SFSE ever supports Game Pass. Owner's note: "I genuinely don't believe we'll be able to do this for console users, but if possible, then yes.". Before: narrowed (wave 2): any SFSE phase excludes Game Pass by SFSE's own statement; a data-only Game Pass build still untested [LP W2-C].

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
- Wave 2: the world core must use full masters (649,596 refs is about 10x a medium master's 65,536 ObjectIDs); medium masters fit interior clusters under 65k records (TC W2-5, inference from **verified** limits).
- Answer by: archive counts with Starfield Engine Fixes' counter on the owner's PC; plugins.txt counts from testers. PC probe plus community contact.
- Blocks: World, All interiors, Release.
- Status: narrowed (wave 2): plugin-type split fixed by the medium limit; archive count open [TC W2-5].

**VM-24. Can one archive pass 4 GiB, and how many numbered archives does a plugin auto-load (`- Main01.ba2`?)?**
- Why it matters: core64 needs about 8.5 GiB at full resolution; `<plugin> - Main.ba2` auto-loads (**verified**, repo S9), numbered ones are **unresolved**.
- Options: split by kind (Main/Textures); numbered archives; INI archive lists (avoid: Controlled Folder Access blocked Documents writes, **verified** repo).
- Wave 2: BA2 offsets are 64-bit (`FileTableOffset: Int64`, per-file `Offset: Int64`, **verified**), so the format does not stop at 4 GiB; FO4 users report 9.5 GB and 14.7 GB archives loading and Archive2 capping at "17.592 gig" (user reports, FO4 only). For Starfield's engine it stays **unresolved**; keep splitting at 4,095 MB until a probe loads one (VP W2-3, TC W2-6).
- Answer by: a synthetic 5 GiB archive and two numbered archives loaded in game (an S9-style spike). PC probe. (also: versions-performance Q4, starfield-toolchain Q14)
- Blocks: All interiors, World.
- Status: narrowed (wave 2): format limit ruled out; engine limit and numbered auto-load open [VP W2-3, TC W2-6].

**VM-25. What is the real medium master record limit, and should interiors or DLC areas be medium masters?**
- Why it matters: the type cannot be changed later. Wave 2: xEdit masks medium ObjectIDs with `$FFFF` and rejects any ID with bits in `$00FF0000`; `MaxMediumSlot` = `$FF`. So a medium master holds 0x0000-0xFFFF (at most 65,536, fewer after any reserved low range) and the MO2 "0xFF" is the slot count (**verified**, TC W2-5). Update plugins cannot hold new records (**verified**).
- Options: full ESM for the world core (it is about 10x a medium master); medium masters per interior cluster under 65k records; update plugins only for pure overrides (cost a slot since 1.12.30). (also: starfield-toolchain Q8, Q32, Q33)
- Answer by: load a synthetic medium master near 60,000 records to confirm the engine agrees with xEdit (PC probe); record counts per FO4 cluster (offline); owner decision.
- Blocks: All interiors, World.
- Status: **Owner answer, 2026-10-19:** decided by owner, 2026-10-19 (page IN-1, confirmed in the Interiors thread): the main plugins stay the normal (full) type; whether later small add-ons use the medium type is decided when there are any. Owner's note: "I agree. Just decide which ones need to be used when; don't force something on something that isn't needed, but make sure we implement the right thing before something is broken and needs to be completely redone." Before: answered (wave 2): 65,536 ObjectIDs, 256 slots; only the in-game check remains [TC W2-5].

**VM-26. Does Starfield have a precombine/previs equivalent our build could produce?**
- Why it matters: decides between writing our own merged meshes or finding an engine feature. FO4 relies on precombines (`SCOL\CM*.NIF`). Wave 2: FO4's CELL has `VISI`, `PCMB`, `XPRI`, `XCRI`; Starfield's CELL has none of them (**verified** schema, xEdit sf1.pas). An `OVIS` "Object Visibility Manager" record exists, purpose undocumented (**verified**). ~~CE2 has no FO4-style bake, so there is nothing to produce and nothing to break (**supported hypothesis**, TC W2-2).~~ [Correction 2026-10-19: that hypothesis is weakened by interiors.md T9 (both CK string dumps, PC job 18): the FO4 CK has `-GeneratePreCombined` and `-GeneratePreVisData`; the Starfield CK has neither switch but has the GUI actions "Generate Precombined Visibility for Current Cell" and "... All Loaded Cells". Starfield may have a precombined-visibility bake run from the CK GUI; what it writes and whether it matters for performance is **unresolved**. The Starfield CK also has `-GenerateCellAndRefCounts` (possibly per-cell reference counts; **unresolved**).]
- Options: accept the cost and measure (VM-27); merge static geometry per cell only if frame time demands it; reduce clutter.
- Answer by: frame-time measurement on a dense cell (VM-27); optionally read what vanilla `OVIS` records hold (offline). (also: versions-performance Q6, starfield-toolchain Q7)
- Blocks: All interiors, World.
- Status: ~~answered (wave 2): no precombine/previs equivalent to produce (supported hypothesis); downgraded to a frame-time measurement~~ [TC W2-2, VP W2-2]. [Correction 2026-10-19: narrowed, open: no FO4-style precombine/previs records (verified schema), but the Starfield CK's "Generate Precombined Visibility" GUI actions may be the equivalent; left: what they write, whether it matters for performance, and what `-GenerateCellAndRefCounts` does (interiors.md T9), plus the frame-time measurement (VM-27).]

**VM-27. What per-cell reference and draw-call budget keeps interiors at 60 fps on a minimum-spec GPU?**
- Why it matters: we place references one by one. Wave 2: Starfield's renderer builds draw arguments on the GPU and issues ExecuteIndirect (**verified**, vkd3d-proton PR 1694), so per-object CPU draw cost, the reason FO4 needed precombines, likely matters less; the cost of many references is likely in reference loading, scripts, Havok and streaming (**supported hypothesis**, VP W2-2). The game uses up to eight CPU cores; New Atlantis with many NPCs was the heaviest test scene (**verified**, DSOGaming). No source measures a dense modded cell.
- Options: as VM-26.
- Answer by: frame time and reference count in the densest FO4 interiors (Vault 111, Diamond City Market interior, Mass Fusion) with PresentMon or the game's overlay. PC probe. (also: versions-performance Q5)
- Blocks: All interiors.
- Status: narrowed (wave 2): draw submission is likely not the bottleneck; budget still unmeasured [VP W2-2].

**VM-28. Does an exterior with 650k+ references stream without traversal stutter?**
- Why it matters: Starfield Engine Fixes ships "Reduce Traversal Stutter" and "Increase File Handle Limit" (**verified** names), which suggests vanilla pain points (**supported hypothesis**).
- Options: accept; merged meshes; fewer references per cell.
- Wave 2: the likely cost is CPU-side reference loading and streaming, not draw calls (**supported hypothesis**, VP W2-2).
- Answer by: frame-time capture on a walking route over core64 (the route runner exists), at three fixed spots (dense downtown, open wasteland, interior), vanilla vs core vs core-with-LOD (VP W2-2 experiment). PC probe. (also: versions-performance Q18)
- Blocks: World.
- Status: narrowed (wave 2): where to look is known; numbers open [VP W2-2].

### F. Hardware, disk and build performance

**VM-29. What texture caps should the default build use per VRAM tier?**
- Why it matters: the 2026-10-12 caps (1024 colour / 512 normal) were set for archive size, not VRAM; no official VRAM figure exists (**verified**).
- Options: three presets keyed to detected VRAM.
- Wave 2: vanilla VRAM on a 12 GB RTX 3080 in one test: under 3 GB at 1080p low, 3.8 GB at 1080p ultra, 4.4 GB at 1440p low, 5.7 GB at 1440p max, about 6.5 GB at 4K ultra with FSR2 Ultra Performance (**verified**, single vanilla test, Noticias3D). Vanilla leaves headroom on the owner's 12 GB card; VRAM with our core loaded is **unresolved**. Corsair recommends 32 GB system RAM over 16 GB without published numbers.
- Answer by: VRAM use at each cap on an 8 GB card (community tester), and on the owner's PC with the caps halved (VP W2-2 experiment). (also: versions-performance Q20)
- Blocks: Launcher, Release.
- Status: narrowed (wave 2): vanilla baseline known; our added VRAM open [VP W2-2].

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
- Status: **Owner answer, 2026-10-19:** decided by owner, 2026-10-19 (page RE-5): "Engine Fixes' crash logger" (as recommended). Before: open.

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
- Wave 2: the matrix says "Steam Starfield only" whenever any phase needs SFSE (**verified** basis, LP W2-C), and lists the supported languages (VM-39).
- Answer by: owner decision after VM-01, VM-12 and VM-39.
- Blocks: Release.
- Status: **Owner answer, 2026-10-19:** decided by owner, 2026-10-19 (page RE-13): ""Use previous build"; no time promise" (as recommended). Before: open (wave 2 added the Steam-only and language lines) [LP W2-C, DC W2-4].

**VM-37. Who owns patch-day duty when the project is quiet?**
- Why it matters: both games are still moving; maintenance runs for years.
- Options: owner; the watchdog/Codex runbook carries detection and reporting only (no deploys or code changes).
- Answer by: owner decision. (also: versions-performance Q33)
- Blocks: Release.
- Status: **Owner answer, 2026-10-19:** decided by owner, 2026-10-19 (page RE-13): ""Use previous build"; no time promise" (as recommended). Before: open.

**VM-38. What is the real long-term cost, measured?**
- Why it matters: precedents took 5 years (Enderal, 14 people; Fallout London, about 100) to 13+ (Skyblivion, Skywind) (**verified**); converting is our structural advantage, but maintenance across two moving games adds cost.
- Options: measure hours per converted interior cell and per patch day now, then extrapolate.
- Answer by: owner plus QA, from docs/ai/optimization.md baselines. (also: precedents Q32)
- Blocks: Release, Multi-game.
- Status: open.

**VM-40. Keep FO4 dismemberment, which needs a small SFSE plugin, or drop it?** (new 2026-10-19)
- Why it matters: it is the largest single use of an FO4 engine native that Starfield lacks, and it is a concrete
  test of VM-17 (data-only core or SFSE).
- Evidence (**verified**, Mechanics job 34, read-only census of Starfield's ContentResources.zip against FO4's
  Scripts\Source\Base\Base.zip; research/engine-mechanics/papyrus-and-script-extenders.md on PR #404): 229 FO4 script
  functions are missing in Starfield; 36 are engine natives and 193 are Papyrus wrappers we can port as our own scripts.
  FO4's scripts call 25 of the 36 natives in 336 places: `actor.Dismember` (125 calls in 25 scripts), `actor.AddSpell`
  (Starfield declares it on ObjectReference), Pip-Boy and SPECIAL menus, `location.SetCleared` and `IsCleared`, and the
  workshop natives.
- Options: (a) keep it through a small SFSE plugin (an optional SFSE module under VM-17); (b) drop it and strip the
  calls in conversion.
- Answer by: owner decision. Blocks: People and story, Fallout systems (combat).
- Status: **Owner answer, 2026-10-19:** decided by owner, 2026-10-19 (page FS-6): "Keep it with a small SFSE plugin" (not the recommended option). Before: open; owner decision.

## Owner decisions in this area

Each line is a recommendation, not a decision.

- **VM-40 Dismemberment:** no recommendation yet; it follows VM-17 (if SFSE stays optional, keep it as an optional
  SFSE module and strip the calls otherwise).

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
- **VM-21 Game Pass:** recommend Steam-only for v1 and say so (SFSE itself excludes Game Pass, LP W2-C), revisit after
  a community Game Pass load test.
- **VM-25 Plugin types:** recommend full masters for the world core (about 10x a medium master) and medium masters only
  for interior clusters under 65k records, after one in-game load of a near-full synthetic medium master.
- **VM-39 Languages:** recommend English-first v1 with string tables passed through for EN, FR, DE, ES, JA, after one
  non-English test build.
- **VM-36 Support matrix and patch-follow promise:** recommend publishing the matrix line and "use the previous build
  until we post support", with no time promise until patch-day timing is measured.
- **VM-37 Patch-day duty:** recommend detection and reporting through the existing watchdog/Codex runbook, with
  fixes owned by Claude and approved by the owner.

## Cheapest experiments

Nothing here runs now; this is a list.

| # | Experiment | Kind | Closes |
|---|---|---|---|
| E0 | Synthetic v7 and v8 BA2 fixtures (v1 layout, version field changed) plus accepting `{1, 7, 8}` in `ba2.py` | Offline unittest, minutes | VM-03 (code side), VM-06 (archive fixture) |
| E1 | On one current Steam Fallout 4 install: read the first 8 bytes of every `Fallout4 - *.ba2` and `cc*.ba2` (which are v7, which v8), hash and size Fallout4.esm and each DLC .esm, list `cc*` files. Compare with the owner's 1.10.163 copy | PC read-only probe, minutes | VM-02 (first half), VM-03 (per-archive list), VM-04, VM-07 (inputs list) |
| E2 | Record-level diff of base and DLC masters between the two installs (Mutagen read-only) | Offline after E1 copies hashes/records | VM-01, VM-02, VM-06 |
| E3 | Scripted diff of every Starfield record we override (start quests, planet, worldspace) and every vanilla path we reference, against Starfield.esm of 1.16.236/.242/.244 | Offline tooling, reusable each patch day | VM-08, VM-09, VM-11, part of VM-34 |
| E4 | Synthetic load spike: one 5 GiB archive, two numbered `- Main01.ba2` archives, one medium master near 60,000 records (in-game check of the xEdit limit); read the Engine Fixes BA2 counter | PC probe (S9-style) | VM-23, VM-24, VM-25 |
| E5 | Frame-time capture (PresentMon + GPU counters) on the core64 walking route and at three fixed spots (dense downtown, open wasteland, interior): fps, frame time, VRAM, RAM; vanilla vs core vs core-with-LOD; repeat with texture caps halved | PC probe, route runner exists | VM-27, VM-28, VM-29 (owner tier), VM-26 (cost side) |
| E6 | Trigger the vault cart Havok assert with Trainwreck, then with Engine Fixes' logger | PC probe | VM-33 |
| E7 | 15-cell build under a memory cap and limited cores; record peak RSS, peak disk, time | Offline or cloud VM | VM-30, VM-31 |
| E8 | List every SFSE, Address Library or runtime-address call in the repo's door, start and bridge code | Offline repo read | VM-17, VM-18 |
| E9 | At the next Starfield patch: diff Plugins.txt and `Starfield.ccc`, read the CK exe version, load a 1.16.244 save | PC probe on patch day | VM-10, VM-13, VM-15 |
| E10 | In the next smoke run: diff `Plugins.txt` before launch, at the main menu and after the first save load | PC probe, minutes | VM-10 (save-load path) |
| E11 | Build once from a non-English Fallout 4 STRINGS set | PC probe or community tester | VM-39, VM-04 (language half) |

## Gaps (after wave 2)

- Which vanilla Fallout 4 archives are v7 and which v8, and whether 1.11.x (Anniversary) changed anything beyond
  next-gen (needs E1; the layout itself is answered, VP W2-1).
- Which .esm files and records changed in Fallout 4 1.10.98x and 1.11.x (patch notes, depot listings, community diffs).
- Fallout 4 runtime and data on GOG, Epic and Microsoft Store / Game Pass today. [Update 2026-10-19: GOG ships only 1.10.163.0 (**verified**, gogdb.org via launcher.md revision 2); Epic and Microsoft Store / Game Pass still open.]
- Starfield Steam depot IDs and whether older public builds are offered as beta branches.
- Measured frame time, reference streaming cost and VRAM with our core loaded (no source measures a dense modded cell;
  ~~the precombine question and~~ vanilla VRAM ~~are~~ [Correction 2026-10-19: is] answered, VP W2-2, TC W2-2).
- [Added 2026-10-19] What the Starfield CK's "Generate Precombined Visibility" GUI actions write and whether they matter for performance (VM-26, interiors.md T9).
- Whether Starfield's engine loads a BA2 over 4 GiB (format allows it, VP W2-3).
- What triggers the save-load `Plugins.txt` reset (DC W2-1).
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
findings/precedents.md, findings/legal-policy.md (wave 2, SFSE and Game Pass).

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

Wave 2:

- https://www.nexusmods.com/fallout4/articles/5844
- https://raw.githubusercontent.com/TES5Edit/TES5Edit/dev-4.1.6/Core/wbBSArchive.pas
- https://raw.githubusercontent.com/TES5Edit/TES5Edit/dev-4.1.6/Core/ (wbDefinitionsSF1.pas, wbDefinitionsFO4.pas, wbImplementation.pas, wbInterface.pas)
- https://gitlab.com/OpenMW/openmw/-/raw/master/components/bsa/ba2gnrlfile.cpp , ba2dx10file.cpp , ba2file.hpp
- https://gitlab.com/OpenMW/openmw/-/merge_requests/4055
- https://git.cijber.net/mirror/openmw/commit/a5d936993fb017f1c6bc17aecdc95e760c270edd
- https://forums.nexusmods.com/topic/13484961-solved-nifskope-and-next-gen-ba2-archives
- https://forums.nexusmods.com/topic/11091353-ba2-size-limits-and-splitting-textures-between-ba2s
- https://github.com/HansKristian-Work/vkd3d-proton/pull/1694
- https://www.destructoid.com/open-source-community-figures-out-problems-with-performance-in-starfield/
- https://www.dsogaming.com/pc-performance-analyses/starfield-pc-performance-analysis/
- https://www.noticias3d.com/noticia/92797/starfield-requisitos-4k-cuanta-memoria-grafica-consume.html
- https://www.corsair.com/us/de/explorer/diy-builder/memory/how-memory-capacity-affects-starfield/
- https://forums.nexusmods.com/topic/13524420-game-launch-deactivates-starfield-plugins/
- https://www.reddit.com/r/starfieldmods/comments/1g5jqca/mod_organizer_2_disabling_core_starfield_plugins/
- https://github.com/ModOrganizer2/modorganizer/issues/2325
- https://store.steampowered.com/api/appdetails?appids=377160
- https://store.steampowered.com/api/appdetails?appids=1716740
- https://store.steampowered.com/api/appdetails?appids=2722710
- https://raw.githubusercontent.com/ianpatt/sfse/master/LICENSE
- https://github.com/ianpatt/sfse
