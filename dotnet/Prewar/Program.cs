// Build and validate FO4SFPrewar.esm (S1 Pre-War quest, actors, 5 stand-in beats, Codsworth Mr. Handy race copy,
// and Stage 20 Vault111Cryo handoff preserving fo4_vault111 Skip Pre-War).

using System.Globalization;
using System.IO.Compression;
using System.Text.Json;
using Mutagen.Bethesda;
using Mutagen.Bethesda.Environments;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Assets;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Cache;
using Mutagen.Bethesda.Plugins.Masters;
using Mutagen.Bethesda.Plugins.Order;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield.Assets;
using Noggog;
using SF = Mutagen.Bethesda.Starfield;

try
{
    return args.Length switch
    {
        >= 3 when args[0] == "write" => PrewarBuilder.Write(
            args[1], args[2],
            PrewarBuilder.ArgOrNull(args, "--handy-esm"),
            PrewarBuilder.ArgOrNull(args, "--spec"),
            PrewarBuilder.ArgOrNull(args, "--voices")),
        >= 3 when args[0] == "check" => PrewarBuilder.Check(
            args[1], args[2],
            PrewarBuilder.ArgOrNull(args, "--handy-esm"),
            PrewarBuilder.ArgOrNull(args, "--spec"),
            PrewarBuilder.ArgOrNull(args, "--voices")),
        >= 2 when args[0] == "selftest" => PrewarBuilder.SelfTest(args[1]),
        _ => PrewarBuilder.Usage(),
    };
}
catch (PrewarBuilder.Refusal e)
{
    Console.Error.WriteLine("refused: " + e.Message);
    return 2;
}

static class PrewarBuilder
{
    public const string Plugin = "FO4SFPrewar.esm";
    public const string QuestEdid = "FO4SF_PrewarQuest";
    public const string QuestScript = "FO4SF_PrewarQuest";
    public const string StandInsScript = "FO4SF_PrewarStandIns";

    // Fixed local FormIDs matching src/fo4sf/prewar/s1_spec.py (0x000800..0x00082A)
    public const uint QuestId = 0x800;
    public const uint CodsworthRaceId = 0x801, CodsworthBptdId = 0x802;
    public const uint CodsworthNpcId = 0x803, CodsworthRefId = 0x804;
    public const uint SpouseMaleNpcId = 0x805, SpouseFemaleNpcId = 0x806, SpouseRefId = 0x807;
    public const uint VaultTecRepNpcId = 0x808, VaultTecRepRefId = 0x809;
    public const uint SoldierCheckerNpcId = 0x80A, SoldierCheckerRefId = 0x80B;
    public const uint VaultDoctorNpcId = 0x80C, VaultDoctorRefId = 0x80D;
    public const uint KelloggNpcId = 0x80E, KelloggRefId = 0x80F;
    public const uint InstAgentMNpcId = 0x810, InstAgentMRefId = 0x811;
    public const uint InstAgentFNpcId = 0x812, InstAgentFRefId = 0x813;
    public const uint PrewarFactionId = 0x814, CrowdFactionId = 0x815;
    public const uint CrowdRunnerNpcId = 0x816;
    public const uint CrowdRunner01RefId = 0x817, CrowdRunner02RefId = 0x818, CrowdRunner03RefId = 0x819, CrowdRunner04RefId = 0x81A;
    public const uint Vertibird01RefId = 0x81B, Vertibird02RefId = 0x81C;
    public const uint ExtLiftPlatformRefId = 0x81D;
    public const uint NukeAnchorRefId = 0x81E;
    public const uint VaultArrivalMarkerId = 0x81F;
    public const uint KelloggMarkRefId = 0x820;
    public const uint SpousePodMarkRefId = 0x821;
    public const uint PlayerPodMarkRefId = 0x822;
    public const uint CrowdGoalMarkRefId = 0x823;
    public const uint HouseSpawnMarkerId = 0x824;
    public const uint UseMessageBoxGlobId = 0x825;
    public const uint HoldingCellId = 0x826;
    public const uint VertibirdBaseId = 0x827;
    public const uint ExtLiftBaseId = 0x828;
    public const uint CodsworthOutfitId = 0x829;
    public const uint StageActiveGlobId = 0x82A;
    public const uint InstMalePodMarkRefId = 0x82B;
    public const uint InstFemalePodMarkRefId = 0x82C;
    public const uint CrowdBridgeMarkRefId = 0x82D;
    public const uint BroadcastNpcId = 0x82E, BroadcastRefId = 0x82F;
    public const uint SpouseMaleRefId = 0x830;
    public const uint Vertibird01HoverMarkRefId = 0x831, Vertibird02HoverMarkRefId = 0x832;
    public const uint VaultSuitStandInId = 0x833;

    // Companion & voice assets cleanly separated between 0x833 and 0x900
    public const uint RepVoiceId = 0x8E9, BroadcastVoiceId = 0x8EA, SoldierVoiceId = 0x8EB;
    public const uint DoctorVoiceId = 0x8EC, MaleVoiceId = 0x8ED, FemaleVoiceId = 0x8EE;
    public const uint CodsworthVoiceId = 0x8F0;
    public const uint CodsworthSkinId = 0x8F1;
    public const uint CodsworthAaStartId = 0x8F2;
    public const uint VoiceStartId = 0x900;

    // Built-in Starfield.esm reference IDs
    public const uint SfHumanRaceId = 0x00347D;
    public const uint SfPlayerFactionId = 0x01C21C;
    public const uint SfXMarkerId = 0x00003B;
    public const uint SfMaleEvenTonedVoiceId = 0x013AD2;
    public const uint SfFemaleEvenTonedVoiceId = 0x013ADD;
    public const uint SfMiniBotSkinId = 0x3FFD3A;
    public const uint SfExplosionFlashImodId = 0x064C26;
    public const uint SfExplosionNukeImodId = 0x02458E;
    public const uint SfFadeToBlackImodId = 0x01F60F;
    public const uint SfVaultSuitStandInArmorId = 0x0CC4F6; // Clothes_Worker_Jumpsuit_ECS_Security
    public const uint SfMaleCitizenTplId = 0x02A9B6;        // EncCitizenFaceM01_EvenToned_AltFace02
    public const uint SfFemaleCitizenTplId = 0x02A998;      // EncCitizenFaceF10_WesternAmerican_AltFace
    public const uint SfOutfitCitizenFormalId = 0x0AA0A5;   // Outfit_Citizen_Formal
    public const uint SfOutfitNhCitizenId = 0x048F36;       // Outfit_NH_Citizen
    public const uint SfOutfitBusinessId = 0x0148F3;        // Outfit_Clothes_Business_Any_NoRyujin
    public const uint SfOutfitArmyFatiguesId = 0x0D41FF;    // Outfit_Clothes_UCNavy_Fatigues_SY-920
    public const uint SfOutfitDoctorId = 0x0021F9;          // Outfit_Clothes_Medical_Doctor_03
    public const uint SfOutfitKelloggId = 0x133D53;         // Outfit_Clothes_First_Mercenary_01_with_Hat
    public const uint SfOutfitScientistId = 0x034115;       // Outfit_Clothes_ScienceLabTec_02
    public const uint SfSirenOnWwedId = 0x030A99;           // WwiseEvent_QST_NewAtlantis_EmergencyAlarm_On_State
    public const uint SfSirenOffWwedId = 0x030A9C;          // WwiseEvent_QST_NewAtlantis_EmergencyAlarm_Off_State
    public const uint SfVertibirdFlybyWwedId = 0x2B16D7;    // WwiseEvent_VEHNPCFlyByClose
    public const uint SfNukeExplosionWwedId = 0x17B6F0;     // QST_Orlase_Ship_Decoy_Explosion_WEF
    public const uint SfGunshotWwedId = 0x23AF77;           // WwiseEvent_WPNHandRifleRussianAssaultRiflePCFire

    public const string SfHumanRaceEdid = "HumanRace";
    public const string SfMiniBotEdid = "OutpostRobotMiniBotA_Garden";
    public const string HandyRaceEdid = "FO4SF_HandyRace";
    public const string HandyBptdEdid = "FO4SF_HandyBodyPartData";

    public static readonly ushort[] RequiredStages = { 0, 10, 20, 30, 40, 50, 60, 200 };

    static readonly ModKey SfEsm = ModKey.FromFileName("Starfield.esm");
    static readonly SF.StarfieldRelease Rel = SF.StarfieldRelease.Starfield;

    public sealed class Refusal(string msg) : Exception(msg);

    public sealed record MarkerPlacement(float X, float Y, float Z, float RotZ = 0f, bool Interior = false);

    public sealed record PrewarSpec(
        string? SanctuaryEsmPath,
        string SanctuaryWorldEdid,
        string? PortEsmPath,
        string PortVaultCellEdid,
        uint PrewarVaultCellId,
        bool FemaleSpouse,
        string? VertibirdModel,
        string? ExtLiftModel,
        float ExtLiftDropM,
        float NukeDelayS,
        Dictionary<string, MarkerPlacement> Markers);

    public sealed record VoiceLineSpec(string SpeakerEdid, string Text, uint Wem, float Duration, string? VoiceTypeEdid = null);

    public sealed record VoicesSpec(
        IReadOnlyList<VoiceLineSpec> KelloggScene,
        IReadOnlyList<VoiceLineSpec> CodsworthScene,
        IReadOnlyList<VoiceLineSpec> VaultTecRepScene,
        IReadOnlyList<VoiceLineSpec> BroadcastScene,
        IReadOnlyList<VoiceLineSpec> SoldierGateScene,
        IReadOnlyList<VoiceLineSpec> VaultDoctorScene);

    public static int Usage()
    {
        Console.Error.WriteLine(
            "usage: Prewar write <Starfield.esm> <out dir> [--handy-esm <FO4SF_RA2Handy.esm>] [--spec <spec.json>] [--voices <voices.json>]\n" +
            "       Prewar check <FO4SFPrewar.esm> <Starfield.esm> [--handy-esm <FO4SF_RA2Handy.esm>] [--spec <spec.json>] [--voices <voices.json>]\n" +
            "       Prewar selftest <scratch dir>");
        return 1;
    }

    public static string? ArgOrNull(string[] args, string flag)
    {
        for (int i = 0; i < args.Length - 1; i++)
            if (args[i] == flag)
                return args[i + 1];
        return null;
    }

    static BinaryReadParameters Styles(params ModKey[] fullMasters)
    {
        var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        foreach (var k in fullMasters) styles.Set(new KeyedMasterStyle(k, MasterStyle.Full));
        return new BinaryReadParameters { MasterFlagsLookup = styles };
    }

    static PrewarSpec LoadSpec(string? specPath)
    {
        var defaults = DefaultMarkers();
        if (string.IsNullOrWhiteSpace(specPath))
        {
            return new PrewarSpec(null, "FO4SF_PrewarSanctuaryWorld", null, "FO4Port_PrewarVault111", 0, true, null, null, 21.6f, 4.2f, defaults);
        }
        if (!File.Exists(specPath)) throw new Refusal($"--spec {specPath} does not exist");
        using var doc = JsonDocument.Parse(File.ReadAllText(specPath));
        var root = doc.RootElement;
        string? sancEsm = null;
        string sancWorld = "FO4SF_PrewarSanctuaryWorld";
        if (root.TryGetProperty("sanctuary_world", out var sw) && sw.ValueKind == JsonValueKind.Object)
        {
            if (sw.TryGetProperty("esm", out var se) && se.ValueKind == JsonValueKind.String) sancEsm = se.GetString();
            if (sw.TryGetProperty("world_edid", out var we) && we.ValueKind == JsonValueKind.String && !string.IsNullOrWhiteSpace(we.GetString()))
                sancWorld = we.GetString()!;
        }
        string? portEsm = null;
        string portCell = "FO4Port_PrewarVault111";
        uint vaultCellId = 0;
        if (root.TryGetProperty("port_vault", out var pv) && pv.ValueKind == JsonValueKind.Object)
        {
            if (pv.TryGetProperty("esm", out var pe) && pe.ValueKind == JsonValueKind.String) portEsm = pe.GetString();
            if (pv.TryGetProperty("cell_edid", out var ce) && ce.ValueKind == JsonValueKind.String && !string.IsNullOrWhiteSpace(ce.GetString()))
                portCell = ce.GetString()!;
            if (pv.TryGetProperty("cell_form_id", out var cf) && cf.ValueKind == JsonValueKind.Number)
                vaultCellId = cf.GetUInt32();
        }
        bool femaleSpouse = !root.TryGetProperty("player_female_spouse", out var fs) || fs.GetBoolean();
        string? vbModel = root.TryGetProperty("vertibird_model", out var vm) && vm.ValueKind == JsonValueKind.String ? vm.GetString() : null;
        string? liftModel = root.TryGetProperty("ext_lift_model", out var lm) && lm.ValueKind == JsonValueKind.String ? lm.GetString() : null;
        float dropM = root.TryGetProperty("elevator_drop_m", out var dm) && dm.ValueKind == JsonValueKind.Number ? dm.GetSingle() : 21.6f;
        float nukeDelay = root.TryGetProperty("nuke_delay_s", out var nd) && nd.ValueKind == JsonValueKind.Number ? nd.GetSingle() : 4.2f;
        if (root.TryGetProperty("markers", out var mk) && mk.ValueKind == JsonValueKind.Object)
        {
            foreach (var prop in mk.EnumerateObject())
            {
                if (prop.Value.ValueKind == JsonValueKind.Array && prop.Value.GetArrayLength() >= 3)
                {
                    var arr = prop.Value;
                    bool isInt = defaults.TryGetValue(prop.Name, out var old) && old.Interior;
                    float rz = arr.GetArrayLength() >= 4 ? arr[3].GetSingle() : 0f;
                    defaults[prop.Name] = new MarkerPlacement(arr[0].GetSingle(), arr[1].GetSingle(), arr[2].GetSingle(), rz, isInt);
                }
            }
        }
        return new PrewarSpec(sancEsm, sancWorld, portEsm, portCell, vaultCellId, femaleSpouse, vbModel, liftModel, dropM, nukeDelay, defaults);
    }

