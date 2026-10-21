// Synthetic checks for TeleportLinks (load-door teleports between converted cells) and for PluginSpike's door state
// (open by default, locks; run through its entry point). No game data: synthetic cells, a graph-less DOOR base, a STAT
// base, hand-written manifests and cell exports.
//   dotnet run --project dotnet/PluginSpike.Tests
using System.Text.Json;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;

void Require(bool ok, string message) { if (!ok) throw new InvalidOperationException(message); }
// an asset path as written, with either separator (Mutagen gives back Windows separators on Windows: Codex, #357)
static string? AssetPath(object? file) => file?.ToString()?.Replace('\\', '/');
var release = StarfieldRelease.Starfield;
var modKey = ModKey.FromNameAndExtension("Synthetic.esm");
FormKey Key(uint id) => new(modKey, id);
var mod = new StarfieldMod(modKey, release);
mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
var loadDoor = new Door(Key(0x900), release) { EditorID = "FO4Port_SyntheticLoadDoor", Model = new Model { File = "fo4port\\doors\\load.nif" } };
var wall = new Static(Key(0x901), release) { EditorID = "FO4Port_Wall" };
mod.Doors.Add(loadDoor); mod.Statics.Add(wall);
Cell MakeCell(uint id, string name) => new(Key(id), release) { EditorID = name, Flags = Cell.Flag.IsInteriorCell };
var first = MakeCell(0x800, "FO4Port_First");
var second = MakeCell(0x801, "FO4Port_Second");
PlacedObject Place(Cell c, uint id, FormKey b, float x)
{
    var o = new PlacedObject(Key(id), release) { Position = new P3Float(x, 0, 0) };
    o.Base.SetTo(b); c.Temporary.Add(o); return o;
}
var a = Place(first, 0x810, loadDoor.FormKey, 1);        // A <-> B: a mutual pair across the two cells
var b = Place(second, 0x811, loadDoor.FormKey, 2);
var c = Place(first, 0x812, loadDoor.FormKey, 3);        // C -> D: D has no XTEL back (one-way)
var d = Place(second, 0x813, loadDoor.FormKey, 4);
var e = Place(first, 0x814, loadDoor.FormKey, 5);        // E -> Z: Z is not placed (its cell is not in the build)
var s = Place(first, 0x815, wall.FormKey, 6);            // STAT base with an XTEL (a hatch converted as a static)
var rel = Place(first, 0x816, loadDoor.FormKey, 7);      // relative-position flag: not implemented, must be reported
var plain = Place(first, 0x817, wall.FormKey, 8);        // no XTEL at all
var block = new CellBlock { BlockNumber = 0, GroupType = GroupTypeEnum.InteriorCellBlock };
var sub = new CellSubBlock { BlockNumber = 0, GroupType = GroupTypeEnum.InteriorCellSubBlock };
sub.Cells.Add(first); sub.Cells.Add(second); block.SubBlocks.Add(sub); mod.Cells.Records.Add(block);
var placed = new Dictionary<string, (PlacedObject, Cell)>
{
    ["A"] = (a, first), ["B"] = (b, second), ["C"] = (c, first), ["D"] = (d, second), ["E"] = (e, first),
    ["S"] = (s, first), ["R"] = (rel, first), ["P"] = (plain, first),
};
using var one = JsonDocument.Parse("""
{"cell":"First","formkey":"first-cell","refs":[
 {"formkey":"A","teleport_destination":{"door":"B","pos":[70,140,210],"rot":[0,0,1.5],"flags":2,"transition_interior":"second-cell"}},
 {"formkey":"C","teleport_destination":{"door":"D","pos":[0,0,0],"rot":[0,0,0],"flags":0,"transition_interior":null}},
 {"formkey":"E","teleport_destination":{"door":"Z","pos":[0,0,0],"rot":[0,0,0],"flags":0,"transition_interior":null}},
 {"formkey":"S","teleport_destination":{"door":"B","pos":[0,0,0],"rot":[0,0,0],"flags":0,"transition_interior":null}},
 {"formkey":"R","teleport_destination":{"door":"B","pos":[0,0,0],"rot":[0,0,0],"flags":4,"transition_interior":null}},
 {"formkey":"P","teleport_destination":null},
 {"formkey":"N","teleport_destination":{"door":"B","pos":[0,0,0],"rot":[0,0,0],"flags":0,"transition_interior":null}}]}
""");
using var two = JsonDocument.Parse("""
{"cell":"Second","formkey":"second-cell","refs":[
 {"formkey":"B","teleport_destination":{"door":"A","pos":[-70,0,35],"rot":[0,0,-1.5],"flags":0,"transition_interior":null}},
 {"formkey":"D","teleport_destination":null}]}
""");
var exports = new[] { one.RootElement, two.RootElement };
var report = TeleportLinks.Apply(mod, placed, exports);
Require(report.Linked == 3, $"expected 3 linked references (A, B, C), got {report.Linked}");
Require(report.Pairs == 1 && report.OneWay == 1, $"expected 1 mutual pair and 1 one-way link, got {report.Pairs}/{report.OneWay}");
Require(report.DestinationNotInBuild == 1 && report.Unlinked.Single() == "First E -> Z", "destination outside the build not listed");
Require(report.SourceNotPlaced == 1 && report.UnplacedSources.Single() == "First N -> B", "XTEL on an unplaced source not listed");
Require(report.Issues.Count == 2, $"expected 2 issues (STAT source, relative flag), got {report.Issues.Count}");
Require(report.Issues.Any(i => i.Source == "S" && i.Reason.Contains("not a DOOR")), "STAT-based source silently linked");
Require(report.Issues.Any(i => i.Source == "R" && i.Reason.Contains("relative")), "relative-position XTEL silently written");
Require(a.TeleportDestination != null && a.TeleportDestination.Door.FormKey == b.FormKey, "A does not link to B");
Require(b.TeleportDestination != null && b.TeleportDestination.Door.FormKey == a.FormKey, "B does not link back to A");
Require(c.TeleportDestination != null && c.TeleportDestination.Door.FormKey == d.FormKey && d.TeleportDestination == null, "one-way link wrong");
Require(a.TeleportDestination!.Position.X == 1 && a.TeleportDestination.Position.Y == 2 && a.TeleportDestination.Position.Z == 3, "arrival point not converted to metres");
Require(a.TeleportDestination.Rotation.Z == 1.5f && b.TeleportDestination!.Rotation.Z == -1.5f, "arrival rotation changed");
Require((uint)a.TeleportDestination.Flags == 2 && (uint)b.TeleportDestination!.Flags == 0, "XTEL flags changed");
Require(a.TeleportDestination.TransitionInterior.IsNull, "transition interior must not be guessed (vanilla never sets it)");
Require(e.TeleportDestination == null && s.TeleportDestination == null && rel.TeleportDestination == null, "unresolved reference received an XTEL");
foreach (var (o, cell, name) in new[] { (a, first, "A"), (b, second, "B"), (c, first, "C"), (d, second, "D") })
    Require(cell.Persistent.Contains(o) && !cell.Temporary.Contains(o) && (o.MajorRecordFlagsRaw & 0x400) != 0, $"{name} not persistent");
foreach (var (o, name) in new[] { (e, "E"), (s, "S"), (rel, "R"), (plain, "P") })
    Require(first.Temporary.Contains(o) && (o.MajorRecordFlagsRaw & 0x400) == 0, $"{name} made persistent without a link");
