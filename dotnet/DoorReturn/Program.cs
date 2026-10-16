using System.Security.Cryptography;
using System.Text.Json;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;

if (args.Length != 5) throw new ArgumentException("usage: <Starfield.esm> <Port.esm> <Core.esm> <return-plan.json> <fresh-output-dir>");
if (Directory.Exists(args[4])) throw new InvalidOperationException("output directory already exists");
string Hash(string path) { using var f = File.OpenRead(path); return Convert.ToHexString(SHA256.HashData(f)).ToLowerInvariant(); }
var pins = args.Take(4).ToDictionary(Path.GetFullPath, Hash);
var keys = args.Take(3).Select(p => ModKey.FromFileName(Path.GetFileName(p))).ToArray();
var styles = keys.Select(k => new KeyedMasterStyle(k, MasterStyle.Full)).ToArray();
var lookup = new Cache<IModMasterStyledGetter, ModKey>(m => m.ModKey);
foreach (var s in styles) lookup.Set(s);
IStarfieldModDisposableGetter Open(string path) => StarfieldMod.CreateFromBinaryOverlay(path, StarfieldRelease.Starfield,
    new BinaryReadParameters { MasterFlagsLookup = lookup });
using var sf = Open(args[0]); using var port = Open(args[1]); using var core = Open(args[2]);
using var json = JsonDocument.Parse(File.ReadAllText(args[3]));
var p = json.RootElement;
P3Float Vector(string name)
{
    var a = p.GetProperty(name).EnumerateArray().Select(x => x.GetSingle()).ToArray();
    if (a.Length != 3) throw new InvalidDataException("arrival vector must have three components");
    return new P3Float(a[0], a[1], a[2]);
}
var plan = new ReturnPlan(FormKey.Factory(p.GetProperty("interior").GetString()!), FormKey.Factory(p.GetProperty("exterior").GetString()!),
    Vector("arrival_position"), Vector("arrival_rotation"), p.GetProperty("flags").GetUInt32());
var mod = ReturnPatch.Build(sf, port, core, plan);
void VerifyPins() { if (pins.Any(p => Hash(p.Key) != p.Value)) throw new InvalidOperationException("input changed during build"); }
VerifyPins();
OutputDirectory.Claim(args[4]);
var receipt = Path.Combine(args[4], "build-state.json");
File.WriteAllText(receipt, "{\"complete\":false}");
var output = Path.Combine(args[4], ReturnPatch.PatchKey.FileName.String);
mod.BeginWrite.ToPath(output).WithLoadOrder(keys).WithKnownMasters(styles).Write();
VerifyPins();
File.WriteAllText(receipt, JsonSerializer.Serialize(new { complete = true, input_sha256 = pins,
    output_sha256 = Hash(output), interior = plan.Interior.ToString(), exterior = plan.Exterior.ToString(),
    native_acceptance = false, installed = false }, new JsonSerializerOptions { WriteIndented = true }));
Console.WriteLine("Wrote interior-only return patch: " + output);
