using System.Diagnostics;
using System.Text.Json;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;

public static class NativeDoorBaseTests
{
    public static void Run()
    {
        var root = Environment.GetEnvironmentVariable("FO4SF_NATIVE_DOOR_EVIDENCE")
            ?? Path.Combine(Path.GetTempPath(), "fo4sf-native-doors-" + Guid.NewGuid().ToString("N"));
        if (Directory.Exists(root)) throw new InvalidOperationException("use a new native-door evidence folder");
        Directory.CreateDirectory(root);
        // Synthetic plugins are retained, including failures, for independent readback.
        Console.WriteLine("Native door evidence: " + root);
        var failures = new List<string>();
        foreach (var scenario in new[] { "native", "no-markers", "missing", "static", "deleted", "local-deleted", "local-static", "local-door" })
        {
            try { Check(root, scenario); }
            catch (Exception e) { failures.Add(scenario + ": " + e.Message); }
        }
        if (failures.Count != 0) throw new InvalidOperationException(string.Join("\n", failures));
        Console.WriteLine("8 native-door CLI/serialized identity controls passed.");
    }

    private static void Check(string root, string scenario)
    {
        void Require(bool ok, string reason) { if (!ok) throw new InvalidOperationException(reason); }
        var folder = Path.Combine(root, scenario);
        Directory.CreateDirectory(folder);
        var sf = ModKey.FromNameAndExtension("Starfield.esm");
        var mk = ModKey.FromNameAndExtension("Synthetic.esm");
        var nativeKey = new FormKey(sf, 0x900);
        var vanilla = new StarfieldMod(sf, StarfieldRelease.Starfield);
        if (scenario == "static") vanilla.Statics.Add(new Static(nativeKey, StarfieldRelease.Starfield));
        else if (scenario != "missing")
        {
            var door = new Door(nativeKey, StarfieldRelease.Starfield) { EditorID = "SyntheticNativeDoor" };
            if (scenario is "deleted" or "local-door") door.MajorRecordFlagsRaw |= 0x20;
            vanilla.Doors.Add(door);
        }
        vanilla.BeginWrite.ToPath(Path.Combine(folder, "Starfield.esm")).WithNoLoadOrder().Write();
        var mod = new StarfieldMod(mk, StarfieldRelease.Starfield);
        if (scenario == "local-static") mod.Statics.Add(new Static(nativeKey, StarfieldRelease.Starfield));
        if (scenario is "local-door" or "local-deleted")
        {
            var door = new Door(nativeKey, StarfieldRelease.Starfield);
            if (scenario == "local-deleted") door.MajorRecordFlagsRaw |= 0x20;
            mod.Doors.Add(door);
        }
        var ids = new Dictionary<string, uint>();
        var exports = new List<string>();
        for (int i = 0; i < 2; i++)
        {
            string name = i == 0 ? "First" : "Second", source = i == 0 ? "a" : "b", other = i == 0 ? "b" : "a";
            uint cellId = 0x800u + (uint)i, refId = 0x810u + (uint)i;
            var cell = new Cell(new FormKey(mk, cellId), StarfieldRelease.Starfield)
                { EditorID = "FO4Port_" + name, Flags = Cell.Flag.IsInteriorCell };
            var placed = new PlacedObject(new FormKey(mk, refId), StarfieldRelease.Starfield)
                { Position = new Noggog.P3Float(i + 1, 2, 3), Rotation = new Noggog.P3Float(0, 0, .5f), Scale = .75f };
            placed.Base.SetTo(nativeKey);
            cell.Temporary.Add(placed);
            var block = new CellBlock { BlockNumber = (int)(cellId % 10), GroupType = GroupTypeEnum.InteriorCellBlock };
            var sub = new CellSubBlock { BlockNumber = (int)((cellId / 10) % 10), GroupType = GroupTypeEnum.InteriorCellSubBlock };
            sub.Cells.Add(cell); block.SubBlocks.Add(sub); mod.Cells.Records.Add(block);
            ids["CELL:FO4Port_" + name] = cellId;
            ids[$"REFR:FO4Port_{name}:{source}"] = refId;
            var path = Path.Combine(folder, name + ".json");
            File.WriteAllText(path, JsonSerializer.Serialize(new
            {
                cell = name, formkey = source + "-cell",
                refs = new[] { new { formkey = source, persistent = true, open_by_default = i == 0,
                    teleport_destination = new { door = other, transition_interior = other + "-cell", flags = 2,
                        pos = new[] { 70, 140, 210 }, rot = new[] { 0, 0, 1 } } } }
            }));
            exports.Add(path);
        }
        var input = Path.Combine(folder, "Synthetic.esm");
        mod.BeginWrite.ToPath(input).WithLoadOrder(sf).WithKnownMasters(new KeyedMasterStyle(sf, MasterStyle.Full)).Write();
        var inputBytes = File.ReadAllBytes(input);
        var vanillaBytes = File.ReadAllBytes(Path.Combine(folder, "Starfield.esm"));
        var map = Path.Combine(folder, "formids.json");
        File.WriteAllText(map, JsonSerializer.Serialize(ids));
        var output = Path.Combine(folder, "out");
        var start = new ProcessStartInfo("dotnet") { RedirectStandardOutput = true, RedirectStandardError = true, UseShellExecute = false };
        start.ArgumentList.Add(typeof(Relationships).Assembly.Location);
        foreach (var arg in new[] { input, map, output }.Concat(exports)) start.ArgumentList.Add(arg);
        if (scenario == "no-markers") start.ArgumentList.Add("--no-markers");
        start.Environment["STARFIELD_DATA"] = folder;
        using var process = Process.Start(start)!;
        var stdout = process.StandardOutput.ReadToEndAsync();
        var stderr = process.StandardError.ReadToEndAsync();
        if (!process.WaitForExit(60000)) { process.Kill(entireProcessTree: true); throw new TimeoutException("synthetic CLI timed out"); }
        Task.WaitAll(stdout, stderr);
        File.WriteAllText(Path.Combine(folder, "cli.log"), stdout.Result + stderr.Result);
        File.WriteAllText(Path.Combine(folder, "exit.txt"), process.ExitCode.ToString());
        Require(File.ReadAllBytes(input).SequenceEqual(inputBytes), "input plugin changed");
        Require(File.ReadAllBytes(Path.Combine(folder, "Starfield.esm")).SequenceEqual(vanillaBytes), "master changed");
        bool success = scenario is "native" or "no-markers" or "local-door";
        Require(process.ExitCode == (success ? 0 : 2), $"CLI exit {process.ExitCode}, expected {(success ? 0 : 2)}");
        using var report = JsonDocument.Parse(File.ReadAllText(Path.Combine(output, "relationships-report.json")));
        Require(report.RootElement.GetProperty("Teleports").GetInt32() == (success ? 2 : 0), "unexpected teleport count");
        var issues = report.RootElement.GetProperty("Issues").EnumerateArray().ToArray();
        Require(issues.Length == (success ? 0 : 3), "unexpected unresolved relationship count");
        if (!success)
        {
            Require(issues.Count(i => i.GetProperty("Field").GetString() == "teleport_destination") == 2 &&
                issues.Count(i => i.GetProperty("Field").GetString() == "open_by_default") == 1,
                "rejection was not the expected typed door-base failure");
            Require(!File.Exists(Path.Combine(output, "Synthetic.esm")), "unresolved door published a plugin");
            return;
        }
        var savedIds = JsonSerializer.Deserialize<Dictionary<string, uint>>(File.ReadAllText(Path.Combine(output, "formids.json")))!;
        Require(ids.Count == savedIds.Count && ids.All(p => savedIds[p.Key] == p.Value), "source identities changed");
        var read = PluginReader.Read(Path.Combine(output, "Synthetic.esm"));
        var cells = read.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells).ToList();
        Require(cells.Count == 2 && cells.All(c => c.Temporary.Count == 0 && c.Persistent.Count == 1), "persistent grouping lost");
        foreach (var cell in cells)
        {
            var obj = cell.Persistent.OfType<IPlacedObjectGetter>().Single();
            var i = obj.FormKey.ID == 0x810 ? 0 : 1;
            Require(obj.FormKey.ID == 0x810 + i && cell.FormKey.ID == 0x800 + i, "endpoint identity or parent changed");
            Require((obj.MajorRecordFlagsRaw & 0x400) != 0 && obj.Base.FormKey == nativeKey, "persistent flag or native base lost");
            Require(obj.Position.X == i + 1 && obj.Rotation.Z == .5f && obj.Scale == .75f, "source transform changed");
            var xtel = obj.TeleportDestination!;
            Require(xtel.Door.FormKey == new FormKey(mk, (uint)(0x811 - i)), "reciprocal door link changed");
            Require(xtel.TransitionInterior.FormKey == new FormKey(mk, (uint)(0x801 - i)), "transition cell link changed");
            Require(xtel.Position == new Noggog.P3Float(1, 2, 3) && xtel.Rotation.Z == 1 && (uint)xtel.Flags == 2, "arrival units/rotation/flags lost");
            Require(obj.OpenByDefault == (i == 0), "open state changed");
        }
        Require(read.Doors.Count == (scenario == "local-door" ? 1 : 0), "native DOOR was cloned or reallocated");
    }
}
