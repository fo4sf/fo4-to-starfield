// ALifeMod: the standalone Starfield A-Life plugin writer for the modder SDK (docs/alife/MODDER-GUIDE.md). It turns any
// validated alife_config.json, or the payload src/fo4sf/alife/schema.py exports from it, into one ready-to-ship .esm
// that needs Starfield.esm plus only the plugins the config's worldspace and squad templates live in.
//
//   build <Starfield.esm> <config-or-payload.json> <out dir> [--extra-master <plugin> ...]
//        writes <out dir>/<plugin_name> (atomically, through a temporary file):
//          0x800        QUST <Prefix>_ALifeSim  start game enabled, starts enabled, repeatable stages; VMAD
//                       FO4SF_ALifeSimQuest with every property the runtime declares (Properties below)
//          0x801-0x804  GLOB <Prefix>_SimEnabled / _OnlineRadius / _MaxSquads / _Notifications (not constant)
//          0x805-0x807  GPOF <Prefix>_GPO_Enabled (0/1) / _GPO_MaxSquads (1..16) / _GPO_Notifications (0/1)
//          0x808        GPOG <Prefix>_GPOG listing the three options (Settings -> Gameplay)
//          0x809        MGEF <Prefix>_TransponderEffect  script archetype, VMAD FO4SF_ALifeBeaconEffect
//          0x80A        ALCH <Prefix>_FieldTransponder   cloned from a Starfield.esm ingestible, one effect: the MGEF
//          0x810+       persistent XMarkerHeading REFRs <Prefix>_Waymarker_NN in the target WRLD's persistent cell
//                       (WRLD + persistent CELL override holding only them; no foreign reference is copied)
//          0x820+i      FACT per faction, relations to PlayerFaction and to every other faction
//          0x828+i      NPC_ per faction, cloned from its npc_template: no scripts, no foreign factions, in its FACT
//                       only, neither unique, essential, protected nor respawning, AI = DefaultTravelToLinkedRef
//        Header: Master; Light (Small) too when light_master is set and every new record fits the light range.
//   check <built.esm> <Starfield.esm> <config-or-payload.json> [--extra-master <plugin> ...]
//        reads the plugin back and checks every record, link, flag, master and property value (exit 1 on a problem).
//   selftest <scratch dir>
//        synthetic Starfield.esm and a synthetic custom-world master: builds + checks (vanilla, light, custom world,
//        128-node), then invalid configs build must refuse and tampered outputs check must reject. No game file read.
// Exit codes: 0 ok, 1 check failed, 2 refused / usage. Nothing is deployed and no game file is written.
using System.Globalization;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;
using Mutagen.Bethesda;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Cache;
using Mutagen.Bethesda.Plugins.Records;
using Noggog;
using SF = Mutagen.Bethesda.Starfield;

if (args.Length == 0) return ALifeMod.Usage();
try
{
    var extras = new List<string>();
    var pos = new List<string>();
    for (int i = 0; i < args.Length; i++)
    {
        if (args[i] == "--extra-master")
        {
            if (i + 1 >= args.Length) throw new ALifeMod.Refusal("--extra-master needs a plugin path");
            extras.Add(args[++i]);
        }
        else pos.Add(args[i]);
    }
    return pos switch
    {
        ["build", var sf, var cfg, var outDir] => ALifeMod.Build(sf, cfg, outDir, extras),
        ["check", var plug, var sf, var cfg] => ALifeMod.Check(plug, sf, cfg, extras),
        ["selftest", var dir] when extras.Count == 0 => ALifeMod.SelfTest(dir),
        _ => ALifeMod.Usage(),
    };
}
catch (ALifeMod.Refusal e)
{
    Console.Error.WriteLine("refused: " + e.Message);
    return 2;
}

public static class ALifeMod
{
    public class Refusal(string m) : Exception(m);

    const SF.StarfieldRelease Rel = SF.StarfieldRelease.Starfield;
    static readonly ModKey SfEsm = ModKey.FromFileName("Starfield.esm");

    public const string QuestScript = "FO4SF_ALifeSimQuest", BeaconScript = "FO4SF_ALifeBeaconEffect";
    public const uint QuestId = 0x800, SimEnabledId = 0x801, OnlineRadiusId = 0x802, MaxSquadsId = 0x803, NotificationsId = 0x804;
    public const uint OptEnabledId = 0x805, OptMaxSquadsId = 0x806, OptNotificationsId = 0x807, GpogId = 0x808;
    public const uint EffectId = 0x809, TransponderId = 0x80A, FirstWaymarkerId = 0x810, FirstFactionId = 0x820, FirstNpcId = 0x828;
    public const int MinPool = 4, MaxPool = 16, MaxFactions = 8, MaxSquadSize = 8, MaxSquads = 16, ArrayCap = 128;
    public const float HysteresisM = 50f;
    public const uint LightMaxId = 0xFFF;
    public const uint PlayerFactionId = 0x01C21C; public const string PlayerFactionEdid = "PlayerFaction";
    public const uint XMarkerHeadingId = 0x000034; public const string XMarkerHeadingEdid = "XMarkerHeading";
    public const string TravelPackageEdid = "DefaultTravelToLinkedRef";
    public static readonly string[] NodeKinds = { "relay", "base", "checkpoint", "lair", "resource" };

    /// FO4SF_ALifeSimQuest's Auto Const properties (scripts/alife/FO4SF_ALifeSimQuest.psc), in the order written.
    public static readonly string[] Properties =
    {
        "SquadTemplates", "SquadFactions", "FactionSquadSize", "FactionPower", "FactionRelationsFlat", "Waymarkers",
        "NodeX", "NodeY", "NodeZ", "NodeCap", "NodeKind", "NodeInitialOwner", "NodeSpawnFaction", "EdgeU", "EdgeV", "EdgeLen",
        "MergeOffsetX", "MergeOffsetY", "OnlineSpawnRadiusM", "OfflineDespawnRadiusM", "OfflineSpeedMps", "TickIntervalS",
        "MaxActiveSquads", "RespawnCooldownS", "SimEnabledGlobal", "OnlineRadiusGlobal", "MaxSquadsGlobal", "NotificationsGlobal",
        "OptEnabled", "OptMaxSquads", "OptNotifications", "FieldTransponder",
    };
    /// FO4SF_ALifeBeaconEffect's properties (scripts/alife/FO4SF_ALifeBeaconEffect.psc).
    public static readonly string[] BeaconProperties = { "SimQuest", "FieldTransponder" };

    public static int Usage()
    {
        Console.Error.WriteLine("usage: ALifeMod build <Starfield.esm> <config.json> <out dir> [--extra-master <plugin> ...] | " +
                                "check <built.esm> <Starfield.esm> <config.json> [--extra-master <plugin> ...] | selftest <scratch dir>");
        return 2;
    }
    static string F(float v) => v.ToString("0.###", CultureInfo.InvariantCulture);

    // ================================================================ config

    public sealed record FactionCfg(int Index, string Id, string Name, string Edid, string NpcEdid, ModKey TplPlugin, uint TplId, string? TplEdid,
                                    int PlayerRel, int SquadSize, float Power);
    public sealed record NodeCfg(int Index, string Id, int Kind, float X, float Y, float Z, int Cap, int Owner, int Spawn);
    public sealed record EdgeCfg(int U, int V, float Len);
    public sealed record Config(string ModName, string PluginName, string Prefix, bool Light, List<ModKey> Masters,
                                ModKey WorldPlugin, uint WorldId, string WorldEdid, float MergeX, float MergeY,
                                bool DefaultEnabled, float Tick, float Speed, float OnlineR, float OfflineR, int Pool, int MaxActive,
                                float Cooldown, bool Notifications, List<FactionCfg> Factions, int[] RelFlat, List<NodeCfg> Nodes,
                                List<EdgeCfg> Edges)
    {
        public ModKey Key => ModKey.FromFileName(PluginName);
        /// where the waymarkers start: the first spawning node, in merged world coordinates
        public (float X, float Y, float Z) Start
        {
            get { var n = Nodes.First(x => x.Spawn >= 0); return (n.X + MergeX, n.Y + MergeY, n.Z); }
        }
        public Dictionary<string, object> FlatProperties() => new()
        {
            ["FactionSquadSize"] = Factions.Select(f => f.SquadSize).ToArray(),
            ["FactionPower"] = Factions.Select(f => f.Power).ToArray(),
            ["FactionRelationsFlat"] = RelFlat,
            ["NodeX"] = Nodes.Select(n => n.X).ToArray(), ["NodeY"] = Nodes.Select(n => n.Y).ToArray(), ["NodeZ"] = Nodes.Select(n => n.Z).ToArray(),
            ["NodeCap"] = Nodes.Select(n => n.Cap).ToArray(), ["NodeKind"] = Nodes.Select(n => n.Kind).ToArray(),
            ["NodeInitialOwner"] = Nodes.Select(n => n.Owner).ToArray(), ["NodeSpawnFaction"] = Nodes.Select(n => n.Spawn).ToArray(),
            ["EdgeU"] = Edges.Select(e => e.U).ToArray(), ["EdgeV"] = Edges.Select(e => e.V).ToArray(), ["EdgeLen"] = Edges.Select(e => e.Len).ToArray(),
            ["MergeOffsetX"] = MergeX, ["MergeOffsetY"] = MergeY, ["OnlineSpawnRadiusM"] = OnlineR, ["OfflineDespawnRadiusM"] = OfflineR,
            ["OfflineSpeedMps"] = Speed, ["TickIntervalS"] = Tick, ["MaxActiveSquads"] = MaxActive, ["RespawnCooldownS"] = Cooldown,
        };
        public Dictionary<string, float> GlobalValues() => new()
        {
            ["SimEnabled"] = DefaultEnabled ? 1f : 0f, ["OnlineRadius"] = OnlineR, ["MaxSquads"] = MaxActive, ["Notifications"] = Notifications ? 1f : 0f,
        };
    }

    static readonly Regex EdidRx = new("^[A-Za-z0-9_]{1,96}$"), PluginRx = new(@"^[A-Za-z0-9 _\-\.]{1,120}\.(esm|esp|esl)$", RegexOptions.IgnoreCase);

    static bool Has(JsonElement o, string k) => o.ValueKind == JsonValueKind.Object && o.TryGetProperty(k, out var v) && v.ValueKind != JsonValueKind.Null;
    static JsonElement Req(JsonElement o, string k, string ctx) =>
        o.ValueKind == JsonValueKind.Object && o.TryGetProperty(k, out var v) && v.ValueKind != JsonValueKind.Null ? v : throw new Refusal($"{ctx}: missing '{k}'");
    static float NumOf(JsonElement v, string what)
    {
        if (v.ValueKind != JsonValueKind.Number) throw new Refusal($"{what} is not a number");
        var f = (float)v.GetDouble();
        return float.IsFinite(f) ? f : throw new Refusal($"{what} is not a finite 32-bit number");
    }
    static float Num(JsonElement o, string k, string ctx, float? dflt = null) =>
        Has(o, k) ? NumOf(o.GetProperty(k), $"{ctx}.{k}") : dflt ?? throw new Refusal($"{ctx}: missing '{k}'");
    static int IntOf(JsonElement v, string what) =>
        v.ValueKind == JsonValueKind.Number && v.TryGetInt32(out var i) ? i : throw new Refusal($"{what} is not an integer");
    static int Int(JsonElement o, string k, string ctx, int? dflt = null) =>
        Has(o, k) ? IntOf(o.GetProperty(k), $"{ctx}.{k}") : dflt ?? throw new Refusal($"{ctx}: missing '{k}'");
    static bool Bool(JsonElement o, string k, string ctx, bool? dflt = null)
    {
        if (!Has(o, k)) return dflt ?? throw new Refusal($"{ctx}: missing '{k}'");
        var v = o.GetProperty(k);
        return v.ValueKind switch
        {
            JsonValueKind.True => true, JsonValueKind.False => false,
            JsonValueKind.Number when v.TryGetInt32(out var i) && (i == 0 || i == 1) => i == 1,
            _ => throw new Refusal($"{ctx}.{k} is not a boolean"),
        };
    }
    static string Str(JsonElement o, string k, string ctx)
    {
        var v = Req(o, k, ctx);
        return v.ValueKind == JsonValueKind.String && !string.IsNullOrWhiteSpace(v.GetString()) ? v.GetString()! : throw new Refusal($"{ctx}.{k} is not a non-empty string");
    }
    /// a plugin-relative FormID: hex, optional 0x, 1..8 digits; a load-order byte is dropped
    public static uint ParseFormId(string s, string what)
    {
        var t = s.Trim();
        if (t.StartsWith("0x", StringComparison.OrdinalIgnoreCase)) t = t[2..];
        if (t.Length is < 1 or > 8 || !uint.TryParse(t, NumberStyles.AllowHexSpecifier, CultureInfo.InvariantCulture, out var v))
            throw new Refusal($"{what} '{s}' is not a hex FormID");
        v &= 0xFFFFFF;
        return v != 0 ? v : throw new Refusal($"{what} '{s}' is the null FormID");
    }
    static int Relation(JsonElement v, string what)
    {
        if (v.ValueKind == JsonValueKind.Number) { var i = IntOf(v, what); return i is >= -1 and <= 1 ? i : throw new Refusal($"{what} {i} is not -1, 0 or 1"); }
        return (v.ValueKind == JsonValueKind.String ? v.GetString()!.ToLowerInvariant() : "") switch
        {
            "ally" => 1, "neutral" => 0, "enemy" => -1, _ => throw new Refusal($"{what} is not ally, neutral or enemy"),
        };
    }
    static ModKey PluginKey(string name, string what)
    {
        if (!PluginRx.IsMatch(name)) throw new Refusal($"{what} '{name}' is not a plugin file name");
        return ModKey.FromFileName(name);
    }

