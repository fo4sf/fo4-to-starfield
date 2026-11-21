// CombatCore: CF-8 Combat Core writer & checker (docs/combat/combat-core.md).
//
// Writes FO4SFCombat.esm (masters [Starfield.esm, FO4SFCoreValues.esm]; adds records only, zero foreign overrides,
// zero duplicate EditorIDs with FO4SFCoreValues.esm or FO4SFProgression.esm):
//   Shared from FO4SFCoreValues.esm (via src/fo4sf/core/core_values.json):
//     0x811       AVIF FO4SF_Special_Perception
//     0x823       AVIF FO4SF_Skill_Guns
//     0x840       GLOB FO4SF_HardcoreEnabled
//     0x851       ALCH FO4SF_Stimpak (shared single stimpak across Hardcore & Combat)
//     0x860       GLOB FO4SF_TestModeEnabled
//   Owned in FO4SFCombat.esm:
//     0x800       QUST FO4SF_CombatQuest               StartGameEnabled combat controller quest
//     0x801..805  GLOB FO4SF_ActiveAmmoSubtype, FO4SF_VatsSlowTimeActive, FO4SF_CombatTitleRule,
//                      FO4SF_CombatHardcoreOverride, FO4SF_VatsApPool
//     0x808..80B  AVIF FO4SF_TargetDT, FO4SF_TargetDR, FO4SF_AimSwayPenalty, FO4SF_LimbCrippleMask
//     0x810..811  MGEF/ALCH FO4SF_DoctorsBagEffect & FO4SF_DoctorsBag
//     0x814       SPEL FO4SF_VatsSlowTimeAb            Unconditional slow-time ability (cloned SlowTimeChem 0x2A34F1)
//     0x815       MESG FO4SF_VatsLimbPickerMsg         7-button VATS limb selector
//     0x816..817  MISC FO4SF_VatsTriggerToken, FO4SF_AmmoCycleToken (console-free fallback triggers)
//     0x820..82B, 0x838..83A  AMMO 15 New Vegas ammo subtypes across 7.77mm, 11mm, Shotgun 12ga, Laser, and .50 Cal
//     0x82C..82F  FLST Calibre base ammo list + parallel AP/Slug, JHP/Flechette, and +P/Magnum subtype lists
//     0x830..835  COBJ 6 Reloading Bench recipes on WorkbenchIndustrialKeyword (0x0AA209) using #813 IRES salvage
//     0x836       FLST FO4SF_ReloadingRecipesList      Index of reloading-bench COBJ recipes
//     0x837       FLST FO4SF_CombatActionTokensList    Inventory event filter list for 0x816..0x817
//     0x840..842  BPTD FO4SF_CombatHumanBptd, FO4SF_CombatRobotBptd, FO4SF_CombatCreatureBptd
//     (Default test-cell mode additionally emits 0x844..84F ACTI range plates/switches, 0x850 FO4SF_CombatTestCell,
//      and 0x860..86B persistent placed targets; omitted when --no-test-cell is passed.)
//
// usage:
//   CombatCore build <Starfield.esm> <out_dir> [--json <core_values.json>] [--no-test-cell]
//   CombatCore check <FO4SFCombat.esm> <Starfield.esm> [--json <core_values.json>] [--no-test-cell]
//   CombatCore fixture <out_dir>
//   CombatCore selftest <scratch_dir>

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
    bool noTestCell = false;

    int jsonIdx = rest.IndexOf("--json");
    if (jsonIdx >= 0)
    {
        if (jsonIdx + 1 >= rest.Count) throw new CombatCore.Refusal("--json needs a path");
        jsonPath = rest[jsonIdx + 1];
        rest.RemoveRange(jsonIdx, 2);
    }
    int ntcIdx = rest.IndexOf("--no-test-cell");
    if (ntcIdx >= 0)
    {
        noTestCell = true;
        rest.RemoveAt(ntcIdx);
    }

    var opts = new CombatCore.BuildOptions(jsonPath ?? CombatCore.DefaultJsonPath(), noTestCell);
    if (rest.Count == 3 && rest[0] == "build") return CombatCore.Build(rest[1], rest[2], opts);
    if (rest.Count == 3 && rest[0] == "check") return CombatCore.Check(rest[1], rest[2], opts);
    if (rest.Count == 2 && rest[0] == "fixture") return CombatCore.Fixture(rest[1]);
    if (rest.Count == 2 && rest[0] == "selftest") return CombatCore.SelfTest(rest[1]);
}
catch (CombatCore.Refusal r)
{
    Console.Error.WriteLine("refused: " + r.Message);
    return 1;
}

Console.Error.WriteLine("usage: CombatCore build <Starfield.esm> <out_dir> [--json <path>] [--no-test-cell] | " +
                        "check <FO4SFCombat.esm> <Starfield.esm> [--json <path>] [--no-test-cell] | fixture <out_dir> | selftest <scratch_dir>");
return 2;

public static class CombatCore
{
    public sealed class Refusal(string m) : Exception(m);
    public record BuildOptions(string JsonPath, bool NoTestCell = false);

    const StarfieldRelease Release = StarfieldRelease.Starfield;
    static readonly ModKey SfEsm = ModKey.FromFileName("Starfield.esm");
    static readonly ModKey CoreValuesEsm = ModKey.FromFileName("FO4SFCoreValues.esm");
    public static readonly ModKey Plugin = ModKey.FromFileName("FO4SFCombat.esm");

    static readonly ModKey[] ExpectedMasters = { SfEsm, CoreValuesEsm };

    // Starfield.esm template & primitive FormIDs
    public const uint SfHeadCondId = 0x00036C;      // PerceptionCondition
    public const uint SfTorsoCondId = 0x00036D;     // EnduranceCondition
    public const uint SfLeftArmCondId = 0x00036E;   // LeftAttackCondition
    public const uint SfRightArmCondId = 0x00036F;  // RightAttackCondition
    public const uint SfLeftLegCondId = 0x000370;   // LeftMobilityCondition
    public const uint SfRightLegCondId = 0x000371;  // RightMobilityCondition
    public const uint SfBrainCondId = 0x000372;     // BrainCondition
    public const uint SfHealthId = 0x0002D4;        // Health
    public const uint SfSpeedMultId = 0x0002DA;     // SpeedMult

    public const uint SfHumanBptdId = 0x003481;     // HumanBodyPartData
    public const uint SfRobotBptdId = 0x00562C;     // ModelABodyPartData
    public const uint SfCreatureBptdId = 0x21E736;  // TerrormorphBodyPartData

    public const uint SfSlowTimeSpellId = 0x0B0885; // abBoostAssaultSlowTime
    public const uint SfSlowTimeMgefId = 0x2A34F1;  // SlowTimeChem
    public const uint SfIndustrialBenchKwId = 0x0AA209; // WorkbenchIndustrialKeyword

    public const uint SfAmmo777Id = 0x04AD3E;
    public const uint SfAmmo11mmId = 0x04AD3F;
    public const uint SfAmmoShotgunId = 0x0547A1;
    public const uint SfAmmoLaserId = 0x00E8EC;
    public const uint SfAmmo50CalId = 0x2B559A;

    public const uint SfGrendelId = 0x028A02;
    public const uint SfBreachId = 0x0547A3;
    public const uint SfTemplateActiId = 0x1CCAC2;
    public const uint SfFloorStatId = 0x050776;
    public const uint SfOmniLighId = 0x03D38C;
    public const uint SfCocMarkerId = 0x000032;

    // Owned FormIDs in FO4SFCombat.esm (>= 0x800)
    public const uint QuestId = 0x800;
    public const uint ActiveAmmoGlobId = 0x801;
    public const uint VatsActiveGlobId = 0x802;
    public const uint TitleRuleGlobId = 0x803;
    public const uint HardcoreOverrideGlobId = 0x804;
    public const uint VatsApPoolGlobId = 0x805;

    public const uint TargetDtAvifId = 0x808;
    public const uint TargetDrAvifId = 0x809;
    public const uint AimSwayAvifId = 0x80A;
    public const uint LimbMaskAvifId = 0x80B;

    public const uint DoctorsBagMgefId = 0x810;
    public const uint DoctorsBagAlchId = 0x811;
    public const uint VatsSlowTimeSpellId = 0x814;
    public const uint VatsLimbMsgId = 0x815;
    public const uint VatsTokenMiscId = 0x816;
    public const uint AmmoTokenMiscId = 0x817;

    public const uint Ammo777ApId = 0x820;
    public const uint Ammo777JhpId = 0x821;
    public const uint Ammo777PlusPId = 0x822;
    public const uint Ammo11mmApId = 0x823;
    public const uint Ammo11mmJhpId = 0x824;
    public const uint Ammo11mmPlusPId = 0x825;
    public const uint AmmoShotgunSlugId = 0x826;
    public const uint AmmoShotgunFlechetteId = 0x827;
    public const uint AmmoShotgunMagnumId = 0x828;
    public const uint AmmoLaserOverchargeId = 0x829;
    public const uint AmmoLaserOptimizedId = 0x82A;
    public const uint AmmoLaserMaxChargeId = 0x82B;

    public const uint CalibreBaseFlstId = 0x82C;
    public const uint SubtypeApFlstId = 0x82D;
    public const uint SubtypeJhpFlstId = 0x82E;
    public const uint SubtypePlusPFlstId = 0x82F;

    public const uint Rcpe777ApId = 0x830;
    public const uint Rcpe777JhpId = 0x831;
    public const uint Rcpe777PlusPId = 0x832;
    public const uint RcpeShotgunSlugId = 0x833;
    public const uint RcpeShotgunFlechetteId = 0x834;
    public const uint RcpeLaserOverchargeId = 0x835;
    public const uint ReloadingRecipesFlstId = 0x836;
    public const uint ActionTokensFlstId = 0x837;
    public const uint Ammo50CalApId = 0x838;
    public const uint Ammo50CalJhpId = 0x839;
    public const uint Ammo50CalPlusPId = 0x83A;

