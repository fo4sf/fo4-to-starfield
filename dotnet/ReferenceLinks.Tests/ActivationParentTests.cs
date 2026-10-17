using System.Diagnostics;
using System.Text.Json;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;

public static class ActivationParentTests
{
    public static void Run()
    {
        var root = Environment.GetEnvironmentVariable("FO4SF_ACTIVATION_EVIDENCE")
            ?? Path.Combine(Path.GetTempPath(), "fo4sf-activation-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        var failures = new List<string>();
        var cases = new[] { "default", "strict", "strict-allow", "report", "strict-report", "null", "empty", "missing-parent" };
        foreach (var name in cases)
            try { Check(root, name); } catch (Exception e) { failures.Add(name + ": " + e.Message); }
        if (failures.Count != 0) throw new InvalidOperationException(string.Join("\n", failures));
        Console.WriteLine(cases.Length + " activation-parent CLI controls passed; evidence: " + root);
    }

    static void Check(string root, string name)
    {
        void Need(bool ok, string why) { if (!ok) throw new InvalidOperationException(why); }
        var dir = Path.Combine(root, name);
        if (Directory.Exists(dir)) throw new InvalidOperationException("fresh evidence required");
        Directory.CreateDirectory(dir);
        var sf = ModKey.FromNameAndExtension("Starfield.esm");
        var mk = ModKey.FromNameAndExtension("Synthetic.esm");
        var vanilla = new StarfieldMod(sf, StarfieldRelease.Starfield);
        vanilla.BeginWrite.ToPath(Path.Combine(dir, sf.FileName)).WithNoLoadOrder().Write();
        var mod = new StarfieldMod(mk, StarfieldRelease.Starfield);
        var cell = new Cell(new FormKey(mk, 0x800), StarfieldRelease.Starfield)
            { EditorID = "FO4Port_Test", Flags = Cell.Flag.IsInteriorCell };
        var sub = new CellSubBlock { BlockNumber = 4, GroupType = GroupTypeEnum.InteriorCellSubBlock };
        var block = new CellBlock { BlockNumber = 8, GroupType = GroupTypeEnum.InteriorCellBlock };
        sub.Cells.Add(cell); block.SubBlocks.Add(sub); mod.Cells.Records.Add(block);
        var baseKey = new FormKey(mk, 0x900);
        mod.Statics.Add(new Static(baseKey, StarfieldRelease.Starfield));
        var placed = new PlacedObject(new FormKey(mk, 0x810), StarfieldRelease.Starfield);
        placed.Base.SetTo(baseKey); cell.Temporary.Add(placed);
        var input = Path.Combine(dir, mk.FileName);
        mod.BeginWrite.ToPath(input).WithNoLoadOrder().Write();
        var original = File.ReadAllBytes(input);
        var ids = Path.Combine(dir, "formids.json");
        var idText = "{\"CELL:FO4Port_Test\":2048,\"REFR:FO4Port_Test:child\":2064}";
        File.WriteAllText(ids, idText);
        var source = Path.Combine(dir, "cell.json");
        var activation = name == "null" ? "null" : name == "empty" ? "{\"flags\":0,\"parents\":[]}"
            : "{\"flags\":129,\"parents\":[{\"reference\":\"parent\",\"delay\":0.1}]}";
        var enable = name == "missing-parent" ? ",\"enable_parent\":{\"reference\":\"missing\",\"flags\":0}" : "";
        var sourceText = "{\"cell\":\"Test\",\"refs\":[{\"formkey\":\"child\",\"activate_parents\":" + activation + enable + "}]}";
        File.WriteAllText(source, sourceText);
        var output = Path.Combine(dir, "out");
        var start = new ProcessStartInfo("dotnet") { RedirectStandardOutput = true, RedirectStandardError = true, UseShellExecute = false };
        foreach (var arg in new[] { typeof(Relationships).Assembly.Location, input, ids, output, source, "--no-markers" }) start.ArgumentList.Add(arg);
        if (name.StartsWith("strict")) start.ArgumentList.Add("--strict-activation-parents");
        if (name == "strict-allow") start.ArgumentList.Add("--allow-unresolved");
        if (name.EndsWith("report")) start.ArgumentList.Add("--report-only");
        start.Environment["STARFIELD_DATA"] = dir;
        using var child = Process.Start(start)!;
        var stdout = child.StandardOutput.ReadToEndAsync(); var stderr = child.StandardError.ReadToEndAsync();
        if (!child.WaitForExit(60000)) { child.Kill(true); throw new TimeoutException(); }
        Task.WaitAll(stdout, stderr);
        File.WriteAllText(Path.Combine(dir, "run.log"), stdout.Result + stderr.Result);
        var refused = name is "strict" or "strict-report" or "missing-parent";
        Need(child.ExitCode == (refused ? 2 : 0), "unexpected exit " + child.ExitCode);
        var written = !refused && !name.EndsWith("report");
        Need(File.Exists(Path.Combine(output, mk.FileName)) == written, "publication gate wrong");
        Need(File.Exists(Path.Combine(output, "formids.json")) == written, "identity publication gate wrong");
        Need(File.ReadAllBytes(input).SequenceEqual(original) && File.ReadAllText(ids) == idText && File.ReadAllText(source) == sourceText, "input mutated");
        using var report = JsonDocument.Parse(File.ReadAllText(Path.Combine(output, "relationships-report.json")));
        var warnings = report.RootElement.GetProperty("Warnings").EnumerateArray().ToArray();
        Need(warnings.Length == (name == "null" ? 0 : 1), "warning count wrong");
        if (warnings.Length != 0)
        {
            Need(warnings[0].GetProperty("Source").GetString() == "child" && warnings[0].GetProperty("Field").GetString() == "activate_parents", "warning attribution lost");
            Need(stderr.Result.Contains("warning: child activate_parents:"), "warning not visible in stderr");
        }
        Need(report.RootElement.GetProperty("Issues").GetArrayLength() == (name == "missing-parent" ? 1 : 0), "blocking issue classification wrong");
        using var state = JsonDocument.Parse(File.ReadAllText(Path.Combine(output, "build-state.json")));
        Need(state.RootElement.GetProperty("complete").GetBoolean() == written, "completion flag wrong");
        Need(state.RootElement.GetProperty("unresolved").GetInt32() == warnings.Length + (name == "missing-parent" ? 1 : 0), "unresolved count hides warnings");
        Need(stdout.Result.Contains("warnings=" + warnings.Length), "console omitted warning count");
        if (!written) return;
        Need(File.ReadAllText(Path.Combine(output, "formids.json")).Replace(" ", "").Replace("\r", "").Replace("\n", "") == idText, "output identities changed");
        Need(state.RootElement.GetProperty("fidelity").GetString() == (name == "null" ? "resolved_exported_relationships" : name == "strict-allow" ? "partial_explicitly_allowed" : "partial_with_warnings"), "unsupported behavior claimed resolved");
        var read = PluginReader.Read(Path.Combine(output, mk.FileName));
        var actual = read.Cells.Records.Single().SubBlocks.Single().Cells.Single().Temporary.OfType<IPlacedObjectGetter>().Single();
        Need(actual.FormKey == placed.FormKey && actual.Base.FormKey == baseKey && actual.EnableParent == null && actual.LinkedReferences.Count == 0, "warning invented target behavior");
    }
}
