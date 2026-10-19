// MergeProbe: does the overlay merge move a persistent reference that an ADD-ON plugin puts into a VANILLA overlay
// world? (docs/terrain/map-markers.md "Markers in the merged world", docs/slice/door-frames.md section 3.)
//
// Vanilla LC172World's persistent COC marker 0010238E reads merged in game (offset -500, -2300, -3.62:
// terrain_A2_lc172, merge_ctrl_lc172), while every persistent reference of our own overlay worlds reads its local
// position; giving our persistent cell vanilla's record shape (fix A, cave_fixA_1015) and WRLD OFST / CLSZ (fix E,
// cave_ofst_1015) both failed. FO4SFMergeProbe.esm separates the two remaining explanations with one reference:
//   0x800  REFR FO4SF_MergeProbeMarker  XMarker 00003B, persistent (0x400), in an override of LC172World's
//          persistent cell, at the reference marker's position + (offset, 0, 0)
// Read in game after `coc LC172Ext01` (the control run's arrival): `prid <load index>000800`, `getpos x / y`.
// Merged (about the marker's local + (-500, -2300)) means the cause lies in our WRLD / LCTN records; local means a
// persistent reference from a non-vanilla plugin never merges, and the runtime moves (door script, #353, #376) stay.
// The override copies the world and the persistent cell without their children (SliceDoor's WorldOnly / CellOnly).
//
// usage: MergeProbe build <Starfield.esm> <out dir> [--plugin FO4SFMergeProbe.esm] [--ref 10238E] [--offset 3]
//        MergeProbe check <plugin> <Starfield.esm> [--ref 10238E] [--offset 3]   (exit 1 on a mismatch)
using System.Globalization;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;

const uint WorldId = 0x02DF8C, ProbeId = 0x800, XMarker = 0x3B;    // LC172World (Mars), as dotnet/TerrainOverlays
const string ProbeEdid = "FO4SF_MergeProbeMarker";

static int Usage()
{
    Console.Error.WriteLine("usage: MergeProbe build <Starfield.esm> <out dir> [--plugin FO4SFMergeProbe.esm] [--ref 10238E] [--offset 3] | " +
                            "MergeProbe check <plugin> <Starfield.esm> [--ref 10238E] [--offset 3]");
    return 2;
}
if (args.Length < 3) return Usage();
string Arg(string name, string dflt) { var i = Array.IndexOf(args, name); return i >= 0 && i + 1 < args.Length ? args[i + 1] : dflt; }
var refId = Convert.ToUInt32(Arg("--ref", "10238E"), 16);
var offset = float.Parse(Arg("--offset", "3"), CultureInfo.InvariantCulture);

static string F(float v) => v.ToString("0.###", CultureInfo.InvariantCulture);
static string P(P3Float p) => $"({F(p.X)}, {F(p.Y)}, {F(p.Z)})";

// the vanilla world, its persistent cell and the reference marker in it
(IWorldspaceGetter World, ICellGetter Top, IPlacedObjectGetter Ref) Vanilla(IStarfieldModGetter sf)
{
    var w = sf.Worldspaces.FirstOrDefault(x => x.FormKey.ID == WorldId)
            ?? throw new InvalidDataException($"no WRLD {WorldId:X6} (LC172World) in {sf.ModKey}");
    var top = w.TopCell ?? throw new InvalidDataException($"{w.EditorID} has no persistent cell");
    var r = top.Persistent.OfType<IPlacedObjectGetter>().FirstOrDefault(x => x.FormKey.ID == refId)
            ?? throw new InvalidDataException($"no persistent REFR {refId:X6} in {w.EditorID}'s persistent cell");
    return (w, top, r);
}

