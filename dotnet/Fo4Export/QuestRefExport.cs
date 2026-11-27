using System.Collections;
using System.Globalization;
using System.Text.Json;
using Mutagen.Bethesda;
using Mutagen.Bethesda.Fallout4;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Cache;
using Mutagen.Bethesda.Plugins.Records;

/// <summary>F0 quest, alias, scene, package, terminal, and attached script reference exporter for Fallout 4 masters.</summary>
public static class QuestRefExport
{
    private sealed record PlacedIndexEntry(IPlacedGetter Placed, bool Persistent, FormKey CellKey, string? CellEdid, string? Worldspace);

    public static int Run(IReadOnlyList<IFallout4ModGetter> loadOrder, ILinkCache cache, string outPath, IReadOnlyList<string> selectors)
    {
        var questsByKey = new Dictionary<FormKey, IQuestGetter>();
        var scenesByKey = new Dictionary<FormKey, ISceneGetter>();
        var termsByKey = new Dictionary<FormKey, ITerminalGetter>();
        var pkgsByKey = new Dictionary<FormKey, IPackageGetter>();

        foreach (var mod in loadOrder)
        {
            foreach (var q in mod.Quests) if (!q.IsDeleted) questsByKey[q.FormKey] = q; else questsByKey.Remove(q.FormKey);
            foreach (var s in mod.EnumerateMajorRecords<ISceneGetter>()) if (!s.IsDeleted) scenesByKey[s.FormKey] = s; else scenesByKey.Remove(s.FormKey);
            foreach (var t in mod.Terminals) if (!t.IsDeleted) termsByKey[t.FormKey] = t; else termsByKey.Remove(t.FormKey);
            foreach (var p in mod.Packages) if (!p.IsDeleted) pkgsByKey[p.FormKey] = p; else pkgsByKey.Remove(p.FormKey);
        }

        var questsByEdid = new Dictionary<string, IQuestGetter>(StringComparer.OrdinalIgnoreCase);
        foreach (var q in questsByKey.Values)
            if (!string.IsNullOrWhiteSpace(q.EditorID)) questsByEdid[q.EditorID] = q;

        var scenesByQuest = new Dictionary<FormKey, List<ISceneGetter>>();
        foreach (var sc in scenesByKey.Values)
        {
            var qk = sc.Quest.FormKey;
            if (!qk.IsNull)
            {
                if (!scenesByQuest.TryGetValue(qk, out var slist)) scenesByQuest[qk] = slist = new List<ISceneGetter>();
                slist.Add(sc);
            }
        }

        // Index placed refs, reverse XLKR links, and XLRT LocationRefTypes across interiors + worldspaces.
        var placedKeys = CellMerge.PlacedKeys(loadOrder);
        var placedIndex = new Dictionary<FormKey, PlacedIndexEntry>();
        var reverseLinkedByTarget = new Dictionary<FormKey, List<PlacedIndexEntry>>();
        var placedByLocRefType = new Dictionary<FormKey, List<PlacedIndexEntry>>();
        var placedByBase = new Dictionary<FormKey, List<PlacedIndexEntry>>();

        foreach (var merged in CellMerge.All(loadOrder, placedKeys, worldspaces: true))
        {
            foreach (var child in merged.Children)
            {
                var entry = new PlacedIndexEntry(child.Record, child.Persistent, merged.Cell.FormKey, merged.EditorID, merged.Worldspace);
                placedIndex[child.Record.FormKey] = entry;

                if (child.Record is IPlacedObjectGetter po)
                {
                    if (!po.Base.IsNull)
                    {
                        if (!placedByBase.TryGetValue(po.Base.FormKey, out var bl)) placedByBase[po.Base.FormKey] = bl = new List<PlacedIndexEntry>();
                        bl.Add(entry);
                    }
                    foreach (var lr in po.LinkedReferences)
                    {
                        if (!lr.Reference.IsNull)
                        {
                            if (!reverseLinkedByTarget.TryGetValue(lr.Reference.FormKey, out var rl)) reverseLinkedByTarget[lr.Reference.FormKey] = rl = new List<PlacedIndexEntry>();
                            rl.Add(entry);
                        }
                    }
                }
                if (GetProp(child.Record, "LocationRefTypes") is IEnumerable lrts)
                {
                    foreach (var lrt in lrts)
                    {
                        if (TryExtractFormKey(lrt, out var lrtFk) && !lrtFk.IsNull)
                        {
                            if (!placedByLocRefType.TryGetValue(lrtFk, out var ll)) placedByLocRefType[lrtFk] = ll = new List<PlacedIndexEntry>();
                            ll.Add(entry);
                        }
                    }
                }
            }
        }

        // Index terminals that reference any QUST in VMAD properties or conditions
        var termsByQuest = new Dictionary<FormKey, HashSet<FormKey>>();
        foreach (var term in termsByKey.Values)
        {
            var referencedInTerm = new HashSet<FormKey>();
            foreach (var sObj in ScriptExport.ScriptsResolved(term, cache, false))
                CollectFormKeysFromScriptObj(sObj, referencedInTerm);
            if (ScriptExport.InspectVmad(term, cache) is { } vmadObj)
            {
                if (GetProp(vmadObj, "script_fragments") is { } sf && GetProp(sf, "script") is { } fragScript)
                    CollectFormKeysFromScriptObj(fragScript, referencedInTerm);
            }
            foreach (var mi in term.MenuItems ?? Array.Empty<ITerminalMenuItemGetter>())
                CollectFormKeysFromConditions(mi.Conditions, referencedInTerm);
            foreach (var fk in referencedInTerm)
            {
                if (questsByKey.ContainsKey(fk))
                {
                    if (!termsByQuest.TryGetValue(fk, out var tl)) termsByQuest[fk] = tl = new HashSet<FormKey>();
                    tl.Add(term.FormKey);
                }
            }
        }

        var exportedQuests = new List<object>();
        foreach (var sel in selectors)
        {
            IQuestGetter? quest = null;
            if (questsByEdid.TryGetValue(sel, out var qByName))
            {
                quest = qByName;
            }
            else if (TryParseHexId(sel, out var targetId))
            {
                quest = questsByKey.Values.FirstOrDefault(q => q.FormKey.ID == targetId);
            }
            if (quest == null)
            {
                Console.Error.WriteLine($"quest-ref: quest '{sel}' not found");
                return 1;
            }
            exportedQuests.Add(ExportOneQuest(quest, cache, scenesByQuest, scenesByKey, termsByKey, pkgsByKey, placedIndex, reverseLinkedByTarget, placedByLocRefType, placedByBase, termsByQuest));
        }

        Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(outPath))!);
        var payload = new
        {
            schema_version = 1,
            plugins = loadOrder.Select(m => m.ModKey.FileName).ToArray(),
            quests = exportedQuests,
        };
        File.WriteAllText(outPath, JsonSerializer.Serialize(payload, new JsonSerializerOptions { WriteIndented = true }));
        Console.WriteLine($"quest-ref: exported {exportedQuests.Count} quests -> {outPath}");
        return 0;
    }

    public static int VerifyIds(IReadOnlyList<IFallout4ModGetter> loadOrder, ILinkCache cache, string idsFile)
    {
        var lines = File.ReadAllLines(idsFile)
            .Select(l => l.Trim())
            .Where(l => l.Length > 0 && !l.StartsWith("#"))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToList();

        var knownIds = new HashSet<uint>();
        foreach (var mod in loadOrder)
        {
            foreach (var rec in mod.EnumerateMajorRecords())
                knownIds.Add(rec.FormKey.ID);
        }

        var missing = new List<string>();
        int resolved = 0;
        foreach (var token in lines)
        {
            if (!TryParseHexId(token, out var id))
            {
                missing.Add(token);
                continue;
            }
            bool ok = knownIds.Contains(id);
            if (!ok)
            {
                foreach (var mod in loadOrder)
                {
                    if (cache.TryResolve<IMajorRecordGetter>(new FormKey(mod.ModKey, id), out _))
                    {
                        ok = true;
                        break;
                    }
                }
            }
            if (ok) resolved++;
            else missing.Add(token);
        }
        Console.WriteLine(JsonSerializer.Serialize(new { resolved, total = lines.Count, missing }));
        return missing.Count == 0 ? 0 : 1;
    }

    public static bool TryParseHexId(string raw, out uint id)
    {
        var s = raw.Trim();
        if (s.StartsWith("0x", StringComparison.OrdinalIgnoreCase)) s = s[2..];
        if (s.Contains(':')) s = s.Split(':')[0];
        return uint.TryParse(s, NumberStyles.HexNumber, CultureInfo.InvariantCulture, out id);
    }

    private static object ExportOneQuest(
        IQuestGetter quest,
        ILinkCache cache,
        Dictionary<FormKey, List<ISceneGetter>> scenesByQuest,
        Dictionary<FormKey, ISceneGetter> scenesByKey,
        Dictionary<FormKey, ITerminalGetter> termsByKey,
        Dictionary<FormKey, IPackageGetter> pkgsByKey,
        Dictionary<FormKey, PlacedIndexEntry> placedIndex,
        Dictionary<FormKey, List<PlacedIndexEntry>> reverseLinkedByTarget,
        Dictionary<FormKey, List<PlacedIndexEntry>> placedByLocRefType,
        Dictionary<FormKey, List<PlacedIndexEntry>> placedByBase,
        Dictionary<FormKey, HashSet<FormKey>> termsByQuest)
    {
        var attachedScripts = new List<object>();
        var seenAttached = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var referencedFormKeys = new HashSet<FormKey>();
        var discoveredTermKeys = new HashSet<FormKey>();
        var discoveredSceneKeys = new HashSet<FormKey>();

        if (termsByQuest.TryGetValue(quest.FormKey, out var qtSet))
            foreach (var tk in qtSet) discoveredTermKeys.Add(tk);

        void RecordScripts(string ownerKind, FormKey ownerFk, string ownerEdid, string role, object? vmadObj, bool isVmad = false)
        {
            foreach (var sObj in ScriptExport.ScriptsResolved(vmadObj, cache, isVmad))
            {
                var sName = GetProp(sObj, "name")?.ToString() ?? "";
                if (string.IsNullOrWhiteSpace(sName)) continue;
                var dedupKey = $"{ownerKind}|{ownerFk}|{role}|{sName}";
                if (seenAttached.Add(dedupKey))
                {
                    attachedScripts.Add(new
                    {
                        script_name = sName,
                        owner_kind = ownerKind,
                        owner_form_id = ScriptExport.FormatFormId(ownerFk),
                        owner_editor_id = ownerEdid,
                        role,
                        properties = GetProp(sObj, "properties"),
                    });
                }
                CollectResolvedLinksFromScript(sObj, referencedFormKeys, discoveredTermKeys, discoveredSceneKeys, placedIndex);
            }
        }

        var vmad = ScriptExport.InspectVmad(quest, cache);
        RecordScripts("QUST", quest.FormKey, quest.EditorID ?? "", "quest", quest);

        // Index fragment scripts per stage and per alias from VMAD
        var stageFragScripts = new Dictionary<int, List<object>>();
        var aliasVmadByIndex = new Dictionary<int, List<object>>();
        if (vmad != null)
        {
            if (GetProp(vmad, "fragments") is IEnumerable qfrags)
            {
                foreach (var f in qfrags)
                {
                    var sn = GetProp(f, "script_name")?.ToString() ?? "";
                    var fn = GetProp(f, "fragment_name")?.ToString() ?? "";
                    int st = Convert.ToInt32(GetProp(f, "stage") ?? -1);
                    if (!stageFragScripts.TryGetValue(st, out var fl)) stageFragScripts[st] = fl = new List<object>();
                    fl.Add(f);
                    if (!string.IsNullOrWhiteSpace(sn) && seenAttached.Add($"QUST_FRAG|{quest.FormKey}|{sn}"))
                    {
                        attachedScripts.Add(new
                        {
                            script_name = sn,
                            owner_kind = "QUST_FRAGMENT",
                            owner_form_id = ScriptExport.FormatFormId(quest.FormKey),
                            owner_editor_id = quest.EditorID ?? "",
                            role = "quest_fragment",
                            sample_function = fn,
                        });
                    }
                }
            }
            if (GetProp(vmad, "aliases") is IEnumerable vaList)
            {
                foreach (var va in vaList)
                {
                    var idxObj = GetProp(va, "alias_index");
                    if (idxObj != null && int.TryParse(idxObj.ToString(), out var aIdx))
                    {
                        if (!aliasVmadByIndex.TryGetValue(aIdx, out var vl)) aliasVmadByIndex[aIdx] = vl = new List<object>();
                        if (GetProp(va, "scripts") is IEnumerable scs)
                        {
                            foreach (var s in scs)
                            {
                                vl.Add(s);
                                var sName = GetProp(s, "name")?.ToString() ?? "";
                                if (!string.IsNullOrWhiteSpace(sName) && seenAttached.Add($"ALIAS|{quest.FormKey}|{aIdx}|{sName}"))
                                {
                                    attachedScripts.Add(new
                                    {
                                        script_name = sName,
                                        owner_kind = "QUST_ALIAS",
                                        owner_form_id = ScriptExport.FormatFormId(quest.FormKey),
                                        owner_editor_id = $"{quest.EditorID ?? ""}[alias {aIdx}]",
                                        role = $"alias_{aIdx}",
                                        properties = GetProp(s, "properties"),
                                    });
                                }
                                CollectResolvedLinksFromScript(s, referencedFormKeys, discoveredTermKeys, discoveredSceneKeys, placedIndex);
                            }
                        }
                    }
                }
            }
        }

        // Stages
        var stages = new List<object>();
        foreach (var st in quest.Stages)
        {
            var logs = new List<object>();
            foreach (var le in st.LogEntries)
            {
                logs.Add(new
                {
                    flags = le.Flags.ToString(),
                    entry = le.Entry?.String ?? "",
                    conditions = SerializeConditions(le.Conditions, cache),
                });
            }
            stageFragScripts.TryGetValue((int)st.Index, out var fragsForStage);
            stages.Add(new
            {
                index = (int)st.Index,
                flags = st.Flags.ToString(),
                log_entries = logs,
                fragments = fragsForStage ?? new List<object>(),
            });
        }

        // Objectives
        var objectives = new List<object>();
        foreach (var ob in quest.Objectives)
        {
            var targets = new List<object>();
            foreach (var tgt in ob.Targets)
            {
                targets.Add(new
                {
                    alias_id = tgt.AliasID,
                    flags = tgt.Flags.ToString(),
                    keyword = ResolveLinkObj(GetProp(tgt, "Keyword"), cache),
                    conditions = SerializeConditions(tgt.Conditions, cache),
                });
            }
            objectives.Add(new
            {
                index = (int)ob.Index,
                flags = ob.Flags.ToString(),
                display_text = ob.DisplayText?.String ?? "",
                targets,
            });
        }

        // Aliases
        var aliases = new List<object>();
        if (quest.Aliases != null)
        {
            foreach (var al in quest.Aliases)
            {
                var idVal = Convert.ToInt32(GetProp(al, "ID") ?? -1);
                var nameVal = GetProp(al, "Name")?.ToString() ?? "";
                var flagsVal = GetProp(al, "Flags")?.ToString() ?? "";
                var fillType = al.GetType().Name.Replace("BinaryOverlay", "");

                var forcedRefLink = GetProp(al, "ForcedReference");
                var forcedInfo = InspectPlacedRef(forcedRefLink, cache, placedIndex, referencedFormKeys, discoveredTermKeys, RecordScripts);
                var specificLoc = ResolveLinkObj(GetProp(al, "SpecificLocation"), cache);
                var uniqueActor = ResolveLinkObj(GetProp(al, "UniqueActor"), cache);
                var refTypeFk = FindLocationRefTypeFormKey(al, cache);
                var refType = refTypeFk.IsNull ? null : ScriptExport.ResolveFormKey(refTypeFk, cache);
                if (!refTypeFk.IsNull) referencedFormKeys.Add(refTypeFk);

                var lrtMatches = new List<object>();
                if (!refTypeFk.IsNull && placedByLocRefType.TryGetValue(refTypeFk, out var matchedPlaced))
                {
                    foreach (var pe in matchedPlaced)
                    {
                        referencedFormKeys.Add(pe.Placed.FormKey);
                        var detail = InspectPlacedEntry(pe, cache, referencedFormKeys, discoveredTermKeys, RecordScripts);
                        if (detail != null) lrtMatches.Add(detail);
                    }
                }

                var pkgSummaries = new List<object>();
                if (GetProp(al, "PackageData") is IEnumerable pkgLinks)
                {
                    foreach (var pl in pkgLinks)
                    {
                        if (TryExtractFormKey(pl, out var pfk) && !pfk.IsNull)
                        {
                            referencedFormKeys.Add(pfk);
                            if (pkgsByKey.TryGetValue(pfk, out var pkg))
                            {
                                pkgSummaries.Add(ExportPackage(pkg, cache, referencedFormKeys, placedIndex));
                                RecordScripts("PACK", pkg.FormKey, pkg.EditorID ?? "", "alias_package", pkg);
                            }
                            else pkgSummaries.Add(ScriptExport.ResolveFormKey(pfk, cache)!);
                        }
                    }
                }

                aliasVmadByIndex.TryGetValue(idVal, out var vmadScripts);
                aliases.Add(new
                {
                    id = idVal,
                    name = nameVal,
                    flags = flagsVal,
                    fill_type = fillType,
                    forced_reference = forcedInfo,
                    unique_actor = uniqueActor,
                    specific_location = specificLoc,
                    reference_type = refType,
                    location_ref_matches = lrtMatches,
                    scripts = vmadScripts ?? new List<object>(),
                    packages = pkgSummaries,
                    conditions = SerializeConditions(GetProp(al, "Conditions") as IEnumerable, cache),
                });
            }
        }

        // Check reverse XLKR links onto referenced placed refs (e.g. basement terminal -> security gate).
        foreach (var fk in referencedFormKeys.ToList())
        {
            if (reverseLinkedByTarget.TryGetValue(fk, out var revList))
            {
                foreach (var revEntry in revList)
                {
                    referencedFormKeys.Add(revEntry.Placed.FormKey);
                    InspectPlacedEntry(revEntry, cache, referencedFormKeys, discoveredTermKeys, RecordScripts);
                }
            }
        }

        // Also include placed refs for any discovered Terminal bases (so terminal ref + its scripts/XLKR are included).
        foreach (var tk in discoveredTermKeys.ToList())
        {
            referencedFormKeys.Add(tk);
            if (placedByBase.TryGetValue(tk, out var termPlaced))
            {
                foreach (var tp in termPlaced)
                {
                    referencedFormKeys.Add(tp.Placed.FormKey);
                    InspectPlacedEntry(tp, cache, referencedFormKeys, discoveredTermKeys, RecordScripts);
                }
            }
        }

        // Inspect all referenced placed refs cleanly
        var referencedPlacedDetails = new List<object>();
        var seenPlaced = new HashSet<FormKey>();
        foreach (var fk in referencedFormKeys.ToList())
        {
            if (placedIndex.TryGetValue(fk, out var pEntry) && seenPlaced.Add(fk))
            {
                var detail = InspectPlacedEntry(pEntry, cache, referencedFormKeys, discoveredTermKeys, RecordScripts);
                if (detail != null) referencedPlacedDetails.Add(detail);
            }
        }

        // Scenes
        var sceneKeys = new HashSet<FormKey>(discoveredSceneKeys);
        if (scenesByQuest.TryGetValue(quest.FormKey, out var qScenes))
            foreach (var s in qScenes) sceneKeys.Add(s.FormKey);

        var scenesOut = new List<object>();
        foreach (var sk in sceneKeys.OrderBy(k => k.ID))
        {
            if (!scenesByKey.TryGetValue(sk, out var sc)) continue;
            scenesOut.Add(ExportScene(sc, cache, pkgsByKey, referencedFormKeys, discoveredTermKeys, placedIndex, RecordScripts, seenAttached, attachedScripts));
        }

        // Terminals
        var terminalsOut = new List<object>();
        foreach (var tk in discoveredTermKeys.OrderBy(k => k.ID))
        {
            referencedFormKeys.Add(tk);
            if (!termsByKey.TryGetValue(tk, out var term)) continue;
            terminalsOut.Add(ExportTerminal(term, cache, referencedFormKeys, RecordScripts, seenAttached, attachedScripts));
        }

        var referencedQuests = new List<object>();
        var referencedRecords = new List<object>();
        foreach (var fk in referencedFormKeys.OrderBy(k => k.ID))
        {
            if (fk.IsNull) continue;
            var res = ScriptExport.ResolveFormKey(fk, cache);
            if (res != null) referencedRecords.Add(res);
            if (cache.TryResolve<IQuestGetter>(fk, out var rq) && rq.FormKey != quest.FormKey)
            {
                referencedQuests.Add(new
                {
                    form_id = ScriptExport.FormatFormId(rq.FormKey),
                    formkey = rq.FormKey.ToString(),
                    editor_id = rq.EditorID ?? "",
                    name = rq.Name?.String ?? "",
                });
            }
        }

        return new
        {
            form_id = ScriptExport.FormatFormId(quest.FormKey),
            formkey = quest.FormKey.ToString(),
            editor_id = quest.EditorID ?? "",
            name = quest.Name?.String ?? "",
            flags = quest.Data?.Flags.ToString() ?? "",
            priority = quest.Data?.Priority,
            vmad,
            stages,
            objectives,
            aliases,
            scenes = scenesOut,
            terminals = terminalsOut,
            referenced_placed_refs = referencedPlacedDetails,
            attached_scripts = attachedScripts,
            referenced_quests = referencedQuests,
            referenced_records = referencedRecords,
        };
    }

    private static FormKey FindLocationRefTypeFormKey(object alias, ILinkCache cache)
    {
        FormKey Scan(object? obj, int depth)
        {
            if (obj == null || depth > 2) return FormKey.Null;
            if (TryExtractFormKey(obj, out var directFk) && !directFk.IsNull && cache.TryResolve<ILocationReferenceTypeGetter>(directFk, out _))
                return directFk;
            var t = obj.GetType();
            if (t.IsPrimitive || t.IsEnum || obj is string) return FormKey.Null;
            foreach (var p in t.GetProperties())
            {
                if (p.GetIndexParameters().Length > 0) continue;
                if (p.Name is "Conditions" or "PackageData" or "Spells" or "Items" or "Keywords" or "Factions" or "SpectatorOveridePackageList" or "StaticRegistration" or "Registration") continue;
                object? val;
                try { val = p.GetValue(obj); } catch { continue; }
                if (val == null) continue;
                if (TryExtractFormKey(val, out var fk))
                {
                    if (!fk.IsNull && cache.TryResolve<ILocationReferenceTypeGetter>(fk, out _))
                        return fk;
                    continue;
                }
                if (depth < 2 && val is not IEnumerable)
                {
                    var sub = Scan(val, depth + 1);
                    if (!sub.IsNull) return sub;
                }
            }
            return FormKey.Null;
        }
        return Scan(alias, 0);
    }

    private static void CollectFormKeysFromScriptObj(object scriptObj, HashSet<FormKey> dest)
    {
        if (GetProp(scriptObj, "properties") is not IEnumerable props) return;
        foreach (var p in props)
        {
            if (GetProp(p, "resolved") is not IEnumerable resList) continue;
            foreach (var r in resList)
            {
                var fkStr = GetProp(r, "formkey")?.ToString();
                if (!string.IsNullOrWhiteSpace(fkStr) && FormKey.TryFactory(fkStr, out var fk) && !fk.IsNull)
                    dest.Add(fk);
            }
        }
    }

    private static void CollectFormKeysFromConditions(IEnumerable? conditions, HashSet<FormKey> dest)
    {
        if (conditions == null) return;
        foreach (var c in conditions)
        {
            var data = GetProp(c, "Data");
            if (data == null) continue;
            foreach (var dp in data.GetType().GetProperties())
            {
                if (dp.GetIndexParameters().Length > 0) continue;
                object? v;
                try { v = dp.GetValue(data); } catch { continue; }
                if (v != null && TryExtractFormKey(v, out var fk) && !fk.IsNull)
                    dest.Add(fk);
            }
        }
    }

    private static object ExportScene(
        ISceneGetter sc,
        ILinkCache cache,
        Dictionary<FormKey, IPackageGetter> pkgsByKey,
        HashSet<FormKey> referencedFormKeys,
        HashSet<FormKey> discoveredTermKeys,
        Dictionary<FormKey, PlacedIndexEntry> placedIndex,
        Action<string, FormKey, string, string, object?, bool> recordScripts,
        HashSet<string> seenAttached,
        List<object> attachedScripts)
    {
        var scVmad = ScriptExport.InspectVmad(sc, cache);
        recordScripts("SCEN", sc.FormKey, sc.EditorID ?? "", "scene", sc, false);
        if (scVmad != null && GetProp(scVmad, "script_fragments") is { } sf)
        {
            void AddSceneFrag(string? sn, string? fn, string role)
            {
                if (!string.IsNullOrWhiteSpace(sn) && seenAttached.Add($"SCEN_FRAG|{sc.FormKey}|{sn}"))
                    attachedScripts.Add(new { script_name = sn, owner_kind = "SCEN_FRAGMENT", owner_form_id = ScriptExport.FormatFormId(sc.FormKey), owner_editor_id = sc.EditorID ?? "", role, sample_function = fn ?? "" });
            }
            if (GetProp(sf, "on_begin") is { } ob) AddSceneFrag(GetProp(ob, "script_name")?.ToString(), GetProp(ob, "fragment_name")?.ToString(), "scene_begin");
            if (GetProp(sf, "on_end") is { } oe) AddSceneFrag(GetProp(oe, "script_name")?.ToString(), GetProp(oe, "fragment_name")?.ToString(), "scene_end");
            if (GetProp(sf, "phase_fragments") is IEnumerable pfs)
                foreach (var pf in pfs) AddSceneFrag(GetProp(pf, "script_name")?.ToString(), GetProp(pf, "fragment_name")?.ToString(), "scene_phase");
        }

        var phases = new List<object>();
        int pIdx = 0;
        foreach (var ph in sc.Phases)
        {
            phases.Add(new
            {
                index = pIdx++,
                name = ph.Name ?? "",
                editor_width = GetProp(ph, "EditorWidth"),
                start_conditions = SerializeConditions(ph.StartConditions, cache),
                completion_conditions = SerializeConditions(ph.CompletionConditions, cache),
            });
        }

        var actors = new List<object>();
        foreach (var act in sc.Actors)
        {
            actors.Add(new
            {
                id = act.ID,
                flags = act.Flags.ToString(),
                behavior_flags = act.BehaviorFlags.ToString(),
                no_command_state = act.Flags.ToString(),
            });
        }

        var actions = new List<object>();
        foreach (var act in sc.Actions)
        {
            var topic = ResolveLinkObj(GetProp(act, "Topic"), cache);
            if (GetProp(act, "Topic") is { } tObj && TryExtractFormKey(tObj, out var tfk) && !tfk.IsNull)
                referencedFormKeys.Add(tfk);

            var actionPkgs = new List<object>();
            if (GetProp(act, "Packages") is IEnumerable apl)
            {
                foreach (var pl in apl)
                {
                    if (TryExtractFormKey(pl, out var pfk) && !pfk.IsNull)
                    {
                        referencedFormKeys.Add(pfk);
                        if (pkgsByKey.TryGetValue(pfk, out var pRec))
                            actionPkgs.Add(ExportPackage(pRec, cache, referencedFormKeys, placedIndex));
                        else
                            actionPkgs.Add(ScriptExport.ResolveFormKey(pfk, cache)!);
                    }
                }
            }
            actions.Add(new
            {
                index = GetProp(act, "Index"),
                type = GetProp(act, "Type")?.ToString() ?? act.GetType().Name.Replace("BinaryOverlay", ""),
                name = GetProp(act, "Name")?.ToString() ?? "",
                actor_id = GetProp(act, "ActorID"),
                start_phase = GetProp(act, "StartPhase"),
                end_phase = GetProp(act, "EndPhase"),
                flags = GetProp(act, "Flags")?.ToString() ?? "",
                timer_seconds = GetProp(act, "TimerSeconds") ?? GetProp(act, "MinSeconds"),
                timer_max_seconds = GetProp(act, "MaxSeconds"),
                topic,
                packages = actionPkgs,
                conditions = SerializeConditions(GetProp(act, "Conditions") as IEnumerable, cache),
            });
        }

        return new
        {
            form_id = ScriptExport.FormatFormId(sc.FormKey),
            formkey = sc.FormKey.ToString(),
            editor_id = sc.EditorID ?? "",
            flags = sc.Flags?.ToString() ?? "",
            vmad = scVmad,
            actors,
            phases,
            actions,
        };
    }

    private static object ExportTerminal(
        ITerminalGetter term,
        ILinkCache cache,
        HashSet<FormKey> referencedFormKeys,
        Action<string, FormKey, string, string, object?, bool> recordScripts,
        HashSet<string> seenAttached,
        List<object> attachedScripts)
    {
        var tVmad = ScriptExport.InspectVmad(term, cache);
        recordScripts("TERM", term.FormKey, term.EditorID ?? "", "terminal", term, false);
        if (tVmad != null && GetProp(tVmad, "script_fragments") is { } sf)
        {
            if (GetProp(sf, "script") is { } fragScript)
            {
                var sn = GetProp(fragScript, "name")?.ToString() ?? "";
                if (!string.IsNullOrWhiteSpace(sn) && seenAttached.Add($"TERM_FRAG_SCRIPT|{term.FormKey}|{sn}"))
                {
                    attachedScripts.Add(new
                    {
                        script_name = sn,
                        owner_kind = "TERM_FRAGMENT",
                        owner_form_id = ScriptExport.FormatFormId(term.FormKey),
                        owner_editor_id = term.EditorID ?? "",
                        role = "terminal_fragment_script",
                        properties = GetProp(fragScript, "properties"),
                    });
                }
                CollectFormKeysFromScriptObj(fragScript, referencedFormKeys);
            }
            if (GetProp(sf, "fragments") is IEnumerable mfs)
            {
                foreach (var mf in mfs)
                {
                    var sn = GetProp(mf, "script_name")?.ToString() ?? "";
                    if (!string.IsNullOrWhiteSpace(sn) && seenAttached.Add($"TERM_FRAG|{term.FormKey}|{sn}"))
                    {
                        attachedScripts.Add(new
                        {
                            script_name = sn,
                            owner_kind = "TERM_FRAGMENT",
                            owner_form_id = ScriptExport.FormatFormId(term.FormKey),
                            owner_editor_id = term.EditorID ?? "",
                            role = "terminal_fragment",
                            sample_function = GetProp(mf, "fragment_name")?.ToString() ?? "",
                        });
                    }
                }
            }
        }

        var items = new List<object>();
        foreach (var mi in term.MenuItems ?? Array.Empty<ITerminalMenuItemGetter>())
        {
            var subObj = GetProp(mi, "Submenu");
            if (subObj != null && TryExtractFormKey(subObj, out var smFk) && !smFk.IsNull) referencedFormKeys.Add(smFk);
            items.Add(new
            {
                item_id = mi.ItemId,
                type = mi.Type.ToString(),
                item_text = mi.ItemText?.String ?? "",
                display_text = mi.DisplayText?.String ?? "",
                response_text = mi.ResponseText?.String ?? "",
                submenu = ResolveLinkObj(subObj, cache),
                conditions = SerializeConditions(mi.Conditions, cache),
            });
        }

        return new
        {
            form_id = ScriptExport.FormatFormId(term.FormKey),
            formkey = term.FormKey.ToString(),
            editor_id = term.EditorID ?? "",
            name = term.Name?.String ?? "",
            header_text = term.HeaderText?.String ?? "",
            menu_items = items,
            vmad = tVmad,
        };
    }

    private static object ExportPackage(
        IPackageGetter pkg,
        ILinkCache cache,
        HashSet<FormKey> referencedFormKeys,
        Dictionary<FormKey, PlacedIndexEntry> placedIndex)
    {
        var template = ResolveLinkObj(pkg.PackageTemplate, cache);
        if (!pkg.PackageTemplate.IsNull) referencedFormKeys.Add(pkg.PackageTemplate.FormKey);

        var dataItems = new List<object>();
        if (pkg.Data != null)
        {
            foreach (var kv in pkg.Data)
            {
                var val = kv.Value;
                var kind = val.GetType().Name.Replace("BinaryOverlay", "");
                object? target = null;
                if (GetProp(val, "Target") is { } tgt) target = SerializePackageTarget(tgt, cache, referencedFormKeys, placedIndex);
                else if (GetProp(val, "Location") is { } loc) target = SerializePackageTarget(loc, cache, referencedFormKeys, placedIndex);
                else target = ScriptExport.ResolveFormKey(FormKey.Null, cache);

                var dataVal = GetProp(val, "Data")?.ToString();
                dataItems.Add(new
                {
                    key = kv.Key,
                    kind,
                    name = GetProp(val, "Name")?.ToString() ?? "",
                    data = dataVal,
                    target,
                });
            }
        }

        return new
        {
            form_id = ScriptExport.FormatFormId(pkg.FormKey),
            formkey = pkg.FormKey.ToString(),
            editor_id = pkg.EditorID ?? "",
            type = pkg.Type.ToString(),
            flags = pkg.Flags.ToString(),
            package_template = template,
            data = dataItems,
            conditions = SerializeConditions(pkg.Conditions, cache),
        };
    }

    private static object? SerializePackageTarget(
        object tgt,
        ILinkCache cache,
        HashSet<FormKey> referencedFormKeys,
        Dictionary<FormKey, PlacedIndexEntry> placedIndex)
    {
        var kind = tgt.GetType().Name.Replace("BinaryOverlay", "");
        object? refObj = null;
        foreach (var propName in new[] { "Reference", "Location", "Keyword", "Link", "Target" })
        {
            var pv = GetProp(tgt, propName);
            if (pv != null && TryExtractFormKey(pv, out var fk) && !fk.IsNull)
            {
                referencedFormKeys.Add(fk);
                refObj = ScriptExport.ResolveFormKey(fk, cache);
                break;
            }
        }
        var aliasIdx = GetProp(tgt, "AliasIndex");
        var radius = GetProp(tgt, "Radius");
        return new { kind, target = refObj, alias_index = aliasIdx, radius };
    }

    private static object? InspectPlacedRef(
        object? linkObj,
        ILinkCache cache,
        Dictionary<FormKey, PlacedIndexEntry> placedIndex,
        HashSet<FormKey> referencedFormKeys,
        HashSet<FormKey> discoveredTermKeys,
        Action<string, FormKey, string, string, object?, bool> recordScripts)
    {
        if (linkObj == null || !TryExtractFormKey(linkObj, out var fk) || fk.IsNull) return null;
        referencedFormKeys.Add(fk);
        if (placedIndex.TryGetValue(fk, out var entry))
            return InspectPlacedEntry(entry, cache, referencedFormKeys, discoveredTermKeys, recordScripts);
        return ScriptExport.ResolveFormKey(fk, cache);
    }

    private static object? InspectPlacedEntry(
        PlacedIndexEntry entry,
        ILinkCache cache,
        HashSet<FormKey> referencedFormKeys,
        HashSet<FormKey> discoveredTermKeys,
        Action<string, FormKey, string, string, object?, bool> recordScripts)
    {
        var placed = entry.Placed;
        FormKey baseFk = FormKey.Null;
        string baseEdid = "", baseType = "";
        object? baseScripts = null;
        if (placed is IPlacedObjectGetter po && po.Base.TryResolve(cache, out var bRec))
        {
            baseFk = bRec.FormKey;
            baseEdid = bRec.EditorID ?? "";
            baseType = bRec.GetType().Name.Replace("BinaryOverlay", "");
            referencedFormKeys.Add(baseFk);
            if (bRec is ITerminalGetter) discoveredTermKeys.Add(baseFk);
            baseScripts = ScriptExport.ScriptsResolved(bRec, cache);
            recordScripts(baseType, baseFk, baseEdid, "base_of_referenced_ref", bRec, false);
        }
        else if (placed is IPlacedNpcGetter pn && pn.Base.TryResolve(cache, out var nRec))
        {
            baseFk = nRec.FormKey;
            baseEdid = nRec.EditorID ?? "";
            baseType = nRec.GetType().Name.Replace("BinaryOverlay", "");
            referencedFormKeys.Add(baseFk);
            baseScripts = ScriptExport.ScriptsResolved(nRec, cache);
            recordScripts(baseType, baseFk, baseEdid, "npc_base_of_referenced_ref", nRec, false);
        }

        var refScripts = ScriptExport.ScriptsResolved(placed, cache);
        recordScripts(placed.GetType().Name.Replace("BinaryOverlay", ""), placed.FormKey, placed.EditorID ?? "", "referenced_ref", placed, false);

        var linked = new List<object>();
        if (placed is IPlacedObjectGetter obj)
        {
            foreach (var lr in obj.LinkedReferences)
            {
                if (!lr.KeywordOrReference.IsNull) referencedFormKeys.Add(lr.KeywordOrReference.FormKey);
                if (!lr.Reference.IsNull) referencedFormKeys.Add(lr.Reference.FormKey);
                linked.Add(new
                {
                    keyword = ResolveLinkObj(lr.KeywordOrReference, cache),
                    reference = ResolveLinkObj(lr.Reference, cache),
                });
            }
        }

        return new
        {
            form_id = ScriptExport.FormatFormId(placed.FormKey),
            formkey = placed.FormKey.ToString(),
            editor_id = placed.EditorID ?? "",
            type = placed.GetType().Name.Replace("BinaryOverlay", ""),
            persistent = entry.Persistent,
            cell_form_id = ScriptExport.FormatFormId(entry.CellKey),
            cell_editor_id = entry.CellEdid ?? "",
            worldspace = entry.Worldspace,
            base_form_id = baseFk.IsNull ? null : ScriptExport.FormatFormId(baseFk),
            base_editor_id = baseEdid,
            base_type = baseType,
            scripts = refScripts,
            base_scripts = baseScripts,
            linked_references = linked,
        };
    }

    private static void CollectResolvedLinksFromScript(
        object scriptObj,
        HashSet<FormKey> referencedFormKeys,
        HashSet<FormKey> discoveredTermKeys,
        HashSet<FormKey> discoveredSceneKeys,
        Dictionary<FormKey, PlacedIndexEntry> placedIndex)
    {
        if (GetProp(scriptObj, "properties") is not IEnumerable props) return;
        foreach (var p in props)
        {
            if (GetProp(p, "resolved") is not IEnumerable resList) continue;
            foreach (var r in resList)
            {
                var fkStr = GetProp(r, "formkey")?.ToString();
                if (!string.IsNullOrWhiteSpace(fkStr) && FormKey.TryFactory(fkStr, out var fk))
                {
                    referencedFormKeys.Add(fk);
                    var rtype = GetProp(r, "record_type")?.ToString() ?? "";
                    if (rtype == "Terminal") discoveredTermKeys.Add(fk);
                    else if (rtype == "Scene") discoveredSceneKeys.Add(fk);
                    if (placedIndex.TryGetValue(fk, out var pe) && pe.Placed is IPlacedObjectGetter po && !po.Base.IsNull)
                    {
                        referencedFormKeys.Add(po.Base.FormKey);
                    }
                }
            }
        }
    }

    private static List<object> SerializeConditions(IEnumerable? conditions, ILinkCache cache)
    {
        var list = new List<object>();
        if (conditions == null) return list;
        foreach (var c in conditions)
        {
            var data = GetProp(c, "Data");
            var fnName = data?.GetType().Name.Replace("ConditionDataBinaryOverlay", "").Replace("ConditionData", "") ?? "";
            var paramProps = new Dictionary<string, object?>();
            if (data != null)
            {
                foreach (var dp in data.GetType().GetProperties())
                {
                    if (dp.GetIndexParameters().Length > 0 || dp.Name is "StaticRegistration" or "Registration" or "RunOnType" or "Reference" or "Unknown3") continue;
                    object? v;
                    try { v = dp.GetValue(data); } catch { continue; }
                    if (v == null) continue;
                    if (TryExtractFormKey(v, out var fk))
                        paramProps[dp.Name] = fk.IsNull ? null : ScriptExport.ResolveFormKey(fk, cache);
                    else if (v.GetType().IsPrimitive || v.GetType().IsEnum || v is string)
                        paramProps[dp.Name] = v.ToString();
                }
            }
            list.Add(new
            {
                function = fnName,
                compare_operator = GetProp(c, "CompareOperator")?.ToString() ?? "",
                comparison_value = GetProp(c, "ComparisonValue")?.ToString() ?? "",
                flags = GetProp(c, "Flags")?.ToString() ?? "",
                run_on = GetProp(data, "RunOnType")?.ToString() ?? "",
                @params = paramProps,
            });
        }
        return list;
    }

    private static object? ResolveLinkObj(object? linkObj, ILinkCache cache)
    {
        if (linkObj == null || !TryExtractFormKey(linkObj, out var fk) || fk.IsNull) return null;
        return ScriptExport.ResolveFormKey(fk, cache);
    }

    private static object? GetProp(object? obj, string name)
    {
        if (obj == null) return null;
        try { return obj.GetType().GetProperty(name)?.GetValue(obj); }
        catch { return null; }
    }

    private static bool TryExtractFormKey(object? obj, out FormKey fk)
    {
        if (obj == null) { fk = FormKey.Null; return false; }
        if (obj is FormKey direct) { fk = direct; return true; }
        var prop = obj.GetType().GetProperty("FormKey")?.GetValue(obj);
        if (prop is FormKey k) { fk = k; return true; }
        fk = FormKey.Null;
        return false;
    }
}
