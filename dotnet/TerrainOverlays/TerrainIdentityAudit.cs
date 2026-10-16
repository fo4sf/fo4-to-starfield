using System.Globalization;
using System.Security.Cryptography;
using System.Text.Json;
using Mutagen.Bethesda.Plugins;

// Identity verification only: existing raw-record checks and native tests remain separate gates.
// Holds the writer's temporary coordination lease, but never writes artifacts, reservations or recovery state.
internal static class TerrainIdentityAudit
{
    private static bool Exists(string path) => File.Exists(path) || Directory.Exists(path) || new FileInfo(path).LinkTarget != null;
    private static bool Has(JsonElement e, string key) => e.TryGetProperty(key, out var v) && v.ValueKind is not (JsonValueKind.Null or JsonValueKind.False);
    private static string Text(JsonElement e, string key) => e.GetProperty(key).GetString() ?? throw new InvalidDataException($"null {key}");
    private static JsonElement[] Entries(JsonElement e, string key) => e.TryGetProperty(key, out var v) ? v.EnumerateArray().ToArray() : Array.Empty<JsonElement>();
    private static string Coordinate(JsonElement value) => value.GetInt32().ToString(CultureInfo.InvariantCulture);
    private static void UniqueProperties(JsonElement value)
    {
        if (value.ValueKind == JsonValueKind.Object)
        {
            var keys = new HashSet<string>(StringComparer.Ordinal);
            foreach (var p in value.EnumerateObject())
            {
                if (!keys.Add(p.Name)) throw new InvalidDataException($"duplicate JSON property: {p.Name}");
                UniqueProperties(p.Value);
            }
        }
        else if (value.ValueKind == JsonValueKind.Array)
            foreach (var item in value.EnumerateArray()) UniqueProperties(item);
    }

