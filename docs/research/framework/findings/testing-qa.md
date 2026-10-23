# Testing and QA at scale: what big Bethesda mod projects and the tool ecosystem do, and what we should adopt

Research agent testing-qa, 2026-10-19. Offline web research plus read-only reads of the repo (`main` checkout) and
the two notes named in the task (research/next-phase/testing-automation.md, docs/PLAY-AND-TEST.md), which this file
does not repeat.

**Bottom line.** The big total conversions (Skywind, Fallout London, TTW, Skyblivion, Sim Settlements 2) test almost
entirely with **people**: closed tester pools, a GitHub or board-based bug lifecycle with QA-owned closing, per-feature
checklists and quest test guidelines. None of them runs anything like this project's unattended in-game runner;
the nearest public precedent is **AutoTest** for Skyrim SE (teleport to locations and circle the camera to catch
crashes, screenshot NPCs), which is a smaller version of what `testqueue.py` already does. So for in-game automation
we are ahead of the field and there is little to copy. Where the ecosystem *is* ahead of us, and where we should
adopt, is: (1) **an SFSE crash logger** (`sf-crash-logger` writes minidumps, a crash signature to group duplicates,
a breadcrumb trace and the load order; Trainwreck writes call stacks with module hashes), which would replace the
18 GB ProcDump dumps for routine runs and give each crash a stable ID; (2) **Spriggit** text snapshots of our
generated plugins for record-level diffs between builds (it lists Starfield and Fallout 4, and can run in CI without
game files through "Known Masters"); (3) **Starfield's own `Debug` script**, which contains automated-test and
profiling functions (`AutomatedTestLogProgress`, `StartScriptProfiling`, `CenterOnCellAndWait`,
`PlayerMoveToAndWait`, `QuitGame`, `ExecuteConsole`) whose availability in the retail build is **unresolved** and
worth one PC probe; (4) the **Skywind bug lifecycle** (Confirmed, Claim Fix, In Current Build, Fix Fail, Closed
Fixed, Known Shippable) for when community testers arrive; and (5) a **reproducible performance protocol**
(PresentMon CLI, fixed route, several passes, a run-to-run variance band) before "breadth" makes frame time the
first thing players notice.

Note on coverage: the shared web-search budget ran out and the fetch proxy rate-limited me partway through. Pages I
could not read: the Skywind QA FAQ and QA Fixes Guide, Spriggit's Workflow page, and the Crash Logger SSE changelog.
Topics I could not search at all: xEdit command-line batch mode, Tracy/frame profilers for Creation Engine,
BetterConsole's features, Beyond Skyrim's QA, and Skyblivion's and SS2's bug process beyond what is below. These
are listed as **unresolved** where they matter.

## Findings

### A. How the big mod projects run QA

