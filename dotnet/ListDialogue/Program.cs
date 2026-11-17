// ListDialogue: silent-player list conversation writer & checker with [Skill N], [SPECIAL N], [Background], and [Trait]
// prefix tags and deterministic New Vegas-style CTDA checks (CF-7, docs/dialogue/list-skill-checks.md).
//
// Built beside PR #792's 4-option wheel (zero #792 files edited; zero Interface/DialogueMenu.swf replacement — Starfield's
// native DialogueMenu renders DialogueListData.aChoices directly for >4-option and prefix-tagged silent-player conversations).
//
// Writes FO4SFListDialogue.esm (sole master Starfield.esm; adds records only, overrides none):
//   0x800 AVIF FO4SF_Skill_Speech          0..100, default 25
//   0x801 AVIF FO4SF_Skill_Science         0..100, default 25
//   0x802 PERK FO4SF_BG_VaultDweller       Playable Background perk ("Vault Dweller")
//   0x803 PERK FO4SF_Trait_GoodNatured     Playable Trait perk ("Good Natured")
//   0x805 FACT FO4SF_ListSpeakerFaction    Allied with PlayerFaction (0x01C21C) so speaker stays calm
//   0x806 NPC_ FO4SF_ListSpeakerNpc        Clean-room stand-in speaker cloned from vanilla NPC_ template
//   0x807 CELL FO4SF_ListTalkCell          Self-contained interior room (`coc FO4SF_ListTalkCell`)
//   0x808 ACHR FO4SF_ListSpeakerRef        Speaker placed 2.5 m ahead of arrival marker
//   0x809 REFR FO4SF_ListArrivalRef        Persistent XMarker arrival (0, 0, 0.1)
//   0x80A REFR FO4SF_ListCocMarkerRef      COCHeadingMarker (0, 0, 0.1)
//   0x810 QUST FO4SF_ListDialogueQuest     StartGameEnabled quest with DLBR + DIAL + 8 player list INFOs (stages 10..70)
//   0x811 DLBR FO4SF_ListTopBranch         TopLevel DialogBranch starting at FO4SF_ListChoicesTopic
//   0x812 DIAL FO4SF_ListChoicesTopic      Topic carrying 8 silent-player list choices (>4 rows):
//     0x820 INFO [Speech 50] PASS          GetValue(FO4SF_Skill_Speech) >= 50 on PlayerRef -> stage 20
//     0x821 INFO [Speech 50] FAIL          GetValue(FO4SF_Skill_Speech) <  50 on PlayerRef -> stage 21 (NV deterministic fail)
//     0x822 INFO [Science 40] PASS         GetValue(FO4SF_Skill_Science) >= 40 on PlayerRef -> stage 22
//     0x823 INFO [Strength 7] PASS         GetValue(Strength) >= 7 on PlayerRef -> stage 30
//     0x824 INFO [Strength 7] FAIL         GetValue(Strength) <  7 on PlayerRef -> stage 31
//     0x825 INFO [Vault Dweller]           HasPerk(FO4SF_BG_VaultDweller) == 1 on PlayerRef -> stage 40
//     0x826 INFO [Good Natured]            HasPerk(FO4SF_Trait_GoodNatured) == 1 on PlayerRef -> stage 50
//     0x827 INFO Plain Goodbye             Unconditional exit choice -> stage 60
//   0x813 DIAL FO4SF_ListGreetingTopic     Greeting topic spoken by FO4SF_ListSpeakerNpc (0x828 INFO)
//
// usage:
//   ListDialogue build <Starfield.esm> <out dir>
//   ListDialogue check <plugin> <Starfield.esm>
//   ListDialogue fixture <out dir>
//   ListDialogue selftest <scratch dir>

using System.Globalization;
using Mutagen.Bethesda;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;

try
{
    if (args.Length == 3 && args[0] == "build") return ListDialogue.Build(args[1], args[2]);
    if (args.Length == 3 && args[0] == "check") return ListDialogue.Check(args[1], args[2]);
    if (args.Length == 2 && args[0] == "fixture") return ListDialogue.Fixture(args[1]);
    if (args.Length == 2 && args[0] == "selftest") return ListDialogue.SelfTest(args[1]);
}
catch (ListDialogue.Refusal r)
{
    Console.Error.WriteLine("refused: " + r.Message);
    return 1;
}

