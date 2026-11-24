// WorkshopCore: Core Settlements, Junk Scrapping (CMPO -> IRES), FO4 COBJ + FNV RCPE Bench Recipes, and Portable C.A.M.P.s
// (docs/workshop/workshop-camps.md)
//
// FO4SFWorkshop.esm (masters Starfield.esm, FO4SFCoreValues.esm; adds 41 own records + 4 localized LCTN/STDT overrides for D4/E6; 0 FLST/PNDT overrides).
// The terrain core is NOT a master: FO4SF_WorkshopCoreQuest resolves FO4TerrainCore.esm / FO4TerrainCore_Mars.esm
// workshop bases at runtime via Game.GetFormFromFile so FO4SFWorkshop.esm loads standalone or folded without cell overrides.
//
// usage:
//   WorkshopCore build <Starfield.esm> <out dir> [--exclusion-radius <float>] [--json <core_values.json>]
//   WorkshopCore check <plugin> <Starfield.esm> [--exclusion-radius <float>] [--json <core_values.json>]
//   WorkshopCore fixture <out dir> [--mode full|minimal]
//   WorkshopCore selftest <scratch dir>

using System.Globalization;
using System.Text.Json;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Mutagen.Bethesda.Strings;
using Noggog;

try
{
    var rest = args.ToList();
    string? Opt(string name)
    {
        int i = rest.IndexOf(name);
        if (i < 0) return null;
        if (i + 1 >= rest.Count) throw new WorkshopCore.Refusal(name + " needs a value");
        var v = rest[i + 1];
        rest.RemoveRange(i, 2);
        return v;
    }

    var exclRaw = Opt("--exclusion-radius");
    float exclRadius = 45.0f;
    if (exclRaw != null)
    {
        if (!float.TryParse(exclRaw, NumberStyles.Float, CultureInfo.InvariantCulture, out exclRadius) || exclRadius < 0.0f || exclRadius > 500.0f)
            throw new WorkshopCore.Refusal($"--exclusion-radius must be in [0, 500], got {exclRaw}");
    }
    var mode = Opt("--mode") ?? "full";
    var jsonPath = Opt("--json");

    if (rest.Count == 3 && rest[0] == "build") return WorkshopCore.Build(rest[1], rest[2], exclRadius, jsonPath);
    if (rest.Count == 3 && rest[0] == "check") return WorkshopCore.Check(rest[1], rest[2], exclRadius, jsonPath);
    if (rest.Count == 2 && rest[0] == "fixture") return WorkshopCore.Fixture(rest[1], mode);
    if (rest.Count == 2 && rest[0] == "selftest") return WorkshopCore.SelfTest(rest[1]);
}
catch (WorkshopCore.Refusal r)
{
    Console.Error.WriteLine("refused: " + r.Message);
    return 1;
}

Console.Error.WriteLine("usage: WorkshopCore build <Starfield.esm> <out dir> [--exclusion-radius <float>] [--json <core_values.json>] | " +
                        "check <plugin> <Starfield.esm> [--exclusion-radius <float>] [--json <core_values.json>] | " +
                        "fixture <out dir> [--mode full|minimal] | selftest <scratch dir>");
return 2;

static class WorkshopCore
{
    public class Refusal(string m) : Exception(m);

    const StarfieldRelease Release = StarfieldRelease.Starfield;
    static readonly ModKey SfEsm = ModKey.FromFileName("Starfield.esm");
    static readonly ModKey CoreValuesEsm = ModKey.FromFileName("FO4SFCoreValues.esm");
    public static readonly ModKey Plugin = ModKey.FromFileName("FO4SFWorkshop.esm");

    // Locked local FormIDs shared with scripts/workshop/FO4SF_WorkshopCoreQuest.psc and tests/test_workshop_core.py
    public const uint QuestId = 0x800;
    public const uint CampExclusionRadiusGlobId = 0x801;
    public const uint ActiveCampCountGlobId = 0x802;
    public const uint TrackedWorkshopCountGlobId = 0x803;
    public const uint TrackedStationCountGlobId = 0x804;

    public const uint CampKitId = 0x810;
    public const uint CampPackTokenId = 0x811;
    public const uint SettlementKitId = 0x812;

    public const uint CmpoIresListId = 0x818;
    public const uint CmpoMiscListId = 0x819;
    public const uint ScrapJunkListId = 0x81A;
    public const uint ScrapTokenId = 0x81B;
    public const uint BenchRecipesListId = 0x81C;
    public const uint KitFilterListId = 0x81D;

    public const uint JunkDeskFanId = 0x820;
    public const uint JunkDuctTapeId = 0x821;
    public const uint JunkHotPlateId = 0x822;
    public const uint JunkTinCanId = 0x823;

    public const uint CraftFieldMedkitId = 0x830;
    public const uint CraftWeaponPartsKitId = 0x831;
    public const uint CraftSensorModuleId = 0x832;
    public const uint CraftSurgicalBagId = 0x833;
    public const uint CraftCombatBlendId = 0x834;
    public const uint CraftTrailRationId = 0x835;

    public const uint CobjFo4FieldMedkitId = 0x840;
    public const uint CobjFo4WeaponPartsKitId = 0x841;
    public const uint CobjFo4SensorModuleId = 0x842;
    public const uint CobjFo4PortableCampKitId = 0x843;
    public const uint RcpeNvSurgicalBagId = 0x844;
    public const uint RcpeNvCombatBlendId = 0x845;
    public const uint RcpeNvHandLoad777Id = 0x846;
    public const uint RcpeNvTrailRationId = 0x847;

    // R11 D4 / E6: Clean Sanctuary Hills Workshop bench (zero Starfield OutpostCategory* keywords),
    // runtime swap switch GLOB 0x84A (default 0.0 = OFF in candidate-2g-fix2), and 3 clean Sanctuary
    // placeables + zero-skill Outpost COBJs (0x84B..0x850).
    public const uint SanctuaryCategoryKwId = 0x848;
    public const uint SanctuaryBenchActiId = 0x849;
    public const uint SanctuaryCleanBenchSwapGlobId = 0x84A;
    public const uint SanctuaryChairFurnId = 0x84B;
    public const uint SanctuaryCotFurnId = 0x84C;
    public const uint SanctuaryCrateContId = 0x84D;
    public const uint SanctuaryChairCobjId = 0x84E;
    public const uint SanctuaryCotCobjId = 0x84F;
    public const uint SanctuaryCrateCobjId = 0x850;
    public const string SanctuaryCategoryKwEdid = "FO4SF_WorkshopCategorySanctuary";
    public const string SanctuaryBenchActiEdid = "FO4SF_SanctuaryWorkshopBench";
    public const string SanctuaryCleanBenchSwapGlobEdid = "FO4SF_SanctuaryCleanBenchSwap";
    public const string SanctuaryChairFurnEdid = "FO4SF_Sanctuary_WoodChair";
    public const string SanctuaryCotFurnEdid = "FO4SF_Sanctuary_SleepingCot";
    public const string SanctuaryCrateContEdid = "FO4SF_Sanctuary_StorageCrate";
    public const string SanctuaryChairCobjEdid = "FO4SF_COBJ_Sanctuary_WoodChair";
    public const string SanctuaryCotCobjEdid = "FO4SF_COBJ_Sanctuary_SleepingCot";
    public const string SanctuaryCrateCobjEdid = "FO4SF_COBJ_Sanctuary_StorageCrate";
    public const string SanctuaryBenchName = "Sanctuary Hills Workshop";
    public const string SanctuaryBenchModel = "fo4core\\setdressing\\garage\\workbenchgarage01.nif";
    public const float SanctuaryBenchRadius = 250.0f;

    // R11 F3 / E6 / F4: Scoped Sanctuary category ONLY on clean bench 0x000849 (0 Starfield Outpost FLST overrides),
    // localized D4 Mars/Sol LCTN + STDT overrides (Commonwealth / Massachusetts, HeaderFlag.Localized + Data/Strings/*),
    // and 3 Starfield furniture/container stand-in placeables (0x84B..0x84D) with zero-skill COBJs (0x84E..0x850).
    public const uint SfLocMarsSurfaceId = 0x01B736;
    public const uint SfLocMarsPlanetId = 0x01B735;
    public const uint SfLocSolSystemId = 0x061527;
    public const uint SfStarSolId = 0x05E5CB;
    public const uint SfFurnWoodChairTplId = 0x12A77F;
    public const uint SfFurnScrapCotTplId = 0x1FEDFD;
    public const uint SfContStorageCrateTplId = 0x0A47D5;
    public const uint SfCobjOutpostDecorTplId = 0x03962D;
    public const uint SfMustPersistKwId = 0x04AF68;
    public const uint SfWorkshopKwId = 0x054BA7;
    public const uint SfOutpostBuildAreaRadiusAvId = 0x063FC5;
    public const string CommonwealthLocName = "Commonwealth";
    public const string MassachusettsStarName = "Massachusetts";
    public const string SanctuaryChairName = "Wooden Chair (Stand-In)";
    public const string SanctuaryCotName = "Sleeping Cot (Stand-In)";
    public const string SanctuaryCrateName = "Storage Crate (Stand-In)";

    static readonly uint[] ForbiddenStarfieldOutpostCategoryIds =
    {
        0x002CFDE6, // OutpostCategoryCrafting (Industrial/Spacesuit/Weapon/Chem/Food/Research)
        0x002BE3B5, // OutpostCategoryFurniture
        0x00293ADF, // OutpostCategoryDecorations
        0x0002BD59, // OutpostCategoryTestAssets
        0x00397027, // OutpostCategoryDisplays
        0x0028F890, // OutpostCategoryPower_InteriorLights
        0x000E6A3E, // OutpostCategoryMiscInterior
    };

    public const uint NextId = 0x858;
    public const int ExpectedOwnRecordCount = 41;
    public const int ExpectedOverrideRecordCount = 4;
    public const int ExpectedMajorRecordCount = ExpectedOwnRecordCount + ExpectedOverrideRecordCount;

    const string QuestEdid = "FO4SF_WorkshopCoreQuest";
    const string QuestScript = "FO4SF_WorkshopCoreQuest";
    static readonly ushort[] Stages = { 5, 10, 15, 20, 30, 40, 50, 60 };

    // 18 Fallout 4 CMPO scrap component archetypes in locked index order [0..17]
    public record CmpoSpec(int Index, string Archetype, string[] IresPrefs, string[] MiscPrefs);

