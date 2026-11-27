// VaultPod: builds and validates FO4SFVaultPod.esm for FO4SF Round 16 (I1 animated CryoPod start).
//
// Exact three non-CELL records in FO4SFVaultPod.esm (masters Starfield.esm, FO4Port.esm):
//   1) ACTI 0x800  FO4SF_PlayerCryoPod (converted model, ActivatorStateGraph01.agx, rig, clips, OBND from model)
//   2) REFR 0x801  Persistent in FO4Port cell 0x0011F3 at (9.142858, -4.114286, -1.0285715), rot (0, 0, 0), Base = 0x800
//   3) REFR 0x001617 Override of FO4Port's static CryoPod01 ref with Initially Disabled (0x800) flag (lever 0x0012F6 untouched)
using System.Globalization;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;

public static class VaultPod
{
    public static readonly ModKey PodEsm = ModKey.FromFileName("FO4SFVaultPod.esm");
    public static readonly ModKey SfEsm = ModKey.FromFileName("Starfield.esm");
    public static readonly ModKey PortEsm = ModKey.FromFileName("FO4Port.esm");

    public const uint ActiId = 0x000800;
    public const string ActiEdid = "FO4SF_PlayerCryoPod";
    public const string ActiName = "CryoPod";
    public const uint PersistentRefId = 0x000801;
    public const string PersistentRefEdid = "FO4SF_PlayerCryoPodRef";
    public const uint VaultCellId = 0x0011F3;
    public const uint StaticPodRefId = 0x001617;
    public const uint LeverRefId = 0x0012F6;
    public const uint PortPodStatId = 0x000855;
    public const string PortPodStatEdid = "FO4Port_CryoPod01";
    public const string GraphAnam = "AnimTextData\\Tables\\Graphs\\ActivatorStateGraph01.agx";

    public const float RefPosX = 9.142858f;
    public const float RefPosY = -4.114286f;
    public const float RefPosZ = -1.0285715f;

    const int FlagPersistent = 0x400;
    const int FlagInitiallyDisabled = 0x800;
    const StarfieldRelease Release = StarfieldRelease.Starfield;

    static Cache<IModMasterStyledGetter, ModKey> Styles()
    {
        var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        styles.Set(new KeyedMasterStyle(SfEsm, MasterStyle.Full));
        styles.Set(new KeyedMasterStyle(PortEsm, MasterStyle.Full));
        styles.Set(new KeyedMasterStyle(PodEsm, MasterStyle.Full));
        return styles;
    }

    static IStarfieldModDisposableGetter Open(string path) =>
        StarfieldMod.CreateFromBinaryOverlay(path, Release, new BinaryReadParameters { MasterFlagsLookup = Styles() });

    static IStaticGetter FindPortPodStat(IStarfieldModGetter port, string edid)
    {
        var byEdid = port.Statics.FirstOrDefault(s => string.Equals(s.EditorID, edid, StringComparison.OrdinalIgnoreCase));
        if (byEdid != null) return byEdid;
        var byId = port.Statics.FirstOrDefault(s => s.FormKey == new FormKey(PortEsm, PortPodStatId));
        return byId ?? throw new InvalidOperationException($"FO4Port.esm lacks STAT {edid} / 0x{PortPodStatId:X6}");
    }

    static (ICellBlockGetter Block, ICellSubBlockGetter SubBlock, ICellGetter Cell) FindVaultCell(IStarfieldModGetter port)
    {
        var cellKey = new FormKey(PortEsm, VaultCellId);
        foreach (var blk in port.Cells.Records)
            foreach (var sub in blk.SubBlocks)
                foreach (var c in sub.Cells)
                    if (c.FormKey == cellKey)
                        return (blk, sub, c);
        throw new InvalidOperationException($"FO4Port.esm lacks CELL 0x{VaultCellId:X6}");
    }

    static bool BoundsMatch(IObjectBoundsGetter? b, P3Float min, P3Float max) =>
        b is not null &&
        MathF.Abs(b.First.X - min.X) <= 1e-3f &&
        MathF.Abs(b.First.Y - min.Y) <= 1e-3f &&
        MathF.Abs(b.First.Z - min.Z) <= 1e-3f &&
        MathF.Abs(b.Second.X - max.X) <= 1e-3f &&
        MathF.Abs(b.Second.Y - max.Y) <= 1e-3f &&
        MathF.Abs(b.Second.Z - max.Z) <= 1e-3f;

    public static int Info(string portPath, string edid)
    {
        using var port = Open(portPath);
        var st = FindPortPodStat(port, edid);
        Console.WriteLine($"STAT {st.FormKey} {st.EditorID} model {st.Model?.File}");
        Console.WriteLine($"BASE_ID 0x{st.FormKey.ID:X6}");
        Console.WriteLine($"MODEL {st.Model?.File}");
        return 0;
    }