    public const uint HumanBptdId = 0x840;
    public const uint RobotBptdId = 0x841;
    public const uint CreatureBptdId = 0x842;

    public const uint ActiZoneHeadId = 0x844;
    public const uint ActiZoneTorsoId = 0x845;
    public const uint ActiZoneLeftArmId = 0x846;
    public const uint ActiZoneRightArmId = 0x847;
    public const uint ActiZoneLeftLegId = 0x848;
    public const uint ActiZoneRightLegId = 0x849;
    public const uint ActiArmoredTargetId = 0x84A;
    public const uint ActiVatsTargetId = 0x84B;
    public const uint ActiAmmoPedestalId = 0x84C;
    public const uint ActiLegTrapSwitchId = 0x84D;
    public const uint ActiHardcoreSwitchId = 0x84E;
    public const uint ActiSupplyRackId = 0x84F;

    public const uint TestCellId = 0x850;
    public const uint CocRefId = 0x851;

    public const uint ZoneHeadRefId = 0x860;
    public const uint ZoneTorsoRefId = 0x861;
    public const uint ZoneLeftArmRefId = 0x862;
    public const uint ZoneRightArmRefId = 0x863;
    public const uint ZoneLeftLegRefId = 0x864;
    public const uint ZoneRightLegRefId = 0x865;
    public const uint ArmoredTargetRefId = 0x866;
    public const uint VatsTargetRefId = 0x867;
    public const uint AmmoPedestalRefId = 0x868;
    public const uint LegTrapSwitchRefId = 0x869;
    public const uint HardcoreSwitchRefId = 0x86A;
    public const uint SupplyRackRefId = 0x86B;

    public static readonly ushort[] Stages = { 10, 20, 30, 40, 50 };

    public static readonly string[] VatsButtons =
    {
        "Head (2.0x Dmg, +4 AP)",
        "Torso (1.0x Dmg, +0 AP)",
        "Left Arm (0.85x Dmg, +2 AP)",
        "Right Arm (0.85x Dmg, +2 AP)",
        "Left Leg (0.85x Dmg, +2 AP)",
        "Right Leg (0.85x Dmg, +2 AP)",
        "Cancel VATS",
    };

    // Exact property declaration order in scripts/combat/FO4SF_CombatQuest.psc
    public static readonly string[] PropNames =
    {
        "ActiveAmmoSubtypeGlobal",
        "VatsSlowTimeActiveGlobal",
        "CombatTitleRuleGlobal",
        "HardcoreOverrideGlobal",
        "VatsApPoolGlobal",
        "HardcoreGlobal",
        "TestModeGlobal",
        "TargetDTAV",
        "TargetDRAV",
        "AimSwayPenaltyAV",
        "LimbCrippleMaskAV",
        "PerceptionAV",
        "GunsSkillAV",
        "HeadCondAV",
        "TorsoCondAV",
        "LeftArmCondAV",
        "RightArmCondAV",
        "LeftLegCondAV",
        "RightLegCondAV",
        "BrainCondAV",
        "SpeedMultAV",
        "HealthAV",
        "DoctorsBag",
        "CombatStimpak",
        "VatsSlowTimeAb",
        "VatsLimbPickerMsg",
        "VatsTriggerToken",
        "AmmoCycleToken",
        "ActionTokensList",
        "CalibreBaseAmmoList",
        "SubtypeAPList",
        "SubtypeJHPList",
        "SubtypePlusPList",
        "ReloadingRecipesList",
        "StarterRifle",
        "StarterShotgun",
        "ZonePlateHeadRef",
        "ZonePlateTorsoRef",
        "ZonePlateLeftArmRef",
        "ZonePlateRightArmRef",
        "ZonePlateLeftLegRef",
        "ZonePlateRightLegRef",
        "ArmoredTargetRef",
        "VatsTargetRef",
        "AmmoCyclePedestalRef",
        "LegTrapSwitchRef",
        "HardcoreToggleSwitchRef",
        "SupplyRackRef",
    };

    public const int TestRefPropCount = 12;

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

    public static Dictionary<string, FormKey> LoadCoreValues(string jsonPath)
    {
        if (!File.Exists(jsonPath)) throw new Refusal($"missing core_values.json: {jsonPath}");
        using var doc = JsonDocument.Parse(File.ReadAllText(jsonPath));
        var root = doc.RootElement;
        var pluginName = root.GetProperty("plugin").GetString() ?? throw new Refusal("core_values.json missing plugin");
        var modKey = ModKey.FromFileName(pluginName);
        if (modKey != CoreValuesEsm)
            throw new Refusal($"core_values.json plugin {modKey} != {CoreValuesEsm}");
        var byEdid = new Dictionary<string, FormKey>(StringComparer.OrdinalIgnoreCase);
        foreach (var el in root.GetProperty("records").EnumerateArray())
        {
            uint id = Convert.ToUInt32(el.GetProperty("id").GetString()!, 16);
            string edid = el.GetProperty("edid").GetString()!;
            byEdid[edid] = new FormKey(modKey, id);
        }
        return byEdid;
    }

    static FormKey RequireCore(Dictionary<string, FormKey> core, string edid) =>
        core.TryGetValue(edid, out var fk) ? fk : throw new Refusal($"core_values.json missing {edid}");

    static Cache<IModMasterStyledGetter, ModKey> MasterStyles(ModKey expectedKey)
    {
        var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        styles.Set(new KeyedMasterStyle(SfEsm, MasterStyle.Full));
        styles.Set(new KeyedMasterStyle(CoreValuesEsm, MasterStyle.Full));
        styles.Set(new KeyedMasterStyle(expectedKey, MasterStyle.Full));
        return styles;
    }

    static IStarfieldModDisposableGetter OpenMod(string path, ModKey expectedKey) =>
        StarfieldMod.CreateFromBinaryOverlay(path, Release, new BinaryReadParameters { MasterFlagsLookup = MasterStyles(expectedKey) });

    static ScriptObjectProperty ObjProp(string name, FormKey fk) => new()
    {
        Name = name,
        Flags = ScriptProperty.Flag.Edited,
        Object = new FormLink<IStarfieldMajorRecordGetter>(fk),
    };

    static Global MakeGlob(uint id, string edid, float val) => new(Own(id), Release)
    {
        EditorID = edid,
        FormVersion = 581,
        Data = val,
    };

    static ActorValueInformation MakeAvif(uint id, string edid, string name, float defVal) => new(Own(id), Release)
    {
        EditorID = edid,
        Name = name,
        DefaultValue = defVal,
        Flags = ActorValueInformation.Flag.DefaultToZero,
        FormVersion = 581,
    };

    static Ammunition MakeSubtypeAmmo(IAmmunitionGetter? tpl, uint id, string edid, string name, string shortName, uint val)
    {
        Ammunition a;
        if (tpl != null)
        {
            a = (Ammunition)tpl.Duplicate(Own(id), new Ammunition.TranslationMask(defaultOn: true) { Name = false, ShortName = false });
            a.EditorID = edid;
            a.Name = name;
            a.ShortName = shortName;
            a.VirtualMachineAdapter = null;
            a.Value = val;
        }
        else
        {
            a = new Ammunition(Own(id), Release)
            {
                EditorID = edid,
                Name = name,
                ShortName = shortName,
                Value = val,
                Weight = 0.01f,
                FormVersion = 581,
            };
        }
        return a;
    }

    static FormList MakeFormList(uint id, string edid, IEnumerable<FormKey> keys)
    {
        var fl = new FormList(Own(id), Release) { EditorID = edid, FormVersion = 581 };
        foreach (var k in keys) fl.Items.Add(k.ToLinkGetter<IStarfieldMajorRecordGetter>());
        return fl;
    }

    static FormKey MapStaleLimbAvif(uint rawId, string partNode)
    {
        return rawId switch
        {
            0x00038A => Sf(SfHeadCondId),
            0x00038B => Sf(SfLeftArmCondId),
            0x00038C => Sf(SfRightArmCondId),
            0x00038D => Sf(SfLeftLegCondId),
            0x00038E => Sf(SfRightLegCondId),
            0x00038F => Sf(SfTorsoCondId),
            0x000373 => Sf(SfBrainCondId),
            _ => partNode.Contains("Head", StringComparison.OrdinalIgnoreCase) ? Sf(SfHeadCondId)
               : partNode.Contains("Spine", StringComparison.OrdinalIgnoreCase) || partNode.Contains("Chest", StringComparison.OrdinalIgnoreCase) ? Sf(SfTorsoCondId)
               : partNode.Contains("L_Bicep", StringComparison.OrdinalIgnoreCase) ? Sf(SfLeftArmCondId)
               : partNode.Contains("R_Bicep", StringComparison.OrdinalIgnoreCase) ? Sf(SfRightArmCondId)
               : partNode.Contains("L_Thigh", StringComparison.OrdinalIgnoreCase) || partNode.Contains("L_Foot", StringComparison.OrdinalIgnoreCase) ? Sf(SfLeftLegCondId)
               : partNode.Contains("R_Thigh", StringComparison.OrdinalIgnoreCase) || partNode.Contains("R_Foot", StringComparison.OrdinalIgnoreCase) ? Sf(SfRightLegCondId)
               : FormKey.Null,
        };
    }

