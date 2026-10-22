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
//   and an override of every one of those REFRs (the owner's play test of 2026-10-22, docs/terrain/map-markers.md
//   "Overrides"): the map-marker flags without UseLocationName (the core copies LC172's 0x1B, and the map then
//   printed the cell's location name instead of the marker's), and the position lifted by ZLift metres (the Concord
//   arrival stood half in the ground at the sampled terrain height; the Red Rocket one dropped 1.9 m without harm).
//   LocalZ holds the lifted height, so the mover puts the marker where the override says.
// The override's containers, the core's WRLD and its persistent CELL, come along as copies that override the core's
// records too (this plugin loads after it), so a stage belongs to one core build. --world takes the WRLD copy from
// dotnet/BorderProbe's variants instead of the core (the border settling test, Interiors, 2026-10-22):
//   control  as the core (SmallWorld kept, HNAM as the core's: today's)
//   nosmall  DATA without SmallWorld, HNAM as the core's
//   city     DATA without SmallWorld, HNAM 5
// check expects the same variant (--world again) and fails any other copy.
// The quest's VMAD shape is dotnet/Bridge's (vanilla Starfield quests: version 6, object format 2, extra-bind-data
// version 3, an empty fragment script entry, object properties with alias -1; record version 581 / 12).
//
// usage: MapMarkers build --core <FO4TerrainCore.esm> --out <dir> [--plugin FO4SFMapMarkers.esm] [--z-lift <m>] [--world control|nosmall|city]
//        MapMarkers check <plugin> <FO4TerrainCore.esm> [--z-lift <m>] [--world control|nosmall|city]   reads both back (exit 1 on a mismatch)
using System.Globalization;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;

const uint QuestId = 0x800, MapMarkerStat = 0x10;
const int PerQuest = 100, DefaultMaxMoves = 40;
const float DefaultZLift = 2.5f;        // metres above the core's sampled terrain height (local units are metres)
const float ZLiftStep = 0.1f;           // lifts come in steps of 0.1 m: the mover's ZTolerance (0.05 m, half a step) then tells
                                        // a marker a save holds at an earlier build's height from one that landed (Codex on #483)
const string ScriptName = "FO4SF_MapMarkers";
var sfKey = ModKey.FromFileName("Starfield.esm");

