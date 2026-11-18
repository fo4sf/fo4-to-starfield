// CoreCandidate: Unified console-free exterior walk harness for gemini/core-candidate (docs/testing/core-candidate-pc-card.md).
//
// Writes FO4SFCoreCandidate.esm (masters Starfield.esm + FO4SFCoreValues.esm; zero foreign overrides):
//   0x800 QUST FO4SF_CoreCandidateWalkQuest    (StartGameEnabled, stages 10/20/30/40/50, script FO4SF_CoreCandidateWalk, TestModeGlobal bound)
//   0x801 ACTI FO4SF_ChargenRebuildKiosk       (cloned from vanilla activator 0x001CCAC2, console-free character creation kiosk)
//   0x802 MESG FO4SF_Msg_ChargenBackground     (MessageBox: choose 1 Background)
//   0x803 MESG FO4SF_Msg_ChargenTrait1         (MessageBox: choose Trait #1 or None)
//   0x804 MESG FO4SF_Msg_ChargenTrait2         (MessageBox: choose Trait #2 or None)
//   0x805 MISC FO4SF_ChargenToken              (droppable backup trigger for Creation Flow)
//   0x806 MISC FO4SF_SpeechPrimerToken         (droppable +35 Speech primer for independent [Speech 50] list check)
//
// usage:
//   CoreCandidate build <Starfield.esm> <out_dir>
//   CoreCandidate check <FO4SFCoreCandidate.esm> <Starfield.esm>
//   CoreCandidate fixture <out_dir>
//   CoreCandidate selftest <scratch_dir>

using System.Text.Json;
using Mutagen.Bethesda;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;

try
{
    if (args.Length == 3 && args[0] == "build") return CoreCandidate.Build(args[1], args[2]);
    if (args.Length == 3 && args[0] == "check") return CoreCandidate.Check(args[1], args[2]);
    if (args.Length == 2 && args[0] == "fixture") return CoreCandidate.Fixture(args[1]);
    if (args.Length == 2 && args[0] == "selftest") return CoreCandidate.SelfTest(args[1]);
}
catch (CoreCandidate.Refusal r)
{
    Console.Error.WriteLine("refused: " + r.Message);
    return 1;
}

Console.Error.WriteLine("usage: CoreCandidate build <Starfield.esm> <out_dir> | check <plugin> <Starfield.esm> | fixture <out_dir> | selftest <scratch_dir>");
return 2;

public static class CoreCandidate
{
    public sealed class Refusal(string m) : Exception(m);

    const StarfieldRelease Release = StarfieldRelease.Starfield;
    static readonly ModKey SfEsm = ModKey.FromFileName("Starfield.esm");
    static readonly ModKey CoreValuesEsm = ModKey.FromFileName("FO4SFCoreValues.esm");
    public static readonly ModKey Plugin = ModKey.FromFileName("FO4SFCoreCandidate.esm");

    public const uint TemplateActiId = 0x001CCAC2;
    public const uint QuestId = 0x800;
    public const uint KioskActiId = 0x801;
    public const uint MsgBgId = 0x802;
    public const uint MsgTrait1Id = 0x803;
    public const uint MsgTrait2Id = 0x804;
    public const uint ChargenTokenId = 0x805;
    public const uint SpeechTokenId = 0x806;
    public const uint NextId = 0x807;

    public const string QuestEdid = "FO4SF_CoreCandidateWalkQuest";
    public const string ScriptName = "FO4SF_CoreCandidateWalk";
    public const string KioskEdid = "FO4SF_ChargenRebuildKiosk";
    public const string MsgBgEdid = "FO4SF_Msg_ChargenBackground";
    public const string MsgTrait1Edid = "FO4SF_Msg_ChargenTrait1";
    public const string MsgTrait2Edid = "FO4SF_Msg_ChargenTrait2";
    public const string ChargenTokenEdid = "FO4SF_ChargenToken";
    public const string SpeechTokenEdid = "FO4SF_SpeechPrimerToken";

    public static readonly ushort[] Stages = { 10, 20, 30, 40, 50 };

    public static readonly string[] BgButtons =
    {
        "Vault Dweller (+Speech/Science/Medicine)",
        "Wasteland Scavenger (+Repair/Lockpick/Survival)",
        "Field Medic (+Medicine/Science/Survival)",
        "Brotherhood Scribe (+Energy/Science/Repair)",
        "Cancel",
    };