    static List<VoiceLineSpec> ParseSceneArray(JsonElement root, string key, IReadOnlyList<VoiceLineSpec> fallback)
    {
        if (!root.TryGetProperty(key, out var arr) || arr.ValueKind != JsonValueKind.Array || arr.GetArrayLength() == 0)
            return new List<VoiceLineSpec>(fallback);
        var list = new List<VoiceLineSpec>();
        foreach (var row in arr.EnumerateArray())
        {
            if (row.ValueKind != JsonValueKind.Array || row.GetArrayLength() < 4) continue;
            string spk = row[0].GetString() ?? "FO4SF_PrewarKelloggNPC";
            string txt = row[1].GetString() ?? "...";
            uint wem = row[2].ValueKind == JsonValueKind.String
                ? uint.Parse(row[2].GetString()!.Replace("0x", "", StringComparison.OrdinalIgnoreCase), NumberStyles.HexNumber)
                : row[2].GetUInt32();
            float dur = row[3].GetSingle();
            string? vtyp = row.GetArrayLength() >= 5 && row[4].ValueKind == JsonValueKind.String ? row[4].GetString() : null;
            list.Add(new VoiceLineSpec(spk, string.IsNullOrWhiteSpace(txt) ? "..." : txt, wem, MathF.Max(1.0f, dur), vtyp));
        }
        return list.Count > 0 ? list : new List<VoiceLineSpec>(fallback);
    }

    static VoicesSpec LoadVoices(string? voicesPath)
    {
        var fallbackKellogg = new[]
        {
            new VoiceLineSpec("FO4SF_PrewarInstAgentMNPC", "Almost got it... Hold on...", 0u, 2.0f, "FO4SF_PrewarMaleVoice"),
            new VoiceLineSpec("FO4SF_PrewarKelloggNPC", "Didn't have to happen this way. We've got the backup.", 0u, 3.2f, "FO4SF_PrewarMaleVoice"),
        };
        var fallbackCods = new[] { new VoiceLineSpec("FO4SF_PrewarCodsworthNPC", "Good morning! Breakfast is ready.", 0u, 2.2f, "FO4SF_PrewarCodsworthVoice") };
        var fallbackRep = new[] { new VoiceLineSpec("FO4SF_PrewarVaultTecRepNPC", "Good morning! Vault-Tec calling!", 0u, 2.2f, "FO4SF_PrewarRepVoice") };
        var fallbackBcast = new[] { new VoiceLineSpec("FO4SF_PrewarBroadcastNPC", "Confirmed reports of nuclear detonations.", 0u, 2.5f, "FO4SF_PrewarBroadcastVoice") };
        var fallbackSoldier = new[] { new VoiceLineSpec("FO4SF_PrewarSoldierCheckerNPC", "Keep moving to the vault!", 0u, 2.0f, "FO4SF_PrewarSoldierVoice") };
        var fallbackDoc = new[] { new VoiceLineSpec("FO4SF_PrewarVaultDoctorNPC", "Step into the decontamination pod.", 0u, 2.2f, "FO4SF_PrewarDoctorVoice") };

        if (string.IsNullOrWhiteSpace(voicesPath))
            return new VoicesSpec(fallbackKellogg, fallbackCods, fallbackRep, fallbackBcast, fallbackSoldier, fallbackDoc);
        if (!File.Exists(voicesPath)) throw new Refusal($"--voices {voicesPath} does not exist");
        using var doc = JsonDocument.Parse(File.ReadAllText(voicesPath));
        var root = doc.RootElement;
        return new VoicesSpec(
            ParseSceneArray(root, "kellogg_scene", fallbackKellogg),
            ParseSceneArray(root, "codsworth_scene", fallbackCods),
            ParseSceneArray(root, "vault_tec_rep_scene", fallbackRep),
            ParseSceneArray(root, "broadcast_scene", fallbackBcast),
            ParseSceneArray(root, "soldier_gate_scene", fallbackSoldier),
            ParseSceneArray(root, "vault_doctor_scene", fallbackDoc));
    }

    static Dictionary<string, MarkerPlacement> DefaultMarkers() => new()
    {
        // Local metres in S1 bounded Sanctuary strip (CW origin (-1200, +1300) -> local range [-200, +200) m)
        ["FO4SF_PrewarHouseSpawnMarker"] = new(52.82f, -2.46f, 112.23f, 0f, false),
        ["FO4SF_PrewarCodsworthRef"] = new(56.42f, -0.70f, 113.38f, 1.57f, false),
        // S1-13: Offset spouse spawns >= 2.3 m from HouseSpawnMarker so player never clips inside spouse on spawn
        ["FO4SF_PrewarSpouseRef"] = new(55.00f, -1.60f, 112.23f, 2.8f, false),
        ["FO4SF_PrewarSpouseMaleRef"] = new(55.00f, -1.60f, 112.23f, 2.8f, false),
        ["FO4SF_PrewarBroadcastRef"] = new(54.20f, -4.10f, 112.23f, 0.2f, false),
        ["FO4SF_PrewarVaultTecRepRef"] = new(57.32f, -1.73f, 112.14f, 3.14f, false),
        ["FO4SF_PrewarSoldierCheckerRef"] = new(-53.54f, 41.08f, 119.66f, 1.2f, false),
        ["FO4SF_PrewarCrowdRunner01Ref"] = new(15.0f, -1.0f, 110.0f, 1.57f, false),
        ["FO4SF_PrewarCrowdRunner02Ref"] = new(-5.0f, -2.0f, 106.0f, 1.57f, false),
        ["FO4SF_PrewarCrowdRunner03Ref"] = new(-25.0f, 10.0f, 113.0f, 1.57f, false),
        ["FO4SF_PrewarCrowdRunner04Ref"] = new(-42.0f, 25.0f, 118.0f, 1.57f, false),
        ["FO4SF_PrewarCrowdGoalMarkRef"] = new(-68.31f, -6.27f, 127.50f, 0f, false),
        // S1-13: Vertibirds spawn & loop exclusively along s1_spec orbit/hover sky altitudes (131m..148m)
        ["FO4SF_PrewarVertibird01Ref"] = new(64.00f, -83.29f, 140.83f, 0.5f, false),
        ["FO4SF_PrewarVertibird02Ref"] = new(-74.68f, 29.42f, 148.11f, -0.7f, false),
        ["FO4SF_PrewarVertibird01HoverMarkRef"] = new(82.03f, -63.61f, 131.66f, 0.9f, false),
        ["FO4SF_PrewarVertibird02HoverMarkRef"] = new(-59.06f, -17.25f, 142.00f, -0.3f, false),
        ["FO4SF_PrewarExtLiftPlatformRef"] = new(-68.31f, -6.27f, 127.50f, 0f, false),
        ["FO4SF_PrewarNukeAnchorRef"] = new(-59.06f, -17.25f, 130.05f, 0f, false),
        // Local metres in FO4Port_PrewarVault111 (PREWAR_V111_KEY_COORDS_M; S1-12: lower elevator landing z = -0.11)
        ["FO4SF_PrewarVaultArrivalMarker"] = new(-70.40f, -2.74f, -0.11f, 0f, true),
        ["FO4SF_PrewarVaultDoctorRef"] = new(-52.50f, -2.80f, -0.10f, 3.14f, true),
        ["FO4SF_PrewarKelloggRef"] = new(9.14f, -8.30f, -1.03f, 1.57f, true),
        ["FO4SF_PrewarInstAgentMRef"] = new(7.80f, -8.60f, -1.03f, 3.14f, true),
        ["FO4SF_PrewarInstAgentFRef"] = new(10.50f, -8.60f, -1.03f, 3.14f, true),
        ["FO4SF_PrewarKelloggMarkRef"] = new(9.14f, -8.30f, -1.03f, 3.14f, true),
        ["FO4SF_PrewarInstMalePodMarkRef"] = new(7.80f, -8.60f, -1.03f, 3.14f, true),
        ["FO4SF_PrewarInstFemalePodMarkRef"] = new(10.50f, -8.60f, -1.03f, 3.14f, true),
        ["FO4SF_PrewarSpousePodMarkRef"] = new(9.14f, -10.51f, -1.03f, 0f, true),
        ["FO4SF_PrewarPlayerPodMarkRef"] = new(9.14f, -4.11f, -1.03f, 3.14f, true),
        ["FO4SF_PrewarCrowdBridgeMarkRef"] = new(-4.84f, -1.49f, 105.34f, 1.57f, false),
    };

    static SF.IRaceGetter RequireRace(ILinkCache cache, uint id, string expectedEdid)
    {
        if (!cache.TryResolve<SF.IRaceGetter>(new FormKey(SfEsm, id), out var race) || race.EditorID != expectedEdid)
            throw new Refusal($"Starfield.esm 0x{id:X6} is not RACE {expectedEdid}");
        return race;
    }

    static (SF.Race Race, SF.Armor? HandySkin) BuildCodsworthRaceZeroMaster(
        SF.StarfieldMod mod,
        SF.IStarfieldModGetter sf,
        ILinkCache sfCache,
        string? handyEsmPath,
        SF.IRaceGetter baseBotRace)
    {
        if (string.IsNullOrWhiteSpace(handyEsmPath))
        {
            var fallbackRace = (SF.Race)baseBotRace.Duplicate(new FormKey(mod.ModKey, CodsworthRaceId));
            fallbackRace.EditorID = "FO4SF_PrewarCodsworthRace";
            fallbackRace.Flags |= SF.Race.Flag.AllowPcDialog;
            fallbackRace.ArmorRace.SetTo(baseBotRace.FormKey);
            mod.Races.Add(fallbackRace);
            return (fallbackRace, null);
        }
        if (!File.Exists(handyEsmPath)) throw new Refusal($"--handy-esm {handyEsmPath} does not exist");
        using var tpl = SF.StarfieldMod.CreateFromBinaryOverlay(handyEsmPath, Rel, Styles(SfEsm));
        var name = Path.GetFileName(handyEsmPath);
        var hr = tpl.Races.FirstOrDefault(r => r.EditorID == HandyRaceEdid)
                 ?? throw new Refusal($"{name} has no RACE {HandyRaceEdid}");
        var hb = tpl.BodyParts.FirstOrDefault(b => b.EditorID == HandyBptdEdid)
                 ?? throw new Refusal($"{name} has no BPTD {HandyBptdEdid}");
        if (hr.BodyPartData.FormKey != hb.FormKey)
            throw new Refusal($"{name}: {HandyRaceEdid} does not bind {HandyBptdEdid}");

        var bptd = (SF.BodyPartData)hb.Duplicate(new FormKey(mod.ModKey, CodsworthBptdId));
        bptd.EditorID = "FO4SF_PrewarCodsworthBPTD";
        mod.BodyParts.Add(bptd);

        var race = (SF.Race)hr.Duplicate(new FormKey(mod.ModKey, CodsworthRaceId));
        race.EditorID = "FO4SF_PrewarCodsworthRace";
        race.Flags |= SF.Race.Flag.AllowPcDialog;
        race.BodyPartData.SetTo(bptd.FormKey);
        race.ArmorRace.Clear();

        // Clone local ARMO/ARMA (FO4SF_RA2Handy_Skin -> handy.nif) so Codsworth does NOT fall back to MiniBot skin!
        var copiedRecords = new List<IMajorRecord> { race, bptd };
        SF.Armor? copiedSkin = null;
        var tplSkin = !hr.Skin.IsNull && hr.Skin.FormKey.ModKey == tpl.ModKey
            ? tpl.Armors.FirstOrDefault(a => a.FormKey == hr.Skin.FormKey)
            : tpl.Armors.FirstOrDefault(a => a.EditorID == "FO4SF_RA2Handy_Skin");
        if (tplSkin is null)
            throw new Refusal($"{name}: missing local Handy skin ARMO on {HandyRaceEdid}");

        copiedSkin = (SF.Armor)tplSkin.Duplicate(new FormKey(mod.ModKey, CodsworthSkinId));
        copiedSkin.EditorID = "FO4SF_PrewarCodsworthSkin";
        copiedSkin.Race.SetTo(race.FormKey);
        var newArmatures = new List<SF.ArmorAddonModel>();
        uint nextAa = CodsworthAaStartId;
        foreach (var arm in copiedSkin.Armatures)
        {
            if (arm.ArmorAddon.IsNull || arm.ArmorAddon.FormKey.ModKey != tpl.ModKey)
            {
                newArmatures.Add(arm);
                continue;
            }
            var tplAa = tpl.ArmorAddons.FirstOrDefault(a => a.FormKey == arm.ArmorAddon.FormKey)
                        ?? throw new Refusal($"{name}: missing ARMA {arm.ArmorAddon.FormKey}");
            if (nextAa >= VoiceStartId)
                throw new Refusal("Codsworth ARMA FormIDs collided with VoiceStartId");
            var aa = (SF.ArmorAddon)tplAa.Duplicate(new FormKey(mod.ModKey, nextAa));
            aa.EditorID = nextAa == CodsworthAaStartId ? "FO4SF_PrewarCodsworthAA" : $"FO4SF_PrewarCodsworthAA_{nextAa - CodsworthAaStartId}";
            nextAa++;
            aa.Race.SetTo(race.FormKey);
            aa.AdditionalRaces.RemoveAll(r => r.FormKey.ModKey == tpl.ModKey);
            mod.ArmorAddons.Add(aa);
            copiedRecords.Add(aa);
            newArmatures.Add(new SF.ArmorAddonModel
            {
                AddonIndex = arm.AddonIndex,
                ArmorAddon = new FormLinkNullable<SF.IArmorAddonGetter>(aa.FormKey),
            });
        }
        copiedSkin.Armatures.Clear();
        copiedSkin.Armatures.AddRange(newArmatures);
        mod.Armors.Add(copiedSkin);
        copiedRecords.Add(copiedSkin);
        race.Skin.SetTo(copiedSkin.FormKey);

        var leaks = copiedRecords.SelectMany(r => r.EnumerateFormLinks())
                                 .Where(l => l.FormKey.ModKey == tpl.ModKey)
                                 .Select(l => l.FormKey.ToString())
                                 .Distinct().ToList();
        if (leaks.Count > 0)
            throw new Refusal($"{name}: master link leaks into {tpl.ModKey} after copy: {string.Join(", ", leaks)}");
        _ = sf;
        _ = sfCache;
        mod.Races.Add(race);
        return (race, copiedSkin);
    }

