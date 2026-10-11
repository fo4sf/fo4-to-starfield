// Terrain experiment 1 (docs/terrain/architecture.md, section 5): three tiny worldspaces with their own BTD terrain.
//   dotnet run -- <Starfield.esm> <output dir>
// Writes FO4TerrainExp1.esm (master Starfield.esm) and, optionally, FO4TerrainExp1_Mars.esm (override of MarsPlanetData that
// registers FO4TX_World01 as a master worldspace on Mars). Nothing is deployed; the lead copies files by hand.
//
//   FO4TX_World01  overlay component -> SFBK FO4TX_Block01 -> Data\TERRAIN\FO4TX_World01.btd   (record path AND name match)
//   FO4TX_World02  overlay component -> SFBK FO4TX_Block02 -> Data\TERRAIN\FO4TX_Shared02.btd  (record path only)
//   FO4TX_World03  no overlay component, file Data\TERRAIN\FO4TX_World03.btd                  (name only, like TempJemisonWorld)
// Each worldspace copies the vanilla Mars landing world LC172World (02DF8C; 5 x 5 cells -2..2, 3 x 3-cell BTD) minus its
// cells/offset tables, and gets 25 empty exterior cells (-2..2) plus a COC marker in cell (0,0) (EditorID FO4TX_W0nSpawn).
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;

var sfPath = args[0];
var outDir = args[1];
Directory.CreateDirectory(outDir);
var sfData = Path.GetDirectoryName(Path.GetFullPath(sfPath))!;
var release = StarfieldRelease.Starfield;
var sfEsm = ModKey.FromNameAndExtension("Starfield.esm");
using var sf = StarfieldMod.CreateFromBinaryOverlay(sfPath, release);

var templateWorld = sf.Worldspaces.First(w => w.FormKey.ID == 0x02DF8C);                 // LC172World (Mars)
var templateBlock = sf.EnumerateMajorRecords<ISurfaceBlockGetter>().First(b => b.FormKey.ID == 0x102382); // OverlayBlockLC172World

var modKey = ModKey.FromNameAndExtension("FO4TerrainExp1.esm");
var mod = new StarfieldMod(modKey, release);
mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
uint next = 0x800;
FormKey NewKey() => new(modKey, next++);

const ushort BorderRaw = 22282;     // 10.0 m in a -500..1000 m BTD: round((10 + 500) / 1500 * 65535)

SurfaceBlock MakeBlock(string edid, string btdPath)
{
    var b = (SurfaceBlock)templateBlock.Duplicate(NewKey());
    b.EditorID = edid;
    b.ANAM = btdPath;
    b.DNAM = new SurfaceBlockIntItem { First = 5, Second = 5 };              // cells per side (vanilla: DNAM = BTD size / 128)
    b.FNAM = Enumerable.Repeat(new[] { (byte)(BorderRaw & 0xFF), (byte)(BorderRaw >> 8) }, 8).SelectMany(x => x).ToArray(); // "Connections": raw border heights
    b.Components.Clear();                                                    // drop BlockEditorMetaData (CK bookkeeping)
    mod.SurfaceBlocks.Add(b);
    return b;
}

