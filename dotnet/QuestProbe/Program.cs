// QuestProbe: the quest-engine questions of docs/questprobe/engine-questions.md (N1 of the NPC and quest research,
// research/next-phase/npcs-ai-factions-dialogue-quests.md section 9) in one plugin, FO4SFQuestProbe.esm. Its quest
// waits until the player stands in one converted interior (by default the Boston Public Library, far from Red Rocket),
// then asks the engine five questions and writes each answer to a user log: does a stage fragment run, does OnStageSet
// fire, does a quest marker follow a forced alias, does our own quest type get a Missions-tab heading, and does a
// Story Manager branch of our own start a quest from a script event. Claude's project.
//
//   write <Starfield.esm> <FO4Port.esm> <out dir> [--cell FO4Port_BostonPublicLibrary02] [--no-sm] [--plugin <name>]
//        the plugin, mastered on Starfield.esm only: QUST FO4SF_QProbe (start game enabled; stages 10 / 20 / 100;
//        objective 10 on the empty optional alias Target; a stage-10 fragment) with FO4SF_QProbeQuest, our quest-type
//        keyword, and unless --no-sm a script-event keyword, the quest FO4SF_QProbeSM and an SMBN / SMQN pair under
//        Starfield's own Script Event node. Starfield.esm is read for the shapes copied from vanilla records: the quest
//        type's keyword type (QuestTypeSideQuest 047600), MQ00's fragment layout and the Script Event node. The port is
//        read for the cell's COC marker (the "player is here" anchor) and the marker's target, the cell's load door
//        farthest from it (else a door or an object on the marker's floor, see Resolve); both are resolved at run time
//        with Game.GetFormFromFile (plugin-local ids).
//   check <plugin> <Starfield.esm> <FO4Port.esm> [same options]
//        reads the plugin back and checks every record, property and id the scripts rely on (exit 1 on a problem); also
//        prints the vanilla shapes it was built from, as evidence.
//   selftest <scratch dir>
//        synthetic Starfield.esm and port; write + check for both variants, and mutations check rejects.
// Nothing is deployed and no game file is written.
using System.Globalization;
using Mutagen.Bethesda;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Cache;
using Mutagen.Bethesda.Plugins.Records;
using Noggog;
using SF = Mutagen.Bethesda.Starfield;

if (args.Length == 0) return QuestProbe.Usage();
try
{
    return args[0] switch
    {
        "write" when args.Length >= 4 => QuestProbe.Write(args[1], args[2], args[3], QuestProbe.Options.From(args)),
        "check" when args.Length >= 4 => QuestProbe.Check(args[1], args[2], args[3], QuestProbe.Options.From(args)),
        "selftest" when args.Length >= 2 => QuestProbe.SelfTest(args[1]),
        _ => QuestProbe.Usage(),
    };
}
catch (QuestProbe.Refusal e)
{
    Console.Error.WriteLine("refused: " + e.Message);
    return 2;
}

static class QuestProbe
{
    public const string Plugin = "FO4SFQuestProbe.esm", DefaultCell = "FO4Port_BostonPublicLibrary02";
    public const string QuestEdid = "FO4SF_QProbe", ScriptName = "FO4SF_QProbeQuest", FragmentScript = "FO4SF_QProbeFragments";
    public const string FragmentName = "Fragment_Stage_0010_Item_00", QuestTypeEdid = "FO4SF_QuestTypeCommonwealth";
    public const string QuestTypeName = "Commonwealth", EventEdid = "FO4SF_QProbeEvent", SmQuestEdid = "FO4SF_QProbeSM";
    public const string SmScript = "FO4SF_QProbeSMQuest", BranchEdid = "FO4SF_QProbeBranch", NodeEdid = "FO4SF_QProbeNode";
    public const uint QuestId = 0x800, QuestTypeId = 0x801, EventId = 0x802, SmQuestId = 0x803, BranchId = 0x804, NodeId = 0x805;
    // Starfield.esm, verified: QuestTypeSideQuest (the mission's tab), COCMarkerHeading (the port's COC markers); MQ00
    // carries a stage-10 fragment (PC, 19 Oct: sets MQ101Debug, waits, starts MQ101)
    public const uint QuestTypeSideId = 0x047600, CocMarkerId = 0x000032;
    public const string QuestTypeSideEdid = "QuestTypeSideQuest", FragmentModel = "MQ00";
    public static readonly ushort[] Stages = { 10, 20, 100 };
    public const ushort Objective = 10, FragmentStage = 10;
    public const string ObjectiveText = "Reach the marked door";
    public const int TargetAlias = 0;
    static readonly ModKey SfEsm = ModKey.FromFileName("Starfield.esm");
    static readonly RecordType ScriptEventType = new("SCPT");

    public class Refusal(string m) : Exception(m);

    public static int Usage()
    {
        Console.Error.WriteLine("usage: see the header of dotnet/QuestProbe/Program.cs (write | check | selftest)");
        return 2;
    }
    public static string? ArgOrNull(string[] a, string name) { var i = Array.IndexOf(a, name); return i >= 0 && i + 1 < a.Length ? a[i + 1] : null; }
    static string F(float v) => v.ToString("0.###", CultureInfo.InvariantCulture);

    public record Options(string Plugin, string Cell, bool StoryManager)
    {
        public static Options From(string[] a) => new(ArgOrNull(a, "--plugin") ?? QuestProbe.Plugin, ArgOrNull(a, "--cell") ?? DefaultCell, !a.Contains("--no-sm"));
    }

