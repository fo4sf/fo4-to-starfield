using System.Security.Cryptography;
using System.Text.Json;

// The caller must hold OutputPublication's lease for this object's entire lifetime.
// Reservations precede publication and are never rolled back or recycled.
internal sealed class TerrainStableIds
{
    public const string FileName = "terrain-stable-ids.json";
    private readonly string root, path, plugin;
    private readonly string[] outputs;
    private readonly bool bootstrap;
    private readonly byte[]? original;
    private readonly Dictionary<string, uint> ids = new(StringComparer.Ordinal);
    private readonly HashSet<string> seen = new(StringComparer.Ordinal);
    private readonly HashSet<uint> occupied = new();
    private readonly Dictionary<string, string?> initialOutputs;
    private Dictionary<string, string?>[] acceptedOutputs;
    public uint NextId { get; private set; } = 0x800;

    private static string Fold(string value) => string.Concat(value.Select(c => c is >= 'A' and <= 'Z' ? (char)(c + 32) : c));
    private static string Key(params string[] parts)
    {
        if (parts.Any(string.IsNullOrWhiteSpace)) throw new InvalidDataException("empty semantic identity part");
        var canonical = parts.Select(Fold).ToArray();
        if (!ValidKey(canonical)) throw new InvalidDataException("invalid semantic identity key");
        return JsonSerializer.Serialize(canonical);
    }

    public static string Source(string source)
    {
        var parts = source.Split(':');
        if (parts.Length != 2 || parts[0].Length != 6 || !parts[0].All(Uri.IsHexDigit)
            || parts[1].IndexOfAny(new[] { '/', '\\', '\0' }) >= 0
            || !new[] { ".esm", ".esp", ".esl" }.Any(ext => parts[1].EndsWith(ext, StringComparison.OrdinalIgnoreCase))
            || parts[1].Length <= 4)
            throw new InvalidDataException($"invalid full source identity: {source}");
        return Fold(source); // Preserve punctuation, extension and non-ASCII spelling.
    }

    private byte[] IdentityBytes() => JsonSerializer.SerializeToUtf8Bytes(new
    {
        format = 1, plugin,
        reservations = ids.OrderBy(kv => kv.Value).ToDictionary(kv => kv.Key, kv => kv.Value),
        accepted_outputs = acceptedOutputs
    });
    private string Checksum() => Convert.ToHexString(SHA256.HashData(IdentityBytes())).ToLowerInvariant();

    public static TerrainStableIds? Open(string root, string plugin, bool enabled, bool bootstrap, IEnumerable<string> outputs)
    {
        string path = Path.Combine(root, FileName);
        if (!enabled)
        {
            if (bootstrap || File.Exists(path) || Directory.Exists(path) || new FileInfo(path).LinkTarget != null)
                throw new InvalidDataException("persistent_ids must remain enabled beside an existing ledger");
            return null;
        }
        return new TerrainStableIds(root, plugin, bootstrap, outputs.ToArray());
    }

