// LodGate: the tiny custom-world gate for the Creation Kit's -MockWorldSpaceLOD (docs/terrain/object-lod.md "What the
// runs showed"). On the PC the mock bakes vanilla LC172World but answers "Failed to find worldspace" for our core's
// FO4Core_Commonwealth, by name, by form ID and with a LODSettings file placed (runs A, B, C, 2026-10-22). Does the
// generator find any worldspace a plugin adds? Three plugins, each one small world of nine empty cells around the
// origin plus a few references to the largest vanilla statics (so a bake has objects to write placeholders for):
//   FO4SFLodGate1.esm  FO4SF_LodGate1  the WRLD record copied from vanilla LC172World (the writer's own template),
//                                      master-flagged like the core; masters: Starfield.esm
//   FO4SFLodGate2.esp  FO4SF_LodGate2  the same without the Master header flag
//   FO4SFLodGate3.esm  FO4SF_LodGate3  the WRLD record copied from our core's FO4Core_Commonwealth (its location
//                                      and surface block links kept); masters: Starfield.esm, FO4TerrainCore.esm
// The run card: CreationKit.exe -MockWorldSpaceLOD:FO4SFLodGate1.esm FO4SF_LodGate1 with the plugin in Data (the
// same backup protocol as the earlier runs). A bake of 1 and not 3 points at our record's fields; a bake of 3 too
// points at the core's scale or cell tree; no bake of 1 says the generator does not find plugin worlds at all,
// and 2 then tells whether the Master flag is the reason.
//
// usage: LodGate build <Starfield.esm> <FO4TerrainCore.esm> <out dir> [--statics N]     N largest statics, default 3
//        LodGate show <plugin> <Starfield.esm> [<FO4TerrainCore.esm>]                  reads a gate plugin back
//        LodGate fixture <dir>      synthetic Starfield.esm and FO4TerrainCore.esm for tests/test_lod_gate.py
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;

const string TemplateWorld = "LC172World", CoreWorld = "FO4Core_Commonwealth";
const int CellRadius = 1;                                 // cells -1..1 on both axes: nine
var release = StarfieldRelease.Starfield;

static int Usage()
{
    Console.Error.WriteLine("usage: LodGate build <Starfield.esm> <FO4TerrainCore.esm> <out dir> [--statics N] | " +
                            "LodGate show <plugin> <Starfield.esm> [<FO4TerrainCore.esm>] | LodGate fixture <dir>");
    return 2;
}
if (args.Length == 0) return Usage();
if (args[0] == "fixture") return args.Length == 2 ? Fixture(args[1]) : Usage();

var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
BinaryReadParameters Params() => new() { MasterFlagsLookup = styles };
IStarfieldModDisposableGetter Load(string path)
{
    var m = StarfieldMod.CreateFromBinaryOverlay(path, release, Params());
    styles.Set(new KeyedMasterStyle(m.ModKey, MasterStyle.Full));
    return m;
}
static string Show(IWorldspaceGetter w) =>
    $"Flags {w.Flags?.ToString() ?? "-"}, HNAM [{string.Join(", ", w.HNAM?.ToArray() ?? Array.Empty<byte>())}], " +
    $"location {w.Location.FormKeyNullable?.ToString() ?? "-"}, components [{string.Join(", ", w.Components.Select(c => c.GetType().Name))}]";
static IEnumerable<ICellGetter> Cells(IWorldspaceGetter w) => w.SubCells.SelectMany(b => b.Items).SelectMany(s => s.Items);

if (args[0] == "show" && args.Length >= 3)
{
    using var sf = Load(args[2]);
    using var core = args.Length > 3 ? Load(args[3]) : null;
    using var mod = Load(args[1]);
    var masters = mod.ModHeader.MasterReferences.Select(m => m.Master.FileName.String).ToList();
    Console.WriteLine($"{mod.ModKey.FileName}: header flags {mod.ModHeader.Flags}, masters [{string.Join(", ", masters)}]");
    foreach (var w in mod.Worldspaces)
    {
        var cells = Cells(w).ToList();
        Console.WriteLine($"  {w.EditorID} {w.FormKey}: {Show(w)}, persistent cell {(w.TopCell == null ? "none" : w.TopCell.FormKey.ToString())}, " +
                          $"{cells.Count} cell(s) at [{string.Join(", ", cells.Select(c => c.Grid == null ? "?" : $"({c.Grid.Point.X},{c.Grid.Point.Y})"))}]");
        foreach (var c in cells)
            foreach (var r in c.Temporary.Concat(c.Persistent).OfType<IPlacedObjectGetter>())
                Console.WriteLine($"    ref {r.FormKey} {r.EditorID} base {r.Base.FormKey} at ({r.Position.X}, {r.Position.Y}, {r.Position.Z})");
    }
    return 0;
}