var again = TeleportLinks.Apply(mod, placed, exports);
Require(again.Linked == 3 && first.Persistent.Count == 2 && second.Persistent.Count == 2 && first.Temporary.Count == 4, "reapplying is not idempotent");

// Binary round trip: write, read back with the overlay reader PluginSpike's `teleports` verb uses, list the links.
var directory = Path.Combine(Path.GetTempPath(), "fo4sf-teleports-" + Guid.NewGuid().ToString("N"));
Directory.CreateDirectory(directory);
try
{
    var path = Path.Combine(directory, "Synthetic.esm");
    var starfield = ModKey.FromNameAndExtension("Starfield.esm");
    mod.BeginWrite.ToPath(path).WithLoadOrderFromHeaderMasters().WithDataFolder(directory)
        .WithKnownMasters(new KeyedMasterStyle(starfield, MasterStyle.Full)).Write();
    var listing = new StringWriter();
    Require(TeleportLinks.List(path, listing) == 3, "read-back listing does not show 3 links");
    var lines = listing.ToString().Split('\n');
    Require(lines.Count(l => l.Contains("back=True")) == 2 && lines.Count(l => l.Contains("back=False")) == 1, "mutual / one-way links not reported on read-back");
    var masters = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
    masters.Set(new KeyedMasterStyle(starfield, MasterStyle.Full));
    using var read = StarfieldMod.CreateFromBinaryOverlay(path, release, new BinaryReadParameters { MasterFlagsLookup = masters });
    var cells = read.Cells.Records.SelectMany(x => x.SubBlocks).SelectMany(x => x.Cells).ToDictionary(x => x.FormKey);
    var writtenA = cells[first.FormKey].Persistent.OfType<IPlacedObjectGetter>().Single(r => r.FormKey == a.FormKey);
    var writtenB = cells[second.FormKey].Persistent.OfType<IPlacedObjectGetter>().Single(r => r.FormKey == b.FormKey);
    Require(writtenA.TeleportDestination!.Door.FormKey == b.FormKey && writtenB.TeleportDestination!.Door.FormKey == a.FormKey, "pair lost in binary output");
    Require(writtenA.TeleportDestination.Position.Z == 3 && writtenA.TeleportDestination.Rotation.Z == 1.5f && (uint)writtenA.TeleportDestination.Flags == 2, "arrival point lost in binary output");
    Require((writtenA.MajorRecordFlagsRaw & 0x400) != 0 && cells[first.FormKey].Temporary.Count == 4, "persistent grouping lost in binary output");
    Require(read.Doors.Single().FormKey == loadDoor.FormKey && !read.Doors.Single().Components.Any(), "graph-less DOOR base lost in binary output");
}
finally { Directory.Delete(directory, true); }
Console.WriteLine("Load-door teleport synthetic checks and binary round-trip passed.");

// ---- posed models (PosedBases): a reference with its own posed model gets that base, every other reference keeps the
// shared base of its model; malformed or conflicting pose entries fail the build instead of placing the wrong base.
using var poseManifest = JsonDocument.Parse("""
{"items":[
 {"editor_id":"FO4Port_Skel","model":"fo4port\\skel.nif","source":"meshes\\SetDressing\\Skel.nif"},
 {"editor_id":"FO4Port_Skel_xrgd_0123456789","model":"fo4port\\skel_xrgd_0123456789.nif","source":"meshes\\SetDressing\\Skel.nif",
  "pose":{"kind":"xrgd","key":"0123456789","refs":["0A:Fallout4.esm","0B:Fallout4.esm"]}},
 {"editor_id":"FO4Port_Bad","model":"x.nif","source":"meshes\\x.nif","pose":{"kind":"xrgd","refs":[]}}]}
""");
var poseItems = poseManifest.RootElement.GetProperty("items").EnumerateArray().ToList();
Require(PosedBases.RefsOf(poseItems[0]).Count == 0, "ordinary item reported as posed");
Require(PosedBases.RefsOf(poseItems[1]).SequenceEqual(new[] { "0A:Fallout4.esm", "0B:Fallout4.esm" }), "posed references not read");
var emptyRefs = false;
try { PosedBases.RefsOf(poseItems[2]); } catch (InvalidOperationException) { emptyRefs = true; }
Require(emptyRefs, "a pose without references was accepted");
var byRefBases = new Dictionary<string, string>();
var bySourceBases = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
foreach (var it in poseItems.Take(2))                                     // posed item first or last: same result
    PosedBases.Register(byRefBases, bySourceBases, it.GetProperty("source").GetString()!, PosedBases.RefsOf(it),
                        it.GetProperty("editor_id").GetString()!);
Require(bySourceBases.Count == 1 && bySourceBases["meshes\\setdressing\\skel.nif"] == "FO4Port_Skel", "posed item replaced the shared base");
Require(PosedBases.TryResolve(byRefBases, bySourceBases, "0A:Fallout4.esm", "SetDressing\\Skel.nif", out var posedBase)
        && posedBase == "FO4Port_Skel_xrgd_0123456789", "posed reference did not get its own base");
Require(PosedBases.TryResolve(byRefBases, bySourceBases, "0C:Fallout4.esm", "SetDressing\\Skel.nif", out var sharedBase)
        && sharedBase == "FO4Port_Skel", "unposed reference of the same model lost the shared base");
Require(!PosedBases.TryResolve(byRefBases, bySourceBases, "0D:Fallout4.esm", "SetDressing\\Other.nif", out _)
        && !PosedBases.TryResolve(byRefBases, bySourceBases, "0E:Fallout4.esm", "", out _), "unconverted model resolved");
var twice = false;
try { PosedBases.Register(byRefBases, bySourceBases, "meshes\\SetDressing\\Skel.nif", new[] { "0B:Fallout4.esm" }, "FO4Port_Skel_xrgd_other"); }
catch (InvalidOperationException) { twice = true; }
Require(twice && byRefBases["0B:Fallout4.esm"] == "FO4Port_Skel_xrgd_0123456789", "a reference with two posed models was accepted");
Console.WriteLine("Posed-model base selection checks passed.");

