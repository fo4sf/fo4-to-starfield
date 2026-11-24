// NextStoryMissionsS2S6: Full R12 S2-S6 story progression & Museum interior wiring for FO4SFMission.esm (strictly 0xB8C..0xBDD).
// Only emitted under --r11-full-mission 1 (default 0 preserves candidate-2g-fix2 parity 100%).
// Covers:
//   - S2 (0xB90..0xB95): FO4SF_Vault111Roaches stage-gated Vault 111 LvlRadRoachAmbush placements w/ Task 1b gate + creature_slot=empty fallback
//   - S3 (0xB96..0xBA6): Codsworth PACK 0019E138/0019E144 (DefaultTraveltoLinkedRef) -> House 01 (-2313.44, -1372.02) & House 02 (-2296.17, -1424.97),
//                        3+3 bloatfly markers + arrival fallback, and Stage-50 Starfield scene (0xB9A)
//   - S4 (0xBA7..0xBAC): Display Laser Musket (0001F22E -> 15 cells + obj 70) + 3 Fusion Cell pickups outside Museum (5 cells each)
//   - Items (0xBAD..0xBB5): A4.5 2 Museum Stimpaks, Caps, Bobby Pin, Pipe Weapon + .38 pickup
//   - S5 (0xBB6..0xBC2): Confirmed-arrival load doors (FO4SF_ConfirmedLoadDoor) + 7 floor-by-floor Museum Raiders (0xBBC..0xBC2) -> Min00 35 -> PrestonDoorREF
//   - S6 (0xBC3..0xBDD): 3F Room (Mama Murphy 0xBC3, Marcy Long 0xBC5, Jun Long 0xBC7, Preston, Sturges; SF HumanRace, non-spacesuit outfits,
//                        --fo4-human-anims keyword 0xBDC default OFF), Preston (0xBC9) & Sturges (0xBD0) Starfield scenes, Basement terminal proxy (0xBD9),
//                        and MQ102FusionCoreREF (0xBDB) -> FO4SFPowerArmor:0x0809 -> stop at "Put the Fusion Core in the Power Armor".
using System.Globalization;
using System.Text.Json;
using Mutagen.Bethesda;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Cache;
using Mutagen.Bethesda.Plugins.Records;
using Noggog;
using SF = Mutagen.Bethesda.Starfield;

static class NextStoryMissionsS2S6
{
    public const string Plugin = "FO4SFMission.esm";
    public static readonly ModKey SfEsm = ModKey.FromFileName("Starfield.esm");

    // Proven Starfield P9 travel driver + non-spacesuit clothes stand-in
    public const uint SfTravelToLinkedRefId = 0x212FDB;
    public const string SfTravelToLinkedRefEdid = "DefaultTraveltoLinkedRef";
    public const uint SfMechanicOutfitId = 0x0005B422;

    // 0xB8C..0xB8E: Shared S2/S3/S6 GLOBs (uses Task 1i holding cell 0xB60 FO4SF_MissionHoldingCell)
    public const uint S2CreatureSlotReadyGlobId = 0xB8C;
    public const string S2CreatureSlotReadyGlobEdid = "FO4SF_S2CreatureSlotReady";
    public const uint Task1bVaultRecoveryReadyGlobId = 0xB8D;
    public const string Task1bVaultRecoveryReadyGlobEdid = "FO4SF_Task1bVaultRecoveryReady";
    public const uint Fo4HumanAnimsEnabledGlobId = 0xB8E;
    public const string Fo4HumanAnimsEnabledGlobEdid = "FO4SF_Fo4HumanAnimsEnabled";

    // 0xB90..0xB95: S2 Vault 111 Radroaches controller quest + 5 FO4 LvlRadRoachAmbush markers
    public const uint S2RoachesQuestId = 0xB90;
    public const string S2RoachesQuestEdid = "FO4SF_Vault111Roaches";
    public const string S2RoachesScriptName = "FO4SF_Vault111RoachesQuest";
    public const uint FirstS2RadroachMarkerId = 0xB91; // ..0xB95 (5 markers)

    // 0xB96..0xBA6: S3 House 01/02 travel PACKs, destination markers, Stage-50 scene, 6 bloatfly markers
    public const uint S3PackHouse01Id = 0xB96;
    public const string S3PackHouse01Edid = "FO4SF_S3_PackHouse01";
    public const uint S3PackHouse02Id = 0xB97;
    public const string S3PackHouse02Edid = "FO4SF_S3_PackHouse02";
    public const uint S3House01MarkerId = 0xB98;
    public const string S3House01MarkerEdid = "FO4SF_S3_House01Marker";
    public const uint S3House2MarkerId = 0xB99;
    public const string S3House02MarkerEdid = "FO4SF_S3_House02Marker";
    public const uint S3Stage50SceneId = 0xB9A;
    public const string S3Stage50SceneEdid = "FO4SF_S3_Stage50Scene";
    public const uint S3Stage50GreetTopicId = 0xB9B, S3Stage50GreetInfoId = 0xB9C;
    public const uint S3Stage50ChoiceTopicId = 0xB9D, S3Stage50ChoiceInfoId = 0xB9E;
    public const uint S3Stage50ReplyTopicId = 0xB9F, S3Stage50ReplyInfoId = 0xBA0;
    public const uint FirstS3BloatflyMarkerId = 0xBA1; // ..0xBA6 (6 markers)

    // 0xBA7..0xBAC: S4 Display Laser Musket (0001F22E) & 3 Fusion Cell pickups
    public const uint S4DisplayMusketActiId = 0xBA7, S4DisplayMusketRefId = 0xBA8;
    public const uint S4FusionCellActiId = 0xBA9, FirstS4FusionCellRefId = 0xBAA; // ..0xBAC (3 pickups)

    // 0xBAD..0xBB5: Museum Items (A4.5 Stimpaks x2, Caps, Bobby Pin, Pipe Pistol+.38)
    public const uint S5StimpakActiId = 0xBAD, FirstS5StimpakRefId = 0xBAE; // ..0xBAF
    public const uint S5CapsActiId = 0xBB0, S5CapsRefId = 0xBB1;
    public const uint S5BobbyPinActiId = 0xBB2, S5BobbyPinRefId = 0xBB3;
    public const uint S5PipeWeaponActiId = 0xBB4, S5PipeWeaponRefId = 0xBB5;

    // 0xBB6..0xBC2: S5 Confirmed-Arrival Load Doors + 7 Museum Raiders (floor-by-floor)
    public const uint S5LoadDoorInActiId = 0xBB6, S5LoadDoorOutActiId = 0xBB7;
    public const uint S5ExtFrontInRefId = 0xBB8, S5IntFrontOutRefId = 0xBB9, S5IntRoofOutRefId = 0xBBA, S5ExtRoofInRefId = 0xBBB;
    public const uint FirstS5MuseumRaiderRefId = 0xBBC; // ..0xBC2 (7 museum raiders)

