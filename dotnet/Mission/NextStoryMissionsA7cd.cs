// NextStoryMissionsA7cd: Lane A Push 6 Act II executable state machines for FO4SFMission.esm (strictly 0xAD0..0xB57).
//
// Adds four complete Act II story quests behind the FO4SF_GameMode == 1 (Story) mission gate,
// with Open-Mode (W7) dead-giver fallbacks, Track 1 vs Track 2 rads integration, switchable
// faction teleporter branch + solo self-build, and clean handoff to FO4Port_InstituteConcourse (0x03D252):
//   1. Reunions            (FO4SF_MQ106 -> 0x000AD0..0x000AEF, FO4 MQ106 0x0229E7)
//   2. Dangerous Minds     (FO4SF_MQ203 -> 0x000AF0..0x000B0F, FO4 MQ202/MQ203 0x0229E9)
//   3. The Glowing Sea     (FO4SF_MQ204 -> 0x000B10..0x000B2F, FO4 MQ204 0x06B500)
//   4. The Molecular Level (FO4SF_MQ206 -> 0x000B30..0x000B57, FO4 MQ205/MQ206 0x0B1752)
//
// Reserved local FormID map (zero overlap with 0x800..0x9FF, A4 0xA00..0xA7F, or A7 0xA80..0xAC4;
// sits inside the extended A5 Pip-Boy DATA/Quests live scan window 0x800..0xBFF):
//   Reunions (MQ106 -> 0x000AD0..0x000AEF):
//     0xAD0  QUST  FO4SF_MQ106                   (stages 10, 50, 75, 100, 125, 150, 200, 500; objectives 10, 50, 100, 150, 200)
//     0xAD1  NPC_  FO4_Kellogg                   (hostile armed boss cloned from FO4_LvlRaider, !Essential, !Protected, !Respawn)
//     0xAD2  ACHR  FO4SF_FortHagen_KelloggREF    (merged -2456.84, -2781.07, 81.83)
//     0xAD3  MISC  FO4SF_CyberBrain              (Kellogg's Cybernetic Brain Augmenter)
//     0xAD4  MISC  FO4SF_KelloggPassword         (Kellogg's Terminal Password)
//     0xAD5  ACTI  FO4SF_MQ106_TerminalProxyActi (Mission.CodsworthTalkActiModel, no Meshes\ prefix)
//     0xAD6  GLOB  FO4SF_PrydwenArrived          (0 -> 1 on exterior load after stage 150)
//     0xAD7  GLOB  FO4SF_MQ203Armed              (0 -> 1 on stage 500 -> starts 0x000AF0)
//     0xAE0..0xAE3  MESG  FO4SF_MQ106_ConfrontMsg..DossierMsg
//   Dangerous Minds (MQ203 -> 0x000AF0..0x000B0F):
//     0xAF0  QUST  FO4SF_MQ203                   (stages 5, 10, 100, 110, 120, 300; objectives 5, 10, 100, 110, 120)
//     0xAF1  NPC_  FO4_DoctorAmari               (female template + GenericFemaleEvenToned + Female flag, !Essential)
//     0xAF2  ACHR  FO4SF_MemoryDen_AmariREF      (merged -902.48, -2870.07, 19.20)
//     0xAF3  ACTI  FO4SF_MQ203_LoungerProxyActi  (Mission.CodsworthTalkActiModel, clean-room lounger bridge + self-scan)
//     0xAF4  GLOB  FO4SF_MemoriesCompleted       (0 -> 1 once memory walk / Virgil's file completed)
//     0xAF5  GLOB  FO4SF_MQ204Armed              (0 -> 1 on stage 300 -> starts 0x000B10)
//     0xB00..0xB03  MESG  FO4SF_MQ203_AmariTalkMsg..LabTerminalMsg
//   The Glowing Sea (MQ204 -> 0x000B10..0x000B2F):
//     0xB10  QUST  FO4SF_MQ204                   (stages 10, 15, 20, 50, 200; objectives 15, 20)
//     0xB11  NPC_  FO4_MotherIsolde              (female template + GenericFemaleEvenToned + Female flag, !Essential)
//     0xB12  ACHR  FO4SF_Crater_IsoldeREF        (merged -2624.44, -4357.85, 107.64)
//     0xB13  NPC_  FO4_Virgil                    (male template, !Essential; script sets IgnoreFriendlyHits + StopCombat)
//     0xB14  ACHR  FO4SF_VirgilsLab_VirgilREF    (merged -2862.82, -4653.27, 143.19)
//     0xB15  MISC  FO4SF_VirgilNote              (Glowing Sea Cave Directions — Open-Mode dead-Isolde fallback)
//     0xB16  ACTI  FO4SF_MQ204_LabTerminalProxyActi (Mission.CodsworthTalkActiModel — dead-Virgil fallback)
//     0xB17  GLOB  FO4SF_GlowingSeaRadsActive    (0/1: Track 1 scripted SW rads tick active when FO4SFRads.esm absent)
//     0xB18  GLOB  FO4SF_MQ206Armed              (0 -> 1 on stage 200 -> starts 0x000B30)
//     0xB20..0xB23  MESG  FO4SF_MQ204_IsoldeTalkMsg..LabTerminalMsg
//   The Molecular Level (MQ206 -> 0x000B30..0x000B57):
//     0xB30  QUST  FO4SF_MQ206                   (stages 10, 20, 65, 100, 200, 300, 350, 600, 700, 1000, 1200; objectives 10..250)
//     0xB31  NPC_  FO4_CourserZ247               (hostile armed boss cloned from FO4_LvlRaider, !Essential, !Protected, !Respawn)
//     0xB32  ACHR  FO4SF_Greenetech_CourserREF   (merged -1238.10, -2687.39, 12.18)
//     0xB33  NPC_  FO4_Desdemona                 (female template + GenericFemaleEvenToned + Female flag, !Essential)
//     0xB34  ACHR  FO4SF_Railroad_DesdemonaREF   (merged -734.83, -2696.65, 10.16)
//     0xB35  NPC_  FO4_TinkerTom                 (male template, !Essential)
//     0xB36  ACHR  FO4SF_Railroad_TinkerTomREF   (merged -731.00, -2695.00, 10.16)
//     0xB37  NPC_  FO4_ProctorIngram             (female template + GenericFemaleEvenToned + Female flag, !Essential)
//     0xB38  ACHR  FO4SF_Airport_IngramREF       (merged -513.23, -2747.60, 10.27)
//     0xB39  MISC  FO4SF_CourserChip             (Courser Chip)
//     0xB3A  MISC  FO4SF_CourserChipHolotape     (Decoded Courser Chip Holotape)
//     0xB3B  MISC  FO4SF_SignalInterceptorPlans  (Signal Interceptor Schematics)
//     0xB3C  ACTI  FO4SF_MQ206_ScannerProxyActi  (Tinker Tom Decoding Scanner — Stage 65 self-decode)
//     0xB3D  ACTI  FO4SF_MQ206_ConsoleProxyActi  (Signal Interceptor Console — relay MoveTo InstituteConcourse 0x03D252)
//     0xB40..0xB47  GLOB  FO4SF_MQ206TeleporterFaction..FO4SF_MQ207Armed
//     0xB50..0xB56  MESG  FO4SF_MQ206_TinkerDecodeMsg..OpenModeFallbackMsg
//
// Zero copyrighted Fallout 4 dialogue appears in this file.

