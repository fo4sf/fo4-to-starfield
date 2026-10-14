# Recoverable Plugins.txt updates (#84)

Conditional configuration writes and removals preserve the file present at the final
operation boundary. The earlier compare-then-replace/unlink could discard an owner edit
made after comparison. Four synthetic boundary regressions fail against the previous code.

## Operation

Every conditional operation creates a unique `.fo4port-config-*` directory next to
Plugins.txt. It writes/fsyncs `intended.txt` and a prepared `transaction.json`, and tests
hard-link support before moving any current configuration. Unsupported filesystems refuse
the update with the target unchanged; there is no destructive fallback.

For an existing target, the operation moves the actual pathname to `before.txt`, then
compares those captured bytes with the expected configuration. A mismatch refuses the
update. Restoration creates a hard link only if the target is absent; a newer file at
Plugins.txt is preserved alongside the captured file. Publication similarly creates a
hard link without replacing an existing pathname. Removal retains `before.txt` rather
than unlinking the configuration bytes. Successful and failed operations retain their
files and journals, including writes that finish through an old editor handle later.

The journal records the target, write/remove operation, expected/intended SHA-256, and
prepared/published/removed/interrupted status. Its hashes describe the supplied byte
snapshots, not a guarantee that an open editor cannot subsequently modify a linked file.
`before.txt` and `intended.txt` are retained file objects, not immutable copies.

## Recovery

On an error, the message names the recovery directory. Deployment recovery manifests
retain plugin cleanup ownership when configuration recovery fails. Do not clear
`plugins_restore_pending` merely because a successful installation retained it: it also
records uninstall ownership.

Prepared transactions, failed restorations and unreadable journals with captured files
block further configuration updates and recovery shortcuts. A missing target therefore
cannot be mistaken for successful restoration of an originally absent file. This is a
retry guard, not a lock that excludes every concurrent deployment process.

The integration installer's `ConcurrentUpdateError` contract is retained only for a refusal
before publication with no capture, or a captured owner file safely restored at the target.
Publication attempts or unavailable/conflicting restorations raise ordinary OSError instead,
so consumers retain cleanup ownership rather than treating a partial update as untouched.
Capture attempts are tracked explicitly. Metadata inspection distinguishes actual absence
from access failures; inaccessible journals, snapshots or configuration paths block recovery
and cannot produce a safe conflict exception by being mistaken for absent files.

After a process stops, inspect transaction.json, the current Plugins.txt, before.txt when
present, and intended.txt. Close the game and editors that hold these files before
comparing/merging. Preserve the owner's newer entries. A prepared journal may have an
absent target after capture, or a published target after a crash immediately following
publication. No automatic replay overwrites an existing target. Keep the recovery files
until their contents have been reviewed and merged; automatic cleanup is deliberately absent.
After resolving a blocked transaction, archive its entire recovery directory outside the
active configuration folder, preserving the files. This removes it from the retry guard's
scan without deleting evidence. Successful transactions do not block later operations.

## Limits and evidence

The target filename can briefly be absent between capture and publication. This changes
the conditional helper's name-visibility behavior; unconditional atomic writes still use
one replace. Deployment requires a closed game and one controller. This is recoverable
publication, not compare-and-swap or an interprocess deployment lock. Power-loss durability,
network filesystems and writers that modify the private recovery directory are unverified.

Synthetic tests cover final write/removal races, a newly created owner file, a late writer
to the captured file, interrupted journals, unsupported links, restoration failure and
actual helper-process exits after capture/publication. Existing deployment rollback tests
remain required. These tests use temporary bytes and never touch a game installation.

Python exposes [hard-link creation](https://docs.python.org/3/library/os.html#os.link).
Microsoft documents its [Windows hard-link API and filesystem constraints](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-createhardlinkw).
The preflight verifies support at the actual destination before capture.
