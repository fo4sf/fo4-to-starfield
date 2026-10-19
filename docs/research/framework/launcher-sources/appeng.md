# Launcher application engineering: how modding tools did it, and what it means for us

Written 2026-10-19 by Claude (cloud research agent, "appeng"). Web research only: nothing installed, nothing run on
Windows. Scope: a Windows desktop launcher for fo4-to-starfield that runs hours-long CPU/disk-heavy conversion jobs
(Python 3 + numpy, plus .NET/Mutagen GPL-3 command-line tools), installs the result into Starfield and later restores
the player's setup, and never ships game assets.

**Labels** (as docs/ai/research-log.md): **verified** = I read the cited page in this session and it says so;
**supported hypothesis** = consistent with what I read or with widely known practice, but I did not read a page that
states it; **unresolved** = not established. Where a page could not be read I say so.

**Access limits in this session (affects confidence):** GitHub API access to the tool repositories was refused
(session not granted those repos), so language percentages and source files were not read; `github.com/.../tree/...`
pages are blocked by robots for the fetcher; partway through, the fetch proxy began answering HTTP 429 (rate limit) for
every page, so these pages were **not read**: docs.velopack.io (main page), the Clowd.Squirrel NuGet page, the
WinSparkle repository, the GitHub REST rate-limit docs, PEP 529, PEP 686, the SetPriorityClass reference. Claims that
depend on them are marked supported hypothesis or unresolved below.

Context already in the repo (verified, read in this session): docs/ai/launcher-backbone.md already has a recipe-driven
resumable build driver with `--min-free-gb` (the D: 40 GB rule), `--idle` (Windows Idle priority), a hard-link-aware
`measure`, a read-only `detect`, snapshot/restore through the existing installers, and notes that INIs are only
watched, never written. This document is about the application around that backbone.

---

## 1. How the reference tools are built (stack, licence, distribution)

