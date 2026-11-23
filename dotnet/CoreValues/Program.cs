// CoreValues: writes and verifies FO4SFCoreValues.esm from src/fo4sf/core/core_values.json.
//
// FO4SFCoreValues.esm is the single shared value store mastered by all FO4SF slices:
//   0x800..0x805 Radiation AVIFs & GLOBs (FO4SF_Rads at 0x800 matches Pip-Boy local id 0x800)
//   0x810..0x817 S.P.E.C.I.A.L. 7 AVIFs + FO4SF_SpecialAVList FLST
//   0x820..0x82D 13 Fallout Skill AVIFs + FO4SF_SkillAVList FLST
//   0x830..0x832 Karma AVIF + KarmaValue & KarmaTier GLOBs
//   0x840..0x847 Hardcore toggle, fast-travel gate, and Hunger/Thirst/Sleep AVIFs + stage GLOBs
//   0x850..0x851 Shared FO4SF_StimpakEffect MGEF + FO4SF_Stimpak ALCH
//   0x860        FO4SF_TestModeEnabled GLOB (default 0)
//   0x865        FO4SF_PipboyAcquired GLOB (default 0, non-constant)
//   0x870..0x876 Start & Mode GLOBs (GameMode, SurvivalStart, SurvivalLocked, StartDifficulty, WarfareFaction, WarfareStartIndex, StartChoiceDone)
//   D7(a) optional Starfield.esm overrides (--commonwealth-weather 1, default on when Starfield.esm contains Mars/NewAtlantis CLMT/ATMO;
//         --commonwealth-weather 0 rollback):
//     CLMT 0x00310DB1 ClimateUniqueCydonia       -> clear New Atlantis WTHS (0x001034AB 60%, 0x0009BC5A 40%)
//     CLMT 0x002EDEA5 ClimateUniqueCydoniaFrozen -> clear New Atlantis WTHS (0x001034AB 60%, 0x0009BC5A 40%)
//     ATMO 0x0000C9D2 ATMO_Mars                  -> ATMO_Jemison (0x0000C010) clear blue-sky atmospheric scattering
//
// usage:
//   CoreValues build <Starfield.esm> <out dir> [--json <core_values.json>] [--default-rads-rule 0|1] [--default-hardcore 0|1] [--test-mode 0|1] [--commonwealth-weather 0|1]
//   CoreValues check <FO4SFCoreValues.esm> <Starfield.esm> [--json <core_values.json>] [--default-rads-rule 0|1] [--default-hardcore 0|1] [--test-mode 0|1] [--commonwealth-weather 0|1]
//   CoreValues fixture <out dir>
//   CoreValues selftest <scratch dir>

using System.Globalization;
using System.Text.Json;
using Mutagen.Bethesda;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;

try
{
    var rest = args.ToList();
    string? jsonPath = null;
    int radsRule = 0;
    int hardcore = 0;
    int testMode = 0;
    int commonwealthWeather = 1;

    void OptInt(string name, ref int into)
    {
        int i = rest.IndexOf(name);
        if (i < 0) return;
        if (i + 1 >= rest.Count || !int.TryParse(rest[i + 1], NumberStyles.Integer, CultureInfo.InvariantCulture, out int v) || (v != 0 && v != 1))
            throw new CoreValuesWriter.Refusal($"{name} must be 0 or 1");
        into = v;
        rest.RemoveRange(i, 2);
    }
    void OptStr(string name, ref string? into)
    {
        int i = rest.IndexOf(name);
        if (i < 0) return;
        if (i + 1 >= rest.Count) throw new CoreValuesWriter.Refusal($"{name} needs a path");
        into = rest[i + 1];
        rest.RemoveRange(i, 2);
    }

    OptStr("--json", ref jsonPath);
    OptInt("--default-rads-rule", ref radsRule);
    OptInt("--default-hardcore", ref hardcore);
    OptInt("--test-mode", ref testMode);
    OptInt("--commonwealth-weather", ref commonwealthWeather);
    var opts = new CoreValuesWriter.BuildOptions(jsonPath ?? CoreValuesWriter.DefaultJsonPath(), radsRule, hardcore, testMode, commonwealthWeather);

    if (rest.Count == 3 && rest[0] == "build") return CoreValuesWriter.Build(rest[1], rest[2], opts);
    if (rest.Count == 3 && rest[0] == "check") return CoreValuesWriter.Check(rest[1], rest[2], opts);
    if (rest.Count == 2 && rest[0] == "fixture") return CoreValuesWriter.Fixture(rest[1]);
    if (rest.Count == 2 && rest[0] == "selftest") return CoreValuesWriter.SelfTest(rest[1]);
}
catch (CoreValuesWriter.Refusal r)
{
    Console.Error.WriteLine("refused: " + r.Message);
    return 1;
}