**Skywind (TESR), the best documented.**
- Bugs live in GitHub Issues (`TESRSkywind/QA`), reached only with a Triage role; reports use a template with
  issue, expected behaviour, optional reproduction steps and **build version**, plus department labels (2D, 3D,
  Animation, Audio, Coding, Landscaping, Level Design, UI, Voice and Dialogue, Writing). **verified**
  (https://handbook.tesrskywind.com/qa/bug-reporting)
- Labels form a lifecycle: New Issues, Confirmed (QA lead validated), In Progress, Claim Fix (developer says fixed),
  In Current Build (the fix shipped in a build), Fix Fail (retest failed, with build number), Closed Fixed,
  Invalid, **Known Shippable** (real but won't fix, e.g. engine bugs), Crash (high priority). Developers must not
  close issues; QA closes after retest. **verified** (bug-reporting and
  https://handbook.tesrskywind.com/qa/onboarding)
- Regression testing targets issues labelled both Claim Fix and In Current Build, and retests "beyond the original
  ticket's scope". **verified** (onboarding)
- Feature cards (ClickUp for quests/coding, Notion for interiors and landscaping) cannot enter QA without a checklist;
  statuses Ready for QA, QA In Progress, QA Reviewed, Complete, with Notion buttons "Begin QA / QA Passed / QA Failed".
  **verified** (onboarding)
- Level-design cards come with an **"automated LD Review report"** that testers read, paying attention to "Review"
  items. What it checks is not described on the page. **verified that it exists; contents unresolved** (onboarding)
- Testers install a clean Skyrim SE with only SKSE and SkyUI, then the newest full build, then patches and hotfixes
  in order; merges about monthly with 2 to 3 hotfixes in the following week; full build about 18 GB zipped.
  **verified** (onboarding)
- Quest testing guideline: play every branch, try to break the quest (wrong order, kill quest NPCs, go early),
  save at critical points; verify journal vs objective vs marker separately; quest items droppable; dialogue that
  repeats or bypasses conditions is a bug; use `moveto` to drag escort NPCs through unfinished navmesh.
  **verified** (https://handbook.tesrskywind.com/dev/quest-testing-guidelines)

**Fallout London (Team FOLON).**
- The release was delayed from April 2024 because Fallout 4's Next-Gen update broke required tools (the FO4 Script
  Extender and other mods). **verified** (https://overclock3d.net/news/software/fallout-london-is-in-its-final-stage-of-qa-testing-at-gog/)
- GOG ran a final QA stage on several builds before release. **verified** (same)
- After launch (late July 2024) it crashed a lot; the first hotfix **merged Buffout 4 (a crash logger and engine
  fix)** into the mod, and the team ran "dedicated 1-on-1 troubleshooting sessions" for installs and crashes on
  Discord. **verified** (https://pcgamer.com/games/rpg/fallout-london-devs-are-working-on-a-huge-patch-offering-dedicated-1-on-1-troubleshooting-sessions-to-help-players-with-installs-and-crashes)
- Inference: a crash logger was added only after release, under pressure. **supported hypothesis**

**Tale of Two Wastelands (TTW): the closest precedent for our launcher** (it builds from two owned games on the
player's PC).
- The installer needs both games with all DLC, **in English**, each run once; documented failures include
  Controlled Folder Access, quoted paths, CPU overheating (workaround `-threads:1`), slowness on Intel E-cores and
  Windows blocking the downloaded archive. Its post-install check is only "the folder size is 17 GB".
  **verified** (https://thebestoftimes.moddinglinked.com/faq.html)
- In 2013 (TTW 2.0) the installer could fail to patch the main BSA, and users compared output sizes by hand.
  **verified** (https://taleoftwowastelands.com/viewtopic.php@t=2111)
- TTW is at 3.4.0 (15 June 2026). **verified** (https://mod.pub/ttw/133/docs/25-faq-frequently-asked-questions)
- Lesson: their verification is weak (size, not hashes), and most support load is environment problems, not
  conversion bugs. **supported hypothesis**

**Skyblivion.** Volunteer team over 40 people (2021); Bethesda required 100% replaced assets; release moved from
2025 to 2026 in December 2025; an ex-developer alleged crunch in September 2025. No public beta is documented.
**verified** (https://en.wikipedia.org/wiki/Skyblivion). Its QA process: **unresolved** (not found).

**Sim Settlements 2 / kinggath.** Testing ran as a **Patreon-only closed beta** with alpha and beta build tracks,
updates every 7 to 10 days over about six months, feedback by Discord and comments. **verified**
(https://www.patreon.com/posts/24469236). Bug intake process: **unresolved**.

**Beyond Skyrim:** **unresolved** (search budget ran out).

### B. Automated testing in the Bethesda world

- **AutoTest (Skyrim SE, Muriel Salvan).** Papyrus suites driven by JSON (config, run lists, per-test statuses);
  `Locations` teleports to a cell or coordinate and spins a far third-person camera to catch CTDs; `NPCs` and
  `NPCsHead` spawn inventory-less copies in a test cell with AI off and screenshot them (neck gaps, black faces);
  it makes an `auto_test` save, skips tests already `ok`, can exit the game at the end, and updates status JSON in
  real time for outside tools. No performance suite. Needs SKSE, PapyrusUtil, SkyUILib, ConsoleUtil; FO4 "eligible
  but not tested". **verified** (https://github.com/Muriel-Salvan/AutoTest,
  https://www.nexusmods.com/skyrimspecialedition/mods/42520)
- **Lilac (Chesko).** Jasmine-style Papyrus unit and end-to-end tests (`it(...)`, `expectInt/Ref/Form`,
  `beEqualTo`, `beNone`); runs when a test quest starts, prints to the Papyrus log; an `enabled` flag prevents
  accidental runs; can ship inside a mod. Skyrim and Fallout 4 versions, last updated 2016, MIT. A Starfield port:
  **unresolved**. **verified** (https://www.nexusmods.com/fallout4/mods/18410,
  https://www.nexusmods.com/skyrim/mods/75652)
- **Starfield's own `Debug` script** lists `AutomatedTestLogDebug/Error/Progress`, `StartScriptProfiling`,
  `StartStackProfiling`, `StartStackRootProfiling`, `DumpEventRegistrations`, `DumpAliasData`, `ShowRefPosition`,
  `CenterOnCell`, `CenterOnCellAndWait`, `PlayerMoveToAndWait`, `EnableAI/Collisions/Detection/Menus`,
  `SetGodMode`, `ExecuteConsole`, `QuitGame`, `GetVersionNumber`, `GetConfigName`. **verified that they are
  declared** (https://dev.starfieldwiki.net/wiki/Starfield_Mod:Script-Debug). The wiki says the whole script is
  `DebugOnly` and does nothing on release builds; see Corrections: our bridge's `Debug.TraceUser` does work in
  retail, so that blanket statement is wrong at least for TraceUser. Which of the others work in retail is
  **unresolved**.
- **Papyrus remote debugger.** Starfield ships a VS Code Papyrus extension (`Tools\VSCodePapyrusAddon\
  vscodepapyrus-1.6.2.vsix`); `[Papyrus] bEnableRemoteDebugging=1`, `iRemoteDebuggingPort=20548`,
  `bLoadDebugInformation=1`; `[General] bAlwaysActive=1`, `bPauseOnAltTab=0` keep the game running when it loses
  focus. **verified** (https://starfieldwiki.net/wiki/Starfield_Mod:Debugging_Papyrus_with_VS_Code). Inference: a
  Debug Adapter Protocol client could read script variables without typing into the console. **supported
  hypothesis**, not tried by anyone I found.
- **Papyrus logging guide** for Starfield: `bEnableLogging`, `bEnableTrace`, `bLoadDebugInformation` = 1,
  `bEnableProfiling` = 0; Papyrus.0.log is the newest; MO2 profile ini can shadow My Games; pasted ini text can carry
  invisible characters that break it. **verified** (https://www.nexusmods.com/starfield/articles/780)
- **Spriggit (Mutagen).** Converts plugins to YAML or JSON, one file per record, for Git diffs and PRs; GPL-3.0.
  CLI: `serialize`, `deserialize`, `upgrade`, `formid-collision`, `merge-version-syncer`, and `standardize`
  ("writes a record-sorted copy of a plugin for binary comparison"). GameRelease values include **Fallout4 and
  Starfield**; Starfield needs master style information, either a `-d` data folder with the masters or "Known
  Masters" in a `.spriggit` file, which the docs call preferable on CI servers without game files. Each output
  records the translation package version. **verified** (https://github.com/Mutagen-Modding/Spriggit,
  https://mutagen-modding.github.io/Spriggit/cli/)
- Spriggit **omits** unused fields, unknown group header data, timestamps and unused condition parameters, and
  resets them to defaults on deserialize, so a round trip is not byte-identical. **verified**
  (https://mutagen-modding.github.io/Spriggit/omissions/)
- **xEdit scripting** exists for Starfield (SF1Edit, Pascal scripts via "Apply Script"), e.g. batch-editing FULL
  names. **verified** (https://www.nexusmods.com/starfield/mods/7610). Headless/command-line batch use of xEdit
  for CI: **unresolved** (not searched).
- **Console `bat` / `sStartingConsoleCommand`.** The line must sit under `[General]` of
  `StarfieldCustom.ini` in My Games (a user's commands loaded only partly until they moved it there); chaining
  several bat files in that setting is reported unreliable, and the workaround is one merged bat; some users report
  the game kept running an old bat. No length or command-count limits are documented there. **verified (as forum
  reports, not Bethesda docs)**
  (https://forums.nexusmods.com/topic/13253886-guide-how-to-properly-merge-mods-fixes-bat-files-sstartingconsolecommand-not-always-working)
- Automated **screenshot comparison** for Bethesda games: no tool found beyond AutoTest's capture-for-human-review.
  **unresolved** (search ran out).

### C. Crash diagnosis for Starfield

- **sf-crash-logger (0xra0, GPL-3.0).** SFSE plugin; exception handler installed at preload; a crash-durable
  breadcrumb trace (`CrashLogger_trace.log`) "that survives crashes that produce no dump"; access-violation
  classification (near-null, sentinel, debug-allocator poison) tied to a register; memory state at the fault;
  stack-overflow detection; SFSE plugins on the stack; faulting thread; an **8-hex crash signature to group
  duplicates**; register dump with RTTI type names; module list; **Plugins.txt load order**; system info including
  Wine/Proton; symbol names with a PDB; Address Library IDs from `versionlib-<ver>.bin` (v1/v2 and v5 formats);
  writes `crash_<timestamp>.log` and a **minidump** `.dmp` for WinDbg/VS to
  `Documents\My Games\Starfield\SFSE\Crashlogs\`. Dump size and supported game version not stated; 19 commits.
  **verified** (https://github.com/0xra0/sf-crash-logger). Maturity: **unresolved**.
- **Trainwreck (Ryan McKenzie) v1.4.0**, last updated 8 January 2024: call stacks, module list with SHA512 per
  module, script-extender plugin list, OS build, source locations with a matching PDB (it checks the PDB matches);
  claims compatibility with all game versions; SFSE or ASI loader. Registers/objects not confirmed.
  **verified** (https://www.nexusmods.com/starfield/mods/5068)
- **Starfield Engine Fixes (LarannKiar) v21.2**, SFSE: explicit support entry for **1.16.244** (our pinned version)
  since v20.0; optional **Detailed Crash Logger** (adds quest alias names, base forms of hazards and projectiles);
  `Dump Pointer Handles` (counts cell and reference handles, warns when low); `Dump Form Data`, `Deep Scan Load
  Order`; **BA2 Counter** (tracks archive count against the limit); 43 always-on vanilla fixes.
  **verified** (https://www.nexusmods.com/starfield/mods/10457)
- **Address Library for SFSE Plugins** (meh321) is the version-mapping database SFSE plugins use; plugins still
  ship updates per game patch (e.g. powerofthree's Tweaks lists 1.8.86, 1.14.70, 1.15.214 changes).
  **verified** (https://stepmodifications.org/wiki/Starfield:Address%20Library%20for%20SFSE%20Plugins,
  https://www.nexusmods.com/starfield/mods/3621)
- BetterConsole's author warns that hook-heavy SFSE plugins are fragile and recommends Trainwreck for crash detail.
  **verified** (https://www.nexusmods.com/starfield/articles/559)

### D. Navmesh and quest validation

- CK **Pathing Tests**: pick an actor (radius and height fill in), right-click two triangles; green path works,
  yellow fails and breaks where the problem is; ignores Havok objects and furniture; test large creatures where they
  appear. Manual, in the editor. **verified** (https://ck.uesp.net/wiki/Pathing_Tests; the page's example actor
  suggests Skyrim's CK, inference)
- Navmesh **Finalize**: "Finalize Cell Navmesh" leaves failing edges yellow; "Generation -> Advanced -> finalize"
  **deletes** triangles that fail. Advice: run "check navmesh" regularly and inspect deleted/skipped navmesh in
  xEdit. **verified for FO4's CK** (https://www.nexusmods.com/fallout4/articles/4209)
- Quest validation precedent is human checklists (Skywind above). Automated quest-graph validation tools for
  Creation Engine: **unresolved** (none found).

### E. Performance

- Gamers Nexus profiled Starfield with **PresentMon CLI**, four passes per result, differences inside run-to-run
  variance treated as noise, 500-frame excerpts; the game is **CPU-bound** at 1080p low on most CPUs (GPU Busy
  ratio 0.57 on a 13100F), near GPU-bound at 1080p ultra on a 13900K (0.99); slow RAM matters only at very low
  speeds; pre-patch build. **verified**
  (https://gamersnexus.net/cpus-game-benchmarks-graphics-guides/starfield-cpu-benchmarks-bottlenecks-intel-vs-amd-comparison)
- In-engine Papyrus profiling functions exist (section B); retail availability **unresolved**.
- Frame/CPU profilers injected into Creation Engine (Tracy-style): **unresolved** (not searched).

### F. General game-QA automation

- EA SEED (Battlefield 2042, Dead Space 2023): RL agents **augmented** scripted bots ("AutoPlayers") only for hard
  locomotion; ego-centric features (waypoints, distances, velocity) beat image input; **fast-forwarding the
  simulation caused physics failures** (parked helicopters fell through the ground); Dead Space ran only 7 agents
  vs 250 for BF2042 because single-player needs one process per agent; models must be retrained as the game
  changes. **verified** (https://arxiv.org/pdf/2307.11105)
- Lesson for us: scripted routes with ego-centric reads (what the bridge already logs) are the right core; vision or
  RL only for narrow gaps. **supported hypothesis**

## Precedents and what they teach us

| Precedent | What they did | What we take |
|---|---|---|
| Skywind label lifecycle | Developers "Claim Fix"; QA closes only after retest in a named build; "Known Shippable" for engine bugs | Map onto our PASS/FAIL ledger: a bug closes only when a runner or human PASS on a build id later than the fix exists. Add a "known shippable" class for Starfield engine bugs we can't fix. |
| Skywind "checklist required before QA" | A card can't enter QA without a checklist | Every new capability (doors, quests) needs its proof list in the inventory table before it gets in-game time. Our §2.1 table is this, keep it mandatory. |
| Skywind clean-install rule | Testers use a clean game + SKSE + SkyUI only | Community testers need a defined "clean Starfield" profile (no other plugins, SFSE pinned) or reports are noise. |
| Fallout London | Next-Gen patch broke tools and delayed release; crash logger merged after launch; 1-on-1 support | Pin versions (we do), and ship crash logging and a support bundle in release 1, not after. |
| TTW | Builds from owned games on the player's PC; verify = folder size; most failures are environment (CFA, language, CPU heat) | Launcher `verify` should hash outputs and preflight the environment (CFA, language, free disk, version), which TTW never did. |
| AutoTest | Locations "visit and spin camera" + NPC screenshot suites, JSON status, auto-exit | Confirms our smoke tier design; add the camera spin (loads all directions) and the NPC portrait sheet for the people-and-story phase. |
| Lilac | Papyrus unit tests run by a test quest | Our Papyrus (bridge, mission, map markers) has no in-engine unit test; a small Lilac-style harness could test it in one launch. |
| EA SEED | Hybrid scripted bots + RL; time acceleration broke physics | Don't speed tests up with timescale on physics-sensitive checks; keep reads ego-centric. |

## Risks

1. **Crash data drowns the disk or loses the crash.** Full dumps (18 GB) vs no dump at all. An SFSE crash logger
   would give a small dump plus a signature, but plugins load at preload and hook the engine; a crash logger bug
   could add its own crashes or mask ours. Likelihood medium: Trainwreck has not been updated since January 2024
   and sf-crash-logger's maturity is unknown. Mitigate by A/B on the same queue.
2. **"Debug" functions may be no-ops in retail.** If `ExecuteConsole`, `CenterOnCellAndWait` or the profiling calls
   are DebugOnly, plans built on them fail. Likelihood: high for some of them (the wiki says DebugOnly; our own
   Probe notes `GetFormEditorID` is DebugOnly). Cheap to probe.
3. **Spriggit diff noise or gaps.** Omitted fields reset on round trip; our writers may emit fields Spriggit treats
   as unknown (`-u ErrorOnUnknown` would tell us). Likelihood medium; impact low because it's a diff aid, not a
   build step.
4. **Human QA does not scale with breadth either.** Skywind needs 40+ people and monthly merges. Our owner is one
   person. Without a contact-sheet workflow (§2.6 of the next-phase note) visual review becomes the bottleneck.
   Likelihood high once interiors and world breadth land.
5. **Community reports are mostly environment noise** (TTW, Fallout London experience). Likelihood high at the
   GitHub release. Mitigation: a support bundle (load order, versions, crash signature, ledger fold) attached by
   the launcher.
6. **Performance regressions go unnoticed** because no test measures frame time; Starfield is already CPU-bound and
   our cells carry up to 6,049 references each (docs/terrain/core64c.md:271). Likelihood high at world breadth.
7. **Version pinning vs Steam updates.** Fallout London lost months to a Bethesda patch. A Starfield update would
   break SFSE, Address Library, crash loggers and our bridge's assumptions at once. Likelihood: medium per year.
8. **SFSE-dependent test tooling vs players without SFSE.** If test hooks need SFSE but play does not, tests run a
   different configuration from what players run. Likelihood medium.

## Questions for the framework

### New game
1. **Can the Vault 111 start be verified by a scripted "new game to first exit" run, and what are its checkpoints?**
   Why: phase 1's acceptance needs a repeatable proof, not one playthrough. Options: Skywind-style checklist
   (journal vs objective vs marker, items, dialogue order) run by a human; a runner scenario reading quest stages
   via FO4SF_Probe.Stage (#406); Debug.`AutomatedTestLogProgress` lines if retail honours them. Evidence: one PC run
   logging every stage transition with timestamps. Who: offline design + PC probe.
2. **How do we start a new game without the Starfield intro, unattended, every night?** Why: each test of phase 1
   starts from the main menu; the runner today loads saves. Options: a `bat` via `sStartingConsoleCommand` (forum
   reports say it must be in [General] and multiple bat chains are unreliable), Papyrus on game load, a scripted menu
   click. Evidence: PC probe of each, 5 runs each, success rate. Who: PC probe.
3. **Does `Debug.QuitGame` work in retail, so a run can end cleanly instead of killing the process?** Why: clean exits
   write logs and avoid false crash dumps. Evidence: one console `cgf "Debug.QuitGame"`. Who: PC probe (whitelist
   decision for the owner).

### Door animations
4. **What is the automated proof that a door played its animation, not just teleported?** Why: door_rounds proves
   arrival within 3 m; phase 2 is about the animation. Options: bridge log of animation events (if Starfield exposes
   them to Papyrus), a timed screenshot pair, the time between activate and load. Evidence: one door with logged
   events vs a door without the animation. Who: offline research of Starfield Papyrus events + PC probe.
5. **Should FO4 door animation bugs be tracked as "Known Shippable" when they come from the Starfield engine?**
   Why: Skywind's label stops endless re-tests of unfixable issues. Who: owner decision.

### All interiors
6. **What does tier-1 smoke add from AutoTest's Locations suite: a 360-degree camera spin after coc?** Why: a spin
   forces every direction's objects to load, so a CTD from one bad mesh shows up in smoke instead of during play.
   Evidence: run 20 known cells with and without spin; compare crash catches and time cost. Who: PC probe.
7. **Can we get navmesh validity offline before in-game tests?** Why: AutoTest and the runner only catch crashes,
   not broken pathing. Options: CK Pathing Tests (manual only), CK finalize that deletes failed triangles, xEdit
   inspection, our own connectivity checker over the converted NAVM (graph reachability between door markers).
   Evidence: our checker vs CK Pathing Test on 3 cells. Who: offline research + one CK session.
8. **Which interior regressions should be judged by screenshot diff, and with what tolerance?** Why: thousands of
   cells can't be eyeballed every build. Options: fixed camera at the cell's COC marker after a settle, perceptual
   hash vs the last accepted build, humans only see changed cells. No Bethesda-world tool found (unresolved). Evidence:
   noise floor of the same cell shot 5 times (lighting, particles, time of day). Who: PC probe.
9. **Do we need an NPC portrait sheet like AutoTest's NPCs suite (inventory-less spawn in a test cell, AI off)?**
   Why: neck gaps and black faces are the classic conversion faults; cheap to catch. Who: offline design, then
   PC probe once actors convert.

### Launcher
10. **What does the launcher's `verify` check that TTW's "folder is 17 GB" didn't?** Why: our users build on their
    own PCs; TTW's failures were environmental (Controlled Folder Access, language, CPU heat, E-cores). Options:
    hash every output against a shipped manifest (ids, not assets), preflight CFA, game language, disk, FO4 and
    Starfield versions, and tier-0 + short tier-1. Evidence: run the build on a second PC and diff hashes. Who:
    offline + a second machine (community contact).
11. **Do we ship an SFSE crash logger with the launcher, and which one?** Why: Fallout London merged Buffout 4 only
    after a rough launch. Options: sf-crash-logger (minidump, signature, breadcrumbs, load order; GPL-3, compatible
    with our GPL-3 notice), Trainwreck (stack + module hashes; not updated since Jan 2024), Starfield Engine Fixes'
    Detailed Crash Logger (supports 1.16.244). Evidence: deliberately trigger a known crash (the Havok collision
    assertion from 16 Oct) with each and compare output and dump size. Who: PC probe + owner decision.
12. **Does the support bundle a player attaches carry the crash signature, load order, versions and the ledger fold,
    and nothing personal?** Why: community reports are mostly noise otherwise (TTW/FOLON). Who: offline design,
    owner decision on what is collected.
13. **Do we require SFSE for players, or only for testing?** Why: if crash logging and probes need SFSE, play
    without SFSE is an untested configuration. Options: require it (brief allows); two profiles with a reduced
    smoke on the no-SFSE one. Who: owner decision.

### World and planet
14. **What is our reproducible performance protocol, and which number is the budget?** Why: Starfield is CPU-bound
    at low settings (GN), our cells are dense; breadth makes frame time the first complaint. Options: PresentMon CLI
    on a fixed walk (Red Rocket to Sanctuary already passes), N passes, report the variance band and 1% lows,
    record in docs/ai/optimization.md per build. Evidence: 4 passes on two builds to find the noise floor. Who: PC
    probe.
15. **Should exterior smoke watch handle and archive counts?** Why: Starfield Engine Fixes can count cell and
    reference handles and warn when low, and count BA2 archives against the limit; a whole Commonwealth plus DLC on
    one planet may approach both. Evidence: one run with Dump Pointer Handles on at 3x3 hops. Who: PC probe.
16. **Is timescale acceleration safe for day/night and weather tests?** Why: EA SEED saw physics break when the sim
    was fast-forwarded. Options: SetLocalTime jumps (already whitelisted) rather than a high timescale. Who:
    PC probe comparing both on havok-heavy cells.
17. **Can route walks become bots that walk navmesh paths instead of fixed key holds?** Why: hand-planned walks
    break on rebuilds; `PlayerMoveToAndWait` (if retail) or an AI package on the player could walk between door
    markers. Evidence: probe `Debug.PlayerMoveToAndWait` in retail. Who: PC probe.

### People and story
18. **What is our quest test checklist, and how much of Skywind's guideline applies?** Why: quests are the biggest
    human-QA load in every TC. Items to adopt: test every branch, try to break order, journal/objective/marker as
    three checks, items droppable, dialogue that bypasses conditions. Who: owner decision + offline.
19. **Can quest stage reads go through `Debug.DumpAliasData` or the Papyrus remote debugger instead of new console
    commands?** Why: the next-phase note prefers FO4SF_Probe over whitelisting `GetStage`; the debugger (port 20548)
    might read state with no game input at all. Evidence: attach a DAP client to retail with
    `bEnableRemoteDebugging=1` and read a quest variable. Who: PC probe.
20. **Do we port Lilac-style Papyrus unit tests to Starfield for our scripts (bridge, mission, map markers, later the
    quest ports)?** Why: today Papyrus is tested only by parsing source in Python tests and end-to-end in game.
    Options: port Lilac (MIT, single script), write our own minimal `expect` harness started by a test quest. Who:
    offline + one compile on the PC.

### Fallout systems
21. **For Pip-Boy, VATS, workshop and power armor, which proofs can be machine-read?** Why: these are UI- and
    input-heavy, and our runner can only type whitelisted console lines. Options: Papyrus events logged by the bridge
    (menu open/close, item added, workshop object placed), screenshot checkpoints, human sessions with the report
    kit. Who: offline research per system.
22. **Does a Starfield update need a "freeze" policy like Fallout London learned the hard way?** Why: one patch broke
    FOLON's toolchain. Options: Steam beta branch pinning, documented downgrade, block launches on version mismatch
    (preflight). Who: owner decision + offline research.

### Release and community
23. **Do we adopt Skywind's lifecycle labels (Confirmed, Claim Fix, In Current Build, Fix Fail, Closed Fixed, Known
    Shippable)?** Why: our labels track agent work, not bug state across builds. Option: map them to ledger states
    so a fix closes only on a later build's PASS. Who: owner decision.
24. **Closed tester pool before the Nexus release: Patreon-style (SS2), Discord role (Skywind), or open GitHub?** Why:
    SS2 ran a ~6-month closed beta with 7 to 10 day cadence; Skywind gates issues behind a Triage role. Who: owner
    decision.
25. **What is a "clean test profile" for community testers?** Why: Skywind insists on clean game + SKSE + SkyUI;
    mixed mod lists make reports unusable. Option: launcher checks Plugins.txt against an allowed list and stamps
    the result into reports. Who: owner decision + offline.
26. **Will we offer FOLON-style 1-on-1 help, or a self-diagnosis tool instead?** Why: support time is the owner's
    scarcest resource. Who: owner decision.

### Tooling and testing
27. **Do we snapshot every built plugin with Spriggit into a (non-public, asset-free?) text tree and diff builds?**
    Why: compare-ids diffs ids; Spriggit diffs every field, per record, which turns "v6 broke doors" into a list of
    changed records. Caveats: output may contain copyrighted text (names, dialogue), so it must not go into Git if
    that counts as assets; omitted fields reset. Evidence: serialize FO4Port.esm with `-u` (error on unknown) and see
    whether our writers emit anything Spriggit can't read. Who: offline (CI can use Known Masters) + owner decision on
    where snapshots live.
28. **Can Spriggit's `standardize` or a Mutagen round trip be a writer validator in tier 0?** Why: if Mutagen can
    read and re-write our plugin identically (after standardize), the plugin is structurally sound by an
    independent parser. Evidence: run on current esms; count diffs. Who: offline (repo has dotnet/ Mutagen writers).
29. **Does xEdit's "Check for Errors" run headless on our plugins, and should it gate builds?** Why: it's the
    community's de-facto validator. Status: command-line batch mode unresolved (search budget). Who: offline research.
30. **What is the crash triage pipeline: signature, dedupe, bisect?** Why: the next-phase note plans bisection;
    sf-crash-logger's 8-hex signature would let the runner say "same crash as cell X" and mark FAIL CRASH on the
    second identical signature without a 18 GB dump. Evidence: two forced crashes, same and different, compare
    signatures. Who: PC probe.
31. **Which Starfield Debug functions are live in retail?** A one-launch probe list: `TraceUser` (known yes),
    `AutomatedTestLogProgress`, `StartScriptProfiling`, `DumpAliasData`, `CenterOnCellAndWait`,
    `PlayerMoveToAndWait`, `ExecuteConsole`, `QuitGame`, `GetConfigName`. Why: each one that works removes a console
    whitelist decision or a keystroke. Who: PC probe (owner whitelists `cgf "Debug.<fn>"`).
32. **Where do the Papyrus profiling outputs go and what do they cost?** Why: scripted systems (workshop, radio)
    will add Papyrus load; `bEnableProfiling` exists in the ini. Who: PC probe after 31.
33. **Can the remote Papyrus debugger be an observation channel that never types into the game?** Why: typing is
    the runner's most fragile part (focus, Alt+Tab). Needs `bAlwaysActive=1`, `bPauseOnAltTab=0` anyway, which may
    also fix focus-loss flakiness. Who: PC probe.

### Cross-cutting
34. **How many human-review minutes per build can the owner give, and what gets them?** Why: every TC relies on
    humans; we have one. Options: contact sheet of only changed screenshots; rotate a 10% random sample. Who: owner
    decision.
35. **When we add FO3/New Vegas, does the test inventory generalise?** Why: TTW's experience (two games, one
    engine) says installers and verification multiply. Option: the inventory planner keyed by source game. Who:
    offline design.

## Corrections

- **External source, not a project note:** the Starfield wiki's Debug script page says the whole script is flagged
  `DebugOnly` so "none of these functions work in release" builds
  (https://dev.starfieldwiki.net/wiki/Starfield_Mod:Script-Debug). The project's bridge calls
  `Debug.TraceUser("fo4sf", ...)` (scripts/bridge/FO4SF_Probe.psc:21, FO4SF_Bridge.psc:19) and the runner reads
  those lines from the retail game's user log (scripts/game/bridge_log.py), so at least `TraceUser` works in retail.
  The page's blanket statement is wrong or out of date; per-function status is unresolved (question 31). Our own
  FO4SF_Probe.psc already notes that `GetFormEditorID` is DebugOnly, consistent with per-function flags.
- No errors found in testing-automation.md or PLAY-AND-TEST.md. One gap: PLAY-AND-TEST's crash section offers only
  ProcDump; an SFSE crash logger would give players a small, shareable log (the guide rightly forbids sharing
  dumps), pending question 11.

## Sources

- https://handbook.tesrskywind.com/qa/bug-reporting
- https://handbook.tesrskywind.com/qa/onboarding
- https://handbook.tesrskywind.com/dev/quest-testing-guidelines
- https://github.com/TESRSkywind/QA/issues (linked from the handbook; not opened)
- https://overclock3d.net/news/software/fallout-london-is-in-its-final-stage-of-qa-testing-at-gog/
- https://pcgamer.com/games/rpg/fallout-london-devs-are-working-on-a-huge-patch-offering-dedicated-1-on-1-troubleshooting-sessions-to-help-players-with-installs-and-crashes
- https://thebestoftimes.moddinglinked.com/faq.html
- https://taleoftwowastelands.com/viewtopic.php@t=2111
- https://mod.pub/ttw/133/docs/25-faq-frequently-asked-questions
- https://en.wikipedia.org/wiki/Skyblivion
- https://www.patreon.com/posts/24469236
- https://github.com/Muriel-Salvan/AutoTest
- https://www.nexusmods.com/skyrimspecialedition/mods/42520
- https://www.nexusmods.com/fallout4/mods/18410
- https://www.nexusmods.com/skyrim/mods/75652
- https://dev.starfieldwiki.net/wiki/Starfield_Mod:Script-Debug
- https://starfieldwiki.net/wiki/Starfield_Mod:Debugging_Papyrus_with_VS_Code
- https://www.nexusmods.com/starfield/articles/780
- https://github.com/Mutagen-Modding/Spriggit
- https://mutagen-modding.github.io/Spriggit/
- https://mutagen-modding.github.io/Spriggit/cli/
- https://mutagen-modding.github.io/Spriggit/omissions/
- https://www.nexusmods.com/starfield/mods/7610
- https://forums.nexusmods.com/topic/13253886-guide-how-to-properly-merge-mods-fixes-bat-files-sstartingconsolecommand-not-always-working
- https://github.com/0xra0/sf-crash-logger
- https://www.nexusmods.com/starfield/mods/5068
- https://allmods.net/starfield-mods/starfield-miscellaneous/trainwreck-a-crash-logger-v1-1/
- https://www.nexusmods.com/starfield/mods/10457
- https://www.nexusmods.com/starfield/mods/3621
- https://stepmodifications.org/wiki/Starfield:Address%20Library%20for%20SFSE%20Plugins
- https://www.nexusmods.com/starfield/articles/559
- https://www.nexusmods.com/starfield/mods/857
- https://ck.uesp.net/wiki/Pathing_Tests
- https://www.nexusmods.com/fallout4/articles/4209
- https://gamersnexus.net/cpus-game-benchmarks-graphics-guides/starfield-cpu-benchmarks-bottlenecks-intel-vs-amd-comparison
- https://arxiv.org/pdf/2307.11105
- Repo files read: docs/PLAY-AND-TEST.md, docs/SETUP.md, docs/PLAN.md, docs/RISKS.md, scripts/bridge/FO4SF_Probe.psc,
  scripts/bridge/FO4SF_Bridge.psc (grep), docs/terrain/core64c.md:271; research/next-phase/testing-automation.md.

## Wave 2 additions (2026-10-19)

Added by a wave-2 research agent (Claude). Wave-1 text above is unchanged. It reads the pages wave 1 could not (Skywind
QA FAQ and QA Fixes Guide, Spriggit workflow, crash-logger changelogs) and answers the xEdit batch-mode gap from the
xEdit source. Labels as above.

### W2-1. xEdit command-line and unattended modes (answers Q29; corrects the "headless" framing)

All **verified** from the xEdit source, branch `dev-4.1.6` (`xEdit/xeInit.pas`, `xEdit/xeMainForm.pas`,
`Core/wbInterface.pas`, `xEdit.dpr`) at https://github.com/TES5Edit/TES5Edit , and from the What's New page
https://tes5edit.github.io/docs/18-whatsnew.html :
- Game mode is chosen by `-SF1` / `-FO4` etc. or the exe name (`SF1Edit.exe`). Tool modes are chosen the same way:
  `edit, view, lodgen, script, translate, onamupdate, masterupdate, masterrestore, setesm, clearesm, sortandclean(masters),
  checkforerrors, checkforitm, checkfordr`.
- **`checkforerrors` is an unattended mode with an exit code**: it loads, runs Check for Errors on the last loaded file,
  never saves, and sets `ExitCode` to the error count capped at 127 (`checkforitm` / `checkfordr` do the same for
  identical-to-master records and deleted references). This is exactly a build gate.
- `-autoload` skips the module-selection dialog and loads what `plugins.txt` marks active; `-P:<file>` points at a
  custom plugins list; `-D:<path>` sets the data folder; `-autoexit` closes after Quick (Auto) Clean, LODGen or Script.
  `-script:"x.pas"` (or a script file named on the command line) enters Script mode and runs it after loading;
  `-testconflicts:<file>` writes a conflict report and returns exit code 255 on a mode clash; `-generateseq:<plugin>`
  writes an SEQ (Skyrim-only menu, see people-story.md W2-1). `-R:<file>` sets a log file.
- **Not headless**: xEdit is a VCL GUI app (`Application.Initialize`, a main form); these modes run "without user
  interaction until final status" but still open a window. The xEdit team declined full CLI automation in 2019
  ("not a current focus nor have we ever wanted to fully automate that"; closed as not planned 2025).
  https://github.com/TES5Edit/TES5Edit/issues/655
- Starfield cost (**verified**, What's New 18.15.1.2.1): first SF1Edit start builds reference info using 4 to 5 GB RAM
  and over 10 minutes; later starts load the cache in seconds. So a CI gate needs a persistent cache directory (`-C:`).
- Answer to Q29 (**supported hypothesis**): yes, xEdit can gate builds on Windows (or under Wine on Linux CI, untested)
  as `xEdit.exe -SF1 -checkforerrors -autoload -P:<our plugins.txt> -D:<data>` and read the exit code; it is
  "unattended", not windowless. Untested whether it runs under Wine on a display-less runner (needs Xvfb at least).

### W2-2. Skywind QA FAQ and QA Fixes Guide (deepens the Skywind lifecycle in §A)

- **verified**: QA FAQ: a dated "not finished as of January 2026, do not report" list (Red Mountain exteriors, Redoran
  areas, navmesh in many areas, steep stairs, most voice acting, placeholder models, missing textures shown blue/purple,
  creatures, crafting systems, balancing; "many Skyrim physics/engine bugs" cannot be fixed). One issue per root cause,
  split by department; keep the most complete duplicate. Testers are encouraged to learn the CK and may attach fixes
  to a GitHub issue using a template for lead review. https://handbook.tesrskywind.com/qa/frequently-asked-questions
- **verified**: level-design cards reaching QA carry a report from an automated **LD Review tool**; nothing may be marked
  Fail, items marked Review get extra attention. Same FAQ and https://handbook.tesrskywind.com/qa/onboarding . This is
  the closest precedent found for an automated per-cell pre-QA check (its checks are not described).
- **verified**: QA Fixes Guide: floating clutter is usually a collision mismatch (F4 in the CK shows collision), which
  is "QA Blocked" for 3D, not a level-design failure; gaps into the void and z-fighting are level-design faults; texture
  seams are 3D; replace objects with Ctrl+F (Selection Only) to keep teleport markers and scripts.
  https://handbook.tesrskywind.com/qa/qa-fixes-guide
- **verified**: onboarding: QA installs a clean Skyrim SE with only SKSE and SkyUI; builds are ~18 GB zipped / 30 GB
  unzipped, monthly merges with 2-3 hotfixes in the first week, distributed by Resilio P2P (preferred) and OneDrive;
  GitHub is not used for builds ("we tried to make it work and had a boatload of problems").
  https://handbook.tesrskywind.com/qa/onboarding
- For us (**supported hypothesis**): (1) publish a dated "known unfinished, do not report" list with each tester build
  (Q24/Q25); (2) the "QA Blocked vs Fail" split maps onto our converter-vs-engine triage: a collision mismatch after
  `meshcollision.py` is a converter bug, a floating object with matching collision is a placement bug; (3) our
  per-cell automated report (testqueue) is the analogue of the LD Review tool and should gate what humans see.

### W2-3. Spriggit workflow and versioning (deepens Q27/Q28)

- **verified**: Workflow page: plugin to `.yaml`/`.json` in a Git repo, commit, collaborators deserialize back to a
  plugin, edit, re-serialize, pull request. https://mutagen-modding.github.io/Spriggit/workflow/
- **verified**: translation logic is in NuGet packages (`Spriggit.Yaml.<Game>`, `Spriggit.Json.<Game>`), downloaded at
  run time by name and version; each text tree is stamped with the package version so old trees deserialize with the
  old package. Upgrades should be a dedicated commit (`Spriggit.CLI.exe upgrade -p <dir> -v <ver>`, then review the
  diff) to avoid "ambush diffs". https://mutagen-modding.github.io/Spriggit/translation-packages/ ,
  https://mutagen-modding.github.io/Spriggit/upgrade-practices/
- For us (**supported hypothesis**): pin the Spriggit package version in the build (it is fetched from nuget.org at run
  time, so offline CI needs a local NuGet cache), and treat a Spriggit version bump like a toolchain bump: its own
  commit, its own baseline diff.

### W2-4. Crash logger changelogs (answers "maturity unresolved" for sf-crash-logger; Q11, Q30)

- **verified**: sf-crash-logger: four releases, v0.1.0 (16 Jun 2026) to **v0.4.0 (10 Jul 2026)**, ~20 commits
  (co-authored with Claude per the commit list), no activity shown after 10 July. v0.3.0 added Address Library IDs from
  `versionlib-<ver>.bin` (omitted if no matching database), fault-to-register correlation, poison-pattern recognition and
  the `Plugins.txt` load order. v0.4.0 added the **version-stable 8-hex crash signature** (hash of exception code,
  access type and the Address Library IDs of the fault site and three callers; tokens printed so it can be
  reproduced; withheld if the game module cannot be located), a dedicated reporter thread so stack overflows produce
  a report, dbghelp-independent unwinding, Wine/Proton detection, and fixed `/EHa` (earlier builds' guarded reads did
  not catch access violations). Its notes say raw `__fastfail` cannot be caught by any plugin (use `PROTON_LOG=1` on
  Proton) and that results were "measured under Wine 11.7". https://github.com/0xra0/sf-crash-logger/releases ,
  https://github.com/0xra0/sf-crash-logger/commits
- **verified**: Crash Logger SSE (Skyrim, alandtse) is the mature sibling: v1.19 to **v1.25.0 (21 Aug 2026)** in 2026,
  adding stack-overflow survival and null-function-pointer caller recovery (1.23.0), `__fastfail` logging via VEH
  (1.24.0), navmesh/NiSkin/NIF-model introspection (1.21.0), BGSLocation/SpellItem introspection (1.22.0).
  https://github.com/alandtse/CrashLoggerSSE/releases
- Change to wave 1 (**supported hypothesis**): sf-crash-logger is young (one month of releases, one maintainer,
  Proton-tested) and its crash signature only became version-stable in v0.4.0, so treat it as a candidate for test
  runs, pinned by version and checked against a deliberate crash (Q30), not yet as the launcher's shipped logger
  (Q11). Starfield Engine Fixes' optional Crash Logger (wave 1) remains the more established player-facing option.

### Wave 2 sources (testing-qa)

- https://github.com/TES5Edit/TES5Edit (dev-4.1.6: xEdit/xeInit.pas, xEdit/xeMainForm.pas, Core/wbInterface.pas, xEdit.dpr)
- https://tes5edit.github.io/docs/18-whatsnew.html , https://github.com/TES5Edit/TES5Edit/issues/655
- https://handbook.tesrskywind.com/qa/frequently-asked-questions , https://handbook.tesrskywind.com/qa/qa-fixes-guide ,
  https://handbook.tesrskywind.com/qa/onboarding
- https://mutagen-modding.github.io/Spriggit/workflow/ , https://mutagen-modding.github.io/Spriggit/translation-packages/ ,
  https://mutagen-modding.github.io/Spriggit/upgrade-practices/
- https://github.com/0xra0/sf-crash-logger/releases , https://github.com/0xra0/sf-crash-logger/commits
- https://github.com/alandtse/CrashLoggerSSE/releases
