// Load-door teleports (XTEL) between converted cells of one build.
//
// A Fallout 4 load door is a persistent DOOR reference whose TeleportDestination (XTEL) names the reference at the other end
// and the arrival point: an absolute position / rotation in the destination cell. Starfield keeps the same layout. Measured
// on Starfield.esm (dotnet/SfInspect `teleports`, 3,291,860 placed objects scanned, docs/ai/research-log.md 2026-10-10):
// 964 placed objects carry an XTEL; all 964 have a DOOR base, sit in their cell's persistent group with record flag 0x400,
// and their destination's XTEL links back to them; TransitionInterior is never set; 458 of the DOOR bases have no animation
// graph at all (hidden elevator doors, automatic cave doors), so the teleport needs no graph; whether a visible graph-less door
// also teleports on the player's activation is an in-game check still to do. The arrival point is an absolute position in the
// destination cell (median 1.0 m from the destination door's own position, p90 5.67 m).
//
// Apply() writes that link on every placed reference whose export carries an XTEL and whose destination reference is placed
// in the same build (any of the cell exports given to the writer). Both ends become persistent. Doors whose other end is
// not in the build keep no XTEL: they stay shut and solid (the Python converter keeps their native collision) and are listed.
using System.Text.Json;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;

public sealed record TeleportIssue(string Source, string Target, string Reason);

public sealed class TeleportReport
{
    public int Linked { get; set; }                 // references that received an XTEL
    public int LoadGraph { get; set; }              // of those, animated load doors moved onto their *_Load graph record
    public int Pairs { get; set; }                  // mutual pairs: both ends link each other (counted once per pair)
    public int OneWay { get; set; }                 // destination placed, but it has no XTEL back to the source
    public int DestinationNotInBuild { get; set; }  // destination reference not placed: its cell is not in this build or its model was not converted
    public int SourceNotPlaced { get; set; }        // the exported XTEL sits on a reference that was not placed (its model was not converted)
    public List<string> Unlinked { get; } = new();  // "<cell> <source ref> -> <destination ref>" for DestinationNotInBuild
    public List<string> UnplacedSources { get; } = new();   // same format, for SourceNotPlaced
    public List<TeleportIssue> Issues { get; } = new();
}

public static class TeleportLinks
{
    public const float UnitsPerMetre = 70f;   // same as PluginSpike positions

    /// <summary>placed: source Fallout 4 reference FormKey (as exported) -> the placed Starfield reference and its cell.
    /// ownRig: DOOR bases with their own opening rig (manifest rig "native"). An FO4 load reference that shares such a
    /// door's model (the vault / utility elevator load doors) would get an XTEL on a door that plays an opening graph;
    /// until it has its own load record it is reported, not linked (review of PR #242).
    /// loadGraphBases: animated load doors (manifest load_door.anim with xtel_anim_graph) -> the copy of their record that
    /// plays the vanilla *_Load graph; a linked reference is moved onto that copy (same model and rig, so no offset).</summary>
    public static TeleportReport Apply(StarfieldMod mod, IReadOnlyDictionary<string, (PlacedObject obj, Cell cell)> placed,
        IEnumerable<JsonElement> exports, IReadOnlySet<FormKey>? ownRig = null,
        IReadOnlyDictionary<FormKey, FormKey>? loadGraphBases = null)
    {
        var report = new TeleportReport();
        var doors = mod.Doors.Select(d => d.FormKey).ToHashSet();
        bool IsDoor(PlacedObject o) => doors.Contains(o.Base.FormKey);
        var linked = new Dictionary<FormKey, FormKey>();   // source ref -> destination ref (pair / one-way count)
        foreach (var export in exports)
        {
            var cellName = export.TryGetProperty("cell", out var cn) ? cn.GetString() ?? "" : "";
            foreach (var r in export.GetProperty("refs").EnumerateArray())
            {
                if (!r.TryGetProperty("teleport_destination", out var tel) || tel.ValueKind == JsonValueKind.Null) continue;
                var source = r.GetProperty("formkey").GetString()!;
                var doorKey = tel.GetProperty("door").GetString();
                if (!placed.TryGetValue(source, out var from))                   // model not converted: nothing placed to link
                {
                    report.SourceNotPlaced++;
                    report.UnplacedSources.Add($"{cellName} {source} -> {doorKey}");
                    continue;
                }
                if (doorKey == null) { report.Issues.Add(new(source, "", "XTEL without a destination door")); continue; }
                if (!placed.TryGetValue(doorKey, out var to))
                {
                    report.DestinationNotInBuild++;
                    report.Unlinked.Add($"{cellName} {source} -> {doorKey}");
                    continue;
                }
                var flags = tel.GetProperty("flags").GetUInt32();
                if ((flags & ~7u) != 0) { report.Issues.Add(new(source, doorKey, "unsupported XTEL flag bits")); continue; }
                if ((flags & 4u) != 0)                                           // FO4 RelativePosition; Starfield.esm never uses it (0 of 964)
                { report.Issues.Add(new(source, doorKey, "relative-position XTEL not implemented")); continue; }
                if (!IsDoor(from.obj))
                { report.Issues.Add(new(source, doorKey, "source base is not a DOOR record (model not marked load_door in the manifest)")); continue; }
                if (ownRig?.Contains(from.obj.Base.FormKey) == true)
                { report.Issues.Add(new(source, doorKey, "source DOOR has its own opening rig (manifest rig native), not a load-door record")); continue; }
                if (!IsDoor(to.obj)) { report.Issues.Add(new(source, doorKey, "destination base is not a DOOR record")); continue; }
                var pos = tel.GetProperty("pos");
                var rot = tel.GetProperty("rot");
                from.obj.TeleportDestination = new TeleportDestination
                {
                    Position = new P3Float(pos[0].GetSingle() / UnitsPerMetre, pos[1].GetSingle() / UnitsPerMetre, pos[2].GetSingle() / UnitsPerMetre),
                    Rotation = new P3Float(rot[0].GetSingle(), rot[1].GetSingle(), rot[2].GetSingle()),
                    Flags = (TeleportDestination.Flag)flags,
                };
                from.obj.TeleportDestination.Door.SetTo(to.obj.FormKey);
                if (loadGraphBases != null && loadGraphBases.TryGetValue(from.obj.Base.FormKey, out var loadBase))
                {
                    from.obj.Base.SetTo(loadBase);
                    report.LoadGraph++;
                }
                // transition_interior (FO4 elevator doors) is dropped: no XTEL in Starfield.esm sets it.
                MakePersistent(from);                                            // the engine resolves XTEL targets through the
                MakePersistent(to);                                              // persistent groups: every vanilla XTEL ref is persistent
                linked[from.obj.FormKey] = to.obj.FormKey;
                report.Linked++;
            }
        }
        foreach (var (a, b) in linked)
        {
            if (linked.TryGetValue(b, out var back) && back == a) { if (a.ID < b.ID) report.Pairs++; }
            else report.OneWay++;
        }
        return report;
    }

