// CoreValues: writes and verifies FO4SFCoreValues.esm from src/fo4sf/core/core_values.json.
//
// FO4SFCoreValues.esm is the single shared value store mastered by all FO4SF slices:
//   0x800..0x805 Radiation AVIFs & GLOBs (FO4SF_Rads at 0x800 matches Pip-Boy local id 0x800)
//   0x810..0x817 S.P.E.C.I.A.L. 7 AVIFs + FO4SF_SpecialAVList FLST
//   0x820..0x82D 13 Fallout Skill AVIFs + FO4SF_SkillAVList FLST
//   0x830..0x832 Karma AVIF + KarmaValue & KarmaTier GLOBs
//   0x840..0x847 Hardcore toggle, fast-travel gate, and Hunger/Thirst/Sleep AVIFs + stage GLOBs
//   0x850..0x851 Shared FO4SF_StimpakEffect MGEF + FO4SF_Stimpak ALCH
//   0x860        FO4SF_TestModeEnabled GLOB (default 0)
//   0x865        FO4SF_PipboyAcquired GLOB (default 0, non-constant)
//   0x870..0x876 Start & Mode GLOBs (GameMode, SurvivalStart, SurvivalLocked, StartDifficulty, WarfareFaction, WarfareStartIndex, StartChoiceDone)
//   D7(a) optional Starfield.esm overrides (--commonwealth-weather 1, default on when Starfield.esm contains Mars/NewAtlantis CLMT/ATMO;
//         --commonwealth-weather 0 rollback; Mars-wide known side effect on all Mars locations including Cydonia):
//     CLMT 0x00310DB1 ClimateUniqueCydonia       -> Weathers & WeatherSettings copied from CLMT 0x0024E982 ClimateUniqueNewAtlantis
//     CLMT 0x002EDEA5 ClimateUniqueCydoniaFrozen -> Weathers & WeatherSettings copied from CLMT 0x0024E982 ClimateUniqueNewAtlantis
//     ATMO 0x0000C9D2 ATMO_Mars                  -> ATMO_Jemison (0x0000C010) clear blue-sky atmospheric scattering
//   A4.1 + Step 4 P5 + Rows 5-20 Arsenal & Core Items (--fo4-10mm 1, --fo4-p5-weapons 1, --fo4-arsenal 1 defaults; 0 rollback):
//     0x851        FO4SF_Stimpak                ALCH ("Stimpak", Props\Stimpack01.nif, wt 0.1, val 48)
//     0x898        FO4_Ammo10mm                 AMMO ("10mm Round", fo4core\ammo\10mm\10mmammo.nif, donor 0x2B5598)
//     0x899        FO4_10mmPistol               WEAP ("10mm Pistol", 18 phys dmg, 12 cap, wt 3.525, val 51, WVIS 0x00D02C, donor 0x24561C)
//     0x89A        FO4_Baton                    WEAP ("Baton", 11 phys dmg [0008C14D], WVIS 0x055DC3, donor 0x04F760 RescueAxe)
//     0x89B        FO4_AmmoFusionCell           AMMO ("Fusion Cell", wt 0.029 [000C1897], val 3, short "Cell", donor 0x00E8EC)
//     0x89C        FO4_CompanionAmmoFusionCell  AMMO ("Companion Fusion Cell", non-playable, wt 0, val 3 [00245D69], donor 0x00E8EC)
//     0x89D        FO4_LaserMusket              WEAP ("Laser Musket", 30 DAMA energy, 2 cap, val 61 [0001DACF+OMOD], rate 0.667s, WVIS 0x1C1162, donor 0x2773C8 Orion)
//     0x89E        FO4_CompPrestonLaserMusket   WEAP ("Preston's Laser Musket", 18 DAMA energy, 2 cap, base 150 -> val 195 [00062AA6+OMOD], non-playable, donor 0x2773C8)
//     0x89F        FO4_Ammo5mm                  AMMO ("5mm Round", wt 0.009 [0001F66C], val 1, short "5mm", donor 0x04AD3E)
//     0x8A0        FO4_Minigun                  WEAP ("Minigun", 8 phys dmg, 500 cap, wt 27.45, val 383, Microgun rate, WVIS 0x00D02C, donor 0x0546CD Microgun)
//     0x8A1..0x8A3 Row 5 Pipe Pistol & Rifle + .38 Round (PipeGun 00024F55 + Ammo38Caliber 0004CE87)
//     0x8A4..0x8A5 FO4_Caps (0000000F) & FO4_BobbyPin (0000000A) MISC items
//     0x8B0..0x8D6 Rows 6-20 AMMO, EXPL, PROJ, Laser Ash / Plasma Goo (GooPile01 / CritPlasma / CritLaser), WEAP
//
// usage:
//   CoreValues build <Starfield.esm> <out dir> [--json <core_values.json>] [--default-rads-rule 0|1] [--default-hardcore 0|1] [--test-mode 0|1] [--commonwealth-weather 0|1] [--fo4-10mm 0|1] [--fo4-p5-weapons 0|1] [--fo4-arsenal 0|1]
//   CoreValues check <FO4SFCoreValues.esm> <Starfield.esm> [--json <core_values.json>] [--default-rads-rule 0|1] [--default-hardcore 0|1] [--test-mode 0|1] [--commonwealth-weather 0|1] [--fo4-10mm 0|1] [--fo4-p5-weapons 0|1] [--fo4-arsenal 0|1]
//   CoreValues fixture <out dir>
//   CoreValues selftest <scratch dir>

using System.Globalization;
using System.Text.Json;
using Mutagen.Bethesda;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;

try
{
    var rest = args.ToList();
    string? jsonPath = null;
    int radsRule = 0;
    int hardcore = 0;
    int testMode = 0;
    int commonwealthWeather = 1;
    int fo410mm = 1;
    int fo4P5Weapons = 1;
    int fo4Arsenal = 1;

    void OptInt(string name, ref int into)
    {
        int i = rest.IndexOf(name);
        if (i < 0) return;
        if (i + 1 >= rest.Count || !int.TryParse(rest[i + 1], NumberStyles.Integer, CultureInfo.InvariantCulture, out int v) || (v != 0 && v != 1))
            throw new CoreValuesWriter.Refusal($"{name} must be 0 or 1");
        into = v;
        rest.RemoveRange(i, 2);
    }
    void OptStr(string name, ref string? into)
    {
        int i = rest.IndexOf(name);
        if (i < 0) return;
        if (i + 1 >= rest.Count) throw new CoreValuesWriter.Refusal($"{name} needs a path");
        into = rest[i + 1];
        rest.RemoveRange(i, 2);
    }

    OptStr("--json", ref jsonPath);
    OptInt("--default-rads-rule", ref radsRule);
    OptInt("--default-hardcore", ref hardcore);
    OptInt("--test-mode", ref testMode);
    OptInt("--commonwealth-weather", ref commonwealthWeather);
    OptInt("--fo4-10mm", ref fo410mm);
    OptInt("--fo4-p5-weapons", ref fo4P5Weapons);
    OptInt("--fo4-arsenal", ref fo4Arsenal);
    var opts = new CoreValuesWriter.BuildOptions(jsonPath ?? CoreValuesWriter.DefaultJsonPath(), radsRule, hardcore, testMode, commonwealthWeather, fo410mm, fo4P5Weapons, fo4Arsenal);

    if (rest.Count == 3 && rest[0] == "build") return CoreValuesWriter.Build(rest[1], rest[2], opts);
    if (rest.Count == 3 && rest[0] == "check") return CoreValuesWriter.Check(rest[1], rest[2], opts);
    if (rest.Count == 2 && rest[0] == "fixture") return CoreValuesWriter.Fixture(rest[1]);
    if (rest.Count == 2 && rest[0] == "selftest") return CoreValuesWriter.SelfTest(rest[1]);
}
catch (CoreValuesWriter.Refusal r)
{
    Console.Error.WriteLine("refused: " + r.Message);
    return 1;
}

Console.Error.WriteLine("usage: CoreValues build <Starfield.esm> <out dir> [--json <path>] [--default-rads-rule 0|1] [--default-hardcore 0|1] [--test-mode 0|1] | " +
                        "check <plugin> <Starfield.esm> [same options] | fixture <out dir> | selftest <scratch dir>");
return 2;

public static class CoreValuesWriter
{
    public class Refusal(string m) : Exception(m);
    public record BuildOptions(string JsonPath, int DefaultRadsRule = 0, int DefaultHardcore = 0, int TestMode = 0, int CommonwealthWeather = 1, int Fo410mm = 1, int Fo4P5Weapons = 1, int Fo4Arsenal = 1);
    public record RecordSpec(
        uint Id, string Type, string Edid, string Name, string Abbr, string Desc,
        float Default, float Min, float Max, string[] Flags, string[] Items, string Effect, bool Constant = false);

    const StarfieldRelease Release = StarfieldRelease.Starfield;
    static readonly ModKey SfEsm = ModKey.FromFileName("Starfield.esm");

    // Owned core item Stimpak overrides on schema ID 0x000851
    public const uint Fo4StimpakId = 0x000851;
    public const string Fo4StimpakModel = @"fo4core\props\stimpack01.nif";
    public const float Fo4StimpakWeight = 0.1f;
    public const uint Fo4StimpakValue = 48;

    // A4.1 + Step 4 P5 weapons & ammo: fixed owned FormIDs in FO4SFCoreValues.esm (0x898..0x8A0).
    public const uint Fo4Ammo10mmId = 0x000898;
    public const uint Fo410mmPistolId = 0x000899;
    public const uint Fo4WeapBatonId = 0x00089A;
    public const uint Fo4AmmoFusionCellId = 0x00089B;
    public const uint Fo4AmmoCompFusionCellId = 0x00089C;
    public const uint Fo4WeapLaserMusketId = 0x00089D;
    public const uint Fo4WeapCompPrestonLaserMusketId = 0x00089E;
    public const uint Fo4Ammo5mmId = 0x00089F;
    public const uint Fo4WeapMinigunId = 0x0008A0;

    // Row 5 + Caps + Bobby Pin (0x8A1..0x8A5)
    public const uint Fo4Ammo38Id = 0x0008A1;
    public const uint Fo4WeapPipePistolId = 0x0008A2;
    public const uint Fo4WeapPipeRifleId = 0x0008A3;
    public const uint Fo4MiscCapsId = 0x0008A4;
    public const uint Fo4MiscBobbyPinId = 0x0008A5;

    // Rows 6-20 Ammo (0x8B0..0x8B8), EXPL (0x8B9..0x8BC), PROJ (0x8BD..0x8C0), Laser Ash / Plasma Goo (0x8C1..0x8C4), Weapons (0x8C5..0x8D6)
    public const uint Fo4Ammo308Id = 0x0008B0;
    public const uint Fo4Ammo45Id = 0x0008B1;
    public const uint Fo4AmmoShotgunShellId = 0x0008B2;
    public const uint Fo4Ammo556Id = 0x0008B3;
    public const uint Fo4AmmoMissileId = 0x0008B4;
    public const uint Fo4AmmoMiniNukeId = 0x0008B5;
    public const uint Fo4AmmoFlamerFuelId = 0x0008B6;
    public const uint Fo4AmmoPlasmaCartridgeId = 0x0008B7;
    public const uint Fo4Ammo2mmEcId = 0x0008B8;

    public const uint Fo4ExplFragGrenadeId = 0x0008B9;
    public const uint Fo4ExplFragMineId = 0x0008BA;
    public const uint Fo4ExplMissileId = 0x0008BB;
    public const uint Fo4ExplFatManId = 0x0008BC;

    public const uint Fo4ProjFragGrenadeId = 0x0008BD;
    public const uint Fo4ProjFragMineId = 0x0008BE;
    public const uint Fo4ProjMissileId = 0x0008BF;
    public const uint Fo4ProjFatManId = 0x0008C0;

    public const uint Fo4ActiGooPileId = 0x0008C1;
    public const uint Fo4MgefCritPlasmaId = 0x0008C2;
    public const uint Fo4SpelCritPlasmaId = 0x0008C3;
    public const uint Fo4SpelCritLaserId = 0x0008C4;

    public const uint Fo4WeapUnarmedHumanId = 0x0008C5;
    public const uint Fo4WeapFragGrenadeId = 0x0008C6;
    public const uint Fo4WeapFragMineId = 0x0008C7;
    public const uint Fo4WeapPipeRevolverId = 0x0008C8;
    public const uint Fo4WeapHuntingRifleId = 0x0008C9;
    public const uint Fo4WeapCombatShotgunId = 0x0008CA;
    public const uint Fo4WeapDoubleBarrelId = 0x0008CB;
    public const uint Fo4WeapSubmachineGunId = 0x0008CC;
    public const uint Fo4WeapAssaultRifleId = 0x0008CD;
    public const uint Fo4WeapLaserPistolId = 0x0008CE;
    public const uint Fo4WeapLaserRifleId = 0x0008CF;
    public const uint Fo4WeapBaseballBatId = 0x0008D0;
    public const uint Fo4WeapMissileLauncherId = 0x0008D1;
    public const uint Fo4WeapFatManId = 0x0008D2;
    public const uint Fo4WeapFlamerId = 0x0008D3;
    public const uint Fo4WeapPlasmaPistolId = 0x0008D4;
    public const uint Fo4WeapPlasmaRifleId = 0x0008D5;
    public const uint Fo4WeapGaussRifleId = 0x0008D6;

    public const string Fo4Ammo10mmEdid = "FO4_Ammo10mm";
    public const string Fo410mmPistolEdid = "FO4_10mmPistol";
    public const string Fo4WeapBatonEdid = "FO4_Baton";
    public const string Fo4AmmoFusionCellEdid = "FO4_AmmoFusionCell";
    public const string Fo4AmmoCompFusionCellEdid = "FO4_CompanionAmmoFusionCell";
    public const string Fo4WeapLaserMusketEdid = "FO4_LaserMusket";
    public const string Fo4WeapCompPrestonLaserMusketEdid = "FO4_CompPrestonLaserMusket";
    public const string Fo4Ammo5mmEdid = "FO4_Ammo5mm";
    public const string Fo4WeapMinigunEdid = "FO4_Minigun";

    public const string Fo4Ammo10mmModel = @"fo4core\ammo\10mm\10mmammo.nif";
    public const string Fo410mmPistolModel = @"fo4sf\weapons\10mm\fo4_10mmpistol.nif";
    public const string Fo4WeapBatonModel = @"fo4sf\weapons\baton\fo4_baton.nif";
    public const string Fo4AmmoFusionCellModel = @"fo4core\ammo\laserammo\microfusioncell.nif";
    public const string Fo4WeapLaserMusketModel = @"fo4sf\weapons\lasermusket\fo4_lasermusket.nif";
    public const string Fo4Ammo5mmModel = @"fo4core\ammo\5mm\5mmammo.nif";
    public const string Fo4WeapMinigunModel = @"fo4sf\weapons\minigun\fo4_minigun.nif";

    // Verified F5 Fallout4.esm WEAP.DNAM + DAMA + default OMOD weight/value formula (base * (1 + sum_adds)):
    public const float Fo410mmBaseDamage = 18f;
    public const uint Fo410mmCapacity = 12;
    public const float Fo410mmAttackDelaySec = 0.2143f;
    public const float Fo410mmWeight = 3.525f;
    public const uint Fo410mmValue = 51;
    public const float Fo410mmMinRange = 12f, Fo410mmMaxRange = 30f;
    public const uint Fo4Ammo10mmValue = 2;
    public const float Fo4Ammo10mmWeight = 0.025f;

    public const float Fo4BatonBaseDamage = 11f;          // Fallout4.esm 0x0008C14D
    public const float Fo4BatonWeight = 2.0f;
    public const uint Fo4BatonValue = 15;

    public const ushort Fo4LaserMusketEnergyDamage = 30;  // Fallout4.esm 0x0001DACF DAMA dtEnergy
    public const ushort Fo4PrestonLaserMusketEnergyDamage = 18; // Fallout4.esm 0x00062AA6 DAMA dtEnergy
    public const uint Fo4LaserMusketCapacity = 2;
    public const float Fo4LaserMusketAttackDelaySec = 0.667f; // Derived combat-plan rate (crank stand-in; vanilla Orion 0.75s)
    public const float Fo4LaserMusketWeight = 12.6f;      // 8.0 * (1 + 0.575)
    public const uint Fo4LaserMusketValue = 61;           // 40 * (1 + 0.525)
    public const uint Fo4PrestonLaserMusketBaseValue = 150;
    public const uint Fo4PrestonLaserMusketValue = 195;   // 150 * (1 + 0.1 + 0.2) OBTS[0]
    public const float Fo4PrestonLaserMusketWeight = 10.8f; // 8.0 * (1 + 0.1 + 0.25) OBTS[0]
    public const float Fo4LaserMusketMinRange = 18f, Fo4LaserMusketMaxRange = 45f;
    public const uint Fo4AmmoFusionCellValue = 3;
    public const float Fo4AmmoFusionCellWeight = 0.029f;  // Fallout4.esm 0x000C1897
    public const uint Fo4AmmoCompFusionCellValue = 3;     // Fallout4.esm 0x00245D69

    public const float Fo4MinigunBaseDamage = 8f;
    public const uint Fo4MinigunCapacity = 500;
    public const float Fo4MinigunWeight = 27.45f;         // 18.0 * (1 + 0.525)
    public const uint Fo4MinigunValue = 383;              // 300 * (1 + 0.275) -> 382.5 rounded
    public const uint Fo4Ammo5mmValue = 1;
    public const float Fo4Ammo5mmWeight = 0.009f;         // Fallout4.esm 0x0001F66C

    static readonly FormKey DonorWeapXm2311Key = new(SfEsm, 0x0024561C);
    static readonly FormKey DonorAmmo45Key = new(SfEsm, 0x002B5598);
    static readonly FormKey DonorWeapRescueAxeKey = new(SfEsm, 0x0004F760);
    static readonly FormKey DonorAmmoLaserKey = new(SfEsm, 0x0000E8EC);
    static readonly FormKey DonorWeapOrionKey = new(SfEsm, 0x002773C8);
    static readonly FormKey DonorAmmo777Key = new(SfEsm, 0x0004AD3E);
    static readonly FormKey DonorWeapMicrogunKey = new(SfEsm, 0x000546CD);
    static readonly FormKey DtEnergyKey = new(SfEsm, 0x00060A81);

    static readonly FormKey AnimGripPistolKwKey = new(SfEsm, 0x0000E6C5);
    static readonly FormKey AnimM1919KwKey = new(SfEsm, 0x0019A60E);
    static readonly FormKey AnimOneHandedKwKey = new(SfEsm, 0x000143AA);
    static readonly FormKey AnimGripExtendedLowKwKey = new(SfEsm, 0x00042AD4);
    static readonly FormKey AnimOrionKwKey = new(SfEsm, 0x002773C7);
    static readonly FormKey AnimGripHeavyKwKey = new(SfEsm, 0x00016759);
    static readonly FormKey AnimMicrogunKwKey = new(SfEsm, 0x001C4C33);
    static readonly FormKey TeammateDontUseAmmoKwKey = new(SfEsm, 0x0023F1CA);

    static readonly FormKey ModAssocXm2311KwKey = new(SfEsm, 0x00245FA9);
    static readonly FormKey ModAssocNullMuzzleKwKey = new(SfEsm, 0x001C9E78);
    static readonly FormKey ModAssocRescueAxeKwKey = new(SfEsm, 0x001F70BD);
    static readonly FormKey ModAssocOrionKwKey = new(SfEsm, 0x001F70C6);
    static readonly FormKey ModAssocMicrogunKwKey = new(SfEsm, 0x001F70C9);

