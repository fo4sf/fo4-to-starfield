// roundtrip: what Mutagen writes back for vanilla NPC_ records, subrecord by subrecord (read-only on the game data;
// the override plugin goes to a scratch folder and is never deployed).
using System.IO.Compression;
using System.Text;
using System.Text.Json;
using Mutagen.Bethesda;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;

static class Roundtrip
{
    /// Raw records of one top-level group: FormID -> decompressed record data (24-byte record headers, a 4-byte
    /// decompressed size before zlib data when flag 0x40000 is set, as in every Bethesda plugin since Skyrim).
    public static Dictionary<uint, byte[]> ReadGroup(string path, string sig, HashSet<uint>? want)
    {
        var outp = new Dictionary<uint, byte[]>();
        using var fs = File.OpenRead(path);
        using var br = new BinaryReader(fs);
        string Sig() => Encoding.ASCII.GetString(br.ReadBytes(4));
        Sig(); var hsize = br.ReadUInt32(); fs.Seek(16 + hsize, SeekOrigin.Current);   // TES4 header record
        while (fs.Position < fs.Length)
        {
            var g = Sig(); var gsize = br.ReadUInt32(); var label = Encoding.ASCII.GetString(br.ReadBytes(4)); fs.Seek(12, SeekOrigin.Current);
            if (g != "GRUP") throw new InvalidDataException($"expected GRUP at {fs.Position - 24}, got {g}");
            long end = fs.Position + gsize - 24;
            if (label != sig) { fs.Seek(end, SeekOrigin.Begin); continue; }
            while (fs.Position < end)
            {
                var t = Sig(); var size = br.ReadUInt32();
                if (t == "GRUP") { fs.Seek(size - 8, SeekOrigin.Current); continue; }
                var flags = br.ReadUInt32(); var id = br.ReadUInt32(); fs.Seek(8, SeekOrigin.Current);
                var data = br.ReadBytes((int)size);
                if (want is not null && !want.Contains(id & 0xFFFFFF)) continue;
                if ((flags & 0x40000) != 0)
                {
                    using var z = new ZLibStream(new MemoryStream(data, 4, data.Length - 4), CompressionMode.Decompress);
                    using var ms = new MemoryStream();
                    z.CopyTo(ms);
                    data = ms.ToArray();
                }
                outp[id & 0xFFFFFF] = data;
            }
        }
        return outp;
    }

    /// The record header form version (offset 20, 2 bytes) of every record of one top-level group: FormID -> version.
    public static Dictionary<uint, ushort> FormVersions(string path, string sig)
    {
        var outp = new Dictionary<uint, ushort>();
        using var fs = File.OpenRead(path);
        using var br = new BinaryReader(fs);
        string Sig() => Encoding.ASCII.GetString(br.ReadBytes(4));
        Sig(); var hsize = br.ReadUInt32(); fs.Seek(16 + hsize, SeekOrigin.Current);
        while (fs.Position < fs.Length)
        {
            var g = Sig(); var gsize = br.ReadUInt32(); var label = Encoding.ASCII.GetString(br.ReadBytes(4)); fs.Seek(12, SeekOrigin.Current);
            if (g != "GRUP") throw new InvalidDataException($"expected GRUP at {fs.Position - 24}, got {g}");
            long end = fs.Position + gsize - 24;
            if (label != sig) { fs.Seek(end, SeekOrigin.Begin); continue; }
            while (fs.Position < end)
            {
                var t = Sig(); var size = br.ReadUInt32();
                if (t == "GRUP") { fs.Seek(size - 8, SeekOrigin.Current); continue; }
                br.ReadUInt32(); var id = br.ReadUInt32(); br.ReadUInt32(); var version = br.ReadUInt16(); br.ReadUInt16();
                fs.Seek(size, SeekOrigin.Current);
                outp[id & 0xFFFFFF] = version;
            }
        }
        return outp;
    }

