// Terrain experiment 2 (docs/terrain/experiment2.md, docs/terrain/overlay-records.md): one worldspace with the real
// Commonwealth heights around Red Rocket.
//   dotnet run -- <Starfield.esm> <staging dir>
// Reads <staging dir>/exp2_params.json (written by scripts/terrain/make_exp2.py build|restage) and writes
// FO4TerrainExp2.esm (master Starfield.esm, own FormIDs from 0x800, nothing shared with FO4Port.esm) and, when the
// params hold "mars", FO4TerrainExp2_Mars.esm (override of MarsPlanetData that registers the worldspace on Mars).
// Nothing is deployed.
//
//   FO4CW_Commonwealth  overlay component -> SFBK FO4CW_CommonwealthBlock -> Data\TERRAIN\FO4CW_Commonwealth.btd
//                       the BTD is reachable by the record path AND by the name, like experiment 1's FO4TX_World01
// The worldspace copies the vanilla Mars landing world LC172World (02DF8C) exactly as experiment 1 does (minus cells,
// offsets and its location) so the two experiments differ only in the BTD and the cell grid; it gets every exterior
// cell the BTD covers (n x n, empty) and a COC marker 2 m above the terrain at the Red Rocket building origin.
//
// Overlay record fixes (params keys; all optional so experiment 2 as first staged can be rebuilt):
//   fnam       one raw u16 per BTD cell (the cell's SW-corner sample): DNAM.x * DNAM.y values like every vanilla SFBK
//              (without it: the 8 "connections" of the first build, 16 B, which no vanilla record has)
//   alignment  "relative" (INAM 0, vanilla LC overlays) or "absolute" (INAM 1, like NewAtlantis) with "hnam" (HNAM)
//   location   true: a Location like LC172WorldLocation (keyword LocTypeOverlay 2CA99D, parent SSol_PMars_Surface
//              01B736) referenced by the worldspace's XLCN
//   anchor     {"edid", "local": [x, y, z]}: a persistent XMarker (00003B) in the persistent cell, FormID 0x800
//   mars       {"plugin", "latitude", "longitude"}: write the Mars registration plugin (PNDT CNAM entry appended)
//   objects    "objects.json" (experiment 2c, docs/terrain/experiment2c.md, written by scripts/terrain/make_exp2c.py
//              stage): converted Fallout 4 models as STAT (or rigged DOOR) records and their references in the
//              exterior cells, {"bases": [{"edid", "model", "door"?}], "refs": [{"src", "base", "cell", "pos", "rot",
//              "scale", "disabled"}]} (metres, radians). Their FormIDs come after every terrain record, so the terrain
//              records, the anchor and the Mars plugin keep exp2b's FormIDs; <staging dir>/formids.json lists them.
//   navmesh    "navmesh.json" (experiment 2d, docs/actors/navmesh-conversion.md, written by scripts/terrain/make_exp2d.py
//              stage): converted Fallout 4 navmeshes, one NAVM per (Fallout 4 navmesh, Starfield cell), in that cell's
//              navmesh group, plus a NAVI override (000FF1:Starfield.esm) holding one NVMI per new navmesh only, as the
//              official plugins do. FormIDs after every object, so exp2c's FormIDs do not move.
using System.Text.Json;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;

var sfPath = args[0];
var outDir = args[1];
var prm = JsonDocument.Parse(File.ReadAllText(Path.Combine(outDir, "exp2_params.json"))).RootElement;
string S(string k) => prm.GetProperty(k).GetString()!;
int I(string k) => prm.GetProperty(k).GetInt32();
float F(string k) => prm.GetProperty(k).GetSingle();
float[] FA(string k) => prm.GetProperty(k).EnumerateArray().Select(e => e.GetSingle()).ToArray();
bool Has(string k) => prm.TryGetProperty(k, out var v) && v.ValueKind is not (JsonValueKind.Null or JsonValueKind.False);

var sfData = Path.GetDirectoryName(Path.GetFullPath(sfPath))!;
var release = StarfieldRelease.Starfield;
var sfEsm = ModKey.FromNameAndExtension("Starfield.esm");
using var sf = StarfieldMod.CreateFromBinaryOverlay(sfPath, release);

var templateWorld = sf.Worldspaces.First(w => w.FormKey.ID == 0x02DF8C);                 // LC172World (Mars), as experiment 1
var templateBlock = sf.EnumerateMajorRecords<ISurfaceBlockGetter>().First(b => b.FormKey.ID == 0x102382); // OverlayBlockLC172World

