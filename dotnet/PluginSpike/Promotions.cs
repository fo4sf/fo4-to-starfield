// Interior promotions (docs/terrain/port-promotions.md): <output dir>/promote.json, written by
// scripts/terrain/port_promote.py from the cell exports. FO4 containers, loose inventory items, activators and terminals
// placed in the converted interiors leave the STAT / MSTT placement and get a native base of their kind, as the exterior
// core's (dotnet/TerrainOverlays, make_cluster.py): one CONT / MISC / ACTI / TERM (+ its TMLM) per edid with the model
// the reference would otherwise have, and the reference keeps its stable REFR FormID. Keys in formids.json:
//   CONT:<edid>   MISC:<edid>   ACTI:<edid>   TERM:<edid>   TMLM:<menu edid>
// File shape: {"starfield_esm": <path or null: needed only with terminals>, "containers": [{"src", "edid", "name",
// "items": [{"form": "Starfield.esm:00000F", "count": 10}]}], "items": [{"src", "edid", "name", "value", "weight"}],
// "activators": [{"src", "edid", "name" (null: no FULL)}], "terminals": [{"src", "edid", "menu_edid", "name", "body"}],
// "furniture": [{"src", "edid", "name", "template": "<6 hex FURN of Starfield.esm>", "markers": [{"offset": [x, y, z]
// metres, "rotation_z": degrees}] or null (the template's own)}]}. FURN:<edid> keys. A chair is a copy of the vanilla
// template FURN (furniture template, marker model, keywords, entry points, animation graph, angles) with our model, the
// FO4 name and FO4's marker places; its script (VMAD) is not copied.
// Every entry of one edid must agree on everything but "src" and on the model (one shared record carries one value).
// A reference on its own posed model or on a DOOR base is never promoted (the caller keeps its base and counts it).
using System.Text.Json;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Starfield;
using Noggog;
using StarfieldActivator = Mutagen.Bethesda.Starfield.Activator;   // not System.Activator (implicit usings)

public sealed class Promotions : IDisposable
{
    public static readonly string[] Kinds = { "containers", "items", "activators", "terminals", "furniture" };
    readonly JsonDocument? doc;
    readonly Dictionary<string, (string Kind, JsonElement Entry)> bySrc = new();
    readonly Dictionary<string, (FormKey Key, string Sig)> byEdid = new(StringComparer.OrdinalIgnoreCase);
    readonly HashSet<string> menuEdids = new(StringComparer.OrdinalIgnoreCase);
    readonly string? starfieldEsm;
    IStarfieldModDisposableGetter? sf;
    ITerminalGetter? termTemplate;
    public readonly SortedDictionary<string, int> Counts = new();
    public readonly HashSet<FormKey> UsableBases = new();   // promoted ACTI / TERM bases: parents an activation chain can start from

    public Promotions(string path)
    {
        if (!File.Exists(path)) return;
        doc = JsonDocument.Parse(File.ReadAllText(path));
        var root = doc.RootElement;
        if (root.TryGetProperty("starfield_esm", out var se) && se.ValueKind == JsonValueKind.String) starfieldEsm = se.GetString();
        foreach (var kind in Kinds)
        {
            if (!root.TryGetProperty(kind, out var list)) continue;
            foreach (var e in list.EnumerateArray())
            {
                var src = e.GetProperty("src").GetString() ?? throw new InvalidDataException($"promote.json {kind}: an entry without src");
                if (!bySrc.TryAdd(src, (kind, e)))
                    throw new InvalidDataException($"promote.json: {src} is listed twice ({bySrc[src].Kind} and {kind})");
            }
        }
    }

    public int Listed => bySrc.Count;
    public bool Has(string src) => bySrc.ContainsKey(src);
    void Count(string what) => Counts[what] = Counts.GetValueOrDefault(what) + 1;
    public void Kept(string src, string why) { if (Has(src)) Count($"kept ({why})"); }

    static string Sig(JsonElement e, string model) =>
        model.ToLowerInvariant() + "|" + string.Join(",", e.EnumerateObject().Where(p => p.Name != "src").Select(p => p.Name + "=" + p.Value.GetRawText()));

    static string? OneLine(JsonElement e, string k, bool optional)
    {
        var v = e.GetProperty(k);
        if (optional && v.ValueKind == JsonValueKind.Null) return null;
        var t = v.GetString();
        if (string.IsNullOrWhiteSpace(t) || t.Contains('\n') || t.Contains('\r'))
            throw new InvalidDataException($"promote.json {e.GetProperty("src").GetString()}: {k} {v} is not one non-empty line");
        return t;
    }

    static MemorySlice<byte>? Bytes(ReadOnlyMemorySlice<byte>? s) => s is { } v ? new MemorySlice<byte>(v.ToArray()) : default(MemorySlice<byte>?);