    public static List<(string Type, byte[] Data)> Subrecords(byte[] d)
    {
        var outp = new List<(string, byte[])>();
        int p = 0; uint big = 0;
        while (p + 6 <= d.Length)
        {
            var type = Encoding.ASCII.GetString(d, p, 4); int size = BitConverter.ToUInt16(d, p + 4); p += 6;
            if (type == "XXXX") { big = BitConverter.ToUInt32(d, p); p += size; continue; }
            if (big > 0) { size = (int)big; big = 0; }
            outp.Add((type, d.AsSpan(p, size).ToArray()));
            p += size;
        }
        return outp;
    }

    public static int Run(string sfPath, uint[] ids, string scratch, string outPath)
    {
        Directory.CreateDirectory(scratch);
        var key = ModKey.FromNameAndExtension("FO4SFNpcRoundtrip.esm");
        var mod = new StarfieldMod(key, StarfieldRelease.Starfield);
        var sfKey = ModKey.FromNameAndExtension("Starfield.esm");
        using (var sf = StarfieldMod.CreateFromBinaryOverlay(sfPath, StarfieldRelease.Starfield))
        {
            var c = Util.Cache(sf);
            foreach (var id in ids)
                mod.Npcs.Add((Npc)c.Resolve<INpcGetter>(new FormKey(sfKey, id & 0xFFFFFF)).DeepCopy());
            var path = Path.Combine(scratch, key.FileName);
            mod.BeginWrite.ToPath(path).WithLoadOrderFromHeaderMasters().WithDataFolder(Path.GetDirectoryName(Path.GetFullPath(sfPath))!)
                .WithKnownMasters(new KeyedMasterStyle(sfKey, MasterStyle.Full)).Write();
        }
        var want = ids.Select(i => i & 0xFFFFFF).ToHashSet();
        var orig = ReadGroup(sfPath, "NPC_", want);
        var back = ReadGroup(Path.Combine(scratch, key.FileName), "NPC_", want);
        var report = new List<object>();
        int bad = 0;
        foreach (var id in want)
        {
            var a = Subrecords(orig[id]); var b = Subrecords(back.GetValueOrDefault(id) ?? Array.Empty<byte>());
            var diffs = new List<string>();
            // align by (type, occurrence): order changes are reported separately from content changes
            var bi = b.Select((s, i) => (s, i)).GroupBy(x => x.s.Type).ToDictionary(g => g.Key, g => g.ToList());
            var seen = new Dictionary<string, int>();
            foreach (var (t, data) in a)
            {
                var k = seen.GetValueOrDefault(t); seen[t] = k + 1;
                if (!bi.TryGetValue(t, out var lst) || k >= lst.Count) { diffs.Add($"{t} ({data.Length} B) missing"); continue; }
                var other = lst[k].s.Data;
                if (!other.AsSpan().SequenceEqual(data)) diffs.Add($"{t} changed ({data.Length} -> {other.Length} B)");
            }
            foreach (var g in bi) if (g.Value.Count > seen.GetValueOrDefault(g.Key)) diffs.Add($"{g.Key} x{g.Value.Count - seen.GetValueOrDefault(g.Key)} added");
            bool order = a.Select(s => s.Type).SequenceEqual(b.Select(s => s.Type));
            if (diffs.Count > 0 || !order) bad++;
            report.Add(new Dictionary<string, object?>
            {
                ["id"] = $"{id:X8}", ["subrecords"] = a.Count, ["written"] = b.Count, ["same_order"] = order,
                ["identical"] = diffs.Count == 0 && order, ["differences"] = diffs,
                ["types"] = string.Join(" ", a.Select(s => s.Type).Distinct()),
            });
            Console.WriteLine($"{id:X8}: {a.Count} subrecords, written {b.Count}, order {(order ? "same" : "differs")}, " +
                              $"{(diffs.Count == 0 ? "bytes identical" : string.Join("; ", diffs))}");
        }
        File.WriteAllText(outPath, JsonSerializer.Serialize(new { records = report, differing = bad }, new JsonSerializerOptions { WriteIndented = true }));
        return 0;
    }
}
