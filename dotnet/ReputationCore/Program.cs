// ReputationCore: Multi-title Global Karma (-1000..+1000) and 16-state Faction Reputation (FO4SFReputation.esm).
//
// Masters [Starfield.esm, FO4SFCoreValues.esm]; adds records only, 0 overrides on vanilla records, and 0 duplicate
// EditorIDs with FO4SFCoreValues.esm or FO4SFProgression.esm.
// Shared records from FO4SFCoreValues.esm (via src/fo4sf/core/core_values.json):
//   0x830          AVIF  FO4SF_Karma                  -1000..+1000, default 0
//   0x831          GLOB  FO4SF_KarmaValue             0 (non-constant)
//   0x832          GLOB  FO4SF_KarmaTier              0 (-2..+2, non-constant)
//   0x860          GLOB  FO4SF_TestModeEnabled        0 (non-constant)
// Deterministic local FormIDs in FO4SFReputation.esm (held equal with src/fo4sf/reputation/tables.py and PSC):
//   0x800          QUST  FO4SF_ReputationQuest        StartGameEnabled, stages 10..60, script FO4SF_ReputationQuest
//   0x804          GLOB  FO4SF_EndingMoralSlide       2 (0..4, default 2 = Neutral, non-constant)
//   0x805          AVIF  FO4SF_VendorBuyMult          0.25..2.00, default 1.00
//   0x806          PERK  FO4SF_RepVendorPerk          ModBuyPrices perk gated per-slot by merchant GetInFaction
//   0x807          GLOB  FO4SF_CompanionMoralReaction 0 (-2 desertion, -1 good warn, 0 steady, +1 evil warn)
//   0x808..0x80C   PERK  FO4SF_KarmaTag_VeryEvil..VeryGood  5 dialogue [Perk] tag perks for Karma tiers -2..+2
//   0x810..0x81E   FACT  FO4SF_RepFact_*              N slots (default 8 FO4 slots; 13 FNV slots; 1..15 configurable)
//   0x81F          FLST  FO4SF_RepFactList            ordered FormList of 0x810..0x810+N-1
//   0x820..0x82E   AVIF  FO4SF_Fame_*                 0..100 Fame AVIFs (FLST 0x82F FO4SF_FameAvList)
//   0x830..0x83E   AVIF  FO4SF_Infamy_*               0..100 Infamy AVIFs (FLST 0x83F FO4SF_InfamyAvList)
//   0x840..0x84E   AVIF  FO4SF_RepState_*             0..15 16-state code AVIFs (FLST 0x84F FO4SF_RepStateAvList)
//   0x850..0x85E   GLOB  FO4SF_FameGlob_*             0..100 Fame GLOBs (FLST 0x85F FO4SF_FameGlobList)
//   0x860..0x86E   GLOB  FO4SF_InfamyGlob_*           0..100 Infamy GLOBs (FLST 0x86F FO4SF_InfamyGlobList)
//   0x870..0x87E   GLOB  FO4SF_StateGlob_*            0..15 state code GLOBs (FLST 0x87F FO4SF_StateGlobList)
//   0x880..0x883   MISC  FO4SF_CharityToken / TheftToken / FactionAidToken / FactionCrimeToken
//   0x88F          FLST  FO4SF_RepTokenList           inventory event filter FormList for 0x880..0x883
//   0x888          NPC_  FO4SF_RepVendorNpc           faction vendor NPC (omitted under --no-test-cell)
//   0x890          CELL  FO4SF_RepTestCell            interior test room (omitted under --no-test-cell)
//
// usage:
//   ReputationCore build <Starfield.esm> <out_dir> [--json <path>] [--slot-count <1..15>] [--no-test-cell]
//   ReputationCore check <FO4SFReputation.esm> <Starfield.esm> [--json <path>] [--slot-count <1..15>] [--no-test-cell]
//   ReputationCore fixture <out_dir>
//   ReputationCore selftest <scratch_dir>

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
    int slotCount = 8;
    bool noTestCell = false;

    int jsonIdx = rest.IndexOf("--json");
    if (jsonIdx >= 0)
    {
        if (jsonIdx + 1 >= rest.Count) throw new ReputationCore.Refusal("--json needs a path");
        jsonPath = rest[jsonIdx + 1];
        rest.RemoveRange(jsonIdx, 2);
    }
    int slotIdx = rest.IndexOf("--slot-count");
    if (slotIdx >= 0)
    {
        if (slotIdx + 1 >= rest.Count ||
            !int.TryParse(rest[slotIdx + 1], NumberStyles.Integer, CultureInfo.InvariantCulture, out slotCount) ||
            slotCount < 1 || slotCount > 15)
            throw new ReputationCore.Refusal("--slot-count must be an integer in 1..15");
        rest.RemoveRange(slotIdx, 2);
    }
    int ntcIdx = rest.IndexOf("--no-test-cell");
    if (ntcIdx >= 0)
    {
        noTestCell = true;
        rest.RemoveAt(ntcIdx);
    }

    var opts = new ReputationCore.BuildOptions(jsonPath ?? ReputationCore.DefaultJsonPath(), slotCount, noTestCell);
    if (rest.Count == 3 && rest[0] == "build") return ReputationCore.Build(rest[1], rest[2], opts);
    if (rest.Count == 3 && rest[0] == "check") return ReputationCore.Check(rest[1], rest[2], opts);
    if (rest.Count == 2 && rest[0] == "fixture") return ReputationCore.Fixture(rest[1]);
    if (rest.Count == 2 && rest[0] == "selftest") return ReputationCore.SelfTest(rest[1]);
}
catch (ReputationCore.Refusal r)
{
    Console.Error.WriteLine("refused: " + r.Message);
    return 1;
}
Console.Error.WriteLine(
    "usage: ReputationCore build <Starfield.esm> <out_dir> [--json <path>] [--slot-count <1..15>] [--no-test-cell] | " +
    "check <FO4SFReputation.esm> <Starfield.esm> [same options] | fixture <out_dir> | selftest <scratch_dir>");
return 2;

static class ReputationCore
{
    public sealed class Refusal(string m) : Exception(m);
    public record BuildOptions(string JsonPath, int SlotCount = 8, bool NoTestCell = false);

    const StarfieldRelease Release = StarfieldRelease.Starfield;
    static readonly ModKey SfEsm = ModKey.FromFileName("Starfield.esm");
    static readonly ModKey CoreValuesEsm = ModKey.FromFileName("FO4SFCoreValues.esm");
    public static readonly ModKey Plugin = ModKey.FromFileName("FO4SFReputation.esm");

    static readonly ModKey[] ExpectedMasters = { SfEsm, CoreValuesEsm };

