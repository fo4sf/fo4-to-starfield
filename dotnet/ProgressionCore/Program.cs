// ProgressionCore: Player Creation & Progression Core plugin writer and checker (CF-6, docs/progression/progression-core.md).
//
// Writes FO4SFProgression.esm (sole master Starfield.esm; adds records only, overrides none):
//   0x800..0x806 AVIF FO4SF_Special_Strength..Luck   (7 SPECIAL attributes, 1..10 base, default 5)
//   0x807        AVIF FO4SF_Karma                    (-1000..+1000 moral axis, decoupled from REPU)
//   0x808        GLOB FO4SF_SpecialPool28            (0 = 40-pt NV default, 1 = 28-pt FO4 option)
//   0x809        GLOB FO4SF_PerkCadenceLevels        (default 2 = 1 Perk per 2 levels; runtime-tunable)
//   0x80A        GLOB FO4SF_QueuedPerkPoints         (0 default)
//   0x80B        GLOB FO4SF_TraitRespecUsed          (0 = exit respec available, 1 = used & locked)
//   0x80C        GLOB FO4SF_KarmaGlobal              (0 default, synced with FO4SF_Karma)
//   0x80D        GLOB FO4SF_QueuedSkillPoints        (0 default)
//   0x80E        FLST FO4SF_SpecialAVList            (7 SPECIAL AVIFs in STR..LCK order)
//   0x810..0x81C AVIF FO4SF_Skill_Barter..Unarmed    (13 NV skills, 1..100)
//   0x81E        FLST FO4SF_SkillAVList              (13 Skill AVIFs in alphabetical NV order)
//   0x820..0x828 PERK FO4SF_BG_*                     (9 Wasteland Backgrounds in FLST 0x82F)
//   0x830..0x838 PERK FO4SF_Trait_*                  (9 Trade-Off Traits in FLST 0x83F)
//   0x840..0x847 PERK FO4SF_Perk_*                   (8 Core Playable Perks in FLST 0x84F)
//   0x860..0x86B GLOB FO4SF_Repu_<Faction>_Fame/Infamy (12 GLOBs = 6 faction pairs in FLST 0x86F)
//   0x870..0x875 FACT FO4SF_Fact_<Faction>           (6 Factions in FLST 0x87F)
//   0x880        QUST FO4SF_ProgressionQuest         (StartGameEnabled creation, respec, cadence & REPU quest)
//
// usage:
//   ProgressionCore build <Starfield.esm> <out dir> [--pool28 0|1] [--cadence <int>=2]
//   ProgressionCore check <plugin> <Starfield.esm> [--pool28 0|1] [--cadence <int>=2]
//   ProgressionCore fixture <out dir>
//   ProgressionCore selftest <scratch dir>

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
    int pool28 = 0;
    int cadence = 2;

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

    if (rest.Count == 3 && rest[0] == "build") return ProgressionCore.Build(rest[1], rest[2], pool28, cadence);
    if (rest.Count == 3 && rest[0] == "check") return ProgressionCore.Check(rest[1], rest[2], pool28, cadence);
    if (rest.Count == 2 && rest[0] == "fixture") return ProgressionCore.Fixture(rest[1]);
    if (rest.Count == 2 && rest[0] == "selftest") return ProgressionCore.SelfTest(rest[1]);
}
catch (ProgressionCore.Refusal r)
{
    Console.Error.WriteLine("refused: " + r.Message);
    return 1;
}

Console.Error.WriteLine("usage: ProgressionCore build <Starfield.esm> <out dir> [--pool28 0|1] [--cadence <int>] | " +
                        "check <plugin> <Starfield.esm> [same options] | fixture <out dir> | selftest <scratch dir>");
return 2;

public static class ProgressionCore
{
    public class Refusal(string m) : Exception(m);

    const StarfieldRelease Release = StarfieldRelease.Starfield;
    static readonly ModKey SfEsm = ModKey.FromFileName("Starfield.esm");
    public static readonly ModKey Plugin = ModKey.FromFileName("FO4SFProgression.esm");

    public const uint PlayerFactionId = 0x01C21C;

    public const uint KarmaAvifId = 0x807;
    public const uint Pool28GlobId = 0x808;
    public const uint CadenceGlobId = 0x809;
    public const uint QueuedPerkGlobId = 0x80A;
    public const uint RespecUsedGlobId = 0x80B;
    public const uint KarmaGlobId = 0x80C;
    public const uint QueuedSkillGlobId = 0x80D;

