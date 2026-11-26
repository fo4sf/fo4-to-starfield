Title: All Fallout titles (Fallout 4 first, then 3, New Vegas, 1, 2, Tactics, and 76) | Mode: Story & Warfare (+ Survival layer) | Track: Track 1 & Track 2 shared launcher — design note + offline first slice (`prototype, offline` for first slice; `design only` for remaining phases)

# Launcher Better Methods & GAMMA-Style Standalone Launcher (`X8`)

> **Status (`R15` Honesty):** This note combines **design only** architecture (`(a)`–`(e)`) with an **offline first slice (`prototype, offline`)** built on `src/fo4sf/launcher/*` (three-step `Locate -> Build or Update -> Play` workflow strip on the existing six-tab GUI plus the stand-alone `StartCover` component in `src/fo4sf/launcher/start_cover.py`, gated **OFF by default** behind `start_cover = false`). Nothing in the first slice starts `Starfield.exe` in tests, and the real boot cover check belongs to Claude (PC) via [launcher-start-cover-card.md](../testing/launcher-start-cover-card.md).

---

## 1. Leading Direction: Our Own Standalone GAMMA-Style Launcher

We build a standalone total-conversion experience on Starfield's engine where Starfield's own start, menus, star map, and content are stripped out and replaced, depending on **no third-party mod and no third-party mod manager** (SFSE is our only external runtime hook). **Our own standalone FO4SF Launcher is therefore the primary program a player opens** — not an optional wrapper around Mod Organizer 2 or Vortex.