if (args[0] == "build")
{
    using var sf = StarfieldMod.CreateFromBinaryOverlay(args[1], StarfieldRelease.Starfield);
    var (w0, top0, r0) = Vanilla(sf);
    var modKey = ModKey.FromFileName(Arg("--plugin", "FO4SFMergeProbe.esm"));
    var mod = new StarfieldMod(modKey, StarfieldRelease.Starfield);
    mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;     // as every plugin of ours that loads

    var w = w0.DeepCopy(new Worldspace.TranslationMask(defaultOn: true)
    {
        SubCells = new WorldspaceBlock.TranslationMask(defaultOn: false, onOverall: false),
        TopCell = new Cell.TranslationMask(defaultOn: false, onOverall: false),
    });
    w.SubCells.Clear();
    var top = top0.DeepCopy(new Cell.TranslationMask(defaultOn: true)
    {
        Persistent = false, Temporary = false,
        NavigationMeshes = new NavigationMesh.TranslationMask(defaultOn: false, onOverall: false),
    });
    top.Persistent.Clear();
    top.Temporary.Clear();
    top.NavigationMeshes.Clear();
    var probe = new PlacedObject(new FormKey(modKey, ProbeId), StarfieldRelease.Starfield)
    {
        EditorID = ProbeEdid,
        Base = new FormLinkNullable<IPlaceableObjectGetter>(new FormKey(sf.ModKey, XMarker)),
        Position = new P3Float(r0.Position.X + offset, r0.Position.Y, r0.Position.Z),
        Rotation = new P3Float(0, 0, 0),
    };
    probe.MajorRecordFlagsRaw |= 0x400;                                      // persistent, like the reference marker
    top.Persistent.Add(probe);
    w.TopCell = top;
    mod.Worldspaces.Add(w);
    mod.ModHeader.Stats.NextFormID = ProbeId + 1;

    Directory.CreateDirectory(args[2]);
    var path = Path.Combine(args[2], modKey.FileName);
    mod.BeginWrite.ToPath(path).WithLoadOrder(sf.ModKey).WithKnownMasters(new KeyedMasterStyle(sf.ModKey, MasterStyle.Full)).Write();
    Console.WriteLine($"wrote {path} ({new FileInfo(path).Length:N0} bytes): {ProbeEdid} {probe.FormKey} persistent in {w0.EditorID} " +
                      $"persistent cell {top0.FormKey} at {P(probe.Position)} (reference {r0.FormKey} {r0.EditorID} at {P(r0.Position)} + ({F(offset)}, 0, 0))");
    Console.WriteLine($"  merged reads about {P(new P3Float(probe.Position.X - 500, probe.Position.Y - 2300, probe.Position.Z - 3.62f))} " +
                      "(the control's offset -500, -2300, -3.62); local reads the position above");
    return 0;
}

if (args[0] == "check")
{
    using var sf = StarfieldMod.CreateFromBinaryOverlay(args[2], StarfieldRelease.Starfield);
    var (w0, top0, r0) = Vanilla(sf);
    var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
    styles.Set(new KeyedMasterStyle(sf.ModKey, MasterStyle.Full));
    using var mod = StarfieldMod.CreateFromBinaryOverlay(args[1], StarfieldRelease.Starfield, new BinaryReadParameters { MasterFlagsLookup = styles });
    var problems = new List<string>();
    var masters = mod.ModHeader.MasterReferences.Select(m => m.Master.FileName.String).ToList();
    Console.WriteLine($"{Path.GetFileName(args[1])}: header flags {mod.ModHeader.Flags}, masters [{string.Join(", ", masters)}], " +
                      $"{mod.Worldspaces.Count} WRLD");
    if (!masters.SequenceEqual(new[] { sf.ModKey.FileName.String })) problems.Add($"masters are not [{sf.ModKey.FileName}]");
    if (mod.Worldspaces.Count != 1) problems.Add("not exactly one WRLD");
    var w = mod.Worldspaces.FirstOrDefault();
    if (w == null || w.FormKey != w0.FormKey) problems.Add($"the WRLD is not an override of {w0.FormKey}");
    else
    {
        if (w.SubCells.Count != 0) problems.Add("the WRLD override carries exterior cells");
        if (w.TopCell == null || w.TopCell.FormKey != top0.FormKey) problems.Add($"the persistent cell is not an override of {top0.FormKey}");
        else
        {
            if (w.TopCell.MajorRecordFlagsRaw != top0.MajorRecordFlagsRaw)
                problems.Add($"persistent cell flags 0x{w.TopCell.MajorRecordFlagsRaw:X} differ from vanilla 0x{top0.MajorRecordFlagsRaw:X}");
            var refs = w.TopCell.Persistent.OfType<IPlacedObjectGetter>().ToList();
            if (refs.Count != 1 || w.TopCell.Temporary.Count != 0) problems.Add("the persistent cell does not hold exactly the probe");
            var pr = refs.FirstOrDefault();
            if (pr != null)
            {
                Console.WriteLine($"  {pr.FormKey} {pr.EditorID} base {pr.Base.FormKey} flags 0x{pr.MajorRecordFlagsRaw:X} at {P(pr.Position)}");
                if (pr.FormKey.ModKey != mod.ModKey || pr.FormKey.ID != ProbeId || pr.EditorID != ProbeEdid) problems.Add($"the probe is not {ProbeEdid} 0x{ProbeId:X}");
                if (pr.Base.FormKey != new FormKey(sf.ModKey, XMarker)) problems.Add("the probe's base is not XMarker 00003B");
                if ((pr.MajorRecordFlagsRaw & 0xC00) != 0x400) problems.Add("the probe is not persistent and enabled");
                var want = new P3Float(r0.Position.X + offset, r0.Position.Y, r0.Position.Z);
                if (pr.Position != want) problems.Add($"the probe is at {P(pr.Position)}, not {P(want)}");
            }
        }
    }
    foreach (var p in problems) Console.WriteLine("FAIL  " + p);
    Console.WriteLine(problems.Count == 0 ? "all checks pass" : $"{problems.Count} problem(s)");
    return problems.Count == 0 ? 0 : 1;
}
return Usage();
