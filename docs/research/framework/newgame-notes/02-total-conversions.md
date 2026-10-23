# 02: Total conversions and merged-game projects as precedents for our NEW GAME

Author: Claude (research subagent), 2026-10-19. Scope: how other total conversions (TCs) start a new game, isolate the
host game, install, and handle the legal side. Web research only; nothing here was checked on the PC or in game.

Labels: **verified** = stated by a primary or well-sourced page fetched for this note; **supported hypothesis** =
community or secondary source, plausible, not confirmed against files; **unresolved** = not found or contradictory.
Some pages could not be read: the Nexus wiki "Porting content" page returned a client error, and the Enderal (PCGamesN),
New California and Beyond Skyrim Bruma pages were refused by the fetch proxy (HTTP 429). Claims about those projects
are marked accordingly.

---

## 1. Fallout: London (FOLON), FO4 total conversion

- Links: https://en.wikipedia.org/wiki/Fallout:_London ,
  https://www.pcgamer.com/games/fallout/after-years-fallout-4s-much-anticipated-dlc-sized-mod-fallout-london-is-out-heres-how-to-install-it/ ,
  https://gamingonlinux.com/2025/09/fallout-london-mod-gets-a-huge-upgrade-with-rabbit-pork
- **Distribution.** Free on GOG (GOG hosted it because it was too large for typical mod sites). Released 25 July 2024
  after delays, one of them caused by FO4's next-gen update (25 Apr 2024). **verified** (Wikipedia).
  Rabbit & Pork update (30 Sep 2025) added its own launcher "powered by Overwolf" and asked for a new save.
  **verified** (GamingOnLinux; Wikipedia says "new launch method" and "requires a new save").
- **Base game.** Needs the pre-next-gen FO4 with all DLC; not the High-Res Texture Pack (wrong textures, crashes).
  Steam users run Team FOLON's Downgrader and set `appmanifest_377160.acf` read-only so Steam does not re-update.
  Steam Guard can block the downgrader. Epic was not supported at launch. **verified** (PC Gamer; PCGamesN headline).
  A reader comment names 1.10.163.0 as the target version: **supported hypothesis**.
- **Install model.** The GOG installer writes into the FO4 folder and edits INI and plugins.txt. PC Gamer says base
  FO4 cannot be played with FOLON installed; going back means uninstalling both and reinstalling FO4. **verified**
  (PC Gamer). A community Vortex method links the GOG folder into a staging folder so FO4 is not changed permanently,
  but then the user must re-apply the INI `[Archive]` lists (`sResourceStartUpArchiveList`, `SResourceArchiveList2`,
  `SGeometryPackageList=Fallout4 - Geometry.csg, LondonWorldSpace - Geometry.csg`, `SCellResourceIndexFileList=Fallout4.cdx, LondonWorldSpace.cdx`,
  later `sAnimationArchiveName`) and the plugins. **verified** (forums.nexusmods.com/topic/13495490).
- **Plugins.** `LondonWorldSpace.esm`, `LondonWorldSpace-DLCBlock.esp` (ESM or ESP: posts differ) and `BakaFramework.esm`
  on top of Fallout4.esm and the DLC masters. **verified** that these names are required (Nexus forum, Steam thread).
  What DLCBlock does exactly is **unresolved**; the name says it blocks FO4 DLC content (the DLC "radio/quest start"
  hooks are the obvious targets): **supported hypothesis**.
- **Start mechanism.** With a correct install, New Game plays London's own intro and title screen and starts the player
  in a lab vat with two scientists. **verified** (Steam threads 4512128445067047059, 4512128114435153923).
  If the plugins or launcher are wrong, the player gets FO4's bathroom/pre-war scene or wakes in the Commonwealth with
  no quests. **verified** (same threads). So FOLON keeps Fallout4.esm loaded and overrides FO4's start; it does not
  remove the host master.
