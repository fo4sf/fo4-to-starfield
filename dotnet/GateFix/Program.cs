// GateFix: the Vault 111 yellow gate's collision fix as a plugin (S2 yellow gates, FAL-976).
//
// FO4SFGateFix.esm (masters Starfield.esm + FO4Port.esm, in that order) holds ONE record: an OVERRIDE of the STAT base of a placed
// reference of FO4Port.esm (default 001317, the gate), its model replaced by the same model with its layer-55 collision bodies
// relayered to L_STATIC (src/fo4sf/relayer.py) on a NEW model path, so nothing archived is replaced. Everything else of the record
// stays as it is. Every other reference of that base (the second gate leaf placements, Vault 114) follows.
//
// usage: GateFix info  <FO4Port.esm> <Starfield.esm> [--ref <hex id>]                 read only: the reference's STAT base and model
//        GateFix build <FO4Port.esm> <Starfield.esm> <out dir> --model <path below Meshes> [--ref <hex id>]
//        GateFix check <plugin> <FO4Port.esm> <Starfield.esm> --model <..> [--ref <hex id>]      exit 1 on a mismatch
//        GateFix fixture <out dir>          a synthetic Starfield.esm and FO4Port.esm (one cell, one STAT, one reference) in <out dir>
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;

try
{
    var rest = args.ToList();
    string? Opt(string name)
    {
        int i = rest.IndexOf(name);
        if (i < 0) return null;
        if (i + 1 >= rest.Count) throw new GateFix.Refusal(name + " needs a value");
        var v = rest[i + 1];
        rest.RemoveRange(i, 2);
        return v;
    }
    var refText = Opt("--ref") ?? GateFix.DefaultRef;
    var model = Opt("--model");
    var refId = GateFix.ParseRef(refText);
    if (rest.Count == 3 && rest[0] == "info") return GateFix.Info(rest[1], rest[2], refId);
    if (rest.Count == 4 && rest[0] == "build")
        return GateFix.Build(rest[1], rest[2], rest[3], refId, model ?? throw new GateFix.Refusal("build needs --model"));
    if (rest.Count == 4 && rest[0] == "check")
        return GateFix.Check(rest[1], rest[2], rest[3], refId, model ?? throw new GateFix.Refusal("check needs --model"));
    if (rest.Count == 2 && rest[0] == "fixture") return GateFix.Fixture(rest[1]);
}
catch (GateFix.Refusal r)
{
    Console.Error.WriteLine("refused: " + r.Message);
    return 1;
}
Console.Error.WriteLine("usage: GateFix info <FO4Port.esm> <Starfield.esm> [--ref H] | build <FO4Port.esm> <Starfield.esm> <out dir> --model M [--ref H] | " +
                        "check <plugin> <FO4Port.esm> <Starfield.esm> --model M [--ref H] | fixture <out dir>");
return 2;

static class GateFix
{
    public class Refusal(string m) : Exception(m);

    const StarfieldRelease Release = StarfieldRelease.Starfield;
    public const string DefaultRef = "001317";
    static readonly ModKey SfEsm = ModKey.FromFileName("Starfield.esm");
    static readonly ModKey PortEsm = ModKey.FromFileName("FO4Port.esm");
    public static readonly ModKey Plugin = ModKey.FromFileName("FO4SFGateFix.esm");

    public static uint ParseRef(string text)
    {
        var t = text.StartsWith("0x", StringComparison.OrdinalIgnoreCase) ? text[2..] : text;
        if (t.Length is < 1 or > 6 || !uint.TryParse(t, System.Globalization.NumberStyles.HexNumber, null, out var id) || id == 0)
            throw new Refusal($"--ref {text} is not a local form id (one to six hex digits, not zero)");
        return id;
    }

    static Cache<IModMasterStyledGetter, ModKey> Styles()
    {
        var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        styles.Set(new KeyedMasterStyle(SfEsm, MasterStyle.Full));
        styles.Set(new KeyedMasterStyle(PortEsm, MasterStyle.Full));
        return styles;
    }

