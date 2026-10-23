# Precedents: how "build it from the player's own files" installers work and fail

Research date: 2026-10-19. Author: Claude (research subagent).
Scope: TTW, Wabbajack, GAMMA, Fallout: London, TES Renewal / SureAI projects, and earlier cross-engine conversions.
Labels follow docs/ai/research-log.md: **verified** (with a URL I actually read, or source code I downloaded and read),
**supported hypothesis** (an inference from verified material), **unresolved** (looked for it, didn't find an answer).

Two notes on method:
- Many first-party docs (wiki.wabbajack.org, nexusmods.com, skyblivion.com) were rate-limited (HTTP 429) part-way
  through. Where that happened I used the projects' source code on raw.githubusercontent.com. Source-code findings
  give the file path.
- The TTW installer itself is closed source. Its package format is described here from a **third-party, clean-room
  Rust reimplementation** (SulfurNitride/TTW_Linux_Installer). So "this is what TTW's MPI format is" counts as a
  supported hypothesis: the reimplementation reports producing a working TTW install, but it is not TTW's own code.

---

## 1. Tale of Two Wastelands (TTW): installer internals

### 1.1 What the installer does
- **verified**: According to the official guide, the installer "Patches and creates all non-unique assets dynamically
  from original game files". It also decompresses both games' BSAs (the copies in the mod folder, not the
  originals), transcodes SFX from OGG to WAV, transcodes voice files to 24 kHz, round-trips FO3 radio MP3 → WAV → MP3,
  moves MP3s out of BSAs as loose files, updates Vorbis libraries to 1.3.7, and writes the Custom INI.
  https://thebestoftimes.moddinglinked.com/faq.html
- **verified**: The output goes into an MO2 mod folder the user creates ("Tale of Two Wastelands"). The installer
  takes three paths: FO3, FNV, and the output folder. Audio encoding is CPU-bound: "about 40 minutes on a Ryzen 5
  5600x", "several hours or even longer on a slower CPU". The install is checked by folder size: "should be 17GB",
  and anything else means it failed. https://thebestoftimes.moddinglinked.com/ttw.html
- **verified**: Requirements: English FO3 + FNV with all DLC, from Steam, GOG or Epic, with mixed stores allowed.
  "Only the English version of the game is supported." The PCR (Polish/Czech/Russian) FNV is supported if set to
  English, GFWL FO3 is supported if it's the English GOTY, and **Microsoft Store versions are not supported**. The
  German "No Gore" FNV is incompatible with xNVSE; Steam owners can use DepotDownloader to get the international
  EXE. You need at least 40 GB free, of which TTW is 17 GB. Windows 10+ 64-bit; "customized or LTSC Windows" is
  unsupported. https://thebestoftimes.moddinglinked.com/intro.html
- **verified**: TTW is distributed from MOD:PUB (needs an account), version 3.4.0, last updated 15 June 2026.
  https://mod.pub/ttw/133/docs/25-faq-frequently-asked-questions

### 1.2 The MPI package format (supported hypothesis: from the clean-room reimplementation)
Source read: `src/models/manifest.rs`, `src/models/asset.rs`, `src/services/install/file_verifier.rs`,
`src/services/archive/mpi/{mod,extractor}.rs`, `src/services/processing/xdelta.rs`, `CHANGELOG.md` in
https://github.com/SulfurNitride/TTW_Linux_Installer (fetched via raw.githubusercontent.com).
- The `.mpi` container is itself a **TES4-family BSA archive** read with the `ba2` crate (`ba2::tes4::Archive`).
  Entries may be LZ4-frame compressed (magic `04 22 4D 18`). It holds the patches and new files.
- The manifest is JSON (PascalCase) with the sections `Package` (title/version/author), `Variables`, `Locations`,
  `Tags`, `Assets`, `Checks`, `FileAttrs` and `PostCommands`.
- `Locations` types: 0 = directory, 1 = BSA to read from, 2 = BSA to **create**, with `ArchiveType`, `ArchiveFlags`,
  `FilesFlags` and `ArchiveCompressed`. So the installer repacks output BSAs to an exact specification.
- Each asset is a compact JSON array `[Tags, OpType, Params, Status, SourceLoc, TargetLoc, SourcePath, TargetPath?]`.
  OpTypes: 0 Copy (from a source BSA or folder), 1 New (file shipped in the MPI), 2 Patch (`.xd3` VCDIFF/xdelta3
  patch against a source file), 4 OggEnc2 (resample), 5 AudioEnc (params such as `-f:24000 -q:5`). Tags are a
  bitmask (FO3 = 1, FNV = 2, TTW = 512).
