// Mission: a cut-down "When Freedom Calls" (docs/spikes/B4-mission-anatomy.md, docs/mission/when-freedom-calls.md) as
// one Starfield plugin on top of the converted Commonwealth core and the converted raider. Claude's project.
//
//   points <Fallout4.esm> <out points.json> [--radius 120] [--max 8]
//        reads Fallout 4 only: where the Museum of Freedom's front door puts the player outside (the XTEL arrival of
//        the interior door in ConcordMuseum01 00017DF7 that leads to the Commonwealth), the Concord raiders around it
//        (placed ACHRs whose base EditorID contains "Raider", enabled at start, within --radius m of that point),
//        Preston's name (NPC_ 00019FD9) and the Min00 texts the plugin shows (quest name, objectives 10 / 85 / 86).
//        Positions in metres in the core's frame: FO4 position / 70 (make_core64c.py: "position = FO4 position / 70").
//   write <Starfield.esm> <FO4TerrainCore.esm> <FO4ActorRaider.esm> <points.json> <out dir> [--plugin FO4SFMission.esm]
//         [--world FO4Core_Commonwealth] [--no-alias]
//        the plugin: Preston (NPC_, a copy of the raider plugin's calm probe FO4_LvlRaider_Calm under Preston's name,
//        Essential and Unique), the raiders and Preston as persistent ACHRs in the core world's persistent cell (a
//        WRLD + persistent CELL override of the core, holding only our references), and the quest FO4SF_Min00
//        (start game enabled; stages 10 / 20 / 30 / 40 / 200; objectives 10 / 85 / 86) carrying the script
//        FO4SF_Min00Quest (scripts/mission/FO4SF_Min00Quest.psc) with its properties. --no-alias drops the Preston
//        reference alias and the objective targets (no quest markers): the fallback when the alias is suspected.
//   check <plugin> <Starfield.esm> <FO4TerrainCore.esm> <FO4ActorRaider.esm> [--no-alias]
//        reads the plugin back and checks every record and link the script and the quest rely on (exit 1 on a problem).
//   selftest <scratch dir>
//        synthetic masters (a Starfield.esm with the Credits MISC, a core with the world, a raider plugin with the calm
//        probe) and a synthetic points.json; write + check against them. No game file is read.
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

if (args.Length == 0) return Mission.Usage();
try
{
    return args[0] switch
    {
        "points" when args.Length >= 3 => Mission.Points(args[1], args[2], Mission.Opt(args, "--radius", 120f), (int)Mission.Opt(args, "--max", 8f)),
        "write" when args.Length >= 6 => Mission.Write(args[1], args[2], args[3], args[4], args[5], Mission.Arg(args, "--plugin", Mission.Plugin),
                                                       Mission.Arg(args, "--world", Mission.World), !args.Contains("--no-alias")),
        "check" when args.Length >= 5 => Mission.Check(args[1], args[2], args[3], args[4], !args.Contains("--no-alias")),
        "selftest" when args.Length >= 2 => Mission.SelfTest(args[1]),
        _ => Mission.Usage(),
    };
}
catch (Mission.Refusal e)
{
    Console.Error.WriteLine("refused: " + e.Message);
    return 2;
}

static class Mission
{
    public const string Plugin = "FO4SFMission.esm", World = "FO4Core_Commonwealth";
    public const string QuestEdid = "FO4SF_Min00", ScriptName = "FO4SF_Min00Quest", PrestonEdid = "FO4_PrestonGarvey";
    public const uint QuestId = 0x800, PrestonNpcId = 0x801, PrestonRefId = 0x802, FirstRaiderRefId = 0x803;
    public const uint CalmProbeId = 0xF04801, RaiderId = 0xF04800;        // FO4ActorRaider.esm (docs/actors/raider-conversion.md)
    public const uint CreditsId = 0x00000F;                                // Starfield.esm MISC "Credits"
    public const uint MuseumCell = 0x017DF7, Commonwealth = 0x00003C, PrestonFo4 = 0x019FD9, Min00 = 0x1A001C;
    public const int PrestonAlias = 0;
    // the stages and objectives the script drives (FO4SF_Min00Quest.psc); objective indices are Min00's own
    public static readonly ushort[] Stages = { 10, 20, 30, 40, 200 };
    public static readonly (ushort Index, string Fallback, bool TargetsPreston)[] Objectives =
    {
        (10, "Find the Last Minutemen", true), (85, "Kill the Raiders", false), (86, "Talk to Preston Garvey", true),
    };
    public const float Units = 70f;                                       // FO4 units per metre
    static readonly ModKey SfEsm = ModKey.FromFileName("Starfield.esm");

