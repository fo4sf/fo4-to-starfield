// Fo4Land export-furniture: every Fallout 4 Furniture base with its sit / lean / lie markers, for the interior furniture
// promotion (docs/terrain/port-promotions.md, "Furniture"). Starfield's FURN carries the same marker block (Mutagen 0.55:
// MarkerParameters Offset / RotationZ / Keyword / EntryTypes, MarkerEntryPoints, MarkerModel), so a chair can keep FO4's
// own marker places; this lists what FO4 has so the mapping is chosen from evidence, not guessed.
//
//   dotnet run --project dotnet/Fo4Land -c Release -- <Fallout4.esm> export-furniture <out.json>
//
// {"plugin", "furniture": {"<base formkey>": {"editor_id", "name", "model", "bench_type", "flags", "marker_model",
// "keywords": [edid], "entry_points": [{"type", "points"}], "markers": [{"enabled", "offset", "rotation_z", "keyword",
// "entry_types"}]}}}: keyword edids resolved inside the plugin (null when the keyword lives elsewhere). Keys sorted.
// The output stays outside the repository (derived game data).
using System.Text.Json;
using Mutagen.Bethesda.Fallout4;
using Mutagen.Bethesda.Plugins;

public static class FurnitureExport
{
    public static object Build(IFallout4ModGetter mod)
    {
        var kw = mod.Keywords.ToDictionary(k => k.FormKey, k => k.EditorID);
        string? Kw(FormKey k) => kw.TryGetValue(k, out var e) ? e : null;
        var furniture = new SortedDictionary<string, object>(StringComparer.Ordinal);
        foreach (var f in mod.Furniture)
            furniture[f.FormKey.ToString()] = new
            {
                editor_id = f.EditorID, name = f.Name?.String, model = f.Model?.File.ToString(),
                bench_type = f.BenchType.ToString(), flags = f.Flags?.ToString(), marker_model = f.MarkerModel,
                keywords = f.Keywords?.Select(k => Kw(k.FormKey) ?? k.FormKey.ToString()).ToArray(),
                entry_points = f.MarkerEntryPoints?.Select(e => new { type = e.Type.ToString(), points = e.Points.ToString() }).ToArray(),
                markers = f.MarkerParameters?.Select(m => new
                {
                    enabled = m.Enabled, offset = new[] { m.Offset.X, m.Offset.Y, m.Offset.Z }, rotation_z = m.RotationZ,
                    keyword = Kw(m.Keyword.FormKey) ?? m.Keyword.FormKey.ToString(), entry_types = m.EntryTypes.ToString(),
                }).ToArray(),
            };
        return new { plugin = mod.ModKey.FileName.String, furniture };
    }

    public static int Run(string[] args)
    {
        if (args.Length != 3)
        {
            Console.Error.WriteLine("usage: Fo4Land <Fallout4.esm> export-furniture <out.json>");
            return 2;
        }
        using var mod = Fallout4Mod.CreateFromBinaryOverlay(args[0], Fallout4Release.Fallout4);
        var doc = Build(mod);
        File.WriteAllText(args[2], JsonSerializer.Serialize(doc, new JsonSerializerOptions { WriteIndented = true }));
        Console.WriteLine($"wrote {args[2]}: {mod.Furniture.Count} furniture bases");
        return 0;
    }
}
