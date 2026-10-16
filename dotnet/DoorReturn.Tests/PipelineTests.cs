using System.Diagnostics;
using System.Text.Json;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;

public static class PipelineTests
{
    public static void Run(string root)
    {
        void Need(bool ok, string message) { if (!ok) throw new InvalidOperationException(message); }
        var folder=Path.Combine(root,"pipeline");Directory.CreateDirectory(folder);
        var sfKey=ModKey.FromNameAndExtension("Starfield.esm");var portKey=ModKey.FromNameAndExtension("Port.esm");var coreKey=ModKey.FromNameAndExtension("Core.esm");
        var sf=new StarfieldMod(sfKey,StarfieldRelease.Starfield);var baseKey=new FormKey(sfKey,0x900);
        sf.Doors.Add(new Door(baseKey,StarfieldRelease.Starfield));
        var sfPath=Path.Combine(folder,"Starfield.esm");sf.BeginWrite.ToPath(sfPath).WithNoLoadOrder().Write();
        var port=new StarfieldMod(portKey,StarfieldRelease.Starfield);
        var cell=new Cell(new FormKey(portKey,0x800),StarfieldRelease.Starfield){Flags=Cell.Flag.IsInteriorCell,EditorID="FO4Port_Cave"};
        var block=new CellBlock{BlockNumber=8,GroupType=GroupTypeEnum.InteriorCellBlock};var sub=new CellSubBlock{BlockNumber=4,GroupType=GroupTypeEnum.InteriorCellSubBlock};
        sub.Cells.Add(cell);block.SubBlocks.Add(sub);port.Cells.Records.Add(block);
        var input=Path.Combine(folder,"Port.esm");port.BeginWrite.ToPath(input).WithNoLoadOrder().Write();
        const string source="000123:Source.esm", exteriorSource="000456:Source.esm", identity="REFR:FO4Port_Cave:"+source;
        var ids=new Dictionary<string,uint>{["CELL:FO4Port_Cave"]=0x800,[identity]=0x810,["RESERVED:unrelated"]=0x920};
        var map=Path.Combine(folder,"formids.json");File.WriteAllText(map,JsonSerializer.Serialize(ids));
        var export=Path.Combine(folder,"cave.json");File.WriteAllText(export,JsonSerializer.Serialize(new{cell="Cave",refs=new[]{new{
            formkey=source,type="Door",pos=new[]{70,140,210},rot=new[]{0,0,.4},scale=.93,disabled=0,persistent=true,open_by_default=false,
            teleport_destination=new{door=exteriorSource,pos=new[]{-350,490,560},rot=new[]{0,0,.2},flags=0,transition_interior=(string?)null}}}}));
        var mapping=Path.Combine(folder,"mapping.json");File.WriteAllText(mapping,JsonSerializer.Serialize(new Dictionary<string,string>{[source]=baseKey.ToString()}));
        int Cli(string name,string assembly,IEnumerable<string> arguments)
        {
            var p=new ProcessStartInfo("dotnet"){RedirectStandardOutput=true,RedirectStandardError=true,UseShellExecute=false};p.ArgumentList.Add(assembly);
            foreach(var arg in arguments)p.ArgumentList.Add(arg);p.Environment["STARFIELD_DATA"]=folder;
            using var child=Process.Start(p)!;var stdout=child.StandardOutput.ReadToEndAsync();var stderr=child.StandardError.ReadToEndAsync();
            if(!child.WaitForExit(60000)){child.Kill(true);throw new TimeoutException(name);}Task.WaitAll(stdout,stderr);
            File.WriteAllText(Path.Combine(folder,name+".log"),stdout.Result+stderr.Result);return child.ExitCode;
        }
        var strict=Path.Combine(folder,"strict");var prepared=Path.Combine(folder,"prepared");
        var prefix=new[]{input,map,strict,export,"--no-markers","--door-bases="+mapping};
        Need(Cli("strict",typeof(Relationships).Assembly.Location,prefix)==2,"unresolved exterior was accepted");
        Need(!File.Exists(Path.Combine(strict,"Port.esm")),"strict phase published a plugin");
        prefix[2]=prepared;
        Need(Cli("prepare",typeof(Relationships).Assembly.Location,prefix.Append("--allow-unresolved"))==0,"endpoint preparation failed");
        var saved=JsonSerializer.Deserialize<Dictionary<string,uint>>(File.ReadAllText(Path.Combine(prepared,"formids.json")))!;
        Need(saved.Count==ids.Count && ids.All(p=>saved[p.Key]==p.Value),"persistent reservations changed");
        var insideKey=new FormKey(portKey,saved[identity]);var outsideKey=new FormKey(coreKey,0x820);
        var core=new StarfieldMod(coreKey,StarfieldRelease.Starfield);var world=new Worldspace(new FormKey(coreKey,0x803),StarfieldRelease.Starfield);
        world.TopCell=new Cell(new FormKey(coreKey,0x804),StarfieldRelease.Starfield);
        var outside=new PlacedObject(outsideKey,StarfieldRelease.Starfield){MajorRecordFlagsRaw=0x400,Position=new P3Float(-3,4,5)};outside.Base.SetTo(baseKey);
        outside.TeleportDestination=new TeleportDestination{Position=new P3Float(2,3,4)};outside.TeleportDestination.Door.SetTo(insideKey);
        world.TopCell.Persistent.Add(outside);core.Worldspaces.Add(world);
        var corePath=Path.Combine(folder,"Core.esm");var keys=new[]{sfKey,portKey,coreKey};var styles=keys.Select(k=>new KeyedMasterStyle(k,MasterStyle.Full)).ToArray();
        core.BeginWrite.ToPath(corePath).WithLoadOrder(keys.Take(2)).WithKnownMasters(styles).Write();
        var plan=Path.Combine(folder,"return.json");File.WriteAllText(plan,JsonSerializer.Serialize(new{interior=insideKey.ToString(),exterior=outsideKey.ToString(),arrival_position=new[]{-5,7,8},arrival_rotation=new[]{0,0,.2},flags=0}));
        var output=Path.Combine(folder,"return");var preparedPath=Path.Combine(prepared,"Port.esm");
        var originals=new[]{input,map,preparedPath,corePath,sfPath}.ToDictionary(p=>p,File.ReadAllBytes);
        Need(Cli("return",typeof(ReturnPatch).Assembly.Location,new[]{sfPath,preparedPath,corePath,plan,output})==0,"return bridge rejected prepared endpoint");
        var read=StarfieldMod.CreateFromBinary(Path.Combine(output,"FO4DoorReturn.esm"),StarfieldRelease.Starfield,
            new Mutagen.Bethesda.Plugins.Binary.Parameters.BinaryReadParameters{MasterFlagsLookup=Styles(styles)});
        var target=read.Cells.Records.Single().SubBlocks.Single().Cells.Single().Persistent.OfType<IPlacedObjectGetter>().Single();
        var coreRead=StarfieldMod.CreateFromBinary(corePath,StarfieldRelease.Starfield,
            new Mutagen.Bethesda.Plugins.Binary.Parameters.BinaryReadParameters{MasterFlagsLookup=Styles(styles)});
        var outward=coreRead.Worldspaces.Single().TopCell!.Persistent.OfType<IPlacedObjectGetter>().Single();
        Need(target.FormKey==insideKey && target.TeleportDestination!.Door.FormKey==outward.FormKey && outward.FormKey==outsideKey && outward.TeleportDestination!.Door.FormKey==insideKey,"serialized reciprocal identity handoff failed");
        Need(target.Position==new P3Float(1,2,3) && Math.Abs(target.Rotation.Z-.4f)<1e-6 && Math.Abs(target.Scale!.Value-.93f)<1e-6 && target.MajorRecordFlagsRaw==0x400,"prepared state changed");
        Need(target.TeleportDestination!.Position==new P3Float(-5,7,8) && Math.Abs(target.TeleportDestination.Rotation.Z-.2f)<1e-6,"arrival conversion changed");
        Need(read.EnumerateMajorRecords().Count()==2 && read.Worldspaces.Count==0,"return patch changed exterior scope");
        Need(originals.All(p=>File.ReadAllBytes(p.Key).SequenceEqual(p.Value)),"input bytes changed");
        File.WriteAllText(Path.Combine(folder,"result.json"),JsonSerializer.Serialize(new{strict_refused=true,reservations_unchanged=true,reciprocal_links=true,input_bytes_unchanged=true,native_acceptance=false},new JsonSerializerOptions{WriteIndented=true}));
        Console.WriteLine("Joint ReferenceLinks -> synthetic Core -> DoorReturn CLI handoff passed.");
    }
    static Cache<IModMasterStyledGetter,ModKey> Styles(IEnumerable<KeyedMasterStyle> styles)
    {var c=new Cache<IModMasterStyledGetter,ModKey>(m=>m.ModKey);foreach(var s in styles)c.Set(s);return c;}
}
