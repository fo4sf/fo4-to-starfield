// TestCell: an object test room. FO4SFTestCell.esm holds one interior cell, reached with `coc <cell>`: a flat floor of
// vanilla platform tiles, an even grid of vanilla omni lights, and converted FO4Port.esm objects in labelled spots next to
// vanilla Starfield controls, each alone, unrotated and at scale 1. An object that misbehaves here misbehaves on its own;
// one that only misbehaves in its home cell points at its placement or its neighbours.
//
// The vanilla FormIDs are the ones dotnet/PluginSpike's door test cell (FO4PORT_DOORTEST) already writes:
//   050776 NA_Transit_PlatformA_Str08x08_01 (8 x 8 m, from its origin x 0..8, top z 0; its y extent is not recorded, so
//          the floor reaches one tile past the spots on every side), 03D38C LGT_ShipInterior_Omni_NS_Neutral_2k,
//   000032 COCMarkerHeading, lighting template 006658 ShipInteriorLT, image space 122393, cubemap Cell_HiTechHallCube.
//
// The layout (tools/testcell/layout.json) is rows of items; spot <row><n> sits at x = (n - 1) * spacing, y = row index *
// spacing, z 0. The arrival is spacing m before A1, facing +X along row A; later rows lie to the left (+Y). An item is
//   {"edid": "FO4Port_X"}            a converted base by editor ID (or the one "FO4Port_X_<hash>" convert_batch gives on a clash)
//   {"vanilla": "0AA24A"}            a Starfield.esm base, by its FormID
//   {"from_cell": "FO4Port_Vault95", "type": "DOOR", "max": 4}
//                                    the distinct bases of that type the port places in that cell (temporary and
//                                    persistent), in the port's FormID order; that is allocation order, which a rebuild
//                                    with new references no longer matches to FO4 placement, so "max" (optional) picks
//                                    by FormID, not by any FO4 meaning
// plus "name" and "note" for the sheet. Missing items are listed as MISSING and leave their spot empty.
//
// usage: TestCell build <FO4Port.esm> <layout.json> <out dir>   writes FO4SFTestCell.esm, spots.json and spots.md
//        TestCell fixture <out dir>                              a synthetic FO4Port.esm for tests/test_test_cell.py
using System.Globalization;
using System.Text;
using System.Text.Json;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;

const uint Floor = 0x050776, Omni = 0x03D38C, CocMarker = 0x000032, LightingTemplate = 0x006658, ImageSpace = 0x122393;
const float Tile = 8f, LightZ = 4f;
var release = StarfieldRelease.Starfield;
var sfKey = ModKey.FromFileName("Starfield.esm");

static int Usage()
{
    Console.Error.WriteLine("usage: TestCell build <FO4Port.esm> <layout.json> <out dir> | TestCell fixture <out dir>");
    return 2;
}
static string F(float v) => v.ToString("0.##", CultureInfo.InvariantCulture);

void AddCell(StarfieldMod mod, Cell cell)
{
    var cid = cell.FormKey.ID;
    var block = new CellBlock { BlockNumber = (int)(cid % 10), GroupType = GroupTypeEnum.InteriorCellBlock };
    var sub = new CellSubBlock { BlockNumber = (int)((cid / 10) % 10), GroupType = GroupTypeEnum.InteriorCellSubBlock };
    sub.Cells.Add(cell);
    block.SubBlocks.Add(sub);
    mod.Cells.Records.Add(block);
}

void Write(StarfieldMod mod, string outDir, params ModKey[] masters)
{
    Directory.CreateDirectory(outDir);
    var path = Path.Combine(outDir, mod.ModKey.FileName);
    // an existing plugin stays until the write succeeds; Mutagen needs the plugin's own file name, so write in a temp folder
    var tmpDir = Path.Combine(outDir, ".tmp-" + Guid.NewGuid().ToString("N"));
    try
    {
        Directory.CreateDirectory(tmpDir);
        var tmp = Path.Combine(tmpDir, mod.ModKey.FileName);
        mod.BeginWrite.ToPath(tmp).WithLoadOrder(masters)
            .WithKnownMasters(masters.Select(m => new KeyedMasterStyle(m, MasterStyle.Full)).ToArray()).Write();
        File.Move(tmp, path, overwrite: true);
    }
    finally
    {
        if (Directory.Exists(tmpDir)) Directory.Delete(tmpDir, true);
    }
}

