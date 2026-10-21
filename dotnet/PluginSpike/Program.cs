// Plugin writer for converted assets (S2 -> WP-08 / WP-10).
//   dotnet run -- <output dir> <manifest.json> [cell.json ...]
//   dotnet run -- teleports <FO4Port.esm>        read a written plugin back and list its load-door teleport links (offline check)
// Creates FO4Port.esm with one STAT per converted item and, for each cell export from dotnet/Fo4Export, an interior cell
// "FO4Port_<cell>" holding every reference whose model was converted, placed at the Fallout 4 position / 70 (metres), same rotation
// (radians) and scale. Initially-disabled FO4 references stay initially disabled; door references FO4 opens by default
// start open (locks are counted, not written). Manifest items marked `load_door` become
// graph-less DOOR records; when both ends of a load door pair are placed (both cell exports given), the references get the
// Starfield teleport link (XTEL) and become persistent (TeleportLinks.cs). Load doors whose other end is not in the build
// stay shut and are listed in <output dir>/teleports.json. Manifest items with "pose" (an FO4 reference's ragdoll pose baked
// into a model of its own, scripts/convert_batch.py) are used for the references they list only (PosedBases.cs).
//
// FormIDs are STABLE: <output dir>/formids.json maps an identity key to its FormID and is reused on every run, so adding or
// removing assets never renumbers existing records (saves and cross-references keep working). Keys:
//   STAT:<editor id>   MSTT:<editor id> (movable items)   DOOR:<editor id>   CELL:<cell name>
//   REFR:<cell name>:<source FO4 FormKey>   (lights and COC markers use their source ref)
using System.Text.Json;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;

if (args.Length == 2 && args[0] == "teleports") { TeleportLinks.List(args[1], Console.Out); return; }

const float UnitsPerMetre = 70f;
var outDir = args[0];
Directory.CreateDirectory(outDir);

var modKey = ModKey.FromNameAndExtension("FO4Port.esm");
var sfEsm = ModKey.FromNameAndExtension("Starfield.esm");
var release = StarfieldRelease.Starfield;
var mod = new StarfieldMod(modKey, release);
mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;

// ---- stable FormID map ------------------------------------------------------------------------------------------------
var mapPath = Path.Combine(outDir, "formids.json");
var ids = StableFormIds.Load(mapPath);
var next = ids.Count == 0 ? StableFormIds.FirstId : ids.Values.Max() + 1;
var usedThisRun = new HashSet<string>();
FormKey Id(string key)
{
    if (!usedThisRun.Add(key)) throw new InvalidOperationException($"duplicate identity key {key}");
    if (!ids.TryGetValue(key, out var v))
    {
        if (next > StableFormIds.LastId) throw new InvalidOperationException($"FormID space exhausted; cannot allocate {key}");
        v = next++;
        ids[key] = v;
    }
    return new FormKey(modKey, v);
}
// load_door_anim.py sounds: a vanilla door's open / close sound (WWise start / stop events; condition and event mapping
// FormKeys of Starfield.esm) on a rig entry of the manifest; null when the entry has none (every manifest before 2026-10-19)
SoundReference? VanillaSound(JsonElement rig, string name)
{
    if (rig.ValueKind != JsonValueKind.Object || !rig.TryGetProperty(name, out var s) || s.ValueKind != JsonValueKind.Object) return null;
    var r = new SoundReference { Start = Guid.Parse(s.GetProperty("start").GetString()!), Stop = Guid.Parse(s.GetProperty("stop").GetString()!) };
    if (s.TryGetProperty("condition", out var c) && c.GetString() is string ck) r.Condition.SetTo(FormKey.Factory(ck));
    if (s.TryGetProperty("mapping", out var m) && m.GetString() is string mk) r.EventMapping.SetTo(FormKey.Factory(mk));
    return r;
}

