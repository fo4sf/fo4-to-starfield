# Fallout 4 source data: versions, stores, downgrading, languages, install detection, Creation Club

Research for the launcher that reads the player's own Fallout 4 + six DLC, identifies the version by file hash and
refuses unknown ones. Written 2026-10-19 by Claude (research subagent). Read-only research; nothing installed.

Labels (docs/ai/research-log.md): **verified** = I read it at the cited URL or in our own repo files;
**supported hypothesis** = consistent with sources but not directly shown; **unresolved** = no evidence found.
"Verified" here means "a source says so and I read the source", not "we checked it on bytes". Community pages can be wrong.

**Pages I could not read:** WebFetch hit a proxy rate limit (HTTP 429) partway through, so I could not read
Nexus article 5844 (BA2 NG format), Nexus news 14503 (Game Pass modding), gogdb.org (GOG build list),
pcgamingwiki.com/wiki/Fallout_4 (store paths, languages), technosports.co.in (AE downgrade guide), or a Steam thread on
localized voice archives. gogdb.org and the GOG content API were also blocked for curl. The gaps this leaves are listed under
"Unresolved". GitHub raw / GitLab raw source code was still readable and is used heavily below.

---

## 0. What we already know from our own repo (verified, repo files)

- Owner's `Fallout4.esm`: 330,745,373 bytes, sha256 `ae7be31a59052f926474a767d9dbfbcc7f19af4ad2070491f7f40d821b2520eb`;
  `DLCRobot.esm` 8,012,051 B `e71e04ac...`; `DLCworkshop01.esm` 633,592 B `82914c20...`
  (`scripts/launcher_recipes/known_sources.json`, `docs/ai/launcher-backbone.md` lines 110-112).
