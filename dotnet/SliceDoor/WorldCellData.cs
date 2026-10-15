// OFST/CLSZ are file-local exterior-cell lookup tables, NOT an overlay merge offset.
// See docs/slice/door-frames.md. This experiment supports only a slice with no exterior
// cells: every lookup entry is absent (zero). Never copy offsets from another plugin.
using System.Text.Json;
using Mutagen.Bethesda.Starfield;

public static class WorldCellData
{
    public static bool Requested(JsonElement parameters)
    {
        if (!parameters.TryGetProperty("world_cell_data", out var data)) return false;
        if (data.GetProperty("mode").GetString() != "empty")
            throw new InvalidDataException("world_cell_data supports only mode empty");
        if (parameters.TryGetProperty("probes", out var probes) && probes.GetArrayLength() != 0)
            throw new InvalidDataException("empty world_cell_data requires no probes/exterior cells");
        return true;
    }

    public static int ByteLength(IWorldspaceGetter world)
    {
        // Mutagen's custom NAM0/NAM9 reader divides raw metres by 4096. Starfield
        // exterior cells are 100m. Native LC172World: -200..300m -> 6x6 u32 entries.
        static long Coordinate(float value)
        {
            double cells = (double)value * 4096 / 100;
            if (!double.IsFinite(cells) || Math.Abs(cells - Math.Round(cells)) > 1e-5 || Math.Abs(cells) > 1_000_000)
                throw new InvalidDataException("world bounds must be finite, aligned 100m cell coordinates");
            return (long)Math.Round(cells);
        }
        long columns = Coordinate(world.ObjectBoundsMax.X) - Coordinate(world.ObjectBoundsMin.X) + 1;
        long rows = Coordinate(world.ObjectBoundsMax.Y) - Coordinate(world.ObjectBoundsMin.Y) + 1;
        if (columns <= 0 || rows <= 0 || columns * rows > 1_048_576)
            throw new InvalidDataException("empty world_cell_data bounds are reversed or exceed the bounded experiment");
        return checked((int)(4 * columns * rows));
    }

    public static void SetEmpty(Worldspace world)
    {
        if (world.SubCells.Count != 0)
            throw new InvalidDataException("empty world_cell_data cannot describe exterior cell groups");
        int length = ByteLength(world);
        world.OffsetData = new byte[length];
        world.CellSizeData = new byte[length];
    }

    public static bool MatchesEmpty(IWorldspaceGetter world)
    {
        int length = ByteLength(world);
        return world.SubCells.Count == 0
            && world.OffsetData is { } offsets && offsets.Length == length && offsets.All(b => b == 0)
            && world.CellSizeData is { } sizes && sizes.Length == length && sizes.All(b => b == 0);
    }
}