// load_door_anim.py flags: the FO4 DOOR's FNAM flags (fo4_door_flags; same bits in Starfield, D13), only the six FO4 has;
// 0 when the entry has none (every manifest before 2026-10-20), as before
Door.Flag Fo4DoorFlags(JsonElement entry) =>
    entry.ValueKind == JsonValueKind.Object && entry.TryGetProperty("fo4_door_flags", out var f) ? (Door.Flag)(f.GetInt32() & 0x7E) : 0;

// ---- statics ----------------------------------------------------------------------------------------------------------
var items = new List<(string editorId, string model, string source, JsonElement? door, JsonElement? loadDoor, bool movable,
                       IReadOnlyList<string> posedRefs)>();
using var manifestDoc = JsonDocument.Parse(File.ReadAllText(args[1]));
foreach (var it in manifestDoc.RootElement.GetProperty("items").EnumerateArray())
    items.Add((it.GetProperty("editor_id").GetString()!, it.GetProperty("model").GetString()!, it.GetProperty("source").GetString()!,
               it.TryGetProperty("door", out var dj) ? dj : null, it.TryGetProperty("load_door", out var lj) ? lj : null,
               it.TryGetProperty("movable", out _), PosedBases.RefsOf(it)));

// source FO4 model -> (base record, origin offset in metres). Hinged doors become DOOR records animated by a vanilla door's
// graph / skeleton / animations; their NIF origin sits at a different point, so references are shifted by origin_offset.
var bySource = new Dictionary<string, (FormKey key, P3Float offset)>(StringComparer.OrdinalIgnoreCase);
// FO4 reference FormKey -> the base of its own posed model (manifest "pose"); wins over bySource for that reference
var byRef = new Dictionary<string, (FormKey key, P3Float offset)>();
var openingDoors = new HashSet<FormKey>();   // bases of animated (non-load) doors: their references take FO4's open state
var xtelLoadBases = new Dictionary<FormKey, FormKey>();   // animated load door -> its copy with the vanilla load graph (XTEL refs)
var ownRigDoors = new HashSet<FormKey>();    // manifest rig "native": an opening rig, never a load door (TeleportLinks)
var modelOf = new Dictionary<FormKey, string>();   // STAT / MSTT base -> its model: what a promoted reference's new base carries
int doors = 0, loadDoors = 0, animatedLoadDoors = 0, movables = 0, posed = 0;
foreach (var (editorId, model, source, door, loadDoor, movable, posedRefs) in items)
{
    if (posedRefs.Count > 0 && (door is not null || loadDoor is not null))
        throw new InvalidOperationException($"posed item {editorId} is a door; posed models are statics or movable statics");
    if (posedRefs.Count > 0) posed++;
    if (loadDoor is JsonElement ld)
    {
        // FO4 load door: a DOOR record with the static-looking converted model (native collision kept, no animation graph).
        // Starfield.esm: 458 of its 964 XTEL references use a DOOR base without an animation graph (322 LoadElevator_InvisibleDoor,
        // 89 AutoloadDoor_Cave, ...; docs/ai/research-log.md 2026-10-10), so the teleport needs no graph; that a visible graph-less
        // door also teleports on the player's activation is still to be seen in game. The link itself is written per reference
        // below. Flags 0, SoundLevel Normal and FacingAxisOverride BasedOnBounds as the vanilla visible load doors
        // (IndIntRmSmWallMid_DoorA01_Load 2AC325).
        var rec = new Door(Id("DOOR:" + editorId), release)
        {
            EditorID = editorId, Model = new Model { File = model }, Name = "Door",
            SoundLevel = SoundLevel.Normal, FacingAxisOverride = Door.FacingAxisOverrideEnum.BasedOnBounds,
            Flags = Fo4DoorFlags(ld),
        };
        // newer manifests carry the model's bounds (metres, NIF space); older ones hold only a note string
        if (ld.ValueKind == JsonValueKind.Object && ld.TryGetProperty("bounds", out var lb))
            rec.ObjectBounds = new ObjectBounds
            {
                First = new P3Float(lb[0][0].GetSingle(), lb[0][1].GetSingle(), lb[0][2].GetSingle()),
                Second = new P3Float(lb[1][0].GetSingle(), lb[1][1].GetSingle(), lb[1][2].GetSingle()),
            };
        // load_door.anim (scripts/door_bridge/load_door_anim.py, convert_batch.py --rig-load-doors): the load door opens
        // before the trip, as Starfield's own visible load doors do. The record takes the rig's graph, skeleton and
        // clips (and the twin's rigged model when the rig is borrowed); references shift by the rig's origin offset as
        // the opening doors' do. Without "anim" (every manifest before 2026-10-19) nothing here changes.
        var loadOffset = new P3Float(0, 0, 0);
        if (ld.ValueKind == JsonValueKind.Object && ld.TryGetProperty("anim", out var la) && la.ValueKind == JsonValueKind.Object)
        {
            var animModel = la.TryGetProperty("model", out var lm) && lm.GetString() is string twinModel ? twinModel : model;
            rec.Model = new Model { File = animModel };
            if (la.TryGetProperty("bounds", out var ab))
                rec.ObjectBounds = new ObjectBounds
                {
                    First = new P3Float(ab[0][0].GetSingle(), ab[0][1].GetSingle(), ab[0][2].GetSingle()),
                    Second = new P3Float(ab[1][0].GetSingle(), ab[1][1].GetSingle(), ab[1][2].GetSingle()),
                };
            rec.Components.Add(new AnimationGraphComponent
            {
                ANAM = la.GetProperty("anim_graph").GetString(), BNAM = la.GetProperty("skeleton").GetString(),
                CNAM = la.GetProperty("animations").GetString(),
            });
            if (la.TryGetProperty("origin_offset", out var lo))
                loadOffset = new P3Float(lo[0].GetSingle(), lo[1].GetSingle(), lo[2].GetSingle());
            animatedLoadDoors++;
            rec.OpenSound = VanillaSound(la, "open_sound");
            rec.CloseSound = VanillaSound(la, "close_sound");
            // xtel_anim_graph: the vanilla load graph of this rig (the Akila template's AK_Ext_Bld_WallA_DoorA_Load_01 1C42C2
            // plays SimpleOpenClose02_Load.agx on the same skeleton and clips; PC read A1). Vanilla XTEL doors play a *_Load
            // graph and scripted doors carry no XTEL, so the references that get an XTEL (TeleportLinks) are moved onto this
            // copy of the record with the load graph, and the scripted ones (FO4SF_AnimatedLoadDoor) keep the record above.
            if (la.TryGetProperty("xtel_anim_graph", out var xg) && xg.GetString() is string xtelGraph)
            {
                var xtel = new Door(Id("DOOR:" + editorId + ":xtel"), release)
                {
                    EditorID = editorId + "_XtelLoad", Model = new Model { File = animModel },
                    Name = "Door", SoundLevel = rec.SoundLevel, FacingAxisOverride = rec.FacingAxisOverride, Flags = rec.Flags,
                    ObjectBounds = rec.ObjectBounds.DeepCopy(),
                    OpenSound = VanillaSound(la, "open_sound"), CloseSound = VanillaSound(la, "close_sound"),
                };
                xtel.Components.Add(new AnimationGraphComponent
                {
                    ANAM = xtelGraph, BNAM = la.GetProperty("skeleton").GetString(), CNAM = la.GetProperty("animations").GetString(),
                });
                mod.Doors.Add(xtel);
                xtelLoadBases[rec.FormKey] = xtel.FormKey;
            }
        }
        mod.Doors.Add(rec);
        bySource[source.Replace('/', '\\')] = (rec.FormKey, loadOffset);
        loadDoors++;
        continue;
    }
    if (movable)
    {
        // FO4 loose item converted with a dynamic body (manifest "movable"): a MoveableStatic, as Starfield's own
        // pushable set dressing; a Static never simulates. DATA 4 as every vanilla MSTT checked (SfInspect mstt).
        var ms = new MoveableStatic(Id("MSTT:" + editorId), release) { EditorID = editorId, Model = new Model { File = model }, DATA = 4 };
        mod.MoveableStatics.Add(ms);
        modelOf[ms.FormKey] = model;
        PosedBases.Register(byRef, bySource, source, posedRefs, (ms.FormKey, new P3Float(0, 0, 0)));
        movables++;
        continue;
    }
    if (door is JsonElement d)
    {
        var rec = new Door(Id("DOOR:" + editorId), release)
        {
            // FO4PORT_DOOR_MODEL (test hook): use this model for every door, e.g. the vanilla template door's own NIF
            EditorID = editorId, Model = new Model { File = Environment.GetEnvironmentVariable("FO4PORT_DOOR_MODEL") ?? model },
            Name = "Door",
            SoundLevel = SoundLevel.Normal,                                     // DEVT 1, as vanilla doors
            FacingAxisOverride = Door.FacingAxisOverrideEnum.BasedOnBounds,     // trailing ANAM, as vanilla doors
            Flags = Fo4DoorFlags(d),
        };
        rec.OpenSound = VanillaSound(d, "open_sound");                         // load_door_anim.py sounds --ordinary-doors
        rec.CloseSound = VanillaSound(d, "close_sound");
        if (d.TryGetProperty("bounds", out var bj))                            // vanilla doors have real bounds
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
        var o = d.GetProperty("origin_offset");
        bySource[source.Replace('/', '\\')] = (rec.FormKey, new P3Float(o[0].GetSingle(), o[1].GetSingle(), o[2].GetSingle()));
        if (Environment.GetEnvironmentVariable("FO4PORT_DOOR_BASE") is string vb)   // test hook: place a vanilla DOOR instead
            bySource[source.Replace('/', '\\')] = (new FormKey(sfEsm, Convert.ToUInt32(vb, 16)), new P3Float(0, 0, 0));
        openingDoors.Add(bySource[source.Replace('/', '\\')].key);
        if (d.TryGetProperty("rig", out var rig) && rig.GetString() == "native") ownRigDoors.Add(rec.FormKey);
        doors++;
        continue;
    }
    var stat = new Static(Id("STAT:" + editorId), release) { EditorID = editorId, Model = new Model { File = model } };
    mod.Statics.Add(stat);
    modelOf[stat.FormKey] = model;
    PosedBases.Register(byRef, bySource, source, posedRefs, (stat.FormKey, new P3Float(0, 0, 0)));
}
Console.WriteLine($"{items.Count - doors - loadDoors - movables} statics, {movables} movable statics, {doors} doors, {loadDoors} load doors" +
                  (animatedLoadDoors > 0 ? $" ({animatedLoadDoors} open before the trip)" : "") + "; " +
                  $"{posed} of these are posed models for {byRef.Count} references");

