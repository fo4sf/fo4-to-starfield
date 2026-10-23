# 01: Alternate-start and skip-intro precedents (Starfield, Fallout 4, Skyrim)

Written 2026-10-19 by Claude (research agent for the new-game phase). Web research only: no game files were read for
this note. Labels: **verified** = a primary source (the mod's own page or the author's article) says so, and the URL is
given; **supported hypothesis** = inferred from one or more primary sources but not stated outright; **unresolved** =
not established. "Verified" here means only "the author says so on the page", not "we checked the mod's records".
Nothing in this note was tested in game.

Pages I could not read: the WebFetch proxy rate-limited me (HTTP 429) on Realm of Lorkhan (nexusmods SSE 8328),
Skyrim Unbound mod 111029, UESP Skyrim:Unbound and a vgtimes mirror. The Realm of Lorkhan and Unbound points below are
therefore **unresolved** and need a later read.

Context: our plugin FO4SFNewGame.esm (master Starfield.esm only) has a start-game-enabled quest that stops MQ00 and
MQ101 from Papyrus, moves the player to the converted Vault 111 cryo pod, calls Game.ShowRaceMenu() and takes them up
the elevator into the converted Commonwealth (docs/newgame/vault111-start.md, options A to D).

---

## 1. Starfield

### 1.1 SKK Fast Start New Game (SKKmods), Nexus Starfield 5971, also a Bethesda Creation
URL: https://www.nexusmods.com/starfield/mods/5971 ; https://skkmods.com/starfield/ ;
Creation: https://www.starfieldunity.com/mods/87/skk-fast-start-new-game-starfield (achievement-enabled edition:
https://www.starfieldunity.com/mods/2444/skk-fast-start-new-game-starfield-achievement-enabled)

- **verified** (mod page): bypasses the Argos/Vectera and Atlantis tutorials for new games and NG+, with "ZERO BASE
  GAME SCRIPT HACKS". New games start at the New Atlantis spaceport and show config menus (start location, loadout,
  character generation). NG+ starts on the Starborn ship.
- **verified**: the ESM sets GLOB `MQ101Debug` to **8** as a "hard edit by the ESM". Its startup validation stops with
  a code when MQ101Debug is not 8, the player is over level 2, MQ101 stage 1510 is already passed in the Lodge, or the
  player is not in cell `NewAtlantisSpaceport03`. NG+ requires MQ101 at stage 0 or 2000 and the player on
  `MQPlayerStarbornShipREF`.
- **supported hypothesis**: MQ101Debug 8 is what puts a vanilla new game in `NewAtlantisSpaceport03` (the mod only
  checks where the player is; it does not move them there itself before validating). Our PC precheck already found
  value 8 set by a test quest and read by `CruiseModeTestSupportScript` (docs/newgame/vault111-start.md section 2), so
  the 8 path appears to be a Bethesda test start that SKK reuses. Note our own finding that MQ00 stage 10 writes 10 to
  MQ101Debug before starting MQ101: how SKK's 8 survives that is **unresolved** (perhaps the vanilla MQ00 fragment
  differs from what we read, or reads it first, or the engine treats a non-default value differently). This is the
  single most important thing to settle before we pick option B.
- **verified**: "Join Constellation [No:0 | Yes:1 | Disable:2]". 1 completes MQ101 "One Small Step" and FFLodge01 and
  moves the player to the Lodge; 2 disables the Constellation main quest to unlock companions. Cruise Mode is enabled
  without finishing One Small Step. Lodge key and Temple Finder holotape given; Vasco is placed in the Lodge as
  crew/follower; Sarah and Andreja unlocked in the Lodge (v004).
- **verified**: v004 added "an extra call to ensure TraitQuest 001687DB starts after Chargen". Known issue: sometimes
  the Fast Start menu does not show after the chargen screen and player controls stay locked.
- **verified** known issues: suppressed weapon noise on new starts (cleared by save/reload); "dialogs or message boxes
  shown before setup completes can block it"; anything touching MQ101Debug or MQ101 startup breaks it; conflicts with
  Crimson Start and other start mods (SKK mods detect each other). ESM must be "ESM large" because ESM(small) caused
  wrong file-index lookups. Not removable from a save.
