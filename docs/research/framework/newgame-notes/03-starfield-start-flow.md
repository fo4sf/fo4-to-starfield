# 03: Starfield's own new-game flow, and what depends on the main quest

Written 2026-10-19 by Claude (cloud research agent, new-game framework). Web research only; nothing here ran in game.
Labels follow docs/ai/research-log.md: **verified** (primary source or PC file read, cited), **supported hypothesis**
(secondary source or inference, cited), **unresolved**. "Verified (repo)" means already verified on the PC and recorded
in `docs/newgame/vault111-start.md`; this file does not re-prove it.

Access note: after about 25 page reads the web-fetch proxy began answering HTTP 429 (rate limited) for
starfieldwiki.net (UESP's Starfield mirror), nexusmods.com and others. These pages could **not** be read and are
left for a later pass: UESP `Starfield:Main_Quest`, `Starfield:New_Game_Plus`, Nexus news 14888 (plugin types),
Nexus article 688, the LOOT changelog, one Steam thread on showlooksmenu, gfinityesports (fast travel). Claims that
needed them are marked unresolved.

---

## 1. From "New" to player control (vanilla)

| # | Fact | Label | Source |
|---|---|---|---|
| 1.1 | MQ00's only fragment (stage 10) sets GLOB `MQ101Debug` to 10, waits 0.1 s, starts MQ101. `MQ101Script.OnQuestInit` calls `SetStage(400)` only when `MQ101Debug == 1`. | verified (repo) | docs/newgame/vault111-start.md section 2 |
| 1.2 | MQ101 is "One Small Step"; its fragment file is `qf_mq101_00003448.psc`, so the quest's form id is 0x003448 in Starfield.esm. | verified (Community Patch issue quotes the path); repo's test-queue cites the same file | https://github.com/Starfield-Community-Patch/Starfield-Community-Patch/issues/714 |
| 1.3 | MQ101 stage outline (UESP): 0-9 startup, preload Vectera, elevator descent, "player can move"; 10-51 laser cutter, mining, cavern, artifact; **60-105 infirmary, character creation, chargen furniture, "character gen completes" (105)**; 157-170 medpack, airlock/helmet tutorial; 180-315 Barrett lands, pirates, Barrett gives his watch (305), controls restored (310); 320-345 board the Frontier with Vasco, takeoff; **400 first space flight** + ship tutorials (403-485); 490-540 encounters, grav jump; **500 "debug skip to New Atlantis"**; 600-700 Kreet, **627 scanner tutorial**; **900-1020 fast travel restrictions, monocle, surface map, data/mission/galaxy menu tutorials**; 1300-1340 Jemison, land in New Atlantis, ship services; 1500-1660 Lodge, Sarah, artifacts; 1750 sets up MQ103; **1800 quest complete**; 1810 player leaves the Lodge; **2000/2100 "STARBORN PATH" start/complete** (the NG+ path). | supported hypothesis (UESP stage table read through a summariser; exact text not re-checked) | https://starfieldwiki.net/wiki/Starfield:One_Small_Step |
| 1.4 | Character creation happens **inside MQ101** (stages 60-105), after the mine, not before the game starts. | supported hypothesis (UESP table, 1.3; SKK stop code "[3] MQ101 character generation state 105 has already been completed") | UESP above; https://www.nexusmods.com/starfield/mods/5971 |
| 1.5 | The "scanner" is not a separate item: Barrett's watch (given at MQ101 stage 305) is the hand scanner; stage 627 is the scanner tutorial. | supported hypothesis | UESP One Small Step (1.3) |
| 1.6 | The player's first ship is the Frontier, lent by Barrett in MQ101 (320-345); Vasco joins as follower/crew under "Protocol Indigo" until the Lodge. | supported hypothesis | UESP One Small Step |
| 1.7 | Constellation membership, Vasco as companion, the Frontier and the Lodge key are MQ101's rewards. | supported hypothesis | UESP One Small Step |
| 1.8 | `MQ_TutorialQuest` (form 0x045640) is started by MQ101 stage 155 (`MQ_TutorialQuest.Start()`), with further attempts at 400 and 605. It covers zero-G, companions, EM weapons, ship damage, scanner, missions menu, Starborn powers, grav jump, commandeering a ship. Its script registers for the player ship's events via `PlayerShip.GetShipRef()` and fails if there is no ship yet. | verified (script lines quoted in the issue, game 1.8.86) for the start and the ship lookup; tutorial list supported hypothesis (UESP) | Issue 714 above; https://dev.starfieldwiki.net/wiki/Starfield:Tutorial_Quest |
| 1.9 | `FFLodge01` "Board and Lodging" is Noel's Lodge tour (stages 10-100); SKK completes MQ101 and FFLodge01 together for a "join Constellation" start. | supported hypothesis | https://starfieldwiki.net/wiki/Starfield:Board_and_Lodging ; SKK 5971 |
| 1.10 | A trait quest, `TraitQuest` 0x001687DB, has to start after chargen; SKK added "an extra call to ensure TraitQuest 001687DB starts after Chargen". So traits are wired to MQ101's chargen, not to the race menu alone. | supported hypothesis (mod author's changelog) | SKK 5971 v004 |
| 1.11 | What the Main Quest's later IDs are (MQ102...MQ305), which one grants powers/temples, and which one leads to the Unity: not read (UESP Main_Quest page rate-limited). | unresolved | - |