    static IStarfieldModDisposableGetter Open(string path) =>
        StarfieldMod.CreateFromBinaryOverlay(path, Release, new BinaryReadParameters { MasterFlagsLookup = Styles() });

    /// <summary>The STAT the placed reference (a local id of FO4Port.esm) stands on; refuses when the reference is missing or its base is not a STAT of FO4Port.esm.</summary>
    static IStaticGetter FindBase(IStarfieldModGetter port, uint refId)
    {
        var refs = port.EnumerateMajorRecords<IPlacedObjectGetter>().Where(r => r.FormKey.ModKey == port.ModKey && r.FormKey.ID == refId).ToList();
        if (refs.Count != 1) throw new Refusal($"{refs.Count} placed references with local id {refId:X6} in {port.ModKey} (one needed)");
        var key = refs[0].Base.FormKey;
        if (key.ModKey != port.ModKey)
            throw new Refusal($"the reference {refId:X6} stands on {key}, which is not a record of {port.ModKey}: an override needs that record's own plugin as a master");
        var stats = port.Statics.Where(s => s.FormKey == key).ToList();
        if (stats.Count != 1) throw new Refusal($"the base {key} of reference {refId:X6} is not a STAT of {port.ModKey} ({stats.Count} STAT records)");
        return stats[0];
    }

    public static int Info(string portPath, string sfPath, uint refId)
    {
        using var port = Open(portPath);
        var s = FindBase(port, refId);
        Console.WriteLine($"REF {refId:X6} base {s.FormKey}");
        Console.WriteLine($"STAT {s.FormKey} {s.EditorID} model {s.Model?.File}");
        Console.WriteLine($"BASE_ID 0x{s.FormKey.ID:X6}");
        Console.WriteLine($"MODEL {s.Model?.File}");
        return 0;
    }

    public static int Build(string portPath, string sfPath, string outDir, uint refId, string model)
    {
        using var port = Open(portPath);
        var baseRec = FindBase(port, refId);
        var mod = new StarfieldMod(Plugin, Release);
        mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        mod.ModHeader.Author = "fo4-to-starfield";
        var ov = baseRec.DeepCopy();                                               // an override: the same form key, FO4Port.esm
        ov.Model ??= new Model();
        ov.Model.File = model;
        mod.Statics.Add(ov);
        mod.ModHeader.Stats.NextFormID = 0x800;
        Write(mod, outDir, SfEsm, PortEsm);
        var path = Path.Combine(outDir, Plugin.FileName);
        Console.WriteLine($"wrote {path} ({new FileInfo(path).Length:N0} bytes): override of STAT {baseRec.FormKey} {baseRec.EditorID}, model {baseRec.Model?.File} -> {model}");
        Console.WriteLine($"BASE_ID 0x{baseRec.FormKey.ID:X6}");
        return 0;
    }

    static void Write(StarfieldMod mod, string outDir, params ModKey[] masters)
    {
        Directory.CreateDirectory(outDir);
        var path = Path.Combine(outDir, mod.ModKey.FileName);
        var tmpDir = Path.Combine(outDir, ".tmp-" + Guid.NewGuid().ToString("N"));
        try
        {
            Directory.CreateDirectory(tmpDir);
            var tmp = Path.Combine(tmpDir, mod.ModKey.FileName);
            foreach (var m in masters)
                if (!mod.ModHeader.MasterReferences.Any(r => r.Master == m)) mod.ModHeader.MasterReferences.Add(new MasterReference { Master = m });
            mod.BeginWrite.ToPath(tmp).WithLoadOrder(masters)
                .WithKnownMasters(masters.Select(m => new KeyedMasterStyle(m, MasterStyle.Full)).ToArray())
                .WithMastersListContent(MastersListContentOption.NoCheck).Write();
            File.Move(tmp, path, overwrite: true);
        }
        finally
        {
            if (Directory.Exists(tmpDir)) Directory.Delete(tmpDir, true);
        }
    }