    // Fixed local FormIDs in FO4SFReputation.esm (held equal with src/fo4sf/reputation/tables.py)
    public const uint QuestId = 0x800;
    public const uint EndingMoralSlideGlobId = 0x804;
    public const uint VendorBuyMultAvId = 0x805;
    public const uint RepVendorPerkId = 0x806;
    public const uint CompanionMoralGlobId = 0x807;
    public const uint KarmaPerkVeryEvilId = 0x808;
    public const uint KarmaPerkEvilId = 0x809;
    public const uint KarmaPerkNeutralId = 0x80A;
    public const uint KarmaPerkGoodId = 0x80B;
    public const uint KarmaPerkVeryGoodId = 0x80C;

    public const uint FactFirstId = 0x810, FactListId = 0x81F;
    public const uint FameAvFirstId = 0x820, FameAvListId = 0x82F;
    public const uint InfamyAvFirstId = 0x830, InfamyAvListId = 0x83F;
    public const uint StateAvFirstId = 0x840, StateAvListId = 0x84F;
    public const uint FameGlobFirstId = 0x850, FameGlobListId = 0x85F;
    public const uint InfamyGlobFirstId = 0x860, InfamyGlobListId = 0x86F;
    public const uint StateGlobFirstId = 0x870, StateGlobListId = 0x87F;

    public const uint CharityTokenId = 0x880;
    public const uint TheftTokenId = 0x881;
    public const uint FactionAidTokenId = 0x882;
    public const uint FactionCrimeTokenId = 0x883;
    public const uint AidTokenId = 0x882;
    public const uint CrimeTokenId = 0x883;
    public const uint VendorNpcId = 0x888;
    public const uint RepTokenListId = 0x88F;

    public const uint RepTestCellId = 0x890;
    public const uint CocRefId = 0x891;
    public const uint ArrivalRefId = 0x892;
    public const uint VendorNpcRefId = 0x893;

    public const string QuestEdid = "FO4SF_ReputationQuest";
    public const string ScriptName = "FO4SF_ReputationQuest";
    public const string QuestScript = ScriptName;
    public const string EndingMoralSlideGlobEdid = "FO4SF_EndingMoralSlide";
    public const string VendorBuyMultAvEdid = "FO4SF_VendorBuyMult";
    public const string RepVendorPerkEdid = "FO4SF_RepVendorPerk";
    public const string CompanionMoralGlobEdid = "FO4SF_CompanionMoralReaction";
    public const string KarmaPerkVeryEvilEdid = "FO4SF_KarmaTag_VeryEvil";
    public const string KarmaPerkEvilEdid = "FO4SF_KarmaTag_Evil";
    public const string KarmaPerkNeutralEdid = "FO4SF_KarmaTag_Neutral";
    public const string KarmaPerkGoodEdid = "FO4SF_KarmaTag_Good";
    public const string KarmaPerkVeryGoodEdid = "FO4SF_KarmaTag_VeryGood";
    public const string CharityTokenEdid = "FO4SF_CharityToken";
    public const string TheftTokenEdid = "FO4SF_TheftToken";
    public const string AidTokenEdid = "FO4SF_FactionAidToken";
    public const string CrimeTokenEdid = "FO4SF_FactionCrimeToken";
    public const string RepTokenListEdid = "FO4SF_RepTokenList";
    public const string RepTestCellEdid = "FO4SF_RepTestCell";
    public const string VendorNpcEdid = "FO4SF_RepVendorNpc";

    const string PlayerFactionEdid = "PlayerFaction",
        TokenTemplateMiscEdid = "Digipick",
        NpcTemplateEdid = "EncShip_UCCitizen_F02_AutopilotAI";

    static readonly string[] CoreFactionKeys =
    {
        "Minutemen",
        "Brotherhood",
        "Railroad",
        "Institute",
        "Settlers",
        "NCR",
        "Legion",
        "Outlaws",
    };

    // Exact 13 FalloutNV.esm REPU EDIDs in fnv_slot 0..12 order
    static readonly string[] FnvSlotKeys =
    {
        "RepNVPrimm",
        "RepNVCaesarsLegion",
        "RepNVNCR",
        "RepNVBoomer",
        "RepNVGoodsprings",
        "RepNVWhiteGloveSociety",
        "RepNVTheStrip",
        "RepNVGreatKhans",
        "RepNVBrotherhood",
        "RepNVFollowers",
        "RepNVNovac",
        "RepNVFreeside",
        "RepNVPowderGanger",
    };

    static readonly (uint Id, string Edid, string Label, string Desc)[] KarmaTagPerks =
    {
        (KarmaPerkVeryEvilId, "FO4SF_KarmaTag_VeryEvil", "Karma: Very Evil", "Moral standing is Very Evil (<= -750)."),
        (KarmaPerkEvilId, "FO4SF_KarmaTag_Evil", "Karma: Evil", "Moral standing is Evil (-749..-250)."),
        (KarmaPerkNeutralId, "FO4SF_KarmaTag_Neutral", "Karma: Neutral", "Moral standing is Neutral (-249..+249)."),
        (KarmaPerkGoodId, "FO4SF_KarmaTag_Good", "Karma: Good", "Moral standing is Good (+250..+749)."),
        (KarmaPerkVeryGoodId, "FO4SF_KarmaTag_VeryGood", "Karma: Very Good", "Moral standing is Very Good (>= +750)."),
    };

    static readonly (uint Id, string Edid, string Label)[] TokenSpecs =
    {
        (CharityTokenId, CharityTokenEdid, "FO4SF Charity Deed Token"),
        (TheftTokenId, TheftTokenEdid, "FO4SF Stolen Ledger Token"),
        (FactionAidTokenId, AidTokenEdid, "FO4SF Faction Aid Commendation"),
        (FactionCrimeTokenId, CrimeTokenEdid, "FO4SF Faction Crime Warrant"),
    };

    static readonly ushort[] QuestStages = { 10, 20, 30, 40, 50, 60 };

    // Proven TestCell vanilla statics/lights/templates
    const uint FloorStat = 0x050776, OmniLight = 0x03D38C, CocMarker = 0x000032, XMarker = 0x00003B,
        LightingTemplate = 0x006658, ImageSpace = 0x122393;
    const float TileStep = 8f, LightZ = 4f;

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

    static string[] SlotKeysFor(int slotCount)
    {
        if (slotCount < 1 || slotCount > 15)
            throw new Refusal($"slotCount must be in 1..15, got {slotCount}");
        if (slotCount == 13)
            return FnvSlotKeys;
        if (slotCount <= CoreFactionKeys.Length)
            return CoreFactionKeys.Take(slotCount).ToArray();
        var list = CoreFactionKeys.ToList();
        for (int i = CoreFactionKeys.Length; i < slotCount; i++)
            list.Add($"Slot_{i:D2}");
        return list.ToArray();
    }

    static Cache<IModMasterStyledGetter, ModKey> MasterStyles()
    {
        var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        styles.Set(new KeyedMasterStyle(SfEsm, MasterStyle.Full));
        styles.Set(new KeyedMasterStyle(CoreValuesEsm, MasterStyle.Full));
        styles.Set(new KeyedMasterStyle(Plugin, MasterStyle.Full));
        return styles;
    }

