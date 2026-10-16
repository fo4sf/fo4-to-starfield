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
    var spikeDir = Path.Combine(Path.GetTempPath(), "fo4sf-doorstate-" + Guid.NewGuid().ToString("N"));
    var outDir = Path.Combine(spikeDir, "out");
    Directory.CreateDirectory(outDir);
    var stdout = Console.Out;
    try
    {
        var manifest = Path.Combine(spikeDir, "manifest.json");
        File.WriteAllText(manifest, """
{"items":[
 {"editor_id":"FO4Port_SynthDoor","model":"fo4port\\d.nif","source":"meshes\\doors\\d.nif",
  "door":{"anim_graph":"SimpleOpenClose01.agx","skeleton":"fo4port\\d\\skeleton.rig","animations":"fo4port\\d\\animations",
          "origin_offset":[0,0,0],"rig":"native"}},
 {"editor_id":"FO4Port_SynthWall","model":"fo4port\\w.nif","source":"meshes\\w.nif"}]}
""");
        var export = Path.Combine(spikeDir, "Synth.json");
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
        Environment.SetEnvironmentVariable("STARFIELD_DATA", spikeDir);
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
    finally { Console.SetOut(stdout); Directory.Delete(spikeDir, true); }
}
Console.WriteLine("Own-rig XTEL guard and PluginSpike door-state checks passed.");
