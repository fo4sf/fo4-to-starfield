// RadsCore: core radiation and optional mutations plugin writer and checker (docs/rads/rads-core.md).
//
// Writes FO4SFRads.esm (mastered on Starfield.esm only; adds records, overrides none):
//   0x800 AVIF FO4SF_Rads             0..1000, DefaultToZero | DamageIsPositive (matches Pip-Boy local id 0x800)
//   0x801 AVIF FO4SF_RadsCapPct       0..100, DefaultToZero (percentage of health bar capped by radiation)
//   0x802 GLOB FO4SF_RadsDisplayPct   0..100 float, synced alongside FO4SF_RadsCapPct for UI/HUD consumers
//   0x803 GLOB FO4SF_RadsStage        0..5 sickness tier (None, Minor, Advanced, Critical, Deadly, Fatal)
//   0x804 AVIF FO4SF_RadResist        0..1000, DefaultToZero (radiation resistance, buffed by FO4SF_RadX)
//   0x805 AVIF FO4SF_InWater          0..1, DefaultToZero (driven by FO4SF_AbWaterDetect IsInWater == 1 ability)
//   0x806 GLOB FO4SF_RadsRule         0 = Mode A (Max-HP cap), 1 = Mode B (Sickness stat thresholds)
//   0x807 GLOB FO4SF_MutationsEnabled 0 = OFF (default), 1 = ON (rolls/cures clean-room mutation PERKs)
//   0x808 GPOF FO4SF_GPO_RadsRule     GameplayOption wired to FO4SF_RadsRule (0 = Max-HP cap, 1 = Stat sickness)
//   0x809 GPOF FO4SF_GPO_Mutations    GameplayOption wired to FO4SF_MutationsEnabled (0 = Off, 1 = On)
//   0x80A GPOG FO4SF_GPOG_Radiation   GameplayOptionsGroup listing FO4SF_GPO_RadsRule and FO4SF_GPO_Mutations
//   0x810 MGEF FO4SF_RadsEffect       copied from DamageHealthContact (Detrimental kept, SecondActorValue = FO4SF_Rads)
//   0x811 SPEL FO4SF_RadsSpell        copied from DamageHealthSpell (+100 rads, Self, FireAndForget, duration 0)
//   0x812 MGEF FO4SF_RadsHazardEffect copied from hazard touch effect (Detrimental kept, Touch, SecondActorValue = FO4SF_Rads)
//   0x813 SPEL FO4SF_RadsHazardSpell  copied from hazard touch spell (+15 rads, Touch, FireAndForget, duration 0)
//   0x814 MGEF FO4SF_RadAwayEffect    restore mirror effect on FO4SF_Rads (built when a restore template exists)
//   0x815 MGEF FO4SF_RadXEffect       restore/buff effect on FO4SF_RadResist (built when a restore template exists)
//   0x816 MGEF FO4SF_InWaterEffect    ConstantEffect Self ValueModifier on FO4SF_InWater (Recover | HideInUI)
//   0x817 SPEL FO4SF_AbWaterDetect    Ability ConstantEffect Self (+1 FO4SF_InWater when IsInWater == 1)
//   0x818 SPEL FO4SF_WaterDrinkSpell  FireAndForget Self (+25 FO4SF_RadsEffect)
//   0x819 SPEL FO4SF_WaterContactSpell FireAndForget Self (+5 FO4SF_RadsEffect)
//   0x820 ALCH FO4SF_RadAway          Medicine (-300 rads via verified script route; cures 1 unlocked mutation when enabled)
//   0x821 ALCH FO4SF_RadX             Medicine (+100 FO4SF_RadResist for 60 s)
//   0x822 ALCH FO4SF_IrradiatedFood   Food ingestible (+50 rads)
//   0x823 ALCH FO4SF_DirtyWater       Drink ingestible (+25 rads)
//   0x828 HAZD FO4SF_RadsHazard       Hazard zone cloned from vanilla HAZD template -> FO4SF_RadsHazardSpell (+15/tick)
//   0x829 KYWD FO4SF_Kw_RadsEmitter   Keyword marking placed radiation emitters
//   0x82A ACTI FO4SF_RadsEmitter      Emitter activator cloned from vanilla ACTI template, tagged FO4SF_Kw_RadsEmitter
//   0x82B WATR FO4SF_IrradiatedWater  Water cloned from vanilla WATR template (Dangerous, Consume/Contact spells)
//   0x830..0x833 PERK FO4SF_Mut_*     4 clean-room mutation PERKs (Marsupial, SpeedDemon, HealingFactor, ScalySkin)
//   0x834 PERK FO4SF_Perk_StarchedGenes Locks active mutations against new rolls and RadAway removal
//   0x835 FLST FO4SF_MutationPerks    FormList of the 4 mutation PERKs in deterministic order
//   0x838..0x83B SPEL FO4SF_AbMut_*   4 ConstantEffect Self Abilities attached to the 4 mutation PERKs
//   0x840..0x847 MGEF FO4SF_MgefMut_* 8 ConstantEffect Self ValueModifier effects backing FO4SF_AbMut_*
//   0x850 QUST FO4SF_RadsCoreQuest    StartGameEnabled quest driving both passive play and verification stages
//
// usage:
//   RadsCore build <Starfield.esm> <out dir> [--default-rule 0|1] [--mutations-default 0|1]
//   RadsCore check <plugin> <Starfield.esm> [--default-rule 0|1] [--mutations-default 0|1]
//   RadsCore fixture <out dir> [--mode full|spell|none]
//   RadsCore selftest <scratch dir>

using System.Globalization;
using System.Text.Json;
using Mutagen.Bethesda;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;
using SF = Mutagen.Bethesda.Starfield;

try
{
    var rest = args.ToList();
    int defaultRule = 0;
    int mutDefault = 0;
    string fixtureMode = "full";
    string? jsonPath = null;

    void OptInt(string name, ref int into)
    {
        int i = rest.IndexOf(name);
        if (i < 0) return;
        if (i + 1 >= rest.Count || !int.TryParse(rest[i + 1], NumberStyles.Integer, CultureInfo.InvariantCulture, out int v) || (v != 0 && v != 1))
            throw new RadsCore.Refusal($"{name} must be 0 or 1");
        into = v;
        rest.RemoveRange(i, 2);
    }
    void OptStr(string name, ref string into)
    {
        int i = rest.IndexOf(name);
        if (i < 0) return;
        if (i + 1 >= rest.Count) throw new RadsCore.Refusal($"{name} needs a value");
        into = rest[i + 1];
        rest.RemoveRange(i, 2);
    }
    void OptStrNull(string name, ref string? into)
    {
        int i = rest.IndexOf(name);
        if (i < 0) return;
        if (i + 1 >= rest.Count) throw new RadsCore.Refusal($"{name} needs a value");
        into = rest[i + 1];
        rest.RemoveRange(i, 2);
    }

    OptInt("--default-rule", ref defaultRule);
    OptInt("--mutations-default", ref mutDefault);
    OptStr("--mode", ref fixtureMode);
    OptStrNull("--json", ref jsonPath);
    var opts = new RadsCore.BuildOptions(defaultRule, mutDefault, jsonPath);

    if (rest.Count == 3 && rest[0] == "build") return RadsCore.Build(rest[1], rest[2], opts);
    if (rest.Count == 3 && rest[0] == "check") return RadsCore.Check(rest[1], rest[2], opts);
    if (rest.Count == 2 && rest[0] == "fixture") return RadsCore.Fixture(rest[1], fixtureMode);
    if (rest.Count == 2 && rest[0] == "selftest") return RadsCore.SelfTest(rest[1]);
}
catch (RadsCore.Refusal r)
{
    Console.Error.WriteLine("refused: " + r.Message);
    return 1;
}

Console.Error.WriteLine("usage: RadsCore build <Starfield.esm> <out dir> [--json <path>] [--default-rule 0|1] [--mutations-default 0|1] | " +
                        "check <plugin> <Starfield.esm> [same options] | fixture <out dir> [--mode full|spell|none] | selftest <scratch dir>");
return 2;

public static class RadsCore
{
    public class Refusal(string m) : Exception(m);
    public record BuildOptions(int DefaultRule = 0, int MutationsDefault = 0, string? CoreValuesJson = null);

    const StarfieldRelease Release = StarfieldRelease.Starfield;
    static readonly ModKey SfEsm = ModKey.FromFileName("Starfield.esm");
    public static readonly ModKey CoreValuesEsm = ModKey.FromFileName("FO4SFCoreValues.esm");
    public static readonly ModKey Plugin = ModKey.FromFileName("FO4SFRads.esm");

    // Deterministic local FormIDs owned by FO4SFRads.esm (shared radiation/SPECIAL/test-mode IDs live in FO4SFCoreValues.esm)
    public const uint InWaterAvifId = 0x805;
    public const uint MutationsGlobId = 0x807;
    public const uint RadsRuleGpoId = 0x808;
    public const uint MutationsGpoId = 0x809;
    public const uint RadiationGpogId = 0x80A;

    public const uint RadsEffectId = 0x810;
    public const uint RadsSpellId = 0x811;
    public const uint RadsHazardEffectId = 0x812;
    public const uint RadsHazardSpellId = 0x813;
    public const uint RadAwayEffectId = 0x814;
    public const uint RadXEffectId = 0x815;
    public const uint InWaterEffectId = 0x816;
    public const uint AbWaterDetectId = 0x817;
    public const uint WaterDrinkSpellId = 0x818;
    public const uint WaterContactSpellId = 0x819;

    public const uint RadAwayId = 0x820;
    public const uint RadXId = 0x821;
    public const uint IrradiatedFoodId = 0x822;
    public const uint DirtyWaterId = 0x823;

    public const uint RadsHazardId = 0x828;
    public const uint RadsEmitterKwId = 0x829;
    public const uint RadsEmitterId = 0x82A;
    public const uint IrradiatedWaterId = 0x82B;

    public const uint MutMarsupialId = 0x830;
    public const uint MutSpeedDemonId = 0x831;
    public const uint MutHealingFactorId = 0x832;
    public const uint MutScalySkinId = 0x833;
    public const uint StarchedGenesId = 0x834;
    public const uint MutationPerksFlstId = 0x835;

    public const uint AbMutMarsupialId = 0x838;
    public const uint AbMutSpeedDemonId = 0x839;
    public const uint AbMutHealingFactorId = 0x83A;
    public const uint AbMutScalySkinId = 0x83B;

