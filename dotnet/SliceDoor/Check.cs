// check: the slice door plugin read back with its masters (Mutagen binary overlays and a link cache over the load order
// Starfield.esm, FO4TerrainExp2.esm, FO4Port.esm, the plugin). Writes a JSON report; exit 0 only when every check holds.
using System.Text.Json;
using Mutagen.Bethesda;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Cache;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;

public static class Check
{
    sealed record Item(string name, bool ok, string detail);

    static List<string> Differences(object a, object b)
    {
        var out_ = new List<string>();
        foreach (var p in a.GetType().GetProperties().Where(p => p.GetIndexParameters().Length == 0))
        {
            object? x, y;
            try { x = p.GetValue(a); y = p.GetValue(b); } catch { continue; }
            if (!Equals(x, y) && !(x is System.Collections.IEnumerable ex && y is System.Collections.IEnumerable ey && x is not string
                                   && ex.Cast<object?>().SequenceEqual(ey.Cast<object?>())))
                out_.Add(p.Name);
        }
        return out_;
    }

    static bool Near(P3Float a, JsonElement e, float tol = 1e-4f)
    {
        var f = Build.Floats(e);
        return Math.Abs(a.X - f[0]) <= tol && Math.Abs(a.Y - f[1]) <= tol && Math.Abs(a.Z - f[2]) <= tol;
    }