    static BinaryReadParameters Full(params ModKey[] keys)
    {
        var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        foreach (var k in keys) styles.Set(new KeyedMasterStyle(k, MasterStyle.Full));
        return new BinaryReadParameters { MasterFlagsLookup = styles };
    }

    // ---------------------------------------------------------------- the port: where the probe runs

    public record Place(uint Anchor, uint Target, string TargetBase, float Distance);
    public const float MaxRise = 3f, MaxReach = 60f, MinReach = 8f;

    /// The cell's one COC marker (the player's "here" test: same parent cell) and the marker's target, so the compass
    /// has somewhere to point: the load door (a placed object with a teleport destination) farthest from it; in a cell
    /// with none (the library in the installed port, PC 19 Oct), the farthest door, then the farthest object, on the
    /// marker's floor (within MaxRise metres of its height) and within MaxReach metres, so the player can walk to it.
    public static Place Resolve(string portPath, string cellEdid)
    {
        using var port = SF.StarfieldMod.CreateFromBinaryOverlay(portPath, SF.StarfieldRelease.Starfield, Full(SfEsm));
        var cell = port.EnumerateMajorRecords<SF.ICellGetter>().FirstOrDefault(c => c.EditorID == cellEdid && c.FormKey.ModKey == port.ModKey)
                   ?? throw new Refusal($"{port.ModKey} has no cell {cellEdid}");
        var refs = cell.Persistent.Concat(cell.Temporary).OfType<SF.IPlacedObjectGetter>().ToList();
        var cocs = refs.Where(r => r.Base.FormKey == new FormKey(SfEsm, CocMarkerId)).ToList();
        if (cocs.Count != 1) throw new Refusal($"{cellEdid} has {cocs.Count} COC markers, not one");
        var a = cocs[0].Position;
        float Dist(SF.IPlacedObjectGetter r) => MathF.Sqrt(MathF.Pow(r.Position.X - a.X, 2) + MathF.Pow(r.Position.Y - a.Y, 2) + MathF.Pow(r.Position.Z - a.Z, 2));
        var doors = port.Doors.Select(d => d.FormKey).ToHashSet();
        var own = refs.Where(r => r.FormKey.ModKey == port.ModKey && r != cocs[0]).ToList();
        var level = own.Where(r => MathF.Abs(r.Position.Z - a.Z) <= MaxRise && Dist(r) <= MaxReach && Dist(r) >= MinReach).ToList();
        SF.IPlacedObjectGetter? Far(IEnumerable<SF.IPlacedObjectGetter> c) => c.OrderByDescending(Dist).ThenBy(r => r.FormKey.ID).FirstOrDefault();
        var (door, kind) = Far(own.Where(r => r.TeleportDestination is not null)) is { } ld ? (ld, "load door")
                         : Far(level.Where(r => doors.Contains(r.Base.FormKey))) is { } d ? (d, "door")
                         : Far(level) is { } o ? (o, "object")
                         : throw new Refusal($"{cellEdid} has nothing between {MinReach} and {MaxReach} m of its COC marker on its floor to point the marker at");
        var b = (port.EnumerateMajorRecords().FirstOrDefault(x => x.FormKey == door.Base.FormKey) is { } rec ? $"{rec.EditorID}" : door.Base.FormKey.ToString()) + $", {kind}";
        return new Place(cocs[0].FormKey.ID, door.FormKey.ID, b, Dist(door));
    }

    // ---------------------------------------------------------------- Starfield: the vanilla shapes copied

    public record Vanilla(SF.IKeywordGetter SideType, SF.IQuestAdapterGetter Mq00Vmad, SF.IQuestScriptFragmentGetter Mq00Fragment,
                          bool FragmentScriptListed, SF.IStoryManagerEventNodeGetter? ScriptEventNode, FormKey? LastChild, int ScriptEventQuests, string EventDataExample);

    public static Vanilla ReadVanilla(SF.IStarfieldModDisposableGetter sf, bool storyManager)
    {
        var side = sf.Keywords.FirstOrDefault(k => k.FormKey == new FormKey(SfEsm, QuestTypeSideId) && k.EditorID == QuestTypeSideEdid)
                   ?? throw new Refusal($"Starfield.esm {QuestTypeSideId:X6} is not the KYWD {QuestTypeSideEdid}");
        var mq00 = sf.Quests.FirstOrDefault(q => q.EditorID == FragmentModel) ?? throw new Refusal($"Starfield.esm has no quest {FragmentModel}");
        var vmad = mq00.VirtualMachineAdapter ?? throw new Refusal($"{FragmentModel} has no scripts");
        var frag = vmad.Fragments.FirstOrDefault() ?? throw new Refusal($"{FragmentModel} has no stage fragment to copy the layout of");
        bool listed = vmad.Scripts.Any(s => s.Name == vmad.Script.Name);
        if (!storyManager) return new Vanilla(side, vmad, frag, listed, null, null, 0, "");
        var nodes = sf.EnumerateMajorRecords<SF.IAStoryManagerNodeGetter>().ToList();
        var events = nodes.OfType<SF.IStoryManagerEventNodeGetter>().Where(n => n.Type == SF.StoryManagerEventNode.Types.ScriptEvent).ToList();
        if (events.Count != 1) throw new Refusal($"Starfield.esm has {events.Count} Script Event SMEN nodes, not one (build with --no-sm)");
        var smen = events[0];
        var children = nodes.Where(n => n.Parent.FormKey == smen.FormKey).ToList();
        var named = children.Select(n => n.PreviousSibling.FormKey).Where(k => !k.IsNull).ToHashSet();
        var last = children.Where(n => !named.Contains(n.FormKey)).ToList();
        int scpt = sf.Quests.Count(q => q.Event == ScriptEventType);
        string example = "none found";
        foreach (var n in nodes)
            foreach (var c in n.Conditions)
                if (c.Data is SF.IGetEventDataConditionDataGetter ge)
                { example = $"{n.EditorID}: GetEventData {ge.Function} {ge.Member} {ge.Record.FormKey} {c.CompareOperator} {(c as SF.IConditionFloatGetter)?.ComparisonValue}"; goto found; }
        found:
        return new Vanilla(side, vmad, frag, listed, smen, last.Count == 1 ? last[0].FormKey : null, scpt, example);
    }

