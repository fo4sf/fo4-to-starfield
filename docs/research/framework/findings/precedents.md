# Precedent total conversions and cross-game ports

Written 2026-10-19 by the `precedents` research agent (Claude-cloud). Builds on
/mnt/project-files/research/next-phase/launcher-gamma-model-and-community-tools.md and launcher-architecture.md and
does not repeat their table (GAMMA, Wabbajack, TTW size/time, Nexus asset rule, licences).
Labels: **verified** (read in the linked source), **supported hypothesis**, **unresolved**.
Research limits: this run hit the shared web-search budget and then an HTTP 429 rate limit. Not read: beyondskyrim.org,
openmw.org/faq, the Skywind volunteer handbook, a Wccftech Fallout London interview and a Hitmarker Skyblivion piece.
Beyond Skyrim, Enderal's Steam edition and Starfield total conversions are therefore thin and marked unresolved.

**Bottom line.** Only one precedent actually converts game A's content into game B's engine on the player's PC and has
shipped for years: **Tale of Two Wastelands**. It works because both games share an engine generation. A FO4 tool hosted
on Nexus ("FNV to FO4", 2023 to 2024) shows that a player-side cross-engine converter can be hosted there, but it ships
"rough edges" and no NPCs, quests or scripts. The closest *legal* precedent to us is **Capital Wasteland (FO3 in FO4,
2018)**, and it is a warning. The team built a tool to extract Fallout 3's audio from the player's copy and convert it
for FO4. After talking to Bethesda staff and a lawyer they cancelled, because voice acting is *licensed, not owned*, by
Bethesda. They restarted only as a full re-voice. Our repo already does the same thing for Codsworth's voice: FO4 `.fuz`
to `.wem` via Wwise (`scripts/actors/codsworth_voice.py`). Every large remake that lasted (Skywind, Skyblivion, F4NV,
Capital Wasteland v2) moved to replacing assets, voices first. Skyblivion did so because Bethesda required 100%
replacement. The schedule lessons repeat across projects: 8 to 14 years for remakes, firm dates slip (Skyblivion 2025 to
2026, Fallout London 2023 to Apr 2024 to Jul 2024), and a platform update can block a finished release (FO4 next-gen
update, Apr 2024). The questions that matter most for us are therefore: is voice and audio conversion in or out, how do
we survive game updates on both sides (FO4 *and* Starfield), and how do we keep a mostly-agent team honest about dates.

## Findings

