// Mission: cut-down "When Freedom Calls" (FO4SF_Min00 0x800), FO4SF_CodsworthKeeper (0x814), FO4SF_COMPreston (0x815),
// FO4SF_Codsworth01 (0x816, MQ102-lite 4-choice Sanctuary conversation), and FO4SF_Sanctuary01 (0x817, Sanctuary
// workbench 0250FE -> FO4TerrainCore.esm 0x005C50 objective) in FO4SFMission.esm.
//
//   points <Fallout4.esm> <out points.json> [--radius 120] [--max 8] [--strings-dir <dir>] [--hello-infos <hex,hex...>]
//   write <Starfield.esm> <FO4TerrainCore.esm> <FO4ActorRaider.esm> <points.json> <out dir> [--plugin FO4SFMission.esm]
//         [--world FO4Core_Commonwealth] [--no-alias] [--codsworth-body OutpostRobotMiniBotA_Garden] [--no-codsworth]
//         [--codsworth-model <mesh under Meshes>] [--codsworth-voice <voice.json>] [--codsworth-mq-voice <mq_voice.json>]
//         [--preston-voice <preston_voice.json>] [--codsworth-race-framing <0|1>]
//   check <plugin> <Starfield.esm> <FO4TerrainCore.esm> <FO4ActorRaider.esm> [--no-alias] [--no-codsworth]
//         [--codsworth-model <mesh>] [--codsworth-voice <voice.json>] [--codsworth-mq-voice <mq_voice.json>]
//         [--preston-voice <preston_voice.json>] [--codsworth-race-framing <0|1>]
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
                                                       Mission.ArgOrNull(args, "--codsworth-mq-voice"),
                                                       Mission.ArgOrNull(args, "--preston-voice"),
                                                       Mission.ArgOrNull(args, "--actor-looks-dir"),
                                                       Mission.BoolFlag(args, "--codsworth-race-framing", false)),
        "check" when args.Length >= 5 => Mission.Check(args[1], args[2], args[3], args[4], !args.Contains("--no-alias"),
                                                       !args.Contains("--no-codsworth"),
                                                       Mission.ArgOrNull(args, "--codsworth-model"),
                                                       Mission.ArgOrNull(args, "--codsworth-voice"),
                                                       Mission.ArgOrNull(args, "--codsworth-mq-voice"),
                                                       Mission.ArgOrNull(args, "--preston-voice"),
                                                       Mission.ArgOrNull(args, "--actor-looks-dir"),
                                                       Mission.BoolFlag(args, "--codsworth-race-framing", false)),
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

    // C3: Starfield.esm Coachman + Caseless Shotgun Shell (matches FO4ActorRaider.esm FO4_LvlRaider CNTO Coachman)
    // and measured merged-world offset (vmad_patch.MERGE_MEASURED) so Concord raiders author directly at Concord.
    public const uint SfRaiderWeaponId = 0x26D96B, SfRaiderAmmoId = 0x2B4AFB;
    public const string SfRaiderWeaponEdid = "Coachman", SfRaiderAmmoEdid = "AmmoShotshell";
    public const int RaiderAmmoCount = 60;
    // R11 D3: Balanced Starfield stand-in sidearm (Eon 10 dmg + Ammo777mm x36 vs Coachman 52 dmg) so a cover-using
    // Level-1 (205 HP) player survives Concord without god mode until A4/A5 replace the stand-in fight.
    public const uint SfRaiderSidearmId = 0x0476C4, SfRaiderSidearmAmmoId = 0x04AD3E;
    public const string SfRaiderSidearmEdid = "Eon", SfRaiderSidearmAmmoEdid = "Ammo777mm";
    public const int RaiderSidearmAmmoCount = 36;
    // R11 D1: ModelARace (Vasco) reference for standing robot dialogue framing metadata on FO4SF_CodsworthRace.
    public const uint SfModelARaceId = 0x005629;
    public const string SfModelARaceEdid = "ModelARace";
    public const float MergeOffsetX = -1200.0f, MergeOffsetY = -2700.0f;

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

    // V2: Codsworth eye-level talk activator + 4-choice MessageBox records for Codsworth & Preston (0x970..0x978)
    public const uint CodsworthTalkActiId = 0x970;
    public const string CodsworthTalkActiEdid = "FO4SF_CodsworthTalkActi";
    public const string CodsworthTalkActiModel = "Effects\\sfbgs006\\SFBGS006_SBShipDecoratorMarker.nif";

    public const uint CodsworthTalkMsgId = 0x971, CodsworthReply0MsgId = 0x972, CodsworthReply1MsgId = 0x973, CodsworthReply2MsgId = 0x974;
    public const string CodsworthTalkMsgEdid = "FO4SF_Codsworth01_TalkMsg",
                        CodsworthReply0MsgEdid = "FO4SF_Codsworth01_Reply0Msg",
                        CodsworthReply1MsgEdid = "FO4SF_Codsworth01_Reply1Msg",
                        CodsworthReply2MsgEdid = "FO4SF_Codsworth01_Reply2Msg";

    public const uint PrestonTalkMsgId = 0x975, PrestonReply0MsgId = 0x976, PrestonReply1MsgId = 0x977, PrestonReply2MsgId = 0x978;
    public const string PrestonTalkMsgEdid = "FO4SF_Min00_PrestonTalkMsg",
                        PrestonReply0MsgEdid = "FO4SF_Min00_PrestonReply0Msg",
                        PrestonReply1MsgEdid = "FO4SF_Min00_PrestonReply1Msg",
                        PrestonReply2MsgEdid = "FO4SF_Min00_PrestonReply2Msg";
    public const uint MissionTalkUseMessageBoxGlobId = 0x979;
    public const string MissionTalkUseMessageBoxGlobEdid = "FO4SF_MissionTalkUseMessageBox";
    // R11/R13 Part 3 E3 + fix4 + Task 0d: softened Concord Raider sidearm (1.5 dmg Eon, AmmoType=Ammo777mm, AmmoList cleared -> exact 36 rounds,
    // ObjectTemplates+AttachParentSlots intact so receivers/barrels/ProjectileNodes render & fire) and softened Concord Raider primary
    // (4.0 dmg x 1 projectile Coachman, AmmoType=AmmoShotshell, AmmoList cleared -> exact 60 rounds, ObjectTemplates+AttachParentSlots intact).
    public const uint ConcordRaiderSidearmWeapId = 0x97A;
    public const string ConcordRaiderSidearmWeapEdid = "FO4SF_ConcordRaiderSidearm";
    public const float ConcordRaiderSidearmDamage = 1.5f;
    public const byte ConcordRaiderSidearmProjectiles = 1;
    public const uint ConcordRaiderPrimaryWeapId = 0x97B;
    public const string ConcordRaiderPrimaryWeapEdid = "FO4SF_ConcordRaiderPrimary";
    public const float ConcordRaiderPrimaryDamage = 4.0f;
    public const byte ConcordRaiderPrimaryProjectiles = 1;

    // R11 Part 3: Post-mission repeat Starfield Scenes hosted on FO4SF_CodsworthKeeper (0x814)
    // Collision-free slots 0x990..0x9EB (FalloutActorLooks uses 0x980..0x98A; A4/A7/A7cd use 0xA00..0xB56; #853 uses 0xB80..0xB8B).
    public const uint KeeperPrestonAlias = 0, KeeperCodsworthAlias = 1;
    public const uint PrestonPostTalkSceneId = 0x990, PrestonPostGreetTopicId = 0x991, PrestonPostGreetInfoId = 0x992;
    public const string PrestonPostTalkSceneEdid = "FO4SF_PrestonPostScene",
                        PrestonPostGreetTopicEdid = "FO4SF_PrestonPostGreetTopic",
                        PrestonPostGreetInfoEdid = "FO4SF_PrestonPostGreetInfo";
    public const uint FirstPrestonPostChoiceTopicId = 0x9A0, FirstPrestonPostChoiceInfoId = 0x9A8;
    public const uint FirstPrestonPostReplyTopicId = 0x9B0, FirstPrestonPostReplyInfoId = 0x9B8;

    public const uint CodsworthPostSceneId = 0x9C0, CodsworthPostGreetTopicId = 0x9C1, CodsworthPostGreetInfoId = 0x9C2;
    public const string CodsworthPostSceneEdid = "FO4SF_CodsworthPostScene",
                        CodsworthPostGreetTopicEdid = "FO4SF_CodsworthPostGreetTopic",
                        CodsworthPostGreetInfoEdid = "FO4SF_CodsworthPostGreetInfo";
    public const uint FirstCodsworthPostChoiceTopicId = 0x9D0, FirstCodsworthPostChoiceInfoId = 0x9D8;
    public const uint FirstCodsworthPostReplyTopicId = 0x9E0, FirstCodsworthPostReplyInfoId = 0x9E8;
    public const int MaxTalkButtons = 4;

    // Task 1i: Interior holding cell owning all Mission persistent ACHRs so FO4SFMission.esm has 0 WRLD overrides
    public const uint MissionHoldingCellId = 0xB60;
    public const string MissionHoldingCellEdid = "FO4SF_MissionHoldingCell";

    // Stages & Objectives
    public static readonly ushort[] Stages = { 10, 20, 30, 35, 40, 200 };
    public static readonly ushort[] CodsworthQuestStages = { 10, 20, 30, 40, 100 };

    public record MissionStartConfig(bool MuteDuplicateObjectiveToasts, string LandingHandoff);

    public static MissionStartConfig LoadMissionStartConfig(string? jsonPath = null)
    {
        string? path = jsonPath;
        if (path is null)
        {
            var dir = AppContext.BaseDirectory;
            for (int up = 0; up < 8 && dir != null; up++, dir = Directory.GetParent(dir)?.FullName)
            {
                var candidate = Path.Combine(dir, "src", "fo4sf", "core", "game_start_config.json");
                if (File.Exists(candidate)) { path = candidate; break; }
            }
            if (path is null)
            {
                var cwd = Directory.GetCurrentDirectory();
                for (int up = 0; up < 8 && cwd != null; up++, cwd = Directory.GetParent(cwd)?.FullName)
                {
                    var candidate = Path.Combine(cwd, "src", "fo4sf", "core", "game_start_config.json");
                    if (File.Exists(candidate)) { path = candidate; break; }
                }
            }
        }
        if (path is null || !File.Exists(path))
            return new MissionStartConfig(true, "single_quest");
        using var doc = JsonDocument.Parse(File.ReadAllText(path));
        var root = doc.RootElement;
        var defGame = root.TryGetProperty("default_game", out var dg) ? (dg.GetString() ?? "fo4") : "fo4";
        var game = root.GetProperty("games").GetProperty(defGame);
        var mute = !game.TryGetProperty("mute_duplicate_objective_toasts", out var mp) || mp.GetBoolean();
        var handoff = game.TryGetProperty("landing_handoff", out var lh) ? (lh.GetString() ?? "single_quest") : "single_quest";
        if (handoff != "single_quest" && handoff != "two_quests")
            throw new Refusal($"Unsupported landing_handoff '{handoff}' in {path}");
        return new MissionStartConfig(mute, handoff);
    }
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
    const string SyntheticPrestonCampButton = "Ask about setting up a safe camp.";
    const string SyntheticPrestonCampReply = "Once the street is clear, check the workshop bench back in the northern neighborhood.";
    static readonly (string Prompt, string Reply)[] SyntheticCodsworthChoices =
    {
        ("Synthetic choice 1: ask what happened and the date.", "Synthetic response 1: elapsed years summary."),
        ("Synthetic choice 2: ask about the neighborhood and family.", "Synthetic response 2: neighborhood report."),
        ("Synthetic choice 3: ask about nearby survivors.", "Synthetic response 3: nearby town report."),
        ("Synthetic choice 4: head toward Concord.", "Synthetic response 4: onward to Concord."),
    };
    const string SyntheticPrestonPostGreet = "Sanctuary check-in active.";
    const string SyntheticPrestonPostButton = "Carry on";
    const string SyntheticPrestonPostPrompt = "Carry on, Preston.";
    const string SyntheticPrestonPostReply = "Keep watching the settlement perimeter.";
    const string SyntheticCodsworthPostGreet = "Sanctuary household check-in active.";
    const string SyntheticCodsworthPostButton = "Carry on";
    const string SyntheticCodsworthPostPrompt = "Carry on, Codsworth.";
    const string SyntheticCodsworthPostReply = "Keeping Sanctuary tidy as ordered.";

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
    public static bool BoolFlag(string[] a, string name, bool dflt)
    {
        var i = Array.IndexOf(a, name);
        if (i < 0) return dflt;
        if (i + 1 >= a.Length) throw new Refusal($"{name} requires 0 or 1");
        return a[i + 1] switch
        {
            "0" or "false" or "False" => false,
            "1" or "true" or "True" => true,
            var bad => throw new Refusal($"{name} expects 0 or 1, got '{bad}'"),
        };
    }
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

        List<Dictionary<string, object>> InfoRespList(uint infoId, string fallback)
        {
            if (infoById.TryGetValue(infoId, out var inf))
            {
                var rows = inf.Responses.OrderBy(x => x.ResponseNumber)
                    .Select(x => (Num: (int)x.ResponseNumber, Txt: StripTokens(x.Text?.String ?? "")))
                    .Where(x => x.Txt.Length > 0)
                    .Select(x => new Dictionary<string, object> { ["response"] = x.Num, ["text"] = x.Txt })
                    .ToList();
                if (rows.Count > 0) return rows;
                if (!string.IsNullOrWhiteSpace(inf.Prompt?.String))
                    return new List<Dictionary<string, object>> { new() { ["response"] = 1, ["text"] = StripTokens(inf.Prompt!.String!) } };
            }
            return new List<Dictionary<string, object>> { new() { ["response"] = 1, ["text"] = fallback } };
        }

        string InfoAllRespText(uint infoId, string fallback) =>
            string.Join(" ", InfoRespList(infoId, fallback).Select(r => (string)r["text"]));

        string InfoButtonText(uint infoId, int respNum, string fallback)
        {
            if (infoById.TryGetValue(infoId, out var inf) && !string.IsNullOrWhiteSpace(inf.Prompt?.String))
                return ShortButtonText(inf.Prompt!.String!);
            return ShortButtonText(InfoRespText(infoId, respNum, fallback));
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
            ["greeting_info"] = "000CA9CC",
            ["greeting"] = InfoAllRespText(0x0CA9CC, "Synthetic Concord greeting."),
            ["greeting_responses"] = InfoRespList(0x0CA9CC, "Synthetic Concord greeting."),
            ["choices"] = new object[]
            {
                new Dictionary<string, object>
                {
                    ["prompt_info"] = "0001C238", ["reply_info"] = "0005DF11",
                    ["button"] = InfoButtonText(0x01C238, 1, SyntheticPrestonChoices[0].Prompt),
                    ["prompt"] = InfoAllRespText(0x01C238, SyntheticPrestonChoices[0].Prompt),
                    ["reply"] = InfoAllRespText(0x05DF11, SyntheticPrestonChoices[0].Reply),
                    ["reply_responses"] = InfoRespList(0x05DF11, SyntheticPrestonChoices[0].Reply),
                },
                new Dictionary<string, object>
                {
                    ["prompt_info"] = "0001C22C", ["reply_info"] = "0005DF0D",
                    ["button"] = InfoButtonText(0x01C22C, 1, SyntheticPrestonChoices[1].Prompt),
                    ["prompt"] = InfoAllRespText(0x01C22C, SyntheticPrestonChoices[1].Prompt),
                    ["reply"] = InfoAllRespText(0x05DF0D, SyntheticPrestonChoices[1].Reply),
                    ["reply_responses"] = InfoRespList(0x05DF0D, SyntheticPrestonChoices[1].Reply),
                },
                new Dictionary<string, object>
                {
                    ["prompt_info"] = "0001C237", ["reply_info"] = "0005DF1B",
                    ["button"] = InfoButtonText(0x01C237, 1, SyntheticPrestonChoices[2].Prompt),
                    ["prompt"] = InfoAllRespText(0x01C237, SyntheticPrestonChoices[2].Prompt),
                    ["reply"] = InfoAllRespText(0x05DF1B, SyntheticPrestonChoices[2].Reply),
                    ["reply_responses"] = InfoRespList(0x05DF1B, SyntheticPrestonChoices[2].Reply),
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
            ["greeting"] = InfoAllRespText(0x01E64D, "Synthetic robot greeting."),
            ["greeting_responses"] = InfoRespList(0x01E64D, "Synthetic robot greeting."),
            ["choices"] = new object[]
            {
                new Dictionary<string, object>
                {
                    ["prompt_info"] = "000A1814", ["reply_info"] = "000A1818", ["reply_response"] = 1,
                    ["button"] = InfoButtonText(0x0A1814, 1, SyntheticCodsworthChoices[0].Prompt),
                    ["prompt"] = InfoAllRespText(0x0A1814, SyntheticCodsworthChoices[0].Prompt),
                    ["reply"] = InfoAllRespText(0x0A1818, SyntheticCodsworthChoices[0].Reply),
                    ["reply_responses"] = InfoRespList(0x0A1818, SyntheticCodsworthChoices[0].Reply),
                },
                new Dictionary<string, object>
                {
                    ["prompt_info"] = "000A519B", ["reply_info"] = "000A51A3", ["reply_response"] = 1,
                    ["button"] = InfoButtonText(0x0A519B, 1, SyntheticCodsworthChoices[1].Prompt),
                    ["prompt"] = InfoAllRespText(0x0A519B, SyntheticCodsworthChoices[1].Prompt),
                    ["reply"] = InfoAllRespText(0x0A51A3, SyntheticCodsworthChoices[1].Reply),
                    ["reply_responses"] = InfoRespList(0x0A51A3, SyntheticCodsworthChoices[1].Reply),
                },
                new Dictionary<string, object>
                {
                    ["prompt_info"] = "0019E113", ["reply_info"] = "0019E112", ["reply_response"] = 1,
                    ["button"] = InfoButtonText(0x19E113, 1, SyntheticCodsworthChoices[2].Prompt),
                    ["prompt"] = InfoAllRespText(0x19E113, SyntheticCodsworthChoices[2].Prompt),
                    ["reply"] = InfoAllRespText(0x19E112, SyntheticCodsworthChoices[2].Reply),
                    ["reply_responses"] = InfoRespList(0x19E112, SyntheticCodsworthChoices[2].Reply),
                },
                new Dictionary<string, object>
                {
                    ["prompt_info"] = "0019E70A", ["reply_info"] = "0019E711", ["reply_response"] = 1,
                    ["button"] = InfoButtonText(0x19E70A, 1, SyntheticCodsworthChoices[3].Prompt),
                    ["prompt"] = InfoAllRespText(0x19E70A, SyntheticCodsworthChoices[3].Prompt),
                    ["reply"] = InfoAllRespText(0x19E711, SyntheticCodsworthChoices[3].Reply),
                    ["reply_responses"] = InfoRespList(0x19E711, SyntheticCodsworthChoices[3].Reply),
                },
            },
        };

        var prestonPostTalk = new Dictionary<string, object?>
        {
            ["greeting_info"] = "000F5D0B",
            ["greeting"] = InfoAllRespText(0x0F5D0B, SyntheticPrestonPostGreet),
            ["greeting_responses"] = InfoRespList(0x0F5D0B, SyntheticPrestonPostGreet),
            ["choices"] = new object[]
            {
                new Dictionary<string, object>
                {
                    ["reply_info"] = "000F5D0D",
                    ["button"] = SyntheticPrestonPostButton,
                    ["prompt"] = SyntheticPrestonPostPrompt,
                    ["reply"] = InfoAllRespText(0x0F5D0D, SyntheticPrestonPostReply),
                    ["reply_responses"] = InfoRespList(0x0F5D0D, SyntheticPrestonPostReply),
                },
            },
        };

        var codsworthPostTalk = new Dictionary<string, object?>
        {
            ["greeting_info"] = "0001D152",
            ["greeting_response"] = 1,
            ["greeting"] = InfoAllRespText(0x01D152, SyntheticCodsworthPostGreet),
            ["greeting_responses"] = InfoRespList(0x01D152, SyntheticCodsworthPostGreet),
            ["choices"] = new object[]
            {
                new Dictionary<string, object>
                {
                    ["reply_info"] = "0001F157",
                    ["reply_response"] = 1,
                    ["button"] = SyntheticCodsworthPostButton,
                    ["prompt"] = SyntheticCodsworthPostPrompt,
                    ["reply"] = InfoAllRespText(0x01F157, SyntheticCodsworthPostReply),
                    ["reply_responses"] = InfoRespList(0x01F157, SyntheticCodsworthPostReply),
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
            ["preston_post_talk"] = prestonPostTalk,
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
            ["codsworth_post_talk"] = codsworthPostTalk,
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

    public static string ShortButtonText(string text, int maxLen = 48)
    {
        var clean = StripTokens(text);
        if (clean.Length <= maxLen) return clean;
        int cut = clean.LastIndexOf(' ', maxLen - 3);
        if (cut < 12) cut = maxLen - 3;
        return clean[..cut].TrimEnd() + "...";
    }

    static SF.Message MakeTalkMessage(ModKey modKey, uint id, string edid, string title, string desc, IReadOnlyList<string> buttons)
    {
        var msg = new SF.Message(new FormKey(modKey, id), SF.StarfieldRelease.Starfield)
        {
            EditorID = edid,
            Name = title,
            Description = desc,
            Flags = SF.Message.Flag.MessageBox,
        };
        foreach (var b in buttons) msg.MenuButtons.Add(new SF.MessageButton { Text = b });
        return msg;
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

    public static IEnumerable<SF.IPlacedNpcGetter> PersistentNpcRefs(SF.IStarfieldModGetter plug) =>
        plug.Cells.Records
            .SelectMany(b => b.SubBlocks)
            .SelectMany(sb => sb.Cells)
            .SelectMany(c => c.Persistent)
            .OfType<SF.IPlacedNpcGetter>();

    public static IEnumerable<SF.PlacedNpc> PersistentNpcRefsMutable(SF.StarfieldMod mod) =>
        mod.Cells.Records
            .SelectMany(b => b.SubBlocks)
            .SelectMany(sb => sb.Cells)
            .SelectMany(c => c.Persistent)
            .OfType<SF.PlacedNpc>();

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

    static SF.Condition GlobalIsZero(FormKey globKey)
    {
        var d = new SF.GetGlobalValueConditionData { RunOnType = SF.Condition.RunOnType.Subject };
        d.FirstParameter.Link.SetTo(globKey);
        return new SF.ConditionFloat { CompareOperator = SF.CompareOperator.EqualTo, ComparisonValue = 0f, Data = d };
    }

    static SF.DialogResponse MakeNpcDialogResponse(string text, uint wem, float durationSec, FormKey speakerVoiceKey)
    {
        float dur = durationSec > 0f ? durationSec : MathF.Max(1.5f, text.Length / 15f);
        var resp = new SF.DialogResponse
        {
            ResponseText = text,
            WEMFile = wem,
            EmotionOut = wem != 0u ? dur : 0f,
        };
        if (wem != 0u && !speakerVoiceKey.IsNull)
        {
            resp.TROTs.Add(new SF.DialogResponseTROT
            {
                VoiceType = new FormLink<SF.IVoiceTypeGetter>(speakerVoiceKey),
                EmotionOut = dur,
            });
        }
        return resp;
    }

    static SF.Scene BuildTopScene(
        ModKey modKey,
        SF.Quest quest,
        FormKey speakerNpcKey,
        FormKey speakerVoiceKey,
        SF.Condition stageGate,
        uint sceneId,
        string sceneEdid,
        uint greetTopicId,
        string greetTopicEdid,
        uint greetInfoId,
        string greetInfoEdid,
        IReadOnlyList<(string Text, uint Wem, float Duration)> greetResponses,
        uint firstChoiceTopicId,
        uint firstChoiceInfoId,
        uint firstReplyTopicId,
        uint firstReplyInfoId,
        string prefixEdid,
        float priority,
        IReadOnlyList<(string Prompt, IReadOnlyList<(string Text, uint Wem, float Duration)> Replies, short EndStage, bool Goodbye)> choices,
        uint aliasId = 0,
        SF.Scene? existingScene = null)
    {
        var rel = SF.StarfieldRelease.Starfield;
        var greetTopic = new SF.DialogTopic(new FormKey(modKey, greetTopicId), rel)
        {
            EditorID = greetTopicEdid,
            FormVersion = 581,
            Quest = new FormLink<SF.IQuestGetter>(quest.FormKey),
            Priority = priority,
            Category = SF.DialogTopic.CategoryEnum.Scene,
            Subtype = SF.DialogTopic.SubtypeEnum.CustomScene,
            SubtypeName = SF.DialogTopic.SubtypeNameEnum.CustomScene,
        };
        var greetInfo = new SF.DialogResponses(new FormKey(modKey, greetInfoId), rel)
        {
            EditorID = greetInfoEdid,
            FormVersion = 581,
            Flags = new SF.DialogResponseFlags { Flags = 0, ResetHours = 0f },
            SubtitlePriority = SF.DialogResponses.SubtitlePriorityLevel.Low,
        };
        foreach (var gr in greetResponses)
            greetInfo.Responses.Add(MakeNpcDialogResponse(gr.Text, gr.Wem, gr.Duration, speakerVoiceKey));
        greetInfo.Conditions.Add(SpeakerIs(speakerNpcKey));
        greetTopic.Responses.Add(greetInfo);
        (greetTopic.TopicInfoList ??= new()).Add(new FormLink<SF.IDialogResponsesGetter>(greetInfo.FormKey));
        quest.DialogTopics.Add(greetTopic);

        // T6 & A1(d) fix: Direct E-Talk NPC scenes in Starfield (e.g. 2B0785) require DEVT = true, Flags = 0x1814
        // (NoFollowerIdleChatter 0x1000 | DisableDialogueCamera 0x0800 | Interruptable 0x0010 | ShowAllText 0x0004),
        // SCPI = null, SceneActor ID = aliasId, and FO4SF_MissionTalkUseMessageBox (0x979) == 0 condition gate.
        var topScene = existingScene ?? new SF.Scene(new FormKey(modKey, sceneId), rel);
        topScene.EditorID = sceneEdid;
        topScene.FormVersion = 581;
        topScene.Quest = new FormLinkNullable<SF.IQuestGetter>(quest.FormKey);
        topScene.Flags = (SF.Scene.Flag)0x1814;
        topScene.DEVT = true;
        topScene.Index = 0;
        topScene.LastActionIndex = 2;
        topScene.SCPI = null;
        topScene.VNAM = new byte[] { 3, 0, 0, 0, 3, 0, 0, 0, 3, 0, 0, 0, 3, 0, 0, 0, 3, 0, 0, 0 };
        topScene.Conditions.Add(SpeakerIs(speakerNpcKey));
        topScene.Conditions.Add(stageGate);
        topScene.Conditions.Add(GlobalIsZero(new FormKey(modKey, MissionTalkUseMessageBoxGlobId)));
        topScene.Actors.Add(new SF.SceneActor
        {
            ID = aliasId,
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
            AliasID = (int)aliasId,
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
            AliasID = (int)aliasId,
            DialogueTargetActor = (int)aliasId,
            StartPhase = 1,
            EndPhase = 1,
        };

        for (uint idx = 0; idx < (uint)choices.Count; idx++)
        {
            var c = choices[(int)idx];
            var pcTopic = new SF.DialogTopic(new FormKey(modKey, firstChoiceTopicId + idx), rel)
            {
                EditorID = $"{prefixEdid}_ChoiceTopic_{idx}",
                FormVersion = 581,
                Quest = new FormLink<SF.IQuestGetter>(quest.FormKey),
                Priority = priority,
                Category = SF.DialogTopic.CategoryEnum.Scene,
                Subtype = SF.DialogTopic.SubtypeEnum.CustomScene,
                SubtypeName = SF.DialogTopic.SubtypeNameEnum.CustomScene,
            };
            // R11 D5 Part 3: Starfield PlayerDialogue PC INFOs carry explicit ENAM (Flags=0, DoNotGrayOut clear) and
            // INAM (SubtitlePriority=Low) across 20,731/20,731 vanilla choices so DialogueMenu greys out asked options.
            var pcInfo = new SF.DialogResponses(new FormKey(modKey, firstChoiceInfoId + idx), rel)
            {
                EditorID = $"{prefixEdid}_ChoiceInfo_{idx}",
                FormVersion = 581,
                Flags = new SF.DialogResponseFlags { Flags = 0, ResetHours = 0f },
                SubtitlePriority = SF.DialogResponses.SubtitlePriorityLevel.Low,
                Prompt = c.Prompt,
            };
            pcInfo.Responses.Add(new SF.DialogResponse { ResponseText = c.Prompt, WEMFile = 0 });
            pcTopic.Responses.Add(pcInfo);
            (pcTopic.TopicInfoList ??= new()).Add(new FormLink<SF.IDialogResponsesGetter>(pcInfo.FormKey));
            quest.DialogTopics.Add(pcTopic);

            var npcTopic = new SF.DialogTopic(new FormKey(modKey, firstReplyTopicId + idx), rel)
            {
                EditorID = $"{prefixEdid}_ReplyTopic_{idx}",
                FormVersion = 581,
                Quest = new FormLink<SF.IQuestGetter>(quest.FormKey),
                Priority = priority,
                Category = SF.DialogTopic.CategoryEnum.Scene,
                Subtype = SF.DialogTopic.SubtypeEnum.CustomScene,
                SubtypeName = SF.DialogTopic.SubtypeNameEnum.CustomScene,
            };
            var npcInfo = new SF.DialogResponses(new FormKey(modKey, firstReplyInfoId + idx), rel)
            {
                EditorID = $"{prefixEdid}_ReplyInfo_{idx}",
                FormVersion = 581,
                SubtitlePriority = SF.DialogResponses.SubtitlePriorityLevel.Low,
            };
            if (c.EndStage > 0)
                npcInfo.SetParentQuestStage = new SF.DialogSetParentQuestStage { OnBegin = -1, OnEnd = c.EndStage };
            if (c.Goodbye)
                npcInfo.Flags = new SF.DialogResponseFlags { Flags = 1, ResetHours = 0f };
            else
            {
                // C2: Starfield TSCE uses INTV (4-byte LE phase index) alongside NAM0 (StartScenePhase) to jump
                // directly to Phase 1 (TOPLEVELNEST) without replaying Phase 0 greeting (verified vs Starfield.esm 0028D90C/0002573C).
                npcInfo.Flags = new SF.DialogResponseFlags { Flags = 0, ResetHours = 0f };
                npcInfo.StartScene = new FormLinkNullable<SF.ISceneGetter>(topScene.FormKey);
                npcInfo.StartScenePhase = "TOPLEVELNEST";
                npcInfo.INTV = new byte[] { 1, 0, 0, 0 };
            }
            foreach (var rp in c.Replies)
                npcInfo.Responses.Add(MakeNpcDialogResponse(rp.Text, rp.Wem, rp.Duration, speakerVoiceKey));
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

    public sealed record MqVoiceSpec(
        uint GreetingWem,
        uint[] ChoiceReplyWems,
        (uint Wem, float Duration)[] GreetingClips,
        (uint Wem, float Duration)[][] ReplyClips);

    public static MqVoiceSpec LoadSceneVoice(string path, int expectedChoices, string label)
    {
        using var doc = JsonDocument.Parse(File.ReadAllText(path));
        var root = doc.RootElement;
        uint greet = uint.Parse(root.GetProperty("greeting_wem").GetString()!, NumberStyles.HexNumber, CultureInfo.InvariantCulture);
        var replies = root.GetProperty("reply_wems").EnumerateArray()
            .Select(x => uint.Parse(x.GetString()!, NumberStyles.HexNumber, CultureInfo.InvariantCulture)).ToArray();
        if (replies.Length != expectedChoices) throw new Refusal($"{path}: expected {expectedChoices} reply_wems for {label}, got {replies.Length}");

        static (uint Wem, float Duration) ParseClip(JsonElement el)
        {
            uint w = uint.Parse(el.GetProperty("wem").GetString()!, NumberStyles.HexNumber, CultureInfo.InvariantCulture);
            float d = el.TryGetProperty("duration", out var de) && de.ValueKind == JsonValueKind.Number ? de.GetSingle() : 0f;
            return (w, d);
        }

        var gClips = root.TryGetProperty("greeting_clips", out var gcEl) && gcEl.ValueKind == JsonValueKind.Array && gcEl.GetArrayLength() > 0
            ? gcEl.EnumerateArray().Select(ParseClip).ToArray()
            : new (uint Wem, float Duration)[] { (greet, 0f) };

        var rClips = new (uint Wem, float Duration)[expectedChoices][];
        if (root.TryGetProperty("reply_clips", out var rcEl) && rcEl.ValueKind == JsonValueKind.Array && rcEl.GetArrayLength() == expectedChoices)
        {
            int idx = 0;
            foreach (var arr in rcEl.EnumerateArray())
            {
                rClips[idx] = arr.ValueKind == JsonValueKind.Array && arr.GetArrayLength() > 0
                    ? arr.EnumerateArray().Select(ParseClip).ToArray()
                    : new (uint Wem, float Duration)[] { (replies[idx], 0f) };
                idx++;
            }
        }
        else
        {
            for (int idx = 0; idx < expectedChoices; idx++)
                rClips[idx] = new (uint Wem, float Duration)[] { (replies[idx], 0f) };
        }

        if (gClips[0].Wem != greet || Enumerable.Range(0, expectedChoices).Any(i => rClips[i][0].Wem != replies[i]))
            throw new Refusal($"{path}: first clip wem mismatch in {label}");
        var allWems = gClips.Select(c => c.Wem).Concat(rClips.SelectMany(arr => arr.Select(c => c.Wem))).ToArray();
        if (allWems.Any(w => w == 0) || allWems.Distinct().Count() != allWems.Length)
            throw new Refusal($"{path}: duplicate or zero {label} wem id");
        return new MqVoiceSpec(greet, replies, gClips, rClips);
    }

    public static MqVoiceSpec LoadMqVoice(string path) => LoadSceneVoice(path, 4, "MQ102");

    static IReadOnlyList<(string Text, uint Wem, float Duration)> PairSceneClips(
        IReadOnlyList<string> texts,
        IReadOnlyList<(uint Wem, float Duration)>? clips)
    {
        if (clips is null || clips.Count == 0)
            return texts.Select(t => (t, 0u, 0f)).ToArray();
        if (texts.Count == clips.Count)
            return texts.Zip(clips, (t, c) => (t, c.Wem, c.Duration)).ToArray();
        if (clips.Count == 1)
            return new[] { (string.Join(" ", texts), clips[0].Wem, clips[0].Duration) };
        var result = new List<(string Text, uint Wem, float Duration)>(clips.Count);
        for (int i = 0; i < clips.Count; i++)
        {
            string t = i < texts.Count ? texts[i] : texts[^1];
            result.Add((t, clips[i].Wem, clips[i].Duration));
        }
        return result;
    }

    static List<string> ExtractRespTexts(JsonElement parent, string arrayProp, string fallbackText)
    {
        if (parent.TryGetProperty(arrayProp, out var arr) && arr.ValueKind == JsonValueKind.Array && arr.GetArrayLength() > 0)
        {
            var list = arr.EnumerateArray()
                .Select(e => e.TryGetProperty("text", out var te) ? te.GetString() : null)
                .Where(s => !string.IsNullOrWhiteSpace(s))
                .Select(s => s!)
                .ToList();
            if (list.Count > 0) return list;
        }
        return new List<string> { fallbackText };
    }

    public static int Write(string sfPath, string corePath, string raiderPath, string pointsPath, string outDir, string plugin,
                            string worldEdid, bool alias, string? codsworthBody = CodsworthBody, string? codsworthModel = null,
                            string? codsworthVoice = null, string? codsworthMqVoice = null, string? prestonVoicePath = null,
                            string? actorLooksDir = null, bool codsworthRaceFraming = false)
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
        if (!m.Cache.TryResolve<SF.IWeaponGetter>(new FormKey(SfEsm, SfRaiderWeaponId), out var raiderWeapon) || raiderWeapon.EditorID != SfRaiderWeaponEdid)
            throw new Refusal($"Starfield.esm {SfRaiderWeaponId:X6} is not the WEAP {SfRaiderWeaponEdid}");
        if (!m.Cache.TryResolve<SF.IAmmunitionGetter>(new FormKey(SfEsm, SfRaiderAmmoId), out var raiderAmmo) || raiderAmmo.EditorID != SfRaiderAmmoEdid)
            throw new Refusal($"Starfield.esm {SfRaiderAmmoId:X6} is not the AMMO {SfRaiderAmmoEdid}");
        if (!m.Cache.TryResolve<SF.IWeaponGetter>(new FormKey(SfEsm, SfRaiderSidearmId), out var raiderSidearm) || raiderSidearm.EditorID != SfRaiderSidearmEdid)
            throw new Refusal($"Starfield.esm {SfRaiderSidearmId:X6} is not the WEAP {SfRaiderSidearmEdid}");
        if (!m.Cache.TryResolve<SF.IAmmunitionGetter>(new FormKey(SfEsm, SfRaiderSidearmAmmoId), out var raiderSidearmAmmo) || raiderSidearmAmmo.EditorID != SfRaiderSidearmAmmoEdid)
            throw new Refusal($"Starfield.esm {SfRaiderSidearmAmmoId:X6} is not the AMMO {SfRaiderSidearmAmmoEdid}");
        if (!m.Cache.TryResolve<SF.IPackageGetter>(new FormKey(SfEsm, RaiderCombatPackageId), out var raiderCombatPack) || raiderCombatPack.EditorID != RaiderCombatPackageEdid)
            throw new Refusal($"Starfield.esm {RaiderCombatPackageId:X6} is not the PACK {RaiderCombatPackageEdid}");
        if (!m.Cache.TryResolve<SF.IPackageGetter>(new FormKey(SfEsm, RaiderSandboxPackageId), out var raiderSandboxPack) || raiderSandboxPack.EditorID != RaiderSandboxPackageEdid)
            throw new Refusal($"Starfield.esm {RaiderSandboxPackageId:X6} is not the PACK {RaiderSandboxPackageEdid}");

        var raiderNpc = m.Raider.Npcs.FirstOrDefault(n => n.FormKey.ID == RaiderId && n.EditorID == "FO4_LvlRaider")
                        ?? throw new Refusal($"{m.Raider.ModKey} has no F04800 FO4_LvlRaider");
        var world = FindWorld(m.Core, worldEdid);

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
        npc.DefaultTemplate.Clear();
        npc.TemplateActors = null;
        npc.CrimeFaction.Clear();
        npc.ActivateTextOverride = "Talk";
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
        // Task 0d: Keep Preston passive and avoid auto-assisting against Concord raiders so raiders lock onto the player.
        npc.Aggression = SF.Npc.AggressionType.Unaggressive;
        npc.Assistance = SF.Npc.AssistanceType.HelpsNobody;
        mod.Npcs.Add(npc);

        // Task 1i: Mission-owned interior holding cell (0x000B60) holds persistent ACHRs with 0 WRLD overrides,
        // so FO4SFMission.esm never copies FO4Core_Commonwealth or Starfield's Mars biome (0x002A3777).
        var cell = new SF.Cell(new FormKey(modKey, MissionHoldingCellId), SF.StarfieldRelease.Starfield)
        {
            EditorID = MissionHoldingCellEdid,
            Name = "Commonwealth Holding",
            FormVersion = 581,
            Flags = SF.Cell.Flag.IsInteriorCell,
        };
        var cellSub = new SF.CellSubBlock { BlockNumber = (int)((MissionHoldingCellId / 10) % 10), GroupType = SF.GroupTypeEnum.InteriorCellSubBlock };
        cellSub.Cells.Add(cell);
        var cellBlock = new SF.CellBlock { BlockNumber = (int)(MissionHoldingCellId % 10), GroupType = SF.GroupTypeEnum.InteriorCellBlock };
        cellBlock.SubBlocks.Add(cellSub);
        mod.Cells.Records.Add(cellBlock);
        var coreNavs = NavmeshSnap.LoadWorldNavmeshes(corePath);
        SF.PlacedNpc Ach(uint id, FormKey baseKey, string edid, JsonElement e, float dx = 0f, float dy = 0f)
        {
            var p = Floats(e.GetProperty("pos"));
            var r = Floats(e.GetProperty("rot"));
            float z = p[2];
            if (NavmeshSnap.TryFindFloorZ(coreNavs, p[0], p[1], p[2], out var floorZ))
            {
                Console.WriteLine($"  navmesh snap {edid}: z {p[2]:F3} -> {floorZ:F3} (dz={floorZ - p[2]:+0.000;-0.000;+0.000} m)");
                z = floorZ;
            }
            var a = new SF.PlacedNpc(new FormKey(modKey, id), SF.StarfieldRelease.Starfield)
            {
                EditorID = edid, Base = new FormLink<SF.INpcGetter>(baseKey),
                Position = new P3Float(p[0] + dx, p[1] + dy, z), Rotation = new P3Float(r[0], r[1], r[2]),
            };
            a.MajorRecordFlagsRaw |= 0x400;
            cell.Persistent.Add(a);
            return a;
        }
        var prestonRef = Ach(PrestonRefId, npc.FormKey, PrestonRefEdid, pts.GetProperty("preston"));
        var raiderRefs = new List<SF.PlacedNpc>();
        uint next = FirstRaiderRefId;
        // C3: Author Concord raider ACHRs at merged Concord coordinates so their Editor Location is Concord,
        // preventing Starfield's low-process sandbox/editor-location AI from walking them 2.85 km home.
        foreach (var r in pts.GetProperty("raiders").EnumerateArray())
            raiderRefs.Add(Ach(next++, raiderNpc.FormKey, $"FO4SF_Min00_Raider_{r.GetProperty("src").GetString()}", r, MergeOffsetX, MergeOffsetY));
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

            // 2h & R11 Review Item #6: Duplicate MiniBotARace with AllowPcDialog + ArmorRace only by default
            // (--codsworth-race-framing 0, exact 2g parity).
            // Passing --codsworth-race-framing 1 opts into the 5 standing-robot dialogue framing edits for variant testing.
            var codsRace = (SF.Race)baseBotRace.Duplicate(new FormKey(modKey, CodsworthRaceId));
            codsRace.EditorID = CodsworthRaceEdid;
            codsRace.Flags |= SF.Race.Flag.AllowPcDialog;
            if (codsworthRaceFraming)
            {
                codsRace.Flags = (codsRace.Flags | SF.Race.Flag.HeadAxisBit0 |
                                  (SF.Race.Flag)0x0080000000000000UL) & ~SF.Race.Flag.TiltFrontBack;
                codsRace.Size = SF.Size.Medium;
                codsRace.DialogueQuest.Clear();
                if (m.Cache.TryResolve<SF.IRaceGetter>(new FormKey(SfEsm, SfModelARaceId), out var modelARace) &&
                    modelARace.EditorID == SfModelARaceEdid &&
                    modelARace.DAT2Unknown3.Length == codsRace.DAT2Unknown3.Length &&
                    modelARace.DAT2Unknown3.Length > 0)
                {
                    codsRace.DAT2Unknown3 = modelARace.DAT2Unknown3.ToArray();
                }
            }
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
            cods.Packages.Clear();
            cods.DefaultTemplate.Clear();
            cods.TemplateActors = null;
            cods.CrimeFaction.Clear();
            cods.Keywords?.Clear();
            cods.ActivateTextOverride = "Talk";
            cods.ObjectBounds = new SF.ObjectBounds
            {
                First = new P3Float(-0.65f, -0.65f, 0f),
                Second = new P3Float(0.65f, 0.65f, 1.80f),
            };
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

        // 2b: FO4SF_Min00 (0x800) — non-StartGameEnabled (started via StartNoWait at FO4SFNewGame stage 200)
        var objText = pts.GetProperty("objectives");
        var quest = new SF.Quest(new FormKey(modKey, QuestId), SF.StarfieldRelease.Starfield)
        {
            EditorID = QuestEdid, Name = pts.GetProperty("quest_name").GetString(), FormVersion = 581, Version2 = 12,
            Data = new SF.QuestData
            {
                Flags = SF.Quest.Flag.AllowRepeatedStages | SF.Quest.Flag.DisplaysInHud |
                        SF.Quest.Flag.RunOnce | SF.Quest.Flag.HasDialogueData,
                Priority = 50,
            },
        };
        quest.QuestType.SetTo(qtyp.FormKey);
        foreach (var s in Stages)
        {
            var st = new SF.QuestStage { Index = s };
            st.LogEntries.Add(new SF.QuestLogEntry
            {
                Flags = s == 200 ? SF.QuestLogEntry.Flag.CompleteQuest : (SF.QuestLogEntry.Flag)0,
            });
            quest.Stages.Add(st);
        }
        foreach (var o in Objectives)
        {
            var obj = new SF.QuestObjective
            {
                Index = o.Index,
                Flags = (SF.QuestObjective.Flag)0,
                DisplayText = objText.GetProperty(o.Index.ToString(CultureInfo.InvariantCulture)).GetString(),
            };
            if (alias && o.TargetsPreston) obj.Targets.Add(new SF.QuestObjectiveTarget { AliasID = PrestonAlias });
            quest.Objectives.Add(obj);
        }

        SF.Scene? prestonScene = null;
        IReadOnlyList<(string Text, uint Wem, float Duration)>? prestonPostGreetPaired = null;
        (string Prompt, IReadOnlyList<(string Text, uint Wem, float Duration)> Replies, short EndStage, bool Goodbye)[]? prestonPostSceneChoices = null;
        if (alias)
        {
            (quest.Aliases ??= new ExtendedList<SF.AQuestAlias>()).Add(new SF.QuestReferenceAlias
            {
                ID = PrestonAlias, Name = "PrestonGarvey",
                Flags = SF.AQuestAlias.Flag.Optional | SF.AQuestAlias.Flag.AllowDead | SF.AQuestAlias.Flag.AllowDisabled |
                        SF.AQuestAlias.Flag.AllowReserved | SF.AQuestAlias.Flag.UsesStoredText,
                ForcedReference = new FormLinkNullable<SF.IPlacedGetter>(prestonRef.FormKey),
            });
            for (int ri = 0; ri < raiderRefs.Count; ri++)
            {
                var raiderAlias = new SF.QuestReferenceAlias
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
                };
                // C3: FO4_LvlRaider carries Coachman (0x26D96B) with UseInventory=0 and zero ammo;
                // supply matching AmmoShotshell (0x2B4AFB) directly on each raider alias so all 5 can fire immediately.
                raiderAlias.Items = new ExtendedList<SF.ContainerEntry>
                {
                    new SF.ContainerEntry
                    {
                        Item = new SF.ContainerItem
                        {
                            Item = new FormLink<SF.IItemGetter>(raiderAmmo.FormKey),
                            Count = RaiderAmmoCount,
                        },
                    },
                };
                quest.Aliases.Add(raiderAlias);
            }

            // 2g / B6 / A1(d): Preston 3-exchange voiced Starfield Scene on FO4SF_Min00 at stage 30 -> end stage 35 (advances to 40 by=info)
            string pGreet = "Synthetic Concord greeting.";
            var pGreetTexts = new List<string> { pGreet };
            var pReplyTextLists = SyntheticPrestonChoices.Select(c => new List<string> { c.Reply }).ToArray();
            var prestonWem = prestonVoicePath is null ? null : LoadSceneVoice(prestonVoicePath, 3, "Preston");
            var pChoices = SyntheticPrestonChoices.Select((c, idx) =>
                (c.Prompt, c.Reply, EndStage: idx == 2 ? (short)35 : (short)-1, Goodbye: idx == 2)).ToArray();
            var pButtons = new[]
            {
                ShortButtonText(SyntheticPrestonChoices[0].Prompt),
                ShortButtonText(SyntheticPrestonChoices[1].Prompt),
                ShortButtonText(SyntheticPrestonCampButton),
                ShortButtonText(SyntheticPrestonChoices[2].Prompt),
            };
            if (pts.TryGetProperty("preston_talk", out var ptEl) && ptEl.ValueKind == JsonValueKind.Object)
            {
                if (ptEl.TryGetProperty("greeting", out var gEl) && gEl.GetString() is { Length: > 0 } gs) pGreet = gs;
                pGreetTexts = ExtractRespTexts(ptEl, "greeting_responses", pGreet);
                if (ptEl.TryGetProperty("choices", out var chEl) && chEl.ValueKind == JsonValueKind.Array && chEl.GetArrayLength() == 3)
                {
                    int ci = 0;
                    foreach (var ce in chEl.EnumerateArray())
                    {
                        var pr = ce.GetProperty("prompt").GetString() ?? SyntheticPrestonChoices[ci].Prompt;
                        var rp = ce.GetProperty("reply").GetString() ?? SyntheticPrestonChoices[ci].Reply;
                        var btn = ce.TryGetProperty("button", out var bEl) && bEl.GetString() is { Length: > 0 } bs ? ShortButtonText(bs) : ShortButtonText(pr);
                        pChoices[ci] = (pr, rp, ci == 2 ? (short)35 : (short)-1, ci == 2);
                        pReplyTextLists[ci] = ExtractRespTexts(ce, "reply_responses", rp);
                        if (ci == 0) pButtons[0] = btn;
                        else if (ci == 1) pButtons[1] = btn;
                        else if (ci == 2) pButtons[3] = btn;
                        ci++;
                    }
                }
            }
            var pSceneChoices = pChoices.Select((c, idx) =>
                (c.Prompt, PairSceneClips(pReplyTextLists[idx], prestonWem?.ReplyClips[idx]), c.EndStage, c.Goodbye)).ToArray();
            var prestonGreetPaired = PairSceneClips(pGreetTexts, prestonWem?.GreetingClips);

            // Step 3: Post-mission Preston scene 0x990 uses short FO4 post-mission lines / 1-choice stand-in
            // (never replaying the 3 Concord meeting choices or mismatched Concord voice WEMs).
            string pPostGreet = SyntheticPrestonPostGreet;
            var pPostGreetTexts = new List<string> { pPostGreet };
            string pPostPrompt = SyntheticPrestonPostPrompt;
            var pPostReplyTexts = new List<string> { SyntheticPrestonPostReply };
            if (pts.TryGetProperty("preston_post_talk", out var pptEl) && pptEl.ValueKind == JsonValueKind.Object)
            {
                if (pptEl.TryGetProperty("greeting", out var gEl) && gEl.GetString() is { Length: > 0 } gs) pPostGreet = gs;
                pPostGreetTexts = ExtractRespTexts(pptEl, "greeting_responses", pPostGreet);
                if (pptEl.TryGetProperty("choices", out var chEl) && chEl.ValueKind == JsonValueKind.Array && chEl.GetArrayLength() >= 1)
                {
                    var ce = chEl.EnumerateArray().First();
                    pPostPrompt = ce.TryGetProperty("prompt", out var prEl) && prEl.GetString() is { Length: > 0 } ps ? ps : SyntheticPrestonPostPrompt;
                    var rp = ce.TryGetProperty("reply", out var rpEl) && rpEl.GetString() is { Length: > 0 } rs ? rs : SyntheticPrestonPostReply;
                    pPostReplyTexts = ExtractRespTexts(ce, "reply_responses", rp);
                }
            }
            prestonPostGreetPaired = PairSceneClips(pPostGreetTexts, null);
            prestonPostSceneChoices = new[]
            {
                (pPostPrompt, (IReadOnlyList<(string Text, uint Wem, float Duration)>)PairSceneClips(pPostReplyTexts, null), (short)-1, true),
            };
            prestonScene = BuildTopScene(
                modKey, quest, npc.FormKey, prestonVoice.FormKey,
                QuestStageCond(quest.FormKey, SF.CompareOperator.EqualTo, 30f),
                PrestonTalkSceneId, PrestonTalkSceneEdid,
                PrestonGreetTopicId, PrestonGreetTopicEdid,
                PrestonGreetInfoId, PrestonGreetInfoEdid,
                prestonGreetPaired,
                FirstPrestonChoiceTopicId, FirstPrestonChoiceInfoId,
                FirstPrestonReplyTopicId, FirstPrestonReplyInfoId,
                "FO4SF_Min00_Preston", 50f, pSceneChoices);

            string pTitle = npc.Name?.String ?? "Preston Garvey";
            mod.Messages.Add(MakeTalkMessage(modKey, PrestonTalkMsgId, PrestonTalkMsgEdid, pTitle, pGreet, pButtons));
            mod.Messages.Add(MakeTalkMessage(modKey, PrestonReply0MsgId, PrestonReply0MsgEdid, pTitle, pChoices[0].Reply, pButtons));
            mod.Messages.Add(MakeTalkMessage(modKey, PrestonReply1MsgId, PrestonReply1MsgEdid, pTitle, pChoices[1].Reply, pButtons));
            mod.Messages.Add(MakeTalkMessage(modKey, PrestonReply2MsgId, PrestonReply2MsgEdid, pTitle, SyntheticPrestonCampReply, pButtons));
        }

        // A1(d): GLOB 09000979 FO4SF_MissionTalkUseMessageBox (0.0 = real DialogueMenu SCEN primary; 1.0 = V2 MessageBox fallback)
        mod.Globals.Add(new SF.Global(new FormKey(modKey, MissionTalkUseMessageBoxGlobId), SF.StarfieldRelease.Starfield)
        {
            EditorID = MissionTalkUseMessageBoxGlobEdid,
            Data = 0f,
        });

        // R11/R13 Part 3 E3 + fix4: Softened Concord Raider sidearm (WEAP 0x097A, AttackDamage=1.5, ProjectilesCount=1,
        // AmmoType=0x04AD3E, AmmoList=null, ObjectTemplates & AttachParentSlots kept intact so model renders/fires, NonPlayable)
        var concordSidearm = (SF.Weapon)raiderSidearm.Duplicate(new FormKey(modKey, ConcordRaiderSidearmWeapId));
        concordSidearm.EditorID = ConcordRaiderSidearmWeapEdid;
        concordSidearm.Name = "Eon";
        concordSidearm.AttackDamage = ConcordRaiderSidearmDamage;
        concordSidearm.ProjectilesCount = ConcordRaiderSidearmProjectiles;
        concordSidearm.AmmoType.SetTo(raiderSidearmAmmo.FormKey);
        concordSidearm.AmmoList.SetToNull();
        concordSidearm.MajorFlags |= SF.Weapon.MajorFlag.NonPlayable;
        concordSidearm.NonPlayable = true;
        mod.Weapons.Add(concordSidearm);

        // R13 E3 + fix4 + Task 0d: Softened Concord Raider primary (WEAP 0x097B, duplicated from Coachman 0x26D96B with
        // AttackDamage=4.0, ProjectilesCount=1, AmmoType=0x2B4AFB, AmmoList=null, ObjectTemplates & AttachParentSlots kept intact, NonPlayable).
        var concordPrimary = (SF.Weapon)raiderWeapon.Duplicate(new FormKey(modKey, ConcordRaiderPrimaryWeapId));
        concordPrimary.EditorID = ConcordRaiderPrimaryWeapEdid;
        concordPrimary.Name = "Coachman";
        concordPrimary.AttackDamage = ConcordRaiderPrimaryDamage;
        concordPrimary.ProjectilesCount = ConcordRaiderPrimaryProjectiles;
        concordPrimary.AmmoType.SetTo(raiderAmmo.FormKey);
        concordPrimary.AmmoList.SetToNull();
        concordPrimary.MajorFlags |= SF.Weapon.MajorFlag.NonPlayable;
        concordPrimary.NonPlayable = true;
        mod.Weapons.Add(concordPrimary);

        float primaryRecordDamage = concordPrimary.AttackDamage * Math.Max(1, (int)concordPrimary.ProjectilesCount);
        float sidearmRecordDamage = concordSidearm.AttackDamage * Math.Max(1, (int)concordSidearm.ProjectilesCount);

        var startCfg = LoadMissionStartConfig();
        SF.ScriptBoolProperty BoolProp(string name, bool val) => new()
        {
            Name = name, Flags = SF.ScriptProperty.Flag.Edited, Data = val,
        };
        SF.ScriptStringProperty StrProp(string name, string val) => new()
        {
            Name = name, Flags = SF.ScriptProperty.Flag.Edited, Data = val,
        };
        var script = new SF.ScriptEntry { Name = ScriptName, Flags = SF.ScriptEntry.Flag.Local };
        SF.ScriptObjectProperty Obj(string name, FormKey fk) => new()
        {
            Name = name, Flags = SF.ScriptProperty.Flag.Edited, Object = new FormLink<SF.IStarfieldMajorRecordGetter>(fk), Alias = -1, Unused = 0,
        };
        SF.ScriptFloatProperty Flt(string name, float val) => new()
        {
            Name = name, Flags = SF.ScriptProperty.Flag.Edited, Data = val,
        };
        SF.ScriptObjectProperty CodsworthProp(string name, FormKey fk) => new()
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
        script.Properties.Add(Obj("RaiderWeapon", concordPrimary.FormKey));
        script.Properties.Add(Obj("RaiderAmmo", raiderAmmo.FormKey));
        script.Properties.Add(Obj("RaiderSidearm", concordSidearm.FormKey));
        script.Properties.Add(Obj("RaiderSidearmAmmo", raiderSidearmAmmo.FormKey));
        script.Properties.Add(Flt("RaiderPrimaryRecordDamage", primaryRecordDamage));
        script.Properties.Add(Flt("RaiderSidearmRecordDamage", sidearmRecordDamage));
        script.Properties.Add(BoolProp("MuteDuplicateObjectiveToasts", startCfg.MuteDuplicateObjectiveToasts));
        if (prestonScene is not null)
        {
            script.Properties.Add(Obj("PrestonTalkMsg", new FormKey(modKey, PrestonTalkMsgId)));
            script.Properties.Add(Obj("PrestonReply0Msg", new FormKey(modKey, PrestonReply0MsgId)));
            script.Properties.Add(Obj("PrestonReply1Msg", new FormKey(modKey, PrestonReply1MsgId)));
            script.Properties.Add(Obj("PrestonReply2Msg", new FormKey(modKey, PrestonReply2MsgId)));
            script.Properties.Add(Obj("TalkUseMessageBox", new FormKey(modKey, MissionTalkUseMessageBoxGlobId)));
        }

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
            // G13(a): Invisible model-less eye-level talk activator (no visible green decorator NIF)
            var codsTalkActi = new SF.Activator(new FormKey(modKey, CodsworthTalkActiId), SF.StarfieldRelease.Starfield)
            {
                EditorID = CodsworthTalkActiEdid,
                Name = cods.Name?.String ?? "Codsworth",
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
                Model = null,
            };
            mod.Activators.Add(codsTalkActi);

            // 2b / B1 / R11 Part 3: FO4SF_CodsworthKeeper (0x814) — non-StartGameEnabled, no StartsEnabled/0x10000 dormancy bits;
            // hosts non-completing repeat Starfield Scenes FO4SF_PrestonPostScene (0x990, alias 0) & FO4SF_CodsworthPostScene (0x9C0, alias 1).
            keeper = new SF.Quest(new FormKey(modKey, KeeperQuestId), SF.StarfieldRelease.Starfield)
            {
                EditorID = KeeperEdid, FormVersion = 581, Version2 = 12,
                Data = new SF.QuestData
                {
                    Flags = SF.Quest.Flag.AllowRepeatedStages | SF.Quest.Flag.HasDialogueData,
                    Priority = 50,
                },
            };
            (keeper.Aliases ??= new ExtendedList<SF.AQuestAlias>()).Add(new SF.QuestReferenceAlias
            {
                ID = KeeperPrestonAlias, Name = "PrestonGarvey",
                Flags = SF.AQuestAlias.Flag.Optional | SF.AQuestAlias.Flag.AllowDead | SF.AQuestAlias.Flag.AllowDisabled |
                        SF.AQuestAlias.Flag.AllowReserved | SF.AQuestAlias.Flag.UsesStoredText,
                ForcedReference = new FormLinkNullable<SF.IPlacedGetter>(prestonRef.FormKey),
            });
            keeper.Aliases.Add(new SF.QuestReferenceAlias
            {
                ID = KeeperCodsworthAlias, Name = "Codsworth",
                Flags = SF.AQuestAlias.Flag.Optional | SF.AQuestAlias.Flag.AllowDead | SF.AQuestAlias.Flag.AllowDisabled |
                        SF.AQuestAlias.Flag.AllowReserved | SF.AQuestAlias.Flag.UsesStoredText,
                ForcedReference = new FormLinkNullable<SF.IPlacedGetter>(codsRef.FormKey),
            });
            var ks = new SF.ScriptEntry { Name = ScriptName, Flags = SF.ScriptEntry.Flag.Local };
            MissionProps(ks);
            ks.Properties.Add(Obj("Codsworth", codsRef.FormKey));
            ks.Properties.Add(new SF.ScriptBoolProperty { Name = "KeeperOnly", Flags = SF.ScriptProperty.Flag.Edited, Data = true });
            keeper.VirtualMachineAdapter = Adapter(ks);

            if (alias && prestonPostGreetPaired is not null && prestonPostSceneChoices is not null)
            {
                var prestonPostScnObj = new SF.Scene(new FormKey(modKey, PrestonPostTalkSceneId), SF.StarfieldRelease.Starfield)
                {
                    EditorID = PrestonPostTalkSceneEdid,
                };
                BuildTopScene(
                    modKey, keeper, npc.FormKey, prestonVoice.FormKey,
                    QuestStageCond(quest.FormKey, SF.CompareOperator.GreaterThanOrEqualTo, 200f),
                    PrestonPostTalkSceneId, PrestonPostTalkSceneEdid,
                    PrestonPostGreetTopicId, PrestonPostGreetTopicEdid,
                    PrestonPostGreetInfoId, PrestonPostGreetInfoEdid,
                    prestonPostGreetPaired,
                    FirstPrestonPostChoiceTopicId, FirstPrestonPostChoiceInfoId,
                    FirstPrestonPostReplyTopicId, FirstPrestonPostReplyInfoId,
                    "FO4SF_PrestonPost", 50f, prestonPostSceneChoices,
                    KeeperPrestonAlias, prestonPostScnObj);
            }

            // 2h & 2b & A1(d): FO4SF_Codsworth01 (0x816) — MQ102-lite 4-choice voiced Sanctuary quest, non-StartGameEnabled
            string cqName = "Synthetic Sanctuary Inquiry";
            string cqObj10 = "Speak with the household robot";
            string cqGreet = "Synthetic robot greeting.";
            var cqGreetTexts = new List<string> { cqGreet };
            var cqReplyTextLists = SyntheticCodsworthChoices.Select(c => new List<string> { c.Reply }).ToArray();
            var mqWem = codsworthMqVoice is null ? null : LoadMqVoice(codsworthMqVoice);
            var cqChoices = SyntheticCodsworthChoices.Select((c, idx) =>
                (c.Prompt, c.Reply, EndStage: CodsworthChoiceEndStages[idx], Goodbye: idx == 3)).ToArray();
            var cqButtons = SyntheticCodsworthChoices.Select(c => ShortButtonText(c.Prompt)).ToArray();

            if (pts.TryGetProperty("codsworth_quest", out var cqEl) && cqEl.ValueKind == JsonValueKind.Object)
            {
                if (cqEl.TryGetProperty("name", out var nEl) && nEl.GetString() is { Length: > 0 } ns) cqName = ns;
                if (cqEl.TryGetProperty("objective_10", out var oEl) && oEl.GetString() is { Length: > 0 } os) cqObj10 = os;
                if (cqEl.TryGetProperty("greeting", out var gEl) && gEl.GetString() is { Length: > 0 } gs) cqGreet = gs;
                cqGreetTexts = ExtractRespTexts(cqEl, "greeting_responses", cqGreet);
                if (cqEl.TryGetProperty("choices", out var chEl) && chEl.ValueKind == JsonValueKind.Array && chEl.GetArrayLength() == 4)
                {
                    int ci = 0;
                    foreach (var ce in chEl.EnumerateArray())
                    {
                        var pr = ce.GetProperty("prompt").GetString() ?? SyntheticCodsworthChoices[ci].Prompt;
                        var rp = ce.GetProperty("reply").GetString() ?? SyntheticCodsworthChoices[ci].Reply;
                        var btn = ce.TryGetProperty("button", out var bEl) && bEl.GetString() is { Length: > 0 } bs ? ShortButtonText(bs) : ShortButtonText(pr);
                        cqChoices[ci] = (pr, rp, CodsworthChoiceEndStages[ci], ci == 3);
                        cqReplyTextLists[ci] = ExtractRespTexts(ce, "reply_responses", rp);
                        cqButtons[ci] = btn;
                        ci++;
                    }
                }
            }

            string cTitle = cods.Name?.String ?? "Codsworth";
            mod.Messages.Add(MakeTalkMessage(modKey, CodsworthTalkMsgId, CodsworthTalkMsgEdid, cTitle, cqGreet, cqButtons));
            mod.Messages.Add(MakeTalkMessage(modKey, CodsworthReply0MsgId, CodsworthReply0MsgEdid, cTitle, cqChoices[0].Reply, cqButtons));
            mod.Messages.Add(MakeTalkMessage(modKey, CodsworthReply1MsgId, CodsworthReply1MsgEdid, cTitle, cqChoices[1].Reply, cqButtons));
            mod.Messages.Add(MakeTalkMessage(modKey, CodsworthReply2MsgId, CodsworthReply2MsgEdid, cTitle, cqChoices[2].Reply, cqButtons));

            codsworthQuest = new SF.Quest(new FormKey(modKey, CodsworthQuestId), SF.StarfieldRelease.Starfield)
            {
                EditorID = CodsworthQuestEdid, Name = cqName, FormVersion = 581, Version2 = 12,
                Data = new SF.QuestData
                {
                    Flags = SF.Quest.Flag.AllowRepeatedStages | SF.Quest.Flag.DisplaysInHud |
                            SF.Quest.Flag.RunOnce | SF.Quest.Flag.HasDialogueData,
                    Priority = 55,
                },
            };
            codsworthQuest.QuestType.SetTo(qtyp.FormKey);
            foreach (var stIdx in CodsworthQuestStages)
            {
                var st = new SF.QuestStage { Index = stIdx };
                st.LogEntries.Add(new SF.QuestLogEntry
                {
                    Flags = stIdx == 100 ? SF.QuestLogEntry.Flag.CompleteQuest : (SF.QuestLogEntry.Flag)0,
                });
                codsworthQuest.Stages.Add(st);
            }
            (codsworthQuest.Aliases ??= new ExtendedList<SF.AQuestAlias>()).Add(new SF.QuestReferenceAlias
            {
                ID = CodsworthAlias, Name = "Codsworth",
                Flags = SF.AQuestAlias.Flag.Optional | SF.AQuestAlias.Flag.AllowDead | SF.AQuestAlias.Flag.AllowDisabled |
                        SF.AQuestAlias.Flag.AllowReserved | SF.AQuestAlias.Flag.UsesStoredText,
                ForcedReference = new FormLinkNullable<SF.IPlacedGetter>(codsRef.FormKey),
            });
            var cqObj = new SF.QuestObjective { Index = 10, Flags = (SF.QuestObjective.Flag)0, DisplayText = cqObj10 };
            cqObj.Targets.Add(new SF.QuestObjectiveTarget { AliasID = CodsworthAlias });
            codsworthQuest.Objectives.Add(cqObj);

            var cqGreetPaired = PairSceneClips(cqGreetTexts, mqWem?.GreetingClips);
            var cqSceneChoices = cqChoices.Select((c, idx) =>
                (c.Prompt, PairSceneClips(cqReplyTextLists[idx], mqWem?.ReplyClips[idx]), c.EndStage, c.Goodbye)).ToArray();
            BuildTopScene(
                modKey, codsworthQuest, cods.FormKey, new FormKey(modKey, CodsworthVoiceId),
                QuestStageCond(codsworthQuest.FormKey, SF.CompareOperator.LessThan, 100f),
                CodsworthSceneId, CodsworthSceneEdid,
                CodsworthGreetTopicId, CodsworthGreetTopicEdid,
                CodsworthGreetInfoId, CodsworthGreetInfoEdid,
                cqGreetPaired,
                FirstCodsworthChoiceTopicId, FirstCodsworthChoiceInfoId,
                FirstCodsworthReplyTopicId, FirstCodsworthReplyInfoId,
                "FO4SF_Codsworth01", 55f, cqSceneChoices);

            // Step 3: Post-mission Codsworth scene 0x9C0 uses DialogueCodsworthPostWar (0x01E64E) / 1-choice stand-in
            // (never replaying the 4 MQ102 first-meeting choices or mismatched MQ102 audio).
            string cqPostGreet = SyntheticCodsworthPostGreet;
            var cqPostGreetTexts = new List<string> { cqPostGreet };
            string cqPostPrompt = SyntheticCodsworthPostPrompt;
            var cqPostReplyTexts = new List<string> { SyntheticCodsworthPostReply };
            if (pts.TryGetProperty("codsworth_post_talk", out var cptEl) && cptEl.ValueKind == JsonValueKind.Object)
            {
                if (cptEl.TryGetProperty("greeting", out var gEl) && gEl.GetString() is { Length: > 0 } gs) cqPostGreet = gs;
                cqPostGreetTexts = ExtractRespTexts(cptEl, "greeting_responses", cqPostGreet);
                if (cptEl.TryGetProperty("choices", out var chEl) && chEl.ValueKind == JsonValueKind.Array && chEl.GetArrayLength() >= 1)
                {
                    var ce = chEl.EnumerateArray().First();
                    cqPostPrompt = ce.TryGetProperty("prompt", out var prEl) && prEl.GetString() is { Length: > 0 } ps ? ps : SyntheticCodsworthPostPrompt;
                    var rp = ce.TryGetProperty("reply", out var rpEl) && rpEl.GetString() is { Length: > 0 } rs ? rs : SyntheticCodsworthPostReply;
                    cqPostReplyTexts = ExtractRespTexts(ce, "reply_responses", rp);
                }
            }
            var cqPostGreetPaired = PairSceneClips(cqPostGreetTexts, null);
            var cqPostChoices = new[]
            {
                (cqPostPrompt, (IReadOnlyList<(string Text, uint Wem, float Duration)>)PairSceneClips(cqPostReplyTexts, null), (short)-1, true),
            };
            var codsworthPostScnObj = new SF.Scene(new FormKey(modKey, CodsworthPostSceneId), SF.StarfieldRelease.Starfield)
            {
                EditorID = CodsworthPostSceneEdid,
            };
            var codsworthPostScene = BuildTopScene(
                modKey, keeper, cods.FormKey, new FormKey(modKey, CodsworthVoiceId),
                QuestStageCond(codsworthQuest.FormKey, SF.CompareOperator.GreaterThanOrEqualTo, 100f),
                CodsworthPostSceneId, CodsworthPostSceneEdid,
                CodsworthPostGreetTopicId, CodsworthPostGreetTopicEdid,
                CodsworthPostGreetInfoId, CodsworthPostGreetInfoEdid,
                cqPostGreetPaired,
                FirstCodsworthPostChoiceTopicId, FirstCodsworthPostChoiceInfoId,
                FirstCodsworthPostReplyTopicId, FirstCodsworthPostReplyInfoId,
                "FO4SF_CodsworthPost", 55f, cqPostChoices,
                KeeperCodsworthAlias, codsworthPostScnObj);

            var cwScript = new SF.ScriptEntry { Name = CodsworthScriptName, Flags = SF.ScriptEntry.Flag.Local };
            cwScript.Properties.Add(CodsworthProp("Codsworth", codsRef.FormKey));
            cwScript.Properties.Add(CodsworthProp("CodsworthTalkActi", new FormKey(modKey, CodsworthTalkActiId)));
            cwScript.Properties.Add(CodsworthProp("CodsworthTalkMsg", new FormKey(modKey, CodsworthTalkMsgId)));
            cwScript.Properties.Add(CodsworthProp("CodsworthReply0Msg", new FormKey(modKey, CodsworthReply0MsgId)));
            cwScript.Properties.Add(CodsworthProp("CodsworthReply1Msg", new FormKey(modKey, CodsworthReply1MsgId)));
            cwScript.Properties.Add(CodsworthProp("CodsworthReply2Msg", new FormKey(modKey, CodsworthReply2MsgId)));
            cwScript.Properties.Add(CodsworthProp("TalkUseMessageBox", new FormKey(modKey, MissionTalkUseMessageBoxGlobId)));
            cwScript.Properties.Add(BoolProp("MuteDuplicateObjectiveToasts", startCfg.MuteDuplicateObjectiveToasts));
            cwScript.Properties.Add(StrProp("LandingHandoff", startCfg.LandingHandoff));
            codsworthQuest.VirtualMachineAdapter = Adapter(cwScript);
        }

        var lines = codsworthVoice is null ? [] : VoiceLines(codsworthVoice);
        if (lines.Count > 0)
        {
            if (cods is null || keeper is null) throw new Refusal("--codsworth-voice needs Codsworth (drop --no-codsworth)");
            keeper.Data!.Flags |= SF.Quest.Flag.HasDialogueData;
            var codsVoiceKey = new FormKey(modKey, CodsworthVoiceId);
            var dial = new SF.DialogTopic(new FormKey(modKey, CodsworthDialId), SF.StarfieldRelease.Starfield)
            {
                EditorID = CodsworthDialEdid, FormVersion = 581, Version2 = 1,
                Quest = new FormLink<SF.IQuestGetter>(keeper.FormKey), Priority = 50,
                Category = SF.DialogTopic.CategoryEnum.Misc, Subtype = SF.DialogTopic.SubtypeEnum.Hello,
                SubtypeName = SF.DialogTopic.SubtypeNameEnum.Hello,
            };
            uint id = FirstCodsworthInfoId;
            foreach (var l in lines)
            {
                var info = new SF.DialogResponses(new FormKey(modKey, id++), SF.StarfieldRelease.Starfield)
                {
                    EditorID = $"FO4SF_Codsworth_{l.Fo4Info}_{l.Response}", FormVersion = 581, Version2 = 2,
                    Flags = new SF.DialogResponseFlags { Flags = (short)SF.DialogResponses.Flag.Random },
                };
                info.Responses.Add(MakeNpcDialogResponse(l.Text, l.Wem, l.Duration, codsVoiceKey));
                info.Conditions.AddRange(VoiceConditions(cods.FormKey, l.Sex));
                dial.Responses.Add(info);
                (dial.TopicInfoList ??= new()).Add(new FormLink<SF.IDialogResponsesGetter>(info.FormKey));
            }
            keeper.DialogTopics.Add(dial);
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
                Flags = SF.Quest.Flag.AllowRepeatedStages | SF.Quest.Flag.DisplaysInHud |
                        SF.Quest.Flag.RunOnce,
                Priority = 50,
            },
        };
        sanctuaryQuest.QuestType.SetTo(qtyp.FormKey);
        foreach (var stIdx in SanctuaryQuestStages)
        {
            var st = new SF.QuestStage { Index = stIdx };
            st.LogEntries.Add(new SF.QuestLogEntry
            {
                Flags = stIdx == 100 ? SF.QuestLogEntry.Flag.CompleteQuest : (SF.QuestLogEntry.Flag)0,
            });
            sanctuaryQuest.Stages.Add(st);
        }
        (sanctuaryQuest.Aliases ??= new ExtendedList<SF.AQuestAlias>()).Add(new SF.QuestReferenceAlias
        {
            ID = SanctuaryBenchAlias, Name = "SanctuaryWorkbench",
            Flags = SF.AQuestAlias.Flag.Optional | SF.AQuestAlias.Flag.AllowReserved | SF.AQuestAlias.Flag.AllowDisabled,
        });
        var sqObj = new SF.QuestObjective { Index = 10, Flags = (SF.QuestObjective.Flag)0, DisplayText = sqObj10 };
        sqObj.Targets.Add(new SF.QuestObjectiveTarget { AliasID = SanctuaryBenchAlias });
        sanctuaryQuest.Objectives.Add(sqObj);
        var sqScript = new SF.ScriptEntry { Name = SanctuaryScriptName, Flags = SF.ScriptEntry.Flag.Local };
        sqScript.Properties.Add(SanctuaryObjProp("XMarkerBase", xMarker.FormKey));
        sanctuaryQuest.VirtualMachineAdapter = Adapter(sqScript);
        mod.Quests.Add(sanctuaryQuest);

        NextStoryMissionsA4.PopulateA4Missions(
            mod, cell, sanctuaryQuest, prestonRef.FormKey, minutemen.FormKey,
            qtyp.FormKey, xMarker.FormKey, m.Sf, prestonTpl, humanRace.FormKey, prestonVoice.FormKey,
            raiderNpc, raiderCombatPack.FormKey, raiderSandboxPack.FormKey, prestonWeapon.FormKey, prestonAmmo.FormKey);

        NextStoryMissionsA7.PopulateA7Missions(
            mod, cell, qtyp.FormKey, xMarker.FormKey, m.Sf, prestonTpl, humanRace.FormKey, prestonVoice.FormKey);

        NextStoryMissionsA7cd.PopulateA7cdMissions(
            mod, cell, qtyp.FormKey, xMarker.FormKey, m.Sf, prestonTpl, humanRace.FormKey, prestonVoice.FormKey,
            raiderNpc, raiderCombatPack.FormKey, raiderSandboxPack.FormKey, prestonWeapon.FormKey, prestonAmmo.FormKey);

        FalloutActorLooks.ApplyActorLooks(
            mod, m.Sf, m.Raider, FalloutActorLooks.ActorLooksModels.FromDirectoryOrArgs(actorLooksDir));

        uint maxId = Math.Max(MissionHoldingCellId + 1, Math.Max(FalloutActorLooks.MaxAllocatedId, Math.Max(NextStoryMissionsA7cd.MaxAllocatedId, Math.Max(NextStoryMissionsA7.MaxAllocatedId, Math.Max(NextStoryMissionsA4.MaxAllocatedId, Math.Max(SanctuaryQuestId + 1, Math.Max(MinutemenFactionId + 1, MissionTalkUseMessageBoxGlobId + 1)))))));
        if (alias) maxId = Math.Max(maxId, Math.Max(FirstPrestonReplyInfoId + 3, PrestonReply2MsgId + 1));
        if (codsworthQuest is not null) maxId = Math.Max(maxId, Math.Max(FirstCodsworthReplyInfoId + 4, CodsworthReply2MsgId + 1));
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
                          $"holding CELL {cell.EditorID} {cell.FormKey} (0 WRLD overrides; core {world.FormKey} verified)");
        return 0;
    }

    static string Show(P3Float p) => $"({F(p.X)}, {F(p.Y)}, {F(p.Z)})";

    // ---------------------------------------------------------------- check

    public record VoiceLine(string Fo4Info, int Response, string Text, uint Wem, string? Sex, float Duration = 0f);

    public static List<VoiceLine> VoiceLines(string path)
    {
        using var doc = JsonDocument.Parse(File.ReadAllText(path));
        var lines = doc.RootElement.EnumerateArray().Select(e => new VoiceLine(
            e.GetProperty("info").GetString()!, e.GetProperty("response").GetInt32(), e.GetProperty("text").GetString()!,
            uint.Parse(e.GetProperty("wem").GetString()!, NumberStyles.HexNumber, CultureInfo.InvariantCulture),
            e.TryGetProperty("sex", out var sx) && sx.ValueKind == JsonValueKind.String ? sx.GetString() : null,
            e.TryGetProperty("duration", out var dur) && dur.ValueKind == JsonValueKind.Number ? (float)dur.GetDouble() : 0f)).ToList();
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
            SF.IGetGlobalValueConditionDataGetter g => g.FirstParameter.Link.FormKey.ToString(),
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
                            string? codsworthModel = null, string? codsworthVoice = null, string? codsworthMqVoice = null,
                            string? prestonVoicePath = null, string? actorLooksDir = null, bool codsworthRaceFraming = false)
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
        Need(
            masters.SequenceEqual(new[] { "Starfield.esm" }) ||
            masters.SequenceEqual(new[] { "Starfield.esm", m.Raider.ModKey.FileName.String }),
            "masters are not [Starfield.esm] (Task 1i removes static core WRLD master dependency)");

        var talkGlob = plug.Globals.FirstOrDefault(g => g.FormKey == new FormKey(key, MissionTalkUseMessageBoxGlobId));
        Need(talkGlob is { EditorID: MissionTalkUseMessageBoxGlobEdid } && MathF.Abs(talkGlob.Data ?? -1f) < 1e-5f,
             $"GLOB 0x{MissionTalkUseMessageBoxGlobId:X} is not {MissionTalkUseMessageBoxGlobEdid} == 0.0");

        void CheckSceneResponsesAndTrot(SF.IDialogResponsesGetter info, IReadOnlyList<(uint Wem, float Duration)>? wantClips, FormKey wantVoiceKey, string label)
        {
            Need(info.Responses.Count > 0 && info.Responses.All(r => !string.IsNullOrWhiteSpace(r.ResponseText?.String)),
                 $"{label} lacks non-empty response text");
            if (wantClips is null)
            {
                Need(info.Responses.All(r => r.WEMFile == 0u && r.TROTs.Count == 0), $"{label} carries WEMFile/TROT without voice spec");
            }
            else
            {
                var gotWems = info.Responses.Select(r => r.WEMFile).ToArray();
                var wantWems = wantClips.Select(c => c.Wem).ToArray();
                Need(gotWems.SequenceEqual(wantWems), $"{label} WEMFiles [{string.Join(",", gotWems.Select(w => w.ToString("X8")))}] != [{string.Join(",", wantWems.Select(w => w.ToString("X8")))}]");
                Need(info.Responses.All(r => r.TROTs.Count == 1 && r.TROTs[0].VoiceType.FormKey == wantVoiceKey && r.TROTs[0].EmotionOut > 0f && r.EmotionOut > 0f),
                     $"{label} voiced response lacks valid TROT for {wantVoiceKey}");
            }
        }

        // 2g: Check Preston's dedicated HumanRace NPC_
        var npc = plug.Npcs.FirstOrDefault(n => n.FormKey == new FormKey(key, PrestonNpcId));
        var minutemen = plug.Factions.FirstOrDefault(f => f.FormKey == new FormKey(key, MinutemenFactionId));
        Need(minutemen is { EditorID: MinutemenFactionEdid } && minutemen.Relations.Count == 1 &&
             minutemen.Relations[0].Target.FormKey == new FormKey(SfEsm, PlayerFactionId) && minutemen.Relations[0].Reaction == SF.CombatReaction.Ally,
             $"FACT 0x{MinutemenFactionId:X} is not {MinutemenFactionEdid} with the one relation Ally to PlayerFaction");
        Need(npc is { EditorID: PrestonEdid } && npc.Flags.HasFlag(SF.Npc.Flag.Essential) && npc.Flags.HasFlag(SF.Npc.Flag.Unique) &&
             !npc.Flags.HasFlag(SF.Npc.Flag.Respawn) && npc.Factions.Count == 1 && npc.Factions[0].Faction.FormKey == minutemen?.FormKey &&
             npc.Aggression == SF.Npc.AggressionType.Unaggressive && npc.Assistance == SF.Npc.AssistanceType.HelpsNobody,
             $"NPC_ 0x801 is not an essential unique Unaggressive/HelpsNobody FO4_PrestonGarvey in {MinutemenFactionEdid} only");
        Need(npc is not null && npc.Race.FormKey == new FormKey(SfEsm, SfHumanRaceId), "Preston's race is not Starfield.esm HumanRace (0x00347D)");
        Need(npc is not null && m.Sf.VoiceTypes.TryGetValue(npc.Voice.FormKey, out var pv) && pv.EditorID == SfPrestonVoiceEdid &&
             pv.Flags.HasFlag(SF.VoiceType.Flag.AllowDefaultDialog),
             $"Preston's VoiceType is not {SfPrestonVoiceEdid} with AllowDefaultDialog");
        FalloutActorLooks.CheckActorLooks(
            plug, m.Sf, m.Raider.ModKey, problems, FalloutActorLooks.ActorLooksModels.FromDirectoryOrArgs(actorLooksDir));
        var prestonItems = npc?.Items?.Select(i => i.Item.Item.FormKey).ToHashSet() ?? [];
        Need(prestonItems.Contains(new FormKey(SfEsm, SfPrestonWeaponId)) && prestonItems.Contains(new FormKey(SfEsm, SfPrestonAmmoId)),
             $"Preston lacks {SfPrestonWeaponEdid} ({SfPrestonWeaponId:X6}) or {SfPrestonAmmoEdid} ({SfPrestonAmmoId:X6})");
        Need(npc is not null && npc.CalcMinLevel >= 10, "Preston CalcMinLevel < 10");
        Need(npc is not null && npc.ActivateTextOverride?.String == "Talk", "Preston lacks ActivateTextOverride == \"Talk\"");
        Need(npc is not null && npc.DefaultTemplate.IsNull && npc.TemplateActors is null, "Preston retains DefaultTemplate or TemplateActors");

        var world = FindWorld(m.Core, World);
        Need(plug.Worldspaces.Count == 0,
             $"Task 1i: FO4SFMission.esm must have ZERO WRLD overrides (0 FO4Core_Commonwealth / 0 Mars biome 0x002A3777), found {plug.Worldspaces.Count}");
        var cell = plug.Cells.Records
            .SelectMany(b => b.SubBlocks)
            .SelectMany(sb => sb.Cells)
            .FirstOrDefault(c => c.FormKey == new FormKey(key, MissionHoldingCellId));
        Need(cell is { EditorID: MissionHoldingCellEdid } && (cell.Flags ?? 0).HasFlag(SF.Cell.Flag.IsInteriorCell) &&
             (cell.Name?.String is null || !cell.Name.String.Contains("FO4SF", StringComparison.OrdinalIgnoreCase)),
             $"holding CELL 0x{MissionHoldingCellId:X} ({MissionHoldingCellEdid}) missing, lacks IsInteriorCell, or exposes FO4SF in FULL ({cell?.Name?.String})");
        var refs = cell?.Persistent.OfType<SF.IPlacedNpcGetter>().ToList() ?? new();
        Need(cell is null || cell.Persistent.Count == refs.Count, "the holding cell holds something other than our ACHRs");
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
        var codsTalkActi = plug.Activators.FirstOrDefault(a => a.FormKey == new FormKey(key, CodsworthTalkActiId));

        void CheckTalkMessages(IReadOnlyList<(uint Id, string Edid)> specs, string ownerLabel)
        {
            foreach (var (mid, medid) in specs)
            {
                var msg = plug.Messages.FirstOrDefault(x => x.FormKey == new FormKey(key, mid));
                Need(msg is not null && msg.EditorID == medid && msg.Flags.HasFlag(SF.Message.Flag.MessageBox) &&
                     !string.IsNullOrWhiteSpace(msg.Name?.String) && !string.IsNullOrWhiteSpace(msg.Description.String) &&
                     msg.MenuButtons.Count == MaxTalkButtons && msg.MenuButtons.Count <= 7 &&
                     msg.MenuButtons.All(b => !string.IsNullOrWhiteSpace(b.Text?.String)),
                     $"{ownerLabel} lacks valid 4-button MessageBox {medid} (0x{mid:X})");
            }
        }

        if (!codsworth)
        {
            Need(cods is null && codsRef is null && codsRace is null && codsVoice is null && codsTalkActi is null &&
                 !plug.Messages.Any(x => x.FormKey.ID is >= CodsworthTalkMsgId and <= CodsworthReply2MsgId),
                 "a --no-codsworth build carries Codsworth records");
        }
        else
        {
            Console.WriteLine($"  NPC_ {cods?.EditorID} \"{cods?.Name?.String}\" race {cods?.Race.FormKey} voice {cods?.Voice.FormKey} factions {cods?.Factions.Count} scripts {(cods?.VirtualMachineAdapter is null ? 0 : 1)}");
            Need(cods is { EditorID: CodsworthEdid } && cods.Flags.HasFlag(SF.Npc.Flag.Essential) && cods.Flags.HasFlag(SF.Npc.Flag.Unique) &&
                 !cods.Flags.HasFlag(SF.Npc.Flag.Respawn) && cods.Factions.Count == 0 &&
                 cods.VirtualMachineAdapter is null && !string.IsNullOrWhiteSpace(cods.Name?.String),
                 "NPC_ 0x810 is not an essential, unique, non-respawning, named FO4_Codsworth without factions and scripts");
            Need(cods is not null && cods.ActivateTextOverride?.String == "Talk", "Codsworth lacks ActivateTextOverride == \"Talk\"");
            Need(cods is not null && cods.DefaultTemplate.IsNull && cods.TemplateActors is null && (cods.Keywords?.Count ?? 0) == 0,
                 "Codsworth retains vanilla MiniBot DefaultTemplate, TemplateActors, or Outpost keywords");
            Need(cods is not null && cods.ObjectBounds.Second.Z >= 1.75f, "Codsworth ObjectBounds.Second.Z < 1.75 m");
            Need(codsTalkActi is { EditorID: CodsworthTalkActiEdid, ActivationAngle: 360, InvertFacing: false, Flags: 0, MajorRecordFlagsRaw: 0 } &&
                 codsTalkActi.ActivateTextOverride?.String == "Talk" &&
                 codsTalkActi.VirtualMachineAdapter is null && (codsTalkActi.Keywords?.Count ?? 0) == 0 && codsTalkActi.Components.Count == 0 &&
                 string.IsNullOrEmpty(codsTalkActi.Model?.File?.GivenPath),
                 $"ACTI 0x{CodsworthTalkActiId:X} is not clean {CodsworthTalkActiEdid} with Talk prompt and invisible Model=null");
            CheckTalkMessages(new[]
            {
                (CodsworthTalkMsgId, CodsworthTalkMsgEdid),
                (CodsworthReply0MsgId, CodsworthReply0MsgEdid),
                (CodsworthReply1MsgId, CodsworthReply1MsgEdid),
                (CodsworthReply2MsgId, CodsworthReply2MsgEdid),
            }, CodsworthQuestEdid);
            Need(codsRace is { EditorID: CodsworthRaceEdid } && codsRace.Flags.HasFlag(SF.Race.Flag.AllowPcDialog) &&
                 cods?.Race.FormKey == codsRace.FormKey,
                 $"Codsworth lacks local RACE {CodsworthRaceEdid} (0x{CodsworthRaceId:X}) with AllowPcDialog");
            if (codsworthRaceFraming)
            {
                Need(codsRace is { Size: SF.Size.Medium } && codsRace.DialogueQuest.IsNull &&
                     codsRace.Flags.HasFlag(SF.Race.Flag.HeadAxisBit0) &&
                     !codsRace.Flags.HasFlag(SF.Race.Flag.TiltFrontBack) &&
                     (((ulong)codsRace.Flags & 0x0080000000000000UL) != 0),
                     $"R11 D1: {CodsworthRaceEdid} lacks standing dialogue framing metadata (--codsworth-race-framing 1)");
            }
            else if (codsRace is not null && m.Cache.TryResolve<SF.IRaceGetter>(codsRace.ArmorRace.FormKey, out var baseBotRaceCheck))
            {
                Need(codsRace.Size == baseBotRaceCheck.Size &&
                     codsRace.DialogueQuest.FormKey == baseBotRaceCheck.DialogueQuest.FormKey &&
                     codsRace.Flags == (baseBotRaceCheck.Flags | SF.Race.Flag.AllowPcDialog) &&
                     codsRace.DAT2Unknown3.Span.SequenceEqual(baseBotRaceCheck.DAT2Unknown3.Span),
                     $"R11 Review Item #6: default build (--codsworth-race-framing 0) must keep 2g {CodsworthRaceEdid} (AllowPcDialog + ArmorRace only)");
            }
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

        Need(refs.All(r => r.FormKey.ID < CodsworthNpcId || r.FormKey.ID == CodsworthRefId || NextStoryMissionsA4.IsA4ActorRefId(r.FormKey.ID) || NextStoryMissionsA7.IsA7ActorRefId(r.FormKey.ID) || NextStoryMissionsA7cd.IsA7cdActorRefId(r.FormKey.ID)),
             "an ACHR outside Preston, the raiders, Codsworth, A4, A7, and A7cd actors");
        Need(raiders.Count > 0 && raiders.All(r => r.Base.FormKey == new FormKey(key, FalloutActorLooks.ConcordRaiderNpcId)), "no raider ACHR on FO4_ConcordRaider (0x986)");
        Need(raiders.All(r => r.Position.X < -1500f && r.Position.Y < -1000f),
             "C3: a raider ACHR is still at unmerged coordinates instead of merged Concord coordinates");
        var coreNavs = NavmeshSnap.LoadWorldNavmeshes(corePath);
        if (coreNavs.Count > 0)
        {
            foreach (var r in new[] { preston, codsRef }.Concat(raiders).Where(x => x is not null))
            {
                bool isRaider = r!.FormKey.ID >= FirstRaiderRefId && r.FormKey.ID < CodsworthNpcId;
                float lx = isRaider ? r.Position.X - MergeOffsetX : r.Position.X;
                float ly = isRaider ? r.Position.Y - MergeOffsetY : r.Position.Y;
                if (NavmeshSnap.TryFindFloorZ(coreNavs, lx, ly, r.Position.Z, out var floorZ))
                {
                    float dz = MathF.Abs(r.Position.Z - floorZ);
                    Need(dz <= NavmeshSnap.HoldFloorMaxToleranceM,
                         $"G13(b): ACHR {r.EditorID} z={r.Position.Z:F3} deviates from core navmesh floor {floorZ:F3} by {dz:F3} m (> {NavmeshSnap.HoldFloorMaxToleranceM:F1} m)");
                }
            }
        }

        static bool HasPhase1Intv(SF.IDialogResponsesGetter info) =>
            info.INTV is { Length: >= 4 } raw && BitConverter.ToInt32(raw.Span) == 1;

        static bool NonStartGameReady(SF.IQuestGetter q) =>
            q.Data is not null && !q.Data.Flags.HasFlag(SF.Quest.Flag.StartGameEnabled) &&
            !q.Data.Flags.HasFlag(SF.Quest.Flag.StartsEnabled) && (((uint)q.Data.Flags & 0x10000u) == 0);

        // Check FO4SF_Min00 (0x800)
        var q = plug.Quests.FirstOrDefault(x => x.FormKey == new FormKey(key, QuestId));
        if (q is null) problems.Add("no QUST 0x800");
        else
        {
            Console.WriteLine($"  QUST {q.EditorID} \"{q.Name?.String}\" flags {q.Data?.Flags} stages [{string.Join(",", q.Stages.Select(s => s.Index))}] " +
                              $"objectives [{string.Join("; ", q.Objectives.Select(o => $"{o.Index} \"{o.DisplayText?.String}\" targets {o.Targets.Count}"))}] aliases {q.Aliases?.Count ?? 0} scenes {q.Scenes.Count}");
            Need(q.EditorID == QuestEdid && NonStartGameReady(q) && q.Data!.Flags.HasFlag(SF.Quest.Flag.RunOnce) &&
                 q.Data.Flags.HasFlag(SF.Quest.Flag.DisplaysInHud),
                 "FO4SF_Min00 must NOT carry StartGameEnabled / StartsEnabled / 0x10000 and must carry RunOnce | DisplaysInHud");
            Need(q.QuestType.FormKey == new FormKey(SfEsm, QuestTypeSideId), $"the quest's QuestType is not {QuestTypeSideEdid}");
            Need(q.Stages.Select(s => s.Index).SequenceEqual(Stages), "stages differ from the script's");

            var dials = q.DialogTopics.ToList();
            int expectedSceneDials = alias ? 7 : 0; // 1 greeting + 3 choice + 3 reply
            Need(dials.Count == expectedSceneDials && !dials.Any(d => d.FormKey == new FormKey(key, CodsworthDialId)),
                 $"FO4SF_Min00 DIAL count {dials.Count} != {expectedSceneDials} or still owns persistent Codsworth Hellos");
            Need(q.Stages.All(s => s.LogEntries.Count >= 1 && s.LogEntries[0].Flags is not null), "a FO4SF_Min00 stage lacks a QSDT QuestLogEntry");
            Need(q.Stages.LastOrDefault()?.LogEntries.Any(l => l.Flags?.HasFlag(SF.QuestLogEntry.Flag.CompleteQuest) == true) == true, "stage 200 does not complete the quest");
            Need(q.Objectives.Select(o => o.Index).SequenceEqual(Objectives.Select(o => o.Index)), "objectives differ from the script's");
            Need(q.Objectives.All(o => o.Flags is not null && !string.IsNullOrWhiteSpace(o.DisplayText?.String) && !o.DisplayText!.String!.Contains('<')), "an objective lacks Flags or has no text / FO4 token");

            if (alias)
            {
                var refAliases = (q.Aliases ?? new List<SF.IAQuestAliasGetter>()).OfType<SF.IQuestReferenceAliasGetter>().ToList();
                var al = refAliases.FirstOrDefault(a => a.ID == PrestonAlias);
                Need(al is not null && al.ForcedReference.FormKey == preston?.FormKey && (al.Flags ?? 0).HasFlag(SF.AQuestAlias.Flag.Optional),
                     "alias 0 is not an Optional reference alias forced to Preston's ACHR");
                var wantRaiderPacks = new[]
                {
                    new FormKey(SfEsm, RaiderCombatPackageId),
                    new FormKey(SfEsm, RaiderSandboxPackageId),
                };
                Need(m.Cache.TryResolve<SF.IPackageGetter>(wantRaiderPacks[0], out var rcp) && rcp.EditorID == RaiderCombatPackageEdid &&
                     m.Cache.TryResolve<SF.IPackageGetter>(wantRaiderPacks[1], out var rsp) && rsp.EditorID == RaiderSandboxPackageEdid,
                     $"Starfield.esm lacks {RaiderCombatPackageEdid} ({RaiderCombatPackageId:X6}) or {RaiderSandboxPackageEdid} ({RaiderSandboxPackageId:X6})");
                var wantRaiderAmmoKey = new FormKey(SfEsm, SfRaiderAmmoId);
                Need(m.Cache.TryResolve<SF.IAmmunitionGetter>(wantRaiderAmmoKey, out var rAmmo) && rAmmo.EditorID == SfRaiderAmmoEdid,
                     $"Starfield.esm lacks {SfRaiderAmmoEdid} ({SfRaiderAmmoId:X6})");
                Need(refAliases.Count == 1 + raiders.Count, $"expected {1 + raiders.Count} reference aliases (Preston + {raiders.Count} raiders), got {refAliases.Count}");
                for (int ri = 0; ri < raiders.Count; ri++)
                {
                    var ral = refAliases.FirstOrDefault(a => a.ID == (uint)(1 + ri));
                    Need(ral is not null && ral.ForcedReference.FormKey == raiders[ri].FormKey &&
                         ral.PackageData.Select(p => p.FormKey).SequenceEqual(wantRaiderPacks),
                         $"raider alias {1 + ri} is not forced to raider {ri} with [{RaiderCombatPackageEdid}, {RaiderSandboxPackageEdid}]");
                    bool hasAmmo = ral?.Items is not null && ral.Items.Any(e => e.Item.Item.FormKey == wantRaiderAmmoKey && e.Item.Count >= RaiderAmmoCount);
                    Need(hasAmmo, $"C3: raider alias {1 + ri} lacks {SfRaiderAmmoEdid} x{RaiderAmmoCount}");
                }
                Need(q.Objectives.Where((o, i) => Objectives[i].TargetsPreston).All(o => o.Targets.Count == 1 && o.Targets[0].AliasID == PrestonAlias),
                     "Preston's objectives do not target alias 0");
                Need(q.Scenes.Count == 1 && q.Scenes[0].FormKey == new FormKey(key, PrestonTalkSceneId), "FO4SF_Min00 lacks Preston talk scene 0x900");
                if (q.Scenes.Count == 1)
                {
                    var pscn = q.Scenes[0];
                    uint pscnFlags = (uint)(pscn.Flags ?? 0);
                    Need((pscnFlags & 0x2000u) == 0 && pscnFlags == 0x1814u, $"Preston talk scene flags 0x{pscnFlags:X4} != 0x1814");
                    Need(pscn.DEVT, "Preston talk scene lacks DEVT == true");
                    Need(pscn.SCPI is null, "Preston talk scene must have SCPI == null");
                    Need(pscn.Actors.Count == 1 && pscn.Actors[0].ID == 0, $"Preston talk scene expected 1 SceneActor (ID=0), found {pscn.Actors.Count}");
                    var wantGlobSig = CondSig(GlobalIsZero(new FormKey(key, MissionTalkUseMessageBoxGlobId)));
                    Need(pscn.Conditions.Select(CondSig).Contains(wantGlobSig), "Preston talk scene lacks FO4SF_MissionTalkUseMessageBox == 0 condition");
                    var pda = pscn.Actions?.OfType<SF.IPlayerDialogueSceneActionGetter>().FirstOrDefault();
                    Need(pda is not null && pda.DialogueList.Count == 3, "Preston talk scene does not carry 3 PlayerDialogueSceneAction exchanges");
                    if (pda is not null && pda.DialogueList.Count == 3)
                    {
                        var pVoiceSpec = prestonVoicePath is null ? null : LoadSceneVoice(prestonVoicePath, 3, "Preston");
                        var pGreetInfo = q.DialogTopics.FirstOrDefault(t => t.FormKey == new FormKey(key, PrestonGreetTopicId))?.Responses.FirstOrDefault();
                        if (pGreetInfo is null) problems.Add("Preston talk scene lacks greeting INFO");
                        else CheckSceneResponsesAndTrot(pGreetInfo, pVoiceSpec?.GreetingClips, npc?.Voice.FormKey ?? FormKey.Null, "Preston greeting INFO");

                        for (int ci = 0; ci < 3; ci++)
                        {
                            var pcInfo = q.DialogTopics.First(t => t.FormKey == pda.DialogueList[ci].PlayerChoice.FormKey).Responses.First();
                            var rpInfo = q.DialogTopics.First(t => t.FormKey == pda.DialogueList[ci].NpcResponse.FormKey).Responses.First();
                            var pTxt = pcInfo.Prompt?.String ?? "";
                            var rTxt = pcInfo.Responses.FirstOrDefault()?.ResponseText?.String ?? "";
                            Need(pTxt.Length > 0 && pTxt == rTxt, $"Preston choice {ci} does not show full player line in both Prompt and ResponseText");
                            Need(pcInfo.Flags is { Flags: 0 } && pcInfo.SubtitlePriority == SF.DialogResponses.SubtitlePriorityLevel.Low &&
                                 rpInfo.SubtitlePriority == SF.DialogResponses.SubtitlePriorityLevel.Low,
                                 $"R11 D5: Preston choice {ci} lacks explicit ENAM (Flags=0, DoNotGrayOut clear) or INAM SubtitlePriority=Low");
                            CheckSceneResponsesAndTrot(rpInfo, pVoiceSpec?.ReplyClips[ci], npc?.Voice.FormKey ?? FormKey.Null, $"Preston reply {ci}");
                            if (ci == 2)
                                Need(rpInfo.SetParentQuestStage?.OnEnd == 35 && rpInfo.Flags?.Flags == 1,
                                     "Preston talk scene exchange 3 does not end conversation at stage 35");
                            else
                                Need(rpInfo.StartScene.FormKey == pscn.FormKey && rpInfo.StartScenePhase == "TOPLEVELNEST" && HasPhase1Intv(rpInfo),
                                     $"Preston choice {ci} does not loop back to TOPLEVELNEST (Phase 1 INTV=1)");
                        }
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
                var concordPrimaryCheck = plug.Weapons.FirstOrDefault(w => w.FormKey == new FormKey(key, ConcordRaiderPrimaryWeapId));
                Need(concordPrimaryCheck is { EditorID: ConcordRaiderPrimaryWeapEdid } &&
                     concordPrimaryCheck.Name?.String == "Coachman" &&
                     concordPrimaryCheck.MajorFlags.HasFlag(SF.Weapon.MajorFlag.NonPlayable) &&
                     concordPrimaryCheck.NonPlayable &&
                     (concordPrimaryCheck.ObjectTemplates?.Count ?? 0) > 0 &&
                     (concordPrimaryCheck.AttachParentSlots?.Count ?? 0) > 0 &&
                     MathF.Abs(concordPrimaryCheck.AttackDamage - ConcordRaiderPrimaryDamage) < 1e-4f &&
                     concordPrimaryCheck.ProjectilesCount == ConcordRaiderPrimaryProjectiles &&
                     concordPrimaryCheck.AmmoType.FormKey == new FormKey(SfEsm, SfRaiderAmmoId) &&
                     concordPrimaryCheck.AmmoList.IsNull,
                     $"R13 E3: WEAP 0x{ConcordRaiderPrimaryWeapId:X} is not non-playable {ConcordRaiderPrimaryWeapEdid} (Name=\"Coachman\", NonPlayable=true, non-empty ObjectTemplates & AttachParentSlots, AttackDamage={ConcordRaiderPrimaryDamage}, ProjectilesCount={ConcordRaiderPrimaryProjectiles}, AmmoType=0x{SfRaiderAmmoId:X}, AmmoList=null)");
                Need(props.TryGetValue("RaiderWeapon", out var rwp) && rwp is SF.IScriptObjectPropertyGetter rwo && rwo.Object.FormKey == new FormKey(key, ConcordRaiderPrimaryWeapId) &&
                     props.TryGetValue("RaiderAmmo", out var rap) && rap is SF.IScriptObjectPropertyGetter rao && rao.Object.FormKey == new FormKey(SfEsm, SfRaiderAmmoId),
                     $"R13 E3: FO4SF_Min00 lacks RaiderWeapon (0x{ConcordRaiderPrimaryWeapId:X}) or RaiderAmmo (AmmoShotshell) bindings");
                var concordSidearmCheck = plug.Weapons.FirstOrDefault(w => w.FormKey == new FormKey(key, ConcordRaiderSidearmWeapId));
                Need(concordSidearmCheck is { EditorID: ConcordRaiderSidearmWeapEdid } &&
                     concordSidearmCheck.Name?.String == "Eon" &&
                     concordSidearmCheck.MajorFlags.HasFlag(SF.Weapon.MajorFlag.NonPlayable) &&
                     concordSidearmCheck.NonPlayable &&
                     (concordSidearmCheck.ObjectTemplates?.Count ?? 0) > 0 &&
                     (concordSidearmCheck.AttachParentSlots?.Count ?? 0) > 0 &&
                     MathF.Abs(concordSidearmCheck.AttackDamage - ConcordRaiderSidearmDamage) < 1e-4f &&
                     concordSidearmCheck.ProjectilesCount == ConcordRaiderSidearmProjectiles &&
                     concordSidearmCheck.AmmoType.FormKey == new FormKey(SfEsm, SfRaiderSidearmAmmoId) &&
                     concordSidearmCheck.AmmoList.IsNull,
                     $"R11/R13 E3: WEAP 0x{ConcordRaiderSidearmWeapId:X} is not non-playable {ConcordRaiderSidearmWeapEdid} (Name=\"Eon\", NonPlayable=true, non-empty ObjectTemplates & AttachParentSlots, AttackDamage={ConcordRaiderSidearmDamage}, ProjectilesCount={ConcordRaiderSidearmProjectiles}, AmmoType=0x{SfRaiderSidearmAmmoId:X}, AmmoList=null)");
                Need(props.TryGetValue("RaiderSidearm", out var rswp) && rswp is SF.IScriptObjectPropertyGetter rswo && rswo.Object.FormKey == new FormKey(key, ConcordRaiderSidearmWeapId) &&
                     props.TryGetValue("RaiderSidearmAmmo", out var rsap) && rsap is SF.IScriptObjectPropertyGetter rsao && rsao.Object.FormKey == new FormKey(SfEsm, SfRaiderSidearmAmmoId),
                     $"R11 D3/E3: FO4SF_Min00 lacks RaiderSidearm (0x{ConcordRaiderSidearmWeapId:X}) or RaiderSidearmAmmo (Ammo777mm) bindings");
                float wantPrimaryRecDmg = concordPrimaryCheck is null ? ConcordRaiderPrimaryDamage : concordPrimaryCheck.AttackDamage * Math.Max(1, (int)concordPrimaryCheck.ProjectilesCount);
                float wantSidearmRecDmg = concordSidearmCheck is null ? ConcordRaiderSidearmDamage : concordSidearmCheck.AttackDamage * Math.Max(1, (int)concordSidearmCheck.ProjectilesCount);
                Need(props.TryGetValue("RaiderPrimaryRecordDamage", out var rprd) && rprd is SF.IScriptFloatPropertyGetter rprdf && MathF.Abs(rprdf.Data - wantPrimaryRecDmg) < 1e-4f,
                     $"R13 E3: FO4SF_Min00 RaiderPrimaryRecordDamage != {wantPrimaryRecDmg}");
                Need(props.TryGetValue("RaiderSidearmRecordDamage", out var rsrd) && rsrd is SF.IScriptFloatPropertyGetter rsrdf && MathF.Abs(rsrdf.Data - wantSidearmRecDmg) < 1e-4f,
                     $"R13 E3: FO4SF_Min00 RaiderSidearmRecordDamage != {wantSidearmRecDmg}");
                if (alias)
                {
                    CheckTalkMessages(new[]
                    {
                        (PrestonTalkMsgId, PrestonTalkMsgEdid),
                        (PrestonReply0MsgId, PrestonReply0MsgEdid),
                        (PrestonReply1MsgId, PrestonReply1MsgEdid),
                        (PrestonReply2MsgId, PrestonReply2MsgEdid),
                    }, QuestEdid);
                    Need(props.TryGetValue("TalkUseMessageBox", out var ptg) && ptg is SF.IScriptObjectPropertyGetter ptgo && ptgo.Object.FormKey == new FormKey(key, MissionTalkUseMessageBoxGlobId),
                         "FO4SF_Min00 lacks TalkUseMessageBox -> 0x979 binding");
                    Need(props.TryGetValue("PrestonTalkMsg", out var ptm) && ptm is SF.IScriptObjectPropertyGetter ptmo && ptmo.Object.FormKey == new FormKey(key, PrestonTalkMsgId) &&
                         props.TryGetValue("PrestonReply0Msg", out var pr0) && pr0 is SF.IScriptObjectPropertyGetter pr0o && pr0o.Object.FormKey == new FormKey(key, PrestonReply0MsgId) &&
                         props.TryGetValue("PrestonReply1Msg", out var pr1) && pr1 is SF.IScriptObjectPropertyGetter pr1o && pr1o.Object.FormKey == new FormKey(key, PrestonReply1MsgId) &&
                         props.TryGetValue("PrestonReply2Msg", out var pr2) && pr2 is SF.IScriptObjectPropertyGetter pr2o && pr2o.Object.FormKey == new FormKey(key, PrestonReply2MsgId),
                         "FO4SF_Min00 lacks PrestonTalkMsg / PrestonReply0..2Msg bindings");
                }
                else
                {
                    Need(!plug.Messages.Any(x => x.FormKey.ID is >= PrestonTalkMsgId and <= PrestonReply2MsgId), "--no-alias carries Preston talk messages");
                    Need(!props.ContainsKey("PrestonTalkMsg") && !props.ContainsKey("TalkUseMessageBox"), "--no-alias binds PrestonTalkMsg or TalkUseMessageBox");
                }
                Need(!props.ContainsKey("PrestonTalkScene") && !props.ContainsKey("PrestonPostTalkScene"),
                     "Task 0c: FO4SF_Min00 VMAD must not bind dead Scene properties PrestonTalkScene / PrestonPostTalkScene");
                Need(!props.ContainsKey("Codsworth") && !props.ContainsKey("KeeperOnly"), "FO4SF_Min00 sets Codsworth or KeeperOnly");
                var wantCfg = LoadMissionStartConfig();
                Need(props.TryGetValue("MuteDuplicateObjectiveToasts", out var minMute) &&
                     minMute is SF.IScriptBoolPropertyGetter minMuteB &&
                     minMuteB.Data == wantCfg.MuteDuplicateObjectiveToasts,
                     $"FO4SF_Min00 lacks MuteDuplicateObjectiveToasts == {wantCfg.MuteDuplicateObjectiveToasts}");
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
                Console.WriteLine($"  QUST {kq.EditorID} flags {kq.Data?.Flags} stages {kq.Stages.Count} dials {kq.DialogTopics.Count} scenes {kq.Scenes.Count}");
                Need(kq.EditorID == KeeperEdid && NonStartGameReady(kq) && !kq.Data!.Flags.HasFlag(SF.Quest.Flag.RunOnce) &&
                     !kq.Data.Flags.HasFlag(SF.Quest.Flag.DisplaysInHud) &&
                     kq.Data.Flags.HasFlag(SF.Quest.Flag.AllowRepeatedStages) &&
                     kq.Data.Flags.HasFlag(SF.Quest.Flag.HasDialogueData),
                     $"{KeeperEdid} flags invalid (must carry AllowRepeatedStages | HasDialogueData without StartGameEnabled/StartsEnabled/0x10000/RunOnce/DisplaysInHud)");
                var kAliases = (kq.Aliases ?? new List<SF.IAQuestAliasGetter>()).OfType<SF.IQuestReferenceAliasGetter>().ToList();
                var kAl0 = kAliases.FirstOrDefault(a => a.ID == KeeperPrestonAlias);
                var kAl1 = kAliases.FirstOrDefault(a => a.ID == KeeperCodsworthAlias);
                Need(kAl0 is not null && kAl0.ForcedReference.FormKey == preston?.FormKey && (kAl0.Flags ?? 0).HasFlag(SF.AQuestAlias.Flag.Optional) &&
                     kAl1 is not null && kAl1.ForcedReference.FormKey == codsRef?.FormKey && (kAl1.Flags ?? 0).HasFlag(SF.AQuestAlias.Flag.Optional),
                     $"{KeeperEdid} lacks forced Optional aliases 0 (Preston) and 1 (Codsworth)");

                int expectedKeeperDials = (codsworthVoice is null ? 0 : 1) + (alias ? 3 : 0) + 3;
                Need(kq.DialogTopics.Count == expectedKeeperDials,
                     $"{KeeperEdid} DIAL count {kq.DialogTopics.Count} != {expectedKeeperDials}");
                var helloDial = kq.DialogTopics.FirstOrDefault(d => d.FormKey == new FormKey(key, CodsworthDialId));
                if (codsworthVoice is null)
                {
                    Need(helloDial is null, $"unexpected Hello DIAL 0x{CodsworthDialId:X} on {KeeperEdid} without --codsworth-voice");
                }
                else
                {
                    var want = VoiceLines(codsworthVoice);
                    var wantVoiceKey = new FormKey(key, CodsworthVoiceId);
                    Console.WriteLine($"  DIAL {helloDial?.EditorID} {helloDial?.Category}/{helloDial?.Subtype}/{helloDial?.SubtypeName} infos {helloDial?.Responses.Count}");
                    Need(kq.Data!.Flags.HasFlag(SF.Quest.Flag.HasDialogueData) &&
                         helloDial is { EditorID: CodsworthDialEdid, FormVersion: 581, Subtype: SF.DialogTopic.SubtypeEnum.Hello, SubtypeName: SF.DialogTopic.SubtypeNameEnum.Hello } &&
                         helloDial.Quest.FormKey == kq.FormKey,
                         $"DIAL 0x{CodsworthDialId:X} is not his FormVersion-581 Hello topic on {KeeperEdid}");
                    var infos = helloDial?.Responses.ToList() ?? [];
                    Need(infos.Count == want.Count && (helloDial!.TopicInfoList ?? []).Select(t => t.FormKey).SequenceEqual(infos.Select(i => i.FormKey)),
                         "his INFOs differ from voice.json or the topic's list");
                    for (int i = 0; i < Math.Min(infos.Count, want.Count); i++)
                    {
                        var info = infos[i];
                        var r = info.Responses.Count == 1 ? info.Responses[0] : null;
                        bool condsOk = cods is not null && info.Conditions.Select(CondSig).SequenceEqual(VoiceConditions(cods.FormKey, want[i].Sex).Select(CondSig));
                        bool trotOk = r is not null && r.TROTs.Count == 1 && r.TROTs[0].VoiceType.FormKey == wantVoiceKey &&
                                      r.TROTs[0].EmotionOut > 0f && r.EmotionOut > 0f;
                        Need(info.FormKey.ID == FirstCodsworthInfoId + i && info.FormVersion == 581 && r is not null &&
                             r.WEMFile == want[i].Wem && r.ResponseText?.String == want[i].Text && condsOk && trotOk,
                             $"INFO 0x{FirstCodsworthInfoId + i:X} is not voiced TROT FormVersion-581 line {want[i].Fo4Info}_{want[i].Response}");
                    }
                }

                // R11 Part 3 Step 3: Verify non-completing repeat 1-choice post scenes on keeper (0x990 Preston alias 0, 0x9C0 Codsworth alias 1)
                void CheckPostScene(
                    uint postSceneId, string postSceneEdid, uint postGreetTopicId, uint wantAliasId,
                    FormKey gateQuestKey, float gateStage,
                    FormKey speakerVoiceKey, SF.IQuestGetter? primaryQuest, uint primaryGreetTopicId)
                {
                    var pscn = kq.Scenes.FirstOrDefault(x => x.FormKey == new FormKey(key, postSceneId));
                    Need(pscn is { EditorID: var ed } && ed == postSceneEdid, $"{KeeperEdid} lacks post scene 0x{postSceneId:X} {postSceneEdid}");
                    if (pscn is null) return;
                    uint pf = (uint)(pscn.Flags ?? 0);
                    Need((pf & 0x2000u) == 0 && pf == 0x1814u && pscn.DEVT && pscn.SCPI is null,
                         $"{postSceneEdid} invalid flags/DEVT/SCPI");
                    Need(pscn.Actors.Count == 1 && pscn.Actors[0].ID == wantAliasId,
                         $"{postSceneEdid} SceneActor ID != {wantAliasId}");
                    var wantGlobSig = CondSig(GlobalIsZero(new FormKey(key, MissionTalkUseMessageBoxGlobId)));
                    var wantStageSig = CondSig(QuestStageCond(gateQuestKey, SF.CompareOperator.GreaterThanOrEqualTo, gateStage));
                    var condSigs = pscn.Conditions.Select(CondSig).ToHashSet();
                    Need(condSigs.Contains(wantGlobSig) && condSigs.Contains(wantStageSig),
                         $"{postSceneEdid} lacks GlobalIsZero(0x979) or GetStage >= {gateStage} condition");
                    var da = pscn.Actions?.OfType<SF.IDialogueSceneActionGetter>().FirstOrDefault();
                    var pda = pscn.Actions?.OfType<SF.IPlayerDialogueSceneActionGetter>().FirstOrDefault();
                    Need(da is not null && da.AliasID == (int)wantAliasId &&
                         pda is not null && pda.AliasID == (int)wantAliasId && pda.DialogueTargetActor == (int)wantAliasId &&
                         pda.DialogueList.Count == 1,
                         $"{postSceneEdid} actions do not target alias {wantAliasId} with 1 post-mission exit choice");
                    var gInfo = kq.DialogTopics.FirstOrDefault(t => t.FormKey == new FormKey(key, postGreetTopicId))?.Responses.FirstOrDefault();
                    if (gInfo is null) problems.Add($"{postSceneEdid} lacks greeting INFO");
                    else
                    {
                        CheckSceneResponsesAndTrot(gInfo, null, speakerVoiceKey, $"{postSceneEdid} greeting INFO");
                        var primGreet = primaryQuest?.DialogTopics.FirstOrDefault(t => t.FormKey == new FormKey(key, primaryGreetTopicId))
                            ?.Responses.FirstOrDefault()?.Responses.FirstOrDefault()?.ResponseText?.String;
                        var postGreetTxt = gInfo.Responses.FirstOrDefault()?.ResponseText?.String;
                        Need(!string.IsNullOrWhiteSpace(postGreetTxt) && !string.Equals(postGreetTxt, primGreet, StringComparison.Ordinal),
                             $"{postSceneEdid} replays primary first-meeting greeting");
                    }
                    if (pda is not null && pda.DialogueList.Count == 1)
                    {
                        var pcInfo = kq.DialogTopics.First(t => t.FormKey == pda.DialogueList[0].PlayerChoice.FormKey).Responses.First();
                        var rpInfo = kq.DialogTopics.First(t => t.FormKey == pda.DialogueList[0].NpcResponse.FormKey).Responses.First();
                        Need(pcInfo.Flags is { Flags: 0 } && pcInfo.SubtitlePriority == SF.DialogResponses.SubtitlePriorityLevel.Low &&
                             rpInfo.SubtitlePriority == SF.DialogResponses.SubtitlePriorityLevel.Low,
                             $"{postSceneEdid} exit choice lacks ENAM=0 / INAM=Low");
                        Need(rpInfo.SetParentQuestStage is null, $"{postSceneEdid} exit choice must not set parent quest stage");
                        CheckSceneResponsesAndTrot(rpInfo, null, speakerVoiceKey, $"{postSceneEdid} reply 0");
                        Need(rpInfo.Flags?.Flags == 1, $"{postSceneEdid} exit choice lacks Goodbye flag");
                    }
                }
                int wantPostSceneCount = alias ? 2 : 1;
                Need(kq.Scenes.Count == wantPostSceneCount, $"{KeeperEdid} scene count {kq.Scenes.Count} != {wantPostSceneCount}");
                if (alias)
                {
                    CheckPostScene(PrestonPostTalkSceneId, PrestonPostTalkSceneEdid, PrestonPostGreetTopicId, KeeperPrestonAlias,
                                   new FormKey(key, QuestId), 200f, npc?.Voice.FormKey ?? FormKey.Null, q, PrestonGreetTopicId);
                }
                CheckPostScene(CodsworthPostSceneId, CodsworthPostSceneEdid, CodsworthPostGreetTopicId, KeeperCodsworthAlias,
                               new FormKey(key, CodsworthQuestId), 100f, new FormKey(key, CodsworthVoiceId), cwq, CodsworthGreetTopicId);
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
                     cwq.Data.Flags.HasFlag(SF.Quest.Flag.RunOnce) && cwq.Data.Flags.HasFlag(SF.Quest.Flag.HasDialogueData) &&
                     cwq.Data.Flags.HasFlag(SF.Quest.Flag.DisplaysInHud),
                     $"{CodsworthQuestEdid} flags invalid (must match FO4SF_NewGame non-StartGameEnabled RunOnce | DisplaysInHud | AllowRepeatedStages | HasDialogueData without StartsEnabled/0x10000)");
                Need(cwq.QuestType.FormKey == new FormKey(SfEsm, QuestTypeSideId), $"{CodsworthQuestEdid} QuestType is not {QuestTypeSideEdid}");
                Need(cwq.Stages.Select(s => s.Index).SequenceEqual(CodsworthQuestStages), $"{CodsworthQuestEdid} stages != [10,20,30,40,100]");
                Need(cwq.Stages.All(s => s.LogEntries.Count >= 1 && s.LogEntries[0].Flags is not null), $"{CodsworthQuestEdid} has a stage without QSDT QuestLogEntry");
                Need(cwq.Stages.Last().LogEntries.Any(l => l.Flags?.HasFlag(SF.QuestLogEntry.Flag.CompleteQuest) == true), $"{CodsworthQuestEdid} stage 100 does not CompleteQuest");
                Need(cwq.Objectives.Count == 1 && cwq.Objectives[0].Index == 10 && cwq.Objectives[0].Flags is not null &&
                     cwq.Objectives[0].Targets.Count == 1 && cwq.Objectives[0].Targets[0].AliasID == CodsworthAlias,
                     $"{CodsworthQuestEdid} lacks objective 10 with Flags targeting alias 0");
                var cal0 = (cwq.Aliases ?? new List<SF.IAQuestAliasGetter>()).OfType<SF.IQuestReferenceAliasGetter>().FirstOrDefault(a => a.ID == CodsworthAlias);
                Need(cal0 is not null && cal0.ForcedReference.FormKey == codsRef?.FormKey && (cal0.Flags ?? 0).HasFlag(SF.AQuestAlias.Flag.Optional),
                     $"{CodsworthQuestEdid} alias 0 is not an Optional reference alias forced to Codsworth ACHR");
                var cws = cwq.VirtualMachineAdapter?.Scripts.FirstOrDefault(x => x.Name == CodsworthScriptName);
                Need(cws is not null, $"{CodsworthQuestEdid} lacks script {CodsworthScriptName}");
                if (cws is not null)
                {
                    var cprops = cws.Properties.ToDictionary(p => p.Name);
                    Need(!cprops.ContainsKey("CodsworthScene") && !cprops.ContainsKey("CodsworthPostScene"),
                         $"Task 0c: {CodsworthQuestEdid} VMAD must not bind dead Scene properties CodsworthScene / CodsworthPostScene");
                    Need(cprops.TryGetValue("Codsworth", out var cwp) && cwp is SF.IScriptObjectPropertyGetter cwo && cwo.Object.FormKey == codsRef?.FormKey &&
                         cprops.TryGetValue("CodsworthTalkActi", out var cap) && cap is SF.IScriptObjectPropertyGetter cao && cao.Object.FormKey == new FormKey(key, CodsworthTalkActiId) &&
                         cprops.TryGetValue("CodsworthTalkMsg", out var cmp) && cmp is SF.IScriptObjectPropertyGetter cmo && cmo.Object.FormKey == new FormKey(key, CodsworthTalkMsgId) &&
                         cprops.TryGetValue("CodsworthReply0Msg", out var cr0) && cr0 is SF.IScriptObjectPropertyGetter cr0o && cr0o.Object.FormKey == new FormKey(key, CodsworthReply0MsgId) &&
                         cprops.TryGetValue("CodsworthReply1Msg", out var cr1) && cr1 is SF.IScriptObjectPropertyGetter cr1o && cr1o.Object.FormKey == new FormKey(key, CodsworthReply1MsgId) &&
                         cprops.TryGetValue("CodsworthReply2Msg", out var cr2) && cr2 is SF.IScriptObjectPropertyGetter cr2o && cr2o.Object.FormKey == new FormKey(key, CodsworthReply2MsgId) &&
                         cprops.TryGetValue("TalkUseMessageBox", out var ctg) && ctg is SF.IScriptObjectPropertyGetter ctgo && ctgo.Object.FormKey == new FormKey(key, MissionTalkUseMessageBoxGlobId),
                         $"{CodsworthQuestEdid} lacks Codsworth / CodsworthTalkActi / CodsworthTalkMsg..Reply2Msg / TalkUseMessageBox properties");
                    var wantCfgCw = LoadMissionStartConfig();
                    Need(cprops.TryGetValue("MuteDuplicateObjectiveToasts", out var cwMute) &&
                         cwMute is SF.IScriptBoolPropertyGetter cwMuteB &&
                         cwMuteB.Data == wantCfgCw.MuteDuplicateObjectiveToasts,
                         $"{CodsworthQuestEdid} lacks MuteDuplicateObjectiveToasts == {wantCfgCw.MuteDuplicateObjectiveToasts}");
                    Need(cprops.TryGetValue("LandingHandoff", out var cwLh) &&
                         cwLh is SF.IScriptStringPropertyGetter cwLhS &&
                         cwLhS.Data == wantCfgCw.LandingHandoff,
                         $"{CodsworthQuestEdid} lacks LandingHandoff == {wantCfgCw.LandingHandoff}");
                }
                Need(cwq.Scenes.Count == 1 && cwq.Scenes[0].FormKey == new FormKey(key, CodsworthSceneId), $"{CodsworthQuestEdid} lacks scene 0x{CodsworthSceneId:X}");
                if (cwq.Scenes.Count == 1)
                {
                    var cscn = cwq.Scenes[0];
                    uint cscnFlags = (uint)(cscn.Flags ?? 0);
                    Need((cscnFlags & 0x2000u) == 0 && cscnFlags == 0x1814u, $"{CodsworthSceneEdid} flags 0x{cscnFlags:X4} != 0x1814");
                    Need(cscn.DEVT, $"{CodsworthSceneEdid} lacks DEVT == true");
                    Need(cscn.SCPI is null, $"{CodsworthSceneEdid} must have SCPI == null");
                    Need(cscn.Actors.Count == 1 && cscn.Actors[0].ID == 0, $"{CodsworthSceneEdid} expected 1 SceneActor (ID=0), found {cscn.Actors.Count}");
                    var wantGlobSig = CondSig(GlobalIsZero(new FormKey(key, MissionTalkUseMessageBoxGlobId)));
                    Need(cscn.Conditions.Select(CondSig).Contains(wantGlobSig), $"{CodsworthSceneEdid} lacks FO4SF_MissionTalkUseMessageBox == 0 condition");
                    var pda = cscn.Actions?.OfType<SF.IPlayerDialogueSceneActionGetter>().FirstOrDefault();
                    Need(pda is not null && pda.DialogueList.Count == 4 && cwq.DialogTopics.Count == 9,
                         $"{CodsworthQuestEdid} must carry 4 player choices and 9 DIAL records");
                    if (pda is not null && pda.DialogueList.Count == 4)
                    {
                        var mqSpec = codsworthMqVoice is null ? null : LoadMqVoice(codsworthMqVoice);
                        var greetTopic = cwq.DialogTopics.FirstOrDefault(t => t.FormKey == new FormKey(key, CodsworthGreetTopicId));
                        var greetInfo = greetTopic?.Responses.FirstOrDefault();
                        var greetWem = greetInfo?.Responses.FirstOrDefault()?.WEMFile ?? 0u;
                        Need(greetWem == (mqSpec?.GreetingWem ?? 0u), $"{CodsworthQuestEdid} greeting WEMFile {greetWem:X8} != {(mqSpec?.GreetingWem ?? 0u):X8}");
                        if (greetInfo is not null)
                            CheckSceneResponsesAndTrot(greetInfo, mqSpec?.GreetingClips, new FormKey(key, CodsworthVoiceId), $"{CodsworthQuestEdid} greeting INFO");
                        for (int ci = 0; ci < 4; ci++)
                        {
                            var pcInfo = cwq.DialogTopics.First(t => t.FormKey == pda.DialogueList[ci].PlayerChoice.FormKey).Responses.First();
                            var rpInfo = cwq.DialogTopics.First(t => t.FormKey == pda.DialogueList[ci].NpcResponse.FormKey).Responses.First();
                            var pTxt = pcInfo.Prompt?.String ?? "";
                            var rTxt = pcInfo.Responses.FirstOrDefault()?.ResponseText?.String ?? "";
                            Need(pTxt.Length > 0 && pTxt == rTxt, $"{CodsworthQuestEdid} choice {ci} does not show full player line in both Prompt and ResponseText");
                            Need(pcInfo.Flags is { Flags: 0 } && pcInfo.SubtitlePriority == SF.DialogResponses.SubtitlePriorityLevel.Low &&
                                 rpInfo.SubtitlePriority == SF.DialogResponses.SubtitlePriorityLevel.Low,
                                 $"R11 D5: {CodsworthQuestEdid} choice {ci} lacks explicit ENAM (Flags=0, DoNotGrayOut clear) or INAM SubtitlePriority=Low");
                            Need(rpInfo.SetParentQuestStage?.OnEnd == CodsworthChoiceEndStages[ci],
                                 $"{CodsworthQuestEdid} choice {ci} OnEnd != {CodsworthChoiceEndStages[ci]}");
                            uint wantWem = mqSpec?.ChoiceReplyWems[ci] ?? 0u;
                            uint gotWem = rpInfo.Responses.FirstOrDefault()?.WEMFile ?? 0u;
                            Need(gotWem == wantWem, $"{CodsworthQuestEdid} reply {ci} WEMFile {gotWem:X8} != {wantWem:X8}");
                            CheckSceneResponsesAndTrot(rpInfo, mqSpec?.ReplyClips[ci], new FormKey(key, CodsworthVoiceId), $"{CodsworthQuestEdid} reply {ci}");
                            if (ci == 3) Need(rpInfo.Flags?.Flags == 1, $"{CodsworthQuestEdid} choice 4 lacks Goodbye flag");
                            else Need(rpInfo.StartScene.FormKey == cscn.FormKey && rpInfo.StartScenePhase == "TOPLEVELNEST" && HasPhase1Intv(rpInfo),
                                      $"{CodsworthQuestEdid} choice {ci} does not loop back to TOPLEVELNEST (Phase 1 INTV=1)");
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

        // 2k, A4 & R7: Check FO4SF_Sanctuary01 (0x817 expanded in place), FO4SF_MinRecruit00 (0xA20), and FO4SF_MQ103 (0xA50)
        var sq = plug.Quests.FirstOrDefault(x => x.FormKey == new FormKey(key, SanctuaryQuestId));
        if (sq is null) problems.Add($"no QUST 0x{SanctuaryQuestId:X} {SanctuaryQuestEdid}");
        else
        {
            Console.WriteLine($"  QUST {sq.EditorID} \"{sq.Name?.String}\" flags {sq.Data?.Flags} stages [{string.Join(",", sq.Stages.Select(s => s.Index))}] objectives {sq.Objectives.Count}");
            Need(sq.Stages.All(s => s.LogEntries.Count >= 1 && s.LogEntries[0].Flags is not null), $"{SanctuaryQuestEdid} has a stage without QSDT QuestLogEntry");
            var sal = (sq.Aliases ?? new List<SF.IAQuestAliasGetter>()).OfType<SF.IQuestReferenceAliasGetter>().FirstOrDefault(a => a.ID == SanctuaryBenchAlias);
            Need(sal is not null && (sal.Flags ?? 0).HasFlag(SF.AQuestAlias.Flag.Optional) && (sal.Flags ?? 0).HasFlag(SF.AQuestAlias.Flag.AllowReserved),
                 $"{SanctuaryQuestEdid} lacks optional SanctuaryWorkbench alias 0");
            var ss = sq.VirtualMachineAdapter?.Scripts.FirstOrDefault(x => x.Name == SanctuaryScriptName);
            Need(ss is not null && ss.Properties.FirstOrDefault(p => p.Name == "XMarkerBase") is SF.IScriptObjectPropertyGetter xp &&
                 xp.Object.FormKey == new FormKey(SfEsm, XMarkerId),
                 $"{SanctuaryQuestEdid} lacks {SanctuaryScriptName} with XMarkerBase -> Starfield.esm:00003B");
        }
        NextStoryMissionsA4.CheckA4Missions(plug, SfEsm, QuestTypeSideId, Need);
        // A7: Check FO4SF_MQ104 (0xA80, Unlikely Valentine) and FO4SF_MQ105 (0xAB0, Getting a Clue)
        NextStoryMissionsA7.CheckA7Missions(plug, SfEsm, QuestTypeSideId, Need);
        // A7cd: Check Act II FO4SF_MQ106 (0xAD0), FO4SF_MQ203 (0xAF0), FO4SF_MQ204 (0xB10), FO4SF_MQ206 (0xB30)
        NextStoryMissionsA7cd.CheckA7cdMissions(plug, SfEsm, QuestTypeSideId, Need);

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
        var femaleVoice = new SF.VoiceType(new FormKey(SfEsm, 0x013AD3), rel) { EditorID = "GenericFemaleEvenToned", Flags = SF.VoiceType.Flag.AllowDefaultDialog };
        sf.VoiceTypes.Add(femaleVoice);
        sf.Outfits.Add(new SF.Outfit(new FormKey(SfEsm, SfPrestonOutfitId), rel) { EditorID = SfPrestonOutfitEdid });
        sf.Weapons.Add(new SF.Weapon(new FormKey(SfEsm, SfPrestonWeaponId), rel) { EditorID = SfPrestonWeaponEdid });
        sf.Ammunitions.Add(new SF.Ammunition(new FormKey(SfEsm, SfPrestonAmmoId), rel) { EditorID = SfPrestonAmmoEdid });
        sf.Weapons.Add(new SF.Weapon(new FormKey(SfEsm, SfRaiderWeaponId), rel)
        {
            EditorID = SfRaiderWeaponEdid,
            AttackDamage = 52f,
            ProjectilesCount = 5,
            AttachParentSlots = new ExtendedList<IFormLinkGetter<SF.IKeywordGetter>> { new FormLink<SF.IKeywordGetter>(new FormKey(SfEsm, 0x05D4E7)) },
            ObjectTemplates = new ExtendedList<SF.ObjectTemplate<SF.Weapon.Property>> { new SF.ObjectTemplate<SF.Weapon.Property>() },
        });
        sf.Ammunitions.Add(new SF.Ammunition(new FormKey(SfEsm, SfRaiderAmmoId), rel) { EditorID = SfRaiderAmmoEdid });
        sf.Weapons.Add(new SF.Weapon(new FormKey(SfEsm, SfRaiderSidearmId), rel)
        {
            EditorID = SfRaiderSidearmEdid,
            AttackDamage = 10f,
            ProjectilesCount = 1,
            AttachParentSlots = new ExtendedList<IFormLinkGetter<SF.IKeywordGetter>> { new FormLink<SF.IKeywordGetter>(new FormKey(SfEsm, 0x05D4E7)) },
            ObjectTemplates = new ExtendedList<SF.ObjectTemplate<SF.Weapon.Property>> { new SF.ObjectTemplate<SF.Weapon.Property>() },
        });
        sf.Ammunitions.Add(new SF.Ammunition(new FormKey(SfEsm, SfRaiderSidearmAmmoId), rel) { EditorID = SfRaiderSidearmAmmoEdid });
        var modelADat3 = new byte[61];
        modelADat3[24] = 2;
        modelADat3[28] = 3;
        modelADat3[32] = 1;
        BitConverter.TryWriteBytes(modelADat3.AsSpan(33, 4), 1.0f);
        var modelARace = new SF.Race(new FormKey(SfEsm, SfModelARaceId), rel)
        {
            EditorID = SfModelARaceEdid,
            Size = SF.Size.Large,
            Flags = SF.Race.Flag.AllowPcDialog | SF.Race.Flag.HeadAxisBit0 | (SF.Race.Flag)0x0080000000000000UL,
            DAT2Unknown3 = modelADat3,
        };
        sf.Races.Add(modelARace);
        sf.Npcs.Add(new SF.Npc(new FormKey(SfEsm, SfPapaKatzId), rel)
        {
            EditorID = SfPapaKatzEdid, Name = "Synthetic Male Template",
            Race = new FormLink<SF.IRaceGetter>(humanRace.FormKey),
            Voice = new FormLinkNullable<SF.IVoiceTypeGetter>(maleVoice.FormKey),
        });
        sf.Npcs.Add(new SF.Npc(new FormKey(SfEsm, 0x01169D), rel)
        {
            EditorID = "SyntheticFemaleTemplate", Name = "Synthetic Female Template",
            Flags = SF.Npc.Flag.Female,
            Race = new FormLink<SF.IRaceGetter>(humanRace.FormKey),
            Voice = new FormLinkNullable<SF.IVoiceTypeGetter>(femaleVoice.FormKey),
        });

        // Codsworth's Garden Mini Bot body (intentionally lacks AllowPcDialog & AllowDefaultDialog in vanilla, which Write fixes)
        var miniBotDialogueQuest = new SF.Quest(new FormKey(SfEsm, 0x225314), rel) { EditorID = "DialogueMiniBot" };
        sf.Quests.Add(miniBotDialogueQuest);
        var race = new SF.Race(new FormKey(SfEsm, 0x900), rel)
        {
            EditorID = "MiniBotARace",
            Size = SF.Size.Small,
            Flags = SF.Race.Flag.TiltFrontBack,
            DialogueQuest = new FormLinkNullable<SF.IQuestGetter>(miniBotDialogueQuest.FormKey),
            DAT2Unknown3 = new byte[61],
        };
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
        var raiderKey = ModKey.FromFileName("FO4ActorRaider.esm");
        var raider = new SF.StarfieldMod(raiderKey, rel);
        raider.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Master;
        raider.Npcs.Add(new SF.Npc(new FormKey(raiderKey, RaiderId), rel) { EditorID = "FO4_LvlRaider", Name = "Synthetic Raider", Flags = SF.Npc.Flag.Respawn });
        raider.Npcs.Add(new SF.Npc(new FormKey(raiderKey, CalmProbeId), rel) { EditorID = "FO4_LvlRaider_Calm", Name = "Synthetic Raider", Flags = SF.Npc.Flag.Respawn });
        raider.ModHeader.Stats.NextFormID = 0xF04802;

        FalloutActorLooks.SeedSyntheticMasters(sf, raider, humanRace.FormKey, maleVoice.FormKey);

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
            var o = Path.Combine(outDir, "codsworth_race_framing");
            int rc = Write(sfPath, corePath, raiderPath, pointsPath, o, Plugin, World, true, CodsworthBody, codsworthRaceFraming: true);
            if (rc == 0) rc = Check(Path.Combine(o, Plugin), sfPath, corePath, raiderPath, true, true, codsworthRaceFraming: true);
            if (rc != 0) return rc;
            if (Check(Path.Combine(o, Plugin), sfPath, corePath, raiderPath, true, true, codsworthRaceFraming: false) == 0)
                { Console.WriteLine("FAIL  check passed --codsworth-race-framing 1 plugin under default 0 mode"); return 1; }
            if (Check(Path.Combine(outDir, "alias", Plugin), sfPath, corePath, raiderPath, true, true, codsworthRaceFraming: true) == 0)
                { Console.WriteLine("FAIL  check passed default --codsworth-race-framing 0 plugin under 1 mode"); return 1; }
            var vmod = SF.StarfieldMod.CreateFromBinary(Path.Combine(o, Plugin), rel, Styles(SfEsm, coreKey, raiderKey));
            vmod.Races[new FormKey(vmod.ModKey, CodsworthRaceId)].Size = SF.Size.Small;
            var vmd = Path.Combine(outDir, "codsworth_race_framing_mutated");
            Directory.CreateDirectory(vmd);
            var vlo = new[] { SfEsm, coreKey, raiderKey };
            vmod.BeginWrite.ToPath(Path.Combine(vmd, Plugin)).WithLoadOrder(vlo)
                .WithKnownMasters(vlo.Select(k => new KeyedMasterStyle(k, MasterStyle.Full)).ToArray()).Write();
            if (Check(Path.Combine(vmd, Plugin), sfPath, corePath, raiderPath, true, true, codsworthRaceFraming: true) == 0)
                { Console.WriteLine("FAIL  check passed mutated --codsworth-race-framing 1 plugin (Size.Small)"); return 1; }
            Console.WriteLine("mutation rejected: Codsworth race reverted to Size.Small (--codsworth-race-framing 1)");
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
                 "reply_wems": ["00F4C102", "00F4C103", "00F4C104", "00F4C105"],
                 "greeting_clips": [{"wem": "00F4C101", "duration": 2.1}, {"wem": "00F4C106", "duration": 3.4}],
                 "reply_clips": [[{"wem": "00F4C102", "duration": 4.0}], [{"wem": "00F4C103", "duration": 3.5}, {"wem": "00F4C107", "duration": 2.8}], [{"wem": "00F4C104", "duration": 4.1}], [{"wem": "00F4C105", "duration": 4.8}]]}
                """);
            var prestonVoice = Path.Combine(dir, "preston_voice.json");
            File.WriteAllText(prestonVoice, """
                {"greeting_wem": "00F4C201",
                 "reply_wems": ["00F4C202", "00F4C203", "00F4C204"],
                 "greeting_clips": [{"wem": "00F4C201", "duration": 2.9}],
                 "reply_clips": [[{"wem": "00F4C202", "duration": 3.6}, {"wem": "00F4C205", "duration": 4.2}], [{"wem": "00F4C203", "duration": 3.2}], [{"wem": "00F4C204", "duration": 3.9}]]}
                """);
            var o = Path.Combine(outDir, "voice");
            int rc = Write(sfPath, corePath, raiderPath, pointsPath, o, Plugin, World, true, CodsworthBody, null, voice, mqVoice, prestonVoice);
            if (rc == 0) rc = Check(Path.Combine(o, Plugin), sfPath, corePath, raiderPath, true, true, null, voice, mqVoice, prestonVoice);
            if (rc != 0) return rc;
            if (Check(Path.Combine(o, Plugin), sfPath, corePath, raiderPath, true, true) == 0)
                { Console.WriteLine("FAIL  check passed a voice build as a plain one"); return 1; }
            if (Check(Path.Combine(outDir, "alias", Plugin), sfPath, corePath, raiderPath, true, true, null, voice, mqVoice, prestonVoice) == 0)
                { Console.WriteLine("FAIL  check passed a plain build as a voice one"); return 1; }

            static SF.DialogTopic HelloDial(SF.StarfieldMod m) =>
                m.Quests[new FormKey(m.ModKey, KeeperQuestId)].DialogTopics.First(d => d.FormKey.ID == CodsworthDialId);

            var voiceMutations = new (string Name, Action<SF.StarfieldMod> Edit)[]
            {
                ("a line's wem changed", m => HelloDial(m).Responses[1].Responses[0].WEMFile = 0x00F4C009),
                ("a hello line's TROT cleared", m => HelloDial(m).Responses[0].Responses[0].TROTs.Clear()),
                ("a line said by anyone", m => HelloDial(m).Responses[0].Conditions.Clear()),
                ("a sir line for either sex", m => HelloDial(m).Responses[1].Conditions.RemoveAt(1)),
                ("a line's text changed", m => HelloDial(m).Responses[2].Responses[0].ResponseText = "Synthetic wrong line"),
                ("said by anyone but him", m => HelloDial(m).Responses[0].Conditions[0].CompareOperator = SF.CompareOperator.NotEqualTo),
                ("sex read on the speaker", m => HelloDial(m).Responses[1].Conditions[1].Data.RunOnType = SF.Condition.RunOnType.Subject),
                ("sex value 0", m => ((SF.ConditionFloat)HelloDial(m).Responses[1].Conditions[1]).ComparisonValue = 0),
                ("sex operator NotEqualTo", m => HelloDial(m).Responses[2].Conditions[1].CompareOperator = SF.CompareOperator.NotEqualTo),
                ("conditions ORed", m => HelloDial(m).Responses[1].Conditions[0].Flags = SF.Condition.Flag.OR),
                ("mq102 reply wem changed", m => m.Quests[new FormKey(m.ModKey, CodsworthQuestId)].DialogTopics.First(d => d.FormKey.ID == FirstCodsworthReplyTopicId).Responses[0].Responses[0].WEMFile = 0x00F4C999),
                ("mq102 greeting TROT cleared", m => m.Quests[new FormKey(m.ModKey, CodsworthQuestId)].DialogTopics.First(d => d.FormKey.ID == CodsworthGreetTopicId).Responses[0].Responses[0].TROTs.Clear()),
                ("preston reply wem changed", m => m.Quests[new FormKey(m.ModKey, QuestId)].DialogTopics.First(d => d.FormKey.ID == FirstPrestonReplyTopicId).Responses[0].Responses[0].WEMFile = 0x00F4C999),
                ("preston greeting TROT cleared", m => m.Quests[new FormKey(m.ModKey, QuestId)].DialogTopics.First(d => d.FormKey.ID == PrestonGreetTopicId).Responses[0].Responses[0].TROTs.Clear()),
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
                if (Check(Path.Combine(md, Plugin), sfPath, corePath, raiderPath, true, true, null, voice, mqVoice, prestonVoice) == 0)
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
            ("Codsworth race leaked Size.Medium into default 0 build (Review Item #6)", m => m.Races[new FormKey(m.ModKey, CodsworthRaceId)].Size = SF.Size.Medium),
            ("Min00 missing RaiderSidearm property (D3)", m => Min00Q(m).VirtualMachineAdapter!.Scripts[0].Properties.RemoveAll(p => p.Name == "RaiderSidearm")),
            ("R13 E3 Min00 RaiderWeapon reverted to vanilla Coachman 0x26D96B", m => ((SF.ScriptObjectProperty)Min00Q(m).VirtualMachineAdapter!.Scripts[0].Properties.First(p => p.Name == "RaiderWeapon")).Object.SetTo(new FormKey(SfEsm, SfRaiderWeaponId))),
            ("R13 E3 Min00 missing RaiderPrimaryRecordDamage property", m => Min00Q(m).VirtualMachineAdapter!.Scripts[0].Properties.RemoveAll(p => p.Name == "RaiderPrimaryRecordDamage")),
            ("R13 E3 Min00 RaiderSidearmRecordDamage mutated", m => ((SF.ScriptFloatProperty)Min00Q(m).VirtualMachineAdapter!.Scripts[0].Properties.First(p => p.Name == "RaiderSidearmRecordDamage")).Data = 3.0f),
            ("R13 E3 ConcordRaiderPrimary 0x97B AttackDamage reverted to 52", m => m.Weapons[new FormKey(m.ModKey, ConcordRaiderPrimaryWeapId)].AttackDamage = 52f),
            ("R13 E3 ConcordRaiderPrimary 0x97B ProjectilesCount reverted to 5", m => m.Weapons[new FormKey(m.ModKey, ConcordRaiderPrimaryWeapId)].ProjectilesCount = 5),
            ("R13 E3 ConcordRaiderPrimary 0x97B stripped ObjectTemplates", m => m.Weapons[new FormKey(m.ModKey, ConcordRaiderPrimaryWeapId)].ObjectTemplates = null),
            ("R13 E3 ConcordRaiderPrimary 0x97B cleared AttachParentSlots", m => m.Weapons[new FormKey(m.ModKey, ConcordRaiderPrimaryWeapId)].AttachParentSlots?.Clear()),
            ("R13 E3 ConcordRaiderPrimary 0x97B marked playable", m => { var pw = m.Weapons[new FormKey(m.ModKey, ConcordRaiderPrimaryWeapId)]; pw.MajorFlags &= ~SF.Weapon.MajorFlag.NonPlayable; pw.NonPlayable = false; }),
            ("R13 E3 ConcordRaiderPrimary 0x97B removed", m => m.Weapons.Remove(new FormKey(m.ModKey, ConcordRaiderPrimaryWeapId))),
            ("E3 ConcordRaiderSidearm 0x97A AttackDamage reverted to 10", m => m.Weapons[new FormKey(m.ModKey, ConcordRaiderSidearmWeapId)].AttackDamage = 10f),
            ("E3 ConcordRaiderSidearm 0x97A stripped ObjectTemplates", m => m.Weapons[new FormKey(m.ModKey, ConcordRaiderSidearmWeapId)].ObjectTemplates = null),
            ("E3 ConcordRaiderSidearm 0x97A cleared AttachParentSlots", m => m.Weapons[new FormKey(m.ModKey, ConcordRaiderSidearmWeapId)].AttachParentSlots?.Clear()),
            ("E3 ConcordRaiderSidearm 0x97A marked playable", m => { var sw = m.Weapons[new FormKey(m.ModKey, ConcordRaiderSidearmWeapId)]; sw.MajorFlags &= ~SF.Weapon.MajorFlag.NonPlayable; sw.NonPlayable = false; }),
            ("E3 ConcordRaiderSidearm 0x97A removed", m => m.Weapons.Remove(new FormKey(m.ModKey, ConcordRaiderSidearmWeapId))),
            ("R13 E3 Holding CELL 0xB60 FULL reverted to FO4SF prefix", m => m.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(sb => sb.Cells).First(c => c.FormKey.ID == MissionHoldingCellId).Name = "FO4SF Mission Holding Cell"),
            ("Preston post scene 0x990 removed from keeper", m => Keeper(m).Scenes.RemoveAll(s => s.FormKey.ID == PrestonPostTalkSceneId)),
            ("Codsworth post scene 0x9C0 removed from keeper", m => Keeper(m).Scenes.RemoveAll(s => s.FormKey.ID == CodsworthPostSceneId)),
            ("Codsworth post scene 0x9C0 wrong alias ID 0", m => Keeper(m).Scenes.First(s => s.FormKey.ID == CodsworthPostSceneId).Actors[0].ID = 0),
            ("Preston post scene 0x990 sets quest stage", m => Keeper(m).DialogTopics.First(t => t.FormKey.ID == FirstPrestonPostReplyTopicId).Responses[0].SetParentQuestStage = new SF.DialogSetParentQuestStage { OnBegin = -1, OnEnd = 35 }),
            ("Codsworth post scene 0x9C0 replays primary greeting", m => Keeper(m).DialogTopics.First(t => t.FormKey.ID == CodsworthPostGreetTopicId).Responses[0].Responses[0].ResponseText = "Synthetic robot greeting."),
            ("Min00 binds dead PrestonTalkScene property", m => Min00Q(m).VirtualMachineAdapter!.Scripts[0].Properties.Add(new SF.ScriptObjectProperty
            {
                Name = "PrestonTalkScene", Flags = SF.ScriptProperty.Flag.Edited, Alias = -1,
                Object = new FormLink<SF.IStarfieldMajorRecordGetter>(new FormKey(m.ModKey, PrestonTalkSceneId)),
            })),
            ("Min00 binds dead PrestonPostTalkScene property", m => Min00Q(m).VirtualMachineAdapter!.Scripts[0].Properties.Add(new SF.ScriptObjectProperty
            {
                Name = "PrestonPostTalkScene", Flags = SF.ScriptProperty.Flag.Edited, Alias = -1,
                Object = new FormLink<SF.IStarfieldMajorRecordGetter>(new FormKey(m.ModKey, PrestonPostTalkSceneId)),
            })),
            ("Codsworth01 binds dead CodsworthPostScene property", m => Cods01(m).VirtualMachineAdapter!.Scripts[0].Properties.Add(new SF.ScriptObjectProperty
            {
                Name = "CodsworthPostScene", Flags = SF.ScriptProperty.Flag.Edited, Alias = -1,
                Object = new FormLink<SF.IStarfieldMajorRecordGetter>(new FormKey(m.ModKey, CodsworthPostSceneId)),
            })),
            ("Preston choice 0 missing ENAM flags (D5)", m => Min00Q(m).DialogTopics.First(t => t.FormKey.ID == FirstPrestonChoiceTopicId).Responses[0].Flags = null),
            ("Preston choice 0 sets DoNotGrayOut (D5)", m => Min00Q(m).DialogTopics.First(t => t.FormKey.ID == FirstPrestonChoiceTopicId).Responses[0].Flags = new SF.DialogResponseFlags { Flags = (short)SF.DialogResponses.Flag.DoNotGrayOut }),
            ("Codsworth voice lacks AllowDefaultDialog", m => m.VoiceTypes[new FormKey(m.ModKey, CodsworthVoiceId)].Flags &= ~SF.VoiceType.Flag.AllowDefaultDialog),
            ("Codsworth missing Talk prompt", m => m.Npcs[new FormKey(m.ModKey, CodsworthNpcId)].ActivateTextOverride = null),
            ("Codsworth retains DefaultTemplate", m => m.Npcs[new FormKey(m.ModKey, CodsworthNpcId)].DefaultTemplate.SetTo(new FormKey(SfEsm, 0x902))),
            ("Codsworth talk activator removed", m => m.Activators.Remove(new FormKey(m.ModKey, CodsworthTalkActiId))),
            ("Codsworth talk message removed", m => m.Messages.Remove(new FormKey(m.ModKey, CodsworthTalkMsgId))),
            ("Codsworth talk message != 4 buttons", m => m.Messages[new FormKey(m.ModKey, CodsworthTalkMsgId)].MenuButtons.Add(new SF.MessageButton { Text = "Extra5" })),
            ("Preston missing Talk prompt", m => m.Npcs[new FormKey(m.ModKey, PrestonNpcId)].ActivateTextOverride = null),
            ("Preston talk message removed", m => m.Messages.Remove(new FormKey(m.ModKey, PrestonTalkMsgId))),
            ("Preston talk message != 4 buttons", m => m.Messages[new FormKey(m.ModKey, PrestonTalkMsgId)].MenuButtons.RemoveAt(0)),
            ("Preston race reverted to robot race", m => m.Npcs[new FormKey(m.ModKey, PrestonNpcId)].Race.SetTo(new FormKey(SfEsm, 0x900))),
            ("Preston missing colonial outfit", m => m.Npcs[new FormKey(m.ModKey, PrestonNpcId)].DefaultOutfit.Clear()),
            ("Preston talk scene removed", m => Min00Q(m).Scenes.Clear()),
            ("Preston talk scene lacks DEVT", m => Min00Q(m).Scenes[0].DEVT = false),
            ("Preston talk scene lacks MissionTalkUseMessageBox gate", m => Min00Q(m).Scenes[0].Conditions.RemoveAt(2)),
            ("Preston talk scene has 0x2814 flags", m => Min00Q(m).Scenes[0].Flags = (SF.Scene.Flag)0x2814),
            ("Preston talk scene has non-null SCPI", m => Min00Q(m).Scenes[0].SCPI = new byte[] { 0x37, 0x00 }),
            ("Preston talk scene has extra ID=-2 actor", m => Min00Q(m).Scenes[0].Actors.Add(new SF.SceneActor
            {
                ID = unchecked((uint)-2),
                BehaviorFlags = (SF.SceneActor.BehaviorFlag)0x10A,
                Flags = SF.SceneActor.Flag.NoCommandState,
            })),
            ("Codsworth scene lacks DEVT", m => Cods01(m).Scenes[0].DEVT = false),
            ("Codsworth scene lacks MissionTalkUseMessageBox gate", m => Cods01(m).Scenes[0].Conditions.RemoveAt(2)),
            ("Codsworth scene has 0x2814 flags", m => Cods01(m).Scenes[0].Flags = (SF.Scene.Flag)0x2814),
            ("Codsworth scene has non-null SCPI", m => Cods01(m).Scenes[0].SCPI = new byte[] { 0x37, 0x00 }),
            ("Codsworth scene has extra ID=-2 actor", m => Cods01(m).Scenes[0].Actors.Add(new SF.SceneActor
            {
                ID = unchecked((uint)-2),
                BehaviorFlags = (SF.SceneActor.BehaviorFlag)0x10A,
                Flags = SF.SceneActor.Flag.NoCommandState,
            })),
            ("MissionTalkUseMessageBox global removed", m => m.Globals.Remove(new FormKey(m.ModKey, MissionTalkUseMessageBoxGlobId))),
            ("MissionTalkUseMessageBox global nonzero default", m => m.Globals[new FormKey(m.ModKey, MissionTalkUseMessageBoxGlobId)].Data = 1f),
            ("Codsworth01 binds dead CodsworthScene property", m => Cods01(m).VirtualMachineAdapter!.Scripts[0].Properties.Add(new SF.ScriptObjectProperty
            {
                Name = "CodsworthScene", Flags = SF.ScriptProperty.Flag.Edited, Alias = -1,
                Object = new FormLink<SF.IStarfieldMajorRecordGetter>(new FormKey(m.ModKey, CodsworthSceneId)),
            })),
            ("Codsworth01 missing TalkUseMessageBox property", m => Cods01(m).VirtualMachineAdapter!.Scripts[0].Properties.RemoveAll(p => p.Name == "TalkUseMessageBox")),
            ("Min00 missing TalkUseMessageBox property", m => Min00Q(m).VirtualMachineAdapter!.Scripts[0].Properties.RemoveAll(p => p.Name == "TalkUseMessageBox")),
            ("Min00 stage 30 lacks QSDT log entry", m => Min00Q(m).Stages.First(s => s.Index == 30).LogEntries.Clear()),
            ("Codsworth01 stage 10 lacks QSDT log entry", m => Cods01(m).Stages.First(s => s.Index == 10).LogEntries.Clear()),
            ("Sanctuary01 stage 10 lacks QSDT log entry", m => Sanct01(m).Stages.First(s => s.Index == 10).LogEntries.Clear()),
            ("Preston alias not Optional", m => ((SF.QuestReferenceAlias)Min00Q(m).Aliases![0]).Flags &= ~SF.AQuestAlias.Flag.Optional),
            ("Codsworth alias not Optional", m => ((SF.QuestReferenceAlias)Cods01(m).Aliases![0]).Flags &= ~SF.AQuestAlias.Flag.Optional),
            ("raider alias lacks combat package", m => ((SF.QuestReferenceAlias)Min00Q(m).Aliases![1]).PackageData.Clear()),
            ("raider alias lacks AmmoShotshell", m => ((SF.QuestReferenceAlias)Min00Q(m).Aliases![1]).Items?.Clear()),
            ("Task 1i WRLD override leaked into FO4SFMission.esm", m => m.Worldspaces.Add(new SF.Worldspace(new FormKey(coreKey, 0x803), rel) { EditorID = World })),
            ("raider ACHR reverted to unmerged coords", m =>
            {
                var r0 = PersistentNpcRefsMutable(m).First(r => r.FormKey.ID == FirstRaiderRefId);
                r0.Position = new P3Float(-829.06f, 1008.31f, 88.09f);
            }),
            ("Preston non-ending reply lacks INTV=1", m => Min00Q(m).DialogTopics.First(d => d.FormKey.ID == FirstPrestonReplyTopicId).Responses[0].INTV = null),
            ("Codsworth non-ending reply lacks INTV=1", m => Cods01(m).DialogTopics.First(d => d.FormKey.ID == FirstCodsworthReplyTopicId).Responses[0].INTV = null),
            ("Sanctuary01 bench alias 0 removed", m => Sanct01(m).Aliases?.RemoveAll(a => a is SF.QuestReferenceAlias qa && qa.ID == SanctuaryBenchAlias)),
            ("Codsworth NPC_ and ACHR removed", m =>
            {
                m.Npcs.Remove(new FormKey(m.ModKey, CodsworthNpcId));
                m.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(sb => sb.Cells).First().Persistent.RemoveAll(r => r.FormKey.ID == CodsworthRefId);
            }),
            ("Codsworth ACHR removed", m => m.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(sb => sb.Cells).First().Persistent.RemoveAll(r => r.FormKey.ID == CodsworthRefId)),
            ("Codsworth not Essential", m => m.Npcs[new FormKey(m.ModKey, CodsworthNpcId)].Flags &= ~SF.Npc.Flag.Essential),
            ("Codsworth not Unique", m => m.Npcs[new FormKey(m.ModKey, CodsworthNpcId)].Flags &= ~SF.Npc.Flag.Unique),
            ("Codsworth respawns", m => m.Npcs[new FormKey(m.ModKey, CodsworthNpcId)].Flags |= SF.Npc.Flag.Respawn),
            ("Codsworth script property removed", m => Keeper(m).VirtualMachineAdapter!.Scripts[0].Properties.RemoveAll(p => p.Name == "Codsworth")),
            ("keeper quest removed", m => m.Quests.Remove(new FormKey(m.ModKey, KeeperQuestId))),
            ("keeper carries StartsEnabled", m => Keeper(m).Data!.Flags |= SF.Quest.Flag.StartsEnabled),
            ("Min00 carries 0x10000 flag", m => Min00Q(m).Data!.Flags |= (SF.Quest.Flag)0x10000),
            ("Min00 MuteDuplicateObjectiveToasts removed", m => Min00Q(m).VirtualMachineAdapter!.Scripts[0].Properties.RemoveAll(p => p.Name == "MuteDuplicateObjectiveToasts")),
            ("Codsworth01 LandingHandoff mutated", m => ((SF.ScriptStringProperty)m.Quests[new FormKey(m.ModKey, CodsworthQuestId)].VirtualMachineAdapter!.Scripts[0].Properties.First(p => p.Name == "LandingHandoff")).Data = "invalid"),
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
            ("Preston Assistance reverted to HelpsAllies", m => m.Npcs[new FormKey(m.ModKey, PrestonNpcId)].Assistance = SF.Npc.AssistanceType.HelpsAllies),
            ("Preston Aggression set to Aggressive", m => m.Npcs[new FormKey(m.ModKey, PrestonNpcId)].Aggression = SF.Npc.AggressionType.Aggressive),
            ("Minutemen only Friend to the player", m => m.Factions[new FormKey(m.ModKey, MinutemenFactionId)].Relations[0].Reaction = SF.CombatReaction.Friend),
            ("Minutemen Ally to another faction", m => m.Factions[new FormKey(m.ModKey, MinutemenFactionId)].Relations[0].Target.SetTo(new FormKey(SfEsm, 0x901))),
            ("follow quest removed", m => m.Quests.Remove(new FormKey(m.ModKey, ComQuestId))),
            ("follow quest shows in the Missions tab", m => Com(m).Data!.Flags |= SF.Quest.Flag.DisplaysInHud),
            ("follow alias has no package", m => ((SF.QuestReferenceAlias)Com(m).Aliases![0]).PackageData.Clear()),
            ("duplicate second Sanctuary quest added", m => m.Quests.Add(new SF.Quest(new FormKey(m.ModKey, 0xA7E), rel) { EditorID = "FO4SF_Sanctuary02", Name = "Duplicate Sanctuary" })),
            ("FO4SF_MinRecruit00 removed", m => m.Quests.Remove(new FormKey(m.ModKey, NextStoryMissionsA4.MinRecruit00QuestId))),
            ("FO4SF_MinRecruit00 has StartGameEnabled", m => m.Quests[new FormKey(m.ModKey, NextStoryMissionsA4.MinRecruit00QuestId)].Data!.Flags |= SF.Quest.Flag.StartGameEnabled),
            ("FO4SF_MQ103 removed", m => m.Quests.Remove(new FormKey(m.ModKey, NextStoryMissionsA4.Mq103QuestId))),
            ("FO4SF_MQ103 has StartGameEnabled", m => m.Quests[new FormKey(m.ModKey, NextStoryMissionsA4.Mq103QuestId)].Data!.Flags |= SF.Quest.Flag.StartGameEnabled),
            ("Min01 BedTotal GLOB mutated", m => m.Globals[new FormKey(m.ModKey, NextStoryMissionsA4.Min01BedTotalId)].Data = 99f),
            ("Sanctuary01 WorkbenchBuildMsg removed", m => m.Messages.Remove(new FormKey(m.ModKey, NextStoryMissionsA4.WorkbenchBuildMsgId))),
            ("FO4SF_MinRecruit00 stage 50 lacks QSDT log entry", m => m.Quests[new FormKey(m.ModKey, NextStoryMissionsA4.MinRecruit00QuestId)].Stages.First(s => s.Index == 50).LogEntries.Clear()),
            ("FO4SF_MinRecruit00 carries StartsEnabled", m => m.Quests[new FormKey(m.ModKey, NextStoryMissionsA4.MinRecruit00QuestId)].Data!.Flags |= SF.Quest.Flag.StartsEnabled),
            ("FO4SF_MQ103 stage 10 lacks QSDT log entry", m => m.Quests[new FormKey(m.ModKey, NextStoryMissionsA4.Mq103QuestId)].Stages.First(s => s.Index == 10).LogEntries.Clear()),
            ("FO4SF_MQ103 carries 0x10000 flag", m => m.Quests[new FormKey(m.ModKey, NextStoryMissionsA4.Mq103QuestId)].Data!.Flags |= (SF.Quest.Flag)0x10000),
            ("FO4SF_MQ104 removed", m => m.Quests.Remove(new FormKey(m.ModKey, NextStoryMissionsA7.Mq104QuestId))),
            ("FO4SF_MQ104 has StartGameEnabled", m => m.Quests[new FormKey(m.ModKey, NextStoryMissionsA7.Mq104QuestId)].Data!.Flags |= SF.Quest.Flag.StartGameEnabled),
            ("FO4SF_MQ104 stage 10 lacks QSDT log entry", m => m.Quests[new FormKey(m.ModKey, NextStoryMissionsA7.Mq104QuestId)].Stages.First(s => s.Index == 10).LogEntries.Clear()),
            ("FO4SF_MQ104 carries StartsEnabled", m => m.Quests[new FormKey(m.ModKey, NextStoryMissionsA7.Mq104QuestId)].Data!.Flags |= SF.Quest.Flag.StartsEnabled),
            ("FO4SF_MQ105 removed", m => m.Quests.Remove(new FormKey(m.ModKey, NextStoryMissionsA7.Mq105QuestId))),
            ("FO4SF_MQ105 has StartGameEnabled", m => m.Quests[new FormKey(m.ModKey, NextStoryMissionsA7.Mq105QuestId)].Data!.Flags |= SF.Quest.Flag.StartGameEnabled),
            ("FO4SF_MQ105 stage 10 lacks QSDT log entry", m => m.Quests[new FormKey(m.ModKey, NextStoryMissionsA7.Mq105QuestId)].Stages.First(s => s.Index == 10).LogEntries.Clear()),
            ("FO4SF_MQ105 carries 0x10000 flag", m => m.Quests[new FormKey(m.ModKey, NextStoryMissionsA7.Mq105QuestId)].Data!.Flags |= (SF.Quest.Flag)0x10000),
            ("FO4SF_KelloggCigar removed", m => m.MiscItems.Remove(new FormKey(m.ModKey, NextStoryMissionsA7.KelloggCigarMiscId))),
            ("FO4SF_MQ106Armed GLOB removed", m => m.Globals.Remove(new FormKey(m.ModKey, NextStoryMissionsA7.Mq106ArmedGlobId))),
            ("FO4SF_MQ106 removed", m => m.Quests.Remove(new FormKey(m.ModKey, NextStoryMissionsA7cd.Mq106QuestId))),
            ("FO4SF_MQ106 has StartGameEnabled", m => m.Quests[new FormKey(m.ModKey, NextStoryMissionsA7cd.Mq106QuestId)].Data!.Flags |= SF.Quest.Flag.StartGameEnabled),
            ("FO4SF_MQ106 stage 10 lacks QSDT log entry", m => m.Quests[new FormKey(m.ModKey, NextStoryMissionsA7cd.Mq106QuestId)].Stages.First(s => s.Index == 10).LogEntries.Clear()),
            ("FO4_Kellogg marked Essential", m => m.Npcs[new FormKey(m.ModKey, NextStoryMissionsA7cd.KelloggNpcId)].Flags |= SF.Npc.Flag.Essential),
            ("FO4SF_MQ203 removed", m => m.Quests.Remove(new FormKey(m.ModKey, NextStoryMissionsA7cd.Mq203QuestId))),
            ("FO4SF_MQ203 carries StartsEnabled", m => m.Quests[new FormKey(m.ModKey, NextStoryMissionsA7cd.Mq203QuestId)].Data!.Flags |= SF.Quest.Flag.StartsEnabled),
            ("FO4_DoctorAmari lacks Female flag", m => m.Npcs[new FormKey(m.ModKey, NextStoryMissionsA7cd.DoctorAmariNpcId)].Flags &= ~SF.Npc.Flag.Female),
            ("FO4SF_MQ204 removed", m => m.Quests.Remove(new FormKey(m.ModKey, NextStoryMissionsA7cd.Mq204QuestId))),
            ("FO4SF_MQ204 stage 10 lacks QSDT log entry", m => m.Quests[new FormKey(m.ModKey, NextStoryMissionsA7cd.Mq204QuestId)].Stages.First(s => s.Index == 10).LogEntries.Clear()),
            ("FO4SF_MQ206 removed", m => m.Quests.Remove(new FormKey(m.ModKey, NextStoryMissionsA7cd.Mq206QuestId))),
            ("FO4SF_MQ206 carries 0x10000 flag", m => m.Quests[new FormKey(m.ModKey, NextStoryMissionsA7cd.Mq206QuestId)].Data!.Flags |= (SF.Quest.Flag)0x10000),
            ("FO4_CourserZ247 marked Essential", m => m.Npcs[new FormKey(m.ModKey, NextStoryMissionsA7cd.CourserZ247NpcId)].Flags |= SF.Npc.Flag.Essential),
            ("FO4SF_CourserChip removed", m => m.MiscItems.Remove(new FormKey(m.ModKey, NextStoryMissionsA7cd.CourserChipMiscId))),
            ("FO4SF_MQ207Armed GLOB removed", m => m.Globals.Remove(new FormKey(m.ModKey, NextStoryMissionsA7cd.Mq207ArmedGlobId))),
        };
        foreach (var (name, edit) in mutations.Concat(FalloutActorLooks.GetSelfTestMutations(raiderKey)))
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
