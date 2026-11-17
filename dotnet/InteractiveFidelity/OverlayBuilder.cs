using System.Drawing;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using Mutagen.Bethesda;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Cache;
using Mutagen.Bethesda.Plugins.Records;
using Noggog;
using F4 = Mutagen.Bethesda.Fallout4;
using SF = Mutagen.Bethesda.Starfield;

public sealed class OverlayBuildReport
{
    public string Plugin { get; set; } = "";
    public List<string> Masters { get; set; } = new();
    public int InteriorCellsScanned { get; set; }
    public int InteriorCellsOverridden { get; set; }
    public int ExteriorCellsScanned { get; set; }
    public int ExteriorCellsOverridden { get; set; }
    public bool WorldspaceOverridden { get; set; }

    public int OverriddenReferences { get; set; }
    public int CreatedInteriorMarkers { get; set; }
    public int CreatedExteriorTopMarkers { get; set; }
    public int CreatedAutoloadDoors { get; set; }
    public int CreatedKeywords { get; set; }

    public int XespWritten { get; set; }
    public int XespOppositeWritten { get; set; }
    public int XespPopInWritten { get; set; }
    public int XespFoldedInitialState { get; set; }
    public int XespUnplacedParentSkipped { get; set; }

    public int XlocWritten { get; set; }
    public int XlocKeyMapped { get; set; }
    public int XlocUnmappedKeyFallback { get; set; }
    public int XlocUnlockedZeroSkipped { get; set; }
    public int XlocUnsupportedLevelSkipped { get; set; }
    public int XlocUnopenableRequiresKeySkipped { get; set; }
    public int XlocNonLockableSkipped { get; set; }

    public int XlkrWritten { get; set; }
    public int XlkrDanglingSkipped { get; set; }
    public int XlkrUnmappedUnionSkipped { get; set; }
    public int XlkrMultirefLodSkipped { get; set; }

    public int XaprParentsWired { get; set; }
    public int XaprEdgesWired { get; set; }
    public int XaprChainXlkrWritten { get; set; }
    public int XaprDelaysPreserved { get; set; }
    public int XaprParentActivateOnlyApplied { get; set; }
    public int XaprUpgradedLegacySingleLinks { get; set; }
    public int XaprParentNotPlaced { get; set; }
    public int XaprChildNotPlaced { get; set; }

    public int XtelCreatedLinks { get; set; }
    public int XtelExistingNativePreserved { get; set; }
    public int XtelExistingScriptPreserved { get; set; }
    public int NavmeshDoorTrianglesVerified { get; set; }
}

public static class OverlayBuilder
{
    public const float UnitsPerMetre = 70f;
    public const double StarfieldCellMetres = 100.0;
    public const double Fo4UnitsPerStarfieldCell = UnitsPerMetre * StarfieldCellMetres; // 7000 FO4 units = 100 m
    public const string ChainScriptName = "FO4SF_ActivateChain";
    public const string LegacySingleScriptName = "DefaultActivateLinkedRefOnActivate";
    public const string ChainKeywordIdentity = "KYWD:FO4SF_ActivateChainLink";
    public const string ChainKeywordEditorId = "FO4SF_ActivateChainLink";

    public static readonly ModKey SfModKey = ModKey.FromNameAndExtension("Starfield.esm");
    public static readonly FormKey EnableMarkerBase = new(SfModKey, 0x010D8D);
    public static readonly FormKey XMarkerBase = new(SfModKey, 0x00003B);
    public static readonly FormKey XMarkerHeadingBase = new(SfModKey, 0x000034);
    public static readonly FormKey LightBoxBase = new(SfModKey, 0x0001F7);
    public static readonly FormKey AutoloadDoorCaveBase = new(SfModKey, 0x24F9CE);
    public static readonly FormKey LegacyLinkCustom02 = new(SfModKey, 0x05D5E7);

    private static readonly IReadOnlyDictionary<string, FormKey> MarkerBases =
        new Dictionary<string, FormKey>(StringComparer.OrdinalIgnoreCase)
        {
            ["EnableMarker"] = EnableMarkerBase,
            ["XMarker"] = XMarkerBase,
            ["XMarkerHeading"] = XMarkerHeadingBase,
            ["LightBox"] = LightBoxBase,
        };

    private static readonly HashSet<int> PickableLockLevels = new() { 1, 25, 50, 75, 100 };
    private static readonly HashSet<int> RefusedLockLevels = new() { 251, 252, 253, 254 };

    private static readonly string[] CoreNestedRefDicts =
    {
        "containers", "items", "activators", "terminals", "workshops", "flora", "benches", "doors", "lights"
    };

    public static Cache<IModMasterStyledGetter, ModKey> MasterStyles(params ModKey[] fullMasters)
    {
        var c = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        foreach (var m in fullMasters)
            c.Set(new KeyedMasterStyle(m, MasterStyle.Full));
        return c;
    }

    public static SF.Worldspace WorldOnly(SF.IWorldspaceGetter w) =>
        SF.WorldspaceMixIn.DeepCopy(w, new SF.Worldspace.TranslationMask(defaultOn: true)
        {
            SubCells = new SF.WorldspaceBlock.TranslationMask(defaultOn: false, onOverall: false),
            TopCell = new SF.Cell.TranslationMask(defaultOn: false, onOverall: false),
        });

    public static SF.Cell CellOnly(SF.ICellGetter c)
    {
        var copy = SF.CellMixIn.DeepCopy(c, new SF.Cell.TranslationMask(defaultOn: true)
        {
            Persistent = false,
            Temporary = false,
            NavigationMeshes = new SF.NavigationMesh.TranslationMask(defaultOn: false, onOverall: false),
        });
        copy.Persistent.Clear();
        copy.Temporary.Clear();
        copy.NavigationMeshes.Clear();
        return copy;
    }

    public static (int X, int Y) StarfieldGridOfFo4Pos(P3Float fo4Pos) =>
        ((int)Math.Floor(fo4Pos.X / Fo4UnitsPerStarfieldCell), (int)Math.Floor(fo4Pos.Y / Fo4UnitsPerStarfieldCell));

    private static P3Float ToMetres(P3Float fo4Pos) =>
        new(fo4Pos.X / UnitsPerMetre, fo4Pos.Y / UnitsPerMetre, fo4Pos.Z / UnitsPerMetre);

