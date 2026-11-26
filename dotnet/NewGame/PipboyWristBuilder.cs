// PipboyWristBuilder: Fallout 4 Pip-Boy 3000 wrist ARMO/ARMA seam for FO4SFNewGame.esm (Round 15 Wave A Item 1 / G5).
//
// Splits FO4SF_PipboyWrist (0x80D) into two separate disjoint ARMAs cloned from Starfield.esm:0x001C9BC2
// (AA_Spacesuit_Mark1_ChronoWatch):
//   - 0x823 FO4SF_PipboyWristHousingAA (bit 54 SSChronoMark; M/F = *_m/f.nif, FirstPerson M/F = *_1st.nif / *_1st_f.nif)
//   - 0x824 FO4SF_PipboyWristScreenAA  (bit 55 unused; M/F = *_m/f.nif, FirstPerson M/F = *_1st.nif / *_1st_f.nif)
// and attaches shared keyword FO4SF_Kw_Pipboy (FO4SFCoreValues.esm:0x000867) to 0x80D (FO4SF_PipboyScreenSource
// lives at FO4SFCoreValues.esm:0x000868; local 0x825 stays retired/reserved).
//
// Note on BO64 / FirstPersonFlag: Starfield.esm:0x001C9BC2 (AA_Spacesuit_Mark1_ChronoWatch) uses
// SF.FirstPersonFlag.SSChronoMark (0x0040000000000000UL, bit 54) and bit 55 (0x0080000000000000UL) is
// unused in Starfield.esm. Housing 0x823 (bit 54) and Screen 0x824 (bit 55) are disjoint so the engine renders
// both sub-armatures on 0x80D (bits 54|55). Behavior against clothes and spacesuits in slots 3 (BODY),
// 8 (SleevesVisOnly), and 35 (SSBODY) is unverified until game check.
using Mutagen.Bethesda;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Assets;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Mutagen.Bethesda.Starfield.Assets;
using Noggog;
using SF = Mutagen.Bethesda.Starfield;

static class PipboyWristBuilder
{
    public const uint WatchTemplateArmaId = 0x001C9BC2; // Starfield.esm AA_Spacesuit_Mark1_ChronoWatch
    public const uint HumanRaceId = 0x00347D;         // Starfield.esm HumanRace

    public const uint WristHousingArmaId = 0x823;
    public const string WristHousingArmaEdid = "FO4SF_PipboyWristHousingAA";

    public const uint WristScreenArmaId = 0x824;
    public const string WristScreenArmaEdid = "FO4SF_PipboyWristScreenAA";

    public const string PipboyKeywordEdid = "FO4SF_Kw_Pipboy";
    public const string WristSlotLabel = "54,55";

    public const SF.FirstPersonFlag HousingSlotFlag = SF.FirstPersonFlag.SSChronoMark; // bit 54 (0x0040000000000000UL)
    public const SF.FirstPersonFlag ScreenSlotFlag = (SF.FirstPersonFlag)(1UL << 55);   // bit 55 (0x0080000000000000UL, disjoint)
    public const SF.FirstPersonFlag WristSlotFlag = HousingSlotFlag | ScreenSlotFlag;   // bits 54|55 (0x00C0000000000000UL)

    public const string HousingWorldMaleModel = @"fo4port\pipboy\pipboy_wrist_housing_m.nif";
    public const string HousingWorldFemaleModel = @"fo4port\pipboy\pipboy_wrist_housing_f.nif";
    public const string HousingFirstPersonModel = @"fo4port\pipboy\pipboy_wrist_housing_1st.nif";
    public const string HousingFirstPersonFemaleModel = @"fo4port\pipboy\pipboy_wrist_housing_1st_f.nif";

