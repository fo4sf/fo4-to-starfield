// FortHagen: standalone runtime controller plugin (FO4SFFortHagen.esm) and read-only binary verifier for Fort Hagen's
// two elevator systems and exterior roof security gate (docs/mission/fort-hagen-elevators.md).
//
//   inspect <FO4Port.esm> <FO4TerrainCore.esm> [--json <out.json>]
//        verifies every placed Fort Hagen elevator door, button, panel, car static, stripped-XESP plank/blocker,
//        load-door VMAD bridge, exterior roof security gate, roof terminal, and persistent arrival marker across
//        FO4Port.esm (FO4Port_FortHagen01 / FO4Port_FortHagen02) and FO4TerrainCore.esm (Ext(-13,-1) / persistent cell).
//   write <Starfield.esm> <FO4Port.esm> <FO4TerrainCore.esm> <out dir> [--plugin FO4SFFortHagen.esm]
//        writes FO4SFFortHagen.esm mastered on Starfield.esm only (adds QUST 0x800 FO4SF_FortHagenElevators, overrides
//        nothing) with FO4SF_FortHagenQuest bound to the verified plugin-local form IDs and landing coordinates.
//   check <plugin> <Starfield.esm> <FO4Port.esm> <FO4TerrainCore.esm>
//        reads the plugin back and checks its header, master list, record counts, flags, and every bound VMAD property
//        against the verified Fort Hagen layout (exit 1 on any mismatch).
//   selftest <scratch dir>
//        builds synthetic Starfield.esm, FO4Port.esm, and FO4TerrainCore.esm plugins; runs inspect + write + check,
//        and verifies that missing records and tampered properties are rejected. No game file is read or modified.
using System.Globalization;
using System.Text;
using System.Text.Json;
using Mutagen.Bethesda;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Cache;
using Mutagen.Bethesda.Plugins.Records;
using Noggog;
using SF = Mutagen.Bethesda.Starfield;

if (args.Length == 0) return FortHagen.Usage();
try
{
    return args[0] switch
    {
        "inspect" when args.Length >= 3 => FortHagen.Inspect(args[1], args[2], FortHagen.ArgOrNull(args, "--json")),
        "write" when args.Length >= 5 => FortHagen.Write(args[1], args[2], args[3], args[4], FortHagen.Arg(args, "--plugin", FortHagen.Plugin)),
        "check" when args.Length >= 5 => FortHagen.Check(args[1], args[2], args[3], args[4]),
        "selftest" when args.Length >= 2 => FortHagen.SelfTest(args[1]),
        _ => FortHagen.Usage(),
    };
}
catch (FortHagen.Refusal e)
{
    Console.Error.WriteLine("refused: " + e.Message);
    return 2;
}

static class FortHagen
{
    public const string Plugin = "FO4SFFortHagen.esm";
    public const string PortPlugin = "FO4Port.esm", CorePlugin = "FO4TerrainCore.esm";
    public const string QuestEdid = "FO4SF_FortHagenElevators", ScriptName = "FO4SF_FortHagenQuest";
    public const string Cell01Edid = "FO4Port_FortHagen01", Cell02Edid = "FO4Port_FortHagen02";
    public const uint QuestId = 0x800;
    public const uint XMarkerId = 0x00003B, CocMarkerId = 0x000032;
    public const float MergeOffsetX = -1200f, MergeOffsetY = -2700f, PosTol = 0.25f;

    // Verified FO4Port.esm local IDs (FO4Port_FortHagen01 0x00BA4B & FO4Port_FortHagen02 0x00CFC6)
    public const uint Cell01Id = 0x00BA4B, Anchor01Id = 0x00C5E3;
    public const uint Car01Id = 0x00C580, InnerDoor01Id = 0x00C7AB, UpperDoor01Id = 0x00C7AC, LowerDoor01Id = 0x00C7B4;
    public const uint LowerCall01Id = 0x00C7AD, InnerPanel01Id = 0x00C7AE, UpperCall01Id = 0x00C7AF, MaintSwitch01Id = 0x00C7B0;
    public const uint Planks01Id = 0x00C641, BlockerDoor01Id = 0x00C7A8, BlockerBoards01Id = 0x00C13A, PostStageDoor01Id = 0x00C7B8;
    public const uint MidLoadDoor01Id = 0x00C7A7;

    public const uint Cell02Id = 0x00CFC6, Marker02Id = 0x00E182;
    public const uint Call02Id = 0x00DC5F, Panel02Id = 0x00DC62, OuterDoor02Id = 0x00DE52, LoadDoor02Id = 0x00DE53;
    public const uint MidLoadDoor02Id = 0x00DE51;

    // Verified FO4TerrainCore.esm local IDs (Ext(-13,-1) 0x000CE3 & persistent cell 0x001805)
    public const uint RoofMarkerId = 0x0A774C;
    public const uint RoofCallId = 0x0547AC, RoofPanelId = 0x0547AF, RoofOuterDoorId = 0x0547B1, RoofLoadDoorId = 0x0547B0;
    public const uint RoofGateId = 0x0232E1, RoofTermId = 0x0232E0;

    // Safe player landing spots verified against placed floor geometry:
    // - UpperLanding: centered on FO4Port_BldDecoSmFlrOnly01 (0x00BEC9 at -10.971, 65.829, 3.657), 1.46 m south of UpperDoor01
    // - LowerCar: inside FO4Port_UtilElevatorCar01 (0x00C580 at -10.971, 69.486, -3.657), facing south (180 deg) toward LowerDoor01
    public const float UpperLandingX = -10.971f, UpperLandingY = 66.200f, UpperLandingZ = 3.750f;
    public const float LowerCarX = -10.971f, LowerCarY = 69.000f, LowerCarZ = -3.550f;

    static readonly ModKey SfEsm = ModKey.FromFileName("Starfield.esm");

