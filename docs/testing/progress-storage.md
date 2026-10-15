# Preserve progress, then reclaim storage

The private progress archive contains original screenshot/recording bytes, reports, plans,
code revisions and checksums. It is separate from Git. GitHub receives source, synthetic
tests and selected small progress images; no extracted/converted game assets or saves.
Keeping something only in a temporary directory is not an archival policy.

## Completed evidence

Use `scripts/archive_progress.py` on an explicitly identified, inactive evidence directory.
Choose an archive destination outside the source tree and repository, preferably another
drive. Create the destination directory first. No file is deleted by this tool.

```powershell
python scripts/archive_progress.py create --source <completed-evidence> --archive <private-archive.zip>
python scripts/archive_progress.py verify --archive <private-archive.zip> --source <completed-evidence>
```

The capsule records every relative path, original byte count, SHA-256 and timestamp. It
reopens/decompresses every archived member, verifies hashes and rechecks the source before
publishing without overwriting an existing archive. Linked/reparse paths, unreadable files,
changed sources and extra/duplicate archive members refuse verification. Compression is
lossless; viewing thumbnails never replace native evidence. The final capsule is a snapshot,
not a claim that a live writer cannot modify the source afterward.

Record its location, SHA-256, verification date, source revision/campaign and retention reason
in a private index. Preserve that index beside the working evidence, so another agent can
find it. A second local drive is local storage, not an offsite/cloud backup. Don't claim an
upload or redundant backup unless it has actually been verified.

## Cleanup

Review exact absolute paths and ownership first. Remove only inactive, independently
regenerable build outputs/caches after a verified capsule and a final unchanged-source
check. Record exact reclaimed bytes and a removal receipt. Never infer disposability from
an age threshold or an extension. No automatic deletion is part of the capsule tool.

Native campaigns/source pins stay at their original locations while a reviewer, runner or
controller depends on them. Retiring those paths needs explicit coordination and updated
evidence references. Active queues, saves, installation receipts, STOP/Guardian controls,
unresolved recovery files and another agent's working files are not cleanup candidates.

To restore a capsule, verify it and expand it into a **new** directory; compare its manifest
before using it. Do not expand over newer owner files or an active installation.

```powershell
python scripts/archive_progress.py verify --archive <private-archive.zip>
Expand-Archive -LiteralPath <private-archive.zip> -DestinationPath <new-restore-directory>
```

## Configuration recovery is separate

`.fo4port-config-*` directories retain file objects that an old editor handle may still
write. Resolve/merge them with game/editors closed using the
[configuration recovery procedure](plugin-config-recovery.md), then archive them outside
the active configuration folder. They are not disposable caches and aren't swept by age.
An archive does not itself resolve a blocked recovery transaction or clear uninstall ownership.
