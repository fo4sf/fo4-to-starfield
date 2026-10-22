// NewGame records: the read-only PC record reader for the open record questions of research/framework/newgame.md
// sections K and N (one PC run settles them). Claude's project.
//
//   records <Fallout 4 Data dir> --out <report.txt> [--sf-data <Starfield Data dir>] [--port <FO4Port.esm>] [--nearest <n>]
//        opens <sf-data>\Starfield.esm, <Fallout 4 Data>\Fallout4.esm and the installed <sf-data>\FO4Port.esm (or --port)
//        read-only and writes one plain-text report, --out, with these sections:
//          NG-K1  MQ102 (Fallout4.esm 0001CC2A): every stage with its flags, log entries (flags, text, conditions) and
//                 script fragments, and which stage completes the quest (a log entry flagged CompleteQuest)
//          NG-K2  MQ101 (Fallout4.esm): stages 710 to 1000, the same detail
//          NG-K4  every reference in the port's Vault 111 cells (EditorID FO4Port_Vault111*) whose base record's EditorID
//                 mentions PipBoy, with cell, base and position
//          NG-K9  the conditions on Codsworth's, Dogmeat's and Min00's records (quests, dialogue, scenes, packages named
//                 for them, and MQ102's aliases named for them) that reference MQ102
//          NG-N4  Starfield's MQ101 stage 0: its log entries' conditions and fragments; MQ00's conditions; the record
//                 002EEA4D (SustenanceAllowed) and every record whose EditorID mentions StartupQuest
//          anchor the persistent references of FO4Port_Vault111Cryo nearest the player's pod (the anchor and terminal
//                 picks), and every terminal in the cell
//        A missing plugin or record is reported in its section, never fatal; the exit code is 0 once the report is
//        written. Nothing but --out is written.
//   records-selftest <scratch dir>
//        synthetic Fallout4.esm, Starfield.esm and port covering each section; the report is checked. The main selftest
//        runs it too.
using System.Collections;
using System.Globalization;
using System.Reflection;
using Mutagen.Bethesda;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Strings;
using Noggog;
using F4 = Mutagen.Bethesda.Fallout4;
using SF = Mutagen.Bethesda.Starfield;

static class NewGameRecords
{
    public const string DefaultSfData = @"D:\SteamLibrary\steamapps\common\Starfield\Data";
    public const string Fo4Esm = "Fallout4.esm", SfEsmName = "Starfield.esm", PortEsm = "FO4Port.esm";
    public const uint SustenanceId = 0x2EEA4D;                 // Starfield.esm 002EEA4D, SustenanceAllowed (NG-M1, NG-N4)
    public const string StartupQuestTerm = "StartupQuest", PipBoyTerm = "PipBoy", VaultCellPrefix = "FO4Port_Vault111";
    public const ushort K2From = 710, K2To = 1000;
    public static readonly string[] K9Names = { "Codsworth", "Dogmeat", "Min00" };
    public const int DefaultNearest = 30;
    static readonly ModKey SfEsm = ModKey.FromFileName(SfEsmName);
    static string F(float v) => v.ToString("0.###", CultureInfo.InvariantCulture);

    public record Inputs(string? Fo4, string? Sf, string? Port, int Nearest = DefaultNearest);

