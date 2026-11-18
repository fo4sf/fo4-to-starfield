// Fo4Land: second, independent decode of Fallout 4 LAND heights for a cell range, through Mutagen's record parser.
// Used to cross-check scripts/terrain/fo4_land_patch.py (our own plugin walker + VHGT decoder). Output is JSON in
// FO4 units; it stays outside the repository (it is derived game data).
//
//   dotnet run --project dotnet/Fo4Land -- <Fallout4.esm> <WorldEditorId> <xmin> <ymin> <xmax> <ymax> <out.json>
//   dotnet run --project dotnet/Fo4Land -- <Fallout4.esm> export-exterior <WorldEditorId> <xmin> <ymin> <xmax> <ymax> <out.json>
//       exterior references as schema v2 placement JSON (ExteriorExport.cs; terrain experiment 2c)
//   dotnet run --project dotnet/Fo4Land -- <Fallout4.esm> export-names <out.json>
//       display names of the Activator / Terminal / Container / MiscItem / Ingestible bases (NamesExport.cs;
//       scripts/terrain/make_cluster.py --names)
//   dotnet run --project dotnet/Fo4Land -- <Fallout4.esm> export-furniture <out.json>
//       every Furniture base with its sit / lean / lie markers (FurnitureExport.cs; docs/terrain/port-promotions.md)
//   dotnet run --project dotnet/Fo4Land -- <Fallout4.esm> export-mapmarkers <out.json> [<WorldEditorId>]
//       every map marker of a world, Commonwealth by default (MapMarkersExport.cs; docs/terrain/map-markers.md)
//
// VHGT layout as documented by fo76utils' fo4land (landdata.cpp): float offset, 33x33 signed byte gradients (row 0 =
// south, column 0 = west; a row's first byte continues from the previous row's first vertex, the others from the
// west neighbour), height = 8 * (offset + accumulated gradient). Mutagen only parses the bytes; the decode is ours.
using System.Text.Json;
using Mutagen.Bethesda;
using Mutagen.Bethesda.Fallout4;

var (strippedArgs, masterPaths, badMasterSyntax) = Fo4LoadOrder.SplitMasters(args);
if (badMasterSyntax)
{
    Console.Error.WriteLine("--master requires a plugin path");
    return 2;
}
args = strippedArgs;

if (args.Length >= 2 && args[1] == "export-exterior") return ExteriorExport.Run(args, masterPaths);
if (args.Length >= 2 && args[1] == "export-names") return NamesExport.Run(args);
if (args.Length >= 2 && args[1] == "export-furniture") return FurnitureExport.Run(args, masterPaths);
if (args.Length >= 2 && args[1] == "export-mapmarkers") return MapMarkersExport.Run(args, masterPaths);
if (args.Length != 7)
{
    Console.Error.WriteLine("usage: Fo4Land <Fallout4.esm> [--master <master.esm>]... <WorldEditorId> <xmin> <ymin> <xmax> <ymax> <out.json>");
    return 2;
}
try { Fo4LoadOrder.RefuseUnsafeOutput(args[6], masterPaths.Append(args[0])); }
catch (InvalidOperationException ex) { Console.Error.WriteLine(ex.Message); return 2; }
int xmin = int.Parse(args[2]), ymin = int.Parse(args[3]), xmax = int.Parse(args[4]), ymax = int.Parse(args[5]);
bool InRange(int x, int y) => x >= xmin && x <= xmax && y >= ymin && y <= ymax;
static string Fid(Mutagen.Bethesda.Plugins.FormKey k) => k.ID.ToString("X8");

static double[][]? DecodeVhgt(ILandscapeGetter? land, out float? offset)
{
    var vh = land?.VertexHeightMap;
    offset = vh?.Offset;
    if (vh is null) return null;
    var hm = vh.HeightMap;
    var heights = new double[33][];
    int rowStart = 0;
    for (int r = 0; r < 33; r++)
    {
        heights[r] = new double[33];
        rowStart += unchecked((sbyte)hm[0, r]);
        int z = rowStart;
        heights[r][0] = 8.0 * (vh.Offset + z);
        for (int c = 1; c < 33; c++)
        {
            z += unchecked((sbyte)hm[c, r]);
            heights[r][c] = 8.0 * (vh.Offset + z);
        }
    }
    return heights;
}

