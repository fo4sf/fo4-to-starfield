# Stores, install layouts and BA2 versions: research for the FO4 → Starfield launcher

Researched 2026-10-19 by Claude (research subagent). Nothing installed, no git writes. Every claim has a label:

- **verified**: I read the source file and line, or the URL, myself in this session.
- **supported hypothesis**: several sources point the same way, but no file or test confirms it.
- **unresolved**: no evidence yet. The open questions at the end name a check for each one.

No sizes or hashes here come from memory. The only numbers quoted are ones printed in the cited sources (GOG installer sizes, Steam depot/manifest IDs).

## Sources read (shallow clones, commit and date)

| Repo | Commit | Date |
|---|---|---|
| Ryan-rsm-McKenzie/bsa (BA2 library used by BAE-style tools) | 2c7280d5 | 2025-02-08 |
| TES5Edit/TES5Edit (xEdit + BSArch, `Core/wbBSArchive.pas`) | 9fb01688 | 2026-09-06 |
| OpenMW/openmw (`components/bsa/ba2*.cpp`) | bfd07f84 | 2026-10-19 |
| loot/libloot (`src/archive/ba2.rs`) | 12df06d2 | 2026-10-19 |
| loot/loot (`src/gui/state/game/detection/*`) | 38dd4acf | 2026-10-11 |
| Ortham/libloadorder (`src/game_settings.rs`) | 186e6437 | 2026-10-13 |
| ModOrganizer2/modorganizer-game_bethesda (MO2 game plugins, now one repo) | a6a23403 | 2026-10-06 |
| wabbajack-tools/wabbajack (`GameRegistry.cs`, BA2 reader) | fc18ab3c | 2026-10-18 |
| Nexus-Mods/vortex-games (`game-fallout4/index.js`) | 18bbee9b | 2026-01-21 |
| Nexus-Mods/game-starfield (Vortex Starfield extension) | ebea0bf2 | 2026-06-10 |
| zerratar/fallout4-downgrader | 9123b12e | 2025-08-13 |

Paths below are relative to each repo. The clones are in
`/tmp/claude-0/-home-claude-fo4-to-starfield/981f8bb8-d11c-56b1-a518-2b9ee32bceac/scratchpad/src_stores/`.

---

## 1. BA2 versions: FO4 v1 / v7 / v8 and Starfield v2 / v3

### 1.1 Header layout, field by field (all little-endian)

| Offset | Size | Field | v1 (FO4) | v7 / v8 (FO4 NG/AE) | v2 (SF) | v3 (SF) |
|---|---|---|---|---|---|---|
| 0x00 | 4 | magic `BTDX` | yes | yes | yes | yes |
| 0x04 | u32 | version | 1 | 7 or 8 | 2 | 3 |
| 0x08 | 4 | type `GNRL` or `DX10` | yes | yes | yes | yes |
| 0x0C | u32 | file count | yes | yes | yes | yes |
| 0x10 | u64 | name-table offset (0 = no names) | yes | yes | yes | yes |
| 0x18 | u64 | extra field, always written as 1 and ignored on load | – | – | yes | yes |
| 0x20 | u32 | compression method: 0 = zlib, 3 = LZ4 | – | – | – | yes |
| | | **header size** | **0x18** | **0x18** | **0x20** | **0x24** |

**verified**, from several independent readers that agree:

