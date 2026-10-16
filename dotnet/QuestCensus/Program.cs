// Read-only static dependency census. No strings/dialogue/PEX/assets are exported.
using System.Reflection;
using System.Security.Cryptography;
using System.Text.Json;
using Mutagen.Bethesda;
using Mutagen.Bethesda.Fallout4;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Records;

if (args.Length != 3) throw new ArgumentException("usage: <Fallout4.esm> <selection.json> <new-report.json>");
string source = Path.GetFullPath(args[0]), selectionPath = Path.GetFullPath(args[1]), destination = Path.GetFullPath(args[2]);
if (File.Exists(destination) || Directory.Exists(destination)) throw new IOException("report already exists; preserve it and choose a new path");
var inputPins = new Dictionary<string, string>();
string Hash(string path)
{
    using var file = File.OpenRead(path);
    return Convert.ToHexString(SHA256.HashData(file)).ToLowerInvariant();
}
byte[] ReadPinned(string path)
{
    var bytes = File.ReadAllBytes(path);
    inputPins.Add(path, Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant());
    return bytes;
}
string Identity(FormKey key) => $"{key.ID:X6}:{key.ModKey.FileName}";
FormKey Parse(string value)
{
    var parts = value.Split(':');
    if (parts.Length != 2 || parts[0].Length != 6 || !parts[0].All(Uri.IsHexDigit)
        || parts[1].IndexOfAny(new[] { '/', '\\', '\0' }) >= 0)
        throw new InvalidDataException($"invalid full source identity: {value}");
    return new FormKey(ModKey.FromNameAndExtension(parts[1]), Convert.ToUInt32(parts[0], 16));
}
using var selectionDoc = JsonDocument.Parse(ReadPinned(selectionPath));
var selection = selectionDoc.RootElement;
string[] Strings(string key) => selection.TryGetProperty(key, out var value)
    ? value.EnumerateArray().Select(v => v.GetString() ?? throw new InvalidDataException("null selector")).ToArray() : Array.Empty<string>();
var requestedCells = Strings("cells").Select(Parse).ToHashSet();
var requestedRefs = Strings("references").Select(Parse).ToHashSet();
var cellNames = Strings("cell_editor_ids");
if (selection.TryGetProperty("reference_map", out var mapName))
{
    string mapPath = Path.GetFullPath(mapName.GetString()!, Path.GetDirectoryName(selectionPath)!);
    using var mapDoc = JsonDocument.Parse(ReadPinned(mapPath));
    foreach (string section in new[] { "refs", "containers" })
        if (mapDoc.RootElement.TryGetProperty(section, out var entries))
            foreach (var entry in entries.EnumerateObject()) requestedRefs.Add(Parse(entry.Name));
}
if (requestedCells.Count + requestedRefs.Count + cellNames.Length == 0) throw new InvalidDataException("selection is empty");
inputPins.Add(source, Hash(source));
using var mod = Fallout4Mod.CreateFromBinaryOverlay(source, Fallout4Release.Fallout4);
IEnumerable<ICellGetter> Cells()
{
    foreach (var cell in mod.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(b => b.Cells)) yield return cell;
    foreach (var world in mod.Worldspaces)
    {
        if (world.TopCell != null) yield return world.TopCell;
        foreach (var cell in world.SubCells.SelectMany(b => b.Items).SelectMany(b => b.Items)) yield return cell;
    }
}
var cells = Cells().ToDictionary(c => c.FormKey);
var missing = new List<string>();
foreach (string name in cellNames)
{
    var matches = cells.Values.Where(c => string.Equals(c.EditorID, name, StringComparison.OrdinalIgnoreCase)).ToArray();
    if (matches.Length != 1) missing.Add($"cell_editor_id:{name} (matches={matches.Length})");
    else requestedCells.Add(matches[0].FormKey);
}
foreach (var key in requestedCells.Where(k => !cells.ContainsKey(k))) missing.Add(Identity(key));
var explicitCells = requestedCells.Where(cells.ContainsKey).ToHashSet();
var parents = new Dictionary<FormKey, FormKey>();
foreach (var cell in cells.Values)
    foreach (var reference in cell.Persistent.Concat(cell.Temporary))
        if (!parents.TryAdd(reference.FormKey, cell.FormKey)) throw new InvalidDataException("duplicate physical reference parent");