    public const uint SpecialFlstId = 0x80E;
    public const uint SkillFlstId = 0x81E;
    public const uint BgFlstId = 0x82F;
    public const uint TraitFlstId = 0x83F;
    public const uint PerkFlstId = 0x84F;
    public const uint RepuFlstId = 0x86F;
    public const uint FactFlstId = 0x87F;

    public const uint QuestId = 0x880;
    public const uint NextId = 0x881;

    public static readonly (uint Id, string Edid, string Name, string Abbr)[] Specials =
    {
        (0x800, "FO4SF_Special_Strength", "Strength", "STR"),
        (0x801, "FO4SF_Special_Perception", "Perception", "PER"),
        (0x802, "FO4SF_Special_Endurance", "Endurance", "END"),
        (0x803, "FO4SF_Special_Charisma", "Charisma", "CHA"),
        (0x804, "FO4SF_Special_Intelligence", "Intelligence", "INT"),
        (0x805, "FO4SF_Special_Agility", "Agility", "AGI"),
        (0x806, "FO4SF_Special_Luck", "Luck", "LCK"),
    };

    public static readonly (uint Id, string Edid, string Name, string Abbr)[] Skills =
    {
        (0x810, "FO4SF_Skill_Barter", "Barter", "Bar"),
        (0x811, "FO4SF_Skill_EnergyWeapons", "Energy Weapons", "EWp"),
        (0x812, "FO4SF_Skill_Explosives", "Explosives", "Exp"),
        (0x813, "FO4SF_Skill_Guns", "Guns", "Gun"),
        (0x814, "FO4SF_Skill_Lockpick", "Lockpick", "Lck"),
        (0x815, "FO4SF_Skill_Medicine", "Medicine", "Med"),
        (0x816, "FO4SF_Skill_MeleeWeapons", "Melee Weapons", "Mel"),
        (0x817, "FO4SF_Skill_Repair", "Repair", "Rep"),
        (0x818, "FO4SF_Skill_Science", "Science", "Sci"),
        (0x819, "FO4SF_Skill_Sneak", "Sneak", "Snk"),
        (0x81A, "FO4SF_Skill_Speech", "Speech", "Spc"),
        (0x81B, "FO4SF_Skill_Survival", "Survival", "Srv"),
        (0x81C, "FO4SF_Skill_Unarmed", "Unarmed", "Unm"),
    };

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

    public static readonly (string Slug, uint FameId, uint InfamyId, uint FactId, string Name)[] RepuFactions =
    {
        ("Minutemen", 0x860, 0x861, 0x870, "Commonwealth Minutemen"),
        ("Brotherhood", 0x862, 0x863, 0x871, "Brotherhood of Steel"),
        ("Railroad", 0x864, 0x865, 0x872, "The Railroad"),
        ("Institute", 0x866, 0x867, 0x873, "The Institute"),
        ("NCR", 0x868, 0x869, 0x874, "New California Republic"),
        ("WastelandSettlers", 0x86A, 0x86B, 0x875, "Wasteland Settlers"),
    };

    public static readonly ushort[] Stages = { 10, 20, 30, 40, 50 };

    // Pinned Quest VMAD property order
    public static readonly string[] PropNames =
    {
        "SpecialAVList",
        "SkillAVList",
        "BackgroundPerks",
        "TraitPerks",
        "PlayablePerks",
        "RepuGlobalsList",
        "FactionList",
        "KarmaAV",
        "KarmaGlobal",
        "Pool28Global",
        "PerkCadenceGlobal",
        "QueuedPerkPointsGlobal",
        "QueuedSkillPointsGlobal",
        "TraitRespecUsedGlobal",
        "CarryWeightAV",
        "HealthAV"
    };

    static FormKey Own(uint id) => new(Plugin, id);
    static FormKey Sf(uint id) => new(SfEsm, id);

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

