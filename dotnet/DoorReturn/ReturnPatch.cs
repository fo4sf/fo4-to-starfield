using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Starfield;
using Noggog;

public sealed record ReturnPlan(FormKey Interior, FormKey Exterior, P3Float Position, P3Float Rotation, uint Flags);

public static class ReturnPatch
{
    public static readonly ModKey PatchKey = ModKey.FromNameAndExtension("FO4DoorReturn.esm");
    static void Need(bool condition, string message)
    { if (!condition) throw new InvalidDataException(message); }
    static bool Finite(P3Float v) => float.IsFinite(v.X) && float.IsFinite(v.Y) && float.IsFinite(v.Z);

    public static StarfieldMod Build(IStarfieldModGetter sf, IStarfieldModGetter port, IStarfieldModGetter core, ReturnPlan plan)
    {
        Need(sf.ModKey == ModKey.FromNameAndExtension("Starfield.esm"), "expected Starfield.esm native master");
        Need(new[] { sf.ModKey, port.ModKey, core.ModKey, PatchKey }.Distinct().Count() == 4, "plugin identities must differ");
        Need(new[] { sf, port, core }.All(m => m.MasterStyle == MasterStyle.Full), "only full-size input plugins are supported");
        Need(port.ModHeader.MasterReferences.All(m => m.Master == sf.ModKey), "Port must depend only on Starfield (no Core/patch cycle)");
        Need(core.ModHeader.MasterReferences.All(m => m.Master == sf.ModKey || m.Master == port.ModKey)
            && core.ModHeader.MasterReferences.Any(m => m.Master == port.ModKey), "Core must explicitly depend on Port; unknown masters refused");
        Need(plan.Interior.ModKey == port.ModKey && plan.Exterior.ModKey == core.ModKey, "endpoint must belong to its owning plugin");
        Need(Finite(plan.Position) && Finite(plan.Rotation) && (plan.Flags & ~3u) == 0,
            "arrival must be finite and use supported absolute flags (relative placement refused)");

        var interiors = (from block in port.Cells.Records from sub in block.SubBlocks from cell in sub.Cells
                         from obj in cell.Persistent.OfType<IPlacedObjectGetter>() where obj.FormKey == plan.Interior
                         select (block, sub, cell, obj)).ToArray();
        Need(interiors.Length == 1, "interior endpoint must occur once in a persistent interior group");
        var inside = interiors[0];
        Need(inside.cell.FormKey.ModKey == port.ModKey && (inside.cell.Flags & Cell.Flag.IsInteriorCell) == Cell.Flag.IsInteriorCell, "Port-owned interior cell required");
        Need((inside.cell.MajorRecordFlagsRaw & 0x20) == 0, "interior parent is deleted");
        var exteriors = (from world in core.Worldspaces where world.TopCell != null
                         from obj in world.TopCell!.Persistent.OfType<IPlacedObjectGetter>() where obj.FormKey == plan.Exterior
                         select (world, obj)).ToArray();
        Need(exteriors.Length == 1, "exterior endpoint must occur once in a world persistent cell");
        var outside = exteriors[0];
        Need(outside.world.FormKey.ModKey == core.ModKey && outside.world.TopCell!.FormKey.ModKey == core.ModKey,
            "Core must own the exterior world and persistent cell");
        Need((outside.world.MajorRecordFlagsRaw & 0x20) == 0 && (outside.world.TopCell!.MajorRecordFlagsRaw & 0x20) == 0,
            "exterior parent is deleted");
        foreach (var endpoint in new[] { inside.obj, outside.obj })
        {
            Need((endpoint.MajorRecordFlagsRaw & 0x420) == 0x400, "endpoint must be persistent and not deleted");
            Need(Finite(endpoint.Position) && Finite(endpoint.Rotation) &&
                (!endpoint.Scale.HasValue || float.IsFinite(endpoint.Scale.Value) && endpoint.Scale.Value > 0), "invalid endpoint transform");
            // Resolve the winning record, including a deleted or different-type override.
            var winner = new[] { core, port, sf }.Select(m => m.EnumerateMajorRecords().FirstOrDefault(r => r.FormKey == endpoint.Base.FormKey))
                .FirstOrDefault(r => r != null);
            Need(winner is IDoorGetter door && (door.MajorRecordFlagsRaw & 0x20) == 0, "endpoint base is not an active resolved DOOR");
        }
        var outward = outside.obj.TeleportDestination;
        Need(outward != null && outward.Door.FormKey == plan.Interior, "Core outbound XTEL must target this Port endpoint");
        Need(Finite(outward!.Position) && Finite(outward.Rotation) && ((uint)outward.Flags & ~3u) == 0, "invalid Core outbound arrival");
        Need(outward.TransitionInterior.IsNull || outward.TransitionInterior.FormKey == inside.cell.FormKey, "wrong outbound transition cell");
        var old = inside.obj.TeleportDestination;
        Need(old == null || old.Door.FormKey == plan.Exterior && old.Position == plan.Position && old.Rotation == plan.Rotation
            && (uint)old.Flags == plan.Flags && old.TransitionInterior.IsNull, "existing return XTEL conflicts with requested connection");

        var mod = new StarfieldMod(PatchKey, StarfieldRelease.Starfield);
        var cellCopy = inside.cell.DeepCopy(new Cell.TranslationMask(defaultOn: true) {
            Persistent = false, Temporary = false,
            NavigationMeshes = new NavigationMesh.TranslationMask(defaultOn: false, onOverall: false) });
        cellCopy.Persistent.Clear(); cellCopy.Temporary.Clear(); cellCopy.NavigationMeshes.Clear();
        var refCopy = inside.obj.DeepCopy();
        refCopy.TeleportDestination = new TeleportDestination { Position = plan.Position, Rotation = plan.Rotation,
            Flags = (TeleportDestination.Flag)plan.Flags };
        refCopy.TeleportDestination.Door.SetTo(plan.Exterior);
        cellCopy.Persistent.Add(refCopy);
        var blockCopy = new CellBlock { BlockNumber = inside.block.BlockNumber, GroupType = inside.block.GroupType };
        var subCopy = new CellSubBlock { BlockNumber = inside.sub.BlockNumber, GroupType = inside.sub.GroupType };
        subCopy.Cells.Add(cellCopy); blockCopy.SubBlocks.Add(subCopy); mod.Cells.Records.Add(blockCopy);
        return mod;
    }
}
