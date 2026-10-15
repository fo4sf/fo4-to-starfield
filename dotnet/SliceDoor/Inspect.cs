// Read-only inspection verbs of SliceDoor (docs/slice/redrocket-door.md). Nothing is written except the JSON a verb is
// asked to write (into a staging folder outside the repository: it is derived game data).
using System.Text.Json;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Records;
using Noggog;
using Fo4 = Mutagen.Bethesda.Fallout4;
using Sf = Mutagen.Bethesda.Starfield;

public static class Inspect
{
    static readonly JsonSerializerOptions Pretty = new() { WriteIndented = true };

    public static float[] V(P3Float p) => new[] { p.X, p.Y, p.Z };

    // ------------------------------------------------------------------------------------------------ Fallout 4 source
    /// <summary>fo4 &lt;Fallout4.esm&gt; &lt;out.json&gt; [interior door] [exterior door]: the two ends of the Red Rocket cave
    /// link as Fallout4.esm stores them (FormIDs 05E844 / 08EB65 by default), their DOOR base and their cells.</summary>
    public static int Fallout4Source(string[] args)
    {
        var esm = args[1];
        var outPath = args[2];
        uint inner = args.Length > 3 ? Convert.ToUInt32(args[3], 16) : 0x05E844;
        uint outer = args.Length > 4 ? Convert.ToUInt32(args[4], 16) : 0x08EB65;
        using var mod = Fo4.Fallout4Mod.CreateFromBinaryOverlay(esm, Fo4.Fallout4Release.Fallout4);
        var found = new Dictionary<uint, object>();
        var bases = new HashSet<FormKey>();

        object RefJson(Fo4.IPlacedObjectGetter r, string where, Fo4.ICellGetter c, bool persistent)
        {
            bases.Add(r.Base.FormKey);
            var t = r.TeleportDestination;
            return new
            {
                formid = r.FormKey.ID.ToString("X6"),
                where,
                cell_formid = c.FormKey.ID.ToString("X6"),
                cell_editor_id = c.EditorID,
                cell_grid = c.Grid is { } g ? new[] { g.Point.X, g.Point.Y } : null,
                persistent_group = persistent,
                record_flags = r.MajorRecordFlagsRaw,
                @base = r.Base.FormKey.ID.ToString("X6"),
                pos = V(r.Position),
                rot = V(r.Rotation),
                scale = r.Scale,
                xtel = t == null ? null : new
                {
                    door = t.Door.FormKey.ID.ToString("X6"),
                    pos = V(t.Position),
                    rot = V(t.Rotation),
                    flags = (uint)t.Flags,
                    transition_interior = t.TransitionInterior.IsNull ? null : t.TransitionInterior.FormKey.ID.ToString("X6"),
                },
            };
        }
        void Scan(Fo4.ICellGetter c, string where)
        {
            foreach (var r in c.Persistent.OfType<Fo4.IPlacedObjectGetter>())
                if (r.FormKey.ID == inner || r.FormKey.ID == outer) found[r.FormKey.ID] = RefJson(r, where, c, true);
            foreach (var r in c.Temporary.OfType<Fo4.IPlacedObjectGetter>())
                if (r.FormKey.ID == inner || r.FormKey.ID == outer) found[r.FormKey.ID] = RefJson(r, where, c, false);
        }
        foreach (var c in mod.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells)) Scan(c, "interior");
        foreach (var w in mod.Worldspaces)
        {
            if (w.TopCell != null) Scan(w.TopCell, $"{w.EditorID} persistent cell");
            foreach (var c in w.SubCells.SelectMany(b => b.Items).SelectMany(s => s.Items)) Scan(c, $"{w.EditorID} exterior");
        }
        var doors = new List<object>();
        foreach (var bk in bases)
        {
            var d = mod.Doors.FirstOrDefault(x => x.FormKey == bk);
            if (d == null) { doors.Add(new { formid = bk.ID.ToString("X6"), type = "not a DOOR of this plugin" }); continue; }
            doors.Add(new
            {
                formid = d.FormKey.ID.ToString("X6"),
                editor_id = d.EditorID,
                name = d.Name?.String,
                model = d.Model?.File.ToString(),
                flags = d.Flags.ToString(),
                flags_raw = (int)d.Flags,
                obnd = d.ObjectBounds is { } b ? new[] { new[] { b.First.X, b.First.Y, b.First.Z }, new[] { b.Second.X, b.Second.Y, b.Second.Z } } : null,
                scripts = d.VirtualMachineAdapter?.Scripts.Select(s => s.Name).ToArray(),
                keywords = d.Keywords?.Select(k => k.FormKey.ID.ToString("X6")).ToArray(),
            });
        }
        var doc = new
        {
            source = Path.GetFileName(esm),
            units = "Fallout 4 units (70 per metre), rotations in radians",
            refs = found.OrderBy(k => k.Key).Select(k => k.Value).ToList(),
            door_bases = doors,
        };
        File.WriteAllText(outPath, JsonSerializer.Serialize(doc, Pretty));
        Console.WriteLine(JsonSerializer.Serialize(doc, Pretty));
        return found.Count == 2 ? 0 : 1;
    }

    // ------------------------------------------------------------------------------------------- Starfield load doors
    /// <summary>sf-door &lt;Starfield.esm&gt; &lt;out.json&gt; [base hex]: the vanilla automatic cave load door (AutoloadDoor_Cave
    /// 24F9CE): its record, every reference (interior or worldspace, persistent cell or exterior cell, overlay world or
    /// not), the reference at the other end and where the arrival point lies relative to it; plus where vanilla keeps the
    /// XTEL doors of overlay worldspaces (the persistent cell or an exterior cell).</summary>
    public static int SfDoor(string[] args)
    {
        var esm = args[1];
        var outPath = args[2];
        uint baseId = args.Length > 3 ? Convert.ToUInt32(args[3], 16) : 0x24F9CE;
        using var mod = Sf.StarfieldMod.CreateFromBinaryOverlay(esm, Sf.StarfieldRelease.Starfield);
        var door = mod.Doors.First(d => d.FormKey.ID == baseId);
        var all = new Dictionary<FormKey, (Sf.IPlacedObjectGetter r, string cell, string world, bool top, bool persistent, bool overlay, int[]? grid)>();
        void Take(Sf.ICellGetter c, string world, bool top, bool overlay)
        {
            var grid = c.Grid is { } g ? new[] { g.Point.X, g.Point.Y } : null;
            foreach (var r in c.Persistent.OfType<Sf.IPlacedObjectGetter>()) all.TryAdd(r.FormKey, (r, c.EditorID ?? c.FormKey.ToString(), world, top, true, overlay, grid));
            foreach (var r in c.Temporary.OfType<Sf.IPlacedObjectGetter>()) all.TryAdd(r.FormKey, (r, c.EditorID ?? c.FormKey.ToString(), world, top, false, overlay, grid));
        }
        foreach (var c in mod.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells)) Take(c, "", false, false);
        foreach (var w in mod.Worldspaces)
        {
            bool overlay = w.Components.OfType<Sf.IWorldSpaceOverlayComponentGetter>().Any();
            if (w.TopCell != null) Take(w.TopCell, w.EditorID ?? "", true, overlay);
            foreach (var c in w.SubCells.SelectMany(b => b.Items).SelectMany(s => s.Items)) Take(c, w.EditorID ?? "", false, overlay);
        }
        object Where((Sf.IPlacedObjectGetter r, string cell, string world, bool top, bool persistent, bool overlay, int[]? grid) x) => new
        {
            formid = x.r.FormKey.ID.ToString("X6"),
            cell = x.cell,
            world = x.world,
            in_world_persistent_cell = x.top,
            persistent_group = x.persistent,
            overlay_world = x.overlay,
            grid = x.grid,
            record_flags = x.r.MajorRecordFlagsRaw,
            @base = x.r.Base.FormKey.ID.ToString("X6"),
            pos = V(x.r.Position),
            rot = V(x.r.Rotation),
            scale = x.r.Scale,
        };
        var refs = new List<object>();
        int worldRefs = 0, worldTop = 0, worldExt = 0, interiorRefs = 0, overlayRefs = 0;
        var scales = new List<float>();
        foreach (var x in all.Values.Where(x => x.r.Base.FormKey == door.FormKey))
        {
            var t = x.r.TeleportDestination;
            object? dest = null;
            double? arrToDest = null;
            if (t != null && all.TryGetValue(t.Door.FormKey, out var d))
            {
                dest = Where(d);
                var p = d.r.Position;
                arrToDest = Math.Sqrt(Math.Pow(t.Position.X - p.X, 2) + Math.Pow(t.Position.Y - p.Y, 2) + Math.Pow(t.Position.Z - p.Z, 2));
            }
            if (x.world == "") interiorRefs++; else { worldRefs++; if (x.top) worldTop++; else worldExt++; }
            if (x.overlay) overlayRefs++;
            scales.Add(x.r.Scale ?? 1f);
            refs.Add(new
            {
                at = Where(x),
                xtel = t == null ? null : new { door = t.Door.FormKey.ID.ToString("X6"), pos = V(t.Position), rot = V(t.Rotation), flags = (uint)t.Flags },
                destination = dest,
                arrival_to_destination_door_m = arrToDest,
            });
        }
        // XTEL doors of overlay worldspaces (any base): which cell vanilla keeps them in
        var ovl = all.Values.Where(x => x.overlay && x.r.TeleportDestination != null).ToList();
        var ovlSummary = new
        {
            xtel_refs = ovl.Count,
            in_world_persistent_cell = ovl.Count(x => x.top),
            in_exterior_cell_persistent_group = ovl.Count(x => !x.top && x.persistent),
            in_exterior_cell_temporary_group = ovl.Count(x => !x.top && !x.persistent),
            worlds = ovl.GroupBy(x => x.world).OrderByDescending(g => g.Count()).Take(12).Select(g => new { world = g.Key, n = g.Count() }).ToList(),
            examples = ovl.Take(8).Select(x => new
            {
                at = Where(x),
                xtel = new { door = x.r.TeleportDestination!.Door.FormKey.ID.ToString("X6"), pos = V(x.r.TeleportDestination.Position) },
                destination = all.TryGetValue(x.r.TeleportDestination.Door.FormKey, out var dd) ? Where(dd) : null,
            }).ToList(),
        };
        // every XTEL ref in a worldspace (not only overlays): persistent cell vs exterior cell
        var wx = all.Values.Where(x => x.world != "" && x.r.TeleportDestination != null).ToList();
        var vmad = door.VirtualMachineAdapter;
        var doc = new
        {
            source = Path.GetFileName(esm),
            door = new
            {
                formid = door.FormKey.ID.ToString("X6"),
                editor_id = door.EditorID,
                name = door.Name?.String,
                model = door.Model?.File.ToString(),
                flags = door.Flags.ToString(),
                flags_raw = (int)door.Flags,
                obnd = door.ObjectBounds is { } b ? new[] { V(b.First), V(b.Second) } : null,
                sound_level = door.SoundLevel.ToString(),
                facing = door.FacingAxisOverride.ToString(),
                open_sound = door.OpenSound?.ToString(),
                close_sound = door.CloseSound?.ToString(),
                components = door.Components.Select(c => c.GetType().Name.Replace("BinaryOverlay", "")).ToArray(),
                keywords = door.Keywords?.Select(k => k.FormKey.ID.ToString("X6")).ToArray(),
                scripts = vmad?.Scripts.Select(s => new
                {
                    name = s.Name,
                    flags = s.Flags.ToString(),
                    properties = s.Properties.Select(p => new { name = p.Name, type = p.GetType().Name.Replace("BinaryOverlay", ""), value = PropValue(p) }).ToArray(),
                }).ToArray(),
            },
            refs_total = refs.Count,
            refs_interior = interiorRefs,
            refs_world = worldRefs,
            refs_world_persistent_cell = worldTop,
            refs_world_exterior_cell = worldExt,
            refs_in_overlay_worlds = overlayRefs,
            scale_min = scales.Count > 0 ? scales.Min() : 0,
            scale_max = scales.Count > 0 ? scales.Max() : 0,
            world_xtel_refs = new { n = wx.Count, in_world_persistent_cell = wx.Count(x => x.top), in_exterior_cell = wx.Count(x => !x.top) },
            overlay_world_xtel = ovlSummary,
            refs,
        };
        File.WriteAllText(outPath, JsonSerializer.Serialize(doc, Pretty));
        var head = JsonSerializer.Serialize(new { doc.door, doc.refs_total, doc.refs_interior, doc.refs_world, doc.refs_world_persistent_cell, doc.refs_world_exterior_cell, doc.refs_in_overlay_worlds, doc.scale_min, doc.scale_max, doc.world_xtel_refs, doc.overlay_world_xtel }, Pretty);
        Console.WriteLine(head);
        return 0;
    }

    static string PropValue(Sf.IScriptPropertyGetter p) => p switch
    {
        Sf.IScriptObjectPropertyGetter o => o.Object.FormKey.ToString(),
        Sf.IScriptIntPropertyGetter i => i.Data.ToString(),
        Sf.IScriptFloatPropertyGetter f => f.Data.ToString(System.Globalization.CultureInfo.InvariantCulture),
        Sf.IScriptBoolPropertyGetter b => b.Data.ToString(),
        Sf.IScriptStringPropertyGetter s => s.Data,
        _ => p.GetType().Name,
    };

    // ------------------------------------------------------------------------------------------------- our build side
    public static Cache<IModMasterStyledGetter, ModKey> Styles(params string[] masters)
    {
        var c = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        foreach (var m in masters) c.Set(new KeyedMasterStyle(ModKey.FromFileName(m), MasterStyle.Full));
        return c;
    }

    /// <summary>port &lt;FO4Port.esm&gt; &lt;cell EditorID&gt; &lt;out.json&gt; [x y z radius]: the converted interior cell as the
    /// pinned build holds it: the CELL, its reference counts, every reference with an XTEL or a DOOR base, and every
    /// reference within radius metres of (x, y, z) (where the Fallout 4 load door stood).</summary>
    public static int Port(string[] args)
    {
        var esm = args[1];
        var cellId = args[2];
        var outPath = args[3];
        float[] at = args.Length > 6 ? new[] { float.Parse(args[4], System.Globalization.CultureInfo.InvariantCulture), float.Parse(args[5], System.Globalization.CultureInfo.InvariantCulture), float.Parse(args[6], System.Globalization.CultureInfo.InvariantCulture) } : new[] { 0f, 0f, 0f };
        float radius = args.Length > 7 ? float.Parse(args[7], System.Globalization.CultureInfo.InvariantCulture) : 3f;
        using var mod = Sf.StarfieldMod.CreateFromBinaryOverlay(esm, Sf.StarfieldRelease.Starfield,
            new BinaryReadParameters { MasterFlagsLookup = Styles("Starfield.esm") });
        var doors = mod.Doors.ToDictionary(d => d.FormKey, d => d.EditorID ?? "");
        var cells = mod.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells).ToList();
        var cell = cells.FirstOrDefault(c => string.Equals(c.EditorID, cellId, StringComparison.OrdinalIgnoreCase));
        if (cell == null) { Console.Error.WriteLine($"no cell {cellId} in {esm}"); return 1; }
        var refs = cell.Persistent.OfType<Sf.IPlacedObjectGetter>().Select(r => (r, persistent: true))
            .Concat(cell.Temporary.OfType<Sf.IPlacedObjectGetter>().Select(r => (r, persistent: false))).ToList();
        var stats = mod.Statics.ToDictionary(s => s.FormKey, s => s.EditorID ?? "");
        string BaseName(FormKey k) => doors.TryGetValue(k, out var d) ? "DOOR " + d : stats.TryGetValue(k, out var s) ? "STAT " + s : k.ToString();
        object J((Sf.IPlacedObjectGetter r, bool persistent) x) => new
        {
            formid = x.r.FormKey.ID.ToString("X6"),
            persistent = x.persistent,
            record_flags = x.r.MajorRecordFlagsRaw,
            @base = x.r.Base.FormKey.ToString(),
            base_name = BaseName(x.r.Base.FormKey),
            pos = V(x.r.Position),
            rot = V(x.r.Rotation),
            scale = x.r.Scale,
            xtel = x.r.TeleportDestination is { } t ? new { door = t.Door.FormKey.ToString(), pos = V(t.Position) } : null,
            dist_m = Math.Sqrt(Math.Pow(x.r.Position.X - at[0], 2) + Math.Pow(x.r.Position.Y - at[1], 2) + Math.Pow(x.r.Position.Z - at[2], 2)),
        };
        var doc = new
        {
            source = Path.GetFileName(esm),
            masters = mod.ModHeader.MasterReferences.Select(m => m.Master.FileName.String).ToArray(),
            header_flags = mod.ModHeader.Flags.ToString(),
            cell = new { formid = cell.FormKey.ID.ToString("X6"), editor_id = cell.EditorID, flags = cell.Flags.ToString() },
            refs_persistent = cell.Persistent.Count,
            refs_temporary = cell.Temporary.Count,
            xtel_refs = refs.Where(x => x.r.TeleportDestination != null).Select(J).ToList(),
            door_based_refs = refs.Where(x => doors.ContainsKey(x.r.Base.FormKey)).Select(J).ToList(),
            near = new { at, radius, refs = refs.Where(x => Math.Sqrt(Math.Pow(x.r.Position.X - at[0], 2) + Math.Pow(x.r.Position.Y - at[1], 2) + Math.Pow(x.r.Position.Z - at[2], 2)) <= radius).Select(J).ToList() },
            door_records = mod.Doors.Count,
            plugin_xtel_refs = cells.Sum(c => c.Persistent.Concat(c.Temporary).OfType<Sf.IPlacedObjectGetter>().Count(r => r.TeleportDestination != null)),
        };
        File.WriteAllText(outPath, JsonSerializer.Serialize(doc, Pretty));
        Console.WriteLine(JsonSerializer.Serialize(new { doc.source, doc.masters, doc.header_flags, doc.cell, doc.refs_persistent, doc.refs_temporary, doc.xtel_refs, doc.door_based_refs, doc.near, doc.door_records, doc.plugin_xtel_refs }, Pretty));
        return 0;
    }
}