    public const string ScreenWorldMaleModel = @"fo4port\pipboy\pipboy_wrist_screen_m.nif";
    public const string ScreenWorldFemaleModel = @"fo4port\pipboy\pipboy_wrist_screen_f.nif";
    public const string ScreenFirstPersonModel = @"fo4port\pipboy\pipboy_wrist_screen_1st.nif";
    public const string ScreenFirstPersonFemaleModel = @"fo4port\pipboy\pipboy_wrist_screen_1st_f.nif";

    public static readonly string[] StagedMeshRelPaths =
    {
        "Data/meshes/fo4port/pipboy/pipboy_wrist_housing_m.nif",
        "Data/meshes/fo4port/pipboy/pipboy_wrist_housing_f.nif",
        "Data/meshes/fo4port/pipboy/pipboy_wrist_housing_1st.nif",
        "Data/meshes/fo4port/pipboy/pipboy_wrist_housing_1st_f.nif",
        "Data/meshes/fo4port/pipboy/pipboy_wrist_screen_m.nif",
        "Data/meshes/fo4port/pipboy/pipboy_wrist_screen_f.nif",
        "Data/meshes/fo4port/pipboy/pipboy_wrist_screen_1st.nif",
        "Data/meshes/fo4port/pipboy/pipboy_wrist_screen_1st_f.nif",
    };

    public static string NormalizeModelPath(string? raw) =>
        (raw ?? string.Empty).Trim().Replace('/', '\\').TrimStart('\\');

    public static bool ModelPathEquals(string? actual, string expected) =>
        string.Equals(NormalizeModelPath(actual), NormalizeModelPath(expected), StringComparison.OrdinalIgnoreCase);

    static void AttachKeyword(SF.Armor armor, FormKey keywordKey)
    {
        armor.Keywords ??= new ExtendedList<IFormLinkGetter<SF.IKeywordGetter>>();
        if (!armor.Keywords.Any(k => k.FormKey == keywordKey))
            armor.Keywords.Add(new FormLink<SF.IKeywordGetter>(keywordKey));

        var kwComp = armor.Components.OfType<SF.KeywordFormComponent>().FirstOrDefault();
        if (kwComp is null)
        {
            kwComp = new SF.KeywordFormComponent();
            armor.Components.Add(kwComp);
        }
        kwComp.Keywords ??= new ExtendedList<IFormLinkGetter<SF.IKeywordGetter>>();
        if (!kwComp.Keywords.Any(k => k.FormKey == keywordKey))
            kwComp.Keywords.Add(new FormLink<SF.IKeywordGetter>(keywordKey));
    }

    /// <summary>
    /// Clones Starfield.esm:0x001C9BC2 (AA_Spacesuit_Mark1_ChronoWatch) into disjoint slots:
    /// 0x823 (housing, bit 54 SSChronoMark) and 0x824 (screen, bit 55), rewires ARMO 0x80D (FO4SF_PipboyWrist)
    /// to [0x823, 0x824] on bits 54|55, and attaches shared keyword FO4SF_Kw_Pipboy.
    /// </summary>
    public static (SF.ArmorAddon HousingAa, SF.ArmorAddon ScreenAa) BuildWristRecords(
        SF.StarfieldMod mod,
        SF.IStarfieldModGetter sf,
        SF.Armor pipboyWrist,
        ModKey sfEsm,
        FormKey? pipboyKeywordKey = null)
    {
        var templateAa = sf.ArmorAddons.FirstOrDefault(a => a.FormKey == new FormKey(sfEsm, WatchTemplateArmaId));

        var housingAa = CreateWristArma(
            mod,
            sfEsm,
            templateAa,
            WristHousingArmaId,
            WristHousingArmaEdid,
            HousingSlotFlag,
            HousingWorldMaleModel,
            HousingWorldFemaleModel,
            HousingFirstPersonModel,
            HousingFirstPersonFemaleModel);

        var screenAa = CreateWristArma(
            mod,
            sfEsm,
            templateAa,
            WristScreenArmaId,
            WristScreenArmaEdid,
            ScreenSlotFlag,
            ScreenWorldMaleModel,
            ScreenWorldFemaleModel,
            ScreenFirstPersonModel,
            ScreenFirstPersonFemaleModel);

        pipboyWrist.FirstPersonFlags = WristSlotFlag;
        pipboyWrist.MajorRecordFlagsRaw &= ~0x4; // playable
        pipboyWrist.VirtualMachineAdapter = null;
        pipboyWrist.Armatures.Clear();
        pipboyWrist.Armatures.Add(new SF.ArmorAddonModel
        {
            AddonIndex = 0,
            ArmorAddon = new FormLinkNullable<SF.IArmorAddonGetter>(housingAa.FormKey),
        });
        pipboyWrist.Armatures.Add(new SF.ArmorAddonModel
        {
            AddonIndex = 0,
            ArmorAddon = new FormLinkNullable<SF.IArmorAddonGetter>(screenAa.FormKey),
        });
        if (pipboyKeywordKey is { } kwKey)
        {
            AttachKeyword(pipboyWrist, kwKey);
        }

        return (housingAa, screenAa);
    }

