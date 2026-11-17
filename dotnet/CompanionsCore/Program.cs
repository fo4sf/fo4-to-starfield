// CompanionsCore: Companions, Crew, and Warfare Squads over Starfield's kept SQ_Followers and SQ_Groups
// (docs/research/gamma-squad-balance.md, docs/companions/companions-warfare-pc-card.md)
//
// FO4SFCompanions.esm (sole master Starfield.esm; adds records, overrides 0).
// SQ_Followers (0x0000D773) and SQ_Groups (0x1A9565) are verified in Starfield.esm and referenced at runtime, never overridden.
//
// usage:
//   CompanionsCore build <Starfield.esm> <out dir> [--base-cap <int>] [--max-cap <int>] [--merc-cost <int>] [--merc-share <float>]
//   CompanionsCore check <plugin> <Starfield.esm> [same options]
//   CompanionsCore fixture <out dir> [--mode full|minimal]
//   CompanionsCore selftest <scratch dir>

using System.Globalization;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;

try
{
    var rest = args.ToList();
    string? Opt(string name)
    {
        int i = rest.IndexOf(name);
        if (i < 0) return null;
        if (i + 1 >= rest.Count) throw new CompanionsCore.Refusal(name + " needs a value");
        var v = rest[i + 1];
        rest.RemoveRange(i, 2);
        return v;
    }

    int ParseInt(string? raw, int defVal, int lo, int hi, string flag)
    {
        if (raw == null) return defVal;
        if (!int.TryParse(raw, NumberStyles.Integer, CultureInfo.InvariantCulture, out var v) || v < lo || v > hi)
            throw new CompanionsCore.Refusal($"{flag} must be in [{lo}, {hi}], got {raw}");
        return v;
    }

    float ParseFloat(string? raw, float defVal, float lo, float hi, string flag)
    {
        if (raw == null) return defVal;
        if (!float.TryParse(raw, NumberStyles.Float, CultureInfo.InvariantCulture, out var v) || v < lo || v > hi)
            throw new CompanionsCore.Refusal($"{flag} must be in [{lo}, {hi}], got {raw}");
        return v;
    }

    var opts = new CompanionsCore.BuildOptions(
        BaseCap: ParseInt(Opt("--base-cap"), 2, 1, 8, "--base-cap"),
        MaxCap: ParseInt(Opt("--max-cap"), 4, 1, 12, "--max-cap"),
        MercCost: ParseInt(Opt("--merc-cost"), 250, 0, 10000, "--merc-cost"),
        MercShare: ParseFloat(Opt("--merc-share"), 0.15f, 0.0f, 0.9f, "--merc-share")
    );
    if (opts.MaxCap < opts.BaseCap)
        throw new CompanionsCore.Refusal($"--max-cap ({opts.MaxCap}) must be >= --base-cap ({opts.BaseCap})");

    var mode = Opt("--mode") ?? "full";

    if (rest.Count == 3 && rest[0] == "build") return CompanionsCore.Build(rest[1], rest[2], opts);
    if (rest.Count == 3 && rest[0] == "check") return CompanionsCore.Check(rest[1], rest[2], opts);
    if (rest.Count == 2 && rest[0] == "fixture") return CompanionsCore.Fixture(rest[1], mode);
    if (rest.Count == 2 && rest[0] == "selftest") return CompanionsCore.SelfTest(rest[1]);
}
catch (CompanionsCore.Refusal r)
{
    Console.Error.WriteLine("refused: " + r.Message);
    return 1;
}

Console.Error.WriteLine("usage: CompanionsCore build <Starfield.esm> <out dir> [--base-cap <int>] [--max-cap <int>] " +
                        "[--merc-cost <int>] [--merc-share <float>] | check <plugin> <Starfield.esm> [same options] | " +
                        "fixture <out dir> [--mode full|minimal] | selftest <scratch dir>");
return 2;

static class CompanionsCore
{
    public class Refusal(string m) : Exception(m);

    public record BuildOptions(int BaseCap, int MaxCap, int MercCost, float MercShare);

    const StarfieldRelease Release = StarfieldRelease.Starfield;
    static readonly ModKey SfEsm = ModKey.FromFileName("Starfield.esm");
    public static readonly ModKey Plugin = ModKey.FromFileName("FO4SFCompanions.esm");

    // Vanilla Starfield.esm FormIDs (verified against Starfield.esm; never overridden)
    public const uint SqFollowersQuestId = 0x0000D773;
    public const uint SqGroupsQuestId = 0x001A9565;
    public const uint FollowPackageId = 0x000301C5;     // DefaultMaster_FollowPackage
    public const uint WaitPackageId = 0x0029D080;       // SQ_Followers_Wait
    public const uint PlayerFactionId = 0x0001C21C;     // PlayerFaction
    public const uint CocMarkerStaticId = 0x000032;     // COCMarkerHeading
    public const uint PerkUnknownStaticId = 0x000002;
    public const uint CreditsMiscId = 0x00000F;
    public const uint GameDaysPassedGlobId = 0x000039;
    public const uint CharismaAvifId = 0x0002C5;
    public const uint HealthAvifId = 0x0002D4;
    public const uint DamageResistAvifId = 0x0002E3;
    public const uint EnergyResistAvifId = 0x0002EB;
    public const uint FollowerStateAvifId = 0x000344;

    // Locked local FormIDs in FO4SFCompanions.esm
    public const uint QuestId = 0x800;
    public const uint SquadBaseCapGlobId = 0x801;
    public const uint SquadMaxCapGlobId = 0x802;
    public const uint MercHireCostGlobId = 0x803;
    public const uint MercRewardShareGlobId = 0x804;
    public const uint ActiveSquadCountGlobId = 0x805;
    public const uint SquadStanceGlobId = 0x806;

    public const uint CompanionAffinityAvifId = 0x807;
    public const uint SquadLoyaltyAvifId = 0x808;
    public const uint RecruitRankTierAvifId = 0x809;
    public const uint SquadOrderStateAvifId = 0x80A;
    public const uint CompanionNerveBonusAvifId = 0x80B;

    public const uint PerkUnitedWeStandId = 0x810;
    public const uint PerkRobotSympathyId = 0x811;
    public const uint PerkSquadCommanderId = 0x812;
    public const uint PerkLoneWandererSoloId = 0x813;

    public const uint CompanionWheelMsgId = 0x815;
    public const uint FireteamCommandMsgId = 0x816;
    public const uint RecruitPromptMsgId = 0x817;
    public const uint SquadAllyFactionId = 0x818;

    public const uint SquadRadioTokenId = 0x820;
    public const uint RadioFilterListId = 0x821;
    public const uint UnitedMgefId = 0x822;
    public const uint UnitedAbSpellId = 0x823;
    public const uint RobotMgefId = 0x824;
    public const uint RobotAbSpellId = 0x825;

