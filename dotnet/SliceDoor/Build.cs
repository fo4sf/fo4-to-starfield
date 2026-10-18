// build / check: the link plugin of the slice's working door (docs/slice/redrocket-door.md).
//
// The plugin holds exactly:
//   - an override of the overlay worldspace (FO4CW_Commonwealth, FO4TerrainExp2.esm) and of its persistent cell, a deep
//     copy of each with no children of its own except the exterior door: a persistent reference (flag 0x400) of the
//     vanilla automatic cave load door AutoloadDoor_Cave (24F9CE:Starfield.esm), at the Fallout 4 exterior door's
//     position / 70, its rotation and scale, with an XTEL to the interior door;
//   - an override of the converted interior cell (FO4Port_RedRocket01, FO4Port.esm), a deep copy with the interior door
//     as its only child: the same base, persistent, at the Fallout 4 interior door's position / 70, with an XTEL back.
// Vanilla keeps all 45 AutoloadDoor_Cave references of its overlay worldspaces, and all 345 XTEL references in
// worldspaces, in the worldspace's persistent cell (SliceDoor sf-door, Starfield.esm 1.16.244), so the exterior door
// goes there too. FormIDs: 0x800 the exterior door, 0x801 the interior door (fixed, so plans can name them).
// Options (docs/slice/door-frames.md section 3): "persistent_cell": {"template_world": "LC172World"} gives the
// persistent cell override a vanilla world's persistent cell record (flag 0x400, DATA XCLC LTMP XCLW XILS) instead of
// the master's (ours: flag 0, DATA only; our persistent refs read unmerged in game); "probes": XMarkers from 0x802 in
// an exterior cell (an override of the master's cell record), persistent or temporary, read by the runner's getpos.
using System.Text.Json;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;

public static class Build
{
    public const uint ExteriorId = 0x800, InteriorId = 0x801;

    public static float[] Floats(JsonElement e) => e.EnumerateArray().Select(x => x.GetSingle()).ToArray();
    public static P3Float P3(JsonElement e) { var f = Floats(e); return new P3Float(f[0], f[1], f[2]); }

    public static IStarfieldModDisposableGetter Open(string path, params string[] masters) =>
        StarfieldMod.CreateFromBinaryOverlay(path, StarfieldRelease.Starfield,
            new BinaryReadParameters { MasterFlagsLookup = Inspect.Styles(masters) });

    /// <summary>The worldspace record alone: a deep copy without its exterior cell blocks and its persistent cell. A
    /// plain DeepCopy materialises every child first (core64c's FO4TerrainCore.esm: 648,358 references), so the copy
    /// leaves them out instead of clearing them afterwards; the record's own fields are copied as before.</summary>
    public static Worldspace WorldOnly(IWorldspaceGetter w) =>
        w.DeepCopy(new Worldspace.TranslationMask(defaultOn: true)
        {
            SubCells = new WorldspaceBlock.TranslationMask(defaultOn: false, onOverall: false),
            TopCell = new Cell.TranslationMask(defaultOn: false, onOverall: false),
        });

    /// <summary>A cell record without its children (persistent, temporary, navigation meshes).</summary>
    public static Cell CellOnly(ICellGetter c)
    {
        var copy = c.DeepCopy(new Cell.TranslationMask(defaultOn: true)
        {
            Persistent = false,
            Temporary = false,
            NavigationMeshes = new NavigationMesh.TranslationMask(defaultOn: false, onOverall: false),
        });
        copy.Persistent.Clear();
        copy.Temporary.Clear();
        copy.NavigationMeshes.Clear();
        return copy;
    }

    public static PlacedObject Door(FormKey key, FormKey doorBase, JsonElement side, FormKey other)
    {
        var o = new PlacedObject(key, StarfieldRelease.Starfield)
        {
            EditorID = side.GetProperty("edid").GetString(),
            Base = new FormLinkNullable<IPlaceableObjectGetter>(doorBase),
            Position = P3(side.GetProperty("pos")),
            Rotation = P3(side.GetProperty("rot")),
        };
        var scale = side.GetProperty("scale").GetSingle();
        if (Math.Abs(scale - 1f) > 1e-6) o.Scale = scale;
        var x = side.GetProperty("xtel");
        o.TeleportDestination = new TeleportDestination
        {
            Position = P3(x.GetProperty("pos")),
            Rotation = P3(x.GetProperty("rot")),
            Flags = (TeleportDestination.Flag)x.GetProperty("flags").GetUInt32(),
        };
        o.TeleportDestination.Door.SetTo(other);
        o.MajorRecordFlagsRaw |= 0x400;                       // persistent: every vanilla XTEL reference is
        return o;
    }