    // Additional Rows 5-20 donors, IPDS, Laser Ash & Plasma Goo Starfield keys
    static readonly FormKey DonorWeapEonKey = new(SfEsm, 0x000476C4);
    static readonly FormKey DonorWeapBeowulfKey = new(SfEsm, 0x0004716C);
    static readonly FormKey DonorWeapUnarmedKey = new(SfEsm, 0x000001F4);
    static readonly FormKey DonorWeapFragGrenadeKey = new(SfEsm, 0x000115EF);
    static readonly FormKey DonorWeapFragMineKey = new(SfEsm, 0x0004A41A);
    static readonly FormKey DonorWeapRazorbackKey = new(SfEsm, 0x00000FD6);
    static readonly FormKey DonorWeapLawgiverKey = new(SfEsm, 0x0002D7F4);
    static readonly FormKey DonorWeapPacifierKey = new(SfEsm, 0x002953F8);
    static readonly FormKey DonorWeapCoachmanKey = new(SfEsm, 0x0026D96B);
    static readonly FormKey DonorWeapMaelstromKey = new(SfEsm, 0x002984DF);
    static readonly FormKey DonorWeapAa99Key = new(SfEsm, 0x002BF65B);
    static readonly FormKey DonorWeapSolsticeKey = new(SfEsm, 0x0026D961);
    static readonly FormKey DonorWeapEquinoxKey = new(SfEsm, 0x0001BC4F);
    static readonly FormKey DonorWeapBridgerKey = new(SfEsm, 0x0026D96A);
    static readonly FormKey DonorWeapArcWelderKey = new(SfEsm, 0x0026D965);
    static readonly FormKey DonorWeapNovalightKey = new(SfEsm, 0x0026D967);
    static readonly FormKey DonorWeapInflictorRifleKey = new(SfEsm, 0x0026D8A0);
    static readonly FormKey DonorWeapMagSniperKey = new(SfEsm, 0x0002EB45);

    static readonly FormKey DonorAmmo50CalKey = new(SfEsm, 0x002B5597);
    static readonly FormKey DonorAmmoShotshellKey = new(SfEsm, 0x002B4AFB);
    static readonly FormKey DonorAmmo11mmKey = new(SfEsm, 0x002B5595);
    static readonly FormKey DonorAmmo40mmXplKey = new(SfEsm, 0x002B5592);

    static readonly FormKey DonorProjFragGrenadeKey = new(SfEsm, 0x000E574E);
    static readonly FormKey DonorProjFragMineKey = new(SfEsm, 0x0005AB87);
    static readonly FormKey DonorProjBridgerRocketKey = new(SfEsm, 0x0029AE2F);
    static readonly FormKey DonorExplFragGrenadeKey = new(SfEsm, 0x000E574F);
    static readonly FormKey DonorExplBridgerRocketKey = new(SfEsm, 0x0029AE30);

    static readonly FormKey SfActiAshPile01Key = new(SfEsm, 0x0009142E);
    static readonly FormKey SfSpelCritLaserDisintKey = new(SfEsm, 0x0024EF1F);
    static readonly FormKey SfMgefCritLaserEffectKey = new(SfEsm, 0x0024EF20);
    static readonly FormKey SfMiscCreditsKey = new(SfEsm, 0x0000000F);
    static readonly FormKey SfMiscDigipickKey = new(SfEsm, 0x0000000A);

    // Explicit Starfield.esm ImpactDataSet (WVIS / EXPL.ENAM) FormKeys
    static readonly FormKey IpdsBulletKey = new(SfEsm, 0x0000D02C);             // FXProjectileBulletImpactSet
    static readonly FormKey IpdsMeleeBashSmallKey = new(SfEsm, 0x000116F1);     // WPNMeleeBashGunSmallImpactSet (blunt melee)
    static readonly FormKey IpdsMeleeBladeSmallKey = new(SfEsm, 0x00055DC3);    // WPNHandBladeSmall_ImpactSet (retained for check/tamper rejection)
    static readonly FormKey IpdsMeleeBladeMediumKey = new(SfEsm, 0x0005C498);   // WPNMeleeImpactBladeMediumSet (retained for check/tamper rejection)
    static readonly FormKey IpdsOrionLaserKey = new(SfEsm, 0x001C1162);         // FXProjectileOrionLaserImpactSet
    static readonly FormKey IpdsEquinoxLaserKey = new(SfEsm, 0x001F5DA1);       // FXProjectileEquinoxLaserImpactSet
    static readonly FormKey IpdsExplosiveKey = new(SfEsm, 0x0015CCFD);          // FXProjectileExplosiveImpactSet
    static readonly FormKey IpdsRocketKey = new(SfEsm, 0x003A5907);             // FXProjectileRocketImpactSet
    static readonly FormKey IpdsUnarmedBashKey = new(SfEsm, 0x00252B4C);        // WPNMeleeBashHandImpactSet
    static readonly FormKey IpdsShotgunKey = new(SfEsm, 0x00239D0F);            // FXProjectileShotgunImpactSet
    static readonly FormKey IpdsCoachmanShotgunKey = new(SfEsm, 0x001D7FEC);    // FXProjectileShotgunCoachmanSet
    static readonly FormKey IpdsFlamethrowerKey = new(SfEsm, 0x00115BE5);       // FXProjectileFlamethrowerImpactSet
    static readonly FormKey IpdsParticlePistolKey = new(SfEsm, 0x00164E05);     // FXParticlePistoltImpactSet
    static readonly FormKey IpdsParticleRifleKey = new(SfEsm, 0x00164E03);      // FXParticletImpactSet
    static readonly FormKey IpdsMagBulletKey = new(SfEsm, 0x0034BE5D);          // FXProjectileBulletMagImpactSet

    static readonly (uint Id, string Edid, FormKey Donor, float Dmg, float Force, float InnerM, float OuterM, float IsM, FormKey IpdsKey)[] ArsenalExplSpecs =
    {
        (Fo4ExplFragGrenadeId, "FO4_FragGrenadeExplosion", DonorExplFragGrenadeKey, 150f, 120f, 2.14f, 7.14f, 14.3f, IpdsRocketKey),
        (Fo4ExplFragMineId,    "FO4_FragMineExplosion",    DonorExplFragGrenadeKey, 100f, 120f, 1.43f, 7.14f, 11.0f, IpdsRocketKey),
        (Fo4ExplMissileId,     "FO4_MissileExplosion",     DonorExplBridgerRocketKey, 135f, 120f, 2.14f, 7.14f, 28.6f, IpdsExplosiveKey),
        (Fo4ExplFatManId,      "FO4_FatManExplosion",      DonorExplBridgerRocketKey, 450f, 150f, 4.29f, 12.14f, 60.0f, IpdsExplosiveKey),
    };

    static readonly (uint Id, string Edid, FormKey Donor, string Model, uint ExplId, float? SpeedOpt, float? GravityOpt)[] ArsenalProjSpecs =
    {
        (Fo4ProjFragGrenadeId, "FO4_FragGrenadeProjectile", DonorProjFragGrenadeKey, @"fo4sf\weapons\grenade\grenadefragprojectile.nif", Fo4ExplFragGrenadeId, null, null),
        (Fo4ProjFragMineId,    "FO4_FragMineProjectile",    DonorProjFragMineKey,    @"fo4sf\weapons\mine\fragmineprojectile.nif",       Fo4ExplFragMineId,    null, null),
        (Fo4ProjMissileId,     "FO4_MissileProjectile",     DonorProjBridgerRocketKey, @"fo4core\ammo\missile\missile.nif",             Fo4ExplMissileId,     90f,  0.05f),
        (Fo4ProjFatManId,      "FO4_FatManProjectile",      DonorProjBridgerRocketKey, @"fo4core\ammo\fatman\ammofatman.nif",           Fo4ExplFatManId,      35f,  0.80f),
    };

    static readonly (uint Id, string Edid, string Name, string Short, FormKey Donor, uint Val, float Wt, string Model, uint ProjId)[] ArsenalAmmoSpecs =
    {
        (Fo4Ammo38Id,             "FO4_Ammo38Caliber",        ".38 Round",                 ".38",   DonorAmmo45Key,        1,   0.015f, @"fo4core\ammo\38\38ammo.nif",                       0),
        (Fo4Ammo308Id,            "FO4_Ammo308Caliber",       ".308 Round",                ".308",  DonorAmmo50CalKey,     3,   0.041f, @"fo4core\ammo\308\308ammo.nif",                     0),
        (Fo4Ammo45Id,             "FO4_Ammo45Caliber",        ".45 Round",                 ".45",   DonorAmmo45Key,        2,   0.030f, @"fo4core\ammo\45cal\45ammo.nif",                    0),
        (Fo4AmmoShotgunShellId,   "FO4_AmmoShotgunShell",     "Shotgun Shell",             "Shell", DonorAmmoShotshellKey, 3,   0.100f, @"fo4core\ammo\shotgunshell\shotgunshellammo.nif",   0),
        (Fo4Ammo556Id,            "FO4_Ammo556",              "5.56 Round",                "5.56",  DonorAmmo11mmKey,      2,   0.035f, @"fo4core\ammo\556\556ammo.nif",                     0),
        (Fo4AmmoMissileId,        "FO4_AmmoMissile",          "Missile",                   "Msl",   DonorAmmo40mmXplKey,   25,  7.000f, @"fo4core\ammo\missile\missile.nif",                 Fo4ProjMissileId),
        (Fo4AmmoMiniNukeId,       "FO4_AmmoMiniNuke",         "Mini Nuke",                 "Nuke",  DonorAmmo40mmXplKey,   100, 12.000f,@"fo4core\ammo\fatman\ammofatman.nif",               Fo4ProjFatManId),
        (Fo4AmmoFlamerFuelId,     "FO4_AmmoFlamerFuel",       "Flamer Fuel",               "Fuel",  DonorAmmoLaserKey,     1,   0.010f, @"fo4core\ammo\flamer\flamerfuel.nif",               0),
        (Fo4AmmoPlasmaCartridgeId,"FO4_AmmoPlasmaCartridge",  "Plasma Cartridge",          "Plsm",  DonorAmmoLaserKey,     5,   0.030f, @"fo4core\ammo\plasma\plasmacellmagazine.nif",       0),
        (Fo4Ammo2mmEcId,          "FO4_Ammo2mmEC",            "2mm EC Cartridge",          "2mm",   DonorAmmo50CalKey,     10,  0.128f, @"fo4core\ammo\gaussrifleammo\gaussrifleammo.nif",   0),
    };

    static readonly (uint Id, string Edid, string Name, FormKey Donor, string? Model, uint AmmoId, uint Cap, float PhysDmg, ushort EnergyDmg, float DelaySec, float? SpeedOpt, float? ReachOpt, float Wt, uint Val, FormKey IpdsKey, uint CritSpellId, uint OverrideProjId, bool NonPlayable)[] ArsenalWeapSpecs =
    {
        (Fo4WeapPipePistolId,      "FO4_PipePistol",          "Pipe Pistol",            DonorWeapEonKey,           @"fo4sf\weapons\pipegun\fo4_pipepistol.nif",             Fo4Ammo38Id,              12,  13f,  0,  0.180f, null,  null, 2.350f,  23, IpdsBulletKey,        0,                  0,                    false),
        (Fo4WeapPipeRifleId,       "FO4_PipeRifle",           "Pipe Rifle",             DonorWeapBeowulfKey,       @"fo4sf\weapons\pipegun\fo4_piperifle.nif",              Fo4Ammo38Id,              12,  13f,  0,  0.180f, null,  null, 3.400f,  28, IpdsBulletKey,        0,                  0,                    false),
        (Fo4WeapUnarmedHumanId,    "FO4_UnarmedHuman",        "Unarmed",                DonorWeapUnarmedKey,       null,                                                    0,                        0,   8f,   0,  0f,     null,  0.68f,0.000f,   0, IpdsUnarmedBashKey,   0,                  0,                    true),
        (Fo4WeapFragGrenadeId,     "FO4_FragGrenade",         "Frag Grenade",           DonorWeapFragGrenadeKey,   @"fo4sf\weapons\fraggrenade\fo4_fraggrenade.nif",        0,                        0,   1f,   0,  0f,     null,  null, 0.500f,  50, IpdsExplosiveKey,     0,                  Fo4ProjFragGrenadeId, false),
        (Fo4WeapFragMineId,        "FO4_FragMine",            "Frag Mine",              DonorWeapFragMineKey,      @"fo4sf\weapons\fragmine\fo4_fragmine.nif",              0,                        0,   1f,   0,  0f,     null,  null, 0.500f,  50, IpdsExplosiveKey,     0,                  Fo4ProjFragMineId,    false),
        (Fo4WeapPipeRevolverId,    "FO4_PipeRevolver",        "Pipe Revolver",          DonorWeapRazorbackKey,     @"fo4sf\weapons\piperevolver\fo4_piperevolver.nif",      Fo4Ammo45Id,              6,   24f,  0,  0.150f, null,  null, 4.300f,  28, IpdsBulletKey,        0,                  0,                    false),
        (Fo4WeapHuntingRifleId,    "FO4_HuntingRifle",        "Hunting Rifle",          DonorWeapLawgiverKey,      @"fo4sf\weapons\huntingrifle\fo4_huntingrifle.nif",      Fo4Ammo308Id,             5,   37f,  0,  0.150f, 1.25f, null, 9.600f,  55, IpdsBulletKey,        0,                  0,                    false),
        (Fo4WeapCombatShotgunId,   "FO4_CombatShotgun",       "Combat Shotgun",         DonorWeapPacifierKey,      @"fo4sf\weapons\combatshotgun\fo4_combatshotgun.nif",    Fo4AmmoShotgunShellId,    8,   50f,  0,  0.500f, null,  null, 11.200f, 89, IpdsShotgunKey,       0,                  0,                    false),
        (Fo4WeapDoubleBarrelId,    "FO4_DoubleBarrelShotgun", "Double-Barrel Shotgun",  DonorWeapCoachmanKey,      @"fo4sf\weapons\doublebarrel\fo4_doublebarrel.nif",      Fo4AmmoShotgunShellId,    2,   45f,  0,  0.275f, null,  null, 9.000f,  41, IpdsCoachmanShotgunKey,0,                 0,                    false),
        (Fo4WeapSubmachineGunId,   "FO4_SubmachineGun",       "Submachine Gun",         DonorWeapMaelstromKey,     @"fo4sf\weapons\submachinegun\fo4_submachinegun.nif",    Fo4Ammo45Id,              50,  9.75f, 0,  0.150f, 1.40f, null, 12.775f,110, IpdsBulletKey,        0,                  0,                    false), // P6-H1: OMOD 0015B044 AttackDamage -0.25 -> 13 * 0.75 = 9.75f (exact float)
        (Fo4WeapAssaultRifleId,    "FO4_AssaultRifle",        "Assault Rifle",          DonorWeapAa99Key,          @"fo4sf\weapons\assaultrifle\fo4_assaultrifle.nif",      Fo4Ammo556Id,             30,  30f,   0,  0.250f, null,  null, 13.200f,145, IpdsBulletKey,        0,                  0,                    false), // P6-H1: OMOD 0018896B AmmoCapacity +0.50 -> 20 * 1.5 = 30
        (Fo4WeapLaserPistolId,     "FO4_LaserPistol",         "Laser Pistol",           DonorWeapSolsticeKey,      @"fo4sf\weapons\lasergun\fo4_laserpistol.nif",          Fo4AmmoFusionCellId,      30,  0f,    24, 0.200f, null,  null, 3.975f,  68, IpdsEquinoxLaserKey,  Fo4SpelCritLaserId, 0,                    false),
        (Fo4WeapLaserRifleId,      "FO4_LaserRifle",          "Laser Rifle",            DonorWeapEquinoxKey,       @"fo4sf\weapons\lasergun\fo4_laserrifle.nif",           Fo4AmmoFusionCellId,      27,  0f,    26, 0.200f, null,  null, 5.250f,  81, IpdsEquinoxLaserKey,  Fo4SpelCritLaserId, 0,                    false), // P6-H1: OMOD 00091FB5 Cap -0.10 -> 27; dtEnergy +0.096 -> 26.304 -> 26 (round-half-away-from-zero ushort)
        (Fo4WeapBaseballBatId,     "FO4_BaseballBat",         "Baseball Bat",           DonorWeapRescueAxeKey,     @"fo4sf\weapons\baseballbat\fo4_baseballbat.nif",        0,                        0,   16f,   0,  0f,     null,  0.80f,3.000f,  25, IpdsMeleeBashSmallKey,0,                  0,                    false), // P6-H2: blunt bash impact set 000116F1
        (Fo4WeapMissileLauncherId, "FO4_MissileLauncher",     "Missile Launcher",       DonorWeapBridgerKey,       @"fo4sf\weapons\missilelauncher\fo4_missilelauncher.nif",Fo4AmmoMissileId,         1,   15f,   0,  0.400f, null,  null, 21.000f,315, IpdsExplosiveKey,     0,                  Fo4ProjMissileId,     false),
        (Fo4WeapFatManId,          "FO4_FatMan",              "Fat Man",                DonorWeapBridgerKey,       @"fo4sf\weapons\fatman\fo4_fatman.nif",                  Fo4AmmoMiniNukeId,        1,   18f,   0,  0f,     null,  null, 30.750f,513, IpdsExplosiveKey,     0,                  Fo4ProjFatManId,      false),
        (Fo4WeapFlamerId,          "FO4_Flamer",              "Flamer",                 DonorWeapArcWelderKey,     @"fo4sf\weapons\flamer\fo4_flamer.nif",                  Fo4AmmoFlamerFuelId,      100, 0f,    9,  0.150f, null,  null, 16.125f,138, IpdsFlamethrowerKey,  0,                  0,                    false),
        (Fo4WeapPlasmaPistolId,    "FO4_PlasmaPistol",        "Plasma Pistol",          DonorWeapNovalightKey,     @"fo4sf\weapons\plasmagun\fo4_plasmapistol.nif",         Fo4AmmoPlasmaCartridgeId, 30,  24f,   24, 0.300f, null,  null, 3.975f, 126, IpdsParticlePistolKey,Fo4SpelCritPlasmaId,0,                    false),
        (Fo4WeapPlasmaRifleId,     "FO4_PlasmaRifle",         "Plasma Rifle",           DonorWeapInflictorRifleKey,@"fo4sf\weapons\plasmagun\fo4_plasmarifle.nif",          Fo4AmmoPlasmaCartridgeId, 30,  24f,   24, 0.300f, null,  null, 4.800f, 157, IpdsParticleRifleKey, Fo4SpelCritPlasmaId,0,                    false),
        (Fo4WeapGaussRifleId,      "FO4_GaussRifle",          "Gauss Rifle",            DonorWeapMagSniperKey,     @"fo4sf\weapons\gaussrifle\fo4_gaussrifle.nif",          Fo4Ammo2mmEcId,           8,   110f,  0,  0.150f, null,  null, 15.800f,229, IpdsMagBulletKey,     0,                  0,                    false), // P6-H1: OMOD 001AC252 Cap +0.50 -> 7.5 -> 8 (round-half-away-from-zero ushort)
    };

    const string ExpectedDonorWeapXm2311Edid = "XM2311";
    const string ExpectedDonorAmmo45Edid = "Ammo45Caliber";
    const string ExpectedDonorWeapRescueAxeEdid = "RescueAxe";
    const string ExpectedDonorAmmoLaserEdid = "AmmoLaser";
    const string ExpectedDonorWeapOrionEdid = "Orion";
    const string ExpectedDonorAmmo777Edid = "Ammo777mm";
    const string ExpectedDonorWeapMicrogunEdid = "Microgun";

    static readonly HashSet<FormKey> ExplicitStripKwKeys = new()
    {
        ModAssocXm2311KwKey, ModAssocNullMuzzleKwKey, ModAssocRescueAxeKwKey, ModAssocOrionKwKey, ModAssocMicrogunKwKey,
    };

