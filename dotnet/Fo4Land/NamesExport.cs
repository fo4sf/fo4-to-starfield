// Fo4Land export-names: the display names (FULL) of Fallout 4 base records, for scripts/terrain/make_cluster.py --names
// (the promoted classes' names: activators, terminals, containers, loose items).
//
//   dotnet run --project dotnet/Fo4Land -c Release -- <Fallout4.esm> export-names <out.json>
//
// {"plugin": "Fallout4.esm", "types": [...], "names": {"<base formkey>": {"type", "editor_id", "name"}}}: every
// Activator, Terminal, Container, MiscItem and Ingestible of the plugin, "name" null when the record has no FULL (in
// Fallout 4 such an activator shows no activation prompt). Fallout4.esm is localized: Mutagen reads its FULL strings
// from the Strings files in the archives next to the plugin (verified on the 1.10.163 depot: MirelurkEgg_Harvestable
// -> "Mirelurk Egg", DefaultTerminalWall -> "Terminal"). Keys are sorted, so the same plugin gives the same bytes.
// The output stays outside the repository (it is derived game data).
using System.Text.Json;
using Mutagen.Bethesda.Fallout4;
using Mutagen.Bethesda.Plugins.Records;

public static class NamesExport
{
    public static readonly string[] Types = { "Activator", "Terminal", "Container", "MiscItem", "Ingestible" };

    static IEnumerable<(string Type, IMajorRecordGetter Record, string? Name)> Named(IFallout4ModGetter mod)
    {
        foreach (var r in mod.Activators) yield return ("Activator", r, r.Name?.String);
        foreach (var r in mod.Terminals) yield return ("Terminal", r, r.Name?.String);
        foreach (var r in mod.Containers) yield return ("Container", r, r.Name?.String);
        foreach (var r in mod.MiscItems) yield return ("MiscItem", r, r.Name?.String);
        foreach (var r in mod.Ingestibles) yield return ("Ingestible", r, r.Name?.String);
    }

    public static object Build(IFallout4ModGetter mod)
    {
        var names = new SortedDictionary<string, object>(StringComparer.Ordinal);
        foreach (var (type, rec, name) in Named(mod))
            names[rec.FormKey.ToString()] = new { type, editor_id = rec.EditorID, name = string.IsNullOrEmpty(name) ? null : name };
        return new { plugin = mod.ModKey.FileName.String, types = Types, names };
    }

    public static int Run(string[] args)
    {
        if (args.Length != 3)
        {
            Console.Error.WriteLine("usage: Fo4Land <Fallout4.esm> export-names <out.json>");
            return 2;
        }
        using var mod = Fallout4Mod.CreateFromBinaryOverlay(args[0], Fallout4Release.Fallout4);
        var doc = Build(mod);
        File.WriteAllText(args[2], JsonSerializer.Serialize(doc, new JsonSerializerOptions { WriteIndented = true }));
        var json = JsonDocument.Parse(File.ReadAllText(args[2])).RootElement.GetProperty("names");
        int n = 0, named = 0;
        foreach (var e in json.EnumerateObject())
        {
            n++;
            if (e.Value.GetProperty("name").ValueKind == JsonValueKind.String) named++;
        }
        Console.WriteLine($"wrote {args[2]}: {n:N0} base records ({string.Join(", ", Types)}), {named:N0} with a name");
        return 0;
    }
}
