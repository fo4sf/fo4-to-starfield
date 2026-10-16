// Synthetic master with the three template identities the real writer requests.
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
mod.ModHeader.Stats.NextFormID = 0x3807BF;
var path = Path.GetFullPath(withMars ? args[1] : args[0]);
Directory.CreateDirectory(Path.GetDirectoryName(path)!);
mod.BeginWrite.ToPath(path).WithLoadOrderFromHeaderMasters().WithDataFolder(Path.GetDirectoryName(path)!)
    .WithKnownMasters(new KeyedMasterStyle(key, MasterStyle.Full)).Write();
Console.WriteLine(path);
