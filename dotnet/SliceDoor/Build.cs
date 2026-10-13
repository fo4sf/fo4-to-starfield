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

        // exterior: worldspace + its persistent cell, deep copies without their children, plus the door
        var wid = S(p.GetProperty("world"), "editor_id");
        var w0 = exp2.Worldspaces.FirstOrDefault(w => w.EditorID == wid) ?? throw new InvalidDataException($"no WRLD {wid} in {exp2.ModKey}");
        if (w0.TopCell == null) throw new InvalidDataException($"{wid} has no persistent cell");
        var w = w0.DeepCopy();
        w.SubCells.Clear();
        var top = w0.TopCell.DeepCopy();
        top.Persistent.Clear();
        top.Temporary.Clear();
        top.NavigationMeshes.Clear();
        top.Persistent.Add(ext);
        w.TopCell = top;
        mod.Worldspaces.Add(w);

        // interior: the converted cell, a deep copy without its children, plus the door
        var cid = S(p.GetProperty("interior"), "editor_id");
        var c0 = port.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells).FirstOrDefault(c => c.EditorID == cid)
                 ?? throw new InvalidDataException($"no CELL {cid} in {port.ModKey}");
        var cell = c0.DeepCopy();
        cell.Persistent.Clear();
        cell.Temporary.Clear();
        cell.NavigationMeshes.Clear();
        cell.Persistent.Add(inn);
        var n = cell.FormKey.ID;
        var block = new CellBlock { BlockNumber = (int)(n % 10), GroupType = GroupTypeEnum.InteriorCellBlock };
        var sub = new CellSubBlock { BlockNumber = (int)((n / 10) % 10), GroupType = GroupTypeEnum.InteriorCellSubBlock };
        sub.Cells.Add(cell);
        block.SubBlocks.Add(sub);
        mod.Cells.Records.Add(block);

        mod.ModHeader.Stats.NextFormID = InteriorId + 1;
        Directory.CreateDirectory(outDir);
        var path = Path.Combine(outDir, modKey.FileName);
        // masters in the load order the runner produces: Starfield.esm, FO4TerrainExp2.esm (..._Mars), FO4Port.esm, this
        mod.BeginWrite.ToPath(path).WithLoadOrder(sfKey, exp2.ModKey, port.ModKey)
            .WithKnownMasters(new KeyedMasterStyle(sfKey, MasterStyle.Full), new KeyedMasterStyle(exp2.ModKey, MasterStyle.Full),
                              new KeyedMasterStyle(port.ModKey, MasterStyle.Full))
            .Write();
        Console.WriteLine($"wrote {path} ({new FileInfo(path).Length:N0} bytes): base {door.EditorID} {baseKey} (flags {door.Flags}); " +
                          $"exterior {extKey} in {wid} persistent cell {top.FormKey} at {ext.Position} -> {intKey}; " +
                          $"interior {intKey} in {cid} {cell.FormKey} at {inn.Position} -> {extKey}");
        return 0;
    }
}
