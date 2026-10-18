# Private experiment receipt history

Before ordinary `exp_install` cleanup changes Plugins.txt, removes installed
files or narrows/removes its active receipt, it preserves the written receipt as
`<SHA256-of-uncompressed-receipt>.json.gz`. This retains packed-archive/plugin
hashes, source inventory, publication state and activation metadata after normal
uninstall. Failed/partial-install receipts are retained as such; they do not
become completed-install evidence. These are cleanup-time bytes: uninstall has
already added `cleanup_pending`, so the snapshot hash need not match a receipt
hash captured during the test. Artifact and source identities are retained.

The default directory is `%LOCALAPPDATA%/FO4SF/experiment-receipts` (on systems
without LOCALAPPDATA, `~/.local/state/FO4SF/experiment-receipts`). Set the absolute
private `FO4SF_EXPERIMENT_RECEIPTS` environment path before invoking the deployer
to use a different volume. The game folder and this experiment's staged folder,
including aliases and the physical Data directory behind a junction/symlink,
are refused. Other staging folders are not automatically excluded; choose a
dedicated private evidence directory. The history volume must support hard
links (for example NTFS); unsupported FAT/exFAT volumes and some network shares
can prevent publication. Even without the environment override, cleanup writes
to the default history folder and prints its private path. This source change
does not alter an already-running runner's environment or install anything.

Snapshots are compressed and content-addressed, so identical receipts are
verified and reused. New snapshots are flushed, atomically published without
overwriting another file, reopened and byte-compared before cleanup. For an
ordinary uninstall, failure leaves the active recovery record and
game/configuration bytes available for retry. A corrupt existing snapshot is
preserved and uninstall refuses; investigate and preserve that corruption
before choosing a different private evidence root.
No automatic history pruning is provided. Include the chosen directory in the
private verified progress archive before any later cleanup.

Failed-install rollback has a narrower exception: if history is unavailable
and the original incomplete receipt remains unchanged, rollback still restores
the configuration and removes confirmed, unchanged publications. It retains
the full written inventory, including entries for removed files. Once every
confirmed effect has been undone without errors, it atomically adds a
`rollback_completed` checkpoint to the active receipt. That checkpoint embeds
the exact original receipt bytes as base64 and their SHA256; all original fields
remain unchanged. Publication checks that the active receipt still matches
those original bytes. The checkpoint records completed cleanup, never a
successful installation or native test.

The command reports receipt preservation pending and tells the operator to
restore history availability and run `uninstall`. Until that succeeds, install,
`active` and `order` still refuse the incomplete installation. On retry, a valid
completion checkpoint is archived and retired without replaying its old
Plugins.txt or file cleanup. Later configuration changes and recreated files
(even byte-identical ones) are therefore left alone. The historical snapshot
retains the complete inventory, original bytes and completion outcome.

If checkpoint publication itself fails, the original receipt remains available
and the command warns to leave Plugins.txt and the former experiment paths
unchanged until recovery finishes. Older receipts without a completion
checkpoint cannot retrospectively prove rollback finished; they keep the
existing guarded cleanup rules. Incomplete rollback likewise retains the
original receipt unchanged: concurrent file/configuration edits are preserved
and reported. Corrupt or mismatched completion checkpoints refuse retirement.
A receipt changed during preservation prevents rollback entirely. This is not
a bypass for ordinary uninstall or for the history-preservation requirement.

The active `Data/FO4SFExp.install.json` remains the sole recovery authority.
History is never loaded to resume an install or decide which game files to
remove. A snapshot does **not** establish successful uninstall, engine-loaded
bytes, complete runtime load order, a passed test or hardware power-loss
durability. Existing missing receipts cannot be reconstructed by this change.
Native campaigns must still bind their exact installation and observations.

Receipts contain private local paths and load-order configuration. Keep this
history outside Git/public uploads. It contains metadata, not game assets or
saves. Preserve original verdicts and failed snapshots alongside passing runs.
