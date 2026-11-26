// AnimConsoleProbe: variant D of the Vault 111 animation experiment, our console on a vanilla activator graph
// (docs/research/anim-console-probe.md, FAL-489).
//
// FO4SFAnimConsole.esm (masters Starfield.esm + FO4Port.esm, in that order):
//   ACTI  an OVERRIDE of the port's console base (default EditorID FO4Port_acti_091a48_fallout4, "Vault Door Controls"): the
//         record as it is, its model path replaced by the converted model with its own rig, and an AnimationGraphComponent
//         added (ANAM = the activator graph, BNAM = the rig, CNAM = the folder of the .af / .afx clips), the door's pattern
//   QUST  FO4SF_AnimConsoleQuest   start game enabled, stages 10 20 21..28 30 40 60, script FO4SF_AnimConsoleQuest, NO properties
// The quest's script spawns a copy of that base with PlaceAtMe (any cell: the override is on the base), so the placed console
// 001319 of the port's Vault 111 cell shows the same model when the player stands there. The base's local id is the script's
// BaseId line (the stager reads it with `info` and writes it in).
//
// usage: AnimConsoleProbe info  <FO4Port.esm> <Starfield.esm> [--edid <EditorID>]      read only: id, model, name, graph component
//        AnimConsoleProbe build <FO4Port.esm> <Starfield.esm> <out dir> --model <path below Meshes> --rig <BNAM> --anims <CNAM> [--edid <EditorID>]
//        AnimConsoleProbe check <plugin> <FO4Port.esm> <Starfield.esm> --model <..> --rig <..> --anims <..> [--edid <EditorID>]   exit 1 on a mismatch
//        AnimConsoleProbe fixture <out dir>     a synthetic Starfield.esm and FO4Port.esm (one ACTI) in <out dir>
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;

try
{
    var rest = args.ToList();
    bool productionLift = rest.Remove("--production-lift");
    string? Opt(string name)
    {
        int i = rest.IndexOf(name);
        if (i < 0) return null;
        if (i + 1 >= rest.Count) throw new AnimConsoleProbe.Refusal(name + " needs a value");
        var v = rest[i + 1];
        rest.RemoveRange(i, 2);
        return v;
    }
    var edid = Opt("--edid") ?? AnimConsoleProbe.DefaultEdid;
    var model = Opt("--model");
    var rig = Opt("--rig");
    var anims = Opt("--anims");
    var surfaceModel = Opt("--surface-model");
    var surfaceRig = Opt("--surface-rig");
    var surfaceAnims = Opt("--surface-anims");
    bool hasAnySurface = surfaceModel != null || surfaceRig != null || surfaceAnims != null;
    if (hasAnySurface)
    {
        if (!productionLift) throw new AnimConsoleProbe.Refusal("--surface-* options require --production-lift");
        if (surfaceModel == null || surfaceRig == null || surfaceAnims == null)
            throw new AnimConsoleProbe.Refusal("--surface-model, --surface-rig, and --surface-anims must all be provided together");
    }
    if (rest.Count == 3 && rest[0] == "info") return AnimConsoleProbe.Info(rest[1], rest[2], edid);
    if (rest.Count == 4 && rest[0] == "build" && model != null && rig != null && anims != null)
        return AnimConsoleProbe.Build(rest[1], rest[2], rest[3], edid, model, rig, anims, productionLift, surfaceModel, surfaceRig, surfaceAnims);
    if (rest.Count == 4 && rest[0] == "check" && model != null && rig != null && anims != null)
        return AnimConsoleProbe.Check(rest[1], rest[2], rest[3], edid, model, rig, anims, productionLift, surfaceModel, surfaceRig, surfaceAnims);
    if (rest.Count == 2 && rest[0] == "fixture") return AnimConsoleProbe.Fixture(rest[1]);
}
catch (AnimConsoleProbe.Refusal r)
{
    Console.Error.WriteLine("refused: " + r.Message);
    return 1;
}
Console.Error.WriteLine("usage: AnimConsoleProbe info <FO4Port.esm> <Starfield.esm> [--edid E] | build <FO4Port.esm> <Starfield.esm> <out dir> --model M --rig R --anims A [--edid E] | " +
                        "check <plugin> <FO4Port.esm> <Starfield.esm> --model M --rig R --anims A [--edid E] | fixture <out dir>");
return 2;

static class AnimConsoleProbe
{
    public class Refusal(string m) : Exception(m);