if (args.Length == 2 && args[0] == "fixture")
{
    // two doors placed in FO4Port_Vault95 (one twice), a stair, a movable and a door whose editor ID clashed
    var key = ModKey.FromFileName("FO4Port.esm");
    var fmod = new StarfieldMod(key, release);
    fmod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
    uint n = 0x800;
    FormKey K() => new(key, n++);
    var d1 = new Door(K(), release) { EditorID = "FO4Port_VltDoor01", Model = new Model { File = "FO4Port\\VltDoor01.nif" } };
    var d2 = new Door(K(), release) { EditorID = "FO4Port_VltDoor02", Model = new Model { File = "FO4Port\\VltDoor02.nif" } };
    var st = new Static(K(), release) { EditorID = "FO4Port_BldDecoSmStairs01", Model = new Model { File = "FO4Port\\BldDecoSmStairs01.nif" } };
    var mv = new MoveableStatic(K(), release) { EditorID = "FO4Port_TrashcanMetalOffice01", Model = new Model { File = "FO4Port\\TrashcanMetalOffice01.nif" } };
    var hx = new Door(K(), release) { EditorID = "FO4Port_PryDoor01_0123456789abcdef", Model = new Model { File = "FO4Port\\PryDoor01.nif" } };
    var d3 = new Door(K(), release) { EditorID = "FO4Port_VltLoadDoor01", Model = new Model { File = "FO4Port\\VltLoadDoor01.nif" } };
    foreach (var d in new[] { d1, d2, hx, d3 }) fmod.Doors.Add(d);
    fmod.Statics.Add(st);
    fmod.MoveableStatics.Add(mv);
    var fcell = new Cell(K(), release) { EditorID = "FO4Port_Vault95", Flags = Cell.Flag.IsInteriorCell };
    // the load door is persistent, as TeleportLinks makes linked load doors, and placed between the temporary doors
    foreach (var (b, x) in new IMajorRecordGetter[] { st, d1, d3, d1, d2 }.Select((b, i) => (b, i)))
    {
        var r = new PlacedObject(K(), release) { Base = new FormLinkNullable<IPlaceableObjectGetter>(b.FormKey), Position = new P3Float(x * 5, 0, 0) };
        if (b == d3) { r.MajorRecordFlagsRaw |= 0x400; fcell.Persistent.Add(r); }
        else fcell.Temporary.Add(r);
    }
    AddCell(fmod, fcell);
    fmod.ModHeader.Stats.NextFormID = n;
    Write(fmod, args[1], sfKey);
    Console.WriteLine($"wrote {Path.Combine(args[1], key.FileName)}");
    return 0;
}

if (args.Length != 4 || args[0] != "build") return Usage();

var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
styles.Set(new KeyedMasterStyle(sfKey, MasterStyle.Full));
using var port = StarfieldMod.CreateFromBinaryOverlay(args[1], release, new BinaryReadParameters { MasterFlagsLookup = styles });
var portKey = port.ModKey;

// the port's placeable bases by editor ID, with their record type
var bases = new Dictionary<string, (FormKey Key, string Type)>(StringComparer.OrdinalIgnoreCase);
var typeOf = new Dictionary<FormKey, string>();
void Index(IEnumerable<IMajorRecordGetter> recs, string type)
{
    foreach (var r in recs)
    {
        typeOf[r.FormKey] = type;
        if (r.EditorID is string e) bases[e] = (r.FormKey, type);
    }
}
Index(port.Statics, "STAT");
Index(port.MoveableStatics, "MSTT");
Index(port.Doors, "DOOR");
Index(port.Furniture, "FURN");
Index(port.Activators, "ACTI");
Index(port.Containers, "CONT");
Index(port.MiscItems, "MISC");
Index(port.Terminals, "TERM");
var cells = port.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells)
    .Where(c => c.EditorID != null).ToDictionary(c => c.EditorID!, StringComparer.OrdinalIgnoreCase);

using var layoutDoc = JsonDocument.Parse(File.ReadAllText(args[2]));
var layout = layoutDoc.RootElement;
var cellEdid = layout.TryGetProperty("cell", out var ce) ? ce.GetString()! : "FO4SF_TestCell";
var spacing = layout.TryGetProperty("spacing_m", out var sp) ? sp.GetSingle() : 4f;
if (!(spacing > 0 && float.IsFinite(spacing))) { Console.Error.WriteLine($"spacing_m {spacing}: not a positive number"); return 2; }

