using System.Globalization;
using System.Text.Json;
using System.Text.RegularExpressions;
using Mutagen.Bethesda;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Aspects;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Cache;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;

namespace AuditBundle;

static class BundleAuditor
{
    private const uint StartupQuestDoId = 0x00562D;
    private const uint MapMarkerStatId = 0x000010;
    private const float MergedMinX = -4400.0f;
    private const float MergedMaxX = 2000.0f;
    private const float MergedMinY = -5900.0f;
    private const float MergedMaxY = 500.0f;
    private const float RawMinX = -3200.0f;
    private const float RawMaxX = 3200.0f;
    private const float RawMinY = -3200.0f;
    private const float RawMaxY = 3200.0f;

    private static readonly Regex PropDeclRe = new(
        @"^\s*([A-Za-z_][A-Za-z0-9_]*(?:\[\])?)\s+[Pp]roperty\s+([A-Za-z_][A-Za-z0-9_]*)\b",
        RegexOptions.Compiled);

    private static readonly Regex HookRe = new(
        @"(?i)\b(?:Event\s+(OnInit|OnQuestInit|OnPlayerLoadGame)\s*\(|(StartTimer|StartTimerGameTime|RegisterForSingleUpdate|RegisterForUpdate)\s*\()",
        RegexOptions.Compiled);

    private static readonly Regex GetFormRe = new(
        @"Game\.GetFormFromFile\s*\(\s*(0x[0-9A-Fa-f]+|\d+|[A-Za-z_][A-Za-z0-9_]*(?:\s*\[[^\]]+\])?)\s*,\s*([A-Za-z_][A-Za-z0-9_]*(?:\s*\[[^\]]+\])?|""[^""]+"")",
        RegexOptions.Compiled);

    private static readonly Regex StringConstRe = new(
        @"^\s*string\s+(?:[Pp]roperty\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*""([^""]+)""",
        RegexOptions.Compiled | RegexOptions.IgnoreCase);

    private static readonly Regex IntConstRe = new(
        @"^\s*int\s+(?:[Pp]roperty\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(0x[0-9A-Fa-f]+|\d+)",
        RegexOptions.Compiled | RegexOptions.IgnoreCase);

    private static readonly Regex ScriptNameRe = new(
        @"^\s*Scriptname\s+([A-Za-z_][A-Za-z0-9_]*)(?:\s+extends\s+([A-Za-z_][A-Za-z0-9_]*))?",
        RegexOptions.Compiled | RegexOptions.IgnoreCase);

    internal sealed record PscInfo(
        string ScriptName,
        string? ExtendsType,
        string RelPath,
        Dictionary<string, string> Properties,
        List<string> Hooks,
        Dictionary<string, uint> IntConsts,
        Dictionary<string, string> StrConsts,
        List<(string IdExpr, string PluginExpr, int Line)> RawGetFormCalls,
        List<(uint LocalId, string Plugin, int Line)> GetFormCalls);

    internal sealed record RecordMeta(
        FormKey Key,
        string TypeName,
        string? EditorId,
        string? Name);

    public static void EnsureSafeOutputPath(string outPath, string? sfDataDir)
    {
        string full = Path.GetFullPath(outPath);
        for (string? dir = Path.GetDirectoryName(full); !string.IsNullOrEmpty(dir); dir = Path.GetDirectoryName(dir))
        {
            string gitEntry = Path.Combine(dir, ".git");
            if (Directory.Exists(gitEntry) || File.Exists(gitEntry))
                throw new InvalidOperationException($"Refusing to write audit output inside Git repository: {full}");
        }
        if (!string.IsNullOrWhiteSpace(sfDataDir))
        {
            string sfRoot = Path.GetFullPath(Path.Combine(Path.GetFullPath(sfDataDir), ".."))
                .TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar) + Path.DirectorySeparatorChar;
            if (full.StartsWith(sfRoot, StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException($"Refusing to write audit output inside Starfield directory: {full}");
        }
    }

    public static MasterStyle ReadMasterStyle(string path, out uint rawFlags, out List<ModKey> declaredMasters)
    {
        declaredMasters = new List<ModKey>();
        using var fs = File.OpenRead(path);
        using var br = new BinaryReader(fs);
        byte[] magic = br.ReadBytes(4);
        if (magic.Length < 4 || magic[0] != (byte)'T' || magic[1] != (byte)'E' || magic[2] != (byte)'S' || magic[3] != (byte)'4')
            throw new InvalidDataException($"Not a TES4 plugin: {path}");
        uint dataSize = br.ReadUInt32();
        rawFlags = br.ReadUInt32();
        _ = br.ReadBytes(12); // formId (4) + revision (4) + formVersion (2) + version2 (2)
        long endPos = Math.Min(fs.Length, 24L + dataSize);
        uint? xxxxLen = null;
        while (fs.Position + 6 <= endPos)
        {
            byte[] subType = br.ReadBytes(4);
            uint subLen = br.ReadUInt16();
            if (xxxxLen.HasValue)
            {
                subLen = xxxxLen.Value;
                xxxxLen = null;
            }
            if (subType[0] == (byte)'X' && subType[1] == (byte)'X' && subType[2] == (byte)'X' && subType[3] == (byte)'X' && subLen == 4 && fs.Position + 4 <= endPos)
            {
                xxxxLen = br.ReadUInt32();
                continue;
            }
            if (fs.Position + subLen > endPos) break;
            if (subType[0] == (byte)'M' && subType[1] == (byte)'A' && subType[2] == (byte)'S' && subType[3] == (byte)'T')
            {
                byte[] strBytes = br.ReadBytes((int)subLen);
                string mastName = System.Text.Encoding.UTF8.GetString(strBytes).TrimEnd('\0').Trim();
                if (ModKey.TryFromFileName(mastName, out var mmk))
                    declaredMasters.Add(mmk);
            }
            else
            {
                fs.Position += subLen;
            }
        }
        if ((rawFlags & 0x0100u) != 0) return MasterStyle.Small;
        if ((rawFlags & 0x0400u) != 0) return MasterStyle.Medium;
        return MasterStyle.Full;
    }

    public static AuditReport Run(
        string bundleDir,
        string portEsmPath,
        string outJsonPath,
        string? sfDataDir,
        string? mapMarkersEsmPath,
        string? repoRoot)
    {
        string fullBundle = Path.GetFullPath(bundleDir);
        string fullPort = Path.GetFullPath(portEsmPath);
        if (!Directory.Exists(fullBundle))
            throw new DirectoryNotFoundException($"Bundle directory not found: {fullBundle}");
        if (!File.Exists(fullPort))
            throw new FileNotFoundException($"Port ESM not found: {fullPort}");

        string? resolvedMapMarkers = mapMarkersEsmPath;
        if (string.IsNullOrWhiteSpace(resolvedMapMarkers))
        {
            string candidate = Path.Combine(fullBundle, "map-markers", "FO4SFMapMarkers.esm");
            if (File.Exists(candidate)) resolvedMapMarkers = candidate;
        }
        if (string.IsNullOrWhiteSpace(resolvedMapMarkers) || !File.Exists(resolvedMapMarkers))
            throw new FileNotFoundException($"FO4SFMapMarkers.esm not found (checked {resolvedMapMarkers})");

        List<string> stagedNames = DiscoverBundlePluginNames(fullBundle);
        string? resolvedSfData = ResolveSfDataDir(fullBundle, sfDataDir);
        EnsureSafeOutputPath(outJsonPath, resolvedSfData);

        var pluginEntries = new List<(string Name, string Path, string Category, uint Flags, MasterStyle Style)>();
        var masterStyles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);

        var allDeclaredMasters = new HashSet<ModKey>();
        void RegisterPlugin(string path, string category)
        {
            ModKey mk = ModKey.FromFileName(Path.GetFileName(path));
            MasterStyle style = ReadMasterStyle(path, out uint flags, out var declMasters);
            masterStyles.Set(new KeyedMasterStyle(mk, style));
            foreach (var dm in declMasters) allDeclaredMasters.Add(dm);
            pluginEntries.Add((mk.FileName, Path.GetFullPath(path), category, flags, style));
        }

        // Collect official masters first
        var officialNames = new List<string>();
        if (!string.IsNullOrWhiteSpace(resolvedSfData) && Directory.Exists(resolvedSfData))
        {
            var implicitPriority = new[]
            {
                "Starfield.esm",
                "BlueprintShips-Starfield.esm",
                "constellation.esm",
                "oldmars.esm",
                "shatteredspace.esm",
            };
            foreach (string name in implicitPriority)
            {
                string p = Path.Combine(resolvedSfData, name);
                if (File.Exists(p))
                {
                    RegisterPlugin(p, "official");
                    officialNames.Add(Path.GetFileName(p));
                }
            }
            foreach (string p in Directory.GetFiles(resolvedSfData, "SFBGS*.esm").OrderBy(Path.GetFileName, StringComparer.OrdinalIgnoreCase))
            {
                RegisterPlugin(p, "official_creation");
                officialNames.Add(Path.GetFileName(p));
            }
        }

        // Load order of our 16 plugins matching Plugins.txt / runtime logs:
        // 02=FO4Port.esm, 03..10=14 staged plugins in bundle_plan order, 11=FO4SFMapMarkers.esm
        RegisterPlugin(fullPort, "port");
        foreach (string name in stagedNames)
        {
            string p = Path.Combine(fullBundle, name);
            if (!File.Exists(p)) throw new FileNotFoundException($"Staged bundle plugin not found: {p}");
            RegisterPlugin(p, "staged_bundle");
        }
        RegisterPlugin(resolvedMapMarkers, "map_markers");
        foreach (var dm in allDeclaredMasters)
        {
            if (!masterStyles.ContainsKey(dm))
                masterStyles.Set(new KeyedMasterStyle(dm, MasterStyle.Full));
        }

        var readParams = new BinaryReadParameters { MasterFlagsLookup = masterStyles };
        var loadedOfficial = new List<IStarfieldModDisposableGetter>();
        var loadedOurs = new List<IStarfieldModDisposableGetter>();
        var modInfoByKey = new Dictionary<ModKey, (string Name, string Category, uint Flags, MasterStyle Style, long Size)>();

        try
        {
            foreach (var e in pluginEntries)
            {
                var mod = StarfieldMod.CreateFromBinaryOverlay(e.Path, StarfieldRelease.Starfield, readParams);
                long sz = new FileInfo(e.Path).Length;
                modInfoByKey[mod.ModKey] = (e.Name, e.Category, e.Flags, e.Style, sz);
                if (e.Category.StartsWith("official", StringComparison.Ordinal))
                    loadedOfficial.Add(mod);
                else
                    loadedOurs.Add(mod);
            }

            return BuildReport(
                fullBundle,
                fullPort,
                resolvedMapMarkers,
                resolvedSfData,
                repoRoot,
                loadedOfficial,
                loadedOurs,
                modInfoByKey);
        }
        finally
        {
            foreach (var m in loadedOurs) m.Dispose();
            foreach (var m in loadedOfficial) m.Dispose();
        }
    }