    public static int Build(string portPath, string sfPath, string outDir, string model, string rig, string anims, string boundsSpec)
    {
        var (boundsMin, boundsMax) = SurfaceLiftCog.ParseBounds(boundsSpec);
        using var port = Open(portPath);
        var (srcBlk, srcSub, srcCell) = FindVaultCell(port);

        var staticKey = new FormKey(PortEsm, StaticPodRefId);
        var srcPersist = srcCell.Persistent.OfType<IPlacedObjectGetter>().FirstOrDefault(r => r.FormKey == staticKey);
        var srcTemp = srcCell.Temporary.OfType<IPlacedObjectGetter>().FirstOrDefault(r => r.FormKey == staticKey);
        var srcStaticRef = srcPersist ?? srcTemp
            ?? throw new InvalidOperationException($"FO4Port.esm cell 0x{VaultCellId:X6} lacks REFR 0x{StaticPodRefId:X6}");

        var mod = new StarfieldMod(PodEsm, Release);
        mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        mod.ModHeader.Author = "fo4-to-starfield";

        var acti = new Mutagen.Bethesda.Starfield.Activator(new FormKey(PodEsm, ActiId), Release)
        {
            EditorID = ActiEdid,
            Name = ActiName,
            Model = new Model { File = model },
            ObjectBounds = new ObjectBounds { First = boundsMin, Second = boundsMax },
            MarkerColor = System.Drawing.Color.FromArgb(0, 0xCC, 0x4C, 0x33),
            Flags = (Mutagen.Bethesda.Starfield.Activator.Flag)0,
            ActivationAngle = 360,
        };
        acti.Components.Add(new AnimationGraphComponent
        {
            ANAM = GraphAnam,
            BNAM = rig,
            CNAM = anims,
        });
        mod.Activators.Add(acti);

        var cellOv = srcCell.DeepCopy();
        cellOv.Persistent.Clear();
        cellOv.Temporary.Clear();
        cellOv.NavigationMeshes.Clear();

        var podRef = new PlacedObject(new FormKey(PodEsm, PersistentRefId), Release)
        {
            EditorID = PersistentRefEdid,
            Base = new FormLinkNullable<IPlaceableObjectGetter>(acti.FormKey),
            Position = new P3Float(RefPosX, RefPosY, RefPosZ),
            Rotation = new P3Float(0f, 0f, 0f),
        };
        podRef.MajorRecordFlagsRaw |= FlagPersistent;
        cellOv.Persistent.Add(podRef);

        var disableRef = srcStaticRef.DeepCopy();
        disableRef.MajorRecordFlagsRaw |= FlagInitiallyDisabled;
        if (srcPersist != null)
        {
            disableRef.MajorRecordFlagsRaw |= FlagPersistent;
            cellOv.Persistent.Add(disableRef);
        }
        else
        {
            cellOv.Temporary.Add(disableRef);
        }

        var blk = new CellBlock { BlockNumber = srcBlk.BlockNumber, GroupType = srcBlk.GroupType };
        var sub = new CellSubBlock { BlockNumber = srcSub.BlockNumber, GroupType = srcSub.GroupType };
        sub.Cells.Add(cellOv);
        blk.SubBlocks.Add(sub);
        mod.Cells.Records.Add(blk);
        mod.ModHeader.Stats.NextFormID = 0x802;

        Directory.CreateDirectory(outDir);
        var path = Path.Combine(outDir, PodEsm.FileName);
        var tmpDir = Path.Combine(outDir, ".tmp-" + Guid.NewGuid().ToString("N"));
        try
        {
            Directory.CreateDirectory(tmpDir);
            var tmp = Path.Combine(tmpDir, PodEsm.FileName);
            var masters = new[] { SfEsm, PortEsm };
            foreach (var m in masters)
                mod.ModHeader.MasterReferences.Add(new MasterReference { Master = m });
            mod.BeginWrite.ToPath(tmp).WithLoadOrder(masters)
                .WithKnownMasters(masters.Select(m => new KeyedMasterStyle(m, MasterStyle.Full)).ToArray())
                .WithMastersListContent(MastersListContentOption.NoCheck).Write();
            File.Move(tmp, path, overwrite: true);
        }
        finally
        {
            if (Directory.Exists(tmpDir)) Directory.Delete(tmpDir, true);
        }
        Console.WriteLine($"wrote {path} ({new FileInfo(path).Length:N0} bytes): ACTI 0x{ActiId:X6} {ActiEdid}, REFR 0x{PersistentRefId:X6}, Disabled 0x{StaticPodRefId:X6}");
        return 0;
    }

