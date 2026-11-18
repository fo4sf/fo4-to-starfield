// PowerArmorCore: Fallout 4 climb-in Power Armor frame + 6-limb BPTD + FusionCore drain + outfit restore + FNV Salvaged NCR worn ARMO.
//
// Writes FO4SFPowerArmor.esm (masters Starfield.esm, FO4SFCoreValues.esm; adds records, overrides zero vanilla records by default, or
// overrides the 5 empty PowerArmor*_DO DFOB records when --override-dfob is explicitly passed; omits FO4SF_PATestCell when --no-test-cell is passed):
//   CELL  0x800  FO4SF_PATestCell                 interior test cell (`coc FO4SF_PATestCell`, omitted under --no-test-cell)
//   FURN  0x801  FO4SF_PowerArmorFrameFurn        climb-in frame furniture (cloned from control chair + FO4SF_Kw_PowerArmorFrameFurn; + PA keywords with --override-dfob)
//   RACE  0x802  FO4SF_PowerArmorRace             cloned from HumanRace, wired to FO4SF_PowerArmorBodyPartData and FO4SF_PowerArmorSkin (own skin + ARMA copies)
//   BPTD  0x803  FO4SF_PowerArmorBodyPartData     cloned from HumanBodyPartData with 6 limb condition AVIFs (0x810..0x815) bound at 100% HealthPercent
//   ARMO  0x804  FO4SF_PowerArmorSkin             cloned from Skin_Naked with cloned ARMAs naming both HumanRace and FO4SF_PowerArmorRace
//   QUST  0x805  FO4SF_PowerArmorCoreQuest        StartGameEnabled quest, stages 10/20/30/40, script FO4SF_PowerArmorCoreQuest (SpecialAgilityAV, TestModeGlobal)
//   KYWD  0x806  FO4SF_PAArmorKeyword             power armor modular piece keyword
//   KYWD  0x807  FO4SF_Kw_SalvagedPowerArmor      FNV salvaged worn heavy armor keyword (no frame, no climb-in, no FusionCore drain)
//   KYWD  0x808  FO4SF_Kw_PowerArmorFrameFurn     identifies climb-in frame furniture references anywhere in the world
//   MISC  0x809  FO4SF_FusionCore                 battery item carrying vanilla isPowerArmorBattery in Keywords and KeywordFormComponent
//   AVIF  0x80A  FO4SF_PAInPowerArmor             0..1 state flag (1 while in climb-in frame, stays 0 when wearing salvaged NCR armor)
//   AVIF  0x80B  FO4SF_PAFusionCharge             0..100 active Fusion Core charge
//   AVIF  0x810..0x815  FO4SF_PACond_*            6 limb condition AVIFs (Head, Torso, LeftArm, RightArm, LeftLeg, RightLeg; 0..100, default 100)
//   ARMO  0x816..0x819  FO4SF_PAFrameArmor / PATorso / PAHelmet / PAPack  4 disjoint slots (BODY, SSBODY, SSHelmet, SSBackpack) + cloned ARMAs for PA race
//   ARMO  0x81A..0x81B  FO4SF_SalvagedNCRPowerArmor / Helmet              plain worn heavy ARMO on HumanRace (high ballistic DR, -1 AGI ENCH, zero frame kw)
//   ENCH  0x81C  FO4SF_Ench_SalvagedNCRAgility    constant self -1 Agility enchantment on FO4SF_SalvagedNCRPowerArmor
//   MGEF  0x81D  FO4SF_Mgef_SalvagedNCRAgility    ValueModifier detrimental effect targeting FO4SFCoreValues.esm FO4SF_Special_Agility (0x815)
//
// usage:
//   PowerArmorCore build <Starfield.esm> <out_dir> [--control <FURN edid>] [--override-dfob] [--no-test-cell] [--json <core_values.json>]
//   PowerArmorCore check <FO4SFPowerArmor.esm> <Starfield.esm> [--control <FURN edid>] [--override-dfob] [--no-test-cell] [--json <core_values.json>]
//   PowerArmorCore fixture <out_dir>
//   PowerArmorCore selftest <scratch_dir>
using System.Globalization;
using System.Text.Json;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;

try
{
    var rest = args.ToList();
    string control = PowerArmorCore.DefaultControlEdid;
    string? Take(string flag)
    {
        int j = rest.IndexOf(flag);
        if (j < 0) return null;
        if (j + 1 >= rest.Count) throw new PowerArmorCore.Refusal(flag + " needs a value");
        var v = rest[j + 1];
        rest.RemoveRange(j, 2);
        return v;
    }
    control = Take("--control") ?? control;
    string? jsonPath = Take("--json");
    bool overrideDfob = rest.Remove("--override-dfob");
    bool noTestCell = rest.Remove("--no-test-cell");
    if (rest.Count == 3 && rest[0] == "build") return PowerArmorCore.Build(rest[1], rest[2], control, overrideDfob, noTestCell, jsonPath);
    if (rest.Count == 3 && rest[0] == "check") return PowerArmorCore.Check(rest[1], rest[2], control, overrideDfob, noTestCell, jsonPath);
    if (rest.Count == 2 && rest[0] == "fixture") return PowerArmorCore.Fixture(rest[1]);
    if (rest.Count == 2 && rest[0] == "selftest") return PowerArmorCore.SelfTest(rest[1]);
}
catch (PowerArmorCore.Refusal r)
{
    Console.Error.WriteLine("refused: " + r.Message);
    return 1;
}
Console.Error.WriteLine(
    "usage: PowerArmorCore build <Starfield.esm> <out_dir> [--control <edid>] [--override-dfob] [--no-test-cell] [--json <core_values.json>] | " +
    "check <plugin> <Starfield.esm> [--control <edid>] [--override-dfob] [--no-test-cell] [--json <core_values.json>] | fixture <out_dir> | selftest <scratch_dir>");
return 2;

static class PowerArmorCore
{
    public sealed class Refusal(string m) : Exception(m);

    const StarfieldRelease Release = StarfieldRelease.Starfield;
    static readonly ModKey SfEsm = ModKey.FromFileName("Starfield.esm");
    static readonly ModKey CoreValuesEsm = ModKey.FromFileName("FO4SFCoreValues.esm");
    public static readonly ModKey Plugin = ModKey.FromFileName("FO4SFPowerArmor.esm");

    // Fixed local FormIDs (held equal by scripts/powerarmor/FO4SF_PowerArmorCoreQuest.psc and tests/test_power_armor_core.py)
    const uint CellId = 0x800, FrameFurnId = 0x801, RaceId = 0x802, BodyPartDataId = 0x803, SkinId = 0x804,
        QuestId = 0x805, ArmorKeywordId = 0x806, SalvagedKeywordId = 0x807, FrameFurnKeywordId = 0x808,
        FusionCoreId = 0x809, InPaAvId = 0x80A, FusionChargeAvId = 0x80B;
    const uint CondHeadId = 0x810, CondTorsoId = 0x811, CondLeftArmId = 0x812, CondRightArmId = 0x813,
        CondLeftLegId = 0x814, CondRightLegId = 0x815;
    const uint FrameArmorId = 0x816, PaTorsoId = 0x817, PaHelmetId = 0x818, PaPackId = 0x819,
        SalvagedBodyId = 0x81A, SalvagedHelmId = 0x81B, SalvagedAgiEnchId = 0x81C, SalvagedAgiMgefId = 0x81D;
    const uint ArrivalRefId = 0x820, CocRefId = 0x821, FrameFurnRefId = 0x822, ExitChairRefId = 0x823,
        CoreRef1Id = 0x824, CoreRef2Id = 0x825, CoreRef3Id = 0x826, SalvagedBodyRefId = 0x827, SalvagedHelmRefId = 0x828;
    const uint FirstCloneArmaId = 0x830, FirstTileId = 0x860;

    public const string DefaultControlEdid = "NPCChairTech03_Free_270";
    const string CellEdid = "FO4SF_PATestCell",
        FrameFurnEdid = "FO4SF_PowerArmorFrameFurn",
        RaceEdid = "FO4SF_PowerArmorRace",
        BodyPartDataEdid = "FO4SF_PowerArmorBodyPartData",
        SkinEdid = "FO4SF_PowerArmorSkin",
        QuestEdid = "FO4SF_PowerArmorCoreQuest",
        QuestScript = "FO4SF_PowerArmorCoreQuest",
        ArmorKeywordEdid = "FO4SF_PAArmorKeyword",
        SalvagedKeywordEdid = "FO4SF_Kw_SalvagedPowerArmor",
        FrameFurnKeywordEdid = "FO4SF_Kw_PowerArmorFrameFurn",
        FusionCoreEdid = "FO4SF_FusionCore",
        InPaAvEdid = "FO4SF_PAInPowerArmor",
        FusionChargeAvEdid = "FO4SF_PAFusionCharge",
        FrameArmorEdid = "FO4SF_PAFrameArmor",
        PaTorsoEdid = "FO4SF_PATorso",
        PaHelmetEdid = "FO4SF_PAHelmet",
        PaPackEdid = "FO4SF_PAPack",
        SalvagedBodyEdid = "FO4SF_SalvagedNCRPowerArmor",
        SalvagedHelmEdid = "FO4SF_SalvagedNCRPowerHelmet",
        SalvagedAgiEnchEdid = "FO4SF_Ench_SalvagedNCRAgility",
        SalvagedAgiMgefEdid = "FO4SF_Mgef_SalvagedNCRAgility";

