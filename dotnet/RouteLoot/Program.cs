// RouteLoot: Phase 2 Track C (2i) Sanctuary-to-Concord (<= 600 m) Route Container Loot & Vault 111 Armory Writer
//
// Writes FO4SFRouteLoot.esm (Master-flagged, mastering Starfield.esm, FO4SFCoreValues.esm, FO4SFRads.esm,
// FO4SFWorkshop.esm, FO4TerrainCore.esm, and FO4Port.esm):
//   - B10: Creates dedicated FO4SFRouteLoot.esm CONT base records (0x000820+) and overrides ONLY placed container
//     REFRs within <= 600 m of the Sanctuary -> Red Rocket -> Concord corridor (zero FO4TerrainCore.esm CONT base
//     overrides; containers elsewhere on the map remain 100% unchanged).
//   - Places a playable semi-auto ballistic pistol + >= 48 matching ammo rounds + 2 FO4SF_Stimpaks inside Vault 111
//     (FO4Port_Vault111Cryo in FO4Port.esm) in both an armory case CONT and visible desk/console pickup spots.
//
// usage:
//   RouteLoot build <Starfield.esm> <FO4TerrainCore.esm> <FO4Port.esm> <out dir> [--json <route_loot_ids.json>]
//   RouteLoot check <FO4SFRouteLoot.esm> <Starfield.esm> <FO4TerrainCore.esm> <FO4Port.esm> [--json <route_loot_ids.json>]
//   RouteLoot census <FO4SFRouteLoot.esm> <Starfield.esm> <FO4TerrainCore.esm> <FO4Port.esm> [--out <census.json>] [--json <route_loot_ids.json>]
//   RouteLoot selftest <scratch dir>

using System.Globalization;
using System.Text.Json;
using System.Text.RegularExpressions;
using Mutagen.Bethesda;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;

try
{
    var rest = args.ToList();
    string? Opt(string name)
    {
        int i = rest.IndexOf(name);
        if (i < 0) return null;
        if (i + 1 >= rest.Count) throw new RouteLoot.Refusal(name + " needs a value");
        var v = rest[i + 1];
        rest.RemoveRange(i, 2);
        return v;
    }

    var jsonPath = Opt("--json");
    var outCensus = Opt("--out");
    var split = RouteLoot.ParseSplit(Opt("--split"));

    if (rest.Count == 5 && rest[0] == "build")
        return RouteLoot.Build(rest[1], rest[2], rest[3], rest[4], jsonPath, split);
    if (rest.Count == 5 && rest[0] == "check")
        return RouteLoot.Check(rest[1], rest[2], rest[3], rest[4], jsonPath, split);
    if (rest.Count == 5 && rest[0] == "census")
        return RouteLoot.Census(rest[1], rest[2], rest[3], rest[4], outCensus, jsonPath, split);
    if (rest.Count == 2 && rest[0] == "selftest")
        return RouteLoot.SelfTest(rest[1]);
}
catch (RouteLoot.Refusal r)
{
    Console.Error.WriteLine("refused: " + r.Message);
    return 1;
}

Console.Error.WriteLine(
    "usage: RouteLoot build <Starfield.esm> <FO4TerrainCore.esm> <FO4Port.esm> <out dir> [--json <path>] [--split full|bases-only|ext-overrides-only] | " +
    "check <plugin> <Starfield.esm> <FO4TerrainCore.esm> <FO4Port.esm> [--json <path>] [--split full|bases-only|ext-overrides-only] | " +
    "census <plugin> <Starfield.esm> <FO4TerrainCore.esm> <FO4Port.esm> [--out <census.json>] [--json <path>] [--split full|bases-only|ext-overrides-only] | " +
    "selftest <scratch dir>");
return 2;

static class RouteLoot
{
    public sealed class Refusal(string m) : Exception(m);

    public enum SplitMode
    {
        Full,
        BasesOnly,
        ExtOverridesOnly,
    }

    public static SplitMode ParseSplit(string? raw) => (raw ?? "full").Trim() switch
    {
        "full" => SplitMode.Full,
        "bases-only" => SplitMode.BasesOnly,
        "ext-overrides-only" => SplitMode.ExtOverridesOnly,
        _ => throw new Refusal($"--split expected full|bases-only|ext-overrides-only, got '{raw}'"),
    };

    public static string SplitLabel(SplitMode mode) => mode switch
    {
        SplitMode.Full => "full",
        SplitMode.BasesOnly => "bases-only",
        SplitMode.ExtOverridesOnly => "ext-overrides-only",
        _ => "full",
    };

    const StarfieldRelease Release = StarfieldRelease.Starfield;
    static readonly ModKey SfEsm = ModKey.FromFileName("Starfield.esm");
    static readonly ModKey CoreValuesEsm = ModKey.FromFileName("FO4SFCoreValues.esm");
    static readonly ModKey RadsEsm = ModKey.FromFileName("FO4SFRads.esm");
    static readonly ModKey WorkshopEsm = ModKey.FromFileName("FO4SFWorkshop.esm");
    static readonly ModKey TerrainCoreEsm = ModKey.FromFileName("FO4TerrainCore.esm");
    static readonly ModKey PortEsm = ModKey.FromFileName("FO4Port.esm");
    public static readonly ModKey Plugin = ModKey.FromFileName("FO4SFRouteLoot.esm");

    static readonly ModKey[] ExpectedMasters =
    {
        SfEsm, CoreValuesEsm, RadsEsm, WorkshopEsm, TerrainCoreEsm, PortEsm
    };

    static readonly ModKey[] BasesOnlyMasters =
    {
        SfEsm, CoreValuesEsm, RadsEsm, WorkshopEsm, PortEsm
    };

    static readonly ModKey[] ExtOverridesOnlyMasters =
    {
        SfEsm, TerrainCoreEsm
    };

    static ModKey[] ExpectedMastersForSplit(SplitMode split) => split switch
    {
        SplitMode.BasesOnly => BasesOnlyMasters,
        SplitMode.ExtOverridesOnly => ExtOverridesOnlyMasters,
        _ => ExpectedMasters,
    };

    const string ArmoryCaseEdid = "FO4SF_Vault111ArmoryCase";
    const uint CreditsId = 0x00000F;
    const uint NextId = 0x000810;
    const uint FirstRouteContBaseId = 0x000820;

    static readonly Regex CoreContEdidRx = new(@"^(?:FO4Core|FO4SF_RouteLoot)_cont_([0-9a-fA-F]{6})_", RegexOptions.Compiled);

    public sealed record LootEntry(ModKey Mod, uint Id, int Count)
    {
        public FormKey Key => new(Mod, Id);
        public bool IsCredits => Mod == SfEsm && Id == CreditsId;
    }

    public sealed record PickupSpec(
        uint OwnRefId,
        ModKey Mod,
        uint Id,
        int Count,
        P3Float Pos,
        P3Float Rot)
    {
        public FormKey BaseKey => new(Mod, Id);
    }

    public sealed class LootSpec
    {
        public required double CorridorRadiusM { get; init; }
        public required (double X, double Y)[] Polyline { get; init; }
        public required Dictionary<string, LootEntry[]> Categories { get; init; }
        public required Dictionary<uint, string> Fo4ContCategories { get; init; }
        public required uint VaultCellId { get; init; }
        public required uint VaultCaseTemplateId { get; init; }
        public required uint OwnCaseBaseId { get; init; }
        public required uint OwnCaseRefId { get; init; }
        public required P3Float CasePos { get; init; }
        public required P3Float CaseRot { get; init; }
        public required uint PortLockerContId { get; init; }
        public required uint PistolId { get; init; }
        public required uint AmmoId { get; init; }
        public required uint StimpakId { get; init; }
        public required int MinAmmoRounds { get; init; }
        public required int MinStimpaks { get; init; }
        public required PickupSpec[] Pickups { get; init; }
    }

    static uint ParseHex(string raw, string label)
    {
        var s = raw.Trim();
        if (!s.StartsWith("0x", StringComparison.OrdinalIgnoreCase) || s.Length != 8 ||
            !uint.TryParse(s.AsSpan(2), NumberStyles.HexNumber, CultureInfo.InvariantCulture, out var v) ||
            v == 0 || v > 0xFFFFFF)
            throw new Refusal($"{label}: expected 0xXXXXXX hex FormID, got '{raw}'");
        return v;
    }

    static P3Float ParseP3(JsonElement arr, string label)
    {
        if (arr.ValueKind != JsonValueKind.Array || arr.GetArrayLength() != 3)
            throw new Refusal($"{label}: expected [x, y, z]");
        var f = arr.EnumerateArray().Select(x => x.GetSingle()).ToArray();
        if (!float.IsFinite(f[0]) || !float.IsFinite(f[1]) || !float.IsFinite(f[2]))
            throw new Refusal($"{label}: non-finite coordinate");
        return new P3Float(f[0], f[1], f[2]);
    }