foreach (var key in requestedRefs.Where(k => !parents.ContainsKey(k))) missing.Add(Identity(key));
var selectedRefs = requestedRefs.Where(parents.ContainsKey).ToHashSet();
var partialCells = selectedRefs.Select(k => parents[k]).ToHashSet();
object? Match(FormKey key)
{
    if (key.IsNull) return null;
    string? relation = null;
    FormKey cell = key;
    if (explicitCells.Contains(key)) relation = "explicit_cell";
    else if (partialCells.Contains(key)) relation = "cell_with_selected_references";
    else if (parents.TryGetValue(key, out cell))
    {
        if (selectedRefs.Contains(key)) relation = "selected_reference";
        else if (explicitCells.Contains(cell)) relation = "reference_in_explicit_cell";
        else if (partialCells.Contains(cell)) relation = "unselected_reference_in_partial_cell";
    }
    return relation == null ? null : new { target = Identity(key), cell = Identity(cell), relation };
}
object[] Matches(IEnumerable<IFormLinkGetter> links) => links.Select(l => l.FormKey).Distinct()
    .OrderBy(Identity, StringComparer.Ordinal).Select(Match).Where(m => m != null).Cast<object>().ToArray();
var quests = new List<object>();
var scripts = new List<object>();
var adapters = new Dictionary<Type, PropertyInfo?>();
var adapterTypes = new Dictionary<string, int>();
int recordsScanned = 0, nonQuestAdapters = 0, fragmentGroups = 0;
void Script(IMajorRecordGetter owner, string path, IScriptEntryGetter script)
{
    if (string.IsNullOrEmpty(script.Name) && script.Properties.Count == 0) return;
    var links = script.EnumerateFormLinks().ToArray();
    scripts.Add(new { owner = Identity(owner.FormKey), owner_editor_id = owner.EditorID, owner_deleted = owner.IsDeleted,
        owner_selection = Match(owner.FormKey), path, name = script.Name, typed_link_count = links.Select(l => l.FormKey).Where(k => !k.IsNull).Distinct().Count(),
        properties = script.Properties.GroupBy(p => p.GetType().Name.Replace("BinaryOverlay", "")).ToDictionary(g => g.Key, g => g.Count()),
        matches = Matches(links), runtime_dependencies_resolved = false });
}
void Fragment(IMajorRecordGetter owner, string path, string name, string fragment) => scripts.Add(new {
    owner = Identity(owner.FormKey), owner_editor_id = owner.EditorID, owner_deleted = owner.IsDeleted,
    owner_selection = Match(owner.FormKey), path, name, fragment, matches = Array.Empty<object>(), runtime_dependencies_resolved = false });
