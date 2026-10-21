// MapMarkers: the plugin that puts the core's map markers into the merged world (docs/terrain/map-markers.md
// "Markers in the merged world", scripts/mapmarkers/make_map_markers.py).
//
// FO4SFMapMarkers.esm (master: the core plugin, the only file it references) holds one quest per PerQuest markers:
//   0x800  QUST FO4SF_MapMarkersQuest  start-game-enabled, no stages, carrying FO4SF_MapMarkers
//          (scripts/mapmarkers/FO4SF_MapMarkers.psc) with Markers -> the core's MapMarker REFRs (base STAT 00000010
//          of Starfield.esm) in FormID order, LocalX / LocalY / LocalZ -> their written positions, and MaxMoves ->
//          twice its marker count when that is above the script's default 40
//   0x801  FO4SF_MapMarkersQuest2, ... the next PerQuest markers, the same way. Papyrus arrays hold at most 128
//          entries when made in script; whether a plugin-filled property may hold more is unverified, so no quest
//          gets more than 100.
// The quest's VMAD shape is dotnet/Bridge's (vanilla Starfield quests: version 6, object format 2, extra-bind-data
// version 3, an empty fragment script entry, object properties with alias -1; record version 581 / 12).
//
// usage: MapMarkers build --core <FO4TerrainCore.esm> --out <dir> [--plugin FO4SFMapMarkers.esm]
//        MapMarkers check <plugin> <FO4TerrainCore.esm>   reads both back (exit 1 on a mismatch)
using System.Globalization;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;

const uint QuestId = 0x800, MapMarkerStat = 0x10;
const int PerQuest = 100, DefaultMaxMoves = 40;
const string ScriptName = "FO4SF_MapMarkers";
var sfKey = ModKey.FromFileName("Starfield.esm");

static int Usage()
{
    Console.Error.WriteLine("usage: MapMarkers build --core <FO4TerrainCore.esm> --out <dir> [--plugin FO4SFMapMarkers.esm] | " +
                            "MapMarkers check <plugin> <FO4TerrainCore.esm>");
    return 2;
}
if (args.Length == 0) return Usage();
string Arg(string name, string dflt) { var i = Array.IndexOf(args, name); return i >= 0 && i + 1 < args.Length ? args[i + 1] : dflt; }

BinaryReadParameters Params(params ModKey[] full)
{
    var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
    foreach (var k in full) styles.Set(new KeyedMasterStyle(k, MasterStyle.Full));
    return new BinaryReadParameters { MasterFlagsLookup = styles };
}

// the core's own MapMarker references, in FormID order
List<IPlacedObjectGetter> CoreMarkers(IStarfieldModGetter core) =>
    core.EnumerateMajorRecords<IPlacedObjectGetter>()
        .Where(r => r.FormKey.ModKey == core.ModKey && r.Base.FormKey == new FormKey(sfKey, MapMarkerStat))
        .OrderBy(r => r.FormKey.ID).ToList();

if (args[0] == "build")
{
    var outDir = Arg("--out", "");
    var corePath = Arg("--core", "");
    if (outDir == "" || corePath == "") return Usage();
    var plugin = Arg("--plugin", "FO4SFMapMarkers.esm");
    var core = StarfieldMod.CreateFromBinaryOverlay(corePath, StarfieldRelease.Starfield, Params(sfKey));
    var markers = CoreMarkers(core);
    if (markers.Count == 0)
    {
        Console.Error.WriteLine($"{corePath}: no MapMarker REFR (base Starfield.esm 00000010) of its own");
        return 1;
    }
    var modKey = ModKey.FromFileName(plugin);
    var mod = new StarfieldMod(modKey, StarfieldRelease.Starfield);
    mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;     // as every plugin of ours that loads

    var chunks = markers.Chunk(PerQuest).ToList();
    for (int k = 0; k < chunks.Count; k++)
    {
        var part = chunks[k];
        var quest = new Quest(new FormKey(modKey, QuestId + (uint)k), StarfieldRelease.Starfield)
        {
            EditorID = QuestName(k), Name = "FO4SF map markers", FormVersion = 581, Version2 = 12,
            Data = new QuestData { Flags = Quest.Flag.StartGameEnabled, Priority = 30 },
        };
        var script = new ScriptEntry { Name = ScriptName, Flags = ScriptEntry.Flag.Local };
        var refs = new ScriptObjectListProperty { Name = "Markers", Flags = ScriptProperty.Flag.Edited };
        foreach (var m in part)
            refs.Objects.Add(new ScriptObjectProperty
            {
                Object = new FormLink<IStarfieldMajorRecordGetter>(m.FormKey), Alias = -1, Unused = 0,
            });
        script.Properties.Add(refs);
        foreach (var (name, pick) in new (string, Func<P3Float, float>)[] { ("LocalX", p => p.X), ("LocalY", p => p.Y), ("LocalZ", p => p.Z) })
        {
            var list = new ScriptFloatListProperty { Name = name, Flags = ScriptProperty.Flag.Edited };
            foreach (var m in part) list.Data.Add(pick(m.Position));
            script.Properties.Add(list);
        }
        if (MaxMovesFor(part.Length) is int cap)                     // every marker may need a move, plus retries
            script.Properties.Add(new ScriptIntProperty { Name = "MaxMoves", Flags = ScriptProperty.Flag.Edited, Data = cap });
        var vmad = new QuestAdapter
        {
            Version = 6, ObjectFormat = 2, ExtraBindDataVersion = 3,
            Script = new ScriptEntry { Name = "", Flags = ScriptEntry.Flag.Local },
        };
        vmad.Scripts.Add(script);
        quest.VirtualMachineAdapter = vmad;
        mod.Quests.Add(quest);
    }

    mod.ModHeader.Stats.NextFormID = QuestId + (uint)chunks.Count;
    Directory.CreateDirectory(outDir);
    var path = Path.Combine(outDir, plugin);
    mod.BeginWrite.ToPath(path).WithLoadOrder(sfKey, core.ModKey)
        .WithKnownMasters(new KeyedMasterStyle(sfKey, MasterStyle.Full), new KeyedMasterStyle(core.ModKey, MasterStyle.Full)).Write();
    Console.WriteLine($"wrote {path} ({new FileInfo(path).Length:N0} bytes): {chunks.Count} quest(s) " +
                      $"{string.Join(", ", mod.Quests.Select(q => $"{q.EditorID} {q.FormKey}"))} script {ScriptName}, " +
                      $"{markers.Count} marker(s):");
    foreach (var m in markers)
        Console.WriteLine($"  {m.FormKey} {m.EditorID} local ({F(m.Position.X)}, {F(m.Position.Y)}, {F(m.Position.Z)})");
    return 0;
}