    // Vanilla template EditorIDs looked up in Starfield.esm (or synthetic fixture)
    const string HumanRaceEdid = "HumanRace",
        HumanBptdEdid = "HumanBodyPartData",
        SkinNakedEdid = "Skin_Naked",
        FrameClothesEdid = "Clothes_Crowd_Akila_Fatigues_01_NOTPLAYABLE",
        Mark1BodyEdid = "Spacesuit_Mark1_Body",
        Mark1HelmetEdid = "Spacesuit_Mark1_Helmet",
        Mark1PackEdid = "Spacesuit_Mark1_Backpack",
        BatteryMiscEdid = "Mfg_Tier02_PositronBattery",
        FurnPaKeywordEdid = "FurnitureTypePowerArmor",
        FrameKeywordEdid = "isPowerArmorFrame",
        BatteryKeywordEdid = "isPowerArmorBattery",
        AgilityAvEdid = "Agility",
        CarryWeightAvEdid = "CarryWeight",
        SpeedMultAvEdid = "SpeedMult";

    static readonly (uint Id, string Edid, string Label, BodyPart.PartType[] Parts)[] LimbSpecs =
    {
        (CondHeadId, "FO4SF_PACond_Head", "FO4SF PA Head Condition", new[] { BodyPart.PartType.Head1 }),
        (CondTorsoId, "FO4SF_PACond_Torso", "FO4SF PA Torso Condition", new[] { BodyPart.PartType.Torso }),
        (CondLeftArmId, "FO4SF_PACond_LeftArm", "FO4SF PA Left Arm Condition", new[] { BodyPart.PartType.LeftArm1 }),
        (CondRightArmId, "FO4SF_PACond_RightArm", "FO4SF PA Right Arm Condition", new[] { BodyPart.PartType.RightArm1 }),
        (CondLeftLegId, "FO4SF_PACond_LeftLeg", "FO4SF PA Left Leg Condition", new[] { BodyPart.PartType.LeftLeg1, BodyPart.PartType.LeftFoot }),
        (CondRightLegId, "FO4SF_PACond_RightLeg", "FO4SF PA Right Leg Condition", new[] { BodyPart.PartType.RightLeg1, BodyPart.PartType.RightFoot }),
    };

    static readonly (string DfobEdid, uint TargetLocalId)[] DfobTargets =
    {
        ("PowerArmorRace_DO", RaceId),
        ("PowerArmorDefaultFrameFurniture_DO", FrameFurnId),
        ("PowerArmorDefaultFrameArmor_DO", FrameArmorId),
        ("PowerArmorArmorKeyword_DO", ArmorKeywordId),
        ("PowerArmorDefaultBatteryObject_DO", FusionCoreId),
    };

    // Proven TestCell vanilla statics/lights/templates
    const uint FloorStat = 0x050776, OmniLight = 0x03D38C, CocMarker = 0x000032, XMarker = 0x00003B,
        LightingTemplate = 0x006658, ImageSpace = 0x122393;
    const float TileStep = 8f, LightZ = 4f;
    static readonly P3Float CocPos = new(-5f, 0f, 0.1f), FramePos = new(3f, 0f, 0f), ExitChairPos = new(0f, 3f, 0f);
    static readonly ushort[] QuestStages = { 10, 20, 30, 40 };

    // 27-byte ENIT header used by constant-effect self armor enchantments in Starfield.esm (word offset 14 = 0x06 ConstantEffect/Self)
    static readonly byte[] ConstantSelfEnit =
    {
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x06, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00,
    };

    const string SpecialAgilityEdid = "FO4SF_Special_Agility",
        TestModeEdid = "FO4SF_TestModeEnabled";

    static FormKey Own(uint id) => new(Plugin, id);
    static FormKey Sf(uint id) => new(SfEsm, id);

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

    static ScriptObjectProperty ObjProp(string name, FormKey fk) => new()
    {
        Name = name, Flags = ScriptProperty.Flag.Edited, Object = new FormLink<IStarfieldMajorRecordGetter>(fk),
    };

    static IStarfieldModDisposableGetter OpenTemplate(string path)
    {
        var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        styles.Set(new KeyedMasterStyle(SfEsm, MasterStyle.Full));
        return StarfieldMod.CreateFromBinaryOverlay(path, Release, new BinaryReadParameters { MasterFlagsLookup = styles });
    }

    static IStarfieldModDisposableGetter OpenPlugin(string path)
    {
        var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        styles.Set(new KeyedMasterStyle(SfEsm, MasterStyle.Full));
        styles.Set(new KeyedMasterStyle(CoreValuesEsm, MasterStyle.Full));
        return StarfieldMod.CreateFromBinaryOverlay(path, Release, new BinaryReadParameters { MasterFlagsLookup = styles });
    }

    static T One<T>(IEnumerable<T> items, string edid, string what) where T : IMajorRecordGetter
    {
        var hits = items.Where(x => string.Equals(x.EditorID, edid, StringComparison.OrdinalIgnoreCase)).ToList();
        if (hits.Count != 1) throw new Refusal($"{hits.Count} {what} named {edid} in Starfield.esm (one needed)");
        return hits[0];
    }

    static void SyncKeywordsAndAdd(
        ref ExtendedList<IFormLinkGetter<IKeywordGetter>>? list,
        ExtendedList<AComponent> components,
        params FormKey[] addKeys)
    {
        list ??= new ExtendedList<IFormLinkGetter<IKeywordGetter>>();
        var comp = components.OfType<KeywordFormComponent>().FirstOrDefault();
        if (comp == null)
        {
            comp = new KeywordFormComponent();
            components.Add(comp);
        }
        comp.Keywords ??= new ExtendedList<IFormLinkGetter<IKeywordGetter>>();
        foreach (var existing in list)
        {
            if (!comp.Keywords.Any(x => x.FormKey == existing.FormKey))
                comp.Keywords.Add(new FormLink<IKeywordGetter>(existing.FormKey));
        }
        foreach (var k in addKeys)
        {
            if (!list.Any(x => x.FormKey == k))
                list.Add(new FormLink<IKeywordGetter>(k));
            if (!comp.Keywords.Any(x => x.FormKey == k))
                comp.Keywords.Add(new FormLink<IKeywordGetter>(k));
        }
    }

    static void CloneArmaturesForPaRace(
        StarfieldMod mod,
        Dictionary<FormKey, IArmorAddonGetter> sfArmas,
        Armor target,
        FormKey humanRaceKey,
        FormKey paRaceKey,
        Dictionary<FormKey, FormKey> armaMap,
        ref uint nextArmaId)
    {
        if (target.Armatures == null || target.Armatures.Count == 0)
            throw new Refusal($"{target.EditorID} has zero armatures to bind to {RaceEdid}");

        foreach (var addonEntry in target.Armatures)
        {
            if (addonEntry.ArmorAddon.FormKeyNullable is not { } srcFk || !sfArmas.TryGetValue(srcFk, out var srcArma))
                throw new Refusal($"{target.EditorID} references missing ARMA {addonEntry.ArmorAddon.FormKeyNullable}");

            if (!armaMap.TryGetValue(srcFk, out var clonedFk))
            {
                clonedFk = Own(nextArmaId++);
                var cloned = (ArmorAddon)srcArma.Duplicate(clonedFk);
                cloned.EditorID = $"FO4SF_AA_{srcArma.EditorID ?? srcFk.ID.ToString("X6", CultureInfo.InvariantCulture)}";
                if (cloned.Race.IsNull)
                    cloned.Race.SetTo(humanRaceKey);
                if (cloned.Race.FormKey != humanRaceKey && !cloned.AdditionalRaces.Any(r => r.FormKey == humanRaceKey))
                    cloned.AdditionalRaces.Add(new FormLink<IRaceGetter>(humanRaceKey));
                if (cloned.Race.FormKey != paRaceKey && !cloned.AdditionalRaces.Any(r => r.FormKey == paRaceKey))
                    cloned.AdditionalRaces.Add(new FormLink<IRaceGetter>(paRaceKey));
                mod.ArmorAddons.Add(cloned);
                armaMap[srcFk] = clonedFk;
            }
            addonEntry.ArmorAddon.SetTo(clonedFk);
        }
    }

    static Armor DuplicateArmorClean(IArmorGetter src, uint localId, string edid, string plainName)
    {
        var a = (Armor)src.Duplicate(Own(localId));
        a.EditorID = edid;
        a.Name = plainName;
        a.Description = null;
        a.VirtualMachineAdapter = null;
        return a;
    }

    static void BoostArmorDefense(Armor a, ushort armorRating, uint primaryResistance)
    {
        a.ArmorRating = armorRating;
        if (a.Resistances != null && a.Resistances.Count > 0)
        {
            a.Resistances[0].Value = primaryResistance;
        }
    }

    // ---------------------------------------------------------------- build

