// A cell as the game sees it over a load order: the winning CELL record (the last plugin's copy) plus its children merged
// across every plugin that holds the cell. A DLC's override CELL carries only the references it overrides or adds; the
// master's other references still belong to the cell, so the children are merged by FormKey in load order: a later copy
// of a reference replaces the earlier one in place (its position in the list is the earlier copy's; its persistent or
// temporary membership is the later copy's), one flagged Deleted (record flag 0x20, IMajorRecordGetter.IsDeleted) removes
// it and adds nothing, one a later plugin holds in another cell (moved) is left out here. A single plugin merges to
// exactly its Temporary then Persistent lists, so an export of a cell no DLC touches does not change.
// Verified against Mutagen.Bethesda.Fallout4 0.55.0-alpha.67 (scratchpad probe-merge, 2026-10-21): a DLC overlay's
// Cells group holds the override CELL under the master's FormKey with only the DLC's children; a deleted reference reads
// back with MajorRecordFlagsRaw 0x20 and IsDeleted true and stays in the list; ILinkCache.TryResolve<ICellGetter> gives
// the DLC's copy and ResolveAllSimpleContexts the copies in priority order. The merge below walks the mods itself (the
// copies in load order) rather than the cache, so the whole-cell walk TeleportDependencies needs costs no cache index.
// A cell's name for lookup and output is the last copy's EditorID that is not null (Merged.EditorID), so an override
// written without EDID keeps the cell findable (Codex's review on #396: synthetic or third-party plugins; the official
// DLC overrides carry EDID).
using Mutagen.Bethesda.Fallout4;
using Mutagen.Bethesda.Plugins;

public static class CellMerge
{
    /// <summary>One copy of a cell: the index of the mod in the load order that holds it, the record, its worldspace (null for an interior).</summary>
    public sealed record Copy(int Mod, ICellGetter Cell, string? Worldspace);

    /// <summary>A merged child: the winning record, whether its winning copy stands in the cell's persistent list, the index of its mod.</summary>
    public sealed record Placed(IPlacedGetter Record, bool Persistent, int Source);

    /// <summary>EditorID: the cell's editor id as the last copy that carries one names it (an override may omit EDID:
    /// Mutagen writes none for a null EditorID; the record is still the same cell), so the cell stays findable by name.</summary>
    public sealed record Merged(ICellGetter Cell, string? Worldspace, IReadOnlyList<Placed> Children, string? EditorID)
    {
        public IEnumerable<IPlacedGetter> Records => Children.Select(c => c.Record);
    }

    /// <summary>The last non-null EditorID among a cell's copies; null when none names it.</summary>
    public static string? EditorIdOf(IReadOnlyList<Copy> copies)
    {
        for (var i = copies.Count - 1; i >= 0; i--)
            if (copies[i].Cell.EditorID != null) return copies[i].Cell.EditorID;
        return null;
    }

    /// <summary>Every cell of one mod: the interior group's (worldspace null), then each worldspace's top cell and sub cells.</summary>
    public static IEnumerable<(ICellGetter Cell, string? Worldspace)> Cells(IFallout4ModGetter mod, bool worldspaces)
    {
        foreach (var c in mod.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(sb => sb.Cells)) yield return (c, null);
        if (!worldspaces) yield break;
        foreach (var world in mod.Worldspaces)
        {
            if (world.TopCell != null) yield return (world.TopCell, world.FormKey.ToString());
            foreach (var c in world.SubCells.SelectMany(b => b.Items).SelectMany(b => b.Items))
                yield return (c, world.FormKey.ToString());
        }
    }

    /// <summary>{cell FormKey: its copies in load order}, keyed in the order the cells are first met.</summary>
    public static Dictionary<FormKey, List<Copy>> Copies(IReadOnlyList<IFallout4ModGetter> mods, bool worldspaces)
    {
        var copies = new Dictionary<FormKey, List<Copy>>();
        for (var i = 0; i < mods.Count; i++)
            foreach (var (cell, worldspace) in Cells(mods[i], worldspaces))
            {
                if (!copies.TryGetValue(cell.FormKey, out var list)) copies[cell.FormKey] = list = new List<Copy>();
                list.Add(new Copy(i, cell, worldspace));
            }
        // A cell whose winning copy carries the Deleted flag is gone from the game: no list, location or export sees it.
        foreach (var key in copies.Where(kv => kv.Value[^1].Cell.IsDeleted).Select(kv => kv.Key).ToList())
            copies.Remove(key);
        return copies;
    }

    /// <summary>The placed FormKeys each mod holds anywhere (interior or worldspace cell), by mod index. Index 0 is left
    /// empty: nothing loads before the first mod, so its keys never decide whether an earlier copy was moved.</summary>
    public static List<HashSet<FormKey>> PlacedKeys(IReadOnlyList<IFallout4ModGetter> mods)
    {
        var keys = new List<HashSet<FormKey>>();
        for (var i = 0; i < mods.Count; i++)
        {
            var set = new HashSet<FormKey>();
            if (i > 0)
                foreach (var (cell, _) in Cells(mods[i], true))
                    foreach (var r in cell.Temporary.Concat(cell.Persistent)) set.Add(r.FormKey);
            keys.Add(set);
        }
        return keys;
    }

    public static Merged Merge(IReadOnlyList<Copy> copies, IReadOnlyList<HashSet<FormKey>> placedKeys)
    {
        var order = new List<FormKey>();
        var by = new Dictionary<FormKey, Placed>();
        foreach (var copy in copies)
        {
            var own = copy.Cell.Temporary.Select(r => (Record: r, Persistent: false)).Concat(copy.Cell.Persistent.Select(r => (Record: r, Persistent: true)));
            foreach (var (record, persistent) in own)
            {
                if (record.IsDeleted)
                {
                    if (by.Remove(record.FormKey)) order.Remove(record.FormKey);
                    continue;
                }
                if (!by.ContainsKey(record.FormKey)) order.Add(record.FormKey);
                by[record.FormKey] = new Placed(record, persistent, copy.Mod);
            }
        }
        var children = new List<Placed>(order.Count);
        foreach (var key in order)
        {
            var placed = by[key];
            // a later plugin that holds the reference (in another cell, since a copy in this cell would have replaced
            // this one) moved it out, or deleted it there
            var moved = false;
            for (var j = placed.Source + 1; j < placedKeys.Count && !moved; j++) moved = placedKeys[j].Contains(key);
            if (!moved) children.Add(placed);
        }
        var winner = copies[copies.Count - 1];
        return new Merged(winner.Cell, winner.Worldspace, children, EditorIdOf(copies));
    }

    /// <summary>Every cell of the load order, merged; the winning record and worldspace are the last copy's.</summary>
    public static IEnumerable<Merged> All(IReadOnlyList<IFallout4ModGetter> mods, IReadOnlyList<HashSet<FormKey>> placedKeys, bool worldspaces) =>
        Copies(mods, worldspaces).Values.Select(c => Merge(c, placedKeys));
}