| Tool | Stack | Licence | How it reaches users | Label / source |
|---|---|---|---|---|
| Wabbajack | .NET; repo has `Wabbajack.App.Wpf` and a separate `Wabbajack.Launcher` project and `release.ps1` | GPL-3 ("All original code in Wabbajack is given freely via the GPL3 license") | Launcher exe; the app lives in a per-version subfolder ("Inside your Wabbajack folder should be another folder with the version number of the current version", where `logs` lives) | **verified** WPF project name and GPL-3: https://github.com/wabbajack-tools/wabbajack ; per-version folder: https://wiki.wabbajack.org/user_documentation/Troubleshooting%20FAQ.html . The README page also mentions Patreon funds keeping a "Code Signing Certificate" alive (**verified**, same page). Whether Wabbajack moved to Avalonia: **unresolved** (README shows only a WPF app project; I found no page confirming an Avalonia release; a Patreon "Wabbajack 3.0 Development Update" exists but was not read). That the launcher self-updates by fetching the newest release into a new version folder: **supported hypothesis** (folder layout plus a separate launcher project; source not read). |
| Mod Organizer 2 | C++ / Qt (Qt version not read) | GPL-3 | GitHub releases; translations via Discord #translation and a `.tx` folder (Transifex config) | **verified** GPL-3 and translation note: https://github.com/ModOrganizer2/modorganizer . C++/Qt: **supported hypothesis** (well known; language bar not captured). |
| Vortex | Electron / TypeScript (not read on the page) | GPL-3 | Nexus Mods site and GitHub releases (beta tags like v2.4.0-beta.1 exist) | **verified** GPL-3: https://github.com/Nexus-Mods/Vortex ; Electron: **supported hypothesis**. |
| LOOT | C++ with Qt 6 (build docs reference `qt6-base-dev`, `/opt/qt/6.11.1/mingw_64`, `windeployqt.exe`); Linux build installs `rustup`, so a Rust toolchain is needed | GPL-3 | GitHub releases; translations on Weblate | **verified**: https://github.com/loot/loot . That libloot itself is now Rust: **supported hypothesis** (rustup in build steps; not stated). |
| xEdit | Delphi ("requires a properly configured Delphi environment", Delphi 12 Community Edition) | MPL-2.0 | Discord `#xedit-builds` (newest), Nexus Mods, GitHub Releases mirror | **verified**: https://github.com/TES5Edit/TES5Edit |
| Synthesis | .NET; projects `Mutagen.Bethesda.Synthesis.WPF`, `Synthesis.Bethesda.GUI` | GPL-3 | GitHub release workflows; NuGet package for patchers | **verified** names and licence: https://github.com/Mutagen-Modding/Synthesis ; WPF: **supported hypothesis** from project name. |
| GAMMA (Grok's Modpack Installer) | Launcher technology not stated | not read | Launcher downloads every add-on "directly from moddb or github"; ships into an MO2 instance; manual launcher update by extracting the new version into `.Grok's Modpack Installer` | **verified**: https://github.com/Grokitach/Stalker_GAMMA and https://github.com/Grokitach/Stalker_GAMMA/wiki/Installing-GAMMA . Launcher is C#/.NET: **unresolved** here. |
| TTW installer | not researched successfully (searches returned nothing usable) | | | **unresolved** |

Take-away (**supported hypothesis**): every major Bethesda modding tool is GPL-3 (or MPL for xEdit) and native or
.NET; none of the ones checked is Python. Our Python core is unusual in this scene but not a blocker.

## 2. UI framework and bundling options for us

### 2.1 Frameworks

| Option | Fit with Python+numpy core | Licence | Size and runtime | Notes |
|---|---|---|---|---|
| **PySide6 (Qt for Python)** | Same process, direct import of `fo4sf` | LGPL-3 (or commercial). Using it as a library does not oblige you to publish your app's source; modifications to PySide itself must be shared | Qt runtime adds tens of MB (number not measured here) | **verified** licence summary: https://www.pythonguis.com/faq/not-an-open-source-application-which-one-to-use-pyqt5-or-pyside2/ . Our repo is open source anyway, so LGPL obligations (ship Qt as replaceable DLLs, which PyInstaller onedir does naturally) are easy: **supported hypothesis**. The official Qt "Commercial Use" page did not render its body (**unresolved** from primary source). MO2 and LOOT both use Qt, so Qt has a modding-scene precedent (**verified** for LOOT). |
| **Tkinter** | Same process | PSF | Ships with CPython; smallest | Not in the embeddable Python package ("Tcl/tk ... pip and the Python documentation are not included") **verified**: https://chromium.googlesource.com/external/github.com/python/cpython/+/3.7/Doc/using/windows.rst . Dated look, weak accessibility (**supported hypothesis**). |
| **Tauri** (Rust + system WebView2) with Python as a sidecar process | Separate process; we already run steps as subprocesses through the driver | MIT/Apache | Much smaller than Electron; Windows bundles only `.exe` / `.msi` | **verified** ".exe and .msi bundles on Windows": https://dolthub.com/blog/2025-11-13-electron-vs-tauri . Adds Rust + JS toolchains to a Python/C# repo. |
| **Electron** (Vortex's choice) | Separate process | MIT | "Hello World ... up to 150 megabytes" | **verified** size claim: https://dolthub.com/blog/2025-11-13-electron-vs-tauri . Adds Node + JS. |
| **.NET WPF / Avalonia / WinUI** (Wabbajack, Synthesis) | Python stays a subprocess (as the driver already does) | WPF/WinUI MIT; Avalonia MIT | .NET runtime (self-contained adds tens of MB, not measured) | We already have a .NET SDK dependency for Mutagen. But a C# GUI linking Mutagen would be GPL-3 too; a GUI that only spawns processes need not link it (**supported hypothesis**, licensing advice not legal advice). |

Recommendation (**supported hypothesis**): the job runner, state and restore are Python and already exist
(launcher-backbone.md). The cheapest correct path is a **Python GUI in the same codebase (PySide6)** that drives the
existing driver as a subprocess, so a GUI crash never kills a 6-hour build and the CLI stays the source of truth. A
web-UI shell (Tauri) is the second choice if the owner wants a web look; Electron is not worth 150 MB plus Node.

### 2.2 Shipping Python

| Method | What it is | AV / size notes | Label |
|---|---|---|---|
| **PyInstaller onedir** | Folder with exe + DLLs + pyc | Hello-world ~15 MB and grows with deps; stock bootloaders are flagged because malware uses them; recommended fix: rebuild bootloader and sign | **verified**: https://pydevtools.com/handbook/explanation/how-do-i-ship-a-python-application-to-end-users.md ; PyInstaller itself lists "avoid anti-virus false positives that result from the wide-spread use of pre-compiled bootloaders" as a reason to build the bootloader, without promising it works: https://pyinstaller.org/en/latest/bootloader-building.html |
| PyInstaller onefile | Self-extracts into `%TEMP%\_MEIxxxxxx` each start | Leaves `_MEI` folders behind on crash or kill ("users will lose disk space"); do not run onefile as admin (temp-folder DLL tampering) | **verified**: https://pyinstaller.org/en/v5.2/operating-mode.html . Velopack also requires onedir ("Velopack packages and updates a directory of files"): **verified** https://docs.velopack.io/getting-started/python |
| Nuitka standalone / onefile | Python compiled to C | Build 5 to 15 min where PyInstaller takes 30 s; "Onefile binaries trigger the same false positives that affect PyInstaller"; AGPL-3 with runtime exception for output; NumPy has a plugin config | **verified**: https://pydevtools.com/handbook/reference/nuitka/ |
| Embeddable Python zip (python.org) | Official minimal CPython "intended for acting as part of another application" | No pip, no Tcl/Tk; we would ship numpy wheels unpacked; launcher would be a small native exe or a `.bat` | **verified**: CPython docs above. Lower AV risk than PyInstaller because python.exe is the signed python.org binary (**supported hypothesis**; python.org signing not checked). |
| python-build-standalone (+ uv) | Astral-maintained portable CPython builds; "most common method of using these distributions is with uv" | Same idea as embeddable but full stdlib (incl. tkinter) | **verified**: https://docs.astral.sh/python-build-standalone/ . A "launcher downloads uv, uv fetches pinned Python + wheels" model (like PyApp) means a tiny signed bootstrap and reproducible envs, but needs network at first run (**supported hypothesis**). |

Size of the result (**supported hypothesis**, not measured): Python runtime ~10 to 30 MB + numpy (~20 to 40 MB of DLLs
incl. OpenBLAS) + Pillow + PySide6 (QtCore/QtGui/QtWidgets only, ~60 to 100 MB) + self-contained .NET Mutagen tools
(tens of MB each unless framework-dependent). A plausible 150 to 300 MB installer; measure it (docs/ai/optimization.md
rule) before quoting it to players.

## 3. Code signing, SmartScreen and antivirus

**Verified facts** (https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/code-signing-options and
https://learn.microsoft.com/et-ee/windows/apps/package-and-deploy/smartscreen-reputation):
- Azure **Artifact Signing** (formerly Trusted Signing): "Approximately $9.99/month"; eligibility "Organizations: USA,
  Canada, EU, UK. Individuals: USA and Canada only"; identity validation "a few business days"; no USB token; CI
  friendly; does **not** give instant SmartScreen trust.
- **OV certificate**: "$150–300/year", worldwide, private key on HSM/hardware token since June 2023.
- **EV**: "$400+/year"; the instant SmartScreen bypass "was removed in 2024"; "Paying a premium for EV solely to avoid
  SmartScreen warnings is no longer justified."
- **Unsigned**: "SmartScreen reputation must build for each new version of your files, starting with zero reputation";
  user sees "Windows protected your PC" and must click "Run anyway".
- Reputation: publisher (certificate) and file hash; "it can take several weeks and hundreds of clean installs";
  "Reputation cannot transfer from previous versions unless both were signed using the same publisher identity";
  "There is no need (or mechanism) to manually submit a file for SmartScreen reputation review for consumer endpoints."
- Microsoft Store (MSIX) avoids the warning entirely; MSI/EXE submitted to the Store must still be signed.

**SignPath Foundation (free for OSS)**, verified at https://signpath.org/terms : OSI licence with no commercial
dual-licensing; no proprietary components (system libraries allowed); actively maintained and already released;
signed binaries must come from "a valid, automated build resulting from the source code"; "Every release needs manual
approval for signing"; roles Authors / Reviewers / Approvers; MFA for everyone on SignPath and the repo; a "Code signing
policy" section on the project home page naming SignPath and the team, with a privacy statement; product name and
version metadata enforced; no hacking tools, respect privacy, announce system changes, provide uninstallation.

Implications for us (**supported hypothesis**):
- We qualify on licence only if the shipped bundle is all OSS: Python, numpy, Pillow, PySide6 (LGPL) and Mutagen
  (GPL-3) are OSS. "Shared AI-agent GitHub account" may collide with "team roles and members" and MFA rules; the owner
  must be the Approver.
- The "build from source in CI" rule means a GitHub Actions Windows release build, not a build on the owner's PC.
- Game assets are never in the signed bundle (also a project rule), which matters because SignPath signs what CI
  builds and we must not build from game files in CI.

**Antivirus / Defender false positives**:
- PyInstaller output is commonly flagged; remedies: submit to each vendor, check VirusTotal, sign; resubmission may be
  needed per release because small changes re-trigger detection (**verified** as forum advice, not vendor policy:
  https://discuss.python.org/t/pyinstaller-false-positive/43171).
- Microsoft's submission portal has a "Software developer" option, 50 MB max file, Medium priority "for analyst review
  within a few days" (**verified**: https://www.microsoft.com/wdsi/filesubmission). An installer above 50 MB must be
  submitted as its individual exes/DLLs (**supported hypothesis**).
- How modding tools cope: GAMMA tells players to put the GAMMA and Anomaly folders "in antivirus exclusions" before
  downloading, to disable Norton/Avast/AVG/Malwarebytes during install, and to exclude MO2 and Anomaly exes from
  Bitdefender Advanced Threat Defense (**verified**: GAMMA wiki above). Wabbajack keeps a code signing certificate
  (**verified**, README). Telling players to add AV exclusions is the scene norm but it is a security cost we should
  avoid asking for if signing works (**supported hypothesis**).

## 4. Self-update

- **Velopack** (successor in spirit to Squirrel): Python support via `pip install velopack`, call
  `velopack.App().run()` first thing because it "might quit/restart the process"; `UpdateManager` points at "a web
  server, S3 bucket, GitHub releases, etc."; packaging with `vpk`, a .NET global tool (needs the .NET SDK, which we
  already have); PyInstaller must be `--onedir` (**verified**: https://docs.velopack.io/getting-started/python).
  Delta updates, per-user install under `%LocalAppData%` without UAC, and code-signing integration in `vpk`:
  **supported hypothesis** (main docs page could not be read, rate-limited).
- **Squirrel.Windows / Clowd.Squirrel**: Velopack is the continuation of Clowd.Squirrel by the same author:
  **supported hypothesis** (NuGet page not read). Do not start a new project on Squirrel.Windows (**supported hypothesis**).
- **WinSparkle**: appcast (RSS) updater for Windows that downloads and runs an installer, with signature checking:
  **supported hypothesis** (repo not read).
- **Plain GitHub Releases API**: unauthenticated REST calls are limited per IP (60/hour is the commonly cited
  number): **supported hypothesis** (docs page not read). A once-per-launch check is far under that.
- How modding tools update: GAMMA's launcher downloads mod content from ModDB/GitHub on "Install / Update GAMMA",
  but the launcher itself is updated by hand ("extracting v8.6 into the `.Grok's Modpack Installer` folder")
  (**verified**, GAMMA wiki). Wabbajack keeps per-version app folders under a launcher (**verified** layout,
  mechanism **supported hypothesis**). Vortex publishes stable and beta releases (beta tags verified only by title on
  newreleases.io, page not read: **unresolved** whether it uses electron-updater).

Key design point (**supported hypothesis**): updating the launcher must never happen while a build or an install is
in progress, and an update must not invalidate a half-done build's checkpoints silently. The driver's fingerprint
includes code content (launcher-backbone.md), so an update mid-build will rerun steps: that is correct but expensive,
and the UI must say so.

## 5. Windows pitfalls

| Pitfall | What is known | Label |
|---|---|---|
| **MAX_PATH** | 260 chars by default. Long paths need **both** `LongPathsEnabled=1` (HKLM\SYSTEM\CurrentControlSet\Control\FileSystem, admin) **and** a `longPathAware` manifest in the exe; cached per process, reboot may be needed; `\\?\` prefix gives ~32,767 chars but disables `.`/`..` handling and does not work with relative paths | **verified**: https://learn.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation |
| Python and long paths | Python 3.6+ supports long paths once the policy is on | **verified**: CPython Windows docs above. Whether a PyInstaller or embeddable-launched exe carries the `longPathAware` manifest: **unresolved** (must test; python.exe has it, a PyInstaller bootloader exe may not). The .NET tools: **unresolved**. Safest default: keep the work root short (e.g. `D:\FO4SF\`) and check path lengths in `detect`. |
| **OneDrive-redirected Documents** | Starfield's INIs live in `Documents\My Games\Starfield\`, or `OneDrive\Documents\My Games\Starfield\` when OneDrive is used | **verified**: https://nexusmods.com/starfield/articles/116 . Must resolve via the Known Folder API (SHGetKnownFolderPath FOLDERID_Documents), never `%USERPROFILE%\Documents`: **supported hypothesis** (standard practice; MS page not read). |
| Starfield's second Data folder | "Starfield can read files from a Data folder in one of two locations" (game root and Documents\My Games\Starfield\Data); mixing them causes surprises | **verified**: https://www.nexusmods.com/starfield/articles/578 . Our snapshot/restore must look at both (backbone currently records the game Data only: **supported hypothesis** from reading launcher-backbone.md). |
| **Controlled Folder Access** | Off by default; when on, protects `C:\Users\<user>\Documents` (and the redirected OneDrive location), Pictures, Videos, Music, Favorites, Public folders; untrusted apps cannot modify or delete there; most apps auto-trusted by prevalence/reputation; script engines like PowerShell are not trusted; allow-list is by exact path | **verified**: https://learn.microsoft.com/defender-endpoint/controlled-folders . So a new, low-prevalence, unsigned launcher writing `StarfieldCustom.ini` or Plugins.txt-adjacent files in Documents can be blocked silently except for a toast. (Plugins.txt is under `%LocalAppData%\Starfield`, not CFA-protected: **supported hypothesis**.) |
| Install location | Wabbajack: not in "Downloads, Desktop, Documents, Videos, Pictures, OneDrive, Program Files", not at a drive root; "create a new folder near the root of your drive". GAMMA: not in Users, Desktop, OneDrive, Program Files; same drive; not USB; 150 GB free | **verified**: Wabbajack FAQ and GAMMA wiki above. Velopack's per-user install avoids Program Files and UAC (**supported hypothesis**). Starfield itself is often in Program Files (Steam default) or a Game Pass (WindowsApps / XboxGames) folder, which needs separate handling: **supported hypothesis**. |
| **UAC** | Writing into the Steam Starfield folder under Program Files may need elevation depending on ACLs | **supported hypothesis**. Do not run the whole app elevated (PyInstaller onefile as admin is explicitly risky: **verified**, PyInstaller docs above). |
| **Non-ASCII user names** | Python 3.6+ uses wide-char APIs for str paths (PEP 529) and Python 3.15 is planned to default to UTF-8 mode (PEP 686) | **supported hypothesis** (PEP pages rate-limited, not read). Risks remain in subprocess output decoding and in .NET/Archive2 tools receiving paths: test with a user named e.g. `Jürgen 測試` (**supported hypothesis**). |
| **Idle priority** | The backbone already supports `--idle` (verified in repo). IDLE vs BELOW_NORMAL vs PROCESS_MODE_BACKGROUND_BEGIN (which also lowers I/O and memory priority) | API detail **supported hypothesis** (SetPriorityClass page rate-limited). Idle starves the job whenever the PC does anything (a game); BELOW_NORMAL is the usual compromise (**supported hypothesis**). |
| **Sleep during long jobs** | `SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)` prevents idle sleep; it "cannot be used to prevent the user from putting the computer to sleep" (lid, power button); per-thread; clear with `ES_CONTINUOUS` alone; don't use away mode on laptops | **verified**: https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-setthreadexecutionstate . So resume-after-sleep must work anyway (the driver already resumes). |
| **Disk free with hard links** | Hard links make folder sizes double-count; the backbone's `measure` counts links once (verified in repo). Free space from GetDiskFreeSpaceEx is volume-level and correct; the error is in estimating what deleting frees | API claim **supported hypothesis**. Hard links only work within one NTFS volume (**supported hypothesis**), so work and output folders must be on the same drive (GAMMA's "same drive" rule is the same idea). |
| Antivirus scanning tens of thousands of files | Real-time scanning slows mass file writes; GAMMA and Wabbajack advise exclusions | **verified** advice (GAMMA wiki); performance effect **supported hypothesis**; measure on the PC. |

## 6. Logs, crash reports, support bundles, telemetry

- **Wabbajack**: logs in `<Wabbajack folder>\<version>\logs`; the newest log is the one for the failed install; the
  end of the log lists download links that failed (**verified**, Wabbajack FAQ). Also asks for 40 to 60 GB headroom
  (**verified**, same page).
- **GAMMA**: support is through Discord and a Technical Support FAQ; no log instructions on the install wiki
  (**verified**, GAMMA wiki).
- **MO2**: writes logs and crash dumps in its instance folder (`logs`, `crashDumps`): **supported hypothesis** (searches
  returned only forum titles; not read).
- **Vortex telemetry**: anonymous in-app pageviews sent to Google Analytics; "Data is only collected and sent with the
  express permission of each user"; toggle at Settings > Vortex > "Diagnostics and usage data"; "nor does this collect
  any data on what mods you are using" (**verified**: https://help.nexusmods.com/article/121-diagnostics-usage-data-vortex).
  Crash reporting not covered on that page (**unresolved**).
- Norm (**supported hypothesis**): in this scene telemetry is opt-in or absent, and support runs on "send me your log"
  in Discord or GitHub issues. SignPath's terms also require that signed projects "respect user privacy" and publish a
  privacy statement (**verified**, signpath.org/terms), which makes zero-telemetry the cheap default.
- Support bundle contents that would be useful for us (**supported hypothesis**): the driver's `state.json`, the failed
  step's log, the build manifest (already contains versions and hashes, no assets), detect output, Plugins.txt, the
  install records; with user name and drive paths redacted (the user profile folder -> `%USERPROFILE%`), and never any game
  file contents.

## 7. Accessibility and localization

- LOOT localizes through Weblate; MO2 through Transifex/Discord volunteers (**verified**, repo pages above).
- Qt widgets expose UI Automation to screen readers on Windows; Tkinter's support is weak; WebView2 apps inherit
  Chromium's accessibility (**supported hypothesis**, not read this session).
- Basics for us (**supported hypothesis**): all strings in one catalogue from day one (Qt `.ts` or gettext `.po`), no
  text baked into images, keyboard-only operation, honour Windows text scaling and high contrast, progress shown as text
  (step N of M, ETA) not colour only, and plain-language error messages with a "copy details" button. Paths and file
  sizes formatted with the system locale.

---

## Questions this raises for our launcher

Each: why it matters, what answers it, recommended default where evidence supports one.

1. **Which UI stack: PySide6, Tauri+Python sidecar, or .NET (Avalonia/WPF) driving Python?**
   Why: decides toolchains, bundle size, AV exposure, who can maintain it. Answer: a one-day spike building the same
   three screens (detect, progress, restore) in PySide6 and one alternative, measuring installer size and cold start.
   Default: **PySide6 in-repo, GUI process separate from the build-driver subprocess** (Python core already exists;
   Qt has MO2/LOOT precedent; LGPL fine for an OSS project).
2. **How do we ship Python: PyInstaller onedir, embeddable CPython + small native stub, or uv bootstrap?**
   Why: AV false positives and update size. Answer: build all three in CI, scan each on VirusTotal and with Defender
   on a clean Windows VM, record results and sizes in optimization.md. Default: **PyInstaller onedir with a
   self-built bootloader, signed** (works with Velopack; onefile is ruled out by Velopack and by `_MEI` leftovers).
3. **Can we get SignPath Foundation signing given one shared GitHub account for all agents?**
   Why: free signing is the only no-cost way out of "Windows protected your PC"; their terms want named roles and
   MFA. Answer: email SignPath with our setup (owner = sole Approver, agents = Authors under the owner's account).
   Default: **apply to SignPath; fall back to Azure Artifact Signing ($9.99/month) only if the owner is in the US/Canada
   as an individual**; never EV.
4. **Where does the release build run?** Why: SignPath requires signing output of an automated build from source.
   Answer: does a GitHub Actions `windows-latest` job reproduce today's tests and produce the bundle with no game files?
   Default: **GitHub Actions Windows job; game-file-dependent tests stay on the PC**.
5. **Self-update: Velopack, or "check GitHub Releases and tell the user"?**
   Why: auto-update during a 6-hour build is dangerous; manual update is GAMMA's approach. Answer: read Velopack's
   main docs (delta, per-user install, signing hooks) and prototype with a dummy app. Default: **Velopack with update
   check at startup only, never applied while a build or install is active, user confirms**.
6. **Do we keep the launcher's work folder short and outside protected locations, and enforce it?**
   Why: MAX_PATH, CFA, OneDrive sync of tens of GB, Program Files UAC. Answer: list the longest path our build writes
   (from a real build manifest) and test with LongPathsEnabled off. Default: **refuse work roots under Users,
   OneDrive, Program Files or a drive root; suggest `<drive>:\FO4SF`; `detect` reports the longest path budget**
   (Wabbajack and GAMMA rules, verified).
7. **Are our exes long-path aware?** Why: the registry switch does nothing without the manifest. Answer: dump the
   manifest of the PyInstaller exe, python.exe, and each dotnet tool (`mt.exe -inputresource` or sigcheck) and create
   a 300-char path in a test. Default: **set longPathAware in our exe manifest anyway, and still keep paths short**.
8. **How do we find Documents\My Games\Starfield reliably?** Why: OneDrive redirection is common (verified Nexus
   article) and Game Pass vs Steam may differ. Answer: call SHGetKnownFolderPath on the owner's PC and on a OneDrive
   test account and compare. Default: **Known Folder API only; show the resolved path to the user in detect**.
9. **Does Controlled Folder Access block our writes, and do we write in Documents at all?** Why: a blocked write
   looks like success unless we check. Answer: enable CFA in Block mode on a test VM and run install/restore.
   Default: **avoid writing in Documents (we do not edit INIs today); if we ever must, verify each write by reading back
   and tell the user how to allow the app if blocked**.
10. **Does restore cover the Documents\My Games\Starfield\Data loose-file folder?** Why: Starfield reads two Data
    folders (verified); a player's loose files there could override ours or survive our restore. Answer: snapshot it
    in `snapshot` on the PC and see what is there. Default: **record it read-only and warn if it holds files that
    overlap ours**.
11. **Which priority class and I/O priority for build steps?** Why: Idle may starve the build whenever the player
    games; normal makes the PC sluggish. Answer: time one recipe step at Idle, Below-normal and with background mode
    while a game runs (optimization.md before/after). Default: **Below-normal CPU plus background I/O; Idle as an
    option**.
12. **Do we hold off sleep during builds, and how do we survive the sleep we cannot stop?** Why: lid close and power
    button always win (verified). Answer: test pause/resume of the driver across a manual sleep. Default:
    **SetThreadExecutionState(ES_CONTINUOUS|ES_SYSTEM_REQUIRED) only while a step runs, cleared after; no display
    flag; rely on the resumable driver after any sleep**.
13. **What free-space number do we show and enforce?** Why: hard links make folder sizes lie; GAMMA says 150 GB,
    Wabbajack says keep 40 to 60 GB extra. Answer: measure a full build's real cost with `launcher.py measure`.
    Default: **volume free space from the OS, need computed from recipe `need_gb`, plus the existing 40 GB floor;
    work and output on the same NTFS volume**.
14. **How do we handle antivirus during builds?** Why: scanning tens of thousands of written files slows builds and
    may quarantine our tools. Answer: time a build step with and without a Defender exclusion on the PC. Default:
    **do not ask players to disable AV; document an optional exclusion for the work folder only, with the measured
    speed-up**.
15. **What goes in a support bundle and how is it redacted?** Why: support will run on logs (Wabbajack/GAMMA
    pattern) and SignPath wants a privacy statement. Answer: draft the bundle from the driver state, step log, manifest,
    detect output, install records; check it on the owner's PC for personal data. Default: **one-click zip, user name
    replaced by %USERPROFILE%, no telemetry, nothing sent automatically**.
16. **Do we collect any telemetry or crash reports?** Why: privacy norms in the scene are opt-in (Vortex, verified).
    Answer: owner decision. Default: **none in v1; crash reports are local files the user attaches to an issue**.
17. **Is a non-ASCII user name safe end to end (Python, subprocess output, dotnet tools, Archive2)?** Why: Windows
    tools often break on such paths. Answer: run detect plus one recipe on a Windows account named with accented and
    CJK characters. Default: **force UTF-8 for our subprocess I/O (`PYTHONUTF8=1`, `encoding="utf-8"`), pass paths as
    arguments not via shell**.
18. **Where do Starfield and its Plugins.txt live for Game Pass vs Steam, and do we need elevation?** Why: Steam in
    Program Files and Game Pass folders have different permissions. Answer: test on both installs. Default: **support
    Steam first (owner's install); refuse Game Pass with a clear message until tested; never run the GUI elevated, and
    elevate only a single copy step if ever needed**.
19. **How does a launcher update interact with an in-progress build's fingerprints?** Why: new code reruns steps
    (driver fingerprints code content). Answer: unit test: update code between runs and check the status view says
    which steps will rerun. Default: **block updates while a build is unfinished, or show "updating will redo N steps
    (about X hours)"**.
20. **Licence of the shipped bundle:** GPL-3 Mutagen tools + LGPL Qt + our licence. Why: SignPath requires OSI and no
    proprietary bits; GPL-3 needs source offer. Answer: list every shipped file and its licence (a CI step). Default:
    **ship sources via the tagged GitHub release; include licence texts in the bundle**.
21. **Localization and accessibility from the first screen?** Why: retrofitting strings is expensive. Answer: pick the
    catalogue format with the framework. Default: **all strings through one translation function from day one; English
    only at first; keyboard-only and screen-reader smoke test before release**.
22. **Is the TTW installer's approach relevant (patch-based installer from the user's own game files)?** Why: TTW is
    the closest precedent for "build from the player's own Bethesda files, ship no assets". Answer: read TTW's install
    guide and installer docs (not reached in this session). Default: none yet (**unresolved**).

## Sources read in this session
- https://signpath.org/terms
- https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/code-signing-options
- https://learn.microsoft.com/et-ee/windows/apps/package-and-deploy/smartscreen-reputation
- https://www.microsoft.com/wdsi/filesubmission
- https://docs.velopack.io/getting-started/python
- https://discuss.python.org/t/pyinstaller-false-positive/43171
- https://pyinstaller.org/en/latest/bootloader-building.html
- https://pyinstaller.org/en/v5.2/operating-mode.html
- https://pydevtools.com/handbook/explanation/how-do-i-ship-a-python-application-to-end-users.md
- https://pydevtools.com/handbook/reference/nuitka/
- https://docs.astral.sh/python-build-standalone/
- https://www.pythonguis.com/faq/not-an-open-source-application-which-one-to-use-pyqt5-or-pyside2/
- https://dolthub.com/blog/2025-11-13-electron-vs-tauri
- https://chromium.googlesource.com/external/github.com/python/cpython/+/3.7/Doc/using/windows.rst
- https://learn.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation
- https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-setthreadexecutionstate
- https://learn.microsoft.com/defender-endpoint/controlled-folders
- https://nexusmods.com/starfield/articles/116
- https://www.nexusmods.com/starfield/articles/578
- https://wiki.wabbajack.org/user_documentation/Troubleshooting%20FAQ.html
- https://help.nexusmods.com/article/121-diagnostics-usage-data-vortex
- https://github.com/wabbajack-tools/wabbajack , https://github.com/ModOrganizer2/modorganizer ,
  https://github.com/Nexus-Mods/Vortex , https://github.com/loot/loot , https://github.com/Mutagen-Modding/Synthesis ,
  https://github.com/TES5Edit/TES5Edit , https://github.com/Grokitach/Stalker_GAMMA ,
  https://github.com/Grokitach/Stalker_GAMMA/wiki/Installing-GAMMA