    public static int Check(string pluginPath, string portPath, string sfPath, string model, string rig, string anims, string boundsSpec)
    {
        var (boundsMin, boundsMax) = SurfaceLiftCog.ParseBounds(boundsSpec);
        using var port = Open(portPath);
        using var mod = Open(pluginPath);
        var problems = new List<string>();
        void Need(bool ok, string what) { if (!ok) problems.Add(what); }

        var masters = mod.ModHeader.MasterReferences.Select(m => m.Master).ToList();
        Console.WriteLine($"{Path.GetFileName(pluginPath)}: header {mod.ModHeader.Flags}, masters [{string.Join(", ", masters)}], next 0x{mod.ModHeader.Stats.NextFormID:X}");
        Need(mod.ModKey == PodEsm, $"the file is {mod.ModKey}, not {PodEsm}");
        Need(mod.ModHeader.Flags.HasFlag(StarfieldModHeader.HeaderFlag.Master), "not flagged as a master");
        Need(masters.SequenceEqual(new[] { SfEsm, PortEsm }), $"masters are not exactly [Starfield.esm, FO4Port.esm] (got [{string.Join(", ", masters)}])");
        Need(mod.Quests.Count == 0, "production pod plugin must carry zero QUST records");
        Need(mod.Worldspaces.Count == 0, "production pod plugin must carry zero WRLD records");

        // Exact three non-CELL major records: ACTI 0x800, REFR 0x801, REFR 0x001617
        var nonCell = mod.EnumerateMajorRecords().Where(r => r is not ICellGetter).ToList();
        Need(nonCell.Count == 3, $"expected exact 3 non-CELL records, found {nonCell.Count}");

        var acti = mod.Activators.FirstOrDefault(a => a.FormKey == new FormKey(PodEsm, ActiId));
        Need(mod.Activators.Count == 1 && acti != null, $"missing ACTI 0x{ActiId:X6} {ActiEdid}");
        if (acti != null)
        {
            Need(acti.EditorID == ActiEdid, $"ACTI EditorID is {acti.EditorID}, expected {ActiEdid}");
            var wantModel = new Model { File = model }.File.ToString();
            Need(string.Equals(acti.Model?.File?.ToString(), wantModel, StringComparison.OrdinalIgnoreCase), $"ACTI model is {acti.Model?.File}, expected {wantModel}");
            var g = acti.Components.OfType<IAnimationGraphComponentGetter>().ToList();
            Need(g.Count == 1 && g[0].ANAM == GraphAnam && string.Equals(g[0].BNAM, rig, StringComparison.OrdinalIgnoreCase) && string.Equals(g[0].CNAM, anims, StringComparison.OrdinalIgnoreCase),
                 "ACTI AnimationGraphComponent mismatch");
            Need(BoundsMatch(acti.ObjectBounds, boundsMin, boundsMax), $"ACTI OBND mismatch (got {acti.ObjectBounds?.First}..{acti.ObjectBounds?.Second}, expected {boundsMin}..{boundsMax})");
        }

        var cells = mod.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells).ToList();
        Need(cells.Count == 1 && cells[0].FormKey == new FormKey(PortEsm, VaultCellId), $"expected single cell override 0x{VaultCellId:X6}");
        var cell = cells.FirstOrDefault();
        var persistRefs = cell?.Persistent.OfType<IPlacedObjectGetter>().ToList() ?? new();
        var allRefs = cell != null ? cell.Persistent.Concat(cell.Temporary).OfType<IPlacedObjectGetter>().ToList() : new();

        var podRef = persistRefs.FirstOrDefault(r => r.FormKey == new FormKey(PodEsm, PersistentRefId));
        Need(podRef != null, $"missing persistent REFR 0x{PersistentRefId:X6} in cell 0x{VaultCellId:X6}");
        if (podRef != null)
        {
            Need((podRef.MajorRecordFlagsRaw & FlagPersistent) != 0, "REFR 0x801 lacks Persistent flag");
            Need(podRef.Base.FormKey == new FormKey(PodEsm, ActiId), $"REFR 0x801 Base is {podRef.Base.FormKey}, expected 0x{ActiId:X6}");
            Need(MathF.Abs(podRef.Position.X - RefPosX) <= 1e-4f && MathF.Abs(podRef.Position.Y - RefPosY) <= 1e-4f && MathF.Abs(podRef.Position.Z - RefPosZ) <= 1e-4f,
                 $"REFR 0x801 Position is {podRef.Position}");
            Need(MathF.Abs(podRef.Rotation.X) <= 1e-4f && MathF.Abs(podRef.Rotation.Y) <= 1e-4f && MathF.Abs(podRef.Rotation.Z) <= 1e-4f,
                 $"REFR 0x801 Rotation is {podRef.Rotation}, expected 0");
        }

        var disRef = allRefs.FirstOrDefault(r => r.FormKey == new FormKey(PortEsm, StaticPodRefId));
        Need(disRef != null, $"missing override of FO4Port REFR 0x{StaticPodRefId:X6}");
        if (disRef != null)
            Need((disRef.MajorRecordFlagsRaw & FlagInitiallyDisabled) != 0, $"REFR 0x{StaticPodRefId:X6} lacks Initially Disabled flag");

        Need(!allRefs.Any(r => r.FormKey == new FormKey(PortEsm, LeverRefId)), $"lever 0x{LeverRefId:X6} must not be modified");

        foreach (var x in problems) Console.WriteLine("FAIL  " + x);
        Console.WriteLine(problems.Count == 0 ? "all checks pass" : $"{problems.Count} problem(s)");
        return problems.Count == 0 ? 0 : 1;
    }
}
