using System.Collections;

/// <summary>Papyrus scripts attached to a record (VMAD), read by reflection so the dump follows whatever Mutagen
/// exposes: each script's name and flags, each property's name, kind and value. Doors use them for locks, elevators and
/// quest-driven opening (docs/spikes/door-behaviour.md); the converter does not consume them yet.</summary>
public static class ScriptExport
{
    public static object? Scripts(object record)
    {
        var vmad = record.GetType().GetProperty("VirtualMachineAdapter")?.GetValue(record);
        if (vmad?.GetType().GetProperty("Scripts")?.GetValue(vmad) is not IEnumerable scripts) return null;
        var output = new List<object>();
        foreach (var script in scripts)
        {
            var t = script.GetType();
            var properties = new List<object>();
            if (t.GetProperty("Properties")?.GetValue(script) is IEnumerable props)
                foreach (var p in props)
                    properties.Add(new
                    {
                        name = p.GetType().GetProperty("Name")?.GetValue(p)?.ToString(),
                        kind = p.GetType().Name.Replace("BinaryOverlay", ""),
                        value = Value(p),
                    });
            output.Add(new { name = t.GetProperty("Name")?.GetValue(script)?.ToString(),
                             flags = t.GetProperty("Flags")?.GetValue(script)?.ToString(), properties });
        }
        return output;
    }

    // the property's own value: Data (int / float / bool / string), Object (a form link: its FormKey), or a list of them
    private static object? Value(object property)
    {
        var t = property.GetType();
        foreach (var name in new[] { "Data", "Object" })
        {
            var v = t.GetProperty(name)?.GetValue(property);
            if (v == null) continue;
            if (v is string || v.GetType().IsPrimitive) return v.ToString();
            if (v is IEnumerable list) return list.Cast<object>().Select(Link).ToArray();
            return Link(v);
        }
        return null;
    }

    private static string? Link(object v) =>
        v.GetType().GetProperty("FormKey")?.GetValue(v)?.ToString() ?? v.ToString();
}
