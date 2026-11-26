// SurfaceLiftCog: overrides FO4TerrainCore.esm:0x0A2D4B (FO4Core_acti_19d22f_fallout4, "Vault 111 Elevator") in
// FO4SFExitLift.esm with the converted animated model, rig, clips, ActivatorStateGraph01, PNAM/FNAM/JNAM, and OBND
// with ZERO WRLD or CELL overrides so #858 worldspace patches remain conflict-free.
using System.Globalization;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;

public static class SurfaceLiftCog
{
    public const uint CoreSurfaceBaseId = 0x0A2D4B;
    public const string CoreSurfaceBaseEdid = "FO4Core_acti_19d22f_fallout4";
    public const string SurfaceCogName = "Vault 111 Elevator";
    public const string GraphAnam = "AnimTextData\\Tables\\Graphs\\ActivatorStateGraph01.agx";
    public static readonly ModKey CoreEsm = ModKey.FromFileName("FO4TerrainCore.esm");

    public static FormKey SurfaceCogKey(uint baseId = CoreSurfaceBaseId) => new(CoreEsm, baseId);

    /// <summary>Parses "minX,minY,minZ,maxX,maxY,maxZ" into finite <see cref="P3Float"/> OBND bounds.</summary>
    public static (P3Float Min, P3Float Max) ParseBounds(string spec)
    {
        var parts = (spec ?? "").Split(',', StringSplitOptions.TrimEntries);
        if (parts.Length != 6)
            throw new ArgumentException($"surface bounds must have 6 comma-separated floats, got '{spec}'", nameof(spec));
        var v = parts.Select(s => float.Parse(s, CultureInfo.InvariantCulture)).ToArray();
        if (v.Any(x => !float.IsFinite(x)))
            throw new ArgumentException($"surface bounds contain non-finite value: '{spec}'", nameof(spec));
        if (v[0] > v[3] || v[1] > v[4] || v[2] > v[5])
            throw new ArgumentException($"surface bounds min exceeds max: '{spec}'", nameof(spec));
        return (new P3Float(v[0], v[1], v[2]), new P3Float(v[3], v[4], v[5]));
    }

    private static bool BoundsMatch(IObjectBoundsGetter? b, P3Float min, P3Float max) =>
        b is not null &&
        MathF.Abs(b.First.X - min.X) <= 1e-4f &&
        MathF.Abs(b.First.Y - min.Y) <= 1e-4f &&
        MathF.Abs(b.First.Z - min.Z) <= 1e-4f &&
        MathF.Abs(b.Second.X - max.X) <= 1e-4f &&
        MathF.Abs(b.Second.Y - max.Y) <= 1e-4f &&
        MathF.Abs(b.Second.Z - max.Z) <= 1e-4f;

    /// <summary>
    /// Adds an override of FO4TerrainCore.esm ACTI <paramref name="coreBaseId"/> (default 0x0A2D4B) to
    /// <paramref name="mod"/> using the converted animated model/rig/clips, copying PNAM/FNAM/JNAM from
    /// <paramref name="interiorOverride"/> and setting OBND from manifest bounds.
    /// Enforces zero WRLD and CELL records on the plugin.
    /// </summary>
    public static Mutagen.Bethesda.Starfield.Activator BuildSurfaceCog(
        StarfieldMod mod,
        IStarfieldModGetter core,
        IActivatorGetter interiorOverride,
        string model,
        string rig,
        string anims,
        P3Float boundsMin,
        P3Float boundsMax,
        uint coreBaseId = CoreSurfaceBaseId)
    {
        ArgumentNullException.ThrowIfNull(mod);
        ArgumentNullException.ThrowIfNull(core);
        ArgumentNullException.ThrowIfNull(interiorOverride);
        if (string.IsNullOrWhiteSpace(model)) throw new ArgumentException("surface cog model path is required", nameof(model));
        if (string.IsNullOrWhiteSpace(rig)) throw new ArgumentException("surface cog rig path is required", nameof(rig));
        if (string.IsNullOrWhiteSpace(anims)) throw new ArgumentException("surface cog anims folder is required", nameof(anims));
        if (core.ModKey != CoreEsm) throw new InvalidOperationException($"surface cog core must be {CoreEsm}, got {core.ModKey}");
        if (mod.Worldspaces.Count > 0)
            throw new InvalidOperationException($"{mod.ModKey} must have zero WRLD overrides (found {mod.Worldspaces.Count})");
        if (mod.Cells.Records.Count > 0)
            throw new InvalidOperationException($"{mod.ModKey} must have zero CELL overrides (found {mod.Cells.Records.Count})");

        var key = SurfaceCogKey(coreBaseId);
        var coreBase = core.Activators.FirstOrDefault(a => a.FormKey == key)
            ?? throw new InvalidOperationException($"core plugin {core.ModKey} lacks ACTI {key}");
        if (mod.Activators.Any(a => a.FormKey == key))
            throw new InvalidOperationException($"{key} already exists in {mod.ModKey}");

        var ov = coreBase.DeepCopy();
        ov.Model ??= new Model();
        ov.Model.File = model;
        foreach (var old in ov.Components.OfType<AnimationGraphComponent>().ToList())
            ov.Components.Remove(old);
        ov.Components.Add(new AnimationGraphComponent
        {
            ANAM = GraphAnam,
            BNAM = rig,
            CNAM = anims,
        });
        ov.MarkerColor = interiorOverride.MarkerColor;
        ov.Flags = interiorOverride.Flags;
        ov.ActivationAngle = interiorOverride.ActivationAngle;
        ov.InvertFacing = interiorOverride.InvertFacing;
        ov.ObjectBounds = new ObjectBounds { First = boundsMin, Second = boundsMax };
        if (string.IsNullOrWhiteSpace(ov.Name?.String))
            ov.Name = SurfaceCogName;
        mod.Activators.Add(ov);
        return ov;
    }

