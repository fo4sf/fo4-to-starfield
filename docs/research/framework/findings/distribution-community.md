# Distribution and community: how the port reaches players and lives in the community

Written 2026-10-19 by distribution-community (Claude-cloud research agent). Builds on, and does not repeat,
next-phase/launcher-gamma-model-and-community-tools.md and next-phase/launcher-architecture.md.
Labels: **verified** (read in the linked source or a repo file), **supported hypothesis**, **unresolved**.
Limits of this pass: the shared web-search budget ran out part-way and three pages were refused with HTTP 429
(the Nexus forum thread "game launch deactivates starfield plugins", starfieldwiki.net Mod:Main_Page, the STEP
Starfield portal). Topics that needed further searching (Fallout London's launch, Skyblivion's volunteer model,
Starfield update/SFSE breakage history, localization language lists, r/FalloutMods rules) are marked **unresolved**
and listed as follow-ups rather than filled in from memory.

**Bottom line.** The mod-manager ground under us has firmed up since the earlier notes: MO2 2.5.2 handles Starfield
plugins natively (the Plugins.txt Enabler is obsolete), reads Creations from ContentCatalog.txt and packs Starfield BA2s;
Vortex manages Starfield plugins natively since June 2024; Wabbajack lists Starfield as "Experimental, Platform-locked"
and a Linux front end (Jackify) exists. None of these can *run a converter*, so neither a Nexus Collection nor a
Wabbajack list can deliver us on its own; our launcher must build, and then hand the output to the player's manager
(or its own folder). Two precedents now answer much of the "will hosts accept a cross-game port tool" worry:
**FNV to FO4** has been on Nexus since October 2023 as a converter the player runs on their own two games, and in
October 2026 a Starfield Nexus mod (Outfit Porter) converts Fallout 4 outfits locally. GAMMA's model is less "an
installer" than "a git-tracked definition + a Discord that does the support", and in December 2025 GOG began selling
GAMMA as a one-click install gated on owning a STALKER game, which is the strongest sign yet that "bring your own game,
we assemble it" is a mainstream distribution form. The biggest community risks for us are not legal but social: an
"FO4 in Starfield" announcement will be read as "a remaster", the Steam/Lemmy discussions we found expect either a
remaster or a legal takedown, and big volunteer patches (the Starfield Community Patch) are already looking for
caretakers. Our repo is publicly indexed by search engines already (it surfaced in a general web search), so
expectation management has effectively started.

## Findings

### 1. Mod managers and Starfield