    public const uint SquadTestCellId = 0x830;
    public const uint FireteamAlphaNpcId = 0x831;
    public const uint FireteamBravoNpcId = 0x832;
    public const uint FireteamCharlieNpcId = 0x833;
    public const uint FireteamDeltaNpcId = 0x834;
    public const uint FireteamAlphaRefId = 0x835;
    public const uint FireteamBravoRefId = 0x836;
    public const uint FireteamCharlieRefId = 0x837;
    public const uint FireteamDeltaRefId = 0x838;
    public const uint StoryCompanionNpcId = 0x839;
    public const uint StoryCompanionRefId = 0x83A;
    public const uint SquadTestCocRefId = 0x83B;
    public const uint SquadTestFloorRefId = 0x83C;

    const string QuestEdid = "FO4SF_CompanionsQuest";
    const string QuestScript = "FO4SF_CompanionsQuest";
    public const int ActiveSquadAliasId = 0;
    public static readonly ushort[] Stages = { 10, 20, 30, 40, 50, 60 };

    public static readonly string[] WheelButtons =
    {
        "Follow Me",
        "Wait / Hold Position",
        "Inspect Status & Loyalty",
        "Toggle Combat Stance",
        "Trade Gear & Ammo",
        "Check Affinity",
        "Dismiss",
        "Close",
    };

    public static readonly string[] FireteamButtons =
    {
        "All Follow / Regroup",
        "All Hold Position",
        "Stance: Aggressive",
        "Stance: Defensive",
        "Stance: Hold Fire",
        "Sync / Teleport Squad Now",
        "Inspect Fireteam (4 Slots)",
        "Close",
    };

    public static readonly string[] RecruitButtons =
    {
        "Recruit (Goodwill / Free)",
        "Hire Contract (Credits)",
        "Cancel",
    };

    public static readonly (uint NpcId, uint RefId, string NpcEdid, string RefEdid, string Name, float PosX, float PosY)[] FireteamSpecs =
    {
        (FireteamAlphaNpcId,   FireteamAlphaRefId,   "FO4SF_Fireteam_Alpha",   "FO4SF_FireteamRef_Alpha",   "Rifleman Alpha", -2.25f, 3.0f),
        (FireteamBravoNpcId,   FireteamBravoRefId,   "FO4SF_Fireteam_Bravo",   "FO4SF_FireteamRef_Bravo",   "Medic Bravo",    -0.75f, 3.5f),
        (FireteamCharlieNpcId, FireteamCharlieRefId, "FO4SF_Fireteam_Charlie", "FO4SF_FireteamRef_Charlie", "Heavy Charlie",   0.75f, 3.5f),
        (FireteamDeltaNpcId,   FireteamDeltaRefId,   "FO4SF_Fireteam_Delta",   "FO4SF_FireteamRef_Delta",   "Scout Delta",     2.25f, 3.0f),
    };

    static FormKey Own(uint id) => new(Plugin, id);
    static FormKey Sf(uint id) => new(SfEsm, id);

    static IStarfieldModDisposableGetter OpenTemplate(string path)
    {
        var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        styles.Set(new KeyedMasterStyle(SfEsm, MasterStyle.Full));
        return StarfieldMod.CreateFromBinaryOverlay(path, Release, new BinaryReadParameters { MasterFlagsLookup = styles });
    }

    sealed class ResolvedTemplates
    {
        public required IQuestGetter SqFollowers { get; init; }
        public required IQuestGetter SqGroups { get; init; }
        public required FormKey FollowPackage { get; init; }
        public required FormKey WaitPackage { get; init; }
        public required FormKey PlayerFaction { get; init; }
        public required INpcGetter HumanNpcTemplate { get; init; }
        public required IMiscItemGetter RadioMiscTemplate { get; init; }
        public required IStaticGetter CocMarkerStatic { get; init; }
        public required IStaticGetter FloorStatic { get; init; }
        public IMagicEffectGetter? AbilityEffectTemplate { get; init; }
        public ISpellGetter? AbilitySpellTemplate { get; init; }
        public required string Summary { get; init; }
    }

    static ResolvedTemplates ResolveTemplates(IStarfieldModGetter sf)
    {
        var sqFol = sf.Quests.FirstOrDefault(q => q.FormKey == Sf(SqFollowersQuestId))
                    ?? throw new Refusal("Starfield.esm lacks SQ_Followers (0x0000D773)");
        var sqGrp = sf.Quests.FirstOrDefault(q => q.FormKey == Sf(SqGroupsQuestId))
                    ?? throw new Refusal("Starfield.esm lacks SQ_Groups (0x001A9565)");

        var followPkg = sf.Packages.FirstOrDefault(p => p.FormKey == Sf(FollowPackageId))
                        ?? sf.Packages.FirstOrDefault(p => string.Equals(p.EditorID, "DefaultMaster_FollowPackage", StringComparison.OrdinalIgnoreCase))
                        ?? throw new Refusal("Starfield.esm lacks DefaultMaster_FollowPackage (0x000301C5)");
        var waitPkg = sf.Packages.FirstOrDefault(p => p.FormKey == Sf(WaitPackageId))
                      ?? sf.Packages.FirstOrDefault(p => string.Equals(p.EditorID, "SQ_Followers_Wait", StringComparison.OrdinalIgnoreCase))
                      ?? followPkg;

        var playerFact = sf.Factions.FirstOrDefault(f => f.FormKey == Sf(PlayerFactionId))
                         ?? throw new Refusal("Starfield.esm lacks PlayerFaction (0x0001C21C)");

        var npcTpl = sf.Npcs.FirstOrDefault(n => string.Equals(n.EditorID, "FC_Neon_GenericCustomerM01", StringComparison.OrdinalIgnoreCase))
                     ?? sf.Npcs.Where(n => !string.IsNullOrEmpty(n.EditorID) && (n.VirtualMachineAdapter?.Scripts.Count ?? 0) == 0)
                               .OrderBy(n => n.FormKey.ID).FirstOrDefault()
                     ?? throw new Refusal("Starfield.esm has no script-free NPC_ template");

        var radioTpl = sf.MiscItems.Where(m => m.Model != null && !string.IsNullOrEmpty(m.EditorID))
                         .OrderBy(m => string.Equals(m.EditorID, "Tool_DuctTape01", StringComparison.OrdinalIgnoreCase) ? 0 : 1)
                         .ThenBy(m => m.FormKey.ID).FirstOrDefault()
                       ?? throw new Refusal("Starfield.esm has no MISC template with a model");

        var cocStat = sf.Statics.FirstOrDefault(s => s.FormKey == Sf(CocMarkerStaticId))
                      ?? throw new Refusal("Starfield.esm lacks COCMarkerHeading (0x000032)");
        var floorStat = sf.Statics.FirstOrDefault(s => string.Equals(s.EditorID, "ShpGenIntAddOn_Panel_Floor01", StringComparison.OrdinalIgnoreCase))
                        ?? sf.Statics.Where(s => s.Model != null && s.FormKey != Sf(CocMarkerStaticId)).OrderBy(s => s.FormKey.ID).FirstOrDefault()
                        ?? cocStat;

        var abSp = sf.Spells.FirstOrDefault(sp => string.Equals(sp.EditorID, "abCrewAstrodynamics_01", StringComparison.OrdinalIgnoreCase))
                   ?? sf.Spells.FirstOrDefault(sp => sp.Type == Spell.SpellType.Ability && sp.Effects.Count >= 1);
        IMagicEffectGetter? abMg = null;
        if (abSp != null && abSp.Effects.Count > 0)
        {
            var ek = abSp.Effects[0].BaseEffect.FormKey;
            abMg = sf.MagicEffects.FirstOrDefault(m => m.FormKey == ek);
        }

        return new ResolvedTemplates
        {
            SqFollowers = sqFol,
            SqGroups = sqGrp,
            FollowPackage = followPkg.FormKey,
            WaitPackage = waitPkg.FormKey,
            PlayerFaction = playerFact.FormKey,
            HumanNpcTemplate = npcTpl,
            RadioMiscTemplate = radioTpl,
            CocMarkerStatic = cocStat,
            FloorStatic = floorStat,
            AbilityEffectTemplate = abMg,
            AbilitySpellTemplate = abSp,
            Summary = $"SQ_Followers={sqFol.FormKey.ID:X6}, SQ_Groups={sqGrp.FormKey.ID:X6}, " +
                      $"FollowPkg={followPkg.FormKey.ID:X6}, WaitPkg={waitPkg.FormKey.ID:X6}, " +
                      $"NPC={npcTpl.EditorID}, Floor={floorStat.EditorID}",
        };
    }

