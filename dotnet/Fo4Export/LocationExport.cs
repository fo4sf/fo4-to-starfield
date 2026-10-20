// Cell-level location data (schema 3): the cell's own DATA flags and FULL name, its XLCN location with the parent chain
// and keywords, and its XEZN encounter zone (the only place Fallout 4 keeps min/max level and reset flags). The plugin
// writer folds the zone's leveling into the one Starfield LCTN it creates per Fallout 4 location (interior-batches.md,
// "Locations"). Links whose record is not in the cache (a missing master) are kept as {formkey, unresolved: true}, the
// same rule TeleportDependencies follows, rather than dropped.
// cell_data also carries the cell's acoustic space (XCAS), music type (XCMO), image space (XCIM), god rays (XGDR),
// water (XCWT, XCLW) and ownership (XOWN, XRNK), the inputs for the sound / image-space family mapping
// (research interiors.md section 3, L14 and L15) and for the location's owner. Additive keys within cell_data: the
// schema version stays 3 and PluginSpike's Locations.cs reads only "name" from it.
// Property names verified by reflection against Mutagen.Bethesda.Fallout4 0.55.0-alpha.67 (ICellGetter.AcousticSpace,
// Music, ImageSpace, GodRays, Water: IFormLinkNullableGetter<...>; WaterHeight: float?; Ownership: IOwnershipGetter?
// with Owner: IFormLinkGetter<IOwnerGetter>, NoCrime, Unknown; FactionRank: int?).
using Mutagen.Bethesda;
using Mutagen.Bethesda.Fallout4;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Cache;
using Mutagen.Bethesda.Plugins.Records;

public static class LocationExport
{
    // a nullable link as null (subrecord absent), {formkey, editor_id} (resolved) or {formkey, unresolved: true}
    static object? Link<T>(IFormLinkNullableGetter<T> link, ILinkCache cache) where T : class, IMajorRecordGetter
    {
        if (link.IsNull) return null;
        if (!link.TryResolve(cache, out var record)) return new { formkey = link.FormKey.ToString(), unresolved = true };
        return new { formkey = record.FormKey.ToString(), editor_id = record.EditorID };
    }

    // XOWN/XRNK: the owner is a FACT or an NPC_ (both implement IOwnerGetter); owner_type says which once resolved.
    // XRNK (FactionRank) is a separate subrecord on the cell, kept beside the owner because it only means something
    // with a faction owner. A cell with XRNK but no XOWN is reported with owner null rather than dropped.
    // The shape differs from the per-reference ownership in ReferenceExport ({owner, no_crime, unknown} with
    // faction_rank as a sibling): the cell adds the resolved owner's type and editor id and folds XRNK in, but keeps
    // XOWN's Unknown int under the same "unknown" key so nothing the per-ref export preserves is lost here.
    static object? Ownership(ICellGetter cell, ILinkCache cache)
    {
        if (cell.Ownership == null && cell.FactionRank == null) return null;
        string? ownerKey = null, ownerType = null, ownerEditorId = null;
        bool? unresolved = null;
        if (cell.Ownership is { } own && !own.Owner.IsNull)
        {
            ownerKey = own.Owner.FormKey.ToString();
            if (own.Owner.TryResolve(cache, out var owner))
            {
                ownerEditorId = owner.EditorID;
                ownerType = owner switch { IFactionGetter => "faction", INpcGetter => "npc", _ => "other" };
            }
            else unresolved = true;
        }
        return new
        {
            owner = ownerKey, owner_type = ownerType, owner_editor_id = ownerEditorId, unresolved,
            faction_rank = cell.FactionRank, no_crime = cell.Ownership?.NoCrime, unknown = cell.Ownership?.Unknown,
        };
    }

    public static object CellData(ICellGetter cell, ILinkCache cache) => new
    {
        flags = (int)cell.Flags, name = cell.Name?.String,
        acoustic_space = Link(cell.AcousticSpace, cache), music = Link(cell.Music, cache),
        image_space = Link(cell.ImageSpace, cache), god_rays = Link(cell.GodRays, cache),
        water = Link(cell.Water, cache),
        // XCLW as read; System.Text.Json throws on NaN or infinity (verified: the NanWater test cell fails the whole
        // serialization without this guard), so a non-finite height is reported as null
        // (hypothesis: FO4 uses a sentinel float for "default height", not verified here; the raw value is kept as is)
        water_height = cell.WaterHeight is { } h && float.IsFinite(h) ? h : (float?)null,
        ownership = Ownership(cell, cache),
    };

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
        cell_data = CellData(cell, cache), location = Location(cell.Location, cache), encounter_zone = EncounterZone(cell.EncounterZone, cache),
    };
}