    public static readonly string[] MandatoryProperties =
    {
        "XMarkerBase",
        "Anchor01Id", "UpperCall01Id", "UpperCall01BaseId", "LowerCall01Id", "InnerPanel01Id", "InnerPanel01BaseId",
        "UpperDoor01Id", "LowerDoor01Id", "OuterDoor01BaseId", "InnerDoor01Id", "InnerDoor01BaseId",
        "Planks01Id", "Planks01BaseId", "BlockerDoor01Id", "BlockerDoor01BaseId", "BlockerBoards01Id", "BlockerBoards01BaseId",
        "MaintSwitch01Id", "MaintSwitch01BaseId",
        "UpperLandingX", "UpperLandingY", "UpperLandingZ", "LowerCarX", "LowerCarY", "LowerCarZ",
        "Marker02Id", "Call02Id", "Call02BaseId", "Panel02Id", "Panel02BaseId",
        "OuterDoor02Id", "OuterDoor02BaseId", "LoadDoor02Id", "LoadDoor02BaseId",
        "RoofMarkerId", "RoofCallId", "RoofCallBaseId", "RoofPanelId", "RoofPanelBaseId",
        "RoofOuterDoorId", "RoofOuterDoorBaseId", "RoofLoadDoorId", "RoofLoadDoorBaseId",
        "RoofGateId", "RoofGateBaseId", "RoofTermId", "RoofTermBaseId",
        "RoofCenterX", "RoofCenterY", "RoofCenterZ",
        "RoofGateX", "RoofGateY", "RoofGateZ",
        "RoofTermX", "RoofTermY", "RoofTermZ",
        "RoofCallX", "RoofCallY", "RoofCallZ",
        "RoofPanelX", "RoofPanelY", "RoofPanelZ",
        "RoofOuterDoorX", "RoofOuterDoorY", "RoofOuterDoorZ",
        "RoofLoadDoorX", "RoofLoadDoorY", "RoofLoadDoorZ",
    };

    public class Refusal(string m) : Exception(m);

    public static int Usage()
    {
        Console.Error.WriteLine("usage: see the header of dotnet/FortHagen/Program.cs (inspect | write | check | selftest)");
        return 2;
    }

    public static string? ArgOrNull(string[] a, string name)
    {
        int i = Array.IndexOf(a, name);
        return i >= 0 && i + 1 < a.Length ? a[i + 1] : null;
    }

    public static string Arg(string[] a, string name, string dflt) => ArgOrNull(a, name) ?? dflt;
    static string F(float v) => v.ToString("0.###", CultureInfo.InvariantCulture);

    static List<string> MasterNames(string path)
    {
        using var f = File.OpenRead(path);
        var h = new byte[24];
        if (f.Read(h, 0, 24) != 24 || Encoding.ASCII.GetString(h, 0, 4) != "TES4")
            throw new Refusal($"{path} is not a plugin (no TES4 record)");
        int size = BitConverter.ToInt32(h, 4);
        var data = new byte[size];
        f.ReadExactly(data, 0, size);
        var names = new List<string>();
        for (int p = 0; p + 6 <= size;)
        {
            string sig = Encoding.ASCII.GetString(data, p, 4);
            int len = BitConverter.ToUInt16(data, p + 4);
            p += 6;
            if (sig == "MAST") names.Add(Encoding.UTF8.GetString(data, p, Math.Max(0, len - 1)));
            p += len;
        }
        return names;
    }

    static SF.IStarfieldModDisposableGetter OpenMod(string path)
    {
        var styles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        styles.Set(new KeyedMasterStyle(SfEsm, MasterStyle.Full));
        foreach (var m in MasterNames(path)) styles.Set(new KeyedMasterStyle(ModKey.FromFileName(m), MasterStyle.Full));
        return SF.StarfieldMod.CreateFromBinaryOverlay(path, SF.StarfieldRelease.Starfield, new BinaryReadParameters { MasterFlagsLookup = styles });
    }

    public sealed record RefInfo(uint RefId, uint BaseId, float X, float Y, float Z, bool Persistent);

    public sealed record Layout(
        RefInfo Anchor01, RefInfo Car01, RefInfo UpperCall01, RefInfo LowerCall01, RefInfo InnerPanel01,
        RefInfo UpperDoor01, RefInfo LowerDoor01, RefInfo InnerDoor01,
        RefInfo Planks01, RefInfo BlockerDoor01, RefInfo BlockerBoards01, RefInfo MaintSwitch01,
        RefInfo Marker02, RefInfo Call02, RefInfo Panel02, RefInfo OuterDoor02, RefInfo LoadDoor02,
        RefInfo RoofMarker, RefInfo RoofCall, RefInfo RoofPanel, RefInfo RoofOuterDoor, RefInfo RoofLoadDoor,
        RefInfo RoofGate, RefInfo RoofTerm);

    static Dictionary<uint, SF.IPlacedObjectGetter> IndexPlaced(SF.IStarfieldModGetter mod)
    {
        var map = new Dictionary<uint, SF.IPlacedObjectGetter>();
        foreach (var r in mod.EnumerateMajorRecords<SF.IPlacedObjectGetter>())
            if (r.FormKey.ModKey == mod.ModKey)
                map[r.FormKey.ID] = r;
        return map;
    }

    static RefInfo RequireRef(Dictionary<uint, SF.IPlacedObjectGetter> map, ModKey owner, uint id, string label)
    {
        if (!map.TryGetValue(id, out var r))
            throw new Refusal($"{owner.FileName}: missing {label} REFR 0x{id:X6}");
        if ((r.MajorRecordFlagsRaw & 0x00000800) != 0)
            throw new Refusal($"{owner.FileName}: {label} REFR 0x{id:X6} is initially disabled");
        var baseKey = r.Base.FormKey;
        var pos = r.Position;
        bool persistent = r.MajorRecordFlagsRaw != 0 && (r.MajorRecordFlagsRaw & 0x00000400) != 0;
        return new RefInfo(id, baseKey.ID, pos.X, pos.Y, pos.Z, persistent);
    }

    static void CheckLoadDoorVmad(Dictionary<uint, SF.IPlacedObjectGetter> map, uint refId, string wantScript, string wantDestPlugin, uint wantDestId, string label)
    {
        var r = map[refId];
        var s = r.VirtualMachineAdapter?.Scripts.FirstOrDefault(x => x.Name == wantScript)
                ?? throw new Refusal($"{label} 0x{refId:X6} does not carry VMAD script {wantScript}");
        var props = s.Properties.ToDictionary(p => p.Name);
        if (!props.TryGetValue("DestinationPlugin", out var dp) || dp is not SF.IScriptStringPropertyGetter dsp || dsp.Data != wantDestPlugin)
            throw new Refusal($"{label} 0x{refId:X6} DestinationPlugin is not {wantDestPlugin}");
        if (!props.TryGetValue("DestinationId", out var di) || di is not SF.IScriptIntPropertyGetter dip || (uint)dip.Data != wantDestId)
            throw new Refusal($"{label} 0x{refId:X6} DestinationId is not 0x{wantDestId:X6}");
        if (!props.TryGetValue("UseDestinationPosition", out var up) || up is not SF.IScriptBoolPropertyGetter ubp || !ubp.Data)
            throw new Refusal($"{label} 0x{refId:X6} UseDestinationPosition is not true");
    }

