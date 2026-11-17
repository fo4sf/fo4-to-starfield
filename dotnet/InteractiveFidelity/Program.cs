// InteractiveFidelity: builds and checks converter interactive-fidelity plugins (CF-5 part 1).
//   build <params.json>
//   check <plugin.esm> --starfield <Starfield.esm> [--core <FO4TerrainCore.esm>] [--port <FO4Port.esm>]
//         [--port-reference <FO4Port.esm>] [--report <out.json>]
//   selftest <scratch_dir>
using System.Text.Json;

if (args.Length == 0)
    return Usage();

try
{
    return args[0] switch
    {
        "build" when args.Length == 2 => OverlayBuilder.Run(args[1]),
        "check" when args.Length >= 2 => FidelityCheck.RunCli(args),
        "selftest" when args.Length == 2 => SelfTest.Run(args[1]),
        _ => Usage(),
    };
}
catch (Exception ex) when (ex is InvalidDataException or InvalidOperationException or FileNotFoundException)
{
    Console.Error.WriteLine("error: " + ex.Message);
    return 2;
}

static int Usage()
{
    Console.Error.WriteLine("usage:");
    Console.Error.WriteLine("  InteractiveFidelity build <params.json>");
    Console.Error.WriteLine("  InteractiveFidelity check <plugin.esm> --starfield <Starfield.esm> [--core <FO4TerrainCore.esm>] [--port <FO4Port.esm>] [--port-reference <FO4Port.esm>] [--report <out.json>]");
    Console.Error.WriteLine("  InteractiveFidelity selftest <scratch_dir>");
    return 1;
}
