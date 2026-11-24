// NextStoryMissionsS7S9: S7 Roof Power Armor + Minigun, S8 Concord Wave 2 (respawnPool=8) + Deathclaw,
// and S9 Museum Lobby Starfield SCEN -> DialogueConcordArea 50 -> Min01 20 -> Min00 100 -> Red Rocket walk ->
// Sanctuary Min01 220 -> Min01SturgesIntro Starfield SCEN -> Min01 1000 ("Build sheltered beds") hard stop.
//
// Reserved local FormIDs strictly in 0xBE0..0xC05 (zero overlap with
// 0x800..0x9FF base/looks, 0xA00..0xB56 A4/A7/A7cd, 0xB60 holding cell, 0xB80..0xB8B Step 3q, or 0xB8C..0xBDC S2-S6):
//   S7 Roof (markers live in 0xBF5 holding cell, relocated at runtime to Commonwealth via 0x005C50/0x0A775B):
//     0xBE0  ACTI  FO4SF_S7_RoofMinigunActi      (Vertibird Minigun 0001F582/0001F583 stand-in world activator)
//     0xBE1  REFR  FO4SF_S7_RoofMinigunRef       (persistent, InitiallyDisabled, target (-2004.72, -1715.40, 102.68))
//     0xBE2  REFR  FO4SF_S7_RoofFrameMarker      (persistent XMarker, target (-1995.73, -1723.10, 97.54), rotZ=351.07 deg)
//     0xBE3  REFR  FO4SF_S7_RoofDoorMarker       (persistent XMarker, target (-2008.49, -1722.39, 97.42))
//   S8 Wave 2 & Deathclaw (actors + markers live in 0xBF5 holding cell):
//     0xBE4  NPC_  FO4_Gristle                   ("Gristle" 00019567 / 0001F68C boss, non-essential, non-respawning)
//     0xBE5  NPC_  FO4_WaveRaiderHeavy           (LvlRaider_Handmade_MG 0007B620 automatic wave raider)
//     0xBE6  ACHR  FO4SF_S8_WaveRaider01         (target DN092_AlleyNearMarker 00023F0B, respawns across Pool=8)
//     0xBE7  ACHR  FO4SF_S8_WaveRaider02         (target RaiderSpawnerMarker02 0001F15D, respawns across Pool=8)
//     0xBE8  ACHR  FO4SF_S8_WaveRaider03         (FO4_WaveRaiderHeavy at TestDeathclawAmbushExitPoint 0002C96B, respawns)
//     0xBE9  ACHR  FO4SF_S8_RoofLookout          (target RaiderSpawnerMarkerRooftop 00023EFA, stays dead)
//     0xBEA  ACHR  FO4SF_S8_Gristle              (FO4_Gristle at 0002C96B, stays dead)
//     0xBEB..0xBF0  REFR  FO4SF_S8_WaveSpawner01..06  (DN092WaveSpawner01..06: 00029BCD..0003D242)
//     0xBF1  REFR  FO4SF_S8_WavePost02Marker     (DN092_WavePost02 00023BC5 failsafe)
//     0xBF2  REFR  FO4SF_S8_GrateTriggerMarker   (DN092ForceSpawnDeathclawTrigger 0009A144, <=17m trigger)
//     0xBF3  REFR  FO4SF_S8_DeathclawSpawnMarker (ConcordAmbushDeathclaw 0001F15B / 0002C969 (-2068.22,-1640.18,88.22))
//   S9 Holding Cell, Hard Stop, & Real Starfield SCENs (zero FO4 copyrighted text in source):
//     0xBF4  GLOB  FO4SF_S9_HardStopAtMin01_1000 (1.0: holds MinRecruit00 & MQ103 off at Min01 1000)
//     0xBF5  CELL  FO4SF_S7S9_HoldingCell        (IsInteriorCell holding cell — 0 WRLD overrides added by S7-S9)
//     0xBF6..0xBFC  SCEN/DIAL/INFO FO4SF_S9_PrestonLobbyScene (Min00 stage 80, alias 0, GlobalIsZero 0x979)
//     0xBFD..0xC03  SCEN/DIAL/INFO FO4SF_S9_SturgesIntroScene (Min01 stage 220, alias 1, GlobalIsZero 0x979, from 001188B4)
//     0xC04  MESG  FO4SF_S9_PrestonLobbyFallbackMsg (gated strictly behind TalkUseMessageBox != 0)
//     0xC05  MESG  FO4SF_S9_SturgesIntroFallbackMsg (gated strictly behind TalkUseMessageBox != 0)

using System.Globalization;
using System.Text.Json;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Records;
using Noggog;
using SF = Mutagen.Bethesda.Starfield;

static class NextStoryMissionsS7S9
{
    public const string Plugin = "FO4SFMission.esm";
    public const string ScriptName = "FO4SF_Min00Quest";
    public const string SanctuaryScriptName = "FO4SF_Sanctuary01Quest";

    public const uint S7RoofMinigunActiId = 0xBE0;
    public const uint S7RoofMinigunRefId = 0xBE1;
    public const uint S7RoofFrameMarkerId = 0xBE2;
    public const uint S7RoofDoorMarkerId = 0xBE3;

    public const uint GristleNpcId = 0xBE4;
    public const uint WaveRaiderHeavyNpcId = 0xBE5;
    public const uint FirstS8WaveActorRefId = 0xBE6;
    public const int S8WaveActorCount = 5;
    public const uint FirstS8WaveSpawnerMarkerId = 0xBEB;
    public const uint S8WaveFailsafeMarkerId = 0xBF1;
    public const uint S8GrateTriggerMarkerId = 0xBF2;
    public const uint S8DeathclawSpawnMarkerId = 0xBF3;

    public const uint S9HardStopGlobId = 0xBF4;
    public const uint S7S9HoldingCellId = 0xBF5;
    public const string S7S9HoldingCellEdid = "FO4SF_S7S9_HoldingCell";

