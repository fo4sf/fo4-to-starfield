// Inspect Starfield.esm: interior cells and their lighting templates, light records.
//   dotnet run -- <Starfield.esm> cells <substr>     interior cells (EditorID contains substr) + lighting template
//   dotnet run -- <Starfield.esm> lights <substr>    LIGH records (EditorID contains substr) + radius/colour
//   dotnet run -- <Starfield.esm> templates          lighting templates in use by interior cells (most used first)
//   dotnet run -- <Starfield.esm> navm <substr|*>     NAVM count per worldspace (+ interior total)
//   dotnet run -- <Starfield.esm> npcfind <substr>   NPC_ by EditorID or race EditorID
//   dotnet run -- <Starfield.esm> npc <hex,hex>      all fields of NPC_ records (verifies the FormIDs exist)
//   dotnet run -- <Starfield.esm> props <Class>      Mutagen's Starfield schema for a record class (Npc, NavmeshGeometry)
using Mutagen.Bethesda.Plugins.Cache;
using Mutagen.Bethesda.Starfield;

if (args.Length > 0 && args[0] == "reflect")
{
    foreach (var asm in AppDomain.CurrentDomain.GetAssemblies().Concat(new[] { typeof(Mutagen.Bethesda.Plugins.ModKey).Assembly, typeof(StarfieldMod).Assembly }).Distinct())
        foreach (var ty in asm.GetTypes().Where(x => x.Name.Contains(args[1])))
            Console.WriteLine(ty.FullName);
    return;
}
using var mod = StarfieldMod.CreateFromBinaryOverlay(args[0], StarfieldRelease.Starfield);
var cells = mod.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells).ToList();
var cache = mod.ToImmutableLinkCache();
string Name(Mutagen.Bethesda.Plugins.FormKey fk) =>
    cache.TryResolve<ILightingTemplateGetter>(fk, out var t) ? (t.EditorID ?? "") : "";

