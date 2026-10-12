// write / check: Starfield NPC_ records from a mapped spec (scripts/actors/raider_map.py), and their re-read.
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
    // unresolved; in Starfield.esm they almost always share the behaviour categories' template, never Traits alone
    // (sf-tplstats: 961 / 847 records match the 10 behaviour categories; 6 / 26 point elsewhere).
    public static readonly (string Name, int Bit)[] Slots =
    {
        ("Traits", 0), ("Stats", 1), ("Factions", 2), ("SpellList", 3), ("AiData", 4), ("AiPackages", 5),
        ("ModelOrAnimation", 6), ("BaseData", 7), ("Inventory", 8), ("Script", 9), ("DefPackList", 10),
        ("AttackData", 11), ("Keywords", 12), ("Unknown1", 13), ("Unknown2", 14),
    };

    // Subrecords that every vanilla NPC_ carries (raw scan of Starfield.esm: 7,131 of 7,131 records, all 2,821 that
    // inherit Traits among them; EDID 7,130). Check reports a written record that lacks one.
    public static readonly string[] AlwaysPresent =
        { "EDID", "OBND", "ODTY", "ACBS", "RNAM", "PRPS", "AIDT", "DATA", "DNAM", "NAM5", "NAM6", "NAM4", "MWGT", "EDCT", "STON", "PRON" };

    // The record header form version of every vanilla NPC_ (581 in all 7,131). Mutagen writes 576 unless told; its
    // round trip of vanilla records keeps 581 and writes their subrecords back byte for byte, so it writes 581's layout.
    public const ushort VanillaNpcFormVersion = 581;

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

    /// One plugin with every NPC_ of the spec's "npcs" list (the conversion and its probe variants).
    public static int Write(string sfPath, string specPath, string outDir)
    {
        var spec = JsonDocument.Parse(File.ReadAllText(specPath)).RootElement;
        using var sf = StarfieldMod.CreateFromBinaryOverlay(sfPath, StarfieldRelease.Starfield);
        var c = Util.Cache(sf);
        var errors = new List<string>();
        var modKey = ModKey.FromNameAndExtension(spec.GetProperty("plugin").GetString()!);
        var mod = new StarfieldMod(modKey, StarfieldRelease.Starfield);
        mod.ModHeader.Flags |= StarfieldModHeader.HeaderFlag.Master;
        mod.ModHeader.Author = "fo4-to-starfield ActorRaider";
        uint next = 0x800;
        var lines = new List<string>();
        foreach (var n in spec.GetProperty("npcs").EnumerateArray())
        {
            var npc = Build(c, n, modKey, errors, out var bits);
            if (npc is null) return 2;
            if (mod.Npcs.ContainsKey(npc.FormKey)) { Console.Error.WriteLine($"form_id {npc.FormKey.ID:X6} used twice"); return 2; }
            mod.Npcs.Add(npc);
            next = Math.Max(next, npc.FormKey.ID + 1);
            lines.Add($"  NPC_ {npc.FormKey} {npc.EditorID} \"{npc.Name}\" ({n.GetProperty("role").GetString()}): template flags " +
                      $"0x{bits:X4}, {npc.Factions.Count} factions, {npc.Items?.Count ?? 0} items, {npc.Properties?.Count ?? 0} " +
                      $"properties, form version {npc.FormVersion}");
        }
        if (errors.Count > 0)
        {
            Console.Error.WriteLine("spec does not match Starfield.esm, nothing written:\n  " + string.Join("\n  ", errors));
            return 2;
        }
        mod.ModHeader.Stats.NextFormID = next;
        Directory.CreateDirectory(outDir);
        var path = Path.Combine(outDir, modKey.FileName);
        mod.BeginWrite.ToPath(path).WithLoadOrderFromHeaderMasters().WithDataFolder(Path.GetDirectoryName(Path.GetFullPath(sfPath))!)
            .WithKnownMasters(new KeyedMasterStyle(SfEsm, MasterStyle.Full)).Write();
        Console.WriteLine($"wrote {path} ({new FileInfo(path).Length:N0} bytes):\n" + string.Join("\n", lines));
        return 0;
    }

    /// One NPC_ from one entry of "npcs" (null: a form_id out of range, already reported).
    static Npc? Build(ILinkCache c, JsonElement n, ModKey modKey, List<string> errors, out int bits)
    {
        bits = 0;
        FormKey V(JsonElement e, string what) => Vanilla(c, e, what, errors);
        FormKey Opt(string key) => n.TryGetProperty(key, out var e) && e.ValueKind == JsonValueKind.Object ? V(e, key) : FormKey.Null;
        var localId = Convert.ToUInt32(n.GetProperty("form_id").GetString(), 16);
        if (localId < 0x800 || localId > 0xFFFFFF) { Console.Error.WriteLine($"form_id {localId:X} outside 000800..FFFFFF"); return null; }

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
            FormVersion = (ushort)n.GetProperty("form_version").GetInt32(),
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
        // an optional link the spec does not give stays unset: SetTo(FormKey.Null) would write a null subrecord (the
        // calm probe's HEFA was 00000000; no vanilla NPC_ has a null HEFA, 29 have one)
        void Set<T>(IFormLinkNullable<T> link, FormKey fk) where T : class, IMajorRecordGetter
        {
            if (!fk.IsNull) link.SetTo(fk);
        }
        Set(npc.DefaultOutfit, Opt("default_outfit"));
        Set(npc.SpaceOutfit, Opt("space_outfit"));
        Set(npc.DeathItem, Opt("death_item"));
        Set(npc.CombatStyle, Opt("combat_style"));
        Set(npc.DefaultPackageList, Opt("default_package_list"));
        Set(npc.CombatOverridePackageList, Opt("combat_override_package_list"));
        Set(npc.FormationFaction, Opt("formation_faction"));
        Set(npc.Class, Opt("class"));
        Set(npc.Voice, Opt("voice"));

        // PRPS, STON, PRON and EDCT are in every vanilla NPC_, also in those that inherit the category. Vanilla templated
        // records carry their template's values: PRPS equals the Stats template's in 2,692 of 4,046 Stats-templated
        // NPC_ whose Stats template is an NPC_; STON / PRON / EDCT equal the Traits template's in 2,287 / 2,317 / 2,274
        // of 2,318. So PRPS, STON and PRON are copied from the template of the category the spec names ("copied"). EDCT
        // counts the tint blocks (MNAM TNAM QNAM VNAM NNAM INTV; it equals the number of MNAM in all 7,131 NPC_), which
        // Mutagen writes from Tints: an empty, non-null list writes EDCT 0 and no block, as in EncSpacer01Template and
        // 4,110 other vanilla NPC_ (the look comes from the Traits template; its tints are not copied).
        var copied = n.GetProperty("copied");
        INpcGetter? Tpl(string what)
        {
            var cat = copied.GetProperty(what).GetString()!;
            var fk = SlotLink(npc.TemplateActors, cat);
            if (fk.IsNull) fk = npc.DefaultTemplate.FormKey;
            if (c.TryResolve<INpcGetter>(fk, out var t)) return t;
            errors.Add($"copied.{what}: the {cat} template {fk} is not an NPC_ (a leveled list has no values to copy)");
            return null;
        }
        if (Tpl("properties") is { } st)
            npc.Properties = st.Properties?.Select(p => p.DeepCopy()).ToExtendedList() ?? new ExtendedList<ObjectProperty>();
        if (Tpl("skin_tone_index") is { } tr) npc.SkinToneIndex = tr.SkinToneIndex ?? 0;
        if (Tpl("pronoun") is { } pr) npc.Pronoun = pr.Pronoun ?? default;
        npc.Tints = new ExtendedList<NpcTint>();
        return npc;
    }

    /// Re-read the plugin, resolve every link and every inherited category against Starfield.esm, and compare the raw
    /// record with what every vanilla NPC_ carries (subrecord types, form version).
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
        var raw = Roundtrip.ReadGroup(pluginPath, "NPC_", null);
        var versions = Roundtrip.FormVersions(pluginPath, "NPC_");
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
                    if (name == "Traits") { d["race"] = R(t.Race.FormKey, "traits race").GetValueOrDefault("edid"); d["voice"] = R(t.Voice.FormKey, "traits voice").GetValueOrDefault("edid"); d["female"] = t.Flags.HasFlag(Npc.Flag.Female); d["head_parts"] = t.HeadParts.Count; d["death_item"] = R(t.DeathItem.FormKey, "traits death item").GetValueOrDefault("edid"); }
                    if (name == "AiData") { d["aggression"] = t.Aggression.ToString(); d["confidence"] = t.Confidence.ToString(); d["assistance"] = t.Assistance.ToString(); d["reaction_radii"] = t.RDSAs?.Count ?? 0; d["combat_style"] = R(t.CombatStyle.FormKey, "ai data combat style").GetValueOrDefault("edid"); }
                    if (name == "Stats") { d["level"] = t.Level is INpcLevelGetter l ? l.Level : null; d["class"] = R(t.Class.FormKey, "stats class").GetValueOrDefault("edid"); }
                    if (name == "DefPackList") d["default_package_list"] = R(t.DefaultPackageList.FormKey, "template package list").GetValueOrDefault("edid");
                }
                else if (c.TryResolve<ILeveledNpcGetter>(fk, out _)) d["template_is_leveled_list"] = true;
                inherited[name] = d;
            }
            var subs = raw.TryGetValue(n.FormKey.ID, out var data) ? Roundtrip.Subrecords(data).Select(s => s.Type).ToList() : new List<string>();
            var missing = AlwaysPresent.Where(s => !subs.Contains(s)).ToList();
            if (missing.Count > 0) problems.Add($"{n.EditorID}: lacks {string.Join(", ", missing)}, which every vanilla NPC_ carries");
            var fv = versions.GetValueOrDefault(n.FormKey.ID);
            if (fv != VanillaNpcFormVersion) problems.Add($"{n.EditorID}: form version {fv}, every vanilla NPC_ has {VanillaNpcFormVersion}");
            npcs.Add(new Dictionary<string, object?>
            {
                ["form_key"] = n.FormKey.ToString(), ["editor_id"] = n.EditorID, ["name"] = n.Name?.String,
                ["runtime_id_if_first_plugin"] = $"02{n.FormKey.ID:X6}",
                ["form_version"] = fv, ["subrecords"] = string.Join(" ", subs),
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
                    ["properties"] = n.Properties?.Count ?? 0, ["skin_tone_index"] = n.SkinToneIndex, ["pronoun"] = n.Pronoun?.ToString(),
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