// ---- posed models end to end (PR #244 review): run PluginSpike itself on a synthetic manifest (a shared and a posed
// MoveableStatic, the posed one last; a posed and a shared Static, the posed one first) and one cell export, then read the
// written plugin back and check every reference's base. Catches a base path in Program.cs that bypasses PosedBases.
var spikeDir = Path.Combine(Path.GetTempPath(), "fo4sf-posed-" + Guid.NewGuid().ToString("N"));
Directory.CreateDirectory(spikeDir);
var oldSfData = Environment.GetEnvironmentVariable("STARFIELD_DATA");
try
{
    File.WriteAllText(Path.Combine(spikeDir, "manifest.json"), """
{"items":[
 {"editor_id":"FO4Port_Skel","model":"fo4port\\skel.nif","source":"meshes\\SetDressing\\Skel.nif","movable":{"mass_kg":10}},
 {"editor_id":"FO4Port_Skel_xrgd_0123456789","model":"fo4port\\skel_xrgd_0123456789.nif","source":"meshes\\SetDressing\\Skel.nif",
  "movable":{"mass_kg":10},"pose":{"kind":"xrgd","refs":["0A:Fallout4.esm"]}},
 {"editor_id":"FO4Port_Saw_xrgd_abcdef0123","model":"fo4port\\saw_xrgd_abcdef0123.nif","source":"meshes\\SetDressing\\Saw.nif",
  "pose":{"kind":"xrgd","refs":["0C:Fallout4.esm"]}},
 {"editor_id":"FO4Port_Saw","model":"fo4port\\saw.nif","source":"meshes\\SetDressing\\Saw.nif"}]}
""");
    string Ref(string fk, string model) =>
        $$"""{"formkey":"{{fk}}","model":"{{model}}","base_editor_id":"X","type":"Static","scale":1.0,"pos":[0,0,0],"rot":[0,0,0]}""";
    File.WriteAllText(Path.Combine(spikeDir, "cell.json"), "{\"cell\":\"Posed\",\"refs\":[" + string.Join(",",
        Ref("0A:Fallout4.esm", "SetDressing\\\\Skel.nif"), Ref("0B:Fallout4.esm", "SetDressing\\\\Skel.nif"),
        Ref("0C:Fallout4.esm", "SetDressing\\\\Saw.nif"), Ref("0D:Fallout4.esm", "SetDressing\\\\Saw.nif"),
        Ref("0E:Fallout4.esm", "SetDressing\\\\Other.nif")) + "]}");
    Environment.SetEnvironmentVariable("STARFIELD_DATA", spikeDir);        // masters come from WithKnownMasters
    typeof(PosedBases).Assembly.EntryPoint!.Invoke(null, new object[] {
        new[] { spikeDir, Path.Combine(spikeDir, "manifest.json"), Path.Combine(spikeDir, "cell.json") } });
    var sfMaster = ModKey.FromNameAndExtension("Starfield.esm");
    var spikeMasters = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
    spikeMasters.Set(new KeyedMasterStyle(sfMaster, MasterStyle.Full));
    using var written = StarfieldMod.CreateFromBinaryOverlay(Path.Combine(spikeDir, "FO4Port.esm"), release,
                                                            new BinaryReadParameters { MasterFlagsLookup = spikeMasters });
    var baseIds = written.MoveableStatics.Select(x => (x.FormKey, x.EditorID)).Concat(written.Statics.Select(x => (x.FormKey, x.EditorID)))
        .ToDictionary(x => x.FormKey, x => x.EditorID ?? "");
    Require(written.MoveableStatics.Count == 2 && written.Statics.Count == 2, "expected 2 MSTT and 2 STAT bases");
    var spikeIds = StableFormIds.Load(Path.Combine(spikeDir, "formids.json"));
    var refs = written.Cells.Records.SelectMany(x => x.SubBlocks).SelectMany(x => x.Cells).Single().Temporary
        .OfType<IPlacedObjectGetter>().ToDictionary(r => r.FormKey.ID, r => baseIds[r.Base.FormKey]);
    string BaseOf(string fk) => refs[spikeIds["REFR:FO4Port_Posed:" + fk]];
    Require(refs.Count == 4 && !spikeIds.ContainsKey("REFR:FO4Port_Posed:0E:Fallout4.esm"), "unconverted reference placed");
    Require(BaseOf("0A:Fallout4.esm") == "FO4Port_Skel_xrgd_0123456789", "posed MSTT reference not on its posed base");
    Require(BaseOf("0B:Fallout4.esm") == "FO4Port_Skel", "unposed MSTT reference not on the shared base");
    Require(BaseOf("0C:Fallout4.esm") == "FO4Port_Saw_xrgd_abcdef0123", "posed STAT reference not on its posed base");
    Require(BaseOf("0D:Fallout4.esm") == "FO4Port_Saw", "unposed STAT reference not on the shared base");
}
finally
{
    Environment.SetEnvironmentVariable("STARFIELD_DATA", oldSfData);
    Directory.Delete(spikeDir, true);
}
Console.WriteLine("Posed-model plugin round trip passed.");

// Review of PR #242, P3: an FO4 load reference that shares an opening door's model gets that model's DOOR base, which plays
// its own rig (manifest rig "native"). Such a source is reported, not linked; a plain load door linking to it still links.
{
    var rigMod = new StarfieldMod(modKey, release);
    var rigged = new Door(Key(0x902), release) { EditorID = "FO4Port_SyntheticElevatorDoor" };
    var plainLoad = new Door(Key(0x903), release) { EditorID = "FO4Port_SyntheticLoadDoor2" };
    rigMod.Doors.Add(rigged); rigMod.Doors.Add(plainLoad);
    var third = MakeCell(0x802, "FO4Port_Third");
    var up = Place(third, 0x820, rigged.FormKey, 1);
    var down = Place(third, 0x821, plainLoad.FormKey, 2);
    using var elevator = JsonDocument.Parse("""
{"cell":"Third","refs":[
 {"formkey":"U","teleport_destination":{"door":"V","pos":[0,0,0],"rot":[0,0,0],"flags":0,"transition_interior":null}},
 {"formkey":"V","teleport_destination":{"door":"U","pos":[0,0,0],"rot":[0,0,0],"flags":0,"transition_interior":null}}]}
""");
    var rigPlaced = new Dictionary<string, (PlacedObject, Cell)> { ["U"] = (up, third), ["V"] = (down, third) };
    var guarded = TeleportLinks.Apply(rigMod, rigPlaced, new[] { elevator.RootElement }, new HashSet<FormKey> { rigged.FormKey });
    Require(up.TeleportDestination == null && guarded.Issues.Single().Source == "U" && guarded.Issues.Single().Reason.Contains("own opening rig"),
            "XTEL written on a door with its own opening rig");
    Require(guarded.Linked == 1 && down.TeleportDestination!.Door.FormKey == up.FormKey, "plain load door no longer links");
}

