using System.Buffers.Binary;
using System.Text.Json;
using Mutagen.Bethesda.Fallout4;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Records;

public static class ActivationParentTests
{
    public static void Run()
    {
        static void Require(bool ok, string message)
        {
            if (!ok) throw new InvalidOperationException(message);
        }
        var own = ModKey.FromNameAndExtension("ActivationSynthetic.esm");
        var other = ModKey.FromNameAndExtension("OtherSynthetic.esm");
        var key = new FormKey(own, 0x801);
        var source = new PlacedObject(key, Fallout4Release.Fallout4)
        {
            ActivateParents = new ActivateParents { Flags = (ActivateParents.Flag)0x81 },
        };
        var a = new ActivateParent { Delay = 0.1f };
        a.Reference.SetTo(new FormKey(own, 0x803));
        var b = new ActivateParent { Delay = 0.0f };
        b.Reference.SetTo(new FormKey(other, 0x803));
        source.ActivateParents.Parents.Add(a);
        source.ActivateParents.Parents.Add(b);
        source.ActivateParents.Parents.Add(new ActivateParent { Delay = 1.25f }); // Null is retained, not guessed.

        static JsonElement Export(IPlacedObjectGetter r) => JsonSerializer.SerializeToElement(
            ReferenceExport.Build(r, "Activator", "SyntheticGarage", "synthetic.nif", false));
        void Check(JsonElement json)
        {
            var block = json.GetProperty("activate_parents");
            Require(block.GetProperty("flags").GetUInt32() == 0x81, "activation flags lost/masked");
            var parents = block.GetProperty("parents");
            Require(parents.GetArrayLength() == 3, "activation parent order/count changed");
            Require(parents[0].GetProperty("reference").GetString() == a.Reference.FormKey.ToString(), "first parent identity lost");
            Require(parents[1].GetProperty("reference").GetString() == b.Reference.FormKey.ToString(), "cross-plugin parent identity collapsed");
            Require(BitConverter.SingleToInt32Bits(parents[0].GetProperty("delay").GetSingle()) == 0x3DCCCCCD,
                    "activation delay did not retain its float32 value");
            Require(parents[1].GetProperty("delay").GetSingle() == 0, "zero activation delay changed");
            Require(parents[2].GetProperty("reference").ValueKind == JsonValueKind.Null &&
                    parents[2].GetProperty("delay").GetSingle() == 1.25f, "null activation parent lost/invented");
        }
        Check(Export(source));
        var empty = new PlacedObject(new FormKey(own, 0x802), Fallout4Release.Fallout4);
        Require(Export(empty).GetProperty("activate_parents").ValueKind == JsonValueKind.Null, "absent activation block invented");
        empty.ActivateParents = new ActivateParents();
        Require(Export(empty).GetProperty("activate_parents").GetProperty("parents").GetArrayLength() == 0,
                "explicit empty activation block collapsed");
        var actor = new PlacedNpc(new FormKey(own, 0x804), Fallout4Release.Fallout4);
        Require(JsonSerializer.SerializeToElement(ReferenceExport.BuildActor(actor, false))
            .GetProperty("activate_parents").ValueKind == JsonValueKind.Null, "absent actor activation block invented");
        actor.ActivateParents = source.ActivateParents;
        Check(JsonSerializer.SerializeToElement(ReferenceExport.BuildActor(actor, false)));

        // Exercise the production binary-overlay getter, not just the mutable object.
        var mod = new Fallout4Mod(own, Fallout4Release.Fallout4);
        var cell = new Cell(new FormKey(own, 0x800), Fallout4Release.Fallout4) { Flags = Cell.Flag.IsInteriorCell };
        cell.Temporary.Add(source);
        var sub = new CellSubBlock { BlockNumber = 0, GroupType = GroupTypeEnum.InteriorCellSubBlock };
        var group = new CellBlock { BlockNumber = 0, GroupType = GroupTypeEnum.InteriorCellBlock };
        sub.Cells.Add(cell); group.SubBlocks.Add(sub); mod.Cells.Records.Add(group);
        var evidence = Environment.GetEnvironmentVariable("FO4SF_EXPORT_EVIDENCE_DIR");
        var directory = Path.Combine(evidence ?? Path.GetTempPath(), "activation-parent-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(directory);
        var path = Path.Combine(directory, own.FileName.String);
        try
        {
            mod.BeginWrite.ToPath(path).WithLoadOrder(other).WithDataFolder(directory).Write();
            using (var loaded = Fallout4Mod.CreateFromBinaryOverlay(path, Fallout4Release.Fallout4))
            {
                var placed = loaded.Cells.Records.SelectMany(g => g.SubBlocks).SelectMany(s => s.Cells)
                    .SelectMany(c => c.Temporary).OfType<IPlacedObjectGetter>().Single();
                Check(Export(placed));
            }
            var raw = Record(File.ReadAllBytes(path), key.ID);
            var fields = new List<(string Type, byte[] Data)>();
            for (int i = 0; i < raw.Length;)
            {
                var size = BinaryPrimitives.ReadUInt16LittleEndian(raw.AsSpan(i + 4));
                fields.Add((System.Text.Encoding.ASCII.GetString(raw, i, 4), raw.AsSpan(i + 6, size).ToArray()));
                i += size + 6;
            }
            Require(fields.Single(f => f.Type == "XAPD").Data.SequenceEqual(new byte[] { 0x81 }), "XAPD flag bytes differ");
            var rows = fields.Where(f => f.Type == "XAPR").Select(f => f.Data).ToArray();
            Require(rows.Length == 3 && rows.All(r => r.Length == 8), "XAPR record framing differs");
            Require(BinaryPrimitives.ReadUInt32LittleEndian(rows[0]) == 0x01000803 &&
                    BinaryPrimitives.ReadUInt32LittleEndian(rows[1]) == 0x00000803 &&
                    BinaryPrimitives.ReadUInt32LittleEndian(rows[2]) == 0, "serialized parent load-order identities differ");
            Require(BinaryPrimitives.ReadInt32LittleEndian(rows[0].AsSpan(4)) == 0x3DCCCCCD, "XAPR delay bytes differ");
        }
        finally
        {
            if (evidence == null) { if (File.Exists(path)) File.Delete(path); Directory.Delete(directory); }
        }
        Console.WriteLine("Activation parents: mutable/overlay/deferred actor, identities, flags and raw XAPR/XAPD checks passed.");
    }

    private static byte[] Record(byte[] data, uint id)
    {
        byte[]? Walk(int start, int end)
        {
            for (int p = start; p < end;)
            {
                int size = checked((int)BinaryPrimitives.ReadUInt32LittleEndian(data.AsSpan(p + 4)));
                if (data.AsSpan(p, 4).SequenceEqual("GRUP"u8))
                {
                    var result = Walk(p + 24, p + size);
                    if (result != null) return result;
                    p += size;
                }
                else
                {
                    if ((BinaryPrimitives.ReadUInt32LittleEndian(data.AsSpan(p + 12)) & 0xFFFFFF) == id)
                        return data.AsSpan(p + 24, size).ToArray();
                    p += size + 24;
                }
            }
            return null;
        }
        return Walk(0, data.Length) ?? throw new InvalidOperationException("synthetic reference absent from binary");
    }
}