- `Checks` types: 0 FileCheck (exists, optionally with checksums), 1 FreeSpace (`FreeSize` in MB), 2 PathCheck.
  `Checksums` may list **several accepted hashes separated by commas or newlines ("multiple valid hashes for different
  versions")**. The type is detected by length: 32 hex characters is MD5, 40 is SHA-1. `Inverted` and `CustomMessage`
  exist, so a check can say "this file must NOT be present", with a custom error message.
- Paths in the manifest are Windows-style and case-insensitive. The Linux port has to normalise them (lowercase, `/`).
- Performance history (CHANGELOG, verified as text): the port's BSA building peaked at 10–15 GB RAM until a streaming
  builder (v0.1.6, 2026-01-29) brought it down to about 1.8 GB. An SQLite-backed BSA cache cut a 10–38 GB in-memory
  cache to about 100 MB (v0.1.4). It reports about 2 minutes total on a Ryzen 7 9800X3D. The README says its output is
  "around 18GBs" and "will not line up with 17GBs output". So output size is **not** byte-identical to the official
  installer, and the official "17 GB" check doesn't carry over to it.
- **supported hypothesis**: The design is "one manifest of per-file operations, plus a package of xdelta patches and
  new files, plus version gating by a whitelist of source hashes". It is a direct model for our conversion plan.
  TTW's design never stores a full original game file; it stores deltas, new content and instructions.

### 1.3 Failure modes documented by TTW (verified: https://thebestoftimes.moddinglinked.com/faq.html)
| Symptom | Documented cause or fix |
|---|---|
| "BASS Init" or "XD3 Input" error | games not English, DLC missing, games never run once. Verify the game files |
| `xdelta3.dll was not found` | ran the installer from inside the zip. Extract it first |
| "Folder … is not absolute" | quotes in the pasted path, or Windows **Controlled Folder Access** |
| Installer closes or NTDLL error | suspected CPU overheating. Use the `-threads:1` argument |
| Slow install | Intel E-cores. Disable them temporarily |
| "This app can't run on your PC" | Mark-of-the-Web. Unblock the archive in Properties |
| P:0000065432 | PCR release of FNV. Set the Steam App ID to 22490 in MO2 |
| 5:0000065434 | Steam not running |
| Output not 17 GB | failed install. Delete and reinstall |
- **verified**: Update and uninstall: delete TTW in MO2, verify the game files if you replaced the original BSAs, then
  reinstall. "Changing the major or minor version requires a new game"; patch-number updates are save-safe. Verifying
  game files in Steam "will revert the Vorbis version and the executable patch", so those steps have to be redone.
  (same FAQ URL)
- **verified**: Community reports: running the official installer under Wine "didn't work" for one user, but it
  worked in a Windows 10 VM. Another user notes the audio re-encode "takes a long time".
  https://gamingonlinux.com/forum/topic/6083
- **verified**: The Amethyst Mod Manager v2.4.3 release fixed its TTW installer path for Linux by fetching installer
  assets with "SHA-256 digests" validation and a GitHub Actions artifact fallback. Third-party managers now wrap MPI
  installs themselves.
  https://www.warp2search.net/story/amethyst-mod-manager-v243-drops-ttw-installer-fix-and-wabbajack-beta/
- **unresolved**: The exact list of FO3/FNV build hashes TTW accepts, and how the Epic FO3 differs (search results
  show Epic FO3 path and FOSE complaints, but I didn't read a primary source). Exact Discord-only troubleshooting.

---

## 2. Wabbajack internals (current to v4.3.2.1, 2026-10-18)
Source read: `README.md`, `CHANGELOG.md`, `Wabbajack.DTOs/ModList/ModList.cs`, `Wabbajack.DTOs/Game/GameRegistry.cs`,
`Wabbajack.Installer/{StandardInstaller,AInstaller}.cs`, `Wabbajack.Compiler/ACompiler.cs`,
`Wabbajack.Downloaders.GameFile/GameFileDownloader.cs`, `*.csproj` and `Wabbajack.sln`, all from
https://github.com/wabbajack-tools/wabbajack (main), fetched via raw.githubusercontent.com.

### 2.1 Format and pipeline
- **verified** (AInstaller.cs `LoadFromFile`): A `.wabbajack` file is a **ZIP**. Its `modlist` entry is JSON
  (`ModList` DTO: `Archives[]`, `Directives[]`, `GameType`, `OtherGames[]`, `Version`, `WabbajackVersion`, `Name`,
  `Author`, `Readme`, `Website`, `Image`, `IsNSFW`). Patches and inlined files are further ZIP entries, loaded by ID
  (`LoadBytesFromPath`, `InlinedFileStream(PatchID)`).
- **verified** (AInstaller.cs, StandardInstaller.cs): Directive kinds handled at install: `FromArchive` (extract and
  move, hash-checked), `PatchedFromArchive` (apply a binary patch to an archive member, hash-checked),
  `TransformedTexture` (re-compress a DDS to the given width, height, mips and format), `InlineFile` and
  `RemappedInlineFile` (shipped in the list, with paths remapped to the user's machine), `CreateBSA` (build BSA/BA2),
  `MergedPatch` (zEdit merges), plus meta-file writing.
- **verified** (Wabbajack.Installer.csproj): Binary patches use **Octopus.Octodiff** (`PackageReference
  Include="Octopus.Octodiff"`). The compiler builds patches through an `IBinaryPatchCache` (ACompiler.cs
  `BuildPatches` → `_patchCache.CreatePatch(src, FromHash, dst, Hash)`).
- **verified**: Hashing is **xxHash64**, chosen for speed. Security is explicitly not a goal; hashes are stored as
  base64. https://wiki.wabbajack.org/technical_talk/Hashing%20Overview.html. A persistent `FileHashCache`
  (`FileHashCachedAsync`, `FileHashWriteCache`) is used throughout the installer (StandardInstaller.cs).
- **verified** (StandardInstaller.cs `BuildBSAs`): After building each BSA, Wabbajack re-reads it and hash-checks every
  member against its source directive, **except `BA2DX10File` entries and non-deterministic directives**
  (`//DX10Files are lossy`, `if (astate is not BA2DX10File && srcDirective.IsDeterministic)`). The `TransformedTexture`
  path has no hash check at all. So even Wabbajack accepts that texture recompression and BA2 DX10 packing aren't
  byte-reproducible.
- **verified** (StandardInstaller.cs `Begin`): Install order: locate game → `OptimizeModlist` → `HashArchives` → fail
  if any archive is missing ("The installer no longer downloads; preflight should have provided every archive") →
  extract modlist → prime VFS → folder structure → `InstallArchives` → included files → meta files → BSAs → zEdit
  merges → force `portable.txt` → remap `ModOrganizer.ini` download path → set screen size in prefs. Telemetry metrics
  are sent at BeginInstall and FinishInstall.
- **verified** (AInstaller.cs `OptimizeModlist`): **Resume and update** work like this. It enumerates existing files
  in the install directory, works out which aren't part of the list, asks the user to **confirm deletion** ("Save
  files, downloads and [NoDelete] folders will be preserved"), deletes them, prunes empty folders, then
  `PruneUnmodified` drops every directive whose output already exists with the right hash, and `PruneBuiltBsas` skips
  BSAs already built. Only the missing work is done, so re-running is the resume and update mechanism.
- **verified** (CHANGELOG 4.3.0.0): "Fixed interrupted downloads resuming from the wrong position" (PR #3054). Also
  fixed: corrupt archives not being detected, temp file collisions, endless retries on moves that can't succeed, and
  SQLite "database is locked" errors. These are the classic failure classes.

### 2.2 Game files, Stock Game, and game updates
- **verified** (GameFileDownloader.cs): Game files are a "download source" (`GameFileSource{Game, GameFile}`) that is
  never downloaded (`Download` throws `NotImplementedException`). `Verify` checks that the file exists in the located
  game folder and its xxHash64 matches the archive hash. So a list is tied to exact game-file hashes.
- **verified** (CHANGELOG 4.3.0.0, 2026-10-15): "Added **game file repair from Steam**: missing or wrong-version game
  files, Creation Kit files and Creation Club content are fetched into the downloads folder, and a list can be
  installed without the game installed. Needs a Steam login in Wabbajack" (PRs #3005–#3031, #3071). The
  `Wabbajack.Networking.Steam` project references **SteamKit2** (csproj). Version 4.2.3.0 added a "Steam Build ID
  fallback for game version detection".
- **verified** (GameRegistry.cs): Fallout 4 = Steam 377160, Creation Kit tool 1946160 (depots 1946161/1946162),
  GOG 1998527297, `CanSourceFrom = Fallout76`. **Starfield = Steam 1716740 only** (Creation Kit 2722710, one depot
  2722711), with no GOG, Epic or Microsoft Store IDs. Store detection goes through the GameFinder library (Steam,
  GOG, EGS, EA Desktop, Origin handlers; Downloaders.GameFile.csproj).
- **supported hypothesis**: Wabbajack does not "downgrade" the user's game folder. It sources wrong-version game files
  from Steam depots into its downloads folder and builds the list into a separate install (the Stock Game pattern).
  That leaves the user's Steam install alone and avoids the Fallout: London-style "make the ACF read-only" hack.
- **verified** (CHANGELOG 4.3.0.0): New **preflight** checklist before every install: "game, archives, game files,
  Nexus login, manual and automated downloads, disk space". Preflight does all downloading, manual downloads come
  first, and files downloaded in the browser are picked up from the Downloads folder. WebView2 was removed; Nexus
  login now happens in the system browser. The UI moved from WPF to Avalonia. **Linux beta 1** shipped in 4.3.2.0
  (2026-10-17).

### 2.3 Nexus downloads
- **verified** (README): It uses the official Nexus API, the same one MO2 and Vortex use, and downloads count toward
  authors' download totals and donation points. Mod authors cannot opt out of being included.
- **verified** (CHANGELOG): Non-premium users go through manual downloads (older: "support for non-premium Nexus
  downloads via manual downloading through the in-app browser"; "Manual Nexus Downloading now explains why it's so
  painful, and how to fix it (get Premium)"). 4.3.1.0 now opens each file's page directly so "only Slow download is
  left to press", with an "Open the next one automatically" option. So **fully automated Nexus downloads are still
  Premium-only**; free users click once per file.
- **verified** (README): Lists must be free; paywalls, paid betas or "pay for current version" are forbidden.
- **unresolved**: Wabbajack's documented disk/temp-space formula. Preflight now checks disk space, but I didn't read
  the rule (wiki page rate-limited).

---

## 3. STALKER GAMMA installer/launcher
- **verified**: The official install: download Anomaly 1.5.3 (ModDB or torrent) and the "GAMMA RC3" archive (Gofile,
  Mediafire or MEGA mirrors, with published SHA-256s, "last updated 2025-12-06"), extract, run `G.A.M.M.A.
  Launcher.exe` (v8.6), click "First Install Initialization" once, then "Install / Update GAMMA". The same button
  updates later. Requirements: 7-Zip ("WinRAR and Windows's default archive manager are known to cause issues"), at
  least 150 GB free ("ideally 175–200GB"), folders not under Users, Desktop, OneDrive or Program Files, same drive,
  not on USB, plus antivirus exclusions (Norton, Avast, AVG, Malwarebytes and Bitdefender called out by name). Sizes:
  Anomaly 9 GB download / 16 GB extracted; RC3 11 GB / 27 GB; mods via launcher 27 GB / 76 GB; about 130 GB total.
  Uninstall = delete the two folders. Deleting `GAMMA/downloads` means the next repair or update re-downloads
  everything. Launcher self-update is **manual** (download v8.6 from Mediafire and overwrite). "Less than the expected
  number of mods" is the headline failure; the fix is antivirus exclusions and re-running Install/Update.
  https://raw.githubusercontent.com/wiki/Grokitach/Stalker_GAMMA/Installing-GAMMA.md
- **verified**: Support model: the Discord `#how-to-install` channel is "the most up-to-date" source, and the wiki is
  secondary. Linux, macOS and Steam Deck are community guides only. GAMMA is also sold-as-free on **GOG's one-click
  mod install system** ("requires to own one of the base games"). README badges show gamma v0.9.5 and launcher v8.6.
  The project says it is "100% copyright free since it redistributes little to no copyrighted content … downloads
  every add-on directly from moddb or github". https://raw.githubusercontent.com/Grokitach/Stalker_GAMMA/main/README.md
- **verified**: The mod definition file `G.A.M.M.A/modpack_data/modpack_maker_list.txt` (main branch, 492 lines) is
  tab-separated: `download URL \t subfolders (":"-separated, or 0) \t author \t title \t ModDB info-page URL`.
  **It carries no hash column.** By count, 438 entries are www.moddb.com and 35 are github.com.
  https://raw.githubusercontent.com/Grokitach/Stalker_GAMMA/main/G.A.M.M.A/modpack_data/modpack_maker_list.txt
- **verified** (third-party reimplementation Mord3rca/gamma-launcher, `launcher/mods/downloader/moddb.py`,
  `launcher/mods/__init__.py`, `launcher/commands/install.py`): Integrity is checked by **scraping the "MD5 Hash"
  and "Filename" from the ModDB info page at install time**. If the scraped mirror link doesn't match the listed URL
  it skips the mod ("ModDB info do not match download url"). Large files and some mods come from GitHub repos
  (`Grokitach/gamma_large_files_v2`, `teivaz_anomaly_gunslinger`, `gamma_setup`). MO2 is fetched from the MO2 GitHub
  releases. The official launcher is .NET/PowerShell and doesn't run on Linux, which is why the reimplementation
  exists. https://raw.githubusercontent.com/Mord3rca/gamma-launcher/master/README.md
- **supported hypothesis**: GAMMA's resilience to host outages is weak by design. There's no pinned hash in the list,
  ModDB is a single point of failure for about 90% of entries, and mitigation is social (Discord, re-run the button)
  plus moving big or fragile files onto GitHub repos the team controls. Versioning is "whatever is on the repo branch
  now", so two users installing a week apart can get different trees.
- **unresolved**: Any documented GAMMA procedure for a ModDB outage, and whether the official launcher caches
  archives across versions beyond keeping `downloads/`.

---

## 4. Fallout: London (FO4 total conversion, GOG-distributed)
- **verified**: Released 25 July 2024 by Team FOLON, distributed by **GOG** because it was too large to host on Nexus.
  Release was delayed by Bethesda's FO4 next-gen update. https://en.wikipedia.org/wiki/Fallout:_London ;
  https://www.eurogamer.net/fallout-london-mod-will-work-with-fallout-4-on-gog-and-steam-but-not-epic
- **verified**: Requirements: FO4 + all DLC or GOTY on GOG or Steam; HD texture pack not needed; "pre-next-gen";
  Steam must be downgraded to **1.10.163.0**. The official recommended flow is: uninstall FO4, clean `Documents\My
  Games` and `AppData\Local` FO4 folders, reinstall, downgrade (Steam only), run FO4 once, then run the London
  installer from GOG. The manual route uses Steam console `download_depot` commands for the base game, the exe,
  the English pack and every DLC, merges the depot folders, then sets `appmanifest_377160.acf` read-only.
  https://fallout4london.com/?page_id=6
- **verified**: **Epic is unsupported** because the store can't roll back game versions. GOG said the GOG and Steam
  versions work, Steam via manual downgrade or a tool "in progress". It also said the installer had to pass GOG QA
  "on all supported machines". (Eurogamer URL above)
- **verified**: PC Gamer's guide: Steam users run a single-exe downgrader from Nexus, **log into Steam inside it**
  (Steam Guard approvals caused trouble; a manual method exists), set the ACF read-only, then run London's installer
  pointing at the same folder. Reverting means uninstalling both and reinstalling FO4.
  https://pcgamer.com/games/fallout/fallout-london-how-to-install
- **verified**: The widely used "Fallout 4 Downgrader" (Nexus fallout4/mods/81630) is by **zerratar**, uses
  DepotDownloader, and has two modes: patch the exes (keeps next-gen data files) or download full depots (replaces
  data files). It asks for Steam credentials or a QR login for depots ("Now without need of steam login!" for
  patching), targets 1.10.163.0, offers "Delete creation club files", warns that Steam may re-update (make the ACF
  read-only) and that non-English selections may still show English, and needs .NET 8/9. Uploaded 27 Apr 2024,
  updated 13 Aug 2025. https://www.nexusmods.com/fallout4/mods/81630
- **verified**: As of 2 Oct 2025 Team FOLON had "no plan to move it to the next-gen": "The current next-gen
  [iteration] has issues … and would likely be broken by any future update that they may also do on a whim". GOG
  copies have a "built-in downgrader" (version rollback); Steam copies need the downgrader. The Rabbit and Pork DLC
  required a fresh save.
  https://www.rockpapershotgun.com/fallout-london-modders-still-have-no-plans-to-port-it-to-next-gen-fallout-4-unless-a-console-version-becomes-possible
- **verified**: FO4 kept changing after that. The Anniversary Edition shipped 11/10/2025 with an in-game Creations
  menu and 150+ CC items; F4SE got no early access, and Nexus published rollback guidance plus a "Works with
  Anniversary Upgrade" tag (https://www.nexusmods.com/news/15400). Further PC-affecting patches followed: 17 Nov 2025,
  16 Dec 2025, 27 May 2026, **18 Aug 2026 (BA2 archive limit raised 256 → 1024)** and 15 Oct 2026 (CK/PlayStation).
  https://help.bethesda.net/app/answers/detail/a_id/72995/~/fallout-4---patch-notes
- **verified**: GOG Galaxy auto-updates also broke London for some users (Facebook group post, search snippet only;
  low weight).
- **supported hypothesis**: Our project faces the same thing on **two** moving targets. FO4 inputs (which GOTY, NG or
  AE build and which BA2 hashes the user has) and the Starfield output (which runtime our generated ESM/BA2 must
  load in) both keep moving. Starfield's own Bethesda patch cadence is unresolved here.

---

## 5. Skyblivion, Skywind, Beyond Skyrim, Enderal
- **verified**: Skyblivion: "will be installed using a **custom installer that will download and move the necessary
  files required**". No Steam release planned. It needs Skyrim SE and **Oblivion GOTY Deluxe on Steam or GOG**, mixed
  allowed, no AE DLC needed. "Microsoft/GamePass and Epic are highly unlikely to receive support as the files for
  these versions are either encrypted and/or different than the Steam files." No Linux/macOS support, English only,
  not on Creation Club, and "no plans to support any of the newer voice lines or assets from the remaster due to legal
  restraints". Release target 2026. https://skyblivion.com/faq (page dated 2025-10-12)
- **verified** (Wikipedia, secondary): "To release *Skyblivion*, Bethesda required the project to fully replace 100% of
  all assets from the original to not redistribute their own proprietary content." Skyblivion began (2012–14) as an
  automated **asset-porting tool** and produced "broken or empty parts of the map, crashes, and bugs". The team then
  switched to a remake. https://en.wikipedia.org/wiki/Skyblivion
- **verified** (Wikipedia, secondary): Skywind likewise started as a port and in Sept 2012 switched to "remaking or
  replacing everything" while "struggling with buggy files". It needs Skyrim SE + Morrowind and has no release date.
  https://en.wikipedia.org/wiki/Skywind
- **supported hypothesis**: The "voices from the original" pattern is the one notable exception to a full asset
  remake (Skyblivion relies on Oblivion's voice cast). It is plausibly sourced from the user's Oblivion install by the
  custom installer. **unresolved**: I couldn't confirm what Skyblivion's installer copies from the user's Oblivion
  folder.
- **verified** (search snippets only, weak): Enderal SE is free on Steam to Skyrim SE owners and ships its own full
  copy of the needed files ("Enderal has its own folder … all of Skyrim's original files"), so Skyrim needn't be
  installed, just owned. That only works because of the Steam ownership-gated app and Bethesda's blessing.
  https://steamcommunity.com/app/933480/discussions/2/3113645647525881723/ ;
  https://wiki.en.sureai.net/Enderal:Technical_Information
- **unresolved**: Whether Beyond Skyrim (Bruma) has any dedicated installer. Everything I found suggests a normal
  Nexus/mod-manager install, but I didn't verify it.

---

## 6. Cross-engine conversion on the player's PC
- **verified**: **Morroblivion** is the closest precedent to us. "It works by running an installer that automatically
  converts the TES3 data to TES4 format" and generates `Morrowind_ob.esm` **from the user's Morrowind install**. That
  is combined with about 2 GB of separately downloaded resources that replace or remap textures and models, and
  OBSE scripting recreates missing Morrowind mechanics. It needs Morrowind + Tribunal + Bloodmoon, Oblivion + SI,
  OBSE, MenuQue and Ely's Silent Voice. Its two-artifact design (generated master + redistributable resource pack)
  is notable. https://toxicfrog.github.io/morroblivion/ ;
  https://perfectworlds.wordpress.com/2014/11/15/morroblivion-install-notes/ ("just point it to your Morrowind and
  Oblivion game directories, and it will do the rest")
- **verified** (search snippet, Patreon): A later "Morrowind-to-Morroblivion ModExporter" (2018) used OpenMW 0.43 to
  import Morrowind + Tamriel Rebuilt and export ESPs for Morroblivion, so the community built conversion pipelines on
  an open engine reimplementation. https://www.patreon.com/posts/17272420
- **verified**: TTW (section 1) is a same-engine-family merge, not a cross-engine conversion, but it's the strongest
  "rebuild from user files" precedent at scale.
- **FO4 → Starfield**: **unresolved** whether any whole-game FO4 → Starfield conversion has ever been published. In
  2026 searches, "Fallout 4 port" on Nexus means mods ported *to* FO4 (e.g. "A Fallout 4 port of Favorites Menu Grid
  for Starfield", uploaded Sep 2026, https://www.nexusmods.com/fallout4/mods/109006 per search snippet) or one-off
  assets. There's also a 2022 Nexus forum thread asking about moving modded FO4 assets to Starfield. I found **no
  evidence of a public FO4-content-in-Starfield total conversion or installer**. That may be a gap or a sign it gets
  quietly removed. **unresolved**: the Nexus moderation record for such uploads.
- **verified**: Starfield save stability: "the system, as-designed by Bethesda, does not support removing mods — at
  all". Removing an `.esm` from a save gives "no guarantee", and Starfield Engine Fixes gained an experimental
  save-cleaner (as of 2025-01-31). This matters for our update and uninstall story. https://www.nexusmods.com/starfield/articles/702

---

## 7. Cross-cutting lessons (supported hypotheses unless marked)
1. **Gate input on a hash whitelist, not a version string.** TTW accepts multiple checksums per file; Wabbajack
   matches xxHash64 per file. Both fail with a clear "unsupported version" instead of producing garbage.
2. **Ship deltas and instructions, never originals.** TTW `.xd3` (VCDIFF), Wabbajack Octodiff, Morroblivion's
   converter plus a resource pack. All three avoid redistributing the base game.
3. **Lossy steps break byte-for-byte verification.** Wabbajack skips hash checks for DX10 BA2 entries and transformed
   textures (verified). The TTW Linux port's output is about 18 GB where the official one is 17 GB (verified). Our
   pipeline needs a verification model for non-deterministic outputs (perceptual or structural checks, or making the
   encoder deterministic).
4. **Version drift is the number-one killer.** Fallout: London is pinned to 1.10.163 with Epic excluded, plus
   read-only ACF hacks and a third-party downgrader that takes Steam credentials. Wabbajack answered with Steam depot
   sourcing into its own folder (4.3.0.0). FO4 kept patching through 2026.
5. **Re-run is the update and resume.** Wabbajack prunes unmodified outputs by hash and asks before deleting
   strangers. GAMMA's single "Install / Update" button does the same. TTW doesn't (delete and reinstall).
6. **Most support load is environmental:** antivirus, Controlled Folder Access, Mark-of-the-Web, paths under
   OneDrive or Program Files, 7-Zip versus WinRAR, CPU overheating during long encodes, E-cores, and free disk space.
   Preflight checks (Wabbajack 4.3, TTW `Checks`) remove whole classes of them.
7. **Store coverage is a legal and technical axis:** Steam and GOG are always supported; Epic is excluded when it
   can't roll back (London) or its files differ (Skyblivion); Microsoft Store is excluded everywhere (TTW, Skyblivion)
   because the files are encrypted or different.
8. **Host risk:** GAMMA's dependence on ModDB with no pinned hashes versus Wabbajack's CDN, retries and manual
   fallback. Big projects end up mirroring onto infrastructure they control (GAMMA on GitHub; London on GOG).
9. **Asset-port projects tend to become remakes.** Skyblivion and Skywind both started as automated ports, hit
   broken output, and (for Skyblivion, per Wikipedia) had Bethesda require 100% replacement for distribution. Our
   on-PC conversion avoids distribution, but the technical "broken map" failure is the same risk.

---

## Questions this raises for our launcher

Each question gives what to answer, why it matters, and what would answer it.

### A. Input gating (the player's Fallout 4)
1. **Which FO4 builds will we accept: 1.10.163 (pre-NG, verified above), the 2024 next-gen build(s) (exact version numbers unresolved here), the AE builds (Nov 2025 → Oct 2026), GOG, or
   all of them?** *Why:* every precedent pins or whitelists, and FO4 changed five times in a year (including the BA2
   limit 256 → 1024). *Answer:* hash (xxHash64 + SHA-1) `Fallout4.esm`, the DLC ESMs and every vanilla BA2 across the
   Steam depots for each build (DepotDownloader manifests), plus GOG. Diff which records and assets actually differ.
2. **Do we gate on per-file hash whitelists (TTW `Checks` style) or on detected build ID (Wabbajack's Steam Build ID
   fallback)?** *Why:* a version string doesn't catch modded or corrupted vanilla files; hashes do. *Answer:* a
   prototype preflight on two real installs, one clean and one with a Vortex-deployed Data folder, logging what each
   method catches.
3. **Does the AE "Creations" content (150+ CC items now in AE) count as input, get ignored, or get rejected?** *Why:*
   London tells users to delete `cc*` files; Wabbajack 4.3 sources CC content from Steam. *Answer:* inventory the AE
   Data folder and decide per file; check whether CC assets are covered by the same ownership as base FO4.
4. **What do we do with a modded FO4 Data folder (Vortex hardlinks, loose files, ENBs)?** *Why:* London's flow starts
   with "uninstall and clean"; Wabbajack hash-matches only vanilla files. *Answer:* define "vanilla set = files whose
   hash is in our whitelist" and ignore or warn on the rest. Test against a Vortex-deployed install.
5. **Which stores do we support: Steam, GOG, Epic, Microsoft Store/Game Pass?** *Why:* Microsoft Store files are
   encrypted or different (TTW and Skyblivion exclude them), and Epic can't roll back. *Answer:* obtain or inspect each
   store's FO4 file list and hashes (Epic and MS where legally possible), and check whether BA2s are readable.
6. **Do we support non-English FO4 (strings, voice `.fuz`)?** *Why:* TTW and Skyblivion are English-only; zerratar's
   downgrader shows language-pack depots are a separate failure source. *Answer:* list which files differ per language
   depot; decide whether conversion is language-agnostic (strings tables) or English-first.

### B. Output target (the player's Starfield)
7. **Which Starfield builds must our generated ESM/BA2 load in, and how do we detect a Starfield update that breaks
   us?** *Why:* London's "would likely be broken by any future update … on a whim"; we depend on a second moving
   target. *Answer:* the Bethesda Starfield patch-notes history, plus a smoke test (load a generated ESM and BA2 in
   each build) run by Claude's live-game control after every Starfield update.
8. **Is Starfield Steam-only for us, like Wabbajack's registry (Steam 1716740, no GOG/Epic/MS IDs)?** *Why:* the
   Microsoft Store/Game Pass Starfield may have a different file layout or protection, and SFSE support differs.
   *Answer:* check SFSE and Plugins.txt support on Game Pass Starfield; decide whether it's supported or explicitly
   rejected in preflight.
9. **Do we install into the Starfield Data folder, a Stock-Game-style copy, or MO2 VFS only?** *Why:* Wabbajack
   avoids touching the user's install; TTW outputs an MO2 mod folder; London writes into the game. *Answer:* measure
   Starfield's Data size, decide whether a Stock Game copy is acceptable on disk, and test that MO2 USVFS works with
   Starfield plus our BA2 count.

### C. Package format and determinism
10. **Do we adopt a TTW-MPI-like manifest (Locations / Assets with op types / Checks / PostCommands) or
    Wabbajack-like directives?** *Why:* both are proven, and an asset-op table maps directly onto our conversion
    steps. *Answer:* draft our op set (Copy, xdelta Patch, Convert-NIF, Convert-DDS, Convert-Audio,
    Generate-Record, Build-BA2) and check it against a sample of 100 real FO4 assets.
11. **Which steps are deterministic, and how do we verify the ones that aren't?** *Why:* Wabbajack skips hash checks
    for DX10 BA2s and transformed textures; the TTW Linux output is about 1 GB off the official size. *Answer:*
    convert the same FO4 input twice on two machines, diff outputs, and classify each op; for lossy ops, define a
    structural check (header, dimensions, mip count, format) instead.
12. **Do we ever need binary deltas (xdelta/Octodiff) against FO4 files, or is everything a deterministic
    transform plus our own new data?** *Why:* deltas are TTW's core trick, but they bind us to exact input hashes per
    build. *Answer:* list the outputs that can't be derived by transform (hand fixes) and measure delta sizes per FO4
    build.
13. **Patch library: xdelta3/VCDIFF (TTW, has Rust `oxidelta`) or Octodiff (Wabbajack, .NET)?** *Why:* language and
    runtime fit for our toolchain (Python + numpy) and Linux support. *Answer:* benchmark both on a 1 GB BA2-sized
    pair for patch size, apply time and memory.

### D. Resources, speed, resume
14. **What are our peak RAM, temp disk, final disk and wall-clock time on a reference machine and a low-end
    machine?** *Why:* the TTW port went from 10–38 GB RAM to about 1.8 GB only after streaming; GAMMA needs 150–200 GB
    free; TTW's audio encode takes hours on slow CPUs. *Answer:* instrumented end-to-end runs, recorded in
    docs/ai/optimization.md (before and after).
15. **Is our install resumable after a crash, power loss or antivirus kill, and is re-running the update?** *Why:*
    Wabbajack's prune-by-hash re-run is the gold standard; TTW requires delete and reinstall. *Answer:* a
    kill-at-random-step test harness that verifies re-run completes and produces identical hashes for deterministic
    outputs.
16. **Do we cache per-file hashes (Wabbajack FileHashCache) and intermediate conversions between versions?**
    *Why:* rehashing about 40 GB of FO4 BA2s on every run is minutes of disk time. *Answer:* measure a cold versus warm
    preflight.

### E. Distribution, hosting, legal
17. **Where do we host our own (non-Bethesda) data packs, and what happens if that host is down?** *Why:* GAMMA's 90%
    ModDB dependency with no pinned hashes; London needed GOG because Nexus couldn't host its size. *Answer:* the size
    of our redistributable pack, plus a decision on GitHub Releases, our own CDN or Nexus, with mirrors and pinned
    SHA-256 in the manifest.
18. **Does anything we produce or ship count as "assets from another Bethesda game" under Nexus rules, even as
    deltas?** *Why:* Nexus forbids other-Bethesda-game assets; Skyblivion was required to replace 100% of assets to
    distribute. *Answer:* a written query to Nexus moderation about the delta-only, on-PC-generated model (cite the
    TTW and Morroblivion precedents); record the answer in docs/ai/decisions.md.
19. **Can we get GOG-style distribution (like Fallout: London and GAMMA's one-click install) or a Bethesda
    blessing?** *Why:* GOG did QA and distribution for London; Bethesda supported Skyblivion publicly. *Answer:*
    an owner decision on outreach (outreach is outside agent scope per AGENTS.md).
20. **Do we need the player's Steam credentials for anything (depot downloads for version repair)?** *Why:* the
    London downgrader and Wabbajack 4.3 both ask for a Steam login, Steam Guard caused failures, and it's a trust and
    security cost. *Answer:* a design decision; prefer "detect and refuse with instructions" over a credential flow
    unless input-version drift makes it unavoidable.

### F. Support and failure UX
21. **Which environmental checks go into preflight?** Candidates from precedents: free space, path not under OneDrive,
    Program Files or Users, Controlled Folder Access, Mark-of-the-Web on our exe, antivirus interference, 7-Zip
    availability, CPU thermal or threads option, games run once (INI present). *Why:* these are the bulk of TTW and
    GAMMA support load. *Answer:* map each TTW FAQ row and GAMMA troubleshooting item to an automated check or a
    documented message.
22. **What is our uninstall and update story for saves, given Bethesda saves don't tolerate ESM removal?** *Why:*
    TTW says a major/minor version change needs a new game; Starfield saves break on ESM removal. *Answer:* a
    versioning policy (semver where minor = new game required), plus a save-compat test per release.
23. **How do we produce support-grade logs (inputs' hashes, versions, store, OS, each op's result) so a Discord or
    GitHub helper can triage without guessing?** *Why:* TTW and GAMMA support relies on users describing symptoms.
    *Answer:* define a log schema; check that a failed synthetic run gives a one-line root cause.
24. **Is Linux/Proton (Steam Deck) a target?** *Why:* TTW, GAMMA and Wabbajack all grew Linux paths late, via
    community reimplementations (TTW Rust port, Mord3rca, Jackify) or 2026 betas. *Answer:* an owner decision; if yes,
    keep the converter pure-Python/numpy and avoid Windows-only tools from day one.

### G. Research gaps to close next
25. **Has anyone published or attempted a FO4 → Starfield total conversion, and what happened to it?** *Why:* there's
    no evidence either way, and a takedown history would shape our legal posture. *Answer:* searches of Nexus
    Starfield (file name and author search), Reddit r/starfieldmods and Bethesda Creations; ask mod-community
    Discords.
26. **What exactly does Skyblivion's installer pull from the user's Oblivion (voices? strings?) and how does it
    verify it?** *Why:* it's the closest same-publisher "remake plus original-voices-from-your-copy" model. *Answer:*
    read the installer once released, or ask the team.
27. **How does Wabbajack's 4.3 Steam repair choose depots and manifests for a given build, and what does it do when
    Valve removes an old manifest?** *Why:* if we ever source exact FO4 builds, this is the reference
    implementation. *Answer:* read `Wabbajack.Networking.Steam` and the PRs #3005–#3031.