    static SF.Npc CloneHumanNpc(
        ModKey modKey, uint id, string edid, string displayName,
        SF.INpcGetter? templateNpc, SF.IRaceGetter humanRace, FormKey voiceKey, FormKey factionKey,
        FormKey outfitKey, bool female = false, bool essential = true)
    {
        var npc = templateNpc is not null
            ? (SF.Npc)templateNpc.Duplicate(new FormKey(modKey, id))
            : new SF.Npc(new FormKey(modKey, id), Rel)
            {
                FormVersion = 581,
                ObjectBounds = new SF.ObjectBounds { First = new P3Float(-0.4f, -0.4f, 0f), Second = new P3Float(0.4f, 0.4f, 1.8f) },
            };
        npc.EditorID = edid;
        npc.Name = displayName;
        npc.Race.SetTo(humanRace.FormKey);
        npc.Voice.SetTo(voiceKey);
        npc.ActivateTextOverride = "Talk";
        npc.VirtualMachineAdapter = null;
        npc.Packages.Clear();
        npc.DefaultTemplate.Clear();
        npc.TemplateActors = null;
        npc.CrimeFaction.Clear();
        npc.Flags = ((npc.Flags | SF.Npc.Flag.Unique | SF.Npc.Flag.AutoCalcStats)
                     & ~(SF.Npc.Flag.Respawn | SF.Npc.Flag.Protected));
        npc.Flags = essential ? (npc.Flags | SF.Npc.Flag.Essential) : (npc.Flags & ~SF.Npc.Flag.Essential);
        npc.Flags = female ? (npc.Flags | SF.Npc.Flag.Female) : (npc.Flags & ~SF.Npc.Flag.Female);
        npc.Factions.Clear();
        npc.Factions.Add(new SF.RankPlacement { Faction = new FormLink<SF.IFactionGetter>(factionKey), Rank = 0 });
        if (!outfitKey.IsNull)
        {
            npc.DefaultOutfit.SetTo(outfitKey);
            npc.SpaceOutfit.SetTo(outfitKey);
        }
        return npc;
    }

    static (uint SystemId, uint PlanetId)? ReadWrldOverlayRaw(string pluginPath, string worldEdid)
    {
        if (!File.Exists(pluginPath)) return null;
        byte[] buf = File.ReadAllBytes(pluginPath);
        if (buf.Length < 24 || System.Text.Encoding.ASCII.GetString(buf, 0, 4) != "TES4") return null;
        uint hdrSize = BitConverter.ToUInt32(buf, 4);
        int pos = 24 + (int)hdrSize;
        while (pos + 24 <= buf.Length)
        {
            string sig = System.Text.Encoding.ASCII.GetString(buf, pos, 4);
            uint sz = BitConverter.ToUInt32(buf, pos + 4);
            if (sig == "GRUP")
            {
                string lbl = System.Text.Encoding.ASCII.GetString(buf, pos + 8, 4);
                int gtype = BitConverter.ToInt32(buf, pos + 12);
                int end = Math.Min(buf.Length, pos + (int)sz);
                if (gtype == 0 && lbl == "WRLD")
                {
                    int wp = pos + 24;
                    while (wp + 24 <= end)
                    {
                        string wsig = System.Text.Encoding.ASCII.GetString(buf, wp, 4);
                        uint wsz = BitConverter.ToUInt32(buf, wp + 4);
                        if (wsig == "GRUP")
                        {
                            wp += Math.Max(24, (int)wsz);
                            continue;
                        }
                        if (wsig == "WRLD" && wp + 24 + wsz <= end)
                        {
                            uint flags = BitConverter.ToUInt32(buf, wp + 8);
                            byte[] recData;
                            if ((flags & 0x00040000u) != 0 && wsz >= 4)
                            {
                                uint rawSz = BitConverter.ToUInt32(buf, wp + 24);
                                using var ms = new MemoryStream(buf, wp + 28, (int)wsz - 4);
                                using var zs = new ZLibStream(ms, CompressionMode.Decompress);
                                recData = new byte[rawSz];
                                zs.ReadExactly(recData, 0, recData.Length);
                            }
                            else
                            {
                                recData = new byte[wsz];
                                Buffer.BlockCopy(buf, wp + 24, recData, 0, (int)wsz);
                            }
                            string? ed = null;
                            bool inOv = false;
                            uint? snam = null, pnam = null;
                            int sp = 0;
                            while (sp + 6 <= recData.Length)
                            {
                                string sg = System.Text.Encoding.ASCII.GetString(recData, sp, 4);
                                ushort sl = BitConverter.ToUInt16(recData, sp + 4);
                                sp += 6;
                                if (sp + sl > recData.Length) break;
                                if (sg == "EDID")
                                    ed = System.Text.Encoding.UTF8.GetString(recData, sp, sl).TrimEnd('\0');
                                else if (sg == "BFCB")
                                    inOv = System.Text.Encoding.UTF8.GetString(recData, sp, sl).TrimEnd('\0') == "BGSWorldSpaceOverlay_Component";
                                else if (sg == "BFCE")
                                    inOv = false;
                                else if (inOv && sg == "SNAM" && sl >= 4)
                                    snam = BitConverter.ToUInt32(recData, sp);
                                else if (inOv && sg == "PNAM" && sl >= 4)
                                    pnam = BitConverter.ToUInt32(recData, sp);
                                sp += sl;
                            }
                            if (ed == worldEdid && snam.HasValue && pnam.HasValue)
                                return (snam.Value, pnam.Value);
                        }
                        wp += 24 + (int)wsz;
                    }
                    break;
                }
                pos += Math.Max(24, (int)sz);
            }
            else
            {
                pos += 24 + (int)sz;
            }
        }
        return null;
    }

    static SF.ScriptObjectProperty ObjProp(string name, FormKey fk) => new()
    {
        Name = name,
        Flags = SF.ScriptProperty.Flag.Edited,
        Object = new FormLink<SF.IStarfieldMajorRecordGetter>(fk),
        Alias = -1,
        Unused = 0,
    };

    static SF.ScriptObjectListProperty ObjListProp(string name, IEnumerable<FormKey> keys)
    {
        var prop = new SF.ScriptObjectListProperty { Name = name, Flags = SF.ScriptProperty.Flag.Edited };
        foreach (var k in keys) prop.Objects.Add(ObjProp("", k));
        return prop;
    }

    static SF.PlacedNpc PlaceNpc(ModKey modKey, uint id, string edid, FormKey npcKey, MarkerPlacement pos) => new(new FormKey(modKey, id), Rel)
    {
        EditorID = edid,
        Base = new FormLinkNullable<SF.INpcGetter>(npcKey),
        Position = new P3Float(pos.X, pos.Y, pos.Z),
        Rotation = new P3Float(0f, 0f, pos.RotZ),
        MajorRecordFlagsRaw = 0x400, // Persistent
    };

    static SF.PlacedObject PlaceObj(ModKey modKey, uint id, string edid, FormKey baseKey, MarkerPlacement pos) => new(new FormKey(modKey, id), Rel)
    {
        EditorID = edid,
        Base = new FormLinkNullable<SF.IPlaceableObjectGetter>(baseKey),
        Position = new P3Float(pos.X, pos.Y, pos.Z),
        Rotation = new P3Float(0f, 0f, pos.RotZ),
        MajorRecordFlagsRaw = 0x400, // Persistent
    };

