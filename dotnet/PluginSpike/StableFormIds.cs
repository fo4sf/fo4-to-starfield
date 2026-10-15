using System.Text.Json;

/// <summary>Persist single-writer ID reservations before a plugin can publish them.</summary>
public static class StableFormIds
{
    public static void Save(string path, IReadOnlyDictionary<string, uint> ids)
    {
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