using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Assets;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield.Assets;
using Noggog;
using SF = Mutagen.Bethesda.Starfield;

static class NextStoryMissionsA7cd
{
    public const string ProxyActiModel = Mission.CodsworthTalkActiModel;

    // 1. Reunions (MQ106): 0xAD0..0xAEF
    public const uint Mq106QuestId = 0xAD0;
    public const string Mq106QuestEdid = "FO4SF_MQ106", Mq106ScriptName = "FO4SF_MQ106Quest";
    public const uint KelloggNpcId = 0xAD1, KelloggRefId = 0xAD2;
    public const uint CyberBrainMiscId = 0xAD3, KelloggPasswordMiscId = 0xAD4;
    public const uint Mq106TerminalProxyActiId = 0xAD5;
    public const string Mq106TerminalProxyActiEdid = "FO4SF_MQ106_TerminalProxyActi";
    public const uint PrydwenArrivedGlobId = 0xAD6, Mq203ArmedGlobId = 0xAD7;
    public const uint Mq106ConfrontMsgId = 0xAE0, Mq106TerminalMsgId = 0xAE1,
                      Mq106DebriefMsgId = 0xAE2, Mq106DossierMsgId = 0xAE3;

    // 2. Dangerous Minds (MQ203): 0xAF0..0xB0F
    public const uint Mq203QuestId = 0xAF0;
    public const string Mq203QuestEdid = "FO4SF_MQ203", Mq203ScriptName = "FO4SF_MQ203Quest";
    public const uint DoctorAmariNpcId = 0xAF1, DoctorAmariRefId = 0xAF2;
    public const uint Mq203LoungerProxyActiId = 0xAF3;
    public const string Mq203LoungerProxyActiEdid = "FO4SF_MQ203_LoungerProxyActi";
    public const uint MemoriesCompletedGlobId = 0xAF4, Mq204ArmedGlobId = 0xAF5;
    public const uint AmariTalkActiId = 0xAF6;
    public const string AmariTalkActiEdid = "FO4SF_MQ203_AmariTalkActi";
    public const uint Mq203AmariTalkMsgId = 0xB00, Mq203LoungerMsgId = 0xB01,
                      Mq203MemoryWalkMsgId = 0xB02, Mq203LabTerminalMsgId = 0xB03;

    // 3. The Glowing Sea (MQ204): 0xB10..0xB2F
    public const uint Mq204QuestId = 0xB10;
    public const string Mq204QuestEdid = "FO4SF_MQ204", Mq204ScriptName = "FO4SF_MQ204Quest";
    public const uint MotherIsoldeNpcId = 0xB11, MotherIsoldeRefId = 0xB12;
    public const uint VirgilNpcId = 0xB13, VirgilRefId = 0xB14;
    public const uint VirgilNoteMiscId = 0xB15;
    public const uint Mq204LabTerminalProxyActiId = 0xB16;
    public const string Mq204LabTerminalProxyActiEdid = "FO4SF_MQ204_LabTerminalProxyActi";
    public const uint GlowingSeaRadsActiveGlobId = 0xB17, Mq206ArmedGlobId = 0xB18;
    public const uint IsoldeTalkActiId = 0xB19, VirgilTalkActiId = 0xB1A;
    public const string IsoldeTalkActiEdid = "FO4SF_MQ204_IsoldeTalkActi",
                        VirgilTalkActiEdid = "FO4SF_MQ204_VirgilTalkActi";
    public const uint Mq204IsoldeTalkMsgId = 0xB20, Mq204VirgilNoteMsgId = 0xB21,
                      Mq204VirgilTalkMsgId = 0xB22, Mq204LabTerminalMsgId = 0xB23;

    // 4. The Molecular Level (MQ206): 0xB30..0xB57
    public const uint Mq206QuestId = 0xB30;
    public const string Mq206QuestEdid = "FO4SF_MQ206", Mq206ScriptName = "FO4SF_MQ206Quest";
    public const uint CourserZ247NpcId = 0xB31, CourserZ247RefId = 0xB32;
    public const uint DesdemonaNpcId = 0xB33, DesdemonaRefId = 0xB34;
    public const uint TinkerTomNpcId = 0xB35, TinkerTomRefId = 0xB36;
    public const uint ProctorIngramNpcId = 0xB37, ProctorIngramRefId = 0xB38;
    public const uint CourserChipMiscId = 0xB39, CourserChipHolotapeMiscId = 0xB3A, SignalInterceptorPlansMiscId = 0xB3B;
    public const uint Mq206ScannerProxyActiId = 0xB3C;
    public const string Mq206ScannerProxyActiEdid = "FO4SF_MQ206_ScannerProxyActi";
    public const uint Mq206ConsoleProxyActiId = 0xB3D;
    public const string Mq206ConsoleProxyActiEdid = "FO4SF_MQ206_ConsoleProxyActi";
    public const uint DesdemonaTalkActiId = 0xB3E, TinkerTomTalkActiId = 0xB3F, IngramTalkActiId = 0xB48;
    public const string DesdemonaTalkActiEdid = "FO4SF_MQ206_DesdemonaTalkActi",
                        TinkerTomTalkActiEdid = "FO4SF_MQ206_TinkerTomTalkActi",
                        IngramTalkActiEdid = "FO4SF_MQ206_IngramTalkActi";
    public const uint Mq206TeleporterFactionGlobId = 0xB40, Mq206BuiltPlatformGlobId = 0xB41,
                      Mq206BuiltBeamGlobId = 0xB42, Mq206BuiltDishGlobId = 0xB43,
                      Mq206BuiltConsoleGlobId = 0xB44, Mq206ArrayPoweredGlobId = 0xB45,
                      Mq206ReadyToTeleportGlobId = 0xB46, Mq207ArmedGlobId = 0xB47;
    public const uint Mq206TinkerDecodeMsgId = 0xB50, Mq206ScannerMsgId = 0xB51,
                      Mq206VirgilPlansMsgId = 0xB52, Mq206FactionPickMsgId = 0xB53,
                      Mq206WorkbenchBuildMsgId = 0xB54, Mq206RelayFireMsgId = 0xB55,
                      Mq206OpenModeFallbackMsgId = 0xB56;

    public const uint MaxAllocatedId = 0xB57;

    public static bool IsA7cdActorRefId(uint id) =>
        id is KelloggRefId or DoctorAmariRefId or MotherIsoldeRefId or VirgilRefId
           or CourserZ247RefId or DesdemonaRefId or TinkerTomRefId or ProctorIngramRefId;

    public static readonly ushort[] Mq106Stages = { 10, 50, 75, 100, 125, 150, 200, 500 };
    public static readonly ushort[] Mq203Stages = { 5, 10, 100, 110, 120, 300 };
    public static readonly ushort[] Mq204Stages = { 10, 15, 20, 50, 200 };
    public static readonly ushort[] Mq206Stages = { 10, 20, 65, 100, 200, 300, 350, 600, 700, 1000, 1200 };

    public static readonly (ushort Index, string Text, int TargetAlias)[] Mq106Objectives =
    {
        (10, "Follow Dogmeat to Fort Hagen", 0),
        (50, "Enter Fort Hagen and reach the Command Center", 0),
        (100, "Confront and defeat Kellogg", 0),
        (150, "Search Kellogg and his terminal, then exit to the roof", 0),
        (200, "Return to Diamond City and report to Nick", 1),
    };