    public static Layout Resolve(string portPath, string corePath)
    {
        using var port = OpenMod(portPath);
        using var core = OpenMod(corePath);

        var c01 = port.EnumerateMajorRecords<SF.ICellGetter>().FirstOrDefault(c => c.FormKey.ID == Cell01Id && c.EditorID == Cell01Edid)
                  ?? throw new Refusal($"{PortPlugin}: missing cell {Cell01Edid} 0x{Cell01Id:X6}");
        var c02 = port.EnumerateMajorRecords<SF.ICellGetter>().FirstOrDefault(c => c.FormKey.ID == Cell02Id && c.EditorID == Cell02Edid)
                  ?? throw new Refusal($"{PortPlugin}: missing cell {Cell02Edid} 0x{Cell02Id:X6}");
        _ = c01; _ = c02;

        var pMap = IndexPlaced(port);
        var cMap = IndexPlaced(core);

        var anchor01 = RequireRef(pMap, port.ModKey, Anchor01Id, "FortHagen01 COC marker");
        if (!anchor01.Persistent || anchor01.BaseId != CocMarkerId)
            throw new Refusal($"{PortPlugin}: Anchor01 0x{Anchor01Id:X6} must be persistent COCMarkerHeading 0x{CocMarkerId:X6}");

        var car01 = RequireRef(pMap, port.ModKey, Car01Id, "FortHagen01 elevator car STAT");
        var upperCall01 = RequireRef(pMap, port.ModKey, UpperCall01Id, "FortHagen01 upper call button");
        var lowerCall01 = RequireRef(pMap, port.ModKey, LowerCall01Id, "FortHagen01 lower call button");
        var innerPanel01 = RequireRef(pMap, port.ModKey, InnerPanel01Id, "FortHagen01 inner lift panel");
        var upperDoor01 = RequireRef(pMap, port.ModKey, UpperDoor01Id, "FortHagen01 upper outer door");
        var lowerDoor01 = RequireRef(pMap, port.ModKey, LowerDoor01Id, "FortHagen01 lower outer door");
        var innerDoor01 = RequireRef(pMap, port.ModKey, InnerDoor01Id, "FortHagen01 inner car door");
        var planks01 = RequireRef(pMap, port.ModKey, Planks01Id, "FortHagen01 upper doorway planks");
        var blockerDoor01 = RequireRef(pMap, port.ModKey, BlockerDoor01Id, "FortHagen01 pre-stage-10 blocker door");
        var blockerBoards01 = RequireRef(pMap, port.ModKey, BlockerBoards01Id, "FortHagen01 pre-stage-10 blocker boards");
        var postDoor01 = RequireRef(pMap, port.ModKey, PostStageDoor01Id, "FortHagen01 post-stage-10 door");
        var maintSwitch01 = RequireRef(pMap, port.ModKey, MaintSwitch01Id, "FortHagen01 maintenance switch");
        var midDoor01 = RequireRef(pMap, port.ModKey, MidLoadDoor01Id, "FortHagen01->02 load door");
        _ = postDoor01; _ = midDoor01;

        if (upperCall01.BaseId != lowerCall01.BaseId)
            throw new Refusal("FortHagen01 upper and lower call buttons do not share the same ACTI base");
        if (upperDoor01.BaseId != lowerDoor01.BaseId)
            throw new Refusal("FortHagen01 upper and lower outer doors do not share the same DOOR base");
        if (car01.Z > -2.0f || upperDoor01.Z < 2.0f)
            throw new Refusal($"FortHagen01 shaft heights unexpected: car z={F(car01.Z)}, upper door z={F(upperDoor01.Z)}");

        var marker02 = RequireRef(pMap, port.ModKey, Marker02Id, "FortHagen02 persistent arrival marker");
        if (!marker02.Persistent || marker02.BaseId != XMarkerId)
            throw new Refusal($"{PortPlugin}: Marker02 0x{Marker02Id:X6} must be persistent XMarker 0x{XMarkerId:X6}");
        var call02 = RequireRef(pMap, port.ModKey, Call02Id, "FortHagen02 call button");
        var panel02 = RequireRef(pMap, port.ModKey, Panel02Id, "FortHagen02 inner lift panel");
        var outerDoor02 = RequireRef(pMap, port.ModKey, OuterDoor02Id, "FortHagen02 outer elevator door");
        var loadDoor02 = RequireRef(pMap, port.ModKey, LoadDoor02Id, "FortHagen02 animated load door");
        var midDoor02 = RequireRef(pMap, port.ModKey, MidLoadDoor02Id, "FortHagen02->01 load door");
        _ = midDoor02;
        CheckLoadDoorVmad(pMap, LoadDoor02Id, "FO4SF_AnimatedLoadDoor", CorePlugin, RoofMarkerId, "FortHagen02 load door");

        var roofMarker = RequireRef(cMap, core.ModKey, RoofMarkerId, "FortHagen roof persistent arrival marker");
        if (!roofMarker.Persistent || roofMarker.BaseId != XMarkerId)
            throw new Refusal($"{CorePlugin}: RoofMarker 0x{RoofMarkerId:X6} must be persistent XMarker 0x{XMarkerId:X6}");
        var roofCall = RequireRef(cMap, core.ModKey, RoofCallId, "FortHagen roof call button");
        var roofPanel = RequireRef(cMap, core.ModKey, RoofPanelId, "FortHagen roof inner panel");
        var roofOuterDoor = RequireRef(cMap, core.ModKey, RoofOuterDoorId, "FortHagen roof outer door");
        var roofLoadDoor = RequireRef(cMap, core.ModKey, RoofLoadDoorId, "FortHagen roof inner load door");
        var roofGate = RequireRef(cMap, core.ModKey, RoofGateId, "FortHagen roof security gate");
        var roofTerm = RequireRef(cMap, core.ModKey, RoofTermId, "FortHagen roof exit terminal");
        CheckLoadDoorVmad(cMap, RoofLoadDoorId, "FO4SF_LoadDoor", PortPlugin, Marker02Id, "FortHagen roof load door");

        return new Layout(
            anchor01, car01, upperCall01, lowerCall01, innerPanel01, upperDoor01, lowerDoor01, innerDoor01,
            planks01, blockerDoor01, blockerBoards01, maintSwitch01,
            marker02, call02, panel02, outerDoor02, loadDoor02,
            roofMarker, roofCall, roofPanel, roofOuterDoor, roofLoadDoor, roofGate, roofTerm);
    }

