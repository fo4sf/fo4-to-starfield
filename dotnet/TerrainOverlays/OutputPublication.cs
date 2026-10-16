using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

// A recoverable file-set publication, not an atomic snapshot for arbitrary readers.
// Consumers must refuse the pending journal. Old/new bytes are retained, never deleted.
internal sealed class OutputPublication : IDisposable
{
    public const string PendingName = "FO4SF.terrain-output.pending.jsonl";
    public const string LeaseName = "FO4SF.terrain-output.lock";
    private sealed class Artifact
    {
        public required string Name;
        public string? OldHash, NewHash;
        public bool BackedUp, Published, Owned;
    }
    private readonly string root, work, pending;
    private readonly Artifact[] artifacts;
    private readonly Action<string>? observe;
    private readonly List<FileStream> handles = new();
    private FileStream? lease, journal;
    private string? journalHash;
    private bool committed, finished;

    public OutputPublication(string directory, IEnumerable<string> names, Action<string>? observe = null)
    {
        this.observe = observe; // fixture-only fault boundary; production supplies no callback
        root = Path.GetFullPath(directory);
        artifacts = names.Select(name => new Artifact { Name = name }).ToArray();
        if (artifacts.Length == 0 || artifacts.Select(a => a.Name).Distinct(StringComparer.OrdinalIgnoreCase).Count() != artifacts.Length
            || artifacts.Any(a => string.IsNullOrWhiteSpace(a.Name) || a.Name is "." or ".."
                || a.Name.Contains('/') || a.Name.Contains('\\') || Path.IsPathRooted(a.Name)
                || a.Name.IndexOfAny(Path.GetInvalidFileNameChars()) >= 0
                || a.Name.Equals(PendingName, StringComparison.OrdinalIgnoreCase)
                || a.Name.Equals(LeaseName, StringComparison.OrdinalIgnoreCase)))
            throw new InvalidDataException("output filenames must be distinct flat names");
        pending = Path.Combine(root, PendingName);
        work = Path.Combine(root, ".fo4sf-output-" + Guid.NewGuid().ToString("N"));
        if (File.Exists(pending) || Directory.Exists(pending))
            throw new IOException($"pending output publication requires review: {pending}");
        try
        {
            lease = new FileStream(Path.Combine(root, LeaseName), FileMode.CreateNew, FileAccess.ReadWrite,
                FileShare.None, 4096, FileOptions.DeleteOnClose);
            foreach (string part in new[] { "new", "old", "withdrawn" })
                Directory.CreateDirectory(Path.Combine(work, part));
            foreach (var artifact in artifacts)
            {
                string path = Target(artifact);
                if (Directory.Exists(path) || new FileInfo(path).LinkTarget != null)
                    throw new IOException($"output is a directory or symbolic link: {path}");
                if (File.Exists(path))
                    artifact.OldHash = HoldHash(path);
            }
            journal = new FileStream(pending, FileMode.CreateNew, FileAccess.ReadWrite, FileShare.Read | FileShare.Delete);
            SaveJournal("preparing");
        }
        catch
        {
            CloseHandles();
            throw;
        }
    }