    public static readonly string[] Trait1Buttons =
    {
        "Good Natured (+5 Social, -5 Combat)",
        "Small Frame (+1 AGI, -15 Carry)",
        "Skilled (+5 All Skills, -10% XP)",
        "Trigger Discipline (+10 Guns/EW, -15% RoF)",
        "No Trait (0 Traits)",
    };

    public static readonly string[] Trait2Buttons =
    {
        "Small Frame (+1 AGI, -15 Carry)",
        "Good Natured (+5 Social, -5 Combat)",
        "Fast Shot (+20% RoF, -5 Guns/EW)",
        "Wild Wasteland",
        "No Second Trait",
    };

    static FormKey Own(uint id) => new(Plugin, id);
    static FormKey Sf(uint id) => new(SfEsm, id);

    static uint LoadCoreValueId(string edid)
    {
        var dir = AppContext.BaseDirectory;
        string? jsonPath = null;
        for (int up = 0; up < 8 && dir != null; up++, dir = Directory.GetParent(dir)?.FullName)
        {
            var cand = Path.Combine(dir, "src", "fo4sf", "core", "core_values.json");
            if (File.Exists(cand)) { jsonPath = cand; break; }
        }
        jsonPath ??= Path.Combine(Directory.GetCurrentDirectory(), "src", "fo4sf", "core", "core_values.json");
        if (!File.Exists(jsonPath)) throw new Refusal("missing src/fo4sf/core/core_values.json");
        using var doc = JsonDocument.Parse(File.ReadAllText(jsonPath));
        foreach (var el in doc.RootElement.GetProperty("records").EnumerateArray())
        {
            if (string.Equals(el.GetProperty("edid").GetString(), edid, StringComparison.OrdinalIgnoreCase))
                return Convert.ToUInt32(el.GetProperty("id").GetString()!, 16);
        }
        throw new Refusal($"core_values.json missing {edid}");
    }

    static IStarfieldModDisposableGetter OpenMod(string path, ModKey expectedKey)
    {
        var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        styles.Set(new KeyedMasterStyle(SfEsm, MasterStyle.Full));
        styles.Set(new KeyedMasterStyle(CoreValuesEsm, MasterStyle.Full));
        styles.Set(new KeyedMasterStyle(expectedKey, MasterStyle.Full));
        return StarfieldMod.CreateFromBinaryOverlay(path, Release, new BinaryReadParameters { MasterFlagsLookup = styles });
    }

    static Message MakeMsg(uint id, string edid, string title, string desc, string[] buttons)
    {
        var m = new Message(Own(id), Release)
        {
            EditorID = edid,
            Name = title,
            Description = desc,
            Flags = Message.Flag.MessageBox,
            FormVersion = 581,
        };
        foreach (var b in buttons)
            m.MenuButtons.Add(new MessageButton { Text = b });
        return m;
    }

    static MiscItem MakeToken(uint id, string edid, string name)
    {
        return new MiscItem(Own(id), Release)
        {
            EditorID = edid,
            Name = name,
            Weight = 0.0f,
            Value = 0,
            FormVersion = 581,
        };
    }

