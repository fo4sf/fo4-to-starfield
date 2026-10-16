// Commonwealth terrain as one or more Starfield overlay worldspaces (docs/terrain/commonwealth-scale.md).
//   dotnet run -- <Starfield.esm> <staging dir>
// Reads <staging dir>/overlays_params.json (written by scripts/terrain/make_cw_overlays.py build) and writes
//   <plugin>        master Starfield.esm, own FormIDs from 0x800 (the anchors first, one per overlay, so plan.json can
//                   name them before the plugin exists), nothing shared with FO4Port.esm
//   <mars plugin>   when params hold "mars": override of MarsPlanetData that appends one PNDT CNAM entry per overlay
// Nothing is deployed.
//
// Per overlay (the records of experiment 2b, docs/terrain/overlay-records.md, once per tile):
//   SFBK <world>Block      copy of OverlayBlockLC172World (102382): ANAM = the tile's BTD, DNAM n x n, ENAM = shared
//                          height range, FNAM = one raw u16 per BTD cell (SW-corner sample), INAM/HNAM alignment
//   LCTN <world>Location   copy of LC172WorldLocation (3807BE): keyword LocTypeOverlay, parent SSol_PMars_Surface; one
//                          per overlay (the CK warns when two overlays share a location)
//   WRLD <world>           copy of LC172World (02DF8C) minus cells/offsets/location; overlay component -> the SFBK;
//                          object bounds = the BTD; every exterior cell of the BTD (empty), the COC cell with a
//                          COCMarkerHeading 2 m above the ground, a persistent XMarker anchor in the persistent cell
// PNDT CNAM entries store latitude first, then longitude (radians; Earth overlays sit at their real cities). Mutagen
// 0.55 names the first value Longitude and the second Latitude, so the params' latitude goes into .Longitude.
//
// Optional "objects": "objects.json" (core64c, docs/terrain/core64c.md, written by scripts/terrain/make_core64c.py stage):
// converted Fallout 4 models as STAT (or rigged DOOR) records and their references in one overlay's exterior cells,
// {"world": <overlay world EditorID>, "bases": [{"edid", "model", "door"?}], "refs": [{"src", "base", "cell", "pos",
// "rot", "scale", "disabled"}]} (metres, radians), as dotnet/TerrainExp2's objects mode. Their FormIDs come after every
// overlay record, so the terrain records, the anchors and the Mars plugin keep the FormIDs they have without objects;
// <staging dir>/formids.json lists the new ones.
using System.Text.Json;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;

var sfPath = args[0];
var outDir = args[1];
var prm = JsonDocument.Parse(File.ReadAllText(Path.Combine(outDir, "overlays_params.json"))).RootElement;
bool Has(JsonElement e, string k) => e.TryGetProperty(k, out var v) && v.ValueKind is not (JsonValueKind.Null or JsonValueKind.False);

var sfData = Path.GetDirectoryName(Path.GetFullPath(sfPath))!;
var release = StarfieldRelease.Starfield;
var sfEsm = ModKey.FromNameAndExtension("Starfield.esm");
using var sf = StarfieldMod.CreateFromBinaryOverlay(sfPath, release);

var templateWorld = sf.Worldspaces.First(w => w.FormKey.ID == 0x02DF8C);                                   // LC172World (Mars)
var templateBlock = sf.EnumerateMajorRecords<ISurfaceBlockGetter>().First(b => b.FormKey.ID == 0x102382);   // OverlayBlockLC172World
var templateLoc = sf.Locations.First(l => l.FormKey.ID == 0x3807BE);                                        // LC172WorldLocation

var modKey = ModKey.FromNameAndExtension(prm.GetProperty("plugin").GetString()!);
var mod = new StarfieldMod(modKey, release);
mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
var overlays = prm.GetProperty("overlays").EnumerateArray().ToList();

// anchors take the first FormIDs, in params order (plan.json names them as 0x800 + index)
uint next = 0x800;
foreach (var o in overlays)
{
    uint want = o.GetProperty("anchor").GetProperty("form_id").GetUInt32();
    if (want != next) throw new InvalidDataException($"anchor form_id 0x{want:X} out of order (expected 0x{next:X})");
    next++;
}
FormKey NewKey() => new(modKey, next++);

