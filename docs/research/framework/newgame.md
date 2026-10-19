# Research framework: the new game start (Vault 111, no Starfield intro)

Owner: the Vault 111 new game thread (Claude-cloud). Folded into the framework index by the Next-phase research
framework thread; do not edit here from other threads, send changes through the coordinator.
Status: revision 1, 19 Oct 18:00Z. Five areas researched (notes 01 to 05); three more agents out (06 FO4's own Vault 111
quest chain, 07 retry of rate-limited sources, 08 saves, install and testing). No game touched; web sources only,
plus our own repo. Several key pages were rate limited (HTTP 429); claims resting on them are marked unresolved.
Raw agent notes: research/framework/newgame-notes/ (one file per area).

Labels as in docs/ai/research-log.md: verified (file, offset, command or a primary source), supported hypothesis,
unresolved. Every question names how it gets answered: offline check, PC read-only check, in-game test, or the owner.

## What exists already (verified unless marked)
- FO4SFNewGame.esm, staged on D: (PR #393, docs/newgame/vault111-start.md): Papyrus stops MQ00 and MQ101, puts the
  player by the pod in the converted Vault 111, ShowRaceMenu, cog door from its console, elevator to the core world.
- FO4SFQuestProbe.esm, staged (docs/questprobe/engine-questions.md): fragments, OnStageSet, alias markers, own quest
  type, own Story Manager branch.

## Areas
1. Alternate-start and skip-intro precedents (Starfield, Fallout 4, Skyrim)
2. Total conversions and merged games (Fallout London, Tale of Two Wastelands, Skyblivion and others)
3. Starfield's new-game flow and what depends on the main quest
4. Character creation, player identity, Pip-Boy and UI in Starfield
5. Tools and the modding ecosystem for a start mod

6. Fallout 4's own opening chain (MQ101, MQ102, Vault 111): what our start recreates or leaves out (agent out)
7. Retry of the rate-limited primary sources: Bethesda's guidelines, UESP main quest and NG+, Nexus start mods (agent out)
8. Saves, install, uninstall, versioning and repeatable start testing (agent out)

## The answer so far, in one paragraph
Every Starfield start mod hits the same wall: almost everything the player starts with (character creation, traits,
scanner, ship, fast travel, tutorials, Cruise Mode, sustenance, Shattered Space) hangs off MQ101, so skipping it
silently turns systems off and the mod must give back each one it wants. Our current design (stop MQ00 and MQ101 from
our own quest, then ShowRaceMenu in the vault) has no public Starfield precedent; the closest are a quest override of
`StartupQuest_DO` (No Ship Fast Start) and the debug global `MQ101Debug` (SKK Fast Start, Crimson Start). Fallout
London's worst start bug was a broken install silently giving the base game's opening, so a loud check matters more
than any clever start. Legally, the only model that has lasted is building from the user's own install and shipping no
Bethesda files; voice files are the known danger (Capital Wasteland was cancelled over them).

## How to read the questions
Each line: **question**, why it matters, how it gets answered (OFF offline in the cloud, PC read-only check on the PC,
GAME in-game test, OWNER decision), label, and the notes file that holds the sources (n01 to n05). Questions repeated
across notes are merged. Ids are stable (NG-A1 ...) so other files and threads can cite them.

## A. The start mechanism (how Starfield's intro is skipped)
- **NG-A1. What does `StartupQuest_DO` start, and is overriding it cleaner than stopping MQ00 and MQ101?** If it is
  the root, our quest never races MQ101's first scene or control locks. PC (Mutagen read of Starfield.esm, its fragment
  in ContentResources.zip). Supported hypothesis (No Ship Fast Start says it "redirects startup from MQ101"). n01, n03.
