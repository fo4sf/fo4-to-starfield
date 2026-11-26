// PipboyWristBuilder: Fallout 4 Pip-Boy 3000 wrist ARMO/ARMA/GLOB seam for FO4SFNewGame.esm (Round 15 Wave A Item 1).
//
// Splits FO4SF_PipboyWrist (0x80D) into two separate ARMAs cloned from Starfield.esm:0x001C9BC2
// (AA_Spacesuit_Mark1_ChronoWatch):
//   - 0x823 FO4SF_PipboyWristHousingAA (WorldModel M/F = pipboy_wrist_housing_{m,f}.nif, FirstPerson = *_1st.nif)
//   - 0x824 FO4SF_PipboyWristScreenAA  (WorldModel M/F = pipboy_wrist_screen_{m,f}.nif,  FirstPerson = *_1st.nif)
// and creates GLOB 0x825 FO4SF_PipboyScreenSource (0.0 = 2D_IMenu, 1.0 = 3D_RTT) so later 3D RTT swaps only the
// screen material/NIF and global without rebuilding 0x80D, 0x823, equip logic, or OnPlayerLoadGame re-equip.
//
// Note on BO64 / FirstPersonFlag: Starfield.esm:0x001C9BC2 (AA_Spacesuit_Mark1_ChronoWatch) uses
// SF.FirstPersonFlag.SSChronoMark (0x0040000000000000UL, bit 54; little-endian bytes 00 00 00 00 00 00 40 00),
// which clothes and spacesuits in slots 3 (BODY), 8 (SleevesVisOnly), and 35 (SSBODY) do NOT occlude.
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

    public const uint PipboyScreenSourceGlobId = 0x825;
    public const string PipboyScreenSourceGlobEdid = "FO4SF_PipboyScreenSource";

    public const float ScreenSource2DIMenu = 0.0f;
    public const float ScreenSource3DRTT = 1.0f;

    // Non-occluded ChronoMark-for-Spacesuit slot (Starfield.esm:0x001C9BC2 FirstPersonFlags:
    // 0x0040000000000000UL == LE bytes 00 00 00 00 00 00 40 00).
    public const SF.FirstPersonFlag WristSlotFlag = SF.FirstPersonFlag.SSChronoMark;

    public const string HousingWorldMaleModel = @"fo4port\pipboy\pipboy_wrist_housing_m.nif";
    public const string HousingWorldFemaleModel = @"fo4port\pipboy\pipboy_wrist_housing_f.nif";
    public const string HousingFirstPersonModel = @"fo4port\pipboy\pipboy_wrist_housing_1st.nif";

    public const string ScreenWorldMaleModel = @"fo4port\pipboy\pipboy_wrist_screen_m.nif";
    public const string ScreenWorldFemaleModel = @"fo4port\pipboy\pipboy_wrist_screen_f.nif";
    public const string ScreenFirstPersonModel = @"fo4port\pipboy\pipboy_wrist_screen_1st.nif";

    public static readonly string[] StagedMeshRelPaths =
    {
        "Data/meshes/fo4port/pipboy/pipboy_wrist_housing_m.nif",
        "Data/meshes/fo4port/pipboy/pipboy_wrist_housing_f.nif",
        "Data/meshes/fo4port/pipboy/pipboy_wrist_housing_1st.nif",
        "Data/meshes/fo4port/pipboy/pipboy_wrist_screen_m.nif",
        "Data/meshes/fo4port/pipboy/pipboy_wrist_screen_f.nif",
        "Data/meshes/fo4port/pipboy/pipboy_wrist_screen_1st.nif",
    };

    public static string NormalizeModelPath(string? raw) =>
        (raw ?? string.Empty).Trim().Replace('/', '\\').TrimStart('\\');

    public static bool ModelPathEquals(string? actual, string expected) =>
        string.Equals(NormalizeModelPath(actual), NormalizeModelPath(expected), StringComparison.OrdinalIgnoreCase);

    /// <summary>
    /// Clones Starfield.esm:0x001C9BC2 (AA_Spacesuit_Mark1_ChronoWatch) into 0x823 (housing) and 0x824 (screen),
    /// rewires ARMO 0x80D (FO4SF_PipboyWrist) to [0x823, 0x824] in the non-occluded SSChronoMark slot, and
    /// creates GLOB 0x825 FO4SF_PipboyScreenSource (default 0.0 = 2D_IMenu).
    /// </summary>
    public static (SF.ArmorAddon HousingAa, SF.ArmorAddon ScreenAa, SF.Global ScreenSourceGlob) BuildWristRecords(
        SF.StarfieldMod mod,
        SF.IStarfieldModGetter sf,
        SF.Armor pipboyWrist,
        ModKey sfEsm)
    {
        var templateAa = sf.ArmorAddons.FirstOrDefault(a => a.FormKey == new FormKey(sfEsm, WatchTemplateArmaId));

        var housingAa = CreateWristArma(
            mod,
            sfEsm,
            templateAa,
            WristHousingArmaId,
            WristHousingArmaEdid,
            HousingWorldMaleModel,
            HousingWorldFemaleModel,
            HousingFirstPersonModel);

        var screenAa = CreateWristArma(
            mod,
            sfEsm,
            templateAa,
            WristScreenArmaId,
            WristScreenArmaEdid,
            ScreenWorldMaleModel,
            ScreenWorldFemaleModel,
            ScreenFirstPersonModel);

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

        var screenSourceGlob = new SF.Global(new FormKey(mod.ModKey, PipboyScreenSourceGlobId), SF.StarfieldRelease.Starfield)
        {
            EditorID = PipboyScreenSourceGlobEdid,
            Data = ScreenSource2DIMenu,
        };
        mod.Globals.Add(screenSourceGlob);

        return (housingAa, screenAa, screenSourceGlob);
    }

    static SF.ArmorAddon CreateWristArma(
        SF.StarfieldMod mod,
        ModKey sfEsm,
        SF.IArmorAddonGetter? templateAa,
        uint localId,
        string edid,
        string worldMale,
        string worldFemale,
        string firstPerson)
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
        arma.FirstPersonFlags = WristSlotFlag;
        arma.Race.SetTo(new FormKey(sfEsm, HumanRaceId));
        arma.WorldModel = new GenderedItem<SF.Model?>(
            new SF.Model { File = new AssetLink<StarfieldModelAssetType>(worldMale) },
            new SF.Model { File = new AssetLink<StarfieldModelAssetType>(worldFemale) });
        arma.FirstPersonModel = new GenderedItem<SF.Model?>(
            new SF.Model { File = new AssetLink<StarfieldModelAssetType>(firstPerson) },
            new SF.Model { File = new AssetLink<StarfieldModelAssetType>(firstPerson) });

        mod.ArmorAddons.Remove(key);
        mod.ArmorAddons.Add(arma);
        return arma;
    }

    /// <summary>
    /// Validates ARMO 0x80D, ARMAs 0x823 &amp; 0x824, and GLOB 0x825 in a built FO4SFNewGame.esm plugin.
    /// </summary>
    public static void ValidateWristRecords(
        SF.IStarfieldModGetter plug,
        SF.IArmorGetter? pipboyWrist,
        Action<bool, string> need)
    {
        var key = plug.ModKey;
        var housingAa = plug.ArmorAddons.FirstOrDefault(a => a.FormKey == new FormKey(key, WristHousingArmaId));
        var screenAa = plug.ArmorAddons.FirstOrDefault(a => a.FormKey == new FormKey(key, WristScreenArmaId));

        need(plug.ArmorAddons.Count == 2 && housingAa is not null && screenAa is not null,
             $"expected 2 ARMAs (0x{WristHousingArmaId:X}, 0x{WristScreenArmaId:X}), found {plug.ArmorAddons.Count}");

        ValidateArma(housingAa, WristHousingArmaId, WristHousingArmaEdid,
                     HousingWorldMaleModel, HousingWorldFemaleModel, HousingFirstPersonModel, need);
        ValidateArma(screenAa, WristScreenArmaId, WristScreenArmaEdid,
                     ScreenWorldMaleModel, ScreenWorldFemaleModel, ScreenFirstPersonModel, need);

        need(pipboyWrist is not null &&
             pipboyWrist.FirstPersonFlags == WristSlotFlag &&
             (pipboyWrist.MajorRecordFlagsRaw & 0x4) == 0 &&
             pipboyWrist.Armatures.Count == 2 &&
             pipboyWrist.Armatures[0].ArmorAddon.FormKey == new FormKey(key, WristHousingArmaId) &&
             pipboyWrist.Armatures[1].ArmorAddon.FormKey == new FormKey(key, WristScreenArmaId),
             $"ARMO FO4SF_PipboyWrist is not playable {WristSlotFlag} pointing to [0x{WristHousingArmaId:X}, 0x{WristScreenArmaId:X}]");

        var sourceGlob = plug.Globals.FirstOrDefault(g => g.FormKey == new FormKey(key, PipboyScreenSourceGlobId));
        need(sourceGlob is { EditorID: PipboyScreenSourceGlobEdid } &&
             sourceGlob.Data is float val &&
             MathF.Abs(val - ScreenSource2DIMenu) <= 1e-4f,
             $"GLOB 0x{PipboyScreenSourceGlobId:X} is not {PipboyScreenSourceGlobEdid} == {ScreenSource2DIMenu:0.0}");
    }

    static void ValidateArma(
        SF.IArmorAddonGetter? aa,
        uint expectedId,
        string expectedEdid,
        string expectedWorldM,
        string expectedWorldF,
        string expected1st,
        Action<bool, string> need)
    {
        if (aa is null)
        {
            need(false, $"missing ARMA 0x{expectedId:X} {expectedEdid}");
            return;
        }

        need(aa.EditorID == expectedEdid &&
             aa.FirstPersonFlags == WristSlotFlag &&
             ModelPathEquals(aa.WorldModel?.Male?.File?.GivenPath, expectedWorldM) &&
             ModelPathEquals(aa.WorldModel?.Female?.File?.GivenPath, expectedWorldF) &&
             ModelPathEquals(aa.FirstPersonModel?.Male?.File?.GivenPath, expected1st) &&
             ModelPathEquals(aa.FirstPersonModel?.Female?.File?.GivenPath, expected1st),
             $"ARMA 0x{expectedId:X} {expectedEdid} mismatch (EDID={aa.EditorID}, Slot={aa.FirstPersonFlags}, " +
             $"WM={aa.WorldModel?.Male?.File?.GivenPath}, WF={aa.WorldModel?.Female?.File?.GivenPath}, " +
             $"1stM={aa.FirstPersonModel?.Male?.File?.GivenPath}, 1stF={aa.FirstPersonModel?.Female?.File?.GivenPath})");
    }
}
