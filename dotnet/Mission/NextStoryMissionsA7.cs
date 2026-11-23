// NextStoryMissionsA7: Lane A A7 implementation for FO4SFMission.esm (strictly 0xA80..0xAFF).
//
// Adds FO4SF_MQ104 (0x000A80, "Unlikely Valentine", source-audited from Fallout 4's MQ104 0x01F25E) and
// FO4SF_MQ105 (0x000AB0, "Getting a Clue", source-audited from Fallout 4's MQ105 0x0229E6) behind the
// FO4SF_GameMode == 1 (Story) mission gate, with Open-Mode (W7) dead-giver fallbacks and clean handoff
// to FO4SFFortHagen.esm (0D) / MQ106 (Reunions).
//
// Reserved local FormID map (zero overlap with 0x800..0x9FF, A4 0xA00..0xA7F, or A7b 0xB00..0xB7F;
// sits directly inside A5's 0x800..0xAFF Pip-Boy DATA/Quests live scan window):
//   Unlikely Valentine (MQ104 -> 0x000A80..0x000AAF):
//     0xA80  QUST  FO4SF_MQ104                  (stages 10, 20, 40, 60, 85, 100, 200; objectives 10, 20, 30, 40)
//     0xA81  NPC_  FO4_NickValentine            (FO4 0x002F24, HumanRace stand-in, Unique, non-essential for W7)
//     0xA82  ACHR  FO4SF_Vault114_NickREF       (persistent at Park Street Station local [212.54, -227.73, 19.2])
//     0xA83  NPC_  FO4_SkinnyMalone             (FO4 0x083FB4, HumanRace, Unique, non-essential)
//     0xA84  ACHR  FO4SF_Vault114_SkinnyMaloneREF (persistent at Vault 114 exit local [114.57, -258.22, 19.2])
//     0xA85  NPC_  FO4_Darla                    (FO4 0x0969D9, HumanRace, Unique, non-essential)
//     0xA86  ACHR  FO4SF_Vault114_DarlaREF      (persistent beside Skinny Malone [117.0, -257.0, 19.2])
//     0xA87  GLOB  FO4SF_Vault114NickFreed      (0 -> 1 once Nick's cell 0x0007E7A4 / terminal 0x000ADA18 unlocked)
//     0xA88  GLOB  FO4SF_Vault114ExitUnlocked   (0 -> 1 once 0x0008A80C / 0x0007C051 unlocked)
//     0xA89  GLOB  FO4SF_MQ105Armed             (0 -> 1 on stage 200 handoff to Getting a Clue 0x000AB0)
//     0xA90..0xA93  MESG  FO4SF_MQ104_NickCellTalkMsg..DebriefMsg (clean-room rescue, case-notes & Malone boxes)
//   Getting a Clue (MQ105 -> 0x000AB0..0x000AFF):
//     0xAB0  QUST  FO4SF_MQ105                  (stages 10, 30, 60, 80, 100, 200; objectives 10, 30, 60, 80)
//     0xAB1  NPC_  FO4_Geneva                   (FO4 0x002F0A, HumanRace, Unique, non-essential for W7)
//     0xAB2  ACHR  FO4SF_DiamondCity_GenevaREF  (persistent at Diamond City hub [-218.0, -425.0, 19.3])
//     0xAB3  NPC_  FO4_DogmeatTrailGuide        (Unique trail scout stand-in, non-essential for W7)
//     0xAB4  ACHR  FO4SF_DiamondCity_DogmeatREF (persistent outside Diamond City gate [-222.0, -435.0, 19.3])
//     0xAB5  MISC  FO4SF_KelloggCigar           (Kellogg's cigar clue item in DmndStandsKellogg01)
//     0xAB6  GLOB  FO4SF_KelloggHouseUnlocked   (0 -> 1 once 0x000021B4 opened by key/lockpick/override)
//     0xAB7  GLOB  FO4SF_KelloggSecretOpened    (0 -> 1 once 0x0011E23C button opens 0x0011E235)
//     0xAB8  GLOB  FO4SF_MQ106Armed             (0 -> 1 on stage 200 Fort Hagen handoff to MQ106 Reunions)
//     0xAC0..0xAC4  MESG  FO4SF_MQ105_AgencyBriefMsg..TrailHandoffMsg (clean-room briefing, dossier & trail boxes)
//
// Zero copyrighted Fallout 4 dialogue appears in this file.