    public static readonly CmpoSpec[] CmpoSpecs =
    {
        new(0,  "Steel",           new[] { "ResInorgCommonIron" },             new[] { "InorgCommonIron", "Ore_Iron" }),
        new(1,  "Wood",            new[] { "ResOrgCommonStructural" },         new[] { "OrgCommonStructural" }),
        new(2,  "Aluminum",        new[] { "ResInorgCommonAluminum" },         new[] { "InorgCommonAluminum", "Ore_Aluminum" }),
        new(3,  "Adhesive",        new[] { "ResOrgRareAdhesive" },             new[] { "OrgRareAdhesive" }),
        new(4,  "Screws",          new[] { "ResInorgUncommonTungsten" },       new[] { "InorgUncommonTungsten" }),
        new(5,  "Copper",          new[] { "ResInorgCommonCopper" },           new[] { "InorgCommonCopper" }),
        new(6,  "Circuitry",       new[] { "ResMfg_Tier01_ZeroWire" },         new[] { "Mfg_Tier01_ZeroWire" }),
        new(7,  "NuclearMaterial", new[] { "ResInorgCommonUranium" },          new[] { "InorgCommonUranium" }),
        new(8,  "Lead",            new[] { "ResInorgCommonLead" },             new[] { "InorgCommonLead" }),
        new(9,  "Gears",           new[] { "ResMfg_Tier01_AdaptiveFrame" },    new[] { "Mfg_Tier01_AdaptiveFrame" }),
        new(10, "Springs",         new[] { "ResInorgRareTitanium" },           new[] { "InorgRareTitanium" }),
        new(11, "Oil",             new[] { "ResOrgExoticLubricant" },          new[] { "OrgExoticLubricant" }),
        new(12, "Cloth",           new[] { "ResOrgCommonFiber" },              new[] { "OrgCommonFiber" }),
        new(13, "Glass",           new[] { "ResOrgUncommonCosmetic" },         new[] { "OrgUncommonCosmetic" }),
        new(14, "Plastic",         new[] { "ResOrgExoticPolymer" },            new[] { "OrgExoticPolymer" }),
        new(15, "Rubber",          new[] { "ResOrgCommonSealant" },            new[] { "OrgCommonSealant" }),
        new(16, "Ceramic",         new[] { "ResInorgUncommonChlorosilanes_L" },new[] { "InorgUncommonChlorosilanes" }),
        new(17, "Antiseptic",      new[] { "ResOrgUncommonAntimicrobial" },    new[] { "OrgUncommonAntimicrobial" }),
    };

    // 4 clean-room FO4 scrap junk MISC items with deterministic CMPO component yields
    public record JunkSpec(uint Id, string Edid, string Name, float Weight, int Value, string[] TemplatePrefs, (int CmpoIndex, uint Count)[] Yields);

    public static readonly JunkSpec[] JunkSpecs =
    {
        new(JunkDeskFanId,  "FO4SF_Junk_DeskFan",  "Salvage Desk Fan",      1.5f, 18,
            new[] { "Deskfan03", "Exotic_DeskFan01", "Misc_Junk_Fork" },
            new[] { (0, 2u), (9, 2u), (4, 2u) }),
        new(JunkDuctTapeId, "FO4SF_Junk_DuctTape", "Salvage Adhesive Roll", 0.4f, 14,
            new[] { "Tool_DuctTape01", "Misc_Junk_Fork" },
            new[] { (3, 2u), (12, 1u) }),
        new(JunkHotPlateId, "FO4SF_Junk_HotPlate", "Salvage Heating Plate", 1.2f, 16,
            new[] { "Kitchenware_Plate01", "Misc_Junk_Fork" },
            new[] { (5, 2u), (6, 1u), (4, 1u) }),
        new(JunkTinCanId,   "FO4SF_Junk_TinCan",   "Salvage Metal Can",     0.2f,  6,
            new[] { "OE_KT_HiveMine_Canister_Poison", "CoffeeMug01", "Misc_Junk_Fork" },
            new[] { (0, 2u), (2, 2u) }),
    };

    public enum BenchKind { Industrial, Chemlab, Cooking }

    // 8 clean-room FO4 COBJ + FNV RCPE bench recipes
    public record RecipeSpec(
        uint Id,
        string Edid,
        string Description,
        BenchKind Bench,
        uint CreatedOwnId,     // 0 means external Starfield.esm Ammo777mm
        ushort AmountProduced,
        float SortOrder,
        (int CmpoIndex, uint Count)[] Costs);

    public static readonly RecipeSpec[] RecipeSpecs =
    {
        // FO4 COBJ recipes (4)
        new(CobjFo4FieldMedkitId,     "FO4SF_COBJ_FO4_FieldMedkit",     "Assemble field trauma dressing from salvaged medical supplies.",
            BenchKind.Chemlab,    CraftFieldMedkitId,    1, 10.0f, new[] { (17, 2u), (0, 1u), (12, 1u) }),
        new(CobjFo4WeaponPartsKitId,  "FO4SF_COBJ_FO4_WeaponPartsKit",  "Machine modular receiver components from salvaged alloy and fasteners.",
            BenchKind.Industrial, CraftWeaponPartsKitId, 1, 11.0f, new[] { (0, 3u), (3, 2u), (4, 2u), (2, 2u) }),
        new(CobjFo4SensorModuleId,    "FO4SF_COBJ_FO4_SensorModule",    "Wire a compact sensor array for settlement turrets and beacons.",
            BenchKind.Industrial, CraftSensorModuleId,   1, 12.0f, new[] { (5, 2u), (6, 2u), (13, 1u) }),
        new(CobjFo4PortableCampKitId, "FO4SF_COBJ_FO4_PortableCAMPKit", "Fabricate a portable field deployment kit for remote C.A.M.P. sites.",
            BenchKind.Industrial, CampKitId,             1, 13.0f, new[] { (0, 4u), (2, 3u), (9, 2u), (6, 1u) }),

        // FNV RCPE bench / reloading / campfire recipes (4)
        new(RcpeNvSurgicalBagId,      "FO4SF_RCPE_NV_SurgicalBag",      "Prepare a frontier surgical kit for limb and trauma recovery.",
            BenchKind.Chemlab,    CraftSurgicalBagId,    1, 20.0f, new[] { (17, 2u), (12, 2u), (15, 1u) }),
        new(RcpeNvCombatBlendId,      "FO4SF_RCPE_NV_CombatBlend",      "Compound a frontier combat stimulant blend.",
            BenchKind.Chemlab,    CraftCombatBlendId,    1, 21.0f, new[] { (17, 2u), (14, 1u), (8, 1u) }),
        new(RcpeNvHandLoad777Id,      "FO4SF_RCPE_NV_HandLoad777",      "Reload caseless small-arms rounds from salvaged lead, copper, and oil.",
            BenchKind.Industrial, 0u,                   12, 22.0f, new[] { (8, 2u), (5, 2u), (11, 1u) }),
        new(RcpeNvTrailRationId,      "FO4SF_RCPE_NV_TrailRation",      "Cook shelf-stable caravan trail rations at a cooking station.",
            BenchKind.Cooking,    CraftTrailRationId,    1, 23.0f, new[] { (1, 1u), (17, 1u), (16, 1u) }),
    };

    const string TestModeEdid = "FO4SF_TestModeEnabled";

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

    static string? ResolveStringsFolder(string pluginPath)
    {
        var dir = Path.GetDirectoryName(Path.GetFullPath(pluginPath)) ?? ".";
        var staged = Path.Combine(dir, "Data", "Strings");
        if (Directory.Exists(staged)) return staged;
        var installed = Path.Combine(dir, "Strings");
        if (Directory.Exists(installed)) return installed;
        return null;
    }

    static IStarfieldModDisposableGetter OpenPlugin(string path)
    {
        var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        styles.Set(new KeyedMasterStyle(SfEsm, MasterStyle.Full));
        styles.Set(new KeyedMasterStyle(CoreValuesEsm, MasterStyle.Full));
        var stringsDir = ResolveStringsFolder(path);
        var rp = new BinaryReadParameters
        {
            MasterFlagsLookup = styles,
            StringsParam = stringsDir != null ? new StringsReadParameters { StringsFolderOverride = stringsDir } : null,
        };
        return StarfieldMod.CreateFromBinaryOverlay(path, Release, rp);
    }

    sealed class ResolvedTemplates
    {
        public required (FormKey Ires, string IresEdid, FormKey Misc, string MiscEdid)[] CmpoPairs { get; init; }
        public required FormKey BenchIndustrialKw { get; init; }
        public required FormKey BenchChemlabKw { get; init; }
        public required FormKey BenchCookingKw { get; init; }
        public FormKey? FilterIndustrialKw { get; init; }
        public FormKey? FilterChemlabKw { get; init; }
        public FormKey? FilterCookingKw { get; init; }
        public required FormKey AmmoProduct { get; init; }
        public required IMiscItemGetter DefaultMiscTemplate { get; init; }
        public required IIngestibleGetter AidTemplate { get; init; }
        public required IIngestibleGetter FoodTemplate { get; init; }
        public IConstructibleObjectGetter? CobjTemplate { get; init; }
        public IConstructibleObjectGetter? OutpostCobjTemplate { get; init; }
        public required IFurnitureGetter SanctuaryChairTemplate { get; init; }
        public required IFurnitureGetter SanctuaryCotTemplate { get; init; }
        public required IContainerGetter SanctuaryCrateTemplate { get; init; }
        public required string Summary { get; init; }
    }

    static IMiscItemGetter PickMiscTemplate(IStarfieldModGetter sf, IEnumerable<string> prefs, IMiscItemGetter fallback)
    {
        var all = sf.MiscItems.ToList();
        foreach (var p in prefs)
        {
            var hit = all.FirstOrDefault(m => m.Model != null && string.Equals(m.EditorID, p, StringComparison.OrdinalIgnoreCase));
            if (hit != null) return hit;
        }
        return fallback;
    }

