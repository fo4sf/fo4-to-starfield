// ProgressionCore: Player Creation & Progression Core plugin writer and checker (CF-6, docs/progression/progression-core.md).
//
// Writes FO4SFProgression.esm (masters Starfield.esm, FO4SFCoreValues.esm; adds records only, overrides none):
//   Shared AVIFs/FLSTs/Karma/TestMode live in FO4SFCoreValues.esm (loaded from src/fo4sf/core/core_values.json):
//     0x817 FLST FO4SF_SpecialAVList, 0x82D FLST FO4SF_SkillAVList,
//     0x830 AVIF FO4SF_Karma, 0x831 GLOB FO4SF_KarmaValue, 0x860 GLOB FO4SF_TestModeEnabled
//   Faction reputation lives solely in FO4SFReputation.esm (0x870+slotIndex FO4SF_StateGlob_<Key>).
//   Owned by FO4SFProgression.esm:
//     0x808        GLOB FO4SF_SpecialPool28            (0 = 40-pt NV default, 1 = 28-pt FO4 option)
//     0x809        GLOB FO4SF_PerkCadenceLevels        (default 2 = 1 Perk per 2 levels; runtime-tunable)
//     0x80A        GLOB FO4SF_QueuedPerkPoints         (0 default)
//     0x80B        GLOB FO4SF_TraitRespecUsed          (0 = exit respec available, 1 = used & locked)
//     0x80D        GLOB FO4SF_QueuedSkillPoints        (0 default)
//     0x820..0x828 PERK FO4SF_BG_*                     (9 Wasteland Backgrounds in FLST 0x82F)
//     0x830..0x838 PERK FO4SF_Trait_*                  (9 Trade-Off Traits in FLST 0x83F)
//     0x840..0x847 PERK FO4SF_Perk_*                   (8 Core Playable Perks in FLST 0x84F)
//     0x870..0x87B MESG FO4SF_Prog*Msg                 (12 Interactive Creation, Standard-Spread & Respec Message Menus, all <= 7 buttons)
//     0x880        QUST FO4SF_ProgressionQuest         (StartGameEnabled creation, lift menu stage 15, & TestMode harness stages)
//
// usage:
//   ProgressionCore build <Starfield.esm> <out dir> [--pool28 0|1] [--cadence <int>=2] [--json <core_values.json>]
//   ProgressionCore check <plugin> <Starfield.esm> [--pool28 0|1] [--cadence <int>=2] [--json <core_values.json>]
//   ProgressionCore fixture <out dir>
//   ProgressionCore selftest <scratch dir>

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
    int pool28 = 0;
    int cadence = 2;

    string? OptStr(string flag)
    {
        int i = rest.IndexOf(flag);
        if (i < 0) return null;
        if (i + 1 >= rest.Count) throw new ProgressionCore.Refusal($"{flag} needs a value");
        var v = rest[i + 1];
        rest.RemoveRange(i, 2);
        return v;
    }

    void OptInt(string flag, ref int dest, int minVal, int maxVal)
    {
        int i = rest.IndexOf(flag);
        if (i < 0) return;
        if (i + 1 >= rest.Count || !int.TryParse(rest[i + 1], NumberStyles.Integer, CultureInfo.InvariantCulture, out int v) || v < minVal || v > maxVal)
            throw new ProgressionCore.Refusal($"{flag} must be an integer in {minVal}..{maxVal}");
        dest = v;
        rest.RemoveRange(i, 2);
    }

    OptInt("--pool28", ref pool28, 0, 1);
    OptInt("--cadence", ref cadence, 1, 20);
    var jsonPath = OptStr("--json");

    if (rest.Count == 3 && rest[0] == "build") return ProgressionCore.Build(rest[1], rest[2], pool28, cadence, jsonPath);
    if (rest.Count == 3 && rest[0] == "check") return ProgressionCore.Check(rest[1], rest[2], pool28, cadence, jsonPath);
    if (rest.Count == 2 && rest[0] == "fixture") return ProgressionCore.Fixture(rest[1]);
    if (rest.Count == 2 && rest[0] == "selftest") return ProgressionCore.SelfTest(rest[1]);
}
catch (ProgressionCore.Refusal r)
{
    Console.Error.WriteLine("refused: " + r.Message);
    return 1;
}

Console.Error.WriteLine("usage: ProgressionCore build <Starfield.esm> <out dir> [--pool28 0|1] [--cadence <int>] [--json <core_values.json>] | " +
                        "check <plugin> <Starfield.esm> [same options] | fixture <out dir> | selftest <scratch dir>");
return 2;

public static class ProgressionCore
{
    public class Refusal(string m) : Exception(m);

    const StarfieldRelease Release = StarfieldRelease.Starfield;
    static readonly ModKey SfEsm = ModKey.FromFileName("Starfield.esm");
    static readonly ModKey CoreValuesEsm = ModKey.FromFileName("FO4SFCoreValues.esm");
    public static readonly ModKey Plugin = ModKey.FromFileName("FO4SFProgression.esm");

    public const int MaxMessageButtons = 7;

    public const uint Pool28GlobId = 0x808;
    public const uint CadenceGlobId = 0x809;
    public const uint QueuedPerkGlobId = 0x80A;
    public const uint RespecUsedGlobId = 0x80B;
    public const uint QueuedSkillGlobId = 0x80D;

