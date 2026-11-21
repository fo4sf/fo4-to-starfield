// NewGame: a Fallout 4 new game in Starfield (docs/newgame/vault111-start.md): one plugin, FO4SFNewGame.esm, whose
// quest is Starfield's startup quest (the DefaultObject StartupQuest_DO overridden to it: our own start, the owner's
// pick F, 29 Oct), so a New Game starts it instead of Starfield's opening. It puts the player at their cryo pod in the
// converted Vault 111 (FO4Port.esm) during the first load and takes them up the elevator onto the Commonwealth
// (FO4TerrainCore.esm). Claude's project.
//
//   points <Fallout4.esm> <out points.json> [--pod-ref <hex>] [--pod-step -2.5] [--terminal-ref <hex>]
//        reads Fallout 4 only: in Vault111Cryo (000016D8) the player's cryo pod (the one placed reference whose
//        EditorID names both the player and a pod, or --pod-ref), the cog door console MQ102GearDoorConsoleREF 00091A49,
//        the cog door Vault111GearDoorREF 000330C3, the elevator platform V111ElevatorREF 000244EB and its floor stand
//        marker RespecMoveMarker 0001B29E, the surface arrival of the ride (the XTEL of Vault111InteriorAutoLoadDoorREF
//        0001F180), and the cell's terminals (every placed reference of a TERM, nearest the pod first, or --terminal-ref
//        alone: the SPECIAL terminal, NG-C4); MQ102's name. Interior positions in metres in the port's frame and exterior
//        ones in the core's (both FO4 position / 70); headings in degrees.
//   write <Starfield.esm> <FO4Port.esm> <port formids.json> <FO4TerrainCore.esm> <points.json> <out dir>
//         [--plugin FO4SFNewGame.esm] [--hold MQ00,MQ101,MQ101PostQuest,MQ_TutorialQuest_Misc04,SQ_ENV] [--mq101debug <n>]
//         [--no-mq101debug] [--debug-after-hold <n>] [--no-looks] [--race-menu-mode <n>] [--no-special] [--no-version] [--build-version <n>]
//         [--exit-anchor <REFR EditorID>] [--keep-inventory | --vault-suit <ARMO EditorID>] [--no-o2-fill] [--allow-temporary-anchor]
//        the plugin, mastered on Starfield.esm only: QUST FO4SF_NewGame (run once, NOT start game enabled; stages 1 /
//        10 / 20 / 30 / 40 / 200, the published stage contract of make_newgame.py STAGE_CONTRACT; objective 10), the
//        override of Starfield's DFOB StartupQuest_DO naming it (the writer refuses a Starfield.esm whose
//        StartupQuest_DO is missing or names another quest than MQ101: the start it replaces must be the one it was
//        written for), the quest carrying
//        FO4SF_NewGameQuest (and FO4SF_NewGameLooks unless --no-looks, FO4SF_NewGameSpecial unless --no-special) with
//        their properties, MESG FO4SF_NewGameElevator and MESG FO4SF_NewGameStart (two buttons each: the elevator
//        prompt, and the opening choice "Create character" or "Quick start" the looks script shows, NG-6 / NG-C9), and
//        no override of Starfield's GLOB MQ101Debug by default (each of MQ101's stage-0 entries moves the player into the
//        game; the first build's 10 was the pirate-fight developer start, the second build's 2 matched no entry and left
//        the new game on its loading screen, 28 Oct), or --mq101debug <n> to override it for an experiment. The quest
//        script reads the global (DebugGlobal) for its guard line and writes DebugAfterHold (default 2, what MQ102 to
//        MQ305 write once the intro is over; --debug-after-hold <n>, 0 writes nothing) right after the hold-off's
//        first pass, once the player has been moved (the owner's decision NG-2: we set it ourselves).
//        Unless --no-version: GLOB FO4SF_NewGameVersion (constant, the build's version number, --build-version <n>,
//        default 1) and a player alias on the quest carrying FO4SF_NewGameVersion, which compares that GLOB to the
//        version the save was started with on every load (NG-15 / NG-L2).
//        --race-menu-mode <n> is the uiMode the looks script passes to Game.ShowRaceMenu (its RaceMenuMode property;
//        default 2, looks only: body and face, seen in the C1 session on 15 Nov; 1 still shows Traits; 0 is the
//        full creator with Starfield's Background and Traits pages). Unless
//        --no-special: seven AVIF FO4SF_Special_<stat> (Strength to Luck, the SPECIAL stats as our own actor values),
//        MESG FO4SF_NewGameTerminal (the prompt at the vault terminal, two buttons) and MESG FO4SF_NewGameSpecial (the
//        allocation: one button per stat, Reset, Confirm, Leave), which the SPECIAL script drives (NG-5 / NG-C4). The
//        port and the core are read for the ids and positions the scripts resolve at run time with Game.GetFormFromFile
//        (plugin-local ids): the vault anchor (a persistent reference of FO4Port_Vault111Cryo, the COC marker first; a
//        cell with none is refused unless --allow-temporary-anchor, which anchors on the temporary COC marker itself
//        and has the script load the cell with Debug.CenterOnCell before the move: the AnchorTemporary / VaultCell
//        properties; --require-persistent-anchor, the default since newgame_v11, is kept for old command lines),
//        the cog door (formids.json
//        REFR:FO4Port_Vault111Cryo:0330C3:...; 0 when the port has none), the terminal (the first of points' terminals
//        the port carries, a persistent one preferred; 0 when it carries none, the prompt then watches points' spot)
//        and the exit anchor (the core's Vault 111 map marker).
//        The inventory reset (default on since S13 row 2, NG-K8): the quest script empties the player's inventory
//        (whether quest items stay is unverified) once the player is confirmed in the vault (before stage 10) and logs
//        the count removed; --keep-inventory builds without it (the player keeps what Starfield gives), and
//        --clear-inventory (the default now) is kept for old command lines. --vault-suit <EditorID> (refused with
//        --keep-inventory) names an ARMO of FO4Port.esm the script then adds and equips, resolved here by EditorID
//        with the same owner check as the other ids (refused when the port lacks it, has two, or it is another
//        plugin's record). With the reset the quest also adds 0002E2 +100 (the O2 capacity a suit's pack gives,
//        which clears the O2/CO2 dial) once; --no-o2-fill leaves it out. SQ_ENV, Starfield's environment system for
//        the player, is on the default hold list (S13 row 2b).
//   check <plugin> <Starfield.esm> <FO4Port.esm> <port formids.json> <FO4TerrainCore.esm> <points.json> [same options]
//        reads the plugin back and checks every record, property and id the script relies on (exit 1 on a problem).
//   selftest <scratch dir>
//        synthetic Fallout4.esm, Starfield.esm, port and core; points + write + check (every option variant, and the
//        temporary-anchor build on a port without a persistent reference), and mutations check rejects; then the
//        records selftest.
//   records <Fallout 4 Data dir> --out <report.txt> [--sf-data <Starfield Data dir>] [--port <FO4Port.esm>] [--nearest <n>]
//        the read-only PC record reader for newgame.md sections K and N (NG-K1, K2, K4, K9, N4 and the anchor
//        picks): Records.cs. Writes only --out.
//   records-selftest <scratch dir>
//        synthetic plugins covering each records section; the report, the missing-input reports and that only --out
//        is written are checked.
// Nothing is deployed and no game file is written.
using System.Globalization;
using System.Text.Json;
using Mutagen.Bethesda;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Cache;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Strings;
using Noggog;
using F4 = Mutagen.Bethesda.Fallout4;
using SF = Mutagen.Bethesda.Starfield;

if (args.Length == 0) return NewGame.Usage();
try
{
    return args[0] switch
    {
        "points" when args.Length >= 3 => NewGame.Points(args[1], args[2], NewGame.ArgOrNull(args, "--pod-ref"), NewGame.Opt(args, "--pod-step", NewGame.DefaultPodStep), NewGame.ArgOrNull(args, "--terminal-ref")),
        "write" when args.Length >= 7 => NewGame.Write(args[1], args[2], args[3], args[4], args[5], args[6], NewGame.Options.From(args)),
        "check" when args.Length >= 7 => NewGame.Check(args[1], args[2], args[3], args[4], args[5], args[6], NewGame.Options.From(args)),
        "selftest" when args.Length >= 2 => NewGame.SelfTest(args[1]),
        "records" when args.Length >= 2 && !args[1].StartsWith("--") => NewGameRecords.Run(args[1], NewGame.ArgOrNull(args, "--out"), NewGame.ArgOrNull(args, "--sf-data"),
                                                                                             NewGame.ArgOrNull(args, "--port"), (int)NewGame.Opt(args, "--nearest", NewGameRecords.DefaultNearest)),
        "records-selftest" when args.Length >= 2 => NewGameRecords.SelfTest(args[1]),
        _ => NewGame.Usage(),
    };
}
catch (NewGame.Refusal e)
{
    Console.Error.WriteLine("refused: " + e.Message);
    return 2;
}

static class NewGame
{
    public const string Plugin = "FO4SFNewGame.esm", World = "FO4Core_Commonwealth", VaultCell = "FO4Port_Vault111Cryo";
    // the plugins the script resolves its ids in (FO4SF_NewGameQuest.psc VaultPlugin and CorePlugin): every resolved
    // reference must be owned by the plugin of that name, or the script would ask for the wrong record
    public const string PortPlugin = "FO4Port.esm", CorePluginFile = "FO4TerrainCore.esm";
    public const string QuestEdid = "FO4SF_NewGame", ScriptName = "FO4SF_NewGameQuest", LooksScript = "FO4SF_NewGameLooks", SpecialScript = "FO4SF_NewGameSpecial";
    public const string MessageEdid = "FO4SF_NewGameElevator", StartMessageEdid = "FO4SF_NewGameStart", ExitAnchorEdid = "FO4Core_CommonwealthMapMarkerVault111";
    public const string TerminalMessageEdid = "FO4SF_NewGameTerminal", SpecialMessageEdid = "FO4SF_NewGameSpecial", SpecialMessagePage2Edid = "FO4SF_NewGameSpecialPage2", SpecialAvifPrefix = "FO4SF_Special_";
    public const string ReturnMsgEdid = "FO4SF_NewGameReturn",
                        ModePickMsgEdid = "FO4SF_NewGameModeMsg",
                        SurvivalPickMsgEdid = "FO4SF_NewGameSurvivalMsg",
                        WarfareDiffMsgEdid = "FO4SF_WarfareDifficultyMsg",
                        WarfareGroupMsgEdid = "FO4SF_WarfareGroupMsg",
                        WarfareSpotMsgEdid = "FO4SF_WarfareSpotMsg",
                        NoPipboyMsgEdid = "FO4SF_NoPipboyConsoleMsg",
                        PipboyAcquiredGlobEdid = "FO4SF_PipboyAcquired",
                        PipboyWristArmorEdid = "FO4SF_PipboyWrist",
                        PipboyCorpseActiEdid = "FO4SF_PipboyCorpsePickup",
                        PipboyCorpseRefEdid = "FO4SF_PipboyCorpsePickupRef",
                        GearDoorConsoleActiEdid = "FO4SF_GearDoorConsole",
                        GearDoorConsoleRefEdid = "FO4SF_GearDoorConsoleRef",
                        ExitFallbackMsgEdid = "FO4SF_NewGameExitFallbackMsg",
                        StartRoomCellEdid = "FO4SF_StartRoomCell",
                        StartRoomMarkerRefEdid = "FO4SF_StartRoomMarkerRef",
                        StoryLineMsgEdid = "FO4SF_NewGameStoryLineMsg",
                        ExitNeedSpecialMsgEdid = "FO4SF_NewGameExitNeedSpecialMsg",
                        VaultPistolRefEdid = "FO4SF_Vault111PistolRef",
                        VaultAmmoRefEdid = "FO4SF_Vault111AmmoRef";
    public const uint QuestId = 0x800, MessageId = 0x801, StartMessageId = 0x802, TerminalMessageId = 0x803, SpecialMessageId = 0x804;   // the overrides keep Starfield's ids
    public const uint ModePickMsgId = 0x806,
                      SurvivalPickMsgId = 0x807,
                      WarfareDiffMsgId = 0x808,
                      WarfareGroupMsgId = 0x809,
                      WarfareSpotMsgId = 0x80A,
                      ReturnMsgId = 0x80B,
                      // 0x80C reserved (former FO4SF_PipboyAcquired GLOB; now owned solely by FO4SFCoreValues.esm:000865)
                      PipboyWristArmorId = 0x80D,
                      PipboyCorpseActiId = 0x80E,
                      PipboyCorpseRefId = 0x80F,
                      // 0x810..0x816 reserved (retired SPECIAL AVIF / early prototype IDs moved to FO4SFCoreValues.esm)
                      NoPipboyMsgId = 0x817,
                      GearDoorConsoleActiId = 0x818,
                      GearDoorConsoleRefId = 0x819,
                      ExitFallbackMsgId = 0x81A,
                      SpecialMessagePage2Id = 0x81B,
                      StartRoomCellId = 0x81C,
                      StartRoomMarkerRefId = 0x81D,
                      StoryLineMsgId = 0x81E,
                      ExitNeedSpecialMsgId = 0x81F;
    public const uint VaultPistolRefId = 0x820, VaultAmmoRefId = 0x821;
    // Retired local FormIDs in FO4SFNewGame.esm: never reused so older saves or external checks never alias new records onto retired forms.
    public static readonly uint[] ReservedFormIds = { 0x80C, 0x810, 0x811, 0x812, 0x813, 0x814, 0x815, 0x816 };
    public const int MaxMessageButtons = 7;
    public const int BackdropNone = 0, BackdropEmptyCell = 1, BackdropTitleCard = 2, BackdropSetupMenu = 3, DefaultStartChoiceBackdrop = BackdropEmptyCell;
    public const uint SfChronomarkArmorId = 0x0D4893, SfFallbackJumpsuitId = 0x01D1D7, SfConsoleActiTemplateId = 0x1CCAC2, SfMapMarkerStaticId = 0x000010,
                      SfVaultPistolId = 0x24561C, SfVaultAmmoId = 0x2B5598;
    public const int VaultAmmoCount = 48;
    public const string PortPipboyStaticEdid = "FO4Port_NpcPipboyGroundTake01";
    public static readonly string[] StartButtons = { "Quick start", "Create character" };
    public static readonly string[] ExitButtons = { "Continue", "S.P.E.C.I.A.L.", "Stay" };
    public static readonly string[] ExitNeedSpecialButtons = { "OK" };
    public static readonly string[] ExitFallbackButtons = { "Go up to the Commonwealth", "Retry lift" };
    public static readonly string[] ReturnButtons = { "Ride down to Vault 111", "Stay" };
    public static readonly string[] ModeButtons = { "Story", "Warfare" };
    public static readonly string[] SurvivalButtons = { "Survival: No", "Survival: Yes" };
    public static readonly string[] WarfareDiffButtons = { "Easy", "Normal", "Hard", "Very Hard" };
    public static readonly string[] NoPipboyButtons = { "OK" };
    public const bool DefaultFadeHold = true;
    // Our own start (the owner's pick F, 29 Oct): Starfield's DefaultObject StartupQuest_DO (Starfield.esm 00562D;
    // verified, the 21 Oct records report: it names MQ101) names the quest the engine starts on a New Game (supported
    // hypothesis: what reads the record is not in that report, NG-N4; the shipped precedents below rely on it). The
    // plugin overrides it to name FO4SF_NewGame, which is therefore NOT start game enabled (so an existing save should
    // never start it). Shipped precedent: Roleplayers' Alternate Start and No Ship Fast Start override the same record
    // (research, 28 Oct). The deployment gate's start check (fo4sf.core.preflight check_start, OWN_START) passes
    // exactly one plugin of ours overriding it, at that id.
    public const string StartupEdid = "StartupQuest_DO";
    public const uint StartupId = 0x00562D;
    public const string CoreValuesPlugin = "FO4SFCoreValues.esm", TestModeGlobEdid = "FO4SF_TestModeEnabled",
                        StartCardOpenGlobEdid = "FO4SF_StartCardOpen",
                        GameModeGlobEdid = "FO4SF_GameMode",
                        SurvivalStartGlobEdid = "FO4SF_SurvivalStart",
                        SurvivalLockedGlobEdid = "FO4SF_SurvivalLocked",
                        StartDifficultyGlobEdid = "FO4SF_StartDifficulty",
                        WarfareFactionGlobEdid = "FO4SF_WarfareFaction",
                        WarfareStartIndexGlobEdid = "FO4SF_WarfareStartIndex",
                        StartChoiceDoneGlobEdid = "FO4SF_StartChoiceDone",
                        StartNeutralSpotGlobEdid = "FO4SF_StartNeutralSpot",
                        StoryLineGlobEdid = "FO4SF_StoryLine",
                        StartPlaceRowGlobEdid = "FO4SF_StartPlaceRow",
                        H00SkipLoadingHookGlobEdid = "FO4SF_H00_SkipLoadingHook",
                        H00ClearChargenGlobEdid = "FO4SF_H00_ClearChargenBeforeSurface",
                        H00SkipArrivalDiscoveryGlobEdid = "FO4SF_H00_SkipArrivalDiscovery",
                        H00SkipMapSetupGlobEdid = "FO4SF_H00_SkipMapSetup",
                        H00SkipRouteLootGlobEdid = "FO4SF_H00_SkipRouteLoot",
                        H00SkipMissionActorsGlobEdid = "FO4SF_H00_SkipMissionActors",
                        H00SkipLandingQuestsGlobEdid = "FO4SF_H00_SkipLandingQuests",
                        H00SkipSurfaceSetPosGlobEdid = "FO4SF_H00_SkipSurfaceSetPos";
    // The save version check (NG-15 / NG-L2, the owner's decision 2026-10-19: a save version from v1). GLOB
    // FO4SF_NewGameVersion holds the build's version number (--build-version <n>, default DefaultBuildVersion;
    // make_newgame.py DEFAULT_BUILD_VERSION is held equal by tests/test_newgame.py). It is flagged Constant so the
    // value is the plugin's, not the save's: the CK documents a constant global as not saved, so a save made under
    // build 1 reads the installed build's number when loaded under build 2; whether Starfield's save keeps the rule is
    // unverified until the PC run (the log's "version load" line is the proof). The quest's alias 0 is forced to the
    // player (PlayerRef 00000014, the engine's fixed id; FO4SF_Probe reads the player as ref 20, door_probe.py
    // PLAYER_ID) and carries FO4SF_NewGameVersion, which records the GLOB's value when the alias fills (a new game)
    // and compares it on OnPlayerLoadGame (on Actor and ReferenceAlias, verified, ContentResources.zip PC read 19 Oct).
    public const string VersionGlobEdid = "FO4SF_NewGameVersion", VersionScript = "FO4SF_NewGameVersion", PlayerAliasName = "Player";
    public const uint VersionGlobId = 0x805, PlayerRefId = 0x000014, PlayerAlias = 0;
    public const float DefaultBuildVersion = 1f;
    // SPECIAL at the vault terminal (NG-5 / NG-C4, the owner's decision 2026-10-19): FO4's numbers, base 1 each, 21
    // points to spend, 10 at most per stat (make_newgame.py SPECIAL_*, held equal by tests/test_newgame.py; the script's
    // defaults are the same). The buttons of MESG FO4SF_NewGameSpecial, in order: the seven stats, Reset, Confirm, Leave
    // (ten buttons, FO4's MESG limit; whether Starfield's message box shows ten is unverified until the PC run). The
    // AVIF shape is minimal (name, abbreviation, SpecialAttribute type, default 1, min 1, max 10, and the record's own
    // flags for those three numbers: DefaultToOne, MinimumOne, MaximumTen, Mutagen's names for Starfield's AVFL bits):
    // nothing in this repo reads a Starfield AVIF back in full, so the shape is unverified until the PC run (xEdit
    // opens the plugin).
    public static readonly string[] SpecialNames = { "Strength", "Perception", "Endurance", "Charisma", "Intelligence", "Agility", "Luck" };
    public static readonly string[] SpecialExtraButtons = { "Reset", "Confirm", "Leave" };
    public static readonly string[] SpecialPage1Buttons = { "Strength", "Perception", "Endurance", "Next (C / I / A / L)", "Reset", "Confirm", "Leave" };
    public static readonly string[] SpecialPage2Buttons = { "Charisma", "Intelligence", "Agility", "Luck", "Back (S / P / E)", "Confirm", "Leave" };
    public const int SpecialBase = 1, SpecialPoints = 21, SpecialMax = 10;
    // Game.ShowRaceMenu(ObjectReference akMenuTarget = None, int uiMode = 0, ...) (verified, Starfield's Game.psc): the
    // names are FO4's (0 chargen, 1 remake, 2 haircut, 3 surgery, 4 face paint, NG-C1) and do not describe Starfield's
    // menu; the in-game C1 session (with MQ101 stopped) settled the looks-only mode, the owner's decision NG-C3.
    // The default is 2, seen looks-only in the C1 session (15 Nov, owner PC: only BODY and FACE; mode 1 still showed
    // TRAITS): 0 shows Starfield's Background and Traits pages, Starfield new-game content the strip-down rule takes
    // out (system model S13); --race-menu-mode 0 builds that full creator
    public const int DefaultRaceMenuMode = 2;
    // The starting inventory (NG-K8 / NG-N3): FO4's MQ101 runs RemoveAllItems at stages 0 and 900 (verified from the SKK
    // FastStart article, research note 06); Starfield's MQ101 stage 0 runs RemoveAllItems and equips the miner suit (PC
    // read 19 Oct), and since newgame_v11 MQ101 never runs. What Starfield then leaves in the player's inventory is
    // unresolved (run 4), and the strip-down rule takes Starfield's own new-game content out (system model S13 row 2),
    // so the reset is ON by default: the quest script's ClearInventory property (true) and VaultSuitId (0, none until the
    // port has a vault suit). The script calls ObjectReference.RemoveAllItems(None, false, false) (written with FO4's
    // arguments; Starfield's third parameter is abRespectTargetCapacity, so whether quest items stay is unverified)
    // after the move into the pod, and with --vault-suit it adds and equips the port's ARMO. --keep-inventory builds
    // the old start, where the player keeps Starfield's items.
    public const bool DefaultClearInventory = true;
    // The vault anchor's mode (PC result 21 Oct, the port installed then: FO4Port_Vault111Cryo had 0 persistent
    // references of 1,166, its COC marker 001338 and every terminal temporary, so the persistent-only resolver refused
    // the build). Verified 16 Oct: a temporary reference of an unloaded cell resolves to None via Game.GetFormFromFile,
    // and a MoveTo onto a non-persistent reference fails. So with no persistent reference the writer can anchor on the
    // temporary COC marker and have the script load the cell first (Debug.CenterOnCell(VaultCell), the AnchorTemporary
    // property; whether Starfield's CenterOnCell works in retail is unverified, the precheck reads its declaration).
    // The port of run 3 (28 Oct) has its COC marker persistent. Since newgame_v11 (our own start) the temporary mode is
    // refused by default: its centering comes during the first load, and when it moves nobody the start cannot tell and
    // hands nothing back, so that load would never end (29 Oct review on #588). --allow-temporary-anchor builds it on
    // request; --require-persistent-anchor, the default now, is kept for old command lines.
    public const bool DefaultRequirePersistentAnchor = true;
    // GLOB MQ101Debug (Starfield.esm 0A7D31): MQ101's stage 0 has 12 log entries, ten conditioned on it (records report,
    // PC 21 Oct): 0 the normal intro, 1 and 3 to 10 developer starts; entry 0 is the NG+ start (PlayerUnityTimesEntered
    // >= 1) and entry 11 has no condition (it only ghosts Lin, Heller and Barrett). Every matching entry's fragment is what moves the player into the game (entry 2:
    // PlayerREF.moveto(CharGenStartMarker) then WaitFor3dLoad; entry 10: SetStage 210 and 250, the pirate fight the
    // first build's override of 10 sent the owner to, run 1 of 28 Oct). A value no entry matches moves nobody: the
    // second build's 2 left the new game on its loading screen for ever: the quest started (its version alias logged)
    // but its OnQuestInit never fired (run 2 of 28 Oct). With our own start MQ101 never runs, so the default build still
    // writes NO override and the quest script writes DefaultDebugAfterHold into the global after the hold-off's first
    // pass: 2 is the value the main quests' developer skip-start stages write (a normal intro leaves 0), matches no
    // start, and opens PEO_SustenanceAllowed's "MQ101Debug != 0", whose normal route (MQ101 stage 310) is never reached
    // (NG-2, NG-M1).
    // --mq101debug <n> overrides the record for an experiment; --debug-after-hold <n> changes the write (0: none).
    public const int DefaultDebugAfterHold = 2;
    public const string DebugGlobEdid = "MQ101Debug";
    // Starfield.esm, verified: QuestTypeSideQuest (the mission, Missions tab), GameDaysPassed (record value 0; the game
    // reads about 0.3335 one second into a new game, 28 Oct), COCMarkerHeading (the port places each cell's COC marker
    // on it, WP10)
    public const uint QuestTypeSideId = 0x047600, GameDaysPassedId = 0x000039, CocMarkerId = 0x000032;
    public const string QuestTypeSideEdid = "QuestTypeSideQuest", GameDaysPassedEdid = "GameDaysPassed";
    // Fallout4.esm, verified in docs/spikes/B4-mission-anatomy.md section 3; Fo4PlatformMarker (RespecMoveMarker 0001B29E)
    // sits on the center of b_Platform at the bottom of the shaft (-77.742, -3.958, -1.751 m), whereas V111ElevatorREF's
    // NIF origin 000244EB (-70.392, -2.742, -0.114 m) sits 7.45 m forward on the catwalk approach.
    // DefaultPodStep = -2.5f steps 2.5 m along -Y in front of pod 0004A011 onto (9.143, -6.614, -1.029) m (walkable on PC,
    // settle drop 0.12 m); heading stays Deg(pod.Rotation.Z) = 0 (do not turn the pod).
    public const float DefaultPodStep = -2.5f;
    public const uint Fo4VaultCell = 0x0016D8, Fo4Console = 0x091A49, Fo4CogDoor = 0x0330C3, Fo4Platform = 0x0244EB,
                      Fo4PlatformMarker = 0x01B29E, Fo4ExitDoor = 0x01F180, Fo4MQ102 = 0x01CC2A,
                      Fo4PipboyPickup = 0x075039, Fo4PipboySkeleton = 0x0AB6AF;
    // the quests held off on a new game: the main-quest start and the opening, and the two MQ101's stage 9000 starts
    // when MQ101 is stopped (MQ101PostQuest always, MQ_TutorialQuest_Misc04 unless the player entered the Unity; PC
    // read 19 Oct, NG-19 / NG-N1), which the script stops on a second pass once the vault has loaded; and SQ_ENV
    // (248D20), Starfield's environment system for the player (S13 row 2b, owner decision of 15 Nov): its player alias
    // gives 17 ENV abilities (suit integrity damage, the O2 adjustment, the extreme-environment soak, water damage,
    // afflictions; PC read of 15 Nov, result-pc-read-s13-2b-env), and no game setting switches them off. Not SQ_ENV's:
    // HumanRace's two ENV_AFFL_AddHitSpellPerk abilities and placed local hazards (vents, pools, clouds), which the PC
    // run checks. Stopping the quest clears the alias and so its spells (Bethesda alias rule; that Starfield removes
    // them, and that nothing else breaks without SQ_ENV, is unverified until the PC run). Fallout radiation comes later
    // from our own systems (S9). A --hold list without SQ_ENV keeps Starfield's environment.
    const string OpeningEdid = "MQ101";
    public static readonly string[] HoldCore = { "MQ00", "MQ101", "MQ101PostQuest", "MQ_TutorialQuest_Misc04", "SQ_ENV" };
    // S13 row 5, the first group (owner, 15 Nov: "Companions first"): Starfield's companion and crew quests, the
    // start-game-enabled ones the PC found running in our new game at stage 10 and 200 (result-pc-read-s13-5-partb):
    // the COM_* companion quests (Sarah Morgan, Barrett, Andreja, Sam Coe and the shared player lines), SQ_Companions,
    // SQ_Crew and the CREW_* quests. Not held: SQ_Followers (the follower system, not a companion) and
    // SQ_COM_CREW_AngerCombatOverride (outside the owner's COM_ / CREW_ / SQ_Companions / SQ_Crew group). Whether
    // they stay stopped, and that nothing else needs them, is unverified until the PC run
    public static readonly string[] HoldCompanions = { "COM_Companion_SarahMorgan",
        "COM_Companion_SarahMorgan_SpeechChallenges", "COM_Companion_Shared_Sarah", "Com_Companion_Barrett",
        "COM_Companion_Barrett_SpeechChallenges", "COM_Companion_Shared_Barrett", "COM_Companion_Andreja",
        "COM_Companion_Andreja_SpeechChallenges", "COM_Companion_Shared_Andreja", "COM_Companion_SamCoe",
        "COM_Companion_SamCoe_SpeechChallenges", "COM_Companion_SamCoe_Cora", "COM_Companion_Shared_SamCoe",
        "COM_System_PlayerSharedLines", "SQ_Companions", "SQ_Crew", "CREW_EliteCrew_Heller", "CREW_GenericCrew" };
    // S13 row 5, the second group (owner, 15 Nov: "Keep going with shutting off quests until stuff starts to break",
    // least risky first): the running audio-log quests and the two tutorials (SQ_ENV_Tutorial, OutpostTutorial) from
    // result-pc-read-s13-5-partb. Story/content quests only, nothing a Warfare squad needs (the owner's boundary, doc §4e).
    public static readonly string[] HoldAudioTutorials = { "AudioLogsQuest", "AudioLogsQuest_KT", "AudioLogsQuest_RQ",
        "AudioLogsQuest_LVC", "AudioLogsQuest_PS", "AudioLogsQuest_JM", "AudioLogsQuest_OB", "AudioLogsQuest_BB",
        "AudioLogsQuest_FAB", "AudioLogsQuest_AN", "AudioLogsQuest_WJS", "AudioLogsQuest_CT", "SQ_ENV_Tutorial",
        "OutpostTutorial" };
    // S13 row 5, the third group (owner, 15 Nov: city and faction dialogue next): the running quests that serve one
    // Starfield city, settlement or faction (City_*, CityNewAtlantisTransitControl, CF_* / CFSD01, the UC support
    // quests, RI_Support, Settlement_Convo_NA and the city- or faction-named Dialogue* quests) from
    // result-pc-read-s13-5-partb. Not in it: the generic dialogue (DialogueGeneric*, DialogueCrowds, the vendor, crime,
    // creature and robot dialogue), the ship dialogue (the ships group), the main-quest AlwaysOn quests and the rest
    // (later groups). None is follower, crew or group plumbing (the owner's Warfare boundary, doc §4e)
    public static readonly string[] HoldCityFaction = { "City_AkilaLife07", "DialogueConstellation",
        "DialogueCrimsonFleet", "DialogueUCNewAtlantis", "DialogueHopetown_Shared", "CityNewAtlantisTransitControl",
        "DialogueTheFirstNPCs", "DialogueUCNewAtlantisSecurity", "City_NA_Viewport_Base", "CF_Unique",
        "UC03_DeepMinesSupportQuest", "DialogueUCNewAtlantis_Shared", "CF_Post", "DialogueUCFactionAlwaysOn",
        "DialogueFCClinic_IntroPost", "City_GG_Bet_SupportQuest", "CF_Main", "DialogueKaiser", "DialogueFCClinic",
        "UC08_SupportQuest", "DialogueRedDevilsHQ", "CFSD01", "Dialogue1OfAKindUC07", "DialogueUCNewAtlantis_Argos",
        "City_Neon_Gang_Dialogue", "DialogueTrackersAllianceAgents", "DialogueFCAkilaCity",
        "DialogueFCNeonEstablishingScene", "DialogueFCNeon", "City_Neon_Chem_Shared", "DialogueNewHomestead",
        "DialogueFreestarRangers", "DialogueCydonia", "DialogueUCInfinityLTD", "DialogueUCFactionCydonia",
        "DialogueParadiso", "DialogueGagarin_UC_GG", "DialogueUCNewAtlantis_LandryHollifeld", "DialogueFCRyujinTower",
        "DialogueECSConstant", "DialogueGenericHouseVaruun", "DialogueEleosRetreat", "DialogueSeokguhSyndicate",
        "DialogueCrucible", "DialogueUCTheLodge", "Settlement_Convo_NA", "DialogueUCNewAtlantis_NadiaMuffaz",
        "UC05_EmbassySupportQuest", "DialogueUCTheDen", "DialogueHopeTown", "RI_Support",
        "UC02_PerrysMeatsSupportQuest", "DialogueRedMile", "DialogueUCFactionNewAtlantis",
        "DialogueWaggonerFarm_IntroScene", "DialogueWaggonerFarm", "DialogueNeonConvo_SecurityCheckpoint_Controller",
        "City_NA_GuardPointer_Well", "City_NA_GuardPointer_Botany", "City_NA_GuardPointer_Viewport",
        "City_NA_GuardPointer_NA02", "DialogueFCNeon_PlayerHomeQuest", "City_AC_FAB_Quest05", "City_AC_FAB_Quest03",
        "City_AC_FAB_Quest01", "City_AC_FAB_Quest02", "City_AC_FAB_Quest04", "City_AC_FAB_Quest06",
        "City_AC_FAB_Quest11", "City_AC_FAB_Quest09", "City_AC_FAB_Quest07", "City_AC_FAB_Quest08",
        "City_AC_FAB_Quest10", "City_AC_FAB_Quest12", "City_AC_FAB_Quest16", "City_AC_FAB_Quest14",
        "City_AC_FAB_Quest13", "City_AC_FAB_Quest15", "City_AC_FAB_Quest17", "City_AC_FAB_Quest19" };
    // S13 row 5, the fourth group (FAL-1041), in the order of Gemini's ranked batches (FAL-883 comment 1b484947): the
    // rest of the city and faction dialogue batches (generic, crowd, creature, robot, Starborn, crime, guard, vendor,
    // staryard and leftover dialogue), then the rest of the activities and misc batches. None is follower, crew or
    // group runtime plumbing (doc §4e); the radiant, ship and system batches and the never-stop quests stay running
    public static readonly string[] HoldGenericDialogue = { "DialogueCrowds", "DialgoueSSNNScenes",
        "CR_Dialogue_Turret", "DialogueTerrormorphThrallHuman", "DialogueGeneric_LISTOutpost",
        "DialogueGenericSpacers", "DialogueGenericUnique_Crime_TheKey", "DialogueGenericChildren",
        "CR_Dialogue_Terrormorph_Base", "DialogueGenericStarborn_Unique", "CR_Dialogue_QuadrupedB", "DialogueMiniBot",
        "DialogueSettleBartenderRumors", "DialogueCrimeGuards", "MQ105_AlwaysOnDialogueNeon",
        "DialogueGenericVendor_Chunks", "DialogueGenericVendor_Terrabrew", "Staryard_StroudEklund_Dialogue",
        "Staryard_Taiyo_Dialogue", "Staryard_Deimos_Dialogue", "DialogueGenericEclipticANDSoldiers",
        "DialogueGenericUnique_Combat", "Staryard_TridentLuxury_Dialogue", "DialogueGenericCitizens",
        "DialogueGenericScum", "DialogueGenericGuards", "DialogueGenericRobotModelA", "DialogueGenericStarborn",
        "DialogueGenericRobotModelS", "DialogueGenericUnique_Crime", "LC082_SuspiciousActors",
        "DialogueStarstations" };
    public static readonly string[] HoldActivities = { "MQ207C_AlwaysOn", "Trait_RaisedEnlightenedBoxEnabler",
        "Traits_Shared", "MQ207C_Support_Fix01", "Trait_RaisedUniversalBoxEnabler", "MQ206B_AlwaysOn", "SQ_Doctors",
        "AspirationalItems", "MS04", "Patch_Hotfix", "Patch_Update03_FixFollower", "StarbornTempleQuest",
        "SkillMag_CyberRunner_Handler", "SQ_PEO_SustenanceDialogue", "Patch_Update05", "SQ_Hoteliers" };
    // S13 row 5, the fifth and final holdable group (doc §4i): the remaining 9 radiant quests (RI_Support joined
    // HoldCityFaction in group 3), the 21 holdable ship hail/vendor/cargo quests (leaving SQ_PlayerShip running), and
    // the 4 Starfield-only system/trait quests. The 5 Warfare squad quests and 7 core engine quests stay running (199
    // held total: 4 non-running MQ* + 195 of the 207 cold-start running quests).
    public static readonly string[] HoldRadiant = { "MB_Parent", "SQ_PlayerClearedReward", "SE_AC01", "RE_Parent",
        "RQ_Parent", "OE_Dialogue", "SEDebug", "Rad01_LIST", "RQ_Dialogue" };
    public static readonly string[] HoldShips = { "DialogueCrimeGuardShips", "DialogueCrimsonFleetShips",
        "DialogueGenericCitizensShips_MuddledChatter", "DialogueGenericGuardsShips_MuddledChatter",
        "DialogueGenericVendor_LIST", "DialogueGenericPiracyShips", "DialogueGenericSpacersShips",
        "DialogueGenericStarbornShips_Unique", "DialogueShipServices", "SQ_ShipVendors",
        "DialogueGenericGuardsShips", "DialogueGenericHouseVaruunShips", "DialogueTheFirstShips",
        "SE_Player_Attack_SharedLines", "SQ_OutpostCargoLink", "DialogueGenericCitizensShips",
        "DialogueGenericEclipticANDSoldierShips", "DialogueGenericScumShips", "DialogueGenericStarbornShips",
        "DialogueGenericUCGuardsShips", "SQ_CargoShips" };
    public static readonly string[] HoldSystem = { "SQ_GravitationalTraits", "SQ_Traits",
        "SQ_ApplyVoices_OBSOLETE", "LDMasterQuest" };
    public static readonly string[] DefaultHold = HoldCore.Concat(HoldCompanions).Concat(HoldAudioTutorials).Concat(HoldCityFaction)
        .Concat(HoldGenericDialogue).Concat(HoldActivities)
        .Concat(HoldRadiant).Concat(HoldShips).Concat(HoldSystem).ToArray();
    // The O2/CO2 dial (S13 row 2b): with no suit the player's 0002E2 (the pack's O2 capacity, an engine value with no
    // record) is 0, Oxygen reads 0 and the dial is red; 0002E2 +100 by ModValue or console modav clears it (PC, 15 Nov,
    // verified at 8c655d22 and f96cd32f; the script resolves the id as an ActorValue). So with the reset the quest adds
    // O2CapacityAmount once right after it, up to 100 (a value ModValue adds stays in the save). --no-o2-fill leaves it out
    public const bool DefaultO2Fill = true;
    public const uint O2CapacityId = 0x0002E2;
    public const float O2CapacityAmount = 100f;
    // the stages and the objective FO4SF_NewGameQuest.psc drives (stage 0, the start and the wait for the vault, is no record)
    public static readonly ushort[] Stages = { 1, 5, 10, 20, 30, 40, 200, 210 };
    public const ushort Objective = 10;
    public const string ObjectiveText = "Leave Vault 111";
    public const float Units = 70f, MergeX = -1200f, MergeY = -2700f;   // FO4 units per metre; vmad_patch.MERGE_MEASURED
    static readonly ModKey SfEsm = ModKey.FromFileName("Starfield.esm"), PortEsm = ModKey.FromFileName(PortPlugin), CoreValuesEsm = ModKey.FromFileName(CoreValuesPlugin);