    // The furniture block of a vanilla standing terminal (OE_AustinF_DeployMicrobe_Terminal 0155A2:Starfield.esm), as
    // TerrainOverlays gives its terminals: every vanilla TERM is also furniture (review of #241).
    static void Furnish(Terminal term, ITerminalGetter t)
    {
        term.FurnitureTemplate.SetTo(t.FurnitureTemplate.FormKeyNullable);
        term.MarkerModel = t.MarkerModel;
        term.MarkerParameters = t.MarkerParameters?.Select(p => p.DeepCopy()).ToExtendedList();
        term.MarkerFlags = t.MarkerFlags;
        term.WorkbenchData = Bytes(t.WorkbenchData);
        term.PNAM = Bytes(t.PNAM); term.FNAM = Bytes(t.FNAM); term.JNAM = Bytes(t.JNAM); term.GNAM = Bytes(t.GNAM);
        term.Keywords = t.Keywords?.Select(k => (IFormLinkGetter<IKeywordGetter>)new FormLink<IKeywordGetter>(k.FormKey)).ToExtendedList();
        foreach (var g in t.Components.OfType<IAnimationGraphComponentGetter>()) term.Components.Add(g.DeepCopy());
    }

    IStarfieldModDisposableGetter Master(StarfieldRelease release, string what)
    {
        if (sf != null) return sf;
        if (string.IsNullOrEmpty(starfieldEsm) || !File.Exists(starfieldEsm))
            throw new InvalidDataException($"promote.json lists {what} but starfield_esm ({starfieldEsm ?? "null"}) is not a file: their furniture block comes from Starfield.esm");
        return sf = StarfieldMod.CreateFromBinaryOverlay(starfieldEsm, release);
    }

    ITerminalGetter TerminalTemplate(StarfieldRelease release)
    {
        if (termTemplate != null) return termTemplate;
        var sfEsm = ModKey.FromNameAndExtension("Starfield.esm");
        return termTemplate = Master(release, "terminals").Terminals.FirstOrDefault(t => t.FormKey == new FormKey(sfEsm, 0x0155A2))
            ?? throw new InvalidDataException("terminals: the template terminal 0155A2:Starfield.esm (OE_AustinF_DeployMicrobe_Terminal) is missing");
    }

    readonly Dictionary<uint, IFurnitureGetter> furnTemplates = new();
    IFurnitureGetter FurnitureTemplate(string hex, StarfieldRelease release)
    {
        var id = Convert.ToUInt32(hex, 16);
        if (furnTemplates.TryGetValue(id, out var t)) return t;
        var sfEsm = ModKey.FromNameAndExtension("Starfield.esm");
        t = Master(release, "furniture").Furniture.FirstOrDefault(f => f.FormKey == new FormKey(sfEsm, id))
            ?? throw new InvalidDataException($"furniture: the template {hex}:Starfield.esm is not a FURN of the master");
        if ((t.BenchType ?? Furniture.BenchTypes.None) != Furniture.BenchTypes.None)
            throw new InvalidDataException($"furniture: the template {hex} ({t.EditorID}) is a crafting bench, not a seat");
        if ((t.MarkerParameters?.Count ?? 0) == 0)
            throw new InvalidDataException($"furniture: the template {hex} ({t.EditorID}) has no marker to copy");
        return furnTemplates[id] = t;
    }