void SimpleFragment(IMajorRecordGetter owner, string path, IScriptFragmentGetter? fragment)
{
    if (fragment != null) Fragment(owner, path, fragment.ScriptName, fragment.FragmentName);
}
void Fragments(IMajorRecordGetter owner, object? group)
{
    if (group == null) return;
    fragmentGroups++;
    // Scene fragments inherit the common begin/end/script fields.
    if (group is IScriptFragmentsGetter common)
    {
        if (common.Script != null) Script(owner, "fragments/script", common.Script);
        SimpleFragment(owner, "fragments/begin", common.OnBegin);
        SimpleFragment(owner, "fragments/end", common.OnEnd);
        if (common is ISceneScriptFragmentsGetter scene)
            foreach (var f in scene.PhaseFragments)
                Fragment(owner, $"fragments/phase/{f.Index}/{f.Flags}", f.ScriptName, f.FragmentName);
    }
    else if (group is IPackageScriptFragmentsGetter package)
    {
        if (package.Script != null) Script(owner, "fragments/script", package.Script);
        SimpleFragment(owner, "fragments/begin", package.OnBegin);
        SimpleFragment(owner, "fragments/end", package.OnEnd);
        SimpleFragment(owner, "fragments/change", package.OnChange);
    }
    else if (group is IPerkScriptFragmentsGetter perk)
    {
        if (perk.Script != null) Script(owner, "fragments/script", perk.Script);
        foreach (var f in perk.Fragments) Fragment(owner, $"fragments/perk/{f.Index}", f.ScriptName, f.FragmentName);
    }
    else if (group is IScriptFragmentsIndexedGetter indexed)
    {
        if (indexed.Script != null) Script(owner, "fragments/script", indexed.Script);
        int i = 0;
        foreach (var f in indexed.Fragments) Fragment(owner, $"fragments/indexed/{i++}", f.ScriptName, f.FragmentName);
    }
    else throw new InvalidDataException($"unsupported fragment group: {group.GetType().FullName}");
}
foreach (var record in mod.EnumerateMajorRecords())
{
    recordsScanned++;
    if (record is IQuestGetter quest)
        quests.Add(new { source = Identity(quest.FormKey), editor_id = quest.EditorID, deleted = quest.IsDeleted,
            stage_count = quest.Stages?.Count ?? 0, objective_count = quest.Objectives?.Count ?? 0,
            alias_count = quest.Aliases?.Count ?? 0,
            aliases_without_forced_reference = quest.Aliases?.Count(a => a is not IQuestReferenceAliasGetter r || r.ForcedReference.IsNull) ?? 0,
            matches = Matches(quest.EnumerateFormLinks()), runtime_dependencies_resolved = false });
    Type type = record.GetType();
    if (!adapters.TryGetValue(type, out var property))
        adapters[type] = property = type.GetProperty("VirtualMachineAdapter", BindingFlags.Public | BindingFlags.Instance);
    var adapter = property?.GetValue(record);
    if (adapter == null) continue;
    if (adapter is not IAVirtualMachineAdapterGetter vm)
        throw new InvalidDataException($"unsupported VMAD getter: {adapter.GetType().FullName}");
    adapterTypes[vm.GetType().Name] = adapterTypes.GetValueOrDefault(vm.GetType().Name) + 1;
    if (record is not IQuestGetter) nonQuestAdapters++;
    int index = 0;
    foreach (var script in vm.Scripts) Script(record, $"scripts/{index++}", script);
    if (vm is IQuestAdapterGetter qvm)
    {
        if (qvm.Script != null) Script(record, "fragment_script", qvm.Script);
        for (int i = 0; i < qvm.Aliases.Count; i++)
        {
            int j = 0;
            foreach (var script in qvm.Aliases[i].Scripts) Script(record, $"aliases/{i}/scripts/{j++}", script);
        }
        foreach (var fragment in qvm.Fragments)
            scripts.Add(new { owner = Identity(record.FormKey), owner_editor_id = record.EditorID, owner_deleted = record.IsDeleted,
                path = $"stage_fragment/{fragment.Stage}/{fragment.StageIndex}", name = fragment.ScriptName,
                fragment = fragment.FragmentName, matches = Array.Empty<object>(), runtime_dependencies_resolved = false });
    }
    else if (vm is IDialogResponsesAdapterGetter dialog) Fragments(record, dialog.ScriptFragments);
    else if (vm is ISceneAdapterGetter scene) Fragments(record, scene.ScriptFragments);
    else if (vm is IPackageAdapterGetter package) Fragments(record, package.ScriptFragments);
    else if (vm is IPerkAdapterGetter perk) Fragments(record, perk.ScriptFragments);
    else if (vm is IVirtualMachineAdapterIndexedGetter indexed) Fragments(record, indexed.ScriptFragments);
    else if (vm is not IVirtualMachineAdapterGetter)
        throw new InvalidDataException($"unsupported VMAD kind: {vm.GetType().FullName}");
}
foreach (var (path, hash) in inputPins)
    if (Hash(path) != hash) throw new IOException($"census input changed: {Path.GetFileName(path)}");
var report = new
{
    schema = 1, source_plugin = mod.ModKey.FileName.String,
    input_pins = inputPins.Select(kv => new { file = Path.GetFileName(kv.Key), sha256 = kv.Value }).ToArray(),
    static_scan_complete = true, selection_complete = missing.Count == 0, runtime_dependencies_resolved = false,
    scope = new { explicit_cells = explicitCells.Select(Identity).Order().ToArray(), selected_reference_count = selectedRefs.Count,
        cells_with_selected_references = partialCells.Select(Identity).Order().ToArray(), missing_selectors = missing.Order().ToArray() },
    counts = new { records_scanned = recordsScanned, quests = quests.Count, script_instances = scripts.Count, non_quest_adapters = nonQuestAdapters,
        non_quest_fragment_groups = fragmentGroups },
    adapter_types = adapterTypes, quests, scripts,
    limitations = new[] { "Only this pinned source plugin, not a winning multi-plugin load order or DLC.",
        "Typed direct links only; no PEX/string scanning, runtime aliases, computed lookup, global state or transitive dependency resolution.",
        "Cell membership is source placement, not proof that every object in the cell is converted or functional.",
        "No matches does not prove irrelevance. Fragment names are attachment metadata, not an analysis of compiled script behavior.",
        "Quest typed links may include nested dialogue/scene data; script rows identify exact attachment provenance separately." }
};
Directory.CreateDirectory(Path.GetDirectoryName(destination)!);
using (var stream = new FileStream(destination, FileMode.CreateNew, FileAccess.Write, FileShare.None))
    JsonSerializer.Serialize(stream, report, new JsonSerializerOptions { WriteIndented = true });
Console.WriteLine(JsonSerializer.Serialize(report.counts));
if (missing.Count != 0) Environment.ExitCode = 2;