    public class Refusal(string m) : Exception(m);

    public static string DefaultCoreValuesJsonPath()
    {
        var dir = AppContext.BaseDirectory;
        for (int up = 0; up < 8 && dir != null; up++, dir = Directory.GetParent(dir)?.FullName)
        {
            var candidate = Path.Combine(dir, "src", "fo4sf", "core", "core_values.json");
            if (File.Exists(candidate)) return candidate;
        }
        var cwd = Path.Combine(Directory.GetCurrentDirectory(), "src", "fo4sf", "core", "core_values.json");
        if (File.Exists(cwd)) return cwd;
        throw new Refusal("cannot locate src/fo4sf/core/core_values.json; pass --core-values-json <path>");
    }

    public static (ModKey PluginKey, Dictionary<string, uint> Ids) LoadCoreValues(string? jsonPath = null)
    {
        var path = jsonPath ?? DefaultCoreValuesJsonPath();
        if (!File.Exists(path)) throw new Refusal($"missing core_values.json: {path}");
        using var doc = JsonDocument.Parse(File.ReadAllText(path));
        var root = doc.RootElement;
        var plugin = root.GetProperty("plugin").GetString() ?? throw new Refusal("core_values.json missing plugin");
        var key = ModKey.FromFileName(plugin);
        if (key != CoreValuesEsm) throw new Refusal($"core_values.json plugin {key} != {CoreValuesEsm}");
        var ids = new Dictionary<string, uint>(StringComparer.Ordinal);
        foreach (var el in root.GetProperty("records").EnumerateArray())
        {
            var edid = el.GetProperty("edid").GetString() ?? throw new Refusal("core_values.json record missing edid");
            var id = Convert.ToUInt32(el.GetProperty("id").GetString()!, 16);
            ids[edid] = id;
        }
        return (key, ids);
    }

    public static uint RequireCoreId(IReadOnlyDictionary<string, uint> ids, string edid) =>
        ids.TryGetValue(edid, out var id) ? id : throw new Refusal($"core_values.json missing {edid}");

    public static string DefaultRouteLootJsonPath()
    {
        var dir = AppContext.BaseDirectory;
        for (int up = 0; up < 8 && dir != null; up++, dir = Directory.GetParent(dir)?.FullName)
        {
            var candidate = Path.Combine(dir, "src", "fo4sf", "loot", "route_loot_ids.json");
            if (File.Exists(candidate)) return candidate;
        }
        var cwd = Path.Combine(Directory.GetCurrentDirectory(), "src", "fo4sf", "loot", "route_loot_ids.json");
        if (File.Exists(cwd)) return cwd;
        throw new Refusal("cannot locate src/fo4sf/loot/route_loot_ids.json; pass --route-loot-json <path>");
    }

    public static uint LoadVaultPistolId(string? jsonPath, SF.IStarfieldModGetter sf)
    {
        var path = jsonPath ?? DefaultRouteLootJsonPath();
        if (!File.Exists(path)) throw new Refusal($"missing route_loot_ids.json: {path}");
        using var doc = JsonDocument.Parse(File.ReadAllText(path));
        var root = doc.RootElement;
        if (!root.TryGetProperty("vault111", out var v111) || !v111.TryGetProperty("pistol_id", out var pidEl))
            throw new Refusal($"route_loot_ids.json missing vault111.pistol_id: {path}");
        var pidStr = pidEl.GetString()?.Trim() ?? "";
        if (pidStr.Length == 0)
            throw new Refusal($"route_loot_ids.json empty vault111.pistol_id: {path}");
        uint pid = Convert.ToUInt32(pidStr, 16);
        if (pid == 0 || !sf.Weapons.Any(w => w.FormKey == new FormKey(SfEsm, pid)))
            throw new Refusal($"Starfield.esm has no WEAP 0x{pid:X6} for vault111.pistol_id in {path}");
        return pid;
    }

    public static int[] LoadRouteLootRefIds(string? jsonPath, string corePath, P3Float exitPos)
    {
        var path = jsonPath ?? DefaultRouteLootJsonPath();
        if (!File.Exists(path)) return Array.Empty<int>();
        using var doc = JsonDocument.Parse(File.ReadAllText(path));
        var root = doc.RootElement;
        if (!root.TryGetProperty("corridor_radius_m", out var radEl) ||
            !root.TryGetProperty("corridor_polyline_m", out var polyEl) ||
            !root.TryGetProperty("fo4_container_categories", out var catEl))
            return Array.Empty<int>();

        double radius = radEl.GetDouble();
        var poly = polyEl.EnumerateArray()
            .Select(pt => { var xy = pt.EnumerateArray().Select(v => v.GetDouble()).ToArray(); return (X: xy[0], Y: xy[1]); })
            .ToArray();
        if (poly.Length < 2) return Array.Empty<int>();

        var mappedFo4Ids = new HashSet<uint>();
        foreach (var prop in catEl.EnumerateObject())
        {
            var s = prop.Name.Trim();
            if (s.StartsWith("0x", StringComparison.OrdinalIgnoreCase)) s = s[2..];
            if (uint.TryParse(s, NumberStyles.HexNumber, CultureInfo.InvariantCulture, out uint fid))
                mappedFo4Ids.Add(fid);
        }

        using var core = SF.StarfieldMod.CreateFromBinaryOverlay(corePath, SF.StarfieldRelease.Starfield, Full(SfEsm));
        var contRx = new System.Text.RegularExpressions.Regex(@"^(?:FO4Core|FO4SF_RouteLoot)_cont_([0-9a-fA-F]{6})_");
        var mappedCoreBases = new HashSet<FormKey>();
        foreach (var c in core.Containers.Where(c => (c.MajorRecordFlagsRaw & 0x20) == 0))
        {
            var ed = c.EditorID;
            if (!string.IsNullOrEmpty(ed) && contRx.Match(ed) is { Success: true } m &&
                uint.TryParse(m.Groups[1].Value, NumberStyles.HexNumber, CultureInfo.InvariantCulture, out uint fo4Id) &&
                mappedFo4Ids.Contains(fo4Id))
                mappedCoreBases.Add(c.FormKey);
        }
        if (mappedCoreBases.Count == 0) return Array.Empty<int>();

        static double SegDist(double px, double py, (double X, double Y) a, (double X, double Y) b)
        {
            double dx = b.X - a.X, dy = b.Y - a.Y, len2 = dx * dx + dy * dy;
            double t = len2 > 0.0 ? Math.Clamp(((px - a.X) * dx + (py - a.Y) * dy) / len2, 0.0, 1.0) : 0.0;
            double qx = a.X + t * dx, qy = a.Y + t * dy;
            return Math.Sqrt((px - qx) * (px - qx) + (py - qy) * (py - qy));
        }

        var hits = new List<(double ExitDist, uint Id)>();
        void ScanCell(SF.ICellGetter? cell)
        {
            if (cell == null) return;
            foreach (var r in cell.Persistent.Concat(cell.Temporary).OfType<SF.IPlacedObjectGetter>())
            {
                if ((r.MajorRecordFlagsRaw & 0x20) != 0 || (r.MajorRecordFlagsRaw & 0x800) != 0) continue;
                if (r.FormKey.ModKey != core.ModKey || !mappedCoreBases.Contains(r.Base.FormKey)) continue;
                double best = double.MaxValue;
                for (int i = 0; i < poly.Length - 1; i++)
                {
                    double d = SegDist(r.Position.X, r.Position.Y, poly[i], poly[i + 1]);
                    if (d < best) best = d;
                }
                if (best <= radius)
                {
                    double ed = Math.Sqrt(Math.Pow(r.Position.X - exitPos.X, 2) + Math.Pow(r.Position.Y - exitPos.Y, 2));
                    hits.Add((ed, r.FormKey.ID));
                }
            }
        }
        foreach (var w in core.Worldspaces)
        {
            ScanCell(w.TopCell);
            foreach (var blk in w.SubCells)
                foreach (var sub in blk.Items)
                    foreach (var ec in sub.Items)
                        ScanCell(ec);
        }
        return hits.OrderBy(h => h.ExitDist).ThenBy(h => h.Id).Select(h => (int)h.Id).Distinct().ToArray();
    }

    public static string DefaultWarfareStartsJsonPath()
    {
        var dir = AppContext.BaseDirectory;
        for (int up = 0; up < 8 && dir != null; up++, dir = Directory.GetParent(dir)?.FullName)
        {
            var candidate = Path.Combine(dir, "src", "fo4sf", "core", "warfare_starts.json");
            if (File.Exists(candidate)) return candidate;
        }
        var cwd = Path.Combine(Directory.GetCurrentDirectory(), "src", "fo4sf", "core", "warfare_starts.json");
        if (File.Exists(cwd)) return cwd;
        throw new Refusal("cannot locate src/fo4sf/core/warfare_starts.json; pass --warfare-starts <path>");
    }

    public record WarfareTable(
        string[] Keys, int[] FactionSlots, string[] FactionButtons, string[] SpotButtons, int[] DistinctFactionSlots,
        int[] MarkerIds, float[] MarkerX, float[] MarkerY, float[] MarkerZ, float[] Headings,
        int[] MinDiffs, int[] MaxDiffs, int[] BgIndices, float[] Fames, float[] Infamies, float[] Karmas, int[] SquadCaps,
        int[] GearRowIndices, string[] GearPlugins, int[] GearIds, int[] GearCounts, bool[] GearEquips);

    public static WarfareTable LoadWarfareStarts(string? jsonPath, SF.IStarfieldModGetter sf, string corePath)
    {
        var path = jsonPath ?? DefaultWarfareStartsJsonPath();
        if (!File.Exists(path)) throw new Refusal($"missing warfare_starts.json: {path}");
        using var core = SF.StarfieldMod.CreateFromBinaryOverlay(corePath, SF.StarfieldRelease.Starfield, Full(SfEsm));
        Owner(core.ModKey, CorePluginFile, "the core");
        var world = core.Worldspaces.FirstOrDefault(w => w.EditorID == World && w.FormKey.ModKey == core.ModKey)
                    ?? throw new Refusal($"{core.ModKey} has no worldspace {World}");
        var coreRefs = new List<SF.IPlacedGetter>();
        if (world.TopCell is { } top) coreRefs.AddRange(top.Persistent.Concat(top.Temporary));
        foreach (var b in world.SubCells) foreach (var s in b.Items) foreach (var c in s.Items) coreRefs.AddRange(c.Persistent.Concat(c.Temporary));
        var placedByEdid = coreRefs.OfType<SF.IPlacedObjectGetter>()
            .Where(r => !string.IsNullOrEmpty(r.EditorID))
            .GroupBy(r => r.EditorID!, StringComparer.Ordinal)
            .ToDictionary(g => g.Key, g => g.ToList(), StringComparer.Ordinal);
        var sfKnownIds = sf.EnumerateMajorRecords().Where(r => r.FormKey.ModKey == SfEsm).Select(r => r.FormKey.ID).ToHashSet();

        using var doc = JsonDocument.Parse(File.ReadAllText(path));
        var root = doc.RootElement;
        if (!root.TryGetProperty("schema_version", out var sv) || sv.GetInt32() != 1)
            throw new Refusal($"unsupported warfare_starts schema_version in {path}");
        var startsArr = root.GetProperty("starts").EnumerateArray().ToList();
        if (startsArr.Count == 0)
            throw new Refusal($"warfare_starts.json has 0 start rows: {path}");
        if (startsArr.Count > 4)
            throw new Refusal($"warfare_starts.json has {startsArr.Count} start rows (> 4 buttons per message box)");

        var keys = new List<string>();
        var seenKeys = new HashSet<string>(StringComparer.Ordinal);
        var fSlots = new List<int>();
        var spotBtns = new List<string>();
        var distinctSlots = new List<int>();
        var facBtns = new List<string>();
        var markerIds = new List<int>();
        var mx = new List<float>();
        var my = new List<float>();
        var mz = new List<float>();
        var headings = new List<float>();
        var minDiffs = new List<int>();
        var maxDiffs = new List<int>();
        var bgIndices = new List<int>();
        var fames = new List<float>();
        var infamies = new List<float>();
        var karmas = new List<float>();
        var squadCaps = new List<int>();
        var gearRows = new List<int>();
        var gearPlugins = new List<string>();
        var gearIds = new List<int>();
        var gearCounts = new List<int>();
        var gearEquips = new List<bool>();

        for (int rowIdx = 0; rowIdx < startsArr.Count; rowIdx++)
        {
            var el = startsArr[rowIdx];
            var rKey = el.GetProperty("key").GetString()?.Trim() ?? "";
            if (rKey.Length == 0 || !seenKeys.Add(rKey))
                throw new Refusal($"warfare_starts.json invalid or duplicate key '{rKey}'");
            int slot = el.GetProperty("faction_slot").GetInt32();
            if (slot < 0 || slot > 7)
                throw new Refusal($"warfare start '{rKey}': faction_slot {slot} outside 0..7");
            string facName = el.GetProperty("faction_name").GetString()?.Trim() ?? "";
            string spotName = el.GetProperty("name").GetString()?.Trim() ?? "";
            if (facName.Length == 0 || spotName.Length == 0)
                throw new Refusal($"warfare start '{rKey}': empty faction_name or name");
            if (!distinctSlots.Contains(slot))
            {
                distinctSlots.Add(slot);
                facBtns.Add(facName);
            }
            string markerEdid = el.GetProperty("marker_edid").GetString()?.Trim() ?? "";
            if (!placedByEdid.TryGetValue(markerEdid, out var mHits) || mHits.Count != 1)
                throw new Refusal($"warfare start '{rKey}': unknown marker_edid '{markerEdid}' in {CorePluginFile}");
            var mRef = mHits[0];
            Owned(mRef, core.ModKey, $"warfare start marker {markerEdid}");
            if (!IsPersistent(mRef))
                throw new Refusal($"warfare start '{rKey}': marker {markerEdid} is not persistent");

            int minD = el.GetProperty("min_difficulty").GetInt32();
            int maxD = el.GetProperty("max_difficulty").GetInt32();
            if (minD < 0 || maxD > 3 || minD > maxD)
                throw new Refusal($"warfare start '{rKey}': invalid difficulty range {minD}..{maxD}");
            int sCap = el.GetProperty("squad_cap").GetInt32();
            if (sCap < 1)
                throw new Refusal($"warfare start '{rKey}': squad_cap {sCap} < 1");

            var gearEl = el.GetProperty("gear").EnumerateArray().ToList();
            if (gearEl.Count == 0)
                throw new Refusal($"warfare start '{rKey}': empty gear list");
            foreach (var g in gearEl)
            {
                string gp = g.GetProperty("plugin").GetString()?.Trim() ?? "";
                uint gid = Convert.ToUInt32(g.GetProperty("id").GetString()!, 16);
                int gcnt = g.GetProperty("count").GetInt32();
                bool geq = g.TryGetProperty("equip", out var eqEl) && eqEl.GetBoolean();
                if (!string.Equals(gp, "Starfield.esm", StringComparison.OrdinalIgnoreCase) || !sfKnownIds.Contains(gid) || gcnt <= 0)
                    throw new Refusal($"warfare start '{rKey}': invalid or unknown gear item {gp}:0x{gid:X6} count={gcnt}");
                gearRows.Add(rowIdx);
                gearPlugins.Add("Starfield.esm");
                gearIds.Add((int)gid);
                gearCounts.Add(gcnt);
                gearEquips.Add(geq);
            }

            keys.Add(rKey);
            fSlots.Add(slot);
            spotBtns.Add(spotName);
            markerIds.Add((int)mRef.FormKey.ID);
            mx.Add(mRef.Position.X);
            my.Add(mRef.Position.Y);
            mz.Add(mRef.Position.Z);
            headings.Add(el.TryGetProperty("heading", out var hEl) ? hEl.GetSingle() : 0f);
            minDiffs.Add(minD);
            maxDiffs.Add(maxD);
            bgIndices.Add(el.TryGetProperty("background_index", out var bgEl) ? bgEl.GetInt32() : 0);
            fames.Add(el.GetProperty("fame").GetSingle());
            infamies.Add(el.TryGetProperty("infamy", out var infEl) ? infEl.GetSingle() : 0f);
            karmas.Add(el.GetProperty("karma").GetSingle());
            squadCaps.Add(sCap);
        }
        if (facBtns.Count > 4)
            throw new Refusal($"warfare_starts.json has {facBtns.Count} distinct factions (> 4 buttons per message box)");

        return new WarfareTable(
            keys.ToArray(), fSlots.ToArray(), facBtns.ToArray(), spotBtns.ToArray(), distinctSlots.ToArray(),
            markerIds.ToArray(), mx.ToArray(), my.ToArray(), mz.ToArray(), headings.ToArray(),
            minDiffs.ToArray(), maxDiffs.ToArray(), bgIndices.ToArray(), fames.ToArray(), infamies.ToArray(), karmas.ToArray(), squadCaps.ToArray(),
            gearRows.ToArray(), gearPlugins.ToArray(), gearIds.ToArray(), gearCounts.ToArray(), gearEquips.ToArray());
    }

    public static string DefaultStartPlacesJsonPath()
    {
        var dir = AppContext.BaseDirectory;
        for (int up = 0; up < 8 && dir != null; up++, dir = Directory.GetParent(dir)?.FullName)
        {
            var candidate = Path.Combine(dir, "src", "fo4sf", "core", "start_places.json");
            if (File.Exists(candidate)) return candidate;
        }
        var cwd = Path.Combine(Directory.GetCurrentDirectory(), "src", "fo4sf", "core", "start_places.json");
        if (File.Exists(cwd)) return cwd;
        throw new Refusal("cannot locate src/fo4sf/core/start_places.json; pass --start-places <path>");
    }

    public record StartPlaceTable(
        string[] StoryIds, string[] StoryLabels,
        string[] PlaceIds, int[] PlaceModes, string[] PlaceStories, string[] PlacePlugins,
        int[] PlaceMarkerIds, float[] PlaceX, float[] PlaceY, float[] PlaceZ, float[] PlaceHeadings,
        bool[] PlaceIsInterior, int[] PlaceQuestMasks, int[] PlaceWarfareRows);

    public static StartPlaceTable LoadStartPlaces(string? jsonPath, JsonElement pts, Places places, WarfareTable wf, string portPath, string corePath)
    {
        var path = jsonPath ?? DefaultStartPlacesJsonPath();
        if (!File.Exists(path)) throw new Refusal($"missing start_places.json: {path}");
        using var port = SF.StarfieldMod.CreateFromBinaryOverlay(portPath, SF.StarfieldRelease.Starfield, Full(SfEsm));
        using var core = SF.StarfieldMod.CreateFromBinaryOverlay(corePath, SF.StarfieldRelease.Starfield, Full(SfEsm));

        var portRefs = new List<SF.IPlacedObjectGetter>();
        foreach (var blk in port.Cells.Records)
            foreach (var sub in blk.SubBlocks)
                foreach (var c in sub.Cells)
                    portRefs.AddRange(c.Persistent.Concat(c.Temporary).OfType<SF.IPlacedObjectGetter>());

        var coreRefs = new List<SF.IPlacedObjectGetter>();
        foreach (var w in core.Worldspaces)
        {
            if (w.TopCell is { } top) coreRefs.AddRange(top.Persistent.Concat(top.Temporary).OfType<SF.IPlacedObjectGetter>());
            foreach (var b in w.SubCells) foreach (var s in b.Items) foreach (var c in s.Items)
                coreRefs.AddRange(c.Persistent.Concat(c.Temporary).OfType<SF.IPlacedObjectGetter>());
        }

        var pod = Floats(pts.GetProperty("pod").GetProperty("pos"));
        float podHeading = pts.GetProperty("pod").GetProperty("heading").GetSingle();

        using var doc = JsonDocument.Parse(File.ReadAllText(path));
        var root = doc.RootElement;
        if (!root.TryGetProperty("schema_version", out var sv) || sv.GetInt32() != 1)
            throw new Refusal($"unsupported start_places schema_version in {path}");

        var storyIds = new List<string>();
        var storyLabels = new List<string>();
        var placeIds = new List<string>();
        var seenIds = new HashSet<string>(StringComparer.Ordinal);
        var placeModes = new List<int>();
        var placeStories = new List<string>();
        var placePlugins = new List<string>();
        var placeMarkerIds = new List<int>();
        var placeX = new List<float>();
        var placeY = new List<float>();
        var placeZ = new List<float>();
        var placeHeadings = new List<float>();
        var placeIsInterior = new List<bool>();
        var placeQuestMasks = new List<int>();
        var placeWfRows = new List<int>();

        foreach (var el in root.GetProperty("places").EnumerateArray())
        {
            var pid = el.GetProperty("id").GetString()?.Trim() ?? "";
            if (pid.Length == 0 || !seenIds.Add(pid))
                throw new Refusal($"start_places.json invalid or duplicate id '{pid}'");
            string modeStr = (el.GetProperty("mode").GetString()?.Trim() ?? "").ToLowerInvariant();
            int modeCode = modeStr switch
            {
                "story" => 1,
                "warfare" => 2,
                _ => throw new Refusal($"start place '{pid}': invalid mode '{modeStr}'"),
            };
            bool available = el.TryGetProperty("available", out var avEl) && avEl.GetBoolean();
            if (!available)
            {
                string reason = el.TryGetProperty("unavailable_reason", out var urEl) ? (urEl.GetString()?.Trim() ?? "") : "";
                if (reason.Length == 0 || reason.Contains('\n') || reason.Contains('\r'))
                    throw new Refusal($"start place '{pid}': available=false requires a non-empty single-line unavailable_reason");
                continue;   // N2 / S3: unbuilt future rows stay in table metadata with 1-line reason but are never offered as loadable targets
            }

            string plg = el.GetProperty("plugin").GetString()?.Trim() ?? "";
            bool isPort = string.Equals(plg, PortPlugin, StringComparison.OrdinalIgnoreCase);
            bool isCore = string.Equals(plg, CorePluginFile, StringComparison.OrdinalIgnoreCase);
            if (!isPort && !isCore)
                throw new Refusal($"start place '{pid}': marked available=true on unloaded plugin '{plg}'");

            string storyId = el.TryGetProperty("story_id", out var sidEl) ? (sidEl.GetString()?.Trim() ?? "none") : "none";
            string storyLabel = el.TryGetProperty("story_label", out var slEl) ? (slEl.GetString()?.Trim() ?? "") : "";
            bool isInterior = el.TryGetProperty("is_interior", out var intEl) && intEl.GetBoolean();
            int questMask = el.TryGetProperty("quest_mask", out var qmEl) ? qmEl.GetInt32() : 0;
            string markerSrc = el.TryGetProperty("marker_source", out var msEl) ? (msEl.GetString()?.Trim() ?? "") : "";
            string markerEdid = el.TryGetProperty("marker_edid", out var meEl) ? (meEl.GetString()?.Trim() ?? "") : "";
            string wfKey = el.TryGetProperty("warfare_key", out var wkEl) ? (wkEl.GetString()?.Trim() ?? "") : "";

            int resolvedMarkerId;
            float rx, ry, rz, rh;
            if (markerSrc == "vault_anchor")
            {
                if (!isPort) throw new Refusal($"start place '{pid}': vault_anchor requires {PortPlugin}");
                resolvedMarkerId = (int)places.VaultAnchor;
                rx = pod[0];
                ry = pod[1];
                rz = pod[2] + 0.3f;
                rh = podHeading;
            }
            else
            {
                if (markerEdid.Length == 0)
                    throw new Refusal($"start place '{pid}': missing marker_source or marker_edid");
                var pool = isPort ? portRefs : coreRefs;
                var ownerKey = isPort ? port.ModKey : core.ModKey;
                var hits = pool.Where(r => string.Equals(r.EditorID, markerEdid, StringComparison.Ordinal)).ToList();
                if (hits.Count != 1)
                    throw new Refusal($"start place '{pid}': marked available=true but marker_edid '{markerEdid}' is absent in {plg}");
                Owned(hits[0], ownerKey, $"start place marker {markerEdid}");
                if (!IsPersistent(hits[0]))
                    throw new Refusal($"start place '{pid}': marker '{markerEdid}' is not persistent");
                resolvedMarkerId = (int)hits[0].FormKey.ID;
                rx = hits[0].Position.X;
                ry = hits[0].Position.Y;
                rz = hits[0].Position.Z;
                rh = Deg(hits[0].Rotation.Z);
            }

            int wfRow = -1;
            if (modeCode == 1)
            {
                if (storyId.Length == 0 || storyId == "none" || storyLabel.Length == 0)
                    throw new Refusal($"start place '{pid}': story row needs story_id and story_label");
                if (!storyIds.Contains(storyId))
                {
                    storyIds.Add(storyId);
                    storyLabels.Add(storyLabel);
                }
            }
            else
            {
                wfRow = Array.IndexOf(wf.Keys, wfKey);
                if (wfRow < 0)
                    throw new Refusal($"start place '{pid}': warfare_key '{wfKey}' not found in warfare_starts.json");
                rh = wf.Headings[wfRow];
            }

            placeIds.Add(pid);
            placeModes.Add(modeCode);
            placeStories.Add(storyId);
            placePlugins.Add(isPort ? PortPlugin : CorePluginFile);
            placeMarkerIds.Add(resolvedMarkerId);
            placeX.Add(rx);
            placeY.Add(ry);
            placeZ.Add(rz);
            placeHeadings.Add(rh);
            placeIsInterior.Add(isInterior);
            placeQuestMasks.Add(questMask);
            placeWfRows.Add(wfRow);
        }

        if (storyIds.Count == 0 || storyLabels.Count > MaxMessageButtons)
            throw new Refusal($"start_places.json has {storyLabels.Count} available story choices (need 1..{MaxMessageButtons})");

        return new StartPlaceTable(
            storyIds.ToArray(), storyLabels.ToArray(),
            placeIds.ToArray(), placeModes.ToArray(), placeStories.ToArray(), placePlugins.ToArray(),
            placeMarkerIds.ToArray(), placeX.ToArray(), placeY.ToArray(), placeZ.ToArray(), placeHeadings.ToArray(),
            placeIsInterior.ToArray(), placeQuestMasks.ToArray(), placeWfRows.ToArray());
    }

    public static int ParseStartChoiceBackdrop(string? raw) => (raw?.Trim().ToLowerInvariant()) switch
    {
        null or "" or "empty_cell" or "1" => BackdropEmptyCell,
        "title_card" or "2" => BackdropTitleCard,
        "setup_menu" or "3" => BackdropSetupMenu,
        "none" or "0" => BackdropNone,
        _ => throw new Refusal($"--start-choice-backdrop must be empty_cell, title_card, setup_menu, or none (got '{raw}')"),
    };

    static void RefuseForbiddenOutDir(string outDir)
    {
        var full = Path.GetFullPath(outDir);
        for (var cur = new DirectoryInfo(full); cur != null; cur = cur.Parent)
        {
            if (Directory.Exists(Path.Combine(cur.FullName, ".git")) || File.Exists(Path.Combine(cur.FullName, ".git")))
                throw new Refusal($"output folder inside Git worktree is forbidden: {full}");
            if (File.Exists(Path.Combine(cur.FullName, "Starfield.exe")))
                throw new Refusal($"output folder inside game install is forbidden: {full}");
        }
    }

    static void WritePlugin(SF.StarfieldMod mod, string path)
    {
        var masters = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        masters.Set(new KeyedMasterStyle(SfEsm, MasterStyle.Full));
        masters.Set(new KeyedMasterStyle(PortEsm, MasterStyle.Full));
        masters.Set(new KeyedMasterStyle(CoreValuesEsm, MasterStyle.Full));
        ((IModGetter)mod).WriteToBinary(path, new BinaryWriteParameters
        {
            ModKey = ModKeyOption.NoCheck,
            MastersListOrdering = new MastersListOrderingByLoadOrder(new[] { SfEsm, PortEsm, CoreValuesEsm }),
            MasterFlagsLookup = masters,
        });
    }

    public static int Usage()
    {
        Console.Error.WriteLine("usage: see the header of dotnet/NewGame/Program.cs (points | write | check | selftest | records | records-selftest)");
        return 2;
    }
    public static string? ArgOrNull(string[] a, string name) { var i = Array.IndexOf(a, name); return i >= 0 && i + 1 < a.Length ? a[i + 1] : null; }
    public static float Opt(string[] a, string name, float dflt) =>
        ArgOrNull(a, name) is { } v ? float.Parse(v, CultureInfo.InvariantCulture) : dflt;
    static string F(float v) => v.ToString("0.###", CultureInfo.InvariantCulture);
    static float Deg(float rad) => rad * 180f / MathF.PI;

