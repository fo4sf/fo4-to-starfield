"""Archive checkpoint identities detect content edits, not just metadata."""
import os
import mmap
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fo4sf import checkpoints


class ArchiveIdentityTests(unittest.TestCase):
    def test_same_size_edit_with_restored_timestamp_changes_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "synthetic.ba2"
            archive.write_bytes(b"first archive payload")
            original_stat = archive.stat()
            original_identity = checkpoints.archive_identity(archive)

            archive.write_bytes(b"other archive payload")
            os.utime(archive, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
            changed_stat = archive.stat()

            self.assertEqual(changed_stat.st_size, original_stat.st_size)
            self.assertEqual(changed_stat.st_mtime_ns, original_stat.st_mtime_ns)
            self.assertNotEqual(original_identity, checkpoints.archive_identity(archive))

    def test_stable_archive_identity_contains_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "synthetic.ba2"
            archive.write_bytes(b"synthetic immutable archive")

            identity = checkpoints.archive_identity(archive)

            self.assertEqual(identity[0], str(archive.resolve()))
            self.assertEqual(identity[1], archive.stat().st_size)
            self.assertEqual(identity[2], checkpoints.digest(archive))
            self.assertEqual(identity, checkpoints.archive_identity(archive))

    def test_archive_modified_during_hash_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "synthetic.ba2"
            archive.write_bytes(b"before")
            hash_open_file = checkpoints._hash_open_file

            def mutate_after_read(stream):
                result = hash_open_file(stream)
                # Size makes the metadata regression deterministic on platforms
                # without enforced Windows sharing, even on coarse clocks.
                archive.write_bytes(b"different length")
                return result

            with patch.object(checkpoints, "_hash_open_file", side_effect=mutate_after_read):
                with self.assertRaises(OSError):
                    checkpoints.archive_identity(archive)


@unittest.skipUnless(os.name == "nt", "Windows enforced sharing")
class WindowsArchiveSharingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="archive-sharing-")
        self.addCleanup(self.tmp.cleanup)
        self.archive = Path(self.tmp.name) / "synthetic.ba2"
        self.archive.write_bytes(b"before")

    def assert_released(self):
        self.archive.write_bytes(b"after!")
        self.assertEqual(self.archive.read_bytes(), b"after!")

    def test_equal_metadata_cannot_hide_same_size_write_during_hash(self):
        original_stat = self.archive.stat()
        real_hash = checkpoints._hash_open_file

        def mutate(stream):
            digest = real_hash(stream)
            self.archive.write_bytes(b"after!")
            os.utime(self.archive, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
            return digest

        # Emulate metadata whose resolution/cache hides the write. The old
        # implementation returns the digest of 'before' for bytes 'after!'.
        with patch.object(checkpoints, "_hash_open_file", side_effect=mutate), \
                patch.object(os, "fstat", return_value=original_stat), \
                patch.object(Path, "stat", return_value=original_stat):
            with self.assertRaises(PermissionError):
                checkpoints.archive_identity(self.archive)
        self.assertEqual(self.archive.read_bytes(), b"before")
        self.assert_released()

    def test_other_process_can_read_but_cannot_write_rename_or_delete(self):
        child = """
import os, pathlib, sys
p = pathlib.Path(sys.argv[1])
assert p.read_bytes() == b'before'
for operation in (lambda: p.write_bytes(b'after!'),
                  lambda: p.rename(p.with_suffix('.renamed')),
                  lambda: p.unlink()):
    try:
        operation()
    except PermissionError:
        pass
    else:
        raise AssertionError('guard allowed mutation')
"""
        real_hash = checkpoints._hash_open_file

        def check_child(stream):
            self.assertFalse(os.get_inheritable(stream.fileno()))
            result = subprocess.run([sys.executable, "-B", "-c", child, str(self.archive)],
                                    capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return real_hash(stream)

        with patch.object(checkpoints, "_hash_open_file", side_effect=check_child):
            identity = checkpoints.archive_identity(self.archive)
        self.assertEqual(identity[2], checkpoints.digest(self.archive))
        self.assert_released()

    def test_existing_writer_is_refused_before_any_hash_read(self):
        with self.archive.open("r+b"), patch.object(checkpoints, "_hash_open_file") as hash_file:
            with self.assertRaises(PermissionError):
                checkpoints.archive_identity(self.archive)
            hash_file.assert_not_called()
        self.assert_released()

    def test_existing_writable_mapping_is_refused_after_file_handle_closes(self):
        with self.archive.open("r+b") as stream:
            mapping = mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_WRITE)
        try:
            with patch.object(checkpoints, "_hash_open_file") as hash_file:
                with self.assertRaises(PermissionError):
                    checkpoints.archive_identity(self.archive)
                hash_file.assert_not_called()
        finally:
            mapping.close()
        self.assert_released()

    def test_existing_readers_remain_compatible(self):
        with self.archive.open("rb") as reader:
            identity = checkpoints.archive_identity(self.archive)
            self.assertEqual(reader.read(), b"before")
        self.assertEqual(identity[2], checkpoints.digest(self.archive))

    def test_hash_failure_releases_guard(self):
        with patch.object(checkpoints, "_hash_open_file", side_effect=OSError("synthetic read failure")):
            with self.assertRaisesRegex(OSError, "synthetic read failure"):
                checkpoints.archive_identity(self.archive)
        self.assert_released()

    def test_native_to_descriptor_failure_releases_handle(self):
        import msvcrt
        with patch.object(msvcrt, "open_osfhandle", side_effect=OSError("descriptor failure")):
            with self.assertRaisesRegex(OSError, "descriptor failure"):
                checkpoints.archive_identity(self.archive)
        self.assert_released()

    def test_descriptor_to_stream_failure_releases_descriptor(self):
        with patch.object(os, "fdopen", side_effect=OSError("stream failure")):
            with self.assertRaisesRegex(OSError, "stream failure"):
                checkpoints.archive_identity(self.archive)
        self.assert_released()

    def test_missing_archive_is_not_created(self):
        self.archive.unlink()
        with self.assertRaises(FileNotFoundError):
            checkpoints.archive_identity(self.archive)
        self.assertFalse(self.archive.exists())

    def test_unicode_long_path_keeps_identity_format(self):
        # Explicit extended paths also work on hosts without the system-wide
        # long-path opt-in. Cleanup uses that same path namespace.
        folder = Path("\\\\?\\" + self.tmp.name) / ("a" * 100) / ("b" * 100) / ("c" * 40)
        folder.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, folder.parents[1])
        archive = folder / "synthetic-\u00e9.ba2"
        archive.write_bytes(b"synthetic")
        self.assertEqual(checkpoints.archive_identity(archive),
                         [str(archive.resolve()), 9, checkpoints.digest(archive)])


if __name__ == "__main__":
    unittest.main()