    static ResolvedTemplates ResolveTemplates(IStarfieldModGetter sf)
    {
        var allMisc = sf.MiscItems.ToList();
        var defaultMisc = allMisc
            .Where(m => m.Model != null && !string.IsNullOrEmpty(m.EditorID))
            .OrderBy(m => string.Equals(m.EditorID, "Kitchenware_Fork01", StringComparison.OrdinalIgnoreCase) ? 0 :
                          string.Equals(m.EditorID, "Misc_Junk_Fork", StringComparison.OrdinalIgnoreCase) ? 1 : 2)
            .ThenBy(m => m.FormKey.ID)
            .FirstOrDefault()
            ?? throw new Refusal("no MISC with a 3D model found in Starfield.esm");

        var allRes = sf.Resources.OrderBy(r => r.FormKey.ID).ToList();
        if (allRes.Count == 0)
            throw new Refusal("no Resource (IRES) records found in Starfield.esm");

        // Map IRES -> MISC via MiscItem.Resources links (as Starfield.esm links InorgCommonIron -> ResInorgCommonIron)
        var resToMisc = new Dictionary<FormKey, List<IMiscItemGetter>>();
        foreach (var m in allMisc)
        {
            if (m.Resources == null) continue;
            foreach (var ir in m.Resources)
            {
                if (!resToMisc.TryGetValue(ir.Resource.FormKey, out var lst)) resToMisc[ir.Resource.FormKey] = lst = new();
                lst.Add(m);
            }
        }

        var pairs = new (FormKey Ires, string IresEdid, FormKey Misc, string MiscEdid)[CmpoSpecs.Length];
        int exactCount = 0;
        for (int i = 0; i < CmpoSpecs.Length; i++)
        {
            var spec = CmpoSpecs[i];
            IResourceGetter? resHit = null;
            foreach (var pref in spec.IresPrefs)
            {
                resHit = allRes.FirstOrDefault(r => string.Equals(r.EditorID, pref, StringComparison.OrdinalIgnoreCase));
                if (resHit != null) { exactCount++; break; }
            }
            resHit ??= allRes[i % allRes.Count];

            IMiscItemGetter? miscHit = null;
            foreach (var mpref in spec.MiscPrefs)
            {
                miscHit = allMisc.FirstOrDefault(m => string.Equals(m.EditorID, mpref, StringComparison.OrdinalIgnoreCase));
                if (miscHit != null) break;
            }
            if (miscHit == null && resToMisc.TryGetValue(resHit.FormKey, out var linked) && linked.Count > 0)
            {
                miscHit = linked
                    .OrderBy(m => (m.EditorID ?? "").Contains("NOCLUTTER", StringComparison.OrdinalIgnoreCase) ? 1 : 0)
                    .ThenBy(m => m.FormKey.ID)
                    .First();
            }
            miscHit ??= allMisc[i % allMisc.Count];

            pairs[i] = (resHit.FormKey, resHit.EditorID ?? $"0x{resHit.FormKey.ID:X6}", miscHit.FormKey, miscHit.EditorID ?? $"0x{miscHit.FormKey.ID:X6}");
        }

        var allKws = sf.Keywords.OrderBy(k => k.FormKey.ID).ToList();
        FormKey FindKw(string[] prefs, uint knownId)
        {
            foreach (var p in prefs)
            {
                var k = allKws.FirstOrDefault(x => string.Equals(x.EditorID, p, StringComparison.OrdinalIgnoreCase));
                if (k != null) return k.FormKey;
            }
            var byId = allKws.FirstOrDefault(x => x.FormKey.ID == knownId);
            if (byId != null) return byId.FormKey;
            return allKws.FirstOrDefault()?.FormKey ?? throw new Refusal("no Keyword records in Starfield.esm");
        }

        FormKey? FindOptKw(string edid, uint knownId)
        {
            var k = allKws.FirstOrDefault(x => string.Equals(x.EditorID, edid, StringComparison.OrdinalIgnoreCase))
                    ?? allKws.FirstOrDefault(x => x.FormKey.ID == knownId);
            return k?.FormKey;
        }

        var indKw = FindKw(new[] { "WorkbenchIndustrialKeyword" }, 0x0AA209);
        var chemKw = FindKw(new[] { "WorkbenchChemlabRecipeKeyword", "WorkbenchChemlabKeywordNEW" }, 0x102158);
        var cookKw = FindKw(new[] { "WorkbenchCookingKeyword" }, 0x102152);

        var allAlch = sf.Ingestibles.Where(a => a.Model != null && !string.IsNullOrEmpty(a.EditorID)).OrderBy(a => a.FormKey.ID).ToList();
        if (allAlch.Count == 0) allAlch = sf.Ingestibles.OrderBy(a => a.FormKey.ID).ToList();
        if (allAlch.Count == 0) throw new Refusal("no Ingestible (ALCH) template found in Starfield.esm");

        var aidTpl = allAlch.FirstOrDefault(a => string.Equals(a.EditorID, "Aid_MedPack", StringComparison.OrdinalIgnoreCase))
                     ?? allAlch.FirstOrDefault(a => string.Equals(a.EditorID, "ShipRepairKit", StringComparison.OrdinalIgnoreCase))
                     ?? allAlch[0];
        var foodTpl = allAlch.FirstOrDefault(a => string.Equals(a.EditorID, "Food_Craft_GalaxyMein", StringComparison.OrdinalIgnoreCase))
                      ?? allAlch[allAlch.Count - 1];

        var ammoHit = sf.Ammunitions.FirstOrDefault(a => string.Equals(a.EditorID, "Ammo777mm", StringComparison.OrdinalIgnoreCase))
                      ?? sf.Ammunitions.OrderBy(a => a.FormKey.ID).FirstOrDefault();
        FormKey ammoKey = ammoHit?.FormKey ?? pairs[8].Misc; // fallback to Lead MISC in minimal synthetic fixtures without AMMO

        var cobjTpl = sf.ConstructibleObjects.FirstOrDefault(c => string.Equals(c.EditorID, "co_mfg_Tier01_AdaptiveFrame", StringComparison.OrdinalIgnoreCase))
                      ?? sf.ConstructibleObjects.OrderBy(c => c.FormKey.ID).FirstOrDefault();
        var outpostCobjTpl = sf.ConstructibleObjects.FirstOrDefault(c => c.FormKey == Sf(SfCobjOutpostDecorTplId))
                             ?? sf.ConstructibleObjects.FirstOrDefault(c => string.Equals(c.EditorID, "co_Outpost_Decor_PortableStoveTop01", StringComparison.OrdinalIgnoreCase))
                             ?? cobjTpl;

        var allFurn = sf.Furniture.Where(f => f.Model != null && !string.IsNullOrEmpty(f.EditorID)).OrderBy(f => f.FormKey.ID).ToList();
        if (allFurn.Count == 0) allFurn = sf.Furniture.OrderBy(f => f.FormKey.ID).ToList();
        if (allFurn.Count == 0) throw new Refusal("no Furniture (FURN) template found in Starfield.esm");
        var chairTpl = allFurn.FirstOrDefault(f => f.FormKey == Sf(SfFurnWoodChairTplId))
                       ?? allFurn.FirstOrDefault(f => string.Equals(f.EditorID, "AK_Chair_Wood_01_Free", StringComparison.OrdinalIgnoreCase))
                       ?? allFurn[0];
        var cotTpl = allFurn.FirstOrDefault(f => f.FormKey == Sf(SfFurnScrapCotTplId))
                     ?? allFurn.FirstOrDefault(f => string.Equals(f.EditorID, "FoundScrapCot01", StringComparison.OrdinalIgnoreCase))
                     ?? allFurn.FirstOrDefault(f => string.Equals(f.EditorID, "FoundCanvasCot01", StringComparison.OrdinalIgnoreCase))
                     ?? allFurn[allFurn.Count - 1];

        var allCont = sf.Containers.Where(c => c.Model != null && !string.IsNullOrEmpty(c.EditorID)).OrderBy(c => c.FormKey.ID).ToList();
        if (allCont.Count == 0) allCont = sf.Containers.OrderBy(c => c.FormKey.ID).ToList();
        if (allCont.Count == 0) throw new Refusal("no Container (CONT) template found in Starfield.esm");
        var crateTpl = allCont.FirstOrDefault(c => c.FormKey == Sf(SfContStorageCrateTplId))
                       ?? allCont.FirstOrDefault(c => string.Equals(c.EditorID, "Loot_Storage_Miscbox05_Common_Empty", StringComparison.OrdinalIgnoreCase))
                       ?? allCont[0];

        var summary = $"CMPO exact={exactCount}/{CmpoSpecs.Length}, Steel={pairs[0].IresEdid}->{pairs[0].MiscEdid}, " +
                      $"Aluminum={pairs[2].IresEdid}->{pairs[2].MiscEdid}, Adhesive={pairs[3].IresEdid}->{pairs[3].MiscEdid}, " +
                      $"BenchKWs=[Ind={indKw.ID:X6}, Chem={chemKw.ID:X6}, Cook={cookKw.ID:X6}], Ammo={ammoKey.ID:X6}";

        return new ResolvedTemplates
        {
            CmpoPairs = pairs,
            BenchIndustrialKw = indKw,
            BenchChemlabKw = chemKw,
            BenchCookingKw = cookKw,
            FilterIndustrialKw = FindOptKw("RecipeManufactured", 0x2E2F2D),
            FilterChemlabKw = FindOptKw("RecipeChem", 0x10215A),
            FilterCookingKw = FindOptKw("RecipeFood", 0x2C6660),
            AmmoProduct = ammoKey,
            DefaultMiscTemplate = defaultMisc,
            AidTemplate = aidTpl,
            FoodTemplate = foodTpl,
            CobjTemplate = cobjTpl,
            OutpostCobjTemplate = outpostCobjTpl,
            SanctuaryChairTemplate = chairTpl,
            SanctuaryCotTemplate = cotTpl,
            SanctuaryCrateTemplate = crateTpl,
            Summary = summary,
        };
    }

    // ---------------------------------------------------------------- build

    static Global MakeGlobal(uint id, string edid, float value) =>
        new Global(Own(id), Release)
        {
            EditorID = edid,
            FormVersion = 581,
            Data = value,
        };

    static MiscItem CloneCleanMisc(IMiscItemGetter tpl, uint id, string edid, string name, float weight, int value)
    {
        var m = (MiscItem)tpl.Duplicate(Own(id), new MiscItem.TranslationMask(defaultOn: true) { Name = false });
        m.EditorID = edid;
        m.Name = name;
        m.VirtualMachineAdapter = null;
        m.FeaturedItemMessage.Clear();
        m.Keywords?.Clear();
        m.Resources?.Clear();
        m.Weight = weight;
        m.Value = value;
        return m;
    }

    static Ingestible CloneCleanAlch(IIngestibleGetter tpl, uint id, string edid, string name, float weight, uint value, bool isFood)
    {
        var a = (Ingestible)tpl.Duplicate(Own(id), new Ingestible.TranslationMask(defaultOn: true) { Name = false, Description = false });
        a.EditorID = edid;
        a.Name = name;
        a.Description = string.Empty;
        a.VirtualMachineAdapter = null;
        a.Keywords?.Clear();
        a.Weight = weight;
        a.Value = value;
        a.Flags = Ingestible.Flag.NoAutoCalc | (isFood ? Ingestible.Flag.FoodItem : Ingestible.Flag.Medicine);
        return a;
    }

    static FormList MakeFormList(uint id, string edid, IEnumerable<FormKey> items)
    {
        var flst = new FormList(Own(id), Release)
        {
            EditorID = edid,
            FormVersion = 581,
        };
        foreach (var k in items)
            flst.Items.Add(k.ToLinkGetter<IStarfieldMajorRecordGetter>());
        return flst;
    }

