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

    int idx = rest.IndexOf("--default-hardcore");
    if (idx >= 0)
    {
        if (idx + 1 >= rest.Count || !int.TryParse(rest[idx + 1], NumberStyles.Integer, CultureInfo.InvariantCulture, out int v) || (v != 0 && v != 1))
            throw new HardcoreToggle.Refusal("--default-hardcore must be 0 or 1");
        defaultHardcore = v;
        rest.RemoveRange(idx, 2);
    }

    if (rest.Count == 3 && rest[0] == "build") return HardcoreToggle.Build(rest[1], rest[2], defaultHardcore);
    if (rest.Count == 3 && rest[0] == "check") return HardcoreToggle.Check(rest[1], rest[2], defaultHardcore);
    if (rest.Count == 2 && rest[0] == "fixture") return HardcoreToggle.Fixture(rest[1]);
    if (rest.Count == 2 && rest[0] == "selftest") return HardcoreToggle.SelfTest(rest[1]);
}
catch (HardcoreToggle.Refusal r)
{
    Console.Error.WriteLine("refused: " + r.Message);
    return 1;
}

Console.Error.WriteLine("usage: HardcoreToggle build <Starfield.esm> <out dir> [--default-hardcore 0|1] | " +
                        "check <plugin> <Starfield.esm> [--default-hardcore 0|1] | fixture <out dir> | selftest <scratch dir>");
return 2;

public static class HardcoreToggle
{
    public class Refusal(string m) : Exception(m);

    const StarfieldRelease Release = StarfieldRelease.Starfield;
    static readonly ModKey SfEsm = ModKey.FromFileName("Starfield.esm");
    public static readonly ModKey Plugin = ModKey.FromFileName("FO4SFHardcore.esm");

    // Vanilla SQ_ENV FormID in Starfield.esm — verified never overridden by Check()
    public const uint VanillaSqEnvId = 0x248D20;

    // Deterministic local FormIDs
    public const uint HardcoreGpoId = 0x800;
    public const uint HardcoreGpogId = 0x801;
    public const uint HardcoreGlobId = 0x802;
    public const uint HungerAvifId = 0x803;
    public const uint ThirstAvifId = 0x804;
    public const uint SleepAvifId = 0x805;
    public const uint AmmoBurdenAvifId = 0x806;
    public const uint HungerStageGlobId = 0x807;
    public const uint ThirstStageGlobId = 0x808;
    public const uint SleepStageGlobId = 0x809;
    public const uint FastTravelBlockedGlobId = 0x80A;

    public const uint HungerReliefEffectId = 0x810;
    public const uint ThirstReliefEffectId = 0x811;
    public const uint StimpakTriggerEffectId = 0x812;

    public const uint RationFoodId = 0x820;
    public const uint PurifiedWaterId = 0x821;
    public const uint StimpakId = 0x822;

    public const uint CaliberLightId = 0x825;
    public const uint CaliberRifleId = 0x826;
    public const uint CaliberHeavyId = 0x827;
    public const uint WeightedAmmoFlstId = 0x828;

    public const uint QuestId = 0x830;
    public const uint NextId = 0x831;

    // EditorIDs
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
    public const string StimpakTriggerEffectEdid = "FO4SF_StimpakTriggerEffect";

