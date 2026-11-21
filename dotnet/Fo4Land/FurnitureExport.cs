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
    public static object Build(IReadOnlyList<IFallout4ModGetter> mods, string pluginLabel)
    {
        var kw = new Dictionary<FormKey, string?>();
        foreach (var m in mods)
            foreach (var k in m.Keywords)
                if (!k.IsDeleted) kw[k.FormKey] = k.EditorID;
        string? Kw(FormKey k) => kw.TryGetValue(k, out var e) ? e : null;

        var winning = new Dictionary<FormKey, IFurnitureGetter>();
        foreach (var m in mods)
        {
            foreach (var f in m.Furniture)
            {
                if (f.IsDeleted) winning.Remove(f.FormKey);
                else winning[f.FormKey] = f;
            }
        }

        var furniture = new SortedDictionary<string, object>(StringComparer.Ordinal);
        foreach (var f in winning.Values)
            furniture[f.FormKey.ToString()] = new
            {
                editor_id = f.EditorID, name = f.Name?.String, model = f.Model?.File?.ToString(),
                bench_type = f.BenchType.ToString(), flags = f.Flags?.ToString(), marker_model = f.MarkerModel,
                keywords = f.Keywords?.Select(k => Kw(k.FormKey) ?? k.FormKey.ToString()).ToArray(),
                entry_points = f.MarkerEntryPoints?.Select(e => new { type = e.Type.ToString(), points = e.Points.ToString() }).ToArray(),
                markers = f.MarkerParameters?.Select(m => new
                {
                    enabled = m.Enabled, offset = new[] { m.Offset.X, m.Offset.Y, m.Offset.Z }, rotation_z = m.RotationZ,
                    keyword = Kw(m.Keyword.FormKey) ?? m.Keyword.FormKey.ToString(), entry_types = m.EntryTypes.ToString(),
                }).ToArray(),
            };
        return new { plugin = pluginLabel, furniture };
    }

    public static object Build(IFallout4ModGetter mod) => Build(new[] { mod }, mod.ModKey.FileName.String);

    public static int Run(string[] args, IReadOnlyList<string>? masterPaths = null)
    {
        masterPaths ??= Array.Empty<string>();
        if (args.Length < 3)
        {
            Console.Error.WriteLine("usage: Fo4Land <Fallout4.esm> [--master <master.esm>]... export-furniture <out.json> [<extra.esm>...]");
            return 2;
        }
        var extraPlugins = args.Skip(3).ToList();
        var outPath = args[2];
        var allMasters = masterPaths.ToList();
        string activePath = args[0];
        if (extraPlugins.Count > 0)
        {
            allMasters.Add(activePath);
            allMasters.AddRange(extraPlugins.Take(extraPlugins.Count - 1));
            activePath = extraPlugins[^1];
        }
        try { Fo4LoadOrder.RefuseUnsafeOutput(outPath, allMasters.Append(activePath)); }
        catch (InvalidOperationException ex) { Console.Error.WriteLine(ex.Message); return 2; }

        if (allMasters.Count == 0)
        {
            using var mod = Fallout4Mod.CreateFromBinaryOverlay(activePath, Fallout4Release.Fallout4);
            var doc = Build(mod);
            File.WriteAllText(outPath, JsonSerializer.Serialize(doc, new JsonSerializerOptions { WriteIndented = true }));
            Console.WriteLine($"wrote {outPath}: {mod.Furniture.Count} furniture bases");
            return 0;
        }
        using var lo = Fo4LoadOrder.Open(activePath, allMasters);
        var label = string.Join(",", lo.Mods.Select(m => m.ModKey.FileName.String));
        var mergedDoc = Build(lo.Mods, label);
        File.WriteAllText(outPath, JsonSerializer.Serialize(mergedDoc, new JsonSerializerOptions { WriteIndented = true }));
        var count = JsonDocument.Parse(File.ReadAllText(outPath)).RootElement.GetProperty("furniture").EnumerateObject().Count();
        Console.WriteLine($"wrote {outPath}: {count} furniture bases across {lo.Mods.Count} plugins");
        return 0;
    }
}