    static Quest MakeQuest(uint id, string edid, string name, string script, IEnumerable<ushort> stages, FormKey testModeKey)
    {
        var quest = new Quest(Own(id), Release)
        {
            EditorID = edid,
            Name = name,
            FormVersion = 581,
            Version2 = 12,
            Data = new QuestData { Flags = Quest.Flag.StartGameEnabled, Priority = 30 },
        };
        foreach (var s in stages)
            quest.Stages.Add(new QuestStage { Index = s });
        var se = new ScriptEntry { Name = script, Flags = ScriptEntry.Flag.Local };
        se.Properties.Add(ObjProp("TestModeGlobal", testModeKey));
        quest.VirtualMachineAdapter = new QuestAdapter
        {
            Version = 6,
            ObjectFormat = 2,
            ExtraBindDataVersion = 3,
            Script = new ScriptEntry { Name = "", Flags = ScriptEntry.Flag.Local },
        };
        quest.VirtualMachineAdapter.Scripts.Add(se);
        return quest;
    }

    public static int Build(string templatePath, string outDir, float exclRadius, string? jsonPath = null)
    {
        var coreIds = LoadCoreValues(jsonPath);
        var testModeKey = Core(coreIds, TestModeEdid);
        using var sf = OpenTemplate(templatePath);
        var tpl = ResolveTemplates(sf);

        var mod = new StarfieldMod(Plugin, Release);
        mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master | StarfieldModHeader.HeaderFlag.Localized;
        mod.ModHeader.Author = "fo4-to-starfield";

        // 1. Quest & Globals
        mod.Quests.Add(MakeQuest(QuestId, QuestEdid, "FO4SF Settlements and C.A.M.P.s", QuestScript, Stages, testModeKey));
        mod.Globals.Add(MakeGlobal(CampExclusionRadiusGlobId, "FO4SF_CAMPExclusionRadiusM", exclRadius));
        mod.Globals.Add(MakeGlobal(ActiveCampCountGlobId, "FO4SF_ActiveCAMPCount", 0.0f));
        mod.Globals.Add(MakeGlobal(TrackedWorkshopCountGlobId, "FO4SF_TrackedWorkshopCount", 0.0f));
        mod.Globals.Add(MakeGlobal(TrackedStationCountGlobId, "FO4SF_TrackedStationCount", 0.0f));
        mod.Globals.Add(MakeGlobal(SanctuaryCleanBenchSwapGlobId, SanctuaryCleanBenchSwapGlobEdid, 0.0f));

        // 2. Portable C.A.M.P., Pack-Up, Settlement, and Scrapper Kits
        var campKitTpl = PickMiscTemplate(sf, new[] { "Tool_DuctTape01", "Deskfan03" }, tpl.DefaultMiscTemplate);
        mod.MiscItems.Add(CloneCleanMisc(campKitTpl, CampKitId, "FO4SF_CAMPKit", "Portable C.A.M.P. Kit", 2.0f, 120));
        mod.MiscItems.Add(CloneCleanMisc(tpl.DefaultMiscTemplate, CampPackTokenId, "FO4SF_CAMPPackToken", "C.A.M.P. Pack-Up Token", 0.0f, 0));
        mod.MiscItems.Add(CloneCleanMisc(tpl.DefaultMiscTemplate, SettlementKitId, "FO4SF_SettlementKit", "Settlement Workbench Kit", 1.0f, 50));
        mod.MiscItems.Add(CloneCleanMisc(tpl.DefaultMiscTemplate, ScrapTokenId, "FO4SF_ScrapToken", "Field Scrapper Kit", 0.0f, 0));

        // 3. Clean-room FO4 scrap junk MISC items with native Starfield IRES links
        foreach (var j in JunkSpecs)
        {
            var jTpl = PickMiscTemplate(sf, j.TemplatePrefs, tpl.DefaultMiscTemplate);
            var m = CloneCleanMisc(jTpl, j.Id, j.Edid, j.Name, j.Weight, j.Value);
            m.Resources = new ExtendedList<ItemResource>();
            foreach (var (cmpoIdx, cnt) in j.Yields)
            {
                var ir = new ItemResource { Count = cnt };
                ir.Resource.SetTo(tpl.CmpoPairs[cmpoIdx].Ires);
                m.Resources.Add(ir);
            }
            mod.MiscItems.Add(m);
        }

        // 4. Clean-room crafted outputs for FO4 COBJ + FNV RCPE bench recipes
        mod.Ingestibles.Add(CloneCleanAlch(tpl.AidTemplate, CraftFieldMedkitId, "FO4SF_Craft_FieldMedkit", "Wasteland Trauma Pack", 0.5f, 65, isFood: false));
        mod.MiscItems.Add(CloneCleanMisc(tpl.DefaultMiscTemplate, CraftWeaponPartsKitId, "FO4SF_Craft_WeaponPartsKit", "Machined Receiver Kit", 1.0f, 85));
        mod.MiscItems.Add(CloneCleanMisc(tpl.DefaultMiscTemplate, CraftSensorModuleId, "FO4SF_Craft_SensorModule", "Field Sensor Module", 0.8f, 95));
        mod.Ingestibles.Add(CloneCleanAlch(tpl.AidTemplate, CraftSurgicalBagId, "FO4SF_Craft_SurgicalBag", "Frontier Trauma Bag", 1.0f, 75, isFood: false));
        mod.Ingestibles.Add(CloneCleanAlch(tpl.AidTemplate, CraftCombatBlendId, "FO4SF_Craft_CombatBlend", "Adrenal Combat Blend", 0.2f, 80, isFood: false));
        mod.Ingestibles.Add(CloneCleanAlch(tpl.FoodTemplate, CraftTrailRationId, "FO4SF_Craft_TrailRation", "Caravan Trail Ration", 0.5f, 35, isFood: true));

        // 5. FO4 COBJ + FNV RCPE ConstructibleObjects
        foreach (var r in RecipeSpecs)
        {
            ConstructibleObject cobj;
            if (tpl.CobjTemplate != null)
            {
                cobj = (ConstructibleObject)tpl.CobjTemplate.Duplicate(Own(r.Id), new ConstructibleObject.TranslationMask(defaultOn: true) { Description = false });
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
                cobj = new ConstructibleObject(Own(r.Id), Release) { FormVersion = 581 };
            }

            cobj.EditorID = r.Edid;
            cobj.Description = r.Description;
            cobj.AmountProduced = r.AmountProduced;
            cobj.MenuSortOrder = r.SortOrder;
            cobj.Tier = 0;
            cobj.LearnMethod = ConstructibleObject.LearnMethodEnum.DefaultOrConditions;

            var benchKw = r.Bench switch
            {
                BenchKind.Industrial => tpl.BenchIndustrialKw,
                BenchKind.Chemlab => tpl.BenchChemlabKw,
                BenchKind.Cooking => tpl.BenchCookingKw,
                _ => tpl.BenchIndustrialKw,
            };
            cobj.WorkbenchKeyword.SetTo(benchKw);

            cobj.RecipeFilters = new ExtendedList<IFormLinkGetter<IKeywordGetter>>();
            var rf = r.Bench switch
            {
                BenchKind.Industrial => tpl.FilterIndustrialKw,
                BenchKind.Chemlab => tpl.FilterChemlabKw,
                BenchKind.Cooking => tpl.FilterCookingKw,
                _ => null,
            };
            if (rf.HasValue && r.CreatedOwnId != 0)
                cobj.RecipeFilters.Add(rf.Value.ToLinkGetter<IKeywordGetter>());

            cobj.CreatedObject.SetTo(r.CreatedOwnId == 0 ? tpl.AmmoProduct : Own(r.CreatedOwnId));
            cobj.ConstructableComponents = new ExtendedList<ConstructibleObjectComponent>();
            foreach (var (cmpoIdx, cnt) in r.Costs)
            {
                var cc = new ConstructibleObjectComponent { RequiredCount = cnt };
                cc.Component.SetTo(tpl.CmpoPairs[cmpoIdx].Ires);
                cobj.ConstructableComponents.Add(cc);
            }
            mod.ConstructibleObjects.Add(cobj);
        }

        // 6. Synchronized FormLists (CMPO -> IRES, CMPO -> MISC, Scrap Junk, Bench Recipes, Inventory Filter)
        mod.FormLists.Add(MakeFormList(CmpoIresListId, "FO4SF_CmpoIresList", tpl.CmpoPairs.Select(p => p.Ires)));
        mod.FormLists.Add(MakeFormList(CmpoMiscListId, "FO4SF_CmpoMiscList", tpl.CmpoPairs.Select(p => p.Misc)));
        mod.FormLists.Add(MakeFormList(ScrapJunkListId, "FO4SF_ScrapJunkList", JunkSpecs.Select(j => Own(j.Id))));
        mod.FormLists.Add(MakeFormList(BenchRecipesListId, "FO4SF_BenchRecipesList", RecipeSpecs.Select(r => Own(r.Id))));
        mod.FormLists.Add(MakeFormList(KitFilterListId, "FO4SF_KitFilterList",
            new[] { Own(CampKitId), Own(CampPackTokenId), Own(SettlementKitId), Own(ScrapTokenId) }));

        // 7. R11 D4: Clean Sanctuary Hills Workshop bench (zero Starfield OutpostCategory* keywords)
        var sancCatKw = new Keyword(Own(SanctuaryCategoryKwId), Release)
        {
            EditorID = SanctuaryCategoryKwEdid,
            Name = "Sanctuary",
            Type = Keyword.TypeEnum.RecipeFilter,
        };
        mod.Keywords.Add(sancCatKw);

        var sancBenchActi = new Mutagen.Bethesda.Starfield.Activator(Own(SanctuaryBenchActiId), Release)
        {
            EditorID = SanctuaryBenchActiEdid,
            Name = SanctuaryBenchName,
            Model = new Model { File = SanctuaryBenchModel },
            MarkerColor = System.Drawing.Color.FromArgb(0, 0xCC, 0x4C, 0x33),
            Flags = (Mutagen.Bethesda.Starfield.Activator.Flag)0,
            ActivationAngle = 360,
            InvertFacing = false,
            Keywords = new ExtendedList<IFormLinkGetter<IKeywordGetter>>
            {
                new FormLink<IKeywordGetter>(Sf(SfMustPersistKwId)),
                new FormLink<IKeywordGetter>(Sf(SfWorkshopKwId)),
                new FormLink<IKeywordGetter>(sancCatKw.FormKey),
            },
            Properties = new ExtendedList<ObjectProperty>
            {
                new ObjectProperty
                {
                    ActorValue = new FormLink<IActorValueInformationGetter>(Sf(SfOutpostBuildAreaRadiusAvId)),
                    Value = SanctuaryBenchRadius,
                },
            },
        };
        mod.Activators.Add(sancBenchActi);

        // 8. R11 F3 / F4: 3 Starfield furniture/container stand-in placeables (0x84B..0x84D: AK_Chair_Wood_01.nif,
        // FoundScrapCot01.nif, ToolBox_SetA_03.nif) + 3 zero-skill Sanctuary COBJs (0x84E..0x850) scoped ONLY to the
        // clean workbench 0x000849 (ZERO Starfield.esm FLST 0x058606/0x1A5507 Outpost overrides).
        Furniture CloneSanctuaryFurn(IFurnitureGetter src, uint id, string edid, string name)
        {
            var f = (Furniture)src.Duplicate(Own(id), new Furniture.TranslationMask(defaultOn: true) { Name = false });
            f.EditorID = edid;
            f.Name = name;
            f.VirtualMachineAdapter = null;
            return f;
        }
        mod.Furniture.Add(CloneSanctuaryFurn(tpl.SanctuaryChairTemplate, SanctuaryChairFurnId, SanctuaryChairFurnEdid, SanctuaryChairName));
        mod.Furniture.Add(CloneSanctuaryFurn(tpl.SanctuaryCotTemplate, SanctuaryCotFurnId, SanctuaryCotFurnEdid, SanctuaryCotName));

        var sancCrate = (Container)tpl.SanctuaryCrateTemplate.Duplicate(Own(SanctuaryCrateContId), new Container.TranslationMask(defaultOn: true) { Name = false });
        sancCrate.EditorID = SanctuaryCrateContEdid;
        sancCrate.Name = SanctuaryCrateName;
        sancCrate.VirtualMachineAdapter = null;
        sancCrate.Items?.Clear();
        mod.Containers.Add(sancCrate);

        ConstructibleObject MakeSanctuaryOutpostCobj(uint cobjId, string cobjEdid, uint createdOwnId, uint steelCost, float sortOrder)
        {
            ConstructibleObject cobj;
            if (tpl.OutpostCobjTemplate != null)
            {
                cobj = (ConstructibleObject)tpl.OutpostCobjTemplate.Duplicate(Own(cobjId), new ConstructibleObject.TranslationMask(defaultOn: true) { Description = false });
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
                cobj = new ConstructibleObject(Own(cobjId), Release) { FormVersion = 581 };
            }
            cobj.EditorID = cobjEdid;
            cobj.Description = string.Empty;
            cobj.AmountProduced = 1;
            cobj.MenuSortOrder = sortOrder;
            cobj.Tier = 0;
            cobj.LearnMethod = ConstructibleObject.LearnMethodEnum.DefaultOrConditions;
            cobj.WorkbenchKeyword.SetTo(sancCatKw.FormKey);
            cobj.RecipeFilters = new ExtendedList<IFormLinkGetter<IKeywordGetter>> { sancCatKw.FormKey.ToLinkGetter<IKeywordGetter>() };
            cobj.CreatedObject.SetTo(Own(createdOwnId));
            var cc = new ConstructibleObjectComponent { RequiredCount = steelCost };
            cc.Component.SetTo(tpl.CmpoPairs[0].Ires);
            cobj.ConstructableComponents = new ExtendedList<ConstructibleObjectComponent> { cc };
            return cobj;
        }
        mod.ConstructibleObjects.Add(MakeSanctuaryOutpostCobj(SanctuaryChairCobjId, SanctuaryChairCobjEdid, SanctuaryChairFurnId, 2, 1.0f));
        mod.ConstructibleObjects.Add(MakeSanctuaryOutpostCobj(SanctuaryCotCobjId, SanctuaryCotCobjEdid, SanctuaryCotFurnId, 2, 2.0f));
        mod.ConstructibleObjects.Add(MakeSanctuaryOutpostCobj(SanctuaryCrateCobjId, SanctuaryCrateCobjEdid, SanctuaryCrateContId, 1, 3.0f));

        // 9. R11 D4 / E6: Localized display-name overrides for Mars/Sol LCTN & STDT (never touches PNDT 0x03F59A!).
        // HeaderFlag.Localized + Data/Strings/FO4SFWorkshop_en.{STRINGS,DLSTRINGS,ILSTRINGS} prevents 2g-fix's blank '.' footer.
        void OverrideLocName(uint sfLocId, string newName, string label)
        {
            var src = sf.Locations.FirstOrDefault(x => x.FormKey == Sf(sfLocId))
                ?? throw new Refusal($"Starfield.esm missing LCTN 0x{sfLocId:X6} ({label})");
            var copy = src.DeepCopy();
            copy.Name = newName;
            mod.Locations.Add(copy);
        }
        OverrideLocName(SfLocMarsSurfaceId, CommonwealthLocName, "SSol_PMars_Surface");
        OverrideLocName(SfLocMarsPlanetId, CommonwealthLocName, "SSol_PMars");
        OverrideLocName(SfLocSolSystemId, MassachusettsStarName, "SSol");

        var solStar = sf.Stars.FirstOrDefault(x => x.FormKey == Sf(SfStarSolId))
            ?? throw new Refusal($"Starfield.esm missing STDT 0x{SfStarSolId:X6} (SolStar)");
        var solCopy = solStar.DeepCopy();
        solCopy.Name = MassachusettsStarName;
        var solFullComp = solCopy.Components.OfType<FullNameComponent>().FirstOrDefault();
        if (solFullComp != null)
            solFullComp.Name = MassachusettsStarName;
        else
            solCopy.Components.Add(new FullNameComponent { Name = MassachusettsStarName });
        mod.Stars.Add(solCopy);

        mod.ModHeader.Stats.NextFormID = NextId;

        Write(mod, outDir, SfEsm, CoreValuesEsm);
        var outPath = Path.Combine(outDir, Plugin.FileName);
        Console.WriteLine($"templates: {tpl.Summary}");
        Console.WriteLine($"wrote {outPath} ({new FileInfo(outPath).Length:N0} bytes): " +
                          $"1 QUST (TestModeGlobal -> {testModeKey}), 5 GLOB (excl={exclRadius.ToString("0.#", CultureInfo.InvariantCulture)}m, cleanSwap=0), " +
                          $"10 MISC, 4 ALCH, 2 FURN + 1 CONT Starfield stand-ins + 11 COBJ (3 Sanctuary zero-skill, 0 Outpost FLST overrides), " +
                          $"5 own FLST, 1 KYWD + 1 ACTI (Sanctuary Hills Workshop, 0 Starfield OutpostCategory* KWs), " +
                          $"3 localized LCTN + 1 localized STDT D4/E6 overrides (Commonwealth / Massachusetts)");
        return 0;
    }

