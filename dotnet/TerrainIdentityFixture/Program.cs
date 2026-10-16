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
mod.ModHeader.Stats.NextFormID = 0x3807C1;
var path = Path.GetFullPath(args[0]);
Directory.CreateDirectory(Path.GetDirectoryName(path)!);
mod.BeginWrite.ToPath(path).WithLoadOrderFromHeaderMasters().WithDataFolder(Path.GetDirectoryName(path)!)
    .WithKnownMasters(new KeyedMasterStyle(key, MasterStyle.Full)).Write();
Console.WriteLine(path);