    static BodyPartData BuildRepairedBptd(IBodyPartDataGetter? tpl, uint id, string edid, float headMult, float torsoMult, float limbMult, float coreMult)
    {
        BodyPartData bptd;
        if (tpl != null)
        {
            bptd = (BodyPartData)tpl.Duplicate(Own(id), new BodyPartData.TranslationMask(defaultOn: true));
            bptd.EditorID = edid;
        }
        else
        {
            bptd = new BodyPartData(Own(id), Release) { EditorID = edid, FormVersion = 581 };
            bptd.Parts.Add(new BodyPart { Name = "Head", PartNode = "C_Head", VatsTarget = "C_Head", ActorValue = new FormLink<IActorValueInformationGetter>(Sf(SfHeadCondId)) });
            bptd.Parts.Add(new BodyPart { Name = "Torso", PartNode = "C_Spine", VatsTarget = "C_Chest", ActorValue = new FormLink<IActorValueInformationGetter>(Sf(SfTorsoCondId)) });
            bptd.Parts.Add(new BodyPart { Name = "LeftArm", PartNode = "L_Biceps", VatsTarget = "L_Biceps", ActorValue = new FormLink<IActorValueInformationGetter>(Sf(SfLeftArmCondId)) });
            bptd.Parts.Add(new BodyPart { Name = "RightArm", PartNode = "R_Biceps", VatsTarget = "R_Biceps", ActorValue = new FormLink<IActorValueInformationGetter>(Sf(SfRightArmCondId)) });
            bptd.Parts.Add(new BodyPart { Name = "LeftLeg", PartNode = "L_Thigh", VatsTarget = "L_Thigh", ActorValue = new FormLink<IActorValueInformationGetter>(Sf(SfLeftLegCondId)) });
            bptd.Parts.Add(new BodyPart { Name = "RightLeg", PartNode = "R_Thigh", VatsTarget = "R_Thigh", ActorValue = new FormLink<IActorValueInformationGetter>(Sf(SfRightLegCondId)) });
            bptd.Parts.Add(new BodyPart { Name = "LeftFoot", PartNode = "L_Foot", VatsTarget = "L_Foot", ActorValue = new FormLink<IActorValueInformationGetter>(Sf(SfLeftLegCondId)) });
            bptd.Parts.Add(new BodyPart { Name = "RightFoot", PartNode = "R_Foot", VatsTarget = "R_Foot", ActorValue = new FormLink<IActorValueInformationGetter>(Sf(SfRightLegCondId)) });
            bptd.Parts.Add(new BodyPart { Name = "Core", PartNode = "C_BackPack", VatsTarget = "C_BackPack", ActorValue = new FormLink<IActorValueInformationGetter>(Sf(SfBrainCondId)) });
        }

        foreach (var p in bptd.Parts)
        {
            string node = p.PartNode ?? string.Empty;
            if (!p.ActorValue.IsNull || !string.IsNullOrEmpty(node))
            {
                var mapped = MapStaleLimbAvif(p.ActorValue.FormKey.ID, node);
                if (!mapped.IsNull && (!p.ActorValue.IsNull || node.StartsWith("C_") || node.StartsWith("L_") || node.StartsWith("R_")))
                {
                    if (p.DamageMult > 0.0f || !p.ActorValue.IsNull)
                        p.ActorValue.SetTo(mapped);
                }
            }

            if (p.ActorValue.FormKey == Sf(SfHeadCondId))
                p.DamageMult = headMult;
            else if (p.ActorValue.FormKey == Sf(SfTorsoCondId))
                p.DamageMult = torsoMult;
            else if (p.ActorValue.FormKey == Sf(SfLeftArmCondId) || p.ActorValue.FormKey == Sf(SfRightArmCondId) ||
                     p.ActorValue.FormKey == Sf(SfLeftLegCondId) || p.ActorValue.FormKey == Sf(SfRightLegCondId))
                p.DamageMult = limbMult;
            else if (p.ActorValue.FormKey == Sf(SfBrainCondId))
                p.DamageMult = coreMult;
        }
        return bptd;
    }

    static Mutagen.Bethesda.Starfield.Activator CloneRangeActi(IActivatorGetter? tpl, uint id, string edid, string name, string prompt)
    {
        Mutagen.Bethesda.Starfield.Activator a;
        if (tpl != null)
        {
            a = new Mutagen.Bethesda.Starfield.Activator(Own(id), Release);
            a.DeepCopyIn(tpl, new Mutagen.Bethesda.Starfield.Activator.TranslationMask(defaultOn: true));
            a.VirtualMachineAdapter = null;
        }
        else
        {
            a = new Mutagen.Bethesda.Starfield.Activator(Own(id), Release) { FormVersion = 581 };
        }
        a.EditorID = edid;
        a.Name = name;
        a.ActivateTextOverride = prompt;
        return a;
    }

    static void AddCell(StarfieldMod mod, Cell cell)
    {
        var cid = cell.FormKey.ID;
        var block = new CellBlock { BlockNumber = (int)(cid % 10), GroupType = GroupTypeEnum.InteriorCellBlock };
        var sub = new CellSubBlock { BlockNumber = (int)((cid / 10) % 10), GroupType = GroupTypeEnum.InteriorCellSubBlock };
        sub.Cells.Add(cell);
        block.SubBlocks.Add(sub);
        mod.Cells.Records.Add(block);
    }

    static void WriteMod(StarfieldMod mod, string outDir)
    {
        Directory.CreateDirectory(outDir);
        string outPath = Path.Combine(outDir, Plugin.FileName);
        string tmpDir = Path.Combine(outDir, ".tmp-" + Guid.NewGuid().ToString("N"));
        try
        {
            Directory.CreateDirectory(tmpDir);
            string tmpPath = Path.Combine(tmpDir, Plugin.FileName);
            mod.WriteToBinary(tmpPath, new BinaryWriteParameters
            {
                ModKey = ModKeyOption.NoCheck,
                MastersListOrdering = new MastersListOrderingByLoadOrder(ExpectedMasters),
                MasterFlagsLookup = MasterStyles(Plugin),
            });
            File.Move(tmpPath, outPath, overwrite: true);
        }
        finally
        {
            if (Directory.Exists(tmpDir)) Directory.Delete(tmpDir, true);
        }
    }

