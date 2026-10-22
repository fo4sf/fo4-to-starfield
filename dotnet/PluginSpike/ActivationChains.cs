// Activation chains (docs/terrain/port-promotions.md, "Activation chains"): a switch that opens a door.
//
// Fallout 4 wires them on the CHILD: its activate parents block (XAPD flags + XAPR parent reference and delay, exported by
// dotnet/Fo4Export as "activate_parents", PR #305) says "when that parent is activated, activate me". Mutagen 0.55
// Starfield has no ActivateParents on a placed object (docs/terrain/garage-button.md), so the chain is written the
// Starfield-native way the core already uses for the Red Rocket garage button (#303): the PARENT reference gets vanilla
// DefaultActivateLinkedRefOnActivate (its LinkedRefKeyword = LinkCustom02 0005D5E7) and a linked reference (XLKR) with
// that keyword to the child. The script activates one linked reference, so a parent that drives more than one child is
// reported and left unwired (a partial wire would look like a working machine that stops halfway), counting children
// that were not converted. Not carried: the
// delay, and FO4's "parent activate only" flag (bit 0: the child cannot be used directly); both are counted.
// Only parents the player can use get the wire: promoted activators and terminals, and opening (non-load) doors.
using System.Text.Json;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Starfield;

public sealed class ActivationReport
{
    public int Wired { get; set; }                      // parent -> child wires written
    public int ChildrenWithParents { get; set; }        // exported references with an activate parents block
    public int ParentNotPlaced { get; set; }            // the parent reference is not in this build (trigger volumes have no model)
    public int ChildNotPlaced { get; set; }             // the child itself was not placed
    public int ParentNotUsable { get; set; }            // the parent's base is not an activator, terminal or opening door
    public int ParentDrivesSeveral { get; set; }        // children of parents with more than one child (left unwired)
    public int ParentHasScript { get; set; }            // the parent already carries a VMAD (left unwired)
    public int DelaysDropped { get; set; }              // wires whose FO4 delay is not 0
    public int ParentActivateOnly { get; set; }         // children FO4 marks "parent activate only" (flag not carried)
    public List<string> Unwired { get; } = new();       // "<parent> -> <child>: <reason>"
}

public static class ActivationChains
{
    public static readonly FormKey LinkCustom02 = new(ModKey.FromNameAndExtension("Starfield.esm"), 0x5D5E7);
    public const string Script = "DefaultActivateLinkedRefOnActivate";

    public static ActivationReport Apply(IReadOnlyDictionary<string, (PlacedObject obj, Cell cell)> placed,
                                         IEnumerable<JsonElement> cellExports, ISet<FormKey> usableBases)
    {
        var report = new ActivationReport();
        var byParent = new Dictionary<string, List<(string child, float delay)>>();
        foreach (var root in cellExports)
            foreach (var r in root.GetProperty("refs").EnumerateArray())
            {
                if (!r.TryGetProperty("activate_parents", out var ap) || ap.ValueKind != JsonValueKind.Object) continue;
                var child = r.GetProperty("formkey").GetString()!;
                report.ChildrenWithParents++;
                if ((ap.GetProperty("flags").GetUInt32() & 1) != 0) report.ParentActivateOnly++;
                // every source edge is kept, placed child or not: a parent's whole FO4 fanout decides whether it can be
                // wired, so a machine whose second child was not converted is not cut down to a one-child wire
                // (Codex's review of #357)
                if (!placed.ContainsKey(child)) report.ChildNotPlaced++;
                foreach (var p in ap.GetProperty("parents").EnumerateArray())
                {
                    var parent = p.GetProperty("reference").GetString();
                    if (parent == null || !placed.ContainsKey(parent))
                    {
                        report.ParentNotPlaced++;
                        report.Unwired.Add($"{parent ?? "null"} -> {child}: parent not placed");
                        continue;
                    }
                    if (!byParent.TryGetValue(parent, out var list)) byParent[parent] = list = new();
                    list.Add((child, p.GetProperty("delay").GetSingle()));
                }
            }
        foreach (var (parent, children) in byParent.OrderBy(kv => kv.Key, StringComparer.Ordinal))
        {
            var obj = placed[parent].obj;
            var missing = children.Where(c => !placed.ContainsKey(c.child)).Select(c => c.child).ToList();
            string? why = !usableBases.Contains(obj.Base.FormKey) ? "parent is not an activator, terminal or opening door"
                        : children.Count > 1 ? $"parent drives {children.Count} children (one linked ref per script)"
                        : missing.Count > 0 ? "child not placed"
                        : obj.VirtualMachineAdapter != null ? "parent already carries a script"
                        : null;
            if (why != null)
            {
                if (why.StartsWith("parent is not")) report.ParentNotUsable += children.Count;
                else if (why.StartsWith("parent drives")) report.ParentDrivesSeveral += children.Count;
                else if (why.StartsWith("parent already")) report.ParentHasScript += children.Count;
                // "child not placed" is already counted per child above
                foreach (var (child, _) in children)
                    report.Unwired.Add($"{parent} -> {child}: {why}" + (missing.Contains(child) && why != "child not placed" ? " (child not placed)" : ""));
                continue;
            }
            var (target, delay) = children[0];
            var vmad = new VirtualMachineAdapter { Version = 6, ObjectFormat = 2 };
            var script = new ScriptEntry { Name = Script };
            script.Properties.Add(new ScriptObjectProperty
            {
                Name = "LinkedRefKeyword", Flags = ScriptProperty.Flag.Edited,
                Object = new FormLink<IStarfieldMajorRecordGetter>(LinkCustom02), Alias = -1, Unused = 0,
            });
            vmad.Scripts.Add(script);
            obj.VirtualMachineAdapter = vmad;
            var link = new LinkedReferences();
            link.KeywordOrReference.SetTo(LinkCustom02);
            link.Reference.SetTo(placed[target].obj.FormKey);
            obj.LinkedReferences.Add(link);
            report.Wired++;
            if (Math.Abs(delay) > 1e-6) report.DelaysDropped++;
        }
        return report;
    }
}
