using System.Collections;
using Mutagen.Bethesda.Fallout4;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Cache;
using Mutagen.Bethesda.Plugins.Records;

/// <summary>Papyrus scripts and VMAD fragments attached to a record, read cleanly for exports and F0 research.</summary>
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

    public static string FormatFormId(FormKey fk) => fk.ID.ToString("X8");

    public static object? ResolveFormKey(FormKey fk, ILinkCache cache)
    {
        if (fk.IsNull) return null;
        if (cache.TryResolve<IMajorRecordGetter>(fk, out var rec))
        {
            return new
            {
                form_id = FormatFormId(fk),
                formkey = fk.ToString(),
                editor_id = rec.EditorID ?? "",
                record_type = rec.GetType().Name.Replace("BinaryOverlay", ""),
            };
        }
        return new
        {
            form_id = FormatFormId(fk),
            formkey = fk.ToString(),
            editor_id = "",
            record_type = "Unresolved",
        };
    }

    public static List<object> ScriptsResolved(object? recordOrVmad, ILinkCache cache, bool isVmad = false)
    {
        var output = new List<object>();
        if (recordOrVmad == null) return output;
        var vmad = isVmad ? recordOrVmad : recordOrVmad.GetType().GetProperty("VirtualMachineAdapter")?.GetValue(recordOrVmad);
        if (vmad == null) return output;

        var scriptList = new List<object>();
        if (vmad.GetType().GetProperty("Scripts")?.GetValue(vmad) is IEnumerable scripts)
            foreach (var s in scripts) scriptList.Add(s);
        var topScript = vmad.GetType().GetProperty("Script")?.GetValue(vmad);
        if (topScript != null && !scriptList.Contains(topScript))
            scriptList.Add(topScript);

        foreach (var script in scriptList)
            output.Add(SerializeScriptEntry(script, cache));
        return output;
    }

    public static object SerializeScriptEntry(object script, ILinkCache cache)
    {
        var t = script.GetType();
        var properties = new List<object>();
        if (t.GetProperty("Properties")?.GetValue(script) is IEnumerable props)
        {
            foreach (var p in props)
            {
                var pt = p.GetType();
                var rawVal = Value(p);
                var resolvedRefs = ResolvePropertyLinks(p, cache);
                var aliasIdx = pt.GetProperty("Alias")?.GetValue(p);
                properties.Add(new
                {
                    name = pt.GetProperty("Name")?.GetValue(p)?.ToString(),
                    kind = pt.Name.Replace("BinaryOverlay", ""),
                    alias_index = aliasIdx,
                    value = rawVal,
                    resolved = resolvedRefs,
                });
            }
        }
        return new
        {
            name = t.GetProperty("Name")?.GetValue(script)?.ToString() ?? "",
            flags = t.GetProperty("Flags")?.GetValue(script)?.ToString(),
            properties,
        };
    }

    public static object? InspectVmad(object record, ILinkCache cache)
    {
        var vmad = record.GetType().GetProperty("VirtualMachineAdapter")?.GetValue(record);
        if (vmad == null) return null;
        var vt = vmad.GetType();
        var scripts = new List<object>();
        if (vt.GetProperty("Scripts")?.GetValue(vmad) is IEnumerable sc)
            foreach (var s in sc) scripts.Add(SerializeScriptEntry(s, cache));

        object? topScript = null;
        if (vt.GetProperty("Script")?.GetValue(vmad) is { } ts)
            topScript = SerializeScriptEntry(ts, cache);

        var questFragments = new List<object>();
        if (vt.GetProperty("Fragments")?.GetValue(vmad) is IEnumerable qfList)
        {
            foreach (var f in qfList)
            {
                questFragments.Add(new
                {
                    stage = GetProp(f, "Stage"),
                    stage_index = GetProp(f, "StageIndex"),
                    unknown = GetProp(f, "Unknown"),
                    unknown2 = GetProp(f, "Unknown2"),
                    script_name = GetProp(f, "ScriptName")?.ToString() ?? "",
                    fragment_name = GetProp(f, "FragmentName")?.ToString() ?? "",
                });
            }
        }

        var aliasEntries = new List<object>();
        if (vt.GetProperty("Aliases")?.GetValue(vmad) is IEnumerable alList)
        {
            foreach (var a in alList)
            {
                var prop = GetProp(a, "Property");
                var propAlias = prop != null ? GetProp(prop, "Alias") : null;
                var propObj = prop != null ? ResolvePropertyLinks(prop, cache) : new List<object>();
                var aScripts = new List<object>();
                if (GetProp(a, "Scripts") is IEnumerable asc)
                    foreach (var s in asc) aScripts.Add(SerializeScriptEntry(s, cache));
                aliasEntries.Add(new
                {
                    alias_index = propAlias,
                    property_targets = propObj,
                    scripts = aScripts,
                });
            }
        }

        object? scriptFragments = null;
        if (vt.GetProperty("ScriptFragments")?.GetValue(vmad) is { } sf)
        {
            var sfScript = GetProp(sf, "Script") is { } sfs ? SerializeScriptEntry(sfs, cache) : null;
            var phaseFrags = new List<object>();
            if (GetProp(sf, "PhaseFragments") is IEnumerable pfs)
                foreach (var pf in pfs)
                    phaseFrags.Add(new
                    {
                        flags = GetProp(pf, "Flags")?.ToString(),
                        index = GetProp(pf, "Index"),
                        script_name = GetProp(pf, "ScriptName")?.ToString() ?? "",
                        fragment_name = GetProp(pf, "FragmentName")?.ToString() ?? "",
                    });
            var menuFrags = new List<object>();
            if (GetProp(sf, "Fragments") is IEnumerable tfs)
                foreach (var tf in tfs)
                    menuFrags.Add(new
                    {
                        item_id = GetProp(tf, "ItemIndex") ?? GetProp(tf, "ItemId"),
                        unknown = GetProp(tf, "Unknown")?.ToString(),
                        script_name = GetProp(tf, "ScriptName")?.ToString() ?? "",
                        fragment_name = GetProp(tf, "FragmentName")?.ToString() ?? "",
                    });
            scriptFragments = new
            {
                flags = GetProp(sf, "Flags")?.ToString(),
                file_name = GetProp(sf, "FileName")?.ToString(),
                script = sfScript,
                phase_fragments = phaseFrags,
                fragments = menuFrags,
                on_begin = SerializeScriptFragmentRef(GetProp(sf, "OnBegin")),
                on_end = SerializeScriptFragmentRef(GetProp(sf, "OnEnd")),
            };
        }

        return new
        {
            vmad_type = vt.Name.Replace("BinaryOverlay", ""),
            extra_bind_data_version = GetProp(vmad, "ExtraBindDataVersion"),
            scripts,
            script = topScript,
            fragments = questFragments,
            aliases = aliasEntries,
            script_fragments = scriptFragments,
        };
    }

    private static object? SerializeScriptFragmentRef(object? frag)
    {
        if (frag == null) return null;
        return new
        {
            unknown = GetProp(frag, "Unknown"),
            script_name = GetProp(frag, "ScriptName")?.ToString() ?? "",
            fragment_name = GetProp(frag, "FragmentName")?.ToString() ?? "",
        };
    }

    private static object? GetProp(object? obj, string name)
    {
        if (obj == null) return null;
        try { return obj.GetType().GetProperty(name)?.GetValue(obj); }
        catch { return null; }
    }

    private static List<object> ResolvePropertyLinks(object property, ILinkCache cache)
    {
        var list = new List<object>();
        var t = property.GetType();
        var objVal = t.GetProperty("Object")?.GetValue(property);
        if (objVal != null)
        {
            if (TryExtractFormKey(objVal, out var fk) && !fk.IsNull)
                list.Add(ResolveFormKey(fk, cache)!);
            else if (objVal is IEnumerable seq && objVal is not string)
            {
                foreach (var item in seq)
                {
                    if (TryExtractFormKey(item, out var itemFk) && !itemFk.IsNull)
                        list.Add(ResolveFormKey(itemFk, cache)!);
                }
            }
        }
        var objsVal = t.GetProperty("Objects")?.GetValue(property);
        if (objsVal is IEnumerable oseq)
        {
            foreach (var item in oseq)
            {
                var inner = item.GetType().GetProperty("Object")?.GetValue(item) ?? item;
                if (TryExtractFormKey(inner, out var itemFk) && !itemFk.IsNull)
                    list.Add(ResolveFormKey(itemFk, cache)!);
            }
        }
        return list;
    }

    private static bool TryExtractFormKey(object obj, out FormKey fk)
    {
        if (obj is FormKey direct) { fk = direct; return true; }
        var prop = obj.GetType().GetProperty("FormKey")?.GetValue(obj);
        if (prop is FormKey k) { fk = k; return true; }
        fk = FormKey.Null;
        return false;
    }

    // the property's own value: Data (int / float / bool / string), Object (a form link: its FormKey), or a list of them
    private static object? Value(object property)
    {
        var t = property.GetType();
        foreach (var name in new[] { "Data", "Object", "Objects" })
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
        v.GetType().GetProperty("FormKey")?.GetValue(v)?.ToString()
        ?? v.GetType().GetProperty("Object")?.GetValue(v)?.GetType().GetProperty("FormKey")?.GetValue(v.GetType().GetProperty("Object")!.GetValue(v))?.ToString()
        ?? v.ToString();
}
