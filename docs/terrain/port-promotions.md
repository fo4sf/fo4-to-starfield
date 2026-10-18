# Interior promotions: usable objects in FO4Port.esm

Author: Claude-cloud, 2026-10-18. Labels as in docs/ai/research-log.md.

## Why
The owner's play test (18 Oct, 19:32Z to 19:41Z, installed v5 set): indoors, things that should be used are not; the
Nuka-Cola machines, chairs and many other usable objects do nothing. **Verified from the code**: dotnet/PluginSpike
writes every converted interior reference as a STAT, or as an MSTT when its model has a dynamic body (DOOR only for
doors). Containers, loose inventory items, activators and terminals therefore have nothing to open, take, press or read.
The exterior core already promotes the same classes (make_cluster.py, make_core64c.py, dotnet/TerrainOverlays), and the
owner verified those work outdoors (docs/owner/playtest-issues.md rows 12 and 16).

## What changes
- `scripts/terrain/port_promote.py` reads the cell exports PluginSpike is given and writes `promote.json` into
  PluginSpike's output dir, with the core's rules and tables (make_cluster.containers / items / activators / terminals):
  containers (table name and vanilla inventory; workshops skipped by the table), items (MiscItem, Ingestible, Weapon as
  MISC with the table's name, value, weight), activators (FO4 name, or none), terminals (name and one body line).
- `dotnet/PluginSpike` (Promotions.cs) reads `promote.json` when it is there and gives each listed reference a CONT /
  MISC / ACTI / TERM (+ TMLM) base with the model its STAT / MSTT would have had, one base per edid. The reference keeps
  its stable REFR FormID (saves keep working); new bases get stable keys `CONT:` / `MISC:` / `ACTI:` / `TERM:` / `TMLM:`.
  References on their own posed model or on a DOOR base keep that base and are counted as kept.
- Without `promote.json` the build is unchanged.

## Activation chains
FO4 wires "this switch opens that door" on the child: its activate parents block (exported since #305). Mutagen 0.55
Starfield has no activate parents on a reference (docs/terrain/garage-button.md), so PluginSpike (ActivationChains.cs)
writes the Starfield-native wire the core's garage button uses (#303): the parent reference gets vanilla
`DefaultActivateLinkedRefOnActivate` (LinkedRefKeyword = LinkCustom02 0005D5E7) and a linked reference with that
keyword to the child. Only parents the player can use get it: promoted activators and terminals, and opening doors.
Left unwired and listed in `<output dir>/activation.json`: a parent not in the build (FO4 trigger volumes and pressure
plates have no model), a parent that is not usable, a parent driving several children (the script activates one), a
parent that already has a script. FO4's delay and its "parent activate only" flag are not carried (counted). Whether the
child responds depends on the child: a rigged door opens; a promoted activator with no animation does nothing visible.

## How to run (PC build, before PluginSpike)
```
python scripts/terrain/port_promote.py --out <staging>\promote.json ^
  --containers-table scripts/terrain/clusters/container_table.json --items-table scripts/terrain/clusters/item_table.json ^
  --names <export-names.json> --starfield-data <Starfield Data> <the same cell exports PluginSpike gets>
```
Then PluginSpike as before; its log prints `promotions: ...; N listed but not placed`.

## Checks
- **verified offline**: dotnet/PluginSpike.Tests (end to end with a synthetic Starfield.esm terminal template) and
  tests/test_port_promote.py.
- **unresolved until in game**: open a promoted container, take a promoted item, read a promoted terminal indoors.

## Furniture (chairs, beds): research step
Starfield's FURN and FO4's FURN carry the same marker block (Mutagen 0.55 reflection, both games: MarkerParameters
Offset / RotationZ / Keyword / EntryTypes, MarkerEntryPoints, MarkerModel) (**verified** on the Mutagen schema, not on
records). The plan (**supported hypothesis**): a chair keeps FO4's own marker places and takes the rest of the block
(furniture template, marker model, keywords, animation graph) from a vanilla Starfield chair of the same kind. Two
read-only dumps choose the mapping from evidence, run on the PC:
```
dotnet run --project dotnet/Fo4Land -c Release -- <Fallout4.esm> export-furniture <out>\fo4-furniture.json
dotnet run --project dotnet/SfInspect -c Release -- <Starfield.esm> furn Chair 40 > <out>\sf-furn-chair.txt
```
(also `furn Bed`, `furn Couch`, `furn Bench`, `furn Stool`).

## Not in this change
- Chairs and other sittable furniture: waits for the two dumps above.
- Pressure plates and trigger volumes as chain starters, parents with several children, delays: open. Door locks and
  door behaviour: the door review (another thread).
- Crafting benches indoors (the core's bench path needs Fallout4.esm's WBDT).
