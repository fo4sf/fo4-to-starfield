// Cell-level location data (schema 3): the cell's own DATA flags and FULL name, its XLCN location with the parent chain
// and keywords, and its XEZN encounter zone (the only place Fallout 4 keeps min/max level and reset flags). The plugin
// writer folds the zone's leveling into the one Starfield LCTN it creates per Fallout 4 location (interior-batches.md,
// "Locations"). Links whose record is not in the cache (a missing master) are kept as {formkey, unresolved: true}, the
// same rule TeleportDependencies follows, rather than dropped.
using Mutagen.Bethesda;
using Mutagen.Bethesda.Fallout4;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Cache;

public static class LocationExport
{
    public static object CellData(ICellGetter cell) => new { flags = (int)cell.Flags, name = cell.Name?.String };

    public static object? Location(IFormLinkNullableGetter<ILocationGetter> link, ILinkCache cache)
    {
        if (link.IsNull) return null;
        if (!link.TryResolve(cache, out var loc)) return new { formkey = link.FormKey.ToString(), unresolved = true };
        // parent chain up to the root (e.g. ConcordLocation -> CommonwealthLocation), cycle-guarded; the core derives the
        // region from the root, the writer replicates none of the intermediates
        var chain = new List<object>();
        var seen = new HashSet<FormKey> { loc.FormKey };
        var cur = loc.ParentLocation;
        while (!cur.IsNull && seen.Add(cur.FormKey))
        {
            if (!cur.TryResolve(cache, out var parent)) { chain.Add(new { formkey = cur.FormKey.ToString(), unresolved = true }); break; }
            chain.Add(new { formkey = parent.FormKey.ToString(), editor_id = parent.EditorID, name = parent.Name?.String });
            cur = parent.ParentLocation;
        }
        // Keywords (KWDA) is nullable on the Fallout 4 LCTN; an absent list is an empty one
        var keywords = (loc.Keywords ?? Array.Empty<IFormLinkGetter<IKeywordGetter>>())
            .Select(k => new { formkey = k.FormKey.ToString(), editor_id = k.TryResolve(cache, out var kw) ? kw.EditorID : null })
            .ToArray();
        return new
        {
            formkey = loc.FormKey.ToString(), editor_id = loc.EditorID, name = loc.Name?.String,
            parent = loc.ParentLocation.IsNull ? null : loc.ParentLocation.FormKey.ToString(),
            parent_chain = chain, keywords,
        };
    }

    public static object? EncounterZone(IFormLinkNullableGetter<IEncounterZoneGetter> link, ILinkCache cache)
    {
        if (link.IsNull) return null;
        if (!link.TryResolve(cache, out var zone)) return new { formkey = link.FormKey.ToString(), unresolved = true };
        return new
        {
            formkey = zone.FormKey.ToString(), editor_id = zone.EditorID,
            min_level = (int)zone.MinLevel, max_level = (int)zone.MaxLevel, rank = (int)zone.Rank, flags = (int)zone.Flags,
            owner = zone.Owner.IsNull ? null : zone.Owner.FormKey.ToString(),
            location = zone.Location.IsNull ? null : zone.Location.FormKey.ToString(),
        };
    }

    // the three keys of one cell, as they appear in both the cell JSON and the locations sidecar
    public static object Build(ICellGetter cell, ILinkCache cache) => new
    {
        cell_data = CellData(cell), location = Location(cell.Location, cache), encounter_zone = EncounterZone(cell.EncounterZone, cache),
    };
}
