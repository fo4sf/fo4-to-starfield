using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;

internal static class Ws0aProbes
{
    private const StarfieldRelease Release = StarfieldRelease.Starfield;
    private static readonly ModKey SfEsm = ModKey.FromFileName("Starfield.esm");
    private static readonly ModKey Sfbgs00dEsm = ModKey.FromFileName("SFBGS00D.esm");
    public static readonly ModKey Ws0aAddon = ModKey.FromFileName("FO4SFWorkshopProbe.esm");
    public static readonly ModKey P6Addon = ModKey.FromFileName("FO4SFWorkshopProbe_P6.esm");

    // Local FormIDs in FO4SFWorkshopProbe.esm (0x810..0x86F, disjoint from base WorkshopProbe 0x800..0x804)
    public const uint Ws0aQuestId = 0x810;
    public const uint P18BenchActiId = 0x820;
    public const uint P14aCotFurnId = 0x821;
    public const uint P14bTurretActiId = 0x822;
    public const uint P4GenActiId = 0x823;
    public const uint P4LightActiId = 0x824;
    public const uint P9LooseStaticId = 0x825;
    public const uint P16SteelMiscId = 0x826;
    public const uint P17StorageContId = 0x827;
    public const uint P17JunkMiscId = 0x828;
    public const uint P5ExtractorActiId = 0x82A;

    public const uint P18BenchKwId = 0x830;
    public const uint P12TestPerkId = 0x831;
    public const uint P14aBedsAvId = 0x832;
    public const uint P14bSafetyAvId = 0x833;
    public const uint P8bLocAId = 0x834;
    public const uint P8bLocBId = 0x835;

    public const uint P18CobjStructId = 0x840;
    public const uint P18CobjFurnId = 0x841;
    public const uint P18CobjMiscId = 0x842;
    public const uint P12CobjPerkId = 0x843;
    public const uint P9CobjBulldozeId = 0x844;
    public const uint P16CobjSteelId = 0x845;
    public const uint P5CobjExtractorId = 0x846;

    // P6 addon local IDs (FO4SFWorkshopProbe_P6.esm, masters [Starfield.esm, SFBGS00D.esm])
    public const uint P6SharedContId = 0x800;
    public const uint P6SharedCobjId = 0x801;

    // Starfield.esm known FormIDs verified offline
    private const uint SfWorkshopKw = 0x054BA7;
    private const uint SfFlstOutpostCategories = 0x058606;
    private const uint SfOutpostCategoryStructures = 0x2A7578;
    private const uint SfOutpostCategoryFurniture = 0x2BE3B5;
    private const uint SfOutpostCategoryMisc = 0x06D72D;
    private const uint SfOutpostCategoryBulldoze = 0x127E9B;
    private const uint SfOutpostAllowBulldozeKw = 0x38E354;
    private const uint SfBulldozeCobj = 0x178B12;
    private const uint SfSkipVeinAv = 0x271128;
    private const uint SfAllowPlacementCndf = 0x2DFD42;
    private const uint SfBulldozeAlwaysAv = 0x21C778;
    private const uint SfIronIres = 0x0057C7;
    private const uint SfIronMisc = 0x00556E;

    // SFBGS00D.esm known FormIDs verified offline
    private const uint DlcSharedContId = 0x02AF77;
    private const uint DlcSharedCobjId = 0x02AF79;

    public static readonly ushort[] Ws0aStages =
    {
        101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122
    };

    private static FormKey Own(uint id) => new(Ws0aAddon, id);
    private static FormKey P6Own(uint id) => new(P6Addon, id);
    private static FormKey Sf(uint id) => new(SfEsm, id);
    private static FormKey Dlc(uint id) => new(Sfbgs00dEsm, id);

    private static IStarfieldModDisposableGetter Open(string path, params ModKey[] masters)
    {
        var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        foreach (var m in masters) styles.Set(new KeyedMasterStyle(m, MasterStyle.Full));
        return StarfieldMod.CreateFromBinaryOverlay(path, Release, new BinaryReadParameters { MasterFlagsLookup = styles });
    }