    public const uint BgFlstId = 0x82F;
    public const uint TraitFlstId = 0x83F;
    public const uint PerkFlstId = 0x84F;

    public const uint SpecialPage1MsgId = 0x870;
    public const uint TagPage1MsgId = 0x871;
    public const uint TagPage2MsgId = 0x872;
    public const uint ProgBackgroundMsgId = 0x873;
    public const uint ProgBackgroundPage2MsgId = 0x874;
    public const uint ProgTraitsMsgId = 0x875;
    public const uint ProgTraitsPage2MsgId = 0x876;
    public const uint RespecRefusedMsgId = 0x877;
    public const uint SpecialPage2MsgId = 0x878;
    public const uint TagPage3MsgId = 0x879;
    public const uint ProgTraitsPage3MsgId = 0x87A;
    public const uint SpecialDefaultMsgId = 0x87B;

    public const string SpecialPage1MsgEdid = "FO4SF_ProgSpecialPage1Msg";
    public const string TagPage1MsgEdid = "FO4SF_ProgTagSkillsPage1Msg";
    public const string TagPage2MsgEdid = "FO4SF_ProgTagSkillsPage2Msg";
    public const string ProgBackgroundMsgEdid = "FO4SF_ProgBackgroundMsg";
    public const string ProgBackgroundPage2MsgEdid = "FO4SF_ProgBackgroundPage2Msg";
    public const string ProgTraitsMsgEdid = "FO4SF_ProgTraitsMsg";
    public const string ProgTraitsPage2MsgEdid = "FO4SF_ProgTraitsPage2Msg";
    public const string RespecRefusedMsgEdid = "FO4SF_ProgRespecRefusedMsg";
    public const string SpecialPage2MsgEdid = "FO4SF_ProgSpecialPage2Msg";
    public const string TagPage3MsgEdid = "FO4SF_ProgTagSkillsPage3Msg";
    public const string ProgTraitsPage3MsgEdid = "FO4SF_ProgTraitsPage3Msg";
    public const string SpecialDefaultMsgEdid = "FO4SF_ProgSpecialDefaultMsg";

    public const uint QuestId = 0x880;
    public const string QuestEdid = "FO4SF_ProgressionQuest";
    public const string ScriptName = "FO4SF_ProgressionQuest";
    public const uint NextId = 0x881;

    // Placeholder standard S.P.E.C.I.A.L. spreads summing to the active pool (40 or 28); the owner may change these values.
    public static readonly int[] StandardSpread40 = { 6, 5, 5, 6, 7, 6, 5 };
    public static readonly int[] StandardSpread28 = { 4, 4, 4, 4, 4, 4, 4 };

    const string SpecialAvListEdid = "FO4SF_SpecialAVList";
    const string SkillAvListEdid = "FO4SF_SkillAVList";
    const string KarmaAvEdid = "FO4SF_Karma";
    const string KarmaValueGlobEdid = "FO4SF_KarmaValue";
    const string TestModeGlobEdid = "FO4SF_TestModeEnabled";

    public static readonly (uint Id, string Edid, string Name, string Desc)[] Backgrounds =
    {
        (0x820, "FO4SF_BG_VaultDweller", "Vault Dweller", "Origin: Raised inside a sealed shelter (+10 Science, Medicine, Speech)."),
        (0x821, "FO4SF_BG_WastelandScavenger", "Wasteland Scavenger", "Origin: Ruin salvager (+10 Repair, Lockpick, Survival)."),
        (0x822, "FO4SF_BG_CaravanGuard", "Caravan Guard", "Origin: Trade-route escort (+10 Guns, Barter, Survival)."),
        (0x823, "FO4SF_BG_FieldMedic", "Field Medic", "Origin: Frontline trauma responder (+10 Medicine, Science, Survival)."),
        (0x824, "FO4SF_BG_BrotherhoodScribe", "Brotherhood Scribe", "Origin: Archival technologist (+10 Energy Weapons, Science, Repair)."),
        (0x825, "FO4SF_BG_EnclaveRemnant", "Enclave Remnant", "Origin: Pre-war enclave descendant (+10 Energy Weapons, Speech, Science)."),
        (0x826, "FO4SF_BG_TribalHunter", "Tribal Hunter", "Origin: Frontier tracker (+10 Melee Weapons, Sneak, Survival)."),
        (0x827, "FO4SF_BG_DesertRanger", "Desert Ranger", "Origin: Long-range peacekeeper (+10 Guns, Sneak, Survival)."),
        (0x828, "FO4SF_BG_MinutemanVolunteer", "Minuteman Volunteer", "Origin: Homestead militia defender (+10 Guns, Repair, Speech)."),
    };