    static string NormModelPath(string? p) => (p ?? string.Empty).Trim().Replace('/', '\\').TrimStart('\\');

    static bool IsDonorBrandingOrSlotKeyword(string? edid)
    {
        if (string.IsNullOrEmpty(edid)) return false;
        return edid.StartsWith("Manufacturer", StringComparison.OrdinalIgnoreCase)
            || edid.StartsWith("UI_Icon_", StringComparison.OrdinalIgnoreCase)
            || edid.StartsWith("ma_", StringComparison.OrdinalIgnoreCase);
    }

    static void StripDonorWeaponKeywords(IStarfieldModGetter sf, Weapon weap, bool keepTeammateDontUseAmmo = false)
    {
        if (weap.Keywords == null) return;
        for (int ki = weap.Keywords.Count - 1; ki >= 0; ki--)
        {
            var kfk = weap.Keywords[ki].FormKey;
            if (ExplicitStripKwKeys.Contains(kfk) || (!keepTeammateDontUseAmmo && kfk == TeammateDontUseAmmoKwKey))
            {
                weap.Keywords.RemoveAt(ki);
                continue;
            }
            if (sf.Keywords.TryGetValue(kfk, out var kw) && IsDonorBrandingOrSlotKeyword(kw.EditorID))
                weap.Keywords.RemoveAt(ki);
        }
    }

    static void Validate10mmDonorEditorIds(IStarfieldModGetter sf)
    {
        bool hasWeap = sf.Weapons.TryGetValue(DonorWeapXm2311Key, out var xm2311);
        bool hasAmmo = sf.Ammunitions.TryGetValue(DonorAmmo45Key, out var ammo45);
        if (hasWeap != hasAmmo)
            throw new Refusal($"Starfield.esm partial 10mm donor set: WEAP {DonorWeapXm2311Key}={hasWeap}, AMMO {DonorAmmo45Key}={hasAmmo}");
        if (hasWeap && !string.Equals(xm2311!.EditorID, ExpectedDonorWeapXm2311Edid, StringComparison.Ordinal))
            throw new Refusal($"WEAP {DonorWeapXm2311Key} EditorID '{xm2311.EditorID ?? "<null>"}' != expected '{ExpectedDonorWeapXm2311Edid}'");
        if (hasAmmo && !string.Equals(ammo45!.EditorID, ExpectedDonorAmmo45Edid, StringComparison.Ordinal))
            throw new Refusal($"AMMO {DonorAmmo45Key} EditorID '{ammo45.EditorID ?? "<null>"}' != expected '{ExpectedDonorAmmo45Edid}'");
    }

    static bool HasP5DonorSet(IStarfieldModGetter sf)
    {
        bool[] present =
        {
            sf.Weapons.TryGetValue(DonorWeapRescueAxeKey, out var axe),
            sf.Ammunitions.TryGetValue(DonorAmmoLaserKey, out var ammoLaser),
            sf.Weapons.TryGetValue(DonorWeapOrionKey, out var orion),
            sf.Ammunitions.TryGetValue(DonorAmmo777Key, out var ammo777),
            sf.Weapons.TryGetValue(DonorWeapMicrogunKey, out var microgun),
        };
        if (present.All(p => !p))
            return false;
        if (!present.All(p => p))
            throw new Refusal($"Starfield.esm partial P5 weapon donor set: [{string.Join(", ", present)}]");
        static void Req(string kind, FormKey fk, string? got, string want)
        {
            if (!string.Equals(got, want, StringComparison.Ordinal))
                throw new Refusal($"{kind} {fk} EditorID '{got ?? "<null>"}' != expected '{want}'");
        }
        Req("WEAP", DonorWeapRescueAxeKey, axe!.EditorID, ExpectedDonorWeapRescueAxeEdid);
        Req("AMMO", DonorAmmoLaserKey, ammoLaser!.EditorID, ExpectedDonorAmmoLaserEdid);
        Req("WEAP", DonorWeapOrionKey, orion!.EditorID, ExpectedDonorWeapOrionEdid);
        Req("AMMO", DonorAmmo777Key, ammo777!.EditorID, ExpectedDonorAmmo777Edid);
        Req("WEAP", DonorWeapMicrogunKey, microgun!.EditorID, ExpectedDonorWeapMicrogunEdid);
        return true;
    }

    static bool HasArsenalDonorSet(IStarfieldModGetter sf)
    {
        bool[] present =
        {
            sf.Weapons.ContainsKey(DonorWeapEonKey),
            sf.Weapons.ContainsKey(DonorWeapBeowulfKey),
            sf.Weapons.ContainsKey(DonorWeapUnarmedKey),
            sf.Weapons.ContainsKey(DonorWeapFragGrenadeKey),
            sf.Weapons.ContainsKey(DonorWeapFragMineKey),
            sf.Weapons.ContainsKey(DonorWeapRazorbackKey),
            sf.Weapons.ContainsKey(DonorWeapLawgiverKey),
            sf.Weapons.ContainsKey(DonorWeapPacifierKey),
            sf.Weapons.ContainsKey(DonorWeapCoachmanKey),
            sf.Weapons.ContainsKey(DonorWeapMaelstromKey),
            sf.Weapons.ContainsKey(DonorWeapAa99Key),
            sf.Weapons.ContainsKey(DonorWeapSolsticeKey),
            sf.Weapons.ContainsKey(DonorWeapEquinoxKey),
            sf.Weapons.ContainsKey(DonorWeapBridgerKey),
            sf.Weapons.ContainsKey(DonorWeapArcWelderKey),
            sf.Weapons.ContainsKey(DonorWeapNovalightKey),
            sf.Weapons.ContainsKey(DonorWeapInflictorRifleKey),
            sf.Weapons.ContainsKey(DonorWeapMagSniperKey),
            sf.Ammunitions.ContainsKey(DonorAmmo50CalKey),
            sf.Ammunitions.ContainsKey(DonorAmmoShotshellKey),
            sf.Ammunitions.ContainsKey(DonorAmmo11mmKey),
            sf.Ammunitions.ContainsKey(DonorAmmo40mmXplKey),
            sf.Projectiles.ContainsKey(DonorProjFragGrenadeKey),
            sf.Projectiles.ContainsKey(DonorProjFragMineKey),
            sf.Projectiles.ContainsKey(DonorProjBridgerRocketKey),
            sf.Explosions.ContainsKey(DonorExplFragGrenadeKey),
            sf.Explosions.ContainsKey(DonorExplBridgerRocketKey),
            sf.Activators.ContainsKey(SfActiAshPile01Key),
            sf.Spells.ContainsKey(SfSpelCritLaserDisintKey),
            sf.MagicEffects.ContainsKey(SfMgefCritLaserEffectKey),
            sf.MiscItems.ContainsKey(SfMiscCreditsKey),
            sf.MiscItems.ContainsKey(SfMiscDigipickKey),
        };
        if (present.All(p => !p))
            return false;
        if (!present.All(p => p))
            throw new Refusal($"Starfield.esm partial Arsenal donor set (matched {present.Count(p => p)}/{present.Length})");
        return true;
    }

    static void SetWeaponDamage(Weapon weap, float physDmg, ushort energyDmg)
    {
        weap.AttackDamage = physDmg;
        weap.DamageTypes ??= new ExtendedList<WeaponDamageType>();
        weap.DamageTypes.Clear();
        if (energyDmg > 0)
        {
            weap.DamageTypes.Add(new WeaponDamageType
            {
                DamageType = new FormLink<IDamageTypeGetter>(DtEnergyKey),
                Value = energyDmg,
            });
        }
    }

    static void SetWeaponEnergyDamage(Weapon weap, ushort energyDmg) => SetWeaponDamage(weap, 0f, energyDmg);

    static bool HasWeaponEnergyDamage(IWeaponGetter weap, ushort expected)
    {
        var hit = weap.DamageTypes?.FirstOrDefault(d => d.DamageType.FormKey == DtEnergyKey);
        return hit != null && Math.Abs((double)hit.Value - expected) < 1e-4;
    }

    // D7(a): binary-verified Starfield.esm FormIDs driving Mars/Cydonia dust storms over FO4Core_Commonwealth
    // (WRLD 0x01000803 BNAM -> BIOM 0x002A3777 DesertRockyNoLifeMars -> ENAM CLMT 0x00310DB1 ClimateUniqueCydonia;
    //  PNDT 0x0003F59A MarsPlanetData -> ATMO 0x0000C9D2 ATMO_Mars).
    static readonly FormKey ClimateCydoniaKey = new(SfEsm, 0x00310DB1);
    static readonly FormKey ClimateCydoniaFrozenKey = new(SfEsm, 0x002EDEA5);
    static readonly FormKey ClimateNewAtlantisKey = new(SfEsm, 0x0024E982);
    static readonly FormKey AtmoMarsKey = new(SfEsm, 0x0000C9D2);
    static readonly FormKey AtmoJemisonKey = new(SfEsm, 0x0000C010);
    const string ExpectedClimateNewAtlantisEdid = "ClimateUniqueNewAtlantis";
    const string ExpectedClimateCydoniaEdid = "ClimateUniqueCydonia";
    const string ExpectedClimateCydoniaFrozenEdid = "ClimateUniqueCydoniaFrozen";
    const string ExpectedAtmoMarsEdid = "ATMO_Mars";
    const string ExpectedAtmoJemisonEdid = "ATMO_Jemison";
    static readonly HashSet<FormKey> AllowedWeatherOverrideKeys = new()
    {
        ClimateCydoniaKey,
        ClimateCydoniaFrozenKey,
        AtmoMarsKey,
    };

    static void ValidateWeatherSourceEditorIds(
        Dictionary<FormKey, IClimateGetter> sfClimates,
        Dictionary<FormKey, IAtmosphereGetter> sfAtmos)
    {
        static void RequireEdid(string kind, FormKey fk, string? actual, string expected)
        {
            if (!string.Equals(actual, expected, StringComparison.Ordinal))
                throw new Refusal($"{kind} {fk} EditorID '{actual ?? "<null>"}' != expected '{expected}'");
        }
        if (sfClimates.TryGetValue(ClimateNewAtlantisKey, out var naClmt))
            RequireEdid("CLMT", ClimateNewAtlantisKey, naClmt.EditorID, ExpectedClimateNewAtlantisEdid);
        if (sfClimates.TryGetValue(ClimateCydoniaKey, out var cydClmt))
            RequireEdid("CLMT", ClimateCydoniaKey, cydClmt.EditorID, ExpectedClimateCydoniaEdid);
        if (sfClimates.TryGetValue(ClimateCydoniaFrozenKey, out var cydFrzClmt))
            RequireEdid("CLMT", ClimateCydoniaFrozenKey, cydFrzClmt.EditorID, ExpectedClimateCydoniaFrozenEdid);
        if (sfAtmos.TryGetValue(AtmoMarsKey, out var marsAtmo))
            RequireEdid("ATMO", AtmoMarsKey, marsAtmo.EditorID, ExpectedAtmoMarsEdid);
        if (sfAtmos.TryGetValue(AtmoJemisonKey, out var jemAtmo))
            RequireEdid("ATMO", AtmoJemisonKey, jemAtmo.EditorID, ExpectedAtmoJemisonEdid);
    }

    public static string DefaultJsonPath()
    {
        var dir = AppContext.BaseDirectory;
        for (int up = 0; up < 8 && dir != null; up++, dir = Directory.GetParent(dir)?.FullName)
        {
            var candidate = Path.Combine(dir, "src", "fo4sf", "core", "core_values.json");
            if (File.Exists(candidate)) return candidate;
        }
        var cwd = Path.Combine(Directory.GetCurrentDirectory(), "src", "fo4sf", "core", "core_values.json");
        if (File.Exists(cwd)) return cwd;
        throw new Refusal("cannot locate src/fo4sf/core/core_values.json; pass --json <path>");
    }

    public static (ModKey PluginKey, uint NextFormId, List<RecordSpec> Specs) LoadSchema(string jsonPath)
    {
        if (!File.Exists(jsonPath)) throw new Refusal($"missing schema json: {jsonPath}");
        using var doc = JsonDocument.Parse(File.ReadAllText(jsonPath));
        var root = doc.RootElement;
        var pluginName = root.GetProperty("plugin").GetString() ?? throw new Refusal("schema missing plugin");
        var nextHex = root.GetProperty("next_form_id").GetString() ?? throw new Refusal("schema missing next_form_id");
        uint nextId = Convert.ToUInt32(nextHex, 16);
        var specs = new List<RecordSpec>();
        var seenIds = new HashSet<uint>();
        var seenEdids = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        foreach (var el in root.GetProperty("records").EnumerateArray())
        {
            uint id = Convert.ToUInt32(el.GetProperty("id").GetString()!, 16);
            string type = el.GetProperty("type").GetString()!;
            string edid = el.GetProperty("edid").GetString()!;
            if (!seenIds.Add(id)) throw new Refusal($"duplicate FormID 0x{id:X6} in {jsonPath}");
            if (!seenEdids.Add(edid)) throw new Refusal($"duplicate EditorID {edid} in {jsonPath}");

            string Str(string k) => el.TryGetProperty(k, out var v) ? v.GetString() ?? "" : "";
            float Flt(string k) => el.TryGetProperty(k, out var v) ? v.GetSingle() : 0f;
            bool Bool(string k) => el.TryGetProperty(k, out var v) && v.GetBoolean();
            string[] Arr(string k) => el.TryGetProperty(k, out var v)
                ? v.EnumerateArray().Select(x => x.GetString()!).ToArray()
                : Array.Empty<string>();
            if (id >= nextId) throw new Refusal($"FormID 0x{id:X6} ({edid}) >= next_form_id 0x{nextId:X6} in {jsonPath}");

            specs.Add(new RecordSpec(
                id, type, edid, Str("name"), Str("abbr"), Str("desc"),
                Flt("default"), Flt("min"), Flt("max"), Arr("flags"), Arr("items"), Str("effect"), Bool("constant")));
        }
        return (ModKey.FromFileName(pluginName), nextId, specs);
    }

    static IStarfieldModDisposableGetter OpenMod(string path)
    {
        var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        styles.Set(new KeyedMasterStyle(SfEsm, MasterStyle.Full));
        return StarfieldMod.CreateFromBinaryOverlay(path, Release, new BinaryReadParameters { MasterFlagsLookup = styles });
    }

    static ActorValueInformation.Flag ParseAvifFlags(string[] names)
    {
        ActorValueInformation.Flag f = 0;
        foreach (var n in names)
        {
            f |= n switch
            {
                "DefaultToZero" => ActorValueInformation.Flag.DefaultToZero,
                "DamageIsPositive" => ActorValueInformation.Flag.DamageIsPositive,
                "DefaultToOne" => ActorValueInformation.Flag.DefaultToOne,
                "MinimumOne" => ActorValueInformation.Flag.MinimumOne,
                "MaximumTen" => ActorValueInformation.Flag.MaximumTen,
                _ => throw new Refusal($"unknown AVIF flag '{n}'"),
            };
        }
        return f;
    }

    static float EffectiveGlobValue(RecordSpec s, BuildOptions opts) => s.Edid switch
    {
        "FO4SF_RadsRule" => opts.DefaultRadsRule,
        "FO4SF_HardcoreEnabled" => opts.DefaultHardcore,
        "FO4SF_HardcoreFastTravelBlocked" => opts.DefaultHardcore,
        "FO4SF_TestModeEnabled" => opts.TestMode,
        _ => s.Default,
    };

    static void RefuseForbiddenOutDir(string outDir)
    {
        var full = Path.GetFullPath(outDir);
        for (var cur = new DirectoryInfo(full); cur != null; cur = cur.Parent)
        {
            if (Directory.Exists(Path.Combine(cur.FullName, ".git")) || File.Exists(Path.Combine(cur.FullName, ".git")))
                throw new Refusal($"output folder inside Git worktree is forbidden: {full}");
            if (File.Exists(Path.Combine(cur.FullName, "Starfield.exe")))
                throw new Refusal($"output folder inside game install is forbidden: {full}");
        }
    }

    static void WriteMod(StarfieldMod mod, ModKey pluginKey, string outDir)
    {
        RefuseForbiddenOutDir(outDir);
        Directory.CreateDirectory(outDir);
        var finalPath = Path.Combine(outDir, pluginKey.FileName);
        var tmpDir = Path.Combine(outDir, ".tmp-" + Guid.NewGuid().ToString("N"));
        try
        {
            Directory.CreateDirectory(tmpDir);
            var tmpPath = Path.Combine(tmpDir, pluginKey.FileName);
            if (pluginKey == SfEsm)
            {
                mod.BeginWrite.ToPath(tmpPath).WithNoLoadOrder().NoCheckIfLowerRangeDisallowed().Write();
            }
            else
            {
                var masters = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
                masters.Set(new KeyedMasterStyle(SfEsm, MasterStyle.Full));
                mod.WriteToBinary(tmpPath, new BinaryWriteParameters
                {
                    ModKey = ModKeyOption.NoCheck,
                    MastersListOrdering = new MastersListOrderingByLoadOrder(new[] { SfEsm }),
                    MasterFlagsLookup = masters,
                });
            }
            File.Move(tmpPath, finalPath, overwrite: true);
        }
        finally
        {
            if (Directory.Exists(tmpDir)) Directory.Delete(tmpDir, recursive: true);
        }
    }

