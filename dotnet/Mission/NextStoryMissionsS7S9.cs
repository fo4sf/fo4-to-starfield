// NextStoryMissionsS7S9: S7 Roof Power Armor + Minigun, S8 Concord Wave 2 (respawnPool=8) + Deathclaw,
// and S9 Museum Lobby -> DialogueConcordArea 50 -> Min01 20 -> Min00 100 -> Red Rocket walk -> Min01 220/1000 hard stop.
//
// Reserved local FormIDs strictly in 0xBE0..0xBF5 (inside A5's 0x800..0xBFF window; zero overlap with
// 0x800..0x9FF base/looks, 0xA00..0xB56 A4/A7/A7cd, 0xB60 holding cell, 0xB80..0xB8B Step 3q, or 0xB8C..0xBDC S2-S6):
//   S7 Roof:
//     0xBE0  ACTI  FO4SF_S7_RoofMinigunActi      (Vertibird Minigun 0001F582/0001F583 stand-in world activator)
//     0xBE1  REFR  FO4SF_S7_RoofMinigunRef       (persistent, InitiallyDisabled, relocated to (-2004.72, -1715.40, 102.68))
//     0xBE2  REFR  FO4SF_S7_RoofFrameMarker      (persistent XMarker at (-1995.73, -1723.10, 97.54), rotZ=351.07 deg)
//     0xBE3  REFR  FO4SF_S7_RoofDoorMarker       (persistent XMarker at (-2008.49, -1722.39, 97.42))
//   S8 Wave 2 & Deathclaw:
//     0xBE4  NPC_  FO4_Gristle                   ("Gristle" 00019567 / 0001F68C boss, non-essential, non-respawning)
//     0xBE5  NPC_  FO4_WaveRaiderHeavy           (LvlRaider_Handmade_MG 0007B620 automatic wave raider)
//     0xBE6  ACHR  FO4SF_S8_WaveRaider01         (at DN092_AlleyNearMarker 00023F0B, respawns across Pool=8)
//     0xBE7  ACHR  FO4SF_S8_WaveRaider02         (at RaiderSpawnerMarker02 0001F15D, respawns across Pool=8)
//     0xBE8  ACHR  FO4SF_S8_WaveRaider03         (FO4_WaveRaiderHeavy at TestDeathclawAmbushExitPoint 0002C96B, respawns)
//     0xBE9  ACHR  FO4SF_S8_RoofLookout          (at RaiderSpawnerMarkerRooftop 00023EFA, stays dead)
//     0xBEA  ACHR  FO4SF_S8_Gristle              (FO4_Gristle at 0002C96B, stays dead)
//     0xBEB..0xBF0  REFR  FO4SF_S8_WaveSpawner01..06  (DN092WaveSpawner01..06: 00029BCD..0003D242)
//     0xBF1  REFR  FO4SF_S8_WaveFailsafeMarker   (DN092_WavePost02 00023BC5 failsafe)
//     0xBF2  REFR  FO4SF_S8_GrateTriggerMarker   (DN092ForceSpawnDeathclawTrigger 0009A144, <=17m trigger)
//     0xBF3  REFR  FO4SF_S8_DeathclawSpawnMarker (ConcordAmbushDeathclaw 0001F15B / 0002C969 (-2068.22,-1640.18,88.22))
//   S9 Sturges Intro & Hard Stop:
//     0xBF4  MESG  FO4SF_S9_SturgesIntroMsg      (Min01SturgesIntro 001188B4 intro talk before Min01 1000)
//     0xBF5  GLOB  FO4SF_S9_HardStopAtMin01_1000 (1.0: holds MinRecruit00 & MQ103 off at Min01 1000)

using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Records;
using Noggog;
using SF = Mutagen.Bethesda.Starfield;

static class NextStoryMissionsS7S9
{
    public const string Plugin = "FO4SFMission.esm";
    public const string ScriptName = "FO4SF_Min00Quest";

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

    public const uint S9SturgesIntroMsgId = 0xBF4;
    public const uint S9HardStopGlobId = 0xBF5;
    public const uint MaxAllocatedId = 0xBF6;

    public const float MergeOffsetX = -1200.0f;
    public const float MergeOffsetY = -2700.0f;

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

    // Merged Commonwealth coordinates verified from Fallout4.esm:
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

