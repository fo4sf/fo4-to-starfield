// ALife: A-Life slice 1 (docs/alife/alife-slice1.md) as one Starfield plugin on top of the converted Commonwealth core
// and the converted raider: the controller quest FO4SF_ALife carrying FO4SF_ALifeControllerQuest, the squad member,
// our Minutemen faction, a pool of reusable waymarkers, and the north-west offline graph as script properties.
//
//   write <Starfield.esm> <FO4TerrainCore.esm> <FO4ActorRaider.esm> <nw_subgraph.json> <out dir> [--plugin FO4SFALife.esm]
//         [--world FO4Core_Commonwealth] [--pool 4]
//        QUST FO4SF_ALife (start game enabled, not run once, kept out of the HUD) with the script and its properties;
//        FACT FO4SF_ALifeMinutemenFaction (Ally to PlayerFaction); NPC_ FO4SF_ALife_Minuteman (a copy of the raider
//        plugin's calm probe FO4_LvlRaider_Calm, docs/actors/raider-conversion.md: no Enemy relation, walks on
//        command, in our faction only, not unique, no respawn); --pool persistent XMarkerHeading REFRs
//        FO4SF_ALife_Waymarker_01.. in the core world's persistent cell (a WRLD + persistent CELL override of the
//        core holding only them, as dotnet/Mission does), at rung 1a's start spot until the script moves them; and
//        the graph (scripts/alife/nw_subgraph.json, make_alife.py graph) as float/int array properties.
//   check <plugin> <Starfield.esm> <FO4TerrainCore.esm> <FO4ActorRaider.esm> <nw_subgraph.json> [--pool 4]
//        reads the plugin back and checks every record, link and property value the script relies on (exit 1 on a
//        problem).
//   selftest <scratch dir>
//        synthetic masters and a synthetic graph; write + check, then mutations of the output that check must
//        reject, and graphs that write must refuse. No game file is read.
// Nothing is deployed and no game file is written.
using System.Globalization;
using System.Text.Json;
using Mutagen.Bethesda;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Cache;
using Mutagen.Bethesda.Plugins.Records;
using Noggog;
using SF = Mutagen.Bethesda.Starfield;

if (args.Length == 0) return ALife.Usage();
try
{
    return args[0] switch
    {
        "write" when args.Length >= 6 => ALife.Write(args[1], args[2], args[3], args[4], args[5], ALife.Arg(args, "--plugin", ALife.Plugin),
                                                     ALife.Arg(args, "--world", ALife.World), int.Parse(ALife.Arg(args, "--pool", "4"), CultureInfo.InvariantCulture)),
        "check" when args.Length >= 6 => ALife.Check(args[1], args[2], args[3], args[4], args[5], int.Parse(ALife.Arg(args, "--pool", "4"), CultureInfo.InvariantCulture)),
        "selftest" when args.Length >= 2 => ALife.SelfTest(args[1]),
        _ => ALife.Usage(),
    };
}
catch (ALife.Refusal e)
{
    Console.Error.WriteLine("refused: " + e.Message);
    return 2;
}

static class ALife
{
    public const string Plugin = "FO4SFALife.esm", World = "FO4Core_Commonwealth";
    public const string QuestEdid = "FO4SF_ALife", ScriptName = "FO4SF_ALifeControllerQuest";
    public const string FactionEdid = "FO4SF_ALifeMinutemenFaction", NpcEdid = "FO4SF_ALife_Minuteman", WaymarkerEdid = "FO4SF_ALife_Waymarker_";
    public const uint QuestId = 0x800, FactionId = 0x801, NpcId = 0x802, FirstWaymarkerId = 0x810;
    public const int MaxPool = 16, ArrayCap = 128;                         // Papyrus arrays hold at most 128 elements
    public const uint CalmProbeId = 0xF04801;                              // FO4ActorRaider.esm FO4_LvlRaider_Calm
    public const uint PlayerFactionId = 0x01C21C; public const string PlayerFactionEdid = "PlayerFaction";
    public const uint XMarkerHeadingId = 0x000034; public const string XMarkerHeadingEdid = "XMarkerHeading";   // dotnet/MapMarkers
    // the script's Auto Const Mandatory properties (make_alife.py PROPERTIES, same order)
    public static readonly string[] Properties =
    {
        "SquadBase", "SquadFaction", "Waymarkers", "NodeX", "NodeY", "NodeZ", "NodeCap", "EdgeU", "EdgeV", "EdgeLen",
        "Rung1aFrom", "Rung1aTo", "Rung1bFrom", "Rung1bGoal", "Rung1bExpectedM",
    };
    static readonly ModKey SfEsm = ModKey.FromFileName("Starfield.esm");

    public class Refusal(string m) : Exception(m);