    public static int Build(string sfPath, string outDir)
    {
        if (!File.Exists(sfPath)) throw new Refusal("Starfield.esm missing: " + sfPath);
        uint testModeGlobId = LoadCoreValueId("FO4SF_TestModeEnabled");
        using var sf = OpenMod(sfPath, SfEsm);

        var tplActi = sf.Activators.FirstOrDefault(a => a.FormKey == Sf(TemplateActiId))
                      ?? sf.Activators.FirstOrDefault()
                      ?? throw new Refusal("no template ACTI in " + sfPath);

        var mod = new StarfieldMod(Plugin, Release);
        mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        mod.ModHeader.Author = "fo4-to-starfield";

        var kiosk = new Mutagen.Bethesda.Starfield.Activator(Own(KioskActiId), Release);
        kiosk.DeepCopyIn(tplActi, new Mutagen.Bethesda.Starfield.Activator.TranslationMask(defaultOn: true));
        kiosk.EditorID = KioskEdid;
        kiosk.Name = "Wasteland Character Rebuild Kiosk";
        kiosk.ActivateTextOverride = "Rebuild Character";
        kiosk.VirtualMachineAdapter = null;
        mod.Activators.Add(kiosk);

        mod.Messages.Add(MakeMsg(MsgBgId, MsgBgEdid, "Wasteland Origin (Background)",
            "Choose 1 Wasteland Background (+10 to 3 signature skills and [Background] dialogue tag):", BgButtons));
        mod.Messages.Add(MakeMsg(MsgTrait1Id, MsgTrait1Edid, "Primary Trait (0-2 Allowed)",
            "Choose your first Trait (trade-off bonus/penalty) or No Trait:", Trait1Buttons));
        mod.Messages.Add(MakeMsg(MsgTrait2Id, MsgTrait2Edid, "Secondary Trait (0-2 Allowed)",
            "Choose an optional second Trait (distinct from Trait #1) or No Second Trait:", Trait2Buttons));

        mod.MiscItems.Add(MakeToken(ChargenTokenId, ChargenTokenEdid, "Wasteland Character Rebuild Slate (Drop to Open)"));
        mod.MiscItems.Add(MakeToken(SpeechTokenId, SpeechTokenEdid, "Wasteland Speech Primer (Drop for +35 Speech)"));

        var quest = new Quest(Own(QuestId), Release)
        {
            EditorID = QuestEdid,
            Name = "FO4SF Core Candidate Walk Harness",
            FormVersion = 581,
            Version2 = 12,
            Data = new QuestData { Flags = Quest.Flag.StartGameEnabled, Priority = 35 },
        };
        foreach (var s in Stages)
            quest.Stages.Add(new QuestStage { Index = s });
        var se = new ScriptEntry { Name = ScriptName, Flags = ScriptEntry.Flag.Local };
        se.Properties.Add(new ScriptObjectProperty
        {
            Name = "TestModeGlobal",
            Flags = ScriptProperty.Flag.Edited,
            Object = new FormLink<IStarfieldMajorRecordGetter>(new FormKey(CoreValuesEsm, testModeGlobId)),
        });
        quest.VirtualMachineAdapter = new QuestAdapter
        {
            Version = 6,
            ObjectFormat = 2,
            ExtraBindDataVersion = 3,
            Script = new ScriptEntry { Name = "", Flags = ScriptEntry.Flag.Local },
        };
        quest.VirtualMachineAdapter.Scripts.Add(se);
        mod.Quests.Add(quest);

        mod.ModHeader.Stats.NextFormID = NextId;
        mod.ModHeader.MasterReferences.Clear();
        mod.ModHeader.MasterReferences.Add(new MasterReference { Master = SfEsm, FileSize = 0 });
        mod.ModHeader.MasterReferences.Add(new MasterReference { Master = CoreValuesEsm, FileSize = 0 });

        Directory.CreateDirectory(outDir);
        string outPath = Path.Combine(outDir, Plugin.FileName);
        var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        styles.Set(new KeyedMasterStyle(SfEsm, MasterStyle.Full));
        styles.Set(new KeyedMasterStyle(CoreValuesEsm, MasterStyle.Full));
        styles.Set(new KeyedMasterStyle(Plugin, MasterStyle.Full));
        mod.WriteToBinary(outPath, new BinaryWriteParameters
        {
            ModKey = ModKeyOption.NoCheck,
            MastersListContent = MastersListContentOption.NoCheck,
            MastersListOrdering = new MastersListOrderingByLoadOrder(new[] { SfEsm, CoreValuesEsm }),
            MasterFlagsLookup = styles,
        });
        Console.WriteLine($"wrote {outPath} ({new FileInfo(outPath).Length} bytes)");
        return 0;
    }