    public static List<(string Name, object Value)> ScalarProperties(Layout l) => new()
    {
        ("Anchor01Id", (int)l.Anchor01.RefId),
        ("UpperCall01Id", (int)l.UpperCall01.RefId),
        ("UpperCall01BaseId", (int)l.UpperCall01.BaseId),
        ("LowerCall01Id", (int)l.LowerCall01.RefId),
        ("InnerPanel01Id", (int)l.InnerPanel01.RefId),
        ("InnerPanel01BaseId", (int)l.InnerPanel01.BaseId),
        ("UpperDoor01Id", (int)l.UpperDoor01.RefId),
        ("LowerDoor01Id", (int)l.LowerDoor01.RefId),
        ("OuterDoor01BaseId", (int)l.UpperDoor01.BaseId),
        ("InnerDoor01Id", (int)l.InnerDoor01.RefId),
        ("InnerDoor01BaseId", (int)l.InnerDoor01.BaseId),
        ("Planks01Id", (int)l.Planks01.RefId),
        ("Planks01BaseId", (int)l.Planks01.BaseId),
        ("BlockerDoor01Id", (int)l.BlockerDoor01.RefId),
        ("BlockerDoor01BaseId", (int)l.BlockerDoor01.BaseId),
        ("BlockerBoards01Id", (int)l.BlockerBoards01.RefId),
        ("BlockerBoards01BaseId", (int)l.BlockerBoards01.BaseId),
        ("MaintSwitch01Id", (int)l.MaintSwitch01.RefId),
        ("MaintSwitch01BaseId", (int)l.MaintSwitch01.BaseId),
        ("UpperLandingX", UpperLandingX),
        ("UpperLandingY", UpperLandingY),
        ("UpperLandingZ", UpperLandingZ),
        ("LowerCarX", LowerCarX),
        ("LowerCarY", LowerCarY),
        ("LowerCarZ", LowerCarZ),
        ("Marker02Id", (int)l.Marker02.RefId),
        ("Call02Id", (int)l.Call02.RefId),
        ("Call02BaseId", (int)l.Call02.BaseId),
        ("Panel02Id", (int)l.Panel02.RefId),
        ("Panel02BaseId", (int)l.Panel02.BaseId),
        ("OuterDoor02Id", (int)l.OuterDoor02.RefId),
        ("OuterDoor02BaseId", (int)l.OuterDoor02.BaseId),
        ("LoadDoor02Id", (int)l.LoadDoor02.RefId),
        ("LoadDoor02BaseId", (int)l.LoadDoor02.BaseId),
        ("RoofMarkerId", (int)l.RoofMarker.RefId),
        ("RoofCallId", (int)l.RoofCall.RefId),
        ("RoofCallBaseId", (int)l.RoofCall.BaseId),
        ("RoofPanelId", (int)l.RoofPanel.RefId),
        ("RoofPanelBaseId", (int)l.RoofPanel.BaseId),
        ("RoofOuterDoorId", (int)l.RoofOuterDoor.RefId),
        ("RoofOuterDoorBaseId", (int)l.RoofOuterDoor.BaseId),
        ("RoofLoadDoorId", (int)l.RoofLoadDoor.RefId),
        ("RoofLoadDoorBaseId", (int)l.RoofLoadDoor.BaseId),
        ("RoofGateId", (int)l.RoofGate.RefId),
        ("RoofGateBaseId", (int)l.RoofGate.BaseId),
        ("RoofTermId", (int)l.RoofTerm.RefId),
        ("RoofTermBaseId", (int)l.RoofTerm.BaseId),
        ("RoofCenterX", l.RoofMarker.X + MergeOffsetX),
        ("RoofCenterY", l.RoofMarker.Y + MergeOffsetY),
        ("RoofCenterZ", l.RoofMarker.Z),
        ("RoofGateX", l.RoofGate.X + MergeOffsetX),
        ("RoofGateY", l.RoofGate.Y + MergeOffsetY),
        ("RoofGateZ", l.RoofGate.Z),
        ("RoofTermX", l.RoofTerm.X + MergeOffsetX),
        ("RoofTermY", l.RoofTerm.Y + MergeOffsetY),
        ("RoofTermZ", l.RoofTerm.Z),
        ("RoofCallX", l.RoofCall.X + MergeOffsetX),
        ("RoofCallY", l.RoofCall.Y + MergeOffsetY),
        ("RoofCallZ", l.RoofCall.Z),
        ("RoofPanelX", l.RoofPanel.X + MergeOffsetX),
        ("RoofPanelY", l.RoofPanel.Y + MergeOffsetY),
        ("RoofPanelZ", l.RoofPanel.Z),
        ("RoofOuterDoorX", l.RoofOuterDoor.X + MergeOffsetX),
        ("RoofOuterDoorY", l.RoofOuterDoor.Y + MergeOffsetY),
        ("RoofOuterDoorZ", l.RoofOuterDoor.Z),
        ("RoofLoadDoorX", l.RoofLoadDoor.X + MergeOffsetX),
        ("RoofLoadDoorY", l.RoofLoadDoor.Y + MergeOffsetY),
        ("RoofLoadDoorZ", l.RoofLoadDoor.Z),
    };