    /// Loads and validates a modder config or a schema payload; refuses anything the runtime or the engine cannot take.
    public static Config LoadConfig(string path)
    {
        JsonElement j;
        try { j = JsonDocument.Parse(File.ReadAllText(path)).RootElement; }
        catch (Exception e) when (e is JsonException or IOException) { throw new Refusal($"cannot read config {Path.GetFileName(path)}: {e.Message}"); }
        if (j.ValueKind != JsonValueKind.Object) throw new Refusal("config is not a JSON object");
        if (Has(j, "schema_version") && Int(j, "schema_version", "config") != 1) throw new Refusal("schema_version is not 1");
        if (Has(j, "payload_version") && Int(j, "payload_version", "config") != 1) throw new Refusal("payload_version is not 1");

        var pluginName = Str(j, "plugin_name", "config");
        if (!pluginName.EndsWith(".esm", StringComparison.OrdinalIgnoreCase)) throw new Refusal($"plugin_name '{pluginName}' must be an .esm");
        var key = PluginKey(pluginName, "plugin_name");
        if (key == SfEsm) throw new Refusal("plugin_name cannot be Starfield.esm");
        var stem = Regex.Replace(Path.GetFileNameWithoutExtension(pluginName), "[^A-Za-z0-9]", "");
        var prefix = Has(j, "editor_prefix") ? Str(j, "editor_prefix", "config") : stem;
        if (!Regex.IsMatch(prefix, "^[A-Za-z][A-Za-z0-9]{0,39}$")) throw new Refusal($"editor_prefix '{prefix}' must be 1..40 letters/digits starting with a letter");
        var modName = Has(j, "mod_name") ? Str(j, "mod_name", "config") : stem;
        if (modName.Length > 80) throw new Refusal("mod_name is longer than 80 characters");
        bool light = Bool(j, "light_master", "config", false);

        var w = Req(j, "worldspace", "config");
        var worldPlugin = PluginKey(Str(w, "plugin", "worldspace"), "worldspace.plugin");
        var worldId = ParseFormId(Str(w, "form_id", "worldspace"), "worldspace.form_id");
        if (worldPlugin != SfEsm && worldId < 0x800) throw new Refusal("worldspace.form_id below 0x800 in a non-Starfield.esm plugin");
        var worldEdid = Str(w, "editor_id", "worldspace");
        float mx = 0, my = 0;
        if (Has(w, "merge_offset_xy"))
        {
            var m = w.GetProperty("merge_offset_xy");
            if (m.ValueKind != JsonValueKind.Array || m.GetArrayLength() != 2) throw new Refusal("worldspace.merge_offset_xy is not [x, y]");
            mx = NumOf(m[0], "merge_offset_xy[0]"); my = NumOf(m[1], "merge_offset_xy[1]");
        }

        var s = Req(j, "simulation", "config");
        bool enabled = Bool(s, "default_enabled", "simulation", true);
        float tick = Num(s, "tick_real_s", "simulation", 2.0f), speed = Num(s, "offline_step_m_per_s", "simulation", 1.35f);
        float onR = Num(s, "online_spawn_radius_m", "simulation", 450f), offR = Num(s, "offline_despawn_radius_m", "simulation", 620f);
        int pool = Int(s, "waymarker_pool_size", "simulation", 8), maxActive = Int(s, "max_active_squads", "simulation", 8);
        float cooldown = Num(s, "respawn_cooldown_s", "simulation", 120f);
        bool notes = Bool(s, "show_notifications", "simulation", true);
        if (Has(j, "waymarker_pool_size") && Int(j, "waymarker_pool_size", "config") != pool) throw new Refusal("waymarker_pool_size disagrees with simulation.waymarker_pool_size");
        if (tick <= 0 || tick > 60) throw new Refusal($"simulation.tick_real_s {F(tick)}: 0 < tick <= 60");
        if (speed <= 0 || speed > 50) throw new Refusal($"simulation.offline_step_m_per_s {F(speed)}: 0 < speed <= 50");
        if (onR <= 0) throw new Refusal("simulation.online_spawn_radius_m must be positive");
        if (offR <= onR + HysteresisM) throw new Refusal($"hysteresis: offline_despawn_radius_m {F(offR)} must exceed online_spawn_radius_m {F(onR)} + {F(HysteresisM)}");
        if (pool < MinPool || pool > MaxPool) throw new Refusal($"waymarker_pool_size {pool}: {MinPool}..{MaxPool}");
        if (maxActive < 1 || maxActive > MaxSquads) throw new Refusal($"max_active_squads {maxActive}: 1..{MaxSquads}");
        if (cooldown < 0) throw new Refusal("simulation.respawn_cooldown_s is negative");

        // factions
        var fj = Req(j, "factions", "config");
        if (fj.ValueKind != JsonValueKind.Array) throw new Refusal("factions is not a list");
        int fc = fj.GetArrayLength();
        if (fc < 1 || fc > MaxFactions) throw new Refusal($"{fc} factions: 1..{MaxFactions}");
        var rawF = fj.EnumerateArray().Select((f, i) => (f, idx: Int(f, "index", $"factions[{i}]", i))).OrderBy(t => t.idx).ToList();
        if (!rawF.Select(t => t.idx).SequenceEqual(Enumerable.Range(0, fc))) throw new Refusal("faction indices are not 0..F-1, each once");
        var ids = rawF.Select((t, i) => Str(t.f, "id", $"factions[{i}]")).ToList();
        if (ids.Distinct(StringComparer.Ordinal).Count() != fc) throw new Refusal("faction ids are not unique");
        var factions = new List<FactionCfg>();
        var flat = new int[fc * fc];
        for (int a = 0; a < fc; a++)
        {
            var f = rawF[a].f; var ctx = $"faction {ids[a]}";
            var tpl = Req(f, "npc_template", ctx);
            var tplPlugin = PluginKey(Str(tpl, "plugin", ctx + ".npc_template"), ctx + ".npc_template.plugin");
            var tplId = ParseFormId(Str(tpl, "form_id", ctx + ".npc_template"), ctx + ".npc_template.form_id");
            if (tplPlugin != SfEsm && tplId < 0x800) throw new Refusal($"{ctx}.npc_template.form_id below 0x800 in a non-Starfield.esm plugin");
            int prel = Relation(Req(f, "player_relation", ctx), ctx + ".player_relation");
            if (Has(f, "player_reaction") && Relation(f.GetProperty("player_reaction"), ctx + ".player_reaction") != prel)
                throw new Refusal($"{ctx}: player_reaction disagrees with player_relation");
            int size = Int(f, "squad_size", ctx);
            if (size < 1 || size > MaxSquadSize) throw new Refusal($"{ctx}.squad_size {size}: 1..{MaxSquadSize}");
            float power = Num(f, "combat_power", ctx);
            if (power <= 0 || power > 1000) throw new Refusal($"{ctx}.combat_power {F(power)}: 0 < power <= 1000");
            var safe = Regex.Replace(ids[a], "[^A-Za-z0-9]", "");
            if (safe.Length == 0) throw new Refusal($"{ctx}: id has no letters or digits");
            var edid = Has(f, "editor_id") ? Str(f, "editor_id", ctx) : $"{prefix}_Faction_{safe}";
            if (!EdidRx.IsMatch(edid)) throw new Refusal($"{ctx}.editor_id '{edid}' is not an EditorID");
            var name = Has(f, "name") ? Str(f, "name", ctx) : ids[a];
            if (name.Length > 80) throw new Refusal($"{ctx}.name is longer than 80 characters");
            var tplEdid = Has(tpl, "editor_id") ? Str(tpl, "editor_id", ctx + ".npc_template") : null;
            factions.Add(new FactionCfg(a, ids[a], name, edid, $"{prefix}_Squad_{safe}", tplPlugin, tplId, tplEdid, prel, size, power));
            for (int b = 0; b < fc; b++) flat[a * fc + b] = a == b ? 1 : 0;
            if (Has(f, "relations"))
            {
                var r = f.GetProperty("relations");
                if (r.ValueKind != JsonValueKind.Object) throw new Refusal($"{ctx}.relations is not an object");
                foreach (var p in r.EnumerateObject())
                {
                    int b = ids.IndexOf(p.Name);
                    if (b < 0) throw new Refusal($"{ctx}.relations names unknown faction '{p.Name}'");
                    int v = Relation(p.Value, $"{ctx}.relations.{p.Name}");
                    if (b == a && v != 1) throw new Refusal($"{ctx} is not an ally of itself");
                    flat[a * fc + b] = v;
                }
            }
        }
        for (int a = 0; a < fc; a++)
            for (int b = 0; b < fc; b++)
                if (flat[a * fc + b] != flat[b * fc + a]) throw new Refusal($"relations are not symmetric: {ids[a]} -> {ids[b]} differs from {ids[b]} -> {ids[a]}");
        if (factions.Select(f => f.Edid).Distinct(StringComparer.OrdinalIgnoreCase).Count() != fc) throw new Refusal("faction editor_ids are not unique");
        if (factions.Select(f => f.NpcEdid).Distinct(StringComparer.OrdinalIgnoreCase).Count() != fc) throw new Refusal("faction ids collide after removing punctuation");

        int FactionRef(JsonElement o, string k, string ctx)
        {
            if (!Has(o, k)) return -1;
            var v = o.GetProperty(k);
            int i = v.ValueKind == JsonValueKind.String ? ids.IndexOf(v.GetString()!) is var x && x >= 0 ? x : throw new Refusal($"{ctx}.{k} names unknown faction '{v.GetString()}'")
                                                        : IntOf(v, $"{ctx}.{k}");
            return i >= -1 && i < fc ? i : throw new Refusal($"{ctx}.{k} {i} is not a faction index or -1");
        }

        // nodes
        var nj = Req(j, "nodes", "config");
        if (nj.ValueKind != JsonValueKind.Array) throw new Refusal("nodes is not a list");
        int nc = nj.GetArrayLength();
        if (nc < 2 || nc > ArrayCap) throw new Refusal($"{nc} nodes: 2..{ArrayCap} fit a Papyrus array");
        var rawN = nj.EnumerateArray().Select((n, i) => (n, idx: Int(n, "index", $"nodes[{i}]", i))).OrderBy(t => t.idx).ToList();
        if (!rawN.Select(t => t.idx).SequenceEqual(Enumerable.Range(0, nc))) throw new Refusal("node indices are not 0..N-1, each once");
        var nodes = new List<NodeCfg>();
        foreach (var (n, i) in rawN)
        {
            var id = Has(n, "id") ? Str(n, "id", $"nodes[{i}]") : $"N{i}";
            var ctx = $"node {i} ({id})";
            var kv = Req(n, "kind", ctx);
            int kind = kv.ValueKind == JsonValueKind.String ? Array.IndexOf(NodeKinds, kv.GetString()!.ToLowerInvariant()) : IntOf(kv, ctx + ".kind");
            if (kind < 0 || kind >= NodeKinds.Length) throw new Refusal($"{ctx}.kind is not one of {string.Join("/", NodeKinds)}");
            int cap = Int(n, "capacity", ctx);
            if (cap < 0 || cap > MaxSquads) throw new Refusal($"{ctx}.capacity {cap}: 0..{MaxSquads}");
            if (kind == 0 && cap != 0) throw new Refusal($"{ctx}: a relay node has capacity 0");
            var node = new NodeCfg(i, id, kind, Num(n, "x", ctx), Num(n, "y", ctx), Num(n, "z", ctx), cap,
                                   FactionRef(n, "initial_owner", ctx), FactionRef(n, "spawn_faction", ctx));
            if (node.Spawn >= 0 && cap == 0) throw new Refusal($"{ctx} spawns squads but cannot garrison (capacity 0)");
            if (!float.IsFinite(node.X + mx) || !float.IsFinite(node.Y + my)) throw new Refusal($"{ctx}: merged position overflows");
            nodes.Add(node);
        }
        if (nodes.Select(n => n.Id).Distinct(StringComparer.Ordinal).Count() != nc) throw new Refusal("node ids are not unique");
        if (!nodes.Any(n => n.Spawn >= 0)) throw new Refusal("no node spawns squads (spawn_faction >= 0)");

        // edges
        var ej = Req(j, "edges", "config");
        if (ej.ValueKind != JsonValueKind.Array) throw new Refusal("edges is not a list");
        int ec = ej.GetArrayLength();
        if (ec < 1 || ec > ArrayCap) throw new Refusal($"{ec} edges: 1..{ArrayCap} fit a Papyrus array");
        int NodeRef(JsonElement v, string what) =>
            v.ValueKind == JsonValueKind.String ? nodes.FindIndex(n => n.Id == v.GetString()) is var x && x >= 0 ? x : throw new Refusal($"{what} names unknown node '{v.GetString()}'")
                                                : IntOf(v, what);
        var edges = new List<EdgeCfg>();
        var seen = new HashSet<(int, int)>();
        foreach (var (e, i) in ej.EnumerateArray().Select((e, i) => (e, i)))
        {
            var ctx = $"edge {i}";
            int u = NodeRef(Req(e, "u", ctx), ctx + ".u"), v = NodeRef(Req(e, "v", ctx), ctx + ".v");
            float len = Num(e, "len_m", ctx);
            if (u < 0 || u >= nc || v < 0 || v >= nc || u == v) throw new Refusal($"{ctx} ({u}, {v}) is not between two distinct nodes");
            if (len <= 0) throw new Refusal($"{ctx} ({u}, {v}) length {F(len)} is not positive");
            if (!seen.Add((Math.Min(u, v), Math.Max(u, v)))) throw new Refusal($"{ctx} ({u}, {v}) duplicates an earlier edge");
            edges.Add(new EdgeCfg(u, v, len));
        }
        var reach = new bool[nc]; var stack = new Stack<int>(); stack.Push(0); reach[0] = true;
        while (stack.Count > 0)
        {
            int x = stack.Pop();
            foreach (var e in edges)
            {
                int y = e.U == x ? e.V : e.V == x ? e.U : -1;
                if (y >= 0 && !reach[y]) { reach[y] = true; stack.Push(y); }
            }
        }
        if (reach.Any(r => !r)) throw new Refusal($"the graph is disconnected: node {Array.IndexOf(reach, false)} cannot be reached from node 0");

        // masters: Starfield.esm first, then exactly the plugins the worldspace and the templates live in
        var referenced = new List<ModKey> { SfEsm };
        foreach (var k in new[] { worldPlugin }.Concat(factions.Select(f => f.TplPlugin)))
            if (!referenced.Contains(k)) referenced.Add(k);
        List<ModKey> masters;
        if (Has(j, "masters"))
        {
            var mj = j.GetProperty("masters");
            if (mj.ValueKind != JsonValueKind.Array) throw new Refusal("masters is not a list");
            masters = mj.EnumerateArray().Select((m, i) => m.ValueKind == JsonValueKind.String ? PluginKey(m.GetString()!, $"masters[{i}]") : throw new Refusal($"masters[{i}] is not a string")).ToList();
            if (masters.Count == 0 || masters[0] != SfEsm) throw new Refusal("masters must start with Starfield.esm");
            if (masters.Distinct().Count() != masters.Count) throw new Refusal("masters lists a plugin twice");
            if (masters.Contains(key)) throw new Refusal("masters lists the plugin itself");
            var missing = referenced.Where(r => !masters.Contains(r)).ToList();
            if (missing.Count > 0) throw new Refusal($"masters lacks referenced plugin(s) {string.Join(", ", missing)}");
            var unused = masters.Where(m => !referenced.Contains(m)).ToList();
            if (unused.Count > 0) throw new Refusal($"masters lists plugin(s) no worldspace or npc_template uses: {string.Join(", ", unused)}");
        }
        else masters = referenced;

        var cfg = new Config(modName, pluginName, prefix, light, masters, worldPlugin, worldId, worldEdid, mx, my, enabled, tick, speed, onR, offR,
                             pool, maxActive, cooldown, notes, factions, flat, nodes, edges);
        CrossCheckPayload(j, cfg);
        return cfg;
    }

