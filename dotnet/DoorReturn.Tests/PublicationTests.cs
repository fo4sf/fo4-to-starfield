using System.Text.Json;

public static class PublicationTests
{
    public static void Run(string root)
    {
        void Need(bool ok,string message) { if(!ok)throw new Exception(message); }
        var filesystemRoot = Path.GetPathRoot(Path.GetFullPath(root))!;
        Need(OutputDirectory.Normalize(filesystemRoot) == filesystemRoot, "normalization changed the filesystem root");
        foreach (var (name, suffix) in new[] { ("separator", Path.DirectorySeparatorChar.ToString()),
            ("alternate", Path.AltDirectorySeparatorChar.ToString()), ("repeated", new string(Path.DirectorySeparatorChar, 3)),
            ("relative", Path.DirectorySeparatorChar.ToString()) })
        {
            var canonical = Path.Combine(root, name);
            var requested = name == "relative" ? Path.GetRelativePath(Environment.CurrentDirectory, canonical) : canonical;
            OutputDirectory.Claim(requested + suffix);
            Need(Directory.Exists(canonical), "trailing separator output not claimed: " + name);
            var marker = Path.Combine(canonical, "owner.txt"); File.WriteAllText(marker, name);
            try { OutputDirectory.Claim(canonical); throw new Exception("path alias replaced existing output"); }
            catch (IOException) { Need(File.ReadAllText(marker) == name, "existing alias contents changed"); }
        }
        var fresh=Path.Combine(root,"nested","fresh");OutputDirectory.Claim(fresh);
        Need(Directory.Exists(fresh),"fresh output not claimed");
        var file=Path.Combine(fresh,"previous.txt");File.WriteAllText(file,"preserved");
        try {OutputDirectory.Claim(fresh);throw new Exception("existing nonempty directory accepted");}
        catch(IOException) {Need(File.ReadAllText(file)=="preserved","prior file changed");}
        var empty=Path.Combine(root,"empty");Directory.CreateDirectory(empty);
        try {OutputDirectory.Claim(empty);throw new Exception("existing empty directory accepted");}
        catch(IOException) {Need(Directory.Exists(empty),"prior empty directory removed");}
        var contested=Path.Combine(root,"contested");using var barrier=new Barrier(2);
        var attempts=Enumerable.Range(0,2).Select(i=>Task.Run(()=>{
            barrier.SignalAndWait();
            try {OutputDirectory.Claim(contested + (i == 0 ? Path.DirectorySeparatorChar.ToString() : ""));File.WriteAllText(Path.Combine(contested,"owner.txt"),i.ToString());return true;}
            catch(IOException) {return false;}
        })).ToArray();Task.WaitAll(attempts);
        Need(attempts.Count(a=>a.Result)==1,"two builders acquired the output");
        var owner=Array.FindIndex(attempts,a=>a.Result);
        Need(File.ReadAllText(Path.Combine(contested,"owner.txt"))==owner.ToString(),"winner overwritten");
        Need(!Directory.EnumerateDirectories(root,".door-return-claim-*",SearchOption.AllDirectories).Any(),"empty temporary claim leaked");
        File.WriteAllText(Path.Combine(root,"publication-results.json"),JsonSerializer.Serialize(new{fresh=true,trailing_separators=true,existing_alias_preserved=true,existing_empty_refused=true,existing_nonempty_preserved=true,one_concurrent_alias_winner=true,temporary_claims_removed=true}));
        Console.WriteLine("Output claim checks passed: trailing separators, existing outputs and concurrent alias ownership.");
    }
}
