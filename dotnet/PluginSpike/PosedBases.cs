// Per-reference bases for posed models. scripts/convert_batch.py (src/fo4sf/placed_pose.py) converts an FO4 reference whose
// ragdoll data (XRGD) lays its model out differently from the NIF's node pose (a skeleton lying on the floor) into a model
// of its own; its manifest item carries "pose": {"kind": "xrgd", "refs": [FO4 FormKeys], ...} and the same "source" as the
// shared item. Such an item's base record is used for exactly those references; every other reference of the model keeps
// the shared base found by its model path.
using System.Text.Json;

public static class PosedBases
{
    /// FO4 FormKeys of the references a manifest item is posed for; empty for an ordinary (shared) item.
    public static IReadOnlyList<string> RefsOf(JsonElement item)
    {
        if (!item.TryGetProperty("pose", out var pose) || pose.ValueKind != JsonValueKind.Object) return Array.Empty<string>();
        if (!pose.TryGetProperty("refs", out var refs) || refs.ValueKind != JsonValueKind.Array || refs.GetArrayLength() == 0)
            throw new InvalidOperationException($"posed manifest item {item.GetProperty("editor_id").GetString()} lists no references");
        return refs.EnumerateArray().Select(r => r.GetString() ?? throw new InvalidOperationException("null pose reference")).ToList();
    }

    /// Registers a base: for each posed reference when `posedRefs` is non-empty (a reference posed twice is an error),
    /// otherwise under the model's source path (backslashes, case-insensitive dictionary expected).
    public static void Register<T>(Dictionary<string, T> byRef, Dictionary<string, T> bySource, string source,
                                   IReadOnlyList<string> posedRefs, T value)
    {
        if (posedRefs.Count == 0) { bySource[source.Replace('/', '\\')] = value; return; }
        foreach (var r in posedRefs)
            if (!byRef.TryAdd(r, value)) throw new InvalidOperationException($"reference {r} has two posed models");
    }

    /// The base for a placed reference: its own posed model when the manifest has one, else the shared base of its model
    /// ("meshes\" + the export's model path); false when neither exists (the reference is skipped).
    public static bool TryResolve<T>(IReadOnlyDictionary<string, T> byRef, IReadOnlyDictionary<string, T> bySource,
                                     string refFormKey, string model, out T value)
    {
        if (byRef.TryGetValue(refFormKey, out value!)) return true;
        if (model.Length > 0 && bySource.TryGetValue("meshes\\" + model.TrimStart('\\'), out value!)) return true;
        value = default!;
        return false;
    }
}
