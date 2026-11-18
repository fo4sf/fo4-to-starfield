// ListDialogue: silent-player list conversation writer & checker with [Skill N], [SPECIAL N], [Background], and [Trait]
// prefix tags and deterministic New Vegas-style CTDA checks (CF-7, docs/dialogue/list-skill-checks.md).
//
// Built beside PR #792's 4-option wheel (zero #792 files edited; zero Interface/DialogueMenu.swf replacement — Starfield's
// native DialogueMenu renders DialogueListData.aChoices directly for >4-option and prefix-tagged silent-player conversations).
//
// Writes FO4SFListDialogue.esm (masters [Starfield.esm, FO4SFCoreValues.esm, FO4SFProgression.esm]; adds records only,
// overrides none, zero duplicate EditorIDs with FO4SFCoreValues.esm or FO4SFProgression.esm):
//   Shared from FO4SFCoreValues.esm (via src/fo4sf/core/core_values.json):
//     0x810 AVIF FO4SF_Special_Strength
//     0x814 AVIF FO4SF_Special_Intelligence
//     0x828 AVIF FO4SF_Skill_Science
//     0x82A AVIF FO4SF_Skill_Speech
//     0x860 GLOB FO4SF_TestModeEnabled
//   Shared from FO4SFProgression.esm:
//     0x820 PERK FO4SF_BG_VaultDweller
//     0x836 PERK FO4SF_Trait_GoodNatured
//   Owned in FO4SFListDialogue.esm:
//     0x805 FACT FO4SF_ListSpeakerFaction    Allied with PlayerFaction (0x01C21C) so speaker stays calm
//     0x810 QUST FO4SF_ListDialogueQuest     StartGameEnabled quest; test conversation & CELL omitted under --no-test-cell
//     (Default test-cell mode additionally emits 0x806 FO4SF_ListSpeakerNpc, 0x807 FO4SF_ListTalkCell,
//      0x808..0x80A placed speaker/markers, 0x811 DLBR, 0x812..0x813 DIAL, and 0x820..0x828 INFOs.)
//
// usage:
//   ListDialogue build <Starfield.esm> <out dir> [--json <core_values.json>] [--no-test-cell]
//   ListDialogue check <plugin> <Starfield.esm> [--json <core_values.json>] [--no-test-cell]
//   ListDialogue fixture <out dir>
//   ListDialogue selftest <scratch dir>

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
        if (jsonIdx + 1 >= rest.Count) throw new ListDialogue.Refusal("--json needs a path");
        jsonPath = rest[jsonIdx + 1];
        rest.RemoveRange(jsonIdx, 2);
    }
    int ntcIdx = rest.IndexOf("--no-test-cell");
    if (ntcIdx >= 0)
    {
        noTestCell = true;
        rest.RemoveAt(ntcIdx);
    }

    var opts = new ListDialogue.BuildOptions(jsonPath ?? ListDialogue.DefaultJsonPath(), noTestCell);
    if (rest.Count == 3 && rest[0] == "build") return ListDialogue.Build(rest[1], rest[2], opts);
    if (rest.Count == 3 && rest[0] == "check") return ListDialogue.Check(rest[1], rest[2], opts);
    if (rest.Count == 2 && rest[0] == "fixture") return ListDialogue.Fixture(rest[1]);
    if (rest.Count == 2 && rest[0] == "selftest") return ListDialogue.SelfTest(rest[1]);
}
catch (ListDialogue.Refusal r)
{
    Console.Error.WriteLine("refused: " + r.Message);
    return 1;
}

Console.Error.WriteLine("usage: ListDialogue build <Starfield.esm> <out dir> [--json <path>] [--no-test-cell] | " +
                        "check <plugin> <Starfield.esm> [--json <path>] [--no-test-cell] | fixture <out dir> | selftest <scratch dir>");
return 2;

public static class ListDialogue
{
    public class Refusal(string m) : Exception(m);
    public record BuildOptions(string JsonPath, bool NoTestCell = false);

    const StarfieldRelease Release = StarfieldRelease.Starfield;
    static readonly ModKey SfEsm = ModKey.FromFileName("Starfield.esm");
    static readonly ModKey CoreValuesEsm = ModKey.FromFileName("FO4SFCoreValues.esm");
    static readonly ModKey ProgressionEsm = ModKey.FromFileName("FO4SFProgression.esm");
    public static readonly ModKey Plugin = ModKey.FromFileName("FO4SFListDialogue.esm");

    static readonly ModKey[] ExpectedMasters = { SfEsm, CoreValuesEsm, ProgressionEsm };

    // Vanilla Starfield.esm references (proven in TestCell and Mission)
    public const uint PlayerRefId = 0x000014;
    public const uint PlayerFactionId = 0x01C21C;
    public const uint FloorStaticId = 0x050776;
    public const uint OmniLightId = 0x03D38C;
    public const uint CocMarkerId = 0x000032;
    public const uint XMarkerId = 0x00003B;
    public const uint LightingTemplateId = 0x006658;
    public const uint ImageSpaceId = 0x122393;