    public static string DefaultJsonPath()
    {
        var dir = AppContext.BaseDirectory;
        for (int up = 0; up < 8 && dir != null; up++, dir = Directory.GetParent(dir)?.FullName)
        {
            var cand = Path.Combine(dir, "src", "fo4sf", "loot", "route_loot_ids.json");
            if (File.Exists(cand)) return cand;
        }
        var cwd = Path.Combine(Directory.GetCurrentDirectory(), "src", "fo4sf", "loot", "route_loot_ids.json");
        if (File.Exists(cwd)) return cwd;
        throw new Refusal("cannot locate src/fo4sf/loot/route_loot_ids.json; pass --json <path>");
    }

    public static LootSpec LoadSpec(string? jsonPath = null)
    {
        var path = jsonPath ?? DefaultJsonPath();
        if (!File.Exists(path)) throw new Refusal($"missing route_loot_ids.json: {path}");
        using var doc = JsonDocument.Parse(File.ReadAllText(path));
        var root = doc.RootElement;
        if (root.GetProperty("schema_version").GetInt32() != 1)
            throw new Refusal("unsupported route_loot_ids.json schema_version");
        var pluginStr = root.GetProperty("plugin").GetString() ?? "";
        if (ModKey.FromFileName(pluginStr) != Plugin)
            throw new Refusal($"route_loot_ids.json plugin '{pluginStr}' != {Plugin}");

        var masters = root.GetProperty("masters").EnumerateArray()
            .Select(m => ModKey.FromFileName(m.GetString()!)).ToArray();
        if (!masters.SequenceEqual(ExpectedMasters))
            throw new Refusal($"route_loot_ids.json masters [{string.Join(", ", masters)}] != [{string.Join(", ", ExpectedMasters)}]");

        var masterSet = ExpectedMasters.ToHashSet();
        double radius = root.GetProperty("corridor_radius_m").GetDouble();
        if (!double.IsFinite(radius) || radius <= 0.0 || radius > 2000.0)
            throw new Refusal($"invalid corridor_radius_m: {radius}");

        var poly = root.GetProperty("corridor_polyline_m").EnumerateArray()
            .Select(pt =>
            {
                var xy = pt.EnumerateArray().Select(v => v.GetDouble()).ToArray();
                if (xy.Length != 2 || !double.IsFinite(xy[0]) || !double.IsFinite(xy[1]))
                    throw new Refusal("invalid corridor_polyline_m point");
                return (xy[0], xy[1]);
            }).ToArray();
        if (poly.Length < 2) throw new Refusal("corridor_polyline_m needs >= 2 points");

        var cats = new Dictionary<string, LootEntry[]>(StringComparer.Ordinal);
        foreach (var prop in root.GetProperty("categories").EnumerateObject())
        {
            var entries = prop.Value.EnumerateArray().Select(it =>
            {
                var mk = ModKey.FromFileName(it.GetProperty("plugin").GetString()!);
                if (!masterSet.Contains(mk)) throw new Refusal($"category {prop.Name} references non-master {mk}");
                var id = ParseHex(it.GetProperty("id").GetString()!, $"categories.{prop.Name}.id");
                var cnt = it.GetProperty("count").GetInt32();
                if (cnt < 1 || cnt > 10000) throw new Refusal($"category {prop.Name} invalid count {cnt}");
                return new LootEntry(mk, id, cnt);
            }).ToArray();
            if (entries.Length == 0) throw new Refusal($"empty category {prop.Name}");
            cats[prop.Name] = entries;
        }

        var fo4Map = new Dictionary<uint, string>();
        foreach (var prop in root.GetProperty("fo4_container_categories").EnumerateObject())
        {
            var fid = ParseHex(prop.Name, $"fo4_container_categories.{prop.Name}");
            var cat = prop.Value.GetString()!;
            if (!cats.ContainsKey(cat) || cat == "vault_armory")
                throw new Refusal($"invalid container category '{cat}' for 0x{fid:X6}");
            fo4Map[fid] = cat;
        }

        var v = root.GetProperty("vault111");
        var pickups = v.GetProperty("pickups").EnumerateArray().Select((pk, idx) =>
        {
            var ownRef = ParseHex(pk.GetProperty("own_ref_id").GetString()!, $"pickups[{idx}].own_ref_id");
            var mk = ModKey.FromFileName(pk.GetProperty("plugin").GetString()!);
            if (!masterSet.Contains(mk)) throw new Refusal($"pickups[{idx}] non-master {mk}");
            var iid = ParseHex(pk.GetProperty("id").GetString()!, $"pickups[{idx}].id");
            var cnt = pk.GetProperty("count").GetInt32();
            if (cnt < 1) throw new Refusal($"pickups[{idx}] count < 1");
            return new PickupSpec(ownRef, mk, iid, cnt,
                ParseP3(pk.GetProperty("pos_m"), $"pickups[{idx}].pos_m"),
                ParseP3(pk.GetProperty("rot_rad"), $"pickups[{idx}].rot_rad"));
        }).ToArray();

        return new LootSpec
        {
            CorridorRadiusM = radius,
            Polyline = poly,
            Categories = cats,
            Fo4ContCategories = fo4Map,
            VaultCellId = ParseHex(v.GetProperty("cell_id").GetString()!, "vault111.cell_id"),
            VaultCaseTemplateId = ParseHex(v.GetProperty("case_template_id").GetString()!, "vault111.case_template_id"),
            OwnCaseBaseId = ParseHex(v.GetProperty("own_case_base_id").GetString()!, "vault111.own_case_base_id"),
            OwnCaseRefId = ParseHex(v.GetProperty("own_case_ref_id").GetString()!, "vault111.own_case_ref_id"),
            CasePos = ParseP3(v.GetProperty("case_pos_m"), "vault111.case_pos_m"),
            CaseRot = ParseP3(v.GetProperty("case_rot_rad"), "vault111.case_rot_rad"),
            PortLockerContId = ParseHex(v.GetProperty("port_locker_cont_id").GetString()!, "vault111.port_locker_cont_id"),
            PistolId = ParseHex(v.GetProperty("pistol_id").GetString()!, "vault111.pistol_id"),
            AmmoId = ParseHex(v.GetProperty("ammo_id").GetString()!, "vault111.ammo_id"),
            StimpakId = ParseHex(v.GetProperty("stimpak_id").GetString()!, "vault111.stimpak_id"),
            MinAmmoRounds = v.GetProperty("min_ammo_rounds").GetInt32(),
            MinStimpaks = v.GetProperty("min_stimpaks").GetInt32(),
            Pickups = pickups,
        };
    }

    static double PointToSegmentDist(double px, double py, (double X, double Y) a, (double X, double Y) b)
    {
        double dx = b.X - a.X, dy = b.Y - a.Y;
        double len2 = dx * dx + dy * dy;
        double t = len2 > 0.0 ? Math.Clamp(((px - a.X) * dx + (py - a.Y) * dy) / len2, 0.0, 1.0) : 0.0;
        double qx = a.X + t * dx, qy = a.Y + t * dy;
        return Math.Sqrt((px - qx) * (px - qx) + (py - qy) * (py - qy));
    }

    public static double CorridorDistance(double px, double py, (double X, double Y)[] poly)
    {
        double best = double.MaxValue;
        for (int i = 0; i < poly.Length - 1; i++)
        {
            double d = PointToSegmentDist(px, py, poly[i], poly[i + 1]);
            if (d < best) best = d;
        }
        return best;
    }

    static Cache<IModMasterStyledGetter, ModKey> Styles(params ModKey[] masters)
    {
        var c = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        foreach (var m in masters) c.Set(new KeyedMasterStyle(m, MasterStyle.Full));
        return c;
    }

    static IStarfieldModDisposableGetter OpenMod(string path, params ModKey[] masters) =>
        StarfieldMod.CreateFromBinaryOverlay(path, Release, new BinaryReadParameters { MasterFlagsLookup = Styles(masters) });

    static Cell CellOnly(ICellGetter c)
    {
        var copy = c.DeepCopy(new Cell.TranslationMask(defaultOn: true)
        {
            Persistent = false,
            Temporary = false,
            NavigationMeshes = new NavigationMesh.TranslationMask(defaultOn: false, onOverall: false),
        });
        copy.Persistent.Clear();
        copy.Temporary.Clear();
        copy.NavigationMeshes.Clear();
        return copy;
    }

    static Worldspace WorldOnly(IWorldspaceGetter w)
    {
        var copy = w.DeepCopy(new Worldspace.TranslationMask(defaultOn: true)
        {
            TopCell = false,
            SubCells = false,
        });
        copy.TopCell = null;
        copy.SubCells.Clear();
        return copy;
    }

    static ExtendedList<ContainerEntry> MakeContainerItems(IEnumerable<LootEntry> entries)
    {
        var list = new ExtendedList<ContainerEntry>();
        foreach (var e in entries)
            list.Add(new ContainerEntry { Item = new ContainerItem { Item = new FormLink<IItemGetter>(e.Key), Count = e.Count } });
        return list;
    }

