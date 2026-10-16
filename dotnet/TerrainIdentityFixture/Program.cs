// Synthetic master with the four template identities the real writer requests (the light only when lights are written).
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
// the light template's identity (12A74B) with a CK object-window filter, which the writer must drop
var light = new Light(new FormKey(key, 0x12A74B), release) { EditorID = "SyntheticTemplateLight", Radius = 1, PbrLuminousPowerLm = 1 };
light.Components.Add(new ObjectWindowFilterComponent { FLTR = "Synthetic/Filter/" });
mod.Lights.Add(light);
mod.ModHeader.Stats.NextFormID = 0x3807BF;
var path = Path.GetFullPath(args[0]);
Directory.CreateDirectory(Path.GetDirectoryName(path)!);
mod.BeginWrite.ToPath(path).WithLoadOrderFromHeaderMasters().WithDataFolder(Path.GetDirectoryName(path)!)
    .WithKnownMasters(new KeyedMasterStyle(key, MasterStyle.Full)).Write();
Console.WriteLine(path);