    private static List<string> DiscoverBundlePluginNames(string bundleDir)
    {
        string planPath = Path.Combine(bundleDir, "bundle_plan.json");
        if (File.Exists(planPath))
        {
            using var doc = JsonDocument.Parse(File.ReadAllText(planPath));
            if (doc.RootElement.TryGetProperty("plugins", out var arr) && arr.ValueKind == JsonValueKind.Array)
            {
                var list = arr.EnumerateArray().Select(x => x.GetString()!).Where(x => !string.IsNullOrWhiteSpace(x)).ToList();
                if (list.Count > 0) return list;
            }
        }
        return Directory.GetFiles(bundleDir, "*.esm")
            .Select(Path.GetFileName)
            .Where(n => n != null && !n.Equals("FO4Port.esm", StringComparison.OrdinalIgnoreCase)
                                  && !n.Equals("FO4SFMapMarkers.esm", StringComparison.OrdinalIgnoreCase))
            .OrderBy(n => n, StringComparer.OrdinalIgnoreCase)
            .ToList()!;
    }

    private static string? ResolveSfDataDir(string bundleDir, string? explicitSfData)
    {
        if (!string.IsNullOrWhiteSpace(explicitSfData)) return Path.GetFullPath(explicitSfData);
        string planPath = Path.Combine(bundleDir, "bundle_plan.json");
        if (File.Exists(planPath))
        {
            using var doc = JsonDocument.Parse(File.ReadAllText(planPath));
            if (doc.RootElement.TryGetProperty("args", out var argsEl)
                && argsEl.TryGetProperty("starfield_dir", out var sfEl))
            {
                string? sfDir = sfEl.GetString();
                if (!string.IsNullOrWhiteSpace(sfDir))
                {
                    string dataDir = Path.Combine(sfDir, "Data");
                    if (Directory.Exists(dataDir)) return Path.GetFullPath(dataDir);
                }
            }
        }
        return null;
    }

    private static Dictionary<string, PscInfo> ScanRepoPscFiles(string? repoRoot)
    {
        var result = new Dictionary<string, PscInfo>(StringComparer.OrdinalIgnoreCase);
        if (string.IsNullOrWhiteSpace(repoRoot) || !Directory.Exists(repoRoot)) return result;

        foreach (string path in Directory.GetFiles(repoRoot, "*.psc", SearchOption.AllDirectories))
        {
            string rel = Path.GetRelativePath(repoRoot, path).Replace('\\', '/');
            string[] lines = File.ReadAllLines(path);
            string scriptName = Path.GetFileNameWithoutExtension(path);
            string? extendsType = null;
            var props = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
            var hooks = new List<string>();
            var strConsts = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
            var intConsts = new Dictionary<string, uint>(StringComparer.OrdinalIgnoreCase);
            var rawCalls = new List<(string, string, int)>();
            var calls = new List<(uint, string, int)>();

            for (int i = 0; i < lines.Length; i++)
            {
                string line = lines[i];
                string trimmed = line.TrimStart();
                if (trimmed.StartsWith(';')) continue;

                var sn = ScriptNameRe.Match(line);
                if (sn.Success)
                {
                    scriptName = sn.Groups[1].Value;
                    if (sn.Groups[2].Success) extendsType = sn.Groups[2].Value;
                }

                var pm = PropDeclRe.Match(line);
                if (pm.Success) props[pm.Groups[2].Value] = pm.Groups[1].Value;

                var sm = StringConstRe.Match(line);
                if (sm.Success) strConsts[sm.Groups[1].Value] = sm.Groups[2].Value;

                var im = IntConstRe.Match(line);
                if (im.Success && TryParseHexOrDec(im.Groups[2].Value, out uint iv))
                    intConsts[im.Groups[1].Value] = iv;

                foreach (Match hm in HookRe.Matches(line))
                {
                    string tok = hm.Groups[1].Success ? hm.Groups[1].Value : hm.Groups[2].Value;
                    hooks.Add($"{rel}:{i + 1} ({tok})");
                }
            }

            // Second pass for GetFormFromFile recording raw expressions and resolving local constants
            for (int i = 0; i < lines.Length; i++)
            {
                string trimmed = lines[i].TrimStart();
                if (trimmed.StartsWith(';')) continue;
                foreach (Match gm in GetFormRe.Matches(lines[i]))
                {
                    string idRaw = gm.Groups[1].Value.Trim();
                    string plRaw = gm.Groups[2].Value.Trim();
                    rawCalls.Add((idRaw, plRaw, i + 1));
                    uint localId;
                    if (!TryParseHexOrDec(idRaw, out localId))
                    {
                        if (!intConsts.TryGetValue(idRaw, out localId)) continue;
                    }
                    string pluginName;
                    if (plRaw.StartsWith('"')) pluginName = plRaw.Trim('"');
                    else if (!strConsts.TryGetValue(plRaw, out pluginName!)) continue;
                    calls.Add((localId, pluginName, i + 1));
                }
            }

            result[scriptName] = new PscInfo(scriptName, extendsType, rel, props, hooks, intConsts, strConsts, rawCalls, calls);
        }
        return result;
    }

    private static bool TryParseHexOrDec(string s, out uint value)
    {
        if (s.StartsWith("0x", StringComparison.OrdinalIgnoreCase))
            return uint.TryParse(s.AsSpan(2), NumberStyles.HexNumber, CultureInfo.InvariantCulture, out value);
        return uint.TryParse(s, NumberStyles.Integer, CultureInfo.InvariantCulture, out value);
    }