    public static int Inspect(string portPath, string corePath, string? jsonOut)
    {
        var l = Resolve(portPath, corePath);
        Console.WriteLine($"inspect: ok ({Cell01Edid} anchor 0x{l.Anchor01.RefId:X6}, planks 0x{l.Planks01.RefId:X6}, upper/lower doors 0x{l.UpperDoor01.RefId:X6}/0x{l.LowerDoor01.RefId:X6}; " +
                          $"{Cell02Edid} load door 0x{l.LoadDoor02.RefId:X6} <-> roof 0x{l.RoofLoadDoor.RefId:X6}; roof gate 0x{l.RoofGate.RefId:X6}, terminal 0x{l.RoofTerm.RefId:X6})");
        if (jsonOut is not null)
        {
            var dir = Path.GetDirectoryName(Path.GetFullPath(jsonOut));
            if (!string.IsNullOrEmpty(dir)) Directory.CreateDirectory(dir);
            var payload = new Dictionary<string, object>
            {
                ["port_plugin"] = PortPlugin,
                ["core_plugin"] = CorePlugin,
                ["merge_offset"] = new[] { MergeOffsetX, MergeOffsetY, 0f },
                ["upper_landing"] = new[] { UpperLandingX, UpperLandingY, UpperLandingZ },
                ["lower_car"] = new[] { LowerCarX, LowerCarY, LowerCarZ },
                ["properties"] = ScalarProperties(l).ToDictionary(p => p.Name, p => p.Value),
            };
            File.WriteAllText(jsonOut, JsonSerializer.Serialize(payload, new JsonSerializerOptions { WriteIndented = true }));
        }
        return 0;
    }

    public static int Write(string sfPath, string portPath, string corePath, string outDir, string pluginName)
    {
        var l = Resolve(portPath, corePath);
        using var sf = OpenMod(sfPath);
        var xmarker = sf.Statics.FirstOrDefault(s => s.FormKey == new FormKey(SfEsm, XMarkerId))
                      ?? throw new Refusal($"Starfield.esm: missing XMarker STAT 0x{XMarkerId:X6}");

        var rel = SF.StarfieldRelease.Starfield;
        var modKey = ModKey.FromFileName(pluginName);
        var mod = new SF.StarfieldMod(modKey, rel);
        mod.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Master;
        mod.ModHeader.Author = "fo4-to-starfield FortHagen";

        var quest = new SF.Quest(new FormKey(modKey, QuestId), rel)
        {
            EditorID = QuestEdid,
            FormVersion = 581,
            Version2 = 12,
            Data = new SF.QuestData { Flags = SF.Quest.Flag.StartGameEnabled, Priority = 50 },
        };

        var script = new SF.ScriptEntry { Name = ScriptName, Flags = SF.ScriptEntry.Flag.Local };
        script.Properties.Add(new SF.ScriptObjectProperty
        {
            Name = "XMarkerBase",
            Flags = SF.ScriptProperty.Flag.Edited,
            Object = new FormLink<SF.IStarfieldMajorRecordGetter>(xmarker.FormKey),
            Alias = -1,
            Unused = 0,
        });
        foreach (var (name, val) in ScalarProperties(l))
        {
            if (val is int iv)
                script.Properties.Add(new SF.ScriptIntProperty { Name = name, Flags = SF.ScriptProperty.Flag.Edited, Data = iv });
            else if (val is float fv)
                script.Properties.Add(new SF.ScriptFloatProperty { Name = name, Flags = SF.ScriptProperty.Flag.Edited, Data = fv });
            else
                throw new Refusal($"unsupported property type for {name}");
        }

        var vm = new SF.QuestAdapter
        {
            Version = 6,
            ObjectFormat = 2,
            ExtraBindDataVersion = 3,
            Script = new SF.ScriptEntry { Name = "", Flags = SF.ScriptEntry.Flag.Local },
        };
        vm.Scripts.Add(script);
        quest.VirtualMachineAdapter = vm;
        mod.Quests.Add(quest);
        mod.ModHeader.Stats.NextFormID = QuestId + 1;

        Directory.CreateDirectory(outDir);
        var outPath = Path.Combine(outDir, pluginName);
        mod.BeginWrite.ToPath(outPath).WithLoadOrder(SfEsm).WithKnownMasters(new KeyedMasterStyle(SfEsm, MasterStyle.Full)).Write();
        Console.WriteLine($"wrote {outPath} ({new FileInfo(outPath).Length:N0} bytes): QUST {QuestEdid} ({script.Properties.Count} properties)");
        return 0;
    }

    public static int Check(string pluginPath, string sfPath, string portPath, string corePath)
    {
        var problems = new List<string>();
        void Need(bool ok, string msg) { if (!ok) problems.Add(msg); }

        var l = Resolve(portPath, corePath);
        using var sf = OpenMod(sfPath);
        Need(sf.Statics.Any(s => s.FormKey == new FormKey(SfEsm, XMarkerId)), $"Starfield.esm missing XMarker 0x{XMarkerId:X6}");

        using var plug = OpenMod(pluginPath);
        var key = plug.ModKey;
        var masters = plug.ModHeader.MasterReferences.Select(m => m.Master.FileName.String).ToList();
        Console.WriteLine($"{key}: flags={plug.ModHeader.Flags}, masters=[{string.Join(", ", masters)}], quests={plug.Quests.Count}");

        Need(plug.ModHeader.Flags.HasFlag(SF.StarfieldModHeader.HeaderFlag.Master), "plugin header lacks Master flag");
        Need(masters.SequenceEqual(new[] { "Starfield.esm" }), $"masters [{string.Join(", ", masters)}] must be [Starfield.esm] only");
        Need(plug.Quests.Count == 1 && plug.Cells.Count == 0 && plug.Worldspaces.Count == 0 && plug.Npcs.Count == 0,
             "plugin must contain exactly 1 QUST and zero CELL/WRLD/NPC_ records");
        Need(plug.EnumerateMajorRecords().All(r => r.FormKey.ModKey == key), "plugin overrides a master record");

        var q = plug.Quests.FirstOrDefault(x => x.FormKey == new FormKey(key, QuestId));
        if (q is null) problems.Add("missing QUST 0x800");
        else
        {
            Need(q.EditorID == QuestEdid, $"QUST EditorID {q.EditorID} != {QuestEdid}");
            Need(q.Data is not null && q.Data.Flags.HasFlag(SF.Quest.Flag.StartGameEnabled) && !q.Data.Flags.HasFlag(SF.Quest.Flag.RunOnce) &&
                 !q.Data.Flags.HasFlag(SF.Quest.Flag.DisplaysInHud),
                 "QUST flags must be StartGameEnabled without RunOnce or DisplaysInHud");
            var vm = q.VirtualMachineAdapter;
            Need(vm is not null && vm.Version == 6 && vm.ObjectFormat == 2, "VMAD version/objectFormat must be 6/2");
            var s = vm?.Scripts.FirstOrDefault(x => x.Name == ScriptName);
            if (s is null) problems.Add($"script {ScriptName} not attached");
            else
            {
                var names = s.Properties.Select(p => p.Name).ToList();
                Need(names.SequenceEqual(MandatoryProperties), $"script property list mismatch ({names.Count} vs {MandatoryProperties.Length})");
                var byName = s.Properties.ToDictionary(p => p.Name);
                Need(byName.TryGetValue("XMarkerBase", out var xm) && xm is SF.IScriptObjectPropertyGetter xmo &&
                     xmo.Object.FormKey == new FormKey(SfEsm, XMarkerId), "XMarkerBase not bound to Starfield.esm:00003B");
                foreach (var (name, val) in ScalarProperties(l))
                {
                    if (val is int iv)
                        Need(byName.TryGetValue(name, out var p) && p is SF.IScriptIntPropertyGetter ip && ip.Data == iv,
                             $"int property {name} != {iv}");
                    else if (val is float fv)
                        Need(byName.TryGetValue(name, out var p) && p is SF.IScriptFloatPropertyGetter fp && MathF.Abs(fp.Data - fv) <= 1e-3f,
                             $"float property {name} != {F(fv)}");
                }
            }
        }

        if (problems.Count > 0)
        {
            foreach (var p in problems) Console.Error.WriteLine("check failed: " + p);
            return 1;
        }
        Console.WriteLine("check: ok");
        return 0;
    }