var modKey = ModKey.FromNameAndExtension(S("plugin"));
var mod = new StarfieldMod(modKey, release);
mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
uint next = 0x800;
FormKey NewKey() => new(modKey, next++);
// the anchor takes the first FormID so plan.json can name it before the plugin exists (0x800)
FormKey? anchorKey = Has("anchor") ? NewKey() : null;

int n = I("n"), cmin = I("cell_min"), cmax = I("cell_max");

// SFBK: BTD path, size in cells, height range (= BTD header, as in vanilla), FNAM, alignment
var block = (SurfaceBlock)templateBlock.Duplicate(NewKey());
block.EditorID = S("world") + "Block";
block.ANAM = S("btd_path");
block.DNAM = new SurfaceBlockIntItem { First = (uint)n, Second = (uint)n };
// ENAM holds two floats; Mutagen 0.55 types them as uint, so pass the IEEE bits (vanilla akilacity: 0xC3FA0000 = -500)
block.ENAM = new SurfaceBlockFloatItem { First = BitConverter.SingleToUInt32Bits(F("hmin")), Second = BitConverter.SingleToUInt32Bits(F("hmax")) };
var fnam = (Has("fnam") ? prm.GetProperty("fnam") : prm.GetProperty("connections")).EnumerateArray().Select(e => (ushort)e.GetInt32()).ToArray();
if (Has("fnam") && fnam.Length != n * n) throw new InvalidDataException($"fnam has {fnam.Length} values, DNAM needs {n * n}");
block.FNAM = fnam.SelectMany(v => new[] { (byte)(v & 0xFF), (byte)(v >> 8) }).ToArray();
if (Has("alignment"))
{
    block.INAM = (byte)(S("alignment") == "absolute" ? 1 : 0);       // 0 Relative (LC overlays), 1 Absolute (NewAtlantis)
    block.HNAM = unchecked((ushort)(short)I("hnam"));                 // signed height offset (NewAtlantis -239 = 0xFF11)
}
block.Components.Clear();                                            // drop BlockEditorMetaData (CK bookkeeping)
mod.SurfaceBlocks.Add(block);

// WRLD
var w = (Worldspace)templateWorld.Duplicate(NewKey());
w.EditorID = S("world");
w.Name = "Commonwealth (FO4 terrain experiment 2)";
w.SubCells.Clear();
w.TopCell = null;
w.OffsetData = null;
w.CellSizeData = null;
w.Location.Clear();                                                  // LC172's location has quest aliases; keep it out
if (Has("location"))
{
    // like LC172WorldLocation (3807BE): keyword LocTypeOverlay, parent = the planet's surface location; no refs
    var loc = (Location)sf.Locations.First(l => l.FormKey.ID == 0x3807BE).Duplicate(NewKey());
    loc.EditorID = S("world") + "Location";
    loc.Name = "Commonwealth (FO4 terrain experiment 2)";
    loc.MasterSpecialReferences.Clear();
    loc.MasterInitiallyDisabledReferences.Clear();
    loc.Keywords = new ExtendedList<IFormLinkGetter<IKeywordGetter>> { new FormLink<IKeywordGetter>(new FormKey(sfEsm, 0x2CA99D)) };
    loc.ParentLocation.SetTo(new FormKey(sfEsm, 0x01B736));          // SSol_PMars_Surface
    mod.Locations.Add(loc);
    w.Location.SetTo(loc.FormKey);
}
w.Components.OfType<WorldSpaceOverlayComponent>().First().SurfaceBlock.SetTo(block.FormKey);
// object bounds: the template stores -200..300 m for its cells -2..2 (Mutagen shows metres / 4096); ours span the BTD
float bmin = F("bounds_min_m") / 4096f, bmax = F("bounds_max_m") / 4096f;
w.ObjectBoundsMin = new P2Float(bmin, bmin);
w.ObjectBoundsMax = new P2Float(bmax, bmax);