    // Shared FO4SFProgression.esm Perk FormIDs
    public const uint ProgBgVaultDwellerPerkId = 0x820;
    public const uint ProgTraitGoodNaturedPerkId = 0x836;

    // Local deterministic FormIDs in FO4SFListDialogue.esm
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
    public const uint TopSceneId = 0x814;

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
    public const uint FirstChoiceTopicId = 0x840;
    public const uint FirstReplyTopicId = 0x850;
    public const uint FirstReplyInfoId = 0x860;
    public const uint NextId = 0x870;
    public const uint NextIdNoTestCell = 0x811;

    // EditorIDs
    public const string SpeakerFactionEdid = "FO4SF_ListSpeakerFaction";
    public const string SpeakerNpcEdid = "FO4SF_ListSpeakerNpc";
    public const string TalkCellEdid = "FO4SF_ListTalkCell";
    public const string QuestEdid = "FO4SF_ListDialogueQuest";
    public const string ScriptName = "FO4SF_ListDialogueQuest";

    public static readonly ushort[] Stages = { 10, 15, 20, 21, 22, 30, 31, 40, 50, 60, 70 };

    // Pinned Quest VMAD property order (held equal with scripts/dialogue/FO4SF_ListDialogueQuest.psc)
    public static readonly string[] PropNames =
    {
        "SpeechAV",
        "ScienceAV",
        "StrengthAV",
        "IntelligenceAV",
        "BgVaultDwellerPerk",
        "TraitGoodNaturedPerk",
        "TestModeGlobal",
        "SpeakerRef",
        "ArrivalRef"
    };

    public static readonly string[] PlayerOnlyPropNames =
    {
        "SpeechAV",
        "ScienceAV",
        "StrengthAV",
        "IntelligenceAV",
        "BgVaultDwellerPerk",
        "TraitGoodNaturedPerk",
        "TestModeGlobal"
    };

    public record ChoiceSpec(
        uint InfoId, string Edid, string Prompt, string NpcReply, short EndStage,
        string CheckKind, FormKey TargetKey, CompareOperator Op, float Threshold, bool Goodbye = false);

    static FormKey Own(uint id) => new(Plugin, id);
    static FormKey Sf(uint id) => new(SfEsm, id);
    static FormKey Prog(uint id) => new(ProgressionEsm, id);

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

    static Cache<IModMasterStyledGetter, ModKey> MasterStyles()
    {
        var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        styles.Set(new KeyedMasterStyle(SfEsm, MasterStyle.Full));
        styles.Set(new KeyedMasterStyle(CoreValuesEsm, MasterStyle.Full));
        styles.Set(new KeyedMasterStyle(ProgressionEsm, MasterStyle.Full));
        styles.Set(new KeyedMasterStyle(Plugin, MasterStyle.Full));
        return styles;
    }

    static IStarfieldModDisposableGetter OpenMod(string path) =>
        StarfieldMod.CreateFromBinaryOverlay(path, Release, new BinaryReadParameters { MasterFlagsLookup = MasterStyles() });

    static INpcGetter PickSpeakerTemplate(IStarfieldModGetter sf)
    {
        // G4 fix: never pick MiniBotARace / RobotMiniBotA (no AllowDefaultDialog); use clean HumanRace + AllowDefaultDialog templates
        var preferred = new[] { "UC_NA_PapaKatz", "MQ101_MinerMale02", "MQ101_MinerMale03", "SynthSpeakerTemplate" };
        foreach (var ed in preferred)
        {
            var hit = sf.Npcs.FirstOrDefault(n => string.Equals(n.EditorID, ed, StringComparison.OrdinalIgnoreCase));
            if (hit != null) return hit;
        }
        var humanRace = sf.Races.FirstOrDefault(r => string.Equals(r.EditorID, "HumanRace", StringComparison.OrdinalIgnoreCase));
        if (humanRace != null)
        {
            foreach (var n in sf.Npcs)
            {
                if (n.Race.FormKey != humanRace.FormKey || string.IsNullOrEmpty(n.EditorID)) continue;
                if (n.TemplateActors != null && !n.TemplateActors.TraitTemplate.IsNull) continue;
                if (sf.VoiceTypes.TryGetValue(n.Voice.FormKey, out var vt) && vt.Flags.HasFlag(VoiceType.Flag.AllowDefaultDialog))
                    return n;
            }
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
            mod.WriteToBinary(tmpPath, new BinaryWriteParameters
            {
                ModKey = ModKeyOption.NoCheck,
                MastersListOrdering = new MastersListOrderingByLoadOrder(ExpectedMasters),
                MasterFlagsLookup = MasterStyles(),
            });
            File.Move(tmpPath, finalPath, overwrite: true);
        }
        finally
        {
            if (Directory.Exists(tmpDir)) Directory.Delete(tmpDir, recursive: true);
        }
    }

