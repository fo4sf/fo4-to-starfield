// Synthetic checks for TeleportLinks (load-door teleports between converted cells). No game data: two synthetic cells, a
// graph-less DOOR base, a STAT base, hand-written cell exports.
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
