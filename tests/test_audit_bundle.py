"""Synthetic-only unit tests for dotnet/AuditBundle (B1 read-only record audit tool)."""

from __future__ import annotations

import pathlib
import subprocess
import tempfile
import unittest

REPO = pathlib.Path(__file__).resolve().parent.parent
CSPROJ = REPO / "dotnet" / "AuditBundle" / "AuditBundle.csproj"


class TestAuditBundle(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        res = subprocess.run(
            ["dotnet", "build", str(CSPROJ), "-v", "quiet"],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode != 0:
            raise RuntimeError(f"dotnet build AuditBundle failed:\n{res.stdout}\n{res.stderr}")

    def test_synthetic_selftest_passes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fo4sf_audit_selftest_") as tmp:
            res = subprocess.run(
                ["dotnet", "run", "--no-build", "--project", str(CSPROJ), "--", "selftest", tmp],
                cwd=str(REPO),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(
                res.returncode,
                0,
                msg=f"AuditBundle selftest failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}",
            )
            self.assertIn("audit-bundle selftest OK", res.stdout)

    def test_refuses_writing_inside_git_repo(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fo4sf_audit_guard_") as tmp:
            tmp_path = pathlib.Path(tmp)
            bundle = tmp_path / "bundle"
            bundle.mkdir()
            port = tmp_path / "FO4Port.esm"
            port.write_bytes(b"")
            mm = tmp_path / "FO4SFMapMarkers.esm"
            mm.write_bytes(b"")
            bad_out = REPO / "docs" / "_should_never_write_audit.json"
            res = subprocess.run(
                [
                    "dotnet",
                    "run",
                    "--no-build",
                    "--project",
                    str(CSPROJ),
                    "--",
                    "audit-bundle",
                    str(bundle),
                    str(port),
                    str(bad_out),
                    "--map-markers",
                    str(mm),
                ],
                cwd=str(REPO),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(res.returncode, 0)
            self.assertFalse(bad_out.exists(), "output file must never be created inside Git repo")
            self.assertIn("Refusing to write audit output inside Git repository", res.stderr)


if __name__ == "__main__":
    unittest.main()