    static SF.ArmorAddon CreateWristArma(
        SF.StarfieldMod mod,
        ModKey sfEsm,
        SF.IArmorAddonGetter? templateAa,
        uint localId,
        string edid,
        SF.FirstPersonFlag slotFlag,
        string worldMale,
        string worldFemale,
        string firstPersonMale,
        string firstPersonFemale)
    {
        var key = new FormKey(mod.ModKey, localId);
        SF.ArmorAddon arma;
        if (templateAa is not null)
        {
            arma = (SF.ArmorAddon)templateAa.Duplicate(key);
        }
        else
        {
            arma = new SF.ArmorAddon(key, SF.StarfieldRelease.Starfield)
            {
                FormVersion = 581,
            };
        }

        arma.EditorID = edid;
        arma.FirstPersonFlags = slotFlag;
        arma.Race.SetTo(new FormKey(sfEsm, HumanRaceId));
        arma.WorldModel = new GenderedItem<SF.Model?>(
            new SF.Model { File = new AssetLink<StarfieldModelAssetType>(worldMale) },
            new SF.Model { File = new AssetLink<StarfieldModelAssetType>(worldFemale) });
        arma.FirstPersonModel = new GenderedItem<SF.Model?>(
            new SF.Model { File = new AssetLink<StarfieldModelAssetType>(firstPersonMale) },
            new SF.Model { File = new AssetLink<StarfieldModelAssetType>(firstPersonFemale) });

        mod.ArmorAddons.Remove(key);
        mod.ArmorAddons.Add(arma);
        return arma;
    }