using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Records;
using Noggog;
using SF = Mutagen.Bethesda.Starfield;

static class NextStoryMissionsA7
{
    // Unlikely Valentine (MQ104): 0xA80..0xAAF
    public const uint Mq104QuestId = 0xA80;
    public const string Mq104QuestEdid = "FO4SF_MQ104", Mq104ScriptName = "FO4SF_MQ104Quest";
    public const uint NickNpcId = 0xA81, NickRefId = 0xA82;
    public const uint SkinnyMaloneNpcId = 0xA83, SkinnyMaloneRefId = 0xA84;
    public const uint DarlaNpcId = 0xA85, DarlaRefId = 0xA86;
    public const uint Vault114NickFreedGlobId = 0xA87;
    public const uint Vault114ExitUnlockedGlobId = 0xA88;
    public const uint Mq105ArmedGlobId = 0xA89;
    public const uint NickTalkActiId = 0xA8A, MaloneTalkActiId = 0xA8B;
    public const string NickTalkActiEdid = "FO4SF_MQ104_NickTalkActi",
                        MaloneTalkActiEdid = "FO4SF_MQ104_MaloneTalkActi";
    public const string TalkProxyActiModel = Mission.CodsworthTalkActiModel;
    public const uint Mq104NickCellTalkMsgId = 0xA90, Mq104CaseNotesMsgId = 0xA91,
                      Mq104MaloneTalkMsgId = 0xA92, Mq104DebriefMsgId = 0xA93;

    // Getting a Clue (MQ105): 0xAB0..0xAFF
    public const uint Mq105QuestId = 0xAB0;
    public const string Mq105QuestEdid = "FO4SF_MQ105", Mq105ScriptName = "FO4SF_MQ105Quest";
    public const uint GenevaNpcId = 0xAB1, GenevaRefId = 0xAB2;
    public const uint DogmeatNpcId = 0xAB3, DogmeatRefId = 0xAB4;
    public const uint KelloggCigarMiscId = 0xAB5;
    public const uint KelloggHouseUnlockedGlobId = 0xAB6;
    public const uint KelloggSecretOpenedGlobId = 0xAB7;
    public const uint Mq106ArmedGlobId = 0xAB8;
    public const uint GenevaTalkActiId = 0xAB9, DogmeatTalkActiId = 0xABA;
    public const string GenevaTalkActiEdid = "FO4SF_MQ105_GenevaTalkActi",
                        DogmeatTalkActiEdid = "FO4SF_MQ105_DogmeatTalkActi";
    public const uint Mq105AgencyBriefMsgId = 0xAC0, Mq105AgencyDossierMsgId = 0xAC1,
                      Mq105GenevaKeyMsgId = 0xAC2, Mq105SecretRoomMsgId = 0xAC3,
                      Mq105TrailHandoffMsgId = 0xAC4;

    public const uint MaxAllocatedId = 0xAC5;

    public static bool IsA7ActorRefId(uint id) =>
        id is NickRefId or SkinnyMaloneRefId or DarlaRefId or GenevaRefId or DogmeatRefId;

    public static readonly ushort[] Mq104Stages = { 10, 20, 40, 60, 85, 100, 200 };
    public static readonly ushort[] Mq105Stages = { 10, 30, 60, 80, 100, 200 };

    public static readonly (ushort Index, string Text, int TargetAlias)[] Mq104Objectives =
    {
        (10, "Search Park Street Station for Nick Valentine", 0),
        (20, "Rescue Nick Valentine inside Vault 114", 0),
        (30, "Escape Vault 114 with Nick Valentine", 1),
        (40, "Meet Nick Valentine at his agency in Diamond City", 0),
    };