    public string StagePath(string name)
    {
        if (!artifacts.Any(a => a.Name == name)) throw new InvalidDataException($"unregistered output: {name}");
        return Path.Combine(work, "new", name);
    }
    private string Target(Artifact a) => Path.Combine(root, a.Name);
    private string Backup(Artifact a) => Path.Combine(work, "old", a.Name);
    private static string HashStream(FileStream stream)
    {
        stream.Position = 0;
        return Convert.ToHexString(SHA256.HashData(stream)).ToLowerInvariant();
    }
    private string HoldHash(string path)
    {
        // Windows denies writable opens/mappings while allowing our guarded renames.
        // Other platforms still require immutable inputs and cooperating writers.
        var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read | FileShare.Delete);
        handles.Add(stream);
        return HashStream(stream);
    }
    private static string? PathHash(string path)
    {
        if (Directory.Exists(path) || new FileInfo(path).LinkTarget != null)
            throw new IOException($"unproven output path: {path}");
        if (!File.Exists(path)) return null;
        using var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete);
        return HashStream(stream);
    }
    private void SaveJournal(string phase)
    {
        if (journalHash != null && PathHash(pending) != journalHash)
            throw new IOException("output publication journal changed; preserved for review");
        var bytes = Encoding.UTF8.GetBytes(JsonSerializer.Serialize(new
        {
            format = 1, phase, recovery_directory = Path.GetFileName(work),
            files = artifacts.Select(a => new { name = a.Name, old_sha256 = a.OldHash, new_sha256 = a.NewHash,
                                                backed_up = a.BackedUp, published = a.Published })
        }));
        // Append complete snapshots: a torn final write must not erase the last
        // durable recovery state. Consumers refuse even an unreadable journal.
        journal!.Position = journal.Length;
        journal.Write(bytes);
        journal.WriteByte((byte)'\n');
        journal.Flush(true);
        journalHash = HashStream(journal);
        if (PathHash(pending) != journalHash) throw new IOException("output journal path changed");
    }
    private void FinishJournal(string phase)
    {
        SaveJournal(phase);
        File.Move(pending, Path.Combine(work, phase + ".jsonl")); // exclusive; retain the receipt
        finished = true;
    }

    public void Commit()
    {
        foreach (var a in artifacts)
        {
            a.NewHash = HoldHash(StagePath(a.Name));
            if (PathHash(Target(a)) != a.OldHash)
                throw new IOException($"output changed during preparation: {a.Name}");
        }
        SaveJournal("publishing");
        foreach (var a in artifacts)
        {
            if (PathHash(Target(a)) != a.OldHash) throw new IOException($"output changed: {a.Name}");
            if (a.OldHash != null)
            {
                File.Move(Target(a), Backup(a));
                a.BackedUp = true;
                if (PathHash(Backup(a)) != a.OldHash) throw new IOException($"moved output changed: {a.Name}");
            }
            SaveJournal("publishing");
        }
        foreach (var a in artifacts)
        {
            File.Move(StagePath(a.Name), Target(a)); // never overwrite a newly created destination
            a.Published = true;
            if (HoldHash(Target(a)) != a.NewHash) throw new IOException($"published output changed: {a.Name}");
            a.Owned = true;
            SaveJournal("publishing");
            observe?.Invoke("published:" + a.Name);
        }
        if (artifacts.Any(a => PathHash(Target(a)) != a.NewHash)) throw new IOException("published output set changed");
        FinishJournal("committed");
        committed = true;
    }

    private void Rollback()
    {
        foreach (var a in artifacts.Reverse())
        {
            try
            {
                if (a.Owned && PathHash(Target(a)) == a.NewHash)
                {
                    string withdrawn = Path.Combine(work, "withdrawn", a.Name);
                    File.Move(Target(a), withdrawn);
                    if (HoldHash(withdrawn) != a.NewHash)
                    {
                        if (!File.Exists(Target(a)) && !Directory.Exists(Target(a))) File.Move(withdrawn, Target(a));
                        continue;
                    }
                }
                if (a.BackedUp && PathHash(Backup(a)) == a.OldHash
                    && !File.Exists(Target(a)) && !Directory.Exists(Target(a)))
                    File.Move(Backup(a), Target(a));
            }
            catch (Exception e) when (e is IOException or UnauthorizedAccessException)
            {
                Console.Error.WriteLine($"publication rollback retained {a.Name}: {e.Message}");
            }
        }
        if (artifacts.All(a => PathHash(Target(a)) == a.OldHash)) FinishJournal("rolled-back");
        else
        {
            SaveJournal("recovery-required");
            Console.Error.WriteLine($"output recovery required; preserve {pending} and {work}");
        }
    }
    private void CloseHandles()
    {
        foreach (var stream in handles) stream.Dispose();
        try { journal?.Dispose(); }
        finally { lease?.Dispose(); }
    }
    public void Dispose()
    {
        try
        {
            if (!committed && !finished && journal != null) Rollback();
        }
        catch (Exception e) when (e is IOException or UnauthorizedAccessException)
        {
            Console.Error.WriteLine($"output recovery retained at {pending}: {e.Message}");
        }
        finally { CloseHandles(); }
    }
}