    public static readonly (uint Id, string Edid, string Name, string Desc)[] Traits =
    {
        (0x830, "FO4SF_Trait_SmallFrame", "Small Frame", "Trait: +1 Agility, -15 Carry Weight."),
        (0x831, "FO4SF_Trait_TriggerDiscipline", "Trigger Discipline", "Trait: +10 Guns/Energy Weapons, -15% Reload Speed."),
        (0x832, "FO4SF_Trait_FastShot", "Fast Shot", "Trait: +20% Reload Speed, -5 Guns/Energy Weapons."),
        (0x833, "FO4SF_Trait_Kamikaze", "Kamikaze", "Trait: +15 Action Points, -15 Damage Resistance."),
        (0x834, "FO4SF_Trait_HeavyHanded", "Heavy Handed", "Trait: +10 Melee/Unarmed, -1 Luck."),
        (0x835, "FO4SF_Trait_FourEyes", "Four Eyes", "Trait: +2 Perception with eyewear, -1 base Perception."),
        (0x836, "FO4SF_Trait_GoodNatured", "Good Natured", "Trait: +5 non-combat skills, -5 combat skills."),
        (0x837, "FO4SF_Trait_Skilled", "Skilled", "Trait: +5 to all 13 skills, -10% XP gain."),
        (0x838, "FO4SF_Trait_WildWasteland", "Wild Wasteland", "Trait: Unlocks strange wasteland encounters."),
    };

    public static readonly (uint Id, string Edid, string Name, string Desc)[] PlayablePerks =
    {
        (0x840, "FO4SF_Perk_Educated", "Educated", "Grants +2 extra skill points every level."),
        (0x841, "FO4SF_Perk_Comprehension", "Comprehension", "Increases skill book and magazine gains."),
        (0x842, "FO4SF_Perk_StrongBack", "Strong Back", "Increases Carry Weight by +50."),
        (0x843, "FO4SF_Perk_Toughness", "Toughness", "Increases Damage Resistance by +15."),
        (0x844, "FO4SF_Perk_Finesse", "Finesse", "Increases critical strike chance."),
        (0x845, "FO4SF_Perk_Commando", "Commando", "Improves two-handed rifle accuracy and handling."),
        (0x846, "FO4SF_Perk_JuryRigging", "Jury Rigging", "Repairs items using broad category matches."),
        (0x847, "FO4SF_Perk_ActionPerson", "Action Boy", "Increases Action Points by +15."),
    };

    public static readonly ushort[] Stages = { 10, 15, 20, 30, 40, 50 };

    // Every MESG in ProgressionCore has <= 7 buttons (B3); Confirm is reachable directly from SpecialPage1Msg.
    public static readonly (uint Id, string Edid, string Name, string Desc, string[] Buttons)[] CreationMessages =
    {
        (SpecialPage1MsgId, SpecialPage1MsgEdid, "S.P.E.C.I.A.L. (1 of 2)",
         "STR %.0f   PER %.0f   END %.0f   CHA %.0f   INT %.0f   AGI %.0f   LCK %.0f\nUnspent Points: %.0f   (Step: %.0f)",
         new[] { "Strength", "Perception", "Endurance", "Toggle +1 / -1", "Next (C / I / A / L)", "Confirm (0 unspent)", "Cancel" }),
        (SpecialPage2MsgId, SpecialPage2MsgEdid, "S.P.E.C.I.A.L. (2 of 2)",
         "STR %.0f   PER %.0f   END %.0f   CHA %.0f   INT %.0f   AGI %.0f   LCK %.0f\nUnspent Points: %.0f   (Step: %.0f)",
         new[] { "Charisma", "Intelligence", "Agility", "Luck", "Toggle +1 / -1", "Back (S / P / E)", "Confirm (0 unspent)" }),
        (SpecialDefaultMsgId, SpecialDefaultMsgEdid, "Standard S.P.E.C.I.A.L. Spread",
         "Three S.P.E.C.I.A.L. attempts ended without confirmation. Apply the standard spread or try again?",
         new[] { "Use the standard spread", "Try again" }),
        (TagPage1MsgId, TagPage1MsgEdid, "Tag Skills (1 of 3)",
         "Select 3 Tag Skills (+15 each). Selected: %.0f / 3",
         new[] { "Barter", "Energy Weapons", "Explosives", "Guns", "Next Page (5-9)", "Confirm (3 selected)", "Cancel" }),
        (TagPage2MsgId, TagPage2MsgEdid, "Tag Skills (2 of 3)",
         "Select 3 Tag Skills (+15 each). Selected: %.0f / 3",
         new[] { "Lockpick", "Medicine", "Melee Weapons", "Repair", "Science", "Next Page (10-13)", "Previous Page (1-4)" }),
        (TagPage3MsgId, TagPage3MsgEdid, "Tag Skills (3 of 3)",
         "Select 3 Tag Skills (+15 each). Selected: %.0f / 3",
         new[] { "Sneak", "Speech", "Survival", "Unarmed", "Previous Page (5-9)", "Clear Tags", "Confirm (3 selected)" }),
        (ProgBackgroundMsgId, ProgBackgroundMsgEdid, "Character Background (1 of 2)",
         "Choose 1 Wasteland Background (+10 to three signature skills):",
         new[] { "Vault Dweller", "Wasteland Scavenger", "Caravan Guard", "Field Medic", "Brotherhood Scribe", "More Backgrounds", "Cancel" }),
        (ProgBackgroundPage2MsgId, ProgBackgroundPage2MsgEdid, "Character Background (2 of 2)",
         "Choose 1 Wasteland Background (+10 to three signature skills):",
         new[] { "Enclave Remnant", "Tribal Hunter", "Desert Ranger", "Minuteman Volunteer", "Previous Page", "Cancel" }),
        (ProgTraitsMsgId, ProgTraitsMsgEdid, "Traits (1 of 3)",
         "Choose 0 to 2 Trade-Off Traits (toggle). Selected: %.0f / 2",
         new[] { "Small Frame", "Trigger Discipline", "Fast Shot", "More Traits", "Clear Traits", "Done (0-2 selected)", "Cancel" }),
        (ProgTraitsPage2MsgId, ProgTraitsPage2MsgEdid, "Traits (2 of 3)",
         "Choose 0 to 2 Trade-Off Traits (toggle). Selected: %.0f / 2",
         new[] { "Kamikaze", "Heavy Handed", "Four Eyes", "More Traits", "Previous Page", "Done (0-2 selected)", "Cancel" }),
        (ProgTraitsPage3MsgId, ProgTraitsPage3MsgEdid, "Traits (3 of 3)",
         "Choose 0 to 2 Trade-Off Traits (toggle). Selected: %.0f / 2",
         new[] { "Good Natured", "Skilled", "Wild Wasteland", "Previous Page", "Clear Traits", "Done (0-2 selected)", "Cancel" }),
        (RespecRefusedMsgId, RespecRefusedMsgEdid, "Character Revision Locked",
         "You have already used your one character revision before leaving Vault 111.",
         new[] { "OK" }),
    };