    private TerrainStableIds(string root, string plugin, bool bootstrap, string[] outputs)
    {
        this.root = root; this.plugin = plugin; this.bootstrap = bootstrap; this.outputs = outputs;
        path = Path.Combine(root, FileName);
        if (outputs.Any(n => n.Equals(FileName, StringComparison.OrdinalIgnoreCase)))
            throw new InvalidDataException("identity ledger cannot be a plugin/map output");
        CheckPath();
        initialOutputs = Snapshot(name => Path.Combine(root, name));
        acceptedOutputs = new[] { initialOutputs };
        if (!File.Exists(path))
        {
            bool any = outputs.Any(n => File.Exists(Path.Combine(root, n)));
            bool all = outputs.All(n => File.Exists(Path.Combine(root, n)));
            if (any && !bootstrap || bootstrap && !all)
                throw new InvalidDataException("existing outputs need explicit identical-output identity bootstrap; partial stages refused");
            return;
        }
        if (bootstrap) throw new InvalidDataException("cannot bootstrap over an existing identity ledger");
        original = File.ReadAllBytes(path);
        using var doc = JsonDocument.Parse(original);
        var data = doc.RootElement;
        if (data.ValueKind != JsonValueKind.Object || data.EnumerateObject().Count() != 5
            || data.GetProperty("format").GetInt32() != 1 || data.GetProperty("plugin").GetString() != plugin)
            throw new InvalidDataException("identity ledger schema/plugin mismatch");
        foreach (var entry in data.GetProperty("reservations").EnumerateObject())
        {
            string[] parts = JsonSerializer.Deserialize<string[]>(entry.Name) ?? throw new InvalidDataException("invalid identity key");
            if (!ValidKey(parts) || Key(parts) != entry.Name || !entry.Value.TryGetUInt32(out uint id)
                || id < 0x800 || id > 0xFFFFFF || !ids.TryAdd(entry.Name, id) || !occupied.Add(id))
                throw new InvalidDataException("invalid or duplicate identity reservation");
            NextId = Math.Max(NextId, id + 1);
        }
        acceptedOutputs = data.GetProperty("accepted_outputs").EnumerateArray().Select(item =>
        {
            var names = item.EnumerateObject().ToArray();
            if (names.Length != outputs.Length || !names.Select(p => p.Name).Order().SequenceEqual(outputs.Order()))
                throw new InvalidDataException("identity ledger output bundle mismatch");
            return names.OrderBy(p => p.Name, StringComparer.Ordinal).ToDictionary(p => p.Name, p =>
            {
                string? value = p.Value.GetString();
                if (value != null && (value.Length != 64 || !value.All(Uri.IsHexDigit)))
                    throw new InvalidDataException("invalid identity output hash");
                return value;
            });
        }).ToArray();
        if (acceptedOutputs.Length is < 1 or > 2 || !acceptedOutputs.Any(s => SameSnapshot(s, initialOutputs)))
            throw new InvalidDataException("identity ledger does not belong to the published output generation");
        if (data.GetProperty("checksum").GetString() != Checksum())
            throw new InvalidDataException("identity ledger checksum mismatch");
    }

    private void CheckPath()
    {
        if (Directory.Exists(path) || new FileInfo(path).LinkTarget != null)
            throw new IOException("identity ledger is a directory or link");
    }

    private static bool ValidKey(string[] p)
    {
        if (p.Length < 2 || p.Any(string.IsNullOrWhiteSpace)) return false;
        bool Coordinate(string v) => int.TryParse(v, System.Globalization.NumberStyles.Integer,
            System.Globalization.CultureInfo.InvariantCulture, out int n)
            && n.ToString(System.Globalization.CultureInfo.InvariantCulture) == v;
        return p[0] switch
        {
            "anchor" or "block" or "location" or "world" or "coc" or "persistent-cell" or "base" or "container" or "item"
                or "door-base" or "activator" or "terminal" or "terminal-menu" or "light-base" or "workshop" or "flora" => p.Length == 2,
            "reference" or "door-arrival" or "light-reference" => p.Length == 2 && Source(p[1]) == p[1],
            "map-marker" => p.Length == 3,
            "cell" => p.Length == 4 && Coordinate(p[2]) && Coordinate(p[3]),
            "navmesh" => p.Length == 5 && Source(p[2]) == p[2] && Coordinate(p[3]) && Coordinate(p[4]),
            _ => false
        };
    }