### How S.T.A.L.K.E.R. G.A.M.M.A.'s Launcher Works, and How Ours Adapts It
- **What G.A.M.M.A. does ([Grokitach/Stalker_GAMMA](https://github.com/Grokitach/Stalker_GAMMA), [Mord3rca/gamma-launcher](https://github.com/Mord3rca/gamma-launcher)):**
  - Presents a single purpose-built window centered on **Install / Update** and **Play** over a clean base *S.T.A.L.K.E.R. Anomaly* folder.
  - Fetches modular add-ons from ModDB/Git, verifies every archive checksum before extraction (`check-md5` in community launchers), generates a pre-configured Mod Organizer 2 instance, and launches via `GAMMA Launcher -> MO2 -> Anomaly Launcher -> Engine`.
  - *(Background note only: GOG later packaged a one-click G.A.M.M.A. distribution, **but per owner direction of 21 Nov 2026, GOG is NOT an option for FO4SF.** We design zero GOG release, zero GOG one-click route, and zero GOG-specific features; we target Steam + our own standalone launcher, while leaving existing read-only GOG Fallout 4 source-folder detection in `src/fo4sf/launcher/locate.py` (`LA-5`) untouched.)*
- **How FO4SF improves on that flow without MO2 in the middle:**
  1. **Zero redistributed game assets:** Instead of downloading mod archives, our launcher hashes the player's own local Steam Fallout 4 (`1.10.163` + DLCs) and Steam Starfield (`1.16.244` + SFSE) installations against `known_sources.json` and `known_runtimes.json` (`SHA-256`, stronger than MD5), converts locally via resumable `driver.py` recipes, and verifies output manifests (`manifest.py`).
  2. **Direct isolated instance instead of a middleman mod manager:** `src/fo4sf/launcher/instance.py` ([fo4sf-instance.md](fo4sf-instance.md)) creates a dedicated FO4SF game folder beside Steam's Starfield using **same-drive NTFS hard links** for vanilla `Data/` and `Tools/` (`0` extra GB for ~120 GB of base archives) plus isolated copies of `Starfield.exe`, SFSE, `Starfield.ini` (`SLocalSavePath=Saves\FO4SF\`), and a crash-journaled `Plugins.txt` swap (`FO4SF-swap.json`). The player's vanilla Steam Starfield and its mods are never touched.
  3. **Direct boot + Start Cover (`Launcher -> sfse_loader.exe`):** Because no MO2 window sits between our launcher and `Starfield.exe`, our launcher owns the entire boot window — arming `crashwatch.py`, displaying a clean-room Fallout-style **Start Cover** over Starfield's boot/menu load, and handing restart-only choices directly to our SFSE plugin.

---

## 2. Comparison: FO4SF Standalone Launcher vs. Mod Organizer 2 (`usvfs`) vs. Vortex

| Dimension | Mod Organizer 2 (`v2.5.0`–`v2.5.2+`, `usvfs`) | Vortex (Hardlink + Folder Junction) | FO4SF Standalone Launcher (`src/fo4sf/launcher/*`) |
|---|---|---|---|
| **Core deployment mechanism** | User-Space Virtual File System ([ModOrganizer2/usvfs](https://github.com/ModOrganizer2/usvfs)) hooks Win32 file APIs in memory; mods stay outside `Data/`, and MO2 **must stay running** during play ([MO2 v2.5.0 release](https://github.com/ModOrganizer2/modorganizer/releases/tag/v2.5.0)). | Physical **NTFS hardlinks** (or symlinks) from a staging folder on the same volume into `Data/`, plus a directory junction for `Documents\My Games\Starfield\Data` ([Starfield Modding Wiki — Vortex](https://starfield.modding.wiki/en/vortex)). | **Isolated FO4SF instance (`instance.py`)** hard-linking vanilla `Data/` & `Tools/` on the same NTFS volume, paired with **SHA-256 install receipts** (`FO4Port.deploy.json`, `FO4SFExp.install.json`, `FO4SFSidecar.install.json`) and snapshot `restore.py`. |
| **Root-folder & SFSE handling** | `usvfs` **cannot virtualize root binaries** (`Starfield.exe`, `sfse_loader.exe`, `sfse_*.dll`, proxy DLLs). Requires manual root copying or the third-party [Kezyma Root Builder](https://github.com/Kezyma/ModOrganizer-Plugins) sync plugin. | Requires Starfield-specific root-deployment extension rules; historically fragile across Starfield root vs `Data/` vs `Documents\My Games\Starfield\Data` splits. | **Native:** `instance.py` copies `Starfield.exe` + `sfse_loader.exe` + `sfse_*.dll` into the FO4SF instance once (verified by `known_runtimes.json` SHA-256) and installs `Data/SFSE/Plugins/*.dll` with `sidecar-install` / `sidecar-undo` receipts. |
| **Install & rollback safety** | High for `Data/` (disabling a mod unmounts its virtual layer); root files rely on Root Builder backup manifests. | Purge removes tracked hardlinks, but interrupted deployments or external edits leave orphaned links or mismatches. | **Deterministic & fail-closed (`recovery.py`, `restore.py`):** Every installer refuses overwrites, records SHA-256 per file, blocks `Play` if any receipt has `complete: false` or `cleanup_pending`, and journals `Plugins.txt` byte-for-byte in `FO4SF-swap.json` across crashes or power cuts. |
| **OneDrive & `Documents` traps** | Profile-local INIs avoid shared INI edits when configured, though `My Games\Starfield` redirection interacts with `usvfs`. | **Severe trap:** OneDrive syncing `Documents\My Games\Starfield` breaks Vortex's `Use Folder Junction` / hardlinks, causing vanishing loose files and sync locks; Windows **Controlled Folder Access (CFA)** also blocks script writes into `Documents` (observed on owner PC, `first-run-failures-1014.md`). | **Solved by design:** `detect.py` and `instance.py` refuse work/instance folders inside OneDrive, Dropbox, Google Drive, iCloud, `Users`, or `Program Files`, and write `SLocalSavePath=Saves\FO4SF\` + `[Papyrus]` keys into the instance's own `Starfield.ini` (`H3`), avoiding `Documents` writes entirely. |
| **Many plugins (`13` player / `22` test / multi-title)** | MO2 `v2.5.0+` manages `Plugins.txt`, `Starfield.ccc`, light (`FE`) and medium (`FD`) ESM flags natively. | Manages `Plugins.txt` via LOOT rules; ordering custom multi-plugin total-conversion stacks requires manual lock rules so LOOT does not scramble master-dependent slots. | **Exact deterministic order (`load_order.py` + `plugin_checks.py`):** Preserves pinned Track-1 (`13` ESMs) and Track-2 (`22` ESMs) slot order, refuses `BlueprintShips-Starfield.esm` masters, and avoids `sTestFile1..10` (which caps at `10` plugins and since Starfield `1.16.236` rewrites shared `Plugins.txt`). |
| **Update path** | Steam updates mutate the shared root `Starfield.exe` unless the user manually builds a `100+ GB` "Stock Game" copy. | Steam updates overwrite the live Starfield folder directly, breaking SFSE until updated. | **Double guard:** `known_runtimes.json` refuses mismatched `Starfield.exe`/`sfse_*.dll` hashes before changes, `instance.py` isolates copied binaries from Steam updates (`H4`), and `selfupdate.py` fast-forwards launcher code when opted in. |

### Explicit Recommendations: Keep, Adopt, Skip
- **KEEP (already proven in `src/fo4sf/launcher/*`):**
  - `instance.py` same-drive hard-linked FO4SF folder + `FO4SF-swap.json` `Plugins.txt` crash journal.
  - Per-installer SHA-256 receipts (`deploy_starfield.py`, `exp_install.py`, `make_core_bundle.py sidecar-install`), `recovery.py` pre-Play gate, and `restore.py` snapshots.
  - `known_sources.json` + `known_runtimes.json` SHA-256 input/runtime pinning and `crashwatch.py` (`settle_s` delayed ProcDump attach avoiding Steam `ERROR 84`).
- **ADOPT NEXT:**
  1. **GAMMA-style 3-step primary workflow (`1. Locate -> 2. Build or Update -> 3. Play`)** at the top of our standalone launcher GUI (first slice built in this PR!).
  2. **Hard-link stage-to-instance bundle deployment with SHA-256 receipt:** When `candidate-2f` (or a player's local `driver.py` stage) sits on the same NTFS volume as the FO4SF instance, `exp_install.py` / `deploy_starfield.py` can hard-link `.ba2` and `.esm` outputs into `<instance>/Data` (recording inode + SHA-256 in the existing install receipt, never mutating linked files in place) so staging + installing does not pay `2x` disk for `4+ GB` `.ba2` archives.
  3. **File-signaled Fallout-style Start Cover (`start_cover.py`)** + `FO4SFLaunchChoices.ini` handoff for restart-only choices and optional SFSE main-menu skip.
- **DO NOT ADOPT (not worth the complexity or actively harmful):**
  - **Writing or bundling a `usvfs`-style API hook DLL:** High antivirus false-positive rate, fragile across Windows 11 builds, and unnecessary when `instance.py` NTFS hardlinks give zero-overhead kernel file reads without a resident hook.
  - **Vortex-style `Documents\My Games\Starfield\Data` folder junctions:** Collides with OneDrive and Windows Controlled Folder Access; packing `.ba2` archives + instance-local `Data/` avoids `My Games\Data` completely.
  - **`sTestFile1..10` plugin loading:** Hard-capped at `10` plugins and corrupts shared `Plugins.txt` on Starfield `1.16.236+`.
  - **Papyrus log tailing for boot readiness:** Risks file-share/rotation hazards (Section 3 `(b)`).

---

## 3. GAMMA-Style Standalone Architecture (`(a)`–`(e)`)

### `(a)` One Window, Three Big Steps — Plus Packaged `.exe` Distribution
1. **Three-Step Workflow Strip (`1. Locate -> 2. Build or Update -> 3. Play`) over the Existing 6-Tab Window:**
   - **Step 1 — `Locate`:** Auto-detects Steam Fallout 4 (`377160` + DLC depots), Steam Starfield (`1716740`), and `My Games\Starfield`, shows the `3/3` confirmation state, and focuses the `⌂ Locations` tab (`Confirm locations`).
   - **Step 2 — `Build or Update`:** Runs read-only `Check installation` / `Build status` (`driver.py` resumable step state, free-space floor, SHA-256 receipts) and `Update` on the `● Status` tab (and future one-click `Build / Update Bundle` recipe runner).
   - **Step 3 — `Play`:** Runs pre-flight checks, arms `crashwatch.py` if enabled, optionally raises the `Start Cover`, swaps `Plugins.txt` when `instance` is set, and launches `sfse_loader.exe`.
   - All six existing tabs (`Locations`, `Status`, `Settings`, `Tests`, `Mod tools`, `Log`), both themes (`DARK_PALETTE` / `LIGHT_PALETTE`), `Reload`, `Save settings`, and `Recover install` stay intact underneath.
2. **Packaged `.exe` (No Python or .NET SDK Required on the Player's PC):**
   - **Packaging tool comparison:**
     - **PyInstaller `--onedir` + Inno Setup installer *(Recommended)*:** Packages `launcher.py`, `src/fo4sf/*`, Python `3.12+` runtime, `tkinter`/Tcl-Tk, `Pillow`, and `numpy` into `FO4SF-Launcher\FO4SF-Launcher.exe` + `_internal\` ([PyInstaller Manual](https://pyinstaller.org/en/stable/operating-mode.html)). Estimated size: `~35–55 MB` uncompressed (`~15–22 MB` installer) for launcher+Tk alone, or `~95–140 MB` uncompressed (`~38–55 MB` installer) when bundling `numpy` + `Pillow` + self-contained C# plugin writers (`dotnet publish -c Release --self-contained true -r win-x64 -p:PublishSingleFile=true` for `dotnet/*`). Crucially, `--onedir` **does not unpack executables into `%TEMP%\_MEIxxxxxx` at startup**, avoiding the #1 heuristic trigger in Windows Defender ([PyInstaller issue #6754](https://github.com/pyinstaller/pyinstaller/issues/6754)).
     - **PyInstaller `--onefile` *(Avoid)*:** Extracts DLLs/PYDs into `%TEMP%` on every launch; slows cold start by `1–3 s` and is routinely quarantined by Windows Defender / SmartScreen heuristics as a packed dropper.
     - **Nuitka `--standalone` *(Fallback)*:** Compiles Python to C via MSVC, reducing script-packer heuristics further at the cost of `10–20 min` CI C++ compile times.
   - **Antivirus false-positives & Authenticode code-signing:**
     - Stock precompiled PyInstaller bootloaders share hashes across thousands of unsigned tools. Building PyInstaller's bootloader from source on our clean CI runner + shipping `--onedir` removes stock-stub signature collisions.
     - **Code signing (`signtool sign /fd sha256 /tr ... /td sha256`):** Unsigned `.exe` files trigger Windows SmartScreen *"Windows protected your PC"*. Standard OV certificates (or **Azure Artifact Signing / Trusted Signing**) establish publisher identity immediately and clear SmartScreen after download reputation accrues; EV hardware-token certificates clear SmartScreen immediately at higher annual cost; pre-release hashes can also be submitted via [Microsoft Security Intelligence file submission](https://www.microsoft.com/en-us/wdsi/filesubmission).

### `(b)` Start Cover: Hiding Starfield's Boot, Logos, Menu & Initial Load Safely
While `Starfield.exe` initializes DX12, loads `.esm`/`.ba2` archives, and enters the starting cell, the launcher can display a full-screen Fallout-style **Start Cover** (`src/fo4sf/launcher/start_cover.py`) containing **our own clean-room terminal art, frame, and status lines only — zero Bethesda logos, music, or movies**.

1. **What `"ready"` means and where the signal comes from (NO log tailing):**
   - **Why NOT log tailing:** An external reader polling or tailing `Documents\My Games\Starfield\Logs\Script\User\*.log` (`Get-Content -Wait` or unshared file opens) is fragile under Windows Controlled Folder Access, can hold directory/file handles across log rotation when orphaned, and requires `[Papyrus] bEnableLogging=1` (which costs script VM RAM/disk even for normal players!).
   - **Preferred signal (`start_ready.json` sentinel file or Win32 named pipe):**
     - Before spawning `sfse_loader.exe`, the launcher generates a per-launch `nonce` (UUID4) and deletes any stale `%LOCALAPPDATA%\FO4SF\start_ready.json`.
     - Our SFSE plugin (`FO4SFPipboyMenu.dll`, loaded on every `route=sfse` run even when `bEnableLogging=0`) writes `<temp>.tmp` and atomically renames (`MoveFileExW(MOVEFILE_REPLACE_EXISTING)`) `%LOCALAPPDATA%\FO4SF\start_ready.json` containing `{"status": "ready", "nonce": "<nonce>", "pid": <pid>, "stage": "vault111_stage20"}` the moment **player 3D & starting cell settle** (for Story: `FO4SF_NewGame` `stage 20` pod settle; for saved games: `kPostLoadGame` + first `PlayerCharacter` 3D ready; an optional Win32 named pipe `\\.\pipe\FO4SF_StartReady_<nonce>` can wake the launcher with `0 ms` poll latency, with the atomic JSON file as universal fallback).
     - Reading `start_ready.json` opens a `120`-byte file inside `%LOCALAPPDATA%\FO4SF` (our own folder, outside `Documents` and outside `Data/`), reads, and closes immediately on each `200 ms` tick — **zero game-log locks, zero Papyrus logging requirement**.
2. **Timeout, Cancel, and Crash-Watcher Override (Safety Invariants):**
   - **Crash watcher ALWAYS wins:** Every poll tick (`200 ms`) checks `crashwatch` / `System.pids()` and crash-event callbacks *before* checking the signal file. If `Starfield.exe` exits early (after first PID seen), if `crashwatch` records a crash/dump, or if `WerFault.exe` appears, the cover **destroys itself immediately (`reason="crash_or_exit"`)** so a crash dialog, assertion box, or desktop error banner is **never** obscured.
   - **Hard timeout:** Bounded `timeout_s` (default `90.0 s`, configurable `5..300 s`). If `"ready"` has not arrived when the deadline expires, the cover **auto-closes (`reason="timeout"`)** so a hung loading spinner (`playtest-issues.md` #41) is immediately visible to the player.
   - **Visible `Cancel` button (`Dismiss cover` + `Esc` on cover):** Always rendered in high-contrast monochrome at the bottom-right of the cover; clicking it dismisses the cover (`reason="cancelled"`) without terminating `Starfield.exe`.
3. **Display Modes, Multi-Monitor, `Alt+Tab`, Focus, Input & Controller Players:**
   - **Zero input injection & zero focus theft:** The cover never sends keystrokes/mouse events to `Starfield.exe` and never calls `focus_force()` or `grab_set()`. On Windows (`ctypes.windll.user32`), applying `WS_EX_NOACTIVATE | WS_EX_TOPMOST` (`GWL_EXSTYLE`) keeps `Starfield.exe` as the active foreground input target while the cover sits visually above it until `"ready"`.
   - **Borderless vs. exclusive fullscreen:** Desktop topmost windows compose cleanly over **borderless fullscreen / windowed** DX12 (`bBorderless=1`, `bFull Screen=0` in `StarfieldPrefs.ini`, Starfield's default PC fullscreen mode). True exclusive fullscreen (`bBorderless=0`, `bFull Screen=1`) either preempts desktop windows or minimizes when another window tops it; when `start_cover=true`, pre-flight checks `StarfieldPrefs.ini` and warns if exclusive fullscreen is forced.
   - **Two monitors:** The cover sizes itself to the **single target monitor's geometry** (`root.winfo_screenwidth()` x `root.winfo_screenheight()` at `+0+0`, or the monitor hosting Starfield) rather than `SM_CXVIRTUALSCREEN`, leaving secondary monitors completely uncovered for reference cards, logs, or chat.
   - **`Alt+Tab` & controller-only players:** If the player `Alt+Tab`s to an unrelated desktop app (neither Starfield nor the launcher owns foreground), the cover drops `-topmost` so it never traps the desktop. Controller-only players never need to touch a mouse or keyboard on the cover: it appears automatically at `Play` and vanishes automatically on `"ready"`, crash, or timeout.

### `(c)` What Belongs in the Launcher vs. In Game (`21 Nov` Restart-Only Rule)
Per the owner's `21 Nov 2026` rule (narrowing the earlier `19 Nov` line): **ONLY choices that would require a game restart if changed mid-session belong in the launcher; everything else is chosen IN GAME.**

| Choice / Option | Where Chosen | Why (Restart-Only Test) | Handoff Mechanism |
|---|---|---|---|
| **Game / Title World** (`Fallout 4` first; later `FO3`, `FNV`, `FO1`, `FO2`, `Tactics`, `FO76`) | **Launcher** | Changes which master `.esm`s and `.ba2` world archives load in `Plugins.txt`; Starfield reads `Plugins.txt` once at process boot. | `Plugins.txt` profile + `[Launch] Title=` in `FO4SFLaunchChoices.ini`. |
| **Bundle Profile** (`player` `13` ESMs vs `test` `22` ESMs) & **Optional Core Modules / Kits** (`A-Life`, `Bridge`, standalone kits) | **Launcher** | Adds/removes `.esm` plugins and SFSE sidecar `.dll`s loaded once at startup. | `exp_install` / `plugin_toggle` / `test_kits` + `Plugins.txt`. |
| **Game Mode (`Story` vs `Warfare`) & Start Preset** *(when switching plugin set or pre-load start cell)* | **Launcher** | Determines whether `FO4SF_NewGame` enters Vault 111 Story cryo or a Warfare faction spawn **before** the first cell loads (and whether Warfare-only A-Life/radiant plugins are enabled). | Launcher writes `GameMode=1\|2` and `StartPreset=<id>` into `FO4SFLaunchChoices.ini`; `FO4SFPipboyMenu.dll` sets `FO4SF_GameMode` (`06000870`) at `kPostDataLoad` before `OnQuestInit`. |
| **Launch Route, Instance, Crash Watcher, Papyrus Logging, Start Cover & SFSE `.ini` Gates** | **Launcher** | Process-spawn flags (`sfse_loader.exe`, `Starfield.ini`, `FO4SFPipboyMenu.ini`, ProcDump attach) read once at OS launch. | `launcher_settings.json`, `<instance>\Starfield.ini`, `FO4SFPipboyMenu.ini`. |
| **Character Appearance** (`Quick start` / `Customize`) | **In Game** | Engine `ChargenMenu` / actor face morphs run live inside the loaded session (`T4` verified single box). | `FO4SF_NewGameQuest` stage `10 -> 20`. |
| **S.P.E.C.I.A.L. Allocation (`40` pool for all titles)** | **In Game** | Live ActorValues (`0x810..0x816`), changeable at start room / Vault 111 lift and one-time exit rebuild without restarting. | In-game allocator (`FO4SF_ProgressionQuest` / `FO4SF_NewGameSpecial`). |
| **Backgrounds, `0..2` Traits, `3` Tagged Skills, Skill Points & Perks** | **In Game** | New Vegas-expanded progression sheet ([character-system.md](../design/character-system.md)); mutates live `AVIF`/`PERK`/`GLOB` state with zero restart. | In-game character setup + Pip-Boy `STAT`/`PERKS` + vault-exit respec. |
| **Difficulty & Survival / Hardcore Layer Toggles** (hunger, thirst, sleep, ammo weight, dual radiation rules, warfare tuning) | **In Game** | Survival is a GAMMA-style layer of live `GLOB` switches over either `Story` or `Warfare`; players can tune hardcore rules mid-campaign in Settings -> Gameplay / Pip-Boy without restarting `Starfield.exe`. | Live `GLOB`s in `FO4SFCoreValues.esm` (`06000800+`) / MCM-style gameplay menu. |
| **Cross-Title Continuity Option** (complete reset per game vs carried character) | **In Game** (at title transition / New Game) | Campaign-transition state reset vs carry-over operates on player `AVIF`/`PERK` records at transition time, requiring no process restart unless switching installed title packs. | In-game campaign transition prompt (`FO4SF_ProgressionQuest`). |

- **Which of today's in-game boxes move OUT vs. STAY:**
  - **Moves OUT to Launcher:** The **boot-time Mode Picker MessageBox** (`Story` vs `Warfare` at `stage 5/10`), which sits directly on the `T3` first-box-invisible stall path (`known-issues.md`). Selecting `Story` or `Warfare` in the launcher before pressing `Play` hands `FO4SF_GameMode` (`06000870`) to the game via `FO4SFLaunchChoices.ini` so neither Story nor Warfare ever blocks on an unseen pre-load MessageBox!
  - **Stays IN GAME:** Character appearance (`Quick start` / `Customize`), S.P.E.C.I.A.L. (`40` pool), backgrounds & traits, tagged skills, vault-exit rebuild prompt, and all Survival/Hardcore gameplay sliders.
- **Cross-reference to `(c2)` In-Game Character System:** See [docs/design/character-system.md](../design/character-system.md) for the full New Vegas-expanded in-game character system specification and the analysis of fitting Fallout 4's `7x10` perk chart into the `SHARED` / `BASE-PLUS-DATA` / `PER-TITLE` framework.

### `(d)` Straight Into Our Game: Skipping Starfield's Main Menu
1. **Layer 1 — Strip Bethesda Intro Logos & Input Delay via Instance `Starfield.ini`:**
   - Setting `[General] SIntroSequence=0` and `uMainMenuDelayBeforeAllowSkip=0` inside the FO4SF instance's own `Starfield.ini` suppresses Starfield's startup logo bink sequence without touching the player's shared `StarfieldCustom.ini` ([SFSE GitHub](https://github.com/ianpatt/sfse)).
2. **Layer 2 — One-Shot SFSE Main-Menu Dispatch (`New Game` or Chosen Save):**
   - Existing SFSE community plugins (*Auto Recent Save Load (SFSE)*, *Auto Load*) demonstrate that an SFSE plugin can wait until `MainMenu` opens *after* Starfield finishes background archive/plugin initialization and then dispatch `LoadGame` or `NewGame`.
   - **What we write ourselves (zero third-party plugins):** Add an opt-in `[Launch]` reader in `FO4SFPipboyMenu.dll` reading `Data/SFSE/Plugins/FO4SFLaunchChoices.ini`:
     - `BootAction = none | new | continue | load` and `BootSave = <Saves\FO4SF\filename.sfs>`.
     - On the **first** `MainMenu` `kShow` message of the process (`g_bootDispatched == false`), `FO4SFPipboyMenu.dll` sets `g_bootDispatched = true`, deletes/clears the one-shot `BootAction` token (so a crash or a later `Quit to Main Menu` never loops!), and invokes the Scaleform/console `MainMenu` start/load entry.
     - Combined with `(b)` **Start Cover**, the cover stays visible from clicking `► Play` in our launcher until `FO4SF_NewGame` hits `stage 20` (or the chosen `.sfs` save finishes loading 3D), making `Launcher -> Vault 111 / Commonwealth` visually continuous with **zero Starfield main menu seen**.

### `(d2)` Where This Sits in the Whole Scope: Standalone Look, Warfare Start Sequence & Start Table
- **One continuous curtain (`10, 14 & 19 Nov` owner vision):**
  - On `10 Nov` ("getting the launcher ready") and `14 Nov` (standalone total-conversion look; Starfield's menus, logos, and planets removed; Warfare mode given a longer opening sequence that masks world/A-Life initialization), the launcher cover and the in-engine opening were aimed at the same problem from opposite ends of process boot:
    1. **Phase A (OS Launch -> Engine Cell Ready):** Launcher's `Start Cover` (`start_cover.py`) masks window creation, DX12 swapchain init, `MainMenu` auto-dispatch, and cell load.
    2. **Phase B (Engine Cell Ready -> World & A-Life Settled):** For `Story`, `stage 20` lifts straight into Vault 111 cryo (`pod settle ok=true`). For `Warfare`, `Start Cover` hands off at `"ready"` into our **in-engine Warfare deployment sequence** (faction briefing / gear roll / camera pan in `FO4SF_NewGame` while initial A-Life squads, garrisons, and nearby markers settle over `5–10 s`), so the player never sees pop-in or Starfield UI at either seam.
- **Data-Driven Start Location Table (keyed by `(title, mode, start_preset)`):**
  - Instead of hard-coding Vault 111, `FO4SFLaunchChoices.ini` passes a `start_key` resolved against a data table in `src/fo4sf/core/`:
    - `("fo4", "story", "vault111")` -> `FO4Port_Vault111Cryo` (Vault 111 cryo pod, pre-war/post-war path).
    - `("fo4", "warfare", "sanctuary_minutemen")` -> Sanctuary Hills exterior (`stage 210`, already proven `2/2` clean in `2c` with `RouteLoot` OFF).
    - `("fo4", "warfare", "concord_outskirts")` / `("fo4", "warfare", "red_rocket")` -> faction-keyed Commonwealth exterior nodes from `fo4sf_commonwealth.json`.
    - Future title rows (`("fo3", "story", "vault101")`, `("fnv", "story", "goodsprings")`, `("fo1", "story", "vault13_cave")`) plug into the exact same table without changing launcher or cover code.

### `(e)` What We Lose Against MO2, and Keeping `"Launch from MO2"` Supported Beside It
- **What our standalone launcher intentionally gives up vs. MO2:**
  - Drag-and-drop loose-file conflict ordering (`usvfs` left-pane priority) across dozens of arbitrary third-party Nexus texture/mesh mods.
  - Per-mod virtual `Overwrite` capture folders, third-party FOMOD XML wizard installers, and general-purpose LOOT sorting for non-FO4SF mod lists.
- **Why `"launch our bundle from MO2"` stays supported alongside our launcher:**
  - Our staged bundles (`candidate-2e`/`2f` and `build_alife_mod.py` `dist/` packages) already emit standard `Data/` (`*.esm`, `*.ba2`) + `Plugins.txt.snippet` + `Data/SFSE/Plugins/` trees (`docs/alife/MODDER-GUIDE.md`).
  - A player who wants to stack personal visual/accessibility mods in MO2 `2.5.2+` can install our staged bundle folder as an MO2 mod (placing `sfse_loader.exe` / `sfse_*.dll` in Starfield's root or via Root Builder, and keeping our pinned ESM order in MO2's right pane) and launch `sfse_loader.exe` through MO2. Supporting that costs us **zero extra code** while keeping our standalone launcher the default, dependency-free path for everyone else.

---

## 4. What Could NOT Be Verified Offline

1. **Programmatic `MainMenu` skip offset on `Starfield.exe 1.16.244`:** While community SFSE plugins (*Auto Recent Save Load*, *Auto Load*) confirm feasibility, we have not yet verified the exact Scaleform / `ConsoleCommand` / `BGSSaveLoadManager` call signature inside `FO4SFPipboyMenu.dll` in a live `1.16.244` session; `(d)` remains **design only** this round.
2. **Real DX12 swapchain & multi-monitor composition with `StartCover`:** Our unit tests verify `StartCoverController` state machines (`ready`, invalid nonce, timeout, `Cancel`, crash-watcher override) headlessly without launching `Starfield.exe`. Actual visual stacking over `Starfield.exe` in borderless fullscreen, `Alt+Tab` behavior, and controller focus preservation require Claude (PC)'s desktop run ([launcher-start-cover-card.md](../testing/launcher-start-cover-card.md)).
3. **Live PC verification of `instance.py` hypotheses `H1`–`H4`:** As recorded in [fo4sf-instance.md](fo4sf-instance.md), hard-linked instance boot (`H1`), `LOCALAPPDATA` vs known-folder `Plugins.txt` resolution (`H2`), instance-local `Starfield.ini` `SLocalSavePath` (`H3`), and Steam update copy-on-write behavior (`H4`) remain gated on live PC checks.
4. **Windows SmartScreen reputation warm-up:** Exact SmartScreen prompt duration for a freshly signed OV/Trusted-Signing PyInstaller `--onedir` build vs unsigned internal builds cannot be measured offline.

---

## 5. First Slice Built This Round (`prototype, offline`)

Stacked on `#842`'s six-tab, dual-theme GUI (`src/fo4sf/launcher/gui.py`, `src/fo4sf/launcher/settings.py`, `src/fo4sf/launcher/start_cover.py`):
1. **Opt-in setting (`OFF` by default):** `start_cover = False` (`bool`) and `start_cover.timeout_s = 90.0` (`float`) in `settings.SPEC` (with `start_cover.default_signal_path()` pointing to `%LOCALAPPDATA%\FO4SF\start_ready.json` and `--signal-file` overrides on `cover-preview` / `cover-signal`) — existing `play`, `settings`, crash watcher, and receipts behave identically when `start_cover` is `False`.
2. **Three-step workflow strip on the GUI (`1. Locate -> 2. Build or Update -> 3. Play`):** Live step-status model (`workflow_steps` in `gui.py`) rendered above the six-tab notebook (`Locations`, `Status`, `Settings`, `Tests`, `Mod tools`, `Log`) in both dark and light themes, guiding the player from folder confirmation -> build/install status -> `Play` without hiding any existing tab or button.
3. **Stand-alone Fallout-style `StartCover` component (`src/fo4sf/launcher/start_cover.py`):**
   - Clean-room terminal art/text (`FO4SF // PIP-OS BOOTLOADER`, step readout, elapsed/timeout countdown, zero Bethesda assets).
   - Pure-stdlib headless `StartCoverController` watching a signal file (`{"status": "ready"}` + optional `nonce`), supporting fake `"ready"` signals for offline testing, bounded `timeout_s`, `Cancel` button (`dismiss("cancelled")`), and immediate **crash-watcher override** (`dismiss("crash_or_exit")` when `crash_check()` or post-attach PID exit fires), plus `WS_EX_NOACTIVATE` non-focus-stealing Tk window wrapper (`StartCoverWindow`).

---

## 6. Consolidated Questions for the Owner

1. **Packaged `.exe` timing (`(a)`):** Should we wire a PyInstaller `--onedir` build recipe now for desktop testing, or keep running the launcher via `python scripts/launcher.py gui` until Track 1's opening mission chain (`A1`–`A6`) is verified in game?
2. **Code signing (`(a)`):** When external testers eventually receive builds, do you want to use Azure Trusted Signing / a standard OV certificate, an EV certificate, or hold signing until public release?
3. **Moving `Story vs Warfare` & bundle profile onto the launcher (`(c)`):** Do you approve moving the `Story vs Warfare` mode selector onto Step 3 (`Play`) of the launcher (passing `FO4SF_GameMode` via `FO4SFLaunchChoices.ini` before first load) so we can permanently retire the boot-time mode MessageBox (`T3` stall vector)?
4. **Main-menu auto-skip (`(d)`):** Once `Start Cover` passes its desktop visual check, should `FO4SFPipboyMenu.dll` add the opt-in one-shot `BootAction = new | continue | load` main-menu skip (default `none` until proven in game)?
