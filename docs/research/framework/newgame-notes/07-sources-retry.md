# 07: Retry of sources the earlier agents could not read (HTTP 429)

Written 2026-10-19 by Claude (research agent, new-game phase). Web research only: no game, PC or project GitHub was
touched. Labels follow docs/ai/research-log.md: **verified** = a primary source quoted, with URL; **supported
hypothesis** = secondary source, a search-result snippet, or an inference from a primary one; **unresolved**.
"Verified" means "the page says so", not "we checked the records". Nothing here was tested in game.

## How the pages were read

- WebFetch refused help.bethesda.net with HTTP 429 on the first try and told me not to retry, so every page below was
  read with the TinyFish fetcher (one or two URLs per call, spaced out). UESP's Starfield pages were read as **raw
  wikitext** (`starfieldwiki.net/w/index.php?title=...&action=raw`), because the rendered page collapses the stage table.
- Nexus pages sometimes timed out. Where a retry also failed I used a mirror: the Wayback Machine (Nexus wiki), the
  author's own release thread (AFK Mods for Live Another Life), or search-result snippets (marked as such).
- Third-party GitHub: I read two public pages read-only (Community Patch issue 957 and the RAS repository front page).
  I did not open the RAS source files. The project's own GitHub was not touched.

Could **not** read, even with mirrors: Realm of Lorkhan's Nexus page (SSE 18223, two timeouts; snippets only),
Nexus SSE 111029 (timeout; I could not tell what mod it is), Live Another Life's Nexus page (timeout; the author's
AFK Mods thread was read instead), the live Nexus wiki (bot-blocked; Wayback copy from 2025-01-08 read), Wynter's Roll
Your Own Start Creation page (JavaScript only, no text), the Address Library files tab (timeout), and any page that
describes `StartupQuest_DO` other than the No Ship Fast Start page (one search found nothing).

---

## 1. Bethesda's rules and Bethesda's actions on cross-game assets

| # | Claim | Label | Source |
|---|---|---|---|
| 1.1 | Bethesda.net Modding Guidelines, "Examples of why Mods are removed": "**Do not upload mods using third-party content (licensed properties, content from other games, and other trademarked properties). This includes using assets from other Bethesda games.**" Also: "Do not upload mods or mods taking content from other mods unless you have permission from the creator." and "Do not create mods that allow users to circumvent the need to purchase add-on content." | verified | https://help.bethesda.net/app/answers/detail/a_id/51731/ (title "Bethesda.net Modding Guidelines - Mods/Creations", author Bethesda Support; no date on page) |
| 1.2 | Scope: the rule is written for uploads to Bethesda.net (Mods/Creations). It does not mention installers or files generated on the user's own PC. Whether Bethesda applies it to a converter that ships no Bethesda files is not stated. | supported hypothesis (reading of 1.1) | same |
| 1.3 | Bethesda.net "Porting Rules" (answer 55219) is only about re-uploading **other people's mods** to Bethesda.net (credit, link, public permission; private-chat permissions not accepted for ports created after 12 March 2023). Nothing about game assets. | verified | https://help.bethesda.net/app/answers/detail/a_id/55219/~/porting-rules---mods---bethesda.net |
| 1.4 | Nexus Mods wiki "Porting content": "Porting **assets** (textures, meshes, sounds, etc.) from one game to another is generally not allowed on Nexus Mods, unless the ... rights holder has explicitly given permission". Table row for "Zenimax: Bethesda Game Studios, ... id Software, ..." : "**Does not allow porting of assets under any circumstances.**" Source column: "Terms of Service". General rules include "You must own a legal copy of the game(s) the assets are ported to and from" and "may not be for commercial purposes". | verified (Wayback copy) | https://web.archive.org/web/20250108164810/https://wiki.nexusmods.com/index.php/Porting_content (oldid 164038; live page bot-blocked) |
| 1.5 | Nexus staff, Fallout Modathon 2025 rules: "No porting Bethesda assets into other games." | verified | https://www.nexusmods.com/fortresscraftevolved/news/15391 (23 Oct 2025) |
| 1.6 | Capital Wasteland (FO3 in FO4), cancelled March 2018. PCGamesN: "The Fallout publishers didn't mandate the mod be shut down"; the issue was FO3 voice files: distributing them was "a definite legal no-no", and letting players "rip from their own copies of Fallout 3 was similarly untenable". Mod lead NafNaf_95 (via Kotaku): Bethesda "can't grant the rights to use the game's voice acting, since it's licensed rather than owned"; "Bethesda didn't technically shut us down. But a few members of staff heavily hinted at our methods being illegal."; a lawyer said it "was sketchy as all hell". | verified (as reported; Bethesda itself is not quoted) | https://www.pcgamesn.com/fallout-4/fallout-4-fallout-3-capital-wasteland-mod |
| 1.7 | Tale of Two Wastelands: "Bethesda personally asked Nexus to not host TTW in the past, and we're still not allowed to host it there in the present date." | supported hypothesis (TTW team forum, search snippet only; no Bethesda text) | https://taleoftwowastelands.com/viewtopic.php@t=7850 |
| 1.8 | Skyblivion FAQ: needs Skyrim SE **and** Oblivion GOTY Deluxe (Steam or GOG); custom installer that "will download and move the necessary files"; not on Creation Club or consoles; "Bethesda has been very supportive of Skyblivion even after the remaster"; "no plans to support any of the newer voice lines or assets from the remaster due to legal restraints"; you start as in Oblivion and travel to Skyrim's worldspaces "may not function". The FAQ does **not** state the "replace 100% of assets" requirement that note 02/05 cite from Wikipedia. | verified (FAQ text) | https://skyblivion.com/faq/ |
| 1.9 | No primary Bethesda statement on Skyblivion, Skywind, TTW or Capital Wasteland was found; every account is the modders' or the press's. | unresolved | searches in this session |
| 1.10 | Recent enforcement (Oct 2026): Bethesda reportedly sent a cease-and-desist over "Fallout New York", a browser game "made entirely with Claude Opus 5.5" in five days; it was taken offline. No lawsuit reported. It was a standalone game, not a mod that needs the owned game. | supported hypothesis (press report) | https://www.tweaktown.com/news/113882/bethesda-shuts-down-vibe-coded-fallout-project/index.html (3 Oct 2026) |

