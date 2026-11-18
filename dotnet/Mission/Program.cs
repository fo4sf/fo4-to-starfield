// Mission: cut-down "When Freedom Calls" (FO4SF_Min00 0x800), FO4SF_CodsworthKeeper (0x814), FO4SF_COMPreston (0x815),
// FO4SF_Codsworth01 (0x816, MQ102-lite 4-choice Sanctuary conversation), and FO4SF_Sanctuary01 (0x817, Sanctuary
// workbench 0250FE -> FO4TerrainCore.esm 0x005C50 objective) in FO4SFMission.esm.
//
//   points <Fallout4.esm> <out points.json> [--radius 120] [--max 8] [--strings-dir <dir>] [--hello-infos <hex,hex...>]
//   write <Starfield.esm> <FO4TerrainCore.esm> <FO4ActorRaider.esm> <points.json> <out dir> [--plugin FO4SFMission.esm]
//         [--world FO4Core_Commonwealth] [--no-alias] [--codsworth-body OutpostRobotMiniBotA_Garden] [--no-codsworth]
//         [--codsworth-model <mesh under Meshes>] [--codsworth-voice <voice.json>] [--codsworth-mq-voice <mq_voice.json>]
//   check <plugin> <Starfield.esm> <FO4TerrainCore.esm> <FO4ActorRaider.esm> [--no-alias] [--no-codsworth]
//         [--codsworth-model <mesh>] [--codsworth-voice <voice.json>] [--codsworth-mq-voice <mq_voice.json>]
//   npcs <plugin.esm> <fo4 | sf> <regex>
//   quests <Starfield.esm> [faction regex]
//   infos <Starfield.esm> <regex | wem:hex,hex...>
//   selftest <scratch dir>
// Nothing is deployed and no game file is written. SelfTest uses synthetic masters and synthetic strings only.
using System.Globalization;
using System.Text.Json;
using Mutagen.Bethesda;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Assets;
using Mutagen.Bethesda.Starfield.Assets;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Cache;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Strings;
using Noggog;
using F4 = Mutagen.Bethesda.Fallout4;
using SF = Mutagen.Bethesda.Starfield;

if (args.Length == 0) return Mission.Usage();
try
{
    return args[0] switch
    {
        "points" when args.Length >= 3 => Mission.Points(args[1], args[2], Mission.Opt(args, "--radius", 120f),
                                                         (int)Mission.Opt(args, "--max", 8f),
                                                         Mission.ArgOrNull(args, "--strings-dir"),
                                                         Mission.ArgOrNull(args, "--hello-infos")),
        "write" when args.Length >= 6 => Mission.Write(args[1], args[2], args[3], args[4], args[5],
                                                       Mission.Arg(args, "--plugin", Mission.Plugin),
                                                       Mission.Arg(args, "--world", Mission.World), !args.Contains("--no-alias"),
                                                       args.Contains("--no-codsworth") ? null : Mission.Arg(args, "--codsworth-body", Mission.CodsworthBody),
                                                       Mission.ArgOrNull(args, "--codsworth-model"),
                                                       Mission.ArgOrNull(args, "--codsworth-voice"),
                                                       Mission.ArgOrNull(args, "--codsworth-mq-voice")),
        "check" when args.Length >= 5 => Mission.Check(args[1], args[2], args[3], args[4], !args.Contains("--no-alias"),
                                                       !args.Contains("--no-codsworth"),
                                                       Mission.ArgOrNull(args, "--codsworth-model"),
                                                       Mission.ArgOrNull(args, "--codsworth-voice"),
                                                       Mission.ArgOrNull(args, "--codsworth-mq-voice")),
        "npcs" when args.Length >= 4 => Mission.Npcs(args[1], args[2], args[3]),
        "quests" when args.Length >= 2 => Mission.Quests(args[1], args.Length >= 3 ? args[2] : "."),
        "infos" when args.Length >= 3 => Mission.Infos(args[1], args[2]),
        "selftest" when args.Length >= 2 => Mission.SelfTest(args[1]),
        _ => Mission.Usage(),
    };
}
catch (Mission.Refusal e)
{
    Console.Error.WriteLine("refused: " + e.Message);
    return 2;
}

static class Mission
{
    public const string Plugin = "FO4SFMission.esm", World = "FO4Core_Commonwealth";
    public const string QuestEdid = "FO4SF_Min00", ScriptName = "FO4SF_Min00Quest";
    public const string PrestonEdid = "FO4_PrestonGarvey", PrestonNpcEdid = "FO4_PrestonGarvey", PrestonRefEdid = "FO4SF_Min00_PrestonREF";
    public const uint QuestId = 0x800, PrestonNpcId = 0x801, PrestonRefId = 0x802, FirstRaiderRefId = 0x803;
    public const uint CalmProbeId = 0xF04801, RaiderId = 0xF04800;        // FO4ActorRaider.esm
    public const uint CreditsId = 0x00000F, XMarkerId = 0x00003B;          // Starfield.esm MISC Credits & STAT XMarker
    public const uint QuestTypeSideId = 0x047600; public const string QuestTypeSideEdid = "QuestTypeSideQuest";

    // Starfield.esm HumanRace + male NPC template + colonial/frontier outfit + Orion laser rifle placeholder for Preston (2g)
    public const uint SfHumanRaceId = 0x00347D, SfPapaKatzId = 0x01169C;
    public const uint SfPrestonOutfitId = 0x208E39, SfPrestonWeaponId = 0x2773C8, SfPrestonAmmoId = 0x00E8EC;
    public const string SfHumanRaceEdid = "HumanRace", SfPapaKatzEdid = "UC_NA_PapaKatz", SfPrestonVoiceEdid = "GenericMaleEvenToned";
    public const string SfPrestonOutfitEdid = "Outfit_FreestarRanger_Vest_with_Hat", SfPrestonWeaponEdid = "Orion", SfPrestonAmmoEdid = "AmmoLaser";

    // FO4TerrainCore.esm Sanctuary workbench (Fallout4.esm 0250FE -> base ACTI 0x0A2ECD, placed REFR 0x005C50)
    public const uint CoreBenchBaseId = 0x0A2ECD, CoreSanctuaryBenchRefId = 0x005C50;
    public const uint SanctuaryBenchFo4Ref = 0x0250FE;

    // Fallout4.esm read-only lookup IDs (used only by `points` at local build time)
    public const uint MuseumCell = 0x017DF7, Commonwealth = 0x00003C, PrestonFo4 = 0x019FD9, Min00 = 0x1A001C;
    public const uint Mq102Fo4 = 0x01CC2A, DialogueConcordFo4 = 0x0179F3, DialogueCodsworthPostWarFo4 = 0x01E64E;
    public const int PrestonAlias = 0, CodsworthAlias = 0, SanctuaryBenchAlias = 0;

    public const uint MinutemenFactionId = 0x81F, PlayerFactionId = 0x01C21C;
    public const string MinutemenFactionEdid = "FO4SF_MinutemenFaction", PlayerFactionEdid = "PlayerFaction";

    public const uint CodsworthFo4Ref = 0x01CA7D, CodsworthFo4Npc = 0x0179FF, CodsworthNpcId = 0x810, CodsworthRefId = 0x811;
    public const string CodsworthEdid = "FO4_Codsworth", CodsworthNpcEdid = "FO4_Codsworth", CodsworthRefEdid = "FO4SF_CodsworthREF";
    public const string CodsworthBody = "OutpostRobotMiniBotA_Garden";
    public const uint CodsworthArmaId = 0x812, CodsworthSkinId = 0x813, MiniBotArmaId = 0x081886, MiniBotSkinId = 0x3FFD3A;
    public const string CodsworthArmaEdid = "FO4_AA_Codsworth", CodsworthSkinEdid = "FO4_Skin_Codsworth",
                        MiniBotArmaEdid = "AA_MiniBotA_Gardening", MiniBotSkinEdid = "Skin_MiniBotA_Gardening";

    // Quests 0x814..0x817 & Codsworth dialogue-capable Race/VoiceType 0x818..0x819
    public const uint KeeperQuestId = 0x814;
    public const string KeeperEdid = "FO4SF_CodsworthKeeper", KeeperQuestEdid = "FO4SF_CodsworthKeeper";
    public const uint ComQuestId = 0x815;
    public const string ComQuestEdid = "FO4SF_COMPreston";
    public const int ComAlias = 0;
    public const string ComAliasName = "Preston";
    public const uint FollowPackageId = 0x0301C5;
    public const string FollowPackageEdid = "DefaultMaster_FollowPackage";
    public const uint RaiderCombatPackageId = 0x042240;
    public const string RaiderCombatPackageEdid = "DefaultCombatMasterPackage";
    public const uint RaiderSandboxPackageId = 0x089605;
    public const string RaiderSandboxPackageEdid = "DefaultSandboxCurrentLocation";

    public const uint CodsworthQuestId = 0x816, SanctuaryQuestId = 0x817;
    public const string CodsworthQuestEdid = "FO4SF_Codsworth01", CodsworthScriptName = "FO4SF_Codsworth01Quest";
    public const string SanctuaryQuestEdid = "FO4SF_Sanctuary01", SanctuaryScriptName = "FO4SF_Sanctuary01Quest";
    public const uint CodsworthRaceId = 0x818, CodsworthVoiceId = 0x819;
    public const string CodsworthRaceEdid = "FO4SF_CodsworthRace", CodsworthVoiceEdid = "FO4SF_CodsworthVoice";

    public const uint CodsworthDialId = 0x820, FirstCodsworthInfoId = 0x821;
    public const string CodsworthDialEdid = "FO4SF_CodsworthHellos";

    // Preston 3-exchange Scene & DIAL/INFO block (0x900..0x92A)
    public const uint PrestonTalkSceneId = 0x900, PrestonGreetTopicId = 0x901, PrestonGreetInfoId = 0x902;
    public const string PrestonTalkSceneEdid = "FO4SF_Min00_PrestonScene",
                        PrestonGreetTopicEdid = "FO4SF_Min00_PrestonGreetTopic",
                        PrestonGreetInfoEdid = "FO4SF_Min00_PrestonGreetInfo";
    public const uint FirstPrestonChoiceTopicId = 0x910, FirstPrestonChoiceInfoId = 0x918;
    public const uint FirstPrestonReplyTopicId = 0x920, FirstPrestonReplyInfoId = 0x928;

    // Codsworth MQ102-lite 4-choice Scene & DIAL/INFO block (0x940..0x96B)
    public const uint CodsworthSceneId = 0x940, CodsworthGreetTopicId = 0x941, CodsworthGreetInfoId = 0x942;
    public const string CodsworthSceneEdid = "FO4SF_Codsworth01_Scene",
                        CodsworthGreetTopicEdid = "FO4SF_Codsworth01_GreetTopic",
                        CodsworthGreetInfoEdid = "FO4SF_Codsworth01_GreetInfo";
    public const uint FirstCodsworthChoiceTopicId = 0x950, FirstCodsworthChoiceInfoId = 0x958;
    public const uint FirstCodsworthReplyTopicId = 0x960, FirstCodsworthReplyInfoId = 0x968;

    // Stages & Objectives
    public static readonly ushort[] Stages = { 10, 20, 30, 35, 40, 200 };
    public static readonly ushort[] CodsworthQuestStages = { 10, 20, 30, 40, 100 };
    public static readonly ushort[] SanctuaryQuestStages = { 10, 100 };
    public static readonly short[] CodsworthChoiceEndStages = { 20, 30, 40, 100 };

    public static readonly (ushort Index, string Fallback, bool TargetsPreston)[] Objectives =
    {
        (10, "Find the Last Minutemen", true), (85, "Kill the Raiders", false), (86, "Talk to Preston Garvey", true),
    };

    // Synthetic defaults (zero FO4 dialogue strings in source)
    static readonly (string Prompt, string Reply)[] SyntheticPrestonChoices =
    {
        ("Synthetic choice 1: ask who they are.", "Synthetic response 1: militia overview."),
        ("Synthetic choice 2: ask where they are going.", "Synthetic response 2: heading north."),
        ("Synthetic choice 3: finish conversation.", "Synthetic response 3: conversation complete."),
    };
    static readonly (string Prompt, string Reply)[] SyntheticCodsworthChoices =
    {
        ("Synthetic choice 1: ask what happened and the date.", "Synthetic response 1: elapsed years summary."),
        ("Synthetic choice 2: ask about the neighborhood and family.", "Synthetic response 2: neighborhood report."),
        ("Synthetic choice 3: ask about nearby survivors.", "Synthetic response 3: nearby town report."),
        ("Synthetic choice 4: head toward Concord.", "Synthetic response 4: onward to Concord."),
    };

    public const float Units = 70f;
    static readonly ModKey SfEsm = ModKey.FromFileName("Starfield.esm");

    public class Refusal(string m) : Exception(m);

    public static int Usage()
    {
        Console.Error.WriteLine("usage: see the header of dotnet/Mission/Program.cs (points | write | check | npcs | quests | infos | selftest)");
        return 2;
    }
    public static string? ArgOrNull(string[] a, string name) { var i = Array.IndexOf(a, name); return i >= 0 && i + 1 < a.Length ? a[i + 1] : null; }
    public static string Arg(string[] a, string name, string dflt) { var i = Array.IndexOf(a, name); return i >= 0 && i + 1 < a.Length ? a[i + 1] : dflt; }
    public static float Opt(string[] a, string name, float dflt) => float.Parse(Arg(a, name, dflt.ToString(CultureInfo.InvariantCulture)), CultureInfo.InvariantCulture);
    static string F(float v) => v.ToString("0.###", CultureInfo.InvariantCulture);

    // ---------------------------------------------------------------- quests (read only)

    public static int Quests(string sfPath, string factionPattern)
    {
        using var sf = SF.StarfieldMod.CreateFromBinaryOverlay(sfPath, SF.StarfieldRelease.Starfield);
        var cache = sf.ToImmutableLinkCache<SF.IStarfieldMod, SF.IStarfieldModGetter>();
        string Kw(FormKey fk) => fk.IsNull ? "-" : cache.TryResolve<SF.IKeywordGetter>(fk, out var k) ? $"{k.EditorID}({fk.ID:X6})" : $"?{fk.ID:X6}";
        foreach (var g in sf.Quests.GroupBy(q => (Kw(q.QuestType.FormKey), Kw(q.QuestGroup.FormKey))).OrderByDescending(g => g.Count()))
        {
            var ex = g.Where(q => q.Name?.String is { Length: > 0 }).Take(4).Select(q => $"{q.EditorID} '{q.Name?.String}' flags={q.Data?.Flags} obj={q.Objectives.Count}");
            Console.WriteLine($"QTYP {g.Key.Item1} group {g.Key.Item2}: {g.Count()} quests; e.g. {string.Join("; ", ex)}");
        }
        var rx = new System.Text.RegularExpressions.Regex(factionPattern, System.Text.RegularExpressions.RegexOptions.IgnoreCase);
        foreach (var f in sf.Factions.Where(f => f.EditorID is not null && rx.IsMatch(f.EditorID)).Take(40))
            Console.WriteLine($"FACT {f.FormKey.ID:X6} {f.EditorID} relations={f.Relations.Count}");
        return 0;
    }

    // ---------------------------------------------------------------- infos (read only)

    public static int Infos(string sfPath, string voicePattern)
    {
        using var sf = SF.StarfieldMod.CreateFromBinaryOverlay(sfPath, SF.StarfieldRelease.Starfield);
        var cache = sf.ToImmutableLinkCache<SF.IStarfieldMod, SF.IStarfieldModGetter>();
        var wems = voicePattern.StartsWith("wem:") ? voicePattern[4..].Split(',').Select(w => Convert.ToUInt32(w, 16)).ToHashSet() : null;
        var rx = new System.Text.RegularExpressions.Regex(wems is null ? voicePattern : "^$", System.Text.RegularExpressions.RegexOptions.IgnoreCase);
        string Ed(FormKey fk) => fk.IsNull ? "-" : cache.TryResolve<IMajorRecordGetter>(fk, out var r) ? $"{r.EditorID}({fk.ID:X6})" : $"?{fk.ID:X6}";
        int n = 0;
        foreach (var t in sf.Quests.SelectMany(q => q.DialogTopics))
            foreach (var info in t.Responses)
            {
                var text = string.Join(" | ", info.Responses.Select(r => $"wem={r.WEMFile:X8} emo={Ed(r.Emotion.FormKey)} '{r.ResponseText?.String}'"));
                var conds = string.Join("; ", info.Conditions.Select(c => $"{c.Data.GetType().Name.Replace("ConditionData", "")} {c.CompareOperator} {(c as SF.IConditionFloatGetter)?.ComparisonValue} runon={c.Data.RunOnType} flags={c.Flags} " +
                                                                         string.Join(",", c.Data.GetType().GetProperties().Where(p => p.Name.EndsWith("Parameter") || p.Name.Contains("OrList")).Select(p => $"{p.Name}={(p.GetValue(c.Data) is IFormLinkOrIndexGetter<IMajorRecordGetter> l ? Ed(l.Link.FormKey) : p.GetValue(c.Data) is { } v && v.GetType().GetProperty("Link")?.GetValue(v) is IFormLinkGetter fl ? Ed(fl.FormKey) : p.GetValue(c.Data))}"))));
                if (wems is not null ? !info.Responses.Any(r => wems.Contains(r.WEMFile)) : !rx.IsMatch(conds) && !rx.IsMatch(t.EditorID ?? "") && !rx.IsMatch(info.EditorID ?? "") && !rx.IsMatch(info.FormKey.ID.ToString("X6"))) continue;
                if (n++ >= 12) continue;
                Console.WriteLine($"INFO {info.FormKey.ID:X6} {info.EditorID} flags={info.Flags?.Flags} speaker={Ed(info.Speaker.FormKey)} [{text}] conds [{conds}]");
                Console.WriteLine($"  DIAL {t.FormKey.ID:X6} {t.EditorID} quest={Ed(t.Quest.FormKey)} category={t.Category} subtype={t.Subtype} name={t.SubtypeName} topicflags={t.TopicFlags} priority={t.Priority} branch={Ed(t.Branch.FormKey)} infos={t.Responses.Count}");
            }
        Console.WriteLine($"{n} INFO(s) matched (the first 12 printed)");
        return 0;
    }

