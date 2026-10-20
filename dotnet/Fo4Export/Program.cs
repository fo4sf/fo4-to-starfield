// Export Fallout 4 interior-cell placements to JSON (input for the cell converter).
//   dotnet run -- <plugin.esm> [--master <Fallout4.esm>]... list <substring>   list interior cells whose EditorID contains <substring>
//   dotnet run -- <plugin.esm> [--master <Fallout4.esm>]... export <EditorID> <out.json>
//   dotnet run -- <plugin.esm> [--master <Fallout4.esm>]... locations <out.json> <EditorID>...
// export writes one cell's placements (schema 3: cell_data, location and encounter_zone sit beside the refs, see
// LocationExport.cs and docs/CELL-EXPORT.md); locations writes only those three keys for several cells at once,
// {"schema_version": 1, "cells": {<EditorID>: {...}}}, the sidecar interior_batch.py keeps for cells whose pinned exports
// predate schema 3. A cell named in locations mode that is not an interior of the plugin fails the run.
// Each reference: base record type + EditorID + model path, position (game units), rotation (radians), scale.
// --master (repeatable, in load order) loads the plugin's masters too, so a DLC plugin's cells resolve the base records
// and the Commonwealth doors that live in Fallout4.esm; the cells listed and exported are still the plugin's own.
using System.Text.Json;
using Mutagen.Bethesda;
using Mutagen.Bethesda.Fallout4;
using Mutagen.Bethesda.Plugins.Cache;
using Mutagen.Bethesda.Plugins.Records;

var masterPaths = new List<string>();
var rest = new List<string>();
for (var i = 0; i < args.Length; i++)
{
    if (args[i] == "--master" && i + 1 < args.Length) masterPaths.Add(args[++i]);
    else rest.Add(args[i]);
}
args = rest.ToArray();
if (args.Length < 3 || args[1] is not ("list" or "export" or "locations") || (args[1] != "list" && args.Length < 4))
{
    Console.Error.WriteLine("usage: <plugin.esm> [--master <master.esm>]... list <substr> | export <EditorID> <out.json> | locations <out.json> <EditorID>...");
    Environment.ExitCode = 1;
    return;
}
var masters = masterPaths.Select(p => (IFallout4ModGetter)Fallout4Mod.CreateFromBinaryOverlay(p, Fallout4Release.Fallout4)).ToList();
using var mod = Fallout4Mod.CreateFromBinaryOverlay(args[0], Fallout4Release.Fallout4);
ILinkCache cache = masters.Count == 0 ? mod.ToImmutableLinkCache() : masters.Append(mod).ToImmutableLinkCache();

IEnumerable<ICellGetter> InteriorCells() =>
    mod.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(sb => sb.Cells);

IEnumerable<(ICellGetter Cell, string? Worldspace)> AllCells()
{
    // the plugin first, then its masters last to first: TeleportDependencies keeps the first hit, the winning record
    foreach (var m in new[] { (IFallout4ModGetter)mod }.Concat(Enumerable.Reverse(masters)))
    {
        foreach (var c in m.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(sb => sb.Cells)) yield return (c, null);
        foreach (var world in m.Worldspaces)
        {
            if (world.TopCell != null) yield return (world.TopCell, world.FormKey.ToString());
            foreach (var c in world.SubCells.SelectMany(b => b.Items).SelectMany(b => b.Items))
                yield return (c, world.FormKey.ToString());
        }
    }
}

if (args[1] == "list")
{
    foreach (var c in InteriorCells().Where(c => (c.EditorID ?? "").Contains(args[2], StringComparison.OrdinalIgnoreCase)))
        Console.WriteLine($"{c.EditorID}  {c.FormKey}  refs={c.Temporary.Count + c.Persistent.Count}");
    return;
}

ICellGetter? FindCell(string editorId) =>
    InteriorCells().FirstOrDefault(c => string.Equals(c.EditorID, editorId, StringComparison.OrdinalIgnoreCase));

if (args[1] == "locations")
{
    var cells = new SortedDictionary<string, object>(StringComparer.Ordinal);
    foreach (var editorId in args.Skip(3))
    {
        var c = FindCell(editorId);
        if (c == null)
        {
            Console.Error.WriteLine($"locations: no interior cell '{editorId}' in {Path.GetFileName(args[0])}");
            Environment.ExitCode = 1;
            return;
        }
        cells[c.EditorID!] = LocationExport.Build(c, cache);
    }
    File.WriteAllText(args[2], JsonSerializer.Serialize(new { schema_version = 1, cells }, new JsonSerializerOptions { WriteIndented = true }));
    Console.WriteLine($"{cells.Count} cells' location data -> {args[2]}");
    return;
}