- **NG-A2. Is there an INI start-quest key in Starfield (TTW's `SCharGenQuest`, FO4 claims MQ101 is hard-coded)?** An
  INI route needs no record override at all. PC (strings in Starfield.exe, default INIs), then GAME. Unresolved. n02.
- **NG-A3. What does each `MQ101Debug` value do (1, 2, 5, 8, 10), and how does SKK's 8 survive MQ00 writing 10?** The
  debug skip is Bethesda's own fallback route. PC (QF_MQ00_00005790.psc, MQ00 conditions), then GAME per value.
  Verified: SKK uses 8 (New Atlantis spaceport), Crimson Start 5 (Vectera mine); our check verified MQ00 stage 10
  sets 10. The conflict is unresolved. n01, n03.
- **NG-A4. When our quest runs, has MQ101 already disabled controls or started a scene, and does `Stop()` release its
  input layers?** A stuck input layer is the commonest start failure (NG+ chargen redirect left Esc dead until a
  coc). PC (MQ101 stages 0 to 9 and its scripts), then GAME (`sqv MQ101`, our log). Unresolved. n01, n03, n04.
- **NG-A5. Do we leave MQ101 stopped, completed, or dormant?** Shattered Space and some Creations wait on MQ101
  complete; completing it may fire rewards and Constellation state. GAME on a throwaway save, then OWNER. Unresolved.
  n01, n02, n03.
- **NG-A6. Which other start-game-enabled Starfield quests must we hold off, and which must keep running?** The fence
  list. OFF/PC (Mutagen list of start-game-enabled quests and their Story Manager events), then a first `sqv` record
  in GAME. Unresolved. n01, n03.
- **NG-A7. Can anything restart MQ101 or the tutorial later (Kreet, Vectera, the Lodge, NG+ triggers)?** A late
  tutorial in the Commonwealth would break the illusion. PC (Story Manager nodes and triggers). Unresolved. n01, n03.
- **NG-A8. Does `GetFormFromFile` resolve correctly for our masters' plugin type?** SKK reports a wrong file index on
  small ESMs; our whole start resolves FO4Port ids that way. OFF: FO4Port carries far more than 4,095 records, so it
  cannot be a small master; check the core's and the start plugin's header flags too. Supported hypothesis that we are
  safe. n03, n05.
- **NG-A9. Run Once and existing saves.** Verified: our quest is StartGameEnabled plus RunOnce
  (dotnet/NewGame/Program.cs:267) and stands down when game days or level say it is not a new game
  (FO4SF_NewGameQuest.psc:149). Still open: does a newly added start-game quest start on an existing save in Starfield
  (CK wiki says yes for Skyrim)? GAME. Supported hypothesis. n03, n08.
- **NG-A10. Choice hub or one fixed start?** Live Another Life keeps the vanilla start as one option and lets the
  choice change until it is final; Roleplayers' Alternate Start does the same in Starfield. OWNER (option D in
  docs/newgame/vault111-start.md). n01, n02.
- **NG-A11. Design the start quest as a selector now (Vault 111 today; Far Harbor, Nuka-World or other Fallout starts
  later)?** Cheap now, costly later. OWNER. n02.
- **NG-A12. Failsafes: every way the player can skip the elevator exit (coc, tcl, fast travel) still ends in a sane
  state?** Live Another Life forces the main quest when the trigger is bypassed. OFF (state table and unittests), then
  GAME. n01.

## B. What MQ101 gives the player, and what we give back
- **NG-B1. Inventory of everything MQ101 grants or unlocks** (stage table 60 to 1800: chargen 60 to 105, scanner 305,
  Frontier and Vasco 320 to 345, first flight 400, fast-travel and menu tutorials 900 to 1020). PC (stage fragments),
  then a curated keep or drop list. Supported hypothesis (UESP). n03.
- **NG-B2. Are Cruise Mode, sustenance (`PEO_SustenanceAllowed`), or any HUD feature off until MQ101 completes?**
  Verified per mod page that start mods restore them. PC, then GAME. n01, n03.
- **NG-B3. Does the scanner work without MQ101's hand-over?** The scanner is the closest thing to a Pip-Boy screen
  we get for free. GAME. Unresolved. n03, n04.
- **NG-B4. Ship or no ship?** `MQ_TutorialQuest` fails silently with no `PlayerShip.GetShipRef()` (verified from
  Community Patch issue 714); No Ship Fast Start makes a hidden placeholder ship. OWNER, then a Papyrus log sweep for
  empty ship references in GAME. n01, n03.
