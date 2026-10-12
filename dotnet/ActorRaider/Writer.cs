// write / check: one Starfield NPC_ from a mapped spec (scripts/actors/raider_map.py), and its re-read.
using System.Text.Json;
using Mutagen.Bethesda;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Cache;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Noggog;

static class Writer
{
    // TPTA slots in ACBS template-flag order. Starfield has 15: Mutagen 0.55.0-alpha.67 names 13 of them and calls the
    // last two Unknown1 / Unknown2 (flag bits 13, 14 have no name in Npc.TemplateActorType either). Their meaning is
    // unresolved; in Starfield.esm they follow the behaviour template, never Traits alone (sf-tplstats).
    public static readonly (string Name, int Bit)[] Slots =
    {
        ("Traits", 0), ("Stats", 1), ("Factions", 2), ("SpellList", 3), ("AiData", 4), ("AiPackages", 5),
        ("ModelOrAnimation", 6), ("BaseData", 7), ("Inventory", 8), ("Script", 9), ("DefPackList", 10),
        ("AttackData", 11), ("Keywords", 12), ("Unknown1", 13), ("Unknown2", 14),
    };

    static IFormLink<INpcTemplateTargetGetter> SlotRef(TemplateActors t, string name) => name switch
    {
        "Traits" => t.TraitTemplate, "Stats" => t.StatsTemplate, "Factions" => t.FactionsTemplate,
        "SpellList" => t.SpellListTemplate, "AiData" => t.AiDataTemplate, "AiPackages" => t.AiPackagesTemplate,
        "ModelOrAnimation" => t.ModelOrAnimationTemplate, "BaseData" => t.BaseDataTemplate,
        "Inventory" => t.InventoryTemplate, "Script" => t.ScriptTemplate, "DefPackList" => t.DefPackListTemplate,
        "AttackData" => t.AttackDataTemplate, "Keywords" => t.KeywordsTemplate, "Unknown1" => t.Unknown1,
        "Unknown2" => t.Unknown2, _ => throw new ArgumentException($"unknown template slot {name}"),
    };

    public static FormKey SlotLink(ITemplateActorsGetter t, string name) => name switch
    {
        "Traits" => t.TraitTemplate.FormKey, "Stats" => t.StatsTemplate.FormKey, "Factions" => t.FactionsTemplate.FormKey,
        "SpellList" => t.SpellListTemplate.FormKey, "AiData" => t.AiDataTemplate.FormKey,
        "AiPackages" => t.AiPackagesTemplate.FormKey, "ModelOrAnimation" => t.ModelOrAnimationTemplate.FormKey,
        "BaseData" => t.BaseDataTemplate.FormKey, "Inventory" => t.InventoryTemplate.FormKey,
        "Script" => t.ScriptTemplate.FormKey, "DefPackList" => t.DefPackListTemplate.FormKey,
        "AttackData" => t.AttackDataTemplate.FormKey, "Keywords" => t.KeywordsTemplate.FormKey,
        "Unknown1" => t.Unknown1.FormKey, "Unknown2" => t.Unknown2.FormKey, _ => FormKey.Null,
    };

    static readonly ModKey SfEsm = ModKey.FromNameAndExtension("Starfield.esm");

    /// A vanilla link of the spec: {"id": "0027BB8C", "edid": "SpacerFaction", "type": "Faction"}. It must be a
    /// Starfield.esm record (load index 00) whose EditorID and record type match, else an error is recorded.
    static FormKey Vanilla(ILinkCache c, JsonElement r, string what, List<string> errors)
    {
        var id = Convert.ToUInt32(r.GetProperty("id").GetString(), 16);
        var edid = r.GetProperty("edid").GetString();
        var type = r.GetProperty("type").GetString();
        if (id >> 24 != 0) { errors.Add($"{what}: {id:X8} is not a Starfield.esm FormID"); return FormKey.Null; }
        var fk = new FormKey(SfEsm, id);
        if (!c.TryResolve<IMajorRecordGetter>(fk, out var rec)) { errors.Add($"{what}: {id:X8} not in Starfield.esm"); return FormKey.Null; }
        var got = Util.RecType(rec);
        if (rec.EditorID != edid || got != type)
            errors.Add($"{what}: {id:X8} is {got} {rec.EditorID}, the spec says {type} {edid}");
        return fk;
    }

