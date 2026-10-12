// ActorRaider: the first converted Fallout 4 NPC (docs/actors/raider-conversion.md). Claude's project.
//
//   export-fo4 <Fallout4.esm> <ACHR hex> <player level> <out.json>
//        the placed FO4 actor, its base NPC_ and, per template category, the record the engine takes that category
//        from at <player level> (TPTA / TPLT followed through LVLN entries; the first qualifying entry is chosen and
//        every candidate is listed). Input of scripts/actors/raider_map.py.
//   write <Starfield.esm> <spec.json> <out dir>
//        one plugin with the spec's NPC_ records (raider_map.py: the conversion and its probe variant). Every vanilla link
//        in the spec names its FormID, EditorID and record type; the writer refuses to write when one of them does not
//        match Starfield.esm.
//   check <Starfield.esm> <plugin.esm> <out.json>
//        re-reads the written plugin (Mutagen), resolves every link and each template category against Starfield.esm,
//        and reports a record without a subrecord that every vanilla NPC_ carries or with another form version.
//   roundtrip <Starfield.esm> <NPC_ ids hex,comma> <scratch dir> <out.json>
//        Mutagen write fidelity for NPC_: copies vanilla records into an override plugin, writes it and compares the
//        subrecords byte by byte with Starfield.esm's (decompressed). Shows what Mutagen cannot write back.
// Inspector (read-only):
//   fo4-find <Fallout4.esm> <cell x> <cell y> <radius cells> [base EditorID substr]   placed NPCs near a Commonwealth cell
//   fo4-dump / sf-dump <esm> <ids hex,comma>     every property of the records
//   sf-find <Starfield.esm> <Class> <EditorID substr> [n]     e.g. sf-find ... Weapon Coachman
//   sf-tplstats <Starfield.esm> [n]              template flag bits and the unnamed slots (TPTA Unknown1/2) over all NPC_
//   rawsubs <plugin> <SIG> <ids hex,comma>       subrecord types and sizes of raw records (decompressed)
//   rawcount <plugin> <SIG> <SUB>                records of a group that contain a subrecord type, and where
//   props <Fallout4|Starfield> <Class>           Mutagen's schema of a class or enum
// Nothing is deployed and no game file is written.
using Mutagen.Bethesda;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Cache;
using Mutagen.Bethesda.Plugins.Records;
using Noggog;
using F4 = Mutagen.Bethesda.Fallout4;
using SF = Mutagen.Bethesda.Starfield;