// FO4 / Starfield reference rotation (radians): Bethesda angles turn CLOCKWISE seen from the positive axis, so the matrix
// uses the negated angles; applied X, then Y, then Z. Rotates a door-local offset into the cell. (0 / 180 degree doors are
// the same either way; the 135 / 225 degree double doors in Parsons looked misplaced with the counter-clockwise version.
// To verify in game.)
static P3Float RotateOffset(P3Float v, P3Float r, float scale)
{
    double cx = Math.Cos(-r.X), sx = Math.Sin(-r.X), cy = Math.Cos(-r.Y), sy = Math.Sin(-r.Y), cz = Math.Cos(-r.Z), sz = Math.Sin(-r.Z);
    double x = v.X * scale, y = v.Y * scale, z = v.Z * scale;
    double y1 = y * cx - z * sx, z1 = y * sx + z * cx;           // about X
    double x2 = x * cy + z1 * sy, z2 = -x * sy + z1 * cy;          // about Y
    double x3 = x2 * cz - y1 * sz, y3 = x2 * sz + y1 * cz;         // about Z
    return new P3Float((float)x3, (float)y3, (float)z2);
}

// Optional per-cell lighting overrides: <output dir>/lighting.json = { "<cell>": { "LIGHTING_TEMPLATE": "06BCF8", ... },
// "*": { ...defaults for every cell... } }. Keys: LIGHTING_TEMPLATE, IMAGE_SPACE, ENV_MAP, OMNI_LIGHT, LIGHT_MERGE_M.
// Lookup order: cell entry, "*" entry, environment variable, built-in default.
var lightCfgPath = Path.Combine(outDir, "lighting.json");
var lightCfg = File.Exists(lightCfgPath)
    ? JsonSerializer.Deserialize<Dictionary<string, Dictionary<string, string>>>(File.ReadAllText(lightCfgPath))!
    : new Dictionary<string, Dictionary<string, string>>();
