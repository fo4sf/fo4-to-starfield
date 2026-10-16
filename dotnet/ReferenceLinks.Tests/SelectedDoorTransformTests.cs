using System.Diagnostics;
using System.Text.Json;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;

public static class SelectedDoorTransformTests
{
    public static void Run()
    {
        var root = Environment.GetEnvironmentVariable("FO4SF_TRANSFORM_EVIDENCE")
            ?? Path.Combine(Path.GetTempPath(), "fo4sf-selected-transform-" + Guid.NewGuid().ToString("N"));
        var failures = new List<string>();
        var cases = new[] { "same", "default-scale", "roundoff", "position", "rotation", "scale",
            "nonfinite-target", "invalid-target-scale", "invalid-source", "position-partial", "position-report",
            "rotation-partial", "scale-report" };
        foreach (var name in cases)
        {
            try { Check(Path.Combine(root, name), name); }
            catch (Exception error) { failures.Add(name + ": " + error.Message); }
        }
        if (failures.Count != 0) throw new InvalidOperationException(string.Join("\n", failures));
        Console.WriteLine(cases.Length + " selected-door transform CLI controls passed; evidence: " + root);
    }

    static void Check(string folder, string name)
    {
        void Need(bool ok, string why) { if (!ok) throw new InvalidOperationException(why); }
        Need(!Directory.Exists(folder), "fresh evidence required"); Directory.CreateDirectory(folder);
        var sf = ModKey.FromNameAndExtension("Starfield.esm"); var port = ModKey.FromNameAndExtension("Synthetic.esm");
        var native = new StarfieldMod(sf, StarfieldRelease.Starfield); var doorBase = new FormKey(sf, 0x900);
        native.Doors.Add(new Door(doorBase, StarfieldRelease.Starfield));
        native.BeginWrite.ToPath(Path.Combine(folder, "Starfield.esm")).WithNoLoadOrder().Write();
        var mod = new StarfieldMod(port, StarfieldRelease.Starfield);
        var cell = new Cell(new FormKey(port, 0x800), StarfieldRelease.Starfield)
            { EditorID = "FO4Port_Cave", Flags = Cell.Flag.IsInteriorCell };
        var door = new PlacedObject(new FormKey(port, 0x810), StarfieldRelease.Starfield)
            { Position = new P3Float(1, -2, 3), Rotation = new P3Float(0, 0, .5f), Scale = .75f,
              MajorRecordFlagsRaw = 0xC00, OpenByDefault = true };
        door.Base.SetTo(doorBase);
        if (name.StartsWith("position")) door.Position = new P3Float(10, 10, 10);
        if (name.StartsWith("rotation")) door.Rotation = new P3Float(0, 0, 1.5f);
        if (name.StartsWith("scale")) door.Scale = 2;
        if (name == "nonfinite-target") door.Position = new P3Float(float.NaN, -2, 3);
        if (name == "invalid-target-scale") door.Scale = -1;
        if (name == "default-scale") door.Scale = null;
        if (name == "roundoff")
        { door.Position = new P3Float(1.000001f, -2, 3); door.Rotation = new P3Float(0, 0, .500001f); door.Scale = .750001f; }
        cell.Persistent.Add(door);
        var block = new CellBlock { BlockNumber = 0, GroupType = GroupTypeEnum.InteriorCellBlock };
        var sub = new CellSubBlock { BlockNumber = 0, GroupType = GroupTypeEnum.InteriorCellSubBlock };
        sub.Cells.Add(cell); block.SubBlocks.Add(sub); mod.Cells.Records.Add(block);
        var input = Path.Combine(folder, "Synthetic.esm");
        mod.BeginWrite.ToPath(input).WithLoadOrder(sf).WithKnownMasters(new KeyedMasterStyle(sf, MasterStyle.Full)).Write();
        const string source = "AAAAAA:Fallout4.esm";
        var ids = new Dictionary<string, uint> { ["CELL:FO4Port_Cave"] = 0x800, ["REFR:FO4Port_Cave:" + source] = 0x810 };
        var map = Path.Combine(folder, "formids.json"); File.WriteAllText(map, JsonSerializer.Serialize(ids));
        var export = Path.Combine(folder, "cave.json");
        File.WriteAllText(export, JsonSerializer.Serialize(new { cell = "Cave", refs = new[] { new {
            formkey = source, type = "Door", pos = new[] { 70, -140, 210 }, rot = new[] { 0f, 0f, .5f },
            scale = name == "invalid-source" ? -1f : name == "default-scale" ? 1f : .75f,
            disabled = 1, persistent = true, open_by_default = true } } }));
        var mapping = Path.Combine(folder, "door-bases.json");
        File.WriteAllText(mapping, JsonSerializer.Serialize(new Dictionary<string, string> { [source] = doorBase.ToString() }));
        var originals = new[] { input, map, export, mapping }.ToDictionary(p => p, File.ReadAllBytes);
        int Run(string from, string idMap, string output)
        {
            var start = new ProcessStartInfo("dotnet") { RedirectStandardOutput = true, RedirectStandardError = true, UseShellExecute = false };
            foreach (var arg in new[] { typeof(Relationships).Assembly.Location, from, idMap, output, export, "--door-bases=" + mapping })
                start.ArgumentList.Add(arg);
            if (name.EndsWith("-partial") || name.EndsWith("-report")) start.ArgumentList.Add("--allow-unresolved");
            if (name.EndsWith("-report")) start.ArgumentList.Add("--report-only");
            start.Environment["STARFIELD_DATA"] = folder;
            using var child = Process.Start(start)!;
            var stdout = child.StandardOutput.ReadToEndAsync(); var stderr = child.StandardError.ReadToEndAsync();
            if (!child.WaitForExit(60000)) { child.Kill(true); throw new TimeoutException(); }
            Task.WaitAll(stdout, stderr); File.WriteAllText(output + ".log", stdout.Result + stderr.Result);
            return child.ExitCode;
        }
        var output = Path.Combine(folder, "out"); var exit = Run(input, map, output);
        Need(originals.All(p => File.ReadAllBytes(p.Key).SequenceEqual(p.Value)), "input or identity map changed");
        if (name is not ("same" or "default-scale" or "roundoff"))
        {
            Need(exit != 0, "conflicting transform was accepted");
            Need(!File.Exists(Path.Combine(output, "Synthetic.esm")) && !File.Exists(Path.Combine(output, "formids.json")), "conflict published output");
            Need(File.ReadAllText(output + ".log").Contains("transform", StringComparison.OrdinalIgnoreCase), "refusal did not identify transform conflict");
            return;
        }
        Need(exit == 0, "matching endpoint refused");
        var read = PluginReader.Read(Path.Combine(output, "Synthetic.esm"));
        var actual = (IPlacedObjectGetter)read.Cells.Records.Single().SubBlocks.Single().Cells.Single().Persistent.Single();
        Need(actual.FormKey == door.FormKey && actual.Base.FormKey == doorBase && actual.Position == door.Position
            && actual.Rotation == door.Rotation && actual.Scale == door.Scale, "existing endpoint identity/transform changed");
        Need(actual.MajorRecordFlagsRaw == door.MajorRecordFlagsRaw && actual.OpenByDefault && actual.TeleportDestination == null, "existing state changed");
        var saved = JsonSerializer.Deserialize<Dictionary<string, uint>>(File.ReadAllText(Path.Combine(output, "formids.json")))!;
        Need(ids.Count == saved.Count && ids.All(p => saved[p.Key] == p.Value), "identity map changed");
        using var report = JsonDocument.Parse(File.ReadAllText(Path.Combine(output, "relationships-report.json")));
        Need(report.RootElement.GetProperty("CreatedDoors").GetInt32() == 0, "reused endpoint counted as newly allocated");
        var repeat = Path.Combine(folder, "repeat");
        Need(Run(Path.Combine(output, "Synthetic.esm"), Path.Combine(output, "formids.json"), repeat) == 0, "idempotent reuse refused");
        foreach (var file in new[] { "Synthetic.esm", "formids.json" })
            Need(File.ReadAllBytes(Path.Combine(output, file)).SequenceEqual(File.ReadAllBytes(Path.Combine(repeat, file))), "repeat changed " + file);
    }
}
