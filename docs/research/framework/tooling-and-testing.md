# Tooling and testing

Part of the [next-phase framework](README.md). Waves 1 and 2, 2026-10-19. Sources: findings/starfield-toolchain.md,
findings/testing-qa.md, findings/versions-performance.md (tooling parts), findings/precedents.md (Skywind QA rules,
wave 2). What the project already does is in research/next-phase/testing-automation.md and is not repeated here.
Wave 2 items are cited as, for example, **ST W2-5** (the `## Wave 2 additions` section of that finding).

Shorthand for cross-references: **ST** = findings/starfield-toolchain.md, **QA** = findings/testing-qa.md,
**VP** = findings/versions-performance.md, **PR** = findings/precedents.md, **TA** =
research/next-phase/testing-automation.md. Labels: **verified**,
**supported hypothesis**, **unresolved**, as in the findings.

## In short

- The toolchain is alive and tracks the game. Starfield 1.16.244 (11 June 2026) is still current; SFSE 0.2.21 shipped
  the same day; Mutagen ships weekly; Spriggit has a Starfield package. The weak spot is lip sync (FaceFX), a CK step
  with no documented batch path. Wave 2: ~~object LOD has a CK command-line switch (`-MockWorldSpaceLOD`, ST W2-1)~~
  [Correction 2026-10-19: ~~whether `-MockWorldSpaceLOD` exists is **unresolved (sources conflict)**~~: web guides say it
  does, ~~but a string dump of the installed CreationKit.exe (job 18) does not show it~~ [Correction 2026-10-19: the
  job 18 dump printed only strings matching its default patterns (Generate, Compile, Lip, AnimInfo, -Convert, -Build),
  so it had filtered the switch out; job 20 (read-only, patterns Mock, WorldSpaceLOD and "Should be -") found it:
  `-MockWorldSpaceLOD` is **verified (Starfield CK, job 20)**, not in the FO4 CK, usage
  "-MockWorldSpaceLOD:(ESMFilename) (WorldSpaceName0) [WorldSpaceName1] [...]"]; the dump does show
  `-GenerateMeshLOD*` switches (**verified**). Lip sync: the Starfield CK has `-CompileFaceFXAnims` plus
  `Tools\LipGenerator\LipGenerator.exe` (**verified**, job 18).], and
  CE2 has no precombine/previs records at all (ST W2-2), ~~so there is no bake step to replicate~~ [Correction
  2026-10-19: but the Starfield CK has the GUI actions "Generate Precombined Visibility for Current Cell" and "... All
  Loaded Cells" (interiors.md T9, job 18), so a precombined-visibility bake from the CK GUI may exist; what it writes
  and whether it matters for performance is **unresolved**].
- For in-game automation we are ahead of every public total conversion; they test with people. Where the ecosystem is
  ahead of us: SFSE crash loggers with crash signatures, Spriggit record diffs, Starfield's own `Debug` test functions,
  Skywind's bug lifecycle, and a repeatable PresentMon performance protocol.
- Most uncertain: which `Debug` functions work in retail, whether CK batch navmesh, object LOD and FaceFX run
  unattended on our plugins, and whether Starfield's engine reads archives over 4 GiB. Wave 2 settled the medium master
  limit (65,536 ObjectIDs, ST W2-5) and showed that Fallout 4 next-gen BA2s (v7/v8) differ only in the version number
  (supported hypothesis, VP W2-1), a one-line reader fix. xEdit `-checkforerrors` gives an unattended build gate with an
  exit code (QA W2-1).
- Decisions that unlock the most: (1) a **data-only core** as the maintenance strategy (TT-04), which sets how much
  SFSE and per-patch native code we carry; (2) **which crash logger** we run and ship (TT-23); (3) **adopt Spriggit**
  as a tier-0 validator and diff tool, and where its snapshots live (TT-15).

## What is settled

