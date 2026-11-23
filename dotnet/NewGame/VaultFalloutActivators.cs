// VaultFalloutActivators: Kept Fallout-look Vault 111 activators for A1(c) (FO4SF_PipboyCorpsePickup 0x80E and
// FO4SF_GearDoorConsole 0x818). Replaces Round 8 V3's temporary Starfield Deimos WallTech08.nif (0x143492) template
// with staged Fallout-only NIFs (v111_pipboy_pickup.nif and v111_geardoor_console.nif) that carry 0 Starfield
// geometry/materials and a single root-node layer-1 (COL_STATIC) watertight convex Havok body.
using System.Drawing;
using Mutagen.Bethesda.Plugins.Assets;
using Mutagen.Bethesda.Starfield;
using Noggog;
using SF = Mutagen.Bethesda.Starfield;

static class VaultFalloutActivators
{
    public const string PipboyPickupModel = @"fo4sf\newgame\v111_pipboy_pickup.nif";
    public const string GearDoorConsoleModel = @"fo4sf\newgame\v111_geardoor_console.nif";

    public const string StagedPipboyRelPath = "Data/meshes/fo4sf/newgame/v111_pipboy_pickup.nif";
    public const string StagedConsoleRelPath = "Data/meshes/fo4sf/newgame/v111_geardoor_console.nif";

    // Forbidden Starfield / legacy models that must never appear on 0x80E or 0x818 in kept builds.
    public const string ForbiddenWallTechModel = @"Ships\Interior\Deimos\WallTech08.nif";
    public const string ForbiddenPedestalModel = @"SetDressing\NativeConsole.nif";
    public const string ForbiddenPortStaticModel = @"FO4Port\SetDressing\PipboyGroundTake01.nif";

    public const ushort FullCircleActivationAngle = 360;

    // Exact union bounds (metres) of re-centered Fallout 4 BSGeometry shapes + root layer-1 convex collision body:
    //   Pip-Boy pickup (at PipboyWorldCenter): visual [-0.1765..+0.0239, -0.1177..+0.0779, -0.1529..-0.0006],
    //                                          layer-1 hull [-0.210..+0.210, -0.150..+0.110, -0.155..+0.045] (Z_world up to 0.8209 m > 0.7722 m).
    //   Gear-door console (at ConsoleWorldPos): visual [-0.5379..+0.5379, -0.2194..+0.2194, -0.2385..+0.0693],
    //                                           layer-1 hull [-0.550..+0.550, -0.235..+0.235, -0.065..+0.095] (+2.61 cm proud of 0.1539 m lid).
    public static readonly P3Float PipboyBoundsMin = new(-0.210f, -0.150f, -0.155f);
    public static readonly P3Float PipboyBoundsMax = new(0.210f, 0.110f, 0.045f);
    public static readonly P3Float ConsoleBoundsMin = new(-0.550f, -0.235f, -0.240f);
    public static readonly P3Float ConsoleBoundsMax = new(0.550f, 0.235f, 0.095f);

    public static string NormalizeModelPath(string? raw) =>
        (raw ?? string.Empty).Trim().Replace('/', '\\').TrimStart('\\');

    public static bool ModelPathEquals(string? actual, string expected) =>
        string.Equals(NormalizeModelPath(actual), NormalizeModelPath(expected), StringComparison.OrdinalIgnoreCase);