    /// The promoted base of a listed reference whose own base would carry `model`; shared per edid.
    public FormKey Base(string src, string model, StarfieldMod mod, Func<string, FormKey> id, StarfieldRelease release)
    {
        var (kind, e) = bySrc[src];
        var edid = e.GetProperty("edid").GetString()!;
        var sig = kind + "|" + Sig(e, model);
        if (byEdid.TryGetValue(edid, out var known))
        {
            if (known.Sig != sig)
                throw new InvalidDataException($"promote.json {edid}: {src} asks for {sig} but the shared record is {known.Sig}");
            Count(kind);
            return known.Key;
        }
        FormKey key;
        switch (kind)
        {
            case "containers":
            {
                var cont = new Container(id("CONT:" + edid), release)
                {
                    EditorID = edid, Model = new Model { File = model }, Name = OneLine(e, "name", optional: false),
                    Items = new ExtendedList<ContainerEntry>(),                   // null by default in Mutagen 0.55
                };
                foreach (var it in e.GetProperty("items").EnumerateArray())
                {
                    var form = it.GetProperty("form").GetString()!;               // "<plugin>:<6 hex>"
                    var colon = form.IndexOf(':');
                    if (colon < 1) throw new InvalidDataException($"promote.json {src}: item form '{form}' is not <plugin>:<hex>");
                    var fk = new FormKey(ModKey.FromNameAndExtension(form[..colon]), Convert.ToUInt32(form[(colon + 1)..], 16));
                    var count = it.GetProperty("count").GetInt32();
                    if (count < 1) throw new InvalidDataException($"promote.json {src}: count {count} for {form}");
                    cont.Items.Add(new ContainerEntry { Item = new ContainerItem { Item = new FormLink<IItemGetter>(fk), Count = count } });
                }
                mod.Containers.Add(cont);
                key = cont.FormKey;
                break;
            }
            case "items":
            {
                var name = OneLine(e, "name", optional: false);
                int value = e.GetProperty("value").GetInt32();
                float weight = e.GetProperty("weight").GetSingle();
                if (value < 0 || !float.IsFinite(weight) || weight < 0)
                    throw new InvalidDataException($"promote.json {src}: needs a value >= 0 and a weight >= 0");
                var misc = new MiscItem(id("MISC:" + edid), release)
                    { EditorID = edid, Model = new Model { File = model }, Name = name, Value = value, Weight = weight };
                mod.MiscItems.Add(misc);
                key = misc.FormKey;
                break;
            }
            case "activators":
            {
                // PNAM / FNAM / JNAM as the vanilla majority, as TerrainOverlays writes its activators (review of #241)
                var acti = new StarfieldActivator(id("ACTI:" + edid), release)
                {
                    EditorID = edid, Model = new Model { File = model }, MarkerColor = System.Drawing.Color.FromArgb(0, 0xCC, 0x4C, 0x33),
                    Flags = (StarfieldActivator.Flag)0, ActivationAngle = 360,
                };
                if (OneLine(e, "name", optional: true) is string n) acti.Name = n;
                mod.Activators.Add(acti);
                key = acti.FormKey;
                break;
            }
            case "terminals":
            {
                var menuEdid = e.GetProperty("menu_edid").GetString()!;
                if (!menuEdids.Add(menuEdid))
                    throw new InvalidDataException($"promote.json terminal {edid}: menu {menuEdid} already belongs to another terminal");
                var name = OneLine(e, "name", optional: false)!;
                var body = OneLine(e, "body", optional: false)!;
                var template = TerminalTemplate(release);
                var term = new Terminal(id("TERM:" + edid), release)
                {
                    EditorID = edid, Model = new Model { File = model }, Name = name, Background = Terminal.BackgroundType.Default,
                };
                Furnish(term, template);
                // the TMLM mirrors vanilla RI04_NyxProgram_Menu_Camden (0788A8), as TerrainOverlays' terminal menus
                var menu = new TerminalMenu(id("TMLM:" + menuEdid), release)
                {
                    EditorID = menuEdid, Name = name, INAM = string.Empty,
                    ShowBodyText = TerminalMenu.ShowBodyTextOption.Document,
                    MenuButtonStyle = (TerminalMenu.MenuButtonStyleOption)0,
                    Style = TerminalMenu.StyleOption.Windows,
                    BodyTexts = new ExtendedList<TerminalMenuBodyText> { new TerminalMenuBodyText { Text = body, UseTemplatedText = false } },
                    MenuItems = new ExtendedList<TerminalMenuItem>(),
                };
                term.Menu.SetTo(menu.FormKey);
                mod.Terminals.Add(term);
                mod.TerminalMenus.Add(menu);
                key = term.FormKey;
                break;
            }
            case "furniture":
            {
                var template = FurnitureTemplate(e.GetProperty("template").GetString()!, release);
                var furn = (Furniture)template.Duplicate(id("FURN:" + edid));
                furn.EditorID = edid;
                furn.Model = new Model { File = model };
                furn.Name = OneLine(e, "name", optional: false);
                furn.VirtualMachineAdapter = null;
                if (e.GetProperty("markers") is { ValueKind: JsonValueKind.Array } marks && marks.GetArrayLength() > 0)
                {
                    var first = template.MarkerParameters![0];
                    var entry = template.MarkerEntryPoints?.FirstOrDefault();
                    furn.MarkerParameters = new Noggog.ExtendedList<FurnitureMarkerParameters>();
                    if (entry != null) furn.MarkerEntryPoints.Clear();          // one entry block per marker, as copied
                    foreach (var m in marks.EnumerateArray())
                    {
                        var o = m.GetProperty("offset");
                        var p = first.DeepCopy();
                        p.Offset = new Noggog.P3Float(o[0].GetSingle(), o[1].GetSingle(), o[2].GetSingle());
                        p.RotationZ = m.GetProperty("rotation_z").GetSingle();
                        furn.MarkerParameters.Add(p);
                        if (entry != null) furn.MarkerEntryPoints.Add(entry.DeepCopy());
                    }
                }
                mod.Furniture.Add(furn);
                key = furn.FormKey;
                break;
            }
            default: throw new InvalidDataException($"promote.json: unknown kind {kind}");
        }
        byEdid[edid] = (key, sig);
        if (kind is "activators" or "terminals") UsableBases.Add(key);
        Count(kind);
        return key;
    }

    public void Dispose()
    {
        sf?.Dispose();
        doc?.Dispose();
    }
}
