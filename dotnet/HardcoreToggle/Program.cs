// HardcoreToggle: GPOF gameplay option & survival toggle writer and checker (docs/survival/hardcore-toggle.md).
//
// Writes FO4SFHardcore.esm (mastered on Starfield.esm only; adds records, overrides none — SQ_ENV 0x248D20 is untouched):
//   0x800 GPOF FO4SF_GPO_Hardcore             GameplayOption (0 = Off, 1 = On) toggling meters, ammo weight, and stimpak HoT
//   0x801 GPOG FO4SF_GPOG_Hardcore            GameplayOptionsGroup listing FO4SF_GPO_Hardcore in Settings -> Gameplay Options
//   0x802 GLOB FO4SF_HardcoreEnabled          0 = OFF (default), 1 = ON (synced with FO4SF_GPO_Hardcore)
//   0x803 AVIF FO4SF_Hunger                   0..1000, DefaultToZero | DamageIsPositive
//   0x804 AVIF FO4SF_Thirst                   0..1000, DefaultToZero | DamageIsPositive
//   0x805 AVIF FO4SF_SleepDeprivation         0..1000, DefaultToZero | DamageIsPositive
//   0x806 AVIF FO4SF_AmmoWeightBurden         0..10000, DefaultToZero (active carried ammo weight when Hardcore is ON)
//   0x807 GLOB FO4SF_HungerStage              0..5 sickness tier (Fed, Peckish, Hungry, Famished, Ravenous, Starving)
//   0x808 GLOB FO4SF_ThirstStage              0..5 sickness tier (Hydrated, Parched, Thirsty, Dehydrated, Critical, Desiccation)
//   0x809 GLOB FO4SF_SleepStage               0..5 sickness tier (Rested, Tired, Weary, Exhausted, Deprived, Collapse)
//   0x80A GLOB FO4SF_HardcoreFastTravelBlocked 0 = allowed, 1 = blocked when Hardcore is ON
//   0x810 MGEF FO4SF_HungerReliefEffect       ValueModifier effect associated with FO4SF_Hunger
//   0x811 MGEF FO4SF_ThirstReliefEffect       ValueModifier effect associated with FO4SF_Thirst
//   0x812 MGEF FO4SF_StimpakTriggerEffect     Medicine trigger effect for FO4SF_Stimpak
//   0x820 ALCH FO4SF_RationFood               Food ingestible (-250 FO4SF_Hunger)
//   0x821 ALCH FO4SF_PurifiedWater            Drink ingestible (-250 FO4SF_Thirst)
//   0x822 ALCH FO4SF_Stimpak                  Medicine ingestible (OFF: +60 instant HP; ON: +10 HP/s x 6 s heal-over-time)
//   0x825 AMMO FO4SF_CaliberLight             0.0 base weight; 0.025 lb/round when Hardcore is ON
//   0x826 AMMO FO4SF_CaliberRifle             0.0 base weight; 0.050 lb/round when Hardcore is ON
//   0x827 AMMO FO4SF_CaliberHeavy             0.0 base weight; 0.100 lb/round when Hardcore is ON
//   0x828 FLST FO4SF_WeightedAmmoList         FormList [CaliberLight, CaliberRifle, CaliberHeavy, ...vanilla AMMO forms]
//   0x830 QUST FO4SF_HardcoreQuest            StartGameEnabled quest driving live GPOF sync, meters, ammo weight, stimpak HoT, & stages
//
// usage:
//   HardcoreToggle build <Starfield.esm> <out dir> [--default-hardcore 0|1]
//   HardcoreToggle check <plugin> <Starfield.esm> [--default-hardcore 0|1]
//   HardcoreToggle fixture <out dir>
//   HardcoreToggle selftest <scratch dir>

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
    int defaultHardcore = 0;
    string? jsonPath = null;

    int idx = rest.IndexOf("--default-hardcore");
    if (idx >= 0)
    {
        if (idx + 1 >= rest.Count || !int.TryParse(rest[idx + 1], NumberStyles.Integer, CultureInfo.InvariantCulture, out int v) || (v != 0 && v != 1))
            throw new HardcoreToggle.Refusal("--default-hardcore must be 0 or 1");
        defaultHardcore = v;
        rest.RemoveRange(idx, 2);
    }
    int jIdx = rest.IndexOf("--json");
    if (jIdx >= 0)
    {
        if (jIdx + 1 >= rest.Count) throw new HardcoreToggle.Refusal("--json needs a path");
        jsonPath = rest[jIdx + 1];
        rest.RemoveRange(jIdx, 2);
    }

    if (rest.Count == 3 && rest[0] == "build") return HardcoreToggle.Build(rest[1], rest[2], defaultHardcore, jsonPath);
    if (rest.Count == 3 && rest[0] == "check") return HardcoreToggle.Check(rest[1], rest[2], defaultHardcore, jsonPath);
    if (rest.Count == 2 && rest[0] == "fixture") return HardcoreToggle.Fixture(rest[1]);
    if (rest.Count == 2 && rest[0] == "selftest") return HardcoreToggle.SelfTest(rest[1]);
}
catch (HardcoreToggle.Refusal r)
{
    Console.Error.WriteLine("refused: " + r.Message);
    return 1;
}

Console.Error.WriteLine("usage: HardcoreToggle build <Starfield.esm> <out dir> [--json <path>] [--default-hardcore 0|1] | " +
                        "check <plugin> <Starfield.esm> [--json <path>] [--default-hardcore 0|1] | fixture <out dir> | selftest <scratch dir>");
return 2;

public static class HardcoreToggle
{
    public class Refusal(string m) : Exception(m);