// Review of PR #242, P2: PluginSpike end to end (its entry point, a synthetic manifest and cell export). FO4's open-by-default
// state reaches the placed references of animated DOOR bases, never a STAT; FO4 lock data is counted, not written.
{
    var doorDir = Path.Combine(Path.GetTempPath(), "fo4sf-doorstate-" + Guid.NewGuid().ToString("N"));
    var outDir = Path.Combine(doorDir, "out");
    Directory.CreateDirectory(outDir);
    var stdout = Console.Out;
    try
    {
        var manifest = Path.Combine(doorDir, "manifest.json");
        File.WriteAllText(manifest, """
{"items":[
 {"editor_id":"FO4Port_SynthDoor","model":"fo4port\\d.nif","source":"meshes\\doors\\d.nif",
  "door":{"anim_graph":"SimpleOpenClose01.agx","skeleton":"fo4port\\d\\skeleton.rig","animations":"fo4port\\d\\animations",
          "origin_offset":[0,0,0],"rig":"native"}},
 {"editor_id":"FO4Port_SynthWall","model":"fo4port\\w.nif","source":"meshes\\w.nif"}]}
""");
        var export = Path.Combine(doorDir, "Synth.json");
        File.WriteAllText(export, """
{"cell":"Synth","formkey":"cell","refs":[
 {"formkey":"000801:Fallout4.esm","base_editor_id":"D","type":"Door","model":"doors\\d.nif","pos":[0,0,0],"rot":[0,0,0],"scale":1,
  "open_by_default":true,"lock_data":null},
 {"formkey":"000802:Fallout4.esm","base_editor_id":"D","type":"Door","model":"doors\\d.nif","pos":[70,0,0],"rot":[0,0,0],"scale":1,
  "open_by_default":false,"lock_data":{"level":253,"key":null,"flags":0,"unused":0}},
 {"formkey":"000803:Fallout4.esm","base_editor_id":"W","type":"Static","model":"w.nif","pos":[140,0,0],"rot":[0,0,0],"scale":1,
  "open_by_default":true}]}
""");
        foreach (var hook in new[] { "FO4PORT_DOOR_MODEL", "FO4PORT_DOOR_BASE", "FO4PORT_DOORTEST" }) Environment.SetEnvironmentVariable(hook, null);
        Environment.SetEnvironmentVariable("STARFIELD_DATA", doorDir);
        var log = new StringWriter();
        Console.SetOut(log);
        typeof(TeleportLinks).Assembly.EntryPoint!.Invoke(null, new object[] { new[] { outDir, manifest, export } });
        Console.SetOut(stdout);
        var ids = StableFormIds.Load(Path.Combine(outDir, "formids.json"));
        var port = ModKey.FromNameAndExtension("FO4Port.esm");
        var spikeMasters = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        spikeMasters.Set(new KeyedMasterStyle(ModKey.FromNameAndExtension("Starfield.esm"), MasterStyle.Full));
        using var written = StarfieldMod.CreateFromBinaryOverlay(Path.Combine(outDir, "FO4Port.esm"), release,
            new BinaryReadParameters { MasterFlagsLookup = spikeMasters });
        var refs = written.Cells.Records.SelectMany(x => x.SubBlocks).SelectMany(x => x.Cells).Single()
            .Temporary.OfType<IPlacedObjectGetter>().ToDictionary(r => r.FormKey);
        IPlacedObjectGetter Ref(string fo4) => refs[new FormKey(port, ids[$"REFR:FO4Port_Synth:{fo4}:Fallout4.esm"])];
        Require(Ref("000801").OpenByDefault, "FO4 open-by-default door written shut");
        Require(!Ref("000802").OpenByDefault && Ref("000802").Lock == null, "shut FO4 door opened or given a lock");
        Require(!Ref("000803").OpenByDefault, "open-by-default written on a STAT reference");
        Require(log.ToString().Contains("doors: 1 open by default (as in FO4), 1 locked in FO4 (lock not written)"), "door state not reported:\n" + log);
    }
    finally { Console.SetOut(stdout); Directory.Delete(doorDir, true); }
}
Console.WriteLine("Own-rig XTEL guard and PluginSpike door-state checks passed.");