    public static int Build(string sfPath, string outDir, int pool28, int cadence)
    {
        using var sf = OpenMod(sfPath);
        var carryAv = One(sf.ActorValueInformation, "CarryWeight", "AVIF");
        var healthAv = One(sf.ActorValueInformation, "Health", "AVIF");

        var mod = new StarfieldMod(Plugin, Release);
        mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        mod.ModHeader.Author = "fo4-to-starfield ProgressionCore";

        // 1. 7 SPECIAL + 1 Karma + 13 Skill AVIFs (21 AVIFs)
        var specialFlst = new FormList(Own(SpecialFlstId), Release) { EditorID = "FO4SF_SpecialAVList" };
        foreach (var sp in Specials)
        {
            var av = new ActorValueInformation(Own(sp.Id), Release)
            {
                EditorID = sp.Edid, Name = sp.Name, Abbreviation = sp.Abbr,
                Type = ActorValueInformation.Types.Variable, DefaultValue = 5f, Min = 1f, Max = 15f,
            };
            mod.ActorValueInformation.Add(av);
            specialFlst.Items.Add(av.FormKey);
        }
        mod.FormLists.Add(specialFlst);

        var karmaAv = new ActorValueInformation(Own(KarmaAvifId), Release)
        {
            EditorID = "FO4SF_Karma", Name = "Karma", Abbreviation = "Krm",
            Type = ActorValueInformation.Types.Variable, DefaultValue = 0f, Min = -1000f, Max = 1000f,
            Flags = ActorValueInformation.Flag.DefaultToZero,
        };
        mod.ActorValueInformation.Add(karmaAv);

        var skillFlst = new FormList(Own(SkillFlstId), Release) { EditorID = "FO4SF_SkillAVList" };
        foreach (var sk in Skills)
        {
            var av = new ActorValueInformation(Own(sk.Id), Release)
            {
                EditorID = sk.Edid, Name = sk.Name, Abbreviation = sk.Abbr,
                Type = ActorValueInformation.Types.Variable, DefaultValue = 15f, Min = 1f, Max = 100f,
            };
            mod.ActorValueInformation.Add(av);
            skillFlst.Items.Add(av.FormKey);
        }
        mod.FormLists.Add(skillFlst);

        // 2. Core Globals + REPU Globals (6 + 12 = 18 GLOBs) & 6 Factions
        var pool28Glob = new Global(Own(Pool28GlobId), Release) { EditorID = "FO4SF_SpecialPool28", Data = pool28 };
        var cadenceGlob = new Global(Own(CadenceGlobId), Release) { EditorID = "FO4SF_PerkCadenceLevels", Data = cadence };
        var qPerkGlob = new Global(Own(QueuedPerkGlobId), Release) { EditorID = "FO4SF_QueuedPerkPoints", Data = 0f };
        var respecGlob = new Global(Own(RespecUsedGlobId), Release) { EditorID = "FO4SF_TraitRespecUsed", Data = 0f };
        var karmaGlob = new Global(Own(KarmaGlobId), Release) { EditorID = "FO4SF_KarmaGlobal", Data = 0f };
        var qSkillGlob = new Global(Own(QueuedSkillGlobId), Release) { EditorID = "FO4SF_QueuedSkillPoints", Data = 0f };
        mod.Globals.Add(pool28Glob);
        mod.Globals.Add(cadenceGlob);
        mod.Globals.Add(qPerkGlob);
        mod.Globals.Add(respecGlob);
        mod.Globals.Add(karmaGlob);
        mod.Globals.Add(qSkillGlob);

        var repuFlst = new FormList(Own(RepuFlstId), Release) { EditorID = "FO4SF_RepuGlobalsList" };
        var factFlst = new FormList(Own(FactFlstId), Release) { EditorID = "FO4SF_FactionList" };
        foreach (var rf in RepuFactions)
        {
            var fameG = new Global(Own(rf.FameId), Release) { EditorID = $"FO4SF_Repu_{rf.Slug}_Fame", Data = 0f };
            var infamyG = new Global(Own(rf.InfamyId), Release) { EditorID = $"FO4SF_Repu_{rf.Slug}_Infamy", Data = 0f };
            mod.Globals.Add(fameG);
            mod.Globals.Add(infamyG);
            repuFlst.Items.Add(fameG.FormKey);
            repuFlst.Items.Add(infamyG.FormKey);

            var fac = new Faction(Own(rf.FactId), Release)
            {
                EditorID = $"FO4SF_Fact_{rf.Slug}", Name = rf.Name,
            };
            fac.Relations.Add(new Relation
            {
                Target = new FormLink<IRelatableGetter>(Sf(PlayerFactionId)),
                Reaction = CombatReaction.Neutral,
            });
            mod.Factions.Add(fac);
            factFlst.Items.Add(fac.FormKey);
        }
        mod.FormLists.Add(repuFlst);
        mod.FormLists.Add(factFlst);

        // 3. 9 Backgrounds + 9 Traits + 8 Playable Perks (26 PERKs)
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

        // 4. Progression Controller Quest (0x880)
        var quest = new Quest(Own(QuestId), Release)
        {
            EditorID = "FO4SF_ProgressionQuest", Name = "FO4SF Player Creation & Progression",
            FormVersion = 581, Version2 = 12,
            Data = new QuestData { Flags = Quest.Flag.StartGameEnabled | Quest.Flag.RunOnce, Priority = 48 },
        };
        foreach (var st in Stages) quest.Stages.Add(new QuestStage { Index = st });

        var se = new ScriptEntry { Name = "FO4SF_ProgressionQuest", Flags = ScriptEntry.Flag.Local };
        var propMap = new Dictionary<string, FormKey>
        {
            ["SpecialAVList"] = specialFlst.FormKey,
            ["SkillAVList"] = skillFlst.FormKey,
            ["BackgroundPerks"] = bgFlst.FormKey,
            ["TraitPerks"] = trFlst.FormKey,
            ["PlayablePerks"] = pkFlst.FormKey,
            ["RepuGlobalsList"] = repuFlst.FormKey,
            ["FactionList"] = factFlst.FormKey,
            ["KarmaAV"] = karmaAv.FormKey,
            ["KarmaGlobal"] = karmaGlob.FormKey,
            ["Pool28Global"] = pool28Glob.FormKey,
            ["PerkCadenceGlobal"] = cadenceGlob.FormKey,
            ["QueuedPerkPointsGlobal"] = qPerkGlob.FormKey,
            ["QueuedSkillPointsGlobal"] = qSkillGlob.FormKey,
            ["TraitRespecUsedGlobal"] = respecGlob.FormKey,
            ["CarryWeightAV"] = carryAv.FormKey,
            ["HealthAV"] = healthAv.FormKey,
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
        var outPath = Path.Combine(outDir, Plugin.FileName);
        Console.WriteLine($"wrote {outPath} ({new FileInfo(outPath).Length:N0} bytes): " +
                          $"21 AVIF, 26 PERK, 7 FLST, 18 GLOB, 6 FACT, 1 QUST ({PropNames.Length} properties); pool28={pool28}, cadence={cadence}");
        return 0;
    }

    public static int Check(string pluginPath, string sfPath, int pool28, int cadence)
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

        foreach (var rec in mod.EnumerateMajorRecords())
        {
            if (rec.FormKey.ModKey != Plugin)
                throw new Refusal($"plugin overrides foreign record {rec.FormKey} ({rec.EditorID})");
        }

        if (mod.ActorValueInformation.Count != 21) throw new Refusal($"expected 21 AVIF (7 SPECIAL + 13 Skills + Karma), found {mod.ActorValueInformation.Count}");
        if (mod.Perks.Count != 26) throw new Refusal($"expected 26 PERK (9 BG + 9 Traits + 8 Perks), found {mod.Perks.Count}");
        if (mod.FormLists.Count != 7) throw new Refusal($"expected 7 FLST, found {mod.FormLists.Count}");
        if (mod.Globals.Count != 18) throw new Refusal($"expected 18 GLOB, found {mod.Globals.Count}");
        if (mod.Factions.Count != 6) throw new Refusal($"expected 6 FACT, found {mod.Factions.Count}");
        if (mod.Quests.Count != 1) throw new Refusal($"expected 1 QUST, found {mod.Quests.Count}");

        var p28G = mod.Globals.First(g => g.FormKey == Own(Pool28GlobId));
        var cadG = mod.Globals.First(g => g.FormKey == Own(CadenceGlobId));
        if (Math.Abs((p28G.Data ?? -1f) - pool28) > 0.001f) throw new Refusal($"FO4SF_SpecialPool28 expected {pool28}, got {p28G.Data}");
        if (Math.Abs((cadG.Data ?? -1f) - cadence) > 0.001f) throw new Refusal($"FO4SF_PerkCadenceLevels expected {cadence}, got {cadG.Data}");

        var q = mod.Quests.First();
        var actualProps = q.VirtualMachineAdapter?.Scripts.FirstOrDefault()?.Properties.Select(p => p.Name).ToArray() ?? Array.Empty<string>();
        if (!actualProps.SequenceEqual(PropNames))
            throw new Refusal($"quest properties [{string.Join(",", actualProps)}] != expected [{string.Join(",", PropNames)}]");

        Console.WriteLine($"FO4SFProgression.esm: header Master, masters [Starfield.esm], 21 AVIF, 26 PERK, 7 FLST, 18 GLOB, 6 FACT, 1 QUST; all checks pass");
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
        Console.WriteLine("selftest: ok");
        return 0;
    }
}