    const StarfieldRelease Release = StarfieldRelease.Starfield;
    static readonly ModKey SfEsm = ModKey.FromFileName("Starfield.esm");
    public static readonly ModKey CoreValuesEsm = ModKey.FromFileName("FO4SFCoreValues.esm");
    public static readonly ModKey Plugin = ModKey.FromFileName("FO4SFHardcore.esm");

    // Vanilla SQ_ENV FormID in Starfield.esm — verified never overridden by Check()
    public const uint VanillaSqEnvId = 0x248D20;

    // Deterministic local FormIDs owned by FO4SFHardcore.esm (shared meters/stages/stimpak/test-mode live in FO4SFCoreValues.esm)
    public const uint HardcoreGpoId = 0x800;
    public const uint HardcoreGpogId = 0x801;
    public const uint AmmoBurdenAvifId = 0x806;

    public const uint HungerReliefEffectId = 0x810;
    public const uint ThirstReliefEffectId = 0x811;

    public const uint RationFoodId = 0x820;
    public const uint PurifiedWaterId = 0x821;

    public const uint CaliberLightId = 0x825;
    public const uint CaliberRifleId = 0x826;
    public const uint CaliberHeavyId = 0x827;
    public const uint WeightedAmmoFlstId = 0x828;

    public const uint QuestId = 0x830;
    public const uint NextId = 0x831;

    // EditorIDs (local + shared FO4SFCoreValues.esm lookup keys)
    public const string HardcoreGpoEdid = "FO4SF_GPO_Hardcore";
    public const string HardcoreGpogEdid = "FO4SF_GPOG_Hardcore";
    public const string HardcoreGlobEdid = "FO4SF_HardcoreEnabled";
    public const string HungerAvifEdid = "FO4SF_Hunger";
    public const string ThirstAvifEdid = "FO4SF_Thirst";
    public const string SleepAvifEdid = "FO4SF_SleepDeprivation";
    public const string AmmoBurdenAvifEdid = "FO4SF_AmmoWeightBurden";
    public const string HungerStageGlobEdid = "FO4SF_HungerStage";
    public const string ThirstStageGlobEdid = "FO4SF_ThirstStage";
    public const string SleepStageGlobEdid = "FO4SF_SleepStage";
    public const string FastTravelBlockedGlobEdid = "FO4SF_HardcoreFastTravelBlocked";

    public const string HungerReliefEffectEdid = "FO4SF_HungerReliefEffect";
    public const string ThirstReliefEffectEdid = "FO4SF_ThirstReliefEffect";

    public const string RationFoodEdid = "FO4SF_RationFood";
    public const string PurifiedWaterEdid = "FO4SF_PurifiedWater";
    public const string StimpakEdid = "FO4SF_Stimpak";

    public const string SpecialStrEdid = "FO4SF_Special_Strength";
    public const string SpecialEndEdid = "FO4SF_Special_Endurance";
    public const string SpecialIntEdid = "FO4SF_Special_Intelligence";
    public const string SpecialAgiEdid = "FO4SF_Special_Agility";
    public const string TestModeGlobEdid = "FO4SF_TestModeEnabled";

    public const string CaliberLightEdid = "FO4SF_CaliberLight";
    public const string CaliberRifleEdid = "FO4SF_CaliberRifle";
    public const string CaliberHeavyEdid = "FO4SF_CaliberHeavy";
    public const string WeightedAmmoFlstEdid = "FO4SF_WeightedAmmoList";

    public const string QuestEdid = "FO4SF_HardcoreQuest";
    public const string ScriptName = "FO4SF_HardcoreQuest";

    public const float MeterMax = 1000f;
    public const float AmmoBurdenMax = 10000f;
    public const int MaxVanillaAmmoSample = 12;

    public static readonly ushort[] Stages = { 5, 10, 20, 30, 40, 50 };

    public static readonly string[] RequiredSfAvifs =
    {
        "Health", "CarryWeight"
    };

    // Quest script properties in exact declaration order (pinned by tests/test_hardcore_toggle.py)
    public static readonly string[] PropNames =
    {
        "HardcoreOption",
        "HardcoreEnabledGlobal",
        "FastTravelBlockedGlobal",
        "HungerAV", "ThirstAV", "SleepAV", "AmmoBurdenAV",
        "HungerStageGlobal", "ThirstStageGlobal", "SleepStageGlobal",
        "HealthAV", "CarryWeightAV", "StrengthAV", "EnduranceAV", "AgilityAV", "IntelligenceAV",
        "RationFood", "PurifiedWater", "Stimpak",
        "CaliberLight", "CaliberRifle", "CaliberHeavy",
        "WeightedAmmoList",
        "TestModeGlobal"
    };

    static FormKey Own(uint id) => new(Plugin, id);
    static ActorValueInformation.Flag MeterFlags => ActorValueInformation.Flag.DefaultToZero | ActorValueInformation.Flag.DamageIsPositive;
    static ActorValueInformation.Flag ZeroFlags => ActorValueInformation.Flag.DefaultToZero;

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

    public static Dictionary<string, uint> LoadCoreValues(string? jsonPath = null)
    {
        var path = jsonPath ?? DefaultJsonPath();
        if (!File.Exists(path)) throw new Refusal($"missing core_values.json: {path}");
        using var doc = JsonDocument.Parse(File.ReadAllText(path));
        var root = doc.RootElement;
        var plugin = root.GetProperty("plugin").GetString() ?? throw new Refusal("core_values.json missing plugin");
        if (ModKey.FromFileName(plugin) != CoreValuesEsm)
            throw new Refusal($"core_values.json plugin {plugin} != {CoreValuesEsm}");
        var ids = new Dictionary<string, uint>(StringComparer.Ordinal);
        foreach (var el in root.GetProperty("records").EnumerateArray())
        {
            var edid = el.GetProperty("edid").GetString() ?? throw new Refusal("core_values.json record missing edid");
            var id = Convert.ToUInt32(el.GetProperty("id").GetString()!, 16);
            ids[edid] = id;
        }
        return ids;
    }