Reading for us (**supported hypothesis**): Bethesda.net/Creations and Nexus both bar uploading assets taken from
another Bethesda game, and Nexus says Zenimax allows it "under any circumstances" never. A build-on-the-user's-PC
converter that ships no Bethesda files (TTW model) is not covered by either text, but has no written blessing, and TTW
itself was kept off Nexus. Voice is the sharpest edge (Capital Wasteland). The AI-built Fallout takedown shows Bethesda
is watching AI-made Fallout projects right now; our repository being public and AI-built matters.

---

## 2. UESP (starfieldwiki.net) Starfield pages

### 2.1 One Small Step (MQ101): stage table, verbatim from the raw wikitext

Source: https://starfieldwiki.net/w/index.php?title=Starfield:One_Small_Step&action=raw — **verified** (wiki text;
"Mission Comment" values look like the CK stage notes, i.e. datamined, but the wiki does not say so).

Header: ID `MQ101`; rewards "Constellation Pack, Vasco available as companion, the Frontier, membership in
Constellation, Lodge Key"; NG+ rewards "Cutter, leveled weapons, 5 Med Packs"; next mission The Old Neighborhood.
Starts "May 7, 2330".

Stages that matter for a skip:

| Stage | Comment (verbatim) |
|---|---|
| 0 | Always Run on Start |
| 5 | Preload Vectara worldspace |
| 7 / 8 / 9 | Start Elevator / Elevator has stopped / Player is allowed to move |
| 60 | Player wakes up |
| 63 | Fire CharGen after Heller's Animation (or failsafe) |
| 100 | Player is in CharGenFurniture |
| 105 | Player finishes Character Gen |
| 155 | START TUTORIALS |
| 302 | Player starts talking to Barrett for watch scene, disable POV shift |
| 305 | Player needs to take the Watch |
| 310 | enable look controls again |
| 400 | Achievement unlocked - Enter Space for the First Time |
| 500 | **DEBUG 10 - Encounter over, skip to New Atlantis** |
| 606 | Register for when player opens the map |
| 627 | TUTORIAL - Scanner |
| 900 | **Block fast travel to everywhere but Jemison and Kreet** |
| 910 / 920 / 930 | Tutorial - Monocle Menu / Surface Map / Player fast travels |
| 1000-1020 | Data Menu, Missions Menu, Galaxy Menu tutorials |
| 1325 / 1335 | Start Ship Services Scene / Player talked to Ship Services NPC |
| 1510 | Always update objectives |
| 1750 | Dialogue to set up MQ103 valid |
| 1800 | fin, Quest Complete |
| 1810 | Player leaves the Lodge After quest complete |
| 2000 / 2100 | STARBORN PATH - Start / Quest Complete (fin) |
| **9000** | **Run on Stop** |

Also verified on the page: Barrett's Chronomark watch "becomes your compass, Oxygen bar and planet name HUD element"
and Analysis mode shows temperature, oxygen and gravity; and at completion "Board and Lodging, Dream Home, Kid Stuff,
and The Old Neighborhood begin immediately".

