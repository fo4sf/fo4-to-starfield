// Converter interactive-fidelity pass (CF-5 part 1):
// Preserves Fallout 4 XESP (enable parent + opposite/pop-in flags + initial-disabled folding when an ancestor is
// unplaced), XLOC (locks on DOOR, CONT and TERM with KEYM remapping and pickable unmapped-key fallback), XLKR (linked
// references with generic KYWD creation and clean skipping of dangling targets), XAPR (activation-parent chains, delays
// and ParentActivateOnly via FO4SF_ActivateChain VMAD + XLKR), and XTEL (load-door teleports, including cross-cell
// endpoints resolved against --port-reference when re-converting a single cell).
using System.Drawing;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;

public sealed record InteractiveFidelityIssue(string Source, string Field, string? Target, string Reason);

public sealed class InteractiveFidelityReport
{
    public int CreatedMarkers { get; set; }
    public int CreatedDoors { get; set; }
    public int CreatedKeywords { get; set; }
    public int CreatedKeys { get; set; }
    public int PromotedPersistent { get; set; }

    public int XespWritten { get; set; }
    public int XespOppositeWritten { get; set; }
    public int XespPopInWritten { get; set; }
    public int XespFoldedInitialState { get; set; }
    public int XespUnplacedParentSkipped { get; set; }

    public int XlocWritten { get; set; }
    public int XlocKeyMapped { get; set; }
    public int XlocUnmappedKeyFallback { get; set; }
    public int XlocUnlockedZeroSkipped { get; set; }
    public int XlocUnsupportedLevelSkipped { get; set; }
    public int XlocUnopenableRequiresKeySkipped { get; set; }
    public int XlocNonLockableSkipped { get; set; }

    public int XlkrWritten { get; set; }
    public int XlkrDanglingSkipped { get; set; }
    public int XlkrUnmappedUnionSkipped { get; set; }
    public int XlkrMultirefLodSkipped { get; set; }

    public int XaprParentsWired { get; set; }
    public int XaprEdgesWired { get; set; }
    public int XaprChainXlkrWritten { get; set; }
    public int XaprDelaysPreserved { get; set; }
    public int XaprParentActivateOnlyApplied { get; set; }
    public int XaprParentNotPlaced { get; set; }
    public int XaprChildNotPlaced { get; set; }

    public int XtelLinked { get; set; }
    public int XtelCrossCellReferenceLinked { get; set; }
    public int NavmeshDoorTrianglesRemapped { get; set; }

    public List<InteractiveFidelityIssue> Issues { get; } = new();
}

public static class InteractiveFidelityPass
{
    public const float UnitsPerMetre = 70f;
    public const string ChainScriptName = "FO4SF_ActivateChain";
    public const string ChainKeywordIdentity = "KYWD:FO4SF_ActivateChainLink";
    public const string ChainKeywordEditorId = "FO4Port_ActivateChainLink";

    // Verified Starfield.esm control marker and automatic cave door FormIDs.
    public static readonly ModKey StarfieldEsm = ModKey.FromNameAndExtension("Starfield.esm");
    public static readonly FormKey EnableMarkerBase = new(StarfieldEsm, 0x010D8D);
    public static readonly FormKey XMarkerBase = new(StarfieldEsm, 0x00003B);
    public static readonly FormKey XMarkerHeadingBase = new(StarfieldEsm, 0x000034);
    public static readonly FormKey LightBoxBase = new(StarfieldEsm, 0x0001F7);
    public static readonly FormKey AutoloadDoorCaveBase = new(StarfieldEsm, 0x24F9CE);

    // Fallout4.esm MultirefLOD keyword (exterior LOD grouping only; never translated as an interactive XLKR).
    private const string MultirefLodNormalized = "195411:fallout4.esm";

    private static readonly IReadOnlyDictionary<string, FormKey> MarkerBases =
        new Dictionary<string, FormKey>(StringComparer.OrdinalIgnoreCase)
        {
            ["EnableMarker"] = EnableMarkerBase,
            ["XMarker"] = XMarkerBase,
            ["XMarkerHeading"] = XMarkerHeadingBase,
            ["LightBox"] = LightBoxBase,
        };

    private static readonly HashSet<int> PickableLockLevels = new() { 1, 25, 50, 75, 100 };
    private static readonly HashSet<int> RefusedLockLevels = new() { 251, 252, 253, 254 };

    public static string NormalizeSourceKey(string raw)
    {
        if (FormKey.TryFactory(raw, out var fk) && !fk.IsNull)
            return $"{fk.ID:X6}:{fk.ModKey.FileName.String.ToLowerInvariant()}";
        return raw.Trim().ToLowerInvariant();
    }

    public static void BuildManifestKeys(JsonElement manifestRoot, StarfieldMod mod, Func<string, FormKey> id,
        StarfieldRelease release, InteractiveFidelityReport report)
    {
        if (!manifestRoot.TryGetProperty("keys", out var keysProp) || keysProp.ValueKind != JsonValueKind.Array)
            return;
        foreach (var k in keysProp.EnumerateArray())
        {
            var src = k.GetProperty("src").GetString() ?? throw new InvalidDataException("manifest keys entry missing src");
            if (!FormKey.TryFactory(src, out var srcFk) || srcFk.IsNull)
                throw new InvalidDataException($"manifest keys entry has invalid FormKey: {src}");
            var edid = k.GetProperty("edid").GetString() ?? throw new InvalidDataException($"manifest key {src} missing edid");
            var model = k.TryGetProperty("model", out var mp) && mp.ValueKind == JsonValueKind.String ? mp.GetString() : null;
            var fk = id("KEYM:" + NormalizeSourceKey(src));
            var rec = new Key(fk, release) { EditorID = edid, Name = "Key" };
            if (!string.IsNullOrEmpty(model))
                rec.Model = new Model { File = model };
            mod.Keys.Add(rec);
            report.CreatedKeys++;
        }
    }