    /// A schema payload repeats the flattened arrays it derived; they must equal what this writer derives.
    static void CrossCheckPayload(JsonElement j, Config cfg)
    {
        if (Has(j, "editor_prefix") && j.GetProperty("editor_prefix").GetString() != cfg.Prefix) throw new Refusal("editor_prefix disagrees");
        if (Has(j, "properties"))
        {
            var p = j.GetProperty("properties");
            if (p.ValueKind != JsonValueKind.Object) throw new Refusal("payload properties is not an object");
            foreach (var (name, want) in cfg.FlatProperties())
            {
                if (!Has(p, name)) throw new Refusal($"payload properties lacks {name}");
                var v = p.GetProperty(name);
                bool ok = want switch
                {
                    int[] ia => v.ValueKind == JsonValueKind.Array && v.EnumerateArray().Select((x, i) => IntOf(x, $"properties.{name}[{i}]")).SequenceEqual(ia),
                    float[] fa => v.ValueKind == JsonValueKind.Array && v.EnumerateArray().Select((x, i) => NumOf(x, $"properties.{name}[{i}]")).SequenceEqual(fa),
                    int iv => IntOf(v, "properties." + name) == iv,
                    float fv => NumOf(v, "properties." + name) == fv,
                    _ => false,
                };
                if (!ok) throw new Refusal($"payload properties.{name} disagrees with the config it was exported from");
            }
        }
        if (Has(j, "globals"))
        {
            var g = j.GetProperty("globals");
            foreach (var (name, want) in cfg.GlobalValues())
                if (!Has(g, name) || NumOf(g.GetProperty(name), "globals." + name) != want) throw new Refusal($"payload globals.{name} disagrees with the config");
        }
    }

    // ================================================================ masters

    /// a plugin's master style from its TES4 header flags (Light 0x100 -> Small, Medium 0x400 -> Medium)
    public static MasterStyle StyleOf(string path)
    {
        var b = new byte[12];
        using (var fs = File.OpenRead(path))
            if (fs.Read(b, 0, 12) != 12 || b[0] != (byte)'T' || b[1] != (byte)'E' || b[2] != (byte)'S' || b[3] != (byte)'4')
                throw new Refusal($"{Path.GetFileName(path)} is not a plugin (no TES4 header)");
        var flags = BitConverter.ToUInt32(b, 8);
        return (flags & 0x100) != 0 ? MasterStyle.Small : (flags & 0x400) != 0 ? MasterStyle.Medium : MasterStyle.Full;
    }

    sealed class Masters : IDisposable
    {
        public required SF.IStarfieldModDisposableGetter Sf;
        public required List<SF.IStarfieldModDisposableGetter> Extras;
        public required ILinkCache<SF.IStarfieldMod, SF.IStarfieldModGetter> Cache;
        public required List<KeyedMasterStyle> Styles;
        public IEnumerable<SF.IStarfieldModGetter> All => new SF.IStarfieldModGetter[] { Sf }.Concat(Extras);
        public SF.IStarfieldModGetter? Mod(ModKey k) => All.FirstOrDefault(m => m.ModKey == k);
        public void Dispose() { Sf.Dispose(); foreach (var e in Extras) e.Dispose(); }
    }

    static BinaryReadParameters Read(IEnumerable<KeyedMasterStyle> styles)
    {
        var c = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        foreach (var s in styles) c.Set(s);
        return new BinaryReadParameters { MasterFlagsLookup = c };
    }

    static Masters Open(string sfPath, IReadOnlyList<string> extraPaths, Config cfg)
    {
        if (!File.Exists(sfPath)) throw new Refusal($"no such file: {Path.GetFileName(sfPath)}");
        if (!Path.GetFileName(sfPath).Equals("Starfield.esm", StringComparison.OrdinalIgnoreCase)) throw new Refusal("the first plugin must be Starfield.esm");
        var styles = new List<KeyedMasterStyle> { new(SfEsm, MasterStyle.Full) };
        foreach (var p in extraPaths)
        {
            if (!File.Exists(p)) throw new Refusal($"no such extra master: {Path.GetFileName(p)}");
            var k = PluginKey(Path.GetFileName(p), "--extra-master");
            if (k == SfEsm || k == cfg.Key || styles.Any(s => s.ModKey == k)) throw new Refusal($"--extra-master {k} is Starfield.esm, the plugin itself or given twice");
            styles.Add(new KeyedMasterStyle(k, StyleOf(p)));
        }
        foreach (var m in cfg.Masters)
            if (!styles.Any(s => s.ModKey == m)) throw new Refusal($"master {m} is not loaded: pass it with --extra-master");
        var sf = SF.StarfieldMod.CreateFromBinaryOverlay(sfPath, Rel);
        var extras = new List<SF.IStarfieldModDisposableGetter>();
        try
        {
            foreach (var p in extraPaths)
            {
                var e = SF.StarfieldMod.CreateFromBinaryOverlay(p, Rel, Read(styles));
                foreach (var mr in e.ModHeader.MasterReferences)
                    if (!styles.Any(s => s.ModKey == mr.Master)) { e.Dispose(); throw new Refusal($"{e.ModKey} needs {mr.Master}, which is not loaded"); }
                extras.Add(e);
            }
        }
        catch { sf.Dispose(); foreach (var e in extras) e.Dispose(); throw; }
        var cache = new SF.IStarfieldModGetter[] { sf }.Concat(extras).ToImmutableLinkCache<SF.IStarfieldMod, SF.IStarfieldModGetter>();
        return new Masters { Sf = sf, Extras = extras, Cache = cache, Styles = styles };
    }

    sealed record Inputs(SF.IFactionGetter PlayerFaction, SF.IStaticGetter XMarker, SF.IPackageGetter Travel, SF.IWorldspaceGetter World,
                         SF.ICellGetter TopCell, List<SF.INpcGetter> Templates, SF.IIngestibleGetter AidTemplate);