    static bool TryParseFo4ContHex(string? edid, out uint fo4Id)
    {
        fo4Id = 0;
        if (string.IsNullOrEmpty(edid)) return false;
        var m = CoreContEdidRx.Match(edid);
        return m.Success && uint.TryParse(m.Groups[1].Value, NumberStyles.HexNumber, CultureInfo.InvariantCulture, out fo4Id);
    }

    static void ValidateStarfieldAssets(IStarfieldModGetter sf, LootSpec spec)
    {
        var weap = sf.Weapons.FirstOrDefault(w => w.FormKey.ID == spec.PistolId)
            ?? throw new Refusal($"Starfield.esm lacks WEAP 0x{spec.PistolId:X6}");
        if (weap.MajorFlags.HasFlag(Weapon.MajorFlag.NonPlayable) || weap.NonPlayable)
            throw new Refusal($"Starfield.esm WEAP 0x{spec.PistolId:X6} is NonPlayable");
        if (weap.Model == null)
            throw new Refusal($"Starfield.esm WEAP 0x{spec.PistolId:X6} lacks a Model");

        var ammoFk = new FormKey(SfEsm, spec.AmmoId);
        var ammo = sf.Ammunitions.FirstOrDefault(a => a.FormKey == ammoFk)
            ?? throw new Refusal($"Starfield.esm lacks AMMO 0x{spec.AmmoId:X6}");
        if (ammo.MajorFlags.HasFlag(Ammunition.MajorFlag.NonPlayable) || ammo.Model == null)
            throw new Refusal($"Starfield.esm AMMO 0x{spec.AmmoId:X6} is NonPlayable or lacks a Model");

        if (!weap.EnumerateFormLinks().Any(l => l.FormKey == ammoFk))
            throw new Refusal($"Starfield.esm WEAP 0x{spec.PistolId:X6} does not link AMMO 0x{spec.AmmoId:X6}");

        var caseTpl = sf.Containers.FirstOrDefault(c => c.FormKey.ID == spec.VaultCaseTemplateId)
            ?? throw new Refusal($"Starfield.esm lacks CONT template 0x{spec.VaultCaseTemplateId:X6}");
        if (caseTpl.Model == null)
            throw new Refusal($"Starfield.esm CONT template 0x{spec.VaultCaseTemplateId:X6} lacks a Model");

        var sfAmmoIds = sf.Ammunitions.Select(a => a.FormKey.ID).ToHashSet();
        var sfMiscIds = sf.MiscItems.Select(m => m.FormKey.ID).ToHashSet();
        var sfWeapIds = sf.Weapons.Select(w => w.FormKey.ID).ToHashSet();
        var sfAlchIds = sf.Ingestibles.Select(a => a.FormKey.ID).ToHashSet();

        foreach (var (cat, list) in spec.Categories)
        {
            foreach (var it in list.Where(x => x.Mod == SfEsm))
            {
                if (!sfAmmoIds.Contains(it.Id) && !sfMiscIds.Contains(it.Id) &&
                    !sfWeapIds.Contains(it.Id) && !sfAlchIds.Contains(it.Id))
                    throw new Refusal($"Starfield.esm lacks item 0x{it.Id:X6} referenced by category '{cat}'");
            }
        }
    }

    sealed record RouteScan(
        int TotalExteriorContainers,
        int RouteContainersWithinRadius,
        Dictionary<FormKey, (uint Fo4Id, string Category)> MappedContCategories,
        Dictionary<FormKey, (FormKey CoreContKey, string Category)> RouteRefCategories,
        Dictionary<string, int> RouteContainersByCategory);

    static RouteScan ScanTerrainCore(IStarfieldModGetter core, LootSpec spec)
    {
        var coreConts = core.Containers.Where(c => (c.MajorRecordFlagsRaw & 0x20) == 0)
            .ToDictionary(c => c.FormKey);
        if (coreConts.Count == 0)
            throw new Refusal($"{core.ModKey}: contains 0 CONT base records");

        var routeContBases = new HashSet<FormKey>();
        var routeRefs = new List<(IPlacedObjectGetter Ref, IContainerGetter Base)>();
        int totalExtConts = 0;

        void VisitCell(ICellGetter? cell)
        {
            if (cell == null) return;
            foreach (var r in cell.Persistent.Concat(cell.Temporary).OfType<IPlacedObjectGetter>())
            {
                if ((r.MajorRecordFlagsRaw & 0x20) != 0 || (r.MajorRecordFlagsRaw & 0x800) != 0) continue;
                if (!coreConts.TryGetValue(r.Base.FormKey, out var cb)) continue;
                totalExtConts++;
                double d = CorridorDistance(r.Position.X, r.Position.Y, spec.Polyline);
                if (d <= spec.CorridorRadiusM)
                {
                    routeContBases.Add(cb.FormKey);
                    routeRefs.Add((r, cb));
                }
            }
        }

        foreach (var w in core.Worldspaces)
        {
            VisitCell(w.TopCell);
            foreach (var blk in w.SubCells)
                foreach (var sub in blk.Items)
                    foreach (var ec in sub.Items)
                        VisitCell(ec);
        }

        var mappedCategories = new Dictionary<FormKey, (uint Fo4Id, string Category)>();
        foreach (var bfk in routeContBases.OrderBy(k => k.ID))
        {
            var cb = coreConts[bfk];
            if (TryParseFo4ContHex(cb.EditorID, out var fo4Id) &&
                spec.Fo4ContCategories.TryGetValue(fo4Id, out var cat))
            {
                mappedCategories[bfk] = (fo4Id, cat);
            }
        }

        var routeRefCategories = new Dictionary<FormKey, (FormKey CoreContKey, string Category)>();
        var byCat = new Dictionary<string, int>(StringComparer.Ordinal)
        {
            ["ammo"] = 0, ["aid"] = 0, ["junk"] = 0, ["caps"] = 0, ["untouched"] = 0,
        };
        foreach (var (r, cb) in routeRefs)
        {
            if (mappedCategories.TryGetValue(cb.FormKey, out var info))
            {
                routeRefCategories[r.FormKey] = (cb.FormKey, info.Category);
                byCat[info.Category] = byCat.GetValueOrDefault(info.Category) + 1;
            }
            else
                byCat["untouched"]++;
        }

        return new RouteScan(totalExtConts, routeRefs.Count, mappedCategories, routeRefCategories, byCat);
    }

    static void WriteAtomic(StarfieldMod mod, string outDir, SplitMode split = SplitMode.Full)
    {
        Directory.CreateDirectory(outDir);
        var finalPath = Path.Combine(outDir, mod.ModKey.FileName);
        var tmpDir = Path.Combine(outDir, ".tmp-" + Guid.NewGuid().ToString("N"));
        var wantMasters = ExpectedMastersForSplit(split);
        if (split != SplitMode.Full)
        {
            mod.ModHeader.MasterReferences.Clear();
            foreach (var mk in wantMasters)
                mod.ModHeader.MasterReferences.Add(new MasterReference { Master = mk });
        }
        try
        {
            Directory.CreateDirectory(tmpDir);
            var tmpPath = Path.Combine(tmpDir, mod.ModKey.FileName);
            var writeParams = split == SplitMode.Full
                ? new BinaryWriteParameters
                {
                    ModKey = ModKeyOption.NoCheck,
                    MastersListOrdering = new MastersListOrderingByLoadOrder(ExpectedMasters),
                    MasterFlagsLookup = Styles(ExpectedMasters),
                }
                : new BinaryWriteParameters
                {
                    ModKey = ModKeyOption.NoCheck,
                    MastersListContent = MastersListContentOption.NoCheck,
                    MastersListOrdering = new MastersListOrderingByLoadOrder(wantMasters),
                    MasterFlagsLookup = Styles(wantMasters),
                };
            mod.WriteToBinary(tmpPath, writeParams);
            File.Move(tmpPath, finalPath, overwrite: true);
        }
        finally
        {
            if (Directory.Exists(tmpDir)) Directory.Delete(tmpDir, recursive: true);
        }
    }

    static string OwnRouteContEdid(uint fo4Id, uint coreLocalId) =>
        $"FO4SF_RouteLoot_cont_{fo4Id:x6}_{coreLocalId:x6}";

    public static int Build(string sfPath, string corePath, string portPath, string outDir, string? jsonPath = null, SplitMode split = SplitMode.Full)
    {
        var spec = LoadSpec(jsonPath);
        using var sf = OpenMod(sfPath, SfEsm);
        using var core = OpenMod(corePath, SfEsm);
        using var port = OpenMod(portPath, SfEsm);

        ValidateStarfieldAssets(sf, spec);
        var scan = ScanTerrainCore(core, spec);
        if (scan.MappedContCategories.Count == 0 || scan.RouteRefCategories.Count == 0)
            throw new Refusal("0 route CONT references matched fo4_container_categories within corridor radius");

        var v111Src = port.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells)
            .FirstOrDefault(c => c.FormKey == new FormKey(PortEsm, spec.VaultCellId))
            ?? throw new Refusal($"FO4Port.esm lacks Vault 111 CELL 0x{spec.VaultCellId:X6}");