Console.Error.WriteLine("usage: CoreValues build <Starfield.esm> <out dir> [--json <path>] [--default-rads-rule 0|1] [--default-hardcore 0|1] [--test-mode 0|1] | " +
                        "check <plugin> <Starfield.esm> [same options] | fixture <out dir> | selftest <scratch dir>");
return 2;

public static class CoreValuesWriter
{
    public class Refusal(string m) : Exception(m);
    public record BuildOptions(string JsonPath, int DefaultRadsRule = 0, int DefaultHardcore = 0, int TestMode = 0, int CommonwealthWeather = 1);
    public record RecordSpec(
        uint Id, string Type, string Edid, string Name, string Abbr, string Desc,
        float Default, float Min, float Max, string[] Flags, string[] Items, string Effect, bool Constant = false);

    const StarfieldRelease Release = StarfieldRelease.Starfield;
    static readonly ModKey SfEsm = ModKey.FromFileName("Starfield.esm");

    // D7(a): binary-verified Starfield.esm FormIDs driving Mars/Cydonia dust storms over FO4Core_Commonwealth
    // (WRLD 0x01000803 BNAM -> BIOM 0x002A3777 DesertRockyNoLifeMars -> ENAM CLMT 0x00310DB1 ClimateUniqueCydonia;
    //  PNDT 0x0003F59A MarsPlanetData -> ATMO 0x0000C9D2 ATMO_Mars).
    static readonly FormKey ClimateCydoniaKey = new(SfEsm, 0x00310DB1);
    static readonly FormKey ClimateCydoniaFrozenKey = new(SfEsm, 0x002EDEA5);
    static readonly FormKey ClimateNewAtlantisKey = new(SfEsm, 0x0024E982);
    static readonly FormKey WeatherNAClearKey = new(SfEsm, 0x001034AB);
    static readonly FormKey WeatherNAPartlyCloudyKey = new(SfEsm, 0x0009BC5A);
    static readonly FormKey AtmoMarsKey = new(SfEsm, 0x0000C9D2);
    static readonly FormKey AtmoJemisonKey = new(SfEsm, 0x0000C010);
    static readonly HashSet<FormKey> AllowedWeatherOverrideKeys = new()
    {
        ClimateCydoniaKey,
        ClimateCydoniaFrozenKey,
        AtmoMarsKey,
    };

    public static string DefaultJsonPath()
    {
        var dir = AppContext.BaseDirectory;
        for (int up = 0; up < 8 && dir != null; up++, dir = Directory.GetParent(dir)?.FullName)
        {
            var candidate = Path.Combine(dir, "src", "fo4sf", "core", "core_values.json");
            if (File.Exists(candidate)) return candidate;
        }
        var cwd = Path.Combine(Directory.GetCurrentDirectory(), "src", "fo4sf", "core", "core_values.json");
        if (File.Exists(cwd)) return cwd;
        throw new Refusal("cannot locate src/fo4sf/core/core_values.json; pass --json <path>");
    }

    public static (ModKey PluginKey, uint NextFormId, List<RecordSpec> Specs) LoadSchema(string jsonPath)
    {
        if (!File.Exists(jsonPath)) throw new Refusal($"missing schema json: {jsonPath}");
        using var doc = JsonDocument.Parse(File.ReadAllText(jsonPath));
        var root = doc.RootElement;
        var pluginName = root.GetProperty("plugin").GetString() ?? throw new Refusal("schema missing plugin");
        var nextHex = root.GetProperty("next_form_id").GetString() ?? throw new Refusal("schema missing next_form_id");
        uint nextId = Convert.ToUInt32(nextHex, 16);
        var specs = new List<RecordSpec>();
        var seenIds = new HashSet<uint>();
        var seenEdids = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        foreach (var el in root.GetProperty("records").EnumerateArray())
        {
            uint id = Convert.ToUInt32(el.GetProperty("id").GetString()!, 16);
            string type = el.GetProperty("type").GetString()!;
            string edid = el.GetProperty("edid").GetString()!;
            if (!seenIds.Add(id)) throw new Refusal($"duplicate FormID 0x{id:X6} in {jsonPath}");
            if (!seenEdids.Add(edid)) throw new Refusal($"duplicate EditorID {edid} in {jsonPath}");

            string Str(string k) => el.TryGetProperty(k, out var v) ? v.GetString() ?? "" : "";
            float Flt(string k) => el.TryGetProperty(k, out var v) ? v.GetSingle() : 0f;
            bool Bool(string k) => el.TryGetProperty(k, out var v) && v.GetBoolean();
            string[] Arr(string k) => el.TryGetProperty(k, out var v)
                ? v.EnumerateArray().Select(x => x.GetString()!).ToArray()
                : Array.Empty<string>();
            if (id >= nextId) throw new Refusal($"FormID 0x{id:X6} ({edid}) >= next_form_id 0x{nextId:X6} in {jsonPath}");

            specs.Add(new RecordSpec(
                id, type, edid, Str("name"), Str("abbr"), Str("desc"),
                Flt("default"), Flt("min"), Flt("max"), Arr("flags"), Arr("items"), Str("effect"), Bool("constant")));
        }
        return (ModKey.FromFileName(pluginName), nextId, specs);
    }