    public static int Check(string pluginPath, string portPath, string sfPath, uint refId, string model)
    {
        using var port = Open(portPath);
        var baseRec = FindBase(port, refId);
        using var mod = Open(pluginPath);
        var problems = new List<string>();
        void Need(bool ok, string what) { if (!ok) problems.Add(what); }
        var masters = mod.ModHeader.MasterReferences.Select(m => m.Master).ToList();
        Console.WriteLine($"{Path.GetFileName(pluginPath)}: header {mod.ModHeader.Flags}, masters [{string.Join(", ", masters)}]");
        Need(mod.ModKey == Plugin, $"the file is {mod.ModKey}, not {Plugin}");
        Need(mod.ModHeader.Flags.HasFlag(StarfieldModHeader.HeaderFlag.Master), "not flagged as a master");
        Need(masters.SequenceEqual(new[] { SfEsm, PortEsm }), "masters are not exactly [Starfield.esm, FO4Port.esm]");
        var all = mod.EnumerateMajorRecords().ToList();
        Need(all.Count == 1, "not exactly one record (the STAT override)");
        var ovr = mod.Statics.FirstOrDefault();
        Need(mod.Statics.Count() == 1 && ovr != null && ovr.FormKey == baseRec.FormKey, $"the STAT is not an override of {baseRec.FormKey}");
        if (ovr != null)
        {
            Console.WriteLine($"  override: STAT {ovr.FormKey} {ovr.EditorID} model {ovr.Model?.File}");
            var wantModel = new Model { File = model }.File.ToString();            // Mutagen files a model path as Meshes/<path>
            Need(ovr.EditorID == baseRec.EditorID, "the override's EditorID changed");
            Need(ovr.Model?.File?.ToString() == wantModel, $"the model is not {wantModel}");
            Need(!string.Equals(ovr.Model?.File?.ToString(), baseRec.Model?.File?.ToString(), StringComparison.OrdinalIgnoreCase), "the model path is the port's own: the override would shadow an archived file, not use a new path");
        }
        foreach (var x in problems) Console.WriteLine("FAIL  " + x);
        Console.WriteLine(problems.Count == 0 ? "all checks pass" : $"{problems.Count} problem(s)");
        return problems.Count == 0 ? 0 : 1;
    }

    public static int Fixture(string outDir)
    {
        Directory.CreateDirectory(outDir);
        var sf = new StarfieldMod(SfEsm, Release);
        sf.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        sf.BeginWrite.ToPath(Path.Combine(outDir, "Starfield.esm")).WithNoLoadOrder().Write();
        var port = new StarfieldMod(PortEsm, Release);
        port.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        var stat = new Static(new FormKey(PortEsm, 0x00DEF8), Release)
        {
            EditorID = "FO4Port_V111GearRoomGate01_xrgd_test", Model = new Model { File = "fo4port\\interiors\\vault\\gate\\v111gearroomgate01_xrgd_test.nif" },
        };
        port.Statics.Add(stat);
        var cell = new Cell(new FormKey(PortEsm, 0x0016D8), Release) { EditorID = "FO4Port_Vault111Cryo", Flags = Cell.Flag.IsInteriorCell };
        cell.Temporary.Add(new PlacedObject(new FormKey(PortEsm, 0x001317), Release) { Base = new FormLink<IPlaceableObjectGetter>(stat.FormKey) });
        var block = new CellBlock { BlockNumber = 0, GroupType = GroupTypeEnum.InteriorCellBlock };
        var sub = new CellSubBlock { BlockNumber = 0, GroupType = GroupTypeEnum.InteriorCellSubBlock };
        sub.Cells.Add(cell);
        block.SubBlocks.Add(sub);
        port.Cells.Records.Add(block);
        port.ModHeader.MasterReferences.Add(new MasterReference { Master = SfEsm });
        port.BeginWrite.ToPath(Path.Combine(outDir, "FO4Port.esm")).WithLoadOrder(SfEsm)
            .WithKnownMasters(new KeyedMasterStyle(SfEsm, MasterStyle.Full)).WithMastersListContent(MastersListContentOption.NoCheck).Write();
        Console.WriteLine($"wrote {Path.Combine(outDir, "Starfield.esm")} and {Path.Combine(outDir, "FO4Port.esm")}");
        return 0;
    }
}