    // ---------------------------------------------------------------- record builders

    static Global MakeGlobal(uint id, string edid, float val) =>
        new(Own(id), Release)
        {
            EditorID = edid,
            FormVersion = 581,
            Data = val,
        };

    static ActorValueInformation MakeAvif(uint id, string edid, string name, string abbr, float defVal, float minVal, float maxVal) =>
        new(Own(id), Release)
        {
            EditorID = edid,
            Name = name,
            Abbreviation = abbr,
            FormVersion = 581,
            Type = ActorValueInformation.Types.Variable,
            DefaultValue = defVal,
            Min = minVal,
            Max = maxVal,
            Flags = defVal == 0f ? ActorValueInformation.Flag.DefaultToZero : 0,
        };

    static Message MakeMessageBox(uint id, string edid, string title, string desc, IEnumerable<string> buttons)
    {
        var msg = new Message(Own(id), Release)
        {
            EditorID = edid,
            Name = title,
            Description = desc,
            FormVersion = 581,
            Flags = Message.Flag.MessageBox,
        };
        foreach (var b in buttons)
            msg.MenuButtons.Add(new MessageButton { Text = b });
        return msg;
    }

    static MagicEffect MakeResistEffect(IMagicEffectGetter? tpl, uint id, string edid, string name, FormKey targetAv)
    {
        MagicEffect mg;
        if (tpl != null)
        {
            mg = (MagicEffect)tpl.Duplicate(Own(id), new MagicEffect.TranslationMask(defaultOn: true));
            mg.VirtualMachineAdapter = null;
            mg.Conditions.Clear();
            mg.Keywords = null;
            mg.CounterEffects.Clear();
        }
        else
        {
            mg = new MagicEffect(Own(id), Release) { FormVersion = 581 };
        }
        mg.EditorID = edid;
        mg.Name = name;
        mg.Description = name;
        mg.Archetype = new MagicEffectArchetype(MagicEffectArchetype.TypeEnum.ValueModifier);
        mg.CastType = CastType.ConstantEffect;
        mg.TargetType = TargetType.Self;
        mg.SecondActorValue.SetTo(targetAv);
        mg.Flags = MagicEffect.Flag.Recover | MagicEffect.Flag.NoDuration | MagicEffect.Flag.NoArea;
        return mg;
    }

    static Spell MakeAbilitySpell(ISpellGetter? tpl, uint id, string edid, string name, FormKey mgefKey, float magnitude)
    {
        Spell sp;
        if (tpl != null)
        {
            sp = (Spell)tpl.Duplicate(Own(id), new Spell.TranslationMask(defaultOn: true));
            sp.VirtualMachineAdapter = null;
            sp.Keywords = null;
            sp.Effects.Clear();
        }
        else
        {
            sp = new Spell(Own(id), Release) { FormVersion = 581 };
        }
        sp.EditorID = edid;
        sp.Name = name;
        sp.Description = name;
        sp.Type = Spell.SpellType.Ability;
        sp.CastType = CastType.ConstantEffect;
        sp.TargetType = TargetType.Self;
        sp.Effects.Add(new Effect
        {
            BaseEffect = new FormLinkNullable<IMagicEffectGetter>(mgefKey),
            Data = new EffectData { Magnitude = magnitude, Area = 0, Duration = 0 },
        });
        return sp;
    }

    static Perk MakePerk(uint id, string edid, string name, string desc, FormKey? abilitySpell = null)
    {
        var perk = new Perk(Own(id), Release)
        {
            EditorID = edid,
            Name = name,
            Description = desc,
            FormVersion = 581,
            Flags = Perk.Flag.PcPlayable,
            MajorFlags = Perk.MajorFlag.NonPlayable,
        };
        var rank = new PerkRank { UnknownStatic = new FormLinkNullable<IStaticGetter>(Sf(PerkUnknownStaticId)) };
        if (abilitySpell.HasValue)
            rank.Effects.Add(new PerkAbilityEffect { Ability = new FormLink<ISpellGetter>(abilitySpell.Value), Rank = 0, Priority = 0 });
        perk.Ranks.Add(rank);
        return perk;
    }

    static Npc CloneRecruitNpc(INpcGetter tpl, uint id, string edid, string name, FormKey factionKey, bool essential)
    {
        var npc = (Npc)tpl.Duplicate(Own(id), new Npc.TranslationMask(defaultOn: true) { Name = false });
        npc.EditorID = edid;
        npc.Name = name;
        npc.VirtualMachineAdapter = null;
        npc.Factions.Clear();
        npc.Factions.Add(new RankPlacement { Faction = new FormLink<IFactionGetter>(factionKey), Rank = 0 });
        npc.Packages.Clear();
        var cleanFlags = (npc.Flags | Npc.Flag.Unique) & ~(Npc.Flag.Respawn | Npc.Flag.Essential | Npc.Flag.Protected);
        npc.Flags = cleanFlags | (essential ? Npc.Flag.Essential : Npc.Flag.Protected);
        return npc;
    }

    static ScriptObjectProperty ObjProp(string name, FormKey fk, short alias = -1) => new()
    {
        Name = name,
        Flags = ScriptProperty.Flag.Edited,
        Object = new FormLink<IStarfieldMajorRecordGetter>(fk),
        Alias = alias,
        Unused = 0,
    };