    const StarfieldRelease Release = StarfieldRelease.Starfield;
    public const string DefaultEdid = "FO4Port_acti_091a48_fallout4";
    public const string GraphAnam = "AnimTextData\\Tables\\Graphs\\ActivatorStateGraph01.agx";
    static readonly ModKey SfEsm = ModKey.FromFileName("Starfield.esm");
    static readonly ModKey PortEsm = ModKey.FromFileName("FO4Port.esm");
    public static readonly ModKey Plugin = ModKey.FromFileName("FO4SFAnimConsole.esm");

    // the layout (scripts/newgame/FO4SF_AnimConsoleQuest.psc carries the same quest id)
    const uint QuestId = 0x800;
    const string QuestEdid = "FO4SF_AnimConsoleQuest", Script = "FO4SF_AnimConsoleQuest";
    static readonly ushort[] Stages = { 10, 11, 20, 21, 22, 23, 24, 25, 26, 27, 28, 30, 31, 32, 40, 60 };

    static FormKey Own(uint id) => new(Plugin, id);

    static Cache<IModMasterStyledGetter, ModKey> Styles()
    {
        var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        styles.Set(new KeyedMasterStyle(SfEsm, MasterStyle.Full));
        styles.Set(new KeyedMasterStyle(PortEsm, MasterStyle.Full));
        return styles;
    }

    static IStarfieldModDisposableGetter Open(string path) =>
        StarfieldMod.CreateFromBinaryOverlay(path, Release, new BinaryReadParameters { MasterFlagsLookup = Styles() });

    static IActivatorGetter FindBase(IStarfieldModGetter port, string edid)
    {
        var hits = port.Activators.Where(a => string.Equals(a.EditorID, edid, StringComparison.OrdinalIgnoreCase)).ToList();
        if (hits.Count != 1) throw new Refusal($"{hits.Count} ACTI named {edid} in {port.ModKey} (one needed)");
        return hits[0];
    }

    static string Show(IActivatorGetter a)
    {
        var g = a.Components.OfType<IAnimationGraphComponentGetter>().FirstOrDefault();
        return $"ACTI {a.FormKey} {a.EditorID} name '{a.Name?.String}' model {a.Model?.File} graph component " +
               (g == null ? "none" : $"ANAM {g.ANAM} BNAM {g.BNAM} CNAM {g.CNAM}");
    }

    public static int Info(string portPath, string sfPath, string edid)
    {
        using var port = Open(portPath);
        var a = FindBase(port, edid);
        Console.WriteLine(Show(a));
        Console.WriteLine($"BASE_ID 0x{a.FormKey.ID:X6}");
        Console.WriteLine($"MODEL {a.Model?.File}");
        return 0;
    }

    static Quest MakeQuest()
    {
        var quest = new Quest(Own(QuestId), Release)
        {
            EditorID = QuestEdid, Name = "FO4SF animation console probe", FormVersion = 581, Version2 = 12,
            Data = new QuestData { Flags = Quest.Flag.StartGameEnabled, Priority = 30 },
        };
        foreach (var s in Stages) quest.Stages.Add(new QuestStage { Index = s });
        quest.VirtualMachineAdapter = new QuestAdapter
        {
            Version = 6, ObjectFormat = 2, ExtraBindDataVersion = 3,
            Script = new ScriptEntry { Name = "", Flags = ScriptEntry.Flag.Local },
        };
        quest.VirtualMachineAdapter.Scripts.Add(new ScriptEntry { Name = Script, Flags = ScriptEntry.Flag.Local });
        return quest;
    }

    public static int Build(string portPath, string sfPath, string outDir, string edid, string model, string rig, string anims, bool productionLift = false, string? surfaceModel = null, string? surfaceRig = null, string? surfaceAnims = null)
    {
        if (productionLift && edid != "FO4Port_acti_0244ef_fallout4") throw new Refusal("production lift must override the original Vault 111 lift");
        bool hasSurface = surfaceModel != null && surfaceRig != null && surfaceAnims != null;
        if (hasSurface && !productionLift) throw new Refusal("--surface-* options require --production-lift");
        using var port = Open(portPath);
        var baseRec = FindBase(port, edid);
        if (baseRec.FormKey.ModKey != PortEsm) throw new Refusal("ACTI must be owned by FO4Port.esm");
        var key = productionLift ? ModKey.FromFileName("FO4SFExitLift.esm") : Plugin;
        var mod = new StarfieldMod(key, Release);
        mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;               // as every plugin of ours that loads
        mod.ModHeader.Author = "fo4-to-starfield";
        var ov = baseRec.DeepCopy();                                               // an override: the same form key, FO4Port.esm
        ov.Model ??= new Model();
        ov.Model.File = model;
        foreach (var old in ov.Components.OfType<AnimationGraphComponent>().ToList()) ov.Components.Remove(old);
        ov.Components.Add(new AnimationGraphComponent { ANAM = GraphAnam, BNAM = rig, CNAM = anims });
        mod.Activators.Add(ov);
        if (!productionLift) mod.Quests.Add(MakeQuest());
        mod.ModHeader.Stats.NextFormID = 0x801;
        if (hasSurface) SurfaceLiftCog.BuildSurfaceCog(mod, surfaceModel!, surfaceRig!, surfaceAnims!);
        Write(mod, outDir, SfEsm, PortEsm);
        var path = Path.Combine(outDir, key.FileName);
        Console.WriteLine($"wrote {path} ({new FileInfo(path).Length:N0} bytes): override of {Show(baseRec)}");
        Console.WriteLine($"now model {model}, graph component ANAM {GraphAnam} BNAM {rig} CNAM {anims}");
        Console.WriteLine($"BASE_ID 0x{baseRec.FormKey.ID:X6}");
        return 0;
    }