## 2. How existing mods bypass the opening (prior art)

| Mod | Method (as the page says) | Label | Source |
|---|---|---|---|
| **SKK Fast Start New Game** (Nexus 5971) | GLOB `MQ101Debug` hard-edited to **8** in its ESM; a new game then lands in cell `NewAtlantisSpaceport03`, and SKK's quest checks: level <= 2, MQ101 chargen stage 105 not done, MQ101 not past 1510, player in that cell. NG+ requires MQ101 at 0 or 2000 and the player on `MQPlayerStarbornShipREF`. "ZERO BASE GAME SCRIPT HACKS". Option to complete MQ101 + FFLodge01, put Vasco in the Lodge hallway, enable the Frontier on the Atlantis pad, give the Lodge key. Since v015 "Cruise Mode is enabled without completing the One Small Step quest". Switched small ESM to large ESM because "Game.GetFormFromFile() lookups resolve the wrong file index on ESM(small)". Conflicts with every other new-game mod; must not be removed mid-save. | supported hypothesis (author's text) | https://www.nexusmods.com/starfield/mods/5971 |
| **Roleplayers' Alternate Start** (15094) | Custom start cell; vanilla One Small Step "skipped entirely", so dependants (SSNN interview) don't occur; Barrett/Frontier moved into a later rescue quest; "Auto Hide HUD and Widgets - SFSE won't work until One Small Step is completed"; deactivates itself on existing saves until NG+. Offers a "no ship" start. | supported hypothesis | https://www.nexusmods.com/starfield/mods/15094 |
| **ECS Asteria** (16206) | New game teleports the player immediately; "One Small Step" stays in the log like NG+; v2.0.1 "script edits to prevent teleportation if installed mid-game"; Frontier locked "due to bugs"; earlier bug affecting Main Quest completion and Unity dialogue fixed in 1.2.2; needs the Cruise Patch. | supported hypothesis | https://www.nexusmods.com/starfield/mods/16206 |
| **Alternate Start Starfield** (2076) | Save files, not a plugin; fast travel "locked in most locations until you return the artifact to Constellation"; uses `showlooksmenu player 1` for looks/name/traits. | supported hypothesis | https://www.nexusmods.com/starfield/mods/2076 |

Conflict to settle: SKK's start works with `MQ101Debug = 8` set in a plugin, yet the repo verified that MQ00 stage 10
sets the global to 10 before starting MQ101 (1.1). Either MQ00's set is conditional (not visible in the line we
recorded), or 8 is acted on before stage 10 runs, or MQ00 does not run when 8 is set. **unresolved**; an offline read of
`QF_MQ00_00005790.psc` around line 7 and of the MQ00 record's conditions answers it.

## 3. Systems that assume the main quest ran, or a planet, or a ship