    static void Write(StarfieldMod mod, string outDir, params ModKey[] masters)
    {
        Directory.CreateDirectory(outDir);
        var path = Path.Combine(outDir, mod.ModKey.FileName);
        var dataStringsDir = Path.Combine(outDir, "Data", "Strings");
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
            if (Directory.Exists(dataStringsDir))
            {
                foreach (var old in Directory.GetFiles(dataStringsDir, $"{mod.ModKey.Name}_*.*"))
                    File.Delete(old);
            }
            var tmpStringsDir = Path.Combine(tmpDir, "Strings");
            if (Directory.Exists(tmpStringsDir))
            {
                var emitted = Directory.GetFiles(tmpStringsDir);
                if (emitted.Length > 0)
                    Directory.CreateDirectory(dataStringsDir);
                foreach (var sfFile in emitted)
                    File.Move(sfFile, Path.Combine(dataStringsDir, Path.GetFileName(sfFile)), overwrite: true);
            }
            File.Move(tmp, path, overwrite: true);
        }
        finally
        {
            if (Directory.Exists(tmpDir)) Directory.Delete(tmpDir, true);
        }
    }

    // ---------------------------------------------------------------- check

    public static int Check(string pluginPath, string templatePath, float exclRadius, string? jsonPath = null)
    {
        var coreIds = LoadCoreValues(jsonPath);
        var testModeKey = Core(coreIds, TestModeEdid);
        using var sf = OpenTemplate(templatePath);
        var tpl = ResolveTemplates(sf);

        using var mod = OpenPlugin(pluginPath);

        var problems = new List<string>();
        void Need(bool ok, string what) { if (!ok) problems.Add(what); }

        var masters = mod.ModHeader.MasterReferences.Select(m => m.Master).ToList();
        Console.WriteLine($"{Path.GetFileName(pluginPath)}: header {mod.ModHeader.Flags}, masters [{string.Join(", ", masters)}], next 0x{mod.ModHeader.Stats.NextFormID:X}");
        Need(mod.ModKey == Plugin, $"file ModKey is {mod.ModKey}, expected {Plugin}");
        Need(mod.ModHeader.Flags.HasFlag(StarfieldModHeader.HeaderFlag.Master), "plugin header lacks Master flag");
        Need(mod.ModHeader.Flags.HasFlag(StarfieldModHeader.HeaderFlag.Localized), "E6 requires HeaderFlag.Localized so Starfield reads Data/Strings/* instead of treating inline bytes as StringID");
        var stringsDir = ResolveStringsFolder(pluginPath);
        var enStrings = stringsDir != null ? Path.Combine(stringsDir, $"{Plugin.Name}_en.STRINGS") : null;
        Need(enStrings != null && File.Exists(enStrings), $"missing {Plugin.Name}_en.STRINGS for Localized header");
        Need(masters.SequenceEqual(new[] { SfEsm, CoreValuesEsm }), $"masters are [{string.Join(", ", masters)}], expected [Starfield.esm, FO4SFCoreValues.esm]");

        var allowedOverrides = new HashSet<FormKey>
        {
            Sf(SfLocMarsSurfaceId),
            Sf(SfLocMarsPlanetId),
            Sf(SfLocSolSystemId),
            Sf(SfStarSolId),
        };
        var allRecords = mod.EnumerateMajorRecords().ToList();
        var ownRecords = allRecords.Where(r => r.FormKey.ModKey == Plugin).ToList();
        var foreign = allRecords.Where(r => r.FormKey.ModKey != Plugin).ToList();
        var badForeign = foreign.Where(r => !allowedOverrides.Contains(r.FormKey)).Select(r => r.FormKey.ToString()).ToList();
        Need(badForeign.Count == 0, $"plugin contains unauthorized foreign override records: {string.Join(", ", badForeign)}");
        Need(mod.Planets.Count == 0, $"plugin must never override Planet (PNDT 0x03F59A belongs to FO4TerrainCore_Mars.esm), found {mod.Planets.Count}");
        Need(mod.FormLists.All(fl => fl.FormKey.ModKey == Plugin), "F3: plugin must NOT override Starfield.esm Outpost FLSTs (0x058606 / 0x1A5507); scope SANCTUARY ONLY to clean workbench 0x000849");
        var dupCore = ownRecords.Where(r => r.EditorID != null && coreIds.ContainsKey(r.EditorID))
            .Select(r => r.EditorID!).ToList();
        Need(dupCore.Count == 0, $"plugin duplicates FO4SFCoreValues.esm EditorIDs: {string.Join(", ", dupCore)}");
        var lowRange = ownRecords.Where(r => r.FormKey.ID < 0x800).Select(r => r.FormKey.ToString()).ToList();
        Need(lowRange.Count == 0, $"plugin contains low-range FormIDs (<0x800): {string.Join(", ", lowRange)}");
        Need(ownRecords.Count == ExpectedOwnRecordCount, $"expected {ExpectedOwnRecordCount} own major records, found {ownRecords.Count}");
        Need(foreign.Count == ExpectedOverrideRecordCount, $"expected {ExpectedOverrideRecordCount} scoped D4/E6 overrides, found {foreign.Count}");
        Need(allRecords.Count == ExpectedMajorRecordCount, $"expected {ExpectedMajorRecordCount} major records, found {allRecords.Count}");

        // 1. Quest check
        var q = mod.Quests.FirstOrDefault(x => x.FormKey == Own(QuestId));
        Need(q != null && q.EditorID == QuestEdid, $"missing QUST 0x{QuestId:X} ({QuestEdid})");
        if (q != null)
        {
            var scripts = q.VirtualMachineAdapter?.Scripts.ToList() ?? new();
            Need(q.Data?.Flags.HasFlag(Quest.Flag.StartGameEnabled) == true, $"{QuestEdid} lacks StartGameEnabled");
            Need(q.Stages.Select(s => s.Index).SequenceEqual(Stages), $"{QuestEdid} stages are [{string.Join(",", q.Stages.Select(s => s.Index))}], expected [{string.Join(",", Stages)}]");
            Need(scripts.Count == 1 && scripts[0].Name == QuestScript && scripts[0].Properties.Count == 1,
                $"{QuestEdid} script must be {QuestScript} with 1 property (TestModeGlobal)");
            if (scripts.Count == 1 && scripts[0].Properties.Count == 1)
            {
                var p0 = scripts[0].Properties[0] as IScriptObjectPropertyGetter;
                Need(p0 != null && p0.Name == "TestModeGlobal" && p0.Object.FormKey == testModeKey,
                    $"{QuestEdid} property[0] must be TestModeGlobal -> {testModeKey}");
            }
        }

        // 2. Globals check
        void CheckGlob(uint id, string edid, float expectedVal)
        {
            var g = mod.Globals.FirstOrDefault(x => x.FormKey == Own(id));
            Need(g != null && g.EditorID == edid && !g.MajorFlags.HasFlag(Global.MajorFlag.Constant) && Math.Abs((g.Data ?? -999f) - expectedVal) < 0.01f,
                $"GLOB 0x{id:X} ({edid}) missing, constant, or != {expectedVal}");
        }
        CheckGlob(CampExclusionRadiusGlobId, "FO4SF_CAMPExclusionRadiusM", exclRadius);
        CheckGlob(ActiveCampCountGlobId, "FO4SF_ActiveCAMPCount", 0.0f);
        CheckGlob(TrackedWorkshopCountGlobId, "FO4SF_TrackedWorkshopCount", 0.0f);
        CheckGlob(TrackedStationCountGlobId, "FO4SF_TrackedStationCount", 0.0f);
        CheckGlob(SanctuaryCleanBenchSwapGlobId, SanctuaryCleanBenchSwapGlobEdid, 0.0f);

        // 3. CMPO -> IRES -> MISC FormLists check
        var iresList = mod.FormLists.FirstOrDefault(x => x.FormKey == Own(CmpoIresListId));
        var miscList = mod.FormLists.FirstOrDefault(x => x.FormKey == Own(CmpoMiscListId));
        Need(iresList != null && iresList.EditorID == "FO4SF_CmpoIresList" && iresList.Items.Count == CmpoSpecs.Length &&
             iresList.Items.Select(x => x.FormKey).SequenceEqual(tpl.CmpoPairs.Select(p => p.Ires)),
            "FLST FO4SF_CmpoIresList missing or does not match the 18 resolved Starfield.esm IRES forms");
        Need(miscList != null && miscList.EditorID == "FO4SF_CmpoMiscList" && miscList.Items.Count == CmpoSpecs.Length &&
             miscList.Items.Select(x => x.FormKey).SequenceEqual(tpl.CmpoPairs.Select(p => p.Misc)),
            "FLST FO4SF_CmpoMiscList missing or does not match the 18 resolved Starfield.esm MISC resource items");

        // 4. Kits & Scrap Junk MISC check
        foreach (var (id, edid) in new[] {
            (CampKitId, "FO4SF_CAMPKit"),
            (CampPackTokenId, "FO4SF_CAMPPackToken"),
            (SettlementKitId, "FO4SF_SettlementKit"),
            (ScrapTokenId, "FO4SF_ScrapToken"),
            (CraftWeaponPartsKitId, "FO4SF_Craft_WeaponPartsKit"),
            (CraftSensorModuleId, "FO4SF_Craft_SensorModule"),
        })
        {
            var m = mod.MiscItems.FirstOrDefault(x => x.FormKey == Own(id));
            Need(m != null && m.EditorID == edid && m.Model != null && (m.VirtualMachineAdapter?.Scripts.Count ?? 0) == 0,
                $"MISC 0x{id:X} ({edid}) missing, lacks model, or carries unexpected script");
        }

        foreach (var j in JunkSpecs)
        {
            var m = mod.MiscItems.FirstOrDefault(x => x.FormKey == Own(j.Id));
            Need(m != null && m.EditorID == j.Edid && m.Model != null, $"junk MISC 0x{j.Id:X} ({j.Edid}) missing or lacks model");
            if (m != null)
            {
                var res = m.Resources?.Select(r => (r.Resource.FormKey, r.Count)).ToList() ?? new();
                var want = j.Yields.Select(y => (tpl.CmpoPairs[y.CmpoIndex].Ires, y.Count)).ToList();
                Need(res.SequenceEqual(want), $"junk MISC {j.Edid} ItemResources do not match expected IRES yields");
            }
        }

        // 5. Crafted ALCH check
        foreach (var (id, edid) in new[] {
            (CraftFieldMedkitId, "FO4SF_Craft_FieldMedkit"),
            (CraftSurgicalBagId, "FO4SF_Craft_SurgicalBag"),
            (CraftCombatBlendId, "FO4SF_Craft_CombatBlend"),
            (CraftTrailRationId, "FO4SF_Craft_TrailRation"),
        })
        {
            var a = mod.Ingestibles.FirstOrDefault(x => x.FormKey == Own(id));
            Need(a != null && a.EditorID == edid && !string.IsNullOrWhiteSpace(a.Name?.String),
                $"ALCH 0x{id:X} ({edid}) missing or unnamed");
        }

        // 6. FO4 COBJ + FNV RCPE ConstructibleObjects check
        var iresSet = tpl.CmpoPairs.Select(p => p.Ires).ToHashSet();
        foreach (var r in RecipeSpecs)
        {
            var c = mod.ConstructibleObjects.FirstOrDefault(x => x.FormKey == Own(r.Id));
            Need(c != null && c.EditorID == r.Edid, $"COBJ 0x{r.Id:X} ({r.Edid}) missing");
            if (c == null) continue;

            var wantBench = r.Bench switch
            {
                BenchKind.Industrial => tpl.BenchIndustrialKw,
                BenchKind.Chemlab => tpl.BenchChemlabKw,
                BenchKind.Cooking => tpl.BenchCookingKw,
                _ => tpl.BenchIndustrialKw,
            };
            Need(c.WorkbenchKeyword.FormKey == wantBench, $"COBJ {r.Edid} WorkbenchKeyword is {c.WorkbenchKeyword.FormKey}, expected {wantBench}");

            var wantCreated = r.CreatedOwnId == 0 ? tpl.AmmoProduct : Own(r.CreatedOwnId);
            Need(c.CreatedObject.FormKey == wantCreated && c.AmountProduced == r.AmountProduced,
                $"COBJ {r.Edid} CreatedObject/AmountProduced mismatch");
            Need(c.Conditions.Count == 0 && (c.RequiredPerks?.Count ?? 0) == 0 &&
                 c.LearnMethod == ConstructibleObject.LearnMethodEnum.DefaultOrConditions,
                $"COBJ {r.Edid} has unexpected Conditions, RequiredPerks, or LearnMethod lock");

            var comps = c.ConstructableComponents?.Select(cc => (cc.Component.FormKey, cc.RequiredCount)).ToList() ?? new();
            var wantComps = r.Costs.Select(k => (tpl.CmpoPairs[k.CmpoIndex].Ires, k.Count)).ToList();
            Need(comps.Count > 0 && comps.SequenceEqual(wantComps) && comps.All(cc => iresSet.Contains(cc.FormKey)),
                $"COBJ {r.Edid} ConstructableComponents do not match resolved IRES costs");
        }

        // 7. Remaining FormLists check
        var junkFlst = mod.FormLists.FirstOrDefault(x => x.FormKey == Own(ScrapJunkListId));
        Need(junkFlst != null && junkFlst.Items.Select(x => x.FormKey).SequenceEqual(JunkSpecs.Select(j => Own(j.Id))),
            "FLST FO4SF_ScrapJunkList does not list the 4 junk MISC items in order");
        var recipeFlst = mod.FormLists.FirstOrDefault(x => x.FormKey == Own(BenchRecipesListId));
        Need(recipeFlst != null && recipeFlst.Items.Select(x => x.FormKey).SequenceEqual(RecipeSpecs.Select(r => Own(r.Id))),
            "FLST FO4SF_BenchRecipesList does not list the 8 bench recipes in order");
        var filterFlst = mod.FormLists.FirstOrDefault(x => x.FormKey == Own(KitFilterListId));
        Need(filterFlst != null && filterFlst.Items.Select(x => x.FormKey).SequenceEqual(
                new[] { Own(CampKitId), Own(CampPackTokenId), Own(SettlementKitId), Own(ScrapTokenId) }),
            "FLST FO4SF_KitFilterList does not list the 4 portable kit/token items in order");

        // 8. R11 D4: Clean Sanctuary Hills Workshop bench + Mars/Sol LCTN/STDT overrides
        var sancKw = mod.Keywords.FirstOrDefault(x => x.FormKey == Own(SanctuaryCategoryKwId));
        Need(sancKw != null && sancKw.EditorID == SanctuaryCategoryKwEdid &&
             sancKw.Name?.String == "Sanctuary" && sancKw.Type == Keyword.TypeEnum.RecipeFilter,
            $"KYWD 0x{SanctuaryCategoryKwId:X} ({SanctuaryCategoryKwEdid}) missing or invalid");

        var sancActi = mod.Activators.FirstOrDefault(x => x.FormKey == Own(SanctuaryBenchActiId));
        Need(sancActi != null && sancActi.EditorID == SanctuaryBenchActiEdid &&
             sancActi.Name?.String == SanctuaryBenchName &&
             string.Equals(sancActi.Model?.File?.GivenPath, SanctuaryBenchModel, StringComparison.OrdinalIgnoreCase) &&
             sancActi.ActivationAngle == 360 && !sancActi.InvertFacing,
            $"ACTI 0x{SanctuaryBenchActiId:X} ({SanctuaryBenchActiEdid}) missing or invalid metadata/model");
        if (sancActi != null)
        {
            var kwSet = (sancActi.Keywords ?? Enumerable.Empty<IFormLinkGetter<IKeywordGetter>>()).Select(k => k.FormKey).ToHashSet();
            Need(kwSet.Contains(Sf(SfWorkshopKwId)) && kwSet.Contains(Own(SanctuaryCategoryKwId)),
                $"{SanctuaryBenchActiEdid} must carry WorkshopKeyword and {SanctuaryCategoryKwEdid}");
            var forbidden = ForbiddenStarfieldOutpostCategoryIds.Where(id => kwSet.Contains(Sf(id))).Select(id => $"0x{id:X6}").ToList();
            Need(forbidden.Count == 0,
                $"{SanctuaryBenchActiEdid} must carry ZERO Starfield OutpostCategory* keywords, found: {string.Join(", ", forbidden)}");
            var radiusProp = sancActi.Properties?.FirstOrDefault(p => p.ActorValue.FormKey == Sf(SfOutpostBuildAreaRadiusAvId));
            Need(radiusProp != null && Math.Abs(radiusProp.Value - SanctuaryBenchRadius) < 0.01f,
                $"{SanctuaryBenchActiEdid} missing OutpostBuildAreaRadius={SanctuaryBenchRadius}");
        }

        // 9. R11 F4: 3 Starfield furniture/container stand-in placeables + zero-skill COBJs (0x84B..0x850) + E6 LCTN/STDT overrides
        foreach (var (fid, edid, wantName) in new[] {
            (SanctuaryChairFurnId, SanctuaryChairFurnEdid, SanctuaryChairName),
            (SanctuaryCotFurnId, SanctuaryCotFurnEdid, SanctuaryCotName),
        })
        {
            var f = mod.Furniture.FirstOrDefault(x => x.FormKey == Own(fid));
            Need(f != null && f.EditorID == edid && f.Name?.String == wantName && f.Model != null && (f.VirtualMachineAdapter?.Scripts.Count ?? 0) == 0,
                $"FURN 0x{fid:X} ({edid}) missing, misnamed, lacks model, or carries script");
        }
        var crateRec = mod.Containers.FirstOrDefault(x => x.FormKey == Own(SanctuaryCrateContId));
        Need(crateRec != null && crateRec.EditorID == SanctuaryCrateContEdid && crateRec.Name?.String == SanctuaryCrateName &&
             crateRec.Model != null && (crateRec.VirtualMachineAdapter?.Scripts.Count ?? 0) == 0 && (crateRec.Items?.Count ?? 0) == 0,
            $"CONT 0x{SanctuaryCrateContId:X} ({SanctuaryCrateContEdid}) missing, misnamed, non-empty, or carries script");

        foreach (var (cobjId, cobjEdid, createdId, steelCost) in new[] {
            (SanctuaryChairCobjId, SanctuaryChairCobjEdid, SanctuaryChairFurnId, 2u),
            (SanctuaryCotCobjId, SanctuaryCotCobjEdid, SanctuaryCotFurnId, 2u),
            (SanctuaryCrateCobjId, SanctuaryCrateCobjEdid, SanctuaryCrateContId, 1u),
        })
        {
            var c = mod.ConstructibleObjects.FirstOrDefault(x => x.FormKey == Own(cobjId));
            Need(c != null && c.EditorID == cobjEdid, $"Sanctuary COBJ 0x{cobjId:X} ({cobjEdid}) missing");
            if (c == null) continue;
            Need(c.WorkbenchKeyword.FormKey == Own(SanctuaryCategoryKwId),
                $"Sanctuary COBJ {cobjEdid} WorkbenchKeyword is {c.WorkbenchKeyword.FormKey}, expected {Own(SanctuaryCategoryKwId)}");
            var rfs = c.RecipeFilters?.Select(k => k.FormKey).ToList() ?? new();
            Need(rfs.SequenceEqual(new[] { Own(SanctuaryCategoryKwId) }),
                $"Sanctuary COBJ {cobjEdid} RecipeFilters must be [{Own(SanctuaryCategoryKwId)}]");
            Need(c.CreatedObject.FormKey == Own(createdId) && c.AmountProduced == 1 && c.Tier == 0,
                $"Sanctuary COBJ {cobjEdid} CreatedObject/AmountProduced/Tier mismatch");
            Need(c.Conditions.Count == 0 && (c.RequiredPerks?.Count ?? 0) == 0 &&
                 c.LearnMethod == ConstructibleObject.LearnMethodEnum.DefaultOrConditions,
                $"Sanctuary COBJ {cobjEdid} has unexpected Conditions, RequiredPerks, or LearnMethod lock");
            var comps = c.ConstructableComponents?.Select(cc => (cc.Component.FormKey, cc.RequiredCount)).ToList() ?? new();
            Need(comps.SequenceEqual(new[] { (tpl.CmpoPairs[0].Ires, steelCost) }),
                $"Sanctuary COBJ {cobjEdid} ConstructableComponents mismatch");
        }

        void CheckLocOverride(uint id, string wantName, string label)
        {
            var loc = mod.Locations.FirstOrDefault(x => x.FormKey == Sf(id));
            Need(loc != null && loc.Name?.String == wantName &&
                 !string.Equals(loc.Name?.String, "Mars", StringComparison.OrdinalIgnoreCase) &&
                 !string.Equals(loc.Name?.String, "Sol", StringComparison.OrdinalIgnoreCase),
                $"E6 LCTN override 0x{id:X6} ({label}) missing or Name != '{wantName}'");
        }
        CheckLocOverride(SfLocMarsSurfaceId, CommonwealthLocName, "SSol_PMars_Surface");
        CheckLocOverride(SfLocMarsPlanetId, CommonwealthLocName, "SSol_PMars");
        CheckLocOverride(SfLocSolSystemId, MassachusettsStarName, "SSol");
        var starOv = mod.Stars.FirstOrDefault(x => x.FormKey == Sf(SfStarSolId));
        var starFull = starOv?.Components.OfType<IFullNameComponentGetter>().FirstOrDefault()?.Name?.String;
        Need(starOv != null && starOv.Name == MassachusettsStarName && starFull == MassachusettsStarName,
            $"E6 STDT override 0x{SfStarSolId:X6} (SolStar) missing or ANAM/FULL != '{MassachusettsStarName}'");

        foreach (var x in problems) Console.WriteLine("FAIL  " + x);
        Console.WriteLine(problems.Count == 0 ? "all checks pass" : $"{problems.Count} problem(s)");
        return problems.Count == 0 ? 0 : 1;
    }

    // ---------------------------------------------------------------- fixture & selftest

    public static int Fixture(string outDir, string mode)
    {
        if (mode is not ("full" or "minimal"))
            throw new Refusal($"fixture --mode must be full or minimal, got {mode}");

        var mod = new StarfieldMod(SfEsm, Release);
        mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;

        // WorkshopKeyword (0x054BA7), MustPersist (0x04AF68), AnimFurnWorkbench (0x01A21C), OutpostBuildAreaRadius (0x063FC5), OutpostBeaconActivator (0x2C60E9)
        mod.Keywords.Add(new Keyword(Sf(SfMustPersistKwId), Release) { EditorID = "MustPersist" });
        mod.Keywords.Add(new Keyword(Sf(SfWorkshopKwId), Release) { EditorID = "WorkshopKeyword" });
        mod.Keywords.Add(new Keyword(Sf(0x01A21C), Release) { EditorID = "AnimFurnWorkbench" });
        mod.ActorValueInformation.Add(new ActorValueInformation(Sf(SfOutpostBuildAreaRadiusAvId), Release) { EditorID = "OutpostBuildAreaRadius" });
        mod.Activators.Add(new Mutagen.Bethesda.Starfield.Activator(Sf(0x2C60E9), Release)
        {
            EditorID = "OutpostBeaconActivator",
            Model = new Model { File = "Meshes\\Outpost\\Beacon.nif" },
        });

        // Mars/Sol LCTN & STDT templates for E6 localized display-name overrides + clean FURN/CONT stand-in templates for F4
        mod.Locations.Add(new Location(Sf(SfLocSolSystemId), Release) { EditorID = "SSol", Name = "Sol" });
        mod.Locations.Add(new Location(Sf(SfLocMarsPlanetId), Release)
        {
            EditorID = "SSol_PMars",
            Name = "Mars",
            ParentLocation = new FormLinkNullable<ILocationGetter>(Sf(SfLocSolSystemId)),
        });
        mod.Locations.Add(new Location(Sf(SfLocMarsSurfaceId), Release)
        {
            EditorID = "SSol_PMars_Surface",
            Name = "Mars",
            ParentLocation = new FormLinkNullable<ILocationGetter>(Sf(SfLocMarsPlanetId)),
        });
        var fixStar = new Star(Sf(SfStarSolId), Release) { EditorID = "SolStar", Name = "Sol" };
        fixStar.Components.Add(new FullNameComponent { Name = "Sol" });
        mod.Stars.Add(fixStar);
        mod.Furniture.Add(new Furniture(Sf(SfFurnWoodChairTplId), Release)
        {
            EditorID = "AK_Chair_Wood_01_Free",
            Name = "Chair",
            Model = new Model { File = "Furniture\\Chairs\\Generic\\AK_Chair_Wood_01.nif" },
        });
        mod.Furniture.Add(new Furniture(Sf(SfFurnScrapCotTplId), Release)
        {
            EditorID = "FoundScrapCot01",
            Name = "Cot",
            Model = new Model { File = "SetDressing\\Found\\FoundScrapCot01.nif" },
        });
        mod.Containers.Add(new Container(Sf(SfContStorageCrateTplId), Release)
        {
            EditorID = "Loot_Storage_Miscbox05_Common_Empty",
            Name = "Storage Crate",
            Model = new Model { File = "SetDressing\\Toolbox_Kits\\ToolBox_SetA_03.nif" },
        });

        // Bench & RecipeFilter Keywords
        mod.Keywords.Add(new Keyword(Sf(0x0AA209), Release) { EditorID = "WorkbenchIndustrialKeyword" });
        if (mode == "full")
        {
            mod.Keywords.Add(new Keyword(Sf(0x102158), Release) { EditorID = "WorkbenchChemlabRecipeKeyword" });
            mod.Keywords.Add(new Keyword(Sf(0x102152), Release) { EditorID = "WorkbenchCookingKeyword" });
            mod.Keywords.Add(new Keyword(Sf(0x2E2F2D), Release) { EditorID = "RecipeManufactured" });
            mod.Keywords.Add(new Keyword(Sf(0x10215A), Release) { EditorID = "RecipeChem" });
            mod.Keywords.Add(new Keyword(Sf(0x2C6660), Release) { EditorID = "RecipeFood" });
        }

        // Base MISC prop templates
        mod.MiscItems.Add(new MiscItem(Sf(0x00FBDB), Release)
        {
            EditorID = mode == "full" ? "Deskfan03" : "Misc_Junk_Fork",
            Name = "Prop",
            Model = new Model { File = "Meshes\\Props\\DeskFan03.nif" },
        });
        if (mode == "full")
        {
            mod.MiscItems.Add(new MiscItem(Sf(0x2AC95F), Release)
            {
                EditorID = "Tool_DuctTape01",
                Name = "Tape",
                Model = new Model { File = "Meshes\\Items\\Tools\\Tool_DuctTape01.nif" },
            });
            mod.MiscItems.Add(new MiscItem(Sf(0x0FD7D1), Release)
            {
                EditorID = "Kitchenware_Plate01",
                Name = "Plate",
                Model = new Model { File = "Meshes\\Props\\Plate01.nif" },
            });
            mod.MiscItems.Add(new MiscItem(Sf(0x04A6C7), Release)
            {
                EditorID = "OE_KT_HiveMine_Canister_Poison",
                Name = "Canister",
                Model = new Model { File = "Meshes\\Props\\Canister.nif" },
            });
        }

        // Resources (IRES) + linked MISC crafting items
        int resCount = mode == "full" ? CmpoSpecs.Length : 3;
        for (int i = 0; i < resCount; i++)
        {
            var spec = CmpoSpecs[i];
            uint iresId = (i == 0) ? 0x0057C7u : (i == 2) ? 0x0057D6u : (uint)(0x009100 + i);
            uint miscId = (i == 0) ? 0x00556Eu : (i == 2) ? 0x00557Du : (uint)(0x009200 + i);
            var res = new Resource(Sf(iresId), Release)
            {
                EditorID = mode == "full" ? spec.IresPrefs[0] : $"SynthRes_{i}",
                Name = spec.Archetype,
            };
            mod.Resources.Add(res);

            var m = new MiscItem(Sf(miscId), Release)
            {
                EditorID = mode == "full" ? spec.MiscPrefs[0] : $"SynthMisc_{i}",
                Name = spec.Archetype,
                Model = new Model { File = "Meshes\\Props\\Ore.nif" },
                Resources = new ExtendedList<ItemResource>(),
            };
            var ir = new ItemResource { Count = 1 };
            ir.Resource.SetTo(res.FormKey);
            m.Resources.Add(ir);
            mod.MiscItems.Add(m);
        }

        // Aid, Food, Ammo, and COBJ templates
        mod.Ingestibles.Add(new Ingestible(Sf(0x00ABF9), Release)
        {
            EditorID = mode == "full" ? "Aid_MedPack" : "SynthAid",
            Name = "Aid",
            Model = new Model { File = "Meshes\\Items\\Aid.nif" },
            Flags = Ingestible.Flag.NoAutoCalc | Ingestible.Flag.Medicine,
        });
        if (mode == "full")
        {
            mod.Ingestibles.Add(new Ingestible(Sf(0x122E94), Release)
            {
                EditorID = "Food_Craft_GalaxyMein",
                Name = "Meal",
                Model = new Model { File = "Meshes\\Items\\Food.nif" },
                Flags = Ingestible.Flag.NoAutoCalc | Ingestible.Flag.FoodItem,
            });
            mod.Ammunitions.Add(new Ammunition(Sf(0x04AD3E), Release)
            {
                EditorID = "Ammo777mm",
                Name = "7.77mm",
                Model = new Model { File = "Meshes\\Items\\Ammo.nif" },
            });
            var tplCobj = new ConstructibleObject(Sf(0x2457C1), Release)
            {
                EditorID = "co_mfg_Tier01_AdaptiveFrame",
                AmountProduced = 1,
                LearnMethod = ConstructibleObject.LearnMethodEnum.DefaultOrConditions,
            };
            tplCobj.WorkbenchKeyword.SetTo(Sf(0x0AA209));
            tplCobj.CreatedObject.SetTo(Sf(0x00556E));
            mod.ConstructibleObjects.Add(tplCobj);
        }

        Directory.CreateDirectory(outDir);
        var sfPath = Path.Combine(outDir, "Starfield.esm");
        mod.BeginWrite.ToPath(sfPath).WithNoLoadOrder().NoCheckIfLowerRangeDisallowed().Write();
        Console.WriteLine($"wrote {sfPath} (mode={mode})");
        return 0;
    }

    static StarfieldMod OpenMutablePlugin(string pluginPath)
    {
        var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        styles.Set(new KeyedMasterStyle(SfEsm, MasterStyle.Full));
        styles.Set(new KeyedMasterStyle(CoreValuesEsm, MasterStyle.Full));
        var stringsDir = ResolveStringsFolder(pluginPath);
        var rp = new BinaryReadParameters
        {
            MasterFlagsLookup = styles,
            StringsParam = stringsDir != null ? new StringsReadParameters { StringsFolderOverride = stringsDir } : null,
        };
        return StarfieldMod.CreateFromBinary(pluginPath, Release, rp);
    }

    public static int SelfTest(string scratchDir)
    {
        Directory.CreateDirectory(scratchDir);
        foreach (var mode in new[] { "full", "minimal" })
        {
            var mDir = Path.Combine(scratchDir, "m_" + mode);
            var bDir = Path.Combine(scratchDir, "b_" + mode);
            if (Fixture(mDir, mode) != 0) throw new Refusal($"fixture {mode} failed");
            var sfPath = Path.Combine(mDir, "Starfield.esm");
            if (Build(sfPath, bDir, 45.0f) != 0) throw new Refusal($"build {mode} failed");
            if (Check(Path.Combine(bDir, Plugin.FileName), sfPath, 45.0f) != 0) throw new Refusal($"check {mode} failed");
        }

        // Custom exclusion radius check
        var fullSf = Path.Combine(scratchDir, "m_full", "Starfield.esm");
        var optDir = Path.Combine(scratchDir, "b_opt");
        if (Build(fullSf, optDir, 60.0f) != 0) throw new Refusal("build --exclusion-radius 60 failed");
        if (Check(Path.Combine(optDir, Plugin.FileName), fullSf, 60.0f) != 0) throw new Refusal("check --exclusion-radius 60 failed");
        if (Check(Path.Combine(optDir, Plugin.FileName), fullSf, 45.0f) == 0)
            throw new Refusal("check failed to reject mismatched --exclusion-radius");

        // 8 tamper negative controls
        var cleanPlugin = Path.Combine(scratchDir, "b_full", Plugin.FileName);
        int tIdx = 0;
        void ExpectTamperFail(string label, Action<StarfieldMod> mutate)
        {
            tIdx++;
            var tDir = Path.Combine(scratchDir, $"tamper_{tIdx}");
            var mod = OpenMutablePlugin(cleanPlugin);
            mutate(mod);
            Write(mod, tDir, SfEsm, CoreValuesEsm);
            if (Check(Path.Combine(tDir, Plugin.FileName), fullSf, 45.0f) == 0)
                throw new Refusal($"tamper control #{tIdx} ({label}) unexpectedly passed Check");
        }

        // 1. Foreign override injected
        ExpectTamperFail("foreign_override", m =>
            m.Globals.Add(new Global(Sf(0x00A039), Release) { EditorID = "ForeignOverrideGlob", Data = 1.0f }));

        // 2. Quest lacks StartGameEnabled
        ExpectTamperFail("quest_not_start_enabled", m =>
            m.Quests.First(q => q.FormKey == Own(QuestId)).Data!.Flags = 0);

        // 3. Extra quest property injected
        ExpectTamperFail("quest_extra_property", m =>
            m.Quests.First(q => q.FormKey == Own(QuestId)).VirtualMachineAdapter!.Scripts[0].Properties
                .Add(new ScriptIntProperty { Name = "BadProp", Data = 1 }));

        // 4. TestModeGlobal property target corrupted
        ExpectTamperFail("quest_bad_testmode_prop", m =>
            ((ScriptObjectProperty)m.Quests.First(q => q.FormKey == Own(QuestId)).VirtualMachineAdapter!.Scripts[0].Properties[0])
                .Object.SetTo(Own(CampExclusionRadiusGlobId)));

        // 4. CMPO -> IRES FormList truncated
        ExpectTamperFail("cmpo_ires_truncated", m =>
            m.FormLists.First(f => f.FormKey == Own(CmpoIresListId)).Items.RemoveAt(0));

        // 5. Junk MISC stripped of ItemResources
        ExpectTamperFail("junk_missing_ires", m =>
            m.MiscItems.First(x => x.FormKey == Own(JunkDeskFanId)).Resources!.Clear());

        // 6. COBJ WorkbenchKeyword cleared
        ExpectTamperFail("cobj_missing_bench_kw", m =>
            m.ConstructibleObjects.First(c => c.FormKey == Own(CobjFo4WeaponPartsKitId)).WorkbenchKeyword.Clear());

        // 7. COBJ locked behind a Condition
        ExpectTamperFail("cobj_locked_by_condition", m =>
            m.ConstructibleObjects.First(c => c.FormKey == Own(RcpeNvSurgicalBagId)).Conditions
                .Add(new ConditionFloat { Data = new IsInWaterConditionData() }));

        // 8. D4: Starfield OutpostCategoryCrafting leaked onto Sanctuary bench
        ExpectTamperFail("d4_starfield_outpost_category_leaked", m =>
            m.Activators.First(a => a.FormKey == Own(SanctuaryBenchActiId)).Keywords!
                .Add(new FormLink<IKeywordGetter>(Sf(ForbiddenStarfieldOutpostCategoryIds[0]))));

        // 10. E6: Mars location display name reverted to "Mars"
        ExpectTamperFail("e6_mars_location_name_reverted", m =>
            m.Locations.First(l => l.FormKey == Sf(SfLocMarsPlanetId)).Name = "Mars");

        // 11. D4: Sanctuary clean bench swap switch defaults to non-zero (must default to 0.0 = OFF)
        ExpectTamperFail("d4_clean_bench_swap_default_nonzero", m =>
            m.Globals.First(g => g.FormKey == Own(SanctuaryCleanBenchSwapGlobId)).Data = 1.0f);

        // 12. E6: Sanctuary Outpost COBJ locked behind a Condition
        ExpectTamperFail("d4_sanctuary_cobj_locked_by_condition", m =>
            m.ConstructibleObjects.First(c => c.FormKey == Own(SanctuaryChairCobjId)).Conditions
                .Add(new ConditionFloat { Data = new IsInWaterConditionData() }));

        // 13. F3: Starfield Outpost FLST override leaked back into FO4SFWorkshop.esm
        ExpectTamperFail("f3_starfield_outpost_flst_leaked", m =>
            m.FormLists.Add(new FormList(Sf(0x058606), Release) { EditorID = "OutpostRecipeCategories" }));

        // 14. E6: Non-localized TES4 header (writes raw inline strings onto localized LCTN overrides -> '2g-fix' blank '.' footer)
        ExpectTamperFail("e6_non_localized_header", m =>
            m.ModHeader.Flags &= ~StarfieldModHeader.HeaderFlag.Localized);

        Console.WriteLine("selftest: ok (full + minimal fixtures, options, and 14 tamper controls passed)");
        return 0;
    }
}