    public record Options(string Plugin, string[] Hold, float? MQ101Debug, bool Looks, int RaceMenuMode, bool Special, bool Version, float BuildVersion, string ExitAnchor,
                          bool ClearInventory = DefaultClearInventory, string? VaultSuit = null, bool RequirePersistentAnchor = DefaultRequirePersistentAnchor,
                          int DebugAfterHold = DefaultDebugAfterHold, bool AnimatedExitLift = false, bool O2Fill = DefaultO2Fill, string? CoreValuesJson = null,
                          bool FadeHold = DefaultFadeHold, string? WarfareStartsJson = null, string? RouteLootJson = null,
                          int StartChoiceBackdrop = DefaultStartChoiceBackdrop, string? StartPlacesJson = null)
    {
        public bool O2 => ClearInventory && O2Fill;   // a --keep-inventory player keeps Starfield's suit and its capacity
        public static Options From(string[] a)
        {
            var suit = ArgOrNull(a, "--vault-suit");
            if (a.Contains("--vault-suit") && (suit is null || suit.StartsWith("--"))) throw new Refusal("--vault-suit needs an ARMO EditorID");
            bool keep = a.Contains("--keep-inventory");
            if (keep && a.Contains("--clear-inventory")) throw new Refusal("--keep-inventory and --clear-inventory contradict each other");
            if (suit is not null && keep) throw new Refusal("--vault-suit is equipped by the inventory reset: --keep-inventory turns it off");
            bool clear = !keep && DefaultClearInventory;
            if (a.Contains("--allow-temporary-anchor") && a.Contains("--require-persistent-anchor"))
                throw new Refusal("--allow-temporary-anchor and --require-persistent-anchor contradict each other");
            var wfJson = ArgOrNull(a, "--warfare-starts");
            if (a.Contains("--warfare-starts") && (wfJson is null || wfJson.StartsWith("--")))
                throw new Refusal("--warfare-starts needs a JSON path");
            var rlJson = ArgOrNull(a, "--route-loot-json");
            if (a.Contains("--route-loot-json") && (rlJson is null || rlJson.StartsWith("--")))
                throw new Refusal("--route-loot-json needs a JSON path");
            var spJson = ArgOrNull(a, "--start-places");
            if (a.Contains("--start-places") && (spJson is null || spJson.StartsWith("--")))
                throw new Refusal("--start-places needs a JSON path");
            var bdRaw = ArgOrNull(a, "--start-choice-backdrop");
            if (a.Contains("--start-choice-backdrop") && (bdRaw is null || bdRaw.StartsWith("--")))
                throw new Refusal("--start-choice-backdrop needs empty_cell, title_card, setup_menu, or none");
            int backdrop = ParseStartChoiceBackdrop(bdRaw);
            return new(
                ArgOrNull(a, "--plugin") ?? NewGame.Plugin,
                (ArgOrNull(a, "--hold") ?? string.Join(",", DefaultHold)).Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries),
                a.Contains("--no-mq101debug") ? null : ArgOrNull(a, "--mq101debug") is { } d ? float.Parse(d, CultureInfo.InvariantCulture) : null,   // no override by default (28 Oct, run 2)
                !a.Contains("--no-looks"),
                ArgOrNull(a, "--race-menu-mode") is { } m ? int.Parse(m, CultureInfo.InvariantCulture) : DefaultRaceMenuMode,
                !a.Contains("--no-special"),
                !a.Contains("--no-version"),
                ArgOrNull(a, "--build-version") is { } v ? float.Parse(v, CultureInfo.InvariantCulture) : DefaultBuildVersion,
                ArgOrNull(a, "--exit-anchor") ?? ExitAnchorEdid,
                clear, suit, !a.Contains("--allow-temporary-anchor"),
                ArgOrNull(a, "--debug-after-hold") is { } w ? int.Parse(w, CultureInfo.InvariantCulture) : DefaultDebugAfterHold,
                a.Contains("--animated-exit-lift"), !a.Contains("--no-o2-fill"),
                ArgOrNull(a, "--core-values-json"),
                !a.Contains("--no-fade-hold"),
                wfJson,
                rlJson,
                backdrop,
                spJson);
        }
    }

    // ---------------------------------------------------------------- points (Fallout 4, read only)

    public static int Points(string fo4Path, string outPath, string? podRef, float podStep, string? terminalRef = null)
    {
        using var fo4 = F4.Fallout4Mod.CreateFromBinaryOverlay(fo4Path, F4.Fallout4Release.Fallout4);
        var key = fo4.ModKey;
        var cell = fo4.EnumerateMajorRecords<F4.ICellGetter>().FirstOrDefault(c => c.FormKey == new FormKey(key, Fo4VaultCell))
                   ?? throw new Refusal($"no Vault111Cryo cell {Fo4VaultCell:X8}");
        var refs = cell.Persistent.Concat(cell.Temporary).ToDictionary(r => r.FormKey.ID);
        F4.IPlacedGetter Ref(uint id, string what) => refs.TryGetValue(id, out var r) ? r : throw new Refusal($"{cell.EditorID} has no {what} {id:X8}");
        // the player's pod: FO4 names it in the reference's EditorID (one reference naming the player and a pod)
        var pods = refs.Values.OfType<F4.IPlacedObjectGetter>().Where(r => IsPlayerPod(r.EditorID)).ToList();
        foreach (var p in pods) Console.WriteLine($"  pod candidate {p.FormKey.ID:X8} {p.EditorID} at fo4 {Show(p.Position)}");
        F4.IPlacedObjectGetter pod = podRef is not null
            ? Ref(uint.Parse(podRef, NumberStyles.HexNumber, CultureInfo.InvariantCulture), "--pod-ref") as F4.IPlacedObjectGetter ?? throw new Refusal("--pod-ref is not a placed object")
            : pods.Count == 1 ? pods[0] : throw new Refusal($"{pods.Count} player pod candidates in {cell.EditorID}: name one with --pod-ref");
        var console = Ref(Fo4Console, "cog door console");
        var cog = Ref(Fo4CogDoor, "cog door");
        var platform = Ref(Fo4Platform, "elevator platform");
        var platformStand = Ref(Fo4PlatformMarker, "elevator platform stand marker");
        var exit = Ref(Fo4ExitDoor, "elevator load door") as F4.IPlacedObjectGetter;
        var tel = exit?.TeleportDestination ?? throw new Refusal($"{Fo4ExitDoor:X8} has no teleport destination");
        // standing up out of the pod: podStep metres along the pod's facing (its local +Y turned by its z rotation)
        float h = pod.Rotation.Z;
        var stand = new[] { pod.Position.X / Units + podStep * MathF.Sin(h), pod.Position.Y / Units + podStep * MathF.Cos(h), pod.Position.Z / Units };
        string mq102 = fo4.Quests.FirstOrDefault(q => q.FormKey.ID == Fo4MQ102)?.Name?.String is { Length: > 0 } n ? n : "Out of Time";
        float[] M(P3Float p) => new[] { p.X / Units, p.Y / Units, p.Z / Units };
        // the SPECIAL terminal (NG-C4): every placed TERM of the cell, nearest the pod first (the cryo hall's terminals
        // stand by the pods), or the one --terminal-ref names, any base. Which the port carries is the writer's call
        var terms = fo4.Terminals.Select(t => t.FormKey).ToHashSet();
        float PodDist(F4.IPlacedObjectGetter r) => MathF.Sqrt(MathF.Pow(r.Position.X - pod.Position.X, 2) + MathF.Pow(r.Position.Y - pod.Position.Y, 2) + MathF.Pow(r.Position.Z - pod.Position.Z, 2));
        var terminals = terminalRef is not null
            ? new List<F4.IPlacedObjectGetter> { Ref(uint.Parse(terminalRef, NumberStyles.HexNumber, CultureInfo.InvariantCulture), "--terminal-ref") as F4.IPlacedObjectGetter ?? throw new Refusal("--terminal-ref is not a placed object") }
            : refs.Values.OfType<F4.IPlacedObjectGetter>().Where(r => terms.Contains(r.Base.FormKey)).OrderBy(PodDist).ThenBy(r => r.FormKey.ID).ToList();
        foreach (var t in terminals) Console.WriteLine($"  terminal {t.FormKey.ID:X8} {t.EditorID} at fo4 {Show(t.Position)}, {F(PodDist(t) / Units)} m from the pod");
        if (terminals.Count == 0) Console.WriteLine($"  no terminal in {cell.EditorID}: write needs --no-special, or points --terminal-ref <hex>");
        var conPos = M(PosOf(console));
        refs.TryGetValue(Fo4PipboyPickup, out var pbRef);
        refs.TryGetValue(Fo4PipboySkeleton, out var skelRef);
        var pbPos = pbRef is not null ? M(PosOf(pbRef)) : new[] { conPos[0] - 0.09f, conPos[1] + 1.55f, conPos[2] - 1.05f };
        var skelPos = skelRef is not null ? M(PosOf(skelRef)) : pbPos;
        var pbRot = pbRef is F4.IPlacedObjectGetter pbo ? new[] { pbo.Rotation.X, pbo.Rotation.Y, pbo.Rotation.Z } : new[] { 0f, 0f, 3.8044f };
        var doc = new Dictionary<string, object?>
        {
            ["source"] = Path.GetFileName(fo4Path),
            ["frame"] = "metres, FO4 position / 70 (interior: the port's cell frame; arrival: the core's local frame); headings in degrees",
            ["quest_name"] = mq102,
            ["pod"] = new Dictionary<string, object?> { ["src"] = $"{pod.FormKey.ID:X8}", ["edid"] = pod.EditorID, ["at"] = M(pod.Position),
                                                         ["pos"] = stand, ["heading"] = Deg(h), ["step_m"] = podStep },
            ["console"] = new Dictionary<string, object?> { ["src"] = $"{Fo4Console:X8}", ["pos"] = conPos },
            ["pipboy_corpse"] = new Dictionary<string, object?> { ["src"] = $"{(pbRef?.FormKey.ID ?? Fo4PipboyPickup):X8}",
                                                                  ["skeleton_src"] = $"{(skelRef?.FormKey.ID ?? Fo4PipboySkeleton):X8}",
                                                                  ["pos"] = pbPos, ["skeleton_pos"] = skelPos, ["rot"] = pbRot },
            ["cog_door"] = new Dictionary<string, object?> { ["src"] = $"{Fo4CogDoor:X8}", ["pos"] = M(PosOf(cog)) },
            ["platform"] = new Dictionary<string, object?> { ["src"] = $"{Fo4Platform:X8}", ["stand_src"] = $"{Fo4PlatformMarker:X8}",
                                                             ["ref_pos"] = M(PosOf(platform)), ["pos"] = M(PosOf(platformStand)) },
            ["arrival"] = new Dictionary<string, object?> { ["src"] = $"{Fo4ExitDoor:X8}:XTEL", ["to"] = $"{tel.Door.FormKey.ID:X8}",
                                                             ["pos"] = M(tel.Position), ["heading"] = Deg(tel.Rotation.Z) },
            ["terminals"] = terminals.Select(t => new Dictionary<string, object?> { ["src"] = $"{t.FormKey.ID:X8}", ["edid"] = t.EditorID, ["pos"] = M(t.Position) }).ToList(),
        };
        Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(outPath))!);
        File.WriteAllText(outPath, JsonSerializer.Serialize(doc, new JsonSerializerOptions { WriteIndented = true }));
        Console.WriteLine($"wrote {outPath}: pod {pod.FormKey.ID:X8} {pod.EditorID}, stand ({F(stand[0])}, {F(stand[1])}, {F(stand[2])}) m heading {F(Deg(h))}; " +
                          $"arrival ({F(tel.Position.X / Units)}, {F(tel.Position.Y / Units)}, {F(tel.Position.Z / Units)}) m; {terminals.Count} terminal(s); quest \"{mq102}\"");
        return 0;
    }

    static P3Float PosOf(F4.IPlacedGetter r) => r switch
    {
        F4.IPlacedObjectGetter o => o.Position, F4.IPlacedNpcGetter n => n.Position,
        _ => throw new Refusal($"{r.FormKey.ID:X8} is neither a placed object nor an actor"),
    };

    /// FO4's two pods in the cryo hall's row (PC, 19 Oct): MQPlayerCryopodREF 0004A011 (the player's) and
    /// MQPlayerSpousePodREF 0004A012 (the spouse's): a spouse pod is never the player's.
    public static bool IsPlayerPod(string? edid) =>
        edid is not null && edid.Contains("Player", StringComparison.OrdinalIgnoreCase) &&
        !edid.Contains("Spouse", StringComparison.OrdinalIgnoreCase) &&
        (edid.Contains("Pod", StringComparison.OrdinalIgnoreCase) || edid.Contains("Cryo", StringComparison.OrdinalIgnoreCase));

    static string Show(P3Float p) => $"({F(p.X)}, {F(p.Y)}, {F(p.Z)})";

    // ---------------------------------------------------------------- the places the script resolves at run time

    public record Places(uint VaultAnchor, P3Float AnchorPos, uint CogDoor, string CogDoorBase, uint ExitAnchor, P3Float ExitPos,
                         uint Terminal, uint TerminalSrc, P3Float TerminalPos, uint VaultSuit = 0, bool AnchorTemporary = false,
                         uint Lift = 0, uint LiftBase = 0, uint Console = 0, uint PortPipboyStatic = 0,
                         uint PortCellId = 0, int CellBlockNum = 0, int CellSubBlockNum = 0, int[]? CoreMarkers = null, P3Float ConsoleRot = default)
    {
        /// "persistent" or "temporary": the anchor's mode, as write and check print it after the anchor's id.
        public string AnchorMode => AnchorTemporary ? "temporary" : "persistent";
    }

    /// points.json's terminals, nearest the pod first: (FO4 id, position in metres).
    public static List<(uint Src, P3Float Pos)> Terminals(JsonElement pts)
    {
        var list = new List<(uint, P3Float)>();
        if (!pts.TryGetProperty("terminals", out var arr)) return list;
        foreach (var t in arr.EnumerateArray())
        {
            var p = Floats(t.GetProperty("pos"));
            list.Add((uint.Parse(t.GetProperty("src").GetString()!, NumberStyles.HexNumber, CultureInfo.InvariantCulture), new P3Float(p[0], p[1], p[2])));
        }
        return list;
    }

    public static BinaryReadParameters Full(params ModKey[] keys)
    {
        var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        foreach (var k in keys) styles.Set(new KeyedMasterStyle(k, MasterStyle.Full));
        return new BinaryReadParameters { MasterFlagsLookup = styles };
    }

    /// The vault anchor (a persistent reference of FO4Port_Vault111Cryo: its one COC marker when that is persistent, else
    /// the port's persistent reference nearest to it; with none, refused while `requirePersistentAnchor` holds, the
    /// default, else the temporary COC marker itself and AnchorTemporary set), the cog door (formids.json's key for FO4 000330C3
    /// in that cell, 0 when absent, and it must be a reference of that cell), the SPECIAL terminal (the first of points'
    /// terminals the port carries, a persistent one preferred, nearest the pod among those; each key named must be the
    /// port's own reference of the cell; 0 when it carries none, and the prompt then watches points' nearest terminal)
    /// the exit anchor (the core world's REFR with that EditorID, persistent) and, when `vaultSuit` names one, the port's
    /// ARMO of that EditorID (exactly one, the port's own record; refused otherwise) the inventory reset equips.
    public static Places Resolve(string portPath, string portIds, string corePath, string exitAnchor, IReadOnlyList<(uint Src, P3Float Pos)>? terminals = null, string? vaultSuit = null,
                                 bool requirePersistentAnchor = DefaultRequirePersistentAnchor, bool animatedExitLift = false)
    {
        using var port = SF.StarfieldMod.CreateFromBinaryOverlay(portPath, SF.StarfieldRelease.Starfield, Full(SfEsm));
        Owner(port.ModKey, PortPlugin, "the port");
        uint suit = 0;
        if (vaultSuit is not null)
        {
            var suits = port.Armors.Where(x => string.Equals(x.EditorID, vaultSuit, StringComparison.OrdinalIgnoreCase)).ToList();
            if (suits.Count != 1) throw new Refusal($"{port.ModKey} has {suits.Count} ARMO {vaultSuit}, not one (--vault-suit names the port's vault suit by EditorID)");
            Owned(suits[0], port.ModKey, $"the vault suit {vaultSuit}");
            suit = suits[0].FormKey.ID;
        }
        SF.ICellGetter? cell = null;
        int cellBlockNum = 0, cellSubBlockNum = 0;
        foreach (var blk in port.Cells.Records)
            foreach (var sub in blk.SubBlocks)
                foreach (var c in sub.Cells)
                    if (c.EditorID == VaultCell && c.FormKey.ModKey == port.ModKey)
                    {
                        cell = c;
                        cellBlockNum = blk.BlockNumber;
                        cellSubBlockNum = sub.BlockNumber;
                    }
        if (cell is null) throw new Refusal($"{port.ModKey} has no cell {VaultCell}");
        var inCell = cell.Persistent.Concat(cell.Temporary).OfType<SF.IPlacedObjectGetter>().ToList();
        var cocs = inCell.Where(r => r.Base.FormKey == new FormKey(SfEsm, CocMarkerId)).ToList();
        if (cocs.Count != 1) throw new Refusal($"{VaultCell} has {cocs.Count} COC markers, not one");
        Owned(cocs[0], port.ModKey, "the vault's COC marker");
        // The script resolves the anchor at game start, while the vault is not loaded: a temporary reference in an
        // unloaded cell resolves to none (16 Oct probe, JOURNAL), so a persistent anchor is preferred. The COC marker
        // when it is; otherwise the port's own persistent reference in the cell nearest to it (the script moves the
        // player by the pod's offset from the anchor, so any persistent reference of the cell serves). 20 Oct review on
        // #393. With none at all (the port installed on 21 Oct: 0 persistent of 1,166) the build is refused unless
        // requirePersistentAnchor is off (--allow-temporary-anchor): the anchor is then the temporary COC marker and
        // AnchorTemporary tells the script to load the cell first (Debug.CenterOnCell(VaultCell)), after which the
        // marker resolves and the same MoveTo applies.
        var c0 = cocs[0].Position;
        float Dist(SF.IPlacedObjectGetter r) => MathF.Sqrt(MathF.Pow(r.Position.X - c0.X, 2) + MathF.Pow(r.Position.Y - c0.Y, 2) + MathF.Pow(r.Position.Z - c0.Z, 2));
        var persistent = IsPersistent(cocs[0]) ? cocs[0]
                       : cell.Persistent.OfType<SF.IPlacedObjectGetter>().Where(r => r.FormKey.ModKey == port.ModKey && IsPersistent(r))
                             .OrderBy(Dist).ThenBy(r => r.FormKey.ID).FirstOrDefault();
        if (persistent is null && requirePersistentAnchor)
            throw new Refusal($"{VaultCell} has no persistent reference of {port.ModKey} to anchor the start on (its COC marker is temporary, and a temporary reference does not resolve before the vault loads; --allow-temporary-anchor builds on the temporary COC marker and the script centers on the cell first, which during our own start's first load is unverified and hands nothing back when it moves nobody)");
        var anchor = persistent ?? cocs[0];
        bool anchorTemporary = persistent is null;
        uint cog = 0, console = 0, portPipboy = 0;
        var liftIds = new List<uint>();
        string cogBase = "none";
        var termRefs = new Dictionary<uint, uint>();            // FO4 terminal id -> the port's reference id
        using (var doc = JsonDocument.Parse(File.ReadAllText(portIds)))
            foreach (var e in doc.RootElement.EnumerateObject())
            {
                if (IsCogDoorKey(e.Name)) cog = e.Value.GetUInt32();
                if (IsRefKey(e.Name, Fo4Console)) console = e.Value.GetUInt32();
                if (IsRefKey(e.Name, Fo4PipboyPickup)) portPipboy = e.Value.GetUInt32();
                if (IsRefKey(e.Name, Fo4Platform)) liftIds.Add(e.Value.GetUInt32());
                foreach (var (src, _) in terminals ?? Array.Empty<(uint, P3Float)>())
                    if (IsRefKey(e.Name, src)) termRefs[src] = e.Value.GetUInt32();
            }
        uint lift = 0, liftBase = 0;
        if (animatedExitLift)
        {
            if (liftIds.Count != 1) throw new Refusal("animated exit needs exactly one original V111ElevatorREF mapping");
            var refs = inCell.Where(x => x.FormKey.ID == liftIds[0]).ToList();
            if (refs.Count != 1) throw new Refusal("lift mapping is not exactly one reference in the vault");
            Owned(refs[0], port.ModKey, "the exit lift");
            float scale = refs[0].Scale ?? 1f;
            var rotation = refs[0].Rotation;
            if (!float.IsFinite(scale) || !float.IsFinite(rotation.X) || !float.IsFinite(rotation.Y) || !float.IsFinite(rotation.Z) ||
                Math.Abs(scale - 1f) > 0.0001f || Math.Abs(rotation.X) > 0.0001f || Math.Abs(rotation.Y) > 0.0001f)
                throw new Refusal("exit lift must retain unit scale and vertical orientation");
            var bases = port.Activators.Where(a => a.FormKey == refs[0].Base.FormKey && a.EditorID == "FO4Port_acti_0244ef_fallout4").ToList();
            if (bases.Count != 1) throw new Refusal("exit lift is not the original Vault 111 lift ACTI");
            Owned(bases[0], port.ModKey, "the exit lift base");
            lift = refs[0].FormKey.ID;
            liftBase = bases[0].FormKey.ID;
        }
        if (cog != 0)
        {
            var r = inCell.FirstOrDefault(x => x.FormKey.ID == cog) ?? throw new Refusal($"formids.json names {cog:X6} as the cog door, not a reference of {VaultCell}");
            Owned(r, port.ModKey, "the cog door");
            cogBase = port.EnumerateMajorRecords().FirstOrDefault(x => x.FormKey == r.Base.FormKey) is { } b ? $"{b.GetType().Name.Replace("BinaryOverlay", "")} {b.EditorID}" : r.Base.FormKey.ToString();
        }
        if (console == 0)
            throw new Refusal($"formids.json has no mapping for gear-door console {Fo4Console:X8} in {VaultCell}");
        var consoleRefInPort = inCell.FirstOrDefault(x => x.FormKey.ID == console)
                               ?? throw new Refusal($"formids.json names {console:X6} as the cog door console, not a reference of {VaultCell}");
        Owned(consoleRefInPort, port.ModKey, "the cog door console");
        var consoleRot = consoleRefInPort.Rotation;
        if (portPipboy != 0)
        {
            var r = inCell.FirstOrDefault(x => x.FormKey.ID == portPipboy) ?? throw new Refusal($"formids.json names {portPipboy:X6} as the ground Pip-Boy static, not a reference of {VaultCell}");
            Owned(r, port.ModKey, "the ground Pip-Boy static");
        }
        // the SPECIAL terminal: the script resolves it once the player is in the vault (the cell is loaded, so a
        // temporary reference resolves too), but a persistent one is the safer handle; among equals, nearest the pod
        uint terminal = 0, terminalSrc = 0;
        var terminalPos = new P3Float(0, 0, 0);
        if (terminals is { Count: > 0 })
        {
            (terminalSrc, terminalPos) = terminals[0];
            var carried = new List<(uint Src, P3Float Pos, SF.IPlacedObjectGetter Ref, int Order)>();
            for (int i = 0; i < terminals.Count; i++)
                if (termRefs.TryGetValue(terminals[i].Src, out var id))
                {
                    var r = inCell.FirstOrDefault(x => x.FormKey.ID == id) ?? throw new Refusal($"formids.json names {id:X6} as terminal {terminals[i].Src:X8}, not a reference of {VaultCell}");
                    Owned(r, port.ModKey, $"terminal {terminals[i].Src:X8}");
                    carried.Add((terminals[i].Src, terminals[i].Pos, r, i));
                }
            if (carried.Count > 0)
            {
                var pick = carried.OrderByDescending(c => IsPersistent(c.Ref)).ThenBy(c => c.Order).First();
                (terminalSrc, terminalPos, terminal) = (pick.Src, pick.Pos, pick.Ref.FormKey.ID);
            }
        }
        using var core = SF.StarfieldMod.CreateFromBinaryOverlay(corePath, SF.StarfieldRelease.Starfield, Full(SfEsm));
        Owner(core.ModKey, CorePluginFile, "the core");
        var world = core.Worldspaces.FirstOrDefault(w => w.EditorID == World && w.FormKey.ModKey == core.ModKey)
                    ?? throw new Refusal($"{core.ModKey} has no worldspace {World}");
        var all = new List<SF.IPlacedGetter>();
        if (world.TopCell is { } top) all.AddRange(top.Persistent.Concat(top.Temporary));
        foreach (var b in world.SubCells) foreach (var s in b.Items) foreach (var c in s.Items) all.AddRange(c.Persistent.Concat(c.Temporary));
        var exits = all.OfType<SF.IPlacedObjectGetter>().Where(r => r.EditorID == exitAnchor).ToList();
        if (exits.Count != 1) throw new Refusal($"{World} has {exits.Count} references {exitAnchor}, not one");
        Owned(exits[0], core.ModKey, "the exit anchor");
        if (!IsPersistent(exits[0])) throw new Refusal($"{exitAnchor} is not persistent (MoveTo needs a persistent reference)");
        var coreMarkers = all.OfType<SF.IPlacedObjectGetter>()
            .Where(r => r.FormKey.ModKey == core.ModKey && IsPersistent(r) &&
                        (r.Base.FormKey == new FormKey(SfEsm, SfMapMarkerStaticId) ||
                         (r.EditorID is not null && r.EditorID.StartsWith("FO4Core_CommonwealthMapMarker", StringComparison.Ordinal))))
            .OrderBy(r => r.FormKey.ID)
            .Select(r => (int)r.FormKey.ID)
            .Distinct()
            .ToArray();
        return new Places(anchor.FormKey.ID, anchor.Position, cog, cogBase, exits[0].FormKey.ID, exits[0].Position, terminal, terminalSrc, terminalPos, suit, anchorTemporary, lift, liftBase, console, portPipboy, cell.FormKey.ID, cellBlockNum, cellSubBlockNum, coreMarkers, consoleRot);
    }

    static bool IsPersistent(IMajorRecordGetter r) => (r.MajorRecordFlagsRaw & 0x400) != 0;

    /// The script resolves each id as GetFormFromFile(id, <plugin name>), so the input must be the plugin of that name.
    static void Owner(ModKey key, string expected, string what)
    {
        if (!key.FileName.String.Equals(expected, StringComparison.OrdinalIgnoreCase))
            throw new Refusal($"{what} is {key.FileName}, but the script resolves its ids in {expected}");
    }

    /// A reference found in an owned cell or world can still be another plugin's record (an override of, say,
    /// Starfield.esm:000801): its local id in our plugin would then name a different record. Codex review on #393.
    static void Owned(IMajorRecordGetter r, ModKey owner, string what)
    {
        if (r.FormKey.ModKey != owner)
            throw new Refusal($"{what} {r.FormKey} is owned by {r.FormKey.ModKey}, not {owner}: its id would resolve to another record");
    }

    /// PluginSpike's key for the cog door's reference: REFR:FO4Port_Vault111Cryo:<FO4 FormKey>, the FormKey as Mutagen
    /// prints it (0330C3:Fallout4.esm, six digits; the PC's first build, 19 Oct, found no match for eight). The id is
    /// compared as a number, so either width matches.
    public static bool IsCogDoorKey(string key) => IsRefKey(key, Fo4CogDoor);

    /// formids.json's key for the port's reference of FO4 reference `src` in the vault cell (the cog door's form).
    public static bool IsRefKey(string key, uint src)
    {
        var prefix = $"REFR:{VaultCell}:";
        if (!key.StartsWith(prefix, StringComparison.OrdinalIgnoreCase)) return false;
        var parts = key[prefix.Length..].Split(':');
        return parts.Length == 2 && parts[1].Equals("Fallout4.esm", StringComparison.OrdinalIgnoreCase) &&
               uint.TryParse(parts[0], System.Globalization.NumberStyles.HexNumber, null, out var id) && id == src;
    }

    // ---------------------------------------------------------------- write (Starfield)

    static float[] Floats(JsonElement e) => e.EnumerateArray().Select(x => x.GetSingle()).ToArray();

    static (P3Float Pos, P3Float Rot) PipboyPlacement(JsonElement pts)
    {
        if (pts.TryGetProperty("pipboy_corpse", out var pb))
        {
            var p = Floats(pb.GetProperty("pos"));
            var r = pb.TryGetProperty("rot", out var re) ? Floats(re) : new[] { 0f, 0f, 3.8044f };
            return (new P3Float(p[0], p[1], p[2]), new P3Float(r[0], r[1], r[2]));
        }
        var con = Floats(pts.GetProperty("console").GetProperty("pos"));
        return (new P3Float(con[0] - 0.09f, con[1] + 1.55f, con[2] - 1.05f), new P3Float(0f, 0f, 3.8044f));
    }

    /// Every script property the plugin writes, by name: what the check compares and the Python contract test reads.
    public static List<(string Name, object Value)> Properties(JsonElement pts, Places p, Options o, WarfareTable wf, StartPlaceTable sp, uint vaultPistolId, int[]? routeLootRefIds = null)
    {
        var pod = Floats(pts.GetProperty("pod").GetProperty("pos"));
        var con = Floats(pts.GetProperty("console").GetProperty("pos"));
        var plat = Floats(pts.GetProperty("platform").GetProperty("pos"));
        var arr = Floats(pts.GetProperty("arrival").GetProperty("pos"));
        return new()
        {
            ("VaultAnchorId", (int)p.VaultAnchor), ("AnchorX", p.AnchorPos.X), ("AnchorY", p.AnchorPos.Y), ("AnchorZ", p.AnchorPos.Z),
            ("PodX", pod[0]), ("PodY", pod[1]), ("PodZ", pod[2]), ("PodHeading", pts.GetProperty("pod").GetProperty("heading").GetSingle()),
            ("CogDoorId", (int)p.CogDoor), ("ConsoleRefId", (int)p.Console), ("ConsoleX", con[0]), ("ConsoleY", con[1]), ("ConsoleZ", con[2]),
            ("PortPipboyStaticId", (int)p.PortPipboyStatic), ("VaultPistolId", (int)vaultPistolId),
            ("PlatformX", plat[0]), ("PlatformY", plat[1]), ("PlatformZ", plat[2]),
            ("LiftId", (int)p.Lift), ("LiftBaseId", (int)p.LiftBase), ("LiftRise", 21.6f), ("LiftSeconds", 9.8667f),
            ("ExitAnchorId", (int)p.ExitAnchor), ("ArrivalX", arr[0]), ("ArrivalY", arr[1]), ("ArrivalZ", arr[2]),
            ("ArrivalDiscoveryId", o.ExitAnchor == ExitAnchorEdid ? (int)p.ExitAnchor : 0),
            ("ArrivalHeading", pts.GetProperty("arrival").GetProperty("heading").GetSingle()),
            ("FallbackX", p.ExitPos.X), ("FallbackY", p.ExitPos.Y), ("FallbackZ", p.ExitPos.Z),
            ("MergeOffsetX", MergeX), ("MergeOffsetY", MergeY), ("LooksWait", o.Looks ? 120f : 0f),
            ("ClearInventory", o.ClearInventory), ("VaultSuitId", (int)p.VaultSuit),
            ("AnchorTemporary", p.AnchorTemporary), ("VaultCell", VaultCell),
            ("DebugAfterHold", o.DebugAfterHold),           // written into MQ101Debug right after the hold-off (0: never)
            ("O2CapacityAmount", o.O2 ? O2CapacityAmount : 0f),   // added to O2Capacity right after the reset (0: never)
            ("FadeHold", o.FadeHold), ("RaceMenuMode", o.RaceMenuMode),
            ("StartChoiceBackdrop", o.StartChoiceBackdrop),
            ("CoreMarkerIds", p.CoreMarkers ?? Array.Empty<int>()),
            ("RouteLootRefIds", routeLootRefIds ?? Array.Empty<int>()),
            ("MapMarkerQuestIds", new[] { 0x800 }),
            ("WarfareKeys", wf.Keys), ("WarfareFactionSlots", wf.FactionSlots), ("WarfareDistinctFactionSlots", wf.DistinctFactionSlots),
            ("WarfareMarkerIds", wf.MarkerIds), ("WarfareMarkerX", wf.MarkerX), ("WarfareMarkerY", wf.MarkerY), ("WarfareMarkerZ", wf.MarkerZ),
            ("WarfareHeadings", wf.Headings), ("WarfareMinDiffs", wf.MinDiffs), ("WarfareMaxDiffs", wf.MaxDiffs),
            ("WarfareBgIndices", wf.BgIndices), ("WarfareFames", wf.Fames), ("WarfareInfamies", wf.Infamies),
            ("WarfareKarmas", wf.Karmas), ("WarfareSquadCaps", wf.SquadCaps),
            ("WarfareGearRowIndices", wf.GearRowIndices), ("WarfareGearPlugins", wf.GearPlugins),
            ("WarfareGearIds", wf.GearIds), ("WarfareGearCounts", wf.GearCounts), ("WarfareGearEquips", wf.GearEquips),
            ("StoryChoiceIds", sp.StoryIds),
            ("StartPlaceIds", sp.PlaceIds), ("StartPlaceModes", sp.PlaceModes), ("StartPlaceStories", sp.PlaceStories),
            ("StartPlacePlugins", sp.PlacePlugins), ("StartPlaceMarkerIds", sp.PlaceMarkerIds),
            ("StartPlaceX", sp.PlaceX), ("StartPlaceY", sp.PlaceY), ("StartPlaceZ", sp.PlaceZ), ("StartPlaceHeadings", sp.PlaceHeadings),
            ("StartPlaceIsInterior", sp.PlaceIsInterior), ("StartPlaceQuestMasks", sp.PlaceQuestMasks), ("StartPlaceWarfareRows", sp.PlaceWarfareRows),
        };
    }

    /// The looks script's value properties (its StartMessage is an object property, written beside them).
    public static List<(string Name, object Value)> LooksProperties(Options o) => new() { ("RaceMenuMode", o.RaceMenuMode) };

    /// The SPECIAL script's value properties (Special, TerminalMessage and SpecialMessage are object properties, written
    /// beside them): the terminal the port carries (0 when none) and points' spot of the terminal the prompt watches.
    /// A points.json without a terminal refuses a SPECIAL build: --no-special, or points --terminal-ref.
    public static List<(string Name, object Value)> SpecialProperties(JsonElement pts, Places p)
    {
        if (Terminals(pts).Count == 0) throw new Refusal("points.json has no terminal in Vault111Cryo: build with --no-special, or run points with --terminal-ref <hex>");
        return new()
        {
            ("TerminalId", (int)p.Terminal), ("TerminalX", p.TerminalPos.X), ("TerminalY", p.TerminalPos.Y), ("TerminalZ", p.TerminalPos.Z),
        };
    }

    static SF.ScriptProperty ValueProperty(string name, object value) => value switch
    {
        int i => new SF.ScriptIntProperty { Name = name, Flags = SF.ScriptProperty.Flag.Edited, Data = i },
        float f => new SF.ScriptFloatProperty { Name = name, Flags = SF.ScriptProperty.Flag.Edited, Data = f },
        bool b => new SF.ScriptBoolProperty { Name = name, Flags = SF.ScriptProperty.Flag.Edited, Data = b },
        string s => new SF.ScriptStringProperty { Name = name, Flags = SF.ScriptProperty.Flag.Edited, Data = s },
        int[] ia => new SF.ScriptIntListProperty { Name = name, Flags = SF.ScriptProperty.Flag.Edited, Data = new ExtendedList<int>(ia) },
        float[] fa => new SF.ScriptFloatListProperty { Name = name, Flags = SF.ScriptProperty.Flag.Edited, Data = new ExtendedList<float>(fa) },
        bool[] ba => new SF.ScriptBoolListProperty { Name = name, Flags = SF.ScriptProperty.Flag.Edited, Data = new ExtendedList<bool>(ba) },
        string[] sa => new SF.ScriptStringListProperty { Name = name, Flags = SF.ScriptProperty.Flag.Edited, Data = new ExtendedList<string>(sa) },
        _ => throw new Refusal($"property {name}: unsupported value"),
    };

    static bool ValueMatches(object value, SF.IScriptPropertyGetter p) => (value, p) switch
    {
        (int i, SF.IScriptIntPropertyGetter ip) => ip.Data == i,
        (float f, SF.IScriptFloatPropertyGetter fp) => fp.Data == f && float.IsFinite(fp.Data),
        (bool b, SF.IScriptBoolPropertyGetter bp) => bp.Data == b,
        (string s, SF.IScriptStringPropertyGetter sp) => sp.Data == s,
        (int[] ia, SF.IScriptIntListPropertyGetter il) => il.Data.SequenceEqual(ia),
        (float[] fa, SF.IScriptFloatListPropertyGetter fl) => fl.Data.Count == fa.Length && fl.Data.Zip(fa).All(x => x.First == x.Second && float.IsFinite(x.First)),
        (bool[] ba, SF.IScriptBoolListPropertyGetter bl) => bl.Data.SequenceEqual(ba),
        (string[] sa, SF.IScriptStringListPropertyGetter sl) => sl.Data.SequenceEqual(sa),
        _ => false,
    };

    public static int Write(string sfPath, string portPath, string portIds, string corePath, string pointsPath, string outDir, Options o)
    {
        RefuseForbiddenOutDir(outDir);
        var (coreKey, coreIds) = LoadCoreValues(o.CoreValuesJson);
        var specialKeys = SpecialNames.Select(n => new FormKey(coreKey, RequireCoreId(coreIds, SpecialAvifPrefix + n))).ToList();
        var testModeKey = new FormKey(coreKey, RequireCoreId(coreIds, TestModeGlobEdid));
        var startCardOpenKey = new FormKey(coreKey, RequireCoreId(coreIds, StartCardOpenGlobEdid));
        var gameModeKey = new FormKey(coreKey, RequireCoreId(coreIds, GameModeGlobEdid));
        var survStartKey = new FormKey(coreKey, RequireCoreId(coreIds, SurvivalStartGlobEdid));
        var survLockedKey = new FormKey(coreKey, RequireCoreId(coreIds, SurvivalLockedGlobEdid));
        var startDiffKey = new FormKey(coreKey, RequireCoreId(coreIds, StartDifficultyGlobEdid));
        var wfFactionKey = new FormKey(coreKey, RequireCoreId(coreIds, WarfareFactionGlobEdid));
        var wfStartIdxKey = new FormKey(coreKey, RequireCoreId(coreIds, WarfareStartIndexGlobEdid));
        var choiceDoneKey = new FormKey(coreKey, RequireCoreId(coreIds, StartChoiceDoneGlobEdid));
        var startNeutralSpotKey = new FormKey(coreKey, RequireCoreId(coreIds, StartNeutralSpotGlobEdid));
        var storyLineKey = new FormKey(coreKey, RequireCoreId(coreIds, StoryLineGlobEdid));
        var startPlaceRowKey = new FormKey(coreKey, RequireCoreId(coreIds, StartPlaceRowGlobEdid));
        var pipboyAcquiredKey = new FormKey(coreKey, RequireCoreId(coreIds, PipboyAcquiredGlobEdid));
        var h00SkipLoadingHookKey = new FormKey(coreKey, RequireCoreId(coreIds, H00SkipLoadingHookGlobEdid));
        var h00ClearChargenKey = new FormKey(coreKey, RequireCoreId(coreIds, H00ClearChargenGlobEdid));
        var h00SkipArrivalDiscoveryKey = new FormKey(coreKey, RequireCoreId(coreIds, H00SkipArrivalDiscoveryGlobEdid));
        var h00SkipMapSetupKey = new FormKey(coreKey, RequireCoreId(coreIds, H00SkipMapSetupGlobEdid));
        var h00SkipRouteLootKey = new FormKey(coreKey, RequireCoreId(coreIds, H00SkipRouteLootGlobEdid));
        var h00SkipMissionActorsKey = new FormKey(coreKey, RequireCoreId(coreIds, H00SkipMissionActorsGlobEdid));
        var h00SkipLandingQuestsKey = new FormKey(coreKey, RequireCoreId(coreIds, H00SkipLandingQuestsGlobEdid));
        var h00SkipSurfaceSetPosKey = new FormKey(coreKey, RequireCoreId(coreIds, H00SkipSurfaceSetPosGlobEdid));
        var pts = JsonDocument.Parse(File.ReadAllText(pointsPath)).RootElement;
        var places = Resolve(portPath, portIds, corePath, o.ExitAnchor, Terminals(pts), o.VaultSuit, o.RequirePersistentAnchor, o.AnimatedExitLift);
        using var sf = SF.StarfieldMod.CreateFromBinaryOverlay(sfPath, SF.StarfieldRelease.Starfield);
        var wf = LoadWarfareStarts(o.WarfareStartsJson, sf, corePath);
        var sp = LoadStartPlaces(o.StartPlacesJson, pts, places, wf, portPath, corePath);
        uint vaultPistolId = LoadVaultPistolId(o.RouteLootJson, sf);
        var routeLootRefIds = LoadRouteLootRefIds(o.RouteLootJson, corePath, places.ExitPos);
        var vaultPistolKey = new FormKey(SfEsm, vaultPistolId);
        var modKey = ModKey.FromFileName(o.Plugin);
        var mod = new SF.StarfieldMod(modKey, SF.StarfieldRelease.Starfield);
        mod.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Master;
        mod.ModHeader.Author = "fo4-to-starfield NewGame";

        var qtyp = sf.Keywords.FirstOrDefault(k => k.FormKey == new FormKey(SfEsm, QuestTypeSideId) && k.EditorID == QuestTypeSideEdid)
                   ?? throw new Refusal($"Starfield.esm {QuestTypeSideId:X6} is not the KYWD {QuestTypeSideEdid}");
        var days = sf.Globals.FirstOrDefault(g => g.FormKey == new FormKey(SfEsm, GameDaysPassedId) && g.EditorID == GameDaysPassedEdid)
                   ?? throw new Refusal($"Starfield.esm {GameDaysPassedId:X6} is not the GLOB {GameDaysPassedEdid}");
        var hold = o.Hold.Select(e => sf.Quests.FirstOrDefault(q => q.EditorID == e) ?? throw new Refusal($"Starfield.esm has no quest {e}")).ToList();
        // the opening: the guard line reads its stage, and the script asks it to start (StartNoWait) when our start
        // stands down during the load (unverified that it then moves the player)
        var opening = sf.Quests.FirstOrDefault(q => q.EditorID == OpeningEdid) ?? throw new Refusal($"Starfield.esm has no quest {OpeningEdid}");
        var startup = Startup(sf, opening);
        // the debug global the script reads for its guard line and writes after the hold-off; overridden below only under --mq101debug
        var debugGlob = sf.Globals.FirstOrDefault(x => x.EditorID == DebugGlobEdid) ?? throw new Refusal($"Starfield.esm has no GLOB {DebugGlobEdid}");

        var msg = new SF.Message(new FormKey(modKey, MessageId), SF.StarfieldRelease.Starfield)
        {
            EditorID = MessageEdid, Name = "Vault 111 elevator",
            Description = "Leave Vault 111 for the Commonwealth, or revise your S.P.E.C.I.A.L. first?",
            Flags = SF.Message.Flag.MessageBox,
        };
        foreach (var b in ExitButtons) msg.MenuButtons.Add(new SF.MessageButton { Text = b });
        mod.Messages.Add(msg);
        var returnMsg = new SF.Message(new FormKey(modKey, ReturnMsgId), SF.StarfieldRelease.Starfield)
        {
            EditorID = ReturnMsgEdid, Name = "Vault 111 lift",
            Description = "Ride the platform back down into Vault 111?",
            Flags = SF.Message.Flag.MessageBox,
        };
        foreach (var b in ReturnButtons) returnMsg.MenuButtons.Add(new SF.MessageButton { Text = b });
        mod.Messages.Add(returnMsg);

        SF.Message MakeMsg(uint id, string edid, string title, string desc, IEnumerable<string> btns)
        {
            var m = new SF.Message(new FormKey(modKey, id), SF.StarfieldRelease.Starfield)
            {
                EditorID = edid, Name = title, Description = desc, Flags = SF.Message.Flag.MessageBox,
            };
            foreach (var b in btns) m.MenuButtons.Add(new SF.MessageButton { Text = b });
            mod.Messages.Add(m);
            return m;
        }
        var modePickMsg = MakeMsg(ModePickMsgId, ModePickMsgEdid, "Select Game Mode", "Choose how you want to start:", ModeButtons);
        var storyLineMsg = MakeMsg(StoryLineMsgId, StoryLineMsgEdid, "Select Story", "Choose which story campaign to begin:", sp.StoryLabels);
        var survPickMsg = MakeMsg(SurvivalPickMsgId, SurvivalPickMsgEdid, "Survival Mode", "Enable Survival mode for this character?", SurvivalButtons);
        var wfDiffMsg = MakeMsg(WarfareDiffMsgId, WarfareDiffMsgEdid, "Warfare Difficulty", "Choose your starting difficulty:", WarfareDiffButtons);
        var wfGroupMsg = MakeMsg(WarfareGroupMsgId, WarfareGroupMsgEdid, "Warfare Allegiance", "Choose your starting allegiance:", wf.FactionButtons);
        var wfSpotMsg = MakeMsg(WarfareSpotMsgId, WarfareSpotMsgEdid, "Warfare Deployment", "Choose your starting deployment:", wf.SpotButtons);
        var noPipboyMsg = MakeMsg(NoPipboyMsgId, NoPipboyMsgEdid, "Vault Door Controls", "A Pip-Boy is required to interface with the Vault 111 door controls.", NoPipboyButtons);
        var exitFallbackMsg = MakeMsg(ExitFallbackMsgId, ExitFallbackMsgEdid, "Vault 111 elevator", "The elevator platform did not reach the surface. Go up to the Commonwealth directly, or try the lift again?", ExitFallbackButtons);
        var exitNeedSpecialMsg = MakeMsg(ExitNeedSpecialMsgId, ExitNeedSpecialMsgEdid, "Vault 111 elevator", "Confirm your S.P.E.C.I.A.L. attributes before leaving Vault 111.", ExitNeedSpecialButtons);
        // the opening choice (NG-6, NG-C9, T4): button 0 keeps the preset and skips the creator, button 1 opens the creator. A
        // message box, so it needs no voice: the player is silent
        var start = new SF.Message(new FormKey(modKey, StartMessageId), SF.StarfieldRelease.Starfield)
        {
            EditorID = StartMessageEdid, Name = "Character Appearance", Description = "Start quickly with the preset, or create your character?",
            Flags = SF.Message.Flag.MessageBox,
        };
        start.MenuButtons.Add(new SF.MessageButton { Text = "Quick start" });
        start.MenuButtons.Add(new SF.MessageButton { Text = "Create character" });
        mod.Messages.Add(start);
        // SPECIAL at the vault terminal (NG-5 / NG-C4): the prompt and two <=7-button allocation MESGs (the seven AVIFs live in FO4SFCoreValues.esm)
        SF.Message? terminalMsg = null, specialMsg = null, specialMsgPage2 = null;
        if (o.Special)
        {
            terminalMsg = new SF.Message(new FormKey(modKey, TerminalMessageId), SF.StarfieldRelease.Starfield)
            {
                EditorID = TerminalMessageEdid, Name = "Vault 111 terminal", Description = "Set your S.P.E.C.I.A.L. at this terminal?",
                Flags = SF.Message.Flag.MessageBox,
            };
            terminalMsg.MenuButtons.Add(new SF.MessageButton { Text = "Set SPECIAL" });
            terminalMsg.MenuButtons.Add(new SF.MessageButton { Text = "Later" });
            mod.Messages.Add(terminalMsg);
            // the text's %.0f tokens take Message.Show's float arguments (the seven values, then the points left), as
            // FO4's message boxes do; split across two <=7-button pages with Confirm reachable on Page 1
            specialMsg = new SF.Message(new FormKey(modKey, SpecialMessageId), SF.StarfieldRelease.Starfield)
            {
                EditorID = SpecialMessageEdid, Name = "S.P.E.C.I.A.L. (S / P / E)",
                Description = SpecialDescription, Flags = SF.Message.Flag.MessageBox,
            };
            foreach (var b in SpecialPage1Buttons) specialMsg.MenuButtons.Add(new SF.MessageButton { Text = b });
            mod.Messages.Add(specialMsg);
            specialMsgPage2 = new SF.Message(new FormKey(modKey, SpecialMessagePage2Id), SF.StarfieldRelease.Starfield)
            {
                EditorID = SpecialMessagePage2Edid, Name = "S.P.E.C.I.A.L. (C / I / A / L)",
                Description = SpecialDescription, Flags = SF.Message.Flag.MessageBox,
            };
            foreach (var b in SpecialPage2Buttons) specialMsgPage2.MenuButtons.Add(new SF.MessageButton { Text = b });
            mod.Messages.Add(specialMsgPage2);
        }

        // Pip-Boy corpse pickup + gear-door console: playable wrist ARMO 0x80D, ACTIs 0x80E & 0x818, persistent REFRs 0x80F & 0x819 in FO4Port_Vault111Cryo
        // (FO4SF_PipboyAcquired GLOB lives solely in FO4SFCoreValues.esm:000865; 0x80C and 0x810..0x816 stay reserved)
        var wristTpl = sf.Armors.FirstOrDefault(a => a.FormKey == new FormKey(SfEsm, SfChronomarkArmorId))
                       ?? sf.Armors.FirstOrDefault(a => a.FormKey == new FormKey(SfEsm, SfFallbackJumpsuitId))
                       ?? throw new Refusal($"Starfield.esm has neither wrist template {SfChronomarkArmorId:X6} nor fallback {SfFallbackJumpsuitId:X6}");
        var pipboyWrist = (SF.Armor)wristTpl.Duplicate(new FormKey(modKey, PipboyWristArmorId));
        pipboyWrist.EditorID = PipboyWristArmorEdid;
        pipboyWrist.Name = "Pip-Boy 3000";
        pipboyWrist.VirtualMachineAdapter = null;
        pipboyWrist.MajorRecordFlagsRaw &= ~0x4;
        mod.Armors.Add(pipboyWrist);

        using var port = SF.StarfieldMod.CreateFromBinaryOverlay(portPath, SF.StarfieldRelease.Starfield, Full(SfEsm));
        var actiTpl = sf.Activators.FirstOrDefault(a => a.FormKey == new FormKey(SfEsm, SfConsoleActiTemplateId));
        var pipboyActi = actiTpl is not null
            ? (SF.Activator)actiTpl.Duplicate(new FormKey(modKey, PipboyCorpseActiId))
            : new SF.Activator(new FormKey(modKey, PipboyCorpseActiId), SF.StarfieldRelease.Starfield);
        pipboyActi.EditorID = PipboyCorpseActiEdid;
        pipboyActi.Name = "Pip-Boy 3000";
        pipboyActi.ActivateTextOverride = "Take";
        pipboyActi.VirtualMachineAdapter = null;
        var portPipboyStat = port.Statics.FirstOrDefault(s => s.EditorID == PortPipboyStaticEdid && s.Model is not null);
        if (portPipboyStat?.Model is not null)
            pipboyActi.Model = SF.ModelMixIn.DeepCopy(portPipboyStat.Model);
        mod.Activators.Add(pipboyActi);

        var gearConsoleActi = actiTpl is not null
            ? (SF.Activator)actiTpl.Duplicate(new FormKey(modKey, GearDoorConsoleActiId))
            : new SF.Activator(new FormKey(modKey, GearDoorConsoleActiId), SF.StarfieldRelease.Starfield);
        gearConsoleActi.EditorID = GearDoorConsoleActiEdid;
        gearConsoleActi.Name = "Vault Door Controls";
        gearConsoleActi.ActivateTextOverride = "Activate";
        gearConsoleActi.VirtualMachineAdapter = null;
        mod.Activators.Add(gearConsoleActi);

        var portCell = port.EnumerateMajorRecords<SF.ICellGetter>().First(c => c.FormKey == new FormKey(PortEsm, places.PortCellId));
        var cellOver = (SF.Cell)portCell.DeepCopy();
        cellOver.Persistent.Clear();
        cellOver.Temporary.Clear();
        var (pbPos, pbRot) = PipboyPlacement(pts);
        var pipboyRef = new SF.PlacedObject(new FormKey(modKey, PipboyCorpseRefId), SF.StarfieldRelease.Starfield)
        {
            EditorID = PipboyCorpseRefEdid,
            Base = new FormLinkNullable<SF.IPlaceableObjectGetter>(pipboyActi.FormKey),
            Position = pbPos,
            Rotation = pbRot,
            Scale = 1.05f,
        };
        pipboyRef.MajorRecordFlagsRaw |= 0x400;
        cellOver.Persistent.Add(pipboyRef);
        var conCoords = Floats(pts.GetProperty("console").GetProperty("pos"));
        var gearConsoleRef = new SF.PlacedObject(new FormKey(modKey, GearDoorConsoleRefId), SF.StarfieldRelease.Starfield)
        {
            EditorID = GearDoorConsoleRefEdid,
            Base = new FormLinkNullable<SF.IPlaceableObjectGetter>(gearConsoleActi.FormKey),
            Position = new P3Float(conCoords[0], conCoords[1], conCoords[2]),
            Rotation = places.ConsoleRot,
        };
        gearConsoleRef.MajorRecordFlagsRaw |= 0x400;
        cellOver.Persistent.Add(gearConsoleRef);
        // T4 / T1: place Vault 111 pistol + 48 rounds in cellOver so Story pistol pickup works when FO4SFRouteLoot.esm is omitted
        bool hasVaultPistolAndAmmo = sf.Weapons.Any(w => w.FormKey == new FormKey(SfEsm, SfVaultPistolId)) &&
                                     sf.Ammunitions.Any(a => a.FormKey == new FormKey(SfEsm, SfVaultAmmoId));
        if (hasVaultPistolAndAmmo)
        {
            var pistolRef = new SF.PlacedObject(new FormKey(modKey, VaultPistolRefId), SF.StarfieldRelease.Starfield)
            {
                EditorID = VaultPistolRefEdid,
                Base = new FormLinkNullable<SF.IPlaceableObjectGetter>(new FormKey(SfEsm, SfVaultPistolId)),
                Position = new P3Float(-57.0338f, 30.006f, 1.29f),
                Rotation = new P3Float(-1.444f, 0.412f, 4.831f),
            };
            cellOver.Temporary.Add(pistolRef);
            var ammoRef = new SF.PlacedObject(new FormKey(modKey, VaultAmmoRefId), SF.StarfieldRelease.Starfield)
            {
                EditorID = VaultAmmoRefEdid,
                Base = new FormLinkNullable<SF.IPlaceableObjectGetter>(new FormKey(SfEsm, SfVaultAmmoId)),
                Position = new P3Float(-57.0522f, 30.3703f, 0.696f),
                Rotation = new P3Float(0.001f, 0.0f, 2.835f),
                Count = VaultAmmoCount,
            };
            cellOver.Temporary.Add(ammoRef);
        }
        var cBlock = new SF.CellBlock { BlockNumber = places.CellBlockNum, GroupType = SF.GroupTypeEnum.InteriorCellBlock };
        var cSub = new SF.CellSubBlock { BlockNumber = places.CellSubBlockNum, GroupType = SF.GroupTypeEnum.InteriorCellSubBlock };
        cSub.Cells.Add(cellOver);

        // N2: Owned empty pre-world staging room FO4SF_StartRoomCell (0x00081C) with persistent FO4SF_StartRoomMarkerRef (0x00081D)
        var startRoomCell = new SF.Cell(new FormKey(modKey, StartRoomCellId), SF.StarfieldRelease.Starfield)
        {
            EditorID = StartRoomCellEdid,
            Name = "Start Setup",
            Flags = SF.Cell.Flag.IsInteriorCell,
            Lighting = new SF.CellLighting
            {
                AmbientColor = System.Drawing.Color.FromArgb(255, 18, 22, 18),
                DirectionalColor = System.Drawing.Color.FromArgb(255, 24, 28, 24),
                FogNearColor = System.Drawing.Color.FromArgb(255, 12, 14, 12),
                DirectionalFade = 1f,
                FogClipDistance = 200f,
                FogPower = 1f,
            },
        };
        var startRoomMarkerRef = new SF.PlacedObject(new FormKey(modKey, StartRoomMarkerRefId), SF.StarfieldRelease.Starfield)
        {
            EditorID = StartRoomMarkerRefEdid,
            Base = new FormLinkNullable<SF.IPlaceableObjectGetter>(new FormKey(SfEsm, CocMarkerId)),
            Position = new P3Float(0f, 0f, 0f),
            Rotation = new P3Float(0f, 0f, 0f),
        };
        startRoomMarkerRef.MajorRecordFlagsRaw |= 0x400;
        startRoomCell.Persistent.Add(startRoomMarkerRef);

        if (places.CellBlockNum == 0 && places.CellSubBlockNum == 0)
        {
            cSub.Cells.Add(startRoomCell);
            cBlock.SubBlocks.Add(cSub);
            mod.Cells.Records.Add(cBlock);
        }
        else
        {
            cBlock.SubBlocks.Add(cSub);
            mod.Cells.Records.Add(cBlock);
            var sBlock = new SF.CellBlock { BlockNumber = 0, GroupType = SF.GroupTypeEnum.InteriorCellBlock };
            var sSub = new SF.CellSubBlock { BlockNumber = 0, GroupType = SF.GroupTypeEnum.InteriorCellSubBlock };
            sSub.Cells.Add(startRoomCell);
            sBlock.SubBlocks.Add(sSub);
            mod.Cells.Records.Add(sBlock);
        }

        var quest = new SF.Quest(new FormKey(modKey, QuestId), SF.StarfieldRelease.Starfield)
        {
            EditorID = QuestEdid, Name = pts.GetProperty("quest_name").GetString(), FormVersion = 581, Version2 = 12,
            // not start game enabled: the engine starts it as the startup quest on a New Game, and nothing starts it on a save
            Data = new SF.QuestData { Flags = SF.Quest.Flag.RunOnce | SF.Quest.Flag.DisplaysInHud, Priority = 70 },
        };
        quest.QuestType.SetTo(qtyp.FormKey);
        foreach (var s in Stages)
        {
            var st = new SF.QuestStage { Index = s };
            if (s == 200 || s == 210) st.LogEntries.Add(new SF.QuestLogEntry { Flags = SF.QuestLogEntry.Flag.CompleteQuest });
            quest.Stages.Add(st);
        }
        quest.Objectives.Add(new SF.QuestObjective { Index = Objective, DisplayText = ObjectiveText });
        var script = new SF.ScriptEntry { Name = ScriptName, Flags = SF.ScriptEntry.Flag.Local };
        SF.ScriptObjectProperty Obj(string name, FormKey fk) => new()
        {
            Name = name, Flags = SF.ScriptProperty.Flag.Edited, Object = new FormLink<SF.IStarfieldMajorRecordGetter>(fk), Alias = -1, Unused = 0,
        };
        script.Properties.Add(Obj("GameDaysPassed", days.FormKey));
        script.Properties.Add(Obj("Opening", opening.FormKey));
        script.Properties.Add(Obj("DebugGlobal", debugGlob.FormKey));
        var list = new SF.ScriptObjectListProperty { Name = "HoldOff", Flags = SF.ScriptProperty.Flag.Edited };
        foreach (var q in hold) list.Objects.Add(Obj("", q.FormKey));
        script.Properties.Add(list);
        script.Properties.Add(Obj("ExitMessage", msg.FormKey));
        script.Properties.Add(Obj("ExitNeedAttrMsg", exitNeedSpecialMsg.FormKey));
        script.Properties.Add(Obj("ExitFallbackMessage", exitFallbackMsg.FormKey));
        script.Properties.Add(Obj("ReturnMessage", returnMsg.FormKey));
        script.Properties.Add(Obj("ModePickMsg", modePickMsg.FormKey));
        script.Properties.Add(Obj("StoryLineMsg", storyLineMsg.FormKey));
        script.Properties.Add(Obj("SurvivalPickMsg", survPickMsg.FormKey));
        script.Properties.Add(Obj("WarfareDiffMsg", wfDiffMsg.FormKey));
        script.Properties.Add(Obj("WarfareGroupMsg", wfGroupMsg.FormKey));
        script.Properties.Add(Obj("WarfareSpotMsg", wfSpotMsg.FormKey));
        script.Properties.Add(Obj("StartPickMsg", start.FormKey));
        script.Properties.Add(Obj("NoPipboyMsg", noPipboyMsg.FormKey));
        script.Properties.Add(Obj("O2Capacity", new FormKey(SfEsm, O2CapacityId)));   // linked by id: no AVIF record
        script.Properties.Add(Obj("TestModeGlobal", testModeKey));
        script.Properties.Add(Obj("StartCardOpenGlobal", startCardOpenKey));
        script.Properties.Add(Obj("GameModeGlobal", gameModeKey));
        script.Properties.Add(Obj("SurvivalStartGlobal", survStartKey));
        script.Properties.Add(Obj("SurvivalLockedGlobal", survLockedKey));
        script.Properties.Add(Obj("StartDifficultyGlobal", startDiffKey));
        script.Properties.Add(Obj("WarfareFactionGlobal", wfFactionKey));
        script.Properties.Add(Obj("WarfareStartIndexGlobal", wfStartIdxKey));
        script.Properties.Add(Obj("StartChoiceDoneGlobal", choiceDoneKey));
        script.Properties.Add(Obj("StartNeutralSpotGlobal", startNeutralSpotKey));
        script.Properties.Add(Obj("StoryLineGlobal", storyLineKey));
        script.Properties.Add(Obj("StartPlaceRowGlobal", startPlaceRowKey));
        script.Properties.Add(Obj("PipboyAcquiredGlobal", pipboyAcquiredKey));
        script.Properties.Add(Obj("H00SkipLoadingHookGlobal", h00SkipLoadingHookKey));
        script.Properties.Add(Obj("H00ClearChargenGlobal", h00ClearChargenKey));
        script.Properties.Add(Obj("H00SkipArrivalDiscoveryGlobal", h00SkipArrivalDiscoveryKey));
        script.Properties.Add(Obj("H00SkipMapSetupGlobal", h00SkipMapSetupKey));
        script.Properties.Add(Obj("H00SkipRouteLootGlobal", h00SkipRouteLootKey));
        script.Properties.Add(Obj("H00SkipMissionActorsGlobal", h00SkipMissionActorsKey));
        script.Properties.Add(Obj("H00SkipLandingQuestsGlobal", h00SkipLandingQuestsKey));
        script.Properties.Add(Obj("H00SkipSurfaceSetPosGlobal", h00SkipSurfaceSetPosKey));
        script.Properties.Add(Obj("PipboyWristArmor", pipboyWrist.FormKey));
        script.Properties.Add(Obj("PipboyCorpseRef", pipboyRef.FormKey));
        script.Properties.Add(Obj("GearDoorConsoleRef", gearConsoleRef.FormKey));
        script.Properties.Add(Obj("StartRoomMarkerRef", startRoomMarkerRef.FormKey));
        script.Properties.Add(Obj("VaultPistolBase", vaultPistolKey));
        foreach (var (name, value) in Properties(pts, places, o, wf, sp, vaultPistolId, routeLootRefIds))
            script.Properties.Add(ValueProperty(name, value));
        quest.VirtualMachineAdapter = new SF.QuestAdapter
        {
            Version = 6, ObjectFormat = 2, ExtraBindDataVersion = 3,
            Script = new SF.ScriptEntry { Name = "", Flags = SF.ScriptEntry.Flag.Local },
        };
        quest.VirtualMachineAdapter.Scripts.Add(script);
        if (o.Looks)
        {
            var looks = new SF.ScriptEntry { Name = LooksScript, Flags = SF.ScriptEntry.Flag.Local };
            looks.Properties.Add(Obj("StartMessage", start.FormKey));
            foreach (var (name, value) in LooksProperties(o)) looks.Properties.Add(ValueProperty(name, value));
            quest.VirtualMachineAdapter.Scripts.Add(looks);
        }
        if (o.Special)
        {
            var special = new SF.ScriptEntry { Name = SpecialScript, Flags = SF.ScriptEntry.Flag.Local };
            var avs = new SF.ScriptObjectListProperty { Name = "Special", Flags = SF.ScriptProperty.Flag.Edited };
            foreach (var fk in specialKeys) avs.Objects.Add(Obj("", fk));
            special.Properties.Add(avs);
            special.Properties.Add(Obj("TerminalMessage", terminalMsg!.FormKey));
            special.Properties.Add(Obj("SpecialMessage", specialMsg!.FormKey));
            special.Properties.Add(Obj("SpecialMessagePage2", specialMsgPage2!.FormKey));
            foreach (var (name, value) in SpecialProperties(pts, places)) special.Properties.Add(ValueProperty(name, value));
            quest.VirtualMachineAdapter.Scripts.Add(special);
        }
        // the save version check (NG-15 / NG-L2): our constant GLOB, and the player alias whose script compares it on
        // every load. The alias script is bound through the VMAD's alias fragment (the quest's form and the alias id),
        // the shape Mutagen reads back; whether the game binds it so is unverified until the PC run
        if (o.Version)
        {
            mod.Globals.Add(VersionGlob(modKey, o.BuildVersion));
            (quest.Aliases ??= new ExtendedList<SF.AQuestAlias>()).Add(new SF.QuestReferenceAlias
            {
                ID = PlayerAlias, Name = PlayerAliasName, ForcedReference = new FormLinkNullable<SF.IPlacedGetter>(new FormKey(SfEsm, PlayerRefId)),
            });
            var version = new SF.ScriptEntry { Name = VersionScript, Flags = SF.ScriptEntry.Flag.Local };
            version.Properties.Add(Obj("BuildVersion", new FormKey(modKey, VersionGlobId)));
            var bound = new SF.QuestFragmentAlias
            {
                Property = new SF.ScriptObjectProperty { Name = "", Flags = SF.ScriptProperty.Flag.Edited, Object = new FormLink<SF.IStarfieldMajorRecordGetter>(quest.FormKey), Alias = (short)PlayerAlias, Unused = 0 },
                Version = 6, ObjectFormat = 2,
            };
            bound.Scripts.Add(version);
            quest.VirtualMachineAdapter.Aliases.Add(bound);
        }
        mod.Quests.Add(quest);
        // our own start: Starfield's StartupQuest_DO, its id and EditorID kept, names our quest
        var startupOver = (SF.DefaultObject)startup.DeepCopy();
        startupOver.Object.SetTo(quest.FormKey);
        mod.DefaultObjects.Add(startupOver);

        if (o.MQ101Debug is { } dbg)
        {
            var over = (SF.Global)debugGlob.DeepCopy();
            over.Data = dbg;
            mod.Globals.Add(over);
        }
        mod.ModHeader.Stats.NextFormID = VaultAmmoRefId + 1;
        Directory.CreateDirectory(outDir);
        var path = Path.Combine(outDir, o.Plugin);
        WritePlugin(mod, path);
        Console.WriteLine($"wrote {path} ({new FileInfo(path).Length:N0} bytes): QUST {QuestEdid} {quest.FormKey} \"{quest.Name}\", " +
                          $"the startup quest: DFOB {StartupEdid} {startup.FormKey} -> {quest.FormKey} (was {OpeningEdid}); " +
                          $"hold [{string.Join(", ", o.Hold)}]; vault anchor FO4Port.esm:{places.VaultAnchor:X6} {places.AnchorMode} at {Show(places.AnchorPos)}, " +
                          $"cog door {(places.CogDoor == 0 ? "none" : $"{places.CogDoor:X6} ({places.CogDoorBase})")}, exit anchor " +
                          $"FO4TerrainCore.esm:{places.ExitAnchor:X6} at {Show(places.ExitPos)}; looks {(o.Looks ? $"on (race menu mode {o.RaceMenuMode})" : "off")}" +
                          (o.MQ101Debug is { } d2 ? $"; GLOB MQ101Debug = {F(d2)}" : "; GLOB MQ101Debug not overridden") +
                          (o.DebugAfterHold != 0 ? $"; the quest writes MQ101Debug = {o.DebugAfterHold} after the hold-off" : "; the quest never writes MQ101Debug") +
                          (o.Special ? $"; SPECIAL on: terminal {TerminalText(places)}, {specialKeys.Count} {CoreValuesPlugin} AVIF links" : "; SPECIAL off") +
                          (o.Version ? $"; version check on: GLOB {VersionGlobEdid} = {F(o.BuildVersion)}, alias {PlayerAlias} {PlayerAliasName} -> Starfield.esm:{PlayerRefId:X6}" : "; version check off") +
                          $"; inventory reset {InventoryText(o, places)}; {O2Text(o)}");
        return 0;
    }

    /// Starfield.esm's DefaultObject StartupQuest_DO, which must name the opening (MQ101) as vanilla does: a Starfield.esm
    /// whose start is another quest (an update, or a start already replaced) is not the start this plugin was written to
    /// replace.
    public static SF.IDefaultObjectGetter Startup(SF.IStarfieldModGetter sf, SF.IQuestGetter opening)
    {
        var dobj = sf.DefaultObjects.FirstOrDefault(d => d.EditorID == StartupEdid) ?? throw new Refusal($"Starfield.esm has no DFOB {StartupEdid}");
        if (dobj.FormKey != new FormKey(SfEsm, StartupId))
            throw new Refusal($"Starfield.esm's {StartupEdid} is {dobj.FormKey}, not Starfield.esm:{StartupId:X6}, the record the deployment gate's start check knows");
        if (dobj.Object.FormKey != opening.FormKey)
            throw new Refusal($"Starfield.esm's {StartupEdid} {dobj.FormKey} names {dobj.Object.FormKey}, not {OpeningEdid} {opening.FormKey}: not the start this plugin replaces");
        return dobj;
    }

    static string O2Text(Options o) => o.O2 ? $"O2 capacity {O2CapacityId:X6} +{F(O2CapacityAmount)} after the reset" : "O2 capacity untouched";
    static string InventoryText(Options o, Places p) => !o.ClearInventory ? "off" :
        $"on (quest items unverified), vault suit {(o.VaultSuit is null ? "none" : $"{o.VaultSuit} FO4Port.esm:{p.VaultSuit:X6}")}";

    /// The build's version number as our own constant GLOB (see the constants' note: Constant so the save does not
    /// carry the value; unverified until the PC run).
    public static SF.Global VersionGlob(ModKey modKey, float version) => new(new FormKey(modKey, VersionGlobId), SF.StarfieldRelease.Starfield)
    {
        EditorID = VersionGlobEdid, Data = version, MajorFlags = SF.Global.MajorFlag.Constant,
    };

    static string TerminalText(Places p) => p.TerminalSrc == 0 ? "none" :
        $"FO4 {p.TerminalSrc:X8} at {Show(p.TerminalPos)} -> {(p.Terminal == 0 ? "not in the port (the prompt watches the spot)" : $"FO4Port.esm:{p.Terminal:X6}")}";

    /// The allocation's text: one %.0f token per value, in Message.Show's argument order (the stats, then the points left).
    public static readonly string SpecialDescription = string.Join("  ", SpecialNames.Select(n => n[0] + " %.0f")) + "   Points left: %.0f";

    // ---------------------------------------------------------------- check

    public static int Check(string pluginPath, string sfPath, string portPath, string portIds, string corePath, string pointsPath, Options o)
    {
        var problems = new List<string>();
        void Need(bool ok, string what) { if (!ok) problems.Add(what); }
        var (coreKey, coreIds) = LoadCoreValues(o.CoreValuesJson);
        var specialKeys = SpecialNames.Select(n => new FormKey(coreKey, RequireCoreId(coreIds, SpecialAvifPrefix + n))).ToList();
        var testModeKey = new FormKey(coreKey, RequireCoreId(coreIds, TestModeGlobEdid));
        var startCardOpenKey = new FormKey(coreKey, RequireCoreId(coreIds, StartCardOpenGlobEdid));
        var gameModeKey = new FormKey(coreKey, RequireCoreId(coreIds, GameModeGlobEdid));
        var survStartKey = new FormKey(coreKey, RequireCoreId(coreIds, SurvivalStartGlobEdid));
        var survLockedKey = new FormKey(coreKey, RequireCoreId(coreIds, SurvivalLockedGlobEdid));
        var startDiffKey = new FormKey(coreKey, RequireCoreId(coreIds, StartDifficultyGlobEdid));
        var wfFactionKey = new FormKey(coreKey, RequireCoreId(coreIds, WarfareFactionGlobEdid));
        var wfStartIdxKey = new FormKey(coreKey, RequireCoreId(coreIds, WarfareStartIndexGlobEdid));
        var choiceDoneKey = new FormKey(coreKey, RequireCoreId(coreIds, StartChoiceDoneGlobEdid));
        var startNeutralSpotKey = new FormKey(coreKey, RequireCoreId(coreIds, StartNeutralSpotGlobEdid));
        var storyLineKey = new FormKey(coreKey, RequireCoreId(coreIds, StoryLineGlobEdid));
        var startPlaceRowKey = new FormKey(coreKey, RequireCoreId(coreIds, StartPlaceRowGlobEdid));
        var pipboyAcquiredKey = new FormKey(coreKey, RequireCoreId(coreIds, PipboyAcquiredGlobEdid));
        var h00SkipLoadingHookKey = new FormKey(coreKey, RequireCoreId(coreIds, H00SkipLoadingHookGlobEdid));
        var h00ClearChargenKey = new FormKey(coreKey, RequireCoreId(coreIds, H00ClearChargenGlobEdid));
        var h00SkipArrivalDiscoveryKey = new FormKey(coreKey, RequireCoreId(coreIds, H00SkipArrivalDiscoveryGlobEdid));
        var h00SkipMapSetupKey = new FormKey(coreKey, RequireCoreId(coreIds, H00SkipMapSetupGlobEdid));
        var h00SkipRouteLootKey = new FormKey(coreKey, RequireCoreId(coreIds, H00SkipRouteLootGlobEdid));
        var h00SkipMissionActorsKey = new FormKey(coreKey, RequireCoreId(coreIds, H00SkipMissionActorsGlobEdid));
        var h00SkipLandingQuestsKey = new FormKey(coreKey, RequireCoreId(coreIds, H00SkipLandingQuestsGlobEdid));
        var h00SkipSurfaceSetPosKey = new FormKey(coreKey, RequireCoreId(coreIds, H00SkipSurfaceSetPosGlobEdid));
        var pts = JsonDocument.Parse(File.ReadAllText(pointsPath)).RootElement;
        var places = Resolve(portPath, portIds, corePath, o.ExitAnchor, Terminals(pts), o.VaultSuit, o.RequirePersistentAnchor, o.AnimatedExitLift);
        using var sf = SF.StarfieldMod.CreateFromBinaryOverlay(sfPath, SF.StarfieldRelease.Starfield);
        var wf = LoadWarfareStarts(o.WarfareStartsJson, sf, corePath);
        var sp = LoadStartPlaces(o.StartPlacesJson, pts, places, wf, portPath, corePath);
        uint vaultPistolId = LoadVaultPistolId(o.RouteLootJson, sf);
        var routeLootRefIds = LoadRouteLootRefIds(o.RouteLootJson, corePath, places.ExitPos);
        var vaultPistolKey = new FormKey(SfEsm, vaultPistolId);
        using var plug = SF.StarfieldMod.CreateFromBinaryOverlay(pluginPath, SF.StarfieldRelease.Starfield, Full(SfEsm, PortEsm, CoreValuesEsm));
        var key = plug.ModKey;
        var masters = plug.ModHeader.MasterReferences.Select(x => x.Master.FileName.String).ToList();
        Console.WriteLine($"{key}: header {plug.ModHeader.Flags}, masters [{string.Join(", ", masters)}], {plug.Quests.Count} QUST, " +
                          $"{plug.Messages.Count} MESG, {plug.Globals.Count} GLOB, {plug.Armors.Count} ARMO, {plug.Activators.Count} ACTI, " +
                          $"{plug.Cells.Records.Count} CELL, {plug.ActorValueInformation.Count} AVIF, " +
                          $"{plug.DefaultObjects.Count} DFOB, {plug.Quests.Sum(q => q.Aliases?.Count ?? 0)} alias(es)");
        Need(plug.ModHeader.Flags.HasFlag(SF.StarfieldModHeader.HeaderFlag.Master), "not flagged as a master");
        Need(masters.SequenceEqual(new[] { "Starfield.esm", PortPlugin, CoreValuesPlugin }), $"masters [{string.Join(", ", masters)}] are not [Starfield.esm, {PortPlugin}, {CoreValuesPlugin}]");
        Need(plug.Npcs.Count == 0 && plug.Worldspaces.Count == 0, "the plugin carries NPC_ or WRLD records");
        Need(plug.ActorValueInformation.Count == 0, "the plugin carries AVIF records (S.P.E.C.I.A.L. AVIFs live in FO4SFCoreValues.esm)");
        var reservedSet = ReservedFormIds.ToHashSet();
        foreach (var rec in plug.EnumerateMajorRecords().Where(r => r.FormKey.ModKey == key && reservedSet.Contains(r.FormKey.ID)))
            Need(false, $"reserved FormID 0x{rec.FormKey.ID:X} carries record {rec.EditorID ?? rec.FormKey.ToString()}");

        var pipboyWrist = plug.Armors.FirstOrDefault(a => a.FormKey == new FormKey(key, PipboyWristArmorId));
        Need(plug.Armors.Count == 1 && pipboyWrist is { EditorID: PipboyWristArmorEdid } && (pipboyWrist.MajorRecordFlagsRaw & 0x4) == 0,
             $"ARMO 0x{PipboyWristArmorId:X} is not playable {PipboyWristArmorEdid}");
        var pipboyActi = plug.Activators.FirstOrDefault(a => a.FormKey == new FormKey(key, PipboyCorpseActiId));
        var gearConsoleActi = plug.Activators.FirstOrDefault(a => a.FormKey == new FormKey(key, GearDoorConsoleActiId));
        Need(plug.Activators.Count == 2 && pipboyActi is { EditorID: PipboyCorpseActiEdid } &&
             gearConsoleActi is { EditorID: GearDoorConsoleActiEdid } &&
             gearConsoleActi.Name?.String == "Vault Door Controls" &&
             gearConsoleActi.ActivateTextOverride?.String == "Activate",
             $"ACTIs are not {PipboyCorpseActiEdid} (0x{PipboyCorpseActiId:X}) and named {GearDoorConsoleActiEdid} (0x{GearDoorConsoleActiId:X})");

        var allPlugCells = plug.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(sb => sb.Cells).ToList();
        var cellOver = allPlugCells.FirstOrDefault(c => c.FormKey == new FormKey(PortEsm, places.PortCellId));
        var startRoomCell = allPlugCells.FirstOrDefault(c => c.FormKey == new FormKey(key, StartRoomCellId));
        var pipboyRef = cellOver?.Persistent.OfType<SF.IPlacedObjectGetter>().FirstOrDefault(r => r.FormKey == new FormKey(key, PipboyCorpseRefId));
        var gearConsoleRef = cellOver?.Persistent.OfType<SF.IPlacedObjectGetter>().FirstOrDefault(r => r.FormKey == new FormKey(key, GearDoorConsoleRefId));
        var startRoomMarkerRef = startRoomCell?.Persistent.OfType<SF.IPlacedObjectGetter>().FirstOrDefault(r => r.FormKey == new FormKey(key, StartRoomMarkerRefId));
        var (wantPbPos, _) = PipboyPlacement(pts);
        var conCoords = Floats(pts.GetProperty("console").GetProperty("pos"));
        var wantConPos = new P3Float(conCoords[0], conCoords[1], conCoords[2]);
        bool hasVaultPistolAndAmmo = sf.Weapons.Any(w => w.FormKey == new FormKey(SfEsm, SfVaultPistolId)) &&
                                     sf.Ammunitions.Any(a => a.FormKey == new FormKey(SfEsm, SfVaultAmmoId));
        int wantVaultTempCount = hasVaultPistolAndAmmo ? 2 : 0;
        Need(allPlugCells.Count == 2 &&
             cellOver is not null && cellOver.FormKey == new FormKey(PortEsm, places.PortCellId) && cellOver.EditorID == VaultCell &&
             cellOver.Temporary.Count == wantVaultTempCount && cellOver.Persistent.Count == 2 &&
             pipboyRef is { EditorID: PipboyCorpseRefEdid } && IsPersistent(pipboyRef) &&
             pipboyRef.Base.FormKey == new FormKey(key, PipboyCorpseActiId) &&
             MathF.Abs(pipboyRef.Position.X - wantPbPos.X) <= 1e-3f &&
             MathF.Abs(pipboyRef.Position.Y - wantPbPos.Y) <= 1e-3f &&
             MathF.Abs(pipboyRef.Position.Z - wantPbPos.Z) <= 1e-3f &&
             gearConsoleRef is { EditorID: GearDoorConsoleRefEdid } && IsPersistent(gearConsoleRef) &&
             gearConsoleRef.Base.FormKey == new FormKey(key, GearDoorConsoleActiId) &&
             MathF.Abs(gearConsoleRef.Position.X - wantConPos.X) <= 1e-3f &&
             MathF.Abs(gearConsoleRef.Position.Y - wantConPos.Y) <= 1e-3f &&
             MathF.Abs(gearConsoleRef.Position.Z - wantConPos.Z) <= 1e-3f,
             $"CELL override is not {VaultCell} carrying persistent {PipboyCorpseRefEdid} (0x{PipboyCorpseRefId:X}) and {GearDoorConsoleRefEdid} (0x{GearDoorConsoleRefId:X})");
        if (hasVaultPistolAndAmmo)
        {
            var pistolRef = cellOver?.Temporary.OfType<SF.IPlacedObjectGetter>().FirstOrDefault(r => r.FormKey == new FormKey(key, VaultPistolRefId));
            var ammoRef = cellOver?.Temporary.OfType<SF.IPlacedObjectGetter>().FirstOrDefault(r => r.FormKey == new FormKey(key, VaultAmmoRefId));
            Need(pistolRef is { EditorID: VaultPistolRefEdid } && !IsPersistent(pistolRef) &&
                 pistolRef.Base.FormKey == new FormKey(SfEsm, SfVaultPistolId) &&
                 MathF.Abs(pistolRef.Position.X - (-57.0338f)) <= 1e-3f &&
                 MathF.Abs(pistolRef.Position.Y - 30.006f) <= 1e-3f &&
                 MathF.Abs(pistolRef.Position.Z - 1.29f) <= 1e-3f,
                 $"CELL override lacks temporary {VaultPistolRefEdid} (0x{VaultPistolRefId:X}) -> Starfield.esm:{SfVaultPistolId:X6}");
            Need(ammoRef is { EditorID: VaultAmmoRefEdid } && !IsPersistent(ammoRef) &&
                 ammoRef.Base.FormKey == new FormKey(SfEsm, SfVaultAmmoId) &&
                 ammoRef.Count == VaultAmmoCount &&
                 MathF.Abs(ammoRef.Position.X - (-57.0522f)) <= 1e-3f &&
                 MathF.Abs(ammoRef.Position.Y - 30.3703f) <= 1e-3f &&
                 MathF.Abs(ammoRef.Position.Z - 0.696f) <= 1e-3f,
                 $"CELL override lacks temporary {VaultAmmoRefEdid} (0x{VaultAmmoRefId:X}) -> Starfield.esm:{SfVaultAmmoId:X6} count {VaultAmmoCount}");
        }
        Need(startRoomCell is { EditorID: StartRoomCellEdid } && (startRoomCell.Flags & SF.Cell.Flag.IsInteriorCell) != 0 &&
             startRoomCell.Temporary.Count == 0 && startRoomCell.Persistent.Count == 1 &&
             startRoomMarkerRef is { EditorID: StartRoomMarkerRefEdid } && IsPersistent(startRoomMarkerRef) &&
             startRoomMarkerRef.Base.FormKey == new FormKey(SfEsm, CocMarkerId),
             $"CELL 0x{StartRoomCellId:X} is not interior {StartRoomCellEdid} carrying persistent {StartRoomMarkerRefEdid} (0x{StartRoomMarkerRefId:X})");
        Console.WriteLine($"  gear door console ACTI {GearDoorConsoleActiEdid} {gearConsoleActi?.FormKey} -> REFR {GearDoorConsoleRefEdid} {gearConsoleRef?.FormKey} persistent at {Show(wantConPos)} (port ref FO4Port.esm:{places.Console:X6})");

        foreach (var anyMsg in plug.Messages)
            Need(anyMsg.MenuButtons.Count <= MaxMessageButtons, $"MESG {anyMsg.EditorID} ({anyMsg.FormKey}) has {anyMsg.MenuButtons.Count} buttons (> {MaxMessageButtons})");

        var msg = plug.Messages.FirstOrDefault(m => m.FormKey == new FormKey(key, MessageId));
        Need(msg is { EditorID: MessageEdid } && msg.Flags.HasFlag(SF.Message.Flag.MessageBox) &&
             msg.MenuButtons.Select(b => b.Text?.String).SequenceEqual(ExitButtons), $"MESG 0x{MessageId:X} is not {MessageEdid} with buttons [{string.Join(", ", ExitButtons)}]");
        var exitNeedSpecialMsg = plug.Messages.FirstOrDefault(m => m.FormKey == new FormKey(key, ExitNeedSpecialMsgId));
        Need(exitNeedSpecialMsg is { EditorID: ExitNeedSpecialMsgEdid } && exitNeedSpecialMsg.Flags.HasFlag(SF.Message.Flag.MessageBox) &&
             exitNeedSpecialMsg.MenuButtons.Select(b => b.Text?.String).SequenceEqual(ExitNeedSpecialButtons), $"MESG 0x{ExitNeedSpecialMsgId:X} is not {ExitNeedSpecialMsgEdid} with buttons [{string.Join(", ", ExitNeedSpecialButtons)}]");
        var exitFallbackMsg = plug.Messages.FirstOrDefault(m => m.FormKey == new FormKey(key, ExitFallbackMsgId));
        Need(exitFallbackMsg is { EditorID: ExitFallbackMsgEdid } && exitFallbackMsg.Flags.HasFlag(SF.Message.Flag.MessageBox) &&
             exitFallbackMsg.MenuButtons.Select(b => b.Text?.String).SequenceEqual(ExitFallbackButtons), $"MESG 0x{ExitFallbackMsgId:X} is not {ExitFallbackMsgEdid} with buttons [{string.Join(", ", ExitFallbackButtons)}]");
        var returnMsg = plug.Messages.FirstOrDefault(m => m.FormKey == new FormKey(key, ReturnMsgId));
        Need(returnMsg is { EditorID: ReturnMsgEdid } && returnMsg.Flags.HasFlag(SF.Message.Flag.MessageBox) &&
             returnMsg.MenuButtons.Select(b => b.Text?.String).SequenceEqual(ReturnButtons), $"MESG 0x{ReturnMsgId:X} is not {ReturnMsgEdid} with buttons [{string.Join(", ", ReturnButtons)}]");
        var modePickMsg = plug.Messages.FirstOrDefault(m => m.FormKey == new FormKey(key, ModePickMsgId));
        Need(modePickMsg is { EditorID: ModePickMsgEdid } && modePickMsg.Flags.HasFlag(SF.Message.Flag.MessageBox) &&
             modePickMsg.MenuButtons.Select(b => b.Text?.String).SequenceEqual(ModeButtons), $"MESG 0x{ModePickMsgId:X} is not {ModePickMsgEdid}");
        var storyLineMsg = plug.Messages.FirstOrDefault(m => m.FormKey == new FormKey(key, StoryLineMsgId));
        Need(storyLineMsg is { EditorID: StoryLineMsgEdid } && storyLineMsg.Flags.HasFlag(SF.Message.Flag.MessageBox) &&
             storyLineMsg.MenuButtons.Select(b => b.Text?.String).SequenceEqual(sp.StoryLabels), $"MESG 0x{StoryLineMsgId:X} is not {StoryLineMsgEdid}");
        var survPickMsg = plug.Messages.FirstOrDefault(m => m.FormKey == new FormKey(key, SurvivalPickMsgId));
        Need(survPickMsg is { EditorID: SurvivalPickMsgEdid } && survPickMsg.Flags.HasFlag(SF.Message.Flag.MessageBox) &&
             survPickMsg.MenuButtons.Select(b => b.Text?.String).SequenceEqual(SurvivalButtons), $"MESG 0x{SurvivalPickMsgId:X} is not {SurvivalPickMsgEdid}");
        var wfDiffMsg = plug.Messages.FirstOrDefault(m => m.FormKey == new FormKey(key, WarfareDiffMsgId));
        Need(wfDiffMsg is { EditorID: WarfareDiffMsgEdid } && wfDiffMsg.Flags.HasFlag(SF.Message.Flag.MessageBox) &&
             wfDiffMsg.MenuButtons.Select(b => b.Text?.String).SequenceEqual(WarfareDiffButtons), $"MESG 0x{WarfareDiffMsgId:X} is not {WarfareDiffMsgEdid}");
        var wfGroupMsg = plug.Messages.FirstOrDefault(m => m.FormKey == new FormKey(key, WarfareGroupMsgId));
        Need(wfGroupMsg is { EditorID: WarfareGroupMsgEdid } && wfGroupMsg.Flags.HasFlag(SF.Message.Flag.MessageBox) &&
             wfGroupMsg.MenuButtons.Select(b => b.Text?.String).SequenceEqual(wf.FactionButtons), $"MESG 0x{WarfareGroupMsgId:X} is not {WarfareGroupMsgEdid}");
        var wfSpotMsg = plug.Messages.FirstOrDefault(m => m.FormKey == new FormKey(key, WarfareSpotMsgId));
        Need(wfSpotMsg is { EditorID: WarfareSpotMsgEdid } && wfSpotMsg.Flags.HasFlag(SF.Message.Flag.MessageBox) &&
             wfSpotMsg.MenuButtons.Select(b => b.Text?.String).SequenceEqual(wf.SpotButtons), $"MESG 0x{WarfareSpotMsgId:X} is not {WarfareSpotMsgEdid}");
        var noPipboyMsg = plug.Messages.FirstOrDefault(m => m.FormKey == new FormKey(key, NoPipboyMsgId));
        Need(noPipboyMsg is { EditorID: NoPipboyMsgEdid } && noPipboyMsg.Flags.HasFlag(SF.Message.Flag.MessageBox) &&
             noPipboyMsg.MenuButtons.Select(b => b.Text?.String).SequenceEqual(NoPipboyButtons), $"MESG 0x{NoPipboyMsgId:X} is not {NoPipboyMsgEdid}");
        var start = plug.Messages.FirstOrDefault(m => m.FormKey == new FormKey(key, StartMessageId));
        Need(start is { EditorID: StartMessageEdid } && start.Name?.String == "Character Appearance" &&
             start.Flags.HasFlag(SF.Message.Flag.MessageBox) &&
             start.MenuButtons.Select(b => b.Text?.String).SequenceEqual(StartButtons),
             $"MESG 0x{StartMessageId:X} is not {StartMessageEdid} titled \"Character Appearance\" with buttons [{string.Join(", ", StartButtons)}]");
        var terminalMsg = plug.Messages.FirstOrDefault(m => m.FormKey == new FormKey(key, TerminalMessageId));
        var specialMsg = plug.Messages.FirstOrDefault(m => m.FormKey == new FormKey(key, SpecialMessageId));
        var specialMsgPage2 = plug.Messages.FirstOrDefault(m => m.FormKey == new FormKey(key, SpecialMessagePage2Id));
        if (o.Special)
        {
            Need(terminalMsg is { EditorID: TerminalMessageEdid } && terminalMsg.Flags.HasFlag(SF.Message.Flag.MessageBox) && terminalMsg.MenuButtons.Count == 2 &&
                 terminalMsg.MenuButtons.All(b => !string.IsNullOrWhiteSpace(b.Text?.String)), $"MESG 0x{TerminalMessageId:X} is not {TerminalMessageEdid}, a message box with two buttons");
            Need(specialMsg is { EditorID: SpecialMessageEdid } && specialMsg.Flags.HasFlag(SF.Message.Flag.MessageBox) &&
                 specialMsg.MenuButtons.Select(b => b.Text?.String).SequenceEqual(SpecialPage1Buttons) && specialMsg.Description?.String == SpecialDescription,
                 $"MESG 0x{SpecialMessageId:X} is not {SpecialMessageEdid}, a <=7-button message box with [{string.Join(", ", SpecialPage1Buttons)}] and the allocation text");
            Need(specialMsgPage2 is { EditorID: SpecialMessagePage2Edid } && specialMsgPage2.Flags.HasFlag(SF.Message.Flag.MessageBox) &&
                 specialMsgPage2.MenuButtons.Select(b => b.Text?.String).SequenceEqual(SpecialPage2Buttons) && specialMsgPage2.Description?.String == SpecialDescription,
                 $"MESG 0x{SpecialMessagePage2Id:X} is not {SpecialMessagePage2Edid}, a <=7-button message box with [{string.Join(", ", SpecialPage2Buttons)}] and the allocation text");
            Need(plug.Messages.Count == 15, $"{plug.Messages.Count} MESG, expected 15");
            Console.WriteLine($"  SPECIAL links [{string.Join(", ", specialKeys)}]; terminal {TerminalText(places)}");
        }
        else
        {
            Need(plug.Messages.Count == 12, $"{plug.Messages.Count} MESG, expected 12 in a --no-special build");
        }

        // the GLOBs: Starfield's MQ101Debug overridden (or not), and our own version GLOB (or not); FO4SF_PipboyAcquired lives in FO4SFCoreValues.esm:000865
        var overrides = plug.Globals.Where(g => g.FormKey.ModKey != key).ToList();
        var own = plug.Globals.Where(g => g.FormKey.ModKey == key).ToList();
        if (o.MQ101Debug is { } dbg)
        {
            var src = sf.Globals.FirstOrDefault(g => g.EditorID == DebugGlobEdid);
            Need(overrides.Count == 1 && src is not null && overrides[0].FormKey == src.FormKey && overrides[0].Data == dbg,
                 $"GLOB MQ101Debug is not overridden to {F(dbg)}");
        }
        else Need(overrides.Count == 0, "a build without --mq101debug overrides a GLOB");
        var ver = own.FirstOrDefault(g => g.FormKey == new FormKey(key, VersionGlobId));
        if (o.Version)
        {
            Need(own.Count == 1 && ver is { EditorID: VersionGlobEdid } && ver.Data == o.BuildVersion && ver.MajorFlags.HasFlag(SF.Global.MajorFlag.Constant),
                 $"GLOB 0x{VersionGlobId:X} is not {VersionGlobEdid} = {F(o.BuildVersion)}, constant");
            Console.WriteLine($"  GLOB {VersionGlobEdid} = {(ver?.Data is { } vd ? F(vd) : "missing")} flags {ver?.MajorFlags}");
        }
        else Need(own.Count == 0, "a --no-version build carries a local GLOB");

        // our own start: exactly one DFOB, Starfield's StartupQuest_DO overridden (same id and EditorID) to name our quest
        var opening = sf.Quests.FirstOrDefault(x => x.EditorID == OpeningEdid);
        SF.IDefaultObjectGetter? vanilla = null;
        try { vanilla = opening is null ? null : Startup(sf, opening); }
        catch (Refusal e) { problems.Add(e.Message); }
        var dobjs = plug.DefaultObjects.ToList();
        Need(dobjs.Count == 1 && vanilla is not null && dobjs[0].FormKey == vanilla.FormKey && dobjs[0].EditorID == StartupEdid &&
             dobjs[0].Object.FormKey == new FormKey(key, QuestId),
             $"the plugin's DFOB are not one override of Starfield's {StartupEdid} naming QUST 0x{QuestId:X} (our own start)");
        Console.WriteLine($"  start: {string.Join("; ", dobjs.Select(d => $"DFOB {d.EditorID} {d.FormKey} -> {d.Object.FormKey}"))}" +
                          (vanilla is null ? "" : $" (vanilla: {vanilla.Object.FormKey})"));

        // our quest alone: an override of one of Starfield's quests (MQ101 above all) would change the start it replaces
        Need(plug.Quests.Count == 1, $"the plugin carries {plug.Quests.Count} QUST, not {QuestEdid} alone");
        var q = plug.Quests.FirstOrDefault(x => x.FormKey == new FormKey(key, QuestId));
        if (q is null) problems.Add("no QUST 0x800");
        else
        {
            Console.WriteLine($"  QUST {q.EditorID} \"{q.Name?.String}\" flags {q.Data?.Flags} stages [{string.Join(",", q.Stages.Select(s => s.Index))}] " +
                              $"objectives [{string.Join("; ", q.Objectives.Select(x => $"{x.Index} \"{x.DisplayText?.String}\""))}]");
            // the startup quest is started by the engine on a New Game only: start game enabled would start it on every
            // save that gains the plugin, too
            Need(q.EditorID == QuestEdid && q.Data is not null && !q.Data.Flags.HasFlag(SF.Quest.Flag.StartGameEnabled) && q.Data.Flags.HasFlag(SF.Quest.Flag.RunOnce),
                 "the quest is not FO4SF_NewGame, run once and NOT start game enabled (the startup quest)");
            Need(q.QuestType.FormKey == new FormKey(SfEsm, QuestTypeSideId), $"the quest's QuestType is not {QuestTypeSideEdid}");
            Need(q.Stages.Select(s => s.Index).SequenceEqual(Stages), "stages differ from the script's");
            Need(q.Stages.FirstOrDefault(s => s.Index == 200)?.LogEntries.Any(l => l.Flags?.HasFlag(SF.QuestLogEntry.Flag.CompleteQuest) == true) == true, "stage 200 does not complete the quest");
            Need(q.Stages.FirstOrDefault(s => s.Index == 210)?.LogEntries.Any(l => l.Flags?.HasFlag(SF.QuestLogEntry.Flag.CompleteQuest) == true) == true, "stage 210 does not complete the quest");
            Need(q.Objectives.Count == 1 && q.Objectives[0].Index == Objective && q.Objectives[0].DisplayText?.String == ObjectiveText, $"objective {Objective} is not \"{ObjectiveText}\"");
            Need(q.DialogTopics.Count == 0, "the quest carries dialogue");
            // the player alias and its script (the version check): alias 0 forced to PlayerRef, bound in the VMAD's
            // alias fragment to one script with the version GLOB as BuildVersion
            var aliases = (q.Aliases ?? new List<SF.IAQuestAliasGetter>()).OfType<SF.IQuestReferenceAliasGetter>().ToList();
            var bound = q.VirtualMachineAdapter?.Aliases.ToList() ?? new();
            if (o.Version)
            {
                Need((q.Aliases?.Count ?? 0) == 1 && aliases.Count == 1 && aliases[0].ID == PlayerAlias && aliases[0].Name == PlayerAliasName &&
                     aliases[0].ForcedReference.FormKey == new FormKey(SfEsm, PlayerRefId), $"alias {PlayerAlias} is not {PlayerAliasName}, forced to Starfield.esm:{PlayerRefId:X6}");
                var vs = bound.Count == 1 ? bound[0].Scripts.FirstOrDefault(s => s.Name == VersionScript) : null;
                Need(bound.Count == 1 && bound[0].Property.Object.FormKey == q.FormKey && bound[0].Property.Alias == PlayerAlias && bound[0].Scripts.Count == 1 && vs is not null,
                     $"the VMAD binds {bound.Count} alias fragment(s), not one on alias {PlayerAlias} with {VersionScript} alone");
                if (vs is not null)
                {
                    var props = vs.Properties.ToDictionary(p => p.Name);
                    Console.WriteLine($"  alias {aliases.FirstOrDefault()?.ID} {aliases.FirstOrDefault()?.Name} -> {aliases.FirstOrDefault()?.ForcedReference.FormKey}; script {vs.Name}: {props.Count} properties");
                    Need(props.Count == 1 && props.TryGetValue("BuildVersion", out var bp) && bp is SF.IScriptObjectPropertyGetter bo && bo.Object.FormKey == ver?.FormKey,
                         $"{VersionScript}'s one property is not BuildVersion -> {VersionGlobEdid}");
                }
            }
            else Need((q.Aliases?.Count ?? 0) == 0 && bound.Count == 0, "a --no-version build carries an alias or an alias script");
            var scripts = q.VirtualMachineAdapter?.Scripts.Select(s => s.Name).ToList() ?? new();
            var wantScripts = new List<string> { ScriptName };
            if (o.Looks) wantScripts.Add(LooksScript);
            if (o.Special) wantScripts.Add(SpecialScript);
            Need(scripts.SequenceEqual(wantScripts), $"scripts [{string.Join(", ", scripts)}] are not [{string.Join(", ", wantScripts)}]");
            var s = q.VirtualMachineAdapter?.Scripts.FirstOrDefault(x => x.Name == ScriptName);
            if (s is not null)
            {
                var props = s.Properties.ToDictionary(p => p.Name);
                Console.WriteLine($"  script {s.Name}: {props.Count} properties");
                Need(props.TryGetValue("GameDaysPassed", out var gp) && gp is SF.IScriptObjectPropertyGetter go && go.Object.FormKey == new FormKey(SfEsm, GameDaysPassedId),
                     "property GameDaysPassed");
                Need(props.TryGetValue("Opening", out var op) && op is SF.IScriptObjectPropertyGetter oq &&
                     oq.Object.FormKey == sf.Quests.FirstOrDefault(x => x.EditorID == OpeningEdid)?.FormKey, $"property Opening is not {OpeningEdid}");
                Need(props.TryGetValue("DebugGlobal", out var dg) && dg is SF.IScriptObjectPropertyGetter dgo &&
                     dgo.Object.FormKey == sf.Globals.FirstOrDefault(x => x.EditorID == DebugGlobEdid)?.FormKey, $"property DebugGlobal is not {DebugGlobEdid}");
                Need(props.TryGetValue("ExitMessage", out var mp) && mp is SF.IScriptObjectPropertyGetter mo && mo.Object.FormKey == msg?.FormKey, "property ExitMessage");
                Need(props.TryGetValue("ExitNeedAttrMsg", out var ensmp) && ensmp is SF.IScriptObjectPropertyGetter ensmo && ensmo.Object.FormKey == exitNeedSpecialMsg?.FormKey, "property ExitNeedAttrMsg");
                Need(props.TryGetValue("ExitFallbackMessage", out var efmp) && efmp is SF.IScriptObjectPropertyGetter efmo && efmo.Object.FormKey == exitFallbackMsg?.FormKey, "property ExitFallbackMessage");
                Need(props.TryGetValue("ReturnMessage", out var rmp) && rmp is SF.IScriptObjectPropertyGetter rmo && rmo.Object.FormKey == returnMsg?.FormKey, "property ReturnMessage");
                Need(props.TryGetValue("ModePickMsg", out var mpm) && mpm is SF.IScriptObjectPropertyGetter mpmo && mpmo.Object.FormKey == modePickMsg?.FormKey, "property ModePickMsg");
                Need(props.TryGetValue("StoryLineMsg", out var slmp) && slmp is SF.IScriptObjectPropertyGetter slmo && slmo.Object.FormKey == storyLineMsg?.FormKey, "property StoryLineMsg");
                Need(props.TryGetValue("SurvivalPickMsg", out var spm) && spm is SF.IScriptObjectPropertyGetter spmo && spmo.Object.FormKey == survPickMsg?.FormKey, "property SurvivalPickMsg");
                Need(props.TryGetValue("WarfareDiffMsg", out var wdm) && wdm is SF.IScriptObjectPropertyGetter wdmo && wdmo.Object.FormKey == wfDiffMsg?.FormKey, "property WarfareDiffMsg");
                Need(props.TryGetValue("WarfareGroupMsg", out var wgm) && wgm is SF.IScriptObjectPropertyGetter wgmo && wgmo.Object.FormKey == wfGroupMsg?.FormKey, "property WarfareGroupMsg");
                Need(props.TryGetValue("WarfareSpotMsg", out var wsm) && wsm is SF.IScriptObjectPropertyGetter wsmo && wsmo.Object.FormKey == wfSpotMsg?.FormKey, "property WarfareSpotMsg");
                Need(props.TryGetValue("StartPickMsg", out var stpm) && stpm is SF.IScriptObjectPropertyGetter stpmo && stpmo.Object.FormKey == start?.FormKey, "property StartPickMsg");
                Need(props.TryGetValue("NoPipboyMsg", out var npm) && npm is SF.IScriptObjectPropertyGetter npmo && npmo.Object.FormKey == noPipboyMsg?.FormKey, "property NoPipboyMsg");
                Need(props.TryGetValue("O2Capacity", out var cp) && cp is SF.IScriptObjectPropertyGetter co && co.Object.FormKey == new FormKey(SfEsm, O2CapacityId),
                     $"property O2Capacity is not Starfield.esm:{O2CapacityId:X6}");
                Need(props.TryGetValue("TestModeGlobal", out var tm) && tm is SF.IScriptObjectPropertyGetter tmo && tmo.Object.FormKey == testModeKey,
                     $"property TestModeGlobal is not {testModeKey}");
                Need(props.TryGetValue("StartCardOpenGlobal", out var scop) && scop is SF.IScriptObjectPropertyGetter scoo && scoo.Object.FormKey == startCardOpenKey,
                     $"property StartCardOpenGlobal is not {startCardOpenKey}");
                Need(props.TryGetValue("GameModeGlobal", out var gmp) && gmp is SF.IScriptObjectPropertyGetter gmpo && gmpo.Object.FormKey == gameModeKey,
                     $"property GameModeGlobal is not {gameModeKey}");
                Need(props.TryGetValue("SurvivalStartGlobal", out var ssp) && ssp is SF.IScriptObjectPropertyGetter sspo && sspo.Object.FormKey == survStartKey,
                     $"property SurvivalStartGlobal is not {survStartKey}");
                Need(props.TryGetValue("SurvivalLockedGlobal", out var slp) && slp is SF.IScriptObjectPropertyGetter slpo && slpo.Object.FormKey == survLockedKey,
                     $"property SurvivalLockedGlobal is not {survLockedKey}");
                Need(props.TryGetValue("StartDifficultyGlobal", out var sdp) && sdp is SF.IScriptObjectPropertyGetter sdpo && sdpo.Object.FormKey == startDiffKey,
                     $"property StartDifficultyGlobal is not {startDiffKey}");
                Need(props.TryGetValue("WarfareFactionGlobal", out var wfp) && wfp is SF.IScriptObjectPropertyGetter wfpo && wfpo.Object.FormKey == wfFactionKey,
                     $"property WarfareFactionGlobal is not {wfFactionKey}");
                Need(props.TryGetValue("WarfareStartIndexGlobal", out var wsip) && wsip is SF.IScriptObjectPropertyGetter wsipo && wsipo.Object.FormKey == wfStartIdxKey,
                     $"property WarfareStartIndexGlobal is not {wfStartIdxKey}");
                Need(props.TryGetValue("StartChoiceDoneGlobal", out var scdp) && scdp is SF.IScriptObjectPropertyGetter scdpo && scdpo.Object.FormKey == choiceDoneKey,
                     $"property StartChoiceDoneGlobal is not {choiceDoneKey}");
                Need(props.TryGetValue("StartNeutralSpotGlobal", out var snsp) && snsp is SF.IScriptObjectPropertyGetter snspo && snspo.Object.FormKey == startNeutralSpotKey,
                     $"property StartNeutralSpotGlobal is not {startNeutralSpotKey}");
                Need(props.TryGetValue("StoryLineGlobal", out var stlgp) && stlgp is SF.IScriptObjectPropertyGetter stlgo && stlgo.Object.FormKey == storyLineKey,
                     $"property StoryLineGlobal is not {storyLineKey}");
                Need(props.TryGetValue("StartPlaceRowGlobal", out var sprgp) && sprgp is SF.IScriptObjectPropertyGetter sprgo && sprgo.Object.FormKey == startPlaceRowKey,
                     $"property StartPlaceRowGlobal is not {startPlaceRowKey}");
                Need(props.TryGetValue("PipboyAcquiredGlobal", out var pgp) && pgp is SF.IScriptObjectPropertyGetter pgo && pgo.Object.FormKey == pipboyAcquiredKey,
                     $"property PipboyAcquiredGlobal is not {pipboyAcquiredKey}");
                Need(props.TryGetValue("H00SkipLoadingHookGlobal", out var h0p) && h0p is SF.IScriptObjectPropertyGetter h0o && h0o.Object.FormKey == h00SkipLoadingHookKey,
                     $"property H00SkipLoadingHookGlobal is not {h00SkipLoadingHookKey}");
                Need(props.TryGetValue("H00ClearChargenGlobal", out var h1p) && h1p is SF.IScriptObjectPropertyGetter h1o && h1o.Object.FormKey == h00ClearChargenKey,
                     $"property H00ClearChargenGlobal is not {h00ClearChargenKey}");
                Need(props.TryGetValue("H00SkipArrivalDiscoveryGlobal", out var h2p) && h2p is SF.IScriptObjectPropertyGetter h2o && h2o.Object.FormKey == h00SkipArrivalDiscoveryKey,
                     $"property H00SkipArrivalDiscoveryGlobal is not {h00SkipArrivalDiscoveryKey}");
                Need(props.TryGetValue("H00SkipMapSetupGlobal", out var h3p) && h3p is SF.IScriptObjectPropertyGetter h3o && h3o.Object.FormKey == h00SkipMapSetupKey,
                     $"property H00SkipMapSetupGlobal is not {h00SkipMapSetupKey}");
                Need(props.TryGetValue("H00SkipRouteLootGlobal", out var h4p) && h4p is SF.IScriptObjectPropertyGetter h4o && h4o.Object.FormKey == h00SkipRouteLootKey,
                     $"property H00SkipRouteLootGlobal is not {h00SkipRouteLootKey}");
                Need(props.TryGetValue("H00SkipMissionActorsGlobal", out var h5p) && h5p is SF.IScriptObjectPropertyGetter h5o && h5o.Object.FormKey == h00SkipMissionActorsKey,
                     $"property H00SkipMissionActorsGlobal is not {h00SkipMissionActorsKey}");
                Need(props.TryGetValue("H00SkipLandingQuestsGlobal", out var h6p) && h6p is SF.IScriptObjectPropertyGetter h6o && h6o.Object.FormKey == h00SkipLandingQuestsKey,
                     $"property H00SkipLandingQuestsGlobal is not {h00SkipLandingQuestsKey}");
                Need(props.TryGetValue("H00SkipSurfaceSetPosGlobal", out var h7p) && h7p is SF.IScriptObjectPropertyGetter h7o && h7o.Object.FormKey == h00SkipSurfaceSetPosKey,
                     $"property H00SkipSurfaceSetPosGlobal is not {h00SkipSurfaceSetPosKey}");
                Need(props.TryGetValue("PipboyWristArmor", out var pwp) && pwp is SF.IScriptObjectPropertyGetter pwo && pwo.Object.FormKey == pipboyWrist?.FormKey,
                     "property PipboyWristArmor");
                Need(props.TryGetValue("PipboyCorpseRef", out var prp) && prp is SF.IScriptObjectPropertyGetter pro && pro.Object.FormKey == pipboyRef?.FormKey,
                     "property PipboyCorpseRef");
                Need(props.TryGetValue("GearDoorConsoleRef", out var gcrp) && gcrp is SF.IScriptObjectPropertyGetter gcro && gcro.Object.FormKey == gearConsoleRef?.FormKey,
                     "property GearDoorConsoleRef");
                Need(props.TryGetValue("StartRoomMarkerRef", out var srmp) && srmp is SF.IScriptObjectPropertyGetter srmo && srmo.Object.FormKey == startRoomMarkerRef?.FormKey,
                     "property StartRoomMarkerRef");
                Need(props.TryGetValue("VaultPistolBase", out var vpbp) && vpbp is SF.IScriptObjectPropertyGetter vpbo && vpbo.Object.FormKey == vaultPistolKey,
                     $"property VaultPistolBase is not {vaultPistolKey}");
                var want = o.Hold.Select(e => sf.Quests.FirstOrDefault(x => x.EditorID == e)?.FormKey).ToList();
                Need(want.All(x => x is not null) && props.TryGetValue("HoldOff", out var hp) && hp is SF.IScriptObjectListPropertyGetter hl &&
                     hl.Objects.Select(x => (FormKey?)x.Object.FormKey).SequenceEqual(want), $"property HoldOff is not [{string.Join(", ", o.Hold)}] in order");
                var expected = Properties(pts, places, o, wf, sp, vaultPistolId, routeLootRefIds);
                foreach (var (name, value) in expected)
                    Need(props.TryGetValue(name, out var p) && ValueMatches(value, p), $"property {name} is not {value}");
                Need(props.Count == expected.Count + 43, $"{props.Count} properties, expected {expected.Count + 43}");
                Need(places.VaultAnchor > 0 && places.ExitAnchor > 0, "an anchor id is 0");
                Need((o.VaultSuit is null) == (places.VaultSuit == 0), "the vault suit id does not follow --vault-suit");
                Console.WriteLine($"  inventory reset {InventoryText(o, places)}; {O2Text(o)}");
            }
            else problems.Add($"script {ScriptName} not attached");
            var ls = q.VirtualMachineAdapter?.Scripts.FirstOrDefault(x => x.Name == LooksScript);
            if (ls is not null)
            {
                var props = ls.Properties.ToDictionary(p => p.Name);
                Console.WriteLine($"  script {ls.Name}: {props.Count} properties, RaceMenuMode {(props.TryGetValue("RaceMenuMode", out var rm) && rm is SF.IScriptIntPropertyGetter ri ? ri.Data.ToString() : "missing")}");
                Need(props.TryGetValue("StartMessage", out var smp) && smp is SF.IScriptObjectPropertyGetter so && so.Object.FormKey == start?.FormKey, "property StartMessage");
                var expected = LooksProperties(o);
                foreach (var (name, value) in expected)
                    Need(props.TryGetValue(name, out var p) && ValueMatches(value, p), $"looks property {name} is not {value}");
                Need(props.Count == expected.Count + 1, $"{props.Count} looks properties, expected {expected.Count + 1}");
            }
            var ss = q.VirtualMachineAdapter?.Scripts.FirstOrDefault(x => x.Name == SpecialScript);
            if (ss is not null)
            {
                var props = ss.Properties.ToDictionary(p => p.Name);
                Console.WriteLine($"  script {ss.Name}: {props.Count} properties");
                Need(props.TryGetValue("Special", out var ap) && ap is SF.IScriptObjectListPropertyGetter al &&
                     al.Objects.Select(x => x.Object.FormKey).SequenceEqual(specialKeys) && al.Objects.Count == SpecialNames.Length,
                     $"property Special is not the seven {CoreValuesPlugin} AVIF, Strength to Luck");
                Need(props.TryGetValue("TerminalMessage", out var tp) && tp is SF.IScriptObjectPropertyGetter to && to.Object.FormKey == terminalMsg?.FormKey, "property TerminalMessage");
                Need(props.TryGetValue("SpecialMessage", out var xp) && xp is SF.IScriptObjectPropertyGetter xo && xo.Object.FormKey == specialMsg?.FormKey, "property SpecialMessage");
                Need(props.TryGetValue("SpecialMessagePage2", out var xp2) && xp2 is SF.IScriptObjectPropertyGetter xo2 && xo2.Object.FormKey == specialMsgPage2?.FormKey, "property SpecialMessagePage2");
                var expected = SpecialProperties(pts, places);
                foreach (var (name, value) in expected)
                    Need(props.TryGetValue(name, out var p) && ValueMatches(value, p), $"SPECIAL property {name} is not {value}");
                Need(props.Count == expected.Count + 4, $"{props.Count} SPECIAL properties, expected {expected.Count + 4}");
            }
        }
        // the anchor line names the mode (make_newgame.py anchor_mode reads it into plan.json): "persistent", or
        // "temporary" when the script must center on the cell before the marker resolves
        Console.WriteLine($"  vault anchor FO4Port.esm:{places.VaultAnchor:X6} {places.AnchorMode}, cog door {(places.CogDoor == 0 ? "none" : $"{places.CogDoor:X6} {places.CogDoorBase}")}, " +
                          $"exit anchor FO4TerrainCore.esm:{places.ExitAnchor:X6}");
        foreach (var p in problems) Console.WriteLine("FAIL  " + p);
        Console.WriteLine(problems.Count == 0 ? "all checks pass" : $"{problems.Count} problem(s)");
        return problems.Count == 0 ? 0 : 1;
    }

    // ---------------------------------------------------------------- selftest (synthetic masters only)

    public static int SelfTest(string dir)
    {
        Directory.CreateDirectory(dir);
        var rel = SF.StarfieldRelease.Starfield;
        // a stand-in Fallout4.esm: Vault111Cryo with the pod, the console, the cog door, the platform and the load door
        var f4Key = ModKey.FromFileName("Fallout4.esm");
        var f4 = new F4.Fallout4Mod(f4Key, F4.Fallout4Release.Fallout4);
        f4.ModHeader.Flags |= F4.Fallout4ModHeader.HeaderFlag.Master;
        var vcell = new F4.Cell(new FormKey(f4Key, Fo4VaultCell), F4.Fallout4Release.Fallout4) { EditorID = "Vault111Cryo", Flags = F4.Cell.Flag.IsInteriorCell };
        F4.PlacedObject P(uint id, string? edid, float x, float y, float z, float rz = 0) =>
            new(new FormKey(f4Key, id), F4.Fallout4Release.Fallout4) { EditorID = edid, Position = new P3Float(x, y, z), Rotation = new P3Float(0, 0, rz) };
        vcell.Temporary.Add(P(0x1000, "Vault111PlayerCryopodREF", 700f, 1400f, 70f, MathF.PI / 2));
        vcell.Temporary.Add(P(0x1001, "MQPlayerSpousePodREF", 840f, 1400f, 70f));
        vcell.Temporary.Add(P(Fo4Console, "MQ102GearDoorConsoleREF", 3500f, 700f, 0f));
        vcell.Temporary.Add(P(Fo4PipboySkeleton, "Vault111PipboySkeletonREF", 3480f, 710f, 50f));
        vcell.Temporary.Add(P(Fo4PipboyPickup, "MQ102PipboyTakeFurnitureREF", 3490f, 770f, 45f, 3.8044f));
        vcell.Temporary.Add(P(Fo4CogDoor, "Vault111GearDoorREF", 3640f, 700f, 0f));
        vcell.Temporary.Add(P(Fo4Platform, "V111ElevatorREF", 4200f, 1050f, -140f));
        vcell.Temporary.Add(P(Fo4PlatformMarker, "RespecMoveMarker", 4725f, 1050f, -122.5f));
        // two terminals: one by the pods (the nearer), one far off; the port carries the far one persistent
        var term = new F4.Terminal(new FormKey(f4Key, 0x2000), F4.Fallout4Release.Fallout4) { EditorID = "Vault111CryoTerminal" };
        f4.Terminals.Add(term);
        F4.PlacedObject T(uint id, string edid, float x, float y, float z) { var r = P(id, edid, x, y, z); r.Base = new FormLinkNullable<F4.IPlaceableObjectGetter>(term.FormKey); return r; }
        vcell.Temporary.Add(T(0x1003, "V111OverseerTerminalREF", 3000f, 700f, 0f));
        vcell.Temporary.Add(T(0x1002, "V111CryoTerminalREF", 770f, 1400f, 70f));
        var door = P(Fo4ExitDoor, "Vault111InteriorAutoLoadDoorREF", 4200f, 1050f, 1563f);
        door.TeleportDestination = new F4.TeleportDestination { Door = new FormLink<F4.IPlacedObjectGetter>(new FormKey(f4Key, 0x0998E3)),
                                                                Position = new P3Float(-87500f, 90300f, 7700f), Rotation = new P3Float(0, 0, MathF.PI) };
        vcell.Persistent.Add(door);
        var block = new F4.CellBlock { BlockNumber = 0, GroupType = F4.GroupTypeEnum.InteriorCellBlock };
        var sub = new F4.CellSubBlock { BlockNumber = 0, GroupType = F4.GroupTypeEnum.InteriorCellSubBlock };
        sub.Cells.Add(vcell);
        block.SubBlocks.Add(sub);
        f4.Cells.Records.Add(block);
        f4.Quests.Add(new F4.Quest(new FormKey(f4Key, Fo4MQ102), F4.Fallout4Release.Fallout4) { EditorID = "MQ102", Name = "Out of Time" });
        var f4Path = Path.Combine(dir, "Fallout4.esm");
        f4.BeginWrite.ToPath(f4Path).WithNoLoadOrder().NoCheckIfLowerRangeDisallowed().Write();
        // a stand-in Starfield.esm: the quest type, GameDaysPassed, MQ101Debug, the opening quests, StartupQuest_DO naming
        // MQ101 (at its real id), the COC marker
        var sf = new SF.StarfieldMod(SfEsm, rel);
        sf.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Master;
        sf.Keywords.Add(new SF.Keyword(new FormKey(SfEsm, QuestTypeSideId), rel) { EditorID = QuestTypeSideEdid });
        sf.Globals.Add(new SF.Global(new FormKey(SfEsm, GameDaysPassedId), rel) { EditorID = GameDaysPassedEdid, Data = 0 });
        sf.Globals.Add(new SF.Global(new FormKey(SfEsm, 0x900), rel) { EditorID = DebugGlobEdid, Data = 0 });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x901), rel) { EditorID = "MQ00" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x902), rel) { EditorID = "MQ101" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x903), rel) { EditorID = "MQ101PostQuest" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x904), rel) { EditorID = "MQ_TutorialQuest_Misc04" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x248D20), rel) { EditorID = "SQ_ENV" });   // the real id (PC read 15 Nov)
        // S13 row 5's companion group, at their real ids (result-pc-read-s13-5-partb)
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x009E99), rel) { EditorID = "COM_Companion_SarahMorgan" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x2C5A4A), rel) { EditorID = "COM_Companion_SarahMorgan_SpeechChallenges" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x2EFD8C), rel) { EditorID = "COM_Companion_Shared_Sarah" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x1C7187), rel) { EditorID = "Com_Companion_Barrett" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x14327D), rel) { EditorID = "COM_Companion_Barrett_SpeechChallenges" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x2EFD8B), rel) { EditorID = "COM_Companion_Shared_Barrett" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x23DF2A), rel) { EditorID = "COM_Companion_Andreja" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x1EA09A), rel) { EditorID = "COM_Companion_Andreja_SpeechChallenges" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x2EFD89), rel) { EditorID = "COM_Companion_Shared_Andreja" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x26C5ED), rel) { EditorID = "COM_Companion_SamCoe" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x23EF00), rel) { EditorID = "COM_Companion_SamCoe_SpeechChallenges" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x231A20), rel) { EditorID = "COM_Companion_SamCoe_Cora" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x2EFD8A), rel) { EditorID = "COM_Companion_Shared_SamCoe" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x010A7B), rel) { EditorID = "COM_System_PlayerSharedLines" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x2A567C), rel) { EditorID = "SQ_Companions" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x2A567D), rel) { EditorID = "SQ_Crew" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x1AD42E), rel) { EditorID = "CREW_EliteCrew_Heller" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x26C4EA), rel) { EditorID = "CREW_GenericCrew" });
        // S13 row 5's second group (audio logs and tutorials), at their real ids
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x012996), rel) { EditorID = "AudioLogsQuest" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x0251D2), rel) { EditorID = "AudioLogsQuest_KT" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x043279), rel) { EditorID = "AudioLogsQuest_RQ" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x08612C), rel) { EditorID = "AudioLogsQuest_LVC" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x0C13D5), rel) { EditorID = "AudioLogsQuest_PS" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x195398), rel) { EditorID = "AudioLogsQuest_JM" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x20C63F), rel) { EditorID = "AudioLogsQuest_OB" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x21A1CA), rel) { EditorID = "AudioLogsQuest_BB" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x2491D9), rel) { EditorID = "AudioLogsQuest_FAB" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x24CC1B), rel) { EditorID = "AudioLogsQuest_AN" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x28DFA6), rel) { EditorID = "AudioLogsQuest_WJS" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x296006), rel) { EditorID = "AudioLogsQuest_CT" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x131E6F), rel) { EditorID = "SQ_ENV_Tutorial" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x1ED71C), rel) { EditorID = "OutpostTutorial" });
        // S13 row 5's third group (city and faction dialogue), at their real ids
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x00DBE9), rel) { EditorID = "City_AkilaLife07" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x00E6B8), rel) { EditorID = "DialogueConstellation" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x012F85), rel) { EditorID = "DialogueCrimsonFleet" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x013497), rel) { EditorID = "DialogueUCNewAtlantis" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x0271D8), rel) { EditorID = "DialogueHopetown_Shared" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x05512A), rel) { EditorID = "CityNewAtlantisTransitControl" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x05EA5B), rel) { EditorID = "DialogueTheFirstNPCs" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x061754), rel) { EditorID = "DialogueUCNewAtlantisSecurity" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x07031D), rel) { EditorID = "City_NA_Viewport_Base" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x0EE9FD), rel) { EditorID = "CF_Unique" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x0FC83A), rel) { EditorID = "UC03_DeepMinesSupportQuest" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x10E8EA), rel) { EditorID = "DialogueUCNewAtlantis_Shared" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x143472), rel) { EditorID = "CF_Post" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x14618F), rel) { EditorID = "DialogueUCFactionAlwaysOn" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x14A876), rel) { EditorID = "DialogueFCClinic_IntroPost" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x14EAE4), rel) { EditorID = "City_GG_Bet_SupportQuest" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x178B1E), rel) { EditorID = "CF_Main" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x1C12BB), rel) { EditorID = "DialogueKaiser" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x1C2C97), rel) { EditorID = "DialogueFCClinic" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x1C54EA), rel) { EditorID = "UC08_SupportQuest" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x1E7A0B), rel) { EditorID = "DialogueRedDevilsHQ" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x1E8E2A), rel) { EditorID = "CFSD01" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x20B923), rel) { EditorID = "Dialogue1OfAKindUC07" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x20C59E), rel) { EditorID = "DialogueUCNewAtlantis_Argos" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x2111FE), rel) { EditorID = "City_Neon_Gang_Dialogue" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x216D3C), rel) { EditorID = "DialogueTrackersAllianceAgents" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x22342E), rel) { EditorID = "DialogueFCAkilaCity" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x22DAD5), rel) { EditorID = "DialogueFCNeonEstablishingScene" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x22DAD6), rel) { EditorID = "DialogueFCNeon" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x235BC7), rel) { EditorID = "City_Neon_Chem_Shared" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x240431), rel) { EditorID = "DialogueNewHomestead" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x247D20), rel) { EditorID = "DialogueFreestarRangers" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x24AFED), rel) { EditorID = "DialogueCydonia" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x251581), rel) { EditorID = "DialogueUCInfinityLTD" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x25D3DB), rel) { EditorID = "DialogueUCFactionCydonia" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x263194), rel) { EditorID = "DialogueParadiso" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x265062), rel) { EditorID = "DialogueGagarin_UC_GG" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x26EE1B), rel) { EditorID = "DialogueUCNewAtlantis_LandryHollifeld" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x26F911), rel) { EditorID = "DialogueFCRyujinTower" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x2741B1), rel) { EditorID = "DialogueECSConstant" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x27AE98), rel) { EditorID = "DialogueGenericHouseVaruun" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x28B932), rel) { EditorID = "DialogueEleosRetreat" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x2927FA), rel) { EditorID = "DialogueSeokguhSyndicate" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x2955D8), rel) { EditorID = "DialogueCrucible" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x2956BB), rel) { EditorID = "DialogueUCTheLodge" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x297E37), rel) { EditorID = "Settlement_Convo_NA" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x29D67A), rel) { EditorID = "DialogueUCNewAtlantis_NadiaMuffaz" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x2A0E95), rel) { EditorID = "UC05_EmbassySupportQuest" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x2A1049), rel) { EditorID = "DialogueUCTheDen" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x2A823E), rel) { EditorID = "DialogueHopeTown" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x2A8318), rel) { EditorID = "RI_Support" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x2B180A), rel) { EditorID = "UC02_PerrysMeatsSupportQuest" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x2B2C2B), rel) { EditorID = "DialogueRedMile" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x2C5402), rel) { EditorID = "DialogueUCFactionNewAtlantis" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x2CC108), rel) { EditorID = "DialogueWaggonerFarm_IntroScene" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x2CC109), rel) { EditorID = "DialogueWaggonerFarm" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x34D426), rel) { EditorID = "DialogueNeonConvo_SecurityCheckpoint_Controller" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x352CB8), rel) { EditorID = "City_NA_GuardPointer_Well" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x352CB9), rel) { EditorID = "City_NA_GuardPointer_Botany" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x352CBA), rel) { EditorID = "City_NA_GuardPointer_Viewport" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x352CBB), rel) { EditorID = "City_NA_GuardPointer_NA02" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x370965), rel) { EditorID = "DialogueFCNeon_PlayerHomeQuest" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x376E3C), rel) { EditorID = "City_AC_FAB_Quest05" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x376E3D), rel) { EditorID = "City_AC_FAB_Quest03" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x376E3E), rel) { EditorID = "City_AC_FAB_Quest01" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x376E3F), rel) { EditorID = "City_AC_FAB_Quest02" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x376E40), rel) { EditorID = "City_AC_FAB_Quest04" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x376E41), rel) { EditorID = "City_AC_FAB_Quest06" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x37A1D4), rel) { EditorID = "City_AC_FAB_Quest11" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x37A1D5), rel) { EditorID = "City_AC_FAB_Quest09" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x37A1D6), rel) { EditorID = "City_AC_FAB_Quest07" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x37A1D7), rel) { EditorID = "City_AC_FAB_Quest08" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x37A1D8), rel) { EditorID = "City_AC_FAB_Quest10" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x37A1D9), rel) { EditorID = "City_AC_FAB_Quest12" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x37C5A8), rel) { EditorID = "City_AC_FAB_Quest16" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x37C5A9), rel) { EditorID = "City_AC_FAB_Quest14" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x37C5AA), rel) { EditorID = "City_AC_FAB_Quest13" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x37C5AB), rel) { EditorID = "City_AC_FAB_Quest15" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x37C5AC), rel) { EditorID = "City_AC_FAB_Quest17" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x38430B), rel) { EditorID = "City_AC_FAB_Quest19" });
        // S13 row 5's fourth group (generic dialogue, then activities), at their real ids
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x01E3F9), rel) { EditorID = "DialogueCrowds" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x184511), rel) { EditorID = "DialgoueSSNNScenes" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x19651F), rel) { EditorID = "CR_Dialogue_Turret" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x19D592), rel) { EditorID = "DialogueTerrormorphThrallHuman" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x1A2D27), rel) { EditorID = "DialogueGeneric_LISTOutpost" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x1BA198), rel) { EditorID = "DialogueGenericSpacers" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x1BFCA7), rel) { EditorID = "DialogueGenericUnique_Crime_TheKey" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x1F77DA), rel) { EditorID = "DialogueGenericChildren" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x20C577), rel) { EditorID = "CR_Dialogue_Terrormorph_Base" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x20EC59), rel) { EditorID = "DialogueGenericStarborn_Unique" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x211C5E), rel) { EditorID = "CR_Dialogue_QuadrupedB" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x225314), rel) { EditorID = "DialogueMiniBot" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x2534D3), rel) { EditorID = "DialogueSettleBartenderRumors" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x269BC0), rel) { EditorID = "DialogueCrimeGuards" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x26D87F), rel) { EditorID = "MQ105_AlwaysOnDialogueNeon" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x2711B4), rel) { EditorID = "DialogueGenericVendor_Chunks" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x2711B5), rel) { EditorID = "DialogueGenericVendor_Terrabrew" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x27A4EF), rel) { EditorID = "Staryard_StroudEklund_Dialogue" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x27A4F0), rel) { EditorID = "Staryard_Taiyo_Dialogue" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x27A4F1), rel) { EditorID = "Staryard_Deimos_Dialogue" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x2959DE), rel) { EditorID = "DialogueGenericEclipticANDSoldiers" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x2963AD), rel) { EditorID = "DialogueGenericUnique_Combat" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x2B2112), rel) { EditorID = "Staryard_TridentLuxury_Dialogue" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x2BCA5A), rel) { EditorID = "DialogueGenericCitizens" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x2BCA5C), rel) { EditorID = "DialogueGenericScum" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x2BCA5E), rel) { EditorID = "DialogueGenericGuards" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x2BCA62), rel) { EditorID = "DialogueGenericRobotModelA" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x2BCA63), rel) { EditorID = "DialogueGenericStarborn" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x2BCA64), rel) { EditorID = "DialogueGenericRobotModelS" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x2C1733), rel) { EditorID = "DialogueGenericUnique_Crime" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x30D5FB), rel) { EditorID = "LC082_SuspiciousActors" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x3272C8), rel) { EditorID = "DialogueStarstations" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x0032F6), rel) { EditorID = "MQ207C_AlwaysOn" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x00637D), rel) { EditorID = "Trait_RaisedEnlightenedBoxEnabler" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x0078DF), rel) { EditorID = "Traits_Shared" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x03DBA8), rel) { EditorID = "MQ207C_Support_Fix01" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x0664E3), rel) { EditorID = "Trait_RaisedUniversalBoxEnabler" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x1736F9), rel) { EditorID = "MQ206B_AlwaysOn" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x189658), rel) { EditorID = "SQ_Doctors" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x1991B3), rel) { EditorID = "AspirationalItems" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x1CD001), rel) { EditorID = "MS04" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x2058DE), rel) { EditorID = "Patch_Hotfix" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x20D397), rel) { EditorID = "Patch_Update03_FixFollower" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x214707), rel) { EditorID = "StarbornTempleQuest" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x2A78ED), rel) { EditorID = "SkillMag_CyberRunner_Handler" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x2EF25C), rel) { EditorID = "SQ_PEO_SustenanceDialogue" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x2F0912), rel) { EditorID = "Patch_Update05" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x32AF5F), rel) { EditorID = "SQ_Hoteliers" });
        // S13 row 5's fifth group (radiant, ships, system), at their real ids
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x015300), rel) { EditorID = "MB_Parent" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x0394C5), rel) { EditorID = "SQ_PlayerClearedReward" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x05B4B0), rel) { EditorID = "SE_AC01" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x05F193), rel) { EditorID = "RE_Parent" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x08D848), rel) { EditorID = "RQ_Parent" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x10AC08), rel) { EditorID = "OE_Dialogue" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x160C29), rel) { EditorID = "SEDebug" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x192DD7), rel) { EditorID = "Rad01_LIST" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x1C439D), rel) { EditorID = "RQ_Dialogue" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x05BD6F), rel) { EditorID = "DialogueCrimeGuardShips" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x063085), rel) { EditorID = "DialogueCrimsonFleetShips" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x13E3C8), rel) { EditorID = "DialogueGenericCitizensShips_MuddledChatter" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x13E3C9), rel) { EditorID = "DialogueGenericGuardsShips_MuddledChatter" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x1A2D28), rel) { EditorID = "DialogueGenericVendor_LIST" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x1A5509), rel) { EditorID = "DialogueGenericPiracyShips" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x1BA199), rel) { EditorID = "DialogueGenericSpacersShips" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x20EC5A), rel) { EditorID = "DialogueGenericStarbornShips_Unique" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x22E153), rel) { EditorID = "DialogueShipServices" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x23DE4E), rel) { EditorID = "SQ_ShipVendors" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x24411E), rel) { EditorID = "DialogueGenericGuardsShips" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x24411F), rel) { EditorID = "DialogueGenericHouseVaruunShips" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x255EAF), rel) { EditorID = "DialogueTheFirstShips" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x261767), rel) { EditorID = "SE_Player_Attack_SharedLines" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x2A6C44), rel) { EditorID = "SQ_OutpostCargoLink" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x2BCB81), rel) { EditorID = "DialogueGenericCitizensShips" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x2BCB83), rel) { EditorID = "DialogueGenericEclipticANDSoldierShips" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x2BCB86), rel) { EditorID = "DialogueGenericScumShips" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x2BCB87), rel) { EditorID = "DialogueGenericStarbornShips" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x2BCB88), rel) { EditorID = "DialogueGenericUCGuardsShips" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x2CFDEC), rel) { EditorID = "SQ_CargoShips" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x07C6A9), rel) { EditorID = "SQ_GravitationalTraits" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x146687), rel) { EditorID = "SQ_Traits" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x1D307F), rel) { EditorID = "SQ_ApplyVoices_OBSOLETE" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x257DE5), rel) { EditorID = "LDMasterQuest" });
        sf.Statics.Add(new SF.Static(new FormKey(SfEsm, CocMarkerId), rel) { EditorID = "COCMarkerHeading" });
        var chrono = new SF.Armor(new FormKey(SfEsm, SfChronomarkArmorId), rel) { EditorID = "Clothes_Chronomark_Mq101_NOTPLAYABLE" };
        chrono.MajorRecordFlagsRaw |= 0x4;
        sf.Armors.Add(chrono);
        sf.Armors.Add(new SF.Armor(new FormKey(SfEsm, SfFallbackJumpsuitId), rel) { EditorID = "Clothes_Miner_Jumpsuit" });
        sf.Weapons.Add(new SF.Weapon(new FormKey(SfEsm, 0x24561C), rel) { EditorID = "SynthPistol" });
        sf.Ammunitions.Add(new SF.Ammunition(new FormKey(SfEsm, 0x2B5598), rel) { EditorID = "SynthPistolAmmo" });
        sf.Ingestibles.Add(new SF.Ingestible(new FormKey(SfEsm, 0x00ABF9), rel) { EditorID = "MedPack" });
        sf.Activators.Add(new SF.Activator(new FormKey(SfEsm, SfConsoleActiTemplateId), rel) { EditorID = "IndIntAddonArtifactHolder01" });
        sf.Statics.Add(new SF.Static(new FormKey(SfEsm, SfMapMarkerStaticId), rel) { EditorID = "MapMarker" });
        var startupDo = new SF.DefaultObject(new FormKey(SfEsm, StartupId), rel) { EditorID = StartupEdid };
        startupDo.Object.SetTo(new FormKey(SfEsm, 0x902));
        sf.DefaultObjects.Add(startupDo);
        sf.ModHeader.Stats.NextFormID = 0x800;
        var sfPath = Path.Combine(dir, "Starfield.esm");
        sf.BeginWrite.ToPath(sfPath).WithNoLoadOrder().NoCheckIfLowerRangeDisallowed().Write();
        // two Starfield.esm the writer refuses: one without StartupQuest_DO, one whose StartupQuest_DO names MQ00 (a start
        // already replaced, or an update)
        string SfVariant(string name, Action<SF.StarfieldMod> edit)
        {
            var m = SF.StarfieldMod.CreateFromBinary(sfPath, rel);
            edit(m);
            var d = Path.Combine(dir, name);
            Directory.CreateDirectory(d);
            var path = Path.Combine(d, "Starfield.esm");
            m.BeginWrite.ToPath(path).WithNoLoadOrder().NoCheckIfLowerRangeDisallowed().Write();
            return path;
        }
        var sfNoStartup = SfVariant("sf_nostartup", m => m.DefaultObjects.Clear());
        var sfOtherStartup = SfVariant("sf_otherstartup", m => m.DefaultObjects.First().Object.SetTo(new FormKey(SfEsm, 0x901)));
        // and one whose StartupQuest_DO sits at another id than 00562D, the record the deployment gate's start check knows
        var sfMovedStartup = SfVariant("sf_movedstartup", m => { var d = m.DefaultObjects.First(); m.DefaultObjects.Remove(d.FormKey); m.DefaultObjects.Add((SF.DefaultObject)d.Duplicate(new FormKey(SfEsm, 0x905))); });
        // a port with FO4Port_Vault111Cryo: its COC marker and the cog door, and formids.json as PluginSpike writes it
        var portKey = ModKey.FromFileName("FO4Port.esm");
        var port = new SF.StarfieldMod(portKey, rel);
        port.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Master;
        var pdoor = new SF.Door(new FormKey(portKey, 0x810), rel) { EditorID = "FO4Port_VltGearDoor01" };
        port.Doors.Add(pdoor);
        var plift = new SF.Activator(new FormKey(portKey, 0x811), rel) { EditorID = "FO4Port_acti_0244ef_fallout4" };
        port.Activators.Add(plift);
        var pconsole = new SF.Activator(new FormKey(portKey, 0x812), rel) { EditorID = "FO4Port_acti_091a48_fallout4", Name = "Vault Door Controls" };
        port.Activators.Add(pconsole);
        var ppipboy = new SF.Static(new FormKey(portKey, 0x813), rel) { EditorID = PortPipboyStaticEdid };
        port.Statics.Add(ppipboy);
        // the vault suit the inventory reset may equip (--vault-suit): the port's own ARMO, named by EditorID
        const string SuitEdid = "FO4Port_VaultSuit111";
        port.Armors.Add(new SF.Armor(new FormKey(portKey, 0x820), rel) { EditorID = SuitEdid });
        var pcell = new SF.Cell(new FormKey(portKey, 0x800), rel) { EditorID = VaultCell, Flags = SF.Cell.Flag.IsInteriorCell };
        pcell.Temporary.Add(new SF.PlacedObject(new FormKey(portKey, 0x801), rel) { Base = new FormLinkNullable<SF.IPlaceableObjectGetter>(new FormKey(SfEsm, CocMarkerId)), Position = new P3Float(60, 15, 1) });
        pcell.Temporary.Add(new SF.PlacedObject(new FormKey(portKey, 0x802), rel) { Base = new FormLinkNullable<SF.IPlaceableObjectGetter>(pdoor.FormKey), Position = new P3Float(52, 10, 0) });
        // persistent references of the port in the cell (the converted load doors are): the COC marker is temporary, so
        // the anchor is the nearer of these two
        SF.PlacedObject Pers(uint id, float x, float y, float z) { var r = new SF.PlacedObject(new FormKey(portKey, id), rel) { Base = new FormLinkNullable<SF.IPlaceableObjectGetter>(pdoor.FormKey), Position = new P3Float(x, y, z) }; r.MajorRecordFlagsRaw |= 0x400; return r; }
        pcell.Persistent.Add(Pers(0x805, 60, 25, 1));
        pcell.Persistent.Add(Pers(0x806, 90, 40, 20));
        // the terminals: the nearer one temporary, the farther persistent (preferred)
        pcell.Temporary.Add(new SF.PlacedObject(new FormKey(portKey, 0x807), rel) { Base = new FormLinkNullable<SF.IPlaceableObjectGetter>(pdoor.FormKey), Position = new P3Float(11, 20, 1) });
        pcell.Persistent.Add(Pers(0x808, 42.857f, 10, 0));
        pcell.Temporary.Add(new SF.PlacedObject(new FormKey(portKey, 0x809), rel) { Base = new FormLinkNullable<SF.IPlaceableObjectGetter>(plift.FormKey), Position = new P3Float(60, 15, -2) });
        pcell.Temporary.Add(new SF.PlacedObject(new FormKey(portKey, 0x80A), rel) { Base = new FormLinkNullable<SF.IPlaceableObjectGetter>(pconsole.FormKey), Position = new P3Float(50, 10, 0) });
        pcell.Temporary.Add(new SF.PlacedObject(new FormKey(portKey, 0x80B), rel) { Base = new FormLinkNullable<SF.IPlaceableObjectGetter>(ppipboy.FormKey), Position = new P3Float(49.857f, 11, 0.643f) });
        var pb = new SF.CellBlock { BlockNumber = 0, GroupType = SF.GroupTypeEnum.InteriorCellBlock };
        var ps = new SF.CellSubBlock { BlockNumber = 0, GroupType = SF.GroupTypeEnum.InteriorCellSubBlock };
        ps.Cells.Add(pcell);
        pb.SubBlocks.Add(ps);
        port.Cells.Records.Add(pb);
        port.ModHeader.Stats.NextFormID = 0x821;
        var portPath = Path.Combine(dir, portKey.FileName);
        port.BeginWrite.ToPath(portPath).WithLoadOrder(SfEsm).WithKnownMasters(new KeyedMasterStyle(SfEsm, MasterStyle.Full)).Write();
        var idsPath = Path.Combine(dir, "formids.json");
        File.WriteAllText(idsPath, $"{{\"CELL:{VaultCell}\": {0x800}, \"REFR:{VaultCell}:0330C3:Fallout4.esm\": {0x802}, \"DOOR:FO4Port_VltGearDoor01\": {0x810}, " +
                                   $"\"REFR:{VaultCell}:091A49:Fallout4.esm\": {0x80A}, \"REFR:{VaultCell}:075039:Fallout4.esm\": {0x80B}, " +
                                   $"\"REFR:{VaultCell}:001002:Fallout4.esm\": {0x807}, \"REFR:{VaultCell}:001003:Fallout4.esm\": {0x808}, \"REFR:{VaultCell}:0244EB:Fallout4.esm\": {0x809}}}");
        var noCogIds = Path.Combine(dir, "formids_nocog.json");          // neither the cog door nor a terminal (retains required console)
        File.WriteAllText(noCogIds, $"{{\"CELL:{VaultCell}\": {0x800}, \"REFR:{VaultCell}:091A49:Fallout4.esm\": {0x80A}}}");
        var noConsoleIds = Path.Combine(dir, "formids_noconsole.json");  // missing required gear-door console mapping -> refused
        File.WriteAllText(noConsoleIds, $"{{\"CELL:{VaultCell}\": {0x800}, \"REFR:{VaultCell}:0330C3:Fallout4.esm\": {0x802}}}");
        var nearTermIds = Path.Combine(dir, "formids_nearterm.json");    // only the nearer, temporary terminal
        File.WriteAllText(nearTermIds, $"{{\"CELL:{VaultCell}\": {0x800}, \"REFR:{VaultCell}:0330C3:Fallout4.esm\": {0x802}, \"REFR:{VaultCell}:091A49:Fallout4.esm\": {0x80A}, \"REFR:{VaultCell}:075039:Fallout4.esm\": {0x80B}, \"REFR:{VaultCell}:001002:Fallout4.esm\": {0x807}}}");
        // a core with the world and its Vault 111 map marker, persistent
        var coreKey = ModKey.FromFileName("FO4TerrainCore.esm");
        var core = new SF.StarfieldMod(coreKey, rel);
        core.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Master;
        var world = new SF.Worldspace(new FormKey(coreKey, 0x803), rel) { EditorID = World };
        world.TopCell = new SF.Cell(new FormKey(coreKey, 0x900), rel);
        var marker = new SF.PlacedObject(new FormKey(coreKey, 0xA775B), rel) { EditorID = ExitAnchorEdid, Base = new FormLinkNullable<SF.IPlaceableObjectGetter>(new FormKey(SfEsm, SfMapMarkerStaticId)), Position = new P3Float(-1275.3f, 1305.3f, 108.2f) };
        marker.MajorRecordFlagsRaw |= 0x400;
        world.TopCell.Persistent.Add(marker);
        var sancMarker = new SF.PlacedObject(new FormKey(coreKey, 0xA775A), rel) { EditorID = "FO4Core_CommonwealthMapMarkerSanctuary", Base = new FormLinkNullable<SF.IPlaceableObjectGetter>(new FormKey(SfEsm, SfMapMarkerStaticId)), Position = new P3Float(-1153.831f, 1259.64f, 110.263f) };
        sancMarker.MajorRecordFlagsRaw |= 0x400;
        world.TopCell.Persistent.Add(sancMarker);
        core.Worldspaces.Add(world);
        core.ModHeader.Stats.NextFormID = 0xA775C;
        var corePath = Path.Combine(dir, coreKey.FileName);
        core.BeginWrite.ToPath(corePath).WithLoadOrder(SfEsm).WithKnownMasters(new KeyedMasterStyle(SfEsm, MasterStyle.Full)).Write();

        var defaultPointsPath = Path.Combine(dir, "points_default.json");
        if (DefaultPodStep != -2.5f || Points(f4Path, defaultPointsPath, null, DefaultPodStep) != 0) { Console.WriteLine("FAIL  DefaultPodStep"); return 1; }
        var dpts = JsonDocument.Parse(File.ReadAllText(defaultPointsPath)).RootElement;
        var dstand = Floats(dpts.GetProperty("pod").GetProperty("pos"));
        if (MathF.Abs(dstand[0] - 7.5f) > 1e-3 || MathF.Abs(dstand[1] - 20f) > 1e-3 || MathF.Abs(dpts.GetProperty("pod").GetProperty("heading").GetSingle() - 90f) > 1e-3 ||
            MathF.Abs(dpts.GetProperty("pod").GetProperty("step_m").GetSingle() - (-2.5f)) > 1e-3)
            { Console.WriteLine($"FAIL  default pod stand point {string.Join(",", dstand)}"); return 1; }
        var platPos = Floats(dpts.GetProperty("platform").GetProperty("pos"));
        var platRefPos = Floats(dpts.GetProperty("platform").GetProperty("ref_pos"));
        if (dpts.GetProperty("platform").GetProperty("src").GetString() != "000244EB" ||
            dpts.GetProperty("platform").GetProperty("stand_src").GetString() != "0001B29E" ||
            MathF.Abs(platPos[0] - 67.5f) > 1e-3 || MathF.Abs(platRefPos[0] - 60f) > 1e-3)
            { Console.WriteLine("FAIL  platform stand marker vs ref origin"); return 1; }
        var pointsPath = Path.Combine(dir, "points.json");
        int rc = Points(f4Path, pointsPath, null, 1.0f);
        if (rc != 0) return rc;
        var pts = JsonDocument.Parse(File.ReadAllText(pointsPath)).RootElement;
        var terms = Terminals(pts);
        // nearest the pod first: the cryo terminal (one metre from the pod), then the overseer's
        if (terms.Count != 2 || terms[0].Src != 0x1002 || terms[1].Src != 0x1003 || MathF.Abs(terms[0].Pos.X - 11f) > 1e-3) { Console.WriteLine($"FAIL  terminals {string.Join(",", terms)}"); return 1; }
        var oneTerm = Path.Combine(dir, "points_oneterm.json");
        if (Points(f4Path, oneTerm, null, 1.0f, "1003") != 0 || Terminals(JsonDocument.Parse(File.ReadAllText(oneTerm)).RootElement).Select(t => t.Src).SequenceEqual(new uint[] { 0x1003 }) == false)
            { Console.WriteLine("FAIL  --terminal-ref"); return 1; }
        var stand = Floats(pts.GetProperty("pod").GetProperty("pos"));
        // the pod faces +x (rotation pi/2): one metre out of it is x + 1
        if (MathF.Abs(stand[0] - 11f) > 1e-3 || MathF.Abs(stand[1] - 20f) > 1e-3 || MathF.Abs(pts.GetProperty("pod").GetProperty("heading").GetSingle() - 90f) > 1e-3)
            { Console.WriteLine($"FAIL  pod stand point {string.Join(",", stand)}"); return 1; }
        if (pts.GetProperty("arrival").GetProperty("to").GetString() != "000998E3") { Console.WriteLine("FAIL  arrival"); return 1; }
        if (!IsPlayerPod("Vault111PlayerCryopodREF") || IsPlayerPod("MQPlayerSpousePodREF") || !IsPlayerPod("MQPlayerCryopodREF") || IsPlayerPod(null)) { Console.WriteLine("FAIL  IsPlayerPod"); return 1; }
        if (!IsCogDoorKey($"REFR:{VaultCell}:0330C3:Fallout4.esm") || !IsCogDoorKey($"REFR:{VaultCell}:000330C3:Fallout4.esm") ||
            IsCogDoorKey($"REFR:{VaultCell}:0330C4:Fallout4.esm") || IsCogDoorKey($"REFR:FO4Port_Other:0330C3:Fallout4.esm") ||
            IsCogDoorKey($"REFR:{VaultCell}:0330C3:DLCRobot.esm")) { Console.WriteLine("FAIL  IsCogDoorKey"); return 1; }

        var outDir = Path.Combine(dir, "out");
        var plain = Options.From(Array.Empty<string>());
        if (plain.MQ101Debug is not null || plain.DebugAfterHold != DefaultDebugAfterHold || !plain.Hold.SequenceEqual(DefaultHold)) { Console.WriteLine("FAIL  the default options"); return 1; }
        // S13 row 2b: Starfield's environment quest is held off by default, and the reset brings the O2 capacity
        if (!DefaultHold.SequenceEqual(HoldCore.Concat(HoldCompanions).Concat(HoldAudioTutorials).Concat(HoldCityFaction).Concat(HoldGenericDialogue).Concat(HoldActivities).Concat(HoldRadiant).Concat(HoldShips).Concat(HoldSystem)) || DefaultHold.Distinct().Count() != DefaultHold.Length) { Console.WriteLine("FAIL  the hold list"); return 1; }
        if (!DefaultHold.Contains("SQ_ENV") || !DefaultO2Fill || !plain.O2 || Options.From(new[] { "--no-o2-fill" }).O2 ||
            Options.From(new[] { "--keep-inventory" }).O2) { Console.WriteLine("FAIL  the environment options"); return 1; }
        var lift = Options.From(new[] { "--animated-exit-lift" });
        var liftKeep = Options.From(new[] { "--animated-exit-lift", "--keep-inventory" });
        var liftNoO2 = Options.From(new[] { "--animated-exit-lift", "--no-o2-fill" });
        if (plain.AnimatedExitLift || !lift.AnimatedExitLift || !lift.ClearInventory || !lift.O2 ||
            !liftKeep.AnimatedExitLift || liftKeep.ClearInventory || liftKeep.O2 ||
            !liftNoO2.AnimatedExitLift || !liftNoO2.ClearInventory || liftNoO2.O2)
            { Console.WriteLine("FAIL  the combined lift/inventory/O2 options"); return 1; }
        if (Options.From(new[] { "--no-mq101debug" }).MQ101Debug is not null || Options.From(new[] { "--mq101debug", "8" }).MQ101Debug != 8 ||
            Options.From(new[] { "--debug-after-hold", "0" }).DebugAfterHold != 0) { Console.WriteLine("FAIL  the MQ101Debug options"); return 1; }
        if (plain.RaceMenuMode != DefaultRaceMenuMode || DefaultRaceMenuMode == 0 || Options.From(new[] { "--race-menu-mode", "0" }).RaceMenuMode != 0) { Console.WriteLine("FAIL  the race menu mode option"); return 1; }
        if (!plain.Special || Options.From(new[] { "--no-special" }).Special) { Console.WriteLine("FAIL  the SPECIAL option"); return 1; }
        if (!plain.Version || plain.BuildVersion != DefaultBuildVersion || Options.From(new[] { "--no-version" }).Version ||
            Options.From(new[] { "--build-version", "2" }).BuildVersion != 2) { Console.WriteLine("FAIL  the version options"); return 1; }
        // the inventory reset is on by default (S13 row 2), --keep-inventory turns it off and --clear-inventory (old
        // command lines) changes nothing; the suit needs the reset and an EditorID
        if (!DefaultClearInventory || !plain.ClearInventory || plain.VaultSuit is not null || Options.From(new[] { "--keep-inventory" }).ClearInventory ||
            !Options.From(new[] { "--clear-inventory" }).ClearInventory ||
            Options.From(new[] { "--vault-suit", SuitEdid }) is not { ClearInventory: true, VaultSuit: SuitEdid } ||
            Options.From(new[] { "--clear-inventory", "--vault-suit", SuitEdid }) is not { ClearInventory: true, VaultSuit: SuitEdid }) { Console.WriteLine("FAIL  the inventory options"); return 1; }
        foreach (var (why, bad) in new[] { ("--vault-suit with --keep-inventory", new[] { "--keep-inventory", "--vault-suit", SuitEdid }), ("--vault-suit without an EditorID", new[] { "--vault-suit" }),
                                           ("--keep-inventory with --clear-inventory", new[] { "--keep-inventory", "--clear-inventory" }),
                                           ("--vault-suit followed by another option", new[] { "--vault-suit", "--no-looks" }) })
        {
            try { Options.From(bad); Console.WriteLine($"FAIL  options accepted {why}"); return 1; }
            catch (Refusal e) { Console.WriteLine($"refused as expected ({why}): {e.Message}"); }
        }
        // the anchor mode: since newgame_v11 the temporary fallback is off by default; --allow-temporary-anchor turns it
        // on, --require-persistent-anchor (old command lines) changes nothing, and the two together are refused
        var allowTemp = plain with { RequirePersistentAnchor = false };
        if (!plain.RequirePersistentAnchor || Options.From(new[] { "--allow-temporary-anchor" }).RequirePersistentAnchor ||
            !Options.From(new[] { "--require-persistent-anchor" }).RequirePersistentAnchor) { Console.WriteLine("FAIL  the anchor option"); return 1; }
        try { Options.From(new[] { "--allow-temporary-anchor", "--require-persistent-anchor" }); Console.WriteLine("FAIL  options accepted both anchor options"); return 1; }
        catch (Refusal e) { Console.WriteLine($"refused as expected (both anchor options): {e.Message}"); }
        if (plain.StartChoiceBackdrop != BackdropEmptyCell ||
            Options.From(new[] { "--start-choice-backdrop", "setup_menu" }).StartChoiceBackdrop != BackdropSetupMenu ||
            Options.From(new[] { "--start-choice-backdrop", "title_card" }).StartChoiceBackdrop != BackdropTitleCard)
            { Console.WriteLine("FAIL  the start-choice-backdrop options"); return 1; }
        var keep = plain with { ClearInventory = false };
        var suit = plain with { VaultSuit = SuitEdid };
        var variants = new (string Name, string Ids, Options O)[]
        {
            ("keep", idsPath, keep), ("suit", idsPath, suit),
            ("lift", idsPath, lift), ("liftkeep", idsPath, liftKeep), ("liftnoo2", idsPath, liftNoO2),
            ("default", idsPath, plain), ("setupmenu", idsPath, plain with { StartChoiceBackdrop = BackdropSetupMenu }),
            ("nolooks", idsPath, plain with { Looks = false }), ("nofadehold", idsPath, plain with { FadeHold = false }),
            ("debug0", idsPath, plain with { MQ101Debug = 0 }), ("debug8", idsPath, plain with { MQ101Debug = 8 }),
            ("nowrite", idsPath, plain with { DebugAfterHold = 0 }),
            ("debug10", idsPath, plain with { MQ101Debug = 10 }),   // the first build's value, still buildable on purpose
            ("nocog", noCogIds, plain), ("hold2", idsPath, plain with { Hold = new[] { "MQ00", "MQ101" } }),
            ("mode0", idsPath, plain with { RaceMenuMode = 0 }), ("nospecial", idsPath, plain with { Special = false }),
            ("nearterm", nearTermIds, plain),
            ("noversion", idsPath, plain with { Version = false }), ("version2", idsPath, plain with { BuildVersion = 2 }),
            ("noo2", idsPath, plain with { O2Fill = false }),
            ("nocompanions", idsPath, plain with { Hold = HoldCore }),
            ("noaudio", idsPath, plain with { Hold = HoldCore.Concat(HoldCompanions).ToArray() }),
            ("nocity", idsPath, plain with { Hold = HoldCore.Concat(HoldCompanions).Concat(HoldAudioTutorials).ToArray() }),
            ("nodialogue", idsPath, plain with { Hold = HoldCore.Concat(HoldCompanions).Concat(HoldAudioTutorials).Concat(HoldCityFaction).ToArray() }),
            ("noactivities", idsPath, plain with { Hold = HoldCore.Concat(HoldCompanions).Concat(HoldAudioTutorials).Concat(HoldCityFaction).Concat(HoldGenericDialogue).ToArray() }),
            ("noradiant", idsPath, plain with { Hold = HoldCore.Concat(HoldCompanions).Concat(HoldAudioTutorials).Concat(HoldCityFaction).Concat(HoldGenericDialogue).Concat(HoldActivities).ToArray() }),
            ("noships", idsPath, plain with { Hold = HoldCore.Concat(HoldCompanions).Concat(HoldAudioTutorials).Concat(HoldCityFaction).Concat(HoldGenericDialogue).Concat(HoldActivities).Concat(HoldRadiant).ToArray() }),
            ("nosystem", idsPath, plain with { Hold = HoldCore.Concat(HoldCompanions).Concat(HoldAudioTutorials).Concat(HoldCityFaction).Concat(HoldGenericDialogue).Concat(HoldActivities).Concat(HoldRadiant).Concat(HoldShips).ToArray() }),
        };
        foreach (var (name, ids, o) in variants)
        {
            var od = Path.Combine(outDir, name);
            rc = Write(sfPath, portPath, ids, corePath, pointsPath, od, o);
            if (rc == 0) rc = Check(Path.Combine(od, Plugin), sfPath, portPath, ids, corePath, pointsPath, o);
            if (rc != 0) return rc;
        }
        // the options are part of the build: checked against other options, a build fails
        var crosses = new (string Build, Options O, string Ids, string Why)[]
        {
            ("default", plain with { AnimatedExitLift = true }, idsPath, "a teleport build as a carrying-lift one"),
            ("lift", plain, idsPath, "a carrying-lift build as a teleport one"),
            ("liftkeep", lift, idsPath, "an inventory-kept lift build as the default reset lift"),
            ("lift", liftKeep, idsPath, "a reset lift build as an inventory-kept one"),
            ("liftnoo2", lift, idsPath, "a no-O2 lift build as the default O2 lift"),
            ("lift", liftNoO2, idsPath, "an O2 lift build as a no-O2 one"),
            ("default", plain with { Looks = false }, idsPath, "a looks build as a no-looks one"),
            ("nolooks", plain, idsPath, "a no-looks build as a looks one"),
            ("default", plain with { FadeHold = false }, idsPath, "a fade-hold build as a no-fade-hold one"),
            ("nofadehold", plain, idsPath, "a no-fade-hold build as a fade-hold one"),
            ("default", plain with { MQ101Debug = 0 }, idsPath, "the default (no override) build as an explicit MQ101Debug 0 one"),
            ("debug0", plain, idsPath, "an explicit MQ101Debug 0 build as the default one"),
            ("default", plain with { DebugAfterHold = 0 }, idsPath, "the default build as one that never writes MQ101Debug"),
            ("nowrite", plain, idsPath, "a never-writes build as the default one"),
            ("default", plain with { MQ101Debug = 8 }, idsPath, "the default build as an MQ101Debug 8 one"),
            ("debug8", plain, idsPath, "an MQ101Debug 8 build as the default one"),
            ("debug10", plain, idsPath, "the first build's MQ101Debug 10 as the default one"),
            ("debug8", plain with { MQ101Debug = 0 }, idsPath, "an MQ101Debug 8 build as an MQ101Debug 0 one"),
            ("debug0", plain with { MQ101Debug = 8 }, idsPath, "an MQ101Debug 0 build as an MQ101Debug 8 one"),
            ("nocog", plain, idsPath, "a build without the cog door against a port with it"),
            ("default", plain with { Hold = new[] { "MQ00", "MQ101" } }, idsPath, "the default hold list as the two-quest one"),
            ("hold2", plain, idsPath, "a two-quest hold list as the default one"),
            ("default", plain with { RaceMenuMode = 0 }, idsPath, "the default (race menu mode 2) build as a full-creator mode 0 one"),
            ("mode0", plain, idsPath, "a full-creator race menu mode 0 build as the default one"),
            ("default", plain with { Special = false }, idsPath, "a SPECIAL build as a --no-special one"),
            ("nospecial", plain, idsPath, "a --no-special build as a SPECIAL one"),
            ("default", plain, nearTermIds, "a build on the persistent terminal against a port with only the temporary one"),
            ("nearterm", plain, idsPath, "a build on the temporary terminal against a port with the persistent one"),
            ("default", plain with { Version = false }, idsPath, "a version-check build as a --no-version one"),
            ("noversion", plain, idsPath, "a --no-version build as a version-check one"),
            ("default", plain with { BuildVersion = 2 }, idsPath, "the default (build version 1) build as a version 2 one"),
            ("version2", plain, idsPath, "a build version 2 build as the default one"),
            ("default", keep, idsPath, "the default (inventory cleared) build as a --keep-inventory one"),
            ("keep", plain, idsPath, "a --keep-inventory build as the default one"),
            ("default", suit, idsPath, "the default build without a suit as a --vault-suit one"),
            ("suit", plain, idsPath, "a --vault-suit build as the default one without a suit"),
            ("suit", keep, idsPath, "a --vault-suit build as a --keep-inventory one"),
            ("default", plain with { O2Fill = false }, idsPath, "the default (O2 capacity) build as a --no-o2-fill one"),
            ("noo2", plain, idsPath, "a --no-o2-fill build as the default one"),
            ("hold2", plain, idsPath, "a hold list without SQ_ENV as the default one"),
            ("nocompanions", plain, idsPath, "a hold list without the companion group as the default one"),
            ("default", plain with { Hold = HoldCore }, idsPath, "the default hold list as one without the companion group"),
            ("noaudio", plain, idsPath, "a hold list without the audio-log and tutorial group as the default one"),
            ("default", plain with { Hold = HoldCore.Concat(HoldCompanions).ToArray() }, idsPath, "the default hold list as one without the audio-log and tutorial group"),
            ("nocity", plain, idsPath, "a hold list without the city and faction group as the default one"),
            ("default", plain with { Hold = HoldCore.Concat(HoldCompanions).Concat(HoldAudioTutorials).ToArray() }, idsPath, "the default hold list as one without the city and faction group"),
            ("nodialogue", plain, idsPath, "a hold list without the generic dialogue and activities group as the default one"),
            ("default", plain with { Hold = HoldCore.Concat(HoldCompanions).Concat(HoldAudioTutorials).Concat(HoldCityFaction).ToArray() }, idsPath, "the default hold list as one without the generic dialogue and activities group"),
            ("noactivities", plain, idsPath, "a hold list without the activities as the default one"),
            ("default", plain with { Hold = HoldCore.Concat(HoldCompanions).Concat(HoldAudioTutorials).Concat(HoldCityFaction).Concat(HoldGenericDialogue).ToArray() }, idsPath, "the default hold list as one without the activities"),
            ("noradiant", plain, idsPath, "a hold list without the radiant, ship and system group as the default one"),
            ("default", plain with { Hold = HoldCore.Concat(HoldCompanions).Concat(HoldAudioTutorials).Concat(HoldCityFaction).Concat(HoldGenericDialogue).Concat(HoldActivities).ToArray() }, idsPath, "the default hold list as one without the radiant, ship and system group"),
            ("noships", plain, idsPath, "a hold list without the ships and system lists as the default one"),
            ("default", plain with { Hold = HoldCore.Concat(HoldCompanions).Concat(HoldAudioTutorials).Concat(HoldCityFaction).Concat(HoldGenericDialogue).Concat(HoldActivities).Concat(HoldRadiant).ToArray() }, idsPath, "the default hold list as one without the ships and system lists"),
            ("nosystem", plain, idsPath, "a hold list without the system list as the default one"),
            ("default", plain with { Hold = HoldCore.Concat(HoldCompanions).Concat(HoldAudioTutorials).Concat(HoldCityFaction).Concat(HoldGenericDialogue).Concat(HoldActivities).Concat(HoldRadiant).Concat(HoldShips).ToArray() }, idsPath, "the default hold list as one without the system list"),
        };
        foreach (var (build, o, ids, why) in crosses)
        {
            if (Check(Path.Combine(outDir, build, Plugin), sfPath, portPath, ids, corePath, pointsPath, o) == 0) { Console.WriteLine($"FAIL  check passed {why}"); return 1; }
            Console.WriteLine($"rejected: {why}");
        }
        var good = Path.Combine(outDir, "default", Plugin);
        var mutations = new (string Name, Action<SF.StarfieldMod> Edit)[]
        {
            ("start game enabled again", m => m.Quests.First().Data!.Flags |= SF.Quest.Flag.StartGameEnabled),
            ("the startup override removed", m => m.DefaultObjects.Clear()),
            ("the startup override names Starfield's opening again", m => m.DefaultObjects.First().Object.SetTo(new FormKey(SfEsm, 0x902))),
            ("the startup override names MQ00", m => m.DefaultObjects.First().Object.SetTo(new FormKey(SfEsm, 0x901))),
            ("the startup override renamed", m => m.DefaultObjects.First().EditorID = "StartupQuest_DO2"),
            ("a second DFOB override", m => m.DefaultObjects.Add(new SF.DefaultObject(new FormKey(SfEsm, StartupId + 1), rel) { EditorID = "OtherDO" })),
            ("our own new DFOB named StartupQuest_DO instead of the override", m =>
                { m.DefaultObjects.Clear(); var d = new SF.DefaultObject(new FormKey(m.ModKey, 0x8FF), rel) { EditorID = StartupEdid }; d.Object.SetTo(new FormKey(m.ModKey, QuestId)); m.DefaultObjects.Add(d); }),
            ("an MQ101 override added", m => m.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x902), rel) { EditorID = "MQ101" })),
            ("not run once", m => m.Quests.First().Data!.Flags &= ~SF.Quest.Flag.RunOnce),
            ("a stage missing", m => m.Quests.First().Stages.RemoveAt(0)),
            ("the vault anchor id changed", m => ((SF.ScriptIntProperty)m.Quests.First().VirtualMachineAdapter!.Scripts[0].Properties.First(p => p.Name == "VaultAnchorId")).Data = 0x999),
            ("a position changed", m => ((SF.ScriptFloatProperty)m.Quests.First().VirtualMachineAdapter!.Scripts[0].Properties.First(p => p.Name == "ArrivalX")).Data += 1),
            ("the merge offset changed", m => ((SF.ScriptFloatProperty)m.Quests.First().VirtualMachineAdapter!.Scripts[0].Properties.First(p => p.Name == "MergeOffsetY")).Data = 0),
            ("a property removed", m => m.Quests.First().VirtualMachineAdapter!.Scripts[0].Properties.RemoveAll(p => p.Name == "PodHeading")),
            ("the Opening property removed", m => m.Quests.First().VirtualMachineAdapter!.Scripts[0].Properties.RemoveAll(p => p.Name == "Opening")),
            ("the DebugGlobal property removed", m => m.Quests.First().VirtualMachineAdapter!.Scripts[0].Properties.RemoveAll(p => p.Name == "DebugGlobal")),
            ("the DebugGlobal property on another global", m => ((SF.ScriptObjectProperty)m.Quests.First().VirtualMachineAdapter!.Scripts[0].Properties.First(p => p.Name == "DebugGlobal")).Object.SetTo(new FormKey(SfEsm, GameDaysPassedId))),
            ("the DebugAfterHold property reads the first build's 10", m => ((SF.ScriptIntProperty)m.Quests.First().VirtualMachineAdapter!.Scripts[0].Properties.First(p => p.Name == "DebugAfterHold")).Data = 10),
            ("the DebugAfterHold property removed", m => m.Quests.First().VirtualMachineAdapter!.Scripts[0].Properties.RemoveAll(p => p.Name == "DebugAfterHold")),
            ("the hold list emptied", m => ((SF.ScriptObjectListProperty)m.Quests.First().VirtualMachineAdapter!.Scripts[0].Properties.First(p => p.Name == "HoldOff")).Objects.Clear()),
            ("the hold list lost MQ101PostQuest", m => ((SF.ScriptObjectListProperty)m.Quests.First().VirtualMachineAdapter!.Scripts[0].Properties.First(p => p.Name == "HoldOff")).Objects.RemoveAt(2)),
            ("the hold list lost SQ_Traits", m => ((SF.ScriptObjectListProperty)m.Quests.First().VirtualMachineAdapter!.Scripts[0].Properties.First(p => p.Name == "HoldOff")).Objects.RemoveAt(HoldCore.Length + HoldCompanions.Length + HoldAudioTutorials.Length + HoldCityFaction.Length + HoldGenericDialogue.Length + HoldActivities.Length + HoldRadiant.Length + HoldShips.Length + Array.IndexOf(HoldSystem, "SQ_Traits"))),
            ("the hold list lost DialogueShipServices", m => ((SF.ScriptObjectListProperty)m.Quests.First().VirtualMachineAdapter!.Scripts[0].Properties.First(p => p.Name == "HoldOff")).Objects.RemoveAt(HoldCore.Length + HoldCompanions.Length + HoldAudioTutorials.Length + HoldCityFaction.Length + HoldGenericDialogue.Length + HoldActivities.Length + HoldRadiant.Length + Array.IndexOf(HoldShips, "DialogueShipServices"))),
            ("the hold list lost MB_Parent", m => ((SF.ScriptObjectListProperty)m.Quests.First().VirtualMachineAdapter!.Scripts[0].Properties.First(p => p.Name == "HoldOff")).Objects.RemoveAt(HoldCore.Length + HoldCompanions.Length + HoldAudioTutorials.Length + HoldCityFaction.Length + HoldGenericDialogue.Length + HoldActivities.Length + Array.IndexOf(HoldRadiant, "MB_Parent"))),
            ("the hold list lost DialogueCrowds", m => ((SF.ScriptObjectListProperty)m.Quests.First().VirtualMachineAdapter!.Scripts[0].Properties.First(p => p.Name == "HoldOff")).Objects.RemoveAt(HoldCore.Length + HoldCompanions.Length + HoldAudioTutorials.Length + HoldCityFaction.Length + Array.IndexOf(HoldGenericDialogue, "DialogueCrowds"))),
            ("the hold list lost SQ_Doctors", m => ((SF.ScriptObjectListProperty)m.Quests.First().VirtualMachineAdapter!.Scripts[0].Properties.First(p => p.Name == "HoldOff")).Objects.RemoveAt(HoldCore.Length + HoldCompanions.Length + HoldAudioTutorials.Length + HoldCityFaction.Length + HoldGenericDialogue.Length + Array.IndexOf(HoldActivities, "SQ_Doctors"))),
            ("the hold list lost DialogueCydonia", m => ((SF.ScriptObjectListProperty)m.Quests.First().VirtualMachineAdapter!.Scripts[0].Properties.First(p => p.Name == "HoldOff")).Objects.RemoveAt(HoldCore.Length + HoldCompanions.Length + HoldAudioTutorials.Length + Array.IndexOf(HoldCityFaction, "DialogueCydonia"))),
            ("the hold list lost OutpostTutorial", m => ((SF.ScriptObjectListProperty)m.Quests.First().VirtualMachineAdapter!.Scripts[0].Properties.First(p => p.Name == "HoldOff")).Objects.RemoveAt(HoldCore.Length + HoldCompanions.Length + Array.IndexOf(HoldAudioTutorials, "OutpostTutorial"))),
            ("the hold list lost SQ_Companions", m => ((SF.ScriptObjectListProperty)m.Quests.First().VirtualMachineAdapter!.Scripts[0].Properties.First(p => p.Name == "HoldOff")).Objects.RemoveAt(HoldCore.Length + Array.IndexOf(HoldCompanions, "SQ_Companions"))),
            ("the hold list lost SQ_ENV", m => ((SF.ScriptObjectListProperty)m.Quests.First().VirtualMachineAdapter!.Scripts[0].Properties.First(p => p.Name == "HoldOff")).Objects.RemoveAt(4)),
            ("the O2 capacity amount changed", m => ((SF.ScriptFloatProperty)m.Quests.First().VirtualMachineAdapter!.Scripts[0].Properties.First(p => p.Name == "O2CapacityAmount")).Data = 50f),
            ("the O2 capacity linked to Oxygen", m => ((SF.ScriptObjectProperty)m.Quests.First().VirtualMachineAdapter!.Scripts[0].Properties.First(p => p.Name == "O2Capacity")).Object = new FormLink<SF.IStarfieldMajorRecordGetter>(new FormKey(SfEsm, 0x0002D5))),
            ("O2Capacity removed", m => m.Quests.First().VirtualMachineAdapter!.Scripts[0].Properties.RemoveAll(p => p.Name == "O2Capacity")),
            ("a MQ101Debug override added at the first build's 10", m => m.Globals.Add(new SF.Global(new FormKey(SfEsm, 0x900), rel) { EditorID = DebugGlobEdid, Data = 10 })),
            ("a MQ101Debug override added at the second build's 2", m => m.Globals.Add(new SF.Global(new FormKey(SfEsm, 0x900), rel) { EditorID = DebugGlobEdid, Data = 2 })),
            ("the version GLOB reads another value", m => m.Globals.First(g => g.EditorID == VersionGlobEdid).Data = 7),
            ("the version GLOB not constant", m => m.Globals.First(g => g.EditorID == VersionGlobEdid).MajorFlags = 0),
            ("the version GLOB removed", m => m.Globals.Remove(m.Globals.First(g => g.EditorID == VersionGlobEdid).FormKey)),
            ("the player alias removed", m => m.Quests.First().Aliases!.Clear()),
            ("the player alias forced to another reference", m => ((SF.QuestReferenceAlias)m.Quests.First().Aliases![0]).ForcedReference.SetTo(new FormKey(SfEsm, 0x902))),
            ("a second alias", m => m.Quests.First().Aliases!.Add(new SF.QuestReferenceAlias { ID = 1, Name = "Other" })),
            ("the alias script unbound", m => m.Quests.First().VirtualMachineAdapter!.Aliases.Clear()),
            ("the alias script bound to another alias", m => m.Quests.First().VirtualMachineAdapter!.Aliases[0].Property.Alias = 1),
            ("the alias script lost BuildVersion", m => m.Quests.First().VirtualMachineAdapter!.Aliases[0].Scripts[0].Properties.Clear()),
            ("the alias script renamed", m => m.Quests.First().VirtualMachineAdapter!.Aliases[0].Scripts[0].Name = "Other"),
            ("the elevator prompt has one button", m => m.Messages.First(x => x.EditorID == MessageEdid).MenuButtons.RemoveAt(1)),
            ("the opening choice has one button", m => m.Messages.First(x => x.EditorID == StartMessageEdid).MenuButtons.RemoveAt(1)),
            ("the opening choice button order swapped", m => { var sm = m.Messages.First(x => x.EditorID == StartMessageEdid); (sm.MenuButtons[0], sm.MenuButtons[1]) = (sm.MenuButtons[1], sm.MenuButtons[0]); }),
            ("the opening choice titled Vault 111", m => m.Messages.First(x => x.EditorID == StartMessageEdid).Name = "Vault 111"),
            ("the opening choice removed", m => m.Messages.Remove(m.Messages.First(x => x.EditorID == StartMessageEdid).FormKey)),
            ("the race menu mode changed", m => ((SF.ScriptIntProperty)m.Quests.First().VirtualMachineAdapter!.Scripts[1].Properties.First(p => p.Name == "RaceMenuMode")).Data = 3),
            ("the looks script lost StartMessage", m => m.Quests.First().VirtualMachineAdapter!.Scripts[1].Properties.RemoveAll(p => p.Name == "StartMessage")),
            ("the quest has no QuestType", m => m.Quests.First().QuestType.Clear()),
            ("a duplicate AVIF added", m => m.ActorValueInformation.Add(new SF.ActorValueInformation(new FormKey(m.ModKey, 0x810), rel) { EditorID = SpecialAvifPrefix + "Strength" })),
            ("a SPECIAL link pointed off FO4SFCoreValues.esm", m => ((SF.ScriptObjectListProperty)m.Quests.First().VirtualMachineAdapter!.Scripts[2].Properties.First(p => p.Name == "Special")).Objects[0].Object.SetTo(new FormKey(m.ModKey, 0x810))),
            ("a SPECIAL link removed", m => ((SF.ScriptObjectListProperty)m.Quests.First().VirtualMachineAdapter!.Scripts[2].Properties.First(p => p.Name == "Special")).Objects.RemoveAt(6)),
            ("TestModeGlobal removed", m => m.Quests.First().VirtualMachineAdapter!.Scripts[0].Properties.RemoveAll(p => p.Name == "TestModeGlobal")),
            ("TestModeGlobal pointed at another global", m => ((SF.ScriptObjectProperty)m.Quests.First().VirtualMachineAdapter!.Scripts[0].Properties.First(p => p.Name == "TestModeGlobal")).Object.SetTo(new FormKey(SfEsm, GameDaysPassedId))),
            ("the allocation lost its Leave button", m => m.Messages.First(x => x.EditorID == SpecialMessageEdid).MenuButtons.RemoveAt(6)),
            ("a message box with more than 7 buttons", m => m.Messages.First(x => x.EditorID == SpecialMessageEdid).MenuButtons.Add(new SF.MessageButton { Text = "Extra8" })),
            ("the allocation page 2 lost a button", m => m.Messages.First(x => x.EditorID == SpecialMessagePage2Edid).MenuButtons.RemoveAt(6)),
            ("the allocation's text lost a token", m => m.Messages.First(x => x.EditorID == SpecialMessageEdid).Description = "S.P.E.C.I.A.L."),
            ("the terminal prompt removed", m => m.Messages.Remove(m.Messages.First(x => x.EditorID == TerminalMessageEdid).FormKey)),
            ("the SPECIAL list order swapped", m => { var l = (SF.ScriptObjectListProperty)m.Quests.First().VirtualMachineAdapter!.Scripts[2].Properties.First(p => p.Name == "Special"); (l.Objects[0], l.Objects[6]) = (l.Objects[6], l.Objects[0]); }),
            ("the terminal id changed", m => ((SF.ScriptIntProperty)m.Quests.First().VirtualMachineAdapter!.Scripts[2].Properties.First(p => p.Name == "TerminalId")).Data = 0x807),
            ("the terminal spot changed", m => ((SF.ScriptFloatProperty)m.Quests.First().VirtualMachineAdapter!.Scripts[2].Properties.First(p => p.Name == "TerminalX")).Data += 1),
            ("the inventory reset switched off", m => ((SF.ScriptBoolProperty)m.Quests.First().VirtualMachineAdapter!.Scripts[0].Properties.First(p => p.Name == "ClearInventory")).Data = false),
            ("a vault suit id without the option", m => ((SF.ScriptIntProperty)m.Quests.First().VirtualMachineAdapter!.Scripts[0].Properties.First(p => p.Name == "VaultSuitId")).Data = 0x820),
            ("ClearInventory removed", m => m.Quests.First().VirtualMachineAdapter!.Scripts[0].Properties.RemoveAll(p => p.Name == "ClearInventory")),
            ("the anchor marked temporary on a persistent one", m => ((SF.ScriptBoolProperty)m.Quests.First().VirtualMachineAdapter!.Scripts[0].Properties.First(p => p.Name == "AnchorTemporary")).Data = true),
            ("AnchorTemporary removed", m => m.Quests.First().VirtualMachineAdapter!.Scripts[0].Properties.RemoveAll(p => p.Name == "AnchorTemporary")),
            ("the vault cell renamed", m => ((SF.ScriptStringProperty)m.Quests.First().VirtualMachineAdapter!.Scripts[0].Properties.First(p => p.Name == "VaultCell")).Data = "FO4Port_Vault111Ent"),
            ("VaultCell removed", m => m.Quests.First().VirtualMachineAdapter!.Scripts[0].Properties.RemoveAll(p => p.Name == "VaultCell")),
            ("the return prompt lost a button", m => m.Messages.First(x => x.EditorID == ReturnMsgEdid).MenuButtons.RemoveAt(1)),
            ("the exit fallback prompt lost a button", m => m.Messages.First(x => x.EditorID == ExitFallbackMsgEdid).MenuButtons.RemoveAt(1)),
            ("retired GLOB 0x80C added", m => m.Globals.Add(new SF.Global(new FormKey(m.ModKey, 0x80C), rel) { EditorID = PipboyAcquiredGlobEdid })),
            ("retired FormID 0x811 reused", m => m.Messages.Add(new SF.Message(new FormKey(m.ModKey, 0x811), rel) { EditorID = "FO4SF_Retired811", Flags = SF.Message.Flag.MessageBox })),
            ("PipboyAcquiredGlobal pointed off FO4SFCoreValues.esm", m => ((SF.ScriptObjectProperty)m.Quests.First().VirtualMachineAdapter!.Scripts[0].Properties.First(p => p.Name == "PipboyAcquiredGlobal")).Object.SetTo(new FormKey(SfEsm, GameDaysPassedId))),
            ("PipboyWrist marked NonPlayable", m => m.Armors.First(a => a.EditorID == PipboyWristArmorEdid).MajorRecordFlagsRaw |= 0x4),
            ("PipboyCorpseRef made temporary", m => { var c = m.Cells.Records[0].SubBlocks[0].Cells[0]; var r = (SF.PlacedObject)c.Persistent.First(x => x.EditorID == PipboyCorpseRefEdid); r.MajorRecordFlagsRaw &= ~0x400; }),
            ("GearDoorConsoleRef made temporary", m => { var c = m.Cells.Records[0].SubBlocks[0].Cells[0]; var r = (SF.PlacedObject)c.Persistent.First(x => x.EditorID == GearDoorConsoleRefEdid); r.MajorRecordFlagsRaw &= ~0x400; }),
            ("GearDoorConsoleActi lost its name", m => m.Activators.First(a => a.EditorID == GearDoorConsoleActiEdid).Name = ""),
            ("VaultPistolBase pointed at another form", m => ((SF.ScriptObjectProperty)m.Quests.First().VirtualMachineAdapter!.Scripts[0].Properties.First(p => p.Name == "VaultPistolBase")).Object.SetTo(new FormKey(SfEsm, SfFallbackJumpsuitId))),
            ("Vault111 temporary pistol removed", m => { var c = m.Cells.Records[0].SubBlocks[0].Cells[0]; c.Temporary.Remove(c.Temporary.First(x => x.EditorID == VaultPistolRefEdid)); }),
            ("Vault111 temporary ammo count changed", m => { var c = m.Cells.Records[0].SubBlocks[0].Cells[0]; ((SF.PlacedObject)c.Temporary.First(x => x.EditorID == VaultAmmoRefEdid)).Count = 12; }),
            ("ConsoleRefId changed", m => ((SF.ScriptIntProperty)m.Quests.First().VirtualMachineAdapter!.Scripts[0].Properties.First(p => p.Name == "ConsoleRefId")).Data = 0x999),
        };
        foreach (var (name, edit) in mutations)
        {
            var mod = SF.StarfieldMod.CreateFromBinary(good, rel, Full(SfEsm, PortEsm, CoreValuesEsm));
            edit(mod);
            var md = Path.Combine(outDir, "mutated");
            Directory.CreateDirectory(md);
            WritePlugin(mod, Path.Combine(md, Plugin));
            if (Check(Path.Combine(md, Plugin), sfPath, portPath, idsPath, corePath, pointsPath, plain) == 0) { Console.WriteLine($"FAIL  check passed a mutation: {name}"); return 1; }
            Console.WriteLine($"mutation rejected: {name}");
        }
        // refusals: references that sit in our cell or world but are owned by another plugin (same local id), and a
        // port under another file name; the owned inputs above are the positive case
        {
            var fdir = Path.Combine(dir, "foreign");
            Directory.CreateDirectory(fdir);
            string Port(Action<SF.StarfieldMod> edit, string file = "FO4Port.esm")
            {
                var m = SF.StarfieldMod.CreateFromBinary(portPath, rel, Full(SfEsm));
                edit(m);
                var d = Path.Combine(fdir, Guid.NewGuid().ToString("N"));
                Directory.CreateDirectory(d);
                var path = Path.Combine(d, file);
                m.BeginWrite.ToPath(path).WithLoadOrder(SfEsm).WithKnownMasters(new KeyedMasterStyle(SfEsm, MasterStyle.Full)).NoModKeySync().Write();
                return path;
            }
            SF.Cell VCell(SF.StarfieldMod m) => m.Cells.Records[0].SubBlocks[0].Cells[0];
            SF.PlacedObject Rekey(SF.PlacedObject r, FormKey k) => (SF.PlacedObject)r.Duplicate(k);
            var liftPlaces = Resolve(portPath, idsPath, corePath, ExitAnchorEdid, terms, animatedExitLift: true);
            if (liftPlaces.Lift != 0x809 || liftPlaces.LiftBase != 0x811) { Console.WriteLine("FAIL lift identity"); return 1; }
            var missingLift = Port(m => VCell(m).Temporary.Remove(VCell(m).Temporary.First(x => x.FormKey.ID == 0x809)));
            var wrongLift = Port(m => ((SF.PlacedObject)VCell(m).Temporary.First(x => x.FormKey.ID == 0x809)).Base.SetTo(pdoor.FormKey));
            var scaledLift = Port(m => ((SF.PlacedObject)VCell(m).Temporary.First(x => x.FormKey.ID == 0x809)).Scale = 2f);
            var tiltedLift = Port(m => ((SF.PlacedObject)VCell(m).Temporary.First(x => x.FormKey.ID == 0x809)).Rotation = new P3Float(0.1f, 0, 0));
            foreach (var badLift in new[] { missingLift, wrongLift, scaledLift, tiltedLift })
            {
                try { Resolve(badLift, idsPath, corePath, ExitAnchorEdid, terms, animatedExitLift: true); Console.WriteLine("FAIL accepted bad lift"); return 1; }
                catch (Refusal) { }
            }
            foreach (var badIds in new[] { noCogIds, nearTermIds })
            {
                try { Resolve(portPath, badIds, corePath, ExitAnchorEdid, terms, animatedExitLift: true); Console.WriteLine("FAIL accepted absent lift mapping"); return 1; }
                catch (Refusal) { }
            }
            var foreignCoc = Port(m => { var c = VCell(m); var r = (SF.PlacedObject)c.Temporary.First(x => x.FormKey.ID == 0x801); c.Temporary.Remove(r); c.Temporary.Add(Rekey(r, new FormKey(SfEsm, 0x801))); });
            var foreignCog = Port(m => { var c = VCell(m); var r = (SF.PlacedObject)c.Temporary.First(x => x.FormKey.ID == 0x802); c.Temporary.Remove(r); c.Temporary.Add(Rekey(r, new FormKey(SfEsm, 0x802))); });
            var renamed = Port(m => { }, "FO4PortB.esm");
            var cm = SF.StarfieldMod.CreateFromBinary(corePath, rel, Full(SfEsm));
            var top = cm.Worldspaces.First().TopCell!;
            var mk = (SF.PlacedObject)top.Persistent.First();
            top.Persistent.Remove(mk);
            top.Persistent.Add(Rekey(mk, new FormKey(SfEsm, 0xA775B)));
            var cd = Path.Combine(fdir, "core");
            Directory.CreateDirectory(cd);
            var foreignCore = Path.Combine(cd, coreKey.FileName);
            cm.BeginWrite.ToPath(foreignCore).WithLoadOrder(SfEsm).WithKnownMasters(new KeyedMasterStyle(SfEsm, MasterStyle.Full)).Write();
            var foreignTerm = Port(m => { var c = VCell(m); var r = (SF.PlacedObject)c.Persistent.First(x => x.FormKey.ID == 0x808); c.Persistent.Remove(r); c.Persistent.Add(Rekey(r, new FormKey(SfEsm, 0x808))); });
            var lostTerm = Port(m => { var c = VCell(m); c.Persistent.Remove(c.Persistent.First(x => x.FormKey.ID == 0x808)); });
            foreach (var (why, p, c) in new[] { ("a COC marker owned by Starfield.esm", foreignCoc, corePath), ("a cog door owned by Starfield.esm", foreignCog, corePath),
                                                ("a port under another file name", renamed, corePath), ("an exit anchor owned by Starfield.esm", portPath, foreignCore),
                                                ("a terminal owned by Starfield.esm", foreignTerm, corePath), ("a terminal formids.json names but the cell lacks", lostTerm, corePath) })
            {
                try { Resolve(p, idsPath, c, ExitAnchorEdid, terms); Console.WriteLine($"FAIL  resolve accepted {why}"); return 1; }
                catch (Refusal e) { Console.WriteLine($"refused as expected ({why}): {e.Message}"); }
            }
            // the vault anchor prefers persistence: a temporary COC marker gives way to the nearest persistent reference
            // of the port in the cell; a persistent COC marker is used itself; none at all (the port installed on 21 Oct)
            // is refused by default and, under --allow-temporary-anchor, anchors on the temporary COC marker with
            // AnchorTemporary set
            var full0 = Resolve(portPath, idsPath, corePath, ExitAnchorEdid, terms);
            if (full0.VaultAnchor != 0x805 || full0.AnchorTemporary || full0.AnchorMode != "persistent") { Console.WriteLine("FAIL  the anchor is not the nearest persistent reference"); return 1; }
            var persCoc = Port(m => { var c = VCell(m); var r = (SF.PlacedObject)c.Temporary.First(x => x.FormKey.ID == 0x801); c.Temporary.Remove(r); r.MajorRecordFlagsRaw |= 0x400; c.Persistent.Add(r); });
            var pc = Resolve(persCoc, idsPath, corePath, ExitAnchorEdid, terms);
            if (pc.VaultAnchor != 0x801 || pc.AnchorTemporary) { Console.WriteLine("FAIL  a persistent COC marker is not the anchor"); return 1; }
            // the installed port's shape (PC 21 Oct): every reference of the cell temporary, the terminals among them
            var noPers = Port(m => { var c = VCell(m); foreach (var r in c.Persistent.ToList()) { var t = (SF.PlacedObject)r; t.MajorRecordFlagsRaw &= ~0x400; c.Temporary.Add(t); } c.Persistent.Clear(); });
            var tmp = Resolve(noPers, idsPath, corePath, ExitAnchorEdid, terms, requirePersistentAnchor: false);
            if (tmp.Terminal != 0x807) { Console.WriteLine($"FAIL  the temporary-only port's terminal is not the nearer one: {tmp.Terminal:X}"); return 1; }
            if (tmp.VaultAnchor != 0x801 || !tmp.AnchorTemporary || tmp.AnchorMode != "temporary" || MathF.Abs(tmp.AnchorPos.X - 60f) > 1e-3) { Console.WriteLine($"FAIL  a vault with no persistent reference is not anchored on its temporary COC marker: {tmp.VaultAnchor:X} {tmp.AnchorMode}"); return 1; }
            try { Resolve(noPers, idsPath, corePath, ExitAnchorEdid, terms); Console.WriteLine("FAIL  resolve accepted a vault with no persistent reference by default"); return 1; }
            catch (Refusal e) { Console.WriteLine($"refused as expected (no persistent reference in the vault, the default): {e.Message}"); }
            // the temporary-anchor build (--allow-temporary-anchor): written and checked against that port (its check
            // line says "temporary"); it fails the check against the port with persistent references and the default
            // build fails against the port without (another anchor id and the other mode); the default refuses to write it
            {
                var td = Path.Combine(outDir, "tempanchor");
                var tw = new StringWriter();
                var stdout = Console.Out;
                Console.SetOut(tw);
                try
                {
                    rc = Write(sfPath, noPers, idsPath, corePath, pointsPath, td, allowTemp);
                    if (rc == 0) rc = Check(Path.Combine(td, Plugin), sfPath, noPers, idsPath, corePath, pointsPath, allowTemp);
                }
                finally { Console.SetOut(stdout); }
                Console.Write(tw.ToString());
                if (rc != 0) { Console.WriteLine("FAIL  the temporary-anchor build"); return 1; }
                if (!tw.ToString().Contains("vault anchor FO4Port.esm:000801 temporary at") || !tw.ToString().Contains("  vault anchor FO4Port.esm:000801 temporary, cog door")) { Console.WriteLine("FAIL  write and check do not print the temporary anchor mode"); return 1; }
                if (Check(Path.Combine(td, Plugin), sfPath, portPath, idsPath, corePath, pointsPath, allowTemp) == 0) { Console.WriteLine("FAIL  check passed a temporary-anchor build against a port with persistent references"); return 1; }
                Console.WriteLine("rejected: a temporary-anchor build against a port with persistent references");
                if (Check(Path.Combine(outDir, "default", Plugin), sfPath, noPers, idsPath, corePath, pointsPath, allowTemp) == 0) { Console.WriteLine("FAIL  check passed a persistent-anchor build against a port without a persistent reference"); return 1; }
                Console.WriteLine("rejected: a persistent-anchor build against a port without a persistent reference");
                try { Write(sfPath, noPers, idsPath, corePath, pointsPath, Path.Combine(outDir, "refused"), plain); Console.WriteLine("FAIL  write accepted a temporary anchor by default"); return 1; }
                catch (Refusal e) { Console.WriteLine($"refused as expected (a temporary anchor, the default): {e.Message}"); }
                // the option changes nothing in a build whose anchor is persistent: the default build passes under it
                if (Check(Path.Combine(outDir, "default", Plugin), sfPath, portPath, idsPath, corePath, pointsPath, allowTemp) != 0) { Console.WriteLine("FAIL  the default build fails under --allow-temporary-anchor"); return 1; }
            }
            // the terminal: the persistent one is preferred over the nearer temporary one; with only the temporary
            // one it is taken; with none the id is 0 and the spot is the nearest terminal's; --terminal-ref pins one
            var full = Resolve(portPath, idsPath, corePath, ExitAnchorEdid, terms);
            if (full.Terminal != 0x808 || full.TerminalSrc != 0x1003 || MathF.Abs(full.TerminalPos.X - 42.857f) > 1e-3) { Console.WriteLine($"FAIL  the terminal is not the persistent one: {full.Terminal:X} {full.TerminalSrc:X}"); return 1; }
            var near = Resolve(portPath, nearTermIds, corePath, ExitAnchorEdid, terms);
            if (near.Terminal != 0x807 || near.TerminalSrc != 0x1002) { Console.WriteLine("FAIL  the only carried terminal is not taken"); return 1; }
            var none = Resolve(portPath, noCogIds, corePath, ExitAnchorEdid, terms);
            if (none.Terminal != 0 || none.TerminalSrc != 0x1002 || MathF.Abs(none.TerminalPos.X - 11f) > 1e-3) { Console.WriteLine("FAIL  a port without a terminal"); return 1; }
            var pinned = Resolve(portPath, idsPath, corePath, ExitAnchorEdid, Terminals(JsonDocument.Parse(File.ReadAllText(oneTerm)).RootElement));
            if (pinned.Terminal != 0x808 || Resolve(portPath, nearTermIds, corePath, ExitAnchorEdid, pinned.Terminal == 0x808 ? Terminals(JsonDocument.Parse(File.ReadAllText(oneTerm)).RootElement) : terms).Terminal != 0)
                { Console.WriteLine("FAIL  --terminal-ref"); return 1; }
            if (!IsRefKey($"REFR:{VaultCell}:001002:Fallout4.esm", 0x1002) || IsRefKey($"REFR:{VaultCell}:001002:Fallout4.esm", 0x1003)) { Console.WriteLine("FAIL  IsRefKey"); return 1; }
            // the vault suit (--vault-suit): the port's one ARMO of that EditorID, any case; none, two, another plugin's
            // record or no option at all give 0 or a refusal
            if (Resolve(portPath, idsPath, corePath, ExitAnchorEdid, terms, SuitEdid).VaultSuit != 0x820 || Resolve(portPath, idsPath, corePath, ExitAnchorEdid, terms, SuitEdid.ToUpperInvariant()).VaultSuit != 0x820 ||
                Resolve(portPath, idsPath, corePath, ExitAnchorEdid, terms).VaultSuit != 0) { Console.WriteLine("FAIL  the vault suit"); return 1; }
            var twoSuits = Port(m => m.Armors.Add(new SF.Armor(new FormKey(portKey, 0x821), rel) { EditorID = SuitEdid }));
            var foreignSuit = Port(m => { var s = m.Armors.First(); m.Armors.Remove(s.FormKey); m.Armors.Add((SF.Armor)s.Duplicate(new FormKey(SfEsm, 0x820))); });
            foreach (var (why, p, edid) in new[] { ("a vault suit the port lacks", portPath, "FO4Port_NoSuchSuit"), ("two vault suits of that EditorID", twoSuits, SuitEdid), ("a vault suit owned by Starfield.esm", foreignSuit, SuitEdid) })
            {
                try { Resolve(p, idsPath, corePath, ExitAnchorEdid, terms, edid); Console.WriteLine($"FAIL  resolve accepted {why}"); return 1; }
                catch (Refusal e) { Console.WriteLine($"refused as expected ({why}): {e.Message}"); }
            }
        }
        // refusals: a --vault-suit build whose suit the port lacks (write resolves it as it does the anchors)
        try { Write(sfPath, portPath, idsPath, corePath, pointsPath, Path.Combine(outDir, "refused"), plain with { VaultSuit = "FO4Port_NoSuchSuit" }); Console.WriteLine("FAIL  write accepted a vault suit the port lacks"); return 1; }
        catch (Refusal e) { Console.WriteLine($"refused as expected (a vault suit the port lacks): {e.Message}"); }
        // refusals: a SPECIAL build from a points.json without a terminal (a --no-special one builds)
        {
            var noTerm = JsonSerializer.Deserialize<Dictionary<string, JsonElement>>(File.ReadAllText(pointsPath))!;
            noTerm["terminals"] = JsonDocument.Parse("[]").RootElement;
            var noTermPath = Path.Combine(dir, "points_noterm.json");
            File.WriteAllText(noTermPath, JsonSerializer.Serialize(noTerm));
            try { Write(sfPath, portPath, idsPath, corePath, noTermPath, Path.Combine(outDir, "refused"), plain); Console.WriteLine("FAIL  write accepted a SPECIAL build without a terminal"); return 1; }
            catch (Refusal e) { Console.WriteLine($"refused as expected (no terminal): {e.Message}"); }
            var od = Path.Combine(outDir, "noterm_nospecial");
            var ns = plain with { Special = false };
            if (Write(sfPath, portPath, idsPath, corePath, noTermPath, od, ns) != 0 || Check(Path.Combine(od, Plugin), sfPath, portPath, idsPath, corePath, noTermPath, ns) != 0) { Console.WriteLine("FAIL  a --no-special build without a terminal"); return 1; }
        }
        // refusals: a Starfield.esm without StartupQuest_DO, or with one naming another quest than MQ101; check refuses the
        // default build against the second too
        foreach (var (why, sfp) in new[] { ("a Starfield.esm without StartupQuest_DO", sfNoStartup), ("a Starfield.esm whose StartupQuest_DO names MQ00", sfOtherStartup),
                                           ("a Starfield.esm whose StartupQuest_DO is not 00562D", sfMovedStartup) })
        {
            try { Write(sfp, portPath, idsPath, corePath, pointsPath, Path.Combine(outDir, "refused"), plain); Console.WriteLine($"FAIL  write accepted {why}"); return 1; }
            catch (Refusal e) { Console.WriteLine($"refused as expected ({why}): {e.Message}"); }
        }
        if (Check(good, sfOtherStartup, portPath, idsPath, corePath, pointsPath, plain) == 0) { Console.WriteLine("FAIL  check passed against a Starfield.esm whose StartupQuest_DO names MQ00"); return 1; }
        Console.WriteLine("rejected: the default build against a Starfield.esm whose StartupQuest_DO names MQ00");
        // refusals: a hold quest Starfield lacks, an exit anchor the core lacks
        foreach (var (why, o) in new[] { ("an unknown hold quest", plain with { Hold = new[] { "MQ999" } }), ("an unknown exit anchor", plain with { ExitAnchor = "NoSuchMarker" }) })
        {
            try { Write(sfPath, portPath, idsPath, corePath, pointsPath, Path.Combine(outDir, "refused"), o); Console.WriteLine($"FAIL  write accepted {why}"); return 1; }
            catch (Refusal e) { Console.WriteLine($"refused as expected ({why}): {e.Message}"); }
        }
        // S3 refusal: warfare_starts.json naming a marker_edid missing from FO4TerrainCore.esm must fail at build time
        {
            var badWfPath = Path.Combine(dir, "bad_warfare_starts.json");
            File.WriteAllText(badWfPath, File.ReadAllText(DefaultWarfareStartsJsonPath()).Replace("FO4Core_CommonwealthMapMarkerSanctuary", "FO4Core_NoSuchWarfareMarker"));
            try { Write(sfPath, portPath, idsPath, corePath, pointsPath, Path.Combine(outDir, "refused_wf"), plain with { WarfareStartsJson = badWfPath }); Console.WriteLine("FAIL  write accepted unknown warfare marker_edid"); return 1; }
            catch (Refusal e) { Console.WriteLine($"refused as expected (unknown warfare marker_edid): {e.Message}"); }
        }
        // B4 refusal: missing gear-door console mapping in formids.json must fail Resolve, Write, and Check
        {
            try { Resolve(portPath, noConsoleIds, corePath, ExitAnchorEdid, terms); Console.WriteLine("FAIL  resolve accepted missing gear-door console mapping"); return 1; }
            catch (Refusal e) { Console.WriteLine($"refused as expected (missing gear-door console mapping in Resolve): {e.Message}"); }
            try { Write(sfPath, portPath, noConsoleIds, corePath, pointsPath, Path.Combine(outDir, "refused_noconsole"), plain); Console.WriteLine("FAIL  write accepted missing gear-door console mapping"); return 1; }
            catch (Refusal e) { Console.WriteLine($"refused as expected (missing gear-door console mapping in Write): {e.Message}"); }
            try { Check(good, sfPath, portPath, noConsoleIds, corePath, pointsPath, plain); Console.WriteLine("FAIL  check accepted missing gear-door console mapping"); return 1; }
            catch (Refusal e) { Console.WriteLine($"refused as expected (missing gear-door console mapping in Check): {e.Message}"); }
        }
        // B5 refusal: route_loot_ids.json naming an unknown weapon in Starfield.esm must fail at build time
        {
            var badRlPath = Path.Combine(dir, "bad_route_loot_ids.json");
            File.WriteAllText(badRlPath, "{\"schema_version\": 1, \"vault111\": {\"pistol_id\": \"0x3FFFFF\"}}");
            try { Write(sfPath, portPath, idsPath, corePath, pointsPath, Path.Combine(outDir, "refused_rl"), plain with { RouteLootJson = badRlPath }); Console.WriteLine("FAIL  write accepted unknown vault111.pistol_id"); return 1; }
            catch (Refusal e) { Console.WriteLine($"refused as expected (unknown vault111.pistol_id): {e.Message}"); }
        }
        // N2: title_card backdrop variant + start_places.json refusal when an unbuilt plugin or missing marker is marked available=true
        {
            var tcDir = Path.Combine(outDir, "titlecard");
            var tcOpt = plain with { StartChoiceBackdrop = BackdropTitleCard };
            if (Write(sfPath, portPath, idsPath, corePath, pointsPath, tcDir, tcOpt) != 0 ||
                Check(Path.Combine(tcDir, Plugin), sfPath, portPath, idsPath, corePath, pointsPath, tcOpt) != 0 ||
                Check(Path.Combine(tcDir, Plugin), sfPath, portPath, idsPath, corePath, pointsPath, plain) == 0)
            { Console.WriteLine("FAIL  title_card backdrop variant"); return 1; }
            var badSpPlugin = Path.Combine(dir, "bad_start_places_plugin.json");
            File.WriteAllText(badSpPlugin, File.ReadAllText(DefaultStartPlacesJsonPath()).Replace("\"available\": false", "\"available\": true"));
            try { Write(sfPath, portPath, idsPath, corePath, pointsPath, Path.Combine(outDir, "refused_sp"), plain with { StartPlacesJson = badSpPlugin }); Console.WriteLine("FAIL  write accepted unbuilt start_places plugin"); return 1; }
            catch (Refusal e) { Console.WriteLine($"refused as expected (unbuilt start_places plugin): {e.Message}"); }
            var badSpMarker = Path.Combine(dir, "bad_start_places_marker.json");
            File.WriteAllText(badSpMarker, File.ReadAllText(DefaultStartPlacesJsonPath()).Replace("FO4Core_CommonwealthMapMarkerSanctuary", "FO4Core_NoSuchStartPlaceMarker"));
            try { Write(sfPath, portPath, idsPath, corePath, pointsPath, Path.Combine(outDir, "refused_sp2"), plain with { StartPlacesJson = badSpMarker }); Console.WriteLine("FAIL  write accepted missing start_places marker"); return 1; }
            catch (Refusal e) { Console.WriteLine($"refused as expected (missing start_places marker): {e.Message}"); }
        }
        // T4: synthetic Starfield.esm without 0x24561C builds and passes Check with 0 temporary vault pickups
        {
            var sfAltPistol = SfVariant("sf_no_24561c", m =>
            {
                m.Weapons.Clear();
                m.Weapons.Add(new SF.Weapon(new FormKey(SfEsm, 0x2773C8), rel) { EditorID = "AltSynthWeapon" });
            });
            var altRlPath = Path.Combine(dir, "alt_route_loot_ids.json");
            File.WriteAllText(altRlPath, "{\"schema_version\": 1, \"vault111\": {\"pistol_id\": \"0x2773C8\"}}");
            var altWfPath = Path.Combine(dir, "alt_warfare_starts.json");
            File.WriteAllText(altWfPath, File.ReadAllText(DefaultWarfareStartsJsonPath()).Replace("0x24561C", "0x2773C8"));
            var altDir = Path.Combine(outDir, "no24561c");
            var altOpt = plain with { RouteLootJson = altRlPath, WarfareStartsJson = altWfPath };
            if (Write(sfAltPistol, portPath, idsPath, corePath, pointsPath, altDir, altOpt) != 0 ||
                Check(Path.Combine(altDir, Plugin), sfAltPistol, portPath, idsPath, corePath, pointsPath, altOpt) != 0)
            { Console.WriteLine("FAIL  synthetic Starfield.esm without 0x24561C"); return 1; }
        }
        // the records reader (Records.cs): its own synthetic plugins, under this scratch dir
        if (NewGameRecords.SelfTest(Path.Combine(dir, "records")) != 0) return 1;
        Console.WriteLine("selftest pass");
        return 0;
    }
}