    private static AuditReport BuildReport(
        string bundleDir,
        string portPath,
        string mapMarkersPath,
        string? sfDataDir,
        string? repoRoot,
        List<IStarfieldModDisposableGetter> officialMods,
        List<IStarfieldModDisposableGetter> ourMods,
        Dictionary<ModKey, (string Name, string Category, uint Flags, MasterStyle Style, long Size)> modInfoByKey)
    {
        var report = new AuditReport
        {
            BundleDir = bundleDir,
            PortEsm = portPath,
            MapMarkersEsm = mapMarkersPath,
            SfDataDir = sfDataDir,
        };

        var pscByScript = ScanRepoPscFiles(repoRoot);
        var officialModKeys = officialMods.Select(m => m.ModKey).ToHashSet();
        var ourModKeys = ourMods.Select(m => m.ModKey).ToHashSet();

        // Compute runtime slot prefixes matching Starfield runtime load order:
        // Non-Blueprint Full official masters load before player plugins: Starfield.esm (00), SFBGS00D.esm (01).
        // Blueprint Full masters (header flag 0x0800, e.g. BlueprintShips-Starfield.esm) load after Full plugins.
        // Medium (0x0400 -> FD:xx) and Small (0x0100 -> FE:xxx) use light/medium slots.
        var slotByMod = new Dictionary<ModKey, string>();
        int nextFull = 0;
        int nextMed = 0;
        int nextSmall = 0;
        var blueprintOfficialMods = new List<ModKey>();
        foreach (var m in officialMods)
        {
            var info = modInfoByKey[m.ModKey];
            if (info.Style == MasterStyle.Medium)
            {
                slotByMod[m.ModKey] = $"FD:{nextMed++:X2}";
            }
            else if (info.Style == MasterStyle.Small)
            {
                slotByMod[m.ModKey] = $"FE:{nextSmall++:X3}";
            }
            else if ((info.Flags & 0x0800u) != 0)
            {
                blueprintOfficialMods.Add(m.ModKey);
            }
            else
            {
                slotByMod[m.ModKey] = $"{nextFull++:X2}";
            }
        }
        foreach (var m in ourMods)
        {
            var info = modInfoByKey[m.ModKey];
            slotByMod[m.ModKey] = info.Style switch
            {
                MasterStyle.Small => $"FE:{nextSmall++:X3}",
                MasterStyle.Medium => $"FD:{nextMed++:X2}",
                _ => $"{nextFull++:X2}",
            };
        }
        foreach (var bmk in blueprintOfficialMods)
        {
            slotByMod[bmk] = $"{nextFull++:X2}";
        }

        string FormatRuntimeId(FormKey fk)
        {
            if (fk.IsNull) return "00000000";
            if (slotByMod.TryGetValue(fk.ModKey, out var slot) && slot.Length == 2)
                return $"{slot}{fk.ID:X6}";
            if (slot != null && (slot.StartsWith("FD:") || slot.StartsWith("FE:")))
                return $"{slot}:{fk.ID:X4}";
            return $"??{fk.ID:X6}";
        }

        // LinkCaches for resolving targets cleanly
        var officialCache = officialMods.ToImmutableLinkCache();
        var fullCache = officialMods.Concat(ourMods).ToImmutableLinkCache();

        // Single-pass index of defining records, overrides, and references across our 16 plugins
        var definingMeta = new Dictionary<FormKey, RecordMeta>();
        var definingOurRecords = new Dictionary<FormKey, IMajorRecordGetter>();
        var overridesByMod = new Dictionary<ModKey, List<IMajorRecordGetter>>();
        var definedCountByMod = new Dictionary<ModKey, int>();
        var overrideCountByMod = new Dictionary<ModKey, int>();
        var targetTouches = new Dictionary<FormKey, TargetTouchAccumulator>();
        var allOurQuests = new List<(ModKey Mod, IQuestGetter Quest)>();
        var scriptAttachments = new Dictionary<string, List<string>>(StringComparer.OrdinalIgnoreCase);
        var mapMarkerRefs = new List<(ModKey Mod, bool IsOverride, IPlacedObjectGetter Ref)>();
        var questMarkerAssignments = new Dictionary<FormKey, List<string>>();
        var nonMapMarkersInQuestArrays = new List<string>();
        var ourLocations = new List<(ModKey Mod, bool IsOverride, ILocationGetter Rec)>();
        var ourWorldspaces = new List<(ModKey Mod, bool IsOverride, IWorldspaceGetter Rec)>();
        var ourPlanets = new List<(ModKey Mod, bool IsOverride, IPlanetGetter Rec)>();
        var ourMessages = new List<(ModKey Mod, bool IsOverride, IMessageGetter Rec)>();
        var ourNamedCells = new List<(ModKey Mod, bool IsOverride, ICellGetter Rec)>();
        var ourLscrTargets = new HashSet<FormKey>();
        int totalQuestArraySlots = 0;
        int mapMarkersQuestCount = 0;

        TargetTouchAccumulator GetAcc(FormKey fk)
        {
            if (!targetTouches.TryGetValue(fk, out var acc))
            {
                acc = new TargetTouchAccumulator(fk);
                targetTouches[fk] = acc;
            }
            return acc;
        }

        RecordMeta? ResolveMeta(FormKey fk)
        {
            if (fk.IsNull) return null;
            if (definingMeta.TryGetValue(fk, out var m)) return m;
            if (fullCache.TryResolve<IMajorRecordGetter>(fk, out var rec))
            {
                string typeName = rec.Registration.ClassType.Name;
                string? name = (rec as INamedGetter)?.Name;
                var rm = new RecordMeta(fk, typeName, rec.EditorID, name);
                definingMeta[fk] = rm;
                return rm;
            }
            return null;
        }

        // First scan our 16 plugins once each
        var sfMapMarkerBase = new FormKey(ModKey.FromFileName("Starfield.esm"), MapMarkerStatId);

        foreach (var mod in ourMods)
        {
            overridesByMod[mod.ModKey] = new List<IMajorRecordGetter>();
            int defCnt = 0;
            int ovrCnt = 0;

            foreach (var rec in mod.EnumerateMajorRecords())
            {
                bool isOvr = rec.FormKey.ModKey != mod.ModKey;
                string typeName = rec.Registration.ClassType.Name;

                if (isOvr)
                {
                    ovrCnt++;
                    overridesByMod[mod.ModKey].Add(rec);
                    var acc = GetAcc(rec.FormKey);
                    acc.OverriddenIn.Add(mod.ModKey.FileName);
                    if (rec is ILoadScreenGetter) ourLscrTargets.Add(rec.FormKey);
                }
                else
                {
                    defCnt++;
                    string? nm = (rec as INamedGetter)?.Name;
                    definingMeta[rec.FormKey] = new RecordMeta(rec.FormKey, typeName, rec.EditorID, nm);
                    definingOurRecords[rec.FormKey] = rec;
                    GetAcc(rec.FormKey).DefinedIn ??= mod.ModKey.FileName;
                }

                // Collect structural references
                foreach (var link in rec.EnumerateFormLinks())
                {
                    if (link.FormKey.IsNull) continue;
                    var acc = GetAcc(link.FormKey);
                    acc.ReferencedByPlugins.Add(mod.ModKey.FileName);
                    if (acc.ReferenceSites.Count < 25)
                        acc.ReferenceSites.Add($"{mod.ModKey.FileName}:{typeName}:{FormatRuntimeId(rec.FormKey)}({rec.EditorID ?? "-"})");
                }

                if (rec is IPlacedObjectGetter po && po.Base.FormKey == sfMapMarkerBase)
                {
                    mapMarkerRefs.Add((mod.ModKey, isOvr, po));
                }
                if (rec is IQuestGetter q)
                {
                    allOurQuests.Add((mod.ModKey, q));
                }
                if (rec is ILocationGetter loc) ourLocations.Add((mod.ModKey, isOvr, loc));
                else if (rec is IWorldspaceGetter wrld) ourWorldspaces.Add((mod.ModKey, isOvr, wrld));
                else if (rec is IPlanetGetter pndt) ourPlanets.Add((mod.ModKey, isOvr, pndt));
                else if (rec is IMessageGetter msg) ourMessages.Add((mod.ModKey, isOvr, msg));
                else if (rec is ICellGetter cell && !string.IsNullOrWhiteSpace(cell.EditorID)) ourNamedCells.Add((mod.ModKey, isOvr, cell));
            }

            definedCountByMod[mod.ModKey] = defCnt;
            overrideCountByMod[mod.ModKey] = ovrCnt;
        }

        // Map psc GetFormFromFile references back to plugins that ship each script in VMAD
        // First collect VMAD attachments + script bindings (Section 3 & 4)
        var attachedScriptsByMod = new Dictionary<string, HashSet<string>>(StringComparer.OrdinalIgnoreCase);

        void RecordAttachment(string scriptName, string attachmentDesc, string pluginFile)
        {
            if (string.IsNullOrWhiteSpace(scriptName)) return;
            if (!scriptAttachments.TryGetValue(scriptName, out var list))
            {
                list = new List<string>();
                scriptAttachments[scriptName] = list;
            }
            if (!list.Contains(attachmentDesc)) list.Add(attachmentDesc);
            if (!attachedScriptsByMod.TryGetValue(scriptName, out var modsSet))
            {
                modsSet = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
                attachedScriptsByMod[scriptName] = modsSet;
            }
            modsSet.Add(pluginFile);
        }

        void InspectScriptEntry(
            IStarfieldModDisposableGetter hostMod,
            IMajorRecordGetter hostRec,
            string context,
            IScriptEntryGetter entry)
        {
            string sname = entry.Name ?? "";
            string hostFk = hostRec.FormKey.ToString();
            string hostRt = FormatRuntimeId(hostRec.FormKey);
            string hostType = hostRec.Registration.ClassType.Name;
            string pluginFile = hostMod.ModKey.FileName;
            RecordAttachment(sname, $"{pluginFile} {hostType} {hostRt} ({hostRec.EditorID ?? "-"}) [{context}]", pluginFile);

            report.ScriptBindings.TotalScriptEntries++;
            pscByScript.TryGetValue(sname, out var psc);
            var propList = new List<ScriptPropertyEntry>();
            var declaredMasters = hostMod.ModHeader.MasterReferences.Select(mr => mr.Master).ToHashSet();
            var vmadInts = new Dictionary<string, uint>(StringComparer.OrdinalIgnoreCase);
            var vmadStrs = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
            var vmadIntLists = new Dictionary<string, List<uint>>(StringComparer.OrdinalIgnoreCase);
            var vmadStrLists = new Dictionary<string, List<string>>(StringComparer.OrdinalIgnoreCase);

            foreach (var prop in entry.Properties)
            {
                report.ScriptBindings.TotalProperties++;
                string? declType = psc != null && psc.Properties.TryGetValue(prop.Name, out var dt) ? dt : null;

                if (prop is IScriptObjectPropertyGetter objProp)
                {
                    var target = AnalyzeObjectTarget(null, objProp.Object.FormKey, objProp.Alias);
                    propList.Add(new ScriptPropertyEntry
                    {
                        Name = prop.Name,
                        Kind = "Object",
                        DeclaredPscType = declType,
                        Targets = new List<ScriptObjectTarget> { target },
                    });
                }
                else if (prop is IScriptObjectListPropertyGetter listProp)
                {
                    var targets = new List<ScriptObjectTarget>();
                    for (int idx = 0; idx < listProp.Objects.Count; idx++)
                    {
                        var item = listProp.Objects[idx];
                        var target = AnalyzeObjectTarget(idx, item.Object.FormKey, item.Alias);
                        targets.Add(target);
                        if (sname.Equals("FO4SF_MapMarkers", StringComparison.OrdinalIgnoreCase)
                            && prop.Name.Equals("Markers", StringComparison.OrdinalIgnoreCase))
                        {
                            totalQuestArraySlots++;
                            if (!item.Object.IsNull)
                            {
                                if (!questMarkerAssignments.TryGetValue(item.Object.FormKey, out var qList))
                                {
                                    qList = new List<string>();
                                    questMarkerAssignments[item.Object.FormKey] = qList;
                                }
                                qList.Add($"{hostRec.EditorID ?? hostRt}[{idx}]");
                                if (target.ResolvedType != null && !target.ResolvedEditorId?.Contains("MapMarker") == true && target.ResolvedType != "PlacedObject")
                                {
                                    nonMapMarkersInQuestArrays.Add($"{hostRec.EditorID ?? hostRt}[{idx}] -> {FormatRuntimeId(item.Object.FormKey)}");
                                }
                            }
                        }
                    }
                    propList.Add(new ScriptPropertyEntry
                    {
                        Name = prop.Name,
                        Kind = $"ObjectList[{listProp.Objects.Count}]",
                        DeclaredPscType = declType,
                        Targets = targets,
                    });
                }
                else
                {
                    if (prop is IScriptIntPropertyGetter ip2 && ip2.Data > 0)
                        vmadInts[prop.Name] = (uint)ip2.Data;
                    else if (prop is IScriptStringPropertyGetter sp2 && !string.IsNullOrWhiteSpace(sp2.Data))
                        vmadStrs[prop.Name] = sp2.Data;
                    else if (prop is IScriptIntListPropertyGetter ilp)
                        vmadIntLists[prop.Name] = ilp.Data.Where(v => v > 0).Select(v => (uint)v).ToList();
                    else if (prop is IScriptStringListPropertyGetter slp)
                        vmadStrLists[prop.Name] = slp.Data.ToList();

                    string val = prop switch
                    {
                        IScriptIntPropertyGetter ip => ip.Data.ToString(CultureInfo.InvariantCulture),
                        IScriptFloatPropertyGetter fp => fp.Data.ToString("G", CultureInfo.InvariantCulture),
                        IScriptBoolPropertyGetter bp => bp.Data ? "true" : "false",
                        IScriptStringPropertyGetter sp => sp.Data ?? "",
                        IScriptIntListPropertyGetter il => $"[{il.Data.Count} ints]",
                        IScriptFloatListPropertyGetter fl => $"[{fl.Data.Count} floats]",
                        IScriptStringListPropertyGetter sl => $"[{sl.Data.Count} strings]",
                        IScriptBoolListPropertyGetter bl => $"[{bl.Data.Count} bools]",
                        _ => prop.GetType().Name.Replace("BinaryOverlay", ""),
                    };
                    propList.Add(new ScriptPropertyEntry
                    {
                        Name = prop.Name,
                        Kind = prop.GetType().Name.Replace("Script", "").Replace("PropertyBinaryOverlay", ""),
                        DeclaredPscType = declType,
                        Value = val,
                    });
                }

                ScriptObjectTarget AnalyzeObjectTarget(int? idx, FormKey fk, short aliasIdx)
                {
                    var flags = new List<string>();
                    RecordMeta? meta = fk.IsNull ? null : ResolveMeta(fk);
                    string targetPlugin = fk.IsNull ? "None" : fk.ModKey.FileName.String;
                    string rt = FormatRuntimeId(fk);

                    if (fk.IsNull)
                    {
                        flags.Add("none_property");
                        report.ScriptBindings.NonePropertyCount++;
                    }
                    else
                    {
                        var acc = GetAcc(fk);
                        acc.ReferencedByPlugins.Add(pluginFile);
                        if (acc.ReferenceSites.Count < 25)
                            acc.ReferenceSites.Add($"{pluginFile}:VMAD:{sname}.{prop.Name}{(idx.HasValue ? $"[{idx}]" : "")}@{hostRt}");

                        if (meta == null)
                        {
                            flags.Add("unresolved_form");
                            report.ScriptBindings.UnresolvedCount++;
                        }
                        if (fk.ModKey != hostMod.ModKey)
                        {
                            flags.Add("cross_plugin");
                            report.ScriptBindings.CrossPluginCount++;
                            int hostWeight = OrderWeight(slotByMod.GetValueOrDefault(hostMod.ModKey));
                            bool masterValidAndPrior = declaredMasters.Contains(fk.ModKey)
                                && slotByMod.TryGetValue(fk.ModKey, out var targetSlot)
                                && targetSlot != "UNLISTED_FULL"
                                && !(hostWeight >= 0 && OrderWeight(targetSlot) >= 0 && OrderWeight(targetSlot) > hostWeight);
                            if (!masterValidAndPrior)
                            {
                                flags.Add("missing_master_for_cross_plugin");
                                report.ScriptBindings.MissingMasterCrossPluginCount++;
                            }
                        }
                        if (meta != null && declType != null && !IsCompatiblePscType(declType, meta.TypeName, pscByScript))
                        {
                            flags.Add($"wrong_type(declared={declType},actual={meta.TypeName})");
                            report.ScriptBindings.WrongTypeCount++;
                        }
                    }

                    if (flags.Any(f => f != "cross_plugin" || fk.ModKey != ModKey.FromFileName("Starfield.esm")))
                    {
                        // Flag None, unresolved, cross-plugin to non-Starfield (or missing master), or wrong type
                        if (flags.Contains("none_property") || flags.Contains("unresolved_form")
                            || flags.Contains("missing_master_for_cross_plugin")
                            || flags.Any(f => f.StartsWith("wrong_type", StringComparison.Ordinal))
                            || (flags.Contains("cross_plugin") && !fk.ModKey.FileName.String.Equals("Starfield.esm", StringComparison.OrdinalIgnoreCase)))
                        {
                            report.ScriptBindings.FlaggedBindings.Add(new ScriptBindingEntry
                            {
                                Plugin = pluginFile,
                                HostFormKey = hostFk,
                                HostEditorId = hostRec.EditorID,
                                Context = context,
                                ScriptName = sname,
                                PropertyName = prop.Name,
                                DeclaredPscType = declType,
                                Index = idx,
                                TargetFormKey = fk.IsNull ? "Null" : fk.ToString(),
                                TargetRuntimeId = rt,
                                TargetPlugin = targetPlugin,
                                ResolvedType = meta?.TypeName,
                                ResolvedEditorId = meta?.EditorId,
                                Flags = flags,
                            });
                        }
                    }

                    return new ScriptObjectTarget
                    {
                        Index = idx,
                        FormKey = fk.IsNull ? "Null" : fk.ToString(),
                        RuntimeId = rt,
                        Alias = aliasIdx,
                        ResolvedType = meta?.TypeName,
                        ResolvedEditorId = meta?.EditorId,
                        TargetPlugin = targetPlugin,
                        Flags = flags,
                    };
                }
            }

            // Resolve VMAD-backed GetFormFromFile(intProp/intList, strProp/strList) soft references on this script instance
            if (psc != null)
            {
                foreach (var (idExpr, plExpr, lineNo) in psc.RawGetFormCalls)
                {
                    int brkId = idExpr.IndexOf('[');
                    string idBase = brkId > 0 ? idExpr[..brkId].Trim() : idExpr;
                    int brkPl = plExpr.IndexOf('[');
                    string plBase = brkPl > 0 ? plExpr[..brkPl].Trim() : plExpr;

                    string? singlePlugin = null;
                    if (plExpr.StartsWith('"')) singlePlugin = plExpr.Trim('"');
                    else if (!vmadStrs.TryGetValue(plBase, out singlePlugin))
                        psc.StrConsts.TryGetValue(plBase, out singlePlugin);

                    if (brkId > 0 && vmadIntLists.TryGetValue(idBase, out var idList))
                    {
                        if (brkPl > 0 && vmadStrLists.TryGetValue(plBase, out var plList))
                        {
                            int n = Math.Min(idList.Count, plList.Count);
                            for (int k = 0; k < n; k++)
                                RecordSoftGetForm(idList[k], plList[k], $"{idBase}[{k}]", lineNo);
                        }
                        else if (!string.IsNullOrWhiteSpace(singlePlugin))
                        {
                            foreach (uint lid in idList)
                                RecordSoftGetForm(lid, singlePlugin, idExpr, lineNo);
                        }
                        continue;
                    }

                    if (string.IsNullOrWhiteSpace(singlePlugin)) continue;
                    uint resolvedId;
                    if (!TryParseHexOrDec(idBase, out resolvedId)
                        && !vmadInts.TryGetValue(idBase, out resolvedId)
                        && !psc.IntConsts.TryGetValue(idBase, out resolvedId))
                    {
                        continue;
                    }
                    if (resolvedId > 0)
                        RecordSoftGetForm(resolvedId, singlePlugin, idExpr, lineNo);
                }

                void RecordSoftGetForm(uint localId, string targetPluginName, string exprLabel, int lineNo)
                {
                    if (!ModKey.TryFromFileName(targetPluginName, out var targetMk)) return;
                    var fk = new FormKey(targetMk, localId);
                    var acc = GetAcc(fk);
                    acc.ScriptGetFormPlugins.Add(pluginFile);
                    string site = $"{pluginFile}:GetFormFromFile({exprLabel}=0x{localId:X6},{targetPluginName}):{psc.RelPath}:{lineNo}";
                    if (acc.ReferenceSites.Count < 25 && !acc.ReferenceSites.Contains(site))
                        acc.ReferenceSites.Add(site);
                }
            }

            report.ScriptBindings.AllScripts.Add(new ScriptSummaryEntry
            {
                Plugin = pluginFile,
                HostFormKey = hostFk,
                HostRuntimeId = hostRt,
                HostType = hostType,
                HostEditorId = hostRec.EditorID,
                Context = context,
                ScriptName = sname,
                PropertyCount = propList.Count,
                Properties = propList,
            });
        }

        // Walk VMAD on all records in our 16 plugins
        foreach (var mod in ourMods)
        {
            foreach (var rec in mod.EnumerateMajorRecords())
            {
                if (rec is IHaveVirtualMachineAdapterGetter hvma && hvma.VirtualMachineAdapter != null)
                {
                    var vma = hvma.VirtualMachineAdapter;
                    foreach (var se in vma.Scripts)
                        InspectScriptEntry(mod, rec, "record_script", se);

                    if (vma is IQuestAdapterGetter qa)
                    {
                        if (!string.IsNullOrWhiteSpace(qa.Script?.Name))
                            InspectScriptEntry(mod, rec, "quest_fragment", qa.Script);
                        foreach (var al in qa.Aliases)
                            foreach (var se in al.Scripts)
                                InspectScriptEntry(mod, rec, $"quest_alias:{al.Property.Name}", se);
                    }
                    else if (vma is IPackageAdapterGetter pa && pa.ScriptFragments?.Script != null && !string.IsNullOrWhiteSpace(pa.ScriptFragments.Script.Name))
                    {
                        InspectScriptEntry(mod, rec, "package_fragment", pa.ScriptFragments.Script);
                    }
                    else if (vma is IDialogResponsesAdapterGetter da && da.ScriptFragments?.Script != null && !string.IsNullOrWhiteSpace(da.ScriptFragments.Script.Name))
                    {
                        InspectScriptEntry(mod, rec, "dialog_fragment", da.ScriptFragments.Script);
                    }
                    else if (vma is ISceneAdapterGetter sa && sa.ScriptFragments?.Script != null && !string.IsNullOrWhiteSpace(sa.ScriptFragments.Script.Name))
                    {
                        InspectScriptEntry(mod, rec, "scene_fragment", sa.ScriptFragments.Script);
                    }
                    else if (vma is IPerkAdapterGetter pka && pka.ScriptFragments?.Script != null && !string.IsNullOrWhiteSpace(pka.ScriptFragments.Script.Name))
                    {
                        InspectScriptEntry(mod, rec, "perk_fragment", pka.ScriptFragments.Script);
                    }
                }
            }
        }

        // Add script-level GetFormFromFile links for attached scripts
        foreach (var kv in pscByScript)
        {
            string sname = kv.Key;
            var psc = kv.Value;
            if (!attachedScriptsByMod.TryGetValue(sname, out var hostPlugins))
            {
                // Still check for Placement helper library called by NewGame/LoadDoor
                if (sname.Equals("FO4SF_Placement", StringComparison.OrdinalIgnoreCase))
                    hostPlugins = new HashSet<string>(StringComparer.OrdinalIgnoreCase) { "FO4SFNewGame.esm" };
                else
                    continue;
            }
            foreach (var (localId, targetPluginName, lineNo) in psc.GetFormCalls)
            {
                if (!ModKey.TryFromFileName(targetPluginName, out var targetMk)) continue;
                var fk = new FormKey(targetMk, localId);
                var acc = GetAcc(fk);
                foreach (string hp in hostPlugins)
                {
                    acc.ScriptGetFormPlugins.Add(hp);
                    if (acc.ReferenceSites.Count < 25)
                        acc.ReferenceSites.Add($"{hp}:GetFormFromFile:{psc.RelPath}:{lineNo}");
                }
            }
        }

        // Populate LoadOrder & OfficialPlugins headers
        foreach (var mod in ourMods)
        {
            var info = modInfoByKey[mod.ModKey];
            var masters = mod.ModHeader.MasterReferences.Select(m => m.Master.FileName.String).ToList();
            report.LoadOrder.Add(new PluginHeaderInfo
            {
                Plugin = info.Name,
                Category = info.Category,
                SlotHex = slotByMod[mod.ModKey],
                MasterStyle = info.Style.ToString(),
                RawHeaderFlags = $"0x{info.Flags:X8}",
                SizeBytes = info.Size,
                Masters = masters,
                MissingOrLateMasters = FindBadMasters(mod.ModKey, masters, slotByMod),
                DefiningRecords = definedCountByMod.GetValueOrDefault(mod.ModKey),
                OverrideRecords = overrideCountByMod.GetValueOrDefault(mod.ModKey),
            });
        }
        foreach (var mod in officialMods)
        {
            var info = modInfoByKey[mod.ModKey];
            report.OfficialPlugins.Add(new PluginHeaderInfo
            {
                Plugin = info.Name,
                Category = info.Category,
                SlotHex = slotByMod[mod.ModKey],
                MasterStyle = info.Style.ToString(),
                RawHeaderFlags = $"0x{info.Flags:X8}",
                SizeBytes = info.Size,
                Masters = mod.ModHeader.MasterReferences.Select(m => m.Master.FileName.String).ToList(),
            });
        }

        // Section 1: Overrides
        foreach (var mod in ourMods)
        {
            foreach (var rec in overridesByMod[mod.ModKey])
            {
                string targetOwner = rec.FormKey.ModKey.FileName;
                bool isOfficial = officialModKeys.Contains(rec.FormKey.ModKey);
                var changes = DescribeOverrideDiff(rec, officialCache, definingOurRecords);
                var entry = new OverrideEntry
                {
                    Plugin = mod.ModKey.FileName.String,
                    FormKey = rec.FormKey.ToString(),
                    RuntimeId = FormatRuntimeId(rec.FormKey),
                    RecordType = rec.Registration.ClassType.Name,
                    EditorId = rec.EditorID,
                    TargetOwner = targetOwner,
                    Changes = changes,
                };
                if (isOfficial)
                {
                    report.Overrides.OfficialOverrides.Add(entry);
                    report.Overrides.OfficialOverrideCount++;
                    report.Overrides.ByPlugin[mod.ModKey.FileName.String] =
                        report.Overrides.ByPlugin.GetValueOrDefault(mod.ModKey.FileName.String) + 1;
                }
                else if (ourModKeys.Contains(rec.FormKey.ModKey))
                {
                    report.Overrides.OurCrossPluginOverrides.Add(entry);
                    report.Overrides.OurCrossPluginOverrideCount++;
                }
            }
        }

        // Section 5: Persistent references (computed before Section 2 so focus/shared entries carry persistent/temporary context)
        var persistentByFk = new Dictionary<FormKey, PersistentRefEntry>();
        foreach (var mod in ourMods)
        {
            void AddPersistent(IPlacedGetter placed, ICellGetter cell, IWorldspaceGetter? wrld)
            {
                bool isOvr = placed.FormKey.ModKey != mod.ModKey;
                FormKey? baseFk = null;
                string? baseType = null;
                string? baseEdid = null;
                bool isMapMarker = false;
                string? xtel = null;
                P3Float pos = default;
                P3Float rot = default;

                if (placed is IPlacedObjectGetter po)
                {
                    baseFk = po.Base.FormKey;
                    pos = po.Position;
                    rot = po.Rotation;
                    isMapMarker = baseFk == sfMapMarkerBase;
                    if (po.TeleportDestination != null && !po.TeleportDestination.Door.IsNull)
                        xtel = $"{po.TeleportDestination.Door.FormKey} pos=({po.TeleportDestination.Position.X:F1},{po.TeleportDestination.Position.Y:F1},{po.TeleportDestination.Position.Z:F1}) flags={po.TeleportDestination.Flags}";
                }
                else if (placed is IPlacedNpcGetter pn)
                {
                    baseFk = pn.Base.FormKey;
                    pos = pn.Position;
                    rot = pn.Rotation;
                }
                if (baseFk.HasValue && !baseFk.Value.IsNull)
                {
                    var bm = ResolveMeta(baseFk.Value);
                    baseType = bm?.TypeName;
                    baseEdid = bm?.EditorId;
                }

                string frame = ClassifyFrame(wrld, pos, mod.ModKey.FileName.String);
                int scriptCnt = (placed is IHaveVirtualMachineAdapterGetter hv && hv.VirtualMachineAdapter != null)
                    ? hv.VirtualMachineAdapter.Scripts.Count : 0;
                bool disabled = (placed.MajorRecordFlagsRaw & 0x0800) != 0;

                var prefEntry = new PersistentRefEntry
                {
                    Plugin = mod.ModKey.FileName.String,
                    FormKey = placed.FormKey.ToString(),
                    RuntimeId = FormatRuntimeId(placed.FormKey),
                    IsOverride = isOvr,
                    EditorId = placed.EditorID,
                    RecordKind = placed is IPlacedNpcGetter ? "ACHR" : "REFR",
                    BaseFormKey = baseFk?.ToString(),
                    BaseType = baseType,
                    BaseEditorId = baseEdid,
                    CellFormKey = cell.FormKey.ToString(),
                    CellEditorId = cell.EditorID,
                    WorldspaceFormKey = wrld?.FormKey.ToString(),
                    WorldspaceEditorId = wrld?.EditorID ?? "Interior",
                    Position = new[] { pos.X, pos.Y, pos.Z },
                    Rotation = new[] { rot.X, rot.Y, rot.Z },
                    Frame = frame,
                    InitiallyDisabled = disabled,
                    IsMapMarker = isMapMarker,
                    TeleportDest = xtel,
                    ScriptCount = scriptCnt,
                };
                report.PersistentReferences.Refs.Add(prefEntry);
                persistentByFk[placed.FormKey] = prefEntry;
                report.PersistentReferences.TotalPersistentRefs++;
                report.PersistentReferences.ByPlugin[mod.ModKey.FileName.String] =
                    report.PersistentReferences.ByPlugin.GetValueOrDefault(mod.ModKey.FileName.String) + 1;
                report.PersistentReferences.ByFrame[frame] =
                    report.PersistentReferences.ByFrame.GetValueOrDefault(frame) + 1;
            }

            foreach (var blk in mod.Cells.Records)
                foreach (var sub in blk.SubBlocks)
                    foreach (var cell in sub.Cells)
                        foreach (var p in cell.Persistent)
                            AddPersistent(p, cell, null);

            foreach (var w in mod.Worldspaces)
            {
                if (w.TopCell != null)
                    foreach (var p in w.TopCell.Persistent)
                        AddPersistent(p, w.TopCell, w);
                foreach (var blk in w.SubCells)
                    foreach (var sub in blk.Items)
                        foreach (var cell in sub.Items)
                            foreach (var p in cell.Persistent)
                                AddPersistent(p, cell, w);
            }
        }

        // Section 2: Shared records + focus forms + map markers
        var focusSpecs = new (string Label, ModKey Mod, uint LocalId)[]
        {
            ("040A775B Vault 111 MapMarker", ModKey.FromFileName("FO4TerrainCore.esm"), 0x0A775B),
            ("040A775C Concord MapMarker", ModKey.FromFileName("FO4TerrainCore.esm"), 0x0A775C),
            ("04000800 CommonwealthAnchor", ModKey.FromFileName("FO4TerrainCore.esm"), 0x000800),
            ("0B000827 NewGame DiscoveryMarker", ModKey.FromFileName("FO4SFNewGame.esm"), 0x000827),
            ("04005A77 Surface Cog Ref", ModKey.FromFileName("FO4TerrainCore.esm"), 0x005A77),
            ("040A2D4B Surface Cog Base Activator", ModKey.FromFileName("FO4TerrainCore.esm"), 0x0A2D4B),
            ("02001618 Port Exit Lift Ref", ModKey.FromFileName("FO4Port.esm"), 0x001618),
            ("0200E0E6 Port Exit Lift Base Activator", ModKey.FromFileName("FO4Port.esm"), 0x00E0E6),
            ("0200DEF9 Vault Gear Door Base", ModKey.FromFileName("FO4Port.esm"), 0x00DEF9),
            ("09000801 PlayerCryoPodRef", ModKey.FromFileName("FO4SFVaultPod.esm"), 0x000801),
            ("0B000819 GearDoorConsoleRef", ModKey.FromFileName("FO4SFNewGame.esm"), 0x000819),
            ("0B00080F PipboyCorpsePickupRef", ModKey.FromFileName("FO4SFNewGame.esm"), 0x00080F),
            ("0A000811 CodsworthRef", ModKey.FromFileName("FO4SFMission.esm"), 0x000811),
            ("110008F2 Landing Area Marker", ModKey.FromFileName("FO4SFMapMarkers.esm"), 0x0008F2),
        };

        SharedRecordEntry BuildSharedEntry(FormKey fk, string? label, TargetTouchAccumulator? acc)
        {
            var meta = ResolveMeta(fk);
            var touched = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            if (acc != null)
            {
                if (acc.DefinedIn != null) touched.Add(acc.DefinedIn);
                foreach (var x in acc.OverriddenIn) touched.Add(x);
                foreach (var x in acc.ReferencedByPlugins) touched.Add(x);
                foreach (var x in acc.ScriptGetFormPlugins) touched.Add(x);
            }
            string? detail = null;
            if (persistentByFk.TryGetValue(fk, out var pref))
            {
                detail = $"persistent=True cell={pref.CellFormKey}({pref.CellEditorId ?? "-"}) world={pref.WorldspaceEditorId} base={pref.BaseFormKey}({pref.BaseEditorId ?? "-"}) pos=({pref.Position[0]:F2},{pref.Position[1]:F2},{pref.Position[2]:F2}) frame={pref.Frame}";
            }
            else if (label != null && definingOurRecords.TryGetValue(fk, out var dRec) && dRec is IPlacedObjectGetter tpo)
            {
                ICellGetter? parentCell = null;
                if (fullCache.TryResolveSimpleContext<IPlacedObjectGetter>(fk, out var sCtx))
                    parentCell = sCtx.Parent?.Record as ICellGetter;
                var bMeta = ResolveMeta(tpo.Base.FormKey);
                detail = $"persistent=False(temporary) cell={parentCell?.FormKey}({parentCell?.EditorID ?? "-"}) base={tpo.Base.FormKey}({bMeta?.EditorId ?? "-"}) pos=({tpo.Position.X:F2},{tpo.Position.Y:F2},{tpo.Position.Z:F2})";
            }
            return new SharedRecordEntry
            {
                Label = label,
                FormKey = fk.ToString(),
                RuntimeId = FormatRuntimeId(fk),
                ResolvedType = meta?.TypeName,
                EditorId = meta?.EditorId,
                Name = meta?.Name,
                Detail = detail,
                DefinedIn = acc?.DefinedIn ?? (officialModKeys.Contains(fk.ModKey) ? (string?)fk.ModKey.FileName.String : null),
                OverriddenIn = acc?.OverriddenIn.OrderBy(x => x).ToList() ?? new(),
                ReferencedByPlugins = acc?.ReferencedByPlugins.OrderBy(x => x).ToList() ?? new(),
                ScriptGetFormPlugins = acc?.ScriptGetFormPlugins.OrderBy(x => x).ToList() ?? new(),
                PluginTouchCount = touched.Count,
                ReferenceSites = acc?.ReferenceSites.Take(20).ToList() ?? new(),
            };
        }

        foreach (var (lbl, mk, lid) in focusSpecs)
        {
            var fk = new FormKey(mk, lid);
            targetTouches.TryGetValue(fk, out var acc);
            report.SharedRecords.FocusForms.Add(BuildSharedEntry(fk, lbl, acc));
        }

        foreach (var kv in targetTouches.OrderBy(k => k.Key.ModKey.FileName.String).ThenBy(k => k.Key.ID))
        {
            var entry = BuildSharedEntry(kv.Key, null, kv.Value);
            if (entry.PluginTouchCount > 1)
                report.SharedRecords.Shared.Add(entry);
        }
        report.SharedRecords.AllSharedCount = report.SharedRecords.Shared.Count;

        // MapMarker inventory
        int coreMarkers = 0, mmOwn = 0, otherMarkers = 0;
        var seenMarkers = new HashSet<FormKey>();
        foreach (var (mk, isOvr, po) in mapMarkerRefs)
        {
            if (!isOvr)
            {
                if (mk.FileName.String.Equals("FO4TerrainCore.esm", StringComparison.OrdinalIgnoreCase)) coreMarkers++;
                else if (mk.FileName.String.Equals("FO4SFMapMarkers.esm", StringComparison.OrdinalIgnoreCase)) mmOwn++;
                else otherMarkers++;
            }
            // Prefer override record if any (e.g. FO4SFMapMarkers overrides 0A7759..0A775C)
            seenMarkers.Add(po.FormKey);
        }
        // Build detail per unique MapMarker FormKey (showing final winning entry + override note)
        var winningMarkerByFk = new Dictionary<FormKey, (ModKey Mod, bool IsOvr, IPlacedObjectGetter Ref)>();
        foreach (var item in mapMarkerRefs)
            winningMarkerByFk[item.Ref.FormKey] = item;

        foreach (var (_, _, po) in winningMarkerByFk.Values.OrderBy(x => FormatRuntimeId(x.Ref.FormKey)))
        {
            var fk = po.FormKey;
            questMarkerAssignments.TryGetValue(fk, out var qOwners);
            targetTouches.TryGetValue(fk, out var acc);
            var otherRefs = acc == null
                ? new List<string>()
                : acc.ScriptGetFormPlugins.Select(p => $"GetForm:{p}")
                    .Concat(acc.ReferenceSites.Where(s => !s.Contains("FO4SF_MapMarkers.Markers")))
                    .Distinct().ToList();
            report.SharedRecords.MapMarkerInventory.Markers.Add(new MapMarkerDetail
            {
                FormKey = fk.ToString(),
                RuntimeId = FormatRuntimeId(fk),
                Plugin = fk.ModKey.FileName.String,
                EditorId = po.EditorID,
                MarkerName = po.MapMarker?.Name?.String,
                Flags = po.MapMarker?.Flags.ToString(),
                Position = new[] { po.Position.X, po.Position.Y, po.Position.Z },
                QuestOwners = qOwners ?? new(),
                OtherScriptRefs = otherRefs,
            });
        }
        mapMarkersQuestCount = allOurQuests.Count(x => x.Mod.FileName.String.Equals("FO4SFMapMarkers.esm", StringComparison.OrdinalIgnoreCase));
        report.SharedRecords.MapMarkerInventory.Markers.Sort((a, b) => string.CompareOrdinal(a.RuntimeId, b.RuntimeId));
        report.SharedRecords.MapMarkerInventory.CoreMarkerCount = coreMarkers;
        report.SharedRecords.MapMarkerInventory.MapMarkersPluginOwnCount = mmOwn;
        report.SharedRecords.MapMarkerInventory.MapMarkersQuestCount = mapMarkersQuestCount;
        report.SharedRecords.MapMarkerInventory.TotalQuestArraySlots = totalQuestArraySlots;
        report.SharedRecords.MapMarkerInventory.OtherPluginMarkerCount = otherMarkers;
        report.SharedRecords.MapMarkerInventory.NonMapMarkersInQuestArrays.AddRange(nonMapMarkersInQuestArrays);

        // Section 4: Unprompted execution
        var startupFk = new FormKey(ModKey.FromFileName("Starfield.esm"), StartupQuestDoId);
        foreach (var ovr in report.Overrides.OfficialOverrides)
        {
            if (ovr.FormKey == startupFk.ToString())
                report.UnpromptedExecution.StartupQuestOverride = $"{ovr.Plugin}: {string.Join("; ", ovr.Changes)}";
        }
        foreach (var (mk, q) in allOurQuests)
        {
            bool sge = q.Data?.Flags.HasFlag(Quest.Flag.StartGameEnabled) == true;
            bool isStartupTarget = report.UnpromptedExecution.StartupQuestOverride?.Contains(q.FormKey.ToString(), StringComparison.OrdinalIgnoreCase) == true
                || (q.EditorID != null && report.UnpromptedExecution.StartupQuestOverride?.Contains(q.EditorID, StringComparison.OrdinalIgnoreCase) == true);
            if (!sge && !isStartupTarget) continue;

            var qScripts = q.VirtualMachineAdapter?.Scripts.Select(s => s.Name ?? "").Where(s => s != "").ToList() ?? new();
            var aScripts = q.VirtualMachineAdapter?.Aliases
                .SelectMany(a => a.Scripts.Select(s => $"{a.Property.Name}:{s.Name}"))
                .ToList() ?? new();

            report.UnpromptedExecution.StartGameEnabledQuests.Add(new StartQuestEntry
            {
                Plugin = mk.FileName.String,
                FormKey = q.FormKey.ToString(),
                RuntimeId = FormatRuntimeId(q.FormKey),
                EditorId = q.EditorID,
                Name = q.Name?.String,
                Flags = q.Data?.Flags.ToString() ?? "None",
                Scripts = qScripts,
                AliasScripts = aScripts,
                StageCount = q.Stages.Count,
            });
        }

        foreach (var psc in pscByScript.Values.Where(p => p.Hooks.Count > 0).OrderBy(p => p.ScriptName, StringComparer.OrdinalIgnoreCase))
        {
            scriptAttachments.TryGetValue(psc.ScriptName, out var att);
            var entry = new UnpromptedScriptEntry
            {
                ScriptName = psc.ScriptName,
                PscPath = psc.RelPath,
                AttachedTo = att ?? new(),
                Hooks = psc.Hooks,
            };
            if (att != null && att.Count > 0)
                report.UnpromptedExecution.AttachedUnpromptedScripts.Add(entry);
            else
                report.UnpromptedExecution.UnattachedRepoScriptsWithHooks.Add(entry);
        }

        // Section 6: Starfield leftovers
        int offLscrTotal = 0, offLscrUncond = 0;
        foreach (var mod in officialMods.Concat(ourMods))
        {
            var info = modInfoByKey[mod.ModKey];
            int total = 0, uncond = 0, cond = 0, ovrByOurs = 0;
            foreach (var ls in mod.LoadScreens)
            {
                total++;
                if (ls.Conditions.Count == 0) uncond++; else cond++;
                if (officialModKeys.Contains(mod.ModKey) && ourLscrTargets.Contains(ls.FormKey)) ovrByOurs++;
            }
            if (officialModKeys.Contains(mod.ModKey))
            {
                offLscrTotal += total;
                offLscrUncond += uncond;
            }
            if (total > 0 || officialModKeys.Contains(mod.ModKey))
            {
                report.StarfieldLeftovers.LscrByPlugin.Add(new LscrPluginCount
                {
                    Plugin = info.Name,
                    Category = info.Category,
                    Total = total,
                    Unconditional = uncond,
                    Conditioned = cond,
                    OverriddenByOurs = ovrByOurs,
                });
            }
        }
        report.StarfieldLeftovers.OfficialLscrTotal = offLscrTotal;
        report.StarfieldLeftovers.OfficialLscrUnconditional = offLscrUncond;

        foreach (var (mk, isOvr, loc) in ourLocations)
        {
            report.StarfieldLeftovers.Locations.Add(new NamedRecordInfo
            {
                Plugin = mk.FileName.String,
                FormKey = loc.FormKey.ToString(),
                RuntimeId = FormatRuntimeId(loc.FormKey),
                IsOverride = isOvr,
                EditorId = loc.EditorID,
                Name = loc.Name?.String,
                Detail = $"LCSR={loc.MasterSpecialReferences?.Count ?? 0}",
            });
        }
        foreach (var (mk, isOvr, w) in ourWorldspaces)
        {
            report.StarfieldLeftovers.Worldspaces.Add(new NamedRecordInfo
            {
                Plugin = mk.FileName.String,
                FormKey = w.FormKey.ToString(),
                RuntimeId = FormatRuntimeId(w.FormKey),
                IsOverride = isOvr,
                EditorId = w.EditorID,
                Name = w.Name?.String,
                Detail = $"Location={w.Location.FormKey} Flags={w.Flags}",
            });
        }
        foreach (var (mk, isOvr, p) in ourPlanets)
        {
            report.StarfieldLeftovers.Planets.Add(new NamedRecordInfo
            {
                Plugin = mk.FileName.String,
                FormKey = p.FormKey.ToString(),
                RuntimeId = FormatRuntimeId(p.FormKey),
                IsOverride = isOvr,
                EditorId = p.EditorID,
                Name = p.Name,
                Detail = $"SurfaceTree={p.SurfaceTree?.FormKey}",
            });
        }
        foreach (var (mk, isOvr, m) in ourMessages)
        {
            string? desc = m.Description?.String;
            if (desc != null && desc.Length > 140) desc = desc[..140] + "...";
            report.StarfieldLeftovers.Messages.Add(new MessageRecordInfo
            {
                Plugin = mk.FileName.String,
                FormKey = m.FormKey.ToString(),
                RuntimeId = FormatRuntimeId(m.FormKey),
                IsOverride = isOvr,
                EditorId = m.EditorID,
                Title = m.Name?.String,
                DescriptionPreview = desc,
                Buttons = m.MenuButtons.Select(b => b.Text?.String ?? "").ToList(),
            });
        }
        foreach (var (mk, isOvr, c) in ourNamedCells.Take(250))
        {
            report.StarfieldLeftovers.CellsNamed.Add(new NamedRecordInfo
            {
                Plugin = mk.FileName.String,
                FormKey = c.FormKey.ToString(),
                RuntimeId = FormatRuntimeId(c.FormKey),
                IsOverride = isOvr,
                EditorId = c.EditorID,
                Name = c.Name?.String,
                Detail = $"Location={c.Location.FormKey} Flags={c.Flags}",
            });
        }

        return report;
    }