    public static int Run(string paramsPath)
    {
        using var doc = JsonDocument.Parse(File.ReadAllText(paramsPath));
        var root = doc.RootElement;

        string Req(string k) => root.GetProperty(k).GetString() ?? throw new InvalidDataException($"params missing {k}");
        string? OptStr(string k) => root.TryGetProperty(k, out var e) && e.ValueKind == JsonValueKind.String ? e.GetString() : null;

        var fo4Path = Req("fo4_esm");
        var sfPath = Req("starfield_esm");
        var outDir = Req("out_dir");
        var pluginName = OptStr("plugin") ?? "FO4SFInteractiveFidelity.esm";
        var portPath = OptStr("port_esm");
        var portIdsPath = OptStr("port_formids");
        var corePath = OptStr("core_esm");
        var coreIdsPath = OptStr("core_formids");
        var fo4WorldHex = OptStr("fo4_world_id") ?? "00003C";
        var coreWorldEdid = OptStr("core_world_edid") ?? "FO4Core_Commonwealth";

        var requestedIntHex = new HashSet<uint>();
        bool allIntCells = false;
        if (root.TryGetProperty("interior_cells", out var icEl) && icEl.ValueKind == JsonValueKind.Array)
        {
            foreach (var item in icEl.EnumerateArray())
            {
                var s = item.GetString()!;
                if (s == "*") allIntCells = true;
                else requestedIntHex.Add(Convert.ToUInt32(s.StartsWith("0x", StringComparison.OrdinalIgnoreCase) ? s[2..] : s, 16));
            }
        }

        var requestedExtGrids = new HashSet<(int X, int Y)>();
        if (root.TryGetProperty("exterior_cells", out var ecEl) && ecEl.ValueKind == JsonValueKind.Array)
        {
            foreach (var item in ecEl.EnumerateArray())
            {
                var arr = item.EnumerateArray().Select(x => x.GetInt32()).ToArray();
                if (arr.Length != 2) throw new InvalidDataException("exterior_cells entry must be [x, y]");
                requestedExtGrids.Add((arr[0], arr[1]));
            }
        }

        Directory.CreateDirectory(outDir);
        var mapPath = Path.Combine(outDir, "fidelity_formids.json");
        var stableIds = File.Exists(mapPath)
            ? JsonSerializer.Deserialize<Dictionary<string, uint>>(File.ReadAllText(mapPath))!
            : new Dictionary<string, uint>(StringComparer.Ordinal);
        uint nextId = stableIds.Count == 0 ? 0x800u : stableIds.Values.Max() + 1;
        var modKey = ModKey.FromFileName(pluginName);

        FormKey AllocId(string key)
        {
            if (!stableIds.TryGetValue(key, out var v))
            {
                if (nextId >= 0x1000000u) throw new InvalidOperationException("FormID space exhausted");
                v = nextId++;
                stableIds[key] = v;
            }
            return new FormKey(modKey, v);
        }

        using var fo4 = F4.Fallout4Mod.CreateFromBinaryOverlay(fo4Path, F4.Fallout4Release.Fallout4);
        ILinkCache fo4Cache = new F4.IFallout4ModGetter[] { fo4 }.ToImmutableLinkCache<F4.IFallout4Mod, F4.IFallout4ModGetter>();
        using var sf = SF.StarfieldMod.CreateFromBinaryOverlay(sfPath, SF.StarfieldRelease.Starfield);

        SF.IStarfieldModDisposableGetter? core = null;
        SF.IStarfieldModDisposableGetter? port = null;
        try
        {
            if (!string.IsNullOrEmpty(corePath))
                core = SF.StarfieldMod.CreateFromBinaryOverlay(corePath, SF.StarfieldRelease.Starfield,
                    new BinaryReadParameters { MasterFlagsLookup = MasterStyles(SfModKey) });
            if (!string.IsNullOrEmpty(portPath))
                port = SF.StarfieldMod.CreateFromBinaryOverlay(portPath, SF.StarfieldRelease.Starfield,
                    new BinaryReadParameters { MasterFlagsLookup = MasterStyles(SfModKey) });

            var mod = new SF.StarfieldMod(modKey, SF.StarfieldRelease.Starfield);
            mod.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Master;

            var report = new OverlayBuildReport { Plugin = pluginName };
            var loadOrderKeys = new List<ModKey> { SfModKey };
            var knownStyles = new List<KeyedMasterStyle> { new(SfModKey, MasterStyle.Full) };
            var cacheMods = new List<SF.IStarfieldModGetter> { sf };
            if (core != null)
            {
                loadOrderKeys.Add(core.ModKey);
                knownStyles.Add(new KeyedMasterStyle(core.ModKey, MasterStyle.Full));
                cacheMods.Add(core);
            }
            if (port != null)
            {
                loadOrderKeys.Add(port.ModKey);
                knownStyles.Add(new KeyedMasterStyle(port.ModKey, MasterStyle.Full));
                cacheMods.Add(port);
            }
            var masterCache = cacheMods.ToImmutableLinkCache<SF.IStarfieldMod, SF.IStarfieldModGetter>();

            // 1. Parse port & core FormID maps: FO4 FormKey -> Starfield FormKey.
            var fo4ToSfRef = new Dictionary<FormKey, FormKey>();
            var fo4ToSfKeym = new Dictionary<FormKey, FormKey>();
            var portCellByEdid = new Dictionary<string, SF.ICellGetter>(StringComparer.OrdinalIgnoreCase);
            var portRefRecords = new Dictionary<FormKey, (SF.IPlacedObjectGetter Obj, FormKey CellKey, bool Persistent)>();

            if (port != null && !string.IsNullOrEmpty(portIdsPath))
            {
                foreach (var c in port.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells))
                {
                    if (c.EditorID != null) portCellByEdid[c.EditorID] = c;
                    foreach (var p in c.Persistent.OfType<SF.IPlacedObjectGetter>())
                        if (p.FormKey.ModKey == port.ModKey && (p.MajorRecordFlagsRaw & 0x20) == 0)
                            portRefRecords[p.FormKey] = (p, c.FormKey, true);
                    foreach (var t in c.Temporary.OfType<SF.IPlacedObjectGetter>())
                        if (t.FormKey.ModKey == port.ModKey && (t.MajorRecordFlagsRaw & 0x20) == 0)
                            portRefRecords[t.FormKey] = (t, c.FormKey, false);
                }
                var activePortKeys = port.Keys.Where(k => (k.MajorRecordFlagsRaw & 0x20) == 0).Select(k => k.FormKey).ToHashSet();
                using var pdoc = JsonDocument.Parse(File.ReadAllText(portIdsPath));
                foreach (var prop in pdoc.RootElement.EnumerateObject())
                {
                    var idVal = prop.Value.GetUInt32();
                    if (prop.Name.StartsWith("REFR:", StringComparison.Ordinal))
                    {
                        var idx = prop.Name.IndexOf(':', 5);
                        if (idx < 0) continue;
                        if (FormKey.TryFactory(prop.Name.Substring(idx + 1), out var fo4Fk) && !fo4Fk.IsNull)
                        {
                            var sfFk = new FormKey(port.ModKey, idVal);
                            if (portRefRecords.ContainsKey(sfFk))
                                fo4ToSfRef[fo4Fk] = sfFk;
                        }
                    }
                    else if (prop.Name.StartsWith("KEYM:", StringComparison.Ordinal))
                    {
                        if (FormKey.TryFactory(prop.Name.Substring(5), out var fo4Fk) && !fo4Fk.IsNull)
                        {
                            var sfFk = new FormKey(port.ModKey, idVal);
                            if (activePortKeys.Contains(sfFk))
                                fo4ToSfKeym[fo4Fk] = sfFk;
                        }
                    }
                }
            }

            SF.IWorldspaceGetter? coreWorld = null;
            var coreGridCells = new Dictionary<(int X, int Y), (SF.IWorldspaceBlockGetter Blk, SF.IWorldspaceSubBlockGetter Sub, SF.ICellGetter Cell)>();
            if (core != null && !string.IsNullOrEmpty(coreIdsPath))
            {
                coreWorld = core.Worldspaces.FirstOrDefault(w => w.EditorID == coreWorldEdid)
                    ?? throw new InvalidDataException($"no worldspace {coreWorldEdid} in {core.ModKey}");
                foreach (var blk in coreWorld.SubCells)
                    foreach (var sub in blk.Items)
                        foreach (var c in sub.Items)
                            if (c.Grid is { } g)
                                coreGridCells[(g.Point.X, g.Point.Y)] = (blk, sub, c);

                var activeCoreKeys = core.Keys.Where(k => (k.MajorRecordFlagsRaw & 0x20) == 0).Select(k => k.FormKey).ToHashSet();
                using var cdoc = JsonDocument.Parse(File.ReadAllText(coreIdsPath));
                var croot = cdoc.RootElement;
                if (croot.TryGetProperty("refs", out var refsObj) && refsObj.ValueKind == JsonValueKind.Object)
                {
                    foreach (var prop in refsObj.EnumerateObject())
                        if (FormKey.TryFactory(prop.Name, out var fo4Fk) && !fo4Fk.IsNull &&
                            uint.TryParse(prop.Value.GetString(), NumberStyles.HexNumber, null, out var idVal))
                            fo4ToSfRef[fo4Fk] = new FormKey(core.ModKey, idVal);
                }
                foreach (var dictName in CoreNestedRefDicts)
                {
                    if (!croot.TryGetProperty(dictName, out var dobj) || dobj.ValueKind != JsonValueKind.Object) continue;
                    foreach (var prop in dobj.EnumerateObject())
                        if (FormKey.TryFactory(prop.Name, out var fo4Fk) && !fo4Fk.IsNull &&
                            prop.Value.ValueKind == JsonValueKind.Object &&
                            prop.Value.TryGetProperty("ref", out var rp) &&
                            uint.TryParse(rp.GetString(), NumberStyles.HexNumber, null, out var idVal))
                            fo4ToSfRef[fo4Fk] = new FormKey(core.ModKey, idVal);
                }
                if (croot.TryGetProperty("keys", out var keysObj) && keysObj.ValueKind == JsonValueKind.Object)
                {
                    foreach (var prop in keysObj.EnumerateObject())
                        if (FormKey.TryFactory(prop.Name, out var fo4Fk) && !fo4Fk.IsNull &&
                            uint.TryParse(prop.Value.GetString(), NumberStyles.HexNumber, null, out var idVal))
                        {
                            var sfFk = new FormKey(core.ModKey, idVal);
                            if (activeCoreKeys.Contains(sfFk))
                                fo4ToSfKeym[fo4Fk] = sfFk;
                        }
                }
            }

            // 2. Collect target FO4 interior cells and exterior Commonwealth references.
            var fo4IntCells = new List<(F4.ICellGetter Fo4Cell, SF.ICellGetter PortCell)>();
            if (port != null && (allIntCells || requestedIntHex.Count > 0))
            {
                foreach (var fc in fo4.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells))
                {
                    if (!allIntCells && !requestedIntHex.Contains(fc.FormKey.ID)) continue;
                    if (fc.EditorID == null) continue;
                    var portName = "FO4Port_" + fc.EditorID;
                    if (portCellByEdid.TryGetValue(portName, out var pc))
                        fo4IntCells.Add((fc, pc));
                }
            }
            report.InteriorCellsScanned = fo4IntCells.Count;

