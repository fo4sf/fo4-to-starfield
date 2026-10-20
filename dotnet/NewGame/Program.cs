// NewGame: a Fallout 4 new game in Starfield (docs/newgame/vault111-start.md): one plugin, FO4SFNewGame.esm, whose
// start-game-enabled quest holds off Starfield's opening, puts the player at their cryo pod in the converted Vault 111
// (FO4Port.esm) and takes them up the elevator onto the Commonwealth (FO4TerrainCore.esm). Claude's project.
//
//   points <Fallout4.esm> <out points.json> [--pod-ref <hex>] [--pod-step 1.0]
//        reads Fallout 4 only: in Vault111Cryo (000016D8) the player's cryo pod (the one placed reference whose
//        EditorID names both the player and a pod, or --pod-ref), the cog door console MQ102GearDoorConsoleREF 00091A49,
//        the cog door Vault111GearDoorREF 000330C3, the elevator platform V111ElevatorREF 000244EB, and the surface
//        arrival of the ride (the XTEL of Vault111InteriorAutoLoadDoorREF 0001F180); MQ102's name. Interior positions
//        in metres in the port's frame and exterior ones in the core's (both FO4 position / 70); headings in degrees.
//   write <Starfield.esm> <FO4Port.esm> <port formids.json> <FO4TerrainCore.esm> <points.json> <out dir>
//         [--plugin FO4SFNewGame.esm] [--hold MQ00,MQ101] [--mq101debug <n>] [--no-looks] [--exit-anchor <REFR EditorID>]
//        the plugin, mastered on Starfield.esm only: QUST FO4SF_NewGame (start game enabled, run once; stages 1 / 10 /
//        20 / 30 / 40 / 200; objective 10) carrying FO4SF_NewGameQuest (and FO4SF_NewGameLooks unless --no-looks) with
//        its properties, and MESG FO4SF_NewGameElevator (two buttons). The port and the core are read for the ids and
//        positions the script resolves at run time with Game.GetFormFromFile (plugin-local ids): the vault anchor (the
//        COC marker of FO4Port_Vault111Cryo), the cog door (formids.json REFR:FO4Port_Vault111Cryo:0330C3:...; 0 when
//        the port has none) and the exit anchor (the core's Vault 111 map marker). --mq101debug also overrides
//        Starfield's GLOB MQ101Debug (the debug start path; off by default, see the doc).
//   check <plugin> <Starfield.esm> <FO4Port.esm> <port formids.json> <FO4TerrainCore.esm> <points.json> [same options]
//        reads the plugin back and checks every record, property and id the script relies on (exit 1 on a problem).
//   selftest <scratch dir>
//        synthetic Fallout4.esm, Starfield.esm, port and core; points + write + check, and mutations check rejects.
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
        "points" when args.Length >= 3 => NewGame.Points(args[1], args[2], NewGame.ArgOrNull(args, "--pod-ref"), NewGame.Opt(args, "--pod-step", 1.0f)),
        "write" when args.Length >= 7 => NewGame.Write(args[1], args[2], args[3], args[4], args[5], args[6], NewGame.Options.From(args)),
        "check" when args.Length >= 7 => NewGame.Check(args[1], args[2], args[3], args[4], args[5], args[6], NewGame.Options.From(args)),
        "selftest" when args.Length >= 2 => NewGame.SelfTest(args[1]),
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
    public const string QuestEdid = "FO4SF_NewGame", ScriptName = "FO4SF_NewGameQuest", LooksScript = "FO4SF_NewGameLooks";
    public const string MessageEdid = "FO4SF_NewGameElevator", ExitAnchorEdid = "FO4Core_CommonwealthMapMarkerVault111";
    public const uint QuestId = 0x800, MessageId = 0x801, MQ101DebugOverride = 0;  // the GLOB override keeps Starfield's id
    // Starfield.esm, verified: QuestTypeSideQuest (the mission, Missions tab), GameDaysPassed (FLTV 0 on a new game,
    // docs/ai/test-queue.md), COCMarkerHeading (the port places each cell's COC marker on it, WP10)
    public const uint QuestTypeSideId = 0x047600, GameDaysPassedId = 0x000039, CocMarkerId = 0x000032;
    public const string QuestTypeSideEdid = "QuestTypeSideQuest", GameDaysPassedEdid = "GameDaysPassed";
    // Fallout4.esm, verified in docs/spikes/B4-mission-anatomy.md section 3
    public const uint Fo4VaultCell = 0x0016D8, Fo4Console = 0x091A49, Fo4CogDoor = 0x0330C3, Fo4Platform = 0x0244EB,
                      Fo4ExitDoor = 0x01F180, Fo4MQ102 = 0x01CC2A;
    public static readonly string[] DefaultHold = { "MQ00", "MQ101" };
    // the stages and the objective FO4SF_NewGameQuest.psc drives
    public static readonly ushort[] Stages = { 1, 10, 20, 30, 40, 200 };
    public const ushort Objective = 10;
    public const string ObjectiveText = "Leave Vault 111";
    public const float Units = 70f, MergeX = -1200f, MergeY = -2700f;   // FO4 units per metre; vmad_patch.MERGE_MEASURED
    static readonly ModKey SfEsm = ModKey.FromFileName("Starfield.esm");

    public class Refusal(string m) : Exception(m);

    public static int Usage()
    {
        Console.Error.WriteLine("usage: see the header of dotnet/NewGame/Program.cs (points | write | check | selftest)");
        return 2;
    }
    public static string? ArgOrNull(string[] a, string name) { var i = Array.IndexOf(a, name); return i >= 0 && i + 1 < a.Length ? a[i + 1] : null; }
    public static float Opt(string[] a, string name, float dflt) =>
        ArgOrNull(a, name) is { } v ? float.Parse(v, CultureInfo.InvariantCulture) : dflt;
    static string F(float v) => v.ToString("0.###", CultureInfo.InvariantCulture);
    static float Deg(float rad) => rad * 180f / MathF.PI;

    public record Options(string Plugin, string[] Hold, float? MQ101Debug, bool Looks, string ExitAnchor)
    {
        public static Options From(string[] a) => new(
            ArgOrNull(a, "--plugin") ?? NewGame.Plugin,
            (ArgOrNull(a, "--hold") ?? string.Join(",", DefaultHold)).Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries),
            ArgOrNull(a, "--mq101debug") is { } d ? float.Parse(d, CultureInfo.InvariantCulture) : null,
            !a.Contains("--no-looks"), ArgOrNull(a, "--exit-anchor") ?? ExitAnchorEdid);
    }

    // ---------------------------------------------------------------- points (Fallout 4, read only)

    public static int Points(string fo4Path, string outPath, string? podRef, float podStep)
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
        };
        Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(outPath))!);
        File.WriteAllText(outPath, JsonSerializer.Serialize(doc, new JsonSerializerOptions { WriteIndented = true }));
        Console.WriteLine($"wrote {outPath}: pod {pod.FormKey.ID:X8} {pod.EditorID}, stand ({F(stand[0])}, {F(stand[1])}, {F(stand[2])}) m heading {F(Deg(h))}; " +
                          $"arrival ({F(tel.Position.X / Units)}, {F(tel.Position.Y / Units)}, {F(tel.Position.Z / Units)}) m; quest \"{mq102}\"");
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

    public record Places(uint VaultAnchor, P3Float AnchorPos, uint CogDoor, string CogDoorBase, uint ExitAnchor, P3Float ExitPos);

    static BinaryReadParameters Full(params ModKey[] keys)
    {
        var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        foreach (var k in keys) styles.Set(new KeyedMasterStyle(k, MasterStyle.Full));
        return new BinaryReadParameters { MasterFlagsLookup = styles };
    }

    /// The vault anchor (the one COC marker of FO4Port_Vault111Cryo), the cog door (formids.json's key for FO4 000330C3
    /// in that cell, 0 when absent, and it must be a reference of that cell) and the exit anchor (the core world's REFR
    /// with that EditorID, persistent).
    public static Places Resolve(string portPath, string portIds, string corePath, string exitAnchor)
    {
        using var port = SF.StarfieldMod.CreateFromBinaryOverlay(portPath, SF.StarfieldRelease.Starfield, Full(SfEsm));
        Owner(port.ModKey, PortPlugin, "the port");
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
        using (var doc = JsonDocument.Parse(File.ReadAllText(portIds)))
            foreach (var e in doc.RootElement.EnumerateObject())
                if (IsCogDoorKey(e.Name)) { cog = e.Value.GetUInt32(); break; }
        if (cog != 0)
        {
            var r = inCell.FirstOrDefault(x => x.FormKey.ID == cog) ?? throw new Refusal($"formids.json names {cog:X6} as the cog door, not a reference of {VaultCell}");
            Owned(r, port.ModKey, "the cog door");
            cogBase = port.EnumerateMajorRecords().FirstOrDefault(x => x.FormKey == r.Base.FormKey) is { } b ? $"{b.GetType().Name.Replace("BinaryOverlay", "")} {b.EditorID}" : r.Base.FormKey.ToString();
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
        return new Places(anchor.FormKey.ID, anchor.Position, cog, cogBase, exits[0].FormKey.ID, exits[0].Position);
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
    public static bool IsCogDoorKey(string key)
    {
        var prefix = $"REFR:{VaultCell}:";
        if (!key.StartsWith(prefix, StringComparison.OrdinalIgnoreCase)) return false;
        var parts = key[prefix.Length..].Split(':');
        return parts.Length == 2 && parts[1].Equals("Fallout4.esm", StringComparison.OrdinalIgnoreCase) &&
               uint.TryParse(parts[0], System.Globalization.NumberStyles.HexNumber, null, out var id) && id == Fo4CogDoor;
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
        };
    }

    public static int Write(string sfPath, string portPath, string portIds, string corePath, string pointsPath, string outDir, Options o)
    {
        var pts = JsonDocument.Parse(File.ReadAllText(pointsPath)).RootElement;
        var places = Resolve(portPath, portIds, corePath, o.ExitAnchor);
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
            script.Properties.Add(value switch
            {
                int i => new SF.ScriptIntProperty { Name = name, Flags = SF.ScriptProperty.Flag.Edited, Data = i },
                float f => (SF.ScriptProperty)new SF.ScriptFloatProperty { Name = name, Flags = SF.ScriptProperty.Flag.Edited, Data = f },
                _ => throw new Refusal($"property {name}: unsupported value"),
            });
        quest.VirtualMachineAdapter = new SF.QuestAdapter
        {
            Version = 6, ObjectFormat = 2, ExtraBindDataVersion = 3,
            Script = new SF.ScriptEntry { Name = "", Flags = SF.ScriptEntry.Flag.Local },
        };
        quest.VirtualMachineAdapter.Scripts.Add(script);
        if (o.Looks) quest.VirtualMachineAdapter.Scripts.Add(new SF.ScriptEntry { Name = LooksScript, Flags = SF.ScriptEntry.Flag.Local });
        mod.Quests.Add(quest);

        if (o.MQ101Debug is { } dbg)
        {
            var g = sf.Globals.FirstOrDefault(x => x.EditorID == "MQ101Debug") ?? throw new Refusal("Starfield.esm has no GLOB MQ101Debug");
            var over = (SF.Global)g.DeepCopy();
            over.Data = dbg;
            mod.Globals.Add(over);
        }
        mod.ModHeader.Stats.NextFormID = MessageId + 1;
        Directory.CreateDirectory(outDir);
        var path = Path.Combine(outDir, o.Plugin);
        mod.BeginWrite.ToPath(path).WithLoadOrder(SfEsm).WithKnownMasters(new KeyedMasterStyle(SfEsm, MasterStyle.Full)).Write();
        Console.WriteLine($"wrote {path} ({new FileInfo(path).Length:N0} bytes): QUST {QuestEdid} {quest.FormKey} \"{quest.Name}\" " +
                          $"hold [{string.Join(", ", o.Hold)}]; vault anchor FO4Port.esm:{places.VaultAnchor:X6} at {Show(places.AnchorPos)}, " +
                          $"cog door {(places.CogDoor == 0 ? "none" : $"{places.CogDoor:X6} ({places.CogDoorBase})")}, exit anchor " +
                          $"FO4TerrainCore.esm:{places.ExitAnchor:X6} at {Show(places.ExitPos)}; looks {(o.Looks ? "on" : "off")}" +
                          (o.MQ101Debug is { } d2 ? $"; GLOB MQ101Debug = {F(d2)}" : ""));
        return 0;
    }

    // ---------------------------------------------------------------- check

    public static int Check(string pluginPath, string sfPath, string portPath, string portIds, string corePath, string pointsPath, Options o)
    {
        var problems = new List<string>();
        void Need(bool ok, string what) { if (!ok) problems.Add(what); }
        var pts = JsonDocument.Parse(File.ReadAllText(pointsPath)).RootElement;
        var places = Resolve(portPath, portIds, corePath, o.ExitAnchor);
        using var sf = SF.StarfieldMod.CreateFromBinaryOverlay(sfPath, SF.StarfieldRelease.Starfield);
        using var plug = SF.StarfieldMod.CreateFromBinaryOverlay(pluginPath, SF.StarfieldRelease.Starfield, Full(SfEsm));
        var key = plug.ModKey;
        var masters = plug.ModHeader.MasterReferences.Select(x => x.Master.FileName.String).ToList();
        Console.WriteLine($"{key}: header {plug.ModHeader.Flags}, masters [{string.Join(", ", masters)}], {plug.Quests.Count} QUST, " +
                          $"{plug.Messages.Count} MESG, {plug.Globals.Count} GLOB");
        Need(plug.ModHeader.Flags.HasFlag(SF.StarfieldModHeader.HeaderFlag.Master), "not flagged as a master");
        Need(masters.SequenceEqual(new[] { "Starfield.esm" }), "masters are not Starfield.esm alone (the port and the core are resolved at run time)");
        Need(plug.Npcs.Count == 0 && plug.Worldspaces.Count == 0 && plug.Cells.Count == 0, "the plugin carries NPC_, WRLD or CELL records (it places nothing)");

        var msg = plug.Messages.FirstOrDefault(m => m.FormKey == new FormKey(key, MessageId));
        Need(msg is { EditorID: MessageEdid } && msg.Flags.HasFlag(SF.Message.Flag.MessageBox) && msg.MenuButtons.Count == 2 &&
             msg.MenuButtons.All(b => !string.IsNullOrWhiteSpace(b.Text?.String)), $"MESG 0x{MessageId:X} is not {MessageEdid}, a message box with two buttons");

        var globals = plug.Globals.ToList();
        if (o.MQ101Debug is { } dbg)
        {
            var src = sf.Globals.FirstOrDefault(g => g.EditorID == "MQ101Debug");
            Need(globals.Count == 1 && src is not null && globals[0].FormKey == src.FormKey && globals[0].Data == dbg,
                 $"GLOB MQ101Debug is not overridden to {F(dbg)}");
        }
        else Need(globals.Count == 0, "a build without --mq101debug overrides a GLOB");

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
            Need((q.Aliases?.Count ?? 0) == 0 && q.DialogTopics.Count == 0, "the quest carries aliases or dialogue");
            var scripts = q.VirtualMachineAdapter?.Scripts.Select(s => s.Name).ToList() ?? new();
            Need(scripts.SequenceEqual(o.Looks ? new[] { ScriptName, LooksScript } : new[] { ScriptName }),
                 $"scripts [{string.Join(", ", scripts)}] are not {ScriptName}{(o.Looks ? " + " + LooksScript : " alone")}");
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
                {
                    bool ok = props.TryGetValue(name, out var p) && (value, p) switch
                    {
                        (int i, SF.IScriptIntPropertyGetter ip) => ip.Data == i,
                        (float f, SF.IScriptFloatPropertyGetter fp) => fp.Data == f && float.IsFinite(fp.Data),
                        _ => false,
                    };
                    Need(ok, $"property {name} is not {value}");
                }
                Need(props.Count == expected.Count + 3, $"{props.Count} properties, expected {expected.Count + 3}");
                Need(places.VaultAnchor > 0 && places.ExitAnchor > 0, "an anchor id is 0");
            }
            else problems.Add($"script {ScriptName} not attached");
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
        var pcell = new SF.Cell(new FormKey(portKey, 0x800), rel) { EditorID = VaultCell, Flags = SF.Cell.Flag.IsInteriorCell };
        pcell.Temporary.Add(new SF.PlacedObject(new FormKey(portKey, 0x801), rel) { Base = new FormLinkNullable<SF.IPlaceableObjectGetter>(new FormKey(SfEsm, CocMarkerId)), Position = new P3Float(60, 15, 1) });
        pcell.Temporary.Add(new SF.PlacedObject(new FormKey(portKey, 0x802), rel) { Base = new FormLinkNullable<SF.IPlaceableObjectGetter>(pdoor.FormKey), Position = new P3Float(52, 10, 0) });
        // persistent references of the port in the cell (the converted load doors are): the COC marker is temporary, so
        // the anchor is the nearer of these two
        SF.PlacedObject Pers(uint id, float x, float y, float z) { var r = new SF.PlacedObject(new FormKey(portKey, id), rel) { Base = new FormLinkNullable<SF.IPlaceableObjectGetter>(pdoor.FormKey), Position = new P3Float(x, y, z) }; r.MajorRecordFlagsRaw |= 0x400; return r; }
        pcell.Persistent.Add(Pers(0x805, 60, 25, 1));
        pcell.Persistent.Add(Pers(0x806, 90, 40, 20));
        var pb = new SF.CellBlock { BlockNumber = 0, GroupType = SF.GroupTypeEnum.InteriorCellBlock };
        var ps = new SF.CellSubBlock { BlockNumber = 0, GroupType = SF.GroupTypeEnum.InteriorCellSubBlock };
        ps.Cells.Add(pcell);
        pb.SubBlocks.Add(ps);
        port.Cells.Records.Add(pb);
        port.ModHeader.Stats.NextFormID = 0x811;
        var portPath = Path.Combine(dir, portKey.FileName);
        port.BeginWrite.ToPath(portPath).WithLoadOrder(SfEsm).WithKnownMasters(new KeyedMasterStyle(SfEsm, MasterStyle.Full)).Write();
        var idsPath = Path.Combine(dir, "formids.json");
        File.WriteAllText(idsPath, $"{{\"CELL:{VaultCell}\": {0x800}, \"REFR:{VaultCell}:0330C3:Fallout4.esm\": {0x802}, \"DOOR:FO4Port_VltGearDoor01\": {0x810}}}");
        var noCogIds = Path.Combine(dir, "formids_nocog.json");
        File.WriteAllText(noCogIds, $"{{\"CELL:{VaultCell}\": {0x800}}}");
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
        var variants = new (string Name, string Ids, Options O)[]
        {
            ("default", idsPath, plain), ("nolooks", idsPath, plain with { Looks = false }),
            ("debug8", idsPath, plain with { MQ101Debug = 8 }), ("nocog", noCogIds, plain),
            ("hold1", idsPath, plain with { Hold = new[] { "MQ101" } }),
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
            ("default", plain with { MQ101Debug = 8 }, idsPath, "a plain build as an MQ101Debug one"),
            ("debug8", plain, idsPath, "an MQ101Debug build as a plain one"),
            ("nocog", plain, idsPath, "a build without the cog door against a port with it"),
            ("default", plain with { Hold = new[] { "MQ101" } }, idsPath, "another hold list"),
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
            ("the elevator prompt has one button", m => m.Messages.First().MenuButtons.RemoveAt(1)),
            ("the quest has no QuestType", m => m.Quests.First().QuestType.Clear()),
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
            foreach (var (why, p, c) in new[] { ("a COC marker owned by Starfield.esm", foreignCoc, corePath), ("a cog door owned by Starfield.esm", foreignCog, corePath),
                                                ("a port under another file name", renamed, corePath), ("an exit anchor owned by Starfield.esm", portPath, foreignCore) })
            {
                try { Resolve(p, idsPath, c, ExitAnchorEdid); Console.WriteLine($"FAIL  resolve accepted {why}"); return 1; }
                catch (Refusal e) { Console.WriteLine($"refused as expected ({why}): {e.Message}"); }
            }
            // the vault anchor is persistent: a temporary COC marker gives way to the nearest persistent reference
            // of the port in the cell; a persistent COC marker is used itself; none at all is refused
            if (Resolve(portPath, idsPath, corePath, ExitAnchorEdid).VaultAnchor != 0x805) { Console.WriteLine("FAIL  the anchor is not the nearest persistent reference"); return 1; }
            var persCoc = Port(m => { var c = VCell(m); var r = (SF.PlacedObject)c.Temporary.First(x => x.FormKey.ID == 0x801); c.Temporary.Remove(r); r.MajorRecordFlagsRaw |= 0x400; c.Persistent.Add(r); });
            if (Resolve(persCoc, idsPath, corePath, ExitAnchorEdid).VaultAnchor != 0x801) { Console.WriteLine("FAIL  a persistent COC marker is not the anchor"); return 1; }
            var noPers = Port(m => VCell(m).Persistent.Clear());
            try { Resolve(noPers, idsPath, corePath, ExitAnchorEdid); Console.WriteLine("FAIL  resolve accepted a vault with no persistent reference"); return 1; }
            catch (Refusal e) { Console.WriteLine($"refused as expected (no persistent reference in the vault): {e.Message}"); }
        }
        // refusals: a hold quest Starfield lacks, an exit anchor the core lacks
        foreach (var (why, o) in new[] { ("an unknown hold quest", plain with { Hold = new[] { "MQ999" } }), ("an unknown exit anchor", plain with { ExitAnchor = "NoSuchMarker" }) })
        {
            try { Write(sfPath, portPath, idsPath, corePath, pointsPath, Path.Combine(outDir, "refused"), o); Console.WriteLine($"FAIL  write accepted {why}"); return 1; }
            catch (Refusal e) { Console.WriteLine($"refused as expected ({why}): {e.Message}"); }
        }
        Console.WriteLine("selftest pass");
        return 0;
    }
}