### 1. Tale of Two Wastelands (FO3 into New Vegas)
- **What ships / what the player supplies.** An installer (`TTW Install.exe`). It needs English FO3 and FNV with all DLC,
  and store versions may be mixed: "You may "mix and match" Steam, GOG, and Epic Games versions". The Microsoft Store is
  not supported. German FNV is a problem ("No Gore" exe, incompatible with xNVSE). **verified**
  ([Best of Times intro](https://thebestoftimes.moddinglinked.com/intro.html))
- **Installer internals.**
  - It applies binary deltas with xdelta3. The FAQ's error list includes "xdelta3.dll was not found" (fix: extract the
    archive first) and "BASS Init" / "XD3 Input" errors (fix: install all DLC in English, run each game once, verify
    files). **verified** ([Best of Times FAQ](https://thebestoftimes.moddinglinked.com/faq.html))
  - BASS is a third-party audio library, so the audio step uses it. **supported hypothesis** (inferred from the error name)
  - It is multi-threaded, with a `-threads:1` fallback for crashes ("NTDLL error"), which the FAQ blames on an overheating
    CPU. The FAQ also suggests disabling Intel E-cores to speed the install up. **verified** (same FAQ)
  - In the 2013-era 2.x installer, BSAs were checked before patching: "Your version of PointLookout - Main.bsa cannot be
    patched", "taleoftwowastelands-Main.bsa failed to patch properly". Support's standard advice was to reinstall FO3.
    **verified** ([TTW forum t=1031](https://taleoftwowastelands.com/viewtopic.php@t=1031),
    [t=2111](https://taleoftwowastelands.com/viewtopic.php@t=2111))
  - The 2.x output was about 7.7 GB; today it is about 17 GB. A folder under 17 GB means the install failed and
    corrupted files (red-diamond missing meshes). **verified** (t=2111; FAQ)
  - Its BSA library, BSA#, was "created for the Tale of Two Wastelands mod project" (MIT). **verified**
    ([bsasharp](https://github.com/jzebedee/bsasharp/))
- **Game updates.** Verifying game files in Steam reverts the 4GB/exe patch and the Vorbis libraries, and the player must
  re-apply them. **verified** (FAQ). The YUP bug-fix patch is now split from the main installer "so existing installations
  can be updated more easily". **verified** ([Best of Times TTW](https://thebestoftimes.moddinglinked.com/ttw.html)).
  The old engines no longer get updates, so TTW never faced a moving target the way FO4 and Starfield do. **supported
  hypothesis**
- **Hosting and support.** TTW's FAQ link now redirects to ModPub (`mod.pub/ttw/133`), which lists version 3.4.0, updated
  2026-06-15. Support is on Discord; the old phpBB forum is read-only. **verified**
  ([ModPub FAQ](https://mod.pub/ttw/133/docs/25-faq-frequently-asked-questions)). The 3.2 "total rebuild" came in
  December 2018 **verified** ([Bloody Disgusting](https://bloody-disgusting.com/video-games/3536003/fallout-new-vegas-mod-tale-two-wastelands-updated-total-rebuild/)).
  Linux is "planned but not imminent". Community managers (Amethyst, Fluorine) run the installer on Linux, and Amethyst
  2.4.3 had to fix "a critical breakdown in the Tales of Two Wastelands installer for Linux users". **verified**
  ([FAQ](https://thebestoftimes.moddinglinked.com/faq.html); [warp2search](https://www.warp2search.net/story/amethyst-mod-manager-v243-drops-ttw-installer-fix-and-wabbajack-beta/))
- **Legal stance.** None published on the pages read. **unresolved**

### 2. Fallout: London (new content on FO4)
- **History.** Started in 2019 and grew to almost 100 modders and over 100 voice actors. It used about 20 testers against
  Fallout 4's 150, and some members left suddenly when the war in Ukraine started. Planned for 2023, then 23 April 2024,
  then released 25 July 2024 on GOG, with 500,000+ downloads in 24 hours. **verified**
  ([Wikipedia](https://en.wikipedia.org/wiki/Fallout:_London))
- **Next-gen breakage.** The FO4 next-gen update (25 April 2024) landed two days after the planned launch. The team
  delayed indefinitely, said a rollback would come "only as a last resort", and noted that third-party partners still
  had to update their tools. The "Fallout 4 Downgrader" reached about 60,000 downloads in under a week. **verified**
  ([TechSpot](https://www.techspot.com/community/topics/fallout-london-was-ready-for-launch-until-bethesdas-buggy-next-gen-update-broke-it.285631/)).
  Dean Carter said at "the 11th hour" that next-gen "isn't stable enough". Epic copies cannot run it because Epic cannot
  roll back updates. **verified** ([PCGamesN](https://www.pcgamesn.com/fallout-london/epic-games-store))
- **Install.** On GOG, install FO4 GOTY in English and turn off cloud saves. On Steam, run Team FOLON's Downgrader, which
  needs a Steam login and had Steam Guard problems; skip the High-Res Texture Pack; and set `appmanifest_377160.acf` to
  read-only so Steam does not update FO4 again. **verified**
  ([PC Gamer](https://www.pcgamer.com/games/fallout/after-years-fallout-4s-much-anticipated-dlc-sized-mod-fallout-london-is-out-heres-how-to-install-it/))
- **Launch problems.** Crashes on the train ride, with weapon debris, precombines and previs (`BGSCombinedCellGeometryDB`).
  Mod managers overwrote the required INIs. CC files and the HD pack broke installs. The wrong `Fallout4.esm` caused
  failures, and GameStar gave the sizes: 322,994 KB is right, 67,326 KB is wrong. Steam auto-updates undid the downgrade.
  Players had to launch through `f4se_loader.exe`. **verified**
  ([GameStar, 2024-07-31](https://www.gamestar.de/artikel/fallout-london-absturz-crash-technische-probleme,3417255,seite2.html)).
  Critics called it "barely playable". A hotfix followed on 2024-08-09. **verified** (Wikipedia)
- **Later.** A VR version on 2025-05-28. On 2025-09-30, *Rabbit & Pork* (needs a new save; "thousands of bug fixes") with
  a **custom Overwolf-based launcher**. **verified**
  ([GamingOnLinux](https://www.gamingonlinux.com/2025/09/fallout-london-mod-gets-a-huge-upgrade-with-rabbit-pork/page=1/)).
  It coincided with a funded Kickstarter for a collector's edition. The team plans an original IP as an indie studio, and
  Carter reported "zero correspondence" from Bethesda. **verified** (Wikipedia). Whether Rabbit & Pork accepts next-gen FO4
  is **unresolved**: one reader comment says it is still pinned to 1.10.163.

### 3. Skyblivion (Oblivion into Skyrim SE)
- **Pipeline.** It began around 2012 as a *port*. Zilav wrote a tool to port Oblivion assets, but incompatible files
  broke map areas and crashed the game. Bethesda then "required that 100% of the original assets be replaced". The
  landscape had to be hand-built. **verified** ([Wikipedia](https://en.wikipedia.org/wiki/Skyblivion))
- **Team.** Over 40 volunteers by 2021, led by Rebelzize, recruited through Nexus from 2016, with "AAA-like" departments.
  **verified** (Wikipedia). An ex-department lead claimed crunch and a shrinking minimum viable product (2025-09-03).
  **verified** ([FRVR](https://frvr.com/blog/news/former-skyblivion-dev-accuses-leads-of-rushing-the-long-in-development-mod))
- **Timeline.** The 2025 window was announced in January 2023. On 2025-12-03 it moved to 2026. Still to do: the last
  Imperial City assets, navmesh "across all locations" ("all NPCs and creatures" depend on it), the last quest lines and
  QA. **verified** ([Skyblivion delay post](https://skyblivion.com/?p=10677);
  [Hitmarker](https://hitmarker.net/news/oblivion-in-skyrim-mod-skyblivion-delayed-to-2026-to-provide-additional-development-time-1591206)).
  No 2026 release found as of this writing. **unresolved** (search budget ran out)
- **Requirements.** Oblivion GOTY Deluxe and Skyrim SE from Steam or GOG, mixed is fine. Epic and Game Pass copies are
  "either encrypted and/or different than the Steam files". A custom installer will "download and move the necessary
  files". Remaster assets are not supported "due to legal restraints". **verified** ([Skyblivion FAQ](https://skyblivion.com/faq))
- **Bethesda.** Bethesda gave the team free Oblivion Remastered keys in April 2025 and praised the project. **verified**
  (Wikipedia, citing IGN and PC Gamer)

### 4. Skywind (Morrowind into Skyrim SE)
- Began in 2012 with about 8 modders and had 70 volunteers by January 2014. In September 2012 it was "advised" to remake
  everything. Wikipedia says it "has been officially approved by the publisher Bethesda Softworks". **verified**
  ([Wikipedia](https://en.wikipedia.org/wiki/Skywind))
- Status in May 2026: all base quests written and being implemented; about 3,000 NPCs cast, over 92% recorded; 10 of 13
  regions at 90 to 100%; 28 of 30 kits done; about 300 volunteer voice actors. It is recruiting asset implementers, NPC
  AI programmers and QA. There is no release date. **verified**
  ([Wccftech, 2026-05-09](https://wccftech.com/skywind-2026-milestone-quests-written-no-release-date/amp/))
- "We will never charge for Skywind" and no donations for exclusive access. It needs SKSE plugins, which is one reason
  there is no console version. **verified** ([Skywind FAQ](https://tesrskywind.com/faq/))

### 5. Capital Wasteland (FO3 into FO4) — the closest legal precedent
- A team of about 5 had **built a tool to extract Fallout 3 audio and convert it for Fallout 4**. Bethesda staff "heavily
  hinted at our methods being illegal" and a lawyer called it "sketchy as all hell". The voice acting is licensed, not
  owned, so Bethesda could not grant it. Staff suggested a Beyond Skyrim-style path instead. Cancelled March 2018.
  **verified** ([Kotaku](https://kotaku.com/fallout-3-in-fallout-4-mod-canceled-after-team-talks-to-1823738281);
  [PCGamesN](https://pcgamesn.com/fallout-4/fallout-4-fallout-3-capital-wasteland-mod))
- PCGamesN says having players extract the audio from their own copies was "also deemed unworkable". **verified** (PCGamesN)
- It restarted on 2019-01-02 as a re-voice of about 45,000 lines with under 10 people, and the halt was described as
  "entirely related to audio". PC Gamer adds that TTW avoided the problem "because its games share an audio format".
  **verified** that PC Gamer says so
  ([PC Gamer](https://www.pcgamer.com/au/capital-wasteland-the-fallout-3-remake-in-fallout-4-has-resumed-development);
  [GameRevolution](https://www.gamerevolution.com/news/478241-fallout-4-capital-wasteland-mod-returns)).
  That explanation is a journalist's gloss, and TTW does re-encode audio for 40 minutes, so "same engine family" is the
  likelier distinction. **supported hypothesis**

### 6. F4NV (New Vegas into FO4) and the FNV to FO4 converter
- F4NV (2018): "dozens" of volunteers. The mod "will not work without both games installed". It uses assets from
  "legally-owned copies" but recreates voice work and music "to avoid legal ramifications". **verified**
  ([GameRevolution](https://www.gamerevolution.com/news/433019-fan-project-fallout-4-new-vegas-shows-progress)).
  Its status after 2018 is **unresolved**.
- **FNV to FO4 (Nexus FO4 mod 75425, by bololo11; GPL-3 on GitHub).** The player runs an `.exe` that converts New Vegas
  models, plugins, worldspace, cells, landscape and placements into an `output` folder. It needs both games launched once
  and the **FO4 Creation Kit**, and takes 1 to 2 hours. NPCs, creatures, quests and scripts are excluded, and weapons and
  armour cannot be equipped. The page warns of "a lot of rough edges". Uploaded 2023-10-17, v63 dated 2024-06-20, 239
  endorsements. **verified** ([Nexus](https://nexusmods.com/fallout4/mods/75425);
  [GitHub](https://github.com/terry-haire/fnv-to-fo4))

### 7. Fallout: The Frontier and Project Brazil (two different projects)
- **Correction to the brief:** Project Brazil became *Fallout: New California* (renamed 2017). **verified**
  ([TechRaptor](https://techraptor.net/gaming/news/fallout-project-brazil-renamed-fallout-new-california-nearing-release)).
  *The Frontier* is a separate FNV mod from another team.
- **Project Brazil.** The lead raced a self-imposed deadline before Fallout 4 ("Not having a clear cut deadline and mandate
  is my kryptonite", 2015) and was still "more or less complete" in 2017. **verified**
  ([Kotaku](https://kotaku.com/ambitious-new-vegas-modders-rush-to-finish-before-fallo-1710449586))
- **The Frontier.** Started around 2014; 30 to 40 active modders and over 100 contributors by 2017. Scope was cut in 2019.
  Nexus's servers buckled at the 2021 release. A rework collapsed around 2023 through "poor management". **verified**
  ([fallout.wiki](https://fallout.wiki/wiki/Mod:Fallout:_The_Frontier)). It was pulled about 28 January 2021 when a
  contributor's off-project content surfaced. It returned by February 1 with that person's art replaced by placeholders,
  and other contributors pulled their voice work and music; the Steam release was postponed. **verified**
  ([PC Gamer](https://www.pcgamer.com/uk/fallout-mod-the-frontier-returns-after-stripping-out-content-from-disgraced-artist/)).
  Another modder's lessons: lack of communication, competing visions, and surprise content not previewed. **verified**
  ([Gfinity](https://www.gfinityesports.com/article/fallout-nuevo-mexico-modder-lessons-learned-from-frontier))

### 8. Cascadia, Miami, Enderal, OpenMW, Beyond Skyrim, Starfield total conversions
- **Fallout: Miami.** Silent for two years, then a new trailer in April 2024. 16 developers, about 6 years in, still
  recruiting, no date. **verified**
  ([3DJuegos](https://www.3djuegos.com/juegos/fallout-4/noticias/interes-fallout-4-tiene-poder-revivir-a-mods-que-parecian-muertos-2-anos-silencio-miami-reaparece-promesas-nuevo-trailer))
- **Fallout: Cascadia.** Volunteers, resumed showcases after a quiet spell, "Whenever we have a date set, it'll be
  announced". **verified** ([PCGamesN](https://www.pcgamesn.com/fallout-cascadia/fan-game-update)); article undated.
- **Enderal.** SureAI, 14 people, five years. Released July 2016 (German first). Needs base Skyrim but no DLC. SureAI
  later turned to commercial games. **verified** ([Wikipedia](https://en.wikipedia.org/wiki/Enderal)). The Steam
  standalone and SE editions were not read: **unresolved**.
- **OpenMW.** A GPL-3 engine reimplementation that "does not include copyrighted material from Bethesda" and needs the
  player's Morrowind. 0.1.0 came in June 2008; 0.50.0 on 2025-11-07, still pre-1.0 after about 17 years. **verified**
  ([Wikipedia](https://en.wikipedia.org/wiki/OpenMW)). Our project cannot take this route because CE2 is closed.
- **Beyond Skyrim.** Only the Kotaku mention (Bethesda staff pointed Capital Wasteland to it) was read. Structure and
  Bruma's release are **unresolved** this run.
- **Starfield total conversions.** Not researched (search budget exhausted). **unresolved.** Next run: search Nexus
  Starfield's "Overhauls"/"Total conversion" categories and Creations.

## Corrections and extensions to project notes
1. launcher-gamma note §1 says Skywind/Skyblivion have "nothing published [showing] a formal permission". Wikipedia
   states Skywind "has been officially approved" by Bethesda, and Skyblivion's remake followed Bethesda's requirement of
   100% asset replacement. There was contact, with conditions, though the primary text of either is not public.
   (Sources: Skywind and Skyblivion Wikipedia.)
2. Same note §2 marks as unresolved whether Nexus accepts a cross-game conversion tool. A precedent exists: FNV to FO4
   (Nexus FO4 75425) has converted the player's New Vegas into FO4 since 2023 and is listed "Safe to use". It converts
   no audio. This extends the note rather than settling it; ask Nexus anyway.
3. Same note §1 says Bethesda later hired some Fallout London modders (Techdirt). Wikipedia quotes Carter: "zero
   correspondence" from Bethesda. These can both be true; do not cite the hiring as Bethesda endorsing the mod.
4. ROADMAP §C1 takes "the launcher Fallout London has" as the owner's model. Since 2025-09-30 that launcher is an
   **Overwolf-based** custom launcher shipped with Rabbit & Pork (GamingOnLinux), not only the GOG installer. Codex's
   step-by-step study should cover it, and its ads/telemetry model is one we should not copy (supported hypothesis;
   Overwolf's terms not read).
5. Brief: "Project Brazil / Fallout The Frontier" are two different projects (see §7).

## Precedents and what they teach us
| Precedent | Lesson for fo4-to-starfield |
|---|---|
| TTW | Patch-on-player-PC works for 10+ years if sources are checked before patching and support has a script for "reinstall the source game". Split frequently changing fixes (YUP) from the heavy base build. Plan a CPU-heat/threads fallback. Expect community Linux tooling to depend on our installer's internals. |
| Capital Wasteland | Cross-engine audio extraction and conversion is the one method Bethesda staff and a lawyer flagged, even from the player's own copy. Our `.fuz` to `.wem` path is the same shape. Decide this before voiced NPCs and companions. |
| F4NV, Skywind, Skyblivion, CW v2 | Every long-lived remake ended up re-voicing, and two of them remade everything. A silent player (already settled) helps, but NPC voices are the hard core of "People and story". |
| FNV to FO4 | Player-side cross-engine conversion is tolerated on Nexus when it is free, GPL, and needs the CK. The scope that lasted is world geometry and placements, not actors, quests or scripts: the same order as our breadth-first plan. |
| Fallout London | A platform update can block a finished mod two days before launch. A store that cannot roll back (Epic) is a store you cannot support. Asking for a Steam login (the downgrader) was fragile because of Steam Guard. Installs broke on mod-manager INI overwrites, CC files, HD packs and wrong ESM sizes: a hash-checked preflight would have caught most. 20 testers was not enough. |
| Skyblivion | Public dates slipped (2025 to 2026) and a lead quit citing crunch. Navmesh "across all locations" was among the last blockers, which matches our own navmesh risk. |
| The Frontier | Contributor vetting and provenance per asset let them strip one person's work within days. Lack of a shared vision and poor management sank the rework. |
| Project Brazil, Miami, Cascadia | Self-imposed race deadlines and long silences are the norm. Regular public progress keeps communities alive. |
| OpenMW | Owning-the-data plus a GPL engine is legally clean but takes decades. Not available to us (CE2 closed). |
| Enderal | A small, tight team (14) shipped in 5 years with a narrow scope, compared with 70 to 100+ volunteers taking 8 to 14 years. |

## Risks
1. **Voice and audio conversion draws a legal objection** (high impact; likelihood medium). Capital Wasteland is a direct
   match: cross-engine conversion from a player-owned copy, Bethesda (same publisher), and voice licensing. The
   difference that helps us: we convert, never ship, and the player owns both games. Still, the one precedent says
   Bethesda staff saw this as a red flag.
2. **Game updates on two moving targets** (high likelihood). Starfield and FO4 both still get patches (FO4 next-gen
   2024). Fallout London shows one update can halt a release. Our build reads FO4 and writes for Starfield, so we face
   both, plus SFSE and Address Library lag.
3. **Schedule optimism** (high likelihood). Every comparable volunteer project slipped by years.
4. **Scope creep** (medium). The Frontier's scope cut and Skyblivion's shrinking minimum viable product.
5. **Install-support load** (high at release). Fallout London's first week was mostly install problems.
6. **Host capacity** (medium). The Frontier overwhelmed Nexus; Fallout London went to GOG for size. Our installer is
   small, but a build guide and a support channel are needed on day one.
7. **Provenance and contributor risk** (low to medium). One contributor's conduct forced The Frontier offline.
8. **Bethesda tolerance is a pattern, not a right** (already noted in project notes). Paid tiers would end it. Fallout
   London's Kickstarter collector's edition is the edge case to avoid copying.

## Questions for the framework

### New game
1. **Does the Vault 111 start use any FO4 voice lines (Nate/Nora, Codsworth, the Vault-Tec rep)?** Why it matters: the
   opening is heavily voiced, and Capital Wasteland's cancellation was "entirely related to audio". Options: silent
   start (settled for the player), subtitles-only NPC lines, converted voice from the player's copy (CW's banned
   pattern), or re-voice. Evidence: a written decision plus a question to Bethesda or Nexus staff. Who: owner decision,
   then a community contact.
2. **What does the new-game start do if Starfield updates and breaks the start quest overrides?** Why: Fallout London's
   next-gen lesson. Options: pin the Starfield version (can't on Steam except a read-only appmanifest, which Fallout
   London used), detect and refuse, or keep overrides minimal. Evidence: a diff of Starfield.esm start quests across two
   game versions. Who: offline research plus a PC probe.

### Door animations
3. **Do we wait for Starfield's own door animations or ship FO4 clips?** (settled: Starfield first). Precedent check:
   Skyblivion, Skywind and Fallout London all reuse the host game's animation set. Keep it. Who: no action, record in
   decisions.md.

### All interiors
4. **How do we prove interior conversion against a fixed source version, the way TTW checks BSAs before patching?** Why:
   TTW refuses unpatchable archives, and wrong `Fallout4.esm` sizes broke Fallout London installs. Options: a per-file
   hash table for every FO4 master and BA2 (1.10.163 first), or per-record hashes. Evidence: hash the depot. Who: PC probe.
5. **Navmesh for every interior: generated or converted?** Why: Skyblivion's final blockers included navmesh "across all
   locations". Options: convert FO4 navmesh, generate in the CK, or hybrid. Evidence: a timed run on 10 cells. Who: PC
   probe.
6. **What is our interior QA budget?** Fallout London had 20 testers and launched "barely playable". Options: automated
   cell-load cycling (the watchdog chain), a community beta, or both. Who: owner.

### Launcher
7. **Which FO4 versions does the launcher accept, and how do we treat next-gen?** Options: 1.10.163 only (Fallout
   London's choice, which forced a Steam login downgrader), or next-gen too. Do not ask for store credentials (ROADMAP).
   Evidence: hash tables for both versions and a record-level diff. Who: offline research plus a PC probe.
8. **Which stores do we support for FO4 and Starfield?** Epic could not roll back (Fallout London). Skyblivion rejects
   Epic and Game Pass as "encrypted and/or different". Starfield on Game Pass/Xbox PC has a protected folder (unresolved
   for our case). Evidence: file-access tests per store. Who: community contact plus offline research.
9. **xdelta-style patches or full rebuilds?** TTW ships binary deltas checked against known inputs. We rebuild from
   records. Option: a hybrid in which deltas fix known-bad source files. Evidence: rebuild time against delta size on one
   archive. Who: offline research.
10. **Separate the "base build" from "fix updates" like TTW and YUP?** Why: re-running a multi-hour build for each bug fix
    drives players away. Options: a stage cache keyed by converter version (already proposed), or a separate small fix
    package. Who: owner plus Implementation.
11. **What threads and thermal limits does the build use?** TTW added `-threads:1` after CPU overheating. Options: a
    configurable worker count with a safe default. Evidence: build telemetry. Who: Implementation.
12. **Do we build our own launcher UI or rely on MO2 or a third party like Overwolf?** Fallout London moved to an
    Overwolf launcher in 2025. Options: CLI plus a minimal UI, MO2 instance, or a custom app. Evidence: Overwolf's terms
    (ads, data). Who: owner decision after research.
13. **Linux and Proton support?** TTW's community tools filled the gap and then broke on installer changes. Options:
    design stages to be headless and scriptable, and document them for third-party managers. Who: owner.

### World and planet
14. **Is a TTW-style "merge DLC worlds into one" a precedent for Far Harbor and Nuka-World on one planet?** TTW merges two
    games' worldspaces into one game, but keeps separate worldspaces. Options: separate worldspaces reached by travel, or
    one planet surface. Evidence: CE2 worldspace limits. Who: offline research.
15. **What world scope can ship first?** FNV to FO4 shipped world, placements and landscape only, without actors, and has
    an audience. Option: a "walkable Commonwealth" release before people and story. Who: owner.

### People and story
16. **What is the voice policy for NPCs and companions?** Options: (a) convert the player's own files (CW's red flag),
    (b) subtitles only, (c) volunteer re-voice like Skywind's 300 actors or CW's 45,000 lines, (d) synthetic voice. That
    last option is a separate legal and ethical risk with voice actors' unions and is unresearched here. Evidence: ask
    Bethesda/ZeniMax community staff in writing; get legal opinion. Who: owner plus a community contact.
17. **Does `scripts/actors/codsworth_voice.py` stay a private test, or get gated off release builds until question 16 is
    answered?** Why: it is exactly the CW pattern. Who: owner, now.
18. **Lip-sync and face data.** Codsworth has no face; humans do. Converting `.lip` data carries the same question as
    audio. Who: offline research.

### Fallout systems
19. **Which Fallout systems do precedents rebuild rather than port?** Skywind rebuilt Morrowind's class system and
    probes on Skyrim's engine. The core pattern is reimplementation on host systems with SKSE plugins (Skywind FAQ).
    Implication: SFSE is likely for the Pip-Boy and VATS. Who: Research.
20. **What happens when SFSE lags a Starfield update?** Fallout London waited on "third-party partners" for the next-gen
    tools. Options: an SFSE-optional core with SFSE features as add-ons. Evidence: SFSE update-lag history. Who: offline
    research.

### Release and community
21. **Do we publish dates?** Every precedent slipped, and Skyblivion's date led to crunch claims. Options: milestones
    without dates (Skywind) or windows with a slip policy. Who: owner.
22. **How do we answer "is this legal?" on the release page?** Precedents: Skywind "will never charge"; TTW says nothing
    on its pages; Fallout London ran a Kickstarter for physical goods. Options: a short no-assets, own-both-games, free
    statement plus a takedown contact. Who: owner.
23. **Do we contact Bethesda before release, as Capital Wasteland did?** The contact killed CW v1, Skyblivion got
    conditions plus later praise, and Fallout London had "zero correspondence". Options: no contact, informal contact, or
    a written question. Risk either way. Who: owner.
24. **Where do we host?** FNV to FO4 shows Nexus accepts a cross-game converter tool. TTW moved to ModPub plus Discord.
    Fallout London used GOG for size. Who: owner plus a Nexus contact.
25. **How do we take human contributors?** Precedents run 14 to 100+ people with departments. The Frontier needed to
    strip one contributor's work. Options: a CLA or DCO, a per-asset provenance manifest, a code of conduct (already in
    the repo). Who: owner.
26. **What is the support model on day one?** Fallout London's first week was install support (INIs, CC files, wrong ESM).
    Options: a launcher that writes a diagnostic bundle (hashes, plugin list, INIs, crash log) for a single support form.
    Who: Implementation.
27. **How do we avoid The Frontier's failure modes (competing visions, poor management) with a team of AI agents?**
    Options: a single owner for direction (already true), decisions.md, and a public roadmap with previews of content.
    Who: owner.

### Tooling and testing
28. **Do we need the Starfield CK on players' PCs, as FNV to FO4 needs the FO4 CK?** It is a tolerated precedent, and it
    gives us a Bethesda-licensed tool for archive packing and compiling. Who: owner (MAY is settled; make it a launcher
    check).
29. **Which of TTW's and FNV to FO4's open code is reusable?** BSA# is MIT and FNV to FO4 is GPL-3: compatible with our
    GPL-3 binaries. Its mesh conversion targets FO4, not Starfield, so it is a reference only. Who: Research (licence and
    code read).
30. **Two-version regression tests.** Can we keep synthetic fixtures for both FO4 1.10.163 and next-gen record layouts so
    a FO4 update is caught offline? Who: Implementation.

### Cross-cutting
31. **Is the multi-game future (FO3, NV) blocked by Capital Wasteland's precedent?** FO3 into a newer engine is literally
    the cancelled project. Each future game needs its own legal check, starting with audio. Who: owner.
32. **What is our realistic time scale?** Precedents: Enderal 5 years with 14 people, Fallout London 5 years with about
    100, Skyblivion and Skywind 13+ years. Converting rather than remaking is our structural advantage. Measure it: hours
    per converted interior cell now, then extrapolate. Who: owner plus QA.

## Sources
- https://thebestoftimes.moddinglinked.com/ttw.html
- https://thebestoftimes.moddinglinked.com/intro.html
- https://thebestoftimes.moddinglinked.com/faq.html
- https://taleoftwowastelands.com/viewtopic.php@t=1031
- https://taleoftwowastelands.com/viewtopic.php@t=2111
- https://mod.pub/ttw/133/docs/25-faq-frequently-asked-questions
- https://github.com/jzebedee/bsasharp/
- https://bloody-disgusting.com/video-games/3536003/fallout-new-vegas-mod-tale-two-wastelands-updated-total-rebuild/
- https://www.warp2search.net/story/amethyst-mod-manager-v243-drops-ttw-installer-fix-and-wabbajack-beta/
- https://en.wikipedia.org/wiki/Fallout:_London
- https://www.techspot.com/community/topics/fallout-london-was-ready-for-launch-until-bethesdas-buggy-next-gen-update-broke-it.285631/
- https://www.pcgamesn.com/fallout-london/epic-games-store
- https://www.pcgamer.com/games/fallout/after-years-fallout-4s-much-anticipated-dlc-sized-mod-fallout-london-is-out-heres-how-to-install-it/
- https://www.gamestar.de/artikel/fallout-london-absturz-crash-technische-probleme,3417255,seite2.html
- https://www.gamingonlinux.com/2025/09/fallout-london-mod-gets-a-huge-upgrade-with-rabbit-pork/page=1/
- https://en.wikipedia.org/wiki/Skyblivion
- https://skyblivion.com/?p=10677
- https://skyblivion.com/faq
- https://hitmarker.net/news/oblivion-in-skyrim-mod-skyblivion-delayed-to-2026-to-provide-additional-development-time-1591206
- https://frvr.com/blog/news/former-skyblivion-dev-accuses-leads-of-rushing-the-long-in-development-mod
- https://en.wikipedia.org/wiki/Skywind
- https://tesrskywind.com/faq/
- https://wccftech.com/skywind-2026-milestone-quests-written-no-release-date/amp/
- https://kotaku.com/fallout-3-in-fallout-4-mod-canceled-after-team-talks-to-1823738281
- https://pcgamesn.com/fallout-4/fallout-4-fallout-3-capital-wasteland-mod
- https://www.pcgamer.com/au/capital-wasteland-the-fallout-3-remake-in-fallout-4-has-resumed-development
- https://www.gamerevolution.com/news/478241-fallout-4-capital-wasteland-mod-returns
- https://www.gamerevolution.com/news/433019-fan-project-fallout-4-new-vegas-shows-progress
- https://nexusmods.com/fallout4/mods/75425
- https://github.com/terry-haire/fnv-to-fo4
- https://techraptor.net/gaming/news/fallout-project-brazil-renamed-fallout-new-california-nearing-release
- https://kotaku.com/ambitious-new-vegas-modders-rush-to-finish-before-fallo-1710449586
- https://fallout.wiki/wiki/Mod:Fallout:_The_Frontier
- https://www.pcgamer.com/uk/fallout-mod-the-frontier-returns-after-stripping-out-content-from-disgraced-artist/
- https://www.gfinityesports.com/article/fallout-nuevo-mexico-modder-lessons-learned-from-frontier
- https://www.3djuegos.com/juegos/fallout-4/noticias/interes-fallout-4-tiene-poder-revivir-a-mods-que-parecian-muertos-2-anos-silencio-miami-reaparece-promesas-nuevo-trailer
- https://www.pcgamesn.com/fallout-cascadia/fan-game-update
- https://en.wikipedia.org/wiki/Enderal
- https://en.wikipedia.org/wiki/OpenMW
- Repo file read: scripts/actors/codsworth_voice.py (FO4 .fuz to .wem via Wwise);
  docs/ROADMAP.md §2 (Phase C launcher model)
- Not readable this run (HTTP 429 or search budget): beyondskyrim.org, openmw.org/faq, handbook.tesrskywind.com,
  Wccftech Fallout London interview, Hitmarker Skyblivion/Bethesda piece; Starfield total-conversion search not run.

## Wave 2 additions (2026-10-19)

Appended by a wave-2 research agent (Claude-cloud). The wave-1 text above is unchanged. Each item names the wave-1
gap or question it answers or changes. Tools: WebSearch plus TinyFish search/fetch (gnu.org and uesp.net blocked or
timed out for direct fetch; TinyFish worked). Nexus Mods pages were not fetched.

### W2-1. Beyond Skyrim (answers wave-1 §8 "Beyond Skyrim ... unresolved")
- **Structure.** "Beyond Skyrim is a collaboration between several modding teams. We're creating large continent
  expansion mods for The Elder Scrolls V: Skyrim." The site lists one released "Cyrodiil Pre-release" (Bruma, SE and
  LE) and a small teaser mod (Dawn's Venture / Cardana Pallo); recruitment and contact are via Discord ("This is where
  we are the most active"). **verified** ([beyondskyrim.org](https://beyondskyrim.org/))
- **Bruma release.** Released 2017-07-01 for Skyrim (LE), requiring "the base game plus all of the DLC"; "recreated
  from scratch", 70+ residents, "Over 24,000 lines of high-quality voiceover from a professional and semi-professional
  cast", 3+ hours of original music; SE and Xbox One promised later. **verified**
  ([Kotaku, 2017-07-01](https://kotaku.com/beyond-skyrim-mod-adding-giant-city-from-the-elder-scro-1796573865)).
  Kotaku's phrase "import all of Oblivion" is a journalist's gloss; the content was rebuilt, not imported.
- **Hosting on Bethesda's own platform.** A Bethesda Creations listing "Beyond Skyrim - Bruma" exists (search snippet
  dated 2021-11-14: "fully voiced mod with a wider scope than the ..."). **supported hypothesis** (the page did not
  render in our fetch; only the search snippet was read:
  [Creations 7559](https://creations.bethesda.net/en/skyrim/details/7559/Beyond_Skyrim___Bruma)). A Nexus SE page
  exists ([Nexus SSE 10917](https://www.nexusmods.com/skyrimspecialedition/mods/10917), search result only, not fetched).
- **Status in late 2025.** Self-identified team members on Reddit (2025-10-22): Bruma is still the only province
  release after 8 years; Cyrodiil "made the decision to commit to the entire province after Bruma"; Iliac Bay had a
  "big leadership shake-up in 2022" after management that "was... not great"; several projects have "entered voice
  acting"; staff leave for industry jobs; smaller item mods are spun off ("Wares of Tamriel"). **supported hypothesis**
  (forum posts by claimed members, not an official statement:
  [r/skyrimmods](https://www.reddit.com/r/skyrimmods/comments/1odnpmo/so_what_happened_to_the_beyond_skyrim_project/))
- **What this changes.** Confirms the wave-1 pattern (remade assets, re-voiced, multi-year), adds two lessons: an
  umbrella of semi-independent teams diverges and stalls; and a playable "pre-release slice" (Bruma) kept interest for
  years while the full scope did not ship. A commenter contrasts this with Tamriel Rebuilt's region-by-region drip
  releases (opinion, not evidence). For us: ship breadth in public slices (Phase 1 Vault 111 start, then interiors) not
  one big drop. The Bethesda-staff reference to "a Beyond Skyrim-style path" in Capital Wasteland (wave-1 §5) therefore
  means "remake everything and voice it yourselves", which our design (convert locally) is not.

### W2-2. Enderal's Steam edition (answers wave-1 §8 "Enderal's Steam standalone ... unresolved")
- **Release model.** *Enderal: Forgotten Stories* is listed on Steam as a free "Community-Made Mod" that "requires
  that you own The Elder Scrolls V: Skyrim"; Developer and Publisher: SureAI; released 2019-02-14; genre includes "Free
  To Play"; "Enderal is free and can be played by anyone owning a legal copy of TES V: Skyrim. (No DLCs are
  necessary.) It is developed non-commercially by SureAI". System notes: "Skyrim Classic needed ... Skyrim Special
  Edition does not work". It has Steam Achievements, Workshop and Cloud. **verified**
  ([Steam 933480](https://store.steampowered.com/app/933480/Enderal_Forgotten_Stories/))
- PCGamesN: "a mostly stand-alone package. You'll still need to own Skyrim ... but you can install and launch Enderal
  totally separately"; separate saves; "Both Enderal and its DLC ... will continue to be completely free". **verified**
  ([PCGamesN, 2019-02-08](https://www.pcgamesn.com/skyrim/skyrim-enderal-forgotten-stories-release-date))
- **Bethesda relation.** No public Bethesda agreement text was found. Steam's "Community-Made Mod" listing requires the
  base game's ownership check, which is a Valve-side programme; whether Bethesda signed off is **unresolved**.
- **What this changes.** A second distribution route beyond GitHub/Nexus exists for free mods that need the base game:
  a free Steam "mod" app with an ownership check. For us it would need two games owned (FO4 + Starfield), which Steam's
  single-parent mod listing may not express (**unresolved**; Steam's mod-listing rules not read). It also shows the
  value of installing *outside* the game folder with separate saves, which is the GAMMA-style launcher's aim.

### W2-3. Fallout: London launch problems, primary text (extends wave-1 §2)
- Team FOLON's own quick-start post on GOG's forum (read in full) tells players to: uninstall FO4 and delete
  `Documents\My Games\Fallout4` and `AppData\Local\Fallout4`; "Uninstall any mod managers and remove mods"; remove all
  `cc*` Creation Club files; on Steam install only the six named DLC and skip the HD texture pack; run the "Official
  FOLON Downgrader", which asks for the Steam "username + password ... so the downgrader can confirm your licence ...
  and access the depot" and may need Steam Guard authorisation "2 or 3 times"; launch FO4 once so the default launcher
  writes registry keys ("This can be the cause of various installation issues"). The installer writes the INIs and
  AppData itself ("you don't need a mod manager") and launches via `f4se_loader.exe`. **verified**
  ([GOG forum, FOLON quick start](https://www.gog.com/forum/fallout_london/fallout_london_quick_start_guide_common_bug_fixes/page1))
- Its FAQ shows which failures dominated: most answers are "Make sure you are opening f4se_loader.exe NOT
  Fallout4.exe" (crash after the train, cannot choose gender, manual-install bugs); HD pack or leftover mods causing odd
  textures; stale INIs causing the vanilla menu; F4SE closing because `iSize H/W` did not match the monitor; intro video
  stalling fixed by "Run this program as an administrator"; a stuck door worked around with `tcl`; a perk bug worked
  around with `player.removeperk`; "Try running at 1080p" for 4K. **verified** (same post)
- PCGamesN (2024-07-29): crashes and "extremely long loading times" on both Steam and GOG; patch promised via X with a
  known-issues list. **verified** ([PCGamesN](https://www.pcgamesn.com/fallout-london/crashes-patch-soon)). A 1.02
  patch with "hundreds of changes/fixes" followed (Wccftech 2024-10-20, search snippet only, **supported hypothesis**).
- **What this changes.** Sharpens wave-1's "hash-checked preflight" lesson into a concrete checklist our launcher's
  preflight should test before building: wrong entry exe, stale INIs, leftover mods/CC files in Data, optional HD
  packs, missing first-run registry keys, resolution mismatch, admin rights. And it adds one firm design rule: **never
  ask for a Steam password** (the Downgrader's Steam Guard loop was its top support issue); use Steam's own
  `steam://` / depot tooling run by the player instead (supported hypothesis).

### W2-4. Sim Settlements 2 and the voiced FO4 player (new; bears on "silent player by default")
- SS2's patch notes repeatedly fix *player* voice files: "Fixed a few player voice lines that were still using
  placeholder “robovoice” versions"; "Restored several missing player voice files"; "Fixed a player line ... that would
  play the male player voice for both male and female player characters". So SS2 ships player-voice audio of its own
  for its new dialogue, with male and female variants and a robotic placeholder during development. **verified**
  ([SS2 wiki patch notes](https://wiki.simsettlements2.com/getting-started/patch-notes))
- How the lines were made: community members say the player lines are "all from the game ... Some are spliced, but all
  are base game", that writers "looked at the lines they had available, and wrote dialogue around that", and that the
  team rejects AI voices. **supported hypothesis** (Reddit comments, not a team statement:
  [r/SimSettlements](https://www.reddit.com/r/SimSettlements/comments/1cdhpbx/player_va_question/)). A player-forum
  question on the SS2 site repeats the "taken from the original game" belief (not answered in the fetched text:
  [simsettlements.com](https://simsettlements.com/site/index.php?threads/changing-the-players-character-voice.26659/)).
  Mods that mute the player voice (Silent Protagonist, Mute Player Voice) are popular companions to SS2 (search results
  only).
- **What this changes.** For a *same-game* FO4 mod, reusing and splicing vanilla player lines is tolerated practice;
  it is not evidence that moving those lines into Starfield is acceptable (Capital Wasteland, wave-1 §5, is the
  cross-game precedent). It supports the settled "silent player by default" and adds a framework question: if a voiced
  player option ever comes, does it use only FO4's own player lines unchanged, converted on the player's PC, and never
  spliced into new sentences we authored (a spliced line is closer to a new derivative recording)? Owner decision plus a
  Bethesda question.

### W2-5. Skywind volunteer handbook (answers wave-1 "Not read: the Skywind volunteer handbook")
- The handbook is a team-only Google Sites hub: "the hub of all Skywind processes, manuals, and guides", editable by
  department heads, with the aim to "Bring our documentation all under one roof" and help new contributors "find the
  information they need, independently". **verified** ([handbook](https://handbook.tesrskywind.com/))
- **Bug tracking.** QA uses GitHub Issues with a template; "Search existing bugs first"; reports must be "easily
  reproducible by another tester"; labels `Confirmed`, `In Progress`, `Claim Fixed`, `Fix Fail`, `Invalid Issue`,
  `Known Shippable`, a `Crash` label, plus department labels; "Do NOT close the issue! All issues need to be retested
  before we can close them. A QA member will verify the proposed fix". **verified**
  ([bug reporting](https://handbook.tesrskywind.com/qa/bug-reporting))
- **Inactive leads.** A lead is inactive after three months of no response, missed meetings without apologies or
  neglected duties; they get a formal message and two weeks to reply, then lose lead permissions; returning does not
  restore the role automatically. "inactivity is not an issue if the lead team is informed". **verified**
  ([inactive lead guide](https://handbook.tesrskywind.com/misc/inactive-lead-guide))
- **Public progress.** "the ongoing health of the project relies on it"; anyone may post their own work to
  `#progress_updates` (WIP labelled), ask a lead before showing anything "big news or secret", never link a store
  ("this would be a conflict of interest"); about 650 Discord servers subscribe to the channel. **verified**
  ([sharing](https://handbook.tesrskywind.com/misc/sharing))
- **Engineering rules worth copying.** Quest rule 0: follow the original "as closely as possible ... things should not
  be changed ... for the sake of easier implementation"; dialogue filenames derive from the first 10 characters of the
  quest ID and 15 of the topic ID, so moving topics between quests breaks the voice pipeline unless prefixes match.
  **verified** ([quest design principles](https://handbook.tesrskywind.com/dev/Principles)). Scripting: avoid
  `Game.GetPlayer()` in favour of a PlayerREF property, avoid persistent ObjectReference properties, avoid polling and
  long `Wait()`. **verified** ([scripting best practices](https://handbook.tesrskywind.com/dev/lessons)); these are
  Skyrim-engine practices, applicability to Starfield is a supported hypothesis.
- **What this changes.** Our AGENTS.md labels (`ready`, `in-progress`, `needs-qa`) already match Skywind's flow; the gaps
  are a `Claim Fixed` → retest-before-close rule, a `Known Shippable` label for accepted engine bugs, and an
  inactivity rule for agents and humans (our watchdog already covers Claude). The filename rule is a direct warning for
  our FO4→Starfield dialogue conversion: Starfield voice file paths are keyed on record IDs, so any record renaming must
  be stable (supported hypothesis; check against Starfield's voice path scheme before People-and-story).

### W2-6. DMCA or takedown of a Bethesda cross-game port or converter (wave-1 legal table: unresolved)
- Searches for a ZeniMax DMCA against a cross-game port or converter (GitHub's DMCA repo, news, Nexus) found **no
  verifiable case** this session. What exists is policy, not enforcement: Bethesda's own help page lists removal for
  "using assets from other Bethesda games" and for mods that "circumvent the need to purchase add-on content".
  **verified** ([Bethesda help 34803](https://help.bethesda.net/app/answers/detail/a_id/34803/~/why-was-my-mod-removed%3F)).
  Detail in legal-policy.md "Wave 2 additions". Status remains **unresolved** (absence of evidence, not evidence).

### W2 new questions for the framework
1. **Release and community.** Do we ship public slices (Vault 111 start, then interiors) like Bruma, and never one
   "full Commonwealth" drop? Evidence: W2-1. Owner decision.
2. **Launcher.** Will the launcher ever need the player's store credentials? Proposed rule: never; detect, instruct,
   refuse. Evidence: W2-3. Owner decision.
3. **Launcher.** Which preflight checks from FOLON's FAQ (entry exe, INI freshness, CC files, HD pack, first-run
   registry keys, resolution, admin rights) map onto Starfield + SFSE? Offline research + PC probe.
4. **People and story.** If a voiced-player option is ever offered, is it FO4 player lines unchanged only, or are
   spliced lines allowed? Evidence: W2-4 vs Capital Wasteland. Owner decision + Bethesda question.
5. **Tooling and testing.** Adopt Skywind's `Claim Fixed`/retest-before-close and `Known Shippable` labels? Evidence:
   W2-5. Owner decision.
6. **Cross-cutting.** Is there a stable naming scheme so converted dialogue and voice paths survive re-builds? Evidence:
   W2-5 filename rule. Offline research on Starfield voice paths.
7. **Release and community.** Is a free Steam "Community-Made Mod" listing (Enderal model) ever an option for a tool that
   needs two games? Evidence: W2-2. Offline research on Steam's mod-app rules; Valve contact.

### W2 sources
- https://beyondskyrim.org/
- https://kotaku.com/beyond-skyrim-mod-adding-giant-city-from-the-elder-scro-1796573865
- https://creations.bethesda.net/en/skyrim/details/7559/Beyond_Skyrim___Bruma (snippet only)
- https://www.reddit.com/r/skyrimmods/comments/1odnpmo/so_what_happened_to_the_beyond_skyrim_project/
- https://store.steampowered.com/app/933480/Enderal_Forgotten_Stories/
- https://www.pcgamesn.com/skyrim/skyrim-enderal-forgotten-stories-release-date
- https://www.gog.com/forum/fallout_london/fallout_london_quick_start_guide_common_bug_fixes/page1
- https://www.pcgamesn.com/fallout-london/crashes-patch-soon
- https://wccftech.com/fallout-londons-patch-1-02-is-out-now-with-hundreds-of-fixes-and-a-specific-focus-on-graphical-improvements/ (snippet only)
- https://wiki.simsettlements2.com/getting-started/patch-notes
- https://www.reddit.com/r/SimSettlements/comments/1cdhpbx/player_va_question/
- https://simsettlements.com/site/index.php?threads/changing-the-players-character-voice.26659/
- https://handbook.tesrskywind.com/ ; /qa/bug-reporting ; /misc/inactive-lead-guide ; /misc/sharing ; /dev/Principles ; /dev/lessons
- https://tesrskywind.com/volunteer/
- https://help.bethesda.net/app/answers/detail/a_id/34803/~/why-was-my-mod-removed%3F