    private static void WriteAtomic(StarfieldMod mod, string outDir, params ModKey[] masters)
    {
        Directory.CreateDirectory(outDir);
        var path = Path.Combine(outDir, mod.ModKey.FileName);
        var tmpDir = Path.Combine(outDir, ".tmp-" + Guid.NewGuid().ToString("N"));
        try
        {
            Directory.CreateDirectory(tmpDir);
            var tmp = Path.Combine(tmpDir, mod.ModKey.FileName);
            mod.BeginWrite.ToPath(tmp)
                .WithLoadOrder(masters)
                .WithKnownMasters(masters.Select(m => new KeyedMasterStyle(m, MasterStyle.Full)).ToArray())
                .WithMastersListContent(MastersListContentOption.NoCheck)
                .NoCheckIfLowerRangeDisallowed()
                .Write();
            File.Move(tmp, path, overwrite: true);
        }
        finally
        {
            if (Directory.Exists(tmpDir)) Directory.Delete(tmpDir, true);
        }
    }

    public static int Build(string sfPath, string outDir, string? dlcPath)
    {
        using var sf = Open(sfPath, SfEsm);
        var mod = new StarfieldMod(Ws0aAddon, Release);
        mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        mod.ModHeader.Author = "fo4-to-starfield";

        // Preserve original base WorkshopProbe 0x800..0x804 records cleanly so both quests coexist
        var item = sf.MiscItems.FirstOrDefault(x => x.FormKey == Sf(SfIronMisc))
            ?? sf.MiscItems.FirstOrDefault(x => x.Model != null && !string.IsNullOrEmpty(x.EditorID))
            ?? throw new InvalidOperationException("No MISC template in Starfield.esm");
        foreach (var (kid, ed, nm) in new[] {
            (0x802u, "FO4SF_WSKit", "FO4SF workshop kit"),
            (0x803u, "FO4SF_WSBeaconKit", "FO4SF beacon kit"),
            (0x804u, "FO4SF_WSResKit", "FO4SF resource kit"),
        })
        {
            var k = (MiscItem)item.Duplicate(Own(kid), new MiscItem.TranslationMask(defaultOn: true) { Name = false });
            k.EditorID = ed;
            k.Name = nm;
            k.VirtualMachineAdapter = null;
            mod.MiscItems.Add(k);
        }

        Quest MakeQuest(uint id, string ed, string nm, string sc, IEnumerable<ushort> stages)
        {
            var q = new Quest(Own(id), Release)
            {
                EditorID = ed,
                Name = nm,
                FormVersion = 581,
                Version2 = 12,
                Data = new QuestData { Flags = Quest.Flag.StartGameEnabled, Priority = 30 },
            };
            foreach (var s in stages) q.Stages.Add(new QuestStage { Index = s });
            q.VirtualMachineAdapter = new QuestAdapter
            {
                Version = 6,
                ObjectFormat = 2,
                ExtraBindDataVersion = 3,
                Script = new ScriptEntry { Name = "", Flags = ScriptEntry.Flag.Local },
            };
            q.VirtualMachineAdapter.Scripts.Add(new ScriptEntry { Name = sc, Flags = ScriptEntry.Flag.Local });
            return q;
        }
        mod.Quests.Add(MakeQuest(0x800, "FO4SF_WSProbeQuest", "FO4SF workshop probe", "FO4SF_WSProbeQuest",
            new ushort[] { 10, 12, 13, 20, 21, 22, 23, 24, 30, 31, 32, 33, 34, 40, 50, 60 }));
        mod.Quests.Add(MakeQuest(0x801, "FO4SF_WSHandQuest", "FO4SF workshop by hand", "FO4SF_WSHandQuest", new ushort[] { 10 }));
        mod.Quests.Add(MakeQuest(Ws0aQuestId, "FO4SF_WS0aProbeQuest", "FO4SF WS0a Tier1-3 probe", "FO4SF_WS0aProbeQuest", Ws0aStages));

        // Keywords, Perks, ActorValues, Locations
        var p18BenchKw = new Keyword(Own(P18BenchKwId), Release)
        {
            EditorID = "FO4SF_P18WorkbenchKeyword",
            Name = "FO4 P18 Workbench",
            Type = Keyword.TypeEnum.None,
        };
        mod.Keywords.Add(p18BenchKw);

        var p12Perk = new Perk(Own(P12TestPerkId), Release)
        {
            EditorID = "FO4SF_P12TestPerk",
            Name = "WS0a Probe Gate Perk",
            Description = "Test-kit only perk for P12 RQPK verification.",
        };
        mod.Perks.Add(p12Perk);

        var p14aBedsAv = new ActorValueInformation(Own(P14aBedsAvId), Release)
        {
            EditorID = "FO4SF_P14aBedsAV",
            Name = "FO4SF Test Beds",
            DefaultValue = 0.0f,
        };
        var p14bSafetyAv = new ActorValueInformation(Own(P14bSafetyAvId), Release)
        {
            EditorID = "FO4SF_P14bSafetyAV",
            Name = "FO4SF Test Safety",
            DefaultValue = 0.0f,
        };
        mod.ActorValueInformation.Add(p14aBedsAv);
        mod.ActorValueInformation.Add(p14bSafetyAv);

        mod.Locations.Add(new Location(Own(P8bLocAId), Release) { EditorID = "FO4SF_P8bLocA", Name = "WS0a Probe Loc A" });
        mod.Locations.Add(new Location(Own(P8bLocBId), Release) { EditorID = "FO4SF_P8bLocB", Name = "WS0a Probe Loc B" });

        // Test-kit objects (P18 bench, P14a cot, P14b turret, P4 gen/light, P9 loose static, P16 steel, P17 storage/junk, P5 extractor)
        var benchTpl = sf.Activators.FirstOrDefault(a => a.Keywords != null && a.Keywords.Any(k => k.FormKey == Sf(SfWorkshopKw)))
            ?? sf.Activators.FirstOrDefault(a => a.Model != null);
        var p18Bench = new Mutagen.Bethesda.Starfield.Activator(Own(P18BenchActiId), Release)
        {
            EditorID = "FO4SF_P18TestBench",
            Name = "WS0a P18 Test Workbench",
            Model = new Model { File = benchTpl?.Model?.File?.GivenPath ?? "Meshes\\Outpost\\Beacon.nif" },
            Keywords = new ExtendedList<IFormLinkGetter<IKeywordGetter>>
            {
                Sf(SfWorkshopKw).ToLinkGetter<IKeywordGetter>(),
                Own(P18BenchKwId).ToLinkGetter<IKeywordGetter>(),
            },
        };
        mod.Activators.Add(p18Bench);

        var p14aCot = new Furniture(Own(P14aCotFurnId), Release)
        {
            EditorID = "FO4SF_P14aTestCot",
            Name = "WS0a P14a Test Cot",
            Model = new Model { File = "Furniture\\Chairs\\Generic\\AK_Chair_Wood_01.nif" },
            Properties = new ExtendedList<ObjectProperty>
            {
                new ObjectProperty { ActorValue = Own(P14aBedsAvId).ToLink<IActorValueInformationGetter>(), Value = 1.0f },
            },
        };
        mod.Furniture.Add(p14aCot);

        var safetyPropList = new ExtendedList<ObjectProperty>
        {
            new ObjectProperty { ActorValue = Own(P14bSafetyAvId).ToLink<IActorValueInformationGetter>(), Value = 2.0f },
        };
        var sfSafety = sf.ActorValueInformation.FirstOrDefault(av => string.Equals(av.EditorID, "Safety", StringComparison.OrdinalIgnoreCase));
        if (sfSafety != null)
            safetyPropList.Add(new ObjectProperty { ActorValue = sfSafety.FormKey.ToLink<IActorValueInformationGetter>(), Value = 2.0f });

        mod.Activators.Add(new Mutagen.Bethesda.Starfield.Activator(Own(P14bTurretActiId), Release)
        {
            EditorID = "FO4SF_P14bTestSafetyObj",
            Name = "WS0a P14b Safety Object",
            Model = new Model { File = "Meshes\\Props\\DeskFan03.nif" },
            Properties = safetyPropList,
        });

        mod.Activators.Add(new Mutagen.Bethesda.Starfield.Activator(Own(P4GenActiId), Release)
        {
            EditorID = "FO4SF_P4TestGenerator",
            Name = "WS0a P4 Generator",
            Model = new Model { File = "Meshes\\Props\\DeskFan03.nif" },
        });
        mod.Activators.Add(new Mutagen.Bethesda.Starfield.Activator(Own(P4LightActiId), Release)
        {
            EditorID = "FO4SF_P4TestLight",
            Name = "WS0a P4 Powered Light",
            Model = new Model { File = "Meshes\\Props\\DeskFan03.nif" },
        });

        mod.Statics.Add(new Static(Own(P9LooseStaticId), Release)
        {
            EditorID = "FO4SF_P9BulldozeStatic",
            Model = new Model { File = "Meshes\\Props\\DeskFan03.nif" },
            Properties = new ExtendedList<ObjectProperty>
            {
                new ObjectProperty { ActorValue = Sf(SfBulldozeAlwaysAv).ToLink<IActorValueInformationGetter>(), Value = 1.0f },
            },
        });
        mod.Activators.Add(new Mutagen.Bethesda.Starfield.Activator(Own(0x82D), Release)
        {
            EditorID = "FO4SF_P9BulldozeTaggedActi",
            Name = "WS0a P9 Bulldoze Tagged",
            Model = new Model { File = "Meshes\\Props\\DeskFan03.nif" },
            Keywords = new ExtendedList<IFormLinkGetter<IKeywordGetter>> { Sf(SfOutpostAllowBulldozeKw).ToLinkGetter<IKeywordGetter>() },
            Properties = new ExtendedList<ObjectProperty>
            {
                new ObjectProperty { ActorValue = Sf(SfBulldozeAlwaysAv).ToLink<IActorValueInformationGetter>(), Value = 1.0f },
            },
        });

        var steelRes = sf.Resources.FirstOrDefault(r => r.FormKey == Sf(SfIronIres))?.FormKey ?? Own(P16SteelMiscId);
        var p16Steel = (MiscItem)item.Duplicate(Own(P16SteelMiscId), new MiscItem.TranslationMask(defaultOn: true) { Name = false });
        p16Steel.EditorID = "FO4SF_P16TestSteel";
        p16Steel.Name = "FO4SF Test Steel";
        p16Steel.VirtualMachineAdapter = null;
        mod.MiscItems.Add(p16Steel);

        var p17Junk = (MiscItem)item.Duplicate(Own(P17JunkMiscId), new MiscItem.TranslationMask(defaultOn: true) { Name = false });
        p17Junk.EditorID = "FO4SF_P17TestJunkSteel";
        p17Junk.Name = "WS0a Junk Steel Scrap";
        p17Junk.VirtualMachineAdapter = null;
        p17Junk.Resources = new ExtendedList<ItemResource>
        {
            new ItemResource { Resource = new FormLink<IResourceGetter>(steelRes), Count = 4 },
        };
        mod.MiscItems.Add(p17Junk);

        mod.Containers.Add(new Container(Own(P17StorageContId), Release)
        {
            EditorID = "FO4SF_P17TestStorage",
            Name = "WS0a P17 Junk Storage",
            Model = new Model { File = "SetDressing\\Toolbox_Kits\\ToolBox_SetA_03.nif" },
            Items = new ExtendedList<ContainerEntry>
            {
                new ContainerEntry { Item = new ContainerItem { Item = Own(P17JunkMiscId).ToLink<IItemGetter>(), Count = 5 } },
            },
        });

        mod.Activators.Add(new Mutagen.Bethesda.Starfield.Activator(Own(P5ExtractorActiId), Release)
        {
            EditorID = "FO4SF_P5TestExtractor",
            Name = "WS0a P5 Extractor",
            Model = new Model { File = "Meshes\\Props\\DeskFan03.nif" },
            Properties = new ExtendedList<ObjectProperty>
            {
                new ObjectProperty { ActorValue = Sf(SfSkipVeinAv).ToLink<IActorValueInformationGetter>(), Value = 1.0f },
            },
        });

        // Resolve Starfield category filters dynamically from FLST 058606 (fallback to known verified IDs)
        var fl058606 = sf.FormLists.FirstOrDefault(f => f.FormKey == Sf(SfFlstOutpostCategories));
        FormKey PickCat(uint preferred) =>
            (fl058606 != null && fl058606.Items.Any(i => i.FormKey == Sf(preferred))) ? Sf(preferred) : Sf(preferred);

        ConstructibleObject MakeCobj(uint id, string ed, FormKey benchKw, FormKey? filterKw, FormKey created, FormKey costItem, uint costCount, float sort)
        {
            var c = new ConstructibleObject(Own(id), Release)
            {
                EditorID = ed,
                Description = ed,
                AmountProduced = 1,
                MenuSortOrder = sort,
                LearnMethod = ConstructibleObject.LearnMethodEnum.DefaultOrConditions,
            };
            c.WorkbenchKeyword.SetTo(benchKw);
            if (filterKw.HasValue)
                c.RecipeFilters = new ExtendedList<IFormLinkGetter<IKeywordGetter>> { filterKw.Value.ToLinkGetter<IKeywordGetter>() };
            c.CreatedObject.SetTo(created);
            if (!costItem.IsNull && costCount > 0)
            {
                var cc = new ConstructibleObjectComponent { RequiredCount = costCount };
                cc.Component.SetTo(costItem);
                c.ConstructableComponents = new ExtendedList<ConstructibleObjectComponent> { cc };
            }
            return c;
        }

        // P18: recipes scoped to P18BenchKwId, filed under Structures / Furniture / Miscellaneous from FLST 058606
        mod.ConstructibleObjects.Add(MakeCobj(P18CobjStructId, "FO4SF_P18CobjStructures", Own(P18BenchKwId), PickCat(SfOutpostCategoryStructures), Own(P9LooseStaticId), Sf(SfIronIres), 1, 1.0f));
        mod.ConstructibleObjects.Add(MakeCobj(P18CobjFurnId, "FO4SF_P18CobjFurniture", Own(P18BenchKwId), PickCat(SfOutpostCategoryFurniture), Own(P14aCotFurnId), Sf(SfIronIres), 1, 2.0f));
        mod.ConstructibleObjects.Add(MakeCobj(P18CobjMiscId, "FO4SF_P18CobjMisc", Own(P18BenchKwId), PickCat(SfOutpostCategoryMisc), Own(P14bTurretActiId), Sf(SfIronIres), 1, 3.0f));

        // P12: recipe requiring our own FO4SF_P12TestPerk
        var cP12 = MakeCobj(P12CobjPerkId, "FO4SF_P12CobjPerkGated", Own(P18BenchKwId), PickCat(SfOutpostCategoryMisc), Own(P14bTurretActiId), Sf(SfIronIres), 1, 4.0f);
        cP12.RequiredPerks = new ExtendedList<ConstructibleRequiredPerk>
        {
            new ConstructibleRequiredPerk { Perk = Own(P12TestPerkId).ToLink<IPerkGetter>(), Rank = 1 },
        };
        mod.ConstructibleObjects.Add(cP12);

        // P9: ungated bulldozer copy under OutpostCategoryBulldoze
        var bulldozeTpl = sf.ConstructibleObjects.FirstOrDefault(c => c.FormKey == Sf(SfBulldozeCobj));
        if (bulldozeTpl != null)
        {
            var bd = (ConstructibleObject)bulldozeTpl.Duplicate(Own(P9CobjBulldozeId), new ConstructibleObject.TranslationMask(defaultOn: true));
            bd.EditorID = "FO4SF_P9CobjBulldoze";
            bd.Conditions.Clear();
            bd.RequiredPerks?.Clear();
            bd.RecipeFilters = new ExtendedList<IFormLinkGetter<IKeywordGetter>> { Sf(SfOutpostCategoryBulldoze).ToLinkGetter<IKeywordGetter>() };
            mod.ConstructibleObjects.Add(bd);
        }
        else
        {
            mod.ConstructibleObjects.Add(MakeCobj(P9CobjBulldozeId, "FO4SF_P9CobjBulldoze", Sf(SfWorkshopKw), Sf(SfOutpostCategoryBulldoze), Own(P9LooseStaticId), Sf(SfIronIres), 1, 5.0f));
        }

        // P16 & P5 recipes
        mod.ConstructibleObjects.Add(MakeCobj(P16CobjSteelId, "FO4SF_P16CobjOwnSteel", Own(P18BenchKwId), PickCat(SfOutpostCategoryMisc), Own(P9LooseStaticId), Own(P16SteelMiscId), 2, 6.0f));
        mod.ConstructibleObjects.Add(MakeCobj(P5CobjExtractorId, "FO4SF_P5CobjExtractor", Sf(SfWorkshopKw), PickCat(SfOutpostCategoryMisc), Own(P5ExtractorActiId), Sf(SfIronIres), 1, 7.0f));

        // P10: test-kit only override of OutpostAllowPlacementConditions (never allowed in player plugins!)
        var cndfTpl = sf.ConditionRecords.FirstOrDefault(c => c.FormKey == Sf(SfAllowPlacementCndf));
        if (cndfTpl != null)
        {
            var cndfCopy = cndfTpl.DeepCopy();
            cndfCopy.Conditions.Clear();
            mod.ConditionRecords.Add(cndfCopy);
        }

        mod.ModHeader.Stats.NextFormID = 0x860;
        if (!mod.ModHeader.MasterReferences.Any(m => m.Master == SfEsm))
            mod.ModHeader.MasterReferences.Add(new MasterReference { Master = SfEsm });
        WriteAtomic(mod, outDir, SfEsm);

        // Optional P6 addon for SFBGS00D.esm Shared Outpost Container (isolated test-kit plugin)
        if (!string.IsNullOrEmpty(dlcPath) && File.Exists(dlcPath))
        {
            using var dlc = Open(dlcPath, SfEsm, Sfbgs00dEsm);
            var p6 = new StarfieldMod(P6Addon, Release);
            p6.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
            p6.ModHeader.Author = "fo4-to-starfield";
            FormKey contOut = P6Own(P6SharedContId);
            var contSrc = dlc.Containers.FirstOrDefault(c => c.FormKey == Dlc(DlcSharedContId));
            if (contSrc != null)
            {
                var c = (Container)contSrc.Duplicate(contOut, new Container.TranslationMask(defaultOn: true));
                c.EditorID = "FO4SF_P6SharedOutpostContainer";
                c.Name = "WS0a P6 Shared Container";
                p6.Containers.Add(c);
            }
            var cobjSrc = dlc.ConstructibleObjects.FirstOrDefault(c => c.FormKey == Dlc(DlcSharedCobjId));
            if (cobjSrc != null)
            {
                var r = (ConstructibleObject)cobjSrc.Duplicate(P6Own(P6SharedCobjId), new ConstructibleObject.TranslationMask(defaultOn: true));
                r.EditorID = "FO4SF_P6SharedOutpostCobj";
                r.CreatedObject.SetTo(contOut);
                r.Conditions.Clear();
                r.RequiredPerks?.Clear();
                p6.ConstructibleObjects.Add(r);
            }
            p6.ModHeader.Stats.NextFormID = 0x810;
            p6.ModHeader.MasterReferences.Add(new MasterReference { Master = SfEsm });
            p6.ModHeader.MasterReferences.Add(new MasterReference { Master = Sfbgs00dEsm });
            WriteAtomic(p6, outDir, SfEsm, Sfbgs00dEsm);
            Console.WriteLine($"wrote {Path.Combine(outDir, P6Addon.FileName)} (masters: Starfield.esm, SFBGS00D.esm)");
        }

        Console.WriteLine($"wrote {Path.Combine(outDir, Ws0aAddon.FileName)}: WS0a Tier1-3 probe records staged offline");
        return 0;
    }