float hmin = prm.GetProperty("hmin").GetSingle(), hmax = prm.GetProperty("hmax").GetSingle();
bool absolute = prm.GetProperty("alignment").GetString() == "absolute";
short hnam = prm.GetProperty("hnam").GetInt16();
var worlds = new List<(Worldspace World, JsonElement Params)>();
var cellsOf = new Dictionary<string, Dictionary<(int, int), Cell>>();
int idx = 0;
foreach (var o in overlays)
{
    string world = o.GetProperty("world").GetString()!;
    int n = o.GetProperty("n").GetInt32(), cmin = o.GetProperty("cell_min").GetInt32(), cmax = o.GetProperty("cell_max").GetInt32();

    var block = (SurfaceBlock)templateBlock.Duplicate(NewKey());
    block.EditorID = o.GetProperty("block").GetString();
    block.ANAM = o.GetProperty("btd_path").GetString();
    block.DNAM = new SurfaceBlockIntItem { First = (uint)n, Second = (uint)n };
    // ENAM holds two floats; Mutagen 0.55 types them as uint, so pass the IEEE bits
    block.ENAM = new SurfaceBlockFloatItem { First = BitConverter.SingleToUInt32Bits(hmin), Second = BitConverter.SingleToUInt32Bits(hmax) };
    var fnam = o.GetProperty("fnam").EnumerateArray().Select(e => (ushort)e.GetInt32()).ToArray();
    if (fnam.Length != n * n) throw new InvalidDataException($"{world}: fnam has {fnam.Length} values, DNAM needs {n * n}");
    block.FNAM = fnam.SelectMany(v => new[] { (byte)(v & 0xFF), (byte)(v >> 8) }).ToArray();
    block.INAM = (byte)(absolute ? 1 : 0);
    block.HNAM = unchecked((ushort)hnam);
    block.Components.Clear();                                                // drop BlockEditorMetaData (CK bookkeeping)
    mod.SurfaceBlocks.Add(block);

    var loc = (Location)templateLoc.Duplicate(NewKey());
    loc.EditorID = o.GetProperty("location").GetString();
    loc.Name = $"Commonwealth {o.GetProperty("tag").GetString()} (FO4 terrain)";
    loc.MasterSpecialReferences?.Clear();
    loc.MasterInitiallyDisabledReferences?.Clear();
    loc.Keywords = new ExtendedList<IFormLinkGetter<IKeywordGetter>> { new FormLink<IKeywordGetter>(new FormKey(sfEsm, 0x2CA99D)) };
    loc.ParentLocation.SetTo(new FormKey(sfEsm, 0x01B736));                  // SSol_PMars_Surface
    mod.Locations.Add(loc);

    var w = (Worldspace)templateWorld.Duplicate(NewKey());
    w.EditorID = world;
    w.Name = $"Commonwealth {o.GetProperty("tag").GetString()} (FO4 terrain)";
    w.SubCells.Clear();
    w.TopCell = null;
    w.OffsetData = null;
    w.CellSizeData = null;
    w.Location.SetTo(loc.FormKey);
    w.Components.OfType<WorldSpaceOverlayComponent>().First().SurfaceBlock.SetTo(block.FormKey);
    // object bounds are raw metres; Mutagen shows them divided by 4096
    float bmin = o.GetProperty("bounds_min_m").GetSingle() / 4096f, bmax = o.GetProperty("bounds_max_m").GetSingle() / 4096f;
    w.ObjectBoundsMin = new P2Float(bmin, bmin);
    w.ObjectBoundsMax = new P2Float(bmax, bmax);

    var spawn = o.GetProperty("spawn").EnumerateArray().Select(e => e.GetSingle()).ToArray();
    var spawnCell = o.GetProperty("spawn_cell").EnumerateArray().Select(e => e.GetInt32()).ToArray();
    string coc = o.GetProperty("coc").GetString()!;
    var blocks = new Dictionary<(int, int), WorldspaceBlock>();
    var subs = new Dictionary<(int, int), WorldspaceSubBlock>();
    var cellAt = cellsOf[world] = new Dictionary<(int, int), Cell>();
    for (int x = cmin; x <= cmax; x++)
        for (int y = cmin; y <= cmax; y++)
        {
            var c = new Cell(NewKey(), release) { Grid = new CellGrid { Point = new P2Int(x, y) } };
            cellAt[(x, y)] = c;
            if (x == spawnCell[0] && y == spawnCell[1])
            {
                c.EditorID = coc;
                c.Temporary.Add(new PlacedObject(NewKey(), release)
                {
                    EditorID = coc + "Marker",
                    Base = new FormLinkNullable<IPlaceableObjectGetter>(new FormKey(sfEsm, 0x000032)),   // COCMarkerHeading
                    Position = new P3Float(spawn[0], spawn[1], spawn[2]),
                    Rotation = new P3Float(0, 0, 0),
                });
            }
            int bx = (int)Math.Floor(x / 32.0), by = (int)Math.Floor(y / 32.0), sx = (int)Math.Floor(x / 8.0), sy = (int)Math.Floor(y / 8.0);
            if (!blocks.TryGetValue((bx, by), out var blk)) { blk = new WorldspaceBlock { BlockNumberX = (short)bx, BlockNumberY = (short)by, GroupType = GroupTypeEnum.ExteriorCellBlock }; blocks[(bx, by)] = blk; w.SubCells.Add(blk); }
            if (!subs.TryGetValue((sx, sy), out var sub)) { sub = new WorldspaceSubBlock { BlockNumberX = (short)sx, BlockNumberY = (short)sy, GroupType = GroupTypeEnum.ExteriorCellSubBlock }; subs[(sx, sy)] = sub; blk.Items.Add(sub); }
            sub.Items.Add(c);
        }
    w.TopCell = new Cell(NewKey(), release) { Flags = Cell.Flag.HasWater };   // persistent top cell (as experiments 1 and 2)
    var a = o.GetProperty("anchor");
    var p = a.GetProperty("local").EnumerateArray().Select(e => e.GetSingle()).ToArray();
    var anchor = new PlacedObject(new FormKey(modKey, a.GetProperty("form_id").GetUInt32()), release)
    {
        EditorID = a.GetProperty("edid").GetString(),
        Base = new FormLinkNullable<IPlaceableObjectGetter>(new FormKey(sfEsm, 0x00003B)),            // XMarker
        Position = new P3Float(p[0], p[1], p[2]),
        Rotation = new P3Float(0, 0, 0),
    };
    anchor.MajorRecordFlagsRaw |= 0x400;                                     // Persistent
    w.TopCell.Persistent.Add(anchor);
    mod.Worldspaces.Add(w);
    worlds.Add((w, o));
    Console.WriteLine($"  {world}: WRLD {w.FormKey}, SFBK {block.FormKey} -> {block.ANAM}, LCTN {loc.FormKey}, anchor {anchor.FormKey} at ({p[0]}, {p[1]}, {p[2]}), " +
                      $"{(cmax - cmin + 1) * (cmax - cmin + 1)} cells {cmin}..{cmax}, COC {coc} in ({spawnCell[0]}, {spawnCell[1]})");
    idx++;
}
int nStat = 0, nDoor = 0, nRef = 0, nDisabled = 0, nNav = 0, nNavTri = 0, nNavLink = 0, nNavDoor = 0;
var refIds = new Dictionary<string, string>();                 // placed reference source -> this plugin's id (6 hex)
Dictionary<string, object>? ids = null;                        // formids.json
Dictionary<(int, int), Cell>? objCells = null;                 // the objects' overlay cells
string? objWorld = null;
if (Has(prm, "objects"))
{
    // core64c: converted FO4 models and their references, allocated after every overlay record
    using var odoc = JsonDocument.Parse(File.ReadAllText(Path.Combine(outDir, prm.GetProperty("objects").GetString()!)));
    var o = odoc.RootElement;
    var referenceSources = ReferenceIdentityPlan.Order(o);
    string world = o.TryGetProperty("world", out var wj) ? wj.GetString()! : worlds[0].World.EditorID!;
    if (!cellsOf.TryGetValue(world, out var cellAt)) throw new InvalidDataException($"objects.json names world {world}, not an overlay of these params");
    objCells = cellAt; objWorld = world;
    var baseKeys = new List<FormKey>();
    var baseIds = new Dictionary<string, string>();
    foreach (var b in o.GetProperty("bases").EnumerateArray())
    {
        var edid = b.GetProperty("edid").GetString()!;
        var model = b.GetProperty("model").GetString()!;
        if (b.TryGetProperty("door", out var d) && d.ValueKind == JsonValueKind.Object)
        {
            // hinged door rigged like the vanilla template door (as PluginSpike and TerrainExp2): graph, skeleton, bounds
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
    // Reserve every original slot, including references promoted out of "refs".
    // A later neighbour must not inherit the promoted source's saved-game ID.
    var referenceKeys = referenceSources.ToDictionary(src => src, _ => NewKey(), StringComparer.OrdinalIgnoreCase);
    foreach (var r in o.GetProperty("refs").EnumerateArray())
    {
        float[] V(string k) => r.GetProperty(k).EnumerateArray().Select(e => e.GetSingle()).ToArray();
        var cxy = r.GetProperty("cell").EnumerateArray().Select(e => e.GetInt32()).ToArray();
        if (!cellAt.TryGetValue((cxy[0], cxy[1]), out var cell))
            throw new InvalidDataException($"reference {r.GetProperty("src").GetString()} in cell ({cxy[0]}, {cxy[1]}) outside {world}'s cells");
        var pos = V("pos");
        var rot = V("rot");
        var obj = new PlacedObject(referenceKeys[r.GetProperty("src").GetString()!], release)
        {
            Base = new FormLinkNullable<IPlaceableObjectGetter>(baseKeys[r.GetProperty("base").GetInt32()]),
            Position = new P3Float(pos[0], pos[1], pos[2]),
            Rotation = new P3Float(rot[0], rot[1], rot[2]),
        };
        var scale = r.GetProperty("scale").GetSingle();
        if (Math.Abs(scale - 1f) > 1e-4) obj.Scale = scale;
        if (r.GetProperty("disabled").GetBoolean())
        {
            obj.MajorRecordFlagsRaw |= 0x800;                                // Initially Disabled, as in FO4
            nDisabled++;
        }
        cell.Temporary.Add(obj);
        refIds[r.GetProperty("src").GetString()!] = obj.FormKey.ID.ToString("X6");
        nRef++;
    }
    // R05 (docs/slice/r05-cluster-plan.md): "containers", interactive objects of the cluster, each a native CONT base
    // with the converted model and a vanilla inventory, and one temporary REFR in its original identity slot.
    // Only the new CONT bases are allocated after every STAT / DOOR and every reserved REFR above.
    // ({"src", "edid", "model", "name", "items": [{"form": "Starfield.esm:00000F", "count": 25}], "cell", "pos",
    // "rot", "scale", "reference_index"}; the source leaves "refs", but its original index is retained).
    var contIds = new Dictionary<string, object>();
    var contByEdid = new Dictionary<string, Container>(StringComparer.OrdinalIgnoreCase);   // one CONT per FO4 base: entries of one base share an edid
    if (o.TryGetProperty("containers", out var conts))
    {
        foreach (var c in conts.EnumerateArray())
        {
            float[] V(string k) => c.GetProperty(k).EnumerateArray().Select(e => e.GetSingle()).ToArray();
            var cxy = c.GetProperty("cell").EnumerateArray().Select(e => e.GetInt32()).ToArray();
            if (!cellAt.TryGetValue((cxy[0], cxy[1]), out var cell))
                throw new InvalidDataException($"container {c.GetProperty("src").GetString()} in cell ({cxy[0]}, {cxy[1]}) outside {world}'s cells");
            var edid = c.GetProperty("edid").GetString()!;
            var cmodel = c.GetProperty("model").GetString()!;
            if (!contByEdid.TryGetValue(edid, out var cont))
            {
                cont = new Container(NewKey(), release)
                {
                    EditorID = edid, Model = new Model { File = cmodel },
                    Name = c.GetProperty("name").GetString(),
                    Items = new ExtendedList<ContainerEntry>(),                    // null by default in Mutagen 0.55
                };
                foreach (var it in c.GetProperty("items").EnumerateArray())
                {
                    var form = it.GetProperty("form").GetString()!;                 // "<plugin>:<6 hex>"
                    var colon = form.IndexOf(':');
                    var fk = new FormKey(ModKey.FromNameAndExtension(form[..colon]), Convert.ToUInt32(form[(colon + 1)..], 16));
                    cont.Items.Add(new ContainerEntry
                    {
                        Item = new ContainerItem { Item = new FormLink<IItemGetter>(fk), Count = it.GetProperty("count").GetInt32() },
                    });
                }
                mod.Containers.Add(cont);
                contByEdid[edid] = cont;
            }
            else if (!string.Equals(cont.Model?.File, cmodel, StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException($"container {edid}: two models ({cont.Model?.File} / {cmodel}) under one edid");
            var pos = V("pos");
            var rot = V("rot");
            var obj = new PlacedObject(referenceKeys[c.GetProperty("src").GetString()!], release)
            {
                Base = new FormLinkNullable<IPlaceableObjectGetter>(cont.FormKey),
                Position = new P3Float(pos[0], pos[1], pos[2]),
                Rotation = new P3Float(rot[0], rot[1], rot[2]),
            };
            var scale = c.GetProperty("scale").GetSingle();
            if (Math.Abs(scale - 1f) > 1e-4) obj.Scale = scale;
            cell.Temporary.Add(obj);
            nRef++;
            contIds[c.GetProperty("src").GetString()!] = new Dictionary<string, string>
            {
                ["base"] = cont.FormKey.ID.ToString("X6"), ["ref"] = obj.FormKey.ID.ToString("X6"),
            };
            if (contByEdid.Count <= 8 || nRef % 500 == 0)
                Console.WriteLine($"  container {cont.EditorID} {cont.FormKey} ({cont.Items.Count} items) -> REFR {obj.FormKey} in cell ({cxy[0]}, {cxy[1]})");
        }
    }
    ids = new Dictionary<string, object> { ["plugin"] = modKey.FileName.String, ["world"] = world, ["bases"] = baseIds, ["refs"] = refIds, ["containers"] = contIds };
}
if (Has(prm, "navmesh"))
{
    // Commonwealth navmesh (docs/actors/navmesh-conversion.md, ported from dotnet/TerrainExp2 2026-10-15): converted
    // Fallout 4 navmeshes (src/fo4sf/navmesh.py export), one NAVM per (FO4 navmesh, Starfield cell) in that cell's
    // navmesh group, allocated after every object, plus a NAVI override (000FF1:Starfield.esm) with one NVMI per new
    // navmesh. Every field is typed in Mutagen except NVMI's Data and Unknown (raw bytes; the worldspace FormID in
    // Unknown is file-local: Starfield.esm is master 0, this plugin's records are 01xxxxxx). The four Mutagen
    // 0.55.0-alpha.67 adjustments of experiment 2d (grid lists as one raw array + Unknown3, parent coordinates
    // y-then-x, the empty MNAM, form version 581) are kept as verified there.
    using var ndoc = JsonDocument.Parse(File.ReadAllText(Path.Combine(outDir, prm.GetProperty("navmesh").GetString()!)));
    var nroot = ndoc.RootElement;
    string nworld = nroot.TryGetProperty("world", out var nwj) ? nwj.GetString()! : (objWorld ?? worlds[0].World.EditorID!);
    if (!cellsOf.TryGetValue(nworld, out var navCells)) throw new InvalidDataException($"navmesh.json names world {nworld}, not an overlay of these params");
    var navWorld = worlds.First(x => x.World.EditorID == nworld).World;
    var navs = nroot.GetProperty("navmeshes").EnumerateArray().ToList();
    var navKeys = navs.Select(_ => NewKey()).ToList();
    uint worldLocal = 0x01000000u | navWorld.FormKey.ID;
    var navi = new NavigationMeshInfoMap(new FormKey(sfEsm, 0x000FF1), release)
    {
        NavMeshVersion = 17,
        PreferredPathing = new PreferredPathing(),
        FormVersion = 581,                                          // Starfield.esm, SFBGS006, BlueprintShips: 581
    };
    var navIds = new List<string>();
    for (int i = 0; i < navs.Count; i++)
    {
        var e = navs[i];
        var cxy = e.GetProperty("cell").EnumerateArray().Select(x => x.GetInt32()).ToArray();
        if (!navCells.TryGetValue((cxy[0], cxy[1]), out var cell))
            throw new InvalidDataException($"navmesh {i} in cell ({cxy[0]}, {cxy[1]}) outside {nworld}'s cells");
        var grid = e.GetProperty("grid");
        float[] GF(string k) => grid.GetProperty(k).EnumerateArray().Select(x => x.GetSingle()).ToArray();
        var gsize = GF("size"); var gmin = GF("min"); var gmax = GF("max");
        var g = new NavmeshGeometry
        {
            NavmeshVersion = 17,
            CrcHash = 0xA5E9A03C,
            Parent = new WorldspaceNavmeshParent
            {
                Parent = new FormLink<IWorldspaceGetter>(navWorld.FormKey),
                // the file holds grid y, then grid x (every vanilla exterior NAVM matches its cell's XCLC that way);
                // Mutagen writes Coordinates.X first, so X takes the grid y
                Coordinates = new P2Int16((short)cxy[1], (short)cxy[0]),
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
            if (!refIds.TryGetValue(src, out var doorId))
                throw new InvalidDataException($"navmesh {i}: door {src} is not a placed reference of this plugin");
            var doorKey = new FormKey(modKey, Convert.ToUInt32(doorId, 16));
            g.DoorTriangles.Add(new DoorTriangle { TriangleBeforeDoor = d[0].GetInt16(), Unknown = unchecked((int)d[1].GetUInt32()), Door = new FormLink<IPlacedObjectGetter>(doorKey) });
            linkedDoors.Add(new LinkedDoor { Type = d[1].GetUInt32(), Door = new FormLink<IPlacedObjectGetter>(doorKey) });
            nNavDoor++;
        }
        foreach (var wp in e.GetProperty("waypoints").EnumerateArray())
            g.Waypoints.Add(new NavmeshWaypoint { Location = new P3Float(wp[0].GetSingle(), wp[1].GetSingle(), wp[2].GetSingle()), TriangleIndex = wp[3].GetInt16(), Unknown = wp[4].GetInt32() });
        // the grid lists with their counts as ONE raw i16 array (navmesh.grid_raw), Unknown3 the trailer (experiment 2d)
        g.GridArrays.Add(new NavmeshGridArray { GridCell = new ExtendedList<short>(grid.GetProperty("raw").EnumerateArray().Select(x => x.GetInt16())) });
        cell.NavigationMeshes.Add(new NavigationMesh(navKeys[i], release)
        {
            NavmeshGeometry = g,
            PreCutMapEntries = new ExtendedList<PreCutMapEntry>(),   // the empty MNAM every vanilla NAVM has
            FormVersion = 581,                                      // as Starfield.esm's newest NAVM and its NAVI
        });
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
    ids ??= new Dictionary<string, object> { ["plugin"] = modKey.FileName.String, ["world"] = nworld };
    ids["navmeshes"] = navIds;
    ids["navi"] = "000FF1:Starfield.esm";
}
if (ids != null)
    File.WriteAllText(Path.Combine(outDir, "formids.json"), JsonSerializer.Serialize(ids));
mod.ModHeader.Stats.NextFormID = next;
var path = Path.Combine(outDir, modKey.FileName);
mod.BeginWrite.ToPath(path).WithLoadOrderFromHeaderMasters().WithDataFolder(sfData)
    .WithKnownMasters(new KeyedMasterStyle(sfEsm, MasterStyle.Full)).Write();
Console.WriteLine($"wrote {path} ({new FileInfo(path).Length:N0} bytes): {worlds.Count} overlays, next FormID 0x{next:X}" +
                  (Has(prm, "objects") ? $"; objects: {nStat} STAT, {nDoor} DOOR, {nRef} REFR ({nDisabled} initially disabled)" : "") +
                  (Has(prm, "navmesh") ? $"; navmesh: {nNav} NAVM, {nNavTri} triangles, {nNavLink} edge links, {nNavDoor} door triangles, NAVI override with {nNav} NVMI" : ""));

if (Has(prm, "mars"))
{
    var m = prm.GetProperty("mars");
    var marsKey = ModKey.FromNameAndExtension(m.GetProperty("plugin").GetString()!);
    var mars = new StarfieldMod(marsKey, release);
    mars.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
    var planet = (Planet)sf.Planets.First(pl => pl.EditorID == "MarsPlanetData").DeepCopy();   // same FormKey = override
    mars.Planets.Add(planet);
    foreach (var (w, o) in worlds)
        planet.MasterWorldspaces!.Add(new MasterWorldspace
        {
            Worldspace = new FormLink<IWorldspaceGetter>(w.FormKey),
            Longitude = o.GetProperty("latitude").GetDouble(),     // first f64 of the entry = latitude
            Latitude = o.GetProperty("longitude").GetDouble(),     // second f64 = longitude
        });
    mars.ModHeader.Stats.NextFormID = 0x800;
    var marsPath = Path.Combine(outDir, marsKey.FileName);
    mars.BeginWrite.ToPath(marsPath).WithLoadOrder(sfEsm, modKey)
        .WithKnownMasters(new KeyedMasterStyle(sfEsm, MasterStyle.Full), new KeyedMasterStyle(modKey, MasterStyle.Full)).Write();
    Console.WriteLine($"wrote {marsPath} ({new FileInfo(marsPath).Length:N0} bytes); Mars master worldspaces now {planet.MasterWorldspaces!.Count}");
}
