// Starfield LCTN records for the converted interiors (D1, needed by C4 leveling): one Location per FO4 location, shared by
// every converted cell of that location (Vault 81 is three cells of one LCTN); one per cell for a cell without a resolved
// FO4 location; all parented to a root FO4Port_InteriorsLocation whose own parent is SSol_PMars_Surface (01B736), the
// same parent the terrain overlay's LCTN has. Parenting to the overlay's LCTN would make FO4Port.esm master the core,
// which the build order forbids (docs/terrain/scripted-doors.md); the root makes re-pointing a one-record change.
//
// Source of the FO4 data, per cell: the cell export's "cell_data" / "location" / "encounter_zone" keys (Fo4Export
// schema 3) when the export has them; else the entry of <output dir>/locations.json (the pinned base cells were exported
// before the keys existed; Fo4Export's `locations` mode writes the sidecar: {"cells": {"<FO4 cell edid>": {...}}});
// else none. A location or zone the exporter could not resolve ({"formkey", "unresolved": true}) counts as absent.
//
// The FO4 encounter zone's leveling folds into Location.Owner (EncounterMinLevel / MaxLevel / EncounterFlags; FO4's four
// flag bits mean the same in Starfield, UseParentsLockedLevel is never set; levels clamp to Starfield's sbyte). Cells
// sharing a location with different zones: the first cell written wins, the rest are reported. No keywords: FO4's
// LocType keywords have no verified Starfield equivalent (the export keeps them for a later pass).
using System.Text.Json;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Starfield;

public sealed class Locations : IDisposable
{
    public const string RootEditorId = "FO4Port_InteriorsLocation";
    public static readonly FormKey RootParent = new(ModKey.FromNameAndExtension("Starfield.esm"), 0x01B736);   // SSol_PMars_Surface

    readonly StarfieldMod mod;
    readonly Func<string, FormKey> id;
    readonly StarfieldRelease release;
    readonly JsonDocument? sidecar;
    readonly Dictionary<string, Location> byKey = new();            // formids key -> record: Id() is called once per key
    readonly Dictionary<FormKey, (string cell, string zone)> leveledBy = new();   // location -> the cell whose zone it carries
    Location? root;

    public int Shared, PerCell, Leveled, FromSidecar, WithoutData;
    public readonly List<string> Warnings = new();

    public Locations(string sidecarPath, StarfieldMod mod, Func<string, FormKey> id, StarfieldRelease release)
    {
        this.mod = mod; this.id = id; this.release = release;
        if (!File.Exists(sidecarPath)) return;
        sidecar = JsonDocument.Parse(File.ReadAllText(sidecarPath));
        if (sidecar.RootElement.ValueKind != JsonValueKind.Object || !sidecar.RootElement.TryGetProperty("cells", out var cells)
            || cells.ValueKind != JsonValueKind.Object)
            throw new InvalidDataException($"{sidecarPath}: expected {{\"cells\": {{\"<FO4 cell editor id>\": {{...}}}}}}");
    }

    /// <summary>The Location of the converted cell `src4` (its FO4 editor id) from its export `cell`, created on first use.</summary>
    public Location For(JsonElement cell, string src4)
    {
        var data = Source(cell, src4);
        var fo4Loc = Resolved(data, "location");
        var zone = Resolved(data, "encounter_zone");
        string? cellName = data is JsonElement d && d.TryGetProperty("cell_data", out var cd) && cd.ValueKind == JsonValueKind.Object
                           ? Text(cd, "name") : null;
        string key, editorId;
        if (fo4Loc is JsonElement l)
        {
            // one Starfield LCTN per FO4 LCTN; an FO4 location without an editor id is keyed by its FormKey
            editorId = Text(l, "editor_id") is string e ? "FO4Port_" + e : "FO4Port_LCTN_" + l.GetProperty("formkey").GetString()!.Replace(':', '_');
            key = "LCTN:" + editorId;
        }
        else
        {
            editorId = $"FO4Port_{src4}Location";
            key = "LCTN:" + editorId;
        }
        if (!byKey.TryGetValue(key, out var loc))
        {
            loc = new Location(id(key), release)
            {
                EditorID = editorId,
                Name = (fo4Loc is JsonElement fl ? Text(fl, "name") : null) ?? cellName,
            };
            loc.ParentLocation.SetTo(Root().FormKey);
            mod.Locations.Add(loc);
            byKey[key] = loc;
            if (fo4Loc != null) Shared++; else PerCell++;
        }
        if (zone is JsonElement z) Level(loc, src4, z);
        return loc;
    }

    // the leveling of an FO4 encounter zone on a Location; a second, different zone on a shared Location is reported
    void Level(Location loc, string src4, JsonElement z)
    {
        var zoneKey = z.GetProperty("formkey").GetString()!;
        var min = z.GetProperty("min_level").GetInt32();
        var max = z.GetProperty("max_level").GetInt32();
        var flags = (LocationOwnerData.EncounterFlag)(z.GetProperty("flags").GetInt32() & 0xF);
        if (leveledBy.TryGetValue(loc.FormKey, out var first))
        {
            var o = loc.Owner!;
            if (first.zone != zoneKey && (o.EncounterMinLevel != Clamp(min) || o.EncounterMaxLevel != Clamp(max) || o.EncounterFlags != flags))
                Warnings.Add($"{loc.EditorID}: {src4} has encounter zone {zoneKey} ({min}-{max}, flags {(int)flags}); kept {first.cell}'s {first.zone}");
            return;
        }
        if (min > sbyte.MaxValue || max > sbyte.MaxValue) Warnings.Add($"{loc.EditorID}: {src4} encounter zone levels {min}-{max} clamped to 127");
        loc.Owner = new LocationOwnerData { EncounterMinLevel = Clamp(min), EncounterMaxLevel = Clamp(max), EncounterFlags = flags };
        leveledBy[loc.FormKey] = (src4, zoneKey);
        Leveled++;
    }

    static sbyte Clamp(int level) => (sbyte)Math.Clamp(level, 0, sbyte.MaxValue);

    Location Root()
    {
        if (root != null) return root;
        root = new Location(id("LCTN:" + RootEditorId), release) { EditorID = RootEditorId };
        root.ParentLocation.SetTo(RootParent);
        mod.Locations.Add(root);
        return root;
    }

    // the object holding the three keys for this cell: the export itself (schema 3), else its sidecar entry, else none
    JsonElement? Source(JsonElement cell, string src4)
    {
        if (cell.TryGetProperty("location", out _) || cell.TryGetProperty("encounter_zone", out _)) return cell;
        if (sidecar != null && sidecar.RootElement.GetProperty("cells").TryGetProperty(src4, out var entry) && entry.ValueKind == JsonValueKind.Object)
        {
            FromSidecar++;
            return entry;
        }
        WithoutData++;
        return null;
    }

    static JsonElement? Resolved(JsonElement? source, string key)
    {
        if (source is not JsonElement s || !s.TryGetProperty(key, out var v) || v.ValueKind != JsonValueKind.Object) return null;
        if (v.TryGetProperty("unresolved", out var u) && u.ValueKind == JsonValueKind.True) return null;
        return v;
    }

    static string? Text(JsonElement o, string key) => o.TryGetProperty(key, out var v) && v.ValueKind == JsonValueKind.String ? v.GetString() : null;

    public void Dispose() => sidecar?.Dispose();
}