    public static int Build(string sfPath, string outDir, BuildOptions opts)
    {
        var (pluginKey, nextId, specs) = LoadSchema(opts.JsonPath);
        using var sf = OpenMod(sfPath);
        var healthHits = sf.ActorValueInformation.Where(a => string.Equals(a.EditorID, "Health", StringComparison.OrdinalIgnoreCase)).ToList();
        if (healthHits.Count != 1 || healthHits[0].FormKey.ModKey != SfEsm)
            throw new Refusal("Starfield.esm must own exactly one Health AVIF");
        var healthKey = healthHits[0].FormKey;

        // Optional aid/mgef template from Starfield.esm (falls back cleanly on synthetic fixtures)
        var mgefs = sf.MagicEffects.ToDictionary(m => m.FormKey);
        IIngestibleGetter? aidTpl = null;
        IMagicEffectGetter? mgefTpl = null;
        IEffectGetter? entryTpl = null;
        foreach (var i in sf.Ingestibles.Where(i => i.Effects.Count == 1 && i.Addiction.IsNull).OrderBy(i => i.FormKey.ID))
        {
            if (i.Effects[0].BaseEffect.FormKey is { } fk && mgefs.TryGetValue(fk, out var m) &&
                m.Archetype.Type == MagicEffectArchetype.TypeEnum.ValueModifier && m.SecondActorValue.FormKey == healthKey &&
                !m.Flags.HasFlag(MagicEffect.Flag.Detrimental) && i.Effects[0].Data?.Duration == 0)
            {
                aidTpl = i;
                mgefTpl = m;
                entryTpl = i.Effects[0];
                break;
            }
        }

        var mod = new StarfieldMod(pluginKey, Release);
        mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        mod.ModHeader.Author = "fo4-to-starfield CoreValues";

        var byEdid = new Dictionary<string, FormKey>(StringComparer.OrdinalIgnoreCase);

        // Pass 1: AVIF, GLOB, MGEF
        foreach (var s in specs.Where(x => x.Type is "AVIF" or "GLOB" or "MGEF"))
        {
            var fk = new FormKey(pluginKey, s.Id);
            byEdid[s.Edid] = fk;
            if (s.Type == "AVIF")
            {
                mod.ActorValueInformation.Add(new ActorValueInformation(fk, Release)
                {
                    EditorID = s.Edid,
                    Name = s.Name,
                    Abbreviation = s.Abbr,
                    Type = ActorValueInformation.Types.Variable,
                    DefaultValue = s.Default,
                    Min = s.Min,
                    Max = s.Max,
                    Flags = ParseAvifFlags(s.Flags),
                });
            }
            else if (s.Type == "GLOB")
            {
                var g = new Global(fk, Release)
                {
                    EditorID = s.Edid,
                    Data = EffectiveGlobValue(s, opts),
                };
                if (s.Constant) g.MajorFlags |= Global.MajorFlag.Constant;
                mod.Globals.Add(g);
            }
            else if (s.Type == "MGEF")
            {
                MagicEffect e;
                if (mgefTpl != null)
                {
                    e = (MagicEffect)mgefTpl.Duplicate(fk, new MagicEffect.TranslationMask(defaultOn: true));
                    e.EditorID = s.Edid;
                    e.Name = s.Name;
                    e.Description = s.Desc;
                    e.Archetype = new MagicEffectArchetype(MagicEffectArchetype.TypeEnum.ValueModifier);
                    e.VirtualMachineAdapter = null;
                    e.Conditions.Clear();
                    e.Keywords = null;
                    e.MagicSkill.SetToNull();
                    e.ResistValue.SetToNull();
                    e.SecondActorValue.SetTo(healthKey);
                    e.ThirdActorValue.SetToNull();
                    e.CounterEffects.Clear();
                    e.CastType = CastType.FireAndForget;
                    e.TargetType = TargetType.Self;
                    e.Flags = (e.Flags & ~MagicEffect.Flag.Detrimental) | MagicEffect.Flag.NoDuration | MagicEffect.Flag.HideInUI;
                }
                else
                {
                    e = new MagicEffect(fk, Release)
                    {
                        EditorID = s.Edid,
                        Name = s.Name,
                        Description = s.Desc,
                        Archetype = new MagicEffectArchetype(MagicEffectArchetype.TypeEnum.ValueModifier),
                        CastType = CastType.FireAndForget,
                        TargetType = TargetType.Self,
                        Flags = MagicEffect.Flag.NoDuration | MagicEffect.Flag.NoArea | MagicEffect.Flag.HideInUI,
                    };
                    e.SecondActorValue.SetTo(healthKey);
                }
                mod.MagicEffects.Add(e);
            }
        }

        // Pass 2: FLST and ALCH
        foreach (var s in specs.Where(x => x.Type is "FLST" or "ALCH"))
        {
            var fk = new FormKey(pluginKey, s.Id);
            byEdid[s.Edid] = fk;
            if (s.Type == "FLST")
            {
                var flst = new FormList(fk, Release) { EditorID = s.Edid };
                foreach (var itemEdid in s.Items)
                {
                    if (!byEdid.TryGetValue(itemEdid, out var itemFk))
                        throw new Refusal($"FLST {s.Edid} references unknown item {itemEdid}");
                    flst.Items.Add(new FormLink<IStarfieldMajorRecordGetter>(itemFk));
                }
                mod.FormLists.Add(flst);
            }
            else if (s.Type == "ALCH")
            {
                if (!byEdid.TryGetValue(s.Effect, out var effFk))
                    throw new Refusal($"ALCH {s.Edid} references unknown effect {s.Effect}");
                Ingestible item;
                if (aidTpl != null)
                {
                    item = (Ingestible)aidTpl.Duplicate(fk, new Ingestible.TranslationMask(defaultOn: true));
                    item.EditorID = s.Edid;
                    item.Name = s.Name;
                    item.Description = s.Desc;
                    item.VirtualMachineAdapter = null;
                    item.Keywords = null;
                    item.Addiction.SetToNull();
                    item.AddictionChance = 0f;
                    item.AddictionName = null;
                    item.Flags |= Ingestible.Flag.Medicine;
                    item.MajorFlags |= Ingestible.MajorFlag.Medicine;
                    item.Effects.Clear();
                }
                else
                {
                    item = new Ingestible(fk, Release)
                    {
                        EditorID = s.Edid,
                        Name = s.Name,
                        Description = s.Desc,
                        Weight = 0.1f,
                        Value = 75,
                        Flags = Ingestible.Flag.Medicine,
                        MajorFlags = Ingestible.MajorFlag.Medicine,
                    };
                }
                item.Effects.Add(new Effect
                {
                    BaseEffect = new FormLinkNullable<IMagicEffectGetter>(effFk),
                    Data = new EffectData { Magnitude = 0f, Area = 0, Duration = 0 },
                    MAGF = entryTpl?.MAGF,
                    EFIF = entryTpl?.EFIF,
                    MUID = entryTpl?.MUID,
                });
                if (s.Id == Fo4StimpakId && opts.Fo410mm != 0 && opts.Fo4P5Weapons != 0 && opts.Fo4Arsenal != 0 &&
                    sf.Weapons.ContainsKey(DonorWeapXm2311Key) && sf.Ammunitions.ContainsKey(DonorAmmo45Key) &&
                    HasP5DonorSet(sf) && HasArsenalDonorSet(sf))
                {
                    item.Model = new Model { File = Fo4StimpakModel, LightLayer = 1 };
                    item.Weight = Fo4StimpakWeight;
                    item.Value = Fo4StimpakValue;
                }
                mod.Ingestibles.Add(item);
            }
        }

        // Pass 3 (D7a): Clear Commonwealth Weather & Blue-Sky Atmosphere overrides in FO4SFCoreValues.esm.
        // FO4Core_Commonwealth (WRLD 0x01000803) inherits BIOM 0x002A3777 DesertRockyNoLifeMars -> CLMT 0x00310DB1 ClimateUniqueCydonia
        // and MarsPlanetData (PNDT 0x0003F59A) embeds ATMO 0x0000C9D2 ATMO_Mars. Validate exact source EditorIDs (refusing on
        // mismatch) and copy WeatherSettings directly from ClimateUniqueNewAtlantis (DeepCopy) when present in Starfield.esm
        // and --commonwealth-weather 1 (default), keeping minimal synthetic Fixture() builds byte-identical.
        // Known side effect: Mars-wide override affects all Mars locations (including Cydonia); rollback via --commonwealth-weather 0.
        int clmtOverrides = 0;
        int atmoOverrides = 0;
        if (opts.CommonwealthWeather != 0)
        {
            var sfClimates = sf.Climates.ToDictionary(c => c.FormKey);
            var sfAtmos = sf.Atmospheres.ToDictionary(a => a.FormKey);
            ValidateWeatherSourceEditorIds(sfClimates, sfAtmos);

            if (sfClimates.TryGetValue(ClimateNewAtlantisKey, out var naClmt))
            {
                foreach (var targetKey in new[] { ClimateCydoniaKey, ClimateCydoniaFrozenKey })
                {
                    if (!sfClimates.TryGetValue(targetKey, out var srcClmt))
                        continue;
                    var ov = srcClmt.DeepCopy();
                    ov.Weathers = naClmt.Weathers?.Select(wt => wt.DeepCopy()).ToExtendedList();
                    ov.WeatherSettings = naClmt.WeatherSettings?.Select(ws => ws.DeepCopy()).ToExtendedList();
                    mod.Climates.Add(ov);
                    clmtOverrides++;
                }
            }

            if (sfAtmos.TryGetValue(AtmoMarsKey, out var marsAtmo) && sfAtmos.TryGetValue(AtmoJemisonKey, out var jemAtmo))
            {
                var ovAtmo = (Atmosphere)jemAtmo.Duplicate(AtmoMarsKey);
                ovAtmo.EditorID = marsAtmo.EditorID;
                mod.Atmospheres.Add(ovAtmo);
                atmoOverrides++;
            }
        }

        // Pass 4 (A4.1 — 10mm Pistol ALONE): FO4_Ammo10mm (0x000898) & FO4_10mmPistol (0x000899) when --fo4-10mm 1
        // and Starfield.esm supplies XM2311 (0x24561C) + Ammo45Caliber (0x2B5598). Minimal synthetic Fixture() builds
        // remain byte-identical; --fo4-10mm 0 cleanly omits both records.
        uint effectiveNextId = nextId;
        int fo410mmBuilt = 0;
        bool hasArsenalSet = opts.Fo4Arsenal != 0 && HasArsenalDonorSet(sf);
        if (opts.Fo410mm != 0)
        {
            Validate10mmDonorEditorIds(sf);
            if (sf.Weapons.TryGetValue(DonorWeapXm2311Key, out var xm2311) &&
                sf.Ammunitions.TryGetValue(DonorAmmo45Key, out var ammo45))
            {
                if (nextId > Fo4Ammo10mmId)
                    throw new Refusal($"schema next_form_id 0x{nextId:X} collides with FO4_Ammo10mm 0x{Fo4Ammo10mmId:X}");
                var ammoFk = new FormKey(pluginKey, Fo4Ammo10mmId);
                var ammo = (Ammunition)ammo45.Duplicate(ammoFk);
                ammo.EditorID = Fo4Ammo10mmEdid;
                ammo.Name = "10mm Round";
                ammo.ShortName = "10mm";
                ammo.Value = Fo4Ammo10mmValue;
                ammo.Weight = Fo4Ammo10mmWeight;
                ammo.ObjectBounds = new ObjectBounds
                {
                    First = new P3Float(-0.086f, -0.050f, -0.001f),
                    Second = new P3Float(0.086f, 0.048f, 0.059f),
                };
                ammo.Model = new Model { File = Fo4Ammo10mmModel, LightLayer = 1 };
                mod.Ammunitions.Add(ammo);

                var weapFk = new FormKey(pluginKey, Fo410mmPistolId);
                var weap = (Weapon)xm2311.Duplicate(weapFk);
                weap.EditorID = Fo410mmPistolEdid;
                weap.Name = "10mm Pistol";
                weap.VirtualMachineAdapter = null;
                weap.ObjectBounds = new ObjectBounds
                {
                    First = new P3Float(-0.039f, -0.073f, -0.116f),
                    Second = new P3Float(0.037f, 0.272f, 0.122f),
                };
                weap.Model = new Model { File = Fo410mmPistolModel, LightLayer = 1 };
                weap.FirstPersonModel = new FirstPersonModel { File = Fo410mmPistolModel, LightLayer = 1 };
                weap.AttachParentSlots?.Clear();
                weap.ObjectTemplates?.Clear();
                weap.ObjectTemplates = null;
                weap.InstanceNaming.SetToNull();
                weap.EmbeddedWeaponMod.SetToNull();
                weap.AmmoType.SetTo(ammoFk);
                weap.AmmoList.SetToNull();
                weap.AmmoCapacity = Fo410mmCapacity;
                SetWeaponDamage(weap, Fo410mmBaseDamage, 0);
                weap.AttackDelaySeconds = Fo410mmAttackDelaySec;
                weap.WFIRUnknown7 = Fo410mmAttackDelaySec;
                weap.ShotsPerSecond = 1f / Fo410mmAttackDelaySec;
                weap.MinRange = Fo410mmMinRange;
                weap.MaxRange = Fo410mmMaxRange;
                weap.OutOfRangeDamageMult = 0.5f;
                weap.CritDamageMult = 2.0f;
                weap.BaseWeight = Fo410mmWeight;
                weap.BaseValue = Fo410mmValue;
                weap.ImpactDataSet.SetTo(IpdsBulletKey);
                weap.NonPlayable = false;
                weap.Keywords ??= new ExtendedList<IFormLinkGetter<IKeywordGetter>>();
                StripDonorWeaponKeywords(sf, weap);
                if (!weap.Keywords.Any(k => k.FormKey == AnimGripPistolKwKey))
                    weap.Keywords.Add(AnimGripPistolKwKey);
                if (!weap.Keywords.Any(k => k.FormKey == AnimM1919KwKey))
                    weap.Keywords.Add(AnimM1919KwKey);
                mod.Weapons.Add(weap);

                effectiveNextId = Fo410mmPistolId + 1;
                fo410mmBuilt = 1;

                // Pass 4b (Step 4 P5 + F2/F5): Baton (0x89A), Fusion Cells (0x89B/0x89C), Laser Muskets (0x89D/0x89E), 5mm (0x89F), Minigun (0x8A0)
                if (opts.Fo4P5Weapons != 0 && HasP5DonorSet(sf))
                {
                    var rescueAxe = sf.Weapons[DonorWeapRescueAxeKey];
                    var ammoLaser = sf.Ammunitions[DonorAmmoLaserKey];
                    var orion = sf.Weapons[DonorWeapOrionKey];
                    var ammo777 = sf.Ammunitions[DonorAmmo777Key];
                    var microgun = sf.Weapons[DonorWeapMicrogunKey];

                    // 0x00089A FO4_Baton (WEAP, "Baton", 11 phys dmg [0008C14D], WVIS 0x055DC3, donor RescueAxe 0x04F760)
                    var batonFk = new FormKey(pluginKey, Fo4WeapBatonId);
                    var baton = (Weapon)rescueAxe.Duplicate(batonFk);
                    baton.EditorID = Fo4WeapBatonEdid;
                    baton.Name = "Baton";
                    baton.VirtualMachineAdapter = null;
                    baton.ObjectBounds = new ObjectBounds
                    {
                        First = new P3Float(-0.020f, -0.020f, -0.102f),
                        Second = new P3Float(0.020f, 0.028f, 0.519f),
                    };
                    baton.Model = new Model { File = Fo4WeapBatonModel, LightLayer = 1 };
                    baton.FirstPersonModel = new FirstPersonModel { File = Fo4WeapBatonModel, LightLayer = 1 };
                    baton.AttachParentSlots?.Clear();
                    baton.ObjectTemplates?.Clear();
                    baton.ObjectTemplates = null;
                    baton.InstanceNaming.SetToNull();
                    baton.EmbeddedWeaponMod.SetToNull();
                    baton.AmmoType.SetToNull();
                    baton.AmmoList.SetToNull();
                    baton.AmmoCapacity = 0;
                    SetWeaponDamage(baton, Fo4BatonBaseDamage, 0);
                    baton.BaseWeight = Fo4BatonWeight;
                    baton.BaseValue = Fo4BatonValue;
                    baton.ImpactDataSet.SetTo(IpdsMeleeBashSmallKey); // P6-H2: blunt bash impact set 000116F1
                    baton.NonPlayable = false;
                    baton.MajorFlags &= ~Weapon.MajorFlag.NonPlayable;
                    baton.Keywords ??= new ExtendedList<IFormLinkGetter<IKeywordGetter>>();
                    StripDonorWeaponKeywords(sf, baton);
                    if (!baton.Keywords.Any(k => k.FormKey == AnimOneHandedKwKey))
                        baton.Keywords.Add(AnimOneHandedKwKey);
                    mod.Weapons.Add(baton);

                    // 0x00089B FO4_AmmoFusionCell (AMMO, "Fusion Cell", wt 0.029 [000C1897], val 3)
                    var fcFk = new FormKey(pluginKey, Fo4AmmoFusionCellId);
                    var fc = (Ammunition)ammoLaser.Duplicate(fcFk);
                    fc.EditorID = Fo4AmmoFusionCellEdid;
                    fc.Name = "Fusion Cell";
                    fc.ShortName = "Cell";
                    fc.Value = Fo4AmmoFusionCellValue;
                    fc.Weight = Fo4AmmoFusionCellWeight;
                    fc.ObjectBounds = new ObjectBounds
                    {
                        First = new P3Float(-0.026f, -0.026f, 0.0f),
                        Second = new P3Float(0.026f, 0.026f, 0.082f),
                    };
                    fc.Model = new Model { File = Fo4AmmoFusionCellModel, LightLayer = 1 };
                    fc.Flags &= ~Ammunition.Flag.NonPlayable;
                    fc.MajorFlags &= ~Ammunition.MajorFlag.NonPlayable;
                    mod.Ammunitions.Add(fc);

                    // 0x00089C FO4_CompanionAmmoFusionCell (AMMO, non-playable, wt 0, val 3 [00245D69])
                    var compFcFk = new FormKey(pluginKey, Fo4AmmoCompFusionCellId);
                    var compFc = (Ammunition)ammoLaser.Duplicate(compFcFk);
                    compFc.EditorID = Fo4AmmoCompFusionCellEdid;
                    compFc.Name = "Companion Fusion Cell";
                    compFc.ShortName = "Cell";
                    compFc.Value = Fo4AmmoCompFusionCellValue;
                    compFc.Weight = 0f;
                    compFc.ObjectBounds = new ObjectBounds
                    {
                        First = new P3Float(-0.026f, -0.026f, 0.0f),
                        Second = new P3Float(0.026f, 0.026f, 0.082f),
                    };
                    compFc.Model = new Model { File = Fo4AmmoFusionCellModel, LightLayer = 1 };
                    compFc.Flags |= Ammunition.Flag.NonPlayable;
                    compFc.MajorFlags |= Ammunition.MajorFlag.NonPlayable;
                    mod.Ammunitions.Add(compFc);

                    Weapon MakeLaserMusket(FormKey fk, string edid, string name, ushort energyDmg, FormKey ammoKey, float wt, uint val, bool nonPlayable)
                    {
                        var lm = (Weapon)orion.Duplicate(fk);
                        lm.EditorID = edid;
                        lm.Name = name;
                        lm.VirtualMachineAdapter = null;
                        lm.ObjectBounds = new ObjectBounds
                        {
                            First = new P3Float(-0.143f, -0.136f, -0.083f),
                            Second = new P3Float(0.069f, 0.936f, 0.196f),
                        };
                        lm.Model = new Model { File = Fo4WeapLaserMusketModel, LightLayer = 1 };
                        lm.FirstPersonModel = new FirstPersonModel { File = Fo4WeapLaserMusketModel, LightLayer = 1 };
                        lm.AttachParentSlots?.Clear();
                        lm.ObjectTemplates?.Clear();
                        lm.ObjectTemplates = null;
                        lm.InstanceNaming.SetToNull();
                        lm.EmbeddedWeaponMod.SetToNull();
                        lm.AmmoType.SetTo(ammoKey);
                        lm.AmmoList.SetToNull();
                        lm.AmmoCapacity = Fo4LaserMusketCapacity;
                        SetWeaponEnergyDamage(lm, energyDmg);
                        lm.AttackDelaySeconds = Fo4LaserMusketAttackDelaySec;
                        lm.WFIRUnknown7 = Fo4LaserMusketAttackDelaySec;
                        lm.ShotsPerSecond = 1f / Fo4LaserMusketAttackDelaySec;
                        lm.MinRange = Fo4LaserMusketMinRange;
                        lm.MaxRange = Fo4LaserMusketMaxRange;
                        lm.BaseWeight = wt;
                        lm.BaseValue = val;
                        lm.ImpactDataSet.SetTo(IpdsOrionLaserKey);
                        lm.CriticalHitSpell.SetTo(hasArsenalSet ? new FormKey(pluginKey, Fo4SpelCritLaserId) : SfSpelCritLaserDisintKey);
                        lm.CritEffectOnDeathOnly = true;
                        lm.NonPlayable = nonPlayable;
                        if (nonPlayable)
                            lm.MajorFlags |= Weapon.MajorFlag.NonPlayable;
                        else
                            lm.MajorFlags &= ~Weapon.MajorFlag.NonPlayable;
                        lm.Keywords ??= new ExtendedList<IFormLinkGetter<IKeywordGetter>>();
                        StripDonorWeaponKeywords(sf, lm, keepTeammateDontUseAmmo: nonPlayable);
                        if (!lm.Keywords.Any(k => k.FormKey == AnimGripExtendedLowKwKey))
                            lm.Keywords.Add(AnimGripExtendedLowKwKey);
                        if (!lm.Keywords.Any(k => k.FormKey == AnimOrionKwKey))
                            lm.Keywords.Add(AnimOrionKwKey);
                        return lm;
                    }

                    // 0x00089D FO4_LaserMusket & 0x00089E FO4_CompPrestonLaserMusket
                    mod.Weapons.Add(MakeLaserMusket(new FormKey(pluginKey, Fo4WeapLaserMusketId), Fo4WeapLaserMusketEdid, "Laser Musket", Fo4LaserMusketEnergyDamage, fcFk, Fo4LaserMusketWeight, Fo4LaserMusketValue, nonPlayable: false));
                    mod.Weapons.Add(MakeLaserMusket(new FormKey(pluginKey, Fo4WeapCompPrestonLaserMusketId), Fo4WeapCompPrestonLaserMusketEdid, "Preston's Laser Musket", Fo4PrestonLaserMusketEnergyDamage, compFcFk, Fo4PrestonLaserMusketWeight, Fo4PrestonLaserMusketValue, nonPlayable: true));

                    // 0x00089F FO4_Ammo5mm (AMMO, "5mm Round", wt 0.009 [0001F66C], val 1, donor Ammo777mm 0x04AD3E)
                    var a5Fk = new FormKey(pluginKey, Fo4Ammo5mmId);
                    var a5 = (Ammunition)ammo777.Duplicate(a5Fk);
                    a5.EditorID = Fo4Ammo5mmEdid;
                    a5.Name = "5mm Round";
                    a5.ShortName = "5mm";
                    a5.Value = Fo4Ammo5mmValue;
                    a5.Weight = Fo4Ammo5mmWeight;
                    a5.ObjectBounds = new ObjectBounds
                    {
                        First = new P3Float(-0.055f, -0.143f, 0.0f),
                        Second = new P3Float(0.055f, 0.136f, 0.195f),
                    };
                    a5.Model = new Model { File = Fo4Ammo5mmModel, LightLayer = 1 };
                    a5.Flags &= ~Ammunition.Flag.NonPlayable;
                    a5.MajorFlags &= ~Ammunition.MajorFlag.NonPlayable;
                    mod.Ammunitions.Add(a5);

                    // 0x0008A0 FO4_Minigun (WEAP, "Minigun", 8 phys dmg, 500 cap, wt 27.45, val 383, Microgun fire-rate stand-in, WVIS 0x00D02C)
                    var mgFk = new FormKey(pluginKey, Fo4WeapMinigunId);
                    var mg = (Weapon)microgun.Duplicate(mgFk);
                    mg.EditorID = Fo4WeapMinigunEdid;
                    mg.Name = "Minigun";
                    mg.VirtualMachineAdapter = null;
                    mg.ObjectBounds = new ObjectBounds
                    {
                        First = new P3Float(-0.330f, -0.110f, -0.538f),
                        Second = new P3Float(0.133f, 1.211f, 0.166f),
                    };
                    mg.Model = new Model { File = Fo4WeapMinigunModel, LightLayer = 1 };
                    mg.FirstPersonModel = new FirstPersonModel { File = Fo4WeapMinigunModel, LightLayer = 1 };
                    mg.AttachParentSlots?.Clear();
                    mg.ObjectTemplates?.Clear();
                    mg.ObjectTemplates = null;
                    mg.InstanceNaming.SetToNull();
                    mg.EmbeddedWeaponMod.SetToNull();
                    mg.AmmoType.SetTo(a5Fk);
                    mg.AmmoList.SetToNull();
                    mg.AmmoCapacity = Fo4MinigunCapacity;
                    SetWeaponDamage(mg, Fo4MinigunBaseDamage, 0);
                    mg.BaseWeight = Fo4MinigunWeight;
                    mg.BaseValue = Fo4MinigunValue;
                    mg.ImpactDataSet.SetTo(IpdsBulletKey);
                    mg.NonPlayable = false;
                    mg.MajorFlags &= ~Weapon.MajorFlag.NonPlayable;
                    mg.Keywords ??= new ExtendedList<IFormLinkGetter<IKeywordGetter>>();
                    StripDonorWeaponKeywords(sf, mg);
                    if (!mg.Keywords.Any(k => k.FormKey == AnimGripHeavyKwKey))
                        mg.Keywords.Add(AnimGripHeavyKwKey);
                    if (!mg.Keywords.Any(k => k.FormKey == AnimMicrogunKwKey))
                        mg.Keywords.Add(AnimMicrogunKwKey);
                    mod.Weapons.Add(mg);

                    effectiveNextId = Fo4WeapMinigunId + 1;

                    // Pass 4c: Row 5 Pipe Pistol/Rifle/.38 (0x8A1..0x8A3), Caps/BobbyPin (0x8A4..0x8A5), and Rows 6-20 Arsenal (0x8B0..0x8D6)
                    if (hasArsenalSet)
                    {
                        // Core MiscItems: 0x0008A4 FO4_Caps & 0x0008A5 FO4_BobbyPin
                        var capsMisc = (MiscItem)sf.MiscItems[SfMiscCreditsKey].Duplicate(new FormKey(pluginKey, Fo4MiscCapsId));
                        capsMisc.EditorID = "FO4_Caps";
                        capsMisc.Name = "Bottlecap";
                        capsMisc.ShortName = null;
                        capsMisc.Value = 1;
                        capsMisc.Weight = 0f;
                        capsMisc.VirtualMachineAdapter = null;
                        capsMisc.Model = new Model { File = @"fo4core\props\bottlecapsingle.nif", LightLayer = 1 };
                        capsMisc.ObjectBounds = new ObjectBounds { First = new P3Float(-0.025f, -0.025f, 0f), Second = new P3Float(0.025f, 0.025f, 0.005f) };
                        mod.MiscItems.Add(capsMisc);

                        var bpMisc = (MiscItem)sf.MiscItems[SfMiscDigipickKey].Duplicate(new FormKey(pluginKey, Fo4MiscBobbyPinId));
                        bpMisc.EditorID = "FO4_BobbyPin";
                        bpMisc.Name = "Bobby Pin";
                        bpMisc.ShortName = null;
                        bpMisc.Value = 1;
                        bpMisc.Weight = 0f;
                        bpMisc.VirtualMachineAdapter = null;
                        bpMisc.Model = new Model { File = @"fo4core\props\bobbypin.nif", LightLayer = 1 };
                        bpMisc.ObjectBounds = new ObjectBounds { First = new P3Float(-0.010f, -0.036f, 0f), Second = new P3Float(0.010f, 0.059f, 0.007f) };
                        mod.MiscItems.Add(bpMisc);

                        foreach (var es in ArsenalExplSpecs)
                        {
                            var expl = (Explosion)sf.Explosions[es.Donor].Duplicate(new FormKey(pluginKey, es.Id));
                            expl.EditorID = es.Edid;
                            expl.Damage = es.Dmg;
                            expl.Force = es.Force;
                            expl.InnerRadius = es.InnerM;
                            expl.OuterRadius = es.OuterM;
                            expl.ISRadius = es.IsM;
                            expl.ImpactDataSet.SetTo(es.IpdsKey);
                            mod.Explosions.Add(expl);
                        }

                        foreach (var ps in ArsenalProjSpecs)
                        {
                            var proj = (Projectile)sf.Projectiles[ps.Donor].Duplicate(new FormKey(pluginKey, ps.Id));
                            proj.EditorID = ps.Edid;
                            proj.Name = null;
                            proj.Model = new Model { File = ps.Model, LightLayer = 1 };
                            proj.Explosion.SetTo(new FormKey(pluginKey, ps.ExplId));
                            if (ps.SpeedOpt.HasValue) proj.Speed = ps.SpeedOpt.Value;
                            if (ps.GravityOpt.HasValue) proj.Gravity = ps.GravityOpt.Value;
                            mod.Projectiles.Add(proj);
                        }

                        foreach (var aSpec in ArsenalAmmoSpecs)
                        {
                            var am = (Ammunition)sf.Ammunitions[aSpec.Donor].Duplicate(new FormKey(pluginKey, aSpec.Id));
                            am.EditorID = aSpec.Edid;
                            am.Name = aSpec.Name;
                            am.ShortName = aSpec.Short;
                            am.Value = aSpec.Val;
                            am.Weight = aSpec.Wt;
                            am.Model = new Model { File = aSpec.Model, LightLayer = 1 };
                            am.Flags &= ~Ammunition.Flag.NonPlayable;
                            am.MajorFlags &= ~Ammunition.MajorFlag.NonPlayable;
                            if (aSpec.ProjId != 0) am.Projectile.SetTo(new FormKey(pluginKey, aSpec.ProjId));
                            mod.Ammunitions.Add(am);
                        }

                        // Laser Ash (FO4_CritLaser 0x8C4) & Plasma Goo (FO4_GooPile01 0x8C1, FO4_CritPlasmaEffect 0x8C2, FO4_CritPlasma 0x8C3)
                        var gooFk = new FormKey(pluginKey, Fo4ActiGooPileId);
                        var goo = (Mutagen.Bethesda.Starfield.Activator)sf.Activators[SfActiAshPile01Key].Duplicate(gooFk);
                        goo.EditorID = "FO4_GooPile01";
                        goo.Name = "Goo Pile";
                        goo.Model = new Model { File = @"fo4core\effects\ashpileplasmagoo.nif", LightLayer = 1 };
                        goo.ObjectBounds = new ObjectBounds { First = new P3Float(-1.021f, -1.021f, 0f), Second = new P3Float(1.021f, 0.980f, 0.222f) };
                        mod.Activators.Add(goo);

                        var cpMgefFk = new FormKey(pluginKey, Fo4MgefCritPlasmaId);
                        var cpMgef = (MagicEffect)sf.MagicEffects[SfMgefCritLaserEffectKey].Duplicate(cpMgefFk);
                        cpMgef.EditorID = "FO4_CritPlasmaEffect";
                        cpMgef.Name = "Plasma Disintegration Effect";
                        if (cpMgef.VirtualMachineAdapter != null)
                        {
                            foreach (var scr in cpMgef.VirtualMachineAdapter.Scripts)
                            {
                                foreach (var prop in scr.Properties)
                                {
                                    if (prop is ScriptObjectProperty sop && string.Equals(sop.Name, "AshPileObject", StringComparison.OrdinalIgnoreCase))
                                        sop.Object.SetTo(gooFk);
                                }
                            }
                        }
                        mod.MagicEffects.Add(cpMgef);

                        var cpSpel = (Spell)sf.Spells[SfSpelCritLaserDisintKey].Duplicate(new FormKey(pluginKey, Fo4SpelCritPlasmaId));
                        cpSpel.EditorID = "FO4_CritPlasma";
                        cpSpel.Name = "Crit Plasma";
                        if (cpSpel.Effects.Count > 0)
                        {
                            cpSpel.Effects[0].BaseEffect.SetTo(cpMgefFk);
                            cpSpel.Effects[0].Data ??= new EffectData();
                            cpSpel.Effects[0].Data!.Magnitude = 10f;
                            cpSpel.Effects[0].Data!.Area = 0;
                            cpSpel.Effects[0].Data!.Duration = 10;
                        }
                        mod.Spells.Add(cpSpel);

                        var clSpel = (Spell)sf.Spells[SfSpelCritLaserDisintKey].Duplicate(new FormKey(pluginKey, Fo4SpelCritLaserId));
                        clSpel.EditorID = "FO4_CritLaser";
                        clSpel.Name = "Crit Laser";
                        if (clSpel.Effects.Count > 0)
                        {
                            clSpel.Effects[0].BaseEffect.SetTo(SfMgefCritLaserEffectKey);
                            clSpel.Effects[0].Data ??= new EffectData();
                            clSpel.Effects[0].Data!.Magnitude = 10f;
                            clSpel.Effects[0].Data!.Area = 0;
                            clSpel.Effects[0].Data!.Duration = 10;
                        }
                        mod.Spells.Add(clSpel);

                        foreach (var ws in ArsenalWeapSpecs)
                        {
                            var wfk = new FormKey(pluginKey, ws.Id);
                            var w = (Weapon)sf.Weapons[ws.Donor].Duplicate(wfk);
                            w.EditorID = ws.Edid;
                            w.Name = ws.Name;
                            w.VirtualMachineAdapter = null;
                            if (ws.Model != null)
                            {
                                w.Model = new Model { File = ws.Model, LightLayer = 1 };
                                w.FirstPersonModel = new FirstPersonModel { File = ws.Model, LightLayer = 1 };
                            }
                            else
                            {
                                w.Model = null;
                                w.FirstPersonModel = null;
                            }
                            w.AttachParentSlots?.Clear();
                            w.ObjectTemplates?.Clear();
                            w.ObjectTemplates = null;
                            w.InstanceNaming.SetToNull();
                            w.EmbeddedWeaponMod.SetToNull();
                            if (ws.AmmoId != 0) w.AmmoType.SetTo(new FormKey(pluginKey, ws.AmmoId));
                            else w.AmmoType.SetToNull();
                            w.AmmoList.SetToNull();
                            w.AmmoCapacity = ws.Cap;
                            SetWeaponDamage(w, ws.PhysDmg, ws.EnergyDmg);
                            if (ws.DelaySec > 0f)
                            {
                                w.AttackDelaySeconds = ws.DelaySec;
                                w.WFIRUnknown7 = ws.DelaySec;
                                w.ShotsPerSecond = 1f / ws.DelaySec;
                            }
                            if (ws.SpeedOpt.HasValue) w.BaseSpeed = ws.SpeedOpt.Value;
                            if (ws.ReachOpt.HasValue) w.MeleeReach = ws.ReachOpt.Value;
                            w.BaseWeight = ws.Wt;
                            w.BaseValue = ws.Val;
                            w.ImpactDataSet.SetTo(ws.IpdsKey);
                            if (ws.CritSpellId != 0)
                            {
                                w.CriticalHitSpell.SetTo(new FormKey(pluginKey, ws.CritSpellId));
                                w.CritEffectOnDeathOnly = true;
                            }
                            if (ws.OverrideProjId != 0) w.OverrideProjectile.SetTo(new FormKey(pluginKey, ws.OverrideProjId));
                            w.NonPlayable = ws.NonPlayable;
                            if (ws.NonPlayable) w.MajorFlags |= Weapon.MajorFlag.NonPlayable;
                            else w.MajorFlags &= ~Weapon.MajorFlag.NonPlayable;
                            w.Keywords ??= new ExtendedList<IFormLinkGetter<IKeywordGetter>>();
                            StripDonorWeaponKeywords(sf, w, keepTeammateDontUseAmmo: ws.NonPlayable);
                            mod.Weapons.Add(w);
                        }

                        effectiveNextId = Fo4WeapGaussRifleId + 1;
                    }
                }
            }
        }

        mod.ModHeader.Stats.NextFormID = effectiveNextId;
        if (!mod.ModHeader.MasterReferences.Any(m => m.Master == SfEsm))
            mod.ModHeader.MasterReferences.Add(new MasterReference { Master = SfEsm });

        WriteMod(mod, pluginKey, outDir);
        var outPath = Path.Combine(outDir, pluginKey.FileName);
        Console.WriteLine($"wrote {outPath} ({new FileInfo(outPath).Length:N0} bytes): " +
                          $"{mod.ActorValueInformation.Count} AVIF, {mod.Globals.Count} GLOB, " +
                          $"{mod.FormLists.Count} FLST, {mod.MagicEffects.Count} MGEF, {mod.Ingestibles.Count} ALCH" +
                          (clmtOverrides > 0 || atmoOverrides > 0 ? $", {clmtOverrides} CLMT, {atmoOverrides} ATMO" : "") +
                          (fo410mmBuilt > 0 ? $", {mod.Ammunitions.Count} AMMO, {mod.Weapons.Count} WEAP" : ""));
        return 0;
    }