// every exterior cell the BTD covers; the spawn cell gets the COC EditorID and a COCMarkerHeading (000032)
var spawn = FA("spawn");
var spawnCell = FA("spawn_cell").Select(v => (int)v).ToArray();
var blocks = new Dictionary<(int, int), WorldspaceBlock>();
var subs = new Dictionary<(int, int), WorldspaceSubBlock>();
var cellAt = new Dictionary<(int, int), Cell>();
int cells = 0;
for (int x = cmin; x <= cmax; x++)
    for (int y = cmin; y <= cmax; y++)
    {
        var c = new Cell(NewKey(), release) { Grid = new CellGrid { Point = new P2Int(x, y) } };
        cellAt[(x, y)] = c;
        if (x == spawnCell[0] && y == spawnCell[1])
        {
            c.EditorID = S("coc");
            c.Temporary.Add(new PlacedObject(NewKey(), release)
            {
                EditorID = S("coc") + "Marker",
                Base = new FormLinkNullable<IPlaceableObjectGetter>(new FormKey(sfEsm, 0x000032)),
                Position = new P3Float(spawn[0], spawn[1], spawn[2]),
                Rotation = new P3Float(0, 0, 0),
            });
        }
        int bx = (int)Math.Floor(x / 32.0), by = (int)Math.Floor(y / 32.0), sx = (int)Math.Floor(x / 8.0), sy = (int)Math.Floor(y / 8.0);
        if (!blocks.TryGetValue((bx, by), out var blk)) { blk = new WorldspaceBlock { BlockNumberX = (short)bx, BlockNumberY = (short)by, GroupType = GroupTypeEnum.ExteriorCellBlock }; blocks[(bx, by)] = blk; w.SubCells.Add(blk); }
        if (!subs.TryGetValue((sx, sy), out var sub)) { sub = new WorldspaceSubBlock { BlockNumberX = (short)sx, BlockNumberY = (short)sy, GroupType = GroupTypeEnum.ExteriorCellSubBlock }; subs[(sx, sy)] = sub; blk.Items.Add(sub); }
        sub.Items.Add(c);
        cells++;
    }
