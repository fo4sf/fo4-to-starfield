// BorderProbe: which worldspace record field gives our Commonwealth world Starfield's landing-area border
// ("BOUNDARY REACHED")? docs/terrain/border.md.
//
// The border is the engine's border-region system: SetINI "bBorderRegionsEnabled:General" 0 removes it (PC run _f,
// Oct 22: the Vault 95 exit PASSes at 0.00 m with it off and FAILs STAYED with the popup with it on), but that setting
// is global. The vanilla worlds the player walks far in differ from the template our world was copied from
// (LC172World, dotnet/TerrainOverlays) in two WRLD fields (C:\Modding\research\terrain\sf_wrld_dump.txt):
//   DATA flags  NewAtlantis 0, LC172World SmallWorld (424 of 433 vanilla worlds are SmallWorld)
//   HNAM        NewAtlantis, akilacity, NeonCity and 376 others 5; LC172World, PCMShipLanding01..04, LC003 0
// uPlayableSpaceOverlayCellBuffer:Planet is 5 too. Each variant overrides only those fields of the world's winning
// record, so one Vault 95 exit with the border on answers whether that field is the per-world switch:
//   nosmall  DATA without SmallWorld
//   hnam5    HNAM 5
//   city     both (NewAtlantis's values)
//
// usage: BorderProbe show <Starfield.esm> <plugin>...                         the world's fields in each plugin
//        BorderProbe build <Starfield.esm> <out dir> --variant nosmall|hnam5|city [--world <EditorID>] <plugin>...
// <plugin>... is every plugin of ours in load order (at least the core, and every later plugin that overrides the
// world: FO4SFMission.esm does). The probe masters all of them, so it loads after the last override and wins.
// Read-only on its inputs; writes FO4SFBorderProbe_<variant>.esm into <out dir>.
//        BorderProbe fixture <dir>   synthetic Starfield.esm, FO4TerrainCore.esm (a SmallWorld, HNAM 0 world with a
//                                    persistent cell) and FO4SFMission.esm (an override of it) for tests/test_border_probe.py;
//                                    no game file is read
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;

static int Usage()
{
    Console.Error.WriteLine("usage: BorderProbe show <Starfield.esm> <plugin>... | " +
                            "BorderProbe build <Starfield.esm> <out dir> --variant nosmall|hnam5|city [--world <EditorID>] <plugin>...");
    return 2;
}
if (args.Length == 2 && args[0] == "fixture") return Fixture(args[1]);
if (args.Length < 3 || (args[0] != "show" && args[0] != "build")) return Usage();
var opts = new Dictionary<string, string>();
var rest = new List<string>();
for (int i = 1; i < args.Length; i++)
{
    if (args[i] is "--variant" or "--world")
    {
        if (i + 1 >= args.Length) return Usage();
        opts[args[i]] = args[++i];
    }
    else rest.Add(args[i]);
}
bool build = args[0] == "build";
if (rest.Count < (build ? 3 : 2)) return Usage();
var variant = opts.GetValueOrDefault("--variant", "");
if (build && variant is not ("nosmall" or "hnam5" or "city"))
{
    Console.Error.WriteLine($"--variant {variant}: want nosmall, hnam5 or city");
    return 2;
}
var sfPath = rest[0];
var outDir = build ? rest[1] : "";
var pluginPaths = rest.Skip(build ? 2 : 1).ToList();