    private static List<string> FindBadMasters(ModKey modKey, List<string> masters, Dictionary<ModKey, string> slotByMod)
    {
        var bad = new List<string>();
        int myOrder = OrderWeight(slotByMod.GetValueOrDefault(modKey));
        foreach (var m in masters)
        {
            if (!ModKey.TryFromFileName(m, out var mmk) || !slotByMod.TryGetValue(mmk, out var mSlot))
            {
                bad.Add($"{m}(missing)");
                continue;
            }
            if (mSlot == "UNLISTED_FULL")
            {
                bad.Add($"{m}(unlisted_full)");
                continue;
            }
            // Small/Medium official masters always load before Full plugin mods in Starfield
            if (myOrder >= 0 && OrderWeight(mSlot) >= 0 && OrderWeight(mSlot) > myOrder)
                bad.Add($"{m}(slot {mSlot} after {slotByMod[modKey]})");
        }
        return bad;
    }

    private static int OrderWeight(string? slot)
    {
        if (string.IsNullOrEmpty(slot) || slot.StartsWith("FD:") || slot.StartsWith("FE:") || slot == "UNLISTED_FULL")
            return -1;
        return int.TryParse(slot, NumberStyles.HexNumber, CultureInfo.InvariantCulture, out int v) ? v : -1;
    }

