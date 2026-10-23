# 08: Saves, install, uninstall and testing for a start mod

Author: Claude (research subagent), 2026-10-19. Scope: what happens to saves when our plugins come and go, how a start
mod versions itself, how it is installed and removed cleanly, how serious projects test a new-game start repeatably,
and how Starfield patches break mods. Target: Starfield 1.16.244 (Steam, PC), our start plugin `FO4SFNewGame.esm`
with the start-game-enabled, run-once quest `FO4SF_NewGameQuest` (guard: `GameDaysPassed` and player level).

Labels: **verified** = primary source quoted (URL, file or in-game evidence named); **supported hypothesis** =
consistent with several sources or one non-primary source; **unresolved** = no usable evidence.

## Access note (read first)

WebFetch was refused with HTTP 429 (rate limited) on **every** page I tried, on five different hosts, and direct
`curl` was refused by the proxy (CONNECT 403). Per the rules I did not retry. Pages I could **not** read:

- https://www.gamingonlinux.com/2025/09/fallout-london-mod-gets-a-huge-upgrade-with-rabbit-pork/page=1/
- https://www.inverse.com/gaming/fallout-london-dlc-first-2025
- https://www.nexusmods.com/starfield/articles/635 (High Mod Index Warning)
- https://forums.nexusmods.com/topic/9981963-how-do-i-update-a-start-game-enabled-quest-to-work-on-existing-saves/
- https://taleoftwowastelands.com/faq
- https://starfieldportal.com/article/starfield-update-11230-full-patch-notes
- https://ck.uesp.net/wiki/Quest (curl, proxy 403)

So the web part of this note rests on (a) search-result **titles** (they show a page exists and what it is about;
they never prove its content, so at most **supported hypothesis**), (b) facts the sibling notes 01, 02, 03 and 05 in
this folder already **verified** with quotes and URLs (cited as "verified, via note NN"), and (c) the repository's own
in-game evidence (docs and scripts, cited by path). Everything a web page would have to confirm is listed as a
"source to read" in the last section.

---

## 1. Starfield save behaviour with plugins

### 1.1 The "different Creations Load Order" dialog (in-game, our PC)

- **verified (repo, in game, 13 Oct 2026).** On loading a save whose plugin list differs from the current one,
  Starfield 1.16.244 shows: *"This save uses a different Creations Load Order than your current Load Order. Would you
  like to use the Load Order from this save, or your current Load Order?"* with **"Save" preselected**. Pressing E
  picked "Save"; Starfield "switched to the save's load order and rewrote Plugins.txt with every experiment plugin
  inactive", and every later `coc` into our worldspaces froze. Source: `scripts/game/loadorder.ps1` lines 1-6;
  `docs/ai/first-run-failures-1014.md` row 2 ("verified in game"); `docs/PLAY-AND-TEST.md` line 123.
- Consequence for players: a player who loads an old (pre-mod) save after installing our plugins, and accepts the
  default, **switches our plugins off in Plugins.txt** without being told. The reverse (loading a Fallout save
  after a vanilla session) offers to switch them back on. **supported hypothesis** (the reverse case was not seen).
- The dialog wording says "Creations Load Order" even for Plugins.txt plugins, so the game treats both kinds in one
  load-order check. **supported hypothesis** (one dialog text; the ContentCatalog/Plugins.txt split behind it is
  not documented in anything I could read).

### 1.2 Removing a plugin, missing content

- Search titles show the long-standing Bethesda message "This save relies on content that is no longer present"
  and community threads asking if continuing is safe (FO4/Skyrim era):
  https://forums.nexusmods.com/topic/4759880-is-it-safe-to-continue-play-in-a-saved-file-that-contains-this-save-relies-on-content-that-is-no-longer-present ;
  Starfield threads on removing mods: https://steamcommunity.com/app/1716740/discussions/0/4638238612651036915 ,
  https://steamcommunity.com/app/1716740/discussions/0/592888717905012156 , Nexus article
  https://www.nexusmods.com/starfield/articles/702 . **unresolved** for content (not read).