    public static int Build(string templatePath, string outDir, string controlEdid, bool overrideDfob, bool noTestCell = false, string? jsonPath = null)
    {
        var coreIds = LoadCoreValues(jsonPath);
        var specialAgilityKey = Core(coreIds, SpecialAgilityEdid);
        var testModeKey = Core(coreIds, TestModeEdid);

        using var sf = OpenTemplate(templatePath);
        var humanRace = One(sf.Races, HumanRaceEdid, "RACE");
        var humanBptd = One(sf.BodyParts, HumanBptdEdid, "BPTD");
        var skinNaked = One(sf.Armors, SkinNakedEdid, "ARMO");
        var frameTmpl = One(sf.Armors, FrameClothesEdid, "ARMO");
        var bodyTmpl = One(sf.Armors, Mark1BodyEdid, "ARMO");
        var helmTmpl = One(sf.Armors, Mark1HelmetEdid, "ARMO");
        var packTmpl = One(sf.Armors, Mark1PackEdid, "ARMO");
        var batteryTmpl = One(sf.MiscItems, BatteryMiscEdid, "MISC");
        var controlFurn = One(sf.Furniture, controlEdid, "FURN");
        var furnPaKw = One(sf.Keywords, FurnPaKeywordEdid, "KYWD");
        var frameKw = One(sf.Keywords, FrameKeywordEdid, "KYWD");
        var batteryKw = One(sf.Keywords, BatteryKeywordEdid, "KYWD");
        _ = One(sf.ActorValueInformation, AgilityAvEdid, "AVIF");
        _ = One(sf.ActorValueInformation, CarryWeightAvEdid, "AVIF");
        _ = One(sf.ActorValueInformation, SpeedMultAvEdid, "AVIF");

        if (controlFurn.Keywords?.Any(k => k.FormKey == furnPaKw.FormKey) == true)
            throw new Refusal($"{controlEdid} already carries {FurnPaKeywordEdid}: cannot serve as clean control chair");

        var sfArmas = sf.ArmorAddons.ToDictionary(a => a.FormKey);
        var armaMap = new Dictionary<FormKey, FormKey>();
        uint nextArmaId = FirstCloneArmaId;

        var mod = new StarfieldMod(Plugin, Release);
        mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        mod.ModHeader.Author = "fo4-to-starfield";

        // 1. Keywords
        mod.Keywords.Add(new Keyword(Own(ArmorKeywordId), Release) { EditorID = ArmorKeywordEdid });
        mod.Keywords.Add(new Keyword(Own(SalvagedKeywordId), Release) { EditorID = SalvagedKeywordEdid });
        mod.Keywords.Add(new Keyword(Own(FrameFurnKeywordId), Release) { EditorID = FrameFurnKeywordEdid });

        // 2. State, FusionCharge, and 6 Limb Condition AVIFs
        mod.ActorValueInformation.Add(new ActorValueInformation(Own(InPaAvId), Release)
        {
            EditorID = InPaAvEdid,
            Name = "FO4SF In Power Armor",
            Type = ActorValueInformation.Types.Variable,
            Flags = ActorValueInformation.Flag.DefaultToZero,
            DefaultValue = 0f,
            Min = 0f,
            Max = 1f,
        });
        mod.ActorValueInformation.Add(new ActorValueInformation(Own(FusionChargeAvId), Release)
        {
            EditorID = FusionChargeAvEdid,
            Name = "FO4SF Fusion Core Charge",
            Type = ActorValueInformation.Types.Variable,
            Flags = ActorValueInformation.Flag.DefaultToZero,
            DefaultValue = 0f,
            Min = 0f,
            Max = 100f,
        });
        foreach (var (id, edid, label, _) in LimbSpecs)
        {
            mod.ActorValueInformation.Add(new ActorValueInformation(Own(id), Release)
            {
                EditorID = edid,
                Name = label,
                Type = ActorValueInformation.Types.Variable,
                DefaultValue = 100f,
                Min = 0f,
                Max = 100f,
            });
        }

        // 3. 6-Limb BodyPartData (cloned from HumanBodyPartData 0x00003481)
        var bptd = (BodyPartData)humanBptd.Duplicate(Own(BodyPartDataId));
        bptd.EditorID = BodyPartDataEdid;
        foreach (var (id, edid, _, partTypes) in LimbSpecs)
        {
            int matched = 0;
            foreach (var part in bptd.Parts.Where(p => partTypes.Contains(p.Type)))
            {
                part.Name = null;
                part.ActorValue.SetTo(Own(id));
                part.HealthPercent = new Percent(1.0);
                matched++;
            }
            if (matched == 0)
                throw new Refusal($"{HumanBptdEdid} has no BodyPart matching {edid} ({string.Join(",", partTypes)})");
        }
        foreach (var part in bptd.Parts)
            part.Name = null;
        mod.BodyParts.Add(bptd);

        // 4. PowerArmorSkin + PowerArmorRace (solving f5d38adb missing third-person body/skin)
        var paSkin = (Armor)skinNaked.Duplicate(Own(SkinId));
        paSkin.EditorID = SkinEdid;
        paSkin.Name = null;
        paSkin.Description = null;
        paSkin.VirtualMachineAdapter = null;
        paSkin.Race.SetTo(humanRace.FormKey);
        CloneArmaturesForPaRace(mod, sfArmas, paSkin, humanRace.FormKey, Own(RaceId), armaMap, ref nextArmaId);
        mod.Armors.Add(paSkin);

        var paRace = (Race)humanRace.Duplicate(Own(RaceId));
        paRace.EditorID = RaceEdid;
        paRace.Name = "FO4SF Power Armor Race";
        paRace.Description = string.Empty;
        paRace.BodyPartData.SetTo(Own(BodyPartDataId));
        paRace.Skin.SetTo(Own(SkinId));
        paRace.ArmorRace.SetTo(humanRace.FormKey);
        mod.Races.Add(paRace);

        // 5. Climb-In Frame Furniture
        var frameFurn = (Furniture)controlFurn.Duplicate(Own(FrameFurnId));
        frameFurn.EditorID = FrameFurnEdid;
        frameFurn.Name = "FO4SF Power Armor Frame";
        frameFurn.VirtualMachineAdapter = null;
        var furnKws = frameFurn.Keywords;
        if (overrideDfob)
            SyncKeywordsAndAdd(ref furnKws, frameFurn.Components, Own(FrameFurnKeywordId), furnPaKw.FormKey, frameKw.FormKey);
        else
            SyncKeywordsAndAdd(ref furnKws, frameFurn.Components, Own(FrameFurnKeywordId));
        frameFurn.Keywords = furnKws;
        mod.Furniture.Add(frameFurn);

        // 6. FusionCore battery item (MISC + isPowerArmorBattery)
        var fusionCore = (MiscItem)batteryTmpl.Duplicate(Own(FusionCoreId));
        fusionCore.EditorID = FusionCoreEdid;
        fusionCore.Name = "FO4SF Fusion Core";
        fusionCore.VirtualMachineAdapter = null;
        fusionCore.Value = 200;
        fusionCore.Weight = 2.0f;
        var coreKws = fusionCore.Keywords;
        SyncKeywordsAndAdd(ref coreKws, fusionCore.Components, batteryKw.FormKey);
        fusionCore.Keywords = coreKws;
        mod.MiscItems.Add(fusionCore);

        // 7. Four non-overlapping climb-in PA pieces (BODY 0x8 non-playable, SSBODY, SSHelmet, SSBackpack)
        var paFrameArmor = DuplicateArmorClean(frameTmpl, FrameArmorId, FrameArmorEdid, "FO4SF Power Armor Frame");
        paFrameArmor.MajorRecordFlagsRaw |= 0x4; // Non-playable so player cannot unequip frame manually while inside
        paFrameArmor.Race.SetTo(humanRace.FormKey);
        var faKws = paFrameArmor.Keywords;
        SyncKeywordsAndAdd(ref faKws, paFrameArmor.Components, frameKw.FormKey);
        paFrameArmor.Keywords = faKws;
        CloneArmaturesForPaRace(mod, sfArmas, paFrameArmor, humanRace.FormKey, Own(RaceId), armaMap, ref nextArmaId);
        mod.Armors.Add(paFrameArmor);

        var paTorso = DuplicateArmorClean(bodyTmpl, PaTorsoId, PaTorsoEdid, "FO4SF Power Armor Torso");
        paTorso.Race.SetTo(humanRace.FormKey);
        BoostArmorDefense(paTorso, 320, 320);
        var torsoKws = paTorso.Keywords;
        SyncKeywordsAndAdd(ref torsoKws, paTorso.Components, Own(ArmorKeywordId));
        paTorso.Keywords = torsoKws;
        CloneArmaturesForPaRace(mod, sfArmas, paTorso, humanRace.FormKey, Own(RaceId), armaMap, ref nextArmaId);
        mod.Armors.Add(paTorso);

        var paHelmet = DuplicateArmorClean(helmTmpl, PaHelmetId, PaHelmetEdid, "FO4SF Power Armor Helmet");
        paHelmet.Race.SetTo(humanRace.FormKey);
        BoostArmorDefense(paHelmet, 120, 120);
        var helmKws = paHelmet.Keywords;
        SyncKeywordsAndAdd(ref helmKws, paHelmet.Components, Own(ArmorKeywordId));
        paHelmet.Keywords = helmKws;
        CloneArmaturesForPaRace(mod, sfArmas, paHelmet, humanRace.FormKey, Own(RaceId), armaMap, ref nextArmaId);
        mod.Armors.Add(paHelmet);

        var paPack = DuplicateArmorClean(packTmpl, PaPackId, PaPackEdid, "FO4SF Power Armor Pack");
        paPack.Race.SetTo(humanRace.FormKey);
        BoostArmorDefense(paPack, 100, 100);
        var packKws = paPack.Keywords;
        SyncKeywordsAndAdd(ref packKws, paPack.Components, Own(ArmorKeywordId));
        paPack.Keywords = packKws;
        CloneArmaturesForPaRace(mod, sfArmas, paPack, humanRace.FormKey, Own(RaceId), armaMap, ref nextArmaId);
        mod.Armors.Add(paPack);

        // 8. FNV Salvaged NCR Power Armor (#806 owner dual-form decision: plain worn heavy ARMO on HumanRace, high ballistic DR, -1 AGI, zero frame)
        var agiMgef = new MagicEffect(Own(SalvagedAgiMgefId), Release)
        {
            EditorID = SalvagedAgiMgefEdid,
            Name = "FO4SF Salvaged Armor Agility Penalty",
            Archetype = new MagicEffectArchetype(MagicEffectArchetype.TypeEnum.ValueModifier), // Association MUST remain empty (RadsProbe crash lesson)
            CastType = CastType.ConstantEffect,
            TargetType = TargetType.Self,
            Flags = MagicEffect.Flag.Recover | MagicEffect.Flag.Detrimental | MagicEffect.Flag.NoDuration | MagicEffect.Flag.NoArea | MagicEffect.Flag.Painless,
        };
        agiMgef.SecondActorValue.SetTo(specialAgilityKey);
        mod.MagicEffects.Add(agiMgef);

        var agiEnch = new ObjectEffect(Own(SalvagedAgiEnchId), Release)
        {
            EditorID = SalvagedAgiEnchEdid,
            Name = "FO4SF Salvaged Armor Weight Penalty",
            UnknownENIT = ConstantSelfEnit.ToArray(),
        };
        agiEnch.Effects.Add(new Effect
        {
            BaseEffect = new FormLinkNullable<IMagicEffectGetter>(Own(SalvagedAgiMgefId)),
            Data = new EffectData { Magnitude = 1f, Area = 0, Duration = 0 },
        });
        mod.ObjectEffects.Add(agiEnch);

        var salvagedBody = DuplicateArmorClean(bodyTmpl, SalvagedBodyId, SalvagedBodyEdid, "FO4SF Salvaged Power Armor");
        salvagedBody.MajorRecordFlagsRaw &= ~0x4; // Playable heavy worn armor
        salvagedBody.Race.SetTo(humanRace.FormKey);
        salvagedBody.Weight = 40.0f;
        salvagedBody.Value = 1200;
        BoostArmorDefense(salvagedBody, 240, 240);
        salvagedBody.ObjectEffect.SetTo(Own(SalvagedAgiEnchId));
        var salvBodyKws = salvagedBody.Keywords;
        SyncKeywordsAndAdd(ref salvBodyKws, salvagedBody.Components, Own(SalvagedKeywordId));
        salvBodyKws!.RemoveAll(k => k.FormKey == frameKw.FormKey || k.FormKey == furnPaKw.FormKey);
        foreach (var kc in salvagedBody.Components.OfType<KeywordFormComponent>())
            kc.Keywords?.RemoveAll(k => k.FormKey == frameKw.FormKey || k.FormKey == furnPaKw.FormKey);
        salvagedBody.Keywords = salvBodyKws;
        mod.Armors.Add(salvagedBody);

        var salvagedHelm = DuplicateArmorClean(helmTmpl, SalvagedHelmId, SalvagedHelmEdid, "FO4SF Salvaged Power Helmet");
        salvagedHelm.MajorRecordFlagsRaw &= ~0x4;
        salvagedHelm.Race.SetTo(humanRace.FormKey);
        salvagedHelm.Weight = 8.0f;
        salvagedHelm.Value = 350;
        BoostArmorDefense(salvagedHelm, 80, 80);
        var salvHelmKws = salvagedHelm.Keywords;
        SyncKeywordsAndAdd(ref salvHelmKws, salvagedHelm.Components, Own(SalvagedKeywordId));
        salvHelmKws!.RemoveAll(k => k.FormKey == frameKw.FormKey || k.FormKey == furnPaKw.FormKey);
        foreach (var kc in salvagedHelm.Components.OfType<KeywordFormComponent>())
            kc.Keywords?.RemoveAll(k => k.FormKey == frameKw.FormKey || k.FormKey == furnPaKw.FormKey);
        salvagedHelm.Keywords = salvHelmKws;
        mod.Armors.Add(salvagedHelm);

        // 9. Opt-in DFOB overrides (--override-dfob only; default build touches zero Starfield.esm records)
        if (overrideDfob)
        {
            foreach (var (dfobEdid, targetId) in DfobTargets)
            {
                var srcDfob = One(sf.DefaultObjects, dfobEdid, "DFOB");
                var ov = srcDfob.DeepCopy();
                ov.Object.SetTo(Own(targetId));
                mod.DefaultObjects.Add(ov);
            }
        }

        // 10. Optional self-contained test room CELL FO4SF_PATestCell (`coc FO4SF_PATestCell`, omitted under --no-test-cell)
        uint nextId = FirstCloneArmaId;
        string cellSummary = "no-test-cell";
        if (!noTestCell)
        {
            var cell = new Cell(Own(CellId), Release) { EditorID = CellEdid, Flags = Cell.Flag.IsInteriorCell };
            cell.LightingTemplate.SetTo(Sf(LightingTemplate));
            cell.ImageSpace.SetTo(Sf(ImageSpace));
            cell.EnvironmentMap = "Data\\Textures\\Cubemaps\\Cell_HiTechHallCube.dds";

            var zero = new P3Float(0, 0, 0);
            PlacedObject MakeRef(uint id, FormKey b, P3Float pos, P3Float rot, string? edid = null, bool persistent = false)
            {
                var r = new PlacedObject(Own(id), Release)
                {
                    EditorID = edid,
                    Base = new FormLinkNullable<IPlaceableObjectGetter>(b),
                    Position = pos,
                    Rotation = rot,
                };
                if (persistent) r.MajorRecordFlagsRaw |= 0x400;
                return r;
            }

            cell.Persistent.Add(MakeRef(ArrivalRefId, Sf(XMarker), CocPos, new P3Float(0, 0, (float)(Math.PI / 2)), "FO4SF_PATestArrival", persistent: true));
            cell.Persistent.Add(MakeRef(FrameFurnRefId, Own(FrameFurnId), FramePos, zero, "FO4SF_PowerArmorFrameFurnRef", persistent: true));
            cell.Persistent.Add(MakeRef(ExitChairRefId, controlFurn.FormKey, ExitChairPos, zero, "FO4SF_PAExitChairRef", persistent: true));

            cell.Temporary.Add(MakeRef(CocRefId, Sf(CocMarker), CocPos, new P3Float(0, 0, (float)(Math.PI / 2))));
            cell.Temporary.Add(MakeRef(CoreRef1Id, Own(FusionCoreId), new P3Float(1.5f, -2.5f, 0.2f), zero, "FO4SF_FusionCoreRef01"));
            cell.Temporary.Add(MakeRef(CoreRef2Id, Own(FusionCoreId), new P3Float(2.0f, -2.5f, 0.2f), zero, "FO4SF_FusionCoreRef02"));
            cell.Temporary.Add(MakeRef(CoreRef3Id, Own(FusionCoreId), new P3Float(2.5f, -2.5f, 0.2f), zero, "FO4SF_FusionCoreRef03"));
            cell.Temporary.Add(MakeRef(SalvagedBodyRefId, Own(SalvagedBodyId), new P3Float(-1.5f, -2.5f, 0.2f), zero, "FO4SF_SalvagedNCRBodyRef"));
            cell.Temporary.Add(MakeRef(SalvagedHelmRefId, Own(SalvagedHelmId), new P3Float(-0.8f, -2.5f, 0.2f), zero, "FO4SF_SalvagedNCRHelmRef"));

            nextId = FirstTileId;
            for (float x = -TileStep; x <= TileStep; x += TileStep)
                for (float y = -TileStep; y <= TileStep; y += TileStep)
                    cell.Temporary.Add(MakeRef(nextId++, Sf(FloorStat), new P3Float(x - 2.0f, y, 0f), zero));
            for (float x = -4f; x <= 4f; x += 8f)
                for (float y = -4f; y <= 4f; y += 8f)
                    cell.Temporary.Add(MakeRef(nextId++, Sf(OmniLight), new P3Float(x, y, LightZ), zero));

            var cid = cell.FormKey.ID;
            var block = new CellBlock { BlockNumber = (int)(cid % 10), GroupType = GroupTypeEnum.InteriorCellBlock };
            var sub = new CellSubBlock { BlockNumber = (int)((cid / 10) % 10), GroupType = GroupTypeEnum.InteriorCellSubBlock };
            sub.Cells.Add(cell);
            block.SubBlocks.Add(sub);
            mod.Cells.Records.Add(block);
            cellSummary = $"CELL {CellEdid} {cell.FormKey}";
        }

        // 11. Quest FO4SF_PowerArmorCoreQuest (StartGameEnabled, stages 10/20/30/40, script FO4SF_PowerArmorCoreQuest)
        var quest = new Quest(Own(QuestId), Release)
        {
            EditorID = QuestEdid,
            Name = "FO4SF Power Armor Core",
            FormVersion = 581,
            Version2 = 12,
            Data = new QuestData { Flags = Quest.Flag.StartGameEnabled, Priority = 30 },
        };
        foreach (var s in QuestStages)
            quest.Stages.Add(new QuestStage { Index = s });
        var se = new ScriptEntry { Name = QuestScript, Flags = ScriptEntry.Flag.Local };
        se.Properties.Add(ObjProp("SpecialAgilityAV", specialAgilityKey));
        se.Properties.Add(ObjProp("TestModeGlobal", testModeKey));
        quest.VirtualMachineAdapter = new QuestAdapter
        {
            Version = 6,
            ObjectFormat = 2,
            ExtraBindDataVersion = 3,
            Script = new ScriptEntry { Name = "", Flags = ScriptEntry.Flag.Local },
        };
        quest.VirtualMachineAdapter.Scripts.Add(se);
        mod.Quests.Add(quest);

        mod.ModHeader.Stats.NextFormID = Math.Max(nextId, nextArmaId);
        WritePlugin(mod, outDir, SfEsm, CoreValuesEsm);
        var writtenPath = Path.Combine(outDir, Plugin.FileName);
        Console.WriteLine(
            $"wrote {writtenPath} ({new FileInfo(writtenPath).Length:N0} bytes): " +
            $"{cellSummary}, RACE {RaceEdid} -> BPTD {BodyPartDataEdid} (6 limb AVIFs) + Skin {SkinEdid}, " +
            $"FURN {FrameFurnEdid}, MISC {FusionCoreEdid}, 4 PA ARMOs ({armaMap.Count} cloned ARMAs), " +
            $"2 Salvaged NCR ARMOs (-1 AGI ENCH {SalvagedAgiEnchEdid} -> {specialAgilityKey}), QUST {QuestEdid}, " +
            $"override_dfob={overrideDfob}, no_test_cell={noTestCell}");
        return 0;
    }