    static Inputs Resolve(Masters m, Config cfg)
    {
        var sf = m.Sf;
        if (!m.Cache.TryResolve<SF.IFactionGetter>(new FormKey(SfEsm, PlayerFactionId), out var pf) || pf.EditorID != PlayerFactionEdid)
            throw new Refusal($"Starfield.esm {PlayerFactionId:X6} is not the FACT {PlayerFactionEdid}");
        if (!m.Cache.TryResolve<SF.IStaticGetter>(new FormKey(SfEsm, XMarkerHeadingId), out var xm) || xm.EditorID != XMarkerHeadingEdid)
            throw new Refusal($"Starfield.esm {XMarkerHeadingId:X6} is not the STAT {XMarkerHeadingEdid}");
        var travel = sf.Packages.Where(p => p.FormKey.ModKey == SfEsm && string.Equals(p.EditorID, TravelPackageEdid, StringComparison.OrdinalIgnoreCase)).ToList();
        if (travel.Count != 1) throw new Refusal($"{travel.Count} PACK named {TravelPackageEdid} in Starfield.esm (one needed)");
        var wm = m.Mod(cfg.WorldPlugin) ?? throw new Refusal($"worldspace plugin {cfg.WorldPlugin} is not loaded");
        var world = wm.Worldspaces.FirstOrDefault(x => x.FormKey == new FormKey(cfg.WorldPlugin, cfg.WorldId))
                    ?? throw new Refusal($"{cfg.WorldPlugin} has no WRLD {cfg.WorldId:X6}");
        if (!string.Equals(world.EditorID, cfg.WorldEdid, StringComparison.OrdinalIgnoreCase))
            throw new Refusal($"WRLD {cfg.WorldPlugin}:{cfg.WorldId:X6} is {world.EditorID}, not {cfg.WorldEdid}");
        var top = world.TopCell ?? throw new Refusal($"WRLD {world.EditorID} has no persistent cell");
        var tpls = new List<SF.INpcGetter>();
        foreach (var f in cfg.Factions)
        {
            var fk = new FormKey(f.TplPlugin, f.TplId);
            if (m.Mod(f.TplPlugin) is null) throw new Refusal($"faction {f.Id}: template plugin {f.TplPlugin} is not loaded");
            if (!m.Cache.TryResolve<SF.INpcGetter>(fk, out var npc) || npc.FormKey.ModKey != f.TplPlugin) throw new Refusal($"faction {f.Id}: {fk} is not an NPC_ of {f.TplPlugin}");
            if (f.TplEdid is not null && !string.Equals(npc.EditorID, f.TplEdid, StringComparison.OrdinalIgnoreCase))
                throw new Refusal($"faction {f.Id}: NPC_ {fk} is {npc.EditorID}, not {f.TplEdid}");
            tpls.Add(npc);
        }
        var singles = sf.Ingestibles.Where(i => i.FormKey.ModKey == SfEsm && i.Effects.Count == 1 && i.Addiction.IsNull).OrderBy(i => i.FormKey.ID).ToList();
        var aid = singles.FirstOrDefault(i => i.Flags.HasFlag(SF.Ingestible.Flag.Medicine)) ?? singles.FirstOrDefault()
                  ?? throw new Refusal("Starfield.esm has no single-effect ingestible to clone the Field Transponder from");
        return new Inputs(pf, xm, travel[0], world, top, tpls, aid);
    }

    // ================================================================ build

    static FormKey Own(Config c, uint id) => new(c.Key, id);
    static SF.CombatReaction Reaction(int r) => r switch { 1 => SF.CombatReaction.Ally, -1 => SF.CombatReaction.Enemy, _ => SF.CombatReaction.Neutral };
    static uint OwnRecordCount(Config c) => 11u + (uint)c.Pool + 2u * (uint)c.Factions.Count;
    static uint NextId(Config c) => FirstNpcId + (uint)c.Factions.Count;
    public static bool FitsLight(Config c) => NextId(c) - 1 <= LightMaxId && OwnRecordCount(c) <= 0x800;

    static SF.ScriptObjectProperty Obj(string name, FormKey fk) => new()
    {
        Name = name, Flags = SF.ScriptProperty.Flag.Edited, Object = new FormLink<SF.IStarfieldMajorRecordGetter>(fk), Alias = -1, Unused = 0,
    };

    static SF.GameplayOption Option(Config c, uint id, string suffix, string name, string desc, float value, float min, float max, IEnumerable<(float V, string N)> rewards)
    {
        var o = new SF.GameplayOption(Own(c, id), Rel)
        {
            EditorID = $"{c.Prefix}_GPO_{suffix}", Name = name, Description = desc,
            Data = new SF.FloatGameplayOptionData { Value1 = value, Value2 = value, Min = min, Max = max, Step = 1f },
        };
        foreach (var (v, n) in rewards) o.Rewards.Add(new SF.GameplayOptionReward { SettingValue = v, Name = n, Description = "{0}: " + n, RewardValue = 0f });
        return o;
    }

    public static int Build(string sfPath, string configPath, string outDir, IReadOnlyList<string> extraPaths)
    {
        var cfg = LoadConfig(configPath);
        if (cfg.Light && !FitsLight(cfg)) throw new Refusal("light_master: the records do not fit the light FormID range");
        using var m = Open(sfPath, extraPaths, cfg);
        var inp = Resolve(m, cfg);
        var mod = new SF.StarfieldMod(cfg.Key, Rel);
        mod.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Master;
        if (cfg.Light) mod.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Light;
        mod.ModHeader.Author = "Starfield A-Life SDK";

        // globals and gameplay options
        var gv = cfg.GlobalValues();
        var globals = new (uint Id, string Name)[] { (SimEnabledId, "SimEnabled"), (OnlineRadiusId, "OnlineRadius"), (MaxSquadsId, "MaxSquads"), (NotificationsId, "Notifications") }
            .Select(g => new SF.Global(Own(cfg, g.Id), Rel) { EditorID = $"{cfg.Prefix}_{g.Name}", Data = gv[g.Name] }).ToList();
        foreach (var g in globals) mod.Globals.Add(g);
        var onOff = new[] { (0f, "OFF"), (1f, "ON") };
        var optEnabled = Option(cfg, OptEnabledId, "Enabled", "A-Life Simulation", "Runs the living-world squad simulation.", gv["SimEnabled"], 0, 1, onOff);
        var optMax = Option(cfg, OptMaxSquadsId, "MaxSquads", "A-Life Max Active Squads", "How many A-Life squads may be active at once.", cfg.MaxActive, 1, MaxSquads,
                            Enumerable.Range(1, MaxSquads).Select(i => ((float)i, i.ToString(CultureInfo.InvariantCulture))));
        var optNotes = Option(cfg, OptNotificationsId, "Notifications", "A-Life Notifications", "Shows brief battle and capture notifications.", gv["Notifications"], 0, 1, onOff);
        foreach (var o in new[] { optEnabled, optMax, optNotes }) mod.GameplayOptions.Add(o);
        mod.GameplayOptionsGroups.Add(new SF.GameplayOptionsGroup(Own(cfg, GpogId), Rel)
        {
            EditorID = $"{cfg.Prefix}_GPOG", Name = cfg.ModName,
            Options = new SF.GameplayOptionsGroupLeaf
            {
                GameplayOptions = new ExtendedList<IFormLinkGetter<SF.IGameplayOptionGetter>>
                {
                    new FormLink<SF.IGameplayOptionGetter>(optEnabled.FormKey), new FormLink<SF.IGameplayOptionGetter>(optMax.FormKey),
                    new FormLink<SF.IGameplayOptionGetter>(optNotes.FormKey),
                },
            },
        });

        // Field Transponder: script effect + an aid item cloned from Starfield.esm
        var questKey = Own(cfg, QuestId);
        var effect = new SF.MagicEffect(Own(cfg, EffectId), Rel)
        {
            EditorID = $"{cfg.Prefix}_TransponderEffect", Name = "A-Life Transponder Ping",
            Description = "Reports nearby A-Life squads and territory.",
            Archetype = new SF.MagicEffectArchetype(SF.MagicEffectArchetype.TypeEnum.Script),
            CastType = SF.CastType.FireAndForget, TargetType = SF.TargetType.Self,
            Flags = SF.MagicEffect.Flag.NoDuration | SF.MagicEffect.Flag.NoArea,
        };
        var beacon = new SF.ScriptEntry { Name = BeaconScript, Flags = SF.ScriptEntry.Flag.Local };
        beacon.Properties.Add(Obj("SimQuest", questKey));
        beacon.Properties.Add(Obj("FieldTransponder", Own(cfg, TransponderId)));
        effect.VirtualMachineAdapter = new SF.VirtualMachineAdapter { Version = 6, ObjectFormat = 2 };
        effect.VirtualMachineAdapter.Scripts.Add(beacon);
        mod.MagicEffects.Add(effect);
        var item = (SF.Ingestible)inp.AidTemplate.Duplicate(Own(cfg, TransponderId));
        item.EditorID = $"{cfg.Prefix}_FieldTransponder";
        item.Name = "A-Life Field Transponder";
        item.Description = "Reusable. Pings the A-Life network for nearby squads and territory.";
        item.VirtualMachineAdapter = null;
        item.Keywords = null;
        item.Addiction.SetToNull();
        item.AddictionChance = 0f;
        item.AddictionName = null;
        item.Weight = 0f;
        item.Value = 0;
        item.Effects.Clear();
        item.Effects.Add(new SF.Effect
        {
            BaseEffect = new FormLinkNullable<SF.IMagicEffectGetter>(effect.FormKey),
            Data = new SF.EffectData { Magnitude = 0, Area = 0, Duration = 0 },
        });
        mod.Ingestibles.Add(item);

        // waymarkers in the target world's persistent cell, nothing else copied
        var w = (SF.Worldspace)inp.World.DeepCopy(new SF.Worldspace.TranslationMask(defaultOn: true) { SubCells = false, TopCell = false });
        var cell = (SF.Cell)inp.TopCell.DeepCopy(new SF.Cell.TranslationMask(defaultOn: true) { Persistent = false, Temporary = false, NavigationMeshes = false });
        w.TopCell = cell;
        var start = cfg.Start;
        var markers = new List<SF.PlacedObject>();
        for (int i = 0; i < cfg.Pool; i++)
        {
            var r = new SF.PlacedObject(Own(cfg, FirstWaymarkerId + (uint)i), Rel)
            {
                EditorID = $"{cfg.Prefix}_Waymarker_{i + 1:00}", Base = new FormLinkNullable<SF.IPlaceableObjectGetter>(inp.XMarker.FormKey),
                Position = new P3Float(start.X, start.Y, start.Z), Rotation = new P3Float(0, 0, 0),
            };
            r.MajorRecordFlagsRaw |= 0x400;                                      // persistent: the runtime moves them
            cell.Persistent.Add(r);
            markers.Add(r);
        }
        mod.Worldspaces.Add(w);

        // factions and squad templates
        var facts = new List<SF.Faction>();
        foreach (var f in cfg.Factions)
            facts.Add(new SF.Faction(Own(cfg, FirstFactionId + (uint)f.Index), Rel) { EditorID = f.Edid, Name = f.Name });
        foreach (var f in cfg.Factions)
        {
            var fa = facts[f.Index];
            fa.Relations.Add(new SF.Relation { Target = new FormLink<SF.IRelatableGetter>(inp.PlayerFaction.FormKey), Reaction = Reaction(f.PlayerRel) });
            foreach (var o in cfg.Factions.Where(o => o.Index != f.Index))
                fa.Relations.Add(new SF.Relation { Target = new FormLink<SF.IRelatableGetter>(facts[o.Index].FormKey), Reaction = Reaction(cfg.RelFlat[f.Index * cfg.Factions.Count + o.Index]) });
            mod.Factions.Add(fa);
        }
        var npcs = new List<SF.Npc>();
        foreach (var f in cfg.Factions)
        {
            var npc = (SF.Npc)inp.Templates[f.Index].Duplicate(Own(cfg, FirstNpcId + (uint)f.Index));
            npc.EditorID = f.NpcEdid;
            npc.VirtualMachineAdapter = null;
            npc.Flags &= ~(SF.Npc.Flag.Respawn | SF.Npc.Flag.Unique | SF.Npc.Flag.Essential | SF.Npc.Flag.Protected | SF.Npc.Flag.IsCharGenFacePreset);
            npc.UseTemplateActors &= ~(SF.Npc.TemplateActorType.Factions | SF.Npc.TemplateActorType.Script | SF.Npc.TemplateActorType.AiPackages);
            npc.Factions.Clear();
            npc.Factions.Add(new SF.RankPlacement { Faction = new FormLink<SF.IFactionGetter>(facts[f.Index].FormKey), Rank = 0 });
            npc.CrimeFaction.SetToNull();
            npc.FormationFaction.SetToNull();
            npc.CompanionInfoQuest.SetToNull();
            npc.CompanionInfoDialogue.SetToNull();
            npc.ForcedLocations?.Clear();
            npc.Packages.Clear();
            npc.Packages.Add(new FormLink<SF.IPackageGetter>(inp.Travel.FormKey));
            mod.Npcs.Add(npc);
            npcs.Add(npc);
        }

        // the controller quest
        var quest = new SF.Quest(questKey, Rel)
        {
            EditorID = $"{cfg.Prefix}_ALifeSim", FormVersion = 581, Version2 = 12,
            Data = new SF.QuestData { Flags = SF.Quest.Flag.StartGameEnabled | SF.Quest.Flag.StartsEnabled | SF.Quest.Flag.AllowRepeatedStages, Priority = 50 },
        };
        var script = new SF.ScriptEntry { Name = QuestScript, Flags = SF.ScriptEntry.Flag.Local };
        SF.ScriptObjectListProperty Objs(string name, IEnumerable<FormKey> keys)
        {
            var p = new SF.ScriptObjectListProperty { Name = name, Flags = SF.ScriptProperty.Flag.Edited };
            foreach (var k in keys) p.Objects.Add(Obj("", k));
            return p;
        }
        var flatProps = cfg.FlatProperties();
        var objects = new Dictionary<string, FormKey>
        {
            ["SimEnabledGlobal"] = globals[0].FormKey, ["OnlineRadiusGlobal"] = globals[1].FormKey, ["MaxSquadsGlobal"] = globals[2].FormKey,
            ["NotificationsGlobal"] = globals[3].FormKey, ["OptEnabled"] = optEnabled.FormKey, ["OptMaxSquads"] = optMax.FormKey,
            ["OptNotifications"] = optNotes.FormKey, ["FieldTransponder"] = item.FormKey,
        };
        foreach (var name in Properties)
        {
            SF.ScriptProperty p = name switch
            {
                "SquadTemplates" => Objs(name, npcs.Select(n => n.FormKey)),
                "SquadFactions" => Objs(name, facts.Select(x => x.FormKey)),
                "Waymarkers" => Objs(name, markers.Select(x => x.FormKey)),
                _ when objects.TryGetValue(name, out var fk) => Obj(name, fk),
                _ => flatProps[name] switch
                {
                    int[] ia => new SF.ScriptIntListProperty { Name = name, Flags = SF.ScriptProperty.Flag.Edited, Data = new ExtendedList<int>(ia) },
                    float[] fa => new SF.ScriptFloatListProperty { Name = name, Flags = SF.ScriptProperty.Flag.Edited, Data = new ExtendedList<float>(fa) },
                    int iv => new SF.ScriptIntProperty { Name = name, Flags = SF.ScriptProperty.Flag.Edited, Data = iv },
                    float fv => new SF.ScriptFloatProperty { Name = name, Flags = SF.ScriptProperty.Flag.Edited, Data = fv },
                    _ => throw new InvalidOperationException(name),
                },
            };
            script.Properties.Add(p);
        }
        quest.VirtualMachineAdapter = new SF.QuestAdapter { Version = 6, ObjectFormat = 2, ExtraBindDataVersion = 3, Script = new SF.ScriptEntry { Name = "", Flags = SF.ScriptEntry.Flag.Local } };
        quest.VirtualMachineAdapter.Scripts.Add(script);
        mod.Quests.Add(quest);
        mod.ModHeader.Stats.NextFormID = NextId(cfg);

        var path = WritePlugin(mod, outDir, cfg.PluginName, m.Styles);
        Console.WriteLine($"wrote {cfg.PluginName} ({new FileInfo(path).Length:N0} bytes, {(cfg.Light ? "light " : "")}master): QUST {quest.EditorID}; 4 GLOB; 3 GPOF + GPOG; " +
                          $"MGEF + ALCH transponder (from {inp.AidTemplate.EditorID}); {cfg.Pool} waymarker(s) at ({F(start.X)}, {F(start.Y)}, {F(start.Z)}) in WRLD " +
                          $"{inp.World.EditorID}; {cfg.Factions.Count} FACT + NPC_; graph {cfg.Nodes.Count} nodes / {cfg.Edges.Count} edges");
        using (var back = SF.StarfieldMod.CreateFromBinaryOverlay(path, Rel, Read(m.Styles.Append(new KeyedMasterStyle(cfg.Key, StyleOf(path))))))
            Console.WriteLine("masters: " + string.Join(", ", back.ModHeader.MasterReferences.Select(x => x.Master.FileName.String)));
        return 0;
    }

