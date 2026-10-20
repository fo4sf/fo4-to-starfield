using System.Text.Json;

// Identity-only planning. Promotion changes the base type, not the source REFR's
// slot in this export. It is not a persistent allocator for reordered exports.
// Every promoted class ("containers", "items", "activators", "terminals", "workshops", "benches") is one ordered list
// of promoted sources: each carries its original reference_index, the remaining "refs" fill the other slots in order.
internal static class ReferenceIdentityPlan
{
    // objects.json keys of the promoted classes (make_core64c.py ALL_PROMOTED): CONT, MISC, ACTI, TERM (+ TMLM), then the
    // workshops' ACTI bases; a bench binds to a vanilla FURN of the master and adds no base; a scripted load door keeps
    // its slot too, its ACTI base and arrival marker are allocated after everything else (docs/terrain/scripted-doors.md)
    public static readonly string[] PromotedClasses = { "containers", "items", "activators", "terminals", "workshops", "flora", "benches", "doors" };

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

    // Exterior lights (docs/terrain/exterior-lights.md): core64c never placed a FO4 Light reference, so a light owns no
    // reserved slot. Its REFR takes a NEW id after every record the build has without lights, in "lights" order.
    // Refused: a light that claims an original reference_index, an empty or repeated source, a source that is also a
    // reserved one (case-insensitive, as Order), a light whose edid is not in "light_bases", a light base listed twice,
    // a light whose "flags" hold any bit but the carried REFR ones: 0x100 DoesNotLightWater, 0x10000 NeverFades,
    // 0x20000 DoesNotLightLandscape (Mutagen's PlacedObject.LightMajorFlag in both games; make_core64c.py LIGHT_REF_FLAGS).
    public const uint LightRefFlags = 0x100 | 0x10000 | 0x20000;

    public static string[] Lights(JsonElement objects, IEnumerable<string> reserved)
    {
        if (!objects.TryGetProperty("lights", out var lights))
            return Array.Empty<string>();
        var bases = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        if (objects.TryGetProperty("light_bases", out var lb))
            foreach (var b in lb.EnumerateArray())
                if (!bases.Add(b.GetProperty("edid").GetString() ?? ""))
                    throw new InvalidDataException("light base listed twice");
        var seen = new HashSet<string>(reserved, StringComparer.OrdinalIgnoreCase);
        var order = new List<string>();
        foreach (var item in lights.EnumerateArray())
        {
            if (item.TryGetProperty("reference_index", out _))
                throw new InvalidDataException("a light owns no original reference slot (core64c never placed it)");
            var source = item.GetProperty("src").GetString();
            if (string.IsNullOrWhiteSpace(source))
                throw new InvalidDataException("light source identity is empty");
            if (!seen.Add(source))
                throw new InvalidDataException("light source identity repeats a reserved or light source");
            if (!bases.Contains(item.GetProperty("edid").GetString() ?? ""))
                throw new InvalidDataException("light names a base that is not in light_bases");
            if (!item.TryGetProperty("flags", out var flags) || flags.ValueKind != JsonValueKind.Number
                || !flags.TryGetUInt32(out var bits) || (bits & ~LightRefFlags) != 0)
                throw new InvalidDataException("light flags must be the FO4 reference's carried REFR bits (0x30100 at most)");
            order.Add(source);
        }
        return order.ToArray();
    }
}
