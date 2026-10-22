using System.Text.Json;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Fo4 = Mutagen.Bethesda.Fallout4;

// Door locks (FO4 REFR XLOC, exported as lock_data) on synthetic records: mapped levels, key resolution,
// refusals, non-door bases, repeat application and binary round-trip.
public static class LockTests
{
    public static void Run()
    {
        void Require(bool ok, string message) { if (!ok) throw new InvalidOperationException(message); }
        // Every written level keeps its Fallout 4 enum name in Starfield's enum; every FO4 value is either
        // written or explicitly refused, so a new FO4 value cannot slip through unnoticed.
        foreach (var (value, name) in Relationships.LockLevels)
            Require(Enum.GetName(typeof(Fo4.LockLevel), value) == name && Enum.GetName(typeof(LockLevel), value) == name,
                $"lock level {value} semantics differ between games");
        foreach (var (value, _) in Relationships.RefusedLockLevels)
            Require(Enum.GetName(typeof(Fo4.LockLevel), value) == Enum.GetName(typeof(LockLevel), value), $"refused level {value} renamed");
        foreach (int value in Enum.GetValues(typeof(Fo4.LockLevel)))
            Require(Relationships.LockLevels.ContainsKey(value) ^ Relationships.RefusedLockLevels.ContainsKey(value), $"FO4 lock level {value} unclassified");
        Require(Enum.GetName(typeof(Fo4.LockData.Flag), 1) == Enum.GetName(typeof(LockData.Flag), 1) &&
                Enum.GetValues(typeof(LockData.Flag)).Length == 1, "lock flag semantics differ between games");

        var modKey = ModKey.FromNameAndExtension("Synthetic.esm");
        FormKey Key(uint id) => new(modKey, id);
        var mod = new StarfieldMod(modKey, StarfieldRelease.Starfield);
        var door = new Door(Key(0x900), StarfieldRelease.Starfield);
        var container = new Container(Key(0x901), StarfieldRelease.Starfield);
        var key = new Key(Key(0x950), StarfieldRelease.Starfield) { EditorID = "SyntheticKey" };
        mod.Doors.Add(door); mod.Containers.Add(container); mod.Keys.Add(key);
        var cell = new Cell(Key(0x800), StarfieldRelease.Starfield) { EditorID = "FO4Port_First", Flags = Cell.Flag.IsInteriorCell };
        var ids = new Dictionary<string, uint> { ["CELL:FO4Port_First"] = 0x800, ["KEYM:000123:Fallout4.esm"] = 0x950,
            ["KEYM:000124:Fallout4.esm"] = 0x951 /* reserved, no record */ };
        var names = new[] { "plain", "keyed", "unresolved", "reserved", "terminal", "inaccessible", "odd", "flags", "keyless", "chest" };
        var refs = new Dictionary<string, PlacedObject>();
        for (int i = 0; i < names.Length; i++)
        {
            var placed = new PlacedObject(Key(0x810u + (uint)i), StarfieldRelease.Starfield);
            placed.Base.SetTo(names[i] == "chest" ? container.FormKey : door.FormKey);
            cell.Temporary.Add(placed); refs[names[i]] = placed;
            ids["REFR:FO4Port_First:" + names[i]] = 0x810u + (uint)i;
        }
        var block = new CellBlock { BlockNumber = 0, GroupType = GroupTypeEnum.InteriorCellBlock };
        var sub = new CellSubBlock { BlockNumber = 0, GroupType = GroupTypeEnum.InteriorCellSubBlock };
        sub.Cells.Add(cell); block.SubBlocks.Add(sub); mod.Cells.Records.Add(block);
        using var export = JsonDocument.Parse("""
{"cell":"First","refs":[
 {"formkey":"plain","lock_data":{"level":50,"key":null,"flags":1,"unused":0}},
 {"formkey":"keyed","lock_data":{"level":255,"key":"000123:fallout4.esm","flags":0,"unused":0}},
 {"formkey":"unresolved","lock_data":{"level":25,"key":"000999:Fallout4.esm","flags":0,"unused":0}},
 {"formkey":"reserved","lock_data":{"level":25,"key":"000124:Fallout4.esm","flags":0,"unused":0}},
 {"formkey":"terminal","lock_data":{"level":253,"key":null,"flags":0,"unused":0}},
 {"formkey":"inaccessible","lock_data":{"level":254,"key":null,"flags":0,"unused":0}},
 {"formkey":"odd","lock_data":{"level":30,"key":null,"flags":0,"unused":0}},
 {"formkey":"flags","lock_data":{"level":50,"key":null,"flags":2,"unused":0}},
 {"formkey":"keyless","lock_data":{"level":255,"key":null,"flags":0,"unused":0}},
 {"formkey":"chest","lock_data":{"level":75,"key":null,"flags":0,"unused":0}},
 {"formkey":"unlocked","lock_data":null}]}
""");
        var sources = new[] { export.RootElement };
        var report = Relationships.Apply(mod, ids, sources);
        Require(report.Locks == 2, $"expected 2 locks, got {report.Locks}");
        var plain = refs["plain"].Lock!;
        Require(plain.Level == LockLevel.Advanced && plain.Flags == LockData.Flag.LeveledLock && plain.Key.IsNull, "mapped level/flags lost");
        var keyed = refs["keyed"].Lock!;
        Require(keyed.Level == LockLevel.RequiresKey && keyed.Key.FormKey == key.FormKey,
            "resolved key not written (the export spells it 000123:fallout4.esm, the map KEYM:000123:Fallout4.esm: one FormKey)");
        string[] Fields(IEnumerable<LinkIssue> list, string source) => list.Where(i => i.Source == source).Select(i => i.Field).ToArray();
        Require(Fields(report.Warnings, "unresolved").SequenceEqual(new[] { "lock_data.key" }), "unresolved key not reported");
        Require(Fields(report.Warnings, "reserved").SequenceEqual(new[] { "lock_data.key" }), "reserved key ID alone resolved a key");
        Require(Fields(report.Issues, "odd").SequenceEqual(new[] { "lock_data.level" }), "unmappable level not reported");
        Require(Fields(report.Issues, "flags").SequenceEqual(new[] { "lock_data.flags" }), "unknown flag bits not reported");
        Require(Fields(report.Warnings, "keyless").SequenceEqual(new[] { "lock_data.key" }), "key-only lock without key not reported");
        Require(Fields(report.Warnings, "terminal").SequenceEqual(new[] { "lock_data.level" }) &&
                Fields(report.Warnings, "inaccessible").SequenceEqual(new[] { "lock_data.level" }), "refused levels not warned");
        Require(Fields(report.Warnings, "chest").SequenceEqual(new[] { "lock_data" }), "non-door lock not warned");
        Require(report.Issues.Count == 2 && report.Warnings.Count == 6, $"unexpected report {report.Issues.Count}/{report.Warnings.Count}");
        foreach (var name in new[] { "unresolved", "reserved", "terminal", "inaccessible", "odd", "flags", "keyless", "chest" })
            Require(refs[name].Lock == null, name + " got a guessed lock");
        Require(mod.Keys.Count == 1, "a key record was invented");

        var again = Relationships.Apply(mod, ids, sources);
        Require(again.Locks == 2 && again.Issues.Count == 2 && refs["keyed"].Lock!.Key.FormKey == key.FormKey &&
                refs["plain"].Lock!.Level == LockLevel.Advanced && mod.Keys.Count == 1, "repeat application changed locks");

        var directory = Path.Combine(Path.GetTempPath(), "fo4sf-locks-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(directory);
        try
        {
            var path = Path.Combine(directory, "Synthetic.esm");
            mod.BeginWrite.ToPath(path).WithNoLoadOrder().Write();
            var read = PluginReader.Read(path);
            var written = read.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells).Single()
                .Temporary.OfType<IPlacedObjectGetter>().ToDictionary(r => r.FormKey);
            var readPlain = written[refs["plain"].FormKey].Lock!;
            var readKeyed = written[refs["keyed"].FormKey].Lock!;
            Require(readPlain.Level == LockLevel.Advanced && readPlain.Flags == LockData.Flag.LeveledLock && readPlain.Key.IsNull,
                "plain lock lost in binary output");
            Require(readKeyed.Level == LockLevel.RequiresKey && readKeyed.Key.FormKey == key.FormKey, "keyed lock lost in binary output");
            Require(written[refs["chest"].FormKey].Lock == null && written[refs["terminal"].FormKey].Lock == null,
                "refused lock appeared in binary output");
        }
        finally { Directory.Delete(directory, true); }

        // Codex on #375: two spellings of one source key reserved at different IDs corrupt the map. Apply refuses it before
        // changing anything; Program calls Apply before writing any output, so --allow-unresolved cannot publish it either.
        var other = new Key(Key(0x952), StarfieldRelease.Starfield) { EditorID = "SyntheticKey2" };
        mod.Keys.Add(other);
        var ambiguous = new Dictionary<string, uint>(ids) { ["KEYM:000123:fallout4.esm"] = 0x952 };
        refs["keyed"].Lock = null;
        string? refusal = null;
        try { Relationships.Apply(mod, ambiguous, sources); }
        catch (InvalidOperationException e) { refusal = e.Message; }
        Require(refusal != null && refusal.Contains("two target IDs") && refs["keyed"].Lock == null && refs["plain"].Lock!.Level == LockLevel.Advanced,
            "ambiguous key reservation was not refused before changes: " + refusal);
        foreach (var bad in new[] { "KEYM:not-a-formkey", "KEYM:000000:Null" })
        {
            string? invalid = null;
            try { Relationships.Apply(mod, new Dictionary<string, uint>(ids) { [bad] = 0x953 }, sources); }
            catch (InvalidOperationException e) { invalid = e.Message; }
            Require(invalid != null && invalid.Contains("invalid key identity") && refs["keyed"].Lock == null, bad + " was accepted: " + invalid);
        }
        Console.WriteLine("Door lock translation, refusal and binary round-trip synthetic checks passed.");
    }
}