    public static int Write(string sfPath, string outDir, string? handyEsm, string? specPath, string? voicesPath)
    {
        if (!File.Exists(sfPath)) throw new Refusal($"Starfield.esm not found at {sfPath}");
        var spec = LoadSpec(specPath);
        var voices = LoadVoices(voicesPath);

        using var sf = SF.StarfieldMod.CreateFromBinaryOverlay(sfPath, Rel);
        var sfCache = sf.ToImmutableLinkCache<SF.IStarfieldMod, SF.IStarfieldModGetter>();
        var humanRace = RequireRace(sfCache, SfHumanRaceId, SfHumanRaceEdid);
        var botNpc = sf.Npcs.FirstOrDefault(n => n.EditorID == SfMiniBotEdid)
                     ?? throw new Refusal($"Starfield.esm missing NPC_ {SfMiniBotEdid}");
        if (!sfCache.TryResolve<SF.IRaceGetter>(botNpc.Race.FormKey, out var botRace))
            throw new Refusal($"{SfMiniBotEdid} race {botNpc.Race.FormKey} does not resolve");
        if (!sfCache.TryResolve<SF.IStaticGetter>(new FormKey(SfEsm, SfXMarkerId), out var xMarker))
            throw new Refusal($"Starfield.esm 0x{SfXMarkerId:X6} XMarker missing");

        var maleVoiceKey = sf.VoiceTypes.FirstOrDefault(v => v.FormKey.ID == SfMaleEvenTonedVoiceId)?.FormKey ?? FormKey.Null;
        var femaleVoiceKey = sf.VoiceTypes.FirstOrDefault(v => v.FormKey.ID == SfFemaleEvenTonedVoiceId)?.FormKey ?? FormKey.Null;
        var playerFaction = sf.Factions.FirstOrDefault(f => f.FormKey.ID == SfPlayerFactionId);
        var maleTpl = sf.Npcs.FirstOrDefault(n => n.FormKey.ID == SfMaleCitizenTplId)
                      ?? sf.Npcs.FirstOrDefault(n => n.Race.FormKey == humanRace.FormKey && !n.Flags.HasFlag(SF.Npc.Flag.Female) && !string.IsNullOrEmpty(n.EditorID) && n.DefaultTemplate.IsNull);
        var femaleTpl = sf.Npcs.FirstOrDefault(n => n.FormKey.ID == SfFemaleCitizenTplId)
                        ?? sf.Npcs.FirstOrDefault(n => n.Race.FormKey == humanRace.FormKey && n.Flags.HasFlag(SF.Npc.Flag.Female) && !string.IsNullOrEmpty(n.EditorID) && n.DefaultTemplate.IsNull);
        FormKey PickOtft(uint id) => sf.Outfits.FirstOrDefault(o => o.FormKey.ID == id)?.FormKey ?? FormKey.Null;
        var otftSpouse = PickOtft(SfOutfitCitizenFormalId);
        var otftCrowd = PickOtft(SfOutfitNhCitizenId);
        var otftRep = PickOtft(SfOutfitBusinessId);
        var otftSoldier = PickOtft(SfOutfitArmyFatiguesId);
        var otftDoctor = PickOtft(SfOutfitDoctorId);
        var otftKellogg = PickOtft(SfOutfitKelloggId);
        var otftScientist = PickOtft(SfOutfitScientistId);

        var modKey = ModKey.FromFileName(Plugin);
        var mod = new SF.StarfieldMod(modKey, Rel);
        mod.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Master;
        mod.ModHeader.Author = "fo4-to-starfield Task 6 Prewar";

        // Globals & Factions
        mod.Globals.Add(new SF.Global(new FormKey(modKey, UseMessageBoxGlobId), Rel)
        {
            EditorID = "FO4SF_PrewarUseMessageBoxGlob",
            Data = 0f,
        });
        var activeGlob = new SF.Global(new FormKey(modKey, StageActiveGlobId), Rel)
        {
            EditorID = "FO4SF_PrewarStageActiveGlob",
            Data = 0f,
        };
        mod.Globals.Add(activeGlob);

        var prewarFaction = new SF.Faction(new FormKey(modKey, PrewarFactionId), Rel) { EditorID = "FO4SF_PrewarFaction" };
        var crowdFaction = new SF.Faction(new FormKey(modKey, CrowdFactionId), Rel) { EditorID = "FO4SF_PrewarCrowdFaction" };
        if (playerFaction is not null)
        {
            prewarFaction.Relations.Add(new SF.Relation { Target = new FormLink<SF.IRelatableGetter>(playerFaction.FormKey), Reaction = SF.CombatReaction.Ally });
            crowdFaction.Relations.Add(new SF.Relation { Target = new FormLink<SF.IRelatableGetter>(playerFaction.FormKey), Reaction = SF.CombatReaction.Ally });
        }
        mod.Factions.Add(prewarFaction);
        mod.Factions.Add(crowdFaction);

        // Codsworth + 6 dedicated S1 VoiceTypes + Vault 111 Suit stand-in ARMO
        var (codsRace, codsHandySkin) = BuildCodsworthRaceZeroMaster(mod, sf, sfCache, handyEsm, botRace);
        var voiceByEdid = new Dictionary<string, FormKey>(StringComparer.OrdinalIgnoreCase);
        SF.VoiceType AddVoice(uint id, string edid)
        {
            var vt = new SF.VoiceType(new FormKey(modKey, id), Rel)
            {
                EditorID = edid,
                Flags = SF.VoiceType.Flag.AllowDefaultDialog,
            };
            mod.VoiceTypes.Add(vt);
            voiceByEdid[edid] = vt.FormKey;
            return vt;
        }
        var codsVoice = AddVoice(CodsworthVoiceId, "FO4SF_PrewarCodsworthVoice");
        var repVoice = AddVoice(RepVoiceId, "FO4SF_PrewarRepVoice");
        var bcastVoice = AddVoice(BroadcastVoiceId, "FO4SF_PrewarBroadcastVoice");
        var soldierVoice = AddVoice(SoldierVoiceId, "FO4SF_PrewarSoldierVoice");
        var doctorVoice = AddVoice(DoctorVoiceId, "FO4SF_PrewarDoctorVoice");
        var prewarMaleVoice = AddVoice(MaleVoiceId, "FO4SF_PrewarMaleVoice");
        var prewarFemaleVoice = AddVoice(FemaleVoiceId, "FO4SF_PrewarFemaleVoice");

        var vaultSuitKey = new FormKey(modKey, VaultSuitStandInId);
        var vaultSuitTpl = sf.Armors.FirstOrDefault(a => a.FormKey.ID == SfVaultSuitStandInArmorId);
        var vaultSuit = vaultSuitTpl is not null
            ? (SF.Armor)vaultSuitTpl.Duplicate(vaultSuitKey)
            : new SF.Armor(vaultSuitKey, Rel) { FormVersion = 581 };
        vaultSuit.EditorID = "FO4SF_PrewarVaultSuitStandIn";
        vaultSuit.Name = "Vault 111 Suit";
        mod.Armors.Add(vaultSuit);

        var codsOutfit = new SF.Outfit(new FormKey(modKey, CodsworthOutfitId), Rel) { EditorID = "FO4SF_PrewarCodsworthOutfit" };
        FormKey codsSkinKey = codsHandySkin?.FormKey ?? sf.Armors.FirstOrDefault(a => a.FormKey.ID == SfMiniBotSkinId)?.FormKey ?? FormKey.Null;
        if (!codsSkinKey.IsNull && codsOutfit.Items is { } outfitItems)
            outfitItems.Add(new FormLink<SF.IOutfitTargetGetter>(codsSkinKey));
        mod.Outfits.Add(codsOutfit);

        var codsNpc = (SF.Npc)botNpc.Duplicate(new FormKey(modKey, CodsworthNpcId));
        codsNpc.EditorID = "FO4SF_PrewarCodsworthNPC";
        codsNpc.Name = "Codsworth";
        codsNpc.Race.SetTo(codsRace.FormKey);
        codsNpc.Voice.SetTo(codsVoice.FormKey);
        if (!codsSkinKey.IsNull)
            codsNpc.Skin.SetTo(codsSkinKey);
        else
            codsNpc.Skin.Clear();
        codsNpc.DefaultOutfit.SetTo(codsOutfit.FormKey);
        codsNpc.Flags = (codsNpc.Flags | SF.Npc.Flag.Essential | SF.Npc.Flag.Unique) & ~SF.Npc.Flag.Respawn;
        codsNpc.Factions.Clear();
        codsNpc.Factions.Add(new SF.RankPlacement { Faction = new FormLink<SF.IFactionGetter>(prewarFaction.FormKey), Rank = 0 });
        codsNpc.Packages.Clear();
        codsNpc.DefaultTemplate.Clear();
        codsNpc.TemplateActors = null;
        codsNpc.VirtualMachineAdapter = null;
        codsNpc.ActivateTextOverride = "Talk";
        mod.Npcs.Add(codsNpc);

        // Human NPCs (S1-05: explicit Female ACBS flags + vanilla templates + default outfits; dedicated S1 VoiceTypes)
        var spouseMaleNpc = CloneHumanNpc(modKey, SpouseMaleNpcId, "FO4SF_PrewarSpouseMaleNPC", "Nate", maleTpl, humanRace, prewarMaleVoice.FormKey, prewarFaction.FormKey, otftSpouse, female: false);
        var spouseFemaleNpc = CloneHumanNpc(modKey, SpouseFemaleNpcId, "FO4SF_PrewarSpouseFemaleNPC", "Nora", femaleTpl, humanRace, prewarFemaleVoice.FormKey, prewarFaction.FormKey, otftSpouse, female: true);
        var repNpc = CloneHumanNpc(modKey, VaultTecRepNpcId, "FO4SF_PrewarVaultTecRepNPC", "Vault-Tec Rep", maleTpl, humanRace, repVoice.FormKey, prewarFaction.FormKey, otftRep, female: false);
        var soldierNpc = CloneHumanNpc(modKey, SoldierCheckerNpcId, "FO4SF_PrewarSoldierCheckerNPC", "Army Soldier", maleTpl, humanRace, soldierVoice.FormKey, prewarFaction.FormKey, otftSoldier, female: false);
        var doctorNpc = CloneHumanNpc(modKey, VaultDoctorNpcId, "FO4SF_PrewarVaultDoctorNPC", "Vault-Tec Doctor", femaleTpl, humanRace, doctorVoice.FormKey, prewarFaction.FormKey, otftDoctor, female: true);
        var kelloggNpc = CloneHumanNpc(modKey, KelloggNpcId, "FO4SF_PrewarKelloggNPC", "Mercenary", maleTpl, humanRace, prewarMaleVoice.FormKey, prewarFaction.FormKey, otftKellogg, female: false);
        var instMNpc = CloneHumanNpc(modKey, InstAgentMNpcId, "FO4SF_PrewarInstAgentMNPC", "Vault-Tec Scientist", maleTpl, humanRace, prewarMaleVoice.FormKey, prewarFaction.FormKey, otftScientist, female: false);
        var instFNpc = CloneHumanNpc(modKey, InstAgentFNpcId, "FO4SF_PrewarInstAgentFNPC", "Vault-Tec Scientist", femaleTpl, humanRace, prewarFemaleVoice.FormKey, prewarFaction.FormKey, otftScientist, female: true);
        var broadcastNpc = CloneHumanNpc(modKey, BroadcastNpcId, "FO4SF_PrewarBroadcastNPC", "Emergency Broadcast", maleTpl, humanRace, bcastVoice.FormKey, prewarFaction.FormKey, otftSpouse, female: false);
        var crowdNpc = CloneHumanNpc(modKey, CrowdRunnerNpcId, "FO4SF_PrewarCrowdRunnerNPC", "Neighbor", maleTpl, humanRace, prewarMaleVoice.FormKey, crowdFaction.FormKey, otftCrowd, female: false, essential: false);
        foreach (var n in new[] { spouseMaleNpc, spouseFemaleNpc, repNpc, soldierNpc, doctorNpc, kelloggNpc, instMNpc, instFNpc, broadcastNpc, crowdNpc })
            mod.Npcs.Add(n);

        var xMarkerModel = xMarker.Model?.File?.GivenPath ?? @"Markers\MarkerX.nif";
        // Beat (b)/(c) standalone prop bases
        var vertiBase = new SF.Static(new FormKey(modKey, VertibirdBaseId), Rel)
        {
            EditorID = "FO4SF_PrewarVertibirdBase",
            Model = new SF.Model { File = spec.VertibirdModel ?? xMarkerModel },
        };
        var liftBase = new SF.Activator(new FormKey(modKey, ExtLiftBaseId), Rel)
        {
            EditorID = "FO4SF_PrewarExtLiftBase",
            Name = "Vault 111 Elevator",
            Model = new SF.Model { File = spec.ExtLiftModel ?? xMarkerModel },
        };
        mod.Statics.Add(vertiBase);
        mod.Activators.Add(liftBase);

        // Placement containers: Holding Cell always built (0x826), plus optional Sanctuary WRLD / Port CELL overrides
        var holdingCell = new SF.Cell(new FormKey(modKey, HoldingCellId), Rel)
        {
            EditorID = "FO4SF_PrewarHoldingCell",
            Name = "Pre-War Staging Cell",
            Flags = SF.Cell.Flag.IsInteriorCell,
        };
        var cSub = new SF.CellSubBlock { BlockNumber = (int)((HoldingCellId / 10) % 10), GroupType = SF.GroupTypeEnum.InteriorCellSubBlock };
        cSub.Cells.Add(holdingCell);
        var cBlk = new SF.CellBlock { BlockNumber = (int)(HoldingCellId % 10), GroupType = SF.GroupTypeEnum.InteriorCellBlock };
        cBlk.SubBlocks.Add(cSub);
        mod.Cells.Records.Add(cBlk);

        var homeEsm = ModKey.FromFileName("FO4SFHome.esm");
        var extraMasters = new List<ModKey>();
        SF.Cell? exteriorTopOverride = null;
        if (!string.IsNullOrWhiteSpace(spec.SanctuaryEsmPath))
        {
            if (!File.Exists(spec.SanctuaryEsmPath)) throw new Refusal($"sanctuary_world.esm {spec.SanctuaryEsmPath} missing");
            using var sMod = SF.StarfieldMod.CreateFromBinaryOverlay(spec.SanctuaryEsmPath, Rel, Styles(SfEsm, homeEsm));
            var sWorld = sMod.Worldspaces.FirstOrDefault(w => w.EditorID == spec.SanctuaryWorldEdid)
                         ?? throw new Refusal($"{spec.SanctuaryEsmPath} has no WRLD {spec.SanctuaryWorldEdid}");
            var wOvr = (SF.Worldspace)sWorld.DeepCopy();
            wOvr.SubCells.Clear();
            // S1-06 + S1-11: Preserve master BGSWorldSpaceOverlay_Component SNAM/PNAM/SurfaceBlock + Climate/Water/Biome
            var srcOv = sWorld.Components.OfType<SF.IWorldSpaceOverlayComponentGetter>().FirstOrDefault();
            var rawOv = ReadWrldOverlayRaw(spec.SanctuaryEsmPath, spec.SanctuaryWorldEdid);
            uint? ovSys = rawOv?.SystemId ?? (srcOv?.SNAM is { } sn && sn.Length >= 4 ? BitConverter.ToUInt32(sn.Span) : null);
            uint? ovPln = rawOv?.PlanetId ?? (srcOv?.PNAM is { } pn && pn.Length >= 4 ? BitConverter.ToUInt32(pn.Span) : null);
            var dstOv = wOvr.Components.OfType<SF.WorldSpaceOverlayComponent>().FirstOrDefault();
            if (dstOv is null && (ovSys.HasValue || ovPln.HasValue || srcOv is not null))
            {
                dstOv = new SF.WorldSpaceOverlayComponent();
                wOvr.Components.Add(dstOv);
            }
            if (dstOv is not null)
            {
                if (ovSys.HasValue) dstOv.SNAM = BitConverter.GetBytes(ovSys.Value);
                if (ovPln.HasValue) dstOv.PNAM = BitConverter.GetBytes(ovPln.Value);
                if (srcOv is not null && !srcOv.SurfaceBlock.IsNull)
                    dstOv.SurfaceBlock.SetTo(srcOv.SurfaceBlock.FormKey);
            }
            if (!sWorld.Climate.IsNull) wOvr.Climate.SetTo(sWorld.Climate.FormKey);
            if (!sWorld.Water.IsNull) wOvr.Water.SetTo(sWorld.Water.FormKey);
            if (!sWorld.Biome.IsNull) wOvr.Biome.SetTo(sWorld.Biome.FormKey);
            var tOvr = (SF.Cell)sWorld.TopCell!.DeepCopy();
            tOvr.Persistent.Clear();
            tOvr.Temporary.Clear();
            tOvr.NavigationMeshes.Clear();
            wOvr.TopCell = tOvr;
            mod.Worldspaces.Add(wOvr);
            exteriorTopOverride = tOvr;
            foreach (var mr in sMod.ModHeader.MasterReferences)
                if (mr.Master != SfEsm && !extraMasters.Contains(mr.Master))
                    extraMasters.Add(mr.Master);
            extraMasters.Add(sMod.ModKey);
        }

        SF.Cell? portCellOverride = null;
        uint resolvedPortCellId = spec.PrewarVaultCellId;
        if (!string.IsNullOrWhiteSpace(spec.PortEsmPath))
        {
            if (!File.Exists(spec.PortEsmPath)) throw new Refusal($"port_vault.esm {spec.PortEsmPath} missing");
            using var pMod = SF.StarfieldMod.CreateFromBinaryOverlay(spec.PortEsmPath, Rel, Styles(SfEsm));
            var pCell = pMod.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells)
                            .FirstOrDefault(c => c.EditorID == spec.PortVaultCellEdid)
                        ?? throw new Refusal($"{spec.PortEsmPath} has no CELL {spec.PortVaultCellEdid}");
            resolvedPortCellId = pCell.FormKey.ID;
            var pOvr = (SF.Cell)pCell.DeepCopy();
            pOvr.Persistent.Clear();
            pOvr.Temporary.Clear();
            pOvr.NavigationMeshes.Clear();
            var pb = new SF.CellBlock { BlockNumber = (int)(pOvr.FormKey.ID % 10), GroupType = SF.GroupTypeEnum.InteriorCellBlock };
            var ps = new SF.CellSubBlock { BlockNumber = (int)((pOvr.FormKey.ID / 10) % 10), GroupType = SF.GroupTypeEnum.InteriorCellSubBlock };
            ps.Cells.Add(pOvr);
            pb.SubBlocks.Add(ps);
            mod.Cells.Records.Add(pb);
            portCellOverride = pOvr;
            extraMasters.Add(pMod.ModKey);
        }

        void AddToCell(string edid, SF.IPlaced p)
        {
            bool isInt = spec.Markers[edid].Interior;
            var dest = isInt ? (portCellOverride ?? holdingCell) : (exteriorTopOverride ?? holdingCell);
            dest.Persistent.Add(p);
        }

        MarkerPlacement Pos(string edid) => spec.Markers[edid];

        // Place all NPC refs & marker refs using fixed FormIDs (S1-05: both spouse refs initially disabled; runtime selects by GetSex)
        _ = maleVoiceKey;
        _ = femaleVoiceKey;
        var codsRef = PlaceNpc(modKey, CodsworthRefId, "FO4SF_PrewarCodsworthRef", codsNpc.FormKey, Pos("FO4SF_PrewarCodsworthRef"));
        var spouseRef = PlaceNpc(modKey, SpouseRefId, "FO4SF_PrewarSpouseRef", spouseFemaleNpc.FormKey, Pos("FO4SF_PrewarSpouseRef"));
        spouseRef.MajorRecordFlagsRaw |= 0x800; // InitiallyDisabled -> enabled when player is male
        var spouseMaleRef = PlaceNpc(modKey, SpouseMaleRefId, "FO4SF_PrewarSpouseMaleRef", spouseMaleNpc.FormKey, Pos("FO4SF_PrewarSpouseMaleRef"));
        spouseMaleRef.MajorRecordFlagsRaw |= 0x800; // InitiallyDisabled -> enabled when player is female
        var repRef = PlaceNpc(modKey, VaultTecRepRefId, "FO4SF_PrewarVaultTecRepRef", repNpc.FormKey, Pos("FO4SF_PrewarVaultTecRepRef"));
        var soldierRef = PlaceNpc(modKey, SoldierCheckerRefId, "FO4SF_PrewarSoldierCheckerRef", soldierNpc.FormKey, Pos("FO4SF_PrewarSoldierCheckerRef"));
        var doctorRef = PlaceNpc(modKey, VaultDoctorRefId, "FO4SF_PrewarVaultDoctorRef", doctorNpc.FormKey, Pos("FO4SF_PrewarVaultDoctorRef"));
        var kelloggRef = PlaceNpc(modKey, KelloggRefId, "FO4SF_PrewarKelloggRef", kelloggNpc.FormKey, Pos("FO4SF_PrewarKelloggRef"));
        var instMRef = PlaceNpc(modKey, InstAgentMRefId, "FO4SF_PrewarInstAgentMRef", instMNpc.FormKey, Pos("FO4SF_PrewarInstAgentMRef"));
        var instFRef = PlaceNpc(modKey, InstAgentFRefId, "FO4SF_PrewarInstAgentFRef", instFNpc.FormKey, Pos("FO4SF_PrewarInstAgentFRef"));
        var broadcastRef = PlaceNpc(modKey, BroadcastRefId, "FO4SF_PrewarBroadcastRef", broadcastNpc.FormKey, Pos("FO4SF_PrewarBroadcastRef"));
        broadcastRef.Scale = 0.05f;
        var c1 = PlaceNpc(modKey, CrowdRunner01RefId, "FO4SF_PrewarCrowdRunner01Ref", crowdNpc.FormKey, Pos("FO4SF_PrewarCrowdRunner01Ref"));
        var c2 = PlaceNpc(modKey, CrowdRunner02RefId, "FO4SF_PrewarCrowdRunner02Ref", crowdNpc.FormKey, Pos("FO4SF_PrewarCrowdRunner02Ref"));
        var c3 = PlaceNpc(modKey, CrowdRunner03RefId, "FO4SF_PrewarCrowdRunner03Ref", crowdNpc.FormKey, Pos("FO4SF_PrewarCrowdRunner03Ref"));
        var c4 = PlaceNpc(modKey, CrowdRunner04RefId, "FO4SF_PrewarCrowdRunner04Ref", crowdNpc.FormKey, Pos("FO4SF_PrewarCrowdRunner04Ref"));
        foreach (var r in new[] { codsRef, spouseRef, spouseMaleRef, repRef, soldierRef, doctorRef, kelloggRef, instMRef, instFRef, broadcastRef, c1, c2, c3, c4 })
            AddToCell(r.EditorID!, r);