    public static (InteractiveFidelityReport Fidelity, TeleportReport Teleports) Apply(
        StarfieldMod mod,
        Dictionary<string, uint> ids,
        Func<string, FormKey> id,
        Dictionary<string, (PlacedObject obj, Cell cell)> placedBySource,
        IReadOnlyList<JsonElement> cellExports,
        IReadOnlySet<FormKey> ownRigDoors,
        IReadOnlyDictionary<FormKey, FormKey> xtelLoadBases,
        string? portReferencePath = null,
        StarfieldRelease release = StarfieldRelease.Starfield,
        string edidPrefix = "FO4Port")
    {
        var report = new InteractiveFidelityReport();

        // Build case-insensitive lookup over local placed references while keeping original keys intact.
        var localByNorm = new Dictionary<string, (string rawKey, PlacedObject obj, Cell cell)>(StringComparer.OrdinalIgnoreCase);
        foreach (var (rawKey, entry) in placedBySource)
            localByNorm[NormalizeSourceKey(rawKey)] = (rawKey, entry.obj, entry.cell);

        var cellsByName = mod.Cells.Records
            .SelectMany(b => b.SubBlocks)
            .SelectMany(s => s.Cells)
            .Where(c => c.EditorID != null)
            .ToDictionary(c => c.EditorID!, StringComparer.OrdinalIgnoreCase);

        var exportedNormInBuild = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var exp in cellExports)
        {
            foreach (var r in exp.GetProperty("refs").EnumerateArray())
                if (r.GetProperty("formkey").GetString() is string fk)
                    exportedNormInBuild.Add(NormalizeSourceKey(fk));
            if (exp.TryGetProperty("deferred_refs", out var defs) && defs.ValueKind == JsonValueKind.Array)
                foreach (var r in defs.EnumerateArray())
                    if (r.TryGetProperty("formkey", out var fkp) && fkp.GetString() is string fk)
                        exportedNormInBuild.Add(NormalizeSourceKey(fk));
        }