    public static int Build(string sfPath, string outDir, BuildOptions? opts = null)
    {
        opts ??= new BuildOptions(DefaultJsonPath(), false);
        var core = LoadCoreValues(opts.JsonPath);
        var speechAvKey = RequireCore(core, "FO4SF_Skill_Speech");
        var scienceAvKey = RequireCore(core, "FO4SF_Skill_Science");
        var strengthAvKey = RequireCore(core, "FO4SF_Special_Strength");
        var intelAvKey = RequireCore(core, "FO4SF_Special_Intelligence");
        var testModeKey = RequireCore(core, "FO4SF_TestModeEnabled");
        var bgPerkKey = Prog(ProgBgVaultDwellerPerkId);
        var traitPerkKey = Prog(ProgTraitGoodNaturedPerkId);

        using var sf = OpenMod(sfPath);

        var mod = new StarfieldMod(Plugin, Release);
        mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        mod.ModHeader.Author = "fo4-to-starfield ListDialogue";

        // 1. Allied Speaker Faction (references Starfield.esm PlayerFaction)
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

        // 2. Quest FO4SF_ListDialogueQuest
        var quest = new Quest(Own(QuestId), Release)
        {
            EditorID = QuestEdid, Name = "FO4SF Silent-Player List Dialogue",
            FormVersion = 581, Version2 = 12,
            Data = new QuestData
            {
                Flags = Quest.Flag.StartGameEnabled | Quest.Flag.StartsEnabled | Quest.Flag.AllowRepeatedStages |
                        Quest.Flag.HasDialogueData | (Quest.Flag)0x10000,
                Priority = 55,
            },
        };
        foreach (var st in Stages) quest.Stages.Add(new QuestStage { Index = st });

        FormKey Core(string edid) => RequireCore(core, edid);
        var propMap = new Dictionary<string, FormKey>
        {
            ["SpeechAV"] = Core("FO4SF_Skill_Speech"),
            ["ScienceAV"] = Core("FO4SF_Skill_Science"),
            ["StrengthAV"] = Core("FO4SF_Special_Strength"),
            ["IntelligenceAV"] = Core("FO4SF_Special_Intelligence"),
            ["BgVaultDwellerPerk"] = bgPerkKey,
            ["TraitGoodNaturedPerk"] = traitPerkKey,
            ["TestModeGlobal"] = Core("FO4SF_TestModeEnabled"),
        };

        if (!opts.NoTestCell)
        {
            var npcTpl = PickSpeakerTemplate(sf);
            Console.WriteLine($"templates: NPC_ {npcTpl.EditorID} {npcTpl.FormKey}");

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

            quest.Aliases ??= new ExtendedList<AQuestAlias>();
            quest.Aliases.Add(new QuestReferenceAlias
            {
                ID = 0,
                Name = "Speaker",
                Flags = QuestReferenceAlias.Flag.AllowDisabled | QuestReferenceAlias.Flag.AllowReserved | QuestReferenceAlias.Flag.UsesStoredText,
                UniqueActor = new FormLinkNullable<INpcGetter>(speakerNpc.FormKey),
            });

            var greetTopic = new DialogTopic(Own(GreetingTopicId), Release)
            {
                EditorID = "FO4SF_ListGreetingTopic",
                Quest = new FormLink<IQuestGetter>(quest.FormKey),
                Priority = 55f,
                Category = DialogTopic.CategoryEnum.Scene,
                Subtype = DialogTopic.SubtypeEnum.CustomScene,
                SubtypeName = DialogTopic.SubtypeNameEnum.CustomScene,
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

            var choiceSpecs = new[]
            {
                new ChoiceSpec(InfoSpeechPassId, "FO4SF_ListInfo_Speech50_Pass",
                    "[Speech 50] Present the convoy clearance protocol.",
                    "Clearance code verified. Gate channel opened.",
                    20, "skill", speechAvKey, CompareOperator.GreaterThanOrEqualTo, 50f),
                new ChoiceSpec(InfoSpeechFailId, "FO4SF_ListInfo_Speech50_Fail",
                    "[Speech 50] Ask them to wave the clearance check anyway.",
                    "Negative. Unverified requests are denied.",
                    21, "skill", speechAvKey, CompareOperator.LessThan, 50f),
                new ChoiceSpec(InfoSciencePassId, "FO4SF_ListInfo_Science40_Pass",
                    "[Science 40] Re-calibrate the relay carrier harmonic.",
                    "Harmonic lock achieved. Telemetry stabilized.",
                    22, "skill", scienceAvKey, CompareOperator.GreaterThanOrEqualTo, 40f),
                new ChoiceSpec(InfoStrengthPassId, "FO4SF_ListInfo_Strength7_Pass",
                    "[Strength 7] Force the manual bulkhead latch.",
                    "The manual latch gives way cleanly.",
                    30, "special", strengthAvKey, CompareOperator.GreaterThanOrEqualTo, 7f),
                new ChoiceSpec(InfoStrengthFailId, "FO4SF_ListInfo_Strength7_Fail",
                    "[Strength 7] Strain against the manual bulkhead latch.",
                    "The latch does not budge.",
                    31, "special", strengthAvKey, CompareOperator.LessThan, 7f),
                new ChoiceSpec(InfoBackgroundId, "FO4SF_ListInfo_BG_VaultDweller",
                    "[Vault Dweller] Cite sealed-shelter atmospheric maintenance.",
                    "Standard shelter manifold acknowledged.",
                    40, "background", bgPerkKey, CompareOperator.EqualTo, 1f),
                new ChoiceSpec(InfoTraitId, "FO4SF_ListInfo_Trait_GoodNatured",
                    "[Good Natured] Share field medical supplies first.",
                    "Supplies logged. Your cooperation is noted.",
                    50, "trait", traitPerkKey, CompareOperator.EqualTo, 1f),
                new ChoiceSpec(InfoExitId, "FO4SF_ListInfo_Exit",
                    "Step away from the relay station.",
                    "Standing by.",
                    60, "plain", FormKey.Null, CompareOperator.EqualTo, 0f, Goodbye: true),
            };

            // G4 fix: Starfield opens silent-player DialogueMenu via a Top-Level Scene (0x2000 | DisableDialogueCamera | Interruptable | ShowAllText = 0x2814)
            // with Phase 0 DialogueSceneAction greeting and Phase 1 PlayerDialogueSceneAction (8 PlayerChoice -> NpcResponse pairs).
            var topScene = new Scene(Own(TopSceneId), Release)
            {
                EditorID = "FO4SF_ListTopScene",
                Quest = new FormLinkNullable<IQuestGetter>(quest.FormKey),
                Flags = (Scene.Flag)0x2814,
                Index = 0,
                LastActionIndex = 2,
                SCPI = new byte[] { 0x37, 0x00 },
                VNAM = new byte[] { 3, 0, 0, 0, 3, 0, 0, 0, 3, 0, 0, 0, 3, 0, 0, 0, 3, 0, 0, 0 },
            };
            topScene.Conditions.Add(SpeakerIs(speakerNpc.FormKey));
            topScene.Actors.Add(new SceneActor
            {
                ID = 0,
                BehaviorFlags = (SceneActor.BehaviorFlag)0x10A,
                Flags = SceneActor.Flag.NoCommandState,
            });
            topScene.Actors.Add(new SceneActor
            {
                ID = unchecked((uint)-2),
                BehaviorFlags = (SceneActor.BehaviorFlag)0x10A,
                Flags = SceneActor.Flag.NoCommandState,
            });
            topScene.Phases.Add(new ScenePhase { Name = "", EditorWidth = 500 });
            topScene.Phases.Add(new ScenePhase { Name = "TOPLEVELNEST", EditorWidth = 500 });

            topScene.Actions ??= new ExtendedList<ASceneAction>();
            topScene.Actions.Add(new DialogueSceneAction
            {
                Name = "",
                Index = 1,
                AliasID = 0,
                StartPhase = 0,
                EndPhase = 0,
                Topic = new FormLinkNullable<IDialogTopicGetter>(greetTopic.FormKey),
                LoopingMin = 1f,
                LoopingMax = 10f,
            });

            var playerAct = new PlayerDialogueSceneAction
            {
                Name = "",
                Index = 2,
                AliasID = 0,
                DialogueTargetActor = 0,
                StartPhase = 1,
                EndPhase = 1,
            };

            for (uint idx = 0; idx < (uint)choiceSpecs.Length; idx++)
            {
                var cs = choiceSpecs[idx];
                var pcTopic = new DialogTopic(Own(FirstChoiceTopicId + idx), Release)
                {
                    EditorID = $"FO4SF_ListChoiceTopic_{idx}",
                    Quest = new FormLink<IQuestGetter>(quest.FormKey),
                    Priority = 55f,
                    Category = DialogTopic.CategoryEnum.Scene,
                    Subtype = DialogTopic.SubtypeEnum.CustomScene,
                    SubtypeName = DialogTopic.SubtypeNameEnum.CustomScene,
                };
                var pcInfo = new DialogResponses(Own(cs.InfoId), Release)
                {
                    EditorID = cs.Edid,
                    Prompt = cs.Prompt,
                };
                pcInfo.Responses.Add(new DialogResponse { ResponseText = cs.Prompt, WEMFile = 0 });
                if (cs.CheckKind is "skill" or "special")
                {
                    pcInfo.Conditions.Add(PlayerValueCheck(cs.TargetKey, cs.Op, cs.Threshold));
                }
                else if (cs.CheckKind is "background" or "trait")
                {
                    pcInfo.Conditions.Add(PlayerHasPerkCheck(cs.TargetKey));
                    pcInfo.Perk = new FormLinkNullable<IPerkGetter>(cs.TargetKey);
                }
                pcTopic.Responses.Add(pcInfo);
                (pcTopic.TopicInfoList ??= new()).Add(new FormLink<IDialogResponsesGetter>(pcInfo.FormKey));
                quest.DialogTopics.Add(pcTopic);

                var npcTopic = new DialogTopic(Own(FirstReplyTopicId + idx), Release)
                {
                    EditorID = $"FO4SF_ListReplyTopic_{idx}",
                    Quest = new FormLink<IQuestGetter>(quest.FormKey),
                    Priority = 55f,
                    Category = DialogTopic.CategoryEnum.Scene,
                    Subtype = DialogTopic.SubtypeEnum.CustomScene,
                    SubtypeName = DialogTopic.SubtypeNameEnum.CustomScene,
                };
                var npcInfo = new DialogResponses(Own(FirstReplyInfoId + idx), Release)
                {
                    EditorID = $"{cs.Edid}_Reply",
                    SetParentQuestStage = new DialogSetParentQuestStage { OnBegin = -1, OnEnd = cs.EndStage },
                };
                if (cs.Goodbye)
                {
                    npcInfo.Flags = new DialogResponseFlags { Flags = 1 };
                }
                else
                {
                    npcInfo.StartScene = new FormLinkNullable<ISceneGetter>(topScene.FormKey);
                    npcInfo.StartScenePhase = "TOPLEVELNEST";
                }
                npcInfo.Responses.Add(new DialogResponse { ResponseText = cs.NpcReply, WEMFile = 0 });
                npcInfo.Conditions.Add(SpeakerIs(speakerNpc.FormKey));
                npcTopic.Responses.Add(npcInfo);
                (npcTopic.TopicInfoList ??= new()).Add(new FormLink<IDialogResponsesGetter>(npcInfo.FormKey));
                quest.DialogTopics.Add(npcTopic);

                playerAct.DialogueList.Add(new PlayerDialogueSceneActionItem
                {
                    PlayerChoice = new FormLinkNullable<IDialogTopicGetter>(pcTopic.FormKey),
                    NpcResponse = new FormLink<IDialogTopicGetter>(npcTopic.FormKey),
                });
            }

            topScene.Actions.Add(playerAct);
            quest.Scenes.Add(topScene);

            propMap["SpeakerRef"] = speakerRef.FormKey;
            propMap["ArrivalRef"] = arrivalRef.FormKey;
        }

        var se = new ScriptEntry { Name = ScriptName, Flags = ScriptEntry.Flag.Local };
        var activeProps = opts.NoTestCell ? PlayerOnlyPropNames : PropNames;
        foreach (var pn in activeProps) se.Properties.Add(ObjProp(pn, propMap[pn]));

        quest.VirtualMachineAdapter = new QuestAdapter
        {
            Version = 6, ObjectFormat = 2, ExtraBindDataVersion = 3,
            Script = new ScriptEntry { Name = "", Flags = ScriptEntry.Flag.Local },
        };
        quest.VirtualMachineAdapter.Scripts.Add(se);
        mod.Quests.Add(quest);

        mod.ModHeader.Stats.NextFormID = opts.NoTestCell ? NextIdNoTestCell : NextId;
        foreach (var mk in ExpectedMasters)
        {
            if (!mod.ModHeader.MasterReferences.Any(m => m.Master == mk))
                mod.ModHeader.MasterReferences.Add(new MasterReference { Master = mk });
        }

        WriteMod(mod, outDir);
        var outPath = Path.Combine(outDir, Plugin.FileName);
        Console.WriteLine($"wrote {outPath} ({new FileInfo(outPath).Length:N0} bytes): " +
                          $"0 AVIF, 0 PERK, 1 FACT, {mod.Npcs.Count} NPC_, {(opts.NoTestCell ? 0 : 1)} CELL, " +
                          $"1 QUST ({quest.Scenes.Count} SCEN, {quest.DialogTopics.Count} DIAL, {activeProps.Length} properties)");
        return 0;
    }

    public static int Check(string pluginPath, string sfPath, BuildOptions? opts = null)
    {
        opts ??= new BuildOptions(DefaultJsonPath(), false);
        var core = LoadCoreValues(opts.JsonPath);
        var speechAvKey = RequireCore(core, "FO4SF_Skill_Speech");
        var scienceAvKey = RequireCore(core, "FO4SF_Skill_Science");
        var strengthAvKey = RequireCore(core, "FO4SF_Special_Strength");
        var intelAvKey = RequireCore(core, "FO4SF_Special_Intelligence");
        var testModeKey = RequireCore(core, "FO4SF_TestModeEnabled");
        var bgPerkKey = Prog(ProgBgVaultDwellerPerkId);
        var traitPerkKey = Prog(ProgTraitGoodNaturedPerkId);

        if (!File.Exists(pluginPath)) throw new Refusal($"missing plugin: {pluginPath}");
        using var sf = OpenMod(sfPath);
        using var mod = OpenMod(pluginPath);

        if (!mod.ModHeader.Flags.HasFlag(StarfieldModHeader.HeaderFlag.Master))
            throw new Refusal("plugin lacks Master header flag");
        var masters = mod.ModHeader.MasterReferences.Select(m => m.Master).ToList();
        if (!masters.SequenceEqual(ExpectedMasters))
            throw new Refusal($"expected masters [{string.Join(", ", ExpectedMasters)}], got [{string.Join(", ", masters)}]");

        var forbiddenEdids = new HashSet<string>(core.Keys, StringComparer.OrdinalIgnoreCase)
        {
            "FO4SF_BG_VaultDweller",
            "FO4SF_Trait_GoodNatured",
        };
        foreach (var rec in mod.EnumerateMajorRecords())
        {
            if (rec.FormKey.ModKey != Plugin)
                throw new Refusal($"plugin overrides foreign record {rec.FormKey} ({rec.EditorID})");
            if (!string.IsNullOrEmpty(rec.EditorID) && forbiddenEdids.Contains(rec.EditorID))
                throw new Refusal($"duplicate shared EditorID {rec.EditorID} in {Plugin}");
        }

        if (mod.ActorValueInformation.Count != 0)
            throw new Refusal($"expected 0 local AVIF (all shared in FO4SFCoreValues.esm), found {mod.ActorValueInformation.Count}");
        if (mod.Perks.Count != 0)
            throw new Refusal($"expected 0 local PERK (all shared in FO4SFProgression.esm), found {mod.Perks.Count}");
        if (mod.Quests.Count != 1)
            throw new Refusal($"expected 1 QUST, found {mod.Quests.Count}");

        var q = mod.Quests.First();
        var script = q.VirtualMachineAdapter?.Scripts.FirstOrDefault() ?? throw new Refusal("missing FO4SF_ListDialogueQuest VMAD script");
        var actualProps = script.Properties.Select(p => p.Name).ToArray();
        var wantProps = opts.NoTestCell ? PlayerOnlyPropNames : PropNames;
        if (!actualProps.SequenceEqual(wantProps))
            throw new Refusal($"quest properties [{string.Join(",", actualProps)}] != expected [{string.Join(",", wantProps)}]");

        FormKey PropObj(string name) =>
            (script.Properties.FirstOrDefault(p => p.Name == name) as IScriptObjectPropertyGetter)?.Object.FormKey ?? FormKey.Null;

        if (PropObj("SpeechAV") != speechAvKey) throw new Refusal($"SpeechAV {PropObj("SpeechAV")} != {speechAvKey}");
        if (PropObj("ScienceAV") != scienceAvKey) throw new Refusal($"ScienceAV {PropObj("ScienceAV")} != {scienceAvKey}");
        if (PropObj("StrengthAV") != strengthAvKey) throw new Refusal($"StrengthAV {PropObj("StrengthAV")} != {strengthAvKey}");
        if (PropObj("IntelligenceAV") != intelAvKey) throw new Refusal($"IntelligenceAV {PropObj("IntelligenceAV")} != {intelAvKey}");
        if (PropObj("BgVaultDwellerPerk") != bgPerkKey) throw new Refusal($"BgVaultDwellerPerk {PropObj("BgVaultDwellerPerk")} != {bgPerkKey}");
        if (PropObj("TraitGoodNaturedPerk") != traitPerkKey) throw new Refusal($"TraitGoodNaturedPerk {PropObj("TraitGoodNaturedPerk")} != {traitPerkKey}");
        if (PropObj("TestModeGlobal") != testModeKey) throw new Refusal($"TestModeGlobal {PropObj("TestModeGlobal")} != {testModeKey}");

        var cells = mod.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells).ToList();
        if (opts.NoTestCell)
        {
            if (cells.Count != 0) throw new Refusal($"expected 0 CELL under --no-test-cell, found {cells.Count}");
            if (mod.Npcs.Count != 0) throw new Refusal($"expected 0 NPC_ under --no-test-cell, found {mod.Npcs.Count}");
            if (q.Scenes.Count != 0 || q.DialogTopics.Count != 0)
                throw new Refusal("expected 0 test SCEN/DIAL under --no-test-cell");
        }
        else
        {
            if (cells.Count != 1 || cells[0].FormKey != Own(TalkCellId))
                throw new Refusal($"expected 1 CELL {TalkCellEdid}, found {cells.Count}");
            if (mod.Npcs.Count != 1 || mod.Npcs.First().FormKey != Own(SpeakerNpcId))
                throw new Refusal($"expected 1 NPC_ {SpeakerNpcEdid}, found {mod.Npcs.Count}");

            var spk = mod.Npcs.First();
            if (sf.Races.TryGetValue(spk.Race.FormKey, out var spkRace) &&
                string.Equals(spkRace.EditorID, "MiniBotARace", StringComparison.OrdinalIgnoreCase))
                throw new Refusal("speaker NPC uses MiniBotARace (cannot open player DialogueMenu)");
            if (sf.VoiceTypes.TryGetValue(spk.Voice.FormKey, out var spkVoice) &&
                !spkVoice.Flags.HasFlag(VoiceType.Flag.AllowDefaultDialog))
                throw new Refusal($"speaker VoiceType {spkVoice.EditorID} lacks AllowDefaultDialog");

            if (q.Aliases == null || !q.Aliases.OfType<IQuestReferenceAliasGetter>().Any(a => a.ID == 0 && a.UniqueActor.FormKey == Own(SpeakerNpcId)))
                throw new Refusal("quest missing ID=0 Speaker QuestReferenceAlias targeting FO4SF_ListSpeakerNpc");
            if (q.Scenes.Count != 1 || q.Scenes[0].FormKey != Own(TopSceneId))
                throw new Refusal($"expected 1 SCEN {Own(TopSceneId)}, found {q.Scenes.Count}");
            var topScene = q.Scenes[0];
            if (((uint)(topScene.Flags ?? 0) & 0x2000u) == 0)
                throw new Refusal("FO4SF_ListTopScene lacks Starfield top-level player-activate scene bit (0x2000)");
            var pda = topScene.Actions?.OfType<IPlayerDialogueSceneActionGetter>().FirstOrDefault()
                      ?? throw new Refusal("FO4SF_ListTopScene missing PlayerDialogueSceneAction");
            if (pda.DialogueList.Count != 8)
                throw new Refusal($"expected 8 silent-player list choices in PlayerDialogueSceneAction (>4), found {pda.DialogueList.Count}");
            if (q.DialogTopics.Count != 17)
                throw new Refusal($"expected 17 DIAL (1 greeting + 8 choice + 8 reply), found {q.DialogTopics.Count}");

            var choiceInfos = pda.DialogueList
                .Select(item => q.DialogTopics.First(t => t.FormKey == item.PlayerChoice.FormKey).Responses.First())
                .ToList();
            var prompts = choiceInfos.Select(r => r.Responses.FirstOrDefault()?.ResponseText.String ?? "").ToList();
            foreach (var prefix in new[] { "[Speech 50]", "[Science 40]", "[Strength 7]", "[Vault Dweller]", "[Good Natured]" })
            {
                if (!prompts.Any(p => p.StartsWith(prefix, StringComparison.Ordinal)))
                    throw new Refusal($"missing required prefix tag {prefix} in PlayerChoice INFO responses");
            }

            bool HasValCond(IDialogResponsesGetter info, FormKey avKey, CompareOperator op, float val) =>
                info.Conditions.Any(c => c is IConditionFloatGetter cf &&
                                         cf.CompareOperator == op &&
                                         Math.Abs(cf.ComparisonValue - val) < 0.01f &&
                                         c.Data is IGetValueConditionDataGetter gv &&
                                         gv.FirstParameter.FormKey == avKey);

            var speechPass = choiceInfos.First(r => r.FormKey == Own(InfoSpeechPassId));
            var speechFail = choiceInfos.First(r => r.FormKey == Own(InfoSpeechFailId));
            var sciencePass = choiceInfos.First(r => r.FormKey == Own(InfoSciencePassId));
            var strPass = choiceInfos.First(r => r.FormKey == Own(InfoStrengthPassId));
            var strFail = choiceInfos.First(r => r.FormKey == Own(InfoStrengthFailId));
            if (!HasValCond(speechPass, speechAvKey, CompareOperator.GreaterThanOrEqualTo, 50f))
                throw new Refusal("Speech 50 PASS INFO lacks FO4SFCoreValues.esm GetValue >= 50 condition");
            if (!HasValCond(speechFail, speechAvKey, CompareOperator.LessThan, 50f))
                throw new Refusal("Speech 50 FAIL INFO lacks FO4SFCoreValues.esm GetValue < 50 condition");
            if (!HasValCond(sciencePass, scienceAvKey, CompareOperator.GreaterThanOrEqualTo, 40f))
                throw new Refusal("Science 40 PASS INFO lacks FO4SFCoreValues.esm GetValue >= 40 condition");
            if (!HasValCond(strPass, strengthAvKey, CompareOperator.GreaterThanOrEqualTo, 7f))
                throw new Refusal("Strength 7 PASS INFO lacks FO4SFCoreValues.esm GetValue >= 7 condition");
            if (!HasValCond(strFail, strengthAvKey, CompareOperator.LessThan, 7f))
                throw new Refusal("Strength 7 FAIL INFO lacks FO4SFCoreValues.esm GetValue < 7 condition");

            var bgInfo = choiceInfos.First(r => r.FormKey == Own(InfoBackgroundId));
            var trInfo = choiceInfos.First(r => r.FormKey == Own(InfoTraitId));
            if (!bgInfo.Conditions.Any(c => c.Data is IHasPerkConditionDataGetter hp && hp.FirstParameter.Link.FormKey == bgPerkKey) || bgInfo.Perk.FormKey != bgPerkKey)
                throw new Refusal("Background INFO lacks FO4SFProgression.esm HasPerk condition or Perk link");
            if (!trInfo.Conditions.Any(c => c.Data is IHasPerkConditionDataGetter hp && hp.FirstParameter.Link.FormKey == traitPerkKey) || trInfo.Perk.FormKey != traitPerkKey)
                throw new Refusal("Trait INFO lacks FO4SFProgression.esm HasPerk condition or Perk link");

            var replyStages = pda.DialogueList
                .Select(item => q.DialogTopics.First(t => t.FormKey == item.NpcResponse.FormKey).Responses.First().SetParentQuestStage?.OnEnd ?? -1)
                .ToArray();
            var wantStages = new short[] { 20, 21, 22, 30, 31, 40, 50, 60 };
            if (!replyStages.SequenceEqual(wantStages))
                throw new Refusal($"NpcResponse OnEnd stages [{string.Join(",", replyStages)}] != expected [{string.Join(",", wantStages)}]");
        }

        Console.WriteLine($"FO4SFListDialogue.esm: header Master, masters [{string.Join(", ", ExpectedMasters)}], no_test_cell={opts.NoTestCell}, all checks pass");
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
        var humanRace = new Race(new FormKey(SfEsm, 0x347D), Release) { EditorID = "HumanRace" };
        sf.Races.Add(humanRace);
        var humanVoice = new VoiceType(new FormKey(SfEsm, 0x12AE7), Release)
        {
            EditorID = "GenericMaleEvenToned",
            Flags = VoiceType.Flag.AllowDefaultDialog,
        };
        sf.VoiceTypes.Add(humanVoice);
        sf.Npcs.Add(new Npc(new FormKey(SfEsm, 0x4297C), Release)
        {
            EditorID = "SynthSpeakerTemplate",
            Name = "Synth Speaker",
            Race = new FormLink<IRaceGetter>(humanRace.FormKey),
            Voice = new FormLinkNullable<IVoiceTypeGetter>(humanVoice.FormKey),
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
        if (Directory.Exists(scratchDir)) Directory.Delete(scratchDir, recursive: true);
        Directory.CreateDirectory(scratchDir);
        var fixDir = Path.Combine(scratchDir, "fixture");
        Fixture(fixDir);
        var sfPath = Path.Combine(fixDir, "Starfield.esm");
        var jsonPath = DefaultJsonPath();

        // 1. Default build (with test cell & 8-row conversation) + determinism check
        var defOpts = new BuildOptions(jsonPath, NoTestCell: false);
        var outDir = Path.Combine(scratchDir, "out");
        var outDir2 = Path.Combine(scratchDir, "out2");
        if (Build(sfPath, outDir, defOpts) != 0) throw new Refusal("Build failed");
        if (Build(sfPath, outDir2, defOpts) != 0) throw new Refusal("Build 2 failed");
        var defPlugin = Path.Combine(outDir, Plugin.FileName);
        if (!File.ReadAllBytes(defPlugin).SequenceEqual(File.ReadAllBytes(Path.Combine(outDir2, Plugin.FileName))))
            throw new Refusal("default FO4SFListDialogue.esm build is not byte-identical");
        if (Check(defPlugin, sfPath, defOpts) != 0) throw new Refusal("Check failed");

        // 2. --no-test-cell build (player profile: zero CELL / NPC_ / test conversation)
        var playerOpts = new BuildOptions(jsonPath, NoTestCell: true);
        var outPlayer = Path.Combine(scratchDir, "out_player");
        if (Build(sfPath, outPlayer, playerOpts) != 0) throw new Refusal("Build --no-test-cell failed");
        var playerPlugin = Path.Combine(outPlayer, Plugin.FileName);
        if (Check(playerPlugin, sfPath, playerOpts) != 0) throw new Refusal("Check --no-test-cell failed");

        // 3. Cross-mode rejection checks
        bool rejected = false;
        try { Check(defPlugin, sfPath, playerOpts); }
        catch (Refusal) { rejected = true; }
        if (!rejected) throw new Refusal("Check --no-test-cell failed to reject plugin containing test cell");

        rejected = false;
        try { Check(playerPlugin, sfPath, defOpts); }
        catch (Refusal) { rejected = true; }
        if (!rejected) throw new Refusal("default Check failed to reject plugin missing test cell");

        Console.WriteLine("selftest: ok");
        return 0;
    }
}