        var mod = new StarfieldMod(Plugin, Release);
        mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        mod.ModHeader.Author = "fo4-to-starfield";

        // 1 (B10 / T1). Create dedicated FO4SFRouteLoot.esm CONT base records (0x000820+) unless --split ext-overrides-only.
        var coreContByKey = core.Containers.ToDictionary(c => c.FormKey);
        var ownRouteContByCoreKey = new Dictionary<FormKey, FormKey>();
        uint nextOwnId = FirstRouteContBaseId;
        if (split != SplitMode.ExtOverridesOnly)
        {
            foreach (var (bfk, info) in scan.MappedContCategories.OrderBy(kv => kv.Key.ID))
            {
                var srcCont = coreContByKey[bfk];
                var ownKey = new FormKey(Plugin, nextOwnId++);
                var ownCont = (Container)srcCont.Duplicate(ownKey);
                ownCont.EditorID = OwnRouteContEdid(info.Fo4Id, bfk.ID);
                ownCont.Items = MakeContainerItems(spec.Categories[info.Category]);
                mod.Containers.Add(ownCont);
                ownRouteContByCoreKey[bfk] = ownKey;
            }
        }

        int writtenExtRefs = 0;
        if (split != SplitMode.BasesOnly)
        {
            bool TryTargetBase(FormKey coreContKey, out FormKey targetBase)
            {
                if (split == SplitMode.ExtOverridesOnly)
                {
                    targetBase = coreContKey;
                    return true;
                }
                return ownRouteContByCoreKey.TryGetValue(coreContKey, out targetBase);
            }

            Cell? BuildCorridorCellOverride(ICellGetter? srcCell)
            {
                if (srcCell == null) return null;
                var pers = new List<PlacedObject>();
                var temp = new List<PlacedObject>();
                foreach (var r in srcCell.Persistent.OfType<IPlacedObjectGetter>())
                {
                    if (scan.RouteRefCategories.TryGetValue(r.FormKey, out var ri) &&
                        TryTargetBase(ri.CoreContKey, out var targetBase))
                    {
                        var ov = r.DeepCopy();
                        ov.Base = new FormLinkNullable<IPlaceableObjectGetter>(targetBase);
                        pers.Add(ov);
                    }
                }
                foreach (var r in srcCell.Temporary.OfType<IPlacedObjectGetter>())
                {
                    if (scan.RouteRefCategories.TryGetValue(r.FormKey, out var ri) &&
                        TryTargetBase(ri.CoreContKey, out var targetBase))
                    {
                        var ov = r.DeepCopy();
                        ov.Base = new FormLinkNullable<IPlaceableObjectGetter>(targetBase);
                        temp.Add(ov);
                    }
                }
                if (pers.Count == 0 && temp.Count == 0) return null;
                writtenExtRefs += pers.Count + temp.Count;
                var cellOut = CellOnly(srcCell);
                foreach (var p in pers) cellOut.Persistent.Add(p);
                foreach (var t in temp) cellOut.Temporary.Add(t);
                return cellOut;
            }

            foreach (var srcWorld in core.Worldspaces)
            {
                var topOut = BuildCorridorCellOverride(srcWorld.TopCell);
                var blocksOut = new List<WorldspaceBlock>();
                foreach (var srcBlk in srcWorld.SubCells)
                {
                    var subsOut = new List<WorldspaceSubBlock>();
                    foreach (var srcSub in srcBlk.Items)
                    {
                        var cellsOut = new List<Cell>();
                        foreach (var srcCell in srcSub.Items)
                        {
                            var ecOut = BuildCorridorCellOverride(srcCell);
                            if (ecOut != null) cellsOut.Add(ecOut);
                        }
                        if (cellsOut.Count > 0)
                        {
                            var subOut = new WorldspaceSubBlock
                            {
                                BlockNumberX = srcSub.BlockNumberX,
                                BlockNumberY = srcSub.BlockNumberY,
                                GroupType = srcSub.GroupType,
                            };
                            foreach (var c in cellsOut) subOut.Items.Add(c);
                            subsOut.Add(subOut);
                        }
                    }
                    if (subsOut.Count > 0)
                    {
                        var blkOut = new WorldspaceBlock
                        {
                            BlockNumberX = srcBlk.BlockNumberX,
                            BlockNumberY = srcBlk.BlockNumberY,
                            GroupType = srcBlk.GroupType,
                        };
                        foreach (var s in subsOut) blkOut.Items.Add(s);
                        blocksOut.Add(blkOut);
                    }
                }
                if (topOut != null || blocksOut.Count > 0)
                {
                    var worldOut = WorldOnly(srcWorld);
                    worldOut.TopCell = topOut;
                    foreach (var b in blocksOut) worldOut.SubCells.Add(b);
                    mod.Worldspaces.Add(worldOut);
                }
            }
        }

        if (split != SplitMode.ExtOverridesOnly)
        {
            // 2. Override Vault 111 security locker CONT in FO4Port.esm (when present) + add dedicated Armory Case CONT.
            var portLockerFk = new FormKey(PortEsm, spec.PortLockerContId);
            var portLocker = port.Containers.FirstOrDefault(c => c.FormKey == portLockerFk);
            if (portLocker != null)
            {
                var lockerOv = portLocker.DeepCopy();
                lockerOv.Items = MakeContainerItems(spec.Categories["vault_armory"]);
                mod.Containers.Add(lockerOv);
            }

            var caseTpl = sf.Containers.First(c => c.FormKey.ID == spec.VaultCaseTemplateId);
            var ownCaseKey = new FormKey(Plugin, spec.OwnCaseBaseId);
            var armoryCase = (Container)caseTpl.Duplicate(ownCaseKey);
            armoryCase.EditorID = ArmoryCaseEdid;
            armoryCase.VirtualMachineAdapter = null;
            armoryCase.Keywords?.Clear();
            armoryCase.Items = MakeContainerItems(spec.Categories["vault_armory"]);
            mod.Containers.Add(armoryCase);

            // 3. Override Vault 111 interior cell (CellOnly) with placed Armory Case + visible pistol/ammo/stimpak pickups.
            var v111Cell = CellOnly(v111Src);
            var caseRef = new PlacedObject(new FormKey(Plugin, spec.OwnCaseRefId), Release)
            {
                Base = new FormLinkNullable<IPlaceableObjectGetter>(ownCaseKey),
                Position = spec.CasePos,
                Rotation = spec.CaseRot,
            };
            v111Cell.Temporary.Add(caseRef);

            foreach (var pk in spec.Pickups)
            {
                var pObj = new PlacedObject(new FormKey(Plugin, pk.OwnRefId), Release)
                {
                    Base = new FormLinkNullable<IPlaceableObjectGetter>(pk.BaseKey),
                    Position = pk.Pos,
                    Rotation = pk.Rot,
                };
                if (pk.Count > 1) pObj.Count = pk.Count;
                v111Cell.Temporary.Add(pObj);
            }

            var cid = v111Cell.FormKey.ID;
            var block = new CellBlock { BlockNumber = (int)(cid % 10), GroupType = GroupTypeEnum.InteriorCellBlock };
            var sub = new CellSubBlock { BlockNumber = (int)((cid / 10) % 10), GroupType = GroupTypeEnum.InteriorCellSubBlock };
            sub.Cells.Add(v111Cell);
            block.SubBlocks.Add(sub);
            mod.Cells.Records.Add(block);
        }

        mod.ModHeader.Stats.NextFormID = Math.Max(NextId, nextOwnId);
        WriteAtomic(mod, outDir, split);