    static IStarfieldModDisposableGetter OpenMod(string path)
    {
        var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        styles.Set(new KeyedMasterStyle(SfEsm, MasterStyle.Full));
        return StarfieldMod.CreateFromBinaryOverlay(path, Release, new BinaryReadParameters { MasterFlagsLookup = styles });
    }

    static ActorValueInformation.Flag ParseAvifFlags(string[] names)
    {
        ActorValueInformation.Flag f = 0;
        foreach (var n in names)
        {
            f |= n switch
            {
                "DefaultToZero" => ActorValueInformation.Flag.DefaultToZero,
                "DamageIsPositive" => ActorValueInformation.Flag.DamageIsPositive,
                "DefaultToOne" => ActorValueInformation.Flag.DefaultToOne,
                "MinimumOne" => ActorValueInformation.Flag.MinimumOne,
                "MaximumTen" => ActorValueInformation.Flag.MaximumTen,
                _ => throw new Refusal($"unknown AVIF flag '{n}'"),
            };
        }
        return f;
    }

    static float EffectiveGlobValue(RecordSpec s, BuildOptions opts) => s.Edid switch
    {
        "FO4SF_RadsRule" => opts.DefaultRadsRule,
        "FO4SF_HardcoreEnabled" => opts.DefaultHardcore,
        "FO4SF_HardcoreFastTravelBlocked" => opts.DefaultHardcore,
        "FO4SF_TestModeEnabled" => opts.TestMode,
        _ => s.Default,
    };

    static void RefuseForbiddenOutDir(string outDir)
    {
        var full = Path.GetFullPath(outDir);
        for (var cur = new DirectoryInfo(full); cur != null; cur = cur.Parent)
        {
            if (Directory.Exists(Path.Combine(cur.FullName, ".git")) || File.Exists(Path.Combine(cur.FullName, ".git")))
                throw new Refusal($"output folder inside Git worktree is forbidden: {full}");
            if (File.Exists(Path.Combine(cur.FullName, "Starfield.exe")))
                throw new Refusal($"output folder inside game install is forbidden: {full}");
        }
    }

    static void WriteMod(StarfieldMod mod, ModKey pluginKey, string outDir)
    {
        RefuseForbiddenOutDir(outDir);
        Directory.CreateDirectory(outDir);
        var finalPath = Path.Combine(outDir, pluginKey.FileName);
        var tmpDir = Path.Combine(outDir, ".tmp-" + Guid.NewGuid().ToString("N"));
        try
        {
            Directory.CreateDirectory(tmpDir);
            var tmpPath = Path.Combine(tmpDir, pluginKey.FileName);
            var masters = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
            masters.Set(new KeyedMasterStyle(SfEsm, MasterStyle.Full));
            mod.WriteToBinary(tmpPath, new BinaryWriteParameters
            {
                ModKey = ModKeyOption.NoCheck,
                MastersListOrdering = new MastersListOrderingByLoadOrder(new[] { SfEsm }),
                MasterFlagsLookup = masters,
            });
            File.Move(tmpPath, finalPath, overwrite: true);
        }
        finally
        {
            if (Directory.Exists(tmpDir)) Directory.Delete(tmpDir, recursive: true);
        }
    }