    public static int Write(string sfPath, string specPath, string outDir)
    {
        var spec = JsonDocument.Parse(File.ReadAllText(specPath)).RootElement;
        var n = spec.GetProperty("npc");
        using var sf = StarfieldMod.CreateFromBinaryOverlay(sfPath, StarfieldRelease.Starfield);
        var c = Util.Cache(sf);
        var errors = new List<string>();
        FormKey V(JsonElement e, string what) => Vanilla(c, e, what, errors);
        FormKey Opt(string key) => n.TryGetProperty(key, out var e) && e.ValueKind == JsonValueKind.Object ? V(e, key) : FormKey.Null;

        var modKey = ModKey.FromNameAndExtension(spec.GetProperty("plugin").GetString()!);
        var mod = new StarfieldMod(modKey, StarfieldRelease.Starfield);
        mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        mod.ModHeader.Author = "fo4-to-starfield ActorRaider";
        var localId = Convert.ToUInt32(n.GetProperty("form_id").GetString(), 16);
        if (localId < 0x800 || localId > 0xFFFFFF) { Console.Error.WriteLine($"form_id {localId:X} outside 000800..FFFFFF"); return 2; }

        var npc = new Npc(new FormKey(modKey, localId), StarfieldRelease.Starfield)
        {
            EditorID = n.GetProperty("editor_id").GetString(),
            Name = n.GetProperty("name").GetString(),
            Level = new NpcLevel { Level = (short)n.GetProperty("level").GetInt32() },
            XpValueOffset = (short)n.GetProperty("xp_value_offset").GetInt32(),
            DispositionBase = (short)n.GetProperty("disposition_base").GetInt32(),
            HeightMin = n.GetProperty("height")[0].GetSingle(),
            HeightMax = n.GetProperty("height")[1].GetSingle(),
            GearedUpWeapons = (byte)n.GetProperty("geared_up_weapons").GetInt32(),
            Unused = (byte)n.GetProperty("unused").GetInt32(),
            NAM5 = new MemorySlice<byte>(Convert.FromHexString(n.GetProperty("nam5").GetString()!)),
            Weight = new NpcWeight(),
        };
        foreach (var f in n.GetProperty("flags").EnumerateArray())
            npc.Flags |= Enum.Parse<Npc.Flag>(f.GetString()!);
        var b = n.GetProperty("object_bounds");
        npc.ObjectBounds = new ObjectBounds
        {
            First = new P3Float(b[0][0].GetSingle(), b[0][1].GetSingle(), b[0][2].GetSingle()),
            Second = new P3Float(b[1][0].GetSingle(), b[1][1].GetSingle(), b[1][2].GetSingle()),
        };
        npc.Race.SetTo(V(n.GetProperty("race"), "race"));

        // templates: the default one plus a slot per category; the flags say which categories are inherited
        npc.DefaultTemplate.SetTo(V(n.GetProperty("default_template"), "default_template"));
        npc.TemplateActors = new TemplateActors();
        foreach (var t in n.GetProperty("templates").EnumerateObject())
            SlotRef(npc.TemplateActors, t.Name).SetTo(V(t.Value, $"templates.{t.Name}"));
        int bits = 0;
        foreach (var u in n.GetProperty("use_template").EnumerateArray())
        {
            var s = Slots.FirstOrDefault(x => x.Name == u.GetString());
            if (s.Name is null) { errors.Add($"use_template: unknown category {u.GetString()}"); continue; }
            bits |= 1 << s.Bit;
        }
        npc.UseTemplateActors = (Npc.TemplateActorType)bits;

        foreach (var f in n.GetProperty("factions").EnumerateArray())
            npc.Factions.Add(new RankPlacement
            {
                Faction = new FormLink<IFactionGetter>(V(f.GetProperty("faction"), "factions")),
                Rank = (sbyte)f.GetProperty("rank").GetInt32(),
            });
        npc.Items = new ExtendedList<ContainerEntry>();
        foreach (var it in n.GetProperty("items").EnumerateArray())
            npc.Items.Add(new ContainerEntry
            {
                Item = new ContainerItem { Item = new FormLink<IItemGetter>(V(it.GetProperty("item"), "items")), Count = it.GetProperty("count").GetInt32() },
            });
        npc.DefaultOutfit.SetTo(Opt("default_outfit"));
        npc.SpaceOutfit.SetTo(Opt("space_outfit"));
        npc.DeathItem.SetTo(Opt("death_item"));
        npc.CombatStyle.SetTo(Opt("combat_style"));
        npc.DefaultPackageList.SetTo(Opt("default_package_list"));
        npc.CombatOverridePackageList.SetTo(Opt("combat_override_package_list"));
        npc.FormationFaction.SetTo(Opt("formation_faction"));
        npc.Class.SetTo(Opt("class"));
        npc.Voice.SetTo(Opt("voice"));

        if (errors.Count > 0)
        {
            Console.Error.WriteLine("spec does not match Starfield.esm, nothing written:\n  " + string.Join("\n  ", errors));
            return 2;
        }
        mod.Npcs.Add(npc);
        mod.ModHeader.Stats.NextFormID = localId + 1;
        Directory.CreateDirectory(outDir);
        var path = Path.Combine(outDir, modKey.FileName);
        mod.BeginWrite.ToPath(path).WithLoadOrderFromHeaderMasters().WithDataFolder(Path.GetDirectoryName(Path.GetFullPath(sfPath))!)
            .WithKnownMasters(new KeyedMasterStyle(SfEsm, MasterStyle.Full)).Write();
        Console.WriteLine($"wrote {path} ({new FileInfo(path).Length:N0} bytes): NPC_ {npc.FormKey} {npc.EditorID} \"{npc.Name}\", " +
                          $"template flags 0x{bits:X4}, {npc.Factions.Count} factions, {npc.Items.Count} items");
        return 0;
    }

