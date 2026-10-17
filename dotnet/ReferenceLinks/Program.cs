using System.Text.Json;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;

if (args.Length < 4)
{
    Console.Error.WriteLine("usage: <input.esm> <formids.json> <output dir> <cell.json...> [--report-only] [--allow-unresolved] [--strict-activation-parents] [--door-bases=map.json]");
    Environment.ExitCode = 1;
    return;
}
var mod = PluginReader.Read(args[0]);
var output = Path.Combine(args[2], mod.ModKey.FileName);
if (Path.GetFullPath(output).Equals(Path.GetFullPath(args[0]), StringComparison.OrdinalIgnoreCase))
    throw new InvalidOperationException("output must be separate from the input plugin");
if (File.Exists(output)) throw new InvalidOperationException("output plugin already exists; use a fresh output directory");
var ids = JsonSerializer.Deserialize<Dictionary<string, uint>>(File.ReadAllText(args[1]))!;
var exports = args.Skip(3).Where(p => !p.StartsWith("--")).Select(p => JsonDocument.Parse(File.ReadAllText(p))).ToArray();
try
{
    var data = Environment.GetEnvironmentVariable("STARFIELD_DATA");
    // Keep typed native records alive through relationship resolution. --no-markers
    // suppresses marker creation, not proof of a native DOOR's record type.
    using var vanilla = data == null ? null : StarfieldMod.CreateFromBinaryOverlay(
        Path.Combine(data, "Starfield.esm"), StarfieldRelease.Starfield);
    Dictionary<string, FormKey>? markerBases = null;
    if (vanilla != null && !args.Contains("--no-markers"))
    {
        var names = new HashSet<string>(new[] { "EnableMarker", "XMarker", "XMarkerHeading", "LightBox" }, StringComparer.OrdinalIgnoreCase);
        markerBases = vanilla.Statics.Where(s => s.EditorID != null && names.Contains(s.EditorID))
            .ToDictionary(s => s.EditorID!, s => s.FormKey, StringComparer.OrdinalIgnoreCase);
    }
    Dictionary<string, FormKey>? doorSelections = null;
    var doorOptions = args.Where(a => a.StartsWith("--door-bases=", StringComparison.Ordinal)).ToArray();
    if (doorOptions.Length > 1) throw new InvalidOperationException("duplicate --door-bases option");
    if (doorOptions.Length == 1)
    {
        using var selections = JsonDocument.Parse(File.ReadAllText(doorOptions[0]["--door-bases=".Length..]));
        doorSelections = new Dictionary<string, FormKey>(StringComparer.OrdinalIgnoreCase);
        foreach (var entry in selections.RootElement.EnumerateObject())
            if (!doorSelections.TryAdd(entry.Name, FormKey.Factory(entry.Value.GetString()!)))
                throw new InvalidOperationException("duplicate door source selection: " + entry.Name);
    }
    var report = Relationships.Apply(mod, ids, exports.Select(x => x.RootElement), markerBases, vanilla, doorSelections);
    var unresolved = report.Issues.Count + report.Warnings.Count;
    var blocking = report.Issues.Count + (args.Contains("--strict-activation-parents") ? report.Warnings.Count : 0);
    Directory.CreateDirectory(args[2]);
    var statePath = Path.Combine(args[2], "build-state.json");
    File.WriteAllText(statePath, JsonSerializer.Serialize(new { complete = false, status = "relationship_translation", unresolved, warnings = report.Warnings.Count, blocking }));
    File.WriteAllText(Path.Combine(args[2], "relationships-report.json"), JsonSerializer.Serialize(report, new JsonSerializerOptions { WriteIndented = true }));
    Console.WriteLine($"markers={report.CreatedMarkers}, keywords={report.CreatedKeywords}, persistent={report.Persistent}, enable parents={report.EnableParents}, linked refs={report.LinkedReferences}, teleports={report.Teleports}, issues={report.Issues.Count}, warnings={report.Warnings.Count}");
    foreach (var warning in report.Warnings)
        Console.Error.WriteLine($"warning: {warning.Source} {warning.Field}: {warning.Reason}");
    if (blocking > 0 && !args.Contains("--allow-unresolved")) { Environment.ExitCode = 2; return; }
    if (args.Contains("--report-only")) return;
    if (data == null) throw new InvalidOperationException("set STARFIELD_DATA");
    mod.BeginWrite.ToPath(output).WithLoadOrderFromHeaderMasters().WithDataFolder(data)
        .WithKnownMasters(new KeyedMasterStyle(ModKey.FromNameAndExtension("Starfield.esm"), MasterStyle.Full)).Write();
    File.WriteAllText(Path.Combine(args[2], "formids.json"), JsonSerializer.Serialize(ids, new JsonSerializerOptions { WriteIndented = true }));
    File.WriteAllText(statePath, JsonSerializer.Serialize(new { complete = true, status = "relationships_written", unresolved, warnings = report.Warnings.Count, blocking,
        fidelity = blocking > 0 ? "partial_explicitly_allowed" : report.Warnings.Count > 0 ? "partial_with_warnings" : "resolved_exported_relationships" }));
    Console.WriteLine($"wrote {output}; input was unchanged");
}
finally { foreach (var export in exports) export.Dispose(); }