// Load doors that open before the trip (load_door.anim, scripts/door_bridge/load_door_anim.py): PluginSpike end to end.
// The animated load door gets the rig's graph, skeleton and clips and the twin's model, its reference shifts by the rig's
// origin offset; a load door without "anim" stays the graph-less DOOR every earlier build wrote.
{
    var animDir = Path.Combine(Path.GetTempPath(), "fo4sf-loadanim-" + Guid.NewGuid().ToString("N"));
    var outDir = Path.Combine(animDir, "out");
    Directory.CreateDirectory(outDir);
    var stdout = Console.Out;
    try
    {
        var manifest = Path.Combine(animDir, "manifest.json");
        File.WriteAllText(manifest, """
{"items":[
 {"editor_id":"FO4Port_SynthDoorLoad","model":"fo4port\\doorload.nif","source":"meshes\\doors\\doorload.nif",
  "load_door":{"bounds":[[-1,-0.1,0],[1,0.1,2.2]],
   "anim":{"anim_graph":"AnimTextData\\Tables\\Graphs\\SimpleOpenClose01.agx","skeleton":"t\\skeleton.rig","animations":"t\\animations",
           "origin_offset":[0.5,0,0],"bounds":[[-1.5,-0.1,0],[0.5,0.1,2.2]],"model":"fo4port\\door.nif","twin":"meshes\\doors\\door.nif",
           "open_seconds":1.0333}}},
 {"editor_id":"FO4Port_SynthPlainLoad","model":"fo4port\\plainload.nif","source":"meshes\\doors\\plainload.nif",
  "load_door":{"bounds":[[-1,-0.1,0],[1,0.1,2.2]]}},
 {"editor_id":"FO4Port_SynthTplLoad","model":"fo4port\\tplload.nif","source":"meshes\\doors\\tplload.nif",
  "load_door":{"bounds":[[-1,-0.1,0],[1,0.1,2.2]],"fo4_door_flags":138,
   "anim":{"anim_graph":"AnimTextData\\Tables\\Graphs\\SimpleOpenClose01.agx","skeleton":"ak\\skeleton.rig","animations":"ak\\animations",
           "origin_offset":[0,0,0],"bounds":[[-1,-0.1,0],[1,0.1,2.2]],"open_seconds":1.0333,
           "xtel_anim_graph":"AnimTextData\\Tables\\Graphs\\SimpleOpenClose02_Load.agx",
           "open_sound":{"start":"11111111-2222-3333-4444-555555555555","stop":"00000000-0000-0000-0000-000000000000","condition":null,"mapping":"000ABC:Starfield.esm"},
           "close_sound":{"start":"66666666-2222-3333-4444-555555555555","stop":"00000000-0000-0000-0000-000000000000"}}}}]}
""");
        var export = Path.Combine(animDir, "Anim.json");
        File.WriteAllText(export, """
{"cell":"Anim","formkey":"cell","refs":[
 {"formkey":"000A01:Fallout4.esm","base_editor_id":"DL","type":"Door","model":"doors\\doorload.nif","pos":[0,0,0],"rot":[0,0,0],"scale":1},
 {"formkey":"000A02:Fallout4.esm","base_editor_id":"PL","type":"Door","model":"doors\\plainload.nif","pos":[70,0,0],"rot":[0,0,0],"scale":1},
 {"formkey":"000A03:Fallout4.esm","base_editor_id":"TL","type":"Door","model":"doors\\tplload.nif","pos":[140,0,0],"rot":[0,0,0],"scale":1,"teleport_destination":{"door":"000A04:Fallout4.esm","pos":[0,0,0],"rot":[0,0,0],"flags":0,"transition_interior":null}},
 {"formkey":"000A04:Fallout4.esm","base_editor_id":"TL","type":"Door","model":"doors\\tplload.nif","pos":[210,0,0],"rot":[0,0,0],"scale":1,"teleport_destination":{"door":"000A03:Fallout4.esm","pos":[0,0,0],"rot":[0,0,0],"flags":0,"transition_interior":null}},
 {"formkey":"000A05:Fallout4.esm","base_editor_id":"TL","type":"Door","model":"doors\\tplload.nif","pos":[280,0,0],"rot":[0,0,0],"scale":1}]}
""");
        foreach (var hook in new[] { "FO4PORT_DOOR_MODEL", "FO4PORT_DOOR_BASE", "FO4PORT_DOORTEST" }) Environment.SetEnvironmentVariable(hook, null);
        Environment.SetEnvironmentVariable("STARFIELD_DATA", animDir);
        var log = new StringWriter();
        Console.SetOut(log);
        typeof(TeleportLinks).Assembly.EntryPoint!.Invoke(null, new object[] { new[] { outDir, manifest, export } });
        Console.SetOut(stdout);
        var ids = StableFormIds.Load(Path.Combine(outDir, "formids.json"));
        var port = ModKey.FromNameAndExtension("FO4Port.esm");
        var spikeMasters = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        spikeMasters.Set(new KeyedMasterStyle(ModKey.FromNameAndExtension("Starfield.esm"), MasterStyle.Full));
        using var written = StarfieldMod.CreateFromBinaryOverlay(Path.Combine(outDir, "FO4Port.esm"), release,
            new BinaryReadParameters { MasterFlagsLookup = spikeMasters });
        var doorsBy = written.Doors.ToDictionary(x => x.EditorID!);
        var animated = doorsBy["FO4Port_SynthDoorLoad"];
        var graph = animated.Components.OfType<IAnimationGraphComponentGetter>().Single();
        Require(graph.ANAM == "AnimTextData\\Tables\\Graphs\\SimpleOpenClose01.agx" && graph.BNAM == "t\\skeleton.rig" && graph.CNAM == "t\\animations",
                "animated load door lost its graph, skeleton or clips");
        Require(AssetPath(animated.Model?.File)?.EndsWith("fo4port/door.nif") == true, "animated load door does not use the twin's rigged model: " + AssetPath(animated.Model?.File));
        Require(animated.ObjectBounds.First.X == -1.5f && animated.ObjectBounds.Second.X == 0.5f, "animated load door keeps the static model's bounds");
        var plainDoor = doorsBy["FO4Port_SynthPlainLoad"];
        Require(!plainDoor.Components.Any() && AssetPath(plainDoor.Model?.File)?.EndsWith("fo4port/plainload.nif") == true, "a load door without anim changed");
        var cellRec = written.Cells.Records.SelectMany(x => x.SubBlocks).SelectMany(x => x.Cells).Single();
        var refs = cellRec.Temporary.Concat(cellRec.Persistent).OfType<IPlacedObjectGetter>().ToDictionary(r => r.FormKey);
        IPlacedObjectGetter Ref(string fo4) => refs[new FormKey(port, ids[$"REFR:FO4Port_Anim:{fo4}:Fallout4.esm"])];
        // a template-rigged load door with xtel_anim_graph: its XTEL references play the vanilla load graph on a copy of the
        // record (same model, skeleton and clips); a reference of the same door without an XTEL (scripted) keeps the original
        var tpl = doorsBy["FO4Port_SynthTplLoad"];
        var tplXtel = doorsBy["FO4Port_SynthTplLoad_XtelLoad"];
        var xg = tplXtel.Components.OfType<IAnimationGraphComponentGetter>().Single();
        Require(xg.ANAM == "AnimTextData\\Tables\\Graphs\\SimpleOpenClose02_Load.agx" && xg.BNAM == "ak\\skeleton.rig" && xg.CNAM == "ak\\animations",
                "XTEL copy lost the load graph, skeleton or clips");
        Require(tpl.Components.OfType<IAnimationGraphComponentGetter>().Single().ANAM.EndsWith("SimpleOpenClose01.agx"), "scripted record lost its graph");
        Require(AssetPath(tplXtel.Model?.File) == AssetPath(tpl.Model?.File), "XTEL copy has another model");
        // load_door_anim.py flags: FO4's FNAM bits on both records (0x8A: Automatic and Minimal Use; 0x80 is not an FO4 bit and
        // is dropped); a door without fo4_door_flags keeps 0
        Require((int)tpl.Flags == 0x0A && (int)tplXtel.Flags == 0x0A, $"FO4 door flags not copied: {tpl.Flags} / {tplXtel.Flags}");
        Require((int)plainDoor.Flags == 0 && (int)animated.Flags == 0, "door flags written without fo4_door_flags");
        Require(Ref("000A03").Base.FormKey == tplXtel.FormKey && Ref("000A04").Base.FormKey == tplXtel.FormKey, "XTEL references not on the load-graph copy");
        Require(Ref("000A03").TeleportDestination != null && Ref("000A05").TeleportDestination == null && Ref("000A05").Base.FormKey == tpl.FormKey,
                "reference without an XTEL moved onto the load-graph copy");
        // load_door_anim.py sounds: the vanilla door's WWise events on both records; doors without them stay silent
        foreach (var r in new[] { tpl, tplXtel })
            Require(r.OpenSound?.Start == Guid.Parse("11111111-2222-3333-4444-555555555555") && r.OpenSound.EventMapping.FormKey.ID == 0xABC
                    && r.CloseSound?.Start == Guid.Parse("66666666-2222-3333-4444-555555555555") && r.CloseSound.EventMapping.IsNull,
                    "vanilla door sounds not written on " + r.EditorID);
        Require(animated.OpenSound == null && plainDoor.OpenSound == null, "sounds written on a door without them");
        Require(!doorsBy.ContainsKey("FO4Port_SynthDoorLoad_XtelLoad"), "load-graph copy written for a rig without xtel_anim_graph");
        Require(log.ToString().Contains("2 animated load doors on their load graph"), "load-graph moves not reported:\n" + log);
        Require(Math.Abs(Ref("000A01").Position.X - 0.5f) < 1e-5 && Ref("000A01").Base.FormKey == animated.FormKey, "animated load door reference not shifted by the rig's origin offset");
        Require(Math.Abs(Ref("000A02").Position.X - 1f) < 1e-5 && Ref("000A02").Base.FormKey == plainDoor.FormKey, "plain load door reference moved");
        Require(log.ToString().Contains("3 load doors (2 open before the trip)"), "animated load doors not counted:\n" + log);
    }
    finally { Console.SetOut(stdout); Directory.Delete(animDir, true); }
}
Console.WriteLine("Animated load-door checks passed.");