        var vb1 = PlaceObj(modKey, Vertibird01RefId, "FO4SF_PrewarVertibird01Ref", vertiBase.FormKey, Pos("FO4SF_PrewarVertibird01Ref"));
        var vb2 = PlaceObj(modKey, Vertibird02RefId, "FO4SF_PrewarVertibird02Ref", vertiBase.FormKey, Pos("FO4SF_PrewarVertibird02Ref"));
        var vb1HoverMark = PlaceObj(modKey, Vertibird01HoverMarkRefId, "FO4SF_PrewarVertibird01HoverMarkRef", xMarker.FormKey, Pos("FO4SF_PrewarVertibird01HoverMarkRef"));
        var vb2HoverMark = PlaceObj(modKey, Vertibird02HoverMarkRefId, "FO4SF_PrewarVertibird02HoverMarkRef", xMarker.FormKey, Pos("FO4SF_PrewarVertibird02HoverMarkRef"));
        var liftRef = PlaceObj(modKey, ExtLiftPlatformRefId, "FO4SF_PrewarExtLiftPlatformRef", liftBase.FormKey, Pos("FO4SF_PrewarExtLiftPlatformRef"));
        var nukeMark = PlaceObj(modKey, NukeAnchorRefId, "FO4SF_PrewarNukeAnchorRef", xMarker.FormKey, Pos("FO4SF_PrewarNukeAnchorRef"));
        var vaultArr = PlaceObj(modKey, VaultArrivalMarkerId, "FO4SF_PrewarVaultArrivalMarker", xMarker.FormKey, Pos("FO4SF_PrewarVaultArrivalMarker"));
        var kelloggMark = PlaceObj(modKey, KelloggMarkRefId, "FO4SF_PrewarKelloggMarkRef", xMarker.FormKey, Pos("FO4SF_PrewarKelloggMarkRef"));
        var instMaleMark = PlaceObj(modKey, InstMalePodMarkRefId, "FO4SF_PrewarInstMalePodMarkRef", xMarker.FormKey, Pos("FO4SF_PrewarInstMalePodMarkRef"));
        var instFemaleMark = PlaceObj(modKey, InstFemalePodMarkRefId, "FO4SF_PrewarInstFemalePodMarkRef", xMarker.FormKey, Pos("FO4SF_PrewarInstFemalePodMarkRef"));
        var spousePodMark = PlaceObj(modKey, SpousePodMarkRefId, "FO4SF_PrewarSpousePodMarkRef", xMarker.FormKey, Pos("FO4SF_PrewarSpousePodMarkRef"));
        var playerPodMark = PlaceObj(modKey, PlayerPodMarkRefId, "FO4SF_PrewarPlayerPodMarkRef", xMarker.FormKey, Pos("FO4SF_PrewarPlayerPodMarkRef"));
        var crowdGoalMark = PlaceObj(modKey, CrowdGoalMarkRefId, "FO4SF_PrewarCrowdGoalMarkRef", xMarker.FormKey, Pos("FO4SF_PrewarCrowdGoalMarkRef"));
        var crowdBridgeMark = PlaceObj(modKey, CrowdBridgeMarkRefId, "FO4SF_PrewarCrowdBridgeMarkRef", xMarker.FormKey, Pos("FO4SF_PrewarCrowdBridgeMarkRef"));
        var houseSpawn = PlaceObj(modKey, HouseSpawnMarkerId, "FO4SF_PrewarHouseSpawnMarker", xMarker.FormKey, Pos("FO4SF_PrewarHouseSpawnMarker"));
        foreach (var r in new[] { vb1, vb2, vb1HoverMark, vb2HoverMark, liftRef, nukeMark, vaultArr, kelloggMark, instMaleMark, instFemaleMark, spousePodMark, playerPodMark, crowdGoalMark, crowdBridgeMark, houseSpawn })
            AddToCell(r.EditorID!, r);

        // Main Quest (0x800): non-StartGameEnabled so fo4_vault111 (Skip Pre-War) never gets preempted
        var quest = new SF.Quest(new FormKey(modKey, QuestId), Rel)
        {
            EditorID = QuestEdid,
            Name = "War Never Changes",
            FormVersion = 581,
            Version2 = 12,
            Data = new SF.QuestData
            {
                Flags = SF.Quest.Flag.AllowRepeatedStages | SF.Quest.Flag.DisplaysInHud | SF.Quest.Flag.HasDialogueData,
                Priority = 50,
            },
        };
        foreach (var s in RequiredStages) quest.Stages.Add(new SF.QuestStage { Index = s });

        // Register real QuestReferenceAliases 0..9 across all 6 scenes + S1-15 QuestObjectives
        var aliasSpecs = new (uint AliasId, string AliasName, FormKey RefKey)[]
        {
            (0u, "Kellogg", kelloggRef.FormKey),
            (1u, "InstAgentM", instMRef.FormKey),
            (2u, "InstAgentF", instFRef.FormKey),
            (3u, "Spouse", spouseRef.FormKey),
            (4u, "Codsworth", codsRef.FormKey),
            (5u, "VaultTecRep", repRef.FormKey),
            (6u, "SoldierChecker", soldierRef.FormKey),
            (7u, "VaultDoctor", doctorRef.FormKey),
            (8u, "BroadcastSpeaker", broadcastRef.FormKey),
            (9u, "SpouseMale", spouseMaleRef.FormKey),
        };
        quest.Aliases ??= new ExtendedList<SF.AQuestAlias>();
        foreach (var (aliasId, aliasName, refKey) in aliasSpecs)
        {
            quest.Aliases.Add(new SF.QuestReferenceAlias
            {
                ID = aliasId,
                Name = aliasName,
                Flags = SF.AQuestAlias.Flag.Optional | SF.AQuestAlias.Flag.AllowDead | SF.AQuestAlias.Flag.AllowDisabled |
                        SF.AQuestAlias.Flag.AllowReserved | SF.AQuestAlias.Flag.UsesStoredText,
                ForcedReference = new FormLinkNullable<SF.IPlacedGetter>(refKey),
            });
        }
        foreach (var (oid, otext, targetAlias) in new (ushort, string, int)[]
        {
            (10, "Prepare for the day in Sanctuary Hills", 4),
            (20, "Evacuate to Vault 111", 6),
            (30, "Step onto the Vault 111 elevator platform", 6),
            (40, "Follow Vault-Tec staff inside Vault 111", 7),
            (50, "Wait inside the cryogenic pod", 0),
        })
        {
            var obj = new SF.QuestObjective { Index = oid, Flags = (SF.QuestObjective.Flag)0, DisplayText = otext };
            obj.Targets.Add(new SF.QuestObjectiveTarget { AliasID = targetAlias });
            quest.Objectives.Add(obj);
        }

        (uint AliasId, FormKey NpcKey, FormKey DefaultVoice) SpeakerMeta(string speakerEdid) => speakerEdid switch
        {
            "FO4SF_PrewarInstAgentMNPC" => (1u, instMNpc.FormKey, prewarMaleVoice.FormKey),
            "FO4SF_PrewarInstAgentFNPC" => (2u, instFNpc.FormKey, prewarFemaleVoice.FormKey),
            "FO4SF_PrewarSpouseFemaleNPC" => (3u, spouseFemaleNpc.FormKey, prewarFemaleVoice.FormKey),
            "FO4SF_PrewarCodsworthNPC" => (4u, codsNpc.FormKey, codsVoice.FormKey),
            "FO4SF_PrewarVaultTecRepNPC" => (5u, repNpc.FormKey, repVoice.FormKey),
            "FO4SF_PrewarSoldierCheckerNPC" => (6u, soldierNpc.FormKey, soldierVoice.FormKey),
            "FO4SF_PrewarVaultDoctorNPC" => (7u, doctorNpc.FormKey, doctorVoice.FormKey),
            "FO4SF_PrewarBroadcastNPC" => (8u, broadcastNpc.FormKey, bcastVoice.FormKey),
            "FO4SF_PrewarSpouseMaleNPC" => (9u, spouseMaleNpc.FormKey, prewarMaleVoice.FormKey),
            _ => (0u, kelloggNpc.FormKey, prewarMaleVoice.FormKey),
        };

        uint nextVoiceId = VoiceStartId;
        SF.Scene BuildPrewarScene(uint? fixedSceneId, string sceneEdid, string prefixEdid, IReadOnlyList<VoiceLineSpec> lines)
        {
            uint sid = fixedSceneId ?? nextVoiceId++;
            if (sid >= nextVoiceId) nextVoiceId = sid + 1;
            var sc = new SF.Scene(new FormKey(modKey, sid), Rel)
            {
                EditorID = sceneEdid,
                FormVersion = 581,
                Quest = new FormLinkNullable<SF.IQuestGetter>(quest.FormKey),
                Flags = (SF.Scene.Flag)0x1814,
                DEVT = true,
                Index = 0,
                SCPI = null,
                VNAM = new byte[] { 3, 0, 0, 0, 3, 0, 0, 0, 3, 0, 0, 0, 3, 0, 0, 0, 3, 0, 0, 0 },
            };
            sc.Actions ??= new ExtendedList<SF.ASceneAction>();
            var usedAliases = new HashSet<uint>();
            for (int idx = 0; idx < lines.Count; idx++)
            {
                var ln = lines[idx];
                var (spkAlias, spkNpcKey, defVoice) = SpeakerMeta(ln.SpeakerEdid);
                usedAliases.Add(spkAlias);
                FormKey spkVoice = !string.IsNullOrWhiteSpace(ln.VoiceTypeEdid) && voiceByEdid.TryGetValue(ln.VoiceTypeEdid, out var explicitV)
                    ? explicitV
                    : defVoice;

                var topic = new SF.DialogTopic(new FormKey(modKey, nextVoiceId++), Rel)
                {
                    EditorID = $"{prefixEdid}Topic_{idx:00}",
                    FormVersion = 581,
                    Quest = new FormLink<SF.IQuestGetter>(quest.FormKey),
                    Priority = 60f,
                    Category = SF.DialogTopic.CategoryEnum.Scene,
                    Subtype = SF.DialogTopic.SubtypeEnum.CustomScene,
                    SubtypeName = SF.DialogTopic.SubtypeNameEnum.CustomScene,
                };
                var info = new SF.DialogResponses(new FormKey(modKey, nextVoiceId++), Rel)
                {
                    EditorID = $"{prefixEdid}Info_{idx:00}",
                    FormVersion = 581,
                };
                var condData = new SF.GetIsIDConditionData { RunOnType = SF.Condition.RunOnType.Subject };
                condData.FirstParameter.Link.SetTo(spkNpcKey);
                info.Conditions.Add(new SF.ConditionFloat { CompareOperator = SF.CompareOperator.EqualTo, ComparisonValue = 1f, Data = condData });

                var resp = new SF.DialogResponse
                {
                    ResponseText = ln.Text,
                    WEMFile = ln.Wem,
                    EmotionOut = ln.Wem != 0u ? ln.Duration : 0f,
                };
                if (ln.Wem != 0u && !spkVoice.IsNull)
                {
                    resp.TROTs.Add(new SF.DialogResponseTROT
                    {
                        VoiceType = new FormLink<SF.IVoiceTypeGetter>(spkVoice),
                        EmotionOut = ln.Duration,
                    });
                }
                info.Responses.Add(resp);
                topic.Responses.Add(info);
                (topic.TopicInfoList ??= new()).Add(new FormLink<SF.IDialogResponsesGetter>(info.FormKey));
                quest.DialogTopics.Add(topic);

                sc.Phases.Add(new SF.ScenePhase { Name = $"Phase_{idx:00}", EditorWidth = 400 });
                sc.Actions.Add(new SF.DialogueSceneAction
                {
                    Name = $"Line_{idx:00}",
                    Index = (uint)(idx + 1),
                    AliasID = (int)spkAlias,
                    StartPhase = (uint)idx,
                    EndPhase = (uint)idx,
                    Topic = new FormLinkNullable<SF.IDialogTopicGetter>(topic.FormKey),
                    LoopingMin = 1f,
                    LoopingMax = 10f,
                });
            }
            foreach (var aId in usedAliases.OrderBy(x => x))
                sc.Actors.Add(new SF.SceneActor { ID = aId, BehaviorFlags = (SF.SceneActor.BehaviorFlag)0x10A, Flags = SF.SceneActor.Flag.NoCommandState });
            sc.LastActionIndex = (uint)lines.Count;
            quest.Scenes.Add(sc);
            return sc;
        }