    static FormKey Core(IReadOnlyDictionary<string, uint> coreIds, string edid) =>
        coreIds.TryGetValue(edid, out var id) ? new FormKey(CoreValuesEsm, id) : throw new Refusal($"core_values.json missing {edid}");

    static IStarfieldModDisposableGetter OpenMod(string path, params ModKey[] masters)
    {
        var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        foreach (var m in (masters.Length > 0 ? masters : new[] { SfEsm, CoreValuesEsm }))
            styles.Set(new KeyedMasterStyle(m, MasterStyle.Full));
        return StarfieldMod.CreateFromBinaryOverlay(path, Release, new BinaryReadParameters { MasterFlagsLookup = styles });
    }

    static T One<T>(IEnumerable<T> items, string edid, string what) where T : IMajorRecordGetter
    {
        var hits = items.Where(x => string.Equals(x.EditorID, edid, StringComparison.OrdinalIgnoreCase)).ToList();
        if (hits.Count != 1) throw new Refusal($"{hits.Count} {what} named {edid} in Starfield.esm (one needed)");
        return hits[0];
    }

    static (IIngestibleGetter? Aid, IMagicEffectGetter? RestoreMgef, IEffectGetter? RestoreEntry, IAmmunitionGetter? AmmoTpl, string Level)
        FindTemplates(IStarfieldModGetter sf, FormKey healthKey)
    {
        var mgefs = sf.MagicEffects.ToDictionary(m => m.FormKey);
        IIngestibleGetter? aid = null;
        IMagicEffectGetter? restoreMgef = null;
        IEffectGetter? restoreEntry = null;

        var singles = sf.Ingestibles.Where(i => i.Effects.Count == 1 && i.Addiction.IsNull).OrderBy(i => i.FormKey.ID).ToList();
        foreach (var i in singles)
        {
            if (i.Effects[0].BaseEffect.FormKey is { } fk && mgefs.TryGetValue(fk, out var m) &&
                m.Archetype.Type == MagicEffectArchetype.TypeEnum.ValueModifier && m.SecondActorValue.FormKey == healthKey &&
                !m.Flags.HasFlag(MagicEffect.Flag.Detrimental) && i.Effects[0].Data?.Duration == 0)
            {
                aid = i;
                restoreMgef = m;
                restoreEntry = i.Effects[0];
                break;
            }
        }
        if (aid == null)
        {
            aid = singles.FirstOrDefault(i => i.Flags.HasFlag(Ingestible.Flag.Medicine)) ?? singles.FirstOrDefault();
        }
        if (restoreMgef == null)
        {
            restoreMgef = sf.MagicEffects
                .Where(m => m.Archetype.Type == MagicEffectArchetype.TypeEnum.ValueModifier && !m.Flags.HasFlag(MagicEffect.Flag.Detrimental))
                .OrderBy(m => m.FormKey.ID)
                .FirstOrDefault();
        }

        var ammoTpl = sf.Ammunitions.OrderBy(a => a.FormKey.ID).FirstOrDefault();
        string level = (aid != null && restoreMgef != null && ammoTpl != null) ? "preferred" : "fallback";
        return (aid, restoreMgef, restoreEntry, ammoTpl, level);
    }

    static MagicEffect MakeReliefEffect(IMagicEffectGetter? tpl, uint id, string edid, string name, string desc, FormKey av)
    {
        MagicEffect e;
        if (tpl != null)
        {
            e = (MagicEffect)tpl.Duplicate(Own(id), new MagicEffect.TranslationMask(defaultOn: true));
            e.EditorID = edid;
            e.Name = name;
            e.Description = desc;
            e.Archetype = new MagicEffectArchetype(MagicEffectArchetype.TypeEnum.ValueModifier);
            e.VirtualMachineAdapter = null;
            e.Conditions.Clear();
            e.Keywords = null;
            e.MagicSkill.SetToNull();
            e.ResistValue.SetToNull();
            e.SecondActorValue.SetTo(av);
            e.ThirdActorValue.SetToNull();
            e.CounterEffects.Clear();
            e.CastType = CastType.FireAndForget;
            e.TargetType = TargetType.Self;
            e.Flags = (e.Flags & ~MagicEffect.Flag.Detrimental) | MagicEffect.Flag.NoDuration | MagicEffect.Flag.HideInUI;
        }
        else
        {
            e = new MagicEffect(Own(id), Release)
            {
                EditorID = edid, Name = name, Description = desc,
                Archetype = new MagicEffectArchetype(MagicEffectArchetype.TypeEnum.ValueModifier),
                CastType = CastType.FireAndForget, TargetType = TargetType.Self,
                Flags = MagicEffect.Flag.NoDuration | MagicEffect.Flag.NoArea | MagicEffect.Flag.HideInUI,
            };
            e.SecondActorValue.SetTo(av);
        }
        return e;
    }