    public static int Build(string sfPath, string outDir, BuildOptions? opts = null)
    {
        opts ??= new BuildOptions(DefaultJsonPath(), false);
        var core = LoadCoreValues(opts.JsonPath);
        var perceptionAvKey = RequireCore(core, "FO4SF_Special_Perception");
        var gunsSkillAvKey = RequireCore(core, "FO4SF_Skill_Guns");
        var hardcoreGlobKey = RequireCore(core, "FO4SF_HardcoreEnabled");
        var stimpakAlchKey = RequireCore(core, "FO4SF_Stimpak");
        var testModeGlobKey = RequireCore(core, "FO4SF_TestModeEnabled");

        if (!File.Exists(sfPath)) throw new Refusal("Starfield.esm missing: " + sfPath);
        using var sf = OpenMod(sfPath, SfEsm);

        // Verify live Starfield.esm limb condition & stat AVIFs
        uint[] reqAvifs =
        {
            SfHeadCondId, SfTorsoCondId, SfLeftArmCondId, SfRightArmCondId,
            SfLeftLegCondId, SfRightLegCondId, SfBrainCondId, SfHealthId, SfSpeedMultId
        };
        foreach (var aid in reqAvifs)
        {
            if (!sf.ActorValueInformation.Any(a => a.FormKey == Sf(aid)))
                throw new Refusal($"Starfield.esm missing required AVIF 0x{aid:X6}");
        }

        IAmmunitionGetter? FindAmmo(uint id, string edid) =>
            sf.Ammunitions.FirstOrDefault(a => a.FormKey == Sf(id))
            ?? sf.Ammunitions.FirstOrDefault(a => string.Equals(a.EditorID, edid, StringComparison.OrdinalIgnoreCase))
            ?? sf.Ammunitions.FirstOrDefault();

        var ammo777 = FindAmmo(SfAmmo777Id, "Ammo777mm") ?? throw new Refusal("no Ammo template in Starfield.esm");
        var ammo11mm = FindAmmo(SfAmmo11mmId, "Ammo11mm") ?? ammo777;
        var ammoShotgun = FindAmmo(SfAmmoShotgunId, "AmmoShotgun") ?? ammo777;
        var ammoLaser = FindAmmo(SfAmmoLaserId, "AmmoLaser") ?? ammo777;
        var ammo50 = FindAmmo(SfAmmo50CalId, "Ammo50Cal") ?? ammo777;

        var weapRifle = sf.Weapons.FirstOrDefault(w => w.FormKey == Sf(SfGrendelId))
                        ?? sf.Weapons.FirstOrDefault()
                        ?? throw new Refusal("no Weapon template in Starfield.esm");
        var weapShotgun = sf.Weapons.FirstOrDefault(w => w.FormKey == Sf(SfBreachId)) ?? weapRifle;

        var aidTpl = sf.Ingestibles.FirstOrDefault(a => string.Equals(a.EditorID, "Aid_MedPack", StringComparison.OrdinalIgnoreCase))
                     ?? sf.Ingestibles.FirstOrDefault();
        var actiTpl = sf.Activators.FirstOrDefault(a => a.FormKey == Sf(SfTemplateActiId))
                      ?? sf.Activators.FirstOrDefault();
        var cobjTpl = sf.ConstructibleObjects.FirstOrDefault(c => string.Equals(c.EditorID, "co_mfg_Tier01_AdaptiveFrame", StringComparison.OrdinalIgnoreCase))
                      ?? sf.ConstructibleObjects.FirstOrDefault();
        var indBenchKw = sf.Keywords.FirstOrDefault(k => k.FormKey == Sf(SfIndustrialBenchKwId))
                         ?? sf.Keywords.FirstOrDefault(k => string.Equals(k.EditorID, "WorkbenchIndustrialKeyword", StringComparison.OrdinalIgnoreCase))
                         ?? sf.Keywords.FirstOrDefault()
                         ?? throw new Refusal("no Keyword in Starfield.esm");

        FormKey FindRes(string edid)
        {
            var r = sf.Resources.FirstOrDefault(x => string.Equals(x.EditorID, edid, StringComparison.OrdinalIgnoreCase))
                    ?? sf.Resources.FirstOrDefault();
            if (r == null) throw new Refusal("no IRES Resource records in Starfield.esm");
            return r.FormKey;
        }

        var resLead = FindRes("ResInorgCommonLead");
        var resIron = FindRes("ResInorgCommonIron");
        var resCopper = FindRes("ResInorgCommonCopper");
        var resTungsten = FindRes("ResInorgUncommonTungsten");
        var resOil = FindRes("ResOrgExoticLubricant");
        var resUranium = FindRes("ResInorgCommonUranium");

        var mod = new StarfieldMod(Plugin, Release);
        mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        mod.ModHeader.Author = "fo4-to-starfield";

        // 1. Globals & AVIFs
        mod.Globals.Add(MakeGlob(ActiveAmmoGlobId, "FO4SF_ActiveAmmoSubtype", 0f));
        mod.Globals.Add(MakeGlob(VatsActiveGlobId, "FO4SF_VatsSlowTimeActive", 0f));
        mod.Globals.Add(MakeGlob(TitleRuleGlobId, "FO4SF_CombatTitleRule", 0f));
        mod.Globals.Add(MakeGlob(HardcoreOverrideGlobId, "FO4SF_CombatHardcoreOverride", -1f));
        mod.Globals.Add(MakeGlob(VatsApPoolGlobId, "FO4SF_VatsApPool", 100f));

        mod.ActorValueInformation.Add(MakeAvif(TargetDtAvifId, "FO4SF_TargetDT", "Damage Threshold", 0f));
        mod.ActorValueInformation.Add(MakeAvif(TargetDrAvifId, "FO4SF_TargetDR", "Damage Resistance", 0f));
        mod.ActorValueInformation.Add(MakeAvif(AimSwayAvifId, "FO4SF_AimSwayPenalty", "Crippled Limb Sway", 0f));
        mod.ActorValueInformation.Add(MakeAvif(LimbMaskAvifId, "FO4SF_LimbCrippleMask", "Crippled Limb Mask", 0f));

        // 2. Limb cure item (Doctor's Bag; Stimpak is shared in FO4SFCoreValues.esm:0x851 FO4SF_Stimpak)
        var docMgef = new MagicEffect(Own(DoctorsBagMgefId), Release)
        {
            EditorID = "FO4SF_DoctorsBagEffect",
            Name = "Restore Crippled Limbs",
            CastType = CastType.FireAndForget,
            TargetType = TargetType.Self,
            Flags = MagicEffect.Flag.Recover | MagicEffect.Flag.NoHitEvent,
            Archetype = new MagicEffectArchetype(MagicEffectArchetype.TypeEnum.ValueModifier),
            FormVersion = 581,
        };
        docMgef.SecondActorValue.SetTo(Sf(SfHealthId));
        mod.MagicEffects.Add(docMgef);

        Ingestible MakeMedicine(uint id, string edid, string name, string desc, float weight, uint val, FormKey effKey, float mag)
        {
            Ingestible item;
            if (aidTpl != null)
            {
                item = (Ingestible)aidTpl.Duplicate(Own(id), new Ingestible.TranslationMask(defaultOn: true) { Name = false, Description = false });
                item.VirtualMachineAdapter = null;
                item.Keywords = null;
                item.Addiction.SetToNull();
                item.Effects.Clear();
            }
            else
            {
                item = new Ingestible(Own(id), Release) { FormVersion = 581 };
            }
            item.EditorID = edid;
            item.Name = name;
            item.Description = desc;
            item.Weight = weight;
            item.Value = val;
            item.Flags = Ingestible.Flag.NoAutoCalc | Ingestible.Flag.Medicine;
            item.MajorFlags |= Ingestible.MajorFlag.Medicine;
            item.Effects.Add(new Effect
            {
                BaseEffect = new FormLinkNullable<IMagicEffectGetter>(effKey),
                Data = new EffectData { Magnitude = mag, Area = 0, Duration = 0 },
            });
            return item;
        }

        mod.Ingestibles.Add(MakeMedicine(DoctorsBagAlchId, "FO4SF_DoctorsBag", "Doctor's Bag",
            "Restores all crippled limbs immediately in both Normal and Hardcore survival modes.", 1.0f, 55, docMgef.FormKey, 5f));

        // 3. Unconditional VATS Slow-Time Ability Spell + VATS Limb Picker Message + Fallback Tokens + Filter FLST
        var slowSpellTpl = sf.Spells.FirstOrDefault(s => s.FormKey == Sf(SfSlowTimeSpellId));
        var slowMgefKey = sf.MagicEffects.Any(m => m.FormKey == Sf(SfSlowTimeMgefId)) ? Sf(SfSlowTimeMgefId) : docMgef.FormKey;
        Spell vatsSpell;
        if (slowSpellTpl != null)
        {
            vatsSpell = (Spell)slowSpellTpl.Duplicate(Own(VatsSlowTimeSpellId), new Spell.TranslationMask(defaultOn: true) { Name = false, Description = false });
            vatsSpell.VirtualMachineAdapter = null;
            foreach (var ef in vatsSpell.Effects)
            {
                ef.Conditions.Clear();
                if (ef.Data != null) ef.Data.Magnitude = 0.25f;
            }
        }
        else
        {
            vatsSpell = new Spell(Own(VatsSlowTimeSpellId), Release)
            {
                Type = Spell.SpellType.Ability,
                CastType = CastType.FireAndForget,
                TargetType = TargetType.Self,
                FormVersion = 581,
            };
            vatsSpell.Effects.Add(new Effect
            {
                BaseEffect = new FormLinkNullable<IMagicEffectGetter>(slowMgefKey),
                Data = new EffectData { Magnitude = 0.25f, Area = 0, Duration = 0 },
            });
        }
        vatsSpell.EditorID = "FO4SF_VatsSlowTimeAb";
        vatsSpell.Name = "VATS Tactical Slow Time";
        vatsSpell.Description = string.Empty;
        mod.Spells.Add(vatsSpell);

        var vatsMsg = new Message(Own(VatsLimbMsgId), Release)
        {
            EditorID = "FO4SF_VatsLimbPickerMsg",
            Name = "V.A.T.S. Tactical Targeting",
            Description = "Time slowed to 25%. Select target limb to queue aimed shot (AP cost and hit chance logged from range, weapon skill, and PER):",
            Flags = Message.Flag.MessageBox,
            FormVersion = 581,
        };
        foreach (var b in VatsButtons) vatsMsg.MenuButtons.Add(new MessageButton { Text = b });
        mod.Messages.Add(vatsMsg);

        mod.MiscItems.Add(new MiscItem(Own(VatsTokenMiscId), Release)
        {
            EditorID = "FO4SF_VatsTriggerToken",
            Name = "VATS Targeting Slate (Drop or Press V)",
            Weight = 0f,
            Value = 0,
            FormVersion = 581,
        });
        mod.MiscItems.Add(new MiscItem(Own(AmmoTokenMiscId), Release)
        {
            EditorID = "FO4SF_AmmoCycleToken",
            Name = "Ammo Subtype Cycler Slate (Drop or Press N)",
            Weight = 0f,
            Value = 0,
            FormVersion = 581,
        });
        mod.FormLists.Add(MakeFormList(ActionTokensFlstId, "FO4SF_CombatActionTokensList", new[]
        {
            Own(VatsTokenMiscId), Own(AmmoTokenMiscId),
        }));

        // 4. Calibre Subtype AMMO records (15 total across all 5 calibres) + Zero-Weapon-Edit Calibre Data-Table FormLists
        mod.Ammunitions.Add(MakeSubtypeAmmo(ammo777, Ammo777ApId, "FO4SF_Ammo777_AP", "7.77mm Caseless, AP", "7.77mm AP", 18));
        mod.Ammunitions.Add(MakeSubtypeAmmo(ammo777, Ammo777JhpId, "FO4SF_Ammo777_JHP", "7.77mm Caseless, JHP", "7.77mm JHP", 18));
        mod.Ammunitions.Add(MakeSubtypeAmmo(ammo777, Ammo777PlusPId, "FO4SF_Ammo777_PlusP", "7.77mm Caseless, +P", "7.77mm +P", 22));

        mod.Ammunitions.Add(MakeSubtypeAmmo(ammo11mm, Ammo11mmApId, "FO4SF_Ammo11mm_AP", "11mm Caseless, AP", "11mm AP", 20));
        mod.Ammunitions.Add(MakeSubtypeAmmo(ammo11mm, Ammo11mmJhpId, "FO4SF_Ammo11mm_JHP", "11mm Caseless, JHP", "11mm JHP", 20));
        mod.Ammunitions.Add(MakeSubtypeAmmo(ammo11mm, Ammo11mmPlusPId, "FO4SF_Ammo11mm_PlusP", "11mm Caseless, +P", "11mm +P", 24));

        mod.Ammunitions.Add(MakeSubtypeAmmo(ammoShotgun, AmmoShotgunSlugId, "FO4SF_AmmoShotgun_Slug", "12g Shotgun, Rifled Slug", "12g Slug", 30));
        mod.Ammunitions.Add(MakeSubtypeAmmo(ammoShotgun, AmmoShotgunFlechetteId, "FO4SF_AmmoShotgun_Flechette", "12g Shotgun, Flechette (AP)", "12g Flech", 34));
        mod.Ammunitions.Add(MakeSubtypeAmmo(ammoShotgun, AmmoShotgunMagnumId, "FO4SF_AmmoShotgun_Magnum", "12g Shotgun, Magnum (+P)", "12g Mag", 34));

        mod.Ammunitions.Add(MakeSubtypeAmmo(ammoLaser, AmmoLaserOverchargeId, "FO4SF_AmmoLaser_Overcharge", "3kV LZR, Overcharge", "3kV OC", 44));
        mod.Ammunitions.Add(MakeSubtypeAmmo(ammoLaser, AmmoLaserOptimizedId, "FO4SF_AmmoLaser_Optimized", "3kV LZR, Optimized", "3kV Opt", 42));
        mod.Ammunitions.Add(MakeSubtypeAmmo(ammoLaser, AmmoLaserMaxChargeId, "FO4SF_AmmoLaser_MaxCharge", "3kV LZR, Max Charge", "3kV Max", 52));

        mod.Ammunitions.Add(MakeSubtypeAmmo(ammo50, Ammo50CalApId, "FO4SF_Ammo50Cal_AP", ".50 Cal, Armor Piercing", ".50 AP", 55));
        mod.Ammunitions.Add(MakeSubtypeAmmo(ammo50, Ammo50CalJhpId, "FO4SF_Ammo50Cal_JHP", ".50 Cal, Hollow Point", ".50 JHP", 55));
        mod.Ammunitions.Add(MakeSubtypeAmmo(ammo50, Ammo50CalPlusPId, "FO4SF_Ammo50Cal_PlusP", ".50 Cal, Overpressure +P", ".50 +P", 62));

        mod.FormLists.Add(MakeFormList(CalibreBaseFlstId, "FO4SF_CalibreBaseAmmoList", new[]
        {
            ammo777.FormKey, ammo11mm.FormKey, ammoShotgun.FormKey, ammoLaser.FormKey, ammo50.FormKey,
        }));
        mod.FormLists.Add(MakeFormList(SubtypeApFlstId, "FO4SF_SubtypeAPList", new[]
        {
            Own(Ammo777ApId), Own(Ammo11mmApId), Own(AmmoShotgunSlugId), Own(AmmoLaserOverchargeId), Own(Ammo50CalApId),
        }));
        mod.FormLists.Add(MakeFormList(SubtypeJhpFlstId, "FO4SF_SubtypeJHPList", new[]
        {
            Own(Ammo777JhpId), Own(Ammo11mmJhpId), Own(AmmoShotgunFlechetteId), Own(AmmoLaserOptimizedId), Own(Ammo50CalJhpId),
        }));
        mod.FormLists.Add(MakeFormList(SubtypePlusPFlstId, "FO4SF_SubtypePlusPList", new[]
        {
            Own(Ammo777PlusPId), Own(Ammo11mmPlusPId), Own(AmmoShotgunMagnumId), Own(AmmoLaserMaxChargeId), Own(Ammo50CalPlusPId),
        }));

        // 5. Reloading-Bench COBJ Recipes hooking #813 (WorkbenchIndustrialKeyword + IRES components)
        void AddReloadRecipe(uint id, string edid, string desc, uint productAmmoId, ushort amount, float sort, (FormKey Res, uint Cnt)[] costs)
        {
            ConstructibleObject cobj;
            if (cobjTpl != null)
            {
                cobj = (ConstructibleObject)cobjTpl.Duplicate(Own(id), new ConstructibleObject.TranslationMask(defaultOn: true) { Description = false });
                cobj.VirtualMachineAdapter = null;
                cobj.Conditions.Clear();
                cobj.RequiredPerks?.Clear();
                cobj.RepairComponents?.Clear();
                cobj.LearnedFrom.Clear();
                cobj.MaxBuildCountGlobal.Clear();
                cobj.InstantiationFilterKeyword.Clear();
            }
            else
            {
                cobj = new ConstructibleObject(Own(id), Release) { FormVersion = 581 };
            }
            cobj.EditorID = edid;
            cobj.Description = desc;
            cobj.AmountProduced = amount;
            cobj.MenuSortOrder = sort;
            cobj.Tier = 0;
            cobj.LearnMethod = ConstructibleObject.LearnMethodEnum.DefaultOrConditions;
            cobj.WorkbenchKeyword.SetTo(indBenchKw.FormKey);
            cobj.RecipeFilters = new ExtendedList<IFormLinkGetter<IKeywordGetter>>();
            cobj.CreatedObject.SetTo(Own(productAmmoId));
            cobj.ConstructableComponents = new ExtendedList<ConstructibleObjectComponent>();
            foreach (var (res, cnt) in costs)
            {
                var cc = new ConstructibleObjectComponent { RequiredCount = cnt };
                cc.Component.SetTo(res);
                cobj.ConstructableComponents.Add(cc);
            }
            mod.ConstructibleObjects.Add(cobj);
        }

        AddReloadRecipe(Rcpe777ApId, "FO4SF_RCPE_Ammo777_AP", "Handload armor-piercing 7.77mm penetrator rounds at an industrial reloading bench.",
            Ammo777ApId, 24, 30f, new[] { (resLead, 2u), (resIron, 2u), (resCopper, 1u) });
        AddReloadRecipe(Rcpe777JhpId, "FO4SF_RCPE_Ammo777_JHP", "Handload jacketed hollow-point 7.77mm soft-target rounds.",
            Ammo777JhpId, 24, 31f, new[] { (resLead, 3u), (resCopper, 2u) });
        AddReloadRecipe(Rcpe777PlusPId, "FO4SF_RCPE_Ammo777_PlusP", "Handload overpressure +P 7.77mm high-velocity rounds.",
            Ammo777PlusPId, 24, 32f, new[] { (resLead, 2u), (resCopper, 2u), (resOil, 1u) });
        AddReloadRecipe(RcpeShotgunSlugId, "FO4SF_RCPE_Shotgun_Slug", "Swage heavy 12-gauge rifled slugs for armor penetration.",
            AmmoShotgunSlugId, 12, 33f, new[] { (resLead, 3u), (resIron, 1u) });
        AddReloadRecipe(RcpeShotgunFlechetteId, "FO4SF_RCPE_Shotgun_Flechette", "Pack tungsten dart flechettes into 12-gauge shells.",
            AmmoShotgunFlechetteId, 12, 34f, new[] { (resIron, 2u), (resTungsten, 2u) });
        AddReloadRecipe(RcpeLaserOverchargeId, "FO4SF_RCPE_Laser_Overcharge", "Overcharge 3kV laser cells for higher output and armor bypass.",
            AmmoLaserOverchargeId, 20, 35f, new[] { (resCopper, 2u), (resUranium, 1u) });

        mod.FormLists.Add(MakeFormList(ReloadingRecipesFlstId, "FO4SF_ReloadingRecipesList", new[]
        {
            Own(Rcpe777ApId), Own(Rcpe777JhpId), Own(Rcpe777PlusPId),
            Own(RcpeShotgunSlugId), Own(RcpeShotgunFlechetteId), Own(RcpeLaserOverchargeId),
        }));

        // 6. Repaired BPTD BodyPartData records (Human 8-part set, Robot, Creature)
        var humanTpl = sf.BodyParts.FirstOrDefault(b => b.FormKey == Sf(SfHumanBptdId));
        var robotTpl = sf.BodyParts.FirstOrDefault(b => b.FormKey == Sf(SfRobotBptdId)) ?? humanTpl;
        var creatureTpl = sf.BodyParts.FirstOrDefault(b => b.FormKey == Sf(SfCreatureBptdId)) ?? humanTpl;

        mod.BodyParts.Add(BuildRepairedBptd(humanTpl, HumanBptdId, "FO4SF_CombatHumanBptd", 2.00f, 1.00f, 0.85f, 1.50f));
        mod.BodyParts.Add(BuildRepairedBptd(robotTpl, RobotBptdId, "FO4SF_CombatRobotBptd", 1.25f, 0.75f, 0.85f, 1.65f));
        mod.BodyParts.Add(BuildRepairedBptd(creatureTpl, CreatureBptdId, "FO4SF_CombatCreatureBptd", 1.75f, 0.90f, 0.85f, 1.85f));

        // 7. Optional Range Activators & Interior Combat Test Cell (`FO4SF_CombatTestCell` 0x850)
        uint nextRef = CreatureBptdId + 1;
        if (!opts.NoTestCell)
        {
            mod.Activators.Add(CloneRangeActi(actiTpl, ActiZoneHeadId, "FO4SF_Acti_ZoneHead", "Silhouette Zone: Head (2.0x)", "Inspect Zone"));
            mod.Activators.Add(CloneRangeActi(actiTpl, ActiZoneTorsoId, "FO4SF_Acti_ZoneTorso", "Silhouette Zone: Torso (1.0x)", "Inspect Zone"));
            mod.Activators.Add(CloneRangeActi(actiTpl, ActiZoneLeftArmId, "FO4SF_Acti_ZoneLeftArm", "Silhouette Zone: Left Arm (0.85x)", "Inspect Zone"));
            mod.Activators.Add(CloneRangeActi(actiTpl, ActiZoneRightArmId, "FO4SF_Acti_ZoneRightArm", "Silhouette Zone: Right Arm (0.85x)", "Inspect Zone"));
            mod.Activators.Add(CloneRangeActi(actiTpl, ActiZoneLeftLegId, "FO4SF_Acti_ZoneLeftLeg", "Silhouette Zone: Left Leg (0.85x)", "Inspect Zone"));
            mod.Activators.Add(CloneRangeActi(actiTpl, ActiZoneRightLegId, "FO4SF_Acti_ZoneRightLeg", "Silhouette Zone: Right Leg (0.85x)", "Inspect Zone"));
            mod.Activators.Add(CloneRangeActi(actiTpl, ActiArmoredTargetId, "FO4SF_Acti_ArmoredTarget", "High-DT Armored Target (DT 18 / DR 15%)", "Inspect Armor Target"));
            mod.Activators.Add(CloneRangeActi(actiTpl, ActiVatsTargetId, "FO4SF_Acti_VatsTarget", "VATS Combat Target Dummy", "Engage VATS"));
            mod.Activators.Add(CloneRangeActi(actiTpl, ActiAmmoPedestalId, "FO4SF_Acti_AmmoPedestal", "Ammo Subtype Cycler (Standard / AP / JHP / +P)", "Cycle Ammo Subtype"));
            mod.Activators.Add(CloneRangeActi(actiTpl, ActiLegTrapSwitchId, "FO4SF_Acti_LegTrapSwitch", "Leg-Cripple Fracture Rig", "Trigger Leg Cripple"));
            mod.Activators.Add(CloneRangeActi(actiTpl, ActiHardcoreSwitchId, "FO4SF_Acti_HardcoreSwitch", "Hardcore Cure Rule Toggle", "Toggle Normal / Hardcore"));
            mod.Activators.Add(CloneRangeActi(actiTpl, ActiSupplyRackId, "FO4SF_Acti_SupplyRack", "Combat Core Weapon & Medical Supply Rack", "Draw Weapons & Supplies"));

            var cell = new Cell(Own(TestCellId), Release)
            {
                EditorID = "FO4SF_CombatTestCell",
                Name = "FO4SF Combat Core Firing Range",
                Flags = Cell.Flag.IsInteriorCell,
                FormVersion = 581,
                EnvironmentMap = "Data\\Textures\\Cubemaps\\Cell_HiTechHallCube.dds",
            };
            if (sf.LightingTemplates.Any(l => l.FormKey == Sf(0x006658)))
                cell.LightingTemplate.SetTo(Sf(0x006658));
            if (sf.ImageSpaces.Any(i => i.FormKey == Sf(0x122393)))
                cell.ImageSpace.SetTo(Sf(0x122393));

            PlacedObject AddPersist(uint refId, FormKey baseKey, float x, float y, float z, float rotZ = 0f, float scale = 1.0f)
            {
                var p = new PlacedObject(Own(refId), Release)
                {
                    Base = new FormLinkNullable<IPlaceableObjectGetter>(baseKey),
                    Position = new P3Float(x, y, z),
                    Rotation = new P3Float(0f, 0f, rotZ),
                    Scale = scale,
                    FormVersion = 581,
                };
                p.MajorRecordFlagsRaw |= 0x400; // Persistent
                cell.Persistent.Add(p);
                return p;
            }

            nextRef = 0x870u;
            if (sf.Statics.Any(s => s.FormKey == Sf(SfCocMarkerId)) || sf.EnumerateMajorRecords().Any(r => r.FormKey == Sf(SfCocMarkerId)))
                AddPersist(CocRefId, Sf(SfCocMarkerId), 0f, -4f, 0.65f);
            else
                AddPersist(CocRefId, Own(ActiSupplyRackId), 0f, -4f, 0.65f);

            if (sf.Statics.Any(s => s.FormKey == Sf(SfFloorStatId)))
            {
                for (int gx = -1; gx <= 1; gx++)
                {
                    for (int gy = -1; gy <= 2; gy++)
                    {
                        cell.Temporary.Add(new PlacedObject(Own(nextRef++), Release)
                        {
                            Base = new FormLinkNullable<IPlaceableObjectGetter>(Sf(SfFloorStatId)),
                            Position = new P3Float(gx * 7.5f - 2.0f, gy * 7.5f, 0f),
                            FormVersion = 581,
                        });
                    }
                }
            }
            if (sf.Lights.Any(l => l.FormKey == Sf(SfOmniLighId)))
            {
                cell.Temporary.Add(new PlacedObject(Own(nextRef++), Release)
                {
                    Base = new FormLinkNullable<IPlaceableObjectGetter>(Sf(SfOmniLighId)),
                    Position = new P3Float(0f, 2f, 4f),
                    FormVersion = 581,
                });
            }

            // Lane A (x = -3.0, y = +6.0): 6-Zone Anatomical Silhouette
            AddPersist(ZoneHeadRefId, Own(ActiZoneHeadId), -3.0f, 6.0f, 1.85f, 0f, 0.45f);
            AddPersist(ZoneTorsoRefId, Own(ActiZoneTorsoId), -3.0f, 6.0f, 1.15f, 0f, 0.65f);
            AddPersist(ZoneLeftArmRefId, Own(ActiZoneLeftArmId), -3.75f, 6.0f, 1.25f, 0f, 0.42f);
            AddPersist(ZoneRightArmRefId, Own(ActiZoneRightArmId), -2.25f, 6.0f, 1.25f, 0f, 0.42f);
            AddPersist(ZoneLeftLegRefId, Own(ActiZoneLeftLegId), -3.35f, 6.0f, 0.45f, 0f, 0.45f);
            AddPersist(ZoneRightLegRefId, Own(ActiZoneRightLegId), -2.65f, 6.0f, 0.45f, 0f, 0.45f);

            // Lane B (x = +0.5, y = +6.0): High-DT Armored Target + Ammo Cycle Pedestal
            AddPersist(ArmoredTargetRefId, Own(ActiArmoredTargetId), 0.5f, 6.0f, 1.0f);
            AddPersist(AmmoPedestalRefId, Own(ActiAmmoPedestalId), 0.5f, 1.0f, 0.0f);

            // Lane C (x = +3.5, y = +6.0): VATS Target + Supply Rack + Leg-Cripple & Hardcore Switches
            AddPersist(VatsTargetRefId, Own(ActiVatsTargetId), 3.5f, 6.0f, 1.0f);
            AddPersist(SupplyRackRefId, Own(ActiSupplyRackId), -1.5f, -1.5f, 0.0f);
            AddPersist(LegTrapSwitchRefId, Own(ActiLegTrapSwitchId), 2.0f, -1.5f, 0.0f);
            AddPersist(HardcoreSwitchRefId, Own(ActiHardcoreSwitchId), 3.2f, -1.5f, 0.0f);

            AddCell(mod, cell);
        }

        // 8. StartGameEnabled Combat Controller Quest
        var quest = new Quest(Own(QuestId), Release)
        {
            EditorID = "FO4SF_CombatQuest",
            Name = "FO4SF Combat Core Controller",
            FormVersion = 581,
            Version2 = 12,
            Data = new QuestData { Flags = Quest.Flag.StartGameEnabled, Priority = 45 },
        };
        foreach (var s in Stages) quest.Stages.Add(new QuestStage { Index = s });

        var propMap = new Dictionary<string, FormKey>
        {
            ["ActiveAmmoSubtypeGlobal"] = Own(ActiveAmmoGlobId),
            ["VatsSlowTimeActiveGlobal"] = Own(VatsActiveGlobId),
            ["CombatTitleRuleGlobal"] = Own(TitleRuleGlobId),
            ["HardcoreOverrideGlobal"] = Own(HardcoreOverrideGlobId),
            ["VatsApPoolGlobal"] = Own(VatsApPoolGlobId),
            ["HardcoreGlobal"] = hardcoreGlobKey,
            ["TestModeGlobal"] = testModeGlobKey,
            ["TargetDTAV"] = Own(TargetDtAvifId),
            ["TargetDRAV"] = Own(TargetDrAvifId),
            ["AimSwayPenaltyAV"] = Own(AimSwayAvifId),
            ["LimbCrippleMaskAV"] = Own(LimbMaskAvifId),
            ["PerceptionAV"] = perceptionAvKey,
            ["GunsSkillAV"] = gunsSkillAvKey,
            ["HeadCondAV"] = Sf(SfHeadCondId),
            ["TorsoCondAV"] = Sf(SfTorsoCondId),
            ["LeftArmCondAV"] = Sf(SfLeftArmCondId),
            ["RightArmCondAV"] = Sf(SfRightArmCondId),
            ["LeftLegCondAV"] = Sf(SfLeftLegCondId),
            ["RightLegCondAV"] = Sf(SfRightLegCondId),
            ["BrainCondAV"] = Sf(SfBrainCondId),
            ["SpeedMultAV"] = Sf(SfSpeedMultId),
            ["HealthAV"] = Sf(SfHealthId),
            ["DoctorsBag"] = Own(DoctorsBagAlchId),
            ["CombatStimpak"] = stimpakAlchKey,
            ["VatsSlowTimeAb"] = Own(VatsSlowTimeSpellId),
            ["VatsLimbPickerMsg"] = Own(VatsLimbMsgId),
            ["VatsTriggerToken"] = Own(VatsTokenMiscId),
            ["AmmoCycleToken"] = Own(AmmoTokenMiscId),
            ["ActionTokensList"] = Own(ActionTokensFlstId),
            ["CalibreBaseAmmoList"] = Own(CalibreBaseFlstId),
            ["SubtypeAPList"] = Own(SubtypeApFlstId),
            ["SubtypeJHPList"] = Own(SubtypeJhpFlstId),
            ["SubtypePlusPList"] = Own(SubtypePlusPFlstId),
            ["ReloadingRecipesList"] = Own(ReloadingRecipesFlstId),
            ["StarterRifle"] = weapRifle.FormKey,
            ["StarterShotgun"] = weapShotgun.FormKey,
            ["ZonePlateHeadRef"] = Own(ZoneHeadRefId),
            ["ZonePlateTorsoRef"] = Own(ZoneTorsoRefId),
            ["ZonePlateLeftArmRef"] = Own(ZoneLeftArmRefId),
            ["ZonePlateRightArmRef"] = Own(ZoneRightArmRefId),
            ["ZonePlateLeftLegRef"] = Own(ZoneLeftLegRefId),
            ["ZonePlateRightLegRef"] = Own(ZoneRightLegRefId),
            ["ArmoredTargetRef"] = Own(ArmoredTargetRefId),
            ["VatsTargetRef"] = Own(VatsTargetRefId),
            ["AmmoCyclePedestalRef"] = Own(AmmoPedestalRefId),
            ["LegTrapSwitchRef"] = Own(LegTrapSwitchRefId),
            ["HardcoreToggleSwitchRef"] = Own(HardcoreSwitchRefId),
            ["SupplyRackRef"] = Own(SupplyRackRefId),
        };

        var activeProps = opts.NoTestCell ? PropNames.Take(PropNames.Length - TestRefPropCount).ToArray() : PropNames;
        var se = new ScriptEntry { Name = "FO4SF_CombatQuest", Flags = ScriptEntry.Flag.Local };
        foreach (var pn in activeProps) se.Properties.Add(ObjProp(pn, propMap[pn]));

        quest.VirtualMachineAdapter = new QuestAdapter
        {
            Version = 6,
            ObjectFormat = 2,
            ExtraBindDataVersion = 3,
            Script = new ScriptEntry { Name = "", Flags = ScriptEntry.Flag.Local },
        };
        quest.VirtualMachineAdapter.Scripts.Add(se);
        mod.Quests.Add(quest);

        mod.ModHeader.Stats.NextFormID = nextRef;
        mod.ModHeader.MasterReferences.Clear();
        foreach (var mk in ExpectedMasters)
            mod.ModHeader.MasterReferences.Add(new MasterReference { Master = mk, FileSize = 0 });

        WriteMod(mod, outDir);
        string written = Path.Combine(outDir, Plugin.FileName);
        Console.WriteLine($"wrote {written} ({new FileInfo(written).Length:N0} bytes): " +
                          $"1 QUST ({activeProps.Length} props), 5 GLOB, 4 AVIF, 1 ALCH, 1 SPEL, 1 MESG, " +
                          $"15 AMMO, 6 FLST, 6 COBJ, 3 BPTD, {mod.Activators.Count} ACTI, {(opts.NoTestCell ? 0 : 1)} CELL");
        return 0;
    }

