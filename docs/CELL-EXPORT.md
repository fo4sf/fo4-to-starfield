# Cell placement export, version 3

`dotnet/Fo4Export` exports placement data from the user's Fallout 4 installation.
JSON stays outside this repository. Version 2 added `schema_version: 2` at the top
level; existing `cell`, `formkey`, `refs` and placement fields keep their meanings.
Version 3 (`schema_version: 3`) adds the cell-level location data described under
"Cell data, location and encounter zone" below; nothing else changed.

Each reference retains `formkey`, original base `type`, `base_editor_id`, `model`,
`pos`, `rot`, `scale`, and the numeric `disabled` mask. Positions remain Fallout 4
units, rotations radians, and scale defaults to one. Translation into Starfield
units occurs in the plugin writer, not this export.

Additional fields preserve source state for later translators:

| Field | Meaning |
|---|---|
| `base_formkey` | Original base record identity, even if resolution fails; null for a null link |
| `record_flags` | Full raw reference flags; `disabled` remains the original `0x800` mask |
| `persistent` | Reference belongs to the source cell's persistent list |
| `open_by_default` | Original default-open state |
| `enable_parent` | Reference identity and numeric enable-parent flags, or null |
| `activate_parents` | Numeric raw `flags` and ordered `parents` with source `reference` FormKey and original float32 `delay`, or null |
| `linked_references` | Ordered links, each with `keyword_or_reference` and `reference` identities |
| `teleport_destination` | Destination door, position, rotation, flags and transition interior, or null |
| `ownership` | Owner FormKey, no-crime setting and unknown numeric field, or null |
| `faction_rank` | Optional ownership faction rank |
| `lock_data` | Lock level, key FormKey, flags and unused field, or null |

Null links stay null; an empty linked-reference list stays empty. Relationships
keep source FormKeys rather than prematurely translating them into target IDs.
`keyword_or_reference` reflects the source format's union field; do not assume
every value is a keyword. Teleport transforms also remain in source units.

`activate_parents` preserves absent blocks as null and explicit empty blocks as
an empty parent list. Parent links may themselves be null; zero delays, ordering
and unknown flag bits are retained. Both the interior exporter and Fo4Land use
this shared serializer, including deferred actor placements. Existing exports
must be regenerated to acquire this previously omitted metadata. The current
ReferenceLinks translator reports each non-null activation block in `refs` as
untranslated, including references with no placed target. It does not infer
enable-parent/linked-reference substitutes or install activation scripts.
These blocks produce counted, listed warnings and permit default ReferenceLinks
output with fidelity `partial_with_warnings`. `--strict-activation-parents` instead
refuses output with exit 2; `--allow-unresolved` explicitly overrides that gate.
Neither mode implements the activation behavior, and other unresolved links
continue to block default output.

Exporting source state is separate from applying it in Starfield. ReferenceLinks
translates selected enable/link/teleport and door-state relationships and reports
unsupported cases; this export alone does not implement those behaviors.
Activation-parent translation, VM scripts and other unexported fields still
require separate work.

`deferred_refs` retains placements outside the current object conversion path.
Actor entries keep their base identity, position/rotation/scale, raw flags,
persistent state, enable and activation parents, linked references and ownership. Each has a
`reason` identifying why translation is deferred. Other unsupported placement
types retain at least their reference identity and type. The current plugin
writer does not consume this list; these entries do not spawn NPCs in Starfield.

`referenced_keywords` resolves linked-reference discriminators that are actual
source keyword records. It retains FormKey, EditorID, raw flags, type name/value,
color, attraction-rule link, resolved name text, notes and source display-name
metadata. Discriminators that are placed references stay references; their numeric
IDs are not used to guess record type. Name text uses the reader's resolved
language; exporting every localized string is still separate work.

`teleport_dependencies` identifies each source teleport's destination reference,
the cell actually containing it, its base FormKey, and its transition-interior
cell. Cell locations include FormKey, optional EditorID and worldspace FormKey
(null for interiors). This covers temporary and persistent placements, including
worldspace top cells. Missing destinations remain null and retain their requested
identities. Use these dependencies to plan neighboring-cell exports; this field
does not itself export those cells or implement their transitions.

Primitive geometry and bound half-extents also remain in source units in the
placement JSON. Primitive colors are explicit RGBA integer arrays.

## Cell data, location and encounter zone (schema 3)

Three top-level keys carry what the plugin writer needs to give every converted
interior a Starfield LCTN (`docs/terrain/interior-batches.md`, "Locations"):

| Key | Shape |
|---|---|
| `cell_data` | `{"flags": int, "name": string\|null, ...}`: the raw CELL DATA flags and FULL name, plus the sound, image-space, water and ownership keys under "Cell data: sound, image space, water and ownership" below |
| `location` | `null` when the cell has no XLCN; else `{"formkey", "editor_id", "name", "parent", "parent_chain", "keywords"}` |
| `encounter_zone` | `null` when the cell has no XEZN; else `{"formkey", "editor_id", "min_level", "max_level", "rank", "flags", "owner", "location"}` |