    public static int Check(string pluginPath, string sfPath, BuildOptions opts)
    {
        var (pluginKey, nextId, specs) = LoadSchema(opts.JsonPath);
        if (!File.Exists(pluginPath)) throw new Refusal($"missing plugin: {pluginPath}");
        using var sf = OpenMod(sfPath);
        using var plug = OpenMod(pluginPath);

        var problems = new List<string>();
        void Need(bool ok, string why) { if (!ok) problems.Add(why); }

        Need(plug.ModKey == pluginKey, $"ModKey {plug.ModKey} != {pluginKey}");
        Need(plug.ModHeader.Flags.HasFlag(StarfieldModHeader.HeaderFlag.Master), "missing Master flag");
        var masters = plug.ModHeader.MasterReferences.Select(m => m.Master.FileName.String).ToList();
        Need(masters.SequenceEqual(new[] { "Starfield.esm" }), $"masters [{string.Join(", ", masters)}] != [Starfield.esm]");

        if (opts.Fo410mm != 0)
            Validate10mmDonorEditorIds(sf);
        int expect10mm = (opts.Fo410mm != 0 &&
                          sf.Weapons.ContainsKey(DonorWeapXm2311Key) &&
                          sf.Ammunitions.ContainsKey(DonorAmmo45Key)) ? 1 : 0;
        int expectP5 = (expect10mm == 1 && opts.Fo4P5Weapons != 0 && HasP5DonorSet(sf)) ? 1 : 0;
        int expectArsenal = (expectP5 == 1 && opts.Fo4Arsenal != 0 && HasArsenalDonorSet(sf)) ? 1 : 0;
        int wantAmmoCount = expect10mm + (expectP5 == 1 ? 3 : 0) + (expectArsenal == 1 ? ArsenalAmmoSpecs.Length : 0);
        int wantWeapCount = expect10mm + (expectP5 == 1 ? 4 : 0) + (expectArsenal == 1 ? ArsenalWeapSpecs.Length : 0);
        uint wantNextId = expectArsenal == 1
            ? Fo4WeapGaussRifleId + 1
            : (expectP5 == 1 ? Fo4WeapMinigunId + 1 : (expect10mm == 1 ? Fo410mmPistolId + 1 : nextId));
        Need(plug.ModHeader.Stats.NextFormID == wantNextId, $"NextFormID 0x{plug.ModHeader.Stats.NextFormID:X} != 0x{wantNextId:X}");

        var sfClimates = sf.Climates.ToDictionary(c => c.FormKey);
        var sfAtmos = sf.Atmospheres.ToDictionary(a => a.FormKey);
        if (opts.CommonwealthWeather != 0)
            ValidateWeatherSourceEditorIds(sfClimates, sfAtmos);

        int expectClmt = (opts.CommonwealthWeather != 0 && sfClimates.ContainsKey(ClimateNewAtlantisKey))
            ? (sfClimates.ContainsKey(ClimateCydoniaKey) ? 1 : 0) + (sfClimates.ContainsKey(ClimateCydoniaFrozenKey) ? 1 : 0)
            : 0;
        int expectAtmo = (opts.CommonwealthWeather != 0 && sfAtmos.ContainsKey(AtmoMarsKey) && sfAtmos.ContainsKey(AtmoJemisonKey)) ? 1 : 0;

        Need(plug.EnumerateMajorRecords().All(r =>
            r.FormKey.ModKey == pluginKey ||
            (opts.CommonwealthWeather != 0 && AllowedWeatherOverrideKeys.Contains(r.FormKey))),
            "contains unexpected foreign record override");

        Need(plug.Climates.Count == expectClmt, $"CLMT override count {plug.Climates.Count} != {expectClmt}");
        Need(plug.Atmospheres.Count == expectAtmo, $"ATMO override count {plug.Atmospheres.Count} != {expectAtmo}");
        if (expectClmt > 0 && sfClimates.TryGetValue(ClimateNewAtlantisKey, out var wantNaClmt))
        {
            var wantWslt = wantNaClmt.WeatherSettings?.Select(w => (w.Settings.FormKey, w.Chance)).ToList() ?? new();
            foreach (var clmt in plug.Climates)
            {
                var wantEdid = clmt.FormKey == ClimateCydoniaKey ? ExpectedClimateCydoniaEdid : ExpectedClimateCydoniaFrozenEdid;
                var gotWslt = clmt.WeatherSettings?.Select(w => (w.Settings.FormKey, w.Chance)).ToList() ?? new();
                Need(string.Equals(clmt.EditorID, wantEdid, StringComparison.Ordinal) && gotWslt.SequenceEqual(wantWslt),
                     $"CLMT {clmt.FormKey} ({clmt.EditorID}) does not match copied ClimateUniqueNewAtlantis WeatherSettings");
            }
        }
        if (expectAtmo == 1)
        {
            var ovAtmo = plug.Atmospheres.FirstOrDefault(a => a.FormKey == AtmoMarsKey);
            Need(ovAtmo != null && string.Equals(ovAtmo.EditorID, ExpectedAtmoMarsEdid, StringComparison.Ordinal),
                 "ATMO_Mars (0x0000C9D2) override mismatch");
        }

        foreach (var s in specs)
        {
            var fk = new FormKey(pluginKey, s.Id);
            if (s.Type == "AVIF")
            {
                var r = plug.ActorValueInformation.FirstOrDefault(x => x.FormKey == fk);
                Need(r != null && r.EditorID == s.Edid && r.Type == ActorValueInformation.Types.Variable &&
                     r.DefaultValue.HasValue && MathF.Abs(r.DefaultValue.Value - s.Default) < 1e-4f &&
                     r.Min.HasValue && MathF.Abs(r.Min.Value - s.Min) < 1e-4f &&
                     r.Max.HasValue && MathF.Abs(r.Max.Value - s.Max) < 1e-4f && r.Flags == ParseAvifFlags(s.Flags),
                     $"AVIF 0x{s.Id:X} {s.Edid} mismatch");
            }
            else if (s.Type == "GLOB")
            {
                var r = plug.Globals.FirstOrDefault(x => x.FormKey == fk);
                float want = EffectiveGlobValue(s, opts);
                Need(r != null && r.EditorID == s.Edid && r.Data.HasValue && MathF.Abs(r.Data.Value - want) < 1e-4f &&
                     r.MajorFlags.HasFlag(Global.MajorFlag.Constant) == s.Constant,
                     $"GLOB 0x{s.Id:X} {s.Edid} mismatch (want {want}, constant={s.Constant})");
            }
            else if (s.Type == "FLST")
            {
                var r = plug.FormLists.FirstOrDefault(x => x.FormKey == fk);
                var wantIds = s.Items.Select(ed => specs.First(x => x.Edid == ed).Id).ToList();
                var gotIds = r?.Items.Select(i => i.FormKey.ID).ToList() ?? new List<uint>();
                Need(r != null && r.EditorID == s.Edid && gotIds.SequenceEqual(wantIds),
                     $"FLST 0x{s.Id:X} {s.Edid} mismatch");
            }
            else if (s.Type == "MGEF")
            {
                var r = plug.MagicEffects.FirstOrDefault(x => x.FormKey == fk);
                Need(r != null && r.EditorID == s.Edid, $"MGEF 0x{s.Id:X} {s.Edid} mismatch");
            }
            else if (s.Type == "ALCH")
            {
                var r = plug.Ingestibles.FirstOrDefault(x => x.FormKey == fk);
                var effId = specs.First(x => x.Edid == s.Effect).Id;
                Need(r != null && r.EditorID == s.Edid && r.Flags.HasFlag(Ingestible.Flag.Medicine) &&
                     r.Effects.Count == 1 && r.Effects[0].BaseEffect.FormKey == new FormKey(pluginKey, effId) &&
                     (s.Id != Fo4StimpakId || expectArsenal == 0 || (MathF.Abs(r.Weight - Fo4StimpakWeight) < 1e-4f && r.Value == Fo4StimpakValue &&
                      string.Equals(NormModelPath(r.Model?.File?.GivenPath), Fo4StimpakModel, StringComparison.OrdinalIgnoreCase))),
                     $"ALCH 0x{s.Id:X} {s.Edid} mismatch");
            }
        }

        Need(plug.ActorValueInformation.Count == specs.Count(x => x.Type == "AVIF"), "unexpected AVIF count");
        Need(plug.Globals.Count == specs.Count(x => x.Type == "GLOB"), "unexpected GLOB count");
        Need(plug.FormLists.Count == specs.Count(x => x.Type == "FLST"), "unexpected FLST count");
        Need(plug.MagicEffects.Count == specs.Count(x => x.Type == "MGEF") + expectArsenal, "unexpected MGEF count");
        Need(plug.Ingestibles.Count == specs.Count(x => x.Type == "ALCH"), "unexpected ALCH count");
        Need(plug.MiscItems.Count == expectArsenal * 2, $"MISC count {plug.MiscItems.Count} != {expectArsenal * 2}");
        Need(plug.Explosions.Count == expectArsenal * ArsenalExplSpecs.Length, $"EXPL count {plug.Explosions.Count} != {expectArsenal * ArsenalExplSpecs.Length}");
        Need(plug.Projectiles.Count == expectArsenal * ArsenalProjSpecs.Length, $"PROJ count {plug.Projectiles.Count} != {expectArsenal * ArsenalProjSpecs.Length}");
        Need(plug.Activators.Count == expectArsenal, $"ACTI count {plug.Activators.Count} != {expectArsenal}");
        Need(plug.Spells.Count == expectArsenal * 2, $"SPEL count {plug.Spells.Count} != {expectArsenal * 2}");
        Need(plug.Ammunitions.Count == wantAmmoCount, $"AMMO count {plug.Ammunitions.Count} != {wantAmmoCount}");
        Need(plug.Weapons.Count == wantWeapCount, $"WEAP count {plug.Weapons.Count} != {wantWeapCount}");
        if (expect10mm == 1)
        {
            var ammoFk = new FormKey(pluginKey, Fo4Ammo10mmId);
            var weapFk = new FormKey(pluginKey, Fo410mmPistolId);
            var ammo = plug.Ammunitions.FirstOrDefault(a => a.FormKey == ammoFk);
            Need(ammo != null &&
                 string.Equals(ammo.EditorID, Fo4Ammo10mmEdid, StringComparison.Ordinal) &&
                 ammo.Name?.String == "10mm Round" &&
                 ammo.Value == Fo4Ammo10mmValue &&
                 MathF.Abs(ammo.Weight - Fo4Ammo10mmWeight) < 1e-4f &&
                 string.Equals(NormModelPath(ammo.Model?.File?.GivenPath), Fo4Ammo10mmModel, StringComparison.OrdinalIgnoreCase),
                 $"AMMO 0x{Fo4Ammo10mmId:X} ({Fo4Ammo10mmEdid}) mismatch");

            var weap = plug.Weapons.FirstOrDefault(w => w.FormKey == weapFk);
            Need(weap != null &&
                 string.Equals(weap.EditorID, Fo410mmPistolEdid, StringComparison.Ordinal) &&
                 weap.Name?.String == "10mm Pistol" &&
                 MathF.Abs(weap.AttackDamage - Fo410mmBaseDamage) < 1e-4f &&
                 weap.AmmoCapacity == Fo410mmCapacity &&
                 MathF.Abs(weap.AttackDelaySeconds - Fo410mmAttackDelaySec) < 1e-4f &&
                 MathF.Abs(weap.BaseWeight - Fo410mmWeight) < 1e-4f &&
                 weap.BaseValue == Fo410mmValue &&
                 weap.AmmoType.FormKey == ammoFk &&
                 weap.ImpactDataSet.FormKey == IpdsBulletKey &&
                 !weap.NonPlayable &&
                 (weap.AttachParentSlots?.Count ?? 0) == 0 &&
                 (weap.ObjectTemplates?.Count ?? 0) == 0 &&
                 string.Equals(NormModelPath(weap.Model?.File?.GivenPath), Fo410mmPistolModel, StringComparison.OrdinalIgnoreCase) &&
                 string.Equals(NormModelPath(weap.FirstPersonModel?.File?.GivenPath), Fo410mmPistolModel, StringComparison.OrdinalIgnoreCase) &&
                 (weap.Keywords?.Any(k => k.FormKey == AnimGripPistolKwKey) ?? false) &&
                 (weap.Keywords?.Any(k => k.FormKey == AnimM1919KwKey) ?? false) &&
                 !(weap.Keywords?.Any(k => k.FormKey == ModAssocXm2311KwKey) ?? false),
                 $"WEAP 0x{Fo410mmPistolId:X} ({Fo410mmPistolEdid}) mismatch");
        }
        if (expectP5 == 1)
        {
            var batonFk = new FormKey(pluginKey, Fo4WeapBatonId);
            var fcFk = new FormKey(pluginKey, Fo4AmmoFusionCellId);
            var compFcFk = new FormKey(pluginKey, Fo4AmmoCompFusionCellId);
            var lmFk = new FormKey(pluginKey, Fo4WeapLaserMusketId);
            var compLmFk = new FormKey(pluginKey, Fo4WeapCompPrestonLaserMusketId);
            var a5Fk = new FormKey(pluginKey, Fo4Ammo5mmId);
            var mgFk = new FormKey(pluginKey, Fo4WeapMinigunId);
            var wantCritLaserFk = expectArsenal == 1 ? new FormKey(pluginKey, Fo4SpelCritLaserId) : SfSpelCritLaserDisintKey;

            var baton = plug.Weapons.FirstOrDefault(w => w.FormKey == batonFk);
            Need(baton != null &&
                 string.Equals(baton.EditorID, Fo4WeapBatonEdid, StringComparison.Ordinal) &&
                 baton.Name?.String == "Baton" &&
                 MathF.Abs(baton.AttackDamage - Fo4BatonBaseDamage) < 1e-4f &&
                 MathF.Abs(baton.BaseWeight - Fo4BatonWeight) < 1e-4f &&
                 baton.BaseValue == Fo4BatonValue &&
                 baton.ImpactDataSet.FormKey == IpdsMeleeBashSmallKey &&
                 baton.AmmoCapacity == 0 &&
                 !baton.NonPlayable &&
                 (baton.AttachParentSlots?.Count ?? 0) == 0 &&
                 (baton.ObjectTemplates?.Count ?? 0) == 0 &&
                 string.Equals(NormModelPath(baton.Model?.File?.GivenPath), Fo4WeapBatonModel, StringComparison.OrdinalIgnoreCase) &&
                 string.Equals(NormModelPath(baton.FirstPersonModel?.File?.GivenPath), Fo4WeapBatonModel, StringComparison.OrdinalIgnoreCase) &&
                 (baton.Keywords?.Any(k => k.FormKey == AnimOneHandedKwKey) ?? false) &&
                 !(baton.Keywords?.Any(k => k.FormKey == ModAssocRescueAxeKwKey) ?? false),
                 $"WEAP 0x{Fo4WeapBatonId:X} ({Fo4WeapBatonEdid}) mismatch");

            var fc = plug.Ammunitions.FirstOrDefault(a => a.FormKey == fcFk);
            Need(fc != null &&
                 string.Equals(fc.EditorID, Fo4AmmoFusionCellEdid, StringComparison.Ordinal) &&
                 fc.Name?.String == "Fusion Cell" &&
                 fc.ShortName?.String == "Cell" &&
                 fc.Value == Fo4AmmoFusionCellValue &&
                 MathF.Abs(fc.Weight - Fo4AmmoFusionCellWeight) < 1e-4f &&
                 !fc.Flags.HasFlag(Ammunition.Flag.NonPlayable) &&
                 !fc.MajorFlags.HasFlag(Ammunition.MajorFlag.NonPlayable) &&
                 string.Equals(NormModelPath(fc.Model?.File?.GivenPath), Fo4AmmoFusionCellModel, StringComparison.OrdinalIgnoreCase),
                 $"AMMO 0x{Fo4AmmoFusionCellId:X} ({Fo4AmmoFusionCellEdid}) mismatch");

            var compFc = plug.Ammunitions.FirstOrDefault(a => a.FormKey == compFcFk);
            Need(compFc != null &&
                 string.Equals(compFc.EditorID, Fo4AmmoCompFusionCellEdid, StringComparison.Ordinal) &&
                 compFc.Name?.String == "Companion Fusion Cell" &&
                 compFc.ShortName?.String == "Cell" &&
                 compFc.Value == Fo4AmmoCompFusionCellValue &&
                 MathF.Abs(compFc.Weight) < 1e-4f &&
                 (compFc.Flags.HasFlag(Ammunition.Flag.NonPlayable) || compFc.MajorFlags.HasFlag(Ammunition.MajorFlag.NonPlayable)) &&
                 string.Equals(NormModelPath(compFc.Model?.File?.GivenPath), Fo4AmmoFusionCellModel, StringComparison.OrdinalIgnoreCase),
                 $"AMMO 0x{Fo4AmmoCompFusionCellId:X} ({Fo4AmmoCompFusionCellEdid}) mismatch");

            var lm = plug.Weapons.FirstOrDefault(w => w.FormKey == lmFk);
            Need(lm != null &&
                 string.Equals(lm.EditorID, Fo4WeapLaserMusketEdid, StringComparison.Ordinal) &&
                 lm.Name?.String == "Laser Musket" &&
                 MathF.Abs(lm.AttackDamage) < 1e-4f &&
                 HasWeaponEnergyDamage(lm, Fo4LaserMusketEnergyDamage) &&
                 lm.AmmoCapacity == Fo4LaserMusketCapacity &&
                 MathF.Abs(lm.AttackDelaySeconds - Fo4LaserMusketAttackDelaySec) < 1e-4f &&
                 MathF.Abs(lm.BaseWeight - Fo4LaserMusketWeight) < 1e-4f &&
                 lm.BaseValue == Fo4LaserMusketValue &&
                 lm.AmmoType.FormKey == fcFk &&
                 lm.ImpactDataSet.FormKey == IpdsOrionLaserKey &&
                 lm.CriticalHitSpell.FormKey == wantCritLaserFk &&
                 lm.CritEffectOnDeathOnly &&
                 !lm.NonPlayable &&
                 (lm.AttachParentSlots?.Count ?? 0) == 0 &&
                 (lm.ObjectTemplates?.Count ?? 0) == 0 &&
                 string.Equals(NormModelPath(lm.Model?.File?.GivenPath), Fo4WeapLaserMusketModel, StringComparison.OrdinalIgnoreCase) &&
                 string.Equals(NormModelPath(lm.FirstPersonModel?.File?.GivenPath), Fo4WeapLaserMusketModel, StringComparison.OrdinalIgnoreCase) &&
                 (lm.Keywords?.Any(k => k.FormKey == AnimOrionKwKey) ?? false) &&
                 !(lm.Keywords?.Any(k => k.FormKey == ModAssocOrionKwKey) ?? false),
                 $"WEAP 0x{Fo4WeapLaserMusketId:X} ({Fo4WeapLaserMusketEdid}) mismatch");

            var compLm = plug.Weapons.FirstOrDefault(w => w.FormKey == compLmFk);
            Need(compLm != null &&
                 string.Equals(compLm.EditorID, Fo4WeapCompPrestonLaserMusketEdid, StringComparison.Ordinal) &&
                 compLm.Name?.String == "Preston's Laser Musket" &&
                 MathF.Abs(compLm.AttackDamage) < 1e-4f &&
                 HasWeaponEnergyDamage(compLm, Fo4PrestonLaserMusketEnergyDamage) &&
                 compLm.AmmoCapacity == Fo4LaserMusketCapacity &&
                 MathF.Abs(compLm.AttackDelaySeconds - Fo4LaserMusketAttackDelaySec) < 1e-4f &&
                 MathF.Abs(compLm.BaseWeight - Fo4PrestonLaserMusketWeight) < 1e-4f &&
                 compLm.BaseValue == Fo4PrestonLaserMusketValue &&
                 compLm.AmmoType.FormKey == compFcFk &&
                 compLm.ImpactDataSet.FormKey == IpdsOrionLaserKey &&
                 compLm.CriticalHitSpell.FormKey == wantCritLaserFk &&
                 compLm.CritEffectOnDeathOnly &&
                 (compLm.NonPlayable || compLm.MajorFlags.HasFlag(Weapon.MajorFlag.NonPlayable)) &&
                 string.Equals(NormModelPath(compLm.Model?.File?.GivenPath), Fo4WeapLaserMusketModel, StringComparison.OrdinalIgnoreCase) &&
                 string.Equals(NormModelPath(compLm.FirstPersonModel?.File?.GivenPath), Fo4WeapLaserMusketModel, StringComparison.OrdinalIgnoreCase) &&
                 !(compLm.Keywords?.Any(k => k.FormKey == ModAssocOrionKwKey) ?? false),
                 $"WEAP 0x{Fo4WeapCompPrestonLaserMusketId:X} ({Fo4WeapCompPrestonLaserMusketEdid}) mismatch");

            var a5 = plug.Ammunitions.FirstOrDefault(a => a.FormKey == a5Fk);
            Need(a5 != null &&
                 string.Equals(a5.EditorID, Fo4Ammo5mmEdid, StringComparison.Ordinal) &&
                 a5.Name?.String == "5mm Round" &&
                 a5.ShortName?.String == "5mm" &&
                 a5.Value == Fo4Ammo5mmValue &&
                 MathF.Abs(a5.Weight - Fo4Ammo5mmWeight) < 1e-4f &&
                 !a5.Flags.HasFlag(Ammunition.Flag.NonPlayable) &&
                 string.Equals(NormModelPath(a5.Model?.File?.GivenPath), Fo4Ammo5mmModel, StringComparison.OrdinalIgnoreCase),
                 $"AMMO 0x{Fo4Ammo5mmId:X} ({Fo4Ammo5mmEdid}) mismatch");

            var mg = plug.Weapons.FirstOrDefault(w => w.FormKey == mgFk);
            Need(mg != null &&
                 string.Equals(mg.EditorID, Fo4WeapMinigunEdid, StringComparison.Ordinal) &&
                 mg.Name?.String == "Minigun" &&
                 MathF.Abs(mg.AttackDamage - Fo4MinigunBaseDamage) < 1e-4f &&
                 mg.AmmoCapacity == Fo4MinigunCapacity &&
                 MathF.Abs(mg.BaseWeight - Fo4MinigunWeight) < 1e-4f &&
                 mg.BaseValue == Fo4MinigunValue &&
                 mg.AmmoType.FormKey == a5Fk &&
                 mg.ImpactDataSet.FormKey == IpdsBulletKey &&
                 !mg.NonPlayable &&
                 (mg.AttachParentSlots?.Count ?? 0) == 0 &&
                 (mg.ObjectTemplates?.Count ?? 0) == 0 &&
                 string.Equals(NormModelPath(mg.Model?.File?.GivenPath), Fo4WeapMinigunModel, StringComparison.OrdinalIgnoreCase) &&
                 string.Equals(NormModelPath(mg.FirstPersonModel?.File?.GivenPath), Fo4WeapMinigunModel, StringComparison.OrdinalIgnoreCase) &&
                 (mg.Keywords?.Any(k => k.FormKey == AnimGripHeavyKwKey) ?? false) &&
                 (mg.Keywords?.Any(k => k.FormKey == AnimMicrogunKwKey) ?? false) &&
                 !(mg.Keywords?.Any(k => k.FormKey == ModAssocMicrogunKwKey) ?? false),
                 $"WEAP 0x{Fo4WeapMinigunId:X} ({Fo4WeapMinigunEdid}) mismatch");
        }
        if (expectArsenal == 1)
        {
            var caps = plug.MiscItems.FirstOrDefault(m => m.FormKey == new FormKey(pluginKey, Fo4MiscCapsId));
            Need(caps != null && caps.EditorID == "FO4_Caps" && caps.Name?.String == "Bottlecap" && caps.Value == 1 && MathF.Abs(caps.Weight) < 1e-4f &&
                 string.Equals(NormModelPath(caps.Model?.File?.GivenPath), @"fo4core\props\bottlecapsingle.nif", StringComparison.OrdinalIgnoreCase),
                 "MISC FO4_Caps mismatch");
            var bp = plug.MiscItems.FirstOrDefault(m => m.FormKey == new FormKey(pluginKey, Fo4MiscBobbyPinId));
            Need(bp != null && bp.EditorID == "FO4_BobbyPin" && bp.Name?.String == "Bobby Pin" && bp.Value == 1 && MathF.Abs(bp.Weight) < 1e-4f &&
                 string.Equals(NormModelPath(bp.Model?.File?.GivenPath), @"fo4core\props\bobbypin.nif", StringComparison.OrdinalIgnoreCase),
                 "MISC FO4_BobbyPin mismatch");

            foreach (var es in ArsenalExplSpecs)
            {
                var expl = plug.Explosions.FirstOrDefault(e => e.FormKey == new FormKey(pluginKey, es.Id));
                Need(expl != null && expl.EditorID == es.Edid &&
                     MathF.Abs(expl.Damage - es.Dmg) < 1e-4f &&
                     MathF.Abs(expl.OuterRadius - es.OuterM) < 1e-4f &&
                     expl.ImpactDataSet.FormKey == es.IpdsKey,
                     $"EXPL 0x{es.Id:X} ({es.Edid}) mismatch");
            }
            foreach (var ps in ArsenalProjSpecs)
            {
                var proj = plug.Projectiles.FirstOrDefault(p => p.FormKey == new FormKey(pluginKey, ps.Id));
                Need(proj != null && proj.EditorID == ps.Edid &&
                     proj.Explosion.FormKey == new FormKey(pluginKey, ps.ExplId) &&
                     string.Equals(NormModelPath(proj.Model?.File?.GivenPath), ps.Model, StringComparison.OrdinalIgnoreCase),
                     $"PROJ 0x{ps.Id:X} ({ps.Edid}) mismatch");
            }
            foreach (var aSpec in ArsenalAmmoSpecs)
            {
                var am = plug.Ammunitions.FirstOrDefault(a => a.FormKey == new FormKey(pluginKey, aSpec.Id));
                Need(am != null && am.EditorID == aSpec.Edid && am.Name?.String == aSpec.Name &&
                     am.ShortName?.String == aSpec.Short && am.Value == aSpec.Val &&
                     MathF.Abs(am.Weight - aSpec.Wt) < 1e-4f &&
                     !am.Flags.HasFlag(Ammunition.Flag.NonPlayable) && !am.MajorFlags.HasFlag(Ammunition.MajorFlag.NonPlayable) &&
                     (aSpec.ProjId == 0 || am.Projectile.FormKey == new FormKey(pluginKey, aSpec.ProjId)) &&
                     string.Equals(NormModelPath(am.Model?.File?.GivenPath), aSpec.Model, StringComparison.OrdinalIgnoreCase),
                     $"AMMO 0x{aSpec.Id:X} ({aSpec.Edid}) mismatch");
            }
            var gooFk = new FormKey(pluginKey, Fo4ActiGooPileId);
            var goo = plug.Activators.FirstOrDefault(a => a.FormKey == gooFk);
            Need(goo != null && goo.EditorID == "FO4_GooPile01" && goo.Name?.String == "Goo Pile" &&
                 string.Equals(NormModelPath(goo.Model?.File?.GivenPath), @"fo4core\effects\ashpileplasmagoo.nif", StringComparison.OrdinalIgnoreCase),
                 "ACTI FO4_GooPile01 mismatch");
            var cpMgefFk = new FormKey(pluginKey, Fo4MgefCritPlasmaId);
            var cpMgef = plug.MagicEffects.FirstOrDefault(m => m.FormKey == cpMgefFk);
            bool hasGooProp = cpMgef?.VirtualMachineAdapter?.Scripts.Any(sc =>
                sc.Properties.OfType<ScriptObjectProperty>().Any(sp =>
                    string.Equals(sp.Name, "AshPileObject", StringComparison.OrdinalIgnoreCase) && sp.Object.FormKey == gooFk)) ?? false;
            Need(cpMgef != null && cpMgef.EditorID == "FO4_CritPlasmaEffect" && hasGooProp, "MGEF FO4_CritPlasmaEffect mismatch");
            var cpSpel = plug.Spells.FirstOrDefault(s => s.FormKey == new FormKey(pluginKey, Fo4SpelCritPlasmaId));
            Need(cpSpel != null && cpSpel.EditorID == "FO4_CritPlasma" && cpSpel.Effects.Count > 0 &&
                 cpSpel.Effects[0].BaseEffect.FormKey == cpMgefFk, "SPEL FO4_CritPlasma mismatch");
            var clSpel = plug.Spells.FirstOrDefault(s => s.FormKey == new FormKey(pluginKey, Fo4SpelCritLaserId));
            Need(clSpel != null && clSpel.EditorID == "FO4_CritLaser" && clSpel.Effects.Count > 0 &&
                 clSpel.Effects[0].BaseEffect.FormKey == SfMgefCritLaserEffectKey, "SPEL FO4_CritLaser mismatch");

            foreach (var ws in ArsenalWeapSpecs)
            {
                var w = plug.Weapons.FirstOrDefault(x => x.FormKey == new FormKey(pluginKey, ws.Id));
                bool nameClean = w?.Name?.String != null && !w.Name.String.Contains("Starfield", StringComparison.OrdinalIgnoreCase) && !w.Name.String.StartsWith("FO4SF", StringComparison.OrdinalIgnoreCase);
                bool modelOk = ws.Model == null
                    ? (w?.Model?.File == null && w?.FirstPersonModel?.File == null)
                    : (string.Equals(NormModelPath(w?.Model?.File?.GivenPath), ws.Model, StringComparison.OrdinalIgnoreCase) &&
                       string.Equals(NormModelPath(w?.FirstPersonModel?.File?.GivenPath), ws.Model, StringComparison.OrdinalIgnoreCase));
                Need(w != null &&
                     string.Equals(w.EditorID, ws.Edid, StringComparison.Ordinal) &&
                     nameClean &&
                     string.Equals(w.Name!.String, ws.Name, StringComparison.Ordinal) &&
                     MathF.Abs(w.AttackDamage - ws.PhysDmg) < 1e-4f &&
                     (ws.EnergyDmg == 0 ? (w.DamageTypes == null || w.DamageTypes.Count == 0) : HasWeaponEnergyDamage(w, ws.EnergyDmg)) &&
                     w.AmmoCapacity == ws.Cap &&
                     (ws.AmmoId == 0 ? w.AmmoType.IsNull : w.AmmoType.FormKey == new FormKey(pluginKey, ws.AmmoId)) &&
                     MathF.Abs(w.BaseWeight - ws.Wt) < 1e-4f &&
                     w.BaseValue == ws.Val &&
                     w.ImpactDataSet.FormKey == ws.IpdsKey &&
                     (ws.CritSpellId == 0 || (w.CriticalHitSpell.FormKey == new FormKey(pluginKey, ws.CritSpellId) && w.CritEffectOnDeathOnly)) &&
                     (ws.OverrideProjId == 0 || w.OverrideProjectile.FormKey == new FormKey(pluginKey, ws.OverrideProjId)) &&
                     (w.NonPlayable || w.MajorFlags.HasFlag(Weapon.MajorFlag.NonPlayable)) == ws.NonPlayable &&
                     (w.AttachParentSlots?.Count ?? 0) == 0 &&
                     (w.ObjectTemplates?.Count ?? 0) == 0 &&
                     modelOk,
                     $"WEAP 0x{ws.Id:X} ({ws.Edid}) mismatch");
            }
        }

        if (problems.Count > 0)
            throw new Refusal(string.Join("; ", problems));
        Console.WriteLine($"check ok: {pluginKey} ({plug.ActorValueInformation.Count} AVIF, {plug.Globals.Count} GLOB, " +
                          $"{plug.FormLists.Count} FLST, {plug.MagicEffects.Count} MGEF, {plug.Ingestibles.Count} ALCH" +
                          (plug.Climates.Count > 0 || plug.Atmospheres.Count > 0
                              ? $", {plug.Climates.Count} CLMT, {plug.Atmospheres.Count} ATMO"
                              : "") +
                          (plug.Weapons.Count > 0 || plug.Ammunitions.Count > 0
                              ? $", {plug.Ammunitions.Count} AMMO, {plug.Weapons.Count} WEAP, " +
                                $"{plug.MiscItems.Count} MISC, {plug.Explosions.Count} EXPL, {plug.Projectiles.Count} PROJ, " +
                                $"{plug.Activators.Count} ACTI, {plug.Spells.Count} SPEL"
                              : "") + ")");
        return 0;
    }

