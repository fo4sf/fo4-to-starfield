// Synthetic master with the template identities the real writer requests (the three overlay templates, the
// terminal whose furniture block every promoted TERM copies, with its own synthetic furniture and keyword, and the
// light the exterior lights copy: the light only when lights are written).
// No game files are read; no mesh, texture, terrain or native record data is copied.
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;

var key = ModKey.FromNameAndExtension("Starfield.esm");
var release = StarfieldRelease.Starfield;
var mod = new StarfieldMod(key, release);
mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
var world = new Worldspace(new FormKey(key, 0x02DF8C), release) { EditorID = "SyntheticTemplateWorld" };
world.Components.Add(new WorldSpaceOverlayComponent());
mod.Worldspaces.Add(world);
mod.SurfaceBlocks.Add(new SurfaceBlock(new FormKey(key, 0x102382), release) { EditorID = "SyntheticTemplateBlock" });
mod.Locations.Add(new Location(new FormKey(key, 0x3807BE), release) { EditorID = "SyntheticTemplateLocation" });
// The template terminal (0155A2): synthetic values in every furniture field the writer copies, and a script, bounds,
// a model and a name it must not copy.
var furniture = new Furniture(new FormKey(key, 0x3807BF), release) { EditorID = "SyntheticTemplateFurniture" };
mod.Furniture.Add(furniture);
var keyword = new Keyword(new FormKey(key, 0x3807C0), release) { EditorID = "SyntheticTerminalKeyword" };
mod.Keywords.Add(keyword);
var terminal = new Terminal(new FormKey(key, 0x0155A2), release)
{
    EditorID = "SyntheticTemplateTerminal", Name = "Synthetic template", Model = new Model { File = "synthetic_template_terminal.nif" },
    ObjectBounds = new ObjectBounds { First = new Noggog.P3Float(-1, -1, 0), Second = new Noggog.P3Float(1, 1, 2) },
    VirtualMachineAdapter = new VirtualMachineAdapterIndexed { Scripts = { new ScriptEntry { Name = "SyntheticTerminalScript" } } },
    Keywords = new Noggog.ExtendedList<IFormLinkGetter<IKeywordGetter>> { new FormLink<IKeywordGetter>(keyword.FormKey) },
    PNAM = new byte[] { 1, 2, 3, 0 }, FNAM = new byte[] { 2, 0 }, JNAM = new byte[] { 0x5A, 0 }, GNAM = new byte[] { 0x2D, 0 },
    MarkerFlags = FurnitureMarkerFlags.HasModel | FurnitureMarkerFlags.InteractionPoint0, WorkbenchData = new byte[] { 7 },
    MarkerModel = "markers/synthetic_terminal_marker.nif",
    MarkerParameters = new Noggog.ExtendedList<FurnitureMarkerParameters> { new() { Offset = new Noggog.P3Float(0, -0.25f, 0), RotationZ = 0.5f } },
};
terminal.FurnitureTemplate.SetTo(furniture.FormKey);
terminal.Components.Add(new AnimationGraphComponent { ANAM = "synthetic.agx", BNAM = "synthetic/skeleton.rig", CNAM = "synthetic/animations" });
mod.Terminals.Add(terminal);
// the light template's identity (12A74B) with a CK object-window filter, which the writer must drop
var light = new Light(new FormKey(key, 0x12A74B), release) { EditorID = "SyntheticTemplateLight", Radius = 1, PbrLuminousPowerLm = 1 };
light.Components.Add(new ObjectWindowFilterComponent { FLTR = "Synthetic/Filter/" });
mod.Lights.Add(light);
// The stations (docs/terrain/stations.md): the keywords, actor value and pre-placed workshop activator the workshop
// writer reads (00024DC7's OutpostCategory* keywords only; its other keywords, name, model and radius are decoys), and
// the four vanilla benches with their bench types, plus a furniture without one and a static, which it must refuse.
Keyword Kw(uint id, string edid) { var k = new Keyword(new FormKey(key, id), release) { EditorID = edid }; mod.Keywords.Add(k); return k; }
var mustPersist = Kw(0x04AF68, "MustPersist");
var workshopKw = Kw(0x054BA7, "WorkshopKeyword");
var catCrafting = Kw(0x2CFDE6, "OutpostCategoryCrafting");
var catFurniture = Kw(0x2BE3B5, "OutpostCategoryFurniture");
var blockFlycam = Kw(0x257536, "OutpostBlockFlycam");
var catDisplays = Kw(0x397027, "OutpostCategoryDisplays");
// the four vanilla benches' recipe keywords (what make_core64c.station_master_check binds each kind to)
var benchKws = new Dictionary<uint, Keyword>
{
    [0x2B6A63] = Kw(0x2CE1C0, "SyntheticWorkbenchWeaponKeyword"), [0x2B6A62] = Kw(0x0657FF, "SyntheticWorkbenchArmorKeyword"),
    [0x2B6A61] = Kw(0x102158, "SyntheticWorkbenchChemlabRecipeKeyword"), [0x2B6A65] = Kw(0x102152, "SyntheticWorkbenchCookingKeyword"),
};
var radiusAv = new ActorValueInformation(new FormKey(key, 0x063FC5), release) { EditorID = "OutpostBuildAreaRadius" };
mod.ActorValueInformation.Add(radiusAv);
var otherAv = new ActorValueInformation(new FormKey(key, 0x3807C4), release) { EditorID = "SyntheticOtherValue" };
mod.ActorValueInformation.Add(otherAv);
var house = new Mutagen.Bethesda.Starfield.Activator(new FormKey(key, 0x024DC7), release)
{
    EditorID = "SyntheticPlayerHouseActivator", Name = "Decorate", Model = new Model { File = "synthetic_lever.nif" },
    Keywords = new Noggog.ExtendedList<IFormLinkGetter<IKeywordGetter>>
    {
        new FormLink<IKeywordGetter>(mustPersist.FormKey), new FormLink<IKeywordGetter>(workshopKw.FormKey),
        new FormLink<IKeywordGetter>(catCrafting.FormKey), new FormLink<IKeywordGetter>(catFurniture.FormKey),
        new FormLink<IKeywordGetter>(blockFlycam.FormKey), new FormLink<IKeywordGetter>(catDisplays.FormKey),
    },
    Properties = new Noggog.ExtendedList<ObjectProperty>
    {
        new ObjectProperty { ActorValue = new FormLink<IActorValueInformationGetter>(radiusAv.FormKey), Value = 250 },
        new ObjectProperty { ActorValue = new FormLink<IActorValueInformationGetter>(otherAv.FormKey), Value = 1 },
    },
    VirtualMachineAdapter = new VirtualMachineAdapter { Scripts = { new ScriptEntry { Name = "SyntheticDecoyScript" } } },
};
mod.Activators.Add(house);
Furniture Bench(uint id, string edid, Furniture.BenchTypes bench)
{
    var f = new Furniture(new FormKey(key, id), release) { EditorID = edid, BenchType = bench, Name = edid, Model = new Model { File = edid + ".nif" } };
    if (benchKws.TryGetValue(id, out var kw))
        f.Keywords = new Noggog.ExtendedList<IFormLinkGetter<IKeywordGetter>> { new FormLink<IKeywordGetter>(kw.FormKey) };
    mod.Furniture.Add(f);
    return f;
}
Bench(0x2B6A63, "SyntheticWorkbenchWeapon", Furniture.BenchTypes.Weapons);
Bench(0x2B6A62, "SyntheticWorkbenchArmor", Furniture.BenchTypes.Armor);
Bench(0x2B6A61, "SyntheticWorkbenchChem", Furniture.BenchTypes.Alchemy);
Bench(0x2B6A65, "SyntheticWorkbenchFood", Furniture.BenchTypes.Alchemy);
Bench(0x3807C5, "SyntheticDecorFurniture", Furniture.BenchTypes.None);
mod.Statics.Add(new Static(new FormKey(key, 0x3807C6), release) { EditorID = "SyntheticStatic", Model = new Model { File = "synthetic_static.nif" } });
mod.ModHeader.Stats.NextFormID = 0x3807C7;
var path = Path.GetFullPath(args[0]);
Directory.CreateDirectory(Path.GetDirectoryName(path)!);
mod.BeginWrite.ToPath(path).WithLoadOrderFromHeaderMasters().WithDataFolder(Path.GetDirectoryName(path)!)
    .WithKnownMasters(new KeyedMasterStyle(key, MasterStyle.Full)).Write();
Console.WriteLine(path);
