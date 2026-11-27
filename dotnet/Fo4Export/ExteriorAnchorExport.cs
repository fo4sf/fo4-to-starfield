using System.Text.Json;
using Mutagen.Bethesda;
using Mutagen.Bethesda.Fallout4;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Cache;
using Mutagen.Bethesda.Plugins.Records;
using Noggog;

/// <summary>F0 exterior-anchor reference scanner for WRLD subcells and persistent worldspace top cell.</summary>
public static class ExteriorAnchorExport
{
    public const double UnitsPerMeter = 70.0;
    public const double CellUnits = 4096.0;

    public static int Run(IReadOnlyList<IFallout4ModGetter> loadOrder, ILinkCache cache, string outPath, string worldSelector, IReadOnlyList<string> anchorSpecs)
    {
        var worldCopies = new List<(int Mod, IWorldspaceGetter World)>();
        FormKey? worldKey = null;
        bool wantHex = QuestRefExport.TryParseHexId(worldSelector, out var worldHex);

        for (int i = 0; i < loadOrder.Count; i++)
        {
            foreach (var w in loadOrder[i].Worldspaces)
            {
                bool hit = (worldKey != null && w.FormKey == worldKey.Value)
                    || (worldKey == null && ((wantHex && w.FormKey.ID == worldHex) || string.Equals(w.EditorID, worldSelector, StringComparison.OrdinalIgnoreCase)));
                if (hit)
                {
                    worldKey ??= w.FormKey;
                    worldCopies.Add((i, w));
                }
            }
        }
        if (worldKey == null || worldCopies.Count == 0)
        {
            Console.Error.WriteLine($"exterior-anchor: worldspace '{worldSelector}' not found");
            return 1;
        }
        var worldEdid = worldCopies.Select(c => c.World.EditorID).LastOrDefault(e => !string.IsNullOrEmpty(e)) ?? worldSelector;

        var placedKeys = CellMerge.PlacedKeys(loadOrder);
        var allCopies = CellMerge.Copies(loadOrder, worldspaces: true);
        var topKeys = worldCopies.Where(c => c.World.TopCell != null).Select(c => c.World.TopCell!.FormKey).ToHashSet();

        // Gather merged subcells (with grid coordinates) and merged TopCell entries for this worldspace.
        var worldCells = new List<(CellMerge.Merged Merged, (int X, int Y)? Grid, bool IsTopCell)>();
        var byRefId = new Dictionary<uint, (CellMerge.Placed Placed, CellMerge.Merged Merged, (int X, int Y)? Grid)>();

        foreach (var (ck, copies) in allCopies)
        {
            if (copies[^1].Worldspace != worldKey.Value.ToString()) continue;
            bool isTop = topKeys.Contains(ck);
            (int X, int Y)? grid = null;
            if (!isTop)
            {
                var g = copies.Select(c => c.Cell.Grid).LastOrDefault(x => x != null);
                if (g != null) grid = (g.Point.X, g.Point.Y);
            }
            var merged = CellMerge.Merge(copies, placedKeys);
            worldCells.Add((merged, grid, isTop));
            foreach (var ch in merged.Children)
                byRefId[ch.Record.FormKey.ID] = (ch, merged, grid);
        }

        var anchorsOut = new List<object>();
        foreach (var spec in anchorSpecs)
        {
            var parts = spec.Split(':');
            if (parts.Length < 1 || !QuestRefExport.TryParseHexId(parts[0], out var anchorId))
            {
                Console.Error.WriteLine($"exterior-anchor: invalid anchor spec '{spec}' (expected <FormID>:<radiusMeters>)");
                return 2;
            }
            double radiusM = parts.Length >= 2 ? double.Parse(parts[1], System.Globalization.CultureInfo.InvariantCulture) : 50.0;
            double radiusUnits = radiusM * UnitsPerMeter;

            if (!byRefId.TryGetValue(anchorId, out var anchorEntry))
            {
                Console.Error.WriteLine($"exterior-anchor: anchor ref 0x{anchorId:X8} not found in {worldEdid}");
                return 1;
            }
            var anchorPos = Position(anchorEntry.Placed.Record);
            if (anchorPos == null)
            {
                Console.Error.WriteLine($"exterior-anchor: anchor ref 0x{anchorId:X8} has no position");
                return 1;
            }

            double ax = anchorPos.Value.X, ay = anchorPos.Value.Y, az = anchorPos.Value.Z;
            int minGx = (int)Math.Floor((ax - radiusUnits) / CellUnits);
            int maxGx = (int)Math.Floor((ax + radiusUnits) / CellUnits);
            int minGy = (int)Math.Floor((ay - radiusUnits) / CellUnits);
            int maxGy = (int)Math.Floor((ay + radiusUnits) / CellUnits);

            var refsOut = new List<object>();
            var referencedRecords = new Dictionary<FormKey, object>();
            void TrackKey(FormKey fk)
            {
                if (!fk.IsNull && !referencedRecords.ContainsKey(fk))
                {
                    var r = ScriptExport.ResolveFormKey(fk, cache);
                    if (r != null) referencedRecords[fk] = r;
                }
            }

            foreach (var (merged, grid, isTop) in worldCells)
            {
                if (!isTop && grid is { } g && (g.X < minGx || g.X > maxGx || g.Y < minGy || g.Y > maxGy))
                    continue;
                foreach (var ch in merged.Children)
                {
                    var pos = Position(ch.Record);
                    if (pos == null) continue;
                    double dx = pos.Value.X - ax, dy = pos.Value.Y - ay, dz = pos.Value.Z - az;
                    double distXyUnits = Math.Sqrt(dx * dx + dy * dy);
                    if (distXyUnits > radiusUnits) continue;
                    double dist3dM = Math.Sqrt(dx * dx + dy * dy + dz * dz) / UnitsPerMeter;

                    var refGrid = isTop
                        ? ((int)Math.Floor(pos.Value.X / CellUnits), (int)Math.Floor(pos.Value.Y / CellUnits))
                        : grid!.Value;
                    refsOut.Add(BuildRefEntry(ch, merged, refGrid, distXyUnits / UnitsPerMeter, dist3dM, cache, TrackKey));
                }
            }

            anchorsOut.Add(new
            {
                anchor_form_id = ScriptExport.FormatFormId(anchorEntry.Placed.Record.FormKey),
                anchor_formkey = anchorEntry.Placed.Record.FormKey.ToString(),
                anchor_editor_id = anchorEntry.Placed.Record.EditorID ?? "",
                anchor_pos = new[] { ax, ay, az },
                radius_m = radiusM,
                radius_units = radiusUnits,
                cell_grid_bounds = new { min_x = minGx, max_x = maxGx, min_y = minGy, max_y = maxGy },
                ref_count = refsOut.Count,
                refs = refsOut,
                referenced_records = referencedRecords.Values,
            });
        }

        Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(outPath))!);
        File.WriteAllText(outPath, JsonSerializer.Serialize(new
        {
            schema_version = 1,
            worldspace = new { form_id = ScriptExport.FormatFormId(worldKey.Value), formkey = worldKey.Value.ToString(), editor_id = worldEdid },
            anchors = anchorsOut,
        }, new JsonSerializerOptions { WriteIndented = true }));
        Console.WriteLine($"exterior-anchor: {worldEdid}: {anchorsOut.Count} anchor(s) -> {outPath}");
        return 0;
    }

    private static object BuildRefEntry(
        CellMerge.Placed ch,
        CellMerge.Merged sourceCell,
        (int X, int Y) cellGrid,
        double distXyM,
        double dist3dM,
        ILinkCache cache,
        Action<FormKey> trackKey)
    {
        var r = ch.Record;
        trackKey(r.FormKey);
        trackKey(sourceCell.Cell.FormKey);

        FormKey baseFk = FormKey.Null;
        string baseEid = "", baseType = "", model = "";
        object? baseScripts = null;
        if (r is IPlacedObjectGetter po)
        {
            if (po.Base.TryResolve(cache, out var b))
            {
                baseFk = b.FormKey; baseEid = b.EditorID ?? "";
                baseType = b.GetType().Name.Replace("BinaryOverlay", "");
                if (b is IModeledGetter m && m.Model?.File != null) model = m.Model.File.ToString();
                baseScripts = ScriptExport.ScriptsResolved(b, cache);
                trackKey(baseFk);
            }
        }
        else if (r is IPlacedNpcGetter pn)
        {
            if (pn.Base.TryResolve(cache, out var b))
            {
                baseFk = b.FormKey; baseEid = b.EditorID ?? "";
                baseType = b.GetType().Name.Replace("BinaryOverlay", "");
                baseScripts = ScriptExport.ScriptsResolved(b, cache);
                trackKey(baseFk);
            }
        }

        var pos = Position(r)!.Value;
        var rot = Rotation(r);
        var scale = r is IPlacedObjectGetter o1 ? o1.Scale ?? 1.0f : (r is IPlacedNpcGetter n1 ? n1.Scale ?? 1.0f : 1.0f);

        var linked = new List<object>();
        IEnumerable<ILinkedReferencesGetter> lrList = r switch
        {
            IPlacedObjectGetter o => o.LinkedReferences,
            IPlacedNpcGetter n => n.LinkedReferences,
            _ => Array.Empty<ILinkedReferencesGetter>(),
        };
        foreach (var lr in lrList)
        {
            if (!lr.KeywordOrReference.IsNull) trackKey(lr.KeywordOrReference.FormKey);
            if (!lr.Reference.IsNull) trackKey(lr.Reference.FormKey);
            linked.Add(new
            {
                keyword = lr.KeywordOrReference.IsNull ? null : ScriptExport.ResolveFormKey(lr.KeywordOrReference.FormKey, cache),
                reference = lr.Reference.IsNull ? null : ScriptExport.ResolveFormKey(lr.Reference.FormKey, cache),
            });
        }

        object? enableParent = null;
        IEnableParentGetter? ep = r is IPlacedObjectGetter eo ? eo.EnableParent : (r is IPlacedNpcGetter en ? en.EnableParent : null);
        if (ep != null && !ep.Reference.IsNull)
        {
            trackKey(ep.Reference.FormKey);
            enableParent = new { reference = ScriptExport.ResolveFormKey(ep.Reference.FormKey, cache), flags = (uint)ep.Flags };
        }

        object? teleport = null;
        if (r is IPlacedObjectGetter to && to.TeleportDestination is { } td)
        {
            if (!td.Door.IsNull) trackKey(td.Door.FormKey);
            if (!td.TransitionInterior.IsNull) trackKey(td.TransitionInterior.FormKey);
            teleport = new
            {
                door = td.Door.IsNull ? null : ScriptExport.ResolveFormKey(td.Door.FormKey, cache),
                pos = new[] { td.Position.X, td.Position.Y, td.Position.Z },
                rot = new[] { td.Rotation.X, td.Rotation.Y, td.Rotation.Z },
                flags = (uint)td.Flags,
                transition_interior = td.TransitionInterior.IsNull ? null : ScriptExport.ResolveFormKey(td.TransitionInterior.FormKey, cache),
            };
        }

        object? lockData = null;
        if (r is IPlacedObjectGetter lo && lo.Lock is { } lk)
        {
            if (!lk.Key.IsNull) trackKey(lk.Key.FormKey);
            lockData = new
            {
                level = (int)lk.Level,
                key = lk.Key.IsNull ? null : ScriptExport.ResolveFormKey(lk.Key.FormKey, cache),
                flags = (uint)lk.Flags,
            };
        }

        return new
        {
            form_id = ScriptExport.FormatFormId(r.FormKey),
            formkey = r.FormKey.ToString(),
            editor_id = r.EditorID ?? "",
            type = r.GetType().Name.Replace("BinaryOverlay", ""),
            persistent = ch.Persistent,
            source_cell_form_id = ScriptExport.FormatFormId(sourceCell.Cell.FormKey),
            source_cell_editor_id = sourceCell.EditorID ?? "",
            cell_grid = new[] { cellGrid.X, cellGrid.Y },
            dist_xy_m = Math.Round(distXyM, 2),
            dist_3d_m = Math.Round(dist3dM, 2),
            pos = new[] { pos.X, pos.Y, pos.Z },
            rot = rot is { } rv ? new[] { rv.X, rv.Y, rv.Z } : null,
            scale,
            record_flags = r.MajorRecordFlagsRaw,
            disabled = (r.MajorRecordFlagsRaw & 0x800) != 0,
            base_form_id = baseFk.IsNull ? null : ScriptExport.FormatFormId(baseFk),
            base_editor_id = baseEid,
            base_type = baseType,
            model,
            scripts = ScriptExport.ScriptsResolved(r, cache),
            base_scripts = baseScripts,
            linked_references = linked,
            enable_parent = enableParent,
            lock_data = lockData,
            teleport_destination = teleport,
        };
    }

    private static P3Float? Position(IPlacedGetter p) => p switch
    {
        IPlacedObjectGetter o => o.Position,
        IPlacedNpcGetter n => n.Position,
        IAPlacedTrapGetter t => t.Position,
        _ => null,
    };

    private static P3Float? Rotation(IPlacedGetter p) => p switch
    {
        IPlacedObjectGetter o => o.Rotation,
        IPlacedNpcGetter n => n.Rotation,
        IAPlacedTrapGetter t => t.Rotation,
        _ => null,
    };
}