    public static int Build(string sfPath, string outDir, BuildOptions opts)
    {
        var (pluginKey, nextId, specs) = LoadSchema(opts.JsonPath);
        using var sf = OpenMod(sfPath);
        var healthHits = sf.ActorValueInformation.Where(a => string.Equals(a.EditorID, "Health", StringComparison.OrdinalIgnoreCase)).ToList();
        if (healthHits.Count != 1 || healthHits[0].FormKey.ModKey != SfEsm)
            throw new Refusal("Starfield.esm must own exactly one Health AVIF");
        var healthKey = healthHits[0].FormKey;

        // Optional aid/mgef template from Starfield.esm (falls back cleanly on synthetic fixtures)
        var mgefs = sf.MagicEffects.ToDictionary(m => m.FormKey);
        IIngestibleGetter? aidTpl = null;
        IMagicEffectGetter? mgefTpl = null;
        IEffectGetter? entryTpl = null;
        foreach (var i in sf.Ingestibles.Where(i => i.Effects.Count == 1 && i.Addiction.IsNull).OrderBy(i => i.FormKey.ID))
        {
            if (i.Effects[0].BaseEffect.FormKey is { } fk && mgefs.TryGetValue(fk, out var m) &&
                m.Archetype.Type == MagicEffectArchetype.TypeEnum.ValueModifier && m.SecondActorValue.FormKey == healthKey &&
                !m.Flags.HasFlag(MagicEffect.Flag.Detrimental) && i.Effects[0].Data?.Duration == 0)
            {
                aidTpl = i;
                mgefTpl = m;
                entryTpl = i.Effects[0];
                break;
            }
        }

        var mod = new StarfieldMod(pluginKey, Release);
        mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        mod.ModHeader.Author = "fo4-to-starfield CoreValues";

        var byEdid = new Dictionary<string, FormKey>(StringComparer.OrdinalIgnoreCase);

        // Pass 1: AVIF, GLOB, MGEF
        foreach (var s in specs.Where(x => x.Type is "AVIF" or "GLOB" or "MGEF"))
        {
            var fk = new FormKey(pluginKey, s.Id);
            byEdid[s.Edid] = fk;
            if (s.Type == "AVIF")
            {
                mod.ActorValueInformation.Add(new ActorValueInformation(fk, Release)
                {
                    EditorID = s.Edid,
                    Name = s.Name,
                    Abbreviation = s.Abbr,
                    Type = ActorValueInformation.Types.Variable,
                    DefaultValue = s.Default,
                    Min = s.Min,
                    Max = s.Max,
                    Flags = ParseAvifFlags(s.Flags),
                });
            }
            else if (s.Type == "GLOB")
            {
                var g = new Global(fk, Release)
                {
                    EditorID = s.Edid,
                    Data = EffectiveGlobValue(s, opts),
                };
                if (s.Constant) g.MajorFlags |= Global.MajorFlag.Constant;
                mod.Globals.Add(g);
            }
            else if (s.Type == "MGEF")
            {
                MagicEffect e;
                if (mgefTpl != null)
                {
                    e = (MagicEffect)mgefTpl.Duplicate(fk, new MagicEffect.TranslationMask(defaultOn: true));
                    e.EditorID = s.Edid;
                    e.Name = s.Name;
                    e.Description = s.Desc;
                    e.Archetype = new MagicEffectArchetype(MagicEffectArchetype.TypeEnum.ValueModifier);
                    e.VirtualMachineAdapter = null;
                    e.Conditions.Clear();
                    e.Keywords = null;
                    e.MagicSkill.SetToNull();
                    e.ResistValue.SetToNull();
                    e.SecondActorValue.SetTo(healthKey);
                    e.ThirdActorValue.SetToNull();
                    e.CounterEffects.Clear();
                    e.CastType = CastType.FireAndForget;
                    e.TargetType = TargetType.Self;
                    e.Flags = (e.Flags & ~MagicEffect.Flag.Detrimental) | MagicEffect.Flag.NoDuration | MagicEffect.Flag.HideInUI;
                }
                else
                {
                    e = new MagicEffect(fk, Release)
                    {
                        EditorID = s.Edid,
                        Name = s.Name,
                        Description = s.Desc,
                        Archetype = new MagicEffectArchetype(MagicEffectArchetype.TypeEnum.ValueModifier),
                        CastType = CastType.FireAndForget,
                        TargetType = TargetType.Self,
                        Flags = MagicEffect.Flag.NoDuration | MagicEffect.Flag.NoArea | MagicEffect.Flag.HideInUI,
                    };
                    e.SecondActorValue.SetTo(healthKey);
                }
                mod.MagicEffects.Add(e);
            }
        }

        // Pass 2: FLST and ALCH
        foreach (var s in specs.Where(x => x.Type is "FLST" or "ALCH"))
        {
            var fk = new FormKey(pluginKey, s.Id);
            byEdid[s.Edid] = fk;
            if (s.Type == "FLST")
            {
                var flst = new FormList(fk, Release) { EditorID = s.Edid };
                foreach (var itemEdid in s.Items)
                {
                    if (!byEdid.TryGetValue(itemEdid, out var itemFk))
                        throw new Refusal($"FLST {s.Edid} references unknown item {itemEdid}");
                    flst.Items.Add(new FormLink<IStarfieldMajorRecordGetter>(itemFk));
                }
                mod.FormLists.Add(flst);
            }
            else if (s.Type == "ALCH")
            {
                if (!byEdid.TryGetValue(s.Effect, out var effFk))
                    throw new Refusal($"ALCH {s.Edid} references unknown effect {s.Effect}");
                Ingestible item;
                if (aidTpl != null)
                {
                    item = (Ingestible)aidTpl.Duplicate(fk, new Ingestible.TranslationMask(defaultOn: true));
                    item.EditorID = s.Edid;
                    item.Name = s.Name;
                    item.Description = s.Desc;
                    item.VirtualMachineAdapter = null;
                    item.Keywords = null;
                    item.Addiction.SetToNull();
                    item.AddictionChance = 0f;
                    item.AddictionName = null;
                    item.Flags |= Ingestible.Flag.Medicine;
                    item.MajorFlags |= Ingestible.MajorFlag.Medicine;
                    item.Effects.Clear();
                }
                else
                {
                    item = new Ingestible(fk, Release)
                    {
                        EditorID = s.Edid,
                        Name = s.Name,
                        Description = s.Desc,
                        Weight = 0.1f,
                        Value = 75,
                        Flags = Ingestible.Flag.Medicine,
                        MajorFlags = Ingestible.MajorFlag.Medicine,
                    };
                }
                item.Effects.Add(new Effect
                {
                    BaseEffect = new FormLinkNullable<IMagicEffectGetter>(effFk),
                    Data = new EffectData { Magnitude = 0f, Area = 0, Duration = 0 },
                    MAGF = entryTpl?.MAGF,
                    EFIF = entryTpl?.EFIF,
                    MUID = entryTpl?.MUID,
                });
                mod.Ingestibles.Add(item);
            }
        }

        // Pass 3 (D7a): Clear Commonwealth Weather & Blue-Sky Atmosphere overrides in FO4SFCoreValues.esm.
        // FO4Core_Commonwealth (WRLD 0x01000803) inherits BIOM 0x002A3777 DesertRockyNoLifeMars -> CLMT 0x00310DB1 ClimateUniqueCydonia
        // and MarsPlanetData (PNDT 0x0003F59A) embeds ATMO 0x0000C9D2 ATMO_Mars. Override both when present in Starfield.esm
        // and --commonwealth-weather 1 (default), keeping minimal synthetic Fixture() builds byte-identical.
        int clmtOverrides = 0;
        int atmoOverrides = 0;
        if (opts.CommonwealthWeather != 0)
        {
            var sfClimates = sf.Climates.ToDictionary(c => c.FormKey);
            if (sfClimates.TryGetValue(ClimateNewAtlantisKey, out var naClmt))
            {
                foreach (var targetKey in new[] { ClimateCydoniaKey, ClimateCydoniaFrozenKey })
                {
                    if (!sfClimates.TryGetValue(targetKey, out var srcClmt))
                        continue;
                    var ov = srcClmt.DeepCopy();
                    ov.Weathers = naClmt.Weathers?.Select(wt => wt.DeepCopy()).ToExtendedList();
                    ov.WeatherSettings = new ExtendedList<ClimateWeatherSettings>
                    {
                        new ClimateWeatherSettings
                        {
                            Settings = new FormLink<IWeatherSettingGetter>(WeatherNAClearKey),
                            Chance = 60,
                        },
                        new ClimateWeatherSettings
                        {
                            Settings = new FormLink<IWeatherSettingGetter>(WeatherNAPartlyCloudyKey),
                            Chance = 40,
                        },
                    };
                    mod.Climates.Add(ov);
                    clmtOverrides++;
                }
            }

            var sfAtmos = sf.Atmospheres.ToDictionary(a => a.FormKey);
            if (sfAtmos.TryGetValue(AtmoMarsKey, out var marsAtmo) && sfAtmos.TryGetValue(AtmoJemisonKey, out var jemAtmo))
            {
                var ovAtmo = (Atmosphere)jemAtmo.Duplicate(AtmoMarsKey);
                ovAtmo.EditorID = marsAtmo.EditorID;
                mod.Atmospheres.Add(ovAtmo);
                atmoOverrides++;
            }
        }

        mod.ModHeader.Stats.NextFormID = nextId;
        if (!mod.ModHeader.MasterReferences.Any(m => m.Master == SfEsm))
            mod.ModHeader.MasterReferences.Add(new MasterReference { Master = SfEsm });

        WriteMod(mod, pluginKey, outDir);
        var outPath = Path.Combine(outDir, pluginKey.FileName);
        Console.WriteLine($"wrote {outPath} ({new FileInfo(outPath).Length:N0} bytes): " +
                          $"{mod.ActorValueInformation.Count} AVIF, {mod.Globals.Count} GLOB, " +
                          $"{mod.FormLists.Count} FLST, {mod.MagicEffects.Count} MGEF, {mod.Ingestibles.Count} ALCH" +
                          (clmtOverrides > 0 || atmoOverrides > 0 ? $", {clmtOverrides} CLMT, {atmoOverrides} ATMO" : ""));
        return 0;
    }