- **NG-B5. Does fast travel and the map work in a worldspace with no planet data?** Players will expect fast travel
  between discovered places. GAME. Unresolved (the map thread's markers test feeds this). n03.
- **NG-B6. Gravity, oxygen, temperature and Cruise Mode (Free Lanes update, Apr 2026) in our world?** Starfield's
  survival layer may misfire off-planet. GAME. Unresolved. n03.
- **NG-B7. Does the intro leave state to reset: time scale, image space, controls, HUD mode?** FO4 start mods reset
  time scale. GAME. n01.
- **NG-B8. Do we publish a fixed "left the vault" stage, like FO4's MQ102 10 and 15, for later phases and other mods
  to listen to?** OWNER. n01 (and n06 when back).
- **NG-B9. Stagger work after the vault exit (radio, Codsworth, workshops)?** Start Me Up Redux waits 20 s; FO4's
  start is a known script bottleneck. Design rule now, timings in GAME. n01.

## C. Character creation and player identity
- **NG-C1. What do `ShowRaceMenu` modes 0 to 4 show when MQ101 is stopped, and which is looks-only?** Verified: same
  signature and modes as FO4 (0 chargen, 1 remake, 2 haircut, 3 surgery, 4 face paint). Which shows backgrounds and
  traits is unresolved. GAME (first test). n04.
- **NG-C2. Do traits and background perks work outside MQ101?** SKK must start TraitQuest 001687DB itself after
  chargen; Dream Home and Kid Stuff need stages set by hand and trigger on leaving the Lodge. GAME (`sqv`). n01, n03,
  n04.
- **NG-C3. Full creator (backgrounds, traits) or looks only? Starfield backgrounds kept, neutral, stripped, or Fallout
  versions? Harmful traits blocked?** Verified: backgrounds and traits are perks; the creator is chargenmenu.swf;
  the neutral background still grants three skills. OWNER. n04.
- **NG-C4. Where are SPECIAL and the name set, and is SPECIAL in scope for phase 1?** FO4 sets them pre-war with the
  Vault-Tec Rep, which our start skips; Start Me Up uses the cryo terminal. OWNER. n04.
- **NG-C5. Can we wait for the menu to close (`RegisterForMenuOpenCloseEvent` on "ChargenMenu")?** Utility has no
  `IsInMenuMode`. PC (ScriptObject.psc in ContentResources.zip). Unresolved. n04.
- **NG-C6. Which `SetInChargen`, `SetCharGenHUDMode`, `PrecacheCharGen` calls does MQ101 make, and are controls left
  locked after our menu? Do we need a save and load after chargen?** One Starfield start adds a save/load step. PC,
  then GAME. n02, n04.
- **NG-C7. Does the creator's camera and lighting work in our Vault 111 cell?** GAME. n04.
- **NG-C8. Converted FO4 dialogue checks the player's sex; what does a "they" player get?** Starfield offers they/them.
  OFF (scan FO4 conditions on GetIsSex in the converted dialogue). n04.
- **NG-C9. Quick start for replays (skip chargen with a preset)?** OWNER. n04.

## D. Pip-Boy and UI
- **NG-D1. SFSE or not?** It decides the whole UI plan: SFSE 0.2.21 is Steam-only, pinned to 1.16.244 and broken
  by past patches; reskins need no SFSE, new screens do (Menu Framework, OSF UI, Carbon UI). OWNER. Verified. n04, n05.
- **NG-D2. Phase 1 Pip-Boy: nothing, a terminal-menu item (the VaultTec S.P.E.C.I.A.L. pattern, no SFSE), or an SFSE
  view?** No Starfield Pip-Boy mod exists (verified). OWNER. n04.
- **NG-D3. Does the cog door keep FO4's "plug in the Pip-Boy" rule?** Ours opens from the console today. OWNER. n04.
- **NG-D4. Which Starfield HUD pieces to reskin or hide (loose Data\Interface SWFs replace whole files)?** Our test PC
  reads no loose files (sResourceDataDirsFinal=STRINGS\), so SWFs would ship in a ba2 too. OWNER, then GAME. n04.

## E. Starfield's world systems in our world
- **NG-E1. Do Starfield's radiant and story events (SSNN, encounters, Constellation calls) fire in our world?** Our
  probe's E5 tests our own Story Manager branch. OFF (event list), then GAME. n02, n03.
- **NG-E2. Which UI and systems depend on "One Small Step" being done?** PC and GAME. n02, n03.
- **NG-E3. Shattered Space and Creations that start their own quests: do we need a block plugin like Fallout London's
  DLC block?** OWNER, then PC scan. n01, n02.
- **NG-E4. Anything tied to a home system or Unity state our world lacks? What do NG+ and Unity do if MQ101 never
  completes?** GAME, OWNER. n02, n03.
- **NG-E5. Vault 111 coherence if the player returns (corpses, spouse pod, cog door)?** Later phase. n01 (n06).

## F. Install, launcher, versions, saves
- **NG-F1. How does the player choose our game over vanilla Starfield: a separate profile and INI, or in game?**
  OWNER. n02.
- **NG-F2. Loud broken-start check, both in the launcher and in game.** Fallout London's commonest failure. OFF
  (launcher check, unittest), in-game script line. n02.
- **NG-F3. Supported Starfield builds and what happens after an update?** Fallout London needed a downgrader and a new
  save. Launcher version gate (PR #394 records versions). n02, n05.
- **NG-F4. Full undo of the install (INIs, Plugins.txt).** OWNER policy; launcher already restores Data and
  Plugins.txt. n02.
- **NG-F5. Save versioning policy from day one.** OWNER, record in docs/ai/decisions.md. n02 (n08).
- **NG-F6. Refuse when an `sTestFile` INI entry exists (it makes Plugins.txt ignored)?** Verified behaviour. OFF plus
  PC read-only check. n05.
- **NG-F7. Do installed Creations or ContentCatalog.txt override our Plugins.txt? Do Mod Organizer 2 or Vortex users
  break our deploy (MO2 keeps INIs in its profile)?** PC read-only, then GAME. n05.
- **NG-F8. Completeness check: a manifest of expected files and hashes (TTW's size rule).** OFF, unittest. n02.
- **NG-F9. Game Pass users?** OWNER. n05.
- **NG-F10. Does `sStartingConsoleCommand` work on 1.16.244 (a test harness and a fallback start)?** GAME, Claude
  only. n05.

## G. Legal and distribution
- **NG-G1. Do we adopt "build from the user's own install, ship no Bethesda files" as written policy?** TTW lasted on
  it; Skyblivion had to replace 100% of assets. OWNER (and docs/ai/decisions.md). n02, n05.
- **NG-G2. FO4 voice files.** Capital Wasteland was cancelled after legal advice because Bethesda licenses the voices.
  OWNER, possibly legal advice. Verified. n02.
- **NG-G3. Bethesda's modding guidelines and the Creation Kit EULA on other games' assets.** Unread (rate limited);
  agent 07 retrying. OWNER after. n05.
- **NG-G4. Hosting: GitHub first, then Nexus (already decided); TTW says Bethesda asked sites not to host it.** OWNER.
  n02.

## H. Tools and build
- **NG-H1. Pin one Mutagen version with a byte-level golden-file test.** We build on 0.55.0-alpha.67; alpha.75 came
  out 19 Oct; stable is 0.54.4. OFF. n05.
- **NG-H2. Can the start plugin be built with Mutagen alone, no Creation Kit?** GAME (the staged build is the test).
  n05.
- **NG-H3. Starfield fragment script names and namespaces (`Fragments:Quests:QF_...`).** Verified for MQ00; the probe's
  E1 tests an unprefixed name. OFF/PC. n05.
- **NG-H4. Are scene records still bound by position in the plugin on 1.16.244?** PC, GAME. n05.
- **NG-H5. Small, medium or full master for the start plugin?** Changing type after release is unsupported. OWNER after
  OFF record count. n05.
- **NG-H6. Creation Kit command-line or windowless use?** Nothing documents it. PC (strings), manual run. n05.
- **NG-H7. Official Papyrus compiler only (Caprica unproven in game, Champollion's Starfield syntax guessed).** Already
  our route. n05.
- **NG-H8. Is our ba2 v2 right for scripts, or is v3 needed?** OFF header check, GAME log. n05.
- **NG-H9. Crash logger and xEdit that work on 1.16.244?** PC read-only. n05.
- **NG-H10. Lip files for reused FO4 voice lines through the Creation Kit (FaceFX; breaks on plugin names with
  spaces)?** Manual CK test. n05.
- **NG-H11. Build time and CPU for a full start build.** Measure on the PC, docs/ai/optimization.md. n02.

## I. Voice, dialogue and the opening scenes (from the framework thread's findings, leads to verify)
- **NG-I1. Does the start use any FO4 voice lines (Nate or Nora, Codsworth, the Vault-Tec Rep)?** The opening is
  heavily voiced and Capital Wasteland died over audio; ties to G2 and to `scripts/actors/codsworth_voice.py`. OWNER,
  then a written question to Bethesda or Nexus staff. findings/precedents.md Q1, Q17.
- **NG-I2. What does the dialogue list show for FO4 player choices: the prompt, the full line, or both?** The first
  scenes are choice-heavy and a silent player turns paraphrases into guesswork. One converted scene in game with each
  option, then OWNER. findings/people-story.md Q1.
- **NG-I3. Which spouse and player-addressed lines break with a silent player (monologue INFOs in MQ101 and MQ102)?**
  OFF (record scan of FO4 INFOs with no choice), then OWNER: keep text, cut, or replay. findings/people-story.md Q2.
- **NG-I4. Can Starfield's looks menu open in our cell (`showlooksmenu player 1` per Nexus 8015), and do we curate
  presets that approximate FO4 looks?** Overlaps C1; FO4 sliders do not map. GAME. findings/people-story.md Q3.
- **NG-I5. Silent placeholder voice files for text-only NPC lines, or Starfield Silent Voice (SFSE)?** Unvoiced lines
  flash past. GAME with one shared silent WEM id, OWNER on SFSE. findings/people-story.md Q11.

## J. Proving the start works, repeatably
- **NG-J1. A scripted "new game to first exit" run with checkpoints (stage transitions with timestamps).** Phase 1
  acceptance needs a repeatable proof, not one playthrough. OFF design (our quest already logs each step), then PC.
  findings/testing-qa.md Q1.
- **NG-J2. How to start a new game unattended with no intro (sStartingConsoleCommand bat, Papyrus on load, a scripted
  menu click)?** The runner today loads saves. PC probe, 5 runs each. findings/testing-qa.md Q2; NG-F10.
- **NG-J3. Does `Debug.QuitGame` work in retail for a clean end of run?** PC probe, whitelist is the owner's call.
  findings/testing-qa.md Q3.
- **NG-J4. Can the start be built and run with no SFSE at all?** Ours is data plus Papyrus today (supported
  hypothesis: ShowRaceMenu and SetInChargen exist in Starfield's sources). The first proof answers it.
  findings/starfield-toolchain.md Q2.
- **NG-J5. What happens to the start quest's overrides after a Starfield patch?** Diff Starfield.esm's start quests
  across two game versions (Fallout London's next-gen lesson). OFF plus PC. findings/precedents.md Q2;
  findings/starfield-toolchain.md Q1, Q3.

## Owner decisions, gathered (for the roadmap talk)
A5 MQ101 end state; A10 hub or fixed start; A11 selector design; B4 ship; B8 published vault-exit stage; C3 creator
scope and backgrounds; C4 SPECIAL; C9 quick start; D1 SFSE; D2 Pip-Boy; D3 cog door rule; D4 HUD; E3 DLC block; E4
NG+ and Unity; F1 how the player picks our game; F4 undo policy; F5 save versions; F9 Game Pass; G1 to G4 legal and
hosting; H5 plugin type; I1 voice lines; I2 choice text; I3 silent-player lines; I5 silent voice route.

## Cheapest first (offline or read-only, no game)
A1, A3, A4, A6, A7, B1, C5, C6 (all read Starfield.esm and ContentResources.zip on the PC, read only); A8 header flags;
C8 dialogue scan; F6, F8; H1, H8. The first in-game proof (after the v6e test, new game, owner's word) then covers
A4, A5, A9, B2, B3, B5, B7, C1, C2, C6, C7 in one session with `sqv MQ101`, `sqv` on our quest and the Papyrus log.