switch (args[1])
{
    case "cells":
        foreach (var c in cells.Where(c => (c.EditorID ?? "").Contains(args[2], StringComparison.OrdinalIgnoreCase)).Take(40))
            Console.WriteLine($"{c.EditorID}  {c.FormKey}  template={c.LightingTemplate.FormKey} {Name(c.LightingTemplate.FormKey)}  refs={c.Temporary.Count}");
        break;
    case "templates":
        foreach (var g in cells.Where(c => !c.LightingTemplate.IsNull).GroupBy(c => c.LightingTemplate.FormKey)
                     .OrderByDescending(g => g.Count()).Take(25))
            Console.WriteLine($"{g.Count(),5}  {g.Key}  {Name(g.Key)}  e.g. {g.First().EditorID}");
        break;
    case "statics":
        foreach (var s in mod.Statics.Where(s => (s.EditorID ?? "").Contains(args[2], StringComparison.OrdinalIgnoreCase)).Take(30))
            Console.WriteLine($"{s.EditorID}  {s.FormKey}  model={s.Model?.File}");
        break;
    case "doors":
        foreach (var d in mod.Doors.Where(d => (d.Model?.File?.ToString() ?? "").Contains(args[2], StringComparison.OrdinalIgnoreCase)).Take(3))
        {
            Console.WriteLine($"== {d.EditorID} {d.FormKey} model={d.Model?.File}");
            foreach (var p in d.GetType().GetProperties())
            {
                object? v; try { v = p.GetValue(d); } catch { continue; }
                var s = v switch { null => "null", string str => str, System.Collections.IEnumerable e and not string => "[" + string.Join(", ", e.Cast<object>().Take(6)) + "]", _ => v.ToString() };
                if (s != null && s.Length > 160) s = s.Substring(0, 160);
                Console.WriteLine($"   {p.Name} = {s}");
            }
        }
        break;
    case "agc":
        foreach (var d in mod.Doors.Where(d => (d.EditorID ?? "").Contains(args[2], StringComparison.OrdinalIgnoreCase)).Take(int.Parse(args.Length > 3 ? args[3] : "3")))
        {
            Console.WriteLine($"== {d.EditorID} {d.FormKey} model={d.Model?.File} flags={d.Flags}");
            foreach (var c in d.Components)
                foreach (var p in c.GetType().GetProperties())
                {
                    object? v; try { v = p.GetValue(c); } catch { continue; }
                    Console.WriteLine($"   {c.GetType().Name.Replace("BinaryOverlay","")}.{p.Name} = {v}");
                }
        }
        break;
    case "celldump":
        foreach (var c in cells.Where(c => string.Equals(c.EditorID, args[2], StringComparison.OrdinalIgnoreCase)).Take(1))
            foreach (var p in c.GetType().GetProperties())
            {
                object? v; try { v = p.GetValue(c); } catch { continue; }
                if (v == null || p.Name is "Temporary" or "Persistent" or "NavigationMeshes") continue;
                var s = v.ToString() ?? ""; if (s.Length > 140) s = s.Substring(0, 140);
                Console.WriteLine($"   {p.Name} = {s}");
            }
        break;
    case "graphs":   // every DOOR grouped by animation graph (ANAM) + skeleton: which vanilla doors slide, swing, lift
        foreach (var g in mod.Doors.Select(d => (d, agc: d.Components.OfType<IAnimationGraphComponentGetter>().FirstOrDefault()))
                     .Where(x => x.agc != null).GroupBy(x => x.agc!.ANAM ?? "").OrderByDescending(g => g.Count()))
        {
            Console.WriteLine($"{g.Count(),5}  {g.Key}");
            foreach (var x in g.Take(4))
                Console.WriteLine($"         {x.d.EditorID}  {x.d.FormKey}  {x.d.Model?.File}  rig={x.agc!.BNAM}");
        }
        break;
    case "doorprops":
        foreach (var p in typeof(Mutagen.Bethesda.Starfield.Door).GetProperties()) Console.WriteLine($"{p.PropertyType} {p.Name}");
        break;
    case "imgs":
        {
            var useCount = cells.Where(c => !c.ImageSpace.IsNull).GroupBy(c => c.ImageSpace.FormKey).ToDictionary(g => g.Key, g => g.Count());
            foreach (var i in mod.ImageSpaces.OrderByDescending(i => useCount.GetValueOrDefault(i.FormKey)).Take(30))
                Console.WriteLine($"{useCount.GetValueOrDefault(i.FormKey),5}  {i.FormKey}  {i.EditorID}");
        }
        break;
    case "lights":
        foreach (var l in mod.Lights.Where(l => (l.EditorID ?? "").Contains(args[2], StringComparison.OrdinalIgnoreCase)).Take(40))
            Console.WriteLine($"{l.EditorID}  {l.FormKey}  radius={l.Radius}  color={l.Color}  model={l.Model?.File}");
        break;
    // ---- actors / navigation (docs/actors/npc-navigation.md); read-only ----
    case "navm":   // NAVM per worldspace (EditorID contains args[2]; "*" = all) and in interior cells
        {
            var sub = args.Length > 2 ? args[2] : "*";
            foreach (var w in mod.Worldspaces.Where(w => sub == "*" || (w.EditorID ?? "").Contains(sub, StringComparison.OrdinalIgnoreCase)))
            {
                var wc = w.SubCells.SelectMany(b => b.Items).SelectMany(s => s.Items).ToList();
                if (w.TopCell != null) wc.Add(w.TopCell);
                Console.WriteLine($"{wc.Sum(c => c.NavigationMeshes.Count),6} NAVM  {wc.Count(c => c.NavigationMeshes.Count > 0),5}/{wc.Count,5} cells  {w.FormKey}  {w.EditorID}");
            }
            Console.WriteLine($"interior: {cells.Sum(c => c.NavigationMeshes.Count)} NAVM in {cells.Count(c => c.NavigationMeshes.Count > 0)}/{cells.Count} cells");
        }
        break;
    case "npcfind":   // NPC_ whose EditorID or race EditorID contains args[2]
        foreach (var n in mod.Npcs.Where(n => (n.EditorID ?? "").Contains(args[2], StringComparison.OrdinalIgnoreCase)
                                             || Edid(cache, n.Race.FormKey).Contains(args[2], StringComparison.OrdinalIgnoreCase))
                     .Take(int.Parse(args.Length > 3 ? args[3] : "40")))
            Console.WriteLine($"{n.FormKey}  {n.EditorID}  race={Edid(cache, n.Race.FormKey)}");
        break;
    case "npc":   // every property of the given NPC_ (FormIDs in hex, comma separated); links shown with EditorIDs
        foreach (var id in args[2].Split(','))
        {
            var fk = Mutagen.Bethesda.Plugins.FormKey.Factory($"{Convert.ToUInt32(id, 16) & 0xFFFFFF:X6}:{mod.ModKey}");
            if (!cache.TryResolve<INpcGetter>(fk, out var n)) { Console.WriteLine($"== {id}: no NPC_ in {mod.ModKey}"); continue; }
            Console.WriteLine($"== {n.FormKey} {n.EditorID}");
            foreach (var p in n.GetType().GetProperties())
            {
                object? v; try { v = p.GetValue(n); } catch { continue; }
                Console.WriteLine($"   {p.Name} = {Show(cache, v)}");
            }
        }
        break;
    case "props":   // Mutagen's Starfield schema for a record class (Npc, NavigationMesh, NavmeshGeometry, ...): what a writer can set
        foreach (var p in typeof(StarfieldMod).Assembly.GetType("Mutagen.Bethesda.Starfield." + args[2])!.GetProperties())
            Console.WriteLine($"{p.PropertyType.Name + string.Concat(p.PropertyType.GenericTypeArguments.Select(a => "<" + a.Name + ">")),-48} {p.Name}");
        break;
}

#pragma warning disable CS0618   // untyped identifier lookup is fine for a one-off inspector
static string Edid(Mutagen.Bethesda.Plugins.Cache.ILinkCache c, Mutagen.Bethesda.Plugins.FormKey fk) =>
    !fk.IsNull && c.TryResolveIdentifier(fk, out var e) ? (e ?? "") : "";
#pragma warning restore CS0618

static string Show(Mutagen.Bethesda.Plugins.Cache.ILinkCache c, object? v)
{
    string s = v switch
    {
        null => "null",
        string str => str,
        Mutagen.Bethesda.Plugins.IFormLinkGetter l => $"{l.FormKey} {Edid(c, l.FormKey)}",
        System.Collections.IEnumerable e => "[" + string.Join(", ", e.Cast<object?>().Take(12).Select(x => Show(c, x))) + "]",
        _ => (v.GetType().GetProperties().FirstOrDefault(p => typeof(Mutagen.Bethesda.Plugins.IFormLinkGetter).IsAssignableFrom(p.PropertyType)) is { } lp
              ? $"{v.GetType().Name.Replace("BinaryOverlay", "")}({Show(c, lp.GetValue(v))})" : v.ToString()) ?? "",
    };
    return s.Length > 220 ? s.Substring(0, 220) : s;
}