    /// <summary>check &lt;plugin&gt; &lt;Starfield.esm&gt; &lt;FO4TerrainExp2.esm&gt; &lt;FO4Port.esm&gt; &lt;params.json&gt; &lt;out.json&gt;</summary>
    public static int Run(string[] args)
    {
        using var pdoc = JsonDocument.Parse(File.ReadAllText(args[5]));
        var p = pdoc.RootElement;
        using var sf = StarfieldMod.CreateFromBinaryOverlay(args[2], StarfieldRelease.Starfield);
        using var exp2 = Build.Open(args[3], "Starfield.esm");
        using var port = Build.Open(args[4], "Starfield.esm");
        using var mod = Build.Open(args[1], "Starfield.esm", exp2.ModKey.FileName, port.ModKey.FileName);
        var items = new List<Item>();
        void Add(string name, bool ok, string detail) => items.Add(new Item(name, ok, detail));

        var masters = mod.ModHeader.MasterReferences.Select(m => m.Master.FileName.String).ToArray();
        Add("masters", masters.SequenceEqual(new[] { "Starfield.esm", exp2.ModKey.FileName.String, port.ModKey.FileName.String }),
            string.Join(", ", masters));
        Add("esm flag", mod.ModHeader.Flags.HasFlag(StarfieldModHeader.HeaderFlag.Master), mod.ModHeader.Flags.ToString());

        // exactly the records the plugin is meant to hold
        var all = mod.EnumerateMajorRecords().ToList();
        var kinds = all.GroupBy(r => r.GetType().Name.Replace("BinaryOverlay", "")).ToDictionary(g => g.Key, g => g.Count());
        // probes (optional): one exterior cell override per probe cell, one reference per probe
        var probes = p.TryGetProperty("probes", out var pe) ? pe.EnumerateArray().ToList() : new List<JsonElement>();
        var probeCells = probes.Select(x => string.Join(",", x.GetProperty("cell").EnumerateArray().Select(e => e.GetInt32()))).Distinct().Count();
        var template = p.TryGetProperty("persistent_cell", out var pc) ? pc.GetProperty("template_world").GetString() : null;
        Add("record set", all.Count == 5 + probeCells + probes.Count && kinds.GetValueOrDefault("Worldspace") == 1
                          && kinds.GetValueOrDefault("Cell") == 2 + probeCells && kinds.GetValueOrDefault("PlacedObject") == 2 + probes.Count,
            string.Join(", ", kinds.OrderBy(k => k.Key).Select(k => $"{k.Key} {k.Value}")));

        var wid = p.GetProperty("world").GetProperty("editor_id").GetString();
        var cid = p.GetProperty("interior").GetProperty("editor_id").GetString();
        var w = mod.Worldspaces.FirstOrDefault();
        var w0 = exp2.Worldspaces.FirstOrDefault(x => x.EditorID == wid);
        var cell = mod.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells).FirstOrDefault();
        var c0 = port.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells).FirstOrDefault(x => x.EditorID == cid);
        if (w == null || w0 == null || cell == null || c0 == null || w.TopCell == null || w0.TopCell == null)
        {
            Add("records found", false, $"world {w?.FormKey} / {w0?.FormKey}, cell {cell?.FormKey} / {c0?.FormKey}");
            return Report(args[6], items);
        }
        // the overrides are the masters' own records: same FormKey, every field equal (children aside)
        Add("world override", w.FormKey == w0.FormKey && w.EditorID == wid, $"{w.FormKey} {w.EditorID}");
        // record-only copies (Build.WorldOnly / CellOnly): a full DeepCopy of the master's world would materialise
        // every exterior reference first (core64c: 648,358)
        var wa = Build.WorldOnly(w0); wa.SubCells.Clear(); wa.TopCell = null;
        var wb = Build.WorldOnly(w); wb.SubCells.Clear(); wb.TopCell = null;
        Add("world override equals its master's record", wa.Equals(wb), string.Join(", ", Differences(wa, wb)));
        var extCells = w.SubCells.SelectMany(b => b.Items).SelectMany(s => s.Items).ToList();
        Add("world has no exterior cells of its own except the probe cells", extCells.Count == probeCells, $"{extCells.Count} cells");
        foreach (var ec in extCells)
        {
            var m0 = w0.SubCells.SelectMany(b => b.Items).SelectMany(s => s.Items).FirstOrDefault(c => c.FormKey == ec.FormKey);
            Add($"probe cell {ec.FormKey} equals its master's record", m0 != null && Build.CellOnly(m0).Equals(Build.CellOnly(ec)),
                m0 == null ? "not in the master" : string.Join(", ", Differences(Build.CellOnly(m0), Build.CellOnly(ec))));
        }
        Add("persistent cell override", w.TopCell.FormKey == w0.TopCell.FormKey, $"{w.TopCell.FormKey}");
        var tb = Build.CellOnly(w.TopCell);
        if (template == null)
        {
            var ta = Build.CellOnly(w0.TopCell);
            Add("persistent cell equals its master's record", ta.Equals(tb), string.Join(", ", Differences(ta, tb)));
        }
        else
        {
            // the vanilla shape: the template world's persistent cell record, under our master's FormKey
            var t0 = sf.Worldspaces.FirstOrDefault(x => x.EditorID == template)?.TopCell;
            var ta = t0 == null ? null : (Cell)Build.CellOnly(t0).Duplicate(w.TopCell.FormKey);
            if (ta != null) { ta.MajorRecordFlagsRaw &= ~0x40000; tb.MajorRecordFlagsRaw &= ~0x40000; }   // compression aside
            Add($"persistent cell equals {template}'s persistent cell record (the vanilla shape, compression aside)", ta != null && ta.Equals(tb),
                ta == null ? "no template" : string.Join(", ", Differences(ta, tb)));
            Add("persistent cell record flag 0x400 (as all 432 vanilla persistent cells)", (w.TopCell.MajorRecordFlagsRaw & 0x400) != 0,
                $"0x{w.TopCell.MajorRecordFlagsRaw:X}");
            Add("persistent cell XCLC: the no-grid sentinel", w.TopCell.Grid?.Point.X == int.MaxValue && w.TopCell.Grid?.Point.Y == int.MaxValue,
                $"{w.TopCell.Grid?.Point}");
        }
        Add("interior cell override", cell.FormKey == c0.FormKey && cell.EditorID == cid, $"{cell.FormKey} {cell.EditorID}");
        var ca = Build.CellOnly(c0);
        var cb = Build.CellOnly(cell);
        Add("interior cell equals its master's record", ca.Equals(cb), string.Join(", ", Differences(ca, cb)));

        // the two doors: persistent, the vanilla automatic door, linked both ways
        // probes as staged: their cell, persistence, base and position
        foreach (var pr in probes)
        {
            var id = Convert.ToUInt32(pr.GetProperty("id").GetString(), 16);
            var g = pr.GetProperty("cell").EnumerateArray().Select(e => e.GetInt32()).ToArray();
            var ec = extCells.FirstOrDefault(c => c.Grid?.Point.X == g[0] && c.Grid?.Point.Y == g[1]);
            var pers = pr.GetProperty("persistent").GetBoolean();
            var r = ec == null ? null : (pers ? ec.Persistent : ec.Temporary).OfType<IPlacedObjectGetter>().FirstOrDefault(x => x.FormKey.ID == id);
            Add($"probe {id:X6} {(pers ? "persistent" : "temporary")} in ({g[0]}, {g[1]}) as staged",
                r != null && Near(r.Position, pr.GetProperty("pos")) && r.Base.FormKey.ID == Convert.ToUInt32(pr.GetProperty("base").GetString(), 16)
                && ((r.MajorRecordFlagsRaw & 0x400) != 0) == pers,
                r == null ? "missing" : $"{r.FormKey} base {r.Base.FormKey} at {r.Position} flags 0x{r.MajorRecordFlagsRaw:X}");
        }
        var ext = w.TopCell.Persistent.OfType<IPlacedObjectGetter>().ToList();
        var inn = cell.Persistent.OfType<IPlacedObjectGetter>().ToList();
        Add("exterior door: one persistent reference, nothing temporary", ext.Count == 1 && w.TopCell.Temporary.Count == 0,
            $"{ext.Count} persistent, {w.TopCell.Temporary.Count} temporary");
        Add("interior door: one persistent reference, nothing temporary", inn.Count == 1 && cell.Temporary.Count == 0,
            $"{inn.Count} persistent, {cell.Temporary.Count} temporary");
        if (ext.Count != 1 || inn.Count != 1) return Report(args[6], items);
        var cache = new IStarfieldModGetter[] { sf, exp2, port, mod }.ToImmutableLinkCache<IStarfieldMod, IStarfieldModGetter>();
        var db = p.GetProperty("door_base");
        foreach (var (name, r, other, side) in new[] { ("exterior", ext[0], inn[0], "outside"), ("interior", inn[0], ext[0], "inside") })
        {
            var s = p.GetProperty(side);
            var baseOk = cache.TryResolve<IDoorGetter>(r.Base.FormKey, out var d);
            Add($"{name} door base resolves to a DOOR", baseOk && d!.EditorID == db.GetProperty("editor_id").GetString()
                                                         && d.Flags.ToString().Contains("Automatic"),
                $"{r.Base.FormKey} {d?.EditorID} flags {d?.Flags}");
            Add($"{name} door persistent (0x400)", (r.MajorRecordFlagsRaw & 0x400) != 0, $"0x{r.MajorRecordFlagsRaw:X}");
            var t = r.TeleportDestination;
            Add($"{name} door XTEL names the other door", t != null && t.Door.FormKey == other.FormKey,
                $"{t?.Door.FormKey} (other {other.FormKey})");
            var resolved = t != null && cache.TryResolve<IPlacedObjectGetter>(t.Door.FormKey, out var dest) && dest.FormKey == other.FormKey;
            Add($"{name} door XTEL resolves in the load order", resolved, $"{t?.Door.FormKey}");
            Add($"{name} door XTEL back-link", other.TeleportDestination?.Door.FormKey == r.FormKey, $"{other.TeleportDestination?.Door.FormKey}");
            Add($"{name} door placement as staged", Near(r.Position, s.GetProperty("pos")) && Near(r.Rotation, s.GetProperty("rot"))
                                                    && Math.Abs((r.Scale ?? 1f) - s.GetProperty("scale").GetSingle()) <= 1e-5,
                $"pos {r.Position} rot {r.Rotation} scale {r.Scale}");
            Add($"{name} door XTEL as staged", t != null && Near(t.Position, s.GetProperty("xtel").GetProperty("pos"))
                                                && Near(t.Rotation, s.GetProperty("xtel").GetProperty("rot"))
                                                && (uint)t.Flags == s.GetProperty("xtel").GetProperty("flags").GetUInt32()
                                                && t.TransitionInterior.IsNull,
                $"arrive {t?.Position} rot {t?.Rotation} flags {t?.Flags}");
        }
        // the winning records in the load order are ours (the masters' WRLD / CELL records are overridden, not duplicated)
        Add("load order: the world resolves to this plugin's override",
            cache.TryResolveContext<IWorldspace, IWorldspaceGetter>(w.FormKey, out var wctx) && wctx.ModKey == mod.ModKey,
            $"{wctx?.ModKey}");
        Add("load order: the interior cell resolves to this plugin's override",
            cache.TryResolveContext<ICell, ICellGetter>(cell.FormKey, out var cctx) && cctx.ModKey == mod.ModKey, $"{cctx?.ModKey}");
        return Report(args[6], items);
    }

    static int Report(string path, List<Item> items)
    {
        var ok = items.All(i => i.ok);
        File.WriteAllText(path, JsonSerializer.Serialize(new { ok, checks = items }, new JsonSerializerOptions { WriteIndented = true }));
        foreach (var i in items) Console.WriteLine($"{(i.ok ? "PASS" : "FAIL")}  {i.name}: {i.detail}");
        Console.WriteLine(ok ? $"all {items.Count} checks pass" : $"{items.Count(i => !i.ok)} of {items.Count} checks FAIL");
        return ok ? 0 : 1;
    }
}
