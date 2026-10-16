using System.Text.Json;
using System.Diagnostics;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;


var root = Environment.GetEnvironmentVariable("FO4SF_RETURN_EVIDENCE") ?? Path.Combine(Path.GetTempPath(), "door-return-"+Guid.NewGuid().ToString("N"));
if (Directory.Exists(root)) throw new Exception("fresh evidence required");
Directory.CreateDirectory(root);
if (args.Contains("--publication-only")) { PublicationTests.Run(root); return; }
if (args.Contains("--pipeline-only")) { PipelineTests.Run(root); return; }
void Need(bool value, string message) { if (!value) throw new Exception(message); }
void CheckMasterHeader(string path)
{
    using var bytes = new BinaryReader(File.OpenRead(path));
    Need(System.Text.Encoding.ASCII.GetString(bytes.ReadBytes(4)) == "TES4", "missing TES4 header");
    bytes.ReadUInt32(); // record payload size
    Need((bytes.ReadUInt32() & 1u) != 0, "serialized TES4 master flag is missing");
}
var results = new List<object>();
foreach (var scenario in new[] { "valid", "missing-exterior", "temporary-exterior", "missing-flag", "deleted", "wrong-outbound", "static-base", "conflicting-return", "nan-arrival", "relative-arrival", "port-cycle", "wrong-owner", "deleted-cell", "deleted-world", "wrong-transition", "light-core", "core-cell-override", "core-door-override", "core-door-deleted", "core-door-temporary" }
    .Where(s => !args.Contains("--overrides-only") || s.StartsWith("core-"))
    .Where(s => !args.Contains("--positive-only") || s is "valid" or "core-cell-override" or "core-door-override")
    .Where(s => !args.Contains("--output-alias-only") || s == "valid"))
{
    var folder = Path.Combine(root,scenario); Directory.CreateDirectory(folder);
    var sfKey = ModKey.FromNameAndExtension("Starfield.esm");
    var portKey = ModKey.FromNameAndExtension("Port.esm"); var coreKey = ModKey.FromNameAndExtension("Core.esm");
    var sf = new StarfieldMod(sfKey,StarfieldRelease.Starfield);
    var port = new StarfieldMod(portKey,StarfieldRelease.Starfield); var core = new StarfieldMod(coreKey,StarfieldRelease.Starfield);
    var baseKey = new FormKey(sfKey,0x900); sf.Doors.Add(new Door(baseKey,StarfieldRelease.Starfield));
    var cell = new Cell(new FormKey(portKey,0x800),StarfieldRelease.Starfield) { Flags=Cell.Flag.IsInteriorCell, EditorID="SyntheticCave" };
    var inside = new PlacedObject(new FormKey(portKey,0x810),StarfieldRelease.Starfield) {
        Position=new P3Float(1,2,3),Rotation=new P3Float(0,0,.4f),Scale=.93f,MajorRecordFlagsRaw=0xC00,OpenByDefault=true };
    inside.Base.SetTo(baseKey); cell.Persistent.Add(inside);
    cell.Temporary.Add(new PlacedObject(new FormKey(portKey,0x811),StarfieldRelease.Starfield) { Base = new FormLinkNullable<IPlaceableObjectGetter>(baseKey) });
    var block=new CellBlock {BlockNumber=8,GroupType=GroupTypeEnum.InteriorCellBlock};
    var sub=new CellSubBlock {BlockNumber=4,GroupType=GroupTypeEnum.InteriorCellSubBlock};
    sub.Cells.Add(cell);block.SubBlocks.Add(sub);port.Cells.Records.Add(block);
    var world = new Worldspace(new FormKey(coreKey,0x803),StarfieldRelease.Starfield);
    world.TopCell = new Cell(new FormKey(coreKey,0x804),StarfieldRelease.Starfield);
    var outside = new PlacedObject(new FormKey(coreKey,0x820),StarfieldRelease.Starfield) {MajorRecordFlagsRaw=0x400,Position=new P3Float(-3,4,5)};
    outside.Base.SetTo(baseKey);
    outside.TeleportDestination = new TeleportDestination {Position=new P3Float(2,3,4)};
    outside.TeleportDestination.Door.SetTo(inside.FormKey);
    world.TopCell.Persistent.Add(outside); core.Worldspaces.Add(world);
    var plan = new ReturnPlan(inside.FormKey,outside.FormKey,new P3Float(-5,7,8),new P3Float(0,0,.2f),0);
    if (scenario == "missing-exterior") plan = plan with {Exterior=new FormKey(coreKey,0x821)};
    if (scenario == "temporary-exterior") {world.TopCell.Persistent.Remove(outside);world.TopCell.Temporary.Add(outside);}
    if (scenario == "missing-flag") outside.MajorRecordFlagsRaw=0;
    if (scenario == "deleted") outside.MajorRecordFlagsRaw |= 0x20;
    if (scenario == "wrong-outbound") outside.TeleportDestination.Door.SetTo(new FormKey(portKey,0x811));
    if (scenario == "static-base") core.Statics.Add(new Static(baseKey,StarfieldRelease.Starfield));
    if (scenario == "conflicting-return") {inside.TeleportDestination=new TeleportDestination();inside.TeleportDestination.Door.SetTo(new FormKey(coreKey,0x821));}
    if (scenario == "nan-arrival") plan=plan with {Position=new P3Float(float.NaN,0,0)};
    if (scenario == "relative-arrival") plan=plan with {Flags=4};
    if (scenario == "port-cycle") inside.Base.SetTo(new FormKey(coreKey,0x999));
    if (scenario == "wrong-owner") plan=plan with {Exterior=new FormKey(portKey,0x820)};
    if (scenario == "deleted-cell") cell.MajorRecordFlagsRaw |= 0x20;
    if (scenario == "deleted-world") world.MajorRecordFlagsRaw |= 0x20;
    if (scenario == "wrong-transition") outside.TeleportDestination.TransitionInterior.SetTo(new FormKey(portKey,0x801));
    if (scenario == "light-core") core.IsSmallMaster = true;
    if (scenario.StartsWith("core-"))
    {
        var cc=cell.DeepCopy();cc.Persistent.Clear();cc.Temporary.Clear();cc.EditorID="WinningCoreCave";
        if(scenario!="core-cell-override")
        {
            var winner=inside.DeepCopy();winner.Position=new P3Float(9,8,7);winner.Scale=.5f;winner.OpenByDefault=false;winner.MajorRecordFlagsRaw=0x400;
            if(scenario=="core-door-deleted")winner.MajorRecordFlagsRaw|=0x20;
            if(scenario=="core-door-temporary")cc.Temporary.Add(winner);else cc.Persistent.Add(winner);
        }
        var cb=new CellBlock{BlockNumber=8,GroupType=GroupTypeEnum.InteriorCellBlock};var cs=new CellSubBlock{BlockNumber=4,GroupType=GroupTypeEnum.InteriorCellSubBlock};
        cs.Cells.Add(cc);cb.SubBlocks.Add(cs);core.Cells.Records.Add(cb);
    }
    var keys = new[]{sfKey,portKey,coreKey};var styles=keys.Select(k=>new KeyedMasterStyle(k,MasterStyle.Full)).ToArray();
    foreach (var mod in new[]{sf,port,core}) mod.BeginWrite.ToPath(Path.Combine(folder,mod.ModKey.FileName.String)).WithLoadOrder(keys.Where(k=>k!=mod.ModKey)).WithKnownMasters(styles).Write();
    var lookup=new Cache<IModMasterStyledGetter,ModKey>(m=>m.ModKey);foreach(var s in styles)lookup.Set(s);
    IStarfieldModDisposableGetter Open(string file)=>StarfieldMod.CreateFromBinaryOverlay(file,StarfieldRelease.Starfield,new BinaryReadParameters {MasterFlagsLookup=lookup});
    using var sfo=Open(Path.Combine(folder,"Starfield.esm"));using var po=Open(Path.Combine(folder,"Port.esm"));using var co=Open(Path.Combine(folder,"Core.esm"));
    var original=Directory.GetFiles(folder,"*.esm").ToDictionary(p=>p,File.ReadAllBytes);
    try
    {
        var patch=ReturnPatch.Build(sfo,po,co,plan);
        Need(scenario is "valid" or "core-cell-override" or "core-door-override","invalid input accepted: "+scenario);
        var path=Path.Combine(folder,"FO4DoorReturn.esm");patch.BeginWrite.ToPath(path).WithLoadOrder(keys).WithKnownMasters(styles).Write();
        CheckMasterHeader(path);
        using var read=Open(path);
        Need(read.IsMaster && read.MasterStyle == MasterStyle.Full, "return patch must be a full master");
        Need(read.Worldspaces.Count==0 && read.EnumerateMajorRecords().Count()==2,"patch contains records outside interior CELL/REFR");
        var c=read.Cells.Records.Single().SubBlocks.Single().Cells.Single();var r=c.Persistent.OfType<IPlacedObjectGetter>().Single();
        Need(c.FormKey==cell.FormKey && c.Temporary.Count==0 && c.NavigationMeshes.Count==0,"wrong cell identity/children");
        var expected=scenario=="core-door-override" ? core.Cells.Records.Single().SubBlocks.Single().Cells.Single().Persistent.OfType<IPlacedObjectGetter>().Single() : inside;
        Need(r.FormKey==expected.FormKey && r.Position==expected.Position && r.Rotation==expected.Rotation && r.Scale==expected.Scale && r.MajorRecordFlagsRaw==expected.MajorRecordFlagsRaw && r.OpenByDefault==expected.OpenByDefault,"winning source state changed");
        Need(c.EditorID==(scenario.StartsWith("core-") ? "WinningCoreCave" : "SyntheticCave"),"winning cell override lost");
        Need(r.TeleportDestination!.Door.FormKey==outside.FormKey && r.TeleportDestination.Position==plan.Position && r.TeleportDestination.Rotation==plan.Rotation,"wrong return link/arrival");
        Need(read.ModHeader.MasterReferences.Select(m=>m.Master).SequenceEqual(keys),"wrong master ordering");
        Need(read.EnumerateMajorRecords().All(r=>r.FormKey.ModKey==portKey),"new patch-owned record allocated");
        var planPath=Path.Combine(folder,"plan.json");File.WriteAllText(planPath,JsonSerializer.Serialize(new{interior=plan.Interior.ToString(),exterior=plan.Exterior.ToString(),arrival_position=new[]{-5,7,8},arrival_rotation=new[]{0,0,.2f},flags=0}));
        var start=new ProcessStartInfo("dotnet"){RedirectStandardOutput=true,RedirectStandardError=true,UseShellExecute=false};start.ArgumentList.Add(typeof(ReturnPatch).Assembly.Location);
        var cliOutput = Path.Combine(folder,"cli") + (args.Contains("--output-alias-only") ? new string(Path.DirectorySeparatorChar, 3) : "");
        foreach(var arg in new[]{Path.Combine(folder,"Starfield.esm"),Path.Combine(folder,"Port.esm"),Path.Combine(folder,"Core.esm"),planPath,cliOutput})start.ArgumentList.Add(arg);
        using var child=Process.Start(start)!;var stdout=child.StandardOutput.ReadToEndAsync();var stderr=child.StandardError.ReadToEndAsync();
        if(!child.WaitForExit(60000)){child.Kill(true);throw new TimeoutException();}Task.WaitAll(stdout,stderr);File.WriteAllText(Path.Combine(folder,"cli.log"),stdout.Result+stderr.Result);
        Need(child.ExitCode==0,"CLI failed");
        CheckMasterHeader(Path.Combine(folder,"cli/FO4DoorReturn.esm"));
        using var receipt=JsonDocument.Parse(File.ReadAllText(Path.Combine(folder,"cli/build-state.json")));Need(receipt.RootElement.GetProperty("complete").GetBoolean(),"CLI receipt incomplete");
        if (args.Contains("--output-alias-only"))
        {
            var canonical = Path.Combine(folder,"cli");
            var published = Directory.GetFiles(canonical).ToDictionary(p => p, File.ReadAllBytes);
            start.ArgumentList[start.ArgumentList.Count - 1] = canonical;
            using var retry = Process.Start(start)!;
            var retryOut = retry.StandardOutput.ReadToEndAsync(); var retryErr = retry.StandardError.ReadToEndAsync();
            if (!retry.WaitForExit(60000)) { retry.Kill(true); throw new TimeoutException(); }
            Task.WaitAll(retryOut,retryErr);
            File.WriteAllText(Path.Combine(folder,"retry.log"), retryOut.Result + retryErr.Result);
            Need(retry.ExitCode != 0, "CLI accepted an already-owned output through its canonical alias");
            Need(Directory.GetFiles(canonical).Length == published.Count && published.All(p => File.ReadAllBytes(p.Key).SequenceEqual(p.Value)),
                "CLI retry changed the published plugin or receipt");
        }
        results.Add(new {scenario,result="binary-and-cli-pass"});
    }
    catch(InvalidDataException e)
    {
        Need(scenario is not ("valid" or "core-cell-override" or "core-door-override"),"valid pair rejected: "+e.Message);
        results.Add(new{scenario,result="refused",reason=e.Message});
    }
    Need(original.All(p=>File.ReadAllBytes(p.Key).SequenceEqual(p.Value)),"input files changed");
}
File.WriteAllText(Path.Combine(root,"results.json"),JsonSerializer.Serialize(results,new JsonSerializerOptions{WriteIndented=true}));
Console.WriteLine(results.Count+" return-patch scenarios passed: "+root);
if(!args.Contains("--overrides-only") && !args.Contains("--positive-only") && !args.Contains("--output-alias-only"))PipelineTests.Run(root);
if(!args.Contains("--overrides-only") && !args.Contains("--positive-only"))PublicationTests.Run(root);