Consequences (**supported hypothesis**, from the table): (a) `Quest.Stop()` on MQ101 runs stage **9000** "Run on
Stop", so whatever that fragment does happens to us; (b) stage 900 *sets* a fast-travel block, so stopping MQ101 before
900 never sets it, but stopping it after 900 and before 1800 may leave it set; (c) chargen is driven by stage 63 with
its own "failsafe"; (d) the HUD compass, O2 bar and planet name come from an item (the watch), not from a flag.

### 2.2 MQ101Debug: what is known now

| # | Claim | Label | Source |
|---|---|---|---|
| 2.2.1 | `MQ101Debug` is GLOB **000A7D31**. Wiki procedure: at the **main menu** open the console, `SET 000A7D31 TO 8`, press **New Game**: "After a short loading screen you will be standing in the New Atlantis spaceport". No mod involved. | verified (wiki how-to) | https://starfieldwiki.net/wiki/Starfield_Mod:Papyrus_debugging_with_VS_Code |
| 2.2.2 | Vanilla condition form `POE_SustenanceAllowed [002EEA4D]` contains `Subject.GetGlobalValue(MQ101Debug[GLOB:000A7D31]) <> 0`; the Community Patch replaced it with `Subject.GetStageDone(MQ101 [QUST:00003448], 9000 Run on Stop) = 1` because sustenance was off in some NG+ universes. | verified (Community Patch maintainer comment, game 1.11.36) | https://github.com/Starfield-Community-Patch/Starfield-Community-Patch/issues/957 |
| 2.2.3 | No Ship Fast Start calls the same form `PEO_SustenanceAllowed` and overrides it "with a custom GlobalVariable set to 1"; it also restores Cruise Mode by script. The two spellings (POE/PEO) disagree; form id 002EEA4D is the reliable key. | verified (both pages); exact EditorID unresolved | https://www.nexusmods.com/starfield/mods/15092 |
| 2.2.4 | SKK Fast Start stop code: "[ 1 ] New new game start GlobalVariable MQ101Debug is not set to 8 (a hard edit by the ESM)". Crimson Start: "Anything that touches the base game startup sequence in MQ101 or MQ101Debug will stop this from working." | verified (search snippets of the Creations and Nexus pages) | https://creations.bethesda.net/es/starfield/details/78e0e1e2-0016-4d9c-9ced-0175d6b73c41/SKK_Fast_Start_New_Game__Starfield_ ; https://www.nexusmods.com/starfield/mods/6869 |
| 2.2.5 | What values 1, 2, 5 and 10 do, and what "DEBUG 10" in stage 500's note refers to: not documented anywhere I could read. "DEBUG 10" cannot simply mean MQ101Debug = 10, because the repo verified MQ00 writes 10 on every normal new game and normal games do not skip to New Atlantis. | unresolved | - |

Consequences (**supported hypothesis**): a non-zero MQ101Debug set **before** New Game survives into the new game and
picks the start, so the repo's "MQ00 stage 10 writes 10" must be conditional or must run only on the default path.
And because vanilla sustenance checks MQ101Debug <> 0, a start that keeps MQ00 from ever running (a `StartupQuest_DO`
override) leaves the global at 0 and silently turns sustenance off; that is why No Ship Fast Start overrides the form.

### 2.3 Main Quests and New Game Plus

| # | Claim | Label | Source |
|---|---|---|---|
| 2.3.1 | Act 1: One Small Step, The Old Neighborhood (with The Empty Nest, Into the Unknown, Back to Vectera), All That Money Can Buy, Starborn. Act 2: Further Into the Unknown, Short Sighted, No Sudden Moves, High Price to Pay, Unity, In Their Footsteps. Act 3: Unearthed, Revelation, One Giant Leap. NG+ Act 4: Among the Stars ... Foreknowledge. NG+ alternate starts are separate quests **MQ401a to MQ401j** (Vasco, Duplicate You, Hunter, Children, etc.). | verified (wiki) | https://starfieldwiki.net/w/index.php?title=Starfield:Main_Quests&action=raw |
| 2.3.2 | NG+: you "appear in a new universe above Vectera" with a new version of One Small Step that points you to the Lodge; keep name, appearance, background, traits ("Able to be changed"), level, skills, powers, research; lose database, visited-location knowledge (fast travel needs revisits), Quantum Essence. | verified (wiki) | https://starfieldwiki.net/w/index.php?title=Starfield:New_Game_Plus&action=raw |
| 2.3.3 | Bug: "On some alternate universe you will be locked out of saving or even accessing your inventory"; workaround console `SetInCharGen 0 0 0` (disables achievements). | verified (wiki bug note) | same |

The last row is Bethesda's own code leaving the chargen flag set after a non-standard start: the exact risk our
start runs if we call ShowRaceMenu ourselves (**supported hypothesis**).