- Engine lessons: (a) chargen does not by itself start the trait quest: something after chargen must; (b) message
  boxes and menus during start-up race each other and can lock controls; (c) a start mod validates game state and
  refuses to run when it is wrong (good practice our quest already copies with its new-game guard).

### 1.2 SKK Fast Start New Game (Legacy), Nexus Starfield 3050 (Sept to Oct 2023, before the Creation Kit)
URL: https://www.nexusmods.com/starfield/mods/3050
- **verified**: a loose `.pex` plus a console batch file run by `StarfieldCustom.ini` `[General] sStartingConsoleCommand
  = bat SKKFastStartNewGame`. It skipped facegen, traits and background (default face, Frontier owned, Argos-mine
  loadout); the player then ran `ShowLooksMenu Player` in the console.
- Lesson: `sStartingConsoleCommand` is a debug path into a fresh game; a PC-only test lever for us, not a shipping
  mechanism (**supported hypothesis**: it is useful for quick in-game experiments without building a plugin).

### 1.3 Crimson Start New Game (SKKmods), Nexus Starfield 6869
URL: https://www.nexusmods.com/starfield/mods/6869
- **verified**: new game (or NG+) begins as a level-1 Crimson pirate in a Crimson Ghost home ship outside the Key;
  completes CF01 and CF02 without XP. Validation: MQ101Debug must be **5** (stop code 1), level <= 2, MQ101 not past
  stage 20, player in cell **`VecteraMine01`**. v007 enables Cruise Mode without One Small Step. "Shattered Space DLC
  quests still won't start until MQ101 is complete." Lodge key given for the Universal Stash.
- **supported hypothesis**: MQ101Debug 5 is another vanilla debug start state, this one leaving the player in the
  Vectera mine (that is, after or at the mine section, before chargen?). Which stage MQ101 is at with 5 is
  **unresolved**; the check "MQ101 not past stage 20" says early.
- Lesson: at least two non-default MQ101Debug values (5 and 8) are used by shipping mods; the global is the engine's
  intended debug lever. Also: **DLC (Shattered Space) gates on MQ101 completion**, so a world without MQ101 complete
  has DLC quests dormant.

### 1.4 No Ship Fast Start (LeavingLasOrleans), Nexus Starfield 15092 and First We Crawl, 15102
URLs: https://www.nexusmods.com/starfield/mods/15092 ; https://www.nexusmods.com/starfield/mods/15102
- **verified**: "overrides `StartupQuest_DO` and redirects startup from MQ101 to a custom controller quest. MQ101
  stays available for later progression." Suppresses later quest triggers (e.g. arriving at Kreet) so the tutorial
  does not restart.
- **verified**: "Starfield expects a home ship for ship services", so it creates a hidden, disabled, partless
  placeholder ship assigned through `SQ_PlayerShip`, with `CannotBeModifiedShipKeyword` and `DisableInventoryTransfer`;
  an `OnHomeShipSet` handler removes it later. Sustenance is enabled by overriding `PEO_SustenanceAllowed` with a
  custom global set to 1. Cruise Mode restored by the controller script.
- **verified**: main quest is idle; visiting the Lodge reactivates it. Known: player can be stuck with no ship/money; a
  ship-tech dialogue glitch (1.3); 2.0 may not work on old saves; First We Crawl notes fast travel beyond ship range is
  an unsolved issue and that 2.3 "hopefully" stopped the tutorial restarting at Kreet.
- Lessons, highly relevant to us: (a) there is a vanilla quest `StartupQuest_DO` that is what launches the opening (so
  "who starts MQ00/MQ101" has a record-level answer we should read on the PC); (b) **some systems assume a home ship
  exists** (ship services, HUD/ship menus); our Vault 111 start has no ship and must decide whether to give a
  placeholder; (c) **survival/sustenance and Cruise Mode are gated by MQ101-related globals/logic**, so skipping MQ101
  silently changes systemic behaviour; (d) geographic triggers (Kreet) can re-arm the tutorial later.

### 1.5 Roleplayers' Alternate Start (ZeCroque), Nexus Starfield 15094
URL: https://www.nexusmods.com/starfield/mods/15094
- **verified**: mid-master `RoleplayersAlternateStart.esm` + BA2s; "relies primarily on hooks and replacers, keeping
  vanilla quest edits to an absolute minimum" (what "hooks" means is **unresolved**; no SFSE requirement is listed).
  One Small Step is skipped entirely; dependent events (the SSNN Vectera interview) do not happen; it can be marked
  complete from a "Narrative Adjustments" terminal for compatibility.