    // ---------------------------------------------------------------- build

    public static int Build(string sfPath, string outDir, BuildOptions opts)
    {
        using var sf = OpenTemplate(sfPath);
        var tpl = ResolveTemplates(sf);

        var mod = new StarfieldMod(Plugin, Release);
        mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        mod.ModHeader.Author = "fo4-to-starfield CompanionsCore";

        // 1. Globals (0x801..0x806)
        var gBaseCap = MakeGlobal(SquadBaseCapGlobId, "FO4SF_SquadBaseCap", opts.BaseCap);
        var gMaxCap = MakeGlobal(SquadMaxCapGlobId, "FO4SF_SquadMaxCap", opts.MaxCap);
        var gMercCost = MakeGlobal(MercHireCostGlobId, "FO4SF_MercHireCost", opts.MercCost);
        var gMercShare = MakeGlobal(MercRewardShareGlobId, "FO4SF_MercRewardShare", opts.MercShare);
        var gActiveCnt = MakeGlobal(ActiveSquadCountGlobId, "FO4SF_ActiveSquadCount", 0f);
        var gStance = MakeGlobal(SquadStanceGlobId, "FO4SF_SquadStance", 0f);
        foreach (var g in new[] { gBaseCap, gMaxCap, gMercCost, gMercShare, gActiveCnt, gStance })
            mod.Globals.Add(g);

        // 2. AVIFs (0x807..0x80B)
        var avAffinity = MakeAvif(CompanionAffinityAvifId, "FO4SF_CompanionAffinity", "Companion Affinity", "Aff", 0f, 0f, 1000f);
        var avLoyalty = MakeAvif(SquadLoyaltyAvifId, "FO4SF_SquadLoyalty", "Squad Loyalty", "Loy", 75f, 0f, 100f);
        var avRank = MakeAvif(RecruitRankTierAvifId, "FO4SF_RecruitRankTier", "Recruit Rank Tier", "Rnk", 0f, 0f, 4f);
        var avOrder = MakeAvif(SquadOrderStateAvifId, "FO4SF_SquadOrderState", "Squad Order State", "Ord", 0f, 0f, 2f);
        var avNerve = MakeAvif(CompanionNerveBonusAvifId, "FO4SF_CompanionNerveBonus", "Companion Nerve Bonus", "Nrv", 0f, 0f, 100f);
        foreach (var av in new[] { avAffinity, avLoyalty, avRank, avOrder, avNerve })
            mod.ActorValueInformation.Add(av);

        // 3. Companion & Leadership Perks + Ability Modifiers (0x810..0x813, 0x822..0x825)
        var mgUnited = MakeResistEffect(tpl.AbilityEffectTemplate, UnitedMgefId, "FO4SF_UnitedWeStandEffect", "United We Stand Defense", Sf(DamageResistAvifId));
        var spUnited = MakeAbilitySpell(tpl.AbilitySpellTemplate, UnitedAbSpellId, "FO4SF_UnitedWeStandAb", "United We Stand Ability", mgUnited.FormKey, 20f);
        var mgRobot = MakeResistEffect(tpl.AbilityEffectTemplate, RobotMgefId, "FO4SF_RobotSympathyEffect", "Robot Sympathy Defense", Sf(EnergyResistAvifId));
        var spRobot = MakeAbilitySpell(tpl.AbilitySpellTemplate, RobotAbSpellId, "FO4SF_RobotSympathyAb", "Robot Sympathy Ability", mgRobot.FormKey, 15f);
        mod.MagicEffects.Add(mgUnited);
        mod.MagicEffects.Add(mgRobot);
        mod.Spells.Add(spUnited);
        mod.Spells.Add(spRobot);

        var pkUnited = MakePerk(PerkUnitedWeStandId, "FO4SF_CompPerk_UnitedWeStand", "United We Stand",
            "Idolized companion perk: grants +20 ballistic resistance during multi-foe engagements.", spUnited.FormKey);
        var pkRobot = MakePerk(PerkRobotSympathyId, "FO4SF_CompPerk_RobotSympathy", "Robot Sympathy",
            "Companion affinity perk: grants +15 energy resistance against automated threats.", spRobot.FormKey);
        var pkCmdr = MakePerk(PerkSquadCommanderId, "FO4SF_Perk_SquadCommander", "Squad Commander",
            "Unlocks the maximum 4-slot Warfare fireteam cap and authorizes veteran squad recruitment.");
        var pkSolo = MakePerk(PerkLoneWandererSoloId, "FO4SF_Perk_LoneWandererSolo", "Solo Operative",
            "Voluntarily sets active squad slot cap to 0 while solo bonuses are active.");
        foreach (var pk in new[] { pkUnited, pkRobot, pkCmdr, pkSolo })
            mod.Perks.Add(pk);

        // 4. Companion Wheel, Fireteam Command, and Recruit Prompt Messages (0x815..0x817)
        var msgWheel = MakeMessageBox(CompanionWheelMsgId, "FO4SF_CompanionWheelMsg", "Companion Tactical Wheel",
            "Select an order or logistics action for this squadmate:", WheelButtons);
        var msgFireteam = MakeMessageBox(FireteamCommandMsgId, "FO4SF_FireteamCommandMsg", "Warfare Fireteam Radio",
            "Issue a fireteam-wide order across all active squad slots:", FireteamButtons);
        var msgRecruit = MakeMessageBox(RecruitPromptMsgId, "FO4SF_RecruitPromptMsg", "Squad Recruitment",
            "Invite this specialist into your active Warfare fireteam?", RecruitButtons);
        mod.Messages.Add(msgWheel);
        mod.Messages.Add(msgFireteam);
        mod.Messages.Add(msgRecruit);

        // 5. Allied Squad Faction (0x818) & Tactical Fireteam Radio MISC + Filter FLST (0x820, 0x821)
        var allyFaction = new Faction(Own(SquadAllyFactionId), Release)
        {
            EditorID = "FO4SF_SquadAllyFaction",
            Name = "Commonwealth Warfare Fireteam",
            FormVersion = 581,
        };
        allyFaction.Relations.Add(new Relation
        {
            Target = new FormLink<IRelatableGetter>(tpl.PlayerFaction),
            Reaction = CombatReaction.Ally,
        });
        mod.Factions.Add(allyFaction);

        var radioToken = (MiscItem)tpl.RadioMiscTemplate.Duplicate(Own(SquadRadioTokenId), new MiscItem.TranslationMask(defaultOn: true) { Name = false });
        radioToken.EditorID = "FO4SF_SquadRadioToken";
        radioToken.Name = "Tactical Fireteam Radio";
        radioToken.VirtualMachineAdapter = null;
        radioToken.FeaturedItemMessage.Clear();
        radioToken.Keywords?.Clear();
        radioToken.Resources?.Clear();
        radioToken.Weight = 0.0f;
        radioToken.Value = 0;
        mod.MiscItems.Add(radioToken);

        var radioFilter = new FormList(Own(RadioFilterListId), Release) { EditorID = "FO4SF_RadioFilterList", FormVersion = 581 };
        radioFilter.Items.Add(radioToken.FormKey.ToLinkGetter<IStarfieldMajorRecordGetter>());
        mod.FormLists.Add(radioFilter);

        // 6. Squad Test Cell (0x830) + 4 Persistent Warfare Recruits (0x831..0x838) + Story Companion (0x839..0x83A)
        var cell = new Cell(Own(SquadTestCellId), Release)
        {
            EditorID = "FO4SF_SquadTestCell",
            Name = "Warfare Fireteam Staging Room",
            FormVersion = 581,
            Flags = Cell.Flag.IsInteriorCell,
            XILS = 1.0f,
        };
        var cocRef = new PlacedObject(Own(SquadTestCocRefId), Release)
        {
            EditorID = "FO4SF_SquadTestCell_COCMarker",
            Base = new FormLinkNullable<IPlaceableObjectGetter>(tpl.CocMarkerStatic.FormKey),
            Position = new P3Float(0f, 0f, 0f),
            Rotation = new P3Float(0f, 0f, 0f),
        };
        var floorRef = new PlacedObject(Own(SquadTestFloorRefId), Release)
        {
            EditorID = "FO4SF_SquadTestCell_Floor",
            Base = new FormLinkNullable<IPlaceableObjectGetter>(tpl.FloorStatic.FormKey),
            Position = new P3Float(0f, 2.0f, -0.1f),
            Rotation = new P3Float(0f, 0f, 0f),
        };
        cell.Temporary.Add(cocRef);
        cell.Temporary.Add(floorRef);

        var fireteamRefs = new List<PlacedNpc>();
        foreach (var fs in FireteamSpecs)
        {
            var rNpc = CloneRecruitNpc(tpl.HumanNpcTemplate, fs.NpcId, fs.NpcEdid, fs.Name, allyFaction.FormKey, essential: false);
            mod.Npcs.Add(rNpc);
            var rRef = new PlacedNpc(Own(fs.RefId), Release)
            {
                EditorID = fs.RefEdid,
                Base = new FormLink<INpcGetter>(rNpc.FormKey),
                Position = new P3Float(fs.PosX, fs.PosY, 0.05f),
                Rotation = new P3Float(0f, 0f, 3.14159f),
            };
            rRef.MajorRecordFlagsRaw |= 0x400; // Persistent so exterior Commonwealth tests can MoveTo them
            cell.Persistent.Add(rRef);
            fireteamRefs.Add(rRef);
        }

        var storyNpc = CloneRecruitNpc(tpl.HumanNpcTemplate, StoryCompanionNpcId, "FO4SF_StoryCompanion_Minuteman",
            "Minuteman Liaison", allyFaction.FormKey, essential: true);
        mod.Npcs.Add(storyNpc);
        var storyRef = new PlacedNpc(Own(StoryCompanionRefId), Release)
        {
            EditorID = "FO4SF_StoryCompanionRef",
            Base = new FormLink<INpcGetter>(storyNpc.FormKey),
            Position = new P3Float(0f, 4.5f, 0.05f),
            Rotation = new P3Float(0f, 0f, 3.14159f),
        };
        storyRef.MajorRecordFlagsRaw |= 0x400;
        cell.Persistent.Add(storyRef);

        int blockNum = (int)(SquadTestCellId % 10);
        int subBlockNum = (int)((SquadTestCellId / 10) % 10);
        var subBlock = new CellSubBlock { BlockNumber = subBlockNum, GroupType = GroupTypeEnum.InteriorCellSubBlock };
        subBlock.Cells.Add(cell);
        var cellBlock = new CellBlock { BlockNumber = blockNum, GroupType = GroupTypeEnum.InteriorCellBlock };
        cellBlock.SubBlocks.Add(subBlock);
        mod.Cells.Add(cellBlock);

        // 7. Quest FO4SF_CompanionsQuest (0x800) with RefCollectionAlias ActiveSquad + Script Properties
        var quest = new Quest(Own(QuestId), Release)
        {
            EditorID = QuestEdid,
            Name = "Companions and Warfare Squads",
            FormVersion = 581,
            Version2 = 12,
            Data = new QuestData { Flags = Quest.Flag.StartGameEnabled, Priority = 40 },
        };
        foreach (var s in Stages)
            quest.Stages.Add(new QuestStage { Index = s });

        var colAlias = new CollectionAlias
        {
            ID = ActiveSquadAliasId,
            MaxInitialFillCount = 0,
            ALAM = 0,
            ReferenceAlias = new QuestReferenceAlias
            {
                ID = ActiveSquadAliasId,
                Name = "ActiveSquad",
                Flags = QuestReferenceAlias.Flag.Optional | QuestReferenceAlias.Flag.AllowReserved,
                PackageData = new ExtendedList<IFormLinkGetter<IPackageGetter>>
                {
                    tpl.WaitPackage.ToLinkGetter<IPackageGetter>(),
                    tpl.FollowPackage.ToLinkGetter<IPackageGetter>(),
                },
            },
        };
        var qca = new QuestCollectionAlias();
        qca.Collection.Add(colAlias);
        (quest.Aliases ??= new ExtendedList<AQuestAlias>()).Add(qca);

        var script = new ScriptEntry { Name = QuestScript, Flags = ScriptEntry.Flag.Local };
        script.Properties.Add(ObjProp("ActiveSquad", quest.FormKey, alias: ActiveSquadAliasId));
        script.Properties.Add(ObjProp("SquadBaseCapGlob", gBaseCap.FormKey));
        script.Properties.Add(ObjProp("SquadMaxCapGlob", gMaxCap.FormKey));
        script.Properties.Add(ObjProp("MercHireCostGlob", gMercCost.FormKey));
        script.Properties.Add(ObjProp("MercRewardShareGlob", gMercShare.FormKey));
        script.Properties.Add(ObjProp("ActiveSquadCountGlob", gActiveCnt.FormKey));
        script.Properties.Add(ObjProp("SquadStanceGlob", gStance.FormKey));
        script.Properties.Add(ObjProp("CompanionAffinityAV", avAffinity.FormKey));
        script.Properties.Add(ObjProp("SquadLoyaltyAV", avLoyalty.FormKey));
        script.Properties.Add(ObjProp("RecruitRankTierAV", avRank.FormKey));
        script.Properties.Add(ObjProp("SquadOrderStateAV", avOrder.FormKey));
        script.Properties.Add(ObjProp("CompanionNerveBonusAV", avNerve.FormKey));
        script.Properties.Add(ObjProp("PerkUnitedWeStand", pkUnited.FormKey));
        script.Properties.Add(ObjProp("PerkRobotSympathy", pkRobot.FormKey));
        script.Properties.Add(ObjProp("PerkSquadCommander", pkCmdr.FormKey));
        script.Properties.Add(ObjProp("PerkLoneWandererSolo", pkSolo.FormKey));
        script.Properties.Add(ObjProp("CompanionWheelMsg", msgWheel.FormKey));
        script.Properties.Add(ObjProp("FireteamCommandMsg", msgFireteam.FormKey));
        script.Properties.Add(ObjProp("RecruitPromptMsg", msgRecruit.FormKey));
        script.Properties.Add(ObjProp("SquadAllyFaction", allyFaction.FormKey));
        script.Properties.Add(ObjProp("SquadRadioToken", radioToken.FormKey));
        script.Properties.Add(ObjProp("RadioFilterList", radioFilter.FormKey));
        script.Properties.Add(ObjProp("StoryCompanionRef", storyRef.FormKey));

        var ftListProp = new ScriptObjectListProperty { Name = "FireteamTestRefs", Flags = ScriptProperty.Flag.Edited };
        foreach (var fr in fireteamRefs)
            ftListProp.Objects.Add(ObjProp("", fr.FormKey));
        script.Properties.Add(ftListProp);

        quest.VirtualMachineAdapter = new QuestAdapter
        {
            Version = 6,
            ObjectFormat = 2,
            ExtraBindDataVersion = 3,
            Script = new ScriptEntry { Name = "", Flags = ScriptEntry.Flag.Local },
        };
        quest.VirtualMachineAdapter.Scripts.Add(script);
        mod.Quests.Add(quest);

        mod.ModHeader.Stats.NextFormID = 0x840;
        if (!mod.ModHeader.MasterReferences.Any(m => m.Master == SfEsm))
            mod.ModHeader.MasterReferences.Add(new MasterReference { Master = SfEsm });

        Write(mod, outDir, SfEsm);
        var outPath = Path.Combine(outDir, Plugin.FileName);
        Console.WriteLine($"templates: {tpl.Summary}");
        Console.WriteLine($"wrote {outPath} ({new FileInfo(outPath).Length:N0} bytes): " +
                          $"1 QUST (RefCollectionAlias ActiveSquad + 24 props), 6 GLOB (cap={opts.BaseCap}..{opts.MaxCap}, " +
                          $"merc={opts.MercCost}/{opts.MercShare.ToString("0.##", CultureInfo.InvariantCulture)}), " +
                          $"5 AVIF, 4 PERK, 3 MESG, 1 FACT, 1 MISC, 1 FLST, 1 CELL (4 Fireteam NPCs + 1 Story Companion)");
        return 0;
    }

