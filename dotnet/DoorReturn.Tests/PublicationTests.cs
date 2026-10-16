using System.Text.Json;

public static class PublicationTests
{
    public static void Run(string root)
    {
        void Need(bool ok,string message) { if(!ok)throw new Exception(message); }
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
            try {OutputDirectory.Claim(contested);File.WriteAllText(Path.Combine(contested,"owner.txt"),i.ToString());return true;}
            catch(IOException) {return false;}
        })).ToArray();Task.WaitAll(attempts);
        Need(attempts.Count(a=>a.Result)==1,"two builders acquired the output");
        var owner=Array.FindIndex(attempts,a=>a.Result);
        Need(File.ReadAllText(Path.Combine(contested,"owner.txt"))==owner.ToString(),"winner overwritten");
        Need(!Directory.EnumerateDirectories(root,".door-return-claim-*",SearchOption.AllDirectories).Any(),"empty temporary claim leaked");
        File.WriteAllText(Path.Combine(root,"publication-results.json"),JsonSerializer.Serialize(new{fresh=true,existing_empty_refused=true,existing_nonempty_preserved=true,one_concurrent_winner=true,temporary_claims_removed=true}));
        Console.WriteLine("Output claim checks passed: fresh, existing empty/nonempty and concurrent ownership.");
    }
}