    public static object Check(string directory, Action<object>? whileValidated = null)
    {
        string root = Path.GetFullPath(directory);
        if (!Directory.Exists(root) || new DirectoryInfo(root).LinkTarget != null)
            throw new IOException("identity audit needs an existing ordinary stage directory");
        string pending = Path.Combine(root, OutputPublication.PendingName);
        if (Exists(pending)) throw new IOException("pending output publication requires review");
        using var lease = new FileStream(Path.Combine(root, OutputPublication.LeaseName), FileMode.CreateNew,
            FileAccess.ReadWrite, FileShare.None, 4096, FileOptions.DeleteOnClose);
        if (Exists(pending)) throw new IOException("pending output publication requires review");
        var docs = new List<JsonDocument>();
        var inputHashes = new Dictionary<string, string>(StringComparer.Ordinal);
        try
        {
            string Inside(string name, bool flat = false)
            {
                if (string.IsNullOrWhiteSpace(name) || Path.IsPathRooted(name)
                    || flat && (name.Contains('/') || name.Contains('\\') || name is "." or ".."
                                || name.IndexOfAny(Path.GetInvalidFileNameChars()) >= 0))
                    throw new InvalidDataException("audit paths must be relative stage paths; outputs must be flat names");
                string path = Path.GetFullPath(Path.Combine(root, name));
                var comparison = OperatingSystem.IsWindows() ? StringComparison.OrdinalIgnoreCase : StringComparison.Ordinal;
                if (!path.StartsWith(root.TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar, comparison))
                    throw new IOException("audit input escapes the stage");
                for (string? p = path; p != null && !p.Equals(root, comparison); p = Path.GetDirectoryName(p))
                    if (new FileInfo(p).LinkTarget != null || new DirectoryInfo(p).LinkTarget != null)
                        throw new IOException("linked audit input/output is unproven");
                return path;
            }
            JsonElement Read(string name)
            {
                string path = Inside(name);
                byte[] bytes = File.ReadAllBytes(path);
                inputHashes[path] = Convert.ToHexString(SHA256.HashData(bytes));
                var doc = JsonDocument.Parse(bytes);
                docs.Add(doc);
                UniqueProperties(doc.RootElement);
                return doc.RootElement;
            }
            var prm = Read("overlays_params.json");
            if (!prm.TryGetProperty("persistent_ids", out var enabled) || enabled.ValueKind != JsonValueKind.True)
                throw new InvalidDataException("audit requires explicit persistent_ids and an existing ledger");
            string plugin = ModKey.FromNameAndExtension(Text(prm, "plugin")).FileName.String;
            var outputs = new List<string> { plugin };
            if (Has(prm, "objects") || Has(prm, "navmesh")) outputs.Add("formids.json");
            if (Has(prm, "mars")) outputs.Add(Text(prm.GetProperty("mars"), "plugin"));
            if (outputs.Distinct(StringComparer.OrdinalIgnoreCase).Count() != outputs.Count)
                throw new InvalidDataException("duplicate output name");
            foreach (string name in outputs)
                if (name.Equals(OutputPublication.LeaseName, StringComparison.OrdinalIgnoreCase)
                    || name.Equals(OutputPublication.PendingName, StringComparison.OrdinalIgnoreCase)
                    || !File.Exists(Inside(name, flat: true))) throw new IOException("published output bundle is incomplete or reserved");
            Read(TerrainStableIds.FileName); // Require an existing ordinary file and reject duplicate JSON properties.
            var stable = TerrainStableIds.Open(root, plugin, true, false, outputs)!;
            int checkedIds = 0;
            uint Reserved(params string[] key) { checkedIds++; return stable.Published(key); }
            void Match(JsonElement value, params string[] key)
            {
                string? hex = value.GetString();
                if (hex == null || hex.Length != 6 || !hex.All(Uri.IsHexDigit)
                    || uint.Parse(hex, NumberStyles.HexNumber, CultureInfo.InvariantCulture) != Reserved(key))
                    throw new InvalidDataException($"mapped id disagrees with reservation: {string.Join('/', key)}");
            }
            void Keys(JsonElement map, IEnumerable<string> expected)
            {
                if (map.ValueKind != JsonValueKind.Object || !map.EnumerateObject().Select(p => p.Name).ToHashSet(StringComparer.Ordinal)
                    .SetEquals(expected)) throw new InvalidDataException("map/source key sets differ");
            }
            Dictionary<string, JsonElement> Index(JsonElement map, IEnumerable<string> expected)
            {
                Keys(map, expected);
                // GetProperty scans a JSON object. Index each large section once, not once per source.
                // Read already rejected duplicate properties; preserve exact ordinal key matching.
                return map.EnumerateObject().ToDictionary(p => p.Name, p => p.Value, StringComparer.Ordinal);
            }
            var overlays = prm.GetProperty("overlays").EnumerateArray().ToArray();
            if (overlays.Length == 0) throw new InvalidDataException("audit needs at least one overlay");
            foreach (var o in overlays)
            {
                string world = Text(o, "world");
                if (Reserved("anchor", world) != o.GetProperty("anchor").GetProperty("form_id").GetUInt32())
                    throw new InvalidDataException("anchor differs from reservation");
                foreach (string kind in new[] { "block", "location", "world", "persistent-cell" }) Reserved(kind, world);
                int lo = o.GetProperty("cell_min").GetInt32(), hi = o.GetProperty("cell_max").GetInt32();
                if (lo > hi) throw new InvalidDataException("invalid overlay cell range");
                for (long x = lo; x <= hi; x++)
                    for (long y = lo; y <= hi; y++) Reserved("cell", world, x.ToString(CultureInfo.InvariantCulture), y.ToString(CultureInfo.InvariantCulture));
                var spawn = o.GetProperty("spawn_cell");
                if (spawn[0].GetInt32() >= lo && spawn[0].GetInt32() <= hi && spawn[1].GetInt32() >= lo && spawn[1].GetInt32() <= hi)
                    Reserved("coc", world);
            }
            JsonElement map = default;
            var sections = new HashSet<string> { "plugin" };
            if (outputs.Contains("formids.json"))
            {
                map = Read("formids.json");
                if (Text(map, "plugin") != plugin) throw new InvalidDataException("map plugin differs");
            }
            string objectWorld = Text(overlays[0], "world");
            if (Has(prm, "objects"))
            {
                var obj = Read(Text(prm, "objects"));
                var sources = ReferenceIdentityPlan.Order(obj);
                ReferenceIdentityPlan.Lights(obj, sources);
                objectWorld = obj.TryGetProperty("world", out var w) ? w.GetString()! : objectWorld;
                if (Text(map, "world") != objectWorld) throw new InvalidDataException("map world differs");
                sections.UnionWith(new[] { "world", "bases", "refs", "containers" });
                var bases = obj.GetProperty("bases").EnumerateArray().ToArray();
                var baseIds = Index(map.GetProperty("bases"), bases.Select(b => Text(b, "edid")));
                foreach (var b in bases) Match(baseIds[Text(b, "edid")], "base", Text(b, "edid"));
                var refs = obj.GetProperty("refs").EnumerateArray().ToArray();
                var refIds = Index(map.GetProperty("refs"), refs.Select(r => Text(r, "src")));
                foreach (var r in refs) Match(refIds[Text(r, "src")], "reference", TerrainStableIds.Source(Text(r, "src")));
                foreach (var (name, kind) in new[] { ("containers", "container"), ("items", "item"), ("activators", "activator"),
                         ("terminals", "terminal"), ("workshops", "workshop"), ("doors", "door-base"), ("lights", "light-base") })
                {
                    var entries = Entries(obj, name);
                    bool present = name == "containers" || (name is "doors" or "lights" ? entries.Length > 0 : obj.TryGetProperty(name, out _));
                    if (!present) continue;
                    sections.Add(name);
                    var ids = Index(map.GetProperty(name), entries.Select(e => Text(e, "src")));
                    foreach (var e in entries)
                    {
                        string src = TerrainStableIds.Source(Text(e, "src"));
                        var v = ids[Text(e, "src")];
                        Keys(v, name == "terminals" ? new[] { "ref", "base", "menu" }
                            : name == "doors" ? new[] { "ref", "base", "arrival" } : new[] { "ref", "base" });
                        Match(v.GetProperty("base"), kind, Text(e, "edid"));
                        Match(v.GetProperty("ref"), name == "lights" ? "light-reference" : "reference", src);
                        if (name == "terminals") Match(v.GetProperty("menu"), "terminal-menu", Text(e, "menu_edid"));
                        if (name == "doors") Match(v.GetProperty("arrival"), "door-arrival", src);
                    }
                }
                if (obj.TryGetProperty("benches", out var benches))
                {
                    sections.Add("benches");
                    var ids = Index(map.GetProperty("benches"), benches.EnumerateArray().Select(e => Text(e, "src")));
                    foreach (var e in benches.EnumerateArray())
                    {
                        var v = ids[Text(e, "src")];
                        Keys(v, new[] { "ref", "base", "kind" });
                        string kind = Text(e, "kind"), vanilla = Text(e, "vanilla");
                        int colon = vanilla.IndexOf(':');
                        if (Text(v, "kind") != kind || Text(v, "base") != vanilla
                            || !ReferenceIdentityPlan.BenchKinds.TryGetValue(kind, out var expected)
                            || colon < 1 || !uint.TryParse(vanilla[..colon], NumberStyles.HexNumber, CultureInfo.InvariantCulture, out var id)
                            || id != expected || !vanilla[(colon + 1)..].Equals("Starfield.esm", StringComparison.OrdinalIgnoreCase))
                            throw new InvalidDataException($"bench identity differs: {Text(e, "src")}");
                        Match(v.GetProperty("ref"), "reference", TerrainStableIds.Source(Text(e, "src")));
                    }
                }
                if (Entries(obj, "lights").Length > 0)
                    foreach (var b in Entries(obj, "light_bases")) Reserved("light-base", Text(b, "edid"));
            }
            if (Has(prm, "navmesh"))
            {
                sections.UnionWith(new[] { "world", "navmeshes", "navi" });
                var nav = Read(Text(prm, "navmesh"));
                string world = nav.TryGetProperty("world", out var w) ? w.GetString()! : objectWorld;
                if (!Has(prm, "objects") && Text(map, "world") != world || Text(map, "navi") != "000FF1:Starfield.esm")
                    throw new InvalidDataException("navmesh map world/NAVI differs");
                var entries = Entries(nav, "navmeshes");
                var ids = map.GetProperty("navmeshes").EnumerateArray().ToArray();
                if (ids.Length != entries.Length) throw new InvalidDataException("navmesh map/source counts differ");
                for (int i = 0; i < ids.Length; i++) Match(ids[i], "navmesh", world, TerrainStableIds.Source(Text(entries[i], "src")),
                    Coordinate(entries[i].GetProperty("cell")[0]), Coordinate(entries[i].GetProperty("cell")[1]));
            }
            if (map.ValueKind != JsonValueKind.Undefined) Keys(map, sections);
            void VerifyGeneration()
            {
                foreach (var (path, hash) in inputHashes)
                {
                    Inside(Path.GetRelativePath(root, path));
                    if (hash != Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path)))) throw new IOException("audit input changed");
                }
                stable.VerifyUnchanged();
                if (Exists(pending)) throw new IOException("publication recovery appeared during audit");
            }
            VerifyGeneration();
            object report = new { mode = "persistent-identity-audit", plugin, checked_ids = checkedIds,
                output_count = outputs.Count, artifacts_changed = false, record_fields_checked = false, native_acceptance = false };
            if (whileValidated != null)
            {
                whileValidated(report); // Keep this lease through the caller's raw-record reads.
                VerifyGeneration();
            }
            return report;
        }
        finally { foreach (var doc in docs) doc.Dispose(); }
    }
}
