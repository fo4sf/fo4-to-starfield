# Independent container output evidence

`scripts/testing/container_records.py` audits the native container entries emitted
by the current TerrainOverlays cluster writer. It reads completed, immutable
staging inputs and writes a new private report. It never installs or starts a game.

```powershell
python -B scripts/testing/container_records.py `
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

Checks bind each source container to its mapped CONT/REFR pair using the actual
TES4 master order. They compare editor ID, inline Windows-1252 name, model path,
CNTO inventory entries, reference base, finite local position/rotation, scale,
active temporary placement, actual world/cell ancestry and cell grid. There
must be exactly one placement for each container base. Duplicate record IDs,
aliased/missing pair IDs, duplicated source entries and ordinary placements
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
surviving identities cannot change; missing ordinary identities fail except
the references explicitly promoted by this cluster. This is a comparison of
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
surviving reference IDs. That failure remains. Counts alone had accepted
changed container XYZ/base/scale and missing inventory; synthetic byte-level
controls now reject those changes.

This is complementary offline evidence. External inventory form types, asset
dependencies, animation, activation, physics, merged runtime positions,
save/reload and persistent inventory behavior need their own evidence. Claude
owns the producer/caller integration, corrected allocation and native tests.
