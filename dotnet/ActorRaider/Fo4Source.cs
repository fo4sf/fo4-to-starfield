// export-fo4: the placed Fallout 4 actor and what each template category resolves to (read-only).
using System.Text.Json;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Cache;
using F4 = Mutagen.Bethesda.Fallout4;

static class Fo4Source
{
    // Template categories in ACBS flag order (Mutagen Fallout4 Npc.TemplateActorType, verified with `props`).
    public static readonly (string Name, int Bit)[] Categories =
    {
        ("Traits", 0), ("Stats", 1), ("Factions", 2), ("SpellList", 3), ("AiData", 4), ("AiPackages", 5),
        ("ModelOrAnimation", 6), ("BaseData", 7), ("Inventory", 8), ("Script", 9), ("DefPackList", 10),
        ("AttackData", 11), ("Keywords", 12),
    };

    static FormKey Slot(F4.ITemplateActorsGetter t, string cat) => cat switch
    {
        "Traits" => t.TraitTemplate.FormKey, "Stats" => t.StatsTemplate.FormKey, "Factions" => t.FactionsTemplate.FormKey,
        "SpellList" => t.SpellListTemplate.FormKey, "AiData" => t.AiDataTemplate.FormKey,
        "AiPackages" => t.AiPackagesTemplate.FormKey, "ModelOrAnimation" => t.ModelOrAnimationTemplate.FormKey,
        "BaseData" => t.BaseDataTemplate.FormKey, "Inventory" => t.InventoryTemplate.FormKey,
        "Script" => t.ScriptTemplate.FormKey, "DefPackList" => t.DefPackListTemplate.FormKey,
        "AttackData" => t.AttackDataTemplate.FormKey, "Keywords" => t.KeywordsTemplate.FormKey,
        _ => FormKey.Null,
    };

    static string Id(FormKey fk) => fk.IsNull ? "" : $"{fk.ID:X8}";
    static Dictionary<string, object?> Ref(ILinkCache c, FormKey fk)
    {
        var d = new Dictionary<string, object?> { ["id"] = Id(fk), ["edid"] = Util.Edid(c, fk) };
        if (!fk.IsNull && c.TryResolve<Mutagen.Bethesda.Plugins.Records.IMajorRecordGetter>(fk, out var r)) d["type"] = Util.RecType(r);
        return d;
    }

    /// The NPC_ records a template link yields at a player level: an NPC_ itself, or the qualifying entries of a
    /// leveled list (all entries at or below the level when the list says "calculate from all levels <= player",
    /// else the highest such level), recursively. Order is the list's order; the caller takes the first.
    static List<F4.INpcGetter> Candidates(ILinkCache c, FormKey fk, int level, int depth = 0)
    {
        var outp = new List<F4.INpcGetter>();
        if (fk.IsNull || depth > 8) return outp;
        if (c.TryResolve<F4.INpcGetter>(fk, out var npc)) { outp.Add(npc); return outp; }
        if (!c.TryResolve<F4.ILeveledNpcGetter>(fk, out var lvl) || lvl.Entries is null) return outp;
        var ok = lvl.Entries.Where(e => e.Data is not null && e.Data.Level <= level).ToList();
        if (!lvl.Flags.HasFlag(F4.LeveledNpc.Flag.CalculateFromAllLevelsLessThanOrEqualPlayer) && ok.Count > 0)
        {
            var top = ok.Max(e => e.Data!.Level);
            ok = ok.Where(e => e.Data!.Level == top).ToList();
        }
        foreach (var e in ok) outp.AddRange(Candidates(c, e.Data!.Reference.FormKey, level, depth + 1));
        return outp;
    }

    /// The record a category's data comes from: follow the per-category template (or the default one) while the
    /// current record has that category's template flag set.
    static (F4.INpcGetter Source, List<object> Hops) Effective(ILinkCache c, F4.INpcGetter npc, string cat, int bit, int level)
    {
        var hops = new List<object>();
        var cur = npc;
        for (int guard = 0; guard < 12; guard++)
        {
            if (((int)cur.UseTemplateActors & (1 << bit)) == 0) break;
            var link = cur.TemplateActors is { } ta ? Slot(ta, cat) : FormKey.Null;
            if (link.IsNull) link = cur.DefaultTemplate.FormKey;
            var cand = Candidates(c, link, level);
            hops.Add(new Dictionary<string, object?>
            {
                ["from"] = cur.EditorID, ["via"] = Ref(c, link),
                ["candidates"] = cand.Select(x => x.EditorID).ToList(), ["picked"] = cand.FirstOrDefault()?.EditorID,
            });
            if (cand.Count == 0) break;
            cur = cand[0];
        }
        return (cur, hops);
    }