    public static int Fixture(string outDir)
    {
        var sf = new StarfieldMod(SfEsm, Release);
        sf.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        var health = new ActorValueInformation(new FormKey(SfEsm, 0x000801), Release)
        {
            EditorID = "Health", Name = "Health", Type = ActorValueInformation.Types.Variable,
        };
        sf.ActorValueInformation.Add(health);
        var mgef = new MagicEffect(new FormKey(SfEsm, 0x000900), Release)
        {
            EditorID = "AbRestoreHealth", Name = "Restore Health",
            Archetype = new MagicEffectArchetype(MagicEffectArchetype.TypeEnum.ValueModifier),
            CastType = CastType.FireAndForget, TargetType = TargetType.Self,
        };
        mgef.SecondActorValue.SetTo(health.FormKey);
        sf.MagicEffects.Add(mgef);
        var aid = new Ingestible(new FormKey(SfEsm, 0x00ABF9), Release)
        {
            EditorID = "MedPack", Name = "Med Pack", Flags = Ingestible.Flag.Medicine, MajorFlags = Ingestible.MajorFlag.Medicine,
        };
        aid.Effects.Add(new Effect
        {
            BaseEffect = new FormLinkNullable<IMagicEffectGetter>(mgef.FormKey),
            Data = new EffectData { Magnitude = 25f, Area = 0, Duration = 0 },
        });
        sf.Ingestibles.Add(aid);
        WriteMod(sf, SfEsm, outDir);
        return 0;
    }

