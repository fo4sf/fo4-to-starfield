using System.Text.Json;
using Mutagen.Bethesda;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Cache;
using Mutagen.Bethesda.Plugins.Records;
using Noggog;
using SF = Mutagen.Bethesda.Starfield;

public sealed record FidelityCheckItem(string Name, bool Ok, string Detail);

public static class FidelityCheck
{
    private static readonly HashSet<int> AllowedLockLevels = new() { 1, 25, 50, 75, 100, 255 };

    public static int RunCli(string[] args)
    {
        var pluginPath = args[1];
        string? sfPath = null, corePath = null, portPath = null, portRefPath = null, reportPath = null;
        for (int i = 2; i < args.Length; i++)
        {
            switch (args[i])
            {
                case "--starfield" when i + 1 < args.Length: sfPath = args[++i]; break;
                case "--core" when i + 1 < args.Length: corePath = args[++i]; break;
                case "--port" when i + 1 < args.Length: portPath = args[++i]; break;
                case "--port-reference" when i + 1 < args.Length: portRefPath = args[++i]; break;
                case "--report" when i + 1 < args.Length: reportPath = args[++i]; break;
                default: throw new InvalidOperationException($"unknown check option: {args[i]}");
            }
        }
        if (string.IsNullOrEmpty(sfPath))
            throw new InvalidOperationException("check requires --starfield <Starfield.esm>");
        return Run(pluginPath, sfPath, corePath, portPath, portRefPath, reportPath);
    }

    public static int Run(string pluginPath, string sfPath, string? corePath = null, string? portPath = null,
        string? portRefPath = null, string? reportPath = null)
    {
        using var sf = SF.StarfieldMod.CreateFromBinaryOverlay(sfPath, SF.StarfieldRelease.Starfield);
        SF.IStarfieldModDisposableGetter? core = null;
        SF.IStarfieldModDisposableGetter? port = null;
        SF.IStarfieldModDisposableGetter? portRef = null;
        try
        {
            var masterKeys = new List<ModKey> { OverlayBuilder.SfModKey };
            var cacheMods = new List<SF.IStarfieldModGetter> { sf };

            if (!string.IsNullOrEmpty(corePath))
            {
                core = SF.StarfieldMod.CreateFromBinaryOverlay(corePath, SF.StarfieldRelease.Starfield,
                    new BinaryReadParameters { MasterFlagsLookup = OverlayBuilder.MasterStyles(OverlayBuilder.SfModKey) });
                masterKeys.Add(core.ModKey);
                cacheMods.Add(core);
            }
            if (!string.IsNullOrEmpty(portPath))
            {
                port = SF.StarfieldMod.CreateFromBinaryOverlay(portPath, SF.StarfieldRelease.Starfield,
                    new BinaryReadParameters { MasterFlagsLookup = OverlayBuilder.MasterStyles(OverlayBuilder.SfModKey) });
                masterKeys.Add(port.ModKey);
                cacheMods.Add(port);
            }

            using var mod = SF.StarfieldMod.CreateFromBinaryOverlay(pluginPath, SF.StarfieldRelease.Starfield,
                new BinaryReadParameters { MasterFlagsLookup = OverlayBuilder.MasterStyles(masterKeys.ToArray()) });
            cacheMods.Add(mod);
            var cache = cacheMods.ToImmutableLinkCache<SF.IStarfieldMod, SF.IStarfieldModGetter>();

            // Optional cross-cell reference port for single-cell PluginSpike re-conversions.
            var convertedCellKeys = mod.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells).Select(c => c.FormKey).ToHashSet();
            var externalCellPlaced = new Dictionary<FormKey, (SF.IPlacedObjectGetter Obj, bool Persistent, bool IsDoor)>();
            if (!string.IsNullOrEmpty(portRefPath))
            {
                portRef = SF.StarfieldMod.CreateFromBinaryOverlay(portRefPath, SF.StarfieldRelease.Starfield,
                    new BinaryReadParameters { MasterFlagsLookup = OverlayBuilder.MasterStyles(OverlayBuilder.SfModKey) });
                var refCache = new SF.IStarfieldModGetter[] { sf, portRef }.ToImmutableLinkCache<SF.IStarfieldMod, SF.IStarfieldModGetter>();
                foreach (var c in portRef.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells))
                {
                    if (convertedCellKeys.Contains(c.FormKey)) continue;
                    foreach (var p in c.Persistent.OfType<SF.IPlacedObjectGetter>())
                        if ((p.MajorRecordFlagsRaw & 0x20) == 0)
                            externalCellPlaced[p.FormKey] = (p, (p.MajorRecordFlagsRaw & 0x400) != 0, refCache.TryResolve<SF.IDoorGetter>(p.Base.FormKey, out _));
                    foreach (var t in c.Temporary.OfType<SF.IPlacedObjectGetter>())
                        if ((t.MajorRecordFlagsRaw & 0x20) == 0)
                            externalCellPlaced.TryAdd(t.FormKey, (t, false, refCache.TryResolve<SF.IDoorGetter>(t.Base.FormKey, out _)));
                }
            }