    /// <summary>build &lt;params.json&gt; &lt;Starfield.esm&gt; &lt;FO4TerrainExp2.esm&gt; &lt;FO4Port.esm&gt; &lt;out dir&gt;</summary>
    public static int Run(string[] args)
    {
        using var doc = JsonDocument.Parse(File.ReadAllText(args[1]));
        var p = doc.RootElement;
        string S(JsonElement e, string k) => e.GetProperty(k).GetString()!;
        var outDir = args[5];
        using var sf = StarfieldMod.CreateFromBinaryOverlay(args[2], StarfieldRelease.Starfield);
        using var exp2 = Open(args[3], "Starfield.esm");
        using var port = Open(args[4], "Starfield.esm");
        var sfKey = sf.ModKey;
        var modKey = ModKey.FromFileName(S(p, "plugin"));
        var mod = new StarfieldMod(modKey, StarfieldRelease.Starfield);
        mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;

        // the door base: a vanilla DOOR, checked to be what the params say it is
        var db = p.GetProperty("door_base");
        var baseKey = new FormKey(ModKey.FromFileName(S(db, "plugin")), Convert.ToUInt32(S(db, "id"), 16));
        var door = sf.Doors.FirstOrDefault(d => d.FormKey == baseKey)
                   ?? throw new InvalidDataException($"door base {baseKey} is not a DOOR of {sf.ModKey}");
        if (door.EditorID != S(db, "editor_id"))
            throw new InvalidDataException($"door base {baseKey} is {door.EditorID}, params say {S(db, "editor_id")}");

        var extKey = new FormKey(modKey, ExteriorId);
        var intKey = new FormKey(modKey, InteriorId);
        var ext = Door(extKey, baseKey, p.GetProperty("outside"), intKey);
        var inn = Door(intKey, baseKey, p.GetProperty("inside"), extKey);

        // exterior: worldspace + its persistent cell, deep copies without their children, plus the door. With
        // "persistent_cell": {"template_world": ...} the persistent cell override takes the record of a vanilla world's
        // persistent cell instead (every one of Starfield.esm's 432 has record flag 0x400 and DATA XCLC LTMP XCLW XILS;
        // ours had flag 0 and DATA only, and our persistent refs read unmerged while LC172World's read merged:
        // docs/slice/door-frames.md section 3)
        var wid = S(p.GetProperty("world"), "editor_id");
        var w0 = exp2.Worldspaces.FirstOrDefault(w => w.EditorID == wid) ?? throw new InvalidDataException($"no WRLD {wid} in {exp2.ModKey}");
        if (w0.TopCell == null) throw new InvalidDataException($"{wid} has no persistent cell");
        var w = WorldOnly(w0);
        w.SubCells.Clear();
        var top = CellOnly(w0.TopCell);
        string topFrom = $"{exp2.ModKey}";
        if (p.TryGetProperty("persistent_cell", out var pc))
        {
            var tw = S(pc, "template_world");
            var t0 = sf.Worldspaces.FirstOrDefault(x => x.EditorID == tw)?.TopCell
                     ?? throw new InvalidDataException($"no persistent cell of WRLD {tw} in {sf.ModKey}");
            top = (Cell)CellOnly(t0).Duplicate(w0.TopCell.FormKey);
            top.MajorRecordFlagsRaw = t0.MajorRecordFlagsRaw & ~0x40000;     // 0x400 persistent (compression aside)
            topFrom = $"{tw}'s persistent cell {t0.FormKey}";
        }
        top.Persistent.Add(ext);
        w.TopCell = top;

        // probes (optional): XMarkers in an exterior cell of the world, persistent (the cell's persistent children) or
        // temporary: where the engine reports each after the merge tells which storage it moves (runner door_trip probes)
        uint nextId = InteriorId + 1;
        var probeLines = new List<string>();
        if (p.TryGetProperty("probes", out var probes) && probes.GetArrayLength() > 0)
        {
            var byCell = new Dictionary<(int, int), Cell>();
            foreach (var pr in probes.EnumerateArray())
            {
                var g = pr.GetProperty("cell").EnumerateArray().Select(e => e.GetInt32()).ToArray();
                if (!byCell.TryGetValue((g[0], g[1]), out var ec))
                {
                    IWorldspaceBlockGetter? blk0 = null; IWorldspaceSubBlockGetter? sub0 = null; ICellGetter? cell0 = null;
                    foreach (var bk in w0.SubCells)
                        foreach (var sb in bk.Items)
                            foreach (var cc in sb.Items)
                                if (cc.Grid?.Point.X == g[0] && cc.Grid?.Point.Y == g[1]) { blk0 = bk; sub0 = sb; cell0 = cc; }
                    if (cell0 == null || blk0 == null || sub0 == null) throw new InvalidDataException($"no exterior cell ({g[0]}, {g[1]}) in {wid}");
                    ec = CellOnly(cell0);
                    byCell[(g[0], g[1])] = ec;
                    var blk = w.SubCells.FirstOrDefault(b => b.BlockNumberX == blk0.BlockNumberX && b.BlockNumberY == blk0.BlockNumberY);
                    if (blk == null) { blk = new WorldspaceBlock { BlockNumberX = blk0.BlockNumberX, BlockNumberY = blk0.BlockNumberY, GroupType = blk0.GroupType }; w.SubCells.Add(blk); }
                    var esub = blk.Items.FirstOrDefault(s => s.BlockNumberX == sub0.BlockNumberX && s.BlockNumberY == sub0.BlockNumberY);
                    if (esub == null) { esub = new WorldspaceSubBlock { BlockNumberX = sub0.BlockNumberX, BlockNumberY = sub0.BlockNumberY, GroupType = sub0.GroupType }; blk.Items.Add(esub); }
                    esub.Items.Add(ec);
                }
                var id = Convert.ToUInt32(S(pr, "id"), 16);
                if (id != nextId) throw new InvalidDataException($"probe id {id:X} out of order (expected {nextId:X})");
                nextId++;
                var o = new PlacedObject(new FormKey(modKey, id), StarfieldRelease.Starfield)
                {
                    EditorID = S(pr, "edid"),
                    Base = new FormLinkNullable<IPlaceableObjectGetter>(new FormKey(sfKey, Convert.ToUInt32(S(pr, "base"), 16))),
                    Position = P3(pr.GetProperty("pos")),
                    Rotation = new P3Float(0, 0, 0),
                };
                if (pr.GetProperty("persistent").GetBoolean()) { o.MajorRecordFlagsRaw |= 0x400; ec.Persistent.Add(o); }
                else ec.Temporary.Add(o);
                probeLines.Add($"probe {o.FormKey} {o.EditorID} {(pr.GetProperty("persistent").GetBoolean() ? "persistent" : "temporary")} in ({g[0]}, {g[1]}) at {o.Position}");
            }
        }
        mod.Worldspaces.Add(w);

        // interior: the converted cell, a deep copy without its children, plus the door
        var cid = S(p.GetProperty("interior"), "editor_id");
        var c0 = port.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells).FirstOrDefault(c => c.EditorID == cid)
                 ?? throw new InvalidDataException($"no CELL {cid} in {port.ModKey}");
        var cell = CellOnly(c0);
        cell.Persistent.Add(inn);
        var n = cell.FormKey.ID;
        var block = new CellBlock { BlockNumber = (int)(n % 10), GroupType = GroupTypeEnum.InteriorCellBlock };
        var sub = new CellSubBlock { BlockNumber = (int)((n / 10) % 10), GroupType = GroupTypeEnum.InteriorCellSubBlock };
        sub.Cells.Add(cell);
        block.SubBlocks.Add(sub);
        mod.Cells.Records.Add(block);

        mod.ModHeader.Stats.NextFormID = nextId;
        Directory.CreateDirectory(outDir);
        var path = Path.Combine(outDir, modKey.FileName);
        // masters in the load order the runner produces: Starfield.esm, FO4TerrainExp2.esm (..._Mars), FO4Port.esm, this
        mod.BeginWrite.ToPath(path).WithLoadOrder(sfKey, exp2.ModKey, port.ModKey)
            .WithKnownMasters(new KeyedMasterStyle(sfKey, MasterStyle.Full), new KeyedMasterStyle(exp2.ModKey, MasterStyle.Full),
                              new KeyedMasterStyle(port.ModKey, MasterStyle.Full))
            .Write();
        Console.WriteLine($"wrote {path} ({new FileInfo(path).Length:N0} bytes): base {door.EditorID} {baseKey} (flags {door.Flags}); " +
                          $"exterior {extKey} in {wid} persistent cell {top.FormKey} (record from {topFrom}) at {ext.Position} -> {intKey}; " +
                          $"interior {intKey} in {cid} {cell.FormKey} at {inn.Position} -> {extKey}");
        foreach (var l in probeLines) Console.WriteLine("  " + l);
        return 0;
    }
}