    private static string ClassifyFrame(IWorldspaceGetter? wrld, P3Float pos, string pluginName)
    {
        if (wrld == null) return "interior";
        bool inRaw = pos.X >= RawMinX && pos.X <= RawMaxX && pos.Y >= RawMinY && pos.Y <= RawMaxY;
        bool inMerged = pos.X >= MergedMinX && pos.X <= MergedMaxX && pos.Y >= MergedMinY && pos.Y <= MergedMaxY;
        // FO4TerrainCore & FO4SFMapMarkers persistent world refs are authored in local raw frame (-3200..3200),
        // while FO4SFMission & FO4SFPowerArmor overlay refs are placed at local + (-1200, -2700) merged coords.
        if (pluginName.Equals("FO4TerrainCore.esm", StringComparison.OrdinalIgnoreCase) ||
            pluginName.Equals("FO4SFMapMarkers.esm", StringComparison.OrdinalIgnoreCase))
        {
            return inRaw ? (inMerged ? "raw_authored(overlaps_merged_box)" : "raw_authored(outside_merged_box)") : "exterior_other";
        }
        if (inMerged)
            return inRaw ? "merged_authored(overlaps_raw_box)" : "merged_authored(outside_raw_box)";
        return inRaw ? "raw_authored(outside_merged_box)" : "exterior_other";
    }