        // S1-01 + S1-02 + S1-16: Real SCEN/DIAL/INFO + TROT for all 6 S1 scenes (0x900 = KelloggPodScene)
        var kelloggScene = BuildPrewarScene(VoiceStartId, "FO4SF_PrewarKelloggPodScene", "FO4SF_PrewarKellogg", voices.KelloggScene);
        var codsworthScene = BuildPrewarScene(null, "FO4SF_PrewarCodsworthScene", "FO4SF_PrewarCodsworth", voices.CodsworthScene);
        var repScene = BuildPrewarScene(null, "FO4SF_PrewarVaultTecRepScene", "FO4SF_PrewarRep", voices.VaultTecRepScene);
        var broadcastScene = BuildPrewarScene(null, "FO4SF_PrewarBroadcastScene", "FO4SF_PrewarBroadcast", voices.BroadcastScene);
        var soldierScene = BuildPrewarScene(null, "FO4SF_PrewarSoldierGateScene", "FO4SF_PrewarSoldier", voices.SoldierGateScene);
        var doctorScene = BuildPrewarScene(null, "FO4SF_PrewarVaultDoctorScene", "FO4SF_PrewarDoctor", voices.VaultDoctorScene);

        // Attach FO4SF_PrewarQuest + FO4SF_PrewarStandIns scripts cleanly
        var mainScript = new SF.ScriptEntry { Name = QuestScript, Flags = SF.ScriptEntry.Flag.Local };
        mainScript.Properties.Add(ObjProp("HouseSpawnMarker", houseSpawn.FormKey));
        mainScript.Properties.Add(ObjProp("PrewarVaultArrivalMarker", vaultArr.FormKey));
        mainScript.Properties.Add(new SF.ScriptIntProperty { Name = "PrewarVaultCellId", Flags = SF.ScriptProperty.Flag.Edited, Data = unchecked((int)resolvedPortCellId) });
        mainScript.Properties.Add(new SF.ScriptStringProperty { Name = "PortPlugin", Flags = SF.ScriptProperty.Flag.Edited, Data = "FO4Port.esm" });
        mainScript.Properties.Add(ObjProp("CodsworthActor", codsRef.FormKey));
        mainScript.Properties.Add(ObjProp("SpouseActor", spouseRef.FormKey));
        mainScript.Properties.Add(ObjProp("SpouseMaleActor", spouseMaleRef.FormKey));
        mainScript.Properties.Add(ObjProp("VaultTecRepActor", repRef.FormKey));
        mainScript.Properties.Add(ObjProp("SoldierCheckerActor", soldierRef.FormKey));
        mainScript.Properties.Add(ObjProp("VaultDoctorActor", doctorRef.FormKey));
        mainScript.Properties.Add(ObjProp("BroadcastActor", broadcastRef.FormKey));
        mainScript.Properties.Add(ObjProp("CodsworthScene", codsworthScene.FormKey));
        mainScript.Properties.Add(ObjProp("VaultTecRepScene", repScene.FormKey));
        mainScript.Properties.Add(ObjProp("BroadcastScene", broadcastScene.FormKey));
        mainScript.Properties.Add(ObjProp("SoldierGateScene", soldierScene.FormKey));
        mainScript.Properties.Add(ObjProp("VaultDoctorScene", doctorScene.FormKey));
        mainScript.Properties.Add(ObjProp("VaultSuitStandIn", vaultSuitKey));
        mainScript.Properties.Add(ObjProp("StandIns", quest.FormKey));
        mainScript.Properties.Add(new SF.ScriptStringProperty { Name = "NewGamePlugin", Flags = SF.ScriptProperty.Flag.Edited, Data = "FO4SFNewGame.esm" });
        mainScript.Properties.Add(new SF.ScriptIntProperty { Name = "NewGameQuestId", Flags = SF.ScriptProperty.Flag.Edited, Data = 0x000800 });
        mainScript.Properties.Add(new SF.ScriptIntProperty { Name = "Stage20LooksDone", Flags = SF.ScriptProperty.Flag.Edited, Data = 20 });
        mainScript.Properties.Add(ObjProp("PrewarActiveGlobal", activeGlob.FormKey));
        if (sf.WWiseEventDatas.Any(w => w.FormKey.ID == SfSirenOffWwedId))
            mainScript.Properties.Add(ObjProp("SirenStopSound", new FormKey(SfEsm, SfSirenOffWwedId)));

        var standInScript = new SF.ScriptEntry { Name = StandInsScript, Flags = SF.ScriptEntry.Flag.Local };
        standInScript.Properties.Add(ObjListProp("CrowdRunners", new[] { c1.FormKey, c2.FormKey, c3.FormKey, c4.FormKey }));
        standInScript.Properties.Add(ObjProp("CrowdBridgeMarker", crowdBridgeMark.FormKey));
        standInScript.Properties.Add(ObjProp("CrowdHillGoalMarker", crowdGoalMark.FormKey));
        if (sf.WWiseEventDatas.Any(w => w.FormKey.ID == SfSirenOnWwedId))
            standInScript.Properties.Add(ObjProp("CrowdPanicSound", new FormKey(SfEsm, SfSirenOnWwedId)));
        standInScript.Properties.Add(ObjProp("CrowdPanicEmitter", nukeMark.FormKey));
        standInScript.Properties.Add(ObjProp("Vertibird01", vb1.FormKey));
        standInScript.Properties.Add(ObjProp("Vertibird02", vb2.FormKey));
        // S1-13: s1_spec orbit/hover sky markers only (never ground CrowdGoalMark)
        standInScript.Properties.Add(ObjListProp("Vertibird01Waypoints", new[] { vb1HoverMark.FormKey, vb2HoverMark.FormKey }));
        standInScript.Properties.Add(ObjListProp("Vertibird02Waypoints", new[] { vb2HoverMark.FormKey, vb1HoverMark.FormKey }));
        if (sf.WWiseEventDatas.Any(w => w.FormKey.ID == SfVertibirdFlybyWwedId))
            standInScript.Properties.Add(ObjProp("VertibirdFlybySound", new FormKey(SfEsm, SfVertibirdFlybyWwedId)));
        standInScript.Properties.Add(ObjProp("ExtElevatorPlatform", liftRef.FormKey));
        standInScript.Properties.Add(ObjProp("ExtElevatorStartMarker", nukeMark.FormKey));
        standInScript.Properties.Add(new SF.ScriptFloatProperty { Name = "ExtElevatorDropM", Flags = SF.ScriptProperty.Flag.Edited, Data = spec.ExtLiftDropM });
        standInScript.Properties.Add(new SF.ScriptFloatProperty { Name = "ExtElevatorDurationS", Flags = SF.ScriptProperty.Flag.Edited, Data = 9.8f });
        standInScript.Properties.Add(new SF.ScriptFloatProperty { Name = "NukeTriggerDelayS", Flags = SF.ScriptProperty.Flag.Edited, Data = spec.NukeDelayS });
        if (sf.ImageSpaceAdapters.Any(im => im.FormKey.ID == SfExplosionFlashImodId))
            standInScript.Properties.Add(ObjProp("NukeExplosionFlashImod", new FormKey(SfEsm, SfExplosionFlashImodId)));
        if (sf.ImageSpaceAdapters.Any(im => im.FormKey.ID == SfExplosionNukeImodId))
            standInScript.Properties.Add(ObjProp("NukeExplosionMainImod", new FormKey(SfEsm, SfExplosionNukeImodId)));
        if (sf.ImageSpaceAdapters.Any(im => im.FormKey.ID == SfFadeToBlackImodId))
            standInScript.Properties.Add(ObjProp("NukeFadeToBlackImod", new FormKey(SfEsm, SfFadeToBlackImodId)));
        if (sf.WWiseEventDatas.Any(w => w.FormKey.ID == SfNukeExplosionWwedId))
            standInScript.Properties.Add(ObjProp("NukeExplosionSound", new FormKey(SfEsm, SfNukeExplosionWwedId)));
        standInScript.Properties.Add(ObjProp("NukeSoundEmitter", nukeMark.FormKey));
        standInScript.Properties.Add(ObjProp("NukeLookMarker", nukeMark.FormKey));
        standInScript.Properties.Add(ObjProp("PlayerPodHoldMarker", playerPodMark.FormKey));
        standInScript.Properties.Add(ObjProp("SpousePodActorMarker", spousePodMark.FormKey));
        standInScript.Properties.Add(ObjProp("KelloggPodMarker", kelloggMark.FormKey));
        standInScript.Properties.Add(ObjProp("InstMalePodMarker", instMaleMark.FormKey));
        standInScript.Properties.Add(ObjProp("InstFemalePodMarker", instFemaleMark.FormKey));
        standInScript.Properties.Add(ObjProp("SpouseActor", spouseRef.FormKey));
        standInScript.Properties.Add(ObjProp("SpouseMaleActor", spouseMaleRef.FormKey));
        standInScript.Properties.Add(ObjProp("KelloggActor", kelloggRef.FormKey));
        standInScript.Properties.Add(ObjProp("InstMaleActor", instMRef.FormKey));
        standInScript.Properties.Add(ObjProp("InstFemaleActor", instFRef.FormKey));
        standInScript.Properties.Add(ObjProp("KelloggSequenceScene", kelloggScene.FormKey));
        if (sf.WWiseEventDatas.Any(w => w.FormKey.ID == SfGunshotWwedId))
            standInScript.Properties.Add(ObjProp("KelloggGunshotSound", new FormKey(SfEsm, SfGunshotWwedId)));

        var vmad = new SF.QuestAdapter
        {
            Version = 6,
            ObjectFormat = 2,
            ExtraBindDataVersion = 3,
            Script = new SF.ScriptEntry { Name = "", Flags = SF.ScriptEntry.Flag.Local },
        };
        vmad.Scripts.Add(mainScript);
        vmad.Scripts.Add(standInScript);
        quest.VirtualMachineAdapter = vmad;
        mod.Quests.Add(quest);

        mod.ModHeader.Stats.NextFormID = nextVoiceId;
        Directory.CreateDirectory(outDir);
        var outPath = Path.Combine(outDir, Plugin);
        var loadOrder = new[] { SfEsm }.Concat(extraMasters).Distinct().ToArray();
        mod.BeginWrite.ToPath(outPath)
            .WithLoadOrder(loadOrder)
            .WithKnownMasters(loadOrder.Select(k => new KeyedMasterStyle(k, MasterStyle.Full)).ToArray())
            .Write();