- bsa `src/bsa/fo4.cpp:106-119`, `sizeof_header()`: v1, v7 and v8 → 0x18; v2 → 0x20; v3 → 0x24.
- bsa `src/bsa/fo4.cpp:146-187` (read) and `:192-214` (write): the u64 is read and dropped for v2/v3 and written as 1; the u32 compression field exists only for v3, where `3` means LZ4 (`constants::compression_lz4 = 3`, `:41`).
- xEdit `Core/wbBSArchive.pas:39-70` gives the sizes: `SizeOfFO4 = 4*4 + 8`, `SizeOfSFv2 = SizeOfFO4 + 8`, `SizeOfSFv3 = SizeOfSFv2 + 4`. `:1438-1447` covers load: "always set to 1, immediately discarded on load", then `CompressionMethod`. `:540-541` defines `COMPRESSION_METHOD_ZLIB = 0` and `COMPRESSION_METHOD_LZ4 = 3`. `:546-553` lists the versions: `FO4v1=$01`, `SFv2=$02`, `SFv3=$03`, `FO4v7=$07 // FO4 NG/AE`, `FO4v8=$08 // FO4 NG/AE`.
- libloot `src/archive/ba2.rs:8` (`HEADER_SIZE = 24`) and `:41-46`: "The header version is 1, 7 or 8 for Fallout 4 and 2 or 3 for Starfield". It reads only the first 24 bytes, then seeks to the name table, so it never needs the extra fields.
- Wabbajack `Wabbajack.Compression.BSA/BA2Archive/Reader.cs:26-27` has the comment "Fallout 4 - Version 1, 7 or 8 / Starfield - Version 2 or 3". `:81-83` reads two u32 "unknown" fields for v2/v3, then the compression u32 only for v3. That is the same 8 bytes split differently.

### 1.2 Do v7/v8 differ from v1 anywhere besides the version number?

- **verified: no structural difference in any reader I read.** bsa `fo4.cpp:110-113` groups v1, v7 and v8 together, and so does OpenMW: `ba2gnrlfile.cpp:93-98` and `ba2dx10file.cpp:96-101` put `Fallout4`, `Fallout4NextGen_v7` and `Fallout4NextGen_v8` in one `break` branch. The per-file record reading is the same for all three: xEdit `wbBSArchive.pas:1450-1494`, bsa `fo4.cpp:930+`.
- **verified: no new compression for FO4 NG/AE.** In bsa `fo4.cpp:139-141`, constructing a header with LZ4 and any version other than v3 throws "compression format is not valid for the given version". bsa `include/bsa/fo4.hpp:89-92` says LZ4 is "Only compatible with Starfield or later". In xEdit `wbBSArchive.pas:177-186`, the FO4 archive types allow `[ctZLib]` only.
- **verified:** the bsa library's own test data has a next-gen fixture covering v7 and v8 in both GNRL and DX10 (`tests/src/bsa/fo4.test.cpp:625-630`, `data/fo4_next_gen_test.7z`). The test reads those archives through the same code path as v1.
- **verified:** xEdit/BSArch always *write* FO4 archives as v1 (`wbBSArchive.pas:1600-1609`). It has no option to write v7 or v8.
- **unresolved: which game build writes v7 and which writes v8, and what the two numbers mean.** No source I read explains it. OpenMW only renamed `Fallout4NG/NG2` to `..._v7/_v8` (commit a5d93699, "Clarify Fallout 4 next gen update BA2 version naming", read via git.cijber.net mirror). The BAMgr FO4NGE page (nexusmods.com/fallout4/mods/81640) says it "supports the newly added Ba2 format (Versions 7 and 8)". It also says its spec comes from the author's own analysis "and may contain mistakes".
- **unresolved: whether the pre-NG exe (1.10.163) loads v7/v8 archives.** The Fallout 4 Downgrader restores the 1.10.163 content depots and not just the exe: `src/FO4Down/DepotManager.cs:18-26` lists depots 377161 and 377163 ("Fallout Content a/b") with pinned manifests. That fits the old exe being unable to use NG data, but it is not proof. The tool also has a delta-"patch" mode that rewrites only `Fallout4.exe`, the launcher and `steam_api64.dll` (`FO4Downgrader.cs:233-252`).
- **verified (our repo):** our own reader at `src/fo4sf/ba2.py:58-60` uses `extra = {1: 0, 2: 8, 3: 12}.get(version)` and **raises on versions 7 and 8**. If a user's FO4 is NG/AE (Steam today, Epic, Xbox), the launcher will fail on their `Fallout4 - *.ba2` until 7 and 8 are added to the zero-extra group.

### 1.3 Per-file records (the same for all versions)

**verified** from xEdit `wbBSArchive.pas:1452-1494` and bsa `fo4.cpp:33-39`.