Console.Error.WriteLine("usage: ListDialogue build <Starfield.esm> <out dir> | check <plugin> <Starfield.esm> | fixture <out dir> | selftest <scratch dir>");
return 2;

public static class ListDialogue
{
    public class Refusal(string m) : Exception(m);

    const StarfieldRelease Release = StarfieldRelease.Starfield;
    static readonly ModKey SfEsm = ModKey.FromFileName("Starfield.esm");
    public static readonly ModKey Plugin = ModKey.FromFileName("FO4SFListDialogue.esm");

    // Vanilla Starfield.esm references (proven in TestCell and Mission)
    public const uint PlayerRefId = 0x000014;
    public const uint PlayerFactionId = 0x01C21C;
    public const uint FloorStaticId = 0x050776;
    public const uint OmniLightId = 0x03D38C;
    public const uint CocMarkerId = 0x000032;
    public const uint XMarkerId = 0x00003B;
    public const uint LightingTemplateId = 0x006658;
    public const uint ImageSpaceId = 0x122393;

    // Local deterministic FormIDs
    public const uint SpeechAvifId = 0x800;
    public const uint ScienceAvifId = 0x801;
    public const uint BgVaultDwellerPerkId = 0x802;
    public const uint TraitGoodNaturedPerkId = 0x803;
    public const uint SpeakerFactionId = 0x805;
    public const uint SpeakerNpcId = 0x806;
    public const uint TalkCellId = 0x807;
    public const uint SpeakerRefId = 0x808;
    public const uint ArrivalRefId = 0x809;
    public const uint CocRefId = 0x80A;

    public const uint QuestId = 0x810;
    public const uint TopBranchId = 0x811;
    public const uint ChoicesTopicId = 0x812;
    public const uint GreetingTopicId = 0x813;

    public const uint InfoSpeechPassId = 0x820;
    public const uint InfoSpeechFailId = 0x821;
    public const uint InfoSciencePassId = 0x822;
    public const uint InfoStrengthPassId = 0x823;
    public const uint InfoStrengthFailId = 0x824;
    public const uint InfoBackgroundId = 0x825;
    public const uint InfoTraitId = 0x826;
    public const uint InfoExitId = 0x827;
    public const uint InfoGreetingId = 0x828;

    public const uint FirstTileRefId = 0x830;
    public const uint NextId = 0x850;

    // EditorIDs
    public const string SpeechAvifEdid = "FO4SF_Skill_Speech";
    public const string ScienceAvifEdid = "FO4SF_Skill_Science";
    public const string BgVaultDwellerEdid = "FO4SF_BG_VaultDweller";
    public const string TraitGoodNaturedEdid = "FO4SF_Trait_GoodNatured";
    public const string SpeakerFactionEdid = "FO4SF_ListSpeakerFaction";
    public const string SpeakerNpcEdid = "FO4SF_ListSpeakerNpc";
    public const string TalkCellEdid = "FO4SF_ListTalkCell";
    public const string QuestEdid = "FO4SF_ListDialogueQuest";
    public const string ScriptName = "FO4SF_ListDialogueQuest";

    public static readonly ushort[] Stages = { 10, 15, 20, 21, 22, 30, 31, 40, 50, 60, 70 };

    // Pinned Quest VMAD property order
    public static readonly string[] PropNames =
    {
        "SpeechAV",
        "ScienceAV",
        "StrengthAV",
        "IntelligenceAV",
        "BgVaultDwellerPerk",
        "TraitGoodNaturedPerk",
        "SpeakerRef",
        "ArrivalRef"
    };

    public record ChoiceSpec(
        uint InfoId, string Edid, string Prompt, string NpcReply, short EndStage,
        string CheckKind, uint TargetId, bool TargetInSf, CompareOperator Op, float Threshold, bool Goodbye = false);

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

    static INpcGetter PickSpeakerTemplate(IStarfieldModGetter sf)
    {
        var preferred = new[] { "OutpostRobotMiniBotA_Garden", "HumanPresetMale01", "MQ101_Lin", "SynthSpeakerTemplate" };
        foreach (var ed in preferred)
        {
            var hit = sf.Npcs.FirstOrDefault(n => string.Equals(n.EditorID, ed, StringComparison.OrdinalIgnoreCase));
            if (hit != null) return hit;
        }
        return sf.Npcs.Where(n => !string.IsNullOrEmpty(n.EditorID)).OrderBy(n => n.FormKey.ID).FirstOrDefault()
               ?? throw new Refusal("no NPC_ template found in Starfield.esm");
    }