    static void WritePlugin(StarfieldMod mod, string outDir, params ModKey[] masters)
    {
        Directory.CreateDirectory(outDir);
        var path = Path.Combine(outDir, mod.ModKey.FileName);
        var tmpDir = Path.Combine(outDir, ".tmp-" + Guid.NewGuid().ToString("N"));
        try
        {
            Directory.CreateDirectory(tmpDir);
            var tmp = Path.Combine(tmpDir, mod.ModKey.FileName);
            var masterFlags = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
            foreach (var m in masters)
                masterFlags.Set(new KeyedMasterStyle(m, MasterStyle.Full));
            mod.WriteToBinary(tmp, new BinaryWriteParameters
            {
                ModKey = ModKeyOption.NoCheck,
                MastersListOrdering = new MastersListOrderingByLoadOrder(masters),
                MasterFlagsLookup = masterFlags,
            });
            File.Move(tmp, path, overwrite: true);
        }
        finally
        {
            if (Directory.Exists(tmpDir)) Directory.Delete(tmpDir, true);
        }
    }

    // ---------------------------------------------------------------- check

    public static int Check(string pluginPath, string templatePath, string controlEdid, bool overrideDfob, bool noTestCell = false, string? jsonPath = null)
    {
        var coreIds = LoadCoreValues(jsonPath);
        var specialAgilityKey = Core(coreIds, SpecialAgilityEdid);
        var testModeKey = Core(coreIds, TestModeEdid);

        using var sf = OpenTemplate(templatePath);
        var humanRace = One(sf.Races, HumanRaceEdid, "RACE");
        var bodyTmpl = One(sf.Armors, Mark1BodyEdid, "ARMO");
        var helmTmpl = One(sf.Armors, Mark1HelmetEdid, "ARMO");
        var packTmpl = One(sf.Armors, Mark1PackEdid, "ARMO");
        var frameTmpl = One(sf.Armors, FrameClothesEdid, "ARMO");
        var furnPaKw = One(sf.Keywords, FurnPaKeywordEdid, "KYWD");
        var frameKw = One(sf.Keywords, FrameKeywordEdid, "KYWD");
        var batteryKw = One(sf.Keywords, BatteryKeywordEdid, "KYWD");
        _ = One(sf.ActorValueInformation, AgilityAvEdid, "AVIF");
        var controlFurn = One(sf.Furniture, controlEdid, "FURN");

        using var mod = OpenPlugin(pluginPath);

        var problems = new List<string>();
        void Need(bool ok, string what) { if (!ok) problems.Add(what); }

        var masters = mod.ModHeader.MasterReferences.Select(m => m.Master).ToList();
        Console.WriteLine($"{Path.GetFileName(pluginPath)}: header {mod.ModHeader.Flags}, masters [{string.Join(", ", masters)}], next 0x{mod.ModHeader.Stats.NextFormID:X}");
        Need(mod.ModKey == Plugin, $"plugin ModKey is {mod.ModKey}, expected {Plugin}");
        Need(mod.ModHeader.Flags.HasFlag(StarfieldModHeader.HeaderFlag.Master), "plugin header lacks Master flag");
        Need(masters.SequenceEqual(new[] { SfEsm, CoreValuesEsm }), $"masters [{string.Join(", ", masters)}] != [Starfield.esm, FO4SFCoreValues.esm]");

        var dupCoreEdids = mod.EnumerateMajorRecords()
            .Where(r => r.FormKey.ModKey == Plugin && r.EditorID != null && coreIds.ContainsKey(r.EditorID))
            .Select(r => r.EditorID!)
            .ToList();
        Need(dupCoreEdids.Count == 0, $"plugin duplicates FO4SFCoreValues.esm EditorIDs: {string.Join(", ", dupCoreEdids)}");

        // Clean-room isolation: zero foreign overrides unless --override-dfob is explicitly active (and then ONLY the 5 PowerArmor*_DO DFOBs)
        var nonDfobForeign = mod.EnumerateMajorRecords()
            .Where(r => r.FormKey.ModKey != Plugin && r is not IDefaultObjectGetter)
            .Select(r => $"{r.GetType().Name}:{r.FormKey}")
            .ToList();
        Need(nonDfobForeign.Count == 0, $"unexpected non-DFOB foreign overrides: {string.Join(", ", nonDfobForeign)}");

        var dfobs = mod.DefaultObjects.ToList();
        if (!overrideDfob)
        {
            Need(dfobs.Count == 0, $"default clean-room build must override 0 DFOBs, found {dfobs.Count}");
        }
        else
        {
            Need(dfobs.Count == DfobTargets.Length, $"--override-dfob expected {DfobTargets.Length} DFOB overrides, found {dfobs.Count}");
            foreach (var (dfobEdid, targetId) in DfobTargets)
            {
                var srcDfob = One(sf.DefaultObjects, dfobEdid, "DFOB");
                var ov = dfobs.FirstOrDefault(d => d.FormKey == srcDfob.FormKey);
                Need(ov != null && ov.Object.FormKey == Own(targetId), $"DFOB {dfobEdid} ({srcDfob.FormKey}) does not point to {Own(targetId)}");
            }
        }

        // Verify 8 AVIFs (2 state/charge + 6 limb conditions)
        var avifs = mod.ActorValueInformation.ToDictionary(a => a.FormKey);
        Need(avifs.Count == 8, $"expected 8 AVIF records, found {avifs.Count}");
        Need(avifs.TryGetValue(Own(InPaAvId), out var inPaAv) && inPaAv.EditorID == InPaAvEdid && inPaAv.Min == 0f && inPaAv.Max == 1f,
            $"missing or invalid {InPaAvEdid}");
        Need(avifs.TryGetValue(Own(FusionChargeAvId), out var chargeAv) && chargeAv.EditorID == FusionChargeAvEdid && chargeAv.Min == 0f && chargeAv.Max == 100f,
            $"missing or invalid {FusionChargeAvEdid}");
        foreach (var (id, edid, _, _) in LimbSpecs)
        {
            Need(avifs.TryGetValue(Own(id), out var av) && av.EditorID == edid && av.DefaultValue == 100f && av.Min == 0f && av.Max == 100f,
                $"missing or invalid limb AVIF {edid}");
        }

        // Verify 6-limb BPTD
        var bptd = mod.BodyParts.FirstOrDefault(b => b.FormKey == Own(BodyPartDataId));
        Need(bptd != null && bptd.EditorID == BodyPartDataEdid, $"missing BPTD {BodyPartDataEdid}");
        if (bptd != null)
        {
            foreach (var (id, edid, _, partTypes) in LimbSpecs)
            {
                var parts = bptd.Parts.Where(p => partTypes.Contains(p.Type)).ToList();
                Need(parts.Count > 0 && parts.All(p => p.ActorValue.FormKey == Own(id) && Math.Abs(p.HealthPercent.Value - 1.0) < 1e-4),
                    $"BPTD {BodyPartDataEdid} limb {edid} not wired to {Own(id)} at 100% HealthPercent");
            }
        }

        // Verify PowerArmorSkin + PowerArmorRace + cloned ARMAs naming both HumanRace and FO4SF_PowerArmorRace
        var ownArmas = mod.ArmorAddons.ToDictionary(a => a.FormKey);
        var paSkin = mod.Armors.FirstOrDefault(a => a.FormKey == Own(SkinId));
        var paRace = mod.Races.FirstOrDefault(r => r.FormKey == Own(RaceId));
        Need(paSkin != null && paSkin.EditorID == SkinEdid, $"missing skin ARMO {SkinEdid}");
        Need(paRace != null && paRace.EditorID == RaceEdid, $"missing RACE {RaceEdid}");
        if (paRace != null)
        {
            Need(paRace.BodyPartData.FormKey == Own(BodyPartDataId), $"{RaceEdid}.BodyPartData != {Own(BodyPartDataId)}");
            Need(paRace.Skin.FormKey == Own(SkinId), $"{RaceEdid}.Skin != {Own(SkinId)}");
            Need(paRace.ArmorRace.FormKey == humanRace.FormKey, $"{RaceEdid}.ArmorRace != {humanRace.FormKey}");
        }

        bool ArmaturesSupportBothRaces(IArmorGetter? armor)
        {
            if (armor == null || armor.Armatures == null || armor.Armatures.Count == 0) return false;
            foreach (var entry in armor.Armatures)
            {
                if (entry.ArmorAddon.FormKeyNullable is not { } fk || !ownArmas.TryGetValue(fk, out var arma))
                    return false;
                bool hasHuman = arma.Race.FormKey == humanRace.FormKey || (arma.AdditionalRaces?.Any(r => r.FormKey == humanRace.FormKey) ?? false);
                bool hasPa = arma.Race.FormKey == Own(RaceId) || (arma.AdditionalRaces?.Any(r => r.FormKey == Own(RaceId)) ?? false);
                if (!hasHuman || !hasPa) return false;
            }
            return true;
        }
        Need(ArmaturesSupportBothRaces(paSkin), $"{SkinEdid} armatures do not name both {HumanRaceEdid} and {RaceEdid}");

        // Verify FusionCore MISC + isPowerArmorBattery in both Keywords and KeywordFormComponent
        var core = mod.MiscItems.FirstOrDefault(m => m.FormKey == Own(FusionCoreId));
        Need(core != null && core.EditorID == FusionCoreEdid, $"missing MISC {FusionCoreEdid}");
        if (core != null)
        {
            bool kwList = core.Keywords?.Any(k => k.FormKey == batteryKw.FormKey) == true;
            bool kwComp = core.Components.OfType<IKywdFormComponentGetterStub>().Any() ||
                          core.Components.OfType<IKeywordFormComponentGetter>().Any(c => c.Keywords?.Any(k => k.FormKey == batteryKw.FormKey) == true);
            Need(kwList && kwComp, $"{FusionCoreEdid} lacks {BatteryKeywordEdid} in Keywords or KeywordFormComponent");
        }

        // Verify Frame Furniture
        var furn = mod.Furniture.FirstOrDefault(f => f.FormKey == Own(FrameFurnId));
        Need(furn != null && furn.EditorID == FrameFurnEdid, $"missing FURN {FrameFurnEdid}");
        if (furn != null)
        {
            Need(furn.Keywords?.Any(k => k.FormKey == Own(FrameFurnKeywordId)) == true, $"{FrameFurnEdid} lacks {FrameFurnKeywordEdid}");
            if (overrideDfob)
            {
                Need(furn.Keywords?.Any(k => k.FormKey == furnPaKw.FormKey) == true &&
                     furn.Keywords?.Any(k => k.FormKey == frameKw.FormKey) == true,
                    $"--override-dfob {FrameFurnEdid} lacks {FurnPaKeywordEdid}/{FrameKeywordEdid}");
            }
        }

        // Verify 4 modular PA pieces: disjoint FirstPersonFlags, preserved template stats/keywords, cloned ARMAs naming both races
        var paFrame = mod.Armors.FirstOrDefault(a => a.FormKey == Own(FrameArmorId));
        var paTorso = mod.Armors.FirstOrDefault(a => a.FormKey == Own(PaTorsoId));
        var paHelm = mod.Armors.FirstOrDefault(a => a.FormKey == Own(PaHelmetId));
        var paPack = mod.Armors.FirstOrDefault(a => a.FormKey == Own(PaPackId));
        Need(paFrame != null && paTorso != null && paHelm != null && paPack != null, "missing one or more modular PA ARMO records");
        if (paFrame != null && paTorso != null && paHelm != null && paPack != null)
        {
            Need((paFrame.MajorRecordFlagsRaw & 0x4) != 0, $"{FrameArmorEdid} must carry non-playable flag 0x4");
            Need(paFrame.Keywords?.Any(k => k.FormKey == frameKw.FormKey) == true &&
                 paFrame.Components.OfType<IKeywordFormComponentGetter>().Any(c => c.Keywords?.Any(k => k.FormKey == frameKw.FormKey) == true),
                $"{FrameArmorEdid} lacks {FrameKeywordEdid} in Keywords or KeywordFormComponent");
            var paPieces = new[] { (paFrame, frameTmpl), (paTorso, bodyTmpl), (paHelm, helmTmpl), (paPack, packTmpl) };
            ulong combinedMask = 0;
            foreach (var (piece, tmpl) in paPieces)
            {
                Need(ArmaturesSupportBothRaces(piece), $"{piece.EditorID} armatures do not support both {HumanRaceEdid} and {RaceEdid}");
                ulong slotBits = (ulong)(piece.FirstPersonFlags ?? 0);
                Need(slotBits != 0 && (combinedMask & slotBits) == 0, $"{piece.EditorID} FirstPersonFlags ({piece.FirstPersonFlags}) overlaps another PA slot");
                combinedMask |= slotBits;
                foreach (var srcKw in tmpl.Keywords ?? Enumerable.Empty<IFormLinkGetter<IKeywordGetter>>())
                    Need(piece.Keywords?.Any(k => k.FormKey == srcKw.FormKey) == true, $"{piece.EditorID} lost template keyword {srcKw.FormKey}");
                Need(piece.Value == tmpl.Value && Math.Abs(piece.Weight - tmpl.Weight) < 1e-4f && piece.Health == tmpl.Health,
                    $"{piece.EditorID} Value/Weight/Health ({piece.Value}/{piece.Weight}/{piece.Health}) differs from template {tmpl.EditorID} ({tmpl.Value}/{tmpl.Weight}/{tmpl.Health})");
            }
            foreach (var piece in new[] { paTorso, paHelm, paPack })
                Need(piece.Keywords?.Any(k => k.FormKey == Own(ArmorKeywordId)) == true, $"{piece.EditorID} lacks {ArmorKeywordEdid}");
        }

        // Verify FNV Salvaged NCR Power Armor (#806): plain worn heavy ARMO on HumanRace, NO frame keyword, high DR, -1 AGI ENCH/MGEF
        var salvBody = mod.Armors.FirstOrDefault(a => a.FormKey == Own(SalvagedBodyId));
        var salvHelm = mod.Armors.FirstOrDefault(a => a.FormKey == Own(SalvagedHelmId));
        var salvEnch = mod.ObjectEffects.FirstOrDefault(e => e.FormKey == Own(SalvagedAgiEnchId));
        var salvMgef = mod.MagicEffects.FirstOrDefault(m => m.FormKey == Own(SalvagedAgiMgefId));
        Need(salvBody != null && salvBody.EditorID == SalvagedBodyEdid, $"missing {SalvagedBodyEdid}");
        Need(salvHelm != null && salvHelm.EditorID == SalvagedHelmEdid, $"missing {SalvagedHelmEdid}");
        Need(salvEnch != null && salvMgef != null, "missing salvaged NCR -1 AGI enchantment or magic effect");
        if (salvBody != null && salvHelm != null)
        {
            foreach (var s in new[] { salvBody, salvHelm })
            {
                Need((s.MajorRecordFlagsRaw & 0x4) == 0, $"{s.EditorID} must be playable worn armor");
                Need(s.Race.FormKey == humanRace.FormKey, $"{s.EditorID} must target {HumanRaceEdid} directly");
                Need(s.Keywords?.Any(k => k.FormKey == Own(SalvagedKeywordId)) == true, $"{s.EditorID} lacks {SalvagedKeywordEdid}");
                Need(s.Keywords?.Any(k => k.FormKey == frameKw.FormKey) != true &&
                     !s.Components.OfType<IKeywordFormComponentGetter>().Any(c => c.Keywords?.Any(k => k.FormKey == frameKw.FormKey) == true),
                    $"{s.EditorID} must NEVER carry {FrameKeywordEdid}");
            }
            Need(salvBody.ArmorRating >= 200 && salvHelm.ArmorRating >= 60, "salvaged NCR armor lacks heavy ballistic ArmorRating");
            Need(salvBody.ObjectEffect.FormKey == Own(SalvagedAgiEnchId), $"{SalvagedBodyEdid} lacks -1 AGI ObjectEffect {Own(SalvagedAgiEnchId)}");
        }
        if (salvEnch != null && salvMgef != null)
        {
            Need(salvEnch.Effects.Count == 1 && salvEnch.Effects[0].BaseEffect.FormKey == Own(SalvagedAgiMgefId) &&
                 Math.Abs((salvEnch.Effects[0].Data?.Magnitude ?? 0f) - 1f) < 1e-4f,
                $"{SalvagedAgiEnchEdid} does not apply magnitude 1.0 of {SalvagedAgiMgefEdid}");
            var arch = salvMgef.Archetype as IMagicEffectArchetypeGetter;
            Need(arch?.Type == MagicEffectArchetype.TypeEnum.ValueModifier && arch.Association.IsNull,
                $"{SalvagedAgiMgefEdid} must be ValueModifier with empty Archetype.Association");
            Need(salvMgef.SecondActorValue.FormKey == specialAgilityKey && salvMgef.Flags.HasFlag(MagicEffect.Flag.Detrimental) &&
                 salvMgef.CastType == CastType.ConstantEffect && salvMgef.TargetType == TargetType.Self,
                $"{SalvagedAgiMgefEdid} must be ConstantEffect Self Detrimental targeting {specialAgilityKey}");
        }

        // Verify Test Cell (omitted under --no-test-cell) and Quest
        var allCells = mod.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells).ToList();
        if (noTestCell)
        {
            Need(mod.Cells.Records.Count == 0 && allCells.Count == 0,
                $"--no-test-cell expected 0 CELL records, found {allCells.Count} ({mod.Cells.Records.Count} cell blocks)");
        }
        else
        {
            var cell = allCells.FirstOrDefault(c => c.FormKey == Own(CellId));
            Need(cell != null && cell.EditorID == CellEdid, $"missing CELL {CellEdid}");
            if (cell != null)
            {
                var pers = cell.Persistent.OfType<IPlacedObjectGetter>().ToDictionary(r => r.FormKey);
                Need(pers.TryGetValue(Own(ArrivalRefId), out var arr) && (arr.MajorRecordFlagsRaw & 0x400) != 0, "missing persistent arrival marker");
                Need(pers.TryGetValue(Own(FrameFurnRefId), out var fref) && fref.Base.FormKey == Own(FrameFurnId) && (fref.MajorRecordFlagsRaw & 0x400) != 0,
                    "missing persistent frame furniture reference");
                Need(pers.TryGetValue(Own(ExitChairRefId), out var eref) && eref.Base.FormKey == controlFurn.FormKey && (eref.MajorRecordFlagsRaw & 0x400) != 0,
                    "missing persistent exit chair reference");
                var temp = cell.Temporary.OfType<IPlacedObjectGetter>().ToDictionary(r => r.FormKey);
                Need(temp.ContainsKey(Own(CoreRef1Id)) && temp.ContainsKey(Own(CoreRef2Id)) && temp.ContainsKey(Own(CoreRef3Id)),
                    "missing placed FusionCore references in test cell");
                Need(temp.ContainsKey(Own(SalvagedBodyRefId)) && temp.ContainsKey(Own(SalvagedHelmRefId)),
                    "missing placed Salvaged NCR armor references in test cell");
            }
        }