    // ---------------------------------------------------------------- selftest

    static SF.PlacedObject AddRef(SF.Cell cell, ModKey modKey, uint refId, FormKey baseKey, float x, float y, float z, bool persistent = false)
    {
        var r = new SF.PlacedObject(new FormKey(modKey, refId), SF.StarfieldRelease.Starfield)
        {
            Position = new P3Float(x, y, z),
        };
        r.Base.SetTo(baseKey);
        if (persistent)
        {
            r.MajorRecordFlagsRaw |= 0x00000400;
            cell.Persistent.Add(r);
        }
        else
        {
            cell.Temporary.Add(r);
        }
        return r;
    }

    static void AttachLoadDoor(SF.PlacedObject r, string scriptName, string destPlugin, uint destId, float dx, float dy, float dz, float? openSec = null)
    {
        var s = new SF.ScriptEntry { Name = scriptName, Flags = SF.ScriptEntry.Flag.Local };
        s.Properties.Add(new SF.ScriptStringProperty { Name = "DestinationPlugin", Flags = SF.ScriptProperty.Flag.Edited, Data = destPlugin });
        s.Properties.Add(new SF.ScriptIntProperty { Name = "DestinationId", Flags = SF.ScriptProperty.Flag.Edited, Data = (int)destId });
        s.Properties.Add(new SF.ScriptFloatProperty { Name = "DestinationX", Flags = SF.ScriptProperty.Flag.Edited, Data = dx });
        s.Properties.Add(new SF.ScriptFloatProperty { Name = "DestinationY", Flags = SF.ScriptProperty.Flag.Edited, Data = dy });
        s.Properties.Add(new SF.ScriptFloatProperty { Name = "DestinationZ", Flags = SF.ScriptProperty.Flag.Edited, Data = dz });
        s.Properties.Add(new SF.ScriptBoolProperty { Name = "UseDestinationPosition", Flags = SF.ScriptProperty.Flag.Edited, Data = true });
        if (openSec is { } os)
            s.Properties.Add(new SF.ScriptFloatProperty { Name = "OpenSeconds", Flags = SF.ScriptProperty.Flag.Edited, Data = os });
        var vm = new SF.VirtualMachineAdapter { Version = 6, ObjectFormat = 2 };
        vm.Scripts.Add(s);
        r.VirtualMachineAdapter = vm;
    }