    // 0xBC3..0xBDC: S6 3F Room Settlers, Preston & Sturges 3F Scenes, Basement Terminal, Fusion Core, --fo4-human-anims KYWD
    public const uint MamaMurphyNpcId = 0xBC3, MamaMurphyRefId = 0xBC4;
    public const uint MarcyLongNpcId = 0xBC5, MarcyLongRefId = 0xBC6;
    public const uint JunLongNpcId = 0xBC7, JunLongRefId = 0xBC8;
    public const uint S6PrestonRoomSceneId = 0xBC9;
    public const uint S6PrestonRoomGreetTopicId = 0xBCA, S6PrestonRoomGreetInfoId = 0xBCB;
    public const uint S6PrestonRoomChoiceTopicId = 0xBCC, S6PrestonRoomChoiceInfoId = 0xBCD;
    public const uint S6PrestonRoomReplyTopicId = 0xBCE, S6PrestonRoomReplyInfoId = 0xBCF;
    public const uint S6SturgesRoomSceneId = 0xBD0;
    public const uint S6SturgesRoomGreetTopicId = 0xBD1, S6SturgesRoomGreetInfoId = 0xBD2;
    public const uint S6SturgesRoomChoiceTopicId = 0xBD3, S6SturgesRoomChoiceInfoId = 0xBD4;
    public const uint S6SturgesRoomReplyTopicId = 0xBD5, S6SturgesRoomReplyInfoId = 0xBD6;
    public const uint S6SturgesTalkActiId = 0xBD7; // reserved helper ACTI slot for Sturges talk UI if needed
    public const uint S6BasementTermActiId = 0xBD8, S6BasementTermRefId = 0xBD9;
    public const uint S6FusionCoreActiId = 0xBDA, S6FusionCoreRefId = 0xBDB;
    public const uint Fo4AnimArchetypeKwId = 0xBDC;
    public const string Fo4AnimArchetypeKwEdid = "FO4SF_AnimArchetypeFO4";
    public const uint MaxAllocatedId = 0xBDD;

    public static bool IsS2S6ActorRefId(uint id) =>
        (id >= FirstS5MuseumRaiderRefId && id <= FirstS5MuseumRaiderRefId + 6)
        || id == MamaMurphyRefId || id == MarcyLongRefId || id == JunLongRefId;

    public const string PickupScriptName = "FO4SF_S5S6ItemPickup";
    public const string LoadDoorScriptName = "FO4SF_ConfirmedLoadDoor";
    public const uint Fo4PipePistolId = 0x0008A2, Fo4Ammo38Id = 0x0008A1, Fo4LaserMusketId = 0x00089D, Fo4FusionCellId = 0x00089B;
    public const uint Fo4StimpakId = 0x000851, Fo4CapsId = 0x0008A4, Fo4BobbyPinId = 0x0008A5, PaFusionCoreId = 0x000809;
    public const uint SfCapsFallbackId = 0x00000F, SfBobbyPinFallbackId = 0x00000A;

    public static readonly string[] S4PreferredRaiderSrcs = { "046458", "01D41F", "046459" };
    public static readonly string[] S5MuseumRaiderSrcs = { "00018D6B", "0001D808", "0001CB6E", "0001E2E0", "0001D809", "0001E2E2", "0001E2E1" };

    public static readonly P3Float S3House01Pos = new(-2313.44f, -1372.02f, 112.66f); // FO4 0019E136
    public static readonly P3Float S3House02Pos = new(-2296.17f, -1424.97f, 111.77f); // FO4 0019E143
    public static readonly P3Float[] S3BloatflyPositions =
    {
        new(-2313.14f, -1372.39f, 112.66f), // House 1: 00074E54
        new(-2316.80f, -1377.73f, 112.66f), // House 1: 0019E134
        new(-2323.03f, -1375.19f, 112.66f), // House 1: 0019E135
        new(-2294.09f, -1424.36f, 111.75f), // House 2: 0019E13C
        new(-2288.62f, -1432.94f, 111.75f), // House 2: 0019E13D
        new(-2286.38f, -1426.89f, 111.75f), // House 2: 0019E13E
    };

    public static readonly P3Float S4DisplayMusketPos = new(-2015.41f, -1697.13f, 88.19f);
    public static readonly P3Float[] S4FusionCellPositions =
    {
        new(-2014.75f, -1696.80f, 88.16f), // FO4 0005597E
        new(-2014.56f, -1696.47f, 88.16f), // FO4 0005597D
        new(-2014.45f, -1696.57f, 88.16f), // FO4 0005597C
    };

    public sealed record CreatureSlotsConfig(bool Ready, string PluginName, uint RadroachNpcId, uint BloatflyNpcId)
    {
        public static CreatureSlotsConfig LoadOrEmpty(string? path)
        {
            if (string.IsNullOrWhiteSpace(path) || !File.Exists(path))
                return new CreatureSlotsConfig(false, "FO4SF_RA5Creatures.esm", 0x000804, 0x000809);
            using var doc = JsonDocument.Parse(File.ReadAllText(path));
            var root = doc.RootElement;
            string plug = root.TryGetProperty("plugin", out var pe) && pe.GetString() is { Length: > 0 } ps
                ? ps : "FO4SF_RA5Creatures.esm";
            static uint ParseHex(JsonElement obj, string key, uint dflt)
            {
                if (!obj.TryGetProperty(key, out var el)) return dflt;
                if (el.ValueKind == JsonValueKind.Number) return el.GetUInt32();
                string s = (el.GetString() ?? "").Trim();
                if (s.StartsWith("0x", StringComparison.OrdinalIgnoreCase)) s = s[2..];
                return uint.TryParse(s, NumberStyles.HexNumber, CultureInfo.InvariantCulture, out uint val) ? val : dflt;
            }
            bool ready = !root.TryGetProperty("ready", out var re) || re.ValueKind != JsonValueKind.False;
            return new CreatureSlotsConfig(ready, plug, ParseHex(root, "radroach_npc", 0x000804), ParseHex(root, "bloatfly_npc", 0x000809));
        }
    }

    static SF.ScriptObjectProperty ObjProp(string name, FormKey fk) => new()
    {
        Name = name,
        Flags = SF.ScriptProperty.Flag.Edited,
        Object = new FormLink<SF.IStarfieldMajorRecordGetter>(fk),
        Alias = -1,
        Unused = 0,
    };

    static SF.Global AddGlob(SF.StarfieldMod mod, ModKey modKey, uint id, string edid, float value)
    {
        var g = new SF.Global(new FormKey(modKey, id), SF.StarfieldRelease.Starfield) { EditorID = edid, Data = value };
        mod.Globals.Add(g);
        return g;
    }

    static SF.Activator AddActivator(SF.StarfieldMod mod, ModKey modKey, uint id, string edid, string name, string verb)
    {
        var a = new SF.Activator(new FormKey(modKey, id), SF.StarfieldRelease.Starfield)
        {
            EditorID = edid,
            Name = name,
            ActivateTextOverride = verb,
            ActivationAngle = 360,
            ObjectBounds = new SF.ObjectBounds { First = new P3Float(-0.25f, -0.25f, -0.25f), Second = new P3Float(0.25f, 0.25f, 0.25f) },
        };
        mod.Activators.Add(a);
        return a;
    }

    static SF.PlacedObject PlacePersistentMarker(SF.Cell cell, ModKey modKey, uint id, string edid, FormKey baseKey, P3Float pos, bool initiallyDisabled)
    {
        var r = new SF.PlacedObject(new FormKey(modKey, id), SF.StarfieldRelease.Starfield)
        {
            EditorID = edid,
            Base = new FormLinkNullable<SF.IPlaceableObjectGetter>(baseKey),
            Position = pos,
            Rotation = new P3Float(0, 0, 0),
        };
        r.MajorRecordFlagsRaw |= 0x400 | (initiallyDisabled ? 0x800 : 0);
        cell.Persistent.Add(r);
        return r;
    }