    private static bool IsCompatiblePscType(string declaredPscType, string actualType, Dictionary<string, PscInfo> pscByScript)
    {
        string raw = declaredPscType.Trim().TrimEnd('[', ']');
        if (string.IsNullOrEmpty(raw)) return true;

        // Walk Papyrus script inheritance (e.g. FO4SF_Min00Quest extends Quest)
        string resolvedPsc = raw;
        var visited = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        while (pscByScript.TryGetValue(resolvedPsc, out var pInfo) && !string.IsNullOrWhiteSpace(pInfo.ExtendsType) && visited.Add(resolvedPsc))
        {
            resolvedPsc = pInfo.ExtendsType!;
        }

        string d = resolvedPsc.ToLowerInvariant();
        if (d is "form" or "var" or "scriptobject") return true;
        return d switch
        {
            "objectreference" => actualType.StartsWith("Placed", StringComparison.Ordinal),
            "actor" => actualType is "PlacedNpc",
            "actorbase" => actualType is "Npc" or "LeveledNpc",
            "quest" => actualType is "Quest",
            "message" => actualType is "Message",
            "globalvariable" => actualType.StartsWith("Global", StringComparison.Ordinal),
            "actorvalue" => actualType is "ActorValueInformation",
            "worldspace" => actualType is "Worldspace",
            "location" => actualType is "Location",
            "locationreftype" or "locreftype" => actualType is "LocationReferenceType",
            "cell" => actualType is "Cell",
            "faction" => actualType is "Faction",
            "race" => actualType is "Race",
            "armor" => actualType is "Armor",
            "armoraddon" => actualType is "ArmorAddon",
            "weapon" => actualType is "Weapon",
            "ammo" => actualType is "Ammunition" or "Ammo",
            "miscobject" => actualType is "MiscItem" or "MiscObject",
            "activator" => actualType is "Activator",
            "static" => actualType is "Static",
            "idle" => actualType is "IdleAnimation" or "Idle",
            "scene" => actualType is "Scene",
            "topicinfo" => actualType is "DialogResponses",
            "topic" => actualType is "DialogTopic",
            "package" => actualType is "Package",
            "keyword" => actualType is "Keyword",
            "spell" => actualType is "Spell",
            "perk" => actualType is "Perk",
            "weathersetting" => actualType is "WeatherSetting",
            "weather" => actualType is "Weather",
            "outfit" => actualType is "Outfit",
            "terminal" => actualType is "Terminal",
            "door" => actualType is "Door",
            "furniture" => actualType is "Furniture",
            "container" => actualType is "Container",
            "potion" => actualType is "Ingestible" or "Potion",
            "npc" => actualType is "Npc",
            "leveleditem" => actualType is "LeveledItem",
            "levelednpc" => actualType is "LeveledNpc",
            "formlist" => actualType is "FormList",
            "voicetype" => actualType is "VoiceType",
            "planet" => actualType is "Planet",
            "book" => actualType is "Book",
            "light" => actualType is "Light",
            "constructibleobject" => actualType is "ConstructibleObject",
            "imagespacemodifier" => actualType is "ImageSpaceAdapter" or "ImageSpaceModifier",
            "effectshader" => actualType is "EffectShader",
            "explosion" => actualType is "Explosion",
            "projectile" => actualType is "Projectile",
            _ => string.Equals(d, actualType, StringComparison.OrdinalIgnoreCase),
        };
    }

