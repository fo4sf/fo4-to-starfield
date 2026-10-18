# Independent container output evidence

`scripts/testing/container_records.py` audits the native container entries emitted
by the current TerrainOverlays cluster writer. It reads completed, immutable
staging inputs and writes a new private report. It never installs or starts a game.

```powershell
python -I -B scripts/testing/container_records.py `
  --plugin <candidate>/FO4TerrainCore.esm `
  --objects <candidate>/objects.json `
  --ids <candidate>/formids.json `
  --baseline-ids <previous>/formids.json `
  --out <private-new-report.json>
```

The output directory must exist. An existing report or input path is never
overwritten. Exit0 means the requested offline comparisons passed, exit1 means
a mismatch or invalid evidence, exit2 means the report could not be published.
Every result has `runtime_accepted: false`.

Use `--kind items` to audit loose MISC items; the default remains `containers`.
Each report names its `audit_kind` and verifies that class's records only. A mixed
stage needs separate container and item reports. MISC checks compare exact
eight-byte DATA value/weight, finite float32 weight, editor ID/name/model, reference
binding and the same placement/state/ancestry checks described below. Expected
weights are rounded to the serialized float32 representation before comparison.
Missing, duplicated, truncated or oversized DATA fields fail.

Declared reference identities include ordinary refs and both promoted classes,
even in a single-class audit. Duplicate identities across classes or shared
CONT/MISC base IDs fail. Optional baseline comparisons preserve both classes'
existing promoted bases. This catches map aliasing; it does not prove that a caller
derived distinct editor IDs from distinct full source plugin identities (PR176),
or that an item can be picked up in game.

Item mode has eight synthetic methods, including nonfinite transforms/weights,
malformed DATA, invalid expected values and mixed-map aliases. Three CLI controls
against preserved actual-writer synthetic outputs pass: mixed containers, mixed
items and items-only. No game files or new stage builds were used.

Checks bind each source container to its mapped CONT/REFR pair using the actual
TES4 master order. They compare editor ID, inline Windows-1252 name, model path,
CNTO inventory entries, reference base, finite local position/rotation, scale,
active temporary placement, actual world/cell ancestry and cell grid. There
must be exactly the declared number of placements for each unique container base.
The CONT, REFR and the actual owning CELL/WRLD must not carry the Deleted flag.
Four synthetic header-only mutations previously passed despite deletion; they now
fail with an explicit record-state reason. The bit is verified against the pinned
Mutagen `0.55.0-alpha.67` SDK: `StarfieldMajorRecordFlag.Deleted == 32`, and a
synthetic `PlacedObject` with raw flags `0x20` has `IsDeleted == true`. This is an
auditor regression, not a claim of deletion in the installed game. Deletion on an
unrelated record is outside the container-state check.
Multiple entries may share one CONT, but every source keeps its unique REFR and
every entry's requested name/model/inventory and transform is checked. The report's
`containers_checked` counts placements; `container_base_records` counts actual CONTs.
Duplicate record IDs, aliased/missing reference IDs, base/reference overlap, duplicated source entries and ordinary placements
that still list a promoted source fail. Localized string-table plugins are
unsupported and fail rather than guessing their names.

The encoding is verified from an independently serialized Mutagen fixture:
`Café boîte` has FULL bytes `436166e920626fee746500` at offset157.
The fixture also verifies MODL and eight-byte CNTO fields. The initial reader's
UTF-8 assumption failed this positive control. Initial QA also found acceptance
of a reference physically in another world and an unknown field whose length
exceeded its CONT record. Physical ancestry and strict subrecord bounds now
reject those cases. All three independently authored controls pass when rerun
by Codex; final peer re-review remains pending after the QA agent hit its usage
limit. This is not an independent final approval.

With `--baseline-ids`, the declared base/reference maps are compared too:
surviving identities cannot change or disappear. Ordinary and promoted reference
maps are combined before comparison, so promotion cannot hide a shifted source
REFR. Previously promoted sources must also retain their CONT base IDs and type;
regrouping them requires an explicit migration outside this auditor. This is a comparison of
the **declared maps**, not proof that every ordinary static's bytes/transform
are unchanged. Retain the existing full reference and dependency checks.
Without a baseline, `baseline_maps_checked` is false; a passing container-pair
audit must not be described as preserving previous identities.

The report pins exactly the bytes read from each input. A report does not prove
that a mutable path or an installed game still contains those bytes. Preserve
the report and revalidate deployment/campaign pins before a native launch.
No IDs are repaired, no source metadata is invented and no old native result
is rescored.

The original PR134 core64d candidate (plugin SHA256
`0957a285a9e998631a3b6a8562a5384412b7be5261111368ac942f7d9160a7e7`)
has one matching container pair, but the baseline comparison fails on235,119
surviving ordinary reference IDs in the original audit. That preserved result is
not rescored; the updated comparison also includes promoted-source IDs. Counts alone had accepted
changed container XYZ/base/scale and missing inventory; synthetic byte-level
controls now reject those changes.

This is complementary offline evidence. External inventory form types, asset
dependencies, animation, activation, physics, merged runtime positions,
save/reload and persistent inventory behavior need their own evidence. Claude
owns the producer/caller integration, corrected allocation and native tests.

## Shared-base and promotion regression evidence

Three new regressions failed on7a3e7a2: a valid shared base was rejected; a promoted
REFR could change ID unnoticed; a previously promoted CONT base could change unnoticed.
All17 focused tests pass after correction, including conflicting shared metadata,
missing/extra placements and reference aliases. The updated CLI also accepts the
retained full-size150/153 candidate with zero shifted/missing IDs, accepts167's
actual equal-metadata synthetic output (two REFRs/one CONT), and rejects its two
first-entry-wins name/inventory outputs with specific metadata errors. Inputs and
earlier reports remain unchanged; no producer or native game was run.

Final independent source review remains required. These checks cannot reconstruct
omitted canonical FO4 base identities, prove every ordinary record's bytes, or
establish native activation/save compatibility.

## Mixed-class map identity integration, October 18

Declared source-reference uniqueness and optional baseline reference comparisons now include ordinary refs plus containers, items, activators, terminals, workshops, flora, benches and doors. A selected CONT/MISC base cannot overlap any of those source references or another declared plugin-owned promoted base. Baseline base comparisons also include the plugin-owned promoted classes. Vanilla bench base keys remain full external FormKeys and are not interpreted as local base IDs. Flora identity checks do not certify serialized FLOR contents or harvest behavior.

This extends declared-map consistency, not raw-content acceptance: only the selected CONT/MISC class is compared against serialized records. Unselected class content, auxiliary terminal menu/door arrival identities, and unknown future map sections still need their own verification; this is not a complete map allocator audit.

Thirty-eight subcases exposed old false passes for new-class aliases, duplicate sources and baseline reference drift. Seven new test methods cover these plus changed promoted bases, malformed reference IDs and valid external bench keys. All35 distinct audit tests pass. One current actual-writer test creates a mixed CONT/MISC/ACTI/TERM build; both read-only CLI audits pass, each pinning four inputs. Deliberately aliasing an ACTI reference to the selected CONT/MISC reference passes the old auditor and is refused by the corrected one. Failed/passing evidence is preserved privately; no game assets, native tests or producer changes.