    public const uint S9PrestonLobbySceneId = 0xBF6;
    public const string S9PrestonLobbySceneEdid = "FO4SF_S9_PrestonLobbyScene";
    public const uint S9PrestonLobbyGreetTopicId = 0xBF7;
    public const uint S9PrestonLobbyGreetInfoId = 0xBF8;
    public const uint S9PrestonLobbyChoiceTopicId = 0xBF9;
    public const uint S9PrestonLobbyChoiceInfoId = 0xBFA;
    public const uint S9PrestonLobbyReplyTopicId = 0xBFB;
    public const uint S9PrestonLobbyReplyInfoId = 0xBFC;

    public const uint S9SturgesIntroSceneId = 0xBFD;
    public const string S9SturgesIntroSceneEdid = "FO4SF_S9_SturgesIntroScene";
    public const uint S9SturgesIntroGreetTopicId = 0xBFE;
    public const uint S9SturgesIntroGreetInfoId = 0xBFF;
    public const uint S9SturgesIntroChoiceTopicId = 0xC00;
    public const uint S9SturgesIntroChoiceInfoId = 0xC01;
    public const uint S9SturgesIntroReplyTopicId = 0xC02;
    public const uint S9SturgesIntroReplyInfoId = 0xC03;

    public const uint S9PrestonLobbyFallbackMsgId = 0xC04;
    public const uint S9SturgesIntroFallbackMsgId = 0xC05;
    public const uint MaxAllocatedId = 0xC06;

    public const string VertibirdMinigunModel = @"fo4sf\powerarmor\vertibirdminigun.nif";
    public const int CoreLaserMusketId = 0x00089D;
    public const int CoreFusionCellId = 0x00089B;
    public const int CoreAmmo5mmId = 0x00089F;
    public const int CoreMinigunId = 0x0008A0;
    public const int CoreBottlecapId = 0x0008A4;

    public static readonly ushort[] SanctuaryS9Stages =
    {
        10, 20, 50, 100, 220, 1000, 1050, 1200, 1250, 1300, 1350, 1400, 1450, 1500
    };

    // Merged Commonwealth target coordinates verified from Fallout4.esm:
    public static readonly P3Float S7RoofDoorMerged = new(-2008.49f, -1722.39f, 97.42f);
    public static readonly P3Float S7RoofFrameMerged = new(-1995.73f, -1723.10f, 97.54f);
    public const float S7RoofFrameYawDeg = 351.07f;
    public static readonly P3Float S7RoofMinigunMerged = new(-2004.72f, -1715.40f, 102.68f);
    public static readonly P3Float S7RoofMinigunRotDeg = new(-0.86f, 13.47f, 292.55f);

    public static readonly (string Name, P3Float MergedPos, float YawDeg, bool Respawns)[] S8WaveInitialSpecs =
    {
        ("WaveRaider01", new(-2050.79f, -1675.63f, 88.40f), 84.70f, true),   // DN092_AlleyNearMarker 00023F0B
        ("WaveRaider02", new(-2055.43f, -1646.49f, 91.59f), 165.32f, true),  // RaiderSpawnerMarker02 0001F15D
        ("WaveRaider03", new(-2066.37f, -1642.37f, 88.17f), 130.82f, true),  // TestDeathclawAmbushExitPoint 0002C96B
        ("RoofLookout",  new(-2042.53f, -1690.99f, 101.09f), 116.14f, false),// RaiderSpawnerMarkerRooftop 00023EFA
        ("Gristle",      new(-2066.37f, -1642.37f, 88.17f), 130.82f, false), // Gristle EncRaider01Boss 00019567
    };

    public static readonly P3Float[] S8WaveSpawnerMergedCoords =
    {
        new(-2109.40f, -1635.39f, 88.27f), // DN092WaveSpawner01 00029BCD
        new(-2058.78f, -1601.50f, 88.65f), // DN092WaveSpawner02 0002C987
        new(-2044.53f, -1634.66f, 88.59f), // DN092WaveSpawner03 0003D241
        new(-2054.62f, -1613.32f, 88.15f), // DN092WaveSpawner04 0002C988
        new(-2093.62f, -1668.45f, 88.55f), // DN092WaveSpawner05 0002C989
        new(-2094.59f, -1654.38f, 88.47f), // DN092WaveSpawner06 0003D242
    };

    public static readonly P3Float S8WaveFailsafeMerged = new(-2055.35f, -1646.86f, 91.63f);     // DN092_WavePost02 00023BC5
    public static readonly P3Float S8GrateTriggerMerged = new(-2068.22f, -1640.23f, 88.22f);     // DN092ForceSpawnDeathclawTrigger 0009A144
    public static readonly P3Float S8DeathclawSpawnMerged = new(-2068.22f, -1640.18f, 88.22f);   // ConcordAmbushDeathclaw 0001F15B

    public static bool IsS8ActorRefId(uint id) =>
        id >= FirstS8WaveActorRefId && id < FirstS8WaveActorRefId + (uint)S8WaveActorCount;

    public static bool IsS7S9ObjectRefId(uint id) =>
        id is >= S7RoofMinigunRefId and <= S7RoofDoorMarkerId ||
        id is >= FirstS8WaveSpawnerMarkerId and <= S8DeathclawSpawnMarkerId;

    // Task 1i: S7-S9 places zero objects in WRLD TopCell (all markers + wave ACHRs start in 0xBF5 HoldingCell).
    public static int ExpectedPersistentObjectCount(int baseR11MarkerCount) => baseR11MarkerCount;

    public static SF.ICellGetter? FindHoldingCell(SF.IStarfieldModGetter plug) =>
        plug.Cells.Records
            .SelectMany(b => b.SubBlocks)
            .SelectMany(sb => sb.Cells)
            .FirstOrDefault(c => c.FormKey == new FormKey(plug.ModKey, S7S9HoldingCellId));

    public static SF.Cell? FindHoldingCellMutable(SF.StarfieldMod mod) =>
        mod.Cells.Records
            .SelectMany(b => b.SubBlocks)
            .SelectMany(sb => sb.Cells)
            .FirstOrDefault(c => c.FormKey == new FormKey(mod.ModKey, S7S9HoldingCellId));