| System | What it depends on | Label | Source |
|---|---|---|---|
| Fast travel | MQ101 stages 900-1020 handle "fast travel restrictions" and the map/galaxy tutorials; save-start players report fast travel locked "until you return the artifact to Constellation". Stopping MQ101 early may leave restrictions set, or never set them. | supported hypothesis | UESP One Small Step; Nexus 2076 |
| Cruise Mode (Free Lanes, 7 Apr 2026) | Gated on One Small Step completion in vanilla (SKK v015 had to enable it separately). Interruptible by attacks; ends in a short load. | supported hypothesis | SKK 5971; https://www.galaxus.fr/en/page/the-future-of-starfield-whats-the-big-update-changing-41937 ; https://frvr.com/blog/starfield-producer-explains-free-lanes-travel-is-completely-under-your-control |
| Tutorials | MQ_TutorialQuest needs the player ship ref; with no ship its registrations fail silently (no retry). | verified (script quote) | Issue 714 |
| Traits | TraitQuest 0x1687DB starts after MQ101's chargen (1.10). Dream Home = `TraitStarterHome`, starts on **leaving the Lodge for the first time**, mortgage via GalBank, home on Nesoi. Kid Stuff: Noel hands "Note from Dad" at the Lodge; parents' activity starts when you first leave the Lodge; 2% weekly (cap 500). Wanted: mercenaries "occasionally attack". Spaced / Terra Firma depend on space vs surface. Serpent's Embrace depends on grav jumps. | supported hypothesis | SKK 5971; https://dev.starfieldwiki.net/wiki/Starfield:Dream_Home_(Mission) ; https://starfieldwiki.net/wiki/Starfield:Kid_Stuff ; https://starfieldwiki.net/wiki/Starfield:Traits |
| Lodge / Constellation companions | Joining Constellation is MQ101's end; Vasco and Barrett's ship are MQ101 rewards; SKK's "disable" option has to unlock Sarah, Barrett, Sam, Andreja in the Lodge by script. | supported hypothesis | UESP; SKK 5971 |
| Workshop / outposts | A workshop activator patterned on `OutpostPlayerHouseActivator` crashed the game in our world. | verified (repo, 19 Oct) | /mnt/attach/project-files/research/next-phase/npcs-ai-factions-dialogue-quests.md section 8 |
| Radiant / encounters | UESP gives no trigger details (pages are stubs); e.g. `OE_KMK_HostileHumans_Ship` has stages "player in range", "ship lands". Our own Story Manager branch is engine question E5 in docs/questprobe/engine-questions.md. | unresolved | https://dev.starfieldwiki.net/wiki/Starfield:Hostile_Humans_-_Ship_Landing ; https://starfieldwiki.net/wiki/Starfield:Radiant |
| Third-party UI mods | "Auto Hide HUD and Widgets - SFSE won't work until One Small Step is completed." | supported hypothesis | Nexus 15094 |
| Powers / temples / Unity / NG+ | MQ101 has a "Starborn path" (2000/2100) for NG+; which MQ quests start powers and the Unity was not read. | unresolved | UESP (rate limited) |
| Ship services, home ship, scanner HUD, gravity/oxygen, starmap in a world with no planet data | No source found. | unresolved | - |

## 4. Start-game-enabled quests from a plugin: new game vs loaded save

- Creation Kit (Skyrim wiki, Quest Data tab): "If this box is checked, the quest starts running at the beginning of the
  game"; "If a Start Game Enabled quest is not also flagged to Run Once, its OnInit event will fire twice"; Run Once
  blocks all resets including `Reset()`; for SGE quests "added to a pre-existing save" Run Once may still be needed;
  Skyrim 1.7+ tracks added SGE quests with SEQ files needed for dialogue and scenes.
  **verified for Skyrim; supported hypothesis for Starfield** (same quest-flag model; not checked).
  https://ck.uesp.net/wiki/Quest_Data_Tab