    static IStarfieldModDisposableGetter OpenTemplate(string path) =>
        StarfieldMod.CreateFromBinaryOverlay(path, Release, new BinaryReadParameters { MasterFlagsLookup = MasterStyles() });

    static T One<T>(IEnumerable<T> items, string edid, string what) where T : IMajorRecordGetter
    {
        var hits = items.Where(x => string.Equals(x.EditorID, edid, StringComparison.OrdinalIgnoreCase)).ToList();
        if (hits.Count != 1) throw new Refusal($"{hits.Count} {what} named {edid} in Starfield.esm (one needed)");
        return hits[0];
    }

    static Global MakeGlob(uint id, string edid, float initial)
        => new(Own(id), Release) { EditorID = edid, Data = initial, FormVersion = 581, Version2 = 4 };

    static ScriptObjectProperty ObjProp(string name, FormKey fk) => new()
    {
        Name = name,
        Flags = ScriptProperty.Flag.Edited,
        Object = new FormLink<IStarfieldMajorRecordGetter>(fk),
    };

    static ScriptObjectListProperty ObjListProp(string name, IEnumerable<FormKey> keys)
    {
        var lp = new ScriptObjectListProperty { Name = name, Flags = ScriptProperty.Flag.Edited };
        foreach (var k in keys) lp.Objects.Add(ObjProp("", k));
        return lp;
    }

    // ---------------------------------------------------------------- build