static int Usage()
{
    Console.Error.WriteLine("usage: MapMarkers build --core <FO4TerrainCore.esm> --out <dir> [--plugin FO4SFMapMarkers.esm] [--z-lift <m>] [--world control|nosmall|city] | " +
                            "MapMarkers check <plugin> <FO4TerrainCore.esm> [--z-lift <m>] [--world control|nosmall|city]");
    return 2;
}
if (args.Length == 0) return Usage();
string Arg(string name, string dflt) { var i = Array.IndexOf(args, name); return i >= 0 && i + 1 < args.Length ? args[i + 1] : dflt; }
float zLift;
if (!float.TryParse(Arg("--z-lift", F(DefaultZLift)), NumberStyles.Float, CultureInfo.InvariantCulture, out zLift) || !float.IsFinite(zLift) || zLift < 0)
{
    Console.Error.WriteLine("--z-lift needs a non-negative number of metres");
    return 2;
}
if (Math.Abs(zLift / ZLiftStep - Math.Round(zLift / ZLiftStep)) > 1e-3)
{
    Console.Error.WriteLine($"--z-lift must be a multiple of {F(ZLiftStep)} m: FO4SF_MapMarkers.psc re-moves a saved marker only when its height " +
                            $"is off by more than ZTolerance ({F(ZLiftStep / 2)} m), so a smaller change between builds would never reach a save");
    return 2;
}
var world = Arg("--world", "control");
if (world is not ("control" or "nosmall" or "city"))
{
    Console.Error.WriteLine($"--world {world}: want control (the core's world record), nosmall or city (dotnet/BorderProbe's variants of it)");
    return 2;
}

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

    // the overrides: the same REFRs under the core's FormKeys, with the marker's own name shown and a lifted arrival
    var cache = core.ToImmutableLinkCache();
    var lifted = new Dictionary<FormKey, P3Float>();
    foreach (var m in markers)
    {
        var ctx = cache.ResolveContext<IPlacedObject, IPlacedObjectGetter>(m.FormKey);
        var ov = ctx.GetOrAddAsOverride(mod);
        Override(ov, zLift);
        lifted[m.FormKey] = ov.Position;
    }
    // the override's parents come along as copies of the core's worldspace and its persistent cell, with every
    // persistent reference of that cell; keep only the markers (an override of anything else is not this plugin's)
    foreach (var w in mod.Worldspaces)
    {
        w.SubCells.Clear();
        if (w.TopCell == null) continue;
        w.TopCell.Persistent.RemoveAll(r => !lifted.ContainsKey(r.FormKey));
        w.TopCell.Temporary.Clear();
    }
    foreach (var w in mod.Worldspaces) WorldVariant(w, world);       // the WRLD copy as the probe's variant

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
            foreach (var m in part) list.Data.Add(pick(lifted[m.FormKey]));     // the override's position
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
                      $"{markers.Count} marker(s) overridden (own name shown, lifted {F(zLift)} m), world copy --world {world} ({WorldDescribed(world)}):");
    foreach (var w in mod.Worldspaces)
        Console.WriteLine($"  worldspace {w.FormKey} {w.EditorID}: flags {w.Flags?.ToString() ?? "-"}, HNAM [{string.Join(", ", w.HNAM?.ToArray() ?? Array.Empty<byte>())}]");
    foreach (var m in markers)
        Console.WriteLine($"  {m.FormKey} {m.EditorID} \"{m.MapMarker?.Name}\" local ({F(m.Position.X)}, {F(m.Position.Y)}, {F(m.Position.Z)}) -> z {F(lifted[m.FormKey].Z)}");
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
    // every core marker has an override here: its name shown, Visible kept, the position lifted by zLift
    var overrides = mod.EnumerateMajorRecords<IPlacedObjectGetter>().Where(r => r.FormKey.ModKey == core.ModKey)
        .ToDictionary(r => r.FormKey);
    var expect = new Dictionary<FormKey, P3Float>();
    foreach (var m in want)
    {
        var target = Lifted(m.Position, zLift);
        expect[m.FormKey] = target;
        if (!overrides.TryGetValue(m.FormKey, out var ov))
        {
            problems.Add($"{m.FormKey} {m.EditorID} has no override");
            continue;
        }
        var flags = ov.MapMarker?.Flags;
        Console.WriteLine($"  override {ov.FormKey} \"{ov.MapMarker?.Name}\" flags {(flags.HasValue ? ((int)flags.Value).ToString("X2") : "none")} " +
                          $"at ({F(ov.Position.X)}, {F(ov.Position.Y)}, {F(ov.Position.Z)})");
        if (ov.MapMarker == null || flags == null) problems.Add($"{m.FormKey} override has no map-marker data");
        else
        {
            if (flags.Value.HasFlag(PlacedObjectMapMarker.Flag.UseLocationName)) problems.Add($"{m.FormKey} override still uses the location's name");
            if (!flags.Value.HasFlag(PlacedObjectMapMarker.Flag.Visible)) problems.Add($"{m.FormKey} override is not Visible");
            if (ov.MapMarker.Name?.String != m.MapMarker?.Name?.String) problems.Add($"{m.FormKey} override name \"{ov.MapMarker.Name}\" != \"{m.MapMarker?.Name}\"");
        }
        if (ov.Position != target) problems.Add($"{m.FormKey} override at z {F(ov.Position.Z)}, not the core's {F(m.Position.Z)} lifted {F(zLift)} m");
        if ((ov.MajorRecordFlagsRaw & 0x800) != 0) problems.Add($"{m.FormKey} override is Initially Disabled");
        if (ov.Base.FormKey != m.Base.FormKey) problems.Add($"{m.FormKey} override has another base");
    }
    foreach (var extra in overrides.Keys.Except(want.Select(m => m.FormKey)))
        problems.Add($"{extra} is overridden but is not a core map marker");
    // the containers the overrides need, the WRLD and its persistent CELL, are copies of the core's records, and a
    // plugin that loads after the core overrides them with whatever it holds: they must match the core this plugin
    // is checked against, or a core rebuilt since the stage (a changed world flag, say) is undone by this plugin
    foreach (var w in mod.Worldspaces)
    {
        var cw = core.Worldspaces.FirstOrDefault(x => x.FormKey == w.FormKey);
        if (cw == null) { problems.Add($"{w.FormKey} worldspace is not the core's"); continue; }
        var wmask = new Worldspace.TranslationMask(defaultOn: true)
        {
            TopCell = new Cell.TranslationMask(defaultOn: false, onOverall: false),
            SubCells = new WorldspaceBlock.TranslationMask(defaultOn: false, onOverall: false),
            SubCellsTimestamp = false, SubCellsUnknown = false,
        };
        var wantWorld = cw.DeepCopy(wmask);
        WorldVariant(wantWorld, world);                              // the core's record as the variant asked for
        var wantName = world == "control" ? "the core's" : $"the core's with --world {world}";
        var sameWorld = wantWorld.Equals(w.DeepCopy(wmask));
        Console.WriteLine($"  worldspace {w.FormKey} {w.EditorID}: flags {w.Flags?.ToString() ?? "-"}, HNAM [{string.Join(", ", w.HNAM?.ToArray() ?? Array.Empty<byte>())}]" +
                          (sameWorld ? $", as {wantName}" : $", NOT {wantName}"));
        if (!sameWorld)
            problems.Add(world == "control"
                ? $"{w.FormKey} worldspace record differs from the core's (a core rebuilt since the stage: stage again)"
                : $"{w.FormKey} worldspace record differs from the core's with --world {world} (a stage with another --world, or a core rebuilt since it: stage again)");
        if (w.SubCells.Count > 0) problems.Add($"{w.FormKey} worldspace carries {w.SubCells.Count} sub-cell block(s)");
        if (w.TopCell == null) continue;
        if (cw.TopCell == null) { problems.Add($"{w.FormKey} has a persistent cell the core lacks"); continue; }
        var cmask = new Cell.TranslationMask(defaultOn: true)
        {
            Persistent = false, Temporary = false, NavigationMeshes = new NavigationMesh.TranslationMask(defaultOn: false, onOverall: false),
            Timestamp = false, UnknownGroupData = false, PersistentTimestamp = false, PersistentUnknownGroupData = false,
            TemporaryTimestamp = false, TemporaryUnknownGroupData = false,
        };
        if (!cw.TopCell.DeepCopy(cmask).Equals(w.TopCell.DeepCopy(cmask)))
            problems.Add($"{w.TopCell.FormKey} persistent cell record differs from the core's (a core rebuilt since the stage: stage again)");
        if (w.TopCell.Temporary.Count > 0) problems.Add($"{w.TopCell.FormKey} carries {w.TopCell.Temporary.Count} temporary reference(s)");
    }
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
            if (data == null || !data.SequenceEqual(part.Select(m => pick(expect[m.FormKey]))))
                problems.Add($"{tag}{name} does not hold the markers' overridden positions");
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
static P3Float Lifted(P3Float p, float lift) => new P3Float(p.X, p.Y, p.Z + lift);
// the override: the same record, the marker's own name on the map, enabled, lifted; everything else as the core wrote it
static void Override(IPlacedObject ov, float lift)
{
    ov.Position = Lifted(ov.Position, lift);
    ov.MajorRecordFlagsRaw = (ov.MajorRecordFlagsRaw | 0x400) & ~0x800;
    if (ov.MapMarker == null) throw new InvalidDataException($"{ov.FormKey} has no map-marker data");
    ov.MapMarker.Flags = (ov.MapMarker.Flags | PlacedObjectMapMarker.Flag.Visible) & ~PlacedObjectMapMarker.Flag.UseLocationName;
}
// the WRLD copy as dotnet/BorderProbe writes the variant: nosmall and city drop SmallWorld, city sets HNAM 5; control leaves the core's
static void WorldVariant(IWorldspace w, string variant)
{
    if (variant is "nosmall" or "city") w.Flags = (w.Flags ?? 0) & ~Worldspace.Flag.SmallWorld;
    if (variant is "city") w.HNAM = new MemorySlice<byte>(new byte[] { 5 });
}
static string WorldDescribed(string variant) => variant switch
{
    "nosmall" => "SmallWorld cleared, HNAM as the core's",
    "city" => "SmallWorld cleared, HNAM 5",
    _ => "as the core's",
};
static string QuestName(int k) => "FO4SF_MapMarkersQuest" + (k == 0 ? "" : (k + 1).ToString(CultureInfo.InvariantCulture));
// the script's own default (40) holds up to 20 markers; above that, twice the quest's markers
static int? MaxMovesFor(int n) => 2 * n > DefaultMaxMoves ? 2 * n : null;