        // Optional cross-cell reference lookup from a baseline FO4Port.esm + sibling formids.json (read-only).
        var externalRefs = new Dictionary<string, (FormKey FormKey, bool IsDoor, bool IsPersistent)>(StringComparer.OrdinalIgnoreCase);
        var externalKeys = new Dictionary<string, FormKey>(StringComparer.OrdinalIgnoreCase);
        if (!string.IsNullOrWhiteSpace(portReferencePath))
        {
            if (!File.Exists(portReferencePath))
                throw new FileNotFoundException($"--port-reference file not found: {portReferencePath}");
            var refIdsPath = Path.Combine(Path.GetDirectoryName(Path.GetFullPath(portReferencePath))!, "formids.json");
            if (File.Exists(refIdsPath))
            {
                var refMap = StableFormIds.Load(refIdsPath);
                var masters = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
                masters.Set(new KeyedMasterStyle(StarfieldEsm, MasterStyle.Full));
                using var portRef = StarfieldMod.CreateFromBinaryOverlay(portReferencePath, release,
                    new BinaryReadParameters { MasterFlagsLookup = masters });
                var refDoors = portRef.Doors.Where(d => (d.MajorRecordFlagsRaw & 0x20) == 0).Select(d => d.FormKey).ToHashSet();
                refDoors.Add(AutoloadDoorCaveBase);
                var refKeys = portRef.Keys.Where(k => (k.MajorRecordFlagsRaw & 0x20) == 0).Select(k => k.FormKey).ToHashSet();
                var refPlaced = new Dictionary<uint, (IPlacedObjectGetter Obj, bool Persistent)>();
                foreach (var c in portRef.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells))
                {
                    foreach (var p in c.Persistent.OfType<IPlacedObjectGetter>())
                        if (p.FormKey.ModKey == portRef.ModKey)
                            refPlaced[p.FormKey.ID] = (p, (p.MajorRecordFlagsRaw & 0x400) != 0);
                    foreach (var t in c.Temporary.OfType<IPlacedObjectGetter>())
                        if (t.FormKey.ModKey == portRef.ModKey)
                            refPlaced.TryAdd(t.FormKey.ID, (t, false));
                }
                foreach (var (identity, localId) in refMap)
                {
                    if (identity.StartsWith("REFR:", StringComparison.Ordinal))
                    {
                        var secondColon = identity.IndexOf(':', 5);
                        if (secondColon < 0) continue;
                        var srcNorm = NormalizeSourceKey(identity.Substring(secondColon + 1));
                        if (exportedNormInBuild.Contains(srcNorm)) continue;
                        if (refPlaced.TryGetValue(localId, out var found) && (found.Obj.MajorRecordFlagsRaw & 0x20) == 0)
                        {
                            externalRefs[srcNorm] = (found.Obj.FormKey, refDoors.Contains(found.Obj.Base.FormKey), found.Persistent);
                        }
                    }
                    else if (identity.StartsWith("KEYM:", StringComparison.Ordinal))
                    {
                        var srcNorm = NormalizeSourceKey(identity.Substring(5));
                        var fk = new FormKey(portRef.ModKey, localId);
                        if (refKeys.Contains(fk))
                            externalKeys[srcNorm] = fk;
                    }
                }
            }
        }

        // Collect all referenced source keys so we recreate only control markers that actually participate in links/states.
        var needed = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var enableTree = new Dictionary<string, (bool RawDisabled, string? ParentNorm, uint Flags)>(StringComparer.OrdinalIgnoreCase);

        static void RecordEnableNode(Dictionary<string, (bool, string?, uint)> tree, JsonElement r)
        {
            if (!r.TryGetProperty("formkey", out var fkEl) || fkEl.GetString() is not string fk) return;
            var rawDis = r.TryGetProperty("disabled", out var dEl) && dEl.ValueKind == JsonValueKind.Number && dEl.GetInt32() != 0;
            string? pNorm = null;
            uint pFlags = 0;
            if (r.TryGetProperty("enable_parent", out var ep) && ep.ValueKind == JsonValueKind.Object)
            {
                if (ep.TryGetProperty("reference", out var pr) && pr.GetString() is string pStr)
                    pNorm = NormalizeSourceKey(pStr);
                if (ep.TryGetProperty("flags", out var pf) && pf.ValueKind == JsonValueKind.Number)
                    pFlags = pf.GetUInt32();
            }
            tree[NormalizeSourceKey(fk)] = (rawDis, pNorm, pFlags);
        }

        foreach (var exp in cellExports)
        {
            foreach (var r in exp.GetProperty("refs").EnumerateArray())
            {
                RecordEnableNode(enableTree, r);
                if (r.TryGetProperty("enable_parent", out var ep) && ep.ValueKind == JsonValueKind.Object &&
                    ep.TryGetProperty("reference", out var epr) && epr.GetString() is string epKey)
                    needed.Add(NormalizeSourceKey(epKey));
                if (r.TryGetProperty("linked_references", out var lr) && lr.ValueKind == JsonValueKind.Array)
                    foreach (var l in lr.EnumerateArray())
                    {
                        if (l.TryGetProperty("reference", out var tr) && tr.GetString() is string tKey)
                            needed.Add(NormalizeSourceKey(tKey));
                        if (l.TryGetProperty("keyword_or_reference", out var kr) && kr.GetString() is string uKey)
                            needed.Add(NormalizeSourceKey(uKey));
                    }
                if (r.TryGetProperty("activate_parents", out var ap) && ap.ValueKind == JsonValueKind.Object &&
                    ap.TryGetProperty("parents", out var pars) && pars.ValueKind == JsonValueKind.Array)
                    foreach (var p in pars.EnumerateArray())
                        if (p.TryGetProperty("reference", out var pr) && pr.GetString() is string pKey)
                            needed.Add(NormalizeSourceKey(pKey));
                if (r.TryGetProperty("teleport_destination", out var td) && td.ValueKind == JsonValueKind.Object &&
                    td.TryGetProperty("door", out var dr) && dr.GetString() is string dKey)
                    needed.Add(NormalizeSourceKey(dKey));
            }
            if (exp.TryGetProperty("deferred_refs", out var defs) && defs.ValueKind == JsonValueKind.Array)
                foreach (var r in defs.EnumerateArray())
                    RecordEnableNode(enableTree, r);
        }

        static P3Float Pos(JsonElement e) => new(e[0].GetSingle() / UnitsPerMetre, e[1].GetSingle() / UnitsPerMetre, e[2].GetSingle() / UnitsPerMetre);
        static P3Float Rot(JsonElement e) => new(e[0].GetSingle(), e[1].GetSingle(), e[2].GetSingle());

        void MakePersistent((PlacedObject obj, Cell cell) entry)
        {
            bool moved = entry.cell.Temporary.Remove(entry.obj);
            if (moved) entry.cell.Persistent.Add(entry.obj);
            if (moved || (entry.obj.MajorRecordFlagsRaw & 0x400) == 0)
                report.PromotedPersistent++;
            entry.obj.MajorRecordFlagsRaw |= 0x400;
        }

        // Index unplaced AutoloadDoor candidates first so mutual marker-door pairs can see each other.
        var autoloadCandidates = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var exp in cellExports)
            foreach (var r in exp.GetProperty("refs").EnumerateArray())
            {
                var src = r.GetProperty("formkey").GetString()!;
                var norm = NormalizeSourceKey(src);
                if (localByNorm.ContainsKey(norm)) continue;
                var type = r.TryGetProperty("type", out var tp) ? tp.GetString() : null;
                var baseEdid = r.TryGetProperty("base_editor_id", out var be) ? be.GetString() : null;
                if (type == "Door" && string.Equals(baseEdid, "AutoloadDoor", StringComparison.Ordinal) &&
                    r.TryGetProperty("teleport_destination", out var td) && td.ValueKind == JsonValueKind.Object)
                    autoloadCandidates.Add(norm);
            }

        // Step A: Recreate needed control markers and connected AutoloadDoor endpoints; honor exported persistence.
        foreach (var exp in cellExports)
        {
            var cellName = $"{edidPrefix}_" + exp.GetProperty("cell").GetString()!;
            if (!cellsByName.TryGetValue(cellName, out var cell)) continue;
            foreach (var r in exp.GetProperty("refs").EnumerateArray())
            {
                var src = r.GetProperty("formkey").GetString()!;
                var norm = NormalizeSourceKey(src);
                if (!localByNorm.TryGetValue(norm, out var existing))
                {
                    var type = r.TryGetProperty("type", out var tp) ? tp.GetString() : null;
                    var baseEdid = r.TryGetProperty("base_editor_id", out var be) ? be.GetString() ?? "" : "";
                    if (type == "Static" && needed.Contains(norm) && MarkerBases.TryGetValue(baseEdid, out var markerBase))
                    {
                        PlacedPrimitive? primitive = null;
                        if (baseEdid.Equals("LightBox", StringComparison.OrdinalIgnoreCase))
                        {
                            if (!r.TryGetProperty("primitive", out var vol) || vol.ValueKind != JsonValueKind.Object)
                            {
                                report.Issues.Add(new(src, "primitive", null, "LightBox missing primitive geometry"));
                                continue;
                            }
                            var pType = vol.GetProperty("type_value").GetInt32();
                            if (!Enum.IsDefined(typeof(PlacedPrimitive.TypeEnum), pType))
                            {
                                report.Issues.Add(new(src, "primitive.type", null, $"unsupported primitive type {pType}"));
                                continue;
                            }
                            var col = vol.GetProperty("color");
                            primitive = new PlacedPrimitive
                            {
                                Bounds = Pos(vol.GetProperty("bounds")),
                                Color = Color.FromArgb(col[3].GetInt32(), col[0].GetInt32(), col[1].GetInt32(), col[2].GetInt32()),
                                Unknown = vol.GetProperty("unknown").GetSingle(),
                                Type = (PlacedPrimitive.TypeEnum)pType,
                            };
                        }
                        var marker = new PlacedObject(id($"REFR:{cellName}:{src}"), release)
                        {
                            Base = new FormLinkNullable<IPlaceableObjectGetter>(markerBase),
                            Position = Pos(r.GetProperty("pos")),
                            Rotation = Rot(r.GetProperty("rot")),
                            Primitive = primitive,
                        };
                        if (r.TryGetProperty("scale", out var sc) && Math.Abs(sc.GetSingle() - 1f) > 1e-4f)
                            marker.Scale = sc.GetSingle();
                        if (r.TryGetProperty("disabled", out var dis) && dis.GetInt32() != 0)
                            marker.MajorRecordFlagsRaw |= 0x800;
                        marker.MajorRecordFlagsRaw |= 0x400;
                        cell.Persistent.Add(marker);
                        placedBySource[src] = (marker, cell);
                        localByNorm[norm] = (src, marker, cell);
                        report.CreatedMarkers++;
                        continue;
                    }
                    if (autoloadCandidates.Contains(norm) &&
                        r.TryGetProperty("teleport_destination", out var td) && td.ValueKind == JsonValueKind.Object &&
                        td.TryGetProperty("door", out var dr) && dr.GetString() is string destRaw)
                    {
                        var destNorm = NormalizeSourceKey(destRaw);
                        bool destAvailable = localByNorm.ContainsKey(destNorm) || autoloadCandidates.Contains(destNorm) ||
                            (externalRefs.TryGetValue(destNorm, out var extD) && extD.IsDoor && extD.IsPersistent);
                        if (destAvailable)
                        {
                            var doorObj = new PlacedObject(id($"REFR:{cellName}:{src}"), release)
                            {
                                Base = new FormLinkNullable<IPlaceableObjectGetter>(AutoloadDoorCaveBase),
                                Position = Pos(r.GetProperty("pos")),
                                Rotation = Rot(r.GetProperty("rot")),
                            };
                            if (r.TryGetProperty("scale", out var sc) && Math.Abs(sc.GetSingle() - 1f) > 1e-4f)
                                doorObj.Scale = sc.GetSingle();
                            if (r.TryGetProperty("disabled", out var dis) && dis.GetInt32() != 0)
                                doorObj.MajorRecordFlagsRaw |= 0x800;
                            doorObj.MajorRecordFlagsRaw |= 0x400;
                            cell.Persistent.Add(doorObj);
                            placedBySource[src] = (doorObj, cell);
                            localByNorm[norm] = (src, doorObj, cell);
                            report.CreatedDoors++;
                            continue;
                        }
                    }
                    continue;
                }
                if (r.TryGetProperty("persistent", out var persEl) && persEl.ValueKind == JsonValueKind.True)
                    MakePersistent((existing.obj, existing.cell));
            }
        }

        // Helper for recursive effective initial-disabled resolution when an XESP parent is unplaced.
        bool EffectiveDisabled(string normKey, HashSet<string> visiting)
        {
            if (!enableTree.TryGetValue(normKey, out var node))
                return false;
            if (node.ParentNorm == null || !visiting.Add(normKey))
                return node.RawDisabled;
            bool opp = (node.Flags & 1u) != 0;
            bool parentDis = enableTree.ContainsKey(node.ParentNorm) ? EffectiveDisabled(node.ParentNorm, visiting) : false;
            visiting.Remove(normKey);
            return parentDis ^ opp;
        }

        // Validate and collect KEYM mappings from ids + mod.Keys + externalKeys.
        var keyMap = new Dictionary<string, FormKey>(externalKeys, StringComparer.OrdinalIgnoreCase);
        var activeModKeys = mod.Keys.Where(k => (k.MajorRecordFlagsRaw & 0x20) == 0).ToDictionary(k => k.FormKey.ID, k => k.FormKey);
        foreach (var (identity, kid) in ids)
        {
            if (!identity.StartsWith("KEYM:", StringComparison.Ordinal)) continue;
            var rawKey = identity.Substring(5);
            if (!FormKey.TryFactory(rawKey, out var fk) || fk.IsNull)
                throw new InvalidOperationException($"invalid KEYM identity in formids.json: {identity}");
            var normKey = NormalizeSourceKey(rawKey);
            if (activeModKeys.TryGetValue(kid, out var targetKeyFk))
            {
                if (keyMap.TryGetValue(normKey, out var prior) && prior != targetKeyFk && prior.ModKey == mod.ModKey)
                    throw new InvalidOperationException($"conflicting KEYM targets for {normKey}: {prior} vs {targetKeyFk}");
                keyMap[normKey] = targetKeyFk;
            }
        }

        // Lockable base set: DOOR, CONT, TERM.
        var lockableBases = new HashSet<FormKey>(
            mod.Doors.Where(d => (d.MajorRecordFlagsRaw & 0x20) == 0).Select(d => d.FormKey)
                .Concat(mod.Containers.Where(c => (c.MajorRecordFlagsRaw & 0x20) == 0).Select(c => c.FormKey))
                .Concat(mod.Terminals.Where(t => (t.MajorRecordFlagsRaw & 0x20) == 0).Select(t => t.FormKey)))
        {
            AutoloadDoorCaveBase
        };
        if (Environment.GetEnvironmentVariable("FO4PORT_DOOR_BASE") is string vb && uint.TryParse(vb, System.Globalization.NumberStyles.HexNumber, null, out var vbId))
            lockableBases.Add(new FormKey(StarfieldEsm, vbId));

        // Index exported generic keywords for XLKR translation (zero Name/Notes game text copied).
        var keywordDefs = new Dictionary<string, (string? EditorId, int[]? Color, bool HasNoneType, bool Generic)>(StringComparer.OrdinalIgnoreCase);
        foreach (var exp in cellExports)
        {
            if (!exp.TryGetProperty("referenced_keywords", out var kws) || kws.ValueKind != JsonValueKind.Array) continue;
            foreach (var kw in kws.EnumerateArray())
            {
                var kRaw = kw.GetProperty("formkey").GetString()!;
                var kNorm = NormalizeSourceKey(kRaw);
                if (keywordDefs.ContainsKey(kNorm)) continue;
                var edid = kw.TryGetProperty("editor_id", out var ep) ? ep.GetString() : null;
                var typeStr = kw.TryGetProperty("type", out var tp) && tp.ValueKind == JsonValueKind.String ? tp.GetString() : null;
                int? typeVal = kw.TryGetProperty("type_value", out var tv) && tv.ValueKind == JsonValueKind.Number ? tv.GetInt32() : null;
                var flags = kw.TryGetProperty("record_flags", out var rf) && rf.ValueKind == JsonValueKind.Number ? rf.GetInt32() : 0;
                var attr = kw.TryGetProperty("attraction_rule", out var ar) && ar.ValueKind == JsonValueKind.String ? ar.GetString() : null;
                int[]? col = kw.TryGetProperty("color", out var ce) && ce.ValueKind == JsonValueKind.Array
                    ? ce.EnumerateArray().Select(x => x.GetInt32()).ToArray() : null;
                bool generic = (typeStr == null ? typeVal == null : typeStr == "None" && typeVal == 0) &&
                               flags == 0 && attr == null &&
                               (col == null || (col.Length == 3 && col.All(v => v >= 0 && v <= 255)));
                keywordDefs[kNorm] = (edid, col, typeStr != null, generic);
            }
        }
        var createdKeywords = new Dictionary<string, FormKey>(StringComparer.OrdinalIgnoreCase);
        FormKey? ResolveOrCreateKeyword(string rawKey)
        {
            var norm = NormalizeSourceKey(rawKey);
            if (createdKeywords.TryGetValue(norm, out var existing)) return existing;
            if (!keywordDefs.TryGetValue(norm, out var def) || !def.Generic) return null;
            var fk = id("KYWD:" + norm);
            var existingRec = mod.Keywords.FirstOrDefault(k => k.FormKey == fk);
            if (existingRec == null)
            {
                var stem = Regex.Replace(def.EditorId ?? "LinkedKeyword", "[^A-Za-z0-9_]", "_");
                var salt = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(norm)))[..16];
                var kw = new Keyword(fk, release)
                {
                    EditorID = $"{edidPrefix}_{stem}_{salt}",
                    Type = def.HasNoneType ? Keyword.TypeEnum.None : null,
                    Color = def.Color == null ? null : Color.FromArgb(def.Color[0], def.Color[1], def.Color[2]),
                };
                mod.Keywords.Add(kw);
                report.CreatedKeywords++;
            }
            createdKeywords[norm] = fk;
            return fk;
        }

        bool TryResolveTargetRef(string rawKey, out FormKey resolvedKey, out (PlacedObject obj, Cell cell)? localEntry)
        {
            var norm = NormalizeSourceKey(rawKey);
            if (localByNorm.TryGetValue(norm, out var loc))
            {
                resolvedKey = loc.obj.FormKey;
                localEntry = (loc.obj, loc.cell);
                return true;
            }
            if (externalRefs.TryGetValue(norm, out var ext))
            {
                resolvedKey = ext.FormKey;
                localEntry = null;
                return true;
            }
            resolvedKey = FormKey.Null;
            localEntry = null;
            return false;
        }

        // Steps C, D, E: Apply XESP, XLOC, and XLKR per placed reference; collect XAPR edges for Step F.
        var xaprByParent = new Dictionary<string, List<(string ChildNorm, PlacedObject ChildObj, float Delay, bool ChildParentOnly)>>(StringComparer.OrdinalIgnoreCase);
        var xaprBlockedChildren = new Dictionary<string, PlacedObject>(StringComparer.OrdinalIgnoreCase);

        foreach (var exp in cellExports)
        {
            foreach (var r in exp.GetProperty("refs").EnumerateArray())
            {
                var src = r.GetProperty("formkey").GetString()!;
                var norm = NormalizeSourceKey(src);
                bool childPlaced = localByNorm.TryGetValue(norm, out var targetEntry);

                // Collect XAPR edges even when child is unplaced so reporting is exact.
                if (r.TryGetProperty("activate_parents", out var ap) && ap.ValueKind == JsonValueKind.Object)
                {
                    bool parentOnly = ap.TryGetProperty("flags", out var apf) && (apf.GetUInt32() & 1u) != 0;
                    if (!childPlaced)
                    {
                        report.XaprChildNotPlaced++;
                    }
                    else if (ap.TryGetProperty("parents", out var pars) && pars.ValueKind == JsonValueKind.Array)
                    {
                        int wiredForThisChild = 0;
                        foreach (var p in pars.EnumerateArray())
                        {
                            var pRaw = p.TryGetProperty("reference", out var pr) ? pr.GetString() : null;
                            var delay = p.TryGetProperty("delay", out var dl) && dl.ValueKind == JsonValueKind.Number ? dl.GetSingle() : 0f;
                            if (!float.IsFinite(delay) || delay < 0f)
                            {
                                report.Issues.Add(new(src, "activate_parents.delay", pRaw, $"invalid delay {delay}"));
                                continue;
                            }
                            if (pRaw == null || !localByNorm.TryGetValue(NormalizeSourceKey(pRaw), out var pLoc))
                            {
                                report.XaprParentNotPlaced++;
                                continue;
                            }
                            var pNorm = NormalizeSourceKey(pRaw);
                            if (pLoc.obj.FormKey == targetEntry.obj.FormKey) continue;
                            if (!xaprByParent.TryGetValue(pNorm, out var list))
                                xaprByParent[pNorm] = list = new();
                            if (!list.Any(x => x.ChildObj.FormKey == targetEntry.obj.FormKey))
                            {
                                list.Add((norm, targetEntry.obj, delay, parentOnly));
                                wiredForThisChild++;
                            }
                        }
                        if (parentOnly && wiredForThisChild > 0)
                            xaprBlockedChildren[norm] = targetEntry.obj;
                    }
                }

                if (!childPlaced) continue;
                var target = targetEntry.obj;

                // C. XESP (EnableParent)
                if (r.TryGetProperty("enable_parent", out var ep) && ep.ValueKind == JsonValueKind.Object)
                {
                    var epRef = ep.TryGetProperty("reference", out var epr) ? epr.GetString() : null;
                    var epFlags = ep.TryGetProperty("flags", out var epf) ? epf.GetUInt32() : 0u;
                    if ((epFlags & ~3u) != 0)
                    {
                        report.Issues.Add(new(src, "enable_parent.flags", epRef, $"unsupported XESP flag bits 0x{epFlags:X}"));
                    }
                    else if (epRef != null && TryResolveTargetRef(epRef, out var parentFk, out var parentLocal) && parentFk != target.FormKey)
                    {
                        if (parentLocal is { } pl)
                            MakePersistent(pl);
                        target.EnableParent = new EnableParent { Flags = (EnableParent.Flag)epFlags };
                        target.EnableParent.Reference.SetTo(parentFk);
                        report.XespWritten++;
                        if ((epFlags & 1u) != 0) report.XespOppositeWritten++;
                        if ((epFlags & 2u) != 0) report.XespPopInWritten++;
                    }
                    else
                    {
                        report.XespUnplacedParentSkipped++;
                        bool effectiveDis = EffectiveDisabled(norm, new HashSet<string>(StringComparer.OrdinalIgnoreCase));
                        bool currentlyDis = (target.MajorRecordFlagsRaw & 0x800) != 0;
                        if (effectiveDis != currentlyDis)
                        {
                            if (effectiveDis) target.MajorRecordFlagsRaw |= 0x800;
                            else target.MajorRecordFlagsRaw &= ~0x800;
                            report.XespFoldedInitialState++;
                        }
                    }
                }

                // D. XLOC (LockData on DOOR / CONT / TERM)
                if (r.TryGetProperty("lock_data", out var lk) && lk.ValueKind == JsonValueKind.Object)
                {
                    int level = lk.GetProperty("level").GetInt32();
                    uint lFlags = lk.TryGetProperty("flags", out var lf) ? lf.GetUInt32() : 0u;
                    string? srcKey = lk.TryGetProperty("key", out var ke) && ke.ValueKind == JsonValueKind.String ? ke.GetString() : null;

                    if (level == 0 && srcKey == null && lFlags == 0)
                    {
                        report.XlocUnlockedZeroSkipped++;
                    }
                    else if (!lockableBases.Contains(target.Base.FormKey))
                    {
                        report.XlocNonLockableSkipped++;
                    }
                    else if (RefusedLockLevels.Contains(level))
                    {
                        report.XlocUnsupportedLevelSkipped++;
                    }
                    else if ((lFlags & ~1u) != 0)
                    {
                        report.Issues.Add(new(src, "lock_data.flags", null, $"unsupported XLOC flag bits 0x{lFlags:X}"));
                    }
                    else if (!PickableLockLevels.Contains(level) && level != 255)
                    {
                        report.Issues.Add(new(src, "lock_data.level", level.ToString(), $"unsupported XLOC level {level}"));
                    }
                    else
                    {
                        FormKey mappedKey = FormKey.Null;
                        bool hasMappedKey = srcKey != null && keyMap.TryGetValue(NormalizeSourceKey(srcKey), out mappedKey);
                        if (level == 255 && !hasMappedKey)
                        {
                            report.XlocUnopenableRequiresKeySkipped++;
                        }
                        else
                        {
                            target.Lock = new LockData
                            {
                                Level = (LockLevel)level,
                                Flags = (LockData.Flag)lFlags,
                            };
                            if (hasMappedKey)
                            {
                                target.Lock.Key.SetTo(mappedKey);
                                report.XlocKeyMapped++;
                            }
                            else if (srcKey != null)
                            {
                                report.XlocUnmappedKeyFallback++;
                            }
                            report.XlocWritten++;
                        }
                    }
                }

                // E. XLKR (LinkedReferences)
                if (r.TryGetProperty("linked_references", out var lrs) && lrs.ValueKind == JsonValueKind.Array)
                {
                    foreach (var link in lrs.EnumerateArray())
                    {
                        var discRaw = link.TryGetProperty("keyword_or_reference", out var dp) && dp.ValueKind == JsonValueKind.String ? dp.GetString() : null;
                        if (discRaw != null && NormalizeSourceKey(discRaw) == MultirefLodNormalized)
                        {
                            report.XlkrMultirefLodSkipped++;
                            continue;
                        }
                        var refRaw = link.TryGetProperty("reference", out var rp) && rp.ValueKind == JsonValueKind.String ? rp.GetString() : null;
                        if (refRaw == null || !TryResolveTargetRef(refRaw, out var targetRefFk, out var targetRefLocal))
                        {
                            report.XlkrDanglingSkipped++;
                            continue;
                        }
                        if (targetRefLocal is { } trl)
                            MakePersistent(trl);

                        FormKey? unionFk = null;
                        if (discRaw != null)
                        {
                            if (TryResolveTargetRef(discRaw, out var discRefFk, out var discRefLocal))
                            {
                                if (discRefLocal is { } drl) MakePersistent(drl);
                                unionFk = discRefFk;
                            }
                            else if (ResolveOrCreateKeyword(discRaw) is { } kwFk)
                            {
                                unionFk = kwFk;
                            }
                            else
                            {
                                report.XlkrUnmappedUnionSkipped++;
                                continue;
                            }
                        }

                        var desiredUnion = unionFk ?? FormKey.Null;
                        if (!target.LinkedReferences.Any(x => x.Reference.FormKey == targetRefFk && x.KeywordOrReference.FormKey == desiredUnion))
                        {
                            var entry = new LinkedReferences();
                            entry.Reference.SetTo(targetRefFk);
                            if (unionFk is { } ufk) entry.KeywordOrReference.SetTo(ufk);
                            target.LinkedReferences.Add(entry);
                            report.XlkrWritten++;
                        }
                    }
                }
            }
        }

        // Step F: Wire XAPR chains (FO4SF_ActivateChain VMAD + KYWD:FO4SF_ActivateChainLink XLKR).
        static ScriptEntry GetOrAddChainScript(PlacedObject obj)
        {
            obj.VirtualMachineAdapter ??= new VirtualMachineAdapter { Version = 6, ObjectFormat = 2 };
            obj.VirtualMachineAdapter.Scripts.RemoveAll(s =>
                string.Equals(s.Name, ActivationChains.Script, StringComparison.OrdinalIgnoreCase));
            var existing = obj.VirtualMachineAdapter.Scripts.FirstOrDefault(s =>
                string.Equals(s.Name, ChainScriptName, StringComparison.OrdinalIgnoreCase));
            if (existing != null) return existing;
            var entry = new ScriptEntry { Name = ChainScriptName, Flags = ScriptEntry.Flag.Local };
            obj.VirtualMachineAdapter.Scripts.Add(entry);
            return entry;
        }

        static void SetBoolProp(ScriptEntry script, string name, bool val)
        {
            script.Properties.RemoveAll(p => string.Equals(p.Name, name, StringComparison.OrdinalIgnoreCase));
            script.Properties.Add(new ScriptBoolProperty { Name = name, Flags = ScriptProperty.Flag.Edited, Data = val });
        }

        foreach (var (pNorm, edges) in xaprByParent.OrderBy(kv => kv.Key, StringComparer.Ordinal))
        {
            var parentEntry = localByNorm[pNorm];
            MakePersistent((parentEntry.obj, parentEntry.cell));
            var script = GetOrAddChainScript(parentEntry.obj);
            script.Properties.RemoveAll(p =>
                string.Equals(p.Name, "Targets", StringComparison.OrdinalIgnoreCase) ||
                string.Equals(p.Name, "Delays", StringComparison.OrdinalIgnoreCase) ||
                string.Equals(p.Name, "UnblockTargets", StringComparison.OrdinalIgnoreCase));

            var targetsProp = new ScriptObjectListProperty { Name = "Targets", Flags = ScriptProperty.Flag.Edited };
            var delaysProp = new ScriptFloatListProperty { Name = "Delays", Flags = ScriptProperty.Flag.Edited };
            var unblockProp = new ScriptBoolListProperty { Name = "UnblockTargets", Flags = ScriptProperty.Flag.Edited };

            foreach (var edge in edges)
            {
                if (localByNorm.TryGetValue(edge.ChildNorm, out var childLoc))
                    MakePersistent((childLoc.obj, childLoc.cell));
                targetsProp.Objects.Add(new ScriptObjectProperty
                {
                    Name = "", Flags = ScriptProperty.Flag.Edited,
                    Object = new FormLink<IStarfieldMajorRecordGetter>(edge.ChildObj.FormKey),
                    Alias = -1, Unused = 0,
                });
                delaysProp.Data.Add(edge.Delay);
                unblockProp.Data.Add(edge.ChildParentOnly);
                if (edge.Delay > 1e-6f) report.XaprDelaysPreserved++;
            }

            script.Properties.Add(targetsProp);
            script.Properties.Add(delaysProp);
            script.Properties.Add(unblockProp);
            report.XaprParentsWired++;
            report.XaprEdgesWired += edges.Count;
        }

        foreach (var (_, childObj) in xaprBlockedChildren.OrderBy(kv => kv.Key, StringComparer.Ordinal))
        {
            var script = GetOrAddChainScript(childObj);
            SetBoolProp(script, "ParentActivateOnly", true);
            report.XaprParentActivateOnlyApplied++;
        }

        // Step G: XTEL (intra-build via TeleportLinks + AutoloadDoor_Cave + cross-cell --port-reference resolution).
        var doorSet = mod.Doors.Where(d => (d.MajorRecordFlagsRaw & 0x20) == 0).Select(d => d.FormKey).ToHashSet();
        doorSet.Add(AutoloadDoorCaveBase);
        var teleports = TeleportLinks.Apply(mod, placedBySource, cellExports, ownRigDoors, xtelLoadBases);

        // Handle any AutoloadDoorCaveBase sources/targets or cross-cell --port-reference destinations that TeleportLinks skipped.
        foreach (var exp in cellExports)
        {
            var cellLabel = exp.TryGetProperty("cell", out var cn) ? cn.GetString() ?? "" : "";
            foreach (var r in exp.GetProperty("refs").EnumerateArray())
            {
                if (!r.TryGetProperty("teleport_destination", out var tel) || tel.ValueKind != JsonValueKind.Object) continue;
                var src = r.GetProperty("formkey").GetString()!;
                if (!localByNorm.TryGetValue(NormalizeSourceKey(src), out var from) || from.obj.TeleportDestination != null)
                    continue;
                if (!doorSet.Contains(from.obj.Base.FormKey) || ownRigDoors.Contains(from.obj.Base.FormKey))
                    continue;
                var doorRaw = tel.TryGetProperty("door", out var dp) ? dp.GetString() : null;
                if (doorRaw == null) continue;
                var flags = tel.GetProperty("flags").GetUInt32();
                if ((flags & ~7u) != 0 || (flags & 4u) != 0) continue;

                FormKey destFk = FormKey.Null;
                bool crossCellRef = false;
                var destNorm = NormalizeSourceKey(doorRaw);
                if (localByNorm.TryGetValue(destNorm, out var localDest) && doorSet.Contains(localDest.obj.Base.FormKey))
                {
                    destFk = localDest.obj.FormKey;
                    MakePersistent((localDest.obj, localDest.cell));
                    teleports.Issues.RemoveAll(i => i.Source == src && i.Target == doorRaw);
                }
                else if (externalRefs.TryGetValue(destNorm, out var extDest) && extDest.IsDoor && extDest.IsPersistent)
                {
                    destFk = extDest.FormKey;
                    crossCellRef = true;
                    if (teleports.Unlinked.Remove($"{cellLabel} {src} -> {doorRaw}"))
                        teleports.DestinationNotInBuild = Math.Max(0, teleports.DestinationNotInBuild - 1);
                }

                if (!destFk.IsNull)
                {
                    var pos = tel.GetProperty("pos");
                    var rot = tel.GetProperty("rot");
                    from.obj.TeleportDestination = new TeleportDestination
                    {
                        Position = new P3Float(pos[0].GetSingle() / UnitsPerMetre, pos[1].GetSingle() / UnitsPerMetre, pos[2].GetSingle() / UnitsPerMetre),
                        Rotation = new P3Float(rot[0].GetSingle(), rot[1].GetSingle(), rot[2].GetSingle()),
                        Flags = (TeleportDestination.Flag)flags,
                    };
                    from.obj.TeleportDestination.Door.SetTo(destFk);
                    if (xtelLoadBases.TryGetValue(from.obj.Base.FormKey, out var loadBase))
                    {
                        from.obj.Base.SetTo(loadBase);
                        teleports.LoadGraph++;
                    }
                    MakePersistent((from.obj, from.cell));
                    teleports.Linked++;
                    if (crossCellRef)
                    {
                        teleports.OneWay++;
                        report.XtelCrossCellReferenceLinked++;
                    }
                }
            }
        }

        // Recount mutual vs one-way if any AutoloadDoorCaveBase local pairs were added above.
        var allLinked = placedBySource.Values
            .Where(x => x.obj.TeleportDestination != null && !x.obj.TeleportDestination.Door.IsNull)
            .ToDictionary(x => x.obj.FormKey, x => x.obj.TeleportDestination!.Door.FormKey);
        int pairs = 0, oneWay = 0;
        foreach (var (a, b) in allLinked)
        {
            if (allLinked.TryGetValue(b, out var back) && back == a)
            {
                if (a.ID < b.ID) pairs++;
            }
            else oneWay++;
        }
        teleports.Pairs = pairs;
        teleports.OneWay = oneWay;
        teleports.Linked = allLinked.Count;
        report.XtelLinked = allLinked.Count;

        // Verify/count any NavmeshGeometry.DoorTriangles on cells in mod.
        foreach (var c in mod.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells))
            foreach (var nm in c.NavigationMeshes)
                if (nm.NavmeshGeometry?.DoorTriangles is { } dts)
                    foreach (var dt in dts)
                        if (!dt.Door.IsNull)
                            report.NavmeshDoorTrianglesRemapped++;

        return (report, teleports);
    }
}