    /// <summary>
    /// Validates that <paramref name="mod"/> overrides FO4TerrainCore.esm ACTI <paramref name="coreBaseId"/>
    /// (0x0A2D4B) with the expected model, rig, clip folder, ActivatorStateGraph01 graph component,
    /// PNAM/FNAM/JNAM matching <paramref name="interiorOverride"/>, OBND matching manifest bounds, and zero WRLD/CELL/QUST.
    /// </summary>
    public static IReadOnlyList<string> CheckSurfaceCog(
        IStarfieldModGetter mod,
        IStarfieldModGetter core,
        IActivatorGetter? interiorOverride,
        string model,
        string rig,
        string anims,
        P3Float boundsMin,
        P3Float boundsMax,
        uint coreBaseId = CoreSurfaceBaseId)
    {
        ArgumentNullException.ThrowIfNull(mod);
        ArgumentNullException.ThrowIfNull(core);
        var problems = new List<string>();
        void Need(bool ok, string what) { if (!ok) problems.Add(what); }

        Need(mod.Worldspaces.Count == 0, $"expected 0 WRLD records, found {mod.Worldspaces.Count}");
        Need(mod.Cells.Records.Count == 0, $"expected 0 CELL records, found {mod.Cells.Records.Count}");
        Need(mod.Quests.Count == 0, $"expected 0 QUST records, found {mod.Quests.Count}");

        var key = SurfaceCogKey(coreBaseId);
        var coreBase = core.Activators.FirstOrDefault(a => a.FormKey == key);
        Need(coreBase != null, $"core plugin {core.ModKey} lacks ACTI {key}");

        var hits = mod.Activators.Where(a => a.FormKey == key).ToList();
        Need(hits.Count == 1, $"expected 1 ACTI override at {key}, found {hits.Count}");
        if (hits.Count == 1)
        {
            var acti = hits[0];
            Need(acti.FormKey.ModKey == CoreEsm, $"ACTI {acti.FormKey} is not an override of {CoreEsm}");
            if (coreBase != null)
                Need(acti.EditorID == coreBase.EditorID, $"ACTI EditorID is '{acti.EditorID}', expected '{coreBase.EditorID}'");

            var wantModel = new Model { File = model }.File?.ToString();
            Need(acti.Model?.File?.ToString() == wantModel, $"ACTI model is '{acti.Model?.File?.ToString()}', expected '{wantModel}'");

            var graphs = acti.Components.OfType<IAnimationGraphComponentGetter>().ToList();
            Need(
                graphs.Count == 1
                && graphs[0].ANAM == GraphAnam
                && graphs[0].BNAM == rig
                && graphs[0].CNAM == anims,
                $"ACTI {acti.FormKey} AnimationGraphComponent mismatch (expected ANAM={GraphAnam}, BNAM={rig}, CNAM={anims})"
            );

            if (interiorOverride != null)
            {
                Need(acti.MarkerColor == interiorOverride.MarkerColor,
                     $"ACTI {acti.FormKey} PNAM MarkerColor {acti.MarkerColor} != {interiorOverride.MarkerColor}");
                Need(acti.Flags == interiorOverride.Flags,
                     $"ACTI {acti.FormKey} FNAM Flags {acti.Flags} != {interiorOverride.Flags}");
                Need(acti.ActivationAngle == interiorOverride.ActivationAngle && acti.InvertFacing == interiorOverride.InvertFacing,
                     $"ACTI {acti.FormKey} JNAM ActivationAngle/InvertFacing mismatch");
            }
            Need(BoundsMatch(acti.ObjectBounds, boundsMin, boundsMax),
                 $"ACTI {acti.FormKey} OBND {acti.ObjectBounds?.First}..{acti.ObjectBounds?.Second} != {boundsMin}..{boundsMax}");
        }

        return problems;
    }
}