    public static int ExpectedPersistentObjectCount(int baseR11MarkerCount) =>
        baseR11MarkerCount + 3 + S8WaveSpawnerMergedCoords.Length + 3; // S7(Minigun,FrameMk,DoorMk) + 6 WaveSpawners + Failsafe + Grate + Deathclaw

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

    public static void PopulateS7S9(
        SF.StarfieldMod mod,
        SF.Cell persistentCell,
        SF.Quest min00Quest,
        SF.Quest sanctuaryQuest,
        FormKey xMarkerKey,
        SF.INpcGetter raiderTemplate,
        FormKey combatPackKey,
        FormKey sandboxPackKey,
        FormKey sidearmKey,
        FormKey sidearmAmmoKey)
    {
        var modKey = mod.ModKey;
        var rel = SF.StarfieldRelease.Starfield;

        // S7 Vertibird Minigun activator + roof markers
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
            persistentCell, modKey, S7RoofMinigunRefId, "FO4SF_S7_RoofMinigunRef", minigunActi.FormKey,
            S7RoofMinigunMerged,
            new P3Float(S7RoofMinigunRotDeg.X * deg2rad, S7RoofMinigunRotDeg.Y * deg2rad, S7RoofMinigunRotDeg.Z * deg2rad),
            initiallyDisabled: true);
        var s7FrameMarker = PlacePersistentMarker(
            persistentCell, modKey, S7RoofFrameMarkerId, "FO4SF_S7_RoofFrameMarker", xMarkerKey,
            S7RoofFrameMerged,
            new P3Float(0f, 0f, S7RoofFrameYawDeg * deg2rad));
        var s7DoorMarker = PlacePersistentMarker(
            persistentCell, modKey, S7RoofDoorMarkerId, "FO4SF_S7_RoofDoorMarker", xMarkerKey,
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
                Position = new P3Float(spec.MergedPos.X - MergeOffsetX, spec.MergedPos.Y - MergeOffsetY, spec.MergedPos.Z),
                Rotation = new P3Float(0f, 0f, spec.YawDeg * deg2rad),
            };
            a.MajorRecordFlagsRaw |= 0x400 | 0x800; // Persistent | InitiallyDisabled
            persistentCell.Persistent.Add(a);
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
                persistentCell, modKey, FirstS8WaveSpawnerMarkerId + (uint)si,
                $"FO4SF_S8_WaveSpawner{si + 1:D2}", xMarkerKey, S8WaveSpawnerMergedCoords[si]));
        }
        var failsafeMarker = PlacePersistentMarker(
            persistentCell, modKey, S8WaveFailsafeMarkerId, "FO4SF_S8_WavePost02Marker", xMarkerKey, S8WaveFailsafeMerged);
        var grateMarker = PlacePersistentMarker(
            persistentCell, modKey, S8GrateTriggerMarkerId, "FO4SF_S8_GrateTriggerMarker", xMarkerKey, S8GrateTriggerMerged);
        var dcSpawnMarker = PlacePersistentMarker(
            persistentCell, modKey, S8DeathclawSpawnMarkerId, "FO4SF_S8_DeathclawSpawnMarker", xMarkerKey, S8DeathclawSpawnMerged);

        // S9 Min01SturgesIntro (001188B4) clean-room talk box & S9 Min01 1000 hard-stop flag
        var s9SturgesIntro = new SF.Message(new FormKey(modKey, S9SturgesIntroMsgId), rel)
        {
            EditorID = "FO4SF_S9_SturgesIntroMsg",
            Name = "Sturges",
            Description = "Everybody is settling in at Sanctuary after Concord. We need sheltered beds up first before anything else.",
            Flags = SF.Message.Flag.MessageBox,
            MenuButtons =
            {
                new SF.MessageButton { Text = "Ask what settlers need first" },
                new SF.MessageButton { Text = "Ask about Sanctuary defenses" },
                new SF.MessageButton { Text = "I'll build the sheltered beds" },
            },
        };
        mod.Messages.Add(s9SturgesIntro);

        var s9HardStopGlob = new SF.Global(new FormKey(modKey, S9HardStopGlobId), rel)
        {
            EditorID = "FO4SF_S9_HardStopAtMin01_1000",
            Data = 1.0f,
        };
        mod.Globals.Add(s9HardStopGlob);

        // Expand FO4SF_Sanctuary01 stages cleanly to include 20 (DialogueConcordArea -> Min01 20 > Min00 100) and 220 (arrival -> Sturges talk)
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

        // Bind S7-S9 properties on FO4SF_Min00Quest
        var min00Script = min00Quest.VirtualMachineAdapter?.Scripts.FirstOrDefault(s => s.Name == "FO4SF_Min00Quest");
        if (min00Script is not null)
        {
            SF.ScriptObjectProperty MakeObjProp(string name, FormKey fk) => new()
            {
                Name = name,
                Flags = SF.ScriptProperty.Flag.Edited,
                Object = new FormLink<SF.IStarfieldMajorRecordGetter>(fk),
                Alias = -1,
                Unused = 0,
            };
            void SetIntProp(string name, int val)
            {
                min00Script.Properties.RemoveAll(p => p.Name == name);
                min00Script.Properties.Add(new SF.ScriptIntProperty { Name = name, Flags = SF.ScriptProperty.Flag.Edited, Data = val });
            }
            void SetObj(string name, FormKey fk)
            {
                min00Script.Properties.RemoveAll(p => p.Name == name);
                min00Script.Properties.Add(MakeObjProp(name, fk));
            }
            SetIntProp("LaserMusketId", CoreLaserMusketId);
            SetIntProp("FusionCellId", CoreFusionCellId);
            SetIntProp("Ammo5mmId", CoreAmmo5mmId);
            SetIntProp("MinigunId", CoreMinigunId);
            SetIntProp("BottlecapId", CoreBottlecapId);

            SetObj("S7RoofMinigunRef", s7MinigunRef.FormKey);
            SetObj("S7RoofFrameMarker", s7FrameMarker.FormKey);
            SetObj("S7RoofDoorMarker", s7DoorMarker.FormKey);

            var actorList = new SF.ScriptObjectListProperty { Name = "S8WaveActors", Flags = SF.ScriptProperty.Flag.Edited };
            foreach (var wa in waveActors) actorList.Objects.Add(MakeObjProp("", wa.FormKey));
            min00Script.Properties.RemoveAll(p => p.Name == "S8WaveActors");
            min00Script.Properties.Add(actorList);

            var spList = new SF.ScriptObjectListProperty { Name = "S8WaveSpawners", Flags = SF.ScriptProperty.Flag.Edited };
            foreach (var sp in waveSpawnerMarkers) spList.Objects.Add(MakeObjProp("", sp.FormKey));
            min00Script.Properties.RemoveAll(p => p.Name == "S8WaveSpawners");
            min00Script.Properties.Add(spList);

            SetObj("S8WaveFailsafeMarker", failsafeMarker.FormKey);
            SetObj("S8GrateTriggerMarker", grateMarker.FormKey);
            SetObj("S8DeathclawSpawnMarker", dcSpawnMarker.FormKey);

            // Bind Sturges (0xA01) in MinutemenGroup so S9 moves & walks Preston + Minutemen party together
            var mmGroup = new SF.ScriptObjectListProperty { Name = "MinutemenGroup", Flags = SF.ScriptProperty.Flag.Edited };
            mmGroup.Objects.Add(MakeObjProp("", new FormKey(modKey, NextStoryMissionsA4.SturgesRefId)));
            min00Script.Properties.RemoveAll(p => p.Name == "MinutemenGroup");
            min00Script.Properties.Add(mmGroup);
        }
    }

    public static void CheckS7S9(
        SF.IStarfieldModGetter plug,
        ModKey sfEsm,
        uint xMarkerId,
        Action<bool, string> need)
    {
        var key = plug.ModKey;
        var cell = plug.Worldspaces.First().TopCell!;
        var markers = cell.Persistent.OfType<SF.IPlacedObjectGetter>().ToList();
        var npcs = cell.Persistent.OfType<SF.IPlacedNpcGetter>().ToList();

        need(plug.Activators.Any(a => a.FormKey.ID == S7RoofMinigunActiId && a.Model?.File == VertibirdMinigunModel),
            "S7 lacks FO4SF_S7_RoofMinigunActi (0xBE0) with vertibirdminigun.nif");
        need(markers.Any(x => x.FormKey.ID == S7RoofMinigunRefId && (x.MajorRecordFlagsRaw & 0xC00u) == 0xC00u),
            "S7 lacks InitiallyDisabled Persistent FO4SF_S7_RoofMinigunRef (0xBE1)");
        need(markers.Any(x => x.FormKey.ID == S7RoofFrameMarkerId && (x.MajorRecordFlagsRaw & 0x400u) != 0),
            "S7 lacks Persistent FO4SF_S7_RoofFrameMarker (0xBE2)");
        need(markers.Any(x => x.FormKey.ID == S7RoofDoorMarkerId && (x.MajorRecordFlagsRaw & 0x400u) != 0),
            "S7 lacks Persistent FO4SF_S7_RoofDoorMarker (0xBE3)");

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
            need(npcs.Any(r => r.FormKey.ID == aid && (r.MajorRecordFlagsRaw & 0xC00u) == 0xC00u),
                $"S8 lacks Persistent InitiallyDisabled wave actor ACHR 0x{aid:X}");
        }
        for (int si = 0; si < S8WaveSpawnerMergedCoords.Length; si++)
        {
            uint spId = FirstS8WaveSpawnerMarkerId + (uint)si;
            need(markers.Any(m => m.FormKey.ID == spId &&
                                  m.EditorID == $"FO4SF_S8_WaveSpawner{si + 1:D2}" &&
                                  m.Base.FormKey == new FormKey(sfEsm, xMarkerId) &&
                                  (m.MajorRecordFlagsRaw & 0x400u) != 0),
                $"S8 lacks Persistent WaveSpawner{si + 1:D2} marker 0x{spId:X}");
        }
        need(markers.Any(m => m.FormKey.ID == S8WaveFailsafeMarkerId && (m.MajorRecordFlagsRaw & 0x400u) != 0),
            "S8 lacks Persistent S8WaveFailsafeMarker (0xBF1)");
        need(markers.Any(m => m.FormKey.ID == S8GrateTriggerMarkerId && (m.MajorRecordFlagsRaw & 0x400u) != 0),
            "S8 lacks Persistent S8GrateTriggerMarker (0xBF2)");
        need(markers.Any(m => m.FormKey.ID == S8DeathclawSpawnMarkerId && (m.MajorRecordFlagsRaw & 0x400u) != 0),
            "S8 lacks Persistent S8DeathclawSpawnMarker (0xBF3)");

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
            "S7-S9 lacks CoreValues FormID int properties (MinigunId/Ammo5mmId/BottlecapId/FusionCellId/LaserMusketId) on FO4SF_Min00");
        need(props.TryGetValue("S7RoofMinigunRef", out var rm) && rm is SF.IScriptObjectPropertyGetter rmo && rmo.Object.FormKey == new FormKey(key, S7RoofMinigunRefId) &&
             props.TryGetValue("S7RoofFrameMarker", out var rf) && rf is SF.IScriptObjectPropertyGetter rfo && rfo.Object.FormKey == new FormKey(key, S7RoofFrameMarkerId) &&
             props.TryGetValue("S7RoofDoorMarker", out var rd) && rd is SF.IScriptObjectPropertyGetter rdo && rdo.Object.FormKey == new FormKey(key, S7RoofDoorMarkerId),
            "S7 lacks S7RoofMinigunRef / S7RoofFrameMarker / S7RoofDoorMarker bindings on FO4SF_Min00");
        need(props.TryGetValue("S8WaveActors", out var wap) && wap is SF.IScriptObjectListPropertyGetter wal && wal.Objects.Count == S8WaveActorCount &&
             props.TryGetValue("S8WaveSpawners", out var wsp) && wsp is SF.IScriptObjectListPropertyGetter wsl && wsl.Objects.Count == S8WaveSpawnerMergedCoords.Length &&
             props.TryGetValue("S8WaveFailsafeMarker", out _) && props.TryGetValue("S8GrateTriggerMarker", out _) && props.TryGetValue("S8DeathclawSpawnMarker", out _),
            "S8 lacks wave actor/spawner/trigger VMAD bindings on FO4SF_Min00");

        need(plug.Messages.Any(m => m.FormKey.ID == S9SturgesIntroMsgId && m.EditorID == "FO4SF_S9_SturgesIntroMsg"),
            "S9 lacks FO4SF_S9_SturgesIntroMsg (0xBF4)");
        need(plug.Globals.FirstOrDefault(g => g.FormKey.ID == S9HardStopGlobId)?.Data == 1.0f,
            "S9 lacks FO4SF_S9_HardStopAtMin01_1000 == 1.0 (0xBF5)");
    }
}