Common prefix, 16 bytes:

- u32 name hash
- 4-byte extension
- u32 directory hash
- u8 (xEdit calls it `ModIndex`, "always 0"; `:1456`)
- u8 chunk count
- u16 chunk-header size

GNRL (36 bytes total):

- chunk count must be 1 (`:1464`)
- u64 offset, u32 packed size (0 = stored), u32 unpacked size
- u32 `0xBAADF00D`

DX10 (24-byte header, then 24 bytes per chunk):

- header: u16 height, u16 width, u8 mips, u8 DXGI format, u8 flags (bit 0 = cubemap), u8 tile mode
- each chunk: u64 offset, u32 packed, u32 unpacked, u16 start mip, u16 end mip, u32 `0xBAADF00D`

Name table: entries of u16 length + bytes, written with `/` by Archive2 (`:1499`, `:1891`). Our `ba2.py` decodes in this order.

### 1.4 Starfield v2 vs v3, and the compression field

- **verified:** xEdit `wbBSArchive.pas:1610-1626` says "official Archive2 tool creates v3 archives for lz4 compression only". So v2 means zlib, and v3 carries the compression field, set to 3 for LZ4 or 0 for zlib (`:1906-1911`).
- **verified:** xEdit's default compression is zlib for Starfield GNRL and LZ4 for Starfield DX10 (`:184-186`, `[ctZLib, ctLZ4]` and `[ctLZ4, ctZLib]`).
- **verified:** Starfield LZ4 is *raw LZ4 block*, not LZ4 frame. bsa `fo4.cpp:447-458` calls `LZ4_decompress_safe`, and xEdit uses `ctLZ4` for Starfield where it uses `ctLZ4F` for SSE (`:182`).
- **verified:** bsa `fo4.hpp:79-81` says Starfield zlib "Uses a custom DEFLATE algorithm with zlib wrapper". That only matters when writing. Any zlib inflater reads it.
- **verified: OpenMW is wrong or incomplete here.** It names v2 `StarfieldGeneral` and v3 `StarfieldDDS` (`ba2file.hpp:14-18`). The GNRL reader rejects v3 and the DX10 reader rejects v2 and LZ4 ("Unsupported LZ4-compressed DDS BA2", `ba2dx10file.cpp:102-108`). Don't copy OpenMW's mapping. Our own `docs/FORMAT-GAP.md` ("2 (GNRL / DX10), 3 (LZ4 textures)") matches xEdit.

---

## 2. GOG Fallout 4

- **verified (gogdb.org/product/1998527297, read 2026-10-19):**
  - Product 1998527297 is "Fallout 4: Game of the Year Edition", GOG release date 2023-08-17.
  - There is **one build only**: build ID 56699004712175290, version **1.10.163.0**, dated 2023-08-11, branch Master. No other builds are listed.
  - The offline installers are all 1.10.163.0 in 8 languages, about 34.5–34.7 GB each in 10 parts. They were re-added 2026-06-23 at the same version.
  - DLC 1408237434 is "High Resolution Texture Pack".
- **So GOG is old-gen 1.10.163, and GOG has never shipped NG (1.10.98x) or AE (1.11.x).** Supporting quotes:
  - F4SE says it "will support the latest version of Fallout available on Steam and GOG (currently not the same version)" (f4se.silverlock.org). The same page lists runtime 1.11.240 → F4SE 0.7.9, 1.10.984 → 0.7.2, and 1.10.163 → 0.6.23.
  - A GOG forum post (gog.com/forum/fallout_series/fallout_4_gog_vs_steam_version) says the GOG copy is "the non-Anniversary/Next-Generation version" and that mods must be compatible with 1.10.163.0.