    static SF.Cell CreateHoldingCell(SF.StarfieldMod mod, ModKey modKey)
    {
        var cell = new SF.Cell(new FormKey(modKey, S7S9HoldingCellId), SF.StarfieldRelease.Starfield)
        {
            EditorID = S7S9HoldingCellEdid,
            Name = "FO4SF S7-S9 Holding Cell",
            FormVersion = 581,
            Flags = SF.Cell.Flag.IsInteriorCell,
        };
        int blkNum = (int)(S7S9HoldingCellId % 10);
        int subNum = (int)((S7S9HoldingCellId / 10) % 10);
        var blk = mod.Cells.Records.FirstOrDefault(b => b.BlockNumber == blkNum);
        if (blk is null)
        {
            blk = new SF.CellBlock { BlockNumber = blkNum, GroupType = SF.GroupTypeEnum.InteriorCellBlock };
            mod.Cells.Records.Add(blk);
        }
        var sub = blk.SubBlocks.FirstOrDefault(sb => sb.BlockNumber == subNum);
        if (sub is null)
        {
            sub = new SF.CellSubBlock { BlockNumber = subNum, GroupType = SF.GroupTypeEnum.InteriorCellSubBlock };
            blk.SubBlocks.Add(sub);
        }
        sub.Cells.Add(cell);
        return cell;
    }

    static SF.PlacedObject PlacePersistentMarker(
        SF.Cell cell,
        ModKey modKey,
        uint id,
        string edid,
        FormKey baseKey,
        P3Float pos,
        P3Float? rotRad = null,
        bool initiallyDisabled = false)
    {
        var rf = new SF.PlacedObject(new FormKey(modKey, id), SF.StarfieldRelease.Starfield)
        {
            EditorID = edid,
            Base = new FormLinkNullable<SF.IPlaceableObjectGetter>(baseKey),
            Position = pos,
            Rotation = rotRad ?? new P3Float(0, 0, 0),
        };
        rf.MajorRecordFlagsRaw |= 0x400 | (initiallyDisabled ? 0x800 : 0);
        cell.Persistent.Add(rf);
        return rf;
    }

    static Mission.MqVoiceSpec? LoadOptionalS9SubVoice(string? prestonVoicePath, string sectionKey)
    {
        if (string.IsNullOrWhiteSpace(prestonVoicePath) || !File.Exists(prestonVoicePath))
            return null;
        using var doc = JsonDocument.Parse(File.ReadAllText(prestonVoicePath));
        if (!doc.RootElement.TryGetProperty(sectionKey, out var sec) || sec.ValueKind != JsonValueKind.Object)
            return null;
        uint greet = uint.Parse(sec.GetProperty("greeting_wem").GetString()!, NumberStyles.HexNumber, CultureInfo.InvariantCulture);
        var replyWems = sec.GetProperty("reply_wems").EnumerateArray()
            .Select(x => uint.Parse(x.GetString()!, NumberStyles.HexNumber, CultureInfo.InvariantCulture)).ToArray();
        static (uint Wem, float Duration) ParseClip(JsonElement el) => (
            uint.Parse(el.GetProperty("wem").GetString()!, NumberStyles.HexNumber, CultureInfo.InvariantCulture),
            el.TryGetProperty("duration", out var de) && de.ValueKind == JsonValueKind.Number ? de.GetSingle() : 0f
        );
        var gClips = sec.GetProperty("greeting_clips").EnumerateArray().Select(ParseClip).ToArray();
        var rClips = sec.GetProperty("reply_clips").EnumerateArray()
            .Select(arr => arr.EnumerateArray().Select(ParseClip).ToArray()).ToArray();
        return new Mission.MqVoiceSpec(greet, replyWems, gClips, rClips);
    }

    static (string Greet, List<string> GreetTexts, string Prompt, string Reply, List<string> ReplyTexts) ReadS9DialogueMeta(
        JsonElement pts,
        string propName,
        string fallbackGreet,
        string fallbackPrompt,
        string fallbackReply)
    {
        string greet = fallbackGreet;
        var greetTexts = new List<string> { fallbackGreet };
        string prompt = fallbackPrompt;
        string reply = fallbackReply;
        var replyTexts = new List<string> { fallbackReply };
        if (pts.TryGetProperty(propName, out var el) && el.ValueKind == JsonValueKind.Object)
        {
            if (el.TryGetProperty("greeting", out var gEl) && gEl.GetString() is { Length: > 0 } gs) greet = gs;
            greetTexts = Mission.ExtractRespTexts(el, "greeting_responses", greet);
            if (el.TryGetProperty("prompt", out var pEl) && pEl.GetString() is { Length: > 0 } ps) prompt = ps;
            if (el.TryGetProperty("reply", out var rEl) && rEl.GetString() is { Length: > 0 } rs) reply = rs;
            replyTexts = Mission.ExtractRespTexts(el, "reply_responses", reply);
        }
        return (greet, greetTexts, prompt, reply, replyTexts);
    }

