// PipboyWristBuilder: Fallout 4 Pip-Boy 3000 wrist ARMO/ARMA seam for FO4SFNewGame.esm (Round 16 I2(c)).
//
// Moves FO4SF_PipboyWrist (0x80D) completely off bit 54 (SSChronoMark, which Starfield.esm spacesuits use for
// ChronoWatch) onto a single combined ARMA on bit 55 (housing + PipboyScreen in one NIF per sex/view):
//   - 0x823 FO4SF_PipboyWristAA (bit 55 only; M/F = pipboy_wrist_housing_{m,f}.nif, 1st M/F = *_1st.nif / *_1st_f.nif)
//   - 0x824 RETIRED & never reused (former FO4SF_PipboyWristScreenAA)
// and attaches shared keyword FO4SF_Kw_Pipboy (FO4SFCoreValues.esm:0x000867) to 0x80D (FO4SF_PipboyScreenSource
// lives at FO4SFCoreValues.esm:0x000868; local 0x824 and 0x825 stay retired/reserved).
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
    public const uint WatchTemplateArmaId = 0x001C9BC2; // Starfield.esm AA_Spacesuit_Mark1_ChronoWatch (used as template only; bit 54 is stripped)
    public const uint HumanRaceId = 0x00347D;         // Starfield.esm HumanRace

    public const uint WristArmaId = 0x823;
    public const string WristArmaEdid = "FO4SF_PipboyWristAA";
    public const uint RetiredWristScreenArmaId = 0x824; // Retired in Round 16 I2(c); never reuse

    public const string PipboyKeywordEdid = "FO4SF_Kw_Pipboy";
    public const string WristSlotLabel = "55";

    public const SF.FirstPersonFlag ForbiddenSpacesuitWatchFlag = SF.FirstPersonFlag.SSChronoMark; // bit 54 (0x0040000000000000UL)
    public const SF.FirstPersonFlag WristSlotFlag = (SF.FirstPersonFlag)(1UL << 55);              // bit 55 only (0x0080000000000000UL)

    public const string WristWorldMaleModel = @"fo4port\pipboy\pipboy_wrist_housing_m.nif";
    public const string WristWorldFemaleModel = @"fo4port\pipboy\pipboy_wrist_housing_f.nif";
    public const string WristFirstPersonModel = @"fo4port\pipboy\pipboy_wrist_housing_1st.nif";
    public const string WristFirstPersonFemaleModel = @"fo4port\pipboy\pipboy_wrist_housing_1st_f.nif";

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
    /// Clones Starfield.esm:0x001C9BC2 into a single combined ARMA 0x823 on bit 55 ONLY (off bit 54 SSChronoMark),
    /// rewires ARMO 0x80D (FO4SF_PipboyWrist) to [0x823] on bit 55, retires 0x824, and attaches FO4SF_Kw_Pipboy.
    /// </summary>
    public static SF.ArmorAddon BuildWristRecords(
        SF.StarfieldMod mod,
        SF.IStarfieldModGetter sf,
        SF.Armor pipboyWrist,
        ModKey sfEsm,
        FormKey? pipboyKeywordKey = null)
    {
        var templateAa = sf.ArmorAddons.FirstOrDefault(a => a.FormKey == new FormKey(sfEsm, WatchTemplateArmaId));

        mod.ArmorAddons.Remove(new FormKey(mod.ModKey, RetiredWristScreenArmaId));

        var wristAa = CreateWristArma(
            mod,
            sfEsm,
            templateAa,
            WristArmaId,
            WristArmaEdid,
            WristSlotFlag,
            WristWorldMaleModel,
            WristWorldFemaleModel,
            WristFirstPersonModel,
            WristFirstPersonFemaleModel);

        pipboyWrist.FirstPersonFlags = WristSlotFlag;
        pipboyWrist.MajorRecordFlagsRaw &= ~0x4; // playable
        pipboyWrist.VirtualMachineAdapter = null;
        pipboyWrist.Armatures.Clear();
        pipboyWrist.Armatures.Add(new SF.ArmorAddonModel
        {
            AddonIndex = 0,
            ArmorAddon = new FormLinkNullable<SF.IArmorAddonGetter>(wristAa.FormKey),
        });
        if (pipboyKeywordKey is { } kwKey)
        {
            AttachKeyword(pipboyWrist, kwKey);
        }

        return wristAa;
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
    /// Validates ARMO 0x80D, single ARMA 0x823 on bit 55 only, retired 0x824, zero bit-54 usage, and FO4SF_Kw_Pipboy.
    /// </summary>
    public static void ValidateWristRecords(
        SF.IStarfieldModGetter plug,
        SF.IArmorGetter? pipboyWrist,
        Action<bool, string> need,
        FormKey? pipboyKeywordKey = null)
    {
        var key = plug.ModKey;
        var wristAa = plug.ArmorAddons.FirstOrDefault(a => a.FormKey == new FormKey(key, WristArmaId));
        var retiredAa = plug.ArmorAddons.FirstOrDefault(a => a.FormKey == new FormKey(key, RetiredWristScreenArmaId));

        need(retiredAa is null,
             $"retired FormID 0x{RetiredWristScreenArmaId:X} must not carry an ARMA record");
        need(plug.ArmorAddons.Count == 1 && wristAa is not null,
             $"expected 1 ARMA (0x{WristArmaId:X}), found {plug.ArmorAddons.Count}");

        foreach (var aa in plug.ArmorAddons)
        {
            ulong bits = (ulong)(aa.FirstPersonFlags ?? 0);
            need((bits & (ulong)ForbiddenSpacesuitWatchFlag) == 0,
                 $"Pip-Boy ARMA 0x{aa.FormKey.ID:X} ({aa.EditorID}) must not use bit 54 (SSChronoMark spacesuit clash): 0x{bits:X16}");
        }
        foreach (var armo in plug.Armors)
        {
            ulong bits = (ulong)(armo.FirstPersonFlags ?? 0);
            need((bits & (ulong)ForbiddenSpacesuitWatchFlag) == 0,
                 $"Pip-Boy ARMO 0x{armo.FormKey.ID:X} ({armo.EditorID}) must not use bit 54 (SSChronoMark spacesuit clash): 0x{bits:X16}");
        }

        ValidateArma(wristAa, WristArmaId, WristArmaEdid, WristSlotFlag,
                     WristWorldMaleModel, WristWorldFemaleModel,
                     WristFirstPersonModel, WristFirstPersonFemaleModel, need);

        need(pipboyWrist is not null &&
             pipboyWrist.FirstPersonFlags == WristSlotFlag &&
             (pipboyWrist.MajorRecordFlagsRaw & 0x4) == 0 &&
             pipboyWrist.Armatures.Count == 1 &&
             pipboyWrist.Armatures[0].ArmorAddon.FormKey == new FormKey(key, WristArmaId),
             $"ARMO FO4SF_PipboyWrist is not playable {WristSlotFlag} (0x{(ulong)WristSlotFlag:X16}) pointing to [0x{WristArmaId:X}]");

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
