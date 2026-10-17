# Private experiment receipt history

Before `exp_install` cleanup changes Plugins.txt, removes installed files or
narrows/removes its active receipt, it preserves the exact written receipt as
`<SHA256-of-uncompressed-receipt>.json.gz`. This retains packed-archive/plugin
hashes, source inventory, publication state and activation metadata after normal
uninstall. Failed/partial-install receipts are retained as such; they do not
become completed-install evidence.

The default directory is `%LOCALAPPDATA%/FO4SF/experiment-receipts` (on systems
without LOCALAPPDATA, `~/.local/state/FO4SF/experiment-receipts`). Set the absolute
private `FO4SF_EXPERIMENT_RECEIPTS` environment path before invoking the deployer
to use a different volume. Game and staging directories are refused. This change
does not modify the active runner's environment or install anything.

Snapshots are compressed and content-addressed, so identical receipts are
verified and reused. New snapshots are flushed, atomically published without
overwriting another file, reopened and byte-compared before cleanup. Failure
leaves the active recovery record and game/configuration bytes available for
retry. A corrupt existing snapshot is preserved and cleanup refuses; investigate
and preserve that corruption before choosing a different private evidence root.
No automatic history pruning is provided. Include the chosen directory in the
private verified progress archive before any later cleanup.

The active `Data/FO4SFExp.install.json` remains the sole recovery authority.
History is never loaded to resume an install or decide which game files to
remove. A snapshot does **not** establish successful uninstall, engine-loaded
bytes, complete runtime load order, a passed test or hardware power-loss
durability. Existing missing receipts cannot be reconstructed by this change.
Native campaigns must still bind their exact installation and observations.

Receipts contain private local paths and load-order configuration. Keep this
history outside Git/public uploads. It contains metadata, not game assets or
saves. Preserve original verdicts and failed snapshots alongside passing runs.
