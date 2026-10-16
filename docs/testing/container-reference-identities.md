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

## Full source-plugin grouping follow-up

Codex's synthetic review of merged PR167 at `0f128805` found that punctuation and extensions were removed from
plugin names before grouping. `04B6E9:Some-DLC.esm` and `04B6E9:SomeDLC.esm`, or `SomeDLC.esm` and `SomeDLC.esp`,
became the same CONT even when both sources were present. The actual writer emitted one CONT for each two-base
case. The disabled-reference refusal and shared name/inventory agreement checks passed; those are not regressions.

The helper retains existing names for alphanumeric `.esm` masters and the Fallout4 R05 reference-only fallback.
Other base keys use SHA256 of the entire source identity, including punctuation and extension,
in a separate `key_` namespace. Reference-only groups from other plugins use a separate `ref_` namespace. An
explicit source-identity comparison refuses even an injected key collision instead of trusting the digest alone.
ASCII case-only variants remain one group. Non-ASCII spelling is retained from the canonical source export;
Python Unicode expansions such as sharp-s to `ss` cannot alias a different plugin. This does not implement an
independent Unicode filesystem/ModKey name resolver. No C# writer, source reference allocation or map schema changes.

Three unit regressions fail on the parent; the new actual-writer method fails all three plugin-pair subcases there.
The corrected writer inputs produce two CONT bases while preserving every original REFR ID, non-NAME data,
flags and cell parent. Existing simple-master/R05 names remain covered. Evidence, including failed attempts, is
retained privately under `test-plans/container-key-review-167-20261016`; no game files are used.

Regenerate and pin a separate candidate before integration. This does not migrate an earlier mixed-plugin build
whose source bases were already aliased, nor guarantee stable previously-promoted CONT IDs when the set of bases
changes. Those require the persistent allocator/migration policy above. Peer review and native acceptance remain
separate; no installation or save was changed.