    static void Write(StarfieldMod mod, string outDir, params ModKey[] masters)
    {
        Directory.CreateDirectory(outDir);
        var path = Path.Combine(outDir, mod.ModKey.FileName);
        // an existing plugin stays until the write succeeds; Mutagen needs the plugin's own file name, so write in a temp folder
        var tmpDir = Path.Combine(outDir, ".tmp-" + Guid.NewGuid().ToString("N"));
        try
        {
            Directory.CreateDirectory(tmpDir);
            var tmp = Path.Combine(tmpDir, mod.ModKey.FileName);
            foreach (var m in masters)
                if (!mod.ModHeader.MasterReferences.Any(r => r.Master == m)) mod.ModHeader.MasterReferences.Add(new MasterReference { Master = m });
            mod.BeginWrite.ToPath(tmp).WithLoadOrder(masters)
                .WithKnownMasters(masters.Select(m => new KeyedMasterStyle(m, MasterStyle.Full)).ToArray())
                .WithMastersListContent(MastersListContentOption.NoCheck).Write();
            File.Move(tmp, path, overwrite: true);
        }
        finally
        {
            if (Directory.Exists(tmpDir)) Directory.Delete(tmpDir, true);
        }
    }

    // ---------------------------------------------------------------- check (Mutagen read-back)