    // ---------------------------------------------------------------- npcs (read only)

    public static int Npcs(string path, string game, string pattern)
    {
        var rx = new System.Text.RegularExpressions.Regex(pattern, System.Text.RegularExpressions.RegexOptions.IgnoreCase);
        bool Hit(params string?[] xs) => xs.Any(x => x is not null && rx.IsMatch(x));
        int n = 0;
        if (game == "sf")
        {
            using var sf = SF.StarfieldMod.CreateFromBinaryOverlay(path, SF.StarfieldRelease.Starfield);
            var cache = sf.ToImmutableLinkCache<SF.IStarfieldMod, SF.IStarfieldModGetter>();
            foreach (var npc in sf.Npcs)
            {
                var race = cache.TryResolve<SF.IRaceGetter>(npc.Race.FormKey, out var r) ? r.EditorID : null;
                if (!Hit(npc.EditorID, npc.Name?.String, race)) continue;
                Console.WriteLine($"NPC_ {npc.FormKey.ID:X6} {npc.EditorID} name='{npc.Name?.String}' race={race} " +
                                  $"template={npc.DefaultTemplate.FormKey.ID:X6} factions={npc.Factions.Count}");
                n++;
            }
        }
        else if (game == "fo4")
        {
            using var fo4 = F4.Fallout4Mod.CreateFromBinaryOverlay(path, F4.Fallout4Release.Fallout4);
            var cache = fo4.ToImmutableLinkCache<F4.IFallout4Mod, F4.IFallout4ModGetter>();
            var hits = new Dictionary<FormKey, string>();
            foreach (var npc in fo4.Npcs)
            {
                var race = cache.TryResolve<F4.IRaceGetter>(npc.Race.FormKey, out var r) ? r.EditorID : null;
                if (!Hit(npc.EditorID, npc.Name?.String, race)) continue;
                Console.WriteLine($"NPC_ {npc.FormKey.ID:X6} {npc.EditorID} name='{npc.Name?.String}' race={race}");
                hits[npc.FormKey] = npc.EditorID ?? "";
                n++;
            }
            void Refs(F4.ICellGetter c, string where, bool exterior)
            {
                foreach (var p in c.Persistent.Concat(c.Temporary).OfType<F4.IPlacedNpcGetter>())
                {
                    if (!hits.TryGetValue(p.Base.FormKey, out var edid)) continue;
                    var q = p.Position;
                    var pos = exterior ? $"core ({F(q.X / Units)}, {F(q.Y / Units)}, {F(q.Z / Units)})" : $"fo4 ({F(q.X)}, {F(q.Y)}, {F(q.Z)})";
                    Console.WriteLine($"  ACHR {p.FormKey.ID:X6} of {edid} in {where} {pos} rot z {F(p.Rotation.Z)} flags 0x{p.MajorRecordFlagsRaw:X}");
                }
            }
            var world = fo4.Worldspaces.FirstOrDefault(w => w.FormKey.ID == Commonwealth);
            if (world is not null)
            {
                if (world.TopCell is { } top) Refs(top, "Commonwealth persistent", true);
                foreach (var b in world.SubCells) foreach (var s in b.Items) foreach (var c in s.Items) Refs(c, $"Commonwealth ({c.Grid?.Point.X}, {c.Grid?.Point.Y})", true);
            }
            foreach (var b in fo4.Cells) foreach (var s in b.SubBlocks) foreach (var c in s.Cells) Refs(c, $"interior {c.EditorID}", false);
        }
        else throw new Refusal("game must be fo4 or sf");
        Console.WriteLine($"{n} NPC_ matched /{pattern}/ in {Path.GetFileName(path)}");
        return 0;
    }

    // ---------------------------------------------------------------- points (Fallout 4, read only)

    public static int Points(string fo4Path, string outPath, float radius, int max, string? stringsDir = null, string? helloInfosCsv = null)
    {
        BinaryReadParameters? rp = stringsDir is null ? null : new BinaryReadParameters
        {
            StringsParam = new StringsReadParameters { StringsFolderOverride = stringsDir },
        };
        using var fo4 = F4.Fallout4Mod.CreateFromBinaryOverlay(fo4Path, F4.Fallout4Release.Fallout4, rp);
        var cache = fo4.ToImmutableLinkCache<F4.IFallout4Mod, F4.IFallout4ModGetter>();
        var fo4Key = fo4.ModKey;
        var world = fo4.Worldspaces.FirstOrDefault(w => w.FormKey.ID == Commonwealth)
                    ?? throw new Refusal("no Commonwealth worldspace 00003C in " + fo4Path);
        var placed = new Dictionary<FormKey, F4.IPlacedGetter>();
        void Add(F4.ICellGetter? c)
        {
            if (c is null) return;
            foreach (var p in c.Persistent) placed[p.FormKey] = p;
            foreach (var p in c.Temporary) placed[p.FormKey] = p;
        }
        Add(world.TopCell);
        foreach (var b in world.SubCells) foreach (var s in b.Items) foreach (var c in s.Items) Add(c);

        var museum = fo4.EnumerateMajorRecords<F4.ICellGetter>().FirstOrDefault(c => c.FormKey.ID == MuseumCell && c.FormKey.ModKey == fo4Key)
                     ?? throw new Refusal("no ConcordMuseum01 cell 00017DF7");
        var doors = museum.Persistent.Concat(museum.Temporary).OfType<F4.IPlacedObjectGetter>()
            .Where(d => d.TeleportDestination is { } t && placed.ContainsKey(t.Door.FormKey)).ToList();
        if (doors.Count == 0) throw new Refusal("ConcordMuseum01 has no door to the Commonwealth");
        var front = doors.OrderBy(d => (placed[d.TeleportDestination!.Door.FormKey] as F4.IPlacedObjectGetter)?.Position.Z ?? 0f).First();
        var arrival = front.TeleportDestination!.Position;
        var arrivalRot = front.TeleportDestination!.Rotation;
        float ax = arrival.X / Units, ay = arrival.Y / Units, az = arrival.Z / Units;

        var raiders = new List<(float D, F4.IPlacedNpcGetter R, string BaseEdid)>();
        foreach (var p in placed.Values.OfType<F4.IPlacedNpcGetter>())
        {
            if ((p.MajorRecordFlagsRaw & 0x800) != 0) continue;
            if (!cache.TryResolve<F4.INpcGetter>(p.Base.FormKey, out var b) || b.EditorID is null) continue;
            if (!b.EditorID.Contains("Raider", StringComparison.OrdinalIgnoreCase)) continue;
            if (IsCorpse(b.EditorID, p.MajorRecordFlagsRaw)) continue;
            var q = p.Position;
            float d = MathF.Sqrt(MathF.Pow(q.X / Units - ax, 2) + MathF.Pow(q.Y / Units - ay, 2));
            if (d <= radius) raiders.Add((d, p, b.EditorID));
        }
        raiders = raiders.OrderBy(r => r.D).Take(max).ToList();
        if (raiders.Count == 0) throw new Refusal($"no enabled raider within {radius} m of the museum door");

        string Text(ITranslatedStringGetter? s, string dflt) => string.IsNullOrWhiteSpace(s?.String) ? dflt : StripTokens(s!.String!);

        // Index INFO records by FormID for local build-time lookup by FormID
        var infoById = new Dictionary<uint, F4.IDialogResponsesGetter>();
        foreach (var qRec in fo4.Quests)
            foreach (var dt in qRec.DialogTopics)
                foreach (var inf in dt.Responses)
                    infoById[inf.FormKey.ID] = inf;

        string InfoRespText(uint infoId, int respNum, string fallback)
        {
            if (!infoById.TryGetValue(infoId, out var inf)) return fallback;
            var r = inf.Responses.FirstOrDefault(x => x.ResponseNumber == respNum) ?? inf.Responses.FirstOrDefault();
            var t = r?.Text?.String;
            if (string.IsNullOrWhiteSpace(t)) t = inf.Prompt?.String;
            return string.IsNullOrWhiteSpace(t) ? fallback : StripTokens(t!);
        }

        cache.TryResolve<F4.INpcGetter>(new FormKey(fo4Key, PrestonFo4), out var preston);
        cache.TryResolve<F4.IQuestGetter>(new FormKey(fo4Key, Min00), out var min00);
        cache.TryResolve<F4.IQuestGetter>(new FormKey(fo4Key, Mq102Fo4), out var mq102);

        var objectives = new Dictionary<string, string>();
        foreach (var o in Objectives)
            objectives[o.Index.ToString(CultureInfo.InvariantCulture)] =
                Text(min00?.Objectives.FirstOrDefault(x => x.Index == o.Index)?.DisplayText, o.Fallback);

        float pcMult = preston?.Level is F4.IPcLevelMultGetter pm ? pm.LevelMult : 1.0f;
        short fixedLvl = preston?.Level is F4.INpcLevelGetter nl ? nl.Level : (short)10;
        var prestonNpcMeta = new Dictionary<string, object?>
        {
            ["src"] = $"{PrestonFo4:X6}",
            ["is_pc_level_mult"] = preston?.Level is F4.IPcLevelMultGetter || preston is null,
            ["pc_level_mult"] = pcMult,
            ["fixed_level"] = fixedLvl,
            ["calc_min_level"] = preston?.CalcMinLevel ?? (short)10,
            ["calc_max_level"] = preston?.CalcMaxLevel ?? (short)0,
            ["essential"] = preston is null || preston.Flags.HasFlag(F4.Npc.Flag.Essential),
            ["protected"] = preston?.Flags.HasFlag(F4.Npc.Flag.Protected) ?? false,
            ["unique"] = preston is null || preston.Flags.HasFlag(F4.Npc.Flag.Unique),
            ["auto_calc_stats"] = preston is null || preston.Flags.HasFlag(F4.Npc.Flag.AutoCalcStats),
        };

        // Preston 3-exchange talk scene strings from DialogueConcordArea (0179F3 / 010SurvivorSceneReward 01C245)
        var prestonTalk = new Dictionary<string, object?>
        {
            ["greeting"] = InfoRespText(0x0CA9CC, 1, "Synthetic Concord greeting."),
            ["choices"] = new object[]
            {
                new Dictionary<string, string>
                {
                    ["prompt"] = InfoRespText(0x01C238, 1, SyntheticPrestonChoices[0].Prompt),
                    ["reply"] = InfoRespText(0x05DF11, 2, SyntheticPrestonChoices[0].Reply),
                },
                new Dictionary<string, string>
                {
                    ["prompt"] = InfoRespText(0x01C22C, 1, SyntheticPrestonChoices[1].Prompt),
                    ["reply"] = InfoRespText(0x05DF0D, 1, SyntheticPrestonChoices[1].Reply),
                },
                new Dictionary<string, string>
                {
                    ["prompt"] = InfoRespText(0x01C237, 1, SyntheticPrestonChoices[2].Prompt),
                    ["reply"] = InfoRespText(0x05DF1B, 1, SyntheticPrestonChoices[2].Reply),
                },
            },
        };

        // Codsworth MQ102-lite 4-choice Sanctuary scene strings from MQ102 (01CC2A) + DialogueCodsworthPostWar (01E64E)
        var codsworthQuestMeta = new Dictionary<string, object?>
        {
            ["name"] = Text(mq102?.Name, "Synthetic Sanctuary Inquiry"),
            ["objective_10"] = Text(mq102?.Objectives.FirstOrDefault(x => x.Index == 10)?.DisplayText, "Speak with the household robot"),
            ["greeting_info"] = "0001E64D",
            ["greeting_response"] = 1,
            ["greeting"] = InfoRespText(0x01E64D, 1, "Synthetic robot greeting."),
            ["choices"] = new object[]
            {
                new Dictionary<string, object>
                {
                    ["prompt_info"] = "000A1814", ["reply_info"] = "000A1818", ["reply_response"] = 1,
                    ["prompt"] = InfoRespText(0x0A1814, 1, SyntheticCodsworthChoices[0].Prompt),
                    ["reply"] = InfoRespText(0x0A1818, 1, SyntheticCodsworthChoices[0].Reply),
                },
                new Dictionary<string, object>
                {
                    ["prompt_info"] = "000A519B", ["reply_info"] = "000A51A3", ["reply_response"] = 1,
                    ["prompt"] = InfoRespText(0x0A519B, 1, SyntheticCodsworthChoices[1].Prompt),
                    ["reply"] = InfoRespText(0x0A51A3, 1, SyntheticCodsworthChoices[1].Reply),
                },
                new Dictionary<string, object>
                {
                    ["prompt_info"] = "0019E113", ["reply_info"] = "0019E112", ["reply_response"] = 1,
                    ["prompt"] = InfoRespText(0x19E113, 1, SyntheticCodsworthChoices[2].Prompt),
                    ["reply"] = InfoRespText(0x19E112, 1, SyntheticCodsworthChoices[2].Reply),
                },
                new Dictionary<string, object>
                {
                    ["prompt_info"] = "0019E70A", ["reply_info"] = "0019E711", ["reply_response"] = 1,
                    ["prompt"] = InfoRespText(0x19E70A, 1, SyntheticCodsworthChoices[3].Prompt),
                    ["reply"] = InfoRespText(0x19E711, 1, SyntheticCodsworthChoices[3].Reply),
                },
            },
        };

        object? codsworth = null;
        if (placed.TryGetValue(new FormKey(fo4Key, CodsworthFo4Ref), out var cw) && cw is F4.IPlacedNpcGetter cn &&
            cn.Base.FormKey == new FormKey(fo4Key, CodsworthFo4Npc))
        {
            cache.TryResolve<F4.INpcGetter>(cn.Base.FormKey, out var cb);
            codsworth = new Dictionary<string, object?>
            {
                ["src"] = $"{cn.FormKey.ID:X6}", ["name"] = Text(cb?.Name, "Codsworth"),
                ["pos"] = new[] { cn.Position.X / Units, cn.Position.Y / Units, cn.Position.Z / Units },
                ["rot"] = new[] { cn.Rotation.X, cn.Rotation.Y, cn.Rotation.Z },
            };
        }

        object? sanctuaryBench = null;
        if (placed.TryGetValue(new FormKey(fo4Key, SanctuaryBenchFo4Ref), out var sb) && sb is F4.IPlacedObjectGetter sbo)
        {
            sanctuaryBench = new Dictionary<string, object?>
            {
                ["src"] = $"{sbo.FormKey.ID:X6}",
                ["pos"] = new[] { sbo.Position.X / Units, sbo.Position.Y / Units, sbo.Position.Z / Units },
                ["rot"] = new[] { sbo.Rotation.X, sbo.Rotation.Y, sbo.Rotation.Z },
            };
        }

        List<object>? helloResolved = null;
        if (!string.IsNullOrWhiteSpace(helloInfosCsv))
        {
            helloResolved = new List<object>();
            foreach (var tok in helloInfosCsv.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries))
            {
                uint hid = Convert.ToUInt32(tok, 16);
                helloResolved.Add(new Dictionary<string, object>
                {
                    ["info"] = $"{hid:X8}",
                    ["response"] = 1,
                    ["text"] = InfoRespText(hid, 1, $"Synthetic hello {hid:X8}"),
                });
            }
        }

