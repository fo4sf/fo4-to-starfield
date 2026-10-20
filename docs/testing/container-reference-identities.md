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

### Full-size private author validation (October 15 Mountain / October 16 UTC)

At source `105a10ca51c083a7136867e6ea1c3ee41286eadf` (PR150 plus PR153), a separate candidate built from pinned
core64c inputs preserved all **648,358 source REFR IDs** and **11,769 original base IDs**. The promoted source
`19EE52:Fallout4.esm` keeps REFR `069435`; its new CONT is `0A2AA5`. The actual plugin contains 664,231 major records:
664,228 original records are byte-identical, and the only changed originals are TES4 HEDR and the promoted REFR's
NAME. Every other promoted field, all original physical group paths and all 3,492 original group headers match.
Exactly one CONT and one top-level CONT group were added; the Mars plugin is byte-identical. The separate pinned
PR146 reader passes container inventory, name/model, transform/scale, active temporary placement and world/cell
checks, with zero baseline ID changes/missing keys. That reader still requires its final peer source review.

The verified 2 GiB managed-heap run hit OOM and is retained. A fresh verified 3 GiB run completed in 18.02 s with
2.82 GiB sampled peak working set. These are bounded author observations, not comparative performance claims.
Initial verifier failures are retained: its HEDR count assumptions were wrong. The final check proves the count
delta of +2 against the added major/group. An inherited -3 difference from the simple absolute framing-count
formula remains unresolved and unchanged; this validation does not establish that formula or repair the baseline.

Private evidence: `test-plans/core64-identity-validation-20261015`. Candidate plugin SHA256
`53a11f9edf235288259e8d703d488343be5141c125302e08c7f166d390472e7a`; map SHA256
`a1f3f98925b978dfe73fea6d552cad5ce23ea267725f7939efe38e4dcc74883e`.
All five production source files were rechecked unchanged. No Data-tree copy, deployment, controller input or
save change occurred. Independent peer QA, lead integration and newly pinned native tests remain required.

Claude owns the canonical writer, staging and game. Review this companion diff, regenerate a separate candidate
from the same ordered export and templates, compare **all** baseline source IDs and serialized records, audit the
CONT/REFR bindings and pin new plugins/maps/plans before any native test. R05's old `020A2AA5` kit target belongs to
the shifted build and must be regenerated from the new map. Preserve old stages, failures and saves. Existing saves
from the shifted build are not made compatible by this proposal.

This reserves promotion slots within the same ordered export. Reordering/changing the base/terrain/export inputs,
or preserving already-promoted base IDs across later promotions, still needs a persistent allocator and migration
policy. Native activation, physics and save/reload behavior remain unverified; full-size resource observations above
apply only to this isolated candidate and these pinned inputs.
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

### Loose-item integration after PR235

The shared `promoted_edid` now applies this identity rule to both CONT and MISC.
Both callers compare the complete canonical source key before sharing an editor ID;
an injected hash/name collision is refused even when all gameplay metadata agrees.
Existing Fallout4.esm names, reference-only R05 names and ASCII case-only sharing remain.
The new synthetic item writer checks three formerly colliding plugin pairs and preserves
all original REFR IDs, non-NAME bytes, flags and cell parents. This does not migrate
already-aliased saves or supply persistent promoted-base IDs across changed exports.
PR235's independent malformed-output checks are a separate follow-up.

### Current-main integration, October 18

Main now routes activators, terminals and workshops through the shared naming helper too. The merge preserves those callers. Previously colliding punctuation/extension pairs must produce distinct bases while retaining reference slots; injected name collisions must still be refused. The compiled writer controls exercise CONT/MISC plus ACTI/TERM/workshop records and terminal menu identities. This remains synthetic identity evidence, not native interaction or a migration of previously aliased saves.