    static void AttachPickupScript(
        SF.PlacedObject refObj, string itemKind, int primaryId, int secondaryId = 0,
        int fallbackId = 0, int primaryCount = 1, int secondaryCount = 0, bool consume = true)
    {
        var s = new SF.ScriptEntry { Name = PickupScriptName, Flags = SF.ScriptEntry.Flag.Local };
        s.Properties.Add(new SF.ScriptStringProperty { Name = "ItemKind", Flags = SF.ScriptProperty.Flag.Edited, Data = itemKind });
        s.Properties.Add(new SF.ScriptIntProperty { Name = "PrimaryFormId", Flags = SF.ScriptProperty.Flag.Edited, Data = primaryId });
        if (secondaryId > 0)
            s.Properties.Add(new SF.ScriptIntProperty { Name = "SecondaryFormId", Flags = SF.ScriptProperty.Flag.Edited, Data = secondaryId });
        if (fallbackId > 0)
            s.Properties.Add(new SF.ScriptIntProperty { Name = "FallbackFormId", Flags = SF.ScriptProperty.Flag.Edited, Data = fallbackId });
        s.Properties.Add(new SF.ScriptIntProperty { Name = "PrimaryCount", Flags = SF.ScriptProperty.Flag.Edited, Data = primaryCount });
        if (secondaryCount > 0)
            s.Properties.Add(new SF.ScriptIntProperty { Name = "SecondaryCount", Flags = SF.ScriptProperty.Flag.Edited, Data = secondaryCount });
        s.Properties.Add(new SF.ScriptBoolProperty { Name = "ConsumeOnActivate", Flags = SF.ScriptProperty.Flag.Edited, Data = consume });
        var vm = new SF.VirtualMachineAdapter { Version = 6, ObjectFormat = 2 };
        vm.Scripts.Add(s);
        refObj.VirtualMachineAdapter = vm;
    }

    static void AttachConfirmedDoorScript(
        SF.PlacedObject refObj, string targetPlugin, int targetFormId, string direction, string doorTag,
        bool useDestPos, P3Float destPos, int fallbackFormId = 0)
    {
        var s = new SF.ScriptEntry { Name = LoadDoorScriptName, Flags = SF.ScriptEntry.Flag.Local };
        s.Properties.Add(new SF.ScriptStringProperty { Name = "TargetPlugin", Flags = SF.ScriptProperty.Flag.Edited, Data = targetPlugin });
        s.Properties.Add(new SF.ScriptIntProperty { Name = "TargetFormId", Flags = SF.ScriptProperty.Flag.Edited, Data = targetFormId });
        if (fallbackFormId > 0)
        {
            s.Properties.Add(new SF.ScriptStringProperty { Name = "FallbackTargetPlugin", Flags = SF.ScriptProperty.Flag.Edited, Data = "FO4TerrainCore.esm" });
            s.Properties.Add(new SF.ScriptIntProperty { Name = "FallbackTargetFormId", Flags = SF.ScriptProperty.Flag.Edited, Data = fallbackFormId });
        }
        s.Properties.Add(new SF.ScriptStringProperty { Name = "Direction", Flags = SF.ScriptProperty.Flag.Edited, Data = direction });
        s.Properties.Add(new SF.ScriptStringProperty { Name = "DoorTag", Flags = SF.ScriptProperty.Flag.Edited, Data = doorTag });
        s.Properties.Add(new SF.ScriptBoolProperty { Name = "UseDestinationPosition", Flags = SF.ScriptProperty.Flag.Edited, Data = useDestPos });
        if (useDestPos)
        {
            s.Properties.Add(new SF.ScriptFloatProperty { Name = "DestinationX", Flags = SF.ScriptProperty.Flag.Edited, Data = destPos.X });
            s.Properties.Add(new SF.ScriptFloatProperty { Name = "DestinationY", Flags = SF.ScriptProperty.Flag.Edited, Data = destPos.Y });
            s.Properties.Add(new SF.ScriptFloatProperty { Name = "DestinationZ", Flags = SF.ScriptProperty.Flag.Edited, Data = destPos.Z });
        }
        var vm = new SF.VirtualMachineAdapter { Version = 6, ObjectFormat = 2 };
        vm.Scripts.Add(s);
        refObj.VirtualMachineAdapter = vm;
    }

    static SF.Npc CloneRoomSettler(
        SF.StarfieldMod mod, ModKey modKey, uint id, string edid, string name,
        SF.INpcGetter template, FormKey humanRace, FormKey voice, FormKey minutemenFaction,
        FormKey outfitKey, FormKey forceHideAv, SF.IStarfieldModGetter sfMod, bool female)
    {
        var npc = (SF.Npc)template.Duplicate(new FormKey(modKey, id));
        npc.EditorID = edid;
        npc.Name = name;
        npc.Race.SetTo(humanRace);
        npc.Voice.SetTo(voice);
        npc.VirtualMachineAdapter = null;
        npc.Packages.Clear();
        npc.DefaultTemplate.Clear();
        npc.TemplateActors = null;
        npc.CrimeFaction.Clear();
        npc.ActivateTextOverride = "Talk";
        npc.Flags = ((npc.Flags | SF.Npc.Flag.Essential | SF.Npc.Flag.Unique | SF.Npc.Flag.AutoCalcStats)
                     & ~(SF.Npc.Flag.Respawn | SF.Npc.Flag.Protected));
        npc.Flags = female ? (npc.Flags | SF.Npc.Flag.Female) : (npc.Flags & ~SF.Npc.Flag.Female);
        npc.Factions.Clear();
        npc.Factions.Add(new SF.RankPlacement { Faction = new FormLink<SF.IFactionGetter>(minutemenFaction), Rank = 0 });
        npc.DefaultOutfit.SetTo(outfitKey);
        npc.SpaceOutfit.SetTo(outfitKey);
        FalloutActorLooks.EnforceNoStarfieldSpacesuit(npc, sfMod, forceHideAv, outfitKey, preserveIntentionalTemplates: false);
        mod.Npcs.Add(npc);
        return npc;
    }