    public static int Usage()
    {
        Console.Error.WriteLine("usage: see the header of dotnet/ALife/Program.cs (write | check | selftest)");
        return 2;
    }
    public static string Arg(string[] a, string name, string dflt) { var i = Array.IndexOf(a, name); return i >= 0 && i + 1 < a.Length ? a[i + 1] : dflt; }
    static string F(float v) => v.ToString("0.###", CultureInfo.InvariantCulture);

    // ---------------------------------------------------------------- graph

    public record Node(string Edid, float X, float Y, float Z, int Cap);
    public record Edge(int U, int V, float Len);
    public record Graph(List<Node> Nodes, List<Edge> Edges, int R1aFrom, int R1aTo, int R1bFrom, int R1bGoal, float R1bLen);

    /// nw_subgraph.json as make_alife.py graph writes it, refused when it does not fit the script: at most 128 nodes and
    /// 128 edges (one Papyrus array each), edges between distinct existing nodes with a positive finite length, finite
    /// positions, capacities >= 0, the rung nodes in range and both rung destinations able to garrison.
    public static Graph LoadGraph(string path)
    {
        var j = JsonDocument.Parse(File.ReadAllText(path)).RootElement;
        var nodes = j.GetProperty("nodes").EnumerateArray().Select(n => new Node(n.GetProperty("edid").GetString() ?? "",
            n.GetProperty("x").GetSingle(), n.GetProperty("y").GetSingle(), n.GetProperty("z").GetSingle(), n.GetProperty("cap").GetInt32())).ToList();
        var edges = j.GetProperty("edges").EnumerateArray().Select(e => new Edge(e.GetProperty("u").GetInt32(), e.GetProperty("v").GetInt32(),
            e.GetProperty("len_m").GetSingle())).ToList();
        var a = j.GetProperty("rung1a"); var b = j.GetProperty("rung1b");
        var g = new Graph(nodes, edges, a.GetProperty("from").GetInt32(), a.GetProperty("to").GetInt32(), b.GetProperty("from").GetInt32(),
                          b.GetProperty("goal").GetInt32(), b.GetProperty("length_m").GetSingle());
        int n = nodes.Count;
        if (n < 2 || n > ArrayCap) throw new Refusal($"{n} nodes: 2..{ArrayCap} fit a Papyrus array");
        if (edges.Count < 1 || edges.Count > ArrayCap) throw new Refusal($"{edges.Count} edges: 1..{ArrayCap} fit a Papyrus array");
        foreach (var (e, i) in edges.Select((e, i) => (e, i)))
            if (e.U < 0 || e.U >= n || e.V < 0 || e.V >= n || e.U == e.V || !float.IsFinite(e.Len) || e.Len <= 0)
                throw new Refusal($"edge {i} ({e.U}, {e.V}, {e.Len}) is not between two nodes with a positive length");
        foreach (var (x, i) in nodes.Select((x, i) => (x, i)))
            if (!float.IsFinite(x.X) || !float.IsFinite(x.Y) || !float.IsFinite(x.Z) || x.Cap < 0) throw new Refusal($"node {i} {x.Edid}: position or capacity");
        foreach (var r in new[] { g.R1aFrom, g.R1aTo, g.R1bFrom, g.R1bGoal })
            if (r < 0 || r >= n) throw new Refusal($"rung node {r} is not a node");
        if (nodes[g.R1aTo].Cap <= 0 || nodes[g.R1bGoal].Cap <= 0) throw new Refusal("a rung destination cannot garrison (capacity 0)");
        if (!float.IsFinite(g.R1bLen) || g.R1bLen <= 0) throw new Refusal($"rung1b length {g.R1bLen}");
        return g;
    }

    // ---------------------------------------------------------------- write

    sealed record Masters(SF.IStarfieldModDisposableGetter Sf, SF.IStarfieldModDisposableGetter Core, SF.IStarfieldModDisposableGetter Raider,
                          ILinkCache<SF.IStarfieldMod, SF.IStarfieldModGetter> Cache) : IDisposable
    {
        public void Dispose() { Sf.Dispose(); Core.Dispose(); Raider.Dispose(); }
    }

    static BinaryReadParameters Styles(params ModKey[] full)
    {
        var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        foreach (var k in full) styles.Set(new KeyedMasterStyle(k, MasterStyle.Full));
        return new BinaryReadParameters { MasterFlagsLookup = styles };
    }

    static Masters Open(string sfPath, string corePath, string raiderPath)
    {
        var sf = SF.StarfieldMod.CreateFromBinaryOverlay(sfPath, SF.StarfieldRelease.Starfield);
        var core = SF.StarfieldMod.CreateFromBinaryOverlay(corePath, SF.StarfieldRelease.Starfield, Styles(SfEsm));
        var raider = SF.StarfieldMod.CreateFromBinaryOverlay(raiderPath, SF.StarfieldRelease.Starfield, Styles(SfEsm));
        var cache = new SF.IStarfieldModGetter[] { sf, core, raider }.ToImmutableLinkCache<SF.IStarfieldMod, SF.IStarfieldModGetter>();
        return new Masters(sf, core, raider, cache);
    }

