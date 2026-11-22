// NextStoryMissionsA4: Lane A A4 implementation for FO4SFMission.esm (zero overlap with 0x800..0x9FF).
//
// Completes FO4SF_Sanctuary01 (0x000817) IN PLACE from Fallout 4's Min01 (0x05DEE4) — NEVER creates a second
// Sanctuary quest — and adds FO4SF_MinRecruit00 (0x000A20, "The First Step", from MinRecruit00 0x11B36E) and
// FO4SF_MQ103 (0x000A50, "Jewel of the Commonwealth", from MQ103 0x0229E5 + DialogueDiamondCityEntrance 0x0190BC)
// behind the FO4SF_GameMode == 1 (Story) mission gate.
//
// Reserved local FormID map (0x000817 expanded in place; new records strictly in 0xA00..0xA7F):
//   Sanctuary (Min01 -> 0x000817 in place):
//     0xA00  NPC_  FO4_Sturges               (FO4 0x019FDA, HumanRace, Essential/Unique)
//     0xA01  ACHR  FO4SF_Sanctuary_SturgesREF (persistent in FO4Core_Commonwealth top cell)
//     0xA02..0xA0D  GLOB  FO4SF_Min01BedCount/Total/Percent, WaterCount/Total/Percent,
//                         FoodCount/Total/Percent, SafetyCount/Total/Percent (totals 5, 5, 5, 2)
//     0xA10..0xA14  MESG  FO4SF_Sanctuary01_SturgesTalkMsg + Reply0..3Msg (4-button clean-room boxes)
//   The First Step (MinRecruit00 -> 0x000A20):
//     0xA20  QUST  FO4SF_MinRecruit00        (stages 10, 50, 100, 200, 450, 500; objectives 10, 20, 30, 40)
//     0xA21  NPC_  FO4_TenpinesSpokesman     (HumanRace, Unique, non-essential for Open-Mode break-it)
//     0xA22  ACHR  FO4SF_Tenpines_SpokesmanREF (persistent at Tenpines Bluff local [-315, 1278, 87.8])
//     0xA23  NPC_  FO4_CorvegaBoss           (HumanRace raider boss, Unique)
//     0xA24  ACHR  FO4SF_Corvega_BossREF     (persistent marker/actor ref for Corvega target)
//     0xA25  MISC  FO4SF_FlareGun            (Minutemen recruitment reward token/flare gun stand-in)
//     0xA26  GLOB  FO4SF_Min02Unlocked       (set to 1 on stage 500 completion)
//     0xA28..0xA2B  MESG  FO4SF_MinRecruit00_TalkMsg..NoteMsg (clean-room settlement & note boxes)
//   Jewel of the Commonwealth (MQ103 -> 0x000A50):
//     0xA50  QUST  FO4SF_MQ103               (stages 10, 20, 25, 30, 100; objectives 10, 20, 30)
//     0xA51  NPC_  FO4_Piper                 (FO4 0x002F1E, HumanRace, Unique)
//     0xA52  ACHR  FO4SF_DiamondCity_PiperREF (persistent at DC gate local [-224, -433, 19.3])
//     0xA53  NPC_  FO4_MayorMcDonough        (FO4 0x002F08, HumanRace, Unique)
//     0xA54  ACHR  FO4SF_DiamondCity_MayorREF (persistent at DC gate local [-219, -431, 19.3])
//     0xA55  NPC_  FO4_ElliePerkins          (FO4 0x0222A2, HumanRace, Unique)
//     0xA56  ACHR  FO4SF_Valentines_EllieREF (persistent ref for agency handoff)
//     0xA57  GLOB  FO4SF_DCGateUnlocked      (0 -> 1 once Piper/Mayor or Open-Mode override opens gate)
//     0xA58  GLOB  FO4SF_MQ104Armed          (0 -> 1 on stage 100 handoff to Unlikely Valentine / Vault 114)
//     0xA60..0xA63  MESG  FO4SF_MQ103_GateTalkMsg..DossierMsg (clean-room gate & agency boxes)
//
// Zero copyrighted Fallout 4 dialogue appears in this file.

using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Records;
using Noggog;
using SF = Mutagen.Bethesda.Starfield;

static class NextStoryMissionsA4
{
    public const uint SanctuaryQuestId = 0x817; // Completed IN PLACE — never allocate a second Sanctuary quest

    // Sanctuary (Min01) companion records: 0xA00..0xA1F
    public const uint SturgesNpcId = 0xA00, SturgesRefId = 0xA01;
    public const string SturgesNpcEdid = "FO4_Sturges", SturgesRefEdid = "FO4SF_Sanctuary_SturgesREF";
    public const uint Min01BedCountId = 0xA02, Min01BedTotalId = 0xA03, Min01BedPercentId = 0xA04;
    public const uint Min01WaterCountId = 0xA05, Min01WaterTotalId = 0xA06, Min01WaterPercentId = 0xA07;
    public const uint Min01FoodCountId = 0xA08, Min01FoodTotalId = 0xA09, Min01FoodPercentId = 0xA0A;
    public const uint Min01SafetyCountId = 0xA0B, Min01SafetyTotalId = 0xA0C, Min01SafetyPercentId = 0xA0D;
    public const uint SturgesTalkMsgId = 0xA10, SturgesReply0MsgId = 0xA11, SturgesReply1MsgId = 0xA12,
                      SturgesReply2MsgId = 0xA13, SturgesDoneMsgId = 0xA14, WorkbenchBuildMsgId = 0xA15;

    // The First Step (MinRecruit00): 0xA20..0xA4F
    public const uint MinRecruit00QuestId = 0xA20;
    public const string MinRecruit00QuestEdid = "FO4SF_MinRecruit00", MinRecruit00ScriptName = "FO4SF_MinRecruit00Quest";
    public const uint TenpinesNpcId = 0xA21, TenpinesRefId = 0xA22;
    public const uint CorvegaBossNpcId = 0xA23, CorvegaBossRefId = 0xA24;
    public const uint FlareGunMiscId = 0xA25, Min02UnlockedGlobId = 0xA26;
    public const uint MinRecruitTalkMsgId = 0xA28, MinRecruitBriefMsgId = 0xA29,
                      MinRecruitRewardMsgId = 0xA2A, MinRecruitNoteMsgId = 0xA2B;