if (args.Length == 0) { Console.Error.WriteLine("usage: see the header of Program.cs"); return 1; }
switch (args[0])
{
    case "export-fo4": return Fo4Source.Export(args[1], Hex(args[2]), int.Parse(args[3]), args[4]);
    case "write": return Writer.Write(args[1], args[2], args[3]);
    case "check": return Writer.Check(args[1], args[2], args[3]);
    case "roundtrip": return Roundtrip.Run(args[1], args[2].Split(',').Select(Hex).ToArray(), args[3], args[4]);
    case "rawsubs":   // rawsubs <plugin> <SIG> <ids hex,comma>: subrecord types of raw records (decompressed)
    {
        var ids = args[3].Split(',').Select(x => Hex(x) & 0xFFFFFF).ToHashSet();
        foreach (var (id, data) in Roundtrip.ReadGroup(args[1], args[2], ids))
            Console.WriteLine($"{id:X8}: " + string.Join(" ", Roundtrip.Subrecords(data).Select(s => $"{s.Type}:{s.Data.Length}")));
        return 0;
    }
    case "rawcount":   // rawcount <plugin> <SIG> <SUB>: records of a group with/without a subrecord type
    {
        int with = 0, all = 0;
        var where = new Dictionary<string, int>();
        foreach (var (id, data) in Roundtrip.ReadGroup(args[1], args[2], null))
        {
            all++;
            var subs = Roundtrip.Subrecords(data);
            int i = subs.FindIndex(s => s.Type == args[3]);
            if (i < 0) continue;
            with++;
            var ctx = $"after {(i > 0 ? subs[i - 1].Type : "-")}, before {(i + 1 < subs.Count ? subs[i + 1].Type : "-")}";
            where[ctx] = where.GetValueOrDefault(ctx) + 1;
        }
        Console.WriteLine($"{args[2]}: {all} records, {with} with {args[3]}");
        foreach (var kv in where.OrderByDescending(k => k.Value).Take(10)) Console.WriteLine($"  {kv.Key}: {kv.Value}");
        return 0;
    }
    case "props":
    {
        var asm = args[1] == "Fallout4" ? typeof(F4.Fallout4Mod).Assembly : typeof(SF.StarfieldMod).Assembly;
        var t = asm.GetType($"Mutagen.Bethesda.{args[1]}.{args[2]}")
                ?? AppDomain.CurrentDomain.GetAssemblies().SelectMany(a => { try { return a.GetTypes(); } catch { return Array.Empty<Type>(); } })
                       .First(x => x.Name == args[2] && (x.Namespace ?? "").Contains(args[1]));
        Console.WriteLine(t.FullName);
        foreach (var p in t.GetProperties())
            Console.WriteLine($"{Util.Tn(p.PropertyType),-60} {p.Name}");
        if (t.IsEnum) foreach (var v in Enum.GetValues(t)) Console.WriteLine($"  {v} = {Convert.ToInt64(v)}");
        return 0;
    }
    case "fo4-find":
    {
        using var mod = F4.Fallout4Mod.CreateFromBinaryOverlay(args[1], F4.Fallout4Release.Fallout4);
        var cache = Util.Cache(mod);
        float cx = float.Parse(args[2]), cy = float.Parse(args[3]), rc = float.Parse(args[4]);
        var sub = args.Length > 5 ? args[5] : "Raider";
        var w = mod.Worldspaces.First(x => x.EditorID == "Commonwealth");
        void Visit(F4.ICellGetter c)
        {
            foreach (var p in c.Persistent.Concat(c.Temporary))
            {
                if (p is not F4.IPlacedNpcGetter a) continue;
                var pos = a.Position;
                float gx = pos.X / 4096f, gy = pos.Y / 4096f;
                if (Math.Abs(gx - cx) > rc || Math.Abs(gy - cy) > rc) continue;
                var b = Util.Edid(cache, a.Base.FormKey);
                if (!b.Contains(sub, StringComparison.OrdinalIgnoreCase)) continue;
                Console.WriteLine($"{a.FormKey.ID:X8} {a.EditorID,-30} base {a.Base.FormKey.ID:X8} {b,-36} pos ({pos.X:F0},{pos.Y:F0},{pos.Z:F0}) " +
                                  $"grid ({Math.Floor(gx)},{Math.Floor(gy)}) cell {c.EditorID} {c.FormKey.ID:X8}");
            }
        }
        if (w.TopCell is { } top) Visit(top);
        foreach (var blk in w.SubCells) foreach (var sb in blk.Items) foreach (var c in sb.Items) Visit(c);
        return 0;
    }
    case "fo4-dump":
    case "sf-dump":
    {
        IDisposable mod = args[0] == "fo4-dump"
            ? F4.Fallout4Mod.CreateFromBinaryOverlay(args[1], F4.Fallout4Release.Fallout4)
            : SF.StarfieldMod.CreateFromBinaryOverlay(args[1], SF.StarfieldRelease.Starfield);
        using var _ = mod;
        var cache = Util.Cache(mod);
        var key = ((IModGetter)mod).ModKey;
        foreach (var id in args[2].Split(','))
        {
            var fk = new FormKey(key, Hex(id) & 0xFFFFFF);
            if (!cache.TryResolve<IMajorRecordGetter>(fk, out var r)) { Console.WriteLine($"== {id}: not found"); continue; }
            Console.WriteLine($"== {r.FormKey} {r.EditorID} {r.GetType().Name}");
            Util.Dump(cache, r, "   ", 2);
        }
        return 0;
    }
    case "sf-find":
    {
        using var mod = SF.StarfieldMod.CreateFromBinaryOverlay(args[1], SF.StarfieldRelease.Starfield);
        var t = typeof(SF.StarfieldMod).Assembly.GetType($"Mutagen.Bethesda.Starfield.I{args[2]}Getter")!;
        int n = 0, max = args.Length > 4 ? int.Parse(args[4]) : 60;
        foreach (var r in mod.EnumerateMajorRecords(t))
        {
            if (!(r.EditorID ?? "").Contains(args[3], StringComparison.OrdinalIgnoreCase)) continue;
            Console.WriteLine($"{r.FormKey.ID:X8} {r.EditorID}");
            if (++n >= max) break;
        }
        return 0;
    }
    case "sf-tplstats":
    {
        using var mod = SF.StarfieldMod.CreateFromBinaryOverlay(args[1], SF.StarfieldRelease.Starfield);
        int all = 0, templated = 0;
        var flagCounts = new int[16];
        var pattern = new Dictionary<string, int>();
        foreach (var n in mod.Npcs)
        {
            all++;
            var f = (int)n.UseTemplateActors;
            if (f == 0) continue;
            templated++;
            for (int b = 0; b < 16; b++) if ((f & (1 << b)) != 0) flagCounts[b]++;
            if (n.TemplateActors is not { } ta) continue;
            var named = Writer.Slots.Where(s => s.Bit < 13).Select(s => (s.Name, Writer.SlotLink(ta, s.Name))).ToArray();
            foreach (var (slot, fk) in new[] { ("Unknown1", ta.Unknown1.FormKey), ("Unknown2", ta.Unknown2.FormKey) })
            {
                var same = named.Where(x => x.Item2 == fk).Select(x => x.Item1).ToArray();
                string key = fk.IsNull ? "null" : named.Select(x => x.Item2).Distinct().Count() == 1 ? "uniform" : string.Join("+", same);
                pattern[$"{slot}: {key}"] = pattern.GetValueOrDefault($"{slot}: {key}") + 1;
            }
        }
        Console.WriteLine($"NPC_ {all}, with template flags {templated}");
        for (int b = 0; b < 16; b++) Console.WriteLine($"  bit {b,2} ({1 << b,5}): {flagCounts[b]}");
        foreach (var kv in pattern.OrderByDescending(k => k.Value).Take(args.Length > 2 ? int.Parse(args[2]) : 30)) Console.WriteLine($"  {kv.Key}: {kv.Value}");
        return 0;
    }
}
Console.Error.WriteLine($"unknown mode {args[0]}");
return 1;

