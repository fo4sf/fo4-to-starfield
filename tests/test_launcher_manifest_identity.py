"""Manifest metadata agreement is distinct from hashed input-content identity."""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fo4sf.launcher import manifest

spec = importlib.util.spec_from_file_location("launcher_manifest_identity_cli", ROOT / "scripts/launcher.py")
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


class ManifestIdentityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def capture(self, name, version=1, payload=b"AAAAAAAA", hashed=False):
        data = self.root / name
        data.mkdir()
        (data / "Fallout4.esm").write_bytes(b"synthetic master")
        archive = data / "Fallout4 - Meshes.ba2"
        # Capture only reads the eight-byte header, not a claimed valid game archive.
        archive.write_bytes(b"BTDX" + struct.pack("<I", version) + payload)
        os.utime(archive, ns=(1700000000000000000, 1700000000000000000))
        return {"schema": 1, "fo4": manifest.fo4_inputs([str(data)], hashed), "tools": {}}

    def diff_cli(self, a, b):
        paths = [self.root / "a.json", self.root / "b.json"]
        for path, value in zip(paths, (a, b)):
            path.write_text(json.dumps(value), encoding="utf-8")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = cli.main(["manifest-diff", *map(str, paths)])
        return status, output.getvalue()

    def test_recorded_header_versions_differ_with_same_size_and_no_hash(self):
        a = self.capture("a")
        for version in (7, 8):
            with self.subTest(version=version):
                b = self.capture(f"b{version}", version=version)
                diffs = manifest.compare_inputs(a, b)
                self.assertEqual(len(diffs), 1)
                self.assertIn("BA2 version", diffs[0])
                status, output = self.diff_cli(a, b)
                self.assertEqual(status, 1)
                self.assertIn("BA2 version", output)

    def test_version_is_compared_even_when_declared_hashes_match(self):
        a = self.capture("a", hashed=True)
        b = copy.deepcopy(a)
        b["fo4"]["archives"]["Fallout4 - Meshes.ba2"]["ba2_version"] = 8
        self.assertTrue(any("BA2 version" in line for line in manifest.compare_inputs(a, b)))

    def test_same_unhashed_metadata_with_different_bytes_is_qualified(self):
        a = self.capture("a", payload=b"AAAAAAAA")
        b = self.capture("b", payload=b"BBBBBBBB")
        self.assertEqual(manifest.compare_inputs(a, b), [])
        status, output = self.diff_cli(a, b)
        self.assertEqual(status, 0)  # No detected compared differences, not a content-proof gate.
        self.assertIn("content identity unverified", output)
        self.assertIn("archive Fallout4 - Meshes.ba2", output)
        self.assertNotIn("same inputs and pins", output)

    def test_one_sided_missing_hash_keeps_difference_and_qualification(self):
        a = self.capture("a", hashed=True)
        b = copy.deepcopy(a)
        del b["fo4"]["archives"]["Fallout4 - Meshes.ba2"]["sha256"]
        status, output = self.diff_cli(a, b)
        self.assertEqual(status, 1)
        self.assertIn("size or hash differs", output)
        self.assertIn("content not compared", output)

    def test_unhashed_game_master_is_not_hidden_by_hashed_archives(self):
        a = self.capture("a", hashed=True)
        a["game"] = {"files": {"Data/Starfield.esm": {"size": 16, "mtime_ns": 1}, "sfse_loader.exe": None}}
        status, output = self.diff_cli(a, copy.deepcopy(a))
        self.assertEqual(status, 0)
        self.assertIn("content identity unverified", output)
        self.assertIn("game Data/Starfield.esm", output)
        self.assertNotIn("game sfse_loader.exe", output)

    def test_fully_hashed_match_still_ignores_paths_and_timestamps(self):
        a = self.capture("a", hashed=True)
        b = copy.deepcopy(a)
        for table in (b["fo4"]["masters"], b["fo4"]["archives"]):
            for identity in table.values():
                identity.update(path="elsewhere", mtime_ns=2)
        self.assertEqual(manifest.compare_inputs(a, b), [])
        status, output = self.diff_cli(a, b)
        self.assertEqual(status, 0)
        self.assertIn("compared input identities and pins match", output)
        self.assertNotIn("unverified", output)

    def test_full_game_and_archive_hashing_is_explicit_opt_in(self):
        self.capture("source")
        game = self.root / "game"
        (game / "Data").mkdir(parents=True)
        (game / "Starfield.exe").write_bytes(b"synthetic exe")
        esm = game / "Data/Starfield.esm"
        esm.write_bytes(b"synthetic game master")
        for hashed in (False, True):
            with self.subTest(hashed=hashed):
                target = self.root / f"capture-{hashed}.json"
                argv = ["manifest", "--out", str(target), "--fo4-data", str(self.root / "source"),
                        "--starfield", str(game)]
                if hashed:
                    argv += ["--hash-archives", "--hash-game-esm"]
                with patch.object(manifest, "tool_pins", return_value={"repo_commit": "test", "repo_dirty": False}), \
                        contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(cli.main(argv), 0)
                captured = json.loads(target.read_text(encoding="utf-8"))
                self.assertEqual("sha256" in captured["fo4"]["archives"]["Fallout4 - Meshes.ba2"], hashed)
                self.assertEqual("sha256" in captured["game"]["files"]["Data/Starfield.esm"], hashed)
                if hashed:
                    self.assertEqual(captured["game"]["files"]["Data/Starfield.esm"]["sha256"],
                                     hashlib.sha256(esm.read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