    public static int SelfTest(string scratchDir)
    {
        if (Directory.Exists(scratchDir)) Directory.Delete(scratchDir, recursive: true);
        Directory.CreateDirectory(scratchDir);
        var fixDir = Path.Combine(scratchDir, "fixture");
        Fixture(fixDir);
        var sfPath = Path.Combine(fixDir, "Starfield.esm");
        var jsonPath = DefaultJsonPath();

        var defOpts = new BuildOptions(jsonPath, 0, 0, 0);
        var outDef = Path.Combine(scratchDir, "default");
        Build(sfPath, outDef, defOpts);
        var plugDef = Path.Combine(outDef, "FO4SFCoreValues.esm");
        Check(plugDef, sfPath, defOpts);

        // Byte-identical determinism check
        var outDef2 = Path.Combine(scratchDir, "default2");
        Build(sfPath, outDef2, defOpts);
        if (!File.ReadAllBytes(plugDef).SequenceEqual(File.ReadAllBytes(Path.Combine(outDef2, "FO4SFCoreValues.esm"))))
            throw new Refusal("FO4SFCoreValues.esm build is not byte-identical");

        // Option variants must validate against their own options and reject mismatched options
        var altOpts = new BuildOptions(jsonPath, 1, 1, 1);
        var outAlt = Path.Combine(scratchDir, "alt");
        Build(sfPath, outAlt, altOpts);
        Check(Path.Combine(outAlt, "FO4SFCoreValues.esm"), sfPath, altOpts);

        bool rejected = false;
        try { Check(Path.Combine(outAlt, "FO4SFCoreValues.esm"), sfPath, defOpts); }
        catch (Refusal) { rejected = true; }
        if (!rejected) throw new Refusal("Check accepted mismatched FO4SF_TestModeEnabled/Hardcore/RadsRule globals");

        // Tamper check: moving FO4SF_Rads off 0x800 must fail
        var tamperedMod = StarfieldMod.CreateFromBinary(plugDef, Release, new BinaryReadParameters
        {
            MasterFlagsLookup = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey) { new KeyedMasterStyle(SfEsm, MasterStyle.Full) }
        });
        tamperedMod.ActorValueInformation.First(a => a.FormKey.ID == 0x800).EditorID = "FO4SF_RadsMoved";
        var outTamper = Path.Combine(scratchDir, "tamper");
        WriteMod(tamperedMod, ModKey.FromFileName("FO4SFCoreValues.esm"), outTamper);
        rejected = false;
        try { Check(Path.Combine(outTamper, "FO4SFCoreValues.esm"), sfPath, defOpts); }
        catch (Refusal) { rejected = true; }
        if (!rejected) throw new Refusal("Check accepted tampered FO4SF_Rads EditorID at 0x800");

