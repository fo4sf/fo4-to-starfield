public static class OutputDirectory
{
    public static string Normalize(string requested) => Path.TrimEndingDirectorySeparator(Path.GetFullPath(requested));

    // Directory.CreateDirectory succeeds for an existing directory. A same-parent
    // rename instead reserves the requested path without replacing another build.
    public static void Claim(string requested)
    {
        var target = Normalize(requested);
        var parent = Path.GetDirectoryName(target) ?? throw new ArgumentException("output needs a parent directory");
        Directory.CreateDirectory(parent);
        var temporary = Path.Combine(parent, ".door-return-claim-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(temporary);
        try { Directory.Move(temporary, target); }
        finally
        {
            // Only our still-empty reservation directory, never a failed output.
            if (Directory.Exists(temporary)) Directory.Delete(temporary);
        }
    }
}