    // Jewel of the Commonwealth (MQ103): 0xA50..0xA7F
    public const uint Mq103QuestId = 0xA50;
    public const string Mq103QuestEdid = "FO4SF_MQ103", Mq103ScriptName = "FO4SF_MQ103Quest";
    public const uint PiperNpcId = 0xA51, PiperRefId = 0xA52;
    public const uint MayorNpcId = 0xA53, MayorRefId = 0xA54;
    public const uint EllieNpcId = 0xA55, EllieRefId = 0xA56;
    public const uint DcGateUnlockedGlobId = 0xA57, Mq104ArmedGlobId = 0xA58, GateProxyActiId = 0xA59;
    public const string GateProxyActiEdid = "FO4SF_MQ103_GateProxyActi";
    public const string GateProxyActiModel = Mission.CodsworthTalkActiModel;
    public const uint Mq103GateTalkMsgId = 0xA60, Mq103GateOpenMsgId = 0xA61,
                      Mq103AgencyTalkMsgId = 0xA62, Mq103DossierMsgId = 0xA63;

    public const uint MaxAllocatedId = 0xA64;

    public const float MergeOffsetX = -1200.0f;
    public const float MergeOffsetY = -2700.0f;

    public static bool IsA4ActorRefId(uint id) =>
        id is SturgesRefId or TenpinesRefId or CorvegaBossRefId or PiperRefId or MayorRefId or EllieRefId;

    // Exact FO4 Min01 resource target totals (verified from Fallout4.esm GLOBs 05FD8E/073041/073040/1DE910)
    public const float DefaultBedTotal = 5.0f;
    public const float DefaultWaterTotal = 5.0f;
    public const float DefaultFoodTotal = 5.0f;
    public const float DefaultSafetyTotal = 2.0f;

    // Stage arrays matching FO4 source + legacy stage 100 compat on Sanctuary01
    public static readonly ushort[] SanctuaryFullStages = { 10, 50, 100, 1000, 1050, 1200, 1250, 1300, 1350, 1400, 1450, 1500 };
    public static readonly ushort[] MinRecruit00Stages = { 10, 50, 100, 200, 450, 500 };
    public static readonly ushort[] Mq103Stages = { 10, 20, 25, 30, 100 };

    public static readonly (ushort Index, string Text, int TargetAlias)[] SanctuaryObjectives =
    {
        (10, "Activate the Sanctuary workbench", 0),
        (50, "Speak with Sturges in Sanctuary", 1),
        (1000, "Provide sheltered beds for Sanctuary settlers (5)", 0),
        (1050, "Report bed progress to Sturges", 1),
        (1200, "Provide clean water for Sanctuary settlers (5)", 0),
        (1250, "Report water progress to Sturges", 1),
        (1300, "Provide food for Sanctuary settlers (5)", 0),
        (1350, "Report food progress to Sturges", 1),
        (1400, "Build defenses for Sanctuary (2)", 0),
        (1450, "Report settlement readiness to Sturges", 1),
    };

    public static readonly (ushort Index, string Text, int TargetAlias)[] MinRecruit00Objectives =
    {
        (10, "Speak with the settlers at Tenpines Bluff", 0),
        (20, "Eliminate the raider leader at Corvega Assembly Plant", 1),
        (30, "Report back to Tenpines Bluff", 0),
        (40, "Report back to Preston Garvey", 2),
    };

    public static readonly (ushort Index, string Text, int TargetAlias)[] Mq103Objectives =
    {
        (10, "Travel to the Diamond City main gate", 0),
        (20, "Gain entry and ask about Shaun in Diamond City", 1),
        (30, "Visit Valentine Detective Agency", 2),
    };

    static SF.ScriptObjectProperty ObjProp(string name, FormKey fk) => new()
    {
        Name = name,
        Flags = SF.ScriptProperty.Flag.Edited,
        Object = new FormLink<SF.IStarfieldMajorRecordGetter>(fk),
        Alias = -1,
        Unused = 0,
    };

    static SF.QuestAdapter MakeAdapter(SF.ScriptEntry entry)
    {
        var vm = new SF.QuestAdapter
        {
            Version = 6,
            ObjectFormat = 2,
            ExtraBindDataVersion = 3,
            Script = new SF.ScriptEntry { Name = "", Flags = SF.ScriptEntry.Flag.Local },
        };
        vm.Scripts.Add(entry);
        return vm;
    }

    static SF.Global AddGlob(SF.StarfieldMod mod, ModKey modKey, uint id, string edid, float value)
    {
        var g = new SF.Global(new FormKey(modKey, id), SF.StarfieldRelease.Starfield)
        {
            EditorID = edid,
            Data = value,
        };
        mod.Globals.Add(g);
        return g;
    }

    static SF.Message AddMessage(SF.StarfieldMod mod, ModKey modKey, uint id, string edid, string title, string body, params string[] buttons)
    {
        var msg = new SF.Message(new FormKey(modKey, id), SF.StarfieldRelease.Starfield)
        {
            EditorID = edid,
            Name = title,
            Description = body,
            Flags = SF.Message.Flag.MessageBox,
        };
        foreach (var b in buttons)
            msg.MenuButtons.Add(new SF.MessageButton { Text = b });
        mod.Messages.Add(msg);
        return msg;
    }

    static SF.INpcGetter PickFemaleTemplate(SF.IStarfieldModGetter sf, FormKey humanRace, SF.INpcGetter fallback) =>
        sf.Npcs.FirstOrDefault(n =>
            n.Race.FormKey == humanRace &&
            n.Flags.HasFlag(SF.Npc.Flag.Female) &&
            !string.IsNullOrEmpty(n.EditorID) &&
            n.DefaultTemplate.IsNull)
        ?? sf.Npcs.FirstOrDefault(n => n.Race.FormKey == humanRace && n.Flags.HasFlag(SF.Npc.Flag.Female))
        ?? fallback;

    static FormKey PickFemaleVoice(SF.IStarfieldModGetter sf, FormKey fallbackVoice) =>
        sf.VoiceTypes.FirstOrDefault(v =>
            v.EditorID == "GenericFemaleEvenToned" && v.Flags.HasFlag(SF.VoiceType.Flag.AllowDefaultDialog))?.FormKey
        ?? sf.VoiceTypes.FirstOrDefault(v =>
            v.EditorID is not null && v.EditorID.Contains("Female", StringComparison.OrdinalIgnoreCase) &&
            v.Flags.HasFlag(SF.VoiceType.Flag.AllowDefaultDialog))?.FormKey
        ?? fallbackVoice;