        Console.WriteLine($"wrote {outPath} ({new FileInfo(outPath).Length:N0} bytes): QUST {QuestEdid}, " +
                          $"{mod.Npcs.Count} NPC_, {mod.VoiceTypes.Count} VTYP, {quest.Scenes.Count} SCEN, {quest.DialogTopics.Count} DIAL");
        return 0;
    }

    static IEnumerable<ModKey> ReadHeaderMasters(string pluginPath)
    {
        var outList = new List<ModKey>();
        using var fs = File.OpenRead(pluginPath);
        if (fs.Length < 24) return outList;
        using var br = new BinaryReader(fs);
        if (System.Text.Encoding.ASCII.GetString(br.ReadBytes(4)) != "TES4") return outList;
        uint dataSize = br.ReadUInt32();
        fs.Position = 24;
        long end = Math.Min(fs.Length, 24L + dataSize);
        while (fs.Position + 6 <= end)
        {
            string sub = System.Text.Encoding.ASCII.GetString(br.ReadBytes(4));
            ushort sz = br.ReadUInt16();
            if (fs.Position + sz > end) break;
            byte[] data = br.ReadBytes(sz);
            if (sub == "MAST")
            {
                string name = System.Text.Encoding.UTF8.GetString(data).TrimEnd('\0');
                if (!string.IsNullOrWhiteSpace(name))
                    outList.Add(ModKey.FromFileName(name));
            }
        }
        return outList;
    }

    public static int Check(string pluginPath, string sfPath, string? handyEsm, string? specPath, string? voicesPath)
    {
        if (!File.Exists(pluginPath)) throw new Refusal($"plugin missing: {pluginPath}");
        if (!File.Exists(sfPath)) throw new Refusal($"Starfield.esm missing: {sfPath}");
        var spec = LoadSpec(specPath);
        _ = LoadVoices(voicesPath);

        var known = new List<ModKey> { SfEsm, ModKey.FromFileName("FO4SFHome.esm") };
        foreach (var hm in ReadHeaderMasters(pluginPath))
            if (!known.Contains(hm)) known.Add(hm);
        if (!string.IsNullOrWhiteSpace(spec.SanctuaryEsmPath) && File.Exists(spec.SanctuaryEsmPath))
        {
            var sk = ModKey.FromFileName(Path.GetFileName(spec.SanctuaryEsmPath));
            if (!known.Contains(sk)) known.Add(sk);
        }
        if (!string.IsNullOrWhiteSpace(spec.PortEsmPath) && File.Exists(spec.PortEsmPath))
        {
            var pk = ModKey.FromFileName(Path.GetFileName(spec.PortEsmPath));
            if (!known.Contains(pk)) known.Add(pk);
        }

        using var plug = SF.StarfieldMod.CreateFromBinaryOverlay(pluginPath, Rel, Styles(known.ToArray()));
        var key = plug.ModKey;
        var problems = new List<string>();
        void Need(bool ok, string msg) { if (!ok) problems.Add(msg); }

        Need(plug.ModHeader.Flags.HasFlag(SF.StarfieldModHeader.HeaderFlag.Master), "missing Master header flag");
        var masters = plug.ModHeader.MasterReferences.Select(m => m.Master.FileName.String).ToList();
        Need(masters.Contains("Starfield.esm"), "Starfield.esm master missing");
        if (!string.IsNullOrWhiteSpace(handyEsm))
        {
            var handyName = Path.GetFileName(handyEsm);
            Need(!masters.Contains(handyName), $"leaked template master {handyName}");
            Need(plug.BodyParts.Any(b => b.FormKey == new FormKey(key, CodsworthBptdId) && b.EditorID == "FO4SF_PrewarCodsworthBPTD"),
                 "missing local FO4SF_PrewarCodsworthBPTD (0x802)");
            var codsSkin = plug.Armors.FirstOrDefault(a => a.FormKey == new FormKey(key, CodsworthSkinId) && a.EditorID == "FO4SF_PrewarCodsworthSkin");
            Need(codsSkin is not null && codsSkin.Armatures.Any(ar => ar.ArmorAddon.FormKey.ModKey == key),
                 "missing local FO4SF_PrewarCodsworthSkin (0x8F1) -> local AA");
            var aaModels = plug.ArmorAddons.Where(a => a.FormKey.ModKey == key)
                               .Select(a => a.WorldModel?.Male?.File?.GivenPath ?? a.WorldModel?.Female?.File?.GivenPath ?? "")
                               .ToList();
            Need(aaModels.Any(p => p.Contains("handy.nif", StringComparison.OrdinalIgnoreCase)),
                 "copied Codsworth ARMA missing handy.nif model");
        }

        var codsRace = plug.Races.FirstOrDefault(r => r.FormKey == new FormKey(key, CodsworthRaceId));
        Need(codsRace is { EditorID: "FO4SF_PrewarCodsworthRace" } && codsRace.Flags.HasFlag(SF.Race.Flag.AllowPcDialog),
             "Codsworth race 0x801 missing or lacks AllowPcDialog");
        if (!string.IsNullOrWhiteSpace(handyEsm))
            Need(codsRace?.Skin.FormKey == new FormKey(key, CodsworthSkinId),
                 "Codsworth race 0x801 WNAM Skin must point to FO4SF_PrewarCodsworthSkin (0x8F1)");

        var codsNpc = plug.Npcs.FirstOrDefault(n => n.FormKey == new FormKey(key, CodsworthNpcId));
        Need(codsNpc is { EditorID: "FO4SF_PrewarCodsworthNPC" } && codsNpc.Race.FormKey == new FormKey(key, CodsworthRaceId)
             && codsNpc.Flags.HasFlag(SF.Npc.Flag.Essential) && codsNpc.Flags.HasFlag(SF.Npc.Flag.Unique)
             && !codsNpc.Flags.HasFlag(SF.Npc.Flag.Respawn),
             "Codsworth NPC_ 0x803 invalid");
        if (!string.IsNullOrWhiteSpace(handyEsm))
            Need(codsNpc?.Skin.FormKey == new FormKey(key, CodsworthSkinId)
                 && codsNpc?.DefaultOutfit.FormKey == new FormKey(key, CodsworthOutfitId),
                 "Codsworth NPC_ 0x803 Skin/DefaultOutfit must point to local Handy skin (0x8F1/0x829)");

        // S1-05: Explicit Female ACBS bit on Nora (0x806), Doctor (0x80C), Female Agent (0x812), plus DefaultOutfit on all humans
        foreach (var femId in new[] { SpouseFemaleNpcId, VaultDoctorNpcId, InstAgentFNpcId })
        {
            var fn = plug.Npcs.FirstOrDefault(n => n.FormKey == new FormKey(key, femId));
            Need(fn is not null && fn.Flags.HasFlag(SF.Npc.Flag.Female), $"NPC_ 0x{femId:X} ({fn?.EditorID}) must have Female ACBS flag set");
        }
        foreach (var maleId in new[] { SpouseMaleNpcId, VaultTecRepNpcId, SoldierCheckerNpcId, KelloggNpcId, InstAgentMNpcId, CrowdRunnerNpcId, BroadcastNpcId })
        {
            var mn = plug.Npcs.FirstOrDefault(n => n.FormKey == new FormKey(key, maleId));
            Need(mn is not null && !mn.Flags.HasFlag(SF.Npc.Flag.Female), $"NPC_ 0x{maleId:X} ({mn?.EditorID}) must NOT have Female flag set");
        }
        foreach (var n in plug.Npcs)
        {
            Need(!n.DefaultOutfit.IsNull, $"NPC_ 0x{n.FormKey.ID:X} ({n.EditorID}) missing DefaultOutfit");
            var dname = n.Name?.String ?? "";
            Need(!dname.StartsWith("FO4SF ", StringComparison.OrdinalIgnoreCase) && !dname.Contains("(Stand-In)", StringComparison.OrdinalIgnoreCase),
                 $"NPC_ {n.EditorID} FULL {dname} leaks banned player-facing label");
        }

        // S1-01: Vault 111 Suit stand-in ARMO + non-stand-in player name
        var vsAr = plug.Armors.FirstOrDefault(a => a.FormKey == new FormKey(key, VaultSuitStandInId));
        Need(vsAr is not null && !string.IsNullOrWhiteSpace(vsAr.Name?.String)
             && !vsAr.Name!.String!.Contains("(Stand-In)", StringComparison.OrdinalIgnoreCase)
             && !vsAr.Name.String.StartsWith("FO4SF ", StringComparison.OrdinalIgnoreCase),
             "FO4SF_PrewarVaultSuitStandIn 0x833 missing or uses banned FULL label");

        // S1-06: Verify WRLD 0x02000803 override preserves master SNAM/PNAM/Climate/Water/Biome
        if (masters.Contains("FO4SFPrewar_Sanctuary.esm"))
        {
            var wOvr = plug.Worldspaces.FirstOrDefault(w => w.EditorID == spec.SanctuaryWorldEdid);
            Need(wOvr is not null, $"missing WRLD override {spec.SanctuaryWorldEdid}");
            var ovRaw = ReadWrldOverlayRaw(pluginPath, spec.SanctuaryWorldEdid);
            Need(ovRaw.HasValue && ovRaw.Value.SystemId != 0 && ovRaw.Value.PlanetId != 0,
                 $"WRLD override {spec.SanctuaryWorldEdid} dropped BGSWorldSpaceOverlay_Component SNAM/PNAM");
            string? sancCheck = !string.IsNullOrWhiteSpace(spec.SanctuaryEsmPath) && File.Exists(spec.SanctuaryEsmPath)
                ? spec.SanctuaryEsmPath
                : Path.Combine(Path.GetDirectoryName(Path.GetFullPath(pluginPath)) ?? "", "FO4SFPrewar_Sanctuary.esm");
            if (File.Exists(sancCheck))
            {
                var masterRaw = ReadWrldOverlayRaw(sancCheck, spec.SanctuaryWorldEdid);
                Need(!masterRaw.HasValue || ovRaw == masterRaw,
                     $"WRLD override SNAM/PNAM ({ovRaw}) mismatches master ({masterRaw})");
                using var sm = SF.StarfieldMod.CreateFromBinaryOverlay(sancCheck, Rel, Styles(SfEsm, ModKey.FromFileName("FO4SFHome.esm")));
                var sw = sm.Worldspaces.FirstOrDefault(w => w.EditorID == spec.SanctuaryWorldEdid);
                if (sw is not null && wOvr is not null)
                {
                    Need(wOvr.Climate.FormKey == sw.Climate.FormKey && wOvr.Water.FormKey == sw.Water.FormKey,
                         "WRLD override Climate/Water does not match FO4SFPrewar_Sanctuary.esm master");
                }
            }
        }

        static P3Float? PlacedPos(SF.IPlacedGetter r) => r switch
        {
            SF.IPlacedObjectGetter o => o.Position,
            SF.IPlacedNpcGetter n => n.Position,
            _ => null,
        };
        var placedById = plug.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(sb => sb.Cells)
                             .Concat(plug.Worldspaces.SelectMany(w => w.TopCell is not null ? new[] { w.TopCell } : Array.Empty<SF.ICellGetter>()))
                             .SelectMany(c => c.Persistent)
                             .ToDictionary(r => r.FormKey.ID, r => r);
        if (placedById.TryGetValue(VaultArrivalMarkerId, out var arrRef) && PlacedPos(arrRef) is { } arrPos)
            Need(MathF.Abs(arrPos.Z - (-0.11f)) < 1.0f, $"FO4SF_PrewarVaultArrivalMarker Z={arrPos.Z:F2} must sit at lower landing (~-0.11)");
        if (placedById.TryGetValue(HouseSpawnMarkerId, out var hsRef) && PlacedPos(hsRef) is { } hsPos)
        {
            foreach (var spId in new[] { SpouseRefId, SpouseMaleRefId })
            {
                Need(placedById.TryGetValue(spId, out var spRef), $"missing spouse ref 0x{spId:X}");
                if (spRef is not null && PlacedPos(spRef) is { } spPos)
                {
                    float dx = spPos.X - hsPos.X, dy = spPos.Y - hsPos.Y;
                    Need(MathF.Sqrt(dx * dx + dy * dy) >= 1.5f, $"Spouse 0x{spId:X} too close to HouseSpawnMarker (< 1.5m)");
                }
            }
        }

        var vtypIds = plug.VoiceTypes.Select(v => v.FormKey).ToHashSet();
        var q = plug.Quests.FirstOrDefault(x => x.FormKey == new FormKey(key, QuestId));
        Need(q is { EditorID: QuestEdid }, $"QUST 0x{QuestId:X} is not {QuestEdid}");
        if (q is not null)
        {
            Need(!q.Data!.Flags.HasFlag(SF.Quest.Flag.StartGameEnabled),
                 "FO4SF_PrewarQuest must NOT be StartGameEnabled (would preempt fo4_vault111 Skip Pre-War)");
            var qName = q.Name?.String ?? "";
            Need(!qName.StartsWith("FO4SF ", StringComparison.OrdinalIgnoreCase) && !qName.Contains("(Stand-In)", StringComparison.OrdinalIgnoreCase),
                 $"QUST name {qName} leaks banned label");
            var stageIds = q.Stages.Select(s => s.Index).ToHashSet();
            Need(RequiredStages.All(stageIds.Contains), "FO4SF_PrewarQuest missing one or more required stages [0,10,20,30,40,50,60,200]");
            Need(q.Objectives.Count >= 4, "FO4SF_PrewarQuest missing S1-15 HUD QuestObjectives");
            foreach (var ob in q.Objectives)
            {
                var dt = ob.DisplayText?.String ?? "";
                Need(!dt.StartsWith("FO4SF ", StringComparison.OrdinalIgnoreCase) && !dt.Contains("(Stand-In)", StringComparison.OrdinalIgnoreCase),
                     $"Objective {ob.Index} text '{dt}' leaks banned label");
            }
            var aliasIds = (q.Aliases ?? Array.Empty<SF.IAQuestAliasGetter>()).OfType<SF.IQuestReferenceAliasGetter>().Select(a => a.ID).ToHashSet();
            Need(new uint[] { 0, 1, 2, 3, 4, 5, 6, 7, 8, 9 }.All(aliasIds.Contains),
                 "FO4SF_PrewarQuest missing QuestReferenceAliases [0..9]");
            var scripts = q.VirtualMachineAdapter?.Scripts ?? Array.Empty<SF.IScriptEntryGetter>();
            var main = scripts.FirstOrDefault(s => s.Name == QuestScript);
            var stand = scripts.FirstOrDefault(s => s.Name == StandInsScript);
            Need(main is not null && stand is not null, "FO4SF_PrewarQuest missing FO4SF_PrewarQuest or FO4SF_PrewarStandIns VMAD script");
            if (main is not null)
            {
                var pMap = main.Properties.ToDictionary(p => p.Name);
                Need(pMap.ContainsKey("HouseSpawnMarker") && pMap.ContainsKey("PrewarVaultArrivalMarker")
                     && pMap.ContainsKey("Stage20LooksDone") && pMap.ContainsKey("NewGameQuestId")
                     && pMap.ContainsKey("SpouseMaleActor") && pMap.ContainsKey("VaultSuitStandIn")
                     && pMap.ContainsKey("CodsworthScene") && pMap.ContainsKey("VaultTecRepScene")
                     && pMap.ContainsKey("BroadcastScene") && pMap.ContainsKey("SoldierGateScene")
                     && pMap.ContainsKey("VaultDoctorScene"),
                     "FO4SF_PrewarQuest missing Stage 20 handoff / scene / spouse / suit properties");
            }
            if (stand is not null)
            {
                var sMap = stand.Properties.ToDictionary(p => p.Name);
                Need(sMap.ContainsKey("CrowdRunners") && sMap.ContainsKey("CrowdBridgeMarker") && sMap.ContainsKey("Vertibird01")
                     && sMap.ContainsKey("ExtElevatorPlatform") && sMap.ContainsKey("KelloggSequenceScene"),
                     "FO4SF_PrewarStandIns missing stand-in beat properties");
                FormKey? MarkerFk(string n) => sMap.TryGetValue(n, out var pr) && pr is SF.IScriptObjectPropertyGetter o ? o.Object.FormKey : null;
                var podMarks = new[] { MarkerFk("PlayerPodHoldMarker"), MarkerFk("SpousePodActorMarker"), MarkerFk("KelloggPodMarker"), MarkerFk("InstMalePodMarker"), MarkerFk("InstFemalePodMarker") };
                Need(podMarks.All(k => k.HasValue) && podMarks.Select(k => k!.Value).Distinct().Count() == 5,
                     "Beat (e) pod markers must all be distinct ObjectReferences");
                foreach (var wProp in new[] { "Vertibird01Waypoints", "Vertibird02Waypoints" })
                {
                    if (sMap.TryGetValue(wProp, out var wp) && wp is SF.IScriptObjectListPropertyGetter wl)
                        Need(wl.Objects.All(o => o.Object.FormKey.ID != CrowdGoalMarkRefId), $"{wProp} must not route Vertibirds to ground CrowdGoalMark");
                }
            }
            Need(q.Scenes.Count >= 6, $"FO4SF_PrewarQuest expected >= 6 scenes (S1-01), got {q.Scenes.Count}");
            var kScene = q.Scenes.FirstOrDefault(s => s.FormKey.ID == VoiceStartId && s.EditorID == "FO4SF_PrewarKelloggPodScene");
            Need(kScene is not null, "missing FO4SF_PrewarKelloggPodScene at 0x900");
            foreach (var sc in q.Scenes)
            {
                var sceneActorIds = sc.Actors.Select(a => a.ID).ToHashSet();
                Need((sc.Actions ?? Array.Empty<SF.IASceneActionGetter>()).OfType<SF.IDialogueSceneActionGetter>()
                    .All(a => a.AliasID >= 0 && aliasIds.Contains((uint)a.AliasID) && sceneActorIds.Contains((uint)a.AliasID)),
                    $"{sc.EditorID} DialogueSceneAction references undeclared AliasID");
            }
            foreach (var dt in q.DialogTopics)
                foreach (var info in dt.Responses)
                    foreach (var r in info.Responses)
                        if (r.WEMFile != 0u)
                            Need(r.TROTs.Count > 0 && r.TROTs.All(t => vtypIds.Contains(t.VoiceType.FormKey)),
                                 $"INFO {info.EditorID} WEMFile 0x{r.WEMFile:X8} missing matching local VTYP TROT");
        }

        if (problems.Count > 0)
        {
            foreach (var p in problems) Console.Error.WriteLine("check fail: " + p);
            return 1;
        }
        Console.WriteLine($"check ok: {pluginPath} (QUST 0x{QuestId:X}, RACE 0x{CodsworthRaceId:X}, {plug.Npcs.Count} NPC_, {q!.Stages.Count} stages, masters={string.Join(",", masters)})");
        return 0;
    }

    public static int SelfTest(string scratchDir)
    {
        Directory.CreateDirectory(scratchDir);
        var sfPath = Path.Combine(scratchDir, "Starfield.esm");
        var handyPath = Path.Combine(scratchDir, "FO4SF_RA2Handy.esm");
        var outDir = Path.Combine(scratchDir, "out");
        Directory.CreateDirectory(outDir);

        // Minimal synthetic Starfield.esm + FO4SF_RA2Handy.esm fixture
        var sf = new SF.StarfieldMod(SfEsm, Rel);
        sf.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Master;
        var hRace = new SF.Race(new FormKey(SfEsm, SfHumanRaceId), Rel) { EditorID = SfHumanRaceEdid };
        var bRace = new SF.Race(new FormKey(SfEsm, 0x010000), Rel) { EditorID = "MiniBotRace" };
        var bSkin = new SF.Armor(new FormKey(SfEsm, SfMiniBotSkinId), Rel) { EditorID = "Skin_MiniBotA_Gardening" };
        bRace.Skin.SetTo(bSkin.FormKey);
        var bot = new SF.Npc(new FormKey(SfEsm, 0x010001), Rel) { EditorID = SfMiniBotEdid, Race = new FormLinkNullable<SF.IRaceGetter>(bRace.FormKey) };
        var xm = new SF.Static(new FormKey(SfEsm, SfXMarkerId), Rel) { EditorID = "XMarker", Model = new SF.Model { File = @"Markers\MarkerX.nif" } };
        var vMale = new SF.VoiceType(new FormKey(SfEsm, SfMaleEvenTonedVoiceId), Rel) { EditorID = "GenericMaleEvenToned", Flags = SF.VoiceType.Flag.AllowDefaultDialog };
        var vFemale = new SF.VoiceType(new FormKey(SfEsm, SfFemaleEvenTonedVoiceId), Rel) { EditorID = "GenericFemaleEvenToned", Flags = SF.VoiceType.Flag.AllowDefaultDialog };
        var pf = new SF.Faction(new FormKey(SfEsm, SfPlayerFactionId), Rel) { EditorID = "PlayerFaction" };
        var flashImad = new SF.ImageSpaceAdapter(new FormKey(SfEsm, SfExplosionFlashImodId), Rel) { EditorID = "ExplosionFlash" };
        var nukeImad = new SF.ImageSpaceAdapter(new FormKey(SfEsm, SfExplosionNukeImodId), Rel) { EditorID = "ExplosionNukeImod" };
        var fadeImad = new SF.ImageSpaceAdapter(new FormKey(SfEsm, SfFadeToBlackImodId), Rel) { EditorID = "FadetoBlackImod" };
        var vsArTpl = new SF.Armor(new FormKey(SfEsm, SfVaultSuitStandInArmorId), Rel) { EditorID = "Clothes_Worker_Jumpsuit_ECS_Security" };
        var maleTplNpc = new SF.Npc(new FormKey(SfEsm, SfMaleCitizenTplId), Rel) { EditorID = "EncCitizenFaceM01_EvenToned_AltFace02", Race = new FormLinkNullable<SF.IRaceGetter>(hRace.FormKey) };
        var femTplNpc = new SF.Npc(new FormKey(SfEsm, SfFemaleCitizenTplId), Rel) { EditorID = "EncCitizenFaceF10_WesternAmerican_AltFace", Race = new FormLinkNullable<SF.IRaceGetter>(hRace.FormKey), Flags = SF.Npc.Flag.Female };
        sf.Races.Add(hRace);
        sf.Races.Add(bRace);
        sf.Armors.Add(bSkin);
        sf.Armors.Add(vsArTpl);
        sf.Npcs.Add(bot);
        sf.Npcs.Add(maleTplNpc);
        sf.Npcs.Add(femTplNpc);
        foreach (var oid in new[] { SfOutfitCitizenFormalId, SfOutfitNhCitizenId, SfOutfitBusinessId, SfOutfitArmyFatiguesId, SfOutfitDoctorId, SfOutfitKelloggId, SfOutfitScientistId })
            sf.Outfits.Add(new SF.Outfit(new FormKey(SfEsm, oid), Rel) { EditorID = $"SynthOtft_{oid:X}" });
        foreach (var wid in new[] { SfSirenOnWwedId, SfSirenOffWwedId, SfVertibirdFlybyWwedId, SfNukeExplosionWwedId, SfGunshotWwedId })
            sf.WWiseEventDatas.Add(new SF.WWiseEventData(new FormKey(SfEsm, wid), Rel) { EditorID = $"SynthWwed_{wid:X}" });
        sf.Statics.Add(xm);
        sf.VoiceTypes.Add(vMale);
        sf.VoiceTypes.Add(vFemale);
        sf.Factions.Add(pf);
        sf.ImageSpaceAdapters.Add(flashImad);
        sf.ImageSpaceAdapters.Add(nukeImad);
        sf.ImageSpaceAdapters.Add(fadeImad);
        sf.ModHeader.Stats.NextFormID = 0x400000;
        sf.BeginWrite.ToPath(sfPath).WithNoLoadOrder().NoCheckIfLowerRangeDisallowed().Write();

        var handyKey = ModKey.FromFileName("FO4SF_RA2Handy.esm");
        var hm = new SF.StarfieldMod(handyKey, Rel);
        hm.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Master;
        var hb = new SF.BodyPartData(new FormKey(handyKey, 0x801), Rel) { EditorID = HandyBptdEdid };
        var ha = new SF.ArmorAddon(new FormKey(handyKey, 0x802), Rel)
        {
            EditorID = "FO4SF_RA2Handy_AA",
            WorldModel = new GenderedItem<SF.Model?>(
                new SF.Model { File = @"FO4SF\Actors\Handy\handy.nif" },
                new SF.Model { File = @"FO4SF\Actors\Handy\handy.nif" }),
        };
        var hs = new SF.Armor(new FormKey(handyKey, 0x803), Rel) { EditorID = "FO4SF_RA2Handy_Skin" };
        hs.Armatures.Add(new SF.ArmorAddonModel { AddonIndex = 0, ArmorAddon = new FormLinkNullable<SF.IArmorAddonGetter>(ha.FormKey) });
        var hr = new SF.Race(new FormKey(handyKey, 0x800), Rel)
        {
            EditorID = HandyRaceEdid,
            BodyPartData = new FormLinkNullable<SF.IBodyPartDataGetter>(hb.FormKey),
            Skin = new FormLinkNullable<SF.IArmorGetter>(hs.FormKey),
        };
        ha.Race.SetTo(hr.FormKey);
        hs.Race.SetTo(hr.FormKey);
        hm.BodyParts.Add(hb);
        hm.ArmorAddons.Add(ha);
        hm.Armors.Add(hs);
        hm.Races.Add(hr);
        hm.ModHeader.Stats.NextFormID = 0x810;
        hm.BeginWrite.ToPath(handyPath).WithLoadOrder(SfEsm).WithKnownMasters(new KeyedMasterStyle(SfEsm, MasterStyle.Full)).Write();

        if (Write(sfPath, outDir, handyPath, null, null) != 0) return 1;
        var plugPath = Path.Combine(outDir, Plugin);
        if (Check(plugPath, sfPath, handyPath, null, null) != 0) return 1;

        // Multi-master Check() without --spec (verifies S1-06 WRLD SNAM/PNAM preservation & TES4 MAST header master discovery)
        var multiDir = Path.Combine(scratchDir, "multi_out");
        Directory.CreateDirectory(multiDir);
        var homeKey = ModKey.FromFileName("FO4SFHome.esm");
        var homeMod = new SF.StarfieldMod(homeKey, Rel);
        homeMod.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Master;
        var homeWatr = new SF.Water(new FormKey(homeKey, 0x80C), Rel) { EditorID = "FO4SFHomeDryWater" };
        homeMod.Waters.Add(homeWatr);
        homeMod.ModHeader.Stats.NextFormID = 0x810;
        var homePath = Path.Combine(scratchDir, "FO4SFHome.esm");
        homeMod.BeginWrite.ToPath(homePath).WithLoadOrder(SfEsm).WithKnownMasters(new KeyedMasterStyle(SfEsm, MasterStyle.Full)).Write();
        var sancKey = ModKey.FromFileName("FO4SFPrewar_Sanctuary.esm");
        var sancMod = new SF.StarfieldMod(sancKey, Rel);
        sancMod.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Master;
        sancMod.Statics.Add(new SF.Static(new FormKey(sancKey, 0x800), Rel) { EditorID = "FO4SF_SanctuaryDummy" });
        var sancClmt = new SF.Climate(new FormKey(sancKey, 0x805), Rel) { EditorID = "FO4SF_PrewarSanctuaryClimate" };
        sancMod.Climates.Add(sancClmt);
        var sancWrld = new SF.Worldspace(new FormKey(sancKey, 0x803), Rel)
        {
            EditorID = "FO4SF_PrewarSanctuaryWorld",
            TopCell = new SF.Cell(new FormKey(sancKey, 0x802), Rel),
        };
        sancWrld.Climate.SetTo(sancClmt.FormKey);
        sancWrld.Water.SetTo(homeWatr.FormKey);
        var sancOv = new SF.WorldSpaceOverlayComponent
        {
            SNAM = BitConverter.GetBytes(0x000F04F2u),
            PNAM = BitConverter.GetBytes(1u),
        };
        sancWrld.Components.Add(sancOv);
        sancMod.Worldspaces.Add(sancWrld);
        sancMod.ModHeader.Stats.NextFormID = 0x810;
        var sancPath = Path.Combine(scratchDir, "FO4SFPrewar_Sanctuary.esm");
        sancMod.BeginWrite.ToPath(sancPath).WithLoadOrder(SfEsm, homeKey)
            .WithKnownMasters(new KeyedMasterStyle(SfEsm, MasterStyle.Full), new KeyedMasterStyle(homeKey, MasterStyle.Full)).Write();
        var multiSpecPath = Path.Combine(scratchDir, "multi_spec.json");
        File.WriteAllText(multiSpecPath, JsonSerializer.Serialize(new { sanctuary_world = new { esm = sancPath, world_edid = "FO4SF_PrewarSanctuaryWorld" } }));
        if (Write(sfPath, multiDir, handyPath, multiSpecPath, null) != 0) return 1;
        var multiPlugPath = Path.Combine(multiDir, Plugin);
        if (Check(multiPlugPath, sfPath, handyPath, null, null) != 0) return 1;

        // Negative mutation on S1-06 (dropping SNAM/PNAM from WRLD override must fail Check)
        var badWrldDir = Path.Combine(scratchDir, "bad_wrld");
        Directory.CreateDirectory(badWrldDir);
        var badWrldPath = Path.Combine(badWrldDir, Plugin);
        var mw = SF.StarfieldMod.CreateFromBinary(multiPlugPath, Rel, Styles(SfEsm, homeKey, sancKey));
        var badOv = mw.Worldspaces.First().Components.OfType<SF.WorldSpaceOverlayComponent>().First();
        badOv.SNAM = null;
        badOv.PNAM = null;
        mw.BeginWrite.ToPath(badWrldPath).WithLoadOrder(SfEsm, homeKey, sancKey)
            .WithKnownMasters(new KeyedMasterStyle(SfEsm, MasterStyle.Full), new KeyedMasterStyle(homeKey, MasterStyle.Full), new KeyedMasterStyle(sancKey, MasterStyle.Full))
            .Write();
        if (Check(badWrldPath, sfPath, handyPath, multiSpecPath, null) == 0)
        {
            Console.Error.WriteLine("selftest fail: WRLD SNAM/PNAM drop unexpectedly passed Check");
            return 1;
        }

        // Negative mutation checks: StartGameEnabled, stripped AllowPcDialog, dropped script, MiniBot skin regression, cleared Aliases, cleared Female flag, cleared DefaultOutfit
        var mutExpectations = new (string Label, Action<SF.StarfieldMod> Mutate)[]
        {
            ("StartGameEnabled set on FO4SF_PrewarQuest", m => m.Quests.First(q => q.FormKey.ID == QuestId).Data!.Flags |= SF.Quest.Flag.StartGameEnabled),
            ("Codsworth race AllowPcDialog cleared", m => m.Races.First(r => r.FormKey.ID == CodsworthRaceId).Flags &= ~SF.Race.Flag.AllowPcDialog),
            ("Codsworth race reverted to MiniBot skin", m => m.Races.First(r => r.FormKey.ID == CodsworthRaceId).Skin.SetTo(new FormKey(SfEsm, SfMiniBotSkinId))),
            ("StandIns script removed", m => m.Quests.First(q => q.FormKey.ID == QuestId).VirtualMachineAdapter!.Scripts.RemoveAll(s => s.Name == StandInsScript)),
            ("Quest Aliases cleared", m => m.Quests.First(q => q.FormKey.ID == QuestId).Aliases!.Clear()),
            ("Nora Female ACBS flag cleared", m => m.Npcs.First(n => n.FormKey.ID == SpouseFemaleNpcId).Flags &= ~SF.Npc.Flag.Female),
            ("Vault Doctor DefaultOutfit cleared", m => m.Npcs.First(n => n.FormKey.ID == VaultDoctorNpcId).DefaultOutfit.Clear()),
        };
        for (int idx = 0; idx < mutExpectations.Length; idx++)
        {
            var (label, mut) = mutExpectations[idx];
            var badDir = Path.Combine(scratchDir, $"bad_{idx}");
            Directory.CreateDirectory(badDir);
            var badPath = Path.Combine(badDir, Plugin);
            var m2 = SF.StarfieldMod.CreateFromBinary(plugPath, Rel, Styles(SfEsm));
            mut(m2);
            m2.BeginWrite.ToPath(badPath).WithLoadOrder(SfEsm).WithKnownMasters(new KeyedMasterStyle(SfEsm, MasterStyle.Full)).Write();
            if (Check(badPath, sfPath, handyPath, null, null) == 0)
            {
                Console.Error.WriteLine($"selftest fail: mutation '{label}' unexpectedly passed Check");
                return 1;
            }
        }
        Console.WriteLine($"selftest ok: passed write + check + {mutExpectations.Length} negative corruption checks");
        return 0;
    }
}
