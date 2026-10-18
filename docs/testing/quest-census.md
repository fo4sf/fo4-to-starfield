# R07: static quest and script dependency census

Author: Codex. Offline read-only proposal; independent review pending. This inventories dependencies before deciding what to port. It does not translate Papyrus, enable quests or establish gameplay compatibility.

## Run and scope

Build `dotnet/QuestCensus` with .NET 9, then run:

```powershell
dotnet dotnet/QuestCensus/bin/Release/net9.0/QuestCensus.dll <source.esm> <selection.json> <new-report.json>
```

Selection accepts `cells` (full source FormKeys), `cell_editor_ids` (must resolve uniquely), `references` (full source FormKeys), and an optional `reference_map` path to a terrain map's `refs`/`containers` keys. Paths are relative to the selection file. Empty selections and malformed keys fail. Missing/ambiguous selectors produce an explicit incomplete report and exit 2. Existing outputs are never replaced. Source, selection and reference map are SHA256-pinned before scanning and checked again before writing; preserve the report with its exact executable/source revision. Run against a stable source snapshot, not a file being rebuilt.

The report contains source identities, EditorIDs, counts, script/fragment names and typed links, not dialogue prose, PEX bytes or assets. Keep full reports private. It scans one source plugin, not a resolved winning DLC/mod load order.

Relation meanings:

| Relation | Meaning |
|---|---|
| `explicit_cell` | The selected source cell itself |
| `reference_in_explicit_cell` | A source reference physically in that cell; not proof that every object converted |
| `selected_reference` | Exact full source key in the selection/map |
| `cell_with_selected_references` | A cell containing at least one mapped reference |
| `unselected_reference_in_partial_cell` | Context only: another reference in that cell, absent from the selected map |

Do not count the last two as converted references. Script rows separately include `owner_selection` so attachments on selected objects remain visible even without selected property links. The `script_instances` count includes script-entry **and fragment metadata rows**, not unique script files or executions. A script may appear at several owners/paths.

## Coverage and limits

- Quest typed links include aliases, conditions and nested data exposed by Mutagen; they are an aggregate, not a claim about which script instruction executes. Alias counts include aliases with no forced reference, whose runtime target remains unresolved.
- Script object properties and object arrays use typed FormLinks. Text that resembles a FormKey is not treated as a link. Full plugin identity prevents equal local IDs from different sources matching.
- Common/ indexed VMAD, quest fragments and alias scripts, dialogue, scene phases, package begin/end/change, and perk fragments are enumerated. Unsupported adapter/group types fail rather than silently skip. Deleted quests remain marked; deleted payload may be absent in serialized source.
- `static_scan_complete` means this declared traversal returned. `runtime_dependencies_resolved` always remains false. PEX instructions, runtime alias filling, computed lookups, quest state, external script source, transitive dependencies and other load-order plugins are not analyzed. Zero matches cannot establish that a quest is safe or irrelevant.

## Pinned October 16 observation

Source SHA256 `ae7be31a59052f926474a767d9dbfbcc7f19af4ad2070491f7f40d821b2520eb`; core64c map SHA256 `00e3e50e36de244c8c503174378d51e39aaa2594ecf57f7b8ddd4d879aabb1d7`. The explicit selection contains the 16 source interior names represented in integ_1011's Port map/exports plus core64c's 648,358 source references. Diagnostic DoorTest is excluded. These pins do not describe later core64g or the installed game.

| Observation | Count |
|---|---:|
| Major records traversed | 1,549,050 |
| Quests | 1,336 |
| Script-entry/fragment rows | 29,266 |
| Non-quest fragment groups | 2,648 |
| Quests with any selected/context match | 270 |
| Quests with selected cell/reference matches | 162 |
| Script rows with selected cell/reference property matches | 250 |
| Script rows attached to selected references | 1,066 |

The script-row counts overlap; do not add them. All selectors resolved. Final private report SHA256 `92c5890b030b65b66e398dbb52efc02934900e90dc35e8dad77474b8f4d8db20`. The initial report omitted non-quest fragments and is preserved as superseded, not accepted evidence. Examples such as MQ101/MQ102 and DialogueVault111 appear in the candidate dependency set; inclusion does not establish that those quests can run in Starfield.

## Verification and next gate

Six tests build entirely synthetic FO4 records and run the real executable. They cover direct versus contextual references, aliases, object arrays, ordinary/quest/alias/package scripts, fragment metadata, empty/deleted records, string bait, foreign-plugin IDs, missing selections, map pins, source immutability and output refusal. Initial failures exposed null optional quest sections and the incorrect common adapter interface; both are corrected. A deleted-fixture payload expectation was also corrected because the writer omits that payload. Failures and superseded reports are retained privately.

Before any scripted content ships: independently review this census, inspect the named dependency paths and corresponding PEX/source, build a source-to-target behavior plan, and validate quest state/aliases/events in a fresh pinned game campaign. Expand to the real winning load order if DLC/mod sources become in scope. This report is the inventory step, not completion of the quest milestone.