// Interior promotions (Promotions.cs, scripts/terrain/port_promote.py): PluginSpike end to end with a promote.json. FO4
// containers, inventory items, activators and terminals get a CONT / MISC / ACTI / TERM + TMLM base carrying the model
// their STAT / MSTT would have had, shared per edid; the reference keeps its stable REFR FormID; a door base is kept; two
// entries of one edid that disagree stop the build.
{
    var promoDir = Path.Combine(Path.GetTempPath(), "fo4sf-promote-" + Guid.NewGuid().ToString("N"));
    var outDir = Path.Combine(promoDir, "out");
    Directory.CreateDirectory(outDir);
    var stdout = Console.Out;
    var sfKey = ModKey.FromNameAndExtension("Starfield.esm");
    try
    {
        // a synthetic master holding the vanilla terminal template 0155A2 with a furniture block
        var master = new StarfieldMod(sfKey, release);
        master.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        var marker = new Keyword(new FormKey(sfKey, 0x000900), release) { EditorID = "SynthFurnitureKeyword" };
        master.Keywords.Add(marker);
        master.Terminals.Add(new Terminal(new FormKey(sfKey, 0x0155A2), release)
        {
            EditorID = "OE_AustinF_DeployMicrobe_Terminal", MarkerModel = "Furniture\\furn_human_standingterminal.nif",
            Keywords = new ExtendedList<IFormLinkGetter<IKeywordGetter>> { new FormLink<IKeywordGetter>(marker.FormKey) },
        });
        // and a vanilla chair template 0027D5 (as NPCChairTech03_Free_270: one marker, one Sit entry block)
        master.Furniture.Add(new Furniture(new FormKey(sfKey, 0x0027D5), release)
        {
            EditorID = "NPCChairTech03_Free_270", MarkerModel = "Markers\\FurnitureMarkers\\ChairNeutral_Free_Marker.nif",
            Keywords = new ExtendedList<IFormLinkGetter<IKeywordGetter>> { new FormLink<IKeywordGetter>(marker.FormKey) },
            MarkerParameters = new ExtendedList<FurnitureMarkerParameters> { new FurnitureMarkerParameters { Offset = new P3Float(0, 0.12f, 0) } },
            MarkerEntryPoints = new ExtendedList<FurnitureMarkerEntryPoints> { new FurnitureMarkerEntryPoints() },
        });
        var sfPath = Path.Combine(promoDir, "Starfield.esm");
        master.BeginWrite.ToPath(sfPath).WithNoLoadOrder().Write();
        var manifest = Path.Combine(promoDir, "manifest.json");
        File.WriteAllText(manifest, """
{"items":[
 {"editor_id":"FO4Port_Crate","model":"fo4port\\crate.nif","source":"meshes\\crate.nif"},
 {"editor_id":"FO4Port_Can","model":"fo4port\\can.nif","source":"meshes\\can.nif","movable":{"mass_kg":1}},
 {"editor_id":"FO4Port_Switch","model":"fo4port\\switch.nif","source":"meshes\\switch.nif"},
 {"editor_id":"FO4Port_Term","model":"fo4port\\term.nif","source":"meshes\\term.nif"},
 {"editor_id":"FO4Port_SynthDoor","model":"fo4port\\d.nif","source":"meshes\\d.nif",
  "door":{"anim_graph":"SimpleOpenClose01.agx","skeleton":"fo4port\\d\\skeleton.rig","animations":"fo4port\\d\\animations","origin_offset":[0,0,0]}},
 {"editor_id":"FO4Port_Chair","model":"fo4port\\chair.nif","source":"meshes\\chair.nif"},
 {"editor_id":"FO4Port_Wall","model":"fo4port\\wall.nif","source":"meshes\\wall.nif"}]}
""");
        // an activate parents block as Fo4Export writes it (PR #305): flags + parents [{reference, delay}]
        string Parents(string parent, float delay) => $$"""{"reference":"{{parent}}:Fallout4.esm","delay":{{delay}}}""";
        string R(string id, string type, string model, string? parents = null, uint flags = 0) =>
            $$"""{"formkey":"{{id}}:Fallout4.esm","base_editor_id":"X","type":"{{type}}","model":"{{model}}","pos":[0,0,0],"rot":[0,0,0],"scale":1""" +
            (parents == null ? "}" : $$$""","activate_parents":{"flags":{{{flags}}},"parents":[{{{parents}}}]}}""");
        var export = Path.Combine(promoDir, "Promo.json");
        File.WriteAllText(export, "{\"cell\":\"Promo\",\"refs\":[" + string.Join(",",
            R("000901", "Container", "crate.nif"), R("000902", "MiscItem", "can.nif"), R("000903", "MiscItem", "can.nif"),
            R("000904", "Activator", "switch.nif"), R("000905", "Terminal", "term.nif", Parents("0009FF", 0)),
            R("000906", "Door", "d.nif", Parents("000904", 0.5f), 1), R("000908", "Static", "wall.nif", Parents("000901", 0)),
            R("000909", "Furniture", "chair.nif"), R("00090A", "Furniture", "chair.nif"),
            // a second switch drives two FO4 doors, one of them not converted (no model in the manifest): no partial wire
            R("00090B", "Activator", "switch.nif"), R("00090C", "Door", "d.nif", Parents("00090B", 0)),
            R("00090D", "Door", "unconverted.nif", Parents("00090B", 0))) + "]}");
        string Promote(string canName) => $$"""
{"starfield_esm": {{JsonSerializer.Serialize(sfPath)}},
 "containers":[{"src":"000901:Fallout4.esm","edid":"FO4Port_cont_A","name":"Crate","items":[{"form":"Starfield.esm:00000F","count":10}]},
               {"src":"000906:Fallout4.esm","edid":"FO4Port_cont_D","name":"Door","items":[]},
               {"src":"000907:Fallout4.esm","edid":"FO4Port_cont_A","name":"Crate","items":[{"form":"Starfield.esm:00000F","count":10}]}],
 "items":[{"src":"000902:Fallout4.esm","edid":"FO4Port_misc_B","name":"Can","value":1,"weight":0.5},
          {"src":"000903:Fallout4.esm","edid":"FO4Port_misc_B","name":"{{canName}}","value":1,"weight":0.5}],
 "activators":[{"src":"000904:Fallout4.esm","edid":"FO4Port_acti_C","name":null},
               {"src":"00090B:Fallout4.esm","edid":"FO4Port_acti_C","name":null}],
 "terminals":[{"src":"000905:Fallout4.esm","edid":"FO4Port_term_E","menu_edid":"FO4Port_tmlm_E","name":"Terminal","body":"FO4 terminal"}],
 "furniture":[{"src":"000909:Fallout4.esm","edid":"FO4Port_furn_F","name":"Chair","template":"0027D5",
               "markers":[{"offset":[0,-0.2,0],"rotation_z":180},{"offset":[0.5,-0.2,0],"rotation_z":180}]},
              {"src":"00090A:Fallout4.esm","edid":"FO4Port_furn_G","name":"Stool","template":"0027D5","markers":null}]}
""";
        File.WriteAllText(Path.Combine(outDir, "promote.json"), Promote("Can"));
        foreach (var hook in new[] { "FO4PORT_DOOR_MODEL", "FO4PORT_DOOR_BASE", "FO4PORT_DOORTEST" }) Environment.SetEnvironmentVariable(hook, null);
        Environment.SetEnvironmentVariable("STARFIELD_DATA", promoDir);
        var log = new StringWriter();
        Console.SetOut(log);
        typeof(Promotions).Assembly.EntryPoint!.Invoke(null, new object[] { new[] { outDir, manifest, export } });
        Console.SetOut(stdout);
        var ids = StableFormIds.Load(Path.Combine(outDir, "formids.json"));
        var port = ModKey.FromNameAndExtension("FO4Port.esm");
        var masters = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        masters.Set(new KeyedMasterStyle(sfKey, MasterStyle.Full));
        using (var written = StarfieldMod.CreateFromBinaryOverlay(Path.Combine(outDir, "FO4Port.esm"), release,
                   new BinaryReadParameters { MasterFlagsLookup = masters }))
        {
            var refs = written.Cells.Records.SelectMany(x => x.SubBlocks).SelectMany(x => x.Cells).Single()
                .Temporary.OfType<IPlacedObjectGetter>().ToDictionary(r => r.FormKey);
            FormKey BaseOf(string fo4) => refs[new FormKey(port, ids[$"REFR:FO4Port_Promo:{fo4}:Fallout4.esm"])].Base.FormKey;
            var cont = written.Containers.Single();
            Require(BaseOf("000901") == cont.FormKey && cont.FormKey.ID == ids["CONT:FO4Port_cont_A"], "container not on its CONT");
            Require(AssetPath(cont.Model?.File) == "Meshes/fo4port/crate.nif" && cont.Name!.String == "Crate"
                    && cont.Items!.Single().Item.Count == 10 && cont.Items!.Single().Item.Item.FormKey == new FormKey(sfKey, 0x00000F),
                    "CONT model, name or inventory wrong");
            var misc = written.MiscItems.Single();
            Require(BaseOf("000902") == misc.FormKey && BaseOf("000903") == misc.FormKey, "the two items do not share one MISC");
            Require(AssetPath(misc.Model?.File) == "Meshes/fo4port/can.nif" && misc.Name!.String == "Can" && misc.Value == 1 && misc.Weight == 0.5f,
                    "MISC model, name, value or weight wrong");
            var acti = written.Activators.Single();
            Require(BaseOf("000904") == acti.FormKey && acti.Name == null && AssetPath(acti.Model?.File) == "Meshes/fo4port/switch.nif",
                    "activator not on a nameless ACTI with its model");
            var term = written.Terminals.Single();
            var menu = written.TerminalMenus.Single();
            Require(BaseOf("000905") == term.FormKey && term.Menu.FormKey == menu.FormKey && term.Name!.String == "Terminal"
                    && term.MarkerModel == "Furniture\\furn_human_standingterminal.nif" && term.Keywords!.Single().FormKey == marker.FormKey
                    && menu.BodyTexts!.Single().Text.String == "FO4 terminal", "terminal, its furniture block or its menu wrong");
            Require(written.Doors.Any(d => d.FormKey == BaseOf("000906")), "a door listed for promotion lost its DOOR base");
            // chairs: copies of the vanilla template with our model, the FO4 name and FO4's marker places
            var chair = written.Furniture.Single(f => f.FormKey == BaseOf("000909"));
            var stool = written.Furniture.Single(f => f.FormKey == BaseOf("00090A"));
            Require(chair.EditorID == "FO4Port_furn_F" && AssetPath(chair.Model?.File) == "Meshes/fo4port/chair.nif" && chair.Name!.String == "Chair"
                    && chair.MarkerModel == "Markers\\FurnitureMarkers\\ChairNeutral_Free_Marker.nif" && chair.Keywords!.Single().FormKey == marker.FormKey,
                    "chair not a copy of the template with our model and name");
            Require(chair.MarkerParameters!.Count == 2 && chair.MarkerEntryPoints!.Count == 2
                    && Math.Abs(chair.MarkerParameters[1].Offset.X - 0.5f) < 1e-6 && Math.Abs(chair.MarkerParameters[0].RotationZ - 180f) < 1e-4,
                    "chair markers not FO4's places");
            Require(stool.MarkerParameters!.Single().Offset.Y == 0.12f && stool.Name!.String == "Stool", "a chair without FO4 markers lost the template's");
            // the switch (a promoted activator) activates the door it is FO4's activate parent of
            IPlacedObjectGetter RefOf(string fo4) => refs[new FormKey(port, ids[$"REFR:FO4Port_Promo:{fo4}:Fallout4.esm"])];
            var wire = RefOf("000904");
            Require(wire.VirtualMachineAdapter?.Scripts.Single().Name == "DefaultActivateLinkedRefOnActivate"
                    && wire.LinkedReferences.Single().Reference.FormKey == RefOf("000906").FormKey
                    && wire.LinkedReferences.Single().KeywordOrReference.FormKey == new FormKey(sfKey, 0x5D5E7),
                    "switch -> door activation chain not written");
            Require(RefOf("00090B").VirtualMachineAdapter == null && RefOf("00090B").LinkedReferences.Count == 0
                    && RefOf("00090C").VirtualMachineAdapter == null,
                    "a switch whose second FO4 child was not converted got a partial one-child wire");
            Require(RefOf("000901").VirtualMachineAdapter == null && RefOf("000901").LinkedReferences.Count == 0,
                    "a container (not a usable parent) got an activation wire");
            Require(written.Statics.Any(s => s.FormKey == BaseOf("000908")) && written.Statics.Count == 5
                    && written.MoveableStatics.Count == 1, "unlisted wall moved, or the promoted models' own bases missing");
        }
        var text = log.ToString();
        var unwired = JsonDocument.Parse(File.ReadAllText(Path.Combine(outDir, "activation.json"))).RootElement.ToString();
        Require(unwired.Contains("00090D:Fallout4.esm: parent drives 2 children (one linked ref per script) (child not placed)"),
                "the unconverted child of a two-child switch is not named in activation.json:\n" + unwired);
        Require(text.Contains("promotions: 2 activators, 1 containers, 2 furniture, 2 items, 1 kept (door base), 1 terminals; 1 listed but not placed"),
                "promotions not reported:\n" + text);
        Require(text.Contains("activation chains: 1 wired; unwired: 1 parent not placed, 1 parent not usable, 2 parent drives several, " +
                              "0 parent already scripted, 1 child not placed; 1 delays and 1 parent-activate-only flags not carried"),
                "activation chains not reported:\n" + text);
        // a second build keeps every FormID; a disagreeing entry of one edid stops it
        var before = File.ReadAllText(Path.Combine(outDir, "formids.json"));
        File.WriteAllText(Path.Combine(outDir, "promote.json"), Promote("Tin"));
        var refused = false;
        Console.SetOut(new StringWriter());
        try { typeof(Promotions).Assembly.EntryPoint!.Invoke(null, new object[] { new[] { outDir, manifest, export } }); }
        catch (System.Reflection.TargetInvocationException ex) when (ex.InnerException is InvalidDataException ide && ide.Message.Contains("FO4Port_misc_B"))
        { refused = true; }
        Console.SetOut(stdout);
        Require(refused, "two entries of one edid with different names were not refused");
        Require(File.ReadAllText(Path.Combine(outDir, "formids.json")) == before, "a refused build changed the FormID map");
    }
    finally { Console.SetOut(stdout); Directory.Delete(promoDir, true); }
}
Console.WriteLine("Interior promotion checks passed.");