    static SF.IWorldspaceGetter FindWorld(SF.IStarfieldModGetter core, string edid) =>
        core.Worldspaces.FirstOrDefault(w => w.EditorID == edid && w.FormKey.ModKey == core.ModKey)
        ?? throw new Refusal($"{core.ModKey} has no worldspace {edid}");

    public static int Write(string sfPath, string corePath, string raiderPath, string graphPath, string outDir, string plugin, string worldEdid, int pool)
    {
        if (pool < 2 || pool > MaxPool) throw new Refusal($"--pool {pool}: 2..{MaxPool} waymarkers (the route reuses them)");
        var g = LoadGraph(graphPath);
        using var m = Open(sfPath, corePath, raiderPath);
        var modKey = ModKey.FromFileName(plugin);
        var rel = SF.StarfieldRelease.Starfield;
        var mod = new SF.StarfieldMod(modKey, rel);
        mod.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Master;
        mod.ModHeader.Author = "fo4-to-starfield ALife";

        if (!m.Cache.TryResolve<SF.IFactionGetter>(new FormKey(SfEsm, PlayerFactionId), out var playerFaction) || playerFaction.EditorID != PlayerFactionEdid)
            throw new Refusal($"Starfield.esm {PlayerFactionId:X6} is not the FACT {PlayerFactionEdid}");
        if (!m.Cache.TryResolve<SF.IStaticGetter>(new FormKey(SfEsm, XMarkerHeadingId), out var xmarker) || xmarker.EditorID != XMarkerHeadingEdid)
            throw new Refusal($"Starfield.esm {XMarkerHeadingId:X6} is not the STAT {XMarkerHeadingEdid}");
        var calm = m.Raider.Npcs.FirstOrDefault(n => n.FormKey.ID == CalmProbeId && n.EditorID == "FO4_LvlRaider_Calm")
                   ?? throw new Refusal($"{m.Raider.ModKey} has no F04801 FO4_LvlRaider_Calm");
        var world = FindWorld(m.Core, worldEdid);
        var top = world.TopCell ?? throw new Refusal($"{worldEdid} has no persistent cell");

        var faction = new SF.Faction(new FormKey(modKey, FactionId), rel) { EditorID = FactionEdid };
        faction.Relations.Add(new SF.Relation { Target = new FormLink<SF.IRelatableGetter>(playerFaction.FormKey), Reaction = SF.CombatReaction.Ally });
        mod.Factions.Add(faction);
        var npc = (SF.Npc)calm.Duplicate(new FormKey(modKey, NpcId));
        npc.EditorID = NpcEdid;
        npc.Name = "Minuteman";
        npc.Flags &= ~(SF.Npc.Flag.Respawn | SF.Npc.Flag.Unique | SF.Npc.Flag.Essential);
        npc.Factions.Clear();
        npc.Factions.Add(new SF.RankPlacement { Faction = new FormLink<SF.IFactionGetter>(faction.FormKey), Rank = 0 });
        mod.Npcs.Add(npc);

        // the world and its persistent cell, overridden with only our waymarkers
        var w = (SF.Worldspace)world.DeepCopy();
        w.SubCells.Clear();
        var cell = (SF.Cell)top.DeepCopy();
        cell.Persistent.Clear();
        cell.Temporary.Clear();
        cell.NavigationMeshes.Clear();
        w.TopCell = cell;
        var start = g.Nodes[g.R1aFrom];
        var markers = new List<SF.PlacedObject>();
        for (int i = 0; i < pool; i++)
        {
            var r = new SF.PlacedObject(new FormKey(modKey, FirstWaymarkerId + (uint)i), rel)
            {
                EditorID = $"{WaymarkerEdid}{i + 1:00}", Base = new FormLinkNullable<SF.IPlaceableObjectGetter>(xmarker.FormKey),
                Position = new P3Float(start.X, start.Y, start.Z), Rotation = new P3Float(0, 0, 0),
            };
            r.MajorRecordFlagsRaw |= 0x400;                                      // persistent: the script moves them
            cell.Persistent.Add(r);
            markers.Add(r);
        }
        mod.Worldspaces.Add(w);

        var quest = new SF.Quest(new FormKey(modKey, QuestId), rel)
        {
            EditorID = QuestEdid, FormVersion = 581, Version2 = 12,
            Data = new SF.QuestData { Flags = SF.Quest.Flag.StartGameEnabled, Priority = 50 },
        };
        var script = new SF.ScriptEntry { Name = ScriptName, Flags = SF.ScriptEntry.Flag.Local };
        SF.ScriptObjectProperty Obj(string name, FormKey fk) => new()
        {
            Name = name, Flags = SF.ScriptProperty.Flag.Edited, Object = new FormLink<SF.IStarfieldMajorRecordGetter>(fk), Alias = -1, Unused = 0,
        };
        SF.ScriptFloatListProperty Floats(string name, IEnumerable<float> v) { var p = new SF.ScriptFloatListProperty { Name = name, Flags = SF.ScriptProperty.Flag.Edited }; p.Data.AddRange(v); return p; }
        SF.ScriptIntListProperty Ints(string name, IEnumerable<int> v) { var p = new SF.ScriptIntListProperty { Name = name, Flags = SF.ScriptProperty.Flag.Edited }; p.Data.AddRange(v); return p; }
        SF.ScriptIntProperty Int(string name, int v) => new() { Name = name, Flags = SF.ScriptProperty.Flag.Edited, Data = v };
        script.Properties.Add(Obj("SquadBase", npc.FormKey));
        script.Properties.Add(Obj("SquadFaction", faction.FormKey));
        var list = new SF.ScriptObjectListProperty { Name = "Waymarkers", Flags = SF.ScriptProperty.Flag.Edited };
        foreach (var r in markers) list.Objects.Add(Obj("", r.FormKey));
        script.Properties.Add(list);
        script.Properties.Add(Floats("NodeX", g.Nodes.Select(x => x.X)));
        script.Properties.Add(Floats("NodeY", g.Nodes.Select(x => x.Y)));
        script.Properties.Add(Floats("NodeZ", g.Nodes.Select(x => x.Z)));
        script.Properties.Add(Ints("NodeCap", g.Nodes.Select(x => x.Cap)));
        script.Properties.Add(Ints("EdgeU", g.Edges.Select(e => e.U)));
        script.Properties.Add(Ints("EdgeV", g.Edges.Select(e => e.V)));
        script.Properties.Add(Floats("EdgeLen", g.Edges.Select(e => e.Len)));
        script.Properties.Add(Int("Rung1aFrom", g.R1aFrom));
        script.Properties.Add(Int("Rung1aTo", g.R1aTo));
        script.Properties.Add(Int("Rung1bFrom", g.R1bFrom));
        script.Properties.Add(Int("Rung1bGoal", g.R1bGoal));
        script.Properties.Add(new SF.ScriptFloatProperty { Name = "Rung1bExpectedM", Flags = SF.ScriptProperty.Flag.Edited, Data = g.R1bLen });
        var vm = new SF.QuestAdapter { Version = 6, ObjectFormat = 2, ExtraBindDataVersion = 3, Script = new SF.ScriptEntry { Name = "", Flags = SF.ScriptEntry.Flag.Local } };
        vm.Scripts.Add(script);
        quest.VirtualMachineAdapter = vm;
        mod.Quests.Add(quest);

        mod.ModHeader.Stats.NextFormID = FirstWaymarkerId + (uint)pool;
        Directory.CreateDirectory(outDir);
        var path = Path.Combine(outDir, plugin);
        var lo = new[] { SfEsm, m.Core.ModKey, m.Raider.ModKey };
        mod.BeginWrite.ToPath(path).WithLoadOrder(lo)
            .WithKnownMasters(lo.Select(k => new KeyedMasterStyle(k, MasterStyle.Full)).ToArray()).Write();
        Console.WriteLine($"wrote {path} ({new FileInfo(path).Length:N0} bytes): QUST {QuestEdid} {quest.FormKey}; FACT {FactionEdid}; " +
                          $"NPC_ {NpcEdid} from {calm.EditorID}; {pool} waymarker REFR(s) of {XMarkerHeadingEdid} at ({F(start.X)}, {F(start.Y)}, {F(start.Z)}); " +
                          $"graph {g.Nodes.Count} nodes / {g.Edges.Count} edges; WRLD {w.EditorID} {w.FormKey} persistent CELL {cell.FormKey} overridden");
        return 0;
    }