            bool TryResolvePlaced(FormKey fk, out SF.IPlacedObjectGetter? placed, out bool isPersistent, out bool isDoorBase)
            {
                if (!fk.IsNull && cache.TryResolve<SF.IPlacedObjectGetter>(fk, out var hit) && (hit.MajorRecordFlagsRaw & 0x20) == 0)
                {
                    placed = hit;
                    isPersistent = (hit.MajorRecordFlagsRaw & 0x400) != 0;
                    isDoorBase = cache.TryResolve<SF.IDoorGetter>(hit.Base.FormKey, out _);
                    return true;
                }
                if (!fk.IsNull && externalCellPlaced.TryGetValue(fk, out var ext))
                {
                    placed = ext.Obj;
                    isPersistent = ext.Persistent;
                    isDoorBase = ext.IsDoor;
                    return true;
                }
                placed = null;
                isPersistent = false;
                isDoorBase = false;
                return false;
            }

            var items = new List<FidelityCheckItem>();
            void Add(string name, bool ok, string detail) => items.Add(new FidelityCheckItem(name, ok, detail));

            // 1. Header & masters.
            Add("esm master flag", mod.ModHeader.Flags.HasFlag(SF.StarfieldModHeader.HeaderFlag.Master), mod.ModHeader.Flags.ToString());
            var headerMasters = mod.ModHeader.MasterReferences.Select(m => m.Master).ToList();
            Add("masters resolvable in load order", headerMasters.All(m => masterKeys.Contains(m)),
                string.Join(", ", headerMasters.Select(m => m.FileName.String)));

            // 2. Keywords owned by mod carry zero game text (Name / Notes).
            var badKeywords = new List<string>();
            foreach (var kw in mod.Keywords.Where(k => k.FormKey.ModKey == mod.ModKey))
            {
                if (kw.Name != null || kw.Notes != null)
                    badKeywords.Add($"{kw.FormKey} carries Name/Notes");
            }
            Add("keywords free of game text", badKeywords.Count == 0,
                badKeywords.Count == 0 ? $"{mod.Keywords.Count} keywords clean" : string.Join("; ", badKeywords.Take(5)));

            // 3. Gather all PlacedObjects and NavigationMeshes in mod, enforcing zero exterior grid Persistent refs (#712).
            var allRefs = new List<(SF.IPlacedObjectGetter Ref, bool InPersistentGroup, bool IsExteriorGrid)>();
            var allNavs = new List<SF.INavigationMeshGetter>();
            var extGridPersistentViolations = new List<string>();