        // D7(a) weather + atmosphere override selftest on a synthetic Starfield.esm fixture containing Mars/NewAtlantis CLMT & ATMO
        var wFixDir = Path.Combine(scratchDir, "weather_fixture");
        var wSf = StarfieldMod.CreateFromBinary(sfPath, Release, new BinaryReadParameters
        {
            MasterFlagsLookup = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey) { new KeyedMasterStyle(SfEsm, MasterStyle.Full) }
        });
        var naFixtureClmt = new Climate(ClimateNewAtlantisKey, Release)
        {
            EditorID = ExpectedClimateNewAtlantisEdid,
            WeatherSettings = new ExtendedList<ClimateWeatherSettings>
            {
                new ClimateWeatherSettings { Settings = new FormLink<IWeatherSettingGetter>(new FormKey(SfEsm, 0x0009BC5A)), Chance = 30 },
                new ClimateWeatherSettings { Settings = new FormLink<IWeatherSettingGetter>(new FormKey(SfEsm, 0x001034AB)), Chance = 25 },
            },
        };
        wSf.Climates.Add(naFixtureClmt);
        wSf.Climates.Add(new Climate(ClimateCydoniaKey, Release) { EditorID = ExpectedClimateCydoniaEdid });
        wSf.Climates.Add(new Climate(ClimateCydoniaFrozenKey, Release) { EditorID = ExpectedClimateCydoniaFrozenEdid });
        wSf.Atmospheres.Add(new Atmosphere(AtmoJemisonKey, Release) { EditorID = ExpectedAtmoJemisonEdid });
        wSf.Atmospheres.Add(new Atmosphere(AtmoMarsKey, Release) { EditorID = ExpectedAtmoMarsEdid });
        WriteMod(wSf, SfEsm, wFixDir);
        var wSfPath = Path.Combine(wFixDir, "Starfield.esm");

        var wOnOpts = new BuildOptions(jsonPath, 0, 0, 0, 1);
        var wOffOpts = new BuildOptions(jsonPath, 0, 0, 0, 0);
        var outWOn = Path.Combine(scratchDir, "weather_on");
        var outWOn2 = Path.Combine(scratchDir, "weather_on2");
        var outWOff = Path.Combine(scratchDir, "weather_off");
        Build(wSfPath, outWOn, wOnOpts);
        Check(Path.Combine(outWOn, "FO4SFCoreValues.esm"), wSfPath, wOnOpts);
        Build(wSfPath, outWOn2, wOnOpts);
        if (!File.ReadAllBytes(Path.Combine(outWOn, "FO4SFCoreValues.esm"))
                 .SequenceEqual(File.ReadAllBytes(Path.Combine(outWOn2, "FO4SFCoreValues.esm"))))
            throw new Refusal("FO4SFCoreValues.esm weather override build is not byte-identical");
        Build(wSfPath, outWOff, wOffOpts);
        Check(Path.Combine(outWOff, "FO4SFCoreValues.esm"), wSfPath, wOffOpts);

        rejected = false;
        try { Check(Path.Combine(outWOn, "FO4SFCoreValues.esm"), wSfPath, wOffOpts); }
        catch (Refusal) { rejected = true; }
        if (!rejected) throw new Refusal("Check accepted weather overrides when --commonwealth-weather 0");

        // Review item #4 negative check: mismatched weather/atmosphere source EditorIDs must refuse Build()
        var badClmtDir = Path.Combine(scratchDir, "weather_bad_clmt");
        var badClmtSf = StarfieldMod.CreateFromBinary(wSfPath, Release, new BinaryReadParameters
        {
            MasterFlagsLookup = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey) { new KeyedMasterStyle(SfEsm, MasterStyle.Full) }
        });
        badClmtSf.Climates.First(c => c.FormKey == ClimateCydoniaKey).EditorID = "WrongClimateEdid";
        WriteMod(badClmtSf, SfEsm, badClmtDir);
        rejected = false;
        try { Build(Path.Combine(badClmtDir, "Starfield.esm"), Path.Combine(scratchDir, "weather_bad_clmt_out"), wOnOpts); }
        catch (Refusal) { rejected = true; }
        if (!rejected) throw new Refusal("Build accepted mismatched ClimateUniqueCydonia EditorID");

        var badAtmoDir = Path.Combine(scratchDir, "weather_bad_atmo");
        var badAtmoSf = StarfieldMod.CreateFromBinary(wSfPath, Release, new BinaryReadParameters
        {
            MasterFlagsLookup = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey) { new KeyedMasterStyle(SfEsm, MasterStyle.Full) }
        });
        badAtmoSf.Atmospheres.First(a => a.FormKey == AtmoJemisonKey).EditorID = "WrongAtmoEdid";
        WriteMod(badAtmoSf, SfEsm, badAtmoDir);
        rejected = false;
        try { Build(Path.Combine(badAtmoDir, "Starfield.esm"), Path.Combine(scratchDir, "weather_bad_atmo_out"), wOnOpts); }
        catch (Refusal) { rejected = true; }
        if (!rejected) throw new Refusal("Build accepted mismatched ATMO_Jemison EditorID");

        // A4.1 (FO4_Ammo10mm 0x000898 + FO4_10mmPistol 0x000899) positive, rollback, determinism & negative tamper checks
        var pFixDir = Path.Combine(scratchDir, "pistol10mm_fixture");
        var pSf = StarfieldMod.CreateFromBinary(sfPath, Release, new BinaryReadParameters
        {
            MasterFlagsLookup = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey) { new KeyedMasterStyle(SfEsm, MasterStyle.Full) }
        });
        pSf.Ammunitions.Add(new Ammunition(DonorAmmo45Key, Release)
        {
            EditorID = ExpectedDonorAmmo45Edid,
            Name = ".45 Caliber ACP",
            Value = 25,
            Weight = 0.01f,
            Model = new Model { File = @"SetDressing\ammo_crates\Ammo45Caliber.nif", LightLayer = 1 },
        });
        var xm2311Fix = new Weapon(DonorWeapXm2311Key, Release)
        {
            EditorID = ExpectedDonorWeapXm2311Edid,
            Name = "XM-2311",
            Model = new Model { File = @"Weapons\Bullpup\BullpupDummyReceiver.nif", LightLayer = 1 },
            FirstPersonModel = new FirstPersonModel { File = @"Weapons\Bullpup\BullpupDummyReceiver.nif", LightLayer = 1 },
            AttackDamage = 36f,
            AmmoCapacity = 9,
            AttackDelaySeconds = 0.15f,
            BaseWeight = 1.1f,
            BaseValue = 8200,
            Keywords = new ExtendedList<IFormLinkGetter<IKeywordGetter>> { AnimGripPistolKwKey, AnimM1919KwKey, ModAssocXm2311KwKey },
            AttachParentSlots = new ExtendedList<IFormLinkGetter<IKeywordGetter>> { ModAssocNullMuzzleKwKey },
            ObjectTemplates = new ExtendedList<ObjectTemplate<Weapon.Property>> { new ObjectTemplate<Weapon.Property>() },
        };
        xm2311Fix.AmmoType.SetTo(DonorAmmo45Key);
        pSf.Weapons.Add(xm2311Fix);
        WriteMod(pSf, SfEsm, pFixDir);
        var pSfPath = Path.Combine(pFixDir, "Starfield.esm");

        var pOnOpts = new BuildOptions(jsonPath, 0, 0, 0, 1, 1);
        var pOffOpts = new BuildOptions(jsonPath, 0, 0, 0, 1, 0);
        var outPOn = Path.Combine(scratchDir, "pistol10mm_on");
        var outPOn2 = Path.Combine(scratchDir, "pistol10mm_on2");
        var outPOff = Path.Combine(scratchDir, "pistol10mm_off");
        Build(pSfPath, outPOn, pOnOpts);
        var plugPOn = Path.Combine(outPOn, "FO4SFCoreValues.esm");
        Check(plugPOn, pSfPath, pOnOpts);
        Build(pSfPath, outPOn2, pOnOpts);
        if (!File.ReadAllBytes(plugPOn).SequenceEqual(File.ReadAllBytes(Path.Combine(outPOn2, "FO4SFCoreValues.esm"))))
            throw new Refusal("FO4SFCoreValues.esm --fo4-10mm 1 build is not byte-identical");

        Build(pSfPath, outPOff, pOffOpts);
        Check(Path.Combine(outPOff, "FO4SFCoreValues.esm"), pSfPath, pOffOpts);

        rejected = false;
        try { Check(plugPOn, pSfPath, pOffOpts); }
        catch (Refusal) { rejected = true; }
        if (!rejected) throw new Refusal("Check accepted FO4_10mmPistol when --fo4-10mm 0");

        foreach (var (label, mutateWeap) in new (string, Action<StarfieldMod>)[]
        {
            ("wrong BaseDamage", m => m.Weapons.First().AttackDamage = 36f),
            ("wrong AmmoCapacity", m => m.Weapons.First().AmmoCapacity = 9),
            ("unstripped FirstPersonModel dummy", m => m.Weapons.First().FirstPersonModel = new FirstPersonModel { File = @"Weapons\Bullpup\BullpupDummyReceiver.nif" }),
            ("leftover ObjectTemplates", m => m.Weapons.First().ObjectTemplates = new ExtendedList<ObjectTemplate<Weapon.Property>> { new ObjectTemplate<Weapon.Property>() }),
        })
        {
            var tMod = StarfieldMod.CreateFromBinary(plugPOn, Release, new BinaryReadParameters
            {
                MasterFlagsLookup = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey) { new KeyedMasterStyle(SfEsm, MasterStyle.Full) }
            });
            mutateWeap(tMod);
            var tDir = Path.Combine(scratchDir, "pistol_tamper_" + label.Replace(' ', '_'));
            WriteMod(tMod, ModKey.FromFileName("FO4SFCoreValues.esm"), tDir);
            rejected = false;
            try { Check(Path.Combine(tDir, "FO4SFCoreValues.esm"), pSfPath, pOnOpts); }
            catch (Refusal) { rejected = true; }
            if (!rejected) throw new Refusal($"Check accepted tampered FO4_10mmPistol ({label})");
        }

        var badWeapDir = Path.Combine(scratchDir, "pistol_bad_donor");
        var badWeapSf = StarfieldMod.CreateFromBinary(pSfPath, Release, new BinaryReadParameters
        {
            MasterFlagsLookup = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey) { new KeyedMasterStyle(SfEsm, MasterStyle.Full) }
        });
        badWeapSf.Weapons.First(w => w.FormKey == DonorWeapXm2311Key).EditorID = "WrongDonorWeapon";
        WriteMod(badWeapSf, SfEsm, badWeapDir);
        rejected = false;
        try { Build(Path.Combine(badWeapDir, "Starfield.esm"), Path.Combine(scratchDir, "pistol_bad_donor_out"), pOnOpts); }
        catch (Refusal) { rejected = true; }
        if (!rejected) throw new Refusal("Build accepted mismatched XM2311 donor EditorID");

        // Step 4 P5 weapons & ammo (0x000898..0x0008A0: 4 AMMO + 5 WEAP) positive, --fo4-p5-weapons 0 rollback, & tamper checks
        var p5FixDir = Path.Combine(scratchDir, "p5_weapons_fixture");
        var p5Sf = StarfieldMod.CreateFromBinary(pSfPath, Release, new BinaryReadParameters
        {
            MasterFlagsLookup = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey) { new KeyedMasterStyle(SfEsm, MasterStyle.Full) }
        });
        p5Sf.Weapons.Add(new Weapon(DonorWeapRescueAxeKey, Release)
        {
            EditorID = ExpectedDonorWeapRescueAxeEdid,
            Name = "Rescue Axe",
            Model = new Model { File = @"Weapons\RescueAxe\RescueAxe.nif", LightLayer = 1 },
            AttackDamage = 40f,
            Keywords = new ExtendedList<IFormLinkGetter<IKeywordGetter>> { AnimOneHandedKwKey, ModAssocRescueAxeKwKey },
        });
        p5Sf.Ammunitions.Add(new Ammunition(DonorAmmoLaserKey, Release)
        {
            EditorID = ExpectedDonorAmmoLaserEdid,
            Name = "3KV LZR Cartridge",
            Model = new Model { File = @"SetDressing\ammo_crates\AmmoLaser.nif", LightLayer = 1 },
        });
        var orionFix = new Weapon(DonorWeapOrionKey, Release)
        {
            EditorID = ExpectedDonorWeapOrionEdid,
            Name = "Orion",
            Model = new Model { File = @"Weapons\Bullpup\BullpupDummyReceiver.nif", LightLayer = 1 },
            AttackDamage = 0f,
            DamageTypes = new ExtendedList<WeaponDamageType>
            {
                new WeaponDamageType { DamageType = new FormLink<IDamageTypeGetter>(DtEnergyKey), Value = 27 },
            },
            Keywords = new ExtendedList<IFormLinkGetter<IKeywordGetter>> { AnimGripExtendedLowKwKey, AnimOrionKwKey, ModAssocOrionKwKey, TeammateDontUseAmmoKwKey },
        };
        orionFix.AmmoType.SetTo(DonorAmmoLaserKey);
        p5Sf.Weapons.Add(orionFix);
        p5Sf.Ammunitions.Add(new Ammunition(DonorAmmo777Key, Release)
        {
            EditorID = ExpectedDonorAmmo777Edid,
            Name = "7.77mm Caseless",
            Model = new Model { File = @"SetDressing\ammo_crates\Ammo777mm.nif", LightLayer = 1 },
        });
        var mgFix = new Weapon(DonorWeapMicrogunKey, Release)
        {
            EditorID = ExpectedDonorWeapMicrogunEdid,
            Name = "Microgun",
            Model = new Model { File = @"Weapons\Bullpup\BullpupDummyReceiver.nif", LightLayer = 1 },
            AttackDamage = 56f,
            Keywords = new ExtendedList<IFormLinkGetter<IKeywordGetter>> { AnimGripHeavyKwKey, AnimMicrogunKwKey, ModAssocMicrogunKwKey },
        };
        mgFix.AmmoType.SetTo(DonorAmmo777Key);
        p5Sf.Weapons.Add(mgFix);
        WriteMod(p5Sf, SfEsm, p5FixDir);
        var p5SfPath = Path.Combine(p5FixDir, "Starfield.esm");

        var p5OnOpts = new BuildOptions(jsonPath, 0, 0, 0, 1, 1, 1);
        var p5Only10mmOpts = new BuildOptions(jsonPath, 0, 0, 0, 1, 1, 0);
        var outP5On = Path.Combine(scratchDir, "p5_weapons_on");
        var outP5On2 = Path.Combine(scratchDir, "p5_weapons_on2");
        var outP5Only10 = Path.Combine(scratchDir, "p5_only_10mm");
        Build(p5SfPath, outP5On, p5OnOpts);
        var plugP5On = Path.Combine(outP5On, "FO4SFCoreValues.esm");
        Check(plugP5On, p5SfPath, p5OnOpts);
        Build(p5SfPath, outP5On2, p5OnOpts);
        if (!File.ReadAllBytes(plugP5On).SequenceEqual(File.ReadAllBytes(Path.Combine(outP5On2, "FO4SFCoreValues.esm"))))
            throw new Refusal("FO4SFCoreValues.esm --fo4-p5-weapons 1 build is not byte-identical");
        Build(p5SfPath, outP5Only10, p5Only10mmOpts);
        Check(Path.Combine(outP5Only10, "FO4SFCoreValues.esm"), p5SfPath, p5Only10mmOpts);

        rejected = false;
        try { Check(plugP5On, p5SfPath, p5Only10mmOpts); }
        catch (Refusal) { rejected = true; }
        if (!rejected) throw new Refusal("Check accepted P5 weapons when --fo4-p5-weapons 0");

        foreach (var (label, mutateP5) in new (string, Action<StarfieldMod>)[]
        {
            ("baton wrong damage", m => m.Weapons.First(w => w.FormKey.ID == Fo4WeapBatonId).AttackDamage = 40f),
            ("musket wrong energy damage", m => m.Weapons.First(w => w.FormKey.ID == Fo4WeapLaserMusketId).DamageTypes![0].Value = 27),
            ("musket nonzero phys damage", m => m.Weapons.First(w => w.FormKey.ID == Fo4WeapLaserMusketId).AttackDamage = 30f),
            ("preston musket playable", m =>
            {
                var w = m.Weapons.First(x => x.FormKey.ID == Fo4WeapCompPrestonLaserMusketId);
                w.NonPlayable = false;
                w.MajorFlags &= ~Weapon.MajorFlag.NonPlayable;
            }),
            ("comp fusion cell playable", m =>
            {
                var a = m.Ammunitions.First(x => x.FormKey.ID == Fo4AmmoCompFusionCellId);
                a.Flags &= ~Ammunition.Flag.NonPlayable;
                a.MajorFlags &= ~Ammunition.MajorFlag.NonPlayable;
            }),
            ("minigun wrong capacity", m => m.Weapons.First(w => w.FormKey.ID == Fo4WeapMinigunId).AmmoCapacity = 300),
            ("minigun unstripped ModAssoc", m => m.Weapons.First(w => w.FormKey.ID == Fo4WeapMinigunId).Keywords!.Add(ModAssocMicrogunKwKey)),
        })
        {
            var tMod = StarfieldMod.CreateFromBinary(plugP5On, Release, new BinaryReadParameters
            {
                MasterFlagsLookup = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey) { new KeyedMasterStyle(SfEsm, MasterStyle.Full) }
            });
            mutateP5(tMod);
            var tDir = Path.Combine(scratchDir, "p5_tamper_" + label.Replace(' ', '_'));
            WriteMod(tMod, ModKey.FromFileName("FO4SFCoreValues.esm"), tDir);
            rejected = false;
            try { Check(Path.Combine(tDir, "FO4SFCoreValues.esm"), p5SfPath, p5OnOpts); }
            catch (Refusal) { rejected = true; }
            if (!rejected) throw new Refusal($"Check accepted tampered P5 weapon/ammo ({label})");
        }

        // Step 4 Row 5-20 Arsenal (0x8A1..0x8A5, 0x8B0..0x8D6), EXPL.ENAM, WVIS, Ash/Goo positive, rollback & tamper checks
        var arsFixDir = Path.Combine(scratchDir, "arsenal_fixture");
        var arsSf = StarfieldMod.CreateFromBinary(p5SfPath, Release, new BinaryReadParameters
        {
            MasterFlagsLookup = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey) { new KeyedMasterStyle(SfEsm, MasterStyle.Full) }
        });
        foreach (var wk in new[]
        {
            DonorWeapEonKey, DonorWeapBeowulfKey, DonorWeapUnarmedKey, DonorWeapFragGrenadeKey, DonorWeapFragMineKey,
            DonorWeapRazorbackKey, DonorWeapLawgiverKey, DonorWeapPacifierKey, DonorWeapCoachmanKey, DonorWeapMaelstromKey,
            DonorWeapAa99Key, DonorWeapSolsticeKey, DonorWeapEquinoxKey, DonorWeapBridgerKey, DonorWeapArcWelderKey,
            DonorWeapNovalightKey, DonorWeapInflictorRifleKey, DonorWeapMagSniperKey,
        })
        {
            arsSf.Weapons.Add(new Weapon(wk, Release) { EditorID = "Donor_" + wk.IDString(), Name = "Starfield " + wk.IDString() });
        }
        foreach (var ak in new[] { DonorAmmo50CalKey, DonorAmmoShotshellKey, DonorAmmo11mmKey, DonorAmmo40mmXplKey })
            arsSf.Ammunitions.Add(new Ammunition(ak, Release) { EditorID = "DonorAmmo_" + ak.IDString(), Name = ak.IDString() });
        foreach (var pk in new[] { DonorProjFragGrenadeKey, DonorProjFragMineKey, DonorProjBridgerRocketKey })
            arsSf.Projectiles.Add(new Projectile(pk, Release) { EditorID = "DonorProj_" + pk.IDString() });
        foreach (var ek in new[] { DonorExplFragGrenadeKey, DonorExplBridgerRocketKey })
            arsSf.Explosions.Add(new Explosion(ek, Release) { EditorID = "DonorExpl_" + ek.IDString() });
        arsSf.Activators.Add(new Mutagen.Bethesda.Starfield.Activator(SfActiAshPile01Key, Release) { EditorID = "AshPile01" });
        var sfCritMgef = new MagicEffect(SfMgefCritLaserEffectKey, Release) { EditorID = "CritLaserEffect" };
        sfCritMgef.VirtualMachineAdapter = new VirtualMachineAdapter();
        var scrEntry = new ScriptEntry { Name = "AttachAshPile" };
        var ashProp = new ScriptObjectProperty { Name = "AshPileObject" };
        ashProp.Object.SetTo(new FormKey(SfEsm, 0x0000001B));
        scrEntry.Properties.Add(ashProp);
        sfCritMgef.VirtualMachineAdapter.Scripts.Add(scrEntry);
        arsSf.MagicEffects.Add(sfCritMgef);
        var sfCritSpel = new Spell(SfSpelCritLaserDisintKey, Release) { EditorID = "Crit_LaserWeapDisintegrateSpell" };
        sfCritSpel.Effects.Add(new Effect { BaseEffect = new FormLinkNullable<IMagicEffectGetter>(SfMgefCritLaserEffectKey), Data = new EffectData { Magnitude = 10f, Duration = 10 } });
        arsSf.Spells.Add(sfCritSpel);
        arsSf.MiscItems.Add(new MiscItem(SfMiscCreditsKey, Release) { EditorID = "Credits" });
        arsSf.MiscItems.Add(new MiscItem(SfMiscDigipickKey, Release) { EditorID = "Digipick" });
        WriteMod(arsSf, SfEsm, arsFixDir);
        var arsSfPath = Path.Combine(arsFixDir, "Starfield.esm");

        var arsOnOpts = new BuildOptions(jsonPath, 0, 0, 0, 1, 1, 1, 1);
        var arsOffOpts = new BuildOptions(jsonPath, 0, 0, 0, 1, 1, 1, 0);
        var outArsOn = Path.Combine(scratchDir, "arsenal_on");
        var outArsOn2 = Path.Combine(scratchDir, "arsenal_on2");
        var outArsOff = Path.Combine(scratchDir, "arsenal_off");
        Build(arsSfPath, outArsOn, arsOnOpts);
        var plugArsOn = Path.Combine(outArsOn, "FO4SFCoreValues.esm");
        Check(plugArsOn, arsSfPath, arsOnOpts);
        Build(arsSfPath, outArsOn2, arsOnOpts);
        if (!File.ReadAllBytes(plugArsOn).SequenceEqual(File.ReadAllBytes(Path.Combine(outArsOn2, "FO4SFCoreValues.esm"))))
            throw new Refusal("FO4SFCoreValues.esm --fo4-arsenal 1 build is not byte-identical");
        Build(arsSfPath, outArsOff, arsOffOpts);
        Check(Path.Combine(outArsOff, "FO4SFCoreValues.esm"), arsSfPath, arsOffOpts);

        rejected = false;
        try { Check(plugArsOn, arsSfPath, arsOffOpts); }
        catch (Refusal) { rejected = true; }
        if (!rejected) throw new Refusal("Check accepted Arsenal records when --fo4-arsenal 0");

        foreach (var (label, mutateArs) in new (string, Action<StarfieldMod>)[]
        {
            ("pipe pistol wrong WVIS", m => m.Weapons.First(w => w.FormKey.ID == Fo4WeapPipePistolId).ImpactDataSet.SetTo(IpdsExplosiveKey)),
            ("grenade explosion wrong ENAM", m => m.Explosions.First(e => e.FormKey.ID == Fo4ExplFragGrenadeId).ImpactDataSet.SetTo(IpdsBulletKey)),
            ("plasma rifle wrong CritSpell", m => m.Weapons.First(w => w.FormKey.ID == Fo4WeapPlasmaRifleId).CriticalHitSpell.SetTo(SfSpelCritLaserDisintKey)),
            ("unarmed playable leak", m =>
            {
                var w = m.Weapons.First(x => x.FormKey.ID == Fo4WeapUnarmedHumanId);
                w.NonPlayable = false;
                w.MajorFlags &= ~Weapon.MajorFlag.NonPlayable;
            }),
            ("goo effect cleared AshPileObject", m =>
            {
                var mg = m.MagicEffects.First(x => x.FormKey.ID == Fo4MgefCritPlasmaId);
                ((ScriptObjectProperty)mg.VirtualMachineAdapter!.Scripts[0].Properties[0]).Object.SetToNull();
            }),
            ("pipe pistol Starfield name leak", m => m.Weapons.First(w => w.FormKey.ID == Fo4WeapPipePistolId).Name = "Starfield Eon"),
            ("baton bladed WVIS regression", m => m.Weapons.First(w => w.FormKey.ID == Fo4WeapBatonId).ImpactDataSet.SetTo(IpdsMeleeBladeSmallKey)),
            ("baseball bat bladed WVIS regression", m => m.Weapons.First(w => w.FormKey.ID == Fo4WeapBaseballBatId).ImpactDataSet.SetTo(IpdsMeleeBladeMediumKey)),
            ("smg missing 0015B044 damage OMOD", m => SetWeaponDamage(m.Weapons.First(w => w.FormKey.ID == Fo4WeapSubmachineGunId), 13f, 0)),
            ("assault rifle missing 0018896B mag OMOD", m => m.Weapons.First(w => w.FormKey.ID == Fo4WeapAssaultRifleId).AmmoCapacity = 20),
            ("laser rifle missing 00091FB5 OMOD", m => m.Weapons.First(w => w.FormKey.ID == Fo4WeapLaserRifleId).AmmoCapacity = 30),
            ("gauss rifle missing 001AC252 mag OMOD", m => m.Weapons.First(w => w.FormKey.ID == Fo4WeapGaussRifleId).AmmoCapacity = 5),
        })
        {
            var tMod = StarfieldMod.CreateFromBinary(plugArsOn, Release, new BinaryReadParameters
            {
                MasterFlagsLookup = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey) { new KeyedMasterStyle(SfEsm, MasterStyle.Full) }
            });
            mutateArs(tMod);
            var tDir = Path.Combine(scratchDir, "ars_tamper_" + label.Replace(' ', '_'));
            WriteMod(tMod, ModKey.FromFileName("FO4SFCoreValues.esm"), tDir);
            rejected = false;
            try { Check(Path.Combine(tDir, "FO4SFCoreValues.esm"), arsSfPath, arsOnOpts); }
            catch (Refusal) { rejected = true; }
            if (!rejected) throw new Refusal($"Check accepted tampered Arsenal record ({label})");
        }

        Console.WriteLine("CoreValues selftest: ok");
        return 0;
    }
}