    public static bool IsStarfieldMeshLeak(string? modelPath)
    {
        var norm = NormalizeModelPath(modelPath);
        return norm.Contains("WallTech", StringComparison.OrdinalIgnoreCase) ||
               norm.Contains("Deimos", StringComparison.OrdinalIgnoreCase) ||
               norm.StartsWith(@"Ships\", StringComparison.OrdinalIgnoreCase) ||
               ModelPathEquals(norm, ForbiddenPedestalModel) ||
               ModelPathEquals(norm, ForbiddenPortStaticModel);
    }

    public static void ConfigurePipboyActivator(SF.Activator acti)
    {
        acti.MarkerColor = Color.FromArgb(0, 0xCC, 0x4C, 0x33);
        acti.Flags = (SF.Activator.Flag)0;
        acti.ActivationAngle = FullCircleActivationAngle;
        acti.InvertFacing = false;
        acti.VirtualMachineAdapter = null;
        acti.Keywords = null;
        acti.Components.Clear();
        acti.ObjectBounds = new SF.ObjectBounds
        {
            First = PipboyBoundsMin,
            Second = PipboyBoundsMax,
        };
        acti.Model = new SF.Model
        {
            File = PipboyPickupModel,
        };
    }

    public static void ConfigureGearConsoleActivator(SF.Activator acti)
    {
        acti.MarkerColor = Color.FromArgb(0, 0xCC, 0x4C, 0x33);
        acti.Flags = (SF.Activator.Flag)0;
        acti.ActivationAngle = FullCircleActivationAngle;
        acti.InvertFacing = false;
        acti.VirtualMachineAdapter = null;
        acti.Keywords = null;
        acti.Components.Clear();
        acti.ObjectBounds = new SF.ObjectBounds
        {
            First = ConsoleBoundsMin,
            Second = ConsoleBoundsMax,
        };
        acti.Model = new SF.Model
        {
            File = GearDoorConsoleModel,
        };
    }

    private static bool BoundsMatch(SF.IObjectBoundsGetter? b, P3Float min, P3Float max) =>
        b is not null &&
        MathF.Abs(b.First.X - min.X) <= 1e-4f &&
        MathF.Abs(b.First.Y - min.Y) <= 1e-4f &&
        MathF.Abs(b.First.Z - min.Z) <= 1e-4f &&
        MathF.Abs(b.Second.X - max.X) <= 1e-4f &&
        MathF.Abs(b.Second.Y - max.Y) <= 1e-4f &&
        MathF.Abs(b.Second.Z - max.Z) <= 1e-4f;

    public static bool ValidateActivators(
        SF.IActivatorGetter? pipboyActi,
        SF.IActivatorGetter? gearConsoleActi,
        string expectedPipboyEdid,
        string expectedConsoleEdid)
    {
        if (pipboyActi is null || gearConsoleActi is null) return false;
        string? pbModel = pipboyActi.Model?.File?.GivenPath;
        string? conModel = gearConsoleActi.Model?.File?.GivenPath;
        if (IsStarfieldMeshLeak(pbModel) || IsStarfieldMeshLeak(conModel)) return false;

        bool pbOk =
            pipboyActi.EditorID == expectedPipboyEdid &&
            pipboyActi.Name?.String == "Pip-Boy 3000" &&
            pipboyActi.ActivateTextOverride?.String == "Take" &&
            pipboyActi.ActivationAngle == FullCircleActivationAngle &&
            !pipboyActi.InvertFacing &&
            pipboyActi.Flags == 0 &&
            pipboyActi.VirtualMachineAdapter is null &&
            (pipboyActi.Keywords?.Count ?? 0) == 0 &&
            pipboyActi.Components.Count == 0 &&
            ModelPathEquals(pbModel, PipboyPickupModel) &&
            BoundsMatch(pipboyActi.ObjectBounds, PipboyBoundsMin, PipboyBoundsMax);

        bool conOk =
            gearConsoleActi.EditorID == expectedConsoleEdid &&
            gearConsoleActi.Name?.String == "Vault Door Controls" &&
            gearConsoleActi.ActivateTextOverride?.String == "Activate" &&
            gearConsoleActi.ActivationAngle == FullCircleActivationAngle &&
            !gearConsoleActi.InvertFacing &&
            gearConsoleActi.Flags == 0 &&
            gearConsoleActi.VirtualMachineAdapter is null &&
            (gearConsoleActi.Keywords?.Count ?? 0) == 0 &&
            gearConsoleActi.Components.Count == 0 &&
            ModelPathEquals(conModel, GearDoorConsoleModel) &&
            BoundsMatch(gearConsoleActi.ObjectBounds, ConsoleBoundsMin, ConsoleBoundsMax);

        return pbOk && conOk;
    }
}