    public static int Check(string pluginPath, string sfPath, BuildOptions opts)
    {
        var (pluginKey, nextId, specs) = LoadSchema(opts.JsonPath);
        if (!File.Exists(pluginPath)) throw new Refusal($"missing plugin: {pluginPath}");
        using var sf = OpenMod(sfPath);
        using var plug = OpenMod(pluginPath);

        var problems = new List<string>();
        void Need(bool ok, string why) { if (!ok) problems.Add(why); }

        Need(plug.ModKey == pluginKey, $"ModKey {plug.ModKey} != {pluginKey}");
        Need(plug.ModHeader.Flags.HasFlag(StarfieldModHeader.HeaderFlag.Master), "missing Master flag");
        var masters = plug.ModHeader.MasterReferences.Select(m => m.Master.FileName.String).ToList();
        Need(masters.SequenceEqual(new[] { "Starfield.esm" }), $"masters [{string.Join(", ", masters)}] != [Starfield.esm]");
        Need(plug.ModHeader.Stats.NextFormID == nextId, $"NextFormID 0x{plug.ModHeader.Stats.NextFormID:X} != 0x{nextId:X}");

        var sfClimateKeys = sf.Climates.Select(c => c.FormKey).ToHashSet();
        var sfAtmoKeys = sf.Atmospheres.Select(a => a.FormKey).ToHashSet();
        int expectClmt = (opts.CommonwealthWeather != 0 && sfClimateKeys.Contains(ClimateNewAtlantisKey))
            ? (sfClimateKeys.Contains(ClimateCydoniaKey) ? 1 : 0) + (sfClimateKeys.Contains(ClimateCydoniaFrozenKey) ? 1 : 0)
            : 0;
        int expectAtmo = (opts.CommonwealthWeather != 0 && sfAtmoKeys.Contains(AtmoMarsKey) && sfAtmoKeys.Contains(AtmoJemisonKey)) ? 1 : 0;

        Need(plug.EnumerateMajorRecords().All(r =>
            r.FormKey.ModKey == pluginKey ||
            (opts.CommonwealthWeather != 0 && AllowedWeatherOverrideKeys.Contains(r.FormKey))),
            "contains unexpected foreign record override");

        Need(plug.Climates.Count == expectClmt, $"CLMT override count {plug.Climates.Count} != {expectClmt}");
        Need(plug.Atmospheres.Count == expectAtmo, $"ATMO override count {plug.Atmospheres.Count} != {expectAtmo}");
        foreach (var clmt in plug.Climates)
        {
            var wslt = clmt.WeatherSettings?.Select(w => (w.Settings.FormKey, w.Chance)).ToList() ?? new();
            Need(wslt.Count == 2 &&
                 wslt[0].FormKey == WeatherNAClearKey && wslt[0].Chance == 60 &&
                 wslt[1].FormKey == WeatherNAPartlyCloudyKey && wslt[1].Chance == 40,
                 $"CLMT {clmt.FormKey} ({clmt.EditorID}) does not match clear New Atlantis weather weights (60/40)");
        }
        if (expectAtmo == 1)
        {
            var ovAtmo = plug.Atmospheres.FirstOrDefault(a => a.FormKey == AtmoMarsKey);
            Need(ovAtmo != null && ovAtmo.EditorID == "ATMO_Mars", "ATMO_Mars (0x0000C9D2) override mismatch");
        }

        foreach (var s in specs)
        {
            var fk = new FormKey(pluginKey, s.Id);
            if (s.Type == "AVIF")
            {
                var r = plug.ActorValueInformation.FirstOrDefault(x => x.FormKey == fk);
                Need(r != null && r.EditorID == s.Edid && r.Type == ActorValueInformation.Types.Variable &&
                     r.DefaultValue.HasValue && MathF.Abs(r.DefaultValue.Value - s.Default) < 1e-4f &&
                     r.Min.HasValue && MathF.Abs(r.Min.Value - s.Min) < 1e-4f &&
                     r.Max.HasValue && MathF.Abs(r.Max.Value - s.Max) < 1e-4f && r.Flags == ParseAvifFlags(s.Flags),
                     $"AVIF 0x{s.Id:X} {s.Edid} mismatch");
            }
            else if (s.Type == "GLOB")
            {
                var r = plug.Globals.FirstOrDefault(x => x.FormKey == fk);
                float want = EffectiveGlobValue(s, opts);
                Need(r != null && r.EditorID == s.Edid && r.Data.HasValue && MathF.Abs(r.Data.Value - want) < 1e-4f &&
                     r.MajorFlags.HasFlag(Global.MajorFlag.Constant) == s.Constant,
                     $"GLOB 0x{s.Id:X} {s.Edid} mismatch (want {want}, constant={s.Constant})");
            }
            else if (s.Type == "FLST")
            {
                var r = plug.FormLists.FirstOrDefault(x => x.FormKey == fk);
                var wantIds = s.Items.Select(ed => specs.First(x => x.Edid == ed).Id).ToList();
                var gotIds = r?.Items.Select(i => i.FormKey.ID).ToList() ?? new List<uint>();
                Need(r != null && r.EditorID == s.Edid && gotIds.SequenceEqual(wantIds),
                     $"FLST 0x{s.Id:X} {s.Edid} mismatch");
            }
            else if (s.Type == "MGEF")
            {
                var r = plug.MagicEffects.FirstOrDefault(x => x.FormKey == fk);
                Need(r != null && r.EditorID == s.Edid, $"MGEF 0x{s.Id:X} {s.Edid} mismatch");
            }
            else if (s.Type == "ALCH")
            {
                var r = plug.Ingestibles.FirstOrDefault(x => x.FormKey == fk);
                var effId = specs.First(x => x.Edid == s.Effect).Id;
                Need(r != null && r.EditorID == s.Edid && r.Flags.HasFlag(Ingestible.Flag.Medicine) &&
                     r.Effects.Count == 1 && r.Effects[0].BaseEffect.FormKey == new FormKey(pluginKey, effId),
                     $"ALCH 0x{s.Id:X} {s.Edid} mismatch");
            }
        }

        Need(plug.ActorValueInformation.Count == specs.Count(x => x.Type == "AVIF"), "unexpected AVIF count");
        Need(plug.Globals.Count == specs.Count(x => x.Type == "GLOB"), "unexpected GLOB count");
        Need(plug.FormLists.Count == specs.Count(x => x.Type == "FLST"), "unexpected FLST count");
        Need(plug.MagicEffects.Count == specs.Count(x => x.Type == "MGEF"), "unexpected MGEF count");
        Need(plug.Ingestibles.Count == specs.Count(x => x.Type == "ALCH"), "unexpected ALCH count");

        if (problems.Count > 0)
            throw new Refusal(string.Join("; ", problems));
        Console.WriteLine($"check ok: {pluginKey} ({plug.ActorValueInformation.Count} AVIF, {plug.Globals.Count} GLOB, " +
                          $"{plug.FormLists.Count} FLST, {plug.MagicEffects.Count} MGEF, {plug.Ingestibles.Count} ALCH" +
                          (plug.Climates.Count > 0 || plug.Atmospheres.Count > 0
                              ? $", {plug.Climates.Count} CLMT, {plug.Atmospheres.Count} ATMO"
                              : "") + ")");
        return 0;
    }