- **How FO4's MQ101 is bypassed.** A Nexus CK thread on making an FO4 alternate start says "MQ101 is hard coded into
  Fallout4.exe" and that FOLON proves a replacement is possible; options given are editing MQ101's script or patching
  the exe. **supported hypothesis** (forums.nexusmods.com/topic/13503261, one modder's reply). FOLON's exact method is
  **unresolved** (no source read). Likely it overrides MQ101 data/script inside its own master.
- **Launch problems.** Many crash reports at launch, a 9 Aug 2024 hotfix, ~20 testers versus ~150 for FO4 (Dean
  Carter). **verified** (Wikipedia). The most common "start" bug was user error in the load order / launcher, which
  silently produced FO4's start.
- **Legal.** No formal arrangement with Bethesda described ("zero correspondence"). **verified** (Wikipedia). FOLON
  ships original assets and requires FO4; it does not redistribute other games' assets.

**Lessons for us**
1. A wrong install must fail loud, not fall back to the host game's start. FOLON's worst support load was players
   silently getting FO4's opening. We need a start-up check (in launcher and in-game) that our plugin is active and
   Starfield's MQ101 did not run.
2. Pin the host game version. A host update broke FOLON and forced a downgrader. Starfield updates often; our launcher
   needs a version gate and a "known good Starfield build" list.
3. Do not permanently change the host install. Use a separate profile / ini / plugin list so the user can still play
   vanilla Starfield (FOLON's one-way install was a common complaint).
4. Their own launcher came a year later "to make install faster and more reliable". Ours is planned from day one; good.
5. A new major version forced a new save. Plan save versioning from the start.

---

## 2. Tale of Two Wastelands (TTW), FO3 merged into New Vegas

- Links: https://fallout.wiki/wiki/Mod:Tale_of_Two_Wastelands , https://en.namu.wiki/w/Tale%20of%20Two%20Wastelands ,
  https://thebestoftimes.moddinglinked.com/ttw.html , https://thebestoftimes.moddinglinked.com/faq.html ,
  https://mod.pub/ttw/133/docs/25-faq-frequently-asked-questions , https://www.nexusmods.com/newvegas/mods/100059
- **Installer (legal model).** The TTW installer reads the user's own FO3 and FNV installs (both with all DLC, English),
  decompresses both games' BSAs, converts sound and voice files (audio re-encode: ~40 min on a Ryzen 5 5600X, hours on
  slower CPUs), patches some radio tracks, writes the Custom INI and builds a ~17 GB mod folder for MO2. **verified**
  (Best of Times guide and FAQ). A missing-size check (folder must be ~17 GB) is the documented integrity test.
  Since 3.4 FO3 no longer needs to be downgraded first. **supported hypothesis** (NamuWiki).
- **Why an installer.** The fallout.wiki page quotes a TTW team member that Bethesda "regularly checked" TTW was not
  distributing FO3 assets and "asked modding sites to not host TTW", so it was hosted on its own site and later ModPub
  (current page: mod.pub, v3.4.0, updated 15 Jun 2026). **supported hypothesis** (wiki quoting a team member; no
  Bethesda statement read). Piracy support leads to bans on the TTW/ModdingLinked Discords. **verified** (FAQ).
- **Start choice.** Early TTW: always FO3's Vault 101 start; reaching the Mojave meant the Union Station train quest,
  and hitting the train switch changed how the NV tutorial began. **verified** (2013 forum thread t=4323).
  From 3.2 the player can choose where to start; the choice depends on the Custom INI (FAQ: "if the option to pick which
  wasteland to start in is missing, edit your Custom INI"). NamuWiki says a Mojave start can also be forced with
  `SCharGenQuest=00102037` in Fallout.ini. **verified** that the INI controls the option (FAQ); the exact key is a
  **supported hypothesis** (NamuWiki). Leaving Vault 101 shows a prompt "Is this now, or just a memory?"; choosing
  "Memory" sends the player to the Mojave start. **supported hypothesis** (wastelandsurvival.guide).
- **The other game's start.** The non-chosen opening is not deleted; it stays reachable (train quest, flashback mods
  like TTW Flashback launch FO3's birth sequence from Doc Mitchell). **verified** for the mod (Nexus 100059).
- **Travel.** Capital to Mojave: a short quest to power Union Station, then the train; Mojave to Capital: Freeside
  station; ticket 100 pre-war money from 3.2.2. **supported hypothesis** (NamuWiki; fallout.wiki confirms Union Station).
- **Balance merges.** Level cap 50 to 60, FO3 bobbleheads become minor perks because stats max too easily. **verified**
  (fallout.wiki). Quick Start mod skips Vault 101 but disables the Mojave start choice. **verified** (survival guide).

**Lessons for us**
1. TTW is the legal template for us: build from the user's own install, ship no game files, own hosting if needed,
   zero tolerance for piracy. Expect Bethesda to watch for asset redistribution, not to bless the project.
2. The engine reads the char-gen/start quest from an INI key in Gamebryo-era games. We must check whether Starfield has
   an equivalent (`sCharGenQuest`, `sStartingConsoleCommand`, or none) before choosing between an INI route and an
   MQ101-override route.
3. Plan the "start choice" as a first-class feature. TTW added it late (3.2); later Fallout games (Far Harbor,
   Nuka-World, other worlds) will want a start-location choice too.
4. Long builds need integrity checks (expected size/hash), CPU-friendly options (`-threads:1`), and clear errors.
5. Don't hard-delete the host's opening; keep it reachable or cleanly stopped so quests that depend on it don't break.

---

## 3. Skyblivion (Oblivion in Skyrim SE)

- Links: https://en.wikipedia.org/wiki/Skyblivion , https://skyblivion.com/faq ,
  https://www.videogameschronicle.com/news/instead-of-shutting-down-mod-remaking-oblivion-in-skyrim-bethesda-gave-the-team-oblivion-remastered-keys
- Requires legally owned Skyrim SE and Oblivion GOTY (Steam or GOG, may mix stores); custom installer that downloads and
  places files; not on Creation Club, consoles, Game Pass/Epic unlikely. **verified** (FAQ).
- Bethesda required all original assets to be replaced, so nothing proprietary is redistributed. Bethesda later gave the
  team Oblivion Remastered keys and praised the project; no use of Remastered assets due to "legal restraints".
  **verified** (Wikipedia, FAQ, VGC headline).
- Start: you begin as in Oblivion, woken by Uriel Septim; travel to Skyrim's worldspaces is not supported and console
  travel there may break the game. **verified** (FAQ). How Skyrim's Helgen start is suppressed: **unresolved**.
- Release target 2026 (delayed from 2025). **verified** (Wikipedia).

**Lessons:** Bethesda's tolerated line for cross-game TCs is "no redistributed assets". Our model (convert on the user's
PC from their own FO4) is closer to TTW than Skyblivion; we must keep it that way. Fencing off host worldspaces is an
accepted design choice, not a failure.

## 4. Skywind (Morrowind in Skyrim)

- Link: https://www.nexusmods.com/uno/news/12752 (2016). Assets rebuilt from scratch after a dispute over cross-title
  assets; Nexus then supported it "along with Bethesda". Needs Morrowind and Skyrim (a quoted site FAQ says disc, GOG and
  Steam installs work). **verified** for the rebuild statement; ownership line **supported hypothesis** (user quote).
  Start design and isolation: **unresolved** (no release yet found in sources read).

## 5. Beyond Skyrim (Bruma etc.)

- Bruma (released on Nexus, Skyrim SE mod 10917/12693 per search results) is an add-on inside Skyrim, reached from the
  host world, not a separate new game; there is a community "alternate vanilla start for Beyond Skyrim Bruma" thread.
  **unresolved** (page refused by rate limit; only search titles seen). Lesson: the "DLC-style" model (enter from the
  host world) is the alternative to a separate new game; we chose the separate start.

## 6. Enderal (Skyrim TC, SureAI)

- Released as a free standalone entry on Steam ("Enderal: Forgotten Stories"), free if you own Skyrim. **supported
  hypothesis** (PCGamesN/mein-mmo headlines; article page refused). Precedent that a Bethesda TC can be listed on Steam
  as its own app with its own launcher and separate ini/saves folder (the separate folders: **unresolved** here).
  Lesson: a separate profile (own ini, own saves) avoids polluting the host game.

## 7. Fallout: New California (FNV)

- Released 2018; later on GOG mods with one-click install (search headline). Start design (own vault prequel) and how
  FNV's main quest is disabled: **unresolved** (page refused).

## 8. Fallout Cascadia, Fallout Miami, Fallout 4: New Vegas (FO4 projects)

- All still in development per PC Gamer "most ambitious Fallout mods in development" and news; FO4:NV rebuilds New
  Vegas in FO4 with new assets. No released start design to study. **supported hypothesis** (headlines only).

## 9. Capital Wasteland (FO3 in FO4), cancelled

- Link: https://pcgamesn.com/fallout-4/fallout-4-fallout-3-capital-wasteland-mod
- Shut down (13 March update) after the team consulted Bethesda and then a lawyer. Main problem: FO3 voice files.
  Distributing them was clearly not allowed; having players extract them from their own copy was also judged
  unworkable; Bethesda licenses the voice acting rather than owning it, so it could not grant rights. Lawyer:
  "sketchy as all hell". **verified** (PCGamesN, as reported).
- **This is the closest precedent to our project and the biggest legal risk**: an FO3-to-FO4 port that leaned on the
  user's own files was still abandoned over voice-actor licensing. TTW survives with the same model, so the risk is
  about Bethesda's tolerance, not a settled rule.

## 10. Starfield alternate starts (host-side precedents)

- Alternate Start Starfield (Nexus 2076, 2023, pre-CK): loaded premade saves and used console commands for traits.
  **verified** (eXputer). Shows the pre-CK hack route; not usable for us.
- LvxMagicks Alternate Start (Nexus 16745): player must watch part of the vanilla intro "so some MQ101 scripts set up
  correctly"; a Kiosk option skips the intro; fixes for chargen menu opening twice, opening mid-save, blocking
  notifications afterwards, a dark-screen hang from the intro mine scene, items removed at start; a save/load warning
  was added after chargen to fix UI notifications; clean reinstall needed on update. **verified** (mod page).
- Roleplayers' Alternate Start (Nexus 15094): skips One Small Step; lists knock-on effects (SSNN interview never
  happens, Frontier locked, Barrett moved, "Echoes from Vectera" missing on NG+, Auto Hide HUD breaks until One Small
  Step completes, leftover Constellation dialogue); on existing saves it deactivates itself until NG+. **verified**.