    static SF.Npc CloneHumanNpc(
        SF.StarfieldMod mod,
        ModKey modKey,
        uint id,
        string edid,
        string displayName,
        SF.INpcGetter template,
        FormKey humanRace,
        FormKey voiceType,
        FormKey? factionKey,
        bool essential,
        bool female = false,
        string? activateTextOverride = "Talk")
    {
        var npc = (SF.Npc)template.Duplicate(new FormKey(modKey, id));
        npc.EditorID = edid;
        npc.Name = displayName;
        npc.Race.SetTo(humanRace);
        npc.Voice.SetTo(voiceType);
        npc.VirtualMachineAdapter = null;
        npc.Packages.Clear();
        npc.DefaultTemplate.Clear();
        npc.TemplateActors = null;
        npc.CrimeFaction.Clear();
        npc.ActivateTextOverride = activateTextOverride;
        var flags = (npc.Flags | SF.Npc.Flag.Unique | SF.Npc.Flag.AutoCalcStats)
                    & ~(SF.Npc.Flag.Respawn | SF.Npc.Flag.Protected);
        flags = essential ? (flags | SF.Npc.Flag.Essential) : (flags & ~SF.Npc.Flag.Essential);
        flags = female ? (flags | SF.Npc.Flag.Female) : (flags & ~SF.Npc.Flag.Female);
        npc.Flags = flags;
        npc.Factions.Clear();
        if (factionKey is { } fk)
            npc.Factions.Add(new SF.RankPlacement { Faction = new FormLink<SF.IFactionGetter>(fk), Rank = 0 });
        mod.Npcs.Add(npc);
        return npc;
    }

    static SF.Npc CloneHostileBossNpc(
        SF.StarfieldMod mod,
        ModKey modKey,
        uint id,
        string edid,
        string displayName,
        SF.INpcGetter raiderTemplate,
        FormKey weaponKey,
        FormKey ammoKey)
    {
        var npc = (SF.Npc)raiderTemplate.Duplicate(new FormKey(modKey, id));
        npc.EditorID = edid;
        npc.Name = displayName;
        npc.VirtualMachineAdapter = null;
        npc.DefaultTemplate.Clear();
        npc.TemplateActors = null;
        npc.CrimeFaction.Clear();
        npc.ActivateTextOverride = null;
        var flags = (npc.Flags | SF.Npc.Flag.Unique | SF.Npc.Flag.AutoCalcStats)
                    & ~(SF.Npc.Flag.Essential | SF.Npc.Flag.Protected | SF.Npc.Flag.Respawn);
        npc.Flags = flags;
        npc.Items ??= new ExtendedList<SF.ContainerEntry>();
        if (!npc.Items.Any(i => i.Item.Item.FormKey == weaponKey))
            npc.Items.Add(new SF.ContainerEntry { Item = new SF.ContainerItem { Item = new FormLink<SF.IItemGetter>(weaponKey), Count = 1 } });
        if (!npc.Items.Any(i => i.Item.Item.FormKey == ammoKey))
            npc.Items.Add(new SF.ContainerEntry { Item = new SF.ContainerItem { Item = new FormLink<SF.IItemGetter>(ammoKey), Count = 50 } });
        mod.Npcs.Add(npc);
        return npc;
    }

    static SF.PlacedNpc PlacePersistentActor(
        SF.Cell persistentCell,
        ModKey modKey,
        uint id,
        string edid,
        FormKey npcBase,
        float x,
        float y,
        float z,
        float rotZ)
    {
        var a = new SF.PlacedNpc(new FormKey(modKey, id), SF.StarfieldRelease.Starfield)
        {
            EditorID = edid,
            Base = new FormLink<SF.INpcGetter>(npcBase),
            Position = new P3Float(x, y, z),
            Rotation = new P3Float(0f, 0f, rotZ),
        };
        a.MajorRecordFlagsRaw |= 0x400; // Persistent
        persistentCell.Persistent.Add(a);
        return a;
    }