// every spot: row letter, column, base (null when missing), what the sheet says
var spots = new List<(string Label, P3Float Pos, FormKey? Base, string Type, string Name, string Source, string Note)>();
var rowTitles = new List<(string Row, string Title)>();
int rowIndex = 0;
foreach (var row in layout.GetProperty("rows").EnumerateArray())
{
    var letter = row.GetProperty("row").GetString()!;
    rowTitles.Add((letter, row.TryGetProperty("title", out var t) ? t.GetString() ?? "" : ""));
    int col = 0;
    void Spot(FormKey? b, string type, string name, string source, string note)
    {
        col++;
        spots.Add(($"{letter}{col}", new P3Float((col - 1) * spacing, rowIndex * spacing, 0), b, type, name, source, note));
    }
    foreach (var it in row.GetProperty("items").EnumerateArray())
    {
        string S(string k) => it.TryGetProperty(k, out var v) ? v.GetString() ?? "" : "";
        if (S("edid") is { Length: > 0 } edid)
        {
            if (!bases.TryGetValue(edid, out var hit))
            {
                // convert_batch.editor_id appends _<16 hex> on a clash; take it only when exactly one matches
                var clash = bases.Where(kv => kv.Key.StartsWith(edid + "_", StringComparison.OrdinalIgnoreCase) &&
                                              kv.Key.Length == edid.Length + 17).ToList();
                if (clash.Count == 1) hit = clash[0].Value;
            }
            Spot(hit.Key.IsNull ? null : hit.Key, hit.Type ?? "", S("name") is { Length: > 0 } nm ? nm : edid, $"FO4Port.esm {edid}", S("note"));
        }
        else if (S("vanilla") is { Length: > 0 } hex)
            Spot(new FormKey(sfKey, Convert.ToUInt32(hex, 16)), "", S("name"), $"Starfield.esm {hex.ToUpperInvariant()}", S("note"));
        else if (S("from_cell") is { Length: > 0 } src)
        {
            var type = S("type");
            var max = it.TryGetProperty("max", out var m) ? m.GetInt32() : int.MaxValue;
            if (!cells.TryGetValue(src, out var c)) { Spot(null, type, $"{type} from {src}", $"FO4Port.esm cell {src}", "no such cell in the port"); continue; }
            // FormID order across both groups: TeleportLinks moves linked load doors into the persistent group, so neither
            // group alone keeps the allocation order (PluginSpike's stable map gives new references max + 1)
            var picked = c.Temporary.Concat(c.Persistent).OfType<IPlacedObjectGetter>().OrderBy(r => r.FormKey.ID)
                .Select(r => r.Base.FormKey).Where(k => typeOf.TryGetValue(k, out var ty) && (type == "" || ty == type))
                .Distinct().Take(max).ToList();
            if (picked.Count == 0) Spot(null, type, $"{type} from {src}", $"FO4Port.esm cell {src}", "none placed there");
            foreach (var k in picked)
            {
                var e = bases.FirstOrDefault(kv => kv.Value.Key == k).Key ?? k.ToString();
                Spot(k, typeOf[k], e, $"FO4Port.esm cell {src}", S("note"));
            }
        }
        else { Console.Error.WriteLine($"row {letter}: an item needs edid, vanilla or from_cell"); return 2; }
    }
    rowIndex++;
}
if (spots.Count == 0) { Console.Error.WriteLine("the layout places nothing"); return 2; }

// ---- the plugin ------------------------------------------------------------------------------------------------------
var modKey = ModKey.FromFileName("FO4SFTestCell.esm");
var mod = new StarfieldMod(modKey, release);
mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;     // as every plugin of ours that loads
uint next = 0x800;
FormKey Id() => new(modKey, next++);
var cell = new Cell(Id(), release) { EditorID = cellEdid, Flags = Cell.Flag.IsInteriorCell };
cell.LightingTemplate.SetTo(new FormKey(sfKey, LightingTemplate));
cell.ImageSpace.SetTo(new FormKey(sfKey, ImageSpace));
cell.EnvironmentMap = "Data\\Textures\\Cubemaps\\Cell_HiTechHallCube.dds";
var zero = new P3Float(0, 0, 0);
PlacedObject Ref(FormKey b, P3Float pos, P3Float rot, string? edid = null) =>
    new(Id(), release) { EditorID = edid, Base = new FormLinkNullable<IPlaceableObjectGetter>(b), Position = pos, Rotation = rot };

