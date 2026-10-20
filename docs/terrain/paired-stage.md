# Paired offline door generations

Codex, October 19. The owner authorized this isolated source extension of #280.
It connects the reviewed #378 reservation callers to the real core stage/check
and port patch/check commands. Claude retains integration, deployment and game
control. No private stage has been rebuilt by this change.

## Pin and run

Start with an explicitly initialized, independently verified #281 marker store.
Never initialize a replacement store beside existing generations. Preserve the
latest state SHA256 outside both the store and generation folders; reading an
untrusted rolled-back store to choose its own expected hash defeats that guard.

A JSON spec supplies absolute paths for `work`, `core` (terrain input), `port`
(unmodified interior input), `cluster` (one merged cluster containing doors),
`sf_esm` and `sf_data`. `sf_esm` must be `sf_data/Starfield.esm`. Optional keys
are `navmesh` (absolute path) and `views` (boolean). Relative paths and unknown
options refuse. This entrypoint never accepts installer or game commands.

```powershell
python scripts/terrain/paired_stage.py pin --spec SPEC.json --out REQUEST.json
python scripts/terrain/paired_stage.py run --request REQUEST.json --request-sha256 REQUEST_HASH --store STORE --state-sha256 EXTERNAL_STATE_HASH --out NEW_GENERATION
```

`pin` writes a new immutable request and prints its hash. It hashes full input
trees (including directory membership), tracked/untracked source build inputs,
Python/dotnet executables and dotnet runtime information. Full game trees can be
expensive to hash; this is a correctness protocol, not a performance result.
Inputs and writer pins are checked again during generation. A changed build or
source needs a fresh request, not edited old hashes.

The generation must be outside every input, store and repository. The store
must also be outside those inputs. A single marker-store session reserves IDs
before either publication and stays held through real core generation/checking
and the real interior patch/check. Both command callers receive the same Plan.
Removed sources retain their reservations; emitted HEDR uses actual records,
not the retained ledger high-water mark. Existing non-paired commands remain
available for legacy input, but refuse planned clusters/paired core metadata
without the live paired session.

## Receipts and recovery

Each generation gets exclusive immutable `intent.json`, `reserved.json` and
`cluster.json`. The store also retains immutable paired-intent registrations;
an unfinished registered leaf blocks an ordinary new run. Only an explicitly
pinned retry supersedes it, retaining the old registration and outputs. Core/port outputs have separate directories. Core artifacts
are pinned immediately after their check and must remain identical through
port checking. `complete.json` is published only after both checks and the
reservation session's exit validation succeed. Its hash must also be preserved
independently when transferring the build. It is **not** a two-file atomic
transaction, an installed-build receipt, or native acceptance.

```powershell
python scripts/terrain/paired_stage.py verify --out GENERATION --completion-sha256 COMPLETION_HASH --store STORE --state-sha256 EXTERNAL_STATE_HASH
```

This read-only verification requires the original writer/input pins, latest
externally selected state hash and exact checked output bytes. It does not
upgrade old native results or repair drift.

A raised failure leaves the intent, reserved IDs, partial outputs and
`failure.json`. An abrupt process death may leave no failure receipt; absence
of `complete.json` is still incomplete. Never clear output controls or delete
partial generations to retry. Resolve an interrupted reservation preparation
with #281's separately pinned explicit recovery first, when necessary.

```powershell
python scripts/terrain/paired_stage.py run --request REQUEST.json --request-sha256 REQUEST_HASH --store STORE --state-sha256 LATEST_EXTERNAL_STATE_HASH --out ANOTHER_NEW_GENERATION --retry-of FAILED_GENERATION --retry-sha256 ORIGINAL_INTENT_HASH
```

Retry verifies the old intent/store/request, retains a manifest of the old
partial bytes, and builds into another fresh folder. It never overwrites the
failed generation, rolls back state, recycles IDs or silently continues an
old publication. Completed generations refuse failed-retry treatment. A
changed source/writer request is a fresh campaign, not this retry operation.

## Evidence boundaries

Synthetic tests use the actual TerrainOverlays writer to produce a core ESM,
actual raw door checks, and both actual port commands with a retained gap and
nonzero offset. The small terrain fixture adapts the core command's asset and
terrain survey environment; it is not a full private `check_stage` acceptance.
Production dispatch calls the unmodified core stage/check implementations with
added paired-session guards. A freshly pinned full-size paired build, current
PEX/archive validation and native outside/inside/return/save/reload remain
required. Independent source QA is required before lead integration.

Runtime launcher aliases are resolved before hashing their actual binary,
so installed Python/dotnet symlinks work on Linux. Rechecking pins resolves the
launcher again, so retargeting changes identity/hash and refuses the old request.
This runtime-only resolution does not relax source/state reparse protections.
