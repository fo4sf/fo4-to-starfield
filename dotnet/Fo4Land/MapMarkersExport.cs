// Fo4Land export-mapmarkers: every map marker of one Fallout 4 worldspace, for the core's Commonwealth map markers
// (docs/terrain/map-markers.md "Every Commonwealth marker"; src/fo4sf/map_markers.py load_fo4_markers).
//
//   dotnet run --project dotnet/Fo4Land -c Release -- <Fallout4.esm> export-mapmarkers <out.json> [<WorldEditorId>]
//
// {"plugin", "world", "markers": [{"fid", "editor_id", "base", "name", "type", "type_id", "pos": [x, y, z], "persistent"}]}: every placed
// object of the world (persistent and temporary) that carries map-marker data (XMRK and its FULL), FO4 units, sorted
// by FormID. "name" is the marker's own FULL: Fallout4.esm is localized, and Mutagen reads it from the Strings files
// in the archives next to the plugin (as export-names). The world defaults to Commonwealth. The output stays outside
// the repository (derived game data). "type" / "type_id" are the marker's TNAM type as Mutagen's Fallout 4 enum
// (Vault = 15, MetroStation = 6, ...), for a later FO4-to-Starfield icon table (docs/terrain/map-markers.md).
using System.Text.Json;
using Mutagen.Bethesda;
using Mutagen.Bethesda.Fallout4;
using Mutagen.Bethesda.Plugins;

public static class MapMarkersExport
{
    public static object Build(IFallout4ModGetter mod, string worldEdid)
    {
        var world = mod.Worldspaces.FirstOrDefault(w => w.EditorID == worldEdid)
                    ?? throw new ArgumentException($"worldspace {worldEdid} not found");
        var markers = new List<(uint Id, object Row)>();
        foreach (var ctx in world.EnumerateMajorRecords<IPlacedObjectGetter>())
        {
            if (ctx.MapMarker == null) continue;
            markers.Add((ctx.FormKey.ID, new
            {
                fid = ctx.FormKey.ID.ToString("X8"), editor_id = ctx.EditorID, @base = ctx.Base.FormKey.ID.ToString("X8"),
                name = string.IsNullOrEmpty(ctx.MapMarker.Name?.String) ? null : ctx.MapMarker.Name!.String,
                type = ctx.MapMarker.Type.ToString(), type_id = (int)ctx.MapMarker.Type,
                pos = new[] { ctx.Position.X, ctx.Position.Y, ctx.Position.Z },
                persistent = (ctx.MajorRecordFlagsRaw & 0x400) != 0,
            }));
        }
        return new { plugin = mod.ModKey.FileName.String, world = worldEdid, markers = markers.OrderBy(m => m.Id).Select(m => m.Row).ToArray() };
    }

    public static object BuildLoadOrder(Fo4LoadOrder lo, string worldEdid)
    {
        var found = lo.FindWorld(worldEdid)
                    ?? throw new ArgumentException($"worldspace {worldEdid} not found");
        var (worldKey, _, resolvedEdid, _) = found;
        var worldKeyStr = worldKey.ToString();
        var placedKeys = CellMerge.PlacedKeys(lo.Mods);
        var allCopies = CellMerge.Copies(lo.Mods, worldspaces: true);
        var markers = new List<((string ModName, uint Id) SortKey, object Row)>();
        foreach (var (_, copies) in allCopies)
        {
            if (copies[^1].Worldspace != worldKeyStr) continue;
            var merged = CellMerge.Merge(copies, placedKeys);
            foreach (var ch in merged.Children)
            {
                if (ch.Record is not IPlacedObjectGetter ctx || ctx.MapMarker == null) continue;
                markers.Add(((ctx.FormKey.ModKey.FileName.String, ctx.FormKey.ID), new
                {
                    fid = ctx.FormKey.ID.ToString("X8"), formkey = ctx.FormKey.ToString(),
                    editor_id = ctx.EditorID, @base = ctx.Base.FormKey.ID.ToString("X8"),
                    base_formkey = ctx.Base.FormKey.ToString(),
                    name = string.IsNullOrEmpty(ctx.MapMarker.Name?.String) ? null : ctx.MapMarker.Name!.String,
                    type = ctx.MapMarker.Type.ToString(), type_id = (int)ctx.MapMarker.Type,
                    pos = new[] { ctx.Position.X, ctx.Position.Y, ctx.Position.Z },
                    persistent = ch.Persistent || (ctx.MajorRecordFlagsRaw & 0x400) != 0,
                }));
            }
        }
        return new
        {
            plugin = lo.ActiveMod.ModKey.FileName.String,
            masters = lo.Mods.Take(lo.Mods.Count - 1).Select(m => m.ModKey.FileName.String).ToArray(),
            world = resolvedEdid,
            markers = markers.OrderBy(m => m.SortKey.Id).ThenBy(m => m.SortKey.ModName, StringComparer.OrdinalIgnoreCase).Select(m => m.Row).ToArray(),
        };
    }

    public static int Run(string[] args, IReadOnlyList<string>? masterPaths = null)
    {
        masterPaths ??= Array.Empty<string>();
        if (args.Length is < 3 or > 4)
        {
            Console.Error.WriteLine("usage: Fo4Land <Fallout4.esm> [--master <master.esm>]... export-mapmarkers <out.json> [<WorldEditorId>]");
            return 2;
        }
        try { Fo4LoadOrder.RefuseUnsafeOutput(args[2], masterPaths.Append(args[0])); }
        catch (InvalidOperationException ex) { Console.Error.WriteLine(ex.Message); return 2; }
        var worldEdid = args.Length == 4 ? args[3] : "Commonwealth";
        object doc;
        if (masterPaths.Count == 0)
        {
            using var mod = Fallout4Mod.CreateFromBinaryOverlay(args[0], Fallout4Release.Fallout4);
            try { doc = Build(mod, worldEdid); }
            catch (ArgumentException e) { Console.Error.WriteLine(e.Message); return 1; }
        }
        else
        {
            using var lo = Fo4LoadOrder.Open(args[0], masterPaths);
            try { doc = BuildLoadOrder(lo, worldEdid); }
            catch (ArgumentException e) { Console.Error.WriteLine(e.Message); return 1; }
        }
        File.WriteAllText(args[2], JsonSerializer.Serialize(doc, new JsonSerializerOptions { WriteIndented = true }));
        var rows = JsonDocument.Parse(File.ReadAllText(args[2])).RootElement.GetProperty("markers");
        int n = rows.GetArrayLength(), named = rows.EnumerateArray().Count(r => r.GetProperty("name").ValueKind == JsonValueKind.String);
        Console.WriteLine($"wrote {args[2]}: {n:N0} map markers in {worldEdid}, {named:N0} with a name");
        return 0;
    }
}