- **GOG does not offer older builds.** **verified:** gogdb lists one build, so there is no rollback within GOG. GOG's only version is itself the old one.
- **Registry keys and IDs, verified:**
  - LOOT `detection/gog.cpp:36-45`: `HKLM\Software\GOG.com\Games\<id>` value `path`, and `HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall\<id>_is1` value `InstallLocation`.
  - Product IDs: 1998527297 (game) and 1408237434 (texture pack) (`gog.cpp:81-85`). Wabbajack `GameRegistry.cs:149` and Vortex `game-fallout4/index.js:14` use the same game ID.
  - LOOT detects a GOG install by the file `goggame-<id>.ico` in the game folder (`detection/generic.cpp:151-165`).
- **Exe and folder layout:**
  - **verified:** the exe is `Fallout4.exe` (LOOT `common.cpp:56-57` uses the same name for all FO4 stores). Data is in `<install>\Data`.
  - **verified:** the AppData/My Games folder is **`Fallout4`**, the same as Steam. LOOT `gog.cpp:114-115` and libloadorder `game_settings.rs:447-456` only switch names for MS and Epic.
  - **supported hypothesis:** the GOG build is Steam-derived and ships `Galaxy64.dll` plus a `steam_api64.dll` shim (GOG forum post above). F4SE 0.6.23 works on it only with `-forcesteamloader` (MO2 issue #1856, member Silarn, 2023-08-21).
- **Do GOG data files match Steam 1.10.163?** **unresolved.** Nobody I found publishes a hash comparison. One forum post says the files were "originally sourced from an edition built for Steam", which fits identical `Data\*.esm/*.ba2`, but that is not proof. Don't treat them as identical without hashing.
- **verified:** MO2's FO4 plugin has **no GOG detection**. `gamefallout4.cpp:61-64` → `GameGamebryo::identifyGamePath` (`gamegamebryo.cpp:211-216`) reads only `HKLM\Software\Bethesda Softworks\Fallout4\Installed Path`. The London plugin even says `// TODO: Add GOG support` (`gamefo4london.cpp:71`).

## 3. Microsoft Store / Game Pass

### Fallout 4
- **verified, install folder:**
  - LOOT `detection/microsoft_store.cpp:124-125` uses `<XboxGamingRoot>\Fallout 4 (PC)\Content`. The root comes from `.GamingRoot` files in each drive root (`:152-157`), and the newer Xbox app writes no registry entries.
  - Bethesda support (help.bethesda.net a_id 65548, after 2025-11-10) lists `C:\XboxGames\Fallout 4 (PC)\Content\Mods` and `...\Content\Creations`. The same article gives Data as `C:\XboxGames\Fallout 4 (PC)\Data` without `Content`, which looks like a typo.
- **verified: DLC lives in separate package folders, not in `Content\Data`.** libloadorder `game_settings.rs:102-112` lists `../../Fallout 4- Far Harbor (PC)/Content/Data`, plus Nuka-World, Automatron, High Resolution Texture Pack, Wasteland Workshop, Contraptions Workshop and Vault-Tec Workshop. The comment says these are safe because "the Microsoft Store version of Fallout 4 won't launch if a DLC is installed and its install path changed". They are used as extra plugin directories (`:549-558`). So for an Xbox install, the "six DLC esms" sit in six or more sibling folders.
- **verified: AppData/My Games folder is `Fallout4 MS`** when `appxmanifest.xml` is in the game folder (libloadorder `:447-449` and `:496-508`). The path is `%LOCALAPPDATA%\Fallout4 MS\Plugins.txt` (`:360-374`, `:603`) and `Documents\My Games\Fallout4 MS` (`:459-486`).
  - The 2021 Nexus article (nexusmods.com/fallout4/news/14503) gave an older path, `%localappdata%\Packages\BethesdaSoftworks.Fallout4-PC_3275kfvn8vcwc\LocalCache\Local\Fallout4 MS\Plugins.txt`, from the `ModifiableWindowsApps` era.
  - **supported hypothesis:** current installs use the libloadorder path. LOOT's comment at `microsoft_store.cpp:168-170` says libloadorder "knows how to detect the appropriate path for modern MS Store game installs".
- **verified:** IDs are package `BethesdaSoftworks.Fallout4-PC` and publisher `3275kfvn8vcwc` (Vortex `index.js:13`; Nexus 2021 article). Vortex launches through the Xbox app with `appExecName: 'Game'` (`index.js:62-93`).
- **Are the files readable or encrypted now?** **supported hypothesis: readable when installed to an XboxGames folder.**
  - The Nov 2021 Xbox Wire post on "Advanced Installation and Management" says Insiders can "easily access local game files" and "mod more games". Games that aren't supported "won't show their files in the install folder".
  - LOOT and libloadorder read `Fallout4.esm` and the DLC Data folders directly, and Vortex hashes `appxmanifest.xml` and `Data/Fallout4.esm` (`index.js:128-131`). Both imply plain files.
  - **unresolved:** whether the default `WindowsApps` location is still locked down. The Vortex Starfield README says WindowsApps is "a system owned virtual file system" and asks users to install to `C:\XboxGames`.
- **Version:**
  - **supported hypothesis:** Xbox gets the current NG/AE build, so its archives would be v7/v8.
  - **unresolved:** the exact build number.
  - **verified:** F4SE "cannot support any potential Windows Store release" (f4se.silverlock.org).
- **verified, exe differences:** the name is `Fallout4.exe` (LOOT `generic.cpp:194-209` checks `appxmanifest.xml` beside it). **unresolved:** whether the binary is a GDK build that differs from Steam's.

### Starfield
- **verified: install folder is `<XboxGamingRoot>\Starfield\Content`** (LOOT `microsoft_store.cpp:126-127`), and the package ID is `BethesdaSoftworks.ProjectGold` (Vortex game-starfield `src/common.ts:20`).
- **verified: Plugins.txt is `%LOCALAPPDATA%\Starfield\Plugins.txt` for both Steam and Game Pass.** There is no `Starfield MS` variant:
  - libloadorder `game_settings.rs:402` (`GameId::Starfield => Some("Starfield")`, no store switch)
  - Vortex `common.ts:7-11` and `util.ts:669-673` (`resolvePluginsFilePath` always returns that path)
  - Nexus guide forums.nexusmods.com/topic/13459379 (Game Pass, 2023-12-16): "%LOCALAPPDATA%\Starfield" (the guide spells out the user folder)
- **verified: My Games is `Documents\My Games\Starfield`** for both stores (libloadorder `:459-486`; MO2 `gamestarfield.cpp:64-68`).
- **verified: Starfield DLC on Game Pass sits in sibling packages.** libloadorder `:559-570` adds `../../Old Mars/Content/Data` and `../../Shattered Space/Content/Data` on MS installs. On all stores it adds `My Games\Starfield\Data`.
- **verified:** libloadorder `:819-830` says Starfield "(at least as of 1.12.32.0) only loads plugins from its additional directory if they're also present in plugins_directory". This matters for where we write.
- **verified:** SFSE "does not support the Windows Store/Game Pass release of Starfield" (sfse.silverlock.org). The current SFSE is 0.2.21 for game 1.16.244.
- **verified:** Game Pass saves can't be read by Vortex: "Save Games functionality is not available for Xbox game pass users" (game-starfield README).

## 4. Epic Fallout 4

- **verified, IDs:** AppName `61d52ce4d09d41e48800c22784d13ae8` (LOOT `epic_games_store.cpp:71-72`; Vortex `index.js:15`).
- **verified, finding the install:** read the `ProgramData\Epic\EpicGamesLauncher\Data\Manifests\*.item` JSON (`AppName` → `InstallLocation`). The Data path comes from the registry `HKLM\Software\Epic Games\EpicGamesLauncher\AppDataPath` (MO2 `gamegamebryo.cpp:421-455`).
- **verified: Epic is identified by `EOSSDK-Win64-Shipping.dll`** in the game folder, and its AppData/My Games folder is **`Fallout4 EPIC`** (libloadorder `:450-453`; LOOT `epic_games_store.cpp:292-293`). The install has a single folder with no language subfolders (`:94-99`). The default path per Bethesda support is `C:\Program Files\Epic Games\Fallout 4` with `Data`, `Mods` and `Creations` underneath.
- **verified: Epic launched with the NG update.** Vortex issue #15580 (2024-04-22): "Bethesda is releasing Fallout 4 on Epic Games store as part of their 'new/next-gen' update", released on the 25th. A user there reported saves being looked for in "Fallout4 vs Fallout4 EPIC".
  - **supported hypothesis:** Epic has only NG/AE builds and no 1.10.163, so its archives would be v7/v8.
  - **unresolved:** Epic's current build number, and whether F4SE works on it.
- **verified:** MO2's FO4 plugin has no Epic detection (see §2). LOOT's generic `isEpicInstall` returns false for fo4 (`generic.cpp:183`) but the dedicated EGS manifest scan covers it.

## 5. How each mod manager finds Starfield, and where it puts Plugins.txt

| Tool | Steam | Game Pass | Plugins.txt |
|---|---|---|---|
| **LOOT** | appid 1716740 via Steam libraries (`steam.cpp:73-74`). Install check: `steam_api64.dll` exists (`generic.cpp:138-139`). No registry key (`generic.cpp:96-98`) | `.GamingRoot` → `Starfield\Content` (`microsoft_store.cpp:126-127`), check `appxmanifest.xml` (`generic.cpp:207-209`) | via libloadorder: `%LOCALAPPDATA%\Starfield\Plugins.txt` |
| **libloadorder** | – (given a path) | MS detected by `appxmanifest.xml` (`:496-508`), which adds the DLC sibling folders | `%LOCALAPPDATA%\Starfield\Plugins.txt` (`:402`, `:603`); CCC is `My Games\Starfield\Starfield.ccc`, then `<game>\Starfield.ccc` (`:625-628`) |
| **MO2** | **Steam only**: `HKCU\Software\Valve\Steam\SteamPath` → `config\libraryfolders.vdf` → `steamapps\common\Starfield` (`gamestarfield.cpp:70-73`, `gamegamebryo.cpp:456-485`) | **not auto-detected** (no code path) | `%LOCALAPPDATA%\Starfield\plugins.txt`, copied into the profile (`gamestarfield.cpp:149-162`). Primary data dir is **`Documents\My Games\Starfield\Data`**, with game `Data` as a secondary (`:75-88`) |
| **Vortex** | `steam: [{ id: 1716740 }]` (`index.ts:118-121`) | `xbox: [{ id: 'BethesdaSoftworks.ProjectGold' }]`, launched via the Xbox app (`index.ts:421-433`); README: `.GamingRoot` resolution, WindowsApps unsupported | `%LOCALAPPDATA%\Starfield\plugins.txt`, any store (`common.ts:7-11`, `util.ts:669-673`) |
| **Wabbajack** | SteamIDs [1716740]; requires `Starfield.exe` (`GameRegistry.cs:650-667`) | no GOG/Xbox IDs listed | (uses MO2) |

For FO4, by comparison (verified):

- **Vortex** queries steam (by name), xbox `BethesdaSoftworks.Fallout4-PC`, gog `1998527297`, epic `61d52ce4…`, and the registry key `HKLM\Software\Wow6432Node\Bethesda Softworks\Fallout4:Installed Path` (`index.js:96-106`).
- **Wabbajack** has Steam 377160 and GOG 1998527297, plus CK tool 1946160 (`GameRegistry.cs:139-158`).
- **MO2** reads only the Bethesda registry key and hardcodes `%LOCALAPPDATA%\Fallout4` (`gamefallout4.cpp:122-135`). It ignores `Fallout4 MS` and `Fallout4 EPIC`.

---

## Questions this raises for our launcher

**BA2 reading**
1. Should `src/fo4sf/ba2.py` accept versions 7 and 8 with zero extra header bytes, like every reader above? It needs a synthetic v7/v8 GNRL and DX10 fixture unittest. Today it raises on NG/AE archives.
2. Which official FO4 NG/AE archives are v7 and which are v8? Check: run `scripts/recon.py` (it already prints `v{version}/{type}/c{codec}` per archive) on an NG install and on a 1.10.163 install, and record the output in research-log.md.
3. Are the 1.10.163 and NG/AE `Fallout4.esm` and the DLC esms byte-identical, or only the BA2s? If records differ, our conversions become build-dependent. Check: hash both sets.
4. Do v7/v8 archives contain different *contents* (new or changed files, renamed NG textures) from the v1 archives with the same names, not just a new version field? This decides whether outputs match across FO4 builds.
5. Should we read the v3 compression field and branch on it (0 = zlib, 3 = raw LZ4 block), rather than assume "v3 = LZ4 textures"? Archive2 may also write v3 with zlib (xEdit writes 0 there).

**Store detection and paths**
6. Which FO4 store builds do we support as *input*: Steam 1.10.163 (the documented baseline), Steam NG/AE, GOG 1.10.163, Epic (NG/AE only), Xbox (NG/AE, with DLC in sibling packages)? What do we tell an NG/AE user?
7. Do GOG 1.10.163 data files match Steam 1.10.163 byte for byte? If yes, GOG is a fully supported input with the same expected-hash table. Check: compare GOG and Steam file hashes on the owner's machine (owner action, no assets in Git).
8. For an Xbox FO4 install, should the launcher find DLC esms/BA2s in the sibling `Fallout 4- <DLC> (PC)\Content\Data` folders, as libloadorder does? Or should it require the user to point at each one?
9. Detection order and evidence for FO4. Proposed:
   - Steam libraries (377160)
   - `HKLM\...\Bethesda Softworks\Fallout4\Installed Path`
   - GOG registry (1998527297) + `goggame-1998527297.ico`
   - Epic manifests (AppName 61d52ce4…) + `EOSSDK-Win64-Shipping.dll`
   - `.GamingRoot` → `Fallout 4 (PC)\Content` + `appxmanifest.xml`

   Do we report the store *and* the exe version (file version resource) before converting?
10. Starfield output target is Steam 1.16.244 only (SFSE requirement, docs/SETUP.md). Do we refuse a Game Pass Starfield outright, or allow an "outputs only, no SFSE features" mode? Game Pass Plugins.txt is still `%LOCALAPPDATA%\Starfield\Plugins.txt`.
11. Where should we write: `<game>\Data` or `Documents\My Games\Starfield\Data`?
    - libloadorder says Starfield ≥1.12.32 loads plugins from the My Games Data folder only if they also exist in game `Data`.
    - MO2 treats My Games Data as primary.
    - Vortex offers a junction between the two (and warns about OneDrive).

    How do we detect an existing junction, and what is the rule for loose files versus plugins?
12. Do we have to handle OneDrive-redirected Documents? MO2 uses `FOLDERID_Documents` with fallbacks (`gamegamebryo.cpp:383-419`). libloadorder uses `dirs::document_dir()`.
13. How do we manage Starfield `Plugins.txt` together with `Starfield.ccc` (the My Games copy overrides the game copy, even when empty) and the `sTestFile` INI entries, which turn off Plugins.txt for FO4 and Starfield? Should the launcher warn when sTestFile entries exist?

**Version pinning and downgrade**
14. If a user only has Steam NG/AE FO4, do we point them to the Fallout 4 Downgrader (Steam login, depot manifests pinned in `DepotManager.cs`) or to Steam console depot downloads? Or do we support NG/AE data directly once question 1 is done?
15. Does the Downgrader's "patch-only" mode leave NG v7/v8 data in place with a 1.10.163 exe? If users arrive with that mixed state, what does our launcher see and accept?

**Process and evidence**
16. Which of these store checks can run offline in CI with synthetic fixtures? Candidates: fake `.GamingRoot`, fake Epic `.item` JSON, fake `goggame-*.ico`, fake `appxmanifest.xml`, fake `libraryfolders.vdf`. Which need the owner's machine?
17. Should we reuse libloadorder's logic (Rust; it has Python bindings via LOOT's ecosystem? unresolved) instead of re-implementing the Plugins.txt and additional-directory rules? Record that decision in docs/ai/decisions.md.
