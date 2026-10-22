// Export Fallout 4 interior-cell placements to JSON (input for the cell converter).
//   dotnet run -- <plugin.esm> [--master <Fallout4.esm>]... list <substring>   list interior cells whose EditorID contains <substring>
//   dotnet run -- <plugin.esm> [--master <Fallout4.esm>]... export <EditorID> <out.json>
//   dotnet run -- <plugin.esm> [--master <Fallout4.esm>]... locations <out.json> <EditorID>...
// export writes one cell's placements (schema 3: cell_data, location and encounter_zone sit beside the refs, see
// LocationExport.cs and docs/CELL-EXPORT.md); locations writes only those three keys for several cells at once,
// {"schema_version": 1, "cells": {<EditorID>: {...}}}, the sidecar interior_batch.py keeps for cells whose pinned exports
// predate schema 3. A cell named in locations mode that is not an interior of the load order fails the run.
// Each reference: base record type + EditorID + model path, position (game units), rotation (radians), scale.
// --master (repeatable, in load order) loads the plugins before <plugin.esm>: the load order is the masters in the order
// given, then the plugin. A cell is exported as the game sees it over that load order (CellMerge.cs): the winning CELL
// record (the last plugin that holds it: its name, flags, location, encounter zone, lighting) with its children merged
// across every plugin that holds the cell, each reference from its winning copy, a reference a later plugin deletes
// (record flag 0x20) or moves to another cell left out. So a DLC's own cell needs --master Fallout4.esm for its bases and
// its Commonwealth doors, and a Fallout4.esm cell a DLC overrides (GeneralAtomicsFactory01, Automatron) is exported as
// `<DLCRobot.esm> --master <Fallout4.esm> export GeneralAtomicsFactory01`; with one plugin nothing changes.
using System.Text.Json;
using Mutagen.Bethesda;
using Mutagen.Bethesda.Fallout4;
using Mutagen.Bethesda.Plugins;
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
var loadOrder = masters.Append((IFallout4ModGetter)mod).ToList();
ILinkCache cache = loadOrder.ToImmutableLinkCache();
// the placed FormKeys each later plugin holds (the first is never scanned), so a reference a DLC moved out of a cell is
// not exported from the master's copy; computed once, before any merge
var placedKeys = CellMerge.PlacedKeys(loadOrder);
var interiorCopies = CellMerge.Copies(loadOrder, worldspaces: false);

// the interior cells of the load order: each cell's copies with the editor id the last copy that carries one gives it
// (an override written without EDID does not unname the cell)
IEnumerable<(string? EditorID, List<CellMerge.Copy> Copies)> InteriorCells() =>
    interiorCopies.Values.Select(c => (CellMerge.EditorIdOf(c), c));

if (args[1] == "list")
{
    foreach (var (editorId, copies) in InteriorCells().Where(c => (c.EditorID ?? "").Contains(args[2], StringComparison.OrdinalIgnoreCase)))
        Console.WriteLine($"{editorId}  {copies[0].Cell.FormKey}  refs={CellMerge.Merge(copies, placedKeys).Children.Count}");
    return;
}

// the cell named, merged over the load order (winning record, merged children); null when no plugin's interior
// group holds a cell of that editor id
CellMerge.Merged? FindCell(string editorId)
{
    var hit = InteriorCells().FirstOrDefault(c => string.Equals(c.EditorID, editorId, StringComparison.OrdinalIgnoreCase));
    return hit.Copies == null ? null : CellMerge.Merge(hit.Copies, placedKeys);
}

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
        cells[c.EditorID!] = LocationExport.Build(c.Cell, cache);
    }
    File.WriteAllText(args[2], JsonSerializer.Serialize(new { schema_version = 1, cells }, new JsonSerializerOptions { WriteIndented = true }));
    Console.WriteLine($"{cells.Count} cells' location data -> {args[2]}");
    return;
}

var merged = FindCell(args[2]) ?? throw new InvalidOperationException($"no interior cell '{args[2]}' in {Path.GetFileName(args[0])}");
var cell = merged.Cell;
var refs = new List<object>();
var deferred = new List<object>();
var keywords = new Dictionary<string, object>();
var byType = new Dictionary<string, int>();
var doorBases = new Dictionary<string, object?>();   // every placed Door base: its record and scripts (door-behaviour.md)
foreach (var (placed, persistent, _) in merged.Children)
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
        deferred.Add(ReferenceExport.BuildActor(npc, persistent));
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
    refs.Add(ReferenceExport.Build(r, type, baseEid, model, persistent));
}
// every cell of the load order (worldspaces too), merged the same way, so a destination door a DLC deleted or moved
// resolves where the game would look for it
var dependencies = TeleportDependencies.Build(merged.Records.OfType<IPlacedObjectGetter>(), CellMerge.All(loadOrder, placedKeys, worldspaces: true));
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
File.WriteAllText(args[3], JsonSerializer.Serialize(new { schema_version = 3, cell = merged.EditorID, formkey = cell.FormKey.ToString(),
    cell_data = LocationExport.CellData(cell, cache), location = LocationExport.Location(cell.Location, cache),
    encounter_zone = LocationExport.EncounterZone(cell.EncounterZone, cache), lighting, refs,
    deferred_refs = deferred, door_bases = doorBases, referenced_keywords = keywords.Values, teleport_dependencies = dependencies },
    new JsonSerializerOptions { WriteIndented = true }));
Console.WriteLine($"{merged.EditorID}: {refs.Count} references -> {args[3]}");
Console.WriteLine($"{deferred.Count} deferred placements retained for future translators");
foreach (var kv in byType.OrderByDescending(k => k.Value)) Console.WriteLine($"  {kv.Key}: {kv.Value}");
