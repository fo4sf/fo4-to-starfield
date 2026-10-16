# Recoverable terrain plugin/map publication

Codex proposal, stacked on PR150. Source-only; independent peer QA and Claude's integration are required. No game,
production stage, install, save or controller changed. The original locked-file failure is preserved privately.

TerrainOverlays wrote `formids.json` before attempting the final plugin write. A synthetic Windows sharing-denial
reproduced the inconsistent result: the old plugin survived while its map was replaced with a different generation.
The optional Mars output could likewise fail after earlier outputs had already changed.

## Protocol

1. Acquire an exclusive cooperating-writer lease, snapshot existing artifact hashes under read handles and create
   `FO4SF.terrain-output.pending.jsonl`. Existing pending state is refused, never cleared automatically.
2. Serialize the main plugin, optional map and optional Mars plugin in `.fo4sf-output-<id>/new`. Prepare all of them
   before changing canonical outputs. Validate destination names and recheck original hashes before publication.
3. Move previous files to that transaction's `old` folder, then publish new files without overwriting a newly
   created destination. Retain old/new snapshots and append full journal records through each phase.
4. On success, verify all new hashes and move the journal to `committed.jsonl`. On a recoverable failure, withdraw
   proven new files, restore prior files and retain `rolled-back.jsonl`. No artifact/history is deleted.
5. Changed or unproven destination files are preserved. Incomplete rollback retains the pending journal and recovery
   directory. An abrupt process exit also leaves the journal. Its last complete JSON line remains available if the
   final append tears; recovery must inspect filesystem contents/hashes as well as recorded progress flags.

This is a recoverable multi-file publication, **not an atomic snapshot for arbitrary readers**. `stage_outputs.py`
refuses a pending journal or lease before native deployment, experiment install/inventory, core parameter reads and
cave stage/check operations. Integrate producer and consumer guards together. Legacy stages without markers retain
their behavior. Old runners that lack these guards must not consume an in-progress or interrupted new publication.

The guard raises `PendingPublication`, an `OSError` subclass, for either control path. The runner's existing
`experiment_mismatch` handler can then record a stopped checkpoint and log the unavailable stage instead of
crashing with `state.json` still at `running`. Independent review #191 reproduced that former `ValueError`
failure. Both journal and lease cases now stop before any launch/input or inventory hashing and preserve the
control bytes. The tested caller has the same syntax tree as current main `aa5b223`'s mismatch handler.

Planning helpers are outside the guarded consumer list: plan only against a quiescent pinned stage. This error
contract fix does not turn planning or arbitrary path readers into a coherent snapshot.

Windows read-sharing handles deny writable opens/mappings while allowing guarded renames. Other platforms retain
the immutable-input/cooperating-writer requirement. The tests establish process/IO failure behavior, not a universal
power-loss guarantee. No automatic recovery may overwrite an owner's concurrent file or silently remove a journal.

## Evidence and reproduction

`test_terrain_output_publication.py` exercises the real linked helper and the real writer on generated synthetic
inputs: successful three-file publication, failure after the first file, concurrent owner destination, abrupt exit,
native Windows locked-plugin failure, optional-Mars preparation failure, and successful real Mars registration. Previous bytes, per-attempt inputs and
receipts are retained when `FO4SF_IDENTITY_EVIDENCE_DIR` names a new scratch directory. No game data is copied/read.

`test_stage_outputs.py` checks early consumer refusal, malformed/directory markers, legacy input and isolated CLI
imports. Deployment, experiment, core, cave and serialized-reference regressions are also run. .NET 9 SDK/runtime is
required for the actual writer tests; native Windows sharing denial skips explicitly on other platforms.
The #191 correction passes five stage-guard tests and 88 synthetic runner tests; C# publication code is unchanged.
Cloud peer review found the publication/rollback protocol sound by reading; fresh review of this correction and
PC integration remain separate gates. Interrupted full-size rollback remains unmeasured.

```powershell
python -B -m unittest discover -s tests -p test_terrain_output_publication.py -v
python -B -m unittest discover -s tests -p test_stage_outputs.py -v
```

Private evidence: `test-plans/terrain-output-publication-20261015`. The original mixed-generation failure and corrected
fault cases are distinct. A full-size private author run at `105a10ca` also published all three outputs with a
committed receipt whose hashes match the actual plugin/map/Mars bytes. The initial 2 GiB heap-limited OOM and its
transaction directory remain intact; a fresh 3 GiB candidate completed in 18.02 s. See
[full-size identity evidence](container-reference-identities.md#full-size-private-author-validation-october-15-mountain--october-16-utc).
This does not establish interrupted full-size recovery or native gameplay acceptance; peer QA/integration remain open.

## Recovery and retention

Preserve the pending journal, transaction folder, inputs and canonical artifacts; compare them with the recorded
hashes before choosing a repair. Do not delete a marker to make installation proceed. A fresh separate candidate
folder permits independent work while an ambiguous old folder stays blocked for review. Prior outputs and failed
candidates are deliberately retained for verified private archiving; use the progress-storage workflow before any
cleanup. These local copies are not offsite backup.
