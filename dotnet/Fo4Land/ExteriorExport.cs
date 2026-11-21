// Fo4Land export-exterior: Fallout 4 EXTERIOR references of a worldspace cell range as schema v2 placement JSON
// (docs/CELL-EXPORT.md), the format dotnet/Fo4Export writes for interiors and scripts/convert_batch.py --cell-json reads.
//
//   dotnet run --project dotnet/Fo4Land -- <Fallout4.esm> export-exterior <WorldEditorId> <xmin> <ymin> <xmax> <ymax> <out.json>
//
// Every reference keeps exactly the fields Fo4Export writes (ReferenceExport / KeywordExport / TeleportDependencies are
// compiled in from dotnet/Fo4Export unchanged), plus two exterior fields:
//   exterior_cell  [x, y]   the FO4 cell grid the reference belongs to
//   source_cell    FormKey  the CELL record that stores it (the worldspace's persistent cell for persistent references)
// Persistent references of exterior cells live in the worldspace's persistent cell in Fallout4.esm, not in their own
// cell: they are taken from there when their position lies in the range (cell = floor(position / 4096)), and from any
// persistent group of the exterior cells themselves. Placed hazards / projectiles (APlacedTrap types) have positions
// too and go to deferred_refs like every placement that is neither REFR nor ACHR; a persistent placement without a
// position is counted in exterior.persistent_unpositioned_by_type. Top level: "cell" is a name for the range, "formkey" the
// worldspace's FormKey (there is no single cell), "worldspace" and "exterior" describe the range and its cells.
// Positions stay FO4 units, rotations radians; translation happens in the plugin writer. Output stays outside the repo.
using System.Text.Json;
using System.Text.Json.Nodes;
using Mutagen.Bethesda;
using Mutagen.Bethesda.Fallout4;
using Mutagen.Bethesda.Plugins.Cache;
using Mutagen.Bethesda.Plugins.Records;

public static class ExteriorExport
{
    public const double CellUnits = 4096.0;

    /// <summary>FO4 exterior cell grid of a position in game units (floor, so -0.5 is cell -1).</summary>
    public static (int X, int Y) CellOf(double x, double y) => ((int)Math.Floor(x / CellUnits), (int)Math.Floor(y / CellUnits));