    static void MakePersistent((PlacedObject obj, Cell cell) p)
    {
        if (p.cell.Temporary.Remove(p.obj)) p.cell.Persistent.Add(p.obj);
        p.obj.MajorRecordFlagsRaw |= 0x400;
    }

    /// <summary>Reads a written plugin back (binary overlay, Starfield.esm as its only full master) and lists every XTEL.
    /// Offline verification only; returns the number of links.</summary>
    public static int List(string pluginPath, TextWriter output)
    {
        var masters = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        masters.Set(new KeyedMasterStyle(ModKey.FromNameAndExtension("Starfield.esm"), MasterStyle.Full));
        using var mod = StarfieldMod.CreateFromBinaryOverlay(pluginPath, StarfieldRelease.Starfield,
            new BinaryReadParameters { MasterFlagsLookup = masters });
        var cells = mod.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells).ToList();
        var refs = new List<(IPlacedObjectGetter r, ICellGetter c, bool persistent)>();
        foreach (var c in cells)
        {
            refs.AddRange(c.Persistent.OfType<IPlacedObjectGetter>().Select(r => (r, c, true)));
            refs.AddRange(c.Temporary.OfType<IPlacedObjectGetter>().Select(r => (r, c, false)));
        }
        var byKey = refs.ToDictionary(x => x.r.FormKey);
        var doors = mod.Doors.ToDictionary(d => d.FormKey);
        int n = 0;
        foreach (var (r, c, persistent) in refs)
        {
            var t = r.TeleportDestination;
            if (t == null) continue;
            n++;
            byKey.TryGetValue(t.Door.FormKey, out var dest);
            doors.TryGetValue(r.Base.FormKey, out var d);
            var back = dest.r?.TeleportDestination?.Door.FormKey == r.FormKey;
            output.WriteLine($"{c.EditorID} {r.FormKey} base={d?.EditorID ?? r.Base.FormKey.ToString()} persistent={persistent} " +
                             $"flags=0x{r.MajorRecordFlagsRaw:X} -> {dest.c?.EditorID ?? "?"} {t.Door.FormKey} " +
                             $"arrive=({t.Position.X:F2},{t.Position.Y:F2},{t.Position.Z:F2}) rot=({t.Rotation.X:F3},{t.Rotation.Y:F3},{t.Rotation.Z:F3}) " +
                             $"xtel={t.Flags} transition={t.TransitionInterior.FormKey} back={back}");
        }
        output.WriteLine($"{n} teleport links in {Path.GetFileName(pluginPath)}");
        return n;
    }
}