        var quest = mod.Quests.FirstOrDefault(q => q.FormKey == Own(QuestId));
        Need(quest != null && quest.EditorID == QuestEdid && quest.Data != null && quest.Data.Flags.HasFlag(Quest.Flag.StartGameEnabled),
            $"missing StartGameEnabled QUST {QuestEdid}");
        if (quest != null)
        {
            Need(quest.Stages.Select(s => s.Index).SequenceEqual(QuestStages), $"{QuestEdid} stages != [{string.Join(",", QuestStages)}]");
            var scripts = quest.VirtualMachineAdapter?.Scripts;
            Need(scripts != null && scripts.Count == 1 && scripts[0].Name == QuestScript && scripts[0].Properties.Count == 2,
                $"{QuestEdid} must attach {QuestScript} with 2 properties (SpecialAgilityAV, TestModeGlobal)");
            if (scripts != null && scripts.Count == 1 && scripts[0].Properties.Count == 2)
            {
                var p0 = scripts[0].Properties[0] as IScriptObjectPropertyGetter;
                var p1 = scripts[0].Properties[1] as IScriptObjectPropertyGetter;
                Need(p0 != null && p0.Name == "SpecialAgilityAV" && p0.Object.FormKey == specialAgilityKey,
                    $"{QuestEdid} property[0] must be SpecialAgilityAV -> {specialAgilityKey}");
                Need(p1 != null && p1.Name == "TestModeGlobal" && p1.Object.FormKey == testModeKey,
                    $"{QuestEdid} property[1] must be TestModeGlobal -> {testModeKey}");
            }
        }