            F4.IWorldspaceGetter? fo4World = null;
            var fo4ExtRefsInTargetGrids = new List<(F4.IPlacedObjectGetter Fo4Ref, (int X, int Y) Grid, bool FromTopCell)>();
            var enableTree = new Dictionary<FormKey, (bool RawDisabled, FormKey? Parent, uint Flags)>();
            var fo4PosIndex = new Dictionary<FormKey, (int X, int Y)>();

            static void RecordFo4Enable(Dictionary<FormKey, (bool, FormKey?, uint)> tree, F4.IPlacedGetter p)
            {
                bool rawDis = (p.MajorRecordFlagsRaw & 0x800) != 0;
                var ep = (p as F4.IPlacedObjectGetter)?.EnableParent ?? (p as F4.IPlacedNpcGetter)?.EnableParent;
                FormKey? parent = ep != null && !ep.Reference.IsNull ? ep.Reference.FormKey : null;
                uint flags = ep != null ? (uint)ep.Flags : 0u;
                tree[p.FormKey] = (rawDis, parent, flags);
            }

            foreach (var (fc, _) in fo4IntCells)
                foreach (var p in fc.Persistent.Concat(fc.Temporary))
                    RecordFo4Enable(enableTree, p);

            if (coreWorld != null && requestedExtGrids.Count > 0)
            {
                var fo4WorldFk = new FormKey(fo4.ModKey, Convert.ToUInt32(fo4WorldHex, 16));
                fo4World = fo4.Worldspaces.FirstOrDefault(w => w.FormKey == fo4WorldFk)
                    ?? throw new InvalidDataException($"no FO4 worldspace {fo4WorldFk} in {fo4.ModKey}");

                if (fo4World.TopCell != null)
                {
                    foreach (var p in fo4World.TopCell.Persistent.Concat(fo4World.TopCell.Temporary))
                    {
                        RecordFo4Enable(enableTree, p);
                        if (p is F4.IPlacedObjectGetter po)
                        {
                            var g = StarfieldGridOfFo4Pos(po.Position);
                            fo4PosIndex[po.FormKey] = g;
                            if (requestedExtGrids.Contains(g))
                                fo4ExtRefsInTargetGrids.Add((po, g, true));
                        }
                    }
                }
                foreach (var blk in fo4World.SubCells)
                    foreach (var sub in blk.Items)
                        foreach (var fc in sub.Items)
                            foreach (var p in fc.Persistent.Concat(fc.Temporary))
                            {
                                RecordFo4Enable(enableTree, p);
                                if (p is F4.IPlacedObjectGetter po)
                                {
                                    var g = StarfieldGridOfFo4Pos(po.Position);
                                    fo4PosIndex[po.FormKey] = g;
                                    if (requestedExtGrids.Contains(g))
                                        fo4ExtRefsInTargetGrids.Add((po, g, false));
                                }
                            }
            }
            report.ExteriorCellsScanned = requestedExtGrids.Count(g => coreGridCells.ContainsKey(g));

            // Materialize core PlacedObject records ONLY for requested grids + any cross-cell target grids.
            var coreRefRecords = new Dictionary<FormKey, (SF.IPlacedObjectGetter Obj, (int X, int Y)? Grid, bool Persistent)>();
            var materializedGrids = new HashSet<(int X, int Y)>();

            void MaterializeCoreGrid((int X, int Y) g)
            {
                if (!materializedGrids.Add(g) || !coreGridCells.TryGetValue(g, out var entry)) return;
                foreach (var p in entry.Cell.Persistent.OfType<SF.IPlacedObjectGetter>())
                    if ((p.MajorRecordFlagsRaw & 0x20) == 0)
                        coreRefRecords[p.FormKey] = (p, g, true);
                foreach (var t in entry.Cell.Temporary.OfType<SF.IPlacedObjectGetter>())
                    if ((t.MajorRecordFlagsRaw & 0x20) == 0)
                        coreRefRecords[t.FormKey] = (t, g, false);
            }

            if (coreWorld != null)
            {
                if (coreWorld.TopCell != null)
                {
                    foreach (var p in coreWorld.TopCell.Persistent.OfType<SF.IPlacedObjectGetter>())
                        if ((p.MajorRecordFlagsRaw & 0x20) == 0) coreRefRecords[p.FormKey] = (p, null, true);
                    foreach (var t in coreWorld.TopCell.Temporary.OfType<SF.IPlacedObjectGetter>())
                        if ((t.MajorRecordFlagsRaw & 0x20) == 0) coreRefRecords[t.FormKey] = (t, null, false);
                }
                foreach (var g in requestedExtGrids)
                    MaterializeCoreGrid(g);
            }