    public uint Reserve(params string[] parts) => ReserveKey(Key(parts), null);
    // Audit callers hold the same publication lease; looking up a key never reserves or recycles an id.
    public uint Published(params string[] parts) => ids.TryGetValue(Key(parts), out uint id) ? id
        : throw new InvalidDataException($"published identity has no reservation: {Key(parts)}");
    public void VerifyUnchanged()
    {
        CheckPath();
        if (original == null || !File.Exists(path) || !File.ReadAllBytes(path).SequenceEqual(original)
            || !SameSnapshot(initialOutputs, Snapshot(name => Path.Combine(root, name))))
            throw new IOException("identity ledger or published outputs changed during audit");
    }
    public void Anchor(string world, uint expected) => ReserveKey(Key("anchor", world), expected);
    private uint ReserveKey(string key, uint? expected)
    {
        if (!seen.Add(key)) throw new InvalidDataException($"duplicate semantic identity: {key}");
        if (ids.TryGetValue(key, out uint prior))
        {
            if (expected.HasValue && prior != expected.Value)
                throw new InvalidDataException("planned anchor disagrees with its persistent reservation");
            return prior;
        }
        uint value = expected ?? NextId;
        if (value < 0x800 || value > 0xFFFFFF || !occupied.Add(value))
            throw new InvalidDataException("identity range exhausted or fixed reservation collides");
        ids.Add(key, value);
        NextId = Math.Max(NextId, value + 1);
        return value;
    }

    private static string Hash(string file)
    {
        using var stream = File.OpenRead(file);
        return Convert.ToHexString(SHA256.HashData(stream));
    }

    private Dictionary<string, string?> Snapshot(Func<string, string> resolve) => outputs.Order(StringComparer.Ordinal).ToDictionary(n => n, n =>
    {
        string file = resolve(n);
        if (Directory.Exists(file) || new FileInfo(file).LinkTarget != null)
            throw new IOException("unproven identity output path");
        return File.Exists(file) ? Hash(file) : null;
    });
    private static bool SameSnapshot(Dictionary<string, string?> a, Dictionary<string, string?> b)
        => a.Count == b.Count && a.All(kv => b.TryGetValue(kv.Key, out var value) && value == kv.Value);

    public void PersistBeforePublication(Func<string, string> stagedPath)
    {
        if (!SameSnapshot(initialOutputs, Snapshot(name => Path.Combine(root, name))))
            throw new IOException("published outputs changed during identity planning");
        // Bootstrap is deliberately strict. Never infer old IDs from changed/reordered inputs.
        if (bootstrap)
            foreach (string name in outputs)
                if (Hash(Path.Combine(root, name)) != Hash(stagedPath(name)))
                    throw new InvalidDataException($"bootstrap output differs from published baseline: {name}");
        var prepared = Snapshot(stagedPath);
        if (prepared.Any(kv => kv.Value == null)) throw new IOException("identity publication requires all staged outputs");
        // A failed publication may restore the old complete bundle. Both snapshots retain the same reservations.
        acceptedOutputs = SameSnapshot(initialOutputs, prepared) ? new[] { prepared } : new[] { initialOutputs, prepared };
        var bytes = JsonSerializer.SerializeToUtf8Bytes(new
        {
            format = 1, plugin,
            reservations = ids.OrderBy(kv => kv.Value).ToDictionary(kv => kv.Key, kv => kv.Value),
            accepted_outputs = acceptedOutputs,
            checksum = Checksum()
        }, new JsonSerializerOptions { WriteIndented = true });
        CheckPath();
        if (original == null ? File.Exists(path) : !File.Exists(path) || !File.ReadAllBytes(path).SequenceEqual(original))
            throw new IOException("identity ledger changed during build; refusing overwrite");
        if (original != null && original.SequenceEqual(bytes)) return;
        string temporary = Path.Combine(root, $".terrain-ids-{Guid.NewGuid():N}.pending");
        // Failure retains the pending file and original ledger for diagnosis.
        using (var stream = new FileStream(temporary, FileMode.CreateNew, FileAccess.Write, FileShare.None))
        {
            stream.Write(bytes); stream.Flush(true);
        }
        File.Move(temporary, path, overwrite: original != null);
        if (!File.ReadAllBytes(path).SequenceEqual(bytes)) throw new IOException("identity ledger readback mismatch");
    }
}