    private static List<string> DescribeOverrideDiff(
        IMajorRecordGetter rec,
        ILinkCache<IStarfieldMod, IStarfieldModGetter> officialCache,
        Dictionary<FormKey, IMajorRecordGetter> definingOurRecords)
    {
        var changes = new List<string>();
        if (!officialCache.TryResolve(rec.FormKey, rec.Registration.GetterType, out var orig))
            definingOurRecords.TryGetValue(rec.FormKey, out orig);

        if (rec is IDefaultObjectGetter dfob)
        {
            string after = dfob.Object.FormKey.ToString();
            string before = (orig as IDefaultObjectGetter)?.Object.FormKey.ToString() ?? "unknown";
            changes.Add($"DefaultObject.Object: {before} -> {after}");
        }
        else if (rec is IGlobalGetter glob)
        {
            float? after = glob.Data;
            float? before = (orig as IGlobalGetter)?.Data;
            changes.Add($"Global.Data: {before} -> {after}");
        }
        else if (rec is IGameSettingIntGetter gmstI)
        {
            changes.Add($"GameSettingInt.Data: {(orig as IGameSettingIntGetter)?.Data} -> {gmstI.Data}");
        }
        else if (rec is IGameSettingFloatGetter gmstF)
        {
            changes.Add($"GameSettingFloat.Data: {(orig as IGameSettingFloatGetter)?.Data} -> {gmstF.Data}");
        }
        else if (rec is IGameSettingStringGetter gmstS)
        {
            changes.Add($"GameSettingString.Data: '{(orig as IGameSettingStringGetter)?.Data}' -> '{gmstS.Data}'");
        }
        else if (rec is IGameSettingBoolGetter gmstB)
        {
            changes.Add($"GameSettingBool.Data: {(orig as IGameSettingBoolGetter)?.Data} -> {gmstB.Data}");
        }
        else if (rec is IQuestGetter q)
        {
            var oq = orig as IQuestGetter;
            changes.Add($"Flags: {oq?.Data?.Flags} -> {q.Data?.Flags}");
            if (q.VirtualMachineAdapter?.Scripts.Count > 0 || oq?.VirtualMachineAdapter?.Scripts.Count > 0)
                changes.Add($"VMAD scripts: {oq?.VirtualMachineAdapter?.Scripts.Count ?? 0} -> {q.VirtualMachineAdapter?.Scripts.Count ?? 0}");
            changes.Add($"Stages: {oq?.Stages.Count ?? 0} -> {q.Stages.Count}");
        }
        else if (rec is IWorldspaceGetter w)
        {
            var ow = orig as IWorldspaceGetter;
            changes.Add($"Flags: {ow?.Flags} -> {w.Flags}");
            changes.Add($"Location: {ow?.Location.FormKey} -> {w.Location.FormKey}");
            changes.Add($"SubCells blocks: {ow?.SubCells.Count ?? 0} -> {w.SubCells.Count}");
            if (w.TopCell != null)
                changes.Add($"TopCell persistent={w.TopCell.Persistent.Count}");
        }
        else if (rec is ILocationGetter loc)
        {
            var ol = orig as ILocationGetter;
            changes.Add($"Name: {ol?.Name?.String ?? "-"} -> {loc.Name?.String ?? "-"}");
            changes.Add($"LCSR count: {ol?.MasterSpecialReferences?.Count ?? 0} -> {loc.MasterSpecialReferences?.Count ?? 0}");
        }
        else if (rec is IPlacedObjectGetter po)
        {
            var op = orig as IPlacedObjectGetter;
            changes.Add($"Pos: ({op?.Position.X:F2},{op?.Position.Y:F2},{op?.Position.Z:F2}) -> ({po.Position.X:F2},{po.Position.Y:F2},{po.Position.Z:F2})");
            if (op != null && op.Base.FormKey != po.Base.FormKey)
                changes.Add($"Base: {op.Base.FormKey} -> {po.Base.FormKey}");
            if ((op != null ? (op.MajorRecordFlagsRaw & 0x0800) != 0 : false) != ((po.MajorRecordFlagsRaw & 0x0800) != 0))
                changes.Add($"InitiallyDisabled: {(op != null && (op.MajorRecordFlagsRaw & 0x0800) != 0)} -> {(po.MajorRecordFlagsRaw & 0x0800) != 0}");
            if (po.MapMarker != null || op?.MapMarker != null)
                changes.Add($"MapMarker Name='{op?.MapMarker?.Name?.String}'->'{po.MapMarker?.Name?.String}' Flags={op?.MapMarker?.Flags}->{po.MapMarker?.Flags}");
        }
        else if (rec is IPlacedNpcGetter pn)
        {
            var opn = orig as IPlacedNpcGetter;
            changes.Add($"Pos: ({opn?.Position.X:F2},{opn?.Position.Y:F2},{opn?.Position.Z:F2}) -> ({pn.Position.X:F2},{pn.Position.Y:F2},{pn.Position.Z:F2}); Base: {opn?.Base.FormKey} -> {pn.Base.FormKey}");
        }
        else if (rec is ICellGetter cell)
        {
            var oc = orig as ICellGetter;
            changes.Add($"Flags={oc?.Flags}->{cell.Flags}; Persistent={oc?.Persistent.Count ?? 0}->{cell.Persistent.Count}; Temporary={oc?.Temporary.Count ?? 0}->{cell.Temporary.Count}");
        }
        else if (rec is IPlanetGetter pndt)
        {
            var op = orig as IPlanetGetter;
            changes.Add($"Name='{op?.Name}'->'{pndt.Name}' SurfaceTree={op?.SurfaceTree?.FormKey}->{pndt.SurfaceTree?.FormKey}");
            AppendGenericPropertyDiffs(orig, rec, changes);
        }
        else if (rec is ILoadScreenGetter ls)
        {
            var ols = orig as ILoadScreenGetter;
            changes.Add($"Conditions: {ols?.Conditions.Count ?? 0} -> {ls.Conditions.Count}");
        }
        else if (rec is IFormListGetter flst)
        {
            var ofl = orig as IFormListGetter;
            changes.Add($"FormList.Items: {ofl?.Items.Count ?? 0} -> {flst.Items.Count}");
        }
        else
        {
            AppendGenericPropertyDiffs(orig, rec, changes);
            if (changes.Count == 0)
                changes.Add($"Record overridden ({rec.Registration.ClassType.Name}); flags=0x{rec.MajorRecordFlagsRaw:X}");
        }

        return changes;
    }

