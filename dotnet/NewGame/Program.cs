// NewGame: a Fallout 4 new game in Starfield (docs/newgame/vault111-start.md): one plugin, FO4SFNewGame.esm, whose
// start-game-enabled quest holds off Starfield's opening, puts the player at their cryo pod in the converted Vault 111
// (FO4Port.esm) and takes them up the elevator onto the Commonwealth (FO4TerrainCore.esm). Claude's project.
//
//   points <Fallout4.esm> <out points.json> [--pod-ref <hex>] [--pod-step 1.0] [--terminal-ref <hex>]
//        reads Fallout 4 only: in Vault111Cryo (000016D8) the player's cryo pod (the one placed reference whose
//        EditorID names both the player and a pod, or --pod-ref), the cog door console MQ102GearDoorConsoleREF 00091A49,
//        the cog door Vault111GearDoorREF 000330C3, the elevator platform V111ElevatorREF 000244EB, the surface
//        arrival of the ride (the XTEL of Vault111InteriorAutoLoadDoorREF 0001F180), and the cell's terminals (every
//        placed reference of a TERM, nearest the pod first, or --terminal-ref alone: the SPECIAL terminal, NG-C4);
//        MQ102's name. Interior positions in metres in the port's frame and exterior ones in the core's (both FO4
//        position / 70); headings in degrees.
//   write <Starfield.esm> <FO4Port.esm> <port formids.json> <FO4TerrainCore.esm> <points.json> <out dir>
//         [--plugin FO4SFNewGame.esm] [--hold MQ00,MQ101,MQ101PostQuest,MQ_TutorialQuest_Misc04] [--mq101debug <n>]
//         [--no-mq101debug] [--no-looks] [--race-menu-mode <n>] [--no-special] [--no-version] [--build-version <n>]
//         [--exit-anchor <REFR EditorID>] [--clear-inventory [--vault-suit <ARMO EditorID>]]
//        the plugin, mastered on Starfield.esm only: QUST FO4SF_NewGame (start game enabled, run once; stages 1 / 10 /
//        20 / 30 / 40 / 200, the published stage contract of make_newgame.py STAGE_CONTRACT; objective 10) carrying
//        FO4SF_NewGameQuest (and FO4SF_NewGameLooks unless --no-looks, FO4SF_NewGameSpecial unless --no-special) with
//        their properties, MESG FO4SF_NewGameElevator and MESG FO4SF_NewGameStart (two buttons each: the elevator
//        prompt, and the opening choice "Create character" or "Quick start" the looks script shows, NG-6 / NG-C9), and
//        an override of Starfield's GLOB MQ101Debug set to 10 (what MQ00 writes before it starts MQ101; the owner's
//        decision NG-2 is that we set it ourselves) unless --no-mq101debug, or --mq101debug <n> for another value.
//        Unless --no-version: GLOB FO4SF_NewGameVersion (constant, the build's version number, --build-version <n>,
//        default 1) and a player alias on the quest carrying FO4SF_NewGameVersion, which compares that GLOB to the
//        version the save was started with on every load (NG-15 / NG-L2).
//        --race-menu-mode <n> is the uiMode the looks script passes to Game.ShowRaceMenu (its RaceMenuMode property;
//        default 0, the full creator: which mode is looks-only is unverified until the in-game C1 test). Unless
//        --no-special: seven AVIF FO4SF_Special_<stat> (Strength to Luck, the SPECIAL stats as our own actor values),
//        MESG FO4SF_NewGameTerminal (the prompt at the vault terminal, two buttons) and MESG FO4SF_NewGameSpecial (the
//        allocation: one button per stat, Reset, Confirm, Leave), which the SPECIAL script drives (NG-5 / NG-C4). The
//        port and the core are read for the ids and positions the scripts resolve at run time with Game.GetFormFromFile
//        (plugin-local ids): the vault anchor (the COC marker of FO4Port_Vault111Cryo), the cog door (formids.json
//        REFR:FO4Port_Vault111Cryo:0330C3:...; 0 when the port has none), the terminal (the first of points' terminals
//        the port carries, a persistent one preferred; 0 when it carries none, the prompt then watches points' spot)
//        and the exit anchor (the core's Vault 111 map marker).
//        --clear-inventory (default off, NG-K8): the quest script empties the player's inventory (quest items kept)
//        right after the move into the pod and logs the count removed; --vault-suit <EditorID> (only with it) names an
//        ARMO of FO4Port.esm the script then adds and equips, resolved here by EditorID with the same owner check as
//        the other ids (refused when the port lacks it, has two, or it is another plugin's record).
//   check <plugin> <Starfield.esm> <FO4Port.esm> <port formids.json> <FO4TerrainCore.esm> <points.json> [same options]
//        reads the plugin back and checks every record, property and id the script relies on (exit 1 on a problem).
//   selftest <scratch dir>
//        synthetic Fallout4.esm, Starfield.esm, port and core; points + write + check, and mutations check rejects;
//        then the records selftest.
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
        "points" when args.Length >= 3 => NewGame.Points(args[1], args[2], NewGame.ArgOrNull(args, "--pod-ref"), NewGame.Opt(args, "--pod-step", 1.0f), NewGame.ArgOrNull(args, "--terminal-ref")),
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
    public const string TerminalMessageEdid = "FO4SF_NewGameTerminal", SpecialMessageEdid = "FO4SF_NewGameSpecial", SpecialAvifPrefix = "FO4SF_Special_";
    public const uint QuestId = 0x800, MessageId = 0x801, StartMessageId = 0x802, TerminalMessageId = 0x803, SpecialMessageId = 0x804;   // the GLOB override keeps Starfield's id
    public const uint SpecialAvifBase = 0x810;                  // the seven AVIF: 0x810 Strength to 0x816 Luck
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
    public const int SpecialBase = 1, SpecialPoints = 21, SpecialMax = 10;
    public const SF.ActorValueInformation.Flag SpecialAvifFlags = SF.ActorValueInformation.Flag.DefaultToOne | SF.ActorValueInformation.Flag.MinimumOne | SF.ActorValueInformation.Flag.MaximumTen;
    // Game.ShowRaceMenu(ObjectReference akMenuTarget = None, int uiMode = 0, ...) (verified, Starfield's Game.psc): the
    // modes are FO4's (0 chargen, 1 remake, 2 haircut, 3 surgery, 4 face paint, NG-C1), but what each shows with
    // MQ101 stopped, and which is looks-only (the owner's decision NG-C3), is unverified until the in-game C1 test
    public const int DefaultRaceMenuMode = 0;
    // The starting inventory (NG-K8 / NG-N3): FO4's MQ101 runs RemoveAllItems at stages 0 and 900; Starfield's MQ101
    // stage 0 swaps the outfit and removes items too (PC read 19 Oct). What a game started with MQ101 held off leaves
    // in the player's inventory is unverified until the first in-game proof, so the reset is OFF by default: the quest
    // script's ClearInventory property (false) and VaultSuitId (0, none). With --clear-inventory the script calls
    // ObjectReference.RemoveAllItems(None, false, false) (quest items kept; FO4's signature, Starfield's is read by the
    // precheck, unverified) after the move into the pod, and with --vault-suit it adds and equips the port's ARMO.
    public const bool DefaultClearInventory = false;
    // GLOB MQ101Debug: MQ00's stage 10 sets it to 10 and starts MQ101 (verified, QF_MQ00_00005790.psc). We stop MQ00,
    // which may leave it at 0 (sustenance off, NG-M1), so the default build writes 10 ourselves (NG-2); which value
    // gives the cleanest start is unverified until the PC run (NG-M4), hence --mq101debug <n> and --no-mq101debug.
    public const float DefaultMQ101Debug = 10f;
    // Starfield.esm, verified: QuestTypeSideQuest (the mission, Missions tab), GameDaysPassed (FLTV 0 on a new game,
    // docs/ai/test-queue.md), COCMarkerHeading (the port places each cell's COC marker on it, WP10)
    public const uint QuestTypeSideId = 0x047600, GameDaysPassedId = 0x000039, CocMarkerId = 0x000032;
    public const string QuestTypeSideEdid = "QuestTypeSideQuest", GameDaysPassedEdid = "GameDaysPassed";
    // Fallout4.esm, verified in docs/spikes/B4-mission-anatomy.md section 3
    public const uint Fo4VaultCell = 0x0016D8, Fo4Console = 0x091A49, Fo4CogDoor = 0x0330C3, Fo4Platform = 0x0244EB,
                      Fo4ExitDoor = 0x01F180, Fo4MQ102 = 0x01CC2A;
    // the quests held off on a new game: the main-quest start and the opening, and the two MQ101's stage 9000 starts
    // when MQ101 is stopped (MQ101PostQuest always, MQ_TutorialQuest_Misc04 unless the player entered the Unity; PC
    // read 19 Oct, NG-19 / NG-N1), which the script stops on a second pass one tick later
    public static readonly string[] DefaultHold = { "MQ00", "MQ101", "MQ101PostQuest", "MQ_TutorialQuest_Misc04" };
    // the stages and the objective FO4SF_NewGameQuest.psc drives (stage 0, the wait for the player's 3D, is no record)
    public static readonly ushort[] Stages = { 1, 10, 20, 30, 40, 200 };
    public const ushort Objective = 10;
    public const string ObjectiveText = "Leave Vault 111";
    public const float Units = 70f, MergeX = -1200f, MergeY = -2700f;   // FO4 units per metre; vmad_patch.MERGE_MEASURED
    static readonly ModKey SfEsm = ModKey.FromFileName("Starfield.esm");

    public class Refusal(string m) : Exception(m);

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
                          bool ClearInventory = DefaultClearInventory, string? VaultSuit = null)
    {
        public static Options From(string[] a)
        {
            var suit = ArgOrNull(a, "--vault-suit");
            if (a.Contains("--vault-suit") && (suit is null || suit.StartsWith("--"))) throw new Refusal("--vault-suit needs an ARMO EditorID");
            bool clear = a.Contains("--clear-inventory");
            if (suit is not null && !clear) throw new Refusal("--vault-suit is equipped by the inventory reset: it needs --clear-inventory");
            return new(
                ArgOrNull(a, "--plugin") ?? NewGame.Plugin,
                (ArgOrNull(a, "--hold") ?? string.Join(",", DefaultHold)).Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries),
                a.Contains("--no-mq101debug") ? null : ArgOrNull(a, "--mq101debug") is { } d ? float.Parse(d, CultureInfo.InvariantCulture) : DefaultMQ101Debug,
                !a.Contains("--no-looks"),
                ArgOrNull(a, "--race-menu-mode") is { } m ? int.Parse(m, CultureInfo.InvariantCulture) : DefaultRaceMenuMode,
                !a.Contains("--no-special"),
                !a.Contains("--no-version"),
                ArgOrNull(a, "--build-version") is { } v ? float.Parse(v, CultureInfo.InvariantCulture) : DefaultBuildVersion,
                ArgOrNull(a, "--exit-anchor") ?? ExitAnchorEdid,
                clear, suit);
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
        var doc = new Dictionary<string, object?>
        {
            ["source"] = Path.GetFileName(fo4Path),
            ["frame"] = "metres, FO4 position / 70 (interior: the port's cell frame; arrival: the core's local frame); headings in degrees",
            ["quest_name"] = mq102,
            ["pod"] = new Dictionary<string, object?> { ["src"] = $"{pod.FormKey.ID:X8}", ["edid"] = pod.EditorID, ["at"] = M(pod.Position),
                                                         ["pos"] = stand, ["heading"] = Deg(h), ["step_m"] = podStep },
            ["console"] = new Dictionary<string, object?> { ["src"] = $"{Fo4Console:X8}", ["pos"] = M(PosOf(console)) },
            ["cog_door"] = new Dictionary<string, object?> { ["src"] = $"{Fo4CogDoor:X8}", ["pos"] = M(PosOf(cog)) },
            ["platform"] = new Dictionary<string, object?> { ["src"] = $"{Fo4Platform:X8}", ["pos"] = M(PosOf(platform)) },
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
                         uint Terminal, uint TerminalSrc, P3Float TerminalPos, uint VaultSuit = 0);

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

    /// The vault anchor (the one COC marker of FO4Port_Vault111Cryo), the cog door (formids.json's key for FO4 000330C3
    /// in that cell, 0 when absent, and it must be a reference of that cell), the SPECIAL terminal (the first of points'
    /// terminals the port carries, a persistent one preferred, nearest the pod among those; each key named must be the
    /// port's own reference of the cell; 0 when it carries none, and the prompt then watches points' nearest terminal)
    /// the exit anchor (the core world's REFR with that EditorID, persistent) and, when `vaultSuit` names one, the port's
    /// ARMO of that EditorID (exactly one, the port's own record; refused otherwise) the inventory reset equips.
    public static Places Resolve(string portPath, string portIds, string corePath, string exitAnchor, IReadOnlyList<(uint Src, P3Float Pos)>? terminals = null, string? vaultSuit = null)
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
        var cell = port.EnumerateMajorRecords<SF.ICellGetter>().FirstOrDefault(c => c.EditorID == VaultCell && c.FormKey.ModKey == port.ModKey)
                   ?? throw new Refusal($"{port.ModKey} has no cell {VaultCell}");
        var inCell = cell.Persistent.Concat(cell.Temporary).OfType<SF.IPlacedObjectGetter>().ToList();
        var cocs = inCell.Where(r => r.Base.FormKey == new FormKey(SfEsm, CocMarkerId)).ToList();
        if (cocs.Count != 1) throw new Refusal($"{VaultCell} has {cocs.Count} COC markers, not one");
        Owned(cocs[0], port.ModKey, "the vault's COC marker");
        // The script resolves the anchor at game start, while the vault is not loaded: a temporary reference in an
        // unloaded cell resolves to none (16 Oct probe, JOURNAL), so the anchor must be persistent. The COC marker when
        // it is; otherwise the port's own persistent reference in the cell nearest to it (the script moves the player
        // by the pod's offset from the anchor, so any persistent reference of the cell serves). 20 Oct review on #393.
        var c0 = cocs[0].Position;
        float Dist(SF.IPlacedObjectGetter r) => MathF.Sqrt(MathF.Pow(r.Position.X - c0.X, 2) + MathF.Pow(r.Position.Y - c0.Y, 2) + MathF.Pow(r.Position.Z - c0.Z, 2));
        var anchor = IsPersistent(cocs[0]) ? cocs[0]
                   : cell.Persistent.OfType<SF.IPlacedObjectGetter>().Where(r => r.FormKey.ModKey == port.ModKey && IsPersistent(r))
                         .OrderBy(Dist).ThenBy(r => r.FormKey.ID).FirstOrDefault()
                     ?? throw new Refusal($"{VaultCell} has no persistent reference of {port.ModKey} to anchor the start on (its COC marker is temporary, and a temporary reference does not resolve before the vault loads)");
        uint cog = 0;
        string cogBase = "none";
        var termRefs = new Dictionary<uint, uint>();            // FO4 terminal id -> the port's reference id
        using (var doc = JsonDocument.Parse(File.ReadAllText(portIds)))
            foreach (var e in doc.RootElement.EnumerateObject())
            {
                if (IsCogDoorKey(e.Name)) cog = e.Value.GetUInt32();
                foreach (var (src, _) in terminals ?? Array.Empty<(uint, P3Float)>())
                    if (IsRefKey(e.Name, src)) termRefs[src] = e.Value.GetUInt32();
            }
        if (cog != 0)
        {
            var r = inCell.FirstOrDefault(x => x.FormKey.ID == cog) ?? throw new Refusal($"formids.json names {cog:X6} as the cog door, not a reference of {VaultCell}");
            Owned(r, port.ModKey, "the cog door");
            cogBase = port.EnumerateMajorRecords().FirstOrDefault(x => x.FormKey == r.Base.FormKey) is { } b ? $"{b.GetType().Name.Replace("BinaryOverlay", "")} {b.EditorID}" : r.Base.FormKey.ToString();
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
        return new Places(anchor.FormKey.ID, anchor.Position, cog, cogBase, exits[0].FormKey.ID, exits[0].Position, terminal, terminalSrc, terminalPos, suit);
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

    /// Every script property the plugin writes, by name: what the check compares and the Python contract test reads.
    public static List<(string Name, object Value)> Properties(JsonElement pts, Places p, Options o)
    {
        var pod = Floats(pts.GetProperty("pod").GetProperty("pos"));
        var con = Floats(pts.GetProperty("console").GetProperty("pos"));
        var plat = Floats(pts.GetProperty("platform").GetProperty("pos"));
        var arr = Floats(pts.GetProperty("arrival").GetProperty("pos"));
        return new()
        {
            ("VaultAnchorId", (int)p.VaultAnchor), ("AnchorX", p.AnchorPos.X), ("AnchorY", p.AnchorPos.Y), ("AnchorZ", p.AnchorPos.Z),
            ("PodX", pod[0]), ("PodY", pod[1]), ("PodZ", pod[2]), ("PodHeading", pts.GetProperty("pod").GetProperty("heading").GetSingle()),
            ("CogDoorId", (int)p.CogDoor), ("ConsoleX", con[0]), ("ConsoleY", con[1]), ("ConsoleZ", con[2]),
            ("PlatformX", plat[0]), ("PlatformY", plat[1]), ("PlatformZ", plat[2]),
            ("ExitAnchorId", (int)p.ExitAnchor), ("ArrivalX", arr[0]), ("ArrivalY", arr[1]), ("ArrivalZ", arr[2]),
            ("ArrivalHeading", pts.GetProperty("arrival").GetProperty("heading").GetSingle()),
            ("FallbackX", p.ExitPos.X), ("FallbackY", p.ExitPos.Y), ("FallbackZ", p.ExitPos.Z),
            ("MergeOffsetX", MergeX), ("MergeOffsetY", MergeY), ("LooksWait", o.Looks ? 120f : 0f),
            ("ClearInventory", o.ClearInventory), ("VaultSuitId", (int)p.VaultSuit),
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
        _ => throw new Refusal($"property {name}: unsupported value"),
    };

    static bool ValueMatches(object value, SF.IScriptPropertyGetter p) => (value, p) switch
    {
        (int i, SF.IScriptIntPropertyGetter ip) => ip.Data == i,
        (float f, SF.IScriptFloatPropertyGetter fp) => fp.Data == f && float.IsFinite(fp.Data),
        (bool b, SF.IScriptBoolPropertyGetter bp) => bp.Data == b,
        _ => false,
    };

    public static int Write(string sfPath, string portPath, string portIds, string corePath, string pointsPath, string outDir, Options o)
    {
        var pts = JsonDocument.Parse(File.ReadAllText(pointsPath)).RootElement;
        var places = Resolve(portPath, portIds, corePath, o.ExitAnchor, Terminals(pts), o.VaultSuit);
        using var sf = SF.StarfieldMod.CreateFromBinaryOverlay(sfPath, SF.StarfieldRelease.Starfield);
        var modKey = ModKey.FromFileName(o.Plugin);
        var mod = new SF.StarfieldMod(modKey, SF.StarfieldRelease.Starfield);
        mod.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Master;
        mod.ModHeader.Author = "fo4-to-starfield NewGame";

        var qtyp = sf.Keywords.FirstOrDefault(k => k.FormKey == new FormKey(SfEsm, QuestTypeSideId) && k.EditorID == QuestTypeSideEdid)
                   ?? throw new Refusal($"Starfield.esm {QuestTypeSideId:X6} is not the KYWD {QuestTypeSideEdid}");
        var days = sf.Globals.FirstOrDefault(g => g.FormKey == new FormKey(SfEsm, GameDaysPassedId) && g.EditorID == GameDaysPassedEdid)
                   ?? throw new Refusal($"Starfield.esm {GameDaysPassedId:X6} is not the GLOB {GameDaysPassedEdid}");
        var hold = o.Hold.Select(e => sf.Quests.FirstOrDefault(q => q.EditorID == e) ?? throw new Refusal($"Starfield.esm has no quest {e}")).ToList();

        var msg = new SF.Message(new FormKey(modKey, MessageId), SF.StarfieldRelease.Starfield)
        {
            EditorID = MessageEdid, Name = "Vault 111 elevator", Description = "Ride the elevator up to the surface?",
            Flags = SF.Message.Flag.MessageBox,
        };
        msg.MenuButtons.Add(new SF.MessageButton { Text = "Ride up" });
        msg.MenuButtons.Add(new SF.MessageButton { Text = "Stay" });
        mod.Messages.Add(msg);
        // the opening choice (NG-6, NG-C9): button 0 opens the creator, button 1 keeps the preset and skips it. A
        // message box, so it needs no voice: the player is silent
        var start = new SF.Message(new FormKey(modKey, StartMessageId), SF.StarfieldRelease.Starfield)
        {
            EditorID = StartMessageEdid, Name = "Vault 111", Description = "Create your character, or start quickly with the preset?",
            Flags = SF.Message.Flag.MessageBox,
        };
        start.MenuButtons.Add(new SF.MessageButton { Text = "Create character" });
        start.MenuButtons.Add(new SF.MessageButton { Text = "Quick start" });
        mod.Messages.Add(start);
        // SPECIAL at the vault terminal (NG-5 / NG-C4): the prompt, the allocation and the seven actor values
        var avifs = new List<SF.ActorValueInformation>();
        SF.Message? terminalMsg = null, specialMsg = null;
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
            // FO4's message boxes do; whether Starfield's substitute the same way is unverified until the PC run
            specialMsg = new SF.Message(new FormKey(modKey, SpecialMessageId), SF.StarfieldRelease.Starfield)
            {
                EditorID = SpecialMessageEdid, Name = "S.P.E.C.I.A.L.",
                Description = SpecialDescription, Flags = SF.Message.Flag.MessageBox,
            };
            foreach (var b in SpecialNames.Concat(SpecialExtraButtons)) specialMsg.MenuButtons.Add(new SF.MessageButton { Text = b });
            mod.Messages.Add(specialMsg);
            for (int i = 0; i < SpecialNames.Length; i++) { var av = SpecialAvif(modKey, i); avifs.Add(av); mod.ActorValueInformation.Add(av); }
        }

        var quest = new SF.Quest(new FormKey(modKey, QuestId), SF.StarfieldRelease.Starfield)
        {
            EditorID = QuestEdid, Name = pts.GetProperty("quest_name").GetString(), FormVersion = 581, Version2 = 12,
            Data = new SF.QuestData { Flags = SF.Quest.Flag.StartGameEnabled | SF.Quest.Flag.RunOnce | SF.Quest.Flag.DisplaysInHud, Priority = 70 },
        };
        quest.QuestType.SetTo(qtyp.FormKey);
        foreach (var s in Stages)
        {
            var st = new SF.QuestStage { Index = s };
            if (s == 200) st.LogEntries.Add(new SF.QuestLogEntry { Flags = SF.QuestLogEntry.Flag.CompleteQuest });
            quest.Stages.Add(st);
        }
        quest.Objectives.Add(new SF.QuestObjective { Index = Objective, DisplayText = ObjectiveText });
        var script = new SF.ScriptEntry { Name = ScriptName, Flags = SF.ScriptEntry.Flag.Local };
        SF.ScriptObjectProperty Obj(string name, FormKey fk) => new()
        {
            Name = name, Flags = SF.ScriptProperty.Flag.Edited, Object = new FormLink<SF.IStarfieldMajorRecordGetter>(fk), Alias = -1, Unused = 0,
        };
        script.Properties.Add(Obj("GameDaysPassed", days.FormKey));
        var list = new SF.ScriptObjectListProperty { Name = "HoldOff", Flags = SF.ScriptProperty.Flag.Edited };
        foreach (var q in hold) list.Objects.Add(Obj("", q.FormKey));
        script.Properties.Add(list);
        script.Properties.Add(Obj("ExitMessage", msg.FormKey));
        foreach (var (name, value) in Properties(pts, places, o))
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
            foreach (var av in avifs) avs.Objects.Add(Obj("", av.FormKey));
            special.Properties.Add(avs);
            special.Properties.Add(Obj("TerminalMessage", terminalMsg!.FormKey));
            special.Properties.Add(Obj("SpecialMessage", specialMsg!.FormKey));
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

        if (o.MQ101Debug is { } dbg)
        {
            var g = sf.Globals.FirstOrDefault(x => x.EditorID == "MQ101Debug") ?? throw new Refusal("Starfield.esm has no GLOB MQ101Debug");
            var over = (SF.Global)g.DeepCopy();
            over.Data = dbg;
            mod.Globals.Add(over);
        }
        mod.ModHeader.Stats.NextFormID = SpecialAvifBase + (uint)SpecialNames.Length;
        Directory.CreateDirectory(outDir);
        var path = Path.Combine(outDir, o.Plugin);
        mod.BeginWrite.ToPath(path).WithLoadOrder(SfEsm).WithKnownMasters(new KeyedMasterStyle(SfEsm, MasterStyle.Full)).Write();
        Console.WriteLine($"wrote {path} ({new FileInfo(path).Length:N0} bytes): QUST {QuestEdid} {quest.FormKey} \"{quest.Name}\" " +
                          $"hold [{string.Join(", ", o.Hold)}]; vault anchor FO4Port.esm:{places.VaultAnchor:X6} at {Show(places.AnchorPos)}, " +
                          $"cog door {(places.CogDoor == 0 ? "none" : $"{places.CogDoor:X6} ({places.CogDoorBase})")}, exit anchor " +
                          $"FO4TerrainCore.esm:{places.ExitAnchor:X6} at {Show(places.ExitPos)}; looks {(o.Looks ? $"on (race menu mode {o.RaceMenuMode})" : "off")}" +
                          (o.MQ101Debug is { } d2 ? $"; GLOB MQ101Debug = {F(d2)}" : "; GLOB MQ101Debug not overridden") +
                          (o.Special ? $"; SPECIAL on: terminal {TerminalText(places)}, {avifs.Count} AVIF" : "; SPECIAL off") +
                          (o.Version ? $"; version check on: GLOB {VersionGlobEdid} = {F(o.BuildVersion)}, alias {PlayerAlias} {PlayerAliasName} -> Starfield.esm:{PlayerRefId:X6}" : "; version check off") +
                          $"; inventory reset {InventoryText(o, places)}");
        return 0;
    }

    static string InventoryText(Options o, Places p) => !o.ClearInventory ? "off" :
        $"on (quest items kept), vault suit {(o.VaultSuit is null ? "none" : $"{o.VaultSuit} FO4Port.esm:{p.VaultSuit:X6}")}";

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

    /// One SPECIAL stat as our own actor value: a SpecialAttribute with FO4's range (default 1, 1 to 10, NG-C4), the
    /// numbers and the flags that name them both. The minimal shape; which other fields a shipped Starfield AVIF
    /// carries is unverified until the PC run.
    public static SF.ActorValueInformation SpecialAvif(ModKey modKey, int i) => new(new FormKey(modKey, SpecialAvifBase + (uint)i), SF.StarfieldRelease.Starfield)
    {
        EditorID = SpecialAvifPrefix + SpecialNames[i], Name = SpecialNames[i], Abbreviation = SpecialNames[i][..1],
        Type = SF.ActorValueInformation.Types.SpecialAttribute, DefaultValue = SpecialBase, Min = SpecialBase, Max = SpecialMax, Flags = SpecialAvifFlags,
    };

    // ---------------------------------------------------------------- check

    public static int Check(string pluginPath, string sfPath, string portPath, string portIds, string corePath, string pointsPath, Options o)
    {
        var problems = new List<string>();
        void Need(bool ok, string what) { if (!ok) problems.Add(what); }
        var pts = JsonDocument.Parse(File.ReadAllText(pointsPath)).RootElement;
        var places = Resolve(portPath, portIds, corePath, o.ExitAnchor, Terminals(pts), o.VaultSuit);
        using var sf = SF.StarfieldMod.CreateFromBinaryOverlay(sfPath, SF.StarfieldRelease.Starfield);
        using var plug = SF.StarfieldMod.CreateFromBinaryOverlay(pluginPath, SF.StarfieldRelease.Starfield, Full(SfEsm));
        var key = plug.ModKey;
        var masters = plug.ModHeader.MasterReferences.Select(x => x.Master.FileName.String).ToList();
        Console.WriteLine($"{key}: header {plug.ModHeader.Flags}, masters [{string.Join(", ", masters)}], {plug.Quests.Count} QUST, " +
                          $"{plug.Messages.Count} MESG, {plug.Globals.Count} GLOB, {plug.ActorValueInformation.Count} AVIF, " +
                          $"{plug.Quests.Sum(q => q.Aliases?.Count ?? 0)} alias(es)");
        Need(plug.ModHeader.Flags.HasFlag(SF.StarfieldModHeader.HeaderFlag.Master), "not flagged as a master");
        Need(masters.SequenceEqual(new[] { "Starfield.esm" }), "masters are not Starfield.esm alone (the port and the core are resolved at run time)");
        Need(plug.Npcs.Count == 0 && plug.Worldspaces.Count == 0 && plug.Cells.Count == 0, "the plugin carries NPC_, WRLD or CELL records (it places nothing)");

        var msg = plug.Messages.FirstOrDefault(m => m.FormKey == new FormKey(key, MessageId));
        Need(msg is { EditorID: MessageEdid } && msg.Flags.HasFlag(SF.Message.Flag.MessageBox) && msg.MenuButtons.Count == 2 &&
             msg.MenuButtons.All(b => !string.IsNullOrWhiteSpace(b.Text?.String)), $"MESG 0x{MessageId:X} is not {MessageEdid}, a message box with two buttons");
        var start = plug.Messages.FirstOrDefault(m => m.FormKey == new FormKey(key, StartMessageId));
        Need(start is { EditorID: StartMessageEdid } && start.Flags.HasFlag(SF.Message.Flag.MessageBox) && start.MenuButtons.Count == 2 &&
             start.MenuButtons.All(b => !string.IsNullOrWhiteSpace(b.Text?.String)), $"MESG 0x{StartMessageId:X} is not {StartMessageEdid}, a message box with two buttons");
        var terminalMsg = plug.Messages.FirstOrDefault(m => m.FormKey == new FormKey(key, TerminalMessageId));
        var specialMsg = plug.Messages.FirstOrDefault(m => m.FormKey == new FormKey(key, SpecialMessageId));
        var avifs = plug.ActorValueInformation.OrderBy(a => a.FormKey.ID).ToList();
        if (o.Special)
        {
            Need(terminalMsg is { EditorID: TerminalMessageEdid } && terminalMsg.Flags.HasFlag(SF.Message.Flag.MessageBox) && terminalMsg.MenuButtons.Count == 2 &&
                 terminalMsg.MenuButtons.All(b => !string.IsNullOrWhiteSpace(b.Text?.String)), $"MESG 0x{TerminalMessageId:X} is not {TerminalMessageEdid}, a message box with two buttons");
            var buttons = SpecialNames.Concat(SpecialExtraButtons).ToList();
            Need(specialMsg is { EditorID: SpecialMessageEdid } && specialMsg.Flags.HasFlag(SF.Message.Flag.MessageBox) &&
                 specialMsg.MenuButtons.Select(b => b.Text?.String).SequenceEqual(buttons) && specialMsg.Description?.String == SpecialDescription,
                 $"MESG 0x{SpecialMessageId:X} is not {SpecialMessageEdid}, a message box with the buttons [{string.Join(", ", buttons)}] and the allocation text");
            Need(plug.Messages.Count == 4, $"{plug.Messages.Count} MESG, expected 4");
            Need(avifs.Count == SpecialNames.Length && avifs.Select((a, i) => a.FormKey == new FormKey(key, SpecialAvifBase + (uint)i) && a.EditorID == SpecialAvifPrefix + SpecialNames[i] &&
                     a.Name?.String == SpecialNames[i] && a.Type == SF.ActorValueInformation.Types.SpecialAttribute && a.DefaultValue == SpecialBase && a.Min == SpecialBase && a.Max == SpecialMax &&
                     a.Flags == SpecialAvifFlags).All(x => x),
                 $"the AVIF are not the seven {SpecialAvifPrefix}<stat> SpecialAttributes, default {SpecialBase}, {SpecialBase} to {SpecialMax}, flags {SpecialAvifFlags}");
            Console.WriteLine($"  AVIF [{string.Join(", ", avifs.Select(a => a.EditorID))}]; terminal {TerminalText(places)}");
        }
        else
        {
            Need(plug.Messages.Count == 2, $"{plug.Messages.Count} MESG, expected 2 in a --no-special build");
            Need(avifs.Count == 0, "a --no-special build carries AVIF records");
        }

        // the GLOBs: Starfield's MQ101Debug overridden (or not), and our own version GLOB (or not); nothing else
        var overrides = plug.Globals.Where(g => g.FormKey.ModKey != key).ToList();
        var own = plug.Globals.Where(g => g.FormKey.ModKey == key).ToList();
        if (o.MQ101Debug is { } dbg)
        {
            var src = sf.Globals.FirstOrDefault(g => g.EditorID == "MQ101Debug");
            Need(overrides.Count == 1 && src is not null && overrides[0].FormKey == src.FormKey && overrides[0].Data == dbg,
                 $"GLOB MQ101Debug is not overridden to {F(dbg)}");
        }
        else Need(overrides.Count == 0, "a --no-mq101debug build overrides a GLOB");
        var ver = own.FirstOrDefault(g => g.FormKey == new FormKey(key, VersionGlobId));
        if (o.Version)
        {
            Need(own.Count == 1 && ver is { EditorID: VersionGlobEdid } && ver.Data == o.BuildVersion && ver.MajorFlags.HasFlag(SF.Global.MajorFlag.Constant),
                 $"GLOB 0x{VersionGlobId:X} is not {VersionGlobEdid} = {F(o.BuildVersion)}, constant");
            Console.WriteLine($"  GLOB {VersionGlobEdid} = {(ver?.Data is { } vd ? F(vd) : "missing")} flags {ver?.MajorFlags}");
        }
        else Need(own.Count == 0, "a --no-version build carries a GLOB of its own");

        var q = plug.Quests.FirstOrDefault(x => x.FormKey == new FormKey(key, QuestId));
        if (q is null) problems.Add("no QUST 0x800");
        else
        {
            Console.WriteLine($"  QUST {q.EditorID} \"{q.Name?.String}\" flags {q.Data?.Flags} stages [{string.Join(",", q.Stages.Select(s => s.Index))}] " +
                              $"objectives [{string.Join("; ", q.Objectives.Select(x => $"{x.Index} \"{x.DisplayText?.String}\""))}]");
            Need(q.EditorID == QuestEdid && q.Data is not null && q.Data.Flags.HasFlag(SF.Quest.Flag.StartGameEnabled) && q.Data.Flags.HasFlag(SF.Quest.Flag.RunOnce),
                 "the quest is not FO4SF_NewGame, start game enabled and run once");
            Need(q.QuestType.FormKey == new FormKey(SfEsm, QuestTypeSideId), $"the quest's QuestType is not {QuestTypeSideEdid}");
            Need(q.Stages.Select(s => s.Index).SequenceEqual(Stages), "stages differ from the script's");
            Need(q.Stages.LastOrDefault()?.LogEntries.Any(l => l.Flags?.HasFlag(SF.QuestLogEntry.Flag.CompleteQuest) == true) == true, "stage 200 does not complete the quest");
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
                Need(props.TryGetValue("ExitMessage", out var mp) && mp is SF.IScriptObjectPropertyGetter mo && mo.Object.FormKey == msg?.FormKey, "property ExitMessage");
                var want = o.Hold.Select(e => sf.Quests.FirstOrDefault(x => x.EditorID == e)?.FormKey).ToList();
                Need(want.All(x => x is not null) && props.TryGetValue("HoldOff", out var hp) && hp is SF.IScriptObjectListPropertyGetter hl &&
                     hl.Objects.Select(x => (FormKey?)x.Object.FormKey).SequenceEqual(want), $"property HoldOff is not [{string.Join(", ", o.Hold)}] in order");
                var expected = Properties(pts, places, o);
                foreach (var (name, value) in expected)
                    Need(props.TryGetValue(name, out var p) && ValueMatches(value, p), $"property {name} is not {value}");
                Need(props.Count == expected.Count + 3, $"{props.Count} properties, expected {expected.Count + 3}");
                Need(places.VaultAnchor > 0 && places.ExitAnchor > 0, "an anchor id is 0");
                Need((o.VaultSuit is null) == (places.VaultSuit == 0), "the vault suit id does not follow --vault-suit");
                Console.WriteLine($"  inventory reset {InventoryText(o, places)}");
            }
            else problems.Add($"script {ScriptName} not attached");
            var ls = q.VirtualMachineAdapter?.Scripts.FirstOrDefault(x => x.Name == LooksScript);
            if (ls is not null)
            {
                var props = ls.Properties.ToDictionary(p => p.Name);
                Console.WriteLine($"  script {ls.Name}: {props.Count} properties, RaceMenuMode {(props.TryGetValue("RaceMenuMode", out var rm) && rm is SF.IScriptIntPropertyGetter ri ? ri.Data.ToString() : "missing")}");
                Need(props.TryGetValue("StartMessage", out var sp) && sp is SF.IScriptObjectPropertyGetter so && so.Object.FormKey == start?.FormKey, "property StartMessage");
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
                     al.Objects.Select(x => x.Object.FormKey).SequenceEqual(avifs.Select(a => a.FormKey)) && al.Objects.Count == SpecialNames.Length,
                     "property Special is not the seven AVIF, Strength to Luck");
                Need(props.TryGetValue("TerminalMessage", out var tp) && tp is SF.IScriptObjectPropertyGetter to && to.Object.FormKey == terminalMsg?.FormKey, "property TerminalMessage");
                Need(props.TryGetValue("SpecialMessage", out var xp) && xp is SF.IScriptObjectPropertyGetter xo && xo.Object.FormKey == specialMsg?.FormKey, "property SpecialMessage");
                var expected = SpecialProperties(pts, places);
                foreach (var (name, value) in expected)
                    Need(props.TryGetValue(name, out var p) && ValueMatches(value, p), $"SPECIAL property {name} is not {value}");
                Need(props.Count == expected.Count + 3, $"{props.Count} SPECIAL properties, expected {expected.Count + 3}");
            }
        }
        Console.WriteLine($"  vault anchor FO4Port.esm:{places.VaultAnchor:X6}, cog door {(places.CogDoor == 0 ? "none" : $"{places.CogDoor:X6} {places.CogDoorBase}")}, " +
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
        vcell.Temporary.Add(P(Fo4CogDoor, "Vault111GearDoorREF", 3640f, 700f, 0f));
        vcell.Temporary.Add(P(Fo4Platform, "V111ElevatorREF", 4200f, 1050f, -140f));
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
        // a stand-in Starfield.esm: the quest type, GameDaysPassed, MQ101Debug, the opening quests, the COC marker
        var sf = new SF.StarfieldMod(SfEsm, rel);
        sf.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Master;
        sf.Keywords.Add(new SF.Keyword(new FormKey(SfEsm, QuestTypeSideId), rel) { EditorID = QuestTypeSideEdid });
        sf.Globals.Add(new SF.Global(new FormKey(SfEsm, GameDaysPassedId), rel) { EditorID = GameDaysPassedEdid, Data = 0 });
        sf.Globals.Add(new SF.Global(new FormKey(SfEsm, 0x900), rel) { EditorID = "MQ101Debug", Data = 0 });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x901), rel) { EditorID = "MQ00" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x902), rel) { EditorID = "MQ101" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x903), rel) { EditorID = "MQ101PostQuest" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x904), rel) { EditorID = "MQ_TutorialQuest_Misc04" });
        sf.Statics.Add(new SF.Static(new FormKey(SfEsm, CocMarkerId), rel) { EditorID = "COCMarkerHeading" });
        sf.ModHeader.Stats.NextFormID = 0x800;
        var sfPath = Path.Combine(dir, "Starfield.esm");
        sf.BeginWrite.ToPath(sfPath).WithNoLoadOrder().NoCheckIfLowerRangeDisallowed().Write();
        // a port with FO4Port_Vault111Cryo: its COC marker and the cog door, and formids.json as PluginSpike writes it
        var portKey = ModKey.FromFileName("FO4Port.esm");
        var port = new SF.StarfieldMod(portKey, rel);
        port.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Master;
        var pdoor = new SF.Door(new FormKey(portKey, 0x810), rel) { EditorID = "FO4Port_VltGearDoor01" };
        port.Doors.Add(pdoor);
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
                                   $"\"REFR:{VaultCell}:001002:Fallout4.esm\": {0x807}, \"REFR:{VaultCell}:001003:Fallout4.esm\": {0x808}}}");
        var noCogIds = Path.Combine(dir, "formids_nocog.json");          // neither the cog door nor a terminal
        File.WriteAllText(noCogIds, $"{{\"CELL:{VaultCell}\": {0x800}}}");
        var nearTermIds = Path.Combine(dir, "formids_nearterm.json");    // only the nearer, temporary terminal
        File.WriteAllText(nearTermIds, $"{{\"CELL:{VaultCell}\": {0x800}, \"REFR:{VaultCell}:0330C3:Fallout4.esm\": {0x802}, \"REFR:{VaultCell}:001002:Fallout4.esm\": {0x807}}}");
        // a core with the world and its Vault 111 map marker, persistent
        var coreKey = ModKey.FromFileName("FO4TerrainCore.esm");
        var core = new SF.StarfieldMod(coreKey, rel);
        core.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Master;
        var world = new SF.Worldspace(new FormKey(coreKey, 0x803), rel) { EditorID = World };
        world.TopCell = new SF.Cell(new FormKey(coreKey, 0x900), rel);
        var marker = new SF.PlacedObject(new FormKey(coreKey, 0xA775B), rel) { EditorID = ExitAnchorEdid, Position = new P3Float(-1275.3f, 1305.3f, 108.2f) };
        marker.MajorRecordFlagsRaw |= 0x400;
        world.TopCell.Persistent.Add(marker);
        core.Worldspaces.Add(world);
        core.ModHeader.Stats.NextFormID = 0xA775C;
        var corePath = Path.Combine(dir, coreKey.FileName);
        core.BeginWrite.ToPath(corePath).WithLoadOrder(SfEsm).WithKnownMasters(new KeyedMasterStyle(SfEsm, MasterStyle.Full)).Write();

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
        if (plain.MQ101Debug != DefaultMQ101Debug || !plain.Hold.SequenceEqual(DefaultHold)) { Console.WriteLine("FAIL  the default options"); return 1; }
        if (Options.From(new[] { "--no-mq101debug" }).MQ101Debug is not null || Options.From(new[] { "--mq101debug", "8" }).MQ101Debug != 8) { Console.WriteLine("FAIL  the MQ101Debug options"); return 1; }
        if (plain.RaceMenuMode != DefaultRaceMenuMode || Options.From(new[] { "--race-menu-mode", "1" }).RaceMenuMode != 1) { Console.WriteLine("FAIL  the race menu mode option"); return 1; }
        if (!plain.Special || Options.From(new[] { "--no-special" }).Special) { Console.WriteLine("FAIL  the SPECIAL option"); return 1; }
        if (!plain.Version || plain.BuildVersion != DefaultBuildVersion || Options.From(new[] { "--no-version" }).Version ||
            Options.From(new[] { "--build-version", "2" }).BuildVersion != 2) { Console.WriteLine("FAIL  the version options"); return 1; }
        // the inventory reset is off by default; the suit needs the reset and an EditorID
        if (plain.ClearInventory || plain.VaultSuit is not null || !Options.From(new[] { "--clear-inventory" }).ClearInventory ||
            Options.From(new[] { "--clear-inventory", "--vault-suit", SuitEdid }) is not { ClearInventory: true, VaultSuit: SuitEdid }) { Console.WriteLine("FAIL  the inventory options"); return 1; }
        foreach (var (why, bad) in new[] { ("--vault-suit without --clear-inventory", new[] { "--vault-suit", SuitEdid }), ("--vault-suit without an EditorID", new[] { "--clear-inventory", "--vault-suit" }),
                                           ("--vault-suit followed by another option", new[] { "--clear-inventory", "--vault-suit", "--no-looks" }) })
        {
            try { Options.From(bad); Console.WriteLine($"FAIL  options accepted {why}"); return 1; }
            catch (Refusal e) { Console.WriteLine($"refused as expected ({why}): {e.Message}"); }
        }
        var clear = plain with { ClearInventory = true };
        var suit = clear with { VaultSuit = SuitEdid };
        var variants = new (string Name, string Ids, Options O)[]
        {
            ("clear", idsPath, clear), ("suit", idsPath, suit),
            ("default", idsPath, plain), ("nolooks", idsPath, plain with { Looks = false }),
            ("nodebug", idsPath, plain with { MQ101Debug = null }), ("debug8", idsPath, plain with { MQ101Debug = 8 }),
            ("nocog", noCogIds, plain), ("hold2", idsPath, plain with { Hold = new[] { "MQ00", "MQ101" } }),
            ("mode1", idsPath, plain with { RaceMenuMode = 1 }), ("nospecial", idsPath, plain with { Special = false }),
            ("nearterm", nearTermIds, plain),
            ("noversion", idsPath, plain with { Version = false }), ("version2", idsPath, plain with { BuildVersion = 2 }),
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
            ("default", plain with { Looks = false }, idsPath, "a looks build as a no-looks one"),
            ("nolooks", plain, idsPath, "a no-looks build as a looks one"),
            ("default", plain with { MQ101Debug = null }, idsPath, "the default (MQ101Debug 10) build as a --no-mq101debug one"),
            ("nodebug", plain, idsPath, "a --no-mq101debug build as the default one"),
            ("default", plain with { MQ101Debug = 8 }, idsPath, "the default build as an MQ101Debug 8 one"),
            ("debug8", plain, idsPath, "an MQ101Debug 8 build as the default one"),
            ("nocog", plain, idsPath, "a build without the cog door against a port with it"),
            ("default", plain with { Hold = new[] { "MQ00", "MQ101" } }, idsPath, "the default hold list as the two-quest one"),
            ("hold2", plain, idsPath, "a two-quest hold list as the default one"),
            ("default", plain with { RaceMenuMode = 1 }, idsPath, "the default (race menu mode 0) build as a mode 1 one"),
            ("mode1", plain, idsPath, "a race menu mode 1 build as the default one"),
            ("default", plain with { Special = false }, idsPath, "a SPECIAL build as a --no-special one"),
            ("nospecial", plain, idsPath, "a --no-special build as a SPECIAL one"),
            ("default", plain, nearTermIds, "a build on the persistent terminal against a port with only the temporary one"),
            ("nearterm", plain, idsPath, "a build on the temporary terminal against a port with the persistent one"),
            ("default", plain with { Version = false }, idsPath, "a version-check build as a --no-version one"),
            ("noversion", plain, idsPath, "a --no-version build as a version-check one"),
            ("default", plain with { BuildVersion = 2 }, idsPath, "the default (build version 1) build as a version 2 one"),
            ("version2", plain, idsPath, "a build version 2 build as the default one"),
            ("default", clear, idsPath, "the default (inventory kept) build as a --clear-inventory one"),
            ("clear", plain, idsPath, "a --clear-inventory build as the default one"),
            ("clear", suit, idsPath, "a --clear-inventory build without a suit as a --vault-suit one"),
            ("suit", clear, idsPath, "a --vault-suit build as a --clear-inventory one without a suit"),
            ("suit", plain, idsPath, "a --vault-suit build as the default one"),
        };
        foreach (var (build, o, ids, why) in crosses)
        {
            if (Check(Path.Combine(outDir, build, Plugin), sfPath, portPath, ids, corePath, pointsPath, o) == 0) { Console.WriteLine($"FAIL  check passed {why}"); return 1; }
            Console.WriteLine($"rejected: {why}");
        }
        var good = Path.Combine(outDir, "default", Plugin);
        var mutations = new (string Name, Action<SF.StarfieldMod> Edit)[]
        {
            ("not start game enabled", m => m.Quests.First().Data!.Flags &= ~SF.Quest.Flag.StartGameEnabled),
            ("not run once", m => m.Quests.First().Data!.Flags &= ~SF.Quest.Flag.RunOnce),
            ("a stage missing", m => m.Quests.First().Stages.RemoveAt(0)),
            ("the vault anchor id changed", m => ((SF.ScriptIntProperty)m.Quests.First().VirtualMachineAdapter!.Scripts[0].Properties.First(p => p.Name == "VaultAnchorId")).Data = 0x999),
            ("a position changed", m => ((SF.ScriptFloatProperty)m.Quests.First().VirtualMachineAdapter!.Scripts[0].Properties.First(p => p.Name == "ArrivalX")).Data += 1),
            ("the merge offset changed", m => ((SF.ScriptFloatProperty)m.Quests.First().VirtualMachineAdapter!.Scripts[0].Properties.First(p => p.Name == "MergeOffsetY")).Data = 0),
            ("a property removed", m => m.Quests.First().VirtualMachineAdapter!.Scripts[0].Properties.RemoveAll(p => p.Name == "PodHeading")),
            ("the hold list emptied", m => ((SF.ScriptObjectListProperty)m.Quests.First().VirtualMachineAdapter!.Scripts[0].Properties.First(p => p.Name == "HoldOff")).Objects.Clear()),
            ("the hold list lost MQ101PostQuest", m => ((SF.ScriptObjectListProperty)m.Quests.First().VirtualMachineAdapter!.Scripts[0].Properties.First(p => p.Name == "HoldOff")).Objects.RemoveAt(2)),
            ("the MQ101Debug override reads 0", m => m.Globals.First(g => g.EditorID == "MQ101Debug").Data = 0),
            ("the MQ101Debug override removed", m => m.Globals.Remove(m.Globals.First(g => g.EditorID == "MQ101Debug").FormKey)),
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
            ("the opening choice removed", m => m.Messages.Remove(m.Messages.First(x => x.EditorID == StartMessageEdid).FormKey)),
            ("the race menu mode changed", m => ((SF.ScriptIntProperty)m.Quests.First().VirtualMachineAdapter!.Scripts[1].Properties.First(p => p.Name == "RaceMenuMode")).Data = 3),
            ("the looks script lost StartMessage", m => m.Quests.First().VirtualMachineAdapter!.Scripts[1].Properties.RemoveAll(p => p.Name == "StartMessage")),
            ("the quest has no QuestType", m => m.Quests.First().QuestType.Clear()),
            ("an AVIF removed", m => m.ActorValueInformation.Remove(m.ActorValueInformation.First(a => a.EditorID == SpecialAvifPrefix + "Luck").FormKey)),
            ("an AVIF's maximum changed", m => m.ActorValueInformation.First(a => a.EditorID == SpecialAvifPrefix + "Strength").Max = 11),
            ("an AVIF's flags cleared", m => m.ActorValueInformation.First(a => a.EditorID == SpecialAvifPrefix + "Charisma").Flags = 0),
            ("the allocation lost its Leave button", m => m.Messages.First(x => x.EditorID == SpecialMessageEdid).MenuButtons.RemoveAt(9)),
            ("the allocation's text lost a token", m => m.Messages.First(x => x.EditorID == SpecialMessageEdid).Description = "S.P.E.C.I.A.L."),
            ("the terminal prompt removed", m => m.Messages.Remove(m.Messages.First(x => x.EditorID == TerminalMessageEdid).FormKey)),
            ("the SPECIAL list order swapped", m => { var l = (SF.ScriptObjectListProperty)m.Quests.First().VirtualMachineAdapter!.Scripts[2].Properties.First(p => p.Name == "Special"); (l.Objects[0], l.Objects[6]) = (l.Objects[6], l.Objects[0]); }),
            ("the terminal id changed", m => ((SF.ScriptIntProperty)m.Quests.First().VirtualMachineAdapter!.Scripts[2].Properties.First(p => p.Name == "TerminalId")).Data = 0x807),
            ("the terminal spot changed", m => ((SF.ScriptFloatProperty)m.Quests.First().VirtualMachineAdapter!.Scripts[2].Properties.First(p => p.Name == "TerminalX")).Data += 1),
            ("the inventory reset switched on", m => ((SF.ScriptBoolProperty)m.Quests.First().VirtualMachineAdapter!.Scripts[0].Properties.First(p => p.Name == "ClearInventory")).Data = true),
            ("a vault suit id without the option", m => ((SF.ScriptIntProperty)m.Quests.First().VirtualMachineAdapter!.Scripts[0].Properties.First(p => p.Name == "VaultSuitId")).Data = 0x820),
            ("ClearInventory removed", m => m.Quests.First().VirtualMachineAdapter!.Scripts[0].Properties.RemoveAll(p => p.Name == "ClearInventory")),
        };
        foreach (var (name, edit) in mutations)
        {
            var mod = SF.StarfieldMod.CreateFromBinary(good, rel, Full(SfEsm));
            edit(mod);
            var md = Path.Combine(outDir, "mutated");
            Directory.CreateDirectory(md);
            mod.BeginWrite.ToPath(Path.Combine(md, Plugin)).WithLoadOrder(SfEsm).WithKnownMasters(new KeyedMasterStyle(SfEsm, MasterStyle.Full)).Write();
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
            // the vault anchor is persistent: a temporary COC marker gives way to the nearest persistent reference
            // of the port in the cell; a persistent COC marker is used itself; none at all is refused
            if (Resolve(portPath, idsPath, corePath, ExitAnchorEdid, terms).VaultAnchor != 0x805) { Console.WriteLine("FAIL  the anchor is not the nearest persistent reference"); return 1; }
            var persCoc = Port(m => { var c = VCell(m); var r = (SF.PlacedObject)c.Temporary.First(x => x.FormKey.ID == 0x801); c.Temporary.Remove(r); r.MajorRecordFlagsRaw |= 0x400; c.Persistent.Add(r); });
            if (Resolve(persCoc, idsPath, corePath, ExitAnchorEdid, terms).VaultAnchor != 0x801) { Console.WriteLine("FAIL  a persistent COC marker is not the anchor"); return 1; }
            var noPers = Port(m => VCell(m).Persistent.Clear());
            try { Resolve(noPers, idsPath, corePath, ExitAnchorEdid, terms); Console.WriteLine("FAIL  resolve accepted a vault with no persistent reference"); return 1; }
            catch (Refusal e) { Console.WriteLine($"refused as expected (no persistent reference in the vault): {e.Message}"); }
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
        try { Write(sfPath, portPath, idsPath, corePath, pointsPath, Path.Combine(outDir, "refused"), clear with { VaultSuit = "FO4Port_NoSuchSuit" }); Console.WriteLine("FAIL  write accepted a vault suit the port lacks"); return 1; }
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
        // refusals: a hold quest Starfield lacks, an exit anchor the core lacks
        foreach (var (why, o) in new[] { ("an unknown hold quest", plain with { Hold = new[] { "MQ999" } }), ("an unknown exit anchor", plain with { ExitAnchor = "NoSuchMarker" }) })
        {
            try { Write(sfPath, portPath, idsPath, corePath, pointsPath, Path.Combine(outDir, "refused"), o); Console.WriteLine($"FAIL  write accepted {why}"); return 1; }
            catch (Refusal e) { Console.WriteLine($"refused as expected ({why}): {e.Message}"); }
        }
        // the records reader (Records.cs): its own synthetic plugins, under this scratch dir
        if (NewGameRecords.SelfTest(Path.Combine(dir, "records")) != 0) return 1;
        Console.WriteLine("selftest pass");
        return 0;
    }
}