- Every alternate-start mod read needs its own guard against mid-game installs (SKK stop codes; ECS v2.0.1; RAS
  "deactivates itself on existing saves until NG+"), which supports that a plugin's SGE quest **does** start when the
  plugin is added to an existing save. **supported hypothesis** (SKK, ECS, RAS pages above). Our level + GameDaysPassed
  guard matches this practice.
- Whether Starfield still uses SEQ files: **unresolved**.
- Plugin type: SKK reports `Game.GetFormFromFile()` resolving "the wrong file index on ESM(small)". Our quest resolves
  FO4Port/core ids with GetFormFromFile, and the repo's door contract "does not support light/medium plugin IDs".
  **supported hypothesis** (one author's report). Medium-master details: unresolved (Nexus news 14888 not read).

## 5. Console commands (UESP Starfield console page; the page itself says it is incomplete and "needs recheck")

Documented with syntax: `setstage <quest> <stage>`, `getstage <quest>`, `resetquest <quest>`, `completequest <quest>`,
`sqs <quest>` (stages), `sqv <quest>` (variables), `sqt`, `set <global> to <value>`, `GetGlobalValue <global>`,
`setpqv <quest> <var> <value>`, `coc`, `cow`, `moveto <actor>`, `tgm`, `tcl`, `tfc`, `bat`, `save`, `help`.
`ShowRaceMenu` with no argument "will bring up the race menu" (under SetPlayerRace). `startquest`/`stopquest` are listed
by name only. Do **not** use `caqs` (completes every quest, unlocks achievements). Mod page (not primary):
`showlooksmenu player 1` for looks/name/traits (Nexus 2076). **supported hypothesis** (UESP marks it unverified).
https://starfieldwiki.net/wiki/Starfield:Console

Testing set for the first proof: `getstage MQ00`, `getstage MQ101`, `sqv MQ101`, `GetGlobalValue MQ101Debug`,
`getstage MQ_TutorialQuest`, `sqs <our quest>`, `sqt`.

---

## 6. Questions our new-game design must answer

| # | Question | Why it matters | How to answer |
|---|---|---|---|
| Q1 | Is MQ00's `MQ101Debug = 10` unconditional, and how does SKK's 8 survive it? | Decides whether option B (debug global) is viable at all | Offline: read QF_MQ00_00005790.psc fully + MQ00 record conditions (Mutagen) |
| Q2 | What does each MQ101Debug value (1, 2, 8, 10) do in MQ101's fragments, and where does 8 put the player (NewAtlantisSpaceport03)? | A Bethesda-built skip may be safer than Stop() | Offline: grep all fragments/scripts in ContentResources.zip for MQ101Debug |
| Q3 | By the time our SGE quest runs, has MQ101 already disabled controls, started its scene, preloaded Vectera or faded the screen? | Stop() may leave the player stuck (controls/camera layers) | In-game: log timestamps + `getstage MQ101` on the first frame; offline: MQ101 stage 0-9 fragments |
| Q4 | Does `Quest.Stop()` on MQ101 release its input layers / InputEnableLayers? | A stopped quest's layers may persist | Offline read of MQ101Script; in-game test |
| Q5 | Does `Game.ShowRaceMenu()` outside MQ101 offer traits and backgrounds, and does TraitQuest 0x1687DB start? | Without it traits are cosmetic or broken | In-game + `getstage` on 0x1687DB; offline: who starts it (Mutagen/scripts) |
| Q6 | Do we offer traits at all? Dream Home and Kid Stuff fire on "leaving the Lodge"; never in our game. | Dead choices confuse players | Owner decision; or our chargen hides them |
| Q7 | Fast travel: is it locked by default and unlocked by MQ101 (stages 900-1020), or locked by MQ101? | Our world needs fast travel to markers | Offline: MQ101 900-1020 fragments; in-game: try fast travel in our world |
| Q8 | Does Starfield's map/fast travel work in a worldspace with no planet (PNDT) at all? | Core to the Commonwealth being playable | In-game test |
| Q9 | Should the player ever get a ship? If not, what in HUD, scanner, MQ_TutorialQuest, ship services or Cruise Mode errors or nags without one? | Ship scripts assume `PlayerShip.GetShipRef()` | Owner decision + Papyrus log search for None ship errors |
| Q10 | Do we stop MQ_TutorialQuest too, or leave it unstarted (MQ101 stopped before 155)? | Its tutorials mention ships/powers | Offline (who else starts it) + `getstage` in game |
| Q11 | Is the hand scanner (watch from stage 305) available without MQ101, and does it work with no planet data? | Scanner replaces nothing yet; may error | In-game test; owner decision on the Pip-Boy role |
| Q12 | Which of the other ~142 SGE quests run in our world and do any fire Story Manager events (planet landing, location change) there? | Fence list; the workshop crash shows unvetted systems run | Offline Mutagen list of SGE quests + SMQN events; in-game `sqt` |
| Q13 | Can our own Story Manager branch fully isolate radiant content (E5)? | Starfield radiant quests must not spawn Starfield NPCs in Concord | Probe quest FO4SF_QProbeSM in game |
| Q14 | Does an SGE quest's OnInit fire twice without Run Once in Starfield, and is ours Run Once? | Double moves / double ShowRaceMenu | Offline check of our QUST flags; in-game log count |
| Q15 | Does our plugin's type (full ESM) and the FO4Port/core types keep GetFormFromFile correct (SKK's small-ESM report)? | Wrong file index = moves to wrong refs | Offline: plugin header flags; in-game log of resolved ids |
| Q16 | Is a "Starfield start" choice (option D) worth keeping, so MQ101 can still run later for those who want Constellation? | Stopping MQ101 at 0 may make it impossible to restart (Run Once?) | Offline: MQ101 flags; owner decision |
| Q17 | What happens to NG+ / Unity if MQ101 never completes? Do we promise NG+ at all? | MQ101 2000 "Starborn path", NG+ checks MQ101 stage | Owner decision; UESP MQ pages when readable |
| Q18 | Do achievements matter? (any plugin disables them unless Creations; caqs etc.) | Players will ask | Owner decision |
| Q19 | Which time/weather/date does Starfield set at start (MQ101 calls SetLocalTime), and do we set FO4's morning? | Vault exit lighting and FO4 date | Offline read of QF_MQ101 fragments; our script |
| Q20 | Gravity/oxygen/environment hazards: what values does a non-planet worldspace give (0 g? no O2)? | Breathing and jump height on the surface | In-game test (`sqv`/HUD readout); offline: WRLD fields in Starfield.esm |
| Q21 | Does Cruise Mode or any Free Lanes script try to pull the player out of a non-planet world? | 2026 update, new systems we have not tested | In-game test after first proof |
| Q22 | What carries over if a player installs our plugin on a save mid-MQ101? (our guard stands down) | Support burden | In-game test on a throwaway save, never the owner's |

