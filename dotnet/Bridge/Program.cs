// Bridge: the observation bridge plugin (docs/ai/test-queue.md "Bridge", scripts/bridge/make_bridge.py).
//
// FO4SFBridge.esm holds exactly two records:
//   0x800  GLOB FO4SF_Cmd          a non-constant global the console sets ("set FO4SF_Cmd to 7"); the script echoes it
//   0x801  QUST FO4SF_BridgeQuest  start-game-enabled, no stages, carrying the Papyrus script FO4SF_Bridge
//                                  (scripts/bridge/FO4SF_Bridge.psc) with its two properties: FO4SF_Cmd -> the global,
//                                  Interval -> seconds between log lines (default 0.5)
// The VMAD shape copies vanilla Starfield quests (Starfield.esm 1.16.244, read with Mutagen 0.55.0-alpha.67): version 6,
// object format 2, extra-bind-data version 3, a fragment script entry with an empty name, object properties with alias
// -1; record versions 581 / 4 (GLOB) and 581 / 12 (QUST) as vanilla's. A quest that is StartGameEnabled with no stages
// exists in vanilla (MQ207C_AlwaysOn), so the engine starts such a quest on its own.
//
// usage: Bridge build --out <dir> [--plugin FO4SFBridge.esm] [--interval 0.5]
//        Bridge check <plugin>                 reads the plugin back and prints its records (exit 1 on a mismatch)
using System.Globalization;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;

const uint GlobalId = 0x800, QuestId = 0x801;
const string ScriptName = "FO4SF_Bridge", GlobalEdid = "FO4SF_Cmd", QuestEdid = "FO4SF_BridgeQuest";

static int Usage()
{
    Console.Error.WriteLine("usage: Bridge build --out <dir> [--plugin FO4SFBridge.esm] [--interval 0.5] | Bridge check <plugin>");
    return 2;
}
if (args.Length == 0) return Usage();
string Arg(string name, string dflt) { var i = Array.IndexOf(args, name); return i >= 0 && i + 1 < args.Length ? args[i + 1] : dflt; }

if (args[0] == "build")
{
    var outDir = Arg("--out", "");
    if (outDir == "") return Usage();
    var plugin = Arg("--plugin", "FO4SFBridge.esm");
    var interval = float.Parse(Arg("--interval", "0.5"), CultureInfo.InvariantCulture);
    var modKey = ModKey.FromFileName(plugin);
    var mod = new StarfieldMod(modKey, StarfieldRelease.Starfield);
    mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;     // as every plugin of ours that loads (TerrainOverlays, SliceDoor)

    var glob = new Global(new FormKey(modKey, GlobalId), StarfieldRelease.Starfield)
    {
        EditorID = GlobalEdid, Data = 0f, FormVersion = 581, Version2 = 4,
    };
    mod.Globals.Add(glob);

    var quest = new Quest(new FormKey(modKey, QuestId), StarfieldRelease.Starfield)
    {
        EditorID = QuestEdid, Name = "FO4SF bridge", FormVersion = 581, Version2 = 12,
        Data = new QuestData { Flags = Quest.Flag.StartGameEnabled, Priority = 30 },
    };
    var script = new ScriptEntry { Name = ScriptName, Flags = ScriptEntry.Flag.Local };
    script.Properties.Add(new ScriptObjectProperty
    {
        Name = GlobalEdid, Flags = ScriptProperty.Flag.Edited,
        Object = new FormLink<IStarfieldMajorRecordGetter>(glob.FormKey), Alias = -1, Unused = 0,
    });
    script.Properties.Add(new ScriptFloatProperty { Name = "Interval", Flags = ScriptProperty.Flag.Edited, Data = interval });
    var vmad = new QuestAdapter
    {
        Version = 6, ObjectFormat = 2, ExtraBindDataVersion = 3,
        Script = new ScriptEntry { Name = "", Flags = ScriptEntry.Flag.Local },
    };
    vmad.Scripts.Add(script);
    quest.VirtualMachineAdapter = vmad;
    mod.Quests.Add(quest);

    mod.ModHeader.Stats.NextFormID = QuestId + 1;
    Directory.CreateDirectory(outDir);
    var path = Path.Combine(outDir, plugin);
    var sfKey = ModKey.FromFileName("Starfield.esm");
    mod.BeginWrite.ToPath(path).WithLoadOrder(sfKey).WithKnownMasters(new KeyedMasterStyle(sfKey, MasterStyle.Full)).Write();
    Console.WriteLine($"wrote {path} ({new FileInfo(path).Length:N0} bytes): {GlobalEdid} {glob.FormKey}, {QuestEdid} {quest.FormKey} " +
                      $"script {ScriptName} (interval {interval.ToString(CultureInfo.InvariantCulture)} s), header flags {mod.ModHeader.Flags}");
    return 0;
}

