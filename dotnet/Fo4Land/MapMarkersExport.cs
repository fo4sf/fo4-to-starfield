// Fo4Land export-mapmarkers: every map marker of one Fallout 4 worldspace, for the core's Commonwealth map markers
// (docs/terrain/map-markers.md "Every Commonwealth marker"; src/fo4sf/map_markers.py load_fo4_markers).
//
//   dotnet run --project dotnet/Fo4Land -c Release -- <Fallout4.esm> export-mapmarkers <out.json> [<WorldEditorId>]
//
// {"plugin", "world", "markers": [{"fid", "editor_id", "base", "name", "pos": [x, y, z], "persistent"}]}: every placed
// object of the world (persistent and temporary) that carries map-marker data (XMRK and its FULL), FO4 units, sorted
// by FormID. "name" is the marker's own FULL: Fallout4.esm is localized, and Mutagen reads it from the Strings files
// in the archives next to the plugin (as export-names). The world defaults to Commonwealth. The output stays outside
// the repository (derived game data).
using System.Text.Json;
using Mutagen.Bethesda;
using Mutagen.Bethesda.Fallout4;

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
                pos = new[] { ctx.Position.X, ctx.Position.Y, ctx.Position.Z },
                persistent = (ctx.MajorRecordFlagsRaw & 0x400) != 0,
            }));
        }
        return new { plugin = mod.ModKey.FileName.String, world = worldEdid, markers = markers.OrderBy(m => m.Id).Select(m => m.Row).ToArray() };
    }

    public static int Run(string[] args)
    {
        if (args.Length is < 3 or > 4)
        {
            Console.Error.WriteLine("usage: Fo4Land <Fallout4.esm> export-mapmarkers <out.json> [<WorldEditorId>]");
            return 2;
        }
        using var mod = Fallout4Mod.CreateFromBinaryOverlay(args[0], Fallout4Release.Fallout4);
        var worldEdid = args.Length == 4 ? args[3] : "Commonwealth";
        object doc;
        try { doc = Build(mod, worldEdid); }
        catch (ArgumentException e) { Console.Error.WriteLine(e.Message); return 1; }
        File.WriteAllText(args[2], JsonSerializer.Serialize(doc, new JsonSerializerOptions { WriteIndented = true }));
        var rows = JsonDocument.Parse(File.ReadAllText(args[2])).RootElement.GetProperty("markers");
        int n = rows.GetArrayLength(), named = rows.EnumerateArray().Count(r => r.GetProperty("name").ValueKind == JsonValueKind.String);
        Console.WriteLine($"wrote {args[2]}: {n:N0} map markers in {worldEdid}, {named:N0} with a name");
        return 0;
    }
}