    public static int Check(string pluginPath)
    {
        using var mod = Open(pluginPath, SfEsm);
        var problems = new List<string>();
        void Need(bool ok, string msg) { if (!ok) problems.Add(msg); }

        Need(mod.ModHeader.Flags.HasFlag(StarfieldModHeader.HeaderFlag.Master), "not flagged as Master");
        Need(mod.ModHeader.MasterReferences.Select(m => m.Master).SequenceEqual(new[] { SfEsm }),
            "masters must be [Starfield.esm]");
        Need(mod.Quests.Any(q => q.FormKey == Own(Ws0aQuestId) && q.Data?.Flags.HasFlag(Quest.Flag.StartGameEnabled) == true),
            $"missing StartGameEnabled QUST 0x{Ws0aQuestId:X}");
        Need(mod.Activators.Any(a => a.FormKey == Own(P18BenchActiId)), $"missing P18 bench 0x{P18BenchActiId:X}");
        Need(mod.Perks.Any(p => p.FormKey == Own(P12TestPerkId)), $"missing P12 perk 0x{P12TestPerkId:X}");
        Need(mod.ConstructibleObjects.Any(c => c.FormKey == Own(P12CobjPerkId) && (c.RequiredPerks?.Any(pk => pk.Perk.FormKey == Own(P12TestPerkId)) ?? false)),
            $"P12 COBJ 0x{P12CobjPerkId:X} missing RequiredPerks -> 0x{P12TestPerkId:X}");
        foreach (var x in problems) Console.WriteLine("FAIL  " + x);
        Console.WriteLine(problems.Count == 0 ? "ws0a-check: ok" : $"ws0a-check: {problems.Count} problem(s)");
        return problems.Count == 0 ? 0 : 1;
    }
}