    // ---------------------------------------------------------------- write

    static SF.ScriptObjectProperty Obj(string name, FormKey fk, int alias = -1) => new()
    {
        Name = name, Flags = SF.ScriptProperty.Flag.Edited, Object = new FormLink<SF.IStarfieldMajorRecordGetter>(fk), Alias = (short)alias, Unused = 0,
    };

    /// The int and float properties of FO4SF_QProbeQuest, by name (the check compares them; the Python test reads them).
    public static List<(string Name, object Value)> Properties(Place p) => new()
    {
        ("AnchorId", (int)p.Anchor), ("TargetId", (int)p.Target),
    };

    public static int Write(string sfPath, string portPath, string outDir, Options o)
    {
        var place = Resolve(portPath, o.Cell);
        using var sf = SF.StarfieldMod.CreateFromBinaryOverlay(sfPath, SF.StarfieldRelease.Starfield);
        var v = ReadVanilla(sf, o.StoryManager);
        var rel = SF.StarfieldRelease.Starfield;
        var modKey = ModKey.FromFileName(o.Plugin);
        var mod = new SF.StarfieldMod(modKey, rel);
        mod.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Master;
        mod.ModHeader.Author = "fo4-to-starfield QuestProbe";

        var qtyp = new SF.Keyword(new FormKey(modKey, QuestTypeId), rel) { EditorID = QuestTypeEdid, Name = QuestTypeName, Type = v.SideType.Type };
        mod.Keywords.Add(qtyp);

        var quest = new SF.Quest(new FormKey(modKey, QuestId), rel)
        {
            EditorID = QuestEdid, Name = "Quest engine probe", FormVersion = 581, Version2 = 12,
            Data = new SF.QuestData { Flags = SF.Quest.Flag.StartGameEnabled | SF.Quest.Flag.RunOnce | SF.Quest.Flag.DisplaysInHud, Priority = 50 },
        };
        quest.QuestType.SetTo(qtyp.FormKey);
        foreach (var s in Stages)
        {
            var st = new SF.QuestStage { Index = s };
            if (s == FragmentStage) st.LogEntries.Add(new SF.QuestLogEntry { Flags = 0 });   // the fragment hangs on log entry 0
            if (s == 100) st.LogEntries.Add(new SF.QuestLogEntry { Flags = SF.QuestLogEntry.Flag.CompleteQuest });
            quest.Stages.Add(st);
        }
        var obj = new SF.QuestObjective { Index = Objective, DisplayText = ObjectiveText };
        obj.Targets.Add(new SF.QuestObjectiveTarget { AliasID = TargetAlias });
        quest.Objectives.Add(obj);
        (quest.Aliases ??= new ExtendedList<SF.AQuestAlias>()).Add(new SF.QuestReferenceAlias
        {
            ID = TargetAlias, Name = "Target", Flags = SF.AQuestAlias.Flag.Optional | SF.AQuestAlias.Flag.AllowReserved,
        });

        var main = new SF.ScriptEntry { Name = ScriptName, Flags = SF.ScriptEntry.Flag.Local };
        main.Properties.Add(Obj("TargetAlias", quest.FormKey, TargetAlias));
        foreach (var (name, value) in Properties(place))
            main.Properties.Add(new SF.ScriptIntProperty { Name = name, Flags = SF.ScriptProperty.Flag.Edited, Data = (int)value });

        if (o.StoryManager)
        {
            var ev = new SF.Keyword(new FormKey(modKey, EventId), rel) { EditorID = EventEdid };
            mod.Keywords.Add(ev);
            var smq = new SF.Quest(new FormKey(modKey, SmQuestId), rel)
            {
                EditorID = SmQuestEdid, Name = "Quest engine probe (Story Manager)", FormVersion = 581, Version2 = 12, Event = ScriptEventType,
                Data = new SF.QuestData { Flags = SF.Quest.Flag.RunOnce, Priority = 50 },
            };
            smq.VirtualMachineAdapter = new SF.QuestAdapter
            {
                Version = v.Mq00Vmad.Version, ObjectFormat = v.Mq00Vmad.ObjectFormat, ExtraBindDataVersion = v.Mq00Vmad.ExtraBindDataVersion,
                Script = new SF.ScriptEntry { Name = "", Flags = SF.ScriptEntry.Flag.Local },
            };
            smq.VirtualMachineAdapter.Scripts.Add(new SF.ScriptEntry { Name = SmScript, Flags = SF.ScriptEntry.Flag.Local });
            mod.Quests.Add(smq);
            // our branch under Starfield's Script Event node, after its last child; only our keyword's events pass it
            var branch = new SF.StoryManagerBranchNode(new FormKey(modKey, BranchId), rel) { EditorID = BranchEdid };
            branch.Parent.SetTo(v.ScriptEventNode!.FormKey);
            if (v.LastChild is { } lc) branch.PreviousSibling.SetTo(lc);
            branch.Conditions.Add(new SF.ConditionFloat
            {
                CompareOperator = SF.CompareOperator.EqualTo, ComparisonValue = 1,
                Data = new SF.GetEventDataConditionData
                {
                    Function = SF.GetEventDataConditionData.EventFunction.GetIsID, Member = SF.GetEventDataConditionData.EventMember.Keyword1,
                    Record = new FormLink<SF.IStarfieldMajorRecordGetter>(ev.FormKey),
                },
            });
            mod.StoryManagerBranchNodes.Add(branch);
            var node = new SF.StoryManagerQuestNode(new FormKey(modKey, NodeId), rel) { EditorID = NodeEdid, QuestFlags = SF.StoryManagerQuestNode.QuestFlag.SharesEvent };
            node.Parent.SetTo(branch.FormKey);
            node.Quests.Add(new SF.StoryManagerQuest { Quest = new FormLinkNullable<SF.IQuestGetter>(smq.FormKey) });
            mod.StoryManagerQuestNodes.Add(node);
            main.Properties.Add(Obj("SMEvent", ev.FormKey));
            main.Properties.Add(Obj("SMQuest", smq.FormKey));
        }

        // the fragment layout copied from MQ00 (stage 10, log entry 0), the same VMAD versions
        quest.VirtualMachineAdapter = new SF.QuestAdapter
        {
            Version = v.Mq00Vmad.Version, ObjectFormat = v.Mq00Vmad.ObjectFormat, ExtraBindDataVersion = v.Mq00Vmad.ExtraBindDataVersion,
            Script = new SF.ScriptEntry { Name = FragmentScript, Flags = SF.ScriptEntry.Flag.Local },
        };
        quest.VirtualMachineAdapter.Fragments.Add(new SF.QuestScriptFragment
        {
            Stage = FragmentStage, StageIndex = 0, Unknown = v.Mq00Fragment.Unknown, Unknown2 = v.Mq00Fragment.Unknown2,
            ScriptName = FragmentScript, FragmentName = FragmentName,
        });
        quest.VirtualMachineAdapter.Scripts.Add(main);
        if (v.FragmentScriptListed) quest.VirtualMachineAdapter.Scripts.Add(new SF.ScriptEntry { Name = FragmentScript, Flags = SF.ScriptEntry.Flag.Local });
        mod.Quests.Add(quest);

        mod.ModHeader.Stats.NextFormID = NodeId + 1;
        Directory.CreateDirectory(outDir);
        var path = Path.Combine(outDir, o.Plugin);
        mod.BeginWrite.ToPath(path).WithLoadOrder(SfEsm).WithKnownMasters(new KeyedMasterStyle(SfEsm, MasterStyle.Full)).Write();
        Console.WriteLine($"wrote {path} ({new FileInfo(path).Length:N0} bytes): QUST {QuestEdid} in {o.Cell}: anchor FO4Port.esm:{place.Anchor:X6}, " +
                          $"target FO4Port.esm:{place.Target:X6} ({place.TargetBase}, {F(place.Distance)} m away); quest type {QuestTypeEdid} \"{QuestTypeName}\"; " +
                          $"fragment {FragmentScript}.{FragmentName} on stage {FragmentStage}; story manager " +
                          (o.StoryManager ? $"{BranchEdid} under {v.ScriptEventNode!.EditorID} {v.ScriptEventNode.FormKey}" : "off"));
        return 0;
    }

