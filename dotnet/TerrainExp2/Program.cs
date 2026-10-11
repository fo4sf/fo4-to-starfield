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
int cells = 0;
for (int x = cmin; x <= cmax; x++)
    for (int y = cmin; y <= cmax; y++)
    {
        var c = new Cell(NewKey(), release) { Grid = new CellGrid { Point = new P2Int(x, y) } };
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
mod.Worldspaces.Add(w);
mod.ModHeader.Stats.NextFormID = next;

var path = Path.Combine(outDir, modKey.FileName);
mod.BeginWrite.ToPath(path).WithLoadOrderFromHeaderMasters().WithDataFolder(sfData)
    .WithKnownMasters(new KeyedMasterStyle(sfEsm, MasterStyle.Full)).Write();
Console.WriteLine($"wrote {path} ({new FileInfo(path).Length:N0} bytes): WRLD {w.FormKey} {w.EditorID}, SFBK {block.FormKey} -> {block.ANAM}, " +
                  $"FNAM {block.FNAM?.Length} B, INAM {block.INAM}, HNAM {block.HNAM}, location {w.Location.FormKeyNullable}, anchor {anchorKey}, " +
                  $"{cells} cells {cmin}..{cmax}, COC {S("coc")} at ({spawn[0]}, {spawn[1]}, {spawn[2]}) in cell ({spawnCell[0]}, {spawnCell[1]}), next FormID 0x{next:X}");

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
