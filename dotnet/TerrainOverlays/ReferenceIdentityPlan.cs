using System.Text.Json;

// Identity-only planning. Promotion changes the base type, not the source REFR's
// slot in this export. It is not a persistent allocator for reordered exports.
// Every promoted class ("containers", "items", "activators", "terminals") is one ordered list of promoted sources:
// each carries its original reference_index, the remaining "refs" fill the other slots in order.
internal static class ReferenceIdentityPlan
{
    // objects.json keys of the promoted classes (make_core64c.py PROMOTED): CONT, MISC, ACTI, then TERM (+ TMLM) bases
    public static readonly string[] PromotedClasses = { "containers", "items", "activators", "terminals" };

    public static string[] Order(JsonElement objects)
    {
        string Source(JsonElement item)
        {
            var source = item.GetProperty("src").GetString();
            if (string.IsNullOrWhiteSpace(source))
                throw new InvalidDataException("reference source identity is empty");
            return source;
        }

        JsonElement[] Promoted(string key) => objects.TryGetProperty(key, out var c)
            ? c.EnumerateArray().ToArray() : Array.Empty<JsonElement>();
        var refs = objects.GetProperty("refs").EnumerateArray().ToArray();
        var promoted = PromotedClasses.SelectMany(Promoted).ToArray();
        var sources = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var item in refs.Concat(promoted))
            if (!sources.Add(Source(item)))
                throw new InvalidDataException("duplicate reference source identity");

        var order = new string[checked(refs.Length + promoted.Length)];
        foreach (var item in promoted)
        {
            if (!item.TryGetProperty("reference_index", out var index) || index.ValueKind != JsonValueKind.Number
                || !index.TryGetInt32(out int slot)
                || slot < 0 || slot >= order.Length)
                throw new InvalidDataException("promoted reference needs its original reference_index");
            if (order[slot] != null)
                throw new InvalidDataException("duplicate promoted reference_index");
            order[slot] = Source(item);
        }
        int next = 0;
        foreach (var item in refs)
        {
            while (order[next] != null) next++;
            order[next++] = Source(item);
        }
        return order;
    }
}
