// Terrain experiment 2 (docs/terrain/experiment2.md): one worldspace with the real Commonwealth heights around Red Rocket.
//   dotnet run -- <Starfield.esm> <staging dir>
// Reads <staging dir>/exp2_params.json (written by scripts/terrain/make_exp2.py build) and writes FO4TerrainExp2.esm
// (master Starfield.esm, own FormIDs from 0x800, nothing shared with FO4Port.esm). Nothing is deployed.
//
//   FO4CW_Commonwealth  overlay component -> SFBK FO4CW_CommonwealthBlock -> Data\TERRAIN\FO4CW_Commonwealth.btd
//                       the BTD is reachable by the record path AND by the name, like experiment 1's FO4TX_World01
// The worldspace copies the vanilla Mars landing world LC172World (02DF8C) exactly as experiment 1 does (minus cells,
// offsets and location) so the two experiments differ only in the BTD and the cell grid; it gets every exterior cell
// the BTD covers (n x n, empty) and a COC marker 2 m above the terrain at the Red Rocket building origin.
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

int n = I("n"), cmin = I("cell_min"), cmax = I("cell_max");
var conn = prm.GetProperty("connections").EnumerateArray().Select(e => (ushort)e.GetInt32()).ToArray();

// SFBK: BTD path, size in cells, height range (= BTD header, as in vanilla), "connections" (8 raw border heights)
var block = (SurfaceBlock)templateBlock.Duplicate(NewKey());
block.EditorID = S("world") + "Block";
block.ANAM = S("btd_path");
block.DNAM = new SurfaceBlockIntItem { First = (uint)n, Second = (uint)n };
// ENAM holds two floats; Mutagen 0.55 types them as uint, so pass the IEEE bits (vanilla akilacity: 0xC3FA0000 = -500)
block.ENAM = new SurfaceBlockFloatItem { First = BitConverter.SingleToUInt32Bits(F("hmin")), Second = BitConverter.SingleToUInt32Bits(F("hmax")) };
block.FNAM = conn.SelectMany(v => new[] { (byte)(v & 0xFF), (byte)(v >> 8) }).ToArray();
block.Components.Clear();                                                    // drop BlockEditorMetaData (CK bookkeeping)
mod.SurfaceBlocks.Add(block);

// WRLD
var w = (Worldspace)templateWorld.Duplicate(NewKey());
w.EditorID = S("world");
w.Name = "Commonwealth (FO4 terrain experiment 2)";
w.SubCells.Clear();
w.TopCell = null;
w.OffsetData = null;
w.CellSizeData = null;
w.Location.Clear();                                                          // LC172's location has quest aliases; keep it out
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
w.TopCell = new Cell(NewKey(), release) { Flags = Cell.Flag.HasWater };   // persistent top cell, empty (as experiment 1)
mod.Worldspaces.Add(w);
mod.ModHeader.Stats.NextFormID = next;

var path = Path.Combine(outDir, modKey.FileName);
mod.BeginWrite.ToPath(path).WithLoadOrderFromHeaderMasters().WithDataFolder(sfData)
    .WithKnownMasters(new KeyedMasterStyle(sfEsm, MasterStyle.Full)).Write();
Console.WriteLine($"wrote {path} ({new FileInfo(path).Length:N0} bytes): WRLD {w.FormKey} {w.EditorID}, SFBK {block.FormKey} -> {block.ANAM}, " +
                  $"{cells} cells {cmin}..{cmax}, COC {S("coc")} at ({spawn[0]}, {spawn[1]}, {spawn[2]}) in cell ({spawnCell[0]}, {spawnCell[1]}), next FormID 0x{next:X}");