w.TopCell = new Cell(NewKey(), release) { Flags = Cell.Flag.HasWater };   // persistent top cell (as experiment 1)
if (anchorKey is FormKey ak)
{
    // persistent XMarker (00003B) at a known local position: the runner reads it with prid + getpos and gets the
    // overlay's merge offset (x, y and z) as read - local
    var a = prm.GetProperty("anchor");
    var p = a.GetProperty("local").EnumerateArray().Select(e => e.GetSingle()).ToArray();
    var anchor = new PlacedObject(ak, release)
    {
        EditorID = a.GetProperty("edid").GetString(),
        Base = new FormLinkNullable<IPlaceableObjectGetter>(new FormKey(sfEsm, 0x00003B)),
        Position = new P3Float(p[0], p[1], p[2]),
        Rotation = new P3Float(0, 0, 0),
    };
    anchor.MajorRecordFlagsRaw |= 0x400;                             // Persistent
    w.TopCell.Persistent.Add(anchor);
}
int nStat = 0, nDoor = 0, nRef = 0, nDisabled = 0;
var ids = new Dictionary<string, object>();
var refKeys = new Dictionary<string, FormKey>();                     // FO4 source key -> placed reference
if (Has("objects"))
{
    // experiment 2c: converted FO4 models and their references, allocated after every terrain record
    using var odoc = JsonDocument.Parse(File.ReadAllText(Path.Combine(outDir, S("objects"))));
    var o = odoc.RootElement;
    var baseKeys = new List<FormKey>();
    var baseIds = new Dictionary<string, string>();
    foreach (var b in o.GetProperty("bases").EnumerateArray())
    {
        var edid = b.GetProperty("edid").GetString()!;
        var model = b.GetProperty("model").GetString()!;
        if (b.TryGetProperty("door", out var d) && d.ValueKind == JsonValueKind.Object)
        {
            // hinged door rigged like the vanilla template door (as PluginSpike): graph, skeleton, animations, bounds
            var rec = new Door(NewKey(), release)
            {
                EditorID = edid, Model = new Model { File = model }, Name = "Door",
                SoundLevel = SoundLevel.Normal, FacingAxisOverride = Door.FacingAxisOverrideEnum.BasedOnBounds,
            };
            if (d.TryGetProperty("bounds", out var bj))
                rec.ObjectBounds = new ObjectBounds
                {
                    First = new P3Float(bj[0][0].GetSingle(), bj[0][1].GetSingle(), bj[0][2].GetSingle()),
                    Second = new P3Float(bj[1][0].GetSingle(), bj[1][1].GetSingle(), bj[1][2].GetSingle()),
                };
            rec.Components.Add(new AnimationGraphComponent
            {
                ANAM = d.GetProperty("anim_graph").GetString(), BNAM = d.GetProperty("skeleton").GetString(),
                CNAM = d.GetProperty("animations").GetString(),
            });
            mod.Doors.Add(rec);
            baseKeys.Add(rec.FormKey);
            nDoor++;
        }
        else
        {
            var stat = new Static(NewKey(), release) { EditorID = edid, Model = new Model { File = model } };
            mod.Statics.Add(stat);
            baseKeys.Add(stat.FormKey);
            nStat++;
        }
        baseIds[edid] = baseKeys[^1].ID.ToString("X6");
    }
    var refIds = new Dictionary<string, string>();
    foreach (var r in o.GetProperty("refs").EnumerateArray())
    {
        float[] V(string k) => r.GetProperty(k).EnumerateArray().Select(e => e.GetSingle()).ToArray();
        var cxy = r.GetProperty("cell").EnumerateArray().Select(e => e.GetInt32()).ToArray();
        if (!cellAt.TryGetValue((cxy[0], cxy[1]), out var cell))
            throw new InvalidDataException($"reference {r.GetProperty("src").GetString()} in cell ({cxy[0]}, {cxy[1]}) outside the BTD cells");
        var pos = V("pos");
        var rot = V("rot");
        var obj = new PlacedObject(NewKey(), release)
        {
            Base = new FormLinkNullable<IPlaceableObjectGetter>(baseKeys[r.GetProperty("base").GetInt32()]),
            Position = new P3Float(pos[0], pos[1], pos[2]),
            Rotation = new P3Float(rot[0], rot[1], rot[2]),
        };
        var scale = r.GetProperty("scale").GetSingle();
        if (Math.Abs(scale - 1f) > 1e-4) obj.Scale = scale;
        if (r.GetProperty("disabled").GetBoolean())
        {
            obj.MajorRecordFlagsRaw |= 0x800;                            // Initially Disabled, as in FO4
            nDisabled++;
        }
        cell.Temporary.Add(obj);
        refIds[r.GetProperty("src").GetString()!] = obj.FormKey.ID.ToString("X6");
        refKeys[r.GetProperty("src").GetString()!] = obj.FormKey;
        nRef++;
    }
    ids["plugin"] = modKey.FileName.String;
    ids["bases"] = baseIds;
    ids["refs"] = refIds;
}
int nNav = 0, nNavTri = 0, nNavLink = 0, nNavDoor = 0;
if (Has("navmesh"))
{
    // experiment 2d: converted Fallout 4 navmeshes (src/fo4sf/navmesh.py export). Every field below is typed in
    // Mutagen except NVMI's Data (u32 flags, f32 x, y, z, f32) and Unknown (traversal count, outline flag, CRC,
    // worldspace, grid, border bits, 4 zero bytes), which hold raw bytes; the worldspace FormID in Unknown is
    // file-local: Starfield.esm is master 0, so this plugin's own records are 01xxxxxx.
    using var ndoc = JsonDocument.Parse(File.ReadAllText(Path.Combine(outDir, S("navmesh"))));
    var navs = ndoc.RootElement.GetProperty("navmeshes").EnumerateArray().ToList();
    var navKeys = navs.Select(_ => NewKey()).ToList();
    uint worldLocal = 0x01000000u | w.FormKey.ID;
    var navi = new NavigationMeshInfoMap(new FormKey(sfEsm, 0x000FF1), release)
    {
        NavMeshVersion = 17,
        PreferredPathing = new PreferredPathing(),
    };
    var navIds = new List<string>();
    for (int i = 0; i < navs.Count; i++)
    {
        var e = navs[i];
        var cxy = e.GetProperty("cell").EnumerateArray().Select(x => x.GetInt32()).ToArray();
        if (!cellAt.TryGetValue((cxy[0], cxy[1]), out var cell))
            throw new InvalidDataException($"navmesh {i} in cell ({cxy[0]}, {cxy[1]}) outside the BTD cells");
        var grid = e.GetProperty("grid");
        float[] GF(string k) => grid.GetProperty(k).EnumerateArray().Select(x => x.GetSingle()).ToArray();
        var gsize = GF("size"); var gmin = GF("min"); var gmax = GF("max");
        var g = new NavmeshGeometry
        {
            NavmeshVersion = 17,
            CrcHash = 0xA5E9A03C,
            Parent = new WorldspaceNavmeshParent
            {
                Parent = new FormLink<IWorldspaceGetter>(w.FormKey),
                Coordinates = new P2Int16((short)cxy[0], (short)cxy[1]),
            },
            GridSize = (uint)grid.GetProperty("divisor").GetInt32(),
            GridMaxDistance = new P2Float(gsize[0], gsize[1]),
            GridMin = new P3Float(gmin[0], gmin[1], gmin[2]),
            GridMax = new P3Float(gmax[0], gmax[1], gmax[2]),
            Unknown3 = 0x0008000C,                                   // the trailing 0c 00 08 00 of vanilla records
        };
        foreach (var v in e.GetProperty("vertices").EnumerateArray())
            g.Vertices.Add(new NavmeshVertex { Point = new P3Float(v[0].GetSingle(), v[1].GetSingle(), v[2].GetSingle()), Unknown = v[3].GetInt32() });
        foreach (var t in e.GetProperty("triangles").EnumerateArray())
        {
            g.Triangles.Add(new NavmeshTriangle
            {
                Vertices = new P3Int16(t[0].GetInt16(), t[1].GetInt16(), t[2].GetInt16()),
                EdgeLink_0_1 = t[3].GetInt16(), EdgeLink_1_2 = t[4].GetInt16(), EdgeLink_2_0 = t[5].GetInt16(),
                Height = t[6].GetSingle(), Unknown = (byte)t[7].GetInt32(),
                Flags = (NavmeshTriangle.Flag)t[8].GetInt32(), CoverFlags = (ushort)t[9].GetInt32(),
            });
            nNavTri++;
        }
        var merged = new List<FormKey>();
        foreach (var l in e.GetProperty("links").EnumerateArray())
        {
            var target = navKeys[l[1].GetInt32()];
            g.EdgeLinks.Add(new EdgeLink
            {
                Unknown = l[0].GetInt32(), Mesh = new FormLink<INavigationMeshGetter>(target),
                TriangleIndex = l[2].GetInt16(), Unknown2 = (sbyte)l[3].GetInt32(),
            });
            if (!merged.Contains(target)) merged.Add(target);
            nNavLink++;
        }
        var linkedDoors = new List<LinkedDoor>();
        foreach (var d in e.GetProperty("doors").EnumerateArray())
        {
            var src = d[2].GetString()!;
            if (!refKeys.TryGetValue(src, out var doorKey))
                throw new InvalidDataException($"navmesh {i}: door {src} is not a placed reference of this plugin");
            g.DoorTriangles.Add(new DoorTriangle { TriangleBeforeDoor = d[0].GetInt16(), Unknown = unchecked((int)d[1].GetUInt32()), Door = new FormLink<IPlacedObjectGetter>(doorKey) });
            linkedDoors.Add(new LinkedDoor { Type = d[1].GetUInt32(), Door = new FormLink<IPlacedObjectGetter>(doorKey) });
            nNavDoor++;
        }
        foreach (var p in e.GetProperty("waypoints").EnumerateArray())
            g.Waypoints.Add(new NavmeshWaypoint { Location = new P3Float(p[0].GetSingle(), p[1].GetSingle(), p[2].GetSingle()), TriangleIndex = p[3].GetInt16(), Unknown = p[4].GetInt32() });
        foreach (var lst in grid.GetProperty("lists").EnumerateArray())
            g.GridArrays.Add(new NavmeshGridArray { GridCell = new ExtendedList<short>(lst.EnumerateArray().Select(x => x.GetInt16())) });
        cell.NavigationMeshes.Add(new NavigationMesh(navKeys[i], release) { NavmeshGeometry = g });

        var nv = e.GetProperty("nvmi");
        var loc = nv.GetProperty("location").EnumerateArray().Select(x => x.GetSingle()).ToArray();
        var data = new byte[20];
        BitConverter.TryWriteBytes(data.AsSpan(0, 4), 0u);                       // flags: no outline
        BitConverter.TryWriteBytes(data.AsSpan(4, 4), loc[0]);
        BitConverter.TryWriteBytes(data.AsSpan(8, 4), loc[1]);
        BitConverter.TryWriteBytes(data.AsSpan(12, 4), loc[2]);
        BitConverter.TryWriteBytes(data.AsSpan(16, 4), 0f);
        var unk = new byte[22];                                                    // traversals 0, outline 0
        BitConverter.TryWriteBytes(unk.AsSpan(5, 4), 0xA5E9A03Cu);
        BitConverter.TryWriteBytes(unk.AsSpan(9, 4), worldLocal);
        BitConverter.TryWriteBytes(unk.AsSpan(13, 2), (short)cxy[1]);              // grid y, then x
        BitConverter.TryWriteBytes(unk.AsSpan(15, 2), (short)cxy[0]);
        unk[17] = (byte)nv.GetProperty("border").GetInt32();
        var info = new NavigationMapInfo
        {
            NavigationMesh = new FormLink<INavigationMeshGetter>(navKeys[i]),
            Data = new MemorySlice<byte>(data),
            Unknown = new MemorySlice<byte>(unk),
        };
        foreach (var m in merged) info.MergedTo.Add(new FormLink<INavigationMeshGetter>(m));
        foreach (var ld in linkedDoors) info.LinkedDoors.Add(ld);
        navi.MapInfos.Add(info);
        navIds.Add(navKeys[i].ID.ToString("X6"));
        nNav++;
    }
    mod.NavigationMeshInfoMaps.Add(navi);
    ids["navmeshes"] = navIds;
    ids["navi"] = "000FF1:Starfield.esm";
}
if (ids.Count > 0)
{
    ids["plugin"] = modKey.FileName.String;
    File.WriteAllText(Path.Combine(outDir, "formids.json"), JsonSerializer.Serialize(ids, new JsonSerializerOptions { WriteIndented = true }));
}
mod.Worldspaces.Add(w);
mod.ModHeader.Stats.NextFormID = next;