    static void Write(StarfieldMod mod, string outDir, params ModKey[] masters)
    {
        Directory.CreateDirectory(outDir);
        var path = Path.Combine(outDir, mod.ModKey.FileName);
        var tmpDir = Path.Combine(outDir, ".tmp-" + Guid.NewGuid().ToString("N"));
        try
        {
            Directory.CreateDirectory(tmpDir);
            var tmp = Path.Combine(tmpDir, mod.ModKey.FileName);
            mod.BeginWrite.ToPath(tmp).WithLoadOrder(masters)
                .WithKnownMasters(masters.Select(m => new KeyedMasterStyle(m, MasterStyle.Full)).ToArray())
                .WithMastersListContent(MastersListContentOption.NoCheck).Write();
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
        using var sf = OpenTemplate(sfPath);
        var tpl = ResolveTemplates(sf);

        var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        styles.Set(new KeyedMasterStyle(SfEsm, MasterStyle.Full));
        using var mod = StarfieldMod.CreateFromBinaryOverlay(pluginPath, Release, new BinaryReadParameters { MasterFlagsLookup = styles });

        var problems = new List<string>();
        void Need(bool ok, string what) { if (!ok) problems.Add(what); }

        var masters = mod.ModHeader.MasterReferences.Select(m => m.Master).ToList();
        Console.WriteLine($"{Path.GetFileName(pluginPath)}: header {mod.ModHeader.Flags}, masters [{string.Join(", ", masters)}], next 0x{mod.ModHeader.Stats.NextFormID:X}");
        Need(mod.ModKey == Plugin, $"ModKey is {mod.ModKey}, expected {Plugin}");
        Need(mod.ModHeader.Flags.HasFlag(StarfieldModHeader.HeaderFlag.Master), "plugin header lacks Master flag");
        Need(masters.SequenceEqual(new[] { SfEsm }), $"masters are [{string.Join(", ", masters)}], expected [Starfield.esm]");

        var allRecs = mod.EnumerateMajorRecords().ToList();
        var foreign = allRecs.Where(r => r.FormKey.ModKey != Plugin).Select(r => r.FormKey.ToString()).ToList();
        Need(foreign.Count == 0, $"plugin contains foreign override records (must never override SQ_Followers/SQ_Groups): {string.Join(", ", foreign)}");
        var lowIds = allRecs.Where(r => r.FormKey.ModKey == Plugin && r.FormKey.ID < 0x800).Select(r => r.FormKey.ToString()).ToList();
        Need(lowIds.Count == 0, $"plugin contains low-range FormIDs (<0x800): {string.Join(", ", lowIds)}");

        // 1. Quest & RefCollectionAlias ActiveSquad check
        var q = mod.Quests.FirstOrDefault(x => x.FormKey == Own(QuestId));
        Need(q != null && q.EditorID == QuestEdid, $"missing QUST 0x{QuestId:X} ({QuestEdid})");
        if (q != null)
        {
            Need(q.Data?.Flags.HasFlag(Quest.Flag.StartGameEnabled) == true, $"{QuestEdid} lacks StartGameEnabled");
            Need(q.Stages.Select(s => s.Index).SequenceEqual(Stages), $"{QuestEdid} stages mismatch");
            var qca = q.Aliases?.OfType<IQuestCollectionAliasGetter>().FirstOrDefault();
            var ca = qca?.Collection.FirstOrDefault();
            Need(ca != null && ca.ReferenceAlias.Name == "ActiveSquad" &&
                 ca.ReferenceAlias.Flags?.HasFlag(QuestReferenceAlias.Flag.Optional) == true &&
                 ca.ReferenceAlias.Flags?.HasFlag(QuestReferenceAlias.Flag.AllowReserved) == true &&
                 (ca.ReferenceAlias.PackageData?.Any(p => p.FormKey == tpl.FollowPackage) ?? false),
                "ActiveSquad RefCollectionAlias missing Optional|AllowReserved or DefaultMaster_FollowPackage");
            var scripts = q.VirtualMachineAdapter?.Scripts.ToList() ?? new();
            Need(scripts.Count == 1 && scripts[0].Name == QuestScript && scripts[0].Properties.Count == 24,
                $"{QuestEdid} script {QuestScript} missing or property count != 24");
        }

        // 2. Globals check
        void CheckGlob(uint id, string edid, float expected)
        {
            var g = mod.Globals.FirstOrDefault(x => x.FormKey == Own(id));
            Need(g != null && g.EditorID == edid && !g.MajorFlags.HasFlag(Global.MajorFlag.Constant) &&
                 Math.Abs((g.Data ?? -999f) - expected) < 0.001f,
                $"GLOB 0x{id:X} ({edid}) missing, constant, or != {expected}");
        }
        CheckGlob(SquadBaseCapGlobId, "FO4SF_SquadBaseCap", opts.BaseCap);
        CheckGlob(SquadMaxCapGlobId, "FO4SF_SquadMaxCap", opts.MaxCap);
        CheckGlob(MercHireCostGlobId, "FO4SF_MercHireCost", opts.MercCost);
        CheckGlob(MercRewardShareGlobId, "FO4SF_MercRewardShare", opts.MercShare);
        CheckGlob(ActiveSquadCountGlobId, "FO4SF_ActiveSquadCount", 0f);
        CheckGlob(SquadStanceGlobId, "FO4SF_SquadStance", 0f);

        // 3. AVIFs check
        foreach (var (id, edid, maxV) in new[] {
            (CompanionAffinityAvifId, "FO4SF_CompanionAffinity", 1000f),
            (SquadLoyaltyAvifId, "FO4SF_SquadLoyalty", 100f),
            (RecruitRankTierAvifId, "FO4SF_RecruitRankTier", 4f),
            (SquadOrderStateAvifId, "FO4SF_SquadOrderState", 2f),
            (CompanionNerveBonusAvifId, "FO4SF_CompanionNerveBonus", 100f),
        })
        {
            var av = mod.ActorValueInformation.FirstOrDefault(x => x.FormKey == Own(id));
            Need(av != null && av.EditorID == edid && Math.Abs((av.Max ?? -1f) - maxV) < 0.01f,
                $"AVIF 0x{id:X} ({edid}) missing or max != {maxV}");
        }

        // 4. Perks, Messages, Radio MISC, and Faction check
        foreach (var (id, edid) in new[] {
            (PerkUnitedWeStandId, "FO4SF_CompPerk_UnitedWeStand"),
            (PerkRobotSympathyId, "FO4SF_CompPerk_RobotSympathy"),
            (PerkSquadCommanderId, "FO4SF_Perk_SquadCommander"),
            (PerkLoneWandererSoloId, "FO4SF_Perk_LoneWandererSolo"),
        })
        {
            var pk = mod.Perks.FirstOrDefault(x => x.FormKey == Own(id));
            Need(pk != null && pk.EditorID == edid && pk.Ranks.Count >= 1, $"PERK 0x{id:X} ({edid}) missing");
        }

        var wheel = mod.Messages.FirstOrDefault(x => x.FormKey == Own(CompanionWheelMsgId));
        var fireteam = mod.Messages.FirstOrDefault(x => x.FormKey == Own(FireteamCommandMsgId));
        var recruit = mod.Messages.FirstOrDefault(x => x.FormKey == Own(RecruitPromptMsgId));
        Need(wheel != null && wheel.EditorID == "FO4SF_CompanionWheelMsg" && wheel.MenuButtons.Count == WheelButtons.Length,
            "MESG FO4SF_CompanionWheelMsg missing or button count != 8");
        Need(fireteam != null && fireteam.EditorID == "FO4SF_FireteamCommandMsg" && fireteam.MenuButtons.Count == FireteamButtons.Length,
            "MESG FO4SF_FireteamCommandMsg missing or button count != 8");
        Need(recruit != null && recruit.EditorID == "FO4SF_RecruitPromptMsg" && recruit.MenuButtons.Count == RecruitButtons.Length,
            "MESG FO4SF_RecruitPromptMsg missing or button count != 3");

        var radio = mod.MiscItems.FirstOrDefault(x => x.FormKey == Own(SquadRadioTokenId));
        Need(radio != null && radio.EditorID == "FO4SF_SquadRadioToken" && radio.Model != null,
            "MISC FO4SF_SquadRadioToken missing or lacks model");

        var fact = mod.Factions.FirstOrDefault(x => x.FormKey == Own(SquadAllyFactionId));
        Need(fact != null && fact.Relations.Any(r => r.Target.FormKey == tpl.PlayerFaction && r.Reaction == CombatReaction.Ally),
            "FACT FO4SF_SquadAllyFaction missing Ally relation to PlayerFaction");

        // 5. SquadTestCell + 4 Persistent Fireteam Recruits + 1 Story Companion check
        var cell = mod.Cells.SelectMany(b => b.SubBlocks).SelectMany(sb => sb.Cells).FirstOrDefault(c => c.FormKey == Own(SquadTestCellId));
        Need(cell != null && cell.EditorID == "FO4SF_SquadTestCell" && (cell.Flags?.HasFlag(Cell.Flag.IsInteriorCell) == true),
            "CELL 0x830 (FO4SF_SquadTestCell) missing or not flagged IsInteriorCell");
        if (cell != null)
        {
            foreach (var fs in FireteamSpecs)
            {
                var npc = mod.Npcs.FirstOrDefault(n => n.FormKey == Own(fs.NpcId));
                var achr = cell.Persistent.OfType<IPlacedNpcGetter>().FirstOrDefault(r => r.FormKey == Own(fs.RefId));
                Need(npc != null && npc.EditorID == fs.NpcEdid && !npc.Flags.HasFlag(Npc.Flag.Essential) && npc.Flags.HasFlag(Npc.Flag.Protected),
                    $"Fireteam NPC {fs.NpcEdid} missing or not mortal/Protected");
                Need(achr != null && achr.EditorID == fs.RefEdid && achr.Base.FormKey == Own(fs.NpcId) && (achr.MajorRecordFlagsRaw & 0x400) != 0,
                    $"Fireteam ACHR {fs.RefEdid} missing or not Persistent");
            }
            var sNpc = mod.Npcs.FirstOrDefault(n => n.FormKey == Own(StoryCompanionNpcId));
            var sRef = cell.Persistent.OfType<IPlacedNpcGetter>().FirstOrDefault(r => r.FormKey == Own(StoryCompanionRefId));
            Need(sNpc != null && sNpc.Flags.HasFlag(Npc.Flag.Essential) && sRef != null && (sRef.MajorRecordFlagsRaw & 0x400) != 0,
                "Story Companion NPC/ACHR (0x839/0x83A) missing or not Essential+Persistent");
        }

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

        mod.Quests.Add(new Quest(Sf(SqFollowersQuestId), Release) { EditorID = "SQ_Followers" });
        mod.Quests.Add(new Quest(Sf(SqGroupsQuestId), Release) { EditorID = "SQ_Groups" });
        mod.Packages.Add(new Package(Sf(FollowPackageId), Release) { EditorID = "DefaultMaster_FollowPackage" });
        if (mode == "full")
            mod.Packages.Add(new Package(Sf(WaitPackageId), Release) { EditorID = "SQ_Followers_Wait" });

        mod.Factions.Add(new Faction(Sf(PlayerFactionId), Release) { EditorID = "PlayerFaction" });
        mod.Statics.Add(new Static(Sf(PerkUnknownStaticId), Release) { EditorID = "PerkUnknownStatic" });
        mod.Statics.Add(new Static(Sf(CocMarkerStaticId), Release) { EditorID = "COCMarkerHeading" });
        mod.Statics.Add(new Static(Sf(0x012235), Release)
        {
            EditorID = mode == "full" ? "ShpGenIntAddOn_Panel_Floor01" : "SynthFloor",
            Model = new Model { File = "Meshes\\Floor01.nif" },
        });

        mod.ActorValueInformation.Add(new ActorValueInformation(Sf(DamageResistAvifId), Release) { EditorID = "DamageResist" });
        mod.ActorValueInformation.Add(new ActorValueInformation(Sf(EnergyResistAvifId), Release) { EditorID = "EnergyResist" });
        mod.ActorValueInformation.Add(new ActorValueInformation(Sf(CharismaAvifId), Release) { EditorID = "Charisma" });

        mod.Npcs.Add(new Npc(Sf(0x003A09), Release)
        {
            EditorID = mode == "full" ? "FC_Neon_GenericCustomerM01" : "SynthHuman",
            Name = "Citizen",
        });
        mod.MiscItems.Add(new MiscItem(Sf(0x2AC95F), Release)
        {
            EditorID = mode == "full" ? "Tool_DuctTape01" : "SynthMisc",
            Name = "RadioShell",
            Model = new Model { File = "Meshes\\Radio.nif" },
        });

        if (mode == "full")
        {
            var mg = new MagicEffect(Sf(0x285E3F), Release)
            {
                EditorID = "abCrewAstrodynamicsEffect",
                Archetype = new MagicEffectArchetype(MagicEffectArchetype.TypeEnum.ValueModifier),
                CastType = CastType.ConstantEffect,
                TargetType = TargetType.Self,
                Flags = MagicEffect.Flag.Recover | MagicEffect.Flag.NoDuration | MagicEffect.Flag.NoArea,
            };
            mg.SecondActorValue.SetTo(Sf(DamageResistAvifId));
            mod.MagicEffects.Add(mg);

            var sp = new Spell(Sf(0x285E40), Release)
            {
                EditorID = "abCrewAstrodynamics_01",
                Type = Spell.SpellType.Ability,
                CastType = CastType.ConstantEffect,
                TargetType = TargetType.Self,
            };
            sp.Effects.Add(new Effect
            {
                BaseEffect = new FormLinkNullable<IMagicEffectGetter>(mg.FormKey),
                Data = new EffectData { Magnitude = 10f, Area = 0, Duration = 0 },
            });
            mod.Spells.Add(sp);
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
        return StarfieldMod.CreateFromBinary(pluginPath, Release, new BinaryReadParameters { MasterFlagsLookup = styles });
    }

    public static int SelfTest(string scratchDir)
    {
        Directory.CreateDirectory(scratchDir);
        var defOpts = new BuildOptions(2, 4, 250, 0.15f);
        foreach (var mode in new[] { "full", "minimal" })
        {
            var mDir = Path.Combine(scratchDir, "m_" + mode);
            var bDir = Path.Combine(scratchDir, "b_" + mode);
            if (Fixture(mDir, mode) != 0) throw new Refusal($"fixture {mode} failed");
            var sfPath = Path.Combine(mDir, "Starfield.esm");
            if (Build(sfPath, bDir, defOpts) != 0) throw new Refusal($"build {mode} failed");
            if (Check(Path.Combine(bDir, Plugin.FileName), sfPath, defOpts) != 0) throw new Refusal($"check {mode} failed");
        }

        var fullSf = Path.Combine(scratchDir, "m_full", "Starfield.esm");
        var customOpts = new BuildOptions(3, 6, 400, 0.20f);
        var optDir = Path.Combine(scratchDir, "b_opt");
        if (Build(fullSf, optDir, customOpts) != 0) throw new Refusal("build custom options failed");
        if (Check(Path.Combine(optDir, Plugin.FileName), fullSf, customOpts) != 0) throw new Refusal("check custom options failed");
        if (Check(Path.Combine(optDir, Plugin.FileName), fullSf, defOpts) == 0)
            throw new Refusal("check failed to reject mismatched cap/cost options");

        // 7 tamper negative controls
        var cleanPlugin = Path.Combine(scratchDir, "b_full", Plugin.FileName);
        int tIdx = 0;
        void ExpectTamperFail(string label, Action<StarfieldMod> mutate)
        {
            tIdx++;
            var tDir = Path.Combine(scratchDir, $"tamper_{tIdx}");
            var mod = OpenMutablePlugin(cleanPlugin);
            mutate(mod);
            Write(mod, tDir, SfEsm);
            if (Check(Path.Combine(tDir, Plugin.FileName), fullSf, defOpts) == 0)
                throw new Refusal($"tamper #{tIdx} ({label}) unexpectedly passed Check");
        }

        // 1. Foreign override of SQ_Followers injected
        ExpectTamperFail("override_sq_followers", m =>
            m.Quests.Add(new Quest(Sf(SqFollowersQuestId), Release) { EditorID = "SQ_Followers" }));

        // 2. ActiveSquad lacks AllowReserved
        ExpectTamperFail("missing_allow_reserved", m =>
        {
            var ca = m.Quests.First(q => q.FormKey == Own(QuestId)).Aliases!.OfType<QuestCollectionAlias>().First().Collection[0];
            ca.ReferenceAlias.Flags = QuestReferenceAlias.Flag.Optional;
        });

        // 3. BaseCap GLOB flagged Constant
        ExpectTamperFail("base_cap_constant", m =>
            m.Globals.First(g => g.FormKey == Own(SquadBaseCapGlobId)).MajorFlags |= Global.MajorFlag.Constant);

        // 4. Companion Wheel button removed
        ExpectTamperFail("wheel_button_removed", m =>
            m.Messages.First(x => x.FormKey == Own(CompanionWheelMsgId)).MenuButtons.RemoveAt(0));

        // 5. SquadAllyFaction stripped of PlayerFaction Ally relation
        ExpectTamperFail("ally_relation_removed", m =>
            m.Factions.First(f => f.FormKey == Own(SquadAllyFactionId)).Relations.Clear());

        // 6. Fireteam recruit improperly flagged Essential instead of mortal/Protected
        ExpectTamperFail("fireteam_essential", m =>
            m.Npcs.First(n => n.FormKey == Own(FireteamAlphaNpcId)).Flags |= Npc.Flag.Essential);

        // 7. SquadTestCell missing a persistent fireteam ACHR
        ExpectTamperFail("missing_fireteam_achr", m =>
            m.Cells[0].SubBlocks[0].Cells[0].Persistent.RemoveAt(0));

        Console.WriteLine("selftest: ok (full + minimal fixtures, custom cap/cost options, and 7 tamper controls passed)");
        return 0;
    }
}
