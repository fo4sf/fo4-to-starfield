# Launcher phase: question framework

Owner: the Launcher thread (Claude-cloud). Written 2026-10-19 from 17:50Z on the owner's ask (17:41Z): research the
modding communities, tools and precedents, and build a framework of questions for the next phases. The Next-phase
research framework thread folds this file into its README and the repo mirror; send edit requests through it.

Labels: **verified** (a source read or a measurement, named), **supported hypothesis**, **unresolved**. Every finding
here is a lead until it is checked again against its source; several web pages were rate-limited during the research.
Each question says who answers it: **owner** (a decision), **PC** (a read-only or staged probe on the owner's PC),
**offline** (cloud code, tests or reading), **outside** (Nexus staff, Bethesda, a lawyer, a community tester).

Builds on, does not repeat: research/next-phase/launcher-architecture.md, research/next-phase/launcher-gamma-model-and-community-tools.md,
docs/ai/launcher-backbone.md (PR #394). Raw research, with every source URL, in
`research/framework/launcher-sources/` (installers-precedents, sfstack, fo4source, appeng, community, buildorch, eula). Also
read from the framework thread's wave 1: findings/distribution-community.md, versions-performance.md, testing-qa.md,
precedents.md, legal-policy.md.

---

## 0. The owner's decisions, in one list

These change what everything else builds. Each has a recommended default; nothing is built against an undecided one
except as reversible groundwork.

| # | Decision | Recommended default | Why |
|---|---|---|---|
| D1 | Which Fallout 4 data versions to accept (1.10.163 only, or also next-gen 1.10.984 and current 1.11.240) | 1.10.163 first (what the owner has), then add 1.11.240 once a record diff shows how far it differs | Most players are on 1.11.240 now (fo4source §1, versions-performance Q7); Fallout London forced a downgrade and paid for it in support load |
| D2 | Which stores to support (Steam, GOG, Game Pass, Epic) for Fallout 4 and Starfield | Steam for both; GOG Fallout 4 as soon as one GOG install is hashed; Game Pass and Epic refused with a clear message until tested | TTW, Wabbajack and Skyblivion exclude the Microsoft Store; SFSE is Steam-only; Epic can't roll back (installers-precedents §1, §7; sfstack §1) |
| D3 | Starfield runtime policy after a Steam update | refuse to build or launch on an unknown Starfield.exe hash, keep a known-good table, tell the player how to stay on the last good build | Starfield shipped 1.16.236, .242 and .244 between April and June 2026; updates broke SFSE twice (sfstack §1) |
| D4 | Where the built game goes: our own folder plus restore, an MO2 instance, or a Vortex package | our own install plus snapshot and restore (built), with an MO2 mod-folder export later | MO2's last public build is 2.5.2 (Aug 2024) with 2026 reports of disabled masters, though wave 1 says it handles Starfield natively; Vortex 1.10.5 is current (sfstack §4; distribution-community); TTW builds an MO2 mod folder |
| D5 | Hosting order and the Nexus question | GitHub first (settled 07:0xZ), and a written question to Nexus staff before any upload | Nexus file rules updated 2026-09-29 ban internet-connecting executables by default; TTW was kept off Nexus at Bethesda's request (TTW's account); FNV to FO4, a converter that needs both games, has lived on Nexus since 2023 (community §2-3; distribution-community) |
| D6 | Ask ZeniMax for written permission before a public release, and what to ask | the owner decides; the research now leans toward asking, because no licence text covers what we do | ~~the Starfield CK EULA's clause (ii) offers an approval route for cross-game mods~~ [Correction, eula.md: clause (ii) ends "to be distributed through Bethesda Creations (hereinafter, "Creations Paid Content")", so it is the paid-Creations route only.] The Fallout 4 licences are the stronger obstacle: ToS §3 licenses content "solely in connection with such Service", and the Fallout 4 Steam EULA says material made with its tools is "used exclusively in combination with" Fallout 4 (verified, eula.md §4). Not legal advice |
| D7 | Does the launcher use the internet at all | offline by default; update check only on the player's click, from GitHub Releases; the hash tables ship inside the release | the Nexus rule above; antivirus profile; trust (community Q4) |
| D8 | Licence of the launcher binary | keep MIT for our code, ship the Mutagen tools as separate GPL-3 programs called by command line and JSON, with source on the same release | GPL FAQ treats command-line and pipe communication as separate programs unless they exchange "complex internal data structures" (community §6); relicensing everything GPL-3 is the simple fallback |
| D9 | Save promise across core versions | 0.y.z with a "save compatible: yes/no" line per release; the launcher blocks a core swap under a save when same-ids says IDS_DIFFER | v6c to v6e changed 010027A0 from DOOR to STAT under the same FormID (PR #394); saves store changed forms with their record type (buildorch §9) |
| D10 | The launcher's UI stack | a Python command line first (exists), then a PySide6 window that runs the same command line as a separate process | Python core exists; Qt has MO2 and LOOT precedent; LGPL is fine for an open-source tool; a CLI keeps Linux and Steam Deck possible (appeng Q1; distribution-community Q12) |
| D11 | Code signing | apply to SignPath Foundation (free for open source); paid signing only if it refuses | EV certificates no longer skip SmartScreen (Microsoft, 2024); SignPath wants named roles and MFA, which our one shared GitHub account may not meet (appeng §3) |
| D12 | Support channel and AI disclosure | GitHub Issues with a log-bundle form first; a plain AI-assisted disclosure on the release page, and a "no AI voices or art in outputs" promise if the owner agrees | every comparable project is Discord-first; Nexus added AI tags on 2026-07-29 and the mood is hostile (community §4, §7) |
| D13 | Add-on rules for mods built on the core | original content plus FormID references only, no converted assets, no paywall, never re-upload generated output | Bethesda's Community Standards ban monetised mod projects; Wabbajack forbids uploading tool outputs (community Q8, Q18) |

---

## 1. Sources: the player's Fallout 4

**Known.**
- Fallout 4 PC versions (verified, F4SE source header): 1.10.163 (last old-gen), 1.10.980 (next-gen, April 2024),
  1.10.984, 1.11.137 (Anniversary Edition), 1.11.159/169/191/221, 1.11.240 (current; one secondary source dates it
  2026-08-18 and says it raised the BA2 limit from 256 to 1024).
- The owner's Fallout4.esm is 330,745,373 bytes, the size one community delta patcher gives for 1.10.163; the next-gen
  file is 330,777,465 (supported hypothesis: no community source publishes hashes). Steam manifests carry a SHA-1 per
  file, so the label can be made verified from the depot manifest (fo4source Q1).
- The owner's data sits in Steam depot-download folders (`steamapps/content/app_377160/depot_*`), not a normal install;
  no existing tool reads that layout, and our measurement lists `Fallout4 - Meshes.ba2` twice with different file counts
  (42,409 and 42,416) (fo4source §3, repo).
- The four missing DLC are missing because only depots 377163, 435871 (Automatron English) and 435880 (Wasteland
  Workshop) were downloaded (supported hypothesis, from the downgrader's depot table).
- Creation Club content is separate plugins loaded through `Fallout4.ccc`, never merged into the seven masters
  (verified, fo4source §6); the Anniversary Edition adds about 150 of them.
- BA2 v7 and v8 (next-gen) have the same 24-byte header as v1 per xEdit and OpenMW source (verified); our `ba2.py`
  accepts v1 to v3 only. All 50 of the owner's archives are v1.
- Install detection (verified in MO2 and LOOT source): registry `HKLM\Software\[WOW6432Node\]Bethesda Softworks\Fallout4`
  "Installed Path"; Steam `HKCU\Software\Valve\Steam` SteamPath then `config\libraryfolders.vdf` (app 377160); GOG
  `HKLM\Software\GOG.com\Games\1998527297` "path"; Game Pass `<drive>\.GamingRoot` then `Fallout 4 (PC)\Content`;
  Epic launcher `Manifests\*.item`. Store can be told from the exe (F4SE's checks: a `.bind` section for Steam,
  `Galaxy64.dll` for GOG, eossdk for Epic).
- Languages: all 11 string tables ship in the language-neutral `Fallout4 - Interface.ba2`; voices come from
  per-language depots; the game picks by `sLanguage` (verified, fo4source §9).

**Questions.**
- S1. Is the owner's Fallout4.esm 1.10.163 on bytes? Compare our sha256 table with the SHA-1 list of depot 377163
  manifest 5819088023757897745 (`DepotDownloader -manifest-only`). **PC.**
- S2. What are the 1.10.163 hashes of DLCCoast, DLCworkshop02, DLCworkshop03 and DLCNukaWorld? The owner downloads the
  four depots, then `launcher.py sources-add`. Blocks a complete detect. **owner + PC.**
- S3. How far does 1.11.240 differ from 1.10.163 in records and FormIDs? A record diff of the two Fallout4.esm files
  with our reader decides D1. **PC** (one current download) **+ offline.**
- S4. Do the DLC esm hashes differ per language? Compare an English and a German depot download. Decides whether
  `known_sources.json` needs a language column. **PC.**
- S5. Do we accept the depot-split layout, merging in a fixed depot order, or require a normal install? And which
  `Meshes.ba2` wins? **owner + offline** (a merge rule and a test that it equals a normal install's file set).
- S6. What does detect do with a modded Fallout 4 Data folder (Vortex hard links, loose files, ENB)? Default: the
  vanilla set is the files whose hash is in our table; everything else is ignored and listed. **offline.**
- S7. Are Creation Club files inputs, ignored, or a refusal? Default: ignored (we read only the seven masters and
  their archives), listed in detect. **owner.**
- S8. Is a GOG or Game Pass Fallout 4 readable and on which version? Needs a community tester's file list and
  hashes. **outside.**
- S9. Should the BA2 reader accept v7 and v8? Header bytes of one next-gen archive settle it; then a synthetic
  fixture per version. **PC + offline.**
- S10. Does a refusal for missing DLC print the exact `download_depot` commands? Only after the manifest IDs are
  cross-checked (the downgrader's table has a duplicated Nuka-World French and Russian row). **offline.**

## 2. Target: the player's Starfield

**Known.**
- Current runtime 1.16.244 (2026-06-11), SFSE 0.2.21 (sfstack §1, verified). Version pinning works with Steam's
  `download_depot` on app 1716740 (depots 1716741/1716742) and auto-update off. No source says an update broke plain
  ESM plus BA2 content, which is all we ship (supported hypothesis).
- Plugin types: full masters 253 slots; medium 256 plugins of about 65,535 new records each; small 4,096 of 4,095
  records. A plugin never records what type its masters were, so a released plugin's type can never change
  (sfstack §2, verified). Our core holds 683,870 records (repo), so it has to stay a full master.
- Plugins.txt: a header line plus `*Name.esm` per enabled plugin; the game rewrites it at start, dropping missing and
  implicit plugins and adding new ones unticked. Any `sTestFile1..10` entry makes the game ignore Plugins.txt
  entirely (verified, sfstack §3; MO2 and Vortex both say so).
- Blueprint plugins load last and can't be overridden; `BlueprintShips-Starfield.esm` as a master causes order shifts;
  tool makers agreed in May 2026 never to write blueprint plugins to Plugins.txt (sfstack §3).
- Archives: vanilla is v2 GNRL, v2 DX10 and v3 DX10 (our measurement). The engine allows 256 active BA2s per
  registry and about 78 are vanilla on the owner's install; players with big mod lists crash or lose assets (sfstack
  §6). Archive2's licence (the CK EULA) forbids copying or redistributing it, so players need their own Creation
  Kit. The open-source `ba2` Rust crate (0BSD) claims Starfield read and write.
- Starfield reads loose files from a second Data folder under Documents\My Games\Starfield (appeng §6); the owner's
  install reads no loose files (`sResourceDataDirsFinal=STRINGS\`).
- Any external plugin flags the save as modded and turns achievements off (sfstack §4).

**Questions.**
- T1. Which Starfield runtimes do we support, and do we block unknown ones? Record Starfield.exe version and sha256
  in the build manifest (done) and a known-good table (to build, like `known_sources.json`). Decides D3. **owner +
  offline.**
- T2. How many BA2s will the full port ship, and how many slots will players have left under the 256 limit? Count the
  converter's planned archives against 256 minus 78. If it does not fit, fewer, larger archives. **offline.**
- T3. Is there a per-archive size cap for Starfield (Fallout 4 breaks above 4 GB)? Build a 4.5 GB test BA2 and read an
  asset past the 4 GiB offset in game. **PC** (later, with the owner's word for any in-game test).
- T4. Who packs the BA2s: the player's Archive2 (needs the Creation Kit, whose minimum spec is 32 GB RAM), or an
  open-source writer? Byte and in-game parity test of the `ba2` crate against Archive2 for v2 GNRL and v3 DX10.
  **offline + PC**; the EULA reading on a launcher driving the player's own Archive2 is **owner / outside.**
- T5. Does the launcher keep our order in Plugins.txt after the game rewrites it? A launch, close and diff test,
  repeated with Creations installed and offline. Default: re-assert our own lines before each launch, never move
  plugins we don't own. **PC.**
- T6. Does detect refuse while any INI has `sTestFile` set? Default yes, naming the file and line; the test chain's own
  use is checked first (`grep sTestFile`). **offline.**
- T7. Do our plugins avoid `BlueprintShips-Starfield.esm` as a master? A unit test on MAST lists. **offline.**
- T8. Does a player's Documents\My Games\Starfield\Data folder hold files that override ours? The snapshot should
  record it read-only and warn on overlaps. **offline** (snapshot change) **+ PC** (read the owner's).
- T9. Does `.wem` audio play from a compressed GNRL archive? One forum report says relocated `.wem` in compressed
  archives does not. **PC** (later).
- T10. Which form version and HEDR version must our plugins carry, and does a patch change them? Compare Starfield.esm
  across 1.16.236 and 1.16.244 and pin a guard test. **offline.**
- T11. Is Game Pass Starfield usable (folder access, Plugins.txt, no SFSE)? Needs one Game Pass tester. **outside.**

## 3. Build: time, disk, determinism, resume

**Known.**
- On one PC, the same inputs give byte-identical core plugins (verified, PR #394 re-stage, 235 s). A staged core costs
  0.3 to 1 GiB of new disk, a mission fold 4.5 GiB (verified, measure).
- Determinism risks (verified, buildorch §2): CPython 3.14 on Windows uses zlib-ng for `zlib.compress`; numpy picks
  SIMD code paths per CPU; Python randomises string hashes by default; .NET string sorting follows culture. In our
  code: `dotnet/ActorRaider/Program.cs:82` uses `float.Parse` without invariant culture (repo, low risk).
- Tools on the player's PC vary: texconv from their xEdit (GPU BC7 unless `-nogpu`), Archive2 from their Creation Kit.
- Mutagen moves fast: alpha.75 came out on 2026-10-19 while our dotnet projects pin alpha.67, and Mutagen and xEdit
  disagree on the LIGH flag bits from bit 4 up (Interiors thread, lead to verify). Correction to
  launcher-gamma-model-and-community-tools.md: "Fallout4 2.8.1-prerelease002" is an unlisted 2021 package, not a newer
  line than the one we pin. So a Mutagen bump is a B4 pin change that reruns every dotnet step and needs a same-ids
  check before it ships.
- Wabbajack, the most careful precedent, skips hash checks for compressed textures because they are not byte-identical
  (verified, installers-precedents §3).
- Windows: Idle CPU priority does not lower disk or memory priority; background mode can only be set by a process on
  itself; children inherit Idle (verified, buildorch §1.3). `SetThreadExecutionState` can't stop a user sleep.
- The driver's code hash is too coarse with no listed code (all of `src/fo4sf`) and too fine with listed files
  (misses changed helpers) (buildorch §1, repo).
- Precedent budgets: TTW 40 GB free, 17 GB output, about 40 minutes of audio encode; GAMMA 150 to 200 GB
  (installers-precedents §2, §6).

**Questions.**
- B1. Do two different PCs give byte-identical plugins from the same inputs? The release bar: IDENTICAL on two
  dissimilar CPUs. A second machine, or the same PC with `NPY_DISABLE_CPU_FEATURES` and a second checkout path, runs
  the example recipe. **PC** (the owner's word for a second machine).
- B2. Should FormIDs come from a shipped lock file instead of allocation order? Default yes, if the lock (ids plus FO4
  keys, no game data) is cleared legally; a build that allocates new ids says "not release-identical". **owner +
  outside.**
- B3. Does the DLC set shift base-game FormIDs? Build base-only and all-DLC and compare the base section of
  formids.json. Default: base ids in a range that never depends on DLC. **PC + offline.**
- B4. Which Python, numpy, .NET, Mutagen, texconv and Archive2 versions are pinned and shipped? Default: embedded
  Python with a wheel lock, a self-contained .NET publish, texconv pinned by hash, Archive2 required and its hash
  recorded. **offline.**
- B5. A determinism suite in CI: the same synthetic build under `PYTHONHASHSEED=0` and `=1`, a de-DE culture and
  `NPY_DISABLE_CPU_FEATURES`, bytes compared; guard rules for unsorted listings, culture-dependent parsing and
  sorting. **offline.**
- B6. Are texconv's CPU block codecs bit-identical across CPUs and thread counts? 20 test images on two CPUs, with
  and without `-singleproc`. Until known, textures are compared by decoded pixels, apart from plugin bytes. **PC.**
- B7. What goes in a step's cache key? Default: argv, inputs, the step's import closure, tool binary hashes and a
  per-step output version. Measure invalidations over the last 50 commits against today's rule. **offline.**
- B8. Keep more than one cached result per step? Default: the last two, evicted under a user cap (20 GB), never the
  one a save depends on. **offline** (needs measured unique bytes per step first: **PC**, `measure`).
- B9. Peak RAM, temp disk, final disk and time for a full build on the owner's PC and on a 16 GB, 6-core machine?
  Instrumented runs, recorded in docs/ai/optimization.md. Feeds the `need_gb` of every recipe step. **PC.**
- B10. How do we keep the PC usable during hours of building: CPU priority only, or background I/O too, and pause
  while a game runs? A 10-minute test with a game open. **PC.**
- B11. What does resume promise after a power cut mid-write? Default: every output is temp file, fsync, rename; a step
  counts only after its outputs are hashed into state. A fault-injection test on synthetic fixtures. **offline.**
- B12. Do we ever ship binary deltas? Default no for anything derived from game files; the downgrader's trick
  (patches encrypted with the original file's SHA-256) is noted for later. **owner + outside.**

## 4. Install, launch, restore

**Known.** The snapshot and restore route works on synthetic installs through our three installers (PR #394); the
install thread's swap scripts are its PC-side twin. Wabbajack resumes and updates by re-running and skipping files
already correct by hash, and asks before deleting files not in its list (verified). TTW updates by delete and
reinstall. Users report the Creations menu re-sorting or disabling plugins managed outside it (sfstack §4, cause not
confirmed).

**Questions.**
- I1. Does `restore --apply` give back a byte-identical Plugins.txt and Data on the real install? The first real
  round trip, with the owner's word since it touches the load order. **PC (owner's word).**
- I2. Does the launcher coexist with MO2 and Vortex users: detect them and refuse, export a package for them, or write
  directly? One install under Vortex 1.10.5 and one under MO2 2.5.2. **PC** (later).
- I3. Does the launcher read Starfield.ccc and ContentCatalog.txt (Creations) in detect and preflight? Read the
  owner's copies first. **PC + offline.**
- I4. How does the player start the Vault 111 game without a console: a launcher "Fallout mode" start, a menu
  entry, or a readme line? Ties to the new-game thread. **owner.**
- I5. What does the launcher store about saves? Default: a backup before every core change, the core fingerprint per
  save (from the save header's plugin lists), refusal to swap the core under a save when same-ids says IDS_DIFFER.
  **offline** (save header reader) **+ owner** (D9).
- I6. What happens in game when a core FormID changes type or disappears under a save, and does Starfield remap plugin
  indices by name when the order changes? In-game tests (a v6c save loaded under v6e). **PC (owner's word).**
- I7. Do Papyrus saves keep old script property values after a plugin changes, as Skyrim's do? Decides whether a door
  VMAD change needs "new game recommended". **PC (owner's word).**

## 5. The launcher app

**Known.** GPL-3 for Wabbajack, MO2, Vortex, LOOT and Synthesis; xEdit is MPL-2.0 (verified, appeng §1). PyInstaller
must be onedir for Velopack and to avoid leftover temp folders (verified). EV certificates no longer skip SmartScreen;
reputation takes "several weeks and hundreds of clean installs" (Microsoft, verified). SFSE bought a signing
certificate ($657 for 3 years) to cut false positives (community §7). Long paths need both the registry switch and a
`longPathAware` manifest. Controlled Folder Access protects Documents and its OneDrive copy, and already blocked our
`make_bridge.py` once. Wabbajack and GAMMA refuse install folders under Users, Documents, OneDrive, Program Files and
drive roots (verified, appeng §6-7). Our code still guesses `~/OneDrive/Documents` then `~/Documents`
(distribution-community Q13).

**Questions.**
- A1. UI stack (D10): a one-day spike of three screens (detect, progress, restore) in PySide6, measured for size and
  cold start. **offline.**
- A2. How to ship Python: PyInstaller onedir with a self-built bootloader, embeddable CPython, or a uv bootstrap?
  Build all three in CI and scan each with Defender and VirusTotal. **offline.**
- A3. Signing (D11): ask SignPath whether one owner as sole approver with agents as authors meets its rules. **owner.**
- A4. Where does the release build run? Default: a GitHub Actions Windows job with no game files; game-dependent
  tests stay on the PC. **offline.**
- A5. Updates (D7): check at start only, never applied while a build or install runs; the status view says how many
  steps an update would redo (the driver reruns steps whose code changed). **offline.**
- A6. Work folder rules: refuse folders under Users, OneDrive, Program Files or a drive root; detect reports the
  longest path the build writes against MAX_PATH. **offline.**
- A7. Are our exes long-path aware (PyInstaller exe, python.exe, each dotnet tool)? Dump the manifests. **offline.**
- A8. Find Documents\My Games\Starfield with the Known Folder API only, and show the resolved path in detect. Check on
  the owner's PC and on a OneDrive-redirected account. **offline + PC.**
- A9. Does Controlled Folder Access block our writes? Default: avoid writing in Documents (we don't today); if we must,
  read every write back and tell the player how to allow the app. **PC** (test VM) **+ offline.**
- A10. Is a non-ASCII Windows user name safe end to end (Python, dotnet tools, Archive2)? Default: UTF-8 for our
  subprocess I/O, paths as arguments. A run on an accented and CJK account. **outside / PC.**
- A11. What goes in the support bundle? Default: a local zip of driver state, step logs, build manifest, detect output,
  install records and INIs, user name replaced by `%USERPROFILE%`, nothing sent automatically, no telemetry. **owner
  (D12) + offline.**
- A12. Which crash logger do we point players to (sf-crash-logger, GPL-3; Starfield Engine Fixes' logger, pinned per
  runtime; Trainwreck, not updated since Jan 2024), and do we ask for its log? Trigger a known crash with each.
  **PC (later).**
- A13. All strings through one translation function and a keyboard-only and screen-reader smoke test from the first
  screen. **offline.**

## 6. Mods on the core

**Known.** LOOT is GPL-3 and its Starfield masterlist is CC0; LOOT breaks ties with the player's current order, so it
does not give the same order on every PC (verified, buildorch §4). MO2's meta.ini has no dependency fields; Vortex rules
are before, after, requires, conflicts, recommends, provides; Thunderstore pins exact versions; CurseForge manifests
carry no hashes. Our draft resolver (PR #394, `mods.py`) puts the core first, then mods in dependency order with id
ties.

**Questions.**
- M1. Who decides the final load order: our resolver, LOOT, or the player's manager? Default: our resolver for the core
  and our mods; we publish LOOT groups (`FO4SF Core`, then `FO4SF Mods`) to the CC0 masterlist so LOOT users agree.
  Test LOOT against our resolver on two sample mods. **offline.**
- M2. Ranges or exact versions in a mod's core requirement? Default: ranges on a core content version set by same-ids
  verdicts (SAME_IDS keeps the minor, IDS_DIFFER bumps the major), plus an optional exact build for byte-level patches.
  Check the rule against v6c to v6e. **offline + owner.**
- M3. May mods be medium plugins? Default yes if they fit, the type stated in the manifest, and a type change under a
  save refused. **offline.**
- M4. Can a patch to the core carry Fallout 4 record data (names, text, values)? That redistributes Bethesda content,
  unlike same-game patches. Default: patches as recipes applied on the player's PC, original data only.
  **outside** (Nexus) **+ owner** (D13).
- M5. Where are add-ons fetched from, and what if a host is down? GAMMA's 438 ModDB entries carry no hashes, so ModDB
  is a single point of failure (verified). Default: every manifest source carries a URL and sha256, mirrors allowed.
  **offline.**
- M6. Does fetching add-ons from Nexus need a registered app and the free-user "slow download" flow? The API policy
  bans personal keys in public apps. **outside.**

## 7. Distribution, legal, community

**Known.** See D5 to D8, D12, D13. More: Bethesda's Community Standards ban "Crowdfunding or Monetization mod
projects" (verified, community §6). GOG now distributes free total conversions that need the base game (Fallout
London, Fallout: New California in July 2026, STALKER GAMMA in December 2025) (community §8). Skyblivion was told to
replace 100% of its assets; Morroblivion's installer converts the player's own Morrowind data into a generated esm,
the closest same-publisher precedent to ours (installers-precedents §8-9). We found no published Fallout 4 to
Starfield total conversion and no takedown of one (unresolved).

**Questions.**
- L1. What exactly do we ask Nexus staff? (a) is a no-assets converter that runs on the player's PC a "modding tool";
  (b) is any internet use allowed, or must the Nexus build be offline; (c) may add-ons that depend on generated masters
  be hosted, and with what in them; (d) which game page and category; (e) which AI tag applies. **owner, then
  outside.**
- L2. Does the "solely in connection with" wording make the output a breach by the player? Now read in full
  (eula.md, ToS of 2024-11-12, both CK EULAs, both Steam game EULAs, Community Standards): clause (ii) is paid
  Creations only; clause (i) is unresolved, leaning no, because the player warrants each Game Mod "is originally
  created by You"; the Fallout 4 EULA's Software Utilities clause ties tool output to Fallout 4; Bethesda's modding
  guidelines say "Do not upload mods using ... content from other games ... This includes using assets from other
  Bethesda games" (verified). What a lawyer would settle: the Editor's scope, automated callers, "in connection with",
  which Fallout 4 EULA governs a player, statutory interoperability rights (17 USC §117, EU Software Directive art. 5
  and 6, UK CDPA s.50A to C and 296A), our liability as publishers of a converter, law and forum, trademark.
  **outside** (a lawyer) **+ owner** (whether to ask ZeniMax, D6).
- L3. Is driving the player's own Archive2 and PapyrusCompiler "use of the Editor"? Supported hypothesis: yes, by the
  player (the CK is licensed as "a single product" whose parts can't be separated); ToS §9 bars tools "created for
  certain Content ... except as authorized in writing", and whether that reaches an offline converter is unresolved.
  The cleaner route: our own BA2 packer (the 0BSD `ba2` crate, T4) and the community Papyrus compiler Caprica, so the
  build calls no Bethesda tool at all. **offline** (parity tests) **+ owner.**
- L2b. Should conversion need an explicit player action each time, check that each game and DLC is owned (not just
  hashed), and write a notice into every output? (eula.md questions.) **owner.**
- L4. Is a FormID lock file (ids plus FO4 keys) distributable? Decides B2. **outside.**
- L5. Do we use "Fallout" in the launcher's or Nexus page's name? Default: a nominative "for Fallout 4" phrasing.
  **owner.**
- L6. Donations at all? Default none, given Bethesda's monetisation rule. **owner.**
- L7. A first-run screen saying the player owns both games, the output is for personal use and must not be
  re-uploaded, and a marker in generated plugins saying they were generated locally? **owner.**
- L8. GPL release checklist: tag, source archive, MIT and GPL-3 licence texts, a third-party notices file for Mutagen
  and its dependencies, checked in CI against the release assets. **offline.**
- L9. Is GOG a better partner than Nexus once the GitHub release is stable? Read GOG's total-conversion terms.
  **outside.**
- L10. Linux and Steam Deck: a target or not? Every precedent grew Linux late through community rewrites. Default:
  keep stages headless and scriptable, avoid new PowerShell-only steps. **owner.**
- L11. A support matrix on the release page and a patch-day promise ("use the previous build until we publish
  support")? **owner.**

---

## What this changes in the backbone (PR #394), as reversible groundwork

Small, offline, testable items the research points at; none needs the owner's word. Listed here so the next pass
picks them up:
1. Code hash per step from the import closure instead of all of `src/fo4sf` (B7).
2. `snapshot` records Documents\My Games\Starfield\Data read-only and warns on overlaps (T8). Detect half done
   (368da05: loose files reported with `--my-games`).
3. `detect` refuses on `sTestFile` entries (done, 368da05), reads Starfield.ccc and ContentCatalog.txt, and reports MO2 or Vortex
   presence (T6, I3, I2).
4. `detect` finds Steam, GOG and Game Pass installs from the registry and libraryfolders.vdf, and tells the store from
   the exe (section 1).
5. A known-good Starfield runtime table next to `known_sources.json` (T1).
6. A MAST-list test that refuses `BlueprintShips-Starfield.esm` as a master (T7).
7. Work-folder rules and a longest-path report in `detect` (A6).
8. The determinism CI variations (B5) on the synthetic recipe.

## Not covered yet (next research wave)
- GOG and Game Pass file layouts for both games (no samples).
- The current ZeniMax ToS and both CK EULAs read in full.
- What changed between BA2 v7 and v8.
- Real support-load numbers from GAMMA, TTW or Fallout London (none published).
- Velopack's delta and per-user install docs (rate-limited).