    static (string SfPath, string PortPath, string CorePath) BuildFixtures(string dir)
    {
        Directory.CreateDirectory(dir);
        var rel = SF.StarfieldRelease.Starfield;

        // 1. Synthetic Starfield.esm
        var sf = new SF.StarfieldMod(SfEsm, rel);
        sf.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Master;
        sf.Statics.Add(new SF.Static(new FormKey(SfEsm, CocMarkerId), rel) { EditorID = "COCMarkerHeading" });
        sf.Statics.Add(new SF.Static(new FormKey(SfEsm, XMarkerId), rel) { EditorID = "XMarker" });
        sf.ModHeader.Stats.NextFormID = 0x800;
        var sfPath = Path.Combine(dir, "Starfield.esm");
        sf.BeginWrite.ToPath(sfPath).WithNoLoadOrder().NoCheckIfLowerRangeDisallowed().Write();

        // 2. Synthetic FO4Port.esm
        var portKey = ModKey.FromFileName(PortPlugin);
        var port = new SF.StarfieldMod(portKey, rel);
        port.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Master;
        var bCar = new SF.Static(new FormKey(portKey, 0x000BF8), rel) { EditorID = "FO4Port_UtilElevatorCar01" };
        var bPlanks = new SF.Static(new FormKey(portKey, 0x0010BE), rel) { EditorID = "FO4Port_DebrisInteriorWoodWindowBoards02" };
        var bBoards = new SF.Static(new FormKey(portKey, 0x0010BF), rel) { EditorID = "FO4Port_DebrisInteriorWoodWindowBoards03" };
        port.Statics.Add(bCar); port.Statics.Add(bPlanks); port.Statics.Add(bBoards);
        var bDoorIn = new SF.Door(new FormKey(portKey, 0x00DE5E), rel) { EditorID = "FO4Port_utilmetalelevatorin01" };
        var bDoorOut = new SF.Door(new FormKey(portKey, 0x00DE5F), rel) { EditorID = "FO4Port_UtilMetalElevatorOut01" };
        var bDoorBlk = new SF.Door(new FormKey(portKey, 0x0066B4), rel) { EditorID = "FO4Port_IndMetalDoor01" };
        var bDoorPost = new SF.Door(new FormKey(portKey, 0x0066B5), rel) { EditorID = "FO4Port_IndMetalDoor02" };
        var bDoorMid = new SF.Door(new FormKey(portKey, 0x00CDFF), rel) { EditorID = "FO4Port_utilmetaldbdoorload01" };
        port.Doors.Add(bDoorIn); port.Doors.Add(bDoorOut); port.Doors.Add(bDoorBlk); port.Doors.Add(bDoorPost); port.Doors.Add(bDoorMid);
        var bCall01 = new SF.Activator(new FormKey(portKey, 0x00E008), rel) { EditorID = "FO4Port_acti_0a2784_fallout4" };
        var bPanel01 = new SF.Activator(new FormKey(portKey, 0x00E009), rel) { EditorID = "FO4Port_acti_0a2785_fallout4" };
        var bMaint = new SF.Activator(new FormKey(portKey, 0x00E00A), rel) { EditorID = "FO4Port_acti_0a285b_fallout4" };
        var bCall02 = new SF.Activator(new FormKey(portKey, 0x00E03E), rel) { EditorID = "FO4Port_acti_09dc99_fallout4" };
        var bPanel02 = new SF.Activator(new FormKey(portKey, 0x00E03F), rel) { EditorID = "FO4Port_acti_09c020_fallout4" };
        port.Activators.Add(bCall01); port.Activators.Add(bPanel01); port.Activators.Add(bMaint); port.Activators.Add(bCall02); port.Activators.Add(bPanel02);

        var c01 = new SF.Cell(new FormKey(portKey, Cell01Id), rel) { EditorID = Cell01Edid, Flags = SF.Cell.Flag.IsInteriorCell };
        AddRef(c01, portKey, Anchor01Id, new FormKey(SfEsm, CocMarkerId), 10.389f, 44.161f, 7.329f, persistent: true);
        AddRef(c01, portKey, Car01Id, bCar.FormKey, -10.971f, 69.486f, -3.657f);
        AddRef(c01, portKey, InnerDoor01Id, bDoorIn.FormKey, -10.971f, 69.486f, -3.657f);
        AddRef(c01, portKey, UpperDoor01Id, bDoorOut.FormKey, -10.971f, 67.657f, 3.657f);
        AddRef(c01, portKey, LowerDoor01Id, bDoorOut.FormKey, -10.971f, 67.657f, -3.657f);
        AddRef(c01, portKey, LowerCall01Id, bCall01.FormKey, -9.921f, 67.429f, -2.405f);
        AddRef(c01, portKey, InnerPanel01Id, bPanel01.FormKey, -11.882f, 68.037f, -2.405f);
        AddRef(c01, portKey, UpperCall01Id, bCall01.FormKey, -11.986f, 67.419f, 4.905f);
        AddRef(c01, portKey, MaintSwitch01Id, bMaint.FormKey, -9.829f, 67.886f, -2.946f);
        AddRef(c01, portKey, Planks01Id, bPlanks.FormKey, -10.971f, 67.429f, 5.029f);
        AddRef(c01, portKey, BlockerDoor01Id, bDoorBlk.FormKey, -10.784f, 54.720f, -2.457f);
        AddRef(c01, portKey, BlockerBoards01Id, bBoards.FormKey, -8.927f, 54.815f, -2.239f);
        AddRef(c01, portKey, PostStageDoor01Id, bDoorPost.FormKey, -7.502f, 56.366f, -2.457f);
        AddRef(c01, portKey, MidLoadDoor01Id, bDoorMid.FormKey, -9.143f, 43.886f, -10.971f, persistent: true);

        var c02 = new SF.Cell(new FormKey(portKey, Cell02Id), rel) { EditorID = Cell02Edid, Flags = SF.Cell.Flag.IsInteriorCell };
        AddRef(c02, portKey, Marker02Id, new FormKey(SfEsm, XMarkerId), 19.958f, 1.334f, -10.971f, persistent: true);
        AddRef(c02, portKey, Call02Id, bCall02.FormKey, 20.796f, 2.502f, -9.554f);
        AddRef(c02, portKey, Panel02Id, bPanel02.FormKey, 21.410f, 2.314f, -9.554f);
        AddRef(c02, portKey, OuterDoor02Id, bDoorOut.FormKey, 21.029f, 1.371f, -10.971f);
        var ld02 = AddRef(c02, portKey, LoadDoor02Id, bDoorIn.FormKey, 22.857f, 1.371f, -10.971f);
        AttachLoadDoor(ld02, "FO4SF_AnimatedLoadDoor", CorePlugin, RoofMarkerId, -2470.491f, -2774.755f, 95.086f, 1.3333f);
        AddRef(c02, portKey, MidLoadDoor02Id, bDoorMid.FormKey, -55.314f, 19.200f, -7.314f, persistent: true);

        var blk = new SF.CellBlock { BlockNumber = 0, GroupType = SF.GroupTypeEnum.InteriorCellBlock };
        var sub = new SF.CellSubBlock { BlockNumber = 0, GroupType = SF.GroupTypeEnum.InteriorCellSubBlock };
        sub.Cells.Add(c01); sub.Cells.Add(c02);
        blk.SubBlocks.Add(sub);
        port.Cells.Add(blk);

        var portPath = Path.Combine(dir, PortPlugin);
        port.BeginWrite.ToPath(portPath).WithLoadOrder(SfEsm).WithKnownMasters(new KeyedMasterStyle(SfEsm, MasterStyle.Full)).Write();

        // 3. Synthetic FO4TerrainCore.esm
        var coreKey = ModKey.FromFileName(CorePlugin);
        var core = new SF.StarfieldMod(coreKey, rel);
        core.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Master;
        var bRoofOut = new SF.Door(new FormKey(coreKey, 0x002C08), rel) { EditorID = "FO4Core_utilmetalelevatorout01" };
        core.Doors.Add(bRoofOut);
        var bRoofIn = new SF.Activator(new FormKey(coreKey, 0x0A7757), rel) { EditorID = "FO4Core_door_09c01f_fallout4" };
        var bRoofCall = new SF.Activator(new FormKey(coreKey, 0x0A2D93), rel) { EditorID = "FO4Core_acti_09dc99_fallout4" };
        var bRoofPanel = new SF.Activator(new FormKey(coreKey, 0x0A2D92), rel) { EditorID = "FO4Core_acti_09c020_fallout4" };
        var bRoofGate = new SF.Activator(new FormKey(coreKey, 0x0A2D9C), rel) { EditorID = "FO4Core_acti_0bb48b_fallout4" };
        core.Activators.Add(bRoofIn); core.Activators.Add(bRoofCall); core.Activators.Add(bRoofPanel); core.Activators.Add(bRoofGate);
        var bRoofTerm = new SF.Terminal(new FormKey(coreKey, 0x0A2E3F), rel) { EditorID = "FO4Core_term_0bf415_fallout4" };
        core.Terminals.Add(bRoofTerm);

        var world = new SF.Worldspace(new FormKey(coreKey, 0x000803), rel) { EditorID = "FO4Core_Commonwealth" };
        var topCell = new SF.Cell(new FormKey(coreKey, 0x001805), rel);
        AddRef(topCell, coreKey, RoofMarkerId, new FormKey(SfEsm, XMarkerId), -1270.491f, -74.755f, 95.086f, persistent: true);
        world.TopCell = topCell;

        var extCell = new SF.Cell(new FormKey(coreKey, 0x000CE3), rel) { Grid = new SF.CellGrid { Point = new P2Int(-13, -1) } };
        AddRef(extCell, coreKey, RoofCallId, bRoofCall.FormKey, -1271.531f, -73.779f, 96.503f);
        AddRef(extCell, coreKey, RoofPanelId, bRoofPanel.FormKey, -1271.342f, -73.165f, 96.503f);
        AddRef(extCell, coreKey, RoofOuterDoorId, bRoofOut.FormKey, -1270.400f, -73.546f, 95.086f);
        var rld = AddRef(extCell, coreKey, RoofLoadDoorId, bRoofIn.FormKey, -1270.400f, -71.718f, 95.086f);
        AttachLoadDoor(rld, "FO4SF_LoadDoor", PortPlugin, Marker02Id, 19.958f, 1.334f, -10.971f);
        AddRef(extCell, coreKey, RoofGateId, bRoofGate.FormKey, -1270.400f, -81.432f, 95.086f);
        AddRef(extCell, coreKey, RoofTermId, bRoofTerm.FormKey, -1271.657f, -81.318f, 95.086f);

        var wSub = new SF.WorldspaceSubBlock { BlockNumberX = -2, BlockNumberY = -1, GroupType = SF.GroupTypeEnum.ExteriorCellSubBlock };
        wSub.Items.Add(extCell);
        var wBlk = new SF.WorldspaceBlock { BlockNumberX = -1, BlockNumberY = -1, GroupType = SF.GroupTypeEnum.ExteriorCellBlock };
        wBlk.Items.Add(wSub);
        world.SubCells.Add(wBlk);
        core.Worldspaces.Add(world);

        var corePath = Path.Combine(dir, CorePlugin);
        core.BeginWrite.ToPath(corePath).WithLoadOrder(SfEsm).WithKnownMasters(new KeyedMasterStyle(SfEsm, MasterStyle.Full)).Write();
        return (sfPath, portPath, corePath);
    }

