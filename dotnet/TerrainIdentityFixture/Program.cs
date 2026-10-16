// Synthetic master with the template identities the real writer requests (the three overlay templates, the
// terminal whose furniture block every promoted TERM copies, with its own synthetic furniture and keyword, and the
// light the exterior lights copy: the light only when lights are written).
// No game files are read; no mesh, texture, terrain or native record data is copied.
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;

if (args[0] == "--stable-fixture")
{
    string root = Path.GetFullPath(args[1]), mode = args[2];
    string[] names = { "Synthetic.esm", "formids.json" };
    using var publication = new OutputPublication(root, names, step =>
    {
        if (mode == "fail" && step == "published:Synthetic.esm")
            throw new IOException("synthetic publication failure after reservations persisted");
    });
    if (mode == "hold")
    {
        File.WriteAllText(Path.Combine(root, "fixture-lease-ready"), "ready");
        Console.ReadLine();
        return;
    }
    var stable = TerrainStableIds.Open(root, "Synthetic.esm", true, false, names)!;
    if (mode == "invalid-keys")
    {
        string[][] invalid = { Array.Empty<string>(), new[] { "unknown", "value" },
            new[] { "reference", "not-a-source" }, new[] { "cell", "world", "01", "0" },
            new[] { "item", "value", "extra" } };
        foreach (var parts in invalid)
        {
            bool refused = false;
            try { stable.Reserve(parts); }
            catch (InvalidDataException) { refused = true; }
            if (!refused) throw new InvalidOperationException("invalid semantic key was reserved");
        }
    }
    stable.Reserve("reference", TerrainStableIds.Source("000001:Synthetic.esm"));
    if (mode == "exhaust") stable.Anchor("last", 0xFFFFFF);
    if (mode != "seed") stable.Reserve("reference", TerrainStableIds.Source("000002:Synthetic.esm"));
    foreach (string name in names) File.WriteAllText(publication.StagePath(name), mode + ":" + name);
    if (mode == "mutate") File.WriteAllText(Path.Combine(root, TerrainStableIds.FileName), "external owner bytes");
    stable.PersistBeforePublication(publication.StagePath);
    if (mode == "crash") Environment.Exit(17);
    publication.Commit();
    return;
}

if (args[0] == "--publish-fixture")
{
    string root = Path.GetFullPath(args[1]), mode = args[2];
    string[] names = { "Synthetic.esm", "formids.json", "Registration.esm" };
    using var publication = new OutputPublication(root, names, step =>
    {
        if (step != "published:Synthetic.esm") return;
        if (mode == "fail") throw new IOException("synthetic failure after first publication");
        if (mode == "owner") File.WriteAllText(Path.Combine(root, "formids.json"), "owner-created file");
        if (mode == "crash") Environment.Exit(17);
    });
    foreach (string name in names) File.WriteAllText(publication.StagePath(name), "new:" + name);
    publication.Commit();
    return;
}

var key = ModKey.FromNameAndExtension("Starfield.esm");
var release = StarfieldRelease.Starfield;
var mod = new StarfieldMod(key, release);
mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
var world = new Worldspace(new FormKey(key, 0x02DF8C), release) { EditorID = "SyntheticTemplateWorld" };
world.Components.Add(new WorldSpaceOverlayComponent());
mod.Worldspaces.Add(world);
mod.SurfaceBlocks.Add(new SurfaceBlock(new FormKey(key, 0x102382), release) { EditorID = "SyntheticTemplateBlock" });
mod.Locations.Add(new Location(new FormKey(key, 0x3807BE), release) { EditorID = "SyntheticTemplateLocation" });
bool withMars = args[0] == "--master-with-mars";
if (withMars)
    mod.Planets.Add(new Planet(new FormKey(key, 0x900), release) { EditorID = "MarsPlanetData", MasterWorldspaces = new() });
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
mod.ModHeader.Stats.NextFormID = 0x3807C1;
var path = Path.GetFullPath(withMars ? args[1] : args[0]);
Directory.CreateDirectory(Path.GetDirectoryName(path)!);
mod.BeginWrite.ToPath(path).WithLoadOrderFromHeaderMasters().WithDataFolder(Path.GetDirectoryName(path)!)
    .WithKnownMasters(new KeyedMasterStyle(key, MasterStyle.Full)).Write();
Console.WriteLine(path);