    /// writes through a temporary file next to the output, then renames it into place
    static string WritePlugin(SF.StarfieldMod mod, string outDir, string fileName, IReadOnlyList<KeyedMasterStyle> styles)
    {
        Directory.CreateDirectory(outDir);
        var final = Path.Combine(outDir, fileName);
        var tmpDir = Path.Combine(outDir, ".partial-" + Guid.NewGuid().ToString("N"));
        try
        {
            Directory.CreateDirectory(tmpDir);
            var tmp = Path.Combine(tmpDir, fileName);
            mod.BeginWrite.ToPath(tmp).WithLoadOrder(styles.Select(s => s.ModKey).ToArray()).WithKnownMasters(styles.ToArray()).Write();
            File.Move(tmp, final, overwrite: true);
        }
        finally
        {
            if (Directory.Exists(tmpDir)) Directory.Delete(tmpDir, recursive: true);
        }
        return final;
    }

    // ================================================================ check

    public static int Check(string pluginPath, string sfPath, string configPath, IReadOnlyList<string> extraPaths)
    {
        var cfg = LoadConfig(configPath);
        if (!File.Exists(pluginPath)) throw new Refusal($"no such plugin: {Path.GetFileName(pluginPath)}");
        if (!Path.GetFileName(pluginPath).Equals(cfg.PluginName, StringComparison.OrdinalIgnoreCase))
            throw new Refusal($"{Path.GetFileName(pluginPath)} is not the configured {cfg.PluginName}");
        using var m = Open(sfPath, extraPaths, cfg);
        var inp = Resolve(m, cfg);
        var styles = m.Styles.Append(new KeyedMasterStyle(cfg.Key, StyleOf(pluginPath))).ToList();
        using var plug = SF.StarfieldMod.CreateFromBinaryOverlay(pluginPath, Rel, Read(styles));
        var key = plug.ModKey;
        var problems = new List<string>();
        void Need(bool ok, string what) { if (!ok) problems.Add(what); }
        FormKey O(uint id) => new(key, id);
        int fc = cfg.Factions.Count;

        // header and masters
        var hf = plug.ModHeader.Flags;
        var masters = plug.ModHeader.MasterReferences.Select(x => x.Master).ToList();
        Console.WriteLine($"{key}: header {hf}, masters [{string.Join(", ", masters)}], next 0x{plug.ModHeader.Stats.NextFormID:X}");
        Need(hf.HasFlag(SF.StarfieldModHeader.HeaderFlag.Master), "not flagged as a master");
        Need(hf.HasFlag(SF.StarfieldModHeader.HeaderFlag.Light) == cfg.Light, cfg.Light ? "light_master is set but the Light flag is not" : "Light flag set without light_master");
        Need(!hf.HasFlag(SF.StarfieldModHeader.HeaderFlag.Medium) && !hf.HasFlag(SF.StarfieldModHeader.HeaderFlag.Localized), "Medium or Localized header flag set");
        Need(masters.Count > 0 && masters[0] == SfEsm, "the first master is not Starfield.esm");
        Need(masters.Contains(cfg.WorldPlugin), $"the worldspace plugin {cfg.WorldPlugin} is not a master");
        int at = 0;
        Need(masters.All(x => (at = cfg.Masters.IndexOf(x, at)) >= 0), $"masters are not an ordered subset of [{string.Join(", ", cfg.Masters)}]");
        Need(plug.ModHeader.Stats.NextFormID == NextId(cfg), $"next FormID 0x{plug.ModHeader.Stats.NextFormID:X} is not 0x{NextId(cfg):X}");

        // record inventory: exactly our records plus the WRLD and persistent CELL overrides
        var own = new HashSet<uint> { QuestId, SimEnabledId, OnlineRadiusId, MaxSquadsId, NotificationsId, OptEnabledId, OptMaxSquadsId, OptNotificationsId, GpogId, EffectId, TransponderId };
        for (int i = 0; i < cfg.Pool; i++) own.Add(FirstWaymarkerId + (uint)i);
        for (int i = 0; i < fc; i++) { own.Add(FirstFactionId + (uint)i); own.Add(FirstNpcId + (uint)i); }
        var records = plug.EnumerateMajorRecords().ToList();
        foreach (var r in records)
        {
            if (r.FormKey.ModKey == key) Need(own.Remove(r.FormKey.ID), $"unexpected or repeated own record {r.FormKey.ID:X6} {r.EditorID}");
            else Need(r.FormKey == inp.World.FormKey || r.FormKey == inp.TopCell.FormKey, $"overrides foreign record {r.FormKey} {r.EditorID}");
        }
        Need(own.Count == 0, $"missing record(s) {string.Join(", ", own.Select(x => x.ToString("X6")))}");
        Need(records.Count(r => r.FormKey.ModKey != key) == 2, "the WRLD and persistent CELL overrides are not both present exactly once");
        if (cfg.Light) Need(records.Where(r => r.FormKey.ModKey == key).All(r => r.FormKey.ID is >= 0x800 and <= LightMaxId), "a record falls outside the light range");
        Need(plug.Quests.Count == 1 && plug.Globals.Count == 4 && plug.GameplayOptions.Count == 3 && plug.GameplayOptionsGroups.Count == 1 && plug.MagicEffects.Count == 1
             && plug.Ingestibles.Count == 1 && plug.Factions.Count == fc && plug.Npcs.Count == fc && plug.Worldspaces.Count == 1, "record group counts differ");

        // every link points into the plugin or a master; links of our own records resolve (the WRLD/CELL overrides
        // carry the master's own links verbatim, so only their plugin is checked)
        var self = new HashSet<FormKey>(records.Select(r => r.FormKey));
        var resolved = new HashSet<FormKey>();
        foreach (var r in records)
            foreach (var l in r.EnumerateFormLinks())
            {
                if (l.IsNull || self.Contains(l.FormKey)) continue;
                if (!masters.Contains(l.FormKey.ModKey)) { problems.Add($"{r.FormKey.ID:X6} {r.EditorID} links to {l.FormKey}, outside the plugin and its masters"); continue; }
                if (r.FormKey.ModKey == key && !resolved.Contains(l.FormKey))
                {
                    // IPlaceableObjectGetter links do not resolve through the aspect type; a STAT does, and the untyped
                    // lookup (which indexes all of Starfield.esm) is kept for whatever is left
                    var ok = m.Cache.TryResolve(l.FormKey, l.Type, out _) || m.Cache.TryResolve<SF.IStaticGetter>(l.FormKey, out _)
                             || m.Cache.TryResolve<SF.IStarfieldMajorRecordGetter>(l.FormKey, out _);
                    Need(ok, $"{r.FormKey.ID:X6} {r.EditorID} links to unresolved {l.FormKey}");
                    if (ok) resolved.Add(l.FormKey);
                }
            }

        // globals and options
        var gv = cfg.GlobalValues();
        foreach (var (id, name) in new[] { (SimEnabledId, "SimEnabled"), (OnlineRadiusId, "OnlineRadius"), (MaxSquadsId, "MaxSquads"), (NotificationsId, "Notifications") })
        {
            var g = plug.Globals.FirstOrDefault(x => x.FormKey == O(id));
            Need(g is not null && g.EditorID == $"{cfg.Prefix}_{name}" && g.Data == gv[name] && !g.MajorFlags.HasFlag(SF.Global.MajorFlag.Constant),
                 $"GLOB {id:X6} is not the non-constant {cfg.Prefix}_{name} = {F(gv[name])}");
        }
        void NeedOption(uint id, string suffix, float value, float min, float max, int rewards)
        {
            var o = plug.GameplayOptions.FirstOrDefault(x => x.FormKey == O(id));
            Need(o is not null && o.EditorID == $"{cfg.Prefix}_GPO_{suffix}" && o.Data is SF.IFloatGameplayOptionDataGetter d && d.Value1 == value && d.Value2 == value
                 && d.Min == min && d.Max == max && d.Step == 1f && o.Rewards.Count == rewards, $"GPOF {id:X6} is not {cfg.Prefix}_GPO_{suffix} {F(min)}..{F(max)} = {F(value)}");
        }
        NeedOption(OptEnabledId, "Enabled", gv["SimEnabled"], 0, 1, 2);
        NeedOption(OptMaxSquadsId, "MaxSquads", cfg.MaxActive, 1, MaxSquads, MaxSquads);
        NeedOption(OptNotificationsId, "Notifications", gv["Notifications"], 0, 1, 2);
        var gpog = plug.GameplayOptionsGroups.FirstOrDefault(x => x.FormKey == O(GpogId));
        Need(gpog is not null && gpog.EditorID == $"{cfg.Prefix}_GPOG" && gpog.Options is SF.IGameplayOptionsGroupLeafGetter leaf
             && leaf.GameplayOptions.Select(x => x.FormKey).SequenceEqual(new[] { O(OptEnabledId), O(OptMaxSquadsId), O(OptNotificationsId) }),
             "GPOG does not list the three options in order");

        // transponder
        var eff = plug.MagicEffects.FirstOrDefault(x => x.FormKey == O(EffectId));
        var bs = eff?.VirtualMachineAdapter?.Scripts;
        Need(eff is not null && eff.EditorID == $"{cfg.Prefix}_TransponderEffect" && eff.Archetype.Type == SF.MagicEffectArchetype.TypeEnum.Script
             && eff.TargetType == SF.TargetType.Self && eff.CastType == SF.CastType.FireAndForget && !eff.Flags.HasFlag(SF.MagicEffect.Flag.Detrimental),
             "MGEF is not the self fire-and-forget script effect");
        Need(bs is { Count: 1 } && bs[0].Name == BeaconScript && bs[0].Properties.Select(p => p.Name).SequenceEqual(BeaconProperties)
             && bs[0].Properties[0] is SF.IScriptObjectPropertyGetter q0 && q0.Object.FormKey == O(QuestId)
             && bs[0].Properties[1] is SF.IScriptObjectPropertyGetter q1 && q1.Object.FormKey == O(TransponderId),
             $"MGEF does not carry {BeaconScript} with SimQuest -> QUST and FieldTransponder -> ALCH");
        var alch = plug.Ingestibles.FirstOrDefault(x => x.FormKey == O(TransponderId));
        Need(alch is not null && alch.EditorID == $"{cfg.Prefix}_FieldTransponder" && alch.Effects.Count == 1 && alch.Effects[0].BaseEffect.FormKey == O(EffectId)
             && alch.VirtualMachineAdapter is null && alch.Addiction.IsNull && alch.Weight == 0f, "ALCH is not the weightless transponder with the one script effect");

        // world, cell, waymarkers
        var w = plug.Worldspaces.FirstOrDefault();
        Need(w is not null && w.FormKey == inp.World.FormKey && w.SubCells.Count == 0, "the WRLD override is not the configured world without exterior cells");
        var cell = w?.TopCell;
        Need(cell is not null && cell.FormKey == inp.TopCell.FormKey && cell.Temporary.Count == 0 && cell.NavigationMeshes.Count == 0,
             "the persistent cell override is not the world's, empty but for waymarkers");
        var refs = cell?.Persistent.OfType<SF.IPlacedObjectGetter>().ToList() ?? new();
        Need(cell is null || cell.Persistent.Count == refs.Count, "the persistent cell holds something other than placed objects");
        Need(refs.Count == cfg.Pool, $"{refs.Count} waymarkers, not {cfg.Pool}");
        var start = cfg.Start;
        foreach (var (r, i) in refs.Select((r, i) => (r, i)))
        {
            Need(r.FormKey == O(FirstWaymarkerId + (uint)i) && r.EditorID == $"{cfg.Prefix}_Waymarker_{i + 1:00}", $"waymarker {i} is not 0x{FirstWaymarkerId + i:X} {cfg.Prefix}_Waymarker_{i + 1:00}");
            Need(r.Base.FormKey == inp.XMarker.FormKey, $"REFR {r.FormKey.ID:X6} is not an {XMarkerHeadingEdid}");
            Need((r.MajorRecordFlagsRaw & 0xC00) == 0x400, $"REFR {r.FormKey.ID:X6} is not persistent and enabled");
            Need(r.Position.X == start.X && r.Position.Y == start.Y && r.Position.Z == start.Z, $"REFR {r.FormKey.ID:X6} is not at the first spawn node");
        }

        // factions and squads
        foreach (var f in cfg.Factions)
        {
            var fa = plug.Factions.FirstOrDefault(x => x.FormKey == O(FirstFactionId + (uint)f.Index));
            var want = new List<(FormKey, SF.CombatReaction)> { (inp.PlayerFaction.FormKey, Reaction(f.PlayerRel)) };
            want.AddRange(cfg.Factions.Where(o => o.Index != f.Index).Select(o => (O(FirstFactionId + (uint)o.Index), Reaction(cfg.RelFlat[f.Index * fc + o.Index]))));
            Need(fa is not null && fa.EditorID == f.Edid && fa.Relations.Select(r => (r.Target.FormKey, r.Reaction)).SequenceEqual(want),
                 $"FACT {f.Edid} relations to PlayerFaction and the other factions differ from the config");
            var npc = plug.Npcs.FirstOrDefault(x => x.FormKey == O(FirstNpcId + (uint)f.Index));
            var tpl = inp.Templates[f.Index];
            Need(npc is not null && npc.EditorID == f.NpcEdid && npc.Factions.Count == 1 && npc.Factions[0].Faction.FormKey == fa?.FormKey && fa is not null,
                 $"NPC_ {f.NpcEdid} is not in {f.Edid} only");
            Need(npc is not null && (npc.Flags & (SF.Npc.Flag.Respawn | SF.Npc.Flag.Unique | SF.Npc.Flag.Essential | SF.Npc.Flag.Protected)) == 0,
                 $"NPC_ {f.NpcEdid} is unique, essential, protected or respawning");
            Need(npc is not null && (npc.VirtualMachineAdapter is null || npc.VirtualMachineAdapter.Scripts.Count == 0) && npc.CrimeFaction.IsNull
                 && npc.CompanionInfoQuest.IsNull && (npc.UseTemplateActors & (SF.Npc.TemplateActorType.Factions | SF.Npc.TemplateActorType.Script | SF.Npc.TemplateActorType.AiPackages)) == 0,
                 $"NPC_ {f.NpcEdid} keeps foreign scripts, factions, quest links or inherited packages");
            Need(npc is not null && npc.Packages.Count == 1 && npc.Packages[0].FormKey == inp.Travel.FormKey, $"NPC_ {f.NpcEdid} AI is not {TravelPackageEdid}");
            Need(npc is not null && npc.Race.FormKey == tpl.Race.FormKey && npc.TemplateActors?.TraitTemplate.FormKey == tpl.TemplateActors?.TraitTemplate.FormKey,
                 $"NPC_ {f.NpcEdid} is not a clone of {tpl.FormKey}");
        }

        // quest and properties
        var q = plug.Quests.FirstOrDefault(x => x.FormKey == O(QuestId));
        if (q is null) problems.Add($"no QUST 0x{QuestId:X}");
        else
        {
            var want = SF.Quest.Flag.StartGameEnabled | SF.Quest.Flag.StartsEnabled | SF.Quest.Flag.AllowRepeatedStages;
            Need(q.EditorID == $"{cfg.Prefix}_ALifeSim" && q.Data is not null && (q.Data.Flags & want) == want
                 && !q.Data.Flags.HasFlag(SF.Quest.Flag.RunOnce) && !q.Data.Flags.HasFlag(SF.Quest.Flag.DisplaysInHud),
                 $"QUST is not {cfg.Prefix}_ALifeSim, start game enabled, starts enabled, repeatable, not run once, out of the HUD");
            Need((q.Aliases?.Count ?? 0) == 0, "the quest carries an alias");
            var scripts = q.VirtualMachineAdapter?.Scripts;
            if (scripts is not { Count: 1 } || scripts[0].Name != QuestScript) problems.Add($"the quest does not carry exactly {QuestScript}");
            else
            {
                var ps = scripts[0].Properties;
                Need(ps.Select(p => p.Name).SequenceEqual(Properties), "the script's properties are not exactly the runtime's, in order");
                var props = ps.GroupBy(p => p.Name).ToDictionary(g => g.Key, g => g.First());
                List<FormKey>? OL(string n) => props.TryGetValue(n, out var p) && p is SF.IScriptObjectListPropertyGetter l ? l.Objects.Select(o => o.Object.FormKey).ToList() : null;
                FormKey? OB(string n) => props.TryGetValue(n, out var p) && p is SF.IScriptObjectPropertyGetter o ? o.Object.FormKey : null;
                Need(OL("SquadTemplates")?.SequenceEqual(cfg.Factions.Select(f => O(FirstNpcId + (uint)f.Index))) == true, "SquadTemplates is not the squad NPC_s by faction index");
                Need(OL("SquadFactions")?.SequenceEqual(cfg.Factions.Select(f => O(FirstFactionId + (uint)f.Index))) == true, "SquadFactions is not the FACTs by faction index");
                Need(OL("Waymarkers")?.SequenceEqual(Enumerable.Range(0, cfg.Pool).Select(i => O(FirstWaymarkerId + (uint)i))) == true, "Waymarkers does not list the pool in order");
                foreach (var (n, id) in new[] { ("SimEnabledGlobal", SimEnabledId), ("OnlineRadiusGlobal", OnlineRadiusId), ("MaxSquadsGlobal", MaxSquadsId),
                                                ("NotificationsGlobal", NotificationsId), ("OptEnabled", OptEnabledId), ("OptMaxSquads", OptMaxSquadsId),
                                                ("OptNotifications", OptNotificationsId), ("FieldTransponder", TransponderId) })
                    Need(OB(n) == O(id), $"{n} does not point at {id:X6}");
                foreach (var (n, v) in cfg.FlatProperties())
                {
                    props.TryGetValue(n, out var p);
                    bool ok = v switch
                    {
                        int[] ia => p is SF.IScriptIntListPropertyGetter il && il.Data.Count <= ArrayCap && il.Data.SequenceEqual(ia),
                        float[] fa => p is SF.IScriptFloatListPropertyGetter fl && fl.Data.Count <= ArrayCap && fl.Data.SequenceEqual(fa),
                        int iv => p is SF.IScriptIntPropertyGetter ip && ip.Data == iv,
                        float fv => p is SF.IScriptFloatPropertyGetter fp && fp.Data == fv,
                        _ => false,
                    };
                    Need(ok, $"{n} differs from the config");
                }
            }
        }
        foreach (var p in problems) Console.WriteLine("FAIL  " + p);
        Console.WriteLine(problems.Count == 0 ? "all checks pass" : $"{problems.Count} problem(s)");
        return problems.Count == 0 ? 0 : 1;
    }