if (args[0] == "check" && args.Length >= 2)
{
    var path = args[1];
    var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
    styles.Set(new KeyedMasterStyle(ModKey.FromFileName("Starfield.esm"), MasterStyle.Full));
    var mod = StarfieldMod.CreateFromBinaryOverlay(path, StarfieldRelease.Starfield, new BinaryReadParameters { MasterFlagsLookup = styles });
    var problems = new List<string>();
    Console.WriteLine($"{Path.GetFileName(path)}: header flags {mod.ModHeader.Flags}, masters [{string.Join(", ", mod.ModHeader.MasterReferences.Select(m => m.Master.FileName))}], " +
                      $"next form id 0x{mod.ModHeader.Stats.NextFormID:X}, {mod.Globals.Count} GLOB, {mod.Quests.Count} QUST");
    var g = mod.Globals.FirstOrDefault();
    if (g == null || g.FormKey.ID != GlobalId || g.EditorID != GlobalEdid) problems.Add("global 0x800 FO4SF_Cmd missing");
    else
    {
        Console.WriteLine($"  GLOB {g.EditorID} {g.FormKey} data={g.Data} flags={g.MajorFlags} fv={g.FormVersion}");
        if (g.MajorFlags.HasFlag(Global.MajorFlag.Constant)) problems.Add("the global is Constant: the console could not set it");
    }
    var q = mod.Quests.FirstOrDefault();
    if (q == null || q.FormKey.ID != QuestId || q.EditorID != QuestEdid) problems.Add("quest 0x801 FO4SF_BridgeQuest missing");
    else
    {
        var v = q.VirtualMachineAdapter;
        Console.WriteLine($"  QUST {q.EditorID} {q.FormKey} flags={q.Data?.Flags} prio={q.Data?.Priority} stages={q.Stages.Count} fv={q.FormVersion} " +
                          $"vmad ver={v?.Version} fmt={v?.ObjectFormat} ebdv={v?.ExtraBindDataVersion} scripts={v?.Scripts.Count}");
        if (q.Data == null || !q.Data.Flags.HasFlag(Quest.Flag.StartGameEnabled)) problems.Add("the quest is not StartGameEnabled");
        var s = v?.Scripts.FirstOrDefault(x => x.Name == ScriptName);
        if (s == null) problems.Add($"script {ScriptName} not attached");
        else
        {
            foreach (var p in s.Properties)
                Console.WriteLine($"    property {p.Name} ({p.GetType().Name.Replace("BinaryOverlay", "")}) flags={p.Flags}" +
                                  (p is IScriptObjectPropertyGetter o ? $" -> {o.Object.FormKey} alias={o.Alias}" : "") +
                                  (p is IScriptFloatPropertyGetter f ? $" = {f.Data.ToString(CultureInfo.InvariantCulture)}" : ""));
            var cmd = s.Properties.OfType<IScriptObjectPropertyGetter>().FirstOrDefault(p => p.Name == GlobalEdid);
            if (cmd == null || g == null || cmd.Object.FormKey != g.FormKey) problems.Add("property FO4SF_Cmd does not point at the global");
        }
    }
    foreach (var p in problems) Console.WriteLine("FAIL  " + p);
    Console.WriteLine(problems.Count == 0 ? "all checks pass" : $"{problems.Count} problem(s)");
    return problems.Count == 0 ? 0 : 1;
}
return Usage();