**Mod Organizer 2**
- **verified** MO2 v2.5.0 (Nov 2023) needed the "Plugins.txt Enabler" (via SFSE or an ASI loader) for Starfield plugin
  management, gave decent support only to ESM files, had LOOT sorting off by default, required removing every
  `sTestFile` entry from the game INIs, and its BSA Packer could only write Fallout 4-format BA2s
  ([v2.5.0 RC2 notes](https://github.com/ModOrganizer2/modorganizer/releases/tag/v2.5.0rc2)).
- **verified** MO2 v2.5.2 (latest on the releases page, dated 4 Aug): "Plugins.txt Enabler is obsolete"; "Utilize
  Starfield.ccc to 'fix' the load order of core plugins"; "Added support for new 'medium'-flagged plugins"; "Added
  support for Creations parsing from ContentCatalog.txt"; "BSA Packer now supports Starfield archive formats"; save
  parsing updated for the newer save format ([releases](https://github.com/Modorganizer2/modorganizer/releases)).
  The page shows no year next to 4 Aug; that it is 2024 is a **supported hypothesis** (2.5.0 was Nov 2023 and the
  Enabler became obsolete when Bethesda added native plugin management in June 2024, per the Vortex page below).
- **verified** "MO2 cannot support Windows Store / Gamepass versions of supported games" (v2.5.0 notes, same page).
- **verified** MO2's BSA extractor is slow on archives with many directories; base-game mesh/geometry archives load
  slowly (v2.5.0 RC2 notes). Relevant if our output is one very large BA2 set.

**Vortex**
- **verified** Starfield Vortex extension 1.10.5, updated 10 June 2026, works for Steam and Game Pass; plugin
  management active "since June 2024, and plugin enablers are no longer required"; drag-and-drop ordering by default or
  LOOT; native plugins are not written to plugins.txt; any `sTestFileX` entry in an INI blocks plugin management "by
  Bethesda's design"; INI edits a mod needs must be made by hand in StarfieldCustom.ini (no INI merging); it can create
  a folder junction between the game's Data folder and the My Games Data folder; cloud sync (OneDrive, Google Drive,
  Dropbox) "can cause data loss with folder junctions"; Game Pass installs must sit outside the protected folder (e.g.
  C:/XboxGames) for junctions; Game Pass cannot use SFSE, so the extension uses the Ultimate-ASI-Loader, which it calls
  outdated ([Nexus site/mods/634](https://www.nexusmods.com/site/mods/634)).
- **verified** Dec 2023 staff posts: Vortex moves `sTestFile` entries into plugins.txt; a purge/redeploy reset load
  order to alphabetical (a core Vortex flaw, ticketed); Vortex "does not currently handle BA2 load order or conflicts"
  ([Nexus forum](https://forums.nexusmods.com/topic/13458887-starfield-extension-has-been-updated-to-support-load-ordering-and-pluginstxt)).
  Whether BA2 conflict handling has landed since is **unresolved**.

**Wabbajack and Linux front ends**
- **verified** Wabbajack's support table: "Starfield | Steam | | Experimental, Platform-locked*"; MO2 is "the only
  officially supported mod manager"; platform-locked because core files differ between platforms, so lists are tied
  to the build they were made for ([Wabbajack wiki](https://wiki.wabbajack.org/user_documentation/Supported%20Games%20and%20Mod%20Managers.html)).
- **verified** Jackify: "A modlist installation and configuration tool for Wabbajack modlists on Linux", listing
  Starfield, alpha quality ([AlternativeTo](https://alternativeto.net/software/jackify/about/)).
- **verified** The MO2 Linux installer (MO2-LINT, now maintained by furglitch, rewritten in Python) lists Starfield and
  Fallout 4 as supported ([GitHub](https://github.com/rockerbacon/modorganizer2-linux-installer)).

**Nexus Collections**
- **verified** A Starfield collections section exists and points to Vortex as the manager for collections
  ([Nexus](https://www.nexusmods.com/games/starfield/collections)); the list itself did not render (JavaScript), so its
  size is **unresolved**.
- **supported hypothesis** A Collection installs mod archives; it cannot run a multi-hour converter against a second
  game's files. So Collections are a channel for *mods built on our core* (L2 manifests) after the launcher has built
  the base, not for the base itself.

### 2. The GAMMA model, in more detail than the earlier note
- **verified** The GitHub repo holds "actively updated" files and "updates happen quite often"; the "complete client
  (heavy, rarely modified files)" is downloaded from the Discord; add-ons are fetched from ModDB or GitHub; the MO2
  instance offers "visit moddb.com" per add-on; PRs go to the `dev2` branch; reuse rules: credit "original addon author,
  from Stalker GAMMA", and numbered addons (105-) need the original author's consent before repost
  ([Stalker_GAMMA](https://github.com/oleh5230/Stalker_GAMMA)).
- **verified** The third-party GPL-3 `gamma-launcher` reimplements the first-setup launcher (commands `anomaly-install`,
  `full-install`, `check-md5` for ModDB add-ons, `--cache-directory` to reuse downloads); the official .NET launcher
  "is not possible on GNU/Linux because of .NET / powershell scripts" ([gamma-launcher](https://github.com/Mord3rca/gamma-launcher)).
- **verified** The update step fetches "the G.A.M.M.A. definition" with `git fetch`; large-repo fetches fail on unstable
  connections (RPC failure, early EOF); the workaround is `GAMMA_LAUNCHER_NO_GIT=1` for a legacy download; users ask for
  auto-resume of large non-git downloads ([issue #185](https://github.com/Mord3rca/gamma-launcher/issues/185)).
  Lesson: a git-backed definition is cheap to update but a fragile transport for players; keep a plain-HTTP fallback.
- **verified** Support model is Discord-first: "join ... and follow the installation steps in #how-to-install", and the
  release culture warns that GAMMA "is not holding your hands"; the 0.9.3 annual update recommended a fresh save because
  saves were only "mostly" compatible ([r/stalker 0.9.3 thread mirror](https://pol1.lr.ggtyler.dev/r/stalker/comments/1h3ylar/gamma_093_release/lzvuf8f/?context=3)).
- **verified** GOG began offering GAMMA as a one-click install (article 1 Dec 2025); a quoted store requirement says the
  buyer must own S.T.A.L.K.E.R. 2 or Call of Pripyat Enhanced Edition; commenters report the GOG version broken on Linux
  (Dec 2025, Apr 2026) and point to gamma-launcher instead
  ([GamingOnLinux](https://www.gamingonlinux.com/2025/12/gog-add-stalker-gamma-as-a-one-click-mod-install/page=1)).

### 3. Direct precedents for "convert another Bethesda game on the player's PC"
- **verified** FNV to FO4 (Nexus fallout4/mods/75425, uploaded 17 Oct 2023, updated 20 Jun 2024, v63, 239
  endorsements): converts the New Vegas base game's models and plugins into Fallout 4, "currently excluding NPCs,
  creatures and other gameplay elements"; "the result will have a lot of rough edges"; takes "around 1-2 hours";
  requires both games launched once and the Fallout 4 Creation Kit; output copied to Data or zipped for a mod manager
  ([Nexus](https://nexusmods.com/fallout4/mods/75425); [GitHub, GPL-3.0](https://github.com/terry-haire/fnv-to-fo4)).
  This is the closest hosting precedent we have: a cross-game converter, Nexus-hosted for three years, no takedown found
  (absence of a takedown is a **supported hypothesis**, not proof of permission).
- **verified** Outfit Porter (Starfield Nexus mods/18458, 14 to 17 Oct 2026, beta): "can automatic convert the outfit for
  starfield" from Fallout 4, requires MO2 and Texconv; the Nexus virus scan shows "Some suspicious files"
  ([Nexus](https://www.nexusmods.com/starfield/mods/18458)). Lesson: Nexus's scanner flags converter executables; plan for
  that (signing, VirusTotal link, source build).
- **verified** TTW's installer FAQ: "Folder ... is not absolute for location" is fixed by removing quotes or disabling
  Windows **Controlled Folder Access**; requires both games "installed in English, with all DLCs"; a crash/NTDLL error may
  be CPU overheating, workaround `-threads:1`; E-cores can slow it; "This app can't run on your PC" fixed by Unblock in
  file properties; Linux support "not yet official", limited to a Discord channel
  ([TTW FAQ](https://thebestoftimes.moddinglinked.com/faq.html)).
- **verified (repo)** We already hit Controlled Folder Access on the owner's PC: `scripts/bridge/make_bridge.py` lines
  207-217 record that on 2026-10-14 it blocked python.exe writing StarfieldCustom.ini in Documents (Defender event 1123)
  and fell back to the game folder's Starfield.ini.

### 4. Where modders gather, and how big community projects run
- **verified** Starfield Community Patch: community-owned with "caretakers", a four-person core team at launch, MIT, releases
  on GitHub and Nexus, discussion in the Starfield Modding Discord, issues submitted on its own site with a Nexus login,
  plugins kept as text with Spriggit and shipped as an ESM ([Nexus news, 30 Aug 2023](https://www.nexusmods.com/codevein/news/14877));
  its site reports "517 fixes from 46 contributors" and accepts a bug only if reproducible "on a new save"
  ([starfieldpatch.dev](https://starfieldpatch.dev)); a Nexus "helpful links" post says it is "looking for new caretakers"
  and may be retired, with Arthmoor's Unofficial Starfield Patch as the likely successor
  ([Nexus forum](https://forums.nexusmods.com/topic/13203033-helpful-links-references-and-news/page/36)).
  Lesson: even a well-run volunteer project loses its core team within ~2-3 years; plan succession from day one.
- **verified** The same post points xEdit downloads to a channel in the xEdit Discord, and Starfield beta feedback to
  the Bethesda Studios Discord's #steam-beta-feedback (same source). Bethesda beta branches are therefore announced
  where we can watch them.
- **verified** r/starfieldmods runs a "Request Wednesday" with the rule "Be reasonable. Making mods is not a small effort"
  and rejects "I'm just the writer / ideas" requests; its feed mixes releases with support posts such as "SFSE won't
  launch from MO2" ([redlib mirror](https://redlib.belloworld.it/r/starfieldmods)). Its self-promotion rules were not in
  the captured page (**unresolved**).
- **verified** Patchers were publicly frustrated with Bethesda's mod support before the CK (Nov 2023)
  ([PCGH forum](https://extreme.pcgameshardware.de/threads/starfield-community-patcher-frustriert-ueber-mangelhaften-mod-support.641868/)).
- **unresolved** Collective Modding Discord, the Starfield Modding Discord's invite and rules, r/FalloutMods rules, and
  the starfieldwiki.net modding namespace (page refused with 429) were not read this pass.

### 5. Existing talk about "Fallout in Starfield's engine" (player expectations)
- **verified** Steam FO4 thread "Play Fallout 4 Remaster With Better Engine?" (11 Jul 2021): posters frame it as a
  *remaster*, argue a port "is close to remaking the game", and expect fan projects to stall
  ([Steam](https://steamcommunity.com/app/377160/discussions/0/3059616584924796846/?l=greek)).
- **verified** A Lemmy !games thread on New Vegas in a newer engine: hope for "a full conversion", immediate doubt it
  would survive a cease and desist, Skywind/Skyblivion cited as the safe pattern because they recreate content, a VATS
  argument, and a joke about "New Vegas as a planet in Starfield" ([next.lemm.ee](https://next.lemm.ee/post/12632388)).
- **verified (by observation)** A general web search for porting the Commonwealth into Starfield returned our own repo
  (github.com/fo4sf/fo4-to-starfield) among the results, so the project is already discoverable.
- **supported hypothesis** Players will expect: (a) the whole game, quests and voices included; (b) Fallout gunplay,
  VATS and Pip-Boy; (c) better graphics than FO4; (d) mod compatibility with their FO4 load order; (e) a date. Our
  phase order delivers interiors and a walkable world long before (a) and (b). This mismatch is the main communication risk.

### 6. Launcher accessibility: Linux, Steam Deck, Windows paths
- **verified** Starfield is not Steam Deck Verified as of the 2023 review (20-30 FPS at 720p low)
  ([GGRecon](https://www.ggrecon.com/guides/starfield-steam-deck-verified-performance-best-settings/)); a May 2025 beta
  crashed on Linux/Deck and Proton Experimental fixed it in ~18 hours; Deck performance stayed "below 30FPS" in New
  Atlantis ([GamingOnLinux](https://www.gamingonlinux.com/2025/05/valve-developers-continue-to-impress-fixing-proton-in-less-than-a-day-for-the-starfield-beta/page=1/)).
  The current Deck rating is **unresolved**.
- **verified** Proton Experimental shipped a crash fix for "Starfield: Creation Kit" (31 Jul 2024)
  ([comss.ru](https://www.comss.ru/page.php?id=14194)). So the CK runs under Proton at least in part; whether the CK's
  Papyrus compiler (spike E's recompile route) works headless under Proton is **unresolved**.
- **verified (repo)** Our code locates My Games by trying `~/OneDrive/Documents` then `~/Documents`
  (`scripts/game/bridge_log.py:46`, `scripts/bridge/make_bridge.py:178`, `scripts/game/testqueue.py:2463,3082`;
  `scripts/mission/make_mission.py:50` tries only `~/Documents`). **supported hypothesis**: this misses (1) Documents
  redirected to another drive, (2) OneDrive folders with a tenant suffix ("OneDrive - Company"), (3) OneDrive-for-Business
  or localized OneDrive folder names on non-English Windows, (4) Proton prefixes, where My Games lives under
  `steamapps/compatdata/1716740/pfx/drive_c/users/steamuser/Documents/My Games/Starfield`. The robust Windows answer is the
  Known Folder API (FOLDERID_Documents); this was not verified against a source in this pass.
- **supported hypothesis** Non-ASCII user names (e.g. `C:\Users\Jürgen`, Cyrillic, CJK) break tools that use the ANSI
  code page; Python 3 and .NET handle Unicode paths, but external tools we call (Archive2, texconv, xEdit, PowerShell
  5.1 scripts saved without a BOM) need testing. **unresolved** which of ours do.

## Precedents and what they teach us

| Precedent | Teaches |
|---|---|
| FNV to FO4 (Nexus, 2023-) | A converter that needs both games can live on Nexus; be blunt about "rough edges" and what is excluded; state the run time up front |
| GAMMA (GitHub + Discord + ModDB, GOG since Dec 2025) | Ship a small, frequently updated definition and a rarely changing heavy client; support lives in Discord channels with a fixed install channel; saves across big updates are "mostly" compatible, so say so; a git transport needs a non-git fallback; even a store version can be broken on Linux while a community launcher works |
| gamma-launcher | An unofficial CLI reimplementation appears when the official launcher is Windows-only (.NET/PowerShell). Designing our launcher as a cross-platform CLI first avoids needing one |
| TTW installer FAQ | The real failure list is environmental: quotes in paths, Controlled Folder Access, blocked downloads (Unblock), overheating CPUs, E-cores, non-English game installs. Our FAQ should start from that list |
| Starfield Community Patch | Text plugins (Spriggit) for review; reproducible-on-new-save bar for bugs; contributor credits page; but core teams churn, so name caretakers and a handover rule |
| Wabbajack "platform-locked" | Steam and Game Pass builds differ; lists are pinned per build. Our build must pin the Starfield build too (it already pins FO4) |
| Outfit Porter | Nexus's scanner flags converters as "suspicious"; expect it and pre-empt with source, reproducible builds and a hash list |

## Risks

1. **Expectation gap (high likelihood, high impact).** Every discussion found frames this as a remaster with full
   content. A showcase of interiors without quests, voices or VATS will draw "it's just the map" reactions. Mitigation is
   wording and a public "what works" matrix, not features.
2. **Starfield updates breaking the build (high likelihood, medium-high impact).** Wabbajack calls Starfield platform-locked
   and the 2025 beta broke Proton until patched; Starfield.ccc, medium plugins and a new save format all appeared in
   MO2's changelog. A Starfield patch can change plugin rules or break SFSE. We pin FO4 1.10.163 but nothing yet pins a
   Starfield build in the launcher. (Specific SFSE breakage history is **unresolved** this pass.)
3. **Game Pass players (medium likelihood, medium impact).** MO2 cannot manage Game Pass installs and SFSE does not run
   there (Vortex page). If any of our phases needs SFSE, Game Pass is out; say so before players buy anything.
4. **Support load on one owner (high likelihood, high impact).** GAMMA, TTW and the Community Patch all rely on volunteer
   Discord helpers. Our project has one human owner and AI agents that are forbidden from acting on `needs-triage`
   reports. Without volunteer triagers, the queue grows faster than the owner can read it.
5. **Antivirus and Windows security (medium likelihood, medium impact).** Controlled Folder Access already blocked us;
   Nexus flagged a comparable converter; unsigned .exe downloads get SmartScreen and "Unblock" prompts.
6. **Legal/hosting (low-medium likelihood, very high impact).** FNV to FO4 and Outfit Porter lower the odds, but neither
   is a formal permission. A cease-and-desist would arrive through the host (Nexus/GitHub).
7. **Volunteer churn (medium likelihood over 2+ years).** The Community Patch is already seeking caretakers.
8. **Linux tooling gap (medium likelihood, low-medium impact).** If the launcher is PowerShell- or WPF-bound, Linux and
   Deck users will build their own (as with gamma-launcher) and file bugs we cannot reproduce.

## Questions for the framework

### New game
1. **Do we promise anything about save compatibility across our releases?** Why: GAMMA says saves are "mostly"
   compatible across a major update and recommends a fresh start; our FormIDs change if the build changes (plan L4).
   Options: no promise before 1.0; a "save-safe" flag per release; a migration tool. Evidence: a determinism test plus a
   save loaded across two builds. Who: owner decision after an L4 probe.
2. **Does the Vault 111 start need to be reachable from Starfield's main menu by players who never used a console?**
   Why: reddit support posts show players struggle with SFSE and MO2 launches already. Options: launcher starts the game
   in Fallout mode; a menu entry; a console command in the readme (FNV to FO4 uses `coc Goodsprings`). Evidence: owner
   trial with a non-technical tester. Who: owner + PC probe.

### Door animations
3. **Which phase outputs are worth showing publicly as video, and which would set wrong expectations?** Why: door
   animations are visible and shareable; a clip implies the rest works. Options: show with an on-screen "pre-alpha,
   no quests" caption; show nothing until interiors. Who: owner decision.

### All interiors
4. **Is "all interiors" a public milestone (a GitHub release) or an internal one?** Why: it is the first build a player
   could explore, and the first that draws a crowd. Options: a tester-only beta (closed, Discord role); a public
   pre-release on GitHub; nothing public. Evidence: support capacity estimate (risk 4). Who: owner.
5. **How do interior bug reports carry enough location data?** Why: the Community Patch only accepts bugs reproducible
   on a new save; our report hotkey already records cell and position (docs/community/reporting-tool.md). Options:
   make the hotkey part of the launcher; add a "copy report" button; require cell + build hash in the issue form.
   Who: offline design; owner sign-off.

### Launcher
6. **Which mod managers do we target as an output, in which order?** Why: MO2 2.5.2 and Vortex both manage Starfield
   plugins natively now; MO2 cannot do Game Pass; Vortex has no BA2 conflict handling (as of Dec 2023). Options:
   own folder + ledger only (current plan); export as an MO2 mod folder (TTW's approach: build into
   `mods/<name>`); a Vortex-installable archive; all three. Evidence: install one built interior set via each on the
   PC, and check plugins.txt and StarfieldCustom.ini afterwards. Who: PC probe.
7. **How does the launcher deal with `sTestFile` entries?** Why: both MO2 and Vortex say any `sTestFile` in an INI
   blocks plugin management; our test chain may still use them. Options: refuse to run while they exist and offer to
   remove them (Vortex's way); never write them ourselves; record them in the ledger and restore. Evidence:
   `grep sTestFile` over our scripts and the owner's INIs. Who: offline + PC probe.
8. **Does the launcher read and respect Starfield.ccc and ContentCatalog.txt (Creations)?** Why: MO2 2.5.2 uses both to
   order core plugins and to name Creations; our preflight checks load order. Options: read them in preflight;
   ignore Creations; refuse to build with certain Creations active. Evidence: read the owner's copies (read-only PC
   job). Who: PC probe + offline.
9. **Do we pin a Starfield build per launcher release, and what happens after a Starfield patch?** Why: Wabbajack
   platform-locks Starfield lists; Steam auto-updates. Options: refuse to launch on an unknown build; warn and continue;
   keep a "known good" table updated within N days. Evidence: hash table of Starfield.exe per build; history of patches
   that broke SFSE (unresolved this pass). Who: offline research + owner policy.
10. **Steam only, or Game Pass too?** Why: MO2 and SFSE do not support Game Pass; Vortex does via an ASI loader it
    calls outdated. Options: Steam-only v1 and say so; Game Pass without SFSE features; later. Who: owner decision,
    informed by whether any phase needs SFSE.
11. **How is the launcher updated, and over what transport?** Why: GAMMA's git-fetched definition fails on unstable
    connections and needed a non-git fallback. Options: GitHub Releases asset + a signed JSON manifest over HTTPS; git;
    Nexus API (needs a key). Evidence: size of our definition files; resume support test. Who: offline design.
12. **Is the launcher a CLI first with a GUI on top, so it runs on Linux and Steam Deck?** Why: GAMMA's .NET/PowerShell
    launcher could not run on Linux, so the community wrote gamma-launcher; our scripts are PowerShell-heavy today.
    Options: Python CLI (already our build language) + thin GUI; .NET GUI; PowerShell. Who: owner decision + decisions.md.
13. **How do we find My Games, the game folders and Documents robustly?** Why: our code guesses `~/OneDrive/Documents`
    then `~/Documents`, which misses redirected, tenant-suffixed and Proton-prefix folders. Options: Windows Known Folder
    API; registry `User Shell Folders`; a manual override always shown; Proton `compatdata/1716740` path on Linux.
    Evidence: a unit test with synthetic layouts; a probe on a non-English Windows VM. Who: offline + a community tester.
14. **Do we handle non-ASCII user names and paths end to end?** Why: converters call external tools; TTW lists
    path-format errors first in its FAQ. Options: test matrix with `C:\Users\Jürgen`, Cyrillic and CJK names; run
    external tools with short (8.3) paths; refuse with a clear message. Evidence: synthetic-path unittest + one VM run.
    Who: offline + tester.
15. **What does the launcher do about Controlled Folder Access, SmartScreen and "Unblock"?** Why: CFA already blocked us
    (make_bridge.py), TTW's FAQ covers both, Nexus flagged a comparable tool. Options: detect CFA and explain; write
    INIs to the game folder fallback (we do already); code-sign releases; publish hashes and a VirusTotal link. Who:
    owner (signing costs money) + offline.
16. **What disk and time budget do we show, and do we support building on a different drive than Starfield?** Why:
    FNV to FO4 states 1-2 hours, TTW 17 GB and 40 minutes of audio; the owner's D: is nearly full. Who: PC probe
    measuring a full build.

### World and planet
17. **What do we say publicly about Far Harbor and Nuka-World on one planet?** Why: players will ask "is it the real map
    scale?" and "where is the Island?"; one planet differs from FO4's separate worldspaces. Options: explain early with a
    map image; stay silent until it works. Who: owner.

### People and story
18. **Which languages can the port support, and does it inherit them from the player's own FO4?** Why: FO4 ships
    localized string tables and voice in several languages, and Starfield has its own set; TTW requires English installs
    of both games. If our record writer keeps localized string references, a German FO4 could produce a German port at
    no cost; if it inlines English, every non-English player is excluded. Options: English-only v1 (TTW precedent);
    string tables passed through; voice per language. Evidence: list FO4's and Starfield's language sets (unresolved this
    pass) and test a non-English FO4 STRINGS file through the converter on a synthetic fixture. Who: offline research + owner.
19. **What happens when a player's FO4 is not English?** Why: hash tables (plan) will differ per language; TTW refuses.
    Options: one hash table per language; hash only language-neutral files and treat STRINGS separately. Who: offline.
20. **How will we answer "will it have voices / quests / companions" before those phases?** Why: the top expectation.
    Options: a public feature matrix with "not yet / partial / works"; a FAQ entry. Who: owner wording.

### Fallout systems
21. **Do we say up front whether VATS, Pip-Boy, power armor and workshop are planned, and in what order?** Why: the
    Lemmy thread shows VATS is contentious and expected. Options: roadmap page; no promises. Who: owner.
22. **Will FO4 mods ever work with the port?** Why: players will ask on day one; the honest answer today is "no, but mods
    built on our core will" (plan L2). Options: state it in the first post; a later FO4-mod converter. Who: owner.

### Release and community
23. **Where is the project's home: GitHub only, a Discord, a subreddit, a Nexus page, our own site?** Why: GAMMA's
    support is Discord, the Community Patch's is its own site + Starfield Modding Discord, TTW's is site + Discord.
    Options: GitHub Issues + Discussions only (fits the owner-only triage rule); add a Discord with a #how-to-install and
    a #known-issues channel; join an existing server (Starfield Modding, Collective Modding) instead of creating one.
    Evidence: ask those servers' admins whether a project channel is possible. Who: owner + community contact.
24. **Who triages community reports when volume grows, given only the owner may remove `needs-triage`?** Why: risk 4.
    Options: trusted human volunteers with a triage role; an AI-drafted summary the owner approves in bulk; a
    "duplicates and known issues" auto-reply. Who: owner decision (AGENTS.md change).
25. **Do we accept outside contributors, and under what terms?** Why: GAMMA takes PRs to a dev branch; the Community Patch
    credits 46 contributors; our repo is MIT with GPL-3 binaries. Options: no outside PRs before 1.0; PRs with a DCO
    sign-off; contributor credits page. Who: owner; note in decisions.md.
26. **How do we recruit the specialists we lack (animators, quest scripters, testers on varied hardware)?** Why: AI
    agents cannot test on other PCs, other languages, Linux, Game Pass. Options: a tester sign-up issue form; ask in
    r/starfieldmods' Meta; collaborate with FNV to FO4's author (same problem one engine back). Who: owner + community.
27. **Should we contact the FNV to FO4 author and the Outfit Porter author?** Why: they solve parts of our pipeline
    (models, outfits) and have already dealt with Nexus about cross-game converters. Who: owner (outreach is owner-only per AGENTS.md).
28. **Do we ask Nexus staff before the first upload, and what do we ask?** Why: the earlier note left this unresolved;
    FNV to FO4 is now a precedent we can cite. Options: cite FNV to FO4 and ask for confirmation that a no-assets
    converter is fine; GitHub first and Nexus later regardless. Who: owner.
29. **What is our policy on dates?** Why: the 2021 Steam thread expects fan projects to stall; a missed date costs more
    trust than no date. Options: never publish dates, only "what works now"; dated milestones only after a feature is
    done. Who: owner.
30. **What goes in a changelog, and for whom?** Why: GAMMA links patch notes on GitHub; players need "what changed, do I
    need a new save, do I need to rebuild". Options: a player changelog section separate from the agent journal;
    generated from PR labels. Who: offline design + owner.
31. **How do we keep the public description from reading as a remaster or a "free FO4"?** Why: the legal-safety pattern
    (TTW, FNV to FO4) is "you must own both games; nothing is shipped"; the Lemmy thread shows the takedown fear is the
    first reaction. Options: put the ownership requirement in the first sentence of every page. Who: owner wording.
32. **Is a GOG-style store listing ever a goal?** Why: GOG now sells GAMMA gated on game ownership; Fallout London went
    through GOG (earlier note). Options: not a goal; revisit after 1.0. Who: owner.

### Tooling and testing
33. **Which non-owner environments do we test before a public release?** Why: GOG GAMMA broke on Linux; Wabbajack calls
    Starfield platform-locked. Options: a matrix of Steam Windows English, Steam Windows non-English, OneDrive-redirected
    Documents, Proton desktop, Steam Deck. Evidence: volunteer testers (Q26). Who: owner + volunteers.
34. **Do we keep built plugins diffable as text, as the Community Patch does with Spriggit?** Why: reviewing changes
    between releases and proving determinism (L4). Who: offline spike.
35. **Can a built output be verified on the player's PC by hash to make bug reports comparable?** Why: a report from a
    build that differs from ours is not reproducible. Options: launcher prints a build hash; the report form requires it.
    Who: offline design.

### Cross-cutting
36. **Does any phase require SFSE, and is that worth losing Game Pass and adding a version lock?** Why: SFSE is
    "may be required" in the brief; Vortex says Game Pass cannot use it. Who: owner, after the phase that first needs it.
37. **Is the Creation Kit under Proton good enough for the Papyrus recompile route?** Why: if the CK is a hard
    requirement, Linux users need it to run headless. Evidence: a Proton test of the CK's Papyrus compiler. Who: a
    Linux tester.

## Corrections and updates to earlier notes
- launcher-gamma-model-and-community-tools.md section 4 lists MO2's Starfield support as "a supported hypothesis; needs a
  test". It is now **verified** in MO2's own release notes (2.5.2: native plugins, Creations, medium plugins, Starfield
  BA2 packing), with the verified limit that Game Pass is not supported. A PC test is still needed for *our* output size.
- Same file, section 4: Archive2 is not the only way to pack Starfield BA2s on the player's PC; MO2 2.5.2's BSA Packer
  "now supports Starfield archive formats" (verified, releases page). BSArch's status is still unchecked.
- Same file, section 2 left "whether Nexus moderators accept a tool whose purpose is a cross-game port" unresolved. It
  remains formally unresolved, but FNV to FO4 (Nexus fallout4/mods/75425, 2023-2024) and Outfit Porter (Starfield
  Nexus, Oct 2026) are verified precedents of Nexus hosting cross-game converters.
- launcher-architecture.md section 3 describes GAMMA "from general knowledge". Verified detail now: a git-fetched
  definition plus a Discord-hosted heavy client, ModDB/GitHub add-ons, Discord-only support, and a GOG listing since
  Dec 2025 (section 2 above).

## Follow-ups not done (search budget exhausted / 429)
Fallout London's release-date history and launch problems; Skyblivion and Skywind volunteer recruitment pages;
Collective Modding and Starfield Modding Discord rules; r/FalloutMods rules; starfieldwiki.net modding namespace;
history of Starfield patches that broke SFSE; FO4 and Starfield language lists; current Steam Deck rating for Starfield;
whether Vortex now handles BA2 conflicts.

## Sources
- https://github.com/ModOrganizer2/modorganizer/releases/tag/v2.5.0rc2
- https://github.com/Modorganizer2/modorganizer/releases
- https://www.nexusmods.com/site/mods/634
- https://forums.nexusmods.com/topic/13458887-starfield-extension-has-been-updated-to-support-load-ordering-and-pluginstxt
- https://wiki.wabbajack.org/user_documentation/Supported%20Games%20and%20Mod%20Managers.html
- https://alternativeto.net/software/jackify/about/
- https://github.com/rockerbacon/modorganizer2-linux-installer
- https://www.nexusmods.com/games/starfield/collections
- https://github.com/oleh5230/Stalker_GAMMA
- https://github.com/Mord3rca/gamma-launcher
- https://github.com/Mord3rca/gamma-launcher/issues/185
- https://pol1.lr.ggtyler.dev/r/stalker/comments/1h3ylar/gamma_093_release/lzvuf8f/?context=3
- https://www.gamingonlinux.com/2025/12/gog-add-stalker-gamma-as-a-one-click-mod-install/page=1
- https://nexusmods.com/fallout4/mods/75425
- https://github.com/terry-haire/fnv-to-fo4
- https://www.nexusmods.com/starfield/mods/18458
- https://thebestoftimes.moddinglinked.com/ttw.html
- https://thebestoftimes.moddinglinked.com/faq.html
- https://www.nexusmods.com/codevein/news/14877
- https://starfieldpatch.dev
- https://forums.nexusmods.com/topic/13203033-helpful-links-references-and-news/page/36
- https://redlib.belloworld.it/r/starfieldmods
- https://extreme.pcgameshardware.de/threads/starfield-community-patcher-frustriert-ueber-mangelhaften-mod-support.641868/
- https://steamcommunity.com/app/377160/discussions/0/3059616584924796846/?l=greek
- https://next.lemm.ee/post/12632388
- https://www.ggrecon.com/guides/starfield-steam-deck-verified-performance-best-settings/
- https://www.gamingonlinux.com/2025/05/valve-developers-continue-to-impress-fixing-proton-in-less-than-a-day-for-the-starfield-beta/page=1/
- https://www.comss.ru/page.php?id=14194
- https://stepmodifications.org/wiki/Starfield:Starfield_Script_Extender_(SFSE)
- Repo files (read-only, main 447ec09): scripts/bridge/make_bridge.py, scripts/game/bridge_log.py, scripts/game/testqueue.py,
  scripts/mission/make_mission.py, docs/community/reporting-tool.md