    // ================================================================ selftest (synthetic masters only)

    static readonly ModKey CustomKey = ModKey.FromFileName("SynthCustomWorld.esm");
    const uint SynthWorldId = 0x00A000, SynthCellId = 0x00A001, SynthNpcA = 0x00B001, SynthNpcB = 0x00B002, SynthNpcC = 0x00B003;
    const uint CustomWorldId = 0x000800, CustomCellId = 0x000801, CustomNpcId = 0x000802;

    static void WriteSynthetic(string dir)
    {
        var sf = new SF.StarfieldMod(SfEsm, Rel);
        sf.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Master;
        sf.Factions.Add(new SF.Faction(new FormKey(SfEsm, PlayerFactionId), Rel) { EditorID = PlayerFactionEdid });
        var foreignFaction = new SF.Faction(new FormKey(SfEsm, 0x00C000), Rel) { EditorID = "SynthCrimeFaction" };
        sf.Factions.Add(foreignFaction);
        sf.Statics.Add(new SF.Static(new FormKey(SfEsm, XMarkerHeadingId), Rel) { EditorID = XMarkerHeadingEdid });
        var race = new SF.Race(new FormKey(SfEsm, 0x000900), Rel) { EditorID = "HumanRace" };
        sf.Races.Add(race);
        sf.Packages.Add(new SF.Package(new FormKey(SfEsm, 0x00D000), Rel) { EditorID = TravelPackageEdid });
        sf.Packages.Add(new SF.Package(new FormKey(SfEsm, 0x00D001), Rel) { EditorID = "SynthSandbox" });
        sf.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x00E000), Rel) { EditorID = "SynthForeignQuest" });
        var mgef = new SF.MagicEffect(new FormKey(SfEsm, 0x00F000), Rel)
        {
            EditorID = "SynthRestore", Archetype = new SF.MagicEffectArchetype(SF.MagicEffectArchetype.TypeEnum.ValueModifier),
        };
        sf.MagicEffects.Add(mgef);
        var aid = new SF.Ingestible(new FormKey(SfEsm, 0x00F001), Rel)
        {
            EditorID = "SynthMedPack", Name = "Synth Med", Weight = 0.5f, Value = 20, Flags = SF.Ingestible.Flag.Medicine, MajorFlags = SF.Ingestible.MajorFlag.Medicine,
        };
        aid.Effects.Add(new SF.Effect { BaseEffect = new FormLinkNullable<SF.IMagicEffectGetter>(mgef.FormKey), Data = new SF.EffectData { Magnitude = 10 } });
        sf.Ingestibles.Add(aid);
        foreach (var (id, edid) in new[] { (SynthNpcA, "SynthGuard"), (SynthNpcB, "SynthSpacer"), (SynthNpcC, "SynthMerc") })
        {
            var n = new SF.Npc(new FormKey(SfEsm, id), Rel)
            {
                EditorID = edid, Name = edid, Race = new FormLink<SF.IRaceGetter>(race.FormKey),
                Flags = SF.Npc.Flag.Unique | SF.Npc.Flag.Essential | SF.Npc.Flag.Respawn | SF.Npc.Flag.Protected,
                UseTemplateActors = SF.Npc.TemplateActorType.Factions | SF.Npc.TemplateActorType.Script | SF.Npc.TemplateActorType.AiPackages | SF.Npc.TemplateActorType.Traits,
            };
            n.Factions.Add(new SF.RankPlacement { Faction = new FormLink<SF.IFactionGetter>(foreignFaction.FormKey), Rank = 1 });
            n.CrimeFaction.SetTo(foreignFaction.FormKey);
            n.Packages.Add(new FormLink<SF.IPackageGetter>(new FormKey(SfEsm, 0x00D001)));
            n.VirtualMachineAdapter = new SF.VirtualMachineAdapter { Version = 6, ObjectFormat = 2 };
            n.VirtualMachineAdapter.Scripts.Add(new SF.ScriptEntry { Name = "SynthForeignNpcScript", Flags = SF.ScriptEntry.Flag.Local });
            sf.Npcs.Add(n);
        }
        var world = new SF.Worldspace(new FormKey(SfEsm, SynthWorldId), Rel) { EditorID = "SynthWorld" };
        world.TopCell = new SF.Cell(new FormKey(SfEsm, SynthCellId), Rel) { Flags = SF.Cell.Flag.HasWater };
        world.TopCell.Persistent.Add(new SF.PlacedObject(new FormKey(SfEsm, 0x00A002), Rel)
        {
            EditorID = "SynthForeignAnchor", Base = new FormLinkNullable<SF.IPlaceableObjectGetter>(new FormKey(SfEsm, XMarkerHeadingId)),
        });
        sf.Worldspaces.Add(world);
        sf.ModHeader.Stats.NextFormID = 0x010000;
        sf.BeginWrite.ToPath(Path.Combine(dir, "Starfield.esm")).WithNoLoadOrder().NoCheckIfLowerRangeDisallowed().Write();

        var cu = new SF.StarfieldMod(CustomKey, Rel);
        cu.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Master;
        var cw = new SF.Worldspace(new FormKey(CustomKey, CustomWorldId), Rel) { EditorID = "SynthCustomWorld" };
        cw.TopCell = new SF.Cell(new FormKey(CustomKey, CustomCellId), Rel) { Flags = SF.Cell.Flag.HasWater };
        cu.Worldspaces.Add(cw);
        cu.Npcs.Add(new SF.Npc(new FormKey(CustomKey, CustomNpcId), Rel) { EditorID = "SynthCustomRaider", Race = new FormLink<SF.IRaceGetter>(race.FormKey) });
        cu.ModHeader.Stats.NextFormID = 0x803;
        cu.BeginWrite.ToPath(Path.Combine(dir, CustomKey.FileName.String)).WithLoadOrder(SfEsm).WithKnownMasters(new KeyedMasterStyle(SfEsm, MasterStyle.Full)).Write();
    }

    static string Hex(uint v) => $"0x{v:X6}";

    /// a valid synthetic config: F factions, N nodes in a ring plus chords, the world in Starfield.esm
    static JsonObject SynthConfig(int factions = 3, int nodes = 8, int edges = 10, int pool = 4)
    {
        string[] tpl = { Hex(SynthNpcA), Hex(SynthNpcB), Hex(SynthNpcC) };
        string[] rel = { "enemy", "neutral", "ally" };
        var fs = new JsonArray();
        for (int a = 0; a < factions; a++)
        {
            var r = new JsonObject();
            for (int b = 0; b < factions; b++) if (a != b) r[$"f{b}"] = rel[(a + b) % 3];
            fs.Add(new JsonObject
            {
                ["id"] = $"f{a}", ["index"] = a, ["name"] = $"Synth Faction {a}",
                ["npc_template"] = new JsonObject { ["plugin"] = "Starfield.esm", ["form_id"] = tpl[a % 3] },
                ["player_relation"] = rel[a % 3], ["relations"] = r, ["squad_size"] = 1 + a % 8, ["combat_power"] = 1.0 + a * 0.25,
            });
        }
        var ns = new JsonArray();
        for (int i = 0; i < nodes; i++)
        {
            int kind = i % 5;
            ns.Add(new JsonObject
            {
                ["index"] = i, ["id"] = $"n{i}", ["kind"] = NodeKinds[kind], ["x"] = i * 37.5, ["y"] = -i * 12.25, ["z"] = 4.0 + i % 3,
                ["capacity"] = kind == 0 ? 0 : 1 + i % 3, ["initial_owner"] = kind == 1 ? (i / 5) % factions : -1, ["spawn_faction"] = kind == 1 ? (i / 5) % factions : -1,
            });
        }
        var es = new JsonArray();
        for (int i = 0; i < edges; i++)
        {
            int u = i < nodes ? i : (i * 7) % nodes, v = i < nodes ? (i + 1) % nodes : (u + 2 + i / nodes) % nodes;
            es.Add(new JsonObject { ["u"] = u, ["v"] = v, ["len_m"] = 25.5 + i });
        }
        return new JsonObject
        {
            ["schema_version"] = 1, ["mod_name"] = "Synth A-Life", ["plugin_name"] = "StarfieldALife.esm", ["light_master"] = false,
            ["masters"] = new JsonArray("Starfield.esm"),
            ["worldspace"] = new JsonObject { ["plugin"] = "Starfield.esm", ["form_id"] = Hex(SynthWorldId), ["editor_id"] = "SynthWorld", ["merge_offset_xy"] = new JsonArray(100.0, -50.0) },
            ["simulation"] = new JsonObject
            {
                ["default_enabled"] = true, ["tick_real_s"] = 2.0, ["offline_step_m_per_s"] = 1.35, ["online_spawn_radius_m"] = 450.0, ["offline_despawn_radius_m"] = 620.0,
                ["waymarker_pool_size"] = pool, ["max_active_squads"] = 8, ["respawn_cooldown_s"] = 120.0, ["show_notifications"] = true,
            },
            ["factions"] = fs, ["nodes"] = ns, ["edges"] = es,
        };
    }

    static JsonObject Edit(JsonObject c, Action<JsonObject> e) { var copy = (JsonObject)JsonNode.Parse(c.ToJsonString())!; e(copy); return copy; }
    static JsonObject N(JsonObject c, string list, int i) => (JsonObject)((JsonArray)c[list]!)[i]!;

    public static int SelfTest(string dir)
    {
        Directory.CreateDirectory(dir);
        var syn = Path.Combine(dir, "synthetic");
        Directory.CreateDirectory(syn);
        WriteSynthetic(syn);
        var sfPath = Path.Combine(syn, "Starfield.esm");
        var customPath = Path.Combine(syn, CustomKey.FileName.String);
        string Save(string name, JsonObject c) { var p = Path.Combine(dir, name); File.WriteAllText(p, c.ToJsonString(new JsonSerializerOptions { WriteIndented = true })); return p; }

        // 1. builds that must pass check
        var vanilla = SynthConfig();
        var light = Edit(vanilla, c => { c["light_master"] = true; c["plugin_name"] = "MyLightALife.esm"; c["editor_prefix"] = "MyLight"; });
        var custom = Edit(vanilla, c =>
        {
            c["plugin_name"] = "CustomALife.esm";
            c["masters"] = new JsonArray("Starfield.esm", CustomKey.FileName.String);
            c["worldspace"] = new JsonObject { ["plugin"] = CustomKey.FileName.String, ["form_id"] = Hex(CustomWorldId), ["editor_id"] = "SynthCustomWorld", ["merge_offset_xy"] = new JsonArray(0.0, 0.0) };
            N(c, "factions", 1)["npc_template"] = new JsonObject { ["plugin"] = CustomKey.FileName.String, ["form_id"] = Hex(CustomNpcId) };
        });
        var big = SynthConfig(factions: 8, nodes: ArrayCap, edges: ArrayCap, pool: MaxPool);
        big["simulation"]!["max_active_squads"] = MaxSquads;
        var bigCfg = LoadConfig(Save("big.json", big));
        var payload = (JsonObject)JsonNode.Parse(big.ToJsonString())!;
        var pj = new JsonObject();
        foreach (var (k, v) in bigCfg.FlatProperties())
            pj[k] = v switch { int[] ia => new JsonArray(ia.Select(x => (JsonNode)x).ToArray()), float[] fa => new JsonArray(fa.Select(x => (JsonNode)(double)x).ToArray()), int iv => iv, float fv => (double)fv, _ => null };
        payload["payload_version"] = 1; payload["properties"] = pj;
        payload["globals"] = new JsonObject(bigCfg.GlobalValues().Select(kv => KeyValuePair.Create(kv.Key, (JsonNode?)(double)kv.Value)));
        payload.Remove("schema_version");
        var good = new (string Name, JsonObject Cfg, string[] Extras, string[] Masters, bool Light)[]
        {
            ("vanilla", vanilla, Array.Empty<string>(), new[] { "Starfield.esm" }, false),
            ("light", light, Array.Empty<string>(), new[] { "Starfield.esm" }, true),
            ("custom", custom, new[] { customPath }, new[] { "Starfield.esm", CustomKey.FileName.String }, false),
            ("payload128", payload, Array.Empty<string>(), new[] { "Starfield.esm" }, false),
        };
        foreach (var (name, c, ex, wantMasters, wantLight) in good)
        {
            var cp = Save(name + ".json", c);
            var od = Path.Combine(dir, name);
            if (Build(sfPath, cp, od, ex) != 0) return 1;
            var plugin = Path.Combine(od, c["plugin_name"]!.GetValue<string>());
            if (Check(plugin, sfPath, cp, ex) != 0) { Console.WriteLine($"FAIL  check rejected the {name} build"); return 1; }
            var styles = new List<KeyedMasterStyle> { new(SfEsm, MasterStyle.Full), new(CustomKey, MasterStyle.Full), new(ModKey.FromFileName(Path.GetFileName(plugin)), StyleOf(plugin)) };
            using var back = SF.StarfieldMod.CreateFromBinaryOverlay(plugin, Rel, Read(styles));
            var got = back.ModHeader.MasterReferences.Select(x => x.Master.FileName.String).ToArray();
            if (!got.SequenceEqual(wantMasters)) { Console.WriteLine($"FAIL  {name} masters [{string.Join(", ", got)}], want [{string.Join(", ", wantMasters)}]"); return 1; }
            if (back.ModHeader.Flags.HasFlag(SF.StarfieldModHeader.HeaderFlag.Light) != wantLight) { Console.WriteLine($"FAIL  {name} light flag"); return 1; }
            Console.WriteLine($"build ok: {name} -> masters [{string.Join(", ", got)}]{(wantLight ? ", light" : "")}");
        }

        // 2. configs build must refuse
        var refusals = new (string Name, JsonObject Cfg, string[] Extras)[]
        {
            ("129 nodes", SynthConfig(nodes: 129, edges: 129), Array.Empty<string>()),
            ("129 edges", SynthConfig(nodes: 20, edges: 129), Array.Empty<string>()),
            ("an edge to a missing node", Edit(vanilla, c => N(c, "edges", 0)["v"] = 99), Array.Empty<string>()),
            ("a zero-length edge", Edit(vanilla, c => N(c, "edges", 0)["len_m"] = 0), Array.Empty<string>()),
            ("a self-loop edge", Edit(vanilla, c => N(c, "edges", 0)["v"] = 0), Array.Empty<string>()),
            ("a duplicate edge", Edit(vanilla, c => ((JsonArray)c["edges"]!).Add(new JsonObject { ["u"] = 1, ["v"] = 0, ["len_m"] = 5 })), Array.Empty<string>()),
            ("a disconnected graph", Edit(SynthConfig(edges: 8), c => { var e = (JsonArray)c["edges"]!; e.RemoveAt(7); e.RemoveAt(3); }), Array.Empty<string>()),
            ("no hysteresis margin", Edit(vanilla, c => c["simulation"]!["offline_despawn_radius_m"] = 500.0), Array.Empty<string>()),
            ("a pool of 3", Edit(vanilla, c => c["simulation"]!["waymarker_pool_size"] = 3), Array.Empty<string>()),
            ("a pool of 17", Edit(vanilla, c => c["simulation"]!["waymarker_pool_size"] = 17), Array.Empty<string>()),
            ("17 active squads", Edit(vanilla, c => c["simulation"]!["max_active_squads"] = 17), Array.Empty<string>()),
            ("no factions", Edit(vanilla, c => c["factions"] = new JsonArray()), Array.Empty<string>()),
            ("9 factions", SynthConfig(factions: 9), Array.Empty<string>()),
            ("a squad of 9", Edit(vanilla, c => N(c, "factions", 0)["squad_size"] = 9), Array.Empty<string>()),
            ("a relation to an unknown faction", Edit(vanilla, c => N(c, "factions", 0)["relations"]!["ghost"] = "enemy"), Array.Empty<string>()),
            ("asymmetric relations", Edit(vanilla, c => N(c, "factions", 0)["relations"]!["f1"] = "ally"), Array.Empty<string>()),
            ("an initial owner out of range", Edit(vanilla, c => N(c, "nodes", 1)["initial_owner"] = 3), Array.Empty<string>()),
            ("no spawning node", Edit(vanilla, c => { foreach (var n in (JsonArray)c["nodes"]!) n!["spawn_faction"] = -1; }), Array.Empty<string>()),
            ("a relay with capacity", Edit(vanilla, c => N(c, "nodes", 0)["capacity"] = 2), Array.Empty<string>()),
            ("a non-hex FormID", Edit(vanilla, c => c["worldspace"]!["form_id"] = "0xZZ12"), Array.Empty<string>()),
            ("an .esp plugin name", Edit(vanilla, c => c["plugin_name"] = "StarfieldALife.esp"), Array.Empty<string>()),
            ("a worldspace EditorID mismatch", Edit(vanilla, c => c["worldspace"]!["editor_id"] = "OtherWorld"), Array.Empty<string>()),
            ("a template that is not an NPC_", Edit(vanilla, c => N(c, "factions", 0)["npc_template"]!["form_id"] = Hex(XMarkerHeadingId)), Array.Empty<string>()),
            ("a non-finite coordinate", Edit(vanilla, c => N(c, "nodes", 2)["x"] = 1e39), Array.Empty<string>()),
            ("duplicate node ids", Edit(vanilla, c => N(c, "nodes", 2)["id"] = "n1"), Array.Empty<string>()),
            ("masters without the custom world", Edit(custom, c => c["masters"] = new JsonArray("Starfield.esm")), new[] { customPath }),
            ("masters with an unused plugin", Edit(vanilla, c => c["masters"] = new JsonArray("Starfield.esm", CustomKey.FileName.String)), new[] { customPath }),
            ("a custom world master not supplied", custom, Array.Empty<string>()),
            ("payload properties disagreeing", Edit(payload, c => ((JsonArray)c["properties"]!["NodeCap"]!)[1] = 7), Array.Empty<string>()),
            ("payload globals disagreeing", Edit(payload, c => c["globals"]!["MaxSquads"] = 3.0), Array.Empty<string>()),
        };
        foreach (var (name, c, ex) in refusals)
        {
            var cp = Save("refuse.json", c);
            try
            {
                Build(sfPath, cp, Path.Combine(dir, "refused"), ex);
                Console.WriteLine($"FAIL  build accepted {name}");
                return 1;
            }
            catch (Refusal e) { Console.WriteLine($"refusal kept: {name} ({e.Message})"); }
        }

        // 3. tampered outputs check must reject
        var vcp = Path.Combine(dir, "vanilla.json");
        var goodPlugin = Path.Combine(dir, "vanilla", "StarfieldALife.esm");
        static SF.ScriptEntry Script(SF.StarfieldMod m) => m.Quests.First().VirtualMachineAdapter!.Scripts[0];
        static T Prop<T>(SF.StarfieldMod m, string n) where T : SF.ScriptProperty => (T)Script(m).Properties.First(p => p.Name == n);
        var foreignRef = new FormKey(SfEsm, 0x00A002);
        var mutations = new (string Name, Action<SF.StarfieldMod> Edit)[]
        {
            ("a node moved", m => Prop<SF.ScriptFloatListProperty>(m, "NodeX").Data[2] += 1f),
            ("a node kind changed", m => Prop<SF.ScriptIntListProperty>(m, "NodeKind").Data[1] = 4),
            ("an initial owner changed", m => Prop<SF.ScriptIntListProperty>(m, "NodeInitialOwner").Data[1] = 2),
            ("an edge dropped", m => Prop<SF.ScriptIntListProperty>(m, "EdgeU").Data.RemoveAt(0)),
            ("an edge length changed", m => Prop<SF.ScriptFloatListProperty>(m, "EdgeLen").Data[0] = 99f),
            ("a relation flipped in the flat matrix", m => Prop<SF.ScriptIntListProperty>(m, "FactionRelationsFlat").Data[1] = 1),
            ("the online radius changed", m => Prop<SF.ScriptFloatProperty>(m, "OnlineSpawnRadiusM").Data = 300f),
            ("a property missing", m => Script(m).Properties.RemoveAll(p => p.Name == "OptNotifications")),
            ("an extra property", m => Script(m).Properties.Add(new SF.ScriptIntProperty { Name = "Mode", Flags = SF.ScriptProperty.Flag.Edited, Data = 1 })),
            ("the squad templates reordered", m => Prop<SF.ScriptObjectListProperty>(m, "SquadTemplates").Objects.Reverse()),
            ("the waymarkers reordered", m => Prop<SF.ScriptObjectListProperty>(m, "Waymarkers").Objects.Reverse()),
            ("the script renamed", m => Script(m).Name = "FO4SF_ALifeControllerQuest"),
            ("a waymarker not persistent", m => m.Worldspaces.First().TopCell!.Persistent[0].MajorRecordFlagsRaw &= ~0x400),
            ("a waymarker disabled", m => m.Worldspaces.First().TopCell!.Persistent[1].MajorRecordFlagsRaw |= 0x800),
            ("a foreign reference copied", m => m.Worldspaces.First().TopCell!.Persistent.Add(new SF.PlacedObject(foreignRef, Rel)
                { EditorID = "SynthForeignAnchor", Base = new FormLinkNullable<SF.IPlaceableObjectGetter>(new FormKey(SfEsm, XMarkerHeadingId)) })),
            ("the quest run once", m => m.Quests.First().Data!.Flags |= SF.Quest.Flag.RunOnce),
            ("the quest not starts enabled", m => m.Quests.First().Data!.Flags &= ~SF.Quest.Flag.StartsEnabled),
            ("a global made constant", m => m.Globals.First().MajorFlags |= SF.Global.MajorFlag.Constant),
            ("a global value changed", m => m.Globals.First(g => g.FormKey.ID == MaxSquadsId).Data = 2f),
            ("an option range changed", m => ((SF.FloatGameplayOptionData)m.GameplayOptions.First(o => o.FormKey.ID == OptMaxSquadsId).Data!).Max = 32f),
            ("an option dropped from the group", m => ((SF.GameplayOptionsGroupLeaf)m.GameplayOptionsGroups.First().Options!).GameplayOptions.RemoveAt(2)),
            ("the beacon script renamed", m => m.MagicEffects.First().VirtualMachineAdapter!.Scripts[0].Name = "Other"),
            ("the transponder effect unlinked", m => m.Ingestibles.First().Effects[0].BaseEffect.SetTo(new FormKey(SfEsm, 0x00F000))),
            ("a squad made essential", m => m.Npcs.First().Flags |= SF.Npc.Flag.Essential),
            ("a squad keeps a foreign faction", m => m.Npcs.First().Factions.Add(new SF.RankPlacement { Faction = new FormLink<SF.IFactionGetter>(new FormKey(SfEsm, 0x00C000)) })),
            ("a squad keeps a script", m => m.Npcs.First().VirtualMachineAdapter = new SF.VirtualMachineAdapter { Scripts = { new SF.ScriptEntry { Name = "SynthForeignNpcScript" } } }),
            ("a squad inherits packages", m => m.Npcs.First().UseTemplateActors |= SF.Npc.TemplateActorType.AiPackages),
            ("a faction turned on the player", m => m.Factions.First(f => f.FormKey.ID == FirstFactionId + 2).Relations[0].Reaction = SF.CombatReaction.Enemy),
            ("an inter-faction relation changed", m => m.Factions.First().Relations[1].Reaction = SF.CombatReaction.Friend),
            ("the master flag dropped", m => m.ModHeader.Flags &= ~SF.StarfieldModHeader.HeaderFlag.Master),
            ("the light flag added", m => m.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Light),
            ("a foreign quest overridden", m => m.Quests.Add(new SF.Quest(new FormKey(SfEsm, 0x00E000), Rel) { EditorID = "SynthForeignQuest" })),
            ("an extra master", m => m.Factions.First().Relations.Add(new SF.Relation { Target = new FormLink<SF.IRelatableGetter>(new FormKey(CustomKey, CustomNpcId)) })),
        };
        var lo = new[] { new KeyedMasterStyle(SfEsm, MasterStyle.Full), new KeyedMasterStyle(CustomKey, MasterStyle.Full) };
        foreach (var (name, edit) in mutations)
        {
            var mod = SF.StarfieldMod.CreateFromBinary(goodPlugin, Rel, Read(lo.Append(new KeyedMasterStyle(ModKey.FromFileName("StarfieldALife.esm"), MasterStyle.Full))));
            edit(mod);
            var md = Path.Combine(dir, "mutated");
            Directory.CreateDirectory(md);
            var mp = Path.Combine(md, "StarfieldALife.esm");
            mod.BeginWrite.ToPath(mp).WithLoadOrder(lo.Select(s => s.ModKey).ToArray()).WithKnownMasters(lo).NoCheckIfLowerRangeDisallowed().Write();
            if (Check(mp, sfPath, vcp, new[] { customPath }) == 0) { Console.WriteLine($"FAIL  check passed a mutation: {name}"); return 1; }
            Console.WriteLine($"mutation rejected: {name}");
        }
        // checking against a different config is a mismatch too
        var other = Save("other.json", Edit(vanilla, c => c["simulation"]!["respawn_cooldown_s"] = 60.0));
        if (Check(goodPlugin, sfPath, other, Array.Empty<string>()) == 0) { Console.WriteLine("FAIL  check passed a build against another config"); return 1; }
        Console.WriteLine($"selftest ok: {good.Length} builds checked, {refusals.Length} refusals, {mutations.Length + 1} mutations rejected");
        return 0;
    }
}