// Door names (DoorNames.cs): PluginSpike end to end. Each FO4 name of a converted model gets a stable copy of its DOOR
// base that keeps the animation graph, and that name's references move to it. No name, or a name that is not one line,
// stays on the base as "Door". A grown export with the same map keeps every old reference on its old base and name.
{
    var nameDir = Path.Combine(Path.GetTempPath(), "fo4sf-doornames-" + Guid.NewGuid().ToString("N"));
    var outDir = Path.Combine(nameDir, "out");
    Directory.CreateDirectory(outDir);
    var stdout = Console.Out;
    try
    {
        var manifest = Path.Combine(nameDir, "manifest.json");
        File.WriteAllText(manifest, """
{"items":[
 {"editor_id":"FO4Port_SynthDoor","model":"fo4port\\d.nif","source":"meshes\\doors\\d.nif",
  "door":{"anim_graph":"SimpleOpenClose01.agx","skeleton":"fo4port\\d\\skeleton.rig","animations":"fo4port\\d\\animations",
          "origin_offset":[0,0,0]}},
 {"editor_id":"FO4Port_SynthHatch","model":"fo4port\\h.nif","source":"meshes\\doors\\h.nif","load_door":{"bounds":[[0,0,0],[1,1,1]]}}]}
""");
        string Ref(string fk, string baseKey, string model, float x) =>
            $$"""{"formkey":"{{fk}}:Fallout4.esm","base_editor_id":"B","base_formkey":"{{baseKey}}:Fallout4.esm","type":"Door","model":"{{model}}","pos":[{{x}},0,0],"rot":[0,0,0],"scale":1}""";
        string Base(string key, string name) => $"\"{key}:Fallout4.esm\":{{\"editor_id\":\"B\",\"model\":\"m\",\"record\":{{\"Name\":{name}}},\"scripts\":[]}}";
        var export = Path.Combine(nameDir, "Synth.json");
        var oldRefs = new[] {
            Ref("000901", "00A001", "doors\\\\d.nif", 0), Ref("000902", "00A001", "doors\\\\d.nif", 70),
            Ref("000903", "00A002", "doors\\\\d.nif", 140), Ref("000904", "00A003", "doors\\\\d.nif", 210),
            Ref("000906", "00A005", "doors\\\\d.nif", 280), Ref("000905", "00A004", "doors\\\\h.nif", 350) };
        var bases = new[] { Base("00A001", "\"Front Door\""), Base("00A002", "\" Storage Room \""),
            Base("00A003", "null"), Base("00A005", "\"bad\\nname\""), Base("00A004", "\"Roof Hatch\""), Base("00A006", "\"Back Door\"") };
        void WriteExport(IEnumerable<string> refList) => File.WriteAllText(export, "{\"cell\":\"Synth\",\"formkey\":\"cell\",\"refs\":[" +
            string.Join(",", refList) + "],\"door_bases\":{" + string.Join(",", bases) + "}}");
        WriteExport(oldRefs);
        foreach (var hook in new[] { "FO4PORT_DOOR_MODEL", "FO4PORT_DOOR_BASE", "FO4PORT_DOORTEST" }) Environment.SetEnvironmentVariable(hook, null);
        Environment.SetEnvironmentVariable("STARFIELD_DATA", nameDir);
        var log = new StringWriter();
        Console.SetOut(log);
        typeof(DoorNames).Assembly.EntryPoint!.Invoke(null, new object[] { new[] { outDir, manifest, export } });
        Console.SetOut(stdout);
        var ids = StableFormIds.Load(Path.Combine(outDir, "formids.json"));
        var port = ModKey.FromNameAndExtension("FO4Port.esm");
        var masters = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        masters.Set(new KeyedMasterStyle(ModKey.FromNameAndExtension("Starfield.esm"), MasterStyle.Full));
        // FO4 ref -> its DOOR base's ID and name, as written
        Dictionary<string, (uint id, string? name)> Bindings(IEnumerable<string> fo4Refs)
        {
            using var written = StarfieldMod.CreateFromBinaryOverlay(Path.Combine(outDir, "FO4Port.esm"), release,
                new BinaryReadParameters { MasterFlagsLookup = masters });
            var doorsByKey = written.Doors.ToDictionary(x => x.FormKey);
            var placed = written.Cells.Records.SelectMany(x => x.SubBlocks).SelectMany(x => x.Cells).Single()
                .Temporary.OfType<IPlacedObjectGetter>().ToDictionary(r => r.FormKey);
            var map = StableFormIds.Load(Path.Combine(outDir, "formids.json"));
            return fo4Refs.ToDictionary(fo4 => fo4, fo4 =>
            {
                var door = doorsByKey[placed[new FormKey(port, map[$"REFR:FO4Port_Synth:{fo4}:Fallout4.esm"])].Base.FormKey];
                return (door.FormKey.ID, door.Name?.String);
            });
        }
        using (var written = StarfieldMod.CreateFromBinaryOverlay(Path.Combine(outDir, "FO4Port.esm"), release,
                   new BinaryReadParameters { MasterFlagsLookup = masters }))
        {
            var doorsByKey = written.Doors.ToDictionary(x => x.FormKey);
            var refs = written.Cells.Records.SelectMany(x => x.SubBlocks).SelectMany(x => x.Cells).Single()
                .Temporary.OfType<IPlacedObjectGetter>().ToDictionary(r => r.FormKey);
            IDoorGetter DoorOf(string fo4) => doorsByKey[refs[new FormKey(port, ids[$"REFR:FO4Port_Synth:{fo4}:Fallout4.esm"])].Base.FormKey];
            Require(DoorOf("000901").Name?.String == "Front Door" && DoorOf("000902").FormKey == DoorOf("000901").FormKey &&
                    DoorOf("000901").FormKey.ID == ids["DOOR:FO4Port_SynthDoor|name:Front Door"], "FO4 name's copy not shared:\n" + log);
            var storage = DoorOf("000903");
            Require(storage.Name?.String == "Storage Room" && storage.FormKey.ID == ids["DOOR:FO4Port_SynthDoor|name:Storage Room"] &&
                    storage.EditorID != "FO4Port_SynthDoor" && storage.Components.OfType<IAnimationGraphComponentGetter>().Single().ANAM == "SimpleOpenClose01.agx",
                "name's copy wrong (name, stable id, editor id or graph)");
            Require(DoorOf("000904").Name?.String == "Door" && DoorOf("000906").FormKey == DoorOf("000904").FormKey &&
                    DoorOf("000904").FormKey.ID == ids["DOOR:FO4Port_SynthDoor"], "unnamed and refused names not kept on the base as Door");
            Require(DoorOf("000905").Name?.String == "Roof Hatch", "load door not named");
            Require(written.Doors.Select(x => x.EditorID).Distinct().Count() == written.Doors.Count, "door editor ids collide");
        }
        Require(log.ToString().Contains("door names: 3 named copies of door bases (4 references moved), " +
                                        "2 door references without an FO4 name, 1 refused"), "door names not reported:\n" + log);
        // a second build allocates nothing new
        var before = File.ReadAllText(Path.Combine(outDir, "formids.json"));
        var old = Bindings(new[] { "000901", "000902", "000903", "000904", "000905", "000906" });
        File.Delete(Path.Combine(outDir, "FO4Port.esm"));
        Console.SetOut(new StringWriter());
        typeof(DoorNames).Assembly.EntryPoint!.Invoke(null, new object[] { new[] { outDir, manifest, export } });
        Console.SetOut(stdout);
        Require(File.ReadAllText(Path.Combine(outDir, "formids.json")) == before, "a repeat build changed the FormID map");
        // growth with the same map (Codex, #400): Storage Room and a new name outnumber Front Door, references reordered;
        // every old reference keeps its base and name
        WriteExport(new[] { Ref("000910", "00A006", "doors\\\\d.nif", 420), Ref("000907", "00A002", "doors\\\\d.nif", 490),
                            Ref("000908", "00A002", "doors\\\\d.nif", 560), Ref("000911", "00A006", "doors\\\\d.nif", 630),
                            Ref("000909", "00A002", "doors\\\\d.nif", 700), Ref("000912", "00A006", "doors\\\\d.nif", 770) }
                    .Concat(Enumerable.Reverse(oldRefs)));
        File.Delete(Path.Combine(outDir, "FO4Port.esm"));
        Console.SetOut(new StringWriter());
        typeof(DoorNames).Assembly.EntryPoint!.Invoke(null, new object[] { new[] { outDir, manifest, export } });
        Console.SetOut(stdout);
        var grown = Bindings(old.Keys.Concat(new[] { "000907", "000910" }));
        foreach (var (fo4, binding) in old)
            Require(grown[fo4] == binding, $"growth moved {fo4} from {binding} to {grown[fo4]}");
        Require(grown["000907"] == old["000903"] && grown["000910"].name == "Back Door" &&
                grown["000910"].id == StableFormIds.Load(Path.Combine(outDir, "formids.json"))["DOOR:FO4Port_SynthDoor|name:Back Door"],
            "grown references not on their names' copies");
    }
    finally { Console.SetOut(stdout); Directory.Delete(nameDir, true); }
}
Console.WriteLine("Door name checks passed.");