- **verified**: the **starting area is a custom Unity** (a hub cell, like Live Another Life's prison) with a
  Character Skills Manager (level, piloting rank), a ship technician and a gear terminal; gear is put aside and
  returned at Unity exit. Three mutually exclusive main-quest entry points (vanilla Argos recruit, the artifact
  spawning "organically" after level 5, or a Starborn "Guide" NPC). Barrett leaves for Vectera before the Lodge, with
  new Constellation dialogue that avoids Argos/Vectera references; the Frontier is locked until "Echoes of Vectera".
  The Kreet laboratory map marker is hidden to prevent issues before the main quest.
- **verified** bugs: v1.1.7 fixed Vasco believing Constellation was dead (blocked recruitment and NG+); unvoiced new
  lines; rescue-beacon ship clipping. On an existing save the mod deactivates itself until NG+.
- Lessons: (a) a hub cell where the player chooses is the cleanest UX and is now the Starfield state of the art;
  (b) skipping MQ101 has a long tail of dialogue/condition fallout (Vasco, parents, SSNN), each needing a fix;
  (c) the "deactivate on existing saves" guard is standard.

### 1.6 New Game Starts With Character Creation (AlmightySE), Nexus Starfield 6598
URL: https://www.nexusmods.com/starfield/mods/6598
- **verified**: starts new games at the point after the first artifact, where character creation begins. Mechanism not
  stated on the page (**unresolved**; plausibly an MQ101Debug value or start-stage edit).

### 1.7 Save-file and console "starts" (Sept 2023)
- Alternate Start Starfield / "Another Start" (SpaceDov4), Nexus 2076: https://www.nexusmods.com/starfield/mods/2076 ;
  coverage https://exputer.com/news/games/starfield-mod-skip-intro/ ,
  https://www.pcgamesn.com/starfield/alternate-start-mod . **verified**: save files per background, then
  `showlooksmenu player 1` for looks, name and traits; fast travel locked until the artifact is returned.
- Create Your Character Immediately (Mybones), Nexus 1298: a save at the chargen point.
- Biometric ID editor (Ravenaut), Nexus 6145: **verified** `slm player 1` reopens Bethesda's chargen in a loaded game;
  "Dream Home and Kid Stuff traits don't work without separate setstage commands." Lesson: **chargen outside its
  normal moment does not run the trait side effects**; those quests/stages must be driven by us.
- Alternate Start (Nexus 4431, "instant Starborn", https://starfieldportal.com/article/begin-starfield-as-an-instant-starborn):
  all powers, level 50; mechanism not stated.

### 1.8 NG+ side: NGPlus skip main quest tweaks (ShadowFX), Nexus 16210
URL: https://www.nexusmods.com/starfield/mods/16210
- **verified**: content gated on MQ402 stage 600 (NG+ "skip the main quest" path) is restored with story-manager
  triggers and new topics: Noel, Vlad, Walter's Overdesigned, SAL-6830, Nyssa's quests, Rafael, Lin/Heller elite crew,
  Moara, "A Light in the Darkness" interview count. Lesson: Bethesda's own skip path (NG+) leaves a catalogue of
  content that silently never unlocks; the same will happen to us for anything gated on main-quest stages.

Also listed in a Nexus video comparing start mods (https://www.nexusmods.com/starfield/videos/3341): "Roll Your Own
Start" and "LSD's New Game Customizer"; I could not find their pages (**unresolved**, not described here).

---

## 2. Fallout 4

### 2.1 SKK Fast Start New Game (SKKmods), Nexus FO4 29227, and the author's article
URLs: https://www.nexusmods.com/fallout4/mods/29227 ; https://www.nexusmods.com/fallout4/articles/1038
- **verified**: "scripted bypass, not a static savegame": Looks menu, SPECIAL menu, then outside Vault 111 in under two
  minutes. v021: the mirror conversation goes straight to chargen. Internal SKK quest stage 10 at bypass start, 20 at
  vault exit. Stop codes: MQ101 past stage 0, MQ102 past stage 0, or player not in `PrewarPlayerHouse01`.
- **verified** (article): FO4's MQ101 script calls `PlayerREF.RemoveAllItems()` at stage 0 **and again at stage 900**,
  so items given early are lost; FastStart "intercepts MQ101 at Stage(20)", bypasses the 900 clear, marks MQ101
  complete and sets MQ102 stages 10 and 15. MQ102 10/15 are a known **event bottleneck**: many mods and Creation Club
  files hang on them, MQ102 "can take several minutes" to return, causing missed Codsworth/Preston scenes.
  WorkshopParentScript can take "TWO MINUTES" to finish registrations; v020 lets you wait in the bathroom for it.
- **verified**: keeps Vault 111 animations (elevator, gear door, spouse) primed so the player can return. Mods that
  open UI dialogues between the mirror and the MQ101 stage-10 elevator exit can break start-up.
- Lessons: (a) the start is the busiest moment of the game for scripts; stagger work; (b) third-party content listens
  for the vanilla stages, so a start that skips them must still set them (or the stages they listen for never fire);
  (c) "the Vault 111 location covers both the internal vault and the elevator area", so OnLocationChange fires only
  when the player walks down the hill.

### 2.2 Start Me Up (TinyManticore), Nexus FO4 18946, and Start Me Up Redux
URLs: https://www.nexusmods.com/fallout4/mods/18946 ; Redux (translation page read):
https://www.nexusmods.com/fallout4/mods/70364
- **verified**: menu after the bathroom: Alternate, Quick (wake in the pod, skip pre-war) or Normal; an alternate
  "vault" start puts you in the cryopod as a pre-war dweller released by mistake. v5.5 sets "all of the MQ101 and MQ102
  stages" for compatibility. Codsworth treats you as his former owner; spouse/son lines removed from the player; some
  Codsworth lines were never rewritten. Bugs attributed to "the engine being overloaded with script commands", fixed
  with redundant checks, trigger boxes and leveled lists.
- **verified** (Redux): after chargen the player is put in the Commonwealth and a script **waits 20 seconds before
  setting MQ102 stage 10** to avoid engine overload; stage 10 triggers 15 (radio, Brotherhood signal). Added an MQ101
  stop stage to clean up aliases (the original lacked it). Vault activators that must not work are disabled. Players
  must wait two minutes in the bathroom. Known: endless loading or crash with large load orders; missing radio,
  Codsworth skipping his search, Preston not opening the museum door; frozen Nate/Nora outside the pod.
- Lessons: the cryo-pod start is precedented and works; the companion/spouse narrative is where it frays; alias cleanup
  on a stopped quest matters.

### 2.3 Skip (WasteTheLand), Nexus FO4 88418
URL: https://nexusmods.com/fallout4/mods/88418
- **verified**: "swapped only vanilla records and quest entries, with no scripts", advanced "with a trigger-box
  activator or by changing the MQ101Debug global" (FO4 also has an MQ101Debug). v001 a trigger setting MQ101 stage
  900; v002 changed to **stage 770 so the cryo corpses spawn properly**. Variants: no chargen (wake in pod, SPECIAL
  menu on exit, male default; female needs `player.sexchange`), chargen then teleport to the pod (keeps the Kellogg
  scene; adds a blurred-vision effect "with no workaround"), or start at the descending elevator. A brief white flash
  on new game comes from an engine image space modifier.
- Lessons: FO4 Bethesda also built an MQ101Debug lever; Vault 111 state (corpses) depends on which stage you jump to;
  skipping chargen leaves a default (male) body.

### 2.4 Others
- Another Life - Alternative Start (FO4; PT-BR translation page read: https://www.nexusmods.com/fallout4/mods/54157):
  **verified** the pre-war section is reframed as a synth memory; awake, the player is in an Institute processing room
  with a terminal for occupation, then sent to the Commonwealth; Vault 111 stays accessible. Mechanism not stated.
- SPECIAL Speed Start (Gritonic), https://www.nexusmods.com/fallout4/mods/99690: **verified** starts in Sanctuary with
  the main quest advanced past the vault; fixed a time-scale problem that stopped the Concord Preston scene (1.02).
  Lesson: global state (time scale) left by the intro must be reset by a skip.
- PC Gamer overview: https://pcgamer.com/begin-a-new-life-in-fallout-4-with-an-alternate-start-mod (not read; 429).

### 2.5 Fallout: London (FOLON team), a world without the base game's main quest
URLs: https://en.wikipedia.org/wiki/Fallout:_London ; reintegration mod https://www.nexusmods.com/fallout4london/mods/641 ;
https://www.nexusmods.com/fallout4london/mods/17?tab=posts ;
https://screenplaysmag.com/blog/character-creation-in-fallout-london-requires-a-new-save-file/
- **verified** (641's page): Fallout London "disables FO4's DLCs and starting quests". The pieces named:
  `Folon_DisablePlayerDialogueScript` (disables the DLC quests), a modified vanilla fragment `QF_MQ101_0001ED86`, and
  London's own `QF_FOLON_MQ101_0119ABAA`. The reintegration mod edits them so MQ101 reaches stages 900 and 1000, MQ102
  is not started or stopped, and a one-shot teleport to Vault 111 starts MQ102 at stage 6.
- **verified**: London has its own chargen (containment chamber, appearance, SPECIAL, traits) and needs a new game.
- **supported hypothesis** (comments on mod 17, unverified user reports): with FO4's quests revived in Boston, speech
  checks broke, the Pip-Boy map stayed on London, companions stuck in Boston, the Kellogg terminal froze.
- Lessons: this is the closest precedent to us in reverse (a total conversion on Creation Engine that keeps the base
  master but turns off its start, DLC and main quest from script). It shows (a) a "disable list" script is the
  practical way; (b) the world map (Pip-Boy/starmap) follows the active worldspace logic and is a pain point; (c)
  everything later reintegrated has to be re-enabled by stage manipulation.

---

## 3. Skyrim

### 3.1 Alternate Start - Live Another Life (Arthmoor), Nexus SSE 272 (LE 9557)
URLs: https://www.nexusmods.com/skyrimspecialedition/mods/272 ;
https://tes-mods.fandom.com/wiki/Alternate_Start_-_Live_Another_Life
- **verified**: the player starts in the Abandoned Prison (cell 00021594, navmesh edited) and picks a start at a
  statue of Mara; a choice is final only when the player sleeps in the bed (re-choose before); "Escape this cell"
  gives lockpicks; "Caught crossing the border" runs vanilla Helgen. Extension framework since 2.5.0 for other mods to
  add starts.
- **verified**: main-quest entry for non-Helgen starts: an innkeeper rumour about Helgen, or going to Helgen; joining
  the Civil War and reaching Whiterun resolves it via a guard line; **failsafe**: entering Dragonsreach's main hall
  without having heard of Helgen force-starts the main quest. The LAL quest closes after speaking to the Jarl. Some
  Helgen-referencing dialogue conditioned (4.2.2). "Failsafes force progression when players bypass expected triggers,
  since the Civil War cannot advance without the Main Quest's early content."
- **verified** incompatibilities: Opening Scene Overhaul (MQ101 conflicts, freeze on load); mods removing essential
  flags from Helgen NPCs; mods editing MQ101 / MQ102 / WERoad01 or fragments `QF_MQ101_0003372B`,
  `QF_MQ102_0004E50D`; duplicate loose copies of its scripts break quest control. Not removable mid-save; console
  bypass of the Whiterun gate discouraged.
- Why it is the gold standard (**supported hypothesis**, from the above): one hub, choices are reversible until
  committed, vanilla start stays available as an option, an extension API, explicit failsafes for every way the
  player can route around the intended trigger, long maintenance with patches against every known MQ101 editor, and
  clear "new game only / do not uninstall" rules.

### 3.2 Realm of Lorkhan (Custom Alternate Start), Nexus SSE 8328 / LE 70959; Skyrim Unbound, 111029
- **unresolved**: pages not read (proxy 429). Do not cite details until read.

---

## 4. Cross-cutting findings for our Vault 111 start

1. Two mechanisms dominate in Starfield: **(i) the MQ101Debug global** (SKK: 8 for New Atlantis, 5 for Vectera mine;
   FO4's Skip mod also uses FO4's MQ101Debug), and **(ii) overriding `StartupQuest_DO`** to launch a custom controller
   instead of MQ101 (No Ship Fast Start). Our option A (Quest.Stop from a start-game-enabled quest) has no public
   Starfield precedent that I found; it is the closest to Fallout London's script-disable approach. **supported
   hypothesis**: option A races MQ00/MQ101 start-up; the StartupQuest_DO path avoids the race by never launching them.
2. Skipping MQ101 has known systemic side effects in Starfield: Cruise Mode (SKK, Crimson, No Ship all restore it),
   sustenance (`PEO_SustenanceAllowed`), home-ship-dependent services (`SQ_PlayerShip` placeholder), the trait quest
   (TraitQuest 001687DB must be started after chargen), DLC gating (Shattered Space waits for MQ101), and later
   re-arming triggers (Kreet). **verified per mod pages**.
3. Chargen timing: every Starfield precedent shows chargen near the start, and SKK reports a real race (menu after
   chargen not appearing, controls locked). Console chargen (`slm player 1`) works mid-game but trait side effects
   (Dream Home, Kid Stuff) need stages set by hand. **verified per pages**.
4. FO4 precedents warn: the start-up window is overloaded with scripts; set stages late and staggered (20 s, 2 min
   waits), clean aliases on stopped quests, reset global state (time scale), and Vault 111 contents depend on stage.
5. Narrative fallout (Vasco, Constellation, parents, SSNN, NG+ content gated on MQ402) is the long tail; RAS and the
   NG+ tweaks mod show each item needs a condition or a story-manager fix.

---

## 5. Questions our new-game design must answer

1. **Does `Quest.Stop()` on MQ00/MQ101 from our start-game quest beat MQ101's first scene, controls lock and fades?**
   Why: no public mod uses this; SKK warns menus during start-up lock controls. How: in-game test with `sqv MQ101`,
   `sqv MQ00`, log timestamps; record what is on screen in the first 5 seconds.
2. **What is `StartupQuest_DO`, what does it start, and is overriding it cleaner than stopping MQ00/MQ101?** Why: No
   Ship Fast Start redirects start-up there without a race. How: read-only PC check of Starfield.esm (xEdit/our
   reader) and its fragment in ContentResources.zip.
3. **How does SKK's MQ101Debug 8 survive MQ00 stage 10 writing 10?** Why: decides whether option B works at all. How:
   PC check of MQ00's record (start-game flag, stage 10 conditions) and QF_MQ00 source; compare with SKK's ESM in xEdit
   (read-only, no redistribution).
4. **What does each MQ101Debug value (1, 2, 5, 8, 10) do?** Why: 5 = Vectera mine and 8 = New Atlantis per SKK's stop
   codes; a value might give a clean "no intro" state for free. How: PC grep of all MQ101Debug readers (precheck
   already lists them) plus an in-game test per value.
5. **Is Cruise Mode, sustenance (`PEO_SustenanceAllowed`) or any HUD feature off until MQ101 completes?** Why: every
   Starfield start mod restores Cruise Mode. How: PC check of globals/conditions; in-game check after our start.
6. **Does Starfield need a home ship (`SQ_PlayerShip`) for anything we use on the ground (HUD, menus, fast travel,
   scanner)?** Why: No Ship Fast Start had to create a placeholder ship. How: in-game test without a ship; owner
   decision whether a ship ever exists in our game.
7. **Does Game.ShowRaceMenu() at our time start the trait quest (TraitQuest 001687DB) and background perks?** Why: SKK
   had to start it after chargen; console chargen leaves traits half-applied. How: in-game `sqv` of the trait quest
   after chargen; PC read of what MQ101 does after chargen.
8. **Which chargen do we show: Starfield's full (backgrounds, traits) or appearance only?** Why: Starfield backgrounds
   and traits (Dream Home, Kid Stuff, Starborn) make no sense in the Commonwealth. Owner decision, then PC check of
   ShowRaceMenu's arguments.
9. **What does the player have when the Starfield fallback runs: does anything later re-arm MQ101 (Kreet, Vectera,
   the Lodge)?** Why: First We Crawl and RAS had to suppress Kreet triggers. How: PC check of story-manager nodes and
   triggers referencing MQ101; owner decision on whether Starfield space is reachable at all.
10. **Which of Starfield's ~144 start-game quests must be held off, and which must keep running (SQ_PlayerShip,
    SQ_ENV, followers, crime)?** Why: Fallout London shows a disable-list script is how a total conversion does it.
    How: first in-game `sqv` record, then a curated list (docs/newgame section 8 already plans this).
11. **Do we set FO4's MQ101/MQ102 equivalent stages for our own converted content and any future FO4-content plugins?**
    Why: FO4 mods hang off MQ102 10/15; our later phases (Codsworth, Preston) will need the same hooks. Owner decision
    on a stage contract for our quest (a public "vault exit" stage others can listen to).
12. **Do we stagger post-exit work (radio, Codsworth, workshops) with waits?** Why: FO4 Start Me Up Redux waits 20 s;
    SKK documents 2-minute workshop registration. How: design rule now; in-game timing later.
13. **Do we offer a hub with choices (LAL prison / RAS Unity) or a single fixed start?** Why: the gold standard is a
    reversible choice hub with the vanilla start kept as one option. Owner decision (option D).
14. **What guards our start against existing saves, NG+ and other start mods (SKK, RAS, Crimson)?** Why: every mature
    start mod validates state and refuses; RAS deactivates on existing saves; SKK mods detect each other. How: offline
    unit test of guard logic; a documented incompatibility list.
15. **What happens to Starfield DLC and Creations that wait on MQ101 completion (Shattered Space)?** Why: Crimson Start
    notes Shattered Space never starts without MQ101. Owner decision (stay dormant, or mark MQ101 complete later).
16. **Do we ever mark MQ101 complete (SKK option 1) or leave it stopped?** Why: completing it unlocks Cruise Mode/DLC but
    may trigger Lodge/Constellation scenes; stopping leaves dependent content dormant. How: in-game test both on a
    throwaway save.
17. **How do we keep Vault 111's own state coherent (corpses, spouse pod, cog door) if the player returns?** Why: the FO4
    Skip mod moved its jump to stage 770 so cryo corpses spawn; SKK keeps vault animations primed. How: later phase
    design; PC check of FO4 MQ101/MQ102 stage effects.
18. **Does any global state from the intro need resetting (time scale, image space, controls, HUD mode)?** Why: SPECIAL
    Speed Start fixed a time-scale bug; Skip notes an engine white flash. How: in-game check of `GetGlobalValue
    TimeScale`, controls and HUD after our start.
19. **What is the starmap/world map behaviour when the player is in our converted Commonwealth with no system/planet
    context?** Why: Fallout London's Pip-Boy map followed the wrong world. How: in-game test of the scanner/map on the
    surface.
20. **Do we add an LAL-style failsafe for every path that routes around our intended trigger (no elevator prompt
    answered, player clips out, save/load mid-start)?** Why: LAL's force-start on entering Dragonsreach is why it is
    robust. How: design list plus offline tests of the quest's state machine.

---

## Sources

- https://www.nexusmods.com/starfield/mods/5971
- https://www.nexusmods.com/starfield/mods/3050
- https://www.nexusmods.com/starfield/mods/6869
- https://www.nexusmods.com/starfield/mods/15092
- https://www.nexusmods.com/starfield/mods/15102
- https://www.nexusmods.com/starfield/mods/15094
- https://www.nexusmods.com/starfield/mods/6598
- https://www.nexusmods.com/starfield/mods/2076
- https://www.nexusmods.com/starfield/mods/1298
- https://www.nexusmods.com/starfield/mods/6145
- https://www.nexusmods.com/starfield/mods/16210
- https://www.nexusmods.com/starfield/videos/3341
- https://skkmods.com/starfield/
- https://starfieldportal.com/article/begin-starfield-as-an-instant-starborn
- https://exputer.com/news/games/starfield-mod-skip-intro/
- https://www.pcgamesn.com/starfield/alternate-start-mod
- https://www.escapistmagazine.com/how-to-skip-the-tutorial-in-starfield/
- https://www.nexusmods.com/fallout4/mods/29227
- https://www.nexusmods.com/fallout4/articles/1038
- https://www.nexusmods.com/fallout4/mods/18946
- https://www.nexusmods.com/fallout4/mods/70364
- https://nexusmods.com/fallout4/mods/88418
- https://www.nexusmods.com/fallout4/mods/54157
- https://www.nexusmods.com/fallout4/mods/99690
- https://www.nexusmods.com/fallout4london/mods/641
- https://www.nexusmods.com/fallout4london/mods/17?tab=posts
- https://screenplaysmag.com/blog/character-creation-in-fallout-london-requires-a-new-save-file/
- https://www.nexusmods.com/skyrimspecialedition/mods/272
- https://tes-mods.fandom.com/wiki/Alternate_Start_-_Live_Another_Life