    public static int Export(string esm, uint achrId, int level, string outPath)
    {
        using var mod = F4.Fallout4Mod.CreateFromBinaryOverlay(esm, F4.Fallout4Release.Fallout4);
        var c = Util.Cache(mod);
        var achrKey = new FormKey(mod.ModKey, achrId & 0xFFFFFF);
        if (!c.TryResolve<F4.IPlacedNpcGetter>(achrKey, out var achr)) { Console.Error.WriteLine($"no ACHR {achrId:X8}"); return 2; }
        if (!c.TryResolve<F4.INpcGetter>(achr.Base.FormKey, out var baseNpc)) { Console.Error.WriteLine("ACHR base is not an NPC_"); return 2; }

        // where it is placed: worldspace and cell (persistent refs sit in the world's persistent cell)
        string world = "", cell = "";
        foreach (var w in mod.Worldspaces)
        {
            bool Has(F4.ICellGetter ce) => ce.Persistent.Concat(ce.Temporary).Any(p => p.FormKey == achrKey);
            if (w.TopCell is { } top && Has(top)) { world = w.EditorID ?? ""; cell = $"{top.FormKey.ID:X8} (persistent)"; break; }
            var hit = w.SubCells.SelectMany(b => b.Items).SelectMany(s => s.Items).FirstOrDefault(Has);
            if (hit is not null) { world = w.EditorID ?? ""; cell = $"{hit.FormKey.ID:X8} {hit.EditorID}"; break; }
        }
        var pos = achr.Position;
        var cats = new Dictionary<string, object?>();
        var src = new Dictionary<string, F4.INpcGetter>();
        foreach (var (name, bit) in Categories)
        {
            var (s, hops) = Effective(c, baseNpc, name, bit, level);
            src[name] = s;
            cats[name] = new Dictionary<string, object?>
            {
                ["templated"] = ((int)baseNpc.UseTemplateActors & (1 << bit)) != 0,
                ["source"] = s.EditorID, ["source_id"] = Id(s.FormKey), ["hops"] = hops,
            };
        }

        // Field values, each read from the record its category resolves to. Which fields a category covers follows
        // the CK's template-data groups (supported hypothesis; FO4 and Starfield use the same 13 flags).
        F4.INpcGetter T = src["Traits"], St = src["Stats"], Fa = src["Factions"], Sp = src["SpellList"], Ai = src["AiData"],
            Pk = src["AiPackages"], Bd = src["BaseData"], Inv = src["Inventory"], Sc = src["Script"], Dp = src["DefPackList"],
            At = src["AttackData"], Kw = src["Keywords"];
        object? Lvl(F4.INpcGetter n) => n.Level switch
        {
            F4.INpcLevelGetter l => new Dictionary<string, object?> { ["level"] = (int)l.Level },
            F4.IPcLevelMultGetter m => new Dictionary<string, object?> { ["pc_level_mult"] = m.LevelMult },
            _ => null,
        };
        List<object> Items(F4.INpcGetter n) => (n.Items ?? new List<F4.IContainerEntryGetter>()).Select(e =>
        {
            var d = Ref(c, e.Item.Item.FormKey);
            d["count"] = e.Item.Count;
            // a leveled item list: its entries at the player level, one level deep (the weapon choice reads these)
            if (c.TryResolve<F4.ILeveledItemGetter>(e.Item.Item.FormKey, out var li) && li.Entries is not null)
                d["entries"] = li.Entries.Where(x => x.Data is not null).Select(x =>
                {
                    var r = Ref(c, x.Data!.Reference.FormKey);
                    r["level"] = (int)x.Data.Level; r["count"] = (int)x.Data.Count;
                    return (object)r;
                }).ToList();
            return (object)d;
        }).ToList();

        var fields = new Dictionary<string, object?>
        {
            ["name"] = Bd.Name?.String, ["short_name"] = Bd.ShortName?.String,
            ["flags"] = Bd.Flags.ToString().Split(", ").Where(x => x != "0").ToList(),
            ["level"] = Lvl(St), ["calc_min_level"] = (int)St.CalcMinLevel, ["calc_max_level"] = (int)St.CalcMaxLevel,
            ["xp_value_offset"] = (int)St.XpValueOffset, ["disposition_base"] = (int)St.DispositionBase,
            ["class"] = Ref(c, St.Class.FormKey),
            ["properties"] = (St.Properties ?? new List<F4.IObjectPropertyGetter>())
                .Select(p => (object)new Dictionary<string, object?> { ["av"] = Util.Edid(c, p.ActorValue.FormKey), ["value"] = p.Value }).ToList(),
            ["factions"] = Fa.Factions.Select(f =>
            {
                var d = Ref(c, f.Faction.FormKey); d["rank"] = (int)f.Rank; return (object)d;
            }).ToList(),
            ["crime_faction"] = Ref(c, Fa.CrimeFaction.FormKey),
            ["perks"] = (Sp.Perks ?? new List<F4.IPerkPlacementGetter>()).Select(p => (object)Ref(c, p.Perk.FormKey)).ToList(),
            ["ai"] = new Dictionary<string, object?>
            {
                ["aggression"] = Ai.Aggression.ToString(), ["confidence"] = Ai.Confidence.ToString(),
                ["energy_level"] = (int)Ai.EnergyLevel, ["responsibility"] = Ai.Responsibility.ToString(),
                ["mood"] = Ai.Mood.ToString(), ["assistance"] = Ai.Assistance.ToString(),
            },
            ["combat_style"] = Ref(c, Ai.CombatStyle.FormKey),
            ["packages"] = Pk.Packages.Select(p => (object)Ref(c, p.FormKey)).ToList(),
            ["race"] = Ref(c, T.Race.FormKey), ["female"] = T.Flags.HasFlag(F4.Npc.Flag.Female),
            ["voice"] = Ref(c, T.Voice.FormKey), ["height"] = new[] { T.HeightMin, T.HeightMax },
            ["head_parts"] = T.HeadParts.Count, ["skin"] = Ref(c, T.Skin.FormKey),
            ["items"] = Items(Inv), ["default_outfit"] = Ref(c, Inv.DefaultOutfit.FormKey),
            ["death_item"] = Ref(c, Inv.DeathItem.FormKey),
            ["scripts"] = Sc.VirtualMachineAdapter?.Scripts.Select(s => (object)s.Name).ToList() ?? new List<object>(),
            ["default_package_list"] = Ref(c, Dp.DefaultPackageList.FormKey),
            ["combat_override_package_list"] = Ref(c, Dp.CombatOverridePackageList.FormKey),
            ["attack_race"] = Ref(c, At.AttackRace.FormKey),
            ["keywords"] = (Kw.Keywords ?? new List<IFormLinkGetter<F4.IKeywordGetter>>()).Select(k => (object)Ref(c, k.FormKey)).ToList(),
        };
        var doc = new Dictionary<string, object?>
        {
            ["source"] = "Fallout4.esm", ["player_level"] = level,
            ["achr"] = new Dictionary<string, object?>
            {
                ["id"] = Id(achr.FormKey), ["edid"] = achr.EditorID, ["world"] = world, ["cell"] = cell,
                ["position"] = new[] { pos.X, pos.Y, pos.Z }, ["rotation"] = new[] { achr.Rotation.X, achr.Rotation.Y, achr.Rotation.Z },
                ["grid"] = new[] { (int)Math.Floor(pos.X / 4096f), (int)Math.Floor(pos.Y / 4096f) },
                ["level_modifier"] = achr.LevelModifier?.ToString(),
                ["location_ref_types"] = (achr.LocationRefTypes ?? new List<IFormLinkGetter<F4.ILocationReferenceTypeGetter>>())
                    .Select(x => (object)Util.Edid(c, x.FormKey)).ToList(),
            },
            ["base"] = new Dictionary<string, object?>
            {
                ["id"] = Id(baseNpc.FormKey), ["edid"] = baseNpc.EditorID, ["use_template_actors"] = (int)baseNpc.UseTemplateActors,
                ["default_template"] = Ref(c, baseNpc.DefaultTemplate.FormKey),
            },
            ["categories"] = cats, ["fields"] = fields,
        };
        File.WriteAllText(outPath, JsonSerializer.Serialize(doc, new JsonSerializerOptions { WriteIndented = true }));
        Console.WriteLine($"{achr.EditorID} ({achr.FormKey.ID:X8}) base {baseNpc.EditorID} ({baseNpc.FormKey.ID:X8}) in {world} {cell}: " +
                          $"traits from {T.EditorID}, stats/AI/inventory from {St.EditorID}/{Ai.EditorID}/{Inv.EditorID}, name {fields["name"]} -> {outPath}");
        return 0;
    }
}