string Setting(string cell, string key, string fallback) =>
    lightCfg.TryGetValue(cell, out var c) && c.TryGetValue(key, out var v) ? v
    : lightCfg.TryGetValue("*", out var d) && d.TryGetValue(key, out var w) ? w
    : Environment.GetEnvironmentVariable(key) ?? fallback;

// Interior promotions (Promotions.cs): <output dir>/promote.json, when present, gives FO4 containers, inventory items,
// activators and terminals a native base of their kind instead of the STAT / MSTT their model would get.
using var promotions = new Promotions(Path.Combine(outDir, "promote.json"));

// ---- cells ------------------------------------------------------------------------------------------------------------
P3Float Pos(JsonElement p) => new(p[0].GetSingle() / UnitsPerMetre, p[1].GetSingle() / UnitsPerMetre, p[2].GetSingle() / UnitsPerMetre);
P3Float Rot(JsonElement o) => new(o[0].GetSingle(), o[1].GetSingle(), o[2].GetSingle());

// every placed reference by its source FO4 FormKey, for the teleport links after all cells are placed
var placedBySource = new Dictionary<string, (PlacedObject obj, Cell cell)>();
var cellDocs = args.Skip(2).Select(p => JsonDocument.Parse(File.ReadAllText(p))).ToList();   // kept open until the links are written
foreach (var cdoc in cellDocs)
{
    var root = cdoc.RootElement;
    var src4 = root.GetProperty("cell").GetString()!;
    var cellName = "FO4Port_" + src4;
    var cell = new Cell(Id("CELL:" + cellName), release) { EditorID = cellName, Flags = Cell.Flag.IsInteriorCell };
    var ltHex = Setting(src4, "LIGHTING_TEMPLATE", "06BCF8");   // KreetBase01LGTtemplate (underground); ShipInteriorLT 006658 is brighter
    cell.LightingTemplate.SetTo(new FormKey(sfEsm, Convert.ToUInt32(ltHex, 16)));
    // exposure + reflections like the vanilla underground interior DR017UndergroundInterior (25CAA7): without these the cell
    // reflects a bright default sky and auto-exposure washes everything out
    cell.ImageSpace.SetTo(new FormKey(sfEsm, Convert.ToUInt32(Setting(src4, "IMAGE_SPACE", "122393"), 16)));
    // ENV_MAP is a per-cell setting. Default: the vanilla hall cubemap (ssPirateShip01Interior's). The library under
    // blackcube.dds was black away from placed lights; with this cube the owner judged it "fine" (18 Oct, FO4Port.esm
    // 5204188f; research log 2026-10-18). Set "blackcube.dds" per cell to get the old look back.
    cell.EnvironmentMap = Setting(src4, "ENV_MAP", "Data\\Textures\\Cubemaps\\Cell_HiTechHallCube.dds");
    var cocMarker = new FormKey(sfEsm, 0x000032);                                        // COCMarkerHeading
    var omni = new FormKey(sfEsm, Convert.ToUInt32(Setting(src4, "OMNI_LIGHT", "03D38C"), 16)); // LGT_ShipInterior_Omni_NS_Neutral_2k
    var merge = float.Parse(Setting(src4, "LIGHT_MERGE_M", "3"), System.Globalization.CultureInfo.InvariantCulture);
    var lit = new List<P3Float>();
    int lights = 0, placed = 0, skipped = 0, disabled = 0, openDoors = 0, lockedDoors = 0, placedPosed = 0;
    foreach (var r in root.GetProperty("refs").EnumerateArray())
    {
        var src = r.GetProperty("formkey").GetString()!;
        var model = r.GetProperty("model").GetString() ?? "";
        PlacedObject? obj = null;
        if (r.GetProperty("base_editor_id").GetString() == "COCMarkerHeading")            // arrival point for `coc`
        {
            obj = new PlacedObject(Id($"REFR:{cellName}:{src}"), release)
                { Base = new FormLinkNullable<IPlaceableObjectGetter>(cocMarker), Position = Pos(r.GetProperty("pos")), Rotation = Rot(r.GetProperty("rot")) };
        }
        else if (r.GetProperty("type").GetString() == "Light")
        {
            if (Environment.GetEnvironmentVariable("FO4PORT_NO_LIGHTS") == "1") continue;
            var pos = Pos(r.GetProperty("pos"));
            if (lit.Any(q => Math.Abs(q.X - pos.X) < merge && Math.Abs(q.Y - pos.Y) < merge && Math.Abs(q.Z - pos.Z) < merge)) continue;
            lit.Add(pos);
            obj = new PlacedObject(Id($"REFR:{cellName}:{src}"), release) { Base = new FormLinkNullable<IPlaceableObjectGetter>(omni), Position = pos };
            lights++;
        }
        else
        {
            if (!PosedBases.TryResolve(byRef, bySource, src, model, out var bas)) { skipped++; continue; }
            if (byRef.ContainsKey(src)) placedPosed++;
            if (promotions.Has(src))
            {
                if (byRef.ContainsKey(src)) promotions.Kept(src, "own posed model");
                else if (!modelOf.TryGetValue(bas.key, out var baseModel)) promotions.Kept(src, "door base");
                else bas = (promotions.Base(src, baseModel, mod, Id, release), bas.offset);
            }
            var scale = r.GetProperty("scale").GetSingle();
            var rot = Rot(r.GetProperty("rot"));
            var pos = Pos(r.GetProperty("pos"));
            var off = RotateOffset(bas.offset, rot, scale);
            obj = new PlacedObject(Id($"REFR:{cellName}:{src}"), release)
            {
                Base = new FormLinkNullable<IPlaceableObjectGetter>(bas.key),
                Position = new P3Float(pos.X + off.X, pos.Y + off.Y, pos.Z + off.Z),
                Rotation = rot,
            };
            if (Math.Abs(scale - 1f) > 1e-4) obj.Scale = scale;
            placed++;
            if (openingDoors.Contains(bas.key))
            {
                // FO4's "open by default" (Fo4Export open_by_default): a doorway FO4 shows open starts open (review of PR
                // #242: 21 vault / elevator refs, 47 hinged ones). FO4 lock data is NOT written: its keys and terminals
                // (Vault 111: lock levels 253 / 254) are not in this build, so a lock would shut a door nothing here can
                // open. Counted and printed instead.
                if (r.TryGetProperty("open_by_default", out var obd) && obd.ValueKind == JsonValueKind.True) { obj.OpenByDefault = true; openDoors++; }
                if (r.TryGetProperty("lock_data", out var lk) && lk.ValueKind == JsonValueKind.Object) lockedDoors++;
            }
        }
        if (r.TryGetProperty("disabled", out var dis) && dis.GetInt32() != 0)
        {
            obj.MajorRecordFlagsRaw |= 0x800;                                              // Initially Disabled, as in FO4
            disabled++;
        }
        cell.Temporary.Add(obj);
        placedBySource[src] = (obj, cell);
    }
    var cid = cell.FormKey.ID;
    var block = new CellBlock { BlockNumber = (int)(cid % 10), GroupType = GroupTypeEnum.InteriorCellBlock };
    var sub = new CellSubBlock { BlockNumber = (int)((cid / 10) % 10), GroupType = GroupTypeEnum.InteriorCellSubBlock };
    sub.Cells.Add(cell);
    block.SubBlocks.Add(sub);
    mod.Cells.Records.Add(block);
    Console.WriteLine($"cell {cellName} {cell.FormKey}: placed {placed} references ({placedPosed} with their own posed model) + {lights} lights ({disabled} initially disabled), skipped {skipped}");
    if (openDoors + lockedDoors > 0)
        Console.WriteLine($"  doors: {openDoors} open by default (as in FO4), {lockedDoors} locked in FO4 (lock not written)");
}