static uint Hex(string s) => Convert.ToUInt32(s.Trim(), 16);

static class Util
{
    public static string Tn(Type t) => t.Name + (t.GenericTypeArguments.Length > 0 ? "<" + string.Join(",", t.GenericTypeArguments.Select(Tn)) + ">" : "");

    public static ILinkCache Cache(object mod) => mod switch
    {
        F4.IFallout4ModGetter f => f.ToImmutableLinkCache<F4.IFallout4Mod, F4.IFallout4ModGetter>(),
        SF.IStarfieldModGetter s => s.ToImmutableLinkCache<SF.IStarfieldMod, SF.IStarfieldModGetter>(),
        _ => throw new ArgumentException("not a Fallout 4 or Starfield mod"),
    };

#pragma warning disable CS0618   // untyped identifier lookup is fine for reports
    public static string Edid(ILinkCache c, FormKey fk) => !fk.IsNull && c.TryResolveIdentifier(fk, out var e) ? (e ?? "") : "";
#pragma warning restore CS0618

    public static string RecType(object r) => r.GetType().Name.Replace("BinaryOverlay", "");

    public static void Dump(ILinkCache c, object? o, string ind, int depth)
    {
        if (o is null) return;
        foreach (var p in o.GetType().GetProperties())
        {
            if (p.GetIndexParameters().Length > 0) continue;
            if (p.Name is "Registration" or "StaticRegistration" or "FormVersion" or "VersionControl" or "Version2" or "IsCompressed" or "IsDeleted" or "MajorRecordFlagsRaw") continue;
            object? v; try { v = p.GetValue(o); } catch (Exception ex) { Console.WriteLine($"{ind}{p.Name} = <{ex.GetType().Name}>"); continue; }
            Console.WriteLine($"{ind}{p.Name} = {Show(c, v)}");
            if (depth <= 0 || v is null || v is string || v is IFormLinkGetter || v.GetType().IsPrimitive || v.GetType().IsEnum || v is IMajorRecordGetter) continue;
            if (v is System.Collections.IEnumerable e)
            {
                if (v is ReadOnlyMemorySlice<byte>) continue;
                int i = 0;
                foreach (var x in e)
                {
                    if (x is null || x is IFormLinkGetter || x.GetType().IsPrimitive || x.GetType().Namespace?.StartsWith("Mutagen") != true) continue;
                    Console.WriteLine($"{ind}   [{i}] {RecType(x)}");
                    Dump(c, x, ind + "      ", depth - 1);
                    if (++i >= 40) break;
                }
            }
            else if (v.GetType().Namespace?.StartsWith("Mutagen") == true)
                Dump(c, v, ind + "   ", depth - 1);
        }
    }

    static string Show(ILinkCache c, object? v)
    {
        string s = v switch
        {
            null => "null",
            string str => '"' + str + '"',
            IFormLinkGetter l => $"{l.FormKey} {Edid(c, l.FormKey)}",
            ReadOnlyMemorySlice<byte> b => $"bytes[{b.Length}] {Convert.ToHexString(b.Span.Slice(0, Math.Min(32, b.Length)))}",
            System.Collections.IEnumerable e => "[" + string.Join(", ", e.Cast<object?>().Take(16).Select(x => Show(c, x))) + "]",
            _ => (v.GetType().GetProperties().FirstOrDefault(p => typeof(IFormLinkGetter).IsAssignableFrom(p.PropertyType)) is { } lp
                  ? $"{RecType(v)}({Show(c, lp.GetValue(v))})" : v.ToString()) ?? "",
        };
        return s.Length > 300 ? s.Substring(0, 300) : s;
    }
}