    // ---------------------------------------------------------------- check

    public static int Check(string pluginPath, string sfPath, string corePath, string raiderPath, string graphPath, int pool)
    {
        var g = LoadGraph(graphPath);
        using var m = Open(sfPath, corePath, raiderPath);
        using var plug = SF.StarfieldMod.CreateFromBinaryOverlay(pluginPath, SF.StarfieldRelease.Starfield, Styles(SfEsm, m.Core.ModKey, m.Raider.ModKey));
        var key = plug.ModKey;
        var problems = new List<string>();
        void Need(bool ok, string what) { if (!ok) problems.Add(what); }
        var masters = plug.ModHeader.MasterReferences.Select(x => x.Master.FileName.String).ToList();
        Console.WriteLine($"{key}: header {plug.ModHeader.Flags}, masters [{string.Join(", ", masters)}], next 0x{plug.ModHeader.Stats.NextFormID:X}, " +
                          $"{plug.Quests.Count} QUST, {plug.Npcs.Count} NPC_, {plug.Factions.Count} FACT, {plug.Worldspaces.Count} WRLD");
        Need(plug.ModHeader.Flags.HasFlag(SF.StarfieldModHeader.HeaderFlag.Master), "not flagged as a master");
        // the squad member is a copy of the calm probe: the raider plugin is a master only when the copy still links
        // into it (its outfit or race, say); the synthetic probe has none
        var want = new List<string> { "Starfield.esm", m.Core.ModKey.FileName.String };
        if (masters.Count == 3) want.Add(m.Raider.ModKey.FileName.String);
        Need(masters.SequenceEqual(want), "masters are not Starfield, core[, raider]");
        Need(plug.Quests.Count == 1 && plug.Npcs.Count == 1 && plug.Factions.Count == 1 && plug.Worldspaces.Count == 1, "records other than one QUST, NPC_, FACT and WRLD");

        var faction = plug.Factions.FirstOrDefault(f => f.FormKey == new FormKey(key, FactionId));
        Need(faction is { EditorID: FactionEdid } && faction.Relations.Count == 1 && faction.Relations[0].Target.FormKey == new FormKey(SfEsm, PlayerFactionId)
             && faction.Relations[0].Reaction == SF.CombatReaction.Ally, $"FACT 0x{FactionId:X} is not {FactionEdid} with the one relation Ally to PlayerFaction");
        var npc = plug.Npcs.FirstOrDefault(n => n.FormKey == new FormKey(key, NpcId));
        Need(npc is { EditorID: NpcEdid } && npc.Factions.Count == 1 && npc.Factions[0].Faction.FormKey == faction?.FormKey
             && !npc.Flags.HasFlag(SF.Npc.Flag.Respawn) && !npc.Flags.HasFlag(SF.Npc.Flag.Unique) && !npc.Flags.HasFlag(SF.Npc.Flag.Essential),
             $"NPC_ 0x{NpcId:X} is not {NpcEdid} in {FactionEdid} only, neither unique, essential nor respawning");
        Need(npc is not null && m.Cache.TryResolve<SF.IRaceGetter>(npc.Race.FormKey, out _) || npc?.Race.IsNull == true, "the squad member's race does not resolve");

        var world = FindWorld(m.Core, World);
        var w = plug.Worldspaces.FirstOrDefault();
        Need(w is not null && w.FormKey == world.FormKey && w.SubCells.Count == 0, "the WRLD override is not the core world without exterior cells");
        var cell = w?.TopCell;
        Need(cell is not null && cell.FormKey == world.TopCell?.FormKey, "the persistent cell override is not the core's");
        var refs = cell?.Persistent.OfType<SF.IPlacedObjectGetter>().ToList() ?? new();
        Need(cell is null || cell.Persistent.Count == refs.Count, "the persistent cell holds something other than our waymarkers");
        Need(refs.Count == pool, $"{refs.Count} waymarkers, not {pool}");
        foreach (var (r, i) in refs.Select((r, i) => (r, i)))
        {
            Console.WriteLine($"  REFR {r.FormKey.ID:X6} {r.EditorID} base {r.Base.FormKey} at ({F(r.Position.X)}, {F(r.Position.Y)}, {F(r.Position.Z)}) flags 0x{r.MajorRecordFlagsRaw:X}");
            Need(r.FormKey == new FormKey(key, FirstWaymarkerId + (uint)i) && r.EditorID == $"{WaymarkerEdid}{i + 1:00}", $"waymarker {i} is not 0x{FirstWaymarkerId + i:X} {WaymarkerEdid}{i + 1:00}");
            Need(r.Base.FormKey == new FormKey(SfEsm, XMarkerHeadingId), $"REFR {r.FormKey.ID:X6} is not an {XMarkerHeadingEdid}");
            Need((r.MajorRecordFlagsRaw & 0xC00) == 0x400, $"REFR {r.FormKey.ID:X6} is not persistent and enabled");
        }
        Need(m.Cache.TryResolve<SF.IStaticGetter>(new FormKey(SfEsm, XMarkerHeadingId), out var xm) && xm.EditorID == XMarkerHeadingEdid,
             $"Starfield.esm {XMarkerHeadingId:X6} is not the STAT {XMarkerHeadingEdid}");

        var q = plug.Quests.FirstOrDefault(x => x.FormKey == new FormKey(key, QuestId));
        if (q is null) problems.Add($"no QUST 0x{QuestId:X}");
        else
        {
            Console.WriteLine($"  QUST {q.EditorID} flags {q.Data?.Flags} aliases {q.Aliases?.Count ?? 0}");
            Need(q.EditorID == QuestEdid && q.Data is not null && q.Data.Flags.HasFlag(SF.Quest.Flag.StartGameEnabled)
                 && !q.Data.Flags.HasFlag(SF.Quest.Flag.RunOnce) && !q.Data.Flags.HasFlag(SF.Quest.Flag.DisplaysInHud),
                 $"the quest is not {QuestEdid}, start game enabled, not run once, out of the HUD");
            Need((q.Aliases?.Count ?? 0) == 0, "the quest carries an alias (the walk is the linked ref alone, the P9 recipe)");
            var s = q.VirtualMachineAdapter?.Scripts.FirstOrDefault(x => x.Name == ScriptName);
            if (s is null) problems.Add($"script {ScriptName} not attached");
            else
            {
                var props = s.Properties.ToDictionary(p => p.Name);
                Console.WriteLine($"  script {s.Name}: " + string.Join(", ", props.Keys));
                Need(props.Keys.ToHashSet().SetEquals(Properties), "the script's properties are not exactly the Mandatory ones");
                FormKey? O(string n) => props.TryGetValue(n, out var p) && p is SF.IScriptObjectPropertyGetter o ? o.Object.FormKey : null;
                List<float>? FL(string n) => props.TryGetValue(n, out var p) && p is SF.IScriptFloatListPropertyGetter l ? l.Data.ToList() : null;
                List<int>? IL(string n) => props.TryGetValue(n, out var p) && p is SF.IScriptIntListPropertyGetter l ? l.Data.ToList() : null;
                int? I(string n) => props.TryGetValue(n, out var p) && p is SF.IScriptIntPropertyGetter l ? l.Data : null;
                bool Same(List<float>? a, IEnumerable<float> b) => a is not null && a.Count <= ArrayCap && a.SequenceEqual(b);
                Need(O("SquadBase") == npc?.FormKey && npc is not null, "property SquadBase is not the squad NPC_");
                Need(O("SquadFaction") == faction?.FormKey && faction is not null, "property SquadFaction is not our faction");
                Need(props.TryGetValue("Waymarkers", out var wp) && wp is SF.IScriptObjectListPropertyGetter wl &&
                     wl.Objects.Select(o => o.Object.FormKey).SequenceEqual(refs.Select(r => r.FormKey)), "property Waymarkers does not list the waymarkers in order");
                Need(Same(FL("NodeX"), g.Nodes.Select(x => x.X)) && Same(FL("NodeY"), g.Nodes.Select(x => x.Y)) && Same(FL("NodeZ"), g.Nodes.Select(x => x.Z)),
                     "NodeX/NodeY/NodeZ differ from the graph");
                Need(IL("NodeCap")?.SequenceEqual(g.Nodes.Select(x => x.Cap)) == true, "NodeCap differs from the graph");
                Need(IL("EdgeU")?.SequenceEqual(g.Edges.Select(e => e.U)) == true && IL("EdgeV")?.SequenceEqual(g.Edges.Select(e => e.V)) == true
                     && Same(FL("EdgeLen"), g.Edges.Select(e => e.Len)), "EdgeU/EdgeV/EdgeLen differ from the graph");
                Need(I("Rung1aFrom") == g.R1aFrom && I("Rung1aTo") == g.R1aTo && I("Rung1bFrom") == g.R1bFrom && I("Rung1bGoal") == g.R1bGoal,
                     "the rung node properties differ from the graph");
                Need(props.TryGetValue("Rung1bExpectedM", out var em) && em is SF.IScriptFloatPropertyGetter ef && ef.Data == g.R1bLen,
                     "Rung1bExpectedM differs from the graph's rung 1b length");
                var start = g.Nodes[g.R1aFrom];
                Need(refs.All(r => r.Position.X == start.X && r.Position.Y == start.Y && r.Position.Z == start.Z), "the waymarkers are not at rung 1a's start spot");
            }
        }
        foreach (var p in problems) Console.WriteLine("FAIL  " + p);
        Console.WriteLine(problems.Count == 0 ? "all checks pass" : $"{problems.Count} problem(s)");
        return problems.Count == 0 ? 0 : 1;
    }