    public static void PopulateS2S6Missions(
        SF.StarfieldMod mod,
        SF.Cell holdingCell,
        SF.IStarfieldModGetter sfMod,
        ILinkCache cache,
        SF.Quest min00Quest,
        SF.ScriptEntry min00Script,
        SF.Quest? codsworthQuest,
        SF.ScriptEntry? codsworthScript,
        FormKey qtypKey,
        FormKey xMarkerKey,
        FormKey minutemenFactionKey,
        SF.INpcGetter humanMaleTemplate,
        FormKey humanRaceKey,
        FormKey maleVoiceKey,
        SF.INpcGetter codsNpc,
        FormKey concordRaiderNpcKey,
        FormKey raiderCombatPackKey,
        FormKey raiderSandboxPackKey,
        CreatureSlotsConfig creatureSlots,
        bool fo4HumanAnims,
        bool task1bVaultRecoveryReady)
    {
        var modKey = mod.ModKey;
        var rel = SF.StarfieldRelease.Starfield;
        var forceHideAv = new FormKey(SfEsm, FalloutActorLooks.SfForceHideSpacesuitAvId);

        // 0. Globals (markers & NPCs go into shared Mission holdingCell 0xB60, 0 WRLD overrides!)
        var creatureSlotGlob = AddGlob(mod, modKey, S2CreatureSlotReadyGlobId, S2CreatureSlotReadyGlobEdid, creatureSlots.Ready ? 1f : 0f);
        var task1bGlob = AddGlob(mod, modKey, Task1bVaultRecoveryReadyGlobId, Task1bVaultRecoveryReadyGlobEdid, task1bVaultRecoveryReady ? 1f : 0f);
        AddGlob(mod, modKey, Fo4HumanAnimsEnabledGlobId, Fo4HumanAnimsEnabledGlobEdid, fo4HumanAnims ? 1f : 0f);

        // 1. S2 Vault 111 Radroaches QUST (0xB90) + 5 stage-gated markers (0xB91..0xB95)
        var roachMarkers = new List<SF.PlacedObject>(5);
        for (uint i = 0; i < 5; i++)
            roachMarkers.Add(PlacePersistentMarker(holdingCell, modKey, FirstS2RadroachMarkerId + i, $"FO4SF_S2_RadroachMarker_{i}", xMarkerKey, new P3Float(0, 0, 0), true));

        var s2Quest = new SF.Quest(new FormKey(modKey, S2RoachesQuestId), rel)
        {
            EditorID = S2RoachesQuestEdid,
            Name = "Out of Time: Vault 111",
            FormVersion = 581,
            Version2 = 12,
            Data = new SF.QuestData
            {
                Flags = SF.Quest.Flag.StartGameEnabled | SF.Quest.Flag.AllowRepeatedStages | SF.Quest.Flag.DisplaysInHud | SF.Quest.Flag.RunOnce,
                Priority = 52,
            },
        };
        s2Quest.QuestType.SetTo(qtypKey);
        foreach (ushort stIdx in new ushort[] { 10, 20, 30, 40, 100 })
        {
            var st = new SF.QuestStage { Index = stIdx };
            st.LogEntries.Add(new SF.QuestLogEntry { Flags = stIdx == 100 ? SF.QuestLogEntry.Flag.CompleteQuest : (SF.QuestLogEntry.Flag)0 });
            s2Quest.Stages.Add(st);
        }
        s2Quest.Objectives.Add(new SF.QuestObjective { Index = 10, Flags = (SF.QuestObjective.Flag)0, DisplayText = "Clear the Vault 111 corridor" });
        var s2Script = new SF.ScriptEntry { Name = S2RoachesScriptName, Flags = SF.ScriptEntry.Flag.Local };
        var rmList = new SF.ScriptObjectListProperty { Name = "RadroachMarkers", Flags = SF.ScriptProperty.Flag.Edited };
        foreach (var rm in roachMarkers) rmList.Objects.Add(ObjProp("", rm.FormKey));
        s2Script.Properties.Add(rmList);
        s2Script.Properties.Add(ObjProp("CreatureSlotReadyGlob", creatureSlotGlob.FormKey));
        s2Script.Properties.Add(ObjProp("Task1bRecoveryReadyGlob", task1bGlob.FormKey));
        s2Script.Properties.Add(new SF.ScriptStringProperty { Name = "CreaturePlugin", Flags = SF.ScriptProperty.Flag.Edited, Data = creatureSlots.PluginName });
        s2Script.Properties.Add(new SF.ScriptIntProperty { Name = "CreatureRadroachNpcId", Flags = SF.ScriptProperty.Flag.Edited, Data = (int)creatureSlots.RadroachNpcId });
        s2Quest.VirtualMachineAdapter = new SF.QuestAdapter
        {
            Version = 6, ObjectFormat = 2, ExtraBindDataVersion = 3,
            Script = new SF.ScriptEntry { Name = "", Flags = SF.ScriptEntry.Flag.Local },
            Scripts = { s2Script },
        };
        mod.Quests.Add(s2Quest);

        // 2. S3 Sanctuary House 01/02 PACKs (DefaultTraveltoLinkedRef 0x212FDB), Markers, Stage-50 Scene & Bloatfly Markers
        // Placed in holdingCell (0xB8F) so S2-S6 emits zero FO4Core_Commonwealth WRLD overrides; relocated via 1i host anchor at runtime.
        var h1Marker = PlacePersistentMarker(holdingCell, modKey, S3House01MarkerId, S3House01MarkerEdid, xMarkerKey, S3House01Pos, false);
        var h2Marker = PlacePersistentMarker(holdingCell, modKey, S3House2MarkerId, S3House02MarkerEdid, xMarkerKey, S3House02Pos, false);

        cache.TryResolve<SF.IPackageGetter>(new FormKey(SfEsm, SfTravelToLinkedRefId), out var baseTravelPack);
        SF.Package BuildTravelPack(uint id, string edid, uint stageMin, uint stageMax)
        {
            var p = baseTravelPack is not null
                ? (SF.Package)baseTravelPack.Duplicate(new FormKey(modKey, id))
                : new SF.Package(new FormKey(modKey, id), rel);
            p.EditorID = edid;
            p.FormVersion = 581;
            if (codsworthQuest is not null)
            {
                p.Conditions.Add(Mission.QuestStageCond(codsworthQuest.FormKey, SF.CompareOperator.GreaterThanOrEqualTo, stageMin));
                p.Conditions.Add(Mission.QuestStageCond(codsworthQuest.FormKey, SF.CompareOperator.LessThanOrEqualTo, stageMax));
            }
            mod.Packages.Add(p);
            return p;
        }
        var packH1 = BuildTravelPack(S3PackHouse01Id, S3PackHouse01Edid, 30, 32);
        var packH2 = BuildTravelPack(S3PackHouse02Id, S3PackHouse02Edid, 36, 38);

        var s3FlyMarkers = new List<SF.PlacedObject>(6);
        for (int i = 0; i < S3BloatflyPositions.Length; i++)
            s3FlyMarkers.Add(PlacePersistentMarker(holdingCell, modKey, FirstS3BloatflyMarkerId + (uint)i, $"FO4SF_S3_BloatflyMarker_{(uint)i}", xMarkerKey, S3BloatflyPositions[i], true));

        if (codsworthQuest is not null && codsworthScript is not null)
        {
            if (codsworthQuest.Aliases?.OfType<SF.QuestReferenceAlias>().FirstOrDefault(a => a.ID == 0) is { } cwAl)
            {
                cwAl.PackageData.Add(new FormLink<SF.IPackageGetter>(packH1.FormKey));
                cwAl.PackageData.Add(new FormLink<SF.IPackageGetter>(packH2.FormKey));
            }
            var cwVoiceKey = new FormKey(modKey, Mission.CodsworthVoiceId);
            var s3Stage50Scene = Mission.BuildTopScene(
                modKey, codsworthQuest, codsNpc.FormKey, cwVoiceKey,
                Mission.QuestStageCond(codsworthQuest.FormKey, SF.CompareOperator.EqualTo, 50f),
                S3Stage50SceneId, S3Stage50SceneEdid,
                S3Stage50GreetTopicId, "FO4SF_S3_Stage50GreetTopic",
                S3Stage50GreetInfoId, "FO4SF_S3_Stage50GreetInfo",
                new[] { ("Sanctuary houses appear clear of immediate threats. Concord south of the bridge still needs investigating.", 0u, 0f) },
                S3Stage50ChoiceTopicId, S3Stage50ChoiceInfoId,
                S3Stage50ReplyTopicId, S3Stage50ReplyInfoId,
                "FO4SF_S3_Stage50", 56f,
                new (string Prompt, IReadOnlyList<(string Text, uint Wem, float Duration)> Replies, short EndStage, bool Goodbye)[]
                {
                    ("Ask Codsworth where to check next.", new[] { ("Try Concord across the river bridge to the south.", 0u, 0f) }, (short)100, true),
                });

            codsworthScript.Properties.Add(ObjProp("S3Stage50Scene", s3Stage50Scene.FormKey));
            codsworthScript.Properties.Add(ObjProp("S3House1Marker", h1Marker.FormKey));
            codsworthScript.Properties.Add(ObjProp("S3House2Marker", h2Marker.FormKey));
            codsworthScript.Properties.Add(ObjProp("S3House1TravelPack", packH1.FormKey));
            codsworthScript.Properties.Add(ObjProp("S3House2TravelPack", packH2.FormKey));
            codsworthScript.Properties.Add(ObjProp("S3CreatureSlotReady", creatureSlotGlob.FormKey));
            var flyProp = new SF.ScriptObjectListProperty { Name = "S3BloatflyMarkers", Flags = SF.ScriptProperty.Flag.Edited };
            foreach (var fm in s3FlyMarkers) flyProp.Objects.Add(ObjProp("", fm.FormKey));
            codsworthScript.Properties.Add(flyProp);
            codsworthScript.Properties.Add(new SF.ScriptStringProperty { Name = "CreaturePlugin", Flags = SF.ScriptProperty.Flag.Edited, Data = creatureSlots.PluginName });
            codsworthScript.Properties.Add(new SF.ScriptIntProperty { Name = "CreatureBloatflyNpcId", Flags = SF.ScriptProperty.Flag.Edited, Data = (int)creatureSlots.BloatflyNpcId });
        }

        // 3. S4 Display Laser Musket (0001F22E -> 15 cells + obj 70) + 3 Fusion Cell pickups (5 cells each) in holdingCell (relocated via 1i host anchor)
        var dispMusketActi = AddActivator(mod, modKey, S4DisplayMusketActiId, "FO4SF_S4_DisplayLaserMusketActi", "Laser Musket", "Take");
        var dispMusketRef = PlacePersistentMarker(holdingCell, modKey, S4DisplayMusketRefId, "FO4SF_S4_DisplayLaserMusketRef", dispMusketActi.FormKey, S4DisplayMusketPos, true);
        AttachPickupScript(dispMusketRef, "display_musket", (int)Fo4LaserMusketId, (int)Fo4FusionCellId, 0, 1, 15, consume: true);

        var fcActi = AddActivator(mod, modKey, S4FusionCellActiId, "FO4SF_S4_FusionCellActi", "Fusion Cell (5)", "Take");
        var fcRefs = new List<SF.PlacedObject>(S4FusionCellPositions.Length);
        for (int i = 0; i < S4FusionCellPositions.Length; i++)
        {
            var fcr = PlacePersistentMarker(holdingCell, modKey, FirstS4FusionCellRefId + (uint)i, $"FO4SF_S4_FusionCellRef_{i}", fcActi.FormKey, S4FusionCellPositions[i], true);
            AttachPickupScript(fcr, "fusion_cell", (int)Fo4FusionCellId, 0, 0, 5, 0, consume: true);
            fcRefs.Add(fcr);
        }

        // 4. Museum Items: A4.5 2 Stimpaks, Caps, Bobby Pin, Pipe Pistol+.38 (inside holdingCell, moved into 0x0100E2F4 on entry)
        var stimActi = AddActivator(mod, modKey, S5StimpakActiId, "FO4SF_Item_StimpakActi", "Stimpak", "Take");
        var stimRef0 = PlacePersistentMarker(holdingCell, modKey, FirstS5StimpakRefId, "FO4SF_S5_MuseumStimpakRef_0", stimActi.FormKey, new P3Float(0, 0, 0), true);
        var stimRef1 = PlacePersistentMarker(holdingCell, modKey, FirstS5StimpakRefId + 1, "FO4SF_S5_MuseumStimpakRef_1", stimActi.FormKey, new P3Float(0, 0, 0), true);
        AttachPickupScript(stimRef0, "stimpak", (int)Fo4StimpakId);
        AttachPickupScript(stimRef1, "stimpak", (int)Fo4StimpakId);

        var capsActi = AddActivator(mod, modKey, S5CapsActiId, "FO4SF_Item_CapsActi", "Bottlecap (15)", "Take");
        var capsRef = PlacePersistentMarker(holdingCell, modKey, S5CapsRefId, "FO4SF_S5_MuseumCapsRef", capsActi.FormKey, new P3Float(0, 0, 0), true);
        AttachPickupScript(capsRef, "caps", (int)Fo4CapsId, 0, (int)SfCapsFallbackId, 15);

        var pinActi = AddActivator(mod, modKey, S5BobbyPinActiId, "FO4SF_Item_BobbyPinActi", "Bobby Pin (2)", "Take");
        var pinRef = PlacePersistentMarker(holdingCell, modKey, S5BobbyPinRefId, "FO4SF_S5_MuseumBobbyPinRef", pinActi.FormKey, new P3Float(0, 0, 0), true);
        AttachPickupScript(pinRef, "bobbypin", (int)Fo4BobbyPinId, 0, (int)SfBobbyPinFallbackId, 2);

        var pipeActi = AddActivator(mod, modKey, S5PipeWeaponActiId, "FO4SF_S5_MuseumPipeWeaponActi", "Pipe Pistol & .38 Rounds", "Take");
        var pipeRef = PlacePersistentMarker(holdingCell, modKey, S5PipeWeaponRefId, "FO4SF_S5_MuseumPipeWeaponRef", pipeActi.FormKey, new P3Float(0, 0, 0), true);
        AttachPickupScript(pipeRef, "pipe_weapon", (int)Fo4PipePistolId, (int)Fo4Ammo38Id, 0, 1, 24);

        // 5. S5 Confirmed-Arrival Load Doors + 7 Museum Raiders (floor-by-floor)
        var doorInActi = AddActivator(mod, modKey, S5LoadDoorInActiId, "FO4SF_S5_LoadDoorInActi", "Museum of Freedom", "Open");
        var doorOutActi = AddActivator(mod, modKey, S5LoadDoorOutActiId, "FO4SF_S5_LoadDoorOutActi", "Commonwealth", "Open");
        var extFrontIn = PlacePersistentMarker(holdingCell, modKey, S5ExtFrontInRefId, "FO4SF_S5_ExtFrontInRef", doorInActi.FormKey, new P3Float(0, 0, 0), true);
        var intFrontOut = PlacePersistentMarker(holdingCell, modKey, S5IntFrontOutRefId, "FO4SF_S5_IntFrontOutRef", doorOutActi.FormKey, new P3Float(0, 0, 0), true);
        var intRoofOut = PlacePersistentMarker(holdingCell, modKey, S5IntRoofOutRefId, "FO4SF_S5_IntRoofOutRef", doorOutActi.FormKey, new P3Float(0, 0, 0), true);
        var extRoofIn = PlacePersistentMarker(holdingCell, modKey, S5ExtRoofInRefId, "FO4SF_S5_ExtRoofInRef", doorInActi.FormKey, new P3Float(0, 0, 0), true);

        AttachConfirmedDoorScript(extFrontIn, "FO4Port.esm", 0x00E2F5, "in", "s5_front_in", false, new P3Float(0, 0, 0));
        AttachConfirmedDoorScript(intFrontOut, "FO4TerrainCore.esm", 0x0A775C, "out", "s5_front_out", true, new P3Float(-2012.50f, -1697.94f, 88.24f), 0x0A775B);
        AttachConfirmedDoorScript(intRoofOut, "FO4TerrainCore.esm", 0x0A775C, "out", "s5_roof_out", true, new P3Float(-2008.49f, -1724.60f, 97.42f), 0x0A775B); // F9: 2.21 m south of ExtRoofIn
        AttachConfirmedDoorScript(extRoofIn, "FO4Port.esm", 0x00E2F5, "in", "s5_roof_in", true, new P3Float(-19.50f, 9.14f, 9.15f));

        var museumRaiders = new List<SF.PlacedNpc>(7);
        for (uint i = 0; i < 7; i++)
        {
            var mr = new SF.PlacedNpc(new FormKey(modKey, FirstS5MuseumRaiderRefId + i), rel)
            {
                EditorID = $"FO4SF_S5_MuseumRaider_{S5MuseumRaiderSrcs[i]}",
                Base = new FormLink<SF.INpcGetter>(concordRaiderNpcKey),
                Position = new P3Float(0, 0, 0),
                Rotation = new P3Float(0, 0, 0),
            };
            mr.MajorRecordFlagsRaw |= 0x400 | 0x800; // Persistent | InitiallyDisabled
            holdingCell.Persistent.Add(mr);
            museumRaiders.Add(mr);
        }

        // 6. S6 3F Room NPCs, Preston & Sturges 3F Scenes, Basement Terminal proxy, MQ102FusionCoreREF, --fo4-human-anims KYWD
        var femaleTpl = sfMod.Npcs.FirstOrDefault(n =>
                            n.Race.FormKey == humanRaceKey && n.Flags.HasFlag(SF.Npc.Flag.Female) && !string.IsNullOrEmpty(n.EditorID) && n.DefaultTemplate.IsNull)
                        ?? sfMod.Npcs.FirstOrDefault(n => n.Race.FormKey == humanRaceKey && n.Flags.HasFlag(SF.Npc.Flag.Female))
                        ?? humanMaleTemplate;
        var femaleVoice = sfMod.VoiceTypes.FirstOrDefault(v => v.EditorID == "GenericFemaleEvenToned" && v.Flags.HasFlag(SF.VoiceType.Flag.AllowDefaultDialog))?.FormKey
                          ?? sfMod.VoiceTypes.FirstOrDefault(v => (v.EditorID ?? "").Contains("Female", StringComparison.OrdinalIgnoreCase) && v.Flags.HasFlag(SF.VoiceType.Flag.AllowDefaultDialog))?.FormKey
                          ?? maleVoiceKey;

        var prestonOutfitKey = new FormKey(modKey, FalloutActorLooks.PrestonOutfitId);
        var raiderOutfitKey = new FormKey(modKey, FalloutActorLooks.RaiderOutfitId);
        var settlerOutfitKey = sfMod.Outfits.Any(o => o.FormKey == new FormKey(SfEsm, SfMechanicOutfitId))
            ? new FormKey(SfEsm, SfMechanicOutfitId)
            : raiderOutfitKey;

        // Upgrade Sturges (0xA00) to non-spacesuit mechanic clothes + ForceHideSpacesuit=1.0
        var sturgesNpc = mod.Npcs.FirstOrDefault(n => n.FormKey == new FormKey(modKey, NextStoryMissionsA4.SturgesNpcId));
        if (sturgesNpc is not null)
        {
            sturgesNpc.DefaultOutfit.SetTo(settlerOutfitKey);
            sturgesNpc.SpaceOutfit.SetTo(settlerOutfitKey);
            FalloutActorLooks.EnforceNoStarfieldSpacesuit(sturgesNpc, sfMod, forceHideAv, settlerOutfitKey, preserveIntentionalTemplates: false);
        }

        var mamaNpc = CloneRoomSettler(mod, modKey, MamaMurphyNpcId, "FO4_MamaMurphy", "Mama Murphy", femaleTpl, humanRaceKey, femaleVoice, minutemenFactionKey, settlerOutfitKey, forceHideAv, sfMod, female: true);
        var marcyNpc = CloneRoomSettler(mod, modKey, MarcyLongNpcId, "FO4_MarcyLong", "Marcy Long", femaleTpl, humanRaceKey, femaleVoice, minutemenFactionKey, settlerOutfitKey, forceHideAv, sfMod, female: true);
        var junNpc = CloneRoomSettler(mod, modKey, JunLongNpcId, "FO4_JunLong", "Jun Long", humanMaleTemplate, humanRaceKey, maleVoiceKey, minutemenFactionKey, settlerOutfitKey, forceHideAv, sfMod, female: false);

        SF.PlacedNpc PlaceRoomNpc(uint id, string edid, FormKey baseKey)
        {
            var r = new SF.PlacedNpc(new FormKey(modKey, id), rel)
            {
                EditorID = edid, Base = new FormLink<SF.INpcGetter>(baseKey),
                Position = new P3Float(0, 0, 0), Rotation = new P3Float(0, 0, 0),
            };
            r.MajorRecordFlagsRaw |= 0x400 | 0x800;
            holdingCell.Persistent.Add(r);
            return r;
        }
        var mamaRef = PlaceRoomNpc(MamaMurphyRefId, "FO4SF_S6_MamaMurphyRef", mamaNpc.FormKey);
        var marcyRef = PlaceRoomNpc(MarcyLongRefId, "FO4SF_S6_MarcyLongRef", marcyNpc.FormKey);
        var junRef = PlaceRoomNpc(JunLongRefId, "FO4SF_S6_JunLongRef", junNpc.FormKey);

        // Optional --fo4-human-anims keyword FO4SF_AnimArchetypeFO4 (default OFF until Claude posts PASS on #856)
        if (fo4HumanAnims)
        {
            var kw = new SF.Keyword(new FormKey(modKey, Fo4AnimArchetypeKwId), rel) { EditorID = Fo4AnimArchetypeKwEdid };
            mod.Keywords.Add(kw);
            foreach (uint nid in new[] { Mission.PrestonNpcId, NextStoryMissionsA4.SturgesNpcId, MamaMurphyNpcId, MarcyLongNpcId, JunLongNpcId, FalloutActorLooks.ConcordRaiderNpcId })
            {
                if (mod.Npcs.FirstOrDefault(n => n.FormKey == new FormKey(modKey, nid)) is { } npcTarget)
                {
                    npcTarget.Keywords ??= new ExtendedList<IFormLinkGetter<SF.IKeywordGetter>>();
                    if (!npcTarget.Keywords.Any(k => k.FormKey == kw.FormKey))
                        npcTarget.Keywords.Add(new FormLink<SF.IKeywordGetter>(kw.FormKey));
                }
            }
        }

        AddActivator(mod, modKey, S6SturgesTalkActiId, "FO4SF_S6_SturgesTalkActi", "Sturges", "Talk");
        var termActi = AddActivator(mod, modKey, S6BasementTermActiId, "FO4SF_S6_BasementTermActi", "Security Terminal", "Unlock Security Gate");
        var termRef = PlacePersistentMarker(holdingCell, modKey, S6BasementTermRefId, "FO4SF_S6_BasementTermRef", termActi.FormKey, new P3Float(0, 0, 0), true);
        AttachPickupScript(termRef, "basement_terminal", 0x00EDF0, 0, 0, 1, 0, consume: false);

        var coreActi = AddActivator(mod, modKey, S6FusionCoreActiId, "FO4SF_S6_FusionCoreActi", "Fusion Core", "Take");
        var coreRef = PlacePersistentMarker(holdingCell, modKey, S6FusionCoreRefId, "FO4SF_S6_FusionCoreRef", coreActi.FormKey, new P3Float(0, 0, 0), true);
        AttachPickupScript(coreRef, "fusion_core", (int)PaFusionCoreId, 0, 0, 1, 0, consume: true);

        // Sturges alias + Preston/Sturges 3F Room Scenes on FO4SF_Min00
        var sturgesRefKey = new FormKey(modKey, NextStoryMissionsA4.SturgesRefId);
        uint sturgesAliasId = (uint)(min00Quest.Aliases?.OfType<SF.IQuestReferenceAliasGetter>().Count() ?? 1);
        (min00Quest.Aliases ??= new ExtendedList<SF.AQuestAlias>()).Add(new SF.QuestReferenceAlias
        {
            ID = sturgesAliasId,
            Name = "Sturges",
            Flags = SF.AQuestAlias.Flag.Optional | SF.AQuestAlias.Flag.AllowDead | SF.AQuestAlias.Flag.AllowDisabled |
                    SF.AQuestAlias.Flag.AllowReserved | SF.AQuestAlias.Flag.UsesStoredText,
            ForcedReference = new FormLinkNullable<SF.IPlacedGetter>(sturgesRefKey),
        });

        var prestonNpcKey = new FormKey(modKey, Mission.PrestonNpcId);
        var s6PrestonScene = Mission.BuildTopScene(
            modKey, min00Quest, prestonNpcKey, maleVoiceKey,
            Mission.QuestStageCond(min00Quest.FormKey, SF.CompareOperator.EqualTo, 35f),
            S6PrestonRoomSceneId, "FO4SF_S6_PrestonRoomScene",
            S6PrestonRoomGreetTopicId, "FO4SF_S6_PrestonRoomGreetTopic",
            S6PrestonRoomGreetInfoId, "FO4SF_S6_PrestonRoomGreetInfo",
            new[] { ("You made it up here. Sturges spotted a fusion core down in the basement and power armor on the roof.", 0u, 0f) },
            S6PrestonRoomChoiceTopicId, S6PrestonRoomChoiceInfoId,
            S6PrestonRoomReplyTopicId, S6PrestonRoomReplyInfoId,
            "FO4SF_S6_PrestonRoom", 52f,
            new (string Prompt, IReadOnlyList<(string Text, uint Wem, float Duration)> Replies, short EndStage, bool Goodbye)[]
            {
                ("Tell Preston you will get the Fusion Core from the basement.", new[] { ("Good luck down there. Talk to Sturges if you need help with the terminal.", 0u, 0f) }, (short)40, true),
            });

        var s6SturgesScene = Mission.BuildTopScene(
            modKey, min00Quest, new FormKey(modKey, NextStoryMissionsA4.SturgesNpcId), maleVoiceKey,
            Mission.QuestStageCond(min00Quest.FormKey, SF.CompareOperator.GreaterThanOrEqualTo, 35f),
            S6SturgesRoomSceneId, "FO4SF_S6_SturgesRoomScene",
            S6SturgesRoomGreetTopicId, "FO4SF_S6_SturgesRoomGreetTopic",
            S6SturgesRoomGreetInfoId, "FO4SF_S6_SturgesRoomGreetInfo",
            new[] { ("The basement security gate can be opened through its terminal or picked with a bobby pin.", 0u, 0f) },
            S6SturgesRoomChoiceTopicId, S6SturgesRoomChoiceInfoId,
            S6SturgesRoomReplyTopicId, S6SturgesRoomReplyInfoId,
            "FO4SF_S6_SturgesRoom", 52f,
            new (string Prompt, IReadOnlyList<(string Text, uint Wem, float Duration)> Replies, short EndStage, bool Goodbye)[]
            {
                ("Head down to unlock the security gate and grab the Fusion Core.", new[] { ("Grab the Fusion Core and drop it straight into the armor up on the roof.", 0u, 0f) }, (short)-1, true),
            },
            aliasId: sturgesAliasId);

        // Bind S5/S6 VMAD properties onto FO4SF_Min00Quest
        var s5RaidersProp = new SF.ScriptObjectListProperty { Name = "S5MuseumRaiders", Flags = SF.ScriptProperty.Flag.Edited };
        foreach (var mr in museumRaiders) s5RaidersProp.Objects.Add(ObjProp("", mr.FormKey));
        min00Script.Properties.Add(s5RaidersProp);

        var s5DoorsProp = new SF.ScriptObjectListProperty { Name = "S5MuseumDoors", Flags = SF.ScriptProperty.Flag.Edited };
        foreach (var dr in new[] { extFrontIn, intFrontOut, intRoofOut, extRoofIn }) s5DoorsProp.Objects.Add(ObjProp("", dr.FormKey));
        min00Script.Properties.Add(s5DoorsProp);

        var s5LootProp = new SF.ScriptObjectListProperty { Name = "S5MuseumLootMarkers", Flags = SF.ScriptProperty.Flag.Edited };
        foreach (var lr in new[] { stimRef0, stimRef1, capsRef, pinRef, pipeRef, termRef, coreRef }) s5LootProp.Objects.Add(ObjProp("", lr.FormKey));
        min00Script.Properties.Add(s5LootProp);

        var mmGroupProp = new SF.ScriptObjectListProperty { Name = "MinutemenGroup", Flags = SF.ScriptProperty.Flag.Edited };
        foreach (var gm in new[] { sturgesRefKey, mamaRef.FormKey, marcyRef.FormKey, junRef.FormKey }) mmGroupProp.Objects.Add(ObjProp("", gm));
        min00Script.Properties.Add(mmGroupProp);

        min00Script.Properties.Add(ObjProp("SturgesRef", sturgesRefKey));
        min00Script.Properties.Add(ObjProp("S4DisplayMusketRef", dispMusketRef.FormKey));
        var fcListProp = new SF.ScriptObjectListProperty { Name = "S4FusionCellRefs", Flags = SF.ScriptProperty.Flag.Edited };
        foreach (var fcr in fcRefs) fcListProp.Objects.Add(ObjProp("", fcr.FormKey));
        min00Script.Properties.Add(fcListProp);
        min00Script.Properties.Add(ObjProp("S6PrestonRoomScene", s6PrestonScene.FormKey));
        min00Script.Properties.Add(ObjProp("S6SturgesRoomScene", s6SturgesScene.FormKey));
        min00Script.Properties.Add(new SF.ScriptBoolProperty { Name = "StopAtFusionCorePowerArmor", Flags = SF.ScriptProperty.Flag.Edited, Data = true });
        min00Script.Properties.Add(new SF.ScriptIntProperty { Name = "LaserMusketId", Flags = SF.ScriptProperty.Flag.Edited, Data = (int)Fo4LaserMusketId });
        min00Script.Properties.Add(new SF.ScriptIntProperty { Name = "FusionCellId", Flags = SF.ScriptProperty.Flag.Edited, Data = (int)Fo4FusionCellId });
        min00Script.Properties.Add(new SF.ScriptIntProperty { Name = "BottlecapId", Flags = SF.ScriptProperty.Flag.Edited, Data = (int)Fo4CapsId });
    }