- Vault 77 Alternate Start (Nexus 7260): Starfield start re-themed as a Vault exit. Mechanism **unresolved**.

**Lessons:** In Starfield, skipping MQ101 has many downstream dependencies (UI unlocks, HUD, ship access, NG+ quests).
Mature mods either let MQ101 run its first setup steps and then branch, or accept a list of broken dependents. The
chargen menu in Starfield is fragile (double-open, notification lock) and needs a save/load or explicit cleanup after.

---

## Cross-cutting lessons

1. **Fail loud on a broken start** (FOLON). 2. **Version-gate the host game** (FOLON downgrader). 3. **Don't change the
   host install permanently** (FOLON complaints; Enderal/TTW use separate profiles). 4. **User-built from own files is
   the only workable legal model for converted assets** (TTW), and voice files are the sharpest legal edge (Capital
   Wasteland). 5. **The host's opening quest is the main source of hidden dependencies** (Starfield alternate starts,
   FO4 "MQ101 hard coded"). 6. **New major version = new save** unless save migration is designed.

---

## Questions our new-game design must answer

1. **Does Starfield have an INI start-quest key like FNV's `SCharGenQuest` (or FO4's)?** Decides INI route vs MQ101
   override. Answer: offline string search of Starfield.exe and default inis; read-only PC check.