var path = Path.Combine(outDir, modKey.FileName);
mod.BeginWrite.ToPath(path).WithLoadOrderFromHeaderMasters().WithDataFolder(sfData)
    .WithKnownMasters(new KeyedMasterStyle(sfEsm, MasterStyle.Full)).Write();
Console.WriteLine($"wrote {path} ({new FileInfo(path).Length:N0} bytes): WRLD {w.FormKey} {w.EditorID}, SFBK {block.FormKey} -> {block.ANAM}, " +
                  $"FNAM {block.FNAM?.Length} B, INAM {block.INAM}, HNAM {block.HNAM}, location {w.Location.FormKeyNullable}, anchor {anchorKey}, " +
                  $"{cells} cells {cmin}..{cmax}, COC {S("coc")} at ({spawn[0]}, {spawn[1]}, {spawn[2]}) in cell ({spawnCell[0]}, {spawnCell[1]}), next FormID 0x{next:X}" +
                  (Has("objects") ? $"; objects: {nStat} STAT, {nDoor} DOOR, {nRef} REFR ({nDisabled} initially disabled)" : "") +
                  (Has("navmesh") ? $"; navmesh: {nNav} NAVM, {nNavTri} triangles, {nNavLink} edge links, {nNavDoor} door triangles, NAVI override with {nNav} NVMI" : ""));

