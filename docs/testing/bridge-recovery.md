# Bridge deployment recovery (#124)

The observation bridge is a separate installation beside the converted build.
Its `FO4SFBridge.install.json` must retain enough information to recover an
interrupted operation before a fresh runner launch is allowed.

The old installer copied directly to the final plugin path and recorded ownership
afterward. A synthetic interrupted copy left a partial file; uninstall then erased
the empty receipt and left that file untracked. The pinned baseline reproduction
is retained privately; it never touched a real game installation.

The corrected path uses the existing exclusive, SHA-checked artifact publisher.
Sources and packed resource bytes are checked before publication. Each file's
expected identity is recorded before copying, with confirmed publication tracked
separately. Exact Plugins.txt before/intended bytes and profile ownership are
journaled before activation, including reactivation of an existing bridge.

| Boundary | Recovery behavior |
|---|---|
| Bad archive, source drift or invalid temporary copy | Refuse publication |
| Another file appears at the target | Exclusive refusal; preserve it without claiming it |
| Confirmed unchanged file, later copy failure | Roll back that owned publication |
| Partial/unconfirmed/changed target | Retain file and retryable receipt |
| Activation writes and then fails | Restore exact bytes only when still owned |
| Different current user profile | Refuse before config or file cleanup |
| Interrupted completed uninstall | Restore only missing original line multiplicities; retry stays idempotent |
| Legacy untracked file or incomplete coverage | Preserve it and the recovery receipt |

Legacy complete receipts remain usable when both files, packed contents and
source identities validate. A legacy interrupted receipt is never treated as
proof that an untracked file is safe to delete.

Claude's `c50e87c` ordering policy is preserved: the bridge's active line goes
last after experiment ordering and before launch. The new recovery-aware
reactivation caller is integrated, and order refuses incomplete/changed file
ownership. Moving an already active line retains its original uninstall ownership.

Offline tests use temporary game/profile directories and synthetic valid General
BA2 bytes. Independent QA also uses child-process exits at operation boundaries.
These checks establish source recovery behavior, not gameplay, native script
execution, power-loss durability or a solution to the existing final configuration
compare/replace and unlink races (#84/#104). One controller remains required;
the corrected installer has not been deployed to the active game.