    public static int Fixture(string outDir)
    {
        var sf = new StarfieldMod(SfEsm, Release);
        sf.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        var health = new ActorValueInformation(new FormKey(SfEsm, 0x000801), Release)
        {
            EditorID = "Health", Name = "Health", Type = ActorValueInformation.Types.Variable,
        };
        sf.ActorValueInformation.Add(health);
        var mgef = new MagicEffect(new FormKey(SfEsm, 0x000900), Release)
        {
            EditorID = "AbRestoreHealth", Name = "Restore Health",
            Archetype = new MagicEffectArchetype(MagicEffectArchetype.TypeEnum.ValueModifier),
            CastType = CastType.FireAndForget, TargetType = TargetType.Self,
        };
        mgef.SecondActorValue.SetTo(health.FormKey);
        sf.MagicEffects.Add(mgef);
        var aid = new Ingestible(new FormKey(SfEsm, 0x00ABF9), Release)
        {
            EditorID = "MedPack", Name = "Med Pack", Flags = Ingestible.Flag.Medicine, MajorFlags = Ingestible.MajorFlag.Medicine,
        };
        aid.Effects.Add(new Effect
        {
            BaseEffect = new FormLinkNullable<IMagicEffectGetter>(mgef.FormKey),
            Data = new EffectData { Magnitude = 25f, Area = 0, Duration = 0 },
        });
        sf.Ingestibles.Add(aid);
        WriteMod(sf, SfEsm, outDir);
        return 0;
    }

