# Persistent terrain record identities

Codex implementation for [R02 / #226](https://github.com/fo4sf/fo4-to-starfield/issues/226), built on the
[recoverable publication proposal](terrain-output-publication.md). Source proposal; independent review and
production-scale/bootstrap/native save validation remain pending. Nothing is deployed by this writer.

The actual synthetic writer previously swapped reference IDs when references were reversed, shifted every
existing reference after an insertion, swapped base IDs when bases were reordered, and moved an existing
CONT base when an earlier container was promoted. #150's original promotion slot guarantee did not cover
these changing-export cases. Merely sorting the next export cannot preserve already-issued identities.

## Enable and bootstrap

Add `"persistent_ids": true` to the private stage's `overlays_params.json`. A new, empty output stage creates
`terrain-stable-ids.json`. Keep that ledger with the source stage, its backups and future rebuilds. A normal
build with published outputs but no ledger is refused. Turning the option off beside an existing ledger is
also refused, including a ledger directory or symbolic link. Legacy stages with no ledger retain their old
allocation behavior until explicitly migrated; this feature does not automatically migrate the installed game.

For an existing stage, use its **original pinned inputs** and a compatible writer:

```powershell
dotnet run --project dotnet/TerrainOverlays -c Release -- <Starfield.esm> <stage> --bootstrap-identities
```

The option must still be enabled. The writer prepares all outputs privately, then requires their SHA256s to
match every published plugin/map/optional Mars companion exactly before saving reservations. A reordered,
changed or partially missing baseline cannot seed a new ledger. An existing ledger cannot be overwritten by
bootstrap. If a newer writer cannot reproduce old bytes, this bootstrap refuses; a separate reviewed migration
is required. This does not repair saves made with previously shifted IDs.

## Identity and recovery contract

- One 24-bit allocation space covers anchors, WRLD/SFBK/LCTN, exterior/persistent cells, COC markers, converted
  bases, source REFRs, promoted CONT/MISC bases and NAVM pieces. Existing keys retain their IDs; new keys append above
  the high-water mark. Removed keys remain reserved, so reintroduction recovers their old IDs.
- Keys encode separate semantic parts as JSON arrays, avoiding delimiter ambiguity. Source identities preserve
  the complete six-digit local ID and full plugin filename, punctuation, extension and non-ASCII spelling.
  ASCII case is canonicalized; invalid source identities are refused. World/base EditorID changes are semantic
  key changes, not automatic renames. No asset-content hash or export array index stands in for source identity.
- A NAVM identity is world + source record + cell. A second piece with that same identity is refused rather than
  silently assigned an array-dependent suffix. Supporting multiple such pieces needs a producer-provided stable
  discriminator. Array-index edge links are resolved through the newly selected persistent NAVM keys. Existing
  raw NVMI/world-link serialization is unchanged; the current writer still assumes its existing master layout.
- Explicit anchor IDs must agree with their reservations and cannot collide with any prior ID. New overlays
  need unused anchor IDs; the old producer's positional anchor numbering is not a migration policy. Duplicate
  keys/IDs, malformed keys, checksum failures, unknown schemas and exhausted IDs refuse before publication.
- The ledger includes checksums of the complete old/prepared output bundles. On reopen, the actual bundle must
  match one accepted generation. This detects a valid ledger accidentally copied from a different output stage;
  it does not authenticate an adversary who rewrites the entire stage and its metadata. Bundle membership changes
  require a separate migration rather than silently omitting an old output.
- The writer holds the publication lease throughout planning and saving. It flushes and replaces the ledger
  **before** publishing any plugin/map. A later failure retains reservations while publication restores the prior
  output bundle. Either complete old or complete new bundle may match the ledger; mixed files do not. A crash
  retains the publication journal, which blocks consumers/retries. Do not clear recovery markers to retry.
- A changed ledger or output observed during planning is refused and preserved. Pending ledger files are retained
  on failure. Other writers must honor the shared lease and immutable-input protocol; arbitrary concurrent edits
  are not a transaction API. Directory-entry durability across sudden power loss is not claimed.

The ledger is private build state, not a game asset or an installed game plugin. Existing publication receipts,
failed and passing evidence, and verified archives must be preserved before cleanup. No caller was changed to
enable the option on an active stage; Claude owns production integration and game control.

## Validation boundaries

Actual-writer synthetic tests cover reordered/inserted/removed/reintroduced references, reordered bases, later
container promotions, expanded cell grids, byte-preserved NAVM records across navmesh reorder/promotion, exact
bootstrap success/refusal, corrupt/missing/foreign ledgers, full source-plugin keys, rollback after reservation,
abrupt exit and externally changed ledger preservation. Prior promotion-state checks remain included. The
publication merge also stages the current writer's NAVM-only `formids.json` through the same bundle protocol.

These fixtures are small and synthetic. They do not prove full-size memory/performance, native exhausted-ID
header behavior, historical production migration, engine loading, doors, physics or save compatibility. Peer QA
must review the merged publication path and allocator together before integration. A fresh pinned native
campaign and explicit save/reload tests remain Claude's responsibility.

## Loose-item integration

MISC bases use the semantic key `["item", editor_id]`, separate from containers and
static/door bases. New reservations must pass the same key-schema check as reopened
ledgers, so an omitted identity cannot be published and then rejected on the next build.
Item IDs survive reordered entries, later container promotion, insertion, removal and
reintroduction. Existing legacy item stages still require byte-identical explicit bootstrap.

The caller must provide collision-free source-derived editor IDs; PR176 extends that
rule to CONT/MISC. This allocator cannot split distinct sources already aliased to one
editor ID, nor repair a ledger produced by an unreviewed caller using unnamed keys.
Preserve such stages for investigation instead of deleting the ledger or resetting IDs.

## Scripted door integration

The scripted-door writer's ACTI bases use `["door-base", editor_id]`; each return marker uses
`["door-arrival", full_source_formkey]`. Door REFRs keep the existing source-reference keys.
With persistent mode enabled, door reordering, adding another base/marker and removing then
reintroducing a door preserve all existing IDs. The whole source plugin identity distinguishes
equal local IDs belonging to different source masters. Removed reservations are never recycled.

Legacy mode retains its allocation order and bytes, including its reorder hazard. Existing
legacy door outputs still require explicit, byte-identical bootstrap before persistent rebuilds.
This integration does not enable persistence in an active stage or change door transforms,
VMAD properties, physics or script behavior. The scripted staging/raw-patch findings on PR261,
independent integration QA, full-size bootstrap and native return/save/reload remain gates.

## Mixed promotions and lights

Ordinary ACTI, TERM and TMLM records use `activator`, `terminal` and `terminal-menu`
keys with their editor IDs. LIGH bases use `light-base` with the editor ID; light
REFRs use `light-reference` with the full canonical source FormKey. Their separate
namespaces prevent ordinary activators from sharing a scripted-door reservation.
All existing reservations, including removed ones, remain occupied when more of
these records are exported or the export order changes.

The integrated legacy writer retains main's order through the lights: ordinary
promotions, NAVMs, light REFRs, LIGH bases, then scripted-door bases and arrivals.
promotions, NAVMs, light REFRs, LIGH bases, then scripted-door arrivals and bases (the current main writer order).
Its mixed-output checker counts ordinary and door ACTIs together and checks door
VMADs/arrivals separately. Sequential ordering remains required in legacy mode.
Persistent checks use the held reservation audit described below instead, while
retaining raw record checks. Full-stage caller validation, independent QA and
native saved-game validation remain required before enabling persistence in an
active stage. Explicit bootstrap must reproduce the entire plugin and map.
VMADs and persistent arrival placement with main's raw checks. These ordering checks still describe legacy allocation;
they are not a persistent-rebuild checker. Production caller/checker integration
and native saved-game validation remain required before enabling persistence in
an active stage. Explicit bootstrap must reproduce the entire plugin and map.

## Audit an existing published identity generation

The source-only `--check-identities` command validates a completed persistent
stage without loading Starfield.esm or rebuilding any artifact:

```powershell
dotnet run --project dotnet/TerrainOverlays -c Release -- --check-identities <stage>
```

It requires explicit `persistent_ids`, a complete published output bundle and an
existing ledger. It takes the writer's temporary coordination lease; an existing
lock or pending recovery journal is refused and preserved. The lease disappears
when this command finishes. Plugin/map/ledger/source bytes are not changed, and
the command never bootstraps, repairs or resets identities.

The producer's existing reader checks the ledger schema, checksum, reservations
and accepted output hashes, including a declared Mars companion. Reusing that
reader avoids reproducing .NET's JSON escaping/checksum rules in another language.
The audit compares mapped source references, promoted bases/menus, scripted-door
arrival markers, lights and NAVM source/cell identities to those reservations.
Terrain keys must exist and anchors must agree with parameters. Removed IDs may
remain reserved. Reordered sources do not need sequential IDs. Duplicate JSON
properties, mismatched source/map sets and changed inputs/outputs are refused.
Inputs must be ordinary files within the stage; linked or external input paths
are not accepted by this audit.

This is an identity audit, not a raw-record or gameplay verifier. Its JSON report
explicitly marks `record_fields_checked` and `native_acceptance` false. Keep raw
record/transform/VMAD checks, full-size validation and native return/save/reload
tests. Invoking this standalone command does not replace the normal check. The
normal checker integration below is source-only and still needs independent QA
and full-stage validation before production use.
tests. The legacy core64c checker still has sequential-order assertions; invoking
this audit alone does not replace them or enable persistent production rebuilds.
Independent QA and caller integration remain pending.

## Workshops and native crafting benches

The main7200aa5 integration adds `workshop` reservations by base EditorID.
Each placed workshop and bench retains its full source `reference` reservation.
Bench bases remain vanilla Starfield FURN FormKeys; they do not consume local
base IDs. The audit checks each bench's source, kind and master-owned base,
including the writer's accepted hex padding and case-insensitive master name.
Legacy light/door checks exclude those external base IDs from local allocation.

Mixed synthetic builds cover workshops, benches, ordinary promotions, lights
and a scripted door. Reordering and adding/removing/reintroducing stations must
preserve every old door reference, base and arrival ID. Explicit migration still
requires byte-identical plugin and map output. This does not migrate core64i or
establish native crafting, door travel or saved-game behavior.

## Preserve the checked input generation
The current-main merge retains six named VMAD properties and places exterior arrival
markers in the world persistent cell. New legacy outputs match that main writer;
existing ledgers retain their prior base/marker numbers even if the historical
allocation order differs. This identity continuity does not validate an existing
save against changed record contents. Native return and save/reload remain unverified.

`make_core64c.py check` records SHA256 and length for its parameters, objects,
ID map, plan, expected results, declared NAVM input and (when enabled) persistent
ledger. Inputs must be ordinary files within the stage. Their receipts must match
at the beginning and end of the check, before a passing report is published.

`verify-data` compares those contents before and after inspecting the existing
asset/plugin size-and-time inventory. Rewriting an ID map at the same size and
timestamp no longer reports an unchanged checked tree. Missing/unknown receipts,
missing inputs, unresolved publication controls, ambiguous paths and a ledger
with persistence disabled are refused; verification never rewrites a report.
Legacy allocation is supported with a new content receipt. Old metadata-only
receipts require a fresh `check`; they are not silently upgraded or accepted.
## Map-marker reservations

These receipts establish input freshness, not semantic ledger validity or native
acceptance. The .NET identity audit and the normal check's raw-record checks
remain separate requirements. Source stages must remain immutable under the
cooperating-writer protocol; repeated hashes are not an atomic snapshot against
arbitrary simultaneous edits. Asset payloads retain their existing metadata
checks.
Map-marker REFRs use `["map-marker", world, tag]` with the ledger's ASCII case folding.
The default empty tag is published as `RedRocket` and uses that same key, so switching
from the default marker to an explicit RedRocket entry retains its ID. Duplicate
canonical tags within one world are refused before publication. The same tag in
another world has a separate reservation. Reordering, growth, removal and later
reintroduction retain existing marker and door IDs; removed marker IDs remain reserved.

## Hold the audit through normal raw checks
Legacy allocation still follows main's marker order and explicit bootstrap must
reproduce its plugin/map bytes. The first-marker alias in `map_markers` follows the
current source order; stable identity comes from `map_marker_refs` tags, not that alias.
The identity audit checks both declared map sections together, all world/tag keys,
their ledger bindings and the first-marker alias. Older or template-free generations
without those sections remain supported; that is not proof that map markers were
written. Record fields, display, discovery and travel still need the raw checker
and native testing. This change neither enables persistent IDs on a live stage nor
wires the paired exterior/interior allocator requested in #280.

For explicit persistent mode, `make_core64c.py check` starts the current writer's
`--check-identities-held` process. It proves the existing identity generation,
emits `ready` and holds the producer's publication lease while Python performs
raw checks. Only sequential reference/base/NAVM/light ordering assertions are
replaced by reservation proof. Record types, counts, transforms, cell membership,
door VMADs/arrivals, dependencies and core comparisons remain checked.
## Flora compatibility with current main (October18)

After raw checks, Python requests `verify`. The audit rechecks the original
source/map/parameters, ledger and output generation before releasing its lease
and emitting `verified`. Python requires that matching response and exit zero
before publishing reports. EOF cancels; timeout, child exit, changed inputs or
publication controls prevent report replacement. Cancellation ends only the
helper process created for this check and does not clear recovery controls.
Legacy mode retains its existing order checks without starting an audit process.
Harvestable FLOR bases reserve `["flora", editor_id]`; each placed plant keeps
its full-source `["reference", source]` reservation. Flora participates in the
same promotion order as main, alongside the existing bench lookup and door
allocations. Shared bases reserve once, while placements retain distinct IDs.
The identity audit checks the declared flora map and its ledger bindings. It
still reports `record_fields_checked: false`: it does not validate harvest
contents, native harvesting or saved-game compatibility.

The lease excludes cooperating producer writes to the audited stage; it does
not lock external core inputs or hard-linked Data assets against arbitrary edits.
Those inputs still require the immutable-input protocol. A report records the
checked generation, not a guarantee that no later write can occur; `verify-data`
must still validate freshness before use. The identity subreport correctly keeps
`record_fields_checked` and `native_acceptance` false; raw results are separate.
Six synthetic-writer regressions cover reorder/growth/removal/reintroduction,
shared bases, explicit byte-identical legacy bootstrap, invalid-ingredient
publication preservation, and a changed declared base rejected by the read-only
audit. Three independent main-writer comparisons preserve exact legacy plugin
and map bytes for the default seed, a custom ingredient and a shared base.
Existing ledgers are neither rewritten nor migrated automatically; reading a
ledger containing flora reservations requires the updated writer/auditor. No
production stage, installation or paired interior/exterior allocator is enabled.

Nine session regressions use the actual synthetic writer/audit and raw promotion
checks, including retained door IDs, writer exclusion, missing VMAD, input drift,
cancellation and an audit crash. Wrapper tests stub the terrain check body; they
do not establish that a complete production terrain `check` passes. Full-stage
validation, full-size bootstrap, peer QA and Claude's native door/save tests
remain gates. No active stage is enabled or migrated by this change.

## Compatibility with the persistent return-marker writer

The integration of identity stack `c909301` with return writer `3446a99`
retains both source-keyed `door-arrival` reservations and the return writer's
world-persistent cell. Selecting either side of their allocation conflict alone
would lose one requirement. The arrival marker keeps its ID, DATA and source
identity while acquiring the persistent flag and the anchor's parent cell.
Both door writers now emit `UseDestinationPosition=True` with their three
coordinates. The combined branch includes the reviewed script `9ffce95`, and
the property-name/type contract runs against that script without skipping.

On the retained two-door fixture (with lights and a container), the combined
legacy writer produces exactly the return writer's plugin and map bytes.
Explicit identity bootstrap preserves both files byte-for-byte. Reordering
doors and lights then preserves every mapped ID; raw marker flags, group
placement and VMAD values still pass, and the read-only audit proves all27
reservations. The bootstrap regression checks marker placement before migration,
after migration and after reordered export. Different destination coordinates,
including zero, remain attached to their source doors; their VMAD bytes remain
identical across reordering. These record-field checks are separate from the
identity-only audit, which correctly keeps `record_fields_checked` false.

This is synthetic compatibility evidence. The earlier full-size core64j result
belongs to `c909301`; it is not validation of a newly rebuilt core64l or later
stage. Combined peer QA, a fresh full-size migration and native return/save
tests remain pending. Enabling the coordinate correction closes the earlier
writer/script contract gap; it does not prove that a far SetPosition succeeds.
The native test must pin the PEX actually packaged in the active archive and
check the resulting position, world/cell, facing and saved state.
A mixed-door regression adds/removes flora while preserving every existing identity
map and the raw records of door bases, references and arrival markers. A separate
main legacy countercontrol demonstrates the expected base/arrival renumbering on
growth; the persistent ledger avoids it. This remains an offline identity check.