    public static void PopulateS7S9(
        SF.StarfieldMod mod,
        SF.Quest min00Quest,
        SF.Quest sanctuaryQuest,
        FormKey xMarkerKey,
        SF.INpcGetter raiderTemplate,
        FormKey combatPackKey,
        FormKey sandboxPackKey,
        FormKey sidearmKey,
        FormKey sidearmAmmoKey,
        FormKey prestonNpcKey,
        FormKey sturgesNpcKey,
        FormKey maleVoiceKey,
        JsonElement pts,
        string? prestonVoicePath)
    {
        var modKey = mod.ModKey;
        var rel = SF.StarfieldRelease.Starfield;
        // Task 1i: dedicated interior holding cell (0xBF5) holds all S7/S8 exterior markers & ACHRs (0 WRLD overrides).
        var holdingCell = CreateHoldingCell(mod, modKey);

        // S7 Vertibird Minigun activator + roof markers (relocated at runtime via 0x005C50/0x0A775B Commonwealth anchor)
        var minigunActi = new SF.Activator(new FormKey(modKey, S7RoofMinigunActiId), rel)
        {
            EditorID = "FO4SF_S7_RoofMinigunActi",
            Name = "Vertibird Minigun",
            ActivateTextOverride = "Take Minigun",
            Model = new SF.Model { File = VertibirdMinigunModel },
            ObjectBounds = new SF.ObjectBounds
            {
                First = new P3Float(-0.45f, -0.45f, -0.45f),
                Second = new P3Float(0.45f, 0.45f, 0.45f),
            },
            Flags = (SF.Activator.Flag)0,
        };
        mod.Activators.Add(minigunActi);

        var deg2rad = MathF.PI / 180f;
        var s7MinigunRef = PlacePersistentMarker(
            holdingCell, modKey, S7RoofMinigunRefId, "FO4SF_S7_RoofMinigunRef", minigunActi.FormKey,
            S7RoofMinigunMerged,
            new P3Float(S7RoofMinigunRotDeg.X * deg2rad, S7RoofMinigunRotDeg.Y * deg2rad, S7RoofMinigunRotDeg.Z * deg2rad),
            initiallyDisabled: true);
        var s7FrameMarker = PlacePersistentMarker(
            holdingCell, modKey, S7RoofFrameMarkerId, "FO4SF_S7_RoofFrameMarker", xMarkerKey,
            S7RoofFrameMerged,
            new P3Float(0f, 0f, S7RoofFrameYawDeg * deg2rad));
        var s7DoorMarker = PlacePersistentMarker(
            holdingCell, modKey, S7RoofDoorMarkerId, "FO4SF_S7_RoofDoorMarker", xMarkerKey,
            S7RoofDoorMerged);

        // S8 Wave 2 NPCs (Gristle + Heavy wave raider)
        SF.Npc CloneWaveNpc(uint id, string edid, string? displayName, bool isUniqueBoss)
        {
            var n = (SF.Npc)raiderTemplate.Duplicate(new FormKey(modKey, id));
            n.EditorID = edid;
            if (!string.IsNullOrEmpty(displayName)) n.Name = displayName;
            n.VirtualMachineAdapter = null;
            n.DefaultTemplate.Clear();
            n.TemplateActors = null;
            n.CrimeFaction.Clear();
            n.ActivateTextOverride = null;
            var flags = (n.Flags | SF.Npc.Flag.AutoCalcStats)
                        & ~(SF.Npc.Flag.Essential | SF.Npc.Flag.Protected | SF.Npc.Flag.Respawn);
            if (isUniqueBoss) flags |= SF.Npc.Flag.Unique;
            else flags &= ~SF.Npc.Flag.Unique;
            n.Flags = flags;
            n.Items ??= new ExtendedList<SF.ContainerEntry>();
            if (!n.Items.Any(i => i.Item.Item.FormKey == sidearmKey))
                n.Items.Add(new SF.ContainerEntry { Item = new SF.ContainerItem { Item = new FormLink<SF.IItemGetter>(sidearmKey), Count = 1 } });
            if (!n.Items.Any(i => i.Item.Item.FormKey == sidearmAmmoKey))
                n.Items.Add(new SF.ContainerEntry { Item = new SF.ContainerItem { Item = new FormLink<SF.IItemGetter>(sidearmAmmoKey), Count = 60 } });
            mod.Npcs.Add(n);
            return n;
        }

        var gristleNpc = CloneWaveNpc(GristleNpcId, "FO4_Gristle", "Gristle", isUniqueBoss: true);
        var heavyNpc = CloneWaveNpc(WaveRaiderHeavyNpcId, "FO4_WaveRaiderHeavy", null, isUniqueBoss: false);

        var waveActors = new List<SF.PlacedNpc>(S8WaveActorCount);
        uint nextAliasId = (uint)((min00Quest.Aliases ?? new ExtendedList<SF.AQuestAlias>()).Count);
        for (int wi = 0; wi < S8WaveInitialSpecs.Length; wi++)
        {
            var spec = S8WaveInitialSpecs[wi];
            FormKey baseKey = spec.Name == "Gristle"
                ? gristleNpc.FormKey
                : (spec.Name == "WaveRaider03" ? heavyNpc.FormKey : raiderTemplate.FormKey);
            var a = new SF.PlacedNpc(new FormKey(modKey, FirstS8WaveActorRefId + (uint)wi), rel)
            {
                EditorID = $"FO4SF_S8_{spec.Name}",
                Base = new FormLink<SF.INpcGetter>(baseKey),
                Position = spec.MergedPos,
                Rotation = new P3Float(0f, 0f, spec.YawDeg * deg2rad),
            };
            a.MajorRecordFlagsRaw |= 0x400 | 0x800; // Persistent | InitiallyDisabled
            holdingCell.Persistent.Add(a);
            waveActors.Add(a);

            min00Quest.Aliases!.Add(new SF.QuestReferenceAlias
            {
                ID = nextAliasId++,
                Name = spec.Name,
                Flags = SF.AQuestAlias.Flag.Optional | SF.AQuestAlias.Flag.AllowReserved |
                        SF.AQuestAlias.Flag.AllowDead | SF.AQuestAlias.Flag.AllowDisabled,
                ForcedReference = new FormLinkNullable<SF.IPlacedGetter>(a.FormKey),
                PackageData =
                {
                    new FormLink<SF.IPackageGetter>(combatPackKey),
                    new FormLink<SF.IPackageGetter>(sandboxPackKey),
                },
            });
        }

        var waveSpawnerMarkers = new List<SF.PlacedObject>(S8WaveSpawnerMergedCoords.Length);
        for (int si = 0; si < S8WaveSpawnerMergedCoords.Length; si++)
        {
            waveSpawnerMarkers.Add(PlacePersistentMarker(
                holdingCell, modKey, FirstS8WaveSpawnerMarkerId + (uint)si,
                $"FO4SF_S8_WaveSpawner{si + 1:D2}", xMarkerKey, S8WaveSpawnerMergedCoords[si]));
        }
        var failsafeMarker = PlacePersistentMarker(
            holdingCell, modKey, S8WaveFailsafeMarkerId, "FO4SF_S8_WavePost02Marker", xMarkerKey, S8WaveFailsafeMerged);
        var grateMarker = PlacePersistentMarker(
            holdingCell, modKey, S8GrateTriggerMarkerId, "FO4SF_S8_GrateTriggerMarker", xMarkerKey, S8GrateTriggerMerged);
        var dcSpawnMarker = PlacePersistentMarker(
            holdingCell, modKey, S8DeathclawSpawnMarkerId, "FO4SF_S8_DeathclawSpawnMarker", xMarkerKey, S8DeathclawSpawnMerged);

        var s9HardStopGlob = new SF.Global(new FormKey(modKey, S9HardStopGlobId), rel)
        {
            EditorID = "FO4SF_S9_HardStopAtMin01_1000",
            Data = 1.0f,
        };
        mod.Globals.Add(s9HardStopGlob);

        // Expand FO4SF_Sanctuary01 flags + stages cleanly for HasDialogueData, stage 20, and stage 220 (Talk to Sturges).
        if (sanctuaryQuest.Data is not null)
        {
            sanctuaryQuest.Data.Flags |= SF.Quest.Flag.HasDialogueData;
        }
        sanctuaryQuest.Stages.Clear();
        foreach (var stIdx in SanctuaryS9Stages)
        {
            var st = new SF.QuestStage { Index = stIdx };
            st.LogEntries.Add(new SF.QuestLogEntry
            {
                Flags = stIdx == 1500 ? SF.QuestLogEntry.Flag.CompleteQuest : (SF.QuestLogEntry.Flag)0,
            });
            sanctuaryQuest.Stages.Add(st);
        }
        if (!sanctuaryQuest.Objectives.Any(o => o.Index == 220))
        {
            var obj220 = new SF.QuestObjective
            {
                Index = 220,
                Flags = (SF.QuestObjective.Flag)0,
                DisplayText = "Talk to Sturges",
            };
            obj220.Targets.Add(new SF.QuestObjectiveTarget { AliasID = 1 });
            sanctuaryQuest.Objectives.Add(obj220);
        }

        // Real Starfield SCEN 0xBF6 (Preston Concord lobby talk) & SCEN 0xBFD (Sanctuary Min01SturgesIntro 001188B4)
        var lobbyMeta = ReadS9DialogueMeta(
            pts, "s9_lobby_talk",
            "Synthetic lobby debrief greeting after Concord cleared.",
            "Ask Preston about heading back to Sanctuary.",
            "Synthetic lobby farewell and supply reward.");
        var lobbyWem = LoadOptionalS9SubVoice(prestonVoicePath, "s9_lobby");
        var lobbyScene = Mission.BuildTopScene(
            modKey, min00Quest, prestonNpcKey, maleVoiceKey,
            Mission.QuestStageCond(min00Quest.FormKey, SF.CompareOperator.EqualTo, 80f),
            S9PrestonLobbySceneId, S9PrestonLobbySceneEdid,
            S9PrestonLobbyGreetTopicId, "FO4SF_S9_PrestonLobbyGreetTopic",
            S9PrestonLobbyGreetInfoId, "FO4SF_S9_PrestonLobbyGreetInfo",
            Mission.PairSceneClips(lobbyMeta.GreetTexts, lobbyWem?.GreetingClips),
            S9PrestonLobbyChoiceTopicId, S9PrestonLobbyChoiceInfoId,
            S9PrestonLobbyReplyTopicId, S9PrestonLobbyReplyInfoId,
            "FO4SF_S9_PrestonLobby", 50f,
            new (string Prompt, IReadOnlyList<(string Text, uint Wem, float Duration)> Replies, short EndStage, bool Goodbye)[]
            {
                (lobbyMeta.Prompt, Mission.PairSceneClips(lobbyMeta.ReplyTexts, lobbyWem?.ReplyClips[0]), (short)-1, true),
            },
            aliasId: 0);

        var sturgesMeta = ReadS9DialogueMeta(
            pts, "s9_sturges_intro",
            "Synthetic Sanctuary arrival greeting from Sturges.",
            "Ask what the Sanctuary settlers need built first.",
            "Synthetic Sturges instructions to build sheltered beds first.");
        var sturgesWem = LoadOptionalS9SubVoice(prestonVoicePath, "s9_sturges");
        var sturgesIntroScene = Mission.BuildTopScene(
            modKey, sanctuaryQuest, sturgesNpcKey, maleVoiceKey,
            Mission.QuestStageCond(sanctuaryQuest.FormKey, SF.CompareOperator.EqualTo, 220f),
            S9SturgesIntroSceneId, S9SturgesIntroSceneEdid,
            S9SturgesIntroGreetTopicId, "FO4SF_S9_SturgesIntroGreetTopic",
            S9SturgesIntroGreetInfoId, "FO4SF_S9_SturgesIntroGreetInfo",
            Mission.PairSceneClips(sturgesMeta.GreetTexts, sturgesWem?.GreetingClips),
            S9SturgesIntroChoiceTopicId, S9SturgesIntroChoiceInfoId,
            S9SturgesIntroReplyTopicId, S9SturgesIntroReplyInfoId,
            "FO4SF_S9_SturgesIntro", 50f,
            new (string Prompt, IReadOnlyList<(string Text, uint Wem, float Duration)> Replies, short EndStage, bool Goodbye)[]
            {
                (sturgesMeta.Prompt, Mission.PairSceneClips(sturgesMeta.ReplyTexts, sturgesWem?.ReplyClips[0]), (short)-1, true),
            },
            aliasId: 1);

        // Explicit TalkUseMessageBox != 0 test fallback MessageBoxes only (never shown when TalkUseMessageBox == 0)
        var lobbyFbMsg = new SF.Message(new FormKey(modKey, S9PrestonLobbyFallbackMsgId), rel)
        {
            EditorID = "FO4SF_S9_PrestonLobbyFallbackMsg",
            Name = "Preston Garvey",
            Description = lobbyMeta.Greet,
            Flags = SF.Message.Flag.MessageBox,
            MenuButtons = { new SF.MessageButton { Text = Mission.ShortButtonText(lobbyMeta.Prompt) } },
        };
        mod.Messages.Add(lobbyFbMsg);

        var sturgesFbMsg = new SF.Message(new FormKey(modKey, S9SturgesIntroFallbackMsgId), rel)
        {
            EditorID = "FO4SF_S9_SturgesIntroFallbackMsg",
            Name = "Sturges",
            Description = sturgesMeta.Greet,
            Flags = SF.Message.Flag.MessageBox,
            MenuButtons = { new SF.MessageButton { Text = Mission.ShortButtonText(sturgesMeta.Prompt) } },
        };
        mod.Messages.Add(sturgesFbMsg);

        static SF.ScriptObjectProperty MakeObjProp(string name, FormKey fk) => new()
        {
            Name = name,
            Flags = SF.ScriptProperty.Flag.Edited,
            Object = new FormLink<SF.IStarfieldMajorRecordGetter>(fk),
            Alias = -1,
            Unused = 0,
        };
        static void SetObj(SF.ScriptEntry entry, string name, FormKey fk)
        {
            entry.Properties.RemoveAll(p => p.Name == name);
            entry.Properties.Add(MakeObjProp(name, fk));
        }

        // Bind S7-S9 properties on FO4SF_Min00Quest
        var min00Script = min00Quest.VirtualMachineAdapter?.Scripts.FirstOrDefault(s => s.Name == ScriptName);
        if (min00Script is not null)
        {
            void SetIntProp(string name, int val)
            {
                min00Script.Properties.RemoveAll(p => p.Name == name);
                min00Script.Properties.Add(new SF.ScriptIntProperty { Name = name, Flags = SF.ScriptProperty.Flag.Edited, Data = val });
            }
            SetIntProp("LaserMusketId", CoreLaserMusketId);
            SetIntProp("FusionCellId", CoreFusionCellId);
            SetIntProp("Ammo5mmId", CoreAmmo5mmId);
            SetIntProp("MinigunId", CoreMinigunId);
            SetIntProp("BottlecapId", CoreBottlecapId);

            SetObj(min00Script, "S7RoofMinigunRef", s7MinigunRef.FormKey);
            SetObj(min00Script, "S7RoofFrameMarker", s7FrameMarker.FormKey);
            SetObj(min00Script, "S7RoofDoorMarker", s7DoorMarker.FormKey);

            var actorList = new SF.ScriptObjectListProperty { Name = "S8WaveActors", Flags = SF.ScriptProperty.Flag.Edited };
            foreach (var wa in waveActors) actorList.Objects.Add(MakeObjProp("", wa.FormKey));
            min00Script.Properties.RemoveAll(p => p.Name == "S8WaveActors");
            min00Script.Properties.Add(actorList);

            var spList = new SF.ScriptObjectListProperty { Name = "S8WaveSpawners", Flags = SF.ScriptProperty.Flag.Edited };
            foreach (var sp in waveSpawnerMarkers) spList.Objects.Add(MakeObjProp("", sp.FormKey));
            min00Script.Properties.RemoveAll(p => p.Name == "S8WaveSpawners");
            min00Script.Properties.Add(spList);

            SetObj(min00Script, "S8WaveFailsafeMarker", failsafeMarker.FormKey);
            SetObj(min00Script, "S8GrateTriggerMarker", grateMarker.FormKey);
            SetObj(min00Script, "S8DeathclawSpawnMarker", dcSpawnMarker.FormKey);
            SetObj(min00Script, "S9PrestonLobbyScene", lobbyScene.FormKey);
            SetObj(min00Script, "S9PrestonLobbyFallbackMsg", lobbyFbMsg.FormKey);

            // Preserve S6 MinutemenGroup members (Sturges, MamaMurphy, MarcyLong, JunLong) and ensure Sturges (0xA01) is present.
            var existingMm = min00Script.Properties.OfType<SF.ScriptObjectListProperty>()
                .FirstOrDefault(p => p.Name == "MinutemenGroup");
            var sturgesFk = new FormKey(modKey, NextStoryMissionsA4.SturgesRefId);
            if (existingMm is null)
            {
                var mmGroup = new SF.ScriptObjectListProperty { Name = "MinutemenGroup", Flags = SF.ScriptProperty.Flag.Edited };
                mmGroup.Objects.Add(MakeObjProp("", sturgesFk));
                min00Script.Properties.RemoveAll(p => p.Name == "MinutemenGroup");
                min00Script.Properties.Add(mmGroup);
            }
            else if (!existingMm.Objects.Any(o => o.Object.FormKey == sturgesFk))
            {
                existingMm.Objects.Add(MakeObjProp("", sturgesFk));
            }
            // S7-S9 stacked build continues past S6 Fusion Core pickup into Concord roof PA -> Wave 2 -> Sanctuary walk home.
            min00Script.Properties.RemoveAll(p => p.Name == "StopAtFusionCorePowerArmor");
            min00Script.Properties.Add(new SF.ScriptBoolProperty
            {
                Name = "StopAtFusionCorePowerArmor",
                Flags = SF.ScriptProperty.Flag.Edited,
                Data = false,
            });
        }

        // Bind S9 Sturges intro Starfield SCEN & TalkUseMessageBox onto FO4SF_Sanctuary01Quest
        var sancScript = sanctuaryQuest.VirtualMachineAdapter?.Scripts.FirstOrDefault(s => s.Name == SanctuaryScriptName);
        if (sancScript is not null)
        {
            SetObj(sancScript, "S9SturgesIntroScene", sturgesIntroScene.FormKey);
            SetObj(sancScript, "S9SturgesIntroFallbackMsg", sturgesFbMsg.FormKey);
            SetObj(sancScript, "TalkUseMessageBox", new FormKey(modKey, Mission.MissionTalkUseMessageBoxGlobId));
        }
    }

