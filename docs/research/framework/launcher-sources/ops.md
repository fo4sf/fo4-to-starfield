# Operations research: updates, support, crash logs, patch day

Scope: a free, open-source Windows launcher (Python core, PySide6 GUI, PyInstaller onedir) for a large
Bethesda-game total conversion that is built on the player's PC from their own game files.
Researched 2026-10-19 by the `ops` research agent (Claude).

Labels used (as in docs/ai/research-log.md):
- **verified**: I read the URL in this session and it says this.
- **supported hypothesis**: inferred from verified facts, or from a source I read that is indirect (press, user comments).
- **unresolved**: I looked and could not confirm it.

---

## 1. Updating the launcher: Velopack vs "check GitHub Releases and tell the user"

### 1.1 What Velopack is and how it fits a PyInstaller onedir build
- **verified**: Velopack is an install and auto-update framework with a `vpk` CLI and per-language SDKs, including Python
  (`pip install velopack`). https://docs.velopack.io/ , https://docs.velopack.io/getting-started/python
- **verified**: the Python quickstart tells you to build with `pyinstaller --onedir` ("Velopack packages and updates a
  directory of files"), put `velopack.App().run()` first in `__main__`, then use `UpdateManager(url)` with
  `check_for_updates()`, `download_updates(info)`, `apply_updates_and_restart(info)`; the steps can be split so the user
  controls each. Progress callbacks exist. https://docs.velopack.io/getting-started/python
- **verified**: `vpk` is a .NET global tool, so **the build machine needs the .NET SDK** (not the player).
  Match the `vpk` version to the Python package version. Same page.
- **verified**: PyPI `velopack` latest stable is **1.2.161 (2026-09-29)**; a prerelease 1.3.39.dev36136 (2026-10-17)
  exists. Wheels are CPython abi3 (>=3.8) for Windows x64, x86 and ARM64. https://pypi.org/project/velopack/
- **verified**: the Python API reference (v1.2.161) lists `App`, `UpdateManager`, `UpdateOptions`, `UpdateInfo`,
  `HttpOptions`, `VelopackAsset`, `VelopackLocatorConfig`, and a `Sources` namespace with `GithubSource`, `GitlabSource`,
  `GiteaSource`, `HttpSource`, `VelopackFlowSource`. Per-method docs were not shown on the index page.
  https://docs.velopack.io/reference/py , https://docs.velopack.io/reference/py/Sources
- **verified**: repo is MIT, ~2.3k stars. https://github.com/velopack/velopack
- **supported hypothesis (maturity)**: the Python binding is real, versioned in lockstep with the core, and ships
  wheels for all Windows arches, but its reference docs are thin (no per-method pages surfaced) and every in-depth guide
  (rollback, sources) is written in C#. Treat it as usable but expect to read the Rust/C# docs and source for edge cases.
  No maturity or beta warning appears on the Python pages I read.
- **unresolved**: Python `GithubSource` constructor parameters (C# has `repoUrl, accessToken, prerelease`); open
  Python-specific issues (GitHub API search was blocked from this session).

### 1.2 Per-user install location, layout and what it means for us
- **verified**: `Setup.exe` is **per-user**, installs to `%LocalAppData%\{packId}`, needs no elevation; override with
  `Setup.exe --installto {dir}`. An MSI can do per-machine (`Program Files`, needs elevation).
  https://docs.velopack.io/packaging/operating-systems/windows
- **verified**: layout is `current\` + `Update.exe` + a root stub exe; **the whole `current` folder is replaced on
  update**; locked files: updater tries to kill the locking processes, else prompts or launches the old version. Same page.
- **supported hypothesis**: so the launcher must keep **nothing it needs to keep** (settings, logs, build caches,
  checkpoints, the built conversion output) inside `current\`. Our build output (tens of GB, built on the PC) must live
  in a user-chosen data folder, never inside the install dir.

### 1.3 Delta updates
- **verified**: deltas are generated automatically when the previous release is in the output dir (or fetched with
  `vpk download ...`); they are per-file Zstandard binary patches; modes `BestSpeed` (default), `BestSize`, `None`.
  Multiple deltas chain (1.0.0 -> 1.0.1 -> 1.0.2 ...); a heuristic picks full vs deltas by size and count.
  **No single file may exceed 2 GB.** With GitHub Releases, each release must contain exactly one full package and one
  delta. https://docs.velopack.io/packaging/deltas
- **supported hypothesis**: a PySide6 onedir is ~100-250 MB, mostly Qt DLLs that rarely change, so deltas should make
  most launcher updates small. Measure before claiming (AGENTS.md: before/after numbers).

### 1.4 Signing hooks
- **verified**: `vpk pack` signs with `--signParams` (your signtool args), `--signTemplate` (any tool, `{{file}}` or
  `{{file...}}`), or `--azureTrustedSignFile` (Azure Artifact Signing; works from Linux/macOS since Velopack 1.3; MSI only
  on Windows). Already-signed third-party files are left alone. `--signParallel` defaults to 10 files per call.
  SmartScreen is reputation-driven: OV certs build reputation over time; EV and Azure Artifact Signing get instant
  reputation per the page. Unsigned apps "may be flagged as a virus".
  https://docs.velopack.io/packaging/signing , https://docs.velopack.io/packaging/operating-systems/windows
- **supported hypothesis**: note "since Velopack 1.3" vs PyPI stable 1.2.161; check which `vpk` version we pin.
- **unresolved**: whether SignPath.io (free signing for OSS) plugs in via `--signTemplate`; very likely, not checked.

### 1.5 GitHub Releases as the feed
- **verified**: `vpk download github --repoUrl` (fetch prior release for deltas) and `vpk upload github --repoUrl
  --publish --releaseName --tag [--token]`; Actions needs `contents: write`.
  https://docs.velopack.io/distributing/github-actions
- **verified**: client `GithubSource(repoUrl, accessToken=null, prerelease=false)`; without a token you are on the
  unauthenticated limit of "60 requests per hour per IP". https://docs.velopack.io/integrating/update-sources
- **verified**: any static host also works (`releases.{channel}.json` next to the `.nupkg`s), which `HttpSource` /
  `UpdateManager("https://...")` reads. https://docs.velopack.io/distributing/overview
- **verified (GitHub)**: unauthenticated REST primary limit is **60 requests/hour, keyed on originating IP**;
  authenticated 5,000/hour. https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api
- **supported hypothesis**: 60/hour/IP is fine for one launcher checking once per start, but players behind CGNAT,
  university or LAN-party IPs share the bucket; a 403/429 must be treated as "could not check", never as an error
  dialog. Shipping a token inside an open-source binary is not an option (it would leak).
- **unresolved**: whether release-asset downloads (`github.com/.../releases/download/...`) count against the REST
  limit; the GitHub page does not say. A static feed (`releases.json` on GitHub Pages or a release asset URL read via
  `HttpSource`) would avoid the REST API entirely for the check.

### 1.6 Rollback
- **verified**: `UpdateOptions.AllowVersionDowngrade` lets the check return the latest applicable lower version (e.g.
  with `ExplicitChannel` to move beta -> stable). An exact older version means building `UpdateInfo(target,
  isDowngrade)` yourself from the feed. Downgrades always download the **full** package (no deltas), delete newer local
  packages, and **auto-apply on startup will not apply a downgrade** ("Relying on auto-apply will silently do nothing").
  The target must still be in the feed. https://docs.velopack.io/integrating/specific-version
- **supported hypothesis**: so "pull a bad release" = publish a higher version number that contains the old code
  (roll forward), and keep a `stable` and `beta` channel; true downgrade UI is optional.

### 1.7 Comparison

| Concern | Velopack | "Query GitHub Releases API, show a banner, user downloads zip" |
|---|---|---|
| Install | per-user Setup.exe, no admin, Start-menu/desktop shortcuts (verified) | user unzips anywhere; Wabbajack/Nolvus-style path problems (see 2) |
| Update size | deltas (verified) | full zip every time |
| Applying | replaces `current\`, restarts, handles locked files (verified) | user must close, replace folder, keep settings themselves |
| Rollback | channels + downgrade API (verified) | user re-downloads an old zip (trivial, but manual) |
| Signing | hooks built in (verified) | sign in CI ourselves (signtool / SignPath) |
| Build deps | .NET SDK on the build machine (verified) | none |
| Rate limits | same 60/h/IP if `GithubSource` used unauthenticated (verified); avoidable with a static feed | same 60/h/IP |
| Failure modes we own | Velopack bugs, AV quarantining `Update.exe` (hypothesis) | half-replaced folders, users running two copies (hypothesis) |
| Portable/USB use | not the default (portable zip exists in vpk but not covered on pages read - unresolved) | natural |

---

## 2. How big mod projects run support

### 2.1 Published size numbers
- **verified**: STALKER G.A.M.M.A. Discord: **710,517 members, 168,223 online** (Discord discovery page, read
  2026-10-19). https://discord.com/servers/stalker-gamma-912320241713958912
- **verified**: Skywind Discord: **41,686 members, 9,220 online**. https://discord.com/servers/skywind-145539675577122816
- **verified**: Fallout: London passed **500,000 GOG redemptions in 24 hours**, "fastest redeemed game" on GOG (press
  release, 2024-08-09). https://gamespress.com/Fallout-London-becomes-the-fastest-redeemed-game-of-all-time-on-GOG-an
- **verified**: Skywind (2026-05-09): still no release date; ~300 volunteer voice actors; recruiting QA testers.
  https://wccftech.com/skywind-2026-milestone-quests-written-no-release-date/amp/ . So Skywind has no public install
  support history to learn from yet (supported hypothesis).
- **unresolved**: member counts for Wabbajack, TTW/ModdingLinked, Team FOLON, Sim Settlements 2 and Nolvus Discords
  (Discord's invite API was blocked from this session; search found no discovery pages). Help-channel message
  volumes and staff counts were not published anywhere I found, for any of the seven projects.

### 2.2 Bug-report templates, log uploaders, triage
- **Nolvus** (verified, https://nolvus.net/appendix/installer/faq): the dashboard writes `log.txt` in its main
  folder ("This file is safe to upload to discord for review"); it has a built-in **Report** button
  (Manage -> Report to PDF, or Instance -> Report to clipboard). Questions go to the Discord auto-installer channel,
  "search first".
- **Wabbajack** (verified, https://wiki.wabbajack.org/user_documentation/Troubleshooting%20FAQ.html): per-version
  `logs\` folder next to the exe; users are told to open "the most recent log (the one where installation failed)".
  README sends help to Discord, docs to the wiki; GPL-3.0. https://github.com/wabbajack-tools/wabbajack .
  Modlist repository validation runs every 4 hours in GitHub Actions.
  https://wiki.wabbajack.org/wabbajack_cdn_and_gallery_access/Repository%20Validation.html
  **unresolved**: Wabbajack's GitHub issue template (robots blocked).
- **Sim Settlements 2** (verified, https://wiki.simsettlements2.com/getting-started/current-issues): moved issue tracking
  to a public upvote board (simsettlements2.featureupvote.com) so players find, upvote and comment on existing issues;
  an issue is listed only after "multiple players report it" and it is confirmed not a mod conflict or user error;
  reports need a description, `plugins.txt`, repro steps, and for small load orders (<20 mods) a save file. Status
  labels: Fixed / Fixed in X / Known issue / Under investigation / Needs investigation / Needs testing / Unknown if still an
  issue / Not a bug / Unfixable.
- **TTW** (verified, https://thebestoftimes.moddinglinked.com/faq.html): support via ModdingLinked or TTW Discord after
  the FAQ; Linux support limited to one channel; NVMP unsupported; **piracy talk = ban**. The FAQ names no installer log.
- **GAMMA** (verified, https://github.com/Grokitach/Stalker_GAMMA): install via wiki or Discord guide or GOG; support
  only via Discord; AGPL-3.0. The community Linux `gamma-launcher` gets GitHub reports with distro, exact command, Wine
  version, mod count and a `modlist.txt` diff (verified, https://github.com/Mord3rca/gamma-launcher/issues/178).
  **unresolved**: GAMMA's own diagnostics/log tooling.
- **Fallout: London** (verified): support through two new Discord channels opened at launch
  (https://www.pcgamesn.com/fallout-london/crashing), the GOG forum and X
  (https://wccftech.com/fallout-london-team-folon-working-on-major-bug-fixes/), and per-person troubleshooting on social
  media and Discord (press release above).

### 2.3 Top install-failure causes they publish (all verified from the pages in 2.2 and below)
| Cause | Who lists it |
|---|---|
| Install path in a protected folder (Downloads, Desktop, Documents, OneDrive, Program Files, drive root) | Wabbajack |
| Wrong or modified base game version / hash mismatch / missing DLC or Creation Club content | Nolvus, Wabbajack, TTW, FOLON |
| Leftover mods, CC files, old INIs in Data or Documents\My Games | TTW, FOLON |
| Antivirus / Controlled Folder Access / firewall blocking | Nolvus, TTW |
| Low disk space (Wabbajack: hash mismatch "usually caused by low disk space"; add 40-60 GB headroom) | Wabbajack |
| Missing runtimes (.NET 8 Desktop, VC++ 2019, WebView2) | Wabbajack |
| Unstable hardware: overclocks, CPU overheating; fix = fewer threads (`-threads:1`), page file, disable E-cores | Wabbajack, TTW |
| Download host limits (Nexus non-Premium 3 MB/s, Mega 509, Google Drive 429) | Nolvus, Wabbajack |
| Corrupt cached downloads ("file is being used by another process", "could not extract") | Nolvus |
| Moving the install folder mid-install; editing internal state files by hand | Nolvus |
| Game not launched once first (registry/INIs missing) | FOLON, TTW |
| Archive "blocked" by Windows Mark-of-the-Web ("This app can't run on your PC") | TTW |
| Quoted paths pasted into a path box | TTW |
| Non-English game install, non-Latin system locale | TTW, Wabbajack |
| Running the wrong exe (`Fallout4.exe` instead of `f4se_loader.exe`) | FOLON |

### 2.4 Fallout: London launch week (verified unless marked)
- Delayed from 2024-04-23 because Bethesda's next-gen FO4 update shipped first; released **2024-07-25** on GOG,
  pinned to the pre-next-gen FO4. https://en.wikipedia.org/wiki/Fallout:_London
- Steam owners had to **downgrade** with the team's Downgrader (log in with Steam credentials, Steam Guard prompts
  "possibly 2 or 3 times") or a manual guide, then make `appmanifest_377160.acf` read-only to stop re-updates; GOG was the
  easy route. https://www.pcgamer.com/games/fallout/after-years-fallout-4s-much-anticipated-dlc-sized-mod-fallout-london-is-out-heres-how-to-install-it/ ,
  https://www.gog.com/forum/fallout_london/fallout_london_quick_start_guide_common_bug_fixes/post12
- A developer-marked GOG quick-start/common-fixes post went up **the next day (2024-07-26)**: use the Downgrader, launch FO4
  once, delete old INIs and AppData, start via `f4se_loader.exe`, remove CC files and all mods, recommend Buffout 4. Same GOG URL.
- Reported problems: crashes after the train sequence (both Steam and GOG), FO4 menu music, green UI, no female
  character, launch crashes; the Steam-credentials downgrader was called "a major barrier to entry".
  https://www.mmorpg.com/news/fallout-london-launch-bugs-are-being-worked-out-little-by-little-2000132346 (2024-07-30)
- Team statement on X (~2024-07-30): "We're working hard to fix the reported technical issues and expect to release an
  update soon." First **hotfix 2024-08-09** (15 days after launch). Wikipedia; press release.
- 2025-09-30 *Rabbit & Pork*: new save required and a **custom Overwolf-powered launcher/installer** to make installation
  "faster and more reliable". https://www.gamingonlinux.com/2025/09/fallout-london-mod-gets-a-huge-upgrade-with-rabbit-pork/page=1/
- **supported hypothesis**: most launch-week load was environment (wrong game version, leftover mods/INIs, wrong exe),
  not content bugs; a launcher that checks those before launch removes the bulk of it. FOLON itself ended up shipping its
  own launcher a year later.

---

## 3. Starfield crash loggers (as of 2026-10)

| | sf-crash-logger (CrashLogger) | Starfield Engine Fixes, Detailed Crash Logger | Trainwreck |
|---|---|---|---|
| URL | https://github.com/0xra0/sf-crash-logger | https://www.nexusmods.com/starfield/mods/10457 | https://www.nexusmods.com/starfield/mods/5068 |
| Licence | **GPL-3.0** (verified) | Nexus permissions: no re-upload, no modification without permission; no OSS licence stated (verified) | "(c) 2023 Ryan McKenzie. All rights reserved." (verified) |
| Records | stack trace (+ stack scan), registers annotated with module offset / RTTI type, RTTI object IDs, module list with SFSE plugins flagged, culprit summary, `Plugins.txt` load order, breadcrumb trace of first-chance exceptions, OS/CPU/GPU/RAM, Wine/Proton detection, **minidump** (verified) | names of game forms, quest aliases, base forms of hazards/projectiles involved (verified, changelog) | OS build, call stack, module list with SHA-512 hashes, SFSE plugin list, PDB type names/source lines when available (verified) |
| Output | `Documents\My Games\Starfield\SFSE\Crashlogs\` : `crash_<ts>.log`, `crash_<ts>.dmp`, `CrashLogger.log`, rotating `CrashLogger_trace.log` (4 MiB) (verified) | path set by `sDetailedCrashLoggerSaveLocation`; default not stated (verified) | `Documents\My Games\Starfield\SFSE\Crashlogs` (verified) |
| Runtime support | not stated; Address Library optional, IDs omitted if no `versionlib-<ver>.bin` matches (verified) | per-runtime builds; v21.2 (2026-10-04) targets **1.16.244**; old builds kept for 1.14.74, 1.15.216, 1.15.222, 1.16.236, 1.16.242 (verified) | claims all versions "in perpetuity"; last update 2024-01-08 (v1.4.0); a 2026-04-20 user log shows it ran on 1.16.236; 2026-08 and 2026-09 users report it not logging, no author reply (verified) |
| Maturity | 1 star, 19 commits, no releases listed on the page (verified) | very active, many releases per month (verified) | unmaintained since 2024 (supported hypothesis) |
| Default on? | yes once installed | **optional, off by default** ("These features are off by default") (verified, inferred from general statement) | yes |

- **verified**: mod authors already ask for Trainwreck logs specifically (BetterConsole, 2024-06-17).
  https://www.nexusmods.com/starfield/articles/559
- **supported hypothesis, recommended ask**: (1) our own launcher log + a machine-readable environment report;
  (2) the newest `crash_*.log` from `Documents\My Games\Starfield\SFSE\Crashlogs\` (Trainwreck and sf-crash-logger both
  write there, so we can collect "newest file in that folder" without caring which logger the player has);
  (3) `.dmp` only on request (large, contains memory, privacy). GPL-3.0 sf-crash-logger is the only one we could legally
  bundle or fork from an OSS launcher, but it is a one-star project; Trainwreck and SFEF can only be recommended and linked,
  not redistributed.
- **unresolved**: whether SFEF's Detailed Crash Logger writes a full crash log or only enriches another logger's; its
  default output path.

---

## 4. Patch day: telling players a game update broke things, and how fast the stack followed

### 4.1 Communication practice seen
- **verified**: SFSE uses one **pinned, dated, continuously edited status post** on its Nexus page: e.g. 2025-05-23
  "The game update has broken most if not all plugins, as well as the Address Library", 2024-09-30 "all gameplay plugins
  will need to be recompiled", and "beta updates are not supported".
  https://www.nexusmods.com/starfield/mods/106?tab=posts
- **verified**: SFEF keeps the last build for every past runtime as a main file ("The latest version that supports Game
  version 1.16.242 (2026 May update)"). https://www.nexusmods.com/starfield/mods/10457?tab=files
- **verified**: Nexus Mods ran an advance news article for the FO4 Anniversary update (posted 2025-11-06 for
  2025-11-10), told users to back up, added a "Works with Anniversary Upgrade" tag, and noted F4SE got no early access.
  https://www.nexusmods.com/hacklastrecode/news/15400
- **verified**: Team FOLON used X + Discord + GOG forum; Sim Settlements 2 uses a public tracker with status labels;
  Wabbajack uses CI validation (sections 2.2, 2.4).
- **verified**: Starfield has a public Steam `beta` branch where updates appear before release (2023 article).
  https://www.bgr.com/entertainment/you-can-test-starfield-updates-before-they-roll-out-to-everyone-heres-how
- **unresolved**: any of the seven projects using an in-launcher banner or a hosted status page; I found none
  documented. Nolvus/GAMMA launchers have news panes (supported hypothesis, not verified).

### 4.2 Measured follow speed, 2025-2026 Starfield updates (all verified from the SFSE, SFEF and Address Library pages)

| Game update (release date) | SFSE | Address Library (offsets) | Starfield Engine Fixes |
|---|---|---|---|
| 1.15.216 (2025-05-22) | 0.2.17 on 2025-05-23 (+1 d) | v18 on 2025-05-24 (+2 d) | v11.x line (exact first date not read) |
| 1.15.222 (beta 2025-07-22, release ~2025-08-05) | updated 2025-08-05 (same day as release) | v19 on 2025-08-05 (0 d) | (first date not read) |
| 1.16.236 (2026-04-07) | 0.2.19 on 2026-04-07 (0 d) | v20 on 2026-04-08 (+1 d) | v17.0 on 2026-04-08 (+1 d) |
| 1.16.242 (2026-05-14) | 0.2.20 on 2026-05-14 (0 d) | v21 on 2026-05-15 (+1 d) | v18.0 on 2026-05-15 (+1 d) |
| 1.16.244 (2026-06-11) | 0.2.21 on 2026-06-11 (0 d) | v22 on 2026-06-13 (+2 d) | v20.0 on 2026-06-13 (+2 d) |

Sources: https://www.nexusmods.com/starfield/mods/106?tab=posts , https://www.nexusmods.com/starfield/mods/3256?tab=files ,
https://www.nexusmods.com/starfield/mods/10457?tab=files

- **supported hypothesis**: the core stack (SFSE + Address Library + SFEF) is back within 0-2 days of a Starfield patch;
  every plugin on top of that is on its own author's schedule. Our conversion's exposure is the plugins we depend on plus
  any game-version-specific data we generate. No Starfield update after 1.16.244 is visible as of 2026-10-19 (SFSE page last
  updated 2026-06-11; SFEF 2026-10-04 still targets 1.16.244).
- **verified**: a player's mod manager missing that a game update replaced a DLL produced a false "logger doesn't
  work" report (Trainwreck comments, 2026-06-11). Version detection belongs in the launcher.

---

## Questions this raises for our launcher

1. **Velopack or "notify and download"?**
   Why: Velopack gives per-user install, deltas, signing and rollback but adds a .NET build dependency and a binding whose
   docs are thin. What answers it: a spike that packs our PySide6 onedir with `vpk`, updates 1.0.0 -> 1.0.1 -> 1.0.2 on a
   clean Windows VM, measures delta size and time, and tests AV behaviour. **Default: Velopack, with a static feed;
   keep a portable zip as a fallback download.**

2. **Where does the update check read from: the GitHub REST API, or a static `releases.json`?**
   Why: 60 req/hour per IP, shared behind CGNAT; no token can ship in an OSS binary. What answers it: confirm whether
   Velopack's `HttpSource` can read a feed from a GitHub release asset URL or GitHub Pages, and whether asset downloads
   count against the REST limit. **Default: static feed (GitHub Pages or release asset), check at most once per launch and
   once per 6 h, and treat 403/429/offline as "couldn't check" silently.**

3. **What must never live in the install folder?**
   Why: Velopack replaces `current\` on every update. What answers it: list every path the launcher writes.
   **Default: settings, logs and caches in `%LocalAppData%\<app>\` outside `current\`; the built conversion and its
   checkpoints in a user-chosen data folder, validated against the Wabbajack protected-folder list.**

4. **Which install and data paths do we refuse or warn about?**
   Why: protected folders, OneDrive, drive roots, quoted paths and moving mid-build are top failure causes (2.3).
   What answers it: a path validator test matrix. **Default: block Program Files, OneDrive, Downloads/Desktop/Documents,
   drive roots and network paths for the data folder; strip quotes; require free space = estimate + 50 GB headroom;
   never allow moving the data folder during a build.**

5. **What does the pre-flight check verify before a build and before every launch?**
   Why: wrong game version, leftover mods/INIs, missing runtimes, MOTW-blocked files and the wrong exe drove FOLON's and
   others' launch-week load. What answers it: one check per row of 2.3 with a synthetic fixture test. **Default: exe
   version + hash of Fallout4.exe/Starfield.exe against a known list, SFSE/Address Library version match, Data-folder
   contamination scan, launched-once check, MOTW check, free space, AV/Controlled Folder Access hint; each failure shows a
   fix, not a stack trace.**

6. **What is the one-click support bundle?**
   Why: Nolvus's Report button and `log.txt` are the clearest precedent; Wabbajack makes users dig for the right log.
   What answers it: decide the fields and redaction rules. **Default: a "Copy report" button producing a zip/markdown with
   launcher version, game versions, SFSE/AL versions, pre-flight results, last build log tail, plugin list, and the newest
   `Documents\My Games\Starfield\SFSE\Crashlogs\crash_*.log`; usernames in paths redacted; no `.dmp` unless the player
   ticks it; nothing uploaded automatically.**

7. **Which crash logger do we recommend, bundle, or neither?**
   Why: only sf-crash-logger is GPL (bundle/forkable) but immature; Trainwreck is unmaintained and closed; SFEF's logger is
   off by default and non-redistributable. What answers it: test each on 1.16.244 with a forced crash and compare outputs.
   **Default: don't bundle; detect which is installed, recommend one in the docs, and collect "newest file in the
   Crashlogs folder" regardless.**

8. **Where does support happen, and what is the intake form?**
   Why: every project funnels to Discord, which is unsearchable and costs volunteer hours; SS2 moved to an upvote board;
   AGENTS.md routes community reports through `community_report.yml` with owner triage. What answers it: the owner's
   capacity and community-agent findings. **Default: GitHub issue form (attach the support bundle) as the canonical
   channel, plus a FAQ generated from pre-flight check IDs; Discord optional and pointed at the FAQ; piracy = no support,
   stated up front (TTW precedent).**

9. **How do we tell players a Starfield or FO4 update broke us?**
   Why: SFSE's dated pinned post works; nobody we studied has an in-launcher banner documented, yet the launcher can
   detect the version itself. What answers it: decide the feed. **Default: a small signed `status.json` (same static host as
   the update feed) with per-game-version states (supported / testing / broken) and a message; the launcher compares it to
   the detected exe version and shows a banner and blocks the build on "broken"; mirror it in a pinned GitHub issue.**

10. **Do we support playing on an old runtime, and do we help players stay on one?**
    Why: FOLON's Steam downgrade (credentials, read-only appmanifest) was its biggest barrier; SFEF keeps per-runtime
    builds; the core stack catches up in 0-2 days. What answers it: EULA and store findings plus how version-specific our
    generated data is. **Default: never downgrade the game for the player or handle Steam credentials; support the current
    release runtime only, show "wait for update" when the game is newer than supported, and document Steam's "update only on
    launch" setting.**

11. **How fast do we commit to follow a game patch?**
    Why: SFSE/AL/SFEF are back in 0-2 days; our dependency chain adds the slowest plugin we need. What answers it: a
    dependency inventory with each author's historical lag. **Default: publish "supported within 7 days of SFSE support,
    best effort"; CI job that re-runs offline checks when a new runtime ID appears.**

12. **Do we test against the Starfield Steam beta branch?**
    Why: updates appear there first, giving warning time; SFSE does not support betas. **Default: a non-blocking QA
    run on the beta branch when one appears, results feeding `status.json` as "testing".**

13. **How do we pull a bad launcher release?**
    Why: Velopack downgrades are full downloads and not auto-applied. **Default: roll forward (re-release old code as a
    higher version); keep `stable` and `beta` channels; keep the last 3 releases in the feed.**

14. **Signing: which route and when?**
    Why: unsigned PyInstaller apps trip SmartScreen and AV; FOLON/TTW list AV as a top cause. What answers it: cost and
    eligibility of SignPath (free OSS) vs Azure Artifact Signing, and whether it fits `--signTemplate`. **Default: sign from
    the first public release; submit each release to Microsoft's false-positive portal; never ask users to disable AV,
    only to add an exclusion for the data folder.**

15. **What support load should we plan for?**
    Why: FOLON saw 500k redemptions in 24 h and needed new Discord channels on day one, a fix post on day two and a hotfix
    on day 15; GAMMA's Discord is 710k members. No project publishes staff or ticket numbers. What answers it: a soft
    launch with telemetry-free counts (GitHub release downloads, issue volume per pre-flight check ID). **Default: staged
    release (beta channel first), a launch-week FAQ prepared from the 2.3 table, and a rule that every repeated issue becomes
    a pre-flight check or FAQ entry within the week.**
