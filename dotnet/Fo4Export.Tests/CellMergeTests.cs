// Synthetic checks for CellMerge and the export of a cell a later plugin overrides (docs/CELL-EXPORT.md, "Load order").
// A master holds the cell Factory with the references A, B (temporary) and C (a persistent load door with an XTEL to a
// door in the master's cell Other), plus the cell Untouched; the DLC overrides Factory (a FULL name and an encounter
// zone of its own), re-saves B moved, deletes C (record flag 0x20), adds D, and moves E (a master reference of Factory)
// into its copy of Other. Both plugins are written to a temp folder and read back through the binary overlay, the way
// Fo4Export reads a DLC with --master.
using System.Diagnostics;
using System.Text.Json;
using Mutagen.Bethesda;
using Mutagen.Bethesda.Fallout4;
using Mutagen.Bethesda.Plugins;
using Noggog;

public static class CellMergeTests
{
    static void Require(bool condition, string message)
    {
        if (!condition) throw new InvalidOperationException(message);
    }

    public static void Run()
    {
        var masterKey = ModKey.FromNameAndExtension("MergeMaster.esm");
        var dlcKey = ModKey.FromNameAndExtension("MergeDlc.esm");
        var master = new Fallout4Mod(masterKey, Fallout4Release.Fallout4);
        var door = new Door(new FormKey(masterKey, 0x1100), Fallout4Release.Fallout4) { EditorID = "LoadDoor" };
        var crate = new Static(new FormKey(masterKey, 0x1101), Fallout4Release.Fallout4) { EditorID = "Crate" };
        master.Doors.Add(door); master.Statics.Add(crate);
        PlacedObject Ref(FormKey key, FormKey baseKey, float x)
        {
            var r = new PlacedObject(key, Fallout4Release.Fallout4) { Position = new P3Float(x, 0, 0) };
            r.Base.SetTo(baseKey);
            return r;
        }
        var factory = new Cell(new FormKey(masterKey, 0x1200), Fallout4Release.Fallout4) { EditorID = "Factory", Flags = Cell.Flag.IsInteriorCell, Name = "Factory" };
        var other = new Cell(new FormKey(masterKey, 0x1201), Fallout4Release.Fallout4) { EditorID = "Other", Flags = Cell.Flag.IsInteriorCell };
        var untouched = new Cell(new FormKey(masterKey, 0x1202), Fallout4Release.Fallout4) { EditorID = "Untouched", Flags = Cell.Flag.IsInteriorCell, Name = "Untouched" };
        var a = Ref(new FormKey(masterKey, 0x1301), crate.FormKey, 1);
        var b = Ref(new FormKey(masterKey, 0x1302), crate.FormKey, 2);
        var c = Ref(new FormKey(masterKey, 0x1303), door.FormKey, 3);
        var e = Ref(new FormKey(masterKey, 0x1305), crate.FormKey, 5);
        var otherDoor = Ref(new FormKey(masterKey, 0x1310), door.FormKey, 10);
        c.TeleportDestination = new TeleportDestination(); c.TeleportDestination.Door.SetTo(otherDoor.FormKey);
        otherDoor.TeleportDestination = new TeleportDestination(); otherDoor.TeleportDestination.Door.SetTo(c.FormKey);
        factory.Temporary.Add(a); factory.Temporary.Add(b); factory.Temporary.Add(e); factory.Persistent.Add(c);
        other.Persistent.Add(otherDoor);
        untouched.Temporary.Add(Ref(new FormKey(masterKey, 0x1320), crate.FormKey, 20));
        untouched.Persistent.Add(Ref(new FormKey(masterKey, 0x1321), crate.FormKey, 21));
        var gone = new Cell(new FormKey(masterKey, 0x1203), Fallout4Release.Fallout4) { EditorID = "Gone", Flags = Cell.Flag.IsInteriorCell };
        gone.Temporary.Add(Ref(new FormKey(masterKey, 0x1330), crate.FormKey, 30));
        AddInterior(master, factory, other, untouched, gone);

        var dlc = new Fallout4Mod(dlcKey, Fallout4Release.Fallout4);
        var zone = new EncounterZone(new FormKey(dlcKey, 0x801), Fallout4Release.Fallout4) { EditorID = "DlcFactoryZone", MinLevel = 7, MaxLevel = 9 };
        dlc.EncounterZones.Add(zone);
        var factoryDlc = new Cell(new FormKey(masterKey, 0x1200), Fallout4Release.Fallout4) { EditorID = "Factory", Flags = Cell.Flag.IsInteriorCell, Name = "Factory (DLC)" };
        factoryDlc.EncounterZone.SetTo(zone.FormKey);
        var b2 = Ref(new FormKey(masterKey, 0x1302), crate.FormKey, 22);           // B edited (and made persistent)
        var c2 = new PlacedObject(new FormKey(masterKey, 0x1303), Fallout4Release.Fallout4) { IsDeleted = true };   // C deleted
        var d = Ref(new FormKey(dlcKey, 0x802), crate.FormKey, 4);                 // D added
        factoryDlc.Temporary.Add(c2); factoryDlc.Temporary.Add(d); factoryDlc.Persistent.Add(b2);
        var otherDlc = new Cell(new FormKey(masterKey, 0x1201), Fallout4Release.Fallout4) { EditorID = "Other", Flags = Cell.Flag.IsInteriorCell };
        otherDlc.Temporary.Add(Ref(new FormKey(masterKey, 0x1305), crate.FormKey, 55));   // E moved here from Factory
        var goneDlc = new Cell(new FormKey(masterKey, 0x1203), Fallout4Release.Fallout4) { EditorID = "Gone", Flags = Cell.Flag.IsInteriorCell, IsDeleted = true };
        AddInterior(dlc, factoryDlc, otherDlc, goneDlc);

        var dir = Path.Combine(Path.GetTempPath(), "fo4sf-cell-merge-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(dir);
        var masterPath = Path.Combine(dir, masterKey.FileName.String);
        var dlcPath = Path.Combine(dir, dlcKey.FileName.String);
        master.BeginWrite.ToPath(masterPath).WithNoLoadOrder().WithDataFolder(dir).Write();
        dlc.BeginWrite.ToPath(dlcPath).WithLoadOrder(masterKey).WithDataFolder(dir).Write();

        using var m = Fallout4Mod.CreateFromBinaryOverlay(masterPath, Fallout4Release.Fallout4);
        using var p = Fallout4Mod.CreateFromBinaryOverlay(dlcPath, Fallout4Release.Fallout4);
        var mods = new IFallout4ModGetter[] { m, p };
        var keys = CellMerge.PlacedKeys(mods);
        Require(keys[0].Count == 0 && keys[1].SetEquals(new[] { b.FormKey, c.FormKey, d.FormKey, e.FormKey }), "the later plugin's placed keys are not what it holds");
        var copies = CellMerge.Copies(mods, worldspaces: false);
        Require(copies[factory.FormKey].Count == 2 && copies[untouched.FormKey].Count == 1, "cell copies not counted per plugin");
        Require(!copies.ContainsKey(gone.FormKey) && CellMerge.Copies(new IFallout4ModGetter[] { m }, false).ContainsKey(gone.FormKey),
            "a cell the winning plugin deletes is still listed");

        var merged = CellMerge.Merge(copies[factory.FormKey], keys);
        Require(merged.Cell.Name?.String == "Factory (DLC)" && merged.Cell.EncounterZone.FormKey == zone.FormKey, "the winning CELL record is not the DLC's");
        var got = merged.Children.Select(ch => (ch.Record.FormKey, ((IPlacedObjectGetter)ch.Record).Position.X, ch.Persistent, ch.Source)).ToList();
        Require(got.SequenceEqual(new[] { (a.FormKey, 1f, false, 0), (b.FormKey, 22f, true, 1), (d.FormKey, 4f, false, 1) }),
            "merged children differ: " + string.Join(", ", got));
        var otherMerged = CellMerge.Merge(copies[other.FormKey], keys);
        Require(otherMerged.Children.Select(ch => ch.Record.FormKey).SequenceEqual(new[] { otherDoor.FormKey, e.FormKey }), "the moved reference did not land in its new cell");
        // one plugin: exactly Temporary then Persistent, nothing merged away
        var single = CellMerge.Merge(CellMerge.Copies(new IFallout4ModGetter[] { m }, false)[factory.FormKey], CellMerge.PlacedKeys(new IFallout4ModGetter[] { m }));
        Require(single.Children.Select(ch => (ch.Record.FormKey, ch.Persistent)).SequenceEqual(new[] { (a.FormKey, false), (b.FormKey, false), (e.FormKey, false), (c.FormKey, true) }),
            "a single plugin's merge is not its own lists");
        // the deleted door resolves no teleport dependency; the master's door into it finds no destination any more
        var deps = TeleportDependencies.Build(otherMerged.Records.OfType<IPlacedObjectGetter>(), CellMerge.All(mods, keys, worldspaces: true));
        Require(deps.Single().door == c.FormKey.ToString() && deps.Single().destination_cell == null, "a deleted destination door still resolves");
        var depsMaster = TeleportDependencies.Build(otherMerged.Records.OfType<IPlacedObjectGetter>(), CellMerge.All(new IFallout4ModGetter[] { m }, CellMerge.PlacedKeys(new IFallout4ModGetter[] { m }), true));
        Require(depsMaster.Single().destination_cell?.editor_id == "Factory", "the master alone no longer resolves its own door");
        Console.WriteLine("Cell merge checks passed.");

        // the exporter end to end: the DLC's cell data and encounter zone, the merged refs, no deleted or moved one
        var exe = Path.Combine(AppContext.BaseDirectory, OperatingSystem.IsWindows() ? "Fo4Export.exe" : "Fo4Export");
        Require(File.Exists(exe), "Fo4Export apphost not beside the test binary");
        (int Code, string Err) RunExporter(params string[] arguments)
        {
            var run = Process.Start(new ProcessStartInfo(exe, arguments) { RedirectStandardOutput = true, RedirectStandardError = true })!;
            var err = run.StandardError.ReadToEnd();
            run.StandardOutput.ReadToEnd();
            run.WaitForExit();
            return (run.ExitCode, err);
        }
        var mergedJson = Path.Combine(dir, "Factory.json");
        var run = RunExporter(dlcPath, "--master", masterPath, "export", "Factory", mergedJson);
        Require(run.Code == 0 && File.Exists(mergedJson), "merged export failed: " + run.Err);
        using (var doc = JsonDocument.Parse(File.ReadAllText(mergedJson)))
        {
            var top = doc.RootElement;
            Require(top.GetProperty("formkey").GetString() == factory.FormKey.ToString(), "the override changed the cell's FormKey");
            Require(top.GetProperty("cell_data").GetProperty("name").GetString() == "Factory (DLC)", "cell_data is not the winning record's");
            Require(top.GetProperty("encounter_zone").GetProperty("editor_id").GetString() == "DlcFactoryZone", "the DLC's encounter zone was not exported");
            var refs = top.GetProperty("refs").EnumerateArray().Select(r => (r.GetProperty("formkey").GetString()!, r.GetProperty("pos")[0].GetSingle(), r.GetProperty("persistent").GetBoolean())).ToList();
            Require(refs.SequenceEqual(new[] { (a.FormKey.ToString(), 1f, false), (b.FormKey.ToString(), 22f, true), (d.FormKey.ToString(), 4f, false) }),
                "exported refs differ: " + string.Join(", ", refs));
            Require(top.GetProperty("teleport_dependencies").GetArrayLength() == 0, "the deleted door left a teleport dependency");
        }
        // Other, merged: the moved E is there, and its door's destination (C) is gone with the DLC loaded
        var otherJson = Path.Combine(dir, "Other.json");
        Require(RunExporter(dlcPath, "--master", masterPath, "export", "Other", otherJson).Code == 0, "export of Other failed");
        using (var doc = JsonDocument.Parse(File.ReadAllText(otherJson)))
        {
            var refs = doc.RootElement.GetProperty("refs").EnumerateArray().Select(r => r.GetProperty("formkey").GetString()).ToList();
            Require(refs.SequenceEqual(new[] { otherDoor.FormKey.ToString(), e.FormKey.ToString() }), "the moved reference is not in its new cell's export");
            var dep = doc.RootElement.GetProperty("teleport_dependencies").EnumerateArray().Single();
            Require(dep.GetProperty("destination_cell").ValueKind == JsonValueKind.Null, "a door to a deleted door still names a destination cell");
        }
        // regression: a cell no DLC touches exports byte for byte the same with and without the DLC loaded, and the
        // master alone exports Factory as it always did (C and E included)
        var aloneJson = Path.Combine(dir, "Untouched.alone.json");
        var withJson = Path.Combine(dir, "Untouched.with.json");
        Require(RunExporter(masterPath, "export", "Untouched", aloneJson).Code == 0, "export of Untouched (master alone) failed");
        Require(RunExporter(dlcPath, "--master", masterPath, "export", "Untouched", withJson).Code == 0, "export of Untouched (with the DLC) failed");
        Require(File.ReadAllText(aloneJson) == File.ReadAllText(withJson), "an untouched cell's export changed when a DLC is loaded");
        using (var doc = JsonDocument.Parse(File.ReadAllText(aloneJson)))
            Require(doc.RootElement.GetProperty("refs").EnumerateArray().Select(r => r.GetProperty("persistent").GetBoolean()).SequenceEqual(new[] { false, true }), "temporary then persistent order changed");
        var factoryAlone = Path.Combine(dir, "Factory.alone.json");
        Require(RunExporter(masterPath, "export", "Factory", factoryAlone).Code == 0, "export of Factory (master alone) failed");
        using (var doc = JsonDocument.Parse(File.ReadAllText(factoryAlone)))
        {
            Require(doc.RootElement.GetProperty("refs").GetArrayLength() == 4 && doc.RootElement.GetProperty("cell_data").GetProperty("name").GetString() == "Factory", "the master alone no longer exports its own cell");
            Require(doc.RootElement.GetProperty("teleport_dependencies").EnumerateArray().Single().GetProperty("destination_cell").GetProperty("editor_id").GetString() == "Other", "the master alone lost its door dependency");
        }
        // locations mode reads the winning record too
        var sidecar = Path.Combine(dir, "locations.json");
        Require(RunExporter(dlcPath, "--master", masterPath, "locations", sidecar, "Factory", "Untouched").Code == 0, "locations mode failed");
        using (var doc = JsonDocument.Parse(File.ReadAllText(sidecar)))
        {
            var cells = doc.RootElement.GetProperty("cells");
            Require(cells.GetProperty("Factory").GetProperty("encounter_zone").GetProperty("editor_id").GetString() == "DlcFactoryZone", "the sidecar's zone is not the DLC's");
            Require(cells.GetProperty("Untouched").GetProperty("encounter_zone").ValueKind == JsonValueKind.Null, "the sidecar invented a zone");
        }
        // a third plugin overrides Factory without an EDID (Mutagen writes none for a null EditorID; a synthetic or
        // third-party case, the official DLC overrides carry it): the cell keeps its name from the earlier copies for
        // the merge, list, locations and export, and the override brings no children, so the refs are the DLC's merge
        var dlc2Key = ModKey.FromNameAndExtension("MergeDlc2.esm");
        var dlc2 = new Fallout4Mod(dlc2Key, Fallout4Release.Fallout4);
        AddInterior(dlc2, new Cell(new FormKey(masterKey, 0x1200), Fallout4Release.Fallout4) { Flags = Cell.Flag.IsInteriorCell, Name = "Factory (no EDID)" });
        var dlc2Path = Path.Combine(dir, dlc2Key.FileName.String);
        dlc2.BeginWrite.ToPath(dlc2Path).WithLoadOrder(masterKey, dlcKey).WithDataFolder(dir).Write();
        using (var p2 = Fallout4Mod.CreateFromBinaryOverlay(dlc2Path, Fallout4Release.Fallout4))
        {
            var three = new IFallout4ModGetter[] { m, p, p2 };
            var copies3 = CellMerge.Copies(three, worldspaces: false)[factory.FormKey];
            Require(copies3.Count == 3 && copies3[2].Cell.EditorID == null, "the EDID-less override did not read back without an EditorID");
            var merged3 = CellMerge.Merge(copies3, CellMerge.PlacedKeys(three));
            Require(merged3.EditorID == "Factory" && merged3.Cell.Name?.String == "Factory (no EDID)", "the cell's name did not fall back to an earlier copy's EditorID");
            Require(merged3.Children.Select(ch => ch.Record.FormKey).SequenceEqual(new[] { a.FormKey, b.FormKey, d.FormKey }), "a childless override changed the merged children");
            Require(merged.EditorID == "Factory" && single.EditorID == "Factory", "the merged editor id is not the winner's when it has one");
        }
        var noEdidJson = Path.Combine(dir, "FactoryNoEdid.json");
        run = RunExporter(dlc2Path, "--master", masterPath, "--master", dlcPath, "export", "Factory", noEdidJson);
        Require(run.Code == 0, "export of a cell whose winning override has no EDID failed: " + run.Err);
        using (var doc = JsonDocument.Parse(File.ReadAllText(noEdidJson)))
        {
            Require(doc.RootElement.GetProperty("cell").GetString() == "Factory", "the export's cell name is not the earlier copy's EditorID");
            Require(doc.RootElement.GetProperty("cell_data").GetProperty("name").GetString() == "Factory (no EDID)", "cell_data is not the winning record's");
            Require(doc.RootElement.GetProperty("refs").GetArrayLength() == 3, "the EDID-less override changed the refs");
        }
        var sidecar2 = Path.Combine(dir, "locations2.json");
        Require(RunExporter(dlc2Path, "--master", masterPath, "--master", dlcPath, "locations", sidecar2, "Factory").Code == 0, "locations mode lost an EDID-less override's cell");
        using (var doc = JsonDocument.Parse(File.ReadAllText(sidecar2)))
            Require(doc.RootElement.GetProperty("cells").GetProperty("Factory").GetProperty("cell_data").GetProperty("name").GetString() == "Factory (no EDID)", "the sidecar is not keyed by the cell's name");
        var listRun = Process.Start(new ProcessStartInfo(exe, new[] { dlc2Path, "--master", masterPath, "--master", dlcPath, "list", "Fact" }) { RedirectStandardOutput = true, RedirectStandardError = true })!;
        var listed = listRun.StandardOutput.ReadToEnd(); listRun.WaitForExit();
        Require(listRun.ExitCode == 0 && listed.StartsWith("Factory  ") && listed.Contains("refs=3"), "list did not name the EDID-less cell: " + listed);
        Console.WriteLine("Merged cell export checks passed.");
    }

    static void AddInterior(Fallout4Mod mod, params Cell[] cells)
    {
        var sub = new CellSubBlock { BlockNumber = 0, GroupType = GroupTypeEnum.InteriorCellSubBlock };
        foreach (var c in cells) sub.Cells.Add(c);
        var block = new CellBlock { BlockNumber = 0, GroupType = GroupTypeEnum.InteriorCellBlock };
        block.SubBlocks.Add(sub);
        mod.Cells.Records.Add(block);
    }
}
