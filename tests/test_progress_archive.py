import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile


spec = importlib.util.spec_from_file_location("archive_progress", Path(__file__).parents[1] / "scripts" / "archive_progress.py")
archive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(archive)


class ProgressArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "evidence"
        self.source.mkdir()
        (self.source / "native.png").write_bytes(bytes(range(256)) * 20)
        (self.source / "report.json").write_text('{"accepted": false}', encoding="utf-8")
        self.output = self.root / "capsule.zip"

    def test_original_bytes_and_provenance_round_trip(self):
        manifest = archive.create(self.source, self.output)
        self.assertEqual(archive.check_source(self.output, self.source), manifest)
        with zipfile.ZipFile(self.output) as capsule:
            for name in manifest["files"]:
                self.assertEqual(capsule.read(name), (self.source / name).read_bytes())
        self.assertTrue((self.source / "native.png").exists())

    def test_existing_destination_is_never_overwritten(self):
        self.output.write_bytes(b"previous archive")
        with self.assertRaises(FileExistsError):
            archive.create(self.source, self.output)
        self.assertEqual(self.output.read_bytes(), b"previous archive")

    def test_archive_inside_source_is_refused(self):
        with self.assertRaises(ValueError):
            archive.create(self.source, self.source / "capsule.zip")

    def test_changed_source_blocks_cleanup_verification(self):
        archive.create(self.source, self.output)
        (self.source / "report.json").write_text("new owner edit", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "source changed"):
            archive.check_source(self.output, self.source)

    def test_added_file_blocks_cleanup_verification(self):
        archive.create(self.source, self.output)
        (self.source / "new.txt").write_bytes(b"new evidence")
        with self.assertRaises(ValueError):
            archive.check_source(self.output, self.source)

    def test_wrong_source_root_is_refused(self):
        archive.create(self.source, self.output)
        other = self.root / "other"
        other.mkdir()
        with self.assertRaisesRegex(ValueError, "root differs"):
            archive.check_source(self.output, other)

    def test_change_during_archiving_prevents_publication(self):
        real_verify = archive.verify
        def change_after_verification(path):
            result = real_verify(path)
            (self.source / "report.json").write_bytes(b"changed after compression")
            return result
        with patch.object(archive, "verify", side_effect=change_after_verification):
            with self.assertRaises(ValueError):
                archive.create(self.source, self.output)
        self.assertFalse(self.output.exists())
        self.assertFalse(list(self.root.glob(".progress-*")))

    def test_corrupted_bytes_fail_verification(self):
        archive.create(self.source, self.output)
        with zipfile.ZipFile(self.output) as capsule:
            members = {name: capsule.read(name) for name in capsule.namelist()}
        members["native.png"] = b"damaged screenshot"
        with zipfile.ZipFile(self.output, "w") as capsule:
            for name, content in members.items():
                capsule.writestr(name, content)
        with self.assertRaisesRegex(ValueError, "bytes do not match"):
            archive.verify(self.output)

    def test_unexpected_member_fails_verification(self):
        archive.create(self.source, self.output)
        with zipfile.ZipFile(self.output, "a") as capsule:
            capsule.writestr("unexpected.txt", b"extra")
        with self.assertRaisesRegex(ValueError, "inventory"):
            archive.verify(self.output)

    def test_duplicate_member_fails_verification(self):
        archive.create(self.source, self.output)
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(self.output, "a") as capsule:
                capsule.writestr("native.png", b"duplicate")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            archive.verify(self.output)

    def test_links_are_not_followed(self):
        target = self.root / "outside.txt"
        target.write_bytes(b"outside evidence")
        try:
            os.symlink(target, self.source / "linked.txt")
        except OSError:
            self.skipTest("symlink creation unavailable")
        with self.assertRaisesRegex(ValueError, "links/reparse"):
            archive.create(self.source, self.output)

    def test_windows_reparse_attribute_is_rejected_without_symlink_privileges(self):
        from types import SimpleNamespace
        fake = SimpleNamespace(st_mode=0o100644, st_file_attributes=0x400)
        with patch.object(Path, "lstat", return_value=fake):
            with self.assertRaisesRegex(ValueError, "links/reparse"):
                archive.ordinary(self.source / "native.png")

    def test_reserved_manifest_case_variant_cannot_overwrite_original_on_restore(self):
        (self.source / archive.MANIFEST.upper()).write_bytes(b"original evidence")
        with self.assertRaisesRegex(ValueError, "reserved"):
            archive.create(self.source, self.output)
        self.assertFalse(self.output.exists())
        self.assertEqual((self.source / archive.MANIFEST.upper()).read_bytes(), b"original evidence")

    def test_reserved_manifest_directory_is_refused_even_when_empty(self):
        (self.source / archive.MANIFEST).mkdir()
        with self.assertRaisesRegex(ValueError, "reserved"):
            archive.create(self.source, self.output)

    def test_reserved_manifest_nested_member_is_refused(self):
        folder = self.source / archive.MANIFEST.upper()
        folder.mkdir()
        (folder / "evidence.txt").write_bytes(b"original")
        with self.assertRaisesRegex(ValueError, "reserved"):
            archive.create(self.source, self.output)

    def test_verify_rejects_reserved_alias_in_untrusted_capsule(self):
        import hashlib
        name = archive.MANIFEST.upper()
        data = b"original evidence"
        manifest = {"version": 1, "source": str(self.source), "files": {
            name: {"size": len(data), "sha256": hashlib.sha256(data).hexdigest(), "mtime_ns": 0}}}
        with zipfile.ZipFile(self.output, "w") as capsule:
            capsule.writestr(name, data)
            capsule.writestr(archive.MANIFEST, json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "reserved"):
            archive.verify(self.output)

    @unittest.skipUnless(os.name == "nt", "native Windows junction regression")
    def test_verify_rejects_real_windows_archive_ancestor_junction(self):
        import subprocess
        folder = self.root / "capsules"
        folder.mkdir()
        output = folder / "capsule.zip"
        archive.create(self.source, output)
        junction = self.root / "alias"
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), str(folder)], capture_output=True)
        if result.returncode:
            self.skipTest("native junction creation unavailable")
        try:
            with self.assertRaisesRegex(ValueError, "links/reparse"):
                archive.check_source(junction / "capsule.zip", self.source)
        finally:
            os.rmdir(junction)
        self.assertTrue(output.exists())

    def test_invalid_names_are_rejected(self):
        for name in ("../escape.txt", "/absolute.txt", "folder/../escape", "a\\b", "C:target", "a//b", archive.MANIFEST):
            with self.subTest(name=name), self.assertRaises(ValueError):
                archive.member_name(name)

    def test_no_final_archive_on_publication_failure(self):
        with patch.object(archive.os, "link", side_effect=OSError("unsupported")):
            with self.assertRaises(OSError):
                archive.create(self.source, self.output)
        self.assertFalse(self.output.exists())
        self.assertFalse(list(self.root.glob(".progress-*")))
        self.assertEqual(len(list(self.source.iterdir())), 2)


if __name__ == "__main__":
    unittest.main()