    public const uint MgefMutJumpId = 0x840;
    public const uint MgefMutCarryId = 0x841;
    public const uint MgefMutIntPenaltyId = 0x842;
    public const uint MgefMutSpeedId = 0x843;
    public const uint MgefMutReloadId = 0x844;
    public const uint MgefMutHealRateId = 0x845;
    public const uint MgefMutPhysResistId = 0x846;
    public const uint MgefMutEnergyResistId = 0x847;

    public const uint QuestId = 0x850;
    public const uint NextId = 0x851;

    // EditorIDs
    public const string RadsAvifEdid = "FO4SF_Rads";
    public const string RadsCapPctAvifEdid = "FO4SF_RadsCapPct";
    public const string RadsDisplayPctGlobEdid = "FO4SF_RadsDisplayPct";
    public const string RadsStageGlobEdid = "FO4SF_RadsStage";
    public const string RadResistAvifEdid = "FO4SF_RadResist";
    public const string InWaterAvifEdid = "FO4SF_InWater";
    public const string RadsRuleGlobEdid = "FO4SF_RadsRule";
    public const string MutationsGlobEdid = "FO4SF_MutationsEnabled";
    public const string RadsRuleGpoEdid = "FO4SF_GPO_RadsRule";
    public const string MutationsGpoEdid = "FO4SF_GPO_Mutations";
    public const string RadiationGpogEdid = "FO4SF_GPOG_Radiation";

    public const string RadsEffectEdid = "FO4SF_RadsEffect";
    public const string RadsSpellEdid = "FO4SF_RadsSpell";
    public const string RadsHazardEffectEdid = "FO4SF_RadsHazardEffect";
    public const string RadsHazardSpellEdid = "FO4SF_RadsHazardSpell";
    public const string RadAwayEffectEdid = "FO4SF_RadAwayEffect";
    public const string RadXEffectEdid = "FO4SF_RadXEffect";
    public const string InWaterEffectEdid = "FO4SF_InWaterEffect";
    public const string AbWaterDetectEdid = "FO4SF_AbWaterDetect";
    public const string WaterDrinkSpellEdid = "FO4SF_WaterDrinkSpell";
    public const string WaterContactSpellEdid = "FO4SF_WaterContactSpell";

    public const string RadAwayEdid = "FO4SF_RadAway";
    public const string RadXEdid = "FO4SF_RadX";
    public const string IrradiatedFoodEdid = "FO4SF_IrradiatedFood";
    public const string DirtyWaterEdid = "FO4SF_DirtyWater";

    public const string RadsHazardEdid = "FO4SF_RadsHazard";
    public const string RadsEmitterKwEdid = "FO4SF_Kw_RadsEmitter";
    public const string RadsEmitterEdid = "FO4SF_RadsEmitter";
    public const string IrradiatedWaterEdid = "FO4SF_IrradiatedWater";

    public const string StarchedGenesEdid = "FO4SF_Perk_StarchedGenes";
    public const string MutationPerksFlstEdid = "FO4SF_MutationPerks";
    public const string QuestEdid = "FO4SF_RadsCoreQuest";
    public const string ScriptName = "FO4SF_RadsCoreQuest";
    public const string SpecialStrEdid = "FO4SF_Special_Strength";
    public const string SpecialEndEdid = "FO4SF_Special_Endurance";
    public const string SpecialIntEdid = "FO4SF_Special_Intelligence";
    public const string SpecialAgiEdid = "FO4SF_Special_Agility";
    public const string TestModeGlobEdid = "FO4SF_TestModeEnabled";

    public const float RadsMax = 1000f;
    public const float CapPctMax = 100f;
    public const float SpellMagnitude = 100f;
    public const float HazardSpellMagnitude = 15f;
    public const float RadAwayMagnitude = -300f;
    public const float RadAwayMirrorMagnitude = 300f;
    public const float RadXMagnitude = 100f;
    public const float IrradiatedFoodMagnitude = 50f;
    public const float DirtyWaterMagnitude = 25f;
    public const float WaterContactMagnitude = 5f;
    public const float HazardRadius = 6f;
    public const float HazardInterval = 1f;

    public static readonly ushort[] Stages = { 5, 10, 20, 30, 40, 50, 60 };

    // Quest script properties in exact declaration order (pinned by tests/test_rads_core.py)
    public static readonly string[] PropNames =
    {
        "RadsAV", "RadsCapPctAV", "RadResistAV", "InWaterAV",
        "HealthAV", "EnduranceAV", "AgilityAV", "StrengthAV",
        "RadsDisplayPctGlobal", "RadsStageGlobal", "RadsRuleGlobal", "MutationsEnabledGlobal",
        "RadsRuleOption", "MutationsOption",
        "RadsSpell", "RadsHazardSpell", "AbWaterDetect", "WaterDrinkSpell", "WaterContactSpell",
        "RadAway", "RadX", "IrradiatedFood", "DirtyWater",
        "RadsHazard", "RadsEmitter", "RadsEmitterKeyword", "IrradiatedWater",
        "MutationPerks", "StarchedGenesPerk", "TestModeGlobal"
    };

    public record MutEffectSpec(uint MgefId, string MgefEdid, string TargetAvEdid, float Magnitude, bool Detrimental);
    public record MutationSpec(uint PerkId, string PerkEdid, string Name, string Desc, uint AbilityId, string AbilityEdid, MutEffectSpec[] Effects);

    public static readonly MutationSpec[] Mutations =
    {
        new(MutMarsupialId, "FO4SF_Mut_Marsupial", "Marsupial",
            "Jump Multiplier +0.5, Carry Capacity +20, Intelligence -1.",
            AbMutMarsupialId, "FO4SF_AbMut_Marsupial",
            new[]
            {
                new MutEffectSpec(MgefMutJumpId, "FO4SF_MgefMut_Jump", "JumpSpeedMult", 0.5f, false),
                new MutEffectSpec(MgefMutCarryId, "FO4SF_MgefMut_Carry", "CarryWeight", 20f, false),
                new MutEffectSpec(MgefMutIntPenaltyId, "FO4SF_MgefMut_IntPenalty", SpecialIntEdid, 1f, true),
            }),
        new(MutSpeedDemonId, "FO4SF_Mut_SpeedDemon", "Speed Demon",
            "Movement Speed +20, Reload Speed +0.2.",
            AbMutSpeedDemonId, "FO4SF_AbMut_SpeedDemon",
            new[]
            {
                new MutEffectSpec(MgefMutSpeedId, "FO4SF_MgefMut_Speed", "SpeedMult", 20f, false),
                new MutEffectSpec(MgefMutReloadId, "FO4SF_MgefMut_Reload", "PlayerReloadSpeedMult", 0.2f, false),
            }),
        new(MutHealingFactorId, "FO4SF_Mut_HealingFactor", "Healing Factor",
            "Health Regeneration +50.",
            AbMutHealingFactorId, "FO4SF_AbMut_HealingFactor",
            new[]
            {
                new MutEffectSpec(MgefMutHealRateId, "FO4SF_MgefMut_HealRate", "HealRateMult", 50f, false),
            }),
        new(MutScalySkinId, "FO4SF_Mut_ScalySkin", "Scaly Skin",
            "Physical Resistance +50, Energy Resistance +50.",
            AbMutScalySkinId, "FO4SF_AbMut_ScalySkin",
            new[]
            {
                new MutEffectSpec(MgefMutPhysResistId, "FO4SF_MgefMut_PhysResist", "DamageResist", 50f, false),
                new MutEffectSpec(MgefMutEnergyResistId, "FO4SF_MgefMut_EnergyResist", "EnergyResist", 50f, false),
            }),
    };

    static readonly string[] RequiredSfAvifs =
    {
        "Health", "CarryWeight", "SpeedMult", "DamageResist", "EnergyResist",
        "HealRateMult", "JumpSpeedMult", "PlayerReloadSpeedMult"
    };

    static FormKey Own(uint id) => new(Plugin, id);
    static ActorValueInformation.Flag RadsAvifFlags => ActorValueInformation.Flag.DefaultToZero | ActorValueInformation.Flag.DamageIsPositive;
    static ActorValueInformation.Flag ZeroAvifFlags => ActorValueInformation.Flag.DefaultToZero;

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

    static FormKey TargetAvKey(string edid, IReadOnlyDictionary<string, IActorValueInformationGetter> sfAvifs, IReadOnlyDictionary<string, uint> coreIds) =>
        edid.StartsWith("FO4SF_", StringComparison.Ordinal) ? Core(coreIds, edid) : sfAvifs[edid].FormKey;

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

    public record FoundTemplates(
        ISpellGetter? SelfSpell, IMagicEffectGetter? SelfEffect,
        ISpellGetter? TouchSpell, IMagicEffectGetter? TouchEffect,
        ISpellGetter? AbilitySpell, IMagicEffectGetter? AbilityEffect,
        IIngestibleGetter? AidShell, IMagicEffectGetter? RestoreEffect, IEffectGetter? RestoreEntry,
        IHazardGetter? Hazard, IWaterGetter? Water, SF.IActivatorGetter? Activator,
        string Level)
    {
        public bool Mirror => AidShell != null && RestoreEffect != null;
    }

