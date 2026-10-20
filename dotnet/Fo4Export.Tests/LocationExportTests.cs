// Synthetic checks for LocationExport (schema 3 cell_data / location / encounter_zone), the `export` mode's schema-3 cell
// JSON and the `locations` sidecar mode.
// A master and a plugin are written to a temp folder and read back through the binary overlay with a two-mod link cache,
// the way Fo4Export reads a DLC with --master, so XLCN, XEZN, PNAM, KWDA and ECZN DATA all go through the real reader.
using System.Diagnostics;
using System.Text.Json;
using Mutagen.Bethesda;
using Mutagen.Bethesda.Fallout4;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Cache;
using Mutagen.Bethesda.Plugins.Records;

public static class LocationExportTests
{
    static void Require(bool condition, string message)
    {
        if (!condition) throw new InvalidOperationException(message);
    }

    static JsonElement Json(object? o) => JsonDocument.Parse(JsonSerializer.Serialize(o)).RootElement.Clone();

    public static void Run()
    {
        var masterKey = ModKey.FromNameAndExtension("SynthMaster.esm");
        var pluginKey = ModKey.FromNameAndExtension("SynthDlc.esm");
        var master = new Fallout4Mod(masterKey, Fallout4Release.Fallout4);
        var grand = new Location(new FormKey(masterKey, 0x801), Fallout4Release.Fallout4) { EditorID = "CommonwealthLocation", Name = "Commonwealth" };
        var parent = new Location(new FormKey(masterKey, 0x802), Fallout4Release.Fallout4) { EditorID = "ConcordLocation", Name = "Concord" };
        parent.ParentLocation.SetTo(grand.FormKey);
        var kw = new Keyword(new FormKey(masterKey, 0x803), Fallout4Release.Fallout4) { EditorID = "LocTypeDungeon" };
        var fac = new Faction(new FormKey(masterKey, 0x804), Fallout4Release.Fallout4) { EditorID = "RaiderFaction" };
        master.Locations.Add(grand); master.Locations.Add(parent); master.Keywords.Add(kw); master.Factions.Add(fac);

        var plugin = new Fallout4Mod(pluginKey, Fallout4Release.Fallout4);
        // (a) the plugin's own LCTN, parented into the master two levels up, with one keyword and one unresolvable keyword
        var loc = new Location(new FormKey(pluginKey, 0x801), Fallout4Release.Fallout4) { EditorID = "DLCMuseumLocation", Name = "Museum of Freedom" };
        loc.ParentLocation.SetTo(parent.FormKey);
        loc.Keywords = new();
        loc.Keywords.Add(kw.FormKey);
        loc.Keywords.Add(new FormKey(masterKey, 0x9999));
        var zone = new EncounterZone(new FormKey(pluginKey, 0x802), Fallout4Release.Fallout4)
            { EditorID = "DLCMuseumZone", MinLevel = 5, MaxLevel = 10, Rank = 2, Flags = EncounterZone.Flag.NeverResets | EncounterZone.Flag.DisableCombatBoundary };
        zone.Owner.SetTo(fac.FormKey);
        zone.Location.SetTo(loc.FormKey);
        // (f) an LCTN with no KWDA and no reference lists at all
        var bare = new Location(new FormKey(pluginKey, 0x803), Fallout4Release.Fallout4) { EditorID = "BareLocation" };
        // a parent cycle must not loop the chain
        var cycleA = new Location(new FormKey(pluginKey, 0x804), Fallout4Release.Fallout4) { EditorID = "CycleA" };
        var cycleB = new Location(new FormKey(pluginKey, 0x805), Fallout4Release.Fallout4) { EditorID = "CycleB" };
        cycleA.ParentLocation.SetTo(cycleB.FormKey);
        cycleB.ParentLocation.SetTo(cycleA.FormKey);
        // a parent whose record is not loaded (a DLC location under an unloaded master) ends the chain as unresolved
        var orphan = new Location(new FormKey(pluginKey, 0x806), Fallout4Release.Fallout4) { EditorID = "OrphanLocation" };
        orphan.ParentLocation.SetTo(new FormKey(masterKey, 0x7779));
        foreach (var l in new[] { loc, bare, cycleA, cycleB, orphan }) plugin.Locations.Add(l);
        plugin.EncounterZones.Add(zone);

        var both = new Cell(new FormKey(pluginKey, 0x810), Fallout4Release.Fallout4) { EditorID = "DLCMuseum01", Flags = Cell.Flag.IsInteriorCell, Name = "Museum" };
        both.Location.SetTo(loc.FormKey);
        both.EncounterZone.SetTo(zone.FormKey);
        var zoneOnly = new Cell(new FormKey(pluginKey, 0x811), Fallout4Release.Fallout4) { EditorID = "EczOnly", Flags = Cell.Flag.IsInteriorCell };
        zoneOnly.EncounterZone.SetTo(zone.FormKey);
        var locOnly = new Cell(new FormKey(pluginKey, 0x812), Fallout4Release.Fallout4) { EditorID = "LctnOnly", Flags = Cell.Flag.IsInteriorCell | Cell.Flag.HasWater };
        locOnly.Location.SetTo(parent.FormKey);
        var neither = new Cell(new FormKey(pluginKey, 0x813), Fallout4Release.Fallout4) { EditorID = "Neither", Flags = Cell.Flag.IsInteriorCell };
        var dangling = new Cell(new FormKey(pluginKey, 0x814), Fallout4Release.Fallout4) { EditorID = "Dangling", Flags = Cell.Flag.IsInteriorCell };
        dangling.Location.SetTo(new FormKey(masterKey, 0x7777));
        dangling.EncounterZone.SetTo(new FormKey(masterKey, 0x7778));
        var bareCell = new Cell(new FormKey(pluginKey, 0x815), Fallout4Release.Fallout4) { EditorID = "BareCell", Flags = Cell.Flag.IsInteriorCell };
        bareCell.Location.SetTo(bare.FormKey);
        var cycleCell = new Cell(new FormKey(pluginKey, 0x816), Fallout4Release.Fallout4) { EditorID = "CycleCell", Flags = Cell.Flag.IsInteriorCell };
        cycleCell.Location.SetTo(cycleA.FormKey);
        var orphanCell = new Cell(new FormKey(pluginKey, 0x817), Fallout4Release.Fallout4) { EditorID = "OrphanCell", Flags = Cell.Flag.IsInteriorCell };
        orphanCell.Location.SetTo(orphan.FormKey);
        var sub = new CellSubBlock { BlockNumber = 0, GroupType = GroupTypeEnum.InteriorCellSubBlock };
        foreach (var cellRecord in new[] { both, zoneOnly, locOnly, neither, dangling, bareCell, cycleCell, orphanCell }) sub.Cells.Add(cellRecord);
        var block = new CellBlock { BlockNumber = 0, GroupType = GroupTypeEnum.InteriorCellBlock };
        block.SubBlocks.Add(sub);
        plugin.Cells.Records.Add(block);

        var dir = Environment.GetEnvironmentVariable("FO4SF_EXPORT_EVIDENCE_DIR") is { Length: > 0 } evidence
            ? Path.Combine(evidence, "location-export")
            : Path.Combine(Path.GetTempPath(), "fo4sf-location-export-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(dir);
        var masterPath = Path.Combine(dir, masterKey.FileName.String);
        var pluginPath = Path.Combine(dir, pluginKey.FileName.String);
        master.BeginWrite.ToPath(masterPath).WithNoLoadOrder().WithDataFolder(dir).Write();
        plugin.BeginWrite.ToPath(pluginPath).WithLoadOrder(masterKey).WithDataFolder(dir).Write();

        using var m = Fallout4Mod.CreateFromBinaryOverlay(masterPath, Fallout4Release.Fallout4);
        using var p = Fallout4Mod.CreateFromBinaryOverlay(pluginPath, Fallout4Release.Fallout4);
        ILinkCache cache = new IFallout4ModGetter[] { m, p }.ToImmutableLinkCache();
        var cells = p.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells).ToDictionary(c => c.EditorID!);
        JsonElement Export(string editorId) => Json(LocationExport.Build(cells[editorId], cache));

        // (a) LCTN + ECZN, parent chain crossing into the master
        var a = Export("DLCMuseum01");
        Require(a.GetProperty("cell_data").GetProperty("flags").GetInt32() == (int)Cell.Flag.IsInteriorCell, "cell flags lost");
        Require(a.GetProperty("cell_data").GetProperty("name").GetString() == "Museum", "cell name lost");
        var al = a.GetProperty("location");
        Require(al.GetProperty("formkey").GetString() == loc.FormKey.ToString(), "location identity lost");
        Require(al.GetProperty("editor_id").GetString() == "DLCMuseumLocation" && al.GetProperty("name").GetString() == "Museum of Freedom", "location names lost");
        Require(al.GetProperty("parent").GetString() == parent.FormKey.ToString(), "direct parent lost");
        var chain = al.GetProperty("parent_chain");
        Require(chain.GetArrayLength() == 2, "parent chain length changed");
        Require(chain[0].GetProperty("editor_id").GetString() == "ConcordLocation" && chain[0].GetProperty("name").GetString() == "Concord", "first parent lost");
        Require(chain[1].GetProperty("editor_id").GetString() == "CommonwealthLocation" && chain[1].GetProperty("formkey").GetString() == grand.FormKey.ToString(), "root parent lost");
        var kws = al.GetProperty("keywords");
        Require(kws.GetArrayLength() == 2, "keyword count changed");
        Require(kws[0].GetProperty("formkey").GetString() == kw.FormKey.ToString() && kws[0].GetProperty("editor_id").GetString() == "LocTypeDungeon", "resolved keyword lost");
        Require(kws[1].GetProperty("editor_id").ValueKind == JsonValueKind.Null, "unresolvable keyword given a name");
        var az = a.GetProperty("encounter_zone");
        Require(az.GetProperty("formkey").GetString() == zone.FormKey.ToString() && az.GetProperty("editor_id").GetString() == "DLCMuseumZone", "zone identity lost");
        Require(az.GetProperty("min_level").GetInt32() == 5 && az.GetProperty("max_level").GetInt32() == 10 && az.GetProperty("rank").GetInt32() == 2, "zone leveling lost");
        Require(az.GetProperty("flags").GetInt32() == 5, "zone flags changed");
        Require(az.GetProperty("owner").GetString() == fac.FormKey.ToString(), "zone owner lost");
        Require(az.GetProperty("location").GetString() == loc.FormKey.ToString(), "zone location lost");

        // (b) ECZN only
        var b = Export("EczOnly");
        Require(b.GetProperty("location").ValueKind == JsonValueKind.Null, "location invented for a zone-only cell");
        Require(b.GetProperty("encounter_zone").GetProperty("min_level").GetInt32() == 5, "zone-only leveling lost");
        // (c) LCTN only, pointing straight into the master
        var c = Export("LctnOnly");
        Require(c.GetProperty("encounter_zone").ValueKind == JsonValueKind.Null, "zone invented for a location-only cell");
        Require(c.GetProperty("location").GetProperty("editor_id").GetString() == "ConcordLocation", "master location lost");
        Require(c.GetProperty("location").GetProperty("parent_chain").GetArrayLength() == 1, "master parent chain changed");
        Require(c.GetProperty("cell_data").GetProperty("flags").GetInt32() == (int)(Cell.Flag.IsInteriorCell | Cell.Flag.HasWater), "extra cell flag lost");
        Require(c.GetProperty("cell_data").GetProperty("name").ValueKind == JsonValueKind.Null, "cell name invented");
        // (d) neither
        var d = Export("Neither");
        Require(d.GetProperty("location").ValueKind == JsonValueKind.Null && d.GetProperty("encounter_zone").ValueKind == JsonValueKind.Null, "links invented");
        // (e) dangling XLCN / XEZN
        var e = Export("Dangling");
        Require(e.GetProperty("location").GetProperty("unresolved").GetBoolean() && e.GetProperty("location").GetProperty("formkey").GetString() == new FormKey(masterKey, 0x7777).ToString(), "dangling location dropped");
        Require(e.GetProperty("encounter_zone").GetProperty("unresolved").GetBoolean(), "dangling zone dropped");
        // (f) LCTN with null Keywords and reference lists
        var f = Export("BareCell");
        Require(f.GetProperty("location").GetProperty("keywords").GetArrayLength() == 0, "null keywords not treated as empty");
        Require(f.GetProperty("location").GetProperty("parent").ValueKind == JsonValueKind.Null && f.GetProperty("location").GetProperty("parent_chain").GetArrayLength() == 0, "parent invented");
        Require(f.GetProperty("location").GetProperty("name").ValueKind == JsonValueKind.Null, "location name invented");
        // a parent cycle terminates
        var cyc = Export("CycleCell").GetProperty("location").GetProperty("parent_chain");
        Require(cyc.GetArrayLength() == 1 && cyc[0].GetProperty("editor_id").GetString() == "CycleB", "parent cycle not guarded");
        // a parent that does not resolve ends the chain with {formkey, unresolved: true}, never silently truncated
        var orphaned = Export("OrphanCell").GetProperty("location");
        Require(orphaned.GetProperty("parent").GetString() == new FormKey(masterKey, 0x7779).ToString(), "unresolved parent link lost");
        var orphanChain = orphaned.GetProperty("parent_chain");
        Require(orphanChain.GetArrayLength() == 1 && orphanChain[0].GetProperty("unresolved").GetBoolean()
                && orphanChain[0].GetProperty("formkey").GetString() == new FormKey(masterKey, 0x7779).ToString(), "unresolved parent not kept in the chain");
        Console.WriteLine("Location export synthetic cell checks passed.");

        // (g) the locations sidecar from the real exe equals the per-cell keys (serialized through the same builder)
        // the exporter's apphost is copied beside the test binary by the project reference
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
        // (h) the export mode's cell JSON is schema 3 and carries the three keys exactly as the builder serializes them
        var cellJsonPath = Path.Combine(dir, "DLCMuseum01.json");
        var exported = RunExporter(pluginPath, "--master", masterPath, "export", "DLCMuseum01", cellJsonPath);
        Require(exported.Code == 0 && File.Exists(cellJsonPath), "export mode failed: " + exported.Err);
        using (var cellJson = JsonDocument.Parse(File.ReadAllText(cellJsonPath)))
        {
            var top = cellJson.RootElement;
            Require(top.GetProperty("schema_version").GetInt32() == 3, "export is not schema 3");
            Require(top.GetProperty("cell").GetString() == "DLCMuseum01" && top.GetProperty("refs").GetArrayLength() == 0, "export lost the schema-2 keys");
            var expected = Export("DLCMuseum01");
            foreach (var key in new[] { "cell_data", "location", "encounter_zone" })
                Require(top.TryGetProperty(key, out var got) && JsonSerializer.Serialize(got) == JsonSerializer.Serialize(expected.GetProperty(key)),
                        $"export's {key} missing or differs from LocationExport.Build");
        }
        Console.WriteLine("Location export mode checks passed.");

        var sidecarPath = Path.Combine(dir, "locations.json");
        var names = new[] { "DLCMuseum01", "EczOnly", "LctnOnly", "Neither", "Dangling", "BareCell", "CycleCell", "OrphanCell" };
        var run = RunExporter(new[] { pluginPath, "--master", masterPath, "locations", sidecarPath }.Concat(names).ToArray());
        Require(run.Code == 0, "locations mode failed: " + run.Err);
        using var sidecar = JsonDocument.Parse(File.ReadAllText(sidecarPath));
        Require(sidecar.RootElement.GetProperty("schema_version").GetInt32() == 1, "sidecar schema changed");
        var sidecarCells = sidecar.RootElement.GetProperty("cells");
        Require(sidecarCells.EnumerateObject().Count() == names.Length, "sidecar cell count changed");
        foreach (var name in names)
            Require(JsonSerializer.Serialize(sidecarCells.GetProperty(name)) == JsonSerializer.Serialize(Export(name)), $"sidecar entry for {name} differs from the per-cell keys");
        // an unknown cell fails the run and writes nothing
        var bad = RunExporter(pluginPath, "--master", masterPath, "locations", Path.Combine(dir, "bad.json"), "DLCMuseum01", "NoSuchCell");
        Require(bad.Code != 0 && bad.Err.Contains("NoSuchCell"), "unknown cell did not fail the locations run");
        Require(!File.Exists(Path.Combine(dir, "bad.json")), "sidecar written despite an unknown cell");
        Console.WriteLine("Location sidecar mode checks passed.");
    }
}
