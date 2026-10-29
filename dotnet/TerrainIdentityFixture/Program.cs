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
// LC172World's two border fields (docs/terrain/border.md): SmallWorld and HNAM 0, which "world_data" may change
var world = new Worldspace(new FormKey(key, 0x02DF8C), release)
{
    EditorID = "SyntheticTemplateWorld", Flags = Worldspace.Flag.SmallWorld, HNAM = new Noggog.MemorySlice<byte>(new byte[] { 0 }),
};
var overlayComponent = new WorldSpaceOverlayComponent();
world.Components.Add(overlayComponent);
mod.Worldspaces.Add(world);
// Optional (args[1..] contains "overlay-ids"): LC172World's overlay system and planet ids (Mars: system 0, planet 4)
// as 4-byte SNAM / PNAM, which dotnet/PlanetProbe requires of its template; the default fixture leaves them unset.
if (args.Skip(1).Contains("overlay-ids"))
{
    overlayComponent.SNAM = BitConverter.GetBytes(0);
    overlayComponent.PNAM = BitConverter.GetBytes(4);
}
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
// FloraMaizeCrop01 + its PFIG seed, a second legal MISC ingredient, and FloraTypeOrganic so the writer can
// Duplicate a harvest FLOR. A STAT ingredient is refused because it is not a MISC/LVLI of this master
// (00000010 is below Mutagen's lower FormKey range, so it is not placed here; SyntheticStatic 3807C6 is).
var organic = Kw(0x222E03, "FloraTypeOrganic");
var seed = new MiscItem(new FormKey(key, 0x260DF2), release) { EditorID = "OrgCommonNutrient_Seed" };
mod.MiscItems.Add(seed);
mod.MiscItems.Add(new MiscItem(new FormKey(key, 0x055AF), release) { EditorID = "OrgCommonFiber" });
var maize = new Flora(new FormKey(key, 0x0EC886), release)
{
    EditorID = "FloraMaizeCrop01", Name = "Maize", Model = new Model { File = "flora01.nif" },
    Keywords = new Noggog.ExtendedList<IFormLinkGetter<IKeywordGetter>> { new FormLink<IKeywordGetter>(organic.FormKey) },
};
maize.Ingredient.SetTo(seed.FormKey);
mod.Florae.Add(maize);
mod.ModHeader.Stats.NextFormID = 0x3807C7;
// Optional map-marker template (args[1] == "map-marker"): persistent REFR 003E5E12 on the template world so the
// writer can Duplicate it. STAT 00000010 is a FormLink only (Mutagen refuses writing that low FormKey). Default
// fixture omits this so identity / lights / doors tests keep their FormIDs (writer skips when 003E5E12 is missing).
if (args.Skip(1).Contains("map-marker"))
{
    var top = new Cell(new FormKey(key, 0x3807C7), release) { Flags = Cell.Flag.HasWater };
    world.TopCell = top;
    var marker = new PlacedObject(new FormKey(key, 0x3E5E12), release)
    {
        EditorID = "SyntheticLc172MapMarker",
        Base = new FormLinkNullable<IPlaceableObjectGetter>(new FormKey(key, 0x10)),
        Position = new Noggog.P3Float(37.4f, 57.2f, 7.6f),
        MapMarker = new PlacedObjectMapMarker { Name = "LC172" },
    };
    marker.MajorRecordFlagsRaw |= 0xC00;
    top.Persistent.Add(marker);
    mod.ModHeader.Stats.NextFormID = 0x3807C8;
}
// Optional Story Manager template ("story-manager" or "story-manager-open"; dotnet/CombinedProbe's P10 branch): a
// Script Event SMEN with branches A and B (B after A) and a quest node under A, plus a root branch outside the event
// node. "story-manager" gives each a GetEventData filter on a keyword of this master: A and its quest node GetIsID /
// Keyword1, B GetIsID / Keyword2, the root branch IsInList / Keyword1 (not under the event node, so never counted).
// "story-manager-open" writes the same nodes with no condition, which CombinedProbe must refuse.
var sm = args.Skip(1).FirstOrDefault(x => x is "story-manager" or "story-manager-open");
if (sm is not null)
{
    var eventKw = Kw(0x3807E0, "SyntheticStoryEventKeyword");
    var smen = new StoryManagerEventNode(new FormKey(key, 0x3807E1), release)
    {
        EditorID = "SyntheticScriptEventNode", Type = StoryManagerEventNode.Types.ScriptEvent,
    };
    mod.StoryManagerEventNodes.Add(smen);
    void Filter(AStoryManagerNode n, GetEventDataConditionData.EventFunction fn, GetEventDataConditionData.EventMember member)
    {
        if (sm != "story-manager") return;
        var data = new GetEventDataConditionData { Function = fn, Member = member };
        data.Record.SetTo(eventKw.FormKey);
        n.Conditions.Add(new ConditionFloat { CompareOperator = CompareOperator.EqualTo, ComparisonValue = 1f, Data = data });
    }
    var a = new StoryManagerBranchNode(new FormKey(key, 0x3807E2), release) { EditorID = "SyntheticScriptEventBranchA" };
    a.Parent.SetTo(smen.FormKey);
    Filter(a, GetEventDataConditionData.EventFunction.GetIsID, GetEventDataConditionData.EventMember.Keyword1);
    mod.StoryManagerBranchNodes.Add(a);
    var q = new StoryManagerQuestNode(new FormKey(key, 0x3807E3), release) { EditorID = "SyntheticScriptEventQuestNode" };
    q.Parent.SetTo(a.FormKey);
    Filter(q, GetEventDataConditionData.EventFunction.GetIsID, GetEventDataConditionData.EventMember.Keyword1);
    mod.StoryManagerQuestNodes.Add(q);
    var b = new StoryManagerBranchNode(new FormKey(key, 0x3807E4), release) { EditorID = "SyntheticScriptEventBranchB" };
    b.Parent.SetTo(smen.FormKey);
    b.PreviousSibling.SetTo(a.FormKey);
    Filter(b, GetEventDataConditionData.EventFunction.GetIsID, GetEventDataConditionData.EventMember.Keyword2);
    mod.StoryManagerBranchNodes.Add(b);
    var root = new StoryManagerBranchNode(new FormKey(key, 0x3807E5), release) { EditorID = "SyntheticRootBranch" };
    Filter(root, GetEventDataConditionData.EventFunction.IsInList, GetEventDataConditionData.EventMember.Keyword1);
    mod.StoryManagerBranchNodes.Add(root);
    mod.ModHeader.Stats.NextFormID = 0x3807E6;
}
var path = Path.GetFullPath(args[0]);
Directory.CreateDirectory(Path.GetDirectoryName(path)!);
mod.BeginWrite.ToPath(path).WithLoadOrderFromHeaderMasters().WithDataFolder(Path.GetDirectoryName(path)!)
    .WithKnownMasters(new KeyedMasterStyle(key, MasterStyle.Full)).Write();
Console.WriteLine(path);