if (args[0] == "check" && args.Length >= 3)
{
    var core = StarfieldMod.CreateFromBinaryOverlay(args[2], StarfieldRelease.Starfield, Params(sfKey));
    var mod = StarfieldMod.CreateFromBinaryOverlay(args[1], StarfieldRelease.Starfield, Params(sfKey, core.ModKey));
    var problems = new List<string>();
    var masters = mod.ModHeader.MasterReferences.Select(m => m.Master.FileName.String).ToList();
    Console.WriteLine($"{Path.GetFileName(args[1])}: header flags {mod.ModHeader.Flags}, masters [{string.Join(", ", masters)}], " +
                      $"{mod.Quests.Count} QUST");
    if (!masters.Contains(core.ModKey.FileName.String))
        problems.Add($"{core.ModKey.FileName} is not a master");
    var want = CoreMarkers(core);
    var chunks = want.Chunk(PerQuest).ToList();
    var quests = mod.Quests.OrderBy(x => x.FormKey.ID).ToList();
    if (quests.Count != chunks.Count)
        problems.Add($"{quests.Count} quest(s) for {want.Count} marker(s): {chunks.Count} wanted ({PerQuest} per quest)");
    for (int k = 0; k < Math.Min(quests.Count, chunks.Count); k++)
    {
        var q = quests[k];
        var part = chunks[k];
        var tag = k == 0 ? "" : $"quest {k + 1}: ";
        if (q.FormKey.ID != QuestId + (uint)k || q.EditorID != QuestName(k))
        {
            problems.Add($"quest 0x{QuestId + (uint)k:X} {QuestName(k)} missing");
            continue;
        }
        if (q.Data == null || !q.Data.Flags.HasFlag(Quest.Flag.StartGameEnabled)) problems.Add($"{tag}the quest is not StartGameEnabled");
        var s = q.VirtualMachineAdapter?.Scripts.FirstOrDefault(x => x.Name == ScriptName);
        if (s == null)
        {
            problems.Add($"{tag}script {ScriptName} not attached");
            continue;
        }
        var objs = s.Properties.OfType<IScriptObjectListPropertyGetter>().FirstOrDefault(p => p.Name == "Markers")?
            .Objects.ToList() ?? new List<IScriptObjectPropertyGetter>();
        var got = objs.Select(o => o.Object.FormKey).ToList();
        // a direct reference: alias -1, unused 0 (the quest has no aliases; an alias-encoded entry is another binding)
        foreach (var (o, j) in objs.Select((o, j) => (o, j)))
            if (o.Alias != -1 || o.Unused != 0) problems.Add($"{tag}Markers[{j}] is not a direct reference (alias {o.Alias}, unused {o.Unused})");
        Console.WriteLine($"  {tag}Markers: {string.Join(", ", got)}");
        if (!got.SequenceEqual(part.Select(m => m.FormKey)))
            problems.Add($"{tag}Markers [{string.Join(", ", got)}] are not the core's MapMarker REFRs [{string.Join(", ", part.Select(m => m.FormKey))}]");
        foreach (var (name, pick) in new (string, Func<P3Float, float>)[] { ("LocalX", p => p.X), ("LocalY", p => p.Y), ("LocalZ", p => p.Z) })
        {
            var data = s.Properties.OfType<IScriptFloatListPropertyGetter>().FirstOrDefault(p => p.Name == name)?.Data.ToList();
            Console.WriteLine($"  {tag}{name}: {(data == null ? "missing" : string.Join(", ", data.Select(F)))}");
            if (data == null || !data.SequenceEqual(part.Select(m => pick(m.Position))))
                problems.Add($"{tag}{name} does not hold the markers' written positions");
        }
        var cap = s.Properties.OfType<IScriptIntPropertyGetter>().FirstOrDefault(p => p.Name == "MaxMoves")?.Data;
        if (cap != MaxMovesFor(part.Length))
            problems.Add($"{tag}MaxMoves {(cap?.ToString() ?? "default")} != {(MaxMovesFor(part.Length)?.ToString() ?? "default")}");
    }
    foreach (var p in problems) Console.WriteLine("FAIL  " + p);
    Console.WriteLine(problems.Count == 0 ? "all checks pass" : $"{problems.Count} problem(s)");
    return problems.Count == 0 ? 0 : 1;
}
return Usage();

static string F(float v) => v.ToString("0.###", CultureInfo.InvariantCulture);
static string QuestName(int k) => "FO4SF_MapMarkersQuest" + (k == 0 ? "" : (k + 1).ToString(CultureInfo.InvariantCulture));
// the script's own default (40) holds up to 20 markers; above that, twice the quest's markers
static int? MaxMovesFor(int n) => 2 * n > DefaultMaxMoves ? 2 * n : null;
