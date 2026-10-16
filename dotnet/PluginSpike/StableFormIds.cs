using System.Text.Json;

/// <summary>Persist single-writer ID reservations before a plugin can publish them.</summary>
public static class StableFormIds
{
    public const uint FirstId = 0x800;
    public const uint LastId = 0xFFFFFF;

    public static Dictionary<string, uint> Load(string path)
    {
        if (!File.Exists(path)) return new Dictionary<string, uint>();
        using var document = JsonDocument.Parse(File.ReadAllText(path));
        if (document.RootElement.ValueKind != JsonValueKind.Object)
            throw new InvalidDataException("stable FormID map must be a JSON object");
        var ids = new Dictionary<string, uint>();
        foreach (var entry in document.RootElement.EnumerateObject())
        {
            if (entry.Value.ValueKind != JsonValueKind.Number || !entry.Value.TryGetUInt32(out var id))
                throw new InvalidDataException($"invalid stable FormID for {entry.Name}");
            if (!ids.TryAdd(entry.Name, id))
                throw new InvalidDataException($"duplicate stable identity key {entry.Name}");
        }
        Validate(ids);
        return ids;
    }

    private static void Validate(IReadOnlyDictionary<string, uint> ids)
    {
        var reserved = new HashSet<uint>();
        foreach (var (key, id) in ids)
        {
            if (id < FirstId || id > LastId)
                throw new InvalidDataException($"stable FormID for {key} is outside {FirstId:X6}..{LastId:X6}: {id:X}");
            if (!reserved.Add(id))
                throw new InvalidDataException($"duplicate stable FormID {id:X6} for {key}");
        }
    }

    public static void Save(string path, IReadOnlyDictionary<string, uint> ids)
    {
        Validate(ids);
        path = Path.GetFullPath(path);
        var temporary = Path.Combine(Path.GetDirectoryName(path)!, $".formids-{Guid.NewGuid():N}.pending");
        try
        {
            var bytes = JsonSerializer.SerializeToUtf8Bytes(
                ids.OrderBy(kv => kv.Value).ToDictionary(kv => kv.Key, kv => kv.Value),
                new JsonSerializerOptions { WriteIndented = true });
            using (var stream = new FileStream(temporary, FileMode.CreateNew, FileAccess.Write, FileShare.None))
            {
                stream.Write(bytes);
                stream.Flush(flushToDisk: true);
            }
            File.Move(temporary, path, overwrite: true);
        }
        finally
        {
            if (File.Exists(temporary)) File.Delete(temporary);
        }
    }
}