    /// <summary>
    /// Validates ARMO 0x80D, disjoint ARMAs 0x823 (bit 54) &amp; 0x824 (bit 55), and FO4SF_Kw_Pipboy keyword.
    /// </summary>
    public static void ValidateWristRecords(
        SF.IStarfieldModGetter plug,
        SF.IArmorGetter? pipboyWrist,
        Action<bool, string> need,
        FormKey? pipboyKeywordKey = null)
    {
        var key = plug.ModKey;
        var housingAa = plug.ArmorAddons.FirstOrDefault(a => a.FormKey == new FormKey(key, WristHousingArmaId));
        var screenAa = plug.ArmorAddons.FirstOrDefault(a => a.FormKey == new FormKey(key, WristScreenArmaId));

        need(plug.ArmorAddons.Count == 2 && housingAa is not null && screenAa is not null,
             $"expected 2 ARMAs (0x{WristHousingArmaId:X}, 0x{WristScreenArmaId:X}), found {plug.ArmorAddons.Count}");

        ValidateArma(housingAa, WristHousingArmaId, WristHousingArmaEdid, HousingSlotFlag,
                     HousingWorldMaleModel, HousingWorldFemaleModel,
                     HousingFirstPersonModel, HousingFirstPersonFemaleModel, need);
        ValidateArma(screenAa, WristScreenArmaId, WristScreenArmaEdid, ScreenSlotFlag,
                     ScreenWorldMaleModel, ScreenWorldFemaleModel,
                     ScreenFirstPersonModel, ScreenFirstPersonFemaleModel, need);

        ulong housingBits = (ulong)(housingAa?.FirstPersonFlags ?? 0);
        ulong screenBits = (ulong)(screenAa?.FirstPersonFlags ?? 0);
        need(housingBits != 0 && screenBits != 0 && (housingBits & screenBits) == 0,
             $"housing ARMA 0x{WristHousingArmaId:X} (0x{housingBits:X16}) and screen ARMA 0x{WristScreenArmaId:X} (0x{screenBits:X16}) must use disjoint FirstPersonFlags");

        need(pipboyWrist is not null &&
             pipboyWrist.FirstPersonFlags == WristSlotFlag &&
             (pipboyWrist.MajorRecordFlagsRaw & 0x4) == 0 &&
             pipboyWrist.Armatures.Count == 2 &&
             pipboyWrist.Armatures[0].ArmorAddon.FormKey == new FormKey(key, WristHousingArmaId) &&
             pipboyWrist.Armatures[1].ArmorAddon.FormKey == new FormKey(key, WristScreenArmaId),
             $"ARMO FO4SF_PipboyWrist is not playable {WristSlotFlag} (0x{(ulong)WristSlotFlag:X16}) pointing to [0x{WristHousingArmaId:X}, 0x{WristScreenArmaId:X}]");

        if (pipboyKeywordKey is { } kwKey)
        {
            bool hasKwList = pipboyWrist?.Keywords?.Any(k => k.FormKey == kwKey) == true;
            bool hasKwComp = pipboyWrist?.Components.OfType<SF.IKeywordFormComponentGetter>()
                .Any(c => c.Keywords?.Any(k => k.FormKey == kwKey) == true) == true;
            need(hasKwList && hasKwComp,
                 $"ARMO FO4SF_PipboyWrist lacks shared keyword {kwKey} in Keywords or KeywordFormComponent");
        }
    }

    static void ValidateArma(
        SF.IArmorAddonGetter? aa,
        uint expectedId,
        string expectedEdid,
        SF.FirstPersonFlag expectedSlotFlag,
        string expectedWorldM,
        string expectedWorldF,
        string expected1stM,
        string expected1stF,
        Action<bool, string> need)
    {
        if (aa is null)
        {
            need(false, $"missing ARMA 0x{expectedId:X} {expectedEdid}");
            return;
        }

        string? male1st = aa.FirstPersonModel?.Male?.File?.GivenPath;
        string? female1st = aa.FirstPersonModel?.Female?.File?.GivenPath;
        need(aa.EditorID == expectedEdid &&
             aa.FirstPersonFlags == expectedSlotFlag &&
             ModelPathEquals(aa.WorldModel?.Male?.File?.GivenPath, expectedWorldM) &&
             ModelPathEquals(aa.WorldModel?.Female?.File?.GivenPath, expectedWorldF) &&
             ModelPathEquals(male1st, expected1stM) &&
             ModelPathEquals(female1st, expected1stF) &&
             !string.Equals(NormalizeModelPath(male1st), NormalizeModelPath(female1st), StringComparison.OrdinalIgnoreCase),
             $"ARMA 0x{expectedId:X} {expectedEdid} mismatch (EDID={aa.EditorID}, Slot=0x{(ulong)(aa.FirstPersonFlags ?? 0):X16} want 0x{(ulong)expectedSlotFlag:X16}, " +
             $"WM={aa.WorldModel?.Male?.File?.GivenPath}, WF={aa.WorldModel?.Female?.File?.GivenPath}, " +
             $"1stM={male1st}, 1stF={female1st})");
    }
}