    // ---------------------------------------------------------------- check

    public static int Check(string pluginPath, string sfPath, string portPath, Options o)
    {
        var problems = new List<string>();
        void Need(bool ok, string what) { if (!ok) problems.Add(what); }
        var place = Resolve(portPath, o.Cell);
        using var sf = SF.StarfieldMod.CreateFromBinaryOverlay(sfPath, SF.StarfieldRelease.Starfield);
        var v = ReadVanilla(sf, o.StoryManager);
        using var plug = SF.StarfieldMod.CreateFromBinaryOverlay(pluginPath, SF.StarfieldRelease.Starfield, Full(SfEsm));
        var key = plug.ModKey;
        var masters = plug.ModHeader.MasterReferences.Select(x => x.Master.FileName.String).ToList();
        Console.WriteLine($"{key}: header {plug.ModHeader.Flags}, masters [{string.Join(", ", masters)}], {plug.Quests.Count} QUST, {plug.Keywords.Count} KYWD, " +
                          $"{plug.StoryManagerBranchNodes.Count} SMBN, {plug.StoryManagerQuestNodes.Count} SMQN");
        Console.WriteLine($"  vanilla: {QuestTypeSideEdid} type {v.SideType.Type}; {FragmentModel} VMAD v{v.Mq00Vmad.Version}/{v.Mq00Vmad.ObjectFormat}/{v.Mq00Vmad.ExtraBindDataVersion} " +
                          $"fragment {v.Mq00Fragment.ScriptName}.{v.Mq00Fragment.FragmentName} stage {v.Mq00Fragment.Stage} index {v.Mq00Fragment.StageIndex} " +
                          $"unknown {v.Mq00Fragment.Unknown}/{v.Mq00Fragment.Unknown2}, fragment script listed {v.FragmentScriptListed}" +
                          (o.StoryManager ? $"; Script Event node {v.ScriptEventNode!.EditorID} {v.ScriptEventNode.FormKey}, last child {v.LastChild?.ToString() ?? "none"}, " +
                                            $"{v.ScriptEventQuests} quests with event SCPT; example {v.EventDataExample}" : ""));
        Need(plug.ModHeader.Flags.HasFlag(SF.StarfieldModHeader.HeaderFlag.Master), "not flagged as a master");
        Need(masters.All(m => m == "Starfield.esm"), "masters other than Starfield.esm (the port is resolved at run time)");
        Need(plug.Npcs.Count == 0 && plug.Worldspaces.Count == 0 && plug.Cells.Count == 0, "the plugin carries NPC_, WRLD or CELL records (it places nothing)");
        Need(plug.Quests.Count == (o.StoryManager ? 2 : 1) && plug.Keywords.Count == (o.StoryManager ? 2 : 1) &&
             plug.StoryManagerBranchNodes.Count == (o.StoryManager ? 1 : 0) && plug.StoryManagerQuestNodes.Count == (o.StoryManager ? 1 : 0),
             $"record counts do not match a {(o.StoryManager ? "story manager" : "--no-sm")} build");
        Need(plug.EnumerateMajorRecords().All(r => r.FormKey.ModKey == key), "the plugin overrides a Starfield record (it only adds)");

        var qtyp = plug.Keywords.FirstOrDefault(k => k.FormKey == new FormKey(key, QuestTypeId));
        Need(qtyp is { EditorID: QuestTypeEdid } && qtyp.Name?.String == QuestTypeName && qtyp.Type == v.SideType.Type,
             $"KYWD {QuestTypeEdid} is not named \"{QuestTypeName}\" with {QuestTypeSideEdid}'s type {v.SideType.Type}");

        var q = plug.Quests.FirstOrDefault(x => x.FormKey == new FormKey(key, QuestId));
        if (q is null) problems.Add("no QUST 0x800");
        else
        {
            Console.WriteLine($"  QUST {q.EditorID} flags {q.Data?.Flags} stages [{string.Join(",", q.Stages.Select(s => s.Index))}] objectives " +
                              $"[{string.Join("; ", q.Objectives.Select(x => $"{x.Index} \"{x.DisplayText?.String}\" targets {string.Join(",", x.Targets.Select(t => t.AliasID))}"))}] " +
                              $"aliases [{string.Join(", ", (q.Aliases ?? new List<SF.IAQuestAliasGetter>()).OfType<SF.IQuestReferenceAliasGetter>().Select(a => $"{a.ID} {a.Name} {a.Flags}"))}]");
            Need(q.EditorID == QuestEdid && q.Data is not null && q.Data.Flags.HasFlag(SF.Quest.Flag.StartGameEnabled) && q.Data.Flags.HasFlag(SF.Quest.Flag.RunOnce),
                 $"the quest is not {QuestEdid}, start game enabled and run once");
            Need(q.QuestType.FormKey == new FormKey(key, QuestTypeId), $"the quest's type is not {QuestTypeEdid}");
            Need(q.Stages.Select(s => s.Index).SequenceEqual(Stages), "stages differ from the script's");
            Need(q.Stages.FirstOrDefault(s => s.Index == FragmentStage)?.LogEntries.Count == 1, $"stage {FragmentStage} has no log entry for its fragment");
            Need(q.Stages.LastOrDefault()?.LogEntries.Any(l => l.Flags?.HasFlag(SF.QuestLogEntry.Flag.CompleteQuest) == true) == true, "stage 100 does not complete the quest");
            Need(q.Objectives.Count == 1 && q.Objectives[0].Index == Objective && q.Objectives[0].DisplayText?.String == ObjectiveText &&
                 q.Objectives[0].Targets.Count == 1 && q.Objectives[0].Targets[0].AliasID == TargetAlias, $"objective {Objective} is not \"{ObjectiveText}\" on alias {TargetAlias}");
            var al = (q.Aliases ?? new List<SF.IAQuestAliasGetter>()).OfType<SF.IQuestReferenceAliasGetter>().ToList();
            Need(al.Count == 1 && al[0].ID == TargetAlias && al[0].Name == "Target" && al[0].Flags?.HasFlag(SF.AQuestAlias.Flag.Optional) == true &&
                 al[0].ForcedReference.IsNull, "the alias is not one empty optional Target (the script forces it)");
            var vm = q.VirtualMachineAdapter;
            var fr = vm?.Fragments.ToList() ?? new();
            Need(vm is not null && vm.Script.Name == FragmentScript && fr.Count == 1 && fr[0].Stage == FragmentStage && fr[0].StageIndex == 0 &&
                 fr[0].ScriptName == FragmentScript && fr[0].FragmentName == FragmentName && fr[0].Unknown == v.Mq00Fragment.Unknown && fr[0].Unknown2 == v.Mq00Fragment.Unknown2,
                 $"the stage {FragmentStage} fragment is not {FragmentScript}.{FragmentName} in {FragmentModel}'s layout");
            Need(vm is not null && vm.Version == v.Mq00Vmad.Version && vm.ObjectFormat == v.Mq00Vmad.ObjectFormat, $"VMAD versions differ from {FragmentModel}'s");
            var scripts = vm?.Scripts.Select(s => s.Name).ToList() ?? new();
            var want = v.FragmentScriptListed ? new[] { ScriptName, FragmentScript } : new[] { ScriptName };
            Need(scripts.SequenceEqual(want), $"scripts [{string.Join(", ", scripts)}] are not [{string.Join(", ", want)}]");
            var s = vm?.Scripts.FirstOrDefault(x => x.Name == ScriptName);
            if (s is null) problems.Add($"script {ScriptName} not attached");
            else
            {
                var props = s.Properties.ToDictionary(p => p.Name);
                Console.WriteLine($"  script {s.Name}: {props.Count} properties");
                Need(props.TryGetValue("TargetAlias", out var ta) && ta is SF.IScriptObjectPropertyGetter tao && tao.Object.FormKey == q.FormKey && tao.Alias == TargetAlias,
                     "property TargetAlias is not the quest's alias 0");
                foreach (var (name, value) in Properties(place))
                    Need(props.TryGetValue(name, out var p) && p is SF.IScriptIntPropertyGetter ip && ip.Data == (int)value, $"property {name} is not {value:X6}");
                if (o.StoryManager)
                {
                    Need(props.TryGetValue("SMEvent", out var ep) && ep is SF.IScriptObjectPropertyGetter eo && eo.Object.FormKey == new FormKey(key, EventId), "property SMEvent");
                    Need(props.TryGetValue("SMQuest", out var sp) && sp is SF.IScriptObjectPropertyGetter so && so.Object.FormKey == new FormKey(key, SmQuestId), "property SMQuest");
                }
                Need(props.Count == Properties(place).Count + 1 + (o.StoryManager ? 2 : 0), $"{props.Count} properties on {ScriptName}");
            }
        }
        if (o.StoryManager)
        {
            var smq = plug.Quests.FirstOrDefault(x => x.FormKey == new FormKey(key, SmQuestId));
            Need(smq is { EditorID: SmQuestEdid } && smq.Event == ScriptEventType && smq.Data?.Flags.HasFlag(SF.Quest.Flag.StartGameEnabled) == false &&
                 smq.VirtualMachineAdapter?.Scripts.Select(x => x.Name).SequenceEqual(new[] { SmScript }) == true,
                 $"QUST {SmQuestEdid} is not a script-event quest (not start game enabled) carrying {SmScript}");
            var br = plug.StoryManagerBranchNodes.FirstOrDefault();
            var c = br?.Conditions.Count == 1 ? br.Conditions[0] : null;
            Need(br is { EditorID: BranchEdid } && br.Parent.FormKey == v.ScriptEventNode!.FormKey &&
                 (v.LastChild is { } lc ? br.PreviousSibling.FormKey == lc : br.PreviousSibling.IsNull) &&
                 c is SF.IConditionFloatGetter cf && cf.ComparisonValue == 1 && cf.CompareOperator == SF.CompareOperator.EqualTo &&
                 c.Data is SF.IGetEventDataConditionDataGetter ge && ge.Function == SF.GetEventDataConditionData.EventFunction.GetIsID &&
                 ge.Member == SF.GetEventDataConditionData.EventMember.Keyword1 && ge.Record.FormKey == new FormKey(key, EventId),
                 $"SMBN {BranchEdid} is not under the Script Event node after its last child, gated on {EventEdid}");
            var nd = plug.StoryManagerQuestNodes.FirstOrDefault();
            Need(nd is { EditorID: NodeEdid } && nd.Parent.FormKey == br?.FormKey && nd.QuestFlags.HasFlag(SF.StoryManagerQuestNode.QuestFlag.SharesEvent) &&
                 nd.Quests.Count == 1 && nd.Quests[0].Quest.FormKey == new FormKey(key, SmQuestId),
                 $"SMQN {NodeEdid} is not under {BranchEdid}, sharing the event, starting {SmQuestEdid}");
        }
        Console.WriteLine($"  {o.Cell}: anchor FO4Port.esm:{place.Anchor:X6}, target FO4Port.esm:{place.Target:X6} {place.TargetBase} at {F(place.Distance)} m");
        foreach (var p in problems) Console.WriteLine("FAIL  " + p);
        Console.WriteLine(problems.Count == 0 ? "all checks pass" : $"{problems.Count} problem(s)");
        return problems.Count == 0 ? 0 : 1;
    }

    // ---------------------------------------------------------------- selftest (synthetic masters only)

    public static int SelfTest(string dir)
    {
        Directory.CreateDirectory(dir);
        var rel = SF.StarfieldRelease.Starfield;
        // a stand-in Starfield.esm: the quest type, MQ00 with a stage-10 fragment, the Script Event node with two children
        var sf = new SF.StarfieldMod(SfEsm, rel);
        sf.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Master;
        sf.Keywords.Add(new SF.Keyword(new FormKey(SfEsm, QuestTypeSideId), rel) { EditorID = QuestTypeSideEdid, Type = SF.Keyword.TypeEnum.Quest });
        sf.Keywords.Add(new SF.Keyword(new FormKey(SfEsm, 0x905), rel) { EditorID = "SomeEventKeyword" });
        var mq00 = new SF.Quest(new FormKey(SfEsm, 0x901), rel) { EditorID = FragmentModel };
        mq00.VirtualMachineAdapter = new SF.QuestAdapter { Version = 6, ObjectFormat = 2, ExtraBindDataVersion = 3, Script = new SF.ScriptEntry { Name = "Fragments:Quests:QF_MQ00_00000901" } };
        mq00.VirtualMachineAdapter.Fragments.Add(new SF.QuestScriptFragment { Stage = 10, StageIndex = 0, Unknown = 0, Unknown2 = 1, ScriptName = "Fragments:Quests:QF_MQ00_00000901", FragmentName = "Fragment_Stage_0010_Item_00" });
        mq00.VirtualMachineAdapter.Scripts.Add(new SF.ScriptEntry { Name = "Fragments:Quests:QF_MQ00_00000901" });
        sf.Quests.Add(mq00);
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x906), rel) { EditorID = "SomeScriptEventQuest", Event = ScriptEventType });
        sf.Statics.Add(new SF.Static(new FormKey(SfEsm, CocMarkerId), rel) { EditorID = "COCMarkerHeading" });
        var smen = new SF.StoryManagerEventNode(new FormKey(SfEsm, 0x902), rel) { EditorID = "SMScriptEvent", Type = SF.StoryManagerEventNode.Types.ScriptEvent };
        sf.StoryManagerEventNodes.Add(smen);
        sf.StoryManagerEventNodes.Add(new SF.StoryManagerEventNode(new FormKey(SfEsm, 0x907), rel) { EditorID = "SMLocationLoaded", Type = SF.StoryManagerEventNode.Types.LocationLoaded });
        var c1 = new SF.StoryManagerBranchNode(new FormKey(SfEsm, 0x903), rel) { EditorID = "VanillaBranch1" };
        c1.Parent.SetTo(smen.FormKey);
        c1.Conditions.Add(new SF.ConditionFloat { ComparisonValue = 1, Data = new SF.GetEventDataConditionData
            { Function = SF.GetEventDataConditionData.EventFunction.GetIsID, Member = SF.GetEventDataConditionData.EventMember.Keyword1, Record = new FormLink<SF.IStarfieldMajorRecordGetter>(new FormKey(SfEsm, 0x905)) } });
        var c2 = new SF.StoryManagerBranchNode(new FormKey(SfEsm, 0x904), rel) { EditorID = "VanillaBranch2" };
        c2.Parent.SetTo(smen.FormKey);
        c2.PreviousSibling.SetTo(c1.FormKey);
        sf.StoryManagerBranchNodes.Add(c1);
        sf.StoryManagerBranchNodes.Add(c2);
        sf.ModHeader.Stats.NextFormID = 0x908;
        var sfPath = Path.Combine(dir, "Starfield.esm");
        sf.BeginWrite.ToPath(sfPath).WithNoLoadOrder().NoCheckIfLowerRangeDisallowed().Write();
        // a port with the library: its COC marker, a near and a far load door, and a plain object farther still
        var portKey = ModKey.FromFileName("FO4Port.esm");
        var port = new SF.StarfieldMod(portKey, rel);
        port.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Master;
        var pdoor = new SF.Door(new FormKey(portKey, 0x810), rel) { EditorID = "FO4Port_LibraryDoor" };
        port.Doors.Add(pdoor);
        var cell = new SF.Cell(new FormKey(portKey, 0x800), rel) { EditorID = DefaultCell, Flags = SF.Cell.Flag.IsInteriorCell };
        SF.PlacedObject R(uint id, FormKey b, float x) => new(new FormKey(portKey, id), rel) { Base = new FormLinkNullable<SF.IPlaceableObjectGetter>(b), Position = new P3Float(x, 0, 0) };
        cell.Temporary.Add(R(0x801, new FormKey(SfEsm, CocMarkerId), 0));
        var near = R(0x802, pdoor.FormKey, 5);
        near.TeleportDestination = new SF.TeleportDestination { Door = new FormLink<SF.IPlacedObjectGetter>(new FormKey(portKey, 0x880)) };
        var far = R(0x803, pdoor.FormKey, 40);
        far.TeleportDestination = new SF.TeleportDestination { Door = new FormLink<SF.IPlacedObjectGetter>(new FormKey(portKey, 0x881)) };
        cell.Persistent.Add(near);
        cell.Persistent.Add(far);
        cell.Temporary.Add(R(0x804, pdoor.FormKey, 90));   // a door with no teleport is not a target
        // cells with no load door (the installed library, PC 19 Oct): the farthest door on the marker's floor and in
        // reach, else the farthest object there; never one a floor up, out of reach, or next to the marker
        var pstat = new SF.Static(new FormKey(portKey, 0x811), rel) { EditorID = "FO4Port_Shelf" };
        port.Statics.Add(pstat);
        SF.PlacedObject Rz(uint id, FormKey b, float x, float z) { var r = R(id, b, x); r.Position = new P3Float(x, 0, z); return r; }
        var noLoad = new SF.Cell(new FormKey(portKey, 0x820), rel) { EditorID = "FO4Port_NoLoadDoors", Flags = SF.Cell.Flag.IsInteriorCell };
        noLoad.Temporary.Add(Rz(0x821, new FormKey(SfEsm, CocMarkerId), 0, 0));
        noLoad.Temporary.Add(Rz(0x822, pstat.FormKey, 50, 1));
        noLoad.Temporary.Add(Rz(0x823, pdoor.FormKey, 30, 0));
        noLoad.Temporary.Add(Rz(0x824, pdoor.FormKey, 45, 10));
        noLoad.Temporary.Add(Rz(0x825, pdoor.FormKey, 100, 0));
        var statsOnly = new SF.Cell(new FormKey(portKey, 0x830), rel) { EditorID = "FO4Port_ObjectsOnly", Flags = SF.Cell.Flag.IsInteriorCell };
        statsOnly.Temporary.Add(Rz(0x831, new FormKey(SfEsm, CocMarkerId), 0, 0));
        statsOnly.Temporary.Add(Rz(0x832, pstat.FormKey, 5, 0));
        statsOnly.Temporary.Add(Rz(0x833, pstat.FormKey, 25, -2));
        statsOnly.Temporary.Add(Rz(0x834, pstat.FormKey, 70, 0));
        var empty = new SF.Cell(new FormKey(portKey, 0x840), rel) { EditorID = "FO4Port_Bare", Flags = SF.Cell.Flag.IsInteriorCell };
        empty.Temporary.Add(Rz(0x841, new FormKey(SfEsm, CocMarkerId), 0, 0));
        empty.Temporary.Add(Rz(0x842, pstat.FormKey, 3, 0));
        var pb = new SF.CellBlock { BlockNumber = 0, GroupType = SF.GroupTypeEnum.InteriorCellBlock };
        var ps = new SF.CellSubBlock { BlockNumber = 0, GroupType = SF.GroupTypeEnum.InteriorCellSubBlock };
        ps.Cells.Add(cell);
        ps.Cells.Add(noLoad);
        ps.Cells.Add(statsOnly);
        ps.Cells.Add(empty);
        pb.SubBlocks.Add(ps);
        port.Cells.Records.Add(pb);
        port.ModHeader.Stats.NextFormID = 0x850;
        var portPath = Path.Combine(dir, portKey.FileName);
        port.BeginWrite.ToPath(portPath).WithLoadOrder(SfEsm).WithKnownMasters(new KeyedMasterStyle(SfEsm, MasterStyle.Full)).Write();

        var place = Resolve(portPath, DefaultCell);
        if (place.Anchor != 0x801 || place.Target != 0x803 || MathF.Abs(place.Distance - 40) > 1e-3) { Console.WriteLine($"FAIL  resolve {place}"); return 1; }
        foreach (var (c, want) in new[] { ("FO4Port_NoLoadDoors", 0x823u), ("FO4Port_ObjectsOnly", 0x833u) })
            if (Resolve(portPath, c).Target != want) { Console.WriteLine($"FAIL  resolve {c}: {Resolve(portPath, c)}"); return 1; }
        try { Resolve(portPath, "FO4Port_Bare"); Console.WriteLine("FAIL  resolve accepted a cell with nothing in reach"); return 1; }
        catch (Refusal) { }

        var outDir = Path.Combine(dir, "out");
        var plain = Options.From(Array.Empty<string>());
        var nosm = plain with { StoryManager = false };
        foreach (var (name, o) in new[] { ("default", plain), ("nosm", nosm) })
        {
            var od = Path.Combine(outDir, name);
            int rc = Write(sfPath, portPath, od, o);
            if (rc == 0) rc = Check(Path.Combine(od, Plugin), sfPath, portPath, o);
            if (rc != 0) return rc;
        }
        foreach (var (build, o, why) in new[] { ("default", nosm, "a story manager build as a --no-sm one"), ("nosm", plain, "a --no-sm build as a story manager one") })
        {
            if (Check(Path.Combine(outDir, build, Plugin), sfPath, portPath, o) == 0) { Console.WriteLine($"FAIL  check passed {why}"); return 1; }
            Console.WriteLine($"rejected: {why}");
        }
        var good = Path.Combine(outDir, "default", Plugin);
        SF.Quest Main(SF.StarfieldMod m) => m.Quests.First(x => x.FormKey.ID == QuestId);
        var mutations = new (string Name, Action<SF.StarfieldMod> Edit)[]
        {
            ("not start game enabled", m => Main(m).Data!.Flags &= ~SF.Quest.Flag.StartGameEnabled),
            ("the fragment renamed", m => Main(m).VirtualMachineAdapter!.Fragments[0].FragmentName = "Fragment_Stage_0020_Item_00"),
            ("the fragment on another stage", m => Main(m).VirtualMachineAdapter!.Fragments[0].Stage = 20),
            ("the fragment layout changed", m => Main(m).VirtualMachineAdapter!.Fragments[0].Unknown2 = 0),
            ("the fragment script not listed", m => Main(m).VirtualMachineAdapter!.Scripts.RemoveAll(s => s.Name == FragmentScript)),
            ("the objective has no target", m => Main(m).Objectives[0].Targets.Clear()),
            ("the alias forced", m => ((SF.QuestReferenceAlias)Main(m).Aliases![0]).ForcedReference.SetTo(new FormKey(SfEsm, 0x902))),
            ("the target id changed", m => ((SF.ScriptIntProperty)Main(m).VirtualMachineAdapter!.Scripts[0].Properties.First(p => p.Name == "TargetId")).Data = 0x802),
            ("the quest type is Starfield's", m => Main(m).QuestType.SetTo(new FormKey(SfEsm, QuestTypeSideId))),
            ("the branch under another node", m => m.StoryManagerBranchNodes.First().Parent.SetTo(new FormKey(SfEsm, 0x907))),
            ("the branch first instead of last", m => m.StoryManagerBranchNodes.First().PreviousSibling.Clear()),
            ("the branch ungated", m => m.StoryManagerBranchNodes.First().Conditions.Clear()),
            ("the node consumes the event", m => m.StoryManagerQuestNodes.First().QuestFlags = 0),
            ("the SM quest start game enabled", m => m.Quests.First(x => x.FormKey.ID == SmQuestId).Data!.Flags |= SF.Quest.Flag.StartGameEnabled),
        };
        foreach (var (name, edit) in mutations)
        {
            var mod = SF.StarfieldMod.CreateFromBinary(good, rel, Full(SfEsm));
            edit(mod);
            var md = Path.Combine(outDir, "mutated");
            Directory.CreateDirectory(md);
            mod.BeginWrite.ToPath(Path.Combine(md, Plugin)).WithLoadOrder(SfEsm).WithKnownMasters(new KeyedMasterStyle(SfEsm, MasterStyle.Full)).Write();
            if (Check(Path.Combine(md, Plugin), sfPath, portPath, plain) == 0) { Console.WriteLine($"FAIL  check passed a mutation: {name}"); return 1; }
            Console.WriteLine($"mutation rejected: {name}");
        }
        try { Write(sfPath, portPath, Path.Combine(outDir, "refused"), plain with { Cell = "FO4Port_NoSuchCell" }); Console.WriteLine("FAIL  write accepted an unknown cell"); return 1; }
        catch (Refusal e) { Console.WriteLine($"refused as expected (an unknown cell): {e.Message}"); }
        Console.WriteLine("selftest pass");
        return 0;
    }
}