    public static readonly (ushort Index, string Text, int TargetAlias)[] Mq203Objectives =
    {
        (5, "Bring Kellogg's cybernetic brain augmenter to the Memory Den", 0),
        (10, "Speak with Doctor Amari in Goodneighbor's Memory Den", 0),
        (100, "Enter the Memory Lounger in Doctor Amari's lab", 0),
        (110, "Explore Kellogg's memories to locate Virgil's trail", 0),
        (120, "Speak with Doctor Amari and prepare for the Glowing Sea", 0),
    };

    public static readonly (ushort Index, string Text, int TargetAlias)[] Mq204Objectives =
    {
        (15, "Search the Glowing Sea for Virgil (Crater of Atom clue)", 0),
        (20, "Reach Virgil inside the Rocky Cave", 1),
    };

    public static readonly (ushort Index, string Text, int TargetAlias)[] Mq206Objectives =
    {
        (10, "Track and defeat the Institute Courser at Greenetech Genetics", 0),
        (20, "Have the Courser Chip decoded at Railroad HQ", 1),
        (30, "Return the decoded Courser Chip to Virgil", 2),
        (50, "Choose a faction ally or solo workbench to build the Signal Interceptor", 3),
        (100, "Build and power the Signal Interceptor components", 3),
        (150, "Use the Signal Interceptor console to teleport to the Institute", 3),
        (250, "Enter the Institute Concourse", 3),
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

    static SF.MiscItem AddMisc(SF.StarfieldMod mod, ModKey modKey, uint id, string edid, string name, int value, float weight)
    {
        var m = new SF.MiscItem(new FormKey(modKey, id), SF.StarfieldRelease.Starfield)
        {
            EditorID = edid,
            Name = name,
            Value = value,
            Weight = weight,
        };
        mod.MiscItems.Add(m);
        return m;
    }

    static SF.Activator AddProxyActi(SF.StarfieldMod mod, ModKey modKey, uint id, string edid, string name, string prompt)
    {
        var a = new SF.Activator(new FormKey(modKey, id), SF.StarfieldRelease.Starfield)
        {
            EditorID = edid,
            Name = name,
            ActivateTextOverride = prompt,
            MarkerColor = System.Drawing.Color.FromArgb(0, 0xCC, 0x4C, 0x33),
            Flags = (SF.Activator.Flag)0,
            ActivationAngle = 360,
            InvertFacing = false,
            ObjectBounds = new SF.ObjectBounds
            {
                First = new P3Float(-0.25f, -0.25f, -0.25f),
                Second = new P3Float(0.25f, 0.25f, 0.25f),
            },
            Model = new SF.Model { File = new AssetLink<StarfieldModelAssetType>(ProxyActiModel) },
        };
        mod.Activators.Add(a);
        return a;
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
        var flags = (npc.Flags | SF.Npc.Flag.Unique | SF.Npc.Flag.AutoCalcStats)
                    & ~(SF.Npc.Flag.Respawn | SF.Npc.Flag.Protected);
        flags = essential ? (flags | SF.Npc.Flag.Essential) : (flags & ~SF.Npc.Flag.Essential);
        flags = female ? (flags | SF.Npc.Flag.Female) : (flags & ~SF.Npc.Flag.Female);
        npc.Flags = flags;
        npc.Factions.Clear();
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
        a.MajorRecordFlagsRaw |= 0x400 | 0x800; // Persistent | InitiallyDisabled (R3)
        persistentCell.Persistent.Add(a);
        return a;
    }

    static SF.Quest MakeStoryQuest(
        ModKey modKey,
        uint id,
        string edid,
        string title,
        FormKey questTypeSideKey,
        ushort[] stages,
        ushort completeStage,
        (ushort Index, string Text, int TargetAlias)[] objectives)
    {
        var q = new SF.Quest(new FormKey(modKey, id), SF.StarfieldRelease.Starfield)
        {
            EditorID = edid,
            Name = title,
            FormVersion = 581,
            Version2 = 12,
            Data = new SF.QuestData
            {
                // B1/B4: match FO4SF_NewGame (RunOnce | DisplaysInHud | AllowRepeatedStages, without StartsEnabled/0x10000)
                Flags = SF.Quest.Flag.AllowRepeatedStages | SF.Quest.Flag.DisplaysInHud | SF.Quest.Flag.RunOnce,
                Priority = 70,
            },
        };
        q.QuestType.SetTo(questTypeSideKey);
        foreach (var stIdx in stages)
        {
            var st = new SF.QuestStage { Index = stIdx };
            st.LogEntries.Add(new SF.QuestLogEntry
            {
                Flags = stIdx == completeStage ? SF.QuestLogEntry.Flag.CompleteQuest : (SF.QuestLogEntry.Flag)0,
            });
            q.Stages.Add(st);
        }
        foreach (var (oid, otext, aliasId) in objectives)
        {
            var obj = new SF.QuestObjective { Index = oid, Flags = 0, DisplayText = otext };
            obj.Targets.Add(new SF.QuestObjectiveTarget { AliasID = aliasId });
            q.Objectives.Add(obj);
        }
        return q;
    }

    static SF.QuestReferenceAlias MakeAlias(uint aliasId, string name, FormKey forcedRef, params FormKey[] packages)
    {
        var al = new SF.QuestReferenceAlias
        {
            ID = aliasId,
            Name = name,
            Flags = SF.AQuestAlias.Flag.Optional | SF.AQuestAlias.Flag.AllowReserved |
                    SF.AQuestAlias.Flag.AllowDisabled | SF.AQuestAlias.Flag.AllowDead,
            ForcedReference = new FormLinkNullable<SF.IPlacedGetter>(forcedRef),
        };
        foreach (var pkg in packages)
            al.PackageData.Add(new FormLink<SF.IPackageGetter>(pkg));
        return al;
    }

    /// <summary>
    /// Adds FO4SF_MQ106 (0x000AD0), FO4SF_MQ203 (0x000AF0), FO4SF_MQ204 (0x000B10), and FO4SF_MQ206 (0x000B30)
    /// into FO4SFMission.esm. Strictly uses 0xAD0..0xB56 with zero overlap against earlier blocks.
    /// </summary>
    public static void PopulateA7cdMissions(
        SF.StarfieldMod mod,
        SF.Cell persistentCell,
        FormKey questTypeSideKey,
        FormKey xMarkerKey,
        SF.IStarfieldModGetter sf,
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
        var femaleTpl = PickFemaleTemplate(sf, humanRaceKey, humanTemplate);
        var femaleVoice = PickFemaleVoice(sf, humanVoiceKey);

        var nickRefKey = new FormKey(modKey, NextStoryMissionsA7.NickRefId);
        var dogmeatRefKey = new FormKey(modKey, NextStoryMissionsA7.DogmeatRefId);
        var sturgesRefKey = new FormKey(modKey, NextStoryMissionsA4.SturgesRefId);

        // ------------------------------------------------------------------ 1. Reunions (MQ106 -> 0x000AD0)
        var kelloggNpc = CloneHostileBossNpc(mod, modKey, KelloggNpcId, "FO4_Kellogg", "Kellogg",
            raiderTemplate, weaponKey, ammoKey);
        // Fort Hagen merged Commonwealth coords (-2456.84, -2781.07, 81.83)
        var kelloggRef = PlacePersistentActor(persistentCell, modKey, KelloggRefId, "FO4SF_FortHagen_KelloggREF",
            kelloggNpc.FormKey, -2456.84f, -2781.07f, 81.83f, 3.14f);

        var cyberBrain = AddMisc(mod, modKey, CyberBrainMiscId, "FO4SF_CyberBrain",
            "Kellogg's Cybernetic Brain Augmenter", 250, 0.5f);
        var kelloggPassword = AddMisc(mod, modKey, KelloggPasswordMiscId, "FO4SF_KelloggPassword",
            "Kellogg's Terminal Password", 10, 0.0f);
        var mq106TerminalProxy = AddProxyActi(mod, modKey, Mq106TerminalProxyActiId, Mq106TerminalProxyActiEdid,
            "Kellogg's Command Terminal", "Access");

        var prydwenArrived = AddGlob(mod, modKey, PrydwenArrivedGlobId, "FO4SF_PrydwenArrived", 0f);
        var mq203Armed = AddGlob(mod, modKey, Mq203ArmedGlobId, "FO4SF_MQ203Armed", 0f);

        var mq106Confront = AddMessage(mod, modKey, Mq106ConfrontMsgId, "FO4SF_MQ106_ConfrontMsg",
            "Fort Hagen Command Center", "The mercenary from Vault 111 waits behind armed synth defenses in Fort Hagen's command room.",
            "Confront Kellogg", "Demand answers about Shaun", "Open fire immediately", "Step back");
        var mq106Terminal = AddMessage(mod, modKey, Mq106TerminalMsgId, "FO4SF_MQ106_TerminalMsg",
            "Kellogg's Command Terminal", "Encrypted Institute transfer logs confirm Shaun was taken to the Institute via relay and reference a cybernetic neural augmenter.",
            "Read Institute transfer logs", "Unlock security doors and recover backup data", "Leave");
        var mq106Debrief = AddMessage(mod, modKey, Mq106DebriefMsgId, "FO4SF_MQ106_DebriefMsg",
            "Reunions Debrief", "With Kellogg defeated and his neural augmenter recovered, Doctor Amari at Goodneighbor's Memory Den may be able to read its memories.",
            "Review Kellogg's augmenter with Nick", "Head straight to Goodneighbor's Memory Den", "Leave");
        var mq106Dossier = AddMessage(mod, modKey, Mq106DossierMsgId, "FO4SF_MQ106_DossierMsg",
            "Agency Memory Den Lead", "Open-Mode case notes point directly to Doctor Amari's Memory Den lab in Goodneighbor to inspect Kellogg's neural augmenter.",
            "Mark Goodneighbor's Memory Den", "Leave");

        var mq106 = MakeStoryQuest(modKey, Mq106QuestId, Mq106QuestEdid, "Reunions",
            questTypeSideKey, Mq106Stages, 500, Mq106Objectives);
        mq106.Aliases = new ExtendedList<SF.AQuestAlias>
        {
            MakeAlias(0, "Kellogg", kelloggRef.FormKey, raiderCombatPackKey, raiderSandboxPackKey),
            MakeAlias(1, "NickValentine", nickRefKey),
            MakeAlias(2, "Dogmeat", dogmeatRefKey),
        };
        var mq106Script = new SF.ScriptEntry { Name = Mq106ScriptName, Flags = SF.ScriptEntry.Flag.Local };
        mq106Script.Properties.Add(ObjProp("XMarkerBase", xMarkerKey));
        mq106Script.Properties.Add(ObjProp("Kellogg", kelloggRef.FormKey));
        mq106Script.Properties.Add(ObjProp("NickValentine", nickRefKey));
        mq106Script.Properties.Add(ObjProp("Dogmeat", dogmeatRefKey));
        mq106Script.Properties.Add(ObjProp("CyberBrain", cyberBrain.FormKey));
        mq106Script.Properties.Add(ObjProp("KelloggPassword", kelloggPassword.FormKey));
        mq106Script.Properties.Add(ObjProp("TerminalProxyActi", mq106TerminalProxy.FormKey));
        mq106Script.Properties.Add(ObjProp("PrydwenArrived", prydwenArrived.FormKey));
        mq106Script.Properties.Add(ObjProp("MQ203Armed", mq203Armed.FormKey));
        mq106Script.Properties.Add(ObjProp("ConfrontMsg", mq106Confront.FormKey));
        mq106Script.Properties.Add(ObjProp("TerminalMsg", mq106Terminal.FormKey));
        mq106Script.Properties.Add(ObjProp("DebriefMsg", mq106Debrief.FormKey));
        mq106Script.Properties.Add(ObjProp("DossierMsg", mq106Dossier.FormKey));
        mq106.VirtualMachineAdapter = MakeAdapter(mq106Script);
        mod.Quests.Add(mq106);

        // ------------------------------------------------------------------ 2. Dangerous Minds (MQ203 -> 0x000AF0)
        var amariNpc = CloneHumanNpc(mod, modKey, DoctorAmariNpcId, "FO4_DoctorAmari", "Doctor Amari",
            femaleTpl, humanRaceKey, femaleVoice, essential: false, female: true);
        // Goodneighbor / Memory Den merged Commonwealth coords (-902.48, -2870.07, 19.20)
        var amariRef = PlacePersistentActor(persistentCell, modKey, DoctorAmariRefId, "FO4SF_MemoryDen_AmariREF",
            amariNpc.FormKey, -902.48f, -2870.07f, 19.20f, 1.57f);

        var loungerProxy = AddProxyActi(mod, modKey, Mq203LoungerProxyActiId, Mq203LoungerProxyActiEdid,
            "Memory Lounger Console", "Use");
        var memoriesCompleted = AddGlob(mod, modKey, MemoriesCompletedGlobId, "FO4SF_MemoriesCompleted", 0f);
        var mq204Armed = AddGlob(mod, modKey, Mq204ArmedGlobId, "FO4SF_MQ204Armed", 0f);

        var mq203AmariTalk = AddMessage(mod, modKey, Mq203AmariTalkMsgId, "FO4SF_MQ203_AmariTalkMsg",
            "Doctor Amari", "Doctor Amari examines Kellogg's neural augmenter and prepares the Memory Den's downstairs pod for a neural trace.",
            "Hand over Kellogg's brain augmenter", "Ask how the Memory Lounger works", "Ask what you are looking for", "Leave");
        var mq203Lounger = AddMessage(mod, modKey, Mq203LoungerMsgId, "FO4SF_MQ203_LoungerMsg",
            "Memory Lounger", "The pod can bridge directly into Kellogg's neural imprint or run an autonomous diagnostic scan.",
            "Enter Kellogg's memories", "Run autonomous pod neural scan", "Leave");
        var mq203MemoryWalk = AddMessage(mod, modKey, Mq203MemoryWalkMsgId, "FO4SF_MQ203_MemoryWalkMsg",
            "Kellogg's Neural Imprint", "Final memory fragments reveal an escaped Institute scientist named Brian Virgil hiding deep inside the Glowing Sea.",
            "Inspect Virgil's file and return to Memory Den", "Skip bridges straight to Virgil's file", "Leave");
        var mq203LabTerminal = AddMessage(mod, modKey, Mq203LabTerminalMsgId, "FO4SF_MQ203_LabTerminalMsg",
            "Memory Den Lab Terminal", "Stored neural-scan output identifies Brian Virgil's last refuge in the southwestern Glowing Sea.",
            "Extract Glowing Sea coordinates for Virgil", "Leave");

        var mq203 = MakeStoryQuest(modKey, Mq203QuestId, Mq203QuestEdid, "Dangerous Minds",
            questTypeSideKey, Mq203Stages, 300, Mq203Objectives);
        mq203.Aliases = new ExtendedList<SF.AQuestAlias>
        {
            MakeAlias(0, "DoctorAmari", amariRef.FormKey),
            MakeAlias(1, "NickValentine", nickRefKey),
        };
        var mq203Script = new SF.ScriptEntry { Name = Mq203ScriptName, Flags = SF.ScriptEntry.Flag.Local };
        mq203Script.Properties.Add(ObjProp("XMarkerBase", xMarkerKey));
        mq203Script.Properties.Add(ObjProp("DoctorAmari", amariRef.FormKey));
        mq203Script.Properties.Add(ObjProp("NickValentine", nickRefKey));
        mq203Script.Properties.Add(ObjProp("CyberBrain", cyberBrain.FormKey));
        mq203Script.Properties.Add(ObjProp("LoungerProxyActi", loungerProxy.FormKey));
        mq203Script.Properties.Add(ObjProp("MemoriesCompleted", memoriesCompleted.FormKey));
        mq203Script.Properties.Add(ObjProp("MQ204Armed", mq204Armed.FormKey));
        mq203Script.Properties.Add(ObjProp("AmariTalkMsg", mq203AmariTalk.FormKey));
        mq203Script.Properties.Add(ObjProp("LoungerMsg", mq203Lounger.FormKey));
        mq203Script.Properties.Add(ObjProp("MemoryWalkMsg", mq203MemoryWalk.FormKey));
        mq203Script.Properties.Add(ObjProp("LabTerminalMsg", mq203LabTerminal.FormKey));
        mq203.VirtualMachineAdapter = MakeAdapter(mq203Script);
        mod.Quests.Add(mq203);

        // ------------------------------------------------------------------ 3. The Glowing Sea (MQ204 -> 0x000B10)
        var isoldeNpc = CloneHumanNpc(mod, modKey, MotherIsoldeNpcId, "FO4_MotherIsolde", "Mother Isolde",
            femaleTpl, humanRaceKey, femaleVoice, essential: false, female: true);
        // Crater of Atom merged Commonwealth coords (-2624.44, -4357.85, 107.64)
        var isoldeRef = PlacePersistentActor(persistentCell, modKey, MotherIsoldeRefId, "FO4SF_Crater_IsoldeREF",
            isoldeNpc.FormKey, -2624.44f, -4357.85f, 107.64f, 0.8f);

        var virgilNpc = CloneHumanNpc(mod, modKey, VirgilNpcId, "FO4_Virgil", "Virgil",
            humanTemplate, humanRaceKey, humanVoiceKey, essential: false, female: false);
        // Rocky Cave / Virgil's Lab merged Commonwealth coords (-2862.82, -4653.27, 143.19)
        var virgilRef = PlacePersistentActor(persistentCell, modKey, VirgilRefId, "FO4SF_VirgilsLab_VirgilREF",
            virgilNpc.FormKey, -2862.82f, -4653.27f, 143.19f, 2.35f);

        var virgilNote = AddMisc(mod, modKey, VirgilNoteMiscId, "FO4SF_VirgilNote",
            "Glowing Sea Cave Directions", 5, 0.0f);
        var mq204LabTerminalProxy = AddProxyActi(mod, modKey, Mq204LabTerminalProxyActiId, Mq204LabTerminalProxyActiEdid,
            "Virgil's Research Terminal", "Access");
        var glowingSeaRadsActive = AddGlob(mod, modKey, GlowingSeaRadsActiveGlobId, "FO4SF_GlowingSeaRadsActive", 0f);
        var mq206Armed = AddGlob(mod, modKey, Mq206ArmedGlobId, "FO4SF_MQ206Armed", 0f);

        var mq204IsoldeTalk = AddMessage(mod, modKey, Mq204IsoldeTalkMsgId, "FO4SF_MQ204_IsoldeTalkMsg",
            "Mother Isolde", "At the Crater of Atom, Mother Isolde knows of a lone recluse sheltering in a rocky cave farther southwest.",
            "Ask about the scientist hiding in the Glowing Sea", "Ask about the Crater of Atom", "Request directions to the Rocky Cave", "Leave");
        var mq204VirgilNote = AddMessage(mod, modKey, Mq204VirgilNoteMsgId, "FO4SF_MQ204_VirgilNoteMsg",
            "Glowing Sea Cave Directions", "A weathered crater map marks a shielded rocky cave further southwest where an ex-Institute scientist built a lab.",
            "Mark Rocky Cave (Virgil's Lab)", "Leave");
        var mq204VirgilTalk = AddMessage(mod, modKey, Mq204VirgilTalkMsgId, "FO4SF_MQ204_VirgilTalkMsg",
            "Virgil", "Virgil explains that the only way inside the Institute is to hijack their molecular relay using a live Courser Chip.",
            "Ask how to reach the Institute", "Ask about the Courser Chip", "Agree to track a Courser at Greenetech Genetics", "Leave");
        var mq204LabTerminal = AddMessage(mod, modKey, Mq204LabTerminalMsgId, "FO4SF_MQ204_LabTerminalMsg",
            "Virgil's Research Terminal", "Laboratory schematics detail how to capture a Courser Chip around Greenetech Genetics to intercept the Institute relay.",
            "Download Courser tracking schematic", "Leave");

        var mq204 = MakeStoryQuest(modKey, Mq204QuestId, Mq204QuestEdid, "The Glowing Sea",
            questTypeSideKey, Mq204Stages, 200, Mq204Objectives);
        mq204.Aliases = new ExtendedList<SF.AQuestAlias>
        {
            MakeAlias(0, "MotherIsolde", isoldeRef.FormKey),
            MakeAlias(1, "Virgil", virgilRef.FormKey),
        };
        var mq204Script = new SF.ScriptEntry { Name = Mq204ScriptName, Flags = SF.ScriptEntry.Flag.Local };
        mq204Script.Properties.Add(ObjProp("XMarkerBase", xMarkerKey));
        mq204Script.Properties.Add(ObjProp("MotherIsolde", isoldeRef.FormKey));
        mq204Script.Properties.Add(ObjProp("Virgil", virgilRef.FormKey));
        mq204Script.Properties.Add(ObjProp("VirgilNote", virgilNote.FormKey));
        mq204Script.Properties.Add(ObjProp("LabTerminalProxyActi", mq204LabTerminalProxy.FormKey));
        mq204Script.Properties.Add(ObjProp("GlowingSeaRadsActive", glowingSeaRadsActive.FormKey));
        mq204Script.Properties.Add(ObjProp("MQ206Armed", mq206Armed.FormKey));
        mq204Script.Properties.Add(ObjProp("IsoldeTalkMsg", mq204IsoldeTalk.FormKey));
        mq204Script.Properties.Add(ObjProp("VirgilNoteMsg", mq204VirgilNote.FormKey));
        mq204Script.Properties.Add(ObjProp("VirgilTalkMsg", mq204VirgilTalk.FormKey));
        mq204Script.Properties.Add(ObjProp("LabTerminalMsg", mq204LabTerminal.FormKey));
        mq204.VirtualMachineAdapter = MakeAdapter(mq204Script);
        mod.Quests.Add(mq204);

        // ------------------------------------------------------------------ 4. The Molecular Level (MQ206 -> 0x000B30)
        var courserNpc = CloneHostileBossNpc(mod, modKey, CourserZ247NpcId, "FO4_CourserZ247", "Z2-47",
            raiderTemplate, weaponKey, ammoKey);
        // Greenetech Genetics merged Commonwealth coords (-1238.10, -2687.39, 12.18)
        var courserRef = PlacePersistentActor(persistentCell, modKey, CourserZ247RefId, "FO4SF_Greenetech_CourserREF",
            courserNpc.FormKey, -1238.10f, -2687.39f, 12.18f, 0.0f);

        var desdemonaNpc = CloneHumanNpc(mod, modKey, DesdemonaNpcId, "FO4_Desdemona", "Desdemona",
            femaleTpl, humanRaceKey, femaleVoice, essential: false, female: true);
        // Railroad HQ merged Commonwealth coords (-734.83, -2696.65, 10.16)
        var desdemonaRef = PlacePersistentActor(persistentCell, modKey, DesdemonaRefId, "FO4SF_Railroad_DesdemonaREF",
            desdemonaNpc.FormKey, -734.83f, -2696.65f, 10.16f, 1.57f);

        var tinkerTomNpc = CloneHumanNpc(mod, modKey, TinkerTomNpcId, "FO4_TinkerTom", "Tinker Tom",
            humanTemplate, humanRaceKey, humanVoiceKey, essential: false, female: false);
        var tinkerTomRef = PlacePersistentActor(persistentCell, modKey, TinkerTomRefId, "FO4SF_Railroad_TinkerTomREF",
            tinkerTomNpc.FormKey, -731.00f, -2695.00f, 10.16f, 3.14f);

        var ingramNpc = CloneHumanNpc(mod, modKey, ProctorIngramNpcId, "FO4_ProctorIngram", "Proctor Ingram",
            femaleTpl, humanRaceKey, femaleVoice, essential: false, female: true);
        // Boston Airport merged Commonwealth coords (-513.23, -2747.60, 10.27)
        var ingramRef = PlacePersistentActor(persistentCell, modKey, ProctorIngramRefId, "FO4SF_Airport_IngramREF",
            ingramNpc.FormKey, -513.23f, -2747.60f, 10.27f, 0.0f);

        var courserChip = AddMisc(mod, modKey, CourserChipMiscId, "FO4SF_CourserChip", "Courser Chip", 300, 0.2f);
        var courserHolotape = AddMisc(mod, modKey, CourserChipHolotapeMiscId, "FO4SF_CourserChipHolotape",
            "Decoded Courser Chip Holotape", 100, 0.1f);
        var interceptorPlans = AddMisc(mod, modKey, SignalInterceptorPlansMiscId, "FO4SF_SignalInterceptorPlans",
            "Signal Interceptor Schematics", 150, 0.1f);

        var scannerProxy = AddProxyActi(mod, modKey, Mq206ScannerProxyActiId, Mq206ScannerProxyActiEdid,
            "Tinker Tom Decoding Scanner", "Decode");
        var consoleProxy = AddProxyActi(mod, modKey, Mq206ConsoleProxyActiId, Mq206ConsoleProxyActiEdid,
            "Signal Interceptor Control Console", "Activate");

        var teleFaction = AddGlob(mod, modKey, Mq206TeleporterFactionGlobId, "FO4SF_MQ206TeleporterFaction", 0f);
        var builtPlatform = AddGlob(mod, modKey, Mq206BuiltPlatformGlobId, "FO4SF_MQ206BuiltPlatform", 0f);
        var builtBeam = AddGlob(mod, modKey, Mq206BuiltBeamGlobId, "FO4SF_MQ206BuiltBeam", 0f);
        var builtDish = AddGlob(mod, modKey, Mq206BuiltDishGlobId, "FO4SF_MQ206BuiltDish", 0f);
        var builtConsole = AddGlob(mod, modKey, Mq206BuiltConsoleGlobId, "FO4SF_MQ206BuiltConsole", 0f);
        var arrayPowered = AddGlob(mod, modKey, Mq206ArrayPoweredGlobId, "FO4SF_MQ206ArrayPowered", 0f);
        var readyTeleport = AddGlob(mod, modKey, Mq206ReadyToTeleportGlobId, "FO4SF_MQ206ReadyToTeleport", 0f);
        var mq207Armed = AddGlob(mod, modKey, Mq207ArmedGlobId, "FO4SF_MQ207Armed", 0f);

        var mq206TinkerDecode = AddMessage(mod, modKey, Mq206TinkerDecodeMsgId, "FO4SF_MQ206_TinkerDecodeMsg",
            "Tinker Tom", "Tinker Tom's analyzer can decrypt the Courser Chip's carrier frequency onto a portable holotape.",
            "Hand over the Courser Chip for decoding", "Ask about the Railroad's scanner", "Leave");
        var mq206Scanner = AddMessage(mod, modKey, Mq206ScannerMsgId, "FO4SF_MQ206_ScannerMsg",
            "Tinker Tom Decoding Scanner", "The Railroad's diagnostic terminal is ready to decode a Courser Chip autonomously.",
            "Self-decode Courser Chip on terminal", "Leave");
        var mq206VirgilPlans = AddMessage(mod, modKey, Mq206VirgilPlansMsgId, "FO4SF_MQ206_VirgilPlansMsg",
            "Signal Interceptor Schematics", "With the chip decoded, Virgil hands over schematics for a four-part Signal Interceptor requiring 27 power.",
            "Take the Signal Interceptor Schematics", "Ask which faction can help build it", "Leave");
        var mq206FactionPick = AddMessage(mod, modKey, Mq206FactionPickMsgId, "FO4SF_MQ206_FactionPickMsg",
            "Signal Interceptor Partner", "Choose an ally engineer to help assemble the Signal Interceptor, or build it solo at Sanctuary's workbench.",
            "Minutemen (Sturges, Sanctuary)", "Railroad (Tinker Tom)", "Brotherhood (Proctor Ingram, Airport)",
            "Solo Open-Mode Self-Build", "Leave");
        var mq206WorkbenchBuild = AddMessage(mod, modKey, Mq206WorkbenchBuildMsgId, "FO4SF_MQ206_WorkbenchBuildMsg",
            "Signal Interceptor Assembly", "Assemble all four relay modules and supply +27 unified grid power to lock onto the Institute signal.",
            "Build Stabilized Reflector Platform", "Build Molecular Beam Emitter", "Build Relay Dish",
            "Build Control Console", "Wire & Power Array (+27 Power)", "Done");
        var mq206RelayFire = AddMessage(mod, modKey, Mq206RelayFireMsgId, "FO4SF_MQ206_RelayFireMsg",
            "Signal Interceptor Ready", "The Stabilized Reflector Platform is powered and locked onto the Institute Concourse carrier frequency.",
            "Teleport to the Institute", "Leave");
        var mq206OpenFallback = AddMessage(mod, modKey, Mq206OpenModeFallbackMsgId, "FO4SF_MQ206_OpenModeFallbackMsg",
            "Autonomous Relay Recovery", "All key faction engineers are unavailable. You can proceed with solo Signal Interceptor assembly at Sanctuary.",
            "Enable solo Open-Mode assembly", "Leave");

        var mq206 = MakeStoryQuest(modKey, Mq206QuestId, Mq206QuestEdid, "The Molecular Level",
            questTypeSideKey, Mq206Stages, 1200, Mq206Objectives);
        mq206.Aliases = new ExtendedList<SF.AQuestAlias>
        {
            MakeAlias(0, "CourserZ247", courserRef.FormKey, raiderCombatPackKey, raiderSandboxPackKey),
            MakeAlias(1, "TinkerTom", tinkerTomRef.FormKey),
            MakeAlias(2, "Virgil", virgilRef.FormKey),
            MakeAlias(3, "Sturges", sturgesRefKey),
            MakeAlias(4, "Desdemona", desdemonaRef.FormKey),
            MakeAlias(5, "ProctorIngram", ingramRef.FormKey),
        };
        var mq206Script = new SF.ScriptEntry { Name = Mq206ScriptName, Flags = SF.ScriptEntry.Flag.Local };
        mq206Script.Properties.Add(ObjProp("XMarkerBase", xMarkerKey));
        mq206Script.Properties.Add(ObjProp("CourserZ247", courserRef.FormKey));
        mq206Script.Properties.Add(ObjProp("Desdemona", desdemonaRef.FormKey));
        mq206Script.Properties.Add(ObjProp("TinkerTom", tinkerTomRef.FormKey));
        mq206Script.Properties.Add(ObjProp("ProctorIngram", ingramRef.FormKey));
        mq206Script.Properties.Add(ObjProp("Sturges", sturgesRefKey));
        mq206Script.Properties.Add(ObjProp("Virgil", virgilRef.FormKey));
        mq206Script.Properties.Add(ObjProp("CourserChip", courserChip.FormKey));
        mq206Script.Properties.Add(ObjProp("CourserChipHolotape", courserHolotape.FormKey));
        mq206Script.Properties.Add(ObjProp("SignalInterceptorPlans", interceptorPlans.FormKey));
        mq206Script.Properties.Add(ObjProp("ScannerProxyActi", scannerProxy.FormKey));
        mq206Script.Properties.Add(ObjProp("ConsoleProxyActi", consoleProxy.FormKey));
        mq206Script.Properties.Add(ObjProp("TeleporterFaction", teleFaction.FormKey));
        mq206Script.Properties.Add(ObjProp("BuiltPlatform", builtPlatform.FormKey));
        mq206Script.Properties.Add(ObjProp("BuiltBeam", builtBeam.FormKey));
        mq206Script.Properties.Add(ObjProp("BuiltDish", builtDish.FormKey));
        mq206Script.Properties.Add(ObjProp("BuiltConsole", builtConsole.FormKey));
        mq206Script.Properties.Add(ObjProp("ArrayPowered", arrayPowered.FormKey));
        mq206Script.Properties.Add(ObjProp("ReadyToTeleport", readyTeleport.FormKey));
        mq206Script.Properties.Add(ObjProp("MQ207Armed", mq207Armed.FormKey));
        mq206Script.Properties.Add(ObjProp("TinkerDecodeMsg", mq206TinkerDecode.FormKey));
        mq206Script.Properties.Add(ObjProp("ScannerMsg", mq206Scanner.FormKey));
        mq206Script.Properties.Add(ObjProp("VirgilPlansMsg", mq206VirgilPlans.FormKey));
        mq206Script.Properties.Add(ObjProp("FactionPickMsg", mq206FactionPick.FormKey));
        mq206Script.Properties.Add(ObjProp("WorkbenchBuildMsg", mq206WorkbenchBuild.FormKey));
        mq206Script.Properties.Add(ObjProp("RelayFireMsg", mq206RelayFire.FormKey));
        mq206Script.Properties.Add(ObjProp("OpenModeFallbackMsg", mq206OpenFallback.FormKey));
        mq206.VirtualMachineAdapter = MakeAdapter(mq206Script);
        mod.Quests.Add(mq206);

        // R4: Per-NPC 360-degree talk proxies carrying each NPC's own display Name (never Codsworth's 0x970)
        AddProxyActi(mod, modKey, AmariTalkActiId, AmariTalkActiEdid, amariNpc.Name?.String ?? "Doctor Amari", "Talk");
        AddProxyActi(mod, modKey, IsoldeTalkActiId, IsoldeTalkActiEdid, isoldeNpc.Name?.String ?? "Mother Isolde", "Talk");
        AddProxyActi(mod, modKey, VirgilTalkActiId, VirgilTalkActiEdid, virgilNpc.Name?.String ?? "Virgil", "Talk");
        AddProxyActi(mod, modKey, DesdemonaTalkActiId, DesdemonaTalkActiEdid, desdemonaNpc.Name?.String ?? "Desdemona", "Talk");
        AddProxyActi(mod, modKey, TinkerTomTalkActiId, TinkerTomTalkActiEdid, tinkerTomNpc.Name?.String ?? "Tinker Tom", "Talk");
        AddProxyActi(mod, modKey, IngramTalkActiId, IngramTalkActiEdid, ingramNpc.Name?.String ?? "Proctor Ingram", "Talk");
    }

    public static void CheckA7cdMissions(
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

        void CheckQuest(uint qid, string edid, string scriptName, ushort[] wantStages, ushort completeStage,
                        (ushort Index, string Text, int TargetAlias)[] wantObjs)
        {
            var q = plug.Quests.FirstOrDefault(x => x.FormKey == new FormKey(key, qid));
            need(q is not null && q.EditorID == edid && NonStartGameReady(q) &&
                 q.QuestType.FormKey == new FormKey(sfEsm, questTypeSideId),
                $"{edid} (0x{qid:X6}) missing or invalid flags/QuestType");
            if (q is null) return;
            need(q.Stages.Select(s => s.Index).SequenceEqual(wantStages), $"{edid} stages mismatch");
            need(q.Stages.All(s => s.LogEntries.Count >= 1 && s.LogEntries[0].Flags is not null),
                $"{edid} has a stage without QSDT QuestLogEntry");
            need(q.Stages.FirstOrDefault(s => s.Index == completeStage)?.LogEntries.Any(
                     l => l.Flags?.HasFlag(SF.QuestLogEntry.Flag.CompleteQuest) == true) == true,
                $"{edid} stage {completeStage} lacks CompleteQuest");
            need(q.Objectives.Select(o => o.Index).SequenceEqual(wantObjs.Select(o => o.Index)) &&
                 q.Objectives.All(o => o.Flags is not null),
                $"{edid} objectives mismatch or lack Flags");
            need(q.VirtualMachineAdapter?.Scripts.Any(s => s.Name == scriptName) == true,
                $"{edid} lacks script binding {scriptName}");
        }

        void CheckBossNpc(uint npcId, string edid)
        {
            var n = plug.Npcs.FirstOrDefault(x => x.FormKey == new FormKey(key, npcId));
            need(n is not null && n.EditorID == edid &&
                 n.Flags.HasFlag(SF.Npc.Flag.Unique) &&
                 !n.Flags.HasFlag(SF.Npc.Flag.Essential) &&
                 !n.Flags.HasFlag(SF.Npc.Flag.Protected) &&
                 !n.Flags.HasFlag(SF.Npc.Flag.Respawn) &&
                 n.ActivateTextOverride is null &&
                 (n.Items?.Count ?? 0) >= 2,
                $"Hostile boss {edid} (0x{npcId:X6}) missing or invalid combat flags/items");
        }

        void CheckFemaleNpc(uint npcId, string edid)
        {
            var n = plug.Npcs.FirstOrDefault(x => x.FormKey == new FormKey(key, npcId));
            need(n is not null && n.EditorID == edid &&
                 n.Flags.HasFlag(SF.Npc.Flag.Female) &&
                 !n.Flags.HasFlag(SF.Npc.Flag.Essential) &&
                 !n.Flags.HasFlag(SF.Npc.Flag.Protected),
                $"Female NPC {edid} (0x{npcId:X6}) missing Female flag or invalid W7 flags");
        }

        void CheckProxyActi(uint actiId, string edid)
        {
            var a = plug.Activators.FirstOrDefault(x => x.FormKey == new FormKey(key, actiId));
            need(a is not null && a.EditorID == edid &&
                 a.ActivationAngle == 360 && !a.InvertFacing &&
                 string.Equals(a.Model?.File?.GivenPath, ProxyActiModel, StringComparison.OrdinalIgnoreCase) &&
                 !(a.Model?.File?.GivenPath?.StartsWith("Meshes\\", StringComparison.OrdinalIgnoreCase) ?? true),
                $"Proxy ACTI {edid} (0x{actiId:X6}) missing or invalid model path");
        }

        // 1. MQ106 Reunions
        CheckQuest(Mq106QuestId, Mq106QuestEdid, Mq106ScriptName, Mq106Stages, 500, Mq106Objectives);
        CheckBossNpc(KelloggNpcId, "FO4_Kellogg");
        CheckProxyActi(Mq106TerminalProxyActiId, Mq106TerminalProxyActiEdid);
        need(plug.MiscItems.Any(m => m.FormKey == new FormKey(key, CyberBrainMiscId) && m.EditorID == "FO4SF_CyberBrain") &&
             plug.MiscItems.Any(m => m.FormKey == new FormKey(key, KelloggPasswordMiscId) && m.EditorID == "FO4SF_KelloggPassword"),
            "FO4SF_MQ106 clue items (0xAD3 / 0xAD4) missing");
        need(plug.Globals.Any(g => g.FormKey == new FormKey(key, PrydwenArrivedGlobId)) &&
             plug.Globals.Any(g => g.FormKey == new FormKey(key, Mq203ArmedGlobId)),
            "FO4SF_MQ106 GLOBs (0xAD6 / 0xAD7) missing");

        // 2. MQ203 Dangerous Minds
        CheckQuest(Mq203QuestId, Mq203QuestEdid, Mq203ScriptName, Mq203Stages, 300, Mq203Objectives);
        CheckFemaleNpc(DoctorAmariNpcId, "FO4_DoctorAmari");
        CheckProxyActi(Mq203LoungerProxyActiId, Mq203LoungerProxyActiEdid);
        need(plug.Globals.Any(g => g.FormKey == new FormKey(key, MemoriesCompletedGlobId)) &&
             plug.Globals.Any(g => g.FormKey == new FormKey(key, Mq204ArmedGlobId)),
            "FO4SF_MQ203 GLOBs (0xAF4 / 0xAF5) missing");

        // 3. MQ204 The Glowing Sea
        CheckQuest(Mq204QuestId, Mq204QuestEdid, Mq204ScriptName, Mq204Stages, 200, Mq204Objectives);
        CheckFemaleNpc(MotherIsoldeNpcId, "FO4_MotherIsolde");
        CheckProxyActi(Mq204LabTerminalProxyActiId, Mq204LabTerminalProxyActiEdid);
        need(plug.MiscItems.Any(m => m.FormKey == new FormKey(key, VirgilNoteMiscId) && m.EditorID == "FO4SF_VirgilNote"),
            "FO4SF_VirgilNote (0xB15) missing");
        need(plug.Globals.Any(g => g.FormKey == new FormKey(key, GlowingSeaRadsActiveGlobId)) &&
             plug.Globals.Any(g => g.FormKey == new FormKey(key, Mq206ArmedGlobId)),
            "FO4SF_MQ204 GLOBs (0xB17 / 0xB18) missing");

        // 4. MQ206 The Molecular Level
        CheckQuest(Mq206QuestId, Mq206QuestEdid, Mq206ScriptName, Mq206Stages, 1200, Mq206Objectives);
        CheckBossNpc(CourserZ247NpcId, "FO4_CourserZ247");
        CheckFemaleNpc(DesdemonaNpcId, "FO4_Desdemona");
        CheckFemaleNpc(ProctorIngramNpcId, "FO4_ProctorIngram");
        CheckProxyActi(Mq206ScannerProxyActiId, Mq206ScannerProxyActiEdid);
        CheckProxyActi(Mq206ConsoleProxyActiId, Mq206ConsoleProxyActiEdid);
        need(plug.MiscItems.Any(m => m.FormKey == new FormKey(key, CourserChipMiscId) && m.EditorID == "FO4SF_CourserChip") &&
             plug.MiscItems.Any(m => m.FormKey == new FormKey(key, CourserChipHolotapeMiscId) && m.EditorID == "FO4SF_CourserChipHolotape") &&
             plug.MiscItems.Any(m => m.FormKey == new FormKey(key, SignalInterceptorPlansMiscId) && m.EditorID == "FO4SF_SignalInterceptorPlans"),
            "FO4SF_MQ206 items (0xB39 / 0xB3A / 0xB3B) missing");
        foreach (var gid in new[]
        {
            Mq206TeleporterFactionGlobId, Mq206BuiltPlatformGlobId, Mq206BuiltBeamGlobId,
            Mq206BuiltDishGlobId, Mq206BuiltConsoleGlobId, Mq206ArrayPoweredGlobId,
            Mq206ReadyToTeleportGlobId, Mq207ArmedGlobId,
        })
        {
            need(plug.Globals.Any(g => g.FormKey == new FormKey(key, gid)),
                $"FO4SF_MQ206 GLOB 0x{gid:X6} missing");
        }

        var a7cdRefs = plug.Worldspaces.FirstOrDefault()?.TopCell?.Persistent.OfType<SF.IPlacedNpcGetter>()
            .Where(r => IsA7cdActorRefId(r.FormKey.ID)).ToList() ?? [];
        need(a7cdRefs.Count == 8 && a7cdRefs.All(r => (r.MajorRecordFlagsRaw & 0x800) != 0),
            "A7cd persistent ACHRs must all carry InitiallyDisabled (0x800, R3)");

        foreach (var (actiId, edid, npcId) in new (uint, string, uint)[]
        {
            (AmariTalkActiId, AmariTalkActiEdid, DoctorAmariNpcId),
            (IsoldeTalkActiId, IsoldeTalkActiEdid, MotherIsoldeNpcId),
            (VirgilTalkActiId, VirgilTalkActiEdid, VirgilNpcId),
            (DesdemonaTalkActiId, DesdemonaTalkActiEdid, DesdemonaNpcId),
            (TinkerTomTalkActiId, TinkerTomTalkActiEdid, TinkerTomNpcId),
            (IngramTalkActiId, IngramTalkActiEdid, ProctorIngramNpcId),
        })
        {
            var talkActi = plug.Activators.FirstOrDefault(x => x.FormKey == new FormKey(key, actiId));
            var talkNpc = plug.Npcs.FirstOrDefault(n => n.FormKey == new FormKey(key, npcId));
            need(talkActi is not null && talkNpc is not null &&
                 talkActi.EditorID == edid &&
                 talkActi.ActivationAngle == 360 && !talkActi.InvertFacing &&
                 talkActi.ActivateTextOverride?.String == "Talk" &&
                 !string.IsNullOrEmpty(talkNpc.Name?.String) &&
                 talkActi.Name?.String == talkNpc.Name?.String &&
                 string.Equals(talkActi.Model?.File?.GivenPath, ProxyActiModel, StringComparison.OrdinalIgnoreCase),
                $"A7cd talk proxy {edid} (0x{actiId:X6}) missing or Name mismatch with NPC 0x{npcId:X6}");
        }
    }
}