if (args[0] == "build" && args.Length >= 4)
{
    var statics = 3;
    var ni = Array.IndexOf(args, "--statics");
    if (ni >= 0 && (ni + 1 >= args.Length || !int.TryParse(args[ni + 1], out statics) || statics < 1)) return Usage();
    using var sf = Load(args[1]);
    using var core = Load(args[2]);
    var outDir = args[3];
    var template = sf.Worldspaces.FirstOrDefault(w => w.EditorID == TemplateWorld);
    if (template == null) { Console.Error.WriteLine($"{args[1]}: no worldspace {TemplateWorld}"); return 1; }
    var ours = core.Worldspaces.FirstOrDefault(w => w.FormKey.ModKey == core.ModKey && w.EditorID == CoreWorld);
    if (ours == null) { Console.Error.WriteLine($"{args[2]}: no worldspace {CoreWorld} of its own"); return 1; }
    // the vanilla statics with the widest object bounds, by extent then form ID: the same picks on every run
    var big = sf.Statics.Where(s => s.FormKey.ModKey == sf.ModKey)
        .Select(s => (s, extent: Extent(s)))
        .OrderByDescending(x => x.extent).ThenBy(x => x.s.FormKey.ID).Take(statics).Select(x => x.s).ToList();
    if (big.Count == 0) { Console.Error.WriteLine($"{args[1]}: no STAT"); return 1; }
    Console.WriteLine($"statics ({big.Count} largest by object bounds): " +
                      string.Join(", ", big.Select(s => $"{s.FormKey} {s.EditorID} ({Extent(s)})")));
    Directory.CreateDirectory(outDir);
    foreach (var (n, master, from, lo) in new (int, bool, IWorldspaceGetter, ModKey[])[]
             {
                 (1, true, template, new[] { sf.ModKey }),
                 (2, false, template, new[] { sf.ModKey }),
                 (3, true, ours, new[] { sf.ModKey, core.ModKey }),
             })
    {
        var modKey = ModKey.FromFileName($"FO4SFLodGate{n}.{(master ? "esm" : "esp")}");
        var mod = new StarfieldMod(modKey, release);
        if (master) mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        uint next = 0x800;
        FormKey NewKey() => new(modKey, next++);
        var w = (Worldspace)from.Duplicate(NewKey());             // the record as the template has it, a new cell tree
        w.EditorID = $"FO4SF_LodGate{n}";
        w.Name = $"FO4SF LOD gate {n}";
        w.SubCells.Clear();
        w.TopCell = null;
        w.OffsetData = null;                                       // as dotnet/TerrainOverlays: OFST / CLSZ belong to the old cells
        w.CellSizeData = null;
        w.TopCell = new Cell(NewKey(), release) { Flags = Cell.Flag.HasWater };
        var blocks = new Dictionary<(int, int), WorldspaceBlock>();
        var subs = new Dictionary<(int, int), WorldspaceSubBlock>();
        for (int x = -CellRadius; x <= CellRadius; x++)
            for (int y = -CellRadius; y <= CellRadius; y++)
            {
                var c = new Cell(NewKey(), release) { Grid = new CellGrid { Point = new P2Int(x, y) } };
                if (x == 0 && y == 0)
                    for (int i = 0; i < big.Count; i++)        // a metre or two into the origin cell, one per static
                        c.Temporary.Add(new PlacedObject(NewKey(), release)
                        {
                            EditorID = $"FO4SF_LodGate{n}Stat{i + 1}",
                            Base = new FormLinkNullable<IPlaceableObjectGetter>(big[i].FormKey),
                            Position = new P3Float(1 + i, 1, 0), Rotation = new P3Float(0, 0, 0),
                        });
                int bx = (int)Math.Floor(x / 32.0), by = (int)Math.Floor(y / 32.0), sx = (int)Math.Floor(x / 8.0), sy = (int)Math.Floor(y / 8.0);
                if (!blocks.TryGetValue((bx, by), out var blk)) { blk = new WorldspaceBlock { BlockNumberX = (short)bx, BlockNumberY = (short)by, GroupType = GroupTypeEnum.ExteriorCellBlock }; blocks[(bx, by)] = blk; w.SubCells.Add(blk); }
                if (!subs.TryGetValue((sx, sy), out var sub)) { sub = new WorldspaceSubBlock { BlockNumberX = (short)sx, BlockNumberY = (short)sy, GroupType = GroupTypeEnum.ExteriorCellSubBlock }; subs[(sx, sy)] = sub; blk.Items.Add(sub); }
                sub.Items.Add(c);
            }
        mod.Worldspaces.Add(w);
        mod.ModHeader.Stats.NextFormID = next;
        var path = Path.Combine(outDir, modKey.FileName);
        mod.BeginWrite.ToPath(path).WithLoadOrder(lo)
            .WithKnownMasters(lo.Select(k => new KeyedMasterStyle(k, MasterStyle.Full)).ToArray())
            .WithExtraIncludedMasters(lo).Write();
        Console.WriteLine($"wrote {path} ({new FileInfo(path).Length:N0} bytes): {w.EditorID} {w.FormKey} from {from.EditorID} {from.FormKey}: " +
                          $"{Show(w)}, {Cells(w).Count()} cells, {big.Count} refs; masters [{string.Join(", ", lo.Select(k => k.FileName))}]");
    }
    return 0;
}
return Usage();