- Engine behaviour carried over from earlier Creation Engine games, consistent with every start mod we read: on load
  the engine drops references and forms whose plugin is missing, but running scripts, script instances and
  persistent data stay in the save (orphaned), so removal mid-playthrough is "not supported". SKK Fast Start is
  "not removable from a save" (verified, via note 01: https://www.nexusmods.com/starfield/mods/5971). For our mod
  the player would also be **standing in a worldspace that no longer exists** (Vault 111 / Commonwealth), which in
  earlier games puts the player in a void or at a fallback location. **supported hypothesis** (no Starfield primary
  source read; to test on a throwaway save).

### 1.3 Load-order position and plugin-type changes

- Starfield plugin slots: full master (one of 253), medium (slot FD), small (slot FE). Bethesda: **"Changing the
  flag on an existing creation isn't supported."** **verified, via note 05**: https://nexusmods.com/news/14993 .
- Form ids in a save are stored against the plugin's position; the engine remaps them on load when order changes
  (the reason reordering is normally safe). **supported hypothesis** (standard Creation Engine behaviour; not read
  for Starfield). Exceptions: pre-CK warning that IPDS, SCEN, KSSM, STND, SFPT, SFTR sub-records were resolved by
  in-plugin position, so adding masters or reordering could break them. **verified as of Nov 2023, via note 05**
  (https://www.nexusmods.com/transformersdevastation/news/14888); whether still true on 1.16.244: **unresolved**.
- `Game.GetFormFromFile()` resolved "the wrong file index on ESM(small)" (SKK). **supported hypothesis, via notes 01
  and 03** (one author). Our start quest resolves FO4Port ids with GetFormFromFile, so **our plugins must stay full
  masters and must never change type between releases** (a type change = a new save).

### 1.4 Does a start-game-enabled quest from a newly added plugin start on an existing save?

- Creation Kit wiki (Skyrim): Start Game Enabled "starts running at the beginning of the game"; SGE quests "added to
  a pre-existing save" are a known case needing Run Once; Skyrim 1.7+ used SEQ files for added SGE quests' dialogue.
  **verified for Skyrim, via note 03** (https://ck.uesp.net/wiki/Quest_Data_Tab). Starfield: **supported
  hypothesis** that SGE quests from a new plugin start when the save loads, because every Starfield start mod needs
  a mid-game guard (Roleplayers' Alternate Start "deactivates itself on existing saves until NG+"; SKK stop codes).
- A Nexus forum thread is titled "How do I update a start game enabled quest to work on existing saves?"
  (https://forums.nexusmods.com/topic/9981963-...). The title suggests the inverse problem too: a quest **already
  started (or stopped) in a save does not restart** when a newer plugin version changes it. **supported hypothesis**
  (not read).
- Our quest: on an existing save it logs "not a new game ... standing down", goes to stage 1 and calls `Stop()`
  (`scripts/newgame/FO4SF_NewGameQuest.psc` lines 116-121). With Run Once set, it can never run again in that save,
  **including on NG+** (Unity), unless NG+ resets it. **verified** (source read) for the code path; NG+ behaviour
  **unresolved**.

### 1.5 Achievements

- **verified (repo, in game).** "First console use after a launch shows an achievements warning; dismissed with E";
  "the console achievements dialog needs a long E press and blocks other input while open"; it once "swallowed the
  `coc`". `docs/JOURNAL.md` lines 65, 71, 634.
- Plugins.txt mods disable achievements, Creations marked achievement-friendly do not; SKK published a separate
  "achievement-enabled" Creation edition of Fast Start. **verified, via note 01**
  (https://www.starfieldunity.com/mods/2444/skk-fast-start-new-game-starfield-achievement-enabled). Search titles
  agree (Prima Games "Do Mods Disable Achievements in Starfield?",
  https://primagames.com/tips/do-mods-disable-achievements-in-starfield-answered ; Steam
  https://steamcommunity.com/app/1716740/discussions/0/4331980041761048280). Whether achievements stay disabled on
  a save made with mods after the mods are removed: **unresolved** (the FO4/Skyrim precedent is that the save is
  flagged; not read for Starfield).
- Our project cannot be a Creation (FO4 assets, size, Bethesda content rules; note 05 section 5), so **our saves
  will have achievements disabled**. This is a documentation item, not a design problem. **supported hypothesis**.

### 1.6 Creations versus Plugins.txt mods

- Since 1.12.30 (9 June 2024) mod loading is on by default; Plugins.txt at `%LOCALAPPDATA%\Starfield\Plugins.txt`,
  `*Name.esm` lines; **ignored if any `sTestFile` INI variable is set**. **verified, via note 05**
  (https://nexusmods.com/news/14993 ; https://www.nexusmods.com/starfield/mods/4157). Our spike enabled
  `*FO4Port.esm` this way (verified in game, `docs/spikes/S2-S4-S9-plugin-units-loading.md` line 49).
- Creations are listed in `ContentCatalog.txt`; MO2 2.5.2 added "Creations parsing from ContentCatalog.txt".
  **verified, via note 05** (https://github.com/Modorganizer2/modorganizer/releases). How the game merges the two
  lists into one load order, and whether Creations always load before Plugins.txt plugins: **unresolved**
  (threads exist: https://forums.nexusmods.com/topic/13490787-the-game-changes-my-load-order ,
  https://forums.nexusmods.com/topic/13524420-game-launch-deactivates-starfield-plugins/ ; not read).

## 2. Save versioning and update policy precedents

- **Fallout: London**, Rabbit & Pork (30 Sep 2025): new launcher, **"requires a new save"**. **verified, via note 02**
  (GamingOnLinux and Wikipedia). German press headline: "Erster DLC mit XXL-Patch erschienen, doch ihr braucht ein
  neues Savegame" (https://www.pcgames.de/Fallout-4-Spiel-18293/News/London-DLC-Patch-Savegame-1483376/ , title
  only). Lesson: even the largest Creation Engine TC chose "new save" over migration for a major content update.
- **Tale of Two Wastelands**: FAQ exists (https://taleoftwowastelands.com/faq ,
  https://thebestoftimes.moddinglinked.com/faq.html); the 3.x "total rebuild" was reported by the press
  (https://bloody-disgusting.com/video-games/3536003/fallout-new-vegas-mod-tale-two-wastelands-updated-total-rebuild/).
  Their mid-playthrough update rule: **unresolved** (FAQ not read). Community practice, not verified: major TTW
  versions need a new game, patch versions do not.
- **SKK (Starfield)**: Fast Start conflicts with other start mods, detects other SKK mods, must not be removed
  mid-save. **verified, via note 01**. A general SKK mid-save policy page: **unresolved** (mod pages found by title:
  https://www.nexusmods.com/starfield/mods/8245 , /9609 , /7055 ; not read).
- **Skyrim save-migration scripts**: the pattern is a version number in a quest script, checked in
  `OnPlayerLoadGame` (a player-alias event) or `OnInit`, running per-version upgrade steps. Search found Enderal SE's
  `_00E_PlayerSetUpScript.psc` (https://git.eddoursul.win/enderal/enderalse/src/tag/2.0.12/source/scripts/_00e_playersetupscript.psc)
  and a commit "Added formlist PlayerPerks to add redundancy in case of overridden Player record by an outdated mod"
  (https://git.eddoursul.win/enderal/enderalse/commit/b4622c6f98a76f69f7049137d36ca9df604dee95), plus forum threads
  "running script on load" (https://forums.nexusmods.com/topic/12937695-running-script-on-load) and "problem with
  OnPlayerLoadGame" (https://forums.nexusmods.com/topic/6352301-le-problem-with-onplayerloadgame). **supported
  hypothesis** (titles; the pattern is standard Papyrus practice). Starfield's Papyrus has `OnPlayerLoadGame` on
  Actor/ReferenceAlias: **unresolved** (check ContentResources.zip sources offline).

**What our mod should record in a save to detect its own version** (proposal, **supported hypothesis** from the
precedents above):
1. A `GlobalVariable` `FO4SF_SaveVersion` (or an int property on a persistent quest) set when the start runs, holding
   our **save-format version** (bump only when a change breaks saves) separate from the release version.
2. The ids that matter: the build ids of `FO4Port.esm` / `FO4TerrainCore.esm` the save was started on (a hash or
   build number written as a global or quest property), because a regenerated port with changed form ids silently
   breaks references in a save (`docs/CODEX-HANDOFF.md` line 24: "Previously aliased mixed-plugin builds still require
   separately pinned regeneration, not silent save compatibility claims").
3. A persistent "checker" (quest alias on the player) that on every load compares the stored value with the plugin's
   constant and writes one log line plus a visible message when they differ ("this save was started with v0.x; it
   needs a new game"). No migration logic until the owner wants one.
4. The stood-down state (stage 1) is already recorded; it should also log the game version and our version.

## 3. Uninstall and reversibility

- Start mods document removal as "not removable mid-save; start a new game" (SKK Fast Start, verified via note 01;
  Fallout: London: base FO4 cannot be played with FOLON installed, going back means uninstalling both and
  reinstalling FO4, verified via note 02, PC Gamer). **supported hypothesis** that this is the norm.
- INI keys:
  - `sTestFile1..10` (`[General]`): disable Plugins.txt entirely when set. **verified, via note 05.** A clean install
    must never write them; an uninstaller should warn if it finds any. Vortex migrates `sTestFile` entries into
    plugins.txt, and "leftover INI entries block plugin management by Bethesda's design". **verified, via note 05**
    (https://forums.nexusmods.com/topic/13458887-starfield-extension-has-been-updated-to-support-load-ordering-and-pluginstxt).
  - `bInvalidateOlderFiles=1` and empty `sResourceDataDirsFinal=` (`[Archive]`): needed for loose files.
    **verified, via notes 04 and 05; and in repo** (`docs/spikes/S2-S4-S9-plugin-units-loading.md` line 42). We ship
    BA2 only, so we should **not** need them; if a user already has them, we must not remove them on uninstall.
  - `sStartingConsoleCommand` (`[General]`): runs a console command (typically `bat <file>`) when the game starts;
    SKK's pre-CK Fast Start used `sStartingConsoleCommand = bat SKKFastStartNewGame`. **verified, via note 01**
    (https://www.nexusmods.com/starfield/mods/3050). A Nexus guide is titled "sStartingConsoleCommand not always
    working" (https://forums.nexusmods.com/topic/13253886-...), behaviour on 1.16.244 **unresolved**. If left in a
    user's INI after uninstall it runs every launch; any installer that writes it must remove it.
  - `[Papyrus] bEnableLogging/bEnableTrace/bLoadDebugInformation`: in `StarfieldCustom.ini`. **verified, via note 05.**
    On our PC Controlled Folder Access blocked writes to Documents, so the repo writes the game folder's
    `Starfield.ini` with a backup (`docs/ai/first-run-failures-1014.md` row 4, verified). An uninstaller must restore
    that backup, and the player docs must say where the keys went.
- Mod Organizer 2: keeps INI files in its **profile folder**, so editing `My Games\Starfield\StarfieldCustom.ini` may do
  nothing under MO2. **verified, via note 05** (https://www.nexusmods.com/starfield/articles/780). MO2 profiles give
  separate load orders, INIs and (optionally) saves, which is the cleanest reversible install for players.
  **supported hypothesis** (MO2 behaviour from other games; Starfield profile-local saves not read).
- Vortex: load-order management off by default for Starfield (Dec 2023 extension). **verified, via note 05.**
- The game itself rewrites Plugins.txt (1.1 above, verified in our runs). Our tools already guard: restore exact
  Plugins.txt bytes on failure, refuse on concurrent edits, `exp_install.py active` check (`docs/JOURNAL.md` line 913;
  `docs/handoff-archive/2026-10-07-codex-history.md` lines 152-153). **verified (repo).**
- Clean removal recipe a start mod should document (**supported hypothesis**, assembled from the above): keep a
  pre-install save; remove plugins from Plugins.txt / the manager; delete our BA2s; restore INI backups; load only
  saves made before installing (they never referenced our forms); answer the load-order dialog with "Current".
  Saves started with the mod are not convertible back.

## 4. Testing practice for a new-game start

- **Console bat files** (`bat <name>` reads `<name>.txt` from the game folder) and **`sStartingConsoleCommand`** are
  the community's repeatable lever (SKK pre-CK). **verified, via notes 01 and 05.** The UESP console list documents
  `bat`, `coc`, `save`, `sqs`, `sqv`, `getstage`, `GetGlobalValue`. **supported hypothesis, via note 03**
  (UESP marks it "needs recheck").
- **`coc` from the main menu** starts a game in that cell without the opening (a known Bethesda debug path; Starfield
  "skip intro" guides exist: https://hub.tcno.co/videos/how-to-skip-intro-starfield-simple-guide/ ,
  https://exputer.com/news/games/starfield-mod-skip-intro/). **supported hypothesis** (not read). Important: a
  main-menu `coc` is **not** a new game for our test purposes (SGE quests may start, but MQ00/MQ101 state, chargen,
  `GameDaysPassed` and the player's level differ). Our own plan already rejects it: "COC entry is not an acceptable
  substitute" (`docs/testing/commonwealth-campaign.md` line 62). **verified (repo decision).**
- **Test saves**: preset/background saves were how Starfield "starts" worked before the CK (Alternate Start Starfield,
  Nexus 2076; verified via notes 01 and 03). For us a save is useful only for the **negative** test (the guard stands
  down on an existing save), never as the start itself.
- **Loud failure**: Fallout: London's lesson "fail loud on a broken start" (note 02); SKK documents known silent
  hangs (Fast Start menu not shown, controls locked; "dialogs or message boxes shown before setup completes can block
  it", verified via note 01). Our quest already logs every step and a status line every 5 s to
  `Logs\Script\User\fo4sf_newgame.0.log` and stands down with a log line (`FO4SF_NewGameQuest.psc` header,
  verified). PASS criteria are written (stage 200, "enter vault ok=True", "landed", no Starfield intro on screen;
  `docs/newgame/vault111-start.md` section 7). What is missing (**supported hypothesis**): a **visible** in-game
  message on failure (not only a log) and a timeout per stage that writes "FAIL stage N" so an unattended runner can
  stop instead of waiting.
- Our runner hazards are known and guarded: the load-order dialog (answer "Current"), the achievements dialog on first
  console use (long E), focus guard. **verified (repo)**, `docs/ai/first-run-failures-1014.md`.
- Automated "New" from the main menu: no community tool found that drives Starfield's main menu to a new game;
  projects use key automation or bat files. **unresolved** (no source found). Our input scripts can do it, but each
  new game also passes Starfield's own opening screens until our quest holds them off.

## 5. Starfield updates breaking mods (2024-2026)

Patch dates from search-result titles and note 05 (titles alone = **supported hypothesis** unless marked):

| Build | Date | What it did to mods | Label |
|---|---|---|---|
| 1.12.30 | 9 Jun 2024 | Creation Kit release, mod loading on by default, Plugins.txt Enabler obsolete | verified, via note 05 (https://nexusmods.com/news/14993) |
| 1.14.70 | late 2024 | Root form class changes forced SFSE plugin recompiles (SFSE 0.2.12-0.2.13) | verified, via note 05 (https://www.nexusmods.com/starfield/mods/106) |
| 1.15.216 / 1.15.222 | 2025 | A patch's compiler changes "invalidate the Address Library and most if not all existing plugins" (SFSE 0.2.17) | verified, via note 05 |
| Free Lanes update + Terran Armada DLC | 2025-26 (date unresolved) | Nexus news item 15482 | title only, supported hypothesis |
| 1.16.236 | 2026 | SFSE 0.2.19 | verified, via note 05 |
| 1.16.242 | 14 May 2026 | "Stability fixes", auto-save crash fix (Bethesda.net, mp1st, PSU titles); SFSE 0.2.20 | supported hypothesis (titles); SFSE line verified via note 05 |
| 1.16.244 | 11 Jun 2026 | Freezing and "major Incursion" fixes (mp1st title); SFSE 0.2.21 same day | supported hypothesis (titles: https://mp1st.com/title-updates-and-patches/starfield-new-update-1-000-006-released-june-11-fix-freezing-major-incursion-via-version-1-16-244 , https://bethesda.net/en-US/news/starfield-update-1-16-244-june-2026); SFSE verified via note 05 |

- What breaks: SFSE and every SFSE DLL plugin on **every** exe update (address changes); plugin-only mods usually
  survive, but plugin **form version** and Starfield.esm record changes can break plugins built by external tools
  (Mutagen form version 576 in our spike, note 05). Pure plugin + Papyrus mods (like our start) are the most
  robust. **supported hypothesis** (pattern across the SFSE changelog; no plugin-format break in 2025-26 found).
- Pinning practice: Fallout: London shipped a downgrader and told Steam users to make `appmanifest_377160.acf`
  read-only. **verified, via note 02.** The Steam equivalent for Starfield would be `appmanifest_1716740.acf`
  (app id from the Steam discussion URLs above). **supported hypothesis.** Our repo already pins and checks the exe
  version (`testqueue.py pin-game-version`, `docs/ai/test-queue.md` line 13; `docs/SETUP.md` pins 1.16.244 and SFSE
  0.2.21). **verified (repo).**
- Gating inside the game: a Papyrus-only mod cannot read the exe version without SFSE (`GetSFSEVersion` is an SFSE
  console command, note 05). So version gating belongs in the **installer/launcher** (read `Starfield.exe` file
  version), not in the plugin. **supported hypothesis.**

---

## Questions for our design

1. **What does the player see when they load a pre-mod save after installing?** Why: the load-order dialog preselects
   "Save", which silently switches our plugins off (verified on our PC). How: player docs + in-game test on a
   throwaway save (owner decision on the wording).
2. **Should the install write a separate profile (MO2 profile, or our own launcher's Plugins.txt swap) rather than
   edit the user's Plugins.txt?** Why: Plugins.txt is rewritten by the game and shared with every save. How: owner
   decision; offline check of MO2 profile behaviour on the PC (read-only).
3. **Do we store a save-format version in the save (global or quest property) from v1?** Why: Fallout: London had to
   say "new save" with no way to detect it; without a stored value we cannot even warn. How: owner decision, then an
   offline unittest of the writer and an in-game load test.
4. **Do we record the FO4Port / FO4TerrainCore build ids the save started with?** Why: regenerated ports can change
   form ids and break saves silently (CODEX-HANDOFF line 24). How: owner decision; offline design in decisions.md.
5. **What is our update policy: "new game on any port rebuild", "new game on save-format bump only", or migration?**
   Why: precedents (FOLON, TTW) pick "new game" for major versions. How: owner decision.
6. **Does Starfield's Papyrus have `OnPlayerLoadGame` (or an equivalent) for a version checker?** Why: needed for the
   per-load check in 2.3. How: offline check of ContentResources.zip sources (Actor.psc / ReferenceAlias.psc).
7. **Does our Run Once quest that `Stop()`ped on an existing save behave correctly on NG+?** Why: Unity may reset or
   carry quest state; a stopped run-once quest never restarts. How: owner decision on NG+ support, then an in-game test.
8. **Does a start-game-enabled quest from a newly added plugin start on a loaded Starfield save at all?** Why: our
   stand-down guard is only tested if it does. How: in-game test on a throwaway save (look for the "standing down"
   log line).
9. **Are `GameDaysPassed == 0` and level 1 reliable new-game signals in 1.16.244, including after chargen and on
   NG+?** Why: a false negative aborts a real new game; a false positive teleports a player mid-game. How: in-game
   test (log values at stage 0 on a new game and an NG+ start).
10. **What does a player get if they remove our plugins from a save started with them?** Why: they stand in a
    worldspace that no longer exists. How: in-game test on a throwaway save; then documented as "not supported".
11. **Should the start show a visible message (not only a log) when it stands down or fails a stage?** Why: "fail
    loud"; a silent stand-down looks like "the mod does nothing". How: owner decision, then in-game test.
12. **Do we add per-stage timeouts that write "FAIL stage N" to the log for unattended runs?** Why: SKK's known hangs
    (menu not shown, controls locked) would otherwise stall a runner. How: offline unittest of the parser + in-game test.
13. **Must our plugins stay full masters forever?** Why: Bethesda says changing the flag is unsupported, and
    GetFormFromFile misresolves on small masters (SKK). How: owner decision recorded in decisions.md; offline guard
    test that the writer refuses light/medium flags.
14. **Does the pre-CK warning about position-resolved SCEN/IPDS references still apply on 1.16.244?** Why: adding a
    master or reordering could break our scenes in saves. How: offline check (write two orders, compare resolved ids
    in xEdit/Mutagen) then in-game test.
15. **Do we ever write `sStartingConsoleCommand`, `sTestFile`, or `bInvalidateOlderFiles` on a player's machine?**
    Why: `sTestFile` disables Plugins.txt; a leftover `sStartingConsoleCommand` runs every launch. How: owner decision
    (proposed: never for players; test PC only, with backup and removal).
16. **Where do our INI changes live on the test PC, and does the uninstall restore the game-folder `Starfield.ini`
    backup?** Why: Controlled Folder Access pushed Papyrus keys into the game folder. How: read-only PC check of the
    backup and the current INI.
17. **What is our new-game test recipe: input automation through "New", a bat file, or both?** Why: main-menu `coc`
    is not a new game (repo decision). How: owner decision; in-game test of the chosen path, three repeat runs.
18. **Which negative tests run before every release: existing save (stand down), NG+, plugin missing, port missing?**
    Why: each is a support case. How: owner decision on the list, in-game tests on throwaway saves only.
19. **Do we gate by Starfield exe version in the installer, and what happens on an unknown build (refuse, warn,
    allow)?** Why: every patch breaks SFSE; a plugin-only start may survive but is untested. How: owner decision;
    offline unittest of the version reader; read-only PC check of the exe version.
20. **Do we tell players how to stop Steam auto-updating (read-only `appmanifest_1716740.acf`) as FOLON did?** Why:
    pinning protects saves but has support and Steam-policy costs. How: owner decision; read-only PC check that the
    file exists at that name.
21. **How do we document achievements being off?** Why: players will ask; console use on our test PC already shows
    the warning. How: owner decision on wording; nothing to test.
22. **How do Creations from ContentCatalog.txt interleave with our Plugins.txt masters, and can a Creation load
    after us and override Vault 111?** Why: load order decides who wins. How: read-only PC check of ContentCatalog.txt
    and Plugins.txt; in-game test with one Creation installed.
23. **What is the clean-uninstall checklist we publish?** Why: start mods are "not removable mid-save"; players need
    the pre-install save rule. How: owner decision, then offline check that `exp_install.py uninstall` restores all
    bytes (existing tests) and a read-only PC check after a real uninstall.

## Sources to read when the fetch limit clears

- TTW FAQ (update and save rules): https://taleoftwowastelands.com/faq
- Fallout: London Rabbit & Pork save notes: https://www.gamingonlinux.com/2025/09/fallout-london-mod-gets-a-huge-upgrade-with-rabbit-pork/page=1/
- CK wiki Quest Data tab and Quest pages: https://ck.uesp.net/wiki/Quest_Data_Tab
- Nexus: "How do I update a start game enabled quest to work on existing saves?": https://forums.nexusmods.com/topic/9981963-how-do-i-update-a-start-game-enabled-quest-to-work-on-existing-saves/
- Nexus Starfield articles 635 (High Mod Index Warning), 702, 1042; forum 13490787, 13524420, 13253886
- Bethesda.net 1.16.242 and 1.16.244 patch notes (links in section 5)
- Enderal SE player setup script (version/migration pattern): https://git.eddoursul.win/enderal/enderalse/src/tag/2.0.12/source/scripts/_00e_playersetupscript.psc