    public static void CheckS2S6Missions(
        SF.IStarfieldModGetter plug,
        List<string> problems,
        bool r11FullMission,
        bool fo4HumanAnims)
    {
        void Need(bool ok, string msg) { if (!ok) problems.Add(msg); }
        var key = plug.ModKey;

        if (!r11FullMission)
        {
            Need(!plug.Quests.Any(q => q.FormKey.ID == S2RoachesQuestId),
                 $"default build (--r11-full-mission 0) must not emit {S2RoachesQuestEdid} (0x{S2RoachesQuestId:X})");
            Need(!plug.Keywords.Any(k => k.FormKey.ID == Fo4AnimArchetypeKwId),
                 $"default build must not emit {Fo4AnimArchetypeKwEdid} (0x{Fo4AnimArchetypeKwId:X})");
            return;
        }

        // Holding cell (0xB60 FO4SF_MissionHoldingCell) + S2 Vault111Roaches
        var hc = plug.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(sb => sb.Cells).FirstOrDefault(c => c.FormKey == new FormKey(key, Mission.MissionHoldingCellId));
        Need(hc is { EditorID: Mission.MissionHoldingCellEdid }, $"R11 full mission lacks holding cell 0x{Mission.MissionHoldingCellId:X}");

        var s2q = plug.Quests.FirstOrDefault(q => q.FormKey == new FormKey(key, S2RoachesQuestId));
        Need(s2q is { EditorID: S2RoachesQuestEdid } && (s2q.Data?.Flags.HasFlag(SF.Quest.Flag.StartGameEnabled) == true),
             $"R11 full mission lacks StartGameEnabled {S2RoachesQuestEdid} (0x{S2RoachesQuestId:X})");

        // S3 Travel PACKs + markers
        Need(plug.Packages.Any(p => p.FormKey == new FormKey(key, S3PackHouse01Id)) &&
             plug.Packages.Any(p => p.FormKey == new FormKey(key, S3PackHouse02Id)),
             $"R11 full mission lacks S3 Travel PACKs (0x{S3PackHouse01Id:X}, 0x{S3PackHouse02Id:X})");

        var extRefs = plug.Worldspaces.SelectMany(w => w.TopCell?.Persistent.OfType<SF.IPlacedObjectGetter>() ?? []).ToDictionary(r => r.FormKey.ID);
        Need(!extRefs.ContainsKey(S3House01MarkerId) && !extRefs.ContainsKey(S3House2MarkerId) &&
             !extRefs.ContainsKey(S4DisplayMusketRefId) &&
             !Enumerable.Range(0, 6).Any(i => extRefs.ContainsKey(FirstS3BloatflyMarkerId + (uint)i)) &&
             !Enumerable.Range(0, 3).Any(i => extRefs.ContainsKey(FirstS4FusionCellRefId + (uint)i)),
             "NextStoryMissionsS2S6 exterior markers must live in holdingCell (0xB60), never FO4Core_Commonwealth WRLD");

        // Holding cell refs (5 S2 roaches + S3 markers/flies + S4 display pickups + 4 doors + 7 loot refs + 7 S5 raiders + 3 S6 3F NPCs)
        var holdObjs = (hc?.Persistent.OfType<SF.IPlacedObjectGetter>() ?? []).ToDictionary(r => r.FormKey.ID);
        var holdNpcs = (hc?.Persistent.OfType<SF.IPlacedNpcGetter>() ?? []).ToDictionary(r => r.FormKey.ID);
        Need(holdObjs.TryGetValue(S3House01MarkerId, out var h1r) && MathF.Abs(h1r.Position.X - S3House01Pos.X) < 0.1f && MathF.Abs(h1r.Position.Y - S3House01Pos.Y) < 0.1f,
             $"S3House01Marker (0x{S3House01MarkerId:X}) missing from holdingCell or not at (-2313.44, -1372.02, 112.66)");
        Need(holdObjs.TryGetValue(S3House2MarkerId, out var h2r) && MathF.Abs(h2r.Position.X - S3House02Pos.X) < 0.1f && MathF.Abs(h2r.Position.Y - S3House02Pos.Y) < 0.1f,
             $"S3House02Marker (0x{S3House2MarkerId:X}) missing from holdingCell or not at (-2296.17, -1424.97, 111.77)");
        Need(Enumerable.Range(0, 6).All(i => holdObjs.ContainsKey(FirstS3BloatflyMarkerId + (uint)i)), "S3 lacking 6 bloatfly markers (0xBA1..0xBA6) in holdingCell");
        Need(holdObjs.ContainsKey(S4DisplayMusketRefId) && Enumerable.Range(0, 3).All(i => holdObjs.ContainsKey(FirstS4FusionCellRefId + (uint)i)),
             "S4 Display Laser Musket (0xBA8) or 3 Fusion Cell pickups (0xBAA..0xBAC) missing from holdingCell");
        Need(Enumerable.Range(0, 5).All(i => holdObjs.ContainsKey(FirstS2RadroachMarkerId + (uint)i)), "S2 lacking 5 radroach markers (0xB91..0xB95)");
        Need(holdObjs.ContainsKey(S5ExtFrontInRefId) && holdObjs.ContainsKey(S5IntFrontOutRefId) && holdObjs.ContainsKey(S5IntRoofOutRefId) && holdObjs.ContainsKey(S5ExtRoofInRefId),
             "S5 lacking 4 confirmed-arrival doors (0xBB8..0xBBB)");
        Need(holdObjs.ContainsKey(S6BasementTermRefId) && holdObjs.ContainsKey(S6FusionCoreRefId) &&
             holdObjs.ContainsKey(FirstS5StimpakRefId) && holdObjs.ContainsKey(FirstS5StimpakRefId + 1) &&
             holdObjs.ContainsKey(S5CapsRefId) && holdObjs.ContainsKey(S5BobbyPinRefId) && holdObjs.ContainsKey(S5PipeWeaponRefId),
             "Museum S5/S6 loot or basement/fusion core refs missing");
        Need(Enumerable.Range(0, 7).All(i => holdNpcs.ContainsKey(FirstS5MuseumRaiderRefId + (uint)i)), "S5 lacking 7 museum raiders (0xBBC..0xBC2)");
        Need(holdNpcs.ContainsKey(MamaMurphyRefId) && holdNpcs.ContainsKey(MarcyLongRefId) && holdNpcs.ContainsKey(JunLongRefId),
             "S6 lacking 3F settlers (Mama Murphy, Marcy Long, Jun Long)");

        // Roof exit separation check (F9 parity: -1724.60 vs -1722.39)
        if (holdObjs.TryGetValue(S5IntRoofOutRefId, out var rOut))
        {
            var sc = rOut.VirtualMachineAdapter?.Scripts.FirstOrDefault(x => x.Name == LoadDoorScriptName);
            var yProp = sc?.Properties.FirstOrDefault(p => p.Name == "DestinationY") as SF.IScriptFloatPropertyGetter;
            Need(yProp is not null && MathF.Abs(yProp.Data - (-1724.60f)) < 0.05f, "S5IntRoofOutRef missing F9 separated DestinationY = -1724.60");
        }

        // --fo4-human-anims flag OFF default check
        bool hasAnimKw = plug.Keywords.Any(k => k.FormKey == new FormKey(key, Fo4AnimArchetypeKwId));
        var animGlob = plug.Globals.FirstOrDefault(g => g.FormKey == new FormKey(key, Fo4HumanAnimsEnabledGlobId));
        Need(hasAnimKw == fo4HumanAnims && MathF.Abs((animGlob?.Data ?? -1f) - (fo4HumanAnims ? 1f : 0f)) < 1e-4f,
             $"--fo4-human-anims {(fo4HumanAnims ? 1 : 0)} mismatch against KYWD 0x{Fo4AnimArchetypeKwId:X} and GLOB 0x{Fo4HumanAnimsEnabledGlobId:X}");
    }
}