if (Has("mars"))
{
    // optional planet registration, a separate plugin so it can be switched on or off (as FO4TerrainExp1_Mars.esm)
    var m = prm.GetProperty("mars");
    var marsKey = ModKey.FromNameAndExtension(m.GetProperty("plugin").GetString()!);
    var mars = new StarfieldMod(marsKey, release);
    mars.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
    var planet = (Planet)sf.Planets.First(p => p.EditorID == "MarsPlanetData").DeepCopy();   // same FormKey = override
    mars.Planets.Add(planet);
    planet.MasterWorldspaces.Add(new MasterWorldspace
    {
        Worldspace = new FormLink<IWorldspaceGetter>(w.FormKey),
        Latitude = m.GetProperty("latitude").GetDouble(),
        Longitude = m.GetProperty("longitude").GetDouble(),
    });
    mars.ModHeader.Stats.NextFormID = 0x800;
    var marsPath = Path.Combine(outDir, marsKey.FileName);
    mars.BeginWrite.ToPath(marsPath).WithLoadOrder(sfEsm, modKey)
        .WithKnownMasters(new KeyedMasterStyle(sfEsm, MasterStyle.Full), new KeyedMasterStyle(modKey, MasterStyle.Full)).Write();
    Console.WriteLine($"wrote {marsPath} ({new FileInfo(marsPath).Length:N0} bytes); Mars master worldspaces now {planet.MasterWorldspaces!.Count}");
}
