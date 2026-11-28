using System.Text.Json;

namespace AuditBundle;

static class Program
{
    private static readonly JsonSerializerOptions JsonOpts = new() { WriteIndented = true };

    static int Main(string[] args)
    {
        if (args.Length == 0) return Usage();
        try
        {
            if (args[0] == "selftest")
            {
                if (args.Length < 2) return Usage();
                return SyntheticSelfTest.Run(args[1]);
            }

            int offset = args[0] == "audit-bundle" ? 1 : 0;
            var positional = new List<string>();
            string? sfData = null;
            string? mapMarkers = null;
            string? repoRoot = null;

            for (int i = offset; i < args.Length; i++)
            {
                switch (args[i])
                {
                    case "--sf-data" when i + 1 < args.Length:
                        sfData = args[++i];
                        break;
                    case "--map-markers" when i + 1 < args.Length:
                        mapMarkers = args[++i];
                        break;
                    case "--repo-root" when i + 1 < args.Length:
                        repoRoot = args[++i];
                        break;
                    case "--help" or "-h":
                        return Usage();
                    default:
                        if (args[i].StartsWith("--", StringComparison.Ordinal))
                        {
                            Console.Error.WriteLine($"Unknown option: {args[i]}");
                            return 2;
                        }
                        positional.Add(args[i]);
                        break;
                }
            }

            if (positional.Count < 3) return Usage();
            string bundleDir = positional[0];
            string portEsm = positional[1];
            string outJson = positional[2];

            repoRoot ??= DetectGitRoot(Directory.GetCurrentDirectory());
            var report = BundleAuditor.Run(bundleDir, portEsm, outJson, sfData, mapMarkers, repoRoot);

            string? outDir = Path.GetDirectoryName(Path.GetFullPath(outJson));
            if (!string.IsNullOrEmpty(outDir)) Directory.CreateDirectory(outDir);
            File.WriteAllText(outJson, JsonSerializer.Serialize(report, JsonOpts));
            Console.WriteLine($"audit-bundle wrote {outJson} ({new FileInfo(outJson).Length:N0} bytes): " +
                              $"plugins={report.LoadOrder.Count}, official_overrides={report.Overrides.OfficialOverrideCount}, " +
                              $"shared={report.SharedRecords.AllSharedCount}, flagged_bindings={report.ScriptBindings.FlaggedBindings.Count}, " +
                              $"persistent={report.PersistentReferences.TotalPersistentRefs}, official_lscr={report.StarfieldLeftovers.OfficialLscrTotal}");
            return 0;
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"audit-bundle error: {ex.Message}");
            return 1;
        }
    }

    private static string? DetectGitRoot(string startDir)
    {
        for (string? dir = Path.GetFullPath(startDir); !string.IsNullOrEmpty(dir); dir = Path.GetDirectoryName(dir))
        {
            string g = Path.Combine(dir, ".git");
            if (Directory.Exists(g) || File.Exists(g)) return dir;
        }
        return null;
    }

    private static int Usage()
    {
        Console.Error.WriteLine(
            "usage: AuditBundle [audit-bundle] <bundle-dir> <port-esm> <out.json> [--sf-data <dir>] [--map-markers <esm>] [--repo-root <dir>]\n" +
            "       AuditBundle selftest <scratch-dir>");
        return 2;
    }
}
