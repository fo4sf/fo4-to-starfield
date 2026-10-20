using Mutagen.Bethesda.Fallout4;

/// <summary>Resolve destination locations from actual cell membership, not editor-ID guesses.</summary>
public static class TeleportDependencies
{
    public sealed record Location(string formkey, string? editor_id, string? worldspace);
    public sealed record Dependency(string source, string? door, Location? destination_cell,
        string? destination_base, string? transition_interior, Location? transition_cell);

    public static Dependency[] Build(IEnumerable<IPlacedObjectGetter> sources,
        IEnumerable<(ICellGetter Cell, string? Worldspace)> cells)
    {
        var teleports = sources.Where(r => r.TeleportDestination != null).ToArray();
        if (teleports.Length == 0) return Array.Empty<Dependency>();
        var wantedDoors = teleports.Select(r => r.TeleportDestination!.Door.FormKey.ToString()).ToHashSet();
        // Cells arrive winning record first (the plugin, then its masters last to first). A cell's name and place come
        // from its first, winning record even when that override carries no children, so a door inherited from the
        // master's copy still reports the cell under the name the game loads.
        var locations = new Dictionary<string, Location>();
        var doors = new Dictionary<string, (string Cell, string? Base)>();
        foreach (var (cell, worldspace) in cells)
        {
            var key = cell.FormKey.ToString();
            locations.TryAdd(key, new Location(key, cell.EditorID, worldspace));
            foreach (var r in cell.Temporary.Concat(cell.Persistent).OfType<IPlacedObjectGetter>())
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