    static Ingestible MakeAid(IIngestibleGetter? tpl, uint id, string edid, string name, string desc, bool medicine, FormKey effectKey, float mag, IEffectGetter? entryTpl)
    {
        Ingestible item;
        if (tpl != null)
        {
            item = (Ingestible)tpl.Duplicate(Own(id), new Ingestible.TranslationMask(defaultOn: true));
            item.EditorID = edid;
            item.Name = name;
            item.Description = desc;
            item.VirtualMachineAdapter = null;
            item.Keywords = null;
            item.Addiction.SetToNull();
            item.AddictionChance = 0f;
            item.AddictionName = null;
            if (medicine)
            {
                item.Flags |= Ingestible.Flag.Medicine;
                item.MajorFlags |= Ingestible.MajorFlag.Medicine;
            }
            else
            {
                item.Flags = (item.Flags & ~Ingestible.Flag.Medicine) | Ingestible.Flag.FoodItem;
                item.MajorFlags &= ~Ingestible.MajorFlag.Medicine;
            }
            item.Effects.Clear();
        }
        else
        {
            item = new Ingestible(Own(id), Release)
            {
                EditorID = edid, Name = name, Description = desc, Weight = 0.25f, Value = 20,
                Flags = medicine ? Ingestible.Flag.Medicine : Ingestible.Flag.FoodItem,
                MajorFlags = medicine ? Ingestible.MajorFlag.Medicine : 0,
            };
        }
        item.Effects.Add(new Effect
        {
            BaseEffect = new FormLinkNullable<IMagicEffectGetter>(effectKey),
            Data = new EffectData { Magnitude = mag, Area = 0, Duration = 0 },
            MAGF = entryTpl?.MAGF, EFIF = entryTpl?.EFIF, MUID = entryTpl?.MUID,
        });
        return item;
    }

    static Ammunition MakeCaliber(IAmmunitionGetter? tpl, uint id, string edid, string name)
    {
        Ammunition a;
        if (tpl != null)
        {
            a = (Ammunition)tpl.Duplicate(Own(id), new Ammunition.TranslationMask(defaultOn: true));
            a.EditorID = edid;
            a.Name = name;
            a.VirtualMachineAdapter = null;
            a.Weight = 0f; // Base weight stays 0 so OFF = 0 weight and ON applies exact reversible runtime CarryWeight delta
        }
        else
        {
            a = new Ammunition(Own(id), Release)
            {
                EditorID = edid, Name = name, Weight = 0f, Value = 2,
            };
        }
        return a;
    }

    static ScriptObjectProperty ObjProp(string name, FormKey fk) => new()
    {
        Name = name, Flags = ScriptProperty.Flag.Edited, Object = new FormLink<IStarfieldMajorRecordGetter>(fk),
    };

    static void WriteMod(StarfieldMod mod, string outDir)
    {
        Directory.CreateDirectory(outDir);
        var finalPath = Path.Combine(outDir, Plugin.FileName);
        var tmpDir = Path.Combine(outDir, ".tmp-" + Guid.NewGuid().ToString("N"));
        try
        {
            Directory.CreateDirectory(tmpDir);
            var tmpPath = Path.Combine(tmpDir, Plugin.FileName);
            var masters = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
            masters.Set(new KeyedMasterStyle(SfEsm, MasterStyle.Full));
            masters.Set(new KeyedMasterStyle(CoreValuesEsm, MasterStyle.Full));
            mod.WriteToBinary(tmpPath, new BinaryWriteParameters
            {
                ModKey = ModKeyOption.NoCheck,
                MastersListOrdering = new MastersListOrderingByLoadOrder(new[] { SfEsm, CoreValuesEsm }),
                MasterFlagsLookup = masters,
            });
            File.Move(tmpPath, finalPath, overwrite: true);
        }
        finally
        {
            if (Directory.Exists(tmpDir)) Directory.Delete(tmpDir, recursive: true);
        }
    }

    static Dictionary<string, FormKey> ExpectedProperties(
        IReadOnlyDictionary<string, IActorValueInformationGetter> sfAvifs,
        IReadOnlyDictionary<string, uint> coreIds) => new()
    {
        ["HardcoreOption"] = Own(HardcoreGpoId),
        ["HardcoreEnabledGlobal"] = Core(coreIds, HardcoreGlobEdid),
        ["FastTravelBlockedGlobal"] = Core(coreIds, FastTravelBlockedGlobEdid),
        ["HungerAV"] = Core(coreIds, HungerAvifEdid),
        ["ThirstAV"] = Core(coreIds, ThirstAvifEdid),
        ["SleepAV"] = Core(coreIds, SleepAvifEdid),
        ["AmmoBurdenAV"] = Own(AmmoBurdenAvifId),
        ["HungerStageGlobal"] = Core(coreIds, HungerStageGlobEdid),
        ["ThirstStageGlobal"] = Core(coreIds, ThirstStageGlobEdid),
        ["SleepStageGlobal"] = Core(coreIds, SleepStageGlobEdid),
        ["HealthAV"] = sfAvifs["Health"].FormKey,
        ["CarryWeightAV"] = sfAvifs["CarryWeight"].FormKey,
        ["StrengthAV"] = Core(coreIds, SpecialStrEdid),
        ["EnduranceAV"] = Core(coreIds, SpecialEndEdid),
        ["AgilityAV"] = Core(coreIds, SpecialAgiEdid),
        ["IntelligenceAV"] = Core(coreIds, SpecialIntEdid),
        ["RationFood"] = Own(RationFoodId),
        ["PurifiedWater"] = Own(PurifiedWaterId),
        ["Stimpak"] = Core(coreIds, StimpakEdid),
        ["CaliberLight"] = Own(CaliberLightId),
        ["CaliberRifle"] = Own(CaliberRifleId),
        ["CaliberHeavy"] = Own(CaliberHeavyId),
        ["WeightedAmmoList"] = Own(WeightedAmmoFlstId),
        ["TestModeGlobal"] = Core(coreIds, TestModeGlobEdid),
    };