    public static int SelfTest(string scratchDir)
    {
        if (Directory.Exists(scratchDir)) Directory.Delete(scratchDir, recursive: true);
        Directory.CreateDirectory(scratchDir);
        var fixDir = Path.Combine(scratchDir, "fixture");
        Fixture(fixDir);
        var sfPath = Path.Combine(fixDir, "Starfield.esm");
        var jsonPath = DefaultJsonPath();

        var defOpts = new BuildOptions(jsonPath, 0, 0, 0);
        var outDef = Path.Combine(scratchDir, "default");
        Build(sfPath, outDef, defOpts);
        var plugDef = Path.Combine(outDef, "FO4SFCoreValues.esm");
        Check(plugDef, sfPath, defOpts);

        // Byte-identical determinism check
        var outDef2 = Path.Combine(scratchDir, "default2");
        Build(sfPath, outDef2, defOpts);
        if (!File.ReadAllBytes(plugDef).SequenceEqual(File.ReadAllBytes(Path.Combine(outDef2, "FO4SFCoreValues.esm"))))
            throw new Refusal("FO4SFCoreValues.esm build is not byte-identical");

        // Option variants must validate against their own options and reject mismatched options
        var altOpts = new BuildOptions(jsonPath, 1, 1, 1);
        var outAlt = Path.Combine(scratchDir, "alt");
        Build(sfPath, outAlt, altOpts);
        Check(Path.Combine(outAlt, "FO4SFCoreValues.esm"), sfPath, altOpts);

        bool rejected = false;
        try { Check(Path.Combine(outAlt, "FO4SFCoreValues.esm"), sfPath, defOpts); }
        catch (Refusal) { rejected = true; }
        if (!rejected) throw new Refusal("Check accepted mismatched FO4SF_TestModeEnabled/Hardcore/RadsRule globals");

        // Tamper check: moving FO4SF_Rads off 0x800 must fail
        var tamperedMod = StarfieldMod.CreateFromBinary(plugDef, Release, new BinaryReadParameters
        {
            MasterFlagsLookup = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey) { new KeyedMasterStyle(SfEsm, MasterStyle.Full) }
        });
        tamperedMod.ActorValueInformation.First(a => a.FormKey.ID == 0x800).EditorID = "FO4SF_RadsMoved";
        var outTamper = Path.Combine(scratchDir, "tamper");
        WriteMod(tamperedMod, ModKey.FromFileName("FO4SFCoreValues.esm"), outTamper);
        rejected = false;
        try { Check(Path.Combine(outTamper, "FO4SFCoreValues.esm"), sfPath, defOpts); }
        catch (Refusal) { rejected = true; }
        if (!rejected) throw new Refusal("Check accepted tampered FO4SF_Rads EditorID at 0x800");