if (promotions.Listed > 0)
{
    var handled = promotions.Counts.Values.Sum();
    Console.WriteLine($"promotions: {string.Join(", ", promotions.Counts.Select(kv => $"{kv.Value} {kv.Key}"))}; " +
                      $"{promotions.Listed - handled} listed but not placed");
}

// ---- door names (DoorNames.cs): the FO4 DOOR name in the prompt; before the chains and links, which read the bases ------
var named = DoorNames.Apply(mod, placedBySource, cellDocs.Select(d => d.RootElement), Id, openingDoors, ownRigDoors);
Console.WriteLine($"door names: {named.Copies} named copies of door bases " +
                  $"({named.Moved} references moved), {named.Unnamed} door references without an FO4 name, {named.Refused.Count} refused");
foreach (var refusal in named.Refused) Console.WriteLine($"  refused {refusal}");

// ---- activation chains (ActivationChains.cs): FO4 activate parents as Starfield linked-ref activation ------------------
var chains = ActivationChains.Apply(placedBySource, cellDocs.Select(d => d.RootElement),
                                    new HashSet<FormKey>(promotions.UsableBases.Concat(openingDoors)));
if (chains.ChildrenWithParents > 0)
{
    Console.WriteLine($"activation chains: {chains.Wired} wired; unwired: {chains.ParentNotPlaced} parent not placed, " +
                      $"{chains.ParentNotUsable} parent not usable, {chains.ParentDrivesSeveral} parent drives several, " +
                      $"{chains.ParentHasScript} parent already scripted, {chains.ChildNotPlaced} child not placed; " +
                      $"{chains.DelaysDropped} delays and {chains.ParentActivateOnly} parent-activate-only flags not carried");
    File.WriteAllText(Path.Combine(outDir, "activation.json"), JsonSerializer.Serialize(chains, new JsonSerializerOptions { WriteIndented = true }));
}