    /// Re-read the plugin, resolve every link and every inherited category against Starfield.esm.
    public static int Check(string sfPath, string pluginPath, string outPath)
    {
        using var sf = StarfieldMod.CreateFromBinaryOverlay(sfPath, StarfieldRelease.Starfield);
        // the plugin's only master is Starfield.esm, a full master (unknown masters get no guessed style)
        var masterStyles = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey);
        masterStyles.Set(new KeyedMasterStyle(SfEsm, MasterStyle.Full));
        using var plug = StarfieldMod.CreateFromBinaryOverlay(pluginPath, StarfieldRelease.Starfield,
            new BinaryReadParameters { MasterFlagsLookup = masterStyles });
        var c = Util.Cache(sf);
        var problems = new List<string>();
        Dictionary<string, object?> R(FormKey fk, string what)
        {
            var d = new Dictionary<string, object?> { ["id"] = fk.IsNull ? "" : $"{fk.ID:X8}" };
            if (fk.IsNull) return d;
            if (fk.ModKey != SfEsm) problems.Add($"{what}: links to {fk.ModKey}, not Starfield.esm");
            if (c.TryResolve<IMajorRecordGetter>(fk, out var r)) { d["edid"] = r.EditorID; d["type"] = Util.RecType(r); }
            else problems.Add($"{what}: {fk} does not resolve");
            return d;
        }
        var counts = plug.EnumerateMajorRecords().GroupBy(Util.RecType).ToDictionary(g => g.Key, g => g.Count());
        var npcs = new List<object>();
        foreach (var n in plug.Npcs)
        {
            int bits = (int)n.UseTemplateActors;
            var inherited = new Dictionary<string, object?>();
            foreach (var (name, bit) in Slots)
            {
                if ((bits & (1 << bit)) == 0) continue;
                var fk = n.TemplateActors is { } ta ? SlotLink(ta, name) : FormKey.Null;
                if (fk.IsNull) fk = n.DefaultTemplate.FormKey;
                var d = R(fk, $"template {name}");
                if (c.TryResolve<INpcGetter>(fk, out var t))
                {
                    if (t.UseTemplateActors != 0 && (((int)t.UseTemplateActors >> bit) & 1) != 0)
                        d["note"] = "the template inherits this category itself";
                    d["template_is_leveled_list"] = false;
                    if (name == "Traits") { d["race"] = R(t.Race.FormKey, "traits race")["edid"]; d["voice"] = R(t.Voice.FormKey, "traits voice")["edid"]; d["female"] = t.Flags.HasFlag(Npc.Flag.Female); d["head_parts"] = t.HeadParts.Count; }
                    if (name == "AiData") { d["aggression"] = t.Aggression.ToString(); d["confidence"] = t.Confidence.ToString(); d["assistance"] = t.Assistance.ToString(); d["reaction_radii"] = t.RDSAs?.Count ?? 0; }
                    if (name == "Stats") { d["level"] = t.Level is INpcLevelGetter l ? l.Level : null; d["class"] = R(t.Class.FormKey, "stats class")["edid"]; }
                    if (name == "DefPackList") d["default_package_list"] = R(t.DefaultPackageList.FormKey, "template package list")["edid"];
                }
                else if (c.TryResolve<ILeveledNpcGetter>(fk, out _)) d["template_is_leveled_list"] = true;
                inherited[name] = d;
            }
            npcs.Add(new Dictionary<string, object?>
            {
                ["form_key"] = n.FormKey.ToString(), ["editor_id"] = n.EditorID, ["name"] = n.Name?.String,
                ["runtime_id_if_first_plugin"] = $"02{n.FormKey.ID:X6}",
                ["flags"] = n.Flags.ToString(), ["level"] = n.Level is INpcLevelGetter lv ? lv.Level : null,
                ["race"] = R(n.Race.FormKey, "race"), ["default_template"] = R(n.DefaultTemplate.FormKey, "default template"),
                ["use_template_actors"] = $"0x{bits:X4}",
                ["inherited"] = inherited,
                ["own"] = new Dictionary<string, object?>
                {
                    ["factions"] = n.Factions.Select(f => (object)new Dictionary<string, object?> { ["faction"] = R(f.Faction.FormKey, "faction"), ["rank"] = (int)f.Rank }).ToList(),
                    ["items"] = (n.Items ?? new List<IContainerEntryGetter>()).Select(i => (object)new Dictionary<string, object?> { ["item"] = R(i.Item.Item.FormKey, "item"), ["count"] = i.Item.Count }).ToList(),
                    ["default_outfit"] = R(n.DefaultOutfit.FormKey, "default outfit"), ["space_outfit"] = R(n.SpaceOutfit.FormKey, "space outfit"),
                    ["death_item"] = R(n.DeathItem.FormKey, "death item"), ["combat_style"] = R(n.CombatStyle.FormKey, "combat style"),
                    ["formation_faction"] = R(n.FormationFaction.FormKey, "formation faction"),
                },
            });
        }
        var doc = new Dictionary<string, object?>
        {
            ["plugin"] = Path.GetFileName(pluginPath), ["bytes"] = new FileInfo(pluginPath).Length,
            ["master"] = plug.ModHeader.Flags.HasFlag(StarfieldModHeader.HeaderFlag.Master),
            ["masters"] = plug.ModHeader.MasterReferences.Select(m => (object)m.Master.FileName.String).ToList(),
            ["records"] = counts, ["npcs"] = npcs, ["problems"] = problems,
        };
        File.WriteAllText(outPath, JsonSerializer.Serialize(doc, new JsonSerializerOptions { WriteIndented = true }));
        Console.WriteLine($"{Path.GetFileName(pluginPath)}: masters [{string.Join(", ", (List<object>)doc["masters"]!)}], records " +
                          $"{string.Join(", ", counts.Select(k => $"{k.Key} {k.Value}"))}, {problems.Count} problems -> {outPath}");
        foreach (var p in problems) Console.WriteLine("  " + p);
        return problems.Count == 0 ? 0 : 3;
    }
}