            // Collect all FO4 refs in scope (interior + exterior) to discover needed control markers & cross-cell targets.
            var scopeRefs = new List<(F4.IPlacedObjectGetter Fo4Ref, bool IsInterior, FormKey? PortCellKey, (int X, int Y)? ExtGrid)>();
            foreach (var (fc, pc) in fo4IntCells)
                foreach (var po in fc.Persistent.Concat(fc.Temporary).OfType<F4.IPlacedObjectGetter>())
                    scopeRefs.Add((po, true, pc.FormKey, null));
            foreach (var (po, g, _) in fo4ExtRefsInTargetGrids)
                scopeRefs.Add((po, false, null, g));

            var neededFo4Keys = new HashSet<FormKey>();
            foreach (var (r, _, _, _) in scopeRefs)
            {
                if (r.EnableParent is { } ep && !ep.Reference.IsNull) neededFo4Keys.Add(ep.Reference.FormKey);
                foreach (var lr in r.LinkedReferences)
                {
                    if (!lr.Reference.IsNull) neededFo4Keys.Add(lr.Reference.FormKey);
                    if (!lr.KeywordOrReference.IsNull) neededFo4Keys.Add(lr.KeywordOrReference.FormKey);
                }
                if (r.ActivateParents is { } ap)
                    foreach (var p in ap.Parents)
                        if (!p.Reference.IsNull) neededFo4Keys.Add(p.Reference.FormKey);
                if (r.TeleportDestination is { } td && !td.Door.IsNull) neededFo4Keys.Add(td.Door.FormKey);
            }

            // Materialize any adjacent exterior grid cells holding cross-cell targets.
            foreach (var nfk in neededFo4Keys)
                if (fo4ToSfRef.TryGetValue(nfk, out var sfFk) && core != null && sfFk.ModKey == core.ModKey &&
                    !coreRefRecords.ContainsKey(sfFk) && fo4PosIndex.TryGetValue(nfk, out var g))
                    MaterializeCoreGrid(g);

            // Prepare lazy override containers for interior cells and worldspace/exterior cells.
            var portCellByKey = fo4IntCells.ToDictionary(x => x.PortCell.FormKey, x => x.PortCell);
            var intCellOverrides = new Dictionary<FormKey, SF.Cell>();
            SF.Cell GetIntCellOverride(FormKey portCellKey)
            {
                if (!intCellOverrides.TryGetValue(portCellKey, out var c))
                {
                    c = CellOnly(portCellByKey[portCellKey]);
                    intCellOverrides[portCellKey] = c;
                }
                return c;
            }

            SF.Worldspace? worldOverride = null;
            SF.Cell? topCellOverride = null;
            var extCellOverrides = new Dictionary<(int X, int Y), SF.Cell>();
            var extBlocks = new Dictionary<(short X, short Y), SF.WorldspaceBlock>();
            var extSubBlocks = new Dictionary<(short X, short Y), SF.WorldspaceSubBlock>();

            SF.Worldspace EnsureWorldOverride()
            {
                if (worldOverride == null)
                {
                    worldOverride = WorldOnly(coreWorld!);
                    worldOverride.SubCells.Clear();
                }
                return worldOverride;
            }

            SF.Cell EnsureTopCellOverride()
            {
                if (topCellOverride == null)
                {
                    var w = EnsureWorldOverride();
                    topCellOverride = CellOnly(coreWorld!.TopCell!);
                    w.TopCell = topCellOverride;
                }
                return topCellOverride;
            }

            SF.Cell GetExtCellOverride((int X, int Y) g)
            {
                if (!extCellOverrides.TryGetValue(g, out var ec))
                {
                    var w = EnsureWorldOverride();
                    var src = coreGridCells[g];
                    ec = CellOnly(src.Cell);
                    extCellOverrides[g] = ec;
                    (short X, short Y) bKey = (src.Blk.BlockNumberX, src.Blk.BlockNumberY);
                    if (!extBlocks.TryGetValue(bKey, out var blk))
                    {
                        blk = new SF.WorldspaceBlock { BlockNumberX = bKey.X, BlockNumberY = bKey.Y, GroupType = src.Blk.GroupType };
                        extBlocks[bKey] = blk;
                        w.SubCells.Add(blk);
                    }
                    (short X, short Y) sKey = (src.Sub.BlockNumberX, src.Sub.BlockNumberY);
                    if (!extSubBlocks.TryGetValue(sKey, out var sub))
                    {
                        sub = new SF.WorldspaceSubBlock { BlockNumberX = sKey.X, BlockNumberY = sKey.Y, GroupType = src.Sub.GroupType };
                        extSubBlocks[sKey] = sub;
                        blk.Items.Add(sub);
                    }
                    sub.Items.Add(ec);
                }
                return ec;
            }

            // 3. Recreate needed invisible control markers and connected AutoloadDoor pairs.
            var createdRefs = new Dictionary<FormKey, SF.PlacedObject>();

            // Identify unplaced AutoloadDoor candidates in scope first so mutual pairs resolve each other.
            var autoloadInScope = new Dictionary<FormKey, (F4.IPlacedObjectGetter Fo4Ref, bool IsInterior, FormKey? PortCellKey, (int X, int Y)? ExtGrid)>();
            foreach (var item in scopeRefs)
            {
                if (fo4ToSfRef.ContainsKey(item.Fo4Ref.FormKey)) continue;
                if ((item.Fo4Ref.MajorRecordFlagsRaw & 0x20) != 0) continue;
                if (item.Fo4Ref.TeleportDestination is not { } td || td.Door.IsNull || td.TransitionInterior.IsNull == false) continue;
                if (((uint)td.Flags & ~7u) != 0 || ((uint)td.Flags & 4u) != 0) continue;
                if (!item.Fo4Ref.Base.TryResolve<F4.IDoorGetter>(fo4Cache, out var fo4Door)) continue;
                if (fo4Door.EditorID == "AutoloadDoor" &&
                    fo4Door.Flags.HasFlag(F4.Door.Flag.Automatic) &&
                    !fo4Door.Flags.HasFlag(F4.Door.Flag.Hidden) &&
                    !fo4Door.Flags.HasFlag(F4.Door.Flag.MinimalUse))
                {
                    autoloadInScope[item.Fo4Ref.FormKey] = item;
                }
            }

            bool IsResolvedDoorRef(FormKey sfFk)
            {
                if (createdRefs.TryGetValue(sfFk, out var cr))
                    return cr.Base.FormKey == AutoloadDoorCaveBase || masterCache.TryResolve<SF.IDoorGetter>(cr.Base.FormKey, out _);
                if (portRefRecords.TryGetValue(sfFk, out var pr))
                    return pr.Persistent && masterCache.TryResolve<SF.IDoorGetter>(pr.Obj.Base.FormKey, out _);
                if (coreRefRecords.TryGetValue(sfFk, out var coreR))
                    return coreR.Persistent && masterCache.TryResolve<SF.IDoorGetter>(coreR.Obj.Base.FormKey, out _);
                return false;
            }

