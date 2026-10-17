# Cell placement export, version 2

`dotnet/Fo4Export` exports placement data from the user's Fallout 4 installation.
JSON stays outside this repository. Version 2 adds `schema_version: 2` at the top
level; existing `cell`, `formkey`, `refs` and placement fields keep their meanings.

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