    public const string RationFoodEdid = "FO4SF_RationFood";
    public const string PurifiedWaterEdid = "FO4SF_PurifiedWater";
    public const string StimpakEdid = "FO4SF_Stimpak";

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
        "Health", "CarryWeight", "Strength", "Endurance", "Agility", "Intelligence"
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
        "WeightedAmmoList"
    };

    static FormKey Own(uint id) => new(Plugin, id);
    static ActorValueInformation.Flag MeterFlags => ActorValueInformation.Flag.DefaultToZero | ActorValueInformation.Flag.DamageIsPositive;
    static ActorValueInformation.Flag ZeroFlags => ActorValueInformation.Flag.DefaultToZero;

    static IStarfieldModDisposableGetter OpenMod(string path)
    {
        var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        styles.Set(new KeyedMasterStyle(SfEsm, MasterStyle.Full));
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

    public static int Build(string sfPath, string outDir, int defaultHardcore)
    {
        using var sf = OpenMod(sfPath);
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

        // 1. GPOF + GPOG + GLOBs
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

        var hcGlob = new Global(Own(HardcoreGlobId), Release) { EditorID = HardcoreGlobEdid, Data = defaultHardcore };
        var hStageGlob = new Global(Own(HungerStageGlobId), Release) { EditorID = HungerStageGlobEdid, Data = 0f };
        var tStageGlob = new Global(Own(ThirstStageGlobId), Release) { EditorID = ThirstStageGlobEdid, Data = 0f };
        var sStageGlob = new Global(Own(SleepStageGlobId), Release) { EditorID = SleepStageGlobEdid, Data = 0f };
        var ftGlob = new Global(Own(FastTravelBlockedGlobId), Release) { EditorID = FastTravelBlockedGlobEdid, Data = defaultHardcore };
        mod.Globals.Add(hcGlob);
        mod.Globals.Add(hStageGlob);
        mod.Globals.Add(tStageGlob);
        mod.Globals.Add(sStageGlob);
        mod.Globals.Add(ftGlob);

        // 2. AVIFs
        var hungerAv = new ActorValueInformation(Own(HungerAvifId), Release)
        {
            EditorID = HungerAvifEdid, Name = "Hunger", Abbreviation = "Hng",
            Type = ActorValueInformation.Types.Variable, DefaultValue = 0f, Min = 0f, Max = MeterMax, Flags = MeterFlags,
        };
        var thirstAv = new ActorValueInformation(Own(ThirstAvifId), Release)
        {
            EditorID = ThirstAvifEdid, Name = "Thirst", Abbreviation = "Thr",
            Type = ActorValueInformation.Types.Variable, DefaultValue = 0f, Min = 0f, Max = MeterMax, Flags = MeterFlags,
        };
        var sleepAv = new ActorValueInformation(Own(SleepAvifId), Release)
        {
            EditorID = SleepAvifEdid, Name = "Sleep Deprivation", Abbreviation = "Slp",
            Type = ActorValueInformation.Types.Variable, DefaultValue = 0f, Min = 0f, Max = MeterMax, Flags = MeterFlags,
        };
        var ammoBurdenAv = new ActorValueInformation(Own(AmmoBurdenAvifId), Release)
        {
            EditorID = AmmoBurdenAvifEdid, Name = "Ammo Weight Burden", Abbreviation = "AWt",
            Type = ActorValueInformation.Types.Variable, DefaultValue = 0f, Min = 0f, Max = AmmoBurdenMax, Flags = ZeroFlags,
        };
        mod.ActorValueInformation.Add(hungerAv);
        mod.ActorValueInformation.Add(thirstAv);
        mod.ActorValueInformation.Add(sleepAv);
        mod.ActorValueInformation.Add(ammoBurdenAv);

        // 3. MagicEffects & Aid Ingestibles
        var hungerEff = MakeReliefEffect(tpl.RestoreMgef, HungerReliefEffectId, HungerReliefEffectEdid, "Ration Relief", "Reduces hunger.", hungerAv.FormKey);
        var thirstEff = MakeReliefEffect(tpl.RestoreMgef, ThirstReliefEffectId, ThirstReliefEffectEdid, "Hydration Relief", "Reduces thirst.", thirstAv.FormKey);
        var stimEff = MakeReliefEffect(tpl.RestoreMgef, StimpakTriggerEffectId, StimpakTriggerEffectEdid, "Stimpak Trigger", "Triggers stimpak healing.", ammoBurdenAv.FormKey);
        mod.MagicEffects.Add(hungerEff);
        mod.MagicEffects.Add(thirstEff);
        mod.MagicEffects.Add(stimEff);

        var ration = MakeAid(tpl.Aid, RationFoodId, RationFoodEdid, "Field Ration", "Restores hunger (-250).", false, hungerEff.FormKey, 0f, tpl.RestoreEntry);
        var water = MakeAid(tpl.Aid, PurifiedWaterId, PurifiedWaterEdid, "Purified Water", "Restores thirst (-250).", false, thirstEff.FormKey, 0f, tpl.RestoreEntry);
        var stimpak = MakeAid(tpl.Aid, StimpakId, StimpakEdid, "Stimpak", "Restores health instantly (Normal) or over 6 seconds (Hardcore).", true, stimEff.FormKey, 0f, tpl.RestoreEntry);
        mod.Ingestibles.Add(ration);
        mod.Ingestibles.Add(water);
        mod.Ingestibles.Add(stimpak);

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
        var propMap = new Dictionary<string, FormKey>
        {
            ["HardcoreOption"] = gpo.FormKey,
            ["HardcoreEnabledGlobal"] = hcGlob.FormKey,
            ["FastTravelBlockedGlobal"] = ftGlob.FormKey,
            ["HungerAV"] = hungerAv.FormKey,
            ["ThirstAV"] = thirstAv.FormKey,
            ["SleepAV"] = sleepAv.FormKey,
            ["AmmoBurdenAV"] = ammoBurdenAv.FormKey,
            ["HungerStageGlobal"] = hStageGlob.FormKey,
            ["ThirstStageGlobal"] = tStageGlob.FormKey,
            ["SleepStageGlobal"] = sStageGlob.FormKey,
            ["HealthAV"] = sfAvifs["Health"].FormKey,
            ["CarryWeightAV"] = sfAvifs["CarryWeight"].FormKey,
            ["StrengthAV"] = sfAvifs["Strength"].FormKey,
            ["EnduranceAV"] = sfAvifs["Endurance"].FormKey,
            ["AgilityAV"] = sfAvifs["Agility"].FormKey,
            ["IntelligenceAV"] = sfAvifs["Intelligence"].FormKey,
            ["RationFood"] = ration.FormKey,
            ["PurifiedWater"] = water.FormKey,
            ["Stimpak"] = stimpak.FormKey,
            ["CaliberLight"] = calLight.FormKey,
            ["CaliberRifle"] = calRifle.FormKey,
            ["CaliberHeavy"] = calHeavy.FormKey,
            ["WeightedAmmoList"] = ammoFlst.FormKey,
        };
        foreach (var pn in PropNames) se.Properties.Add(ObjProp(pn, propMap[pn]));

        quest.VirtualMachineAdapter = new QuestAdapter
        {
            Version = 6, ObjectFormat = 2, ExtraBindDataVersion = 3,
            Script = new ScriptEntry { Name = "", Flags = ScriptEntry.Flag.Local },
        };
        quest.VirtualMachineAdapter.Scripts.Add(se);
        mod.Quests.Add(quest);

        mod.ModHeader.Stats.NextFormID = NextId;
        if (!mod.ModHeader.MasterReferences.Any(m => m.Master == SfEsm))
            mod.ModHeader.MasterReferences.Add(new MasterReference { Master = SfEsm });

        WriteMod(mod, outDir);
        var writtenPath = Path.Combine(outDir, Plugin.FileName);
        Console.WriteLine($"wrote {writtenPath} ({new FileInfo(writtenPath).Length:N0} bytes): " +
                          $"1 GPOF, 1 GPOG, 5 GLOB, 4 AVIF, 3 MGEF, 3 ALCH, 3 AMMO, 1 FLST ({ammoFlst.Items.Count} items), 1 QUST ({PropNames.Length} properties); default_hardcore={defaultHardcore}");
        return 0;
    }

    public static int Check(string pluginPath, string sfPath, int defaultHardcore)
    {
        if (!File.Exists(pluginPath)) throw new Refusal($"missing plugin: {pluginPath}");
        using var sf = OpenMod(sfPath);
        var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        styles.Set(new KeyedMasterStyle(SfEsm, MasterStyle.Full));
        styles.Set(new KeyedMasterStyle(Plugin, MasterStyle.Full));
        using var mod = StarfieldMod.CreateFromBinaryOverlay(pluginPath, Release, new BinaryReadParameters { MasterFlagsLookup = styles });

        if (!mod.ModHeader.Flags.HasFlag(StarfieldModHeader.HeaderFlag.Master))
            throw new Refusal("plugin lacks Master header flag");
        var masters = mod.ModHeader.MasterReferences.Select(m => m.Master.FileName.String).ToList();
        if (masters.Count != 1 || !string.Equals(masters[0], "Starfield.esm", StringComparison.OrdinalIgnoreCase))
            throw new Refusal($"expected sole master [Starfield.esm], got [{string.Join(", ", masters)}]");

        // Verify zero record overrides of Starfield.esm (including SQ_ENV 0x248D20)
        foreach (var rec in mod.EnumerateMajorRecords())
        {
            if (rec.FormKey.ModKey != Plugin)
                throw new Refusal($"plugin overrides foreign record {rec.FormKey} ({rec.EditorID}) — must add records only and never touch SQ_ENV");
            if (rec.FormKey.ID == VanillaSqEnvId)
                throw new Refusal("plugin touches SQ_ENV FormID");
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

        if (mod.Globals.Count != 5) throw new Refusal($"expected 5 GLOB, found {mod.Globals.Count}");
        var hcGlob = mod.Globals.First(g => g.FormKey == Own(HardcoreGlobId));
        if (Math.Abs((hcGlob.Data ?? -1f) - defaultHardcore) > 0.001f)
            throw new Refusal($"FO4SF_HardcoreEnabled expected {defaultHardcore}, got {hcGlob.Data}");

        if (mod.ActorValueInformation.Count != 4) throw new Refusal($"expected 4 AVIF, found {mod.ActorValueInformation.Count}");
        foreach (var (id, edid) in new[] { (HungerAvifId, HungerAvifEdid), (ThirstAvifId, ThirstAvifEdid), (SleepAvifId, SleepAvifEdid) })
        {
            var av = mod.ActorValueInformation.FirstOrDefault(a => a.FormKey == Own(id)) ?? throw new Refusal($"missing AVIF {edid}");
            if (av.EditorID != edid || !(av.Flags ?? 0).HasFlag(ActorValueInformation.Flag.DamageIsPositive) || Math.Abs((av.Max ?? -1f) - MeterMax) > 0.01f)
                throw new Refusal($"AVIF {edid} flags/max mismatch");
        }

        if (mod.Ingestibles.Count != 3) throw new Refusal($"expected 3 ALCH, found {mod.Ingestibles.Count}");
        var stim = mod.Ingestibles.FirstOrDefault(i => i.FormKey == Own(StimpakId)) ?? throw new Refusal("missing FO4SF_Stimpak");
        if (!stim.Flags.HasFlag(Ingestible.Flag.Medicine)) throw new Refusal("FO4SF_Stimpak lacks Medicine flag");

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

        Console.WriteLine($"FO4SFHardcore.esm: header Master, masters [Starfield.esm], next 0x{mod.ModHeader.Stats.NextFormID:X}, zero foreign overrides (SQ_ENV 0x{VanillaSqEnvId:X6} untouched)");
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
        Console.WriteLine("selftest: ok");
        return 0;
    }
}