            foreach (var item in scopeRefs)
            {
                var r = item.Fo4Ref;
                if (fo4ToSfRef.ContainsKey(r.FormKey) || (r.MajorRecordFlagsRaw & 0x20) != 0) continue;
                if (item.ExtGrid is { } eg && !coreGridCells.ContainsKey(eg)) continue;

                // Control markers: EnableMarker, XMarker, XMarkerHeading, LightBox.
                if (neededFo4Keys.Contains(r.FormKey) &&
                    r.Base.TryResolve<F4.IStaticGetter>(fo4Cache, out var fo4Stat) &&
                    fo4Stat.EditorID != null &&
                    MarkerBases.TryGetValue(fo4Stat.EditorID, out var markerBase))
                {
                    SF.PlacedPrimitive? primitive = null;
                    if (fo4Stat.EditorID.Equals("LightBox", StringComparison.OrdinalIgnoreCase))
                    {
                        if (r.Primitive == null) continue;
                        int pType = (int)r.Primitive.Type;
                        if (!Enum.IsDefined(typeof(SF.PlacedPrimitive.TypeEnum), pType)) continue;
                        primitive = new SF.PlacedPrimitive
                        {
                            Bounds = ToMetres(r.Primitive.Bounds),
                            Color = r.Primitive.Color,
                            Unknown = r.Primitive.Unknown,
                            Type = (SF.PlacedPrimitive.TypeEnum)pType,
                        };
                    }
                    var newFk = AllocId($"MARKER:{r.FormKey.ID:X6}:{r.FormKey.ModKey.FileName}");
                    var marker = new SF.PlacedObject(newFk, SF.StarfieldRelease.Starfield)
                    {
                        Base = new FormLinkNullable<SF.IPlaceableObjectGetter>(markerBase),
                        Position = ToMetres(r.Position),
                        Rotation = r.Rotation,
                        Primitive = primitive,
                    };
                    if (r.Scale is { } sc && Math.Abs(sc - 1f) > 1e-4f) marker.Scale = sc;
                    if ((r.MajorRecordFlagsRaw & 0x800) != 0) marker.MajorRecordFlagsRaw |= 0x800;
                    marker.MajorRecordFlagsRaw |= 0x400; // Persistent

                    if (item.IsInterior)
                    {
                        GetIntCellOverride(item.PortCellKey!.Value).Persistent.Add(marker);
                        report.CreatedInteriorMarkers++;
                    }
                    else
                    {
                        // CRITICAL (#712): Exterior persistent control markers MUST live in Worldspace.TopCell.Persistent,
                        // never in an exterior grid cell's Persistent group.
                        EnsureTopCellOverride().Persistent.Add(marker);
                        report.CreatedExteriorTopMarkers++;
                    }
                    fo4ToSfRef[r.FormKey] = newFk;
                    createdRefs[newFk] = marker;
                    continue;
                }

                // Connected AutoloadDoor pairs (e.g. RedRocket01 05E844 <-> Commonwealth 08EB65).
                if (autoloadInScope.ContainsKey(r.FormKey))
                {
                    var destFo4 = r.TeleportDestination!.Door.FormKey;
                    bool destOk = autoloadInScope.ContainsKey(destFo4) ||
                                  (fo4ToSfRef.TryGetValue(destFo4, out var existingDestSf) && IsResolvedDoorRef(existingDestSf));
                    if (destOk)
                    {
                        var newFk = AllocId($"DOOR:{r.FormKey.ID:X6}:{r.FormKey.ModKey.FileName}");
                        var doorObj = new SF.PlacedObject(newFk, SF.StarfieldRelease.Starfield)
                        {
                            Base = new FormLinkNullable<SF.IPlaceableObjectGetter>(AutoloadDoorCaveBase),
                            Position = ToMetres(r.Position),
                            Rotation = r.Rotation,
                        };
                        if (r.Scale is { } sc && Math.Abs(sc - 1f) > 1e-4f) doorObj.Scale = sc;
                        if ((r.MajorRecordFlagsRaw & 0x800) != 0) doorObj.MajorRecordFlagsRaw |= 0x800;
                        doorObj.MajorRecordFlagsRaw |= 0x400; // Persistent: all vanilla XTEL doors are persistent in TopCell / interior Persistent.

                        if (item.IsInterior)
                            GetIntCellOverride(item.PortCellKey!.Value).Persistent.Add(doorObj);
                        else
                            EnsureTopCellOverride().Persistent.Add(doorObj);

                        fo4ToSfRef[r.FormKey] = newFk;
                        createdRefs[newFk] = doorObj;
                        report.CreatedAutoloadDoors++;
                    }
                }
            }

            // Wire mutual XTEL on newly created AutoloadDoor endpoints.
            foreach (var (fo4Fk, item) in autoloadInScope)
            {
                if (!fo4ToSfRef.TryGetValue(fo4Fk, out var srcSfFk) || !createdRefs.TryGetValue(srcSfFk, out var srcDoor))
                    continue;
                var td = item.Fo4Ref.TeleportDestination!;
                if (!fo4ToSfRef.TryGetValue(td.Door.FormKey, out var dstSfFk) || !IsResolvedDoorRef(dstSfFk))
                    continue;
                srcDoor.TeleportDestination = new SF.TeleportDestination
                {
                    Position = ToMetres(td.Position),
                    Rotation = td.Rotation,
                    Flags = (SF.TeleportDestination.Flag)(uint)td.Flags,
                };
                srcDoor.TeleportDestination.Door.SetTo(dstSfFk);
                report.XtelCreatedLinks++;
            }

            // Helper: check whether a mapped Starfield FormKey is actually loaded/resolvable in the load order + createdRefs.
            bool IsResolvablePlacedRef(FormKey sfFk) =>
                createdRefs.ContainsKey(sfFk) || portRefRecords.ContainsKey(sfFk) || coreRefRecords.ContainsKey(sfFk);

            bool TryResolveFo4Ref(FormKey fo4Fk, out FormKey sfFk)
            {
                if (fo4ToSfRef.TryGetValue(fo4Fk, out sfFk) && IsResolvablePlacedRef(sfFk))
                    return true;
                sfFk = FormKey.Null;
                return false;
            }