`parent` is the LCTN's PNAM FormKey or null. `parent_chain` walks PNAM up to the
root, in order, each entry `{"formkey", "editor_id", "name"}`; it is cycle-guarded,
and a parent whose record is not loaded ends the chain with
`{"formkey", "unresolved": true}`. `keywords` lists the LCTN's KWDA as
`{"formkey", "editor_id"}` (editor id null when unresolved); an absent KWDA is an
empty list. `flags` on the zone is the raw ECZN DATA flag word (NeverResets 1,
MatchPcBelowMinimumLevel 2, DisableCombatBoundary 4, Workshop 8); `owner` and
`location` are FormKeys or null. An XLCN or XEZN whose record is in no loaded
plugin (a missing `--master`) is kept as `{"formkey", "unresolved": true}` rather
than dropped, the rule `teleport_dependencies` already follows. Fallout 4 keeps
leveling only on the encounter zone, so a cell can carry any of the four
combinations; nothing is inherited from parent locations here.

### Cell data: sound, image space, water and ownership

`cell_data` also carries the cell's own atmosphere and ownership subrecords, the
inputs for the vanilla-family mapping of acoustic spaces, music and image spaces
(`research/framework/interiors.md`, section 3, L14 and L15) and for the owner the
combined core gives a place. These keys are additive within `cell_data`;
`schema_version` stays 3, and PluginSpike's `Locations.cs` keeps reading only
`name`. Every link is `null` when the subrecord is absent, `{"formkey", "editor_id"}`
when its record is loaded, and `{"formkey", "unresolved": true}` when it is not (a
missing `--master`), the same rule as `location` and `encounter_zone`.

| Key | FO4 subrecord | Mutagen property (verified by reflection, 0.55.0-alpha.67) | Starfield field it could feed |
|---|---|---|---|
| `acoustic_space` | XCAS | `ICellGetter.AcousticSpace` | CELL XCAS (verified: Starfield CELL has XCAS, interiors.md section 3). The FO4 ASPC itself cannot be copied: Starfield acoustic spaces reference Wwise events (verified), so the writer must pick a vanilla ASPC per FO4 acoustic family (L14, **hypothesis**: family grouping by editor id) |
| `music` | XCMO | `ICellGetter.Music` | CELL XCMO (verified: present on the Starfield CELL). Mapping to a vanilla MUSC by family is a **hypothesis**; which of cell XCMO and ASPC music wins is L16, unresolved |
| `image_space` | XCIM | `ICellGetter.ImageSpace` | CELL XCIM (verified: present on the Starfield CELL). FO4 IMGS cannot be converted field for field (Starfield IMGS is an opaque reflection blob, verified), so this feeds the choice of a vanilla IMGS per cell family (L8, **hypothesis**) |
| `god_rays` | XGDR | `ICellGetter.GodRays` | none: FO4 god rays have no Starfield record (verified). Exported so the family grouping can tell "hazy" cells apart; a VOLI or FOGV substitute is a **hypothesis** (L8, L9) |
| `water` | XCWT | `ICellGetter.Water` | CELL XCWT (**hypothesis**: not yet checked against the Starfield CELL definition) |
| `water_height` | XCLW | `ICellGetter.WaterHeight` (`float?`) | CELL XCLW (**hypothesis**, as above). The value is the raw FO4 float; whether FO4 uses a sentinel for "default height" is a **hypothesis**, not verified here. A non-finite height is written as `null` because JSON cannot carry it (Mutagen reads a NaN XCLW back as NaN; verified by the synthetic test) |
| `ownership` | XOWN, XRNK | `ICellGetter.Ownership` (`Owner`, `NoCrime`), `ICellGetter.FactionRank` | LCTN DATA ownership (verified: the Starfield LCTN DATA carries ownership, interiors.md section 4); whether the Starfield CELL also keeps XOWN is a **hypothesis** |

`ownership` is `null` when the cell has neither XOWN nor XRNK; otherwise
`{"owner", "owner_type", "owner_editor_id", "unresolved", "faction_rank", "no_crime", "unknown"}`.
`owner` is the XOWN FormKey or null; `owner_type` is `"faction"` or `"npc"` (both
implement Mutagen's `IOwnerGetter`; anything else is `"other"`) and null when the
owner is not loaded, in which case `unresolved` is `true` (null otherwise).
`faction_rank` is the raw XRNK integer or null; `no_crime` and `unknown` are the
XOWN flag and its unknown integer, null without XOWN. The shape is wider than the
per-reference `ownership` above (`{"owner", "no_crime", "unknown"}` with
`faction_rank` as a sibling key): the cell adds the resolved owner's type and
editor id and folds XRNK in, but every XOWN field the reference shape keeps is here
under the same name. Exports and `locations` sidecars written before this change lack
these keys; readers treat a missing key as the subrecord being absent.

### `locations` mode

```powershell
dotnet run --project dotnet/Fo4Export -- <plugin.esm> [--master <m.esm>]... locations <out.json> <EditorID>...
```

writes only those three keys for several interior cells of the plugin:

```json
{"schema_version": 1, "cells": {"<cell EditorID>": {"cell_data": ..., "location": ..., "encounter_zone": ...}}}
```

Each entry is exactly what the same cell's schema-3 export would carry.
`interior_batch.py` uses it to build `plugin/locations.json` for the pinned base
cells whose exports predate schema 3. A named cell that is not an interior of the
plugin fails the run (non-zero exit, nothing written).

Synthetic checks run with:

```powershell
dotnet run --project dotnet/Fo4Export.Tests/Fo4Export.Tests.csproj
```

They exercise the same serializer helper used by the exporter, with synthetic
references and no game installation. A separate local Vault 81 check exported
4,620 references with zero changes to the eight legacy placement fields. The new
data includes 408 persistent references, 130 enable parents, 96 references with
linked-reference lists, three default-open references and three teleport targets.
It also retains 33 deferred placements, 910 ownership entries and four locks.
These counts describe source data, not implemented gameplay behavior.
