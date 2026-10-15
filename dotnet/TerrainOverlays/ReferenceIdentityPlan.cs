using System.Text.Json;

// Identity-only planning. Promotion changes the base type, not the source REFR's
// slot in this export. It is not a persistent allocator for reordered exports.
internal static class ReferenceIdentityPlan
{
    public static string[] Order(JsonElement objects)
    {
        string Source(JsonElement item)
        {
            var source = item.GetProperty("src").GetString();
            if (string.IsNullOrWhiteSpace(source))
                throw new InvalidDataException("reference source identity is empty");
            return source;
        }

        var refs = objects.GetProperty("refs").EnumerateArray().ToArray();
        var containers = objects.TryGetProperty("containers", out var c)
            ? c.EnumerateArray().ToArray() : Array.Empty<JsonElement>();
        var sources = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var item in refs.Concat(containers))
            if (!sources.Add(Source(item)))
                throw new InvalidDataException("duplicate reference source identity");

        var order = new string[checked(refs.Length + containers.Length)];
        foreach (var item in containers)
        {
            if (!item.TryGetProperty("reference_index", out var index) || index.ValueKind != JsonValueKind.Number
                || !index.TryGetInt32(out int slot)
                || slot < 0 || slot >= order.Length)
                throw new InvalidDataException("container needs its original reference_index");
            if (order[slot] != null)
                throw new InvalidDataException("duplicate container reference_index");
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