    public static int Build(string sfPath, string outDir, int defaultHardcore, string? jsonPath = null)
    {
        var coreIds = LoadCoreValues(jsonPath);
        using var sf = OpenMod(sfPath, SfEsm);
        var sfAvifs = RequiredSfAvifs.ToDictionary(n => n, n =>
        {
            var av = One(sf.ActorValueInformation, n, "AVIF");
            if (av.FormKey.ModKey != SfEsm) throw new Refusal($"{n} is not owned by Starfield.esm");
            return av;
        });

        var tpl = FindTemplates(sf, sfAvifs["Health"].FormKey);
        string TplStr(IMajorRecordGetter? r) => r == null ? "none" : $"{r.EditorID} {r.FormKey}";
        Console.WriteLine($"templates ({tpl.Level}): ALCH {TplStr(tpl.Aid)}, RestoreMGEF {TplStr(tpl.RestoreMgef)}, AMMO {TplStr(tpl.AmmoTpl)}");

        var mod = new StarfieldMod(Plugin, Release);
        mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        mod.ModHeader.Author = "fo4-to-starfield HardcoreToggle";

        // 1. GPOF + GPOG (shared survival/stimpak/test-mode GLOBs & AVIFs live in FO4SFCoreValues.esm)
        var gpo = new GameplayOption(Own(HardcoreGpoId), Release)
        {
            EditorID = HardcoreGpoEdid,
            Name = "Hardcore Survival Mode",
            Description = "Toggles hunger, thirst, and sleep meters, ammunition weight, and stimpak heal-over-time.",
            Data = new FloatGameplayOptionData
            {
                Value1 = defaultHardcore, Value2 = defaultHardcore, Min = 0f, Max = 1f, Step = 1f,
            },
        };
        gpo.Rewards.Add(new GameplayOptionReward
        {
            SettingValue = 0f, Name = "OFF",
            Description = "{0}: Survival meters disabled, ammunition is weightless, and stimpaks heal instantly.",
            RewardValue = 0f,
        });
        gpo.Rewards.Add(new GameplayOptionReward
        {
            SettingValue = 1f, Name = "ON",
            Description = "{0}: Hunger, thirst, and sleep meters active, ammunition carries weight, and stimpaks heal over time.",
            RewardValue = 0f,
        });
        mod.GameplayOptions.Add(gpo);

        var gpog = new GameplayOptionsGroup(Own(HardcoreGpogId), Release)
        {
            EditorID = HardcoreGpogEdid,
            Name = "Survival & Hardcore Options",
            Options = new GameplayOptionsGroupLeaf
            {
                GameplayOptions = new ExtendedList<IFormLinkGetter<IGameplayOptionGetter>>
                {
                    new FormLink<IGameplayOptionGetter>(gpo.FormKey),
                },
            },
        };
        mod.GameplayOptionsGroups.Add(gpog);

        // 2. Local AVIF (FO4SF_AmmoWeightBurden)
        var ammoBurdenAv = new ActorValueInformation(Own(AmmoBurdenAvifId), Release)
        {
            EditorID = AmmoBurdenAvifEdid, Name = "Ammo Weight Burden", Abbreviation = "AWt",
            Type = ActorValueInformation.Types.Variable, DefaultValue = 0f, Min = 0f, Max = AmmoBurdenMax, Flags = ZeroFlags,
        };
        mod.ActorValueInformation.Add(ammoBurdenAv);

        // 3. Relief MagicEffects targeting FO4SFCoreValues.esm Hunger/Thirst & Aid Ingestibles
        var hungerEff = MakeReliefEffect(tpl.RestoreMgef, HungerReliefEffectId, HungerReliefEffectEdid, "Ration Relief", "Reduces hunger.", Core(coreIds, HungerAvifEdid));
        var thirstEff = MakeReliefEffect(tpl.RestoreMgef, ThirstReliefEffectId, ThirstReliefEffectEdid, "Hydration Relief", "Reduces thirst.", Core(coreIds, ThirstAvifEdid));
        mod.MagicEffects.Add(hungerEff);
        mod.MagicEffects.Add(thirstEff);

        var ration = MakeAid(tpl.Aid, RationFoodId, RationFoodEdid, "Field Ration", "Restores hunger (-250).", false, hungerEff.FormKey, 0f, tpl.RestoreEntry);
        var water = MakeAid(tpl.Aid, PurifiedWaterId, PurifiedWaterEdid, "Purified Water", "Restores thirst (-250).", false, thirstEff.FormKey, 0f, tpl.RestoreEntry);
        mod.Ingestibles.Add(ration);
        mod.Ingestibles.Add(water);

        // 4. Calibers & Weighted Ammo FormList
        var calLight = MakeCaliber(tpl.AmmoTpl, CaliberLightId, CaliberLightEdid, "Caliber Light Round");
        var calRifle = MakeCaliber(tpl.AmmoTpl, CaliberRifleId, CaliberRifleEdid, "Caliber Rifle Round");
        var calHeavy = MakeCaliber(tpl.AmmoTpl, CaliberHeavyId, CaliberHeavyEdid, "Caliber Heavy Round");
        mod.Ammunitions.Add(calLight);
        mod.Ammunitions.Add(calRifle);
        mod.Ammunitions.Add(calHeavy);

        var ammoFlst = new FormList(Own(WeightedAmmoFlstId), Release) { EditorID = WeightedAmmoFlstEdid };
        ammoFlst.Items.Add(new FormLink<IStarfieldMajorRecordGetter>(calLight.FormKey));
        ammoFlst.Items.Add(new FormLink<IStarfieldMajorRecordGetter>(calRifle.FormKey));
        ammoFlst.Items.Add(new FormLink<IStarfieldMajorRecordGetter>(calHeavy.FormKey));
        foreach (var va in sf.Ammunitions.Where(a => a.FormKey.ModKey == SfEsm).OrderBy(a => a.FormKey.ID).Take(MaxVanillaAmmoSample))
        {
            ammoFlst.Items.Add(new FormLink<IStarfieldMajorRecordGetter>(va.FormKey));
        }
        mod.FormLists.Add(ammoFlst);

        // 5. Controller Quest
        var quest = new Quest(Own(QuestId), Release)
        {
            EditorID = QuestEdid, Name = "FO4SF Hardcore & Survival Controller",
            FormVersion = 581, Version2 = 12,
            Data = new QuestData { Flags = Quest.Flag.StartGameEnabled | Quest.Flag.RunOnce, Priority = 45 },
        };
        foreach (var st in Stages) quest.Stages.Add(new QuestStage { Index = st });
        var se = new ScriptEntry { Name = ScriptName, Flags = ScriptEntry.Flag.Local };
        var propMap = ExpectedProperties(sfAvifs, coreIds);
        foreach (var pn in PropNames) se.Properties.Add(ObjProp(pn, propMap[pn]));

        quest.VirtualMachineAdapter = new QuestAdapter
        {
            Version = 6, ObjectFormat = 2, ExtraBindDataVersion = 3,
            Script = new ScriptEntry { Name = "", Flags = ScriptEntry.Flag.Local },
        };
        quest.VirtualMachineAdapter.Scripts.Add(se);
        mod.Quests.Add(quest);

        mod.ModHeader.Stats.NextFormID = NextId;

        WriteMod(mod, outDir);
        var writtenPath = Path.Combine(outDir, Plugin.FileName);
        Console.WriteLine($"wrote {writtenPath} ({new FileInfo(writtenPath).Length:N0} bytes): " +
                          $"1 GPOF, 1 GPOG, 0 GLOB, 1 AVIF, 2 MGEF, 2 ALCH, 3 AMMO, 1 FLST ({ammoFlst.Items.Count} items), 1 QUST ({PropNames.Length} properties); default_hardcore={defaultHardcore}");
        return 0;
    }