            foreach (var c in mod.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells))
            {
                foreach (var p in c.Persistent.OfType<SF.IPlacedObjectGetter>()) allRefs.Add((p, true, false));
                foreach (var t in c.Temporary.OfType<SF.IPlacedObjectGetter>()) allRefs.Add((t, false, false));
                allNavs.AddRange(c.NavigationMeshes);
            }
            foreach (var w in mod.Worldspaces)
            {
                if (w.TopCell != null)
                {
                    foreach (var p in w.TopCell.Persistent.OfType<SF.IPlacedObjectGetter>()) allRefs.Add((p, true, false));
                    foreach (var t in w.TopCell.Temporary.OfType<SF.IPlacedObjectGetter>()) allRefs.Add((t, false, false));
                    allNavs.AddRange(w.TopCell.NavigationMeshes);
                }
                foreach (var blk in w.SubCells)
                    foreach (var sub in blk.Items)
                        foreach (var ec in sub.Items)
                        {
                            if (ec.Persistent.Count > 0)
                                extGridPersistentViolations.Add($"{ec.FormKey} ({ec.Grid?.Point}): {ec.Persistent.Count} persistent children");
                            foreach (var p in ec.Persistent.OfType<SF.IPlacedObjectGetter>()) allRefs.Add((p, true, true));
                            foreach (var t in ec.Temporary.OfType<SF.IPlacedObjectGetter>()) allRefs.Add((t, false, true));
                            allNavs.AddRange(ec.NavigationMeshes);
                        }
            }
            Add("exterior grid cells have zero persistent children", extGridPersistentViolations.Count == 0,
                extGridPersistentViolations.Count == 0 ? "0 exterior grid persistent refs" : string.Join("; ", extGridPersistentViolations.Take(5)));

            // 4. Validate all 5 subrecord families across allRefs.
            var xespErrors = new List<string>();
            var xlocErrors = new List<string>();
            var xlkrErrors = new List<string>();
            var xaprErrors = new List<string>();
            var xtelErrors = new List<string>();
            int nXesp = 0, nXloc = 0, nXlkr = 0, nXaprEdges = 0, nXtel = 0;

            static bool Finite(P3Float v) => float.IsFinite(v.X) && float.IsFinite(v.Y) && float.IsFinite(v.Z);

            foreach (var (r, inPersGroup, _) in allRefs)
            {
                if ((r.MajorRecordFlagsRaw & 0x20) != 0) continue;

                // XESP
                if (r.EnableParent is { } ep)
                {
                    nXesp++;
                    uint flags = (uint)ep.Flags;
                    if ((flags & ~3u) != 0)
                        xespErrors.Add($"{r.FormKey}: invalid XESP flags 0x{flags:X}");
                    else if (ep.Reference.IsNull || ep.Reference.FormKey == r.FormKey)
                        xespErrors.Add($"{r.FormKey}: null or self XESP reference {ep.Reference.FormKey}");
                    else if (!TryResolvePlaced(ep.Reference.FormKey, out _, out _, out _))
                        xespErrors.Add($"{r.FormKey}: dangling XESP parent {ep.Reference.FormKey}");
                }

                // XLOC
                if (r.Lock is { } lk)
                {
                    nXloc++;
                    bool lockable = cache.TryResolve<SF.IDoorGetter>(r.Base.FormKey, out _) ||
                                    cache.TryResolve<SF.IContainerGetter>(r.Base.FormKey, out _) ||
                                    cache.TryResolve<SF.ITerminalGetter>(r.Base.FormKey, out _);
                    int lvl = (int)lk.Level;
                    uint lFlags = (uint)lk.Flags;
                    if (!lockable)
                        xlocErrors.Add($"{r.FormKey}: XLOC on non-DOOR/CONT/TERM base {r.Base.FormKey}");
                    else if (!AllowedLockLevels.Contains(lvl))
                        xlocErrors.Add($"{r.FormKey}: disallowed XLOC level {lvl}");
                    else if ((lFlags & ~1u) != 0)
                        xlocErrors.Add($"{r.FormKey}: unsupported XLOC flags 0x{lFlags:X}");
                    else if (!lk.Key.IsNull)
                    {
                        if (!cache.TryResolve<SF.IKeyGetter>(lk.Key.FormKey, out var keyRec) || (keyRec.MajorRecordFlagsRaw & 0x20) != 0)
                            xlocErrors.Add($"{r.FormKey}: dangling XLOC key {lk.Key.FormKey}");
                    }
                    else if (lvl == 255)
                    {
                        xlocErrors.Add($"{r.FormKey}: RequiresKey (255) lock without a mapped KEYM");
                    }
                }

                // XLKR
                foreach (var lr in r.LinkedReferences)
                {
                    nXlkr++;
                    if (lr.Reference.IsNull || !TryResolvePlaced(lr.Reference.FormKey, out _, out _, out _))
                        xlkrErrors.Add($"{r.FormKey}: dangling XLKR target {lr.Reference.FormKey}");
                    if (!lr.KeywordOrReference.IsNull)
                    {
                        bool unionOk = TryResolvePlaced(lr.KeywordOrReference.FormKey, out _, out _, out _) ||
                                       (cache.TryResolve<SF.IKeywordGetter>(lr.KeywordOrReference.FormKey, out var kw) &&
                                        (kw.MajorRecordFlagsRaw & 0x20) == 0);
                        if (!unionOk)
                            xlkrErrors.Add($"{r.FormKey}: dangling XLKR union {lr.KeywordOrReference.FormKey}");
                    }
                }

                // XAPR (FO4SF_ActivateChain VMAD)
                if (r.VirtualMachineAdapter is { } vmad)
                {
                    var chainScripts = vmad.Scripts.Where(s => s.Name.Equals(OverlayBuilder.ChainScriptName, StringComparison.OrdinalIgnoreCase)).ToList();
                    if (chainScripts.Count > 1)
                        xaprErrors.Add($"{r.FormKey}: duplicate {OverlayBuilder.ChainScriptName} script entries ({chainScripts.Count})");
                    if (chainScripts.Count > 0 &&
                        vmad.Scripts.Any(s => s.Name.Equals(OverlayBuilder.LegacySingleScriptName, StringComparison.OrdinalIgnoreCase)))
                        xaprErrors.Add($"{r.FormKey}: carries both {OverlayBuilder.ChainScriptName} and {OverlayBuilder.LegacySingleScriptName}");

                    foreach (var cs in chainScripts)
                    {
                        var tProp = cs.Properties.FirstOrDefault(p => p.Name.Equals("Targets", StringComparison.OrdinalIgnoreCase));
                        var dProp = cs.Properties.FirstOrDefault(p => p.Name.Equals("Delays", StringComparison.OrdinalIgnoreCase));
                        var uProp = cs.Properties.FirstOrDefault(p => p.Name.Equals("UnblockTargets", StringComparison.OrdinalIgnoreCase));
                        var pOnlyProp = cs.Properties.FirstOrDefault(p => p.Name.Equals("ParentActivateOnly", StringComparison.OrdinalIgnoreCase));

                        if (tProp == null && pOnlyProp == null)
                        {
                            xaprErrors.Add($"{r.FormKey}: {OverlayBuilder.ChainScriptName} has neither Targets nor ParentActivateOnly");
                            continue;
                        }
                        if (pOnlyProp != null && pOnlyProp is not SF.IScriptBoolPropertyGetter)
                            xaprErrors.Add($"{r.FormKey}: ParentActivateOnly is not a Bool property");

                        if (tProp != null)
                        {
                            if (tProp is not SF.IScriptObjectListPropertyGetter tList ||
                                dProp is not SF.IScriptFloatListPropertyGetter dList ||
                                uProp is not SF.IScriptBoolListPropertyGetter uList)
                            {
                                xaprErrors.Add($"{r.FormKey}: Targets / Delays / UnblockTargets property types invalid or missing");
                                continue;
                            }
                            if (tList.Objects.Count == 0 || dList.Data.Count != tList.Objects.Count || uList.Data.Count != tList.Objects.Count)
                            {
                                xaprErrors.Add($"{r.FormKey}: mismatched array lengths Targets={tList.Objects.Count} Delays={dList.Data.Count} Unblock={uList.Data.Count}");
                                continue;
                            }
                            for (int i = 0; i < tList.Objects.Count; i++)
                            {
                                nXaprEdges++;
                                var tfk = tList.Objects[i].Object.FormKey;
                                var dly = dList.Data[i];
                                if (!float.IsFinite(dly) || dly < 0f)
                                    xaprErrors.Add($"{r.FormKey}: invalid XAPR delay {dly} at index {i}");
                                if (tfk.IsNull || tfk == r.FormKey || !TryResolvePlaced(tfk, out _, out _, out _))
                                    xaprErrors.Add($"{r.FormKey}: invalid or dangling XAPR target {tfk} at index {i}");
                            }
                        }
                    }
                }

                // XTEL
                if (r.TeleportDestination is { } td)
                {
                    nXtel++;
                    uint tFlags = (uint)td.Flags;
                    bool srcDoor = cache.TryResolve<SF.IDoorGetter>(r.Base.FormKey, out _);
                    if (!srcDoor)
                        xtelErrors.Add($"{r.FormKey}: XTEL on non-DOOR base {r.Base.FormKey}");
                    else if (!inPersGroup || (r.MajorRecordFlagsRaw & 0x400) == 0)
                        xtelErrors.Add($"{r.FormKey}: XTEL source is not persistent (group={inPersGroup}, flags=0x{r.MajorRecordFlagsRaw:X})");
                    else if ((tFlags & ~7u) != 0 || (tFlags & 4u) != 0)
                        xtelErrors.Add($"{r.FormKey}: unsupported XTEL flags 0x{tFlags:X}");
                    else if (!td.TransitionInterior.IsNull)
                        xtelErrors.Add($"{r.FormKey}: non-null TransitionInterior {td.TransitionInterior.FormKey}");
                    else if (!Finite(td.Position) || !Finite(td.Rotation))
                        xtelErrors.Add($"{r.FormKey}: non-finite XTEL position/rotation");
                    else if (td.Door.IsNull || !TryResolvePlaced(td.Door.FormKey, out _, out var dstPers, out var dstDoor) || !dstPers || !dstDoor)
                        xtelErrors.Add($"{r.FormKey}: XTEL destination {td.Door.FormKey} is missing, non-DOOR, or non-persistent");
                }
            }

            // 5. Validate NAVM DoorTriangles.
            var navErrors = new List<string>();
            int nDoorTris = 0;
            foreach (var nm in allNavs)
            {
                if ((nm.MajorRecordFlagsRaw & 0x20) != 0 || nm.NavmeshGeometry == null) continue;
                var triCount = nm.NavmeshGeometry.Triangles.Count;
                foreach (var dt in nm.NavmeshGeometry.DoorTriangles)
                {
                    nDoorTris++;
                    if (dt.TriangleBeforeDoor < 0 || dt.TriangleBeforeDoor >= triCount)
                        navErrors.Add($"{nm.FormKey}: DoorTriangle index {dt.TriangleBeforeDoor} outside 0..{triCount - 1}");
                    if (dt.Door.IsNull || !TryResolvePlaced(dt.Door.FormKey, out _, out _, out _))
                        navErrors.Add($"{nm.FormKey}: dangling DoorTriangle target {dt.Door.FormKey}");
                }
            }

            Add("XESP enable parents valid", xespErrors.Count == 0,
                xespErrors.Count == 0 ? $"{nXesp} XESP records verified" : string.Join("; ", xespErrors.Take(5)));
            Add("XLOC locks valid and openable", xlocErrors.Count == 0,
                xlocErrors.Count == 0 ? $"{nXloc} XLOC records verified" : string.Join("; ", xlocErrors.Take(5)));
            Add("XLKR linked references resolved", xlkrErrors.Count == 0,
                xlkrErrors.Count == 0 ? $"{nXlkr} XLKR pairs verified" : string.Join("; ", xlkrErrors.Take(5)));
            Add("XAPR activation chains valid", xaprErrors.Count == 0,
                xaprErrors.Count == 0 ? $"{nXaprEdges} XAPR edges verified" : string.Join("; ", xaprErrors.Take(5)));
            Add("XTEL teleport links valid", xtelErrors.Count == 0,
                xtelErrors.Count == 0 ? $"{nXtel} XTEL doors verified" : string.Join("; ", xtelErrors.Take(5)));
            Add("NAVM door triangles resolved", navErrors.Count == 0,
                navErrors.Count == 0 ? $"{nDoorTris} NAVM door triangles verified" : string.Join("; ", navErrors.Take(5)));

            bool allOk = items.All(i => i.Ok);
            if (!string.IsNullOrEmpty(reportPath))
            {
                Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(reportPath))!);
                File.WriteAllText(reportPath, JsonSerializer.Serialize(
                    new
                    {
                        ok = allOk,
                        counts = new { xesp = nXesp, xloc = nXloc, xlkr = nXlkr, xapr_edges = nXaprEdges, xtel = nXtel, navmesh_door_triangles = nDoorTris },
                        checks = items,
                    },
                    new JsonSerializerOptions { WriteIndented = true }));
            }

            foreach (var it in items)
                Console.WriteLine($"{(it.Ok ? "PASS" : "FAIL")}  {it.Name}: {it.Detail}");
            Console.WriteLine(allOk ? $"all {items.Count} checks pass" : $"{items.Count(i => !i.Ok)} of {items.Count} checks FAIL");
            return allOk ? 0 : 1;
        }
        finally
        {
            portRef?.Dispose();
            port?.Dispose();
            core?.Dispose();
        }
    }
}