    public static void CheckS7S9(
        SF.IStarfieldModGetter plug,
        ModKey sfEsm,
        uint xMarkerId,
        Action<bool, string> need)
    {
        var key = plug.ModKey;
        var worldMarkers = plug.Worldspaces.FirstOrDefault()?.TopCell?.Persistent.OfType<SF.IPlacedObjectGetter>().ToList() ?? new();
        var worldNpcs = plug.Worldspaces.FirstOrDefault()?.TopCell?.Persistent.OfType<SF.IPlacedNpcGetter>().ToList() ?? new();
        need(!worldMarkers.Any(m => IsS7S9ObjectRefId(m.FormKey.ID)) && !worldNpcs.Any(r => IsS8ActorRefId(r.FormKey.ID)),
            "Task 1i: S7-S9 exterior markers and wave ACHRs must live in FO4SF_S7S9_HoldingCell (0xBF5), never FO4Core_Commonwealth WRLD");

        var hc = FindHoldingCell(plug);
        need(hc is { EditorID: S7S9HoldingCellEdid } && (hc.Flags ?? 0).HasFlag(SF.Cell.Flag.IsInteriorCell),
            $"Task 1i: holding cell 0x{S7S9HoldingCellId:X} ({S7S9HoldingCellEdid}) missing or lacks IsInteriorCell");
        var markers = hc?.Persistent.OfType<SF.IPlacedObjectGetter>().ToList() ?? new();
        var npcs = hc?.Persistent.OfType<SF.IPlacedNpcGetter>().ToList() ?? new();

        need(plug.Activators.Any(a => a.FormKey.ID == S7RoofMinigunActiId && a.Model?.File == VertibirdMinigunModel),
            "S7 lacks FO4SF_S7_RoofMinigunActi (0xBE0) with vertibirdminigun.nif");
        need(markers.Any(x => x.FormKey.ID == S7RoofMinigunRefId && (x.MajorRecordFlagsRaw & 0xC00u) == 0xC00u),
            "S7 lacks InitiallyDisabled Persistent FO4SF_S7_RoofMinigunRef (0xBE1) in holding cell");
        need(markers.Any(x => x.FormKey.ID == S7RoofFrameMarkerId && (x.MajorRecordFlagsRaw & 0x400u) != 0),
            "S7 lacks Persistent FO4SF_S7_RoofFrameMarker (0xBE2) in holding cell");
        need(markers.Any(x => x.FormKey.ID == S7RoofDoorMarkerId && (x.MajorRecordFlagsRaw & 0x400u) != 0),
            "S7 lacks Persistent FO4SF_S7_RoofDoorMarker (0xBE3) in holding cell");

        var gristle = plug.Npcs.FirstOrDefault(n => n.FormKey.ID == GristleNpcId);
        var heavy = plug.Npcs.FirstOrDefault(n => n.FormKey.ID == WaveRaiderHeavyNpcId);
        need(gristle?.Name?.String == "Gristle" &&
             !gristle.Flags.HasFlag(SF.Npc.Flag.Essential) &&
             !gristle.Flags.HasFlag(SF.Npc.Flag.Protected) &&
             !gristle.Flags.HasFlag(SF.Npc.Flag.Respawn),
            "S8 lacks non-essential non-respawning NPC_ FO4_Gristle (0xBE4) named 'Gristle'");
        need(heavy?.EditorID == "FO4_WaveRaiderHeavy" &&
             !heavy.Flags.HasFlag(SF.Npc.Flag.Essential) &&
             !heavy.Flags.HasFlag(SF.Npc.Flag.Protected) &&
             !heavy.Flags.HasFlag(SF.Npc.Flag.Respawn),
            "S8 lacks non-essential non-respawning NPC_ FO4_WaveRaiderHeavy (0xBE5)");
        for (int wi = 0; wi < S8WaveActorCount; wi++)
        {
            uint aid = FirstS8WaveActorRefId + (uint)wi;
            var spec = S8WaveInitialSpecs[wi];
            var wa = npcs.FirstOrDefault(r => r.FormKey.ID == aid);
            need(wa is not null && (wa.MajorRecordFlagsRaw & 0xC00u) == 0xC00u &&
                 MathF.Abs(wa.Position.X - spec.MergedPos.X) <= 0.1f &&
                 MathF.Abs(wa.Position.Y - spec.MergedPos.Y) <= 0.1f,
                $"S8 wave actor ACHR 0x{aid:X} missing from holding cell or coordinates do not match S8WaveInitialSpecs ({spec.MergedPos.X}, {spec.MergedPos.Y})");
        }
        for (int si = 0; si < S8WaveSpawnerMergedCoords.Length; si++)
        {
            uint spId = FirstS8WaveSpawnerMarkerId + (uint)si;
            need(markers.Any(m => m.FormKey.ID == spId &&
                                  m.EditorID == $"FO4SF_S8_WaveSpawner{si + 1:D2}" &&
                                  m.Base.FormKey == new FormKey(sfEsm, xMarkerId) &&
                                  (m.MajorRecordFlagsRaw & 0x400u) != 0),
                $"S8 lacks Persistent WaveSpawner{si + 1:D2} marker 0x{spId:X} in holding cell");
        }
        need(markers.Any(m => m.FormKey.ID == S8WaveFailsafeMarkerId && (m.MajorRecordFlagsRaw & 0x400u) != 0),
            "S8 lacks Persistent S8WaveFailsafeMarker (0xBF1) in holding cell");
        need(markers.Any(m => m.FormKey.ID == S8GrateTriggerMarkerId && (m.MajorRecordFlagsRaw & 0x400u) != 0),
            "S8 lacks Persistent S8GrateTriggerMarker (0xBF2) in holding cell");
        need(markers.Any(m => m.FormKey.ID == S8DeathclawSpawnMarkerId && (m.MajorRecordFlagsRaw & 0x400u) != 0),
            "S8 lacks Persistent S8DeathclawSpawnMarker (0xBF3) in holding cell");

        var min00 = plug.Quests.First(q => q.FormKey.ID == 0x800);
        need(min00.Objectives.Any(o => o.Index == 65 && o.DisplayText?.String == "Clear Concord of Hostiles"),
            "S8 lacks FO4SF_Min00 objective 65 'Clear Concord of Hostiles'");
        foreach (var (name, _, _, _) in S8WaveInitialSpecs)
        {
            need((min00.Aliases ?? Array.Empty<SF.IAQuestAliasGetter>()).OfType<SF.IQuestReferenceAliasGetter>().Any(a => a.Name == name),
                $"S8 lacks wave QuestReferenceAlias '{name}' on FO4SF_Min00");
        }
        var min00Sc = min00.VirtualMachineAdapter?.Scripts.FirstOrDefault(s => s.Name == ScriptName);
        var props = min00Sc?.Properties.ToDictionary(p => p.Name) ?? new Dictionary<string, SF.IScriptPropertyGetter>();
        need(props.TryGetValue("MinigunId", out var mgp) && mgp is SF.IScriptIntPropertyGetter mgi && mgi.Data == CoreMinigunId &&
             props.TryGetValue("Ammo5mmId", out var a5p) && a5p is SF.IScriptIntPropertyGetter a5i && a5i.Data == CoreAmmo5mmId &&
             props.TryGetValue("BottlecapId", out var bcp) && bcp is SF.IScriptIntPropertyGetter bci && bci.Data == CoreBottlecapId &&
             props.TryGetValue("FusionCellId", out var fcp) && fcp is SF.IScriptIntPropertyGetter fci && fci.Data == CoreFusionCellId &&
             props.TryGetValue("LaserMusketId", out var lmp) && lmp is SF.IScriptIntPropertyGetter lmi && lmi.Data == CoreLaserMusketId,
            "S7-S9 lacks CoreValues FormID int properties on FO4SF_Min00");
        need(props.TryGetValue("S7RoofMinigunRef", out var rm) && rm is SF.IScriptObjectPropertyGetter rmo && rmo.Object.FormKey == new FormKey(key, S7RoofMinigunRefId) &&
             props.TryGetValue("S7RoofFrameMarker", out var rf) && rf is SF.IScriptObjectPropertyGetter rfo && rfo.Object.FormKey == new FormKey(key, S7RoofFrameMarkerId) &&
             props.TryGetValue("S7RoofDoorMarker", out var rd) && rd is SF.IScriptObjectPropertyGetter rdo && rdo.Object.FormKey == new FormKey(key, S7RoofDoorMarkerId),
            "S7 lacks S7RoofMinigunRef / S7RoofFrameMarker / S7RoofDoorMarker bindings on FO4SF_Min00");
        need(props.TryGetValue("S8WaveActors", out var wap) && wap is SF.IScriptObjectListPropertyGetter wal && wal.Objects.Count == S8WaveActorCount &&
             props.TryGetValue("S8WaveSpawners", out var wsp) && wsp is SF.IScriptObjectListPropertyGetter wsl && wsl.Objects.Count == S8WaveSpawnerMergedCoords.Length &&
             props.TryGetValue("S8WaveFailsafeMarker", out _) && props.TryGetValue("S8GrateTriggerMarker", out _) && props.TryGetValue("S8DeathclawSpawnMarker", out _),
            "S8 lacks wave actor/spawner/trigger VMAD bindings on FO4SF_Min00");
        need(props.TryGetValue("S9PrestonLobbyScene", out var lsc) && lsc is SF.IScriptObjectPropertyGetter lsco && lsco.Object.FormKey == new FormKey(key, S9PrestonLobbySceneId) &&
             props.TryGetValue("S9PrestonLobbyFallbackMsg", out var lfm) && lfm is SF.IScriptObjectPropertyGetter lfmo && lfmo.Object.FormKey == new FormKey(key, S9PrestonLobbyFallbackMsgId),
            "S9 lacks S9PrestonLobbyScene (0xBF6) or S9PrestonLobbyFallbackMsg (0xC04) bindings on FO4SF_Min00");

        var lobbyScn = min00.Scenes.FirstOrDefault(s => s.FormKey.ID == S9PrestonLobbySceneId);
        need(lobbyScn is { DEVT: true, SCPI: null } && (uint)(lobbyScn.Flags ?? 0) == 0x1814u &&
             lobbyScn.Actors.Count == 1 && lobbyScn.Actors[0].ID == 0,
            "S9 lacks real DEVT Starfield SCEN FO4SF_S9_PrestonLobbyScene (0xBF6) on FO4SF_Min00");

        var sanc = plug.Quests.FirstOrDefault(q => q.FormKey.ID == NextStoryMissionsA4.SanctuaryQuestId);
        need(sanc?.Data is not null && sanc.Data.Flags.HasFlag(SF.Quest.Flag.HasDialogueData),
            "S9: FO4SF_Sanctuary01 (0x817) lacks HasDialogueData flag for Min01SturgesIntro Starfield SCEN");
        var sturgesScn = sanc?.Scenes.FirstOrDefault(s => s.FormKey.ID == S9SturgesIntroSceneId);
        need(sturgesScn is { DEVT: true, SCPI: null } && (uint)(sturgesScn.Flags ?? 0) == 0x1814u &&
             sturgesScn.Actors.Count == 1 && sturgesScn.Actors[0].ID == 1,
            "S9 lacks real DEVT Starfield SCEN FO4SF_S9_SturgesIntroScene (0xBFD, AliasID=1) on FO4SF_Sanctuary01");
        var sancSc = sanc?.VirtualMachineAdapter?.Scripts.FirstOrDefault(s => s.Name == SanctuaryScriptName);
        var sancProps = sancSc?.Properties.ToDictionary(p => p.Name) ?? new Dictionary<string, SF.IScriptPropertyGetter>();
        need(sancProps.TryGetValue("S9SturgesIntroScene", out var ssc) && ssc is SF.IScriptObjectPropertyGetter ssco && ssco.Object.FormKey == new FormKey(key, S9SturgesIntroSceneId) &&
             sancProps.TryGetValue("S9SturgesIntroFallbackMsg", out var sfm) && sfm is SF.IScriptObjectPropertyGetter sfmo && sfmo.Object.FormKey == new FormKey(key, S9SturgesIntroFallbackMsgId) &&
             sancProps.TryGetValue("TalkUseMessageBox", out var stg) && stg is SF.IScriptObjectPropertyGetter stgo && stgo.Object.FormKey == new FormKey(key, Mission.MissionTalkUseMessageBoxGlobId),
            "S9 lacks S9SturgesIntroScene (0xBFD) / S9SturgesIntroFallbackMsg (0xC05) / TalkUseMessageBox bindings on FO4SF_Sanctuary01");

        need(!plug.Messages.Any(m => m.EditorID == "FO4SF_S9_SturgesIntroMsg"),
            "S9 must not emit standalone FO4SF_S9_SturgesIntroMsg replacing Starfield SCEN");
        need(plug.Globals.FirstOrDefault(g => g.FormKey.ID == S9HardStopGlobId)?.Data == 1.0f,
            "S9 lacks FO4SF_S9_HardStopAtMin01_1000 == 1.0 (0xBF4)");
    }
}
