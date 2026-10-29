"""A small cross-process lock on a file path, pure Python, Windows and POSIX (docs/ai/leader-core.md §1).

os.open with O_EXCL creates the lock file atomically; the holder writes its pid and time into it and removes it on
exit. A lock older than stale_s (a crashed holder) is removed and taken; one that cannot be removed (on Windows, a
holder that still runs keeps it open) is waited for like any other. Waiting longer than timeout_s raises TimeoutError
(an OSError), so a caller refuses rather than hangs. Every writer of the ledger and of the lease file
takes the lock around its read-decide-write, so two processes (the runner, lease.py from a PowerShell script, the
importer) never interleave inside one of them.
"""
import contextlib
import os
import time


@contextlib.contextmanager
def locked(path, timeout_s=5.0, stale_s=30.0, poll_s=0.02):
    deadline = time.monotonic() + timeout_s
    fd = None
    while fd is None:
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                age = time.time() - os.stat(path).st_mtime
            except OSError:                                # released between the two calls
                continue
            if age > stale_s:
                try:
                    os.unlink(path)                        # a crashed holder's lock
                    continue
                except OSError:                            # still open: its holder runs, so wait for it as for any
                    pass
            if time.monotonic() > deadline:
                raise TimeoutError(f"{path}: held by another process for {age:.0f} s")
            time.sleep(poll_s)
    try:
        os.write(fd, f"{os.getpid()} {time.time():.0f}\n".encode("ascii"))
        yield
    finally:
        os.close(fd)
        try:
            os.unlink(path)
        except OSError:
            pass