object RefJson(IPlacedGetter p)
{
    Noggog.P3Float? pos = p switch { IPlacedObjectGetter o => o.Position, IPlacedNpcGetter n => n.Position, _ => null };
    var baseKey = p switch
    {
        IPlacedObjectGetter o => Fid(o.Base.FormKey),
        IPlacedNpcGetter n => Fid(n.Base.FormKey),
        _ => null,
    };
    return new { fid = Fid(p.FormKey), @base = baseKey, pos = pos is { } v ? new[] { v.X, v.Y, v.Z } : null };
}

var cells = new List<object>();
var persistent = new List<object>();
string worldFidStr;

if (masterPaths.Count == 0)
{
    using var mod = Fallout4Mod.CreateFromBinaryOverlay(args[0], Fallout4Release.Fallout4);
    var world = mod.Worldspaces.FirstOrDefault(w => w.EditorID == args[1]);
    if (world is null)
    {
        Console.Error.WriteLine($"worldspace {args[1]} not found");
        return 1;
    }
    worldFidStr = Fid(world.FormKey);
    foreach (var block in world.SubCells)
    foreach (var sub in block.Items)
    foreach (var cell in sub.Items)
    {
        if (cell.Grid is not { } grid || !InRange(grid.Point.X, grid.Point.Y)) continue;
        var heights = DecodeVhgt(cell.Landscape, out var offset);
        cells.Add(new
        {
            x = grid.Point.X,
            y = grid.Point.Y,
            cell = Fid(cell.FormKey),
            land = cell.Landscape is { } l ? Fid(l.FormKey) : null,
            offset,
            heights,
            refs = cell.Temporary.Select(RefJson).ToList(),
        });
    }
    if (world.TopCell is { } top)
    {
        foreach (var p in top.Persistent)
        {
            if (p is IPlacedObjectGetter o && o.Position is var pl &&
                InRange((int)Math.Floor(pl.X / 4096.0), (int)Math.Floor(pl.Y / 4096.0)))
                persistent.Add(RefJson(p));
        }
    }
}
else
{
    using var lo = Fo4LoadOrder.Open(args[0], masterPaths);
    var found = lo.FindWorld(args[1]);
    if (found is null)
    {
        Console.Error.WriteLine($"worldspace {args[1]} not found");
        return 1;
    }
    var (worldKey, _, _, worldCopies) = found.Value;
    worldFidStr = Fid(worldKey);
    var placedKeys = CellMerge.PlacedKeys(lo.Mods);
    var allCopies = CellMerge.Copies(lo.Mods, worldspaces: true);
    var topKeys = worldCopies.Where(w => w.TopCell != null).Select(w => w.TopCell!.FormKey).ToHashSet();

    foreach (var (ck, copies) in allCopies)
    {
        if (copies[^1].Worldspace != worldKey.ToString()) continue;
        if (topKeys.Contains(ck))
        {
            var mergedTop = CellMerge.Merge(copies, placedKeys);
            foreach (var pl in mergedTop.Children)
            {
                if (!pl.Persistent) continue;
                if (pl.Record is IPlacedObjectGetter o && o.Position is var ppos &&
                    InRange((int)Math.Floor(ppos.X / 4096.0), (int)Math.Floor(ppos.Y / 4096.0)))
                    persistent.Add(RefJson(o));
            }
            continue;
        }
        var grid = copies.Select(c => c.Cell.Grid).LastOrDefault(g => g != null);
        if (grid is null || !InRange(grid.Point.X, grid.Point.Y)) continue;
        ILandscapeGetter? winLand = null;
        for (int i = copies.Count - 1; i >= 0; i--)
        {
            if (copies[i].Cell.Landscape is { } l && !l.IsDeleted && l.VertexHeightMap != null) { winLand = l; break; }
        }
        winLand ??= copies.Select(c => c.Cell.Landscape).LastOrDefault(l => l != null && !l.IsDeleted);
        var heights = DecodeVhgt(winLand, out var offset);
        var merged = CellMerge.Merge(copies, placedKeys);
        cells.Add(new
        {
            x = grid.Point.X,
            y = grid.Point.Y,
            cell = Fid(merged.Cell.FormKey),
            land = winLand is { } wl ? Fid(wl.FormKey) : null,
            offset,
            heights,
            refs = merged.Children.Where(c => !c.Persistent).Select(c => RefJson(c.Record)).ToList(),
        });
    }
}

var doc = new { world = args[1], world_fid = worldFidStr, cells, persistent };
File.WriteAllText(args[6], JsonSerializer.Serialize(doc, new JsonSerializerOptions { WriteIndented = false }));
Console.WriteLine($"cells {cells.Count}, persistent refs in range {persistent.Count} -> {args[6]}");
return 0;