    public static int Build(string templatePath, string outDir, BuildOptions? opts = null)
    {
        opts ??= new BuildOptions(DefaultJsonPath(), 8, false);
        var core = LoadCoreValues(opts.JsonPath);
        var karmaAvKey = RequireCore(core, "FO4SF_Karma");
        var karmaValGlobKey = RequireCore(core, "FO4SF_KarmaValue");
        var karmaTierGlobKey = RequireCore(core, "FO4SF_KarmaTier");
        var testModeGlobKey = RequireCore(core, "FO4SF_TestModeEnabled");
        var slotKeys = SlotKeysFor(opts.SlotCount);

        using var sf = OpenTemplate(templatePath);
        var playerFaction = One(sf.Factions, PlayerFactionEdid, "FACT");
        var miscTmpl = One(sf.MiscItems, TokenTemplateMiscEdid, "MISC");
        var npcTmpl = One(sf.Npcs, NpcTemplateEdid, "NPC_");

        var mod = new StarfieldMod(Plugin, Release);
        mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        mod.ModHeader.Author = "fo4-to-starfield";

        // 1. Moral Slide + Vendor Buy Mult AVIF + Companion Moral Reaction Global (Karma lives in FO4SFCoreValues.esm)
        mod.Globals.Add(MakeGlob(EndingMoralSlideGlobId, EndingMoralSlideGlobEdid, 2f));
        mod.ActorValueInformation.Add(new ActorValueInformation(Own(VendorBuyMultAvId), Release)
        {
            EditorID = VendorBuyMultAvEdid,
            Name = "FO4SF Vendor Buy Price Multiplier",
            Type = ActorValueInformation.Types.Variable,
            DefaultValue = 1.0f,
            Min = 0.25f,
            Max = 2.0f,
        });
        mod.Globals.Add(MakeGlob(CompanionMoralGlobId, CompanionMoralGlobEdid, 0f));

        // 2. Vendor Price Modifier Perk (0x806) with per-slot target merchant GetInFaction conditions & 5 Karma Tag Perks
        var vendorEffect = new PerkEntryPointModifyActorValue
        {
            EntryPoint = APerkEntryPointEffect.EntryType.ModBuyPrices,
            PerkConditionTabCount = 2,
            ActorValue = new FormLink<IActorValueInformationGetter>(Own(VendorBuyMultAvId)),
            Value = 1.0f,
            Modification = PerkEntryPointModifyActorValue.ModificationType.MultiplyAVMult,
        };
        var merchantTabCond = new PerkCondition { RunOnTabIndex = 1 };
        for (uint i = 0; i < (uint)slotKeys.Length; i++)
        {
            var gif = new GetInFactionConditionData { RunOnType = Condition.RunOnType.Subject };
            gif.FirstParameter.Link.SetTo(Own(FactFirstId + i));
            merchantTabCond.Conditions.Add(new ConditionFloat
            {
                CompareOperator = CompareOperator.EqualTo,
                ComparisonValue = 1f,
                Flags = i + 1 < (uint)slotKeys.Length ? Condition.Flag.OR : 0,
                Data = gif,
            });
        }
        vendorEffect.Conditions.Add(merchantTabCond);

        var vendorPerk = new Perk(Own(RepVendorPerkId), Release)
        {
            EditorID = RepVendorPerkEdid,
            Name = "FO4SF Faction Vendor Standing",
            Description = "Adjusts faction vendor buy prices from standing independently of global Karma.",
            Flags = Perk.Flag.PcPlayable,
            FormVersion = 581,
            Version2 = 11,
        };
        var vendorRank = new PerkRank { Description = "Active faction vendor standing modifier." };
        vendorRank.Effects.Add(vendorEffect);
        vendorPerk.Ranks.Add(vendorRank);
        mod.Perks.Add(vendorPerk);

        foreach (var (pid, pedid, plabel, pdesc) in KarmaTagPerks)
        {
            var kp = new Perk(Own(pid), Release)
            {
                EditorID = pedid,
                Name = plabel,
                Description = pdesc,
                Flags = 0, // G6 fix: never set PcTrait or PcPlayable (prevents appearing in Starfield ChargenMenu trait list)
                FormVersion = 581,
                Version2 = 11,
            };
            kp.Ranks.Add(new PerkRank { Description = pdesc });
            mod.Perks.Add(kp);
        }

        // 3. Configurable N Factions (0x810..0x810+N-1) + Per-Faction Fame/Infamy/State AVIFs & GLOBs + 7 FormLists
        var factList = new FormList(Own(FactListId), Release) { EditorID = "FO4SF_RepFactList" };
        var fameAvList = new FormList(Own(FameAvListId), Release) { EditorID = "FO4SF_FameAvList" };
        var infamyAvList = new FormList(Own(InfamyAvListId), Release) { EditorID = "FO4SF_InfamyAvList" };
        var stateAvList = new FormList(Own(StateAvListId), Release) { EditorID = "FO4SF_RepStateAvList" };
        var fameGlobList = new FormList(Own(FameGlobListId), Release) { EditorID = "FO4SF_FameGlobList" };
        var infamyGlobList = new FormList(Own(InfamyGlobListId), Release) { EditorID = "FO4SF_InfamyGlobList" };
        var stateGlobList = new FormList(Own(StateGlobListId), Release) { EditorID = "FO4SF_StateGlobList" };

        for (uint i = 0; i < (uint)slotKeys.Length; i++)
        {
            string key = slotKeys[i];
            uint factId = FactFirstId + i;
            uint fameAvId = FameAvFirstId + i;
            uint infAvId = InfamyAvFirstId + i;
            uint stAvId = StateAvFirstId + i;
            uint fameGlId = FameGlobFirstId + i;
            uint infGlId = InfamyGlobFirstId + i;
            uint stGlId = StateGlobFirstId + i;

            var fac = new Faction(Own(factId), Release)
            {
                EditorID = $"FO4SF_RepFact_{key}",
                Name = $"FO4SF {key}",
            };
            fac.Relations.Add(new Relation
            {
                Target = new FormLink<IRelatableGetter>(playerFaction.FormKey),
                Reaction = CombatReaction.Neutral,
            });
            mod.Factions.Add(fac);
            factList.Items.Add(new FormLink<IStarfieldMajorRecordGetter>(Own(factId)));

            mod.ActorValueInformation.Add(new ActorValueInformation(Own(fameAvId), Release)
            {
                EditorID = $"FO4SF_Fame_{key}",
                Name = $"FO4SF {key} Fame",
                Type = ActorValueInformation.Types.Variable,
                Flags = ActorValueInformation.Flag.DefaultToZero,
                DefaultValue = 0f,
                Min = 0f,
                Max = 100f,
            });
            fameAvList.Items.Add(new FormLink<IStarfieldMajorRecordGetter>(Own(fameAvId)));

            mod.ActorValueInformation.Add(new ActorValueInformation(Own(infAvId), Release)
            {
                EditorID = $"FO4SF_Infamy_{key}",
                Name = $"FO4SF {key} Infamy",
                Type = ActorValueInformation.Types.Variable,
                Flags = ActorValueInformation.Flag.DefaultToZero,
                DefaultValue = 0f,
                Min = 0f,
                Max = 100f,
            });
            infamyAvList.Items.Add(new FormLink<IStarfieldMajorRecordGetter>(Own(infAvId)));

            mod.ActorValueInformation.Add(new ActorValueInformation(Own(stAvId), Release)
            {
                EditorID = $"FO4SF_RepState_{key}",
                Name = $"FO4SF {key} Standing Code",
                Type = ActorValueInformation.Types.Variable,
                Flags = ActorValueInformation.Flag.DefaultToZero,
                DefaultValue = 0f,
                Min = 0f,
                Max = 15f,
            });
            stateAvList.Items.Add(new FormLink<IStarfieldMajorRecordGetter>(Own(stAvId)));

            mod.Globals.Add(MakeGlob(fameGlId, $"FO4SF_FameGlob_{key}", 0f));
            fameGlobList.Items.Add(new FormLink<IStarfieldMajorRecordGetter>(Own(fameGlId)));

            mod.Globals.Add(MakeGlob(infGlId, $"FO4SF_InfamyGlob_{key}", 0f));
            infamyGlobList.Items.Add(new FormLink<IStarfieldMajorRecordGetter>(Own(infGlId)));

            mod.Globals.Add(MakeGlob(stGlId, $"FO4SF_StateGlob_{key}", 0f));
            stateGlobList.Items.Add(new FormLink<IStarfieldMajorRecordGetter>(Own(stGlId)));
        }

        // 4. Console-Free Field Walk Tokens (0x880..0x883) + Token Filter FormList (0x88F)
        var repTokenList = new FormList(Own(RepTokenListId), Release) { EditorID = RepTokenListEdid };
        foreach (var (tid, tedid, tlabel) in TokenSpecs)
        {
            var tok = (MiscItem)miscTmpl.Duplicate(Own(tid));
            tok.EditorID = tedid;
            tok.Name = tlabel;
            tok.VirtualMachineAdapter = null;
            tok.Value = 10;
            tok.Weight = 0f;
            mod.MiscItems.Add(tok);
            repTokenList.Items.Add(new FormLink<IStarfieldMajorRecordGetter>(Own(tid)));
        }

        foreach (var fl in new[] { factList, fameAvList, infamyAvList, stateAvList, fameGlobList, infamyGlobList, stateGlobList, repTokenList })
            mod.FormLists.Add(fl);

        // 5. Optional Faction Vendor NPC (0x888) & Interior Test Room CELL FO4SF_RepTestCell (0x890)
        uint nextId = RepTestCellId;
        if (!opts.NoTestCell)
        {
            var vendorNpc = (Npc)npcTmpl.Duplicate(Own(VendorNpcId));
            vendorNpc.EditorID = VendorNpcEdid;
            vendorNpc.Name = "FO4SF Faction Quartermaster";
            vendorNpc.VirtualMachineAdapter = null;
            vendorNpc.Flags = (vendorNpc.Flags | Npc.Flag.Essential | Npc.Flag.Unique) & ~Npc.Flag.Respawn;
            vendorNpc.Factions.Clear();
            vendorNpc.Factions.Add(new RankPlacement { Faction = new FormLink<IFactionGetter>(Own(FactFirstId)), Rank = 0 });
            mod.Npcs.Add(vendorNpc);

            var cell = new Cell(Own(RepTestCellId), Release) { EditorID = RepTestCellEdid, Flags = Cell.Flag.IsInteriorCell };
            cell.LightingTemplate.SetTo(Sf(LightingTemplate));
            cell.ImageSpace.SetTo(Sf(ImageSpace));
            cell.EnvironmentMap = "Data\\Textures\\Cubemaps\\Cell_HiTechHallCube.dds";

            var zero = new P3Float(0f, 0f, 0f);
            PlacedObject MakeObjRef(uint id, FormKey b, P3Float pos, P3Float rot, string? edid = null, bool persistent = false)
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

            cell.Persistent.Add(MakeObjRef(ArrivalRefId, Sf(XMarker), new P3Float(-3.5f, 0f, 0.65f), new P3Float(0f, 0f, (float)(Math.PI / 2)), "FO4SF_RepTestArrival", persistent: true));
            var npcRef = new PlacedNpc(Own(VendorNpcRefId), Release)
            {
                EditorID = "FO4SF_RepVendorNpcRef",
                Base = new FormLink<INpcGetter>(Own(VendorNpcId)),
                Position = new P3Float(3f, 0f, 0.55f),
                Rotation = new P3Float(0f, 0f, -(float)(Math.PI / 2)),
            };
            npcRef.MajorRecordFlagsRaw |= 0x400;
            cell.Persistent.Add(npcRef);

            cell.Temporary.Add(MakeObjRef(CocRefId, Sf(CocMarker), new P3Float(-3.5f, 0f, 0.65f), new P3Float(0f, 0f, (float)(Math.PI / 2))));

            uint tokRefId = 0x894u;
            var tokenPlacements = new (uint BaseId, float X, float Y, string Edid)[]
            {
                (TheftTokenId, -1.5f, -2.0f, "FO4SF_TheftTokenRef01"),
                (TheftTokenId, -1.0f, -2.0f, "FO4SF_TheftTokenRef02"),
                (TheftTokenId, -0.5f, -2.0f, "FO4SF_TheftTokenRef03"),
                (CharityTokenId, 0.5f, -2.0f, "FO4SF_CharityTokenRef01"),
                (CharityTokenId, 1.0f, -2.0f, "FO4SF_CharityTokenRef02"),
                (CharityTokenId, 1.5f, -2.0f, "FO4SF_CharityTokenRef03"),
                (FactionAidTokenId, -1.0f, 2.0f, "FO4SF_FactionAidTokenRef01"),
                (FactionAidTokenId, -0.5f, 2.0f, "FO4SF_FactionAidTokenRef02"),
                (FactionCrimeTokenId, 0.5f, 2.0f, "FO4SF_FactionCrimeTokenRef01"),
                (FactionCrimeTokenId, 1.0f, 2.0f, "FO4SF_FactionCrimeTokenRef02"),
            };
            foreach (var (baseId, tx, ty, tedid) in tokenPlacements)
                cell.Temporary.Add(MakeObjRef(tokRefId++, Own(baseId), new P3Float(tx, ty, 0.2f), zero, tedid));

            nextId = 0x8B0u;
            for (float x = -TileStep; x <= TileStep; x += TileStep)
                for (float y = -TileStep; y <= TileStep; y += TileStep)
                    cell.Temporary.Add(MakeObjRef(nextId++, Sf(FloorStat), new P3Float(x, y, 0f), zero));
            for (float x = -4f; x <= 4f; x += 8f)
                for (float y = -4f; y <= 4f; y += 8f)
                    cell.Temporary.Add(MakeObjRef(nextId++, Sf(OmniLight), new P3Float(x, y, LightZ), zero));

            var cid = cell.FormKey.ID;
            var block = new CellBlock { BlockNumber = (int)(cid % 10), GroupType = GroupTypeEnum.InteriorCellBlock };
            var sub = new CellSubBlock { BlockNumber = (int)((cid / 10) % 10), GroupType = GroupTypeEnum.InteriorCellSubBlock };
            sub.Cells.Add(cell);
            block.SubBlocks.Add(sub);
            mod.Cells.Records.Add(block);
        }

        // 6. Quest FO4SF_ReputationQuest (0x800) with bound VMAD properties
        var quest = new Quest(Own(QuestId), Release)
        {
            EditorID = QuestEdid,
            Name = "FO4SF Karma and Faction Reputation",
            FormVersion = 581,
            Version2 = 12,
            Data = new QuestData { Flags = Quest.Flag.StartGameEnabled, Priority = 30 },
        };
        foreach (var st in QuestStages)
            quest.Stages.Add(new QuestStage { Index = st });

        FormKey Core(string edid) => RequireCore(core, edid);
        var se = new ScriptEntry { Name = ScriptName, Flags = ScriptEntry.Flag.Local };
        se.Properties.Add(ObjProp("KarmaAV", Core("FO4SF_Karma")));
        se.Properties.Add(ObjProp("KarmaValueGlob", Core("FO4SF_KarmaValue")));
        se.Properties.Add(ObjProp("KarmaTierGlob", Core("FO4SF_KarmaTier")));
        se.Properties.Add(ObjProp("TestModeGlobal", Core("FO4SF_TestModeEnabled")));
        se.Properties.Add(new ScriptIntProperty { Name = "FactionCount", Flags = ScriptProperty.Flag.Edited, Data = opts.SlotCount });
        se.Properties.Add(ObjProp("RepTokenList", Own(RepTokenListId)));
        se.Properties.Add(ObjProp("CharityToken", Own(CharityTokenId)));
        se.Properties.Add(ObjProp("TheftToken", Own(TheftTokenId)));
        se.Properties.Add(ObjProp("FactionAidToken", Own(AidTokenId)));
        se.Properties.Add(ObjProp("FactionCrimeToken", Own(CrimeTokenId)));
        se.Properties.Add(ObjProp("EndingSlideGlob", Own(EndingMoralSlideGlobId)));
        se.Properties.Add(ObjProp("VendorBuyMultAV", Own(VendorBuyMultAvId)));
        se.Properties.Add(ObjProp("RepVendorPerk", Own(RepVendorPerkId)));
        se.Properties.Add(ObjProp("CompanionMoralGlob", Own(CompanionMoralGlobId)));
        se.Properties.Add(ObjProp("PlayerFaction", playerFaction.FormKey));
        se.Properties.Add(ObjListProp("KarmaTagPerks", KarmaTagPerks.Select(k => Own(k.Id))));
        se.Properties.Add(ObjListProp("SlotFactions", Enumerable.Range(0, slotKeys.Length).Select(k => Own(FactFirstId + (uint)k))));
        se.Properties.Add(ObjListProp("SlotFameAVs", Enumerable.Range(0, slotKeys.Length).Select(k => Own(FameAvFirstId + (uint)k))));
        se.Properties.Add(ObjListProp("SlotInfamyAVs", Enumerable.Range(0, slotKeys.Length).Select(k => Own(InfamyAvFirstId + (uint)k))));
        se.Properties.Add(ObjListProp("SlotStateAVs", Enumerable.Range(0, slotKeys.Length).Select(k => Own(StateAvFirstId + (uint)k))));
        se.Properties.Add(ObjListProp("SlotFameGlobs", Enumerable.Range(0, slotKeys.Length).Select(k => Own(FameGlobFirstId + (uint)k))));
        se.Properties.Add(ObjListProp("SlotInfamyGlobs", Enumerable.Range(0, slotKeys.Length).Select(k => Own(InfamyGlobFirstId + (uint)k))));
        se.Properties.Add(ObjListProp("SlotStateGlobs", Enumerable.Range(0, slotKeys.Length).Select(k => Own(StateGlobFirstId + (uint)k))));
        if (!opts.NoTestCell)
            se.Properties.Add(ObjProp("VendorNpcRef", Own(VendorNpcRefId)));

        quest.VirtualMachineAdapter = new QuestAdapter
        {
            Version = 6,
            ObjectFormat = 2,
            ExtraBindDataVersion = 3,
            Script = new ScriptEntry { Name = "", Flags = ScriptEntry.Flag.Local },
        };
        quest.VirtualMachineAdapter.Scripts.Add(se);
        mod.Quests.Add(quest);

        mod.ModHeader.Stats.NextFormID = nextId;
        WritePlugin(mod, outDir, ExpectedMasters);
        var path = Path.Combine(outDir, Plugin.FileName);
        Console.WriteLine(
            $"wrote {Path.GetFileName(path)} ({new FileInfo(path).Length:N0} bytes): " +
            $"QUST {QuestEdid} (slots={opts.SlotCount}), {mod.Factions.Count} FACT, {mod.ActorValueInformation.Count} AVIF, " +
            $"{mod.Globals.Count} GLOB, {mod.Perks.Count} PERK, {mod.FormLists.Count} FLST, " +
            $"{mod.MiscItems.Count} MISC tokens, no_test_cell={opts.NoTestCell}");
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
            mod.BeginWrite.ToPath(tmp)
                .WithLoadOrder(masters)
                .WithKnownMasters(masters.Select(m => new KeyedMasterStyle(m, MasterStyle.Full)).ToArray())
                .Write();
            File.Move(tmp, path, overwrite: true);
        }
        finally
        {
            if (Directory.Exists(tmpDir)) Directory.Delete(tmpDir, true);
        }
    }

    // ---------------------------------------------------------------- check

    public static int Check(string pluginPath, string templatePath, BuildOptions? opts = null)
    {
        opts ??= new BuildOptions(DefaultJsonPath(), 8, false);
        var core = LoadCoreValues(opts.JsonPath);
        var karmaAvKey = RequireCore(core, "FO4SF_Karma");
        var karmaValGlobKey = RequireCore(core, "FO4SF_KarmaValue");
        var karmaTierGlobKey = RequireCore(core, "FO4SF_KarmaTier");
        var testModeGlobKey = RequireCore(core, "FO4SF_TestModeEnabled");
        var slotKeys = SlotKeysFor(opts.SlotCount);

        using var sf = OpenTemplate(templatePath);
        var playerFaction = One(sf.Factions, PlayerFactionEdid, "FACT");
        using var mod = StarfieldMod.CreateFromBinaryOverlay(pluginPath, Release, new BinaryReadParameters { MasterFlagsLookup = MasterStyles() });

        var problems = new List<string>();
        void Need(bool ok, string what) { if (!ok) problems.Add(what); }

        var masters = mod.ModHeader.MasterReferences.Select(m => m.Master).ToList();
        Console.WriteLine($"{Path.GetFileName(pluginPath)}: header {mod.ModHeader.Flags}, masters [{string.Join(", ", masters)}], next 0x{mod.ModHeader.Stats.NextFormID:X}");
        Need(mod.ModKey == Plugin, $"plugin ModKey is {mod.ModKey}, expected {Plugin}");
        Need(mod.ModHeader.Flags.HasFlag(StarfieldModHeader.HeaderFlag.Master), "plugin header lacks Master flag");
        Need(masters.SequenceEqual(ExpectedMasters), $"masters [{string.Join(", ", masters)}] != [{string.Join(", ", ExpectedMasters)}]");

        // Zero foreign overrides and zero duplicate EditorIDs with FO4SFCoreValues.esm
        var foreign = mod.EnumerateMajorRecords()
            .Where(r => r.FormKey.ModKey != Plugin)
            .Select(r => $"{r.GetType().Name}:{r.FormKey}")
            .ToList();
        Need(foreign.Count == 0, $"unexpected foreign record overrides: {string.Join(", ", foreign)}");
        var dupEdids = mod.EnumerateMajorRecords()
            .Where(r => !string.IsNullOrEmpty(r.EditorID) && core.ContainsKey(r.EditorID))
            .Select(r => r.EditorID!)
            .ToList();
        Need(dupEdids.Count == 0, $"duplicate EditorIDs with FO4SFCoreValues.esm: {string.Join(", ", dupEdids)}");

        // Verify Quest & VMAD properties
        var quest = mod.Quests.FirstOrDefault(q => q.FormKey == Own(QuestId));
        Need(quest != null && quest.EditorID == QuestEdid && quest.Data != null && quest.Data.Flags.HasFlag(Quest.Flag.StartGameEnabled),
            $"missing StartGameEnabled QUST {QuestEdid}");
        if (quest != null)
        {
            Need(quest.Stages.Select(s => s.Index).SequenceEqual(QuestStages), $"{QuestEdid} stages != [{string.Join(",", QuestStages)}]");
            var script = quest.VirtualMachineAdapter?.Scripts.FirstOrDefault();
            Need(script != null && script.Name == QuestScript, $"{QuestEdid} missing script {QuestScript}");
            if (script != null)
            {
                FormKey PropObj(string name) =>
                    (script.Properties.FirstOrDefault(p => p.Name == name) as IScriptObjectPropertyGetter)?.Object.FormKey ?? FormKey.Null;
                Need(PropObj("KarmaAV") == karmaAvKey, "KarmaAV not bound to FO4SFCoreValues.esm:0x830");
                Need(PropObj("KarmaValueGlob") == karmaValGlobKey, "KarmaValueGlob not bound to FO4SFCoreValues.esm:0x831");
                Need(PropObj("KarmaTierGlob") == karmaTierGlobKey, "KarmaTierGlob not bound to FO4SFCoreValues.esm:0x832");
                Need(PropObj("TestModeGlobal") == testModeGlobKey, "TestModeGlobal not bound to FO4SFCoreValues.esm:0x860");
                Need(PropObj("RepTokenList") == Own(RepTokenListId), "RepTokenList not bound to 0x88F");
                var fcProp = script.Properties.FirstOrDefault(p => p.Name == "FactionCount") as IScriptIntPropertyGetter;
                Need(fcProp != null && fcProp.Data == opts.SlotCount, $"FactionCount property != {opts.SlotCount}");
            }
        }

        // Verify AVIFs (1 vendor + 3*N faction)
        int wantAvifs = 1 + 3 * slotKeys.Length;
        var avifs = mod.ActorValueInformation.ToDictionary(a => a.FormKey);
        Need(avifs.Count == wantAvifs, $"expected {wantAvifs} AVIF records, found {avifs.Count}");
        Need(!avifs.ContainsKey(Own(0x801)), "removed duplicate 0x801 FO4SF_RepKarma still present");
        Need(avifs.TryGetValue(Own(VendorBuyMultAvId), out var vendorAv) && vendorAv.EditorID == VendorBuyMultAvEdid && Math.Abs((vendorAv.DefaultValue ?? 0f) - 1.0f) < 1e-4f,
            $"missing or invalid {VendorBuyMultAvEdid}");

        // Verify Globals (2 core + 3*N faction, all non-constant)
        int wantGlobs = 2 + 3 * slotKeys.Length;
        var globs = mod.Globals.ToDictionary(g => g.FormKey);
        Need(globs.Count == wantGlobs, $"expected {wantGlobs} GLOB records, found {globs.Count}");
        Need(globs.Values.All(g => !g.MajorFlags.HasFlag(Global.MajorFlag.Constant)), "one or more GLOB records are flagged Constant");
        Need(!globs.ContainsKey(Own(0x802)) && !globs.ContainsKey(Own(0x803)), "removed duplicate 0x802/0x803 Karma GLOBs still present");
        Need(globs.TryGetValue(Own(EndingMoralSlideGlobId), out var es) && es.EditorID == EndingMoralSlideGlobEdid && Math.Abs((es.Data ?? 0f) - 2f) < 1e-4f,
            $"missing or invalid {EndingMoralSlideGlobEdid}");
        Need(globs.TryGetValue(Own(CompanionMoralGlobId), out var cm) && cm.EditorID == CompanionMoralGlobEdid, $"missing {CompanionMoralGlobEdid}");

        // Verify Perks (1 vendor price perk with per-slot GetInFaction merchant gating + 5 Karma tag perks = 6)
        var perks = mod.Perks.ToDictionary(p => p.FormKey);
        Need(perks.Count == 6, $"expected 6 PERK records, found {perks.Count}");
        Need(perks.TryGetValue(Own(RepVendorPerkId), out var vp) && vp.EditorID == RepVendorPerkEdid && vp.Ranks.Count == 1 && vp.Ranks[0].Effects.Count == 1,
            $"missing or invalid {RepVendorPerkEdid}");
        if (vp != null && vp.Ranks.Count == 1 && vp.Ranks[0].Effects.Count == 1)
        {
            var tab1 = vp.Ranks[0].Effects[0].Conditions.FirstOrDefault(pc => pc.RunOnTabIndex == 1);
            var wantFacts = Enumerable.Range(0, slotKeys.Length).Select(k => Own(FactFirstId + (uint)k)).ToList();
            var gotFacts = tab1?.Conditions
                .Select(c => (c.Data as IGetInFactionConditionDataGetter)?.FirstParameter.Link.FormKey ?? FormKey.Null)
                .ToList() ?? new List<FormKey>();
            Need(gotFacts.SequenceEqual(wantFacts), $"{RepVendorPerkEdid} lacks per-slot merchant GetInFaction conditions");
        }
        foreach (var (pid, pedid, _, _) in KarmaTagPerks)
        {
            Need(perks.TryGetValue(Own(pid), out var kp) && kp.EditorID == pedid, $"missing Karma tag PERK {pedid}");
            if (kp != null)
            {
                Need(!kp.Flags.HasFlag(Perk.Flag.PcTrait) && !kp.Flags.HasFlag(Perk.Flag.PcPlayable),
                    $"Karma tag PERK {pedid} must not set PcTrait or PcPlayable (ChargenMenu trait leak)");
            }
        }

        // Verify N Core Factions & 8 FormLists (7 faction + 1 RepTokenList)
        var facts = mod.Factions.ToDictionary(f => f.FormKey);
        Need(facts.Count == slotKeys.Length, $"expected {slotKeys.Length} FACT records, found {facts.Count}");
        var flsts = mod.FormLists.ToDictionary(fl => fl.FormKey);
        Need(flsts.Count == 8, $"expected 8 FLST records, found {flsts.Count}");

        for (uint i = 0; i < (uint)slotKeys.Length; i++)
        {
            string key = slotKeys[i];
            Need(facts.TryGetValue(Own(FactFirstId + i), out var fac) && fac.EditorID == $"FO4SF_RepFact_{key}" &&
                 fac.Relations.Any(r => r.Target.FormKey == playerFaction.FormKey),
                $"missing or invalid FACT FO4SF_RepFact_{key}");
            Need(avifs.TryGetValue(Own(FameAvFirstId + i), out var fa) && fa.EditorID == $"FO4SF_Fame_{key}" && fa.Min == 0f && fa.Max == 100f,
                $"missing AVIF FO4SF_Fame_{key}");
            Need(avifs.TryGetValue(Own(InfamyAvFirstId + i), out var ia) && ia.EditorID == $"FO4SF_Infamy_{key}" && ia.Min == 0f && ia.Max == 100f,
                $"missing AVIF FO4SF_Infamy_{key}");
            Need(avifs.TryGetValue(Own(StateAvFirstId + i), out var sa) && sa.EditorID == $"FO4SF_RepState_{key}" && sa.Min == 0f && sa.Max == 15f,
                $"missing AVIF FO4SF_RepState_{key}");
            Need(globs.ContainsKey(Own(FameGlobFirstId + i)) && globs.ContainsKey(Own(InfamyGlobFirstId + i)) && globs.ContainsKey(Own(StateGlobFirstId + i)),
                $"missing faction GLOBs for {key}");
        }

        void CheckFlst(uint listId, uint firstItemId, string name)
        {
            var want = Enumerable.Range(0, slotKeys.Length).Select(k => Own(firstItemId + (uint)k)).ToList();
            Need(flsts.TryGetValue(Own(listId), out var fl) && fl.Items.Select(x => x.FormKey).SequenceEqual(want),
                $"FLST {name} (0x{listId:X}) items do not match expected {slotKeys.Length}-slot order");
        }
        CheckFlst(FactListId, FactFirstId, "FO4SF_RepFactList");
        CheckFlst(FameAvListId, FameAvFirstId, "FO4SF_FameAvList");
        CheckFlst(InfamyAvListId, InfamyAvFirstId, "FO4SF_InfamyAvList");
        CheckFlst(StateAvListId, StateAvFirstId, "FO4SF_RepStateAvList");
        CheckFlst(FameGlobListId, FameGlobFirstId, "FO4SF_FameGlobList");
        CheckFlst(InfamyGlobListId, InfamyGlobFirstId, "FO4SF_InfamyGlobList");
        CheckFlst(StateGlobListId, StateGlobFirstId, "FO4SF_StateGlobList");

        var wantTokItems = TokenSpecs.Select(t => Own(t.Id)).ToList();
        Need(flsts.TryGetValue(Own(RepTokenListId), out var tokFlst) && tokFlst.EditorID == RepTokenListEdid &&
             tokFlst.Items.Select(x => x.FormKey).SequenceEqual(wantTokItems),
            $"missing or invalid FLST {RepTokenListEdid} (0x{RepTokenListId:X})");

        // Verify Tokens, Vendor NPC, and Test Cell
        var miscs = mod.MiscItems.ToDictionary(m => m.FormKey);
        Need(miscs.Count == TokenSpecs.Length, $"expected {TokenSpecs.Length} MISC token records, found {miscs.Count}");
        foreach (var (tid, tedid, _) in TokenSpecs)
            Need(miscs.TryGetValue(Own(tid), out var tk) && tk.EditorID == tedid, $"missing MISC token {tedid}");

        var cells = mod.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells).ToList();
        if (opts.NoTestCell)
        {
            Need(cells.Count == 0, $"expected 0 CELL under --no-test-cell, found {cells.Count}");
            Need(mod.Npcs.Count == 0, $"expected 0 NPC_ under --no-test-cell, found {mod.Npcs.Count}");
        }
        else
        {
            var vnpc = mod.Npcs.FirstOrDefault(n => n.FormKey == Own(VendorNpcId));
            Need(vnpc != null && vnpc.EditorID == VendorNpcEdid && vnpc.Factions.Any(f => f.Faction.FormKey == Own(FactFirstId)),
                $"missing or invalid NPC_ {VendorNpcEdid}");

            var cell = cells.FirstOrDefault(c => c.FormKey == Own(RepTestCellId));
            Need(cell != null && cell.EditorID == RepTestCellEdid, $"missing CELL {RepTestCellEdid}");
            if (cell != null)
            {
                Need(cell.Persistent.Any(r => r.FormKey == Own(ArrivalRefId) && (r.MajorRecordFlagsRaw & 0x400) != 0), "missing persistent arrival XMarker");
                Need(cell.Persistent.Any(r => r.FormKey == Own(VendorNpcRefId) && (r.MajorRecordFlagsRaw & 0x400) != 0), "missing persistent vendor NPC ref");
                Need(cell.Temporary.Count >= 10, "missing placed walk tokens / tiles in FO4SF_RepTestCell");
            }
        }

        if (problems.Count > 0)
        {
            foreach (var p in problems) Console.Error.WriteLine("check failed: " + p);
            return 1;
        }
        Console.WriteLine($"check ok: {Plugin.FileName} verified (0 overrides, {slotKeys.Length} FACTs, {wantAvifs} AVIFs, {wantGlobs} GLOBs, 6 PERKs, 8 FLSTs, no_test_cell={opts.NoTestCell})");
        return 0;
    }

    // ---------------------------------------------------------------- fixture & selftest

    public static int Fixture(string outDir)
    {
        var mod = new StarfieldMod(SfEsm, Release);
        mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;

        mod.Factions.Add(new Faction(Sf(0x01C21C), Release) { EditorID = PlayerFactionEdid });
        mod.MiscItems.Add(new MiscItem(Sf(0x00080A), Release) { EditorID = TokenTemplateMiscEdid, Value = 35, Weight = 0f });
        mod.Npcs.Add(new Npc(Sf(0x0189BA), Release) { EditorID = NpcTemplateEdid });

        Directory.CreateDirectory(outDir);
        var sfPath = Path.Combine(outDir, "Starfield.esm");
        mod.BeginWrite.ToPath(sfPath).WithNoLoadOrder().Write();
        Console.WriteLine($"wrote synthetic {Path.GetFileName(sfPath)}");
        return 0;
    }

    public static int SelfTest(string scratchDir)
    {
        if (Directory.Exists(scratchDir)) Directory.Delete(scratchDir, true);
        Directory.CreateDirectory(scratchDir);
        var fixDir = Path.Combine(scratchDir, "fixture");
        var outOmitted = Path.Combine(scratchDir, "out_omitted");
        var outSlot8 = Path.Combine(scratchDir, "out_slot8");
        var outSlot13 = Path.Combine(scratchDir, "out_slot13");
        var outPlayer = Path.Combine(scratchDir, "out_player");

        if (Fixture(fixDir) != 0) return 1;
        var sfPath = Path.Combine(fixDir, "Starfield.esm");
        var jsonPath = DefaultJsonPath();

        // 1. Default omitted --slot-count vs explicit --slot-count 8 MUST be byte-identical
        if (Build(sfPath, outOmitted) != 0) return 1;
        var slot8Opts = new BuildOptions(jsonPath, SlotCount: 8, NoTestCell: false);
        if (Build(sfPath, outSlot8, slot8Opts) != 0) return 1;
        var pluginPath = Path.Combine(outOmitted, Plugin.FileName);
        var slot8Path = Path.Combine(outSlot8, Plugin.FileName);
        if (!File.ReadAllBytes(pluginPath).SequenceEqual(File.ReadAllBytes(slot8Path)))
            throw new Refusal("selftest failed: omitted --slot-count and --slot-count 8 builds are not byte-identical");
        if (Check(pluginPath, sfPath, slot8Opts) != 0) return 1;

        // 2. --slot-count 13 (13 FalloutNV.esm REPU slots) builds and passes Check
        var slot13Opts = new BuildOptions(jsonPath, SlotCount: 13, NoTestCell: false);
        if (Build(sfPath, outSlot13, slot13Opts) != 0) return 1;
        var slot13Path = Path.Combine(outSlot13, Plugin.FileName);
        if (Check(slot13Path, sfPath, slot13Opts) != 0) return 1;
        if (Check(slot13Path, sfPath, slot8Opts) == 0)
            throw new Refusal("selftest failed: 8-slot Check accepted 13-slot plugin");

        // 3. --no-test-cell builds and passes Check (and cross-mode Check rejects mismatch)
        var playerOpts = new BuildOptions(jsonPath, SlotCount: 8, NoTestCell: true);
        if (Build(sfPath, outPlayer, playerOpts) != 0) return 1;
        var playerPath = Path.Combine(outPlayer, Plugin.FileName);
        if (Check(playerPath, sfPath, playerOpts) != 0) return 1;
        if (Check(pluginPath, sfPath, playerOpts) == 0)
            throw new Refusal("selftest failed: --no-test-cell Check accepted plugin with test cell");

        var styles = MasterStyles();

        // Negative 1: foreign override injected -> Check must fail
        var badForeign = Path.Combine(scratchDir, "bad_foreign");
        {
            var mut = StarfieldMod.CreateFromBinary(pluginPath, Release, new BinaryReadParameters { MasterFlagsLookup = styles });
            mut.Factions.Add(new Faction(Sf(0x01C21C), Release) { EditorID = PlayerFactionEdid });
            WritePlugin(mut, badForeign, ExpectedMasters);
            if (Check(Path.Combine(badForeign, Plugin.FileName), sfPath, slot8Opts) == 0)
                throw new Refusal("selftest failed: foreign override was not rejected");
        }

        // Negative 2: Constant flag set on a GLOB -> Check must fail
        var badGlob = Path.Combine(scratchDir, "bad_glob");
        {
            var mut = StarfieldMod.CreateFromBinary(pluginPath, Release, new BinaryReadParameters { MasterFlagsLookup = styles });
            mut.Globals.First().MajorFlags |= Global.MajorFlag.Constant;
            WritePlugin(mut, badGlob, ExpectedMasters);
            if (Check(Path.Combine(badGlob, Plugin.FileName), sfPath, slot8Opts) == 0)
                throw new Refusal("selftest failed: Constant GLOB was not rejected");
        }

        // Negative 3: Misordered FormList -> Check must fail
        var badFlst = Path.Combine(scratchDir, "bad_flst");
        {
            var mut = StarfieldMod.CreateFromBinary(pluginPath, Release, new BinaryReadParameters { MasterFlagsLookup = styles });
            var fl = mut.FormLists.First(x => x.FormKey == Own(FactListId));
            var tmp = fl.Items[0];
            fl.Items[0] = fl.Items[1];
            fl.Items[1] = tmp;
            WritePlugin(mut, badFlst, ExpectedMasters);
            if (Check(Path.Combine(badFlst, Plugin.FileName), sfPath, slot8Opts) == 0)
                throw new Refusal("selftest failed: misordered FLST was not rejected");
        }

        Console.WriteLine("selftest pass: byte-identical 8-slot, 13-slot FNV, --no-test-cell, and 3 negative tamper checks verified");
        return 0;
    }
}