### 2.4 StartupQuest_DO
The only public description is No Ship Fast Start's: "The alternate start overrides StartupQuest_DO, redirecting
startup from MQ101 to a custom controller quest. MQ101 is left available for later progression." **verified** (that
page, section 3). Its form id, flags, and whether it starts MQ00 or MQ101 directly: **unresolved** (needs a read-only
look at Starfield.esm).

---

## 3. Starfield alternate-start mods

### 3.1 No Ship Fast Start (LeavingLasOrleans), Nexus 15092, v2.0 (updated 28 Sep 2026)
**verified** (https://www.nexusmods.com/starfield/mods/15092):
- "The alternate start overrides StartupQuest_DO, redirecting startup from MQ101 to a custom controller quest. MQ101 is
  left available for later progression. Skipping the tutorial requires suppressing quest triggers that can still fire
  later, such as when traveling to Kreet."
- "Starfield expects the player to have a home ship or the ship services interface won't work." Fix: "a hidden,
  disabled, partless ship ... assign[ed] as the home ship through SQ_PlayerShip", with `CannotBeModifiedShipKeyword`
  and `DisableInventoryTransfer`; an `OnHomeShipSet` handler removes it later.
- "This mod manually activates Sustenance and Cruise Mode, which are otherwise activated by the tutorial."
- "The main quest tutorial is skipped and the main quest is idle. If you want to reactivate the main quest, just go to
  the Lodge." v2.0 "suppresses several of the lingering tutorial triggers that previous versions had left active" and
  "might not be compatible with existing saves". A choice after the Unity: default post-Unity start or start again.

### 3.2 First We Crawl (Legacy, parts based), Nexus 15102, v2.5 (updated 5 Oct 2026)
**verified** (https://www.nexusmods.com/starfield/mods/15102): the no-ship start is the standalone 15092; superseded
by a skill-based version. Known: "You're allowed to fast travel to points beyond your ship's range ... I haven't found
any real solution". Uses `SpaceshipGravJumpDistancePerFuel`. The note-01 line "2.3 hopefully stopped the tutorial
restarting at Kreet" is not on the current page (**unresolved**; possibly in the changelog).

### 3.3 Roleplayers' Alternate Start (ZeCroque), Nexus 15094, v1.2.4 (updated 24 Sep 2026)
**verified** (https://www.nexusmods.com/starfield/mods/15094 ; same text at https://github.com/ZeCroque/RoleplayersAlternateStart):
- "relies primarily on hooks and replacers, keeping vanilla quest edits to an absolute minimum". Credits: SKK Fast
  Start "a good scripting resource to make my own hooks to MQ", and Wynterhawk's Creation **Roll Your Own Start** "which
  learnt me a proper way to edit the new game logic that have been crucial for the 1.1.0 update".
- **Open source, GPL-3.0**, source on GitHub (repo above). Tools: CK, SF1Edit, Champollion, xVASynth.
- Start area: "a custom area inspired by the Unity". "The vanilla 'One Small Step' quest is skipped entirely. As a
  result, events depending on it will not occur (e.g. the SSNN interview ...)"; it can be marked complete from a
  "Narrative Adjustments" terminal.
- Traits: parents "will only have dialogs after you join Constellation"; the Adoring Fan is held until "Echoes From
  Vectera"; "The dream home quest will trigger at the start of the game (you need to complete 'One Small Step' in
  vanilla)".
- "Auto Hide HUD and Widgets - SFSE ... will not work until you complete 'One Small Step'". "Starborn Trait by IgnusT:
  incompatible". "On existing saves, the mod will de-activate itself until NG+". Esm is a **mid (medium) master**.
- Planned fix list of leftover dialogue (Yumi, SysDef arrest scene, parents, Lin's "Dusty", Sarah, Vladimir, Walter's
  "rock breaker", Cora, Ebbside Strikers, Revelation flashbacks): the long tail of skipping MQ101.

### 3.4 SKK Fast Start New Game (5971) and Crimson Start (6869)
Not re-fetched (note 01 read them). Stop-code text re-confirmed through search snippets (2.2.4). **verified** (snippet).

### 3.5 Mod 15088 (what it actually is)
"Jonpaul Deschain - Chargen Preset": a face preset that needs the SFSE plugin **CharGenMenu**, Extended Facial
Sculpting and Starfield Hair And Beards; installed to `Documents\My Games\Starfield\SFSE\Plugins\Chargen\Presets` and
"Select the preset within the Chargen menu". **verified** (https://www.nexusmods.com/starfield/mods/15088). It is not a
start mod. Relevance: an SFSE preset format for player faces exists (**supported hypothesis** that it could carry a
converted FO4 face; format not read).

### 3.6 Expanded Backgrounds (Barsoomchild), Nexus 15724, v0.3.0
**verified** (https://www.nexusmods.com/starfield/mods/15724): reworks vanilla background records to five skills each
and adds six; ships an edited `chargenmenu.swf` (CK + JPEXS) so five skills show; "any loose files editing the
chargenmenu swf will win over the archived version"; "visually incompatible with mods that modify chargenmenu.swf";
patch for CharGenMenu; "There should be no issue with mods that add additional backgrounds"; v0.3.0 "adds duplicated
vanilla background conditioned dialog for all added backgrounds"; built on game 1.15.222.
**supported hypothesis**: the menu lists background records without a hand-kept list (new ones just appear), and
background dialogue is conditioned on the background perk, so new Fallout backgrounds would get no Starfield lines.

### 3.7 Roll Your Own Start (Wynterhawk), paid Creation
Creation page empty to my fetcher. Snippets: "immersive alternative starts that let you begin the game's main quest at a
time of your choosing or ignore it entirely" (https://creations.bethesda.net/en/starfield/details/c27a121a-c565-4ae0-9394-c58952c98f86/RYOS_Roll_Your_Own_Start);
sold for 600 credits, "achievement friendly" (YouTube review snippet). Mechanism: **unresolved**.

---

## 4. Skyrim alternate starts

### 4.1 Alternate Start - Live Another Life (Arthmoor)
Read from the author's release thread (Nexus page timed out). **verified**
(https://www.afkmods.com/index.php?/topic/4638-relz-alternate-start-live-another-life/):
- Main-quest entry: innkeeper rumour; or go to Helgen; or via the Civil War at Whiterun. Failsafe, quoted: "If you
  somehow avoid all the guards and get into Dragonsreach without ever hearing about Helgen, the MQ will be force-started
  upon entering the main hall. Sorry, but this failsafe is required because it is not possible to advance the Civil War
  until Bleak Falls Barrow and Dragon Rising have been completed."
- Gate guard made essential, resurrected if dead while the controlling quest runs, and moved into place when needed
  (v4.0.2): failsafes on the actors as well as the quest.
- Incompatible with mods editing MQ101 / MQ102 / WERoad01 or scripts `QF_MQ101_0003372B`, `QF_MQ102_0004E50D` and
  several `TIF__` fragments; loose copies of those scripts "will break the quest controls". "Become High King of Skyrim
  - Edits MQ101 ... make sure it loads BEFORE ... so that it won't cause the 'new game' menu to get stuck."
- "Nothing happened. I tried to start a new game and ended up going to Helgen. Again. Make sure the mod is actually
  activated." (a silent fall-back to the vanilla start, the FOLON lesson again).
- "Upgrading a save when you're still in the prison cell is not supported"; a version number is tracked on new game
  and a warning shown (v4.0.2a fixed false warnings).
- "the GetFormFromFile() Papyrus function cannot return a result for a non-persistent reference".
- Whiterun map markers are turned off until the gate scene; "Please DO NOT console your way around them."

### 4.2 Realm of Lorkhan
Correct page is **SSE 18223** ("Realm of Lorkhan - Freeform Alternate Start", v4.2), not 8328 (see 4.3). Page timed out
twice. Snippets only (**supported hypothesis**): "You are transported to the 'Realm of Lorkhan' as soon as you press NEW
GAME" (Creations listing); "I've edited dialogue to remove references to Helgen on Jarl Balgruuf, Irileth, Ulfric, and
General ..."; "Wherever you choose, you simply make your way back to Helgen" to start the main quest.

### 4.3 Nexus SSE 8328 is RASR, not Realm of Lorkhan
**verified** (https://www.nexusmods.com/skyrimspecialedition/mods/8328): "RASR - Random Alternate Start Reborn SE and
VR": "Custom empty CharGen location"; "Wait Timer options to allow setting up mods ... before randomly warping to a
start location"; main quest "picked up by investigating rumors of dragons near Helgen"; known issue: "Mods that alter
the game's time scale may cause the 'double menu bug'"; move to the bottom of the load order if the Whiterun gate guard
or Jarl dialogue breaks.

### 4.4 Skyrim Unbound
Nexus SSE 111029 timed out; I could not tell which mod it is. Search shows Skyrim Unbound Reborn at SSE 27962 and a
Creations listing. Secondary source (**supported hypothesis**): Unbound is set up through an MCM before starting and
"lets you toggle dragons, soul absorption, and word walls, making it possible to disable the main quest entirely"
(https://bandurart.com/skyrim-alternate-start/). A Reddit title reports a player who "visited Helgen and Dragonsreach,
but nothing seems to start the quest line" on Xbox (no detail read).

---

## 5. Nexus porting policy
See 1.4 and 1.5 (verified). The Nexus wiki also lists other publishers that allow porting (CDPR within The Witcher,
Konami, GSC) and those that do not (Zenimax, Microsoft Xbox Game Studios, Take-Two, Square Enix western studios,
Larian). Since Microsoft owns Zenimax, both rows point the same way. **verified** (Wayback copy).

---

## 6. Address Library for SFSE and Starfield CK command line

| # | Claim | Label | Source |
|---|---|---|---|
| 6.1 | Address Library for SFSE Plugins (meh321): version **22**, last updated **13 June 2026**; "a database that helps make DLL mods version independent"; `.bin` files go in `Data/SFSE/Plugins/`; file naming `versionlib-<game>.bin` for Steam, `versionlib-<game>.1.bin` for the **MS Store** build ("the 1 at the end ... says it is MS store"). | verified | https://www.nexusmods.com/starfield/mods/3256 |
| 6.2 | Current public build **1.16.244** (Steam build 23518663, 11 Jun 2026); SFSE 0.2.21 the same day; Address Library v22 two days later. 17 of 17 SFSE updates landed within two days of a patch. "Creations installed from the in-game menu, and mods that are only plugins and assets, don't use SFSE and keep working." | supported hypothesis (third-party tracker) | https://modlag.com/starfield |
| 6.3 | Starfield CK command line: `creationkit.exe -GenerateWorkshopIcons:<YourModName>.esm`, and `-GenerateShipBuilderIcons:` / inventory equivalents, run from the Starfield folder; output `.tif` that Asset Watcher (`Tools\assetwatcher.exe`) converts to `.dds`. One user saw no output from the command line at all. | supported hypothesis (community post, July 2024) | https://www.reddit.com/r/starfieldmods/comments/1e3tc8r/how_to_add_menu_images_for_your_constructable/ |
| 6.4 | Any official list of Starfield CK switches (LipGen, SEQ, precombines, ESL/medium conversion): none found. FO4/Skyrim switches such as `-GenerateSEQ:` and command-line LipGen exist for those CKs. | unresolved for Starfield | searches this session |
| 6.5 | CK ships a VS Code Papyrus extension (`Starfield\Tools\VSCodePapyrusAddon\vscodepapyrus-1.6.2.vsix`) with a live remote debugger: `[Papyrus] iRemoteDebuggingPort=20548, bEnableRemoteDebugging=1, bLoadDebugInformation=1`, log `Logs\Script\RemoteDebugger.0.log`. | verified (wiki) | https://starfieldwiki.net/wiki/Starfield_Mod:Papyrus_debugging_with_VS_Code |

---

## Questions for our design

1. **Does MQ00 write 10 to MQ101Debug only when it is 0?** Why: the wiki shows a value of 8 set before New Game survives
   into the game (2.2.1), which contradicts an unconditional write. How: offline, re-read `QF_MQ00_00005790.psc` in full
   and MQ00's stage-10 conditions; one in-game check (`GetGlobalValue MQ101Debug` right after New Game with 8 set).
2. **What does MQ101 stage 9000 "Run on Stop" do?** Why: our option A calls `Quest.Stop()` on MQ101, which runs it.
   How: offline read of the stage-9000 fragment in `qf_mq101_00003448.psc`.
3. **Do we let MQ00 run to stage 10 or prevent it (StartupQuest_DO override)?** Why: vanilla sustenance needs
   MQ101Debug <> 0 (2.2.2); preventing MQ00 leaves it 0 and sustenance off. How: offline read of `POE_SustenanceAllowed`
   (002EEA4D) and its users; then owner decision on whether sustenance exists in our game.
4. **What is `StartupQuest_DO` (form id, flags, what it starts)?** Why: the cleanest documented redirect (No Ship Fast
   Start) overrides it instead of racing MQ101. How: offline read of Starfield.esm with our reader or xSFEdit, read-only.
5. **Which MQ101Debug value, if any, gives a clean "no intro" state we can reuse?** Why: 8 lands in New Atlantis with
   no mod; another value may land nowhere special. How: offline grep of every MQ101Debug reader, then one in-game run
   per value on a throwaway profile (Claude only, per AGENTS.md).
6. **Is the fast-travel block (stage 900) ever set in our start, and what clears it?** Why: stopping MQ101 between 900
   and 1800 may leave fast travel restricted. How: offline read of the stage-900 and stage-1800 fragments.
7. **Do we copy the HUD compass / O2 / planet name from the Chronomark watch?** Why: MQ101 stage 305 gives the watch
   that "becomes your compass, Oxygen bar and planet name HUD element". How: in-game test of the HUD with and without the
   watch item; owner decision on a Pip-Boy stand-in.
8. **How do we guarantee the chargen flag is cleared after our ShowRaceMenu?** Why: Bethesda's own NG+ alternate
   universes leave saving and inventory locked (`SetInCharGen 0 0 0` fix, 2.3.3). How: offline read of what MQ101
   stages 63-105 call; in-game check that saving, waiting and inventory work after our menu.
9. **Do we give the player a placeholder home ship?** Why: "Starfield expects the player to have a home ship or the ship
   services interface won't work"; No Ship Fast Start had to fake one. How: owner decision (ship services in the
   Commonwealth or not), then an in-game check of any ship-dependent menu.
10. **What do Dream Home, Kid Stuff, Board and Lodging and The Old Neighborhood do if MQ101 never reaches 1800?** Why:
    UESP says they all begin at MQ101's completion; RAS had to trigger Dream Home itself. How: offline read of their
    start conditions; owner decision on hiding those traits.
11. **Do we publish a "vault exit" stage contract and a version number, LAL style?** Why: LAL tracks a version on new
    game and warns on saves made in the start cell; FO4 mods hang on MQ102 stages. How: owner decision, then an offline
    unittest of the guard logic.
12. **Which failsafes do we need for players who route around the elevator (LAL's Dragonsreach rule)?** Why: LAL
    force-starts the main quest and even resurrects a critical actor. How: design list from our quest's state machine;
    offline tests.
13. **Does our quest resolve any non-persistent reference with GetFormFromFile?** Why: Arthmoor states GetFormFromFile
    "cannot return a result for a non-persistent reference" (Skyrim); SKK reported wrong results on small ESMs. How:
    offline check that every ref our script looks up is persistent in our plugins.
14. **Can we read RAS's GPL-3.0 source to see how it hooks the new-game logic?** Why: it is the only open-source Starfield
    alternate start and credits RYOS for "a proper way to edit the new game logic". How: owner decision (GPL-3.0 means
    copying code would make our scripts GPL; reading it for ideas is fine), then an offline read.
15. **What is our public stance on cross-game assets?** Why: Bethesda.net bans assets "from other Bethesda games";
    Nexus says Zenimax never allows porting; TTW was kept off Nexus; Capital Wasteland died on voice. How: owner
    decision, written in docs/ai/decisions.md and the README (no hosting of converted output anywhere; Creations never).
16. **Do we convert or reuse FO4 voice files at all in the first release?** Why: voice is the legal edge Bethesda says it
    cannot license (Capital Wasteland). How: owner decision; possibly legal advice.
17. **Does the repository's AI-built status change our risk?** Why: Bethesda reportedly sent a C&D to an AI-built Fallout
    game in Oct 2026. How: owner decision on visibility (public repo, project name, "Fallout" in titles).
18. **Is SFSE CharGenMenu's preset format a route for carrying an FO4 face?** Why: mod 15088 shows player-face presets
    as files under `SFSE\Plugins\Chargen\Presets`. How: offline read of one preset file; owner decision on SFSE.
19. **Do we need Starfield CK command-line generation (icons, lip, SEQ) in the launcher?** Why: only icon switches are
    reported, and one user saw no output. How: read-only PC check of `CreationKit.exe` strings for `-Generate`; then a
    manual CK run.
20. **Which Starfield build do we pin, and do we refuse to run on an MS Store build?** Why: SFSE is Steam-only, while
    Address Library ships MS Store tables; a plugin-only start needs neither. How: owner decision; launcher version gate
    with an offline unittest.

---

## Earlier notes (01 to 05): what this reading confirms or contradicts

Confirms:
- 01 1.4 / 03: No Ship Fast Start overrides `StartupQuest_DO`, uses a placeholder home ship via `SQ_PlayerShip`, and
  restores sustenance and Cruise Mode (verified again, page text quoted).
- 01 1.1 / 03 section 2: MQ101Debug 8 puts a new game in the New Atlantis spaceport. Now shown **without any mod**
  (wiki how-to), so it is a vanilla debug start.
- 03 1.3: the UESP stage outline, now read verbatim from the wikitext (adds 0 "Always Run on Start", 63 chargen
  failsafe, 155 "START TUTORIALS", 900 fast-travel block, 9000 "Run on Stop").
- 01 1.5 / 02 / 03: RAS skips One Small Step entirely, lists SSNN and Auto Hide HUD fallout, deactivates on existing
  saves; uses a medium master.
- 01 3.1: LAL's Dragonsreach failsafe, the MQ101/MQ102/WERoad01 incompatibility list and the "do not console around the
  Whiterun gate" rule (now from the author's own thread).
- 02 section 9: Capital Wasteland ended over voice licensing, with the "sketchy as all hell" quote; adds that Bethesda
  "didn't technically shut us down".
- 02 section 3 / 05 section 5: Skyblivion needs both games, uses a custom installer, avoids remaster assets for legal
  reasons, and you cannot travel to Skyrim's worlds.
- 04 section 1: chargen is `chargenmenu.swf`, edited with JPEXS (Expanded Backgrounds again); NG+ chargen can leave
  controls/saving locked (UESP NG+ bug, `SetInCharGen 0 0 0`).
- 05 section 3: SFSE 0.2.21 targets 1.16.244 (tracker agrees).

Contradicts or corrects:
- 01 section 3.2 and this task's brief: **Nexus SSE 8328 is RASR (Random Alternate Start Reborn), not Realm of
  Lorkhan.** Realm of Lorkhan is SSE 18223.
- 01 1.4: the sustenance form is spelled `PEO_SustenanceAllowed` there (as on No Ship Fast Start's page), but the
  Community Patch names it `POE_SustenanceAllowed [002EEA4D]`. Use the form id until the PC check settles the name.
- 03 table 3 (Traits): "Dream Home ... starts on leaving the Lodge for the first time" is not what UESP's One Small Step
  page says: Dream Home, Kid Stuff, Board and Lodging and The Old Neighborhood "begin immediately" at MQ101's completion
  (RAS: "you need to complete One Small Step in vanilla"). The two may both hold (quest starts at 1800, objective fires
  on leaving), but 03's wording is incomplete.
- 03 1.3: stage 500's note is "DEBUG 10 - Encounter over, skip to New Atlantis", not just "debug skip to New Atlantis";
  the "10" is unexplained and should not be read as MQ101Debug = 10.
- 03 1.11 / Q17: "Main quest IDs not read" is now answered in part (act list; NG+ starts are MQ401a-j).
- 05 section 5 / 02 lesson 1: "Bethesda's guideline text is still unread" is resolved: it bans uploads using "assets
  from other Bethesda games" (verified). 05's "supported hypothesis" that distribution through Creations is the riskiest
  channel becomes a direct rule for Bethesda.net/Creations.
- 02 / 05 Skyblivion "Bethesda required 100% of assets replaced": not in the Skyblivion FAQ; remains Wikipedia-only
  (supported hypothesis, not verified).
- 04 header / 05 Q: mod 15088 is a chargen face preset needing SFSE CharGenMenu, not a start or chargen-flow mod.
- 05 section 1: "CK command-line options: no source" is now partly answered (icon generation switches, community
  source); LipGen/SEQ/precombine switches remain unresolved.
- 05 section 3: the Address Library "snapshot showed only 1.7.23 files" is out of date: v22 (13 June 2026) covers
  1.16.244 and has MS Store tables.

## Sources
- https://help.bethesda.net/app/answers/detail/a_id/51731/
- https://help.bethesda.net/app/answers/detail/a_id/55219/~/porting-rules---mods---bethesda.net
- https://web.archive.org/web/20250108164810/https://wiki.nexusmods.com/index.php/Porting_content
- https://www.nexusmods.com/fortresscraftevolved/news/15391
- https://www.pcgamesn.com/fallout-4/fallout-4-fallout-3-capital-wasteland-mod
- https://skyblivion.com/faq/
- https://taleoftwowastelands.com/viewtopic.php@t=7850 (snippet)
- https://www.tweaktown.com/news/113882/bethesda-shuts-down-vibe-coded-fallout-project/index.html
- https://starfieldwiki.net/w/index.php?title=Starfield:One_Small_Step&action=raw
- https://starfieldwiki.net/w/index.php?title=Starfield:Main_Quests&action=raw
- https://starfieldwiki.net/w/index.php?title=Starfield:New_Game_Plus&action=raw
- https://starfieldwiki.net/wiki/Starfield_Mod:Papyrus_debugging_with_VS_Code
- https://github.com/Starfield-Community-Patch/Starfield-Community-Patch/issues/957
- https://www.nexusmods.com/starfield/mods/15092
- https://www.nexusmods.com/starfield/mods/15102
- https://www.nexusmods.com/starfield/mods/15094 ; https://github.com/ZeCroque/RoleplayersAlternateStart (front page only)
- https://www.nexusmods.com/starfield/mods/15088
- https://www.nexusmods.com/starfield/mods/15724
- https://creations.bethesda.net/es/starfield/details/78e0e1e2-0016-4d9c-9ced-0175d6b73c41/SKK_Fast_Start_New_Game__Starfield_ (snippet)
- https://creations.bethesda.net/en/starfield/details/c27a121a-c565-4ae0-9394-c58952c98f86/RYOS_Roll_Your_Own_Start (snippet)
- https://www.afkmods.com/index.php?/topic/4638-relz-alternate-start-live-another-life/
- https://www.nexusmods.com/skyrimspecialedition/mods/8328
- https://www.nexusmods.com/skyrimspecialedition/mods/18223 (snippets only)
- https://bandurart.com/skyrim-alternate-start/
- https://www.nexusmods.com/starfield/mods/3256
- https://modlag.com/starfield
- https://www.reddit.com/r/starfieldmods/comments/1e3tc8r/how_to_add_menu_images_for_your_constructable/