## 7. The 5 most important findings

1. **Character creation, traits, the scanner, the first ship, Vasco, Constellation and fast-travel unlocks all live
   inside MQ101** (stages 60-105, 305, 320-345, 900-1020, 1800). Stopping MQ101 at the start removes all of them at once;
   each one we want back has to be re-provided by our quest. (supported hypothesis, UESP)
2. **SKK Fast Start uses MQ101Debug = 8 in a plugin** and lands the player in `NewAtlantisSpaceport03`, which conflicts
   with our verified MQ00 "sets 10" reading. Resolving this (Q1, Q2) decides whether a Bethesda debug skip exists.
3. **TraitQuest 0x1687DB must start after chargen** (SKK had to start it by hand); `Game.ShowRaceMenu()` in the vault
   probably leaves chosen traits inert. Dream Home and Kid Stuff are triggered by leaving the Lodge.
4. **MQ_TutorialQuest (0x045640), started at MQ101 stage 155, assumes a player ship** and fails silently without one; a
   no-ship game has more of these (verified pattern). A Papyrus-log sweep for None ship refs belongs in the first proof.
5. **GetFormFromFile on small ESMs resolves the wrong file index** (SKK's report), and every alternate start guards
   against mid-game installs because a plugin's SGE quest starts on an existing save too. Our design already guards;
   plugin types must be checked.
