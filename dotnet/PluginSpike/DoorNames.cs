// Door names (docs/spikes/door-behaviour.md, "Name in the prompt"): the FO4 DOOR's FULL, so the prompt reads "Open Roof
// Hatch" instead of "Open Door".
//
// PluginSpike makes one DOOR base per converted MODEL, while Fallout 4 names its DOOR records: one model can sit under
// several FO4 bases with different names (a "Door" and a "Front Door"). Each placed reference's FO4 base is in its cell
// export (base_formkey), and that base's record in door_bases (Fo4Export, 2026-10-18: record.Name, the FULL as text;
// Mutagen 0.55's TranslatedString dumps as its string, checked 2026-10-19). Per converted DOOR base:
// - every reference's FO4 name is one line, or "Door" when FO4 gives none (an unnamed base, or an export without
//   door_bases);
// - the most common name becomes the base's name (ties: an FO4 name before "Door", then ordinal order);
// - each other name gets a copy of the base under identity DOOR:<editor id>|name:<name>, so its FormID is stable, and
//   that name's references move to the copy. A copy keeps the original's open / own-rig roles (the caller's sets).
// Runs before activation chains and teleport links, which read the bases. Not verified in game.
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Starfield;

public sealed class DoorNameReport
{
    public int Named { get; set; }        // DOOR bases whose name is no longer "Door"
    public int Copies { get; set; }       // extra DOOR bases made for a second (third, ...) name of one model
    public int Moved { get; set; }        // references moved to a copy
    public int Unnamed { get; set; }      // door references with no usable FO4 name (kept "Door")
    public List<string> Refused { get; } = new();   // "<source ref>: <reason>" for names that are not one line
}

public static class DoorNames
{
    public const string Default = "Door";
    const int MaxLength = 128;

    public static DoorNameReport Apply(StarfieldMod mod, IReadOnlyDictionary<string, (PlacedObject obj, Cell cell)> placed,
                                       IEnumerable<JsonElement> cellExports, Func<string, FormKey> id, params ISet<FormKey>[] roles)
    {
        var report = new DoorNameReport();
        var doors = mod.Doors.ToDictionary(d => d.FormKey);
        var byBase = new Dictionary<FormKey, List<(PlacedObject obj, string name)>>();
        foreach (var export in cellExports)
        {
            var bases = export.TryGetProperty("door_bases", out var db) && db.ValueKind == JsonValueKind.Object ? db : (JsonElement?)null;
            foreach (var r in export.GetProperty("refs").EnumerateArray())
            {
                var src = r.GetProperty("formkey").GetString()!;
                if (!placed.TryGetValue(src, out var p) || !doors.ContainsKey(p.obj.Base.FormKey)) continue;
                var name = Name(r, bases, src, report);
                if (name == null) { report.Unnamed++; name = Default; }
                if (!byBase.TryGetValue(p.obj.Base.FormKey, out var list)) byBase[p.obj.Base.FormKey] = list = new();
                list.Add((p.obj, name));
            }
        }
        foreach (var (key, refs) in byBase.OrderBy(kv => kv.Key.ID))
        {
            var door = doors[key];
            var names = refs.GroupBy(r => r.name, StringComparer.Ordinal)
                .OrderByDescending(g => g.Count()).ThenBy(g => g.Key == Default).ThenBy(g => g.Key, StringComparer.Ordinal).ToList();
            door.Name = names[0].Key;
            if (names[0].Key != Default) report.Named++;
            foreach (var group in names.Skip(1))
            {
                var copy = door.Duplicate(id($"DOOR:{door.EditorID}|name:{group.Key}"));
                copy.EditorID = $"{door.EditorID}_N{Digest(group.Key)}";
                copy.Name = group.Key;
                mod.Doors.Add(copy);
                foreach (var set in roles)
                    if (set.Contains(key)) set.Add(copy.FormKey);
                foreach (var (obj, _) in group) { obj.Base.SetTo(copy.FormKey); report.Moved++; }
                report.Copies++;
                if (group.Key != Default) report.Named++;
            }
        }
        return report;
    }

    // the reference's FO4 base name: door_bases[base_formkey].record.Name, one trimmed line; null when absent or empty
    static string? Name(JsonElement r, JsonElement? bases, string src, DoorNameReport report)
    {
        if (bases is not JsonElement b || !r.TryGetProperty("base_formkey", out var bk) || bk.ValueKind != JsonValueKind.String
            || !b.TryGetProperty(bk.GetString()!, out var entry) || !entry.TryGetProperty("record", out var rec)
            || rec.ValueKind != JsonValueKind.Object || !rec.TryGetProperty("Name", out var n) || n.ValueKind != JsonValueKind.String)
            return null;
        var t = n.GetString()!.Trim();
        if (t.Length == 0) return null;
        if (t.Length > MaxLength || t.Any(char.IsControl)) { report.Refused.Add($"{src}: name is not one short line"); return null; }
        return t;
    }

    static string Digest(string name) =>
        Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(name)))[..8];
}