float maxX = spots.Max(s => s.Pos.X), maxY = spots.Max(s => s.Pos.Y);
cell.Temporary.Add(Ref(new FormKey(sfKey, CocMarker), new P3Float(-spacing, 0, 0.1f), new P3Float(0, 0, (float)(Math.PI / 2))));
int tiles = 0, lights = 0;
for (float x = -spacing - Tile; x <= maxX + Tile; x += Tile)
    for (float y = -Tile; y <= maxY + Tile; y += Tile) { cell.Temporary.Add(Ref(new FormKey(sfKey, Floor), new P3Float(x, y, 0), zero)); tiles++; }
for (float x = -spacing; x <= maxX + spacing; x += Tile)
    for (float y = 0; y <= maxY + spacing; y += Tile) { cell.Temporary.Add(Ref(new FormKey(sfKey, Omni), new P3Float(x, y, LightZ), zero)); lights++; }
var refIds = new Dictionary<string, FormKey>();
foreach (var s in spots.Where(s => s.Base != null))
{
    var r = Ref(s.Base!.Value, s.Pos, zero, $"FO4SF_Test_{s.Label}");
    cell.Temporary.Add(r);
    refIds[s.Label] = r.FormKey;
}
AddCell(mod, cell);
mod.ModHeader.Stats.NextFormID = next;
var outDir = args[3];
Write(mod, outDir, sfKey, portKey);

// ---- the sheet -------------------------------------------------------------------------------------------------------
var missing = spots.Count(s => s.Base == null);
File.WriteAllText(Path.Combine(outDir, "spots.json"), JsonSerializer.Serialize(new
{
    plugin = modKey.FileName.String, cell = cellEdid, port = Path.GetFileName(args[1]),
    port_sha256 = Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(File.ReadAllBytes(args[1]))).ToLowerInvariant(),
    spacing_m = spacing,
    spots = spots.Select(s => new
    {
        spot = s.Label, x = s.Pos.X, y = s.Pos.Y, z = s.Pos.Z, name = s.Name, type = s.Type, source = s.Source, note = s.Note,
        @base = s.Base?.ToString(), reference = refIds.TryGetValue(s.Label, out var k) ? k.ToString() : null, missing = s.Base == null,
    }),
}, new JsonSerializerOptions { WriteIndented = true }));
var md = new StringBuilder();
md.AppendLine($"# {cellEdid}\n");
md.AppendLine($"`coc {cellEdid}` arrives {F(spacing)} m before spot A1, facing along row A. Later rows lie to the left, " +
              $"{F(spacing)} m apart; spots in a row are {F(spacing)} m apart. Every object stands unrotated at scale 1 on a flat floor.\n");
foreach (var (r, title) in rowTitles)
{
    md.AppendLine($"## Row {r}{(title.Length > 0 ? ": " + title : "")}\n");
    md.AppendLine("| Spot | Object | From | Note |\n|---|---|---|---|");
    foreach (var s in spots.Where(s => s.Label.StartsWith(r) && s.Label.Substring(r.Length).All(char.IsDigit)))
        md.AppendLine($"| {s.Label} | {(s.Base == null ? "MISSING " : "")}{s.Name}{(s.Type.Length > 0 ? $" ({s.Type})" : "")} | {s.Source} | {s.Note} |");
    md.AppendLine();
}
File.WriteAllText(Path.Combine(outDir, "spots.md"), md.ToString());
Console.WriteLine($"wrote {Path.Combine(outDir, modKey.FileName)} ({new FileInfo(Path.Combine(outDir, modKey.FileName)).Length:N0} bytes): " +
                  $"cell {cellEdid} {cell.FormKey}, {refIds.Count} objects in {spots.Count} spots ({missing} missing), {tiles} floor tiles, {lights} lights");
foreach (var s in spots.Where(s => s.Base == null)) Console.WriteLine($"  MISSING {s.Label}: {s.Name} ({s.Source}) {s.Note}");
return 0;