    public static int Check(string pluginPath, string portPath, string sfPath, string edid, string model, string rig, string anims, bool productionLift = false, string? surfaceModel = null, string? surfaceRig = null, string? surfaceAnims = null)
    {
        if (productionLift && edid != "FO4Port_acti_0244ef_fallout4") throw new Refusal("production lift must override the original Vault 111 lift");
        bool hasSurface = surfaceModel != null && surfaceRig != null && surfaceAnims != null;
        if (hasSurface && !productionLift) throw new Refusal("--surface-* options require --production-lift");
        using var port = Open(portPath);
        var baseRec = FindBase(port, edid);
        using var mod = Open(pluginPath);
        var problems = new List<string>();
        void Need(bool ok, string what) { if (!ok) problems.Add(what); }

        var masters = mod.ModHeader.MasterReferences.Select(m => m.Master).ToList();
        Console.WriteLine($"{Path.GetFileName(pluginPath)}: header {mod.ModHeader.Flags}, masters [{string.Join(", ", masters)}], next 0x{mod.ModHeader.Stats.NextFormID:X}");
        var key = productionLift ? ModKey.FromFileName("FO4SFExitLift.esm") : Plugin;
        Need(mod.ModKey == key, $"the file is {mod.ModKey}, not {key}");
        Need(baseRec.FormKey.ModKey == PortEsm, "ACTI is not owned by FO4Port.esm");
        Need(mod.ModHeader.Flags.HasFlag(StarfieldModHeader.HeaderFlag.Master), "not flagged as a master");
        Need(masters.SequenceEqual(new[] { SfEsm, PortEsm }), "masters are not exactly [Starfield.esm, FO4Port.esm]");
        var all = mod.EnumerateMajorRecords().ToList();
        int expectedAll = productionLift ? (hasSurface ? 2 : 1) : 2;
        Need(all.Count == expectedAll, "unexpected record count in exit lift plugin");
        var own = all.Where(r => r.FormKey.ModKey == key).Select(r => r.FormKey).ToList();
        if (productionLift)
        {
            if (hasSurface)
            {
                Need(own.Count == 1 && own[0] == SurfaceLiftCog.SurfaceCogKey(key), "unexpected records owned by this plugin");
                problems.AddRange(SurfaceLiftCog.CheckSurfaceCog(mod, surfaceModel!, surfaceRig!, surfaceAnims!));
            }
            else
            {
                Need(own.Count == 0, "unexpected records owned by this plugin");
            }
            Need(mod.Quests.Count == 0, "production lift carries a probe quest");
        }
        else
        {
            Need(own.Count == 1 && own[0] == Own(QuestId), "unexpected records owned by this plugin");
        }
        int expectedActi = hasSurface ? 2 : 1;
        var ovr = mod.Activators.FirstOrDefault(a => a.FormKey == baseRec.FormKey);
        Need(mod.Activators.Count() == expectedActi && ovr != null, $"the ACTI is not an override of {baseRec.FormKey}");
        if (ovr != null)
        {
            Console.WriteLine("  override: " + Show(ovr));
            Need(ovr.EditorID == baseRec.EditorID, "the override's EditorID changed");
            Need(ovr.Name?.String == baseRec.Name?.String, "the override's name changed (the prompt must stay)");
            var wantModel = new Model { File = model }.File.ToString();                        // Mutagen files a model path as Meshes/<path>
            Need(ovr.Model?.File?.ToString() == wantModel, $"the model is not {wantModel}");
            var g = ovr.Components.OfType<IAnimationGraphComponentGetter>().ToList();
            Need(g.Count == 1 && g[0].ANAM == GraphAnam && g[0].BNAM == rig && g[0].CNAM == anims, "the animation graph component is not (activator graph, rig, clip folder) exactly once");
            Need(ovr.Components.Count() == baseRec.Components.Count() - baseRec.Components.OfType<IAnimationGraphComponentGetter>().Count() + 1,
                 "the override dropped or added another component");
        }
        var q = mod.Quests.FirstOrDefault(x => x.FormKey == Own(QuestId));
        if (!productionLift) Need(q?.EditorID == QuestEdid, $"no QUST {QuestEdid}");
        if (!productionLift && q != null)
        {
            var scripts = q.VirtualMachineAdapter?.Scripts.ToList() ?? new();
            Console.WriteLine($"  QUST {q.EditorID} flags {q.Data?.Flags} stages [{string.Join(",", q.Stages.Select(s => s.Index))}] scripts [{string.Join(", ", scripts.Select(s => $"{s.Name} ({s.Properties.Count} properties)"))}]");
            Need(q.Data?.Flags.HasFlag(Quest.Flag.StartGameEnabled) == true, "the quest is not start game enabled");
            Need(q.Stages.Select(s => s.Index).SequenceEqual(Stages), $"stages are not [{string.Join(",", Stages)}]");
            Need(scripts.Count == 1 && scripts[0].Name == Script && scripts[0].Properties.Count == 0, $"script is not {Script} without properties");
        }
        foreach (var x in problems) Console.WriteLine("FAIL  " + x);
        Console.WriteLine(problems.Count == 0 ? "all checks pass" : $"{problems.Count} problem(s)");
        return problems.Count == 0 ? 0 : 1;
    }

    // ---------------------------------------------------------------- fixture

    public static int Fixture(string outDir)
    {
        Directory.CreateDirectory(outDir);
        var sf = new StarfieldMod(SfEsm, Release);
        sf.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        sf.BeginWrite.ToPath(Path.Combine(outDir, "Starfield.esm")).WithNoLoadOrder().Write();
        var port = new StarfieldMod(PortEsm, Release);
        port.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        var acti = new Mutagen.Bethesda.Starfield.Activator(new FormKey(PortEsm, 0x001234), Release)
        {
            EditorID = DefaultEdid, Name = "Vault Door Controls", Model = new Model { File = "fo4port\\interiors\\vault\\props\\console01.nif" },
        };
        port.Activators.Add(acti);
        port.Activators.Add(new Mutagen.Bethesda.Starfield.Activator(new FormKey(PortEsm, 0x1235), Release)
        {
            EditorID = "FO4Port_acti_0244ef_fallout4", Model = new Model { File = "fo4port/lift.nif" },
        });
        port.ModHeader.MasterReferences.Add(new MasterReference { Master = SfEsm });
        port.BeginWrite.ToPath(Path.Combine(outDir, "FO4Port.esm")).WithLoadOrder(SfEsm)
            .WithKnownMasters(new KeyedMasterStyle(SfEsm, MasterStyle.Full)).WithMastersListContent(MastersListContentOption.NoCheck).Write();
        Console.WriteLine($"wrote {Path.Combine(outDir, "Starfield.esm")} and {Path.Combine(outDir, "FO4Port.esm")}");
        return 0;
    }
}