        if (problems.Count > 0)
        {
            foreach (var p in problems) Console.Error.WriteLine("check failed: " + p);
            return 1;
        }
        Console.WriteLine($"check ok: {Plugin.FileName} verified (6-limb BPTD, PA race+skin, 4 disjoint PA slots, FusionCore, Salvaged NCR -1 AGI -> {specialAgilityKey}, override_dfob={overrideDfob}, no_test_cell={noTestCell})");
        return 0;
    }

    private interface IKywdFormComponentGetterStub { } // unused marker; IKeywordFormComponentGetter is checked directly

    // ---------------------------------------------------------------- fixture & selftest

    public static int Fixture(string outDir)
    {
        var mod = new StarfieldMod(SfEsm, Release);
        mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;

        var kwFurnPa = new Keyword(Sf(0x03430B), Release) { EditorID = FurnPaKeywordEdid };
        var kwFrame = new Keyword(Sf(0x15503F), Release) { EditorID = FrameKeywordEdid };
        var kwBatt = new Keyword(Sf(0x05BDAA), Release) { EditorID = BatteryKeywordEdid };
        var kwLink = new Keyword(Sf(0x077CA9), Release) { EditorID = "LinkPowerArmor" };
        var kwSuit = new Keyword(Sf(0x0027D5), Release) { EditorID = "ArmorTypeSpacesuitBody" };
        foreach (var k in new[] { kwFurnPa, kwFrame, kwBatt, kwLink, kwSuit })
            mod.Keywords.Add(k);

        mod.ActorValueInformation.Add(new ActorValueInformation(Sf(0x0012C7), Release) { EditorID = AgilityAvEdid, Type = ActorValueInformation.Types.Variable, DefaultValue = 5f, Min = 1f, Max = 20f });
        mod.ActorValueInformation.Add(new ActorValueInformation(Sf(0x0012DA), Release) { EditorID = SpeedMultAvEdid, Type = ActorValueInformation.Types.Variable, DefaultValue = 100f });
        mod.ActorValueInformation.Add(new ActorValueInformation(Sf(0x0012DC), Release) { EditorID = CarryWeightAvEdid, Type = ActorValueInformation.Types.Variable, DefaultValue = 135f });

        var bptd = new BodyPartData(Sf(0x003481), Release) { EditorID = HumanBptdEdid };
        foreach (var pt in new[]
        {
            BodyPart.PartType.Torso, BodyPart.PartType.Head1, BodyPart.PartType.LeftArm1, BodyPart.PartType.RightArm1,
            BodyPart.PartType.LeftLeg1, BodyPart.PartType.LeftFoot, BodyPart.PartType.RightLeg1, BodyPart.PartType.RightFoot,
        })
        {
            bptd.Parts.Add(new BodyPart { Type = pt, PartNode = $"Node_{pt}", HealthPercent = new Percent(1.0) });
        }
        mod.BodyParts.Add(bptd);

        var human = new Race(Sf(0x00347D), Release) { EditorID = HumanRaceEdid };
        human.BodyPartData.SetTo(bptd.FormKey);
        human.Skin.SetTo(Sf(0x000D64));
        mod.Races.Add(human);

        ArmorAddon MakeArma(uint id, string edid)
        {
            var aa = new ArmorAddon(Sf(id), Release) { EditorID = edid };
            aa.Race.SetTo(human.FormKey);
            mod.ArmorAddons.Add(aa);
            return aa;
        }
        var aaSkinBody = MakeArma(0x012204, "AA_Naked_Body");
        var aaSkinHands = MakeArma(0x030580, "AA_Naked_Hands");
        var aaFatigues = MakeArma(0x17C68E, "AA_Akila_Fatigues");
        var aaMark1Body = MakeArma(0x017550, "AA_Mark1_Body");
        var aaMark1Helm = MakeArma(0x017551, "AA_Mark1_Helmet");
        var aaMark1Pack = MakeArma(0x017552, "AA_Mark1_Backpack");

        ExtendedList<ArmorAddonModel> Addons(params ArmorAddon[] aas) =>
            new(aas.Select(a => new ArmorAddonModel { ArmorAddon = new FormLinkNullable<IArmorAddonGetter>(a.FormKey) }));
        ExtendedList<IFormLinkGetter<IKeywordGetter>> SuitKws() =>
            new() { new FormLink<IKeywordGetter>(kwSuit.FormKey) };

        mod.Armors.Add(new Armor(Sf(0x000D64), Release)
        {
            EditorID = SkinNakedEdid,
            Race = new FormLinkNullable<IRaceGetter>(human.FormKey),
            FirstPersonFlags = FirstPersonFlag.BODY,
            Armatures = Addons(aaSkinBody, aaSkinHands),
        });
        mod.Armors.Add(new Armor(Sf(0x17C68D), Release)
        {
            EditorID = FrameClothesEdid,
            MajorRecordFlagsRaw = 0x4,
            Race = new FormLinkNullable<IRaceGetter>(human.FormKey),
            FirstPersonFlags = FirstPersonFlag.BODY,
            Value = 50,
            Weight = 1.5f,
            Health = 100,
            Keywords = SuitKws(),
            Armatures = Addons(aaFatigues),
        });
        mod.Armors.Add(new Armor(Sf(0x01754D), Release)
        {
            EditorID = Mark1BodyEdid,
            Race = new FormLinkNullable<IRaceGetter>(human.FormKey),
            FirstPersonFlags = (FirstPersonFlag)(1UL << 35), // SSBODY
            ArmorRating = 128,
            Value = 800,
            Weight = 9.0f,
            Health = 200,
            Keywords = SuitKws(),
            Resistances = new ExtendedList<DamageTypeValue> { new DamageTypeValue { Value = 128 } },
            Armatures = Addons(aaMark1Body),
        });
        mod.Armors.Add(new Armor(Sf(0x01754F), Release)
        {
            EditorID = Mark1HelmetEdid,
            Race = new FormLinkNullable<IRaceGetter>(human.FormKey),
            FirstPersonFlags = (FirstPersonFlag)(1UL << 36), // SSHelmet
            ArmorRating = 48,
            Value = 300,
            Weight = 3.0f,
            Health = 100,
            Keywords = SuitKws(),
            Resistances = new ExtendedList<DamageTypeValue> { new DamageTypeValue { Value = 48 } },
            Armatures = Addons(aaMark1Helm),
        });
        mod.Armors.Add(new Armor(Sf(0x01754E), Release)
        {
            EditorID = Mark1PackEdid,
            Race = new FormLinkNullable<IRaceGetter>(human.FormKey),
            FirstPersonFlags = (FirstPersonFlag)(1UL << 37), // SSBackpack
            ArmorRating = 40,
            Value = 250,
            Weight = 4.0f,
            Health = 100,
            Keywords = SuitKws(),
            Resistances = new ExtendedList<DamageTypeValue> { new DamageTypeValue { Value = 40 } },
            Armatures = Addons(aaMark1Pack),
        });

        mod.MiscItems.Add(new MiscItem(Sf(0x246B71), Release)
        {
            EditorID = BatteryMiscEdid,
            Value = 120,
            Weight = 1.5f,
            Keywords = new ExtendedList<IFormLinkGetter<IKeywordGetter>> { new FormLink<IKeywordGetter>(kwSuit.FormKey) },
        });

        mod.Furniture.Add(new Furniture(Sf(0x076E67), Release)
        {
            EditorID = DefaultControlEdid,
            MarkerModel = "Markers\\FurnitureMarkers\\ChairNeutral_Free_Marker.nif",
            Keywords = new ExtendedList<IFormLinkGetter<IKeywordGetter>> { new FormLink<IKeywordGetter>(kwSuit.FormKey) },
            Components = new ExtendedList<AComponent>
            {
                new KeywordFormComponent { Keywords = new ExtendedList<IFormLinkGetter<IKeywordGetter>> { new FormLink<IKeywordGetter>(kwSuit.FormKey) } },
            },
            MarkerParameters = new ExtendedList<FurnitureMarkerParameters> { new FurnitureMarkerParameters { Offset = new P3Float(0, 0.12f, 0) } },
            MarkerEntryPoints = new ExtendedList<FurnitureMarkerEntryPoints> { new FurnitureMarkerEntryPoints() },
        });

        mod.DefaultObjects.Add(new DefaultObject(Sf(0x05C254), Release) { EditorID = "PowerArmorRace_DO" });
        mod.DefaultObjects.Add(new DefaultObject(Sf(0x22BC97), Release) { EditorID = "PowerArmorDefaultFrameFurniture_DO" });
        mod.DefaultObjects.Add(new DefaultObject(Sf(0x15503E), Release) { EditorID = "PowerArmorDefaultFrameArmor_DO" });
        mod.DefaultObjects.Add(new DefaultObject(Sf(0x140C44), Release) { EditorID = "PowerArmorArmorKeyword_DO" });
        mod.DefaultObjects.Add(new DefaultObject(Sf(0x0BD5C5), Release) { EditorID = "PowerArmorDefaultBatteryObject_DO" });

        Directory.CreateDirectory(outDir);
        var sfPath = Path.Combine(outDir, "Starfield.esm");
        mod.BeginWrite.ToPath(sfPath).WithNoLoadOrder().Write();
        Console.WriteLine($"wrote synthetic {sfPath}");
        return 0;
    }

    public static int SelfTest(string scratchDir)
    {
        Directory.CreateDirectory(scratchDir);
        var fixDir = Path.Combine(scratchDir, "fixture");
        var cleanDir = Path.Combine(scratchDir, "clean");
        var noCellDir = Path.Combine(scratchDir, "no-test-cell");
        var dfobDir = Path.Combine(scratchDir, "dfob");
        if (Fixture(fixDir) != 0) return 1;
        var sfPath = Path.Combine(fixDir, "Starfield.esm");

        // 1. Default clean-room build (with test cell) & check
        if (Build(sfPath, cleanDir, DefaultControlEdid, overrideDfob: false, noTestCell: false) != 0) return 1;
        var cleanPlugin = Path.Combine(cleanDir, Plugin.FileName);
        if (Check(cleanPlugin, sfPath, DefaultControlEdid, overrideDfob: false, noTestCell: false) != 0) return 1;
        // Checking a clean build with --override-dfob or --no-test-cell must fail
        if (Check(cleanPlugin, sfPath, DefaultControlEdid, overrideDfob: true, noTestCell: false) == 0)
            throw new Refusal("selftest failed: clean build unexpectedly passed --override-dfob check");
        if (Check(cleanPlugin, sfPath, DefaultControlEdid, overrideDfob: false, noTestCell: true) == 0)
            throw new Refusal("selftest failed: default build with test cell unexpectedly passed --no-test-cell check");

        // 2. --no-test-cell build & check (omits FO4SF_PATestCell and placed test chairs/frame)
        if (Build(sfPath, noCellDir, DefaultControlEdid, overrideDfob: false, noTestCell: true) != 0) return 1;
        var noCellPlugin = Path.Combine(noCellDir, Plugin.FileName);
        if (Check(noCellPlugin, sfPath, DefaultControlEdid, overrideDfob: false, noTestCell: true) != 0) return 1;
        if (Check(noCellPlugin, sfPath, DefaultControlEdid, overrideDfob: false, noTestCell: false) == 0)
            throw new Refusal("selftest failed: --no-test-cell build unexpectedly passed default test-cell check");

        // 3. Opt-in --override-dfob build & check
        if (Build(sfPath, dfobDir, DefaultControlEdid, overrideDfob: true, noTestCell: false) != 0) return 1;
        var dfobPlugin = Path.Combine(dfobDir, Plugin.FileName);
        if (Check(dfobPlugin, sfPath, DefaultControlEdid, overrideDfob: true, noTestCell: false) != 0) return 1;
        // Checking a DFOB build without --override-dfob must fail (protects non-PA clean-room guarantee)
        if (Check(dfobPlugin, sfPath, DefaultControlEdid, overrideDfob: false, noTestCell: false) == 0)
            throw new Refusal("selftest failed: DFOB-overriding plugin unexpectedly passed clean-room check");

        // 4. Negative mutation: strip a limb AVIF from BPTD -> Check must fail
        var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        styles.Set(new KeyedMasterStyle(SfEsm, MasterStyle.Full));
        styles.Set(new KeyedMasterStyle(CoreValuesEsm, MasterStyle.Full));
        var badBptdDir = Path.Combine(scratchDir, "bad-bptd");
        {
            var mut = StarfieldMod.CreateFromBinary(cleanPlugin, Release, new BinaryReadParameters { MasterFlagsLookup = styles });
            mut.BodyParts.First().Parts[0].ActorValue.SetToNull();
            WritePlugin(mut, badBptdDir, SfEsm, CoreValuesEsm);
            if (Check(Path.Combine(badBptdDir, Plugin.FileName), sfPath, DefaultControlEdid, overrideDfob: false) == 0)
                throw new Refusal("selftest failed: missing limb AVIF on BPTD was not rejected");
        }

        // 5. Negative mutation: leak isPowerArmorFrame onto FO4SF_SalvagedNCRPowerArmor -> Check must fail
        var badSalvDir = Path.Combine(scratchDir, "bad-salvaged");
        {
            var mut = StarfieldMod.CreateFromBinary(cleanPlugin, Release, new BinaryReadParameters { MasterFlagsLookup = styles });
            var salv = mut.Armors.First(a => a.FormKey == Own(SalvagedBodyId));
            salv.Keywords ??= new ExtendedList<IFormLinkGetter<IKeywordGetter>>();
            salv.Keywords.Add(new FormLink<IKeywordGetter>(Sf(0x15503F)));
            WritePlugin(mut, badSalvDir, SfEsm, CoreValuesEsm);
            if (Check(Path.Combine(badSalvDir, Plugin.FileName), sfPath, DefaultControlEdid, overrideDfob: false) == 0)
                throw new Refusal("selftest failed: Salvaged NCR armor carrying isPowerArmorFrame was not rejected");
        }

        // 6. Negative mutation: remove FO4SF_PowerArmorRace from skin ARMA -> Check must fail
        var badSkinDir = Path.Combine(scratchDir, "bad-skin");
        {
            var mut = StarfieldMod.CreateFromBinary(cleanPlugin, Release, new BinaryReadParameters { MasterFlagsLookup = styles });
            foreach (var aa in mut.ArmorAddons) aa.AdditionalRaces?.Clear();
            WritePlugin(mut, badSkinDir, SfEsm, CoreValuesEsm);
            if (Check(Path.Combine(badSkinDir, Plugin.FileName), sfPath, DefaultControlEdid, overrideDfob: false) == 0)
                throw new Refusal("selftest failed: missing FO4SF_PowerArmorRace on cloned ARMAs was not rejected");
        }

        // 7. Negative mutation: point SalvagedAgiMgef away from FO4SFCoreValues.esm:0x815 -> Check must fail
        var badAgiDir = Path.Combine(scratchDir, "bad-agi");
        {
            var mut = StarfieldMod.CreateFromBinary(cleanPlugin, Release, new BinaryReadParameters { MasterFlagsLookup = styles });
            mut.MagicEffects.First(m => m.FormKey == Own(SalvagedAgiMgefId)).SecondActorValue.SetTo(Sf(0x0012C7));
            WritePlugin(mut, badAgiDir, SfEsm, CoreValuesEsm);
            if (Check(Path.Combine(badAgiDir, Plugin.FileName), sfPath, DefaultControlEdid, overrideDfob: false) == 0)
                throw new Refusal("selftest failed: SalvagedAgiMgef targeting Starfield Agility instead of FO4SFCoreValues.esm was not rejected");
        }

        // 8. Negative mutation: corrupt TestModeGlobal VMAD property -> Check must fail
        var badPropDir = Path.Combine(scratchDir, "bad-prop");
        {
            var mut = StarfieldMod.CreateFromBinary(cleanPlugin, Release, new BinaryReadParameters { MasterFlagsLookup = styles });
            var props = mut.Quests.First().VirtualMachineAdapter!.Scripts[0].Properties;
            ((ScriptObjectProperty)props[1]).Object.SetTo(Own(QuestId));
            WritePlugin(mut, badPropDir, SfEsm, CoreValuesEsm);
            if (Check(Path.Combine(badPropDir, Plugin.FileName), sfPath, DefaultControlEdid, overrideDfob: false) == 0)
                throw new Refusal("selftest failed: tampered TestModeGlobal VMAD property was not rejected");
        }

        Console.WriteLine("selftest pass: default build, --no-test-cell build, --override-dfob build, and 5 negative tamper checks all verified");
        return 0;
    }
}