        int nonCreditRoute = split == SplitMode.Full
            ? (scan.RouteContainersByCategory["ammo"] +
               scan.RouteContainersByCategory["aid"] +
               scan.RouteContainersByCategory["junk"])
            : 0;
        var outPath = Path.Combine(outDir, Plugin.FileName);
        var splitNote = split == SplitMode.Full ? "" : $" [split={SplitLabel(split)}]";
        Console.WriteLine(
            $"wrote {outPath}{splitNote} ({new FileInfo(outPath).Length:N0} bytes): " +
            $"{ownRouteContByCoreKey.Count} own route CONT bases, {writtenExtRefs} corridor REFR overrides (0 core CONT overrides; {nonCreditRoute}/{scan.RouteContainersWithinRadius} route containers non-credit), " +
            $"Vault 111 CELL 0x{spec.VaultCellId:X6} armory CONT 0x{spec.OwnCaseBaseId:X6} + {(split == SplitMode.ExtOverridesOnly ? 0 : 1 + spec.Pickups.Length)} REFRs");
        return 0;
    }

    static bool Near(P3Float a, P3Float b, float tol = 1e-3f) =>
        Math.Abs(a.X - b.X) <= tol && Math.Abs(a.Y - b.Y) <= tol && Math.Abs(a.Z - b.Z) <= tol;

    static List<(FormKey Item, int Count)> ReadContItems(IContainerGetter c) =>
        c.Items?.Select(e => (e.Item.Item.FormKey, e.Item.Count)).ToList() ?? new();

    static Dictionary<FormKey, IPlacedObjectGetter> CollectWorldspacePlacedObjects(IStarfieldModGetter mod)
    {
        var dict = new Dictionary<FormKey, IPlacedObjectGetter>();
        void Visit(ICellGetter? c)
        {
            if (c == null) return;
            foreach (var r in c.Persistent.Concat(c.Temporary).OfType<IPlacedObjectGetter>())
                dict[r.FormKey] = r;
        }
        foreach (var w in mod.Worldspaces)
        {
            Visit(w.TopCell);
            foreach (var blk in w.SubCells)
                foreach (var sub in blk.Items)
                    foreach (var ec in sub.Items)
                        Visit(ec);
        }
        return dict;
    }

    public static int Check(string pluginPath, string sfPath, string corePath, string portPath, string? jsonPath = null, SplitMode split = SplitMode.Full)
    {
        var spec = LoadSpec(jsonPath);
        using var sf = OpenMod(sfPath, SfEsm);
        using var core = OpenMod(corePath, SfEsm);
        using var port = OpenMod(portPath, SfEsm);
        var wantMasters = ExpectedMastersForSplit(split);
        using var mod = OpenMod(pluginPath, wantMasters);

        ValidateStarfieldAssets(sf, spec);
        var scan = ScanTerrainCore(core, spec);

        var problems = new List<string>();
        void Need(bool ok, string msg) { if (!ok) problems.Add(msg); }

        Need(mod.ModKey == Plugin, $"ModKey {mod.ModKey} != {Plugin}");
        Need(mod.ModHeader.Flags.HasFlag(StarfieldModHeader.HeaderFlag.Master), "plugin lacks Master header flag");
        var masters = mod.ModHeader.MasterReferences.Select(m => m.Master).ToArray();
        Need(masters.SequenceEqual(wantMasters),
            $"masters [{string.Join(", ", masters)}] != [{string.Join(", ", wantMasters)}]");

        var lowOwn = mod.EnumerateMajorRecords().Where(r => r.FormKey.ModKey == Plugin && r.FormKey.ID < 0x800).ToList();
        Need(lowOwn.Count == 0, $"plugin has own records with ID < 0x800: {string.Join(", ", lowOwn.Select(r => r.FormKey))}");

        var coreContOverrides = mod.Containers.Where(c => c.FormKey.ModKey == TerrainCoreEsm).ToList();
        Need(coreContOverrides.Count == 0,
            $"B10 violation: plugin overrides {coreContOverrides.Count} FO4TerrainCore.esm CONT base records (expected 0)");

        var coreContByKey = core.Containers.ToDictionary(c => c.FormKey);
        var modContByEdid = mod.Containers.Where(c => c.FormKey.ModKey == Plugin && !string.IsNullOrEmpty(c.EditorID))
            .ToDictionary(c => c.EditorID!, StringComparer.OrdinalIgnoreCase);
        var expectedOwnBaseByCoreKey = new Dictionary<FormKey, FormKey>();

        if (split != SplitMode.ExtOverridesOnly)
        {
            foreach (var (bfk, info) in scan.MappedContCategories)
            {
                var wantEdid = OwnRouteContEdid(info.Fo4Id, bfk.ID);
                if (!modContByEdid.TryGetValue(wantEdid, out var ownCont))
                {
                    problems.Add($"missing dedicated route CONT base '{wantEdid}' for {bfk}");
                    continue;
                }
                expectedOwnBaseByCoreKey[bfk] = ownCont.FormKey;
                var src = coreContByKey[bfk];
                var ovModel = ownCont.Model?.File?.ToString();
                var srcModel = src.Model?.File?.ToString();
                Need(string.Equals(ovModel, srcModel, StringComparison.OrdinalIgnoreCase),
                    $"CONT {ownCont.FormKey} ({wantEdid}) changed Model ({ovModel} != {srcModel})");
                var gotItems = ReadContItems(ownCont);
                var wantItems = spec.Categories[info.Category].Select(e => (e.Key, e.Count)).ToList();
                Need(gotItems.SequenceEqual(wantItems), $"CONT {ownCont.FormKey} ({wantEdid}) items mismatch for category '{info.Category}'");
            }
        }
        else
        {
            Need(mod.Containers.Count == 0,
                $"ext-overrides-only must contain 0 CONT records, found {mod.Containers.Count}");
        }

        // Verify Worldspace & exterior Cell headers match FO4TerrainCore.esm and ONLY corridor REFRs are overridden.
        var coreWorldByKey = core.Worldspaces.ToDictionary(w => w.FormKey);
        var coreCellsByKey = new Dictionary<FormKey, ICellGetter>();
        var coreRefsByKey = new Dictionary<FormKey, IPlacedObjectGetter>();
        foreach (var cw in core.Worldspaces)
        {
            if (cw.TopCell != null)
            {
                coreCellsByKey[cw.TopCell.FormKey] = cw.TopCell;
                foreach (var r in cw.TopCell.Persistent.Concat(cw.TopCell.Temporary).OfType<IPlacedObjectGetter>())
                    coreRefsByKey[r.FormKey] = r;
            }
            foreach (var blk in cw.SubCells)
                foreach (var sub in blk.Items)
                    foreach (var ec in sub.Items)
                    {
                        coreCellsByKey[ec.FormKey] = ec;
                        foreach (var r in ec.Persistent.Concat(ec.Temporary).OfType<IPlacedObjectGetter>())
                            coreRefsByKey[r.FormKey] = r;
                    }
        }

        var modExtRefs = CollectWorldspacePlacedObjects(mod);
        if (split == SplitMode.BasesOnly)
        {
            Need(mod.Worldspaces.Count == 0 && modExtRefs.Count == 0,
                $"bases-only must contain 0 Worldspace / exterior REFR overrides, found worldspaces={mod.Worldspaces.Count}, refs={modExtRefs.Count}");
        }
        else
        {
            foreach (var mw in mod.Worldspaces)
            {
                Need(coreWorldByKey.TryGetValue(mw.FormKey, out var sw) && WorldOnly(sw).Equals(WorldOnly(mw)),
                    $"Worldspace {mw.FormKey} header differs from FO4TerrainCore.esm");
                void CheckExtCell(ICellGetter? mc)
                {
                    if (mc == null) return;
                    Need(coreCellsByKey.TryGetValue(mc.FormKey, out var sc) && CellOnly(sc).Equals(CellOnly(mc)),
                        $"Exterior CELL {mc.FormKey} header differs from FO4TerrainCore.esm");
                }
                CheckExtCell(mw.TopCell);
                foreach (var blk in mw.SubCells)
                    foreach (var sub in blk.Items)
                        foreach (var ec in sub.Items)
                            CheckExtCell(ec);
            }

            Need(modExtRefs.Count == scan.RouteRefCategories.Count,
                $"overridden exterior REFR count {modExtRefs.Count} != expected corridor count {scan.RouteRefCategories.Count}");
            foreach (var (rfk, ri) in scan.RouteRefCategories)
            {
                if (!modExtRefs.TryGetValue(rfk, out var mref))
                {
                    problems.Add($"missing corridor REFR override {rfk}");
                    continue;
                }
                var srcRef = coreRefsByKey[rfk];
                if (split == SplitMode.ExtOverridesOnly)
                {
                    Need(mref.Base.FormKey == ri.CoreContKey,
                        $"ext-overrides-only REFR {rfk} Base {mref.Base.FormKey} != core CONT base {ri.CoreContKey}");
                }
                else
                {
                    Need(expectedOwnBaseByCoreKey.TryGetValue(ri.CoreContKey, out var wantBase) && mref.Base.FormKey == wantBase,
                        $"REFR {rfk} Base {mref.Base.FormKey} != dedicated route CONT base");
                }
                Need(Near(mref.Position, srcRef.Position), $"REFR {rfk} moved position ({mref.Position} != {srcRef.Position})");
            }
            foreach (var extraRef in modExtRefs.Keys.Where(k => !scan.RouteRefCategories.ContainsKey(k)))
                problems.Add($"unexpected non-corridor REFR override in Worldspaces: {extraRef}");
        }

        var cells = mod.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells).ToList();
        if (split == SplitMode.ExtOverridesOnly)
        {
            Need(cells.Count == 0, $"ext-overrides-only must contain 0 interior CELL overrides, found {cells.Count}");
        }
        else
        {
            var modContByKey = mod.Containers.ToDictionary(c => c.FormKey);
            var ownCaseKey = new FormKey(Plugin, spec.OwnCaseBaseId);
            Need(modContByKey.TryGetValue(ownCaseKey, out var armoryCase) && armoryCase.EditorID == ArmoryCaseEdid,
                $"missing own CONT {ownCaseKey} ({ArmoryCaseEdid})");
            if (armoryCase != null)
            {
                var gotArmory = ReadContItems(armoryCase);
                var wantArmory = spec.Categories["vault_armory"].Select(e => (e.Key, e.Count)).ToList();
                Need(gotArmory.SequenceEqual(wantArmory), $"{ArmoryCaseEdid} items do not match vault_armory");
                int pistolCnt = gotArmory.Where(x => x.Item == new FormKey(SfEsm, spec.PistolId)).Sum(x => x.Count);
                int ammoCnt = gotArmory.Where(x => x.Item == new FormKey(SfEsm, spec.AmmoId)).Sum(x => x.Count);
                int stimCnt = gotArmory.Where(x => x.Item == new FormKey(CoreValuesEsm, spec.StimpakId)).Sum(x => x.Count);
                Need(pistolCnt >= 1 && ammoCnt >= spec.MinAmmoRounds && stimCnt >= spec.MinStimpaks,
                    $"{ArmoryCaseEdid} holds pistol={pistolCnt}, ammo={ammoCnt}, stimpaks={stimCnt}");
            }

            var v111Fk = new FormKey(PortEsm, spec.VaultCellId);
            Need(cells.Count == 1 && cells[0].FormKey == v111Fk,
                $"expected 1 interior CELL override ({v111Fk}), found [{string.Join(", ", cells.Select(c => c.FormKey))}]");
            if (cells.Count == 1)
            {
                var srcCell = port.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells)
                    .FirstOrDefault(c => c.FormKey == v111Fk);
                Need(srcCell != null && CellOnly(srcCell).Equals(CellOnly(cells[0])),
                    $"CELL {v111Fk} header/fields differ from FO4Port.esm");
                var placed = cells[0].Temporary.OfType<IPlacedObjectGetter>().ToDictionary(r => r.FormKey);
                var caseRefFk = new FormKey(Plugin, spec.OwnCaseRefId);
                Need(placed.TryGetValue(caseRefFk, out var cr) && cr.Base.FormKey == ownCaseKey && Near(cr.Position, spec.CasePos),
                    $"missing or misplaced Vault 111 armory case REFR {caseRefFk}");
                foreach (var pk in spec.Pickups)
                {
                    var pfk = new FormKey(Plugin, pk.OwnRefId);
                    Need(placed.TryGetValue(pfk, out var pr) && pr.Base.FormKey == pk.BaseKey &&
                         Near(pr.Position, pk.Pos) && (pk.Count == 1 ? (pr.Count ?? 1) == 1 : pr.Count == pk.Count),
                        $"missing or mismatched Vault 111 pickup REFR {pfk}");
                }
            }
        }

        if (problems.Count > 0)
        {
            foreach (var p in problems) Console.Error.WriteLine("FAIL  " + p);
            return 1;
        }
        Console.WriteLine(
            $"check: ok ({mod.Containers.Count} CONT records, 0 core CONT overrides, {modExtRefs.Count} corridor REFR overrides, " +
            $"{cells.Count} interior CELL override, {(split == SplitMode.ExtOverridesOnly ? 0 : 1 + spec.Pickups.Length)} Vault 111 REFRs)");
        return 0;
    }

    public static int Census(string pluginPath, string sfPath, string corePath, string portPath, string? outJson, string? jsonPath = null, SplitMode split = SplitMode.Full)
    {
        var spec = LoadSpec(jsonPath);
        using var sf = OpenMod(sfPath, SfEsm);
        using var core = OpenMod(corePath, SfEsm);
        using var port = OpenMod(portPath, SfEsm);
        using var mod = OpenMod(pluginPath, ExpectedMastersForSplit(split));

        ValidateStarfieldAssets(sf, spec);

        var coreConts = core.Containers.Where(c => (c.MajorRecordFlagsRaw & 0x20) == 0).ToDictionary(c => c.FormKey);
        var winningConts = new Dictionary<FormKey, IContainerGetter>(coreConts);
        foreach (var c in port.Containers.Where(c => (c.MajorRecordFlagsRaw & 0x20) == 0))
            winningConts[c.FormKey] = c;
        foreach (var c in mod.Containers.Where(c => (c.MajorRecordFlagsRaw & 0x20) == 0))
            winningConts[c.FormKey] = c;

        var modExtRefs = CollectWorldspacePlacedObjects(mod);

        int totalExtConts = 0;
        int routeWithin = 0;
        int routeModified = 0;
        int routeNonCredit = 0;
        int routeCreditsOnly = 0;
        int routeEmpty = 0;
        int outsideTotal = 0;
        int outsideModified = 0;
        var catCounts = new SortedDictionary<string, int>(StringComparer.Ordinal)
        {
            ["ammo"] = 0, ["aid"] = 0, ["junk"] = 0, ["caps"] = 0, ["untouched"] = 0,
        };

        void VisitExtCell(ICellGetter? cell)
        {
            if (cell == null) return;
            foreach (var r in cell.Persistent.Concat(cell.Temporary).OfType<IPlacedObjectGetter>())
            {
                if ((r.MajorRecordFlagsRaw & 0x20) != 0 || (r.MajorRecordFlagsRaw & 0x800) != 0) continue;
                if (!coreConts.TryGetValue(r.Base.FormKey, out var origCont))
                    continue;
                totalExtConts++;
                var effRef = modExtRefs.GetValueOrDefault(r.FormKey) ?? r;
                if (!winningConts.TryGetValue(effRef.Base.FormKey, out var effCont))
                    effCont = origCont;

                var origItems = ReadContItems(origCont);
                var effItems = ReadContItems(effCont);
                bool modified = effRef.Base.FormKey != r.Base.FormKey || !effItems.SequenceEqual(origItems);

                double d = CorridorDistance(effRef.Position.X, effRef.Position.Y, spec.Polyline);
                if (d > spec.CorridorRadiusM)
                {
                    outsideTotal++;
                    if (modified) outsideModified++;
                    continue;
                }

                routeWithin++;
                if (modified) routeModified++;

                bool hasNonCredit = effItems.Any(it => !(it.Item.ModKey == SfEsm && it.Item.ID == CreditsId) && it.Count > 0);
                if (hasNonCredit) routeNonCredit++;
                else if (effItems.Count > 0) routeCreditsOnly++;
                else routeEmpty++;

                if (TryParseFo4ContHex(effCont.EditorID, out var fo4Id) && spec.Fo4ContCategories.TryGetValue(fo4Id, out var cat))
                    catCounts[cat]++;
                else
                    catCounts["untouched"]++;
            }
        }

        foreach (var w in core.Worldspaces)
        {
            VisitExtCell(w.TopCell);
            foreach (var blk in w.SubCells)
                foreach (var sub in blk.Items)
                    foreach (var ec in sub.Items)
                        VisitExtCell(ec);
        }

        var v111Cell = mod.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells)
            .FirstOrDefault(c => c.FormKey == new FormKey(PortEsm, spec.VaultCellId));
        if (split != SplitMode.ExtOverridesOnly && v111Cell == null)
            throw new Refusal($"FO4SFRouteLoot.esm lacks Vault 111 CELL 0x{spec.VaultCellId:X6}");

        var ownCaseKey = new FormKey(Plugin, spec.OwnCaseBaseId);
        var caseItems = (split != SplitMode.ExtOverridesOnly && winningConts.TryGetValue(ownCaseKey, out var ac))
            ? ReadContItems(ac)
            : new();
        var pistolFk = new FormKey(SfEsm, spec.PistolId);
        var ammoFk = new FormKey(SfEsm, spec.AmmoId);
        var stimFk = new FormKey(CoreValuesEsm, spec.StimpakId);

        int casePistols = caseItems.Where(x => x.Item == pistolFk).Sum(x => x.Count);
        int caseAmmo = caseItems.Where(x => x.Item == ammoFk).Sum(x => x.Count);
        int caseStims = caseItems.Where(x => x.Item == stimFk).Sum(x => x.Count);

        var placedV111 = v111Cell != null ? v111Cell.Temporary.OfType<IPlacedObjectGetter>().ToList() : new List<IPlacedObjectGetter>();
        int pickupPistols = placedV111.Where(r => r.Base.FormKey == pistolFk).Sum(r => r.Count ?? 1);
        int pickupAmmo = placedV111.Where(r => r.Base.FormKey == ammoFk).Sum(r => r.Count ?? 1);
        int pickupStims = placedV111.Where(r => r.Base.FormKey == stimFk).Sum(r => r.Count ?? 1);

        int coreContOverrides = mod.Containers.Count(c => c.FormKey.ModKey == TerrainCoreEsm);
        int portContOverrides = mod.Containers.Count(c => c.FormKey.ModKey == PortEsm);
        int ownRouteContBases = mod.Containers.Count(c => c.FormKey.ModKey == Plugin && c.FormKey.ID != spec.OwnCaseBaseId);

        var v111Report = new
        {
            cell_id = $"0x{spec.VaultCellId:X6}",
            pistol_id = $"0x{spec.PistolId:X6}",
            ammo_id = $"0x{spec.AmmoId:X6}",
            stimpak_id = $"0x{spec.StimpakId:X6}",
            armory_case_base_id = $"0x{spec.OwnCaseBaseId:X6}",
            armory_case_ref_id = $"0x{spec.OwnCaseRefId:X6}",
            armory_case_pos_m = new[] { spec.CasePos.X, spec.CasePos.Y, spec.CasePos.Z },
            armory_case_pistols = casePistols,
            armory_case_ammo_rounds = caseAmmo,
            armory_case_stimpaks = caseStims,
            pickup_pistols = pickupPistols,
            pickup_ammo_rounds = pickupAmmo,
            pickup_stimpaks = pickupStims,
            total_pistols = casePistols + pickupPistols,
            total_ammo_rounds = caseAmmo + pickupAmmo,
            total_stimpaks = caseStims + pickupStims,
            pickups = placedV111.Where(r => r.FormKey.ModKey == Plugin && r.FormKey.ID != spec.OwnCaseRefId)
                .OrderBy(r => r.FormKey.ID)
                .Select(r => new
                {
                    ref_id = $"0x{r.FormKey.ID:X6}",
                    base_plugin = r.Base.FormKey.ModKey.FileName.String,
                    base_id = $"0x{r.Base.FormKey.ID:X6}",
                    count = r.Count ?? 1,
                    pos_m = new[] { Math.Round(r.Position.X, 4), Math.Round(r.Position.Y, 4), Math.Round(r.Position.Z, 4) },
                }).ToArray(),
        };

        object report = split == SplitMode.Full
            ? new
            {
                schema_version = 1,
                plugin = Plugin.FileName.String,
                corridor_radius_m = spec.CorridorRadiusM,
                corridor_polyline_m = spec.Polyline.Select(p => new[] { p.X, p.Y }).ToArray(),
                total_exterior_containers = totalExtConts,
                route_containers_within_600m = routeWithin,
                route_containers_modified = routeModified,
                route_containers_with_non_credit_items = routeNonCredit,
                route_containers_credits_only = routeCreditsOnly,
                route_containers_empty = routeEmpty,
                route_containers_by_category = catCounts,
                outside_corridor_containers = outsideTotal,
                outside_corridor_containers_modified = outsideModified,
                overridden_core_cont_bases = coreContOverrides,
                own_route_cont_bases = ownRouteContBases,
                overridden_route_container_refs = modExtRefs.Count,
                overridden_port_cont_bases = portContOverrides,
                vault111 = v111Report,
            }
            : new
            {
                schema_version = 1,
                plugin = Plugin.FileName.String,
                split = SplitLabel(split),
                corridor_radius_m = spec.CorridorRadiusM,
                corridor_polyline_m = spec.Polyline.Select(p => new[] { p.X, p.Y }).ToArray(),
                total_exterior_containers = totalExtConts,
                route_containers_within_600m = routeWithin,
                route_containers_modified = routeModified,
                route_containers_with_non_credit_items = routeNonCredit,
                route_containers_credits_only = routeCreditsOnly,
                route_containers_empty = routeEmpty,
                route_containers_by_category = catCounts,
                outside_corridor_containers = outsideTotal,
                outside_corridor_containers_modified = outsideModified,
                overridden_core_cont_bases = coreContOverrides,
                own_route_cont_bases = ownRouteContBases,
                overridden_route_container_refs = modExtRefs.Count,
                overridden_worldspaces = mod.Worldspaces.Count,
                overridden_port_cont_bases = portContOverrides,
                vault111 = v111Report,
            };

        if (outJson != null)
        {
            Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(outJson))!);
            File.WriteAllText(outJson, JsonSerializer.Serialize(report, new JsonSerializerOptions { WriteIndented = true }) + "\n");
        }

        if (coreContOverrides != 0 || outsideModified != 0)
            throw new Refusal($"census failed acceptance: core_cont_overrides={coreContOverrides}, outside_modified={outsideModified}");
        if (split == SplitMode.Full && (routeNonCredit <= 0 || casePistols < 1 || caseAmmo < spec.MinAmmoRounds || caseStims < spec.MinStimpaks))
            throw new Refusal(
                $"census failed acceptance: route_non_credit={routeNonCredit}, case_pistols={casePistols}, case_ammo={caseAmmo}, case_stims={caseStims}");
        if (split == SplitMode.BasesOnly && (ownRouteContBases <= 0 || modExtRefs.Count != 0 || mod.Worldspaces.Count != 0 ||
            casePistols < 1 || caseAmmo < spec.MinAmmoRounds || caseStims < spec.MinStimpaks))
            throw new Refusal(
                $"census failed bases-only acceptance: own_bases={ownRouteContBases}, ext_refs={modExtRefs.Count}, worldspaces={mod.Worldspaces.Count}, case_pistols={casePistols}");
        if (split == SplitMode.ExtOverridesOnly && (ownRouteContBases != 0 || mod.Containers.Count != 0 || modExtRefs.Count <= 0 || mod.Worldspaces.Count <= 0))
            throw new Refusal(
                $"census failed ext-overrides-only acceptance: own_bases={ownRouteContBases}, conts={mod.Containers.Count}, ext_refs={modExtRefs.Count}, worldspaces={mod.Worldspaces.Count}");

        Console.WriteLine(
            $"census: ok (split={SplitLabel(split)}, exterior={totalExtConts}, <=600m={routeWithin}, route_modified={routeModified}, non_credit={routeNonCredit}, " +
            $"outside_modified={outsideModified}/{outsideTotal}, Vault111 pistol=0x{spec.PistolId:X6} case_ammo={caseAmmo} total_ammo={caseAmmo + pickupAmmo})");
        return 0;
    }

    public static int SelfTest(string scratchDir)
    {
        if (Directory.Exists(scratchDir)) Directory.Delete(scratchDir, recursive: true);
        Directory.CreateDirectory(scratchDir);

        var spec = LoadSpec();
        var sfPath = Path.Combine(scratchDir, "Starfield.esm");
        var corePath = Path.Combine(scratchDir, "FO4TerrainCore.esm");
        var portPath = Path.Combine(scratchDir, "FO4Port.esm");
        var outDir = Path.Combine(scratchDir, "stage");
        var censusPath = Path.Combine(outDir, "census.json");

        // 1. Build synthetic Starfield.esm with playable pistol, matching ammo, route ammos, Credits, and CONT template.
        var sf = new StarfieldMod(SfEsm, Release);
        sf.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        sf.MiscItems.Add(new MiscItem(new FormKey(SfEsm, CreditsId), Release)
        {
            EditorID = "Synth_Credits", Model = new Model { File = @"Meshes\Synth\Credit.nif" },
        });
        foreach (var aid in new[] { spec.AmmoId, 0x04AD3Eu, 0x2B5599u, 0x2B558Du })
        {
            if (sf.Ammunitions.Any(a => a.FormKey.ID == aid)) continue;
            sf.Ammunitions.Add(new Ammunition(new FormKey(SfEsm, aid), Release)
            {
                EditorID = $"Synth_Ammo_{aid:X6}", Model = new Model { File = @"Meshes\Synth\Ammo.nif" },
            });
        }
        var pistol = new Weapon(new FormKey(SfEsm, spec.PistolId), Release)
        {
            EditorID = "Synth_Pistol",
            Model = new Model { File = @"Meshes\Synth\Pistol.nif" },
            AmmoType = new FormLinkNullable<IAmmunitionGetter>(new FormKey(SfEsm, spec.AmmoId)),
        };
        sf.Weapons.Add(pistol);
        sf.Containers.Add(new Container(new FormKey(SfEsm, spec.VaultCaseTemplateId), Release)
        {
            EditorID = "Synth_SafeTable",
            Model = new Model { File = @"Meshes\Synth\SafeTable.nif" },
            Items = new ExtendedList<ContainerEntry>(),
        });
        sf.ModHeader.Stats.NextFormID = 0x800;
        sf.BeginWrite.ToPath(sfPath).WithNoLoadOrder().NoCheckIfLowerRangeDisallowed().Write();

        // 2. Build synthetic FO4TerrainCore.esm with in-corridor (ammo, aid, junk, caps, empty) & far (>600m) containers.
        var core = new StarfieldMod(TerrainCoreEsm, Release);
        core.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        var contDefs = new (uint LocalId, string Edid, P3Float Pos)[]
        {
            (0x0A2AA8, "FO4Core_cont_038c1e_fallout4", new P3Float(-1005f, 1136f, 105f)), // ammo, on corridor
            (0x0A2A9D, "FO4Core_cont_04b6e9_fallout4", new P3Float(-1120f, 1270f, 112f)), // aid, on corridor
            (0x0A2A93, "FO4Core_cont_059a9a_fallout4", new P3Float(-815f, 1005f, 89f)),   // junk, on corridor
            (0x0A2AA9, "FO4Core_cont_180a15_fallout4", new P3Float(-900f, 1070f, 95f)),   // caps, on corridor
            (0x0A2AFA, "FO4Core_cont_04424d_fallout4", new P3Float(-950f, 1100f, 98f)),   // empty, untouched
            (0x0A2B00, "FO4Core_cont_0ae537_fallout4", new P3Float(1500f, -1500f, 10f)),  // >600m outside corridor
        };
        var wrld = new Worldspace(new FormKey(TerrainCoreEsm, 0x000802), Release)
        {
            EditorID = "FO4Core_Commonwealth",
            TopCell = new Cell(new FormKey(TerrainCoreEsm, 0x001805), Release),
        };
        var extCell = new Cell(new FormKey(TerrainCoreEsm, 0x000900), Release)
        {
            Grid = new CellGrid { Point = new P2Int(-10, 11) },
        };
        uint refNext = 0x004000;
        foreach (var (lid, edid, pos) in contDefs)
        {
            var c = new Container(new FormKey(TerrainCoreEsm, lid), Release)
            {
                EditorID = edid,
                Model = new Model { File = @"Meshes\Synth\Crate.nif" },
                Items = MakeContainerItems(new[] { new LootEntry(SfEsm, CreditsId, 10) }),
            };
            core.Containers.Add(c);
            extCell.Temporary.Add(new PlacedObject(new FormKey(TerrainCoreEsm, refNext++), Release)
            {
                Base = new FormLinkNullable<IPlaceableObjectGetter>(c.FormKey),
                Position = pos,
            });
        }
        // B10 proof: place a SECOND container REFR >600m away sharing the exact same ammo base 0x0A2AA8;
        // it must stay 100% untouched while the corridor REFR of 0x0A2AA8 gets ammo loot.
        extCell.Temporary.Add(new PlacedObject(new FormKey(TerrainCoreEsm, refNext++), Release)
        {
            Base = new FormLinkNullable<IPlaceableObjectGetter>(new FormKey(TerrainCoreEsm, 0x0A2AA8)),
            Position = new P3Float(1600f, -1600f, 12f),
        });
        var wBlk = new WorldspaceBlock { BlockNumberX = -1, BlockNumberY = 0, GroupType = GroupTypeEnum.ExteriorCellBlock };
        var wSub = new WorldspaceSubBlock { BlockNumberX = -2, BlockNumberY = 1, GroupType = GroupTypeEnum.ExteriorCellSubBlock };
        wSub.Items.Add(extCell);
        wBlk.Items.Add(wSub);
        wrld.SubCells.Add(wBlk);
        core.Worldspaces.Add(wrld);
        core.WriteToBinary(corePath, new BinaryWriteParameters
        {
            ModKey = ModKeyOption.NoCheck,
            MastersListOrdering = new MastersListOrderingByLoadOrder(new[] { SfEsm }),
            MasterFlagsLookup = Styles(SfEsm),
        });

        // 3. Build synthetic FO4Port.esm with Vault 111 cell 0x0011F3 + locker CONT 0x00E0D6.
        var port = new StarfieldMod(PortEsm, Release);
        port.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        port.Containers.Add(new Container(new FormKey(PortEsm, spec.PortLockerContId), Release)
        {
            EditorID = "FO4Port_cont_090e68_fallout4",
            Model = new Model { File = @"Meshes\Synth\Locker.nif" },
            Items = MakeContainerItems(new[] { new LootEntry(SfEsm, CreditsId, 10) }),
        });
        var vCell = new Cell(new FormKey(PortEsm, spec.VaultCellId), Release)
        {
            EditorID = "FO4Port_Vault111Cryo",
            Flags = Cell.Flag.IsInteriorCell,
        };
        var pBlk = new CellBlock { BlockNumber = (int)(spec.VaultCellId % 10), GroupType = GroupTypeEnum.InteriorCellBlock };
        var pSub = new CellSubBlock { BlockNumber = (int)((spec.VaultCellId / 10) % 10), GroupType = GroupTypeEnum.InteriorCellSubBlock };
        pSub.Cells.Add(vCell);
        pBlk.SubBlocks.Add(pSub);
        port.Cells.Records.Add(pBlk);
        port.WriteToBinary(portPath, new BinaryWriteParameters
        {
            ModKey = ModKeyOption.NoCheck,
            MastersListOrdering = new MastersListOrderingByLoadOrder(new[] { SfEsm }),
            MasterFlagsLookup = Styles(SfEsm),
        });

        // 4. Positive build + check + census.
        if (Build(sfPath, corePath, portPath, outDir) != 0)
            throw new Refusal("selftest Build failed");
        var builtPlugin = Path.Combine(outDir, Plugin.FileName);
        if (Check(builtPlugin, sfPath, corePath, portPath) != 0)
            throw new Refusal("selftest Check failed");
        if (Census(builtPlugin, sfPath, corePath, portPath, censusPath) != 0)
            throw new Refusal("selftest Census failed");

        using (var cdoc = JsonDocument.Parse(File.ReadAllText(censusPath)))
        {
            var cr = cdoc.RootElement;
            if (cr.GetProperty("total_exterior_containers").GetInt32() != 7 ||
                cr.GetProperty("route_containers_within_600m").GetInt32() != 5 ||
                cr.GetProperty("route_containers_with_non_credit_items").GetInt32() != 3 ||
                cr.GetProperty("outside_corridor_containers").GetInt32() != 2 ||
                cr.GetProperty("outside_corridor_containers_modified").GetInt32() != 0 ||
                cr.GetProperty("overridden_core_cont_bases").GetInt32() != 0 ||
                cr.GetProperty("overridden_route_container_refs").GetInt32() != 4)
                throw new Refusal("selftest census counts mismatch");
            var vr = cr.GetProperty("vault111");
            if (vr.GetProperty("armory_case_ammo_rounds").GetInt32() < 48 ||
                vr.GetProperty("armory_case_pistols").GetInt32() < 1 ||
                vr.GetProperty("armory_case_stimpaks").GetInt32() < 2)
                throw new Refusal("selftest Vault 111 counts below threshold");
        }

        // 5. Negative tamper control: drop ammo below 48 in armory case and confirm Check refuses.
        var badDir = Path.Combine(scratchDir, "bad");
        Directory.CreateDirectory(badDir);
        var badMod = StarfieldMod.CreateFromBinary(builtPlugin, Release, new BinaryReadParameters { MasterFlagsLookup = Styles(ExpectedMasters) });
        var badCase = badMod.Containers.First(c => c.FormKey == new FormKey(Plugin, spec.OwnCaseBaseId));
        badCase.Items!.Clear();
        badCase.Items.Add(new ContainerEntry { Item = new ContainerItem { Item = new FormLink<IItemGetter>(new FormKey(SfEsm, spec.PistolId)), Count = 1 } });
        badCase.Items.Add(new ContainerEntry { Item = new ContainerItem { Item = new FormLink<IItemGetter>(new FormKey(SfEsm, spec.AmmoId)), Count = 12 } });
        WriteAtomic(badMod, badDir);
        if (Check(Path.Combine(badDir, Plugin.FileName), sfPath, corePath, portPath) == 0)
            throw new Refusal("selftest Check accepted tampered <48 ammo plugin");

        // 6. T1 split builds: bases-only vs ext-overrides-only + negative tamper controls.
        var basesDir = Path.Combine(scratchDir, "stage-bases-only");
        var basesCensus = Path.Combine(basesDir, "census.json");
        if (Build(sfPath, corePath, portPath, basesDir, split: SplitMode.BasesOnly) != 0)
            throw new Refusal("selftest Build bases-only failed");
        var basesPlugin = Path.Combine(basesDir, Plugin.FileName);
        if (Check(basesPlugin, sfPath, corePath, portPath, split: SplitMode.BasesOnly) != 0)
            throw new Refusal("selftest Check bases-only failed");
        if (Census(basesPlugin, sfPath, corePath, portPath, basesCensus, split: SplitMode.BasesOnly) != 0)
            throw new Refusal("selftest Census bases-only failed");
        if (Check(basesPlugin, sfPath, corePath, portPath, split: SplitMode.Full) == 0)
            throw new Refusal("selftest Check full accepted bases-only plugin");

        var extDir = Path.Combine(scratchDir, "stage-ext-overrides-only");
        var extCensus = Path.Combine(extDir, "census.json");
        if (Build(sfPath, corePath, portPath, extDir, split: SplitMode.ExtOverridesOnly) != 0)
            throw new Refusal("selftest Build ext-overrides-only failed");
        var extPlugin = Path.Combine(extDir, Plugin.FileName);
        if (Check(extPlugin, sfPath, corePath, portPath, split: SplitMode.ExtOverridesOnly) != 0)
            throw new Refusal("selftest Check ext-overrides-only failed");
        if (Census(extPlugin, sfPath, corePath, portPath, extCensus, split: SplitMode.ExtOverridesOnly) != 0)
            throw new Refusal("selftest Census ext-overrides-only failed");
        if (Check(extPlugin, sfPath, corePath, portPath, split: SplitMode.Full) == 0)
            throw new Refusal("selftest Check full accepted ext-overrides-only plugin");

        Console.WriteLine("selftest: PASS");
        return 0;
    }
}