    static FoundTemplates FindTemplates(IStarfieldModGetter sf, FormKey healthKey)
    {
        var mgefs = sf.MagicEffects.ToDictionary(m => m.FormKey);
        IMagicEffectGetter? SingleEffect(ISpellGetter sp) =>
            sp.Effects.Count >= 1 && sp.Effects[0].BaseEffect.FormKey is { } fk && mgefs.TryGetValue(fk, out var m) ? m : null;

        // 1. Self Detrimental spell/effect (DamageHealthSpell preferred, proven in RadsProbe)
        ISpellGetter? selfSpell = sf.Spells.FirstOrDefault(sp => string.Equals(sp.EditorID, "DamageHealthSpell", StringComparison.OrdinalIgnoreCase) && sp.Effects.Count == 1 && SingleEffect(sp) != null);
        string level = selfSpell != null ? "preferred" : "none";
        if (selfSpell == null)
        {
            selfSpell = sf.Spells.Where(sp => sp.Type == Spell.SpellType.Spell && sp.CastType == CastType.FireAndForget && sp.TargetType == TargetType.Self && sp.Effects.Count == 1)
                .OrderBy(sp => sp.FormKey.ID)
                .FirstOrDefault(sp => SingleEffect(sp) is { } m && m.Archetype.Type == MagicEffectArchetype.TypeEnum.ValueModifier);
            if (selfSpell != null) level = "search";
        }
        var selfEffect = selfSpell != null ? SingleEffect(selfSpell) : null;

        // 2. Touch Detrimental hazard spell/effect (SpaceDistortionCloudHazardSpell preferred)
        ISpellGetter? touchSpell = sf.Spells.FirstOrDefault(sp => string.Equals(sp.EditorID, "SpaceDistortionCloudHazardSpell", StringComparison.OrdinalIgnoreCase) && sp.Effects.Count == 1 && SingleEffect(sp) != null)
            ?? sf.Spells.Where(sp => sp.Type == Spell.SpellType.Spell && sp.CastType == CastType.FireAndForget && sp.TargetType == TargetType.Touch && sp.Effects.Count == 1)
                .OrderBy(sp => sp.FormKey.ID)
                .FirstOrDefault(sp => SingleEffect(sp) is { } m && m.Archetype.Type == MagicEffectArchetype.TypeEnum.ValueModifier && m.Flags.HasFlag(MagicEffect.Flag.Detrimental));
        var touchEffect = touchSpell != null ? SingleEffect(touchSpell) : null;

        // 3. ConstantEffect Self Ability spell/effect (abCrewAstrodynamics_01 preferred)
        ISpellGetter? abSpell = sf.Spells.FirstOrDefault(sp => string.Equals(sp.EditorID, "abCrewAstrodynamics_01", StringComparison.OrdinalIgnoreCase) && SingleEffect(sp) != null)
            ?? sf.Spells.Where(sp => sp.Type == Spell.SpellType.Ability && sp.CastType == CastType.ConstantEffect && sp.TargetType == TargetType.Self)
                .OrderBy(sp => sp.FormKey.ID)
                .FirstOrDefault(sp => SingleEffect(sp) != null);
        var abEffect = abSpell != null ? SingleEffect(abSpell) : null;

        // 4. Aid shell & restore effect (proven RadsProbe pattern: ingestible first, then Dueling_RestoreHealth_Spell)
        IIngestibleGetter? aid = null;
        IMagicEffectGetter? restoreEffect = null;
        IEffectGetter? restoreEntry = null;
        var singles = sf.Ingestibles.Where(i => i.Effects.Count == 1 && i.Addiction.IsNull).OrderBy(i => i.FormKey.ID).ToList();
        foreach (var i in singles)
        {
            if (i.Effects[0].BaseEffect.FormKey is { } fk && mgefs.TryGetValue(fk, out var m) &&
                m.Archetype.Type == MagicEffectArchetype.TypeEnum.ValueModifier && m.SecondActorValue.FormKey == healthKey &&
                !m.Flags.HasFlag(MagicEffect.Flag.Detrimental) && i.Effects[0].Data?.Duration == 0)
            {
                aid = i; restoreEffect = m; restoreEntry = i.Effects[0]; break;
            }
        }
        if (aid == null)
        {
            var meds = singles.Where(i => i.Flags.HasFlag(Ingestible.Flag.Medicine) && i.MajorFlags.HasFlag(Ingestible.MajorFlag.Medicine)).ToList();
            aid = meds.FirstOrDefault(i => i.Effects[0].Data?.Duration == 0) ?? meds.FirstOrDefault();
        }
        if (aid != null && restoreEffect == null)
        {
            bool IsRestore(ISpellGetter sp) => sp.Effects.Count == 1 && sp.Effects[0].Data?.Duration == 0 && SingleEffect(sp) is { } m &&
                m.Archetype.Type == MagicEffectArchetype.TypeEnum.ValueModifier && m.SecondActorValue.FormKey == healthKey && !m.Flags.HasFlag(MagicEffect.Flag.Detrimental);
            var rs = sf.Spells.Where(sp => string.Equals(sp.EditorID, "Dueling_RestoreHealth_Spell", StringComparison.OrdinalIgnoreCase)).FirstOrDefault(IsRestore)
                     ?? sf.Spells.Where(IsRestore).OrderBy(sp => sp.FormKey.ID).FirstOrDefault();
            if (rs != null)
            {
                restoreEffect = SingleEffect(rs);
                restoreEntry = rs.Effects[0];
            }
        }

        // 5. Hazard, Water, Activator templates
        IHazardGetter? haz = sf.Hazards.FirstOrDefault(h => string.Equals(h.EditorID, "ENV_PoolHazard_Radiation", StringComparison.OrdinalIgnoreCase))
                             ?? sf.Hazards.OrderBy(h => h.FormKey.ID).FirstOrDefault();
        IWaterGetter? wat = sf.Waters.FirstOrDefault(w => string.Equals(w.EditorID, "WaterClear", StringComparison.OrdinalIgnoreCase))
                            ?? sf.Waters.OrderBy(w => w.FormKey.ID).FirstOrDefault();
        SF.IActivatorGetter? acti = sf.Activators.FirstOrDefault(a => string.Equals(a.EditorID, "EmptyTrigger", StringComparison.OrdinalIgnoreCase))
                                    ?? sf.Activators.OrderBy(a => a.FormKey.ID).FirstOrDefault();

        return new FoundTemplates(selfSpell, selfEffect, touchSpell, touchEffect, abSpell, abEffect, aid, restoreEffect, restoreEntry, haz, wat, acti, level);
    }

    static MagicEffect CopyValueEffect(IMagicEffectGetter? tm, uint id, string edid, string name, string desc, FormKey av,
        CastType fallbackCast, TargetType fallbackTarget, MagicEffect.Flag? forceFlags = null)
    {
        MagicEffect e;
        if (tm != null)
        {
            e = (MagicEffect)tm.Duplicate(Own(id), new MagicEffect.TranslationMask(defaultOn: true));
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
            e.CastType = fallbackCast;
            e.TargetType = fallbackTarget;
            if (forceFlags.HasValue) e.Flags = forceFlags.Value;
        }
        else
        {
            e = new MagicEffect(Own(id), Release)
            {
                EditorID = edid, Name = name, Description = desc,
                Archetype = new MagicEffectArchetype(MagicEffectArchetype.TypeEnum.ValueModifier),
                CastType = fallbackCast, TargetType = fallbackTarget,
                Flags = forceFlags ?? (MagicEffect.Flag.Detrimental | MagicEffect.Flag.NoDuration | MagicEffect.Flag.NoArea),
            };
            e.SecondActorValue.SetTo(av);
        }
        return e;
    }

    static Effect MakeEntry(FormKey baseEffect, float magnitude, IEffectGetter? from, int duration = 0) => new()
    {
        BaseEffect = new FormLinkNullable<IMagicEffectGetter>(baseEffect),
        Data = new EffectData { Magnitude = magnitude, Area = 0, Duration = duration },
        MAGF = from?.MAGF, EFIF = from?.EFIF, MUID = from?.MUID,
    };

    static Spell MakeSpell(ISpellGetter? tpl, uint id, string edid, string name, string desc,
        Spell.SpellType spType, CastType castType, TargetType targetType, params Effect[] entries)
    {
        Spell sp;
        if (tpl != null)
        {
            sp = (Spell)tpl.Duplicate(Own(id), new Spell.TranslationMask(defaultOn: true));
            sp.EditorID = edid;
            sp.Name = name;
            sp.Description = desc;
            sp.Type = spType;
            sp.CastType = castType;
            sp.TargetType = targetType;
            sp.VirtualMachineAdapter = null;
            sp.Keywords = null;
            sp.Effects.Clear();
        }
        else
        {
            sp = new Spell(Own(id), Release)
            {
                EditorID = edid, Name = name, Description = desc,
                Type = spType, CastType = castType, TargetType = targetType,
                Flags = spType == Spell.SpellType.Spell ? Spell.Flag.ManualCostCalc : 0,
            };
        }
        foreach (var e in entries) sp.Effects.Add(e);
        return sp;
    }