    public static int Check(string pluginPath, string sfPath)
    {
        if (!File.Exists(pluginPath)) throw new Refusal("plugin missing: " + pluginPath);
        if (!File.Exists(sfPath)) throw new Refusal("Starfield.esm missing: " + sfPath);
        uint testModeGlobId = LoadCoreValueId("FO4SF_TestModeEnabled");
        using var mod = OpenMod(pluginPath, Plugin);

        if (!mod.ModHeader.Flags.HasFlag(StarfieldModHeader.HeaderFlag.Master))
            throw new Refusal("header missing Master flag");
        var masters = mod.ModHeader.MasterReferences.Select(m => m.Master.FileName.String).ToList();
        var wantMasters = new[] { "Starfield.esm", "FO4SFCoreValues.esm" };
        if (!masters.SequenceEqual(wantMasters, StringComparer.OrdinalIgnoreCase))
            throw new Refusal($"masters must be [Starfield.esm, FO4SFCoreValues.esm], got [{string.Join(", ", masters)}]");

        foreach (var rec in mod.EnumerateMajorRecords())
        {
            if (rec.FormKey.ModKey != Plugin)
                throw new Refusal($"foreign override forbidden: {rec.FormKey}");
            if (rec.FormKey.ID < 0x800)
                throw new Refusal($"local FormID < 0x800 forbidden: {rec.FormKey}");
        }

        if (mod.Quests.Count != 1 || mod.Quests.First().FormKey != Own(QuestId))
            throw new Refusal("expected QUST 0x800 FO4SF_CoreCandidateWalkQuest");
        var q = mod.Quests.First();
        var tProp = q.VirtualMachineAdapter?.Scripts.FirstOrDefault()?.Properties.OfType<IScriptObjectPropertyGetter>()
            .FirstOrDefault(p => p.Name == "TestModeGlobal");
        if (tProp == null || tProp.Object.FormKey != new FormKey(CoreValuesEsm, testModeGlobId))
            throw new Refusal("expected TestModeGlobal bound to FO4SFCoreValues.esm FO4SF_TestModeEnabled");

        if (mod.Activators.Count != 1 || mod.Activators.First().FormKey != Own(KioskActiId))
            throw new Refusal("expected ACTI 0x801 FO4SF_ChargenRebuildKiosk");
        if (mod.Messages.Count != 3)
            throw new Refusal($"expected 3 MESG records, got {mod.Messages.Count}");
        if (mod.MiscItems.Count != 2)
            throw new Refusal($"expected 2 MISC token records, got {mod.MiscItems.Count}");

        Console.WriteLine($"FO4SFCoreCandidate.esm: header Master, masters [Starfield.esm, FO4SFCoreValues.esm], 1 QUST, 1 ACTI, 3 MESG, 2 MISC, zero foreign overrides; all checks pass");
        return 0;
    }

    public static int Fixture(string outDir)
    {
        Directory.CreateDirectory(outDir);
        var sf = new StarfieldMod(SfEsm, Release);
        sf.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        var acti = new Mutagen.Bethesda.Starfield.Activator(Sf(TemplateActiId), Release)
        {
            EditorID = "ControlConsoleTemplate",
            Name = "Console",
            FormVersion = 581,
        };
        sf.Activators.Add(acti);
        string sfPath = Path.Combine(outDir, "Starfield.esm");
        var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        styles.Set(new KeyedMasterStyle(SfEsm, MasterStyle.Full));
        sf.WriteToBinary(sfPath, new BinaryWriteParameters
        {
            ModKey = ModKeyOption.NoCheck,
            MastersListContent = MastersListContentOption.NoCheck,
            MasterFlagsLookup = styles,
        });
        return 0;
    }

    public static int SelfTest(string scratchDir)
    {
        if (Directory.Exists(scratchDir)) Directory.Delete(scratchDir, true);
        Directory.CreateDirectory(scratchDir);
        string fixDir = Path.Combine(scratchDir, "fixture");
        string outDir = Path.Combine(scratchDir, "out");
        Fixture(fixDir);
        string sfPath = Path.Combine(fixDir, "Starfield.esm");
        Build(sfPath, outDir);
        string esm = Path.Combine(outDir, Plugin.FileName);
        Check(esm, sfPath);

        // Negative tamper test: clear Master header flag (byte 9 bit 0x01 in TES4 record flags at offset 8)
        string badPath = Path.Combine(scratchDir, "bad.esm");
        var raw = File.ReadAllBytes(esm);
        raw[8] &= 0xFE;
        File.WriteAllBytes(badPath, raw);
        bool caught = false;
        try { Check(badPath, sfPath); }
        catch (Refusal) { caught = true; }
        if (!caught) throw new Refusal("selftest failed: missing Master flag was not refused");

        Console.WriteLine("selftest: ok");
        return 0;
    }
}