2. **Is MQ101 hard-coded in Starfield.exe as claimed for FO4?** If yes we must override MQ101 itself rather than add a
   new start quest. Answer: offline exe strings/xref + in-game test with MQ101 stopped.
3. **Which MQ101 setup stages must run before we stop it** (UI unlocks, HUD, scanner, ship, Unity/NG+ flags)? Alternate
   start mods show breakage when skipped. Answer: offline read of MQ101 stages/scripts in Starfield.esm; in-game test.
4. **What state does a "complete" FO4SFNewGame start leave Starfield's main quest in** (stopped, completed, or dormant)?
   Affects Constellation content and later re-entry. Owner decision + in-game test.
5. **How does the player choose our game vs vanilla Starfield?** Separate profile/ini, separate plugin list, or in-game
   menu like TTW's choice? Owner decision.
6. **How do we detect and report a broken start** (our plugin missing, MQ101 ran)? FOLON's top failure. Answer: launcher
   pre-flight check + in-game first-frame script; offline unittest of the launcher check.
7. **Do we keep Starfield's opening reachable** (TTW style) or remove it? Owner decision.
8. **Which Starfield builds do we support, and what happens after a Starfield update?** Answer: launcher version gate;
   read-only PC check of exe version.
9. **Do we change the user's Starfield folder, inis or plugins.txt permanently?** Need a reversible install. Owner
   decision + offline launcher design.