static float Extent(IStaticGetter s)
{
    var b = s.ObjectBounds;
    if (b == null) return 0;
    return Math.Max(b.Second.X - b.First.X, b.Second.Y - b.First.Y);
}

// the synthetic inputs: a Starfield.esm stand-in with LC172World and four statics of known bounds, and a core whose
// FO4Core_Commonwealth links a location of its own (as the writer's does)
static int Fixture(string dir)
{
    var rel = StarfieldRelease.Starfield;
    Directory.CreateDirectory(dir);
    var sfKey = ModKey.FromFileName("Starfield.esm");
    var sf = new StarfieldMod(sfKey, rel);
    sf.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
    var loc = new Location(new FormKey(sfKey, 0x3807BE), rel) { EditorID = "LC172WorldLocation" };
    sf.Locations.Add(loc);
    var world = new Worldspace(new FormKey(sfKey, 0x02DF8C), rel)
    {
        EditorID = TemplateWorld, Name = "Mars", Flags = Worldspace.Flag.SmallWorld, HNAM = new MemorySlice<byte>(new byte[] { 0 }),
    };
    world.Location.SetTo(loc.FormKey);
    world.TopCell = new Cell(new FormKey(sfKey, 0x02DF8D), rel);
    sf.Worldspaces.Add(world);
    foreach (var (id, edid, half) in new (uint, string, float)[] { (0x1000, "StatSmall", 1), (0x1001, "StatBig1", 100), (0x1002, "StatBig2", 80), (0x1003, "StatBig3", 60) })
        sf.Statics.Add(new Static(new FormKey(sfKey, id), rel)
        {
            EditorID = edid,
            ObjectBounds = new ObjectBounds { First = new P3Float(-half, -half, 0), Second = new P3Float(half, half, half) },
        });
    sf.ModHeader.Stats.NextFormID = 0x1004;
    sf.BeginWrite.ToPath(Path.Combine(dir, sfKey.FileName)).WithNoLoadOrder().NoCheckIfLowerRangeDisallowed().Write();

    var coreKey = ModKey.FromFileName("FO4TerrainCore.esm");
    var core = new StarfieldMod(coreKey, rel);
    core.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
    var cloc = new Location(new FormKey(coreKey, 0x801), rel) { EditorID = "FO4Core_CommonwealthLocation" };
    core.Locations.Add(cloc);
    var cw = new Worldspace(new FormKey(coreKey, 0x803), rel)
    {
        EditorID = CoreWorld, Name = "Commonwealth", Flags = Worldspace.Flag.SmallWorld, HNAM = new MemorySlice<byte>(new byte[] { 0 }),
    };
    cw.Location.SetTo(cloc.FormKey);
    cw.TopCell = new Cell(new FormKey(coreKey, 0x900), rel);
    cw.TopCell.Persistent.Add(new PlacedObject(new FormKey(coreKey, 0x800), rel) { EditorID = "SyntheticAnchor" });
    core.Worldspaces.Add(cw);
    core.ModHeader.Stats.NextFormID = 0x901;
    core.BeginWrite.ToPath(Path.Combine(dir, coreKey.FileName)).WithLoadOrder(sfKey)
        .WithKnownMasters(new KeyedMasterStyle(sfKey, MasterStyle.Full)).Write();
    Console.WriteLine($"wrote {sfKey}, {coreKey} in {dir}");
    return 0;
}