var cell = FindCell(args[2]) ?? throw new InvalidOperationException($"no interior cell '{args[2]}' in {Path.GetFileName(args[0])}");
var refs = new List<object>();
var deferred = new List<object>();
var keywords = new Dictionary<string, object>();
var byType = new Dictionary<string, int>();
var doorBases = new Dictionary<string, object?>();   // every placed Door base: its record and scripts (door-behaviour.md)
var persistentKeys = cell.Persistent.Select(r => r.FormKey).ToHashSet();
foreach (var placed in cell.Temporary.Concat(cell.Persistent))
{
    IEnumerable<ILinkedReferencesGetter> linked = placed switch
    {
        IPlacedObjectGetter obj => obj.LinkedReferences,
        IPlacedNpcGetter actor => actor.LinkedReferences,
        _ => Array.Empty<ILinkedReferencesGetter>(),
    };
    foreach (var link in linked)
        if (link.KeywordOrReference.TryResolve(cache, out var union) && union is IKeywordGetter keyword)
            keywords.TryAdd(keyword.FormKey.ToString(), KeywordExport.Build(keyword));
    if (placed is IPlacedNpcGetter npc)
    {
        deferred.Add(ReferenceExport.BuildActor(npc, persistentKeys.Contains(npc.FormKey)));
        continue;
    }
    if (placed is not IPlacedObjectGetter r)
    {
        deferred.Add(new { formkey = placed.FormKey.ToString(), type = placed.GetType().Name.Replace("BinaryOverlay", ""),
            reason = "placement_type_not_implemented" });
        continue;
    }
    string type = "?", baseEid = "", model = "";
    if (r.Base.TryResolve(cache, out var baseRec))
    {
        type = baseRec.GetType().Name.Replace("BinaryOverlay", "");
        baseEid = baseRec.EditorID ?? "";
        if (baseRec is IModeledGetter m && m.Model?.File != null) model = m.Model.File.ToString();
        if (baseRec is IDoorGetter && !doorBases.ContainsKey(baseRec.FormKey.ToString()))
            doorBases[baseRec.FormKey.ToString()] = new { editor_id = baseEid, model, record = Dump(baseRec, 0),
                                                          scripts = ScriptExport.Scripts(baseRec) };
    }
    byType[type] = byType.GetValueOrDefault(type) + 1;
    refs.Add(ReferenceExport.Build(r, type, baseEid, model, persistentKeys.Contains(r.FormKey)));
}
var dependencies = TeleportDependencies.Build(cell.Temporary.Concat(cell.Persistent).OfType<IPlacedObjectGetter>(), AllCells());
// the cell's own lighting (XCLL: ambient, directional, directional-ambient and fog colours) and its lighting template's,
// read by reflection so the dump follows whatever Mutagen exposes; the writer does not consume it yet (research log 2026-10-18)
object? Dump(object? o, int depth)
{
    if (o == null) return null;
    if (o is System.Drawing.Color col) return new int[] { col.R, col.G, col.B };
    var t = o.GetType();
    if (t.IsPrimitive || t.IsEnum || o is string || o is decimal || o is Type) return o.ToString();
    if (depth >= 3 || o is System.Collections.IEnumerable) return o.ToString();
    var d = new SortedDictionary<string, object?>();
    foreach (var p in t.GetProperties())
    {
        if (p.GetIndexParameters().Length > 0 || p.Name is "Registration" or "StaticRegistration") continue;
        object? v;
        try { v = p.GetValue(o); } catch { continue; }
        d[p.Name] = Dump(v, depth + 1);
    }
    return d;
}
var lighting = new Dictionary<string, object?> { ["cell"] = Dump(cell.Lighting, 0), ["template"] = cell.LightingTemplate.FormKey.ToString() };
if (cell.LightingTemplate.TryResolve(cache, out var lgtm))
{
    lighting["template_editor_id"] = lgtm.EditorID;
    lighting["template_values"] = Dump(lgtm, 0);
}
File.WriteAllText(args[3], JsonSerializer.Serialize(new { schema_version = 3, cell = cell.EditorID, formkey = cell.FormKey.ToString(),
    cell_data = LocationExport.CellData(cell), location = LocationExport.Location(cell.Location, cache),
    encounter_zone = LocationExport.EncounterZone(cell.EncounterZone, cache), lighting, refs,
    deferred_refs = deferred, door_bases = doorBases, referenced_keywords = keywords.Values, teleport_dependencies = dependencies },
    new JsonSerializerOptions { WriteIndented = true }));
Console.WriteLine($"{cell.EditorID}: {refs.Count} references -> {args[3]}");
Console.WriteLine($"{deferred.Count} deferred placements retained for future translators");
foreach (var kv in byType.OrderByDescending(k => k.Value)) Console.WriteLine($"  {kv.Key}: {kv.Value}");