        var doc = new Dictionary<string, object?>
        {
            ["source"] = Path.GetFileName(fo4Path),
            ["frame"] = "metres, FO4 position / 70 (the core's local frame); rotation in radians as stored",
            ["quest_name"] = Text(min00?.Name, "When Freedom Calls"),
            ["preston_name"] = Text(preston?.Name, "Preston Garvey"),
            ["preston_npc"] = prestonNpcMeta,
            ["preston_talk"] = prestonTalk,
            ["objectives"] = objectives,
            ["preston"] = new Dictionary<string, object?>
            {
                ["src"] = $"{front.FormKey.ID:X6}:XTEL", ["pos"] = new[] { ax, ay, az },
                ["rot"] = new[] { arrivalRot.X, arrivalRot.Y, arrivalRot.Z },
            },
            ["raiders"] = raiders.Select(r => (object)new Dictionary<string, object?>
            {
                ["src"] = $"{r.R.FormKey.ID:X6}", ["edid"] = r.R.EditorID ?? "", ["base"] = r.BaseEdid, ["dist_m"] = MathF.Round(r.D, 2),
                ["pos"] = new[] { r.R.Position.X / Units, r.R.Position.Y / Units, r.R.Position.Z / Units },
                ["rot"] = new[] { r.R.Rotation.X, r.R.Rotation.Y, r.R.Rotation.Z },
            }).ToList(),
            ["codsworth"] = codsworth,
            ["codsworth_quest"] = codsworthQuestMeta,
            ["sanctuary_bench"] = sanctuaryBench,
            ["sanctuary_quest"] = new Dictionary<string, string>
            {
                ["name"] = "First Settlement",
                ["objective_10"] = "Activate the Sanctuary workbench",
            },
        };
        if (helloResolved is not null) doc["codsworth_hellos"] = helloResolved;

        Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(outPath))!);
        File.WriteAllText(outPath, JsonSerializer.Serialize(doc, new JsonSerializerOptions { WriteIndented = true }));
        Console.WriteLine($"wrote {outPath}: museum door {front.FormKey.ID:X6} -> arrival ({F(ax)}, {F(ay)}, {F(az)}) m; " +
                          $"{raiders.Count} raider(s): " + string.Join(", ", raiders.Select(r => $"{r.R.FormKey.ID:X6} {r.R.EditorID} {r.BaseEdid} {F(r.D)} m")) +
                          (codsworth is null ? "; no Codsworth ACHR 01CA7D" : $"; Codsworth {CodsworthFo4Ref:X6}"));
        return 0;
    }

    public static bool IsCorpse(string baseEdid, int flags) =>
        (flags & 0x200) != 0 || baseEdid.StartsWith("Loot_", StringComparison.OrdinalIgnoreCase) ||
        baseEdid.Contains("Corpse", StringComparison.OrdinalIgnoreCase);

    public static string StripTokens(string text)
    {
        var t = System.Text.RegularExpressions.Regex.Replace(text, @"<[A-Za-z]+=[^>]*>", "");
        t = System.Text.RegularExpressions.Regex.Replace(t, @"\(\s*/?\s*\)", "");
        return System.Text.RegularExpressions.Regex.Replace(t, @"\s{2,}", " ").Trim();
    }

    // ---------------------------------------------------------------- write (Starfield)

    sealed record Masters(SF.IStarfieldModGetter Sf, SF.IStarfieldModGetter Core, SF.IStarfieldModGetter Raider, ILinkCache Cache) : IDisposable
    {
        public void Dispose() { (Raider as IDisposable)?.Dispose(); (Core as IDisposable)?.Dispose(); (Sf as IDisposable)?.Dispose(); }
    }

    static BinaryReadParameters Styles(params ModKey[] full)
    {
        var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        foreach (var k in full) styles.Set(new KeyedMasterStyle(k, MasterStyle.Full));
        return new BinaryReadParameters { MasterFlagsLookup = styles };
    }

    static Masters Open(string sfPath, string corePath, string raiderPath)
    {
        var sf = SF.StarfieldMod.CreateFromBinaryOverlay(sfPath, SF.StarfieldRelease.Starfield);
        var core = SF.StarfieldMod.CreateFromBinaryOverlay(corePath, SF.StarfieldRelease.Starfield, Styles(SfEsm));
        var raider = SF.StarfieldMod.CreateFromBinaryOverlay(raiderPath, SF.StarfieldRelease.Starfield, Styles(SfEsm));
        var cache = new SF.IStarfieldModGetter[] { sf, core, raider }.ToImmutableLinkCache<SF.IStarfieldMod, SF.IStarfieldModGetter>();
        return new Masters(sf, core, raider, cache);
    }

    static SF.IWorldspaceGetter FindWorld(SF.IStarfieldModGetter core, string edid) =>
        core.Worldspaces.FirstOrDefault(w => w.EditorID == edid && w.FormKey.ModKey == core.ModKey)
        ?? throw new Refusal($"{core.ModKey} has no worldspace {edid}");

    static float[] Floats(JsonElement e) => e.EnumerateArray().Select(x => x.GetSingle()).ToArray();

    static SF.INpcGetter PickPrestonTemplate(SF.IStarfieldModGetter sf, FormKey humanRaceKey)
    {
        var papa = sf.Npcs.FirstOrDefault(n => n.FormKey == new FormKey(SfEsm, SfPapaKatzId) && n.EditorID == SfPapaKatzEdid);
        if (papa is not null) return papa;
        var fallback = sf.Npcs.FirstOrDefault(n => n.Race.FormKey == humanRaceKey && !string.IsNullOrEmpty(n.EditorID));
        return fallback ?? throw new Refusal($"Starfield.esm has neither {SfPapaKatzEdid} ({SfPapaKatzId:X6}) nor a HumanRace NPC template");
    }

    static SF.Condition SpeakerIs(FormKey npcKey)
    {
        var d = new SF.GetIsIDConditionData { RunOnType = SF.Condition.RunOnType.Subject };
        d.FirstParameter.Link.SetTo(npcKey);
        return new SF.ConditionFloat { CompareOperator = SF.CompareOperator.EqualTo, ComparisonValue = 1f, Data = d };
    }

    static SF.Condition QuestStageCond(FormKey questKey, SF.CompareOperator op, float stageVal)
    {
        var d = new SF.GetStageConditionData { RunOnType = SF.Condition.RunOnType.Subject };
        d.FirstParameter.Link.SetTo(questKey);
        return new SF.ConditionFloat { CompareOperator = op, ComparisonValue = stageVal, Data = d };
    }

    static SF.Scene BuildTopScene(
        ModKey modKey,
        SF.Quest quest,
        FormKey speakerNpcKey,
        SF.Condition stageGate,
        uint sceneId,
        string sceneEdid,
        uint greetTopicId,
        string greetTopicEdid,
        uint greetInfoId,
        string greetInfoEdid,
        string greetText,
        uint greetWem,
        uint firstChoiceTopicId,
        uint firstChoiceInfoId,
        uint firstReplyTopicId,
        uint firstReplyInfoId,
        string prefixEdid,
        float priority,
        IReadOnlyList<(string Prompt, string Reply, short EndStage, bool Goodbye, uint Wem)> choices)
    {
        var rel = SF.StarfieldRelease.Starfield;
        var greetTopic = new SF.DialogTopic(new FormKey(modKey, greetTopicId), rel)
        {
            EditorID = greetTopicEdid,
            Quest = new FormLink<SF.IQuestGetter>(quest.FormKey),
            Priority = priority,
            Category = SF.DialogTopic.CategoryEnum.Scene,
            Subtype = SF.DialogTopic.SubtypeEnum.CustomScene,
            SubtypeName = SF.DialogTopic.SubtypeNameEnum.CustomScene,
        };
        var greetInfo = new SF.DialogResponses(new FormKey(modKey, greetInfoId), rel)
        {
            EditorID = greetInfoEdid,
        };
        greetInfo.Responses.Add(new SF.DialogResponse { ResponseText = greetText, WEMFile = greetWem });
        greetInfo.Conditions.Add(SpeakerIs(speakerNpcKey));
        greetTopic.Responses.Add(greetInfo);
        (greetTopic.TopicInfoList ??= new()).Add(new FormLink<SF.IDialogResponsesGetter>(greetInfo.FormKey));
        quest.DialogTopics.Add(greetTopic);

        var topScene = new SF.Scene(new FormKey(modKey, sceneId), rel)
        {
            EditorID = sceneEdid,
            Quest = new FormLinkNullable<SF.IQuestGetter>(quest.FormKey),
            Flags = (SF.Scene.Flag)0x2814,
            Index = 0,
            LastActionIndex = 2,
            SCPI = new byte[] { 0x37, 0x00 },
            VNAM = new byte[] { 3, 0, 0, 0, 3, 0, 0, 0, 3, 0, 0, 0, 3, 0, 0, 0, 3, 0, 0, 0 },
        };
        topScene.Conditions.Add(SpeakerIs(speakerNpcKey));
        topScene.Conditions.Add(stageGate);
        topScene.Actors.Add(new SF.SceneActor
        {
            ID = 0,
            BehaviorFlags = (SF.SceneActor.BehaviorFlag)0x10A,
            Flags = SF.SceneActor.Flag.NoCommandState,
        });
        topScene.Actors.Add(new SF.SceneActor
        {
            ID = unchecked((uint)-2),
            BehaviorFlags = (SF.SceneActor.BehaviorFlag)0x10A,
            Flags = SF.SceneActor.Flag.NoCommandState,
        });
        topScene.Phases.Add(new SF.ScenePhase { Name = "", EditorWidth = 500 });
        topScene.Phases.Add(new SF.ScenePhase { Name = "TOPLEVELNEST", EditorWidth = 500 });

        topScene.Actions ??= new ExtendedList<SF.ASceneAction>();
        topScene.Actions.Add(new SF.DialogueSceneAction
        {
            Name = "",
            Index = 1,
            AliasID = 0,
            StartPhase = 0,
            EndPhase = 0,
            Topic = new FormLinkNullable<SF.IDialogTopicGetter>(greetTopic.FormKey),
            LoopingMin = 1f,
            LoopingMax = 10f,
        });

        var playerAct = new SF.PlayerDialogueSceneAction
        {
            Name = "",
            Index = 2,
            AliasID = 0,
            DialogueTargetActor = 0,
            StartPhase = 1,
            EndPhase = 1,
        };

        for (uint idx = 0; idx < (uint)choices.Count; idx++)
        {
            var c = choices[(int)idx];
            var pcTopic = new SF.DialogTopic(new FormKey(modKey, firstChoiceTopicId + idx), rel)
            {
                EditorID = $"{prefixEdid}_ChoiceTopic_{idx}",
                Quest = new FormLink<SF.IQuestGetter>(quest.FormKey),
                Priority = priority,
                Category = SF.DialogTopic.CategoryEnum.Scene,
                Subtype = SF.DialogTopic.SubtypeEnum.CustomScene,
                SubtypeName = SF.DialogTopic.SubtypeNameEnum.CustomScene,
            };
            var pcInfo = new SF.DialogResponses(new FormKey(modKey, firstChoiceInfoId + idx), rel)
            {
                EditorID = $"{prefixEdid}_ChoiceInfo_{idx}",
                Prompt = c.Prompt,
            };
            pcInfo.Responses.Add(new SF.DialogResponse { ResponseText = c.Prompt, WEMFile = 0 });
            pcTopic.Responses.Add(pcInfo);
            (pcTopic.TopicInfoList ??= new()).Add(new FormLink<SF.IDialogResponsesGetter>(pcInfo.FormKey));
            quest.DialogTopics.Add(pcTopic);

            var npcTopic = new SF.DialogTopic(new FormKey(modKey, firstReplyTopicId + idx), rel)
            {
                EditorID = $"{prefixEdid}_ReplyTopic_{idx}",
                Quest = new FormLink<SF.IQuestGetter>(quest.FormKey),
                Priority = priority,
                Category = SF.DialogTopic.CategoryEnum.Scene,
                Subtype = SF.DialogTopic.SubtypeEnum.CustomScene,
                SubtypeName = SF.DialogTopic.SubtypeNameEnum.CustomScene,
            };
            var npcInfo = new SF.DialogResponses(new FormKey(modKey, firstReplyInfoId + idx), rel)
            {
                EditorID = $"{prefixEdid}_ReplyInfo_{idx}",
            };
            if (c.EndStage > 0)
                npcInfo.SetParentQuestStage = new SF.DialogSetParentQuestStage { OnBegin = -1, OnEnd = c.EndStage };
            if (c.Goodbye)
                npcInfo.Flags = new SF.DialogResponseFlags { Flags = 1 };
            else
            {
                npcInfo.StartScene = new FormLinkNullable<SF.ISceneGetter>(topScene.FormKey);
                npcInfo.StartScenePhase = "TOPLEVELNEST";
            }
            npcInfo.Responses.Add(new SF.DialogResponse { ResponseText = c.Reply, WEMFile = c.Wem });
            npcInfo.Conditions.Add(SpeakerIs(speakerNpcKey));
            npcTopic.Responses.Add(npcInfo);
            (npcTopic.TopicInfoList ??= new()).Add(new FormLink<SF.IDialogResponsesGetter>(npcInfo.FormKey));
            quest.DialogTopics.Add(npcTopic);

            playerAct.DialogueList.Add(new SF.PlayerDialogueSceneActionItem
            {
                PlayerChoice = new FormLinkNullable<SF.IDialogTopicGetter>(pcTopic.FormKey),
                NpcResponse = new FormLink<SF.IDialogTopicGetter>(npcTopic.FormKey),
            });
        }

        topScene.Actions.Add(playerAct);
        quest.Scenes.Add(topScene);
        return topScene;
    }

    public sealed record MqVoiceSpec(uint GreetingWem, uint[] ChoiceReplyWems);

    public static MqVoiceSpec LoadMqVoice(string path)
    {
        using var doc = JsonDocument.Parse(File.ReadAllText(path));
        var root = doc.RootElement;
        uint greet = uint.Parse(root.GetProperty("greeting_wem").GetString()!, NumberStyles.HexNumber, CultureInfo.InvariantCulture);
        var replies = root.GetProperty("reply_wems").EnumerateArray()
            .Select(x => uint.Parse(x.GetString()!, NumberStyles.HexNumber, CultureInfo.InvariantCulture)).ToArray();
        if (replies.Length != 4) throw new Refusal($"{path}: expected 4 reply_wems, got {replies.Length}");
        var all = new[] { greet }.Concat(replies).ToArray();
        if (all.Any(w => w == 0) || all.Distinct().Count() != all.Length)
            throw new Refusal($"{path}: duplicate or zero MQ102 wem id");
        return new MqVoiceSpec(greet, replies);
    }

    public static int Write(string sfPath, string corePath, string raiderPath, string pointsPath, string outDir, string plugin,
                            string worldEdid, bool alias, string? codsworthBody = CodsworthBody, string? codsworthModel = null,
                            string? codsworthVoice = null, string? codsworthMqVoice = null)
    {
        var pts = JsonDocument.Parse(File.ReadAllText(pointsPath)).RootElement;
        using var m = Open(sfPath, corePath, raiderPath);
        var modKey = ModKey.FromFileName(plugin);
        var mod = new SF.StarfieldMod(modKey, SF.StarfieldRelease.Starfield);
        mod.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Master;
        mod.ModHeader.Author = "fo4-to-starfield Mission";

        if (!m.Cache.TryResolve<SF.IMiscItemGetter>(new FormKey(SfEsm, CreditsId), out var credits) || credits.EditorID != "Credits")
            throw new Refusal("Starfield.esm 00000F is not the MISC Credits");
        if (!m.Cache.TryResolve<SF.IKeywordGetter>(new FormKey(SfEsm, QuestTypeSideId), out var qtyp) || qtyp.EditorID != QuestTypeSideEdid)
            throw new Refusal($"Starfield.esm {QuestTypeSideId:X6} is not the KYWD {QuestTypeSideEdid}");
        if (!m.Cache.TryResolve<SF.IFactionGetter>(new FormKey(SfEsm, PlayerFactionId), out var playerFaction) || playerFaction.EditorID != PlayerFactionEdid)
            throw new Refusal($"Starfield.esm {PlayerFactionId:X6} is not the FACT {PlayerFactionEdid}");
        if (!m.Cache.TryResolve<SF.IStaticGetter>(new FormKey(SfEsm, XMarkerId), out var xMarker) || xMarker.EditorID != "XMarker")
            throw new Refusal($"Starfield.esm {XMarkerId:X6} is not the STAT XMarker");
        if (!m.Cache.TryResolve<SF.IRaceGetter>(new FormKey(SfEsm, SfHumanRaceId), out var humanRace) || humanRace.EditorID != SfHumanRaceEdid)
            throw new Refusal($"Starfield.esm {SfHumanRaceId:X6} is not the RACE {SfHumanRaceEdid}");
        var prestonVoice = m.Sf.VoiceTypes.FirstOrDefault(v => v.EditorID == SfPrestonVoiceEdid && v.Flags.HasFlag(SF.VoiceType.Flag.AllowDefaultDialog))
                           ?? throw new Refusal($"Starfield.esm has no VTYP {SfPrestonVoiceEdid} with AllowDefaultDialog");
        if (!m.Cache.TryResolve<SF.IOutfitGetter>(new FormKey(SfEsm, SfPrestonOutfitId), out var prestonOutfit) || prestonOutfit.EditorID != SfPrestonOutfitEdid)
            throw new Refusal($"Starfield.esm {SfPrestonOutfitId:X6} is not the OTFT {SfPrestonOutfitEdid}");
        if (!m.Cache.TryResolve<SF.IWeaponGetter>(new FormKey(SfEsm, SfPrestonWeaponId), out var prestonWeapon) || prestonWeapon.EditorID != SfPrestonWeaponEdid)
            throw new Refusal($"Starfield.esm {SfPrestonWeaponId:X6} is not the WEAP {SfPrestonWeaponEdid}");
        if (!m.Cache.TryResolve<SF.IAmmunitionGetter>(new FormKey(SfEsm, SfPrestonAmmoId), out var prestonAmmo) || prestonAmmo.EditorID != SfPrestonAmmoEdid)
            throw new Refusal($"Starfield.esm {SfPrestonAmmoId:X6} is not the AMMO {SfPrestonAmmoEdid}");
        if (!m.Cache.TryResolve<SF.IPackageGetter>(new FormKey(SfEsm, RaiderCombatPackageId), out var raiderCombatPack) || raiderCombatPack.EditorID != RaiderCombatPackageEdid)
            throw new Refusal($"Starfield.esm {RaiderCombatPackageId:X6} is not the PACK {RaiderCombatPackageEdid}");
        if (!m.Cache.TryResolve<SF.IPackageGetter>(new FormKey(SfEsm, RaiderSandboxPackageId), out var raiderSandboxPack) || raiderSandboxPack.EditorID != RaiderSandboxPackageEdid)
            throw new Refusal($"Starfield.esm {RaiderSandboxPackageId:X6} is not the PACK {RaiderSandboxPackageEdid}");

        var raiderNpc = m.Raider.Npcs.FirstOrDefault(n => n.FormKey.ID == RaiderId && n.EditorID == "FO4_LvlRaider")
                        ?? throw new Refusal($"{m.Raider.ModKey} has no F04800 FO4_LvlRaider");
        var world = FindWorld(m.Core, worldEdid);
        var top = world.TopCell ?? throw new Refusal($"{worldEdid} has no persistent cell");

        // 2g: Preston's dedicated HumanRace NPC_ from FO4 0x00019FD9 metadata + Starfield colonial/Orion stand-ins
        var minutemen = new SF.Faction(new FormKey(modKey, MinutemenFactionId), SF.StarfieldRelease.Starfield) { EditorID = MinutemenFactionEdid };
        minutemen.Relations.Add(new SF.Relation { Target = new FormLink<SF.IRelatableGetter>(playerFaction.FormKey), Reaction = SF.CombatReaction.Ally });
        mod.Factions.Add(minutemen);

        var prestonTpl = PickPrestonTemplate(m.Sf, humanRace.FormKey);
        var npc = (SF.Npc)prestonTpl.Duplicate(new FormKey(modKey, PrestonNpcId));
        npc.EditorID = PrestonEdid;
        npc.Name = pts.GetProperty("preston_name").GetString();
        npc.Race.SetTo(humanRace.FormKey);
        npc.Voice.SetTo(prestonVoice.FormKey);
        npc.VirtualMachineAdapter = null;
        npc.Packages.Clear();
        npc.TemplateActors = null;
        npc.CrimeFaction.Clear();
        npc.DefaultOutfit.SetTo(prestonOutfit.FormKey);
        npc.Items ??= new ExtendedList<SF.ContainerEntry>();
        npc.Items.Clear();
        npc.Items.Add(new SF.ContainerEntry { Item = new SF.ContainerItem { Item = new FormLink<SF.IItemGetter>(prestonWeapon.FormKey), Count = 1 } });
        npc.Items.Add(new SF.ContainerEntry { Item = new SF.ContainerItem { Item = new FormLink<SF.IItemGetter>(prestonAmmo.FormKey), Count = 50 } });

        short minLvl = 10, maxLvl = 0;
        float lvlMult = 1.0f;
        bool isMult = true, isProt = false;
        if (pts.TryGetProperty("preston_npc", out var pMeta) && pMeta.ValueKind == JsonValueKind.Object)
        {
            if (pMeta.TryGetProperty("calc_min_level", out var cmin)) minLvl = cmin.GetInt16();
            if (pMeta.TryGetProperty("calc_max_level", out var cmax)) maxLvl = cmax.GetInt16();
            if (pMeta.TryGetProperty("pc_level_mult", out var pmult)) lvlMult = pmult.GetSingle();
            if (pMeta.TryGetProperty("is_pc_level_mult", out var ipm)) isMult = ipm.GetBoolean();
            if (pMeta.TryGetProperty("protected", out var pr)) isProt = pr.GetBoolean();
        }
        npc.Level = isMult ? new SF.PcLevelMult { LevelMult = lvlMult } : new SF.NpcLevel { Level = minLvl };
        npc.CalcMinLevel = minLvl;
        npc.CalcMaxLevel = maxLvl;
        var pFlags = (npc.Flags | SF.Npc.Flag.Essential | SF.Npc.Flag.Unique | SF.Npc.Flag.AutoCalcStats) & ~SF.Npc.Flag.Respawn;
        if (isProt) pFlags |= SF.Npc.Flag.Protected;
        npc.Flags = pFlags;
        npc.Factions.Clear();
        npc.Factions.Add(new SF.RankPlacement { Faction = new FormLink<SF.IFactionGetter>(minutemen.FormKey), Rank = 0 });
        mod.Npcs.Add(npc);

        // Worldspace & persistent cell override holding our persistent ACHRs
        var w = (SF.Worldspace)world.DeepCopy();
        w.SubCells.Clear();
        var cell = (SF.Cell)top.DeepCopy();
        cell.Persistent.Clear();
        cell.Temporary.Clear();
        cell.NavigationMeshes.Clear();
        w.TopCell = cell;
        SF.PlacedNpc Ach(uint id, FormKey baseKey, string edid, JsonElement e)
        {
            var p = Floats(e.GetProperty("pos"));
            var r = Floats(e.GetProperty("rot"));
            var a = new SF.PlacedNpc(new FormKey(modKey, id), SF.StarfieldRelease.Starfield)
            {
                EditorID = edid, Base = new FormLink<SF.INpcGetter>(baseKey),
                Position = new P3Float(p[0], p[1], p[2]), Rotation = new P3Float(r[0], r[1], r[2]),
            };
            a.MajorRecordFlagsRaw |= 0x400;
            cell.Persistent.Add(a);
            return a;
        }
        var prestonRef = Ach(PrestonRefId, npc.FormKey, PrestonRefEdid, pts.GetProperty("preston"));
        var raiderRefs = new List<SF.PlacedNpc>();
        uint next = FirstRaiderRefId;
        foreach (var r in pts.GetProperty("raiders").EnumerateArray())
            raiderRefs.Add(Ach(next++, raiderNpc.FormKey, $"FO4SF_Min00_Raider_{r.GetProperty("src").GetString()}", r));
        if (next > CodsworthNpcId) throw new Refusal($"{raiderRefs.Count} raiders overrun 0x{CodsworthNpcId:X} (Codsworth's id)");

        SF.Npc? cods = null;
        SF.PlacedNpc? codsRef = null;
        if (codsworthBody is not null)
        {
            if (!pts.TryGetProperty("codsworth", out var cj) || cj.ValueKind != JsonValueKind.Object)
                throw new Refusal("points.json has no codsworth (rerun points, or write --no-codsworth)");
            var body = m.Sf.Npcs.FirstOrDefault(n => n.EditorID == codsworthBody)
                       ?? throw new Refusal($"Starfield.esm has no NPC_ {codsworthBody} (the Codsworth body)");
            if (!m.Cache.TryResolve<SF.IRaceGetter>(body.Race.FormKey, out var baseBotRace))
                throw new Refusal($"Codsworth body {codsworthBody} race {body.Race.FormKey} does not resolve");

            // 2h: Dialogue-capable duplicate Race (AllowPcDialog) + custom VoiceType (AllowDefaultDialog)
            var codsRace = (SF.Race)baseBotRace.Duplicate(new FormKey(modKey, CodsworthRaceId));
            codsRace.EditorID = CodsworthRaceEdid;
            codsRace.Flags |= SF.Race.Flag.AllowPcDialog;
            codsRace.ArmorRace.SetTo(baseBotRace.FormKey);
            mod.Races.Add(codsRace);

            var codsVoice = new SF.VoiceType(new FormKey(modKey, CodsworthVoiceId), SF.StarfieldRelease.Starfield)
            {
                EditorID = CodsworthVoiceEdid,
                Flags = SF.VoiceType.Flag.AllowDefaultDialog,
            };
            mod.VoiceTypes.Add(codsVoice);

            cods = (SF.Npc)body.Duplicate(new FormKey(modKey, CodsworthNpcId));
            cods.EditorID = CodsworthEdid;
            cods.Name = cj.GetProperty("name").GetString();
            cods.Race.SetTo(codsRace.FormKey);
            cods.Voice.SetTo(codsVoice.FormKey);
            cods.Flags = (cods.Flags | SF.Npc.Flag.Essential | SF.Npc.Flag.Unique) & ~SF.Npc.Flag.Respawn;
            cods.Factions.Clear();
            cods.VirtualMachineAdapter = null;
            if (codsworthModel is not null)
            {
                var aa = m.Sf.ArmorAddons.FirstOrDefault(x => x.FormKey == new FormKey(SfEsm, MiniBotArmaId) && x.EditorID == MiniBotArmaEdid)
                         ?? throw new Refusal($"Starfield.esm {MiniBotArmaId:X6} is not the ARMA {MiniBotArmaEdid}");
                var sk = m.Sf.Armors.FirstOrDefault(x => x.FormKey == new FormKey(SfEsm, MiniBotSkinId) && x.EditorID == MiniBotSkinEdid)
                         ?? throw new Refusal($"Starfield.esm {MiniBotSkinId:X6} is not the ARMO {MiniBotSkinEdid}");
                var arma = (SF.ArmorAddon)aa.Duplicate(new FormKey(modKey, CodsworthArmaId));
                arma.EditorID = CodsworthArmaEdid;
                arma.Race.SetTo(codsRace.FormKey);
                arma.AdditionalRaces.Add(new FormLink<SF.IRaceGetter>(baseBotRace.FormKey));
                int set = 0;
                foreach (var g in new[] { arma.WorldModel?.Male, arma.WorldModel?.Female })
                    if (g?.File?.GivenPath is { Length: > 0 } given)
                        { g.File = new AssetLink<StarfieldModelAssetType>(ModelPath(given, codsworthModel)); set++; }
                if (set == 0) throw new Refusal($"{MiniBotArmaEdid} has no world model to replace");
                var skin = (SF.Armor)sk.Duplicate(new FormKey(modKey, CodsworthSkinId));
                skin.EditorID = CodsworthSkinEdid;
                var entry = new SF.ArmorAddonModel
                {
                    AddonIndex = skin.Armatures.FirstOrDefault()?.AddonIndex ?? 0,
                    ArmorAddon = new FormLinkNullable<SF.IArmorAddonGetter>(arma.FormKey),
                };
                skin.Armatures.Clear();
                skin.Armatures.Add(entry);
                cods.Skin.SetTo(skin.FormKey);
                mod.ArmorAddons.Add(arma);
                mod.Armors.Add(skin);
            }
            mod.Npcs.Add(cods);
            codsRef = Ach(CodsworthRefId, cods.FormKey, CodsworthRefEdid, cj);
        }
        mod.Worldspaces.Add(w);

        // 2b: FO4SF_Min00 (0x800) — non-StartGameEnabled (started via StartNoWait at FO4SFNewGame stage 200)
        var objText = pts.GetProperty("objectives");
        var quest = new SF.Quest(new FormKey(modKey, QuestId), SF.StarfieldRelease.Starfield)
        {
            EditorID = QuestEdid, Name = pts.GetProperty("quest_name").GetString(), FormVersion = 581, Version2 = 12,
            Data = new SF.QuestData
            {
                Flags = SF.Quest.Flag.StartsEnabled | SF.Quest.Flag.AllowRepeatedStages | SF.Quest.Flag.DisplaysInHud |
                        SF.Quest.Flag.RunOnce | SF.Quest.Flag.HasDialogueData | (SF.Quest.Flag)0x10000,
                Priority = 50,
            },
        };
        quest.QuestType.SetTo(qtyp.FormKey);
        foreach (var s in Stages)
        {
            var st = new SF.QuestStage { Index = s };
            if (s == 200) st.LogEntries.Add(new SF.QuestLogEntry { Flags = SF.QuestLogEntry.Flag.CompleteQuest });
            quest.Stages.Add(st);
        }
        foreach (var o in Objectives)
        {
            var obj = new SF.QuestObjective { Index = o.Index, DisplayText = objText.GetProperty(o.Index.ToString(CultureInfo.InvariantCulture)).GetString() };
            if (alias && o.TargetsPreston) obj.Targets.Add(new SF.QuestObjectiveTarget { AliasID = PrestonAlias });
            quest.Objectives.Add(obj);
        }

        SF.Scene? prestonScene = null;
        if (alias)
        {
            (quest.Aliases ??= new ExtendedList<SF.AQuestAlias>()).Add(new SF.QuestReferenceAlias
            {
                ID = PrestonAlias, Name = "PrestonGarvey",
                Flags = SF.AQuestAlias.Flag.AllowDisabled | SF.AQuestAlias.Flag.AllowReserved | SF.AQuestAlias.Flag.UsesStoredText,
                ForcedReference = new FormLinkNullable<SF.IPlacedGetter>(prestonRef.FormKey),
            });
            for (int ri = 0; ri < raiderRefs.Count; ri++)
            {
                quest.Aliases.Add(new SF.QuestReferenceAlias
                {
                    ID = (uint)(1 + ri), Name = $"Raider_{ri}",
                    Flags = SF.AQuestAlias.Flag.Optional | SF.AQuestAlias.Flag.AllowReserved |
                            SF.AQuestAlias.Flag.AllowDead | SF.AQuestAlias.Flag.AllowDisabled,
                    ForcedReference = new FormLinkNullable<SF.IPlacedGetter>(raiderRefs[ri].FormKey),
                    PackageData =
                    {
                        new FormLink<SF.IPackageGetter>(raiderCombatPack.FormKey),
                        new FormLink<SF.IPackageGetter>(raiderSandboxPack.FormKey),
                    },
                });
            }

            // 2g / B6: Preston 3-exchange Starfield Scene on FO4SF_Min00 at stage 30 -> end stage 35 (advances to 40 by=info)
            string pGreet = "Synthetic Concord greeting.";
            var pChoices = SyntheticPrestonChoices.Select((c, idx) =>
                (c.Prompt, c.Reply, EndStage: idx == 2 ? (short)35 : (short)-1, Goodbye: idx == 2, Wem: 0u)).ToArray();
            if (pts.TryGetProperty("preston_talk", out var ptEl) && ptEl.ValueKind == JsonValueKind.Object)
            {
                if (ptEl.TryGetProperty("greeting", out var gEl) && gEl.GetString() is { Length: > 0 } gs) pGreet = gs;
                if (ptEl.TryGetProperty("choices", out var chEl) && chEl.ValueKind == JsonValueKind.Array && chEl.GetArrayLength() == 3)
                {
                    int ci = 0;
                    foreach (var ce in chEl.EnumerateArray())
                    {
                        var pr = ce.GetProperty("prompt").GetString() ?? SyntheticPrestonChoices[ci].Prompt;
                        var rp = ce.GetProperty("reply").GetString() ?? SyntheticPrestonChoices[ci].Reply;
                        pChoices[ci] = (pr, rp, ci == 2 ? (short)35 : (short)-1, ci == 2, 0u);
                        ci++;
                    }
                }
            }
            prestonScene = BuildTopScene(
                modKey, quest, npc.FormKey,
                QuestStageCond(quest.FormKey, SF.CompareOperator.EqualTo, 30f),
                PrestonTalkSceneId, PrestonTalkSceneEdid,
                PrestonGreetTopicId, PrestonGreetTopicEdid,
                PrestonGreetInfoId, PrestonGreetInfoEdid,
                pGreet, 0u,
                FirstPrestonChoiceTopicId, FirstPrestonChoiceInfoId,
                FirstPrestonReplyTopicId, FirstPrestonReplyInfoId,
                "FO4SF_Min00_Preston", 50f, pChoices);
        }

        var script = new SF.ScriptEntry { Name = ScriptName, Flags = SF.ScriptEntry.Flag.Local };
        SF.ScriptObjectProperty Obj(string name, FormKey fk) => new()
        {
            Name = name, Flags = SF.ScriptProperty.Flag.Edited, Object = new FormLink<SF.IStarfieldMajorRecordGetter>(fk), Alias = -1, Unused = 0,
        };
        SF.ScriptObjectProperty SanctuaryObjProp(string name, FormKey fk) => new()
        {
            Name = name, Flags = SF.ScriptProperty.Flag.Edited, Object = new FormLink<SF.IStarfieldMajorRecordGetter>(fk), Alias = -1, Unused = 0,
        };
        void MissionProps(SF.ScriptEntry e)
        {
            e.Properties.Add(Obj("Preston", prestonRef.FormKey));
            var list = new SF.ScriptObjectListProperty { Name = "Raiders", Flags = SF.ScriptProperty.Flag.Edited };
            foreach (var r in raiderRefs) list.Objects.Add(Obj("", r.FormKey));
            e.Properties.Add(list);
            e.Properties.Add(Obj("Credits", credits.FormKey));
        }
        MissionProps(script);
        if (prestonScene is not null)
            script.Properties.Add(Obj("PrestonTalkScene", prestonScene.FormKey));

        SF.QuestAdapter Adapter(SF.ScriptEntry entry)
        {
            var vm = new SF.QuestAdapter
            {
                Version = 6, ObjectFormat = 2, ExtraBindDataVersion = 3,
                Script = new SF.ScriptEntry { Name = "", Flags = SF.ScriptEntry.Flag.Local },
            };
            vm.Scripts.Add(entry);
            return vm;
        }
        quest.VirtualMachineAdapter = Adapter(script);

        SF.Quest? keeper = null;
        SF.Quest? codsworthQuest = null;
        if (codsRef is not null && cods is not null)
        {
            // 2b: FO4SF_CodsworthKeeper (0x814) — non-StartGameEnabled (started via StartNoWait at FO4SFNewGame stage 200)
            keeper = new SF.Quest(new FormKey(modKey, KeeperQuestId), SF.StarfieldRelease.Starfield)
            {
                EditorID = KeeperEdid, FormVersion = 581, Version2 = 12,
                Data = new SF.QuestData { Flags = SF.Quest.Flag.StartsEnabled | (SF.Quest.Flag)0x10000, Priority = 50 },
            };
            var ks = new SF.ScriptEntry { Name = ScriptName, Flags = SF.ScriptEntry.Flag.Local };
            MissionProps(ks);
            ks.Properties.Add(Obj("Codsworth", codsRef.FormKey));
            ks.Properties.Add(new SF.ScriptBoolProperty { Name = "KeeperOnly", Flags = SF.ScriptProperty.Flag.Edited, Data = true });
            keeper.VirtualMachineAdapter = Adapter(ks);

            // 2h & 2b: FO4SF_Codsworth01 (0x816) — MQ102-lite 4-choice Sanctuary quest, non-StartGameEnabled
            string cqName = "Synthetic Sanctuary Inquiry";
            string cqObj10 = "Speak with the household robot";
            string cqGreet = "Synthetic robot greeting.";
            var mqWem = codsworthMqVoice is null ? null : LoadMqVoice(codsworthMqVoice);
            var cqChoices = SyntheticCodsworthChoices.Select((c, idx) =>
                (c.Prompt, c.Reply, EndStage: CodsworthChoiceEndStages[idx], Goodbye: idx == 3, Wem: mqWem?.ChoiceReplyWems[idx] ?? 0u)).ToArray();

            if (pts.TryGetProperty("codsworth_quest", out var cqEl) && cqEl.ValueKind == JsonValueKind.Object)
            {
                if (cqEl.TryGetProperty("name", out var nEl) && nEl.GetString() is { Length: > 0 } ns) cqName = ns;
                if (cqEl.TryGetProperty("objective_10", out var oEl) && oEl.GetString() is { Length: > 0 } os) cqObj10 = os;
                if (cqEl.TryGetProperty("greeting", out var gEl) && gEl.GetString() is { Length: > 0 } gs) cqGreet = gs;
                if (cqEl.TryGetProperty("choices", out var chEl) && chEl.ValueKind == JsonValueKind.Array && chEl.GetArrayLength() == 4)
                {
                    int ci = 0;
                    foreach (var ce in chEl.EnumerateArray())
                    {
                        var pr = ce.GetProperty("prompt").GetString() ?? SyntheticCodsworthChoices[ci].Prompt;
                        var rp = ce.GetProperty("reply").GetString() ?? SyntheticCodsworthChoices[ci].Reply;
                        cqChoices[ci] = (pr, rp, CodsworthChoiceEndStages[ci], ci == 3, mqWem?.ChoiceReplyWems[ci] ?? 0u);
                        ci++;
                    }
                }
            }

            codsworthQuest = new SF.Quest(new FormKey(modKey, CodsworthQuestId), SF.StarfieldRelease.Starfield)
            {
                EditorID = CodsworthQuestEdid, Name = cqName, FormVersion = 581, Version2 = 12,
                Data = new SF.QuestData
                {
                    Flags = SF.Quest.Flag.StartsEnabled | SF.Quest.Flag.AllowRepeatedStages | SF.Quest.Flag.DisplaysInHud |
                            SF.Quest.Flag.HasDialogueData | (SF.Quest.Flag)0x10000,
                    Priority = 55,
                },
            };
            codsworthQuest.QuestType.SetTo(qtyp.FormKey);
            foreach (var stIdx in CodsworthQuestStages)
            {
                var st = new SF.QuestStage { Index = stIdx };
                if (stIdx == 100) st.LogEntries.Add(new SF.QuestLogEntry { Flags = SF.QuestLogEntry.Flag.CompleteQuest });
                codsworthQuest.Stages.Add(st);
            }
            (codsworthQuest.Aliases ??= new ExtendedList<SF.AQuestAlias>()).Add(new SF.QuestReferenceAlias
            {
                ID = CodsworthAlias, Name = "Codsworth",
                Flags = SF.AQuestAlias.Flag.AllowDisabled | SF.AQuestAlias.Flag.AllowReserved | SF.AQuestAlias.Flag.UsesStoredText,
                ForcedReference = new FormLinkNullable<SF.IPlacedGetter>(codsRef.FormKey),
            });
            var cqObj = new SF.QuestObjective { Index = 10, DisplayText = cqObj10 };
            cqObj.Targets.Add(new SF.QuestObjectiveTarget { AliasID = CodsworthAlias });
            codsworthQuest.Objectives.Add(cqObj);

            BuildTopScene(
                modKey, codsworthQuest, cods.FormKey,
                QuestStageCond(codsworthQuest.FormKey, SF.CompareOperator.LessThan, 100f),
                CodsworthSceneId, CodsworthSceneEdid,
                CodsworthGreetTopicId, CodsworthGreetTopicEdid,
                CodsworthGreetInfoId, CodsworthGreetInfoEdid,
                cqGreet, mqWem?.GreetingWem ?? 0u,
                FirstCodsworthChoiceTopicId, FirstCodsworthChoiceInfoId,
                FirstCodsworthReplyTopicId, FirstCodsworthReplyInfoId,
                "FO4SF_Codsworth01", 55f, cqChoices);

            codsworthQuest.VirtualMachineAdapter = Adapter(new SF.ScriptEntry { Name = CodsworthScriptName, Flags = SF.ScriptEntry.Flag.Local });
        }

        var lines = codsworthVoice is null ? [] : VoiceLines(codsworthVoice);
        if (lines.Count > 0)
        {
            if (cods is null) throw new Refusal("--codsworth-voice needs Codsworth (drop --no-codsworth)");
            var dial = new SF.DialogTopic(new FormKey(modKey, CodsworthDialId), SF.StarfieldRelease.Starfield)
            {
                EditorID = CodsworthDialEdid, Quest = new FormLink<SF.IQuestGetter>(quest.FormKey), Priority = 50,
                Category = SF.DialogTopic.CategoryEnum.Misc, Subtype = SF.DialogTopic.SubtypeEnum.Hello,
                SubtypeName = SF.DialogTopic.SubtypeNameEnum.Hello,
            };
            uint id = FirstCodsworthInfoId;
            foreach (var l in lines)
            {
                var info = new SF.DialogResponses(new FormKey(modKey, id++), SF.StarfieldRelease.Starfield)
                {
                    EditorID = $"FO4SF_Codsworth_{l.Fo4Info}_{l.Response}",
                    Flags = new SF.DialogResponseFlags { Flags = (short)SF.DialogResponses.Flag.Random },
                };
                info.Responses.Add(new SF.DialogResponse { ResponseText = l.Text, WEMFile = l.Wem });
                info.Conditions.AddRange(VoiceConditions(cods.FormKey, l.Sex));
                dial.Responses.Add(info);
                (dial.TopicInfoList ??= new()).Add(new FormLink<SF.IDialogResponsesGetter>(info.FormKey));
            }
            quest.DialogTopics.Add(dial);
        }

        mod.Quests.Add(quest);
        if (keeper is not null) mod.Quests.Add(keeper);

        // Test-only follow quest (0x815, empty optional alias, hidden from HUD)
        var com = new SF.Quest(new FormKey(modKey, ComQuestId), SF.StarfieldRelease.Starfield)
        {
            EditorID = ComQuestEdid, FormVersion = 581, Version2 = 12,
            Data = new SF.QuestData { Flags = SF.Quest.Flag.StartGameEnabled, Priority = 60 },
        };
        (com.Aliases ??= new ExtendedList<SF.AQuestAlias>()).Add(new SF.QuestReferenceAlias
        {
            ID = ComAlias, Name = ComAliasName,
            Flags = SF.AQuestAlias.Flag.Optional | SF.AQuestAlias.Flag.AllowReserved,
            PackageData = { new FormLink<SF.IPackageGetter>(new FormKey(SfEsm, FollowPackageId)) },
        });
        mod.Quests.Add(com);
        if (codsworthQuest is not null) mod.Quests.Add(codsworthQuest);

        // 2k & 2b: FO4SF_Sanctuary01 (0x817) — First Settlement workbench objective, non-StartGameEnabled
        string sqName = "First Settlement", sqObj10 = "Activate the Sanctuary workbench";
        if (pts.TryGetProperty("sanctuary_quest", out var sqEl) && sqEl.ValueKind == JsonValueKind.Object)
        {
            if (sqEl.TryGetProperty("name", out var nEl) && nEl.GetString() is { Length: > 0 } ns) sqName = ns;
            if (sqEl.TryGetProperty("objective_10", out var oEl) && oEl.GetString() is { Length: > 0 } os) sqObj10 = os;
        }
        var sanctuaryQuest = new SF.Quest(new FormKey(modKey, SanctuaryQuestId), SF.StarfieldRelease.Starfield)
        {
            EditorID = SanctuaryQuestEdid, Name = sqName, FormVersion = 581, Version2 = 12,
            Data = new SF.QuestData
            {
                Flags = SF.Quest.Flag.StartsEnabled | SF.Quest.Flag.AllowRepeatedStages | SF.Quest.Flag.DisplaysInHud |
                        SF.Quest.Flag.RunOnce | (SF.Quest.Flag)0x10000,
                Priority = 50,
            },
        };
        sanctuaryQuest.QuestType.SetTo(qtyp.FormKey);
        foreach (var stIdx in SanctuaryQuestStages)
        {
            var st = new SF.QuestStage { Index = stIdx };
            if (stIdx == 100) st.LogEntries.Add(new SF.QuestLogEntry { Flags = SF.QuestLogEntry.Flag.CompleteQuest });
            sanctuaryQuest.Stages.Add(st);
        }
        (sanctuaryQuest.Aliases ??= new ExtendedList<SF.AQuestAlias>()).Add(new SF.QuestReferenceAlias
        {
            ID = SanctuaryBenchAlias, Name = "SanctuaryWorkbench",
            Flags = SF.AQuestAlias.Flag.Optional | SF.AQuestAlias.Flag.AllowReserved | SF.AQuestAlias.Flag.AllowDisabled,
        });
        var sqObj = new SF.QuestObjective { Index = 10, DisplayText = sqObj10 };
        sqObj.Targets.Add(new SF.QuestObjectiveTarget { AliasID = SanctuaryBenchAlias });
        sanctuaryQuest.Objectives.Add(sqObj);
        var sqScript = new SF.ScriptEntry { Name = SanctuaryScriptName, Flags = SF.ScriptEntry.Flag.Local };
        sqScript.Properties.Add(SanctuaryObjProp("XMarkerBase", xMarker.FormKey));
        sanctuaryQuest.VirtualMachineAdapter = Adapter(sqScript);
        mod.Quests.Add(sanctuaryQuest);

        uint maxId = Math.Max(SanctuaryQuestId + 1, MinutemenFactionId + 1);
        if (alias) maxId = Math.Max(maxId, FirstPrestonReplyInfoId + 3);
        if (codsworthQuest is not null) maxId = Math.Max(maxId, FirstCodsworthReplyInfoId + 4);
        if (lines.Count > 0) maxId = Math.Max(maxId, FirstCodsworthInfoId + (uint)lines.Count);
        mod.ModHeader.Stats.NextFormID = maxId;

        Directory.CreateDirectory(outDir);
        var path = Path.Combine(outDir, plugin);
        var lo = new[] { SfEsm, m.Core.ModKey, m.Raider.ModKey };
        mod.BeginWrite.ToPath(path).WithLoadOrder(lo)
            .WithKnownMasters(lo.Select(k => new KeyedMasterStyle(k, MasterStyle.Full)).ToArray()).Write();
        Console.WriteLine($"wrote {path} ({new FileInfo(path).Length:N0} bytes): QUST {QuestEdid} {quest.FormKey} \"{quest.Name}\" " +
                          $"({Stages.Length} stages, {quest.Objectives.Count} objectives, {(alias ? "alias PrestonGarvey + 3-choice scene" : "no alias")}); " +
                          $"NPC_ {PrestonEdid} {npc.FormKey} \"{npc.Name}\" (HumanRace + {SfPrestonOutfitEdid} + {SfPrestonWeaponEdid}); " +
                          $"ACHR Preston {prestonRef.FormKey} at {Show(prestonRef.Position)}; " +
                          $"{raiderRefs.Count} raider ACHR(s) of {raiderNpc.EditorID}; " +
                          (cods is null ? "no Codsworth; " : $"NPC_ {CodsworthEdid} {cods.FormKey} \"{cods.Name}\" race {CodsworthRaceEdid} voice {CodsworthVoiceEdid}, ACHR {codsRef!.FormKey} at {Show(codsRef.Position)}, QUST {CodsworthQuestEdid} 0x{CodsworthQuestId:X}" +
                                            (codsworthModel is null ? "; " : $", skin {CodsworthSkinEdid} model {codsworthModel}; ")) +
                          $"QUST {SanctuaryQuestEdid} {sanctuaryQuest.FormKey}; " +
                          $"QUST {ComQuestEdid} {com.FormKey} alias {ComAliasName} package {FollowPackageEdid} {FollowPackageId:X6}; " +
                          $"WRLD {w.EditorID} {w.FormKey} persistent CELL {cell.FormKey} overridden");
        return 0;
    }

    static string Show(P3Float p) => $"({F(p.X)}, {F(p.Y)}, {F(p.Z)})";

    // ---------------------------------------------------------------- check

    public record VoiceLine(string Fo4Info, int Response, string Text, uint Wem, string? Sex);

    public static List<VoiceLine> VoiceLines(string path)
    {
        using var doc = JsonDocument.Parse(File.ReadAllText(path));
        var lines = doc.RootElement.EnumerateArray().Select(e => new VoiceLine(
            e.GetProperty("info").GetString()!, e.GetProperty("response").GetInt32(), e.GetProperty("text").GetString()!,
            uint.Parse(e.GetProperty("wem").GetString()!, NumberStyles.HexNumber, CultureInfo.InvariantCulture),
            e.TryGetProperty("sex", out var sx) && sx.ValueKind == JsonValueKind.String ? sx.GetString() : null)).ToList();
        if (lines.Count == 0 || lines.Count > 0xDF) throw new Refusal($"{path}: {lines.Count} voice lines");
        if (lines.Select(l => l.Wem).Distinct().Count() != lines.Count) throw new Refusal($"{path}: two lines share a wem id");
        if (lines.Any(l => string.IsNullOrWhiteSpace(l.Text) || l.Sex is not (null or "male" or "female"))) throw new Refusal($"{path}: a line has no text or a bad sex");
        return lines;
    }

    public static List<SF.Condition> VoiceConditions(FormKey codsworth, string? sex)
    {
        var id = new SF.GetIsIDConditionData { RunOnType = SF.Condition.RunOnType.Subject };
        id.FirstParameter.Link.SetTo(codsworth);
        var list = new List<SF.Condition> { new SF.ConditionFloat { CompareOperator = SF.CompareOperator.EqualTo, ComparisonValue = 1, Data = id } };
        if (sex is not null)
            list.Add(new SF.ConditionFloat
            {
                CompareOperator = SF.CompareOperator.EqualTo, ComparisonValue = 1,
                Data = new SF.GetIsSexConditionData { RunOnType = SF.Condition.RunOnType.Target, FirstParameter = sex == "male" ? MaleFemaleGender.Male : MaleFemaleGender.Female },
            });
        return list;
    }

    static string CondSig(SF.IConditionGetter c)
    {
        string param = c.Data switch
        {
            SF.IGetIsIDConditionDataGetter g => g.FirstParameter.Link.FormKey.ToString(),
            SF.IGetIsSexConditionDataGetter g => g.FirstParameter.ToString(),
            SF.IGetStageConditionDataGetter g => g.FirstParameter.Link.FormKey.ToString(),
            _ => "unsupported",
        };
        return $"{c.Data.GetType().Name.Replace("BinaryOverlay", "")} {c.Data.RunOnType} {c.CompareOperator} {(c as SF.IConditionFloatGetter)?.ComparisonValue} {c.Flags} {param}";
    }

    public static string ModelPath(string vanilla, string rel)
    {
        rel = rel.Replace('/', '\\').TrimStart('\\');
        if (rel.StartsWith("meshes\\", StringComparison.OrdinalIgnoreCase)) rel = rel[7..];
        return vanilla.StartsWith("meshes\\", StringComparison.OrdinalIgnoreCase) ? vanilla[..7] + rel : rel;
    }

    public static int Check(string pluginPath, string sfPath, string corePath, string raiderPath, bool alias, bool codsworth = true,
                            string? codsworthModel = null, string? codsworthVoice = null, string? codsworthMqVoice = null)
    {
        using var m = Open(sfPath, corePath, raiderPath);
        using var plug = SF.StarfieldMod.CreateFromBinaryOverlay(pluginPath, SF.StarfieldRelease.Starfield, Styles(SfEsm, m.Core.ModKey, m.Raider.ModKey));
        var key = plug.ModKey;
        var problems = new List<string>();
        void Need(bool ok, string what) { if (!ok) problems.Add(what); }
        var masters = plug.ModHeader.MasterReferences.Select(x => x.Master.FileName.String).ToList();
        Console.WriteLine($"{key}: header {plug.ModHeader.Flags}, masters [{string.Join(", ", masters)}], next 0x{plug.ModHeader.Stats.NextFormID:X}, " +
                          $"{plug.Quests.Count} QUST, {plug.Npcs.Count} NPC_, {plug.Races.Count} RACE, {plug.VoiceTypes.Count} VTYP, {plug.Worldspaces.Count} WRLD");
        Need(plug.ModHeader.Flags.HasFlag(SF.StarfieldModHeader.HeaderFlag.Master), "not flagged as a master");
        Need(masters.SequenceEqual(new[] { "Starfield.esm", m.Core.ModKey.FileName.String, m.Raider.ModKey.FileName.String }), "masters are not Starfield, core, raider");

        // 2g: Check Preston's dedicated HumanRace NPC_
        var npc = plug.Npcs.FirstOrDefault(n => n.FormKey == new FormKey(key, PrestonNpcId));
        var minutemen = plug.Factions.FirstOrDefault(f => f.FormKey == new FormKey(key, MinutemenFactionId));
        Need(minutemen is { EditorID: MinutemenFactionEdid } && minutemen.Relations.Count == 1 &&
             minutemen.Relations[0].Target.FormKey == new FormKey(SfEsm, PlayerFactionId) && minutemen.Relations[0].Reaction == SF.CombatReaction.Ally,
             $"FACT 0x{MinutemenFactionId:X} is not {MinutemenFactionEdid} with the one relation Ally to PlayerFaction");
        Need(npc is { EditorID: PrestonEdid } && npc.Flags.HasFlag(SF.Npc.Flag.Essential) && npc.Flags.HasFlag(SF.Npc.Flag.Unique) &&
             !npc.Flags.HasFlag(SF.Npc.Flag.Respawn) && npc.Factions.Count == 1 && npc.Factions[0].Faction.FormKey == minutemen?.FormKey,
             $"NPC_ 0x801 is not an essential unique FO4_PrestonGarvey in {MinutemenFactionEdid} only");
        Need(npc is not null && npc.Race.FormKey == new FormKey(SfEsm, SfHumanRaceId), "Preston's race is not Starfield.esm HumanRace (0x00347D)");
        Need(npc is not null && m.Sf.VoiceTypes.TryGetValue(npc.Voice.FormKey, out var pv) && pv.EditorID == SfPrestonVoiceEdid &&
             pv.Flags.HasFlag(SF.VoiceType.Flag.AllowDefaultDialog),
             $"Preston's VoiceType is not {SfPrestonVoiceEdid} with AllowDefaultDialog");
        Need(npc is not null && npc.DefaultOutfit.FormKey == new FormKey(SfEsm, SfPrestonOutfitId),
             $"Preston's DefaultOutfit is not {SfPrestonOutfitEdid} ({SfPrestonOutfitId:X6})");
        var prestonItems = npc?.Items?.Select(i => i.Item.Item.FormKey).ToHashSet() ?? [];
        Need(prestonItems.Contains(new FormKey(SfEsm, SfPrestonWeaponId)) && prestonItems.Contains(new FormKey(SfEsm, SfPrestonAmmoId)),
             $"Preston lacks {SfPrestonWeaponEdid} ({SfPrestonWeaponId:X6}) or {SfPrestonAmmoEdid} ({SfPrestonAmmoId:X6})");
        Need(npc is not null && npc.CalcMinLevel >= 10, "Preston CalcMinLevel < 10");

        var world = FindWorld(m.Core, World);
        var w = plug.Worldspaces.FirstOrDefault();
        Need(w is not null && w.FormKey == world.FormKey && w.SubCells.Count == 0, "the WRLD override is not the core world without exterior cells");
        var cell = w?.TopCell;
        Need(cell is not null && cell.FormKey == world.TopCell?.FormKey, "the persistent cell override is not the core's");
        var refs = cell?.Persistent.OfType<SF.IPlacedNpcGetter>().ToList() ?? new();
        Need(cell is null || cell.Persistent.Count == refs.Count, "the persistent cell holds something other than our ACHRs");
        foreach (var r in refs)
        {
            Console.WriteLine($"  ACHR {r.FormKey.ID:X6} {r.EditorID} base {r.Base.FormKey} at {Show(r.Position)} flags 0x{r.MajorRecordFlagsRaw:X}");
            Need((r.MajorRecordFlagsRaw & 0x400) != 0, $"ACHR {r.FormKey.ID:X6} is not persistent");
            Need(m.Cache.TryResolve<SF.INpcGetter>(r.Base.FormKey, out _) || r.Base.FormKey.ModKey == key, $"ACHR {r.FormKey.ID:X6}: base {r.Base.FormKey} does not resolve");
        }
        var preston = refs.FirstOrDefault(r => r.FormKey.ID == PrestonRefId);
        Need(preston is not null && preston.Base.FormKey == npc?.FormKey, "ACHR 0x802 is not Preston");
        var raiders = refs.Where(r => r.FormKey.ID >= FirstRaiderRefId && r.FormKey.ID < CodsworthNpcId).ToList();
        var cods = plug.Npcs.FirstOrDefault(n => n.FormKey == new FormKey(key, CodsworthNpcId));
        var codsRef = refs.FirstOrDefault(r => r.FormKey.ID == CodsworthRefId);
        var codsRace = plug.Races.FirstOrDefault(r => r.FormKey == new FormKey(key, CodsworthRaceId));
        var codsVoice = plug.VoiceTypes.FirstOrDefault(v => v.FormKey == new FormKey(key, CodsworthVoiceId));

        if (!codsworth)
        {
            Need(cods is null && codsRef is null && codsRace is null && codsVoice is null, "a --no-codsworth build carries Codsworth records");
        }
        else
        {
            Console.WriteLine($"  NPC_ {cods?.EditorID} \"{cods?.Name?.String}\" race {cods?.Race.FormKey} voice {cods?.Voice.FormKey} factions {cods?.Factions.Count} scripts {(cods?.VirtualMachineAdapter is null ? 0 : 1)}");
            Need(cods is { EditorID: CodsworthEdid } && cods.Flags.HasFlag(SF.Npc.Flag.Essential) && cods.Flags.HasFlag(SF.Npc.Flag.Unique) &&
                 !cods.Flags.HasFlag(SF.Npc.Flag.Respawn) && cods.Factions.Count == 0 &&
                 cods.VirtualMachineAdapter is null && !string.IsNullOrWhiteSpace(cods.Name?.String),
                 "NPC_ 0x810 is not an essential, unique, non-respawning, named FO4_Codsworth without factions and scripts");
            Need(codsRace is { EditorID: CodsworthRaceEdid } && codsRace.Flags.HasFlag(SF.Race.Flag.AllowPcDialog) &&
                 cods?.Race.FormKey == codsRace.FormKey,
                 $"Codsworth lacks local RACE {CodsworthRaceEdid} (0x{CodsworthRaceId:X}) with AllowPcDialog");
            Need(codsVoice is { EditorID: CodsworthVoiceEdid } && codsVoice.Flags.HasFlag(SF.VoiceType.Flag.AllowDefaultDialog) &&
                 cods?.Voice.FormKey == codsVoice.FormKey,
                 $"Codsworth lacks local VTYP {CodsworthVoiceEdid} (0x{CodsworthVoiceId:X}) with AllowDefaultDialog");
            Need(codsRef is not null && codsRef.Base.FormKey == cods?.FormKey, "ACHR 0x811 is not Codsworth");
        }

        var arma = plug.ArmorAddons.FirstOrDefault(x => x.FormKey == new FormKey(key, CodsworthArmaId));
        var skin = plug.Armors.FirstOrDefault(x => x.FormKey == new FormKey(key, CodsworthSkinId));
        if (codsworth && codsworthModel is not null)
        {
            var files = new[] { arma?.WorldModel?.Male, arma?.WorldModel?.Female }.Select(g => g?.File?.GivenPath).OfType<string>().Where(f => f.Length > 0).ToList();
            Console.WriteLine($"  ARMA {arma?.EditorID} race {arma?.Race.FormKey} models [{string.Join(", ", files)}]; ARMO {skin?.EditorID} " +
                              $"armatures [{string.Join(", ", skin?.Armatures.Select(x => x.ArmorAddon.FormKey.ToString()) ?? [])}]");
            Need(arma is { EditorID: CodsworthArmaEdid } && files.Count > 0 &&
                 files.All(f => string.Equals(ModelPath("", f), ModelPath("", codsworthModel), StringComparison.OrdinalIgnoreCase)),
                 $"ARMA 0x{CodsworthArmaId:X} is not {CodsworthArmaEdid} with the model {codsworthModel}");
            Need(arma is not null && arma.Race.FormKey == codsRace?.FormKey, "Codsworth's ARMA race is not FO4SF_CodsworthRace");
            Need(skin is { EditorID: CodsworthSkinEdid } && skin.Armatures.Count == 1 && skin.Armatures[0].ArmorAddon.FormKey == arma?.FormKey,
                 $"ARMO 0x{CodsworthSkinId:X} is not {CodsworthSkinEdid} with only his ARMA");
            Need(cods?.Skin.FormKey == skin?.FormKey && skin is not null, "Codsworth's skin (WNAM) is not his ARMO");
        }
        else Need(arma is null && skin is null && (cods is null || cods.Skin.FormKey != new FormKey(key, CodsworthSkinId)),
                  "a build without --codsworth-model carries Codsworth's ARMA or ARMO");

        Need(refs.All(r => r.FormKey.ID < CodsworthNpcId || r.FormKey.ID == CodsworthRefId), "an ACHR outside Preston, the raiders and Codsworth");
        Need(raiders.Count > 0 && raiders.All(r => r.Base.FormKey == new FormKey(m.Raider.ModKey, RaiderId)), "no raider ACHR on FO4_LvlRaider");

        static bool NonStartGameReady(SF.IQuestGetter q) =>
            q.Data is not null && !q.Data.Flags.HasFlag(SF.Quest.Flag.StartGameEnabled) &&
            q.Data.Flags.HasFlag(SF.Quest.Flag.StartsEnabled) && (((uint)q.Data.Flags & 0x10000u) != 0);

        // Check FO4SF_Min00 (0x800)
        var q = plug.Quests.FirstOrDefault(x => x.FormKey == new FormKey(key, QuestId));
        if (q is null) problems.Add("no QUST 0x800");
        else
        {
            Console.WriteLine($"  QUST {q.EditorID} \"{q.Name?.String}\" flags {q.Data?.Flags} stages [{string.Join(",", q.Stages.Select(s => s.Index))}] " +
                              $"objectives [{string.Join("; ", q.Objectives.Select(o => $"{o.Index} \"{o.DisplayText?.String}\" targets {o.Targets.Count}"))}] aliases {q.Aliases?.Count ?? 0} scenes {q.Scenes.Count}");
            Need(q.EditorID == QuestEdid && NonStartGameReady(q), "FO4SF_Min00 must NOT be StartGameEnabled and must carry StartsEnabled | 0x10000");
            Need(q.QuestType.FormKey == new FormKey(SfEsm, QuestTypeSideId), $"the quest's QuestType is not {QuestTypeSideEdid}");
            Need(q.Stages.Select(s => s.Index).SequenceEqual(Stages), "stages differ from the script's");

            var dials = q.DialogTopics.ToList();
            var helloDial = dials.FirstOrDefault(d => d.FormKey == new FormKey(key, CodsworthDialId));
            int expectedSceneDials = alias ? 7 : 0; // 1 greeting + 3 choice + 3 reply
            if (codsworthVoice is null)
            {
                Need(helloDial is null && dials.Count == expectedSceneDials, $"unexpected DIAL count {dials.Count} without --codsworth-voice (expected {expectedSceneDials})");
            }
            else
            {
                var want = VoiceLines(codsworthVoice);
                Console.WriteLine($"  DIAL {helloDial?.EditorID} {helloDial?.Category}/{helloDial?.Subtype}/{helloDial?.SubtypeName} infos {helloDial?.Responses.Count}");
                Need(dials.Count == expectedSceneDials + 1 && helloDial is { EditorID: CodsworthDialEdid, Subtype: SF.DialogTopic.SubtypeEnum.Hello, SubtypeName: SF.DialogTopic.SubtypeNameEnum.Hello }
                     && helloDial.Quest.FormKey == q.FormKey, $"DIAL 0x{CodsworthDialId:X} is not his Hello topic in the quest");
                var infos = helloDial?.Responses.ToList() ?? [];
                Need(infos.Count == want.Count && (helloDial!.TopicInfoList ?? []).Select(t => t.FormKey).SequenceEqual(infos.Select(i => i.FormKey)), "his INFOs differ from voice.json or the topic's list");
                for (int i = 0; i < Math.Min(infos.Count, want.Count); i++)
                {
                    var info = infos[i];
                    var r = info.Responses.Count == 1 ? info.Responses[0] : null;
                    bool condsOk = cods is not null && info.Conditions.Select(CondSig).SequenceEqual(VoiceConditions(cods.FormKey, want[i].Sex).Select(CondSig));
                    Need(info.FormKey.ID == FirstCodsworthInfoId + i && r is not null && r.WEMFile == want[i].Wem && r.ResponseText?.String == want[i].Text
                         && condsOk, $"INFO 0x{FirstCodsworthInfoId + i:X} is not line {want[i].Fo4Info}_{want[i].Response}");
                }
            }
            Need(q.Stages.LastOrDefault()?.LogEntries.Any(l => l.Flags?.HasFlag(SF.QuestLogEntry.Flag.CompleteQuest) == true) == true, "stage 200 does not complete the quest");
            Need(q.Objectives.Select(o => o.Index).SequenceEqual(Objectives.Select(o => o.Index)), "objectives differ from the script's");
            Need(q.Objectives.All(o => !string.IsNullOrWhiteSpace(o.DisplayText?.String) && !o.DisplayText!.String!.Contains('<')), "an objective has no text or an FO4 text token");

            if (alias)
            {
                var refAliases = (q.Aliases ?? new List<SF.IAQuestAliasGetter>()).OfType<SF.IQuestReferenceAliasGetter>().ToList();
                var al = refAliases.FirstOrDefault(a => a.ID == PrestonAlias);
                Need(al is not null && al.ForcedReference.FormKey == preston?.FormKey, "alias 0 is not forced to Preston's ACHR");
                var wantRaiderPacks = new[]
                {
                    new FormKey(SfEsm, RaiderCombatPackageId),
                    new FormKey(SfEsm, RaiderSandboxPackageId),
                };
                Need(m.Cache.TryResolve<SF.IPackageGetter>(wantRaiderPacks[0], out var rcp) && rcp.EditorID == RaiderCombatPackageEdid &&
                     m.Cache.TryResolve<SF.IPackageGetter>(wantRaiderPacks[1], out var rsp) && rsp.EditorID == RaiderSandboxPackageEdid,
                     $"Starfield.esm lacks {RaiderCombatPackageEdid} ({RaiderCombatPackageId:X6}) or {RaiderSandboxPackageEdid} ({RaiderSandboxPackageId:X6})");
                Need(refAliases.Count == 1 + raiders.Count, $"expected {1 + raiders.Count} reference aliases (Preston + {raiders.Count} raiders), got {refAliases.Count}");
                for (int ri = 0; ri < raiders.Count; ri++)
                {
                    var ral = refAliases.FirstOrDefault(a => a.ID == (uint)(1 + ri));
                    Need(ral is not null && ral.ForcedReference.FormKey == raiders[ri].FormKey &&
                         ral.PackageData.Select(p => p.FormKey).SequenceEqual(wantRaiderPacks),
                         $"raider alias {1 + ri} is not forced to raider {ri} with [{RaiderCombatPackageEdid}, {RaiderSandboxPackageEdid}]");
                }
                Need(q.Objectives.Where((o, i) => Objectives[i].TargetsPreston).All(o => o.Targets.Count == 1 && o.Targets[0].AliasID == PrestonAlias),
                     "Preston's objectives do not target alias 0");
                Need(q.Scenes.Count == 1 && q.Scenes[0].FormKey == new FormKey(key, PrestonTalkSceneId), "FO4SF_Min00 lacks Preston talk scene 0x900");
                if (q.Scenes.Count == 1)
                {
                    var pscn = q.Scenes[0];
                    Need(((uint)(pscn.Flags ?? 0) & 0x2814u) == 0x2814u, "Preston talk scene lacks 0x2814 flags");
                    var pda = pscn.Actions?.OfType<SF.IPlayerDialogueSceneActionGetter>().FirstOrDefault();
                    Need(pda is not null && pda.DialogueList.Count == 3, "Preston talk scene does not carry 3 PlayerDialogueSceneAction exchanges");
                    if (pda is not null && pda.DialogueList.Count == 3)
                    {
                        var endReply = q.DialogTopics.FirstOrDefault(t => t.FormKey == pda.DialogueList[2].NpcResponse.FormKey)?.Responses.FirstOrDefault();
                        Need(endReply?.SetParentQuestStage?.OnEnd == 35 && endReply.Flags?.Flags == 1,
                             "Preston talk scene exchange 3 does not end conversation at stage 35");
                    }
                }
            }
            else
            {
                Need((q.Aliases?.Count ?? 0) == 0 && q.Objectives.All(o => o.Targets.Count == 0) && q.Scenes.Count == 0,
                     "--no-alias build carries an alias, target, or scene");
            }

            var s = q.VirtualMachineAdapter?.Scripts.FirstOrDefault(x => x.Name == ScriptName);
            if (s is null) problems.Add($"script {ScriptName} not attached");
            else
            {
                var props = s.Properties.ToDictionary(p => p.Name);
                Console.WriteLine($"  script {s.Name}: " + string.Join(", ", props.Keys));
                Need(props.TryGetValue("Preston", out var pp) && pp is SF.IScriptObjectPropertyGetter po && po.Object.FormKey == preston?.FormKey, "property Preston");
                Need(props.TryGetValue("Credits", out var cp) && cp is SF.IScriptObjectPropertyGetter co && co.Object.FormKey == new FormKey(SfEsm, CreditsId), "property Credits");
                Need(props.TryGetValue("Raiders", out var rp) && rp is SF.IScriptObjectListPropertyGetter rl &&
                     rl.Objects.Select(o => o.Object.FormKey).SequenceEqual(raiders.Select(r => r.FormKey)), "property Raiders lists the raider ACHRs in order");
                if (alias)
                    Need(props.TryGetValue("PrestonTalkScene", out var sp) && sp is SF.IScriptObjectPropertyGetter spo && spo.Object.FormKey == new FormKey(key, PrestonTalkSceneId),
                         "property PrestonTalkScene not bound to 0x900");
                else
                    Need(!props.ContainsKey("PrestonTalkScene"), "--no-alias binds PrestonTalkScene");
                Need(!props.ContainsKey("Codsworth") && !props.ContainsKey("KeeperOnly"), "FO4SF_Min00 sets Codsworth or KeeperOnly");
            }
        }

        // Check FO4SF_CodsworthKeeper (0x814) & FO4SF_Codsworth01 (0x816)
        var kq = plug.Quests.FirstOrDefault(x => x.FormKey == new FormKey(key, KeeperQuestId));
        var cwq = plug.Quests.FirstOrDefault(x => x.FormKey == new FormKey(key, CodsworthQuestId));
        if (!codsworth)
        {
            Need(kq is null && cwq is null, $"a --no-codsworth build carries {KeeperEdid} or {CodsworthQuestEdid}");
        }
        else
        {
            if (kq is null) problems.Add($"no QUST 0x{KeeperQuestId:X} {KeeperEdid}");
            else
            {
                Console.WriteLine($"  QUST {kq.EditorID} flags {kq.Data?.Flags} stages {kq.Stages.Count}");
                Need(kq.EditorID == KeeperEdid && NonStartGameReady(kq) && !kq.Data!.Flags.HasFlag(SF.Quest.Flag.RunOnce) &&
                     !kq.Data.Flags.HasFlag(SF.Quest.Flag.DisplaysInHud),
                     $"{KeeperEdid} must NOT be StartGameEnabled, RunOnce, or DisplaysInHud, and must carry StartsEnabled | 0x10000");
                var ks = kq.VirtualMachineAdapter?.Scripts.FirstOrDefault(x => x.Name == ScriptName);
                if (ks is null) problems.Add($"script {ScriptName} not attached to {KeeperEdid}");
                else
                {
                    var props = ks.Properties.ToDictionary(p => p.Name);
                    Console.WriteLine($"  script {ks.Name} on {KeeperEdid}: " + string.Join(", ", props.Keys));
                    Need(props.TryGetValue("Codsworth", out var wp) && wp is SF.IScriptObjectPropertyGetter wo && wo.Object.FormKey == codsRef?.FormKey,
                         "property Codsworth is not his ACHR");
                    Need(props.TryGetValue("KeeperOnly", out var kp) && kp is SF.IScriptBoolPropertyGetter kb && kb.Data,
                         "property KeeperOnly is not True");
                    Need(props.TryGetValue("Preston", out var pp) && pp is SF.IScriptObjectPropertyGetter po && po.Object.FormKey == preston?.FormKey
                         && props.ContainsKey("Raiders") && props.ContainsKey("Credits"), "the keeper lacks a Mandatory property");
                }
            }

            if (cwq is null) problems.Add($"no QUST 0x{CodsworthQuestId:X} {CodsworthQuestEdid}");
            else
            {
                Console.WriteLine($"  QUST {cwq.EditorID} \"{cwq.Name?.String}\" flags {cwq.Data?.Flags} stages [{string.Join(",", cwq.Stages.Select(s => s.Index))}] scenes {cwq.Scenes.Count} dials {cwq.DialogTopics.Count}");
                Need(cwq.EditorID == CodsworthQuestEdid && NonStartGameReady(cwq) && cwq.Data!.Flags.HasFlag(SF.Quest.Flag.AllowRepeatedStages) &&
                     cwq.Data.Flags.HasFlag(SF.Quest.Flag.HasDialogueData) && cwq.Data.Flags.HasFlag(SF.Quest.Flag.DisplaysInHud),
                     $"{CodsworthQuestEdid} flags invalid (must be non-StartGameEnabled with StartsEnabled | AllowRepeatedStages | DisplaysInHud | HasDialogueData | 0x10000)");
                Need(cwq.QuestType.FormKey == new FormKey(SfEsm, QuestTypeSideId), $"{CodsworthQuestEdid} QuestType is not {QuestTypeSideEdid}");
                Need(cwq.Stages.Select(s => s.Index).SequenceEqual(CodsworthQuestStages), $"{CodsworthQuestEdid} stages != [10,20,30,40,100]");
                Need(cwq.Objectives.Count == 1 && cwq.Objectives[0].Index == 10 && cwq.Objectives[0].Targets.Count == 1 && cwq.Objectives[0].Targets[0].AliasID == CodsworthAlias,
                     $"{CodsworthQuestEdid} lacks objective 10 targeting alias 0");
                var cal0 = (cwq.Aliases ?? new List<SF.IAQuestAliasGetter>()).OfType<SF.IQuestReferenceAliasGetter>().FirstOrDefault(a => a.ID == CodsworthAlias);
                Need(cal0 is not null && cal0.ForcedReference.FormKey == codsRef?.FormKey, $"{CodsworthQuestEdid} alias 0 is not forced to Codsworth ACHR");
                Need(cwq.VirtualMachineAdapter?.Scripts.Any(x => x.Name == CodsworthScriptName) == true, $"{CodsworthQuestEdid} lacks script {CodsworthScriptName}");
                Need(cwq.Scenes.Count == 1 && cwq.Scenes[0].FormKey == new FormKey(key, CodsworthSceneId), $"{CodsworthQuestEdid} lacks scene 0x{CodsworthSceneId:X}");
                if (cwq.Scenes.Count == 1)
                {
                    var cscn = cwq.Scenes[0];
                    Need(((uint)(cscn.Flags ?? 0) & 0x2814u) == 0x2814u, $"{CodsworthSceneEdid} lacks 0x2814 flags");
                    var pda = cscn.Actions?.OfType<SF.IPlayerDialogueSceneActionGetter>().FirstOrDefault();
                    Need(pda is not null && pda.DialogueList.Count == 4 && cwq.DialogTopics.Count == 9,
                         $"{CodsworthQuestEdid} must carry 4 player choices and 9 DIAL records");
                    if (pda is not null && pda.DialogueList.Count == 4)
                    {
                        var mqSpec = codsworthMqVoice is null ? null : LoadMqVoice(codsworthMqVoice);
                        var greetTopic = cwq.DialogTopics.FirstOrDefault(t => t.FormKey == new FormKey(key, CodsworthGreetTopicId));
                        var greetWem = greetTopic?.Responses.FirstOrDefault()?.Responses.FirstOrDefault()?.WEMFile ?? 0u;
                        Need(greetWem == (mqSpec?.GreetingWem ?? 0u), $"{CodsworthQuestEdid} greeting WEMFile {greetWem:X8} != {(mqSpec?.GreetingWem ?? 0u):X8}");
                        for (int ci = 0; ci < 4; ci++)
                        {
                            var pcInfo = cwq.DialogTopics.First(t => t.FormKey == pda.DialogueList[ci].PlayerChoice.FormKey).Responses.First();
                            var rpInfo = cwq.DialogTopics.First(t => t.FormKey == pda.DialogueList[ci].NpcResponse.FormKey).Responses.First();
                            var pTxt = pcInfo.Prompt?.String ?? "";
                            var rTxt = pcInfo.Responses.FirstOrDefault()?.ResponseText?.String ?? "";
                            Need(pTxt.Length > 0 && pTxt == rTxt, $"{CodsworthQuestEdid} choice {ci} does not show full player line in both Prompt and ResponseText");
                            Need(rpInfo.SetParentQuestStage?.OnEnd == CodsworthChoiceEndStages[ci],
                                 $"{CodsworthQuestEdid} choice {ci} OnEnd != {CodsworthChoiceEndStages[ci]}");
                            uint wantWem = mqSpec?.ChoiceReplyWems[ci] ?? 0u;
                            uint gotWem = rpInfo.Responses.FirstOrDefault()?.WEMFile ?? 0u;
                            Need(gotWem == wantWem, $"{CodsworthQuestEdid} reply {ci} WEMFile {gotWem:X8} != {wantWem:X8}");
                            if (ci == 3) Need(rpInfo.Flags?.Flags == 1, $"{CodsworthQuestEdid} choice 4 lacks Goodbye flag");
                            else Need(rpInfo.StartScene.FormKey == cscn.FormKey && rpInfo.StartScenePhase == "TOPLEVELNEST",
                                      $"{CodsworthQuestEdid} choice {ci} does not loop back to TOPLEVELNEST");
                        }
                    }
                }
            }
        }

        // Check FO4SF_COMPreston (0x815)
        var cq = plug.Quests.FirstOrDefault(x => x.FormKey == new FormKey(key, ComQuestId));
        if (cq is null) problems.Add($"no QUST 0x{ComQuestId:X} {ComQuestEdid}");
        else
        {
            var cal = (cq.Aliases ?? new List<SF.IAQuestAliasGetter>()).OfType<SF.IQuestReferenceAliasGetter>()
                .FirstOrDefault(a => a.ID == ComAlias);
            var packageKey = new FormKey(SfEsm, FollowPackageId);
            Console.WriteLine($"  QUST {cq.EditorID} flags {cq.Data?.Flags} aliases {cq.Aliases?.Count ?? 0} " +
                              $"package {(cal == null ? "none" : string.Join(",", cal.PackageData.Select(p => p.FormKey.ToString())))}");
            Need(cq.EditorID == ComQuestEdid && cq.Data is not null && cq.Data.Flags.HasFlag(SF.Quest.Flag.StartGameEnabled)
                 && !cq.Data.Flags.HasFlag(SF.Quest.Flag.RunOnce) && !cq.Data.Flags.HasFlag(SF.Quest.Flag.DisplaysInHud),
                 $"{ComQuestEdid} is not a start-game-enabled quest kept out of the Missions tab");
            var wantFlags = SF.AQuestAlias.Flag.Optional | SF.AQuestAlias.Flag.AllowReserved;
            Need(cal is not null && cal.Name == ComAliasName && cal.Flags == wantFlags
                 && cal.ForcedReference.IsNull
                 && cal.PackageData.Select(p => p.FormKey).SequenceEqual(new[] { packageKey }),
                 $"alias {ComAlias} is not an empty optional reserved {ComAliasName} with only {FollowPackageEdid}");
            Need(m.Cache.TryResolve<SF.IPackageGetter>(packageKey, out var pack) && pack.EditorID == FollowPackageEdid,
                 $"Starfield.esm {FollowPackageId:X6} is not the package {FollowPackageEdid}");
            Need(cq.VirtualMachineAdapter is null || cq.VirtualMachineAdapter.Scripts.Count == 0,
                 $"{ComQuestEdid} carries a script");
        }

        // 2k: Check FO4SF_Sanctuary01 (0x817)
        var sq = plug.Quests.FirstOrDefault(x => x.FormKey == new FormKey(key, SanctuaryQuestId));
        if (sq is null) problems.Add($"no QUST 0x{SanctuaryQuestId:X} {SanctuaryQuestEdid}");
        else
        {
            Console.WriteLine($"  QUST {sq.EditorID} \"{sq.Name?.String}\" flags {sq.Data?.Flags} stages [{string.Join(",", sq.Stages.Select(s => s.Index))}] objectives {sq.Objectives.Count}");
            Need(sq.EditorID == SanctuaryQuestEdid && NonStartGameReady(sq) && sq.Data!.Flags.HasFlag(SF.Quest.Flag.DisplaysInHud),
                 $"{SanctuaryQuestEdid} must be non-StartGameEnabled with StartsEnabled | DisplaysInHud | 0x10000");
            Need(sq.QuestType.FormKey == new FormKey(SfEsm, QuestTypeSideId), $"{SanctuaryQuestEdid} QuestType is not {QuestTypeSideEdid}");
            Need(sq.Stages.Select(s => s.Index).SequenceEqual(SanctuaryQuestStages), $"{SanctuaryQuestEdid} stages != [10,100]");
            Need(sq.Stages.Last().LogEntries.Any(l => l.Flags?.HasFlag(SF.QuestLogEntry.Flag.CompleteQuest) == true), $"{SanctuaryQuestEdid} stage 100 does not CompleteQuest");
            var sal = (sq.Aliases ?? new List<SF.IAQuestAliasGetter>()).OfType<SF.IQuestReferenceAliasGetter>().FirstOrDefault(a => a.ID == SanctuaryBenchAlias);
            Need(sal is not null && (sal.Flags ?? 0).HasFlag(SF.AQuestAlias.Flag.Optional) && (sal.Flags ?? 0).HasFlag(SF.AQuestAlias.Flag.AllowReserved),
                 $"{SanctuaryQuestEdid} lacks optional SanctuaryWorkbench alias 0");
            Need(sq.Objectives.Count == 1 && sq.Objectives[0].Index == 10 && sq.Objectives[0].Targets.Count == 1 && sq.Objectives[0].Targets[0].AliasID == SanctuaryBenchAlias,
                 $"{SanctuaryQuestEdid} lacks objective 10 targeting alias 0");
            var ss = sq.VirtualMachineAdapter?.Scripts.FirstOrDefault(x => x.Name == SanctuaryScriptName);
            Need(ss is not null && ss.Properties.FirstOrDefault(p => p.Name == "XMarkerBase") is SF.IScriptObjectPropertyGetter xp &&
                 xp.Object.FormKey == new FormKey(SfEsm, XMarkerId),
                 $"{SanctuaryQuestEdid} lacks {SanctuaryScriptName} with XMarkerBase -> Starfield.esm:00003B");
        }

        foreach (var p in problems) Console.WriteLine("FAIL  " + p);
        Console.WriteLine(problems.Count == 0 ? "all checks pass" : $"{problems.Count} problem(s)");
        return problems.Count == 0 ? 0 : 1;
    }

    // ---------------------------------------------------------------- selftest (synthetic masters & synthetic strings only)

    public static int SelfTest(string dir)
    {
        Directory.CreateDirectory(dir);
        var rel = SF.StarfieldRelease.Starfield;
        var sf = new SF.StarfieldMod(SfEsm, rel);
        sf.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Master;
        sf.MiscItems.Add(new SF.MiscItem(new FormKey(SfEsm, CreditsId), rel) { EditorID = "Credits" });
        sf.Statics.Add(new SF.Static(new FormKey(SfEsm, XMarkerId), rel) { EditorID = "XMarker" });
        sf.Packages.Add(new SF.Package(new FormKey(SfEsm, FollowPackageId), rel) { EditorID = FollowPackageEdid });
        sf.Packages.Add(new SF.Package(new FormKey(SfEsm, RaiderCombatPackageId), rel) { EditorID = RaiderCombatPackageEdid });
        sf.Packages.Add(new SF.Package(new FormKey(SfEsm, RaiderSandboxPackageId), rel) { EditorID = RaiderSandboxPackageEdid });
        sf.Keywords.Add(new SF.Keyword(new FormKey(SfEsm, QuestTypeSideId), rel) { EditorID = QuestTypeSideEdid });

        // Preston's Starfield HumanRace + male template + voice + colonial outfit + Orion laser rifle + ammo
        var humanRace = new SF.Race(new FormKey(SfEsm, SfHumanRaceId), rel) { EditorID = SfHumanRaceEdid, Flags = SF.Race.Flag.AllowPcDialog };
        sf.Races.Add(humanRace);
        var maleVoice = new SF.VoiceType(new FormKey(SfEsm, 0x013AD2), rel) { EditorID = SfPrestonVoiceEdid, Flags = SF.VoiceType.Flag.AllowDefaultDialog };
        sf.VoiceTypes.Add(maleVoice);
        sf.Outfits.Add(new SF.Outfit(new FormKey(SfEsm, SfPrestonOutfitId), rel) { EditorID = SfPrestonOutfitEdid });
        sf.Weapons.Add(new SF.Weapon(new FormKey(SfEsm, SfPrestonWeaponId), rel) { EditorID = SfPrestonWeaponEdid });
        sf.Ammunitions.Add(new SF.Ammunition(new FormKey(SfEsm, SfPrestonAmmoId), rel) { EditorID = SfPrestonAmmoEdid });
        sf.Npcs.Add(new SF.Npc(new FormKey(SfEsm, SfPapaKatzId), rel)
        {
            EditorID = SfPapaKatzEdid, Name = "Synthetic Male Template",
            Race = new FormLink<SF.IRaceGetter>(humanRace.FormKey),
            Voice = new FormLinkNullable<SF.IVoiceTypeGetter>(maleVoice.FormKey),
        });

        // Codsworth's Garden Mini Bot body (intentionally lacks AllowPcDialog & AllowDefaultDialog in vanilla, which Write fixes)
        var race = new SF.Race(new FormKey(SfEsm, 0x900), rel) { EditorID = "MiniBotARace" };
        sf.Races.Add(race);
        var botVoice = new SF.VoiceType(new FormKey(SfEsm, 0x903), rel) { EditorID = "RobotMiniBotA", Flags = 0 };
        sf.VoiceTypes.Add(botVoice);
        var faction = new SF.Faction(new FormKey(SfEsm, 0x901), rel) { EditorID = "OutpostFaction" };
        sf.Factions.Add(faction);
        sf.Factions.Add(new SF.Faction(new FormKey(SfEsm, PlayerFactionId), rel) { EditorID = PlayerFactionEdid });
        var bot = new SF.Npc(new FormKey(SfEsm, 0x902), rel)
        {
            EditorID = CodsworthBody, Name = "Synthetic Mini Bot",
            Race = new FormLink<SF.IRaceGetter>(race.FormKey),
            Voice = new FormLinkNullable<SF.IVoiceTypeGetter>(botVoice.FormKey),
        };
        bot.Factions.Add(new SF.RankPlacement { Faction = new FormLink<SF.IFactionGetter>(faction.FormKey), Rank = 0 });
        bot.VirtualMachineAdapter = new SF.VirtualMachineAdapter { Version = 6, ObjectFormat = 2 };
        bot.VirtualMachineAdapter.Scripts.Add(new SF.ScriptEntry { Name = "OutpostBotScript" });
        sf.Npcs.Add(bot);

        var aa = new SF.ArmorAddon(new FormKey(SfEsm, MiniBotArmaId), rel) { EditorID = MiniBotArmaEdid, Race = new FormLinkNullable<SF.IRaceGetter>(race.FormKey) };
        aa.WorldModel = new GenderedItem<SF.Model?>(new SF.Model { File = new AssetLink<StarfieldModelAssetType>("Meshes\\Actors\\MiniBot\\MiniBotA.nif") }, null);
        sf.ArmorAddons.Add(aa);
        var sk = new SF.Armor(new FormKey(SfEsm, MiniBotSkinId), rel) { EditorID = MiniBotSkinEdid };
        sk.Armatures.Add(new SF.ArmorAddonModel { AddonIndex = 0, ArmorAddon = new FormLinkNullable<SF.IArmorAddonGetter>(aa.FormKey) });
        sk.Armatures.Add(new SF.ArmorAddonModel { AddonIndex = 1, ArmorAddon = new FormLinkNullable<SF.IArmorAddonGetter>(aa.FormKey) });
        sf.Armors.Add(sk);
        bot.Skin.SetTo(sk.FormKey);
        sf.ModHeader.Stats.NextFormID = 0x800;
        var sfPath = Path.Combine(dir, "Starfield.esm");
        sf.BeginWrite.ToPath(sfPath).WithNoLoadOrder().NoCheckIfLowerRangeDisallowed().Write();

        var coreKey = ModKey.FromFileName("FO4TerrainCore.esm");
        var core = new SF.StarfieldMod(coreKey, rel);
        core.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Master;
        core.Activators.Add(new SF.Activator(new FormKey(coreKey, CoreBenchBaseId), rel) { EditorID = "FO4Core_wkshp_0c1aeb_fallout4" });
        var world = new SF.Worldspace(new FormKey(coreKey, 0x803), rel) { EditorID = World };
        world.TopCell = new SF.Cell(new FormKey(coreKey, 0x900), rel) { Flags = SF.Cell.Flag.HasWater };
        world.TopCell.Persistent.Add(new SF.PlacedObject(new FormKey(coreKey, 0x800), rel) { EditorID = "Anchor" });
        core.Worldspaces.Add(world);
        core.ModHeader.Stats.NextFormID = 0x901;
        var corePath = Path.Combine(dir, coreKey.FileName);
        core.BeginWrite.ToPath(corePath).WithLoadOrder(SfEsm).WithKnownMasters(new KeyedMasterStyle(SfEsm, MasterStyle.Full)).Write();

        var raiderKey = ModKey.FromFileName("FO4ActorRaider.esm");
        var raider = new SF.StarfieldMod(raiderKey, rel);
        raider.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Master;
        raider.Npcs.Add(new SF.Npc(new FormKey(raiderKey, RaiderId), rel) { EditorID = "FO4_LvlRaider", Name = "Synthetic Raider", Flags = SF.Npc.Flag.Respawn });
        raider.Npcs.Add(new SF.Npc(new FormKey(raiderKey, CalmProbeId), rel) { EditorID = "FO4_LvlRaider_Calm", Name = "Synthetic Raider", Flags = SF.Npc.Flag.Respawn });
        raider.ModHeader.Stats.NextFormID = 0xF04802;
        var raiderPath = Path.Combine(dir, raiderKey.FileName);
        raider.BeginWrite.ToPath(raiderPath).WithLoadOrder(SfEsm).WithKnownMasters(new KeyedMasterStyle(SfEsm, MasterStyle.Full)).Write();

        var pointsPath = Path.Combine(dir, "points.json");
        File.WriteAllText(pointsPath, """
        {"quest_name": "Synthetic Concord Mission", "preston_name": "Synthetic Militia Leader",
         "objectives": {"10": "Synthetic Objective 10", "85": "Synthetic Objective 85", "86": "Synthetic Objective 86"},
         "preston": {"src": "01E2EA:XTEL", "pos": [-880.5, 1050.25, 90.0], "rot": [0, 0, 1.5]},
         "raiders": [{"src": "046458", "pos": [-829.06, 1008.31, 88.09], "rot": [0, 0, 0.5]},
                     {"src": "046459", "pos": [-835.0, 1012.0, 88.5], "rot": [0, 0, 0.0]}],
         "codsworth": {"src": "01CA7D", "name": "Synthetic Household Robot", "pos": [-1146.709, 1293.837, 111.734], "rot": [0, 0, 2.356]}}
        """);

        var outDir = Path.Combine(dir, "out");
        foreach (var alias in new[] { true, false })
        {
            var o = Path.Combine(outDir, alias ? "alias" : "noalias");
            int rc = Write(sfPath, corePath, raiderPath, pointsPath, o, Plugin, World, alias);
            if (rc != 0) return rc;
            rc = Check(Path.Combine(o, Plugin), sfPath, corePath, raiderPath, alias);
            if (rc != 0) return rc;
        }
        {
            var o = Path.Combine(outDir, "nocodsworth");
            int rc = Write(sfPath, corePath, raiderPath, pointsPath, o, Plugin, World, true, null);
            if (rc == 0) rc = Check(Path.Combine(o, Plugin), sfPath, corePath, raiderPath, true, false);
            if (rc != 0) return rc;
            if (Check(Path.Combine(o, Plugin), sfPath, corePath, raiderPath, true, true) == 0)
                { Console.WriteLine("FAIL  check passed a build without Codsworth when he was expected"); return 1; }
        }
        {
            var o = Path.Combine(outDir, "model");
            const string model = "fo4port\\actors\\codsworth\\codsworth.nif";
            int rc = Write(sfPath, corePath, raiderPath, pointsPath, o, Plugin, World, true, CodsworthBody, model);
            if (rc == 0) rc = Check(Path.Combine(o, Plugin), sfPath, corePath, raiderPath, true, true, model);
            if (rc != 0) return rc;
            if (Check(Path.Combine(o, Plugin), sfPath, corePath, raiderPath, true, true) == 0)
                { Console.WriteLine("FAIL  check passed a model build as a plain one"); return 1; }
            if (Check(Path.Combine(outDir, "alias", Plugin), sfPath, corePath, raiderPath, true, true, model) == 0)
                { Console.WriteLine("FAIL  check passed a plain build as a model one"); return 1; }
            {
                var mod = SF.StarfieldMod.CreateFromBinary(Path.Combine(o, Plugin), rel, Styles(SfEsm, coreKey, raiderKey));
                mod.ArmorAddons.First().WorldModel!.Male!.File = new AssetLink<StarfieldModelAssetType>("Meshes\\Elsewhere\\" + model);
                var md = Path.Combine(outDir, "model_moved");
                Directory.CreateDirectory(md);
                var lo = new[] { SfEsm, coreKey, raiderKey };
                mod.BeginWrite.ToPath(Path.Combine(md, Plugin)).WithLoadOrder(lo)
                    .WithKnownMasters(lo.Select(k => new KeyedMasterStyle(k, MasterStyle.Full)).ToArray()).Write();
                if (Check(Path.Combine(md, Plugin), sfPath, corePath, raiderPath, true, true, model) == 0)
                    { Console.WriteLine("FAIL  check passed his model in another folder"); return 1; }
                Console.WriteLine("mutation rejected: model in another folder");
            }
            if (ModelPath("Meshes\\Actors\\x.nif", "Meshes\\" + model) != "Meshes\\" + model || ModelPath("Actors\\x.nif", model) != model)
                { Console.WriteLine("FAIL  ModelPath does not follow the vanilla prefix"); return 1; }
        }
        {
            var voice = Path.Combine(dir, "voice.json");
            File.WriteAllText(voice, """
                [{"info": "000F1F6E", "response": 1, "text": "Synthetic hello 1", "wem": "00F4C001", "sex": null},
                 {"info": "000F1F78", "response": 1, "text": "Synthetic hello sir", "wem": "00F4C002", "sex": "male"},
                 {"info": "000F1F80", "response": 1, "text": "Synthetic hello mum", "wem": "00F4C003", "sex": "female"}]
                """);
            var mqVoice = Path.Combine(dir, "mq_voice.json");
            File.WriteAllText(mqVoice, """
                {"greeting_wem": "00F4C101",
                 "reply_wems": ["00F4C102", "00F4C103", "00F4C104", "00F4C105"]}
                """);
            var o = Path.Combine(outDir, "voice");
            int rc = Write(sfPath, corePath, raiderPath, pointsPath, o, Plugin, World, true, CodsworthBody, null, voice, mqVoice);
            if (rc == 0) rc = Check(Path.Combine(o, Plugin), sfPath, corePath, raiderPath, true, true, null, voice, mqVoice);
            if (rc != 0) return rc;
            if (Check(Path.Combine(o, Plugin), sfPath, corePath, raiderPath, true, true) == 0)
                { Console.WriteLine("FAIL  check passed a voice build as a plain one"); return 1; }
            if (Check(Path.Combine(outDir, "alias", Plugin), sfPath, corePath, raiderPath, true, true, null, voice, mqVoice) == 0)
                { Console.WriteLine("FAIL  check passed a plain build as a voice one"); return 1; }

            static SF.DialogTopic HelloDial(SF.StarfieldMod m) =>
                m.Quests[new FormKey(m.ModKey, QuestId)].DialogTopics.First(d => d.FormKey.ID == CodsworthDialId);

            var voiceMutations = new (string Name, Action<SF.StarfieldMod> Edit)[]
            {
                ("a line's wem changed", m => HelloDial(m).Responses[1].Responses[0].WEMFile = 0x00F4C009),
                ("a line said by anyone", m => HelloDial(m).Responses[0].Conditions.Clear()),
                ("a sir line for either sex", m => HelloDial(m).Responses[1].Conditions.RemoveAt(1)),
                ("a line's text changed", m => HelloDial(m).Responses[2].Responses[0].ResponseText = "Synthetic wrong line"),
                ("said by anyone but him", m => HelloDial(m).Responses[0].Conditions[0].CompareOperator = SF.CompareOperator.NotEqualTo),
                ("sex read on the speaker", m => HelloDial(m).Responses[1].Conditions[1].Data.RunOnType = SF.Condition.RunOnType.Subject),
                ("sex value 0", m => ((SF.ConditionFloat)HelloDial(m).Responses[1].Conditions[1]).ComparisonValue = 0),
                ("sex operator NotEqualTo", m => HelloDial(m).Responses[2].Conditions[1].CompareOperator = SF.CompareOperator.NotEqualTo),
                ("conditions ORed", m => HelloDial(m).Responses[1].Conditions[0].Flags = SF.Condition.Flag.OR),
                ("mq102 reply wem changed", m => m.Quests[new FormKey(m.ModKey, CodsworthQuestId)].DialogTopics.First(d => d.FormKey.ID == FirstCodsworthReplyTopicId).Responses[0].Responses[0].WEMFile = 0x00F4C999),
            };
            foreach (var (name, edit) in voiceMutations)
            {
                var mod = SF.StarfieldMod.CreateFromBinary(Path.Combine(o, Plugin), rel, Styles(SfEsm, coreKey, raiderKey));
                edit(mod);
                var md = Path.Combine(outDir, "voice_mutated");
                Directory.CreateDirectory(md);
                var lo = new[] { SfEsm, coreKey, raiderKey };
                mod.BeginWrite.ToPath(Path.Combine(md, Plugin)).WithLoadOrder(lo)
                    .WithKnownMasters(lo.Select(k => new KeyedMasterStyle(k, MasterStyle.Full)).ToArray()).Write();
                if (Check(Path.Combine(md, Plugin), sfPath, corePath, raiderPath, true, true, null, voice, mqVoice) == 0)
                    { Console.WriteLine($"FAIL  check passed a mutation: {name}"); return 1; }
                Console.WriteLine($"mutation rejected: {name}");
            }
        }

        static SF.Quest Min00Q(SF.StarfieldMod m) => m.Quests[new FormKey(m.ModKey, QuestId)];
        static SF.Quest Keeper(SF.StarfieldMod m) => m.Quests[new FormKey(m.ModKey, KeeperQuestId)];
        static SF.Quest Com(SF.StarfieldMod m) => m.Quests[new FormKey(m.ModKey, ComQuestId)];
        static SF.Quest Cods01(SF.StarfieldMod m) => m.Quests[new FormKey(m.ModKey, CodsworthQuestId)];
        static SF.Quest Sanct01(SF.StarfieldMod m) => m.Quests[new FormKey(m.ModKey, SanctuaryQuestId)];
        var good = Path.Combine(outDir, "alias", Plugin);
        var mutations = new (string Name, Action<SF.StarfieldMod> Edit)[]
        {
            ("FO4SF_Min00 has StartGameEnabled", m => Min00Q(m).Data!.Flags |= SF.Quest.Flag.StartGameEnabled),
            ("keeper has StartGameEnabled", m => Keeper(m).Data!.Flags |= SF.Quest.Flag.StartGameEnabled),
            ("FO4SF_Codsworth01 has StartGameEnabled", m => Cods01(m).Data!.Flags |= SF.Quest.Flag.StartGameEnabled),
            ("FO4SF_Sanctuary01 has StartGameEnabled", m => Sanct01(m).Data!.Flags |= SF.Quest.Flag.StartGameEnabled),
            ("FO4SF_Codsworth01 removed", m => m.Quests.Remove(new FormKey(m.ModKey, CodsworthQuestId))),
            ("FO4SF_Sanctuary01 removed", m => m.Quests.Remove(new FormKey(m.ModKey, SanctuaryQuestId))),
            ("Codsworth race lacks AllowPcDialog", m => m.Races[new FormKey(m.ModKey, CodsworthRaceId)].Flags &= ~SF.Race.Flag.AllowPcDialog),
            ("Codsworth voice lacks AllowDefaultDialog", m => m.VoiceTypes[new FormKey(m.ModKey, CodsworthVoiceId)].Flags &= ~SF.VoiceType.Flag.AllowDefaultDialog),
            ("Preston race reverted to robot race", m => m.Npcs[new FormKey(m.ModKey, PrestonNpcId)].Race.SetTo(new FormKey(SfEsm, 0x900))),
            ("Preston missing colonial outfit", m => m.Npcs[new FormKey(m.ModKey, PrestonNpcId)].DefaultOutfit.Clear()),
            ("Preston talk scene removed", m => Min00Q(m).Scenes.Clear()),
            ("raider alias lacks combat package", m => ((SF.QuestReferenceAlias)Min00Q(m).Aliases![1]).PackageData.Clear()),
            ("Codsworth NPC_ and ACHR removed", m =>
            {
                m.Npcs.Remove(new FormKey(m.ModKey, CodsworthNpcId));
                m.Worldspaces.First().TopCell!.Persistent.RemoveAll(r => r.FormKey.ID == CodsworthRefId);
            }),
            ("Codsworth ACHR removed", m => m.Worldspaces.First().TopCell!.Persistent.RemoveAll(r => r.FormKey.ID == CodsworthRefId)),
            ("Codsworth not Essential", m => m.Npcs[new FormKey(m.ModKey, CodsworthNpcId)].Flags &= ~SF.Npc.Flag.Essential),
            ("Codsworth not Unique", m => m.Npcs[new FormKey(m.ModKey, CodsworthNpcId)].Flags &= ~SF.Npc.Flag.Unique),
            ("Codsworth respawns", m => m.Npcs[new FormKey(m.ModKey, CodsworthNpcId)].Flags |= SF.Npc.Flag.Respawn),
            ("Codsworth script property removed", m => Keeper(m).VirtualMachineAdapter!.Scripts[0].Properties.RemoveAll(p => p.Name == "Codsworth")),
            ("keeper quest removed", m => m.Quests.Remove(new FormKey(m.ModKey, KeeperQuestId))),
            ("keeper lacks StartsEnabled", m => Keeper(m).Data!.Flags &= ~SF.Quest.Flag.StartsEnabled),
            ("keeper runs the mission", m => ((SF.ScriptBoolProperty)Keeper(m).VirtualMachineAdapter!.Scripts[0].Properties.First(p => p.Name == "KeeperOnly")).Data = false),
            ("Codsworth also set on the mission", m => Min00Q(m).VirtualMachineAdapter!.Scripts[0].Properties.Add(new SF.ScriptObjectProperty
            {
                Name = "Codsworth", Flags = SF.ScriptProperty.Flag.Edited, Alias = -1,
                Object = new FormLink<SF.IStarfieldMajorRecordGetter>(new FormKey(m.ModKey, CodsworthRefId)),
            })),
            ("Codsworth has a faction", m => m.Npcs[new FormKey(m.ModKey, CodsworthNpcId)].Factions.Add(
                new SF.RankPlacement { Faction = new FormLink<SF.IFactionGetter>(new FormKey(SfEsm, 0x901)) })),
            ("quest has no QuestType", m => Min00Q(m).QuestType.Clear()),
            ("Preston without the Minutemen faction", m => m.Npcs[new FormKey(m.ModKey, PrestonNpcId)].Factions.Clear()),
            ("Minutemen only Friend to the player", m => m.Factions[new FormKey(m.ModKey, MinutemenFactionId)].Relations[0].Reaction = SF.CombatReaction.Friend),
            ("Minutemen Ally to another faction", m => m.Factions[new FormKey(m.ModKey, MinutemenFactionId)].Relations[0].Target.SetTo(new FormKey(SfEsm, 0x901))),
            ("follow quest removed", m => m.Quests.Remove(new FormKey(m.ModKey, ComQuestId))),
            ("follow quest shows in the Missions tab", m => Com(m).Data!.Flags |= SF.Quest.Flag.DisplaysInHud),
            ("follow alias has no package", m => ((SF.QuestReferenceAlias)Com(m).Aliases![0]).PackageData.Clear()),
        };
        foreach (var (name, edit) in mutations)
        {
            var mod = SF.StarfieldMod.CreateFromBinary(good, rel, Styles(SfEsm, coreKey, raiderKey));
            edit(mod);
            var md = Path.Combine(outDir, "mutated");
            Directory.CreateDirectory(md);
            var mp = Path.Combine(md, Plugin);
            var lo = new[] { SfEsm, coreKey, raiderKey };
            mod.BeginWrite.ToPath(mp).WithLoadOrder(lo).WithKnownMasters(lo.Select(k => new KeyedMasterStyle(k, MasterStyle.Full)).ToArray()).Write();
            if (Check(mp, sfPath, corePath, raiderPath, true, true) == 0)
                { Console.WriteLine($"FAIL  check passed a mutated plugin: {name}"); return 1; }
            Console.WriteLine($"mutation rejected: {name}");
        }
        if (StripTokens("Synthetic Objective (<Global=TestCount>/<Global=TestTotal>)") != "Synthetic Objective")
            { Console.WriteLine("FAIL  StripTokens"); return 1; }
        if (!IsCorpse("Loot_CorpseRaiderMale01", 0) || !IsCorpse("LvlRaider", 0x200) || IsCorpse("LvlRaider", 0x400))
            { Console.WriteLine("FAIL  IsCorpse"); return 1; }
        Console.WriteLine("selftest pass");
        return 0;
    }
}
