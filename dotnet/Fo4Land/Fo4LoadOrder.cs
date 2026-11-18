using Mutagen.Bethesda;
using Mutagen.Bethesda.Fallout4;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Cache;

public sealed class Fo4LoadOrder : IDisposable
{
    private readonly List<IDisposable> _disposables = new();
    public IReadOnlyList<IFallout4ModGetter> Mods { get; }
    public IFallout4ModGetter ActiveMod => Mods[^1];
    public ILinkCache Cache { get; }

    private Fo4LoadOrder(List<IDisposable> disposables, List<IFallout4ModGetter> mods)
    {
        _disposables = disposables;
        Mods = mods;
        Cache = mods.ToImmutableLinkCache();
    }

    public static Fo4LoadOrder Open(string pluginPath, IReadOnlyList<string> masterPaths)
    {
        var disposables = new List<IDisposable>();
        var mods = new List<IFallout4ModGetter>();
        try
        {
            foreach (var mp in masterPaths)
            {
                var m = Fallout4Mod.CreateFromBinaryOverlay(mp, Fallout4Release.Fallout4);
                disposables.Add(m);
                mods.Add(m);
            }
            var active = Fallout4Mod.CreateFromBinaryOverlay(pluginPath, Fallout4Release.Fallout4);
            disposables.Add(active);
            mods.Add(active);
            return new Fo4LoadOrder(disposables, mods);
        }
        catch
        {
            foreach (var d in disposables) d.Dispose();
            throw;
        }
    }

    public (FormKey Key, IWorldspaceGetter Winner, string EditorId, List<IWorldspaceGetter> Copies)? FindWorld(string worldEdid)
    {
        var byKey = new Dictionary<FormKey, List<IWorldspaceGetter>>();
        var order = new List<FormKey>();
        foreach (var m in Mods)
        {
            foreach (var w in m.Worldspaces)
            {
                if (!byKey.TryGetValue(w.FormKey, out var list))
                {
                    list = new List<IWorldspaceGetter>();
                    byKey[w.FormKey] = list;
                    order.Add(w.FormKey);
                }
                list.Add(w);
            }
        }
        foreach (var k in order)
        {
            var copies = byKey[k];
            if (copies[^1].IsDeleted) continue;
            string? edid = null;
            for (int i = copies.Count - 1; i >= 0; i--)
            {
                if (!string.IsNullOrEmpty(copies[i].EditorID)) { edid = copies[i].EditorID; break; }
            }
            if (string.Equals(edid, worldEdid, StringComparison.Ordinal))
                return (k, copies[^1], edid!, copies);
        }
        return null;
    }

    public static (string[] Args, List<string> Masters, bool BadSyntax) SplitMasters(string[] args)
    {
        var masters = new List<string>();
        var rest = new List<string>();
        for (int i = 0; i < args.Length; i++)
        {
            if (args[i] == "--master")
            {
                if (i + 1 >= args.Length) return (Array.Empty<string>(), masters, true);
                masters.Add(args[++i]);
            }
            else
            {
                rest.Add(args[i]);
            }
        }
        return (rest.ToArray(), masters, false);
    }

    private static readonly HashSet<string> GameInstallMarkers = new(StringComparer.OrdinalIgnoreCase)
    {
        "starfield.exe", "fallout4.exe", "fallout4launcher.exe", "starfield.ccc", "fallout4.ccc", "creationkit.exe"
    };

    private static readonly HashSet<string> GameDataEsms = new(StringComparer.OrdinalIgnoreCase)
    {
        "starfield.esm", "fallout4.esm"
    };

    public static void RefuseUnsafeOutput(string outPath, IEnumerable<string> inputPaths)
    {
        if (string.IsNullOrWhiteSpace(outPath))
            throw new InvalidOperationException("refused: empty output path");
        var fullOut = Path.GetFullPath(outPath);
        foreach (var inp in inputPaths)
        {
            if (string.IsNullOrWhiteSpace(inp)) continue;
            if (string.Equals(fullOut, Path.GetFullPath(inp), StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException($"refused: output path '{outPath}' aliases input '{inp}'");
        }
        var slash = fullOut.Replace('\\', '/').ToLowerInvariant();
        if (slash.Contains("/steamapps/common/") || slash.Contains("/steamapps/content/"))
            throw new InvalidOperationException($"refused: output path '{outPath}' lies inside a Steam game/depot folder");

        var cur = Directory.Exists(fullOut) ? fullOut : Path.GetDirectoryName(fullOut);
        while (!string.IsNullOrEmpty(cur))
        {
            if (File.Exists(Path.Combine(cur, ".git")) || Directory.Exists(Path.Combine(cur, ".git")))
                throw new InvalidOperationException($"refused: output path '{outPath}' lies inside Git worktree '{cur}'");
            if (Directory.Exists(cur))
            {
                try
                {
                    var entries = Directory.EnumerateFileSystemEntries(cur).Select(Path.GetFileName).Where(n => n != null).ToList();
                    if (entries.Any(n => GameInstallMarkers.Contains(n!)))
                        throw new InvalidOperationException($"refused: output path '{outPath}' lies inside game directory '{cur}'");
                    if (string.Equals(Path.GetFileName(cur), "Data", StringComparison.OrdinalIgnoreCase) &&
                        entries.Any(n => GameDataEsms.Contains(n!)))
                        throw new InvalidOperationException($"refused: output path '{outPath}' lies inside game Data directory '{cur}'");
                }
                catch (UnauthorizedAccessException) { }
            }
            var parent = Path.GetDirectoryName(cur);
            if (parent == cur) break;
            cur = parent;
        }
    }

    public void Dispose()
    {
        for (int i = _disposables.Count - 1; i >= 0; i--)
            _disposables[i].Dispose();
    }
}
