// SurfaceLiftCog: adds ACTI 0x802 (FO4SF_Vault111SurfaceCog, "Vault 111 Elevator") to FO4SFExitLift.esm
// with ZERO WRLD overrides so #858 (FO4SFHome.esm) and worldspace patches remain conflict-free.
// The shared lift-pair script places/ensures this activator dynamically at the Vault 111 hilltop entrance.
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;

public static class SurfaceLiftCog
{
    public const uint SurfaceCogId = 0x802;
    public const string SurfaceCogEdid = "FO4SF_Vault111SurfaceCog";
    public const string SurfaceCogName = "Vault 111 Elevator";
    public const string GraphAnam = "AnimTextData\\Tables\\Graphs\\ActivatorStateGraph01.agx";

    public static FormKey SurfaceCogKey(ModKey plugin) => new(plugin, SurfaceCogId);

    /// <summary>
    /// Adds ACTI 0x802 (FO4SF_Vault111SurfaceCog) to <paramref name="mod"/> using the converted
    /// vltelevatorexterior_anim model, rig, and animation clips under ActivatorStateGraph01.
    /// Enforces zero WRLD records on the plugin.
    /// </summary>
    public static Mutagen.Bethesda.Starfield.Activator BuildSurfaceCog(
        StarfieldMod mod,
        string model,
        string rig,
        string anims)
    {
        ArgumentNullException.ThrowIfNull(mod);
        if (string.IsNullOrWhiteSpace(model)) throw new ArgumentException("surface cog model path is required", nameof(model));
        if (string.IsNullOrWhiteSpace(rig)) throw new ArgumentException("surface cog rig path is required", nameof(rig));
        if (string.IsNullOrWhiteSpace(anims)) throw new ArgumentException("surface cog anims folder is required", nameof(anims));
        if (mod.Worldspaces.Count > 0)
            throw new InvalidOperationException($"{mod.ModKey} must have zero WRLD overrides (found {mod.Worldspaces.Count})");
        if (mod.Cells.Records.Count > 0)
            throw new InvalidOperationException($"{mod.ModKey} must have zero CELL overrides (found {mod.Cells.Records.Count})");

        var key = SurfaceCogKey(mod.ModKey);
        if (mod.Activators.Any(a => a.FormKey == key))
            throw new InvalidOperationException($"{key} already exists in {mod.ModKey}");

        var acti = new Mutagen.Bethesda.Starfield.Activator(key, StarfieldRelease.Starfield)
        {
            EditorID = SurfaceCogEdid,
            Name = SurfaceCogName,
            Model = new Model { File = model },
        };
        acti.Components.Add(new AnimationGraphComponent
        {
            ANAM = GraphAnam,
            BNAM = rig,
            CNAM = anims,
        });
        mod.Activators.Add(acti);

        if (mod.ModHeader.Stats.NextFormID <= SurfaceCogId)
            mod.ModHeader.Stats.NextFormID = SurfaceCogId + 1;

        return acti;
    }

    /// <summary>
    /// Validates that <paramref name="mod"/> carries ACTI 0x802 (FO4SF_Vault111SurfaceCog) with the expected
    /// model, rig, clip folder, and ActivatorStateGraph01 graph component, and carries zero WRLD/CELL/QUST records.
    /// Returns a list of problem strings (empty when valid).
    /// </summary>
    public static IReadOnlyList<string> CheckSurfaceCog(
        IStarfieldModGetter mod,
        string model,
        string rig,
        string anims)
    {
        ArgumentNullException.ThrowIfNull(mod);
        var problems = new List<string>();
        void Need(bool ok, string what) { if (!ok) problems.Add(what); }

        Need(mod.Worldspaces.Count == 0, $"expected 0 WRLD records, found {mod.Worldspaces.Count}");
        Need(mod.Cells.Records.Count == 0, $"expected 0 CELL records, found {mod.Cells.Records.Count}");
        Need(mod.Quests.Count == 0, $"expected 0 QUST records, found {mod.Quests.Count}");

        var key = SurfaceCogKey(mod.ModKey);
        var hits = mod.Activators.Where(a => a.FormKey == key).ToList();
        Need(hits.Count == 1, $"expected 1 ACTI at {key}, found {hits.Count}");
        if (hits.Count == 1)
        {
            var acti = hits[0];
            Need(acti.FormKey.ModKey == mod.ModKey, $"ACTI {acti.FormKey} is not owned by {mod.ModKey}");
            Need(acti.EditorID == SurfaceCogEdid, $"ACTI EditorID is '{acti.EditorID}', expected '{SurfaceCogEdid}'");
            Need(acti.Name?.String == SurfaceCogName, $"ACTI Name is '{acti.Name?.String}', expected '{SurfaceCogName}'");

            var wantModel = new Model { File = model }.File?.ToString();
            Need(acti.Model?.File?.ToString() == wantModel, $"ACTI model is '{acti.Model?.File?.ToString()}', expected '{wantModel}'");

            var graphs = acti.Components.OfType<IAnimationGraphComponentGetter>().ToList();
            Need(
                graphs.Count == 1
                && graphs[0].ANAM == GraphAnam
                && graphs[0].BNAM == rig
                && graphs[0].CNAM == anims,
                $"ACTI {SurfaceCogEdid} AnimationGraphComponent mismatch (expected ANAM={GraphAnam}, BNAM={rig}, CNAM={anims})"
            );
        }

        return problems;
    }
}