    public static int Run(string[] args, IReadOnlyList<string>? masterPaths = null)
    {
        masterPaths ??= Array.Empty<string>();
        if (args.Length != 8)
        {
            Console.Error.WriteLine("usage: Fo4Land <Fallout4.esm> [--master <master.esm>]... export-exterior <WorldEditorId> <xmin> <ymin> <xmax> <ymax> <out.json>");
            return 2;
        }
        int xmin = int.Parse(args[3]), ymin = int.Parse(args[4]), xmax = int.Parse(args[5]), ymax = int.Parse(args[6]);
        var outPath = args[7];
        try { Fo4LoadOrder.RefuseUnsafeOutput(outPath, masterPaths.Append(args[0])); }
        catch (InvalidOperationException ex) { Console.Error.WriteLine(ex.Message); return 2; }

        bool InRange((int X, int Y) c) => c.X >= xmin && c.X <= xmax && c.Y >= ymin && c.Y <= ymax;
        using var lo = Fo4LoadOrder.Open(args[0], masterPaths);
        var cache = lo.Cache;

        // (placed, persistent, exterior cell, storing cell)
        var placements = new List<(IPlacedGetter Placed, bool Persistent, (int X, int Y) Cell, ICellGetter Source)>();
        var cellInfo = new List<object>();
        int fromTop = 0;
        var unpositioned = new Dictionary<string, int>();
        string worldEdid;
        string worldFormKey;
        string? worldTopCellFormKey;

        if (masterPaths.Count == 0)
        {
            var mod = lo.ActiveMod;
            var world = mod.Worldspaces.FirstOrDefault(w => w.EditorID == args[2]);
            if (world is null)
            {
                Console.Error.WriteLine($"worldspace {args[2]} not found");
                return 1;
            }
            worldEdid = world.EditorID!;
            worldFormKey = world.FormKey.ToString();
            worldTopCellFormKey = world.TopCell?.FormKey.ToString();
            foreach (var cell in world.SubCells.SelectMany(b => b.Items).SelectMany(sb => sb.Items))
            {
                if (cell.Grid is not { } grid) continue;
                var xy = (grid.Point.X, grid.Point.Y);
                if (!InRange(xy)) continue;
                foreach (var p in cell.Temporary) placements.Add((p, false, xy, cell));
                foreach (var p in cell.Persistent) placements.Add((p, true, xy, cell));
                cellInfo.Add(new { x = xy.Item1, y = xy.Item2, formkey = cell.FormKey.ToString(), editor_id = cell.EditorID,
                                   temporary = cell.Temporary.Count, persistent_in_cell = cell.Persistent.Count });
            }
            if (world.TopCell is { } top)
            {
                foreach (var p in top.Persistent)
                {
                    var pos = Position(p);
                    if (pos is null)
                    {
                        var t = p.GetType().Name.Replace("BinaryOverlay", "");
                        unpositioned[t] = unpositioned.GetValueOrDefault(t) + 1;
                        continue;
                    }
                    var xy = CellOf(pos.Value.X, pos.Value.Y);
                    if (!InRange(xy)) continue;
                    placements.Add((p, true, xy, top));
                    fromTop++;
                }
            }
        }
        else
        {
            var found = lo.FindWorld(args[2]);
            if (found is null)
            {
                Console.Error.WriteLine($"worldspace {args[2]} not found");
                return 1;
            }
            var (worldKey, winner, resolvedEdid, worldCopies) = found.Value;
            worldEdid = resolvedEdid;
            worldFormKey = worldKey.ToString();
            var topKeys = worldCopies.Where(w => w.TopCell != null).Select(w => w.TopCell!.FormKey).ToHashSet();
            worldTopCellFormKey = winner.TopCell?.FormKey.ToString() ?? worldCopies.Select(w => w.TopCell?.FormKey.ToString()).LastOrDefault(s => s != null);

            var placedKeys = CellMerge.PlacedKeys(lo.Mods);
            var allCopies = CellMerge.Copies(lo.Mods, worldspaces: true);
            foreach (var (ck, copies) in allCopies)
            {
                if (copies[^1].Worldspace != worldFormKey) continue;
                if (topKeys.Contains(ck)) continue;
                var grid = copies.Select(c => c.Cell.Grid).LastOrDefault(g => g != null);
                if (grid is null) continue;
                var xy = (grid.Point.X, grid.Point.Y);
                if (!InRange(xy)) continue;
                var merged = CellMerge.Merge(copies, placedKeys);
                int tempCnt = 0, persCnt = 0;
                foreach (var ch in merged.Children)
                {
                    placements.Add((ch.Record, ch.Persistent, xy, merged.Cell));
                    if (ch.Persistent) persCnt++; else tempCnt++;
                }
                cellInfo.Add(new { x = xy.Item1, y = xy.Item2, formkey = merged.Cell.FormKey.ToString(), editor_id = merged.EditorID,
                                   temporary = tempCnt, persistent_in_cell = persCnt });
            }
            foreach (var tk in topKeys)
            {
                if (!allCopies.TryGetValue(tk, out var tcopies)) continue;
                var mergedTop = CellMerge.Merge(tcopies, placedKeys);
                foreach (var ch in mergedTop.Children)
                {
                    if (!ch.Persistent) continue;
                    var pos = Position(ch.Record);
                    if (pos is null)
                    {
                        var t = ch.Record.GetType().Name.Replace("BinaryOverlay", "");
                        unpositioned[t] = unpositioned.GetValueOrDefault(t) + 1;
                        continue;
                    }
                    var xy = CellOf(pos.Value.X, pos.Value.Y);
                    if (!InRange(xy)) continue;
                    placements.Add((ch.Record, true, xy, mergedTop.Cell));
                    fromTop++;
                }
            }
        }

        var refs = new List<JsonNode>();
        var deferred = new List<JsonNode>();
        var keywords = new Dictionary<string, object>();
        var byType = new Dictionary<string, int>();
        foreach (var (placed, persistent, xy, source) in placements)
        {
            IEnumerable<ILinkedReferencesGetter> linked = placed switch
            {
                IPlacedObjectGetter obj => obj.LinkedReferences,
                IPlacedNpcGetter actor => actor.LinkedReferences,
                _ => Array.Empty<ILinkedReferencesGetter>(),
            };
            foreach (var link in linked)
                if (link.KeywordOrReference.TryResolve(cache, out var union) && union is IKeywordGetter keyword)
                    keywords.TryAdd(keyword.FormKey.ToString(), KeywordExport.Build(keyword));
            JsonObject node;
            if (placed is IPlacedNpcGetter npc)
            {
                node = Tag(ReferenceExport.BuildActor(npc, persistent), xy, source);
                deferred.Add(node);
                continue;
            }
            if (placed is not IPlacedObjectGetter r)
            {
                node = Tag(new { formkey = placed.FormKey.ToString(), type = placed.GetType().Name.Replace("BinaryOverlay", ""),
                                 reason = "placement_type_not_implemented" }, xy, source);
                deferred.Add(node);
                continue;
            }
            string type = "?", baseEid = "", model = "";
            if (r.Base.TryResolve(cache, out var baseRec))
            {
                type = baseRec.GetType().Name.Replace("BinaryOverlay", "");
                baseEid = baseRec.EditorID ?? "";
                if (baseRec is IModeledGetter m && m.Model?.File != null) model = m.Model.File.ToString();
            }
            byType[type] = byType.GetValueOrDefault(type) + 1;
            refs.Add(Tag(ReferenceExport.Build(r, type, baseEid, model, persistent), xy, source));
        }

        IEnumerable<(ICellGetter Cell, string? Worldspace)> AllCells()
        {
            if (masterPaths.Count == 0)
            {
                var mod = lo.ActiveMod;
                foreach (var c in mod.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(sb => sb.Cells)) yield return (c, null);
                foreach (var w in mod.Worldspaces)
                {
                    if (w.TopCell != null) yield return (w.TopCell, w.FormKey.ToString());
                    foreach (var c in w.SubCells.SelectMany(b => b.Items).SelectMany(b => b.Items))
                        yield return (c, w.FormKey.ToString());
                }
            }
            else
            {
                var pks = CellMerge.PlacedKeys(lo.Mods);
                foreach (var m in CellMerge.All(lo.Mods, pks, worldspaces: true))
                    yield return (m.Cell, m.Worldspace);
            }
        }
        var dependencies = TeleportDependencies.Build(placements.Select(p => p.Placed).OfType<IPlacedObjectGetter>(), AllCells());

        var name = $"{worldEdid}_x{xmin}_{xmax}_y{ymin}_{ymax}";
        var doc = new
        {
            schema_version = 2,
            cell = name,
            formkey = worldFormKey,
            worldspace = new { editor_id = worldEdid, formkey = worldFormKey },
            exterior = new { xmin, ymin, xmax, ymax, cell_units = CellUnits, cells = cellInfo,
                             persistent_from_world_cell = fromTop,
                             persistent_unpositioned_by_type = unpositioned,
                             world_persistent_cell = worldTopCellFormKey },
            refs,
            deferred_refs = deferred,
            referenced_keywords = keywords.Values,
            teleport_dependencies = dependencies,
        };
        File.WriteAllText(outPath, JsonSerializer.Serialize(doc, new JsonSerializerOptions { WriteIndented = true }));
        Console.WriteLine($"{name}: {cellInfo.Count} cells, {refs.Count} references ({fromTop} persistent from the world's persistent cell), " +
                          $"{deferred.Count} deferred -> {outPath}");
        foreach (var kv in byType.OrderByDescending(k => k.Value)) Console.WriteLine($"  {kv.Key}: {kv.Value}");
        foreach (var kv in unpositioned) Console.WriteLine($"  persistent without a position (not range-tested): {kv.Key}: {kv.Value}");
        return 0;
    }

    static Noggog.P3Float? Position(IPlacedGetter p) => p switch
    {
        IPlacedObjectGetter o => o.Position,
        IPlacedNpcGetter n => n.Position,
        IAPlacedTrapGetter t => t.Position,     // hazards, missiles, arrows, beams, cones, flames, barriers, traps
        _ => null,
    };

    static JsonObject Tag(object value, (int X, int Y) xy, ICellGetter source)
    {
        var node = JsonSerializer.SerializeToNode(value)!.AsObject();
        node["exterior_cell"] = new JsonArray(xy.X, xy.Y);
        node["source_cell"] = source.FormKey.ToString();
        return node;
    }
}
