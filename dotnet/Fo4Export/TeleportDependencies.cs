using Mutagen.Bethesda.Fallout4;

/// <summary>Resolve destination locations from actual cell membership, not editor-ID guesses.</summary>
public static class TeleportDependencies
{
    public sealed record Location(string formkey, string? editor_id, string? worldspace);
    public sealed record Dependency(string source, string? door, Location? destination_cell,
        string? destination_base, string? transition_interior, Location? transition_cell);

    /// <summary>Cells as single records, winning record first (the plugin, then its masters last to first): a cell's
    /// name and place come from its first record even when that override carries no children, so a door inherited
    /// from the master's copy still reports the cell under the name the game loads. Fo4Land (one plugin) and the
    /// synthetic tests use this form; the exporter passes merged cells (below).</summary>
    public static Dependency[] Build(IEnumerable<IPlacedObjectGetter> sources,
        IEnumerable<(ICellGetter Cell, string? Worldspace)> cells) =>
        Build(sources, cells.Select(c => new CellMerge.Merged(c.Cell, c.Worldspace,
            c.Cell.Temporary.Select(r => new CellMerge.Placed(r, false, 0)).Concat(c.Cell.Persistent.Select(r => new CellMerge.Placed(r, true, 0))).ToList(), c.Cell.EditorID)));

    /// <summary>Cells as the game sees them (CellMerge: the winning record, the children merged over the load order,
    /// deleted ones gone), so a door a DLC deletes resolves no destination and one it adds does.</summary>
    public static Dependency[] Build(IEnumerable<IPlacedObjectGetter> sources, IEnumerable<CellMerge.Merged> cells)
    {
        var teleports = sources.Where(r => r.TeleportDestination != null).ToArray();
        if (teleports.Length == 0) return Array.Empty<Dependency>();
        var wantedDoors = teleports.Select(r => r.TeleportDestination!.Door.FormKey.ToString()).ToHashSet();
        var locations = new Dictionary<string, Location>();
        var doors = new Dictionary<string, (string Cell, string? Base)>();
        foreach (var cell in cells)
        {
            var key = cell.Cell.FormKey.ToString();
            locations.TryAdd(key, new Location(key, cell.EditorID, cell.Worldspace));
            foreach (var r in cell.Records.OfType<IPlacedObjectGetter>())
                if (wantedDoors.Contains(r.FormKey.ToString()))
                    doors.TryAdd(r.FormKey.ToString(), (key, r.Base.IsNull ? null : r.Base.FormKey.ToString()));
        }
        return teleports.Select(r =>
        {
            var t = r.TeleportDestination!;
            var door = t.Door.IsNull ? null : t.Door.FormKey.ToString();
            var transition = t.TransitionInterior.IsNull ? null : t.TransitionInterior.FormKey.ToString();
            var destination = door != null && doors.TryGetValue(door, out var found) ? found : default;
            return new Dependency(r.FormKey.ToString(), door,
                destination.Cell != null ? locations[destination.Cell] : null, destination.Base,
                transition, transition != null && locations.TryGetValue(transition, out var c) ? c : null);
        }).ToArray();
    }
}