        // D7(a) weather + atmosphere override selftest on a synthetic Starfield.esm fixture containing Mars/NewAtlantis CLMT & ATMO
        var wFixDir = Path.Combine(scratchDir, "weather_fixture");
        var wSf = StarfieldMod.CreateFromBinary(sfPath, Release, new BinaryReadParameters
        {
            MasterFlagsLookup = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey) { new KeyedMasterStyle(SfEsm, MasterStyle.Full) }
        });
        wSf.Climates.Add(new Climate(ClimateNewAtlantisKey, Release) { EditorID = "ClimateUniqueNewAtlantis" });
        wSf.Climates.Add(new Climate(ClimateCydoniaKey, Release) { EditorID = "ClimateUniqueCydonia" });
        wSf.Climates.Add(new Climate(ClimateCydoniaFrozenKey, Release) { EditorID = "ClimateUniqueCydoniaFrozen" });
        wSf.Atmospheres.Add(new Atmosphere(AtmoJemisonKey, Release) { EditorID = "ATMO_Jemison" });
        wSf.Atmospheres.Add(new Atmosphere(AtmoMarsKey, Release) { EditorID = "ATMO_Mars" });
        WriteMod(wSf, SfEsm, wFixDir);
        var wSfPath = Path.Combine(wFixDir, "Starfield.esm");

        var wOnOpts = new BuildOptions(jsonPath, 0, 0, 0, 1);
        var wOffOpts = new BuildOptions(jsonPath, 0, 0, 0, 0);
        var outWOn = Path.Combine(scratchDir, "weather_on");
        var outWOn2 = Path.Combine(scratchDir, "weather_on2");
        var outWOff = Path.Combine(scratchDir, "weather_off");
        Build(wSfPath, outWOn, wOnOpts);
        Check(Path.Combine(outWOn, "FO4SFCoreValues.esm"), wSfPath, wOnOpts);
        Build(wSfPath, outWOn2, wOnOpts);
        if (!File.ReadAllBytes(Path.Combine(outWOn, "FO4SFCoreValues.esm"))
                 .SequenceEqual(File.ReadAllBytes(Path.Combine(outWOn2, "FO4SFCoreValues.esm"))))
            throw new Refusal("FO4SFCoreValues.esm weather override build is not byte-identical");
        Build(wSfPath, outWOff, wOffOpts);
        Check(Path.Combine(outWOff, "FO4SFCoreValues.esm"), wSfPath, wOffOpts);

        rejected = false;
        try { Check(Path.Combine(outWOn, "FO4SFCoreValues.esm"), wSfPath, wOffOpts); }
        catch (Refusal) { rejected = true; }
        if (!rejected) throw new Refusal("Check accepted weather overrides when --commonwealth-weather 0");

        Console.WriteLine("CoreValues selftest: ok");
        return 0;
    }
}