    public static int Check(string pluginPath, string sfPath, BuildOptions? opts = null)
    {
        opts ??= new BuildOptions(DefaultJsonPath(), false);
        var core = LoadCoreValues(opts.JsonPath);
        var perceptionAvKey = RequireCore(core, "FO4SF_Special_Perception");
        var gunsSkillAvKey = RequireCore(core, "FO4SF_Skill_Guns");
        var hardcoreGlobKey = RequireCore(core, "FO4SF_HardcoreEnabled");
        var stimpakAlchKey = RequireCore(core, "FO4SF_Stimpak");
        var testModeGlobKey = RequireCore(core, "FO4SF_TestModeEnabled");

        if (!File.Exists(pluginPath)) throw new Refusal("plugin missing: " + pluginPath);
        if (!File.Exists(sfPath)) throw new Refusal("Starfield.esm missing: " + sfPath);
        using var mod = OpenMod(pluginPath, Plugin);

        if (!mod.ModHeader.Flags.HasFlag(StarfieldModHeader.HeaderFlag.Master))
            throw new Refusal("header missing Master flag");
        var masters = mod.ModHeader.MasterReferences.Select(m => m.Master).ToList();
        if (!masters.SequenceEqual(ExpectedMasters))
            throw new Refusal($"masters must be [{string.Join(", ", ExpectedMasters)}], got [{string.Join(", ", masters)}]");

        foreach (var rec in mod.EnumerateMajorRecords())
        {
            if (rec.FormKey.ModKey != Plugin)
                throw new Refusal($"foreign override forbidden: {rec.FormKey}");
            if (rec.FormKey.ID < 0x800)
                throw new Refusal($"local FormID < 0x800 forbidden: {rec.FormKey}");
            if (!string.IsNullOrEmpty(rec.EditorID) && core.ContainsKey(rec.EditorID))
                throw new Refusal($"duplicate shared EditorID {rec.EditorID} in {Plugin}");
        }

        if (mod.Weapons.Count != 0)
            throw new Refusal($"zero per-weapon edits required, found {mod.Weapons.Count} WEAP records");
        if (mod.Quests.Count != 1 || mod.Quests.First().FormKey != Own(QuestId))
            throw new Refusal("expected QUST 0x800 FO4SF_CombatQuest");
        if (mod.MagicEffects.Count != 1 || mod.MagicEffects.First().FormKey != Own(DoctorsBagMgefId))
            throw new Refusal($"expected 1 MGEF (FO4SF_DoctorsBagEffect; stimpak is shared), got {mod.MagicEffects.Count}");
        if (mod.Ingestibles.Count != 1 || mod.Ingestibles.First().FormKey != Own(DoctorsBagAlchId))
            throw new Refusal($"expected 1 ALCH (FO4SF_DoctorsBag; stimpak is shared), got {mod.Ingestibles.Count}");

        if (mod.BodyParts.Count != 3)
            throw new Refusal($"expected 3 BPTD records (human/robot/creature), got {mod.BodyParts.Count}");
        foreach (var bptd in mod.BodyParts)
        {
            foreach (var p in bptd.Parts)
            {
                uint aid = p.ActorValue.FormKey.ID;
                if (!p.ActorValue.IsNull && (aid >= 0x38A && aid <= 0x38F || aid == 0x373))
                    throw new Refusal($"{bptd.EditorID} still contains unmigrated stale AVIF 0x{aid:X6}");
            }
        }
        if (mod.Ammunitions.Count != 15)
            throw new Refusal($"expected 15 subtype AMMO records (including .50 Cal JHP/+P), got {mod.Ammunitions.Count}");
        if (!mod.Ammunitions.Any(a => a.FormKey == Own(Ammo50CalJhpId) && a.EditorID == "FO4SF_Ammo50Cal_JHP") ||
            !mod.Ammunitions.Any(a => a.FormKey == Own(Ammo50CalPlusPId) && a.EditorID == "FO4SF_Ammo50Cal_PlusP"))
            throw new Refusal("missing 0x839 FO4SF_Ammo50Cal_JHP or 0x83A FO4SF_Ammo50Cal_PlusP");

        if (mod.FormLists.Count != 6)
            throw new Refusal($"expected 6 FLST records, got {mod.FormLists.Count}");
        var jhpFlst = mod.FormLists.FirstOrDefault(f => f.FormKey == Own(SubtypeJhpFlstId)) ?? throw new Refusal("missing FO4SF_SubtypeJHPList");
        var plusPFlst = mod.FormLists.FirstOrDefault(f => f.FormKey == Own(SubtypePlusPFlstId)) ?? throw new Refusal("missing FO4SF_SubtypePlusPList");
        if (jhpFlst.Items.Count != 5 || jhpFlst.Items[4].FormKey != Own(Ammo50CalJhpId))
            throw new Refusal("FO4SF_SubtypeJHPList slot 4 must be 0x839 FO4SF_Ammo50Cal_JHP");
        if (plusPFlst.Items.Count != 5 || plusPFlst.Items[4].FormKey != Own(Ammo50CalPlusPId))
            throw new Refusal("FO4SF_SubtypePlusPList slot 4 must be 0x83A FO4SF_Ammo50Cal_PlusP");

        var tokFlst = mod.FormLists.FirstOrDefault(f => f.FormKey == Own(ActionTokensFlstId)) ?? throw new Refusal("missing 0x837 FO4SF_CombatActionTokensList");
        if (!tokFlst.Items.Select(i => i.FormKey).SequenceEqual(new[] { Own(VatsTokenMiscId), Own(AmmoTokenMiscId) }))
            throw new Refusal("FO4SF_CombatActionTokensList must contain [0x816 FO4SF_VatsTriggerToken, 0x817 FO4SF_AmmoCycleToken]");

        if (mod.ConstructibleObjects.Count != 6)
            throw new Refusal($"expected 6 reloading-bench COBJ recipes, got {mod.ConstructibleObjects.Count}");
        if (mod.Spells.Count != 1)
            throw new Refusal($"expected 1 VATS slow-time SPEL, got {mod.Spells.Count}");
        if (mod.Spells.First().Effects.Any(e => e.Conditions.Count > 0))
            throw new Refusal("FO4SF_VatsSlowTimeAb must have unconditional SlowTime effect (0 conditions)");

        var q = mod.Quests.First();
        var script = q.VirtualMachineAdapter?.Scripts.FirstOrDefault() ?? throw new Refusal("missing FO4SF_CombatQuest VMAD script");
        var wantProps = opts.NoTestCell ? PropNames.Take(PropNames.Length - TestRefPropCount).ToArray() : PropNames;
        var gotProps = script.Properties.Select(p => p.Name).ToArray();
        if (!gotProps.SequenceEqual(wantProps))
            throw new Refusal($"quest properties [{string.Join(",", gotProps)}] != expected [{string.Join(",", wantProps)}]");

        FormKey PropObj(string name) =>
            (script.Properties.FirstOrDefault(p => p.Name == name) as IScriptObjectPropertyGetter)?.Object.FormKey ?? FormKey.Null;
        if (PropObj("CombatStimpak") != stimpakAlchKey) throw new Refusal($"CombatStimpak {PropObj("CombatStimpak")} != {stimpakAlchKey}");
        if (PropObj("PerceptionAV") != perceptionAvKey) throw new Refusal($"PerceptionAV {PropObj("PerceptionAV")} != {perceptionAvKey}");
        if (PropObj("GunsSkillAV") != gunsSkillAvKey) throw new Refusal($"GunsSkillAV {PropObj("GunsSkillAV")} != {gunsSkillAvKey}");
        if (PropObj("HardcoreGlobal") != hardcoreGlobKey) throw new Refusal($"HardcoreGlobal {PropObj("HardcoreGlobal")} != {hardcoreGlobKey}");
        if (PropObj("TestModeGlobal") != testModeGlobKey) throw new Refusal($"TestModeGlobal {PropObj("TestModeGlobal")} != {testModeGlobKey}");
        if (PropObj("ActionTokensList") != Own(ActionTokensFlstId)) throw new Refusal("ActionTokensList not bound to 0x837");

        var cells = mod.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells).ToList();
        if (opts.NoTestCell)
        {
            if (cells.Count != 0) throw new Refusal($"expected 0 CELL under --no-test-cell, got {cells.Count}");
            if (mod.Activators.Count != 0) throw new Refusal($"expected 0 test ACTI under --no-test-cell, got {mod.Activators.Count}");
        }
        else
        {
            if (cells.Count != 1 || cells[0].FormKey != Own(TestCellId))
                throw new Refusal("expected 1 interior CELL 0x850 FO4SF_CombatTestCell");
            if (mod.Activators.Count != 12)
                throw new Refusal($"expected 12 range ACTI records, got {mod.Activators.Count}");
        }