10. **Is chargen (ShowRaceMenu-equivalent) safe to run outside MQ101** in the Vault 111 cell? LvxMagicks hit double
    opens and notification locks. Answer: in-game test.
11. **Do we need a save/load after chargen** to reset UI state, as LvxMagicks added? In-game test.
12. **What happens to the converted world if a later version changes forms?** Save versioning policy (FOLON forced new
    saves). Owner decision + design note in decisions.md.
13. **How do we handle FO4 voice files legally?** Capital Wasteland died on voice licensing; TTW converts them locally.
    Owner decision (possibly legal advice); document in decisions.md.
14. **Where do we host the launcher** (GitHub, Nexus, own site) given Bethesda reportedly asked sites not to host TTW?
    Owner decision.
15. **Do Starfield's radiant/event systems (SSNN, encounters, ship events, Constellation calls) fire in our world**
    before or after we stop MQ101? Answer: offline scan of story manager nodes + in-game test.
16. **Which UI elements depend on One Small Step** (Auto Hide HUD broke in RAS)? Answer: offline condition scan; in-game.
17. **How will future start choices (Far Harbor, Nuka-World, other Fallout games) plug in?** Design the start quest as
    a selector now (TTW added it late). Owner decision.
18. **What integrity check proves the build is complete** (TTW's ~17 GB rule)? Answer: launcher manifest of expected
    output files/hashes; offline unittest.
19. **What are build time and CPU needs** (TTW audio re-encode takes hours)? Answer: measured launcher run on the PC;
    record in docs/ai/optimization.md.
20. **Does our plugin need a "DLC block" equivalent** (FOLON's DLCBlock) for Shattered Space and Creations that inject
    quests at start? Answer: offline scan of Starfield DLC/Creation start-game-enabled quests; in-game test.
21. **Does anything in Starfield trigger on the player's home system or Unity state** that our world lacks? In-game test.

## Five most important findings

1. **Starfield's MQ101 has many hidden dependents.** Alternate-start mods either let part of MQ101 run first
   (LvxMagicks) or list broken side effects (Roleplayers' Alternate Start: SSNN, HUD auto-hide, Frontier, NG+ quests).
   This is verified on the mod pages.
2. **A wrong install silently fell back to FO4's start.** That was FOLON's most common start bug (bathroom scene,
   Commonwealth with no quests). Verified. We need a loud pre-flight check and an in-game check.
3. **The legal model only works if users build from their own files, and voice is the risky part.** TTW survives that
   way, with its own hosting (supported hypothesis). Capital Wasteland was cancelled over FO3 voice licensing (verified).
4. **Older engines choose the start quest from an INI key.** TTW's start choice is controlled through the Custom INI,
   reportedly `SCharGenQuest` (supported hypothesis). One modder says FO4's MQ101 is hard-coded in the exe (also a
   supported hypothesis). Whether Starfield has either is unresolved and decides our route.
5. **Changing the host install and updating the host game caused FOLON's biggest problems.** It needed the downgrader
   and a later Overwolf launcher, and a new version forced a new save (verified). Pin the Starfield version, install
   reversibly and version our saves from the start.