    // ---------------------------------------------------------------- selftest (synthetic masters only)

    public static int SelfTest(string dir)
    {
        Directory.CreateDirectory(dir);
        var rel = SF.StarfieldRelease.Starfield;
        var sf = new SF.StarfieldMod(SfEsm, rel);
        sf.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Master;
        sf.Factions.Add(new SF.Faction(new FormKey(SfEsm, PlayerFactionId), rel) { EditorID = PlayerFactionEdid });
        sf.Statics.Add(new SF.Static(new FormKey(SfEsm, XMarkerHeadingId), rel) { EditorID = XMarkerHeadingEdid });
        var race = new SF.Race(new FormKey(SfEsm, 0x900), rel) { EditorID = "HumanRace" };
        sf.Races.Add(race);
        sf.ModHeader.Stats.NextFormID = 0x901;
        var sfPath = Path.Combine(dir, "Starfield.esm");
        sf.BeginWrite.ToPath(sfPath).WithNoLoadOrder().NoCheckIfLowerRangeDisallowed().Write();
        var coreKey = ModKey.FromFileName("FO4TerrainCore.esm");
        var core = new SF.StarfieldMod(coreKey, rel);
        core.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Master;
        var world = new SF.Worldspace(new FormKey(coreKey, 0x803), rel) { EditorID = World };
        world.TopCell = new SF.Cell(new FormKey(coreKey, 0x900), rel) { Flags = SF.Cell.Flag.HasWater };
        world.TopCell.Persistent.Add(new SF.PlacedObject(new FormKey(coreKey, 0x800), rel) { EditorID = "Anchor" });
        core.Worldspaces.Add(world);
        core.ModHeader.Stats.NextFormID = 0x901;
        var corePath = Path.Combine(dir, coreKey.FileName);
        core.BeginWrite.ToPath(corePath).WithLoadOrder(SfEsm).WithKnownMasters(new KeyedMasterStyle(SfEsm, MasterStyle.Full)).Write();
        var raiderKey = ModKey.FromFileName("FO4ActorRaider.esm");
        var raider = new SF.StarfieldMod(raiderKey, rel);
        raider.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Master;
        var calm = new SF.Npc(new FormKey(raiderKey, CalmProbeId), rel)
        {
            EditorID = "FO4_LvlRaider_Calm", Name = "Raider", Flags = SF.Npc.Flag.Respawn | SF.Npc.Flag.Unique, Race = new FormLink<SF.IRaceGetter>(race.FormKey),
        };
        calm.Factions.Add(new SF.RankPlacement { Faction = new FormLink<SF.IFactionGetter>(new FormKey(SfEsm, PlayerFactionId)), Rank = 0 });
        raider.Npcs.Add(calm);
        raider.ModHeader.Stats.NextFormID = 0xF04802;
        var raiderPath = Path.Combine(dir, raiderKey.FileName);
        raider.BeginWrite.ToPath(raiderPath).WithLoadOrder(SfEsm).WithKnownMasters(new KeyedMasterStyle(SfEsm, MasterStyle.Full)).Write();

        string GraphJson(int nodes, int edges, string extra = "")
        {
            var ns = string.Join(",", Enumerable.Range(0, nodes).Select(i => $"{{\"edid\": \"N{i}\", \"x\": {i * 10}.5, \"y\": {-i * 3}.25, \"z\": 1.0, \"cap\": {(i % 3 == 2 ? 0 : 2)}}}"));
            var es = string.Join(",", Enumerable.Range(0, edges).Select(i => $"{{\"u\": {i % nodes}, \"v\": {(i + 1) % nodes}, \"len_m\": {10 + i}.75}}"));
            return $"{{\"nodes\": [{ns}], \"edges\": [{es}], \"rung1a\": {{\"from\": 0, \"to\": 1}}, \"rung1b\": {{\"from\": 0, \"goal\": 3, \"length_m\": 33.5}}{extra}}}";
        }
        var graphPath = Path.Combine(dir, "graph.json");
        File.WriteAllText(graphPath, GraphJson(6, 8));
        var outDir = Path.Combine(dir, "out");
        int rc = Write(sfPath, corePath, raiderPath, graphPath, outDir, Plugin, World, 4);
        if (rc == 0) rc = Check(Path.Combine(outDir, Plugin), sfPath, corePath, raiderPath, graphPath, 4);
        if (rc != 0) return rc;
        // the full 128 fit; 129 nodes or edges are refused (one Papyrus array each)
        var big = Path.Combine(dir, "graph128.json");
        File.WriteAllText(big, GraphJson(128, 128));
        rc = Write(sfPath, corePath, raiderPath, big, Path.Combine(dir, "out128"), Plugin, World, 4);
        if (rc == 0) rc = Check(Path.Combine(dir, "out128", Plugin), sfPath, corePath, raiderPath, big, 4);
        if (rc != 0) return rc;
        var refusals = new (string Name, string Json, int Pool)[]
        {
            ("129 nodes", GraphJson(129, 10), 4),
            ("129 edges", GraphJson(10, 129), 4),
            ("an edge to a missing node", GraphJson(6, 8).Replace("\"v\": 1,", "\"v\": 6,"), 4),
            ("a zero-length edge", GraphJson(6, 8).Replace("\"len_m\": 10.75", "\"len_m\": 0"), 4),
            ("a rung destination that cannot garrison", GraphJson(6, 8).Replace("\"goal\": 3", "\"goal\": 2"), 4),
            ("a pool of 1", GraphJson(6, 8), 1),
            ("a pool of 17", GraphJson(6, 8), 17),
        };
        foreach (var (name, json, poolSize) in refusals)
        {
            var p = Path.Combine(dir, "refuse.json");
            File.WriteAllText(p, json);
            try
            {
                Write(sfPath, corePath, raiderPath, p, Path.Combine(dir, "refused"), Plugin, World, poolSize);
                Console.WriteLine($"FAIL  write accepted {name}");
                return 1;
            }
            catch (Refusal e) { Console.WriteLine($"refusal kept: {name} ({e.Message})"); }
        }
        // mutations of the good output, each of which check must reject
        var good = Path.Combine(outDir, Plugin);
        static SF.ScriptEntry Script(SF.StarfieldMod m) => m.Quests.First().VirtualMachineAdapter!.Scripts[0];
        static T Prop<T>(SF.StarfieldMod m, string n) where T : SF.ScriptProperty => (T)Script(m).Properties.First(p => p.Name == n);
        var mutations = new (string Name, Action<SF.StarfieldMod> Edit)[]
        {
            ("a node moved", m => Prop<SF.ScriptFloatListProperty>(m, "NodeX").Data[2] += 1f),
            ("a capacity changed", m => Prop<SF.ScriptIntListProperty>(m, "NodeCap").Data[1] = 5),
            ("an edge dropped", m => { Prop<SF.ScriptIntListProperty>(m, "EdgeU").Data.RemoveAt(0); }),
            ("an edge length changed", m => Prop<SF.ScriptFloatListProperty>(m, "EdgeLen").Data[0] = 99f),
            ("the rung 1b goal changed", m => Prop<SF.ScriptIntProperty>(m, "Rung1bGoal").Data = 4),
            ("the expected length changed", m => Prop<SF.ScriptFloatProperty>(m, "Rung1bExpectedM").Data = 1f),
            ("a property missing", m => Script(m).Properties.RemoveAll(p => p.Name == "SquadFaction")),
            ("an extra property", m => Script(m).Properties.Add(new SF.ScriptIntProperty { Name = "Mode", Flags = SF.ScriptProperty.Flag.Edited, Data = 1 })),
            ("the waymarkers reordered", m => Prop<SF.ScriptObjectListProperty>(m, "Waymarkers").Objects.Reverse()),
            ("a waymarker not persistent", m => m.Worldspaces.First().TopCell!.Persistent[0].MajorRecordFlagsRaw &= ~0x400),
            ("a waymarker disabled", m => m.Worldspaces.First().TopCell!.Persistent[1].MajorRecordFlagsRaw |= 0x800),
            ("the quest run once", m => m.Quests.First().Data!.Flags |= SF.Quest.Flag.RunOnce),
            ("the quest not start game enabled", m => m.Quests.First().Data!.Flags &= ~SF.Quest.Flag.StartGameEnabled),
            ("an alias added", m => (m.Quests.First().Aliases ??= new ExtendedList<SF.AQuestAlias>()).Add(new SF.QuestReferenceAlias { ID = 0, Name = "Walker" })),
            ("the member respawns", m => m.Npcs.First().Flags |= SF.Npc.Flag.Respawn),
            ("the faction hostile", m => m.Factions.First().Relations[0].Reaction = SF.CombatReaction.Enemy),
            ("the squad base swapped", m => Prop<SF.ScriptObjectProperty>(m, "SquadBase").Object = new FormLink<SF.IStarfieldMajorRecordGetter>(m.Factions.First().FormKey)),
        };
        foreach (var (name, edit) in mutations)
        {
            var mod = SF.StarfieldMod.CreateFromBinary(good, rel, Styles(SfEsm, coreKey, raiderKey));
            edit(mod);
            var md = Path.Combine(dir, "mutated");
            Directory.CreateDirectory(md);
            var lo = new[] { SfEsm, coreKey, raiderKey };
            mod.BeginWrite.ToPath(Path.Combine(md, Plugin)).WithLoadOrder(lo)
                .WithKnownMasters(lo.Select(k => new KeyedMasterStyle(k, MasterStyle.Full)).ToArray()).Write();
            if (Check(Path.Combine(md, Plugin), sfPath, corePath, raiderPath, graphPath, 4) == 0)
                { Console.WriteLine($"FAIL  check passed a mutation: {name}"); return 1; }
            Console.WriteLine($"mutation rejected: {name}");
        }
        if (Check(good, sfPath, corePath, raiderPath, graphPath, 3) == 0) { Console.WriteLine("FAIL  check passed a 4-marker pool as 3"); return 1; }
        Console.WriteLine($"selftest ok: write + check, 128-element graph, {refusals.Length} refusals, {mutations.Length + 1} mutations rejected");
        return 0;
    }
}