    public static int Check(string pluginPath, string sfPath, int defaultHardcore, string? jsonPath = null)
    {
        if (!File.Exists(pluginPath)) throw new Refusal($"missing plugin: {pluginPath}");
        var coreIds = LoadCoreValues(jsonPath);
        using var sf = OpenMod(sfPath, SfEsm);
        var sfAvifs = RequiredSfAvifs.ToDictionary(n => n, n => One(sf.ActorValueInformation, n, "AVIF"));
        using var mod = OpenMod(pluginPath, SfEsm, CoreValuesEsm);

        if (!mod.ModHeader.Flags.HasFlag(StarfieldModHeader.HeaderFlag.Master))
            throw new Refusal("plugin lacks Master header flag");
        var masters = mod.ModHeader.MasterReferences.Select(m => m.Master).ToList();
        if (!masters.SequenceEqual(new[] { SfEsm, CoreValuesEsm }))
            throw new Refusal($"expected masters [Starfield.esm, FO4SFCoreValues.esm], got [{string.Join(", ", masters)}]");

        // Verify zero record overrides of Starfield.esm (including SQ_ENV 0x248D20) and zero duplicate FO4SFCoreValues.esm EditorIDs
        foreach (var rec in mod.EnumerateMajorRecords())
        {
            if (rec.FormKey.ModKey != Plugin)
                throw new Refusal($"plugin overrides foreign record {rec.FormKey} ({rec.EditorID}) — must add records only and never touch SQ_ENV");
            if (rec.FormKey.ID == VanillaSqEnvId)
                throw new Refusal("plugin touches SQ_ENV FormID");
            if (rec.EditorID != null && coreIds.ContainsKey(rec.EditorID))
                throw new Refusal($"plugin duplicates FO4SFCoreValues.esm EditorID {rec.EditorID}");
        }

        if (mod.GameplayOptions.Count != 1) throw new Refusal($"expected 1 GPOF, found {mod.GameplayOptions.Count}");
        var gpo = mod.GameplayOptions.First();
        if (gpo.FormKey != Own(HardcoreGpoId) || gpo.EditorID != HardcoreGpoEdid)
            throw new Refusal($"unexpected GPOF {gpo.FormKey} {gpo.EditorID}");
        if (gpo.Data is not IFloatGameplayOptionDataGetter fgd || Math.Abs((fgd.Value1 ?? -1f) - defaultHardcore) > 0.001f || Math.Abs(fgd.Min) > 0.001f || Math.Abs(fgd.Max - 1f) > 0.001f || Math.Abs(fgd.Step - 1f) > 0.001f)
            throw new Refusal("GPOF FloatGameplayOptionData mismatch");
        if (gpo.Rewards.Count != 2) throw new Refusal($"expected 2 GPOF rewards (OFF/ON), got {gpo.Rewards.Count}");

        if (mod.GameplayOptionsGroups.Count != 1) throw new Refusal($"expected 1 GPOG, found {mod.GameplayOptionsGroups.Count}");
        var gpog = mod.GameplayOptionsGroups.First();
        if (gpog.FormKey != Own(HardcoreGpogId) || gpog.EditorID != HardcoreGpogEdid)
            throw new Refusal("unexpected GPOG id/edid");
        if (gpog.Options is not IGameplayOptionsGroupLeafGetter leaf || leaf.GameplayOptions.Count != 1 || leaf.GameplayOptions[0].FormKey != Own(HardcoreGpoId))
            throw new Refusal("GPOG leaf does not link FO4SF_GPO_Hardcore");

        if (mod.Globals.Count != 0) throw new Refusal($"expected 0 GLOB, found {mod.Globals.Count}");

        if (mod.ActorValueInformation.Count != 1) throw new Refusal($"expected 1 AVIF, found {mod.ActorValueInformation.Count}");
        var ammoAv = mod.ActorValueInformation.FirstOrDefault(a => a.FormKey == Own(AmmoBurdenAvifId)) ?? throw new Refusal($"missing AVIF {AmmoBurdenAvifEdid}");
        if (ammoAv.EditorID != AmmoBurdenAvifEdid || Math.Abs((ammoAv.Max ?? -1f) - AmmoBurdenMax) > 0.01f)
            throw new Refusal($"AVIF {AmmoBurdenAvifEdid} max/edid mismatch");

        if (mod.MagicEffects.Count != 2) throw new Refusal($"expected 2 MGEF, found {mod.MagicEffects.Count}");
        var hEff = mod.MagicEffects.FirstOrDefault(m => m.FormKey == Own(HungerReliefEffectId)) ?? throw new Refusal($"missing MGEF {HungerReliefEffectEdid}");
        var tEff = mod.MagicEffects.FirstOrDefault(m => m.FormKey == Own(ThirstReliefEffectId)) ?? throw new Refusal($"missing MGEF {ThirstReliefEffectEdid}");
        if (hEff.SecondActorValue.FormKey != Core(coreIds, HungerAvifEdid) || tEff.SecondActorValue.FormKey != Core(coreIds, ThirstAvifEdid))
            throw new Refusal("Hunger/Thirst relief MGEFs do not target FO4SFCoreValues.esm 0x842/0x843");

        if (mod.Ingestibles.Count != 2) throw new Refusal($"expected 2 ALCH, found {mod.Ingestibles.Count}");
        if (mod.Ingestibles.FirstOrDefault(i => i.FormKey == Own(RationFoodId))?.EditorID != RationFoodEdid ||
            mod.Ingestibles.FirstOrDefault(i => i.FormKey == Own(PurifiedWaterId))?.EditorID != PurifiedWaterEdid)
            throw new Refusal("missing FO4SF_RationFood or FO4SF_PurifiedWater");

        if (mod.Ammunitions.Count != 3) throw new Refusal($"expected 3 AMMO, found {mod.Ammunitions.Count}");
        foreach (var a in mod.Ammunitions)
        {
            if (Math.Abs(a.Weight) > 0.0001f) throw new Refusal($"AMMO {a.EditorID} base weight must be 0.0 for clean OFF toggle");
        }

        if (mod.FormLists.Count != 1) throw new Refusal($"expected 1 FLST, found {mod.FormLists.Count}");
        var flst = mod.FormLists.First();
        if (flst.Items.Count < 3 || flst.Items[0].FormKey != Own(CaliberLightId) || flst.Items[1].FormKey != Own(CaliberRifleId) || flst.Items[2].FormKey != Own(CaliberHeavyId))
            throw new Refusal("FO4SF_WeightedAmmoList missing leading caliber entries");

        if (mod.Quests.Count != 1) throw new Refusal($"expected 1 QUST, found {mod.Quests.Count}");
        var q = mod.Quests.First();
        if (q.FormKey != Own(QuestId) || q.EditorID != QuestEdid || q.Data == null || !q.Data.Flags.HasFlag(Quest.Flag.StartGameEnabled))
            throw new Refusal("FO4SF_HardcoreQuest flags/id mismatch");
        var qStages = q.Stages.Select(s => s.Index).ToArray();
        if (!qStages.SequenceEqual(Stages))
            throw new Refusal($"quest stages [{string.Join(",", qStages)}] != [{string.Join(",", Stages)}]");
        var scripts = q.VirtualMachineAdapter?.Scripts;
        if (scripts == null || scripts.Count != 1 || scripts[0].Name != ScriptName)
            throw new Refusal("quest script adapter mismatch");
        var actualProps = scripts[0].Properties.Select(p => p.Name).ToArray();
        if (!actualProps.SequenceEqual(PropNames))
            throw new Refusal($"quest properties [{string.Join(",", actualProps)}] != expected [{string.Join(",", PropNames)}]");
        var propTargets = ExpectedProperties(sfAvifs, coreIds);
        var boundMap = scripts[0].Properties.OfType<IScriptObjectPropertyGetter>().ToDictionary(p => p.Name, p => p.Object.FormKey);
        foreach (var (name, wantFk) in propTargets)
        {
            if (!boundMap.TryGetValue(name, out var gotFk) || gotFk != wantFk)
                throw new Refusal($"quest property {name} -> {(boundMap.TryGetValue(name, out var g) ? g.ToString() : "missing")} != {wantFk}");
        }

        Console.WriteLine($"FO4SFHardcore.esm: header Master, masters [Starfield.esm, FO4SFCoreValues.esm], next 0x{mod.ModHeader.Stats.NextFormID:X}, zero foreign overrides (SQ_ENV 0x{VanillaSqEnvId:X6} untouched)");
        Console.WriteLine("all checks pass");
        return 0;
    }