    static Ingestible MakeIngestible(IIngestibleGetter? tpl, uint id, string edid, string name, string desc, bool medicine, Effect entry)
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
            if (!medicine)
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
                EditorID = edid, Name = name, Description = desc, Weight = 0.5f, Value = 15,
                Flags = medicine ? Ingestible.Flag.Medicine : Ingestible.Flag.FoodItem,
                MajorFlags = medicine ? Ingestible.MajorFlag.Medicine : 0,
            };
        }
        item.Effects.Add(entry);
        return item;
    }

    static string TplName(IMajorRecordGetter? r) => r == null ? "none" : $"{r.EditorID} {r.FormKey}";

    // ---------------------------------------------------------------- build

    public static int Build(string sfPath, string outDir, BuildOptions opts)
    {
        var coreIds = LoadCoreValues(opts.CoreValuesJson);
        var radsFk = Core(coreIds, RadsAvifEdid);
        var radResistFk = Core(coreIds, RadResistAvifEdid);
        using var sf = OpenMod(sfPath, SfEsm);
        var sfAvifs = RequiredSfAvifs.ToDictionary(n => n, n =>
        {
            var av = One(sf.ActorValueInformation, n, "AVIF");
            if (av.FormKey.ModKey != SfEsm) throw new Refusal($"{n} is not owned by Starfield.esm");
            return av;
        });
        var found = FindTemplates(sf, sfAvifs["Health"].FormKey);
        Console.WriteLine($"templates ({found.Level}): SPEL {TplName(found.SelfSpell)}, TouchSPEL {TplName(found.TouchSpell)}, " +
                          $"AbSPEL {TplName(found.AbilitySpell)}, ALCH {TplName(found.AidShell)}, " +
                          $"RestoreMGEF {TplName(found.RestoreEffect)}, HAZD {TplName(found.Hazard)}, " +
                          $"WATR {TplName(found.Water)}, ACTI {TplName(found.Activator)}");

        var mod = new StarfieldMod(Plugin, Release);
        mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        mod.ModHeader.Author = "fo4-to-starfield RadsCore";

        // 1. Local AVIF & GLOB & GameplayOptions (shared Rads/SPECIAL/TestMode live in FO4SFCoreValues.esm)
        var inWaterAv = new ActorValueInformation(Own(InWaterAvifId), Release)
        {
            EditorID = InWaterAvifEdid, Name = "In Water", Abbreviation = "Wtr",
            Type = ActorValueInformation.Types.Variable, DefaultValue = 0f, Min = 0f, Max = 1f, Flags = ZeroAvifFlags,
        };
        mod.ActorValueInformation.Add(inWaterAv);

        var mutGlob = new Global(Own(MutationsGlobId), Release) { EditorID = MutationsGlobEdid, Data = opts.MutationsDefault };
        mod.Globals.Add(mutGlob);

        var gpoRule = new GameplayOption(Own(RadsRuleGpoId), Release)
        {
            EditorID = RadsRuleGpoEdid,
            Name = "Radiation Penalty Rule",
            Description = "Selects whether radiation caps maximum health or applies threshold stat penalties.",
            Data = new FloatGameplayOptionData { Value1 = opts.DefaultRule, Value2 = opts.DefaultRule, Min = 0f, Max = 1f, Step = 1f },
        };
        gpoRule.Rewards.Add(new GameplayOptionReward { SettingValue = 0f, Name = "MAX HP CAP", Description = "{0}: Radiation caps maximum health by 10% per 100 rads.", RewardValue = 0f });
        gpoRule.Rewards.Add(new GameplayOptionReward { SettingValue = 1f, Name = "STAT SICKNESS", Description = "{0}: Radiation applies threshold penalties to Endurance, Agility, and Strength.", RewardValue = 0f });
        mod.GameplayOptions.Add(gpoRule);

        var gpoMut = new GameplayOption(Own(MutationsGpoId), Release)
        {
            EditorID = MutationsGpoEdid,
            Name = "Radiation Mutations",
            Description = "Controls whether radiation exposure can grant and RadAway can cure mutations.",
            Data = new FloatGameplayOptionData { Value1 = opts.MutationsDefault, Value2 = opts.MutationsDefault, Min = 0f, Max = 1f, Step = 1f },
        };
        gpoMut.Rewards.Add(new GameplayOptionReward { SettingValue = 0f, Name = "OFF", Description = "{0}: Radiation mutations are disabled.", RewardValue = 0f });
        gpoMut.Rewards.Add(new GameplayOptionReward { SettingValue = 1f, Name = "ON", Description = "{0}: Radiation mutations are enabled.", RewardValue = 0f });
        mod.GameplayOptions.Add(gpoMut);

        var gpog = new GameplayOptionsGroup(Own(RadiationGpogId), Release)
        {
            EditorID = RadiationGpogEdid,
            Name = "Radiation Options",
            Options = new GameplayOptionsGroupLeaf
            {
                GameplayOptions = new ExtendedList<IFormLinkGetter<IGameplayOptionGetter>>
                {
                    new FormLink<IGameplayOptionGetter>(gpoRule.FormKey),
                    new FormLink<IGameplayOptionGetter>(gpoMut.FormKey),
                }
            }
        };
        mod.GameplayOptionsGroups.Add(gpog);

        // 2. Radiation & Water & Aid Effects and Spells
        var radsEffect = CopyValueEffect(found.SelfEffect, RadsEffectId, RadsEffectEdid, "Radiation Exposure",
            "Raises radiation burden.", radsFk, CastType.FireAndForget, TargetType.Self,
            found.SelfEffect?.Flags ?? (MagicEffect.Flag.Detrimental | MagicEffect.Flag.NoDuration | MagicEffect.Flag.NoArea));
        mod.MagicEffects.Add(radsEffect);

        var selfEntryTpl = found.SelfSpell?.Effects.FirstOrDefault();
        var radsSpell = MakeSpell(found.SelfSpell, RadsSpellId, RadsSpellEdid, "Radiation Dose", "Raises radiation by 100.",
            Spell.SpellType.Spell, CastType.FireAndForget, TargetType.Self,
            MakeEntry(radsEffect.FormKey, SpellMagnitude, selfEntryTpl));
        mod.Spells.Add(radsSpell);

        var hazTplMgef = found.TouchEffect ?? found.SelfEffect;
        var hazFlags = found.TouchEffect?.Flags ?? ((found.SelfEffect?.Flags ?? (MagicEffect.Flag.Detrimental | MagicEffect.Flag.NoDuration)) | MagicEffect.Flag.NoArea);
        if (!hazFlags.HasFlag(MagicEffect.Flag.Detrimental)) hazFlags |= MagicEffect.Flag.Detrimental;
        var radsHazEffect = CopyValueEffect(hazTplMgef, RadsHazardEffectId, RadsHazardEffectEdid, "Radiation Zone Exposure",
            "Raises radiation inside a hazard zone.", radsFk, CastType.FireAndForget, TargetType.Touch, hazFlags);
        mod.MagicEffects.Add(radsHazEffect);

        var touchEntryTpl = found.TouchSpell?.Effects.FirstOrDefault() ?? selfEntryTpl;
        var radsHazSpell = MakeSpell(found.TouchSpell ?? found.SelfSpell, RadsHazardSpellId, RadsHazardSpellEdid,
            "Radiation Zone", "Raises radiation by 15 per tick.",
            Spell.SpellType.Spell, CastType.FireAndForget, TargetType.Touch,
            MakeEntry(radsHazEffect.FormKey, HazardSpellMagnitude, touchEntryTpl));
        mod.Spells.Add(radsHazSpell);

        MagicEffect? radAwayEffect = null;
        MagicEffect? radXEffect = null;
        if (found.Mirror)
        {
            radAwayEffect = CopyValueEffect(found.RestoreEffect!, RadAwayEffectId, RadAwayEffectEdid, "RadAway Cure",
                "Lowers radiation burden.", radsFk, found.RestoreEffect!.CastType, found.RestoreEffect.TargetType,
                found.RestoreEffect.Flags);
            mod.MagicEffects.Add(radAwayEffect);

            radXEffect = CopyValueEffect(found.RestoreEffect!, RadXEffectId, RadXEffectEdid, "Rad-X Resistance",
                "Increases radiation resistance.", radResistFk, found.RestoreEffect!.CastType, found.RestoreEffect.TargetType,
                found.RestoreEffect.Flags);
            mod.MagicEffects.Add(radXEffect);
        }

        const MagicEffect.Flag AbilityPosFlags = MagicEffect.Flag.Recover | MagicEffect.Flag.NoDuration | MagicEffect.Flag.NoArea | MagicEffect.Flag.HideInUI;
        const MagicEffect.Flag AbilityNegFlags = AbilityPosFlags | MagicEffect.Flag.Detrimental;

        var inWaterEffect = CopyValueEffect(found.AbilityEffect, InWaterEffectId, InWaterEffectEdid, "Water Immersion Detector",
            "Marks active water immersion.", inWaterAv.FormKey, CastType.ConstantEffect, TargetType.Self, AbilityPosFlags);
        mod.MagicEffects.Add(inWaterEffect);

        var abEntryTpl = found.AbilitySpell?.Effects.FirstOrDefault();
        var waterDetectEntry = MakeEntry(inWaterEffect.FormKey, 1f, abEntryTpl);
        waterDetectEntry.Conditions.Add(new ConditionFloat
        {
            CompareOperator = CompareOperator.EqualTo,
            ComparisonValue = 1f,
            Data = new IsInWaterConditionData { RunOnType = Condition.RunOnType.Subject, Unknown3 = -1 },
        });
        var abWaterDetect = MakeSpell(found.AbilitySpell, AbWaterDetectId, AbWaterDetectEdid, "Water Immersion Monitor",
            "Detects water immersion.", Spell.SpellType.Ability, CastType.ConstantEffect, TargetType.Self, waterDetectEntry);
        mod.Spells.Add(abWaterDetect);

        var waterDrinkSpell = MakeSpell(found.SelfSpell, WaterDrinkSpellId, WaterDrinkSpellEdid, "Irradiated Water Intake",
            "Raises radiation when drinking irradiated water.", Spell.SpellType.Spell, CastType.FireAndForget, TargetType.Self,
            MakeEntry(radsEffect.FormKey, DirtyWaterMagnitude, selfEntryTpl));
        mod.Spells.Add(waterDrinkSpell);

        var waterContactSpell = MakeSpell(found.SelfSpell, WaterContactSpellId, WaterContactSpellEdid, "Irradiated Water Contact",
            "Raises radiation on irradiated water contact.", Spell.SpellType.Spell, CastType.FireAndForget, TargetType.Self,
            MakeEntry(radsEffect.FormKey, WaterContactMagnitude, selfEntryTpl));
        mod.Spells.Add(waterContactSpell);

        // 3. Ingestibles (RadAway, Rad-X, Irradiated Food, Dirty Water)
        var aidEntryTpl = found.AidShell?.Effects.FirstOrDefault();
        var radAwayEntry = found.Mirror
            ? MakeEntry(radAwayEffect!.FormKey, RadAwayMirrorMagnitude, found.RestoreEntry ?? aidEntryTpl)
            : MakeEntry(radsEffect.FormKey, RadAwayMagnitude, aidEntryTpl);
        var radXEntry = found.Mirror
            ? MakeEntry(radXEffect!.FormKey, RadXMagnitude, found.RestoreEntry ?? aidEntryTpl)
            : MakeEntry(radsEffect.FormKey, 0f, aidEntryTpl);

        var radAway = MakeIngestible(found.AidShell, RadAwayId, RadAwayEdid, "RadAway", "Cures 300 rads.", true, radAwayEntry);
        var radX = MakeIngestible(found.AidShell, RadXId, RadXEdid, "Rad-X", "Grants +100 Radiation Resistance for 60 seconds.", true, radXEntry);
        var irrFood = MakeIngestible(found.AidShell, IrradiatedFoodId, IrradiatedFoodEdid, "Irradiated Food", "Packaged food carrying +50 rads.", false,
            MakeEntry(radsEffect.FormKey, IrradiatedFoodMagnitude, aidEntryTpl));
        var dirtyWater = MakeIngestible(found.AidShell, DirtyWaterId, DirtyWaterEdid, "Dirty Water", "Unpurified water carrying +25 rads.", false,
            MakeEntry(radsEffect.FormKey, DirtyWaterMagnitude, aidEntryTpl));
        mod.Ingestibles.Add(radAway);
        mod.Ingestibles.Add(radX);
        mod.Ingestibles.Add(irrFood);
        mod.Ingestibles.Add(dirtyWater);

        // 4. Hazard, Emitter Keyword + Activator, and Irradiated Water
        Hazard hazard;
        if (found.Hazard != null)
        {
            hazard = (Hazard)found.Hazard.Duplicate(Own(RadsHazardId), new Hazard.TranslationMask(defaultOn: true));
            hazard.Components.Clear();
            hazard.ImageSpaceModifier.SetToNull();
            hazard.Light.SetToNull();
            hazard.ImpactDataSet.SetToNull();
        }
        else
        {
            hazard = new Hazard(Own(RadsHazardId), Release) { ObjectBounds = new ObjectBounds() };
        }
        hazard.EditorID = RadsHazardEdid;
        hazard.Name = "Radiation Zone";
        hazard.Effect.SetTo(radsHazSpell.FormKey);
        hazard.Radius = HazardRadius;
        hazard.TargetInterval = HazardInterval;
        hazard.Lifetime = 0f;
        hazard.TaperFullEffectRadius = 2f;
        hazard.TaperWeight = 1f;
        hazard.TaperCurse = 1f;
        hazard.Gravity = 1f;
        hazard.Limit = 0;
        hazard.Flags = Hazard.Flag.AffectsPlayerOnly;
        mod.Hazards.Add(hazard);

        var emitterKw = new Keyword(Own(RadsEmitterKwId), Release) { EditorID = RadsEmitterKwEdid };
        mod.Keywords.Add(emitterKw);

        SF.Activator emitter;
        if (found.Activator != null)
        {
            emitter = (SF.Activator)found.Activator.Duplicate(Own(RadsEmitterId), new SF.Activator.TranslationMask(defaultOn: true));
            emitter.VirtualMachineAdapter = null;
            emitter.Conditions?.Clear();
        }
        else
        {
            emitter = new SF.Activator(Own(RadsEmitterId), Release) { ObjectBounds = new ObjectBounds() };
        }
        emitter.EditorID = RadsEmitterEdid;
        emitter.Name = "Radiation Emitter";
        emitter.Keywords = new ExtendedList<IFormLinkGetter<IKeywordGetter>> { new FormLink<IKeywordGetter>(emitterKw.FormKey) };
        mod.Activators.Add(emitter);

        Water irrWater;
        if (found.Water != null)
        {
            irrWater = (Water)found.Water.Duplicate(Own(IrradiatedWaterId), new Water.TranslationMask(defaultOn: true));
        }
        else
        {
            irrWater = new Water(Own(IrradiatedWaterId), Release) { Opacity = 80 };
        }
        irrWater.EditorID = IrradiatedWaterEdid;
        irrWater.Name = "Irradiated Water";
        irrWater.Flags = Water.Flag.Dangerous;
        irrWater.ConsumeSpell.SetTo(waterDrinkSpell.FormKey);
        irrWater.ContactSpell.SetTo(waterContactSpell.FormKey);
        mod.Waters.Add(irrWater);

        // 5. Optional FO76-style Mutation PERKs, Abilities, StarchedGenes, and FormList
        var perkStaticKey = new FormKey(SfEsm, 0x000002);
        var mutFlst = new FormList(Own(MutationPerksFlstId), Release) { EditorID = MutationPerksFlstEdid };
        foreach (var ms in Mutations)
        {
            var abEntries = new List<Effect>();
            foreach (var es in ms.Effects)
            {
                var mg = CopyValueEffect(found.AbilityEffect, es.MgefId, es.MgefEdid, ms.Name + " Modifier",
                    ms.Desc, TargetAvKey(es.TargetAvEdid, sfAvifs, coreIds), CastType.ConstantEffect, TargetType.Self,
                    es.Detrimental ? AbilityNegFlags : AbilityPosFlags);
                mod.MagicEffects.Add(mg);
                abEntries.Add(MakeEntry(mg.FormKey, es.Magnitude, abEntryTpl));
            }
            var abSp = MakeSpell(found.AbilitySpell, ms.AbilityId, ms.AbilityEdid, ms.Name + " Ability", ms.Desc,
                Spell.SpellType.Ability, CastType.ConstantEffect, TargetType.Self, abEntries.ToArray());
            mod.Spells.Add(abSp);

            var perk = new Perk(Own(ms.PerkId), Release)
            {
                EditorID = ms.PerkEdid, Name = ms.Name, Description = ms.Desc,
                Flags = Perk.Flag.PcPlayable, MajorFlags = Perk.MajorFlag.NonPlayable,
            };
            var rank = new PerkRank { UnknownStatic = new FormLinkNullable<IStaticGetter>(perkStaticKey) };
            rank.Effects.Add(new PerkAbilityEffect { Ability = new FormLink<ISpellGetter>(abSp.FormKey), Rank = 0, Priority = 0 });
            perk.Ranks.Add(rank);
            mod.Perks.Add(perk);
            mutFlst.Items.Add(perk.FormKey);
        }

        var starched = new Perk(Own(StarchedGenesId), Release)
        {
            EditorID = StarchedGenesEdid, Name = "Starched Genes",
            Description = "Locks active mutations: radiation grants no new mutations and RadAway removes none.",
            Flags = Perk.Flag.PcPlayable, MajorFlags = Perk.MajorFlag.NonPlayable,
        };
        starched.Ranks.Add(new PerkRank { UnknownStatic = new FormLinkNullable<IStaticGetter>(perkStaticKey) });
        mod.Perks.Add(starched);
        mod.FormLists.Add(mutFlst);

        // 6. Core Quest & Script Properties
        var quest = new Quest(Own(QuestId), Release)
        {
            EditorID = QuestEdid, Name = "Fallout Radiation Core", FormVersion = 581, Version2 = 12,
            Data = new QuestData { Flags = Quest.Flag.StartGameEnabled, Priority = 30 },
        };
        foreach (var st in Stages) quest.Stages.Add(new QuestStage { Index = st });

        var script = new ScriptEntry { Name = ScriptName, Flags = ScriptEntry.Flag.Local };
        ScriptObjectProperty Obj(string propName, FormKey fk) => new()
        {
            Name = propName, Flags = ScriptProperty.Flag.Edited, Object = new FormLink<IStarfieldMajorRecordGetter>(fk), Alias = -1, Unused = 0,
        };
        var propTargets = ExpectedProperties(sfAvifs, coreIds);
        foreach (var name in PropNames)
            script.Properties.Add(Obj(name, propTargets[name]));

        quest.VirtualMachineAdapter = new QuestAdapter
        {
            Version = 6, ObjectFormat = 2, ExtraBindDataVersion = 3,
            Script = new ScriptEntry { Name = "", Flags = ScriptEntry.Flag.Local },
        };
        quest.VirtualMachineAdapter.Scripts.Add(script);
        mod.Quests.Add(quest);
        mod.ModHeader.Stats.NextFormID = NextId;

        WriteMod(mod, outDir);
        var path = Path.Combine(outDir, Plugin.FileName);
        Console.WriteLine($"wrote {path} ({new FileInfo(path).Length:N0} bytes): 1 AVIF, 1 GLOB, 2 GPOF, 1 GPOG, " +
                          $"{mod.MagicEffects.Count} MGEF, {mod.Spells.Count} SPEL, 4 ALCH, 1 HAZD, 1 ACTI, 1 KYWD, 1 WATR, " +
                          $"5 PERK, 1 FLST, 1 QUST ({PropNames.Length} properties); rule={opts.DefaultRule}, mutations={opts.MutationsDefault}");
        return 0;
    }

    static Dictionary<string, FormKey> ExpectedProperties(
        IReadOnlyDictionary<string, IActorValueInformationGetter> sfAvifs,
        IReadOnlyDictionary<string, uint> coreIds) => new()
    {
        ["RadsAV"] = Core(coreIds, RadsAvifEdid),
        ["RadsCapPctAV"] = Core(coreIds, RadsCapPctAvifEdid),
        ["RadResistAV"] = Core(coreIds, RadResistAvifEdid),
        ["InWaterAV"] = Own(InWaterAvifId),
        ["HealthAV"] = sfAvifs["Health"].FormKey,
        ["EnduranceAV"] = Core(coreIds, SpecialEndEdid),
        ["AgilityAV"] = Core(coreIds, SpecialAgiEdid),
        ["StrengthAV"] = Core(coreIds, SpecialStrEdid),
        ["RadsDisplayPctGlobal"] = Core(coreIds, RadsDisplayPctGlobEdid),
        ["RadsStageGlobal"] = Core(coreIds, RadsStageGlobEdid),
        ["RadsRuleGlobal"] = Core(coreIds, RadsRuleGlobEdid),
        ["MutationsEnabledGlobal"] = Own(MutationsGlobId),
        ["RadsRuleOption"] = Own(RadsRuleGpoId),
        ["MutationsOption"] = Own(MutationsGpoId),
        ["RadsSpell"] = Own(RadsSpellId),
        ["RadsHazardSpell"] = Own(RadsHazardSpellId),
        ["AbWaterDetect"] = Own(AbWaterDetectId),
        ["WaterDrinkSpell"] = Own(WaterDrinkSpellId),
        ["WaterContactSpell"] = Own(WaterContactSpellId),
        ["RadAway"] = Own(RadAwayId),
        ["RadX"] = Own(RadXId),
        ["IrradiatedFood"] = Own(IrradiatedFoodId),
        ["DirtyWater"] = Own(DirtyWaterId),
        ["RadsHazard"] = Own(RadsHazardId),
        ["RadsEmitter"] = Own(RadsEmitterId),
        ["RadsEmitterKeyword"] = Own(RadsEmitterKwId),
        ["IrradiatedWater"] = Own(IrradiatedWaterId),
        ["MutationPerks"] = Own(MutationPerksFlstId),
        ["StarchedGenesPerk"] = Own(StarchedGenesId),
        ["TestModeGlobal"] = Core(coreIds, TestModeGlobEdid),
    };

    static void WriteMod(StarfieldMod mod, string outDir)
    {
        Directory.CreateDirectory(outDir);
        var path = Path.Combine(outDir, mod.ModKey.FileName);
        var tmpDir = Path.Combine(outDir, ".tmp-" + Guid.NewGuid().ToString("N"));
        try
        {
            Directory.CreateDirectory(tmpDir);
            var tmp = Path.Combine(tmpDir, mod.ModKey.FileName);
            var masters = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
            masters.Set(new KeyedMasterStyle(SfEsm, MasterStyle.Full));
            masters.Set(new KeyedMasterStyle(CoreValuesEsm, MasterStyle.Full));
            mod.WriteToBinary(tmp, new BinaryWriteParameters
            {
                ModKey = ModKeyOption.NoCheck,
                MastersListOrdering = new MastersListOrderingByLoadOrder(new[] { SfEsm, CoreValuesEsm }),
                MasterFlagsLookup = masters,
            });
            File.Move(tmp, path, overwrite: true);
        }
        finally
        {
            if (Directory.Exists(tmpDir)) Directory.Delete(tmpDir, true);
        }
    }

    // ---------------------------------------------------------------- check

    public static int Check(string pluginPath, string sfPath, BuildOptions opts)
    {
        var coreIds = LoadCoreValues(opts.CoreValuesJson);
        using var sf = OpenMod(sfPath, SfEsm);
        var sfAvifs = RequiredSfAvifs.ToDictionary(n => n, n => One(sf.ActorValueInformation, n, "AVIF"));
        var found = FindTemplates(sf, sfAvifs["Health"].FormKey);
        using var mod = OpenMod(pluginPath, SfEsm, CoreValuesEsm);

        var problems = new List<string>();
        void Need(bool ok, string what) { if (!ok) problems.Add(what); }

        var masters = mod.ModHeader.MasterReferences.Select(m => m.Master).ToList();
        Console.WriteLine($"{Path.GetFileName(pluginPath)}: header {mod.ModHeader.Flags}, masters [{string.Join(", ", masters)}], next 0x{mod.ModHeader.Stats.NextFormID:X}");
        Need(mod.ModKey == Plugin, $"the file is {mod.ModKey}, not {Plugin}");
        Need(mod.ModHeader.Flags.HasFlag(StarfieldModHeader.HeaderFlag.Master), "not flagged as a master");
        Need(masters.SequenceEqual(new[] { SfEsm, CoreValuesEsm }), "masters are not exactly [Starfield.esm, FO4SFCoreValues.esm]");
        Need(mod.ModHeader.Stats.NextFormID == NextId, $"NextFormID is 0x{mod.ModHeader.Stats.NextFormID:X}, expected 0x{NextId:X}");
        var foreign = mod.EnumerateMajorRecords().Where(r => r.FormKey.ModKey != Plugin).Select(r => r.FormKey.ToString()).ToList();
        Need(foreign.Count == 0, $"plugin contains foreign override records: {string.Join(", ", foreign)}");
        var dupEdids = mod.EnumerateMajorRecords().Where(r => r.EditorID != null && coreIds.ContainsKey(r.EditorID)).Select(r => r.EditorID!).ToList();
        Need(dupEdids.Count == 0, $"plugin duplicates FO4SFCoreValues.esm EditorIDs: {string.Join(", ", dupEdids)}");

        // AVIF checks (only FO4SF_InWater stays local)
        Need(mod.ActorValueInformation.Count == 1, $"expected 1 AVIF, found {mod.ActorValueInformation.Count}");
        void CheckAvif(uint id, string edid, float max, ActorValueInformation.Flag flags)
        {
            var av = mod.ActorValueInformation.FirstOrDefault(a => a.FormKey == Own(id));
            Need(av != null && av.EditorID == edid && av.Type == ActorValueInformation.Types.Variable &&
                 av.DefaultValue == 0f && av.Min == 0f && av.Max == max && av.Flags == flags,
                 $"AVIF 0x{id:X} ({edid}) missing or mismatched");
        }
        CheckAvif(InWaterAvifId, InWaterAvifEdid, 1f, ZeroAvifFlags);

        // GLOB checks (only FO4SF_MutationsEnabled stays local)
        Need(mod.Globals.Count == 1, $"expected 1 GLOB, found {mod.Globals.Count}");
        void CheckGlob(uint id, string edid, float wantVal)
        {
            var g = mod.Globals.FirstOrDefault(x => x.FormKey == Own(id));
            Need(g != null && g.EditorID == edid && g.Data == wantVal && !g.MajorFlags.HasFlag(Global.MajorFlag.Constant),
                 $"GLOB 0x{id:X} ({edid}) is not non-constant {wantVal}");
        }
        CheckGlob(MutationsGlobId, MutationsGlobEdid, opts.MutationsDefault);

        // GPOF & GPOG checks
        Need(mod.GameplayOptions.Count == 2, $"expected 2 GPOF, found {mod.GameplayOptions.Count}");
        void CheckGpo(uint id, string edid, float defVal)
        {
            var gp = mod.GameplayOptions.FirstOrDefault(x => x.FormKey == Own(id));
            var fd = gp?.Data as IFloatGameplayOptionDataGetter;
            Need(gp != null && gp.EditorID == edid && fd != null && fd.Value1 == defVal && fd.Value2 == defVal &&
                 fd.Min == 0f && fd.Max == 1f && fd.Step == 1f && gp.Rewards.Count == 2,
                 $"GPOF 0x{id:X} ({edid}) missing or invalid FloatGameplayOptionData/Rewards");
        }
        CheckGpo(RadsRuleGpoId, RadsRuleGpoEdid, opts.DefaultRule);
        CheckGpo(MutationsGpoId, MutationsGpoEdid, opts.MutationsDefault);

        var gpog = mod.GameplayOptionsGroups.SingleOrDefault();
        var leaf = gpog?.Options as IGameplayOptionsGroupLeafGetter;
        Need(gpog != null && gpog.FormKey == Own(RadiationGpogId) && gpog.EditorID == RadiationGpogEdid &&
             leaf != null && leaf.GameplayOptions.Select(x => x.FormKey).SequenceEqual(new[] { Own(RadsRuleGpoId), Own(MutationsGpoId) }),
             "GPOG FO4SF_GPOG_Radiation does not list [FO4SF_GPO_RadsRule, FO4SF_GPO_Mutations]");

        // MGEF checks (every MGEF must carry SecondActorValue, empty Association, no conditions/scripts/keywords/resist)
        int wantMgefCount = 3 + (found.Mirror ? 2 : 0) + Mutations.Sum(m => m.Effects.Length);
        Need(mod.MagicEffects.Count == wantMgefCount, $"expected {wantMgefCount} MGEF, found {mod.MagicEffects.Count}");
        void CheckMgef(uint id, string edid, FormKey wantAv, CastType cast, TargetType target, bool? detrimental)
        {
            var m = mod.MagicEffects.FirstOrDefault(x => x.FormKey == Own(id));
            var arch = m?.Archetype as IMagicEffectArchetypeGetter;
            Need(m != null && m.EditorID == edid, $"MGEF 0x{id:X} ({edid}) missing");
            if (m == null) return;
            Need(arch?.Type == MagicEffectArchetype.TypeEnum.ValueModifier && arch.Association.IsNull,
                 $"MGEF {edid} is not ValueModifier with null Association");
            Need(m.SecondActorValue.FormKey == wantAv,
                 $"MGEF {edid} SecondActorValue (DATA word 14) is {m.SecondActorValue.FormKey}, not {wantAv}");
            Need(m.ResistValue.IsNull && m.MagicSkill.IsNull && m.ThirdActorValue.IsNull,
                 $"MGEF {edid} still carries a resist, skill or third actor value");
            Need(m.Conditions.Count == 0 && m.VirtualMachineAdapter == null && (m.Keywords?.Count ?? 0) == 0,
                 $"MGEF {edid} still carries conditions, script, or keywords");
            Need(m.CastType == cast && m.TargetType == target, $"MGEF {edid} cast/target is {m.CastType}/{m.TargetType}, expected {cast}/{target}");
            if (detrimental.HasValue)
                Need(m.Flags.HasFlag(MagicEffect.Flag.Detrimental) == detrimental.Value,
                     $"MGEF {edid} Detrimental flag is {!detrimental.Value}, expected {detrimental.Value}");
        }
        CheckMgef(RadsEffectId, RadsEffectEdid, Core(coreIds, RadsAvifEdid), CastType.FireAndForget, TargetType.Self, true);
        CheckMgef(RadsHazardEffectId, RadsHazardEffectEdid, Core(coreIds, RadsAvifEdid), CastType.FireAndForget, TargetType.Touch, true);
        CheckMgef(InWaterEffectId, InWaterEffectEdid, Own(InWaterAvifId), CastType.ConstantEffect, TargetType.Self, false);
        if (found.Mirror)
        {
            CheckMgef(RadAwayEffectId, RadAwayEffectEdid, Core(coreIds, RadsAvifEdid), found.RestoreEffect!.CastType, found.RestoreEffect.TargetType, false);
            CheckMgef(RadXEffectId, RadXEffectEdid, Core(coreIds, RadResistAvifEdid), found.RestoreEffect!.CastType, found.RestoreEffect.TargetType, false);
        }
        foreach (var ms in Mutations)
            foreach (var es in ms.Effects)
                CheckMgef(es.MgefId, es.MgefEdid, TargetAvKey(es.TargetAvEdid, sfAvifs, coreIds), CastType.ConstantEffect, TargetType.Self, es.Detrimental);

        // SPEL checks
        Need(mod.Spells.Count == 5 + Mutations.Length, $"expected {5 + Mutations.Length} SPEL, found {mod.Spells.Count}");
        void CheckSingleSpell(uint id, string edid, Spell.SpellType st, CastType ct, TargetType tt, uint mgefId, float mag, bool needWaterCond = false)
        {
            var sp = mod.Spells.FirstOrDefault(x => x.FormKey == Own(id));
            Need(sp != null && sp.EditorID == edid && sp.Type == st && sp.CastType == ct && sp.TargetType == tt &&
                 sp.VirtualMachineAdapter == null && (sp.Keywords?.Count ?? 0) == 0 &&
                 sp.Effects.Count == 1 && sp.Effects[0].BaseEffect.FormKey == Own(mgefId) &&
                 sp.Effects[0].Data?.Magnitude == mag && sp.Effects[0].Data?.Duration == 0,
                 $"SPEL 0x{id:X} ({edid}) invalid or mismatched effect");
            if (sp != null && needWaterCond)
            {
                var c = sp.Effects[0].Conditions.SingleOrDefault() as IConditionFloatGetter;
                Need(c != null && c.CompareOperator == CompareOperator.EqualTo && c.ComparisonValue == 1f && c.Data is IIsInWaterConditionDataGetter,
                     $"SPEL {edid} lacks IsInWater == 1 condition");
            }
        }
        CheckSingleSpell(RadsSpellId, RadsSpellEdid, Spell.SpellType.Spell, CastType.FireAndForget, TargetType.Self, RadsEffectId, SpellMagnitude);
        CheckSingleSpell(RadsHazardSpellId, RadsHazardSpellEdid, Spell.SpellType.Spell, CastType.FireAndForget, TargetType.Touch, RadsHazardEffectId, HazardSpellMagnitude);
        CheckSingleSpell(AbWaterDetectId, AbWaterDetectEdid, Spell.SpellType.Ability, CastType.ConstantEffect, TargetType.Self, InWaterEffectId, 1f, needWaterCond: true);
        CheckSingleSpell(WaterDrinkSpellId, WaterDrinkSpellEdid, Spell.SpellType.Spell, CastType.FireAndForget, TargetType.Self, RadsEffectId, DirtyWaterMagnitude);
        CheckSingleSpell(WaterContactSpellId, WaterContactSpellEdid, Spell.SpellType.Spell, CastType.FireAndForget, TargetType.Self, RadsEffectId, WaterContactMagnitude);

        // ALCH checks
        Need(mod.Ingestibles.Count == 4, $"expected 4 ALCH, found {mod.Ingestibles.Count}");
        void CheckAlch(uint id, string edid, uint mgefId, float mag, bool med)
        {
            var a = mod.Ingestibles.FirstOrDefault(x => x.FormKey == Own(id));
            Need(a != null && a.EditorID == edid && a.Addiction.IsNull && a.VirtualMachineAdapter == null &&
                 (a.Keywords?.Count ?? 0) == 0 && a.Flags.HasFlag(Ingestible.Flag.Medicine) == med &&
                 a.Effects.Count == 1 && a.Effects[0].BaseEffect.FormKey == Own(mgefId) &&
                 a.Effects[0].Data?.Magnitude == mag && a.Effects[0].Data?.Duration == 0,
                 $"ALCH 0x{id:X} ({edid}) invalid or mismatched effect");
        }
        CheckAlch(RadAwayId, RadAwayEdid, found.Mirror ? RadAwayEffectId : RadsEffectId, found.Mirror ? RadAwayMirrorMagnitude : RadAwayMagnitude, true);
        CheckAlch(RadXId, RadXEdid, found.Mirror ? RadXEffectId : RadsEffectId, found.Mirror ? RadXMagnitude : 0f, true);
        CheckAlch(IrradiatedFoodId, IrradiatedFoodEdid, RadsEffectId, IrradiatedFoodMagnitude, false);
        CheckAlch(DirtyWaterId, DirtyWaterEdid, RadsEffectId, DirtyWaterMagnitude, false);

        // HAZD, KYWD, ACTI, WATR checks
        var haz = mod.Hazards.SingleOrDefault();
        Need(haz != null && haz.FormKey == Own(RadsHazardId) && haz.EditorID == RadsHazardEdid &&
             haz.Effect.FormKey == Own(RadsHazardSpellId) && haz.Radius == HazardRadius && haz.TargetInterval == HazardInterval &&
             haz.Lifetime == 0f && haz.Flags.HasFlag(Hazard.Flag.AffectsPlayerOnly),
             "HAZD FO4SF_RadsHazard missing or does not reference FO4SF_RadsHazardSpell");

        var kw = mod.Keywords.SingleOrDefault();
        Need(kw != null && kw.FormKey == Own(RadsEmitterKwId) && kw.EditorID == RadsEmitterKwEdid, "KYWD FO4SF_Kw_RadsEmitter missing");

        var acti = mod.Activators.SingleOrDefault();
        Need(acti != null && acti.FormKey == Own(RadsEmitterId) && acti.EditorID == RadsEmitterEdid &&
             (acti.Keywords?.Select(k => k.FormKey).SequenceEqual(new[] { Own(RadsEmitterKwId) }) ?? false),
             "ACTI FO4SF_RadsEmitter missing or lacks FO4SF_Kw_RadsEmitter");

        var wat = mod.Waters.SingleOrDefault();
        Need(wat != null && wat.FormKey == Own(IrradiatedWaterId) && wat.EditorID == IrradiatedWaterEdid &&
             wat.Flags.HasFlag(Water.Flag.Dangerous) && wat.ConsumeSpell.FormKey == Own(WaterDrinkSpellId) &&
             wat.ContactSpell.FormKey == Own(WaterContactSpellId),
             "WATR FO4SF_IrradiatedWater missing or lacks Dangerous/ConsumeSpell/ContactSpell");

        // PERK & FLST checks
        Need(mod.Perks.Count == Mutations.Length + 1, $"expected {Mutations.Length + 1} PERK, found {mod.Perks.Count}");
        foreach (var ms in Mutations)
        {
            var pk = mod.Perks.FirstOrDefault(x => x.FormKey == Own(ms.PerkId));
            var ab = pk?.Ranks.SingleOrDefault()?.Effects.SingleOrDefault() as IPerkAbilityEffectGetter;
            var sp = mod.Spells.FirstOrDefault(x => x.FormKey == Own(ms.AbilityId));
            Need(pk != null && pk.EditorID == ms.PerkEdid && ab != null && ab.Ability.FormKey == Own(ms.AbilityId) &&
                 sp != null && sp.EditorID == ms.AbilityEdid && sp.Type == Spell.SpellType.Ability && sp.Effects.Count == ms.Effects.Length,
                 $"Mutation PERK {ms.PerkEdid} or its ability {ms.AbilityEdid} is invalid");
        }
        var sg = mod.Perks.FirstOrDefault(x => x.FormKey == Own(StarchedGenesId));
        Need(sg != null && sg.EditorID == StarchedGenesEdid && sg.Ranks.Count == 1, "PERK FO4SF_Perk_StarchedGenes missing");

        var flst = mod.FormLists.SingleOrDefault();
        Need(flst != null && flst.FormKey == Own(MutationPerksFlstId) && flst.EditorID == MutationPerksFlstEdid &&
             flst.Items.Select(i => i.FormKey).SequenceEqual(Mutations.Select(m => Own(m.PerkId))),
             "FLST FO4SF_MutationPerks does not list the 4 mutation PERKs in order");

        // QUST & script property checks
        var q = mod.Quests.SingleOrDefault();
        Need(q != null && q.FormKey == Own(QuestId) && q.EditorID == QuestEdid, "QUST FO4SF_RadsCoreQuest missing");
        if (q != null)
        {
            Need(q.Data?.Flags.HasFlag(Quest.Flag.StartGameEnabled) == true, "QUST is not StartGameEnabled");
            Need(q.Stages.Select(s => s.Index).SequenceEqual(Stages), $"QUST stages are not [{string.Join(",", Stages)}]");
            var scripts = q.VirtualMachineAdapter?.Scripts.ToList() ?? new();
            Need(scripts.Count == 1 && scripts[0].Name == ScriptName && scripts[0].Properties.Count == PropNames.Length,
                 $"QUST script is not {ScriptName} with {PropNames.Length} properties");
            if (scripts.Count == 1)
            {
                var gotNames = scripts[0].Properties.Select(p => p.Name).ToList();
                Need(gotNames.SequenceEqual(PropNames), $"script property order [{string.Join(",", gotNames)}] != [{string.Join(",", PropNames)}]");
                var map = scripts[0].Properties.OfType<IScriptObjectPropertyGetter>().ToDictionary(p => p.Name, p => p.Object.FormKey);
                foreach (var (name, wantFk) in ExpectedProperties(sfAvifs, coreIds))
                    Need(map.TryGetValue(name, out var fk) && fk == wantFk, $"property {name} is not {wantFk}");
            }
        }

        foreach (var p in problems) Console.WriteLine("FAIL  " + p);
        Console.WriteLine(problems.Count == 0 ? "all checks pass" : $"{problems.Count} problem(s)");
        return problems.Count == 0 ? 0 : 1;
    }

    // ---------------------------------------------------------------- fixture & selftest

    public static int Fixture(string outDir, string mode = "full")
    {
        if (mode is not ("full" or "spell" or "none")) throw new Refusal("fixture --mode must be full, spell, or none");
        var mod = new StarfieldMod(SfEsm, Release);
        mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;

        var avIds = new (uint Id, string Edid)[]
        {
            (0x0002D4, "Health"), (0x0002C2, "Strength"), (0x0002C4, "Endurance"), (0x0002C7, "Agility"),
            (0x0002C6, "Intelligence"), (0x0002DC, "CarryWeight"), (0x0002DA, "SpeedMult"),
            (0x0002E3, "DamageResist"), (0x0002EB, "EnergyResist"), (0x000358, "HealRateMult"),
            (0x20317B, "JumpSpeedMult"), (0x2D87C4, "PlayerReloadSpeedMult"), (0x00A02E, "SynthOther"),
        };
        foreach (var (id, edid) in avIds)
            mod.ActorValueInformation.Add(new ActorValueInformation(new FormKey(SfEsm, id), Release) { EditorID = edid, Name = edid });

        mod.Statics.Add(new Static(new FormKey(SfEsm, 0x000002), Release) { EditorID = "SynthPerkStatic" });

        if (mode != "none")
        {
            var dmgMg = new MagicEffect(new FormKey(SfEsm, 0x00A100), Release)
            {
                EditorID = "DamageHealthContact", Name = "Damage Health",
                Archetype = new MagicEffectArchetype(MagicEffectArchetype.TypeEnum.ValueModifier),
                CastType = CastType.FireAndForget, TargetType = TargetType.Self,
                Flags = MagicEffect.Flag.Hostile | MagicEffect.Flag.Detrimental | MagicEffect.Flag.NoDuration | MagicEffect.Flag.NoArea,
            };
            dmgMg.SecondActorValue.SetTo(new FormKey(SfEsm, 0x0002D4));
            dmgMg.ResistValue.SetTo(new FormKey(SfEsm, 0x00A02E));
            mod.MagicEffects.Add(dmgMg);

            var dmgSp = new Spell(new FormKey(SfEsm, 0x29AAE9), Release)
            {
                EditorID = "DamageHealthSpell", Name = "Damage Health",
                Type = Spell.SpellType.Spell, CastType = CastType.FireAndForget, TargetType = TargetType.Self,
                Flags = Spell.Flag.ManualCostCalc,
            };
            dmgSp.EquipmentType.SetTo(new FormKey(SfEsm, 0x013F44));
            dmgSp.Effects.Add(new Effect { BaseEffect = new FormLinkNullable<IMagicEffectGetter>(dmgMg.FormKey), Data = new EffectData { Magnitude = 40f, Duration = 0 }, MAGF = 70, EFIF = 80, MUID = 90 });
            mod.Spells.Add(dmgSp);

            var touchMg = new MagicEffect(new FormKey(SfEsm, 0x00A101), Release)
            {
                EditorID = "SpaceDistortionCloudHazardEffect", Name = "Synth Hazard Effect",
                Archetype = new MagicEffectArchetype(MagicEffectArchetype.TypeEnum.ValueModifier),
                CastType = CastType.FireAndForget, TargetType = TargetType.Touch,
                Flags = MagicEffect.Flag.Detrimental | MagicEffect.Flag.NoDuration | MagicEffect.Flag.NoArea,
            };
            touchMg.SecondActorValue.SetTo(new FormKey(SfEsm, 0x00A02E));
            mod.MagicEffects.Add(touchMg);

            var touchSp = new Spell(new FormKey(SfEsm, 0x1FAC9F), Release)
            {
                EditorID = "SpaceDistortionCloudHazardSpell", Name = "Synth Hazard Spell",
                Type = Spell.SpellType.Spell, CastType = CastType.FireAndForget, TargetType = TargetType.Touch,
            };
            touchSp.EquipmentType.SetTo(new FormKey(SfEsm, 0x013F44));
            touchSp.Effects.Add(new Effect { BaseEffect = new FormLinkNullable<IMagicEffectGetter>(touchMg.FormKey), Data = new EffectData { Magnitude = 3f, Duration = 0 }, EFIF = 0, MUID = 1 });
            mod.Spells.Add(touchSp);

            var abMg = new MagicEffect(new FormKey(SfEsm, 0x00A102), Release)
            {
                EditorID = "SynthAbFortifyEffect", Name = "Synth Ability Effect",
                Archetype = new MagicEffectArchetype(MagicEffectArchetype.TypeEnum.ValueModifier),
                CastType = CastType.ConstantEffect, TargetType = TargetType.Self,
                Flags = MagicEffect.Flag.Recover | MagicEffect.Flag.NoDuration | MagicEffect.Flag.NoArea,
            };
            abMg.SecondActorValue.SetTo(new FormKey(SfEsm, 0x00A02E));
            mod.MagicEffects.Add(abMg);

            var abSp = new Spell(new FormKey(SfEsm, 0x285E40), Release)
            {
                EditorID = "abCrewAstrodynamics_01", Name = "Synth Ability",
                Type = Spell.SpellType.Ability, CastType = CastType.ConstantEffect, TargetType = TargetType.Self,
            };
            abSp.EquipmentType.SetTo(new FormKey(SfEsm, 0x013F44));
            abSp.Effects.Add(new Effect { BaseEffect = new FormLinkNullable<IMagicEffectGetter>(abMg.FormKey), Data = new EffectData { Magnitude = 1f, Duration = 0 }, EFIF = 1, MUID = 2 });
            mod.Spells.Add(abSp);

            var restoreMg = new MagicEffect(new FormKey(SfEsm, 0x00A104), Release)
            {
                EditorID = "SynthRestoreHealthEffect", Name = "Synth Restore",
                Archetype = new MagicEffectArchetype(MagicEffectArchetype.TypeEnum.ValueModifier),
                CastType = CastType.FireAndForget, TargetType = TargetType.Self,
                Flags = MagicEffect.Flag.NoDuration | MagicEffect.Flag.HideInUI,
            };
            restoreMg.SecondActorValue.SetTo(new FormKey(SfEsm, 0x0002D4));
            mod.MagicEffects.Add(restoreMg);

            var restoreEntry = new Effect { BaseEffect = new FormLinkNullable<IMagicEffectGetter>(restoreMg.FormKey), Data = new EffectData { Magnitude = 25f, Duration = 0 }, MAGF = 4, EFIF = 5, MUID = 6 };
            if (mode == "full")
            {
                var aid = new Ingestible(new FormKey(SfEsm, 0x00A105), Release)
                {
                    EditorID = "SynthRestoreAid", Name = "Synth Aid", Flags = Ingestible.Flag.Medicine, MajorFlags = Ingestible.MajorFlag.Medicine,
                    Model = new Model { File = @"Meshes\Synth\Aid.nif" },
                };
                aid.Effects.Add(restoreEntry);
                mod.Ingestibles.Add(aid);
            }
            else
            {
                var timedAid = new Ingestible(new FormKey(SfEsm, 0x00A105), Release)
                {
                    EditorID = "ShipRepairKit", Name = "Synth Timed Aid", Flags = Ingestible.Flag.Medicine, MajorFlags = Ingestible.MajorFlag.Medicine,
                    Model = new Model { File = @"Meshes\Synth\Kit.nif" },
                };
                timedAid.Effects.Add(new Effect { BaseEffect = new FormLinkNullable<IMagicEffectGetter>(dmgMg.FormKey), Data = new EffectData { Magnitude = 10f, Duration = 10 }, MAGF = 1, EFIF = 2, MUID = 3 });
                mod.Ingestibles.Add(timedAid);

                var rSpell = new Spell(new FormKey(SfEsm, 0x1E1171), Release)
                {
                    EditorID = "Dueling_RestoreHealth_Spell", Name = "Synth Restore Spell",
                    Type = Spell.SpellType.Spell, CastType = CastType.FireAndForget, TargetType = TargetType.Self,
                };
                rSpell.Effects.Add(restoreEntry);
                mod.Spells.Add(rSpell);
            }

            mod.Hazards.Add(new Hazard(new FormKey(SfEsm, 0x047386), Release)
            {
                EditorID = "ENV_PoolHazard_Radiation", Name = "Synth Pool", ObjectBounds = new ObjectBounds(),
                Model = new Model { File = @"Meshes\Markers\SynthHazard.nif" },
                Effect = new FormLinkNullable<IEffectRecordGetter>(touchSp.FormKey), Radius = 5f, TargetInterval = 0.3f,
            });
            mod.Waters.Add(new Water(new FormKey(SfEsm, 0x000018), Release)
            {
                EditorID = "WaterClear", Name = "Synth Water", Opacity = 80,
            });
            mod.Activators.Add(new SF.Activator(new FormKey(SfEsm, 0x00573F), Release)
            {
                EditorID = "EmptyTrigger", ObjectBounds = new ObjectBounds(),
            });
        }

        Directory.CreateDirectory(outDir);
        var path = Path.Combine(outDir, "Starfield.esm");
        mod.BeginWrite.ToPath(path).WithNoLoadOrder().NoCheckIfLowerRangeDisallowed().Write();
        Console.WriteLine($"wrote {path} (mode={mode})");
        return 0;
    }

    public static int SelfTest(string scratchDir)
    {
        if (Directory.Exists(scratchDir)) Directory.Delete(scratchDir, true);
        Directory.CreateDirectory(scratchDir);

        void Must(int rc, string step) { if (rc != 0) throw new Refusal($"selftest failed at {step} (rc={rc})"); }
        void MustFail(int rc, string step) { if (rc == 0) throw new Refusal($"selftest expected failure at {step}, but Check returned 0"); }

        foreach (var mode in new[] { "full", "spell", "none" })
        {
            var mDir = Path.Combine(scratchDir, "m_" + mode);
            var bDir = Path.Combine(scratchDir, "b_" + mode);
            Must(Fixture(mDir, mode), $"fixture {mode}");
            var sfPath = Path.Combine(mDir, "Starfield.esm");
            Must(Build(sfPath, bDir, new BuildOptions(0, 0)), $"build {mode}");
            Must(Check(Path.Combine(bDir, Plugin.FileName), sfPath, new BuildOptions(0, 0)), $"check {mode}");
        }

        // Option variants
        var sfFull = Path.Combine(scratchDir, "m_full", "Starfield.esm");
        var bOpt = Path.Combine(scratchDir, "b_opt");
        Must(Build(sfFull, bOpt, new BuildOptions(1, 1)), "build opts(1,1)");
        Must(Check(Path.Combine(bOpt, Plugin.FileName), sfFull, new BuildOptions(1, 1)), "check opts(1,1)");
        MustFail(Check(Path.Combine(bOpt, Plugin.FileName), sfFull, new BuildOptions(0, 0)), "check opts mismatch");

        // Corrupt-plugin negative controls
        var goodPlugin = Path.Combine(scratchDir, "b_full", Plugin.FileName);

        void TamperAndExpectRefusal(string name, Action<StarfieldMod> mutate)
        {
            using var ro = OpenMod(goodPlugin, SfEsm, CoreValuesEsm);
            var copy = new StarfieldMod(Plugin, Release);
            copy.DeepCopyIn(ro);
            mutate(copy);
            var dir = Path.Combine(scratchDir, "bad_" + name);
            WriteMod(copy, dir);
            MustFail(Check(Path.Combine(dir, Plugin.FileName), sfFull, new BuildOptions(0, 0)), "tamper " + name);
        }

        TamperAndExpectRefusal("mgef_av", m => m.MagicEffects.First(x => x.FormKey == Own(RadsEffectId)).SecondActorValue.SetToNull());
        TamperAndExpectRefusal("avif_flag", m => m.ActorValueInformation.First(x => x.FormKey == Own(InWaterAvifId)).Flags = RadsAvifFlags);
        TamperAndExpectRefusal("dup_core_avif", m => m.ActorValueInformation.Add(new ActorValueInformation(Own(0x800), Release) { EditorID = RadsAvifEdid }));
        TamperAndExpectRefusal("hazd_spell", m => m.Hazards.First().Effect.SetTo(Own(RadsSpellId)));
        TamperAndExpectRefusal("watr_flag", m => m.Waters.First().Flags = 0);
        TamperAndExpectRefusal("gpo_rewards", m => m.GameplayOptions.First().Rewards.Clear());
        TamperAndExpectRefusal("flst_order", m => m.FormLists.First().Items!.RemoveAt(0));
        TamperAndExpectRefusal("foreign_override", m => m.Globals.Add(new Global(new FormKey(SfEsm, 0x00A039), Release) { EditorID = "SynthForeignGlob", Data = 1f }));

        Console.WriteLine("selftest: ok (all modes, options, and 8 tamper controls passed)");
        return 0;
    }
}