    /// The CLI: the Fallout 4 Data folder is the argument, Starfield's defaults to the owner's install.
    public static int Run(string fo4Data, string? outPath, string? sfData, string? port, int nearest)
    {
        if (outPath is null) throw new NewGame.Refusal("records needs --out <report.txt>");
        sfData ??= DefaultSfData;
        var inputs = new Inputs(Path.Combine(fo4Data, Fo4Esm), Path.Combine(sfData, SfEsmName), port ?? Path.Combine(sfData, PortEsm), nearest);
        var text = Report(inputs);
        Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(outPath))!);
        File.WriteAllText(outPath, text);
        Console.WriteLine($"records ok: {text.Split('\n').Length} lines, {Sections(text).Count(s => s.Contains("\nmissing: "))} section(s) with a missing input; report {outPath}");
        return 0;
    }

    static IEnumerable<string> Sections(string text) => text.Split("\n===== ").Skip(1);

    // ---------------------------------------------------------------- the report

    public static string Report(Inputs ins)
    {
        var o = new Out();
        o.Line($"newgame records: {DateTime.UtcNow:yyyy-MM-dd HH:mm} UTC; Fallout4.esm {ins.Fo4 ?? "(none)"}; Starfield.esm {ins.Sf ?? "(none)"}; port {ins.Port ?? "(none)"}");
        o.Line("Every section names the newgame.md question it answers. Positions are in metres, the port's frame (Fallout 4's pod position / 70).");
        using var fo4Mod = Open(ins.Fo4, p => F4.Fallout4Mod.CreateFromBinaryOverlay(p, F4.Fallout4Release.Fallout4), o, "Fallout4.esm");
        using var sfMod = Open(ins.Sf, p => SF.StarfieldMod.CreateFromBinaryOverlay(p, SF.StarfieldRelease.Starfield), o, "Starfield.esm");
        using var portMod = Open(ins.Port, p => SF.StarfieldMod.CreateFromBinaryOverlay(p, SF.StarfieldRelease.Starfield, NewGame.Full(SfEsm)), o, "FO4Port.esm");
        var fo4 = fo4Mod as F4.IFallout4ModGetter;
        var sf = sfMod as SF.IStarfieldModGetter;
        var port = portMod as SF.IStarfieldModGetter;
        // the name indexes are one pass over every record of each plugin: a record Mutagen cannot parse must not
        // take the whole report down, so a failed pass leaves an index that names by id alone, and says so
        var f4Names = Index(fo4, null, o, "Fallout4.esm");
        var sfNames = Index(sf, null, o, "Starfield.esm");
        var portNames = Index(port, sfNames, o, "FO4Port.esm");

        o.Section("NG-K1 MQ102 (Fallout4.esm): the full stage table and which stage completes it", () =>
        {
            if (fo4 is null) { o.Line("missing: Fallout4.esm"); return; }
            var q = fo4.Quests.FirstOrDefault(x => x.FormKey.ID == NewGame.Fo4MQ102) ?? fo4.Quests.FirstOrDefault(x => x.EditorID == "MQ102");
            if (q is null) { o.Line($"missing: QUST MQ102 ({NewGame.Fo4MQ102:X8}) is not in Fallout4.esm"); return; }
            Quest(o, q, f4Names!, null, null);
        });
        o.Section($"NG-K2 MQ101 (Fallout4.esm): stages {K2From} to {K2To}", () =>
        {
            if (fo4 is null) { o.Line("missing: Fallout4.esm"); return; }
            var q = fo4.Quests.FirstOrDefault(x => x.EditorID == "MQ101");
            if (q is null) { o.Line("missing: QUST MQ101 is not in Fallout4.esm"); return; }
            Quest(o, q, f4Names!, K2From, K2To);
        });
        o.Section($"NG-K4 the port's Vault 111 cells ({VaultCellPrefix}*): references whose base EditorID mentions {PipBoyTerm}", () =>
        {
            if (port is null) { o.Line("missing: FO4Port.esm"); return; }
            int cells = 0, refs = 0, hits = 0;
            foreach (var cell in port.EnumerateMajorRecords<SF.ICellGetter>().Where(c => c.EditorID?.StartsWith(VaultCellPrefix, StringComparison.OrdinalIgnoreCase) == true))
            {
                cells++;
                foreach (var r in cell.Persistent.Concat(cell.Temporary))
                {
                    refs++;
                    var (baseKey, pos) = Placed(r);
                    var baseName = portNames!.Of(baseKey);
                    if (!baseName.Contains(PipBoyTerm, StringComparison.OrdinalIgnoreCase)) continue;
                    hits++;
                    o.Line($"  {cell.EditorID} {cell.FormKey}: REFR {r.FormKey} {r.EditorID ?? ""} base {baseName} at {Pos(pos)} m{(Persistent(r) ? " persistent" : "")}");
                }
            }
            o.Line($"{cells} Vault 111 cell(s), {refs} reference(s), {hits} with a {PipBoyTerm} base{(hits == 0 ? ": none (no Pip-Boy prop in the converted vault, or its base is named otherwise)" : "")}");
        });
        o.Section($"NG-K9 the conditions on {string.Join(", ", K9Names)} records that reference MQ102", () =>
        {
            if (fo4 is null) { o.Line("missing: Fallout4.esm"); return; }
            K9(o, fo4, f4Names!);
        });
        o.Section("NG-N4 Starfield.esm: MQ101 stage 0, MQ00's conditions, 002EEA4D (SustenanceAllowed), StartupQuest records", () =>
        {
            if (sf is null) { o.Line("missing: Starfield.esm"); return; }
            var mq101 = sf.Quests.FirstOrDefault(x => x.EditorID == "MQ101");
            if (mq101 is null) o.Line("missing: QUST MQ101 is not in Starfield.esm");
            else { o.Line($"MQ101 {mq101.FormKey} \"{mq101.Name?.String}\" flags {mq101.Data?.Flags}: stage 0 only (stage 9000 is in the scripts, start_read.py)"); Quest(o, mq101, sfNames!, 0, 0, header: false); }
            var mq00 = sf.Quests.FirstOrDefault(x => x.EditorID == "MQ00");
            if (mq00 is null) o.Line("missing: QUST MQ00 is not in Starfield.esm");
            else Quest(o, mq00, sfNames!, null, null);
            var sus = sfNames!.Record(new FormKey(SfEsm, SustenanceId));
            if (sus is null) o.Line($"missing: {SfEsm}:{SustenanceId:X6} is not in Starfield.esm");
            else RecordDetail(o, sus, sfNames);
            var startup = sfNames.Containing(StartupQuestTerm).ToList();
            o.Line($"{startup.Count} record(s) whose EditorID mentions {StartupQuestTerm}{(startup.Count == 0 ? " (none: the name may be a script property, not a record)" : "")}");
            foreach (var r in startup) RecordDetail(o, r, sfNames);
        });
        o.Section($"anchor: the persistent references of {NewGame.VaultCell} nearest the player's pod, and the cell's terminals", () =>
        {
            if (port is null) { o.Line("missing: FO4Port.esm"); return; }
            var cell = port.EnumerateMajorRecords<SF.ICellGetter>().FirstOrDefault(c => c.EditorID == NewGame.VaultCell);
            if (cell is null) { o.Line($"missing: the port has no cell {NewGame.VaultCell}"); return; }
            var all = cell.Persistent.Concat(cell.Temporary).ToList();
            // the origin: FO4's player pod / 70 (the port's frame), else the COC marker
            P3Float origin; string from;
            var f4Cell = fo4?.EnumerateMajorRecords<F4.ICellGetter>().FirstOrDefault(c => c.FormKey.ID == NewGame.Fo4VaultCell);
            var pods = f4Cell?.Temporary.Concat(f4Cell.Persistent).OfType<F4.IPlacedObjectGetter>().Where(r => NewGame.IsPlayerPod(r.EditorID)).ToList() ?? new();
            var coc = all.OfType<SF.IPlacedObjectGetter>().FirstOrDefault(r => r.Base.FormKey == new FormKey(SfEsm, NewGame.CocMarkerId));
            if (pods.Count > 0)
            {
                var p = pods[0].Position;
                origin = new P3Float(p.X / NewGame.Units, p.Y / NewGame.Units, p.Z / NewGame.Units);
                from = $"FO4 {pods[0].FormKey.ID:X8} {pods[0].EditorID} / 70{(pods.Count > 1 ? $" (first of {pods.Count} candidates: {string.Join(", ", pods.Select(x => x.EditorID))})" : "")}";
            }
            else if (coc is not null) { origin = coc.Position; from = fo4 is null ? "the cell's COC marker (Fallout4.esm missing)" : "the cell's COC marker (no player pod found in Fallout4.esm)"; }
            else { o.Line("missing: neither a player pod in Fallout4.esm nor a COC marker in the cell to measure from"); return; }
            o.Line($"origin {Pos(origin)} m: {from}; COC marker {(coc is null ? "none" : $"{coc.FormKey} at {Pos(coc.Position)} m{(Persistent(coc) ? " persistent" : " temporary")}")}");
            float D(IMajorRecordGetter r) { var (_, p) = Placed(r); return MathF.Sqrt(MathF.Pow(p.X - origin.X, 2) + MathF.Pow(p.Y - origin.Y, 2) + MathF.Pow(p.Z - origin.Z, 2)); }
            var pers = all.Where(Persistent).OrderBy(D).ThenBy(r => r.FormKey.ID).ToList();
            o.Line($"{pers.Count} persistent reference(s) of {all.Count}; nearest {Math.Min(ins.Nearest, pers.Count)}:");
            foreach (var r in pers.Take(ins.Nearest))
            {
                var (baseKey, pos) = Placed(r);
                o.Line($"  {r.FormKey}{(r.FormKey.ModKey == port.ModKey ? "" : " (not the port's own record)")} {r.EditorID ?? ""} base {portNames!.Of(baseKey)} at {Pos(pos)} m, {F(D(r))} m away");
            }
            var terms = all.Where(r => portNames!.TypeOf(Placed(r).Base) == "Terminal").OrderBy(D).ToList();
            o.Line($"{terms.Count} terminal reference(s) in the cell{(terms.Count == 0 ? " (the SPECIAL prompt then watches points' spot)" : "")}:");
            foreach (var r in terms)
            {
                var (baseKey, pos) = Placed(r);
                o.Line($"  {r.FormKey} {r.EditorID ?? ""} base {portNames!.Of(baseKey)} at {Pos(pos)} m, {F(D(r))} m away{(Persistent(r) ? ", persistent" : ", temporary")}");
            }
        });
        return o.Text();
    }

    static Names? Index(IModGetter? mod, Names? fallback, Out o, string what)
    {
        if (mod is null) return null;
        try { return new Names(mod, fallback); }
        catch (Exception e)
        {
            o.Line($"ERROR indexing {what}'s records (links print as ids; the sections still run): {e.GetType().Name}: {e.Message}");
            return new Names(fallback);
        }
    }

    static IDisposable? Open(string? path, Func<string, IModDisposeGetter> open, Out o, string what)
    {
        if (path is null || !File.Exists(path)) { o.Line($"missing: {what} {(path is null ? "(no path)" : path)}"); return null; }
        try { var m = open(path); o.Line($"opened {what}: {path} ({new FileInfo(path).Length:N0} bytes, {m.ModKey})"); return m; }
        catch (Exception e) { o.Line($"missing: {what} {path} could not be read: {e.GetType().Name}: {e.Message}"); return null; }
    }

    static bool Persistent(IMajorRecordGetter r) => (r.MajorRecordFlagsRaw & 0x400) != 0;
    static string Pos(P3Float p) => $"({F(p.X)}, {F(p.Y)}, {F(p.Z)})";

    /// A placed record's base and position (objects and actors of either game; anything else has none).
    static (FormKey Base, P3Float Pos) Placed(IMajorRecordGetter r) => r switch
    {
        SF.IPlacedObjectGetter o => (o.Base.FormKey, o.Position),
        SF.IPlacedNpcGetter n => (n.Base.FormKey, n.Position),
        F4.IPlacedObjectGetter o => (o.Base.FormKey, o.Position),
        F4.IPlacedNpcGetter n => (n.Base.FormKey, n.Position),
        _ => (FormKey.Null, default),
    };

    // ---------------------------------------------------------------- quests and conditions, both games

    /// A quest's stages (all, or From..To) with flags, log entries, conditions and fragments, after its own conditions.
    static void Quest(Out o, IMajorRecordGetter q, Names names, ushort? from, ushort? to, bool header = true)
    {
        var qd = new Q(q);
        if (header) o.Line($"{qd.Type} {q.EditorID} {q.FormKey} \"{qd.Name}\" flags {qd.Flags}: {qd.Stages.Count} stage(s) [{string.Join(",", qd.Stages.Select(s => s.Index))}], {qd.Aliases.Count} alias(es), {qd.Fragments.Count} fragment(s)");
        foreach (var (where, conds) in ConditionLists(q, "quest"))
            if (conds.Count > 0) { o.Line($"  {where}: {conds.Count} condition(s)"); foreach (var c in conds) o.Line("    " + Condition(c, names)); }
        if (from is null) foreach (var a in qd.Aliases) Alias(o, a, names, "  ");
        var completes = new List<ushort>();
        foreach (var s in qd.Stages)
        {
            if (from is { } lo && (s.Index < lo || s.Index > to)) continue;
            var frags = qd.Fragments.Where(f => f.Stage == s.Index).Select(f => $"{f.ScriptName}.{f.FragmentName}").ToList();
            o.Line($"  stage {s.Index}{(s.Flags is { Length: > 0 } ? $" [{s.Flags}]" : "")}: {s.Entries.Count} log entr{(s.Entries.Count == 1 ? "y" : "ies")}{(frags.Count > 0 ? $"; fragments {string.Join(", ", frags)}" : "")}");
            for (int i = 0; i < s.Entries.Count; i++)
            {
                var e = s.Entries[i];
                if (e.Complete) completes.Add(s.Index);
                o.Line($"    log {i}{(e.Flags is { Length: > 0 } ? $" [{e.Flags}]" : "")}{(string.IsNullOrEmpty(e.Text) ? "" : $" \"{e.Text}\"")}{(e.Conditions.Count == 0 ? "" : $": {e.Conditions.Count} condition(s)")}");
                foreach (var c in e.Conditions) o.Line("      " + Condition(c, names));
            }
        }
        if (from is null)
            o.Line(completes.Count > 0 ? $"  completes: stage {string.Join(", ", completes.Distinct())} (log entry flagged CompleteQuest)"
                                       : "  completes: no log entry is flagged CompleteQuest (completion is scripted, if anywhere: see the fragments)");
    }

    static void Alias(Out o, object a, Names names, string indent)
    {
        var id = Prop(a, "ID"); var name = Prop(a, "Name"); var flags = Prop(a, "Flags")?.ToString();
        var lists = ConditionLists(a, "alias").Where(l => l.Conds.Count > 0).ToList();
        o.Line($"{indent}alias {id} {name}{(flags is null || flags == "0" ? "" : $" [{flags}]")}: {lists.Sum(l => l.Conds.Count)} condition(s)");
        foreach (var (_, conds) in lists) foreach (var c in conds) o.Line(indent + "  " + Condition(c, names));
    }

    /// The uniform view of either game's quest getter, by reflection (the two Mutagen types share their shape).
    sealed class Q
    {
        public readonly string Type, Name, Flags;
        public readonly List<object> Aliases;
        public readonly List<(ushort Stage, string ScriptName, string FragmentName)> Fragments = new();
        public readonly List<(ushort Index, string Flags, List<(string Flags, string Text, bool Complete, IReadOnlyList<object> Conditions)> Entries)> Stages = new();
        public Q(IMajorRecordGetter q)
        {
            Type = q.GetType().Name.Replace("BinaryOverlay", "");
            Name = (Prop(q, "Name") as ITranslatedStringGetter)?.String ?? "";
            Flags = Prop(Prop(q, "Data"), "Flags")?.ToString() is { } qf && qf != "0" ? qf : "none";
            Aliases = (Prop(q, "Aliases") as IEnumerable)?.Cast<object>().ToList() ?? new();
            if (Prop(Prop(q, "VirtualMachineAdapter"), "Fragments") is IEnumerable fr)
                foreach (var f in fr) Fragments.Add(((ushort)Prop(f, "Stage")!, Prop(f, "ScriptName")?.ToString() ?? "", Prop(f, "FragmentName")?.ToString() ?? ""));
            foreach (var s in (IEnumerable)Prop(q, "Stages")!)
            {
                var entries = new List<(string, string, bool, IReadOnlyList<object>)>();
                foreach (var e in (IEnumerable)Prop(s, "LogEntries")!)
                {
                    var fl = Prop(e, "Flags")?.ToString() is { } ef && ef != "0" ? ef : "";
                    entries.Add((fl, (Prop(e, "Entry") as ITranslatedStringGetter)?.String ?? "", fl.Contains("CompleteQuest"), ((IEnumerable)Prop(e, "Conditions")!).Cast<object>().ToList()));
                }
                Stages.Add(((ushort)Prop(s, "Index")!, Prop(s, "Flags")?.ToString() is { } sf && sf != "0" ? sf : "", entries));
            }
        }
    }

    /// A property by name, on the class or any interface it implements (an overlay class can hide a member under
    /// the same name, which makes the class lookup ambiguous: then the interface lookup decides).
    static object? Prop(object? o, string name)
    {
        if (o is null) return null;
        try { if (o.GetType().GetProperty(name) is { } p && p.GetIndexParameters().Length == 0 && p.GetValue(o) is { } v) return v; }
        catch (AmbiguousMatchException) { }
        return Getter(o, name);
    }
    static object? Getter(object? o, string name)
    {
        if (o is null) return null;
        foreach (var i in o.GetType().GetInterfaces()) if (i.GetProperty(name) is { } p) return p.GetValue(o);
        return null;
    }

    /// Every list of conditions a record or sub-record carries at its top level (DialogConditions, Conditions,
    /// StartConditions...), by property name, for either game.
    static IEnumerable<(string Where, IReadOnlyList<object> Conds)> ConditionLists(object o, string what)
    {
        var seen = new HashSet<string>();
        foreach (var i in o.GetType().GetInterfaces().Where(i => i.Name.EndsWith("Getter")))
            foreach (var p in i.GetProperties())
            {
                if (!seen.Add(p.Name) || p.GetIndexParameters().Length > 0) continue;
                var t = p.PropertyType;
                if (!t.IsGenericType || !typeof(IEnumerable).IsAssignableFrom(t)) continue;
                var arg = t.GetGenericArguments().LastOrDefault();
                if (arg is null || !(arg == typeof(F4.IConditionGetter) || arg == typeof(SF.IConditionGetter))) continue;
                if (p.GetValue(o) is IEnumerable list) yield return ($"{what} {p.Name}", list.Cast<object>().ToList());
            }
    }

    /// One condition as text: [flags] Function(parameters) on <RunOnType> <Reference> <op> <value>. Starfield's data
    /// is typed per function (FirstParameter, SecondParameter...). Fallout 4's is one shape whose parameter slots are
    /// unions (ParameterOneRecord and ParameterOneNumber are the same bytes): slot one is printed as the record when
    /// Fallout4.esm has one of that id, else as the number; slot two as the number, with the record of that id after a
    /// bar when there is one (a stage number can collide with a low engine id).
    public static string Condition(object c, Names names)
    {
        var data = Prop(c, "Data");
        var fn = Prop(data, "Function")?.ToString() ?? data?.GetType().Name.Replace("BinaryOverlay", "").Replace("ConditionData", "") ?? "?";
        var skip = new HashSet<string> { "Function", "RunOnType", "Reference", "Unknown2", "Unknown3", "UseAliases", "UsePackageData", "StaticRegistration", "Registration", "BinaryWriteTranslator",
                                         "Parameter1", "Parameter2", "Parameter1Type", "Parameter2Type" };
        var props = new Dictionary<string, object?>();
        if (data is not null)
            foreach (var i in data.GetType().GetInterfaces().Where(i => i.Name.EndsWith("Getter")))
                foreach (var p in i.GetProperties())
                    if (!skip.Contains(p.Name) && !props.ContainsKey(p.Name) && p.GetIndexParameters().Length == 0) props[p.Name] = p.GetValue(data);
        var pars = new List<string>();
        if (props.ContainsKey("ParameterOneRecord"))
        {
            foreach (var (slot, label) in new[] { ("One", "p1"), ("Two", "p2") })
            {
                var rec = props.GetValueOrDefault($"Parameter{slot}Record") as IFormLinkGetter;
                var num = props.GetValueOrDefault($"Parameter{slot}Number")?.ToString() ?? "0";
                var str = props.GetValueOrDefault($"Parameter{slot}String") as string;
                bool known = rec is { IsNull: false } && names.Known(rec.FormKey);
                var text = !string.IsNullOrEmpty(str) ? $"\"{str}\"" : slot == "One" ? (known ? names.Of(rec!.FormKey) : num) : known ? $"{num}|{names.Of(rec!.FormKey)}" : num;
                pars.Add($"{label}={text}");
            }
        }
        else
            foreach (var (name, v) in props)
                if (Value(v, names) is { } text) pars.Add($"{name}={text}");
        var run = Prop(data, "RunOnType")?.ToString() ?? "";
        var reference = Prop(data, "Reference") as IFormLinkGetter;
        var op = Prop(c, "CompareOperator")?.ToString() switch { "EqualTo" => "==", "NotEqualTo" => "!=", "GreaterThan" => ">", "GreaterThanOrEqualTo" => ">=", "LessThan" => "<", "LessThanOrEqualTo" => "<=", var s => s ?? "?" };
        var value = Value(Prop(c, "ComparisonValue"), names) ?? "?";
        var flags = Prop(c, "Flags")?.ToString();
        return $"{(flags is { } f && f != "0" ? $"[{f}] " : "")}{fn}({string.Join(", ", pars)}) on {run}{(reference is { IsNull: false } ? " " + names.Of(reference.FormKey) : "")} {op} {value}";
    }

    static string? Value(object? v, Names names) => v switch
    {
        null => null,
        IFormLinkGetter l => l.IsNull ? null : names.Of(l.FormKey),
        string s => s.Length == 0 ? null : $"\"{s}\"",
        float f => F(f),
        int or uint or short or ushort or long or byte or sbyte => v.ToString(),
        _ when v.GetType().Name.StartsWith("FormLinkOrIndex") => Prop(v, "Link") is IFormLinkGetter l && !l.IsNull ? names.Of(l.FormKey) : Prop(v, "Index") is { } ix ? $"alias {ix}" : null,
        _ => v.ToString(),
    };

    /// NG-K9: the conditions on the named records that reference MQ102, across quests, dialogue, scenes and packages.
    static void K9(Out o, F4.IFallout4ModGetter fo4, Names names)
    {
        var mq102 = fo4.Quests.FirstOrDefault(x => x.FormKey.ID == NewGame.Fo4MQ102) ?? fo4.Quests.FirstOrDefault(x => x.EditorID == "MQ102");
        if (mq102 is null) { o.Line("missing: QUST MQ102 is not in Fallout4.esm"); return; }
        bool Named(string? e) => e is not null && K9Names.Any(n => e.Contains(n, StringComparison.OrdinalIgnoreCase));
        bool Refers(object c) => c is IFormLinkContainerGetter fc && fc.EnumerateFormLinks().Any(l => l.FormKey == mq102.FormKey);
        int scanned = 0, hits = 0;
        void Lists(string owner, object holder, string what)
        {
            foreach (var (where, conds) in ConditionLists(holder, what))
            {
                var r = conds.Where(Refers).ToList();
                if (r.Count == 0) continue;
                hits += r.Count;
                o.Line($"  {owner} {where}: {r.Count} of {conds.Count} condition(s) reference MQ102");
                foreach (var c in r) o.Line("    " + Condition(c, names));
            }
        }
        foreach (var q in fo4.Quests.Where(q => Named(q.EditorID)))
        {
            scanned++;
            var owner = $"QUST {q.EditorID} {q.FormKey}";
            Lists(owner, q, "quest");
            foreach (var s in q.Stages) foreach (var e in s.LogEntries) Lists($"{owner} stage {s.Index}", e, "log entry");
            foreach (var a in q.Aliases ?? []) Lists($"{owner} alias {Prop(a, "Name")}", a, "alias");
            foreach (var ob in q.Objectives) foreach (var t in ob.Targets) Lists($"{owner} objective {ob.Index}", t, "target");
        }
        // MQ102's own aliases named for them: their fill conditions are what the start needs to satisfy
        foreach (var a in (mq102.Aliases ?? []).Where(a => Named(Prop(a, "Name")?.ToString())))
        {
            scanned++;
            Lists($"QUST MQ102 alias {Prop(a, "ID")} {Prop(a, "Name")}", a, "alias");
        }
        // dialogue and scenes sit under their quest in the plugin; a topic or scene named for them under any quest counts
        foreach (var t in fo4.Quests.SelectMany(q => q.DialogTopics.Select(t => (Quest: q, Topic: t))).Where(x => Named(x.Topic.EditorID) || Named(x.Quest.EditorID) || Named(names.EditorId(x.Topic.Quest.FormKey))).Select(x => x.Topic))
        {
            scanned++;
            foreach (var r in t.Responses) Lists($"DIAL {t.EditorID} INFO {r.FormKey}", r, "response");
        }
        foreach (var s in fo4.Quests.SelectMany(q => q.Scenes.Select(s => (Quest: q, Scene: s))).Where(x => Named(x.Scene.EditorID) || Named(x.Quest.EditorID) || Named(names.EditorId(x.Scene.Quest.FormKey))).Select(x => x.Scene))
        {
            scanned++;
            var owner = $"SCEN {s.EditorID} {s.FormKey}";
            Lists(owner, s, "scene");
            for (int i = 0; i < s.Phases.Count; i++) Lists($"{owner} phase {i} {s.Phases[i].Name}", s.Phases[i], "phase");
        }
        foreach (var p in fo4.Packages.Where(p => Named(p.EditorID) || Named(names.EditorId(p.OwnerQuest.FormKey))))
        {
            scanned++;
            Lists($"PACK {p.EditorID} {p.FormKey}", p, "package");
        }
        o.Line($"{scanned} record(s) named for {string.Join(", ", K9Names)} (or owned by a quest so named) scanned; {hits} condition(s) reference MQ102{(hits == 0 ? ": none (their start does not read MQ102 in a condition; look at scripts and aliases)" : "")}");
    }

    /// A record of any type: its type, EditorID, condition lists and the records it links to.
    static void RecordDetail(Out o, IMajorRecordGetter r, Names names)
    {
        o.Line($"{names.TypeOf(r.FormKey)} {r.EditorID ?? "(no EditorID)"} {r.FormKey}{(Prop(r, "Name") is ITranslatedStringGetter n && n.String is { Length: > 0 } s ? $" \"{s}\"" : "")}");
        foreach (var (where, conds) in ConditionLists(r, "record"))
        {
            o.Line($"  {where}: {conds.Count} condition(s)");
            foreach (var c in conds) o.Line("    " + Condition(c, names));
        }
        var links = (r as IFormLinkContainerGetter)?.EnumerateFormLinks().Where(l => !l.IsNull).Select(l => l.FormKey).Distinct().Take(40).ToList() ?? new();
        if (links.Count > 0) o.Line($"  links: {string.Join(", ", links.Select(names.Of))}");
    }

    // ---------------------------------------------------------------- names

    /// Every record of a plugin by FormKey: its EditorID and type, for naming links; and the records themselves for
    /// a few wanted ones (by key or by an EditorID term). One pass over the plugin; a fallback (Starfield.esm for the
    /// port) names what the plugin itself does not own.
    public sealed class Names
    {
        readonly Dictionary<FormKey, (string? Edid, string Type)> map = new();
        readonly Dictionary<FormKey, IMajorRecordGetter> wanted = new();
        readonly Names? fallback;
        /// The empty index: every name is its id (or the fallback's name).
        public Names(Names? fallback) { this.fallback = fallback; }
        public Names(IModGetter mod, Names? fallback = null)
        {
            this.fallback = fallback;
            foreach (var r in mod.EnumerateMajorRecords())
            {
                map[r.FormKey] = (r.EditorID, r.GetType().Name.Replace("BinaryOverlay", ""));
                if (r.FormKey == new FormKey(SfEsm, SustenanceId) || r.EditorID?.Contains(StartupQuestTerm, StringComparison.OrdinalIgnoreCase) == true) wanted[r.FormKey] = r;
            }
        }
        public string Of(FormKey k) => k.IsNull ? "none" : map.TryGetValue(k, out var e) ? $"{e.Edid ?? "(no EditorID)"} ({e.Type} {k})" : fallback?.Of(k) ?? k.ToString();
        public string? EditorId(FormKey k) => map.TryGetValue(k, out var e) ? e.Edid : fallback?.EditorId(k);
        public bool Known(FormKey k) => map.ContainsKey(k) || fallback?.Known(k) == true;
        public string TypeOf(FormKey k) => map.TryGetValue(k, out var e) ? e.Type : fallback?.TypeOf(k) ?? "?";
        public IMajorRecordGetter? Record(FormKey k) => wanted.TryGetValue(k, out var r) ? r : null;
        public IEnumerable<IMajorRecordGetter> Containing(string term) => wanted.Values.Where(r => r.EditorID?.Contains(term, StringComparison.OrdinalIgnoreCase) == true).OrderBy(r => r.FormKey.ID);
    }

    sealed class Out
    {
        readonly List<string> lines = new();
        public void Line(string s) => lines.Add(s);
        public void Section(string title, Action body)
        {
            lines.Add(""); lines.Add("===== " + title);
            try { body(); }
            catch (Exception e) { lines.Add($"ERROR in this section (the rest of the report stands): {e.GetType().Name}: {e.Message}"); }
        }
        public string Text() => string.Join("\n", lines) + "\n";
    }

    // ---------------------------------------------------------------- selftest (synthetic plugins only)

    public static int SelfTest(string dir)
    {
        Directory.CreateDirectory(dir);
        var f4Key = ModKey.FromFileName(Fo4Esm);
        var f4 = new F4.Fallout4Mod(f4Key, F4.Fallout4Release.Fallout4);
        f4.ModHeader.Flags |= F4.Fallout4ModHeader.HeaderFlag.Master;
        var mq102 = new F4.Quest(new FormKey(f4Key, NewGame.Fo4MQ102), F4.Fallout4Release.Fallout4) { EditorID = "MQ102", Name = "Out of Time", Data = new F4.QuestData { Flags = F4.Quest.Flag.RunOnce } };
        F4.ConditionFloat StageDone(FormKey quest, int stage, float value = 1) => new()
        {
            CompareOperator = F4.CompareOperator.EqualTo, ComparisonValue = value,
            Data = new F4.FunctionConditionData { Function = F4.Condition.Function.GetStageDone, ParameterOneRecord = new FormLink<F4.IFallout4MajorRecordGetter>(quest), ParameterTwoNumber = stage },
        };
        F4.QuestStage St(ushort i, string? text = null, bool complete = false, F4.Condition? cond = null, F4.QuestStage.Flag flags = 0)
        {
            var s = new F4.QuestStage { Index = i, Flags = flags };
            var e = new F4.QuestLogEntry { Entry = text, Flags = complete ? F4.QuestLogEntry.Flag.CompleteQuest : null };
            if (cond is not null) e.Conditions.Add(cond);
            if (text is not null || complete || cond is not null) s.LogEntries.Add(e);
            return s;
        }
        mq102.Stages.Add(St(0, flags: F4.QuestStage.Flag.RunOnStart));
        mq102.Stages.Add(St(5, "The console needs a Pip-Boy"));
        mq102.Stages.Add(St(10, "Go home", cond: StageDone(mq102.FormKey, 9)));
        mq102.Stages.Add(St(15, "Radios on"));
        mq102.Stages.Add(St(200, "Done", complete: true));
        mq102.VirtualMachineAdapter = new F4.QuestAdapter { Version = 6, ObjectFormat = 2, Script = new F4.ScriptEntry { Name = "", Flags = F4.ScriptEntry.Flag.Local } };
        mq102.VirtualMachineAdapter.Fragments.Add(new F4.QuestScriptFragment { Stage = 200, ScriptName = "Fragments:Quests:QF_MQ102_0001CC2A", FragmentName = "Fragment_Stage_0200_Item_00" });
        var codsAlias = new F4.QuestReferenceAlias { ID = 3, Name = "Codsworth" };
        codsAlias.Conditions.Add(StageDone(mq102.FormKey, 10, 0));
        (mq102.Aliases ??= new ExtendedList<F4.AQuestAlias>()).Add(codsAlias);
        f4.Quests.Add(mq102);
        var mq101 = new F4.Quest(new FormKey(f4Key, 0x1CC2B), F4.Fallout4Release.Fallout4) { EditorID = "MQ101", Name = "War Never Changes", Data = new F4.QuestData() };
        foreach (var (i, t) in new (ushort, string)[] { (700, "pre-war"), (710, "cryo scene"), (770, "pod corpses"), (900, "the move and RemoveAllItems"), (1000, "the end"), (1010, "after") }) mq101.Stages.Add(St(i, t));
        f4.Quests.Add(mq101);
        var cods = new F4.Quest(new FormKey(f4Key, 0x3000), F4.Fallout4Release.Fallout4) { EditorID = "COMCodsworth", Data = new F4.QuestData() };
        cods.DialogConditions.Add(StageDone(mq102.FormKey, 15));
        f4.Quests.Add(cods);
        var min = new F4.Quest(new FormKey(f4Key, 0x3001), F4.Fallout4Release.Fallout4) { EditorID = "Min00", Data = new F4.QuestData() };
        min.Stages.Add(St(10, "Concord", cond: new F4.ConditionFloat { CompareOperator = F4.CompareOperator.EqualTo, ComparisonValue = 1, Data = new F4.FunctionConditionData { Function = F4.Condition.Function.GetQuestCompleted, ParameterOneRecord = new FormLink<F4.IFallout4MajorRecordGetter>(mq102.FormKey) } }));
        f4.Quests.Add(min);
        var dog = new F4.Quest(new FormKey(f4Key, 0x3002), F4.Fallout4Release.Fallout4) { EditorID = "COMDogmeat", Data = new F4.QuestData() };
        dog.DialogConditions.Add(StageDone(mq101.FormKey, 900));           // another quest: not reported
        f4.Quests.Add(dog);
        var pack = new F4.Package(new FormKey(f4Key, 0x3003), F4.Fallout4Release.Fallout4) { EditorID = "DogmeatSandboxPackage" };
        pack.Conditions.Add(StageDone(mq102.FormKey, 10));
        f4.Packages.Add(pack);
        var topic = new F4.DialogTopic(new FormKey(f4Key, 0x3004), F4.Fallout4Release.Fallout4) { EditorID = "COMCodsworthHello" };
        topic.Quest.SetTo(cods.FormKey);
        var info = new F4.DialogResponses(new FormKey(f4Key, 0x3005), F4.Fallout4Release.Fallout4) { EditorID = "COMCodsworthHello01" };
        info.Conditions.Add(StageDone(mq102.FormKey, 55));
        topic.Responses.Add(info);
        cods.DialogTopics.Add(topic);
        var vcell = new F4.Cell(new FormKey(f4Key, NewGame.Fo4VaultCell), F4.Fallout4Release.Fallout4) { EditorID = "Vault111Cryo", Flags = F4.Cell.Flag.IsInteriorCell };
        vcell.Temporary.Add(new F4.PlacedObject(new FormKey(f4Key, 0x4A011), F4.Fallout4Release.Fallout4) { EditorID = "MQPlayerCryopodREF", Position = new P3Float(700f, 1400f, 70f) });
        var block = new F4.CellBlock { BlockNumber = 0, GroupType = F4.GroupTypeEnum.InteriorCellBlock };
        var sub = new F4.CellSubBlock { BlockNumber = 0, GroupType = F4.GroupTypeEnum.InteriorCellSubBlock };
        sub.Cells.Add(vcell); block.SubBlocks.Add(sub); f4.Cells.Records.Add(block);
        var f4Path = Path.Combine(dir, Fo4Esm);
        f4.BeginWrite.ToPath(f4Path).WithNoLoadOrder().NoCheckIfLowerRangeDisallowed().Write();

        var rel = SF.StarfieldRelease.Starfield;
        var sf = new SF.StarfieldMod(SfEsm, rel);
        sf.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Master;
        var dbg = new SF.Global(new FormKey(SfEsm, 0x900), rel) { EditorID = "MQ101Debug", Data = 0 };
        sf.Globals.Add(dbg);
        SF.ConditionFloat Glob(float value, SF.CompareOperator op = SF.CompareOperator.EqualTo)
        {
            var d = new SF.GetGlobalValueConditionData();
            d.FirstParameter.Link.SetTo(dbg.FormKey);
            return new SF.ConditionFloat { CompareOperator = op, ComparisonValue = value, Data = d };
        }
        var smq101 = new SF.Quest(new FormKey(SfEsm, 0x902), rel) { EditorID = "MQ101", Name = "One Small Step", Data = new SF.QuestData { Flags = SF.Quest.Flag.StartGameEnabled } };
        // every entry has Flags set: Mutagen writes a Starfield log entry's QSDT marker only then, and the reader
        // starts an entry at each marker (a shipped plugin has one per entry)
        var st0 = new SF.QuestStage { Index = 0, Flags = SF.QuestStage.Flag.RunOnStart };
        var e0 = new SF.QuestLogEntry { Entry = "the NG+ start", Flags = 0 }; e0.Conditions.Add(Glob(1)); st0.LogEntries.Add(e0);
        var e1 = new SF.QuestLogEntry { Entry = "the Kreet quick start", Flags = 0 }; e1.Conditions.Add(Glob(8)); st0.LogEntries.Add(e1);
        var e2 = new SF.QuestLogEntry { Entry = "the normal start", Flags = 0 }; e2.Conditions.Add(Glob(10)); st0.LogEntries.Add(e2);
        smq101.Stages.Add(st0);
        smq101.Stages.Add(new SF.QuestStage { Index = 105 });
        smq101.VirtualMachineAdapter = new SF.QuestAdapter { Version = 6, ObjectFormat = 2, ExtraBindDataVersion = 3, Script = new SF.ScriptEntry { Name = "", Flags = SF.ScriptEntry.Flag.Local } };
        smq101.VirtualMachineAdapter.Fragments.Add(new SF.QuestScriptFragment { Stage = 0, ScriptName = "Fragments:Quests:QF_MQ101_00003448", FragmentName = "Fragment_Stage_0000_Item_00" });
        sf.Quests.Add(smq101);
        var mq00 = new SF.Quest(new FormKey(SfEsm, 0x901), rel) { EditorID = "MQ00", Data = new SF.QuestData { Flags = SF.Quest.Flag.StartGameEnabled } };
        mq00.DialogConditions.Add(Glob(0));
        var s10 = new SF.QuestStage { Index = 10 }; var e10 = new SF.QuestLogEntry { Flags = 0 }; e10.Conditions.Add(Glob(8, SF.CompareOperator.NotEqualTo)); s10.LogEntries.Add(e10); mq00.Stages.Add(s10);
        sf.Quests.Add(mq00);
        var sus = new SF.ConditionRecord(new FormKey(SfEsm, SustenanceId), rel) { EditorID = "SustenanceAllowed" };
        sus.Conditions.Add(Glob(0, SF.CompareOperator.GreaterThan));
        sf.ConditionRecords.Add(sus);
        var dobj = new SF.DefaultObject(new FormKey(SfEsm, 0x903), rel) { EditorID = "StartupQuest_DO" };
        dobj.Object.SetTo(mq00.FormKey);
        sf.DefaultObjects.Add(dobj);
        sf.Statics.Add(new SF.Static(new FormKey(SfEsm, NewGame.CocMarkerId), rel) { EditorID = "COCMarkerHeading" });
        sf.ModHeader.Stats.NextFormID = 0x904;
        var sfPath = Path.Combine(dir, SfEsmName);
        sf.BeginWrite.ToPath(sfPath).WithNoLoadOrder().NoCheckIfLowerRangeDisallowed().Write();

        var portKey = ModKey.FromFileName(PortEsm);
        var port = new SF.StarfieldMod(portKey, rel);
        port.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Master;
        var pip = new SF.Static(new FormKey(portKey, 0x810), rel) { EditorID = "FO4Port_PipBoySkeleton01" };
        var wall = new SF.Static(new FormKey(portKey, 0x811), rel) { EditorID = "FO4Port_VltWall01" };
        var term = new SF.Terminal(new FormKey(portKey, 0x812), rel) { EditorID = "FO4Port_VltTerminal01" };
        port.Statics.Add(pip); port.Statics.Add(wall); port.Terminals.Add(term);
        SF.PlacedObject R(uint id, FormKey b, float x, float y, float z, bool persistent = false, string? edid = null)
        {
            var r = new SF.PlacedObject(new FormKey(portKey, id), rel) { EditorID = edid, Base = new FormLinkNullable<SF.IPlaceableObjectGetter>(b), Position = new P3Float(x, y, z) };
            if (persistent) r.MajorRecordFlagsRaw |= 0x400;
            return r;
        }
        var cryo = new SF.Cell(new FormKey(portKey, 0x800), rel) { EditorID = NewGame.VaultCell, Flags = SF.Cell.Flag.IsInteriorCell };
        cryo.Temporary.Add(R(0x801, new FormKey(SfEsm, NewGame.CocMarkerId), 60, 15, 1));
        cryo.Temporary.Add(R(0x802, wall.FormKey, 10, 20, 1));
        cryo.Persistent.Add(R(0x803, wall.FormKey, 12, 21, 1, true, "FO4Port_NearWall"));
        cryo.Persistent.Add(R(0x804, wall.FormKey, 90, 40, 20, true, "FO4Port_FarWall"));
        cryo.Persistent.Add(R(0x805, term.FormKey, 11, 20, 1, true, "FO4Port_CryoTerminal"));
        cryo.Temporary.Add(R(0x806, term.FormKey, 50, 10, 0, false, "FO4Port_OverseerTerminal"));
        cryo.Temporary.Add(R(0x807, pip.FormKey, 52, 10, 0));
        var entrance = new SF.Cell(new FormKey(portKey, 0x820), rel) { EditorID = "FO4Port_Vault111Ent", Flags = SF.Cell.Flag.IsInteriorCell };
        entrance.Persistent.Add(R(0x821, pip.FormKey, 1, 2, 3, true, "FO4Port_PipBoyREF"));
        var other = new SF.Cell(new FormKey(portKey, 0x830), rel) { EditorID = "FO4Port_RedRocket", Flags = SF.Cell.Flag.IsInteriorCell };
        other.Temporary.Add(R(0x831, pip.FormKey, 5, 5, 5));            // not a Vault 111 cell: not reported
        var pb = new SF.CellBlock { BlockNumber = 0, GroupType = SF.GroupTypeEnum.InteriorCellBlock };
        var ps = new SF.CellSubBlock { BlockNumber = 0, GroupType = SF.GroupTypeEnum.InteriorCellSubBlock };
        ps.Cells.Add(cryo); ps.Cells.Add(entrance); ps.Cells.Add(other); pb.SubBlocks.Add(ps); port.Cells.Records.Add(pb);
        port.ModHeader.Stats.NextFormID = 0x832;
        var portPath = Path.Combine(dir, PortEsm);
        port.BeginWrite.ToPath(portPath).WithLoadOrder(SfEsm).WithKnownMasters(new KeyedMasterStyle(SfEsm, MasterStyle.Full)).Write();

        var outDir = Path.Combine(dir, "report");
        var before = Directory.GetFiles(dir).Select(Path.GetFileName).OrderBy(x => x).ToList();
        var outPath = Path.Combine(outDir, "records.txt");
        if (Run(dir, outPath, dir, null, 5) != 0) { Console.WriteLine("FAIL  records run"); return 1; }
        var text = File.ReadAllText(outPath);
        var after = Directory.GetFiles(dir).Select(Path.GetFileName).OrderBy(x => x).ToList();
        if (!before.SequenceEqual(after) || Directory.GetFiles(outDir).Length != 1) { Console.WriteLine("FAIL  records wrote more than --out"); return 1; }
        var expect = new (string What, string Needle)[]
        {
            ("K1 header", $"Quest MQ102 01CC2A:Fallout4.esm \"Out of Time\""),
            ("K1 stage 0 flag", "stage 0 [RunOnStart]: 0 log entries"),
            ("K1 stage 10 condition", "stage 10: 1 log entry"), ("K1 stage 10 text", "log 0 \"Go home\": 1 condition(s)"),
            ("K1 GetStageDone text", "GetStageDone(p1=MQ102 (Quest 01CC2A:Fallout4.esm), p2=9) on Subject == 1"),
            ("K1 stage 200", "stage 200: 1 log entry; fragments Fragments:Quests:QF_MQ102_0001CC2A.Fragment_Stage_0200_Item_00"),
            ("K1 complete flag", "log 0 [CompleteQuest] \"Done\""), ("K1 completes", "completes: stage 200 (log entry flagged CompleteQuest)"),
            ("K1 alias", "alias 3 Codsworth: 1 condition(s)"), ("K1 alias cond", "GetStageDone(p1=MQ102 (Quest 01CC2A:Fallout4.esm), p2=10) on Subject == 0"),
            ("K2 header", "Quest MQ101 01CC2B:Fallout4.esm \"War Never Changes\" flags none"),
            ("K2 710", "stage 710: 1 log entry"), ("K2 770", "\"pod corpses\""), ("K2 1000", "stage 1000: 1 log entry"),
            ("K4 cryo", $"{NewGame.VaultCell} 000800:FO4Port.esm: REFR 000807:FO4Port.esm  base FO4Port_PipBoySkeleton01 (Static 000810:FO4Port.esm) at (52, 10, 0) m"),
            ("K4 entrance", "FO4Port_Vault111Ent 000820:FO4Port.esm: REFR 000821:FO4Port.esm FO4Port_PipBoyREF base FO4Port_PipBoySkeleton01 (Static 000810:FO4Port.esm) at (1, 2, 3) m persistent"),
            ("K4 count", "2 Vault 111 cell(s), 8 reference(s), 2 with a PipBoy base"),
            ("K9 Codsworth", "QUST COMCodsworth 003000:Fallout4.esm quest DialogConditions: 1 of 1 condition(s) reference MQ102"),
            ("K9 Min00", "QUST Min00 003001:Fallout4.esm stage 10 log entry Conditions: 1 of 1 condition(s) reference MQ102"),
            ("K9 GetQuestCompleted", "GetQuestCompleted(p1=MQ102 (Quest 01CC2A:Fallout4.esm), p2=0) on Subject == 1"),
            ("K9 package", "PACK DogmeatSandboxPackage 003003:Fallout4.esm package Conditions: 1 of 1 condition(s) reference MQ102"),
            ("K9 dialogue", "DIAL COMCodsworthHello INFO 003005:Fallout4.esm response Conditions: 1 of 1 condition(s) reference MQ102"),
            ("K9 MQ102 alias", "QUST MQ102 alias 3 Codsworth alias Conditions: 1 of 1 condition(s) reference MQ102"), ("K9 count", "6 record(s) named for Codsworth, Dogmeat, Min00 (or owned by a quest so named) scanned; 5 condition(s) reference MQ102"),
            ("N4 MQ101", "MQ101 000902:Starfield.esm \"One Small Step\" flags StartGameEnabled: stage 0 only"),
            ("N4 stage 0", "stage 0 [RunOnStart]: 3 log entries; fragments Fragments:Quests:QF_MQ101_00003448.Fragment_Stage_0000_Item_00"),
            ("N4 entry 1", "log 1 \"the Kreet quick start\": 1 condition(s)"), ("N4 entry 2", "log 2 \"the normal start\": 1 condition(s)"),
            ("N4 GetGlobalValue", "GetGlobalValue(FirstParameter=MQ101Debug (Global 000900:Starfield.esm), SecondParameter=0) on Subject == 8"),
            ("N4 MQ00", "Quest MQ00 000901:Starfield.esm \"\" flags StartGameEnabled: 1 stage(s) [10]"), ("N4 MQ00 conds", "quest DialogConditions: 1 condition(s)"),
            ("N4 MQ00 stage 10", "SecondParameter=0) on Subject != 8"),
            ("N4 sustenance", "ConditionRecord SustenanceAllowed 2EEA4D:Starfield.esm"), ("N4 sustenance cond", "on Subject > 0"),
            ("N4 startup", "1 record(s) whose EditorID mentions StartupQuest"), ("N4 startup DO", "DefaultObject StartupQuest_DO 000903:Starfield.esm"),
            ("N4 startup link", "links: MQ00 (Quest 000901:Starfield.esm)"),
            ("anchor origin", "origin (10, 20, 1) m: FO4 0004A011 MQPlayerCryopodREF / 70; COC marker 000801:FO4Port.esm at (60, 15, 1) m temporary"),
            ("anchor count", "3 persistent reference(s) of 7; nearest 3:"),
            ("anchor nearest", "000805:FO4Port.esm FO4Port_CryoTerminal base FO4Port_VltTerminal01 (Terminal 000812:FO4Port.esm) at (11, 20, 1) m, 1 m away"),
            ("anchor terminals", "2 terminal reference(s) in the cell:"), ("anchor temp terminal", "FO4Port_OverseerTerminal base FO4Port_VltTerminal01 (Terminal 000812:FO4Port.esm) at (50, 10, 0) m, 41.243 m away, temporary"),
        };
        foreach (var (what, needle) in expect)
            if (!text.Contains(needle)) { Console.WriteLine($"FAIL  report lacks {what}: {needle}\n----\n{text}"); return 1; }
        if (!text.Contains("FO4Port_NearWall") || text.IndexOf("FO4Port_CryoTerminal") > text.IndexOf("FO4Port_NearWall") || text.IndexOf("FO4Port_NearWall") > text.IndexOf("FO4Port_FarWall"))
            { Console.WriteLine("FAIL  the persistent references are not nearest first"); return 1; }
        foreach (var absent in new[] { "stage 700", "stage 1010", "FO4Port_RedRocket", "COMDogmeat", "000831:FO4Port.esm", "ERROR in this section" })
            if (text.Contains(absent)) { Console.WriteLine($"FAIL  report has {absent}\n----\n{text}"); return 1; }
        // missing inputs are reported, never fatal: no Fallout 4, and a port that is not there
        var missPath = Path.Combine(outDir, "missing.txt");
        if (Run(Path.Combine(dir, "nowhere"), missPath, dir, Path.Combine(dir, "nowhere", PortEsm), 5) != 0) { Console.WriteLine("FAIL  a missing input was fatal"); return 1; }
        var miss = File.ReadAllText(missPath);
        foreach (var needle in new[] { $"missing: Fallout4.esm {Path.Combine(dir, "nowhere", Fo4Esm)}", "===== NG-K1", "missing: Fallout4.esm\n", "===== NG-K4", "missing: FO4Port.esm\n",
                                       "Quest MQ00 000901:Starfield.esm", "===== anchor", "missing: FO4Port.esm" })
            if (!miss.Contains(needle)) { Console.WriteLine($"FAIL  the missing-input report lacks: {needle}\n----\n{miss}"); return 1; }
        if (Sections(miss).Count() != 6) { Console.WriteLine($"FAIL  {Sections(miss).Count()} sections, not 6"); return 1; }
        // without Fallout 4 the anchor origin falls back to the COC marker
        var cocOnly = Path.Combine(outDir, "coc.txt");
        if (Run(Path.Combine(dir, "nowhere"), cocOnly, dir, null, 5) != 0 || !File.ReadAllText(cocOnly).Contains("origin (60, 15, 1) m: the cell's COC marker (Fallout4.esm missing)"))
            { Console.WriteLine("FAIL  the COC marker fallback"); return 1; }
        // a plugin that is there but cannot be read is reported like a missing one, not fatal
        var badDir = Path.Combine(dir, "bad");
        Directory.CreateDirectory(badDir);
        File.WriteAllBytes(Path.Combine(badDir, Fo4Esm), new byte[] { 0x54, 0x45, 0x53, 0x34, 1, 2, 3 });
        var badPath = Path.Combine(outDir, "bad.txt");
        if (Run(badDir, badPath, dir, null, 5) != 0 || !File.ReadAllText(badPath).Contains($"missing: Fallout4.esm {Path.Combine(badDir, Fo4Esm)} could not be read: "))
            { Console.WriteLine("FAIL  an unreadable Fallout4.esm was not reported as missing"); return 1; }
        try { Run(dir, null, dir, null, 5); Console.WriteLine("FAIL  records ran without --out"); return 1; }
        catch (NewGame.Refusal e) { Console.WriteLine($"refused as expected (no --out): {e.Message}"); }
        Console.WriteLine("records selftest pass");
        return 0;
    }
}