| Fact or decision | Label | Source |
|---|---|---|
| SFSE and the free Starfield Creation Kit MAY be required of players. | owner decision | findings/BRIEF.md |
| GitHub release first, then Nexus, with a GPL-3 notice for Mutagen. | owner decision | findings/BRIEF.md |
| The launcher never asks for store credentials, so no credential-based downgrade. | owner decision | repo docs/ROADMAP.md C1 (ST section 8) |
| Development pins: Starfield 1.16.244 + SFSE 0.2.21, Steam only; Fallout 4 1.10.163. | verified (repo) | docs/SETUP.md, docs/PLAY-AND-TEST.md (VP) |
| 1.16.244 is still the newest Starfield on 2026-10-19; SFSE 0.2.21 came the same day. | verified | [starfield.gg](https://starfield.gg/starfield-latest-update/), [SFSE Nexus 106](https://www.nexusmods.com/starfield/mods/106) |
| SFSE supports only the latest Steam runtime, not Game Pass, Windows Store or EGS. | verified | [sfse.silverlock.org](https://sfse.silverlock.org/), [SFSE Nexus 106](https://www.nexusmods.com/starfield/mods/106) |
| SFSE co-save serialization has been disabled since 0.2.12 and not re-enabled. | verified | [sfse_whatsnew](https://raw.githubusercontent.com/ianpatt/sfse/master/sfse_whatsnew.txt) |
| 1.15.216 compiler changes invalidated the Address Library and most SFSE plugins. | verified | sfse_whatsnew (SFSE 0.2.17) |
| Medium masters exist (256 in FD, about 65,535 records each); 253 full; 4,096 small (4,095 records). | verified | [Nexus news 14993](https://www.nexusmods.com/news/14993), [LOOT changelog](https://loot.readthedocs.io/en/0.24.1/app/changelog.html) |
| Two more plugin kinds: update plugins (formerly overlay, take a load-order slot since 1.12.30) and blueprint masters. | verified | LOOT changelog, [MO2 BPM Nexus 17318](https://www.nexusmods.com/starfield/mods/17318) |
| CreationKit.exe carries navmesh batch switches (`-UpdateNavmeshGeneration`, `-FinalizeNavmeshes`, `-UpdateNavmeshFinalization:<esm>`, `-Part`, ...). Strings only, never run. | verified (repo) | docs/actors/npc-navigation.md section 2.4 |
| FaceFX lip sync is a CK menu (Audio > Run FaceFX Compiler); WAV in, `.ffxanim` out; slow on large batches. | verified | [starfieldwiki Audio File Conversion](https://dev.starfieldwiki.net/wiki/Starfield_Mod:Audio_File_Conversion) |
| xEdit (SF1Edit 4.1.5q, Discord-only) cannot create update files or save blueprint-master modules. It is an oracle, not a writer. | verified (limits); inference (role) | [reddit snapshot](https://reddit.sentinel-team.org/posts/1u6jz38/snapshots/2026-06-16T07%3A02%3A42.6264Z) |
| `Debug.TraceUser` works in retail (our bridge depends on it), so the wiki's "whole Debug script is DebugOnly" is wrong at least there. | verified (repo) | scripts/bridge/FO4SF_Probe.psc:21, scripts/game/bridge_log.py (QA Corrections) |
| BA2 engine limit: 256 active archives (8-bit index). | verified | [Nexus 17936](https://www.nexusmods.com/starfield/mods/17936) |
| The repo's BA2 reader accepts header versions 1 to 3 only. | verified (repo) | src/fo4sf/ba2.py:59 (VP) |
| Medium master: ObjectIDs 0x0000 to 0xFFFF (at most 65,536), 256 medium slots; the MO2 page's "0xFF" is the slot count. Light: mask `$FFF`. | verified (xEdit source) | ST W2-5, wbImplementation.pas 5219, 2464-2468; wbInterface.pas 22600 |
| Update-flagged plugins cannot hold new records (override-only). | verified (xEdit source) | ST W2-5 |
| The CK builds object LOD from the command line: `CreationKit.exe -MockWorldSpaceLOD:<Plugin>.esp <Worldspace>,...`; objects chosen by the layer's LOD checkbox; some cells may fail in multi-cell worldspaces. | ~~verified~~ [Correction 2026-10-19: ~~**unresolved (sources conflict)**~~: web guides say it exists; ~~a keyword-filtered string dump of the installed CreationKit.exe (job 18, `D:\Modding\research\ck_switches_1.txt`) does not show it, though it does show other "WorldSpace" strings; it may be a wide string the filter missed, or absent in the current CK~~] [Correction 2026-10-19: **verified (Starfield CK, job 20)**: the job 18 dump printed only strings matching its default patterns (Generate, Compile, Lip, AnimInfo, -Convert, -Build), so it had filtered the switch out (the other "WorldSpace" strings appeared only because they also contain "Generate"); job 20 (read-only, patterns Mock, WorldSpaceLOD and "Should be -") shows it in the Starfield CK, not in the FO4 CK, usage "-MockWorldSpaceLOD:(ESMFilename) (WorldSpaceName0) [WorldSpaceName1] [...]" (an ESM filename)] | ST W2-1, job 20, [modding.wiki](https://modding.wiki/en/starfield/developers/tutorials/creatingworldspacelod), [forum 13497519](https://forums.nexusmods.com/topic/13497519-how-to-create-lod/) |
| LOD membership is plugin data: LAYR `LODB` (Default / Aggregate / No LODs), "Has Distant LOD" / "Is Full LOD" flags, `BGSLodOwner_Component`. | verified (schema) | ST W2-1, sf1.pas 13330-13339 |
| [Added 2026-10-19] Starfield CreationKit.exe LOD-related switches in the string dump: `-GenerateMeshLODAssociations`, `-GenerateMeshLODFailureReport`, `-GenerateMeshLODStats`. Strings only, never run. | verified | PC string dump, job 18 (`D:\Modding\research\ck_switches_1.txt`) |
| [Added 2026-10-19] Starfield CK has no `-GenerateLips`; its lip path is `-CompileFaceFXAnims` plus `Tools\LipGenerator\LipGenerator.exe` (job 19 queued for LipGenerator's usage text). The FO4 CK has `-GenerateLips` and `-GenerateSingleLip`. Neither CK has a script-compile switch; `PapyrusCompiler.exe` does that, headless. | verified | job 18 |
| [Added 2026-10-19] `-GenerateSEQ` exists in the Starfield CK. | verified | job 18 |
| [Added 2026-10-19] Starfield CK switches: `-CheckInPlugin`, `-DepersistRefs`, "-ExportESM:(ESMFilename) (output folder) [raw] [--progress]", "-ExportFaceGenData:(ESMFilename) (TESNPCExportFaceDataMode) [Platform]", `-ImportScalingData`, "-RunValidationSuite:(ESMFilename) (ValidationSuiteName)[:[TestName1],...]", `-SaveDefaultPlugin`; still no precombined or previs switch (only the GUI actions). FO4 CK: "-ExportFaceGenData:(ESMFilename) (XB1\|X64\|PS4\|W32)", `-GeneratePreCombined`, `-GeneratePreVisData`, `-GenerateStaticCollections`, `-MapInfo`, "-MapMaker:(ESMFilename) (Worldspace\|Interior)", `-UpdateModelData`, "-GenerateSingleLip:"WAVFilePath" "Text"". Strings only, never run. | verified | PC string read, job 20 |
| [Added 2026-10-19] Starfield's archives ship 0 `.facefx` files and 278,582 per-line `.ffxanim` lip files; LipGenerator.exe's required `actor.facefx` and `actoranalysis.facefx` inputs are not in the shipped data (where they come from is unresolved). | verified | job 21 |
| Terrain edits reach the game only via an exported `.btd`; our pipeline already writes BTD. | verified | ST W2-1, [Steam guide 3385012985](https://steamcommunity.com/sharedfiles/filedetails/?id=3385012985) |
| xLODGen/DynDoLOD do not list Starfield. | verified | [dyndolod.info](https://dyndolod.info/Help/xLODGen) |
| Starfield CELL has no `VISI`/`PCMB`/`XPRI`/`XCRI` (FO4's previs/precombine subrecords); an `OVIS` record of unknown purpose exists. ~~No precombine bake in CE2 is a supported hypothesis.~~ [Correction 2026-10-19: weakened: the FO4 CK has `-GeneratePreCombined` and `-GeneratePreVisData`; the Starfield CK has neither switch but has the GUI actions "Generate Precombined Visibility for Current Cell" and "... All Loaded Cells", so it may have a precombined-visibility bake run from the CK GUI; what it writes and whether it matters for performance is unresolved. It also has `-GenerateCellAndRefCounts` (possibly per-cell reference counts; unresolved).] | verified (schema); ~~bake absence supported hypothesis~~ [Correction 2026-10-19: bake **unresolved**] | ST W2-2; interiors.md T9 (job 18) |
| Fallout 4 next-gen BA2s are header versions 7 and 8; xEdit and OpenMW read them with the v1 layout; xEdit writes FO4 v1. | verified (versions); same layout is supported hypothesis | VP W2-1, [Nexus FO4 article 5844](https://www.nexusmods.com/fallout4/articles/5844), [OpenMW MR 4055](https://gitlab.com/OpenMW/openmw/-/merge_requests/4055) |
| BA2 file-table and per-file offsets are 64-bit; the format does not stop at 4 GiB (engine limit for Starfield unresolved). | verified (format) | ST W2-6, VP W2-3, wbBSArchive.pas 54, 75 |
| xEdit tool modes include `checkforerrors`, `checkforitm`, `checkfordr`: unattended, never save, exit code = error count capped at 127. Still a GUI window, not headless; full CLI automation declined by the xEdit team. | verified (xEdit source) | QA W2-1, [What's New](https://tes5edit.github.io/docs/18-whatsnew.html), [issue 655](https://github.com/TES5Edit/TES5Edit/issues/655) |
| SF1Edit's first start builds reference info: 4 to 5 GB RAM, over 10 minutes; later starts load the cache in seconds. | verified | QA W2-1 (What's New 18.15.1.2.1) |
| sf-crash-logger: v0.1.0 (16 Jun 2026) to v0.4.0 (10 Jul 2026); version-stable 8-hex signature only since v0.4.0; raw `__fastfail` cannot be caught by any plugin. | verified | QA W2-4, [releases](https://github.com/0xra0/sf-crash-logger/releases) |
| Spriggit translation packages are fetched from NuGet at run time and each text tree is stamped with the package version; upgrades are a dedicated `upgrade` commit. | verified | QA W2-3, [translation packages](https://mutagen-modding.github.io/Spriggit/translation-packages/) |
| Synthesis `main` creates Starfield profiles as masters and pins Mutagen 0.54.4. | verified | ST W2-4 |
| No public tool writes or merges `materialsbeta.cdb`; community uses loose `.mat` JSON. SFME (open source) reads the CDB. | supported hypothesis (no writer); verified (SFME reads) | ST W2-3 |
| Already built or planned (do not redo): one runner (testqueue.py) with generated plans, tiers 0 to 3, crash budget, disk floor, plugin toggle, FO4SF_Probe.Stage, regress.py, preflight report. | verified / proposal | TA sections 1, 2, 6 |

## Possibilities

### Versions and patch day

| Option | What it gives | Cost or risk | Precedent | Label |
|---|---|---|---|---|
| Pin and refuse on mismatch (current preflight `game_version` gate) | No undefined state | Players wait after each patch | GAMMA-style pinning (general knowledge) | verified (gate exists, VP Q12); precedent unresolved |
| MO2-style "Stock Game" copy | Version stays frozen "even if an update is released" | Doubles disk (about 100+ GB) | [ejams1 guide](https://github.com/ejams1/starfield-modding-guide) | verified (copy keeps version); disk is supported hypothesis |
| Player-run downgrader (xdelta, no login) | Players can roll back | We would maintain patches | FO4 universal downgrader ([Steam thread](https://steamcommunity.com/app/377160/discussions/0/685239894022330731/)) | verified for FO4 |
| Watch Steam `beta` branch | Warning before a patch | Someone must watch | 1.15.214 was public beta first ([r/Starfield mirror](https://twt.omada.cafe/r/Starfield/comments/1kg7k32/starfield_update_115214_may_6_2025_beta)) | verified |
| Automated patch-day regression run | Fast "still works" signal | Needs the runner free | none public | proposal |

### Creation Kit and CK-only steps

| Option | What it gives | Cost or risk | Precedent | Label |
|---|---|---|---|---|
| CK navmesh batch command line | Navmesh for 1,000+ interiors without hand work | May not load plugin worldspaces/terrain | `-Part <part> <count>` suggests a build farm | verified (strings); behaviour unresolved |
| FaceFX via CK GUI per plugin | Documented lip sync | Slow; manual; about 123k lines | starfieldwiki, [Nexus guide 12576](https://nexusmods.com/starfield/mods/12576) | verified |
| FaceFX by a CK switch | Batch lip sync | ~~Not known to exist~~ [Correction 2026-10-19: `-CompileFaceFXAnims` exists, plus `Tools\LipGenerator\LipGenerator.exe`; behaviour not yet run (job 19 queued for LipGenerator's usage text)] | job 18 | ~~unresolved~~ [Correction 2026-10-19: verified (switch and tool exist); batch behaviour unresolved] |
| CK as oracle (load our ESM, scrape log) | Independent validation | Owner time per load | PLAN L2 (ST Q5) | proposal |
| CK `-MockWorldSpaceLOD` object LOD on the player's PC | Object LOD with no hand work | Partial-cell failures in multi-cell worldspaces; `.esm` acceptance and 64-cell run time unknown | modding.wiki tutorial, forum 13497519 (ST W2-1) | ~~verified (switch)~~ [Correction 2026-10-19: ~~**unresolved (sources conflict)**: not in the job 18 string dump of CreationKit.exe~~] [Correction 2026-10-19: **verified (Starfield CK, job 20)**; the job 18 dump's filter patterns had filtered it out; usage "-MockWorldSpaceLOD:(ESMFilename) (WorldSpaceName0) [WorldSpaceName1] [...]"]; unattended use is supported hypothesis |
| Converter writes LAYR `LODB` and object LOD flags | CK LOD run picks the right objects without layer clicks | We map FO4 LOD data to them | none | verified (schema); approach is proposal |
| Own `.btd`/`.lod` writer | LOD without CK | No public object-LOD writer; terrain `.btd` we already write | none | unresolved (object LOD) |

### SFSE and native code

| Option | What it gives | Cost or risk | Precedent | Label |
|---|---|---|---|---|
| Data + Papyrus only core | Survives patches; possible Game Pass tier | Fewer capabilities | USFP, data mods | supported hypothesis |
| Own SFSE plugin per runtime | Native hooks (menus, Scaleform 0.1.3) | Rebuild each compiler-change patch; no co-save | 1.15.216 broke most plugins | verified (risk) |
| Third-party SFSE plugins (BA2 Limit Fix, Engine Fixes) | Raise limits, extra diagnostics | Lag per patch | Nexus 17936, [Nexus 10457](https://www.nexusmods.com/starfield/mods/10457) | verified |

### Record tools and diffs

| Option | What it gives | Cost or risk | Precedent | Label |
|---|---|---|---|---|
| Mutagen pinned stable (0.54.4) | Fewer surprises | Misses 0.55 fixes | [NuGet](https://www.nuget.org/packages/Mutagen.Bethesda.Starfield) | verified (versions) |
| Spriggit `serialize` snapshots per build | Per-record, per-field diffs; Linux CLI; CI with "Known Masters" | Omitted fields reset; text may contain FO4 content; size for 683k records; package fetched from NuGet at run time, so offline CI needs a local cache and a pinned version (QA W2-3) | [Spriggit](https://github.com/Mutagen-Modding/Spriggit), [CLI](https://mutagen-modding.github.io/Spriggit/cli/), [upgrade practices](https://mutagen-modding.github.io/Spriggit/upgrade-practices/) | verified (tool); scale unresolved |
| Spriggit `standardize` or Mutagen round trip as tier-0 validator | Independent parser check | Not byte-identical by design ([omissions](https://mutagen-modding.github.io/Spriggit/omissions/)) | none | verified (feature) |
| xEdit `-checkforerrors` (also `-checkforitm`, `-checkfordr`) | Community's de-facto validator as a build gate: exit code = error count (max 127) | Opens a window (not headless); Windows only, Wine on Linux CI untested (needs Xvfb at least); first SF1Edit start 4 to 5 GB RAM and 10+ minutes, so keep a persistent cache (`-C:`) | xEdit source dev-4.1.6 (QA W2-1) | verified (mode, exit code); CI use is supported hypothesis |
| SFME as a material oracle | Decode vanilla materials to compare with our generated `.mat` | Reader only, last release Dec 2023 | [SFME](https://github.com/maximusmaxy/SFME), [Nexus 7830](https://www.nexusmods.com/starfield/mods/7830) (ST W2-3) | verified (reads CDB); use is proposal |

### In-game automation

| Option | What it gives | Cost or risk | Precedent | Label |
|---|---|---|---|---|
| Starfield `Debug` functions (`CenterOnCellAndWait`, `PlayerMoveToAndWait`, `QuitGame`, `ExecuteConsole`, `AutomatedTestLog*`, `StartScriptProfiling`, `DumpAliasData`) | Fewer keystrokes and whitelist decisions | May be DebugOnly no-ops in retail | [wiki Script-Debug](https://dev.starfieldwiki.net/wiki/Starfield_Mod:Script-Debug) | verified declared; retail unresolved |
| Papyrus remote debugger (port 20548) as read channel | Reads state with no game input | Untried by anyone found | [VS Code debugging page](https://starfieldwiki.net/wiki/Starfield_Mod:Debugging_Papyrus_with_VS_Code) | verified settings; use is supported hypothesis |
| `bAlwaysActive=1`, `bPauseOnAltTab=0` | Game keeps running unfocused | None known | same page | verified (settings) |
| AutoTest-style camera spin after coc | Loads every direction; catches mesh CTDs in smoke | Time per cell | [AutoTest](https://github.com/Muriel-Salvan/AutoTest) | verified (precedent) |
| AutoTest-style NPC portrait sheet | Catches neck gaps, black faces | Needs actors converted | same | verified (precedent) |
| Lilac-style Papyrus unit tests | In-engine tests of our scripts | Port effort; no Starfield port known | [Lilac FO4](https://www.nexusmods.com/fallout4/mods/18410), MIT | verified (FO4); Starfield unresolved |
| `sStartingConsoleCommand` bat | Unattended start-up commands | Must sit in `[General]`; chained bats unreliable | [Nexus forum guide](https://forums.nexusmods.com/topic/13253886-guide-how-to-properly-merge-mods-fixes-bat-files-sstartingconsolecommand-not-always-working) | verified (forum reports) |
| Screenshot diff per cell | Scales visual review | No Bethesda-world tool; noise floor unknown | none | unresolved |

### Crash diagnosis

| Option | What it gives | Cost or risk | Precedent | Label |
|---|---|---|---|---|
| sf-crash-logger (GPL-3) | Minidump, 8-hex signature (version-stable since v0.4.0: exception code, access type, Address Library IDs of fault site and three callers), stack-overflow reports, load order | Young: four releases in one month (to v0.4.0, 10 Jul 2026), one maintainer, measured under Wine 11.7; guarded reads did not catch access violations before v0.4.0 | [GitHub](https://github.com/0xra0/sf-crash-logger), [releases](https://github.com/0xra0/sf-crash-logger/releases) (QA W2-4) | verified (features, history) |
| Trainwreck v1.4.0 | Call stacks, module SHA512; claims all versions; SFSE or ASI | Not updated since Jan 2024; licence unread | [Nexus 5068](https://www.nexusmods.com/starfield/mods/5068) | verified (features) |
| Starfield Engine Fixes Detailed Crash Logger | Supports 1.16.244; handle dump; BA2 counter | Pinned per runtime | [Nexus 10457](https://www.nexusmods.com/starfield/mods/10457) | verified |
| Crash Logger SSE (Skyrim) as a reference | Shows where a mature logger goes: `__fastfail` via VEH, stack-overflow survival, navmesh/NIF introspection | Skyrim only | [CrashLoggerSSE releases](https://github.com/alandtse/CrashLoggerSSE/releases) (QA W2-4) | verified |
| ProcDump/WER (current) | Full detail | 17 to 18 GB per dump; Havok `HK_ASSERT` int3 leaves no WER entry | docs/JOURNAL.md 2026-10-16 | verified (repo) |

### Performance

| Option | What it gives | Cost or risk | Precedent | Label |
|---|---|---|---|---|
| PresentMon CLI on a fixed route, 4 passes, variance band | Comparable numbers per build | Runner time | [Gamers Nexus](https://gamersnexus.net/cpus-game-benchmarks-graphics-guides/starfield-cpu-benchmarks-bottlenecks-intel-vs-amd-comparison) | verified (method) |
| Engine Fixes handle and BA2 counters | Early warning on engine ceilings | SFSE dependency | Nexus 10457 | verified (features) |
| Fixed-spot probe: 3 spots (dense downtown, open wasteland, interior), PresentMon plus GPU counters, VRAM and RAM; vanilla vs core vs core-with-LOD; repeat with texture caps halved | Separates ref-loading cost from rendering and texture cost | Runner time | vanilla VRAM baseline: under 3 GB at 1080p low to about 6.5 GB at 4K ([Noticias3D](https://www.noticias3d.com/noticia/92797/starfield-requisitos-4k-cuanta-memoria-grafica-consume.html), single test) (VP W2-2) | verified (baseline); experiment is proposal |
| `SetLocalTime` jumps instead of high timescale | Avoids physics breaking under fast-forward | none known | EA SEED ([arXiv 2307.11105](https://arxiv.org/pdf/2307.11105)) | verified (EA finding); transfer is supported hypothesis |

### Navmesh validation

| Option | What it gives | Cost or risk | Precedent | Label |
|---|---|---|---|---|
| CK Pathing Tests | Green/yellow path between two triangles | Manual only | [ck.uesp Pathing Tests](https://ck.uesp.net/wiki/Pathing_Tests) | verified (Skyrim CK, inference for SF) |
| CK finalize | Flags or deletes failing triangles | Advanced finalize deletes triangles | [Nexus FO4 article 4209](https://www.nexusmods.com/fallout4/articles/4209) | verified (FO4 CK) |
| Own offline reachability checker over converted NAVM | Scales to every cell, tier 0 | We build it | none | proposal |

### Community testing

| Option | What it gives | Cost or risk | Precedent | Label |
|---|---|---|---|---|
| Skywind lifecycle labels (Confirmed, In Progress, Claim Fixed, Fix Fail, Invalid Issue, Known Shippable, a Crash label, department labels; "Do NOT close the issue", QA verifies the fix) | Fix closes only after a later build's retest | Label overhead | [Skywind bug reporting](https://handbook.tesrskywind.com/qa/bug-reporting) (PR W2-5) | verified |
| Dated "not finished, do not report" list per tester build; one issue per root cause, keep the most complete duplicate | Fewer noise reports | Upkeep per build | [Skywind QA FAQ](https://handbook.tesrskywind.com/qa/frequently-asked-questions) (QA W2-2) | verified (precedent) |
| Automated per-cell report gates what humans see (Skywind's LD Review tool: nothing may be Fail, Review items get attention) | Human time goes to flagged cells | Its checks are not described | Skywind QA FAQ, onboarding (QA W2-2) | verified (exists); our testqueue as the analogue is supported hypothesis |
| "QA Blocked vs Fail" triage split (collision mismatch is a 3D fault, gaps and z-fighting are level design) | Maps onto converter-bug vs placement-bug triage | Needs a collision check per report | [Skywind QA Fixes Guide](https://handbook.tesrskywind.com/qa/qa-fixes-guide) (QA W2-2) | verified (precedent); mapping is supported hypothesis |
| Clean test profile (game + SFSE only) | Usable reports | Tester discipline | [Skywind onboarding](https://handbook.tesrskywind.com/qa/onboarding) | verified |
| Closed beta with fixed cadence | Controlled feedback | Community management | SS2 Patreon beta, 7 to 10 days ([Patreon](https://www.patreon.com/posts/24469236)) | verified |
| 1-on-1 support sessions | Rescues failing installs | Owner time | Fallout London ([PC Gamer](https://pcgamer.com/games/rpg/fallout-london-devs-are-working-on-a-huge-patch-offering-dedicated-1-on-1-troubleshooting-sessions-to-help-players-with-installs-and-crashes)) | verified |
| Hash-based `verify` plus environment preflight | Catches environment faults TTW missed | Manifest upkeep | TTW checks folder size only ([TTW FAQ](https://thebestoftimes.moddinglinked.com/faq.html)) | verified (TTW gap) |

## Questions

### Versions, pinning and patch day

**TT-01. What does the launcher do when Steam updates Starfield, and what support matrix do we print?**
- Why it matters: SFSE supports only the latest Steam runtime, so a patch forces update-both or roll-back-both.
- Options: refuse until SFSE and we publish support (current gate); Stock Game copy; guide a `download_depot` rollback
  (unresolved, and credentials are ruled out); stop Steam auto-update (player's setting). One-line matrix on the
  release page (VP Q25). (also: ST Q1, ST Q13, VP Q12, VP Q13, VP Q25, QA Q22)
- Answer by: owner decision, informed by the measured patch-day timeline (SFSE same day in 2026).
- Blocks: Launcher, Release.
- Status: open.

**TT-02. What is the patch-day checklist, is it automated, and who owns it?**
- Why it matters: patches renamed mesh paths (1.11.36), changed the root form class (1.14.70), broke SFSE plugins
  (1.15.216) and changed planet data storage (USFP 1.0.7a/b).
- Options: re-run SFSE/Address Library check, NifSkope loads a vanilla mesh, Mutagen reads the Starfield.esm header,
  our plugin loads, vanilla path hash list (door clips included), Plugins.txt and `Starfield.ccc` diff, record diff of
  our overridden Starfield records, S1/S2/S9 smoke routes, post to #32. Watchdog/Codex runbook could carry detection.
  (also: ST Q3, ST Q4, ST Q31, VP Q19, VP Q26, VP Q29, VP Q33)
- Answer by: offline design; time one full smoke chain on PC; owner names the owner and the follow-up promise.
- Blocks: Release, World, Launcher.
- Status: open.

**TT-03. Can we keep a previous-runtime profile and watch the `beta` branch?**
- Why it matters: reproduce reports from players who have not updated; get warning before a patch.
- Options: Steam beta branch (older public builds as branches unresolved); depot download; exe copy.
  (also: VP Q28, VP Q30)
- Answer by: offline research on Steam branches; PC probe.
- Blocks: Release.
- Status: open.

**TT-04. Is a data-only core the long-term maintenance strategy?**
- Why it matters: everything exe-bound breaks on patches; data breaks less often and a diff catches it. It also
  decides whether a no-SFSE Game Pass tier is possible.
- Options: data + Papyrus with SFSE optional; SFSE plugins per runtime (CommonLibSF + Address Library); a policy per
  system for when SFSE breaks (degrade, block launch, Papyrus fallback). (also: VP Q32, VP Q21, VP Q23, ST Q21)
- Answer by: owner decision, recorded in docs/ai/decisions.md.
- Blocks: Fallout systems, People and story, Release, Multi-game.
- Status: open.

**TT-05. Do saves survive a Starfield patch with our plugins loaded?**
- Why it matters: long playthroughs span patches.
- Options: test save on 1.16.242, load on 1.16.244 (both on Steam depots).
- Answer by: PC probe. (also: VP Q22)
- Blocks: Release.
- Status: open.

**TT-06. Do we need per-runtime Fallout 4 test fixtures, and does the BA2 reader need v7/v8?**
- Why it matters: most players run Fallout 4 1.11.240; `ba2.py` accepts versions 1 to 3 only; next-gen headers being
  7/8 is **unresolved** (from memory). Unit tests use synthetic fixtures.
- Options: synthetic per-runtime header and record fixtures; no change if headers stay 1 to 3.
- Answer by: PC probe (first 8 bytes of each `Fallout4 - *.ba2` and `cc*.ba2` on a current install), then offline
  fixture work. (also: VP Q9, VP Q31)
- Blocks: Launcher, New game.
- Status: narrowed (wave 2): v7/v8 are **verified** next-gen versions; xEdit and OpenMW read them with the v1 layout,
  so "only the version number changed" is a **supported hypothesis** and the fix is to accept `{1, 7, 8}` at
  `ba2.py` line 59 with a synthetic v7/v8 fixture test. [Update 2026-10-19: fix on PR #394, not merged: draft PR #394
  at 1825141 reads FO4 BA2 v7 and v8 with the v1 layout, with a synthetic test; detect lists archive versions and
  duplicate archive names; 368da05 makes detect refuse sTestFile INIs and report loose files in My Games Data.] Left: which vanilla archives are 7 vs 8, and whether the
  Anniversary update changed anything beyond NG (PC probe). [VP W2-1]

### Creation Kit and CK-only steps

**TT-07. Is CK batch navmesh usable on our ESM for 1,000+ interiors?**
- Why it matters: converted FO4 navmesh is the plan; CK generation is the fallback (R4 vs R5).
- Options: `-UpdateNavmeshGeneration ... -Part`; marker-seeded interior generation in the CK GUI ([Nexus news 14993](https://www.nexusmods.com/news/14993)).
- Answer by: PC probe on 3 cells, timed, output diffed. (also: ST Q6)
- Blocks: All interiors, People and story.
- Status: open.

**TT-08. Can FaceFX lip generation run in batch for about 123k lines?**
- Why it matters: without it, voiced dialogue stalls on each player's PC.
- Options: CK GUI per plugin (documented); a CreationKit.exe switch ~~(unknown)~~ [Correction 2026-10-19:
  `-CompileFaceFXAnims` plus `Tools\LipGenerator\LipGenerator.exe`, **verified** in job 18; the Starfield CK has no
  `-GenerateLips`, which only the FO4 CK has, with `-GenerateSingleLip`]; convert FO4 `.lip` to `.ffxanim`
  (format unknown); silent fallback. Voice type and body type must match.
- Answer by: offline strings scan of CreationKit.exe for FaceFX switches (like the navmesh scan) [done, job 18; job 19
  queued for LipGenerator's usage text]; one timed batch on PC.
  (also: ST Q18)
- Blocks: People and story.
- Status: open; narrowed 2026-10-19 (lip switch and tool exist, batch behaviour unproven). [Update 2026-10-19, job 21 **Half answered (2026-10-19, PC jobs 24 and 27 to 31, verified; research/engine-mechanics/dialogue.md):** ~~LipGenerator.exe with the CK's Tools\FaceFX actors made `.ffxanim` files from a synthetic WAV in seconds, headless~~ [Correction: LipGenerator.exe ran headless in seconds but writes a raw FaceFX animation, not the compiled `.ffxanim` the game needs]. The compile step is `Tools\FaceFX\ffxc.exe`, which runs headless but takes only `.facefx` actors or YAML `.ffxcproj` projects; whether a generated animation can be mounted into a project and compiled is job 32. Open: that compile, time per 1,000 real lines, resume, acceptance in game.
  (**verified**): Starfield's archives ship 0 `.facefx` files and 278,582 per-line `.ffxanim` lip files;
  LipGenerator.exe's required `actor.facefx` and `actoranalysis.facefx` inputs are not in the shipped data; where they
  come from is **unresolved**, and that now gates any batch run.]

**TT-09. How do we produce `.wem` audio without shipping Wwise?**
- Why it matters: Starfield plays `.wem`; Wwise need is a **supported hypothesis** (general knowledge, not read).
- Options: Wwise CLI on the player's PC (licence); community encoders; another playback path.
- Answer by: offline research on Wwise terms; PC test of other formats. (also: ST Q19; asset pipeline file)
- Blocks: People and story, Launcher.
- Status: open.

**TT-10. How is LOD made, and is there a precombine/previs step in CE2?**
- Why it matters: exterior breadth needs distant LOD; FO4 relies on precombines and we place refs one by one, so draw
  calls may grow sharply (supported hypothesis).
- Options: CK LOD generation (undocumented); own `.btd`/`.lod` writer; merge static geometry per cell at build time;
  accept the cost.
- Answer by: offline scan of Starfield.esm for precombine-like data and CK strings for LOD switches; frame-time PC
  probe (see TT-31). (also: ST Q7, ST Q15, VP Q5, VP Q6)
- Blocks: World, All interiors.
- Status: narrowed (wave 2): object LOD comes from CK `-MockWorldSpaceLOD:<Plugin>.esp <Worldspaces>` ~~(**verified**;
  unattended use is a **supported hypothesis**)~~ [Correction 2026-10-19: ~~**unresolved (sources conflict)**~~: web guides
  say the switch exists; ~~the job 18 string dump of the installed CreationKit.exe does not show it (a wide string the
  filter missed, or absent in the current CK)~~ [Correction 2026-10-19: the job 18 dump printed only strings matching
  its default patterns (Generate, Compile, Lip, AnimInfo, -Convert, -Build), so it could not show the switch either
  way; the other "WorldSpace" strings appeared only because they also contain "Generate"]. Verified LOD-related switches: `-GenerateMeshLODAssociations`,
  `-GenerateMeshLODFailureReport`, `-GenerateMeshLODStats`. First settle whether the switch exists: ~~a wide-string
  search of CreationKit.exe or running it on a test worldspace~~ [Correction 2026-10-19: settled by job 20 (read-only,
  patterns Mock, WorldSpaceLOD, "Should be -"): the switch is **verified (Starfield CK, job 20)**, not in the FO4 CK,
  usage "-MockWorldSpaceLOD:(ESMFilename) (WorldSpaceName0) [WorldSpaceName1] [...]" (an ESM filename); unattended
  use is still a **supported hypothesis**]]; terrain goes through `.btd`, which we already write. Starfield CELL has
  no precombine/previs subrecords (**verified**, schema), and the renderer is GPU-driven (ExecuteIndirect, **verified**),
  so ~~"no bake step to replicate" is a **supported hypothesis**~~ [Correction 2026-10-19: the "no bake step"
  hypothesis is weakened: interiors.md T9 (both CK string dumps, job 18) found `-GeneratePreCombined` and
  `-GeneratePreVisData` in the FO4 CK only, and the GUI actions "Generate Precombined Visibility for Current Cell" and
  "... All Loaded Cells" in the Starfield CK. Starfield may have a precombined-visibility bake run from the CK GUI;
  what it writes and whether it matters for performance is **unresolved**. The Starfield CK also has
  `-GenerateCellAndRefCounts` (possibly per-cell reference counts; **unresolved**)]. Left: run it on a 4-cell test worldspace, time it,
  check `.esm` acceptance and partial-cell failures on 64 cells; measure frame time on a dense cell (TT-31). See TT-41.
  [ST W2-1, ST W2-2, VP W2-2]

**TT-11. Can the CK load our plugins (ESM, worldspace overlay, door PackIns) as an oracle?**
- Why it matters: CK tools (navmesh, preview, finalize) only help if it opens our output.
- Options: one load per build kind, scrape its log.
- Answer by: PC probe (owner time). (also: ST Q5, ST Q16)
- Blocks: All interiors, World, Door animations.
- Status: open.

**TT-12. Does a CK older than the game refuse or corrupt plugins?**
- Why it matters: CK changes ride in game patches; whether every patch has a matching CK build is a supported hypothesis.
- Answer by: PC probe of the CK exe version after the next patch. (also: ST Q34)
- Blocks: Release.
- Status: open.

**TT-13. Where do the launcher's Archive2 and Papyrus compiler come from?**
- Why it matters: the CK (Steam app 2722710, about 823 MB) is allowed but adds a step.
- Options: the player's CK install; bundled open alternatives (bsa-rs, Caprica, named in ST, not evaluated).
- Answer by: offline test of our pipeline with the CK absent; owner decision. (also: ST Q11)
- Blocks: Launcher.
- Status: open.

### SFSE and native code

**TT-14. Without SFSE co-save serialization, where does SFSE-plugin state live?**
- Why it matters: serialization has been disabled since 0.2.12.
- Options: Papyrus properties and globals only; a separate file next to saves.
- Answer by: offline design. (also: ST Q22)
- Blocks: Fallout systems.
- Status: open.

### Record tools, diffs and validators

**TT-15. Do we snapshot every build with Spriggit and diff builds, and where do snapshots live?**
- Why it matters: compare-ids diffs ids; Spriggit diffs every field per record, turning "v6 broke doors" into a list.
- Options: snapshot in CI with Known Masters; keep snapshots out of Git if names/dialogue count as game content;
  scale limit unknown for 683k-record plugins.
- Answer by: offline: time `serialize` of core64c and of FO4Port.esm with `-u ErrorOnUnknown`; owner decision on
  storage. (also: ST Q29, QA Q27)
- Blocks: World, All interiors, Release.
- Status: narrowed (wave 2): versioning is settled by Spriggit's own design (**verified**): translation packages are
  fetched from NuGet by name and version and stamped into each tree; a bump is its own `upgrade` commit with its own
  baseline diff. So pin the package version and keep a local NuGet cache for offline CI (**supported hypothesis**).
  Scale and storage remain open. [QA W2-3]

**TT-16. Can Spriggit `standardize` or a Mutagen round trip be a tier-0 writer validator?**
- Why it matters: an independent parser that reads and rewrites our plugin cleanly is a structural check.
- Answer by: offline run on current ESMs, count diffs (expect omitted-field resets). (also: QA Q28)
- Blocks: all phases (tier 0).
- Status: open.

**TT-17. Which Mutagen version do we pin, and how do we upgrade?**
- Why it matters: 0.55 alphas weekly; Starfield mod-index fix in stable 0.54.4.
- Answer by: offline round-trip tests on both. (also: ST Q28)
- Blocks: all build work.
- Status: narrowed (wave 2): Synthesis `main` (21 Aug 2026) also pins Mutagen 0.54.4 and creates Starfield profiles as
  masters (**verified**), a data point for staying on stable 0.54.4. [ST W2-4]
- [Added 2026-10-19] The Starfield CK has "-ExportESM:(ESMFilename) (output folder) [raw] [--progress]" (**verified**,
  job 20, never run): a possible reference output for our record writer; what it exports is **unresolved**.

**TT-18. Which oracle reads our plugins if xEdit refuses them, and does xEdit Check for Errors run headless?**
- Why it matters: xEdit refuses update and blueprint flags and is Discord-only.
- Options: Mutagen re-read; CK load; game; keep oracle-friendly flags in test builds;
  `xEdit.exe -SF1 -checkforerrors -autoload -P:<plugins.txt> -D:<data>` with a persistent cache (`-C:`), reading the
  exit code (also `-checkforitm`, `-checkfordr`).
- Answer by: offline decision; one timed gate run on Windows; a Wine plus Xvfb trial if Linux CI is wanted.
  (also: ST Q30, QA Q29)
- Blocks: Release.
- Status: answered (wave 2): `checkforerrors` is an unattended mode that never saves and returns the error count
  (capped at 127) as the exit code (**verified**, xEdit source). It is unattended, not headless: a GUI window still
  opens, and the team declined full CLI automation. Using it as a build gate is a **supported hypothesis**; Wine on a
  display-less runner is untested. First SF1Edit start costs 4 to 5 GB RAM and over 10 minutes until cached. The
  oracle choice for update/blueprint-flagged files stays open. [QA W2-1]
- [Added 2026-10-19] The Starfield CK has "-RunValidationSuite:(ESMFilename) (ValidationSuiteName)[:[TestName1],...]"
  (**verified**, job 20, never run): a possible Bethesda-side validator for our ESM (and for navmesh or quest checks,
  TT-11, TT-35); which suites and tests exist is **unresolved**.

### Plugin types and engine limits

**TT-19. Medium master record limit: about 65,535 (Bethesda) or ObjectID up to 0xFF (MO2 BPM page)?**
- Why it matters: decides whether interior clusters and DLC areas can be medium masters.
- Answer by: PC probe with synthetic medium masters of 4,000 and 60,000 records. (also: ST Q32)
- Blocks: All interiors, World.
- Status: answered (wave 2): xEdit masks medium ObjectIDs with `$FFFF` and rejects bits in `$00FF0000`, so at most
  65,536 ObjectIDs; `MaxMediumSlot` = `$FF` is the 256-slot count (**verified**, xEdit source). Inference: the 64-cell
  core (649,596 refs) is about 10x a medium master, so world plugins must be full masters; interiors fit in clusters
  under 65k records. Keep only the in-game check that the engine agrees. [ST W2-5]

**TT-20. Are update plugins useful to us now that they cost a slot?**
- Answer by: offline design. (also: ST Q33)
- Blocks: World.
- Status: narrowed (wave 2): update-flagged files cannot hold new records (**verified**, xEdit source), so they could
  only carry overrides of records we or Starfield already define. [ST W2-5]

**TT-21. What is the plugin-slot and archive budget for the full world, and do we need the BA2 Limit Fix?**
- Why it matters: 256 archives, 253 full slots, a soft limit around 100 to 120 plugins ([Nexus article 688](https://www.nexusmods.com/starfield/articles/688), "one study"), all shared with the player's Creations.
- Options: one ESM + 1 to 3 archives; medium masters for DLC; BA2 Limit Fix (SFSE).
- Answer by: PC probe with the Engine Fixes BA2 counter; Plugins.txt counts from testers. (also: ST Q17, VP Q17)
- Blocks: World, Release.
- Status: open.

**TT-22. Can one archive pass 4 GiB, and how many archives auto-load per plugin?**
- Why it matters: a full-resolution 64-cell core needs about 8.5 GiB; per-archive limit is 4,095 MB (ejams1 guide).
- Answer by: PC probe: a synthetic archive over 4 GiB (5 GiB); a plugin with two numbered archives. (also: ST Q14,
  VP Q4)
- Blocks: World, All interiors, Launcher.
- Status: narrowed (wave 2): BA2 offsets are 64-bit, so the **format** does not stop at 4 GiB (**verified**); FO4 users
  report 9.5 and 14.7 GB archives loading (user reports, FO4 only). Whether **Starfield's engine** reads past 4 GiB is
  still **unresolved**; vanilla archives stop just under it. Until the probe, keep splitting at 4,095 MB.
  [ST W2-6, VP W2-3]

### Crash diagnosis

**TT-23. Which crash logger do we run in tests and ship to players, and what does triage do with its signature?**
- Why it matters: Fallout London merged Buffout 4 only after a rough launch; our dumps are 18 GB; the Havok int3 leaves
  no WER entry. A signature lets the runner mark a repeat crash FAIL CRASH without a dump.
- Options: sf-crash-logger; Trainwreck; Engine Fixes Detailed Crash Logger. Risk: the logger itself may crash or mask.
- Answer by: PC probe: trigger the known Havok assert (vault cart case) with each, compare output and dump size; two
  forced crashes (same, different) to compare signatures; owner picks. (also: QA Q11, QA Q30, VP Q24)
- Blocks: Release, Launcher, all in-game testing.
- Status: narrowed (wave 2): sf-crash-logger maturity is now known (**verified**): four releases in one month, last
  v0.4.0 on 10 Jul 2026, one maintainer, tested under Wine; the signature became version-stable only in v0.4.0, and
  raw `__fastfail` cannot be caught by any plugin. So (**supported hypothesis**) it is a candidate for test runs, pinned
  by version and checked against a deliberate crash, not yet the shipped logger; Engine Fixes' logger remains the more
  established player-facing option. Trainwreck licence still unread. [QA W2-4]

**TT-24. What goes into the player's support bundle, and nothing personal?**
- Options: crash signature, load order, versions, ledger fold, preflight results (CFA, language, disk, versions).
- Answer by: offline design; owner decision on what is collected. (also: QA Q12, QA Q10)
- Blocks: Launcher, Release.
- Status: open.

### In-game automation

**TT-25. Which Starfield `Debug` functions are live in retail?**
- Why it matters: each live one removes a keystroke or a whitelist decision; route walks could follow navmesh via
  `PlayerMoveToAndWait`; clean exits via `QuitGame` avoid false dumps; `DumpAliasData` might read quest state.
- Options: one-launch probe list: `TraceUser` (known yes), `AutomatedTestLogProgress`, `StartScriptProfiling`,
  `DumpAliasData`, `CenterOnCellAndWait`, `PlayerMoveToAndWait`, `ExecuteConsole`, `QuitGame`, `GetConfigName`.
  Note our own probe found `GetFormEditorID` DebugOnly.
- Answer by: PC probe; owner whitelists `cgf "Debug.<fn>"`. (also: QA Q31, QA Q3, QA Q17, QA Q19, QA Q32)
- Blocks: New game, People and story, World, all in-game testing.
- Status: open.

**TT-26. Can the Papyrus remote debugger be a read-only observation channel?**
- Why it matters: typing is the runner's most fragile part; `bAlwaysActive=1` and `bPauseOnAltTab=0` may also fix
  focus-loss flakiness.
- Answer by: PC probe: attach a DAP client with `bEnableRemoteDebugging=1`, read one quest variable. (also: QA Q33, QA Q19)
- Blocks: People and story, Fallout systems.
- Status: open.

**TT-27. How do we start a new game unattended from the main menu?**
- Why it matters: the runner loads saves today; every phase-1 test starts from the menu.
- Options: `sStartingConsoleCommand` bat in `[General]` (one merged bat); Papyrus on game load; scripted menu click.
- Answer by: PC probe, 5 runs each, success rate. (also: QA Q2)
- Blocks: New game.
- Status: open.

**TT-28. Do smoke runs add a camera spin and NPC portrait sheet (AutoTest pattern)?**
- Answer by: PC probe: 20 known cells with and without spin, crash catches vs time; portrait sheet once actors convert.
  (also: QA Q6, QA Q9)
- Blocks: All interiors, People and story.
- Status: open.

**TT-29. Which regressions are judged by screenshot diff, and with what tolerance?**
- Why it matters: thousands of cells cannot be eyeballed; no Bethesda-world tool found.
- Options: fixed camera at the COC marker after a settle; perceptual hash vs last accepted build; humans see changed
  cells only.
- Answer by: PC probe: same cell shot 5 times for the noise floor. (also: QA Q8)
- Blocks: All interiors, World.
- Status: open.

**TT-30. Do we port a Lilac-style Papyrus unit-test harness?**
- Why it matters: our Papyrus is tested only by parsing source and end to end.
- Options: port Lilac (MIT); own minimal `expect` harness started by a test quest.
- Answer by: offline + one PC compile. (also: QA Q20)
- Blocks: People and story, Fallout systems.
- Status: open.

### Performance protocol

**TT-31. What is the reproducible performance protocol and the budget?**
- Why it matters: Starfield is CPU-bound at low settings (Gamers Nexus); our cells hold up to 6,049 refs; 650k+ refs
  per 64 cells; SFEF's "Reduce Traversal Stutter" exists because vanilla stutters.
- Options: PresentMon CLI on the Red Rocket to Sanctuary walk, 4 passes, variance band, 1% lows, logged in
  docs/ai/optimization.md; densest interiors (Vault 111, Diamond City Market interior, Mass Fusion).
- Answer by: PC probe: 4 passes on two builds for the noise floor; plus the 3-spot probe (dense downtown, open
  wasteland, interior) logging fps, frame time, VRAM and RAM, vanilla vs core vs core-with-LOD. (also: QA Q14, VP Q5,
  VP Q18)
- Blocks: World, All interiors, Release.
- Status: narrowed (wave 2): Starfield's renderer generates indirect draw arguments on the GPU and issues
  ExecuteIndirect (**verified**, vkd3d-proton PR 1694), and uses up to eight CPU cores (**verified**, DSOGaming). So the
  cost of 650k refs is more likely in reference loading, scripts, Havok and streaming than in draw submission
  (**supported hypothesis**; no source measured a dense modded cell). [VP W2-2]

**TT-32. Should exterior smoke log handle and archive counts?**
- Answer by: PC probe: one 3x3 hop run with Engine Fixes `Dump Pointer Handles` on. (also: QA Q15)
- Blocks: World.
- Status: open.

**TT-33. Is timescale acceleration safe for day/night and weather tests?**
- Why it matters: EA SEED saw physics fail under fast-forward.
- Options: `SetLocalTime` jumps (already whitelisted) vs high timescale.
- Answer by: PC probe on Havok-heavy cells. (also: QA Q16)
- Blocks: World.
- Status: open.

**TT-34. What does a minimum-spec player see (build time, VRAM, frame time)?**
- Why it matters: the owner's 7950X3D / 4070 Ti hides costs; no data at the 16 GB / GTX 1070 Ti floor.
- Options: run the 15-cell build with a memory cap and fewer cores; VRAM per texture cap on an 8 GB card.
- Answer by: PC probe or cloud VM; community contact for low-end GPUs. (also: VP Q16, VP Q20)
- Blocks: Launcher, Release.
- Status: narrowed (wave 2): one vanilla VRAM baseline exists (RTX 3080 12 GB: under 3 GB at 1080p low, 3.8 GB at
  1080p ultra, about 6.5 GB at 4K; **verified**, single test). VRAM with our core loaded is **unresolved**; the 3-spot
  probe with texture caps halved (TT-31) measures it. [VP W2-2]

### Navmesh validation

**TT-35. Can we validate navmesh offline before in-game tests?**
- Why it matters: the runner and AutoTest catch crashes, not broken pathing.
- Options: CK Pathing Tests (manual); CK finalize (deletes failures); xEdit inspection; our own reachability checker
  between door markers over converted NAVM.
- Answer by: offline checker vs a CK Pathing Test on 3 cells (one CK session). (also: QA Q7)
- Blocks: All interiors, People and story.
- Status: open.

### Community testing

**TT-36. Do we adopt Skywind's lifecycle labels, including Known Shippable for engine bugs?**
- Why it matters: our labels track agent work, not bug state across builds.
- Options: map onto ledger states so a fix closes only on a later build's PASS; Skywind's full set is Confirmed,
  In Progress, Claim Fixed, Fix Fail, Invalid Issue, Known Shippable, a Crash label and department labels, with "Do NOT
  close the issue" until QA retests; "QA Blocked vs Fail" split as converter-vs-placement triage (a collision mismatch
  after `meshcollision.py` is a converter bug, floating with matching collision is a placement bug); an inactivity rule
  (Skywind: three months, then two weeks' notice).
- Answer by: owner decision. (also: QA Q23, QA Q5, PR W2 question 5)
- Blocks: Release.
- Status: narrowed (wave 2): label set, retest-before-close rule and triage split are **verified** from the Skywind
  handbook; our AGENTS.md labels already match the flow, the gaps are `Claim Fixed` with retest-before-close and
  `Known Shippable`. Still an owner decision. [PR W2-5, QA W2-2]

**TT-37. What tester pool, clean profile and support model do we run before Nexus?**
- Options: closed beta (SS2 Patreon, 7 to 10 day cadence); Discord role (Skywind); open GitHub; launcher checks
  Plugins.txt against an allowed list and stamps reports; 1-on-1 help (FOLON) vs self-diagnosis tool; a dated "known
  unfinished, do not report" list with each tester build.
- Answer by: owner decision. (also: QA Q24, QA Q25, QA Q26)
- Blocks: Release.
- Status: narrowed (wave 2): Skywind's practice is **verified**: clean Skyrim SE with only SKSE and SkyUI; monthly
  builds with 2 to 3 hotfixes in the first week; builds by P2P (Resilio) and OneDrive, not GitHub ("a boatload of
  problems"); a dated do-not-report list. Our builds are generated on the player's PC, so build distribution matters
  less to us; the do-not-report list carries over (**supported hypothesis**). [QA W2-2]

**TT-38. How many human-review minutes per build can the owner give, and what gets them?**
- Options: contact sheet of changed screenshots only; a 10% random sample; only cells our automated per-cell report
  marks Review (Skywind's LD Review pattern).
- Answer by: owner decision. (also: QA Q34)
- Blocks: All interiors, World, Release.
- Status: narrowed (wave 2): Skywind gates level-design QA with an automated LD Review report (**verified** that it
  exists; its checks are not described). Our testqueue per-cell report as the gate is a **supported hypothesis**.
  [QA W2-2]

**TT-39. Which tools do players install vs only the team, and do we require SFSE for play or only for tests?**
- Why it matters: if logging and probes need SFSE but play does not, tests run a configuration players do not.
- Options: CK yes; xEdit no (Discord-only); NifSkope no; SFSE required (allowed) or two profiles with a reduced smoke
  on no-SFSE; Game Pass excluded or an SFSE-free tier.
- Answer by: owner decision; Game Pass load test via community contact. (also: ST Q24, ST Q25, QA Q13, VP Q27)
- Blocks: Launcher, Release.
- Status: open.

### Multi-game

**TT-40. Does the test inventory generalise when FO3 or New Vegas are added?**
- Why it matters: TTW shows installers and verification multiply with two games.
- Options: inventory planner keyed by source game.
- Answer by: offline design. (also: QA Q35)
- Blocks: Multi-game.
- Status: open.

### Added in wave 2

**TT-41. Should the converter set LAYR `LODB` and object LOD flags itself so the CK LOD run needs no layer work?**
- Why it matters: `-MockWorldSpaceLOD` picks objects by layer [Correction 2026-10-19: per web guides; whether the
  switch exists is ~~**unresolved (sources conflict)**~~, see TT-10] [Correction 2026-10-19: the switch is **verified
  (Starfield CK, job 20)**, see TT-10]; LOD membership is plugin data (LAYR `LODB`, "Has Distant
  LOD" / "Is Full LOD", `BGSLodOwner_Component`), so we can write it instead of asking the player to tick layers.
- Options: converter writes layers and flags from FO4 LOD data; CK GUI layer ticking; no object LOD.
- Answer by: offline (xEdit read of a vanilla overlay's layers) + PC probe of one LOD run. (also: ST W2 Q35)
- Blocks: World.
- Status: open (wave 2). [ST W2-1]

**TT-42. Do we use SFME as a material oracle to compare our generated `.mat` with vanilla?**
- Why it matters: no public tool writes a CDB, so our loose-`.mat` route has no independent check; SFME (open source)
  reads `materialsbeta.cdb` and exports `.mat` JSON.
- Options: offline diff of our `.mat` against SFME exports of the vanilla materials we imitate; no oracle.
- Answer by: offline. (also: ST W2 Q36)
- Blocks: World, All interiors.
- Status: open (wave 2). [ST W2-3]

## Owner decisions in this area

All are recommendations, not decisions.

- TT-01 patch response: **recommend** pin and refuse (current gate), no downgrade guidance, a one-line support matrix;
  SFSE has been same-day in 2026, so the wait is our own fixes.
- TT-02 patch-day owner: **recommend** watchdog/Codex runbook detects, Claude runs the checklist; promise "within a
  week, previous build until then".
- TT-04 data-only core: **recommend** yes, SFSE optional per system; it is the cheapest to maintain and keeps a Game
  Pass tier possible.
- TT-13 Archive2 and Papyrus compiler: **recommend** use the player's CK install (already allowed); revisit open tools
  only if CK install friction shows in testing.
- TT-15 Spriggit snapshots: **recommend** adopt for diffs, stored outside Git (local or PC only) until we know whether
  record text counts as game content.
- TT-23 crash logger: **recommend** sf-crash-logger for test runs (signature, small dump, GPL-3 fits our notice),
  pinned at v0.4.0 or later (first version-stable signature), pending the A/B probe; wave 2 points to Engine Fixes'
  logger as the player default unless the probe says otherwise.
- TT-24 support bundle: **recommend** signature, load order, versions, ledger fold and preflight only; no paths with
  user names.
- TT-25 Debug whitelist: **recommend** allow `cgf "Debug.<fn>"` for the one probe list only.
- TT-36 lifecycle labels: **recommend** adopt `Claim Fixed` with retest-before-close and `Known Shippable`, mapped
  onto ledger states.
- TT-37 testers: **recommend** a small closed pool with a clean profile stamped by the launcher; self-diagnosis over
  1-on-1 help, given owner time.
- TT-38 review minutes: **recommend** changed-screenshot contact sheet only.
- TT-39 player tools: **recommend** require CK and SFSE for release 1, Game Pass out of scope until TT-04 lands.

## Cheapest experiments

Offline first:
1. **Strings scan of CreationKit.exe** for FaceFX switches, like the navmesh scan. Narrows TT-08. (LOD switch and
   precombine absence came from wave 2 sources, TT-10.) [Correction 2026-10-19: precombine absence is weakened (the
   Starfield CK has "Generate Precombined Visibility" GUI actions, interiors.md T9), and `-MockWorldSpaceLOD` is
   **verified (Starfield CK, job 20)**; see TT-10.]
2. **Spriggit and Mutagen on current ESMs**: `serialize -u ErrorOnUnknown`, `standardize`, Mutagen round trip; time
   core64c; on Mutagen 0.54.4 and the current 0.55 alpha. Closes TT-15, TT-16, TT-17, informs TT-18.
3. **Offline NAVM reachability checker prototype** on 3 converted cells. Half of TT-35.
4. **Record diff of Starfield.esm quest and planet records** we override across 1.16.236/242/244. Informs TT-02,
   TT-05.
4a. **BA2 v7/v8 fixture test**: accept `{1, 7, 8}` in `ba2.py` with synthetic headers. Code half of TT-06.
4b. **SFME export of vanilla materials** we imitate, diffed against our `.mat`. Closes TT-42.

PC read-only or single-launch probes:
5. **One `Debug` probe launch** with `bEnableRemoteDebugging=1`, `bAlwaysActive=1`, `bPauseOnAltTab=0`: call the
   TT-25 list via `cgf`, attach a DAP client to read one variable. Closes TT-25, TT-26, informs TT-27, TT-33.
6. **Crash logger A/B**: trigger the Havok assert with sf-crash-logger, Trainwreck and Engine Fixes in turn; force a
   second, different crash. Closes TT-23, informs TT-24, TT-32.
7. **File header read**: first 8 bytes of each `Fallout4 - *.ba2` and `cc*.ba2` on a current install, plus CK exe
   version. Closes TT-06 (which archives are 7 vs 8), TT-12 baseline.
8. **Synthetic limits plugin**: a 5 GiB archive, a plugin with two numbered archives, a medium master near 60,000
   records (in-game confirmation only), with the Engine Fixes BA2 counter on. Closes TT-22, confirms TT-19, informs
   TT-21.
9. **CK session**: load our ESM, run batch navmesh on 3 cells and a Pathing Test; ~~run `-MockWorldSpaceLOD` on a
   4-cell test worldspace (timed, `.esm` vs `.esp`).~~ [Correction 2026-10-19: first settle whether
   `-MockWorldSpaceLOD` exists: ~~a wide-string search of CreationKit.exe or running it on a test worldspace~~
   [Correction 2026-10-19: settled, **verified (Starfield CK, job 20)**]; only then
   time it on a 4-cell test worldspace, `.esm` vs `.esp`.] Closes TT-07, TT-11, other half of TT-35, narrows TT-10, TT-41.
10. **PresentMon baseline**: 4 passes on the Red Rocket walk on two builds, the 3-spot fixed probe (vanilla vs core vs
    core-with-LOD, VRAM and RAM), plus a 5-shot screenshot noise floor at one COC marker. Closes TT-31 (protocol),
    TT-29 (noise floor), informs TT-34.
11. **xEdit gate run**: `-SF1 -checkforerrors -autoload` on our plugins with a persistent cache, timed, exit code read.
    Settles TT-18 in practice.

## Gaps (after wave 2)

- Wwise licence terms and community `.wem` encoders (TT-09).
- Whether xEdit gate modes run under Wine on a display-less Linux runner (TT-18).
- Trainwreck GitHub page and licence; sf-crash-logger's supported game runtimes on Windows (TT-23).
- Starfield depot IDs and older public branches (TT-03).
- Whether `-MockWorldSpaceLOD` [Correction 2026-10-19: ~~exists at all (sources conflict), and whether it~~] accepts `.esm` and its run time on 64 cells (TT-10, TT-41). [Correction 2026-10-19: existence settled, **verified (Starfield CK, job 20)**; its usage text names an "(ESMFilename)"; run time on 64 cells still open.]
- [Added 2026-10-19] What the Starfield CK's "Generate Precombined Visibility" GUI actions write and whether they matter for performance; what `-GenerateCellAndRefCounts` does (TT-10; interiors.md T9).
- Frame/CPU profilers usable with Creation Engine (Tracy-style); measured draw-call cost of a dense modded cell; VRAM
  with our core loaded (TT-31, TT-34).
- Custom Command Framework vs Cassiopeia claims on SFSE custom Papyrus natives (ST section 3, not re-checked).
- Published Synthesis patchers for Starfield; BetterConsole features; Skyblivion and SS2 bug intake; the checks in
  Skywind's automated LD Review report.
- Automated screenshot comparison and quest-graph validation tools for Creation Engine (TT-29).
- Pages rate-limited and not read: Nexus 17161, JMPZ11 nifskope-sf-mesh, mp1st 1.16.244, KitGuru CK article.

## Handed to phase files

| Question | Target |
|---|---|
| Can the Vault 111 start be built with no SFSE (data + Papyrus only)? (ST Q2) | newgame.md |
| Scripted "new game to first exit" run and its checkpoints (QA Q1) | newgame.md |
| Does the start survive a Starfield patch; which Fallout4.esm runtime is canonical for Vault 111 / MQ101? (VP Q1, Q2) | newgame.md |
| Automated proof that a door played its animation, not just teleported (QA Q4) | door-animations.md |
| Do door hooks rely on SFSE or runtime addresses? (VP Q3) | door-animations.md |
| Interiors as small/medium masters, record count per cluster (ST Q8); interiors per plugin/archive (VP Q4) | interiors.md |
| Fallout 4 source runtimes accepted, detection from data, CC files, GOG/Game Pass sources (VP Q7, Q8, Q10, Q11) | launcher.md |
| Launcher detects Starfield version and store (ST Q9); fetch SFSE/Address Library (ST Q10); INI write rule (ST Q12) | launcher.md |
| Build cache keyed to Starfield runtime (VP Q14); disk space check (VP Q15) | launcher.md |
| Scaleform menu interface for Pip-Boy on 1.16.244 (ST Q23); machine-readable proofs for Pip-Boy, VATS, workshop, power armor (QA Q21) | engine-mechanics.md |
| Quest test checklist from Skywind guidelines (QA Q18); voice type to body type mapping (ST Q20) | people-and-story (cross-cutting file) |
| GPL-3 obligations for Mutagen and Spriggit (ST Q26); Nexus requirement tagging (ST Q27) | release/legal (cross-cutting file) |

## Sources

- https://raw.githubusercontent.com/ianpatt/sfse/master/sfse_whatsnew.txt
- https://sfse.silverlock.org/
- https://www.nexusmods.com/starfield/mods/106 ; https://www.nexusmods.com/starfield/mods/106?tab=files
- https://www.nexusmods.com/starfield/mods/3256 ; https://stepmodifications.org/wiki/Starfield:Address%20Library%20for%20SFSE%20Plugins
- https://www.nexusmods.com/starfield/mods/857 ; https://www.nexusmods.com/starfield/mods/14577 ; https://www.nexusmods.com/starfield/mods/3621
- https://starfield.gg/starfield-latest-update/ ; https://starfield.gg/starfield-update-1-16-236-patch-notes-free-lanes/
- https://www.gamewatcher.com/Starfield/guides/patch-notes-hub-and-roadmap-of-updates-for-2026
- https://bethesda.net/en/article/2HBTwuF9g9baAQkEud4WZ9/starfield-update-1-16-242-may-14-2026
- https://bethesda.net/en-US/news/starfield-update-1-16-244-june-2026
- https://steamdb.info/patchnotes/18285521
- https://patched.gg/games/starfield ; https://patchbot.io/games/starfield/articles/507-update-116244-june-11-2026
- https://twt.omada.cafe/r/Starfield/comments/1kg7k32/starfield_update_115214_may_6_2025_beta
- https://www.afkmods.com/Unofficial%20Starfield%20Patch%20Version%20History.html
- https://www.nexusmods.com/news/14993 ; https://www.nexusmods.com/news/15400
- https://starfieldwiki.net/wiki/Starfield_Mod:Creation_Kit ; https://stepmodifications.org/wiki/Starfield:Creation_Kit ; https://dev.starfieldwiki.net/wiki/Starfield_Mod:Main_Page
- https://dev.starfieldwiki.net/wiki/Starfield_Mod:Audio_File_Conversion ; https://nexusmods.com/starfield/mods/12576 ; https://facefx.com/node/4600
- https://github.com/TES5Edit/TES5Edit/releases ; https://github.com/TES5Edit/TES5Edit/releases/tag/xedit-4.1.5
- https://reddit.sentinel-team.org/posts/1u6jz38/snapshots/2026-06-16T07%3A02%3A42.6264Z
- https://www.nexusmods.com/starfield/mods/7610
- https://www.nuget.org/packages/Mutagen.Bethesda.Starfield ; https://github.com/Mutagen-Modding/Mutagen ; https://api.github.com/repos/Mutagen-Modding/Mutagen/releases?per_page=8 ; https://mutagen-modding.github.io/Mutagen/
- https://github.com/Mutagen-Modding/Spriggit ; https://mutagen-modding.github.io/Spriggit/ ; https://mutagen-modding.github.io/Spriggit/cli/ ; https://mutagen-modding.github.io/Spriggit/omissions/ ; https://www.nuget.org/packages/Spriggit.Yaml.Starfield ; https://api.github.com/repos/Mutagen-Modding/Spriggit/releases?per_page=6
- https://github.com/Mutagen-Modding/Synthesis ; https://mutagen-modding.github.io/Synthesis/
- https://loot.readthedocs.io/en/0.24.1/app/changelog.html
- https://www.nexusmods.com/starfield/mods/17318
- https://github.com/fo76utils/nifskope/releases ; https://nexusmods.com/starfield/mods/4360 ; https://github.com/BadDogSkyrim/PyNifly/ ; https://www.nexusmods.com/starfield/mods/9234
- https://github.com/ejams1/starfield-modding-guide
- https://forums.nexusmods.com/topic/13459379-a-guide-to-game-pass-modding-no-mod-manager
- https://www.nexusmods.com/starfield/mods/17936
- https://forums.nexusmods.com/topic/13518743-crash-issue-too-many-ba2-files-causing-ctds-%E2%80%93-looking-for-fix-or-insight/
- https://www.nexusmods.com/starfield/articles/688
- https://starfieldwiki.net/wiki/Starfield:System_Requirements
- https://www.nexusmods.com/fallout4/mods/42147?tab=files
- https://forums.nexusmods.com/topic/13525754-how-to-downgrade-fallout-4-game-of-the-year-edition-after-the-anniversary-update-rollback-from-111137-to-110984/
- https://steamcommunity.com/sharedfiles/filedetails/?id=3604110005
- https://steamcommunity.com/app/377160/discussions/0/685239894022330731/
- https://handbook.tesrskywind.com/qa/bug-reporting ; https://handbook.tesrskywind.com/qa/onboarding ; https://handbook.tesrskywind.com/dev/quest-testing-guidelines ; https://github.com/TESRSkywind/QA/issues (not opened)
- https://overclock3d.net/news/software/fallout-london-is-in-its-final-stage-of-qa-testing-at-gog/
- https://pcgamer.com/games/rpg/fallout-london-devs-are-working-on-a-huge-patch-offering-dedicated-1-on-1-troubleshooting-sessions-to-help-players-with-installs-and-crashes
- https://thebestoftimes.moddinglinked.com/faq.html ; https://taleoftwowastelands.com/viewtopic.php@t=2111 ; https://mod.pub/ttw/133/docs/25-faq-frequently-asked-questions
- https://en.wikipedia.org/wiki/Skyblivion
- https://www.patreon.com/posts/24469236
- https://github.com/Muriel-Salvan/AutoTest ; https://www.nexusmods.com/skyrimspecialedition/mods/42520
- https://www.nexusmods.com/fallout4/mods/18410 ; https://www.nexusmods.com/skyrim/mods/75652
- https://dev.starfieldwiki.net/wiki/Starfield_Mod:Script-Debug
- https://starfieldwiki.net/wiki/Starfield_Mod:Debugging_Papyrus_with_VS_Code
- https://www.nexusmods.com/starfield/articles/780
- https://forums.nexusmods.com/topic/13253886-guide-how-to-properly-merge-mods-fixes-bat-files-sstartingconsolecommand-not-always-working
- https://github.com/0xra0/sf-crash-logger
- https://www.nexusmods.com/starfield/mods/5068 ; https://allmods.net/starfield-mods/starfield-miscellaneous/trainwreck-a-crash-logger-v1-1/
- https://www.nexusmods.com/starfield/mods/10457 ; https://www.nexusmods.com/starfield/mods/10457?tab=files
- https://www.nexusmods.com/starfield/articles/559
- https://ck.uesp.net/wiki/Pathing_Tests
- https://www.nexusmods.com/fallout4/articles/4209
- https://gamersnexus.net/cpus-game-benchmarks-graphics-guides/starfield-cpu-benchmarks-bottlenecks-intel-vs-amd-comparison
- https://arxiv.org/pdf/2307.11105
- Not read (rate limit or gate): https://www.nexusmods.com/starfield/mods/17161 ; https://github.com/JMPZ11/nifskope-sf-mesh/ ; mp1st 1.16.244 article ; KitGuru CK article ; Steam Community downgrade thread 802331493180395957
- Wave 2: https://modding.wiki/en/starfield/developers/tutorials/creatingworldspacelod ; https://forums.nexusmods.com/topic/13497519-how-to-create-lod/
- Wave 2: https://steamcommunity.com/sharedfiles/filedetails/?id=3385012985 ; https://steamcommunity.com/sharedfiles/filedetails/?id=3266682879 ; https://dyndolod.info/Help/xLODGen
- Wave 2: https://github.com/maximusmaxy/SFME ; https://www.nexusmods.com/starfield/mods/7830 ; https://www.nexusmods.com/starfield/mods/14659 ; https://www.nexusmods.com/starfield/mods/17879
- Wave 2: https://github.com/Mutagen-Modding/Synthesis (commit 14cf3fa)
- Wave 2: https://github.com/TES5Edit/TES5Edit (dev-4.1.6: Core/wbDefinitionsSF1.pas, wbDefinitionsFO4.pas, wbImplementation.pas, wbInterface.pas, wbBSArchive.pas; xEdit/xeInit.pas, xeMainForm.pas, xEdit.dpr) ; https://tes5edit.github.io/docs/18-whatsnew.html ; https://github.com/TES5Edit/TES5Edit/issues/655
- Wave 2: https://forums.nexusmods.com/topic/11091353-ba2-size-limits-and-splitting-textures-between-ba2s
- Wave 2: https://www.nexusmods.com/fallout4/articles/5844 ; https://gitlab.com/OpenMW/openmw/-/merge_requests/4055 ; https://git.cijber.net/mirror/openmw/commit/a5d936993fb017f1c6bc17aecdc95e760c270edd ; https://gitlab.com/OpenMW/openmw/-/raw/master/components/bsa/ba2gnrlfile.cpp ; https://forums.nexusmods.com/topic/13484961-solved-nifskope-and-next-gen-ba2-archives
- Wave 2: https://github.com/HansKristian-Work/vkd3d-proton/pull/1694 ; https://www.destructoid.com/open-source-community-figures-out-problems-with-performance-in-starfield/ ; https://www.dsogaming.com/pc-performance-analyses/starfield-pc-performance-analysis/
- Wave 2: https://www.noticias3d.com/noticia/92797/starfield-requisitos-4k-cuanta-memoria-grafica-consume.html ; https://www.corsair.com/us/de/explorer/diy-builder/memory/how-memory-capacity-affects-starfield/
- Wave 2: https://handbook.tesrskywind.com/qa/frequently-asked-questions ; https://handbook.tesrskywind.com/qa/qa-fixes-guide ; https://handbook.tesrskywind.com/ ; https://handbook.tesrskywind.com/misc/inactive-lead-guide
- Wave 2: https://mutagen-modding.github.io/Spriggit/workflow/ ; https://mutagen-modding.github.io/Spriggit/translation-packages/ ; https://mutagen-modding.github.io/Spriggit/upgrade-practices/
- Wave 2: https://github.com/0xra0/sf-crash-logger/releases ; https://github.com/0xra0/sf-crash-logger/commits ; https://github.com/alandtse/CrashLoggerSSE/releases
- Repo files cited by the findings: docs/actors/npc-navigation.md section 2.4; docs/spikes/S2-S4-S9-plugin-units-loading.md; docs/FORMAT-GAP.md; docs/ROADMAP.md C1; docs/SETUP.md; docs/PLAY-AND-TEST.md; docs/ai/known-unknowns.md; docs/ai/optimization.md; docs/ai/decisions.md (2026-10-12); docs/JOURNAL.md (2026-10-16); docs/terrain/core64c.md:271; src/fo4sf/ba2.py; src/fo4sf/core/preflight.py; scripts/bridge/FO4SF_Probe.psc; scripts/bridge/FO4SF_Bridge.psc; scripts/game/bridge_log.py
