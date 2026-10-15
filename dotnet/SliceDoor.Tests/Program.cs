// Synthetic binary Build.Run/Check.Run integration. Never opens a game file.
using System.Text.Json;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;

static void Assert(bool ok, string message) { if (!ok) throw new Exception(message); }
static void Refuses(Action action) {
    try { action(); } catch (InvalidDataException) { return; }
    throw new Exception("expected rejection");
}
var dir = Path.Combine(Path.GetTempPath(), "slice-world-data-" + Guid.NewGuid());
Directory.CreateDirectory(dir);
try
{
    var sf = new StarfieldMod(ModKey.FromFileName("Starfield.esm"), StarfieldRelease.Starfield);
    sf.Doors.Add(new Door(new FormKey(sf.ModKey, 0x800), StarfieldRelease.Starfield) { EditorID = "SyntheticDoor", Flags = Door.Flag.Automatic });
    var core = new StarfieldMod(ModKey.FromFileName("SyntheticCore.esm"), StarfieldRelease.Starfield);
    var world = new Worldspace(new FormKey(core.ModKey, 0x800), StarfieldRelease.Starfield) {
        EditorID = "SyntheticWorld", ObjectBoundsMin = new P2Float(-100f / 4096, -200f / 4096),
        ObjectBoundsMax = new P2Float(100f / 4096, 100f / 4096),
        TopCell = new Cell(new FormKey(core.ModKey, 0x801), StarfieldRelease.Starfield),
    };
    core.Worldspaces.Add(world);
    var port = new StarfieldMod(ModKey.FromFileName("SyntheticPort.esm"), StarfieldRelease.Starfield);
    var cb = new CellBlock { GroupType = GroupTypeEnum.InteriorCellBlock };
    var cs = new CellSubBlock { GroupType = GroupTypeEnum.InteriorCellSubBlock };
    cs.Cells.Add(new Cell(new FormKey(port.ModKey, 0x800), StarfieldRelease.Starfield) { EditorID = "SyntheticRoom" });
    cb.SubBlocks.Add(cs); port.Cells.Records.Add(cb);
    foreach (var mod in new[] { sf, core, port }) {
        mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        mod.WriteToBinary(Path.Combine(dir, mod.ModKey.FileName));
    }
    object Side(string id) => new { edid=id, pos=new[]{1f,2f,3f}, rot=new[]{0f,0f,0f}, scale=1f,
        xtel=new {pos=new[]{4f,5f,6f}, rot=new[]{0f,0f,0f}, flags=0}};
    var parameters = new Dictionary<string,object> {
        ["plugin"]="SyntheticSlice.esm", ["world"]=new{editor_id="SyntheticWorld"},
        ["interior"]=new{editor_id="SyntheticRoom"}, ["door_base"]=new{plugin="Starfield.esm",id="000800",editor_id="SyntheticDoor"},
        ["outside"]=Side("SyntheticExt"), ["inside"]=Side("SyntheticInt"),
    };
    var paramsPath=Path.Combine(dir,"params.json");
    var sfPath=Path.Combine(dir,"Starfield.esm"); var corePath=Path.Combine(dir,"SyntheticCore.esm");
    var portPath=Path.Combine(dir,"SyntheticPort.esm"); var slicePath=Path.Combine(dir,"SyntheticSlice.esm");
    void SaveParams() => File.WriteAllText(paramsPath,JsonSerializer.Serialize(parameters));
    int BuildIt() => Build.Run(new[]{"build",paramsPath,sfPath,corePath,portPath,dir});
    int CheckIt() => Check.Run(new[]{"check",slicePath,sfPath,corePath,portPath,paramsPath,Path.Combine(dir,"check.json")});
    SaveParams(); Assert(BuildIt()==0 && CheckIt()==0,"default build/check");
    using (var m=Build.Open(slicePath,"Starfield.esm",core.ModKey.FileName,port.ModKey.FileName))
        Assert(m.Worldspaces.First().OffsetData==null && m.Worldspaces.First().CellSizeData==null,"default unchanged");
    parameters["world_cell_data"]=new{mode="empty"}; SaveParams();
    Assert(BuildIt()==0 && CheckIt()==0,"empty build/check");
    using (var m=Build.Open(slicePath,"Starfield.esm",core.ModKey.FileName,port.ModKey.FileName)) {
        var w=m.Worldspaces.First();
        Assert(WorldCellData.ByteLength(w)==48 && WorldCellData.MatchesEmpty(w),"rectangular array");
        Assert(m.EnumerateMajorRecords().Count()==5,"exact five records");
        Assert(w.TopCell!.Persistent.Single().FormKey.ID==Build.ExteriorId,"fixed exterior ID");
    }
    // Typed corruption controls and a binary read-back rejection.
    var copy=Build.WorldOnly(world); WorldCellData.SetEmpty(copy);
    copy.OffsetData=new byte[44]; Assert(!WorldCellData.MatchesEmpty(copy),"short OFST");
    WorldCellData.SetEmpty(copy); var stale=new byte[48]; stale[0]=1;
    copy.CellSizeData=stale; Assert(!WorldCellData.MatchesEmpty(copy),"stale CLSZ");
    copy.SubCells.Add(new WorldspaceBlock()); Refuses(()=>WorldCellData.SetEmpty(copy));
    copy.SubCells.Clear(); copy.ObjectBoundsMax=new P2Float(-200f/4096,100f/4096); Refuses(()=>WorldCellData.SetEmpty(copy));
    copy.ObjectBoundsMax=new P2Float(float.NaN,0); Refuses(()=>WorldCellData.SetEmpty(copy));
    copy.ObjectBoundsMax=new P2Float(150f/4096,100f/4096); Refuses(()=>WorldCellData.SetEmpty(copy));
    copy.ObjectBoundsMax=new P2Float(100000f,100000f); Refuses(()=>WorldCellData.SetEmpty(copy));
    var bytes=File.ReadAllBytes(slicePath); var tag=System.Text.Encoding.ASCII.GetBytes("OFST");
    int at=Enumerable.Range(0,bytes.Length-4).First(i=>bytes.AsSpan(i,4).SequenceEqual(tag));
    bytes[at+6]=1; File.WriteAllBytes(slicePath,bytes);
    Assert(CheckIt()==1,"serialized stale pointer rejected");
    parameters["probes"]=new[]{new{id="000802"}}; SaveParams(); Refuses(()=>BuildIt());
    parameters.Remove("probes"); parameters["world_cell_data"]=new{mode="copy-template"}; SaveParams(); Refuses(()=>BuildIt());
    Console.WriteLine("synthetic world-cell-data controls pass");
}
finally { Directory.Delete(dir,recursive:true); }
