# Preserve reference slots during container promotion

Codex proposal, stacked on Claude's PR134 at `6d7bd988`. Source-only, offline tested; peer QA and lead integration
are required. No production stage, installed plugin, controller or save was changed.

PR134 removed promoted sources from `refs` before the terrain writer assigned sequential IDs. Appending a CONT
and a new REFR afterwards did not preserve the omitted slot: 235,119 later references in core64d shifted relative
to core64c. The independent review and PR146 audit preserve that failure; the old core64d artifacts remain pinned.

`cluster_containers` now emits each promotion's zero-based `reference_index` in the original, unfiltered placement
list. This is one integer per promoted source. `ReferenceIdentityPlan.Order` reconstructs that order, refusing
missing/duplicate/out-of-range indices or source aliases. TerrainOverlays reserves those REFR keys after the
unchanged STAT/DOOR bases, emits ordinary references at their reserved keys and uses the promoted source's existing
key for the container's REFR. Only new CONT bases consume keys after the original reference range. The declared
`formids.json` shape stays the same; a promoted source lives in `containers`, with its original `ref` value.

The core check verifies declared slot consistency. Actual serialized reference bindings, data and placement still
require raw/typed artifact checks, including the independent container auditor; declaration consistency alone is
not acceptance. Legacy container input without original indices is refused and must be regenerated from the source
placement list. Regenerating a failed identity input preserves an existing plugin/map in the synthetic controls.

## Evidence

- The real parent writer fails the middle-promotion regression: the later source inherits the removed source's ID.
- The real proposed writer passes four serialized scenarios: first, middle, last and multiple/reversed promotions.
  Every source REFR ID is preserved; ordinary REFR bodies/flags/cell ownership are identical. A promoted REFR retains
  its non-NAME data, flags and cell ownership, with NAME pointing to its new CONT. All new CONT keys follow the old
  record range. The no-cluster plugin is byte-identical to the parent writer's complete output.
- Five ambiguous-input scenarios refuse publication and preserve existing plugin/map bytes. Per-attempt input and
  logs are retained. Initial synthetic fixture failure (missing anchor fields) and the corrected run are retained.
- 29 producer tests plus three actual-writer test methods pass. The latter use a three-record synthetic master
  created by `dotnet/TerrainIdentityFixture`; no game data is read or copied. .NET 9 SDK/runtime is required; those
  methods skip explicitly where unavailable. Release builds pass with the existing CA1831 inventory-parser warning.

```powershell
python -B -m unittest discover -s tests -p test_make_core64c.py -v
python -B -m unittest discover -s tests -p test_terrain_reference_identity.py -v
```

Private evidence is under `test-plans/container-reference-identities-20261015`. Set
`FO4SF_IDENTITY_EVIDENCE_DIR` to a new scratch directory to retain synthetic test artifacts.

## Integration gates

Claude owns the canonical writer, staging and game. Review this companion diff, regenerate a separate candidate
from the same ordered export and templates, compare **all** baseline source IDs and serialized records, audit the
CONT/REFR bindings and pin new plugins/maps/plans before any native test. R05's old `020A2AA5` kit target belongs to
the shifted build and must be regenerated from the new map. Preserve old stages, failures and saves. Existing saves
from the shifted build are not made compatible by this proposal.

This reserves promotion slots within the same ordered export. Reordering/changing the base/terrain/export inputs,
or preserving already-promoted base IDs across later promotions, still needs a persistent allocator and migration
policy. Native activation, physics, save/reload behavior and full-scale resource use remain unverified.