            // Helper: generic FO4 KYWD creation (zero Name / Notes game text copied).
            var keywordMap = new Dictionary<FormKey, FormKey>();
            FormKey? ResolveOrCreateGenericKeyword(FormKey fo4KwFk)
            {
                if (keywordMap.TryGetValue(fo4KwFk, out var existing)) return existing;
                if (!fo4Cache.TryResolve<F4.IKeywordGetter>(fo4KwFk, out var fo4Kw)) return null;
                if (string.Equals(fo4Kw.EditorID, "MultirefLOD", StringComparison.OrdinalIgnoreCase)) return null;
                if (fo4Kw.MajorRecordFlagsRaw != 0 || !fo4Kw.AttractionRule.IsNull) return null;
                if (fo4Kw.Type != null && fo4Kw.Type != F4.Keyword.TypeEnum.None) return null;

                var norm = $"{fo4KwFk.ID:X6}:{fo4KwFk.ModKey.FileName.String.ToLowerInvariant()}";
                var kwFk = AllocId("KYWD:" + norm);
                if (mod.Keywords.All(k => k.FormKey != kwFk))
                {
                    var stem = Regex.Replace(fo4Kw.EditorID ?? "LinkedKeyword", "[^A-Za-z0-9_]", "_");
                    var salt = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(norm)))[..16];
                    var rec = new SF.Keyword(kwFk, SF.StarfieldRelease.Starfield)
                    {
                        EditorID = $"FO4SF_{stem}_{salt}",
                        Type = fo4Kw.Type == null ? null : SF.Keyword.TypeEnum.None,
                        Color = fo4Kw.Color,
                    };
                    mod.Keywords.Add(rec);
                    report.CreatedKeywords++;
                }
                keywordMap[fo4KwFk] = kwFk;
                return kwFk;
            }

            bool EffectiveDisabled(FormKey fo4Fk, HashSet<FormKey> visiting)
            {
                if (!enableTree.TryGetValue(fo4Fk, out var node)) return false;
                if (node.Parent is not { } pFk || !visiting.Add(fo4Fk)) return node.RawDisabled;
                bool opp = (node.Flags & 1u) != 0;
                bool pDis = enableTree.ContainsKey(pFk) ? EffectiveDisabled(pFk, visiting) : false;
                visiting.Remove(fo4Fk);
                return pDis ^ opp;
            }

            bool IsLockableBase(FormKey baseFk) =>
                baseFk == AutoloadDoorCaveBase ||
                masterCache.TryResolve<SF.IDoorGetter>(baseFk, out _) ||
                masterCache.TryResolve<SF.IContainerGetter>(baseFk, out _) ||
                masterCache.TryResolve<SF.ITerminalGetter>(baseFk, out _);

            // Mutable clone registry so multiple passes (XESP/XLOC/XLKR + XAPR) edit one override per FormKey.
            var workingClones = new Dictionary<FormKey, (SF.PlacedObject Clone, bool IsInterior, FormKey? PortCellKey, (int X, int Y)? ExtGrid, bool Persistent)>();
            SF.PlacedObject? GetMutableOverride(FormKey sfFk)
            {
                if (createdRefs.TryGetValue(sfFk, out var created)) return created;
                if (workingClones.TryGetValue(sfFk, out var existing)) return existing.Clone;
                if (portRefRecords.TryGetValue(sfFk, out var pr))
                {
                    var clone = SF.PlacedObjectMixIn.DeepCopy(pr.Obj);
                    workingClones[sfFk] = (clone, true, pr.CellKey, null, pr.Persistent);
                    return clone;
                }
                if (coreRefRecords.TryGetValue(sfFk, out var cr) && cr.Grid is { } g && requestedExtGrids.Contains(g))
                {
                    var clone = SF.PlacedObjectMixIn.DeepCopy(cr.Obj);
                    workingClones[sfFk] = (clone, false, null, g, cr.Persistent);
                    return clone;
                }
                return null;
            }

            SF.IPlacedObjectGetter? GetReadOnlyRef(FormKey sfFk)
            {
                if (createdRefs.TryGetValue(sfFk, out var c)) return c;
                if (workingClones.TryGetValue(sfFk, out var w)) return w.Clone;
                if (portRefRecords.TryGetValue(sfFk, out var p)) return p.Obj;
                if (coreRefRecords.TryGetValue(sfFk, out var r)) return r.Obj;
                return null;
            }

            // 4. Pass over in-scope placed references: count existing XTEL/script doors, apply XESP, XLOC, XLKR, collect XAPR.
            var xaprByParent = new Dictionary<FormKey, List<(FormKey ChildSf, float Delay, bool ChildParentOnly)>>();
            var xaprBlockedChildren = new HashSet<FormKey>();

            foreach (var item in scopeRefs)
            {
                var r = item.Fo4Ref;
                if (!TryResolveFo4Ref(r.FormKey, out var sfFk))
                {
                    if (r.ActivateParents != null && r.ActivateParents.Parents.Count > 0)
                        report.XaprChildNotPlaced++;
                    continue;
                }
                if (createdRefs.ContainsKey(sfFk)) continue; // Newly created markers/doors already handled above.
                var orig = GetReadOnlyRef(sfFk);
                if (orig == null) continue;

                // Record existing native XTEL or scripted load-door bridges in scope so nothing clobbers them.
                if (orig.TeleportDestination != null && !orig.TeleportDestination.Door.IsNull)
                    report.XtelExistingNativePreserved++;
                if (orig.VirtualMachineAdapter?.Scripts.Any(s =>
                        s.Name.Equals("FO4SF_LoadDoor", StringComparison.OrdinalIgnoreCase) ||
                        s.Name.Equals("FO4SF_AnimatedLoadDoor", StringComparison.OrdinalIgnoreCase)) == true)
                    report.XtelExistingScriptPreserved++;

                // Collect XAPR edges.
                if (r.ActivateParents is { } ap && ap.Parents.Count > 0)
                {
                    bool parentOnly = ((uint)ap.Flags & 1u) != 0;
                    int wiredHere = 0;
                    foreach (var p in ap.Parents)
                    {
                        if (!float.IsFinite(p.Delay) || p.Delay < 0f) continue;
                        if (p.Reference.IsNull || !TryResolveFo4Ref(p.Reference.FormKey, out var parentSfFk))
                        {
                            report.XaprParentNotPlaced++;
                            continue;
                        }
                        if (parentSfFk == sfFk) continue;
                        // Parent must also be editable in scope (interior cell or requested exterior grid).
                        if (portRefRecords.ContainsKey(parentSfFk) && !portCellByKey.ContainsKey(portRefRecords[parentSfFk].CellKey))
                        {
                            report.XaprParentNotPlaced++;
                            continue;
                        }
                        if (coreRefRecords.ContainsKey(parentSfFk) && (coreRefRecords[parentSfFk].Grid is not { } pg || !requestedExtGrids.Contains(pg)))
                        {
                            report.XaprParentNotPlaced++;
                            continue;
                        }
                        if (!xaprByParent.TryGetValue(parentSfFk, out var list))
                            xaprByParent[parentSfFk] = list = new();
                        if (!list.Any(x => x.ChildSf == sfFk))
                        {
                            list.Add((sfFk, p.Delay, parentOnly));
                            wiredHere++;
                        }
                    }
                    if (parentOnly && wiredHere > 0)
                        xaprBlockedChildren.Add(sfFk);
                }

                // Evaluate whether XESP, XLOC, or XLKR mutates this reference.
                bool needXesp = false;
                FormKey xespTarget = FormKey.Null;
                uint xespFlags = 0;
                bool needFoldFlip = false;
                bool foldValue = false;

                if (r.EnableParent is { } ep)
                {
                    var flags = (uint)ep.Flags;
                    if ((flags & ~3u) == 0)
                    {
                        if (!ep.Reference.IsNull && TryResolveFo4Ref(ep.Reference.FormKey, out var pSfFk) && pSfFk != sfFk)
                        {
                            if (orig.EnableParent == null || orig.EnableParent.Reference.FormKey != pSfFk || (uint)orig.EnableParent.Flags != flags)
                            {
                                needXesp = true;
                                xespTarget = pSfFk;
                                xespFlags = flags;
                            }
                        }
                        else
                        {
                            report.XespUnplacedParentSkipped++;
                            bool effDis = EffectiveDisabled(r.FormKey, new HashSet<FormKey>());
                            bool curDis = (orig.MajorRecordFlagsRaw & 0x800) != 0;
                            if (effDis != curDis)
                            {
                                needFoldFlip = true;
                                foldValue = effDis;
                            }
                        }
                    }
                }

                bool needXloc = false;
                int xlocLevel = 0;
                uint xlocFlags = 0;
                FormKey xlocKey = FormKey.Null;
                bool xlocMappedKey = false;
                bool xlocFallback = false;

                if (r.Lock is { } lk)
                {
                    int level = (int)lk.Level;
                    uint lFlags = (uint)lk.Flags;
                    bool hasSrcKey = !lk.Key.IsNull;
                    if (level == 0 && !hasSrcKey && lFlags == 0)
                        report.XlocUnlockedZeroSkipped++;
                    else if (!IsLockableBase(orig.Base.FormKey))
                        report.XlocNonLockableSkipped++;
                    else if (RefusedLockLevels.Contains(level))
                        report.XlocUnsupportedLevelSkipped++;
                    else if ((lFlags & ~1u) == 0 && (PickableLockLevels.Contains(level) || level == 255))
                    {
                        bool mapped = hasSrcKey && fo4ToSfKeym.TryGetValue(lk.Key.FormKey, out xlocKey);
                        if (level == 255 && !mapped)
                        {
                            report.XlocUnopenableRequiresKeySkipped++;
                        }
                        else if (orig.Lock == null || (int)orig.Lock.Level != level || (uint)orig.Lock.Flags != lFlags ||
                                 orig.Lock.Key.FormKey != (mapped ? xlocKey : FormKey.Null))
                        {
                            needXloc = true;
                            xlocLevel = level;
                            xlocFlags = lFlags;
                            xlocMappedKey = mapped;
                            xlocFallback = hasSrcKey && !mapped;
                        }
                    }
                }

                var pendingXlkr = new List<(FormKey? Union, FormKey Target)>();
                foreach (var lr in r.LinkedReferences)
                {
                    if (!lr.KeywordOrReference.IsNull &&
                        fo4Cache.TryResolve<F4.IKeywordGetter>(lr.KeywordOrReference.FormKey, out var kwCheck) &&
                        string.Equals(kwCheck.EditorID, "MultirefLOD", StringComparison.OrdinalIgnoreCase))
                    {
                        report.XlkrMultirefLodSkipped++;
                        continue;
                    }
                    if (lr.Reference.IsNull || !TryResolveFo4Ref(lr.Reference.FormKey, out var targetSfFk))
                    {
                        report.XlkrDanglingSkipped++;
                        continue;
                    }
                    FormKey? unionSfFk = null;
                    if (!lr.KeywordOrReference.IsNull)
                    {
                        if (TryResolveFo4Ref(lr.KeywordOrReference.FormKey, out var unionRefFk))
                            unionSfFk = unionRefFk;
                        else if (ResolveOrCreateGenericKeyword(lr.KeywordOrReference.FormKey) is { } kwFk)
                            unionSfFk = kwFk;
                        else
                        {
                            report.XlkrUnmappedUnionSkipped++;
                            continue;
                        }
                    }
                    var desiredU = unionSfFk ?? FormKey.Null;
                    bool already = orig.LinkedReferences.Any(x => x.Reference.FormKey == targetSfFk && x.KeywordOrReference.FormKey == desiredU) ||
                                   pendingXlkr.Any(x => x.Target == targetSfFk && (x.Union ?? FormKey.Null) == desiredU);
                    if (!already)
                        pendingXlkr.Add((unionSfFk, targetSfFk));
                }

                if (!needXesp && !needFoldFlip && !needXloc && pendingXlkr.Count == 0)
                    continue;

                var clone = GetMutableOverride(sfFk);
                if (clone == null) continue;

                if (needXesp)
                {
                    clone.EnableParent = new SF.EnableParent { Flags = (SF.EnableParent.Flag)xespFlags };
                    clone.EnableParent.Reference.SetTo(xespTarget);
                    report.XespWritten++;
                    if ((xespFlags & 1u) != 0) report.XespOppositeWritten++;
                    if ((xespFlags & 2u) != 0) report.XespPopInWritten++;
                }
                if (needFoldFlip)
                {
                    if (foldValue) clone.MajorRecordFlagsRaw |= 0x800;
                    else clone.MajorRecordFlagsRaw &= ~0x800;
                    report.XespFoldedInitialState++;
                }
                if (needXloc)
                {
                    clone.Lock = new SF.LockData
                    {
                        Level = (SF.LockLevel)xlocLevel,
                        Flags = (SF.LockData.Flag)xlocFlags,
                    };
                    if (xlocMappedKey)
                    {
                        clone.Lock.Key.SetTo(xlocKey);
                        report.XlocKeyMapped++;
                    }
                    else if (xlocFallback)
                    {
                        report.XlocUnmappedKeyFallback++;
                    }
                    report.XlocWritten++;
                }
                foreach (var (uFk, tFk) in pendingXlkr)
                {
                    var entry = new SF.LinkedReferences();
                    entry.Reference.SetTo(tFk);
                    if (uFk is { } u) entry.KeywordOrReference.SetTo(u);
                    clone.LinkedReferences.Add(entry);
                    report.XlkrWritten++;
                }
            }

            // 5. Wire XAPR chains (FO4SF_ActivateChain VMAD + KYWD:FO4SF_ActivateChainLink XLKR).
            static SF.ScriptEntry GetOrAddChainScript(SF.PlacedObject obj, OverlayBuildReport rep)
            {
                obj.VirtualMachineAdapter ??= new SF.VirtualMachineAdapter { Version = 6, ObjectFormat = 2 };
                int removed = obj.VirtualMachineAdapter.Scripts.RemoveAll(s =>
                    string.Equals(s.Name, LegacySingleScriptName, StringComparison.OrdinalIgnoreCase));
                if (removed > 0)
                {
                    rep.XaprUpgradedLegacySingleLinks += removed;
                    for (int i = obj.LinkedReferences.Count - 1; i >= 0; i--)
                        if (obj.LinkedReferences[i].KeywordOrReference.FormKey == LegacyLinkCustom02)
                            obj.LinkedReferences.RemoveAt(i);
                }
                var existing = obj.VirtualMachineAdapter.Scripts.FirstOrDefault(s =>
                    string.Equals(s.Name, ChainScriptName, StringComparison.OrdinalIgnoreCase));
                if (existing != null) return existing;
                var entry = new SF.ScriptEntry { Name = ChainScriptName, Flags = SF.ScriptEntry.Flag.Local };
                obj.VirtualMachineAdapter.Scripts.Add(entry);
                return entry;
            }

            foreach (var (parentSf, edges) in xaprByParent.OrderBy(kv => kv.Key.ToString(), StringComparer.Ordinal))
            {
                var pClone = GetMutableOverride(parentSf);
                if (pClone == null) continue;
                var script = GetOrAddChainScript(pClone, report);
                script.Properties.RemoveAll(p =>
                    string.Equals(p.Name, "Targets", StringComparison.OrdinalIgnoreCase) ||
                    string.Equals(p.Name, "Delays", StringComparison.OrdinalIgnoreCase) ||
                    string.Equals(p.Name, "UnblockTargets", StringComparison.OrdinalIgnoreCase));

                var targetsProp = new SF.ScriptObjectListProperty { Name = "Targets", Flags = SF.ScriptProperty.Flag.Edited };
                var delaysProp = new SF.ScriptFloatListProperty { Name = "Delays", Flags = SF.ScriptProperty.Flag.Edited };
                var unblockProp = new SF.ScriptBoolListProperty { Name = "UnblockTargets", Flags = SF.ScriptProperty.Flag.Edited };

                foreach (var edge in edges)
                {
                    targetsProp.Objects.Add(new SF.ScriptObjectProperty
                    {
                        Name = "", Flags = SF.ScriptProperty.Flag.Edited,
                        Object = new FormLink<SF.IStarfieldMajorRecordGetter>(edge.ChildSf),
                        Alias = -1, Unused = 0,
                    });
                    delaysProp.Data.Add(edge.Delay);
                    unblockProp.Data.Add(edge.ChildParentOnly);
                    if (edge.Delay > 1e-6f) report.XaprDelaysPreserved++;
                }
                script.Properties.Add(targetsProp);
                script.Properties.Add(delaysProp);
                script.Properties.Add(unblockProp);
                report.XaprParentsWired++;
                report.XaprEdgesWired += edges.Count;
            }

            foreach (var childSf in xaprBlockedChildren.OrderBy(k => k.ToString(), StringComparer.Ordinal))
            {
                var cClone = GetMutableOverride(childSf);
                if (cClone == null) continue;
                var script = GetOrAddChainScript(cClone, report);
                script.Properties.RemoveAll(p => string.Equals(p.Name, "ParentActivateOnly", StringComparison.OrdinalIgnoreCase));
                script.Properties.Add(new SF.ScriptBoolProperty
                {
                    Name = "ParentActivateOnly", Flags = SF.ScriptProperty.Flag.Edited, Data = true,
                });
                report.XaprParentActivateOnlyApplied++;
            }

            // 6. Attach all workingClones into their owning override cells (preserving master Persistent vs Temporary group).
            foreach (var (_, entry) in workingClones.OrderBy(kv => kv.Key.ToString(), StringComparer.Ordinal))
            {
                report.OverriddenReferences++;
                if (entry.IsInterior)
                {
                    var cell = GetIntCellOverride(entry.PortCellKey!.Value);
                    if (entry.Persistent) cell.Persistent.Add(entry.Clone);
                    else cell.Temporary.Add(entry.Clone);
                }
                else
                {
                    // CRITICAL (#712): Exterior grid references stay in gridCell.Temporary so they keep the planetary
                    // merge offset (-1200, -2700) m and never populate exterior grid Cell.Persistent.
                    var cell = GetExtCellOverride(entry.ExtGrid!.Value);
                    cell.Temporary.Add(entry.Clone);
                }
            }

            // Verify existing NavmeshGeometry.DoorTriangles on scanned exterior/interior cells, and apply optional navmesh_doors patches.
            if (root.TryGetProperty("navmesh_door_triangles", out var navDoorsEl) && navDoorsEl.ValueKind == JsonValueKind.Array)
            {
                foreach (var nd in navDoorsEl.EnumerateArray())
                {
                    var cellFk = FormKey.Factory(nd.GetProperty("cell").GetString()!);
                    var navFk = FormKey.Factory(nd.GetProperty("navmesh").GetString()!);
                    var doorFo4 = FormKey.Factory(nd.GetProperty("fo4_door").GetString()!);
                    short triIdx = nd.GetProperty("triangle").GetInt16();
                    if (!TryResolveFo4Ref(doorFo4, out var sfDoorFk)) continue;
                    if (portCellByKey.TryGetValue(cellFk, out var srcCell))
                    {
                        var srcNav = srcCell.NavigationMeshes.FirstOrDefault(n => n.FormKey == navFk);
                        if (srcNav != null)
                        {
                            var navCopy = SF.NavigationMeshMixIn.DeepCopy(srcNav);
                            if (navCopy.NavmeshGeometry != null &&
                                !navCopy.NavmeshGeometry.DoorTriangles.Any(d => d.Door.FormKey == sfDoorFk && d.TriangleBeforeDoor == triIdx))
                            {
                                navCopy.NavmeshGeometry.DoorTriangles.Add(new SF.DoorTriangle
                                {
                                    TriangleBeforeDoor = triIdx,
                                    Unknown = 1,
                                    Door = new FormLink<SF.IPlacedObjectGetter>(sfDoorFk),
                                });
                                GetIntCellOverride(cellFk).NavigationMeshes.Add(navCopy);
                                report.NavmeshDoorTrianglesVerified++;
                            }
                        }
                    }
                }
            }

            foreach (var g in requestedExtGrids)
                if (coreGridCells.TryGetValue(g, out var ce))
                    foreach (var nm in ce.Cell.NavigationMeshes)
                        if (nm.NavmeshGeometry?.DoorTriangles is { } dts)
                            foreach (var dt in dts)
                                if (!dt.Door.IsNull && IsResolvablePlacedRef(dt.Door.FormKey))
                                    report.NavmeshDoorTrianglesVerified++;

            // 7. Emit interior cell blocks & worldspace into mod.
            foreach (var (cellKey, cell) in intCellOverrides.OrderBy(kv => kv.Key.ID))
            {
                var cid = cellKey.ID;
                var block = mod.Cells.Records.FirstOrDefault(b => b.BlockNumber == (int)(cid % 10));
                if (block == null)
                {
                    block = new SF.CellBlock { BlockNumber = (int)(cid % 10), GroupType = SF.GroupTypeEnum.InteriorCellBlock };
                    mod.Cells.Records.Add(block);
                }
                var sub = block.SubBlocks.FirstOrDefault(s => s.BlockNumber == (int)((cid / 10) % 10));
                if (sub == null)
                {
                    sub = new SF.CellSubBlock { BlockNumber = (int)((cid / 10) % 10), GroupType = SF.GroupTypeEnum.InteriorCellSubBlock };
                    block.SubBlocks.Add(sub);
                }
                sub.Cells.Add(cell);
                report.InteriorCellsOverridden++;
            }

            if (worldOverride != null)
            {
                mod.Worldspaces.Add(worldOverride);
                report.WorldspaceOverridden = true;
                report.ExteriorCellsOverridden = extCellOverrides.Count;
            }

            mod.ModHeader.Stats.NextFormID = nextId;
            File.WriteAllText(mapPath, JsonSerializer.Serialize(
                new SortedDictionary<string, uint>(stableIds, StringComparer.Ordinal),
                new JsonSerializerOptions { WriteIndented = true }));

            var outPluginPath = Path.Combine(outDir, pluginName);
            mod.BeginWrite.ToPath(outPluginPath)
                .WithLoadOrder(loadOrderKeys.ToArray())
                .WithKnownMasters(knownStyles.ToArray())
                .Write();

            using (var writtenCheck = SF.StarfieldMod.CreateFromBinaryOverlay(outPluginPath, SF.StarfieldRelease.Starfield,
                       new BinaryReadParameters { MasterFlagsLookup = MasterStyles(loadOrderKeys.ToArray()) }))
            {
                report.Masters = writtenCheck.ModHeader.MasterReferences.Select(m => m.Master.FileName.String).ToList();
            }

            var reportPath = Path.Combine(outDir, "fidelity_build_report.json");
            File.WriteAllText(reportPath, JsonSerializer.Serialize(report, new JsonSerializerOptions { WriteIndented = true }));
            Console.WriteLine($"wrote {outPluginPath} ({new FileInfo(outPluginPath).Length:N0} bytes): " +
                              $"interiors {report.InteriorCellsOverridden}/{report.InteriorCellsScanned}, " +
                              $"exteriors {report.ExteriorCellsOverridden}/{report.ExteriorCellsScanned}, " +
                              $"XESP={report.XespWritten} (folded={report.XespFoldedInitialState}), " +
                              $"XLOC={report.XlocWritten}, XLKR={report.XlkrWritten}, " +
                              $"XAPR={report.XaprEdgesWired} edges on {report.XaprParentsWired} parents, " +
                              $"XTEL_created={report.XtelCreatedLinks} (existing_native={report.XtelExistingNativePreserved}, existing_script={report.XtelExistingScriptPreserved})");
            return 0;
        }
        finally
        {
            port?.Dispose();
            core?.Dispose();
        }
    }
}