    public static readonly (ushort Index, string Text, int TargetAlias)[] Mq105Objectives =
    {
        (10, "Sit down and brief Nick Valentine at his agency", 0),
        (30, "Gain access to Kellogg's house in Diamond City", 1),
        (60, "Search Kellogg's house for a hidden room and clues", 0),
        (80, "Follow the cigar trail to Fort Hagen", 2),
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
        bool essential,
        bool female = false)
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
        npc.ActivateTextOverride = "Talk";
        var flags = (npc.Flags | SF.Npc.Flag.Unique | SF.Npc.Flag.AutoCalcStats) & ~(SF.Npc.Flag.Respawn | SF.Npc.Flag.Protected);
        flags = essential ? (flags | SF.Npc.Flag.Essential) : (flags & ~SF.Npc.Flag.Essential);
        flags = female ? (flags | SF.Npc.Flag.Female) : (flags & ~SF.Npc.Flag.Female);
        npc.Flags = flags;
        npc.Factions.Clear();
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
        a.MajorRecordFlagsRaw |= 0x400 | 0x800; // Persistent | InitiallyDisabled (R3)
        persistentCell.Persistent.Add(a);
        return a;
    }

    /// <summary>
    /// Adds FO4SF_MQ104 (0x000A80) and FO4SF_MQ105 (0x000AB0) into FO4SFMission.esm.
    /// Strictly uses 0xA80..0xAFF so 0x800..0x9FF, A4 0xA00..0xA7F, and A7b 0xB00+ are untouched.
    /// </summary>
    public static void PopulateA7Missions(
        SF.StarfieldMod mod,
        SF.Cell persistentCell,
        FormKey questTypeSideKey,
        FormKey xMarkerKey,
        SF.IStarfieldModGetter sf,
        SF.INpcGetter humanTemplate,
        FormKey humanRaceKey,
        FormKey humanVoiceKey)
    {
        var modKey = mod.ModKey;
        var rel = SF.StarfieldRelease.Starfield;
        var femaleTpl = PickFemaleTemplate(sf, humanRaceKey, humanTemplate);
        var femaleVoice = PickFemaleVoice(sf, humanVoiceKey);

        // ------------------------------------------------------------------ 1. Unlikely Valentine (MQ104 -> 0x000A80)
        var nickNpc = CloneHumanNpc(mod, modKey, NickNpcId, "FO4_NickValentine", "Nick Valentine",
            humanTemplate, humanRaceKey, humanVoiceKey, essential: false);
        // Park Street Station merged Commonwealth coords (Local 212.54, -227.73 + MergeOffset -1200, -2700)
        var nickRef = PlacePersistentActor(persistentCell, modKey, NickRefId, "FO4SF_Vault114_NickREF",
            nickNpc.FormKey, -987.46f, -2927.73f, 19.2f, 0.0f);

        var maloneNpc = CloneHumanNpc(mod, modKey, SkinnyMaloneNpcId, "FO4_SkinnyMalone", "Skinny Malone",
            humanTemplate, humanRaceKey, humanVoiceKey, essential: false);
        // Vault 114 exit merged Commonwealth coords (Local 114.57, -258.22 + MergeOffset -1200, -2700)
        var maloneRef = PlacePersistentActor(persistentCell, modKey, SkinnyMaloneRefId, "FO4SF_Vault114_SkinnyMaloneREF",
            maloneNpc.FormKey, -1085.43f, -2958.22f, 19.2f, 3.14f);

        var darlaNpc = CloneHumanNpc(mod, modKey, DarlaNpcId, "FO4_Darla", "Darla",
            femaleTpl, humanRaceKey, femaleVoice, essential: false, female: true);
        var darlaRef = PlacePersistentActor(persistentCell, modKey, DarlaRefId, "FO4SF_Vault114_DarlaREF",
            darlaNpc.FormKey, -1083.0f, -2957.0f, 19.2f, 3.14f);

        var nickFreedGlob = AddGlob(mod, modKey, Vault114NickFreedGlobId, "FO4SF_Vault114NickFreed", 0f);
        var exitUnlockedGlob = AddGlob(mod, modKey, Vault114ExitUnlockedGlobId, "FO4SF_Vault114ExitUnlocked", 0f);
        var mq105ArmedGlob = AddGlob(mod, modKey, Mq105ArmedGlobId, "FO4SF_MQ105Armed", 0f);

        var nickCellTalk = AddMessage(mod, modKey, Mq104NickCellTalkMsgId, "FO4SF_MQ104_NickCellTalkMsg",
            "Nick Valentine", "The detective is locked inside the Overseer wing of Vault 114 with Triggermen guarding the exit.",
            "Unlock the cell and lead the way", "Ask how he was captured", "Ask about the exit route", "Leave");
        var caseNotes = AddMessage(mod, modKey, Mq104CaseNotesMsgId, "FO4SF_MQ104_CaseNotesMsg",
            "Overseer Office Case Notes", "Nick's field ledger lists an override code for the Vault 114 exit and points back to Valentine Detective Agency.",
            "Continue");
        var maloneTalk = AddMessage(mod, modKey, Mq104MaloneTalkMsgId, "FO4SF_MQ104_MaloneTalkMsg",
            "Skinny Malone", "Skinny Malone and Darla block the Vault 114 exit elevator with armed Triggermen.",
            "Convince Darla to walk away", "Persuade Skinny Malone to let you pass", "Fight your way out", "Step back");
        var debriefMsg = AddMessage(mod, modKey, Mq104DebriefMsgId, "FO4SF_MQ104_DebriefMsg",
            "Unlikely Valentine", "Out of Vault 114, Nick agrees to review your missing-son case back at his Diamond City agency.",
            "Continue");

        var mq104 = new SF.Quest(new FormKey(modKey, Mq104QuestId), rel)
        {
            EditorID = Mq104QuestEdid,
            Name = "Unlikely Valentine",
            FormVersion = 581,
            Version2 = 12,
            Data = new SF.QuestData
            {
                // B1/B4: match FO4SF_NewGame (RunOnce | DisplaysInHud | AllowRepeatedStages, without StartsEnabled/0x10000)
                Flags = SF.Quest.Flag.AllowRepeatedStages | SF.Quest.Flag.DisplaysInHud | SF.Quest.Flag.RunOnce,
                Priority = 70,
            },
        };
        mq104.QuestType.SetTo(questTypeSideKey);
        foreach (var stIdx in Mq104Stages)
        {
            var st = new SF.QuestStage { Index = stIdx };
            st.LogEntries.Add(new SF.QuestLogEntry
            {
                Flags = stIdx == 200 ? SF.QuestLogEntry.Flag.CompleteQuest : (SF.QuestLogEntry.Flag)0,
            });
            mq104.Stages.Add(st);
        }
        mq104.Aliases = new ExtendedList<SF.AQuestAlias>
        {
            new SF.QuestReferenceAlias
            {
                ID = 0, Name = "NickValentine",
                Flags = SF.AQuestAlias.Flag.Optional | SF.AQuestAlias.Flag.AllowReserved |
                        SF.AQuestAlias.Flag.AllowDisabled | SF.AQuestAlias.Flag.AllowDead,
                ForcedReference = new FormLinkNullable<SF.IPlacedGetter>(nickRef.FormKey),
            },
            new SF.QuestReferenceAlias
            {
                ID = 1, Name = "SkinnyMalone",
                Flags = SF.AQuestAlias.Flag.Optional | SF.AQuestAlias.Flag.AllowReserved |
                        SF.AQuestAlias.Flag.AllowDisabled | SF.AQuestAlias.Flag.AllowDead,
                ForcedReference = new FormLinkNullable<SF.IPlacedGetter>(maloneRef.FormKey),
            },
            new SF.QuestReferenceAlias
            {
                ID = 2, Name = "Darla",
                Flags = SF.AQuestAlias.Flag.Optional | SF.AQuestAlias.Flag.AllowReserved |
                        SF.AQuestAlias.Flag.AllowDisabled | SF.AQuestAlias.Flag.AllowDead,
                ForcedReference = new FormLinkNullable<SF.IPlacedGetter>(darlaRef.FormKey),
            },
        };
        foreach (var (oid, otext, aliasId) in Mq104Objectives)
        {
            var obj = new SF.QuestObjective { Index = oid, Flags = 0, DisplayText = otext };
            obj.Targets.Add(new SF.QuestObjectiveTarget { AliasID = aliasId });
            mq104.Objectives.Add(obj);
        }
        var mq104Script = new SF.ScriptEntry { Name = Mq104ScriptName, Flags = SF.ScriptEntry.Flag.Local };
        mq104Script.Properties.Add(ObjProp("XMarkerBase", xMarkerKey));
        mq104Script.Properties.Add(ObjProp("NickValentine", nickRef.FormKey));
        mq104Script.Properties.Add(ObjProp("SkinnyMalone", maloneRef.FormKey));
        mq104Script.Properties.Add(ObjProp("Darla", darlaRef.FormKey));
        mq104Script.Properties.Add(ObjProp("Vault114NickFreed", nickFreedGlob.FormKey));
        mq104Script.Properties.Add(ObjProp("Vault114ExitUnlocked", exitUnlockedGlob.FormKey));
        mq104Script.Properties.Add(ObjProp("MQ105Armed", mq105ArmedGlob.FormKey));
        mq104Script.Properties.Add(ObjProp("NickCellTalkMsg", nickCellTalk.FormKey));
        mq104Script.Properties.Add(ObjProp("CaseNotesMsg", caseNotes.FormKey));
        mq104Script.Properties.Add(ObjProp("MaloneTalkMsg", maloneTalk.FormKey));
        mq104Script.Properties.Add(ObjProp("DebriefMsg", debriefMsg.FormKey));
        mq104.VirtualMachineAdapter = MakeAdapter(mq104Script);
        mod.Quests.Add(mq104);

        // ------------------------------------------------------------------ 2. Getting a Clue (MQ105 -> 0x000AB0)
        var genevaNpc = CloneHumanNpc(mod, modKey, GenevaNpcId, "FO4_Geneva", "Geneva",
            femaleTpl, humanRaceKey, femaleVoice, essential: false, female: true);
        // Diamond City hub merged Commonwealth coords (Local -218.0, -425.0 + MergeOffset -1200, -2700)
        var genevaRef = PlacePersistentActor(persistentCell, modKey, GenevaRefId, "FO4SF_DiamondCity_GenevaREF",
            genevaNpc.FormKey, -1418.0f, -3125.0f, 19.3f, 2.2f);

        var dogmeatNpc = CloneHumanNpc(mod, modKey, DogmeatNpcId, "FO4_DogmeatTrailGuide", "Dogmeat",
            humanTemplate, humanRaceKey, humanVoiceKey, essential: false);
        // Diamond City gate merged Commonwealth coords (Local -222.0, -435.0 + MergeOffset -1200, -2700)
        var dogmeatRef = PlacePersistentActor(persistentCell, modKey, DogmeatRefId, "FO4SF_DiamondCity_DogmeatREF",
            dogmeatNpc.FormKey, -1422.0f, -3135.0f, 19.3f, 0.0f);

        var kelloggCigar = new SF.MiscItem(new FormKey(modKey, KelloggCigarMiscId), rel)
        {
            EditorID = "FO4SF_KelloggCigar",
            Name = "San Francisco Sunlights Cigar",
            Value = 15,
            Weight = 0.1f,
        };
        mod.MiscItems.Add(kelloggCigar);

        var houseUnlockedGlob = AddGlob(mod, modKey, KelloggHouseUnlockedGlobId, "FO4SF_KelloggHouseUnlocked", 0f);
        var secretOpenedGlob = AddGlob(mod, modKey, KelloggSecretOpenedGlobId, "FO4SF_KelloggSecretOpened", 0f);
        var mq106ArmedGlob = AddGlob(mod, modKey, Mq106ArmedGlobId, "FO4SF_MQ106Armed", 0f);

        var agencyBrief = AddMessage(mod, modKey, Mq105AgencyBriefMsgId, "FO4SF_MQ105_AgencyBriefMsg",
            "Valentine Detective Agency", "Nick matches the description of the scarred mercenary to Kellogg, who kept a locked house in Diamond City.",
            "Investigate Kellogg's house", "Ask about Kellogg's background", "Ask how to get inside", "Leave");
        var agencyDossier = AddMessage(mod, modKey, Mq105AgencyDossierMsgId, "FO4SF_MQ105_AgencyDossierMsg",
            "Kellogg Case Dossier", "Agency files point to Kellogg's locked house in Diamond City and note that the mayor's office holds a spare key.",
            "Continue");
        var genevaKey = AddMessage(mod, modKey, Mq105GenevaKeyMsgId, "FO4SF_MQ105_GenevaKeyMsg",
            "Geneva", "The Mayor's secretary holds the spare key to Kellogg's house in the Diamond City stands.",
            "Persuade Geneva for the spare key", "Offer caps for the key", "Check the mayor's desk instead", "Leave");
        var secretRoom = AddMessage(mod, modKey, Mq105SecretRoomMsgId, "FO4SF_MQ105_SecretRoomMsg",
            "Kellogg's Hidden Room", "Pressing the button beneath Kellogg's desk slides open a concealed armory holding a fresh San Francisco Sunlights cigar.",
            "Take the cigar clue", "Leave");
        var trailHandoff = AddMessage(mod, modKey, Mq105TrailHandoffMsgId, "FO4SF_MQ105_TrailHandoffMsg",
            "Cigar Scent Trail", "The cigar trail leads west across the Commonwealth straight toward Fort Hagen.",
            "Track trail to Fort Hagen", "Mark Fort Hagen directly");

        var mq105 = new SF.Quest(new FormKey(modKey, Mq105QuestId), rel)
        {
            EditorID = Mq105QuestEdid,
            Name = "Getting a Clue",
            FormVersion = 581,
            Version2 = 12,
            Data = new SF.QuestData
            {
                // B1/B4: match FO4SF_NewGame (RunOnce | DisplaysInHud | AllowRepeatedStages, without StartsEnabled/0x10000)
                Flags = SF.Quest.Flag.AllowRepeatedStages | SF.Quest.Flag.DisplaysInHud | SF.Quest.Flag.RunOnce,
                Priority = 70,
            },
        };
        mq105.QuestType.SetTo(questTypeSideKey);
        foreach (var stIdx in Mq105Stages)
        {
            var st = new SF.QuestStage { Index = stIdx };
            st.LogEntries.Add(new SF.QuestLogEntry
            {
                Flags = stIdx == 200 ? SF.QuestLogEntry.Flag.CompleteQuest : (SF.QuestLogEntry.Flag)0,
            });
            mq105.Stages.Add(st);
        }
        mq105.Aliases = new ExtendedList<SF.AQuestAlias>
        {
            new SF.QuestReferenceAlias
            {
                ID = 0, Name = "NickValentine",
                Flags = SF.AQuestAlias.Flag.Optional | SF.AQuestAlias.Flag.AllowReserved |
                        SF.AQuestAlias.Flag.AllowDisabled | SF.AQuestAlias.Flag.AllowDead,
                ForcedReference = new FormLinkNullable<SF.IPlacedGetter>(nickRef.FormKey),
            },
            new SF.QuestReferenceAlias
            {
                ID = 1, Name = "Geneva",
                Flags = SF.AQuestAlias.Flag.Optional | SF.AQuestAlias.Flag.AllowReserved |
                        SF.AQuestAlias.Flag.AllowDisabled | SF.AQuestAlias.Flag.AllowDead,
                ForcedReference = new FormLinkNullable<SF.IPlacedGetter>(genevaRef.FormKey),
            },
            new SF.QuestReferenceAlias
            {
                ID = 2, Name = "Dogmeat",
                Flags = SF.AQuestAlias.Flag.Optional | SF.AQuestAlias.Flag.AllowReserved |
                        SF.AQuestAlias.Flag.AllowDisabled | SF.AQuestAlias.Flag.AllowDead,
                ForcedReference = new FormLinkNullable<SF.IPlacedGetter>(dogmeatRef.FormKey),
            },
        };
        foreach (var (oid, otext, aliasId) in Mq105Objectives)
        {
            var obj = new SF.QuestObjective { Index = oid, Flags = 0, DisplayText = otext };
            obj.Targets.Add(new SF.QuestObjectiveTarget { AliasID = aliasId });
            mq105.Objectives.Add(obj);
        }
        var mq105Script = new SF.ScriptEntry { Name = Mq105ScriptName, Flags = SF.ScriptEntry.Flag.Local };
        mq105Script.Properties.Add(ObjProp("XMarkerBase", xMarkerKey));
        mq105Script.Properties.Add(ObjProp("NickValentine", nickRef.FormKey));
        mq105Script.Properties.Add(ObjProp("Geneva", genevaRef.FormKey));
        mq105Script.Properties.Add(ObjProp("Dogmeat", dogmeatRef.FormKey));
        mq105Script.Properties.Add(ObjProp("KelloggCigar", kelloggCigar.FormKey));
        mq105Script.Properties.Add(ObjProp("KelloggHouseUnlocked", houseUnlockedGlob.FormKey));
        mq105Script.Properties.Add(ObjProp("KelloggSecretOpened", secretOpenedGlob.FormKey));
        mq105Script.Properties.Add(ObjProp("MQ106Armed", mq106ArmedGlob.FormKey));
        mq105Script.Properties.Add(ObjProp("AgencyBriefMsg", agencyBrief.FormKey));
        mq105Script.Properties.Add(ObjProp("AgencyDossierMsg", agencyDossier.FormKey));
        mq105Script.Properties.Add(ObjProp("GenevaKeyMsg", genevaKey.FormKey));
        mq105Script.Properties.Add(ObjProp("SecretRoomMsg", secretRoom.FormKey));
        mq105Script.Properties.Add(ObjProp("TrailHandoffMsg", trailHandoff.FormKey));
        mq105.VirtualMachineAdapter = MakeAdapter(mq105Script);
        mod.Quests.Add(mq105);

        SF.Activator AddTalkProxyActi(uint id, string edid, string npcName)
        {
            var a = new SF.Activator(new FormKey(modKey, id), rel)
            {
                EditorID = edid,
                Name = npcName,
                ActivateTextOverride = "Talk",
                MarkerColor = System.Drawing.Color.FromArgb(0, 0xCC, 0x4C, 0x33),
                Flags = (SF.Activator.Flag)0,
                ActivationAngle = 360,
                InvertFacing = false,
                ObjectBounds = new SF.ObjectBounds
                {
                    First = new P3Float(-0.25f, -0.25f, -0.25f),
                    Second = new P3Float(0.25f, 0.25f, 0.25f),
                },
                Model = new SF.Model { File = new Mutagen.Bethesda.Plugins.Assets.AssetLink<Mutagen.Bethesda.Starfield.Assets.StarfieldModelAssetType>(TalkProxyActiModel) },
            };
            mod.Activators.Add(a);
            return a;
        }
        AddTalkProxyActi(NickTalkActiId, NickTalkActiEdid, nickNpc.Name?.String ?? "Nick Valentine");
        AddTalkProxyActi(MaloneTalkActiId, MaloneTalkActiEdid, maloneNpc.Name?.String ?? "Skinny Malone");
        AddTalkProxyActi(GenevaTalkActiId, GenevaTalkActiEdid, genevaNpc.Name?.String ?? "Geneva");
        AddTalkProxyActi(DogmeatTalkActiId, DogmeatTalkActiEdid, dogmeatNpc.Name?.String ?? "Dogmeat");
    }

    public static void CheckA7Missions(
        SF.IStarfieldModGetter plug,
        ModKey sfEsm,
        uint questTypeSideId,
        Action<bool, string> need)
    {
        var key = plug.ModKey;
        static bool NonStartGameReady(SF.IQuestGetter q) =>
            q.Data is not null &&
            !q.Data.Flags.HasFlag(SF.Quest.Flag.StartGameEnabled) &&
            !q.Data.Flags.HasFlag(SF.Quest.Flag.StartsEnabled) &&
            (((uint)q.Data.Flags & 0x10000u) == 0) &&
            q.Data.Flags.HasFlag(SF.Quest.Flag.RunOnce) &&
            q.Data.Flags.HasFlag(SF.Quest.Flag.DisplaysInHud);

        // 1. MQ104 (0x000A80)
        var mq104 = plug.Quests.FirstOrDefault(q => q.FormKey == new FormKey(key, Mq104QuestId));
        need(mq104 is { EditorID: Mq104QuestEdid } && NonStartGameReady(mq104) &&
             mq104.QuestType.FormKey == new FormKey(sfEsm, questTypeSideId),
            "FO4SF_MQ104 (0x000A80) missing or invalid flags/QuestType");
        if (mq104 is not null)
        {
            need(mq104.Stages.Select(s => s.Index).SequenceEqual(Mq104Stages), "FO4SF_MQ104 stages mismatch");
            need(mq104.Stages.All(s => s.LogEntries.Count >= 1 && s.LogEntries[0].Flags is not null),
                "FO4SF_MQ104 has a stage without QSDT QuestLogEntry");
            need(mq104.Stages.Last().LogEntries.Any(l => l.Flags?.HasFlag(SF.QuestLogEntry.Flag.CompleteQuest) == true),
                "FO4SF_MQ104 stage 200 lacks CompleteQuest");
            need(mq104.Objectives.Select(o => o.Index).SequenceEqual(Mq104Objectives.Select(o => o.Index)) &&
                 mq104.Objectives.All(o => o.Flags is not null),
                "FO4SF_MQ104 objectives mismatch or lack Flags");
            need(mq104.VirtualMachineAdapter?.Scripts.Any(s => s.Name == Mq104ScriptName) == true,
                "FO4SF_MQ104 lacks script binding");
        }
        need(plug.Globals.Any(g => g.FormKey == new FormKey(key, Vault114NickFreedGlobId)) &&
             plug.Globals.Any(g => g.FormKey == new FormKey(key, Vault114ExitUnlockedGlobId)) &&
             plug.Globals.Any(g => g.FormKey == new FormKey(key, Mq105ArmedGlobId)),
            "FO4SF_MQ104 GLOBs (0x000A87 / 0x000A88 / 0x000A89) missing");

        // 2. MQ105 (0x000AB0)
        var mq105 = plug.Quests.FirstOrDefault(q => q.FormKey == new FormKey(key, Mq105QuestId));
        need(mq105 is { EditorID: Mq105QuestEdid } && NonStartGameReady(mq105) &&
             mq105.QuestType.FormKey == new FormKey(sfEsm, questTypeSideId),
            "FO4SF_MQ105 (0x000AB0) missing or invalid flags/QuestType");
        if (mq105 is not null)
        {
            need(mq105.Stages.Select(s => s.Index).SequenceEqual(Mq105Stages), "FO4SF_MQ105 stages mismatch");
            need(mq105.Stages.All(s => s.LogEntries.Count >= 1 && s.LogEntries[0].Flags is not null),
                "FO4SF_MQ105 has a stage without QSDT QuestLogEntry");
            need(mq105.Stages.Last().LogEntries.Any(l => l.Flags?.HasFlag(SF.QuestLogEntry.Flag.CompleteQuest) == true),
                "FO4SF_MQ105 stage 200 lacks CompleteQuest");
            need(mq105.Objectives.Select(o => o.Index).SequenceEqual(Mq105Objectives.Select(o => o.Index)) &&
                 mq105.Objectives.All(o => o.Flags is not null),
                "FO4SF_MQ105 objectives mismatch or lack Flags");
            need(mq105.VirtualMachineAdapter?.Scripts.Any(s => s.Name == Mq105ScriptName) == true,
                "FO4SF_MQ105 lacks script binding");
        }
        need(plug.MiscItems.Any(m => m.FormKey == new FormKey(key, KelloggCigarMiscId) && m.EditorID == "FO4SF_KelloggCigar"),
            "FO4SF_KelloggCigar clue item (0x000AB5) missing");
        need(plug.Globals.Any(g => g.FormKey == new FormKey(key, KelloggHouseUnlockedGlobId)) &&
             plug.Globals.Any(g => g.FormKey == new FormKey(key, KelloggSecretOpenedGlobId)) &&
             plug.Globals.Any(g => g.FormKey == new FormKey(key, Mq106ArmedGlobId)),
            "FO4SF_MQ105 GLOBs (0x000AB6 / 0x000AB7 / 0x000AB8) missing");

        var a7Refs = plug.Worldspaces.FirstOrDefault()?.TopCell?.Persistent.OfType<SF.IPlacedNpcGetter>()
            .Where(r => IsA7ActorRefId(r.FormKey.ID)).ToList() ?? [];
        need(a7Refs.Count == 5 && a7Refs.All(r => (r.MajorRecordFlagsRaw & 0x800) != 0),
            "A7 persistent ACHRs must all carry InitiallyDisabled (0x800, R3)");

        foreach (var (actiId, edid, npcId) in new (uint, string, uint)[]
        {
            (NickTalkActiId, NickTalkActiEdid, NickNpcId),
            (MaloneTalkActiId, MaloneTalkActiEdid, SkinnyMaloneNpcId),
            (GenevaTalkActiId, GenevaTalkActiEdid, GenevaNpcId),
            (DogmeatTalkActiId, DogmeatTalkActiEdid, DogmeatNpcId),
        })
        {
            var talkActi = plug.Activators.FirstOrDefault(a => a.FormKey == new FormKey(key, actiId));
            var talkNpc = plug.Npcs.FirstOrDefault(n => n.FormKey == new FormKey(key, npcId));
            need(talkActi is not null && talkNpc is not null &&
                 talkActi.EditorID == edid &&
                 talkActi.ActivationAngle == 360 && !talkActi.InvertFacing &&
                 talkActi.ActivateTextOverride?.String == "Talk" &&
                 !string.IsNullOrEmpty(talkNpc.Name?.String) &&
                 talkActi.Name?.String == talkNpc.Name?.String &&
                 string.Equals(talkActi.Model?.File?.GivenPath, TalkProxyActiModel, StringComparison.OrdinalIgnoreCase),
                $"A7 talk proxy {edid} (0x{actiId:X6}) missing or Name mismatch with NPC 0x{npcId:X6}");
        }
    }
}
