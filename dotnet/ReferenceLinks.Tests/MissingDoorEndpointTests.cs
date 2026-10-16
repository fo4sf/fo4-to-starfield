using System.Diagnostics;
using System.Text.Json;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;

public static class MissingDoorEndpointTests
{
    public static void Run(bool cellsOnly = false)
    {
        var root = Environment.GetEnvironmentVariable("FO4SF_MISSING_DOOR_EVIDENCE")
            ?? Path.Combine(Path.GetTempPath(), "fo4sf-missing-doors-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        var failures = new List<string>();
        var cellScenarios = new[] { "missing-map-strict", "missing-map-partial", "missing-record-strict",
            "missing-record-partial", "missing-map-report", "unselected-missing-partial" };
        var scenarios = cellsOnly ? cellScenarios : new[] { "allocated", "reserved", "static-base", "wrong-type",
            "occupied", "invalid-scale", "unknown-source" }.Concat(cellScenarios).ToArray();
        foreach (var scenario in scenarios)
        {
            try { Check(root, scenario); }
            catch (Exception e) { failures.Add(scenario + ": " + e.Message); }
        }
        if (failures.Count != 0) throw new InvalidOperationException(string.Join("\n", failures));
        Console.WriteLine(scenarios.Length + " missing-door CLI controls passed; evidence: " + root);
    }

    static void Check(string root, string scenario)
    {
        void Need(bool ok, string why) { if (!ok) throw new InvalidOperationException(why); }
        var folder = Path.Combine(root, scenario);
        if (Directory.Exists(folder)) throw new InvalidOperationException("fresh evidence required");
        Directory.CreateDirectory(folder);
        var sf = ModKey.FromNameAndExtension("Starfield.esm");
        var mk = ModKey.FromNameAndExtension("Synthetic.esm");
        var baseKey = new FormKey(sf, 0x900);
        var vanilla = new StarfieldMod(sf, StarfieldRelease.Starfield);
        if (scenario == "static-base") vanilla.Statics.Add(new Static(baseKey, StarfieldRelease.Starfield));
        else vanilla.Doors.Add(new Door(baseKey, StarfieldRelease.Starfield));
        vanilla.BeginWrite.ToPath(Path.Combine(folder, "Starfield.esm")).WithNoLoadOrder().Write();
        var mod = new StarfieldMod(mk, StarfieldRelease.Starfield);
        var cell = new Cell(new FormKey(mk, 0x800), StarfieldRelease.Starfield)
            { EditorID = "FO4Port_Cave", Flags = Cell.Flag.IsInteriorCell };
        var sub = new CellSubBlock { BlockNumber = 4, GroupType = GroupTypeEnum.InteriorCellSubBlock };
        var block = new CellBlock { BlockNumber = 8, GroupType = GroupTypeEnum.InteriorCellBlock };
        sub.Cells.Add(cell); block.SubBlocks.Add(sub); mod.Cells.Records.Add(block);
        var ids = new Dictionary<string, uint> { ["CELL:FO4Port_Cave"] = 0x800 };
        if (scenario.StartsWith("missing-map-")) ids.Clear();
        if (scenario.StartsWith("missing-record-")) sub.Cells.Clear();
        const string source = "05E844:Fallout4.esm";
        const string identity = "REFR:FO4Port_Cave:" + source;
        if (scenario is "reserved" or "occupied") ids[identity] = 0x810;
        if (scenario == "occupied") mod.Statics.Add(new Static(new FormKey(mk, 0x810), StarfieldRelease.Starfield));
        var input = Path.Combine(folder, "Synthetic.esm");
        mod.BeginWrite.ToPath(input).WithLoadOrder(sf).WithKnownMasters(new KeyedMasterStyle(sf, MasterStyle.Full)).Write();
        var original = File.ReadAllBytes(input);
        var map = Path.Combine(folder, "formids.json");
        File.WriteAllText(map, JsonSerializer.Serialize(ids));
        var export = Path.Combine(folder, "cave.json");
        File.WriteAllText(export, JsonSerializer.Serialize(new { cell = "Cave", refs = new[] { new {
            formkey = source, type = scenario == "wrong-type" ? "Static" : "Door",
            pos = new[] { 70, -140, 210 }, rot = new[] { 0f, 0f, .5f },
            scale = scenario == "invalid-scale" ? -1f : .75f, disabled = 1, persistent = false,
            open_by_default = true } } }));
        var mapping = Path.Combine(folder, "door-bases.json");
        File.WriteAllText(mapping, JsonSerializer.Serialize(new Dictionary<string, string> {
            [scenario == "unknown-source" ? "FFFFFF:Fallout4.esm" : source] = baseKey.ToString() }));
        var output = Path.Combine(folder, "out");
        var extraExport = Path.Combine(folder, "unselected.json");
        if (scenario == "unselected-missing-partial")
            File.WriteAllText(extraExport, "{\"cell\":\"UnselectedMissing\",\"refs\":[]}");
        int Run(string from, string idMap, string to)
        {
            var start = new ProcessStartInfo("dotnet") { RedirectStandardOutput = true, RedirectStandardError = true, UseShellExecute = false };
            start.ArgumentList.Add(typeof(Relationships).Assembly.Location);
            foreach (var arg in new[] { from, idMap, to, export, "--door-bases=" + mapping }) start.ArgumentList.Add(arg);
            if (scenario.EndsWith("-partial") || scenario.EndsWith("-report")) start.ArgumentList.Add("--allow-unresolved");
            if (scenario.EndsWith("-report")) start.ArgumentList.Add("--report-only");
            if (scenario == "unselected-missing-partial") start.ArgumentList.Add(extraExport);
            start.Environment["STARFIELD_DATA"] = folder;
            using var child = Process.Start(start)!;
            var stdout = child.StandardOutput.ReadToEndAsync(); var stderr = child.StandardError.ReadToEndAsync();
            if (!child.WaitForExit(60000)) { child.Kill(true); throw new TimeoutException(); }
            Task.WaitAll(stdout, stderr);
            File.WriteAllText(to + ".log", stdout.Result + stderr.Result);
            return child.ExitCode;
        }
        var exit = Run(input, map, output);
        Need(File.ReadAllBytes(input).SequenceEqual(original), "input changed");
        Need(File.ReadAllText(map) == JsonSerializer.Serialize(ids), "input map changed");
        if (scenario is not ("allocated" or "reserved" or "unselected-missing-partial"))
        {
            Need(exit != 0 && !File.Exists(Path.Combine(output, "Synthetic.esm")), "invalid mapping published output");
            Need(!File.Exists(Path.Combine(output, "formids.json")), "invalid mapping published identities");
            return;
        }
        Need(exit == 0, "valid missing door refused: " + exit);
        var saved = JsonSerializer.Deserialize<Dictionary<string, uint>>(File.ReadAllText(Path.Combine(output, "formids.json")))!;
        Need(saved.Count == 2 && saved["CELL:FO4Port_Cave"] == 0x800, "map damaged");
        if (scenario == "reserved") Need(saved[identity] == 0x810, "reservation replaced");
        var read = PluginReader.Read(Path.Combine(output, "Synthetic.esm"));
        var actual = read.Cells.Records.Single().SubBlocks.Single().Cells.Single();
        Need(actual.Temporary.Count == 0 && actual.Persistent.Count == 1, "endpoint not persistent");
        var door = (IPlacedObjectGetter)actual.Persistent.Single();
        Need(door.FormKey.ID == saved[identity] && door.Base.FormKey == baseKey, "identity/base mismatch");
        Need((door.MajorRecordFlagsRaw & 0xC00) == 0xC00 && door.OpenByDefault, "state lost");
        Need(door.Position == new P3Float(1, -2, 3) && door.Rotation.Z == .5f && door.Scale == .75f, "transform lost");
        Need(door.TeleportDestination == null, "invented link");
        if (scenario == "unselected-missing-partial")
        {
            using var report = JsonDocument.Parse(File.ReadAllText(Path.Combine(output, "relationships-report.json")));
            Need(report.RootElement.GetProperty("CreatedDoors").GetInt32() == 1, "selected door omitted");
            var issue = report.RootElement.GetProperty("Issues").EnumerateArray().Single();
            Need(issue.GetProperty("Source").GetString() == "FO4Port_UnselectedMissing", "unrelated unresolved cell hidden");
        }
        var repeat = Path.Combine(folder, "repeat");
        Need(Run(Path.Combine(output, "Synthetic.esm"), Path.Combine(output, "formids.json"), repeat) == 0, "repeat refused");
        Need(File.ReadAllText(Path.Combine(output, "formids.json")) == File.ReadAllText(Path.Combine(repeat, "formids.json")), "repeat IDs changed");
        Need(PluginReader.Read(Path.Combine(repeat, "Synthetic.esm")).Cells.Records.Single().SubBlocks.Single().Cells.Single().Persistent.Count == 1, "duplicate endpoint");
    }
}