    /// <summary>
    /// Expands FO4SF_Sanctuary01 (0x000817) IN PLACE and adds FO4SF_MinRecruit00 (0x000A20) and FO4SF_MQ103 (0x000A50)
    /// into FO4SFMission.esm. Preserves all existing 0x800..0x9FF FormIDs.
    /// </summary>
    public static void PopulateA4Missions(
        SF.StarfieldMod mod,
        SF.Cell persistentCell,
        SF.Quest sanctuaryQuest,
        FormKey prestonRefKey,
        FormKey minutemenFactionKey,
        FormKey questTypeSideKey,
        FormKey xMarkerKey,
        SF.IStarfieldModGetter sfMod,
        SF.INpcGetter humanTemplate,
        FormKey humanRaceKey,
        FormKey humanVoiceKey,
        SF.INpcGetter raiderTemplate,
        FormKey raiderCombatPackKey,
        FormKey raiderSandboxPackKey,
        FormKey weaponKey,
        FormKey ammoKey)
    {
        var modKey = mod.ModKey;
        var rel = SF.StarfieldRelease.Starfield;
        var femaleTemplate = PickFemaleTemplate(sfMod, humanRaceKey, humanTemplate);
        var femaleVoiceKey = PickFemaleVoice(sfMod, humanVoiceKey);

        // ------------------------------------------------------------------ 1. Sanctuary (Min01 -> 0x000817 IN PLACE)
        var sturgesNpc = CloneHumanNpc(mod, modKey, SturgesNpcId, SturgesNpcEdid, "Sturges",
            humanTemplate, humanRaceKey, humanVoiceKey, minutemenFactionKey, essential: false, female: false);
        // Merged Sanctuary Hills coords beside workbench (-1127.0 + -1200, 1281.5 + -2700, 112.1)
        var sturgesRef = PlacePersistentActor(persistentCell, modKey, SturgesRefId, SturgesRefEdid,
            sturgesNpc.FormKey, -1127.0f + MergeOffsetX, 1281.5f + MergeOffsetY, 112.1f, 3.14f);

        var bedCount = AddGlob(mod, modKey, Min01BedCountId, "FO4SF_Min01BedCount", 0f);
        var bedTotal = AddGlob(mod, modKey, Min01BedTotalId, "FO4SF_Min01BedTotal", DefaultBedTotal);
        var bedPct = AddGlob(mod, modKey, Min01BedPercentId, "FO4SF_Min01BedPercent", 0f);
        var waterCount = AddGlob(mod, modKey, Min01WaterCountId, "FO4SF_Min01WaterCount", 0f);
        var waterTotal = AddGlob(mod, modKey, Min01WaterTotalId, "FO4SF_Min01WaterTotal", DefaultWaterTotal);
        var waterPct = AddGlob(mod, modKey, Min01WaterPercentId, "FO4SF_Min01WaterPercent", 0f);
        var foodCount = AddGlob(mod, modKey, Min01FoodCountId, "FO4SF_Min01FoodCount", 0f);
        var foodTotal = AddGlob(mod, modKey, Min01FoodTotalId, "FO4SF_Min01FoodTotal", DefaultFoodTotal);
        var foodPct = AddGlob(mod, modKey, Min01FoodPercentId, "FO4SF_Min01FoodPercent", 0f);
        var safetyCount = AddGlob(mod, modKey, Min01SafetyCountId, "FO4SF_Min01SafetyCount", 0f);
        var safetyTotal = AddGlob(mod, modKey, Min01SafetyTotalId, "FO4SF_Min01SafetyTotal", DefaultSafetyTotal);
        var safetyPct = AddGlob(mod, modKey, Min01SafetyPercentId, "FO4SF_Min01SafetyPercent", 0f);

        var sturgesTalk = AddMessage(mod, modKey, SturgesTalkMsgId, "FO4SF_Sanctuary01_SturgesTalkMsg",
            "Sturges", "Sanctuary needs shelter, clean water, food, and defenses to support the settlers.",
            "Check settlement needs", "Ask about the workshop", "Ask about the survivors", "I will get on it");
        var sturgesReply0 = AddMessage(mod, modKey, SturgesReply0MsgId, "FO4SF_Sanctuary01_SturgesReply0Msg",
            "Sturges", "Start with sheltered beds, then clean water, food crops, and defensive turrets.",
            "Continue");
        var sturgesReply1 = AddMessage(mod, modKey, SturgesReply1MsgId, "FO4SF_Sanctuary01_SturgesReply1Msg",
            "Sturges", "Use the red workshop bench across the street to build supplies anywhere inside Sanctuary.",
            "Continue");
        var sturgesReply2 = AddMessage(mod, modKey, SturgesReply2MsgId, "FO4SF_Sanctuary01_SturgesReply2Msg",
            "Sturges", "Everyone is still shaken up after Concord, but having a safe camp changes everything.",
            "Continue");
        var sturgesDone = AddMessage(mod, modKey, SturgesDoneMsgId, "FO4SF_Sanctuary01_SturgesDoneMsg",
            "Sturges", "Sanctuary has shelter, water, food, and defenses. Check in with Preston about nearby settlements.",
            "Finish");
        var workbenchBuild = AddMessage(mod, modKey, WorkbenchBuildMsgId, "FO4SF_Sanctuary01_WorkbenchBuildMsg",
            "Sanctuary Workbench", "Build supplies for Sanctuary settlers using the workshop bench.",
            "Build Sheltered Bed (+1)", "Build Water Pump (+1)", "Plant Food Crops (+1)", "Build Settlement Defense (+1)", "Done");

        // Expand FO4SF_Sanctuary01 (0x000817) in place (B1/B4: QSDT on every stage, FNAM=0 on every objective, no StartsEnabled/0x10000)
        sanctuaryQuest.Name = "Sanctuary";
        if (sanctuaryQuest.Data is not null)
        {
            sanctuaryQuest.Data.Flags = SF.Quest.Flag.AllowRepeatedStages | SF.Quest.Flag.DisplaysInHud | SF.Quest.Flag.RunOnce;
        }
        sanctuaryQuest.Stages.Clear();
        foreach (var stIdx in SanctuaryFullStages)
        {
            var st = new SF.QuestStage { Index = stIdx };
            st.LogEntries.Add(new SF.QuestLogEntry
            {
                Flags = stIdx == 1500 ? SF.QuestLogEntry.Flag.CompleteQuest : (SF.QuestLogEntry.Flag)0,
            });
            sanctuaryQuest.Stages.Add(st);
        }
        sanctuaryQuest.Aliases ??= new ExtendedList<SF.AQuestAlias>();
        if (!sanctuaryQuest.Aliases.OfType<SF.QuestReferenceAlias>().Any(a => a.ID == 1))
        {
            sanctuaryQuest.Aliases.Add(new SF.QuestReferenceAlias
            {
                ID = 1,
                Name = "Sturges",
                Flags = SF.AQuestAlias.Flag.Optional | SF.AQuestAlias.Flag.AllowReserved |
                        SF.AQuestAlias.Flag.AllowDisabled | SF.AQuestAlias.Flag.AllowDead,
                ForcedReference = new FormLinkNullable<SF.IPlacedGetter>(sturgesRef.FormKey),
            });
        }
        sanctuaryQuest.Objectives.Clear();
        foreach (var (oid, otext, aliasId) in SanctuaryObjectives)
        {
            var obj = new SF.QuestObjective { Index = oid, Flags = (SF.QuestObjective.Flag)0, DisplayText = otext };
            obj.Targets.Add(new SF.QuestObjectiveTarget { AliasID = aliasId });
            sanctuaryQuest.Objectives.Add(obj);
        }
        var sEntry = sanctuaryQuest.VirtualMachineAdapter?.Scripts.FirstOrDefault(s => s.Name == "FO4SF_Sanctuary01Quest");
        if (sEntry is null)
        {
            sEntry = new SF.ScriptEntry { Name = "FO4SF_Sanctuary01Quest", Flags = SF.ScriptEntry.Flag.Local };
            sEntry.Properties.Add(ObjProp("XMarkerBase", xMarkerKey));
            sanctuaryQuest.VirtualMachineAdapter = MakeAdapter(sEntry);
        }
        void SetProp(SF.ScriptEntry se, string name, FormKey fk)
        {
            se.Properties.RemoveAll(p => p.Name == name);
            se.Properties.Add(ObjProp(name, fk));
        }
        SetProp(sEntry, "Sturges", sturgesRef.FormKey);
        SetProp(sEntry, "BedCount", bedCount.FormKey);
        SetProp(sEntry, "BedTotal", bedTotal.FormKey);
        SetProp(sEntry, "BedPercent", bedPct.FormKey);
        SetProp(sEntry, "WaterCount", waterCount.FormKey);
        SetProp(sEntry, "WaterTotal", waterTotal.FormKey);
        SetProp(sEntry, "WaterPercent", waterPct.FormKey);
        SetProp(sEntry, "FoodCount", foodCount.FormKey);
        SetProp(sEntry, "FoodTotal", foodTotal.FormKey);
        SetProp(sEntry, "FoodPercent", foodPct.FormKey);
        SetProp(sEntry, "SafetyCount", safetyCount.FormKey);
        SetProp(sEntry, "SafetyTotal", safetyTotal.FormKey);
        SetProp(sEntry, "SafetyPercent", safetyPct.FormKey);
        SetProp(sEntry, "SturgesTalkMsg", sturgesTalk.FormKey);
        SetProp(sEntry, "SturgesReply0Msg", sturgesReply0.FormKey);
        SetProp(sEntry, "SturgesReply1Msg", sturgesReply1.FormKey);
        SetProp(sEntry, "SturgesReply2Msg", sturgesReply2.FormKey);
        SetProp(sEntry, "SturgesDoneMsg", sturgesDone.FormKey);
        SetProp(sEntry, "WorkbenchBuildMsg", workbenchBuild.FormKey);

        // ------------------------------------------------------------------ 2. The First Step (MinRecruit00 -> 0x000A20)
        var tenpinesNpc = CloneHumanNpc(mod, modKey, TenpinesNpcId, "FO4_TenpinesSpokesman", "Tenpines Settler",
            humanTemplate, humanRaceKey, humanVoiceKey, null, essential: false, female: false);
        var tenpinesRef = PlacePersistentActor(persistentCell, modKey, TenpinesRefId, "FO4SF_Tenpines_SpokesmanREF",
            tenpinesNpc.FormKey, -315.0f + MergeOffsetX, 1278.0f + MergeOffsetY, 87.8f, 3.0f);

        var corvegaBossNpc = CloneHostileBossNpc(mod, modKey, CorvegaBossNpcId, "FO4_CorvegaBoss", "Raider Leader",
            raiderTemplate, weaponKey, ammoKey);
        var corvegaBossRef = PlacePersistentActor(persistentCell, modKey, CorvegaBossRefId, "FO4SF_Corvega_BossREF",
            corvegaBossNpc.FormKey, -512.0f + MergeOffsetX, 479.0f + MergeOffsetY, 54.0f, 0.0f);

        var flareGun = new SF.MiscItem(new FormKey(modKey, FlareGunMiscId), rel)
        {
            EditorID = "FO4SF_FlareGun",
            Name = "Minutemen Flare Gun",
            Value = 50,
            Weight = 2.0f,
        };
        mod.MiscItems.Add(flareGun);

        var min02Unlocked = AddGlob(mod, modKey, Min02UnlockedGlobId, "FO4SF_Min02Unlocked", 0f);
        var mrTalk = AddMessage(mod, modKey, MinRecruitTalkMsgId, "FO4SF_MinRecruit00_TalkMsg",
            "Tenpines Bluff", "Raiders operating out of the Corvega Assembly Plant have been attacking this farm.",
            "Ask about the raiders", "Ask where Corvega is", "Agree to clear Corvega", "Leave");
        var mrBrief = AddMessage(mod, modKey, MinRecruitBriefMsgId, "FO4SF_MinRecruit00_BriefMsg",
            "Tenpines Bluff", "Clear the raider leader at Corvega Assembly Plant south of here, then return.",
            "Continue");
        var mrReward = AddMessage(mod, modKey, MinRecruitRewardMsgId, "FO4SF_MinRecruit00_RewardMsg",
            "Tenpines Bluff", "With Corvega cleared, Tenpines Bluff pledges support to the Minutemen.",
            "Continue");
        var mrNote = AddMessage(mod, modKey, MinRecruitNoteMsgId, "FO4SF_MinRecruit00_NoteMsg",
            "Settlement Request Note", "Raiders from Corvega Assembly Plant hit Tenpines Bluff. Eliminate their leader to secure the farm.",
            "Continue");

        var mrQuest = new SF.Quest(new FormKey(modKey, MinRecruit00QuestId), rel)
        {
            EditorID = MinRecruit00QuestEdid,
            Name = "The First Step",
            FormVersion = 581,
            Version2 = 12,
            Data = new SF.QuestData
            {
                Flags = SF.Quest.Flag.AllowRepeatedStages | SF.Quest.Flag.DisplaysInHud | SF.Quest.Flag.RunOnce,
                Priority = 76,
            },
        };
        mrQuest.QuestType.SetTo(questTypeSideKey);
        foreach (var stIdx in MinRecruit00Stages)
        {
            var st = new SF.QuestStage { Index = stIdx };
            st.LogEntries.Add(new SF.QuestLogEntry
            {
                Flags = stIdx == 500 ? SF.QuestLogEntry.Flag.CompleteQuest : (SF.QuestLogEntry.Flag)0,
            });
            mrQuest.Stages.Add(st);
        }
        mrQuest.Aliases = new ExtendedList<SF.AQuestAlias>
        {
            new SF.QuestReferenceAlias
            {
                ID = 0, Name = "TenpinesSpokesman",
                Flags = SF.AQuestAlias.Flag.Optional | SF.AQuestAlias.Flag.AllowReserved |
                        SF.AQuestAlias.Flag.AllowDisabled | SF.AQuestAlias.Flag.AllowDead,
                ForcedReference = new FormLinkNullable<SF.IPlacedGetter>(tenpinesRef.FormKey),
            },
            new SF.QuestReferenceAlias
            {
                ID = 1, Name = "CorvegaBoss",
                Flags = SF.AQuestAlias.Flag.Optional | SF.AQuestAlias.Flag.AllowReserved |
                        SF.AQuestAlias.Flag.AllowDisabled | SF.AQuestAlias.Flag.AllowDead,
                ForcedReference = new FormLinkNullable<SF.IPlacedGetter>(corvegaBossRef.FormKey),
                PackageData =
                {
                    new FormLink<SF.IPackageGetter>(raiderCombatPackKey),
                    new FormLink<SF.IPackageGetter>(raiderSandboxPackKey),
                },
            },
            new SF.QuestReferenceAlias
            {
                ID = 2, Name = "PrestonGarvey",
                Flags = SF.AQuestAlias.Flag.Optional | SF.AQuestAlias.Flag.AllowReserved |
                        SF.AQuestAlias.Flag.AllowDisabled | SF.AQuestAlias.Flag.AllowDead,
                ForcedReference = new FormLinkNullable<SF.IPlacedGetter>(prestonRefKey),
            },
        };
        foreach (var (oid, otext, aliasId) in MinRecruit00Objectives)
        {
            var obj = new SF.QuestObjective { Index = oid, Flags = (SF.QuestObjective.Flag)0, DisplayText = otext };
            obj.Targets.Add(new SF.QuestObjectiveTarget { AliasID = aliasId });
            mrQuest.Objectives.Add(obj);
        }
        var mrScript = new SF.ScriptEntry { Name = MinRecruit00ScriptName, Flags = SF.ScriptEntry.Flag.Local };
        mrScript.Properties.Add(ObjProp("XMarkerBase", xMarkerKey));
        mrScript.Properties.Add(ObjProp("TenpinesSpokesman", tenpinesRef.FormKey));
        mrScript.Properties.Add(ObjProp("CorvegaBoss", corvegaBossRef.FormKey));
        mrScript.Properties.Add(ObjProp("Preston", prestonRefKey));
        mrScript.Properties.Add(ObjProp("FlareGun", flareGun.FormKey));
        mrScript.Properties.Add(ObjProp("Min02Unlocked", min02Unlocked.FormKey));
        mrScript.Properties.Add(ObjProp("MinutemenFaction", minutemenFactionKey));
        mrScript.Properties.Add(ObjProp("TalkMsg", mrTalk.FormKey));
        mrScript.Properties.Add(ObjProp("BriefMsg", mrBrief.FormKey));
        mrScript.Properties.Add(ObjProp("RewardMsg", mrReward.FormKey));
        mrScript.Properties.Add(ObjProp("NoteMsg", mrNote.FormKey));
        mrQuest.VirtualMachineAdapter = MakeAdapter(mrScript);
        mod.Quests.Add(mrQuest);

        // ------------------------------------------------------------------ 3. Jewel of the Commonwealth (MQ103 -> 0x000A50)
        var piperNpc = CloneHumanNpc(mod, modKey, PiperNpcId, "FO4_Piper", "Piper",
            femaleTemplate, humanRaceKey, femaleVoiceKey, null, essential: false, female: true);
        var piperRef = PlacePersistentActor(persistentCell, modKey, PiperRefId, "FO4SF_DiamondCity_PiperREF",
            piperNpc.FormKey, -224.0f + MergeOffsetX, -433.0f + MergeOffsetY, 19.3f, 0.5f);

        var mayorNpc = CloneHumanNpc(mod, modKey, MayorNpcId, "FO4_MayorMcDonough", "Mayor McDonough",
            humanTemplate, humanRaceKey, humanVoiceKey, null, essential: false, female: false);
        var mayorRef = PlacePersistentActor(persistentCell, modKey, MayorRefId, "FO4SF_DiamondCity_MayorREF",
            mayorNpc.FormKey, -219.0f + MergeOffsetX, -431.0f + MergeOffsetY, 19.3f, 3.6f);

        var ellieNpc = CloneHumanNpc(mod, modKey, EllieNpcId, "FO4_ElliePerkins", "Ellie Perkins",
            femaleTemplate, humanRaceKey, femaleVoiceKey, null, essential: false, female: true);
        // Post-gate / Valentine's Agency side (past Diamond City main gate, never beside Piper outside the locked gate)
        var ellieRef = PlacePersistentActor(persistentCell, modKey, EllieRefId, "FO4SF_Valentines_EllieREF",
            ellieNpc.FormKey, -192.0f + MergeOffsetX, -402.0f + MergeOffsetY, 19.3f, 0.0f);

        var dcGateUnlocked = AddGlob(mod, modKey, DcGateUnlockedGlobId, "FO4SF_DCGateUnlocked", 0f);
        var mq104Armed = AddGlob(mod, modKey, Mq104ArmedGlobId, "FO4SF_MQ104Armed", 0f);
        var gateProxyActi = new SF.Activator(new FormKey(modKey, GateProxyActiId), rel)
        {
            EditorID = GateProxyActiEdid,
            Name = "Diamond City Gate Controls",
            ActivateTextOverride = "Activate",
            MarkerColor = System.Drawing.Color.FromArgb(0, 0xCC, 0x4C, 0x33),
            Flags = (SF.Activator.Flag)0,
            ActivationAngle = 360,
            InvertFacing = false,
            ObjectBounds = new SF.ObjectBounds
            {
                First = new P3Float(-0.25f, -0.25f, -0.25f),
                Second = new P3Float(0.25f, 0.25f, 0.25f),
            },
            Model = new SF.Model { File = new Mutagen.Bethesda.Plugins.Assets.AssetLink<Mutagen.Bethesda.Starfield.Assets.StarfieldModelAssetType>(GateProxyActiModel) },
        };
        mod.Activators.Add(gateProxyActi);

        var mqGateTalk = AddMessage(mod, modKey, Mq103GateTalkMsgId, "FO4SF_MQ103_GateTalkMsg",
            "Diamond City Gate", "A reporter at the intercom offers to help open the Diamond City gate.",
            "Play along to open the gate", "Ask about Diamond City", "Ask about missing people", "Use gate override");
        var mqGateOpen = AddMessage(mod, modKey, Mq103GateOpenMsgId, "FO4SF_MQ103_GateOpenMsg",
            "Diamond City Gate", "The main gate unlocks. Head inside and seek out Valentine Detective Agency.",
            "Continue");
        var mqAgencyTalk = AddMessage(mod, modKey, Mq103AgencyTalkMsgId, "FO4SF_MQ103_AgencyTalkMsg",
            "Valentine Detective Agency", "Ellie Perkins says Nick Valentine went missing on a case at Park Street Station (Vault 114).",
            "Ask about Nick", "Ask about Park Street Station", "Offer to find Nick", "Finish");
        var mqDossier = AddMessage(mod, modKey, Mq103DossierMsgId, "FO4SF_MQ103_DossierMsg",
            "Detective Agency Case Dossier", "Active case notes place Nick Valentine at Park Street Station near Vault 114.",
            "Continue");

        var mq103 = new SF.Quest(new FormKey(modKey, Mq103QuestId), rel)
        {
            EditorID = Mq103QuestEdid,
            Name = "Jewel of the Commonwealth",
            FormVersion = 581,
            Version2 = 12,
            Data = new SF.QuestData
            {
                Flags = SF.Quest.Flag.AllowRepeatedStages | SF.Quest.Flag.DisplaysInHud | SF.Quest.Flag.RunOnce,
                Priority = 70,
            },
        };
        mq103.QuestType.SetTo(questTypeSideKey);
        foreach (var stIdx in Mq103Stages)
        {
            var st = new SF.QuestStage { Index = stIdx };
            st.LogEntries.Add(new SF.QuestLogEntry
            {
                Flags = stIdx == 100 ? SF.QuestLogEntry.Flag.CompleteQuest : (SF.QuestLogEntry.Flag)0,
            });
            mq103.Stages.Add(st);
        }
        mq103.Aliases = new ExtendedList<SF.AQuestAlias>
        {
            new SF.QuestReferenceAlias
            {
                ID = 0, Name = "DiamondCityGate",
                Flags = SF.AQuestAlias.Flag.Optional | SF.AQuestAlias.Flag.AllowReserved | SF.AQuestAlias.Flag.AllowDisabled,
            },
            new SF.QuestReferenceAlias
            {
                ID = 1, Name = "Piper",
                Flags = SF.AQuestAlias.Flag.Optional | SF.AQuestAlias.Flag.AllowReserved |
                        SF.AQuestAlias.Flag.AllowDisabled | SF.AQuestAlias.Flag.AllowDead,
                ForcedReference = new FormLinkNullable<SF.IPlacedGetter>(piperRef.FormKey),
            },
            new SF.QuestReferenceAlias
            {
                ID = 2, Name = "Ellie",
                Flags = SF.AQuestAlias.Flag.Optional | SF.AQuestAlias.Flag.AllowReserved |
                        SF.AQuestAlias.Flag.AllowDisabled | SF.AQuestAlias.Flag.AllowDead,
                ForcedReference = new FormLinkNullable<SF.IPlacedGetter>(ellieRef.FormKey),
            },
        };
        foreach (var (oid, otext, aliasId) in Mq103Objectives)
        {
            var obj = new SF.QuestObjective { Index = oid, Flags = (SF.QuestObjective.Flag)0, DisplayText = otext };
            obj.Targets.Add(new SF.QuestObjectiveTarget { AliasID = aliasId });
            mq103.Objectives.Add(obj);
        }
        var mqScript = new SF.ScriptEntry { Name = Mq103ScriptName, Flags = SF.ScriptEntry.Flag.Local };
        mqScript.Properties.Add(ObjProp("XMarkerBase", xMarkerKey));
        mqScript.Properties.Add(ObjProp("GateProxyActi", gateProxyActi.FormKey));
        mqScript.Properties.Add(ObjProp("Piper", piperRef.FormKey));
        mqScript.Properties.Add(ObjProp("Mayor", mayorRef.FormKey));
        mqScript.Properties.Add(ObjProp("Ellie", ellieRef.FormKey));
        mqScript.Properties.Add(ObjProp("DCGateUnlocked", dcGateUnlocked.FormKey));
        mqScript.Properties.Add(ObjProp("MQ104Armed", mq104Armed.FormKey));
        mqScript.Properties.Add(ObjProp("GateTalkMsg", mqGateTalk.FormKey));
        mqScript.Properties.Add(ObjProp("GateOpenMsg", mqGateOpen.FormKey));
        mqScript.Properties.Add(ObjProp("AgencyTalkMsg", mqAgencyTalk.FormKey));
        mqScript.Properties.Add(ObjProp("DossierMsg", mqDossier.FormKey));
        mq103.VirtualMachineAdapter = MakeAdapter(mqScript);
        mod.Quests.Add(mq103);
    }