Worldspace MakeWorld(int n, SurfaceBlock? block)
{
    var w = (Worldspace)templateWorld.Duplicate(NewKey());
    w.EditorID = $"FO4TX_World0{n}";
    w.Name = $"FO4 Terrain Test 0{n}";
    w.SubCells.Clear();
    w.TopCell = null;
    w.OffsetData = null;
    w.CellSizeData = null;
    w.Location.Clear();                                                      // LC172's location has quest aliases; keep it out
    var overlay = w.Components.OfType<WorldSpaceOverlayComponent>().FirstOrDefault();
    if (block == null) w.Components.Clear();
    else overlay!.SurfaceBlock.SetTo(block.FormKey);

    // 25 empty exterior cells -2..2 (vanilla LC172World has the same grid), COC marker + a vanilla platform in cell (0,0)
    var blocks = new Dictionary<(int, int), WorldspaceBlock>();
    var subs = new Dictionary<(int, int), WorldspaceSubBlock>();
    for (int x = -2; x <= 2; x++)
        for (int y = -2; y <= 2; y++)
        {
            var c = new Cell(NewKey(), release) { Grid = new CellGrid { Point = new P2Int(x, y) } };
            if (x == 0 && y == 0)
            {
                c.EditorID = $"FO4TX_W0{n}Spawn";
                // COCMarkerHeading (000032) on the flat 10 m ground, facing north
                c.Temporary.Add(new PlacedObject(NewKey(), release) { Base = new FormLinkNullable<IPlaceableObjectGetter>(new FormKey(sfEsm, 0x000032)), Position = new P3Float(50, 50, 12), Rotation = new P3Float(0, 0, 0) });
                // NA_Transit_PlatformA_Str08x08_01 (050776): x -2..6 around its origin, top at z 0 -> top flush with 10 m ground
                c.Temporary.Add(new PlacedObject(NewKey(), release) { Base = new FormLinkNullable<IPlaceableObjectGetter>(new FormKey(sfEsm, 0x050776)), Position = new P3Float(90, 50, 10), Rotation = new P3Float(0, 0, 0) });
            }
            int bx = (int)Math.Floor(x / 32.0), by = (int)Math.Floor(y / 32.0), sx = (int)Math.Floor(x / 8.0), sy = (int)Math.Floor(y / 8.0);
            if (!blocks.TryGetValue((bx, by), out var blk)) { blk = new WorldspaceBlock { BlockNumberX = (short)bx, BlockNumberY = (short)by, GroupType = GroupTypeEnum.ExteriorCellBlock }; blocks[(bx, by)] = blk; w.SubCells.Add(blk); }
            if (!subs.TryGetValue((sx, sy), out var sub)) { sub = new WorldspaceSubBlock { BlockNumberX = (short)sx, BlockNumberY = (short)sy, GroupType = GroupTypeEnum.ExteriorCellSubBlock }; subs[(sx, sy)] = sub; blk.Items.Add(sub); }
            sub.Items.Add(c);
        }
    w.TopCell = new Cell(NewKey(), release) { Flags = Cell.Flag.HasWater };   // persistent top cell, empty
    mod.Worldspaces.Add(w);
    return w;
}

var b1 = MakeBlock("FO4TX_Block01", @"Data\TERRAIN\FO4TX_World01.btd");
var b2 = MakeBlock("FO4TX_Block02", @"Data\TERRAIN\FO4TX_Shared02.btd");
var w1 = MakeWorld(1, b1);
MakeWorld(2, b2);
MakeWorld(3, null);
mod.ModHeader.Stats.NextFormID = next;

void Save(StarfieldMod m)
{
    var path = Path.Combine(outDir, m.ModKey.FileName);
    m.BeginWrite.ToPath(path).WithLoadOrderFromHeaderMasters().WithDataFolder(sfData)
        .WithKnownMasters(new KeyedMasterStyle(sfEsm, MasterStyle.Full)).Write();
    Console.WriteLine($"wrote {path} ({new FileInfo(path).Length:N0} bytes)");
}
Save(mod);

// optional planet registration, a separate plugin so it can be switched on or off: Mars, away from the vanilla Mars sites
var marsKey = ModKey.FromNameAndExtension("FO4TerrainExp1_Mars.esm");
var mars = new StarfieldMod(marsKey, release);
mars.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
var planet = (Planet)sf.Planets.First(p => p.EditorID == "MarsPlanetData").DeepCopy();   // same FormKey = override
mars.Planets.Add(planet);
planet.MasterWorldspaces.Add(new MasterWorldspace { Worldspace = new FormLink<IWorldspaceGetter>(w1.FormKey), Latitude = 1.2, Longitude = 0.2 });
mars.ModHeader.Stats.NextFormID = 0x800;
var marsPath = Path.Combine(outDir, marsKey.FileName);
mars.BeginWrite.ToPath(marsPath).WithLoadOrder(sfEsm, modKey)
    .WithKnownMasters(new KeyedMasterStyle(sfEsm, MasterStyle.Full), new KeyedMasterStyle(modKey, MasterStyle.Full)).Write();
Console.WriteLine($"wrote {marsPath} ({new FileInfo(marsPath).Length:N0} bytes); Mars master worldspaces now {planet.MasterWorldspaces.Count}");