    private static void AppendGenericPropertyDiffs(IMajorRecordGetter? orig, IMajorRecordGetter rec, List<string> changes)
    {
        if (orig == null) return;
        var getterType = rec.Registration.GetterType;
        var props = getterType.GetProperties(System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.Instance)
            .Concat(getterType.GetInterfaces().SelectMany(i => i.GetProperties(System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.Instance)))
            .GroupBy(p => p.Name)
            .Select(g => g.First());

        foreach (var p in props)
        {
            if (p.GetIndexParameters().Length > 0) continue;
            if (p.Name is "FormKey" or "EditorID" or "Registration" or "FormVersion" or "Version2" or "IsCompressed" or "MajorRecordFlagsRaw")
                continue;
            try
            {
                string before = FormatPropVal(p.GetValue(orig), 0);
                string after = FormatPropVal(p.GetValue(rec), 0);
                if (before != after)
                    changes.Add($"{p.Name}: {before} -> {after}");
            }
            catch
            {
                // Ignore overlay binary parsing quirks on optional subrecords
            }
        }
    }

    private static string FormatPropVal(object? val, int depth)
    {
        if (val == null) return "null";
        if (val is string s) return $"'{s}'";
        if (val is bool or byte or sbyte or short or ushort or int or uint or long or ulong or float or double or Enum or FormKey)
            return Convert.ToString(val, CultureInfo.InvariantCulture) ?? "";
        if (val is IFormLinkGetter fl) return fl.FormKey.ToString();
        if (val is IModeledGetter mg) return $"Model('{mg.Model?.File}')";
        if (val is IModelGetter mdl) return $"Model('{mdl.File}')";
        if (val is System.Collections.ICollection col) return $"count={col.Count}";
        if (val is System.Collections.IEnumerable en && val is not IEnumerable<char>)
        {
            int c = 0;
            var samples = new List<string>();
            foreach (var item in en)
            {
                if (c < 4 && depth < 1) samples.Add(FormatPropVal(item, depth + 1));
                c++;
            }
            return c <= 4 && depth < 1 ? $"[{string.Join(", ", samples)}]" : $"count={c}";
        }
        if (depth < 1)
        {
            var subParts = new List<string>();
            foreach (var sp in val.GetType().GetProperties(System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.Instance).Take(8))
            {
                if (sp.GetIndexParameters().Length > 0 || sp.Name.Contains("Binary") || sp.Name is "Registration") continue;
                try
                {
                    subParts.Add($"{sp.Name}={FormatPropVal(sp.GetValue(val), depth + 1)}");
                }
                catch { }
            }
            if (subParts.Count > 0) return "{" + string.Join(", ", subParts) + "}";
        }
        return val.ToString() ?? val.GetType().Name;
    }

    private sealed class TargetTouchAccumulator
    {
        public FormKey Key { get; }
        public string? DefinedIn { get; set; }
        public HashSet<string> OverriddenIn { get; } = new(StringComparer.OrdinalIgnoreCase);
        public HashSet<string> ReferencedByPlugins { get; } = new(StringComparer.OrdinalIgnoreCase);
        public HashSet<string> ScriptGetFormPlugins { get; } = new(StringComparer.OrdinalIgnoreCase);
        public List<string> ReferenceSites { get; } = new();

        public TargetTouchAccumulator(FormKey key) => Key = key;
    }
}
