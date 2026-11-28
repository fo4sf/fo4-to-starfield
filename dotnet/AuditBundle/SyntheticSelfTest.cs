using System.Text.Json;
using Mutagen.Bethesda;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;

namespace AuditBundle;

static class SyntheticSelfTest
{
    public static int Run(string scratchDir)
    {
        string root = Path.GetFullPath(scratchDir);
        if (Directory.Exists(root)) Directory.Delete(root, true);
        Directory.CreateDirectory(root);

        string sfData = Path.Combine(root, "starfield", "Data");
        string bundleDir = Path.Combine(root, "bundle");
        string mmDir = Path.Combine(bundleDir, "map-markers");
        string scriptsDir = Path.Combine(root, "repo_scripts");
        Directory.CreateDirectory(sfData);
        Directory.CreateDirectory(bundleDir);
        Directory.CreateDirectory(mmDir);
        Directory.CreateDirectory(scriptsDir);

        var rel = StarfieldRelease.Starfield;
        var sfKey = ModKey.FromFileName("Starfield.esm");
        var bgsKey = ModKey.FromFileName("SFBGS004.esm");
        var portKey = ModKey.FromFileName("FO4Port.esm");
        var coreKey = ModKey.FromFileName("FO4TerrainCore.esm");
        var ngKey = ModKey.FromFileName("FO4SFNewGame.esm");
        var mmKey = ModKey.FromFileName("FO4SFMapMarkers.esm");

        // 1. Synthetic Starfield.esm: StartupQuest_DO, MQ101, MapMarker STAT, XMarker STAT, 2 LSCRs, Mars WRLD/LCTN
        var sf = new StarfieldMod(sfKey, rel);
        sf.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        var mq101 = new Quest(new FormKey(sfKey, 0x003448), rel) { EditorID = "MQ101" };
        sf.Quests.Add(mq101);
        sf.DefaultObjects.Add(new DefaultObject(new FormKey(sfKey, 0x00562D), rel)
        {
            EditorID = "StartupQuest_DO",
            Object = new FormLinkNullable<IStarfieldMajorRecordGetter>(mq101.FormKey),
        });
        sf.Statics.Add(new Static(new FormKey(sfKey, 0x000010), rel) { EditorID = "MapMarker" });
        sf.Statics.Add(new Static(new FormKey(sfKey, 0x00003B), rel) { EditorID = "XMarker" });
        sf.Locations.Add(new Location(new FormKey(sfKey, 0x000999), rel) { EditorID = "MarsLocation", Name = "Mars" });
        sf.LoadScreens.Add(new LoadScreen(new FormKey(sfKey, 0x000700), rel) { EditorID = "SynthLSCR_1" });
        sf.LoadScreens.Add(new LoadScreen(new FormKey(sfKey, 0x000701), rel) { EditorID = "SynthLSCR_2" });
        sf.BeginWrite.ToPath(Path.Combine(sfData, sfKey.FileName)).WithNoLoadOrder().NoCheckIfLowerRangeDisallowed().Write();

        // 2. Synthetic SFBGS004.esm (Small master 0x0100 + Master 0x0001) with 1 LSCR
        var bgs = new StarfieldMod(bgsKey, rel);
        bgs.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master | (StarfieldModHeader.HeaderFlag)0x0100;
        bgs.LoadScreens.Add(new LoadScreen(new FormKey(bgsKey, 0x000800), rel) { EditorID = "SynthBgsLSCR" });
        bgs.BeginWrite.ToPath(Path.Combine(sfData, bgsKey.FileName)).WithNoLoadOrder().NoCheckIfLowerRangeDisallowed().Write();

        var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        styles.Set(new KeyedMasterStyle(sfKey, MasterStyle.Full));
        styles.Set(new KeyedMasterStyle(bgsKey, MasterStyle.Small));
        styles.Set(new KeyedMasterStyle(portKey, MasterStyle.Full));
        styles.Set(new KeyedMasterStyle(coreKey, MasterStyle.Full));
        styles.Set(new KeyedMasterStyle(ngKey, MasterStyle.Full));
        styles.Set(new KeyedMasterStyle(mmKey, MasterStyle.Full));

        // 3. Synthetic FO4Port.esm (interior cell with persistent ref 0x1618)
        var port = new StarfieldMod(portKey, rel);
        port.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        var vcell = new Cell(new FormKey(portKey, 0x0011F3), rel) { EditorID = "FO4Port_Vault111Cryo" };
        vcell.Persistent.Add(new PlacedObject(new FormKey(portKey, 0x001618), rel)
        {
            EditorID = "FO4Port_ExitLiftRef",
            Base = new FormLinkNullable<IPlaceableObjectGetter>(new FormKey(sfKey, 0x00003B)),
            Position = new P3Float(1, 2, 3),
        });
        port.Cells.Records.Add(new CellBlock { BlockNumber = 0, SubBlocks = { new CellSubBlock { BlockNumber = 0, Cells = { vcell } } } });
        string portPath = Path.Combine(root, portKey.FileName);
        port.BeginWrite.ToPath(portPath).WithLoadOrder(new[] { sfKey })
            .WithKnownMasters(new[] { new KeyedMasterStyle(sfKey, MasterStyle.Full) })
            .WithExtraIncludedMasters(new[] { sfKey }).Write();

        // 4. Synthetic FO4TerrainCore.esm (world + raw map marker 0x0A775B + anchor 0x000800)
        var core = new StarfieldMod(coreKey, rel);
        core.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        var cw = new Worldspace(new FormKey(coreKey, 0x000803), rel) { EditorID = "FO4Core_Commonwealth" };
        var markerV111 = new PlacedObject(new FormKey(coreKey, 0x0A775B), rel)
        {
            EditorID = "FO4Core_CommonwealthMapMarkerVault111",
            Base = new FormLinkNullable<IPlaceableObjectGetter>(new FormKey(sfKey, 0x000010)),
            Position = new P3Float(-1275.31f, 1305.28f, 127.21f),
            MapMarker = new PlacedObjectMapMarker { Name = "Vault 111" },
        };
        var anchor = new PlacedObject(new FormKey(coreKey, 0x000800), rel)
        {
            EditorID = "FO4Core_CommonwealthAnchor",
            Base = new FormLinkNullable<IPlaceableObjectGetter>(new FormKey(sfKey, 0x00003B)),
            Position = new P3Float(-989.26f, 1146.51f, 107.14f),
        };
        cw.TopCell = new Cell(new FormKey(coreKey, 0x001805), rel) { Persistent = { anchor, markerV111 } };
        core.Worldspaces.Add(cw);
        core.BeginWrite.ToPath(Path.Combine(bundleDir, coreKey.FileName)).WithLoadOrder(new[] { sfKey })
            .WithKnownMasters(new[] { new KeyedMasterStyle(sfKey, MasterStyle.Full) })
            .WithExtraIncludedMasters(new[] { sfKey }).Write();

        // 5. Synthetic FO4SFNewGame.esm (StartupQuest_DO override + StartGameEnabled QUST + broken/wrong-type/cross-plugin VMAD + MESG)
        var unloadedKey = ModKey.FromFileName("FO4UnloadedMaster.esm");
        var ng = new StarfieldMod(ngKey, rel);
        ng.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        var ngQuest = new Quest(new FormKey(ngKey, 0x000800), rel)
        {
            EditorID = "FO4SF_NewGame",
            Data = new QuestData { Flags = Quest.Flag.StartGameEnabled },
        };
        var msg = new Message(new FormKey(ngKey, 0x000801), rel) { EditorID = "FO4SF_NewGameElevator", Name = "SynthPrompt" };
        ng.Messages.Add(msg);
        ngQuest.VirtualMachineAdapter = new QuestAdapter
        {
            Scripts =
            {
                new ScriptEntry
                {
                    Name = "SynthNewGameScript",
                    Properties =
                    {
                        new ScriptObjectProperty { Name = "NoneProp", Object = new FormLink<IStarfieldMajorRecordGetter>(FormKey.Null) },
                        new ScriptObjectProperty { Name = "CrossAnchor", Object = new FormLink<IStarfieldMajorRecordGetter>(markerV111.FormKey) },
                        new ScriptObjectProperty { Name = "UnloadedMasterProp", Object = new FormLink<IStarfieldMajorRecordGetter>(new FormKey(unloadedKey, 0x000800)) },
                        new ScriptObjectProperty { Name = "WrongTypeProp", Object = new FormLink<IStarfieldMajorRecordGetter>(msg.FormKey) },
                    },
                },
            },
        };
        ng.Quests.Add(ngQuest);
        ng.DefaultObjects.Add(new DefaultObject(new FormKey(sfKey, 0x00562D), rel)
        {
            EditorID = "StartupQuest_DO",
            Object = new FormLinkNullable<IStarfieldMajorRecordGetter>(ngQuest.FormKey),
        });
        ng.BeginWrite.ToPath(Path.Combine(bundleDir, ngKey.FileName))
            .WithLoadOrder(new[] { sfKey, coreKey, unloadedKey })
            .WithKnownMasters(new[]
            {
                new KeyedMasterStyle(sfKey, MasterStyle.Full),
                new KeyedMasterStyle(coreKey, MasterStyle.Full),
                new KeyedMasterStyle(unloadedKey, MasterStyle.Full),
            })
            .WithExtraIncludedMasters(new[] { sfKey, coreKey, unloadedKey }).Write();

        // 6. Synthetic FO4SFMapMarkers.esm (overrides markerV111 + lists it in Markers[0] -> shared record + SGE quest)
        var mm = new StarfieldMod(mmKey, rel);
        mm.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        var mmCw = new Worldspace(cw.FormKey, rel)
        {
            EditorID = cw.EditorID,
            TopCell = new Cell(cw.TopCell.FormKey, rel)
            {
                Persistent =
                {
                    new PlacedObject(markerV111.FormKey, rel)
                    {
                        EditorID = markerV111.EditorID,
                        Base = new FormLinkNullable<IPlaceableObjectGetter>(new FormKey(sfKey, 0x000010)),
                        Position = new P3Float(-1275.31f, 1305.28f, 129.71f),
                        MapMarker = new PlacedObjectMapMarker { Name = "Vault 111" },
                    },
                },
            },
        };
        mm.Worldspaces.Add(mmCw);
        mm.Quests.Add(new Quest(new FormKey(mmKey, 0x000800), rel)
        {
            EditorID = "FO4SF_MapMarkersQuest",
            Data = new QuestData { Flags = Quest.Flag.StartGameEnabled },
            VirtualMachineAdapter = new QuestAdapter
            {
                Scripts =
                {
                    new ScriptEntry
                    {
                        Name = "FO4SF_MapMarkers",
                        Properties =
                        {
                            new ScriptObjectListProperty
                            {
                                Name = "Markers",
                                Objects = { new ScriptObjectProperty { Object = new FormLink<IStarfieldMajorRecordGetter>(markerV111.FormKey) } },
                            },
                        },
                    },
                },
            },
        });
        string mmPath = Path.Combine(mmDir, mmKey.FileName);
        mm.BeginWrite.ToPath(mmPath).WithLoadOrder(new[] { sfKey, coreKey })
            .WithKnownMasters(new[] { new KeyedMasterStyle(sfKey, MasterStyle.Full), new KeyedMasterStyle(coreKey, MasterStyle.Full) })
            .WithExtraIncludedMasters(new[] { sfKey, coreKey }).Write();

        // Write synthetic bundle_plan.json and synthetic .psc declaring WrongTypeProp as Actor (while bound to MESG!)
        File.WriteAllText(Path.Combine(bundleDir, "bundle_plan.json"), JsonSerializer.Serialize(new
        {
            plugins = new[] { coreKey.FileName.String, ngKey.FileName.String },
        }));
        File.WriteAllText(Path.Combine(scriptsDir, "SynthNewGameScript.psc"),
            "Scriptname SynthNewGameScript extends Quest\n" +
            "ObjectReference Property NoneProp Auto\n" +
            "ObjectReference Property CrossAnchor Auto\n" +
            "ObjectReference Property UnloadedMasterProp Auto\n" +
            "Actor Property WrongTypeProp Auto\n" +
            "Event OnQuestInit()\n" +
            "    StartTimer(1.0, 1)\n" +
            "EndEvent\n");

        string outJson = Path.Combine(root, "audit_out.json");
        var report = BundleAuditor.Run(bundleDir, portPath, outJson, sfData, mmPath, scriptsDir);
        File.WriteAllText(outJson, JsonSerializer.Serialize(report, new JsonSerializerOptions { WriteIndented = true }));

        static void Require(bool cond, string msg)
        {
            if (!cond) throw new InvalidOperationException("selftest failed: " + msg);
        }

        Require(report.Overrides.OfficialOverrideCount == 1, $"expected 1 official override, got {report.Overrides.OfficialOverrideCount}");
        Require(report.SharedRecords.FocusForms.Any(f => f.FormKey == markerV111.FormKey.ToString() && f.PluginTouchCount == 3),
            "expected synthetic markerV111 touched by 3 plugins (core, newgame, mapmarkers)");
        Require(report.SharedRecords.MapMarkerInventory.Markers.Count == 1,
            $"expected 1 map marker detail, got {report.SharedRecords.MapMarkerInventory.Markers.Count}");
        Require(report.ScriptBindings.NonePropertyCount == 1, $"expected 1 none_property, got {report.ScriptBindings.NonePropertyCount}");
        Require(report.ScriptBindings.MissingMasterCrossPluginCount >= 1, "expected missing_master_for_cross_plugin flagged for CrossAnchor");
        Require(report.ScriptBindings.WrongTypeCount == 1, $"expected 1 wrong_type binding, got {report.ScriptBindings.WrongTypeCount}");
        Require(report.UnpromptedExecution.StartGameEnabledQuests.Count == 2, "expected 2 start-game-enabled quests");
        Require(report.UnpromptedExecution.AttachedUnpromptedScripts.Any(s => s.ScriptName == "SynthNewGameScript" && s.Hooks.Count == 2),
            "expected OnQuestInit + StartTimer hooks detected");
        Require(report.PersistentReferences.TotalPersistentRefs >= 4, "expected >= 4 persistent refs");
        Require(report.StarfieldLeftovers.OfficialLscrTotal == 3, $"expected 3 official LSCRs, got {report.StarfieldLeftovers.OfficialLscrTotal}");
        Require(report.StarfieldLeftovers.Messages.Count == 1, "expected 1 message");

        Console.WriteLine($"audit-bundle selftest OK: official_overrides={report.Overrides.OfficialOverrideCount}, " +
                          $"shared={report.SharedRecords.AllSharedCount}, none_props={report.ScriptBindings.NonePropertyCount}, " +
                          $"wrong_type={report.ScriptBindings.WrongTypeCount}, lscr_official={report.StarfieldLeftovers.OfficialLscrTotal}");
        return 0;
    }
}