// every plugin of ours is a full-slot master (their headers carry the Master flag)
var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
var disposables = new List<IDisposable>();
try
{
    var sf = StarfieldMod.CreateFromBinaryOverlay(sfPath, StarfieldRelease.Starfield);
    disposables.Add(sf);
    styles.Set(new KeyedMasterStyle(sf.ModKey, MasterStyle.Full));
    var plugins = new List<IStarfieldModDisposableGetter>();
    foreach (var p in pluginPaths)
    {
        var m = StarfieldMod.CreateFromBinaryOverlay(p, StarfieldRelease.Starfield, new BinaryReadParameters { MasterFlagsLookup = styles });
        disposables.Add(m);
        plugins.Add(m);
        styles.Set(new KeyedMasterStyle(m.ModKey, MasterStyle.Full));
    }

    // the world: a WRLD the first plugin (the core) defines, by EditorID when it defines several
    var core = plugins[0];
    var own = core.Worldspaces.Where(w => w.FormKey.ModKey == core.ModKey).ToList();
    if (opts.TryGetValue("--world", out var edid)) own = own.Where(w => w.EditorID == edid).ToList();
    if (own.Count != 1)
    {
        Console.Error.WriteLine($"{core.ModKey} defines {own.Count} matching WRLD ({string.Join(", ", own.Select(w => w.EditorID))}); " +
                                "name one with --world");
        return 1;
    }
    var key = own[0].FormKey;

    static string Show(IWorldspaceGetter w) =>
        $"Flags {w.Flags?.ToString() ?? "-"}, FNAM [{string.Join(", ", w.FNAM?.ToArray() ?? Array.Empty<byte>())}], " +
        $"HNAM [{string.Join(", ", w.HNAM?.ToArray() ?? Array.Empty<byte>())}], " +
        $"bounds {w.ObjectBoundsMin} .. {w.ObjectBoundsMax} (raw / 4096), components [{string.Join(", ", w.Components.Select(c => c.GetType().Name))}]";
    IWorldspaceGetter? winner = null;
    foreach (var m in plugins)
    {
        var w = m.Worldspaces.FirstOrDefault(x => x.FormKey == key);
        if (w is null) continue;
        Console.WriteLine($"{m.ModKey.FileName}: {w.EditorID} {key}: {Show(w)}");
        winner = w;
    }
    if (!build) return 0;

    var w2 = winner!.DeepCopy(new Worldspace.TranslationMask(defaultOn: true)
    {
        SubCells = new WorldspaceBlock.TranslationMask(defaultOn: false, onOverall: false),
        TopCell = new Cell.TranslationMask(defaultOn: false, onOverall: false),
    });
    w2.SubCells.Clear();
    w2.TopCell = null;                                    // the override changes the WRLD record only
    if (variant is "nosmall" or "city") w2.Flags = (w2.Flags ?? 0) & ~Worldspace.Flag.SmallWorld;
    if (variant is "hnam5" or "city") w2.HNAM = new MemorySlice<byte>(new byte[] { 5 });

    var modKey = ModKey.FromFileName($"FO4SFBorderProbe_{variant}.esm");
    var mod = new StarfieldMod(modKey, StarfieldRelease.Starfield);
    mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;     // as every plugin of ours that loads
    mod.Worldspaces.Add(w2);
    var lo = new[] { sf.ModKey }.Concat(plugins.Select(m => m.ModKey)).ToArray();

    Directory.CreateDirectory(outDir);
    var path = Path.Combine(outDir, modKey.FileName);
    // an existing plugin stays until the write succeeds; Mutagen needs the plugin's own file name, so write in a temp folder
    var tmpDir = Path.Combine(outDir, ".tmp-" + Guid.NewGuid().ToString("N"));
    try
    {
        Directory.CreateDirectory(tmpDir);
        var tmp = Path.Combine(tmpDir, modKey.FileName);
        mod.BeginWrite.ToPath(tmp).WithLoadOrder(lo)
            .WithKnownMasters(lo.Select(k => new KeyedMasterStyle(k, MasterStyle.Full)).ToArray())
            .WithExtraIncludedMasters(lo).Write();               // every plugin given: load after the last override
        File.Move(tmp, path, overwrite: true);
    }
    finally
    {
        if (Directory.Exists(tmpDir)) Directory.Delete(tmpDir, true);
    }
    Console.WriteLine($"wrote {path} ({new FileInfo(path).Length:N0} bytes): {w2.EditorID} {key}: {Show(w2)}");
    return 0;
}
finally
{
    foreach (var d in Enumerable.Reverse(disposables)) d.Dispose();
}

static int Fixture(string dir)
{
    var rel = StarfieldRelease.Starfield;
    Directory.CreateDirectory(dir);
    var sfKey = ModKey.FromFileName("Starfield.esm");
    var sf = new StarfieldMod(sfKey, rel);
    sf.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
    var loc = new Location(new FormKey(sfKey, 0x800), rel) { EditorID = "SyntheticLocation" };
    sf.Locations.Add(loc);
    sf.ModHeader.Stats.NextFormID = 0x801;
    sf.BeginWrite.ToPath(Path.Combine(dir, sfKey.FileName)).WithNoLoadOrder().NoCheckIfLowerRangeDisallowed().Write();

    var coreKey = ModKey.FromFileName("FO4TerrainCore.esm");
    var core = new StarfieldMod(coreKey, rel);
    core.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
    var world = new Worldspace(new FormKey(coreKey, 0x803), rel)
    {
        EditorID = "SyntheticCoreWorld", Name = "Core", Flags = Worldspace.Flag.SmallWorld, HNAM = new MemorySlice<byte>(new byte[] { 0 }),
    };
    world.Location.SetTo(loc.FormKey);
    world.TopCell = new Cell(new FormKey(coreKey, 0x900), rel);
    world.TopCell.Persistent.Add(new PlacedObject(new FormKey(coreKey, 0x800), rel) { EditorID = "SyntheticAnchor" });
    core.Worldspaces.Add(world);
    core.ModHeader.Stats.NextFormID = 0x901;
    core.BeginWrite.ToPath(Path.Combine(dir, coreKey.FileName)).WithLoadOrder(sfKey)
        .WithKnownMasters(new KeyedMasterStyle(sfKey, MasterStyle.Full)).Write();

    var missionKey = ModKey.FromFileName("FO4SFMission.esm");
    var mission = new StarfieldMod(missionKey, rel);
    mission.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
    var over = new Worldspace(world.FormKey, rel)
    {
        EditorID = "SyntheticCoreWorld", Name = "Mission", Flags = Worldspace.Flag.SmallWorld, HNAM = new MemorySlice<byte>(new byte[] { 0 }),
    };
    over.Location.SetTo(loc.FormKey);
    mission.Worldspaces.Add(over);
    mission.ModHeader.Stats.NextFormID = 0x800;
    var lo = new[] { sfKey, coreKey };
    mission.BeginWrite.ToPath(Path.Combine(dir, missionKey.FileName)).WithLoadOrder(lo)
        .WithKnownMasters(lo.Select(k => new KeyedMasterStyle(k, MasterStyle.Full)).ToArray()).Write();
    Console.WriteLine($"wrote {sfKey}, {coreKey}, {missionKey} in {dir}");
    return 0;
}