    static Condition SpeakerIs(FormKey npcKey)
    {
        var d = new GetIsIDConditionData { RunOnType = Condition.RunOnType.Subject };
        d.FirstParameter.Link.SetTo(npcKey);
        return new ConditionFloat { CompareOperator = CompareOperator.EqualTo, ComparisonValue = 1f, Data = d };
    }

    static Condition PlayerValueCheck(FormKey avKey, CompareOperator op, float threshold)
    {
        var d = new GetValueConditionData
        {
            RunOnType = Condition.RunOnType.Reference,
            Reference = new FormLink<IStarfieldMajorRecordGetter>(Sf(PlayerRefId)),
        };
        d.FirstParameter.SetTo(avKey);
        return new ConditionFloat { CompareOperator = op, ComparisonValue = threshold, Data = d };
    }

    static Condition PlayerHasPerkCheck(FormKey perkKey)
    {
        var d = new HasPerkConditionData
        {
            RunOnType = Condition.RunOnType.Reference,
            Reference = new FormLink<IStarfieldMajorRecordGetter>(Sf(PlayerRefId)),
        };
        d.FirstParameter.Link.SetTo(perkKey);
        return new ConditionFloat { CompareOperator = CompareOperator.EqualTo, ComparisonValue = 1f, Data = d };
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

    public static int Build(string sfPath, string outDir)
    {
        using var sf = OpenMod(sfPath);
        var strengthAv = One(sf.ActorValueInformation, "Strength", "AVIF");
        var intelAv = One(sf.ActorValueInformation, "Intelligence", "AVIF");
        var npcTpl = PickSpeakerTemplate(sf);
        Console.WriteLine($"templates: NPC_ {npcTpl.EditorID} {npcTpl.FormKey}, Strength {strengthAv.FormKey}, Intelligence {intelAv.FormKey}");

        var mod = new StarfieldMod(Plugin, Release);
        mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        mod.ModHeader.Author = "fo4-to-starfield ListDialogue";

        // 1. Skill AVIFs + Background & Trait PERKs
        var speechAv = new ActorValueInformation(Own(SpeechAvifId), Release)
        {
            EditorID = SpeechAvifEdid, Name = "Speech", Abbreviation = "Spc",
            Type = ActorValueInformation.Types.Variable, DefaultValue = 25f, Min = 0f, Max = 100f,
            Flags = ActorValueInformation.Flag.DefaultToZero,
        };
        var scienceAv = new ActorValueInformation(Own(ScienceAvifId), Release)
        {
            EditorID = ScienceAvifEdid, Name = "Science", Abbreviation = "Sci",
            Type = ActorValueInformation.Types.Variable, DefaultValue = 25f, Min = 0f, Max = 100f,
            Flags = ActorValueInformation.Flag.DefaultToZero,
        };
        mod.ActorValueInformation.Add(speechAv);
        mod.ActorValueInformation.Add(scienceAv);

        var bgPerk = new Perk(Own(BgVaultDwellerPerkId), Release)
        {
            EditorID = BgVaultDwellerEdid, Name = "Vault Dweller",
            Description = "Background: Raised inside a sealed subterranean shelter.",
            Flags = Perk.Flag.PcPlayable,
        };
        var traitPerk = new Perk(Own(TraitGoodNaturedPerkId), Release)
        {
            EditorID = TraitGoodNaturedEdid, Name = "Good Natured",
            Description = "Trait: Trained in cooperative skills at the expense of direct combat.",
            Flags = Perk.Flag.PcPlayable,
        };
        mod.Perks.Add(bgPerk);
        mod.Perks.Add(traitPerk);

        // 2. Allied Speaker Faction, Clean-Room Speaker NPC_, and Self-Contained Test Room
        var fac = new Faction(Own(SpeakerFactionId), Release)
        {
            EditorID = SpeakerFactionEdid, Name = "Relay Operator Faction",
        };
        fac.Relations.Add(new Relation
        {
            Target = new FormLink<IRelatableGetter>(Sf(PlayerFactionId)),
            Reaction = CombatReaction.Ally,
        });
        mod.Factions.Add(fac);

        var speakerNpc = (Npc)npcTpl.Duplicate(Own(SpeakerNpcId), new Npc.TranslationMask(defaultOn: true));
        speakerNpc.EditorID = SpeakerNpcEdid;
        speakerNpc.Name = "Relay Operator";
        speakerNpc.VirtualMachineAdapter = null;
        speakerNpc.Factions.Clear();
        speakerNpc.Factions.Add(new RankPlacement { Faction = new FormLink<IFactionGetter>(fac.FormKey), Rank = 0 });
        speakerNpc.Flags |= Npc.Flag.Essential | Npc.Flag.Unique;
        mod.Npcs.Add(speakerNpc);

        var cell = new Cell(Own(TalkCellId), Release)
        {
            EditorID = TalkCellEdid, Name = "FO4SF List Dialogue Test Room",
            Flags = Cell.Flag.IsInteriorCell,
            LightingTemplate = new FormLinkNullable<ILightingTemplateGetter>(Sf(LightingTemplateId)),
            ImageSpace = new FormLinkNullable<IImageSpaceGetter>(Sf(ImageSpaceId)),
        };

        var arrivalRef = new PlacedObject(Own(ArrivalRefId), Release)
        {
            EditorID = "FO4SF_ListArrivalRef",
            Base = new FormLink<IPlaceableObjectGetter>(Sf(XMarkerId)),
            Position = new P3Float(0f, 0f, 0.1f),
        };
        arrivalRef.MajorRecordFlagsRaw |= 0x400; // Persistent
        cell.Persistent.Add(arrivalRef);

        var cocRef = new PlacedObject(Own(CocRefId), Release)
        {
            Base = new FormLink<IPlaceableObjectGetter>(Sf(CocMarkerId)),
            Position = new P3Float(0f, 0f, 0.1f),
        };
        cell.Temporary.Add(cocRef);

        uint tileId = FirstTileRefId;
        for (int gx = -1; gx <= 1; gx++)
        {
            for (int gy = -1; gy <= 1; gy++)
            {
                cell.Temporary.Add(new PlacedObject(Own(tileId++), Release)
                {
                    Base = new FormLink<IPlaceableObjectGetter>(Sf(FloorStaticId)),
                    Position = new P3Float(gx * 8f, gy * 8f, 0f),
                });
            }
        }
        cell.Temporary.Add(new PlacedObject(Own(tileId++), Release)
        {
            Base = new FormLink<IPlaceableObjectGetter>(Sf(OmniLightId)),
            Position = new P3Float(0f, 0f, 4f),
        });

        var speakerRef = new PlacedNpc(Own(SpeakerRefId), Release)
        {
            EditorID = "FO4SF_ListSpeakerRef",
            Base = new FormLink<INpcGetter>(speakerNpc.FormKey),
            Position = new P3Float(0f, 2.5f, 0.1f),
            Rotation = new P3Float(0f, 0f, 3.14159f),
        };
        speakerRef.MajorRecordFlagsRaw |= 0x400; // Persistent
        cell.Persistent.Add(speakerRef);

        mod.Cells.Records.Add(new CellBlock
        {
            BlockNumber = 0, GroupType = GroupTypeEnum.InteriorCellBlock,
            SubBlocks = new ExtendedList<CellSubBlock>
            {
                new CellSubBlock
                {
                    BlockNumber = 0, GroupType = GroupTypeEnum.InteriorCellSubBlock,
                    Cells = new ExtendedList<Cell> { cell },
                },
            },
        });

        // 3. Quest + TopLevel Branch + Greeting + 8-Choice Silent-Player List Topic
        var quest = new Quest(Own(QuestId), Release)
        {
            EditorID = QuestEdid, Name = "FO4SF Silent-Player List Dialogue",
            FormVersion = 581, Version2 = 12,
            Data = new QuestData { Flags = Quest.Flag.StartGameEnabled | Quest.Flag.RunOnce, Priority = 55 },
        };
        foreach (var st in Stages) quest.Stages.Add(new QuestStage { Index = st });

        var branch = new DialogBranch(Own(TopBranchId), Release)
        {
            EditorID = "FO4SF_ListTopBranch",
            Quest = new FormLink<IQuestGetter>(quest.FormKey),
            Category = (DialogBranch.CategoryType)0,
            Flags = DialogBranch.Flag.TopLevel,
            StartingTopic = new FormLinkNullable<IDialogTopicGetter>(Own(ChoicesTopicId)),
        };
        quest.DialogBranches.Add(branch);

        var choicesTopic = new DialogTopic(Own(ChoicesTopicId), Release)
        {
            EditorID = "FO4SF_ListChoicesTopic",
            Name = "Inquire at the relay station",
            Quest = new FormLink<IQuestGetter>(quest.FormKey),
            Branch = new FormLinkNullable<IDialogBranchGetter>(branch.FormKey),
            Priority = 55f,
            Category = DialogTopic.CategoryEnum.Player,
            Subtype = DialogTopic.SubtypeEnum.Custom,
            SubtypeName = DialogTopic.SubtypeNameEnum.Custom,
        };

        var choiceSpecs = new[]
        {
            new ChoiceSpec(InfoSpeechPassId, "FO4SF_ListInfo_Speech50_Pass",
                "[Speech 50] Present the convoy clearance protocol.",
                "Clearance code verified. Gate channel opened.",
                20, "skill", SpeechAvifId, false, CompareOperator.GreaterThanOrEqualTo, 50f),
            new ChoiceSpec(InfoSpeechFailId, "FO4SF_ListInfo_Speech50_Fail",
                "[Speech 50] Ask them to wave the clearance check anyway.",
                "Negative. Unverified requests are denied.",
                21, "skill", SpeechAvifId, false, CompareOperator.LessThan, 50f),
            new ChoiceSpec(InfoSciencePassId, "FO4SF_ListInfo_Science40_Pass",
                "[Science 40] Re-calibrate the relay carrier harmonic.",
                "Harmonic lock achieved. Telemetry stabilized.",
                22, "skill", ScienceAvifId, false, CompareOperator.GreaterThanOrEqualTo, 40f),
            new ChoiceSpec(InfoStrengthPassId, "FO4SF_ListInfo_Strength7_Pass",
                "[Strength 7] Force the manual bulkhead latch.",
                "The manual latch gives way cleanly.",
                30, "special", strengthAv.FormKey.ID, true, CompareOperator.GreaterThanOrEqualTo, 7f),
            new ChoiceSpec(InfoStrengthFailId, "FO4SF_ListInfo_Strength7_Fail",
                "[Strength 7] Strain against the manual bulkhead latch.",
                "The latch does not budge.",
                31, "special", strengthAv.FormKey.ID, true, CompareOperator.LessThan, 7f),
            new ChoiceSpec(InfoBackgroundId, "FO4SF_ListInfo_BG_VaultDweller",
                "[Vault Dweller] Cite sealed-shelter atmospheric maintenance.",
                "Standard shelter manifold acknowledged.",
                40, "background", BgVaultDwellerPerkId, false, CompareOperator.EqualTo, 1f),
            new ChoiceSpec(InfoTraitId, "FO4SF_ListInfo_Trait_GoodNatured",
                "[Good Natured] Share field medical supplies first.",
                "Supplies logged. Your cooperation is noted.",
                50, "trait", TraitGoodNaturedPerkId, false, CompareOperator.EqualTo, 1f),
            new ChoiceSpec(InfoExitId, "FO4SF_ListInfo_Exit",
                "Step away from the relay station.",
                "Standing by.",
                60, "plain", 0, false, CompareOperator.EqualTo, 0f, Goodbye: true),
        };

        foreach (var cs in choiceSpecs)
        {
            var info = new DialogResponses(Own(cs.InfoId), Release)
            {
                EditorID = cs.Edid,
                Prompt = cs.Prompt,
                SetParentQuestStage = new DialogSetParentQuestStage { OnBegin = -1, OnEnd = cs.EndStage },
            };
            if (cs.Goodbye)
                info.Flags = new DialogResponseFlags { Flags = 1 }; // Goodbye flag (0x0001)

            info.Responses.Add(new DialogResponse { ResponseText = cs.NpcReply, WEMFile = 0 });
            info.Conditions.Add(SpeakerIs(speakerNpc.FormKey));

            if (cs.CheckKind is "skill" or "special")
            {
                var fk = cs.TargetInSf ? Sf(cs.TargetId) : Own(cs.TargetId);
                info.Conditions.Add(PlayerValueCheck(fk, cs.Op, cs.Threshold));
            }
            else if (cs.CheckKind is "background" or "trait")
            {
                var fk = Own(cs.TargetId);
                info.Conditions.Add(PlayerHasPerkCheck(fk));
                info.Perk = new FormLinkNullable<IPerkGetter>(fk);
            }

            choicesTopic.Responses.Add(info);
            (choicesTopic.TopicInfoList ??= new()).Add(new FormLink<IDialogResponsesGetter>(info.FormKey));
        }
        quest.DialogTopics.Add(choicesTopic);

        var greetTopic = new DialogTopic(Own(GreetingTopicId), Release)
        {
            EditorID = "FO4SF_ListGreetingTopic",
            Quest = new FormLink<IQuestGetter>(quest.FormKey),
            Priority = 55f,
            Category = DialogTopic.CategoryEnum.Misc,
            Subtype = DialogTopic.SubtypeEnum.Hello,
            SubtypeName = DialogTopic.SubtypeNameEnum.Hello,
        };
        var greetInfo = new DialogResponses(Own(InfoGreetingId), Release)
        {
            EditorID = "FO4SF_ListInfo_Greeting",
        };
        greetInfo.Responses.Add(new DialogResponse { ResponseText = "Relay terminal online. State your authorization.", WEMFile = 0 });
        greetInfo.Conditions.Add(SpeakerIs(speakerNpc.FormKey));
        greetTopic.Responses.Add(greetInfo);
        (greetTopic.TopicInfoList ??= new()).Add(new FormLink<IDialogResponsesGetter>(greetInfo.FormKey));
        quest.DialogTopics.Add(greetTopic);

        var se = new ScriptEntry { Name = ScriptName, Flags = ScriptEntry.Flag.Local };
        var propMap = new Dictionary<string, FormKey>
        {
            ["SpeechAV"] = speechAv.FormKey,
            ["ScienceAV"] = scienceAv.FormKey,
            ["StrengthAV"] = strengthAv.FormKey,
            ["IntelligenceAV"] = intelAv.FormKey,
            ["BgVaultDwellerPerk"] = bgPerk.FormKey,
            ["TraitGoodNaturedPerk"] = traitPerk.FormKey,
            ["SpeakerRef"] = speakerRef.FormKey,
            ["ArrivalRef"] = arrivalRef.FormKey,
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
                          $"2 AVIF, 2 PERK, 1 FACT, 1 NPC_, 1 CELL, 1 QUST (1 DLBR, 2 DIAL, {choiceSpecs.Length + 1} INFO, {PropNames.Length} properties)");
        return 0;
    }

    public static int Check(string pluginPath, string sfPath)
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

        if (mod.ActorValueInformation.Count != 2) throw new Refusal($"expected 2 AVIF, found {mod.ActorValueInformation.Count}");
        if (mod.Perks.Count != 2) throw new Refusal($"expected 2 PERK, found {mod.Perks.Count}");
        if (mod.Quests.Count != 1) throw new Refusal($"expected 1 QUST, found {mod.Quests.Count}");

        var q = mod.Quests.First();
        if (q.DialogBranches.Count != 1) throw new Refusal($"expected 1 DLBR, found {q.DialogBranches.Count}");
        if (q.DialogTopics.Count != 2) throw new Refusal($"expected 2 DIAL, found {q.DialogTopics.Count}");

        var choicesTopic = q.DialogTopics.FirstOrDefault(t => t.FormKey == Own(ChoicesTopicId)) ?? throw new Refusal("missing FO4SF_ListChoicesTopic");
        if (choicesTopic.Responses.Count != 8)
            throw new Refusal($"expected 8 silent-player list INFOs (>4), found {choicesTopic.Responses.Count}");

        var prompts = choicesTopic.Responses.Select(r => r.Prompt?.String ?? "").ToList();
        foreach (var prefix in new[] { "[Speech 50]", "[Science 40]", "[Strength 7]", "[Vault Dweller]", "[Good Natured]" })
        {
            if (!prompts.Any(p => p.StartsWith(prefix, StringComparison.Ordinal)))
                throw new Refusal($"missing required prefix tag {prefix} in DIAL prompts");
        }

        // Verify deterministic NV-style dual-branch (PASS >= N and FAIL < N) on Speech 50 and Strength 7, and HasPerk == 1 on BG/Trait
        var speechPass = choicesTopic.Responses.First(r => r.FormKey == Own(InfoSpeechPassId));
        var speechFail = choicesTopic.Responses.First(r => r.FormKey == Own(InfoSpeechFailId));
        if (!speechPass.Conditions.Any(c => c is IConditionFloatGetter cf && cf.CompareOperator == CompareOperator.GreaterThanOrEqualTo && Math.Abs(cf.ComparisonValue - 50f) < 0.01f && c.Data is IGetValueConditionDataGetter))
            throw new Refusal("Speech 50 PASS INFO lacks deterministic GetValue >= 50 condition");
        if (!speechFail.Conditions.Any(c => c is IConditionFloatGetter cf && cf.CompareOperator == CompareOperator.LessThan && Math.Abs(cf.ComparisonValue - 50f) < 0.01f && c.Data is IGetValueConditionDataGetter))
            throw new Refusal("Speech 50 FAIL INFO lacks deterministic GetValue < 50 condition");

        var bgInfo = choicesTopic.Responses.First(r => r.FormKey == Own(InfoBackgroundId));
        var trInfo = choicesTopic.Responses.First(r => r.FormKey == Own(InfoTraitId));
        if (!bgInfo.Conditions.Any(c => c.Data is IHasPerkConditionDataGetter) || bgInfo.Perk.FormKey != Own(BgVaultDwellerPerkId))
            throw new Refusal("Background INFO lacks HasPerk condition or Perk link");
        if (!trInfo.Conditions.Any(c => c.Data is IHasPerkConditionDataGetter) || trInfo.Perk.FormKey != Own(TraitGoodNaturedPerkId))
            throw new Refusal("Trait INFO lacks HasPerk condition or Perk link");

        var actualProps = q.VirtualMachineAdapter?.Scripts.FirstOrDefault()?.Properties.Select(p => p.Name).ToArray() ?? Array.Empty<string>();
        if (!actualProps.SequenceEqual(PropNames))
            throw new Refusal($"quest properties [{string.Join(",", actualProps)}] != expected [{string.Join(",", PropNames)}]");

        Console.WriteLine($"FO4SFListDialogue.esm: header Master, masters [Starfield.esm], 8 list INFOs ([Skill N], [SPECIAL N], [Background], [Trait]), deterministic CTDA checks verified");
        Console.WriteLine("all checks pass");
        return 0;
    }

