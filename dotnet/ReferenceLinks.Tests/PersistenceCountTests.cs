using System.Text.Json;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;

public static class PersistenceCountTests
{
    public static void Run()
    {
        var rows = new List<object>(); var failures = new List<string>();
        foreach (var selected in new[] { false, true })
        foreach (var persistentGroup in new[] { false, true })
        foreach (var persistentFlag in new[] { false, true })
            Check(selected, persistentGroup, persistentFlag, false);
        Check(true, false, false, true);
        var evidence = Environment.GetEnvironmentVariable("FO4SF_PERSISTENCE_EVIDENCE");
        if (evidence != null)
        {
            Directory.CreateDirectory(evidence);
            var path = Path.Combine(evidence, "results.json");
            if (File.Exists(path)) throw new InvalidOperationException("fresh evidence required");
            File.WriteAllText(path, JsonSerializer.Serialize(rows, new JsonSerializerOptions { WriteIndented = true }));
        }
        if (failures.Count != 0) throw new InvalidOperationException(string.Join("\n", failures));
        Console.WriteLine(rows.Count + " persistence-count first/repeat controls passed.");

        void Check(bool selected, bool persistentGroup, bool persistentFlag, bool missing)
        {
            var name = $"selected={selected},group={persistentGroup},flag={persistentFlag},missing={missing}";
            void Need(bool value, string why) { if (!value) failures.Add(name + ": " + why); }
            var key = ModKey.FromNameAndExtension("Synthetic.esm");
            var mod = new StarfieldMod(key, StarfieldRelease.Starfield);
            var baseKey = new FormKey(key, 0x900); mod.Doors.Add(new Door(baseKey, StarfieldRelease.Starfield));
            var cell = new Cell(new FormKey(key, 0x800), StarfieldRelease.Starfield) { EditorID = "FO4Port_Test", Flags = Cell.Flag.IsInteriorCell };
            var block = new CellBlock { BlockNumber = 0, GroupType = GroupTypeEnum.InteriorCellBlock };
            var sub = new CellSubBlock { BlockNumber = 0, GroupType = GroupTypeEnum.InteriorCellSubBlock };
            sub.Cells.Add(cell); block.SubBlocks.Add(sub); mod.Cells.Records.Add(block);
            var door = new PlacedObject(new FormKey(key, 0x810), StarfieldRelease.Starfield) {
                Position = new P3Float(1, 2, 3), Rotation = new P3Float(0, 0, .5f), Scale = .75f,
                MajorRecordFlagsRaw = persistentFlag ? 0xC00 : 0x800 };
            door.Base.SetTo(baseKey);
            if (!missing) { if (persistentGroup) cell.Persistent.Add(door); else cell.Temporary.Add(door); }
            var ids = new Dictionary<string, uint> { ["CELL:FO4Port_Test"] = 0x800, ["REFR:FO4Port_Test:source"] = 0x810 };
            using var export = JsonDocument.Parse("""
{"cell":"Test","refs":[{"formkey":"source","type":"Door","persistent":true,"disabled":1,"pos":[70,140,210],"rot":[0,0,0.5],"scale":0.75}]}
""");
            var selection = selected ? new Dictionary<string, FormKey> { ["source"] = baseKey } : null;
            var first = Relationships.Apply(mod, ids, new[] { export.RootElement }, missingDoorBases: selection);
            var firstRecord = (PlacedObject)cell.Persistent.Single();
            var repeat = Relationships.Apply(mod, ids, new[] { export.RootElement }, missingDoorBases: selection);
            var expected = !missing && persistentGroup && persistentFlag ? 0 : 1;
            rows.Add(new { name, expected, first = first.Persistent, repeat = repeat.Persistent,
                created_first = first.CreatedDoors, created_repeat = repeat.CreatedDoors });
            Need(first.Persistent == expected, $"first count {first.Persistent}, expected {expected}");
            Need(repeat.Persistent == 0, $"unchanged repeat counted {repeat.Persistent}");
            Need(first.CreatedDoors == (missing ? 1 : 0) && repeat.CreatedDoors == 0, "creation count changed");
            Need(cell.Temporary.Count == 0 && cell.Persistent.Count == 1 && ReferenceEquals(firstRecord, cell.Persistent.Single()), "endpoint grouping/instance changed on repeat");
            Need(firstRecord.FormKey == door.FormKey && firstRecord.Base.FormKey == baseKey && firstRecord.Position == door.Position
                && firstRecord.Rotation == door.Rotation && firstRecord.Scale == door.Scale && firstRecord.MajorRecordFlagsRaw == 0xC00, "endpoint identity/state/transform changed");
            Need(ids.Count == 2 && ids["REFR:FO4Port_Test:source"] == 0x810 && first.Issues.Count == 0 && repeat.Issues.Count == 0, "map or relationship result changed");
        }
    }
}