    static readonly uint[] SpecialAllocationMsgIds = { SpecialPage1MsgId, SpecialPage2MsgId };

    public static string[] SpecialBoxNamesFromTable() =>
        SpecialAllocationMsgIds.Select(id => CreationMessages.First(m => m.Id == id).Edid).ToArray();

    public static int[] SpecialBoxButtonCountsFromTable() =>
        SpecialAllocationMsgIds.Select(id => CreationMessages.First(m => m.Id == id).Buttons.Length).ToArray();

    // Pinned Quest VMAD object & value property order
    public static readonly string[] ObjPropNames =
    {
        "SpecialAVList",
        "SkillAVList",
        "BackgroundPerks",
        "TraitPerks",
        "PlayablePerks",
        "KarmaAV",
        "KarmaGlobal",
        "Pool28Global",
        "PerkCadenceGlobal",
        "QueuedPerkPointsGlobal",
        "QueuedSkillPointsGlobal",
        "TraitRespecUsedGlobal",
        "CarryWeightAV",
        "HealthAV",
        "TestModeGlobal",
        "SpecialPage1Msg",
        "SpecialPage2Msg",
        "SpecialDefaultMsg",
        "TagSkillsPage1Msg",
        "TagSkillsPage2Msg",
        "TagSkillsPage3Msg",
        "BackgroundPage1Msg",
        "BackgroundPage2Msg",
        "TraitsPage1Msg",
        "TraitsPage2Msg",
        "TraitsPage3Msg",
        "RespecRefusedMsg"
    };

    public static readonly string[] ValuePropNames =
    {
        "SpecialBoxNames",
        "SpecialBoxButtonCounts",
        "StandardSpread40",
        "StandardSpread28"
    };

    public static readonly string[] PropNames = ObjPropNames.Concat(ValuePropNames).ToArray();

    static FormKey Own(uint id) => new(Plugin, id);

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

    static ScriptObjectProperty ObjProp(string name, FormKey fk) => new()
    {
        Name = name, Flags = ScriptProperty.Flag.Edited, Object = new FormLink<IStarfieldMajorRecordGetter>(fk),
    };

    static ScriptStringListProperty StrListProp(string name, IEnumerable<string> values) => new()
    {
        Name = name, Flags = ScriptProperty.Flag.Edited, Data = new ExtendedList<string>(values),
    };

    static ScriptIntListProperty IntListProp(string name, IEnumerable<int> values) => new()
    {
        Name = name, Flags = ScriptProperty.Flag.Edited, Data = new ExtendedList<int>(values),
    };