- **The owner's data is not a normal Steam install.** It is a Steam console / DepotDownloader output tree:
  `C:/Program Files (x86)/Steam/steamapps/content/app_377160/depot_377163/Data/Fallout4.esm` (docs/terrain/flora.md:53),
  and `Fallout4 - Voices.ba2` comes from `<depot_377164>\Data\` (scripts/actors/codsworth_voice.py:5). So the files are
  split across one folder per depot. The launcher has to handle this "depot-split" layout as well as a merged install.
- `docs/measurements/fo4_ba2.json`: all 50 measured FO4 archives are **BA2 version 1** (27 GNRL, 23 DX10). That's consistent with
  pre-next-gen data (see section 1). `Fallout4 - Interface.ba2` holds 11 each of `.STRINGS`, `.DLSTRINGS` and `.ILSTRINGS`
  (`Strings\Fallout4_cn/de/en/es/...`), so **text for every language ships in the language-neutral Interface archive**.
  `Fallout4 - Meshes.ba2` appears **twice** with different file counts (42,409 and 42,416). Two depot folders probably
  each hold a copy (supported hypothesis), and the launcher must pick one deterministically.
- Measured CC archives on the owner's PC: ccBGSFO4001/003/004/006 (Pip-Boy skins), 016 Prey, 018 Gauss Rifle Prototype,
  019 Chinese Stealth Armor, 020 PA skin Black, 038 Horse Armor, 044 Hellfire PA, ccFRSFO4001 Handmade Shotgun,
  ccFSVFO4001 Military Backpack, ccFSVFO4002 Mid-Century Modern. All are BA2 v1. The DLC archives measured are only DLCRobot.
- `docs/ai/launcher-backbone.md`: detect reported **NOT READY: Far Harbor, Contraptions, Vault-Tec and Nuka-World missing**
  on the PC. The owner's three depots (377163, 435871, 435880) cover the base game, Automatron English and Wasteland Workshop only.

---

## 1. PC versions that matter

### Runtime (Fallout4.exe) version list. **Verified** from F4SE source
`f4se_common/f4se_version.h` (https://raw.githubusercontent.com/ianpatt/f4se/master/f4se_common/f4se_version.h):

| Runtime | F4SE comment | Notes |
|---|---|---|
| 1.10.162 | creation club update 16 | |
| **1.10.163** | creation club update 17 | Last old-gen build. F4SE 0.6.23 |
| **1.10.980** | 'next generation' update | |
| **1.10.984** | hotfix | F4SE 0.7.2 |
| **1.11.137** | 'anniversary edition' update | |
| 1.11.159 / 1.11.169 / 1.11.191 | hotfix | |
| 1.11.221 | (no comment) | |
| **1.11.240** | creation club | `CURRENT_RELEASE_RUNTIME`, F4SE 0.7.9 |

- F4SE's home page lists 0.7.9 → 1.11.240, 0.7.2 → 1.10.984, 0.6.23 → 1.10.163, and says "F4SE will support the latest version
  of Fallout available on Steam and GOG (currently not the same version)" — **verified** (https://f4se.silverlock.org/).
- F4SE packs the store into the low nibble of the version: `RUNTIME_TYPE_BETHESDA 0, GOG 1, EPIC 2, MSSTORE 3`; save
  folders "Fallout4", "Fallout4 GOG", "Fallout4 EPIC", "Fallout4 MS"; comment "gog 1.10.984 doesn't exist at the time of
  this writing" — **verified** (same file).
- Dates: next-gen update 1.10.980 = 25 April 2024 — **supported hypothesis** (r/fo4 "update megathread" dated Apr 25 '24 and
  press coverage in search results; I did not read a dated official note). 1.10.984 = 2024-05-13; AE Nov 2025;
  patches 2025-12-16, 2026-02-10 (PS4), 2026-05-27; **2026-08-18 update = 1.11.240, BA2 archive limit raised 256 → 1024**,
  Microsoft Store crash fix; nothing newer as of 2026-10-09 — **verified** as that page's claims
  (https://gaming-st.com/pc-games/fallout4-latest-update-history-2026-10/, Japanese, secondary source).
- Anniversary Edition: released **10 November 2025**; "all six official DLCs" and "over 150 pieces of Creation Club content";
  an in-game Creations menu; existing owners buy a **paid upgrade** — **verified** (https://www.nexusmods.com/rust/news/15400,
  Nexus news dated 6 Nov 2025). The 1.11.137 / rollback target 1.10.984 numbers there come from a user comment, which the F4SE header confirms.
- SteamDB public branch: build **24564252**, built 5 Aug 2026, updated 18 Aug 2026; 60 depots — **verified**
  (https://steamdb.info/app/377160/depots/). That matches the 2026-08-18 1.11.240 update (supported hypothesis).

### Fallout4.esm sizes. **Verified** as listed by one community tool
"Delta patcher to change the version of Fallout4.esm to/from VR/1.10.163/NG/AE" (https://www.nexusmods.com/fallout4/mods/95677):

| Build | Fallout4.esm size |
|---|---|
| VR | 330,553,163 |
| **1.10.163** | **330,745,373** |
| NG | 330,777,465 |
| AE | not listed (the tool supports AE, so AE's esm differs again: supported hypothesis) |

- **The owner's 330,745,373 equals the 1.10.163 size.** This is a strong **supported hypothesis** that the owner's file is
  1.10.163 (size match only; the page gives **no hashes**). To verify it on bytes, compare against the depot manifest (section 3) or a
  second independent install.
- The page gives no CRC, MD5 or SHA, and I found **no community source that publishes Fallout4.esm or DLC esm hashes**
  (**unresolved**). Wabbajack modlists store per-game-file xxHash64 keyed by GameVersion (`GameFileSource`,
  https://raw.githubusercontent.com/wabbajack-tools/wabbajack/main/Wabbajack.DTOs/DownloadStates/GameFileSource.cs, **verified**),
  so public Wabbajack modlist JSONs are a possible hash source, but they use xxHash64, not sha256.
- What changed inside Fallout4.esm between 163 → NG → AE (records edited, FormIDs added, header version): **unresolved**.
  The NG esm is 32,092 bytes larger. Nexus says plugin-based mods are "likely unaffected" by AE, which suggests no FormID
  renumbering (supported hypothesis only).
- Whether the six DLC esms changed in NG/AE: **unresolved**. The downgrader re-downloads all DLC depots at the old manifests
  (section 3), which suggests they changed or that the author wasn't sure.

### BA2 archive versions
- BA2 header `version` field: 1 = FO4 original, 2/3 = Starfield, **7 and 8 = "FO4 NG/AE"**. xEdit maps 1, 7 and 8 to the
  same FO4 reader, and only 2/3 read the extra 8-byte (and v3 compression) fields — **verified** in xEdit source
  (https://raw.githubusercontent.com/TES5Edit/TES5Edit/dev-4.1.6/Core/wbBSArchive.pas lines 546-553, 1337-1346, 1439-1447).
  OpenMW has the same: `Fallout4 = 1, StarfieldGeneral = 2, StarfieldDDS = 3, Fallout4NextGen_v7 = 7, Fallout4NextGen_v8 = 8`,
  with v1/v7/v8 handled identically in GNRL and DX10 — **verified**
  (https://gitlab.com/OpenMW/openmw/-/raw/master/components/bsa/ba2file.hpp, ba2gnrlfile.cpp, ba2dx10file.cpp).
- So **the 24-byte header layout is the same for v1, v7 and v8** (verified in two independent readers). Pre-NG 1.10.163 cannot load v7/v8
  without the "Backported Archive2 Support System" mod — **verified** as that claim
  (https://nexusmods.com/fallout4/mods/82095; https://www.nexusmods.com/fallout4/mods/81630). Bethesda Archive Manager
  FO4NGE "supports the newly added Ba2 format (Versions 7 and 8)" — **verified** (https://www.nexusmods.com/fallout4/mods/81640).
- The semantic difference between v7 and v8 (which archives get which; whether payload or compression differs): **unresolved**.
  Our reader (`docs/FORMAT-GAP.md`: BA2 version 1, zlib) would need at minimum to accept 7 and 8 if we ever read NG data.
- AE CC skins "consume BA2 archive slots" (user comment), and the 2026-08 patch raised the limit to 1024 — supported hypothesis /
  verified-as-claimed respectively. This matters for us only if we read AE data.

### Creation Club content bundled with NG (2024). **Verified**
- Shacknews patch notes list free CC on all platforms: Enclave Remnants, Enclave Weapon Skins, Enclave Armor Skins, Tesla Cannon,
  Hellfire Power Armor, X-02 Power Armor, Heavy Incinerator, Halloween Workshop, Makeshift Weapon Pack; also "Release on Epic Store"
  and "not yet on GOG" (https://shacknews.com/article/139651/fallout-4-next-gen-update-patch-notes).
- The downgrader's `DeleteNextGenFiles` names the plugins/archives: `ccBGSFO4044-HellfirePowerArmor`, `ccBGSFO4046-TesCan`,
  `ccBGSFO4096-AS_Enclave`, `ccBGSFO4110-WS_Enclave`, `ccBGSFO4115-X02`, `ccBGSFO4116-HeavyFlamer`, `ccFSVFO4007-Halloween`,
  `ccOTMFO4001-Remnants`, `ccSBJFO4003-Grenade` (each `.esl` + `- Main.ba2` + `- Textures.ba2`), and separately the older
  2017 free CC set (Pip-Boy skins, Prey, Gauss, Chinese Stealth, PA Black, Horse Armor, Handmade Shotgun, Backpack,
  Mid-Century Modern, Hellfire) — **verified**
  (https://raw.githubusercontent.com/zerratar/fallout4-downgrader/HEAD/src/FO4Down/FO4Downgrader.cs lines ~840-940).
  Hellfire (4044) is in **both** lists, so it existed pre-NG and was re-shipped (supported hypothesis). The owner's measured ccBGSFO4044
  archives are BA2 v1, which fits pre-NG.
- NG also adds `Fallout4.ccc` and `Fallout4IDs.ccc` in the game root — **verified** as claimed
  (https://nexusmods.com/fallout4/mods/82095; the NG depot 377163 manifest named there is 8363807899725426636).

---

## 2. Stores

| Store | IDs / markers | Version situation | Sources |
|---|---|---|---|
| Steam | app **377160**; CK app 1946160 (depots 1946161/1946162) | Public = 1.11.240 since 2026-08-18 (supported hypothesis); old builds only via depot manifests | LOOT `steam.cpp`, Wabbajack GameRegistry.cs, SteamDB (all **verified**) |
| GOG | game **1998527297**, HD texture pack **1408237434**; root file `goggame-1998527297.ico` | F4SE: latest GOG ≠ latest Steam (**verified**); Fallout: London gives GOG users no downgrade step (**verified**, https://fallout4london.com/?page_id=6); exact GOG build numbers **unresolved** (gogdb blocked) | LOOT `gog.cpp`, `generic.cpp`; Wabbajack GOGIDs (**verified**) |
| Microsoft Store / Game Pass | folder `<XboxGamingRoot>\Fallout 4 (PC)\Content`; root found from a `.GamingRoot` file at each drive root; no registry entries for new Xbox-app installs | F4SE refuses: "The Windows Store (gamepass) version of Fallout 4 is not supported" (**verified**); version parity and whether files are readable/unlocked **unresolved** | LOOT `microsoft_store.cpp`, `loot_state.cpp`; F4SE `IdentifyEXE.cpp` |
| Epic | catalog id `61d52ce4d09d41e48800c22784d13ae8`, app name "Fallout4 EPIC"; manifests in `%ProgramData%\Epic\EpicGamesLauncher\Data\Manifests\*.item` (JSON `AppName`, `InstallLocation`) | Exists since the NG update (Shacknews, **verified**); F4SE: "The Epic Store version of Fallout 4 is not supported"; MO2/Wabbajack have no FO4 Epic id | LOOT `epic_games_store.cpp`, MO2 `gamegamebryo.cpp` |

- **Store from the exe itself** (useful and cheap). F4SE heuristics: Steam exe has a `.bind` PE section; GOG imports
  `Galaxy64.dll`; MS Store imports `api-ms-win-core-psm-appnotify-l1-1-0.dll`; Epic imports `eossdk-win64-shipping.dll` —
  **verified** (https://raw.githubusercontent.com/ianpatt/f4se/master/f4se_loader_common/IdentifyEXE.cpp lines 153-180).
  F4SE's own comments say the GOG/Epic/Store checks are guesses ("haven't seen it"), so treat them as a supported hypothesis.
  The downgrader exe-patching targets, by CRC64 and file version: `Fallout4.exe` 1.10.163.0, `steam_api64.dll` 2.89.45.4,
  `Fallout4Launcher.exe` 1.3.22.0 — **verified** (FO4Downgrader.cs ~528-575).
- LOOT marks a Steam install by `installscript.vdf` in the game folder, and a GOG install by `goggame-<id>.ico` —
  **verified** (https://raw.githubusercontent.com/loot/loot/master/src/gui/state/game/detection/generic.cpp).
- GOG installer layout differences (single merged folder? language selection at install?): **unresolved**. LOOT treats
  FO4 on Epic and MS Store as one folder of "any language" — **verified** (`getGameLocalisationDirectories` returns `{basePath,"en"}`).

---

## 3. Downgrading

- **Fallout 4 Downgrader** (zerratar, Nexus 81630, GPL-3.0, .NET 8, uses DepotDownloader with the user's Steam login or QR) —
  **verified** (https://www.nexusmods.com/fallout4/mods/81630; https://github.com/zerratar/fallout4-downgrader). Two modes:
  1. *Patch mode*: binary patches for exe/launcher/steam_api64 only. It "leaves the next-gen data files intact", so you need
     BASS for v7/v8 archives. The patches are **AES-encrypted with the SHA-256 of the original file as key**, chosen by the source file's
     CRC64 (`CanPatch`/`Decrypt` in FO4Downgrader.cs, **verified**). So the patch is useless without the genuine original file.
     That's a good legal pattern for any launcher patch we ship.
  2. *Depot mode*: downloads full old depots, deletes the NG CC files, copies depot folders over the install, fixes language,
     makes `appmanifest_377160.acf` read-only so Steam doesn't update.
- **The full 1.10.163 manifest table** (depot → manifest), from `src/FO4Down/DepotManager.cs`
  (https://raw.githubusercontent.com/zerratar/fallout4-downgrader/HEAD/src/FO4Down/DepotManager.cs, **verified** as that file's
  content; depot names cross-checked against SteamDB **verified**):
  - Base: 377161 `7497069378349273908` (content_a), 377162 `5847529232406005096` (exe), **377163 `5819088023757897745`** (content_b).
  - Language: 377164 en `2178106366609958945`, 377165 fr `7549549550652702123`, 377166 de `6854162778963425477`,
    377167 it `783101348965844295`, 377168 es `7717372852115364102`, 393880 pl `8378357397609964253`, 393881 ru `9220466047319762009`,
    393882 pt-BR `7540680803954664080`, 393883 zh-Hant `6742459130628608886`, 393884 ja `3455288010746962666`.
  - Wasteland Workshop **435880 `1255562923187931216`**; Automatron base 435870 `1691678129192680960`, **Automatron English 435871 `5106118861901111234`** (other languages 435872-435879, 404091).
  - Contraptions 480630 `5527412439359349504`; Far Harbor base 435881 `1207717296920736193`, English 435882 `8482181819175811242`;
    Vault-Tec base 480631 `6588493486198824788`, English 393885 `5000262035721758737`; Nuka-World base 490650 `4873048792354485093`,
    English 393895 `7677765994120765493`; HD textures 540810 `1558929737289295473`; CK 1946161 `6928748513006443409`, 1946162 `3951536123944501689`.
  - Oddity: Nuka-World French (393896) and Russian (393899) share manifest `4271967849859961419`. That's probably a copy-paste bug in that
    table (supported hypothesis). Don't trust that row without checking.
- Fallout: London's official page says Steam owners must roll back to 1.10.163.0 via `download_depot 377160 <depot> <manifest>`
  per part, executable, language pack and owned DLC; merge the depot folders into one; set `appmanifest_377160.acf` read-only;
  GOG owners install as-is — **verified** (https://fallout4london.com/?page_id=6).
- Our owner's depot set (377163, 435871, 435880) matches exactly the depots the downgrader's manual instructions list on the Nexus page
  (base + Workshop + Automatron), but **not** Far Harbor / Contraptions / Vault-Tec / Nuka-World (the downgrader's
  `AllDlc` group). This probably explains the four missing DLC (supported hypothesis).
- Legality/acceptability: `download_depot` is Valve's own client feature and only serves depots the account owns
  (supported hypothesis; no Valve doc read). Nexus hosts downgraders and the biggest total-conversion mod (London) officially instructs
  depot rollback (**verified**). I found no Bethesda statement either way (**unresolved**). Shipping Bethesda files or
  plain patches would be redistribution. The hash-keyed encrypted-patch pattern avoids that (our inference).

---

## 4. Languages

- Steam has a separate depot per language for base and for Automatron / Far Harbor / Vault-Tec / Nuka-World. Wasteland Workshop
  and Contraptions have none — **verified** (SteamDB depot list + DepotManager.cs). Language depot sizes (en 3.55 GiB, ja
  6.30 GiB, ...) mean voices plus probably localized video. The exact contents are **unresolved** (manifests list them).
- Text strings for all languages sit in `Fallout4 - Interface.ba2` as `Strings\Fallout4_<lang>.STRINGS/.DLSTRINGS/.ILSTRINGS`
  (**verified**, our own measurement). The base voice archive is `Fallout4 - Voices.ba2` (English, from depot_377164) and DLC voices are
  `DLCRobot - Voices_en.ba2` (**verified**, measurement).
- The game selects language via `[General] sLanguage` in Fallout4.ini / Fallout4_Default.ini. The downgrader reads `sLanguage`
  (two-letter code, e.g. `en`, `de`), and when switching it rewrites every `[Archive]` value from `_en.` to `_<lang>.` and
  deletes duplicate `_en` archives — **verified** (FO4Downgrader.cs `ApplyLanguageAsync`, AppContext.cs `GetTargetCultureInfo`).
  So localized archives follow a `<name>_<lang>.ba2` pattern listed in the ini `[Archive]` keys (supported hypothesis for the base
  `Fallout4 - Voices*.ba2` naming in non-English installs; I could not read the Steam thread).
- xEdit discovers languages by scanning `*_<lang>.*STRINGS` in containers or `Data\Strings\` — **verified** (wbLocalization.pas).
- Is `Fallout4.esm` itself identical across languages (localized plugin, strings external)? **Supported hypothesis**: it lives in
  language-neutral depot 377163, and the 11 language string tables sit beside it. So the esm hash should be language-independent on Steam.
  For DLC esms, which depot (base vs language) holds `DLCRobot.esm` etc. is **unresolved**. If it's the language depot, DLC esm hashes
  could differ per language.

---

## 5. Finding installs (how MO2, LOOT and Wabbajack do it)

- Registry: `HKLM\Software\Bethesda Softworks\Fallout4`, value `Installed Path`. LOOT reads the **32-bit view first**
  (`RRF_SUBKEY_WOW6432KEY` = `HKLM\SOFTWARE\WOW6432Node\...`), then the 64-bit view — **verified**
  (LOOT generic.cpp lines 88-91, registry.cpp lines 70-105). MO2 uses the same key/value — **verified**
  (https://raw.githubusercontent.com/ModOrganizer2/modorganizer-game_bethesda/master/src/gamebryo/gamegamebryo.cpp `identifyGamePath`).
- Steam: `HKCU\Software\Valve\Steam` `SteamPath` → `<SteamPath>\config\libraryfolders.vdf`. Each library has `path` and an
  `apps` map; if `377160` is in `apps`, the game is at `<path>\steamapps\common\Fallout 4` — **verified** (MO2 `parseSteamLocation`).
  The downgrader also tries the current directory, "known paths", then Steam libraries — **verified** (FO4Downgrader.cs ~1040-1120).
- GOG: `HKLM\Software\GOG.com\Games\1998527297` value `path`, or
  `HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall\1998527297_is1` `InstallLocation` — **verified** (LOOT gog.cpp 30-48).
- MS Store/Game Pass: read `<drive>:\.GamingRoot` on every drive → `<root>\Fallout 4 (PC)\Content` — **verified** (LOOT).
- Epic: `HKLM\Software\Epic Games\EpicGamesLauncher` `AppDataPath` (fallback `%ProgramData%\Epic\EpicGamesLauncher\Data\`) +
  `Manifests\*.item` — **verified** (MO2/LOOT).
- My Games/ini folder: Documents\My Games\Fallout4 (MO2 `determineMyGamesPath`, **verified**); per-store save folders differ
  ("Fallout4 GOG", "Fallout4 EPIC", "Fallout4 MS"). F4SE and LOOT name them this way, so they apply to ini/plugins.txt location too
  (supported hypothesis for ini; **verified** for the names in LOOT's Epic/GOG app-data folder functions).
- MO2 primary plugins (always loaded, in order): `fallout4.esm, dlcrobot.esm, dlcworkshop01.esm, dlccoast.esm,
  dlcworkshop02.esm, dlcworkshop03.esm, dlcnukaworld.esm, dlcultrahighresolution.esm`, then every line of
  `<game root>\Fallout4.ccc` as CC plugins — **verified** (MO2 gamefallout4.cpp `primaryPlugins`, `CCPlugins`).
- **None of these tools handle the depot-split layout** (`steamapps\content\app_377160\depot_*`) that the owner actually has.
  That's our own requirement.

---

## 6. Anniversary / Creation Club and our converter

- CC content is **separate plugins** (`cc*.esl` + BA2s), auto-loaded through `Fallout4.ccc`, not merged into `Fallout4.esm` —
  **verified** for the mechanism (MO2 `CCPlugins`; downgrader file lists). So CC does **not** become a master of the base or DLC esms.
  A converter that reads only the 7 esms is unaffected by CC presence. One exception: if a user's own mods or saves reference cc FormIDs.
- Whether AE's 1.11 `Fallout4.esm` moved, added or removed FormIDs vs 1.10.163: **unresolved**. The size differs (NG +32,092 B;
  AE size unknown). Any FormID-keyed output (our formids.json, `docs/ai/launcher-backbone.md` same-ids checks) must treat each
  esm hash as its own source and never assume ID stability across versions.
- AE CC ESLs live in FE-space light slots, so they don't shift full-master load-order indices of the 7 masters (supported
  hypothesis from how ESL/`.ccc` works). But load order index of DLC masters after Fallout4.esm is fixed by the primary
  plugin list above (verified).
- AE CC for players who didn't buy the upgrade: the Creations menu and files exist, but whether the 150+ items are on disk without
  the upgrade is **unresolved**.

---

## Questions this raises for our launcher

1. **Is the owner's Fallout4.esm really 1.10.163, on bytes?** It matters because the whole known-version table is keyed on that label.
   Answered by: running `download_depot 377160 377163 5819088023757897745` (or reading that manifest's file list and
   SHA-1 per file with DepotDownloader `-manifest-only`) and comparing to our sha256's file. Steam manifests carry a SHA-1 per file,
   so a match against manifest 5819088023757897745 makes it verified.
2. **Which depot ships each of the 7 esms and each DLC BA2 (base vs language depot)?** If DLC esms sit in language depots, their hashes
   may differ per language and our table needs one row per (file, language). Answered by: `-manifest-only` listings for 435870/435871,
   435881/435882, 480631/393885, 490650/393895, 480630, 435880.
3. **Why does `Fallout4 - Meshes.ba2` appear twice (42,409 vs 42,416 files) in our measurement?** It matters because the launcher must
   choose one copy deterministically, and the copies may be different versions. Answered by: listing which depot_* folder each came from
   and its hash/size; checking whether one is an NG leftover.
4. **Should the launcher accept the depot-split layout (`steamapps/content/app_377160/depot_*`) as a source, merging by a fixed
   depot priority, or require a merged install?** The owner's real data is split, and no existing tool (MO2/LOOT/Wabbajack)
   handles it. Answered by: an owner decision plus a test that merging in depot order 377161 → 377163 → language → DLC gives the
   same file set as a normal install.
5. **What are the sha256 hashes of the remaining four DLC esms (DLCCoast, DLCworkshop02, DLCworkshop03, DLCNukaWorld) at 1.10.163?**
   Without them the launcher can't accept a complete install. Answered by: the owner downloading depots 435881/435882, 480630,
   480631/393885, 490650/393895 at the manifests in section 3, then `launcher.py sources-add`.
6. **Do we support NG/AE (1.10.984 / 1.11.240) input at all, or refuse and tell the user to downgrade?** Most players are on 1.11.240 now,
   and refusing them means asking every user to run a depot downgrade. Answered by: a spike that diffs 1.10.163 vs 1.11.240
   Fallout4.esm records/FormIDs with our own reader (the owner can fetch the current depot once). Also add BA2 v7/v8 to our reader,
   since the header is identical (verified).
7. **What exactly differs between BA2 v7 and v8?** If we read NG data, we need to know whether one of them changes payload/compression.
   Answered by: reading the headers and first records of NG `Fallout4 - *.ba2` and the NG CC archives with our BA2 reader;
   BAMgr FO4NGE / BASS docs (could not read: rate-limited).
8. **Does the language of the install change any file the converter reads besides voices?** It decides whether we hash per language.
   Answered by: comparing Fallout4.esm/DLC esm hashes from a German depot download (377166 + DLC de depots) against English.
9. **Which `sLanguage` codes exist (en, fr, de, it, es, pl, ru, ptbr, cn, ja, esmx?), and how should converted Starfield strings pick
   one?** We have 11 string tables in Interface.ba2 but have only seen 4 names. Answered by: listing all `Strings\Fallout4_*.STRINGS` in
   our `fo4_ba2.json` source archive, plus reading `sLanguage` from the user's Fallout4.ini / Fallout4_Default.ini.
10. **How do we identify the store and version without trusting folder names?** Answered by: hashing Fallout4.exe and reading its version
    resource, plus F4SE's import/section checks (Galaxy64.dll / .bind / appnotify / eossdk). Then verify on real GOG and Game Pass installs
    (we have none). Needs owner or community samples.
11. **Is a Game Pass install readable at all (no WindowsApps lock with the newer XboxGames folder), and which version does it ship?** If it
    is readable and its esms match a known hash, we can support it without F4SE (we only read data). Answered by: a Game Pass
    tester listing `<GamingRoot>\Fallout 4 (PC)\Content\Data` with sizes/hashes.
12. **Which GOG build is current and does GOG still offer 1.10.163?** London says GOG users need no downgrade, so GOG may be the easiest
    path for new users. Answered by: gogdb.org build list (blocked from here) or a GOG owner's `goggame-1998527297.info`.
13. **Do CC plugins matter to us?** If a user's FO4 data has `Fallout4.ccc` and cc*.esl, do we ignore them (only the 7 masters) or
    convert them too? Ignoring keeps the hash table small. Answered by: an owner decision; checking whether any of our converted records
    reference cc FormIDs (they can't if we read only the 7 masters).
14. **Can we use the downgrader's encrypted-patch pattern (patch keyed by the SHA-256 of the original file) for any launcher-provided
    fix-ups?** It lets us distribute patches without distributing Bethesda bytes. Answered by: a decision in docs/ai/decisions.md and a
    licence check (the downgrader is GPL-3.0, so reuse its idea but not its code unless we accept GPL).
15. **Should the launcher show the owner's exact `download_depot` commands for missing DLC when it refuses?** The downgrader's table gives
    them. Answered by: cross-checking each manifest ID against SteamDB's manifest history (SteamDB depot pages; JS needed), because of the
    duplicated Nuka-World fr/ru manifest.
16. **Does Steam's `appmanifest_377160.acf` (read-only trick) affect a depot-split install?** The owner's data in `steamapps/content`
    is outside Steam's update path, so updates can't overwrite it (supported hypothesis). Answered by: checking whether Steam ever
    touched depot_377163 timestamps after 2026-08-18.
