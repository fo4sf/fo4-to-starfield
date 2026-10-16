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