        Console.WriteLine($"FO4SFCombat.esm: header Master, masters [{string.Join(", ", ExpectedMasters)}], 0 WEAP edits, 0 foreign overrides, 3 repaired BPTDs, 15 AMMOs, 6 FLSTs, 6 COBJs, no_test_cell={opts.NoTestCell}; all checks pass");
        return 0;
    }

    public static int Fixture(string outDir)
    {
        Directory.CreateDirectory(outDir);
        var sf = new StarfieldMod(SfEsm, Release);
        sf.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;

        void AddAv(uint id, string edid) => sf.ActorValueInformation.Add(new ActorValueInformation(Sf(id), Release)
        {
            EditorID = edid, DefaultValue = 100f, FormVersion = 581,
        });
        AddAv(SfHeadCondId, "PerceptionCondition");
        AddAv(SfTorsoCondId, "EnduranceCondition");
        AddAv(SfLeftArmCondId, "LeftAttackCondition");
        AddAv(SfRightArmCondId, "RightAttackCondition");
        AddAv(SfLeftLegCondId, "LeftMobilityCondition");
        AddAv(SfRightLegCondId, "RightMobilityCondition");
        AddAv(SfBrainCondId, "BrainCondition");
        AddAv(SfHealthId, "Health");
        AddAv(SfSpeedMultId, "SpeedMult");

        void AddAmmo(uint id, string edid) => sf.Ammunitions.Add(new Ammunition(Sf(id), Release)
        {
            EditorID = edid, Name = edid, Value = 10, Weight = 0.01f, FormVersion = 581,
        });
        AddAmmo(SfAmmo777Id, "Ammo777mm");
        AddAmmo(SfAmmo11mmId, "Ammo11mm");
        AddAmmo(SfAmmoShotgunId, "AmmoShotgun");
        AddAmmo(SfAmmoLaserId, "AmmoLaser");
        AddAmmo(SfAmmo50CalId, "Ammo50Cal");

        sf.Weapons.Add(new Weapon(Sf(SfGrendelId), Release) { EditorID = "Grendel", Name = "Grendel", FormVersion = 581 });
        sf.Weapons.Add(new Weapon(Sf(SfBreachId), Release) { EditorID = "Breach", Name = "Breach", FormVersion = 581 });
        sf.Keywords.Add(new Keyword(Sf(SfIndustrialBenchKwId), Release) { EditorID = "WorkbenchIndustrialKeyword", FormVersion = 581 });
        sf.Activators.Add(new Mutagen.Bethesda.Starfield.Activator(Sf(SfTemplateActiId), Release) { EditorID = "ConsoleTpl", Name = "Console", FormVersion = 581 });
        sf.Statics.Add(new Static(Sf(SfFloorStatId), Release) { EditorID = "FloorTile", FormVersion = 581 });
        sf.Statics.Add(new Static(Sf(SfCocMarkerId), Release) { EditorID = "COCMarkerHeading", FormVersion = 581 });

        string[] resNames =
        {
            "ResInorgCommonLead", "ResInorgCommonIron", "ResInorgCommonCopper",
            "ResInorgUncommonTungsten", "ResOrgExoticLubricant", "ResInorgCommonUranium",
        };
        uint rid = 0x050000;
        foreach (var rn in resNames)
            sf.Resources.Add(new Resource(Sf(rid++), Release) { EditorID = rn, FormVersion = 581 });

        var slowMgef = new MagicEffect(Sf(SfSlowTimeMgefId), Release) { EditorID = "SlowTimeChem", FormVersion = 581 };
        sf.MagicEffects.Add(slowMgef);
        var slowSpell = new Spell(Sf(SfSlowTimeSpellId), Release) { EditorID = "abBoostAssaultSlowTime", Type = Spell.SpellType.Ability, FormVersion = 581 };
        var eff = new Effect { BaseEffect = new FormLinkNullable<IMagicEffectGetter>(slowMgef.FormKey), Data = new EffectData { Magnitude = 0.3f } };
        eff.Conditions.Add(new ConditionFloat { ComparisonValue = 1f, Data = new IsBoostPackHoveringConditionData() });
        slowSpell.Effects.Add(eff);
        sf.Spells.Add(slowSpell);

        // Synthetic HumanBodyPartData with unmigrated stale 0x00038A..0x00038F links to verify BPTD repair
        var hb = new BodyPartData(Sf(SfHumanBptdId), Release) { EditorID = "HumanBodyPartData", FormVersion = 581 };
        hb.Parts.Add(new BodyPart { Name = "Head", PartNode = "C_Head", DamageMult = 2f, ActorValue = new FormLink<IActorValueInformationGetter>(Sf(0x00038A)) });
        hb.Parts.Add(new BodyPart { Name = "Torso", PartNode = "C_Spine", DamageMult = 1f, ActorValue = new FormLink<IActorValueInformationGetter>(Sf(0x00038F)) });
        hb.Parts.Add(new BodyPart { Name = "LeftArm", PartNode = "L_Biceps", DamageMult = 1f, ActorValue = new FormLink<IActorValueInformationGetter>(Sf(0x00038B)) });
        hb.Parts.Add(new BodyPart { Name = "RightArm", PartNode = "R_Biceps", DamageMult = 1f, ActorValue = new FormLink<IActorValueInformationGetter>(Sf(0x00038C)) });
        hb.Parts.Add(new BodyPart { Name = "LeftLeg", PartNode = "L_Thigh", DamageMult = 1f, ActorValue = new FormLink<IActorValueInformationGetter>(Sf(0x00038D)) });
        hb.Parts.Add(new BodyPart { Name = "RightLeg", PartNode = "R_Thigh", DamageMult = 1f, ActorValue = new FormLink<IActorValueInformationGetter>(Sf(0x00038E)) });
        hb.Parts.Add(new BodyPart { Name = "LeftFoot", PartNode = "L_Foot", DamageMult = 1f, ActorValue = new FormLink<IActorValueInformationGetter>(Sf(0x00038D)) });
        hb.Parts.Add(new BodyPart { Name = "RightFoot", PartNode = "R_Foot", DamageMult = 1f, ActorValue = new FormLink<IActorValueInformationGetter>(Sf(0x00038E)) });
        hb.Parts.Add(new BodyPart { Name = "Boostpack", PartNode = "C_BackPack", DamageMult = 1f, ActorValue = new FormLink<IActorValueInformationGetter>(Sf(0x000373)) });
        sf.BodyParts.Add(hb);

        string sfPath = Path.Combine(outDir, "Starfield.esm");
        sf.BeginWrite.ToPath(sfPath).WithNoLoadOrder().NoCheckIfLowerRangeDisallowed().Write();
        return 0;
    }

    public static int SelfTest(string scratchDir)
    {
        if (Directory.Exists(scratchDir)) Directory.Delete(scratchDir, true);
        Directory.CreateDirectory(scratchDir);
        string fixDir = Path.Combine(scratchDir, "fixture");
        string outDir = Path.Combine(scratchDir, "out");
        string outDir2 = Path.Combine(scratchDir, "out2");
        string outPlayer = Path.Combine(scratchDir, "out_player");
        Fixture(fixDir);
        string sfPath = Path.Combine(fixDir, "Starfield.esm");
        string jsonPath = DefaultJsonPath();

        var defOpts = new BuildOptions(jsonPath, NoTestCell: false);
        Build(sfPath, outDir, defOpts);
        Build(sfPath, outDir2, defOpts);
        string esm = Path.Combine(outDir, Plugin.FileName);
        if (!File.ReadAllBytes(esm).SequenceEqual(File.ReadAllBytes(Path.Combine(outDir2, Plugin.FileName))))
            throw new Refusal("default FO4SFCombat.esm build is not byte-identical");
        Check(esm, sfPath, defOpts);

        var playerOpts = new BuildOptions(jsonPath, NoTestCell: true);
        Build(sfPath, outPlayer, playerOpts);
        string playerEsm = Path.Combine(outPlayer, Plugin.FileName);
        Check(playerEsm, sfPath, playerOpts);

        bool rejected = false;
        try { Check(esm, sfPath, playerOpts); }
        catch (Refusal) { rejected = true; }
        if (!rejected) throw new Refusal("Check --no-test-cell failed to reject plugin containing test cell");

        rejected = false;
        try { Check(playerEsm, sfPath, defOpts); }
        catch (Refusal) { rejected = true; }
        if (!rejected) throw new Refusal("default Check failed to reject plugin missing test cell");

        string badPath = Path.Combine(scratchDir, "bad.esm");
        var raw = File.ReadAllBytes(esm);
        raw[8] &= 0xFE;
        File.WriteAllBytes(badPath, raw);
        bool caught = false;
        try { Check(badPath, sfPath, defOpts); }
        catch (Refusal) { caught = true; }
        if (!caught) throw new Refusal("selftest failed: missing Master flag was not refused");

        Console.WriteLine("selftest: ok");
        return 0;
    }
}