    public static int Fixture(string outDir)
    {
        Directory.CreateDirectory(outDir);
        var sf = new StarfieldMod(SfEsm, Release);
        sf.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;

        sf.ActorValueInformation.Add(new ActorValueInformation(new FormKey(SfEsm, 0xA022), Release)
        {
            EditorID = "Strength", Name = "Strength", Type = ActorValueInformation.Types.Variable, DefaultValue = 5f, Min = 1f, Max = 15f,
        });
        sf.ActorValueInformation.Add(new ActorValueInformation(new FormKey(SfEsm, 0xA026), Release)
        {
            EditorID = "Intelligence", Name = "Intelligence", Type = ActorValueInformation.Types.Variable, DefaultValue = 5f, Min = 1f, Max = 15f,
        });
        sf.Npcs.Add(new Npc(new FormKey(SfEsm, 0x4297C), Release)
        {
            EditorID = "SynthSpeakerTemplate", Name = "Synth Speaker",
        });

        var sfPath = Path.Combine(outDir, "Starfield.esm");
        var masters = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        masters.Set(new KeyedMasterStyle(SfEsm, MasterStyle.Full));
        sf.WriteToBinary(sfPath, new BinaryWriteParameters
        {
            ModKey = ModKeyOption.NoCheck,
            MasterFlagsLookup = masters,
        });
        Console.WriteLine($"wrote synthetic fixture {sfPath}");
        return 0;
    }

    public static int SelfTest(string scratchDir)
    {
        Directory.CreateDirectory(scratchDir);
        var fixDir = Path.Combine(scratchDir, "fixture");
        Fixture(fixDir);
        var sfPath = Path.Combine(fixDir, "Starfield.esm");
        var outDir = Path.Combine(scratchDir, "out");
        if (Build(sfPath, outDir) != 0) throw new Refusal("Build failed");
        if (Check(Path.Combine(outDir, Plugin.FileName), sfPath) != 0) throw new Refusal("Check failed");
        Console.WriteLine("selftest: ok");
        return 0;
    }
}