    public class Refusal(string m) : Exception(m);

    public static int Usage()
    {
        Console.Error.WriteLine("usage: see the header of dotnet/Mission/Program.cs (points | write | check | selftest)");
        return 2;
    }
    public static string Arg(string[] a, string name, string dflt) { var i = Array.IndexOf(a, name); return i >= 0 && i + 1 < a.Length ? a[i + 1] : dflt; }
    public static float Opt(string[] a, string name, float dflt) => float.Parse(Arg(a, name, dflt.ToString(CultureInfo.InvariantCulture)), CultureInfo.InvariantCulture);
    static string F(float v) => v.ToString("0.###", CultureInfo.InvariantCulture);

    // ---------------------------------------------------------------- points (Fallout 4, read only)

    public static int Points(string fo4Path, string outPath, float radius, int max)
    {
        using var fo4 = F4.Fallout4Mod.CreateFromBinaryOverlay(fo4Path, F4.Fallout4Release.Fallout4);
        var cache = fo4.ToImmutableLinkCache<F4.IFallout4Mod, F4.IFallout4ModGetter>();
        var fo4Key = fo4.ModKey;
        var world = fo4.Worldspaces.FirstOrDefault(w => w.FormKey.ID == Commonwealth)
                    ?? throw new Refusal("no Commonwealth worldspace 00003C in " + fo4Path);
        // every placed reference of the Commonwealth (persistent cell and exterior cells) by FormKey
        var placed = new Dictionary<FormKey, F4.IPlacedGetter>();
        void Add(F4.ICellGetter? c)
        {
            if (c is null) return;
            foreach (var p in c.Persistent) placed[p.FormKey] = p;
            foreach (var p in c.Temporary) placed[p.FormKey] = p;
        }
        Add(world.TopCell);
        foreach (var b in world.SubCells) foreach (var s in b.Items) foreach (var c in s.Items) Add(c);

        var museum = fo4.EnumerateMajorRecords<F4.ICellGetter>().FirstOrDefault(c => c.FormKey.ID == MuseumCell && c.FormKey.ModKey == fo4Key)
                     ?? throw new Refusal("no ConcordMuseum01 cell 00017DF7");
        var doors = museum.Persistent.Concat(museum.Temporary).OfType<F4.IPlacedObjectGetter>()
            .Where(d => d.TeleportDestination is { } t && placed.ContainsKey(t.Door.FormKey)).ToList();
        if (doors.Count == 0) throw new Refusal("ConcordMuseum01 has no door to the Commonwealth");
        // the front door: the interior door whose exterior twin is the lowest (the balcony door is a floor up)
        var front = doors.OrderBy(d => (placed[d.TeleportDestination!.Door.FormKey] as F4.IPlacedObjectGetter)?.Position.Z ?? 0f).First();
        var arrival = front.TeleportDestination!.Position;
        var arrivalRot = front.TeleportDestination!.Rotation;
        float ax = arrival.X / Units, ay = arrival.Y / Units, az = arrival.Z / Units;

        var raiders = new List<(float D, F4.IPlacedNpcGetter R, string BaseEdid)>();
        foreach (var p in placed.Values.OfType<F4.IPlacedNpcGetter>())
        {
            if ((p.MajorRecordFlagsRaw & 0x800) != 0) continue;   // initially disabled: a later wave
            if (!cache.TryResolve<F4.INpcGetter>(p.Base.FormKey, out var b) || b.EditorID is null) continue;
            if (!b.EditorID.Contains("Raider", StringComparison.OrdinalIgnoreCase)) continue;
            var q = p.Position;
            float d = MathF.Sqrt(MathF.Pow(q.X / Units - ax, 2) + MathF.Pow(q.Y / Units - ay, 2));
            if (d <= radius) raiders.Add((d, p, b.EditorID));
        }
        raiders = raiders.OrderBy(r => r.D).Take(max).ToList();
        if (raiders.Count == 0) throw new Refusal($"no enabled raider within {radius} m of the museum door");

        string Text(ITranslatedStringGetter? s, string dflt) => string.IsNullOrWhiteSpace(s?.String) ? dflt : s!.String!;
        cache.TryResolve<F4.INpcGetter>(new FormKey(fo4Key, PrestonFo4), out var preston);
        cache.TryResolve<F4.IQuestGetter>(new FormKey(fo4Key, Min00), out var min00);
        var objectives = new Dictionary<string, string>();
        foreach (var o in Objectives)
            objectives[o.Index.ToString(CultureInfo.InvariantCulture)] =
                Text(min00?.Objectives.FirstOrDefault(x => x.Index == o.Index)?.DisplayText, o.Fallback);

        var doc = new Dictionary<string, object?>
        {
            ["source"] = Path.GetFileName(fo4Path),
            ["frame"] = "metres, FO4 position / 70 (the core's local frame); rotation in radians as stored",
            ["quest_name"] = Text(min00?.Name, "When Freedom Calls"),
            ["preston_name"] = Text(preston?.Name, "Preston Garvey"),
            ["objectives"] = objectives,
            ["preston"] = new Dictionary<string, object?>
            {
                ["src"] = $"{front.FormKey.ID:X6}:XTEL", ["pos"] = new[] { ax, ay, az },
                ["rot"] = new[] { arrivalRot.X, arrivalRot.Y, arrivalRot.Z },
            },
            ["raiders"] = raiders.Select(r => (object)new Dictionary<string, object?>
            {
                ["src"] = $"{r.R.FormKey.ID:X6}", ["edid"] = r.R.EditorID ?? "", ["base"] = r.BaseEdid, ["dist_m"] = MathF.Round(r.D, 2),
                ["pos"] = new[] { r.R.Position.X / Units, r.R.Position.Y / Units, r.R.Position.Z / Units },
                ["rot"] = new[] { r.R.Rotation.X, r.R.Rotation.Y, r.R.Rotation.Z },
            }).ToList(),
        };
        Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(outPath))!);
        File.WriteAllText(outPath, JsonSerializer.Serialize(doc, new JsonSerializerOptions { WriteIndented = true }));
        Console.WriteLine($"wrote {outPath}: museum door {front.FormKey.ID:X6} -> arrival ({F(ax)}, {F(ay)}, {F(az)}) m; " +
                          $"{raiders.Count} raider(s): " + string.Join(", ", raiders.Select(r => $"{r.R.FormKey.ID:X6} {r.R.EditorID} {r.BaseEdid} {F(r.D)} m")));
        return 0;
    }

    // ---------------------------------------------------------------- write (Starfield)

    sealed record Masters(SF.IStarfieldModGetter Sf, SF.IStarfieldModGetter Core, SF.IStarfieldModGetter Raider, ILinkCache Cache) : IDisposable
    {
        public void Dispose() { (Raider as IDisposable)?.Dispose(); (Core as IDisposable)?.Dispose(); (Sf as IDisposable)?.Dispose(); }
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

    static float[] Floats(JsonElement e) => e.EnumerateArray().Select(x => x.GetSingle()).ToArray();

    public static int Write(string sfPath, string corePath, string raiderPath, string pointsPath, string outDir, string plugin,
                            string worldEdid, bool alias)
    {
        var pts = JsonDocument.Parse(File.ReadAllText(pointsPath)).RootElement;
        using var m = Open(sfPath, corePath, raiderPath);
        var modKey = ModKey.FromFileName(plugin);
        var mod = new SF.StarfieldMod(modKey, SF.StarfieldRelease.Starfield);
        mod.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Master;
        mod.ModHeader.Author = "fo4-to-starfield Mission";

        // the links the script needs, each checked by type and EditorID before anything is written
        if (!m.Cache.TryResolve<SF.IMiscItemGetter>(new FormKey(SfEsm, CreditsId), out var credits) || credits.EditorID != "Credits")
            throw new Refusal("Starfield.esm 00000F is not the MISC Credits");
        var calm = m.Raider.Npcs.FirstOrDefault(n => n.FormKey.ID == CalmProbeId && n.EditorID == "FO4_LvlRaider_Calm")
                   ?? throw new Refusal($"{m.Raider.ModKey} has no F04801 FO4_LvlRaider_Calm");
        var raiderNpc = m.Raider.Npcs.FirstOrDefault(n => n.FormKey.ID == RaiderId && n.EditorID == "FO4_LvlRaider")
                        ?? throw new Refusal($"{m.Raider.ModKey} has no F04800 FO4_LvlRaider");
        var world = FindWorld(m.Core, worldEdid);
        var top = world.TopCell ?? throw new Refusal($"{worldEdid} has no persistent cell");

        // Preston: the calm probe (no factions: nothing makes it hostile) under Preston's name
        var npc = (SF.Npc)calm.Duplicate(new FormKey(modKey, PrestonNpcId));
        npc.EditorID = PrestonEdid;
        npc.Name = pts.GetProperty("preston_name").GetString();
        npc.Flags = (npc.Flags | SF.Npc.Flag.Essential | SF.Npc.Flag.Unique) & ~SF.Npc.Flag.Respawn;
        mod.Npcs.Add(npc);

        // the world and its persistent cell, overridden with only our references (vanilla keeps every persistent
        // worldspace reference there; TerrainOverlays puts the door arrival markers there for the same reason)
        var w = (SF.Worldspace)world.DeepCopy();
        w.SubCells.Clear();
        var cell = (SF.Cell)top.DeepCopy();
        cell.Persistent.Clear();
        cell.Temporary.Clear();
        cell.NavigationMeshes.Clear();
        w.TopCell = cell;
        SF.PlacedNpc Ach(uint id, FormKey baseKey, string edid, JsonElement e)
        {
            var p = Floats(e.GetProperty("pos"));
            var r = Floats(e.GetProperty("rot"));
            var a = new SF.PlacedNpc(new FormKey(modKey, id), SF.StarfieldRelease.Starfield)
            {
                EditorID = edid, Base = new FormLink<SF.INpcGetter>(baseKey),
                Position = new P3Float(p[0], p[1], p[2]), Rotation = new P3Float(r[0], r[1], r[2]),
            };
            a.MajorRecordFlagsRaw |= 0x400;                                  // Persistent
            cell.Persistent.Add(a);
            return a;
        }
        var prestonRef = Ach(PrestonRefId, npc.FormKey, "FO4SF_Min00_PrestonREF", pts.GetProperty("preston"));
        var raiderRefs = new List<SF.PlacedNpc>();
        uint next = FirstRaiderRefId;
        foreach (var r in pts.GetProperty("raiders").EnumerateArray())
            raiderRefs.Add(Ach(next++, raiderNpc.FormKey, $"FO4SF_Min00_Raider_{r.GetProperty("src").GetString()}", r));
        mod.Worldspaces.Add(w);

        // the quest
        var objText = pts.GetProperty("objectives");
        var quest = new SF.Quest(new FormKey(modKey, QuestId), SF.StarfieldRelease.Starfield)
        {
            EditorID = QuestEdid, Name = pts.GetProperty("quest_name").GetString(), FormVersion = 581, Version2 = 12,
            Data = new SF.QuestData { Flags = SF.Quest.Flag.StartGameEnabled | SF.Quest.Flag.RunOnce | SF.Quest.Flag.DisplaysInHud, Priority = 50 },
        };
        foreach (var s in Stages)
        {
            var st = new SF.QuestStage { Index = s };
            if (s == 200) st.LogEntries.Add(new SF.QuestLogEntry { Flags = SF.QuestLogEntry.Flag.CompleteQuest });
            quest.Stages.Add(st);
        }
        foreach (var o in Objectives)
        {
            var obj = new SF.QuestObjective { Index = o.Index, DisplayText = objText.GetProperty(o.Index.ToString(CultureInfo.InvariantCulture)).GetString() };
            if (alias && o.TargetsPreston) obj.Targets.Add(new SF.QuestObjectiveTarget { AliasID = PrestonAlias });
            quest.Objectives.Add(obj);
        }
        if (alias)
            (quest.Aliases ??= new ExtendedList<SF.AQuestAlias>()).Add(new SF.QuestReferenceAlias
            {
                ID = PrestonAlias, Name = "PrestonGarvey", ForcedReference = new FormLinkNullable<SF.IPlacedGetter>(prestonRef.FormKey),
            });
        var script = new SF.ScriptEntry { Name = ScriptName, Flags = SF.ScriptEntry.Flag.Local };
        SF.ScriptObjectProperty Obj(string name, FormKey fk) => new()
        {
            Name = name, Flags = SF.ScriptProperty.Flag.Edited, Object = new FormLink<SF.IStarfieldMajorRecordGetter>(fk), Alias = -1, Unused = 0,
        };
        script.Properties.Add(Obj("Preston", prestonRef.FormKey));
        var list = new SF.ScriptObjectListProperty { Name = "Raiders", Flags = SF.ScriptProperty.Flag.Edited };
        foreach (var r in raiderRefs) list.Objects.Add(Obj("", r.FormKey));
        script.Properties.Add(list);
        script.Properties.Add(Obj("Credits", credits.FormKey));
        quest.VirtualMachineAdapter = new SF.QuestAdapter
        {
            Version = 6, ObjectFormat = 2, ExtraBindDataVersion = 3,
            Script = new SF.ScriptEntry { Name = "", Flags = SF.ScriptEntry.Flag.Local },
        };
        quest.VirtualMachineAdapter.Scripts.Add(script);
        mod.Quests.Add(quest);

        mod.ModHeader.Stats.NextFormID = next;
        Directory.CreateDirectory(outDir);
        var path = Path.Combine(outDir, plugin);
        var lo = new[] { SfEsm, m.Core.ModKey, m.Raider.ModKey };
        mod.BeginWrite.ToPath(path).WithLoadOrder(lo)
            .WithKnownMasters(lo.Select(k => new KeyedMasterStyle(k, MasterStyle.Full)).ToArray()).Write();
        Console.WriteLine($"wrote {path} ({new FileInfo(path).Length:N0} bytes): QUST {QuestEdid} {quest.FormKey} \"{quest.Name}\" " +
                          $"({Stages.Length} stages, {quest.Objectives.Count} objectives, {(alias ? "alias PrestonGarvey" : "no alias")}); " +
                          $"NPC_ {PrestonEdid} {npc.FormKey} \"{npc.Name}\"; ACHR Preston {prestonRef.FormKey} at {Show(prestonRef.Position)}; " +
                          $"{raiderRefs.Count} raider ACHR(s) of {raiderNpc.EditorID}; WRLD {w.EditorID} {w.FormKey} persistent CELL {cell.FormKey} overridden");
        return 0;
    }

    static string Show(P3Float p) => $"({F(p.X)}, {F(p.Y)}, {F(p.Z)})";

    // ---------------------------------------------------------------- check

    public static int Check(string pluginPath, string sfPath, string corePath, string raiderPath, bool alias)
    {
        using var m = Open(sfPath, corePath, raiderPath);
        using var plug = SF.StarfieldMod.CreateFromBinaryOverlay(pluginPath, SF.StarfieldRelease.Starfield, Styles(SfEsm, m.Core.ModKey, m.Raider.ModKey));
        var key = plug.ModKey;
        var problems = new List<string>();
        void Need(bool ok, string what) { if (!ok) problems.Add(what); }
        var masters = plug.ModHeader.MasterReferences.Select(x => x.Master.FileName.String).ToList();
        Console.WriteLine($"{key}: header {plug.ModHeader.Flags}, masters [{string.Join(", ", masters)}], next 0x{plug.ModHeader.Stats.NextFormID:X}, " +
                          $"{plug.Quests.Count} QUST, {plug.Npcs.Count} NPC_, {plug.Worldspaces.Count} WRLD");
        Need(plug.ModHeader.Flags.HasFlag(SF.StarfieldModHeader.HeaderFlag.Master), "not flagged as a master (every plugin of ours that loads is)");
        Need(masters.SequenceEqual(new[] { "Starfield.esm", m.Core.ModKey.FileName.String, m.Raider.ModKey.FileName.String }), "masters are not Starfield, core, raider");

        var npc = plug.Npcs.FirstOrDefault(n => n.FormKey == new FormKey(key, PrestonNpcId));
        Need(npc is { EditorID: PrestonEdid } && npc.Flags.HasFlag(SF.Npc.Flag.Essential) && npc.Factions.Count == 0,
             "NPC_ 0x801 is not an essential, faction-less FO4_PrestonGarvey");

        var world = FindWorld(m.Core, World);
        var w = plug.Worldspaces.FirstOrDefault();
        Need(w is not null && w.FormKey == world.FormKey && w.SubCells.Count == 0, "the WRLD override is not the core world without exterior cells");
        var cell = w?.TopCell;
        Need(cell is not null && cell.FormKey == world.TopCell?.FormKey, "the persistent cell override is not the core's");
        var refs = cell?.Persistent.OfType<SF.IPlacedNpcGetter>().ToList() ?? new();
        Need(cell is null || cell.Persistent.Count == refs.Count, "the persistent cell holds something other than our ACHRs");
        foreach (var r in refs)
        {
            Console.WriteLine($"  ACHR {r.FormKey.ID:X6} {r.EditorID} base {r.Base.FormKey} at {Show(r.Position)} flags 0x{r.MajorRecordFlagsRaw:X}");
            Need((r.MajorRecordFlagsRaw & 0x400) != 0, $"ACHR {r.FormKey.ID:X6} is not persistent");
            Need(m.Cache.TryResolve<SF.INpcGetter>(r.Base.FormKey, out _) || r.Base.FormKey.ModKey == key, $"ACHR {r.FormKey.ID:X6}: base {r.Base.FormKey} does not resolve");
        }
        var preston = refs.FirstOrDefault(r => r.FormKey.ID == PrestonRefId);
        Need(preston is not null && preston.Base.FormKey == npc?.FormKey, "ACHR 0x802 is not Preston");
        var raiders = refs.Where(r => r.FormKey.ID >= FirstRaiderRefId).ToList();
        Need(raiders.Count > 0 && raiders.All(r => r.Base.FormKey == new FormKey(m.Raider.ModKey, RaiderId)), "no raider ACHR on FO4_LvlRaider");

        var q = plug.Quests.FirstOrDefault(x => x.FormKey == new FormKey(key, QuestId));
        if (q is null) problems.Add("no QUST 0x800");
        else
        {
            Console.WriteLine($"  QUST {q.EditorID} \"{q.Name?.String}\" flags {q.Data?.Flags} stages [{string.Join(",", q.Stages.Select(s => s.Index))}] " +
                              $"objectives [{string.Join("; ", q.Objectives.Select(o => $"{o.Index} \"{o.DisplayText?.String}\" targets {o.Targets.Count}"))}] aliases {q.Aliases?.Count ?? 0}");
            Need(q.EditorID == QuestEdid && q.Data is not null && q.Data.Flags.HasFlag(SF.Quest.Flag.StartGameEnabled), "the quest is not FO4SF_Min00, start game enabled");
            Need(q.Stages.Select(s => s.Index).SequenceEqual(Stages), "stages differ from the script's");
            Need(q.Stages.LastOrDefault()?.LogEntries.Any(l => l.Flags?.HasFlag(SF.QuestLogEntry.Flag.CompleteQuest) == true) == true, "stage 200 does not complete the quest");
            Need(q.Objectives.Select(o => o.Index).SequenceEqual(Objectives.Select(o => o.Index)), "objectives differ from the script's");
            Need(q.Objectives.All(o => !string.IsNullOrWhiteSpace(o.DisplayText?.String)), "an objective has no text");
            if (alias)
            {
                var al = (q.Aliases ?? new List<SF.IAQuestAliasGetter>()).OfType<SF.IQuestReferenceAliasGetter>().FirstOrDefault(a => a.ID == PrestonAlias);
                Need(al is not null && al.ForcedReference.FormKey == preston?.FormKey, "alias 0 is not forced to Preston's ACHR");
                Need(q.Objectives.Where((o, i) => Objectives[i].TargetsPreston).All(o => o.Targets.Count == 1 && o.Targets[0].AliasID == PrestonAlias),
                     "Preston's objectives do not target alias 0");
            }
            else Need((q.Aliases?.Count ?? 0) == 0 && q.Objectives.All(o => o.Targets.Count == 0), "--no-alias build carries an alias or a target");
            var s = q.VirtualMachineAdapter?.Scripts.FirstOrDefault(x => x.Name == ScriptName);
            if (s is null) problems.Add($"script {ScriptName} not attached");
            else
            {
                var props = s.Properties.ToDictionary(p => p.Name);
                Console.WriteLine($"  script {s.Name}: " + string.Join(", ", props.Keys));
                Need(props.TryGetValue("Preston", out var pp) && pp is SF.IScriptObjectPropertyGetter po && po.Object.FormKey == preston?.FormKey, "property Preston");
                Need(props.TryGetValue("Credits", out var cp) && cp is SF.IScriptObjectPropertyGetter co && co.Object.FormKey == new FormKey(SfEsm, CreditsId), "property Credits");
                Need(props.TryGetValue("Raiders", out var rp) && rp is SF.IScriptObjectListPropertyGetter rl &&
                     rl.Objects.Select(o => o.Object.FormKey).SequenceEqual(raiders.Select(r => r.FormKey)), "property Raiders lists the raider ACHRs in order");
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
        // a stand-in Starfield.esm: the Credits MISC at 00000F
        var sf = new SF.StarfieldMod(SfEsm, rel);
        sf.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Master;
        sf.MiscItems.Add(new SF.MiscItem(new FormKey(SfEsm, CreditsId), rel) { EditorID = "Credits" });
        sf.ModHeader.Stats.NextFormID = 0x800;
        var sfPath = Path.Combine(dir, "Starfield.esm");
        sf.BeginWrite.ToPath(sfPath).WithNoLoadOrder().NoCheckIfLowerRangeDisallowed().Write();
        // a core with the world and its persistent cell (holding one marker of its own, which the override must drop)
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
        // a raider plugin with the conversion and the calm probe
        var raiderKey = ModKey.FromFileName("FO4ActorRaider.esm");
        var raider = new SF.StarfieldMod(raiderKey, rel);
        raider.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Master;
        raider.Npcs.Add(new SF.Npc(new FormKey(raiderKey, RaiderId), rel) { EditorID = "FO4_LvlRaider", Name = "Raider", Flags = SF.Npc.Flag.Respawn });
        raider.Npcs.Add(new SF.Npc(new FormKey(raiderKey, CalmProbeId), rel) { EditorID = "FO4_LvlRaider_Calm", Name = "Raider", Flags = SF.Npc.Flag.Respawn });
        raider.ModHeader.Stats.NextFormID = 0xF04802;
        var raiderPath = Path.Combine(dir, raiderKey.FileName);
        raider.BeginWrite.ToPath(raiderPath).WithLoadOrder(SfEsm).WithKnownMasters(new KeyedMasterStyle(SfEsm, MasterStyle.Full)).Write();
        // points as `points` writes them
        var pointsPath = Path.Combine(dir, "points.json");
        File.WriteAllText(pointsPath, """
        {"quest_name": "When Freedom Calls", "preston_name": "Preston Garvey",
         "objectives": {"10": "Find the Last Minutemen", "85": "Kill the Raiders", "86": "Talk to Preston Garvey"},
         "preston": {"src": "01E2EA:XTEL", "pos": [-880.5, 1050.25, 90.0], "rot": [0, 0, 1.5]},
         "raiders": [{"src": "046458", "pos": [-829.06, 1008.31, 88.09], "rot": [0, 0, 0.5]},
                     {"src": "046459", "pos": [-835.0, 1012.0, 88.5], "rot": [0, 0, 0.0]}]}
        """);
        var outDir = Path.Combine(dir, "out");
        foreach (var alias in new[] { true, false })
        {
            var o = Path.Combine(outDir, alias ? "alias" : "noalias");
            int rc = Write(sfPath, corePath, raiderPath, pointsPath, o, Plugin, World, alias);
            if (rc != 0) return rc;
            rc = Check(Path.Combine(o, Plugin), sfPath, corePath, raiderPath, alias);
            if (rc != 0) return rc;
        }
        Console.WriteLine("selftest pass");
        return 0;
    }
}