// ---- load-door teleports between the cells of this build ---------------------------------------------------------------
var teleports = TeleportLinks.Apply(mod, placedBySource, cellDocs.Select(d => d.RootElement), ownRigDoors, xtelLoadBases);
foreach (var d in cellDocs) d.Dispose();
Console.WriteLine($"teleports: {teleports.Linked} references linked ({teleports.Pairs} mutual pairs, {teleports.OneWay} one-way), " +
                  $"{teleports.DestinationNotInBuild} destinations not in this build, {teleports.SourceNotPlaced} sources not placed, {teleports.Issues.Count} issues" +
                  (teleports.LoadGraph > 0 ? $", {teleports.LoadGraph} animated load doors on their load graph" : ""));
foreach (var issue in teleports.Issues) Console.WriteLine($"  issue {issue.Source} -> {issue.Target}: {issue.Reason}");
File.WriteAllText(Path.Combine(outDir, "teleports.json"), JsonSerializer.Serialize(teleports, new JsonSerializerOptions { WriteIndented = true }));

// ---- door test cell (FO4PORT_DOORTEST=<door editor id>) ------------------------------------------------------------------
// One 8x8 m vanilla platform, the converted door at the origin (facing +X like an FO4 door with no rotation), the vanilla
// Akila door 0AA24A 3 m to the side for comparison, and a COC marker 1.5 m in front of the converted door, facing it.
if (Environment.GetEnvironmentVariable("FO4PORT_DOORTEST") is string testDoor)
{
    var cell = new Cell(Id("CELL:FO4Port_DoorTest"), release) { EditorID = "FO4Port_DoorTest", Flags = Cell.Flag.IsInteriorCell };
    cell.LightingTemplate.SetTo(new FormKey(sfEsm, 0x006658));
    cell.ImageSpace.SetTo(new FormKey(sfEsm, 0x122393));
    cell.EnvironmentMap = "Data\\Textures\\cubemaps\\blackcube.dds";
    var entry = items.First(i => i.editorId == testDoor);
    var (doorKey, doorOff) = bySource[entry.source.Replace('/', '\\')];
    PlacedObject P(string key, FormKey b, P3Float pos, P3Float rot) =>
        new(Id("REFR:FO4Port_DoorTest:" + key), release) { Base = new FormLinkNullable<IPlaceableObjectGetter>(b), Position = pos, Rotation = rot };
    var zero = new P3Float(0, 0, 0);
    cell.Temporary.Add(P("floor", new FormKey(sfEsm, 0x050776), new P3Float(-2, 0, 0), zero));  // NA_Transit_PlatformA_Str08x08_01: x -2..6, top z 0
    cell.Temporary.Add(P("door", doorKey, doorOff, zero));
    cell.Temporary.Add(P("vanilla", new FormKey(sfEsm, 0x0AA24A), new P3Float(0, 3, 0), zero));
    cell.Temporary.Add(P("coc", new FormKey(sfEsm, 0x000032), new P3Float(-1.5f, 0, 0.1f), new P3Float(0, 0, (float)(Math.PI / 2))));
    cell.Temporary.Add(P("light", new FormKey(sfEsm, 0x03D38C), new P3Float(-1, 1.5f, 3), zero));
    var cid = cell.FormKey.ID;
    var block = new CellBlock { BlockNumber = (int)(cid % 10), GroupType = GroupTypeEnum.InteriorCellBlock };
    var sub = new CellSubBlock { BlockNumber = (int)((cid / 10) % 10), GroupType = GroupTypeEnum.InteriorCellSubBlock };
    sub.Cells.Add(cell);
    block.SubBlocks.Add(sub);
    mod.Cells.Records.Add(block);
    Console.WriteLine($"door test cell {cell.FormKey} with {testDoor}");
}

mod.ModHeader.Stats.NextFormID = next;
var path = Path.Combine(outDir, modKey.FileName);
var sfData = Environment.GetEnvironmentVariable("STARFIELD_DATA") ?? throw new InvalidOperationException("set STARFIELD_DATA to the Starfield Data folder");
// Reserve identities before any plugin write. Failed output retains these IDs
// for retry; a failed map publication must not replace the previous plugin.
StableFormIds.Save(mapPath, ids);
mod.BeginWrite.ToPath(path).WithLoadOrderFromHeaderMasters().WithDataFolder(sfData)
    .WithKnownMasters(new KeyedMasterStyle(sfEsm, MasterStyle.Full))
    .Write();
Console.WriteLine($"wrote {path} ({new FileInfo(path).Length:N0} bytes); {ids.Count} stable FormIDs in {mapPath}");
