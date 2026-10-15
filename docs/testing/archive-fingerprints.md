# Archive fingerprint stability (#117)

The resume identity remains `[resolved path, size, SHA-256]`. A different source
payload invalidates the resume signature even when its size and timestamps match.

On Windows, `archive_identity` opens an existing source with `GENERIC_READ` and
`FILE_SHARE_READ`, holds that handle through hashing and the final path check, and
then closes it. Readers remain compatible. Existing writers or writable mappings
refuse the fingerprint before reading; new write/delete/rename opens are denied
while it runs. Acquisition failure propagates as `OSError`; there is no permissive
fallback or retry that accepts a busy archive.

This addresses a reproduced equal-metadata counterexample: a synthetic six-byte
overwrite after hashing could return the previous digest. The deterministic fixture
simulates unchanged metadata; it does not claim every Windows write hides its times.
Two earlier Windows suites also retained failures in the ordinary concurrent-write
test. Passing an isolated retry did not resolve them.

The [Microsoft sharing contract](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew)
defines the guard, including writable mappings and deletion/rename access.
[File-time documentation](https://learn.microsoft.com/en-us/windows/win32/sysinfo/file-times)
explains why timestamp checks alone cannot supply isolation. CRT descriptor/stream
ownership is transferred once; failures close whichever layer currently owns it.

Run synthetic checks with `python -m unittest discover -s tests -p test_archive_identity.py -v`.
Windows cases cover equal metadata, an independent reader/writer process, existing
writer and mapping, handle-transfer/read failures, missing files and an extended
Unicode path. The existing signature test checks edits between calls.

This is a guard during one fingerprint, not a snapshot of the conversion run.
Sources must remain immutable after return. Other platforms keep the existing
best-effort metadata checks and do not gain enforced exclusion of uncooperative
writers. No game-format, installation, saved-game or runtime acceptance claim follows.