    public static void CheckA4Missions(
        SF.IStarfieldModGetter plug,
        ModKey sfEsm,
        uint questTypeSideId,
        Action<bool, string> need)
    {
        var key = plug.ModKey;
        static bool NonStartGameReady(SF.IQuestGetter q) =>
            q.Data is not null && !q.Data.Flags.HasFlag(SF.Quest.Flag.StartGameEnabled) &&
            !q.Data.Flags.HasFlag(SF.Quest.Flag.StartsEnabled) && (((uint)q.Data.Flags & 0x10000u) == 0);

        // 1. Sanctuary01 (0x000817) expanded IN PLACE (zero duplicate Sanctuary quests)
        var sanctuaryQuests = plug.Quests.Where(q => q.EditorID is not null && q.EditorID.Contains("Sanctuary", StringComparison.OrdinalIgnoreCase)).ToList();
        need(sanctuaryQuests.Count == 1 && sanctuaryQuests[0].FormKey == new FormKey(key, SanctuaryQuestId),
            "FO4SF_Sanctuary01 must exist once at 0x000817 (completed in place, no second Sanctuary quest)");
        var sq = sanctuaryQuests.FirstOrDefault();
        if (sq is not null)
        {
            need(NonStartGameReady(sq) && sq.Data!.Flags.HasFlag(SF.Quest.Flag.RunOnce) && sq.Data.Flags.HasFlag(SF.Quest.Flag.DisplaysInHud),
                "FO4SF_Sanctuary01 flags invalid (must be RunOnce | DisplaysInHud without StartGameEnabled/StartsEnabled/0x10000)");
            need(sq.Stages.Select(s => s.Index).SequenceEqual(SanctuaryFullStages),
                "FO4SF_Sanctuary01 stages mismatch SanctuaryFullStages");
            need(sq.Stages.All(s => s.LogEntries.Count >= 1 && s.LogEntries[0].Flags is not null),
                "FO4SF_Sanctuary01 has a stage without QSDT QuestLogEntry");
            need(sq.Stages.Last().LogEntries.Any(l => l.Flags?.HasFlag(SF.QuestLogEntry.Flag.CompleteQuest) == true),
                "FO4SF_Sanctuary01 stage 1500 lacks CompleteQuest");
            need(sq.Objectives.Select(o => o.Index).SequenceEqual(SanctuaryObjectives.Select(o => o.Index)) &&
                 sq.Objectives.All(o => o.Flags is not null),
                "FO4SF_Sanctuary01 objectives mismatch Min01 specification or lack Flags");
            need(sq.QuestType.FormKey == new FormKey(sfEsm, questTypeSideId),
                "FO4SF_Sanctuary01 QuestType mismatch");
            var sal = (sq.Aliases ?? new List<SF.IAQuestAliasGetter>()).OfType<SF.IQuestReferenceAliasGetter>().FirstOrDefault(a => a.ID == 0);
            need(sal is not null && (sal.Flags ?? 0).HasFlag(SF.AQuestAlias.Flag.Optional) && (sal.Flags ?? 0).HasFlag(SF.AQuestAlias.Flag.AllowReserved),
                "FO4SF_Sanctuary01 lacks optional SanctuaryWorkbench alias 0");
            var ss = sq.VirtualMachineAdapter?.Scripts.FirstOrDefault(x => x.Name == "FO4SF_Sanctuary01Quest");
            need(ss is not null && ss.Properties.FirstOrDefault(p => p.Name == "XMarkerBase") is SF.IScriptObjectPropertyGetter xp &&
                 xp.Object.FormKey == new FormKey(sfEsm, 0x00003B),
                "FO4SF_Sanctuary01 lacks FO4SF_Sanctuary01Quest with XMarkerBase -> Starfield.esm:00003B");
            need(ss is not null && ss.Properties.FirstOrDefault(p => p.Name == "WorkbenchBuildMsg") is SF.IScriptObjectPropertyGetter wbp &&
                 wbp.Object.FormKey == new FormKey(key, WorkbenchBuildMsgId),
                "FO4SF_Sanctuary01 lacks WorkbenchBuildMsg -> 0x000A15");
        }
        var wbMsg = plug.Messages.FirstOrDefault(m => m.FormKey == new FormKey(key, WorkbenchBuildMsgId));
        need(wbMsg is { EditorID: "FO4SF_Sanctuary01_WorkbenchBuildMsg" } && wbMsg.MenuButtons.Count == 5,
            "FO4SF_Sanctuary01_WorkbenchBuildMsg (0x000A15) missing or != 5 buttons");
        need(plug.Globals.FirstOrDefault(g => g.FormKey == new FormKey(key, Min01BedTotalId))?.Data == DefaultBedTotal &&
             plug.Globals.FirstOrDefault(g => g.FormKey == new FormKey(key, Min01WaterTotalId))?.Data == DefaultWaterTotal &&
             plug.Globals.FirstOrDefault(g => g.FormKey == new FormKey(key, Min01FoodTotalId))?.Data == DefaultFoodTotal &&
             plug.Globals.FirstOrDefault(g => g.FormKey == new FormKey(key, Min01SafetyTotalId))?.Data == DefaultSafetyTotal,
             "Min01 resource total GLOBs (5, 5, 5, 2) missing or mismatched");

        // 2. MinRecruit00 (0x000A20)
        var mr = plug.Quests.FirstOrDefault(q => q.FormKey == new FormKey(key, MinRecruit00QuestId));
        need(mr is { EditorID: MinRecruit00QuestEdid } && NonStartGameReady(mr) &&
             mr.Data!.Flags.HasFlag(SF.Quest.Flag.RunOnce) && mr.Data.Flags.HasFlag(SF.Quest.Flag.DisplaysInHud) &&
             mr.QuestType.FormKey == new FormKey(sfEsm, questTypeSideId),
            "FO4SF_MinRecruit00 (0x000A20) missing or invalid flags/QuestType");
        if (mr is not null)
        {
            need(mr.Stages.Select(s => s.Index).SequenceEqual(MinRecruit00Stages), "FO4SF_MinRecruit00 stages mismatch");
            need(mr.Stages.All(s => s.LogEntries.Count >= 1 && s.LogEntries[0].Flags is not null), "FO4SF_MinRecruit00 has a stage without QSDT QuestLogEntry");
            need(mr.Objectives.Select(o => o.Index).SequenceEqual(MinRecruit00Objectives.Select(o => o.Index)) &&
                 mr.Objectives.All(o => o.Flags is not null), "FO4SF_MinRecruit00 objectives mismatch or lack Flags");
            need(mr.VirtualMachineAdapter?.Scripts.Any(s => s.Name == MinRecruit00ScriptName) == true, "FO4SF_MinRecruit00 lacks script binding");
        }
        need(plug.MiscItems.Any(m => m.FormKey == new FormKey(key, FlareGunMiscId) && m.EditorID == "FO4SF_FlareGun"),
            "FO4SF_FlareGun reward item (0x000A25) missing");

        // 3. MQ103 (0x000A50)
        var mq = plug.Quests.FirstOrDefault(q => q.FormKey == new FormKey(key, Mq103QuestId));
        need(mq is { EditorID: Mq103QuestEdid } && NonStartGameReady(mq) &&
             mq.Data!.Flags.HasFlag(SF.Quest.Flag.RunOnce) && mq.Data.Flags.HasFlag(SF.Quest.Flag.DisplaysInHud) &&
             mq.QuestType.FormKey == new FormKey(sfEsm, questTypeSideId),
            "FO4SF_MQ103 (0x000A50) missing or invalid flags/QuestType");
        if (mq is not null)
        {
            need(mq.Stages.Select(s => s.Index).SequenceEqual(Mq103Stages), "FO4SF_MQ103 stages mismatch");
            need(mq.Stages.All(s => s.LogEntries.Count >= 1 && s.LogEntries[0].Flags is not null), "FO4SF_MQ103 has a stage without QSDT QuestLogEntry");
            need(mq.Objectives.Select(o => o.Index).SequenceEqual(Mq103Objectives.Select(o => o.Index)) &&
                 mq.Objectives.All(o => o.Flags is not null), "FO4SF_MQ103 objectives mismatch or lack Flags");
            need(mq.VirtualMachineAdapter?.Scripts.Any(s => s.Name == Mq103ScriptName) == true, "FO4SF_MQ103 lacks script binding");
        }
        need(plug.Globals.Any(g => g.FormKey == new FormKey(key, DcGateUnlockedGlobId)) &&
             plug.Globals.Any(g => g.FormKey == new FormKey(key, Mq104ArmedGlobId)),
             "FO4SF_MQ103 GLOBs (0x000A57 / 0x000A58) missing");
        var gpActi = plug.Activators.FirstOrDefault(a => a.FormKey == new FormKey(key, GateProxyActiId));
        need(gpActi is { EditorID: GateProxyActiEdid, ActivationAngle: 360, InvertFacing: false } &&
             gpActi.ActivateTextOverride?.String == "Activate" &&
             string.Equals(gpActi.Model?.File?.GivenPath, GateProxyActiModel, StringComparison.OrdinalIgnoreCase) &&
             gpActi.ObjectBounds is { First.X: -0.25f, Second.X: 0.25f },
            "FO4SF_MQ103_GateProxyActi (0x000A59) missing or invalid");
        var bossNpc = plug.Npcs.FirstOrDefault(n => n.FormKey == new FormKey(key, CorvegaBossNpcId));
        need(bossNpc is { EditorID: "FO4_CorvegaBoss" } &&
             !bossNpc.Flags.HasFlag(SF.Npc.Flag.Essential) && !bossNpc.Flags.HasFlag(SF.Npc.Flag.Protected) && !bossNpc.Flags.HasFlag(SF.Npc.Flag.Respawn) &&
             bossNpc.ActivateTextOverride is null && (bossNpc.Items?.Count ?? 0) >= 2,
            "FO4_CorvegaBoss (0x000A23) must be hostile non-essential/non-protected armed boss without Talk override");
        var bossAlias = (mr?.Aliases ?? new List<SF.IAQuestAliasGetter>()).OfType<SF.IQuestReferenceAliasGetter>().FirstOrDefault(a => a.ID == 1);
        need(bossAlias is not null && bossAlias.PackageData.Count >= 2,
            "FO4SF_MinRecruit00 CorvegaBoss alias 1 lacks combat/sandbox packages");
        var piperNpcCheck = plug.Npcs.FirstOrDefault(n => n.FormKey == new FormKey(key, PiperNpcId));
        var ellieNpcCheck = plug.Npcs.FirstOrDefault(n => n.FormKey == new FormKey(key, EllieNpcId));
        need(piperNpcCheck is not null && piperNpcCheck.Flags.HasFlag(SF.Npc.Flag.Female) &&
             ellieNpcCheck is not null && ellieNpcCheck.Flags.HasFlag(SF.Npc.Flag.Female),
            "FO4_Piper (0x000A51) and FO4_ElliePerkins (0x000A55) must carry Female flag");
        // Verify all 6 A4 persistent ACHRs are placed at merged Commonwealth coordinates (X < -1000, Y < -1000)
        var topRefs = plug.Worldspaces.FirstOrDefault()?.TopCell?.Persistent.OfType<SF.IPlacedNpcGetter>()
            .Where(r => IsA4ActorRefId(r.FormKey.ID)).ToList() ?? [];
        need(topRefs.Count == 6 && topRefs.All(r => r.Position.X < -1000f && r.Position.Y < -1000f),
            "A4 persistent ACHRs must all be placed at merged Commonwealth coordinates");
    }
}
