# R05: the first semantic object cluster at Red Rocket (plan, not implemented)

Status (2026-10-14, Claude): a bounded implementation plan drawn from a read of the current writers (`src/fo4sf/exterior.py`, `dotnet/TerrainOverlays`, `dotnet/ReferenceLinks`, `dotnet/SliceDoor`), core64c's `objects.json` / `skipped.json` and a reflection probe of Mutagen.Bethesda.Starfield 0.55.0-alpha.67. Nothing here has run in game. Owner packet R05 of the 2026-10-14 handoff; persistent-ID choices to be coordinated with Codex (R02) before a save-bearing build.


Worktree pins: `...\scratchpad\integ1014`. V = verified (read/ran), H = supported hypothesis, U = unresolved.

> **Revision 2026-10-15 (after cave_probes_1015 / cave_fixA_1015):** two in-game results change section 2 and 3.
> (a) An add-on plugin's override of a core64c exterior cell (a child-less copy carrying new references) makes
> `coc FO4Core_RedRocketSpawn` land at (50, 50, 12.6), the centre of cell (0, 0), instead of the COC marker:
> verified twice (cave_core64c_1015, cave_probes_1015), absent without the override (cave_fixA_1015, the walks).
> So the "override of the master REFR" and "exterior cell override" items below are **out**. The cluster's records
> go into **core64c's own build** (make_core64c.py -> objects.json -> TerrainOverlays, which already writes STAT /
> DOOR bases and references natively): TerrainOverlays grows native CONT / MISC / ACTI / TERM / XPRM / XESP writing
> for a declared cluster, with the retained ID map (PluginSpike's identity-keyed formids.json) so the rest of the
> 648,358 references keep their ids. (b) Fix A (the vanilla persistent-cell shape) does not make our persistent
> references merge; the persistent-border item waits for the door bridge's answer (WRLD OFST / CLSZ next).

## 1. Cluster (12 refs, radius 21 m around the arrival (-989.26, 1146.51), SF cells (-10,11)/(-11,11))

| role | FO4 ref | base | why |
|---|---|---|---|
| CONT | `19EE52` Loot_Prewar_Medkit | CONT `04B6E9` | 6 m, 3 m off wp01; 1 LVLI |
| CONT + persistent-on-border | `03A785` Prewar_Cabinet_Garage_01 | CONT `049D9F` | flag 0x400, x = -999.3 (0.7 m east of x = -1000) |
| items | `066996` Stimpak, `157551` Newspaper01, `152DA0` Cram | ALCH/MISC | 7-11 m, MISC path is the generic one |
| TERM / ACTI | `048506` RedRocketTerminal, `056BBA` RedR_ButtonBox (persistent), `058813` loot_capsStash_tin | TERM `073255`, ACTI `05815F`/`03000C` | inside the shop, 20 m |
| trigger | `1A62DF` DefaultSetStageTriggerOnLeavePlayerOnly | ACTI `03252F`, box 13.1x7.6x3.2 | smallest, covers shop interior |
| XESP | `03A7B9` WoodCrate02 -> `03A793` WoodCrate01 (flags 0, same state) | STAT | only in-cluster pair; no opposite-state pair within 150 m (V, candidates scan) |
| border control | `1382B1` MetalTable02 at x = -1002.4 | STAT | straddles x = -1000 with `03A785` |

All but the trigger are already placed by core64c as temporary STAT (`exterior.py:25-26`, `TerrainOverlays/Program.cs:193, 222`, V), so their SF FormKeys exist in `formids.json["refs"][src]` (`Program.cs:223`, V). Drop the forecourt trigger `19EE49` from the first sitting (extent convention unchecked, H).

## 2. Where the code goes

A separate add-on plugin `FO4SliceRedRocketCore.esm` built the SliceDoor way, **extending the cave slice build** rather than a second plugin, because both would override persistent cell `001805` (H, Code Map). Do not touch TerrainOverlays: its `NewKey()` is a positional counter (`Program.cs:52-59`, V); any inserted base renumbers 648,358 REFRs and breaks `expected.json`.

Reuse:
- `SliceDoor/Build.cs`: `Open` overlays with `Inspect.Styles` (31-33), `WorldOnly` (38-43), `CellOnly` (46-58), the probe path that creates a child-less exterior-cell override with the master's block/sub-block numbers (141-160), the fixed-ID order check (161-163), `NextFormID` (191), masters/`KeyedMasterStyle` (195-197). All V.
- `ReferenceLinks/Relationships.cs:143-154` (XESP, flags masked to bits 0-1) and `114-119` (temporary->persistent + 0x400): copy the two snippets into a new `Build.Cluster(...)` step keyed by a `cluster` array in `slice_params.json`; do not call `Relationships.Apply` (it enumerates interior `mod.Cells.Records` only, line 28, V).
- Inventory/Value/Weight from Fallout4.esm via the already-referenced Mutagen.Bethesda.Fallout4 (SliceDoor csproj, V per Code Map), or via `src/fo4sf/fo4land.py` `iter_subrecords` emitted into `slice_params.json` by `make_cave_core64c.py` (keeps the C# dumb; preferred).
- Trigger bounds: read from `band_15_24.json` (`ReferenceExport.cs:21-27`, V) in the make script.

## 3. Record-level output

Add-on FormIDs: keep `0x800/0x801` door, probes `0x802-0x803`; cluster namespace **`0x810-0x83F`** bases, **`0x840-0x87F`** new REFRs, hand-fixed in `slice_params.json`, asserted in order like the probes. Never reuse a master ID; master REFRs are addressed by FormKey `(FO4TerrainCore.esm, formids.json["refs"][src])`. **Codex/R02 note:** R02's own IDs must stay out of `0x810-0x87F` of this plugin; if R02 wants a shared allocator, adopt PluginSpike's identity-keyed `formids.json` (`PluginSpike/Program.cs:34-46`, V) in the slice build, keyed by FO4 formkey.

Per object (Starfield record, Mutagen 0.55.0-alpha.67 classes V by the probe):
- **CONT** `Container{EditorID, Model(core64c path), ObjectBounds, Items[ContainerEntry{Item->Fallout4 LVLI is NOT resolvable}]}`: substitute a vanilla Starfield item (e.g. a MedPack FormKey) with `Count=1`; `Data: ExtraData` left null (untested path). Two REFRs: Medkit = **override of the master REFR** (same FormKey, swap `Base` to the new CONT, keep pos/rot/scale) in the `(-10,11)` cell override; Cabinet = master REFR override with flag 0x800 set (hide the STAT), plus a **new persistent REFR** (0x400) in the overridden `001805` persistent cell per fix A (`Build.cs:123-131`, `Check.cs:328-340`, V).
- **MISC/ALCH** `MiscItem{Model, Name, Value, Weight}` (ALCH also as MiscItem for sitting 1): base swap on the master REFR override.
- **TERM** `Terminal{Model, Name, Menu->TerminalMenu{BodyTexts:[one line]}}`; **ACTI** `Activator{Model, Name, ActivateTextOverride}`; `056BBA` as a disable+new-persistent pair like the cabinet.
- **Trigger** new REFR, `Base` = vanilla `Starfield.esm` LightBox/EnableMarker (`ReferenceLinks/Program.cs:237-239`), `Primitive{Bounds (/70), Type=Box}`, XESP -> WoodCrate01 so its state is observable; no XAPR exists (V), so it is geometry-only.
- **XESP** WoodCrate02 override: `EnableParent{Reference=WoodCrate01 FormKey, Flags=0}`. Add a second override `MetalTable02` with `Flags=SetEnableStateToOppositeOfParent` on the same parent, giving an opposite-state pair inside the cluster.
- **Persistent border**: cabinet (new persistent) vs MetalTable02 (temporary override) both listed as door_trip probes.

## 4. Offline checks

- Extend `ReferenceLinks.Tests`-style synthetic round-trip (`Program.cs:113-132`, V) to Container with Items, Terminal menu, primitive on an exterior temporary ref, override of a master REFR with changed Base.
- `SliceDoor check`: add asserts: every cluster ID in namespace and ordered; master-REFR overrides keep master pos/rot within 1e-4; persistent cell shape unchanged (33 -> ~45 checks); `NextFormID` = last+1.
- Read-back with `PluginReader` + xEdit-free dump of CONT/TERM/ACTI counts.
- In-game acceptance (record visual / collision / interaction separately, per the handoff): (a) coc arrival, screenshot cluster; (b) `<WoodCrate01>.disable` then `.enable`: WoodCrate02 follows, MetalTable02 inverts; (c) walk wp00->wp02 across x = -1000, read probes; (d) enter cave door, return; (e) open medkit, read terminal, press button; (f) save, quit, reload, repeat (b)-(e).

## 5. Runner / queue

- `door_trip` already does (a),(c),(d) and reads up to 8 `probes` by getpos (`testqueue.py:799-808`, V): list cabinet, MetalTable02, WoodCrate01/02.
- `console_pre/post` whitelist is `GetINI/SetINI/SetLocalTime/cgf/fw` only (`console_plan.py:21-23`, V): **extend** with `<8hex>.enable|disable|GetDisabled` and `<8hex>.getpos x|y|z` (one regex line + `test_console_plan.py` cases) to do (b) without a new kind.
- Interaction (e) and save/reload (f) have no runner step: first pass manual by the user; a later `interact` kind (walk to ref, press E, OCR the prompt) is the only new kind needed.

## 6. Open questions / risks

- V: TerrainOverlays renumbering; no `ActivateParents` in Mutagen; whitelist gap; `Relationships.Apply` interior-only.
- H: overriding a master exterior REFR from a child-less cell override is honoured by the engine; load-order bytes 02/04/05 (`make_cave_core64c.py:53-56`); a persistent REFR added to overridden `001805` merges (fix A still unseen in game, `door-frames.md:401`); vanilla LightBox as trigger base.
- U: does a Starfield CONT/ACTI/TERM with an FO4 model (no Components/animation graph) accept activation; do FO4 LVLI-less containers show an empty but openable menu; whether disabling the master STAT via override leaves collision behind.