    public static int SelfTest(string scratchDir)
    {
        var fxDir = Path.Combine(scratchDir, "fixtures");
        var outDir = Path.Combine(scratchDir, "out");
        var (sfPath, portPath, corePath) = BuildFixtures(fxDir);

        var jsonPath = Path.Combine(outDir, "inspect.json");
        if (Inspect(portPath, corePath, jsonPath) != 0 || !File.Exists(jsonPath))
            throw new Refusal("selftest: Inspect failed");

        if (Write(sfPath, portPath, corePath, outDir, Plugin) != 0)
            throw new Refusal("selftest: Write failed");

        var plugPath = Path.Combine(outDir, Plugin);
        if (Check(plugPath, sfPath, portPath, corePath) != 0)
            throw new Refusal("selftest: Check rejected valid output");

        // Negative control 1: tampered int property in output plugin must fail Check
        var badDir = Path.Combine(scratchDir, "bad");
        Directory.CreateDirectory(badDir);
        var badPath = Path.Combine(badDir, Plugin);
        var mod = SF.StarfieldMod.CreateFromBinary(plugPath, SF.StarfieldRelease.Starfield,
            new BinaryReadParameters { MasterFlagsLookup = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey) { new KeyedMasterStyle(SfEsm, MasterStyle.Full) } });
        var prop = mod.Quests.First().VirtualMachineAdapter!.Scripts.First().Properties.OfType<SF.ScriptIntProperty>().First(p => p.Name == "RoofGateId");
        prop.Data += 1;
        mod.BeginWrite.ToPath(badPath).WithLoadOrder(SfEsm).WithKnownMasters(new KeyedMasterStyle(SfEsm, MasterStyle.Full)).Write();
        if (Check(badPath, sfPath, portPath, corePath) == 0)
            throw new Refusal("selftest: Check accepted tampered RoofGateId");

        // Negative control 2: missing RoofGate REFR in core must throw Refusal
        var badCoreDir = Path.Combine(scratchDir, "bad_core");
        Directory.CreateDirectory(badCoreDir);
        var badCorePath = Path.Combine(badCoreDir, CorePlugin);
        var cMod = SF.StarfieldMod.CreateFromBinary(corePath, SF.StarfieldRelease.Starfield,
            new BinaryReadParameters { MasterFlagsLookup = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey) { new KeyedMasterStyle(SfEsm, MasterStyle.Full) } });
        var ext = ((SF.WorldspaceSubBlock)((SF.WorldspaceBlock)cMod.Worldspaces.First().SubCells[0]).Items[0]).Items.OfType<SF.Cell>().First();
        ext.Temporary.RemoveWhere(r => r.FormKey.ID == RoofGateId);
        cMod.BeginWrite.ToPath(badCorePath).WithLoadOrder(SfEsm).WithKnownMasters(new KeyedMasterStyle(SfEsm, MasterStyle.Full)).Write();
        bool caught = false;
        try { Resolve(portPath, badCorePath); }
        catch (Refusal) { caught = true; }
        if (!caught) throw new Refusal("selftest: Resolve accepted missing RoofGateId");

        Console.WriteLine("selftest: ok");
        return 0;
    }
}
