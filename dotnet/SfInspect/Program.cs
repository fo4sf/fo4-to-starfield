// Inspect Starfield.esm: interior cells and their lighting templates, light records.
//   dotnet run -- <Starfield.esm> cells <substr>     interior cells (EditorID contains substr) + lighting template
//   dotnet run -- <Starfield.esm> lights <substr>    LIGH records (EditorID contains substr) + radius/colour
//   dotnet run -- <Starfield.esm> templates          lighting templates in use by interior cells (most used first)
//   dotnet run -- <Starfield.esm> envmaps            interior cells' environment maps (most used first) + a sample cell
//   dotnet run -- <Starfield.esm> models "<a>|<b>"   every record (any type) using a model whose path contains a or b
// Terrain (read-only, docs/terrain/architecture.md):
//   wrld [substr]            every WRLD with terrain/planet/parent fields      sfbk [substr]   every SurfaceBlock (BTD path, sizes)
//   planetworlds             planets registering master worldspaces            wcells <WRLD> [out.tsv]   cells + ref positions
//   form <hex>... | form type:<TypePrefix> <EditorID substr>   one-level dump of any record      landcount
// Note: opening a plugin other than Starfield.esm needs a master flag lookup (not implemented).
//   dotnet run -- <Starfield.esm> navm <substr|*>     NAVM count per worldspace (+ interior total)
//   dotnet run -- <Starfield.esm> npcfind <substr>   NPC_ by EditorID or race EditorID
//   dotnet run -- <Starfield.esm> npc <hex,hex>      all fields of NPC_ records (verifies the FormIDs exist)
//   dotnet run -- <Starfield.esm> props <Class>      Mutagen's Starfield schema for a record class (Npc, NavmeshGeometry)
//   dotnet run -- <Starfield.esm> doortsv            one TSV row per DOOR: graph (ANAM), rig (BNAM), clip folder (CNAM), flags
//   dotnet run -- <Starfield.esm> doorsounds         one TSV row per DOOR with sounds: open / close WWise events, graph, rig
//   dotnet run -- <Starfield.esm> furn <substr> [n]   FURN without a bench type (chairs, beds, ...): markers, template, graph
//   dotnet run -- <Starfield.esm> scripted <Script>  bases and placed refs with that script (base, graph, linked-ref keywords)
//   dotnet run -- <Starfield.esm> landing <WRLD substr> [n]   ship landing / map / heading markers of those worlds, their links,
//                                                              and the world's Location LCSR rows (how a ship lands there)
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
    case "envmaps":
        foreach (var g in cells.GroupBy(c => c.EnvironmentMap?.ToString() ?? "").OrderByDescending(g => g.Count()).Take(30))
            Console.WriteLine($"{g.Count(),5}  env='{g.Key}'  e.g. {g.First().EditorID} template={Name(g.First().LightingTemplate.FormKey)} " +
                $"imagespace={g.First().ImageSpace.FormKey}");
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
    case "mstt":     // MoveableStatic records whose model contains the substring: every property (what vanilla fills in)
        foreach (var d in mod.MoveableStatics.Where(d => (d.Model?.File?.ToString() ?? "").Contains(args[2], StringComparison.OrdinalIgnoreCase)).Take(3))
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
    case "doortsv":  // read-only: one TSV row per DOOR (graph ANAM, rig BNAM, clip folder CNAM, flags) for the sliding-door survey
        Console.WriteLine("editor_id\tformkey\tmodel\tanam\tbnam\tcnam\tflags\tkeywords");
        foreach (var d in mod.Doors)
        {
            var agc = d.Components.OfType<IAnimationGraphComponentGetter>().FirstOrDefault();
            Console.WriteLine(string.Join("\t", d.EditorID ?? "", d.FormKey.ToString(), d.Model?.File?.ToString() ?? "",
                agc?.ANAM ?? "", agc?.BNAM ?? "", agc?.CNAM ?? "", d.Flags.ToString(),
                string.Join("|", d.Keywords?.Select(k => k.FormKey.ToString()) ?? Array.Empty<string>())));
        }
        break;
    case "doorsounds":  // read-only: one TSV row per DOOR with a sound (WWise start / stop events, condition, event mapping)
        {
            string Snd(ISoundReferenceGetter? r) => r == null ? "\t\t\t" : string.Join("\t", r.Start.ToString(), r.Stop.ToString(),
                r.Condition.IsNull ? "" : r.Condition.FormKey.ToString(), r.EventMapping.IsNull ? "" : r.EventMapping.FormKey.ToString());
            Console.WriteLine("editor_id\tformkey\tanam\tbnam\topen_start\topen_stop\topen_condition\topen_mapping" +
                              "\tclose_start\tclose_stop\tclose_condition\tclose_mapping\tloop");
            foreach (var d in mod.Doors)
            {
                if (d.OpenSound == null && d.CloseSound == null && d.LoopSound == null) continue;
                var agc = d.Components.OfType<IAnimationGraphComponentGetter>().FirstOrDefault();
                Console.WriteLine(string.Join("\t", d.EditorID ?? "", d.FormKey.ToString(), agc?.ANAM ?? "", agc?.BNAM ?? "",
                    Snd(d.OpenSound), Snd(d.CloseSound), d.LoopSound == null ? "" : d.LoopSound.Start.ToString()));
            }
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
    case "wrld":     // read-only: every WRLD with its terrain/planet/parent fields (reflection dump; [substr] filters EditorID)
        {
            var filter = args.Length > 2 ? args[2] : "";
            var skip = new HashSet<string> { "TopCell", "SubCells", "LargeReferences", "Version2", "VersionControl", "FormVersion", "IsCompressed", "IsDeleted", "MajorFlags", "MajorRecordFlagsRaw", "SubCellsTimestamp", "SubCellsUnknown", "TopCellTimestamp", "Timestamp" };
            Console.WriteLine($"# WRLD count={mod.Worldspaces.Count}");
            foreach (var w in mod.Worldspaces.Where(w => (w.EditorID ?? "").Contains(filter, StringComparison.OrdinalIgnoreCase)))
            {
                var nCells = w.SubCells.SelectMany(b => b.Items).SelectMany(s => s.Items).Count();
                Console.WriteLine($"== {w.EditorID} {w.FormKey} subcells={nCells} topcell={(w.TopCell != null)}");
                foreach (var p in w.GetType().GetProperties())
                {
                    if (skip.Contains(p.Name) || p.GetIndexParameters().Length > 0) continue;
                    object? v; try { v = p.GetValue(w); } catch (Exception e) { v = "ERR " + e.GetType().Name; }
                    if (v == null) continue;
                    var s = v switch { string str => str, System.Collections.IEnumerable e and not string => "[" + string.Join(", ", e.Cast<object>().Take(8)) + "]", _ => v.ToString() ?? "" };
                    if (s.Length == 0 || s == "[]" || s == "Null" || s.EndsWith(":Null")) continue;
                    if (p.Name == "Name") s = s.Split(',').Skip(2).FirstOrDefault()?.Trim(' ', ']') ?? s;   // English name only
                    if (s.Length > 200) s = s.Substring(0, 200) + "...";
                    Console.WriteLine($"   {p.Name} = {s.Replace("\n", " ").Replace("\r", "")}");
                    // one level deeper for nested overlay structs (LandDefaults, MapData, Parent, Components, ...)
                    var nested = v is System.Collections.IEnumerable en && v is not string ? en.Cast<object>().Where(o => o.GetType().Namespace?.StartsWith("Mutagen") == true).ToList()
                               : (v.GetType().Namespace?.StartsWith("Mutagen.Bethesda.Starfield") == true ? new List<object> { v } : new List<object>());
                    foreach (var o in nested)
                        foreach (var q in o.GetType().GetProperties())
                        {
                            if (q.GetIndexParameters().Length > 0 || q.Name is "StaticRegistration" or "Registration") continue;
                            object? qv; try { qv = q.GetValue(o); } catch (Exception e) { qv = "ERR " + e.GetType().Name; }
                            if (qv == null) continue;
                            var qs = qv is System.Collections.IEnumerable qe && qv is not string ? "[" + string.Join(", ", qe.Cast<object>().Take(12)) + "]" : qv.ToString() ?? "";
                            if (qs.Length > 160) qs = qs.Substring(0, 160) + "...";
                            Console.WriteLine($"      {o.GetType().Name.Replace("BinaryOverlay", "")}.{q.Name} = {qs}");
                        }
                }
            }
        }
        break;
    case "form":     // read-only: form <hexid>... -> record type, EditorID and a one-level property dump
        {
            // form <hex>...           by FormID
            // form type:<TypePrefix> <EditorID substr>   e.g. form type:Planet Jemison
            Func<Mutagen.Bethesda.Plugins.Records.IMajorRecordGetter, bool> pick;
            if (args[2].StartsWith("type:"))
            {
                var tp = args[2].Substring(5); var sub = args.Length > 3 ? args[3] : "";
                pick = r => r.GetType().Name.StartsWith(tp) && (r.EditorID ?? "").Contains(sub, StringComparison.OrdinalIgnoreCase);
            }
            else
            {
                var want = args.Skip(2).Select(a => Convert.ToUInt32(a, 16) & 0xFFFFFF).ToHashSet();
                pick = r => want.Contains(r.FormKey.ID);
            }
            foreach (var r in mod.EnumerateMajorRecords().Where(pick).Take(12))
            {
                Console.WriteLine($"== {r.FormKey} {r.GetType().Name.Replace("BinaryOverlay", "")} {r.EditorID}");
                if (r is ICellGetter or IWorldspaceGetter) continue;   // use celldump / wrld for those
                foreach (var p in r.GetType().GetProperties())
                {
                    if (p.GetIndexParameters().Length > 0 || p.Name is "StaticRegistration" or "Registration") continue;
                    object? v; try { v = p.GetValue(r); } catch (Exception e) { v = "ERR " + e.GetType().Name; }
                    if (v == null) continue;
                    var s = v is System.Collections.IEnumerable en && v is not string ? "[" + string.Join(", ", en.Cast<object>().Take(16)) + "]" : v.ToString() ?? "";
                    if (s.Length == 0 || s == "[]") continue;
                    if (s.Length > 240) s = s.Substring(0, 240) + "...";
                    Console.WriteLine($"   {p.Name} = {s}");
                    if (v is System.Collections.IEnumerable en2 && v is not string)
                        foreach (var o in en2.Cast<object>().Where(o => o.GetType().Namespace?.StartsWith("Mutagen.Bethesda.Starfield") == true).Take(6))
                            foreach (var q in o.GetType().GetProperties().Where(q => q.GetIndexParameters().Length == 0 && q.Name != "StaticRegistration"))
                            {
                                object? qv; try { qv = q.GetValue(o); } catch { continue; }
                                if (qv == null) continue;
                                var qs = qv is System.Collections.IEnumerable qe && qv is not string ? "[" + string.Join(", ", qe.Cast<object>().Take(12)) + "]" : qv.ToString() ?? "";
                                if (qs.Length > 160) qs = qs.Substring(0, 160) + "...";
                                Console.WriteLine($"      {o.GetType().Name.Replace("BinaryOverlay", "")}.{q.Name} = {qs}");
                            }
                }
            }
        }
        break;
    case "sfbk":     // read-only: every SurfaceBlock (SFBK): BTD path (ANAM), category (NAM1), water height, nested DNAM/ENAM items
        {
            string Flat(object? o)
            {
                if (o == null) return "null";
                if (o is string s0) return s0;
                if (o is System.Collections.IEnumerable e && o is not string) return "[" + string.Join(",", e.Cast<object>().Take(16)) + "]";
                if (o.GetType().Namespace?.StartsWith("Mutagen.Bethesda.Starfield") == true)
                    return "{" + string.Join(" ", o.GetType().GetProperties().Where(q => q.GetIndexParameters().Length == 0 && q.Name != "StaticRegistration")
                        .Select(q => { object? v = null; try { v = q.GetValue(o); } catch { } return $"{q.Name}={(v is System.Collections.IEnumerable ve && v is not string ? "[" + string.Join(",", ve.Cast<object>().Take(16)) + "]" : v)}"; })) + "}";
                return o.ToString() ?? "";
            }
            var filter = args.Length > 2 ? args[2] : "";
            var blocks = mod.EnumerateMajorRecords().Where(r => r.GetType().Name.StartsWith("SurfaceBlock") && (r.EditorID ?? "").Contains(filter, StringComparison.OrdinalIgnoreCase)).ToList();
            Console.WriteLine($"# SFBK count={blocks.Count}");
            foreach (var b in blocks)
            {
                var t = b.GetType();
                string P(string n) { var p = t.GetProperty(n); object? v = null; try { v = p?.GetValue(b); } catch { } return Flat(v); }
                var meta = b.GetType().GetProperty("Components")?.GetValue(b) is System.Collections.IEnumerable comps ? string.Join(" ", comps.Cast<object>().Select(Flat)) : "";
                Console.WriteLine($"{b.FormKey}\t{b.EditorID}\tANAM={P("ANAM")}\tNAM1={P("NAM1")}\tWHGT={P("WHGT")}\tHNAM={P("HNAM")}\tINAM={P("INAM")}\tNAM5={P("NAM5")}\tDNAM={P("DNAM")}\tENAM={P("ENAM")}\tNAM3={P("NAM3")}\tNAM4={P("NAM4")}\tFNAM={P("FNAM")}\tMETA={meta}");
            }
        }
        break;
    case "wcells":   // read-only: wcells <WRLD EditorID> [out.tsv] -> per exterior cell: grid and ref position ranges; optional per-ref TSV
        {
            var w = mod.Worldspaces.First(x => string.Equals(x.EditorID, args[2], StringComparison.OrdinalIgnoreCase));
            var sub = w.SubCells.SelectMany(b => b.Items).SelectMany(s => s.Items).ToList();
            using var tsv = args.Length > 3 ? new StreamWriter(args[3]) : null;
            tsv?.WriteLine("cellx\tcelly\tref\tbase\tbasetype\tbaseedid\tx\ty\tz");
            var all = sub.Concat(w.TopCell != null ? new[] { w.TopCell } : Array.Empty<ICellGetter>());
            foreach (var c in all)
            {
                var refs = c.Temporary.Concat(c.Persistent).OfType<IPlacedObjectGetter>().ToList();
                var g = c.Grid?.Point;
                if (refs.Count > 0)
                    Console.WriteLine($"{c.FormKey} grid={g} flags={c.Flags} refs={refs.Count} x=[{refs.Min(r => r.Position.X):F1},{refs.Max(r => r.Position.X):F1}] y=[{refs.Min(r => r.Position.Y):F1},{refs.Max(r => r.Position.Y):F1}] z=[{refs.Min(r => r.Position.Z):F1},{refs.Max(r => r.Position.Z):F1}]");
                if (tsv != null)
                    foreach (var r in refs)
                    {
                        var bt = cache.TryResolve(r.Base.FormKey, out var baseRec) ? baseRec : null;
                        tsv.WriteLine($"{g?.X}\t{g?.Y}\t{r.FormKey}\t{r.Base.FormKey}\t{bt?.GetType().Name.Replace("BinaryOverlay", "")}\t{bt?.EditorID}\t{r.Position.X}\t{r.Position.Y}\t{r.Position.Z}");
                    }
            }
        }
        break;
    case "planetworlds": // read-only: planets (PNDT) that register master worldspaces (lat/long) + their surface tree
        {
            var wr = mod.Worldspaces.ToDictionary(w => w.FormKey, w => w.EditorID);
            var planets = mod.Planets.ToList();
            Console.WriteLine($"# PNDT count={planets.Count} with SurfaceTree={planets.Count(p => !p.SurfaceTree.IsNull)} with MasterWorldspaces={planets.Count(p => p.MasterWorldspaces.Count > 0)}");
            foreach (var p in planets.Where(p => p.MasterWorldspaces.Count > 0))
                foreach (var m in p.MasterWorldspaces)
                    Console.WriteLine($"{p.EditorID}\t{p.Name}\t{m.Worldspace.FormKey}\t{wr.GetValueOrDefault(m.Worldspace.FormKey)}\tlat={m.Latitude:F4}\tlon={m.Longitude:F4}\tsurfaceTree={p.SurfaceTree.FormKey}");
            var registered = planets.SelectMany(p => p.MasterWorldspaces.Select(m => m.Worldspace.FormKey)).ToHashSet();
            Console.WriteLine($"# worldspaces registered as master: {registered.Count} of {wr.Count}");
        }
        break;
    case "landcount": // read-only: count LAND records anywhere in the worldspace cells (FORMAT-GAP says 0)
        {
            int land = 0, ext = 0;
            foreach (var w in mod.Worldspaces)
                foreach (var c in w.SubCells.SelectMany(b => b.Items).SelectMany(s => s.Items).Concat(w.TopCell != null ? new[] { w.TopCell } : Array.Empty<ICellGetter>()))
                {
                    ext++;
                    var lp = c.GetType().GetProperty("Landscape");
                    if (lp != null && lp.GetValue(c) != null) land++;
                }
            Console.WriteLine($"exterior cells={ext} cells with Landscape={land} (Landscape property on cell type: {typeof(ICellGetter).GetProperty("Landscape") != null})");
        }
        break;
    case "lights":
        foreach (var l in mod.Lights.Where(l => (l.EditorID ?? "").Contains(args[2], StringComparison.OrdinalIgnoreCase)).Take(40))
            Console.WriteLine($"{l.EditorID}  {l.FormKey}  radius={l.Radius}  color={l.Color}  model={l.Model?.File}");
        break;
    case "models":   // every record (any type) whose model path contains one of the |-separated substrings
        var wanted = args[2].Split('|');
        foreach (var r in mod.EnumerateMajorRecords())
            if (r is IModeledGetter m && m.Model?.File is { } file
                && wanted.Any(w => file.ToString().Contains(w, StringComparison.OrdinalIgnoreCase)))
                Console.WriteLine($"{r.GetType().Name.Replace("BinaryOverlay", "")}  {r.EditorID}  {r.FormKey}  model={file}");
        break;
    case "teleports":   // how vanilla load doors are set up: every placed object with an XTEL, its base record, its destination
    {
        // (ref, cell, persistent group?) for every placed object in interior and worldspace cells
        var all = new Dictionary<Mutagen.Bethesda.Plugins.FormKey, (IPlacedObjectGetter r, ICellGetter c, bool persistent, bool interior)>();
        void Take(ICellGetter c, bool interior)
        {
            foreach (var r in c.Persistent.OfType<IPlacedObjectGetter>()) all.TryAdd(r.FormKey, (r, c, true, interior));
            foreach (var r in c.Temporary.OfType<IPlacedObjectGetter>()) all.TryAdd(r.FormKey, (r, c, false, interior));
        }
        foreach (var c in cells) Take(c, true);
        foreach (var w in mod.Worldspaces)
        {
            if (w.TopCell != null) Take(w.TopCell, false);
            foreach (var c in w.SubCells.SelectMany(b => b.Items).SelectMany(b => b.Items)) Take(c, false);
        }
        var tele = all.Values.Where(x => x.r.TeleportDestination != null).ToList();
        Console.WriteLine($"placed objects scanned: {all.Count}; with XTEL: {tele.Count} (interior {tele.Count(x => x.interior)}, " +
                          $"persistent group {tele.Count(x => x.persistent)}, record flag 0x400 {tele.Count(x => (x.r.MajorRecordFlagsRaw & 0x400) != 0)})");
        int baseDoor = 0, baseOther = 0, destDoor = 0, destBack = 0, destMissing = 0, transition = 0, sameCell = 0, agc = 0, agcNull = 0;
        var xtelFlags = new Dictionary<uint, int>();
        var doorFlags = new Dictionary<string, int>();
        var bases = new Dictionary<Mutagen.Bethesda.Plugins.FormKey, int>();
        var dist = new List<double>();
        var recFlags = new Dictionary<int, int>();
        foreach (var (r, c, persistent, interior) in tele)
        {
            var t = r.TeleportDestination!;
            xtelFlags[(uint)t.Flags] = xtelFlags.GetValueOrDefault((uint)t.Flags) + 1;
            recFlags[r.MajorRecordFlagsRaw] = recFlags.GetValueOrDefault(r.MajorRecordFlagsRaw) + 1;
            if (!t.TransitionInterior.IsNull) transition++;
            if (cache.TryResolve<IDoorGetter>(r.Base.FormKey, out var d))
            {
                baseDoor++;
                bases[d.FormKey] = bases.GetValueOrDefault(d.FormKey) + 1;
                doorFlags[d.Flags.ToString()] = doorFlags.GetValueOrDefault(d.Flags.ToString()) + 1;
                if (d.Components.OfType<IAnimationGraphComponentGetter>().Any()) agc++; else agcNull++;
            }
            else baseOther++;
            if (all.TryGetValue(t.Door.FormKey, out var dest))
            {
                if (cache.TryResolve<IDoorGetter>(dest.r.Base.FormKey, out _)) destDoor++;
                if (dest.r.TeleportDestination?.Door.FormKey == r.FormKey) destBack++;
                if (dest.c.FormKey == c.FormKey) sameCell++;
                var p = dest.r.Position;
                dist.Add(Math.Sqrt(Math.Pow(t.Position.X - p.X, 2) + Math.Pow(t.Position.Y - p.Y, 2) + Math.Pow(t.Position.Z - p.Z, 2)));
            }
            else destMissing++;
        }
        Console.WriteLine($"base is DOOR: {baseDoor}, other: {baseOther}; of those DOORs: with AnimationGraphComponent {agc}, without {agcNull}");
        Console.WriteLine($"destination found: {tele.Count - destMissing} (base DOOR {destDoor}, links back to source {destBack}, same cell {sameCell}); not found {destMissing}");
        Console.WriteLine($"XTEL TransitionInterior set: {transition}");
        foreach (var kv in xtelFlags.OrderByDescending(k => k.Value)) Console.WriteLine($"  XTEL flags {kv.Key}: {kv.Value}");
        foreach (var kv in recFlags.OrderByDescending(k => k.Value).Take(6)) Console.WriteLine($"  record flags 0x{kv.Key:X}: {kv.Value}");
        foreach (var kv in doorFlags.OrderByDescending(k => k.Value)) Console.WriteLine($"  DOOR flags [{kv.Key}]: {kv.Value}");
        dist.Sort();
        if (dist.Count > 0) Console.WriteLine($"XTEL arrival point to destination door position: median {dist[dist.Count / 2]:F2}, p10 {dist[dist.Count / 10]:F2}, p90 {dist[dist.Count * 9 / 10]:F2}");
        Console.WriteLine("most used DOOR bases with an XTEL:");
        foreach (var kv in bases.OrderByDescending(k => k.Value).Take(12))
        {
            var d = cache.Resolve<IDoorGetter>(kv.Key);
            var g = d.Components.OfType<IAnimationGraphComponentGetter>().FirstOrDefault();
            Console.WriteLine($"{kv.Value,5}  {d.FormKey} {d.EditorID}  name={d.Name}  flags={d.Flags}  model={d.Model?.File}  agc={g?.ANAM ?? "none"}  components=[{string.Join(",", d.Components.Select(x => x.GetType().Name.Replace("BinaryOverlay", "")))}]");
        }
        var want = args.Length > 2 ? args[2] : null;
        Console.WriteLine("examples (interior source, destination resolved):");
        foreach (var (r, c, persistent, interior) in tele.Where(x => x.interior && all.ContainsKey(x.r.TeleportDestination!.Door.FormKey) &&
                     (want == null || (x.c.EditorID ?? "").Contains(want, StringComparison.OrdinalIgnoreCase))).Take(want == null ? 6 : 20))
        {
            var t = r.TeleportDestination!;
            var dest = all[t.Door.FormKey];
            cache.TryResolve<IDoorGetter>(r.Base.FormKey, out var d);
            cache.TryResolve<IDoorGetter>(dest.r.Base.FormKey, out var dd);
            Console.WriteLine($"  {c.EditorID} {r.FormKey} persistent={persistent} flags=0x{r.MajorRecordFlagsRaw:X} base={d?.EditorID} pos=({r.Position.X:F2},{r.Position.Y:F2},{r.Position.Z:F2}) rotZ={r.Rotation.Z:F3}");
            Console.WriteLine($"     -> {dest.c.EditorID} {dest.r.FormKey} persistent={dest.persistent} base={dd?.EditorID} destpos=({dest.r.Position.X:F2},{dest.r.Position.Y:F2},{dest.r.Position.Z:F2}) destrotZ={dest.r.Rotation.Z:F3}");
            Console.WriteLine($"     XTEL pos=({t.Position.X:F2},{t.Position.Y:F2},{t.Position.Z:F2}) rot=({t.Rotation.X:F3},{t.Rotation.Y:F3},{t.Rotation.Z:F3}) flags={t.Flags} transition={t.TransitionInterior.FormKey} back={(dest.r.TeleportDestination?.Door.FormKey == r.FormKey)}");
        }
        break;
    }
    case "scripted":   // read-only: scripted <ScriptName>: base records and placed objects whose VMAD names the script, with each
                       // placed object's base type, model, animation graph and linked-ref keywords (how vanilla wires elevators)
    {
        var script = args[2];
        bool Has(IVirtualMachineAdapterGetter? v) => v?.Scripts.Any(s => string.Equals(s.Name, script, StringComparison.OrdinalIgnoreCase)) == true;
        foreach (var r in mod.EnumerateMajorRecords())
            if (r is not IPlacedObjectGetter && r.GetType().GetProperty("VirtualMachineAdapter")?.GetValue(r) is IVirtualMachineAdapterGetter bv && Has(bv))
                Console.WriteLine($"base {r.GetType().Name.Replace("BinaryOverlay", "")} {r.FormKey} {r.EditorID}");
        int shown = 0, total = 0;
        void ShowScripted(ICellGetter c, IPlacedObjectGetter r)
        {
            if (!Has(r.VirtualMachineAdapter)) return;
            total++;
            if (shown++ >= 12) return;
            var b = cache.TryResolve<Mutagen.Bethesda.Plugins.Records.IMajorRecordGetter>(r.Base.FormKey, out var br) ? br : null;
            var agc = (b?.GetType().GetProperty("Components")?.GetValue(b) as System.Collections.IEnumerable)?.OfType<IAnimationGraphComponentGetter>().FirstOrDefault();
            var model = (b as IModeledGetter)?.Model?.File?.ToString() ?? "";
            var links = string.Join(", ", r.LinkedReferences.Select(l =>
                (cache.TryResolve<IKeywordGetter>(l.KeywordOrReference.FormKey, out var k) ? k.EditorID : l.KeywordOrReference.FormKey.ToString()) + "->" + l.Reference.FormKey));
            Console.WriteLine($"ref {c.EditorID} {r.FormKey} base={b?.GetType().Name.Replace("BinaryOverlay", "")} {b?.EditorID} model={model} graph={agc?.ANAM} rig={agc?.BNAM} clips={agc?.CNAM}");
            Console.WriteLine($"    links: {links}");
        }
        foreach (var c in cells)
            foreach (var r in c.Persistent.Concat(c.Temporary).OfType<IPlacedObjectGetter>()) ShowScripted(c, r);
        foreach (var w in mod.Worldspaces)
            foreach (var c in w.SubCells.SelectMany(b => b.Items).SelectMany(b => b.Items).Concat(w.TopCell != null ? new[] { w.TopCell } : Array.Empty<ICellGetter>()))
                foreach (var r in c.Persistent.Concat(c.Temporary).OfType<IPlacedObjectGetter>()) ShowScripted(c, r);
        Console.WriteLine($"placed objects with {script}: {total}");
        break;
    }
    case "furn":   // read-only: furn <EditorID substr> [n]: sittable furniture (no bench type) and what a converted chair must copy
    {
        var kwEdid = mod.Keywords.ToDictionary(k => k.FormKey, k => k.EditorID);
        string K(Mutagen.Bethesda.Plugins.FormKey k) => kwEdid.TryGetValue(k, out var e) ? $"{e} {k.ID:X6}" : k.ToString();
        var limit = args.Length > 3 ? int.Parse(args[3]) : 20;
        var hits = mod.Furniture.Where(f => (f.BenchType ?? Furniture.BenchTypes.None) == Furniture.BenchTypes.None
                                            && (f.EditorID ?? "").Contains(args[2], StringComparison.OrdinalIgnoreCase)).ToList();
        Console.WriteLine($"{hits.Count} FURN without a bench type match '{args[2]}' (showing {Math.Min(limit, hits.Count)})");
        foreach (var f in hits.Take(limit))
        {
            Console.WriteLine($"== {f.EditorID} {f.FormKey.ID:X6} model={f.Model?.File} name={f.Name?.String}");
            Console.WriteLine($"   template={f.FurnitureTemplate.FormKeyNullable} markerModel={f.MarkerModel} markerFlags={f.MarkerFlags} flags={f.Flags}");
            Console.WriteLine($"   keywords: {string.Join(", ", (f.Keywords?.Select(k => K(k.FormKey)) ?? Enumerable.Empty<string>()))}");
            foreach (var e in f.MarkerEntryPoints ?? Enumerable.Empty<IFurnitureMarkerEntryPointsGetter>()) Console.WriteLine($"   entry {e.Type}: {e.EntryPoints}");
            foreach (var m in f.MarkerParameters ?? Enumerable.Empty<IFurnitureMarkerParametersGetter>())
                Console.WriteLine($"   marker offset=({m.Offset.X:F2}, {m.Offset.Y:F2}, {m.Offset.Z:F2}) rotZ={m.RotationZ:F3} keyword={K(m.Keyword.FormKey)} entry={m.EntryTypes} exit={m.ExitTypes}");
            foreach (var g in f.Components.OfType<IAnimationGraphComponentGetter>()) Console.WriteLine($"   graph {g.ANAM} skeleton {g.BNAM} anims {g.CNAM}");
            Console.WriteLine($"   markerFiles={f.MarkerFiles?.Count ?? 0} properties={f.Properties?.Count ?? 0} sittingAngle={f.ActivationAngleForSittingActor}");
        }
        break;
    }
    case "doorrefs":   // read-only: doorrefs <DOOR EditorID substr> [n]: placed doors of those bases, every REFR property, their linked
                       // references with each target's base, and the references that link to them (how a vanilla load elevator is wired)
        {
            var sub = args[2]; var max = args.Length > 3 ? int.Parse(args[3]) : 6;
            var placed = new List<(IPlacedObjectGetter r, string where)>();
            foreach (var c in cells)
                foreach (var r in c.Persistent.Concat(c.Temporary).OfType<IPlacedObjectGetter>()) placed.Add((r, c.EditorID ?? c.FormKey.ToString()));
            foreach (var w in mod.Worldspaces)
            {
                if (w.TopCell != null)
                    foreach (var r in w.TopCell.Persistent.Concat(w.TopCell.Temporary).OfType<IPlacedObjectGetter>()) placed.Add((r, w.EditorID ?? ""));
                foreach (var c in w.SubCells.SelectMany(b => b.Items).SelectMany(b => b.Items))
                    foreach (var r in c.Persistent.Concat(c.Temporary).OfType<IPlacedObjectGetter>()) placed.Add((r, (w.EditorID ?? "") + "/" + (c.EditorID ?? c.FormKey.ToString())));
            }
            var byKey = new Dictionary<Mutagen.Bethesda.Plugins.FormKey, IPlacedObjectGetter>();
            foreach (var (r, _) in placed) byKey.TryAdd(r.FormKey, r);
            string BaseOf(Mutagen.Bethesda.Plugins.FormKey fk) =>
                byKey.TryGetValue(fk, out var t) && cache.TryResolve<Mutagen.Bethesda.Plugins.Records.IMajorRecordGetter>(t.Base.FormKey, out var b)
                    ? $"{b.GetType().Name.Replace("BinaryOverlay", "")} {b.EditorID}" : "?";
            var picked = placed.Where(x => cache.TryResolve<IDoorGetter>(x.r.Base.FormKey, out var d) && (d.EditorID ?? "").Contains(sub, StringComparison.OrdinalIgnoreCase)).Take(max).ToList();
            Console.WriteLine($"placed objects: {placed.Count}; doors of bases matching '{sub}' shown: {picked.Count}");
            foreach (var (r, where) in picked)
            {
                Console.WriteLine($"== {r.FormKey} base {Edid(cache, r.Base.FormKey)} in {where} pos {r.Position} flags 0x{r.MajorRecordFlagsRaw:X}");
                foreach (var p in r.GetType().GetProperties())
                {
                    if (p.GetIndexParameters().Length > 0 || p.Name is "StaticRegistration" or "Registration") continue;
                    object? v; try { v = p.GetValue(r); } catch (Exception e) { v = "ERR " + e.GetType().Name; }
                    if (v == null) continue;
                    var s = v is System.Collections.IEnumerable en && v is not string ? "[" + string.Join(", ", en.Cast<object>().Take(16)) + "]" : v.ToString() ?? "";
                    if (s.Length == 0 || s == "[]") continue;
                    Console.WriteLine($"   {p.Name} = {(s.Length > 240 ? s.Substring(0, 240) + "..." : s)}");
                }
                if (r.TeleportDestination is { } t)
                    Console.WriteLine($"   XTEL -> {t.Door.FormKey} ({BaseOf(t.Door.FormKey)}) flags {t.Flags} at {t.Position}");
                foreach (var l in r.LinkedReferences)
                    Console.WriteLine($"   link {Edid(cache, l.KeywordOrReference.FormKey)} -> {l.Reference.FormKey} ({BaseOf(l.Reference.FormKey)})");
                foreach (var (o, ow) in placed.Where(x => x.r.LinkedReferences.Any(l => l.Reference.FormKey == r.FormKey)).Take(12))
                    Console.WriteLine($"   linked from {o.FormKey} ({BaseOf(o.FormKey)}) in {ow} by {string.Join(",", o.LinkedReferences.Where(l => l.Reference.FormKey == r.FormKey).Select(l => Edid(cache, l.KeywordOrReference.FormKey)))}");
                if (r.EnableParent is { } ep)
                    Console.WriteLine($"   enable parent {ep.Reference.FormKey} ({BaseOf(ep.Reference.FormKey)}) flags {ep.Flags}");
            }
        }
        break;
    case "landing":   // read-only: landing <WRLD EditorID substr> [n]: how a vanilla world lets a ship land (the owner's temporary
                      // landing spot, Map thread 2026-10-23; docs/terrain/map-markers.md): in up to n worlds (default 4), every placed
                      // object whose base EditorID names a ship landing, a map marker, a heading marker or a landing zone, with every
                      // REFR property, its scripts with their properties, its linked references (keyword -> target and its base) and
                      // the references that link to it,
                      // then the world's Location: keywords, parent, and every LCSR row (ref type -> ref, world, grid)
        {
            var sub = args[2]; var max = args.Length > 3 ? int.Parse(args[3]) : 4;
            string[] kinds = { "ShipLanding", "MapMarker", "XMarkerHeading", "LandingZone", "Landing" };
            foreach (var w in mod.Worldspaces.Where(w => (w.EditorID ?? "").Contains(sub, StringComparison.OrdinalIgnoreCase)).Take(max))
            {
                var placed = new List<(IPlacedObjectGetter r, string where)>();
                if (w.TopCell != null)
                    foreach (var r in w.TopCell.Persistent.Concat(w.TopCell.Temporary).OfType<IPlacedObjectGetter>()) placed.Add((r, "persistent"));
                foreach (var c in w.SubCells.SelectMany(b => b.Items).SelectMany(b => b.Items))
                    foreach (var r in c.Persistent.Concat(c.Temporary).OfType<IPlacedObjectGetter>()) placed.Add((r, $"cell ({c.Grid?.Point.X}, {c.Grid?.Point.Y}) {c.EditorID}"));
                var byKey = new Dictionary<Mutagen.Bethesda.Plugins.FormKey, IPlacedObjectGetter>();
                foreach (var (r, _) in placed) byKey.TryAdd(r.FormKey, r);
                string BaseEdid(IPlacedObjectGetter r) => Edid(cache, r.Base.FormKey);
                string BaseOf(Mutagen.Bethesda.Plugins.FormKey fk) => byKey.TryGetValue(fk, out var t) ? BaseEdid(t) : "? (outside this world)";
                var picked = placed.Where(x => x.r.MapMarker != null || kinds.Any(k => BaseEdid(x.r).Contains(k, StringComparison.OrdinalIgnoreCase))).ToList();
                var keys = picked.Select(x => x.r.FormKey).ToHashSet();
                foreach (var (r, wh) in picked.ToList())                     // one hop: what they link to, in this world
                    foreach (var l in r.LinkedReferences)
                        if (byKey.TryGetValue(l.Reference.FormKey, out var t) && keys.Add(t.FormKey)) picked.Add((t, placed.First(x => x.r.FormKey == t.FormKey).where));
                Console.WriteLine($"######## {w.EditorID} {w.FormKey}: {placed.Count} placed objects, {picked.Count} shown; location {w.Location.FormKey} {Edid(cache, w.Location.FormKey)}");
                foreach (var (r, where) in picked)
                {
                    Console.WriteLine($"== {r.FormKey} base {Edid(cache, r.Base.FormKey)} {r.Base.FormKey} in {where} pos {r.Position} rot {r.Rotation} flags 0x{r.MajorRecordFlagsRaw:X}");
                    foreach (var p in r.GetType().GetProperties())
                    {
                        if (p.GetIndexParameters().Length > 0 || p.Name is "StaticRegistration" or "Registration" or "Position" or "Rotation") continue;
                        object? v; try { v = p.GetValue(r); } catch (Exception e) { v = "ERR " + e.GetType().Name; }
                        if (v == null) continue;
                        var s = v is System.Collections.IEnumerable en && v is not string ? "[" + string.Join(", ", en.Cast<object>().Take(16)) + "]" : v.ToString() ?? "";
                        if (s.Length == 0 || s == "[]" || s == "Null") continue;
                        Console.WriteLine($"   {p.Name} = {(s.Length > 240 ? s.Substring(0, 240) + "..." : s)}");
                    }
                    foreach (var sc in r.VirtualMachineAdapter?.Scripts ?? Enumerable.Empty<IScriptEntryGetter>())
                        Console.WriteLine($"   script {sc.Name}: " + string.Join("; ", sc.Properties.Select(sp => sp switch
                        {
                            IScriptObjectPropertyGetter o => $"{sp.Name} = {o.Object.FormKey} {Edid(cache, o.Object.FormKey)}",
                            IScriptObjectListPropertyGetter ol => $"{sp.Name} = [{string.Join(", ", ol.Objects.Select(o => $"{o.Object.FormKey} {Edid(cache, o.Object.FormKey)}"))}]",
                            IScriptFloatPropertyGetter f => $"{sp.Name} = {f.Data}",
                            IScriptIntPropertyGetter n => $"{sp.Name} = {n.Data}",
                            IScriptBoolPropertyGetter b => $"{sp.Name} = {b.Data}",
                            IScriptStringPropertyGetter t => $"{sp.Name} = \"{t.Data}\"",
                            _ => $"{sp.Name} ({sp.GetType().Name.Replace("BinaryOverlay", "")})",
                        })));
                    if (r.MapMarker is { } mm)
                        Console.WriteLine($"   map marker: flags {mm.Flags} (0x{(int)mm.Flags:X}) name \"{mm.Name}\" type {mm.Type}");
                    foreach (var l in r.LinkedReferences)
                        Console.WriteLine($"   link {Edid(cache, l.KeywordOrReference.FormKey)} -> {l.Reference.FormKey} ({BaseOf(l.Reference.FormKey)})");
                    foreach (var (o, ow) in placed.Where(x => x.r.LinkedReferences.Any(l => l.Reference.FormKey == r.FormKey)).Take(12))
                        Console.WriteLine($"   linked from {o.FormKey} ({BaseEdid(o)}) in {ow} by {string.Join(",", o.LinkedReferences.Where(l => l.Reference.FormKey == r.FormKey).Select(l => Edid(cache, l.KeywordOrReference.FormKey)))}");
                    if (r.EnableParent is { } ep)
                        Console.WriteLine($"   enable parent {ep.Reference.FormKey} ({BaseOf(ep.Reference.FormKey)}) flags {ep.Flags}");
                }
                if (cache.TryResolve<ILocationGetter>(w.Location.FormKey, out var loc))
                {
                    Console.WriteLine($"-- location {loc.FormKey} {loc.EditorID} \"{loc.Name}\" parent {Edid(cache, loc.ParentLocation.FormKey)} " +
                                      $"keywords [{string.Join(", ", (loc.Keywords ?? Array.Empty<Mutagen.Bethesda.Plugins.IFormLinkGetter<IKeywordGetter>>()).Select(k => Edid(cache, k.FormKey)))}]");
                    foreach (var row in loc.MasterSpecialReferences ?? Enumerable.Empty<ILocationCellStaticReferenceGetter>())
                        Console.WriteLine($"   LCSR {Edid(cache, row.LocationRefType.FormKey)} -> {row.Marker.FormKey} ({BaseOf(row.Marker.FormKey)}) world {Edid(cache, row.Location.FormKey)} grid {row.Grid} unknown {row.Unknown}");
                    foreach (var r in loc.MasterInitiallyDisabledReferences ?? Enumerable.Empty<Mutagen.Bethesda.Plugins.IFormLinkGetter<IPlacedGetter>>())
                        Console.WriteLine($"   LCID {r.FormKey} ({BaseOf(r.FormKey)})");
                }
            }
        }
        break;
    case "doorrec":   // one DOOR record by EditorID substring: every property, for comparing a load door with a hinged door
        foreach (var d in mod.Doors.Where(d => (d.EditorID ?? "").Contains(args[2], StringComparison.OrdinalIgnoreCase)).Take(3))
        {
            Console.WriteLine($"== {d.EditorID} {d.FormKey} model={d.Model?.File}");
            foreach (var p in d.GetType().GetProperties())
            {
                object? v; try { v = p.GetValue(d); } catch { continue; }
                var s = v switch { null => "null", string str => str, System.Collections.IEnumerable e and not string => "[" + string.Join(", ", e.Cast<object>().Take(8).Select(x => x.GetType().Name.Replace("BinaryOverlay", ""))) + "]", _ => v.ToString() };
                if (s != null && s.Length > 200) s = s.Substring(0, 200);
                Console.WriteLine($"   {p.Name} = {s}");
            }
        }
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