    public static int Fixture(string outDir)
    {
        Directory.CreateDirectory(outDir);
        var sf = new StarfieldMod(SfEsm, Release);
        sf.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;

        uint nextId = 0xA020;
        foreach (var avName in RequiredSfAvifs)
        {
            sf.ActorValueInformation.Add(new ActorValueInformation(new FormKey(SfEsm, nextId++), Release)
            {
                EditorID = avName, Name = avName, Type = ActorValueInformation.Types.Variable, DefaultValue = 100f, Min = 0f, Max = 1000f,
            });
        }
        var healthKey = sf.ActorValueInformation.First(a => a.EditorID == "Health").FormKey;

        var mgef = new MagicEffect(new FormKey(SfEsm, 0xA100), Release)
        {
            EditorID = "SynthRestoreHealthEffect", Name = "Synth Restore",
            Archetype = new MagicEffectArchetype(MagicEffectArchetype.TypeEnum.ValueModifier),
            CastType = CastType.FireAndForget, TargetType = TargetType.Self,
            Flags = MagicEffect.Flag.NoDuration | MagicEffect.Flag.HideInUI,
        };
        mgef.SecondActorValue.SetTo(healthKey);
        sf.MagicEffects.Add(mgef);

        var aid = new Ingestible(new FormKey(SfEsm, 0xA101), Release)
        {
            EditorID = "SynthMedPack", Name = "Synth Med", Weight = 0.1f, Value = 25,
            Flags = Ingestible.Flag.Medicine, MajorFlags = Ingestible.MajorFlag.Medicine,
        };
        aid.Effects.Add(new Effect
        {
            BaseEffect = new FormLinkNullable<IMagicEffectGetter>(mgef.FormKey),
            Data = new EffectData { Magnitude = 25f, Area = 0, Duration = 0 },
        });
        sf.Ingestibles.Add(aid);

        sf.Ammunitions.Add(new Ammunition(new FormKey(SfEsm, 0xA200), Release)
        {
            EditorID = "SynthAmmo762", Name = "Synth 7.62", Weight = 0f, Value = 2,
        });
        sf.Ammunitions.Add(new Ammunition(new FormKey(SfEsm, 0xA201), Release)
        {
            EditorID = "SynthAmmo10mm", Name = "Synth 10mm", Weight = 0f, Value = 1,
        });

        // Include SQ_ENV 0x248D20 in synthetic Starfield.esm so Check() proves we never override it
        sf.Quests.Add(new Quest(new FormKey(SfEsm, VanillaSqEnvId), Release)
        {
            EditorID = "SQ_ENV", Name = "Synthetic Vanilla SQ_ENV",
        });

        var sfPath = Path.Combine(outDir, "Starfield.esm");
        var masters = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        masters.Set(new KeyedMasterStyle(SfEsm, MasterStyle.Full));
        sf.WriteToBinary(sfPath, new BinaryWriteParameters
        {
            ModKey = ModKeyOption.NoCheck,
            MasterFlagsLookup = masters,
        });
        Console.WriteLine($"wrote synthetic fixture {sfPath}");
        return 0;
    }