    static Dictionary<string, FormKey> ExpectedProperties(
        IReadOnlyDictionary<string, uint> coreIds,
        FormKey carryKey,
        FormKey healthKey) => new()
    {
        ["SpecialAVList"] = Core(coreIds, SpecialAvListEdid),
        ["SkillAVList"] = Core(coreIds, SkillAvListEdid),
        ["BackgroundPerks"] = Own(BgFlstId),
        ["TraitPerks"] = Own(TraitFlstId),
        ["PlayablePerks"] = Own(PerkFlstId),
        ["KarmaAV"] = Core(coreIds, KarmaAvEdid),
        ["KarmaGlobal"] = Core(coreIds, KarmaValueGlobEdid),
        ["Pool28Global"] = Own(Pool28GlobId),
        ["PerkCadenceGlobal"] = Own(CadenceGlobId),
        ["QueuedPerkPointsGlobal"] = Own(QueuedPerkGlobId),
        ["QueuedSkillPointsGlobal"] = Own(QueuedSkillGlobId),
        ["TraitRespecUsedGlobal"] = Own(RespecUsedGlobId),
        ["CarryWeightAV"] = carryKey,
        ["HealthAV"] = healthKey,
        ["TestModeGlobal"] = Core(coreIds, TestModeGlobEdid),
        ["SpecialPage1Msg"] = Own(SpecialPage1MsgId),
        ["SpecialPage2Msg"] = Own(SpecialPage2MsgId),
        ["SpecialDefaultMsg"] = Own(SpecialDefaultMsgId),
        ["TagSkillsPage1Msg"] = Own(TagPage1MsgId),
        ["TagSkillsPage2Msg"] = Own(TagPage2MsgId),
        ["TagSkillsPage3Msg"] = Own(TagPage3MsgId),
        ["BackgroundPage1Msg"] = Own(ProgBackgroundMsgId),
        ["BackgroundPage2Msg"] = Own(ProgBackgroundPage2MsgId),
        ["TraitsPage1Msg"] = Own(ProgTraitsMsgId),
        ["TraitsPage2Msg"] = Own(ProgTraitsPage2MsgId),
        ["TraitsPage3Msg"] = Own(ProgTraitsPage3MsgId),
        ["RespecRefusedMsg"] = Own(RespecRefusedMsgId),
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

    static void WriteMod(StarfieldMod mod, string outDir)
    {
        RefuseForbiddenOutDir(outDir);
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

    public static int Build(string sfPath, string outDir, int pool28, int cadence, string? jsonPath = null)
    {
        if (StandardSpread40.Length != 7 || StandardSpread40.Sum() != 40)
            throw new Refusal("StandardSpread40 must hold 7 values summing to 40");
        if (StandardSpread28.Length != 7 || StandardSpread28.Sum() != 28)
            throw new Refusal("StandardSpread28 must hold 7 values summing to 28");

        var coreIds = LoadCoreValues(jsonPath);
        using var sf = OpenMod(sfPath, SfEsm);
        var carryAv = One(sf.ActorValueInformation, "CarryWeight", "AVIF");
        var healthAv = One(sf.ActorValueInformation, "Health", "AVIF");

        var mod = new StarfieldMod(Plugin, Release);
        mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        mod.ModHeader.Author = "fo4-to-starfield ProgressionCore";

        // 1. 5 Progression-owned Globals (0x808..0x80B, 0x80D)
        var pool28Glob = new Global(Own(Pool28GlobId), Release) { EditorID = "FO4SF_SpecialPool28", Data = pool28 };
        var cadenceGlob = new Global(Own(CadenceGlobId), Release) { EditorID = "FO4SF_PerkCadenceLevels", Data = cadence };
        var qPerkGlob = new Global(Own(QueuedPerkGlobId), Release) { EditorID = "FO4SF_QueuedPerkPoints", Data = 0f };
        var respecGlob = new Global(Own(RespecUsedGlobId), Release) { EditorID = "FO4SF_TraitRespecUsed", Data = 0f };
        var qSkillGlob = new Global(Own(QueuedSkillGlobId), Release) { EditorID = "FO4SF_QueuedSkillPoints", Data = 0f };
        mod.Globals.Add(pool28Glob);
        mod.Globals.Add(cadenceGlob);
        mod.Globals.Add(qPerkGlob);
        mod.Globals.Add(respecGlob);
        mod.Globals.Add(qSkillGlob);

        // 2. 9 Backgrounds + 9 Traits + 8 Playable Perks (26 PERKs) + 3 Perk FLSTs (0x82F, 0x83F, 0x84F)
        var bgFlst = new FormList(Own(BgFlstId), Release) { EditorID = "FO4SF_BackgroundPerks" };
        foreach (var bg in Backgrounds)
        {
            var p = new Perk(Own(bg.Id), Release)
            {
                EditorID = bg.Edid, Name = bg.Name, Description = bg.Desc,
                Flags = Perk.Flag.PcPlayable,
            };
            mod.Perks.Add(p);
            bgFlst.Items.Add(p.FormKey);
        }
        mod.FormLists.Add(bgFlst);

        var trFlst = new FormList(Own(TraitFlstId), Release) { EditorID = "FO4SF_TraitPerks" };
        foreach (var tr in Traits)
        {
            var p = new Perk(Own(tr.Id), Release)
            {
                EditorID = tr.Edid, Name = tr.Name, Description = tr.Desc,
                Flags = Perk.Flag.PcPlayable,
            };
            mod.Perks.Add(p);
            trFlst.Items.Add(p.FormKey);
        }
        mod.FormLists.Add(trFlst);

        var pkFlst = new FormList(Own(PerkFlstId), Release) { EditorID = "FO4SF_PlayablePerks" };
        foreach (var pk in PlayablePerks)
        {
            var p = new Perk(Own(pk.Id), Release)
            {
                EditorID = pk.Edid, Name = pk.Name, Description = pk.Desc,
                Flags = Perk.Flag.PcPlayable,
            };
            mod.Perks.Add(p);
            pkFlst.Items.Add(p.FormKey);
        }
        mod.FormLists.Add(pkFlst);

        // 3. Interactive Creation Sheet, Standard-Spread & Respec Message Menus (0x870..0x87B, all <= 7 buttons)
        foreach (var cm in CreationMessages.OrderBy(x => x.Id))
        {
            if (cm.Buttons.Length > MaxMessageButtons)
                throw new Refusal($"MESG 0x{cm.Id:X} ({cm.Edid}) has {cm.Buttons.Length} buttons (> {MaxMessageButtons})");
            var msg = new Message(Own(cm.Id), Release)
            {
                EditorID = cm.Edid, Name = cm.Name, Description = cm.Desc,
                Flags = Message.Flag.MessageBox,
            };
            foreach (var b in cm.Buttons) msg.MenuButtons.Add(new MessageButton { Text = b });
            mod.Messages.Add(msg);
        }

        // 4. Progression Controller Quest (0x880)
        var quest = new Quest(Own(QuestId), Release)
        {
            EditorID = QuestEdid, Name = "FO4SF Player Creation & Progression",
            FormVersion = 581, Version2 = 12,
            Data = new QuestData { Flags = Quest.Flag.StartGameEnabled | Quest.Flag.RunOnce, Priority = 48 },
        };
        foreach (var st in Stages) quest.Stages.Add(new QuestStage { Index = st });

        var se = new ScriptEntry { Name = ScriptName, Flags = ScriptEntry.Flag.Local };
        var propMap = ExpectedProperties(coreIds, carryAv.FormKey, healthAv.FormKey);
        foreach (var pn in ObjPropNames) se.Properties.Add(ObjProp(pn, propMap[pn]));
        se.Properties.Add(StrListProp("SpecialBoxNames", SpecialBoxNamesFromTable()));
        se.Properties.Add(IntListProp("SpecialBoxButtonCounts", SpecialBoxButtonCountsFromTable()));
        se.Properties.Add(IntListProp("StandardSpread40", StandardSpread40));
        se.Properties.Add(IntListProp("StandardSpread28", StandardSpread28));

        quest.VirtualMachineAdapter = new QuestAdapter
        {
            Version = 6, ObjectFormat = 2, ExtraBindDataVersion = 3,
            Script = new ScriptEntry { Name = "", Flags = ScriptEntry.Flag.Local },
        };
        quest.VirtualMachineAdapter.Scripts.Add(se);
        mod.Quests.Add(quest);

        mod.ModHeader.Stats.NextFormID = NextId;

        WriteMod(mod, outDir);
        var outPath = Path.Combine(outDir, Plugin.FileName);
        Console.WriteLine($"wrote {outPath} ({new FileInfo(outPath).Length:N0} bytes): " +
                          $"0 AVIF, 26 PERK, 3 FLST, 5 GLOB, {CreationMessages.Length} MESG, 0 FACT, 1 QUST ({PropNames.Length} properties); pool28={pool28}, cadence={cadence}");
        return 0;
    }

    public static int Check(string pluginPath, string sfPath, int pool28, int cadence, string? jsonPath = null)
    {
        if (!File.Exists(pluginPath)) throw new Refusal($"missing plugin: {pluginPath}");
        var coreIds = LoadCoreValues(jsonPath);
        using var sf = OpenMod(sfPath, SfEsm);
        var carryAv = One(sf.ActorValueInformation, "CarryWeight", "AVIF");
        var healthAv = One(sf.ActorValueInformation, "Health", "AVIF");
        using var mod = OpenMod(pluginPath, SfEsm, CoreValuesEsm);

        if (!mod.ModHeader.Flags.HasFlag(StarfieldModHeader.HeaderFlag.Master))
            throw new Refusal("plugin lacks Master header flag");
        var masters = mod.ModHeader.MasterReferences.Select(m => m.Master).ToList();
        if (!masters.SequenceEqual(new[] { SfEsm, CoreValuesEsm }))
            throw new Refusal($"expected masters [Starfield.esm, FO4SFCoreValues.esm], got [{string.Join(", ", masters)}]");

        foreach (var rec in mod.EnumerateMajorRecords())
        {
            if (rec.FormKey.ModKey != Plugin)
                throw new Refusal($"plugin overrides foreign record {rec.FormKey} ({rec.EditorID})");
            if (rec.EditorID != null && coreIds.ContainsKey(rec.EditorID))
                throw new Refusal($"plugin duplicates FO4SFCoreValues.esm EditorID {rec.EditorID}");
        }

        if (mod.ActorValueInformation.Count != 0)
            throw new Refusal($"expected 0 AVIF (all SPECIAL/Skill/Karma AVIFs live in FO4SFCoreValues.esm), found {mod.ActorValueInformation.Count}");
        if (mod.Perks.Count != 26)
            throw new Refusal($"expected 26 PERK (9 BG + 9 Traits + 8 Perks), found {mod.Perks.Count}");
        if (mod.FormLists.Count != 3)
            throw new Refusal($"expected 3 FLST (BackgroundPerks, TraitPerks, PlayablePerks), found {mod.FormLists.Count}");
        if (mod.Globals.Count != 5)
            throw new Refusal($"expected 5 GLOB (0x808..0x80B, 0x80D), found {mod.Globals.Count}");
        if (mod.Messages.Count != CreationMessages.Length)
            throw new Refusal($"expected {CreationMessages.Length} MESG (0x870..0x87B), found {mod.Messages.Count}");
        if (mod.Factions.Count != 0)
            throw new Refusal($"expected 0 FACT (faction reputation lives in FO4SFReputation.esm), found {mod.Factions.Count}");
        if (mod.Quests.Count != 1)
            throw new Refusal($"expected 1 QUST, found {mod.Quests.Count}");

        foreach (var m in mod.Messages)
        {
            if (m.MenuButtons.Count > MaxMessageButtons)
                throw new Refusal($"MESG {m.FormKey} ({m.EditorID}) has {m.MenuButtons.Count} buttons, exceeding maximum {MaxMessageButtons}");
        }

        foreach (var cm in CreationMessages)
        {
            var m = mod.Messages.FirstOrDefault(x => x.FormKey == Own(cm.Id));
            if (m is null || m.EditorID != cm.Edid || !m.Flags.HasFlag(Message.Flag.MessageBox) ||
                m.MenuButtons.Count > MaxMessageButtons ||
                !m.MenuButtons.Select(b => b.Text?.String).SequenceEqual(cm.Buttons))
                throw new Refusal($"MESG 0x{cm.Id:X} ({cm.Edid}) missing or button contract mismatch");
        }

        var expectedGlobIds = new[] { Pool28GlobId, CadenceGlobId, QueuedPerkGlobId, RespecUsedGlobId, QueuedSkillGlobId };
        var actualGlobIds = mod.Globals.Select(g => g.FormKey.ID).OrderBy(x => x).ToArray();
        if (!actualGlobIds.SequenceEqual(expectedGlobIds))
            throw new Refusal($"unexpected GLOB IDs [{string.Join(",", actualGlobIds.Select(x => $"0x{x:X}"))}]");

        var expectedFlstIds = new[] { BgFlstId, TraitFlstId, PerkFlstId };
        var actualFlstIds = mod.FormLists.Select(f => f.FormKey.ID).OrderBy(x => x).ToArray();
        if (!actualFlstIds.SequenceEqual(expectedFlstIds))
            throw new Refusal($"unexpected FLST IDs [{string.Join(",", actualFlstIds.Select(x => $"0x{x:X}"))}]");

        var p28G = mod.Globals.First(g => g.FormKey == Own(Pool28GlobId));
        var cadG = mod.Globals.First(g => g.FormKey == Own(CadenceGlobId));
        if (Math.Abs((p28G.Data ?? -1f) - pool28) > 0.001f) throw new Refusal($"FO4SF_SpecialPool28 expected {pool28}, got {p28G.Data}");
        if (Math.Abs((cadG.Data ?? -1f) - cadence) > 0.001f) throw new Refusal($"FO4SF_PerkCadenceLevels expected {cadence}, got {cadG.Data}");

        var q = mod.Quests.First();
        if (q.FormKey != Own(QuestId) || q.EditorID != QuestEdid)
            throw new Refusal($"unexpected QUST {q.FormKey} ({q.EditorID})");
        if (!q.Stages.Select(s => s.Index).SequenceEqual(Stages))
            throw new Refusal($"quest stages [{string.Join(",", q.Stages.Select(s => s.Index))}] != expected [{string.Join(",", Stages)}]");
        var props = q.VirtualMachineAdapter?.Scripts.FirstOrDefault()?.Properties ?? Array.Empty<IScriptPropertyGetter>();
        var actualProps = props.Select(p => p.Name).ToArray();
        if (!actualProps.SequenceEqual(PropNames))
            throw new Refusal($"quest properties [{string.Join(",", actualProps)}] != expected [{string.Join(",", PropNames)}]");

        var expectedMap = ExpectedProperties(coreIds, carryAv.FormKey, healthAv.FormKey);
        var byName = props.ToDictionary(p => p.Name);
        foreach (var pn in ObjPropNames)
        {
            if (byName[pn] is not IScriptObjectPropertyGetter op || op.Object.FormKey != expectedMap[pn])
                throw new Refusal($"quest property {pn} target {(byName[pn] as IScriptObjectPropertyGetter)?.Object.FormKey} != expected {expectedMap[pn]}");
        }

        // Verify SpecialBoxNames and SpecialBoxButtonCounts match the written MESG records
        var actualBoxNames = SpecialAllocationMsgIds.Select(id => mod.Messages.First(x => x.FormKey == Own(id)).EditorID ?? "").ToArray();
        var actualBoxCounts = SpecialAllocationMsgIds.Select(id => mod.Messages.First(x => x.FormKey == Own(id)).MenuButtons.Count).ToArray();
        if (byName["SpecialBoxNames"] is not IScriptStringListPropertyGetter sbn || !sbn.Data.SequenceEqual(actualBoxNames))
            throw new Refusal("quest property SpecialBoxNames does not match written S.P.E.C.I.A.L. MESG EditorIDs");
        if (byName["SpecialBoxButtonCounts"] is not IScriptIntListPropertyGetter sbc || !sbc.Data.SequenceEqual(actualBoxCounts))
            throw new Refusal("quest property SpecialBoxButtonCounts does not match written S.P.E.C.I.A.L. MESG MenuButtons counts");
        if (byName["StandardSpread40"] is not IScriptIntListPropertyGetter sp40 || !sp40.Data.SequenceEqual(StandardSpread40) || sp40.Data.Sum() != 40)
            throw new Refusal("quest property StandardSpread40 mismatch or sum != 40");
        if (byName["StandardSpread28"] is not IScriptIntListPropertyGetter sp28 || !sp28.Data.SequenceEqual(StandardSpread28) || sp28.Data.Sum() != 28)
            throw new Refusal("quest property StandardSpread28 mismatch or sum != 28");

        Console.WriteLine($"FO4SFProgression.esm: header Master, masters [Starfield.esm, FO4SFCoreValues.esm], 0 AVIF, 26 PERK, 3 FLST, 5 GLOB, {CreationMessages.Length} MESG (all <= {MaxMessageButtons} buttons), 0 FACT, 1 QUST; all checks pass");
        return 0;
    }

    public static int Fixture(string outDir)
    {
        Directory.CreateDirectory(outDir);
        var sf = new StarfieldMod(SfEsm, Release);
        sf.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        sf.ActorValueInformation.Add(new ActorValueInformation(new FormKey(SfEsm, 0xA010), Release)
        {
            EditorID = "CarryWeight", Name = "Carry Weight", Type = ActorValueInformation.Types.Variable, DefaultValue = 150f, Min = 0f, Max = 5000f,
        });
        sf.ActorValueInformation.Add(new ActorValueInformation(new FormKey(SfEsm, 0xA011), Release)
        {
            EditorID = "Health", Name = "Health", Type = ActorValueInformation.Types.Variable, DefaultValue = 100f, Min = 0f, Max = 5000f,
        });
        var sfPath = Path.Combine(outDir, "Starfield.esm");
        var masters = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        masters.Set(new KeyedMasterStyle(SfEsm, MasterStyle.Full));
        sf.WriteToBinary(sfPath, new BinaryWriteParameters { ModKey = ModKeyOption.NoCheck, MasterFlagsLookup = masters });
        return 0;
    }

    public static int SelfTest(string scratchDir)
    {
        Directory.CreateDirectory(scratchDir);
        var fixDir = Path.Combine(scratchDir, "fixture");
        Fixture(fixDir);
        var sfPath = Path.Combine(fixDir, "Starfield.esm");

        foreach (var (p28, cad) in new[] { (0, 2), (1, 1) })
        {
            var outDir = Path.Combine(scratchDir, $"out_{p28}_{cad}");
            if (Build(sfPath, outDir, p28, cad) != 0) throw new Refusal($"Build({p28},{cad}) failed");
            var plugin = Path.Combine(outDir, Plugin.FileName);
            if (Check(plugin, sfPath, p28, cad) != 0) throw new Refusal($"Check({p28},{cad}) failed");

            bool refused = false;
            try { Check(plugin, sfPath, p28, cad + 1); }
            catch (Refusal) { refused = true; }
            if (!refused) throw new Refusal("Check failed to refuse mismatched --cadence");
        }

        // Negative tamper controls: duplicate CoreValues AVIF, > 7 MESG buttons, mismatched SpecialBoxButtonCounts, wrong VMAD link, and stray FACT
        var cleanPlugin = Path.Combine(scratchDir, "out_0_2", Plugin.FileName);
        var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        styles.Set(new KeyedMasterStyle(SfEsm, MasterStyle.Full));
        styles.Set(new KeyedMasterStyle(CoreValuesEsm, MasterStyle.Full));

        void ExpectRefusal(string name, Action<StarfieldMod> tamper)
        {
            var tDir = Path.Combine(scratchDir, "tamper_" + name);
            var mut = StarfieldMod.CreateFromBinary(cleanPlugin, Release, new BinaryReadParameters { MasterFlagsLookup = styles });
            tamper(mut);
            WriteMod(mut, tDir);
            bool rejected = false;
            try { Check(Path.Combine(tDir, Plugin.FileName), sfPath, 0, 2); }
            catch (Refusal) { rejected = true; }
            if (!rejected) throw new Refusal($"tamper {name} was not refused by Check");
        }

        var firstCoreEdid = LoadCoreValues().Keys.First();
        ExpectRefusal("dup_avif", m =>
            m.ActorValueInformation.Add(new ActorValueInformation(Own(0x800), Release) { EditorID = firstCoreEdid, Type = ActorValueInformation.Types.Variable }));
        ExpectRefusal("bad_vmad_link", m =>
            ((ScriptObjectProperty)m.Quests.First().VirtualMachineAdapter!.Scripts[0].Properties[0]).Object.SetTo(Own(BgFlstId)));
        ExpectRefusal("stray_fact", m =>
            m.Factions.Add(new Faction(Own(0x890), Release) { EditorID = "FO4SF_UnexpectedFaction" }));
        ExpectRefusal("missing_mesg", m =>
            m.Messages.Remove(m.Messages.First().FormKey));
        ExpectRefusal("bad_mesg_buttons", m =>
            m.Messages.First().MenuButtons.RemoveAt(0));
        ExpectRefusal("over_7_mesg_buttons", m =>
            m.Messages.First(x => x.FormKey == Own(SpecialPage1MsgId)).MenuButtons.Add(new MessageButton { Text = "Extra8th" }));
        ExpectRefusal("bad_box_count_prop", m =>
            ((ScriptIntListProperty)m.Quests.First().VirtualMachineAdapter!.Scripts[0].Properties.First(p => p.Name == "SpecialBoxButtonCounts")).Data[0] = 10);
        ExpectRefusal("bad_spread40_sum", m =>
            ((ScriptIntListProperty)m.Quests.First().VirtualMachineAdapter!.Scripts[0].Properties.First(p => p.Name == "StandardSpread40")).Data[0] = 7);

        Console.WriteLine("selftest: ok");
        return 0;
    }
}