    public static int SelfTest(string scratchDir)
    {
        Directory.CreateDirectory(scratchDir);
        var fixDir = Path.Combine(scratchDir, "fixture");
        Fixture(fixDir);
        var sfPath = Path.Combine(fixDir, "Starfield.esm");

        foreach (var defVal in new[] { 0, 1 })
        {
            var outDir = Path.Combine(scratchDir, $"out_{defVal}");
            if (Build(sfPath, outDir, defVal) != 0) throw new Refusal($"Build({defVal}) failed");
            var pluginPath = Path.Combine(outDir, Plugin.FileName);
            if (Check(pluginPath, sfPath, defVal) != 0) throw new Refusal($"Check({defVal}) failed");

            // Negative mutation check: wrong expected defaultHardcore must be refused!
            bool refused = false;
            try { Check(pluginPath, sfPath, 1 - defVal); }
            catch (Refusal) { refused = true; }
            if (!refused) throw new Refusal("Check failed to refuse mismatched --default-hardcore");
        }

        // Tamper checks: duplicate CoreValues record or re-pointed relief MGEF must fail Check()
        var goodPlugin = Path.Combine(scratchDir, "out_0", Plugin.FileName);
        void MustRefuse(string label, Action<StarfieldMod> mutate)
        {
            using var ro = OpenMod(goodPlugin, SfEsm, CoreValuesEsm);
            var copy = new StarfieldMod(Plugin, Release);
            copy.DeepCopyIn(ro);
            mutate(copy);
            var badDir = Path.Combine(scratchDir, "bad_" + label);
            WriteMod(copy, badDir);
            bool refused = false;
            try { Check(Path.Combine(badDir, Plugin.FileName), sfPath, 0); }
            catch (Refusal) { refused = true; }
            if (!refused) throw new Refusal($"Check failed to refuse tamper '{label}'");
        }
        MustRefuse("dup_glob", m => m.Globals.Add(new Global(Own(0x802), Release) { EditorID = HardcoreGlobEdid, Data = 0f }));
        MustRefuse("mgef_av", m => m.MagicEffects.First(x => x.FormKey == Own(HungerReliefEffectId)).SecondActorValue.SetTo(Own(AmmoBurdenAvifId)));
        MustRefuse("stimpak_prop", m => ((ScriptObjectProperty)m.Quests.First().VirtualMachineAdapter!.Scripts[0].Properties.First(p => p.Name == "Stimpak")).Object.SetTo(Own(RationFoodId)));
        MustRefuse("testmode_prop", m => ((ScriptObjectProperty)m.Quests.First().VirtualMachineAdapter!.Scripts[0].Properties.First(p => p.Name == "TestModeGlobal")).Object.SetTo(Own(HardcoreGpoId)));

        Console.WriteLine("selftest: ok");
        return 0;
    }
}
